"""批 Z56 —— 新 UI「📖 憑什麼」兩項（客戶 2026-10-13 裁示 B：數值資料異常 → 不下結論）。

A｜AI 問答（Z53A-4）：工具結果有 NaN／±inf 時，L3 `run_agent(stop_on_invalid_number=True)` 停下、
   ⛔ 不送 Gemini，回客戶句；新 UI 紅卡只放客戶句、⛔ 不叫人換問法重送、⛔ 不寫 assistant 歷史。
   旗標 False（舊 UI `tab_ai_chat`）行為逐字不變。
B｜雙演算法對帳卡（Z53B-a5）：新 L3 `services/reconcile_service.py` 接線；每個輸入先擋無效數值；
   與舊面板 `compute_reconcile_rows` 同輸入逐列對帳；旌旗指數改 `jingqi_info` 優先。
"""
from __future__ import annotations

import ast
import json
import math
import pathlib
import re

import numpy as np
import pandas as pd
import pytest
import requests

import src.services.ai_qa_service as ai
import src.services.reconcile_service as RS
from shared.station_specs import invalid_data_text
from shared.ui_state import UI_FAILED, UI_LIVE, UI_MISSING_RETRYABLE
from src.ui.views import page_why as P

ROOT = pathlib.Path(__file__).resolve().parents[1]
NAN, INF = float("nan"), float("inf")
_BAD_VALUES = [NAN, INF, -INF, np.float64("nan"), np.float64("inf")]
_BAD_IDS = ["nan", "+inf", "-inf", "np.float64-nan", "np.float64-inf"]
_NONFINITE_RE = re.compile(r"(?<![A-Za-z])(nan|inf|infinity)(?![A-Za-z])", re.I)


# ══════════════════════════════════════════════════════════════════
# A｜AI 問答
# ══════════════════════════════════════════════════════════════════
class _Http:
    """離線 Gemini：照劇本回；記下每一次 payload。"""

    def __init__(self, script):
        self.script, self.payloads = list(script), []

    def __call__(self, payload):
        self.payloads.append(payload)
        return self.script.pop(0) if self.script else _txt("…")

    @property
    def calls(self):
        return len(self.payloads)


def _txt(t):
    return {"candidates": [{"content": {"parts": [{"text": t}]}, "finishReason": "STOP"}]}


def _fcall(name, args=None):
    return {"candidates": [{"content": {"parts": [{"functionCall": {"name": name, "args": args or {}}}]},
                            "finishReason": "STOP"}]}


def _leading_tool(value):
    return {"get_market_leading": lambda days=7: {"ok": True, "data": {"日期": "2026-10-13", "外資": value,
                                                                     "投信": 12.5},
                                                  "provenance": {"source": "x", "as_of": "2026-10-13"}}}


def _stop_case(value):
    g = _Http([_fcall("get_market_leading", {"days": 7}), _txt("不該被呼叫")])
    r = ai.run_agent("大盤?", api_key="x", gemini_http=g, tools=_leading_tool(value),
                     fail_on_blocked_reply=True, stop_on_invalid_number=True)
    return r, g


def _assert_stops(r, g, items):
    assert r.ok is False
    assert g.calls == 1, "偵測到無效數值後 ⛔ 不得再送 Gemini"
    assert r.invalid_items == tuple(items)
    assert r.error == "".join(invalid_data_text(_i) for _i in items)
    assert r.text == ""


class TestToolItemNames:
    def test_every_real_tool_has_a_name_taken_from_its_schema_description(self):
        desc = {t["name"]: t["description"] for t in ai.TOOLS_SCHEMA}
        assert set(ai.TOOL_ITEM_NAMES) == set(ai.REAL_TOOLS) == set(desc)
        for name, item in ai.TOOL_ITEM_NAMES.items():
            assert item and item in desc[name], f"{name} 的項目名「{item}」不是 TOOLS_SCHEMA 描述裡的既有字串"


class TestStopOnInvalidNumber:
    @pytest.mark.parametrize("value", _BAD_VALUES, ids=_BAD_IDS)
    def test_nonfinite_tool_value_stops_before_the_second_gemini_call(self, value):
        r, g = _stop_case(value)
        _assert_stops(r, g, ["外資"])
        assert [c["name"] for c in r.tool_calls] == ["get_market_leading"]

    def test_english_keys_fall_back_to_the_tool_item_name_nested(self):
        tools = {"get_etf_quality": lambda etf_id: {
            "ok": True, "data": {"etf_id": "0050", "score": 0.7,
                                 "factors": {"aum": {"value": INF}, "beta": [1.0, -INF]}},
            "provenance": {}}}
        g = _Http([_fcall("get_etf_quality", {"etf_id": "0050"})])
        r = ai.run_agent("0050?", api_key="x", gemini_http=g, tools=tools, stop_on_invalid_number=True)
        _assert_stops(r, g, ["ETF 品質評分"])

    def test_nearest_chinese_key_wins_and_items_dedupe_in_order(self):
        tools = {"get_financial_health": lambda stock_id: {
            "ok": True, "data": {"毛利率(%)": NAN, "EPS": np.float64("inf"), "x": {"負債比率(%)": -INF},
                                 "毛利率": 1.0},
            "provenance": {}},
            "get_market_leading": _leading_tool(NAN)["get_market_leading"]}
        both = {"candidates": [{"content": {"parts": [
            {"functionCall": {"name": "get_financial_health", "args": {"stock_id": "2330"}}},
            {"functionCall": {"name": "get_market_leading", "args": {}}}]}, "finishReason": "STOP"}]}
        g = _Http([both])
        r = ai.run_agent("2330?", api_key="x", gemini_http=g, tools=tools, stop_on_invalid_number=True)
        _assert_stops(r, g, ["毛利率(%)", "個股財務體質", "負債比率(%)", "外資"])

    def test_strings_bools_none_are_not_invalid_numbers(self):
        assert ai._invalid_number_items("get_stock_score", {
            "ok": True, "data": {"stock_name": "台積電", "grade": "A", "vcp_atr_pass": True,
                                 "x": None, "日期": "nan", "n": 0, "neg": -1.5}}) == ()

    def test_real_market_leading_tool_with_nan_column(self, monkeypatch):
        """實測來源：先行指標表缺欄被設 NaN、`_jsonable` 放行（調查組 Z53A-4）。"""
        import src.data.macro as dm
        df = pd.DataFrame([{"日期": "2026-10-13", "外資": NAN, "投信": 3.2, "自營": 1.1,
                            "選PCR": 1.05}])
        monkeypatch.setattr(dm, "build_leading_fast", lambda days=7, token=None: df, raising=False)
        g = _Http([_fcall("get_market_leading", {"days": 7})])
        r = ai.run_agent("籌碼?", api_key="x", gemini_http=g,
                         tools={"get_market_leading": ai._tool_get_market_leading},
                         stop_on_invalid_number=True)
        _assert_stops(r, g, ["外資"])

    def test_tool_failure_dict_is_not_treated_as_invalid(self):
        g = _Http([_fcall("get_market_leading"), _txt("無法判斷方向")])
        r = ai.run_agent("x", api_key="x", gemini_http=g,
                         tools={"get_market_leading": lambda days=7: {"ok": False, "error": "空表"}},
                         stop_on_invalid_number=True)
        assert r.ok and r.text == "無法判斷方向" and g.calls == 2 and r.invalid_items == ()


