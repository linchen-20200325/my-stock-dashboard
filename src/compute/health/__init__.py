"""src/compute/health/ — 健康度 / 老師 體檢計算。PEP 562 lazy forward。"""
from . import health_reconcile, mj_health_diff, mj_snapshot_io, mj_trend_score  # noqa: F401

_SUBMODULES = (health_reconcile, mj_health_diff, mj_snapshot_io, mj_trend_score)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.compute.health' has no attribute {name!r}")
