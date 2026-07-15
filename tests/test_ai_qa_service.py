#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_ai_qa_service.py — AI 分析師 panel + 問答 golden test（v19.121 Phase 1）

不需 GEMINI 金鑰、不需 repo 其他模組（工具與 Gemini 皆注入假物）。驗證:
  聊天 tool-calling / 數字只從工具 / Fail-Loud / panel 輕量單次 / panel 完整管線(3分析師→辯論→風控→報告)
  / 無資料 Fail-Loud / discuss_stock / summarize_tab / Gemini 失敗回報

執行:  pytest tests/test_ai_qa_service.py -q
"""
try:
    from src.services.ai_qa_service import (
        run_agent, discuss, discuss_stock, summarize_tab, PANELS,
        _calc_single_quarter_roe, _json_safe)
except Exception:  # pragma: no cover
    from ai_qa_service import (
        run_agent, discuss, discuss_stock, summarize_tab, PANELS,
        _calc_single_quarter_roe, _json_safe)


class _Http:
    def __init__(self, script):
        self.script, self.calls = list(script), 0

    def __call__(self, payload):
        self.calls += 1
        return self.script.pop(0) if self.script else _t("…")


def _t(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def _fc(name, args):
    return {"candidates": [{"content": {"parts": [{"functionCall": {"name": name, "args": args}}]}}]}


_TOOLS = {
    "get_stock_score": lambda stock_id: {"ok": True, "data": {"total": 82, "grade": "A", "stock_id": stock_id},
                                         "provenance": {"source": "FinMind", "as_of": "2026-07-11"}},
    "get_financial_health": lambda stock_id: {"ok": True, "data": {"毛利率(%)": 55}, "provenance": {"source": "FinMind"}},
    "get_risk_plan": lambda stock_id, capital_twd=1e6: {"ok": True, "data": {"stop_loss": 800},
                                                        "provenance": {"source": "calc"}},
}
_BUNDLE = {"評分": {"ok": True, "data": {"total": 82}, "provenance": {"source": "FinMind", "as_of": "2026-07-11"}}}


# ---- 聊天 -------------------------------------------------------------------
def test_chat_numbers_from_tools():
    g = _Http([_fc("get_stock_score", {"stock_id": "2330"}), _t("2330 評分 82。")])
    r = run_agent("2330 評分?", api_key="x", gemini_http=g, tools=_TOOLS)
    assert r.ok and r.tool_calls[0]["result"]["data"]["total"] == 82 and g.calls == 2


def test_chat_fail_loud():
    def boom(stock_id):
        raise RuntimeError("FinMind quota")
    r = run_agent("2330?", api_key="x", gemini_http=_Http([_fc("get_stock_score", {"stock_id": "2330"}), _t("")]),
                  tools={"get_stock_score": boom})
    assert r.tool_calls[0]["result"]["ok"] is False and "quota" in r.tool_calls[0]["result"]["error"]


def test_run_agent_question_sent_once():
    """契約(v19.126 回歸守門):run_agent 會自行把本次 question 當成新 user turn 接在
    history 之後(contents = _history_to_contents(history) + [question])。呼叫端(tab_ai_chat)
    因此必須傳『append 本次問題之前』的歷史快照;否則同一句被送兩次 → Gemini 收到連續兩個
    相同 user turn(輸入「6239」被串成「62396239」)。此測試釘住:給乾淨歷史時 question 只出現一次,
    且先前歷史不被吃掉。"""
    seen = {}

    class _CapHttp:
        def __call__(self, payload):
            seen["contents"] = payload["contents"]
            return _t("結論")

    hist = [{"role": "user", "content": "先前問題"},
            {"role": "assistant", "content": "先前回答"}]
    r = run_agent("6239 評分?", hist, api_key="x", gemini_http=_CapHttp(), tools=_TOOLS)
    assert r.ok
    user_texts = [p.get("text", "") for c in seen["contents"] if c.get("role") == "user"
                  for p in c.get("parts", []) if isinstance(p, dict)]
    assert sum(t == "6239 評分?" for t in user_texts) == 1, user_texts   # 本次問題只送一次
    assert any("先前問題" in t for t in user_texts)                       # 歷史保留


# ---- panel ------------------------------------------------------------------
def test_panel_lite_single_call():
    g = _Http([_t("小組討論結論")])
    p = discuss("stock", _BUNDLE, mode="lite", gemini_http=g)
    assert p.ok and p.text == "小組討論結論" and g.calls == 1
    assert p.data_bundle["評分"]["data"]["total"] == 82         # 權威數字來自 bundle


def test_panel_full_pipeline():
    g = _Http([_t("基本面"), _t("技術"), _t("風險"), _t("多"), _t("空"), _t("hold"), _t("風控OK"), _t("報告")])
    p = discuss("stock", _BUNDLE, mode="full", gemini_http=g)
    assert p.ok and len(p.per_analyst) == 3 and g.calls == len(PANELS["stock"]) + 5   # 3 分析師+多+空+裁判+風控+報告
    assert p.debate["verdict"] == "hold" and p.risk_review["text"] == "風控OK" and p.text == "報告"


def test_panel_fail_loud_no_llm_call():
    g = _Http([_t("不該被呼叫")])
    p = discuss("stock", {"x": {"ok": False, "error": "來源全敗"}}, mode="lite", gemini_http=g)
    assert p.ok is False and g.calls == 0                       # 無資料 → 不呼叫 LLM,不 fabricate


def test_discuss_stock_and_summarize_tab():
    g = _Http([_t("a"), _t("b"), _t("c"), _t("多"), _t("空"), _t("hold"), _t("風控"), _t("報告")])
    p = discuss_stock("2330", gemini_http=g, tools=_TOOLS, mode="full")
    assert p.ok and p.data_bundle["get_stock_score"]["data"]["total"] == 82 and p.text == "報告"
    p2 = summarize_tab("任意頁", bundle={"重點": {"ok": True, "data": {"x": 1}, "provenance": {}}},
                       gemini_http=_Http([_t("本頁總結")]))
    assert p2.ok and p2.text == "本頁總結"


def test_gemini_failure_reported():
    def bad(payload):
        raise ConnectionError("no net")
    p = discuss("stock", _BUNDLE, mode="lite", gemini_http=bad)
    assert p.ok is False and "Gemini" in (p.error or "")


# ---- 單季 ROE(v19.123 Phase 1.5)------------------------------------------
def test_single_quarter_roe_calc():
    roe = _calc_single_quarter_roe
    assert roe(1000, 10000) == 10.0            # 正常:單季淨利 1000 / 權益 10000 = 10%
    assert roe(-500, 10000) == -5.0            # 虧損:淨利負 → 合法負 ROE(不擋分子)
    assert roe(1000, 0) is None                # 分母 0 → None(§4.4 不 silent ÷0)
    assert roe(1000, -5000) is None            # 分母負(資不抵債)→ None
    assert roe(1000, float('nan')) is None     # NaN 分母 → None(§1 不腦補)
    assert roe(float('nan'), 10000) is None    # NaN 分子 → None
    assert roe(None, 10000) is None            # 缺分子 → None
    assert roe(1000, None) is None             # 缺分母 → None
    assert roe("x", 10000) is None             # 非數字 → None(不 fabricate)


# ---- JSON-safe(v19.124 修 numpy bool 送 Gemini 炸掉)------------------------
def test_json_safe_numpy_serializable():
    import json as _json
    import numpy as _np
    raw = {"ok": True, "data": {"pass": _np.bool_(True), "score": _np.int64(82),
                                "ratio": _np.float64(1.5), "tags": {"x", "y"},
                                "nested": [_np.int64(1), {"b": _np.bool_(False)}]}}
    safe = _json_safe(raw)
    _json.dumps(safe)                           # 不可拋 TypeError(修前 numpy bool/int 會炸)
    assert safe["data"]["pass"] is True
    assert safe["data"]["score"] == 82 and safe["data"]["ratio"] == 1.5
    assert safe["data"]["nested"][1]["b"] is False


def test_run_agent_numpy_tool_result_no_crash():
    """複現 bug:工具回傳含 numpy → functionResponse 送 Gemini 前必須可 json.dumps(修前整段死)。"""
    import json as _json
    import numpy as _np
    tools = {"get_stock_score": lambda stock_id: {
        "ok": True, "data": {"vcp_atr_pass": _np.bool_(True), "total": _np.int64(82)},
        "provenance": {"source": "x"}}}

    class _NumpyHttp:
        def __init__(self):
            self.n = 0

        def __call__(self, payload):
            self.n += 1
            _json.dumps(payload)                # 模擬 requests(json=payload):修前 numpy bool 在此炸
            if self.n == 1:
                return _fc("get_stock_score", {"stock_id": "2330"})
            return _t("2330 評分 82。")

    r = run_agent("2330?", api_key="x", gemini_http=_NumpyHttp(), tools=tools)
    assert r.ok and r.tool_calls[0]["result"]["data"]["total"] == 82


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok: {fn.__name__}")
    print(f"\n{len(fns)} 項 golden test 全部通過 ✅")
