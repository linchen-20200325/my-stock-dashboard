"""P0-FWD-STORE-FAILCLOSED — 總經前進式驗證帳本 `macro_fwd_test_store` 的 fail-closed 守衛。

病史:舊版 `load_signals()` 對「檔案存在但讀不出來」(損壞 / 截斷 / 權限 / 非 parquet)
只 print 後回 [];`append_signals()` 於是把它當成空帳本,用「只有新一列」的內容
**覆寫整本凍結帳本**。帳本是唯一的無 lookahead 樣本,覆寫 = 不可逆的歷史消失(§1)。

契約:
  檔不存在 → [] / 首次建檔(合法);合法 parquet 0 列 → [](空帳本);
  檔存在但讀不出來 → `LedgerReadError`,append 傳播同例外且**不寫入任何位元組**。

突變驗證(自動化,見 `TestMutationsAreCaught`):
  M1 把讀取失敗改回 `return []`          → 故障注入檢查必須轉紅
  M2 在讀舊檔之前先寫入                   → 故障注入檢查必須轉紅
"""
from __future__ import annotations

import hashlib
import os
import types
from pathlib import Path

import pandas as pd
import pytest

from shared.macro_forward_test_schema import MACRO_FWD_TEST_HEADERS, MACRO_FWD_TEST_KEY
from src.compute.macro.macro_forward_test import build_signal_row
import src.data.macro.macro_fwd_test_store as store
from src.data.macro.macro_fwd_test_store import LedgerReadError, append_signals, load_signals

_STORE_SRC = Path(store.__file__)


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


def _row(date='2026-08-18', **over):
    kw = dict(date=date, captured_at=f'{date}T17:40:00+08:00', twii_close=23500.0,
              inputs_as_of=date, git_sha='abc1234', ruleset_hash='deadbeef0000')
    tl = over.pop('tl', _tl())
    kw.update(over)
    return build_signal_row(tl, **kw)


def _snapshot(root: Path) -> dict:
    """目錄 / 檔案狀態快照:相對路徑 → (sha256 或 None, mtime_ns, size)。"""
    snap: dict = {}
    if root.is_file() or root.is_symlink():
        root = root.parent
    for dp, dns, fns in os.walk(root):
        for n in dns + fns:
            fp = Path(dp) / n
            rel = str(fp.relative_to(root))
            if fp.is_file():
                st = fp.stat()
                snap[rel] = (hashlib.sha256(fp.read_bytes()).hexdigest(), st.st_mtime_ns, st.st_size)
            else:
                snap[rel] = (None, None, None)
    return snap


# ── 故障注入:每個 case 在 tmp_path 內造出一個「已存在但讀不出來」的帳本 ──────────
def _mk_random_bytes(p: Path) -> None:
    p.write_bytes(bytes(range(256)) * 8)


def _mk_zero_bytes(p: Path) -> None:
    p.write_bytes(b'')


