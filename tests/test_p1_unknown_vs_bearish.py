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
import pathlib

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
        """^TWII 自 2026-07-09 起 volume 連續 33 個交易日為 0 → 濾網未評估必須說出來。

        2026-08-27 更正:2026-08-26 起 streak 中斷（真量回來），但零星單日 0 仍會間歇出現（2019/2022/2024/2025 皆有前例，全檔 41 筆）→ 仍不可信，不畫的理由不變。
        """
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
# (3b) 假 0 混入均量 → **假瘋牛**（2026-08-27 新增：本檔原本的覆蓋缺口）
#
# 原 TestVolumeMissing 只釘了 `vol_today=0, avg_vol_20=0` 這一種組合 ——
# 也就是「全部都缺」。**真正在畫面上出事的是「大部分缺、一筆真」的混合情境**：
#   實測 data_cache/twii_ohlcv.parquet（量測日 2026-08-27）
#     · 全檔 41 筆 volume == 0，41/41 都 high > low（價格有波動 ⇒ 必有成交）
#     · 2026-07-09~08-25 連續 33 個交易日為 0
#     · 2026-08-26 真量 4,026,600 回來 → streak 中斷
#   → 近 20 日 = 19 個假 0 + 1 個真量
#   → rolling(20).mean() = 4,026,600 / 20 = 201,330
#   → 量比 = 4,026,600 / 201,330 = 20.0x > 門檻 1.3
#   → 畫面把誠實的「⬜ 成交量資料缺失」換成「💹 瘋牛模式：成交量 20.0x 均量」，
#     而且會持續約 19 個交易日直到假 0 滾出視窗。
# ══════════════════════════════════════════════════════════════
class TestFakeZeroVolumeDilutesAverage:

    _REAL_VOL = 4_026_600.0    # 2026-08-26 實測真量

    @staticmethod
    def _df(volumes, *, with_volume_col=True):
        """造一段夠長（>=120 bar，過 MA120 門檻）且**日期夠新**的日 K。

        價格用單調微升，讓 regime 落在 bull —— 本檔關心的是量能腿，
        其他腿保持穩定才不會把斷言的失敗原因混在一起。
        """
        n = 200
        idx = pd.bdate_range(end=pd.Timestamp.now().normalize(), periods=n)
        close = pd.Series([100.0 + i * 0.1 for i in range(n)], index=idx)
        vols = [3_000_000.0] * (n - len(volumes)) + list(volumes)
        data = {'open': close, 'high': close * 1.01, 'low': close * 0.99, 'close': close}
        if with_volume_col:
            data['volume'] = pd.Series(vols, index=idx)
        return pd.DataFrame(data, index=idx)

    def test_19_fake_zeros_plus_1_real_must_not_fire_bullrun(self):
        """**本輪的核心迴歸**：19 個假 0 + 1 個真量 ≠ 瘋牛。"""
        from src.services.market_strategy import get_market_assessment
        df = self._df([0.0] * 19 + [self._REAL_VOL])
        r = get_market_assessment(df_index=df, foreign_net=1e9)
        assert r is not None
        assert r['bullrun'] is False, '假 0 稀釋均量後不得判成瘋牛'
        # ⚠️ 誠實文案「⬜ 成交量資料缺失（瘋牛濾網未評估）」本身就含「瘋牛」二字，
        #    所以這裡認的是**訊號本體**「瘋牛模式」，不是子字串「瘋牛」。
        assert not any('瘋牛模式' in s for s in r['signals']), \
            f'送出了假瘋牛訊號：{r["signals"]}'
        assert any('成交量資料缺失' in s for s in r['signals']), \
            f'缺值必須誠實說出來，實得：{r["signals"]}'

    def test_the_exact_arithmetic_that_produced_20x(self):
        """把舊行為的算式釘死，證明這條測試守的是真的東西（不是恆真斷言）。

        舊碼 `rolling(20).mean()` 對同一段輸入會得到 201,330 → 20.0x。
        """
        vols = pd.Series([0.0] * 19 + [self._REAL_VOL])
        naive_avg = float(vols.rolling(20).mean().iloc[-1])
        assert naive_avg == pytest.approx(201_330.0)
        assert self._REAL_VOL / naive_avg == pytest.approx(20.0)

    def test_stats_helper_excludes_zeros_and_reports_none(self):
        from src.services.market_strategy import volume_window_stats
        df = self._df([0.0] * 19 + [self._REAL_VOL])
        assert volume_window_stats(df.rename(columns=str.title)) == (None, None)

    def test_a_few_scattered_zeros_still_compute_honestly(self):
        """反向守衛：零星缺值不該把整條濾網關掉（否則就是矯枉過正）。

        18 個真量 + 2 個假 0 → 有效樣本 18 >= 門檻 15 → 照算，
        且均量必須是**18 筆的平均**，不是「除以 20」。
        """
        from src.services.market_strategy import volume_window_stats
        vols = [0.0, 0.0] + [1_000_000.0] * 18
        df = self._df(vols).rename(columns=str.title)
        avg, today = volume_window_stats(df)
        assert avg == pytest.approx(1_000_000.0), '假 0 不得進分母'
        assert today == pytest.approx(1_000_000.0)

    def test_no_volume_column_must_not_fabricate_1000(self):
        """舊碼 `else 1000` / `else avg_vol` 憑空生出一組觀測（§1 明禁）。"""
        from src.services.market_strategy import volume_window_stats, get_market_assessment
        df = self._df([], with_volume_col=False)
        assert volume_window_stats(df.rename(columns=str.title)) == (None, None)
        r = get_market_assessment(df_index=df, foreign_net=1e9)
        assert r is not None
        assert r['bullrun'] is False
        assert any('成交量資料缺失' in s for s in r['signals'])
        assert not any('1000' in s or '1.0x' in s for s in r['signals'])

    def test_all_real_volume_still_fires_bullrun(self):
        """再一道反向守衛：資料健康時瘋牛**要**照樣點得起來。

        沒有這條，上面那些測試可以靠「永遠回 False」全部作弊通過。
        """
        from src.services.market_strategy import get_market_assessment
        df = self._df([1_000_000.0] * 19 + [5_000_000.0])
        r = get_market_assessment(df_index=df, foreign_net=1e9)
        assert r is not None
        assert r['bullrun'] is True
        assert any('瘋牛模式' in s for s in r['signals'])

    def test_threshold_comes_from_ssot_not_inline_literal(self):
        """§3.3：`BULLRUN_VOL_THRESHOLD` 原本是 0 consumer 的死 SSOT。"""
        import src.services.market_strategy as MS
        from src.config import BULLRUN_VOL_THRESHOLD
        assert MS.BULLRUN_VOL_THRESHOLD == BULLRUN_VOL_THRESHOLD
        src = pathlib.Path('src/services/market_strategy.py').read_text(encoding='utf-8')
        assert 'avg_vol_20 * BULLRUN_VOL_THRESHOLD' in src, \
            '瘋牛門檻必須引 SSOT，不得寫回 inline 1.3'


