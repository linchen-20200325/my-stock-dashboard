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

⚠️ E2(2026-08)搬遷後的 patch 目標(勿回退):三個 fetcher 已從
`src/ui/tabs/yield_screener.py`(L5 UI Tab)下沉到 `src/data/stock/yield_pe_fetcher.py`
(L1),L5 只剩 re-export。`fetch_pe_name_maps` 在呼叫時從 **L1 模組 globals** 解析兩個
fetcher,且 L1 的 HTTP 出口是 **L1 自己的** `proxy_fetch_url`(不再繞 L3
`yield_screener_service`)。patch 打舊目標會「照樣綠但打真網路」= 假綠燈,
所以下面每處 mock 都加了 call_count 斷言。
"""
from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


def _clear_fetcher_cache(*names: str) -> None:
    """清 @st.cache_data(無 streamlit 環境時 decorator 退化為 no-op,無 .clear())。"""
    from src.data.stock import yield_pe_fetcher as ypf
    for _fn in (names or ('fetch_tpex_yield_pe', 'fetch_twse_yield_pe')):
        try:
            getattr(ypf, _fn).clear()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def _clear_caches():
    """清 streamlit cache_data,避免 case 間串擾(fetch_tpex_yield_pe / fetch_twse_yield_pe)。"""
    _clear_fetcher_cache()
    yield
    _clear_fetcher_cache()


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

# L1 模組內 HTTP 出口的 patch 目標(唯一正確的那個)
_HTTP_TARGET = 'src.data.stock.yield_pe_fetcher.proxy_fetch_url'


def _assert_http_mock_used(mock, *, expect_host: str):
    """證明 patch 真的攔到 —— 打錯目標時這裡炸,而不是靜默去打真 OpenAPI。"""
    assert mock.call_count >= 1, (
        f"{_HTTP_TARGET} mock 從未被呼叫 —— patch 目標沒打到 L1 的 HTTP 出口,"
        "這條測試可能正在打真網路"
    )
    assert expect_host in str(mock.call_args), (
        f"proxy_fetch_url 收到的 URL 不含 {expect_host}:{mock.call_args}"
    )


# ── 1. TPEX 解析 ────────────────────────────────────────────────────────────
class TestFetchTpexYieldPe:
    def test_parses_tpex_fields(self):
        from src.data.stock.yield_pe_fetcher import fetch_tpex_yield_pe
        with patch(_HTTP_TARGET, return_value=_resp(_TPEX_ROWS)) as _http:
            df = fetch_tpex_yield_pe()
            _assert_http_mock_used(_http, expect_host='tpex.org.tw')
        assert not df.empty
        assert set(['代碼', '名稱', '本益比', '殖利率(%)', '股價淨值比']).issubset(df.columns)
        _row = df[df['代碼'] == '5483'].iloc[0]
        assert _row['名稱'] == '中美晶'
        assert math.isclose(_row['本益比'], 12.50, rel_tol=1e-9)
        assert math.isclose(_row['殖利率(%)'], 3.20, rel_tol=1e-9)
        assert df.attrs.get('source') == 'TPEX:OpenAPI:peratio_analysis'

    def test_dash_placeholder_becomes_nan(self):
        """'-' 佔位 → NaN(§1:不填 0、不造假)。"""
        from src.data.stock.yield_pe_fetcher import fetch_tpex_yield_pe
        with patch(_HTTP_TARGET, return_value=_resp(_TPEX_ROWS)) as _http:
            df = fetch_tpex_yield_pe()
            _assert_http_mock_used(_http, expect_host='tpex.org.tw')
        _row = df[df['代碼'] == '6488'].iloc[0]
        assert pd.isna(_row['本益比'])
        assert _row['名稱'] == '環球晶'  # 名稱仍在(不因 PE 缺而丟)

    def test_dividend_yield_fallback(self):
        """殖利率欄名為 DividendYield(非 YieldRatio)時仍解析。"""
        from src.data.stock.yield_pe_fetcher import fetch_tpex_yield_pe
        _rows = [{"SecuritiesCompanyCode": "5483", "CompanyName": "中美晶",
                  "PriceEarningRatio": "12.50", "DividendYield": "3.20",
                  "PriceBookRatio": "1.80"}]
        with patch(_HTTP_TARGET, return_value=_resp(_rows)) as _http:
            df = fetch_tpex_yield_pe()
            _assert_http_mock_used(_http, expect_host='tpex.org.tw')
        assert math.isclose(df.iloc[0]['殖利率(%)'], 3.20, rel_tol=1e-9)

    def test_empty_or_bad_payload_returns_empty(self):
        from src.data.stock import yield_pe_fetcher as ypf
        # 每個 case 之間必須清 cache:同函式同參數,不清會拿到上一輪的快取結果
        # → mock 不被呼叫 → _assert_http_mock_used 會炸(而不是靜默通過)。
        for _payload in ([], {"not": "a list"}, None):
            _clear_fetcher_cache('fetch_tpex_yield_pe')
            with patch(_HTTP_TARGET, return_value=_resp(_payload)) as _http:
                assert ypf.fetch_tpex_yield_pe().empty
                _assert_http_mock_used(_http, expect_host='tpex.org.tw')
        # 非 200
        _clear_fetcher_cache('fetch_tpex_yield_pe')
        with patch(_HTTP_TARGET, return_value=_resp(_TPEX_ROWS, status=500)) as _http:
            assert ypf.fetch_tpex_yield_pe().empty
            _assert_http_mock_used(_http, expect_host='tpex.org.tw')
        # None response
        _clear_fetcher_cache('fetch_tpex_yield_pe')
        with patch(_HTTP_TARGET, return_value=None) as _http:
            assert ypf.fetch_tpex_yield_pe().empty
            _assert_http_mock_used(_http, expect_host='tpex.org.tw')


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


def _assert_both_fetchers_mocked(_twse, _tpex):
    """兩個市場的 mock 都必須被走到 —— 否則代表 patch 打在 L5 re-export 別名上。"""
    assert _twse.call_count == 1, (
        f"fetch_twse_yield_pe mock 被呼叫 {_twse.call_count} 次(預期 1)—— "
        "patch 目標應為 L1 模組 src.data.stock.yield_pe_fetcher"
    )
    assert _tpex.call_count == 1, (
        f"fetch_tpex_yield_pe mock 被呼叫 {_tpex.call_count} 次(預期 1)—— "
        "patch 目標應為 L1 模組 src.data.stock.yield_pe_fetcher"
    )


class TestFetchPeNameMaps:
    def test_merges_listed_and_otc(self):
        from src.data.stock import yield_pe_fetcher as ypf
        with patch.object(ypf, 'fetch_twse_yield_pe', return_value=_TWSE_DF) as _tw, \
             patch.object(ypf, 'fetch_tpex_yield_pe', return_value=_TPEX_DF) as _tp:
            pe_map, name_map = ypf.fetch_pe_name_maps()
            _assert_both_fetchers_mocked(_tw, _tp)
        # 上市 + 上櫃 都在
        assert set(pe_map) == {'2330', '2027', '5483', '8069'}
        assert name_map['5483'] == '中美晶'   # 原本空白的上櫃股 → 有名稱
        assert math.isclose(pe_map['5483'], 12.5, rel_tol=1e-9)  # 上櫃股 → 有 PE

    def test_listed_wins_on_duplicate_code(self):
        """代碼偶發重疊時上市先填(setdefault)。"""
        from src.data.stock import yield_pe_fetcher as ypf
        _dup = pd.DataFrame({'代碼': ['2330'], '名稱': ['冒充'], '本益比': [99.0]})
        with patch.object(ypf, 'fetch_twse_yield_pe', return_value=_TWSE_DF) as _tw, \
             patch.object(ypf, 'fetch_tpex_yield_pe', return_value=_dup) as _tp:
            pe_map, name_map = ypf.fetch_pe_name_maps()
            _assert_both_fetchers_mocked(_tw, _tp)
        assert math.isclose(pe_map['2330'], 18.0, rel_tol=1e-9)  # 上市值贏
        assert name_map['2330'] == '台積電'

    def test_filters_nan_names(self):
        from src.data.stock import yield_pe_fetcher as ypf
        _bad = pd.DataFrame({'代碼': ['9999'], '名稱': ['nan'], '本益比': [10.0]})
        with patch.object(ypf, 'fetch_twse_yield_pe',
                          return_value=pd.DataFrame()) as _tw, \
             patch.object(ypf, 'fetch_tpex_yield_pe', return_value=_bad) as _tp:
            pe_map, name_map = ypf.fetch_pe_name_maps()
            _assert_both_fetchers_mocked(_tw, _tp)
        assert '9999' in pe_map              # PE 仍收
        assert '9999' not in name_map        # 'nan' 名稱不收(避免畫面顯示 "nan")

    def test_fail_soft_one_source_down(self):
        """單一來源丟例外 → 仍回另一邊(fail-soft,不炸)。"""
        from src.data.stock import yield_pe_fetcher as ypf
        def _boom():
            raise RuntimeError("TWSE down")
        with patch.object(ypf, 'fetch_twse_yield_pe', side_effect=_boom) as _tw, \
             patch.object(ypf, 'fetch_tpex_yield_pe', return_value=_TPEX_DF) as _tp:
            pe_map, name_map = ypf.fetch_pe_name_maps()
            _assert_both_fetchers_mocked(_tw, _tp)
        assert set(pe_map) == {'5483', '8069'}   # 上市掛了,上櫃照回

    def test_both_down_returns_empty(self):
        from src.data.stock import yield_pe_fetcher as ypf
        with patch.object(ypf, 'fetch_twse_yield_pe',
                          return_value=pd.DataFrame()) as _tw, \
             patch.object(ypf, 'fetch_tpex_yield_pe',
                          return_value=pd.DataFrame()) as _tp:
            pe_map, name_map = ypf.fetch_pe_name_maps()
            _assert_both_fetchers_mocked(_tw, _tp)
        assert pe_map == {} and name_map == {}


# ── 3. 整合:合併後上櫃股拿得到估值分(非 None)──────────────────────────────
class TestOtcGetsValuationScore:
    def test_otc_gets_valuation_percentile(self):
        from src.data.stock import yield_pe_fetcher as ypf
        from src.services.fundamental_screener_service import _percentile_scores
        with patch.object(ypf, 'fetch_twse_yield_pe', return_value=_TWSE_DF) as _tw, \
             patch.object(ypf, 'fetch_tpex_yield_pe', return_value=_TPEX_DF) as _tp:
            pe_map, _ = ypf.fetch_pe_name_maps()
            _assert_both_fetchers_mocked(_tw, _tp)
        ids = ['2330', '2027', '5483', '8069']  # 含 2 上櫃
        scores = _percentile_scores(ids, pe_map, higher_better=False)  # PE 低→分高
        # 上櫃股原本 None,現在有分
        assert '5483' in scores and '8069' in scores
        # PE 最低(2027=9.5)分最高
        assert scores['2027'] == max(scores.values())
