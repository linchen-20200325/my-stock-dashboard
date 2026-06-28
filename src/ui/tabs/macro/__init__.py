"""src/ui/tabs/macro/ — tab_macro 拆分子目錄。

F-7.1a:抽 tab_macro.py top 8 個 helper 到 helpers.py 降 file LOC。
PEP 562 lazy forward,caller 用 `from src.ui.tabs.macro import X` 取。
"""
from . import helpers  # noqa: F401

_SUBMODULES = (helpers,)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.ui.tabs.macro' has no attribute {name!r}")
