# -*- coding: utf-8 -*-
"""I2（2026-08-10）— `bias_240` 的估算旗標必須被揭露，且**判定一位都不准變**。

病史（本檔存在的理由）
────────────────────────────────────────────────────────────────
`src/data/macro/macro_snapshot.compute_twii_bias` 在 TWII 歷史不足 240 個交易日時，
用「手上全部資料的均值」當 MA240（`_cs.tail(min(240, _n)).mean()`），並誠實回傳
`is_estimated=True` + `data_days=N`。

**但那個旗標只被 1／10 個消費點讀到。** 2026-08-10 盤點，讀 `bias_240` 的地方有：

    src/compute/macro/macro_helpers.compute_five_bucket_summary   五桶燈號
    src/services/app_ai_service.build_llm_context                 → 餵 Gemini
    src/ui/tabs/macro/section_news_ai.py     `_ctx`               → 餵 Gemini（live）
    src/ui/tabs/macro/section_warroom.py                          紅線 + 5 分鐘清單 + v4 位階
    src/ui/tabs/macro/section_mid.py                              策略1 二維矩陣
    src/ui/tabs/macro/section_long.py                             ← 唯一有揭露的
    src/ui/tabs/stock_sections/section_op_recommendation.py       個股即時操作建議
    （另有 section_state / section_cross_ai / data_registry_scanner，見報告盤點表）

其中最危險的是兩處 prompt：送進 Gemini 的只有一個數字，模型沒有任何依據能分辨
「這是實測年線」還是「這其實是 MA90」，只能當實測值寫進建議
（§1「錯誤的數字比沒有數字更危險」）。

本批的範圍（**只揭露，不動判定**）
────────────────────────────────────────────────────────────────
允許：把 `is_estimated` 傳下去，並在**顯示文字與 prompt 文字**上標明。
不允許：讓 `is_estimated` 影響任何燈號 / 門檻 / 分數 / 桶判定
        —— 那是行為變更，依 §-1 需 user 明確指派。

本檔釘的東西
────────────────────────────────────────────────────────────────
  A. **行為**：L2 揭露 SSOT 的三態（估算 / 非估算 / 旗標缺席）。
  B. **行為**：`compute_twii_bias` 的 240 天翻轉點（釘住 `BIAS_MA240_FULL_WINDOW_DAYS`
     這個常數確實與上游同一個數字 —— 用**跑一次**證明，不掃原始碼字面）。
  C. **行為 · 本檔最重要的一組**：`compute_five_bucket_summary` 在
     `is_estimated=True` / `False` 兩種輸入下，**每一桶的 level / label / 每盞燈的
     danger 逐位相同**，且整棵輸出樹的唯一差異就是那三個字的徽章。
     ⇒ 這就是「本批零行為變更」的證明。
  D. **行為**：`build_llm_context` / `generate_ai_comment` 的實際輸出字串。
  E. **行為（AppTest 真 render）**：個股「即時操作建議」section 的揭露 caption。
  F. **wiring（AST）**：另外 4 個 UI / prompt 消費點真的呼叫了 helper。

── 為什麼 F 用 AST 而不是字串掃描 ───────────────────────────────
沿用 `tests/test_g1_llm_stale_tagging.py` 立下的規矩：
**守衛照抄實作字面，所以它永遠不會發現實作有問題。**
故 F 組：完全走 `ast`（註解在 AST 裡不存在、docstring 是 `ast.Constant` 不是
`ast.Call`，天生不可能被誤判）；檢查的是「helper 真的被呼叫、而且引數是那個
bias dict」這個**語意**；失敗訊息印出 `檔:行` 與該行原文；並用 `TestGuardItself`
拿一段刻意在註解 / docstring / 字串字面裡寫滿假 wiring 的原始碼證明守衛不上當。

⚠️ 本檔**不吃執行當天的日期**：I2 的揭露與時間無關，
   `compute_twii_bias` 的測資用固定起始日的 `date_range`。
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.compute.macro.macro_helpers import (
    BIAS_MA240_FULL_WINDOW_DAYS,
    MACRO_ESTIMATED_LEGEND,
    bias_data_days,
    bias_estimated_badge,
    bias_estimated_note,
    bias_estimated_prompt_prefix,
    bias_is_estimated,
    compute_five_bucket_summary,
    macro_estimated_legend,
)

_REPO = Path(__file__).resolve().parent.parent

#: 徽章字面（本檔唯一一處寫死它 —— 其餘斷言一律引 `bias_estimated_badge()` 的輸出）
_BADGE = "（估算）"

#: 「估算」與「非估算」兩份 bias_info，數值完全相同、只差旗標。
_BIAS_EST = {"bias_240": 32.7, "bias_20": 5.1, "price": 26000.0,
             "ma240": 19593.0, "data_days": 90, "is_estimated": True}
_BIAS_FULL = {"bias_240": 32.7, "bias_20": 5.1, "price": 26000.0,
              "ma240": 19593.0, "data_days": 240, "is_estimated": False}


# ══════════════════════════════════════════════════════════════
# A. L2 揭露 SSOT 的三態（純函式行為）
# ══════════════════════════════════════════════════════════════
class TestBiasIsEstimated:

    def test_true_only_when_flag_says_so(self):
        assert bias_is_estimated(_BIAS_EST) is True
        assert bias_is_estimated(_BIAS_FULL) is False

    @pytest.mark.parametrize("bad", [None, {}, [], "x", 0, {"bias_240": 1.0}])
    def test_missing_flag_is_not_estimated(self, bad):
        """§1：旗標缺席 → False，且**不得**從 data_days 倒推（那會變第二套判定）。"""
        assert bias_is_estimated(bad) is False

    def test_does_not_infer_from_data_days(self):
        """只有 data_days=10、沒有旗標 → 仍判非估算（不猜、不反推）。"""
        assert bias_is_estimated({"bias_240": 1.0, "data_days": 10}) is False


class TestBiasDataDays:

    def test_reads_the_real_count(self):
        assert bias_data_days(_BIAS_EST) == 90

    @pytest.mark.parametrize("bad", [
        None, {}, {"data_days": None}, {"data_days": "abc"}, {"data_days": 0},
        {"data_days": -3},
    ])
    def test_unusable_returns_none_not_zero(self, bad):
        """§1：取不到 → None。回 0 會被格式化成「0 天資料」= 一個具體但假的讀數。"""
        assert bias_data_days(bad) is None


class TestBadgeAndNote:

    def test_badge_three_states(self):
        assert bias_estimated_badge(_BIAS_EST) == _BADGE
        assert bias_estimated_badge(_BIAS_FULL) == ""
        assert bias_estimated_badge(None) == ""

    def test_note_says_actual_days_and_required_days(self):
        note = bias_estimated_note(_BIAS_EST)
        assert note, "估算時必須有揭露句"
        assert "90" in note, f"沒講實際用了幾天：{note}"
        assert str(BIAS_MA240_FULL_WINDOW_DAYS) in note, f"沒講年線需要幾天：{note}"
        assert "估算" in note

    def test_note_admits_the_verdict_was_not_adjusted(self):
        """本批只揭露不改判定 —— 這件事必須一起講。

        只寫「這是估算值」而不寫「燈號仍照它判」，使用者會誤以為系統已經
        對估算值做了特別處理（那才是真正誤導的版本）。
        """
        note = bias_estimated_note(_BIAS_EST)
        assert "燈號" in note and "門檻" in note, (
            f"揭露句沒有說明「判定未跟著調整」：{note}")

    def test_note_is_empty_when_not_estimated(self):
        assert bias_estimated_note(_BIAS_FULL) == ""
        assert bias_estimated_note(None) == ""

    def test_note_handles_missing_data_days_without_faking_a_number(self):
        """有旗標、沒 data_days → 照實說天數不明，**不得**編一個天數出來。

        （不能直接斷言 `'0 個交易日' not in note` —— 「年線需要 240 個交易日」
        本來就含這串子字串。改為斷言「報實際天數」的那句話沒出現。）
        """
        note = bias_estimated_note({"bias_240": 1.0, "is_estimated": True})
        known = bias_estimated_note({"bias_240": 1.0, "is_estimated": True,
                                     "data_days": 90})
        assert note
        assert "不明" in note, note
        assert "目前只有" in known and "目前只有" not in note, (
            f"天數缺席時仍宣稱「目前只有 N 個交易日」= 編了一個數字：{note}")


class TestPromptPrefixAndLegend:

    def test_prefix_shape_matches_the_g1_convention(self):
        """與 `macro_stale_prefix` 的 `'[STALE:67d] '` 同一套：方括號 + 結尾一個空格。"""
        pre = bias_estimated_prompt_prefix(_BIAS_EST)
        assert pre == "[ESTIMATED:MA90/240] ", pre
        assert pre.startswith("["), "行首標記必須是方括號（沿用 G1 慣例）"
        assert pre.endswith(" "), "結尾要留一個空格，才能直接串在指標名稱前"

    def test_prefix_uses_the_ssot_window_constant(self):
        assert str(BIAS_MA240_FULL_WINDOW_DAYS) in bias_estimated_prompt_prefix(_BIAS_EST)

    def test_prefix_empty_when_not_estimated(self):
        assert bias_estimated_prompt_prefix(_BIAS_FULL) == ""
        assert bias_estimated_prompt_prefix(None) == ""

    def test_prefix_marks_unknown_days_explicitly(self):
        """§1：天數不明時不留白、不假裝知道。"""
        pre = bias_estimated_prompt_prefix({"bias_240": 1.0, "is_estimated": True})
        assert pre == "[ESTIMATED:MA?/240] ", pre

    def test_legend_only_when_tag_present(self):
        assert macro_estimated_legend("• [ESTIMATED:MA90/240] BIAS240：+32.7%") == \
            MACRO_ESTIMATED_LEGEND
        assert macro_estimated_legend("• BIAS240：+32.7%") == ""
        assert macro_estimated_legend("") == ""
        assert macro_estimated_legend(None) == ""

    def test_legend_actually_explains_the_tag(self):
        """只丟 `[ESTIMATED:...]` 給 LLM 等於沒標 —— 圖例必須有行為指令。"""
        assert "[ESTIMATED:" in MACRO_ESTIMATED_LEGEND
        assert "不得" in MACRO_ESTIMATED_LEGEND, "圖例只描述、沒下指令 → LLM 照樣當實測值講"
        assert "估算" in MACRO_ESTIMATED_LEGEND

    def test_legend_is_not_the_stale_legend(self):
        """兩套標記各自獨立;圖例不得互相抄（抄了就會對 LLM 說錯話）。"""
        from src.services.ai_structured_summary import MACRO_STALE_LEGEND
        assert MACRO_ESTIMATED_LEGEND != MACRO_STALE_LEGEND
        assert "[STALE:" not in MACRO_ESTIMATED_LEGEND
        assert "[ESTIMATED:" not in MACRO_STALE_LEGEND


# ══════════════════════════════════════════════════════════════
# B. 上游翻轉點（行為，不掃 240 這個字面）
# ══════════════════════════════════════════════════════════════
def _twii_df(n: int) -> pd.DataFrame:
    """固定起始日的 n 列收盤 —— 不吃執行當天日期。"""
    return pd.DataFrame(
        {"Close": np.linspace(20000.0, 21000.0, n)},
        index=pd.date_range("2024-01-01", periods=n, freq="D"),
    )


class TestUpstreamEstimatedThreshold:
    """`BIAS_MA240_FULL_WINDOW_DAYS` 必須與 `compute_twii_bias` 是同一個數字。

    用**跑一次**證明翻轉點，不是去 grep 原始碼裡的 `240` ——
    後者只會抄實作，實作改了它也跟著改，永遠不會紅。
    """

    def test_one_day_short_is_estimated(self, monkeypatch):
        import src.data.macro.macro_snapshot as snap
        calls: list[int] = []

        def _no_2y():
            calls.append(1)
            return None        # 離線 / 上游不可用 → 只能用手上的天數

        monkeypatch.setattr(snap, "fetch_twii_2y_for_ma240", _no_2y)

        n = BIAS_MA240_FULL_WINDOW_DAYS - 1
        out = snap.compute_twii_bias(_twii_df(n))
        assert calls == [1], "monkeypatch 的 fetch_twii_2y_for_ma240 沒有被呼叫到 —— patch 目標失效"
        assert out is not None
        assert out["data_days"] == n
        assert out["is_estimated"] is True

    def test_exactly_full_window_is_not_estimated(self, monkeypatch):
        import src.data.macro.macro_snapshot as snap
        calls: list[int] = []

        def _no_2y():
            calls.append(1)
            return None

        monkeypatch.setattr(snap, "fetch_twii_2y_for_ma240", _no_2y)

        n = BIAS_MA240_FULL_WINDOW_DAYS
        out = snap.compute_twii_bias(_twii_df(n))
        assert calls == [], (
            "資料已滿 240 天卻仍去抓 2y —— 表示翻轉點與 "
            "BIAS_MA240_FULL_WINDOW_DAYS 不同步")
        assert out is not None
        assert out["is_estimated"] is False
        assert out["data_days"] == n

    def test_estimated_ma240_is_really_the_short_window_mean(self, monkeypatch):
        """揭露的前提：`ma240` 在估算時確實是「手上全部資料的均值」。"""
        import src.data.macro.macro_snapshot as snap
        calls: list[int] = []
        monkeypatch.setattr(snap, "fetch_twii_2y_for_ma240",
                            lambda: (calls.append(1), None)[1])
        df = _twii_df(90)
        out = snap.compute_twii_bias(df)
        assert calls == [1]
        assert out["ma240"] == pytest.approx(float(df["Close"].mean()))

    def test_producer_output_feeds_the_disclosure_helpers(self, monkeypatch):
        """端到端：producer 的回傳直接餵 helper 就能產生揭露（不必 caller 自行加工）。"""
        import src.data.macro.macro_snapshot as snap
        calls: list[int] = []
        monkeypatch.setattr(snap, "fetch_twii_2y_for_ma240",
                            lambda: (calls.append(1), None)[1])
        out = snap.compute_twii_bias(_twii_df(90))
        assert calls == [1]
        assert bias_estimated_badge(out) == _BADGE
        assert bias_estimated_prompt_prefix(out) == "[ESTIMATED:MA90/240] "
        assert "90" in bias_estimated_note(out)

    def test_docstring_still_documents_the_consumer_contract(self):
        """揭露本身是文字 —— 這是唯一能守住「別把契約無聲拿掉」的方式。"""
        from src.data.macro.macro_snapshot import compute_twii_bias
        doc = inspect.getdoc(compute_twii_bias) or ""
        assert "is_estimated" in doc and "240" in doc, doc


# ══════════════════════════════════════════════════════════════
# C. 五桶：揭露有出現，但**判定逐位相同**（本檔最重要的一組）
# ══════════════════════════════════════════════════════════════
_MACRO_INFO = {
    "vix": {"current": 35.0},
    "ism_pmi": {"value": 44.0},
    "us_core_cpi": {"yoy": 4.5},
    "tw_export": {"yoy": -8.0},
    "ndc_signal": {"score": 14.0},
    "us10y": {"current": 4.63},
}
_WARROOM = {"health_score": 30.0}
_M1B = {"gap": -0.5}
_CL_DATA = {"margin": 3500.0}
_NEWS = [{"is_systemic": True}, {"is_systemic": True}]


def _five(bias_info):
    return compute_five_bucket_summary(
        macro_info=_MACRO_INFO, warroom_summary=_WARROOM,
        m1b_m2_info=_M1B, bias_info=bias_info, cl_data=_CL_DATA,
        news_items=_NEWS,
    )


def _strip_badge(obj):
    """遞迴把徽章從所有字串拿掉（用來證明「差異只有徽章」）。"""
    if isinstance(obj, dict):
        return {k: _strip_badge(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(_strip_badge(v) for v in obj)
    if isinstance(obj, str):
        return obj.replace(_BADGE, "")
    return obj


def _verdicts(summary):
    """只取**判定**欄位：桶等級 / 桶標籤 / 每盞燈的顏色。顯示字串一律不取。"""
    return {
        bucket: (
            payload["level"],
            payload["label"],
            payload["color"],
            payload["emoji"],
            tuple((d["key"], d["danger"]) for d in payload["details"]),
        )
        for bucket, payload in summary.items()
    }


#: 涵蓋 bias_240 的綠 / 黃 / 紅（high_bad，SSOT 黃 10 紅 20）與負乖離側
_BIAS_VALUES = [-30.0, -15.0, 0.0, 5.0, 9.9, 10.0, 15.0, 19.9, 20.0, 32.7, 60.0]


class TestFiveBucketZeroBehaviourChange:

    @pytest.mark.parametrize("b240", _BIAS_VALUES)
    def test_verdicts_are_bit_identical(self, b240):
        """**本批零行為變更的證明**：燈號 / 桶等級 / 標籤在兩種旗標下完全一樣。"""
        est = _five({"bias_240": b240, "data_days": 90, "is_estimated": True})
        full = _five({"bias_240": b240, "data_days": 240, "is_estimated": False})
        assert _verdicts(est) == _verdicts(full), (
            f"bias_240={b240} 時，is_estimated 改變了判定 —— "
            "本批只准揭露、不准動判定（§-1）")

    @pytest.mark.parametrize("b240", _BIAS_VALUES)
    def test_only_difference_is_the_badge(self, b240):
        """整棵輸出樹拿掉徽章後必須完全相同 —— 連 headline 的措辭都不准變。"""
        est = _five({"bias_240": b240, "data_days": 90, "is_estimated": True})
        full = _five({"bias_240": b240, "data_days": 240, "is_estimated": False})
        assert _strip_badge(est) == full

    def test_flagless_bias_info_is_byte_identical_to_before(self):
        """既有 caller（不帶旗標的舊快照 / 測試 fixture）輸出一字不變。"""
        no_flag = _five({"bias_240": 32.7})
        full = _five({"bias_240": 32.7, "is_estimated": False})
        assert no_flag == full
        assert _BADGE not in str(no_flag)

    def test_badge_actually_shows_up(self):
        """反向守衛：上面兩條若因為徽章根本沒接上而恆綠，這條會紅。"""
        est = _five({"bias_240": 32.7, "data_days": 90, "is_estimated": True})
        detail = _bias_detail(est)
        assert detail["value_str"].endswith(_BADGE), (
            f"五桶的 bias_240 顯示值沒有帶估算徽章：{detail['value_str']}")
        assert "32.7" in detail["value_str"], "揭露不得把原始數字改掉"

    def test_badge_reaches_the_headline_when_bias_is_the_worst_light(self):
        """bias_240 是該桶主因時，桶 headline（給人看的那句）也要帶徽章。

        情境取自既有回歸測試 `test_macro_buckets.
        test_five_bucket_mid_red_label_overheat_on_bias`（PMI/CPI/出口皆綠、
        只有 BIAS240 過熱轉紅 ⇒ 主因必定是 BIAS240），不靠碰運氣。
        """
        _kw = dict(macro_info={"ism_pmi": {"value": 55}, "us_core_cpi": {"yoy": 2.0},
                               "tw_export": {"yoy": 54.6}})
        est = compute_five_bucket_summary(
            bias_info={"bias_240": 32.7, "data_days": 90, "is_estimated": True}, **_kw)
        full = compute_five_bucket_summary(
            bias_info={"bias_240": 32.7, "data_days": 240, "is_estimated": False}, **_kw)
        assert est["mid"]["level"] == full["mid"]["level"] == "red"
        assert "年線乖離" in est["mid"]["headline"], est["mid"]["headline"]
        assert _BADGE in est["mid"]["headline"], est["mid"]["headline"]
        assert _BADGE not in full["mid"]["headline"]
        # 判定側（等級 + 紅燈方向標籤）仍逐位相同
        assert est["mid"]["label"] == full["mid"]["label"] == "循環過熱"

    def test_no_badge_glued_onto_a_missing_value(self):
        """§1：沒有數字時是「—」，不得變成「—（估算）」這種假裝有讀數的組合。"""
        est = _five({"data_days": 90, "is_estimated": True})   # 沒有 bias_240
        detail = _bias_detail(est)
        assert detail["value_str"] == "—", detail["value_str"]
        assert detail["danger"] == "gray"


def _bias_detail(summary):
    for payload in summary.values():
        for d in payload["details"]:
            if d["key"] == "bias_240":
                return d
    raise AssertionError("五桶裡找不到 bias_240 這盞燈（spec 被移除了？）")


# ══════════════════════════════════════════════════════════════
# D. 兩個 prompt builder 的實際輸出（行為斷言，不掃原始碼）
# ══════════════════════════════════════════════════════════════
class _StubST:
    """取代 `app_ai_service.st`（同 test_g1 的作法）。"""

    def __init__(self, session_state=None):
        self.session_state = session_state if session_state is not None else {}
        self.secrets: dict = {}


@pytest.fixture
def ctx(monkeypatch):
    """回一個 `(macro_info, session_state) -> str` 的呼叫器。"""
    from src.services import app_ai_service as A

    def _call(macro_info: dict, session_state: dict | None = None) -> str:
        stub = _StubST(session_state)
        monkeypatch.setattr(A, "st", stub)
        out = A.build_llm_context(macro_info)
        _call.last_stub = stub
        return out

    return _call


class TestBuildLlmContextEstimatedTag:

    def test_stub_is_actually_read_first(self, ctx):
        """先證明 patch 有效，否則以下斷言全部不可信（假綠防護）。"""
        out = ctx({}, {"bias_info": {"bias_240": 8.5}})
        assert "BIAS240：+8.5%" in out, (
            "stub 的 session_state 沒被讀到 —— patch 目標失效")

    def test_estimated_bias_is_tagged_and_explained(self, ctx):
        out = ctx({}, {"bias_info": _BIAS_EST})
        assert "[ESTIMATED:MA90/240] " in out, out
        assert MACRO_ESTIMATED_LEGEND in out, "標了卻不解釋 → LLM 讀不懂這個標記"
        assert "+32.7%" in out, "揭露不得把原始數字改掉"

    def test_tag_sits_between_bullet_and_indicator_name(self, ctx):
        """`• [ESTIMATED:...] 指標…` —— 標記不得破壞 bullet 結構。"""
        out = ctx({}, {"bias_info": _BIAS_EST})
        tagged = [ln for ln in out.splitlines() if "[ESTIMATED:" in ln
                  and not ln.startswith("⚠️")]
        assert len(tagged) == 1, tagged
        assert tagged[0].startswith("• [ESTIMATED:"), tagged[0]

    def test_full_window_bias_is_not_tagged(self, ctx):
        out = ctx({}, {"bias_info": _BIAS_FULL})
        assert "BIAS240：+32.7%" in out
        assert "[ESTIMATED:" not in out, "足額 240 天卻被標估算"
        assert MACRO_ESTIMATED_LEGEND not in out, "沒有估算就不該塞圖例（製造雜訊）"

    def test_flagless_output_is_unchanged(self, ctx):
        """回歸釘：舊 caller（bias_info 不帶旗標）輸出與 I2 前逐字元相同。"""
        out = ctx({}, {"bias_info": {"bias_240": 8.5}})
        assert out == "• 台股大盤年線乖離率 BIAS240：+8.5%", repr(out)

    def test_both_legends_coexist_without_breaking_bullets(self, ctx):
        """過期 + 估算同時出現：兩段圖例都在，資料行仍是合法 bullet。"""
        out = ctx(
            {"us_core_cpi": {"yoy": 3.1, "date": "2020-01-01"}},   # 固定舊日期
            {"bias_info": _BIAS_EST},
        )
        from src.services.ai_structured_summary import MACRO_STALE_LEGEND
        assert MACRO_STALE_LEGEND in out
        assert MACRO_ESTIMATED_LEGEND in out
        lines = [ln for ln in out.splitlines() if ln.strip()]
        assert lines[0] == MACRO_STALE_LEGEND, "過期圖例應排在最前（沿用 G1 既有順序）"
        assert lines[1] == MACRO_ESTIMATED_LEGEND
        data_lines = lines[2:]
        assert data_lines and all(ln.startswith("• ") for ln in data_lines), data_lines


class TestGenerateAiCommentBadge:
    """個股「即時操作建議」的 rule-based 文案 —— 加徽章，但判定分支不准動。"""

    _BASE = {"score": 0, "rsi": 50, "val_label": "", "trend": "",
             "cl": 0, "cx": 0, "foreign_buy": 0, "trust_buy": 0,
             "vcp_ok": False, "m1b_diff": 0, "bias_20": 0}

    def _call(self, b240, bias_info=None):
        from src.services.app_ai_service import generate_ai_comment
        data = dict(self._BASE, bias_240=b240)
        if bias_info is not None:
            data["bias_info"] = bias_info
        return generate_ai_comment(data)

    @pytest.mark.parametrize("b240", [-30.0, -25.0, -20.0, 0.0, 25.0, 26.0, 33.0])
    def test_only_difference_is_the_badge(self, b240):
        est = self._call(b240, _BIAS_EST)
        full = self._call(b240, _BIAS_FULL)
        assert _strip_badge(est) == full, (
            f"bias_240={b240}:估算旗標改變了文案內容（不只是徽章）")

    @pytest.mark.parametrize("b240", [-30.0, 0.0, 33.0])
    def test_omitting_bias_info_is_backward_compatible(self, b240):
        """回歸釘：不帶 `bias_info` 的舊 caller 輸出逐字元不變。"""
        assert self._call(b240) == self._call(b240, _BIAS_FULL)

    def test_overheat_line_carries_the_badge(self):
        out = self._call(33.0, _BIAS_EST)
        line = next(ln for ln in out.splitlines() if "過熱警告" in ln)
        assert _BADGE in line, line
        assert "33" in line, "揭露不得把原始數字改掉"

    def test_undervalued_line_carries_the_badge(self):
        out = self._call(-25.0, _BIAS_EST)
        line = next(ln for ln in out.splitlines() if "低估機會" in ln)
        assert _BADGE in line, line

    def test_no_badge_when_full_window(self):
        assert _BADGE not in self._call(33.0, _BIAS_FULL)


# ══════════════════════════════════════════════════════════════
# E. AppTest 真 render：個股「即時操作建議」的揭露 caption
# ══════════════════════════════════════════════════════════════
def _op_driver(bias_info: dict) -> str:
    return f'''
import sys, os
sys.path.insert(0, os.getcwd())
import streamlit as st
st.session_state["bias_info"] = {bias_info!r}
st.session_state["m1b_m2_info"] = {{"m1b_yoy": 5.0, "m2_yoy": 3.0}}
st.session_state["cl_data"] = {{"inst": {{}}}}
from src.ui.tabs.stock_sections.section_op_recommendation import (
    render_op_recommendation_section,
)
render_op_recommendation_section("2330", 82.0, {{"contracting": True}},
                                 5.0, 100.0, 55.0, 0, 0)
'''


def _run_app(body: str):
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(body, default_timeout=60)
    at.run()
    if at.exception:
        pytest.fail("render 有 uncaught exception:\n" + "\n".join(
            f"{e.type}: {str(e.value)[:300]}" for e in at.exception))
    return at


def _texts(at) -> list[str]:
    """收 caption + markdown 的文字（不同 streamlit 版本 `st.caption` 落點不同）。"""
    out: list[str] = []
    for attr in ("caption", "markdown"):
        for el in getattr(at, attr, []) or []:
            try:
                out.append(str(el.value))
            except Exception:      # noqa: BLE001 — 元素型別差異，不讓收集器本身炸掉
                pass
    return out


class TestOpRecommendationRender:
    """AppTest 真 render 個股「即時操作建議」—— 揭露有沒有真的長在畫面上。"""

    def test_estimated_shows_disclosure(self):
        at = _run_app(_op_driver(_BIAS_EST))
        texts = _texts(at)
        assert texts, "render 完全沒有輸出元素 —— driver 沒跑到 section"
        assert any("年線乖離是" in t and "90" in t for t in texts), (
            f"估算時畫面上找不到揭露。實得文字：{texts}")

    def test_full_window_shows_no_disclosure(self):
        at = _run_app(_op_driver(_BIAS_FULL))
        texts = _texts(at)
        assert texts, "render 完全沒有輸出元素 —— driver 沒跑到 section"
        assert not any("年線乖離是" in t for t in texts), (
            f"非估算卻出現估算揭露：{texts}")


# ══════════════════════════════════════════════════════════════
# F. wiring（AST）—— 其餘 4 個消費點真的呼叫了 helper
# ══════════════════════════════════════════════════════════════
def _load(rel: str) -> tuple[ast.AST, list[str]]:
    src = (_REPO / rel).read_text(encoding="utf-8")
    return ast.parse(src), src.splitlines()


def _calls_with_arg(tree: ast.AST, helper: str) -> list[tuple[str, int]]:
    """子樹內 `helper(<Name>)` 的 (第一個引數變數名, lineno)。

    只認 `ast.Call` 且 `func` 是 `ast.Name` —— 註解在 AST 裡不存在，
    docstring / 字串字面是 `ast.Constant`，兩者天生不可能被算成 wiring。
    第一個引數非單純變數（例：字面 dict）→ 記為 `<expr>`。
    """
    out: list[tuple[str, int]] = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == helper):
            arg0 = n.args[0] if n.args else None
            name = arg0.id if isinstance(arg0, ast.Name) else "<expr>"
            out.append((name, n.lineno))
    return out


#: (檔案, 該檔持有 bias dict 的變數名, 必須被呼叫的 helper 別名)
_UI_SITES = [
    ("src/ui/tabs/macro/section_long.py", "_bias_info",
     ("_bias_est_badge", "_bias_est_note")),
    ("src/ui/tabs/macro/section_warroom.py", "_wr_bias",
     ("_bias_est_badge", "_bias_est_note")),
    ("src/ui/tabs/macro/section_mid.py", "_bias_info8",
     ("_bias_est_note",)),
    ("src/ui/tabs/stock_sections/section_op_recommendation.py", "_bias_g",
     ("_bias_est_note",)),
]


class TestUiWiring:

    @pytest.mark.parametrize("rel,var,helpers", _UI_SITES)
    def test_helper_called_with_the_bias_dict(self, rel, var, helpers):
        tree, lines = _load(rel)
        for helper in helpers:
            hits = _calls_with_arg(tree, helper)
            assert hits, (
                f"{rel}: 完全沒有呼叫 `{helper}(...)` —— 這個消費點沒有揭露估算值")
            args = {a for a, _ in hits}
            assert var in args, (
                f"{rel}: `{helper}` 沒有吃該檔的 bias dict `{var}`，實得引數 "
                f"{sorted(args)}。命中行：\n" + "\n".join(
                    f"  {rel}:{ln}: {lines[ln - 1].strip()}" for _, ln in hits))


#: 兩處真的會餵給 Gemini 的 prompt：必須有標記 helper + 圖例 helper
_PROMPT_SITES = [
    ("src/ui/tabs/macro/section_news_ai.py", "_ctx",
     "_bias_est_prefix", "_macro_est_legend", "_bi_d"),
    ("src/services/app_ai_service.py", "_lines",
     "_est_prefix", "_est_legend", "_bi"),
]


def _append_calls(tree: ast.AST, list_name: str) -> list[ast.Call]:
    """`<list_name>.append(...)` 的所有呼叫節點（沿用 test_g1 的作法）。"""
    return [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute) and n.func.attr == "append"
        and isinstance(n.func.value, ast.Name) and n.func.value.id == list_name
    ]


class TestPromptWiring:
    """餵 LLM 的兩處必須把估算標記真的用在 BIAS240 那一行上。"""

    @pytest.mark.parametrize("rel,list_name,prefix,legend,var", _PROMPT_SITES)
    def test_anchor_exists(self, rel, list_name, prefix, legend, var):
        """錨點消失 → 守衛靜默失效，先擋在這裡。"""
        tree, _ = _load(rel)
        assert _append_calls(tree, list_name), (
            f"{rel}: 找不到任何 `{list_name}.append(...)` —— 變數被改名？"
            f"請同步更新本檔 _PROMPT_SITES，否則本組守衛等於沒有")

    @pytest.mark.parametrize("rel,list_name,prefix,legend,var", _PROMPT_SITES)
    def test_prefix_is_used_inside_an_appended_line(self, rel, list_name,
                                                    prefix, legend, var):
        tree, lines = _load(rel)
        hits: list[tuple[str, int]] = []
        for call in _append_calls(tree, list_name):
            hits += _calls_with_arg(call, prefix)
        assert hits, (
            f"{rel}: `{list_name}.append(...)` 裡沒有任何 `{prefix}(...)` 呼叫 —— "
            f"BIAS240 還是裸數字送進 Gemini")
        args = {a for a, _ in hits}
        assert var in args, (
            f"{rel}: `{prefix}` 沒有吃 bias dict `{var}`，實得 {sorted(args)}。"
            "命中行：\n" + "\n".join(
                f"  {rel}:{ln}: {lines[ln - 1].strip()}" for _, ln in hits))

    @pytest.mark.parametrize("rel,list_name,prefix,legend,var", _PROMPT_SITES)
    def test_legend_is_attached(self, rel, list_name, prefix, legend, var):
        """標了卻不附圖例 = LLM 讀不懂 `[ESTIMATED:...]`，等於沒標。"""
        tree, _ = _load(rel)
        assert _calls_with_arg(tree, legend), (
            f"{rel}: 沒有呼叫 `{legend}(...)` —— 估算標記缺少圖例")


# ══════════════════════════════════════════════════════════════
# G. 守衛自檢 —— 證明 F 組不是在掃字面
# ══════════════════════════════════════════════════════════════
_DECOY = '''
"""這個 docstring 裡寫滿假 wiring：
_ctx.append(f'{_bias_est_prefix(_bi_d)}BIAS240')
_bias_est_note(_wr_bias)
"""
# 註解也寫一份：_ctx.append(f'{_bias_est_prefix(_bi_d)}BIAS240')
def f():
    """_bias_est_note(_bias_info)"""
    other = []
    other.append("_bias_est_prefix(_bi_d)")        # 字串字面，不是呼叫
    _ctx.append(f'{_bias_est_prefix(_fake_var)}X')  # ← 唯一真的呼叫
'''


class TestGuardItself:

    def test_not_fooled_by_comments_docstrings_or_string_literals(self):
        tree = ast.parse(_DECOY)
        args: list[str] = []
        for call in _append_calls(tree, "_ctx"):
            args += [a for a, _ in _calls_with_arg(call, "_bias_est_prefix")]
        assert args == ["_fake_var"], (
            f"守衛被註解 / docstring / 字串字面騙到了：{args}")

    def test_string_literal_that_looks_like_a_call_is_not_counted(self):
        tree = ast.parse(_DECOY)
        args: list[str] = []
        for call in _append_calls(tree, "other"):
            args += [a for a, _ in _calls_with_arg(call, "_bias_est_prefix")]
        assert args == []

    def test_note_helper_in_docstring_is_not_counted_as_wiring(self):
        """docstring 裡的 `_bias_est_note(_bias_info)` 不是呼叫節點。"""
        tree = ast.parse(_DECOY)
        assert _calls_with_arg(tree, "_bias_est_note") == []

    def test_append_calls_scoped_to_the_named_list(self):
        tree = ast.parse(_DECOY)
        assert len(_append_calls(tree, "_ctx")) == 1
        assert len(_append_calls(tree, "other")) == 1
        assert _append_calls(tree, "不存在的變數") == []
