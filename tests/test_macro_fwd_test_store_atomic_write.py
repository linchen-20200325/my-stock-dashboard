"""P0-FWD-STORE-ATOMIC-WRITE — `macro_fwd_test_store.append_signals` 的原子寫入守衛。

病史:舊版 `_out.to_parquet(正式路徑)` 直接寫,寫到一半失敗(磁碟滿 / 中斷)會留下半個 parquet,
凍結帳本(唯一無 lookahead 樣本)被毀。現行:同目錄暫存檔 → fsync → 讀回驗證 → `os.replace`。

突變驗證(自動,見 `TestMutationsAreCaught`):
  ① 原子路徑改回直接 `to_parquet(p)`      → 中途失敗檢查轉紅
  ② 拿掉 finally 清理                      → tmp 殘留檢查轉紅
  ③ 拿掉驗證(讀回結果改成 df 自己)       → 竄改檢查轉紅
  ④ 拿掉 os.replace 改直接複製覆蓋          → replace 失敗檢查轉紅
"""
from __future__ import annotations

import errno
import os
import shutil
import types
from pathlib import Path

import pandas as pd
import pytest

from shared.macro_forward_test_schema import MACRO_FWD_TEST_HEADERS, MACRO_FWD_TEST_KEY
import src.data.macro.macro_fwd_test_store as store
from src.data.macro.macro_fwd_test_store import (
    LedgerReadError,
    LedgerWriteError,
    append_signals,
    load_signals,
)
from tests.test_macro_fwd_test_store_fail_closed import _row, _snapshot

_STORE_SRC = Path(store.__file__)


def _seed(led: Path, dates=('2026-08-17',)) -> None:
    for d in dates:
        append_signals([_row(d)], led)


def _tmp_leftovers(d: Path) -> list[str]:
    return sorted(p.name for p in d.rglob('*') if p.name.endswith('.tmp'))


def _partial_then_raise(exc: BaseException):
    """取代 `DataFrame.to_parquet`:先往目的地寫幾個位元組(模擬寫到一半),再丟例外。"""
    def _fake(self, path_or_buf=None, *a, **k):
        if hasattr(path_or_buf, 'write'):
            path_or_buf.write(b'PAR1-half-written')
            path_or_buf.flush()
        else:
            with open(path_or_buf, 'wb') as fh:
                fh.write(b'PAR1-half-written')
        raise exc
    return _fake


# ── 故障檢查器:對給定 store 模組(真實或突變版)回違規清單,空 = 合規 ─────────────
def _check_midwrite(mod, d: Path, mp) -> list[str]:
    led = d / 'signals.parquet'
    mod.append_signals([_row('2026-08-17')], led)
    before = _snapshot(d)
    mp.setattr(pd.DataFrame, 'to_parquet', _partial_then_raise(OSError(errno.EIO, 'I/O error')))
    bad: list[str] = []
    try:
        mod.append_signals([_row('2026-08-18')], led)
        bad.append('未丟例外')
    except mod.LedgerWriteError as e:
        if not isinstance(e.__cause__, OSError):
            bad.append('缺 __cause__')
    except Exception as e:  # noqa: BLE001
        bad.append(f'例外型別不是 LedgerWriteError:{type(e).__name__}')
    mp.undo()
    if _snapshot(d) != before:
        bad.append('正式檔 / 目錄被改動')
    return bad


_DRIFT_KINDS = ('rel_drift', 'zero_to_tiny', 'float32', 'round2', 'bool_to_int', 'int_to_float')


def _tamper_patch(mp, kind: str):
    real_read = pd.read_parquet

    def _read(path, *a, **k):
        df = real_read(path, *a, **k)
        if not str(path).endswith('.tmp'):
            return df
        if kind == 'drop_row':
            return df.iloc[:-1]
        if kind == 'drop_col':
            return df.drop(columns=[MACRO_FWD_TEST_HEADERS[-1]])
        if kind == 'alter_value':
            df = df.copy()
            df.loc[df.index[0], 'twii_close'] = float(df.loc[df.index[0], 'twii_close']) + 1.0
            return df
        df = df.copy()
        if kind == 'rel_drift':          # +9e-6 相對偏移(< assert_frame_equal 預設 rtol=1e-5)
            df['twii_close'] = df['twii_close'] * (1 + 9e-6)
            return df
        if kind == 'zero_to_tiny':       # 0.0 → 1e-9(< 預設 atol=1e-8)
            df['health'] = df['health'].where(df['health'] != 0.0, 1e-9)
            return df
        if kind == 'float32':            # float32 截斷
            df['twii_close'] = df['twii_close'].astype('float32')
            return df
        if kind == 'round2':             # 四捨五入到 2 位
            df['twii_close'] = df['twii_close'].round(2)
            return df
        if kind == 'bool_to_int':
            df['defense'] = df['defense'].astype('int64')
            return df
        if kind == 'int_to_float':
            df['conf'] = df['conf'].astype('float64')
            return df
        raise AssertionError(kind)
    mp.setattr(pd, 'read_parquet', _read)