class TestFlagOffIsUnchanged:
    def test_flag_off_still_sends_the_nan_payload_and_requests_still_rejects_it(self):
        """旗標 False（舊 UI）＝ 修前行為：第二輪照送，真的 `requests` 序列化會拋 InvalidJSONError，
        `run_agent` 回「Gemini 呼叫失敗」（修前的那張誤導紅卡就是這樣來的）。"""
        sent = []

        def _real_prepare_http(payload):
            sent.append(payload)
            requests.Request("POST", "https://example.invalid/v1", json=payload).prepare()
            return _fcall("get_market_leading")

        r = ai.run_agent("大盤?", api_key="x", gemini_http=_real_prepare_http,
                         tools=_leading_tool(NAN))
        assert len(sent) == 2
        assert r.ok is False and r.error.startswith("Gemini 呼叫失敗:InvalidJSONError")
        assert r.invalid_items == ()
        with pytest.raises(requests.exceptions.InvalidJSONError):
            requests.Request("POST", "https://example.invalid/v1", json=sent[1]).prepare()

    def test_flag_off_default_and_explicit_false_send_identical_payloads(self):
        outs = []
        for kw in ({}, {"stop_on_invalid_number": False}):
            g = _Http([_fcall("get_market_leading"), _txt("偏強")])
            r = ai.run_agent("x", api_key="x", gemini_http=g, tools=_leading_tool(NAN), **kw)
            outs.append((json.dumps(g.payloads, ensure_ascii=False, default=str), r.ok, r.text, r.error))
        assert outs[0] == outs[1]

    def test_old_ui_caller_does_not_pass_the_flag(self):
        src = (ROOT / "src/ui/tabs/tab_ai_chat.py").read_text(encoding="utf-8")
        assert "stop_on_invalid_number" not in src


class TestNormalPathGolden:
    def test_finite_values_flag_on_equals_flag_off_byte_for_byte(self):
        runs = []
        for flag in (False, True):
            g = _Http([_fcall("get_market_leading", {"days": 7}), _txt("中性偏多。外資買超 12.5 億。")])
            r = ai.run_agent("大盤?", api_key="x", gemini_http=g, tools=_leading_tool(12.5),
                             fail_on_blocked_reply=True, stop_on_invalid_number=flag)
            for p in g.payloads:   # 正常路徑的 payload 一定能被 requests 序列化
                requests.Request("POST", "https://example.invalid/v1", json=p).prepare()
            runs.append((json.dumps(g.payloads, ensure_ascii=False), r.ok, r.text, r.error,
                         r.invalid_items, json.dumps(r.tool_calls, ensure_ascii=False)))
        assert runs[0] == runs[1]
        assert runs[1][1] is True and runs[1][2] == "中性偏多。外資買超 12.5 億。"


def _assert_guard_stops():
    r, g = _stop_case(NAN)
    _assert_stops(r, g, ["外資"])


def test_mutation_removing_the_scan_turns_red(monkeypatch):
    monkeypatch.setattr(ai, "_invalid_number_items", lambda name, result: ())
    with pytest.raises(AssertionError):
        _assert_guard_stops()


# ── A｜新 UI ─────────────────────────────────────────────────────────
class _FakeRes:
    def __init__(self, **kw):
        self.ok, self.text, self.error, self.model = kw.get("ok", True), kw.get("text", ""), \
            kw.get("error"), kw.get("model", "gemini-2.5-flash")
        self.tool_calls = kw.get("tool_calls", [])
        self.invalid_items = kw.get("invalid_items", ())


class TestLoadQa:
    def test_load_qa_passes_both_flags_and_carries_invalid_items(self, monkeypatch):
        import src.services.app_ai_service as aas
        seen = {}

        def _spy(question, history, **kw):
            seen.update(kw)
            return _FakeRes(ok=False, error="外資資料異常，無法計算，不下結論。",
                            tool_calls=[{"name": "get_market_leading"}], invalid_items=("外資",))
        monkeypatch.setattr(aas, "get_gemini_api_key", lambda: "k")
        monkeypatch.setattr(ai, "run_agent", _spy)
        qa = P.load_qa(P.QaRequest(asked=True, question="大盤?"))
        assert seen.get("fail_on_blocked_reply") is True and seen.get("stop_on_invalid_number") is True
        assert qa.invalid_items == ("外資",) and not qa.answered and qa.error

    def test_end_to_end_with_real_run_agent(self, monkeypatch):
        import src.services.app_ai_service as aas
        g = _Http([_fcall("get_market_leading"), _txt("不該被呼叫")])
        monkeypatch.setattr(aas, "get_gemini_api_key", lambda: "k")
        monkeypatch.setattr(ai, "_make_default_http", lambda api_key, model, **k: g)
        monkeypatch.setattr(ai, "REAL_TOOLS", _leading_tool(INF))
        qa = P.load_qa(P.QaRequest(asked=True, question="大盤?"))
        assert g.calls == 1 and qa.invalid_items == ("外資",) and not qa.answered


