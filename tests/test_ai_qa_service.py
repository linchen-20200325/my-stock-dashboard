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
        _calc_single_quarter_roe, _json_safe, _annotate_staleness,
        _scrub_secrets, _fmt_gemini_error, _tool_get_etf_quality)
except Exception:  # pragma: no cover
    from ai_qa_service import (
        run_agent, discuss, discuss_stock, summarize_tab, PANELS,
        _calc_single_quarter_roe, _json_safe, _annotate_staleness,
        _scrub_secrets, _fmt_gemini_error, _tool_get_etf_quality)


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


# ---- 頻率感知過期標記(v19.127 修季報「已過期100+天」誤報)------------------
def _as_of_days_ago(n):
    from datetime import datetime, timezone, timedelta
    return (datetime.now(timezone.utc) - timedelta(days=n)).date().isoformat()


def test_quarterly_financial_not_flagged_when_latest():
    """複現 bug:季報 as_of=季末,季後~45d 才公告;力積電 Q1(as_of~106d 前)是當期最新一季,
    修前套日頻 7d 門檻 → 誤標「已過期106天」。修後 quarterly 走 150d 門檻 → 不標。"""
    r = _annotate_staleness({"ok": True, "data": {"EPS": 3.36},
                             "provenance": {"source": "FinMind 季報", "as_of": _as_of_days_ago(106),
                                            "cadence": "quarterly"}})
    assert "_stale_days" not in r                       # 當期最新一季不該被標過期


def test_quarterly_financial_flagged_when_truly_overdue():
    """季報若真的停在舊季(>150d,下一季早該公告)→ 仍須標過期(§1 不放水)。"""
    r = _annotate_staleness({"ok": True, "data": {"EPS": 1.0},
                             "provenance": {"as_of": _as_of_days_ago(200), "cadence": "quarterly"}})
    assert r.get("_stale_days") == 200


def test_daily_cadence_unchanged_still_7d():
    """日頻(未宣告 cadence → default daily)維持 7d 門檻:10 天前資料仍標過期(不回歸)。"""
    r = _annotate_staleness({"ok": True, "data": {"x": 1},
                             "provenance": {"as_of": _as_of_days_ago(10)}})   # 無 cadence → daily
    assert r.get("_stale_days") == 10
    # 3 天前(日頻新鮮)→ 不標
    r2 = _annotate_staleness({"ok": True, "data": {"x": 1},
                              "provenance": {"as_of": _as_of_days_ago(3)}})
    assert "_stale_days" not in r2


# ---- 錯誤訊息金鑰洗白 + 429 友善化(v19.128 修 ?key=API_KEY 印到 UI)--------------
def test_scrub_secrets_removes_api_key():
    assert _scrub_secrets("…generateContent?key=AIzaSyABC_123-xyz reason") == \
        "…generateContent?key=*** reason"                          # URL query key 值洗掉
    assert "AIzaSyABC_123-xyz" not in _scrub_secrets("?key=AIzaSyABC_123-xyz")
    assert _scrub_secrets("裸露 AIzaSyABC_123defGHIjklmnop 洩漏") == "裸露 AIza*** 洩漏"  # 裸 AIza 也洗
    assert _scrub_secrets("token=abc123def456&x=1").startswith("token=***")
    assert _scrub_secrets("無金鑰的普通訊息") == "無金鑰的普通訊息"  # 無誤傷


def test_run_agent_429_scrubs_key_and_friendly():
    """複現 bug:429 HTTPError 的 URL 含 ?key=<GEMINI_KEY>;修前整串(含金鑰)被塞進 UI 錯誤。
    修後:金鑰不得出現 + 429 給友善提示。"""
    KEY = "AIzaSyFAKE0123456789ABCDEFGHIJKLMNOPQRS"

    class _Boom:
        def __call__(self, payload):
            raise RuntimeError("429 Client Error: Too Many Requests for url: "
                               "https://generativelanguage.googleapis.com/v1beta/models/"
                               f"gemini-2.5-flash:generateContent?key={KEY}")

    r = run_agent("etf 哪個好?", api_key=KEY, gemini_http=_Boom(), tools={})
    assert r.ok is False
    assert KEY not in (r.error or ""), r.error                     # 金鑰絕不洩漏
    assert "額度" in r.error and "429" in r.error                   # 友善 429 提示


def test_fmt_gemini_error_non_429_scrubbed():
    """非 429 的錯誤也要洗金鑰(仍保留原因供診斷)。"""
    KEY = "AIzaSyFAKE0123456789ABCDEFGHIJKLMNOPQRS"
    out = _fmt_gemini_error("Gemini 呼叫失敗", RuntimeError(f"boom ?key={KEY}"))
    assert KEY not in out and "key=***" in out and "boom" in out


# ---- ETF 品質工具(v19.129 加單檔 ETF 品質評分工具)------------------------------
def test_etf_quality_tool_registered():
    from src.services.ai_qa_service import REAL_TOOLS, TOOLS_SCHEMA
    assert "get_etf_quality" in REAL_TOOLS
    assert any(t["name"] == "get_etf_quality" for t in TOOLS_SCHEMA)


