"""tests/test_etf_official_premium.py — v18.450 TWSE MIS 全體投信 ETF 淨值解析守衛。

fetch_etf_official_premium 抓 `mis.twse.com.tw/stock/data/all_etf.txt`(user 用瀏覽器
DevTools Network 面板實測確認的真實 endpoint)。**回應頂層其實是物件 `{"a1": [...]}`**
(v18.446 誤判成裸陣列,production log 證實連線成功但解析失敗才發現這個結構差異 —— 見
`test_response_is_dict_wrapped_not_bare_list` 回歸守衛)。`a1` 的值才是「投信」區塊陣列,
每區塊帶 `msgArray`(該投信旗下 ETF)。本測試釘死欄位對映(a=代號 / e=成交價 /
f=投信預估淨值 / g=折溢價率% / h=前一營業日淨值),用真實 0050/0051 數值驗算過:
  g == (e - f) / f * 100(0050: (109.35-109.69)/109.69*100 ≈ -0.31 ✓)
避免日後誤把 e(市價)與 f(淨值)接反 → 又算出假溢價。

v18.448:改用自建 session(暖身 GET 揭露頁面建立 JSESSIONID,再 GET all_etf.txt)取代
`fetch_url`,故 mock 對象改為 `_fetch_all_etf_json`(直接回傳 parsed JSON,略過真實
HTTP 呼叫細節)。
"""
from __future__ import annotations

import pytest

import src.data.etf.etf_fetch as ef
import src.data.proxy.proxy_helper as ph


# 「投信區塊」陣列本體(24 家投信各自的 msgArray)
_ISSUER_BLOCKS = [
    {'refURL': 'https://www.jkoam.com/etf/predict', 'userDelay': '15000',
     'rtMessage': 'OK', 'rtCode': '0000'},  # 無 msgArray 的投信區塊(防呆用)
    {
        'refURL': 'https://www.yuantaetfs.com/tradeInfo/INav',
        'userDelay': 15000, 'rtMessage': 'OK', 'rtCode': '0000',
        'msgArray': [
            {'a': '0050', 'b': '元大台灣50', 'c': 20754500000, 'd': 48000000,
             'e': '109.3500', 'f': '109.6900', 'g': '-0.31', 'h': '106.7400',
             'i': '20260701', 'j': '13:30:45', 'k': '1'},
            {'a': '0051', 'b': '元大中型100', 'c': 24500000, 'd': 0,
             'e': '147.8000', 'f': '147.2200', 'g': '0.39', 'h': '147.8200',
             'i': '20260701', 'j': '13:30:45', 'k': '1'},
        ],
    },
    {},  # 空區塊(真實 payload 最後一筆是 {})
]

# 真實 all_etf.txt 頂層結構(v18.450 修正):物件包一層,鍵名 "a1"，值才是投信區塊陣列。
_ALL_ETF_PAYLOAD = {'a1': _ISSUER_BLOCKS}


def _patch_proxy_and_mis(monkeypatch, payload=_ALL_ETF_PAYLOAD):
    monkeypatch.setattr(ph, 'get_proxy_config', lambda: {'http': 'x', 'https': 'x'})
    monkeypatch.setattr(ef, '_fetch_all_etf_json',
                        lambda *a, **k: (payload, 200))
    ef.fetch_etf_official_premium.clear()


def test_field_mapping_0050(monkeypatch):
    """e=成交價、f=投信預估淨值、g=折溢價率 —— 對映不可接反(真實數值驗算)。"""
    _patch_proxy_and_mis(monkeypatch)
    out = ef.fetch_etf_official_premium('0050.TW')
    assert out is not None, '元大投信區塊有 0050 → 應回值'
    assert out['nav'] == pytest.approx(109.69), 'nav 應取 f(投信預估淨值)'
    assert out['price'] == pytest.approx(109.35), 'price 應取 e(成交價)'
    assert out['premium_pct'] == pytest.approx(-0.31), 'premium_pct 應取 g(折溢價率)'
    assert out['data_date'] == '2026/07/01'
    assert 'TWSE-MIS' in out['source']


def test_field_mapping_0051(monkeypatch):
    """第二檔(同投信區塊內)驗算,防止只挑對第一筆的偶然通過。"""
    _patch_proxy_and_mis(monkeypatch)
    out = ef.fetch_etf_official_premium('0051.TW')
    assert out is not None
    assert out['nav'] == pytest.approx(147.22)
    assert out['price'] == pytest.approx(147.80)
    assert out['premium_pct'] == pytest.approx(0.39)


