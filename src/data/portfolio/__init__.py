"""src/data/portfolio/ — 持股組合資料 fetcher。PEP 562 lazy forward,見 macro/__init__.py 註釋。"""
from . import gsheet_portfolio  # noqa: F401

_SUBMODULES = (gsheet_portfolio,)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.data.portfolio' has no attribute {name!r}")
