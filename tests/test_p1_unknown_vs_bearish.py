"""P1 v19.470 — 「不知道」與「壞消息」必須分開（§1 Fail Loud, Never Fake）。

背景（2026-08-19 四方交叉稽核）
--------------------------------
總經燈號卡出現 🔴「⛔ 大環境惡化，系統已啟動資金保護機制／禁止追買任何個股」
時，稽核發現全鏈路有 6 處把「資料沒拿到」靜默編碼成一個**合法的利空數值**：

    1. macro_helpers.calc_traffic_light   `_mkt.get('score', 0)`      → 大盤抓失敗 = 0 分
    2. macro_helpers.calc_traffic_light   `.get('net', 0)`            → 外資 net=None = 淨買賣 0
    3. market_strategy.market_regime      `foreign_buy == 0` 併入 None → 持平 = 沒抓到
    4. market_strategy.market_regime      `avg_vol_20 <= 0` → `else False` → 濾網靜默死亡
    5. market_strategy.market_score       `avg_volume <= 0` → `_vol_ratio = 1`（捏造量比）
    6. market_assessment_apply            `_foreign_net_loaded = 0`   → 缺值當觀測值

其中 (1) 最危險：`score=0` ⇒ `score_pct=0` ⇒ health 被硬拉低 40 分
⇒ 極易跌破 `HEALTH_DEFENSE_THRESHOLD` ⇒ 全站禁買令。而同一份
`shared/regime_arbiter.py` 對 `health=None` 早就有誠實的 `UNLOADED_VERDICT`
路徑 —— 防護原則本來就在，只是漏了 score 這條腿。

本檔釘住的不變量
----------------
**缺資料絕不可以讓結論比「有資料且數值中性」更悲觀。**
"""
import pandas as pd
import pytest

from src.compute.macro.macro_helpers import calc_traffic_light
from src.services.market_strategy import market_regime, market_score
from shared import regime_arbiter as RA


_JQ = {'avg': 49.28}          # 實測 2026-08-12~18 的 ad_ratio 五日均
_MKT_OK = {'score': 3.0, 'max_score': 4.0, 'regime': 'bull'}
_INST_OK = {'外資': {'net': -119.86}}


def _cl(inst):
    return {'inst': inst, 'adl': pd.DataFrame({'ad_ratio': [50.0]})}


# ══════════════════════════════════════════════════════════════
# (1) 大盤評分缺失 —— 最關鍵的一條
# ══════════════════════════════════════════════════════════════
class TestMissingMarketScore:

    def test_missing_mkt_info_must_not_produce_bear(self):
        """大盤整包沒抓到 → 不可判 🔴。

        修復前：`_mkt.get('score', 0)` ⇒ score_pct=0 ⇒
        health = 0.6×49.28 + 0.4×0 = 29.6 < 35 ⇒ 🔴 defense:health_below_threshold。
        修復後：score 這條腿缺席 ⇒ 權重歸一化 ⇒ health = 49.28 ⇒ 不觸發防禦。
        """
        tl = calc_traffic_light(None, _JQ, _cl(_INST_OK), None)
        assert tl is not None
        assert tl['regime_source'] != RA.SOURCE_DEFENSE_HEALTH, (
            '大盤資料缺失被判成「健康分跌破防禦門檻」—— 缺資料偽裝成利空')
        assert tl['effective_regime'] != 'bear'

    def test_missing_score_is_none_not_zero(self):
        tl = calc_traffic_light(None, _JQ, _cl(_INST_OK), None)
        assert tl['score'] is None, 'score 應為 None(沒拿到)，不可退回 0(=最低分)'

    def test_missing_score_renormalises_weights(self):
        """health 應等於 jqavg 本身（唯一剩下的分項），而非被 0 拉低。"""
        tl = calc_traffic_light(None, _JQ, _cl(_INST_OK), None)
        assert tl['health'] == pytest.approx(49.28, abs=0.05)
        assert tl['health_partial'] is True

    def test_both_legs_missing_returns_unloaded(self):
        """兩條腿都沒有 → ⬜ 總經未評估，不是 0 分也不是 🟡。"""
        tl = calc_traffic_light(None, None, _cl(_INST_OK), None)
        assert tl['health'] is None
        assert tl['regime_source'] == RA.SOURCE_UNLOADED
        assert tl['effective_regime'] == 'unknown'
        assert tl['light'] == RA.LIGHT_UNKNOWN

    def test_missing_score_cannot_trigger_futures_defense(self):
        """score 未知時，外資期貨防禦分支不得成立（需 score < 2 為**已知**）。"""
        li = pd.DataFrame({'外資大小': [-50000.0], '韭菜指數': [10.0]})
        tl = calc_traffic_light(None, _JQ, _cl(_INST_OK), li)
        assert tl['regime_source'] != RA.SOURCE_DEFENSE_FUTURES
        assert tl['defense'] is False


