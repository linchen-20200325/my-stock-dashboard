"""四頁 id／顯示名：只取 `shared.ia_nav4`（SSOT，Reuse Matrix L0-5 KEEP AS-IS），⛔ 複製第二份。"""
from __future__ import annotations

from shared.ia_nav4 import (  # noqa: F401  (re-export)
    P4_HOLD, P4_ME, P4_MARKET, P4_TARGET, PAGE4_LABELS,
)

#: 順序＝導覽順序（客戶 (5)-7：市場／標的／持股／我的；⛔ 第五頁）。
PAGE_IDS: tuple[str, ...] = tuple(PAGE4_LABELS)

#: Preview 場景（fake／scenario）。
SCENARIO_COLD = "cold"
SCENARIO_LOADED = "loaded"
SCENARIO_MISSING = "missing"
SCENARIO_STALE = "stale"
SCENARIO_UNAVAILABLE = "unavailable"
SCENARIO_NOT_EVALUATED = "not_evaluated"
SCENARIO_IDS: tuple[str, ...] = (
    SCENARIO_COLD, SCENARIO_LOADED, SCENARIO_MISSING,
    SCENARIO_STALE, SCENARIO_UNAVAILABLE, SCENARIO_NOT_EVALUATED,
)
