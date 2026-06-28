"""src/compute/macro/ — 總經 helper / 訊號 lookback / 驗證。PEP 562 lazy forward。"""
from . import macro_helpers, macro_signal_lookback_tw, macro_validation_tw  # noqa: F401

_SUBMODULES = (macro_helpers, macro_signal_lookback_tw, macro_validation_tw)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.compute.macro' has no attribute {name!r}")