def test_premium_backfill_when_g_missing(monkeypatch):
    """g(折溢價率)缺 → 由 (成交價-淨值)/淨值 反推(fail-loud 保底,不留空)。"""
    payload = [{
        'refURL': 'x', 'msgArray': [
            {'a': '0050', 'e': '101.0', 'f': '100.0', 'i': '20260701'},  # 無 g
        ],
    }]
    _patch_proxy_and_mis(monkeypatch, payload)
    out = ef.fetch_etf_official_premium('0050.TW')
    assert out is not None
    assert out['premium_pct'] == pytest.approx(1.0, abs=0.001)  # (101-100)/100


def test_ticker_searched_across_all_issuer_blocks(monkeypatch):
    """代號須跨全部投信區塊搜尋(不能只看第一個非空區塊)。"""
    payload = [
        {'refURL': 'a', 'msgArray': [{'a': '0056', 'e': '40', 'f': '40', 'g': '0'}]},
        {'refURL': 'b'},  # 無 msgArray
        {'refURL': 'c', 'msgArray': [{'a': '0050', 'e': '109.35', 'f': '109.69',
                                       'g': '-0.31', 'i': '20260701'}]},
    ]
    _patch_proxy_and_mis(monkeypatch, payload)
    out = ef.fetch_etf_official_premium('0050.TW')
    assert out is not None, '0050 在第 3 個區塊,須搜尋全部區塊才找得到'
    assert out['nav'] == pytest.approx(109.69)


def test_no_proxy_returns_none(monkeypatch):
    """完全未設代理(PROXY_URL/NAS_PROXY_URL)→ 回 None(不觸網,呼叫端走既有鏈)。"""
    monkeypatch.setattr(ph, 'get_proxy_config', lambda: None)
    ef.fetch_etf_official_premium.clear()
    assert ef.fetch_etf_official_premium('0050.TW') is None


def test_warmup_and_data_fetch_both_attempted(monkeypatch):
    """_fetch_all_etf_json 失敗(如暖身頁 403)時,fetch_etf_official_premium 應乾淨回 None,
    不拋例外(呼叫端才能安全 fallback 既有 NAV 鏈)。"""
    monkeypatch.setattr(ph, 'get_proxy_config', lambda: {'http': 'x', 'https': 'x'})
    monkeypatch.setattr(ef, '_fetch_all_etf_json', lambda *a, **k: (None, 403))
    ef.fetch_etf_official_premium.clear()
    assert ef.fetch_etf_official_premium('0050.TW') is None


def test_connection_exception_does_not_propagate(monkeypatch):
    """代理/直連皆拋例外(如逾時)→ 吞例外回 None,不讓整個折溢價計算炸掉。"""
    def _boom(*a, **k):
        raise ConnectionError('simulated network failure')
    monkeypatch.setattr(ph, 'get_proxy_config', lambda: {'http': 'x', 'https': 'x'})
    monkeypatch.setattr(ef, '_fetch_all_etf_json', _boom)
    ef.fetch_etf_official_premium.clear()
    assert ef.fetch_etf_official_premium('0050.TW') is None


def test_us_etf_skipped(monkeypatch):
    """海外 ETF(SPY)非數字碼 → 直接 None(TWSE 無資料),不觸網。"""
    ef.fetch_etf_official_premium.clear()
    assert ef.fetch_etf_official_premium('SPY') is None


def test_ticker_not_found_in_any_block(monkeypatch):
    """全部區塊都搜過但代號不存在 → None(不誤配錯的 ETF)。"""
    _patch_proxy_and_mis(monkeypatch)
    out = ef.fetch_etf_official_premium('00999.TW')
    assert out is None


def test_response_is_dict_wrapped_not_bare_list(monkeypatch):
    """v18.450 回歸守衛:production log 證實 v18.446/448 連線已成功(HTTP 200 + json()
    正常),但解析卡在「回應非預期陣列結構」—— 回應頂層其實是 `{"a1": [...]}`(物件包一層,
    鍵名剛好叫 "a1"),先前誤判成裸陣列。此測試直接餵 dict-wrapped payload(而非本檔其他
    測試常用的裸 list),確保不會再退回誤判。"""
    _patch_proxy_and_mis(monkeypatch, {'a1': _ISSUER_BLOCKS})
    out = ef.fetch_etf_official_premium('0050.TW')
    assert out is not None, '{"a1": [...]} 結構應能正確解析,不得誤判為「非預期結構」'
    assert out['premium_pct'] == pytest.approx(-0.31)


def test_response_dict_with_unknown_key_still_parses(monkeypatch):
    """鍵名若非 "a1"(TWSE 未來若改變內部命名)→ 仍應在 dict 的所有 value 裡找到
    list-of-dict 並正確解析,不因鍵名寫死而脆弱。"""
    _patch_proxy_and_mis(monkeypatch, {'some_other_key': _ISSUER_BLOCKS})
    out = ef.fetch_etf_official_premium('0050.TW')
    assert out is not None
    assert out['premium_pct'] == pytest.approx(-0.31)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
