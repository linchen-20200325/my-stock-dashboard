"""📊「接入狀態」證據截圖用的 streamlit 入口（僅供 `wired_status_shots.py` 使用；⛔ 不是產品入口、不是測試）。

啟動前把 `src.ui2.shell.app.read_real_snapshot` 換成「先照常讀真 feed，再依 `UI2_WIRED_CASE` 覆寫幾個欄位」的版本，
再執行 `app_ui2.py`。**覆寫的是 snapshot 欄位（過期天數、上游狀態、是否缺值…），不是畫面**；畫面仍由真 shell／真 VM／真 view 產生。
`live`＝完全不覆寫（沙箱本機 git 追蹤快取的真 Real 現況）。`degraded`＝讀取整體 raise（同 `degraded_launcher.py`）。

環境變數：`UI2_WIRED_CASE`（見 `CASES`）、`UI2_REPO_ROOT`（要啟動的 checkout 根；預設為本檔所在 repo。用來對 base worktree
跑同一組態，量「沒有該區塊」的對照）。檔名不以 `test_` 開頭、不在 `measure_viewport.source_files()` 內，不影響 DEC-137 `source_hash`。
"""
import dataclasses
import os
import runpy
import sys

_ROOT = os.environ.get("UI2_REPO_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

import src.ui2.shell.app as _shell  # noqa: E402
from shared import regime_arbiter as RA  # noqa: E402
from src.services.ui2.real_canonical import RegimeFact  # noqa: E402

CASES = ("live", "loaded", "stale", "missing", "no_new_data", "undetermined",
         "unavailable", "fetch_failed", "legacy_upstream_error", "degraded")


def _both(s, **kw):
    """台股卡與日 K 兩個事實同步覆寫同名欄位（日 K 與卡片須同一份快照，否則日 K 會誠實顯示『不同步』而干擾本次量測）。"""
    t = dataclasses.replace(s.twii, **kw)
    k = dataclasses.replace(s.kbar, **kw) if s.kbar is not None else None
    return dataclasses.replace(s, twii=t, kbar=k)


def _apply(case: str, s):
    if case == "live":
        return s
    if case == "loaded":
        s = _both(s, is_stale=False, age_days=0)
        return dataclasses.replace(s, regime=RegimeFact("bull", "🟢", RA.SOURCE_BULL_SCORE, True))
    if case == "stale":
        return _both(s, is_stale=True, age_days=5)
    if case == "missing":
        return dataclasses.replace(s, twii=dataclasses.replace(s.twii, ok=False, close=(), as_of=None, is_stale=None, age_days=None))
    if case == "no_new_data":
        return _both(s, upstream_state="NO_NEW_DATA")
    if case == "undetermined":
        return _both(s, upstream_state="UNDETERMINED")
    if case == "unavailable":
        return dataclasses.replace(s, twii=None, twii_error="OSError")
    if case == "fetch_failed":
        return _both(s, upstream_state="FETCH_FAILED", has_upstream_error=True)
    if case == "legacy_upstream_error":
        return dataclasses.replace(s, twii=dataclasses.replace(s.twii, has_upstream_error=True))
    raise SystemExit(f"unknown UI2_WIRED_CASE {case!r}")


_case = os.environ.get("UI2_WIRED_CASE", "live")
_orig = _shell.read_real_snapshot


def _read():
    if _case == "degraded":
        raise RuntimeError("secret-token")
    return _apply(_case, _orig())


_shell.read_real_snapshot = _read
runpy.run_path(os.path.join(_ROOT, "app_ui2.py"), run_name="__main__")
