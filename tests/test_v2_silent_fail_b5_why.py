"""批次 5：「📖 憑什麼」AI 問答卡 `why.qa` —— 「回覆被擋／格式壞掉」與「模型真的沒話說」必須分得開。

（客戶 2026-09-26：⛔ 只修這一張卡；其他卡／其他呼叫端的輸出一律不動；⛔ 不新造文案；⛔ 不動版面。）

根因（L3 `ai_qa_service`）：`_parts()` 用 `try/except` 把三種**失敗**一律吞成 `[]` ——
  · 問題本身被擋（`promptFeedback.blockReason`，通常連 `candidates` 都沒有）；
  · 回答被擋或被截斷成空（`candidates[0].finishReason` ＝ SAFETY / RECITATION / MAX_TOKENS …，
    或**缺席** ＝ FINISH_REASON_UNSPECIFIED，模型沒說它停了）；
  · 結構缺件（沒有／空的 candidates、候選不是物件、型別不對）；
  （⚠️ **明講** `STOP` 而沒有 `content`／`parts` **不在此列**：Gemini REST 把空欄位整個省略，
  那是自然結束的空回答。）
`run_agent()` 於是回 `ok=True, text=""`，L5 `load_qa()` 落到分支 (e)，卡片畫成灰的
「**這一輪沒有回答內容**」＋「這是一個**有效結果**（模型真的沒話說），不是故障」。

修法：
  · L3 新增 `_reply_failure(resp)`（`_parts()` 一字未動），`run_agent(..., fail_on_blocked_reply=True)`
    在**最後一輪沒有文字**時才問它；被擋／格式壞掉 → `ok=False` ＋ 既有前綴「Gemini 呼叫失敗」＋ 上游原文。
    **預設 False** ⇒ 舊分頁 `tab_ai_chat`（不傳）與分析師 panel（不經 `run_agent`）一個 byte 不差。
  · L5 `load_qa()` 只多傳 `fail_on_blocked_reply=True` ⇒ 走既有分支 (d)：紅卡 `QA_FAILED_NOW`
    ＋ 既有 why（`_error_why`）＋ 既有 where。**一句新文案都沒有。**

每條失敗路徑三件事（同批次 1～4）：
  (a) 被擋／格式壞掉 → 紅卡 `QA_FAILED_NOW`；⛔ 不得是灰卡「這一輪沒有回答內容」／「有效結果」；
  (b) 格式完整、自然結束的空回答（規格 `UI_PAGE_WHY.md` ⑤(f)）與有文字的回答 → 原封不動；
      其他卡、其他呼叫端的輸出一字不變；
  (c) 突變：拿掉本批新加的任何一條判定 → (a) 或 (b) 必須失敗。
"""
from __future__ import annotations

import ast
import functools
import hashlib
import html
import importlib.util
import json
import pathlib
import sys
import types

import pytest

import src.services.ai_qa_service as S
import src.services.app_ai_service as K
from shared.ui_state import UI_FAILED, UI_LIVE
from src.ui.views import page_why as P

