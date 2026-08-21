"""順暢化 A+C(v19.204)+ P1(v19.205)—— Sheet ID 持久化 + 綁定 SSOT 守衛。

痛點:被迫 登入→組合管理選 Sheet→才能戰情室/選股分析(順序卡)。
A:選 Sheet 寫入 URL ?sheet= → 重整/直接開任一頁自動還原。
C:清單只有 1 本自動選 + app.py 開機 gate 集中還原兩通道。
P1:綁定「寫兩通道 + ?sheet=」寫入契約與 Drive 挑選器抽成 portfolio_binder(SSOT),
   原散 3 份(portfolio_manager / 側欄 / app.py 開機)委派同一支。
"""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


# ── A:apply_active_sheet 同步兩通道 + 寫 query param(功能測,mock streamlit)──
#    SSOT 已自 portfolio_manager 搬到 portfolio_binder(P1);portfolio_manager._apply_active_sheet
#    現為委派薄殼,故功能測直接測 SSOT。
def test_apply_active_sheet_sets_both_channels_and_query_param(monkeypatch):
    import src.ui.tabs.portfolio_binder as pb

    class _FakeSt:
        def __init__(self):
            self.session_state = {}
            self.query_params = {}
    _fst = _FakeSt()
    monkeypatch.setattr(pb, 'st', _fst)

    class _FakeGsp:
        PORTFOLIO_SHEET_KEY = 'portfolio_sheet_id'
        STOCK_PORTFOLIO_SHEET_KEY = 'stock_portfolio_sheet_id'

    pb.apply_active_sheet(_FakeGsp, 'SHEET_ABC123')
    # 兩通道(ETF+個股)都套上
    assert _fst.session_state['portfolio_sheet_id'] == 'SHEET_ABC123'
    assert _fst.session_state['stock_portfolio_sheet_id'] == 'SHEET_ABC123'
    # A:持久化到 URL query param → 重整/斷線重連自動還原
    assert _fst.query_params['sheet'] == 'SHEET_ABC123'


def test_apply_active_sheet_query_param_failure_not_fatal(monkeypatch):
    """query param 寫入失敗(如唯讀環境)不該擋設定主線(§1 不因附帶動作炸)。"""
    import src.ui.tabs.portfolio_binder as pb

    class _QPRaises(dict):
        def __setitem__(self, *_a):
            raise RuntimeError('query params read-only')

    class _FakeSt:
        def __init__(self):
            self.session_state = {}
            self.query_params = _QPRaises()
    _fst = _FakeSt()
    monkeypatch.setattr(pb, 'st', _fst)

    class _FakeGsp:
        PORTFOLIO_SHEET_KEY = 'portfolio_sheet_id'
        STOCK_PORTFOLIO_SHEET_KEY = 'stock_portfolio_sheet_id'

    pb.apply_active_sheet(_FakeGsp, 'X')             # 不應 raise
    assert _fst.session_state['portfolio_sheet_id'] == 'X'   # 主線仍成功


def test_portfolio_manager_apply_delegates_to_binder():
    """portfolio_manager._apply_active_sheet 現為委派薄殼(SSOT 在 portfolio_binder)。"""
    src = (_REPO / 'src' / 'ui' / 'tabs' / 'portfolio_manager.py').read_text(encoding='utf-8')
    assert 'from src.ui.tabs.portfolio_binder import apply_active_sheet' in src, \
        '_apply_active_sheet 應委派 portfolio_binder.apply_active_sheet(SSOT)'


# ── C:單一 Sheet 自動選 wiring 存在(源碼守衛;主體已在 portfolio_binder)──────
def test_drive_picker_auto_selects_single_sheet():
    src = (_REPO / 'src' / 'ui' / 'tabs' / 'portfolio_binder.py').read_text(encoding='utf-8')
    assert 'len(_sheets) == 1' in src and '_get_active_sheet_id()' in src, \
        '清單只有 1 本應自動選用(省一次點擊)'
    assert 'apply_active_sheet' in src


# ── A/C:app.py 開機 gate 還原 ?sheet= 到兩通道(源碼守衛)────────────
def test_app_boot_restores_sheet_id_to_both_channels():
    src = (_REPO / 'app.py').read_text(encoding='utf-8')
    assert "_qp.get('sheet')" in src, 'app.py 開機應還原 ?sheet='
    # §8.2 R4:app.py(L6)不得 import L1 gsheet_portfolio 取常數 → 用其 session key 字面值。
    # PORTFOLIO_SHEET_KEY/STOCK_PORTFOLIO_SHEET_KEY 的值即這兩個字串,還原到 ETF+個股兩通道。
    assert 'portfolio_sheet_id' in src and 'stock_portfolio_sheet_id' in src, \
        '應還原到 ETF+個股兩通道'
    assert 'setdefault' in src, '應以 setdefault 還原(本 session 已選則不覆寫)'