def _drift_seed_row() -> dict:
    """含「非整數 float」與「0.0」的種子列:讓微小漂移類竄改有東西可漂。"""
    from tests.test_macro_fwd_test_store_fail_closed import _tl
    return _row('2026-08-17', twii_close=23456.123456789, tl=_tl(health=0.0))


def _check_tamper(mod, d: Path, mp, kind: str) -> list[str]:
    led = d / 'signals.parquet'
    mod.append_signals([_drift_seed_row() if kind in _DRIFT_KINDS else _row('2026-08-17')], led)
    before = _snapshot(d)
    _tamper_patch(mp, kind)
    bad: list[str] = []
    try:
        mod.append_signals([_row('2026-08-18')], led)
        bad.append('驗證沒擋下竄改的新檔')
    except mod.LedgerWriteError:
        pass
    mp.undo()
    if _snapshot(d) != before:
        bad.append('正式檔 / 目錄被改動(含殘留 tmp)')
    return bad


def _check_replace_fail(mod, d: Path, mp) -> list[str]:
    led = d / 'signals.parquet'
    mod.append_signals([_row('2026-08-17')], led)
    before = _snapshot(d)

    def _boom(*a, **k):
        raise OSError(errno.EXDEV, 'Invalid cross-device link')
    mp.setattr(os, 'replace', _boom)
    bad: list[str] = []
    try:
        mod.append_signals([_row('2026-08-18')], led)
        bad.append('未丟例外')
    except mod.LedgerWriteError:
        pass
    mp.undo()
    if _snapshot(d) != before:
        bad.append('正式檔 / 目錄被改動')
    return bad


