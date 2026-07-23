"""src/ui/tabs/ — L5 主 Streamlit Tab + 其他渲染元件。PEP 562 lazy forward。

v18.406 U4 Phase 2:新增 `stock_sections/` 子目錄,收 tab_stock.py 拆檔後的
section render 函式(類比 `macro/` 子目錄模式)。
"""
from . import (  # noqa: F401
    tab_edu, tab_helpers, tab_macro,
    tab_stock, tab_stock_grp,
    tab_stock_picker,
    # F-8 補搬:L5 渲染元件(非單一 tab,但同層性質)
    chip_radar, grape_ladder, hot_money, macro_classroom, macro_stock_link,
    portfolio_linkage, yield_screener,
    # U4 Phase 2:tab_stock 子目錄
    stock_sections,
)
# v18.464: tab_etf_margin_simulator 從 UI 移除；v19.159 團隊稽核真刪整功能棧
# (UI + etf_margin_simulator L2 engine + fetch_etf_close_history + 測試),見 docs/ARCHIVED_FEATURES.md

_SUBMODULES = (
    tab_edu, tab_helpers, tab_macro,
    tab_stock, tab_stock_grp,
    tab_stock_picker,
    chip_radar, grape_ladder, hot_money, macro_classroom, macro_stock_link,
    portfolio_linkage, yield_screener,
    stock_sections,
)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.ui.tabs' has no attribute {name!r}")
