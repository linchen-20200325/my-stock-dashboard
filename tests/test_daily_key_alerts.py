# -*- coding: utf-8 -*-
"""v19.108 — ⚡ 今日關鍵橫幅(第九份 4-C 精簡版,user 核准設計 A)回歸鎖。

三個最容易出錯的輸入(§6):
1. 全空/None 輸入(未載入)→ items=[] 顯「無異常」,不炸
2. vix.values 含 None/垃圾字串 → 急變層跳過,門檻層不受影響
3. fed_funds 只有 current 沒 prev → 急變層誠實跳過(不腦補變化)
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _src(rel: str) -> str:
    return (REPO / rel).read_text(encoding='utf-8')


def _mk_threshold(level='red', key='vix', label='VIX 恐慌指數', value=32.0):
    return {'key': key, 'label': label, 'unit': '', 'value': value,
            'level': level, 'emoji': {'red': '🔴', 'yellow': '🟡',
                                      'green': '🟢'}[level],
            'message': f'{label} 超限測試訊息'}


# ═════════════════════════════════════════════════════════════════
# L2 collect_key_alerts
# ═════════════════════════════════════════════════════════════════
class TestCollectKeyAlerts:
    def test_all_empty_inputs_no_crash(self):
        from src.compute.macro.daily_key_alerts import collect_key_alerts
        out = collect_key_alerts(None, None)
        assert out == {'items': [], 'n_red': 0, 'n_yellow': 0}

    def test_threshold_layer_filters_green_and_sorts_red_first(self):
        from src.compute.macro.daily_key_alerts import collect_key_alerts
        alerts = [_mk_threshold('green', key='dxy'),
                  _mk_threshold('yellow', key='cpi', label='CPI', value=3.4),
                  _mk_threshold('red', key='vix')]
        out = collect_key_alerts(alerts, {})
        assert len(out['items']) == 2, 'green 不進橫幅'
        assert out['items'][0]['severity'] == 0 and out['items'][1]['severity'] == 1
        assert out['n_red'] == 1 and out['n_yellow'] == 1
        assert out['items'][0]['detail'], '白話 detail 沿用 rule message(SSOT 敘事)'

    def test_vix_spike_triggers_delta(self):
        from shared.signal_thresholds import KEY_ALERT_VIX_DAY_SPIKE_PCT
        from src.compute.macro.daily_key_alerts import collect_key_alerts
        _mult = 1 + (KEY_ALERT_VIX_DAY_SPIKE_PCT + 5) / 100   # 超門檻 5%
        mi = {'vix': {'values': [15.0, 15.0 * _mult]}}
        out = collect_key_alerts([], mi)
        assert len(out['items']) == 1 and out['items'][0]['layer'] == 'delta'
        assert out['items'][0]['severity'] == 0
        assert 'VIX 單日急升' in out['items'][0]['text']

    def test_vix_below_threshold_or_drop_no_item(self):
        from src.compute.macro.daily_key_alerts import collect_key_alerts
        assert collect_key_alerts([], {'vix': {'values': [20.0, 21.0]}})['items'] == []
        # 急跌(恐慌消退)不亮 — 設計只看急升
        assert collect_key_alerts([], {'vix': {'values': [30.0, 18.0]}})['items'] == []

    def test_vix_garbage_values_skipped_not_crash(self):
        from src.compute.macro.daily_key_alerts import collect_key_alerts
        out = collect_key_alerts(
            [_mk_threshold('red')],
            {'vix': {'values': [None, 'N/A', 15.0]}})   # 尾兩點含垃圾
        # 急變層跳過,門檻層仍在
        assert len(out['items']) == 1 and out['items'][0]['layer'] == 'threshold'

    def test_fed_funds_move_both_directions(self):
        from src.compute.macro.daily_key_alerts import collect_key_alerts
        up = collect_key_alerts([], {'fed_funds': {'current': 4.58, 'prev': 4.33}})
        dn = collect_key_alerts([], {'fed_funds': {'current': 4.08, 'prev': 4.33}})
        assert '升息' in up['items'][0]['text']
        assert '降息' in dn['items'][0]['text']

    def test_fed_funds_missing_prev_honest_skip(self):
        from src.compute.macro.daily_key_alerts import collect_key_alerts
        assert collect_key_alerts([], {'fed_funds': {'current': 4.33}})['items'] == []

    def test_l2_purity_no_streamlit_no_io(self):
        text = _src('src/compute/macro/daily_key_alerts.py')
        for banned in ('import streamlit', 'import requests', 'fetch_url'):
            assert banned not in text, f'L2 純函式不得 {banned}(§8.2)'


# ═════════════════════════════════════════════════════════════════
# L4 key_alerts_banner
# ═════════════════════════════════════════════════════════════════
class TestKeyAlertsBanner:
    def test_empty_shows_honest_all_clear(self):
        from src.ui.render.macro_ui_components import key_alerts_banner
        html = key_alerts_banner({'items': [], 'n_red': 0, 'n_yellow': 0})
        assert '無異常' in html

    def test_red_items_render_with_tooltip(self):
        from shared.colors import TRAFFIC_RED
        from src.compute.macro.daily_key_alerts import collect_key_alerts
        from src.ui.render.macro_ui_components import key_alerts_banner
        out = collect_key_alerts([_mk_threshold('red')], {})
        html = key_alerts_banner(out)
        assert '今日關鍵（1 項）' in html
        assert TRAFFIC_RED in html            # 紅框
        assert 'title="' in html and '超限測試訊息' in html   # hover 白話

    def test_yellow_only_uses_yellow_border(self):
        from shared.colors import TRAFFIC_RED, TRAFFIC_YELLOW
        from src.compute.macro.daily_key_alerts import collect_key_alerts
        from src.ui.render.macro_ui_components import key_alerts_banner
        out = collect_key_alerts([_mk_threshold('yellow')], {})
        html = key_alerts_banner(out)
        assert TRAFFIC_YELLOW in html
        assert f'border-left:3px solid {TRAFFIC_RED}' not in html


# ═════════════════════════════════════════════════════════════════
# SSOT + 接線
# ═════════════════════════════════════════════════════════════════
def test_delta_thresholds_are_ssot():
    from shared.signal_thresholds import (
        KEY_ALERT_FED_FUNDS_MOVE_PCTPT, KEY_ALERT_VIX_DAY_SPIKE_PCT,
    )
    assert KEY_ALERT_VIX_DAY_SPIKE_PCT > 0
    assert KEY_ALERT_FED_FUNDS_MOVE_PCTPT > 0
    text = _src('src/compute/macro/daily_key_alerts.py')
    assert 'from shared.signal_thresholds import' in text, '門檻必須 import SSOT'


def test_tab_macro_mounts_banner_at_top():
    text = _src('src/ui/tabs/tab_macro.py')
    assert 'collect_key_alerts' in text and 'key_alerts_banner' in text
    # 掛在載入 gate 之後、模組一(紅綠燈)之前
    _pos_banner = text.index('key_alerts_banner')
    _pos_mod1 = text.index('【模組一】紅綠燈決策儀表板')
    assert _pos_banner < _pos_mod1, '橫幅須在紅綠燈模組之前(頁首)'