# ═════════════════════════════════════════════════════════════════════
class TestWriteFailuresLeaveLedgerIntact:
    def test_midwrite_oserror(self, tmp_path, monkeypatch):
        assert _check_midwrite(store, tmp_path, monkeypatch) == []

    def test_disk_full_enospc(self, tmp_path, monkeypatch):
        led = tmp_path / 'signals.parquet'
        _seed(led)
        before = _snapshot(tmp_path)
        monkeypatch.setattr(pd.DataFrame, 'to_parquet',
                            _partial_then_raise(OSError(errno.ENOSPC, 'No space left on device')))
        with pytest.raises(LedgerWriteError) as ei:
            append_signals([_row('2026-08-18')], led)
        assert isinstance(ei.value.__cause__, OSError) and ei.value.__cause__.errno == errno.ENOSPC
        assert str(led) in str(ei.value) and '未替換正式檔' in str(ei.value)
        monkeypatch.undo()
        assert _snapshot(tmp_path) == before and _tmp_leftovers(tmp_path) == []

    def test_pyarrow_exception_wrapped(self, tmp_path, monkeypatch):
        import pyarrow as pa
        led = tmp_path / 'signals.parquet'
        _seed(led)
        before = _snapshot(tmp_path)
        monkeypatch.setattr(pd.DataFrame, 'to_parquet', _partial_then_raise(pa.ArrowInvalid('boom')))
        with pytest.raises(LedgerWriteError) as ei:
            append_signals([_row('2026-08-18')], led)
        assert isinstance(ei.value.__cause__, pa.ArrowInvalid)
        monkeypatch.undo()
        assert _snapshot(tmp_path) == before

    def test_replace_failure(self, tmp_path, monkeypatch):
        assert _check_replace_fail(store, tmp_path, monkeypatch) == []

    def test_fsync_failure(self, tmp_path, monkeypatch):
        led = tmp_path / 'signals.parquet'
        _seed(led)
        before = _snapshot(tmp_path)

        def _boom(fd):
            raise OSError(errno.EIO, 'fsync failed')
        monkeypatch.setattr(os, 'fsync', _boom)
        with pytest.raises(LedgerWriteError) as ei:
            append_signals([_row('2026-08-18')], led)
        assert isinstance(ei.value.__cause__, OSError)
        monkeypatch.undo()
        assert _snapshot(tmp_path) == before and _tmp_leftovers(tmp_path) == []

    @pytest.mark.parametrize('kind', ['drop_row', 'drop_col', 'alter_value', *_DRIFT_KINDS])
    def test_verification_failure_does_not_replace(self, tmp_path, monkeypatch, kind):
        """含微小漂移:+9e-6 相對、0.0→1e-9、float32 截斷、四捨五入、bool→int、int→float 皆須擋下。"""
        assert _check_tamper(store, tmp_path, monkeypatch, kind) == []

    def test_readonly_existing_ledger_refused_before_tmp(self, tmp_path, monkeypatch):
        """D2:唯讀既有帳本 → 在建 tmp 之前拒寫(`os.replace` 不看檔案權限,否則會靜默替換)。"""
        import tempfile
        led = tmp_path / 'signals.parquet'
        _seed(led)
        before = _snapshot(tmp_path)
        calls: list = []
        real = tempfile.mkstemp
        monkeypatch.setattr(tempfile, 'mkstemp', lambda *a, **k: calls.append(1) or real(*a, **k))
        real_access = os.access
        monkeypatch.setattr(os, 'access', lambda p, m, *a, **k:
                            False if (Path(p) == led and m == os.W_OK) else real_access(p, m, *a, **k))
        with pytest.raises(LedgerWriteError, match='帳本唯讀，已拒絕寫入'):
            append_signals([_row('2026-08-18')], led)
        assert calls == []
        monkeypatch.undo()
        assert _snapshot(tmp_path) == before

    @pytest.mark.skipif(os.name != 'posix', reason='chmod 0444 語意僅 POSIX')
    def test_real_chmod_0444_refused_when_not_root(self, tmp_path):
        led = tmp_path / 'signals.parquet'
        _seed(led)
        led.chmod(0o444)
        try:
            if os.access(led, os.W_OK):
                pytest.skip('以 root 執行,os.access 恆真;由注入測試涵蓋 D2')
            before = _snapshot(tmp_path)
            with pytest.raises(LedgerWriteError, match='唯讀'):
                append_signals([_row('2026-08-18')], led)
            assert _snapshot(tmp_path) == before
        finally:
            led.chmod(0o644)

    def test_first_creation_failure_leaves_no_ledger_no_tmp(self, tmp_path, monkeypatch):
        d = tmp_path / 'fresh'
        led = d / 'signals.parquet'
        monkeypatch.setattr(pd.DataFrame, 'to_parquet', _partial_then_raise(OSError(errno.ENOSPC, 'full')))
        with pytest.raises(LedgerWriteError):
            append_signals([_row()], led)
        monkeypatch.undo()
        assert not led.exists()
        assert list(d.iterdir()) == [], '首次建檔失敗不得留下半檔或 tmp(目錄可存在)'

    def test_dir_fsync_failure_after_replace_is_not_fatal(self, tmp_path, monkeypatch):
        """replace 已完成後,目錄 fsync 失敗只 log:新檔已是完整正式檔。"""
        if os.name == 'nt':
            assert append_signals([_row()], tmp_path / 's.parquet') == 1   # Windows:略過目錄 fsync
            return
        led = tmp_path / 'signals.parquet'
        real_open = os.open

        def _open(p, flags, *a, **k):
            if flags == os.O_RDONLY and Path(p) == tmp_path:
                raise PermissionError(errno.EACCES, 'no dir open')
            return real_open(p, flags, *a, **k)
        monkeypatch.setattr(os, 'open', _open)
        assert append_signals([_row()], led) == 1
        monkeypatch.undo()
        assert [r['date'] for r in load_signals(led)] == ['2026-08-18']
        assert _tmp_leftovers(tmp_path) == []