class TestTwiiVolumeSanityGates:
    """資料層 + schema 層：假 0 不該再被寫進 parquet / 不該再對守衛隱形。"""

    def test_schema_rejects_zero_volume_when_price_moved(self):
        from shared.schemas import OHLCVSchema, try_validate, PANDERA_AVAILABLE
        if not PANDERA_AVAILABLE:
            pytest.skip('pandera 未安裝')
        bad = pd.DataFrame({'open': [1.0], 'high': [2.0], 'low': [0.5],
                            'close': [1.5], 'volume': pd.Series([0], dtype='int64')})
        _, errors = try_validate(bad, OHLCVSchema)
        assert errors, 'volume==0 且 high>low 是物理上不可能的觀測，schema 必須看得見'

    def test_schema_still_allows_flat_bar_with_zero_volume(self):
        """§4.6「跌停 0 vol：有 close 但 vol=0 → 視為有效報價」不得被誤殺。"""
        from shared.schemas import OHLCVSchema, try_validate, PANDERA_AVAILABLE
        if not PANDERA_AVAILABLE:
            pytest.skip('pandera 未安裝')
        flat = pd.DataFrame({'open': [1.0], 'high': [1.0], 'low': [1.0],
                             'close': [1.0], 'volume': pd.Series([0], dtype='int64')})
        _, errors = try_validate(flat, OHLCVSchema)
        assert not errors, f'整日無成交（high==low）是有效報價，不該被擋：{errors}'

    def test_cron_marks_impossible_zero_as_nan(self, monkeypatch):
        """`fetch_twii_ohlcv` 落地前要把「價格有動但量為 0」標成 NaN，不寫 0。"""
        import datetime as _dt
        import scripts.update_macro_history as U

        class _R:
            status_code = 200

            @staticmethod
            def json():
                ts = [int(_dt.datetime(2026, 7, d).timestamp()) for d in (9, 10, 13)]
                return {'chart': {'result': [{
                    'timestamp': ts,
                    'indicators': {'quote': [{
                        'open':  [100.0, 101.0, 102.0],
                        'high':  [103.0, 101.0, 104.0],   # 第 2 筆 high==low(整日無成交)
                        'low':   [ 99.0, 101.0, 101.0],
                        'close': [102.0, 101.0, 103.0],
                        'volume': [0, 0, 5_000_000],
                    }]},
                }]}}

        monkeypatch.setattr(U, '_fetch_url_via_proxy', lambda *a, **k: _R())
        out = U.fetch_twii_ohlcv(_dt.date(2026, 7, 9), _dt.date(2026, 7, 13))
        assert len(out) == 3
        assert pd.isna(out['volume'].iloc[0]), '價格有波動卻 volume=0 → 必須標 NaN'
        assert out['volume'].iloc[1] == 0, 'high==low 的 0 是有效報價，不得動它'
        assert out['volume'].iloc[2] == 5_000_000
        assert out['close'].notna().all(), 'close 是好的，不得因 volume 有問題就整批擋掉'


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
