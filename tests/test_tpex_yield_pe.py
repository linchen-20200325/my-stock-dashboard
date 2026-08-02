"""上櫃(TPEX)估值補上測試 — fetch_tpex_yield_pe + fetch_pe_name_maps SSOT 合併。

背景:選股網「估值分」原僅來自 TWSE BWIBBU_d(上市),上櫃股不在該表 → 估值分 None、
名稱空白(同一來源)。本次補 TPEX peratio_analysis(上櫃)並以 fetch_pe_name_maps
合併上市 + 上櫃,四個 orchestrator(畫面 / 推播 / 凍結 / MCP)同源。

驗證重點:
1. fetch_tpex_yield_pe 正確解析 TPEX 欄位(SecuritiesCompanyCode / CompanyName /
   PriceEarningRatio / YieldRatio / PriceBookRatio),值為字串 → to_numeric。
2. YieldRatio 缺席時 fallback DividendYield。
3. '-' 空值 → NaN;非 list / 空 → 空 DataFrame(§1 不假造)。
4. fetch_pe_name_maps 合併上市 + 上櫃:上櫃代碼進 pe_map / name_map、上市優先、
   'nan' 名稱過濾、單一來源失敗仍 fail-soft 回另一邊。
5. 整合:合併後的 pe_map 餵 _percentile_scores → 上櫃股拿得到估值分(非 None)。

3 個最容易出錯的輸入:空 list、'-' 佔位符、殖利率欄改名(YieldRatio↔DividendYield)。
"""
from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _clear_caches():
    """清 streamlit cache_data,避免 case 間串擾(fetch_tpex_yield_pe / fetch_twse_yield_pe)。"""
    from src.ui.tabs import yield_screener as ys
    for _fn in ('fetch_tpex_yield_pe', 'fetch_twse_yield_pe'):
        try:
            getattr(ys, _fn).clear()
        except Exception:
            pass
    yield
    for _fn in ('fetch_tpex_yield_pe', 'fetch_twse_yield_pe'):
        try:
            getattr(ys, _fn).clear()
        except Exception:
            pass


def _resp(json_payload, status=200):
    """假 requests-like response:.status_code + .json()。"""
    _r = MagicMock()
    _r.status_code = status
    _r.json.return_value = json_payload
    return _r


# TPEX peratio_analysis 真實欄位(驗證自 TWSEMCPServer e2e 契約)
_TPEX_ROWS = [
    {"SecuritiesCompanyCode": "5483", "CompanyName": "中美晶",
     "PriceEarningRatio": "12.50", "YieldRatio": "3.20", "PriceBookRatio": "1.80"},
    {"SecuritiesCompanyCode": "8069", "CompanyName": "元太",
     "PriceEarningRatio": "20.00", "YieldRatio": "2.10", "PriceBookRatio": "4.50"},
    {"SecuritiesCompanyCode": "6488", "CompanyName": "環球晶",
     "PriceEarningRatio": "-", "YieldRatio": "-", "PriceBookRatio": "-"},  # 空值佔位
]


# ── 1. TPEX 解析 ────────────────────────────────────────────────────────────
class TestFetchTpexYieldPe:
    def test_parses_tpex_fields(self):
        from src.ui.tabs.yield_screener import fetch_tpex_yield_pe
        with patch('src.services.yield_screener_service.proxy_fetch_url',
                   return_value=_resp(_TPEX_ROWS)):
            df = fetch_tpex_yield_pe()
        assert not df.empty
        assert set(['代碼', '名稱', '本益比', '殖利率(%)', '股價淨值比']).issubset(df.columns)
        _row = df[df['代碼'] == '5483'].iloc[0]
        assert _row['名稱'] == '中美晶'
        assert math.isclose(_row['本益比'], 12.50, rel_tol=1e-9)
        assert math.isclose(_row['殖利率(%)'], 3.20, rel_tol=1e-9)
        assert df.attrs.get('source') == 'TPEX:OpenAPI:peratio_analysis'

    def test_dash_placeholder_becomes_nan(self):
        """'-' 佔位 → NaN(§1:不填 0、不造假)。"""
        from src.ui.tabs.yield_screener import fetch_tpex_yield_pe
        with patch('src.services.yield_screener_service.proxy_fetch_url',
                   return_value=_resp(_TPEX_ROWS)):
            df = fetch_tpex_yield_pe()
        _row = df[df['代碼'] == '6488'].iloc[0]
        assert pd.isna(_row['本益比'])
        assert _row['名稱'] == '環球晶'  # 名稱仍在(不因 PE 缺而丟)

    def test_dividend_yield_fallback(self):
        """殖利率欄名為 DividendYield(非 YieldRatio)時仍解析。"""
        from src.ui.tabs.yield_screener import fetch_tpex_yield_pe
        _rows = [{"SecuritiesCompanyCode": "5483", "CompanyName": "中美晶",
                  "PriceEarningRatio": "12.50", "DividendYield": "3.20",
                  "PriceBookRatio": "1.80"}]
        with patch('src.services.yield_screener_service.proxy_fetch_url',
                   return_value=_resp(_rows)):
            df = fetch_tpex_yield_pe()
        assert math.isclose(df.iloc[0]['殖利率(%)'], 3.20, rel_tol=1e-9)

    def test_empty_or_bad_payload_returns_empty(self):
        from src.ui.tabs.yield_screener import fetch_tpex_yield_pe
        for _payload in ([], {"not": "a list"}, None):
            with patch('src.services.yield_screener_service.proxy_fetch_url',
                       return_value=_resp(_payload)):
                assert fetch_tpex_yield_pe().empty
        # 非 200
        with patch('src.services.yield_screener_service.proxy_fetch_url',
                   return_value=_resp(_TPEX_ROWS, status=500)):
            assert fetch_tpex_yield_pe().empty
        # None response
        with patch('src.services.yield_screener_service.proxy_fetch_url',
                   return_value=None):
            assert fetch_tpex_yield_pe().empty


