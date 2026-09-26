"""燈卡「變化方向」列（2026-09-24）。

守什麼：
- L0 `shared/lamp_direction_thresholds.py`：key 集合、持平帶、m1b 無帶寬。
- L2 `src/compute/macro/lamp_direction.py`：邊界（None / 空 / 單點 / 恰 n 點 /
  NaN / inf / 帶寬邊緣 / 舊值 ≤ 0 / 缺月 / 未知 key）與文字格式。
- L3 `macro_v2_service.get_monthly_history`：缺檔 → {}，NaN 列丟棄不補。
- L5 `page_today`：16 張燈卡裡只有 4 張出「變化方向」，且其餘 12 張、燈號、
  等級與不傳 directions 時**逐字相同**。
- 2026-09-26 擴到 16 盞：vix 有真方向（序列取自本輪 session，經 L3
  `load_section_inputs`）；其餘 11 盞（含 adl：單日估算無自相關）恆為「無資料」；
  foreign_net（未接線）不出列；首批 4 盞的卡面與 origin/main 10f385c 的黃金雜湊逐字相同。
"""
from __future__ import annotations

import math
import re

import pytest

from shared.lamp_direction_thresholds import (
    LAMP_DIRECTION_FACT_KEY,
    LAMP_DIRECTION_FLAT_BAND,
    LAMP_DIRECTION_KEYS,
    LAMP_DIRECTION_NODATA_TEXT,
    LAMP_DIRECTION_WINDOWS,
)
from shared.macro_buckets import BUCKET_DANGER_SPECS, SPECS_BY_KEY
from src.compute.macro.lamp_direction import (
    LampDirection,
    compute_lamp_direction,
    format_direction_text,
)


def _daily(values, start_day=1):
    """交易日序列：每列一個日期（ISO 字串遞增）。"""
    return [(f"2026-{1 + (i // 28):02d}-{1 + (i % 28):02d}", v)
            for i, v in enumerate(values, start=start_day - 1)]


def _monthly(values, year=2025, month=1):
    out = []
    for i, v in enumerate(values):
        m = month - 1 + i
        out.append((f"{year + m // 12}-{m % 12 + 1:02d}-01", v))
    return out


# ════════════════════════════════════════════════════════════════
# L0
# ════════════════════════════════════════════════════════════════
class TestL0:
    def test_keys_are_all_sixteen_lamps(self):
        # 2026-09-26：擴到全部 16 盞；首批 4 盞的順序不動
        assert set(LAMP_DIRECTION_KEYS) == {s.key for s in BUCKET_DANGER_SPECS}
        assert len(LAMP_DIRECTION_KEYS) == len(set(LAMP_DIRECTION_KEYS)) == 16
        assert LAMP_DIRECTION_KEYS[:4] == ("margin", "bias_240", "m1b_m2_gap", "ism_pmi")

    def test_keys_are_real_lamps(self):
        assert set(LAMP_DIRECTION_KEYS) <= set(SPECS_BY_KEY)

    def test_every_key_has_window(self):
        assert set(LAMP_DIRECTION_WINDOWS) == set(LAMP_DIRECTION_KEYS)

    def test_flat_band_values(self):
        assert LAMP_DIRECTION_FLAT_BAND == {"margin": 1.0, "bias_240": 1.0, "ism_pmi": 0.5,
                                            "vix": 0.5, "ndc_signal": 0.0}

    def test_band_exactly_for_computed_keys(self):
        # 有帶寬 ⇔ 會算方向（mode != none）—— 不得有「算方向卻沒量過帶寬」的燈
        computed = {k for k, c in LAMP_DIRECTION_WINDOWS.items() if c["mode"] != "none"}
        assert computed == set(LAMP_DIRECTION_FLAT_BAND) == set(_REAL_KEYS)

    def test_new_windows_use_existing_texts_only(self):
        # ⛔ 不新增使用者看得到的文字：視窗 / 單位只能是首批已用過的那幾種
        first = ("margin", "bias_240", "ism_pmi", "m1b_m2_gap")
        texts = {LAMP_DIRECTION_WINDOWS[k]["window_text"] for k in first}
        units = {LAMP_DIRECTION_WINDOWS[k]["unit"] for k in first}
        for k, c in LAMP_DIRECTION_WINDOWS.items():
            assert c["window_text"] in texts, k
            assert c["unit"] in units, k

    @pytest.mark.parametrize("key", sorted(set(LAMP_DIRECTION_KEYS) - {"margin", "bias_240",
                                                                     "ism_pmi", "m1b_m2_gap",
                                                                     "vix", "ndc_signal"}))
    def test_none_keys_have_reason_and_no_band(self, key):
        c = LAMP_DIRECTION_WINDOWS[key]
        assert c["mode"] == "none" and key not in LAMP_DIRECTION_FLAT_BAND
        assert c["none_reason"]
        d = compute_lamp_direction(key, _daily([1.0] * 10 + [99.0] * 21))
        assert d.direction == "nodata" and d.delta is None
        assert c["none_reason"] in d.reason
        assert format_direction_text(d) == LAMP_DIRECTION_NODATA_TEXT

    def test_m1b_has_no_band_and_no_history(self):
        assert "m1b_m2_gap" not in LAMP_DIRECTION_FLAT_BAND
        assert LAMP_DIRECTION_WINDOWS["m1b_m2_gap"]["mode"] == "none"


# ════════════════════════════════════════════════════════════════
# L2 compute
# ════════════════════════════════════════════════════════════════
class TestComputeNodata:
    @pytest.mark.parametrize("key", ["margin", "bias_240", "ism_pmi"])
    @pytest.mark.parametrize("pts", [None, []])
    def test_none_or_empty(self, key, pts):
        assert compute_lamp_direction(key, pts).direction == "nodata"

    def test_single_row(self):
        assert compute_lamp_direction("margin", _daily([100.0])).direction == "nodata"

    def test_exactly_n_rows_is_insufficient(self):
        n = LAMP_DIRECTION_WINDOWS["margin"]["lookback_rows"]
        assert compute_lamp_direction("margin", _daily([100.0] * n)).direction == "nodata"

    def test_n_plus_one_rows_is_enough(self):
        n = LAMP_DIRECTION_WINDOWS["margin"]["lookback_rows"]
        d = compute_lamp_direction("margin", _daily([100.0] * n + [110.0]))
        assert d.direction == "up"

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_new_end(self, bad):
        assert compute_lamp_direction("bias_240", _daily([1.0] * 20 + [bad])).direction == "nodata"

    @pytest.mark.parametrize("bad", [float("nan"), float("inf")])
    def test_non_finite_old_end(self, bad):
        assert compute_lamp_direction("bias_240", _daily([bad] + [1.0] * 20)).direction == "nodata"

    @pytest.mark.parametrize("base", [0.0, -5.0])
    def test_margin_base_le_zero(self, base):
        d = compute_lamp_direction("margin", _daily([base] + [100.0] * 20))
        assert d.direction == "nodata"
        assert d.delta is None

    def test_m1b_always_nodata_even_with_clean_data(self):
        pts = _monthly([1.0, 2.0, 3.0, 50.0])
        assert compute_lamp_direction("m1b_m2_gap", pts).direction == "nodata"
        assert compute_lamp_direction("m1b_m2_gap", None).direction == "nodata"

    def test_unknown_key_raises(self):
        with pytest.raises(KeyError):
            compute_lamp_direction("usdtwd", _daily([1.0] * 30))   # 參考走勢，不是燈

    def test_m1b_reason_unchanged(self):
        # 2026-09-26 L2 加 `none_reason` 後，m1b 的原因字串逐字不變
        assert (compute_lamp_direction("m1b_m2_gap", None).reason
                == "m1b_m2_gap：歷史資料已知不可信，刻意不算方向")

    def test_pmi_missing_month_is_nodata(self):
        pts = [("2026-05-01", 50.0), ("2026-07-01", 55.0)]
        assert compute_lamp_direction("ism_pmi", pts).direction == "nodata"

    def test_duplicate_dates_nodata(self):
        pts = [("2026-07-01", 50.0), ("2026-07-01", 55.0)]
        assert compute_lamp_direction("ism_pmi", pts).direction == "nodata"

    @pytest.mark.parametrize("key", ["margin", "bias_240", "vix"])
    def test_duplicate_dates_nodata_on_daily_keys(self, key):
        """QA 補洞（2026-09-26）：上一條的月序列同時被「中間缺月」擋下（gap 0 ≠ 1），
        重複日期檢查本身在日序列上沒人守（拿掉它全綠）。這裡夠長、端點會算出 ↗，
        只有重複日期檢查能讓它變 nodata —— ⛔ 不得靜默用錯位的視窗算方向。"""
        n = LAMP_DIRECTION_WINDOWS[key]["lookback_rows"]
        pts = _daily([100.0] * (n + 1) + [150.0])
        pts[-1] = (pts[-2][0], pts[-1][1])            # 最後兩列同一天
        d = compute_lamp_direction(key, pts)
        assert d.direction == "nodata" and d.delta is None
        assert "重複日期" in d.reason


