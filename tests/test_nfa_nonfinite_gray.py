"""tests/test_nfa_nonfinite_gray.py — 批 NF-a：非有限值（NaN / ±inf）一律灰燈。

DL-f1-s45（違 CLAUDE.md §1）：五桶 bar 遇到 M1B-M2 gap = +inf 會亮**綠燈**。
  L2 `compute_five_bucket_summary._first_sane` 以 L0 `within_valid_range` 過濾，
  但 `m1b_m2_gap` 沒設 `valid_min` / `valid_max` ⇒ `within_valid_range(+inf)` 回 True，
  `classify_danger(+inf)` 再落到 green（−inf 落到 red）。v2 今天頁 m1b 燈同病
  （側車 state=ok、燈號頻道「綠」）。

修法只在 L0 `shared/macro_buckets.py`：非有限值與 None 同等對待 ——
  · `within_valid_range` 回 False（不論 spec 有無範圍）
  · `classify_danger` 回 'gray'
⛔ 沒有替 `m1b_m2_gap` 發明 `valid_min` / `valid_max`（那是門檻規格，憑空訂就是捏造）。

本檔守四件事：
  1. L0 兩個函式 × 三種 direction × (+inf / −inf / NaN / None / 有限值含邊界 0 與門檻)
  2. 有限值 0 差異（門檻邊界逐點表 + 全部 spec 的「有限值永不變灰」性質）
  3. v1 五桶（L2 → L5 `render_five_bucket_bar`）與 v2 今天頁（L5 `page_today`）實跑 gap=+inf → 不綠
  4. 其他直接呼叫 `classify_danger` 的消費端（推播 VIX / 參考走勢 usdtwd / v2 總經分頁）

突變（實作組自跑）：拿掉非有限判斷 / 只擋 +inf / 只擋 NaN / 只改其中一個函式 → 本檔轉紅。
"""
from __future__ import annotations

import dataclasses
import math
import sys
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from shared import macro_buckets as mb
from shared.macro_buckets import (
    BUCKET_LEVEL_LABEL,
    LEVEL_COLOR,
    LEVEL_EMOJI,
    MISSING_NO_VALUE,
    MISSING_NOT_LOADED,
    MISSING_OUT_OF_RANGE,
    SPECS_BY_KEY,
    classify_danger,
    within_valid_range,
)
from src.compute.macro.macro_helpers import compute_five_bucket_summary

_KEY = "m1b_m2_gap"
INF, NINF, NAN = math.inf, -math.inf, math.nan

#: (值, id)。同一個非有限值的各種型別 —— `float()` 之後才是 inf / nan。
NON_FINITE: list[tuple[object, str]] = [
    (INF, "float+inf"), (NINF, "float-inf"), (NAN, "float-nan"),
    (np.float64("inf"), "np+inf"), (np.float64("-inf"), "np-inf"),
    (np.float64("nan"), "np-nan"),
    ("inf", "str+inf"), ("-inf", "str-inf"), ("nan", "str-nan"),
    (Decimal("Infinity"), "dec+inf"), (Decimal("-Infinity"), "dec-inf"),
    (Decimal("NaN"), "dec-nan"),
]
_NF_VALUES = [v for v, _ in NON_FINITE]
_NF_IDS = [i for _, i in NON_FINITE]

#: 16 盞燈 + 有門檻的參考走勢（usdtwd）—— classify_danger 可用的全部 spec。
_THR_SPECS = list(mb.BUCKET_DANGER_SPECS) + [
    s for s in mb.REFERENCE_TREND_SPECS if mb.has_thresholds(s)]
#: within_valid_range 不看門檻 → 連無門檻的 taiex 也納入。
_ALL_SPECS = list(mb.BUCKET_DANGER_SPECS) + list(mb.REFERENCE_TREND_SPECS)


def _unranged(key: str) -> mb.DangerSpec:
    """拿掉 valid_* 的副本 —— 證明非有限值的擋法**不依賴**範圍設定。"""
    return dataclasses.replace(SPECS_BY_KEY[key], valid_min=None, valid_max=None)


