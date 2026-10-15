"""C-1 / C-2（2026-10-15）：總經燈號前進式驗證帳本的兩個實錘 bug 的回歸守衛。

C-1：`scripts/update_macro_forward_test.py::_twii_close_and_asof` 只認 `'Close'`，
     但 L1 `daily_data_fetchers._fetch_single_cached` 把欄名轉小寫 ⇒ 永遠 (None, None)；
     帳本 34 列 `twii_close` / `inputs_as_of` 全為 None，只 warn 不擋。
C-2：列的 `date` 取執行當下 `datetime.now(TW)`；cron 實際延遲到台北午夜後 ⇒ 日期偏一天、
     週末/假日也生列；`append_signals` 同 date 後寫者勝 ⇒ 5 筆真實觀測從 HEAD 消失。

本檔釘住的不變量
----------------
1. 收盤欄大小寫不敏感；取不到收盤 / 交易日 → **不寫列、exit 1**（不落無法對帳的列）。
2. `date` = 實抓 ^TWII 最後一根 K 棒的交易日（= `inputs_as_of`），**不是**執行日期；
   盤中（未收盤）K 棒不得當觀測。
3. 同觀測日已存在 → 保留既有、不覆寫；不同觀測日互不覆蓋。
4. 修復後的帳本：date 唯一、皆為交易日、無捏造 twii_close、每列有 `date_source`；
   自 git 史撈回的 5 筆存在且值與原列一致。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from shared.macro_forward_test_schema import (
    DATE_SOURCE_BACKFILL,
    DATE_SOURCE_LIVE,
    MACRO_FWD_TEST_DATE_SOURCES,
    MACRO_FWD_TEST_HEADERS,
)
from src.compute.macro.macro_forward_test import (
    build_signal_row,
    derive_observation_date,
    session_has_closed,
)

_REPO = Path(__file__).resolve().parents[1]


def _tl(**over):
    base = {
        'icon': '🔴', 'label': '空頭防禦｜降低部位', 'effective_regime': 'bear',
        'regime_source': 'health_defense', 'defense': True,
        'health': 40.2, 'health_partial': False,
        'score': 2.0, 'max_score': 5.0, 'jqavg': 49.3, 'conf': 100,
        'conf_groups': {'yfinance_twii': True}, 'missing_sources': [],
    }
    base.update(over)
    return base


def _twii(dates, closes, col='close'):
    return pd.DataFrame({col: closes}, index=pd.to_datetime(dates))


# ══════════════════════════════════════════════════════════════════
# C-1：收盤欄大小寫
# ══════════════════════════════════════════════════════════════════
class TestTwiiCloseParsing:
    @staticmethod
    def _f():
        import scripts.update_macro_forward_test as S
        return S._twii_close_and_asof

    @pytest.mark.parametrize('col', ['close', 'Close'])
    def test_either_case_is_read(self, col):
        df = _twii(['2026-08-17', '2026-08-18'], [100.0, 101.5], col=col)
        assert self._f()({'台股加權指數': df}) == (101.5, '2026-08-18')

    def test_lowercase_preferred_when_both_present(self):
        df = pd.DataFrame({'close': [1.0], 'Close': [2.0]},
                          index=pd.to_datetime(['2026-08-18']))
        assert self._f()({'台股加權指數': df}) == (1.0, '2026-08-18')

    def test_trailing_nan_rows_are_not_the_observation(self):
        df = _twii(['2026-08-17', '2026-08-18'], [100.0, float('nan')])
        assert self._f()({'台股加權指數': df}) == (100.0, '2026-08-17')

    @pytest.mark.parametrize('df', [
        None,
        pd.DataFrame(),
        pd.DataFrame({'open': [1.0]}, index=pd.to_datetime(['2026-08-18'])),
        pd.DataFrame({'close': [float('nan')] * 2},
                     index=pd.to_datetime(['2026-08-17', '2026-08-18'])),
    ], ids=['none', 'empty', 'no_close_col', 'all_nan'])
    def test_unusable_frames_return_none(self, df):
        assert self._f()({'台股加權指數': df}) == (None, None)


# ══════════════════════════════════════════════════════════════════
# 腳本整合：隔離所有真實 I/O，只驗控制流與寫出的列
# ══════════════════════════════════════════════════════════════════
def _isolate(monkeypatch, tmp_path, *, tw_raw, now_iso, tl=None):
    import scripts.update_macro_forward_test as S
    import src.compute.macro as CM
    import src.data.macro.macro_fwd_test_store as store
    import src.services.jingqi_calc as JQ
    import src.services.market_assessment_apply as MA
    monkeypatch.setattr(S, '_fetch_live_bundle', lambda *a, **k: {'tw_raw': tw_raw, 'inst': {}})
    monkeypatch.setattr(S, '_git_sha', lambda: 'test0000')
    monkeypatch.setattr(S, '_now_tw', lambda: datetime.fromisoformat(now_iso))
    monkeypatch.setattr(MA, 'compute_and_apply_market_assessment', lambda **k: None)
    monkeypatch.setattr(JQ, 'compute_and_store_jingqi', lambda *a, **k: None)
    monkeypatch.setattr(CM, 'calc_traffic_light', lambda *a, **k: (tl or _tl()))
    monkeypatch.setattr(store, 'MACRO_FWD_TEST_PATH', tmp_path / 'signals.parquet')
    monkeypatch.delenv('GITHUB_OUTPUT', raising=False)
    return S, store


def _run(monkeypatch, tmp_path, *, dates, closes, now_iso, argv=(), col='close', tl=None):
    S, store = _isolate(monkeypatch, tmp_path, tw_raw={'台股加權指數': _twii(dates, closes, col)},
                        now_iso=now_iso, tl=tl)
    rc = S.main(list(argv))
    return rc, store.load_signals()


class TestFailLoudWithoutTwii:
    @pytest.mark.parametrize('tw_raw', [
        {},
        {'台股加權指數': pd.DataFrame({'open': [1.0]}, index=pd.to_datetime(['2026-08-18']))},
        {'台股加權指數': pd.DataFrame({'close': [float('nan')]},
                                     index=pd.to_datetime(['2026-08-18']))},
    ], ids=['missing', 'no_close_col', 'all_nan'])
    def test_no_row_and_nonzero_exit(self, monkeypatch, tmp_path, tw_raw):
        S, store = _isolate(monkeypatch, tmp_path, tw_raw=tw_raw,
                            now_iso='2026-08-18T17:40:00+08:00')
        rc = S.main([])
        assert rc != 0, '取不到 ^TWII 收盤卻 exit 0 —— workflow 不會紅燈'
        assert store.load_signals() == [], '寫出了一列無法對帳的列（twii_close / 觀測日皆無）'

    def test_intraday_bar_is_not_an_observation(self, monkeypatch, tmp_path):
        rc, rows = _run(monkeypatch, tmp_path, dates=['2026-08-17', '2026-08-18'],
                        closes=[1.0, 2.0], now_iso='2026-08-18T10:00:00+08:00')
        assert rc != 0 and rows == []

    def test_weekend_labelled_bar_rejected(self, monkeypatch, tmp_path):
        """twii_ohlcv 的 git 史實測出現過一根 2026-09-20（週日）的 Yahoo K 棒。"""
        rc, rows = _run(monkeypatch, tmp_path, dates=['2026-09-18', '2026-09-20'],
                        closes=[1.0, 2.0], now_iso='2026-09-20T21:30:00+08:00')
        assert rc != 0 and rows == []

    def test_date_assertion_mismatch_fails(self, monkeypatch, tmp_path):
        rc, rows = _run(monkeypatch, tmp_path, dates=['2026-08-18'], closes=[1.0],
                        now_iso='2026-08-19T00:30:00+08:00', argv=['--date', '2026-08-19'])
        assert rc != 0 and rows == []


class TestObservationDateIsTheTradingDay:
    @pytest.mark.parametrize('now_iso', ['2026-08-19T00:30:00+08:00',
                                         '2026-08-19T03:00:00+08:00'])
    def test_after_midnight_is_previous_trading_day(self, monkeypatch, tmp_path, now_iso):
        rc, rows = _run(monkeypatch, tmp_path, dates=['2026-08-17', '2026-08-18'],
                        closes=[1.0, 2.0], now_iso=now_iso)
        assert rc == 0 and len(rows) == 1
        r = rows[0]
        assert r['date'] == '2026-08-18', f'跨午夜跑出了 {r["date"]}（應為前一交易日）'
        assert r['inputs_as_of'] == r['date']
        assert r['date_source'] == DATE_SOURCE_LIVE
        assert r['captured_at'] == now_iso, 'captured_at 必須是實際執行時刻（provenance）'
        assert r['twii_close'] == 2.0

    def test_weekend_run_does_not_create_a_weekend_row(self, monkeypatch, tmp_path):
        rc, rows = _run(monkeypatch, tmp_path, dates=['2026-08-20', '2026-08-21'],
                        closes=[1.0, 2.0], now_iso='2026-08-22T03:00:00+08:00')  # 週六
        assert rc == 0 and [r['date'] for r in rows] == ['2026-08-21']

    def test_weekend_rerun_does_not_overwrite_friday(self, monkeypatch, tmp_path):
        _run(monkeypatch, tmp_path, dates=['2026-08-21'], closes=[2.0],
             now_iso='2026-08-21T18:00:00+08:00', tl=_tl(icon='🔴'))
        rc, rows = _run(monkeypatch, tmp_path, dates=['2026-08-21'], closes=[2.0],
                        now_iso='2026-08-22T03:00:00+08:00', tl=_tl(icon='🟢'))
        assert rc == 0 and len(rows) == 1
        assert rows[0]['icon'] == '🔴' and rows[0]['captured_at'] == '2026-08-21T18:00:00+08:00'

    def test_same_execution_date_two_observations_both_kept(self, monkeypatch, tmp_path):
        """修前：兩次都記成 08-19，第二次覆寫第一次 ⇒ 08-18 的觀測消失。"""
        _run(monkeypatch, tmp_path, dates=['2026-08-18'], closes=[1.0],
             now_iso='2026-08-19T00:30:00+08:00', tl=_tl(icon='🔴'))
        rc, rows = _run(monkeypatch, tmp_path, dates=['2026-08-18', '2026-08-19'],
                        closes=[1.0, 2.0], now_iso='2026-08-19T18:00:00+08:00',
                        tl=_tl(icon='🟢'))
        assert rc == 0
        got = {r['date']: r['icon'] for r in rows}
        assert got == {'2026-08-18': '🔴', '2026-08-19': '🟢'}, got

    def test_uppercase_close_also_works_end_to_end(self, monkeypatch, tmp_path):
        rc, rows = _run(monkeypatch, tmp_path, dates=['2026-08-18'], closes=[7.0], col='Close',
                        now_iso='2026-08-18T18:00:00+08:00')
        assert rc == 0 and rows[0]['twii_close'] == 7.0


class TestBuildRowLiveInvariant:
    def test_live_row_requires_date_equal_inputs_as_of(self):
        with pytest.raises(ValueError, match='inputs_as_of'):
            build_signal_row(_tl(), date='2026-08-19', captured_at='2026-08-19T00:30:00+08:00',
                             inputs_as_of='2026-08-18', date_source=DATE_SOURCE_LIVE)

    def test_unknown_date_source_raises(self):
        with pytest.raises(ValueError, match='date_source'):
            build_signal_row(_tl(), date='2026-08-18', captured_at='x', date_source='now()')


# ══════════════════════════════════════════════════════════════════
# 推導規則（歷史修復用的純函式）
# ══════════════════════════════════════════════════════════════════
_CAL = ['2026-09-21', '2026-09-22', '2026-09-23', '2026-09-24',   # 09-25 / 09-28 休市
        '2026-09-29', '2026-09-30']


class TestDeriveObservationDate:
    @pytest.mark.parametrize('cap, want', [
        ('2026-09-23T00:30:00+08:00', '2026-09-22'),   # 跨午夜
        ('2026-09-23T03:00:00+08:00', '2026-09-22'),
        ('2026-09-23T13:29:59+08:00', '2026-09-22'),   # 收盤前
        ('2026-09-23T13:30:00+08:00', '2026-09-23'),   # 收盤（含）
        ('2026-09-23T22:00:00+08:00', '2026-09-23'),
        ('2026-09-25T22:44:28+08:00', '2026-09-24'),   # 假日
        ('2026-09-29T01:48:58+08:00', '2026-09-24'),   # 連假後凌晨
        ('2026-09-26T03:00:00+08:00', '2026-09-24'),   # 週六
        ('2026-09-22T16:00:00+00:00', '2026-09-22'),   # UTC 輸入 = TW 09-23 00:00 → 前一交易日
    ])
    def test_rule(self, cap, want):
        assert derive_observation_date(cap, _CAL, calendar_complete_through='2026-09-30') == want

    def test_never_returns_non_trading_day(self):
        for h in range(0, 24 * 10):
            cap = pd.Timestamp('2026-09-22T00:00:00+08:00') + pd.Timedelta(hours=h)
            if cap.date() > pd.Timestamp('2026-09-30').date():
                break
            assert derive_observation_date(cap.to_pydatetime(), _CAL,
                                           calendar_complete_through='2026-09-30') in _CAL

    def test_naive_timestamp_rejected(self):
        with pytest.raises(ValueError, match='時區'):
            derive_observation_date('2026-09-23T00:30:00', _CAL,
                                    calendar_complete_through='2026-09-30')

    def test_beyond_calendar_rejected(self):
        with pytest.raises(ValueError, match='超出'):
            derive_observation_date('2026-10-01T18:00:00+08:00', _CAL,
                                    calendar_complete_through='2026-09-30')

    def test_session_has_closed_edges(self):
        assert not session_has_closed('2026-09-23', '2026-09-23T13:29:00+08:00')
        assert session_has_closed('2026-09-23', '2026-09-23T13:30:00+08:00')
        assert not session_has_closed('2026-09-24', '2026-09-23T23:00:00+08:00')


# ══════════════════════════════════════════════════════════════════
# 修復後的帳本（git 追蹤的 data_cache/macro_forward_test/signals.parquet）
# ══════════════════════════════════════════════════════════════════
_REPAIR_THROUGH = '2026-10-14'

#: 自 git 史撈回的 5 筆（HEAD 曾被後寫覆蓋）—— captured_at → (觀測日, icon, health, jqavg, git_sha, 來源 commit)
_RESTORED = {
    '2026-09-01T01:14:05+08:00': ('2026-08-31', '🟡', 60.2, 53.60, '79d59e0', 'f6fc4018'),
    '2026-09-15T00:00:06+08:00': ('2026-09-14', '🟡', 53.5, 49.12, '34e043e', '9d24ae06'),
    '2026-09-22T00:01:09+08:00': ('2026-09-21', '🟢', 71.9, 53.22, '6cc73c8', '8e813536'),
    '2026-10-02T00:41:47+08:00': ('2026-10-01', '🟢', 69.9, 49.86, '8499493', '91dbaac2'),
    '2026-10-14T01:07:55+08:00': ('2026-10-13', '🟢', 63.5, 52.52, '456be94', 'd8e00b18'),
}

#: 推導後與較早一筆同觀測日、依「保留最早」排除（仍在 git 史）。
_EXCLUDED = {'2026-09-25T22:44:28+08:00', '2026-09-29T01:48:58+08:00',
             '2026-10-10T00:33:30+08:00'}


@pytest.fixture(scope='module')
def ledger():
    return pd.read_parquet(_REPO / 'data_cache' / 'macro_forward_test' / 'signals.parquet')


@pytest.fixture(scope='module')
def tw_calendar():
    """已落地的 TWSE 盤後官方統計鏡像（三大法人 ∩ 融資）—— 僅交易日有值。

    不用 `twii_ohlcv.parquet`：實測其 HEAD 漏了 2026-09-22 一根（git 史中曾有），
    而 FinMind 兩個 TWSE 鏡像集都有 09-22 且值逐日不同（真交易日）。
    """
    def _d(name):
        df = pd.read_parquet(_REPO / 'data_cache' / f'{name}.parquet')
        return set(pd.to_datetime(df['date'].astype(str)).dt.strftime('%Y-%m-%d'))
    return {d for d in (_d('finmind_inst') & _d('finmind_margin')) if d <= _REPAIR_THROUGH}


class TestRepairedLedger:
    def test_columns_are_schema(self, ledger):
        assert list(ledger.columns) == list(MACRO_FWD_TEST_HEADERS)

    def test_date_unique(self, ledger):
        assert ledger['date'].is_unique, ledger['date'][ledger['date'].duplicated()].tolist()

    def test_dates_are_trading_days(self, ledger, tw_calendar):
        d = pd.to_datetime(ledger['date'])
        assert (d.dt.weekday < 5).all(), ledger['date'][d.dt.weekday >= 5].tolist()
        old = ledger[ledger['date'] <= _REPAIR_THROUGH]
        bad = sorted(set(old['date']) - tw_calendar)
        assert not bad, f'非交易日列:{bad}'

    def test_every_row_has_provenance(self, ledger):
        assert ledger['date_source'].isin(MACRO_FWD_TEST_DATE_SOURCES).all()

    def test_backfill_rows_have_no_fabricated_values(self, ledger):
        bf = ledger[ledger['date_source'] == DATE_SOURCE_BACKFILL]
        assert len(bf) >= 36
        assert bf['twii_close'].isna().all(), '回填列出現了 twii_close —— 當時沒抓到就是沒抓到'
        assert bf['inputs_as_of'].isna().all(), '推導日被偽裝成當時實抓的 inputs_as_of'

    def test_live_rows_are_self_consistent(self, ledger):
        lv = ledger[ledger['date_source'] == DATE_SOURCE_LIVE]
        assert (lv['inputs_as_of'] == lv['date']).all()
        assert lv['twii_close'].notna().all()

    def test_backfill_dates_follow_the_rule(self, ledger, tw_calendar):
        bf = ledger[ledger['date_source'] == DATE_SOURCE_BACKFILL]
        for cap, d in zip(bf['captured_at'], bf['date']):
            assert derive_observation_date(
                cap, tw_calendar, calendar_complete_through=_REPAIR_THROUGH) == d, cap

    def test_restored_rows_present_and_unchanged(self, ledger):
        by_cap = ledger.set_index('captured_at')
        for cap, (d, icon, health, jq, sha, _commit) in _RESTORED.items():
            assert cap in by_cap.index, f'git 史撈回的列不見了:{cap}（{_commit}）'
            r = by_cap.loc[cap]
            assert (r['date'], r['icon'], r['git_sha'], r['date_source']) == (
                d, icon, sha, DATE_SOURCE_BACKFILL)
            assert r['health'] == pytest.approx(health) and r['jqavg'] == pytest.approx(jq)
            assert r['ruleset_hash'] == '532c3a57698f' and int(r['schema_version']) == 1

    def test_dedup_excluded_rows_not_in_head(self, ledger):
        assert not (_EXCLUDED & set(ledger['captured_at']))


# ══════════════════════════════════════════════════════════════════
# NB-2（2026-10-15 稽核追加）
# ══════════════════════════════════════════════════════════════════
class TestNb2Guards:
    def test_append_signals_rejects_duplicate_keys_in_one_batch(self, tmp_path):
        from src.data.macro.macro_fwd_test_store import append_signals
        row = build_signal_row(_tl(), date='2026-08-18', captured_at='2026-08-18T18:00:00+08:00')
        p = tmp_path / 'signals.parquet'
        with pytest.raises(ValueError, match='同批'):
            append_signals([row, dict(row, icon='🟢')], p)
        assert not p.exists(), '同批重複鍵仍寫出了檔案'

    def test_github_output_key_matches_workflow(self, monkeypatch, tmp_path):
        import re

        import scripts.update_macro_forward_test as S
        out = tmp_path / 'gh_output'
        monkeypatch.setenv('GITHUB_OUTPUT', str(out))
        S._emit_github_output('2026-08-18')
        emitted = dict(line.split('=', 1) for line in out.read_text(encoding='utf-8').splitlines())
        assert emitted, '_emit_github_output 沒有寫出任何 key'

        yml = (_REPO / '.github' / 'workflows' / 'update_macro_forward_test.yml').read_text(
            encoding='utf-8')
        assert re.search(r'^\s*id:\s*capture\s*$', yml, re.M), 'workflow 腳本步驟缺 id: capture'
        used = set(re.findall(r'steps\.capture\.outputs\.(\w+)', yml))
        assert used, 'workflow 沒有讀 steps.capture.outputs.*'
        assert used <= set(emitted), (
            f'workflow 讀的 key {sorted(used)} 腳本沒寫出（腳本寫的是 {sorted(emitted)}）'
            ' —— commit 訊息會靜默退回 runner 日期')
        assert emitted['observation_date'] == '2026-08-18'

    def test_twii_unsorted_index_uses_last_trading_day(self):
        import scripts.update_macro_forward_test as S
        df = _twii(['2026-08-18', '2026-08-14', '2026-08-17'], [103.0, 101.0, 102.0])
        assert S._twii_close_and_asof({'台股加權指數': df}) == (103.0, '2026-08-18')
