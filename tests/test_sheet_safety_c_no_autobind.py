"""DEC-083 C 段：取消「Drive 只有一本 Sheet 就自動綁」—— 必須使用者明確按「✅ 使用此 Sheet」。

客戶原文：「唯一本 Sheet 自動綁 取消。就算 Drive 只有一本：仍要使用者明確按『使用這本』。
不要替使用者做綁定決策。」以假 streamlit 實跑 `portfolio_binder.render_drive_picker`。
"""
from __future__ import annotations

import pytest

import src.data.portfolio.oauth_state as ost
import src.ui.tabs.portfolio_binder as pb

_P = '_t_'
_ONE = [{'id': 'ONLY_SHEET_ID_123', 'name': '我的投組'}]


class _Rerun(Exception):
    pass


class _Col:
    def __init__(self, st):
        self._st = st

    def button(self, label, key=None, **_k):
        return self._st.button(label, key=key)


class _St:
    def __init__(self, press=()):
        self.session_state = {f'{_P}sheets': list(_ONE)}
        self.query_params = {}
        self.press = set(press)
        self.calls = []

    def selectbox(self, label, options, key=None, **_k):
        return options[0]

    def columns(self, spec):
        return [_Col(self) for _ in spec]

    def button(self, label, key=None, **_k):
        self.calls.append(('button', key))
        return key in self.press

    def caption(self, *a, **k):
        self.calls.append(('caption', a))

    def info(self, *a, **k):
        self.calls.append(('info', a))

    def success(self, *a, **k):
        self.calls.append(('success', a))

    def error(self, *a, **k):
        self.calls.append(('error', a))

    def rerun(self):
        raise _Rerun


class _Gsp:
    def _has_oauth_tokens(self):
        return True

    def _get_active_sheet_id(self):
        return ''

    def list_user_folders(self):
        return []


@pytest.fixture
def run(monkeypatch):
    def _go(press=()):
        f = _St(press)
        monkeypatch.setattr(pb, 'st', f)
        monkeypatch.setattr(ost, 'st', f)
        monkeypatch.setattr(ost, 'sync_silent_marker', lambda: False)
        return f
    return _go


def test_single_sheet_listed_is_not_bound_without_pressing_use(run):
    f = run()
    pb.render_drive_picker(_Gsp(), key_prefix=_P)          # 不應 rerun、不應綁
    assert 'portfolio_sheet_id' not in f.session_state
    assert 'stock_portfolio_sheet_id' not in f.session_state
    assert f.query_params == {}
    assert ('button', f'{_P}use') in f.calls, '「✅ 使用此 Sheet」按鈕必須畫出來'


def test_single_sheet_bound_only_after_pressing_use(run):
    f = run(press={f'{_P}use'})
    with pytest.raises(_Rerun):
        pb.render_drive_picker(_Gsp(), key_prefix=_P)
    assert f.session_state['portfolio_sheet_id'] == 'ONLY_SHEET_ID_123'
    assert f.session_state['stock_portfolio_sheet_id'] == 'ONLY_SHEET_ID_123'
    assert f.query_params == {'sheet': 'ONLY_SHEET_ID_123'}
