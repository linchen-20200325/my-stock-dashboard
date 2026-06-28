"""src/data/proxy/ — 代理層(Squid / 直連 / NAS / yfinance)。

PEP 562 lazy forward,見 macro/__init__.py 註釋。
nas_server.py 故意不 re-export:它是 FastAPI server entry,不該被當 lib import。
"""
from . import proxy_helper, yf_proxy  # noqa: F401

_SUBMODULES = (proxy_helper, yf_proxy)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.data.proxy' has no attribute {name!r}")
