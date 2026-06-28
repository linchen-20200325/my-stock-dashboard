"""src/compute/scoring/ — 評分 / 出場訊號。PEP 562 lazy forward。"""
from . import scoring_engine, exit_signals  # noqa: F401

_SUBMODULES = (scoring_engine, exit_signals)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.compute.scoring' has no attribute {name!r}")
