"""順暢化 A+C(v19.204)—— Sheet ID 持久化 + 開機集中還原守衛。

痛點:被迫 登入→組合管理選 Sheet→才能戰情室/選股分析(順序卡)。
A:選 Sheet 寫入 URL ?sheet= → 重整/直接開任一頁自動還原。
C:清單只有 1 本自動選 + app.py 開機 gate 集中還原兩通道。
"""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


# ── A:_apply_active_sheet 同步兩通道 + 寫 query param(功能測,mock streamlit)──
def test_apply_active_sheet_sets_both_channels_and_query_param(monkeypatch):
    import src.ui.tabs.portfolio_manager as pm

    class _FakeSt:
        def __init__(self):
            self.session_state = {}
            self.query_params = {}
    _fst = _FakeSt()
    monkeypatch.setattr(pm, 'st', _fst)

    class _FakeGsp:
        PORTFOLIO_SHEET_KEY = 'portfolio_sheet_id'
        STOCK_PORTFOLIO_SHEET_KEY = 'stock_portfolio_sheet_id'

    pm._apply_active_sheet(_FakeGsp, 'SHEET_ABC123')
    # 兩通道(ETF+個股)都套上
    assert _fst.session_state['portfolio_sheet_id'] == 'SHEET_ABC123'
    assert _fst.session_state['stock_portfolio_sheet_id'] == 'SHEET_ABC123'
    # A:持久化到 URL query param → 重整/斷線重連自動還原
    assert _fst.query_params['sheet'] == 'SHEET_ABC123'


def test_apply_active_sheet_query_param_failure_not_fatal(monkeypatch):
    """query param 寫入失敗(如唯讀環境)不該擋設定主線(§1 不因附帶動作炸)。"""
    import src.ui.tabs.portfolio_manager as pm

    class _QPRaises(dict):
        def __setitem__(self, *_a):
            raise RuntimeError('query params read-only')

    class _FakeSt:
        def __init__(self):
            self.session_state = {}
            self.query_params = _QPRaises()
    _fst = _FakeSt()
    monkeypatch.setattr(pm, 'st', _fst)

    class _FakeGsp:
        PORTFOLIO_SHEET_KEY = 'portfolio_sheet_id'
        STOCK_PORTFOLIO_SHEET_KEY = 'stock_portfolio_sheet_id'

    pm._apply_active_sheet(_FakeGsp, 'X')            # 不應 raise
    assert _fst.session_state['portfolio_sheet_id'] == 'X'   # 主線仍成功


# ── C:單一 Sheet 自動選 wiring 存在(源碼守衛)──────────────────────
def test_drive_picker_auto_selects_single_sheet():
    src = (_REPO / 'src' / 'ui' / 'tabs' / 'portfolio_manager.py').read_text(encoding='utf-8')
    assert 'len(_sheets) == 1' in src and '_get_active_sheet_id()' in src, \
        '清單只有 1 本應自動選用(省一次點擊)'
    assert '_apply_active_sheet' in src


# ── A/C:app.py 開機 gate 還原 ?sheet= 到兩通道(源碼守衛)────────────
def test_app_boot_restores_sheet_id_to_both_channels():
    src = (_REPO / 'app.py').read_text(encoding='utf-8')
    assert "_qp.get('sheet')" in src, 'app.py 開機應還原 ?sheet='
    assert 'PORTFOLIO_SHEET_KEY' in src and 'STOCK_PORTFOLIO_SHEET_KEY' in src, \
        '應還原到 ETF+個股兩通道'
    assert 'setdefault' in src, '應以 setdefault 還原(本 session 已選則不覆寫)'
