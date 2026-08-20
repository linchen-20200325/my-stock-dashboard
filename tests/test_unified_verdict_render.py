"""統一裁決徽章 render(L4)golden test(v19.201)。純字串,無 streamlit。"""
from __future__ import annotations

from shared.unified_verdict_thresholds import (
    PROFILE_DIVIDEND_HOLD,
    PROFILE_TRADING,
)
from src.compute.scoring.unified_verdict import assess_unified
from src.ui.render.unified_verdict_render import render_unified_verdict_html


def test_keep_badge_has_label_and_axes():
    v = assess_unified(profile=PROFILE_TRADING, technical_health=90,
                       fundamental_grade='A')
    html = render_unified_verdict_html(v)
    assert '🟢 續抱' in html
    assert '技術面' in html and '基本面' in html
    assert '（主）' in html                     # 主軸標記


def test_na_badge_shows_coverage_note():
    v = assess_unified(profile=PROFILE_DIVIDEND_HOLD,
                       fundamental_grade=None, technical_health=95)
    html = render_unified_verdict_html(v)
    assert '⚪ 無法評分' in html
    assert '主軸資料不足' in html                # §1 誠實揭露


def test_divergence_rendered():
    v = assess_unified(profile=PROFILE_DIVIDEND_HOLD,
                       fundamental_grade='A', technical_health=40)
    html = render_unified_verdict_html(v)
    assert '⚠️ 背離' in html


def test_valuation_is_shown_as_independent_axis():
    v = assess_unified(profile=PROFILE_TRADING, technical_health=90,
                       valuation_label='🟢便宜')
    html = render_unified_verdict_html(v)
    assert '🟢便宜' in html
    assert '獨立軸' in html


def test_float_composite_value_formatted():
    from shared.unified_verdict_thresholds import PROFILE_ETF
    v = assess_unified(profile=PROFILE_ETF, etf_composite=0.7231)
    html = render_unified_verdict_html(v)
    assert '0.72' in html                        # float 2 位
