"""src/compute/macro/ — 總經 helper / 訊號 lookback / 驗證 / 跨資產流動性。PEP 562 lazy forward。"""
from . import (  # noqa: F401
    macro_helpers, macro_signal_lookback_tw, macro_validation_tw, flow_engine,
)

_SUBMODULES = (
    macro_helpers, macro_signal_lookback_tw, macro_validation_tw, flow_engine,
)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.compute.macro' has no attribute {name!r}")