def test_param_sets_cover_all_three_directions():
    """前提守衛：參數化的 spec 集合真的涵蓋三種 direction，否則下面的全覆蓋是空話。"""
    assert {s.direction for s in _THR_SPECS} >= {"high_bad", "low_bad", "band"}
    # 修的那條病的前提：m1b_m2_gap 本身沒有範圍（修法**不是**替它加範圍）
    _m1b = SPECS_BY_KEY[_KEY]
    assert _m1b.direction == "low_bad"
    assert _m1b.valid_min is None and _m1b.valid_max is None


# ════════════════════════════════════════════════════════════════
# 1. L0 within_valid_range
# ════════════════════════════════════════════════════════════════
class TestWithinValidRange:

    @pytest.mark.parametrize("spec", _ALL_SPECS, ids=lambda s: s.key)
    @pytest.mark.parametrize("value", _NF_VALUES, ids=_NF_IDS)
    def test_non_finite_never_in_range(self, spec, value):
        assert within_valid_range(value, spec) is False

    @pytest.mark.parametrize("key", ["vix", _KEY, "ndc_signal", "us10y", "dxy", "foreign_net"])
    @pytest.mark.parametrize("value", [INF, NINF, NAN], ids=["+inf", "-inf", "nan"])
    def test_non_finite_rejected_even_without_range(self, key, value):
        """high_bad（vix / us10y / dxy）、low_bad（m1b / foreign_net）、band（ndc）
        各自拿掉範圍後仍擋 —— 擋法是「不是觀測值」，不是「超出範圍」。"""
        assert within_valid_range(value, _unranged(key)) is False

    def test_bug_case_plus_inf_gap(self):
        """DL-f1-s45 本案：修前回 True（m1b 無範圍 → 放行 +inf）。"""
        assert within_valid_range(INF, SPECS_BY_KEY[_KEY]) is False
        assert within_valid_range(NINF, SPECS_BY_KEY[_KEY]) is False

    def test_none_and_unparseable_unchanged(self):
        _s = SPECS_BY_KEY[_KEY]
        assert within_valid_range(None, _s) is False
        assert within_valid_range("n/a", _s) is False
        assert within_valid_range(object(), _s) is False

    @pytest.mark.parametrize("value", [
        0.0, -0.0, 1.0, -1.0, 1.0 + 1e-12, 5e-324, -5e-324, 1e300, -1e300,
        sys.float_info.max, -sys.float_info.max, 3, np.float64(0.5), "2.5", Decimal("-0.25"),
    ])
    def test_finite_on_unranged_spec_always_in_range(self, value):
        """有限值 0 差異：未設範圍 = 不檢查數值範圍（含極大 / 極小 / 各型別）。"""
        assert within_valid_range(value, SPECS_BY_KEY[_KEY]) is True

    @pytest.mark.parametrize("key,value,expected", [
        ("us10y", 0.0, True), ("us10y", 20.0, True), ("us10y", 4.63, True),
        ("us10y", -1e-9, False), ("us10y", 20.000001, False), ("us10y", 46.3, False),
        ("dxy", 70.0, True), ("dxy", 130.0, True), ("dxy", 69.99, False), ("dxy", 27.0, False),
        ("foreign_net", -9999.0, True), ("foreign_net", 9999.0, True), ("foreign_net", 0.0, True),
        ("foreign_net", -9999.01, False), ("foreign_net", -2.5e10, False),
    ])
    def test_finite_ranged_boundaries_unchanged(self, key, value, expected):
        """有限值 0 差異：有範圍的三條（us10y / dxy / foreign_net），邊界含端點。"""
        assert within_valid_range(value, SPECS_BY_KEY[key]) is expected