class TestComputeDirection:
    def test_vix_diff_points_and_band(self):
        # 帶寬 0.5 點（含等於）：+0.5 持平、+0.6 上升、-0.6 下降
        for new, exp in ((20.5, "flat"), (20.6, "up"), (19.4, "down"), (19.5, "flat")):
            d = compute_lamp_direction("vix", _daily([20.0] * 20 + [new]))
            assert d.direction == exp, (new, d)
        d = compute_lamp_direction("vix", _daily([20.0] * 20 + [25.0]))
        assert format_direction_text(d).startswith("↗ 上升（近 20 交易日 +5.0 點，至 ")

    def test_adl_is_nodata_even_with_clean_series(self):
        # 2026-09-26 QA：ad_ratio 單日估算無自相關（lag-1 −0.028 / lag-20 0.016）⇒ 不出箭頭
        d = compute_lamp_direction("adl", _daily([50.0] * 20 + [80.0]))
        assert d.direction == "nodata" and "自相關" in d.reason
        assert "adl" not in LAMP_DIRECTION_FLAT_BAND

    def test_jingqi_is_nodata_even_with_clean_series(self):
        # 2026-09-26 第二批：5 日均的 lag-20 自相關 0.025（量測見 L0 檔頭）⇒ 不出箭頭
        d = compute_lamp_direction("jingqi", _daily([50.0] * 20 + [80.0]))
        assert d.direction == "nodata" and "自相關" in d.reason and "0.025" in d.reason
        assert "jingqi" not in LAMP_DIRECTION_FLAT_BAND

    @pytest.mark.parametrize("key,needle", [
        ("health", "health_partial"),      # 凍結檔 date 非交易日 + 燈值不帶 partial 旗標
        ("tw_export", "持平帶量不到"),
    ])
    def test_second_batch_stays_nodata_with_reason(self, key, needle):
        # 2026-09-26 第二批：逐盞查證後維持無資料；給乾淨序列也不能冒出箭頭
        monthly = [(f"2025-{m:02d}-01", float(m)) for m in range(1, 13)]
        for pts in (_daily([1.0] * 20 + [99.0]), monthly):
            d = compute_lamp_direction(key, pts)
            assert d.direction == "nodata" and d.delta is None, (key, d)
            assert needle in d.reason, d.reason
            assert format_direction_text(d) == LAMP_DIRECTION_NODATA_TEXT
        assert key not in LAMP_DIRECTION_FLAT_BAND

    @pytest.mark.parametrize("key", ["vix"])
    def test_new_keys_need_21_rows(self, key):
        assert compute_lamp_direction(key, _daily([1.0] * 20)).direction == "nodata"
        assert compute_lamp_direction(key, _daily([1.0] * 19 + [9.0, 9.0])).direction == "up"

    def test_margin_up_down_pct(self):
        up = compute_lamp_direction("margin", _daily([100.0] * 20 + [109.9]))
        assert up.direction == "up" and math.isclose(up.delta, 9.9, rel_tol=1e-9)
        dn = compute_lamp_direction("margin", _daily([100.0] * 20 + [95.0]))
        assert dn.direction == "down" and math.isclose(dn.delta, -5.0, rel_tol=1e-9)

    def test_margin_band_edge_is_flat(self):
        # 101/100 − 1 = 1.0000000000000009%（浮點）— 仍須判持平（== 帶寬 → 持平）
        d = compute_lamp_direction("margin", _daily([100.0] * 20 + [101.0]))
        assert d.direction == "flat"
        d = compute_lamp_direction("margin", _daily([100.0] * 20 + [99.0]))
        assert d.direction == "flat"

    def test_margin_just_outside_band(self):
        assert compute_lamp_direction("margin", _daily([100.0] * 20 + [101.2])).direction == "up"

    def test_bias_diff_points(self):
        d = compute_lamp_direction("bias_240", _daily([5.0] * 20 + [7.5]))
        assert d.direction == "up" and math.isclose(d.delta, 2.5)
        assert compute_lamp_direction("bias_240", _daily([5.0] * 20 + [6.0])).direction == "flat"
        assert compute_lamp_direction("bias_240", _daily([5.0] * 20 + [3.0])).direction == "down"

    def test_bias_uses_row_n_back_not_first(self):
        # 第 1 列是 999，但只有第 −21 列才是比較基準
        d = compute_lamp_direction("bias_240", _daily([999.0] + [5.0] * 20 + [8.0]))
        assert d.direction == "up" and math.isclose(d.delta, 3.0)

    def test_pmi_mom(self):
        assert compute_lamp_direction("ism_pmi", _monthly([50.0, 50.5])).direction == "flat"
        assert compute_lamp_direction("ism_pmi", _monthly([50.0, 49.5])).direction == "flat"
        assert compute_lamp_direction("ism_pmi", _monthly([50.0, 50.6])).direction == "up"
        assert compute_lamp_direction("ism_pmi", _monthly([50.0, 49.4])).direction == "down"

    @pytest.mark.parametrize("new, expected, text", [
        (50.51, "flat", "→ 持平（較上月 +0.5 點"),
        (50.49, "flat", "→ 持平（較上月 +0.5 點"),
        (50.5, "flat", "→ 持平（較上月 +0.5 點"),
        (49.49, "flat", "→ 持平（較上月 -0.5 點"),
        (50.56, "up", "↗ 上升（較上月 +0.6 點"),
    ])
    def test_pmi_rounding_never_contradicts_arrow(self, new, expected, text):
        d = compute_lamp_direction("ism_pmi", _monthly([50.0, new]))
        assert d.direction == expected
        assert format_direction_text(d).startswith(text)

    @pytest.mark.parametrize("new, expected, text", [
        (101.04, "flat", "→ 持平（近 20 交易日 +1.0%"),
        (100.96, "flat", "→ 持平（近 20 交易日 +1.0%"),
        (98.96, "flat", "→ 持平（近 20 交易日 -1.0%"),
        (101.2, "up", "↗ 上升（近 20 交易日 +1.2%"),
    ])
    def test_margin_rounding_never_contradicts_arrow(self, new, expected, text):
        d = compute_lamp_direction("margin", _daily([100.0] * 20 + [new]))
        assert d.direction == expected
        assert format_direction_text(d).startswith(text)

    def test_pmi_across_year_boundary(self):
        pts = [("2025-12-01", 50.0), ("2026-01-01", 52.0)]
        assert compute_lamp_direction("ism_pmi", pts).direction == "up"

    def test_unsorted_input_is_sorted(self):
        pts = [("2026-08-01", 55.0), ("2026-07-01", 50.0)]
        d = compute_lamp_direction("ism_pmi", pts)
        assert d.direction == "up" and d.as_of == "2026-08-01"

    def test_does_not_mutate_input(self):
        pts = [("2026-08-01", 55.0), ("2026-07-01", 50.0)]
        before = list(pts)
        compute_lamp_direction("ism_pmi", pts)
        assert pts == before