# ═════════════════════════════════════════════════════════════════════
class TestSuccessPaths:
    def test_append_keeps_old_rows_columnwise_sorted_and_ordered(self, tmp_path):
        led = tmp_path / 'signals.parquet'
        _seed(led, ('2026-08-19', '2026-08-17'))
        old = pd.read_parquet(led)
        assert append_signals([_row('2026-08-18')], led) == 1
        new = pd.read_parquet(led)
        assert list(new[MACRO_FWD_TEST_KEY]) == ['2026-08-17', '2026-08-18', '2026-08-19']
        assert list(new.columns) == list(MACRO_FWD_TEST_HEADERS)
        for d in ('2026-08-17', '2026-08-19'):
            pd.testing.assert_series_equal(
                new[new[MACRO_FWD_TEST_KEY] == d].iloc[0],
                old[old[MACRO_FWD_TEST_KEY] == d].iloc[0], check_names=False)
        assert _tmp_leftovers(tmp_path) == []

    def test_first_creation_creates_parent_dirs(self, tmp_path):
        led = tmp_path / 'a' / 'b' / 'signals.parquet'
        assert append_signals([_row()], led) == 1
        assert led.is_file() and _tmp_leftovers(tmp_path) == []

    def test_duplicate_date_touches_nothing_and_creates_no_tmp(self, tmp_path, monkeypatch):
        import tempfile
        led = tmp_path / 'signals.parquet'
        _seed(led)
        before = _snapshot(tmp_path)
        calls: list = []
        real = tempfile.mkstemp
        monkeypatch.setattr(tempfile, 'mkstemp', lambda *a, **k: calls.append(1) or real(*a, **k))
        assert append_signals([_row('2026-08-17', tl=dict(icon='🟡'))], led) == 0
        assert calls == [], '同日冪等路徑不得建暫存檔'
        monkeypatch.undo()
        assert _snapshot(tmp_path) == before

    def test_real_committed_ledger_roundtrips_through_verification(self, tmp_path):
        """用 repo 內真實帳本(NaN / None / 混合型別欄位)驗證「讀回驗證」不會對真資料誤殺。"""
        src = store.MACRO_FWD_TEST_PATH
        if not src.is_file():
            pytest.skip('repo 內無真實帳本')
        led = tmp_path / 'signals.parquet'
        shutil.copyfile(src, led)
        old = load_signals(led)
        assert append_signals([_row('2099-01-02')], led) == 1
        new = load_signals(led)
        assert len(new) == len(old) + 1
        assert [r[MACRO_FWD_TEST_KEY] for r in new[:-1]] == [r[MACRO_FWD_TEST_KEY] for r in old]


class TestSymlinkLedger:
    @pytest.mark.skipif(not hasattr(os, 'symlink'), reason='no symlink')
    def test_writes_through_symlink_and_keeps_link(self, tmp_path):
        real_dir = tmp_path / 'real'
        real_dir.mkdir()
        target = real_dir / 'signals.parquet'
        _seed(target)
        link = tmp_path / 'link.parquet'
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            pytest.skip('此環境不能建 symlink')
        assert append_signals([_row('2026-08-18')], link) == 1
        assert link.is_symlink(), 'symlink 本身必須保留'
        assert [r['date'] for r in load_signals(target)] == ['2026-08-17', '2026-08-18']
        assert _tmp_leftovers(tmp_path) == []

    @pytest.mark.skipif(not hasattr(os, 'symlink'), reason='no symlink')
    def test_failure_through_symlink_leaves_target_unchanged(self, tmp_path, monkeypatch):
        real_dir = tmp_path / 'real'
        real_dir.mkdir()
        target = real_dir / 'signals.parquet'
        _seed(target)
        link = tmp_path / 'link.parquet'
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            pytest.skip('此環境不能建 symlink')
        before = _snapshot(real_dir)
        monkeypatch.setattr(pd.DataFrame, 'to_parquet', _partial_then_raise(OSError(errno.EIO, 'x')))
        with pytest.raises(LedgerWriteError):
            append_signals([_row('2026-08-18')], link)
        monkeypatch.undo()
        assert link.is_symlink() and _snapshot(real_dir) == before and _tmp_leftovers(tmp_path) == []

    @pytest.mark.skipif(not hasattr(os, 'symlink'), reason='no symlink')
    def test_tmp_is_created_next_to_the_real_target(self, tmp_path, monkeypatch):
        import tempfile
        real_dir = tmp_path / 'real'
        real_dir.mkdir()
        target = real_dir / 'signals.parquet'
        _seed(target)
        link = tmp_path / 'link.parquet'
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            pytest.skip('此環境不能建 symlink')
        seen: list = []
        real = tempfile.mkstemp
        monkeypatch.setattr(tempfile, 'mkstemp', lambda *a, **k: seen.append(k) or real(*a, **k))
        append_signals([_row('2026-08-18')], link)
        monkeypatch.undo()
        assert Path(seen[0]['dir']).resolve() == real_dir.resolve()
        assert seen[0]['prefix'].startswith('.signals.parquet.') and seen[0]['suffix'] == '.tmp'


class TestPermissions:
    def test_existing_ledger_mode_preserved(self, tmp_path):
        led = tmp_path / 'signals.parquet'
        _seed(led)
        if os.name == 'posix':
            led.chmod(0o640)
        append_signals([_row('2026-08-18')], led)
        if os.name == 'posix':
            assert (led.stat().st_mode & 0o777) == 0o640
        else:   # Windows 只有唯讀位:至少檔案可讀可寫
            assert os.access(led, os.R_OK | os.W_OK)

    def test_new_ledger_mode_is_0644_not_mkstemp_0600(self, tmp_path):
        led = tmp_path / 'signals.parquet'
        append_signals([_row()], led)
        if os.name == 'posix':
            assert (led.stat().st_mode & 0o777) == 0o644
        else:
            assert os.access(led, os.R_OK | os.W_OK)