# ════════════════════════════════════════════════════════════════
# 2. L0 classify_danger
# ════════════════════════════════════════════════════════════════
class TestClassifyDanger:

    @pytest.mark.parametrize("spec", _THR_SPECS, ids=lambda s: s.key)
    @pytest.mark.parametrize("value", _NF_VALUES, ids=_NF_IDS)
    def test_non_finite_is_gray(self, spec, value):
        assert classify_danger(value, spec) == "gray"

    @pytest.mark.parametrize("key", ["vix", _KEY, "ndc_signal"],
                             ids=["high_bad", "low_bad", "band"])
    @pytest.mark.parametrize("value", [INF, NINF, NAN], ids=["+inf", "-inf", "nan"])
    def test_each_direction_non_finite_gray(self, key, value):
        """修前：+inf → high_bad 紅 / low_bad 綠 / band 紅；−inf → 綠 / 紅 / 紅；
        NaN → 三種 direction 全綠（NaN 的比較皆 False → 落到最後的 return）。"""
        assert classify_danger(value, SPECS_BY_KEY[key]) == "gray"
        assert classify_danger(value, _unranged(key)) == "gray"

    def test_bug_case_m1b_plus_inf_not_green(self):
        _s = SPECS_BY_KEY[_KEY]
        assert classify_danger(INF, _s) == "gray"     # 修前 green（偽綠）
        assert classify_danger(NINF, _s) == "gray"    # 修前 red（偽紅）

    def test_none_and_unparseable_still_gray(self):
        _vix = SPECS_BY_KEY["vix"]
        assert classify_danger(None, _vix) == "gray"
        assert classify_danger("n/a", _vix) == "gray"

    @pytest.mark.parametrize("value,expected", [
        (0.0, "green"), (21.99, "green"), (22.0, "yellow"), (29.99, "yellow"),
        (30.0, "red"), (1e300, "red"), (-1e300, "green"), (np.float64(25.0), "yellow"),
    ])
    def test_finite_high_bad_boundaries_unchanged(self, value, expected):
        assert classify_danger(value, SPECS_BY_KEY["vix"]) == expected          # 22 / 30

    @pytest.mark.parametrize("value,expected", [
        (2.0, "green"), (1.0001, "green"), (1.0, "yellow"), (0.5, "yellow"),
        (0.0, "red"), (-0.0, "red"), (-0.5, "red"), (1e300, "green"), (-1e300, "red"),
    ])
    def test_finite_low_bad_boundaries_unchanged(self, value, expected):
        assert classify_danger(value, SPECS_BY_KEY[_KEY]) == expected           # 1.0 / 0.0

    # 批 Z4 R9（客戶 2026-10-02 定性「NDC 23 分程式判黃」為程式 bug）—— 有意識的變更：
    #   低側黃線 23→22，原本的 (23.0, "yellow") 改為 (22.0, "yellow") ＋ (23.0, "green")。
    #   本類「有限值判定不受 NF-a 非有限值修法影響」的本意不變（其餘列一字未動）。
    @pytest.mark.parametrize("value,expected", [
        (0.0, "red"), (16.0, "red"), (16.5, "yellow"), (22.0, "yellow"), (23.0, "green"),
        (23.5, "green"),
        (28.0, "green"), (31.9, "green"), (32.0, "yellow"), (37.9, "yellow"),
        (38.0, "red"), (1e300, "red"), (-1e300, "red"),
    ])
    def test_finite_band_boundaries_unchanged(self, value, expected):
        assert classify_danger(value, SPECS_BY_KEY["ndc_signal"]) == expected   # 16/22/32/38

    @pytest.mark.parametrize("spec", _THR_SPECS, ids=lambda s: s.key)
    def test_finite_never_gray(self, spec):
        """有限值 0 差異的性質版：任何 spec、任何有限值都**不會**因本次改動變灰。"""
        _lines = [x for x in (spec.yellow, spec.red, spec.yellow_lo, spec.red_lo)
                  if x is not None]
        _grid = {0.0, -0.0, 1e300, -1e300, sys.float_info.max, -sys.float_info.max}
        for _x in _lines:
            _grid |= {_x, _x - 1e-9, _x + 1e-9, math.nextafter(_x, INF),
                      math.nextafter(_x, NINF)}
        for _v in sorted(_grid):
            assert classify_danger(_v, spec) in ("green", "yellow", "red"), (spec.key, _v)

    def test_no_threshold_spec_contract(self):
        """無門檻 spec（taiex）：有限值仍 TypeError（刻意的 fail loud 不變）；
        None 與非有限值在比大小**之前**就回 gray（None 本來就如此）。"""
        _t = mb.REF_SPECS_BY_KEY["taiex"]
        with pytest.raises(TypeError):
            classify_danger(23000.0, _t)
        assert classify_danger(None, _t) == "gray"
        for _v in (INF, NINF, NAN):
            assert classify_danger(_v, _t) == "gray"


