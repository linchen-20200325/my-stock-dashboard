"""src/data/stock/ — TW 個股資料 fetcher。PEP 562 lazy forward,見 macro/__init__.py 註釋。"""
from . import tw_stock_data_fetcher  # noqa: F401

_SUBMODULES = (tw_stock_data_fetcher,)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.data.stock' has no attribute {name!r}")
