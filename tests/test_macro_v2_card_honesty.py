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
#   · L5 `tab_macro_v2.py` 2 處(第 3 層表格的「燈」欄、第 1 層總經位階),
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
