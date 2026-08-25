"""src/compute/risk/ — 風控 / 短線雷達 / 法人 sanity / 對帳。PEP 562 `__getattr__` 即時轉發。"""
from . import risk_contribution, risk_control, risk_radar, inst_sanity, reconcile  # noqa: F401

_SUBMODULES = (risk_contribution, risk_control, risk_radar, inst_sanity, reconcile)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.compute.risk' has no attribute {name!r}")
