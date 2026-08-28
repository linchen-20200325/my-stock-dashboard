"""tests/test_macro_v2_card_honesty.py — L4 `macro_v2_cards` 的「卡片別說謊」守衛。

B 段接線後暴露出來的兩個整合缺口,共同點是**畫面上的字與卡片的內容互相矛盾**,
而且兩邊看起來都很正常 —— 正是 §1「錯誤的數字比沒有數字更危險」點名的形狀。

**缺口 1｜右上角說「無資料」,卡片同時畫著 60 根真實 K 棒。**
  `BAND_META` 原本只有四個 band。加權指數是**參考走勢、沒有門檻**,上游只能
  填 `"gray"`(`classify_danger` 對無門檻 spec 會 TypeError,是 L0 刻意的
  fail loud),而 `"gray"` 在 L4 讀成「無資料」。
  → 加第 5 個 band「不判燈」,並由 `band_meta(band, spec)` 依 L0
    `has_thresholds(spec)` 解析。**不列指標名單**(列了就是第二把尺)。

**缺口 2｜兩句固定文案沒有分支。**
  a. K 線卡永遠印「門檻線由 SSOT 畫出」—— 但加權指數一條門檻線都沒有
     (實測 `fig.layout.shapes == 0`)。
  b. 走勢卡遇空序列永遠印「歷史序列取得失敗」—— 但融資餘額卡的實情是
     「取到了,但資料不可用所以不畫」,不是取得失敗。

本檔同時釘住**零行為變更**:有門檻的 spec、以及不傳新參數的既有 caller,
輸出必須與改動前**逐字相同**。

⚠️ 本檔不啟動 Streamlit runtime;`render_*` 以假 st 離線驗。
"""
from __future__ import annotations

import pytest

from shared.macro_buckets import (
    BUCKET_DANGER_SPECS,
    REF_SPECS_BY_KEY,
    REFERENCE_TREND_SPECS,
    SPECS_BY_KEY,
    has_thresholds,
)
from src.ui.render import macro_v2_cards as C

#: 改動前 `BAND_META` 的四個 band —— **逐字**釘住,用來擋「順手改了既有標籤」。
_LEGACY_BAND_META = {
    "green": ("綠", "#0ca30c"),
    "yellow": ("黃", "#fab219"),
    "red": ("紅", "#d03b3b"),
    "gray": ("無資料", "#8a8e96"),
}

#: 全部 18 個 spec(16 盞燈 + 2 條參考走勢)。窮舉本身就是斷言的一部分:
#: 上游多一條 spec,這裡自動跟著掃到,不需要有人記得回來加。
_ALL_SPECS = list(BUCKET_DANGER_SPECS) + list(REFERENCE_TREND_SPECS)


class _NullCtx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeST:
    """只記錄「畫面上出現過哪些字」,不模擬 Streamlit 任何行為。"""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.figs: list = []

    def markdown(self, body, **kw):
        self.calls.append(("markdown", str(body)))

    def caption(self, body, **kw):
        self.calls.append(("caption", str(body)))

    def plotly_chart(self, fig, **kw):
        self.figs.append(fig)
        self.calls.append(("plotly_chart", str(kw.get("key", ""))))

    def container(self, **kw):
        return _NullCtx()

    def columns(self, spec, **kw):
        n = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        return [_NullCtx() for _ in range(n)]

    # ── 查詢介面 ──────────────────────────────────────────────────────
    def screen(self) -> str:
        """畫面上所有文字接成一串 —— 斷言「有沒有出現某句話」用。"""
        return "\n".join(b for _, b in self.calls)

    def captions(self) -> list[str]:
        return [b for k, b in self.calls if k == "caption"]


def _render(monkeypatch, fn, *a, **kw) -> _FakeST:
    fake = _FakeST()
    monkeypatch.setattr(C, "st", fake)
    fn(*a, **kw)
    return fake


def _row(*, key: str = "taiex", label: str = "加權指數", band: str = "gray",
         value: float | None = 24_500.0, unit: str = "點",
         thr_text: str = "—", decimals: int = 0) -> C.Row:
    return C.Row(key=key, label=label, bucket="ref", unit=unit, value=value,
                 band=band, state="live", reason=None, hit_source=None,
                 thr_text=thr_text, source="TEST", note="", decimals=decimals)


