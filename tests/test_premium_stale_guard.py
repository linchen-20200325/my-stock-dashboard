"""tests/test_premium_stale_guard.py — v18.441 折溢價跨日錯位守衛。

production bug:0050.TW 顯示折溢價 +5.16%(🔴 嚴禁追高),但實際同日折溢價僅 -0.12%。
根因:calc_premium_discount 的 Path B2(假日兜底)在同日 inner-join 落空時,拿
「最新 NAV(過時,如 06/29≈104)」配「最新市價(當日,07/01≈109.45)」,gap<=4 就硬配 →
價在那 2 天大漲 → 假 +5.16%。修:NAV 比市價舊 ≥1 天 → 標 stale(不硬配)+ 回傳 nav_date/price_date。
"""
from __future__ import annotations

import datetime

import pandas as pd
import pytest

import src.compute.etf.etf_calc as ec


@pytest.fixture(autouse=True)
def _force_official_premium_miss(monkeypatch):
    """v18.450:本檔測試的是 calc_premium_discount 的**舊 5 段 NAV 鏈**(Path A/B/B2),
    但 v18.443 起 Path 0(fetch_etf_official_premium,MIS 官方即時源)排在最前面。
    `@st.cache_data` 的快取跨測試檔案持續存在(同一 pytest process),若
    tests/test_etf_official_premium.py 先跑並留下 0050.TW 的 mock 結果快取,本檔測試會
    在無感情況下命中該快取,而非測試原本要驗證的舊鏈邏輯 —— 曾造成 4 個測試失敗
    (單獨跑本檔會過,和其他檔一起跑全 suite 才會現形,典型測試汙染)。
    強制 Path 0 回 None,讓每個測試都乾淨落到本檔真正要測的舊鏈。"""
    monkeypatch.setattr(ec, 'fetch_etf_official_premium', lambda *a, **k: None)


def _nav_hist(dates, navs):
    return pd.DataFrame({'date': [str(d) for d in dates], 'nav': navs})


def test_stale_when_nav_older_than_price(monkeypatch):
    """0050 案:NAV 只到 3 天前、市價到今天(inner-join 落空 → B2)→ 應 stale,不得算假溢價。"""
    _today = datetime.date.today()
    _nav_day = _today - datetime.timedelta(days=3)
    monkeypatch.setattr(ec, 'fetch_etf_nav_history',
                        lambda *a, **k: _nav_hist([_nav_day], [104.03]))
    # 市價只有今天(無 nav_day)→ 同日 inner join 空 → 走 B2
    df = pd.DataFrame({'Close': [109.45]}, index=pd.to_datetime([str(_today)]))

    out = ec.calc_premium_discount({}, df, '0050.TW')
    assert out['premium_pct'] is None, f'跨日錯位應回 None(§1 寧缺勿假),不得算出假溢價:{out}'
    assert out.get('stale_nav') is True
    assert str(out.get('nav_date')) == str(_nav_day), '應回傳 NAV 最新日供 UI 標註'
    assert str(out.get('price_date')) == str(_today), '應回傳市價日供 UI 標註'


def test_same_day_pairing_correct(monkeypatch):
    """NAV 與市價同日 → 正常算折溢價(不誤判 stale)。"""
    _today = datetime.date.today()
    monkeypatch.setattr(ec, 'fetch_etf_nav_history',
                        lambda *a, **k: _nav_hist([_today], [109.58]))
    df = pd.DataFrame({'Close': [109.45]}, index=pd.to_datetime([str(_today)]))

    out = ec.calc_premium_discount({}, df, '0050.TW')
    assert out['premium_pct'] is not None, f'同日應算得折溢價:{out}'
    # (109.45 - 109.58) / 109.58 * 100 ≈ -0.12%
    assert out['premium_pct'] == pytest.approx(-0.12, abs=0.03), out
    assert out.get('stale_nav') is not True


