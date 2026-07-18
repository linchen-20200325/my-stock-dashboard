"""
test_active_etf_fallback.py — 主動式 ETF Yuanta fallback + 異常分級

驗證重點：
1. _fetch_yuanta_active_etf_meta 對非主動式 ETF 直接 return None（不浪費網路）
2. 對主動式 ETF + proxy 全失敗 return None
3. 對主動式 ETF + proxy 成功 + HTML 含經理人 regex 命中 → 回 dict
4. fetch_etf_manager 對主動式 ETF + 前 3 段失敗時走 Yuanta fallback
5. get_etf_expense_ratio_safe 對主動式 ETF 串接 Yuanta
"""
from __future__ import annotations

from unittest.mock import MagicMock


from src.data.etf import etf_fetch


# ════════════════════════════════════════════════════════════
# Yuanta meta fetcher 本身
# ════════════════════════════════════════════════════════════

def test_yuanta_fetcher_returns_none_for_passive_etf():
    """0050（純被動）不該觸發 Yuanta，直接 return None。"""
    assert etf_fetch._fetch_yuanta_active_etf_meta('0050.TW') is None


def test_yuanta_fetcher_returns_none_for_empty_ticker():
    assert etf_fetch._fetch_yuanta_active_etf_meta('') is None
    assert etf_fetch._fetch_yuanta_active_etf_meta(None) is None


def test_yuanta_fetcher_all_urls_fail(monkeypatch):
    """proxy_helper 全部回 None → Yuanta fetcher return None，不爆。"""
    from src.data.proxy import proxy_helper
    monkeypatch.setattr(proxy_helper, 'fetch_url', lambda *a, **kw: None)
    r = etf_fetch._fetch_yuanta_active_etf_meta('00980A.TW')
    assert r is None


def test_yuanta_fetcher_parses_manager(monkeypatch):
    """HTML 含「經理人：張三」格式 → 應抓到 manager='張三'。"""
    from src.data.proxy import proxy_helper
    _html = '''
    <html><body>
    <div class="profile">
      <span>基金經理人：張三</span>
      <span>總費用率 0.85%</span>
      <span>淨值：14.32</span>
      <span>資料日期 2026/05/29</span>
    </div></body></html>
    '''
    _resp = MagicMock()
    _resp.status_code = 200
    _resp.text = _html + ('x' * 600)  # 確保 len > 500
    _resp.encoding = 'utf-8'
    monkeypatch.setattr(proxy_helper, 'fetch_url',
                        lambda *a, **kw: _resp)
    r = etf_fetch._fetch_yuanta_active_etf_meta('00980A.TW')
    assert r is not None
    assert r['manager'] == '張三'
    assert r['expense'] is not None
    assert abs(r['expense'] - 0.0085) < 1e-6
    assert r['nav_latest'] == 14.32
    assert r['source'] == 'yuanta-official'


def test_yuanta_fetcher_parses_multi_managers(monkeypatch):
    """多人共管「張三 / 李四」應正確解析。"""
    from src.data.proxy import proxy_helper
    _html = '經理人：張三 / 李四'
    _resp = MagicMock()
    _resp.status_code = 200
    _resp.text = _html + ('x' * 600)
    _resp.encoding = 'utf-8'
    monkeypatch.setattr(proxy_helper, 'fetch_url',
                        lambda *a, **kw: _resp)
    r = etf_fetch._fetch_yuanta_active_etf_meta('00982A.TW')
    assert r is not None
    assert '張三' in r['manager'] and '李四' in r['manager']


# ════════════════════════════════════════════════════════════
# 整合：fetch_etf_manager 串接 Yuanta
# ════════════════════════════════════════════════════════════

def test_fetch_etf_manager_falls_back_to_yuanta(monkeypatch):
    """MoneyDJ 3 端點 + SITCA 全失敗時，主動式 ETF 應走 Yuanta。"""
    # MoneyDJ 全部 fail
    from src.data.proxy import proxy_helper
    _resp_fail = MagicMock()
    _resp_fail.status_code = 200
    _resp_fail.text = 'x' * 600  # 200 但無經理人 regex 不命中
    _resp_fail.encoding = 'utf-8'
    _yuanta_resp = MagicMock()
    _yuanta_resp.status_code = 200
    _yuanta_resp.text = '經理人：王五' + ('x' * 600)
    _yuanta_resp.encoding = 'utf-8'

    _calls = []
    def _fake_fetch(url, **kw):
        _calls.append(url)
        if 'yuantaetfs' in url:
            return _yuanta_resp
        return _resp_fail

    monkeypatch.setattr(proxy_helper, 'fetch_url', _fake_fetch)
    # SITCA fallback 也回 None
    monkeypatch.setattr(etf_fetch, '_fetch_sitca_manager', lambda t: None)
    # 跳過 curl_cffi fallback（在沙箱跑可能無此模組或實際 network）
    import sys
    if 'curl_cffi' not in sys.modules:
        _stub = MagicMock()
        _stub.requests.get = lambda *a, **kw: MagicMock(status_code=500, text='')
        sys.modules['curl_cffi'] = _stub

    # 清 st.cache_data
    etf_fetch.fetch_etf_manager.clear()
    r = etf_fetch.fetch_etf_manager('00980A.TW')
    assert r is not None, f'Yuanta fallback 失敗 — calls: {_calls}'
    assert r['name'] == '王五'
    # v18.257 S-PROV-1 phase 11:fetch_etf_manager 的 source 升級為 Provenance
    # 慣例 'Provider:Dataset'(對齊 'FRED:<sid>' / 'Yahoo:^VIX'),etf_fetch.py:1085。
    assert r.get('source') == 'Yuanta:official'


