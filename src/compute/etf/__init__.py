"""src/compute/etf/ — ETF 計算 / 品質 / helper / 分類 / 模擬 / 評分。PEP 562 lazy forward。"""
from . import (  # noqa: F401
    etf_calc, etf_quality, etf_helpers,
    etf_categories, etf_margin_simulator, etf_scoring_helpers,
    etf_smart_analysis, etf_recommendation,
)

_SUBMODULES = (
    etf_calc, etf_quality, etf_helpers,
    etf_categories, etf_margin_simulator, etf_scoring_helpers,
    etf_smart_analysis, etf_recommendation,
)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.compute.etf' has no attribute {name!r}")
