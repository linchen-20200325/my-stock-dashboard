"""src/services/ — L3 業務邏輯編排 / AI 整合 / 摘要。

PEP 562 lazy `__getattr__`(F-6.2 R4 教訓):每次 attr lookup 從 submod 即時取,
支援 caller 的 `from src.services import X` 對 monkeypatch.setattr(submod, X) 生效。
"""
from . import market_strategy, ai_engine, ai_structured_summary, daily_checklist  # noqa: F401

_SUBMODULES = (market_strategy, ai_engine, ai_structured_summary, daily_checklist)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.services' has no attribute {name!r}")
