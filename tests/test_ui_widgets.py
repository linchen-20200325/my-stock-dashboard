"""ui_widgets.py 純函式 unit test — Phase 7F（首批：cond_badge）。"""
from __future__ import annotations

from ui_widgets import cond_badge


class TestCondBadge:
    def test_returns_string(self):
        assert isinstance(cond_badge(True, 'OK'), str)

    def test_truthy_uses_green(self):
        # ok=True → 綠色 #3fb950
        html = cond_badge(True, 'A 已達成')
        assert '#3fb950' in html
        assert '#484f58' not in html

    def test_falsy_uses_gray(self):
        # ok=False → 灰色 #484f58
        html = cond_badge(False, 'B 未達成')
        assert '#484f58' in html
        assert '#3fb950' not in html

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
