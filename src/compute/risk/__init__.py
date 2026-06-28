"""src/compute/risk/ — 風控 / 短線雷達 / 法人 sanity / 對帳。PEP 562 lazy forward。"""
from . import risk_control, risk_radar, inst_sanity, reconcile  # noqa: F401

_SUBMODULES = (risk_control, risk_radar, inst_sanity, reconcile)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.compute.risk' has no attribute {name!r}")