# ── 2. SSOT 合併 ────────────────────────────────────────────────────────────
_TWSE_DF = pd.DataFrame({
    '代碼': ['2330', '2027'],
    '名稱': ['台積電', '大成鋼'],
    '本益比': [18.0, 9.5],
    '殖利率(%)': [2.0, 4.0],
    '股價淨值比': [5.0, 1.2],
})
_TPEX_DF = pd.DataFrame({
    '代碼': ['5483', '8069'],
    '名稱': ['中美晶', '元太'],
    '本益比': [12.5, 20.0],
    '殖利率(%)': [3.2, 2.1],
    '股價淨值比': [1.8, 4.5],
})


class TestFetchPeNameMaps:
    def test_merges_listed_and_otc(self):
        from src.ui.tabs import yield_screener as ys
        with patch.object(ys, 'fetch_twse_yield_pe', return_value=_TWSE_DF), \
             patch.object(ys, 'fetch_tpex_yield_pe', return_value=_TPEX_DF):
            pe_map, name_map = ys.fetch_pe_name_maps()
        # 上市 + 上櫃 都在
        assert set(pe_map) == {'2330', '2027', '5483', '8069'}
        assert name_map['5483'] == '中美晶'   # 原本空白的上櫃股 → 有名稱
        assert math.isclose(pe_map['5483'], 12.5, rel_tol=1e-9)  # 上櫃股 → 有 PE

    def test_listed_wins_on_duplicate_code(self):
        """代碼偶發重疊時上市先填(setdefault)。"""
        from src.ui.tabs import yield_screener as ys
        _dup = pd.DataFrame({'代碼': ['2330'], '名稱': ['冒充'], '本益比': [99.0]})
        with patch.object(ys, 'fetch_twse_yield_pe', return_value=_TWSE_DF), \
             patch.object(ys, 'fetch_tpex_yield_pe', return_value=_dup):
            pe_map, name_map = ys.fetch_pe_name_maps()
        assert math.isclose(pe_map['2330'], 18.0, rel_tol=1e-9)  # 上市值贏
        assert name_map['2330'] == '台積電'

    def test_filters_nan_names(self):
        from src.ui.tabs import yield_screener as ys
        _bad = pd.DataFrame({'代碼': ['9999'], '名稱': ['nan'], '本益比': [10.0]})
        with patch.object(ys, 'fetch_twse_yield_pe', return_value=pd.DataFrame()), \
             patch.object(ys, 'fetch_tpex_yield_pe', return_value=_bad):
            pe_map, name_map = ys.fetch_pe_name_maps()
        assert '9999' in pe_map              # PE 仍收
        assert '9999' not in name_map        # 'nan' 名稱不收(避免畫面顯示 "nan")

    def test_fail_soft_one_source_down(self):
        """單一來源丟例外 → 仍回另一邊(fail-soft,不炸)。"""
        from src.ui.tabs import yield_screener as ys
        def _boom():
            raise RuntimeError("TWSE down")
        with patch.object(ys, 'fetch_twse_yield_pe', side_effect=_boom), \
             patch.object(ys, 'fetch_tpex_yield_pe', return_value=_TPEX_DF):
            pe_map, name_map = ys.fetch_pe_name_maps()
        assert set(pe_map) == {'5483', '8069'}   # 上市掛了,上櫃照回

    def test_both_down_returns_empty(self):
        from src.ui.tabs import yield_screener as ys
        with patch.object(ys, 'fetch_twse_yield_pe', return_value=pd.DataFrame()), \
             patch.object(ys, 'fetch_tpex_yield_pe', return_value=pd.DataFrame()):
            pe_map, name_map = ys.fetch_pe_name_maps()
        assert pe_map == {} and name_map == {}


# ── 3. 整合:合併後上櫃股拿得到估值分(非 None)──────────────────────────────
class TestOtcGetsValuationScore:
    def test_otc_gets_valuation_percentile(self):
        from src.ui.tabs import yield_screener as ys
        from src.services.fundamental_screener_service import _percentile_scores
        with patch.object(ys, 'fetch_twse_yield_pe', return_value=_TWSE_DF), \
             patch.object(ys, 'fetch_tpex_yield_pe', return_value=_TPEX_DF):
            pe_map, _ = ys.fetch_pe_name_maps()
        ids = ['2330', '2027', '5483', '8069']  # 含 2 上櫃
        scores = _percentile_scores(ids, pe_map, higher_better=False)  # PE 低→分高
        # 上櫃股原本 None,現在有分
        assert '5483' in scores and '8069' in scores
        # PE 最低(2027=9.5)分最高
        assert scores['2027'] == max(scores.values())
