"""v18.466 守衛測試：ETF 單檔診斷下方三個 smart 區塊改成吃「上方那一個代號」。

使用者回報：單檔診斷下方的 σ 買賣帶 / 分散度 / MK 3-3-3 各自帶獨立輸入框（顯示 0050），
沒吃上方「開始診斷」輸入的代號。修法：三個 render 函式改收 ticker 參數、移除各自的
獨立 ETF 代號 text_input；組合頁改用單一共用輸入框（render_smart_ticker_input）。

本測試以 inspect.getsource + signature 當 golden，防止未來又被改回「各自開輸入框」。
"""
import inspect

import src.ui.etf.etf_tab_smart as smart


THREE_SECTIONS = [
    smart.render_std_band_section,
    smart.render_correlation_finder,
    smart.render_333_section,
]


def test_three_sections_take_ticker_first_param():
    """三個區塊的第一個參數必須是 ticker（由呼叫端傳入，不再自己開輸入框）。"""
    for fn in THREE_SECTIONS:
        params = list(inspect.signature(fn).parameters)
        assert params[0] == 'ticker', f'{fn.__name__} 首參數應為 ticker，實際 {params}'
        assert 'key_suffix' in params, f'{fn.__name__} 應保留 key_suffix'


def test_three_sections_no_own_ticker_input():
    """三個區塊內不得再出現獨立的 ETF 代號輸入框 / 舊的 etf_g_active fallback。"""
    for fn in THREE_SECTIONS:
        src = inspect.getsource(fn)
        assert "text_input(" not in src, (
            f'{fn.__name__} 仍自帶 text_input（應改吃上方傳入的 ticker）')
        assert "etf_g_active" not in src, (
            f'{fn.__name__} 仍有 etf_g_active 舊 fallback（該 key 從未被寫入）')
        assert "_normalize(ticker)" in src, (
            f'{fn.__name__} 應以 _normalize(ticker) 取用傳入代號')


def test_shared_ticker_input_exists():
    """組合頁專用的單一共用輸入框 helper 必須存在（3 框收斂成 1 框）。"""
    fn = getattr(smart, 'render_smart_ticker_input', None)
    assert fn is not None, '缺 render_smart_ticker_input（組合頁共用輸入框）'
    src = inspect.getsource(fn)
    assert "text_input(" in src, 'render_smart_ticker_input 應含一個共用 text_input'
    assert "etf_smart_shared" in src, '共用輸入框 key 應為 etf_smart_shared*'


def test_app_wires_single_tab_to_etf_s_active():
    """app.py 單檔頁三區塊必須吃 session_state['etf_s_active']（上方開始診斷代號）。"""
    with open('app.py', encoding='utf-8') as f:
        app_src = f.read()
    assert "st.session_state.get('etf_s_active')" in app_src
    assert "render_333_section(_etf_s_tk, key_suffix='_single')" in app_src
    # 組合頁改用共用輸入框
    assert "render_smart_ticker_input(key_suffix='_grp')" in app_src
    assert "render_333_section(_etf_grp_tk, key_suffix='_grp')" in app_src