class TestIssue1041Regression:
    def test_corrupt_ledger_still_fail_closed_without_tmp(self, tmp_path, monkeypatch):
        import tempfile
        led = tmp_path / 'signals.parquet'
        led.write_bytes(bytes(range(256)))
        before = _snapshot(tmp_path)
        calls: list = []
        monkeypatch.setattr(tempfile, 'mkstemp', lambda *a, **k: calls.append(1))
        with pytest.raises(LedgerReadError):
            append_signals([_row()], led)
        monkeypatch.undo()
        assert calls == [] and _snapshot(tmp_path) == before

    def test_validation_errors_still_valueerror(self, tmp_path):
        led = tmp_path / 'signals.parquet'
        with pytest.raises(ValueError, match='缺唯一鍵'):
            append_signals([{'foo': 1}], led)
        with pytest.raises(ValueError, match='schema 外'):
            append_signals([dict(_row(), bogus=1)], led)
        with pytest.raises(ValueError, match='重複'):
            append_signals([_row(), _row()], led)
        assert list(tmp_path.iterdir()) == []


# ═════════════════════════════════════════════════════════════════════
def _load_mutant(replacements: list[tuple[str, str]]) -> types.ModuleType:
    src = _STORE_SRC.read_text(encoding='utf-8')
    for old, new in replacements:
        assert src.count(old) == 1, f'突變錨點必須唯一存在:{old!r}'
        src = src.replace(old, new)
    mod = types.ModuleType('mutant_store_atomic')
    mod.__file__ = str(_STORE_SRC)
    exec(compile(src, str(_STORE_SRC), 'exec'), mod.__dict__)  # noqa: S102 — 僅測試內自讀原始碼
    return mod


_MUT_DIRECT = [("    _atomic_write_parquet(_out, p)\n", "    _out.to_parquet(p, index=False)\n")]
_MUT_NO_FINALLY = [("        if tmp is not None:\n            try:\n                os.unlink(tmp)",
                    "        if False:\n            try:\n                os.unlink(tmp)")]
_MUT_NO_VERIFY = [("            chk = pd.read_parquet(tmp)\n", "            chk = df\n")]
_MUT_NO_REPLACE = [("            os.replace(tmp, real)\n", "            shutil.copyfile(tmp, real)\n")]


# D6 之後純量層已是獨立必經檢查:單獨拿掉 check_exact 不再讓漂移漏網(縱深層被純量層覆蓋);
# 因此 check_exact 的獨立價值改為「純量層也被拿掉時,它仍是最後一道防線」。
_MUT_NO_EXACT_ONLY = [("check_dtype=False, check_exact=True)", "check_dtype=False)"),
                      ("            if not nx and not _scalar_exactly_equal(x, y):", "            if False:")]
_MUT_NO_TYPES = [("        if ka in 'biufcM' and ka != kb:", "        if False:"),
                 ("            if not nx and _value_category(x) != _value_category(y):", "            if False:")]
_MUT_NO_EXACT_AND_TYPES = _MUT_NO_EXACT_ONLY + _MUT_NO_TYPES
_MUT_NO_RO = [("        if real.exists() and not os.access(real, os.W_OK):", "        if False:")]


