"""src/ui/render/ — L4 圖表 / 通用 UI 元件 / macro snapshot。PEP 562 lazy forward。"""
from . import (  # noqa: F401
    chart_plotter, etf_render, ui_widgets, macro_ui_components, macro_snapshot,
)

_SUBMODULES = (
    chart_plotter, etf_render, ui_widgets, macro_ui_components, macro_snapshot,
)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.ui.render' has no attribute {name!r}")