class TestFormat:
    def test_up_text(self):
        d = compute_lamp_direction("margin", [(f"2026-08-{i:02d}", 100.0) for i in range(1, 21)]
                                   + [("2026-09-24", 109.9)])
        assert format_direction_text(d) == "↗ 上升（近 20 交易日 +9.9%，至 2026-09-24）"

    def test_flat_and_down_text(self):
        flat = compute_lamp_direction("ism_pmi", [("2026-07-01", 50.0), ("2026-08-01", 50.3)])
        assert format_direction_text(flat) == "→ 持平（較上月 +0.3 點，至 2026-08-01）"
        down = compute_lamp_direction("bias_240", _daily([5.0] * 20 + [2.0]))
        assert format_direction_text(down).startswith("↘ 下降（近 20 交易日 -3.0 個百分點，至 ")

    def test_nodata_text_has_no_arrow(self):
        for key in LAMP_DIRECTION_KEYS:
            txt = format_direction_text(compute_lamp_direction(key, None))
            assert txt == LAMP_DIRECTION_NODATA_TEXT == "無資料"

    def test_no_forbidden_glyphs(self):
        samples = [compute_lamp_direction("bias_240", _daily([5.0] * 20 + [v]))
                   for v in (1.0, 5.5, 9.0)] + [compute_lamp_direction("m1b_m2_gap", None)]
        for d in samples:
            t = format_direction_text(d)
            assert "▲" not in t and "▼" not in t
            assert not any(c in t for c in "🔴🟢🟡")

    def test_tiny_negative_does_not_print_minus_zero(self):
        d = LampDirection("flat", -0.01, "%", "近 20 交易日", "2026-09-24")
        assert "-0.0" not in format_direction_text(d)

    def test_invalid_direction_rejected(self):
        with pytest.raises(ValueError):
            LampDirection("sideways", 0.0, "", "", None)


# ════════════════════════════════════════════════════════════════
# L3
# ════════════════════════════════════════════════════════════════
class TestL3MonthlyHistory:
    def _call(self, monkeypatch, tmp_path):
        from src.data.macro import macro_cache_reader as R
        from src.services import macro_v2_service as S

        monkeypatch.setattr(R, "DEFAULT_PARQUET_CACHE_DIR", tmp_path)
        try:
            S.get_monthly_history.clear()
        except AttributeError:
            pass
        try:
            return S.get_monthly_history()
        finally:
            try:
                S.get_monthly_history.clear()
            except AttributeError:
                pass

    def test_missing_file_returns_empty(self, monkeypatch, tmp_path, capsys):
        assert self._call(monkeypatch, tmp_path) == {}
        assert "tw_pmi.parquet" in capsys.readouterr().out

    def test_nan_rows_dropped_not_filled(self, monkeypatch, tmp_path):
        import pandas as pd

        pd.DataFrame({"date": ["2026-06-01", "2026-07-01", "2026-08-01"],
                      "pmi": [50.0, float("nan"), 52.0]}).to_parquet(tmp_path / "tw_pmi.parquet")
        out = self._call(monkeypatch, tmp_path)
        assert out == {"ism_pmi": [("2026-06-01", 50.0), ("2026-08-01", 52.0)]}
        # 缺 7 月 → 「較上月」不成立 → nodata（不跨月硬比）
        assert compute_lamp_direction("ism_pmi", out["ism_pmi"]).direction == "nodata"


# ════════════════════════════════════════════════════════════════
# L5 render
# ════════════════════════════════════════════════════════════════
def _live_readout():
    from src.ui.views import page_today as P

    rd = {s.key: {"wired": True, "discriminative": True, "state": "ok",
                  "value": float(s.yellow), "reason": None, "hit_source": "TEST"}
          for s in BUCKET_DANGER_SPECS}
    return P.MacroReadout(requested=True, readiness=rd)


#: 會算真方向的燈（其餘 mode = "none"）。
_REAL_KEYS = ("margin", "bias_240", "ism_pmi", "vix", "ndc_signal")
#: 首批 4 盞（2026-09-24），卡面必須與擴充前逐字相同。
_FIRST_FOUR = ("margin", "bias_240", "m1b_m2_gap", "ism_pmi")


def _first_four_directions():
    return {
        "margin": compute_lamp_direction("margin", _daily([100.0] * 20 + [109.9])),
        "bias_240": compute_lamp_direction("bias_240", _daily([5.0] * 20 + [5.5])),
        "ism_pmi": compute_lamp_direction("ism_pmi", _monthly([50.0, 48.0])),
        "m1b_m2_gap": compute_lamp_direction("m1b_m2_gap", None),
    }


def _directions():
    d = _first_four_directions()
    d["vix"] = compute_lamp_direction("vix", _daily([20.0] * 20 + [25.0]))
    for k in LAMP_DIRECTION_KEYS:
        d.setdefault(k, compute_lamp_direction(k, None))
    # 不在 LAMP_DIRECTION_KEYS 的 key（參考走勢）就算塞進來也不得出列
    d["taiex"] = LampDirection("up", 5.0, "%", "近 20 交易日", "2026-09-24")
    return d


#: origin/main 10f385c 的首批 4 張卡（見 `test_first_four_match_origin_main_golden`）。
_GOLDEN_10F385C = {
    "margin": "6306261e4ef22d50adf63221f7178ca4dea2a09a1ca30f612bd3862e25c844a0",
    "bias_240": "13492b2a500fc1e67bacfee820c14c5d0e94a190d255af196f261545a53325e9",
    "m1b_m2_gap": "b0726ac01d187ef6647f5a87e20b97dc502ac79127d37ae6708251890c7643bc",
    "ism_pmi": "6f4a0a50abae3854e86e5f5629fc22f457fdb6724ac400dc1867dc413391731f",
}
_GOLDEN_ROW = {
    "margin": "↗ 上升（近 20 交易日 +9.9%，至 2026-01-21）",
    "bias_240": "→ 持平（近 20 交易日 +0.5 個百分點，至 2026-01-21）",
    "m1b_m2_gap": "無資料",
    "ism_pmi": "↘ 下降（較上月 -2.0 點，至 2025-02-01）",
}


def _flat(tiles_by_bucket):
    return {t.card.key: t for ts in tiles_by_bucket.values() for t in ts}


#: 卡面上「變化方向」那一列的標籤 span（⚠️ 不能只搜「變化方向」四個字 ——
#: margin 的既有說明文字本來就含這四個字）。
_ROW_SPAN = f'<span class="blk-fact-k">{LAMP_DIRECTION_FACT_KEY}</span>'


def _build(readout, with_dirs):
    from src.ui.views import page_today as P

    band_label, thr_text, _, l4_err = P._load_l4_labels()
    kw = dict(band_label=band_label, thr_text=thr_text, l4_error=l4_err)
    if with_dirs:
        kw["directions"] = _directions()
    return _flat(P.build_indicator_tiles(readout, **kw))


def _cold_readout():
    from src.ui.views import page_today as P

    return P.MacroReadout(requested=False)


def _failed_readout():
    from src.ui.views import page_today as P

    return P.MacroReadout(requested=True, error="ImportError('x')")