class TestMutationsAreCaught:
    def test_unmutated_module_passes_every_checker(self, tmp_path, monkeypatch):
        mod = _load_mutant([])
        n = 0
        for fn in (lambda d: _check_midwrite(mod, d, monkeypatch),
                   lambda d: _check_replace_fail(mod, d, monkeypatch),
                   lambda d: _check_tamper(mod, d, monkeypatch, 'drop_row'),
                   lambda d: _check_tamper(mod, d, monkeypatch, 'alter_value')):
            d = tmp_path / str(n)
            d.mkdir()
            assert fn(d) == []
            n += 1

    def test_m1_direct_to_parquet_is_caught_by_midwrite(self, tmp_path, monkeypatch):
        assert _check_midwrite(_load_mutant(_MUT_DIRECT), tmp_path, monkeypatch) != []

    def test_m2_no_finally_cleanup_is_caught_by_tmp_leftover(self, tmp_path, monkeypatch):
        assert _check_tamper(_load_mutant(_MUT_NO_FINALLY), tmp_path, monkeypatch, 'drop_row') != []

    def test_m3_no_verification_is_caught_by_tamper(self, tmp_path, monkeypatch):
        bad = _check_tamper(_load_mutant(_MUT_NO_VERIFY), tmp_path, monkeypatch, 'alter_value')
        assert bad != []

    @pytest.mark.parametrize('kind', ['rel_drift', 'zero_to_tiny', 'float32', 'round2'])
    def test_m5_no_check_exact_is_caught(self, tmp_path, monkeypatch, kind):
        """D1:拿掉 `check_exact=True`(並旁路型別層)→ 微小漂移類竄改必須被某一層抓到;
        這裡只拿掉 check_exact,確認漂移測試對「僅剩型別層」的版本仍轉紅的是數值層本身。"""
        mod = _load_mutant(_MUT_NO_EXACT_AND_TYPES)
        assert _check_tamper(mod, tmp_path, monkeypatch, kind) != []

    def test_m6_remove_only_check_exact_still_caught_by_value_layer(self, tmp_path, monkeypatch):
        """單獨拿掉 check_exact(其餘層都在):四種數值漂移都必須因此「漏網」→ 檢查器轉紅,
        證明 check_exact 本身是獨立有效的一層(預設 rtol=1e-5 / atol=1e-8 會放行它們)。"""
        mod = _load_mutant(_MUT_NO_EXACT_ONLY)
        for k in ('rel_drift', 'zero_to_tiny', 'float32', 'round2'):
            d = tmp_path / k
            d.mkdir()
            assert _check_tamper(mod, d, monkeypatch, k) != [], f'{k}:拿掉 check_exact 後仍被擋下'

    @pytest.mark.parametrize('kind', ['bool_to_int', 'int_to_float'])
    def test_m7_no_type_layer_is_caught(self, tmp_path, monkeypatch, kind):
        mod = _load_mutant(_MUT_NO_TYPES)
        assert _check_tamper(mod, tmp_path, monkeypatch, kind) != []

    def test_m8_readonly_check_removed_is_caught(self, tmp_path, monkeypatch):
        mod = _load_mutant(_MUT_NO_RO)
        led = tmp_path / 'signals.parquet'
        mod.append_signals([_row('2026-08-17')], led)
        real_access = os.access
        monkeypatch.setattr(os, 'access', lambda p, m, *a, **k:
                            False if (Path(p) == led and m == os.W_OK) else real_access(p, m, *a, **k))
        before = _snapshot(tmp_path)
        try:
            mod.append_signals([_row('2026-08-18')], led)
            replaced = True
        except mod.LedgerWriteError:
            replaced = False
        monkeypatch.undo()
        assert replaced and _snapshot(tmp_path) != before, '拿掉唯讀檢查後應靜默替換(守衛才有意義)'

    def test_m4_no_os_replace_is_caught_by_replace_failure(self, tmp_path, monkeypatch):
        assert _check_replace_fail(_load_mutant(_MUT_NO_REPLACE), tmp_path, monkeypatch) != []


# ═════════════════════════════════════════════════════════════════════
# D6 / Issue #1044 — 純量層(版本無關)的精確比較
#   QA 回報 pandas 2.0.x 對 object 浮點欄 `assert_frame_equal(check_exact=True)` 無效(1e-9 漂移漏網)。
#   以下所有案例都直接針對「df 端 object 欄」構造,並在另一組測試把 assert_frame_equal 整層
#   monkeypatch 成 no-op,證明純量層(+空值/型別層)單獨就能擋下全部漂移 —— 這就是版本無關的證據。
# ═════════════════════════════════════════════════════════════════════
import numpy as np  # noqa: E402

_X = 'x'


def _vr_run(mod, d: Path, mp, orig, back, rd: str, noop_afe: bool):
    """df 端 object 欄 `x`=[orig, orig],讀回端 `x`=[back, orig](dtype 由 rd 決定)。

    回傳 ('rejected'|'accepted', 違規清單):違規 = 拒絕時正式檔/目錄被動過。
    """
    led = d / 'signals.parquet'
    pd.DataFrame({MACRO_FWD_TEST_KEY: ['2026-08-16'], _X: [1.0]}).to_parquet(led, index=False)
    before = _snapshot(d)
    df = pd.DataFrame({MACRO_FWD_TEST_KEY: ['2026-08-17', '2026-08-18'],
                       _X: pd.Series([orig, orig], dtype=object)})
    real_read = pd.read_parquet

    def _read(path, *a, **k):
        out = real_read(path, *a, **k)
        if str(path).endswith('.tmp'):
            out = out.copy()
            second = float('nan') if (rd == 'f8' and orig is pd.NA) else orig   # pd.NA 不能進 float64 欄
            out[_X] = pd.Series([back, second], dtype='float64' if rd == 'f8' else object)
        return out
    mp.setattr(pd, 'read_parquet', _read)
    if noop_afe:
        mp.setattr('pandas.testing.assert_frame_equal', lambda *a, **k: None)
    bad: list[str] = []
    try:
        mod._atomic_write_parquet(df, led)
        outcome = 'accepted'
    except mod.LedgerWriteError:
        outcome = 'rejected'
        if _snapshot(d) != before:
            bad.append('拒絕時正式檔 sha256/mtime 或目錄被改動(含殘留 tmp)')
    mp.undo()
    return outcome, bad