def _ohlc(n: int = 5) -> C.OHLC:
    return C.OHLC(
        xs=[f"2026-08-{i + 1:02d}" for i in range(n)],
        open=[100.0 + i for i in range(n)],
        high=[102.0 + i for i in range(n)],
        low=[99.0 + i for i in range(n)],
        close=[101.0 + i for i in range(n)],
    )


_TAIEX = REF_SPECS_BY_KEY["taiex"]      # 唯一無門檻的 spec
_DXY = SPECS_BY_KEY["dxy"]              # 有門檻:黃 105 / 紅 110

#: K 線卡腳註裡「為什麼不畫成交量」那一段的**預期文案,測試端自己持有一份字面**。
#: 來源端改字 → 下面的逐字斷言仍會轉紅（守衛沒有因為抽成變數而變成恆真）。
#:
#: 2026-08-28 更正:原文案為「不畫成交量（該欄目前恆為 0）」,而該句在更正當天
#: **已經是假的** —— `data_cache/twii_ohlcv.parquet` 2026-08-26 真量 4,026,600
#: 回來,33 個交易日的 0 streak 已中斷。
#: ⚠️ **改這兩條斷言不是為了讓 CI 綠,是因為被斷言的那句文案本身是錯的。**
#: 畫面上掛一句假話,正是本檔開宗明義那條 §1「錯誤的數字比沒有數字更危險」。
_CAP_VOL_EXPECTED = "不畫成交量（該欄缺值時為 0，與「真的沒成交」無法區分）"


# ══════════════════════════════════════════════════════════════════════
# 一、缺口 1 —— 參考走勢的右上角不得說「無資料」
# ══════════════════════════════════════════════════════════════════════

class TestReferenceBandDoesNotLie:

    def test_the_premise_still_holds_taiex_really_has_no_thresholds(self):
        """本組測試的前提。哪天 taiex 被設了門檻,先在這裡紅,而不是默默失效。"""
        assert has_thresholds(_TAIEX) is False

    def test_candlestick_card_never_says_no_data_while_drawing_real_bars(self,
                                                                        monkeypatch):
        """缺口 1 的本體:圖畫出來了,右上角就不准說「無資料」。"""
        fake = _render(monkeypatch, C.render_candlestick_card,
                       _row(), _TAIEX, _ohlc())
        assert len(fake.figs) == 1, "前提:這一輪確實畫了 K 線"
        assert "無資料" not in fake.screen()

    def test_and_it_still_shows_the_real_value(self, monkeypatch):
        """反向守衛:不准用「把數字藏起來」來消滅矛盾。"""
        fake = _render(monkeypatch, C.render_candlestick_card,
                       _row(value=24_500.0), _TAIEX, _ohlc())
        assert "24,500" in fake.screen()

    def test_the_label_says_it_is_not_judged_not_that_data_is_missing(self):
        zh, _color = C.band_meta("gray", _TAIEX)
        assert zh == "不判燈"
        assert zh != _LEGACY_BAND_META["gray"][0]

    def test_reference_band_is_registered_in_band_meta(self):
        assert C.BAND_REFERENCE in C.BAND_META
        assert C.BAND_META[C.BAND_REFERENCE][0] != "無資料"

    def test_reference_band_is_neutral_grey(self):
        """配中性灰 —— 不得挑一個新顏色(那是視覺規格,不是 L4 能拍板的)。"""
        assert C.BAND_META[C.BAND_REFERENCE][1] == _LEGACY_BAND_META["gray"][1]

    def test_explicit_reference_band_from_upstream_is_understood(self):
        """上游哪天直接送 `"reference"` 進來(不再借用 gray),這裡也要認得。"""
        assert C.band_meta(C.BAND_REFERENCE, _TAIEX) == C.BAND_META[C.BAND_REFERENCE]
        assert C.band_meta(C.BAND_REFERENCE, _DXY) == C.BAND_META[C.BAND_REFERENCE]


