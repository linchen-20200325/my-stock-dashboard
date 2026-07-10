"""tests/test_etf_moneydj_nav_parse.py — v18.451 MoneyDJ Basic0003 淨值表格解析守衛。

production bug:「近期淨值及折溢價」表格顯示 0050.TW 假折溢價(2026/07/01 誤配淨值
106.74,實際 07/01 淨值應為 109.69)。追查發現 fetch_etf_nav_history 的 MoneyDJ
Basic0003 備援(4b)用 regex「日期後 40 字內接數字」抓 NAV,但 user 提供的實測
HTML 證實這是**正規 <table>**(<td class="col07">日期</td><td class="col08">淨值
</td><td class="col09">市價</td><td class="col09">折溢價%</td>),日期與淨值中間
隔了其他欄位,遠超過 40 字 → regex 從未真的抓到過(production log:「200 但 regex
無 date+nav pair」),一路 fallback 到 yfinance 過時 navPrice。

本測試用 user 實際在瀏覽器 DevTools 複製給我的真實 <tr> HTML(2026/07/01 那列)+
比照同一頁面截圖的另外兩列(06/30、06/29),驗證新的 BeautifulSoup 解析器能正確
抓出 date/nav/price/premium_pct,且同一列的三個數值同源同日(無跨欄位錯位風險)。
"""
from __future__ import annotations

import datetime

import pytest

import src.data.etf.etf_fetch as ef


# user 用瀏覽器 DevTools「Copy outerHTML」複製的真實一列(2026/07/01),
# 另外兩列(06/30 折溢價正值、06/29)依同一頁面截圖數值比照真實格式補齊,
# 用以驗證：(a) 負值 <span class="negative"> 包裹、(b) 正值不含 span 兩種情境皆可解析。
_MONEYDJ_HTML = '''
<html><body>
<table>
<tr><th>日期</th><th>淨值</th><th>市價</th><th>折溢價(%)</th></tr>
<tr>
    <td class="col07">
        2026/07/01
    </td>
    <td class="col08">
        109.6900
    </td>
    <td class="col09">
        109.3500
    </td>
    <td class="col09">
        <span class="negative">-0.31</span>
    </td>
</tr>
<tr>
    <td class="col07">2026/06/30</td>
    <td class="col08">106.7400</td>
    <td class="col09">107.8000</td>
    <td class="col09">0.99</td>
</tr>
<tr>
    <td class="col07">2026/06/29</td>
    <td class="col08">104.0300</td>
    <td class="col09">104.4500</td>
    <td class="col09">0.40</td>
</tr>
</table>
</body></html>
'''


class _FakeResp:
    status_code = 200
    text = _MONEYDJ_HTML

    def json(self):  # pragma: no cover - 不會被呼叫,僅防呆
        raise NotImplementedError


class _FakeSecrets(dict):
    """空 st.secrets 替身 — 沙盒環境無 secrets.toml,真呼叫 st.secrets 會 raise。"""
    def get(self, key, default=None):
        return default


def _patch_moneydj_only(monkeypatch):
    """讓 fetch_etf_nav_history 略過 FinMind/goodinfo/Basic0001,直接落到 Basic0003(4b)。

    v19.74:patch 目標從 package(`src.data.proxy`)改為真正持有者
    `proxy_helper`。package 是 PEP 562 lazy forward(無實體 fetch_url 屬性),
    monkeypatch 對 package setattr 後,teardown「還原」會把真函式物件寫成
    package 的**實體屬性** → 永久蓋住 __getattr__ 轉發 → 其後任何測試 patch
    `proxy_helper.fetch_url` 都打不進 production 的
    `from src.data.proxy import fetch_url`(risk_radar CBOE 4 測全套件連跑
    order-dependent 失敗的根因)。patch 持有者則 teardown 乾淨,轉發不受污染。
    """
    from src.data.proxy import proxy_helper as _ph

    monkeypatch.setattr(ef.st, 'secrets', _FakeSecrets(), raising=False)

    def _fake_fetch_url(url, *a, **k):
        if 'Basic0003' in url:
            return _FakeResp()
        return None  # FinMind / goodinfo / Basic0001 皆回 None,強制落到 4b
    monkeypatch.setattr(_ph, 'fetch_url', _fake_fetch_url)
    ef.fetch_etf_nav_history.clear()