# (id, 原值, 讀回值, 讀回端 dtype) —— 一律「必須拒絕」
_D6_REJECT = [
    ('1.0->1.000000001', 1.0, 1.000000001, 'f8'),
    ('0.0->1e-9', 0.0, 1e-9, 'f8'),
    ('42.0->42.000001', 42.0, 42.000001, 'f8'),
    ('round2', 1.23456789, float(round(1.23456789, 2)), 'f8'),
    ('nextafter_up', 1.1, float(np.nextafter(1.1, np.inf)), 'f8'),
    ('nextafter_down', 1.1, float(np.nextafter(1.1, -np.inf)), 'f8'),
    ('float32_truncation', 0.1, float(np.float32(0.1)), 'f8'),
    ('int->float', 3, 3.0, 'f8'),
    ('int_precision_2**53+1', 2 ** 53 + 1, 2 ** 53, 'obj'),
    ('bool->int', True, 1, 'obj'),
    ('bool->float', True, 1.0, 'f8'),
    ('str->number', '1', 1, 'obj'),
    ('number->str', 1.0, '1.0', 'obj'),
    ('nan_vs_zero', float('nan'), 0.0, 'f8'),
    ('zero_vs_nan', 0.0, float('nan'), 'f8'),
    ('none_vs_zero', None, 0.0, 'f8'),
    ('inf->-inf', float('inf'), float('-inf'), 'f8'),
    ('inf->big', float('inf'), 1e308, 'f8'),
    ('big->inf', 1e308, float('inf'), 'f8'),
    ('str_changed', 'abc', 'abd', 'obj'),
]
# 必須通過(良性白名單)
_D6_ACCEPT = [
    ('identical_float', 1.5, 1.5, 'f8'),
    ('np.float64_vs_float', np.float64(1.5), 1.5, 'f8'),
    ('float_vs_np.float64', 1.5, np.float64(1.5), 'obj'),
    ('np.bool_vs_bool', np.bool_(True), True, 'obj'),
    ('bool_vs_np.bool_', True, np.bool_(True), 'obj'),
    ('np.int64_vs_int', np.int64(3), 3, 'obj'),
    ('int_vs_np.int64', 3, np.int64(3), 'obj'),
    ('None_vs_NaN', None, float('nan'), 'f8'),
    ('NaN_vs_None', float('nan'), None, 'obj'),
    ('pd.NA_vs_NaN', pd.NA, float('nan'), 'f8'),
    ('NaN_vs_pd.NA', float('nan'), pd.NA, 'obj'),
    ('+inf_same', float('inf'), float('inf'), 'f8'),
    ('-inf_same', float('-inf'), float('-inf'), 'f8'),
    ('neg_zero_equals_zero', 0.0, -0.0, 'f8'),
    ('zero_equals_neg_zero', -0.0, 0.0, 'f8'),
    ('same_str', 'abc', 'abc', 'obj'),
    ('large_int_same', 2 ** 53 + 1, 2 ** 53 + 1, 'obj'),
]


