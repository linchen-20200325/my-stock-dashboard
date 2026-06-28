"""src/ui/render/ — L4 圖表 / 通用 UI 元件。PEP 562 lazy forward。"""
from . import chart_plotter, etf_render, ui_widgets, macro_ui_components  # noqa: F401

_SUBMODULES = (chart_plotter, etf_render, ui_widgets, macro_ui_components)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.ui.render' has no attribute {name!r}")