class TestRenderLive:
    def _both(self):
        from src.ui.views import page_today as P

        return P, _build(_live_readout(), False), _build(_live_readout(), True)

    def test_row_on_every_live_or_degraded_card(self):
        P, _, with_ = self._both()
        assert len(with_) == 16
        has = {k.split(".", 1)[1] for k, t in with_.items()
               if any(f[0] == LAMP_DIRECTION_FACT_KEY for f in t.facts)}
        # foreign_net 未接線 ⇒ 不出列；其餘 15 盞（live / degraded）都有
        assert has == set(LAMP_DIRECTION_KEYS) - {"foreign_net"}
        assert with_["detail.foreign_net"].card.state == P.UI_UNWIRED
        for k, t in with_.items():
            html = P.v2_card_html(t)
            assert (_ROW_SPAN in html) == (k.split(".", 1)[1] in has)

    def test_unwired_card_identical(self):
        P, without, with_ = self._both()
        k = "detail.foreign_net"
        assert with_[k] == without[k]
        assert P.v2_card_html(with_[k]) == P.v2_card_html(without[k])

    def test_first_four_match_origin_main_golden(self):
        # 首批 4 盞：與 origin/main 10f385c（擴充前）產出的卡面 HTML 黃金雜湊逐字相同。
        # 黃金值取得方式（2026-09-26）：在 10f385c 以本檔 `_live_readout()` ＋
        # `_first_four_directions()` 呼叫 `build_indicator_tiles` → `v2_card_html`，取 sha256。
        # margin 的 hover `title` 含 "\n\n"（同日修的 HTML 區塊外洩 bug）：它的黃金值 ＝
        # 10f385c 原字串**只把 title 屬性內的 "\n" 換成 "&#10;"** 後的 sha256
        # （原始 10f385c 雜湊 0bc5bb1f…b7a678；卡片本體一個字元都不變）。
        import hashlib

        from src.ui.views import page_today as P

        band_label, thr_text, _, l4_err = P._load_l4_labels()
        kw = dict(band_label=band_label, thr_text=thr_text, l4_error=l4_err)
        full = _flat(P.build_indicator_tiles(_live_readout(), directions=_directions(), **kw))
        # 2026-09-26 a11y（客戶核可）：「▸ 詳細」開關加了 `aria-labelledby`／`aria-controls`，
        # 並在標題／label／body 掛 `id`（純屬性、⛔ 畫面與文字不變）。黃金值**不重算**：
        # 先拿掉這幾個新增屬性再比 ⇒ 仍證明卡片其餘部分與 10f385c 逐字相同。
        _a11y = re.compile(
            r' (?:aria-labelledby|aria-controls)="[^"]*"'
            r'|(?<=<span class="blk-title") id="[^"]*"'
            r'|(?<=<label class="blk-fold-s") id="[^"]*"'
            r'|(?<=<div class="blk-fold-b") id="[^"]*"')
        for key in _FIRST_FOUR:
            raw = P.v2_card_html(full[f"detail.{key}"])
            assert "aria-labelledby" in raw, key       # a11y 屬性確實在（不是剝了個空）
            html = _a11y.sub("", raw)
            assert hashlib.sha256(html.encode()).hexdigest() == _GOLDEN_10F385C[key], key
            assert dict(full[f"detail.{key}"].facts)[LAMP_DIRECTION_FACT_KEY] == _GOLDEN_ROW[key]

    def test_band_level_state_unchanged(self):
        _, without, with_ = self._both()
        for k in with_:
            a, b = with_[k], without[k]
            assert (a.card, a.signal_text, a.signal_color) == (b.card, b.signal_text, b.signal_color)
            # 只多一列，其餘列順序與內容不變
            assert tuple(f for f in a.facts if f[0] != LAMP_DIRECTION_FACT_KEY) == b.facts

    def test_position(self):
        P, _, with_ = self._both()
        for key in set(LAMP_DIRECTION_KEYS) - {"foreign_net"}:
            t = with_[f"detail.{key}"]
            state = t.card.state
            assert state in (P.UI_LIVE, P.UI_DEGRADED)
            idx = [f[0] for f in t.facts].index(LAMP_DIRECTION_FACT_KEY)
            if state == P.UI_DEGRADED:
                assert t.facts[0][0] == "現值" and idx == 1
            else:
                assert idx == 0
                html = P.v2_card_html(t)
                # 判決行正下方的第一列
                assert ('</div><div class="blk-facts"><div class="blk-fact">'
                        f'<span class="blk-fact-k">{LAMP_DIRECTION_FACT_KEY}</span>') in html
                assert html.index('class="blk-lvl"') < html.index(LAMP_DIRECTION_FACT_KEY)

    def test_texts(self):
        _, _, with_ = self._both()
        txt = {k.split(".", 1)[1]: dict(t.facts).get(LAMP_DIRECTION_FACT_KEY)
               for k, t in with_.items()}
        assert txt["m1b_m2_gap"] == "無資料"
        assert txt["margin"].startswith("↗ 上升（近 20 交易日 +9.9%")
        assert txt["bias_240"].startswith("→ 持平（近 20 交易日 +0.5 個百分點")
        assert txt["ism_pmi"].startswith("↘ 下降（較上月 -2.0 點")
        assert txt["vix"].startswith("↗ 上升（近 20 交易日 +5.0 點")
        assert txt["adl"] == "無資料"
        assert txt["foreign_net"] is None
        for k in set(LAMP_DIRECTION_KEYS) - set(_REAL_KEYS) - {"foreign_net"}:
            assert txt[k] == "無資料", k


@pytest.mark.parametrize("factory", [_cold_readout, _failed_readout],
                         ids=["cold_start", "failed"])
class TestRenderNotLive:
    """尚未載入 / 失敗：**任何一張卡都不出「變化方向」**，且與不傳 directions 逐字相同。"""

    def test_no_row_anywhere_and_identical(self, factory):
        from src.ui.views import page_today as P

        without, with_ = _build(factory(), False), _build(factory(), True)
        assert len(with_) == 16
        for k, t in with_.items():
            assert t.card.state not in (P.UI_LIVE, P.UI_DEGRADED)
            assert all(f[0] != LAMP_DIRECTION_FACT_KEY for f in t.facts)
            assert _ROW_SPAN not in P.v2_card_html(t)
            assert t == without[k]
            assert P.v2_card_html(t) == P.v2_card_html(without[k])


def test_direction_on_foreign_key_rejected(monkeypatch):
    # 2026-09-26 起 16 盞全在 LAMP_DIRECTION_KEYS；守衛本身仍要在（把 keys 縮回首批驗證）
    from src.ui.views import page_today as P

    monkeypatch.setattr(P, "LAMP_DIRECTION_KEYS", _FIRST_FOUR)
    with pytest.raises(ValueError):
        P.build_indicator_tile("vix", {}, requested=False, error="",
                               direction=compute_lamp_direction("m1b_m2_gap", None))


# ════════════════════════════════════════════════════════════════
# 2026-09-25 §1 Fail Loud：方向計算失敗 ⇒ 4 張卡顯示「計算失敗」，⛔ 不靜默消失
# ════════════════════════════════════════════════════════════════
from shared.lamp_direction_thresholds import (  # noqa: E402
    LAMP_DIRECTION_ERROR_TEXT,
    LAMP_DIRECTION_MISSING_REASON,
)
from src.compute.macro.lamp_direction import error_direction  # noqa: E402


def _dir_text(tiles, key):
    return dict(tiles[f"detail.{key}"].facts).get(LAMP_DIRECTION_FACT_KEY)


def _patch_loaders(monkeypatch, *, chart=None, monthly=None):
    from src.services import macro_v2_service as S

    monkeypatch.setattr(S, "get_chart_series", chart or (lambda: {}))
    monkeypatch.setattr(S, "get_monthly_history", monthly or (lambda: {}))


def _boom(*_a, **_k):
    raise RuntimeError("upstream exploded — long message that must not reach the card")


class TestErrorFormat:
    def test_error_text_constant(self):
        assert LAMP_DIRECTION_ERROR_TEXT == "計算失敗"

    @pytest.mark.parametrize("key", list(LAMP_DIRECTION_KEYS))
    def test_error_text_has_no_arrow(self, key):
        t = format_direction_text(error_direction(key, "RuntimeError"))
        assert t == "計算失敗（RuntimeError）"
        assert not any(c in t for c in "↗→↘▲▼🔴🟢🟡")

    def test_error_without_reason(self):
        assert format_direction_text(error_direction("margin", "")) == "計算失敗"

    def test_error_is_distinct_from_nodata(self):
        d = error_direction("ism_pmi", "KeyError")
        assert d.direction == "error" and d.delta is None and d.as_of is None
        assert format_direction_text(d) != LAMP_DIRECTION_NODATA_TEXT

    def test_error_unknown_key_raises(self):
        with pytest.raises(KeyError):
            error_direction("usdtwd", "RuntimeError")