def _mk_truncated_parquet(p: Path) -> None:
    pd.DataFrame([_row()]).to_parquet(p, index=False)
    raw = p.read_bytes()
    p.write_bytes(raw[: len(raw) // 2])


def _mk_text_file(p: Path) -> None:
    p.write_text('this is not a parquet file\n', encoding='utf-8')


def _mk_directory(p: Path) -> None:
    p.mkdir()
    (p / 'child.txt').write_text('x', encoding='utf-8')


def _mk_parquet_without_key(p: Path) -> None:
    pd.DataFrame({'foo': [1, 2], 'bar': ['a', 'b']}).to_parquet(p, index=False)


def _mk_dangling_symlink(p: Path) -> None:
    os.symlink(p.parent / 'no_such_target.parquet', p)


_FILE_CASES = {
    'random_bytes': _mk_random_bytes,
    'zero_bytes': _mk_zero_bytes,
    'truncated_parquet': _mk_truncated_parquet,
    'text_file': _mk_text_file,
    'directory_masquerade': _mk_directory,
    'parquet_without_key_column': _mk_parquet_without_key,
    'dangling_symlink': _mk_dangling_symlink,
}


def _good_parquet(p: Path) -> None:
    pd.DataFrame([_row('2026-08-17')]).to_parquet(p, index=False)


# 讀取注入:檔本身是合法 parquet,但 pandas 讀取時丟各種例外
def _raise_factory(exc):
    def _boom(*a, **k):
        raise exc
    return _boom


def _arrow_invalid():
    import pyarrow as pa
    return pa.ArrowInvalid('Parquet magic bytes not found in footer')


_INJECTIONS = {
    'OSError': lambda: OSError('I/O error'),
    'PermissionError': lambda: PermissionError(13, 'Permission denied'),
    'ArrowInvalid': _arrow_invalid,
    'ValueError': lambda: ValueError('cannot parse'),
    'ImportError_engine': lambda: ImportError('no parquet engine'),
}


def _check_fail_closed(mod, ledger: Path, new_row: dict) -> list[str]:
    """對給定 store 模組(真實或突變版)檢查 fail-closed 契約,回違規清單(空 = 合規)。"""
    bad: list[str] = []
    before = _snapshot(ledger.parent)
    try:
        got = mod.load_signals(ledger)
        bad.append(f'load_signals 未丟例外,回 {got!r}')
    except mod.LedgerReadError:
        pass
    try:
        n = mod.append_signals([new_row], ledger)
        bad.append(f'append_signals 未丟例外,回 {n!r}')
    except mod.LedgerReadError:
        pass
    if _snapshot(ledger.parent) != before:
        bad.append('檔案系統狀態被改動(bytes / mtime / 新增檔)')
    return bad


# ═════════════════════════════════════════════════════════════════════
class TestCorruptLedgerFailsClosed:
    @pytest.mark.parametrize('name', sorted(_FILE_CASES))
    def test_load_and_append_raise_and_nothing_written(self, tmp_path, name):
        led = tmp_path / 'signals.parquet'
        _FILE_CASES[name](led)
        before = _snapshot(tmp_path)
        with pytest.raises(LedgerReadError) as ei:
            load_signals(led)
        assert str(led) in str(ei.value) and 'fail-closed' in str(ei.value)
        with pytest.raises(LedgerReadError):
            append_signals([_row()], led)
        assert _snapshot(tmp_path) == before, '故障帳本被改動'
        assert not list(tmp_path.glob('*.tmp')) and not list(tmp_path.glob('.*'))

    def test_error_names_cause_type(self, tmp_path):
        led = tmp_path / 'signals.parquet'
        _mk_text_file(led)
        with pytest.raises(LedgerReadError, match=r'(ArrowInvalid|ArrowIOError|OSError|ValueError)'):
            load_signals(led)

    def test_chmod_000_unreadable(self, tmp_path):
        led = tmp_path / 'signals.parquet'
        _good_parquet(led)
        led.chmod(0)
        try:
            if os.access(led, os.R_OK):
                pytest.skip('以 root 執行,chmod 000 無效;改由注入測試涵蓋 PermissionError')
            # 不可讀檔無法算 sha;改比 stat(mtime/size)+ 目錄清單
            st0 = led.stat()
            with pytest.raises(LedgerReadError):
                load_signals(led)
            with pytest.raises(LedgerReadError):
                append_signals([_row()], led)
            st1 = led.stat()
            assert (st0.st_mtime_ns, st0.st_size) == (st1.st_mtime_ns, st1.st_size)
            assert sorted(p.name for p in tmp_path.iterdir()) == ['signals.parquet']
        finally:
            led.chmod(0o644)

    @pytest.mark.parametrize('name', sorted(_INJECTIONS))
    def test_pandas_read_injection(self, tmp_path, monkeypatch, name):
        led = tmp_path / 'signals.parquet'
        _good_parquet(led)
        before = _snapshot(tmp_path)
        monkeypatch.setattr(pd, 'read_parquet', _raise_factory(_INJECTIONS[name]()))
        with pytest.raises(LedgerReadError):
            load_signals(led)
        with pytest.raises(LedgerReadError):
            append_signals([_row()], led)
        monkeypatch.undo()
        assert _snapshot(tmp_path) == before
        assert [r['date'] for r in load_signals(led)] == ['2026-08-17'], '原帳本內容應完整保留'

    def test_to_parquet_never_reached_when_read_fails(self, tmp_path, monkeypatch):
        """寫入函式在讀取失敗時根本不得被呼叫(不只是結果相同)。"""
        led = tmp_path / 'signals.parquet'
        _mk_random_bytes(led)
        calls: list = []
        monkeypatch.setattr(pd.DataFrame, 'to_parquet', lambda *a, **k: calls.append(a))
        with pytest.raises(LedgerReadError):
            append_signals([_row()], led)
        assert calls == []

    def test_missing_parent_dir_is_first_time_not_error(self, tmp_path):
        led = tmp_path / 'not' / 'yet' / 'signals.parquet'
        assert load_signals(led) == []
        assert append_signals([_row()], led) == 1

    def test_parent_dir_is_a_file_fails_closed(self, tmp_path):
        """父路徑是檔案(ENOTDIR):存在性無法判定,不得當成首次建檔。"""
        (tmp_path / 'blocker').write_text('x', encoding='utf-8')
        led = tmp_path / 'blocker' / 'signals.parquet'
        with pytest.raises(LedgerReadError):
            load_signals(led)
        with pytest.raises(LedgerReadError):
            append_signals([_row()], led)
        assert sorted(p.name for p in tmp_path.iterdir()) == ['blocker']


# ═════════════════════════════════════════════════════════════════════
class TestPreservedBehaviour:
    def test_missing_file_returns_empty_and_first_write_creates(self, tmp_path):
        led = tmp_path / 'signals.parquet'
        assert load_signals(led) == []
        assert append_signals([_row()], led) == 1
        got = load_signals(led)
        assert [r['date'] for r in got] == ['2026-08-18']
        assert list(pd.read_parquet(led).columns) == list(MACRO_FWD_TEST_HEADERS)

    def test_valid_empty_parquet_is_empty_ledger(self, tmp_path):
        led = tmp_path / 'signals.parquet'
        pd.DataFrame({c: pd.Series([], dtype=object) for c in MACRO_FWD_TEST_HEADERS}).to_parquet(led, index=False)
        assert load_signals(led) == []
        assert append_signals([_row()], led) == 1
        assert len(load_signals(led)) == 1

    def test_valid_zero_column_empty_parquet_is_empty_ledger(self, tmp_path):
        led = tmp_path / 'signals.parquet'
        pd.DataFrame().to_parquet(led, index=False)
        assert load_signals(led) == []
        assert append_signals([_row()], led) == 1

    def test_same_date_is_idempotent_and_does_not_rewrite(self, tmp_path):
        led = tmp_path / 'signals.parquet'
        assert append_signals([_row()], led) == 1
        before = _snapshot(tmp_path)
        assert append_signals([_row(tl=_tl(icon='🟡', label='中性'))], led) == 0
        assert _snapshot(tmp_path) == before, '同 date 重跑不得重寫檔(bytes / mtime)'
        assert load_signals(led)[0]['icon'] == '🔴', '保留既有、不覆寫'

    def test_different_date_appends_and_keeps_old_rows_columnwise(self, tmp_path):
        led = tmp_path / 'signals.parquet'
        assert append_signals([_row('2026-08-17')], led) == 1
        old = pd.read_parquet(led).iloc[0].to_dict()
        assert append_signals([_row('2026-08-18')], led) == 1
        df = pd.read_parquet(led)
        assert list(df[MACRO_FWD_TEST_KEY]) == ['2026-08-17', '2026-08-18']
        assert list(df.columns) == list(MACRO_FWD_TEST_HEADERS)
        pd.testing.assert_series_equal(
            df.iloc[0], pd.Series(old), check_names=False)

    def test_sorted_by_date_even_when_appended_out_of_order(self, tmp_path):
        led = tmp_path / 'signals.parquet'
        append_signals([_row('2026-08-19')], led)
        append_signals([_row('2026-08-17')], led)
        assert [r['date'] for r in load_signals(led)] == ['2026-08-17', '2026-08-19']

    def test_validation_errors_still_valueerror_and_write_nothing(self, tmp_path):
        led = tmp_path / 'signals.parquet'
        with pytest.raises(ValueError, match='缺唯一鍵'):
            append_signals([{'foo': 1}], led)
        with pytest.raises(ValueError, match='schema 外'):
            append_signals([dict(_row(), bogus=1)], led)
        with pytest.raises(ValueError, match='重複'):
            append_signals([_row(), _row()], led)
        assert list(tmp_path.iterdir()) == []

    def test_old_ledger_missing_new_columns_still_readable(self, tmp_path):
        """schema-additive:舊檔缺新欄 ≠ 損壞,新欄補 None(不補 0)。"""
        led = tmp_path / 'signals.parquet'
        old = _row('2026-08-17')
        legacy = {k: v for k, v in old.items() if k != MACRO_FWD_TEST_HEADERS[-1]}
        pd.DataFrame([legacy]).to_parquet(led, index=False)
        assert append_signals([_row('2026-08-18')], led) == 1
        df = pd.read_parquet(led)
        assert len(df) == 2 and pd.isna(df.iloc[0][MACRO_FWD_TEST_HEADERS[-1]])


# ═════════════════════════════════════════════════════════════════════
def _load_mutant(replacements: list[tuple[str, str]]) -> types.ModuleType:
    src = _STORE_SRC.read_text(encoding='utf-8')
    for old, new in replacements:
        assert src.count(old) == 1, f'突變錨點必須唯一存在:{old!r}'
        src = src.replace(old, new)
    mod = types.ModuleType('mutant_store')
    mod.__file__ = str(_STORE_SRC)
    exec(compile(src, str(_STORE_SRC), 'exec'), mod.__dict__)  # noqa: S102 — 僅測試內自讀原始碼
    return mod


_M1 = [("        raise _ledger_error(p, _e) from _e\n\n\n",
        "        return []\n\n\n")]
_M2 = [("    _old = pd.DataFrame(load_signals(path))\n",
        "    pd.DataFrame(_rows).to_parquet(Path(path) if path else MACRO_FWD_TEST_PATH, index=False)\n"
        "    _old = pd.DataFrame(load_signals(path))\n")]


class TestMutationsAreCaught:
    def test_unmutated_module_passes_the_checker(self, tmp_path):
        """基準:檢查器對真實模組回空清單(否則突變測試沒有意義)。"""
        mod = _load_mutant([])
        for name, mk in _FILE_CASES.items():
            d = tmp_path / name
            d.mkdir()
            led = d / 'signals.parquet'
            mk(led)
            assert _check_fail_closed(mod, led, _row()) == [], name

    @pytest.mark.parametrize('label,repl', [('M1_except_return_empty', _M1),
                                            ('M2_write_before_read', _M2)])
    def test_mutant_turns_checker_red(self, tmp_path, label, repl):
        mod = _load_mutant(repl)
        caught = 0
        for name, mk in _FILE_CASES.items():
            d = tmp_path / name
            d.mkdir()
            led = d / 'signals.parquet'
            mk(led)
            try:
                bad = _check_fail_closed(mod, led, _row())
            except Exception as e:  # noqa: BLE001 — 突變版以非預期方式炸也算被抓到
                bad = [f'unexpected {type(e).__name__}']
            caught += bool(bad)
        assert caught >= 4, f'{label} 只被 {caught}/{len(_FILE_CASES)} 個 case 抓到'


# ═════════════════════════════════════════════════════════════════════
class TestCronScriptPropagates:
    """cron 腳本不吞 LedgerReadError:例外傳出 `main()` → 直譯器以非零碼(1)結束並印 traceback。

    刻意**不**在腳本內 try/except 轉 `return 1`:腳本內容被 `tests/test_c1_observability.py` 的還原鏈
    逐位 sha 釘住,改它要新增一整節還原鏈,超出本批最小必要範圍。未捕捉例外的退出碼 1 已滿足
    「非零 + 明確錯誤、不當成功、不寫半套」;workflow 該步失敗 → 後續 publish 步驟不執行。
    """

    def test_main_raises_and_ledger_untouched(self, monkeypatch, tmp_path):
        from tests.test_macro_fwd_test_c12 import _isolate, _twii
        led = tmp_path / 'signals.parquet'
        _mk_random_bytes(led)
        before = _snapshot(tmp_path)
        S, st = _isolate(monkeypatch, tmp_path,
                         tw_raw={'台股加權指數': _twii(['2026-08-17', '2026-08-18'], [1.0, 2.0], 'close')},
                         now_iso='2026-08-18T17:40:00+08:00')
        with pytest.raises(LedgerReadError, match='fail-closed'):
            S.main([])      # 傳出例外 = 不 return 0;`sys.exit(main())` 之外的未捕捉例外 → exit code 1
        assert _snapshot(tmp_path) == before

    def test_dry_run_does_not_touch_ledger(self, monkeypatch, tmp_path):
        from tests.test_macro_fwd_test_c12 import _isolate, _twii
        led = tmp_path / 'signals.parquet'
        _mk_random_bytes(led)
        before = _snapshot(tmp_path)
        S, st = _isolate(monkeypatch, tmp_path,
                         tw_raw={'台股加權指數': _twii(['2026-08-17', '2026-08-18'], [1.0, 2.0], 'close')},
                         now_iso='2026-08-18T17:40:00+08:00')
        assert S.main(['--dry-run']) == 0
        assert _snapshot(tmp_path) == before
