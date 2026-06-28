"""src/ui/pages/ — L5 獨立頁面(sidebar / diagnostics / calibration / OAuth)。PEP 562 lazy forward。"""
from . import (  # noqa: F401
    sidebar_health, calibration_ui, api_diagnostic, data_coverage, oauth_state,
)

_SUBMODULES = (
    sidebar_health, calibration_ui, api_diagnostic, data_coverage, oauth_state,
)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.ui.pages' has no attribute {name!r}")
