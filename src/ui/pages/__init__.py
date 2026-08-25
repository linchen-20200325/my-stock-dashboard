"""src/ui/pages/ — L5 獨立頁面(sidebar / diagnostics / calibration / health inspector)。PEP 562 `__getattr__` 即時轉發。

v18.400 D4:`oauth_state` 已從本目錄歸位至 `src/data/portfolio/oauth_state.py`(L1 同層)。

「即時轉發」= attribute lookup 即時,**不是**延遲載入 —— 下面 `from . import (...)`
是立即執行的。細節與 WONTFIX 理由見 `src/data/macro/__init__.py` 檔頭。
⚠️ 本目錄**不是** Streamlit multipage 的 `pages/`(那要求與進入點同層,
   而進入點 app.py 在 repo root、root 無 pages/)。這裡就是普通 package。
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
