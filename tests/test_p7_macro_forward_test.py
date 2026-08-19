"""P7（2026-08-19）：總經燈號前進式驗證 —— headless 落地。

背景（實測）
------------
`calc_traffic_light` 的輸出從來沒有離開過瀏覽器 session ⇒ 「紅燈準不準」
在本 repo 沒有樣本外證據。唯一能離線重算的 `calibrate_macro_traffic` 是
**重建版**，實測至少兩處與線上系統性不同（`conf` 恆 60 vs 可達 100；
`m1b_m2_prev` 有真值 vs 恆 None）。

本檔釘住的不變量
----------------
1. **不落空殼**：算不出燈號就不寫列（空殼日後會被統計當成真實觀測）。
2. **缺值不變 0**：health / score 的 0 是合法觀測（最強利空），不可拿來頂替 None。
3. **無 lookahead**：對帳只看該列**之後**的價格。
4. **窗口未滿 ≠ 沒中**：`hit` 必須是 None 不是 False，否則最近幾個月的紅燈
   全被記成「沒中」，系統性低估 precision。
5. **規則版本可追**：`ruleset_hash` 必須隨「會改變燈號的常數」變動——
   2026-08-19 一天之內燈號規則改了三次，沒有這欄整份資料的可稽核性歸零。
6. **同日重跑後寫者勝**（與 `forward_test_store` 的「保留最早」相反，且是刻意的）。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shared.macro_forward_test_schema import (
    FWD_EVAL_HORIZON_DAYS,
    MACRO_FWD_TEST_HEADERS,
    MACRO_FWD_TEST_KEY,
)
from src.compute.macro.macro_forward_test import (
    build_signal_row,
    compute_ruleset_hash,
    evaluate_rows,
    summarise,
)
from src.data.macro.macro_fwd_test_store import append_signals, load_signals


def _tl(**over):
    base = {
        'icon': '🔴', 'label': '空頭防禦｜降低部位', 'effective_regime': 'bear',
        'regime_source': 'health_defense', 'defense': True,
        'health': 40.2, 'health_partial': False,
        'score': 2.0, 'max_score': 5.0, 'jqavg': 49.3, 'conf': 100,
        'conf_groups': {'yfinance_twii': True, 'twse_bfi82u': True, 'finmind_taifex': True},
        'missing_sources': [],
    }
    base.update(over)
    return base


def _row(**over):
    kw = dict(date='2026-08-18', captured_at='2026-08-18T17:40:00+08:00',
              twii_close=23500.0, inputs_as_of='2026-08-18',
              git_sha='abc1234', ruleset_hash='deadbeef0000')
    tl = over.pop('tl', _tl())
    kw.update(over)
    return build_signal_row(tl, **kw)


class TestSchemaContract:
    def test_row_matches_schema_exactly(self):
        r = _row()
        assert set(r) == set(MACRO_FWD_TEST_HEADERS), (
            f'多出：{set(r) - set(MACRO_FWD_TEST_HEADERS)}；'
            f'缺少：{set(MACRO_FWD_TEST_HEADERS) - set(r)}')

    def test_conf_groups_是_json_字串不是_dict(self):
        """dict 直接進 parquet 會變 struct 欄、跨 pandas 版本讀寫易碎。"""
        r = _row()
        assert isinstance(r['conf_groups'], str)
        assert json.loads(r['conf_groups'])['yfinance_twii'] is True

    def test_schema_無重複欄名(self):
        assert len(MACRO_FWD_TEST_HEADERS) == len(set(MACRO_FWD_TEST_HEADERS))


class TestNeverFakeARow:
    def test_empty_tl_raises(self):
        """§1：算不出燈號就不該有列。落了空殼，日後統計會把它當成真實觀測。"""
        with pytest.raises(ValueError, match='空殼'):
            build_signal_row({}, date='2026-08-18', captured_at='x')

    def test_missing_date_raises(self):
        with pytest.raises(ValueError, match='date'):
            build_signal_row(_tl(), date='', captured_at='x')

    @pytest.mark.parametrize('bad', [None, float('nan'), 'n/a', ''])
    def test_missing_numbers_become_none_not_zero(self, bad):
        """0 在 health / score 都是合法觀測（最強利空）——不可拿來頂替缺值。"""
        r = _row(tl=_tl(health=bad, jqavg=bad))
        assert r['health'] is None, f'{bad!r} 被轉成了 {r["health"]!r}'
        assert r['jqavg'] is None

    def test_zero_health_survives_as_zero(self):
        """反向：真的是 0 就要留 0，不可被當成缺值吃掉。"""
        assert _row(tl=_tl(health=0.0))['health'] == 0.0

    def test_missing_sources_joined_with_pipe_not_comma(self):
        """來源名含中文括號；逗號會在 CSV 匯出時炸欄。"""
        r = _row(tl=_tl(missing_sources=['外資買賣超 (三大法人)', '先行指標 (期貨/PCR/韭菜)']))
        assert '|' in r['missing_sources']
        assert r['missing_sources'].count('|') == 1


class TestRulesetHashTracksRuleChanges:
    def test_stable_across_calls(self):
        assert compute_ruleset_hash() == compute_ruleset_hash()

    def test_changes_when_a_rule_constant_changes(self, monkeypatch):
        """這一條是整個欄位存在的理由：規則變了，hash 必須變。"""
        before = compute_ruleset_hash()
        import shared.position_throttle as PT
        monkeypatch.setattr(PT, 'THROTTLE_HEALTH_A', PT.THROTTLE_HEALTH_A + 1)
        assert compute_ruleset_hash() != before, (
            'throttle 切點改了但 ruleset_hash 沒變 —— 這欄就失去意義了')

    def test_changes_when_m1b_leg_toggles(self, monkeypatch):
        before = compute_ruleset_hash()
        import shared.signal_thresholds as ST
        monkeypatch.setattr(ST, 'M1B_M2_LEG_ENABLED', not ST.M1B_M2_LEG_ENABLED)
        assert compute_ruleset_hash() != before


class TestStore:
    def test_roundtrip(self, tmp_path):
        p = tmp_path / 'sub' / 'signals.parquet'
        assert append_signals([_row()], p) == 1
        got = load_signals(p)
        assert len(got) == 1 and got[0]['date'] == '2026-08-18'

    def test_same_date_last_writer_wins(self, tmp_path):
        """與 forward_test_store 的「保留最早」相反，且是刻意的：

        那邊存的是真實進場價（改掉 = 竄改成交紀錄）；這邊存的是「這套規則對
        那天的判定」，而規則會改。重跑通常正是為了記錄新規則。
        """
        p = tmp_path / 'signals.parquet'
        append_signals([_row()], p)
        append_signals([_row(tl=_tl(icon='🟡', label='中性'))], p)
        got = load_signals(p)
        assert len(got) == 1, '同一天堆了兩列 → precision 統計會把那天算兩次'
        assert got[0]['icon'] == '🟡'

    def test_missing_key_raises(self, tmp_path):
        bad = _row(); bad.pop(MACRO_FWD_TEST_KEY)
        with pytest.raises(ValueError, match=MACRO_FWD_TEST_KEY):
            append_signals([bad], tmp_path / 'x.parquet')

    def test_extra_column_raises_not_silently_dropped(self, tmp_path):
        """靜默丟欄會讓下游以為那個欄位從來不存在。"""
        bad = {**_row(), 'my_new_field': 1}
        with pytest.raises(ValueError, match='schema 外'):
            append_signals([bad], tmp_path / 'x.parquet')

    def test_empty_rows_is_noop(self, tmp_path):
        p = tmp_path / 'x.parquet'
        assert append_signals([], p) == 0
        assert not p.exists(), '空輸入不該建檔'

    def test_column_order_is_schema_order(self, tmp_path):
        p = tmp_path / 'x.parquet'
        append_signals([_row()], p)
        assert list(pd.read_parquet(p).columns) == list(MACRO_FWD_TEST_HEADERS)


class TestEvaluateNoLookahead:
    @staticmethod
    def _close(start='2026-08-19', n=80, path='crash'):
        idx = pd.bdate_range(start, periods=n)
        if path == 'crash':          # 60 日內跌 15%（n < 60 時就是那段的前綴）
            full = np.concatenate([np.linspace(23500, 20000, 60), np.full(max(n - 60, 0), 20000.0)])
            v = full[:n]
        else:                        # 平穩上漲
            v = np.linspace(23500, 24500, n)
        return pd.Series(v, index=idx)

    def test_hit_true_on_real_crash(self):
        df = evaluate_rows([_row()], self._close())
        assert df['evaluable'].iloc[0] is np.True_ or bool(df['evaluable'].iloc[0])
        assert bool(df['hit'].iloc[0]) is True
        assert df['fwd_mdd_pct'].iloc[0] < -10.0

    def test_hit_false_on_calm_market(self):
        df = evaluate_rows([_row()], self._close(path='calm'))
        assert bool(df['hit'].iloc[0]) is False

    def test_window_not_full_is_none_not_false(self):
        """『還沒到期』與『沒出事』是兩件事。混在一起 = 系統性低估 precision。"""
        df = evaluate_rows([_row()], self._close(n=FWD_EVAL_HORIZON_DAYS - 1))
        assert df['hit'].iloc[0] is None, f'窗口未滿卻判了 {df["hit"].iloc[0]!r}'
        assert not bool(df['evaluable'].iloc[0])

    def test_only_looks_at_bars_strictly_after_the_row_date(self):
        """把該列當日之前（含當日）的價格改掉，結果必須完全不變。"""
        close = self._close(start='2026-08-01', n=100)
        base = evaluate_rows([_row()], close)
        tampered = close.copy()
        tampered.loc[tampered.index <= pd.Timestamp('2026-08-18')] *= 0.5
        after = evaluate_rows([_row()], tampered)
        assert base['hit'].iloc[0] == after['hit'].iloc[0]
        assert base['fwd_ret_pct'].iloc[0] == after['fwd_ret_pct'].iloc[0]

    def test_empty_rows_returns_empty_frame_with_columns(self):
        df = evaluate_rows([], self._close())
        assert df.empty
        for c in ('hit', 'evaluable', 'fwd_ret_pct', 'fwd_mdd_pct'):
            assert c in df.columns


class TestSummarise:
    def test_pending_is_visible(self):
        """pending 必須看得見，否則讀者分不清『樣本少』與『訊號差』。"""
        close = pd.Series(np.linspace(23500, 24500, 30),
                          index=pd.bdate_range('2026-08-19', periods=30))
        s = summarise(evaluate_rows([_row()], close), '🔴')
        assert s['n_pending'] == 1 and s['n_evaluable'] == 0
        assert s['precision'] is None, '沒有可評估樣本時不可回一個數字'

    def test_empty_input_is_safe(self):
        s = summarise(pd.DataFrame(), '🔴')
        assert s['n_evaluable'] == 0 and s['precision'] is None


class TestCronScriptNeverWritesAPartialRow:
    """§1：cron 的兩條失敗路徑都必須「exit 0 且完全不寫」。

    exit 0 而非 1 是刻意的 —— 休市日走的是同一條路，讓 cron 紅燈會製造
    每週兩次的假警報，真正的失敗反而會被忽略（狼來了）。

    「不寫」比「exit code」更重要：落一列空殼，日後 precision 統計會把它
    當成一個真實觀測，而它什麼都不是。
    """

    def test_fetch_chain_totally_fails(self, monkeypatch):
        import scripts.update_macro_forward_test as S
        import src.data.macro.macro_fwd_test_store as store
        calls = []
        monkeypatch.setattr(S, '_fetch_live_bundle',
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError('proxy 403')))
        monkeypatch.setattr(store, 'append_signals', lambda *a, **k: calls.append(a) or 1)
        assert S.main([]) == 0
        assert calls == [], '抓取全失敗卻仍寫了列'

    @staticmethod
    def _isolate(monkeypatch, calls, tl):
        """把 script 與所有真實 I/O 隔開。

        必須連 `compute_and_apply_market_assessment` 一起 mock —— 它在 df_index
        失敗時會走 yfinance 備援重抓，沙箱無外網 ⇒ 三次重試逾時，讓單元測試變成
        一分鐘。本測試要驗的是**腳本的控制流**（失敗時寫不寫），不是 fetcher。
        """
        import scripts.update_macro_forward_test as S
        import src.compute.macro as CM
        import src.data.macro.macro_fwd_test_store as store
        import src.services.jingqi_calc as JQ
        import src.services.market_assessment_apply as MA
        monkeypatch.setattr(S, '_fetch_live_bundle', lambda *a, **k: {'tw_raw': {}, 'inst': {}})
        monkeypatch.setattr(S, '_git_sha', lambda: 'test0000')
        monkeypatch.setattr(MA, 'compute_and_apply_market_assessment', lambda **k: None)
        monkeypatch.setattr(JQ, 'compute_and_store_jingqi', lambda *a, **k: None)
        monkeypatch.setattr(CM, 'calc_traffic_light', lambda *a, **k: tl)
        monkeypatch.setattr(store, 'append_signals', lambda *a, **k: calls.append(a) or 1)
        return S

    def test_traffic_light_returns_none(self, monkeypatch):
        calls = []
        S = self._isolate(monkeypatch, calls, None)
        assert S.main([]) == 0
        assert calls == [], '燈號算不出來卻仍寫了列（空殼）'

    def test_dry_run_never_writes(self, monkeypatch):
        calls = []
        S = self._isolate(monkeypatch, calls, _tl())
        assert S.main(['--dry-run']) == 0
        assert calls == [], '--dry-run 竟然寫了檔'

    def test_happy_path_does_write_exactly_one_row(self, monkeypatch):
        """反向守衛：上面三條都在證明「不寫」，這條證明正常時**真的會寫**。

        沒有這條，把 `append_signals` 整個拿掉也能讓上面三條全綠。
        """
        calls = []
        S = self._isolate(monkeypatch, calls, _tl())
        assert S.main(['--date', '2026-08-18']) == 0
        assert len(calls) == 1, f'正常路徑沒寫列：{calls}'
        rows = calls[0][0]
        assert len(rows) == 1 and rows[0]['date'] == '2026-08-18'
        assert rows[0]['icon'] == '🔴'
        # 無 tw_raw ⇒ 沒有收盤價。誠實記 None，不可捏造（該列日後無法對帳）。
        assert rows[0]['twii_close'] is None
