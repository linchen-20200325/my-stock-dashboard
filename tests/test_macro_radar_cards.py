"""v18.317 — 🌍 全球風險桶 sparkline 小卡 helper 測試。

涵蓋:
1. _radar_threshold_lines SPEC 線 cut-off 與 risk_radar SSOT 常數同源（§3.3 反捏造）
2. delta/結構型燈無 natural level 線 → []
3. tuple 結構 (y, dash, color, txt) 不被破壞
4. _make_radar_sparkline 空/單筆 trend → None（不 raise）
5. _render_global_risk_bucket AppTest 守衛（key<30 字元 → 完全跳過）
"""
from __future__ import annotations

from unittest.mock import MagicMock

import risk_radar as rr
import tab_macro


class TestRadarThresholdLinesSSOT:
    """SPEC 線 cut-off 必須 == risk_radar 各 _signal_* 判讀用的同一組常數。"""

    def test_vix_level_matches_rr_constants(self):
        lines = tab_macro._radar_threshold_lines("vix_level")
        assert [lines[0][0], lines[1][0]] == [rr.VIX_WARN_LEVEL, rr.VIX_PANIC_LEVEL]

    def test_vix_term_matches_rr_constants(self):
        lines = tab_macro._radar_threshold_lines("vix_term_struct")
        assert [lines[0][0], lines[1][0]] == [rr.VIX_TERM_WARN, rr.VIX_TERM_PANIC]

    def test_move_matches_rr_constants(self):
        lines = tab_macro._radar_threshold_lines("move_level")
        assert [lines[0][0], lines[1][0]] == [rr.MOVE_WARN_LEVEL, rr.MOVE_PANIC_LEVEL]

    def test_pcr_matches_rr_constants(self):
        lines = tab_macro._radar_threshold_lines("put_call_ratio")
        assert [lines[0][0], lines[1][0]] == [rr.PCR_WARN, rr.PCR_PANIC]

    def test_delta_structural_keys_no_lines(self):
        """trend 所繪量 != 判讀量 的燈 → 不畫線（避免誤導）。"""
        for k in ("hy_oas_delta", "yield_10y_shock", "sox_drop",
                  "sector_rotation", "spx_trend_break", "asia_overnight",
                  "nonexistent"):
            assert tab_macro._radar_threshold_lines(k) == []

    def test_each_line_has_4_fields(self):
        for k in ("vix_level", "vix_term_struct", "move_level", "put_call_ratio"):
            for line in tab_macro._radar_threshold_lines(k):
                assert len(line) == 4
                _y, _dash, _color, _txt = line
                assert isinstance(_y, (int, float))
                assert _dash in ("dot", "dash", "solid")
                assert _color.startswith("#")
                assert _txt


class TestRadarSparklineEmpty:
    def test_empty_or_single_trend_returns_none(self):
        assert tab_macro._make_radar_sparkline([], "vix_level", "#fff") is None
        assert tab_macro._make_radar_sparkline(None, "vix_level", "#fff") is None
        assert tab_macro._make_radar_sparkline([1.0], "vix_level", "#fff") is None

    def test_valid_trend_returns_figure(self):
        fig = tab_macro._make_radar_sparkline([10.0, 12.0, 14.0], "vix_level", "#fff")
        assert fig is not None  # plotly Figure


class TestGlobalRiskBucketGuard:
    def test_short_key_skips_no_render(self, monkeypatch):
        """AppTest 守衛：key < 30 字元 → 直接 return，不渲染任何 markdown。"""
        fake = MagicMock()
        monkeypatch.setattr(tab_macro, "st", fake)
        tab_macro._render_global_risk_bucket("short", slow_verdict=None)
        fake.markdown.assert_not_called()

    def test_empty_key_skips(self, monkeypatch):
        fake = MagicMock()
        monkeypatch.setattr(tab_macro, "st", fake)
        tab_macro._render_global_risk_bucket("", slow_verdict=None)
        fake.markdown.assert_not_called()