_VALID = "有效結果"
_PREFIX = "Gemini 呼叫失敗:"      # run_agent 既有的錯誤前綴（`_fmt_gemini_error("Gemini 呼叫失敗", e)`）
_Q = "2330 健康度多少？"


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    """把 `mod` 的原始碼裡每一組 `old` **恰好一處**換成 `new`，載成一個獨立的新模組。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_b5_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


# ══════════════════════════════════════════════════════════════════
# 「本批之前」＝ 把本批的改動整段中和掉
# ══════════════════════════════════════════════════════════════════
_REVERT_L3 = (
    ("              model: str = DEFAULT_MODEL, max_rounds: int = 4,\n"
     "              fail_on_blocked_reply: bool = False) -> QAResult:",
     "              model: str = DEFAULT_MODEL, max_rounds: int = 4) -> QAResult:"),
    ("        if fail_on_blocked_reply and not text:\n"
     "            _why = _reply_failure(resp)\n"
     "            if _why is not None:\n"
     "                _why = _scrub_secrets(_why)\n"
     "                print(f\"[ai_qa run_agent] 空回覆且被擋/格式異常 → ok=False:{_why}\")\n"
     "                return QAResult(ok=False, error=f\"Gemini 呼叫失敗:{_why}\", model=model, "
     "tool_calls=tool_calls)\n",
     ""),
)
_REVERT_VIEW = (("api_key=_key,\n                         fail_on_blocked_reply=True)",
                 "api_key=_key)"),)


@functools.lru_cache(maxsize=None)
def _old_l3() -> types.ModuleType:
    return _mutant(S, *_REVERT_L3)


@functools.lru_cache(maxsize=None)
def _old_view() -> types.ModuleType:
    return _mutant(P, *_REVERT_VIEW)


# ══════════════════════════════════════════════════════════════════
# Gemini REST 回覆的各種形狀（欄位名照 generateContent 的 JSON）
# ══════════════════════════════════════════════════════════════════
_RATINGS = [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "probability": "HIGH", "blocked": True}]
_USAGE = {"promptTokenCount": 12, "totalTokenCount": 12}


def _ans(text: str, finish: str | None = "STOP") -> dict:
    cand: dict = {"content": {"parts": [{"text": text}], "role": "model"}, "index": 0}
    if finish is not None:
        cand["finishReason"] = finish
    return {"candidates": [cand], "usageMetadata": _USAGE}


def _fc(name: str, args: dict) -> dict:
    return {"candidates": [{"content": {"parts": [{"functionCall": {"name": name, "args": args}}],
                                        "role": "model"}, "finishReason": "STOP"}]}


_MFC_MSG = "Malformed function call: print(get_stock_score('2330'))"

#: id → (回覆, L3 應回的 error 全文扣掉前綴後的那一段 —— **上游原文**，⛔ 沒有任何自寫的解釋)
_BLOCKED: dict[str, tuple[object, str]] = {
    "prompt_blocked": (
        {"promptFeedback": {"blockReason": "SAFETY", "safetyRatings": _RATINGS}, "usageMetadata": _USAGE},
        json.dumps({"promptFeedback": {"blockReason": "SAFETY"}}, ensure_ascii=False)),
    "prompt_blocked_with_message": (
        {"promptFeedback": {"blockReason": "PROHIBITED_CONTENT", "blockReasonMessage": "上游說明原文"}},
        json.dumps({"promptFeedback": {"blockReason": "PROHIBITED_CONTENT",
                                       "blockReasonMessage": "上游說明原文"}}, ensure_ascii=False)),
    "answer_safety_no_content": (
        {"candidates": [{"finishReason": "SAFETY", "index": 0, "safetyRatings": _RATINGS}]},
        json.dumps({"finishReason": "SAFETY"})),
    "answer_safety_empty_text": (
        {"candidates": [{"content": {"parts": [{"text": ""}], "role": "model"}, "finishReason": "SAFETY"}]},
        json.dumps({"finishReason": "SAFETY"})),
    "recitation": (
        {"candidates": [{"finishReason": "RECITATION", "index": 0}]},
        json.dumps({"finishReason": "RECITATION"})),
    "max_tokens_nothing_left": (
        {"candidates": [{"content": {"role": "model"}, "finishReason": "MAX_TOKENS", "index": 0}]},
        json.dumps({"finishReason": "MAX_TOKENS"})),
    "malformed_function_call": (
        {"candidates": [{"content": {}, "finishReason": "MALFORMED_FUNCTION_CALL", "finishMessage": _MFC_MSG}]},
        json.dumps({"finishReason": "MALFORMED_FUNCTION_CALL", "finishMessage": _MFC_MSG})),
    # ── finishReason 缺席（＝ FINISH_REASON_UNSPECIFIED，模型沒說它停了）＋ 沒有文字 → 紅 ──
    "no_finish_reason": (_ans("", finish=None),
                         json.dumps({"candidates[0]": {"content": "dict", "index": "int"}})),
    "no_finish_reason_no_parts": ({"candidates": [{"content": {"role": "model"}, "index": 0}]},
                                  json.dumps({"candidates[0]": {"content": "dict", "index": "int"}})),
    "no_finish_reason_no_content": ({"candidates": [{"index": 0}]},
                                    json.dumps({"candidates[0]": {"index": "int"}})),
    # ── 結構缺件／型別不對：證據＝出事那一層**實際收到的形狀**（物件列 {key: 型別名}、不帶內容）──
    "no_candidates": ({"usageMetadata": _USAGE}, json.dumps({"usageMetadata": "dict"})),
    "empty_candidates": ({"candidates": []}, json.dumps({"candidates": []})),
    "candidates_not_a_list": ({"candidates": {"content": {}}},
                              json.dumps({"candidates": {"content": "dict"}})),
    "candidate_null": ({"candidates": [None]}, json.dumps({"candidates[0]": None})),
    "candidate_empty_object": ({"candidates": [{}]}, json.dumps({"candidates[0]": {}})),
    "content_null": ({"candidates": [{"content": None, "finishReason": "STOP"}]},
                     json.dumps({"candidates[0].content": None})),
    "parts_null": ({"candidates": [{"content": {"parts": None}, "finishReason": "STOP"}]},
                   json.dumps({"candidates[0].content.parts": None})),
    "parts_a_string": ({"candidates": [{"content": {"parts": "abc"}, "finishReason": "STOP"}]},
                       json.dumps({"candidates[0].content.parts": "str"})),
    "not_an_object": ([], "[]"),
}

#: 格式完整、自然結束、就是沒有文字 —— 規格 ⑤(f) 的「有效結果」，**本批之後仍然存在**。
#: ⚠️ Gemini REST 會把空 list／空物件**整個省略** ⇒ `STOP` 而沒有 `content`／`parts` 也是這一種（⛔ 不是故障）。
#: ⚠️ 只有**明講** `finishReason == "STOP"` 才算；缺席的（模型沒說它停了）在 `_BLOCKED`。
_GENUINE_EMPTY: dict[str, dict] = {
    "stop_empty_text": _ans(""),
    "stop_whitespace_text": _ans("  \n "),
    "stop_empty_parts_list": {"candidates": [{"content": {"parts": [], "role": "model"},
                                              "finishReason": "STOP"}]},
    "stop_no_parts": {"candidates": [{"content": {"role": "model"}, "finishReason": "STOP", "index": 0}],
                      "usageMetadata": _USAGE},
    "stop_no_content": {"candidates": [{"finishReason": "STOP", "index": 0}], "usageMetadata": _USAGE},
}

#: 有文字的回答 —— 本批一律不碰（含「有字但 finishReason 不是 STOP」這種，見 `TestGenuineUnchanged`）。
_GENUINE_TEXT: dict[str, dict] = {
    "stop": _ans("偏強。毛利率 55%（FinMind 2026Q2）。"),
    "no_finish_reason": _ans("中性。", finish=None),
    "partial_with_safety": _ans("前半段已經寫出來的回答", "SAFETY"),
    "partial_with_max_tokens": _ans("被截斷的回答", "MAX_TOKENS"),
}

_FAKE_TOOLS = {
    "get_stock_score": lambda stock_id: {"ok": True, "data": {"total": 82, "stock_id": stock_id},
                                         "provenance": {"source": "FinMind", "as_of": None}},
}


def _pipeline(monkeypatch, *responses, view=P, l3=S):
    """真的走 L5 `load_qa` → L3 `run_agent`（只把 HTTP 換成照稿回覆、工具換成離線假物）→ `build_qa_card`。"""
    script = list(responses)
    calls: list[dict] = []

    def _http(payload):
        calls.append(payload)
        _r = script.pop(0)
        if isinstance(_r, BaseException):
            raise _r
        return _r

    monkeypatch.setattr(l3, "_make_default_http", lambda api_key, model, **_k: _http)
    monkeypatch.setattr(l3, "REAL_TOOLS", dict(_FAKE_TOOLS))
    monkeypatch.setitem(sys.modules, "src.services.ai_qa_service", l3)
    monkeypatch.setattr(K, "get_gemini_api_key", lambda: "k")
    qa = view.load_qa(view.QaRequest(asked=True, question=_Q))
    return qa, view.build_qa_card(qa), calls


def _old_pipeline(monkeypatch, *responses):
    return _pipeline(monkeypatch, *responses, view=_old_view(), l3=_old_l3())


def _fingerprint(view, built) -> str:
    card, facts, sig = built
    return repr((card, tuple(facts), sig)) + view.v2_card_html(card, facts, sig)


def _badge(out: str) -> str:
    return out.split('class="bdg bdg-', 1)[1].split(" ", 1)[0]


#: 既有紅卡（上游回 ok=False）當參照 —— 本批的紅卡必須跟它**同一套**文案與版面。
_REF_FAILED = P.build_qa_card(P.QaReadout(asked=True, model="m", error="429 quota"))
_REF_EMPTY = P.build_qa_card(P.QaReadout(asked=True, model="m"))


# ══════════════════════════════════════════════════════════════════
# 根因釘住：`_parts()` 把失敗吞成 `[]`；不傳旗標時 run_agent 仍是 ok=True + 空字串
# ══════════════════════════════════════════════════════════════════
class TestRootCause:
    @pytest.mark.parametrize("key", list(_BLOCKED))
    def test_parts_yields_no_text_and_no_reason_for_every_failed_shape(self, key):
        """`_parts()`（本批一字未動）只回 parts —— 失敗原因（blockReason / finishReason / 缺件）全部看不到。"""
        parts = S._parts(_BLOCKED[key][0])
        assert "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip() == ""

    @pytest.mark.parametrize("key", list(_BLOCKED))
    def test_without_the_flag_the_legacy_contract_is_ok_and_empty(self, key):
        """舊分頁 `tab_ai_chat` 不傳旗標 —— 它看到的仍是本批之前的 ok=True + 空字串。"""
        r = S.run_agent(_Q, api_key="x", gemini_http=lambda _p: _BLOCKED[key][0], tools={})
        assert (r.ok, r.text, r.error) == (True, "", None)

    def test_before_this_batch_the_card_called_a_block_a_valid_result(self, monkeypatch):
        _qa, built, _c = _old_pipeline(monkeypatch, _BLOCKED["answer_safety_no_content"][0])
        card = built[0]
        assert card.state != UI_FAILED and card.note.now == P.QA_EMPTY_NOW
        assert _VALID in card.note.why, "修之前：被擋的回覆被說成「有效結果」（本批要修的謊）"


# ══════════════════════════════════════════════════════════════════
# (a) 被擋／格式壞掉 → 紅（走既有分支 (d)，既有文案）
# ══════════════════════════════════════════════════════════════════
class TestBlockedIsRed:
    @pytest.mark.parametrize("key", list(_BLOCKED))
    def test_a_l3_reports_the_upstream_evidence_with_the_existing_prefix(self, key):
        resp, detail = _BLOCKED[key]
        r = S.run_agent(_Q, api_key="x", gemini_http=lambda _p: resp, tools={},
                        fail_on_blocked_reply=True)
        assert r.ok is False and r.text == ""
        assert r.error == _PREFIX + detail, "只能是既有前綴 ＋ 上游原文，⛔ 不自己寫一句解釋"

    @pytest.mark.parametrize("key", list(_BLOCKED))
    def test_a_the_card_is_red_with_the_existing_failed_note(self, monkeypatch, key):
        resp, detail = _BLOCKED[key]
        qa, built, calls = _pipeline(monkeypatch, resp)
        card = built[0]
        assert len(calls) == 1
        assert qa.answered is False and qa.error == _PREFIX + detail
        assert card.state == UI_FAILED and card.note.now == P.QA_FAILED_NOW
        assert card.note.now != P.QA_EMPTY_NOW
        assert card.note.why == P._error_why(P.SRC_QA_AGENT, _PREFIX + detail)
        assert card.note.where == _REF_FAILED[0].note.where
        assert _VALID not in card.note.why and "不是故障" not in card.note.why

    @pytest.mark.parametrize("key", list(_BLOCKED))
    def test_a_the_face_is_the_existing_red_face_and_the_fold_keeps_the_evidence(self, monkeypatch, key):
        resp, detail = _BLOCKED[key]
        _qa, built, _c = _pipeline(monkeypatch, resp)
        assert P.v2_short_rows(built[0])[0] == P.v2_short_rows(_REF_FAILED[0])[0]
        out = P.v2_card_html(*built)
        assert _badge(out) == _badge(P.v2_card_html(*_REF_FAILED))
        assert _badge(out) != _badge(P.v2_card_html(*_REF_EMPTY))
        text = html.unescape(out)
        assert _PREFIX + detail in text, "上游原文在「▸ 詳細」摺疊區看得到"
        assert P.QA_EMPTY_NOW.strip("*") not in text and _VALID not in text

    def test_a_a_block_after_a_tool_round_keeps_the_tools_disclosed(self, monkeypatch):
        qa, built, calls = _pipeline(monkeypatch, _fc("get_stock_score", {"stock_id": "2330"}),
                                     _BLOCKED["answer_safety_no_content"][0])
        assert len(calls) == 2 and qa.tool_calls == ("get_stock_score",)
        assert built[0].state == UI_FAILED
        assert dict(built[1])["這一輪用到的工具"] == "get_stock_score"

    def test_a_the_prefix_is_the_one_run_agent_already_used(self):
        """前綴 ⛔ 不是新文案：本批之前 run_agent 就用它回報 Gemini 呼叫失敗。"""
        old_src = pathlib.Path(S.__file__).read_text(encoding="utf-8")
        for old, new in _REVERT_L3:
            old_src = old_src.replace(old, new)
        assert '_fmt_gemini_error("Gemini 呼叫失敗", e)' in old_src
        assert _PREFIX == "Gemini 呼叫失敗" + ":"

    def test_a_secrets_in_upstream_text_are_scrubbed(self):
        resp = {"candidates": [{"finishReason": "OTHER",
                                "finishMessage": "see ?key=AIzaSyA1234567890abcdef for details"}]}
        r = S.run_agent(_Q, api_key="x", gemini_http=lambda _p: resp, tools={},
                        fail_on_blocked_reply=True)
        assert r.ok is False and "AIzaSy" not in r.error and "1234567890abcdef" not in r.error

    def test_a_the_failure_is_logged(self, capsys):
        S.run_agent(_Q, api_key="x", gemini_http=lambda _p: _BLOCKED["prompt_blocked"][0], tools={},
                    fail_on_blocked_reply=True)
        assert _BLOCKED["prompt_blocked"][1] in capsys.readouterr().out


# ══════════════════════════════════════════════════════════════════
# (b) 真的沒話說 ／ 有文字 ／ 其他路徑 → 原封不動
# ══════════════════════════════════════════════════════════════════
class TestGenuineUnchanged:
    @pytest.mark.parametrize("key", list(_GENUINE_EMPTY))
    def test_b_a_well_formed_natural_empty_is_still_the_valid_result(self, monkeypatch, key):
        """規格 `UI_PAGE_WHY.md` ⑤(f)：`ok=True` 但沒有文字 → 灰「有效結果」。**這條路仍然存在。**"""
        qa, built, _c = _pipeline(monkeypatch, _GENUINE_EMPTY[key])
        card = built[0]
        assert qa.error == "" and qa.answered is False
        assert card.state != UI_FAILED and card.note.now == P.QA_EMPTY_NOW
        assert _VALID in card.note.why
        _oqa, obuilt, _oc = _old_pipeline(monkeypatch, _GENUINE_EMPTY[key])
        assert _fingerprint(P, built) == _fingerprint(_old_view(), obuilt)

    @pytest.mark.parametrize("key", list(_GENUINE_TEXT))
    def test_b_an_answer_with_text_is_byte_identical(self, monkeypatch, key):
        """有字的回答一律不碰 —— 含「有字但 finishReason 不是 STOP」（本卡的謊是『把失敗說成沒有結果』，
        那一種是另一件事，⛔ 不在本批射程內）。"""
        qa, built, _c = _pipeline(monkeypatch, _GENUINE_TEXT[key])
        assert built[0].state == UI_LIVE and qa.text
        _oqa, obuilt, _oc = _old_pipeline(monkeypatch, _GENUINE_TEXT[key])
        assert repr(qa) == repr(_oqa)
        assert _fingerprint(P, built) == _fingerprint(_old_view(), obuilt)

    def test_b_a_tool_round_then_an_answer_is_byte_identical(self, monkeypatch):
        seq = (_fc("get_stock_score", {"stock_id": "2330"}), _GENUINE_TEXT["stop"])
        _qa, built, _c = _pipeline(monkeypatch, *seq)
        _oqa, obuilt, _oc = _old_pipeline(monkeypatch, *seq)
        assert built[0].state == UI_LIVE
        assert _fingerprint(P, built) == _fingerprint(_old_view(), obuilt)

    @pytest.mark.parametrize("exc", [RuntimeError("503 Server Error: Service Unavailable"),
                                     ConnectionError("reset by peer")], ids=["503", "conn"])
    def test_b_the_http_exception_path_is_byte_identical(self, monkeypatch, exc):
        _qa, built, _c = _pipeline(monkeypatch, exc)
        _oqa, obuilt, _oc = _old_pipeline(monkeypatch, exc)
        assert built[0].state == UI_FAILED
        assert _fingerprint(P, built) == _fingerprint(_old_view(), obuilt)

    def test_b_running_out_of_rounds_is_byte_identical(self, monkeypatch):
        seq = [_fc("get_stock_score", {"stock_id": "2330"})] * 4
        _qa, built, _c = _pipeline(monkeypatch, *seq)
        _oqa, obuilt, _oc = _old_pipeline(monkeypatch, *seq)
        assert _fingerprint(P, built) == _fingerprint(_old_view(), obuilt)


# ══════════════════════════════════════════════════════════════════
# (b) 其他呼叫端／其他卡：輸出一字不變
# ══════════════════════════════════════════════════════════════════
_ALL_RESPONSES = ([r for r, _d in _BLOCKED.values()] + list(_GENUINE_EMPTY.values())
                  + list(_GENUINE_TEXT.values()))


class TestOtherCallersByteIdentical:
    def test_b_run_agent_without_the_flag_equals_before_this_batch(self):
        """`tab_ai_chat`（🧬 AI 問答舊分頁）不傳旗標 —— 每一種回覆都要與本批之前逐字相同。"""
        for resp in _ALL_RESPONSES:
            new = S.run_agent(_Q, [{"role": "user", "content": "前一題"}], api_key="x",
                              gemini_http=lambda _p, _r=resp: _r, tools={})
            old = _old_l3().run_agent(_Q, [{"role": "user", "content": "前一題"}], api_key="x",
                                      gemini_http=lambda _p, _r=resp: _r, tools={})
            assert repr(new) == repr(old), resp

    def test_b_the_analyst_panel_functions_equal_before_this_batch(self):
        """`discuss` / `summarize_tab` / `discuss_stock` 經 `_gemini_text` → `_parts`（本批未動）。"""
        bundle = {"評分": {"ok": True, "data": {"total": 82}, "provenance": {"source": "FinMind"}}}
        for resp in _ALL_RESPONSES:
            for mode in ("lite", "full"):
                new = S.discuss("stock", bundle, mode=mode, gemini_http=lambda _p, _r=resp: _r)
                old = _old_l3().discuss("stock", bundle, mode=mode, gemini_http=lambda _p, _r=resp: _r)
                assert repr(new) == repr(old), (mode, resp)
            new = S.summarize_tab("x", bundle=bundle, gemini_http=lambda _p, _r=resp: _r)
            old = _old_l3().summarize_tab("x", bundle=bundle, gemini_http=lambda _p, _r=resp: _r)
            assert repr(new) == repr(old)
            new = S.discuss_stock("2330", gemini_http=lambda _p, _r=resp: _r, tools=_FAKE_TOOLS)
            old = _old_l3().discuss_stock("2330", gemini_http=lambda _p, _r=resp: _r, tools=_FAKE_TOOLS)
            assert repr(new) == repr(old)

    _ROOT = pathlib.Path(P.__file__).resolve().parents[3]

    @staticmethod
    def _run_agent_calls(path: pathlib.Path) -> list[ast.Call]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                and getattr(n.func, "id", getattr(n.func, "attr", None)) == "run_agent"]

    def test_b_only_this_card_opts_in(self):
        """全 repo 正式碼（`app.py`／`src/`／`shared/`／`scripts/`）逐一掃 `run_agent(...)` 呼叫點：
        只有 `page_why.load_qa` 帶 `fail_on_blocked_reply=True`；其餘（舊分頁 `tab_ai_chat`）一律不帶、
        也不准用 `**kwargs` 夾帶 —— 它們的輸出必須一字不變。"""
        files = [self._ROOT / "app.py"] + [
            p for d in ("src", "shared", "scripts") for p in sorted((self._ROOT / d).rglob("*.py"))]
        sites = {p.relative_to(self._ROOT).as_posix(): self._run_agent_calls(p) for p in files}
        sites = {k: v for k, v in sites.items() if v}
        why = pathlib.Path(P.__file__).resolve().relative_to(self._ROOT).as_posix()
        assert "src/ui/tabs/tab_ai_chat.py" in sites, "舊分頁仍呼叫 run_agent（前提）"
        opted = []
        for rel, calls in sites.items():
            for c in calls:
                kws = {k.arg: k.value for k in c.keywords}
                assert None not in kws, f"{rel}: run_agent(**...) 可能夾帶旗標"
                if "fail_on_blocked_reply" in kws:
                    opted.append((rel, kws["fail_on_blocked_reply"]))
        assert len(sites[why]) == 1
        assert [r for r, _v in opted] == [why], "⛔ 只有本卡開旗標"
        assert isinstance(opted[0][1], ast.Constant) and opted[0][1].value is True

    def test_b_every_why_card_is_byte_identical_with_or_without_this_batch(self):
        from tests import test_p05_why_v2_cards as E

        def _prints(view):
            _orig = E.P
            E.P = view
            try:
                _notes, builts = E._enumerate()
            finally:
                E.P = _orig
            return [(b[0].key, hashlib.sha256(_fingerprint(view, b).encode()).hexdigest())
                    for b in builts]

        before, after = _prints(_old_view()), _prints(P)
        assert len(after) > 20 and {k for k, _ in after} >= {
            "why.edu.lights", "why.source.none", "why.engineer.gate", "why.qa"}
        assert before == after

    def test_b_no_new_wording_in_either_layer(self):
        """L5：模組層字串常數、短句表一個都沒多、一個都沒改；L3：同。"""
        def _strs(mod):
            return {k: v for k, v in vars(mod).items()
                    if isinstance(v, str) and not k.startswith("__")}
        assert _strs(P) == _strs(_old_view())
        assert P.V2_SHORT_ROWS == _old_view().V2_SHORT_ROWS
        assert _strs(S) == _strs(_old_l3())


# ══════════════════════════════════════════════════════════════════
# (c) 突變 —— 拿掉本批的任何一條判定，(a) 或 (b) 必須失敗
# ══════════════════════════════════════════════════════════════════
def _card_with(monkeypatch, l3, key_or_resp):
    resp = _BLOCKED[key_or_resp][0] if isinstance(key_or_resp, str) else key_or_resp
    qa, built, _c = _pipeline(monkeypatch, resp, l3=l3)
    return qa, built[0]


class TestMutations:
    def test_c_the_view_not_opting_in_turns_a_back_into_a_valid_result(self, monkeypatch):
        m = _mutant(P, *_REVERT_VIEW)
        _qa, built, _c = _pipeline(monkeypatch, _BLOCKED["answer_safety_no_content"][0], view=m)
        assert built[0].state != UI_FAILED and _VALID in built[0].note.why

    def test_c_dropping_the_l3_gate_turns_a_back_into_a_valid_result(self, monkeypatch):
        m = _mutant(S, ("        if fail_on_blocked_reply and not text:\n", "        if False:\n"))
        for key in _BLOCKED:
            _qa, card = _card_with(monkeypatch, m, key)
            assert card.state != UI_FAILED and _VALID in card.note.why, key

    @pytest.mark.parametrize("old,new,key", [
        ('    if isinstance(_pf, dict) and _pf.get("blockReason"):\n', "    if False:\n", "prompt_blocked"),
        ("    if not isinstance(resp, dict):\n", "    if False:\n", "not_an_object"),
        ('    if "candidates" not in resp:\n', "    if False:\n", "no_candidates"),
        ("    if not isinstance(_cands, list) or not _cands:\n", "    if False:\n", "empty_candidates"),
        ("    if not isinstance(_cand, dict):\n", "    if False:\n", "candidate_null"),
        ("    if not isinstance(_c, dict):\n", "    if False:\n", "content_null"),
        ("        _v = {k: type(node[k]).__name__ for k in sorted(node)}\n", "        _v = node\n",
         "candidates_not_a_list"),
        ("        _v = type(node).__name__\n", "        _v = node\n", "parts_a_string"),
    ], ids=["block_reason", "root_type", "candidates_key", "candidates_list", "candidate_type",
            "content_type", "keys_only", "type_name_only"])
    def test_c_dropping_a_structure_check_loses_the_upstream_evidence(self, monkeypatch, old, new, key):
        """拿掉任一條結構判定 → 證據不再是上游收到的形狀（變成 Python 例外、或整包內容倒出來）—— (a) 抓得到。"""
        m = _mutant(S, (old, new))
        qa, card = _card_with(monkeypatch, m, key)
        assert qa.error != _PREFIX + _BLOCKED[key][1]

    def test_c_dropping_the_finish_reason_check_loses_the_upstream_reason(self, monkeypatch):
        """拿掉「非 STOP → 帶出 finishReason 原文」：仍是紅（下一條「缺 STOP → 紅」接住），
        但上游給的原因（SAFETY）不見了，只剩形狀 —— (a) 的逐字比對抓得到。"""
        m = _mutant(S, ('    if _fr and _fr != "STOP":\n', "    if False:\n"))
        qa, _card = _card_with(monkeypatch, m, "answer_safety_empty_text")
        assert qa.error != _PREFIX + _BLOCKED["answer_safety_empty_text"][1] and "SAFETY" not in qa.error

    def test_c_dropping_both_finish_reason_checks_turns_a_safety_block_grey(self, monkeypatch):
        m = _mutant(S, ('    if _fr and _fr != "STOP":\n', "    if False:\n"),
                    ('    if _fr != "STOP":\n', "    if False:\n"))
        _qa, card = _card_with(monkeypatch, m, "answer_safety_empty_text")
        assert card.state != UI_FAILED and _VALID in card.note.why

    def test_c_treating_every_finish_reason_as_a_failure_turns_b_red(self, monkeypatch):
        m = _mutant(S, ('    if _fr and _fr != "STOP":\n', "    if _fr:\n"))
        _qa, card = _card_with(monkeypatch, m, _GENUINE_EMPTY["stop_empty_text"])
        assert card.state == UI_FAILED, "真的沒話說被畫成紅（假警報）—— (b) 必須抓到"

    def test_c_dropping_the_parts_type_check_turns_parts_null_grey(self, monkeypatch):
        m = _mutant(S, ("    if not isinstance(_p, list):\n", "    if False:\n"))
        _qa, card = _card_with(monkeypatch, m, "parts_null")
        assert card.state != UI_FAILED and _VALID in card.note.why

    def test_c_a_strict_parts_lookup_turns_a_natural_empty_red(self, monkeypatch):
        """REST 省略空 list：`STOP` ＋ 沒有 `parts` 必須是灰。嚴格取 `["parts"]` → 假警報 —— (b) 抓得到。"""
        m = _mutant(S, ('    _p = _c.get("parts", [])\n', '    _p = _c["parts"]\n'))
        for key in ("stop_no_parts", "stop_no_content"):
            _qa, card = _card_with(monkeypatch, m, _GENUINE_EMPTY[key])
            assert card.state == UI_FAILED, key

    def test_c_requiring_content_on_stop_turns_a_natural_empty_red(self, monkeypatch):
        m = _mutant(S, ('    _c = _cand.get("content", {})\n', '    _c = _cand["content"]\n'))
        _qa, card = _card_with(monkeypatch, m, _GENUINE_EMPTY["stop_no_content"])
        assert card.state == UI_FAILED, "STOP 而沒有 content 被畫成紅（假警報）—— (b) 必須抓到"

    def test_c_accepting_a_missing_finish_reason_turns_an_unfinished_reply_grey(self, monkeypatch):
        """只有明講 `STOP` 才是灰：拿掉「缺席 → 紅」這一條，模型沒說它停了的空回覆就被說成「有效結果」。"""
        m = _mutant(S, ('    if _fr != "STOP":\n', "    if False:\n"))
        for key in ("no_finish_reason", "no_finish_reason_no_parts"):
            _qa, card = _card_with(monkeypatch, m, key)
            assert card.state != UI_FAILED and _VALID in card.note.why, key

    def test_c_checking_answers_that_have_text_turns_b_red(self, monkeypatch):
        m = _mutant(S, ("        if fail_on_blocked_reply and not text:\n",
                        "        if fail_on_blocked_reply:\n"))
        _qa, card = _card_with(monkeypatch, m, _GENUINE_TEXT["partial_with_safety"])
        assert card.state == UI_FAILED, "有字的回答被改判 —— (b) 必須抓到"

    def test_c_flipping_the_default_changes_the_legacy_caller(self):
        m = _mutant(S, ("              fail_on_blocked_reply: bool = False) -> QAResult:",
                        "              fail_on_blocked_reply: bool = True) -> QAResult:"))
        resp = _BLOCKED["answer_safety_no_content"][0]
        new = m.run_agent(_Q, api_key="x", gemini_http=lambda _p: resp, tools={})
        old = _old_l3().run_agent(_Q, api_key="x", gemini_http=lambda _p: resp, tools={})
        assert repr(new) != repr(old), "預設值一翻，舊分頁的輸出就變 —— 上面的逐字比對必須抓到"