# ══════════════════════════════════════════════════════════════
# (2) 外資買賣超：None ≠ 0
# ══════════════════════════════════════════════════════════════
class TestForeignNetTriState:

    def test_key_present_but_net_none_counts_as_missing(self):
        """key 在、net 為 None → 信心必須扣分（修復前顯示 100% 卻同時說「待更新」）。"""
        tl = calc_traffic_light(_MKT_OK, _JQ, _cl({'外資': {'net': None}}), None)
        assert tl['fnet'] is None
        assert '外資買賣超 (三大法人)' in tl['missing_sources']
        assert tl['conf'] < 100

    def test_real_zero_is_not_missing(self):
        """真的買賣相抵(0) 是**已知**觀測值 → 不可列為缺失。"""
        tl = calc_traffic_light(_MKT_OK, _JQ, _cl({'外資': {'net': 0.0}}), None)
        assert tl['fnet'] == 0.0
        assert '外資買賣超 (三大法人)' not in tl['missing_sources']

    def test_market_regime_distinguishes_zero_from_none(self):
        r_none = market_regime(100, 90, 80, None)
        r_zero = market_regime(100, 90, 80, 0)
        assert any('待更新' in s for s in r_none['signals'])
        assert any('相抵' in s for s in r_zero['signals'])
        assert r_none['score'] == r_zero['score']   # 兩者都不加分，行為零位移


# ══════════════════════════════════════════════════════════════
# (3) 成交量缺失不得靜默
# ══════════════════════════════════════════════════════════════
class TestVolumeMissing:

    def test_zero_volume_is_disclosed_not_swallowed(self):
        """^TWII 自 2026-07-09 起 volume 全 0 → 濾網未評估必須說出來。"""
        r = market_regime(100, 90, 80, 1e9, vol_today=0, avg_vol_20=0)
        assert r['bullrun'] is False
        assert any('成交量資料缺失' in s for s in r['signals'])

    def test_market_score_does_not_fabricate_vol_ratio(self):
        """舊碼 `else 1` 憑空生出「量比 1.0x」。"""
        r = market_score(100, 90, 1e9, volume=0, avg_volume=0)
        assert not any('1.0x' in s for s in r['signals'])
        assert any('成交量資料缺失' in s for s in r['signals'])

    def test_market_score_handles_none_foreign(self):
        r = market_score(100, 90, None, volume=100, avg_volume=50)
        assert any('待更新' in s for s in r['signals'])


# ══════════════════════════════════════════════════════════════
# (4) 核心不變量：缺資料不得比中性資料更悲觀
# ══════════════════════════════════════════════════════════════
def test_invariant_unknown_never_worse_than_neutral():
    """對每一條輸入腿：拿掉它，結論不可以比「有值且中性」更空。"""
    _RANK = {'bull': 2, 'neutral': 1, 'unknown': 1, 'caution': 0, 'bear': 0}
    base = calc_traffic_light(_MKT_OK, _JQ, _cl(_INST_OK), None)
    variants = {
        'mkt_info 缺':  calc_traffic_light(None, _JQ, _cl(_INST_OK), None),
        '外資 net 缺':  calc_traffic_light(_MKT_OK, _JQ, _cl({'外資': {'net': None}}), None),
        'inst 整包缺':  calc_traffic_light(_MKT_OK, _JQ, _cl(None), None),
    }
    for name, tl in variants.items():
        assert _RANK[tl['effective_regime']] >= _RANK[base['effective_regime']], (
            f'{name} 後結論變得比原本更空 —— 缺資料被當成利空訊號')