def test_passive_etf_fake_premium_capped(monkeypatch):
    """0050 真實案(v18.442):即時來源(yfinance navPrice/goodinfo)把過時 NAV(104.03,實為
    數日前值)硬戳「今日」→ 與當日市價(109.3)同日 inner-join 成功、日期守門員全過,但算出
    假 +5.07%「嚴禁追高」。被動式上限守門員(±3%)應攔為 stale,不得顯示假溢價。"""
    _today = datetime.date.today()
    # NAV 戳今日(= price 日),值為過時 104.03 → 日期守門員 G1/G3 攔不到(日期已同日)
    monkeypatch.setattr(ec, 'fetch_etf_nav_history',
                        lambda *a, **k: _nav_hist([_today], [104.03]))
    df = pd.DataFrame({'Close': [109.3]}, index=pd.to_datetime([str(_today)]))

    out = ec.calc_premium_discount({}, df, '0050.TW')
    assert out['premium_pct'] is None, f'被動式假 +5% 應攔為 None(§1 寧缺勿假):{out}'
    assert out.get('stale_nav') is True
    assert out.get('stale_reason') == 'nav_value_stale', out
    # 保留推算值供 UI 說明「超出合理套利範圍」
    assert out.get('premium_raw') == pytest.approx(5.07, abs=0.05), out


def test_passive_premium_under_cap_still_shows(monkeypatch):
    """被動式真實小溢價(< 3% 上限)不得被誤殺 — 2% 溢價應正常顯示。"""
    _today = datetime.date.today()
    monkeypatch.setattr(ec, 'fetch_etf_nav_history',
                        lambda *a, **k: _nav_hist([_today], [100.0]))
    df = pd.DataFrame({'Close': [102.0]}, index=pd.to_datetime([str(_today)]))

    out = ec.calc_premium_discount({}, df, '0050.TW')
    assert out['premium_pct'] == pytest.approx(2.0, abs=0.02), out
    assert out.get('stale_nav') is not True


def test_relay_official_premium_wins(monkeypatch):
    """v18.443:NAS 中繼站(家用台灣 IP)抓到 TWSE 官方同 snapshot 折溢價 → 直接採用,
    不再落到會產生假溢價的 yfinance navPrice 路徑。"""
    # 中繼站命中官方值(0050 真實 -0.13%),同時讓 NAV history 回一個「會算出假溢價」的
    # 過時值,證明 path 0 優先、根本不碰後面的假溢價鏈。
    monkeypatch.setattr(ec, 'fetch_etf_official_premium',
                        lambda *a, **k: {'nav': 109.58, 'price': 109.45,
                                         'premium_pct': -0.13, 'source': 'NAS中繼:TWSE',
                                         'data_date': '2026-07-01'})
    _today = datetime.date.today()
    monkeypatch.setattr(ec, 'fetch_etf_nav_history',
                        lambda *a, **k: _nav_hist([_today], [104.03]))  # 過時假值,不該被用到
    df = pd.DataFrame({'Close': [109.3]}, index=pd.to_datetime([str(_today)]))

    out = ec.calc_premium_discount({}, df, '0050.TW')
    assert out['premium_pct'] == pytest.approx(-0.13, abs=0.001), f'應採官方 -0.13%:{out}'
    assert out.get('stale_nav') is not True
    assert out.get('data_date') == '2026-07-01'


def test_relay_official_still_capped(monkeypatch):
    """中繼站官方值若仍 > 合理上限(疑官方資料未更新)→ 仍守 §1 寧缺勿假回 stale。"""
    monkeypatch.setattr(ec, 'fetch_etf_official_premium',
                        lambda *a, **k: {'nav': 100.0, 'price': 105.0,
                                         'premium_pct': 5.0, 'source': 'NAS中繼:TWSE'})
    _today = datetime.date.today()
    df = pd.DataFrame({'Close': [105.0]}, index=pd.to_datetime([str(_today)]))
    out = ec.calc_premium_discount({}, df, '0050.TW')
    assert out['premium_pct'] is None, out
    assert out.get('stale_reason') == 'nav_value_stale'


def test_active_etf_cap_tighter_at_2pct(monkeypatch):
    """主動式(代號末碼字母,如 00982A)上限較嚴(±2%)— 2.5% 溢價即應攔 stale。"""
    _today = datetime.date.today()
    monkeypatch.setattr(ec, 'fetch_etf_nav_history',
                        lambda *a, **k: _nav_hist([_today], [100.0]))
    df = pd.DataFrame({'Close': [102.5]}, index=pd.to_datetime([str(_today)]))

    out = ec.calc_premium_discount({}, df, '00982A.TW')
    assert out['premium_pct'] is None, f'主動式 2.5% > ±2% 應攔:{out}'
    assert out.get('stale_reason') == 'nav_value_stale', out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
