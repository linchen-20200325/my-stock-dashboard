"""src/data/core/ — 核心資料 fetcher。PEP 562 lazy forward,見 macro/__init__.py 註釋。"""
from . import data_loader, data_registry  # noqa: F401

_SUBMODULES = (data_loader, data_registry)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.data.core' has no attribute {name!r}")
