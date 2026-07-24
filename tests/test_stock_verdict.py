"""tests/test_stock_verdict.py — v19.167 守衛:個股頁頂『一眼判讀』綜合結論。

`summarize_stock_verdict` 純聚合 compute_stock_section_levels 的 4 個可評定桶
(進場RS/健康/籌碼/先行),回單一 level+verdict+理由。對稱 ETF 🚦 卡 / 組合排行 headline。
§1:on-demand 的 financials/ai gray 桶不納入(不偽造);§4.3:理由=桶 headline,零重算。
"""
from __future__ import annotations

from shared.stock_buckets import compute_stock_section_levels, summarize_stock_verdict


def test_all_strong_is_green_偏多():
    lv = compute_stock_section_levels(
        health=85, rs_val=80, chips_sig='吸籌', chips_con=60,
        li_green=5, li_yellow=0, li_red=0)
    v = summarize_stock_verdict(lv, trend_label='🟢 強勢多頭')
    assert v['level'] == 'green' and '偏多' in v['verdict']
    assert v['counts'][2] == 0                      # 無紅
    assert v['reasons'] and len(v['reasons']) == 4  # 4 桶 headline 都在
    assert v['trend_label'] == '🟢 強勢多頭'          # 趨勢透傳


def test_red_dominant_is_red_保守():
    lv = compute_stock_section_levels(
        health=40, rs_val=30, chips_sig='倒貨', chips_con=70,
        li_green=0, li_yellow=1, li_red=4)
    v = summarize_stock_verdict(lv)
    assert v['level'] == 'red' and '保守' in v['verdict']
    assert v['counts'][2] >= 2


def test_on_demand_gray_buckets_excluded_not_faked():
    """§1:financials/ai 永遠 gray(on-demand)→ 不得被當成任何燈納入計數。"""
    lv = compute_stock_section_levels(health=85, rs_val=80, chips_sig='吸籌',
                                      li_green=5, li_yellow=0, li_red=0)
    v = summarize_stock_verdict(lv)
    # 只 4 桶可評定(entry/tech/chips/fundamental),financials+ai 兩 gray 不算
    assert v['n'] == 4
    assert sum(v['counts']) == 4


def test_all_gray_returns_待算_not_green():
    """資料全未載 → gray「資料待算」,§1 不得偽綠。"""
    v = summarize_stock_verdict(compute_stock_section_levels())
    assert v['level'] == 'gray' and v['n'] == 0
    assert v['reasons'] == []


def test_no_red_but_yellow_majority_is_yellow_觀望():
    """無紅但綠不過半(綠≤黃)→ 中性觀望,不硬升綠。"""
    lv = compute_stock_section_levels(
        health=85, rs_val=60, chips_sig='中性',   # green, yellow(RS 50~75), yellow
        li_green=3, li_yellow=1, li_red=0)         # fundamental yellow(有黃)
    v = summarize_stock_verdict(lv)
    # g=1(tech), y=3(entry+chips+fundamental), r=0 → g 不 > y → yellow
    assert v['level'] == 'yellow' and '觀望' in v['verdict']
    assert v['counts'][2] == 0


def test_reasons_are_headlines_no_recompute():
    """§4.3:理由必須直接來自桶 headline,不另算數字。"""
    lv = compute_stock_section_levels(health=90, rs_val=88, chips_sig='吸籌',
                                      li_green=6, li_yellow=0, li_red=0)
    v = summarize_stock_verdict(lv)
    assert any('健康度 90' in r for r in v['reasons'])
    assert any('RS 相對強度 88' in r for r in v['reasons'])


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
