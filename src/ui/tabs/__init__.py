"""src/ui/tabs/ — L5 主 Streamlit Tab + 其他渲染元件。PEP 562 `__getattr__` 即時轉發。

v18.406 U4 Phase 2:新增 `stock_sections/` 子目錄,收 tab_stock.py 拆檔後的
section render 函式(類比 `macro/` 子目錄模式)。

「即時轉發」= attribute lookup 即時,**不是**延遲載入 —— 下面 `from . import (...)`
是立即執行的。細節與 WONTFIX 理由見 `src/data/macro/__init__.py` 檔頭。
⚠️ 本 barrel 是 `src/ui/tabs/` 全樹的 eager 進入點,且經 `tab_stock.py` 連鎖
   拉進整個 `src/ui/pages/`。測試若要裝 streamlit stub,**務必在裝之前**
   先 import 目標(見 tests/test_zz_streamlit_pollution_lock.py 第四層守衛)。
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
