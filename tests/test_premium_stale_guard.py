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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