def test_etf_quality_tool_ok_fail_invalid(monkeypatch):
    """包 L2 compute_etf_quality:成功回 mapped 欄位;stars=None(抓失敗/因子全缺)→ Fail-Loud;
    代碼無效 → 不評分即 ok:False。monkeypatch 避免真打 yfinance。"""
    import src.compute.etf as E
    monkeypatch.setattr(E, "normalize_etf_ticker", lambda s: (str(s) + ".TW") if s else "", raising=False)
    # 成功
    monkeypatch.setattr(E, "compute_etf_quality",
                        lambda t: {"stars": 4, "score": 0.72, "weakest": "expense",
                                   "coverage": 0.85, "factors": {"aum": {"val": 1e9, "score": 0.9}}},
                        raising=False)
    r = _tool_get_etf_quality("00878")
    assert r["ok"] and r["data"]["etf_id"] == "00878.TW"
    assert r["data"]["stars"] == 4 and r["data"]["coverage"] == 0.85
    assert r["provenance"]["as_of"] is None                     # ETF 品質無單一 as_of → 不套過期
    # 失敗:stars=None → Fail-Loud(§1 不假裝有分數)
    monkeypatch.setattr(E, "compute_etf_quality", lambda t: {"stars": None, "_err": "4 因子全缺資料"}, raising=False)
    _fail = _tool_get_etf_quality("00878")
    assert _fail["ok"] is False and "全缺" in _fail["error"]
    # 代碼無效 → 不呼叫評分即 Fail-Loud
    assert _tool_get_etf_quality("")["ok"] is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok: {fn.__name__}")
    print(f"\n{len(fns)} 項 golden test 全部通過 ✅")


# ── B-hotfix 2026-07-22:Gemini 503 退避重試(user 回報「AI 總結本頁」503 硬失敗)──
def test_make_default_http_retries_503_then_succeeds(monkeypatch):
    """503(暫時性上游過載)→ 退避重試 → 次次 200 成功。無此 retry 則單次即拋 HTTPError。"""
    import requests
    from src.services.ai_qa_service import _make_default_http

    class _Resp:
        def __init__(self, code, body=None):
            self.status_code, self._body, self.text = code, body or {}, str(body)
        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(f"{self.status_code} Server Error: Service Unavailable for url: x")
        def json(self):
            return self._body

    seq = [_Resp(503), _Resp(200, {"ok": True})]
    calls = {"n": 0}
    def _fake_post(*a, **k):
        calls["n"] += 1
        return seq.pop(0)
    monkeypatch.setattr(requests, "post", _fake_post)
    monkeypatch.setattr("time.sleep", lambda *_: None)   # 不真的睡,測試秒過

    http = _make_default_http("KEY", "gemini-2.5-flash", max_attempts=3)
    out = http({"contents": []})
    assert calls["n"] == 2 and out == {"ok": True}       # 重試 1 次後成功


def test_make_default_http_503_exhausted_raises(monkeypatch):
    """503 連 max_attempts 次 → 用盡才拋(fail-loud §1)。"""
    import pytest as _pt
    import requests
    from src.services.ai_qa_service import _make_default_http

    class _Resp:
        status_code, text = 503, "503"
        def raise_for_status(self):
            raise requests.HTTPError("503 Server Error: Service Unavailable for url: x")
        def json(self):
            return {}
    calls = {"n": 0}
    def _fake_post(*a, **k):
        calls["n"] += 1
        return _Resp()
    monkeypatch.setattr(requests, "post", _fake_post)
    monkeypatch.setattr("time.sleep", lambda *_: None)

    http = _make_default_http("KEY", "m", max_attempts=3)
    with _pt.raises(requests.HTTPError):
        http({})
    assert calls["n"] == 3                                # 試滿 3 次


def test_make_default_http_400_no_retry(monkeypatch):
    """400(永久性 prompt/設定錯)→ 不重試,立即拋。"""
    import pytest as _pt
    import requests
    from src.services.ai_qa_service import _make_default_http

    class _Resp:
        status_code, text = 400, "bad"
        def raise_for_status(self):
            raise requests.HTTPError("400 Bad Request")
        def json(self):
            return {}
    calls = {"n": 0}
    def _fake_post(*a, **k):
        calls["n"] += 1
        return _Resp()
    monkeypatch.setattr(requests, "post", _fake_post)
    monkeypatch.setattr("time.sleep", lambda *_: None)

    http = _make_default_http("KEY", "m", max_attempts=3)
    with _pt.raises(requests.HTTPError):
        http({})
    assert calls["n"] == 1                                # 永久性錯不重試


def test_fmt_gemini_error_503_friendly():
    """503 → 友善提示(不丟原始 HTTPError,且不洩金鑰)。"""
    import requests
    e = requests.HTTPError("503 Server Error: Service Unavailable for url: https://x?key=SECRET")
    msg = _fmt_gemini_error("Gemini 失敗", e)
    assert "503" in msg and "重試" in msg and "SECRET" not in msg
