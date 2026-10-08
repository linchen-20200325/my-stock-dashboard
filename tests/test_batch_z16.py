"""批 Z16（第十輪分類 A、B 兩組一致判「可自主」）：C9-n3、C9-n6 (a)。

- C9-n3（L5 `src/ui/tabs/tab_macro.py::render_tab_macro`）：空狀態閘門 `_macro_loaded`
  在按鈕之前就算好 ⇒ 冷啟動第一次按「🚀 一鍵更新全部數據」，當輪只立 `chips_loaded`
  旗標就走「👉 點擊上方按鈕載入總經資料」return，要按第二下才載入。
  修法：閘門改看 `_macro_loaded or do_refresh`（按下的那一輪本來就要載入）。
  ⚠️ S1（`tests/test_s1_zombie_loaded_state.py`）不得回退：沒按按鈕的空 session
  仍須停在誠實空狀態（下方 `test_cold_start_without_click_stays_empty` 守住）。
- C9-n6 (a)（L5 `src/ui/tabs/macro/section_warroom.py::render_section_warroom`）：
  L1 三大法人缺外資列時預填 net 0.0（`shared/inst_net.InstNetDict.unobserved_net`），
  作戰室「外資方向」把它當觀測值印「賣超 0億」。修法：依 `is_net_observed` 判斷，
  沒觀測到 ⇒ 走既有「未知」。⛔ (b)「真的觀測到淨額 0」需新字，本批不做（下方守住它逐字不變）。

本檔所有斷言皆為實跑行為斷言（AppTest／`_FakeST`），不讀原始碼字面。
"""
from __future__ import annotations

import pytest


# ══════════════════════════════════════════════════════════════════════════
# C9-n3：冷啟動第一下就要載入
# ══════════════════════════════════════════════════════════════════════════
_EMPTY_HINT = '點擊上方按鈕載入總經資料'   # st.info 會把開頭 emoji 拆成 icon


def _macro_app(monkeypatch):
    """AppTest 跑 `render_tab_macro`；過了空狀態閘門後的第一個呼叫
    （`render_traffic_light_top`）換成「記一筆 + st.stop()」，不走任何網路。"""
    from streamlit.testing.v1 import AppTest

    import src.ui.tabs.tab_macro as TM

    def _reached(*_a, **_k):
        import streamlit as st
        st.session_state['_z16_reached'] = True
        st.stop()

    monkeypatch.setattr(TM, 'render_traffic_light_top', _reached)
    # 強制重抓的 on_click 會清 /tmp pkl、全站 st.cache_data、proxy 快取（行程全域副作用）
    # ⇒ 測試只留它 scoped 的那一步（清總經 session_state），閘門行為與正式路徑相同。
    monkeypatch.setattr(TM, '_on_force_clear_click', TM._macro_session_reset)

    def _script():
        from src.ui.tabs.tab_macro import render_tab_macro
        render_tab_macro()

    return AppTest.from_function(_script, default_timeout=120)


def _infos(at) -> list[str]:
    return [i.value for i in at.info]


class TestC9n3ColdStartFirstClickLoads:
    def test_cold_start_without_click_stays_empty(self, monkeypatch):
        """S1 相容：沒按按鈕的空 session ⇒ 誠實空狀態，不進主流程。"""
        at = _macro_app(monkeypatch).run()
        assert not at.exception
        assert _EMPTY_HINT in _infos(at)
        assert '_z16_reached' not in at.session_state

    @pytest.mark.parametrize('key', ['cl_refresh', 'cl_force_refresh'])
    def test_first_click_on_cold_start_loads(self, monkeypatch, key):
        at = _macro_app(monkeypatch).run()
        assert '_z16_reached' not in at.session_state
        at.button(key=key).click().run()
        assert not at.exception
        assert '_z16_reached' in at.session_state and at.session_state['_z16_reached'], (
            '冷啟動第一次按更新就該進主流程載入，不能要按第二下')
        assert _EMPTY_HINT not in _infos(at)
