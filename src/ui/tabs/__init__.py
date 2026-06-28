"""src/ui/tabs/ — L5 主 Streamlit Tab + 其他渲染元件。PEP 562 lazy forward。"""
from . import (  # noqa: F401
    tab_edu, tab_etf_margin_simulator, tab_helpers, tab_macro,
    tab_macro_validation, tab_mj_health_diff, tab_stock, tab_stock_grp,
    tab_stock_picker,
    # F-8 補搬:L5 渲染元件(非單一 tab,但同層性質)
    chip_radar, grape_ladder, hot_money, macro_classroom, macro_stock_link,
    monthly_revenue_screener, portfolio_linkage, yield_screener,
)

_SUBMODULES = (
    tab_edu, tab_etf_margin_simulator, tab_helpers, tab_macro,
    tab_macro_validation, tab_mj_health_diff, tab_stock, tab_stock_grp,
    tab_stock_picker,
    chip_radar, grape_ladder, hot_money, macro_classroom, macro_stock_link,
    monthly_revenue_screener, portfolio_linkage, yield_screener,
)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.ui.tabs' has no attribute {name!r}")
