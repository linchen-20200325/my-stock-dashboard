"""src/ui/pages/ — L5 獨立頁面(sidebar / diagnostics / calibration / OAuth / health inspector)。PEP 562 lazy forward。"""
from . import (  # noqa: F401
    sidebar_health, calibration_ui, api_diagnostic, data_coverage,
    data_registry_panel, oauth_state, health_inspector,
)

_SUBMODULES = (
    sidebar_health, calibration_ui, api_diagnostic, data_coverage,
    data_registry_panel, oauth_state, health_inspector,
)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.ui.pages' has no attribute {name!r}")
