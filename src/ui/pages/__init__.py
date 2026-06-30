"""src/ui/pages/ — L5 獨立頁面(sidebar / diagnostics / calibration / health inspector)。PEP 562 lazy forward。

v18.400 D4:`oauth_state` 已從本目錄歸位至 `src/data/portfolio/oauth_state.py`(L1 同層)。
"""
from . import (  # noqa: F401
    sidebar_health, calibration_ui, api_diagnostic, data_coverage,
    data_registry_panel, reconcile_panel, health_inspector,
)

_SUBMODULES = (
    sidebar_health, calibration_ui, api_diagnostic, data_coverage,
    data_registry_panel, reconcile_panel, health_inspector,
)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.ui.pages' has no attribute {name!r}")
