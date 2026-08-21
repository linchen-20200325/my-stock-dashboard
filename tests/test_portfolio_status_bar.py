"""P3a(v19.207 順暢化)—— 全域「🔗 我的組合」狀態列守衛。

L3 get_binding_state 三態判定 + 降級;L5 標籤 + render 分支 + 不炸整頁;app.py 掛載。
"""
from __future__ import annotations

from pathlib import Path

import src.services.portfolio_binding_service as svc
import src.ui.tabs.portfolio_status_bar as bar

_REPO = Path(__file__).resolve().parents[1]


# ── L3:get_binding_state 三態 + graceful degrade(monkeypatch L1)──────────
def _patch_gsp(monkeypatch, *, logged, sid, portfolios):
    import src.data.portfolio.gsheet_portfolio as gsp

    def _tok():
        if isinstance(logged, Exception):
            raise logged
        return logged
    monkeypatch.setattr(gsp, '_has_oauth_tokens', _tok)
    monkeypatch.setattr(gsp, '_get_active_sheet_id', lambda: sid)

    def _list(*a, **k):
        if isinstance(portfolios, Exception):
            raise portfolios
        return portfolios
    monkeypatch.setattr(gsp, 'list_portfolios', _list)


def test_binding_state_unbound_when_not_logged_in(monkeypatch):
    _patch_gsp(monkeypatch, logged=False, sid='ABC', portfolios=['a'])
    bs = svc.get_binding_state()
    assert bs.status == svc.STATUS_UNBOUND      # 未登入 → 一律 unbound(即使 ?sheet= 有值)
    assert bs.logged_in is False


def test_binding_state_unbound_when_no_sheet(monkeypatch):
    _patch_gsp(monkeypatch, logged=True, sid='', portfolios=['a'])
    bs = svc.get_binding_state()
    assert bs.status == svc.STATUS_UNBOUND
    assert bs.logged_in is True


def test_binding_state_bound_empty(monkeypatch):
    _patch_gsp(monkeypatch, logged=True, sid='SHEET1', portfolios=[])
    bs = svc.get_binding_state()
    assert bs.status == svc.STATUS_BOUND_EMPTY
    assert bs.portfolio_count == 0              # 空表:0(明確)而非 None


def test_binding_state_bound_with_data(monkeypatch):
    _patch_gsp(monkeypatch, logged=True, sid='SHEET1', portfolios=['核心', '衛星'])
    bs = svc.get_binding_state()
    assert bs.status == svc.STATUS_BOUND
    assert bs.portfolio_count == 2
    assert bs.sheet_id == 'SHEET1'


def test_binding_state_degrades_when_list_fails(monkeypatch):
    """§1:list_portfolios 失敗 → 中性 bound + count=None(不腦補 0、不炸)。"""
    _patch_gsp(monkeypatch, logged=True, sid='SHEET1',
               portfolios=RuntimeError('quota'))
    bs = svc.get_binding_state()
    assert bs.status == svc.STATUS_BOUND
    assert bs.portfolio_count is None          # 讀不到 → 未知,不是 0


def test_binding_state_token_check_failure_is_logged_out(monkeypatch):
    _patch_gsp(monkeypatch, logged=RuntimeError('boom'), sid='ABC', portfolios=['a'])
    bs = svc.get_binding_state()
    assert bs.status == svc.STATUS_UNBOUND      # token 讀取失敗 → 視為未登入(不假裝已登入)
    assert bs.logged_in is False


# ── L5:_label_for 純函式三態 ────────────────────────────────────────────
def test_label_for_three_states():
    B = svc.BindingState
    assert '🟢' in bar._label_for(B(True, 'SHEETID12345678xx', 3, svc.STATUS_BOUND))[0]
    assert '3 本' in bar._label_for(B(True, 'S', 3, svc.STATUS_BOUND))[0]
    assert '🟡' in bar._label_for(B(True, 'S', 0, svc.STATUS_BOUND_EMPTY))[0]
    assert '⚪' in bar._label_for(B(False, '', None, svc.STATUS_UNBOUND))[0]


# ── L5:render 分支 + 不炸整頁(fake st)────────────────────────────────
class _NullCtx:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _FakeSt:
    def __init__(self):
        self.calls = []

    def popover(self, label, help=None, use_container_width=False):
        self.calls.append(('popover', label))
        return _NullCtx()

    def caption(self, *a, **k):
        self.calls.append(('caption', a))

    def markdown(self, *a, **k):
        self.calls.append(('markdown', a))

    def info(self, *a, **k):
        self.calls.append(('info', a))


def _wire_bar(monkeypatch, bs):
    fst = _FakeSt()
    monkeypatch.setattr(bar, 'st', fst)
    monkeypatch.setattr(svc, 'get_binding_state', lambda: bs)
    _binder_calls = {'n': 0}
    import src.ui.tabs.portfolio_binder as pb
    monkeypatch.setattr(pb, 'render_holdings_binder',
                        lambda *a, **k: _binder_calls.__setitem__('n', _binder_calls['n'] + 1))
    return fst, _binder_calls


def test_render_unbound_opens_binder(monkeypatch):
    fst, binder = _wire_bar(monkeypatch, svc.BindingState(False, '', None, svc.STATUS_UNBOUND))
    bar.render_portfolio_status_bar()
    assert any(c[0] == 'popover' for c in fst.calls)
    assert binder['n'] == 1, '未綁 → popover 內就地開 binder'


def test_render_bound_shows_sheet_and_switch(monkeypatch):
    fst, binder = _wire_bar(monkeypatch, svc.BindingState(True, 'SHEET_XYZ', 2, svc.STATUS_BOUND))
    bar.render_portfolio_status_bar()
    _txt = ' '.join(str(c) for c in fst.calls)
    assert 'SHEET_XYZ' in _txt, '已綁 → 顯示目前 Sheet'
    assert binder['n'] == 1, '已綁 → 仍提供換一本(binder)'


def test_render_never_crashes_page(monkeypatch):
    """§1:狀態列讀取失敗是全域 chrome → 誠實吞 + 不畫,不得炸整頁。"""
    fst = _FakeSt()
    monkeypatch.setattr(bar, 'st', fst)

    def _boom():
        raise RuntimeError('svc down')
    monkeypatch.setattr(svc, 'get_binding_state', _boom)

    bar.render_portfolio_status_bar()          # 不應 raise
    assert not any(c[0] == 'popover' for c in fst.calls)   # 失敗 → 不畫


# ── app.py 掛載守衛:狀態列在總經指南針之前 ──────────────────────────────
def test_app_mounts_status_bar_before_compass():
    src = (_REPO / 'app.py').read_text(encoding='utf-8')
    assert 'render_portfolio_status_bar()' in src, 'app.py 應掛載全域組合狀態列'
    assert src.index('render_portfolio_status_bar()') < src.index('render_macro_compass()'), \
        '狀態列應在標題下、總經指南針之上'