class TestLoaderFailLoud:
    @pytest.mark.parametrize("which", ["both", "chart", "monthly"])
    def test_loader_raises_its_keys_show_error(self, monkeypatch, capsys, which):
        from src.ui.views import page_today as P

        if which == "both":
            _patch_loaders(monkeypatch, chart=_boom, monthly=_boom)
            err_keys = {"margin", "bias_240", "ism_pmi"}
        elif which == "chart":
            _patch_loaders(monkeypatch, chart=_boom,
                           monthly=lambda: {"ism_pmi": _monthly([50.0, 52.0])})
            err_keys = {"margin", "bias_240"}
        else:
            _patch_loaders(monkeypatch, monthly=_boom,
                           chart=lambda: {"margin": _daily([100.0] * 20 + [109.9]),
                                          "bias_240": _daily([5.0] * 20 + [5.5])})
            err_keys = {"ism_pmi"}
        dirs = P._load_lamp_directions()
        assert "變化方向計算失敗" in capsys.readouterr().out      # log 仍在
        assert set(dirs) == set(LAMP_DIRECTION_KEYS)
        assert {k for k, d in dirs.items() if d.direction == "error"} == err_keys
        # m1b（與其餘 mode = none）不讀 L3 ⇒ 任何 loader 失敗都仍是「無資料」
        assert dirs["m1b_m2_gap"].direction == "nodata"
        for k in {"margin", "bias_240", "ism_pmi"} - err_keys:
            assert dirs[k].direction in ("up", "flat", "down")
        for k in set(LAMP_DIRECTION_KEYS) - {"margin", "bias_240", "ism_pmi"}:
            assert dirs[k].direction == "nodata", k       # session=None ⇒ vix/adl 也無資料

        from src.ui.views import page_today as P2
        band_label, thr_text, _, l4_err = P2._load_l4_labels()
        kw = dict(band_label=band_label, thr_text=thr_text, l4_error=l4_err)
        with_ = _flat(P2.build_indicator_tiles(_live_readout(), directions=dirs, **kw))
        without = _flat(P2.build_indicator_tiles(_live_readout(), **kw))
        for key in err_keys:
            txt = _dir_text(with_, key)
            assert txt == "計算失敗（RuntimeError）"
            assert "upstream exploded" not in txt
            assert _ROW_SPAN in P2.v2_card_html(with_[f"detail.{key}"])
        assert _dir_text(with_, "m1b_m2_gap") == LAMP_DIRECTION_NODATA_TEXT
        # 未接線的卡不受影響
        assert with_["detail.foreign_net"] == without["detail.foreign_net"]
        # 燈號 / 等級不受影響
        for k in with_:
            a, b = with_[k], without[k]
            assert (a.card, a.signal_text, a.signal_color) == (b.card, b.signal_text, b.signal_color)

    def test_per_key_failure_isolated(self, monkeypatch, capsys):
        from src.compute.macro import lamp_direction as L
        from src.ui.views import page_today as P

        pmi = _monthly([50.0, 52.0])
        _patch_loaders(monkeypatch,
                       chart=lambda: {"margin": _daily([100.0] * 20 + [109.9]),
                                      "bias_240": _daily([5.0] * 20 + [5.5])},
                       monthly=lambda: {"ism_pmi": pmi})
        real = L.compute_lamp_direction

        def flaky(key, pts):
            if key == "bias_240":
                raise ZeroDivisionError("x")
            return real(key, pts)

        monkeypatch.setattr(L, "compute_lamp_direction", flaky)
        dirs = P._load_lamp_directions()
        assert "bias_240" in capsys.readouterr().out
        assert dirs["bias_240"].direction == "error"
        assert format_direction_text(dirs["bias_240"]) == "計算失敗（ZeroDivisionError）"
        assert dirs["margin"].direction == "up"
        assert dirs["ism_pmi"].direction == "up"
        assert dirs["m1b_m2_gap"].direction == "nodata"

    def test_l2_import_failure_still_shows_error(self, monkeypatch, capsys):
        import builtins

        from src.ui.views import page_today as P

        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "src.compute.macro.lamp_direction":
                raise ImportError("gone")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        dirs = P._load_lamp_directions()
        monkeypatch.setattr(builtins, "__import__", real_import)
        assert dirs == {}
        assert "L2 載入失敗" in capsys.readouterr().out
        band_label, thr_text, _, l4_err = P._load_l4_labels()
        tiles = _flat(P.build_indicator_tiles(_live_readout(), band_label=band_label,
                                              thr_text=thr_text, l4_error=l4_err,
                                              directions=dirs))
        for key in set(LAMP_DIRECTION_KEYS) - {"foreign_net"}:
            assert _dir_text(tiles, key) == f"計算失敗（{LAMP_DIRECTION_MISSING_REASON}）"
        assert _dir_text(tiles, "foreign_net") is None


class TestMissingKey:
    def test_missing_one_key_shows_error_not_dropped(self, capsys):
        from src.ui.views import page_today as P

        band_label, thr_text, _, l4_err = P._load_l4_labels()
        dirs = {k: v for k, v in _directions().items() if k != "ism_pmi"}
        tiles = _flat(P.build_indicator_tiles(_live_readout(), band_label=band_label,
                                              thr_text=thr_text, l4_error=l4_err,
                                              directions=dirs))
        assert "ism_pmi" in capsys.readouterr().out
        assert _dir_text(tiles, "ism_pmi") == "計算失敗（未回傳）"
        assert _dir_text(tiles, "margin").startswith("↗ 上升")
        assert _dir_text(tiles, "m1b_m2_gap") == "無資料"

    def test_none_value_treated_as_missing(self, capsys):
        from src.ui.views import page_today as P

        band_label, thr_text, _, l4_err = P._load_l4_labels()
        dirs = dict(_directions(), margin=None)
        tiles = _flat(P.build_indicator_tiles(_live_readout(), band_label=band_label,
                                              thr_text=thr_text, l4_error=l4_err,
                                              directions=dirs))
        assert "margin" in capsys.readouterr().out
        assert _dir_text(tiles, "margin") == "計算失敗（未回傳）"
        assert _ROW_SPAN in P.v2_card_html(tiles["detail.margin"])
        assert _dir_text(tiles, "ism_pmi").startswith("↘ 下降")

    def test_none_directions_still_no_row(self):
        # directions=None ＝ 呼叫端沒要這一列 ⇒ 仍然不出（既有行為）
        tiles = _build(_live_readout(), False)
        for key in LAMP_DIRECTION_KEYS:
            assert _dir_text(tiles, key) is None


@pytest.mark.parametrize("factory", [_cold_readout, _failed_readout],
                         ids=["cold_start", "failed"])
@pytest.mark.parametrize("dirs", [
    {k: error_direction(k, "RuntimeError") for k in LAMP_DIRECTION_KEYS},
    {},
], ids=["all_error", "all_missing"])
def test_not_live_never_shows_error_row(factory, dirs):
    from src.ui.views import page_today as P

    band_label, thr_text, _, l4_err = P._load_l4_labels()
    kw = dict(band_label=band_label, thr_text=thr_text, l4_error=l4_err)
    with_ = _flat(P.build_indicator_tiles(factory(), directions=dirs, **kw))
    without = _flat(P.build_indicator_tiles(factory(), **kw))
    for k, t in with_.items():
        assert all(f[0] != LAMP_DIRECTION_FACT_KEY for f in t.facts)
        assert t == without[k]
        assert P.v2_card_html(t) == P.v2_card_html(without[k])


# ════════════════════════════════════════════════════════════════
# 2026-09-26：vix / adl 序列取自本輪 session（經 L3 load_section_inputs）
# ════════════════════════════════════════════════════════════════
def _vix_block(values, current=None, dates=None):
    import pandas as pd

    dates = dates or [d.date().isoformat()
                      for d in pd.bdate_range(end="2026-09-25", periods=len(values))]
    return {"current": values[-1] if current is None else current,
            "dates": dates, "values": list(values)}


