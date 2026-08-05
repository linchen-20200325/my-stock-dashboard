"""src/compute/strategy/ — v4/v5 策略 / 組合管理 / 回測 / 技術指標。PEP 562 lazy forward。

v19.174 去識別化：`caisen_targets` 已改名為 `pattern_targets`。舊檔僅保留
deprecation re-export（待手動刪除），**不**登記於 `_SUBMODULES`，避免同一批
public 名稱被解析兩次。舊 public 名（`compute_caisen_targets` 等）在新模組內
已保留同物件 alias，caller 不會斷。
"""
from . import (  # noqa: F401
    v4_strategy_engine, v5_modules,
    tw_backtest, portfolio_manager, tech_indicators,
    pattern_targets,
)

_SUBMODULES = (
    v4_strategy_engine, v5_modules,
    tw_backtest, portfolio_manager, tech_indicators,
    pattern_targets,
)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.compute.strategy' has no attribute {name!r}")
