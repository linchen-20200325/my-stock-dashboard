"""P1(v19.205 順暢化)—— 💼 戰情室空狀態就地綁定守衛。

原本無持股 → 只丟一句「請先到 📁 組合管理…」把使用者踢去別的分頁(死路)。
P1 改成**就地**三態(未登入登入 CTA / 已登入挑 Sheet / 已綁但空表誠實提示),
綁定邏輯抽 portfolio_binder(SSOT)。本檔守衛:分支正確 + 貼網址端到端 + 不再死路。
"""
from __future__ import annotations

from pathlib import Path

import pytest

import src.data.portfolio.oauth_state as _ost
import src.ui.tabs.portfolio_binder as pb

_REPO = Path(__file__).resolve().parents[1]


class _RerunSignal(Exception):
    """模擬 st.rerun 中斷本輪執行。"""


class _NullCtx:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _FakeSt:
    """記錄型假 streamlit:夠 render_holdings_binder / paste binder 用。"""

    def __init__(self, *, text_return=''):
        self.calls: list[tuple] = []
        self.session_state: dict = {}
        self.query_params: dict = {}
        self._text_return = text_return

    def markdown(self, *a, **k):
        self.calls.append(('markdown', a))

    def caption(self, *a, **k):
        self.calls.append(('caption', a))

    def success(self, *a, **k):
        self.calls.append(('success', a))

    def error(self, *a, **k):
        self.calls.append(('error', a))

    def info(self, *a, **k):
        self.calls.append(('info', a))

    def text_input(self, *a, **k):
        self.calls.append(('text_input', a))
        self.last_text_kwargs = k
        return self._text_return

    def user_types(self, raw):
        """模擬使用者在剛畫好的文字框改了文字:寫 widget 值 → 觸發 on_change(同真 Streamlit 的順序)。"""
        _k = self.last_text_kwargs
        self.session_state[_k['key']] = raw
        _k['on_change'](*_k.get('args', ()))

    def link_button(self, label, url, *, use_container_width=False, help=None,
                    type='secondary', icon=None, disabled=False):
        # 嚴格比照真 st.link_button 簽章(**無 key**)—— 若 code 誤傳 key= 會 TypeError,
        # 正是要在測試就抓到(link_button 非 stateful widget)。
        self.calls.append(('link_button', (label, url)))

    def expander(self, *a, **k):
        return _NullCtx()

    def rerun(self):
        raise _RerunSignal


class _FakeGsp:
    PORTFOLIO_SHEET_KEY = 'portfolio_sheet_id'
    STOCK_PORTFOLIO_SHEET_KEY = 'stock_portfolio_sheet_id'

    def __init__(self, *, logged: bool, active_sid: str = ''):
        self._logged = logged
        self._active = active_sid

    def _has_oauth_tokens(self) -> bool:
        return self._logged

    def _get_active_sheet_id(self) -> str:
        return self._active


# ── 分支:未登入 → 登入 CTA + 去死路引導(不叫使用者去別的分頁)────────────
def test_holdings_binder_not_logged_in_shows_login_cta(monkeypatch):
    fst = _FakeSt()
    monkeypatch.setattr(pb, 'st', fst)
    seen = {'login': 0, 'picker': 0}
    monkeypatch.setattr(pb, 'render_login_cta',
                        lambda **k: seen.__setitem__('login', seen['login'] + 1) or True)
    monkeypatch.setattr(pb, 'render_drive_picker',
                        lambda *a, **k: seen.__setitem__('picker', seen['picker'] + 1))

    pb.render_holdings_binder(_FakeGsp(logged=False), key_prefix='_station_')

    assert seen['login'] == 1, '未登入應顯示就地登入 CTA'
    assert seen['picker'] == 0, '未登入不應顯示 Drive 挑選器'
    # 去死路化:提供「不用綁表也能用」的引導(而非只叫人去 📁 組合管理)
    _txt = ' '.join(str(a) for _, a in fst.calls)
    assert '不用綁表' in _txt or '多檔比較' in _txt