# ══════════════════════════════════════════════════════════════════════
# 二、零行為變更 —— 有門檻的 spec 一個字都不准變
# ══════════════════════════════════════════════════════════════════════

class TestNoBehaviourChangeForRealLights:

    @pytest.mark.parametrize("band", sorted(_LEGACY_BAND_META))
    @pytest.mark.parametrize(
        "spec", [s for s in _ALL_SPECS if has_thresholds(s)],
        ids=[s.key for s in _ALL_SPECS if has_thresholds(s)])
    def test_band_meta_is_a_no_op_for_every_threshold_bearing_spec(self, spec,
                                                                   band):
        """17 個有門檻的 spec × 四個舊 band —— 全部必須與直讀 BAND_META 相同。"""
        assert C.band_meta(band, spec) == _LEGACY_BAND_META[band]

    def test_gray_with_thresholds_still_reads_no_data(self):
        """最容易改壞的一格:有門檻卻沒值,那**就是**「無資料」,不准改寫。"""
        assert C.band_meta("gray", _DXY)[0] == "無資料"

    def test_the_four_legacy_entries_are_untouched(self):
        for band, meta in _LEGACY_BAND_META.items():
            assert C.BAND_META[band] == meta

    def test_no_threshold_spec_with_a_lit_band_is_left_alone(self):
        """無門檻卻判出綠燈 = 上游出事了。改寫成「不判燈」會把 bug 蓋掉。"""
        for band in ("green", "yellow", "red"):
            assert C.band_meta(band, _TAIEX) == _LEGACY_BAND_META[band]

    def test_a_normal_chart_card_still_shows_its_light(self, monkeypatch):
        fake = _render(monkeypatch, C.render_chart_card,
                       _row(key="dxy", label="美元指數", band="yellow",
                            value=106.0, unit="", thr_text="黃 105 / 紅 110",
                            decimals=1),
                       _DXY, ["2026-08-01", "2026-08-02"], [105.0, 106.0])
        assert "黃" in fake.screen()
        assert "不判燈" not in fake.screen()


# ══════════════════════════════════════════════════════════════════════
# 三、多一個 key 之後,既有消費端還活著嗎
# ══════════════════════════════════════════════════════════════════════
#
# `BAND_META` 的消費端分兩類:
#   · L4 本檔 6 處(5 處有 spec → 已改走 `band_meta`;`render_bucket_cards`
#     吃的是桶彙總、拿不到 spec → 維持直讀)。
#   · L5 `tab_macro_v2.py` 2 處(第 3 層表格的「燈」欄、第 1 層**指標危險度** ——
#     2026-08-27 客戶正名前叫「總經位階」,那個名字是錯的:它算的是危險度,
#     不含多空方向;那次同時把 `BAND_META` 直讀搬進 `parallel_verdict()`),
#     兩處都直讀 `BAND_META[...]` —— 只要它們**永遠拿不到** `"reference"`
#     就不會 KeyError。下面把「拿不到」測出來,而不是用讀的。

class TestExistingConsumersSurviveTheNewKey:

    def test_bucket_cards_still_render_with_the_four_old_bands(self, monkeypatch):
        """`render_bucket_cards` 沒有 spec 可問,維持直讀 —— 四個舊 band 都要活。"""
        summary = [{"band": b, "name": f"桶{b}", "worst_label": "x",
                    "worst_value": "1", "n": 3, "n_bad": 0}
                   for b in sorted(_LEGACY_BAND_META)]
        fake = _render(monkeypatch, C.render_bucket_cards, summary)
        assert len(fake.calls) == len(summary)

    def test_l5_light_column_never_receives_the_reference_band(self):
        """第 3 層表格的「燈」欄直讀 BAND_META —— 它的輸入不含參考走勢。"""
        from src.ui.tabs.tab_macro_v2 import _table_columns, build_rows

        rows = build_rows({})
        assert rows, "前提:build_rows 至少產得出 16 盞燈"
        assert all(r.band in _LEGACY_BAND_META for r in rows)
        cols = _table_columns(rows)
        assert set(cols["燈"]) <= {m[0] for m in _LEGACY_BAND_META.values()}

    def test_l5_overall_verdict_never_returns_the_reference_band(self):
        from src.ui.tabs.tab_macro_v2 import bucket_summary, build_rows, overall_verdict

        rows = build_rows({})
        summary = bucket_summary(rows)
        assert all(b["band"] in _LEGACY_BAND_META for b in summary)
        assert overall_verdict(summary)[0] in _LEGACY_BAND_META
        assert overall_verdict([])[0] in _LEGACY_BAND_META

    def test_reference_rows_are_not_part_of_the_16_lights(self):
        """參考走勢與 16 盞燈是兩張物理隔離的表 —— 這是上一條成立的理由。"""
        from src.ui.tabs.tab_macro_v2 import build_rows

        ref_keys = {s.key for s in REFERENCE_TREND_SPECS}
        assert not ({r.key for r in build_rows({})} & ref_keys)


