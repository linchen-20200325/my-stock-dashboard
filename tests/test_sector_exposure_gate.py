"""tests/test_sector_exposure_gate.py — 產業曝險上限檢查:未對映 ETF 不得亮假紅燈。

回歸 §1:對映不到單一 GICS 類股的主動/廣泛型 ETF 歸「其他」收容桶,**不得**被當成
「單一類股集中 100%」觸發紅色「超限」。實機 bug:使用者 7 檔主動 ETF 全落「其他」→
誤報「其他 100% 超限、建議分散」(與事實相反——這些 ETF 本身已高度分散)。
"""
from __future__ import annotations

import pytest


def _rows(*specs):
    return [{'ticker': t, 'current_value': float(v)} for t, v in specs]


def _capture(monkeypatch):
    import src.ui.render.etf_render as R
    boxes: list[tuple[str, str]] = []
    monkeypatch.setattr(R, '_colored_box',
                        lambda text, color='green': boxes.append((color, text)))
    monkeypatch.setattr(R.st, 'dataframe', lambda *a, **k: None)
    return R, boxes


def test_all_unmapped_etfs_no_false_red(monkeypatch):
    """全部主動 ETF(對映不到)→ 不得亮紅『超限』,改標黃色『無法判定』。"""
    R, boxes = _capture(monkeypatch)
    rows = _rows(('00980A.TW', 400000), ('00982A.TW', 300000),
                 ('00980D.TWO', 27990), ('00989A.TW', 50000))
    R._check_sector_exposure(rows, sum(r['current_value'] for r in rows))
    colors = [c for c, _ in boxes]
    assert 'red' not in colors, '未對映 ETF 不得觸發假『超限』紅燈'
    assert 'yellow' in colors and any('無法判定' in t for _, t in boxes)


def test_real_single_sector_concentration_still_red(monkeypatch):
    """真被對映到單一類股且 >30% → 仍須亮紅(不可因本次修改而漏報真集中)。"""
    R, boxes = _capture(monkeypatch)
    # XLK→資訊科技 佔 83% > 30% → 真集中風險
    rows = _rows(('XLK', 500000), ('XLF', 100000))
    R._check_sector_exposure(rows, 600000)
    assert any(c == 'red' for c, _ in boxes), '真單一類股集中仍須報超限'
    assert any('資訊科技' in t for c, t in boxes if c == 'red')


def test_mixed_mapped_under_limit_is_green(monkeypatch):
    """對映到的類股各 <30% + 部分未對映 → 綠燈,且註明未對映佔比未計入。"""
    R, boxes = _capture(monkeypatch)
    rows = _rows(('XLK', 100000), ('XLF', 100000), ('XLE', 100000),
                 ('XLV', 100000), ('00980A.TW', 100000))  # 各 20%
    R._check_sector_exposure(rows, 500000)
    colors = [c for c, _ in boxes]
    assert 'red' not in colors
    assert 'green' in colors
    assert any('未計入' in t for c, t in boxes if c == 'green')
