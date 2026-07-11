# -*- coding: utf-8 -*-
"""v19.95 — 批次3(a) 布林突破量能確認（§7 user 核准:加 vol_ratio gate）。

detect_bollinger_breakout 原 docstring 聲明吃 volume 但從未用。改:
- vol_ratio = 今量 / 20 日均量(mirror check_fake_breakout;SSOT VOLUME_RATIO_SURGE=1.5)
- near_upper 且 bw>3:有量 → 🔴 突破爆發(量增);量不足 → 🟡 突破待確認(防假突破);
  量未知(缺 volume 欄) → 維持舊 🔴(誠實標「量能未知」,不偽造 1.0)
- dict 加 vol_ratio / volume_confirmed(schema-additive)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from shared.signal_thresholds import VOLUME_RATIO_SURGE
from src.compute.strategy.v5_modules import detect_bollinger_breakout


def _breakout_df(last_vol_mult: float | None = 3.0, n: int = 60):
    """造「貼近上軌 + bw>3」的序列:前段震盪(撐開 std)+末段強拉。

    last_vol_mult: 最後一根量 = 均量 × 此倍數;None = 不給 volume 欄。
    """
    rng = np.random.default_rng(7)
    base = 100 + np.sin(np.arange(n - 6)) * 2 + rng.normal(0, 0.5, n - 6)
    tail = np.linspace(base[-1], base[-1] * 1.12, 6)        # 末 6 根強拉 → 貼上軌
    close = np.concatenate([base, tail])
    df = pd.DataFrame({"close": close})
    if last_vol_mult is not None:
        vol = np.full(len(close), 1_000_000.0)
        vol[-1] = 1_000_000.0 * last_vol_mult
        df["volume"] = vol
    return df


class TestVolumeGate:
    def test_confirmed_breakout_red_with_ratio(self):
        r = detect_bollinger_breakout(_breakout_df(last_vol_mult=3.0))
        assert r["near_upper"] is True and r["bw"] > 3        # 前提成立
        assert r["volume_confirmed"] is True
        assert r["vol_ratio"] >= VOLUME_RATIO_SURGE
        assert "🔴" in r["signal"] and "量增" in r["msg"]

    def test_low_volume_downgrades_to_yellow(self):
        r = detect_bollinger_breakout(_breakout_df(last_vol_mult=0.5))
        assert r["near_upper"] is True and r["bw"] > 3
        assert r["volume_confirmed"] is False
        assert r["signal"] == "🟡 布林突破待確認"
        assert "假突破" in r["msg"]

    def test_missing_volume_keeps_old_red_labeled_unknown(self):
        # 缺 volume 欄 → vol_ratio=None(誠實未知,不偽造)→ 維持舊 🔴 行為 + 標註
        r = detect_bollinger_breakout(_breakout_df(last_vol_mult=None))
        assert r["vol_ratio"] is None
        assert r["volume_confirmed"] is False
        assert "🔴" in r["signal"] and "量能未知" in r["msg"]

    def test_non_breakout_paths_untouched(self):
        # 平盤(不貼上軌) → ⚪/🟡 原路徑不受量能 gate 影響
        df = pd.DataFrame({"close": [100.0 + np.sin(i) for i in range(60)],
                           "volume": [1e6] * 60})
        r = detect_bollinger_breakout(df)
        assert "突破" not in r["signal"]

    def test_output_schema_additive(self):
        r = detect_bollinger_breakout(_breakout_df())
        for key in ("bw", "bw_pct", "upper", "lower", "ma", "close",
                    "near_upper", "vol_ratio", "volume_confirmed",
                    "signal", "color", "msg"):
            assert key in r

    def test_zero_volume_series_not_confirmed(self):
        # 全 0 量(停牌資料) → 均量 0 → vol_ratio=None → 不確認(不除零)
        df = _breakout_df(last_vol_mult=1.0)
        df["volume"] = 0.0
        r = detect_bollinger_breakout(df)
        assert r["vol_ratio"] is None
        assert r["volume_confirmed"] is False


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
