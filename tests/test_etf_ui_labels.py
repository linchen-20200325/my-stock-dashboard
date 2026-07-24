"""tests/test_etf_ui_labels.py — v19.166 守衛:ETF UI 標籤 SSOT(同指標一個名 + 兩套評分正名)。"""
from __future__ import annotations

from shared.etf_ui_labels import ETF_METRIC_LABELS, etf_label


def test_labels_nonempty_and_unique():
    vals = list(ETF_METRIC_LABELS.values())
    assert all(v.strip() for v in vals), '有空標籤'
    assert len(vals) == len(set(vals)), '標籤重複 → 違反「同指標一個名」SSOT 目的'


def test_two_star_scores_named_apart():
    """兩套評分不可同名:體質星等(4因子) ≠ 綜合評等(7維)。"""
    assert ETF_METRIC_LABELS['quality_stars'] != ETF_METRIC_LABELS['composite']
    assert '星等' in ETF_METRIC_LABELS['quality_stars']
    assert '評等' in ETF_METRIC_LABELS['composite']


def test_etf_label_fallback_no_fabrication():
    assert etf_label('total_ret_1y') == '近1年含息報酬'
    assert etf_label('__missing__', '—') == '—'
    assert etf_label('__missing__') == '__missing__'   # 無 default → 回 key,不腦補