# ════════════════════════════════════════════════════════════════
# 3a. v1 五桶：L2 compute_five_bucket_summary → L5 render_five_bucket_bar
# ════════════════════════════════════════════════════════════════
def _v1(gap, **kw):
    rd: dict = {}
    info = {"m1b_yoy": 3.0, "m2_yoy": 1.0, "gap": gap, "source": "CBC-tier1"}
    out = compute_five_bucket_summary(m1b_m2_info=info, readiness_out=rd, **kw)
    det = next(d for d in out["long"]["details"] if d["key"] == _KEY)
    return out, rd, det


class _FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _FakeSt:
    """只攔 `render_five_bucket_bar` 用到的三個 API，把 HTML 原樣收下來。"""

    def __init__(self):
        self.md: list[str] = []

    def columns(self, n):
        return [_FakeCtx() for _ in range(n)]

    def markdown(self, body, **_kw):
        self.md.append(body)

    def expander(self, *_a, **_kw):
        return _FakeCtx()


class TestV1FiveBucket:

    def test_plus_inf_gap_is_gray_not_green(self):
        out, rd, det = _v1(INF)
        assert det["danger"] == "gray"                 # 修前 green
        assert det["value_str"] == "—"                 # 修前 'inf%'
        assert out["long"]["level"] == "gray"          # 修前 green「結構健康」
        assert out["long"]["label"] == BUCKET_LEVEL_LABEL["long"]["gray"]
        assert out["long"]["emoji"] == LEVEL_EMOJI["gray"]
        assert rd[_KEY]["state"] == "missing" and rd[_KEY]["value"] is None

    def test_minus_inf_gap_is_gray_not_red(self):
        out, rd, det = _v1(NINF)
        assert det["danger"] == "gray"                 # 修前 red
        assert out["long"]["level"] == "gray"          # 修前 red「結構防禦」
        assert rd[_KEY]["state"] == "missing" and rd[_KEY]["value"] is None

    @pytest.mark.parametrize("value", [INF, NINF], ids=["+inf", "-inf"])
    def test_sidecar_same_as_nan_precedent(self, value):
        """灰燈沿用既有缺值呈現：±inf 的側車與 NaN（既有前例）逐鍵相同，
        只差 `rejected` 裡記下的原始值。"""
        _, rd_x, _ = _v1(value)
        _, rd_n, _ = _v1(NAN)
        assert rd_x[_KEY]["reason"] == rd_n[_KEY]["reason"] == MISSING_OUT_OF_RANGE
        _strip = lambda r: {k: v for k, v in r.items() if k != "rejected"}  # noqa: E731
        assert _strip(rd_x[_KEY]) == _strip(rd_n[_KEY])
        assert rd_x[_KEY]["rejected"][0][1] == value

    def test_inf_is_not_counted_as_green(self):
        """其他燈照常：ndc 綠時長期桶綠，但綠燈數只算 ndc 一盞（修前會算成 2 盞）。"""
        out, _, det = _v1(INF, macro_info={"ndc_signal": {"score": 28}})
        assert det["danger"] == "gray"
        assert out["long"]["level"] == "green"
        assert sum(d["danger"] == "green" for d in out["long"]["details"]) == 1

    @pytest.mark.parametrize("score,level", [(34, "yellow"), (40, "red")])
    def test_inf_does_not_mask_other_lamps(self, score, level):
        out, _, det = _v1(INF, macro_info={"ndc_signal": {"score": score}})
        assert det["danger"] == "gray"
        assert out["long"]["level"] == level

    @pytest.mark.parametrize("gap,danger", [
        (2.0, "green"), (1.0, "yellow"), (0.5, "yellow"), (0.0, "red"), (-0.5, "red")])
    def test_finite_gap_unchanged(self, gap, danger):
        out, rd, det = _v1(gap)
        assert det["danger"] == danger == out["long"]["level"]
        assert rd[_KEY]["state"] == "ok" and rd[_KEY]["value"] == gap

    @staticmethod
    def _all_lamps(value, *, li_latest=None):
        rd: dict = {}
        out = compute_five_bucket_summary(
            macro_info={"ndc_signal": {"score": value}, "ism_pmi": {"value": value},
                        "us_core_cpi": {"yoy": value}, "tw_export": {"yoy": value},
                        "vix": {"current": value}, "us10y": {"current": value}},
            m1b_m2_info={"gap": value}, bias_info={"bias_240": value},
            warroom_summary={"health_score": value},
            cl_data={"intl": {"美元指數 DXY": pd.DataFrame({"close": [value]}),
                              "10Y公債殖利率": pd.DataFrame({"close": [value]})},
                     "adl": pd.DataFrame({"ad_ratio": [value]}),
                     "margin": value,
                     "inst": {"外資及陸資": {"net": value}}},
            li_latest=li_latest,
            jingqi_info={"avg": value}, news_items=[],
            readiness_out=rd)
        lights = {d["key"]: d["danger"] for b in out.values() for d in b["details"]}
        return out, lights, rd

    @pytest.mark.parametrize("value", [INF, NINF, NAN], ids=["+inf", "-inf", "nan"])
    def test_every_numeric_lamp_non_finite_is_gray(self, value):
        """16 盞扣掉 news_systemic（則數，不可能非有限）與 fut_net（見下一條）＝ 14 盞，
        全部餵同一個非有限值 → 14 盞全灰，且缺值原因是「值被擋下」（out_of_range）
        而不是「沒給值」。修前除 us10y / dxy / foreign_net（有範圍）外，
        其餘 11 盞會被 ±inf 判成綠 / 紅。"""
        out, lights, rd = self._all_lamps(value)
        numeric = {k: v for k, v in lights.items() if k not in ("news_systemic", "fut_net")}
        assert len(numeric) == 14
        assert set(numeric.values()) == {"gray"}, numeric
        for k in numeric:
            assert rd[k]["state"] == "missing" and rd[k]["value"] is None, k
            assert rd[k]["reason"] == MISSING_OUT_OF_RANGE, (k, rd[k]["reason"])
        for b in ("long", "mid", "chips"):              # 三桶的燈全在上面 14 盞裡
            assert out[b]["level"] == "gray", (b, out[b]["level"])

    @pytest.mark.parametrize("value", [INF, NINF, NAN], ids=["+inf", "-inf", "nan"])
    def test_fut_net_non_finite_is_gray(self, value):
        _, lights, rd = self._all_lamps(value, li_latest=pd.DataFrame({"外資大小": [value]}))
        """NF-f1（2026-10-01 修）：原為 strict xfail（L2 `_traced` 對 DataFrame 做
        `not container` → ValueError）。L2 改看 `.empty` 後轉為正式測試。"""
        assert lights["fut_net"] == "gray"
        assert rd["fut_net"]["reason"] == MISSING_OUT_OF_RANGE

    @pytest.mark.parametrize("li_latest, reason", [
        (pd.DataFrame({"外資大小": ["-"]}), MISSING_NO_VALUE),       # tab_macro 全 '-' 也存入
        (pd.DataFrame({"其他欄": [1.0]}), MISSING_NO_VALUE),         # 缺欄
        (pd.DataFrame(), MISSING_NOT_LOADED),                         # 空表 = 容器空
        (pd.DataFrame({"外資大小": []}), MISSING_NOT_LOADED),        # 有欄無列 = 容器空
        (None, MISSING_NOT_LOADED),                                   # 沒載入
    ], ids=["dash", "no-col", "empty-df", "empty-rows", "none"])
    def test_fut_net_missing_dataframe_does_not_crash(self, li_latest, reason):
        """NF-f1：fut_net 的 container 是 DataFrame；取不到值時 L2 不得拋
        ValueError（修前 '-' / 缺欄 / 空表全炸），而是回灰燈並給正確缺值原因。
        ⛔ 不得捏 0（0 在 fut_net 會被判成某個燈色）。"""
        _, lights, rd = self._all_lamps(1.0, li_latest=li_latest)
        assert lights["fut_net"] == "gray"
        assert rd["fut_net"]["state"] == "missing"
        assert rd["fut_net"]["value"] is None
        assert rd["fut_net"]["reason"] == reason

    def test_v1_bar_render_shows_gray_not_green(self, monkeypatch):
        """真的呼叫 v1 `render_five_bucket_bar`（攔 st），確認長期桶那格印的是灰燈。"""
        from src.ui.tabs.macro import helpers as H
        fake = _FakeSt()
        monkeypatch.setattr(H, "st", fake)
        out, _, _ = _v1(INF)
        H.render_five_bucket_bar(out)
        _long = next(h for h in fake.md if "🌳 長期:" in h)
        _gray = (f'<span style="color:{LEVEL_COLOR["gray"]};">'
                 f'{LEVEL_EMOJI["gray"]} {BUCKET_LEVEL_LABEL["long"]["gray"]}</span>')
        assert _gray in _long
        assert LEVEL_EMOJI["green"] not in _long
        _detail = next(h for h in fake.md if "M1B-M2 資金動能" in h)
        assert f'{LEVEL_EMOJI["gray"]} M1B-M2 資金動能：<b>—</b>' in _detail

    def test_v1_bucket_summary_bar_html_shows_gray(self):
        """v1 各桶頂部的輕量 bar（L0 純字串 builder）同樣吃 L2 summary。"""
        out, _, _ = _v1(INF)
        html = mb.bucket_summary_bar_html("long", out["long"])
        assert f'{LEVEL_EMOJI["gray"]} {BUCKET_LEVEL_LABEL["long"]["gray"]}' in html
        assert "🔴 0 ｜ 🟡 0 ｜ 🟢 0" in html


