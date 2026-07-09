"""src/compute/screener/ — 基本面 / 月營收 / 缺貨 等篩選器計算。PEP 562 lazy forward。"""
from . import fundamental_prescreen, fundamental_screener, shortage_screener  # noqa: F401

_SUBMODULES = (fundamental_screener, fundamental_prescreen, shortage_screener)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.compute.screener' has no attribute {name!r}")
