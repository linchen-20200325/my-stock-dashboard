"""test_reconcile_panel.py — §4.3 reconcile UI panel smoke(v18.403 #8+#12)。

覆蓋:
- compute_reconcile_rows 純函式(空 state / 部分填 / 全填 健康評分)
- _STATUS_EMOJI / _STATUS_COLOR mapping 完整性
- pages __getattr__ lazy forward
"""
from __future__ import annotations

import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _stub_st(monkeypatch):
    """注 stub streamlit(本檔純測 compute_reconcile_rows,不渲染)。"""
    mod = types.ModuleType('streamlit')
    class _State(dict):
        def get(self, key, default=None):
            return super().get(key, default)
    mod.session_state = _State()
    monkeypatch.setitem(sys.modules, 'streamlit', mod)
    yield mod


class TestStatusMapping:
    def test_complete_status_emoji(self):
        from src.ui.pages.reconcile_panel import _STATUS_EMOJI
        # reconcile_pair 5 種 status 全覆蓋
        for s in ('agree', 'disagree', 'a_missing', 'b_missing', 'both_missing'):
            assert s in _STATUS_EMOJI, f'missing status {s}'

    def test_complete_status_color(self):
        from src.ui.pages.reconcile_panel import _STATUS_COLOR
        for s in ('agree', 'disagree', 'a_missing', 'b_missing', 'both_missing'):
            assert s in _STATUS_COLOR

    def test_agree_green_disagree_red(self):
        from src.ui.pages.reconcile_panel import _STATUS_EMOJI, _STATUS_COLOR
        assert _STATUS_EMOJI['agree'] == '🟢'
        assert _STATUS_EMOJI['disagree'] == '🔴'
        assert _STATUS_COLOR['agree'].startswith('#') and _STATUS_COLOR['agree'] != _STATUS_COLOR['disagree']


class TestComputeReconcileRows:
    def test_empty_state(self, monkeypatch):
        """空 session_state → 3 row 全 missing(US10Y/月營收/健康評分)"""
        # 直 patch _ss helper 而非整個 st(避 conftest pristine 衝突)
        from src.ui.pages import reconcile_panel
        monkeypatch.setattr(reconcile_panel, '_ss', lambda k, d=None: d)
        rows = reconcile_panel.compute_reconcile_rows()
        assert len(rows) == 3
        assert all('missing' in r['status'] for r in rows)
        assert all(r['emoji'] == '⬜' for r in rows)

    def test_health_score_filled_agree(self, monkeypatch):
        """填齊健康評分 3 input(80/80/+) → v1=84 v2=80 → delta=4 < 15 → agree"""
        from src.ui.pages import reconcile_panel
        _state = {
            'warroom_summary': {'jingqi_avg': 80},
            'mkt_info': {'score': 3.2},  # 3.2/4*100 = 80
            'cl_data': {'inst': {'外資及陸資': {'net': 5000}}},
        }
        monkeypatch.setattr(reconcile_panel, '_ss', lambda k, d=None: _state.get(k, d))
        rows = reconcile_panel.compute_reconcile_rows()
        health = rows[2]
        assert health['name'] == '健康評分(v1 vs v2)'
        assert health['status'] == 'agree'
        assert health['emoji'] == '🟢'

    def test_health_score_short_board_disagree(self, monkeypatch):
        """短板隱藏:jqavg=90 / score=0.8(=20%)/ fnet=+ → v1=64 v2=20 → disagree"""
        from src.ui.pages import reconcile_panel
        _state = {
            'warroom_summary': {'jingqi_avg': 90},
            'mkt_info': {'score': 0.8},
            'cl_data': {'inst': {'外資及陸資': {'net': 5000}}},
        }
        monkeypatch.setattr(reconcile_panel, '_ss', lambda k, d=None: _state.get(k, d))
        rows = reconcile_panel.compute_reconcile_rows()
        health = rows[2]
        assert health['status'] == 'disagree'
        assert health['emoji'] == '🔴'


class TestPagesInitForward:
    def test_render_reconcile_panel_importable(self):
        """src.ui.pages.__getattr__ lazy forward 須 expose render_reconcile_panel"""
        from src.ui.pages import render_reconcile_panel
        assert callable(render_reconcile_panel)
