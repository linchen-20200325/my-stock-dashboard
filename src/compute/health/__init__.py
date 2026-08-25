"""src/compute/health/ — 健康度 / 財報體檢計算。PEP 562 `__getattr__` 即時轉發。

v19.174 去識別化：`mj_health_diff` / `mj_snapshot_io` / `mj_trend_score` 三檔
已改名為 `fin_health_diff` / `fin_snapshot_io` / `fin_trend_score`。
舊檔僅保留 deprecation re-export（待手動刪除），**不**登記於 `_SUBMODULES`，
避免同一批 public 名稱被解析兩次。舊 public 名（`diff_mj_health`
/ `compute_mj_trend_subscore`）在新模組內已保留同物件 alias，caller 不會斷。
"""
from . import fin_health_diff, fin_snapshot_io, fin_trend_score, health_reconcile  # noqa: F401

_SUBMODULES = (health_reconcile, fin_health_diff, fin_snapshot_io, fin_trend_score)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.compute.health' has no attribute {name!r}")
