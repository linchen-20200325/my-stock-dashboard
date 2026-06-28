"""src/data/daily/ — 日間快照 fetcher。PEP 562 lazy forward,見 macro/__init__.py 註釋。"""
from . import daily_data_fetchers  # noqa: F401

_SUBMODULES = (daily_data_fetchers,)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.data.daily' has no attribute {name!r}")
