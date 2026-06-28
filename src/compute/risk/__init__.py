"""src/compute/risk/ — 風控。PEP 562 lazy forward。"""
from . import risk_control  # noqa: F401

_SUBMODULES = (risk_control,)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.compute.risk' has no attribute {name!r}")
