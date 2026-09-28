"""批 W（2026-09-28）持股頁／今天頁文字指引修正的守衛：H1-f1／H1-f3／H1-f4／SA2-f1。

~~每一條都以「修前行為會紅」為準（突變驗證見交付報告）。~~
← 2026-09-28 更正（有意識的更正，⛔ 不是漏刪）：上句是錯的全稱句 —— 批 W 獨立 QA 在修前的
origin/main（`d61a1fd`）上實跑本檔的原 22 條，結果 16 紅 6 綠；追加第 7 條守衛後，實作組在同一版本
重跑本檔 23 條：16 紅 7 綠。**現行如實描述**（本檔兩類測試）：
  · **修前會紅**（16 條）：直接釘住本批修掉的錯誤行為。
  · **修後不變守衛**（7 條，修前本來就綠）：釘住本批 ⛔ 不准順手改到的既有文字／行為，
    有效性靠**突變驗證**（改動守衛目標就轉紅；見交付報告）。每一條的 docstring 以
    「修後不變守衛」開頭標明，名單：
      `test_var_card_where_is_unchanged`、`test_var_short_row_is_unchanged`、
      `test_station_own_error_keeps_the_original_sentence`、
      `test_other_error_src_keeps_the_original_sentence[none]`／`[station]`、
      `test_v2_short_rows_calls_do_not_raise`（以上 6 條為 QA 點名），
      `test_exit_alerts_partial_tail_is_verbatim`（本次追加，QA 突變 Q13 的缺口）。
  ⚠️ 兩類的條數是**量測值**（2026-09-28，修前 `d61a1fd` 上實跑本檔）；增刪測試時請重跑、⛔ 不要沿用。

  · H1-f1：`page_hold._totals_facts()`「⚠️ 上面兩個金額只涵蓋一部分」—— 只缺**現價**的列
    （L3 `compute_portfolio_totals()` 三者缺一就不納入）在 📁 組合管理補不了，
    「到 📁 組合管理補齊即可」對它是錯的指引 ⇒ 改用同檔既有的條件子句
    （上提成 `IF_LOTS_AVG_MISSING_WHERE`，另外兩處既有用法逐字不變）。
  · H1-f3：`page_hold._ai_failed_note()` —— 持股清單讀不出來（`error_src == SRC_HOLDINGS`）時，
    ⑦ 的「去哪補」與卡面短句改指 `STATION_ERROR_WHERE`／`_V2_CHECK_NET`（同結論卡、預覽卡）；
    戰情表本身出錯時維持原句。
  · H1-f4：v1 `etf_tab_dividend_station._render_layer1()` 的 partial 註記 —— 同 H1-f1。
  · SA2-f1：`page_today.EXIT_FIX_CODE` 刪掉指向資料體檢的尾句（只刪不改）。
"""
from __future__ import annotations

import ast
import contextlib
import pathlib
import re

import pytest

from shared import ia_nav
from shared.macro_buckets import MISSING_NO_EXTRACTION
from shared.ui_state import UI_EMPTY, UI_FAILED
from src.services.dividend_station_service import compute_portfolio_totals
from src.services.portfolio_deep_service import VarResult
from src.ui.etf import etf_tab_dividend_station as V1
from src.ui.render import station_cards as SC
from src.ui.tabs.tab_today import NO_EXIT_MARKER
from src.ui.views import page_hold as P
from src.ui.views import page_today as T

_E = "RuntimeError('boom')"
#: 被上提成 `IF_LOTS_AVG_MISSING_WHERE` 的那一段（修前在 `page_hold` 裡逐字寫了兩次）。
#: ⚠️ 刻意在測試裡**寫死**：常數被改了一個位元組，下面「逐字不變」那幾條就會紅。
_CLAUSE = "若是缺張數／均價，到既有的 📁 組合管理分頁補齊"
_PARTIAL_KEY = "⚠️ 上面兩個金額只涵蓋一部分"


