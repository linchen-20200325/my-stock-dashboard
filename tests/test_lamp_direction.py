"""燈卡「變化方向」列（2026-09-24）。

守什麼：
- L0 `shared/lamp_direction_thresholds.py`：key 集合、持平帶、m1b 無帶寬。
- L2 `src/compute/macro/lamp_direction.py`：邊界（None / 空 / 單點 / 恰 n 點 /
  NaN / inf / 帶寬邊緣 / 舊值 ≤ 0 / 缺月 / 未知 key）與文字格式。
- L3 `macro_v2_service.get_monthly_history`：缺檔 → {}，NaN 列丟棄不補。
- L5 `page_today`：16 張燈卡裡只有 4 張出「變化方向」，且其餘 12 張、燈號、
  等級與不傳 directions 時**逐字相同**。
"""
from __future__ import annotations

import math

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
    def test_keys_exactly_four(self):
        assert set(LAMP_DIRECTION_KEYS) == {"margin", "bias_240", "m1b_m2_gap", "ism_pmi"}

    def test_keys_are_real_lamps(self):
        assert set(LAMP_DIRECTION_KEYS) <= set(SPECS_BY_KEY)

    def test_every_key_has_window(self):
        assert set(LAMP_DIRECTION_WINDOWS) == set(LAMP_DIRECTION_KEYS)

    def test_flat_band_values(self):
        assert LAMP_DIRECTION_FLAT_BAND == {"margin": 1.0, "bias_240": 1.0, "ism_pmi": 0.5}

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
            compute_lamp_direction("vix", _daily([1.0] * 30))

    def test_pmi_missing_month_is_nodata(self):
        pts = [("2026-05-01", 50.0), ("2026-07-01", 55.0)]
        assert compute_lamp_direction("ism_pmi", pts).direction == "nodata"

    def test_duplicate_dates_nodata(self):
        pts = [("2026-07-01", 50.0), ("2026-07-01", 55.0)]
        assert compute_lamp_direction("ism_pmi", pts).direction == "nodata"


class TestComputeDirection:
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


def _directions():
    return {
        "margin": compute_lamp_direction("margin", _daily([100.0] * 20 + [109.9])),
        "bias_240": compute_lamp_direction("bias_240", _daily([5.0] * 20 + [5.5])),
        "ism_pmi": compute_lamp_direction("ism_pmi", _monthly([50.0, 48.0])),
        "m1b_m2_gap": compute_lamp_direction("m1b_m2_gap", None),
        # 不在 LAMP_DIRECTION_KEYS 的 key 就算塞進來也不得出列
        "vix": LampDirection("up", 5.0, "%", "近 20 交易日", "2026-09-24"),
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

    def test_row_only_on_four_keys(self):
        P, _, with_ = self._both()
        assert len(with_) == 16
        has = {k.split(".", 1)[1] for k, t in with_.items()
               if any(f[0] == LAMP_DIRECTION_FACT_KEY for f in t.facts)}
        assert has == set(LAMP_DIRECTION_KEYS)
        for k, t in with_.items():
            html = P.v2_card_html(t)
            assert (_ROW_SPAN in html) == (k.split(".", 1)[1] in LAMP_DIRECTION_KEYS)

    def test_other_twelve_identical(self):
        P, without, with_ = self._both()
        others = [k for k in with_ if k.split(".", 1)[1] not in LAMP_DIRECTION_KEYS]
        assert len(others) == 12
        for k in others:
            assert with_[k] == without[k]
            assert P.v2_card_html(with_[k]) == P.v2_card_html(without[k])

    def test_band_level_state_unchanged(self):
        _, without, with_ = self._both()
        for k in with_:
            a, b = with_[k], without[k]
            assert (a.card, a.signal_text, a.signal_color) == (b.card, b.signal_text, b.signal_color)
            # 只多一列，其餘列順序與內容不變
            assert tuple(f for f in a.facts if f[0] != LAMP_DIRECTION_FACT_KEY) == b.facts

    def test_position(self):
        P, _, with_ = self._both()
        for key in LAMP_DIRECTION_KEYS:
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


def test_direction_on_foreign_key_rejected():
    from src.ui.views import page_today as P

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
            error_direction("vix", "RuntimeError")


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
        # m1b 不讀 L3 ⇒ 任何 loader 失敗都仍是「無資料」
        assert dirs["m1b_m2_gap"].direction == "nodata"
        for k in set(LAMP_DIRECTION_KEYS) - err_keys - {"m1b_m2_gap"}:
            assert dirs[k].direction in ("up", "flat", "down")

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
        others = [k for k in with_ if k.split(".", 1)[1] not in LAMP_DIRECTION_KEYS]
        assert len(others) == 12
        for k in others:
            assert with_[k] == without[k]
            assert P2.v2_card_html(with_[k]) == P2.v2_card_html(without[k])
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
        for key in LAMP_DIRECTION_KEYS:
            assert _dir_text(tiles, key) == f"計算失敗（{LAMP_DIRECTION_MISSING_REASON}）"


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
