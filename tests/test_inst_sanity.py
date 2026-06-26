"""tests/test_inst_sanity.py — §3.2 三大法人 sanity 守(v18.299)

CLAUDE.md §3.2:|inst_net_shares| > 30D 均量 × 5 → outlier 旗標。
本檔守 inst_sanity.is_inst_net_outlier / flag_inst_net_outliers_batch 行為。
"""
from __future__ import annotations

import pytest

from inst_sanity import (
    is_inst_net_outlier,
    flag_inst_net_outliers_batch,
    InstNetSanityResult,
)
from shared.signal_thresholds import INST_NET_OUTLIER_VOLUME_RATIO


# ════════════════════════════════════════════════════════════════
# 1. SSOT threshold
# ════════════════════════════════════════════════════════════════
class TestSSotThreshold:
    def test_threshold_is_5x(self):
        """§3.2 default 5x SSOT。任何改動都要更新 CLAUDE.md。"""
        assert INST_NET_OUTLIER_VOLUME_RATIO == 5.0


# ════════════════════════════════════════════════════════════════
# 2. 正向 detection
# ════════════════════════════════════════════════════════════════
class TestOutlierDetection:
    def test_exactly_at_threshold_not_outlier(self):
        """ratio == 5.0 邊界:**不**標 outlier(> 5x 才異常)。"""
        r = is_inst_net_outlier(500_000, 100_000)
        assert r.ratio == 5.0
        assert not r.is_outlier
        assert r.reason == 'ok'

    def test_above_threshold_is_outlier(self):
        r = is_inst_net_outlier(1_000_000, 100_000)
        assert r.ratio == 10.0
        assert r.is_outlier
        assert r.reason == 'outlier'

    def test_negative_inst_net_above_threshold(self):
        """賣超(負值)|abs| > 5x → outlier。"""
        r = is_inst_net_outlier(-2_000_000, 100_000)
        assert r.is_outlier
        assert r.ratio == 20.0

    def test_normal_within_threshold(self):
        r = is_inst_net_outlier(50_000, 100_000)
        assert not r.is_outlier
        assert r.ratio == 0.5
        assert r.reason == 'ok'


# ════════════════════════════════════════════════════════════════
# 3. 缺值處理(§1 Fail Loud:無法判定 ≠ 確認異常)
# ════════════════════════════════════════════════════════════════
class TestMissingValues:
    def test_inst_net_none(self):
        r = is_inst_net_outlier(None, 100_000)
        assert not r.is_outlier
        assert r.ratio is None
        assert r.reason == 'inst_net_zero'

    def test_inst_net_zero(self):
        r = is_inst_net_outlier(0, 100_000)
        assert not r.is_outlier
        assert r.ratio == 0.0
        assert r.reason == 'inst_net_zero'

    def test_vol_none(self):
        r = is_inst_net_outlier(1_000_000, None)
        assert not r.is_outlier
        assert r.ratio is None
        assert r.reason == 'vol_unavailable'

    def test_vol_zero(self):
        """vol 0 → 無法 ratio(避免 ZeroDivisionError + 偽陽 outlier)。"""
        r = is_inst_net_outlier(1_000_000, 0)
        assert not r.is_outlier
        assert r.ratio is None
        assert r.reason == 'vol_unavailable'

    def test_vol_negative(self):
        """vol < 0 異常(資料錯)→ 無法判定。"""
        r = is_inst_net_outlier(1_000_000, -100)
        assert not r.is_outlier
        assert r.ratio is None
        assert r.reason == 'vol_unavailable'


# ════════════════════════════════════════════════════════════════
# 4. 可調 threshold
# ════════════════════════════════════════════════════════════════
class TestCustomThreshold:
    def test_lower_threshold(self):
        """放寬到 3× → 4x 均量已 outlier。"""
        r = is_inst_net_outlier(400_000, 100_000, threshold_ratio=3.0)
        assert r.is_outlier
        assert r.ratio == 4.0

    def test_higher_threshold(self):
        """收緊到 10× → 8x 不 outlier。"""
        r = is_inst_net_outlier(800_000, 100_000, threshold_ratio=10.0)
        assert not r.is_outlier


# ════════════════════════════════════════════════════════════════
# 5. Batch 介面
# ════════════════════════════════════════════════════════════════
class TestBatchFlag:
    def test_batch_mixed(self):
        nets = [50_000, None, 800_000, 0, -1_500_000]
        results = flag_inst_net_outliers_batch(nets, 100_000)
        assert len(results) == 5
        assert results[0].reason == 'ok'           # 0.5x
        assert results[1].reason == 'inst_net_zero'
        assert results[2].is_outlier               # 8x outlier
        assert results[3].reason == 'inst_net_zero'
        assert results[4].is_outlier               # 15x outlier(賣超)

    def test_batch_empty(self):
        assert flag_inst_net_outliers_batch([], 100_000) == []

    def test_batch_vol_unavailable(self):
        """整批 vol_30d_avg 缺 → 全 vol_unavailable。"""
        results = flag_inst_net_outliers_batch([500_000, 1_000_000], None)
        assert all(r.reason == 'vol_unavailable' for r in results)
        assert all(not r.is_outlier for r in results)
