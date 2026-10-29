"""tests/test_uit_target_page_qa.py — UI-T 三組獨立 QA 回修（2026-10-29）的守衛。

M-1 新鮮度／舊 session 殘值、M-2 籌碼失敗格、P1-1 查看此檔判型、P1-2 值得看只列通過、
F1 手機卡片列、F2–F5 文案、F6 薄 L3 strict、F7 本益比失敗市場、以及 parity 補強（degraded／failed／unknown／覆寫卡、
非卡片元素差集）。共用夾具與小工具取自 `tests/test_uit_target_page.py`。
"""
from __future__ import annotations

import datetime as dt
import re

import pytest

from src.ui.views import _target_blocks as B
from src.ui.views import page_find as F
from src.ui.views import page_inspect as I
from tests import uit_fakes as U
from tests.test_uit_target_page import (
    _all_text,
    _cards_html,
    _click,
    _full,
    _matrix_df,
    _new,
    _walk,
)


class _Clock:
    """可注入的台北時鐘（`B.now_taipei`）。"""

    def __init__(self, h=10, m=5):
        self.t = dt.datetime(2026, 10, 29, h, m, tzinfo=B.TAIPEI)

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t = self.t + dt.timedelta(**kw)


def _picked_rows(at):
    return [d.value for d in at.dataframe if "標的" in list(d.value.columns)][0]