def _row(code, lots, avg, cur):
    return {"代號": code, "held": True, "張數": lots, "均價": avg, "現價": cur}


_ONLY_PRICE = [_row("0050", 1, 100.0, 110.0), _row("2330", 1, 500.0, None)]
_ONLY_LOTS = [_row("0050", 1, 100.0, 110.0), _row("2330", None, 500.0, 600.0)]
_ONLY_AVG = [_row("0050", 1, 100.0, 110.0), _row("2330", 1, None, 600.0)]


def _partial_fact(rows, totals=None) -> str:
    """`_totals_facts()` 的「⚠️ 上面兩個金額只涵蓋一部分」那一列。預設 totals 走**真的** L3。"""
    _t = compute_portfolio_totals(rows) if totals is None else totals
    st_ = P.StationReadout(requested=True, submitted=True, bound=True,
                           holdings_n=len(rows), rows=tuple(rows), totals=_t)
    return dict(P._totals_facts(st_))[_PARTIAL_KEY]


def _code_str_literals(path: pathlib.Path) -> list[str]:
    """`path` 裡**程式碼**的字串常值（`ast.Constant` 且值為 `str`）。

    · 註解本來就不在 AST 裡 ⇒ 天然排除。
    · 單獨成句的字串（module／class／function docstring，以及其他 `ast.Expr` 字串陳述）也排除 ——
      它們是文件，不會被程式拿去用。
    · 隱式相接的字面（`"a" "b"`）在 AST 裡已併成一個常值；f-string 的字面片段是 `JoinedStr` 底下的
      `ast.Constant`，照樣收進來。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    _docs = {id(_n.value) for _n in ast.walk(tree)
             if isinstance(_n, ast.Expr) and isinstance(_n.value, ast.Constant)
             and isinstance(_n.value.value, str)}
    return [_n.value for _n in ast.walk(tree)
            if isinstance(_n, ast.Constant) and isinstance(_n.value, str) and id(_n) not in _docs]


# ══════════════════════════════════════════════════════════════════
# H1-f1：只缺現價的列 ⛔ 不叫人去 📁 組合管理「補齊即可」
# ══════════════════════════════════════════════════════════════════
class TestH1f1TotalsGuide:
    def test_price_only_row_gets_the_conditional_clause(self):
        # 前提：L3 真的把「只缺現價」算成沒納入（修的就是這一種）。
        _t = compute_portfolio_totals(_ONLY_PRICE)
        assert (_t["held_n"], _t["valued_n"], _t["partial"]) == (2, 1, True)
        v = _partial_fact(_ONLY_PRICE)
        assert "補齊即可" not in v, v
        assert P.IF_LOTS_AVG_MISSING_WHERE in v, v
        # 標點照修前的接法：句號後接子句，子句後直接接「；沒有納入：」（⛔ 不另加標點）。
        assert v.endswith("其餘 1 檔。" + _CLAUSE + "；沒有納入：2330"), v

    @pytest.mark.parametrize("rows", [_ONLY_LOTS, _ONLY_AVG], ids=["lots", "avg"])
    def test_lots_or_avg_missing_row_gets_the_clause(self, rows):
        v = _partial_fact(rows)
        assert _CLAUSE in v and "補齊即可" not in v, v

    def test_without_codes_the_sentence_ends_on_the_clause(self):
        # 列上反推的檔數與 L3 對不上 ⇒ 不列代號（既有行為）；句尾就是子句本身，⛔ 不補句號。
        v = _partial_fact(_ONLY_LOTS, totals={
            "pnl_twd": 1.0, "pnl_pct": 1.0, "value_twd": 10.0,
            "held_n": 3, "valued_n": 1, "partial": True})
        assert "沒有納入：" not in v
        assert v.endswith("其餘 1 檔。" + _CLAUSE), v


class TestH1f1ExistingUsesUnchanged:
    """上提成常數後，另外兩處既有用法渲染出來的字**一個位元組都不變**。"""

    @staticmethod
    def _var_empty():
        deep = P.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                             has_station_rows=True,
                             var=VarResult(computed=False, reason="樣本不足"))
        return P.build_var_card(deep)

    def test_constant_is_the_old_literal_byte_for_byte(self):
        assert P.IF_LOTS_AVG_MISSING_WHERE.encode("utf-8") == _CLAUSE.encode("utf-8")

    def test_var_card_where_is_unchanged(self):
        """修後不變守衛（修前也綠；有效性靠突變驗證）：VaR 灰卡 where 逐字不變。"""
        card = self._var_empty()[0]
        assert card.state == UI_EMPTY and card.note.now == P.VAR_EMPTY_NOW
        assert card.note.where == (
            "若是新上市／剛買進的標的，等歷史累積到至少一個月的共同交易日"
            "再回本頁" + P.press(P.ACTION_RUN_WARROOM_LABEL) + "；" + _CLAUSE)

    def test_var_short_row_is_unchanged(self):
        """修後不變守衛（修前也綠；有效性靠突變驗證）：VaR 灰卡的卡面短句逐字不變。"""
        spec = P.V2_SHORT_ROWS[("hold.deep.var", P.VAR_EMPTY_NOW)]
        assert spec == (
            "有持股，但 VaR 算不出來",
            "這是一個有效的結果" + P.V2_EXCERPT_GAP
            + "本站寧可不給，也不給一個用補值撐出來的尾部估計",
            "若是新上市／剛買進的標的，等歷史累積" + P.V2_EXCERPT_GAP + _CLAUSE)
        short, _full = P.v2_short_rows(self._var_empty()[0])   # 摘錄對不上原文會 KeyError
        assert dict(short)[P.V2_GUIDE_FACT_KEY] == spec[2]

    def test_the_clause_is_written_once_in_page_hold(self):
        """三處共用同一個常數 —— 原文只准在**程式碼**的常數定義那一處出現。

        只數程式碼裡的字串常值（`_code_str_literals()`）：註解引用這句子句、docstring 裡舉例
        ⛔ 不算（2026-09-28 QA 建議：修前的全文字面計數會把註解也數進去 ⇒ 誤報）。
        """
        n = sum(_s.count(_CLAUSE) for _s in _code_str_literals(pathlib.Path(P.__file__)))
        assert n == 1, "條件子句又被逐字抄了一份（應共用 `IF_LOTS_AVG_MISSING_WHERE`）"


# ══════════════════════════════════════════════════════════════════
# H1-f3：持股清單讀不出來 ⇒ ⑦ 的去哪補 ⛔ 不叫人「先讓戰情表跑起來」
# ══════════════════════════════════════════════════════════════════
def _ai_card_on_holdings_error():
    st_ = P.load_station(P.HoldingsReadout(requested=True, submitted=True, error=_E))
    ai = P.load_ai_summary(True, st_, P.SwitchReadout(requested=True, error=st_.error))
    return P.build_ai_summary_card(ai, st_)


def _ai_card_on_station_error():
    st_ = P.StationReadout(requested=True, submitted=True, error=_E)
    ai = P.load_ai_summary(True, st_, P.SwitchReadout(requested=True, error=_E))
    return P.build_ai_summary_card(ai, st_)


def _old_ai_where() -> str:
    return ("AI 總結吃的是戰情表已經算好的結論；**上面那幾張卡這一輪也會是紅的** —— "
            "先讓戰情表跑起來（到" + P.SETUP_WHERE + P.press(P.ACTION_RUN_WARROOM_LABEL)
            + "），這一格才有東西可以摘要")


class TestH1f3AiGuideOnHoldingsError:
    def test_holdings_error_where_is_station_error_where(self):
        card = _ai_card_on_holdings_error()[0]
        assert card.state == UI_FAILED
        assert card.note.now == P.PREVIEW_FAILED_NOW          # 前提（P1a-f1）
        assert card.note.where == P.STATION_ERROR_WHERE
        assert "先讓戰情表跑起來" not in card.note.where

    def test_holdings_error_face_row_is_check_net(self):
        built = _ai_card_on_holdings_error()
        short, full = P.v2_short_rows(built[0])
        assert dict(short)[P.V2_GUIDE_FACT_KEY] == P._V2_CHECK_NET
        assert dict(full)[P.V2_GUIDE_FACT_KEY] == P.v2_plain(P.STATION_ERROR_WHERE)
        assert "先讓戰情表跑起來" not in P.v2_card_html(*built)

    def test_same_guide_as_the_preview_card_for_the_same_error(self):
        _ai = dict(P.v2_short_rows(_ai_card_on_holdings_error()[0])[0])
        _pv_card = P.build_holdings_preview_card(
            P.HoldingsReadout(requested=True, submitted=True, error=_E))[0]
        _pv = dict(P.v2_short_rows(_pv_card)[0])
        assert _ai[P.V2_GUIDE_FACT_KEY] == _pv[P.V2_GUIDE_FACT_KEY]

    def test_station_own_error_keeps_the_original_sentence(self):
        """修後不變守衛（修前也綠；有效性靠突變驗證）：戰情表本身出錯時原句與短句不變。"""
        card = _ai_card_on_station_error()[0]
        assert card.note.now == P.AI_UPSTREAM_NOW
        assert card.note.where == _old_ai_where()
        short, _full = P.v2_short_rows(card)
        assert dict(short)[P.V2_GUIDE_FACT_KEY] == (
            "先讓戰情表跑起來（到" + P.SETUP_WHERE + P.press(P.ACTION_RUN_WARROOM_LABEL) + "）")

    @pytest.mark.parametrize("src", [None, P.SRC_STATION], ids=["none", "station"])
    def test_other_error_src_keeps_the_original_sentence(self, src):
        """修後不變守衛（修前也綠；有效性靠突變驗證）：非持股的 `error_src` 維持原句。"""
        note = P._ai_failed_note(P.AiSummaryReadout(
            requested=True, error=_E, error_kind=P.AI_ERR_UPSTREAM, error_src=src))
        assert note.now == P.AI_UPSTREAM_NOW
        assert note.where == _old_ai_where()

    def test_v2_short_rows_calls_do_not_raise(self):
        """修後不變守衛（修前也綠；有效性靠突變驗證）：兩種上游錯誤的短句查表都不拋錯。"""
        for built in (_ai_card_on_holdings_error(), _ai_card_on_station_error()):
            short, full = P.v2_short_rows(built[0])
            assert len(short) == len(full) == 3
            assert P.v2_card_html(*built)


# ══════════════════════════════════════════════════════════════════
# H1-f4：v1「💼 我的持股戰情室」第 1 層 partial 註記（假 `st` 攔 markdown）
# ══════════════════════════════════════════════════════════════════
class _CapturingST:
    """假的 `st` —— 只收 markdown／info 文字。**不啟動 Streamlit runtime。**"""

    def __init__(self) -> None:
        self.md: list[str] = []

    def markdown(self, body="", **_kw) -> None:
        self.md.append(str(body))

    def info(self, body="", **_kw) -> None:
        self.md.append(str(body))

    def columns(self, spec, **_kw):
        return [contextlib.nullcontext()
                for _ in range(spec if isinstance(spec, int) else len(spec))]


def _v1_note(monkeypatch, rows) -> str:
    fake = _CapturingST()
    monkeypatch.setattr(V1, "st", fake)
    monkeypatch.setattr(SC, "st", fake)            # 卡①由 L4 `render_conclusion_card` 畫
    V1._render_layer1([dict(_r) for _r in rows], 17.0)
    cards = [m for m in fake.md if "這個組合現在該做什麼" in m]
    assert len(cards) == 1, fake.md
    m = re.search(r'<div class="dsl-sub" style="margin-top:8px">(.*?)</div>', cards[0])
    assert m, cards[0]
    return m.group(1)


class TestH1f4V1PartialNote:
    def test_price_only_row(self, monkeypatch):
        note = _v1_note(monkeypatch, _ONLY_PRICE)
        assert note == ("⚠️ 1/2 檔持股缺張數／均價／現價，**沒有**納入損益與市值 —— "
                        "上面兩個金額只涵蓋其餘 1 檔。" + _CLAUSE + "。"), note
        assert "缺張數或均價" not in note and "補齊即可" not in note

    @pytest.mark.parametrize("rows", [_ONLY_LOTS, _ONLY_AVG], ids=["lots", "avg"])
    def test_lots_or_avg_missing_row(self, monkeypatch, rows):
        note = _v1_note(monkeypatch, rows)
        assert "持股缺張數／均價／現價" in note and (_CLAUSE + "。") in note, note
        assert "缺張數或均價" not in note and "補齊即可" not in note

    def test_v1_copy_is_byte_identical_to_page_hold(self):
        """v1 刻意不 import `page_hold`（理由見 v1 該常數的註解）⇒ 兩份字由這一條釘成逐字相同。"""
        assert V1._IF_LOTS_AVG_MISSING_WHERE.encode("utf-8") \
            == P.IF_LOTS_AVG_MISSING_WHERE.encode("utf-8")
        # 「缺張數／均價／現價」逐字取自 `page_hold._totals_facts()` 既有的那一句。
        assert "持股缺張數／均價／現價，**沒有**納入" in _partial_fact(_ONLY_PRICE)


# ══════════════════════════════════════════════════════════════════
# SA2-f1：`EXIT_FIX_CODE` ⛔ 不指向資料體檢（只刪尾句，其餘一字不改）
# ══════════════════════════════════════════════════════════════════
class TestSa2f1ExitFixCode:
    def test_no_data_health_pointer(self):
        assert ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH) not in T.EXIT_FIX_CODE
        assert "資料體檢" not in T.EXIT_FIX_CODE

    def test_marker_kept_and_the_rest_verbatim(self):
        assert NO_EXIT_MARKER in T.EXIT_FIX_CODE
        assert T.EXIT_FIX_CODE == (
            f"{NO_EXIT_MARKER} —— **這一格重抓沒有用**：問題不在「今天有沒有資料」，"
            "而在取值路徑本身（值不在約定的形態裡、或這盞燈根本沒有取值程式）。"
            f"{ia_nav.where_to_press(ia_nav.ACTION_UPDATE_TODAY)}按一百次也一樣。")

    def test_identity_lookup_unaffected(self):
        assert any(_c is T.EXIT_FIX_CODE and _p == "需修程式" for _c, _p in T.V2_EXIT_PHRASES)
        assert T._v2_exit_phrase(T.EXIT_FIX_CODE) == "需修程式"
        tile = T.build_indicator_tile(
            "vix", {"state": "missing", "reason": MISSING_NO_EXTRACTION},
            requested=True, error="")
        assert tile.card.note.where is T.EXIT_FIX_CODE
        html = T.v2_card_html(tile)
        assert "需修程式" in html and "資料體檢" not in html


class TestSa2f1LeavesExitAlertsPartialAlone:
    """批 W 規格：`EXIT_ALERTS_PARTIAL` ⛔ 不動（SA2-f1 只刪 `EXIT_FIX_CODE` 的尾句）。

    QA 突變 Q13：拿掉 `EXIT_ALERTS_PARTIAL` 的尾句，整條 fast lane 沒有任何一條測試轉紅 ⇒ 補這一條。
    ⚠️ 它只釘「本批沒有動到它」：日後有意識地改這一句（另案）時，連同本條一起改。
    """

    def test_exit_alerts_partial_tail_is_verbatim(self):
        """修後不變守衛（修前也綠；有效性靠突變驗證）：尾句（最後一個「。」之後）逐字不變。"""
        assert T.EXIT_ALERTS_PARTIAL.rsplit("。", 1)[-1] == (
            f"要看門檻層到底怎麼了，去 {ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}")