def _adl_df(ratios):
    import pandas as pd

    return pd.DataFrame({"date": pd.date_range("2026-07-01", periods=len(ratios), freq="B"),
                         "ad_ratio": ratios})


def _session(vix=None, adl=None):
    s = {}
    if vix is not None:
        s["macro_info"] = {"vix": vix}
    if adl is not None:
        s["cl_data"] = {"adl": adl}
    return s


class TestSessionSeries:
    def test_live_directions_from_session(self, monkeypatch):
        from src.ui.views import page_today as P

        _patch_loaders(monkeypatch)
        dirs = P._load_lamp_directions(_session(
            vix=_vix_block([20.0] * 40 + [26.0]),
            adl=_adl_df([50.0] * 40 + [44.0])))
        assert dirs["vix"].direction == "up"
        assert math.isclose(dirs["vix"].delta, 6.0)            # 26 − 20（往前第 20 列）
        assert dirs["vix"].as_of == "2026-09-25"
        # adl 有乾淨序列也不出箭頭（單日估算無自相關）
        assert dirs["adl"].direction == "nodata"

    def test_session_none_or_empty_is_nodata(self, monkeypatch):
        from src.ui.views import page_today as P

        _patch_loaders(monkeypatch)
        for sess in (None, {}):
            dirs = P._load_lamp_directions(sess)
            assert dirs["vix"].direction == "nodata"
            assert dirs["adl"].direction == "nodata"

    def test_vix_length_mismatch_is_nodata(self, monkeypatch, capsys):
        from src.ui.views import page_today as P

        _patch_loaders(monkeypatch)
        blk = _vix_block([20.0] * 30)
        blk["dates"] = blk["dates"][:-1]
        dirs = P._load_lamp_directions(_session(vix=blk))
        assert dirs["vix"].direction == "nodata"
        assert "dates 29 筆 ≠ values 30 筆" in capsys.readouterr().out

    def test_vix_series_not_matching_lamp_value_is_nodata(self, monkeypatch, capsys):
        # 序列末值 ≠ 燈值 ⇒ 不是同一次抓取，⛔ 不拿來配
        from src.ui.views import page_today as P

        _patch_loaders(monkeypatch)
        dirs = P._load_lamp_directions(_session(vix=_vix_block([20.0] * 30, current=31.0)))
        assert dirs["vix"].direction == "nodata"
        assert "不混抓取批次" in capsys.readouterr().out

    @pytest.mark.parametrize("bad", ["abc", None, [1]])
    def test_malformed_vix_value_only_fails_vix(self, monkeypatch, capsys, bad):
        # F2：一盞的值壞掉只讓那一盞計算失敗，⛔ 不連坐、⛔ 不補值
        from src.ui.views import page_today as P

        _patch_loaders(monkeypatch,
                       chart=lambda: {"margin": _daily([100.0] * 20 + [109.9]),
                                      "bias_240": _daily([5.0] * 20 + [5.5])},
                       monthly=lambda: {"ism_pmi": _monthly([50.0, 52.0])})
        blk = _vix_block([20.0] * 29 + [bad], current=20.0)
        dirs = P._load_lamp_directions(_session(vix=blk, adl=_adl_df([50.0] * 30)))
        assert "session 序列 vix" in capsys.readouterr().out
        assert {k for k, d in dirs.items() if d.direction == "error"} == {"vix"}
        assert dirs["vix"].delta is None
        assert dirs["adl"].direction == "nodata"
        assert dirs["margin"].direction == "up" and dirs["ism_pmi"].direction == "up"

    def test_nan_vix_end_is_nodata_not_filled(self, monkeypatch):
        from src.ui.views import page_today as P

        _patch_loaders(monkeypatch)
        dirs = P._load_lamp_directions(_session(
            vix=_vix_block([20.0] * 30 + [float("nan")], current=float("nan"))))
        assert dirs["vix"].direction == "nodata"

    def test_session_read_failure_only_hits_session_keys(self, monkeypatch, capsys):
        from src.services import section_inputs as SI
        from src.ui.views import page_today as P

        _patch_loaders(monkeypatch,
                       chart=lambda: {"margin": _daily([100.0] * 20 + [109.9]),
                                      "bias_240": _daily([5.0] * 20 + [5.5])},
                       monthly=lambda: {"ism_pmi": _monthly([50.0, 52.0])})
        monkeypatch.setattr(SI, "load_section_inputs", _boom)
        dirs = P._load_lamp_directions({"macro_info": {}})
        assert "session 序列" in capsys.readouterr().out
        assert {k for k, d in dirs.items() if d.direction == "error"} == {"vix", "ndc_signal"}
        assert dirs["adl"].direction == "nodata"
        assert format_direction_text(dirs["vix"]) == "計算失敗（RuntimeError）"
        assert dirs["margin"].direction == "up" and dirs["ism_pmi"].direction == "up"

    def test_does_not_mutate_session(self, monkeypatch):
        import copy

        from src.ui.views import page_today as P

        _patch_loaders(monkeypatch)
        blk = _vix_block([20.0] * 30)
        sess = _session(vix=blk)
        before = copy.deepcopy(sess)
        P._load_lamp_directions(sess)
        assert sess == before

    def test_render_page_passes_session(self):
        # 呼叫點一定要把本輪 session 傳下去（否則 vix / adl 永遠是無資料）
        import inspect

        from src.ui.views import page_today as P

        src = inspect.getsource(P.render_page_today)
        assert "directions=_load_lamp_directions(_session)" in src

    def test_live_card_texts_end_to_end(self, monkeypatch):
        from src.ui.views import page_today as P

        _patch_loaders(monkeypatch)
        dirs = P._load_lamp_directions(_session(
            vix=_vix_block([20.0] * 40 + [20.3]), adl=_adl_df([50.0] * 40 + [58.0])))
        band_label, thr_text, _, l4_err = P._load_l4_labels()
        tiles = _flat(P.build_indicator_tiles(_live_readout(), band_label=band_label,
                                              thr_text=thr_text, l4_error=l4_err,
                                              directions=dirs))
        assert _dir_text(tiles, "vix").startswith("→ 持平（近 20 交易日 +0.3 點")
        for k in ("adl", "dxy", "us10y", "jingqi", "fut_net", "health", "ndc_signal",
                  "us_core_cpi", "tw_export", "news_systemic", "m1b_m2_gap"):
            # ndc_signal：這個 session 沒帶 ndc_signal ⇒ 無資料（有帶的情形見 TestNdcSignal）
            assert _dir_text(tiles, k) == "無資料", k
        assert _dir_text(tiles, "foreign_net") is None


# ════════════════════════════════════════════════════════════════
# 2026-09-26：hover title 內的換行不得結束 HTML 區塊（margin degraded 卡外洩 bug）
# ════════════════════════════════════════════════════════════════
class TestHoverTitleNewline:
    def _margin_html(self):
        from src.ui.views import page_today as P

        band_label, thr_text, _, l4_err = P._load_l4_labels()
        tiles = _flat(P.build_indicator_tiles(_live_readout(), band_label=band_label,
                                              thr_text=thr_text, l4_error=l4_err,
                                              directions=_directions()))
        t = tiles["detail.margin"]
        assert t.card.state == P.UI_DEGRADED
        assert "\n\n" in (t.card.note.why or "")          # 前提：why 真的含空行
        return P.v2_card_html(t)

    def test_title_has_no_raw_newline(self):
        import re

        html = self._margin_html()
        m = re.match(r'<div title="([^"]*)">', html)
        assert m, html[:80]
        assert "\n" not in m.group(1)
        assert "&#10;&#10;" in m.group(1)                   # 換行保留成字元參照，沒被吃掉

    def test_single_html_block(self):
        # CommonMark：HTML 區塊遇到空行即結束 ⇒ 整張卡不得含空行
        html = self._margin_html()
        assert "\n\n" not in html
        assert not any(line.strip() == "" for line in html.split("\n")[1:-1])

    def test_markdown_render_keeps_card_inside_block(self):
        md = pytest.importorskip("markdown_it")
        html = self._margin_html()
        tokens = md.MarkdownIt("commonmark").parse(html)
        assert [t.type for t in tokens] == ["html_block"]


