"""src/ui/render/ui_widgets.py 純函式 unit test — Phase 7F（cond_badge）+ Phase 7G（其餘 9 函式 + 常數補測）。"""
from __future__ import annotations

from src.ui.render import (
    TERM_EXPLAIN,
    _STRATEGY_MAP,
    _to_strategy,
    beginner_kpi,
    cond_badge,
    explain_box,
    kpi,
    show_term_help,
    signal_box,
    teacher_box,
    teacher_conclusion,
    traffic_light,
)


class TestCondBadge:
    def test_returns_string(self):
        assert isinstance(cond_badge(True, 'OK'), str)

    def test_truthy_uses_green(self):
        # ok=True → 綠色 #3fb950
        html = cond_badge(True, 'A 已達成')
        assert '#22c55e' in html
        assert '#484f58' not in html

    def test_falsy_uses_gray(self):
        # ok=False → 灰色 #484f58
        html = cond_badge(False, 'B 未達成')
        assert '#484f58' in html
        assert '#22c55e' not in html

    def test_label_embedded(self):
        html = cond_badge(True, '自訂條件 X=42.5')
        assert '自訂條件 X=42.5' in html

    def test_html_structure(self):
        html = cond_badge(True, 'L')
        assert html.startswith('<span ')
        assert html.endswith('</span>')
        assert 'border-radius:4px' in html
        assert 'font-size:12px' in html

    def test_zero_is_falsy(self):
        # 0 視為 False（一致於 _ring1_pass 等 boolean 邏輯）
        html = cond_badge(0, 'L')
        assert '#484f58' in html

    def test_none_is_falsy(self):
        html = cond_badge(None, 'L')
        assert '#484f58' in html

    def test_empty_label(self):
        # 空 label 仍須回合法 HTML
        html = cond_badge(True, '')
        assert html.startswith('<span ')
        assert html.endswith('</span>')


class TestTermExplain:
    def test_is_dict(self):
        assert isinstance(TERM_EXPLAIN, dict)

    def test_has_expected_terms(self):
        # 13 個常見術語
        expected = {'RSI', 'KD', 'ADL', 'VCP', 'IBS', 'M1B-M2',
                    '旌旗指數', '騰落指標', '乖離率', '多頭排列',
                    '布林通道', '量比', 'PCR'}
        assert expected.issubset(set(TERM_EXPLAIN.keys()))

    def test_each_entry_is_2tuple(self):
        # (中文名, 白話說明) 結構
        for term, val in TERM_EXPLAIN.items():
            assert isinstance(val, tuple), f'{term} 不是 tuple'
            assert len(val) == 2, f'{term} 不是 2 元 tuple'
            assert all(isinstance(v, str) and v for v in val), f'{term} 含空字串'


class TestExplainBox:
    def test_returns_string(self):
        assert isinstance(explain_box('A', 'B'), str)

    def test_term_and_simple_embedded(self):
        html = explain_box('RSI', '強弱指數')
        assert 'RSI' in html
        assert '強弱指數' in html

    def test_detail_appended_when_provided(self):
        html = explain_box('RSI', '簡單', '進階說明')
        assert '進階說明' in html
        assert '<br>' in html

    def test_detail_omitted_when_empty(self):
        html = explain_box('RSI', '簡單', '')
        assert '<br>' not in html

    def test_html_structure(self):
        html = explain_box('A', 'B')
        assert html.startswith('<div ')
        assert html.endswith('</div>')
        assert 'border-left:3px solid #58a6ff' in html


class TestTrafficLight:
    def test_returns_color_label_tuple(self):
        out = traffic_light(0, True, False, 'good', 'bad')
        assert isinstance(out, tuple)
        assert len(out) == 2

    def test_good_cond_green(self):
        color, label = traffic_light(0, True, False, '達標', '未達')
        assert color == '#22c55e'
        assert '🟢' in label
        assert '達標' in label

    def test_bad_cond_red(self):
        color, label = traffic_light(0, False, True, '達標', '未達')
        assert color == '#ef4444'
        assert '🔴' in label
        assert '未達' in label

    def test_neither_yellow_default(self):
        color, label = traffic_light(0, False, False, 'g', 'b')
        assert color == '#eab308'
        assert label == '⚪ 觀察'

    def test_custom_neutral_label(self):
        color, label = traffic_light(0, False, False, 'g', 'b', neutral_label='🟡 中性')
        assert label == '🟡 中性'

    def test_good_takes_precedence_over_bad(self):
        # 兩個 cond 同時 True，good 優先
        color, label = traffic_light(0, True, True, '好', '壞')
        assert color == '#22c55e'
        assert '好' in label

    def test_value_arg_unused_but_accepted(self):
        # value 目前未用，純為 API 預留位置；任何型別都應接受
        color, _ = traffic_light(None, True, False, 'g', 'b')
        assert color == '#22c55e'