# ══════════════════════════════════════════════════════════════════════
# 四、缺口 2a —— 沒畫門檻線就不准說「門檻線由 SSOT 畫出」
# ══════════════════════════════════════════════════════════════════════

class TestThresholdCaptionTellsTheTruth:

    def test_the_premise_no_threshold_spec_really_draws_zero_lines(self):
        """先把前提測出來:taiex 的圖上**一條門檻線都沒有**。

        這條是整個缺口 2a 的立足點。哪天 spec 被設了門檻、線真的畫出來了,
        這裡會先紅 —— 而不是讓下面那些「不准說有門檻線」的斷言默默變成
        錯的要求。
        """
        fig = C.build_candlestick_figure(_ohlc(), _TAIEX)
        assert fig is not None
        assert len(fig.layout.shapes) == 0

    def test_a_threshold_bearing_spec_really_does_draw_lines(self):
        """對照組:有門檻就真的有線 —— 證明上一條不是「反正都畫不出來」。"""
        fig = C.build_candlestick_figure(_ohlc(), _DXY)
        assert len(fig.layout.shapes) > 0

    def test_candlestick_card_does_not_claim_thresholds_it_never_drew(self,
                                                                      monkeypatch):
        fake = _render(monkeypatch, C.render_candlestick_card,
                       _row(), _TAIEX, _ohlc())
        assert C._CAP_HAS_THR not in fake.screen()
        assert C._CAP_NO_THR in fake.screen()

    def test_candlestick_card_still_claims_them_when_they_exist(self, monkeypatch):
        """零行為變更:有門檻的 spec 照印原句,且腳註其餘部分逐字不變。"""
        fake = _render(monkeypatch, C.render_candlestick_card,
                       _row(band="green"), _DXY, _ohlc(), series_note="註")
        assert fake.captions()[-1] == (
            "門檻線由 SSOT 畫出　·　" + _CAP_VOL_EXPECTED + "　·　註")

    def test_candlestick_caption_without_series_note_is_byte_identical(self,
                                                                       monkeypatch):
        fake = _render(monkeypatch, C.render_candlestick_card,
                       _row(band="green"), _DXY, _ohlc())
        assert fake.captions()[-1] == "門檻線由 SSOT 畫出　·　" + _CAP_VOL_EXPECTED

    def test_chart_card_caption_is_byte_identical_for_a_normal_spec(self,
                                                                    monkeypatch):
        """走勢卡走的是同一句 SSOT 文案 —— 有門檻時腳註必須逐字不變。"""
        fake = _render(monkeypatch, C.render_chart_card,
                       _row(key="dxy", label="美元指數", band="green",
                            value=104.0, unit="", decimals=1),
                       _DXY, ["2026-08-01", "2026-08-02"], [103.0, 104.0],
                       series_note="近 60 個交易日")
        assert fake.captions()[-1] == "門檻線由 SSOT 畫出　·　近 60 個交易日"

    @pytest.mark.parametrize(
        "spec", [s for s in _ALL_SPECS if has_thresholds(s)],
        ids=[s.key for s in _ALL_SPECS if has_thresholds(s)])
    def test_every_threshold_bearing_spec_keeps_the_original_sentence(self, spec):
        assert C.threshold_caption(spec) == "門檻線由 SSOT 畫出"

    def test_the_no_threshold_sentence_does_not_hardcode_any_indicator(self):
        """L4 不准把業務名稱寫進文案 —— 寫了就是名單,上游多一條不會自己長。"""
        for name in ("加權指數", "taiex", "TAIEX", "融資"):
            assert name not in C._CAP_NO_THR

    # ── 2026-08-28 新增:逐字斷言擋不住「文案本身是假的」──────────────────
    #
    # 上面兩條逐字斷言守的是「文案有沒有被順手改掉」,**守不到**「這句話是不是
    # 真的」—— 實證:「該欄目前恆為 0」被逐字釘了一個月,期間 streak 早就中斷,
    # 兩條斷言全綠,而畫面一直在說假話。逐字守衛與誠實守衛是**兩件事**。
    #
    # 這條補的是**可機械檢查的那一小塊**:腳註不得對一個**會變的資料狀態**下
    # 絕對化斷言。
    #
    # ⚠️ **它的漏報面很大,據實寫在這裡,不要高估它(2026-08-28 獨立稽核實測)**:
    # 拿 11 種同義寫法餵這份關鍵字清單,**只抓到 2 種**(「恆為」「永遠」)。
    # 漏掉的包括:`該欄目前都是 0` / `一直是 0` / `始終為 0` / `全部為 0` /
    # `現在是 0` / `已於 2026-08-26 回復正常` / `100% 為 0` / `從未有過非零值`,
    # **以及 `該欄自 2026-07-09 起連續 33 個交易日為 0`** ——
    # 最後那句正是 source 端 docstring 現在用的寫法。
    # 也就是說:它連**自稱要抓的那個形狀**(把當下狀態寫成永久事實)的
    # **鄰近語法變體**都抓不到,遑論「語意上是不是真的」(那需要人讀)。
    # 而且它**只看 render 出來的 caption,對 docstring / 註解零覆蓋** ——
    # 本輪修掉的 6 處過期宣稱裡,有 5 處就在 docstring / 註解,這條一個都擋不到。
    #
    # → 它守得住的只有一件事:**這次真的出過事的那句原文,不會再原樣回來**。
    #   後續建議(本輪不做,避免擴大範圍):改成「數字 + 日期 + 絕對量詞」的型樣
    #   比對,或至少把 `都是 / 一直 / 始終 / 全部 / 現在 / 回復 / 100%` 補進清單。

    #: 對「會變的資料狀態」下絕對化/當下式斷言的字眼。寫進畫面 = 保證會過期。
    _STALENESS_PRONE = ("恆為", "恆等", "永遠", "已恢復", "全為 0", "至今仍")

    def test_candlestick_caption_makes_no_absolute_claim_about_data_state(
            self, monkeypatch):
        """腳註不得宣稱一個會變的資料狀態是永久的（**僅涵蓋少數關鍵字,見上方漏報說明**）。

        §1:錯誤的數字比沒有數字更危險 —— 一句**保證會過期**的斷言,
        過期之後就是畫面上的假話,而且沒有任何東西會通知你它過期了。
        正確寫法是陳述該欄位的**永久性質**(「缺值時為 0，與『真的沒成交』
        無法區分」),那句話無論來源當下有沒有掉量都成立。
        """
        for kw in ({}, {"series_note": "註"}):
            fake = _render(monkeypatch, C.render_candlestick_card,
                           _row(band="green"), _DXY, _ohlc(), **kw)
            cap = fake.captions()[-1]
            for bad in self._STALENESS_PRONE:
                assert bad not in cap, (
                    f"腳註出現會過期的絕對化斷言「{bad}」：{cap}　"
                    f"—— 請改成陳述該欄位的永久性質，不要陳述當下狀態")

    def test_the_guard_above_would_actually_have_caught_the_real_bug(self):
        """證明上一條不是恆真斷言:拿**真的出過事的那句原文**餵它,必須被抓到。

        ⚠️ 本條證明的是「**這一句**會被抓到」,**不是**「這類寫法都會被抓到」——
        實測 11 種同義寫法只命中 2 種(見上方漏報說明)。不要把這條讀成覆蓋率證明。
        """
        historical_false_caption = "門檻線由 SSOT 畫出　·　不畫成交量（該欄目前恆為 0）"
        assert any(bad in historical_false_caption
                   for bad in self._STALENESS_PRONE)
        # 而現行文案必須通過
        assert not any(bad in _CAP_VOL_EXPECTED
                       for bad in self._STALENESS_PRONE)


