"""src/data/macro/ — 總經資料 fetcher。

PEP 562 lazy `__getattr__`：每次 `from src.data.macro import X` lookup 時
從 submodule 即時取 attribute,使 `monkeypatch.setattr(submod, 'X', mock)`
能對 caller 的 deferred / lazy import 生效（避免 re-export snapshot trap）。
"""
from . import macro_core, tw_macro, leading_indicators, macro_alert  # noqa: F401

_SUBMODULES = (macro_core, tw_macro, leading_indicators, macro_alert)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.data.macro' has no attribute {name!r}")
