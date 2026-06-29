"""src/services/ — L3 業務邏輯編排 / AI 整合 / 摘要 / 狀態鎖 / section input / MJ 體檢。

PEP 562 lazy `__getattr__`(F-6.2 R4 教訓):每次 attr lookup 從 submod 即時取,
支援 caller 的 `from src.services import X` 對 monkeypatch.setattr(submod, X) 生效。
"""
from . import (  # noqa: F401
    market_strategy, ai_structured_summary, daily_checklist,
    macro_state_locker, section_inputs, financial_health_engine,
)

_SUBMODULES = (
    market_strategy, ai_structured_summary, daily_checklist,
    macro_state_locker, section_inputs, financial_health_engine,
)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.services' has no attribute {name!r}")
