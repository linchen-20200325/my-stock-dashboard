"""src/ui/tabs/ — L5 主 Streamlit Tab。PEP 562 lazy forward。"""
from . import (  # noqa: F401
    tab_edu, tab_etf_margin_simulator, tab_helpers, tab_macro,
    tab_macro_validation, tab_mj_health_diff, tab_stock, tab_stock_grp,
    tab_stock_picker,
)

_SUBMODULES = (
    tab_edu, tab_etf_margin_simulator, tab_helpers, tab_macro,
    tab_macro_validation, tab_mj_health_diff, tab_stock, tab_stock_grp,
    tab_stock_picker,
)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.ui.tabs' has no attribute {name!r}")