# ══════════════════════════════════════════════════════════════════════
# 五、缺口 2b —— 空序列不等於「取得失敗」
# ══════════════════════════════════════════════════════════════════════

class TestEmptySeriesNotice:

    _DEFAULT = "歷史序列取得失敗 —— 不以合成資料替代。"

    def test_default_is_unchanged_when_no_notice_is_given(self, monkeypatch):
        """零行為變更:既有 caller 不傳 notice,輸出必須與改動前逐字相同。"""
        fake = _render(monkeypatch, C.render_chart_card,
                       _row(key="margin", label="融資餘額", band="green",
                            value=3200.0, unit="億", thr_text="黃 3400"),
                       SPECS_BY_KEY["margin"], [], [])
        assert fake.captions() == [self._DEFAULT, "門檻帶　黃 3400"]

    def test_a_given_notice_replaces_the_failure_sentence(self, monkeypatch):
        fake = _render(monkeypatch, C.render_chart_card,
                       _row(key="margin", label="融資餘額", band="green",
                            value=3200.0, unit="億", thr_text="黃 3400"),
                       SPECS_BY_KEY["margin"], [], [],
                       notice="取到了，但這段資料有疑義，圖暫不繪製。")
        assert fake.captions() == [
            "取到了，但這段資料有疑義，圖暫不繪製。", "門檻帶　黃 3400"]
        assert self._DEFAULT not in fake.screen()

    def test_the_門檻帶_line_is_still_printed_either_way(self, monkeypatch):
        """notice 只換掉第一句,不准順手吃掉門檻帶那一行。"""
        fake = _render(monkeypatch, C.render_chart_card,
                       _row(thr_text="黃 3400"), SPECS_BY_KEY["margin"], [], [],
                       notice="X")
        assert "門檻帶　黃 3400" in fake.captions()

    def test_notice_is_keyword_only_so_it_cannot_be_passed_by_accident(self):
        """位置參數會讓 `notice` 撞到 `kind` —— 用 keyword-only 在語法層擋掉。"""
        import inspect

        sig = inspect.signature(C.render_chart_card)
        assert sig.parameters["notice"].kind is inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["notice"].default == ""

    def test_l4_hardcodes_no_indicator_name_in_any_caption(self):
        """L4 不得內建「哪個指標配哪句原因」的表 —— 原因一律由 caller 給。

        測法:把函式裡**所有字串字面值**(docstring 除外)抓出來,對照 L0
        全部 18 個 spec 的 key 與中文名,一個都不准出現。用 AST 而不是
        逐字 grep,是因為 `margin=dict(...)` 這種**版面關鍵字**會讓純文字
        比對誤報 —— 誤報的守衛遲早會被人關掉。
        """
        import ast
        import inspect
        import textwrap

        fn = ast.parse(textwrap.dedent(
            inspect.getsource(C.render_chart_card))).body[0]
        # docstring 整段跳過 —— 它拿融資餘額當例子說明這個參數為何存在,
        # 那是**說明**,不是「哪個指標配哪句話」的分支。
        stmts = fn.body[1:] if ast.get_docstring(fn) else fn.body
        literals = [
            n.value for stmt in stmts for n in ast.walk(stmt)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        ]
        blob = "\n".join(literals)
        for spec in _ALL_SPECS:
            assert spec.key not in blob, f"L4 硬編了指標 key {spec.key!r}"
            assert spec.label not in blob, f"L4 硬編了指標名 {spec.label!r}"

    def test_notice_does_not_leak_into_the_normal_path(self, monkeypatch):
        """有序列時 notice 不該出現在畫面上(它只管空序列那一格)。"""
        fake = _render(monkeypatch, C.render_chart_card,
                       _row(key="dxy", label="美元指數", band="green",
                            value=104.0, unit="", decimals=1),
                       _DXY, ["2026-08-01"], [104.0], notice="不該出現")
        assert "不該出現" not in fake.screen()
