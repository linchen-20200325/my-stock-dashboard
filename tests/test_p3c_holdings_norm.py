"""P3-C(v19.199 對稱性稽核):ETF 持股重疊 Jaccard 名稱正規化 SSOT。

build_holdings_set(智慧分析) 對齊 _canonical_holding_key(多檔頁 calc_jaccard_overlap 用),
修「跨來源『台積電 (2330)』vs『台積電』同股被當兩支 → 交集低估 → 分散度高估」。
"""
from __future__ import annotations

from src.compute.etf.etf_calc import _canonical_holding_key
from src.compute.etf.etf_smart_analysis import _jaccard, build_holdings_set


def test_build_holdings_set_dedups_paren_code_across_sources():
    """跨來源「台積電 (2330)」(yfinance) 與「台積電」(Yahoo TW)須落同一 key(去括號 SSOT)。"""
    a = build_holdings_set({'台積電 (2330)': 0.3, '聯發科 (2454)': 0.2})
    b = build_holdings_set({'台積電': 0.4, '鴻海': 0.1})
    assert '台積電' in a and '台積電' in b            # 兩來源同 key
    assert (a & b) == {'台積電'}
    assert abs(_jaccard(a, b) - 1 / 3) < 1e-9         # 1 共同 / 3 聯集(修前交集=0 誤判全分散)


def test_build_holdings_set_uses_canonical_key():
    """build_holdings_set 的 key == _canonical_holding_key(與 calc_jaccard_overlap 同源)。"""
    s = build_holdings_set({'台積電 (2330)': 1.0})
    assert s == {_canonical_holding_key('台積電 (2330)')}
    assert s == {'台積電'}                             # 去括號 + lower


def test_build_holdings_set_spaces_normalized():
    """全形/半形空白正規化一致(同 _canonical_holding_key)。"""
    assert build_holdings_set({'台 積 電': 1.0}) == build_holdings_set({'台積電': 1.0})
