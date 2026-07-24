"""src/compute/strategy/ — v4/v5 策略 / 組合管理 / 回測 / 技術指標。PEP 562 lazy forward。"""
from . import (  # noqa: F401
    v4_strategy_engine, v5_modules,
    tw_backtest, portfolio_manager, tech_indicators,
    caisen_targets,
)

_SUBMODULES = (
    v4_strategy_engine, v5_modules,
    tw_backtest, portfolio_manager, tech_indicators,
    caisen_targets,
)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.compute.strategy' has no attribute {name!r}")
