"""src/data/etf/ — ETF 資料 fetcher。PEP 562 lazy forward,見 macro/__init__.py 註釋。"""
from . import etf_fetch  # noqa: F401

_SUBMODULES = (etf_fetch,)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.data.etf' has no attribute {name!r}")
