"""src/compute/strategy/ — v4 / v5 策略 / 組合。PEP 562 lazy forward。"""
from . import v4_strategy_engine, v5_modules  # noqa: F401

_SUBMODULES = (v4_strategy_engine, v5_modules)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.compute.strategy' has no attribute {name!r}")