# ── 分支:已登入未綁 → Drive 挑選器 + 貼網址,不畫登入 CTA ────────────────
def test_holdings_binder_logged_in_shows_picker(monkeypatch):
    fst = _FakeSt()
    monkeypatch.setattr(pb, 'st', fst)
    seen = {'login': 0, 'picker': 0, 'paste': 0}
    monkeypatch.setattr(pb, 'render_login_cta',
                        lambda **k: seen.__setitem__('login', seen['login'] + 1) or True)
    monkeypatch.setattr(pb, 'render_drive_picker',
                        lambda *a, **k: seen.__setitem__('picker', seen['picker'] + 1))
    monkeypatch.setattr(pb, 'render_paste_id_binder',
                        lambda *a, **k: seen.__setitem__('paste', seen['paste'] + 1))

    pb.render_holdings_binder(_FakeGsp(logged=True), key_prefix='_station_')

    assert seen['picker'] == 1, '已登入應顯示 Drive 挑選器'
    assert seen['paste'] == 1, '已登入應提供貼網址/ID 備援'
    assert seen['login'] == 0, '已登入不應再顯示登入 CTA'


# ── 登入 CTA:實打 link_button(嚴格簽章)→ 抓「誤傳 key=」這類 runtime bug ──────
def test_login_cta_calls_link_button_with_valid_signature(monkeypatch):
    import infra.oauth as _io
    import src.data.portfolio.oauth_state as _os
    fst = _FakeSt()
    monkeypatch.setattr(pb, 'st', fst)
    monkeypatch.setattr(_os, 'get_oauth_cfg',
                        lambda: {'client_id': 'cid', 'redirect_uri': 'https://app/'})
    monkeypatch.setattr(_os, 'get_login_state', lambda: 'nonce123')
    monkeypatch.setattr(_io, 'build_authorize_url',
                        lambda cid, ru, state: f'https://accounts.google/o?state={state}')

    ok = pb.render_login_cta(key_suffix='_station_')

    assert ok is True
    _lb = [c for c in fst.calls if c[0] == 'link_button']
    assert len(_lb) == 1, '應打一顆 Google 登入 link_button'


def test_login_cta_degrades_when_oauth_unconfigured(monkeypatch):
    """OAuth 未設定 → 誠實降級提示,不炸、回 False。"""
    import src.data.portfolio.oauth_state as _os
    fst = _FakeSt()
    monkeypatch.setattr(pb, 'st', fst)
    monkeypatch.setattr(_os, 'get_oauth_cfg', lambda: None)

    ok = pb.render_login_cta()

    assert ok is False
    assert any(c[0] == 'caption' for c in fst.calls), '未設定應有誠實提示'


# ── 端到端:貼 URL → 解析 ID → 寫兩通道 + ?sheet=(SSOT 寫入契約)───────────
# QA BLK-2(2026-10-25,有意識的修改):貼網址框改成「使用者真的改了文字(on_change)才呼叫寫入契約」——
# ~~每輪 rerun 拿 widget 回傳值呼叫契約~~ 會把剛用 Drive 選的新 Sheet 默默綁回框裡的舊值。
# 以下三支改以 `user_types()` 模擬改文字;只「畫一次」(沒改文字)的情形見 test_paste_id_binder_render_alone_writes_nothing。
_PREFIX = '_station_'


def _paste_flow(fst, raw, *, active=''):
    gsp = _FakeGsp(logged=True, active_sid=active)
    pb.render_paste_id_binder(gsp, key_prefix=_PREFIX)        # 第一輪:畫框
    fst.user_types(raw)                                        # 使用者改文字 → on_change
    pb.render_paste_id_binder(gsp, key_prefix=_PREFIX)        # 下一輪:顯示結果


def _bind(fst):
    return {k: v for k, v in fst.session_state.items()
            if k in ('portfolio_sheet_id', 'stock_portfolio_sheet_id')}


