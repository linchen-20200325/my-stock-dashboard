"""src/compute/scoring/ — 評分 / 出場訊號 / 閾值優化 / 多因子。PEP 562 lazy forward。"""
from . import (  # noqa: F401
    scoring_engine, exit_signals,
    scoring_helpers, unified_verdict,
)

_SUBMODULES = (
    scoring_engine, exit_signals,
    scoring_helpers, unified_verdict,
)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.compute.scoring' has no attribute {name!r}")