# ════════════════════════════════════════════════════════════════
# 3b. v2 今天頁：L3 load_section_inputs → L2 側車 → L5 page_today 燈卡
# ════════════════════════════════════════════════════════════════
def _v2_today(gap):
    from src.ui.render.macro_v2_cards import band_meta, threshold_text
    from src.ui.views import page_today as P
    sess = {"m1b_m2_info": {"m1b_yoy": 3.0, "m2_yoy": 1.0, "gap": gap,
                            "source": "CBC-tier1"}}
    ro = P.load_macro_readout(sess)
    tiles = P.build_indicator_tiles(ro, band_label=band_meta, thr_text=threshold_text)
    tile = next(t for t in tiles["long"] if t.card.key == f"detail.{_KEY}")
    btile = next(t for t in P.build_bucket_tiles(ro) if t.card.key == "summary.long")
    return ro, tile, P.coverage(tiles), btile


class TestV2Today:

    def test_plus_inf_lamp_not_green(self):
        from shared.ui_state import UI_LIVE
        ro, tile, cov, btile = _v2_today(INF)
        rec = ro.readiness[_KEY]
        assert rec["state"] == "missing" and rec["value"] is None   # 修前 ok / inf
        assert tile.card.state != UI_LIVE                            # 修前 live
        assert tile.signal_text == ""                                # 修前「綠」
        assert "inf" not in str(tile.card.value)                     # 修前 'inf%'
        assert cov.live == 0                                         # 修前 1
        assert btile.card.state != UI_LIVE                           # 修前 live「結構健康」
        assert btile.signal_text == ""

    @pytest.mark.parametrize("value", [INF, NINF], ids=["+inf", "-inf"])
    def test_presentation_identical_to_nan(self, value):
        """灰燈沿用既有缺值呈現：與 NaN（既有前例）的卡片逐欄相同，不新增任何字。"""
        _, t_x, c_x, b_x = _v2_today(value)
        _, t_n, c_n, b_n = _v2_today(NAN)
        assert (t_x.card, t_x.signal_text, t_x.signal_color, t_x.facts) == \
               (t_n.card, t_n.signal_text, t_n.signal_color, t_n.facts)
        assert c_x == c_n
        assert (b_x.card, b_x.signal_text) == (b_n.card, b_n.signal_text)

    @pytest.mark.parametrize("value", [INF, NINF, NAN], ids=["+inf", "-inf", "nan"])
    def test_defense_in_depth_sidecar_bypassing_range_guard(self, value):
        """縱深：就算側車被別的路徑寫成 state=ok / value=非有限值（繞過
        `within_valid_range`），燈號頻道也只會是灰，不會是綠 / 紅。"""
        from src.ui.render.macro_v2_cards import band_meta
        from src.ui.views import page_today as P
        _spec = SPECS_BY_KEY[_KEY]
        rec = {"state": "ok", "value": value, "reason": None, "hit_source": "test"}
        t = P.build_indicator_tile(_KEY, rec, requested=True, error="",
                                   band_label=band_meta, thr_text=None)
        assert t.signal_text == band_meta("gray", _spec)[0]
        assert t.signal_text not in (band_meta(b, _spec)[0]
                                     for b in ("green", "yellow", "red"))

    @pytest.mark.parametrize("gap,signal", [(2.0, "綠"), (0.5, "黃"), (-0.5, "紅")])
    def test_finite_unchanged(self, gap, signal):
        from shared.ui_state import UI_LIVE
        _, tile, cov, _ = _v2_today(gap)
        assert tile.card.state == UI_LIVE and tile.signal_text == signal
        assert cov.live == 1


