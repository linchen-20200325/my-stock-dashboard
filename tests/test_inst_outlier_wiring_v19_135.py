# -*- coding: utf-8 -*-
"""tests/test_inst_outlier_wiring_v19_135.py — §3.2 三大法人單日爆量 wiring(v19.135)。

helper `is_inst_net_outlier` 早已落地(v18.299,test_inst_sanity.py 15 測),但
**0 production caller**。v19.135 新增 L2 adapter `flag_latest_inst_outlier_from_df`
(從個股 K 線 df 取最新一日 主力合計 + 30 日均量 → 呼 helper),wire 進
section_chips_20d 的 signal banner 顯示徽章。

單位(§4.1):主力合計 與 volume 皆「張」→ ratio 無量綱,張/張 == 股/股。
嚴格 window(§4.6):不足 30 日有效量 → vol_unavailable,不誤報。

三個最容易出錯的輸入(§6):
1. **最新一日缺欄/缺值**(法人資料當天沒抓到)→ 不可用舊值冒充,回 inst_net_zero。
2. **資料不足 30 日**(新上市)/ window 內有 NaN → vol_unavailable,不誤報。
3. **賣超(負值)**→ 取絕對值判倍數(大額賣超也是爆量)。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.compute.risk import flag_latest_inst_outlier_from_df, InstNetSanityResult
from shared.signal_thresholds import INST_NET_OUTLIER_VOLUME_RATIO

REPO = Path(__file__).resolve().parent.parent


def _mk_df(inst_latest, vols, main_rest=0.0, inst_col='主力合計', vol_col='volume'):
    """建個股 K 線樣本:最後一列 主力合計=inst_latest,其餘=main_rest;volume=vols。"""
    n = len(vols)
    main = [main_rest] * (n - 1) + [inst_latest]
    idx = pd.date_range(end='2026-07-18', periods=n, freq='B')
    return pd.DataFrame({inst_col: main, vol_col: vols}, index=idx)


# ══════════════════════════════════════════════════════════════
# 正常判定
# ══════════════════════════════════════════════════════════════
class TestOutlierDetection:
    def test_outlier_flagged(self):
        """最新日主力合計 600 張 vs 30 日均量 100 張 → ratio 6.0 > 5 → outlier。"""
        df = _mk_df(600, [100] * 30)
        r = flag_latest_inst_outlier_from_df(df)
        assert isinstance(r, InstNetSanityResult)
        assert r.is_outlier is True
        assert abs(r.ratio - 6.0) < 1e-9
        assert r.reason == 'outlier'

    def test_not_outlier(self):
        """200 vs 100 → ratio 2.0 < 5 → ok。"""
        r = flag_latest_inst_outlier_from_df(_mk_df(200, [100] * 30))
        assert r.is_outlier is False and r.reason == 'ok'
        assert abs(r.ratio - 2.0) < 1e-9

    def test_sell_outlier_uses_abs(self):
        """易錯輸入 3:賣超 -600 → |−600|/100 = 6 → outlier(絕對值)。"""
        r = flag_latest_inst_outlier_from_df(_mk_df(-600, [100] * 30))
        assert r.is_outlier is True and abs(r.ratio - 6.0) < 1e-9

    def test_golden_uneven_volume(self):
        """GOLDEN:主力合計 750,volume=[100]×29+[200] → 均量=(2900+200)/30=103.33,
        ratio=750/103.33=7.258 → outlier。"""
        df = _mk_df(750, [100] * 29 + [200])
        r = flag_latest_inst_outlier_from_df(df)
        assert abs(r.ratio - 750 / (3100 / 30)) < 1e-9
        assert r.is_outlier is True

    def test_custom_threshold(self):
        """threshold=3 → ratio 4.0(400/100)變 outlier(SSOT 預設 5 則否)。"""
        df = _mk_df(400, [100] * 30)
        assert flag_latest_inst_outlier_from_df(df).is_outlier is False           # 預設 5×
        assert flag_latest_inst_outlier_from_df(df, threshold_ratio=3.0).is_outlier is True


# ══════════════════════════════════════════════════════════════
# 降級(fail-soft,不炸 UI)
# ══════════════════════════════════════════════════════════════
class TestDegradation:
    def test_insufficient_history(self):
        """易錯輸入 2:不足 30 列(新上市)→ vol_unavailable,不誤報。"""
        r = flag_latest_inst_outlier_from_df(_mk_df(9999, [100] * 20))   # 極大 net 也不報
        assert r.is_outlier is False and r.reason == 'vol_unavailable' and r.ratio is None

    def test_nan_in_volume_window(self):
        """window 內任一 NaN 量 → 嚴格模式視為不足 → vol_unavailable。"""
        vols = [100] * 15 + [np.nan] + [100] * 15   # 31 列,tail(30) 含 1 NaN
        r = flag_latest_inst_outlier_from_df(_mk_df(9999, vols))
        assert r.reason == 'vol_unavailable'

    def test_exactly_30_valid_ok(self):
        """剛好 30 列有效 → 可判定(邊界)。"""
        r = flag_latest_inst_outlier_from_df(_mk_df(600, [100] * 30))
        assert r.reason == 'outlier'

    def test_missing_inst_column(self):
        """缺 主力合計 欄 → fail-soft vol_unavailable(不 KeyError)。"""
        df = pd.DataFrame({'volume': [100] * 30})
        assert flag_latest_inst_outlier_from_df(df).reason == 'vol_unavailable'

    def test_missing_volume_column(self):
        df = pd.DataFrame({'主力合計': [100] * 30})
        assert flag_latest_inst_outlier_from_df(df).reason == 'vol_unavailable'

    def test_latest_inst_net_nan(self):
        """易錯輸入 1:最新一日主力合計 NaN → 不用舊值冒充 → inst_net_zero。"""
        df = _mk_df(np.nan, [100] * 30, main_rest=500)   # 前 29 日有值,最新日 NaN
        assert flag_latest_inst_outlier_from_df(df).reason == 'inst_net_zero'

    def test_none_and_empty(self):
        assert flag_latest_inst_outlier_from_df(None).reason == 'vol_unavailable'
        assert flag_latest_inst_outlier_from_df(
            pd.DataFrame({'主力合計': [], 'volume': []})).reason == 'vol_unavailable'


# ══════════════════════════════════════════════════════════════
# Property:單位無量綱(§4.1 張/張 == 股/股)
# ══════════════════════════════════════════════════════════════
class TestUnitInvariance:
    def test_ratio_scale_invariant(self):
        """主力合計 與 volume 同乘 1000(張→股)→ ratio 不變(無需換價)。"""
        df_lots = _mk_df(600, [100] * 30)
        df_shares = _mk_df(600_000, [100_000] * 30)
        r1 = flag_latest_inst_outlier_from_df(df_lots)
        r2 = flag_latest_inst_outlier_from_df(df_shares)
        assert abs(r1.ratio - r2.ratio) < 1e-9
        assert r1.is_outlier == r2.is_outlier


# ══════════════════════════════════════════════════════════════
# Wiring source-scan(釘住 UI 接線)
# ══════════════════════════════════════════════════════════════
class TestWiringPinned:
    def test_ssot_threshold_used(self):
        """adapter 預設門檻 = SSOT(不 inline)。"""
        # 5.0× 剛好不觸發(> 才算),5.01× 觸發 → 證明用 SSOT 值
        base = 100
        just_under = _mk_df(base * INST_NET_OUTLIER_VOLUME_RATIO, [base] * 30)       # ==5× → 不算
        just_over = _mk_df(base * INST_NET_OUTLIER_VOLUME_RATIO + 1, [base] * 30)    # >5× → 算
        assert flag_latest_inst_outlier_from_df(just_under).is_outlier is False
        assert flag_latest_inst_outlier_from_df(just_over).is_outlier is True

    def test_ui_section_wires_adapter(self):
        src = (REPO / 'src/ui/tabs/stock_sections/section_chips_20d.py').read_text(encoding='utf-8')
        assert 'flag_latest_inst_outlier_from_df' in src, 'UI 未接 adapter'
        assert '三大法人單日爆量' in src, '徽章文案缺失'
        assert '_inst_flag.is_outlier' in src, '未依 is_outlier 條件顯示'
