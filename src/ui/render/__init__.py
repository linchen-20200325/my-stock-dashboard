"""src/ui/render/ — L4 圖表 / 通用 UI 元件。PEP 562 lazy forward。

P1-2 v18.373:macro_snapshot.py 搬至 src/data/macro/macro_snapshot.py(L1)
— 原檔含 yfinance.download HTTP I/O,符合 L1 fetcher 定位。
"""
from . import (  # noqa: F401
    chart_plotter, etf_render, ui_widgets, macro_ui_components, tab_sections,
)

_SUBMODULES = (
    chart_plotter, etf_render, ui_widgets, macro_ui_components, tab_sections,
)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.ui.render' has no attribute {name!r}")