# ════════════════════════════════════════════════════════════════
# QA 補洞（2026-09-26）：vix 序列**存在但被拒**（長度不一 / 末值 ≠ 燈值 / 無燈值）
# ⇒ 使用者在卡面上看到的是「無資料」列 —— 釘住這個**畫面結果**。
#
# 既有 `TestSessionSeries` 只驗 `LampDirection.direction == "nodata"`，沒有走到卡面。
# 下面每組的序列若被「湊」進來（截斷 zip / 忽略燈值），都會算出 ↗ 上升 ——
# 所以卡面一旦出現箭頭或數值，就是回歸成「填了一個值」。
# ⚠️ **刻意不釘 L2 的 reason 字串**：現況被拒時 reason 寫「沒有歷史序列」，
#    但序列其實存在、只是被拒 —— 那句不精確（已上報，本批不改 src）。
#    釘它等於把不精確的措辭鎖死，故只釘使用者看得到的「無資料」。
# ════════════════════════════════════════════════════════════════
def _rejected_vix_blocks():
    base = [20.0] * 40 + [26.0]                  # 若被接受 ⇒ ↗ 上升 +6.0 點
    short_dates = _vix_block(base)
    short_dates["dates"] = short_dates["dates"][1:]           # 40 日期 vs 41 值
    long_dates = _vix_block(base)
    long_dates["values"] = long_dates["values"][1:]           # 41 日期 vs 40 值
    long_dates["current"] = 26.0
    return {
        "dates_shorter": short_dates,
        "values_shorter": long_dates,
        "end_value_not_lamp_value": _vix_block(base, current=31.0),
        "no_lamp_value": {**_vix_block(base), "current": None},
    }


class TestRejectedVixSeriesShowsNoDataOnCard:
    def _card(self, monkeypatch, blk):
        from src.ui.views import page_today as P

        _patch_loaders(monkeypatch)
        dirs = P._load_lamp_directions(_session(vix=blk))
        band_label, thr_text, _, l4_err = P._load_l4_labels()
        tiles = _flat(P.build_indicator_tiles(_live_readout(), band_label=band_label,
                                              thr_text=thr_text, l4_error=l4_err,
                                              directions=dirs))
        return dirs["vix"], tiles

    def test_control_an_accepted_series_does_show_an_arrow(self, monkeypatch):
        """對照組：同一組數值若被接受，卡面一定有箭頭（否則下面的「無資料」沒有鑑別力）。"""
        d, tiles = self._card(monkeypatch, _vix_block([20.0] * 40 + [26.0]))
        assert d.direction == "up"
        assert _dir_text(tiles, "vix").startswith("↗ 上升（近 20 交易日 +6.0 點")

    @pytest.mark.parametrize("case", sorted(_rejected_vix_blocks()))
    def test_rejected_series_is_a_no_data_row(self, monkeypatch, case):
        from src.ui.views import page_today as P

        d, tiles = self._card(monkeypatch, _rejected_vix_blocks()[case])
        assert d.direction == "nodata" and d.delta is None
        txt = _dir_text(tiles, "vix")
        assert txt == LAMP_DIRECTION_NODATA_TEXT == "無資料"
        assert not any(c in txt for c in "↗→↘0123456789")
        html = P.v2_card_html(tiles["detail.vix"])
        assert _ROW_SPAN in html, "被拒 ⛔ 不得讓整列消失（要誠實顯示無資料）"
        assert "↗" not in html and "↘" not in html

    @pytest.mark.parametrize("case", sorted(_rejected_vix_blocks()))
    def test_rejection_does_not_touch_the_lamp_itself(self, monkeypatch, case):
        """方向被拒只影響那一列；vix 的燈號 / 其他列與「沒給方向」時逐字相同（除方向列）。"""
        _, tiles = self._card(monkeypatch, _rejected_vix_blocks()[case])
        _, clean = self._card(monkeypatch, _vix_block([20.0] * 40 + [26.0]))
        strip = lambda t: [f for f in t.facts if f[0] != LAMP_DIRECTION_FACT_KEY]  # noqa: E731
        assert tiles["detail.vix"].card.state == clean["detail.vix"].card.state
        assert tiles["detail.vix"].signal_text == clean["detail.vix"].signal_text
        assert strip(tiles["detail.vix"]) == strip(clean["detail.vix"])


# ════════════════════════════════════════════════════════════════
# 2026-09-26 第二批：ndc_signal 真方向（整數官方分數，帶寬 0＝資料解析度）
# L1 additive（prev_score / prev_date）→ L5 session 抽取 → L2 較上月
# ════════════════════════════════════════════════════════════════
_NDC_EXISTING_KEYS = {"score", "signal", "date", "source"}


def _tbi_df(dates, scores, colors=None):
    import pandas as pd

    return pd.DataFrame({"date": dates, "monitoring": [float(x) for x in scores],
                         "monitoring_color": colors or ["綠燈"] * len(dates)})


def _zip_df(dates, scores, colors=None):
    import pandas as pd

    return pd.DataFrame({"date": dates, "value": scores,
                         "color": colors or ["綠燈"] * len(dates)})


def _call_ndc_block(monkeypatch, *, tbi=None, zdf=None, fetch_url=None):
    import src.data.macro.macro_snapshot as ms
    import src.data.macro.tw_macro as tw

    monkeypatch.setattr(tw, "fetch_business_indicator_series", lambda **_k: tbi)
    monkeypatch.setattr(tw, "_dgtw_ndc_signal_from_zip", lambda label="ndc_signal": zdf)
    if fetch_url is not None:
        # 同 test_ndc_official_zip_fallback：patch 真正持有者，不 patch PEP 562 轉發器
        monkeypatch.setattr("src.data.proxy.proxy_helper.fetch_url", fetch_url)
    ms.fetch_ndc_block.clear()
    try:
        return ms.fetch_ndc_block()
    finally:
        ms.fetch_ndc_block.clear()


class TestNdcSignalL1:
    def test_tbi_branch_carries_prev_month_additively(self, monkeypatch):
        out = _call_ndc_block(monkeypatch, tbi=_tbi_df(
            ["2026-06-01", "2026-07-01", "2026-08-01"], [30, 33.4, 36.6],
            ["黃藍燈", "綠燈", "黃紅燈"]))
        sig = out["ndc_signal"]
        # 既有鍵值逐字不變（與加鍵前的回傳相同）
        assert {k: sig[k] for k in _NDC_EXISTING_KEYS} == {
            "score": 37, "signal": "黃紅燈", "date": "2026-08-01",
            "source": "FinMind:TaiwanBusinessIndicator"}
        assert sig["prev_score"] == 33 and sig["prev_date"] == "2026-07-01"
        assert set(sig) == _NDC_EXISTING_KEYS | {"prev_score", "prev_date"}

    def test_zip_branch_carries_prev_month_additively(self, monkeypatch):
        out = _call_ndc_block(monkeypatch, zdf=_zip_df(
            ["2026-05-01", "2026-06-01"], [28, 31], ["黃藍燈", "綠燈"]))
        sig = out["ndc_signal"]
        assert {k: sig[k] for k in _NDC_EXISTING_KEYS} == {
            "score": 31, "signal": "綠燈", "date": "2026-06-01",
            "source": "data.gov.tw:6099(景氣指標及燈號)"}
        assert sig["prev_score"] == 28 and sig["prev_date"] == "2026-05-01"

    @pytest.mark.parametrize("dates", [["2026-05-01", "2026-08-01"],   # 中間缺月
                                       ["2025-08-01", "2026-08-01"]])  # 同月不同年
    def test_non_adjacent_months_carry_nothing(self, monkeypatch, dates):
        out = _call_ndc_block(monkeypatch, tbi=_tbi_df(dates, [30, 33]))
        sig = out["ndc_signal"]
        assert set(sig) == _NDC_EXISTING_KEYS and sig["score"] == 33

    @pytest.mark.parametrize("prev", [float("nan"), 50.0, 3.0])
    def test_bad_prev_row_carries_nothing(self, monkeypatch, prev):
        out = _call_ndc_block(monkeypatch, zdf=_zip_df(["2026-05-01", "2026-06-01"], [prev, 31]))
        assert set(out["ndc_signal"]) == _NDC_EXISTING_KEYS

    def test_single_row_carries_nothing(self, monkeypatch):
        out = _call_ndc_block(monkeypatch, zdf=_zip_df(["2026-06-01"], [31]))
        assert set(out["ndc_signal"]) == _NDC_EXISTING_KEYS

    def test_stockfeel_branch_carries_nothing(self, monkeypatch):
        html = "<html><body>2026 年 7 月 景氣對策信號 綜合分數 為 33 分</body></html>"

        class _R:
            status_code = 200
            text = html
            encoding = "utf-8"

        out = _call_ndc_block(monkeypatch, fetch_url=lambda *a, **k: _R())
        sig = out["ndc_signal"]
        assert sig["source"] == "StockFeel" and sig["score"] == 33
        assert "prev_score" not in sig and "prev_date" not in sig