class TestScalarLayerExactness:
    @pytest.mark.parametrize('cid,orig,back,rd', _D6_REJECT, ids=[c[0] for c in _D6_REJECT])
    def test_reject_with_pandas_layer_enabled(self, tmp_path, monkeypatch, cid, orig, back, rd):
        out, bad = _vr_run(store, tmp_path, monkeypatch, orig, back, rd, noop_afe=False)
        assert out == 'rejected' and bad == []

    @pytest.mark.parametrize('cid,orig,back,rd', _D6_REJECT, ids=[c[0] for c in _D6_REJECT])
    def test_reject_even_when_assert_frame_equal_is_noop(self, tmp_path, monkeypatch, cid, orig, back, rd):
        """版本無關的證據:pandas 的 assert_frame_equal 層整個失效(模擬 pandas 2.0.x),仍全數擋下。"""
        out, bad = _vr_run(store, tmp_path, monkeypatch, orig, back, rd, noop_afe=True)
        assert out == 'rejected' and bad == []

    @pytest.mark.parametrize('noop', [False, True])
    @pytest.mark.parametrize('cid,orig,back,rd', _D6_ACCEPT, ids=[c[0] for c in _D6_ACCEPT])
    def test_benign_equivalences_accepted(self, tmp_path, monkeypatch, cid, orig, back, rd, noop):
        out, bad = _vr_run(store, tmp_path, monkeypatch, orig, back, rd, noop_afe=noop)
        assert out == 'accepted', f'{cid} 被誤拒'

    def test_untampered_object_float_column_passes(self, tmp_path):
        """sanity:df 端 object 浮點欄、真實讀回端 float64、未竄改 → 通過(不誤殺)。"""
        led = tmp_path / 'signals.parquet'
        df = pd.DataFrame({MACRO_FWD_TEST_KEY: ['2026-08-17', '2026-08-18'],
                           _X: pd.Series([0.1 + 0.2, None], dtype=object)})
        store._atomic_write_parquet(df, led)
        assert led.is_file() and _tmp_leftovers(tmp_path) == []

    def test_scalar_helper_semantics(self):
        f = store._scalar_exactly_equal
        assert f(0.0, -0.0) and f(float('inf'), float('inf')) and not f(float('inf'), float('-inf'))
        assert not f(1.0, np.nextafter(1.0, 2.0)) and f(np.float64(2.5), 2.5)
        assert f(True, np.bool_(True)) and not f(True, False)
        assert f(np.int64(7), 7) and not f(2 ** 53 + 1, 2 ** 53)
        assert f('a', 'a') and not f('a', 'b')


_D6_MUT_NO_SCALAR = [("            if not nx and not _scalar_exactly_equal(x, y):", "            if False:")]
_D6_MUT_TOLERANCE = [("        return float(x) == float(y)",
                      "        return __import__('math').isclose(float(x), float(y), rel_tol=1e-6, abs_tol=1e-9)")]
_D6_MUT_NO_CATEGORY = [("            if not nx and _value_category(x) != _value_category(y):", "            if False:")]
_D6_MUT_NAN_CONFLICT = [("            nx, ny = _is_null(x), _is_null(y)", "            nx, ny = (x is None), (y is None)")]


def _slipped(mod, tmp_path, mp) -> set:
    out_ids = set()
    for n, (cid, orig, back, rd) in enumerate(_D6_REJECT):
        d = tmp_path / str(n)
        d.mkdir()
        out, _ = _vr_run(mod, d, mp, orig, back, rd, noop_afe=True)
        if out == 'accepted':
            out_ids.add(cid)
    return out_ids


class TestScalarLayerMutations:
    """D6 突變:拿掉/弱化純量層必須使上面的案例轉紅(此處的「紅」= 突變版沒擋下該擋的案例)。"""

    def test_m1_remove_scalar_layer_float_drifts_slip_through_noop_afe(self, tmp_path, monkeypatch):
        slipped = _slipped(_load_mutant(_D6_MUT_NO_SCALAR), tmp_path, monkeypatch)
        for must in ('1.0->1.000000001', '0.0->1e-9', 'nextafter_up', 'nextafter_down',
                     'float32_truncation', 'round2', 'int_precision_2**53+1', 'inf->big'):
            assert must in slipped, f'拿掉純量層後 {must} 沒有漏網(守衛沒有獨立價值)'

    def test_m2_tolerance_instead_of_equality_is_caught(self, tmp_path, monkeypatch):
        slipped = _slipped(_load_mutant(_D6_MUT_TOLERANCE), tmp_path, monkeypatch)
        assert {'1.0->1.000000001', '0.0->1e-9', 'nextafter_up', 'float32_truncation'} <= slipped

    def test_m3_remove_category_check_is_caught(self, tmp_path, monkeypatch):
        slipped = _slipped(_load_mutant(_D6_MUT_NO_CATEGORY), tmp_path, monkeypatch)
        assert {'bool->int', 'bool->float', 'int->float'} <= slipped

    def test_m4_nan_treated_as_conflict_breaks_none_nan_equivalence(self, tmp_path, monkeypatch):
        mod = _load_mutant(_D6_MUT_NAN_CONFLICT)
        wrongly_rejected = []
        cases = [c for c in _D6_ACCEPT if 'NaN' in c[0] or 'NA' in c[0]]
        for n, (cid, orig, back, rd) in enumerate(cases):
            d = tmp_path / str(n)
            d.mkdir()
            out, _ = _vr_run(mod, d, monkeypatch, orig, back, rd, noop_afe=False)
            if out == 'rejected':
                wrongly_rejected.append(cid)
        assert wrongly_rejected, '空值規則被弱化後,None↔NaN 正向案例應被誤拒(守衛才有意義)'