class TestQaCard:
    def _built(self, items=("外資",)):
        return P.build_qa_card(P.QaReadout(
            asked=True, error="".join(invalid_data_text(_i) for _i in items),
            tool_calls=("get_market_leading",), invalid_items=items))

    def test_red_card_uses_only_the_approved_sentence_and_no_retry_advice(self):
        card, facts, _ = self._built(("外資", "投信"))
        assert card.state == UI_FAILED
        assert card.note.now == P.QA_FAILED_NOW
        assert card.note.why == "外資資料異常，無法計算，不下結論。投信資料異常，無法計算，不下結論。"
        assert card.note.where == P.PANEL_REPORT_WHERE
        assert "換個問法" not in card.note.where and "Gemini" not in card.note.why

    def test_v2_face_excerpt_matches_and_shows_no_nonfinite_text(self):
        built = self._built()
        short, full = P.v2_short_rows(built[0])
        # QA T1：放得下時卡面帶項目名（整句客戶句）
        assert dict(short)[P.V2_WHY_FACT_KEY] == "外資資料異常，無法計算，不下結論。"
        assert dict(short)[P.V2_GUIDE_FACT_KEY] == P.v2_plain(P.PANEL_REPORT_WHERE)
        assert dict(full)[P.V2_WHY_FACT_KEY] == "外資資料異常，無法計算，不下結論。"
        html = P.v2_card_html(*built)
        assert "外資資料異常，無法計算，不下結論。" in html and not _NONFINITE_RE.search(html)

    def test_two_items_that_fit_show_both_on_the_face(self):
        short, _full = P.v2_short_rows(self._built(("外資", "投信"))[0])
        assert dict(short)[P.V2_WHY_FACT_KEY] == \
            "外資資料異常，無法計算，不下結論。投信資料異常，無法計算，不下結論。"

    def test_too_long_falls_back_to_the_generic_excerpt(self):
        items = ("毛利率(%)", "負債比率(%)", "現金佔總資產(%)")
        short, full = P.v2_short_rows(self._built(items)[0])
        assert len(dict(full)[P.V2_WHY_FACT_KEY]) > P.v2_markup.FACT_VALUE_MAX_CHARS
        assert dict(short)[P.V2_WHY_FACT_KEY] == "資料異常，無法計算，不下結論。"

    def test_runtime_candidate_needs_equality_with_the_rebuilt_sentence(self):
        """執行期候選只收「由 `invalid_items` 重組的客戶句、與原文相等、且放得下」—— ⛔ 不靠長相猜。"""
        acc = P._V2_INVALID_WHOLE.accept
        ok = P._InvalidDataNote(now=P.QA_FAILED_NOW, why="外資資料異常，無法計算，不下結論。",
                                where=P.PANEL_REPORT_WHERE, invalid_items=("外資",))
        assert acc("外資資料異常，無法計算，不下結論。", ok)
        for text in ("請立即賣出資料異常，無法計算，不下結論。",
                     "L3 AI 問答（`services.ai_qa_service.run_agent`）拋出例外：外資資料異常，無法計算，不下結論。",
                     "投信資料異常，無法計算，不下結論。"):
            assert not acc(text, ok), text
            plain = P.Note(now=P.QA_FAILED_NOW, why=text, where=P.PANEL_REPORT_WHERE)
            assert not acc(text, plain), text   # 一般 Note（沒帶項目名）一律不收

    @pytest.mark.parametrize("why", [
        "請立即賣出資料異常，無法計算，不下結論。",
        "L3 AI 問答（`services.ai_qa_service.run_agent`）拋出例外：外資資料異常，無法計算，不下結論。"])
    def test_lookalike_text_never_goes_on_the_face_whole(self, why):
        card = P.Card(key="why.qa", label="AI 問答", state=UI_FAILED,
                      note=P.Note(now=P.QA_FAILED_NOW, why=why, where=P.PANEL_REPORT_WHERE))
        face = dict(P.v2_short_rows(card)[0])[P.V2_WHY_FACT_KEY]
        assert face != P.v2_plain(why)
        assert face in ("資料異常，無法計算，不下結論。", P._v2_raised(P.SRC_QA_AGENT))

    def test_c9_exception_card_still_hits_the_raised_candidate_first(self):
        """C9：一般例外紅卡（即使訊息裡夾著像客戶句的字）仍命中「…拋出例外」，⛔ 不被整句候選搶先。"""
        for err in ("RuntimeError('boom')", "ValueError('外資資料異常，無法計算，不下結論。')"):
            card = P.build_qa_card(P.QaReadout(asked=True, error=err))[0]
            assert type(card.note) is P.Note
            assert dict(P.v2_short_rows(card)[0])[P.V2_WHY_FACT_KEY] == P._v2_raised(P.SRC_QA_AGENT)
        why = P.V2_SHORT_ROWS[("why.qa", P.QA_FAILED_NOW)][1]
        assert why.index(P._v2_raised(P.SRC_QA_AGENT)) < why.index(P._V2_INVALID_WHOLE)

    def test_mutation_dropping_the_runtime_candidate_loses_the_item_name(self, monkeypatch):
        key = ("why.qa", P.QA_FAILED_NOW)
        now, why, where = P.V2_SHORT_ROWS[key]
        monkeypatch.setitem(P.V2_SHORT_ROWS, key,
                            (now, tuple(c for c in why if c is not P._V2_INVALID_WHOLE), where))
        with pytest.raises(AssertionError):
            self.test_v2_face_excerpt_matches_and_shows_no_nonfinite_text()

    def test_other_red_card_unchanged(self):
        card, _f, _s = P.build_qa_card(P.QaReadout(asked=True, error="RuntimeError('boom')"))
        assert card.note.where.startswith("可以換個問法再送一次")
        assert dict(P.v2_short_rows(card)[0])[P.V2_GUIDE_FACT_KEY] == \
            "可以換個問法再送一次；若持續失敗，請把上面那行訊息回報給維護者"


