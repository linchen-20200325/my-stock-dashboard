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

import src.services.allocation_service as AS
import src.ui.tabs.macro.section_warroom as W
from shared.allocation_decision import build_allocation_decision
from shared.inst_net import InstNetDict
from tests.test_m2n2_no_zero_fill import _FakeST


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


# ══════════════════════════════════════════════════════════════════════════
# C9-n6 (a)：缺外資列（預填 0.0）⇒「外資方向」未知
# ══════════════════════════════════════════════════════════════════════════
_UNLOADED = build_allocation_decision(None)
_FK = '外資及陸資'
_BIAS = {'price': 20000.0, 'ma240': 19000.0, 'bias_240': 5.3}   # 年線位置有值 ⇒ 整段輸出別處不出現「未知」


def _wr(inst, mp):
    mp.setattr(AS, 'get_allocation', lambda *a, **k: _UNLOADED)
    state = {'bias_info': _BIAS, 'cl_data': {'margin': 2000.0, 'inst': inst},
             'warroom_summary': {'futures_net': None}}
    fake = _FakeST(state)
    mp.setattr(W, 'st', fake)
    W.render_section_warroom('bull', True, False)
    return list(fake.out)


def _card(val: str) -> str:
    return f"line-height:1.25;'>{val}</div>"


def _rows(net: float) -> dict:
    return {_FK: {'net': net}, '投信': {'net': 1.0}, '自營商': {'net': -1.0}}


class TestC9n6aUnobservedForeignNet:
    def test_unobserved_prefill_shows_unknown(self, monkeypatch):
        out = _wr(InstNetDict(_rows(0.0), unobserved_net={_FK}), monkeypatch)
        joined = '\n'.join(t for _k, t in out)
        assert _card('未知') in joined
        assert _card('賣超 0億') not in joined

    def test_only_that_card_changes(self, monkeypatch):
        """同一份資料、只差「有沒有觀測到」⇒ 整段輸出只差外資方向那一格。"""
        unobs = _wr(InstNetDict(_rows(0.0), unobserved_net={_FK}), monkeypatch)
        obs = _wr(InstNetDict(_rows(0.0)), monkeypatch)
        joined = '\x1e'.join(t for _k, t in unobs)
        assert joined.count(_card('未知')) == 1
        undone = [(k, t.replace(_card('未知'), _card('賣超 0億'))) for k, t in unobs]
        assert undone == obs

    @pytest.mark.parametrize('inst, shown', [
        pytest.param(_rows(0.0), '賣超 0億', id='plain-dict-observed-zero(b-not-in-scope)'),
        pytest.param(InstNetDict(_rows(0.0)), '賣超 0億', id='instnet-observed-zero'),
        pytest.param(InstNetDict(_rows(25.4)), '買超 25億', id='instnet-buy'),
        pytest.param(InstNetDict(_rows(-30.0), unobserved_net={'投信'}), '賣超 30億',
                     id='other-row-unobserved'),
    ])
    def test_observed_paths_unchanged(self, monkeypatch, inst, shown):
        joined = '\n'.join(t for _k, t in _wr(inst, monkeypatch))
        assert _card(shown) in joined
        assert _card('未知') not in joined
