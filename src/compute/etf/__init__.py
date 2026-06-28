"""src/compute/etf/ — ETF 計算 / 品質 / helper。PEP 562 lazy forward。"""
from . import etf_calc, etf_quality, etf_helpers  # noqa: F401

_SUBMODULES = (etf_calc, etf_quality, etf_helpers)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.compute.etf' has no attribute {name!r}")
