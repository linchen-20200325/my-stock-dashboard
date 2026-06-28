"""src/ui/etf/ — L5 ETF dashboard + 子 Tab。PEP 562 lazy forward。"""
from . import (  # noqa: F401
    etf_dashboard, etf_tab_ai, etf_tab_grp_compare, etf_tab_portfolio,
    etf_tab_single,
)

_SUBMODULES = (
    etf_dashboard, etf_tab_ai, etf_tab_grp_compare, etf_tab_portfolio,
    etf_tab_single,
)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.ui.etf' has no attribute {name!r}")