class TestBeginnerKpi:
    def test_returns_string(self):
        assert isinstance(beginner_kpi('T', 'V', 'M'), str)

    def test_title_value_meaning_embedded(self):
        html = beginner_kpi('健康度', '85', '優秀')
        assert '健康度' in html
        assert '85' in html
        assert '優秀' in html

    def test_default_color(self):
        html = beginner_kpi('T', 'V', 'M')
        assert '#e6edf3' in html

    def test_custom_color(self):
        html = beginner_kpi('T', 'V', 'M', color='#ff0000')
        assert '#ff0000' in html

    def test_tip_appended_when_provided(self):
        html = beginner_kpi('T', 'V', 'M', tip='試試這個')
        assert '試試這個' in html
        assert '💡' in html

    def test_tip_omitted_when_empty(self):
        html = beginner_kpi('T', 'V', 'M', tip='')
        assert '💡' not in html

    def test_html_structure(self):
        html = beginner_kpi('T', 'V', 'M')
        assert html.startswith('<div ')
        assert html.endswith('</div>')
        assert 'text-align:center' in html


class TestShowTermHelp:
    def test_known_term_returns_html(self):
        html = show_term_help('RSI')
        assert html  # 非空
        assert 'RSI' in html
        assert '強弱指數' in html

    def test_known_term_uses_question_emoji(self):
        html = show_term_help('KD')
        assert '❓' in html

    def test_unknown_term_returns_empty(self):
        assert show_term_help('NotAnIndicator') == ''
        assert show_term_help('') == ''

    def test_chinese_term(self):
        html = show_term_help('旌旗指數')
        assert '旌旗指數' in html
        assert '全市場健康度' in html

    def test_uses_explain_box_format(self):
        # 應該複用 explain_box 包裝
        html = show_term_help('RSI')
        assert html.startswith('<div ')


class TestKpi:
    def test_returns_string(self):
        assert isinstance(kpi('T', 'V'), str)

    def test_title_value_embedded(self):
        html = kpi('股價', '420')
        assert '股價' in html
        assert '420' in html

    def test_sub_embedded(self):
        html = kpi('T', 'V', sub='漲 1%')
        assert '漲 1%' in html

    def test_default_color_and_border(self):
        html = kpi('T', 'V')
        assert '#e6edf3' in html
        assert '#21262d' in html

    def test_custom_color_and_border(self):
        html = kpi('T', 'V', color='#ff0000', border='#00ff00')
        assert '#ff0000' in html
        assert '#00ff00' in html

    def test_html_structure(self):
        html = kpi('T', 'V')
        assert html.startswith('<div ')
        assert html.endswith('</div>')


class TestToStrategy:
    def test_strategy1_teachers(self):
        # 估值 / 存股
        assert _to_strategy('孫慶龍')[0] == '策略1'
        assert _to_strategy('郭俊宏')[0] == '策略1'

    def test_strategy2_teachers(self):
        # 財報體檢
        assert _to_strategy('MJ')[0] == '策略2'
        assert _to_strategy('林明樟')[0] == '策略2'

    def test_strategy3_teachers(self):
        # 技術 / 動能 / 資金面
        for t in ('蔡森', '春哥', '弘爺', '妮可', '朱家泓', '宏爺'):
            assert _to_strategy(t)[0] == '策略3', f'{t} 未對應到策略3'

    def test_unknown_fallback(self):
        label, icon = _to_strategy('未知老師')
        assert label == '策略'
        assert icon == '👤'

    def test_returns_2tuple(self):
        out = _to_strategy('孫慶龍')
        assert isinstance(out, tuple)
        assert len(out) == 2
        assert all(isinstance(x, str) for x in out)

    def test_strategy_map_structure(self):
        # 防呆：常數結構一致
        for teacher, val in _STRATEGY_MAP.items():
            assert isinstance(val, tuple) and len(val) == 2
            assert val[0] in ('策略1', '策略2', '策略3')


