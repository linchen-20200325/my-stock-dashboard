"""find_diversifiers_by_category:分散度按 ETF 大類分組(每類前 N)測試。"""
import math

import pandas as pd

from src.compute.etf.etf_smart_analysis import find_diversifiers_by_category


def _make_pivot():
    dates = pd.date_range('2025-01-01', periods=40, freq='D')
    cols = {}
    # 0050(市值型輸入)+ 各類候選:00679B 債券 / 0056+00878 高股息 / 006208 市值型
    for i, tk in enumerate(['0050.TW', '00679B.TW', '0056.TW', '006208.TW', '00878.TW']):
        cols[tk] = [100 + i * 10 + math.sin((j + i * 2) / 3.0) * 6 for j in range(40)]
    return pd.DataFrame(cols, index=dates)


def test_returns_dict_grouped_by_category():
    out = find_diversifiers_by_category('0050.TW', _make_pivot(), {}, per_category=10)
    assert isinstance(out, dict) and out, '應回非空 dict'
    for cat, df in out.items():
        assert not df.empty
        assert '分散指數' in df.columns
        assert '0050.TW' not in set(df['ticker']), f'{cat} 不應含輸入自己'


def test_bond_category_contains_bond_etf():
    out = find_diversifiers_by_category('0050.TW', _make_pivot(), {}, per_category=10)
    assert '債券' in out, '債券類應有成員入榜'
    assert '00679B.TW' in set(out['債券']['ticker'])


def test_per_category_limit():
    out = find_diversifiers_by_category('0050.TW', _make_pivot(), {}, per_category=1)
    for df in out.values():
        assert len(df) <= 1


def test_empty_pivot_returns_empty_dict():
    assert find_diversifiers_by_category('0050.TW', pd.DataFrame(), {}) == {}