# ══════════════════════════════════════════════════════════════════
class TestFreshness:
    """M-1（§2.4）：session 記住的結果不得靜默過期 —— 每區一行灰字講載入時間與怎麼重新載入，超過 TTL 改寫『可能已過期』。"""

    def _loaded(self, monkeypatch):
        at, _calls = _new(monkeypatch)
        clock = _Clock()
        monkeypatch.setattr(B, "now_taipei", clock)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        _click(at, F.ACTION_LOAD_MAP_LABEL)
        at.text_input(key=I.SS_TICKER_WIDGET).set_value("2330")
        _click(at, I.ACTION_LOAD_INSPECT_LABEL)
        at.text_area(key=I.SS_BATCH_WIDGET).set_value("2330")
        _click(at, I.ACTION_RUN_BATCH_LABEL)
        return at, clock

    @staticmethod
    def _lines(at):
        return [t for k, t in _walk(at.main) if k == "Caption" and "此結果載入於" in t]

    def test_each_of_the_four_zones_shows_load_time_and_reload_instruction(self, monkeypatch):
        at, _ = self._loaded(monkeypatch)
        lines = self._lines(at)
        assert len(lines) == 4, lines
        for lab in ("🎯 開始選股", "🗺️ 載入板塊地圖", "🔍 載入完整分析", "🚀 批次分析"):
            assert any(f"再按「{lab}」重新載入" in x for x in lines), lab
        assert all("10:05" in x and "不會自動更新" in x and "可能已過期" not in x for x in lines)

    def test_past_the_ttl_it_says_possibly_expired_and_keeps_the_reload_hint(self, monkeypatch):
        at, clock = self._loaded(monkeypatch)
        clock.advance(seconds=B.FRESH_TTL_SEC["single"] + 60)     # 單檔／批次 1 小時、地圖 30 分已過；選股 1 天未到
        at.run()
        expired = [x for x in self._lines(at) if "可能已過期" in x]
        assert len(expired) == 3, self._lines(at)
        assert all("再按「" in x for x in expired)
        clock.advance(seconds=B.FRESH_TTL_SEC["screen"])
        at.run()
        assert len([x for x in self._lines(at) if "可能已過期" in x]) == 4
        assert any("載入於 10:05" in x for x in self._lines(at)), "載入時間不得被改成現在"

    def test_ttls_come_from_shared_ttls_not_inline_numbers(self):
        from shared import ttls
        assert B.FRESH_TTL_SEC == {"screen": ttls.TTL_1DAY, "map": ttls.TTL_30MIN,
                                   "single": ttls.TTL_1HOUR, "batch": ttls.TTL_1HOUR}

    def test_ttl_table_is_built_from_names_not_literals(self):
        import ast
        from pathlib import Path
        tree = ast.parse((Path(B.__file__)).read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.AnnAssign) and getattr(n.target, "id", "") == "FRESH_TTL_SEC")
        assert node.value.values and all(isinstance(v, ast.Name) for v in node.value.values), "TTL 不得寫 inline 數字（§3.3）"

    def test_freshness_line_is_pure_and_boundary_exact(self):
        t = dt.datetime(2026, 10, 29, 9, 0, tzinfo=B.TAIPEI)
        assert "可能已過期" not in B.freshness_line(t, t + dt.timedelta(seconds=3600), 3600, "X")
        assert "可能已過期" in B.freshness_line(t, t + dt.timedelta(seconds=3601), 3600, "X")

    def test_stale_flow_caption_says_it_was_judged_at_load_time(self, monkeypatch):
        at, _ = _new(monkeypatch, flow=U.make_flow(stale=True))
        at.run()
        _click(at, F.ACTION_LOAD_MAP_LABEL)
        assert any("載入當下判定" in t for k, t in _walk(at.main) if k == "Caption")

    def test_no_freshness_line_before_anything_was_requested(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        assert not self._lines(at)


class TestLegacyResidueDoesNotTrigger:
    """舊 session 殘留 legacy 的已套用值（`?legacy=0` 切回新模式）：新頁只認自己 gate 寫入點的世代，第一輪不得取數。"""

    def test_stale_legacy_applied_values_do_not_fetch_on_the_first_run(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.session_state[F.SS_APPLIED_SCREEN] = {"factors": ["eps_high"], "top_n": 50}
        at.session_state[F.SS_MAP_REQUESTED] = True
        at.session_state[I.SS_APPLIED_TICKER] = {"ticker": "2330", "period_days": 250, "mas": [20],
                                                 "kind_choice": I.KIND_CHOICE_AUTO}
        at.session_state[I.SS_APPLIED_BATCH] = {"raw": "2330 2317", "kind_filter": I.BATCH_FILTER_ALL}
        at.run()
        assert not at.exception, at.exception
        assert sum(calls.values()) == 0, dict(calls)
        assert B.ZONE3_IDLE in _all_text(at) and B.ZONE1_IDLE in _all_text(at)

    def test_own_submit_after_residue_works_normally(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.session_state[I.SS_APPLIED_TICKER] = {"ticker": "2317", "period_days": 250, "mas": [], "kind_choice": "auto"}
        at.run()
        at.text_input(key=I.SS_TICKER_WIDGET).set_value("2330")
        _click(at, I.ACTION_LOAD_INSPECT_LABEL)
        assert calls["stock"] == 1 and "2330" in _all_text(at)


class TestChipsFailureCell:
    """M-2：『⬜ 取數失敗』分支有夾具與斷言（不是 0／中性／空）。"""

    def test_cell_is_the_failure_mark(self):
        s = B.SingleBundle(req=I.InspectRequest(submitted=True, ticker="2330"),
                           verdict=I.KindVerdict(requested=True, code="2330", is_stock=True),
                           chips=U.make_chips(error="RuntimeError('日線抓不到')"))
        c = B.chips_cell("2330", s)
        assert c == "⬜ 取數失敗"
        assert c not in ("0", "0.0", "中性", "") and "中性" not in c

    def test_failed_chips_through_the_page(self, monkeypatch):
        at, _ = _new(monkeypatch, chips_error="RuntimeError('日線抓不到')")
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        at.selectbox(key=B.SS_PICK_WIDGET).set_value("2330").run()
        at.button(key=B.SS_PICK_BUTTON).click().run()
        df = _picked_rows(at)
        assert df.loc[0, "籌碼"] == "⬜ 取數失敗"
        assert df.loc[1, "籌碼"] == B.CHIPS_NOT_FETCHED


class TestPickResetsKindOverride:
    """P1-1：『🔍 查看此檔』的判型一律 auto（進階選項殘留的『強制當 ETF』不得套到候選股）；期間／均線沿用。"""

    def test_override_etf_is_not_applied_to_the_picked_candidate(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.run()
        at.selectbox(key=I.SS_KIND_WIDGET).set_value(I.KIND_CHOICE_ETF)
        at.selectbox(key=I.SS_PERIOD_WIDGET).set_value(500)
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        at.selectbox(key=B.SS_PICK_WIDGET).set_value("2317").run()
        at.button(key=B.SS_PICK_BUTTON).click().run()
        a = at.session_state[I.SS_APPLIED_TICKER]
        assert a["kind_choice"] == I.KIND_CHOICE_AUTO
        assert a["period_days"] == 500, "期間應沿用"
        assert calls["stock"] == 1 and calls["etf"] == 0, "候選個股被當成 ETF 了"

    def test_search_form_still_honours_the_override(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.run()
        at.text_input(key=I.SS_TICKER_WIDGET).set_value("2317")
        at.selectbox(key=I.SS_KIND_WIDGET).set_value(I.KIND_CHOICE_ETF)
        _click(at, I.ACTION_LOAD_INSPECT_LABEL)
        assert at.session_state[I.SS_APPLIED_TICKER]["kind_choice"] == I.KIND_CHOICE_ETF and calls["etf"] == 1


class TestWorthBlockOnlyListsPasses:
    """P1-2：『為什麼值得看』只列通過／達標（門檻＝L0 既有等第下界），低分不得出現。"""

    @staticmethod
    def _go(monkeypatch, score, grade):
        at, _ = _new(monkeypatch, stock_score=score, stock_grade=grade)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        at.text_input(key=I.SS_TICKER_WIDGET).set_value("2330")
        _click(at, I.ACTION_LOAD_INSPECT_LABEL)
        return at

    @staticmethod
    def _worth_block(at):
        out, on = [], False
        for k, t in _walk(at.main):
            if k == "Markdown" and t.strip() == f"**{B.WORTH_BLOCK}**":
                on = True
                continue
            if on:
                if k == "Markdown" and t.startswith("**"):
                    break
                out.append(t)
        return "\n".join(out)

    def test_a_15_point_d_grade_is_not_listed_as_a_reason_to_watch(self, monkeypatch):
        at = self._go(monkeypatch, 15.0, "D")
        w = self._worth_block(at)
        assert "財報體檢綜合分" not in w and "15" not in w and "D 級" not in w
        assert "入選本次選股" in w, "候選列存在＝通過初篩，仍可列"
        assert "15" in _all_text(at), "分數本身仍在健康度卡（只是不在『值得看』區塊）"

    def test_a_passing_score_is_listed(self, monkeypatch):
        at = self._go(monkeypatch, 82.0, "A")
        assert "財報體檢綜合分 82 / 100（A 級）" in self._worth_block(at)

    def test_threshold_is_the_ssot_grade_b_floor(self):
        from shared.health_thresholds import HEALTH_GRADE_B_MIN

        def mk(sc):
            return B.worth_facts(B.SingleBundle(req=None, verdict=None, stock=U.make_stock(score=sc)), None)
        assert mk(HEALTH_GRADE_B_MIN) and not mk(HEALTH_GRADE_B_MIN - 0.1)

    def test_factor_percentile_scores_are_not_listed_here(self, monkeypatch):
        w = self._worth_block(self._go(monkeypatch, 82.0, "A"))
        for c in ("估值分", "EPS分", "88.5"):
            assert c not in w


class TestPeFailedMarkets:
    """F7：某市場本輪整個沒給本益比 ⇒ 缺的代碼寫『⬜ 取不到』而非『未提供』，且不在 rerun 重打。"""

    def test_missing_code_under_a_failed_market_says_cannot_fetch(self, monkeypatch):
        at, _ = _new(monkeypatch, pe_failed_markets=("上櫃 TPEX",))
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        df = _picked_rows(at)
        assert df.loc[1, "估值"] == B.PE_FAILED_CELL
        assert df.loc[0, "估值"] == "22.5", "有值的格子不受影響"

    def test_no_failed_market_keeps_not_provided(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        assert _picked_rows(at).loc[1, "估值"] == B.PE_NOT_PROVIDED_CELL

    def test_second_read_happens_once_per_request(self, monkeypatch):
        at, calls = _new(monkeypatch, pe_failed_markets=("上市 TWSE",))
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        for _ in range(3):
            at.run()
        assert calls["pe"] == 1


class TestIndustryService:
    """F6：薄 L3 用 strict 讀；『對映檔缺／空／壞』與『對映在、查無此股』是兩件事。"""

    @staticmethod
    def _patch(monkeypatch, view=None, exc=None):
        import src.data.sector_flow.reader as R
        seen = {}

        def _fake(*, strict=False):
            seen["strict"] = strict
            if exc:
                raise exc
            return view
        monkeypatch.setattr(R, "read_sector_flow_cache", _fake)
        return seen

    def test_reads_strict_and_returns_mapping(self, monkeypatch):
        from src.services import target_industry_service as S
        seen = self._patch(monkeypatch, {"ok": True, "ticker_sector": {"2330": "半導體業"}})
        m = S.get_ticker_sector_map()
        assert seen["strict"] is True and m.available and m.mapping == {"2330": "半導體業"}

    @pytest.mark.parametrize("view", [{"ok": False, "reason": "尚未產生"}, {"ok": True, "ticker_sector": {}},
                                      {"ok": True, "ticker_sector": None}, {"ok": True}])
    def test_missing_or_empty_mapping_is_unavailable(self, monkeypatch, view):
        from src.services import target_industry_service as S
        self._patch(monkeypatch, view)
        m = S.get_ticker_sector_map()
        assert not m.available and m.mapping == {} and m.reason

    def test_corrupt_cache_raises_instead_of_being_swallowed(self, monkeypatch):
        from src.services import target_industry_service as S
        self._patch(monkeypatch, exc=ValueError("bubble 壞檔"))
        with pytest.raises(ValueError):
            S.get_ticker_sector_map()

    def test_page_shows_whole_column_blank_when_mapping_missing_and_unclassified_when_unknown(self, monkeypatch):
        from src.services.target_industry_service import TickerSectorMap
        at, _ = _new(monkeypatch)
        monkeypatch.setattr("src.services.target_industry_service.get_ticker_sector_map",
                            lambda: TickerSectorMap(available=False, reason="缺"))
        at.run()
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
        assert set(_picked_rows(at)["產業"]) == {B.SECTOR_UNAVAILABLE_CELL}
        at2, _ = _new(monkeypatch)       # 夾具預設：對映在、2891 查無 → 『⬜ 未分類』
        at2.run()
        _click(at2, F.ACTION_RUN_SCREEN_LABEL)
        assert _picked_rows(at2).loc[2, "產業"] == "⬜ 未分類"


class TestMobileMatrixCards:
    """F1：同一份 HTML，窄螢幕以 CSS 變成每產業一張卡片列。"""

    def test_one_dom_with_labelled_cells_and_a_narrow_screen_card_rule(self):
        h = B.matrix_html(B.build_industry_matrix(U.SECTORS))
        assert h.count("<table") == 1 and "\n\n" not in h
        for c in B.MATRIX_COLS:
            assert f'data-label="{c}"' in h
        assert "@media (max-width:768px)" in B.MATRIX_CSS and "attr(data-label)" in B.MATRIX_CSS
        assert "display:none" in B.MATRIX_CSS

    def test_cells_are_html_escaped(self):
        r = B.MatrixRow(sector="<script>x</script>", fundamentals="a", strength="b", flow="c&d", valuation="e", trust="f")
        h = B.matrix_html([r])
        assert "<script>x" not in h and "&lt;script&gt;" in h and "c&amp;d" in h

    def test_matrix_still_carries_every_column_value(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        _click(at, F.ACTION_LOAD_MAP_LABEL)
        m = _matrix_df(at)
        assert list(m.columns) == list(B.MATRIX_COLS) and len(m) == 4


class TestWordingFixes:
    SENT = "僅顯示：勾選只會回顯在判型結果；K 線與均線圖新版尚未接上，不影響任何結論。"

    def test_ma_note_and_help_use_the_agreed_sentence(self, monkeypatch):
        assert B.MA_ONLY_DISPLAY_NOTE == self.SENT and B.MA_GROUP_LABEL == "**均線（僅顯示）**"
        at, _ = _new(monkeypatch)
        at.run()
        assert self.SENT in _all_text(at)
        ma = [c for c in at.checkbox if str(c.key).startswith(I.SS_MA_WIDGET_PREFIX)]
        assert ma and all(getattr(c.proto, "help", "") == self.SENT for c in ma)

    def test_ma_claim_is_true_the_kind_card_echoes_the_choice(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        at.text_input(key=I.SS_TICKER_WIDGET).set_value("2330")
        _click(at, I.ACTION_LOAD_INSPECT_LABEL)
        assert "MA20" in _all_text(at), "『只會回顯在判型結果』必須是真的"

    def test_no_not_wired_wording_and_advanced_title_is_plain(self, monkeypatch):
        at, _ = _new(monkeypatch)
        _full(at)
        t = _all_text(at)
        assert "尚未接線" not in t and B.RISK_PLACEHOLDER == "⬜ 個股風險指標尚未提供"
        assert B.ADVANCED_EXPANDER == "進階分析" and any(e.label == "進階分析" for e in at.expander)
        for w in ("功能保留", "只降階"):
            assert w not in t

    def test_health_block_title_matches_its_content(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        at.text_input(key=I.SS_TICKER_WIDGET).set_value("2330")
        _click(at, I.ACTION_LOAD_INSPECT_LABEL)
        seq = [t for k, t in _walk(at.main) if k == "Markdown"]
        i = seq.index(f"**{B.TREND_BLOCK}**")
        assert "健康度" in seq[i + 1] and B.TREND_BLOCK == "財報體檢（健康度）"

    def test_first_zone_is_lean_and_the_long_note_moved_into_basis(self, monkeypatch):
        at, _ = _new(monkeypatch)
        at.run()
        caps = [t for k, t in _walk(at.main) if k == "Caption"]
        assert B.ZONE1_SAY in caps and B.ZONE1_SORT_NOTE in caps and B.ZONE1_NO_TREND_NOTE not in caps
        md = "\n".join(t for k, t in _walk(at.main) if k == "Markdown")
        assert B.ZONE1_NO_TREND_NOTE in md, "說明不得消失：收進第一區『查看依據』"


# ══════════════════════════════════════════════════════════════════
# parity 補強（QA-B 盲點）
# ══════════════════════════════════════════════════════════════════
def _legacy_find():
    from src.ui.views.page_find import render_page_find
    render_page_find()


def _legacy_inspect():
    from src.ui.views.page_inspect import render_page_inspect
    render_page_inspect()


def _pair(monkeypatch, legacy_fn, act, **kw):
    from streamlit.testing.v1 import AppTest
    U.install(monkeypatch, U.Calls(), **kw)
    old = AppTest.from_function(legacy_fn, default_timeout=120).run()
    new = AppTest.from_function(U.page_app, default_timeout=120).run()
    act(old)
    act(new)
    assert not old.exception and not new.exception
    return _cards_html(old), _cards_html(new)


def _single(ticker, kind=None):
    def _act(at):
        at.text_input(key=I.SS_TICKER_WIDGET).set_value(ticker)
        if kind:
            at.selectbox(key=I.SS_KIND_WIDGET).set_value(kind)
        _click(at, I.ACTION_LOAD_INSPECT_LABEL)
    return _act


class TestParityEdgeStates:
    def test_failed_screen_card(self, monkeypatch):
        o, n = _pair(monkeypatch, _legacy_find, lambda at: _click(at, F.ACTION_RUN_SCREEN_LABEL),
                     screen_error="RuntimeError('額度用罄')")
        assert o["選股結果"] == n["選股結果"] and "額度用罄" in n["選股結果"]

    def test_degraded_stale_bubble_card_and_failed_heatmap_card(self, monkeypatch):
        o, n = _pair(monkeypatch, _legacy_find, lambda at: _click(at, F.ACTION_LOAD_MAP_LABEL),
                     flow=U.make_flow(stale=True), heatmap=U.make_heatmap(failed=True))
        assert o["三大法人資金流向泡泡圖"] == n["三大法人資金流向泡泡圖"]
        # 熱力圖卡唯一的差別＝把指向舊分頁的『切換市場或區間』句換成白話（其餘逐字相同）
        # （v2 卡面對長句會另產生短句摘錄，所以比對時把兩邊的那一列整列拿掉；該列內容由下方 plain 常數另行斷言）
        _strip = lambda h: re.sub(r'<div class="blk-fact"><span class="blk-fact-k">切換市場或區間</span>'      # noqa: E731
                                  r'<span class="blk-fact-v"[^>]*>.*?</span></div>', "", h)
        assert _strip(o["產業漲跌熱力圖"]) == _strip(n["產業漲跌熱力圖"])
        assert B.HEATMAP_SWITCH_PLAIN in n["產業漲跌熱力圖"] and "🌍 市場環境" not in n["產業漲跌熱力圖"]

    def test_unknown_cards(self, monkeypatch):
        o, n = _pair(monkeypatch, _legacy_inspect, _single("AAPL"))
        for t in ("判型結果", "判不出型別 —— 已停在這裡"):
            assert o[t] == n[t], t

    def test_override_kind_card(self, monkeypatch):
        o, n = _pair(monkeypatch, _legacy_inspect, _single("AAPL", I.KIND_CHOICE_STOCK))
        assert o["判型結果"] == n["判型結果"] and "手動指定" in n["判型結果"]

    def test_failed_leg_and_gap_cards(self, monkeypatch):
        from streamlit.testing.v1 import AppTest
        U.install(monkeypatch, U.Calls(), chips_error="RuntimeError('日線抓不到')", stock_score=None)
        old = AppTest.from_function(_legacy_inspect, default_timeout=120).run()
        new = AppTest.from_function(U.page_app, default_timeout=120).run()
        _single("2330")(old)
        _single("2330")(new)
        o, n = _cards_html(old), _cards_html(new)
        assert o["健康度"] == n["健康度"] and o["判型結果"] == n["判型結果"]
        # 失敗的籌碼卡是精簡卡面（沒有 `blk-title`）→ 改取『含籌碼＋取得失敗』的整張卡 HTML 比對
        def pick(at):
            return [t for k, t in _walk(at.main) if k == "Markdown" and t.startswith("<div")
                    and "籌碼" in t and "取得失敗" in t]
        assert pick(old) and pick(old) == pick(new)


class TestNonCardElementDiff:
    """卡片以外的元素（標題、說明 caption）：新舊差集必須全部可解釋。"""

    #: 舊頁獨有、新頁刻意不要的（工程字樣、葉標題、舊頁自己的敘述）。
    OLD_ONLY_OK = ("**取數接線揭露**", "K 線一律用**還原價**", "一個代碼進去", "健康度／估值／籌碼 —— 三格各自判態",
                   "客戶已核准**允許混貼**", "系統判成什麼、這一輪實際用什麼", "線框", "預設勾 MA", "## 🔬 查一檔",
                   "#### 判型結果", "#### 葉", "**① 代碼**", "**② 期間", "**③ 均線**")

    def test_old_only_elements_are_all_engineering_or_legacy_headings(self, monkeypatch):
        from streamlit.testing.v1 import AppTest
        U.install(monkeypatch, U.Calls())
        old = AppTest.from_function(_legacy_inspect, default_timeout=120).run()
        new = AppTest.from_function(U.page_app, default_timeout=120).run()
        for at in (old, new):
            _single("2330")(at)
        o = {t for k, t in _walk(old.main) if k in ("Caption", "Markdown") and not t.startswith("<")}
        n = {t for k, t in _walk(new.main) if k in ("Caption", "Markdown") and not t.startswith("<")}
        bad = [t for t in sorted(o - n) if not any(t.startswith(p) or p in t for p in self.OLD_ONLY_OK)]
        assert not bad, f"舊頁有、新頁卻沒了（無法解釋的消失）：{bad}"

    def test_new_only_elements_all_come_from_this_pages_constants(self, monkeypatch):
        from streamlit.testing.v1 import AppTest
        U.install(monkeypatch, U.Calls())
        new = AppTest.from_function(U.page_app, default_timeout=120).run()
        _click(new, F.ACTION_RUN_SCREEN_LABEL)
        _single("2330")(new)
        consts = set()
        for v in vars(B).values():
            if isinstance(v, str):
                consts.add(v.strip("*"))
            elif isinstance(v, tuple):
                for x in v:
                    if isinstance(x, str):
                        consts.add(x.strip("*"))
                    elif isinstance(x, tuple):
                        consts.update(str(y).strip("*") for y in x)
        old = {t for k, t in _walk(AppTest.from_function(_legacy_find, default_timeout=120).run().main)
               if k in ("Caption", "Markdown")}
        unexplained = []
        for k, t in _walk(new.main):
            if k not in ("Caption", "Markdown") or t.startswith("<") or t in old:
                continue
            s = t.strip("*")
            if (s in consts or any(s in c or c in s for c in consts if len(c) >= 4)
                    or re.match(r"^(此結果載入於|本次因子：|現有文字判讀|\*\*\d{4,5}\b|\*\*\d{2}\.\d)|^- ", t)):
                continue
            unexplained.append(t)
        assert not unexplained, unexplained