class TestTeacherBox:
    def test_returns_string(self):
        assert isinstance(teacher_box('💰', '孫慶龍', '估值偏低'), str)

    def test_logic_embedded(self):
        html = teacher_box('💰', '孫慶龍', '估值合理可買')
        assert '估值合理可買' in html

    def test_known_teacher_uses_strategy_label(self):
        html = teacher_box('💰', '孫慶龍', '邏輯')
        assert '策略1' in html

    def test_unknown_teacher_fallback(self):
        html = teacher_box('💰', '不存在老師', '邏輯')
        assert '策略' in html  # fallback label
        assert '👤' in html    # fallback icon

    def test_html_structure(self):
        html = teacher_box('💰', '孫慶龍', '邏輯')
        assert html.startswith('<div ')
        assert 'teacher-card' in html


class TestTeacherConclusion:
    def test_returns_string(self):
        out = teacher_conclusion('蔡森', '費半 7837', '半導體強勢')
        assert isinstance(out, str)

    def test_positive_keyword_red(self):
        # 「強勢」是正面關鍵字 → 台股慣例紅色 #da3633
        html = teacher_conclusion('蔡森', '費半 7837', '半導體強勢')
        assert '#da3633' in html

    def test_negative_keyword_green(self):
        # 「警戒」是負面關鍵字 → 台股慣例綠色 #2ea043
        html = teacher_conclusion('蔡森', 'PMI 45', '景氣警戒')
        assert '#2ea043' in html

    def test_neutral_default_yellow(self):
        # 既非正面也非負面 → 黃色 #d29922
        html = teacher_conclusion('蔡森', '中性指標', '持平觀察')
        assert '#eab308' in html

    def test_manual_color_overrides(self):
        html = teacher_conclusion('蔡森', 'X', '強勢', color='#000fff')
        assert '#000fff' in html
        # 不應再自動套紅
        assert '#da3633' not in html

    def test_action_appended_when_provided(self):
        html = teacher_conclusion('蔡森', 'X', '持平', action='留意風險')
        assert '留意風險' in html
        assert '，留意風險' in html

    def test_action_omitted_when_empty(self):
        html = teacher_conclusion('蔡森', 'X', '持平', action='')
        # 不應有開頭的「，」
        assert '，' not in html.split('</span>')[-2]

    def test_action_keyword_triggers_color(self):
        # 結論中性，但 action 帶正面詞 → 仍紅
        html = teacher_conclusion('蔡森', 'X', '持平', action='可加碼')
        assert '#da3633' in html

    def test_unknown_teacher_fallback(self):
        html = teacher_conclusion('不存在', 'X', 'Y')
        assert '策略' in html
        assert '👤' in html

    def test_indicator_and_conclusion_embedded(self):
        html = teacher_conclusion('蔡森', '費半 7837(+0.5%)', '半導體強勢', action='台股多方加分')
        assert '費半 7837(+0.5%)' in html
        assert '半導體強勢' in html
        assert '台股多方加分' in html


class TestSignalBox:
    def test_returns_string(self):
        assert isinstance(signal_box('L', 'green'), str)

    def test_green_color(self):
        html = signal_box('OK', 'green')
        assert '#22c55e' in html
        assert '#0d2818' in html

    def test_red_color(self):
        html = signal_box('Danger', 'red')
        assert '#ef4444' in html
        assert '#2a0d0d' in html

    def test_yellow_color(self):
        html = signal_box('Watch', 'yellow')
        assert '#eab308' in html
        assert '#2a1f00' in html

    def test_blue_color(self):
        html = signal_box('Info', 'blue')
        assert '#58a6ff' in html
        assert '#0d1b2a' in html

    def test_unknown_color_fallback(self):
        html = signal_box('L', 'purple')
        # fallback: ('#161b22', '#8b949e')
        assert '#161b22' in html
        assert '#8b949e' in html

    def test_label_embedded(self):
        html = signal_box('我的標籤', 'green')
        assert '我的標籤' in html

    def test_desc_embedded(self):
        html = signal_box('L', 'green', desc='額外說明')
        assert '額外說明' in html

    def test_empty_desc_still_valid_html(self):
        html = signal_box('L', 'green', desc='')
        assert html.startswith('<div ')
        assert html.endswith('</div>')