def test_paste_id_binder_parses_url_and_applies(monkeypatch):
    _url = 'https://docs.google.com/spreadsheets/d/ABC123xyz_-/edit#gid=0'
    fst = _FakeSt()
    monkeypatch.setattr(pb, 'st', fst)
    # Sheet Safety 批 B4:寫入改由 L1 `oauth_state.apply_sheet_binding`(唯一寫入契約)執行 ⇒ 它的 st 也換成同一個假物件。
    monkeypatch.setattr(_ost, 'st', fst)
    _paste_flow(fst, _url)
    assert fst.session_state['portfolio_sheet_id'] == 'ABC123xyz_-'
    assert fst.session_state['stock_portfolio_sheet_id'] == 'ABC123xyz_-'
    assert fst.query_params['sheet'] == 'ABC123xyz_-'
    assert [c[0] for c in fst.calls].count('success') == 1
    assert f'{_PREFIX}paste_sid' not in fst.session_state, '綁定一變,框的舊 widget 狀態要被丟掉(顯示現值)'


def test_paste_id_binder_render_alone_writes_nothing(monkeypatch):
    """沒改文字(只是 rerun 又畫一次)→ 一行都不寫(QA BLK-2 的根)。"""
    fst = _FakeSt(text_return='OLDSHEET1234')
    monkeypatch.setattr(pb, 'st', fst)
    monkeypatch.setattr(_ost, 'st', fst)
    for _ in range(3):
        pb.render_paste_id_binder(_FakeGsp(logged=True, active_sid='NEWSHEET5678'), key_prefix=_PREFIX)
    assert _bind(fst) == {} and fst.query_params == {}


def test_paste_id_binder_noop_when_unchanged(monkeypatch):
    """貼的 ID 與現值(兩格 + 網址)全同 → 不重設、不換代,顯示「已是目前使用的 Sheet」。"""
    fst = _FakeSt()
    fst.session_state = {'portfolio_sheet_id': 'SAME', 'stock_portfolio_sheet_id': 'SAME'}
    fst.query_params = {'sheet': 'SAME'}
    monkeypatch.setattr(pb, 'st', fst)
    monkeypatch.setattr(_ost, 'st', fst)
    _paste_flow(fst, 'SAME', active='SAME')
    assert _bind(fst) == {'portfolio_sheet_id': 'SAME', 'stock_portfolio_sheet_id': 'SAME'}
    assert fst.query_params == {'sheet': 'SAME'}
    assert ('info', (pb.ALREADY_CURRENT_MSG,)) in fst.calls


@pytest.mark.parametrize('raw', [
    'https://docs.google.com/spreadsheets/d/e/2PACX-1vQabc/pubhtml', '<script>x</script>'])
def test_paste_id_binder_rejects_publish_link_and_garbage(monkeypatch, raw):
    """B3:發布連結 / 看不懂的輸入 → 白話紅字拒絕,什麼都不寫(修前發布連結會綁成 `e`)。"""
    fst = _FakeSt()
    monkeypatch.setattr(pb, 'st', fst)
    monkeypatch.setattr(_ost, 'st', fst)
    _paste_flow(fst, raw)
    assert _bind(fst) == {} and fst.query_params == {}
    assert [c[0] for c in fst.calls].count('error') == 1


# ── 源碼守衛:戰情室空狀態已改就地三態,不再是「只指路去組合管理」的死路 ──────
def test_station_empty_state_is_in_place_three_state():
    src = (_REPO / 'src' / 'ui' / 'etf' / 'etf_tab_dividend_station.py').read_text(encoding='utf-8')
    assert 'render_holdings_binder' in src, '空狀態應就地呼叫綁定元件'
    assert '_station_' in src, '應用 _station_ key 前綴(與 📁 組合管理 _mgmt_ 隔離)'
    # 三態:已綁但空表要與「未綁」區分(§1 綁定 ≠ 有資料)
    assert '已綁定持股 Sheet' in src, '已綁但空表應誠實提示(不與未綁混為一談)'
