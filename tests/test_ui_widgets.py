"""src/ui/render/ui_widgets.py 純函式 unit test — Phase 7F（cond_badge）+ Phase 7G（其餘 9 函式 + 常數補測）。

v19.174 去識別化：`_STRATEGY_MAP`（10 個人名 key）已刪除，本檔改測新契約
`STRATEGY_VALUATION/FINANCIAL/TECHNICAL` + `_STRATEGY_ICON`，函式名亦改為
`strategy_box` / `strategy_conclusion`。另新增 `TestNoPersonNameInSource`
守衛，防止人名被加回原始碼。
"""
from __future__ import annotations

from pathlib import Path

from src.ui.render import (
    STRATEGY_FINANCIAL,
    STRATEGY_TECHNICAL,
    STRATEGY_VALUATION,
    TERM_EXPLAIN,
    _STRATEGY_ICON,
    _to_strategy,
    beginner_kpi,
    cond_badge,
    explain_box,
    kpi,
    show_term_help,
    signal_box,
    strategy_box,
    strategy_conclusion,
    traffic_light,
    ui_widgets,
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
        # v19.176 P0-C:原本斷言 '全市場健康度' —— 該名稱已**退役**並登記於
        # ui_widgets.BREADTH_DEPRECATED_TITLES。退役理由:它同時被貼在三個不同
        # 的量上(旌旗 5 日均 / 當日上漲佔比 / 綜合健康度),且「旌旗＝站上 20MA
        # 家數比」這個舊描述是捏造的 —— 全 repo 沒有任何 code 在算站上均線家數
        # 比,真實公式是「上漲佔比的 5 日均」(src/services/jingqi_calc.py:43)。
        # 這條測試原本正好釘住那個錯名,故一併改釘新的 nickname。
        assert '廣度 5 日均' in html

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
    def test_strategy1_valuation(self):
        # 策略1 = 估值 / 存股
        assert _to_strategy(STRATEGY_VALUATION) == ('策略1', '💡')

    def test_strategy2_financial(self):
        # 策略2 = 財報體檢
        assert _to_strategy(STRATEGY_FINANCIAL) == ('策略2', '🏥')

    def test_strategy3_technical(self):
        # 策略3 = 技術 / 動能 / 資金面
        assert _to_strategy(STRATEGY_TECHNICAL) == ('策略3', '🎯')

    def test_constants_are_the_display_codes(self):
        # caller 一律傳這三個常數；常數值本身就是畫面標籤
        assert STRATEGY_VALUATION == '策略1'
        assert STRATEGY_FINANCIAL == '策略2'
        assert STRATEGY_TECHNICAL == '策略3'

    def test_unknown_fallback(self):
        # v19.174：漏改的 caller 不該 KeyError，而是退化成通用標籤 ——
        # 畫面上的 👤 就是「還沒改乾淨」的可見訊號（§1 降級要看得見）。
        label, icon = _to_strategy('尚未遷移的字串')
        assert label == '策略'
        assert icon == '👤'

    def test_empty_string_does_not_raise(self):
        assert _to_strategy('') == ('策略', '👤')

    def test_returns_2tuple(self):
        out = _to_strategy(STRATEGY_VALUATION)
        assert isinstance(out, tuple)
        assert len(out) == 2
        assert all(isinstance(x, str) for x in out)

    def test_strategy_icon_structure(self):
        # 防呆：常數結構一致（key = 策略代號、value = 非空 icon 字串）
        assert set(_STRATEGY_ICON) == {
            STRATEGY_VALUATION, STRATEGY_FINANCIAL, STRATEGY_TECHNICAL,
        }
        for code, icon in _STRATEGY_ICON.items():
            assert code in ('策略1', '策略2', '策略3')
            assert isinstance(icon, str) and icon


class TestStrategyBox:
    def test_returns_string(self):
        assert isinstance(strategy_box('💰', STRATEGY_VALUATION, '估值偏低'), str)

    def test_logic_embedded(self):
        html = strategy_box('💰', STRATEGY_VALUATION, '估值合理可買')
        assert '估值合理可買' in html

    def test_known_strategy_uses_strategy_label(self):
        html = strategy_box('💰', STRATEGY_VALUATION, '邏輯')
        assert '策略1' in html
        # icon 一律取自 _STRATEGY_ICON，第一參數目前不參與渲染
        assert '💡' in html

    def test_unknown_strategy_fallback(self):
        html = strategy_box('💰', '未登記代號', '邏輯')
        assert '策略' in html  # fallback label
        assert '👤' in html    # fallback icon

    def test_html_structure(self):
        html = strategy_box('💰', STRATEGY_VALUATION, '邏輯')
        assert html.startswith('<div class=')
        assert html.endswith('</div>')

    def test_legacy_alias_still_points_to_new_fn(self):
        # v19.174 過渡期 alias；待 ui_widgets 檔尾 alias 移除時連同本測試刪除
        assert ui_widgets.teacher_box is ui_widgets.strategy_box


class TestStrategyConclusion:
    def test_returns_string(self):
        out = strategy_conclusion(STRATEGY_TECHNICAL, '費半 7837', '半導體強勢')
        assert isinstance(out, str)

    def test_positive_keyword_red(self):
        # 「強勢」是正面關鍵字 → 台股慣例紅色 #da3633
        html = strategy_conclusion(STRATEGY_TECHNICAL, '費半 7837', '半導體強勢')
        assert '#da3633' in html

    def test_negative_keyword_green(self):
        # 「警戒」是負面關鍵字 → 台股慣例綠色 #2ea043
        html = strategy_conclusion(STRATEGY_TECHNICAL, 'PMI 45', '景氣警戒')
        assert '#2ea043' in html

    def test_neutral_default_yellow(self):
        # 既非正面也非負面 → 黃色 TRAFFIC_YELLOW #eab308
        html = strategy_conclusion(STRATEGY_TECHNICAL, '中性指標', '持平觀察')
        assert '#eab308' in html

    def test_manual_color_overrides(self):
        html = strategy_conclusion(STRATEGY_TECHNICAL, 'X', '強勢', color='#000fff')
        assert '#000fff' in html
        # 不應再自動套紅
        assert '#da3633' not in html

    def test_action_appended_when_provided(self):
        html = strategy_conclusion(STRATEGY_TECHNICAL, 'X', '持平', action='留意風險')
        assert '留意風險' in html
        assert '，留意風險' in html

    def test_action_omitted_when_empty(self):
        html = strategy_conclusion(STRATEGY_TECHNICAL, 'X', '持平', action='')
        # 不應有開頭的「，」
        assert '，' not in html.split('</span>')[-2]

    def test_action_keyword_triggers_color(self):
        # 結論中性，但 action 帶正面詞 → 仍紅
        html = strategy_conclusion(STRATEGY_TECHNICAL, 'X', '持平', action='可加碼')
        assert '#da3633' in html

    def test_strategy_label_and_icon_embedded(self):
        html = strategy_conclusion(STRATEGY_FINANCIAL, 'X', 'Y')
        assert '策略2' in html
        assert '🏥' in html

    def test_unknown_strategy_fallback(self):
        html = strategy_conclusion('未登記代號', 'X', 'Y')
        assert '策略' in html
        assert '👤' in html

    def test_indicator_and_conclusion_embedded(self):
        html = strategy_conclusion(
            STRATEGY_TECHNICAL, '費半 7837(+0.5%)', '半導體強勢', action='台股多方加分')
        assert '費半 7837(+0.5%)' in html
        assert '半導體強勢' in html
        assert '台股多方加分' in html

    def test_legacy_alias_still_points_to_new_fn(self):
        # v19.174 過渡期 alias；待 ui_widgets 檔尾 alias 移除時連同本測試刪除
        assert ui_widgets.teacher_conclusion is ui_widgets.strategy_conclusion


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


class TestNoPersonNameInSource:
    """v19.174 去識別化守衛 —— `ui_widgets.py` 原始碼不得再出現任何人名。

    背景：改版前畫面上其實看不到人名（`_to_strategy()` 會把人名翻成
    策略1/2/3），**但原始碼裡有** —— `_STRATEGY_MAP` 的 10 個 key 就是
    真實人名，且每個 caller 都在傳人名字串。user 2026-08-05 要求整份移除，
    本測試負責防止未來有人再加回去（review 容易漏看、但這條會紅）。
    """

    # ⚠️ 這是**守衛黑名單**，刻意保留的檢查清單，不是去識別化殘留 ——
    #    全 repo 掃人名時請跳過本區塊（v19.174 AI-D 收尾註記）。
    _BANNED = ('孫慶龍', '郭俊宏', '林明樟', '蔡森', '春哥',
               '弘爺', '妮可', '朱家泓', '宏爺')

    def test_ui_widgets_source_has_no_person_name(self):
        src = Path(ui_widgets.__file__).read_text(encoding='utf-8')
        hit = [n for n in self._BANNED if n in src]
        assert not hit, f'ui_widgets.py 殘留人名：{hit}'

    def test_rendered_html_has_no_person_name(self):
        # 實際輸出也掃一次，防止人名被塞進 icon / label 而非常數表
        for code in (STRATEGY_VALUATION, STRATEGY_FINANCIAL, STRATEGY_TECHNICAL):
            html = (strategy_conclusion(code, '指標 1', '結論', action='行動')
                    + strategy_box('x', code, '邏輯'))
            hit = [n for n in self._BANNED if n in html]
            assert not hit, f'{code} 輸出殘留人名：{hit}'