# ════════════════════════════════════════════════════════════
# 整合：get_etf_expense_ratio_safe 串接 Yuanta
# ════════════════════════════════════════════════════════════

def test_expense_ratio_uses_yuanta_for_active_etf(monkeypatch):
    """SITCA + MDJ 都回 None，主動式 ETF 應拿 Yuanta 的費用率。"""
    # get_etf_expense_ratio_safe 的 primary 是 fetch_etf_meta_moneydj(Basic0004),
    # 必須一併 mock 回 None — 否則 CI(NAS proxy 可達)會抓到真資料 → 提早 return,
    # 永遠走不到 Yuanta 分支(本機 proxy 不可達才會「碰巧」過)。網路相依改為確定性。
    monkeypatch.setattr(etf_fetch, 'fetch_etf_meta_moneydj', lambda t: None)
    monkeypatch.setattr(etf_fetch, 'fetch_sitca_expense_ratio', lambda t: None)
    monkeypatch.setattr(etf_fetch, 'fetch_moneydj_expense_ratio', lambda t: None)
    monkeypatch.setattr(etf_fetch, '_fetch_yuanta_active_etf_meta',
                        lambda t: {'manager': None, 'expense': 0.0095,
                                   'nav_latest': None, 'nav_date': None,
                                   'source': 'yuanta-official', 'url': 'x'})
    r = etf_fetch.get_etf_expense_ratio_safe('00984A.TW')
    assert r == 0.0095


def test_expense_ratio_skips_yuanta_for_passive_etf(monkeypatch):
    """被動式 ETF 不該走 Yuanta（節省網路）。"""
    monkeypatch.setattr(etf_fetch, 'fetch_sitca_expense_ratio', lambda t: None)
    monkeypatch.setattr(etf_fetch, 'fetch_moneydj_expense_ratio', lambda t: None)
    _yuanta_called = []
    monkeypatch.setattr(etf_fetch, '_fetch_yuanta_active_etf_meta',
                        lambda t: _yuanta_called.append(t) or None)
    # 0050 被動 ETF — 不該觸發 Yuanta
    monkeypatch.setattr(etf_fetch, 'fetch_etf_info', lambda t: {})
    etf_fetch.get_etf_expense_ratio_safe('0050.TW')
    assert _yuanta_called == [], f'Yuanta 不該對被動 ETF 呼叫，但被呼叫了：{_yuanta_called}'


# ════════════════════════════════════════════════════════════
# is_active_etf 分類 golden test（v19.130 L/R 誤判修正）
# ════════════════════════════════════════════════════════════
# Regression 守門：台股後綴 L(槓桿正2)/R(反向反1)/B(債券)/U,F(期貨) 皆屬
# 被動追蹤,絕不可判為主動式。原程式排除集誤寫 ('B','K')——台股無 'K' 後綴,
# 且漏掉 L/R,導致 00631L(正2)/00632R(反1) 被 `_last.isalpha()` 分支誤判成
# 主動式 → 觸發錯誤的「主動式 ETF 弱勢判定」+ 無謂的 Yuanta 官網抓取。

def test_leveraged_etf_is_passive():
    """00631L(元大台灣50正2,槓桿)= 被動追蹤,非主動經理式。(修正前誤判為 True)"""
    assert etf_fetch.is_active_etf('00631L.TW') is False
    assert etf_fetch.is_active_etf('00675L') is False   # 富邦臺灣加權正2


def test_inverse_etf_is_passive():
    """00632R(元大台灣50反1,反向)= 被動追蹤。(修正前誤判為 True)"""
    assert etf_fetch.is_active_etf('00632R.TW') is False
    assert etf_fetch.is_active_etf('00676R') is False   # 富邦臺灣加權反1


def test_bond_etf_is_passive():
    """00679B(元大美債20年,債券型)= 被動追蹤。"""
    assert etf_fetch.is_active_etf('00679B.TW') is False
    assert etf_fetch.is_active_etf('00687B') is False   # 國泰20年美債


def test_futures_etf_is_passive():
    """期貨型 ETF(U/F 後綴)= 被動追蹤。"""
    assert etf_fetch.is_active_etf('00642U.TW') is False   # 期元大S&P石油
    assert etf_fetch.is_active_etf('00635U') is False      # 期元大道瓊白銀


def test_active_whitelist_etf_is_active():
    """白名單主動式 ETF(A/D/T 後綴)→ True。"""
    assert etf_fetch.is_active_etf('00980A.TW') is True   # 元大台灣價值高息(主動)
    assert etf_fetch.is_active_etf('00982T') is True      # 白名單 T 後綴
    assert etf_fetch.is_active_etf('00980D') is True      # 白名單 D 後綴


def test_active_a_suffix_non_whitelist_is_active():
    """未在白名單但 'A' 後綴(主動式命名慣例)→ True(fallback 分支)。"""
    # 元大主動式系列尚未全列入白名單者,靠 isalpha 分支仍判主動
    assert etf_fetch.is_active_etf('00999A') is True


def test_passive_numeric_etf_is_passive():
    """純數字代號 = 被動追蹤指數。"""
    for _t in ('0050.TW', '00878', '00940.TW', '006208'):
        assert etf_fetch.is_active_etf(_t) is False, f'{_t} 應為被動'


def test_is_active_etf_empty_ticker():
    """空 / None → False(不腦補)。"""
    assert etf_fetch.is_active_etf('') is False
    assert etf_fetch.is_active_etf(None) is False
