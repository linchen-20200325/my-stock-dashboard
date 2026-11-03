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

#: 🎯 標的頁雙模式（Freeze §3／§16.2；⛔ 同時完整展開）。
MODE_CURATED = "curated"     # 市場精選
MODE_LOOKUP = "lookup"       # 即時查一檔
MODE_IDS: tuple[str, ...] = (MODE_CURATED, MODE_LOOKUP)
MODE_LABELS: dict[str, str] = {MODE_CURATED: "市場精選", MODE_LOOKUP: "即時查一檔"}

#: 👤 我的頁帳戶狀態（FAKE 連線事實；非資料語意）。
ACCOUNT_SIGNED_OUT = "signed_out"
ACCOUNT_SIGNED_IN = "signed_in"
ACCOUNT_UNAVAILABLE = "unavailable"
ACCOUNT_IDS: tuple[str, ...] = (ACCOUNT_SIGNED_IN, ACCOUNT_SIGNED_OUT, ACCOUNT_UNAVAILABLE)