def test_apptest_qa_leaf_stops_and_writes_no_assistant_history(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import src.services.app_ai_service as aas

    g = _Http([_fcall("get_market_leading"), _txt("不該被呼叫")])
    monkeypatch.setattr(aas, "get_gemini_api_key", lambda: "k")
    monkeypatch.setattr(ai, "_make_default_http", lambda api_key, model, **k: g)
    monkeypatch.setattr(ai, "REAL_TOOLS", _leading_tool(NAN))
    script = tmp_path / "_z56_qa.py"
    script.write_text("from src.ui.views import page_why as P\nP.render_page_why()\n", encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=180)
    at.run()
    at.chat_input[0].set_value("今天大盤籌碼如何").run()
    assert not at.exception, at.exception
    assert g.calls == 1
    hist = at.session_state[P.SS_QA_HISTORY]
    assert [m["role"] for m in hist] == ["user"], hist
    md = "\n".join(m.value for m in at.markdown)
    assert "外資資料異常，無法計算，不下結論。" in md
    assert "Gemini 呼叫失敗" not in md and "InvalidJSONError" not in md
    qa_cards = [m.value for m in at.markdown if "AI 問答" in m.value and "blk" in m.value]
    assert qa_cards and not any(_NONFINITE_RE.search(c) for c in qa_cards)


# ══════════════════════════════════════════════════════════════════
# B｜雙演算法對帳
# ══════════════════════════════════════════════════════════════════
def _tnx(v):
    return pd.DataFrame({"close": [4.1, v]})


def _full_session(**over):
    s = {"macro_info": {"us10y": {"value": 4.25}},
         "cl_data": {"intl": {"10Y公債殖利率": _tnx(4.27)},
                     "inst": {"外資及陸資": {"net": 35.2}}},
         "jingqi_info": {"avg": 62.0},
         "mkt_info": {"score": 3, "max_score": 5}}
    s.update(over)
    return s


def _rows(session):
    return {r.name: r for r in RS.compute_reconcile(session).rows}


def _mutant_rs(*pairs):
    """`reconcile_service` 原始碼逐組替換（每組恰好一處）後載成獨立模組（不影響本尊）。"""
    import importlib.util
    import sys
    src = pathlib.Path(RS.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, old
        src = src.replace(old, new)
    name = "_z56_rs_mutant"
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    m.__file__ = RS.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, RS.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


class TestInvalidInputs:
    @pytest.mark.parametrize("value", _BAD_VALUES, ids=_BAD_IDS)
    @pytest.mark.parametrize("where,row,item", [
        ("fred", RS.ROW_US10Y, "10Y公債殖利率"),
        ("tnx", RS.ROW_US10Y, "10Y公債殖利率"),
        ("jq", RS.ROW_HEALTH, "旌旗指數"),
        ("score", RS.ROW_HEALTH, "大盤評分"),
        ("max_score", RS.ROW_HEALTH, "大盤評分"),
        ("fnet", RS.ROW_HEALTH, "外資"),
        ("rev", RS.ROW_REV_YOY, "月營收 YoY"),
    ])
    def test_each_input_blocks_only_its_row(self, value, where, row, item):
        s = _full_session()
        if where == "fred":
            s["macro_info"] = {"us10y": {"value": value}}
        elif where == "tnx":
            s["cl_data"]["intl"] = {"10Y公債殖利率": _tnx(value)}
        elif where == "jq":
            s["jingqi_info"] = {"avg": value}
        elif where == "score":
            s["mkt_info"] = {"score": value, "max_score": 5}
        elif where == "max_score":
            s["mkt_info"] = {"score": 3, "max_score": value}
        elif where == "fnet":
            s["cl_data"]["inst"] = {"外資及陸資": {"net": value}}
        else:
            s["t2_data"] = {"rev_yoy_self": value, "rev_yoy_finmind": 3.0}
        rows = _rows(s)
        assert rows[row].invalid_items == (item,) and rows[row].result is None
        for other, r in rows.items():
            if other != row:
                assert r.invalid_items == ()
        text = P.reconcile_row_text(rows[row])
        assert text == invalid_data_text(item) and not _NONFINITE_RE.search(text)

    def test_invalid_row_never_reaches_l2(self, monkeypatch):
        called = []
        monkeypatch.setattr(RS, "reconcile_health_score", lambda *a, **k: called.append(a))
        monkeypatch.setattr(RS, "reconcile_us10y_yield", lambda *a, **k: called.append(a))
        s = _full_session(jingqi_info={"avg": NAN}, macro_info={"us10y": {"value": INF}})
        rows = _rows(s)
        assert called == [] and rows[RS.ROW_HEALTH].invalid_items == ("旌旗指數",)

    def test_several_items_in_one_row_are_listed_in_input_order(self):
        s = _full_session(jingqi_info={"avg": NAN}, mkt_info={"score": INF})
        s["cl_data"]["inst"] = {"外資及陸資": {"net": -INF}}
        assert _rows(s)[RS.ROW_HEALTH].invalid_items == ("旌旗指數", "大盤評分", "外資")

    def test_max_score_invalid_ignored_when_score_missing(self):
        s = _full_session(mkt_info={"max_score": NAN})
        assert _rows(s)[RS.ROW_HEALTH].invalid_items == ()


class TestStringInputs:
    """QA D1：字串輸入 ⛔ 不得讓例外穿到卡層。空字串／空白 ＝ 缺值；轉不成數字 ＝ 資料異常。"""

    @pytest.mark.parametrize("fred", ["", "   "])
    def test_blank_fred_is_missing_not_an_exception(self, fred):
        r = _rows(_full_session(macro_info={"us10y": {"value": fred}}))[RS.ROW_US10Y]
        assert r.invalid_items == () and r.result["status"] == "a_missing"
        card = P.build_reconcile_card(P.load_reconcile(_REQ, _full_session(
            macro_info={"us10y": {"value": fred}})))[0]
        assert card.state == UI_LIVE
        assert dict(P.build_reconcile_card(P.load_reconcile(_REQ, _full_session(
            macro_info={"us10y": {"value": fred}})))[1])[RS.ROW_US10Y].startswith("⬜ 未觸發")

    def test_numeric_string_fred_is_compared(self):
        r = _rows(_full_session(macro_info={"us10y": {"value": "4.25"}}))[RS.ROW_US10Y]
        assert r.result["status"] == "agree"

    def test_non_numeric_string_fred_is_invalid(self):
        r = _rows(_full_session(macro_info={"us10y": {"value": "abc"}}))[RS.ROW_US10Y]
        assert r.invalid_items == ("10Y公債殖利率",)

    @pytest.mark.parametrize("pair,status", [(("", ""), "both_missing"), (("5", "5.05"), "agree"),
                                             ((" ", "3.0"), "a_missing")])
    def test_rev_yoy_strings_do_not_raise(self, pair, status):
        s = {"t2_data": {"rev_yoy_self": pair[0], "rev_yoy_finmind": pair[1]}}
        assert _rows(s)[RS.ROW_REV_YOY].result["status"] == status
        assert P.load_reconcile(_REQ, s).error == ""

    def test_mutation_raw_float_on_fred_turns_red(self):
        m = _mutant_rs(("reconcile_us10y_yield(_to_float_or_none(_fred_raw),",
                        "reconcile_us10y_yield(float(_fred_raw),"))
        with pytest.raises(ValueError):
            m.compute_reconcile(_full_session(macro_info={"us10y": {"value": ""}}))


class TestMaxScoreAndSources:
    @pytest.mark.parametrize("max_score,want", [(0, 75.0), (None, 75.0), (4, 75.0), (6, 50.0)])
    def test_max_score_or_fallback(self, max_score, want):
        assert RS.score_pct_from(3, max_score) == pytest.approx(want)

    def test_negative_max_score_gives_none_and_row_both_missing(self):
        assert RS.score_pct_from(3, -4) is None
        r = _rows(_full_session(mkt_info={"score": 3, "max_score": -4}))[RS.ROW_HEALTH]
        assert r.invalid_items == () and r.result["status"] == "both_missing"

    def test_score_pct_clamped_to_100(self):
        assert RS.score_pct_from(5.5, 4) == 100.0

    def test_jingqi_info_wins_over_stale_warroom(self):
        s = _full_session(jingqi_info={"avg": 30.0}, warroom_summary={"jingqi_avg": 90.0})
        assert RS.health_inputs(s)["jq"] == 30.0

    def test_warroom_used_only_without_jingqi_info(self):
        s = _full_session(warroom_summary={"jingqi_avg": 90.0})
        s.pop("jingqi_info")
        assert RS.health_inputs(s)["jq"] == 90.0

    @staticmethod
    def _assert_no_warroom_fallback(mod):
        """QA B10：`jingqi_info` 存在但沒有 `avg` ⇒ 缺值，⛔ 不讀 warroom（可能是舊頁籤殘留）。"""
        for jq in ({"regime": "多"}, {"avg": None}):
            s = _full_session(jingqi_info=jq, warroom_summary={"jingqi_avg": 90.0})
            assert mod.health_inputs(s)["jq"] is None
            assert mod.compute_reconcile(s).rows[2].result["status"] == "both_missing"

    def test_jingqi_info_without_avg_does_not_read_warroom(self):
        self._assert_no_warroom_fallback(RS)

    def test_mutation_adding_the_warroom_fallback_turns_red(self):
        m = _mutant_rs(('        _jq = _get(_jq_info, "avg")',
                        '        _jq = _get(_jq_info, "avg")\n'
                        '        if _jq is None:\n            _jq = _get(_wr, "jingqi_avg")'))
        with pytest.raises(AssertionError):
            self._assert_no_warroom_fallback(m)

    def test_unobserved_foreign_net_is_none(self):
        from shared.inst_net import InstNetDict
        s = _full_session()
        s["cl_data"]["inst"] = InstNetDict({"外資及陸資": {"net": 0.0}}, unobserved_net={"外資及陸資"})
        assert RS.health_inputs(s)["fnet"] is None


# ── B｜與舊面板逐列對帳 ───────────────────────────────────────────────
_EQUIV_SESSIONS = [
    {},
    _full_session(),
    _full_session(mkt_info={"score": 3, "max_score": 0}),
    _full_session(mkt_info={"score": 3, "max_score": None}),
    _full_session(mkt_info={"score": 3, "max_score": -1}),
    _full_session(mkt_info={"score": 6.5, "max_score": 6}),
    _full_session(cl_data={"intl": {"10Y公債殖利率": _tnx(42.7)}, "inst": {"外資": {"net": -5.0}}}),
    _full_session(cl_data={"intl": {"10Y公債殖利率": _tnx(250.0)}}),
    _full_session(macro_info={"us10y": {"value": 3.1}}),               # disagree
    _full_session(jingqi_info={"avg": 20.0}),                         # health disagree
    {"mkt_info": {"score": 2}},
    {"t2_data": {"rev_yoy_self": 5.0, "rev_yoy_finmind": 5.05}},
    {"cl_data": {"intl": {"10Y公債殖利率": pd.DataFrame({"Close": [4.2]})}},
     "macro_info": {"us10y": {"value": 4.2}}},
]


def _old_rows(monkeypatch, session):
    from src.ui.pages import reconcile_panel as RP
    monkeypatch.setattr(RP, "_ss", lambda k, d=None: session.get(k, d))
    return RP.compute_reconcile_rows()


@pytest.mark.parametrize("session", _EQUIV_SESSIONS, ids=[str(i) for i in range(len(_EQUIV_SESSIONS))])
def test_rows_match_the_old_panel(monkeypatch, session):
    old = _old_rows(monkeypatch, session)
    new = RS.compute_reconcile(session).rows
    assert [o["name"] for o in old] == [n.name for n in new]
    for o, n in zip(old, new):
        r = n.result
        assert n.invalid_items == ()
        assert (o["status"], o["source_a"], o["source_b"]) == (r["status"], r["source_a"], r["source_b"])
        for a, b in ((o["v_a"], r["value_a"]), (o["v_b"], r["value_b"]), (o["delta"], r["delta_abs"])):
            assert (a is None and b is None) or math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)


def test_old_panel_diverges_on_stale_warroom_and_new_one_follows_jingqi(monkeypatch):
    s = _full_session(jingqi_info={"avg": 30.0}, warroom_summary={"jingqi_avg": 90.0})
    old = {o["name"]: o for o in _old_rows(monkeypatch, s)}
    new = _rows(s)
    want = RS.reconcile_health_score(30.0, RS.score_pct_from(3, 5), 35.2)
    assert new[RS.ROW_HEALTH].result == want
    assert old[RS.ROW_HEALTH]["v_a"] != want["value_a"], "舊面板讀 warroom 舊值（本批要避開的行為）"


def test_old_panel_false_signals_that_the_wrapper_blocks(monkeypatch):
    """前提查證：不先擋時 L2 對無效值會誤判（FRED NaN → 假紅；外資 inf → 假綠）。"""
    assert RS.reconcile_us10y_yield(NAN, 4.2)["status"] == "disagree"
    assert RS.reconcile_health_score(70.0, 70.0, INF)["status"] == "agree"
    s = _full_session(macro_info={"us10y": {"value": NAN}})
    assert _rows(s)[RS.ROW_US10Y].invalid_items == ("10Y公債殖利率",)


def _assert_fred_nan_is_blocked():
    r = _rows(_full_session(macro_info={"us10y": {"value": NAN}}))[RS.ROW_US10Y]
    assert r.invalid_items == ("10Y公債殖利率",) and r.result is None


def test_mutation_removing_the_input_check_turns_red(monkeypatch):
    monkeypatch.setattr(RS, "is_invalid_number", lambda v: False)
    with pytest.raises(AssertionError):
        _assert_fred_nan_is_blocked()


# ── B｜卡片 ──────────────────────────────────────────────────────────
_REQ = P.EngineerRequest(opened=True)


class TestReconcileCard:
    def test_only_mkt_score_is_grey(self):
        """QA D2：只有 `mkt_info.score`（其餘全缺）⇒ 三列全 ⬜ 未觸發 ⇒ 灰，⛔ 不是綠。"""
        card = P.build_reconcile_card(P.load_reconcile(_REQ, {"mkt_info": {"score": 3}}))[0]
        assert card.state == UI_MISSING_RETRYABLE and card.note.now == P.RECONCILE_NOT_TRIGGERED_NOW

    def test_partial_us10y_only_is_grey(self):
        card = P.build_reconcile_card(P.load_reconcile(_REQ, {"macro_info": {"us10y": {"value": 4.2}}}))[0]
        assert card.state == UI_MISSING_RETRYABLE

    def test_only_invalid_inputs_show_the_invalid_sentence_not_grey(self):
        """QA B21：只有無效輸入 ⇒ live、該列顯示資料異常句（⛔ 不落成灰卡把異常藏起來）。"""
        built = P.build_reconcile_card(P.load_reconcile(_REQ, {"jingqi_info": {"avg": NAN}}))
        assert built[0].state == UI_LIVE
        assert dict(built[1])[RS.ROW_HEALTH] == "旌旗指數資料異常，無法計算，不下結論。"

    def test_mutation_ignoring_invalid_rows_in_comparable_turns_red(self, monkeypatch):
        monkeypatch.setattr(RS.ReconcileReport, "comparable", property(lambda self: any(
            (_r.result or {}).get("status") in ("agree", "disagree") for _r in self.rows)))
        with pytest.raises(AssertionError):
            self.test_only_invalid_inputs_show_the_invalid_sentence_not_grey()

    def test_mutation_back_to_any_input_turns_red(self, monkeypatch):
        """判準不分可比對與否（只要算得出列就當有值；原 `has_input` 判準的同類放寬）⇒ 只有 score 時變綠 ⇒ 守衛轉紅。"""
        monkeypatch.setattr(RS.ReconcileReport, "comparable", property(lambda self: bool(self.rows)))
        with pytest.raises(AssertionError):
            self.test_only_mkt_score_is_grey()

    def test_c5_only_a_disagree_row_is_live(self):
        """C5：只有一列 disagree（其餘兩列缺）⇒ 綠（可比對），該列寫「🔴 不一致(警示)」。"""
        s = {"macro_info": {"us10y": {"value": 3.1}},
             "cl_data": {"intl": {"10Y公債殖利率": _tnx(4.27)}}}
        built = P.build_reconcile_card(P.load_reconcile(_REQ, s))
        assert built[0].state == UI_LIVE
        assert dict(built[1])[RS.ROW_US10Y].startswith("🔴 不一致(警示)")

    def test_mutation_comparable_only_counting_agree_turns_red(self, monkeypatch):
        monkeypatch.setattr(RS.ReconcileReport, "comparable", property(lambda self: any(
            _r.invalid_items or (_r.result or {}).get("status") == "agree" for _r in self.rows)))
        with pytest.raises(AssertionError):
            self.test_c5_only_a_disagree_row_is_live()

    def test_grey_why_lists_every_key_read_in_order(self):
        why = P.RECONCILE_NOT_TRIGGERED_WHY
        keys = ["macro_info['us10y']['value']", "cl_data['intl']['10Y公債殖利率']",
                "t2_data['rev_yoy_self']", "t2_data['rev_yoy_finmind']", "jingqi_info['avg']",
                "warroom_summary['jingqi_avg']", "mkt_info['score']", "mkt_info['max_score']",
                "cl_data['inst']"]
        pos = [why.index(k) for k in keys]
        assert pos == sorted(pos), keys

    def test_has_input_orphan_removed(self):
        assert not hasattr(RS.ReconcileReport, "has_input")
        assert "has_input" not in {f.name for f in __import__("dataclasses").fields(RS.ReconcileRow)}

    def test_never_refreshed_is_grey_with_existing_where(self):
        card, facts, _ = P.build_reconcile_card(P.load_reconcile(_REQ, {}))
        assert card.state == UI_MISSING_RETRYABLE
        assert card.note.now == P.RECONCILE_NOT_TRIGGERED_NOW
        assert card.note.where == P.REGISTRY_NOT_WRITTEN_WHERE == "到「🚦 今天」更新"

    def test_exception_is_red(self, monkeypatch):
        def _boom(_s):
            raise RuntimeError("boom")
        monkeypatch.setattr(RS, "compute_reconcile", _boom)
        card, _f, _s = P.build_reconcile_card(P.load_reconcile(_REQ, {}))
        assert card.state == UI_FAILED and card.note.now == P.RECONCILE_FAILED_NOW
        assert card.note.where == P.PANEL_REPORT_WHERE

    def test_disagree_is_a_row_warning_not_a_red_card(self):
        card, facts, _ = P.build_reconcile_card(P.load_reconcile(
            _REQ, _full_session(macro_info={"us10y": {"value": 3.1}})))
        assert card.state == UI_LIVE and card.value == "3 個對帳"
        f = dict(facts)
        assert f[RS.ROW_US10Y].startswith("🔴 不一致(警示)")
        assert f[RS.ROW_REV_YOY] == P.RECONCILE_REV_YOY_NO_WRITER

    def test_live_card_with_invalid_rows_shows_no_number_for_them(self):
        s = _full_session(macro_info={"us10y": {"value": NAN}}, jingqi_info={"avg": INF})
        built = P.build_reconcile_card(P.load_reconcile(_REQ, s))
        f = dict(built[1])
        assert f[RS.ROW_US10Y] == "10Y公債殖利率資料異常，無法計算，不下結論。"
        assert f[RS.ROW_HEALTH] == "旌旗指數資料異常，無法計算，不下結論。"
        assert not _NONFINITE_RE.search(P.v2_card_html(*built))

    def test_agree_row_text_format(self):
        f = dict(P.build_reconcile_card(P.load_reconcile(_REQ, _full_session()))[1])
        assert f[RS.ROW_US10Y] == ("🟢 一致 ｜ v1 4.25（FRED:DGS10） ｜ v2 4.27（Yahoo:^TNX(直接%)）"
                                   " ｜ 差距 0.02")

    def test_view_row_name_constant_matches_l3(self):
        assert P._RECONCILE_ROW_REV_YOY == RS.ROW_REV_YOY

    def test_unchecked_gate_calls_nothing(self, monkeypatch):
        monkeypatch.setattr(RS, "compute_reconcile",
                            lambda _s: pytest.fail("沒勾進階診斷不得呼叫 L3"))
        r = P.load_reconcile(P.EngineerRequest(opened=False), {"mkt_info": {"score": 3}})
        assert r.requested is False and r.report is None
        with pytest.raises(ValueError):
            P.build_reconcile_card(r)

    def test_panel_row_order_and_unwired_count(self):
        row = P.build_engineer_panel_row(
            P.RegistryReadout(requested=True, error="x"),
            P.CalibrationReadout(requested=True, error="x"),
            P.load_reconcile(_REQ, {}))
        assert [b[0].key for b in row] == ["why.engineer.registry", "why.engineer.reconcile",
                                           "why.engineer.api_root", "why.engineer.raw",
                                           "why.engineer.calibration"]
        assert [s.key for s in P.ENGINEER_PANEL_SPECS] == ["why.engineer.api_root", "why.engineer.raw"]
        assert not hasattr(P, "ENGINEER_RECONCILE_NOW")


_WHY_SCRIPT = """
import pandas as pd
import streamlit as st
st.session_state.setdefault("macro_info", {"us10y": {"value": 4.25}})
st.session_state.setdefault("cl_data", {"intl": {"10Y公債殖利率": pd.DataFrame({"close": [4.27]})},
                                        "inst": {"外資及陸資": {"net": float("nan")}}})
st.session_state.setdefault("jingqi_info", {"avg": 62.0})
st.session_state.setdefault("mkt_info", {"score": 3, "max_score": 5})
from src.ui.views import page_why as P
P.render_page_why()
"""


def _run_why(tmp_path, tick):
    from streamlit.testing.v1 import AppTest
    script = tmp_path / "_z56_why.py"
    script.write_text(_WHY_SCRIPT, encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=180)
    if tick:
        at.session_state[P.SS_ENGINEER_GATE] = True
    at.run()
    assert not at.exception, at.exception
    return "\n".join(m.value for m in at.markdown) + "\n".join(c.value for c in at.caption)


def test_apptest_gate_unticked_never_calls_l3(tmp_path, monkeypatch):
    calls = []
    real = RS.compute_reconcile
    monkeypatch.setattr(RS, "compute_reconcile", lambda s: (calls.append(1), real(s))[1])
    md = _run_why(tmp_path, tick=False)
    assert calls == [] and "3 個對帳" not in md


def test_apptest_gate_ticked_shows_the_wired_card(tmp_path, monkeypatch):
    calls = []
    real = RS.compute_reconcile
    monkeypatch.setattr(RS, "compute_reconcile", lambda s: (calls.append(1), real(s))[1])
    md = _run_why(tmp_path, tick=True)
    assert calls == [1]
    assert "3 個對帳" in md and "外資資料異常，無法計算，不下結論。" in md
    assert "雙演算法對帳本頁跑不了" not in md
    assert "其餘兩個各自卡在不同的地方" in md


# ── B｜結構守衛 ──────────────────────────────────────────────────────
def test_service_is_pure_l3_no_streamlit_no_old_panel():
    tree = ast.parse((ROOT / "src/services/reconcile_service.py").read_text(encoding="utf-8"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add(n.module or "")
    assert not {m for m in mods if m.startswith(("streamlit", "src.ui", "src.data", "app"))}, mods


def test_rev_yoy_keys_still_have_no_writer():
    """月營收列的事實句「全 repo 沒有任何一處寫這兩個 key（實測 0 個寫入點）」要一直成立。"""
    pat = re.compile(r"""(\[\s*['"]rev_yoy_(self|finmind)['"]\s*\]\s*=(?!=))"""
                     r"""|(['"]rev_yoy_(self|finmind)['"]\s*:)"""
                     r"""|(rev_yoy_(self|finmind)\s*=(?!=))""")
    hits = []
    files = [ROOT / "app.py", *(ROOT / "src").rglob("*.py"), *(ROOT / "scripts").rglob("*.py"),
             *(ROOT / "shared").rglob("*.py")]
    for p in files:
        if p.exists():
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if pat.search(line):
                    hits.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()}")
    assert hits == [], hits


# ══════════════════════════════════════════════════════════════════
# 舊批次還原體串接用（同 `tests/test_batch_z36.py::z36_pairs_for` 慣例）
# ══════════════════════════════════════════════════════════════════
#: 批 Z56 → 修前（`f5042a3b`）的替換組 `(現行, 修前)`，每組恰好一處。
#: `ai_qa_service.py` 全數換回後逐字等於 `f5042a3b`（下方 `test_z56_revert_pairs_restore_the_base_exactly` 以 sha256 守）；
#: `page_why.py` 只換回 `load_qa` 呼叫 L3 那一段（舊批次 b5 的突變錨點）。
Z56_REVERT_PAIRS: dict = {
    "src/services/ai_qa_service.py": (
        ('    tool_calls: list = field(default_factory=list)   # [{"name","args","result"}]\n    #: 批 Z56（客戶 2026-10-13 裁示 B）：`run_agent(stop_on_invalid_number=True)` 在工具結果裡\n    #: 掃到 NaN／±inf 時停下，這裡放「哪幾個項目」（項目名規則見 `_invalid_number_items`）。\n    #: 空 tuple ＝ 沒有異常（修前行為；預設值讓既有建構方式逐字不變）。\n    #: `repr=False`：舊 UI（`tab_ai_chat`，不傳旗標）拿到的 `QAResult` 連 repr 都與修前逐字相同。\n    invalid_items: tuple = field(default=(), repr=False)\n',
         '    tool_calls: list = field(default_factory=list)   # [{"name","args","result"}]\n'),
        ('\n# ── 批 Z56：工具結果裡的無效數值（NaN／±inf）→ 停止，不送 Gemini ──────────────────\n#: 英文欄名的工具 → 項目名。⛔ 不新造：每一個都是該工具 `TOOLS_SCHEMA` 描述裡的既有字串\n#: （守衛：`tests/test_batch_z56.py` 逐一驗「是 description 的子字串」）。\n#: 工具 data 的欄名本身是中文（例：`get_market_leading` 的「外資」「選PCR」、\n#: `get_financial_health` 的「毛利率(%)」）時，直接用那個欄名，不查本表。\nTOOL_ITEM_NAMES: dict = {\n    "get_market_state": "目前總經/大盤狀態",\n    "get_stock_score": "個股量化評分",\n    "get_financial_health": "個股財務體質",\n    "get_market_leading": "大盤先行/籌碼",\n    "get_risk_plan": "停損與倉位",\n    "get_etf_quality": "ETF 品質評分",\n}\n\n\ndef _has_cjk(text: str) -> bool:\n    return any("\\u4e00" <= _ch <= "\\u9fff" for _ch in str(text))\n\n\ndef _invalid_number_items(tool_name: str, result) -> tuple:\n    """`_json_safe` 之後的工具結果裡，**數值型**欄位是 NaN／±inf（`shared.station_specs.is_invalid_number`）\n    的項目名（依出現順序、去重）。沒有 → `()`。\n\n    · 只看 int／float（⛔ 不看 bool、⛔ 不看字串：字串欄位如股名、來源、日期本來就不是數字，\n      拿 `is_invalid_number` 去判會把每一個字串都判成異常）。\n    · 項目名：最近一層**含中文**的欄名；一路上都是英文欄名 → `TOOL_ITEM_NAMES[tool_name]`\n      （查無此工具 → 工具名本身，只有測試注入的工具會走到）。\n    """\n    from shared.station_specs import is_invalid_number   # 區域 import：L0 純函式，零依賴\n\n    _fallback = TOOL_ITEM_NAMES.get(tool_name, tool_name)\n    _out: list = []\n\n    def _walk(node, label: str) -> None:\n        if isinstance(node, dict):\n            for _k, _v in node.items():\n                _walk(_v, str(_k) if _has_cjk(_k) else label)\n        elif isinstance(node, (list, tuple)):\n            for _v in node:\n                _walk(_v, label)\n        elif (isinstance(node, (int, float)) and not isinstance(node, bool)\n              and is_invalid_number(node)):\n            if label not in _out:\n                _out.append(label)\n\n    _walk(result, _fallback)\n    return tuple(_out)\n\n\n',
         '\n'),
        ('              model: str = DEFAULT_MODEL, max_rounds: int = 4,\n              fail_on_blocked_reply: bool = False,\n              stop_on_invalid_number: bool = False) -> QAResult:\n',
         '              model: str = DEFAULT_MODEL, max_rounds: int = 4,\n              fail_on_blocked_reply: bool = False) -> QAResult:\n'),
        ('        預設 False = 本參數出現之前的行為,一個 byte 不差(🧬 AI 問答舊分頁 `tab_ai_chat` 不傳)。\n    stop_on_invalid_number:\n        批 Z56(客戶 2026-10-13 裁示 B)。True → 每一輪工具跑完後掃結果(`_invalid_number_items`);\n        有 NaN／±inf → **不送下一輪給 Gemini**,回 `ok=False`、`error` 為客戶句\n        `{項目}資料異常，無法計算，不下結論。`(逐項串接)、`invalid_items` 為項目名。\n        ⛔ 不拿替代值補、⛔ 不把異常值改寫後照送(資料層與 AI 層分離:AI 收不到這份資料)。\n        修前此情境會在 `requests.post(json=...)` 拋 InvalidJSONError,被畫成「Gemini 呼叫失敗」。\n        預設 False = 本參數出現之前的行為,一個 byte 不差(`tab_ai_chat` 不傳)。\n',
         '        預設 False = 本參數出現之前的行為,一個 byte 不差(🧬 AI 問答舊分頁 `tab_ai_chat` 不傳)。\n'),
        ('            rparts = []\n            _bad: list = []\n',
         '            rparts = []\n'),
        ('                rparts.append({"functionResponse": {"name": name, "response": result}})\n                if stop_on_invalid_number:\n                    _bad += [_i for _i in _invalid_number_items(name, result) if _i not in _bad]\n            if _bad:\n                from shared.station_specs import invalid_data_text\n                _msg = "".join(invalid_data_text(_i) for _i in _bad)\n                print(f"[ai_qa run_agent] 工具結果含無效數值(NaN/±inf)→ 停止、不送 Gemini:{_bad}")\n                return QAResult(ok=False, error=_msg, model=model, tool_calls=tool_calls,\n                                invalid_items=tuple(_bad))\n',
         '                rparts.append({"functionResponse": {"name": name, "response": result}})\n'),
    ),
    "src/ui/views/page_why.py": (
        ('        # 批 Z56：`stop_on_invalid_number=True` —— 工具結果有 NaN／±inf 時 L3 停下、⛔ 不送 Gemini，\n        #   回 `ok=False` ＋ 客戶句（修前：送出時 `requests` 拋 InvalidJSONError → 誤導的「Gemini 呼叫失敗」）。\n        _res = run_agent(req.question, list(req.history), api_key=_key,\n                         fail_on_blocked_reply=True, stop_on_invalid_number=True)',
         '        _res = run_agent(req.question, list(req.history), api_key=_key,\n                         fail_on_blocked_reply=True)'),
    ),
}
#: `git show f5042a3b:src/services/ai_qa_service.py | sha256sum` 實算（寫死以免測試依賴 git）。
Z56_AI_QA_BASE_SHA: str = "f94c356e78f2e0ffe79e5c52d9911424b2546514b6384d1fcc556f3bbd67ad5b"


def z56_pairs_for(file_path) -> tuple:
    """給模組 `__file__`（或 repo 相對路徑），回本批該檔的還原組（無則空 tuple）。"""
    p = pathlib.Path(file_path)
    rel = (p.resolve().relative_to(ROOT) if p.is_absolute() else p).as_posix()
    return Z56_REVERT_PAIRS.get(rel, ())


def z56_revert_for(file_path, code: str) -> str:
    for new, old in z56_pairs_for(file_path):
        assert code.count(new) == 1, f"{file_path} 替換點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    return code


def test_z56_revert_pairs_restore_the_base_exactly():
    import hashlib
    rel = "src/services/ai_qa_service.py"
    code = z56_revert_for(rel, (ROOT / rel).read_text(encoding="utf-8"))
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == Z56_AI_QA_BASE_SHA
    assert "stop_on_invalid_number" not in code
