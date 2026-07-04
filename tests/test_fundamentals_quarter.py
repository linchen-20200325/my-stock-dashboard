"""latest_published_quarter 邊界測試(純函式,依台股財報公告截止日推算季別)。"""
import datetime

from scripts.update_fundamentals_snapshot import latest_published_quarter


def _q(y, m, d):
    return latest_published_quarter(datetime.date(y, m, d))


def test_quarter_boundaries_2026():
    # Q1 公布 5/15 前 → 仍是去年年報(民國114 Q4)
    assert _q(2026, 5, 14) == (114, 4)
    # 5/15 起 → 民國115 Q1
    assert _q(2026, 5, 15) == (115, 1)
    # 8/14 起 → Q2
    assert _q(2026, 8, 14) == (115, 2)
    # 11/14 起 → Q3
    assert _q(2026, 11, 14) == (115, 3)


def test_year_annual_and_pre_annual():
    # 3/31 起 → 去年年報(民國114 Q4)
    assert _q(2026, 3, 31) == (114, 4)
    # 年初(年報未出)→ 去年 Q3(民國114 Q3)
    assert _q(2026, 1, 10) == (114, 3)
    assert _q(2026, 3, 30) == (114, 3)


def test_roc_year_conversion():
    # 西元 2026 → 民國 115
    ry, _ = _q(2026, 6, 1)
    assert ry == 115
