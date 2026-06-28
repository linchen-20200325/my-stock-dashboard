"""src/ui/pages/ — L5 獨立頁面(sidebar / diagnostics / calibration)。PEP 562 lazy forward。"""
from . import sidebar_health, calibration_ui, api_diagnostic, data_coverage  # noqa: F401

_SUBMODULES = (sidebar_health, calibration_ui, api_diagnostic, data_coverage)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.ui.pages' has no attribute {name!r}")