def test_moneydj_table_parsed_correctly(monkeypatch):
    """正規 <table> 結構(td class 分欄)須正確解析,不再依賴「40 字內」的 regex 假設。"""
    _patch_moneydj_only(monkeypatch)
    df = ef.fetch_etf_nav_history('0050.TW', days=35)
    assert not df.empty, 'MoneyDJ Basic0003 應解析出至少 1 筆'
    assert 'nav' in df.columns and 'price' in df.columns and 'premium_pct' in df.columns
    assert len(df) == 3, f'應解析出 3 列,實際 {len(df)}'


def test_moneydj_latest_row_matches_real_values(monkeypatch):
    """2026/07/01 那列(user 實測 HTML)須精確對上 wantgoo 真值:
    淨值=109.69 / 市價=109.35 / 折溢價%=-0.31(負值 <span class="negative"> 包裹須正確解出)。"""
    _patch_moneydj_only(monkeypatch)
    df = ef.fetch_etf_nav_history('0050.TW', days=35)
    _latest = df.sort_values('date').iloc[-1]
    assert _latest['date'] == datetime.date(2026, 7, 1)
    assert _latest['nav'] == pytest.approx(109.69)
    assert _latest['price'] == pytest.approx(109.35)
    assert _latest['premium_pct'] == pytest.approx(-0.31)


def test_moneydj_positive_premium_row_parsed(monkeypatch):
    """06/30 那列(正值折溢價,無 <span> 包裹)也須正確解析 —— 不只負值情境。"""
    _patch_moneydj_only(monkeypatch)
    df = ef.fetch_etf_nav_history('0050.TW', days=35)
    _row_0630 = df[df['date'] == datetime.date(2026, 6, 30)].iloc[0]
    assert _row_0630['nav'] == pytest.approx(106.74)
    assert _row_0630['price'] == pytest.approx(107.80)
    assert _row_0630['premium_pct'] == pytest.approx(0.99)


def test_moneydj_same_row_values_are_self_consistent():
    """回歸守衛(不觸網,純邏輯驗算):同一列的 nav/price/premium_pct 必須同源同日,
    驗算 premium_pct ≈ (price-nav)/nav*100 —— 這正是本次 bug 的核心(舊 regex 拿
    MoneyDJ 的 nav 配 yfinance 的 price,兩者不同源同日,導致 07/01 出現假 2.45%)。"""
    _rows = [
        (109.69, 109.35, -0.31),
        (106.74, 107.80, 0.99),
        (104.03, 104.45, 0.40),
    ]
    for _nav, _price, _prem in _rows:
        _calc = round((_price - _nav) / _nav * 100, 2)
        assert _calc == pytest.approx(_prem, abs=0.02), (
            f'nav={_nav} price={_price} 驗算折溢價 {_calc}% 應約等於頁面標示 {_prem}%'
        )


def test_moneydj_malformed_row_skipped(monkeypatch):
    """非日期起頭的列(如表頭 <th> 或欄數不對的雜訊列)須被安全跳過,不誤判/不炸例外。"""
    _bad_html = '''
    <html><body><table>
    <tr><th>日期</th><th>淨值</th><th>市價</th><th>折溢價(%)</th></tr>
    <tr><td class="col07">N/A</td><td class="col08">--</td>
        <td class="col09">--</td><td class="col09">--</td></tr>
    <tr><td class="col07">2026/07/01</td><td class="col08">109.6900</td>
        <td class="col09">109.3500</td><td class="col09">-0.31</td></tr>
    </table></body></html>
    '''
    from src.data.proxy import proxy_helper as _ph  # v19.74:同 _patch_moneydj_only,patch 持有者非 package

    class _FR:
        status_code = 200
        text = _bad_html

    monkeypatch.setattr(ef.st, 'secrets', _FakeSecrets(), raising=False)

    def _fake_fetch_url(url, *a, **k):
        return _FR() if 'Basic0003' in url else None
    monkeypatch.setattr(_ph, 'fetch_url', _fake_fetch_url)
    ef.fetch_etf_nav_history.clear()
    df = ef.fetch_etf_nav_history('0050.TW', days=35)
    assert len(df) == 1, '雜訊列(非日期/非數字)應被跳過,只留 1 筆有效資料'
    assert df.iloc[0]['nav'] == pytest.approx(109.69)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