class TestNdcSignalDirection:
    def _dirs(self, monkeypatch, ndc):
        from src.ui.views import page_today as P

        _patch_loaders(monkeypatch)
        return P._load_lamp_directions({"macro_info": {"ndc_signal": ndc}})

    def test_up_down_flat_with_band_zero(self, monkeypatch):
        base = {"signal": "綠燈", "source": "FinMind:TaiwanBusinessIndicator",
                "date": "2026-08-01", "prev_date": "2026-07-01", "prev_score": 33}
        for cur, exp, txt in ((34, "up", "↗ 上升（較上月 +1.0，至 2026-08-01）"),
                              (32, "down", "↘ 下降（較上月 -1.0，至 2026-08-01）"),
                              (33, "flat", "→ 持平（較上月 +0.0，至 2026-08-01）")):
            d = self._dirs(monkeypatch, {**base, "score": cur})["ndc_signal"]
            assert d.direction == exp, (cur, d)
            assert format_direction_text(d) == txt

    def test_last_point_is_the_lamp_value(self, monkeypatch):
        # 守衛：序列最新點就是燈值讀的那個 `score`（同一個 dict）
        from src.services.section_inputs import load_section_inputs
        from src.ui.views import page_today as P

        ndc = {"score": 36, "date": "2026-08-01", "prev_score": 35, "prev_date": "2026-07-01"}
        pts = P._session_ndc_series(load_section_inputs({"macro_info": {"ndc_signal": ndc}}))
        assert pts[-1] == ("2026-08-01", 36.0)
        assert pts[-1][1] == float(ndc["score"])

    @pytest.mark.parametrize("ndc", [
        {"score": 33, "date": "2026-08-01", "source": "StockFeel"},          # 單點分支
        {"score": 33, "date": "2026-08-01", "prev_score": 30},               # 缺 prev_date
        {"score": 33, "date": "2026-08-01", "prev_score": 30, "prev_date": "2026-05-01"},  # 缺月
        {"score": None, "date": "2026-08-01", "prev_score": 30, "prev_date": "2026-07-01"},
    ])
    def test_nodata_cases(self, monkeypatch, ndc):
        d = self._dirs(monkeypatch, ndc)["ndc_signal"]
        assert d.direction == "nodata" and format_direction_text(d) == LAMP_DIRECTION_NODATA_TEXT

    def test_malformed_prev_only_fails_ndc(self, monkeypatch):
        from src.ui.views import page_today as P

        _patch_loaders(monkeypatch)
        dirs = P._load_lamp_directions({"macro_info": {
            "ndc_signal": {"score": 33, "date": "2026-08-01",
                           "prev_score": "abc", "prev_date": "2026-07-01"},
            "vix": _vix_block([20.0] * 30 + [26.0])}})
        assert {k for k, d in dirs.items() if d.direction == "error"} == {"ndc_signal"}
        assert dirs["vix"].direction == "up"

    def test_card_row_end_to_end(self, monkeypatch):
        from src.ui.views import page_today as P

        dirs = self._dirs(monkeypatch, {"score": 36, "date": "2026-08-01",
                                        "prev_score": 33, "prev_date": "2026-07-01"})
        band_label, thr_text, _, l4_err = P._load_l4_labels()
        tiles = _flat(P.build_indicator_tiles(_live_readout(), band_label=band_label,
                                              thr_text=thr_text, l4_error=l4_err,
                                              directions=dirs))
        assert _dir_text(tiles, "ndc_signal") == "↗ 上升（較上月 +3.0，至 2026-08-01）"


# ── 2026-09-26 QA 追加：跨年相鄰（N1）與「燈值、方向同一個 dict」端到端（N2）──
class TestNdcSignalQaAdditions:
    @pytest.mark.parametrize("branch", ["tbi", "zip"])
    def test_dec_to_jan_is_adjacent(self, monkeypatch, branch):
        # N1：2025-12 → 2026-01 是相鄰月（跨年）；忽略年份只比月份的寫法會判成「不相鄰」
        dates, scores = ["2025-11-01", "2025-12-01", "2026-01-01"], [30, 32, 35]
        kw = ({"tbi": _tbi_df(dates, scores)} if branch == "tbi"
              else {"zdf": _zip_df(dates, scores)})
        sig = _call_ndc_block(monkeypatch, **kw)["ndc_signal"]
        assert sig["score"] == 35 and sig["date"] == "2026-01-01"
        assert sig["prev_score"] == 32 and sig["prev_date"] == "2025-12-01"
        # 而且 L2 的「較上月」也承認它（monthly 相鄰檢查同樣跨年）
        from src.ui.views import page_today as P

        _patch_loaders(monkeypatch)
        d = P._load_lamp_directions({"macro_info": {"ndc_signal": sig}})["ndc_signal"]
        assert d.direction == "up" and math.isclose(d.delta, 3.0)
        assert d.as_of == "2026-01-01"

    def test_lamp_value_and_direction_from_same_dict(self, monkeypatch):
        # N2：同一個 session、同一個 macro_info dict 同時餵燈值（真的 load_macro_readout
        #     → compute_five_bucket_summary）與方向（_load_lamp_directions）——
        #     卡上顯示的分數必須就是方向序列的最新點。
        from src.ui.views import page_today as P
        from src.services.section_inputs import load_section_inputs

        _patch_loaders(monkeypatch)
        ndc = {"score": 36, "signal": "黃紅燈", "date": "2026-01-01",
               "source": "FinMind:TaiwanBusinessIndicator",
               "prev_score": 33, "prev_date": "2025-12-01"}
        session = {"macro_info": {"ndc_signal": ndc}}
        readout = P.load_macro_readout(session)
        assert readout.requested and not readout.error
        lamp_value = readout.readiness["ndc_signal"]["value"]
        dirs = P._load_lamp_directions(session)
        d = dirs["ndc_signal"]
        pts = P._session_ndc_series(load_section_inputs(session))
        assert math.isclose(lamp_value, pts[-1][1]) and math.isclose(lamp_value, 36.0)
        assert d.as_of == pts[-1][0] == ndc["date"]
        assert math.isclose(d.delta, lamp_value - ndc["prev_score"])
        band_label, thr_text, _, l4_err = P._load_l4_labels()
        tiles = _flat(P.build_indicator_tiles(readout, band_label=band_label,
                                              thr_text=thr_text, l4_error=l4_err,
                                              directions=dirs))
        html = P.v2_card_html(tiles["detail.ndc_signal"])
        assert "36" in html
        assert _dir_text(tiles, "ndc_signal") == "↗ 上升（較上月 +3.0，至 2026-01-01）"