# ════════════════════════════════════════════════════════════════
# 4. 其他直接呼叫 classify_danger 的消費端
# ════════════════════════════════════════════════════════════════
class TestOtherCallers:

    @pytest.mark.parametrize("value", [INF, NINF, NAN], ids=["+inf", "-inf", "nan"])
    def test_v2_macro_tab_rows(self, value):
        """v2 總經分頁 `build_rows`：經側車 → 灰 / missing；強塞側車也只會灰。"""
        from src.ui.tabs import tab_macro_v2 as T
        _, rd, _ = _v1(value)
        row = next(r for r in T.build_rows(rd) if r.key == _KEY)
        assert row.band == "gray" and row.state == "missing"
        forced = {_KEY: {"state": "ok", "value": value, "wired": True}}
        assert next(r for r in T.build_rows(forced) if r.key == _KEY).band == "gray"

    @pytest.mark.parametrize("value", [INF, NINF, NAN], ids=["+inf", "-inf", "nan"])
    def test_reference_row_usdtwd_band_gray(self, value):
        """參考走勢 usdtwd（有門檻、不經 within_valid_range）：修前 +inf 紅、−inf / NaN 綠。"""
        from src.ui.tabs import tab_macro_v2 as T
        assert T.build_reference_row("usdtwd", value).band == "gray"

    @pytest.mark.parametrize("value", [31.0, 32.5, 33.5])
    def test_reference_row_usdtwd_finite_unchanged(self, value):
        from src.ui.tabs import tab_macro_v2 as T
        _spec = mb.REF_SPECS_BY_KEY["usdtwd"]
        assert T.build_reference_row("usdtwd", value).band == classify_danger(value, _spec)
        assert classify_danger(value, _spec) != "gray"

    @pytest.mark.parametrize("key", ["usdtwd", "taiex"])
    @pytest.mark.parametrize("value", [INF, NINF, NAN], ids=["+inf", "-inf", "nan"])
    def test_reference_row_non_finite_same_as_missing(self, key, value):
        """NF-f3：參考走勢遇非有限值 → 與「沒有值」完全同一條既有呈現
        （state=missing、reason=MISSING_NO_VALUE、數字印「無資料」），
        修前 state=live、L4 印出「inf TWD/USD」。⛔ 不捏 0。"""
        from src.ui.tabs import tab_macro_v2 as T
        from src.ui.render.macro_v2_cards import fmt_value
        r, miss = T.build_reference_row(key, value), T.build_reference_row(key, None)
        assert r == miss
        assert r.value is None and r.state == "missing" and r.reason == MISSING_NO_VALUE
        assert fmt_value(r.value, r.unit, r.decimals) == "無資料"

    @pytest.mark.parametrize("key,value", [("usdtwd", 32.5), ("taiex", 22000.0), ("usdtwd", 0.0)])
    def test_reference_row_finite_stays_live(self, key, value):
        """有限值（含 0）照舊 live，不被誤當缺值。"""
        from src.ui.tabs import tab_macro_v2 as T
        r = T.build_reference_row(key, value)
        assert r.value == value and r.state == "live" and r.reason is None

    @pytest.mark.parametrize("value", [INF, NINF, NAN], ids=["+inf", "-inf", "nan"])
    def test_digest_vix_non_finite_same_as_missing(self, value):
        """推播 VIX 行：修前 +inf「🔴 市場恐慌」、−inf / NaN「🟢 市場平靜」（給了操作建議）。
        修後與「沒有值」走同一條既有文案，不給任何建議。"""
        from src.compute.notify.holdings_digest_message import _vix_line
        assert _vix_line(value, 3) == _vix_line(None, 3)

    @pytest.mark.parametrize("value,level", [(15.0, "green"), (25.0, "yellow"), (35.0, "red")])
    def test_digest_vix_finite_unchanged(self, value, level):
        from src.compute.notify.holdings_digest_message import _vix_line
        assert LEVEL_EMOJI[level] in _vix_line(value, 3)[0]
