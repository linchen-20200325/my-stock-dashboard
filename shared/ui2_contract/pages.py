"""UI2 頁 id／顯示名。

前四頁 id／顯示名只取 `shared.ia_nav4`（SSOT，Reuse Matrix L0-5 KEEP AS-IS），⛔ 複製第二份。
第五頁 `🗂 資料`（DEC-146）是 **UI2 自有登錄**：⛔ 修改／擴充 `shared/ia_nav4`（舊 UI 共用，固定四頁）。
"""
from __future__ import annotations

from shared.ia_nav4 import (  # noqa: F401  (re-export)
    P4_HOLD, P4_ME, P4_MARKET, P4_TARGET, PAGE4_LABELS,
)

#: 第五頁（DEC-146 客戶核准：📊市場 → 🎯標的 → 💼持股 → 👤我的 → 🗂資料；頂部導覽）。UI2 自有，非 `ia_nav4`。
P4_DATA = "p4_data"

#: UI2 五頁 id → 顯示名（前四項取自 `ia_nav4.PAGE4_LABELS` 原值；順序＝導覽順序）。
PAGE_LABELS: dict[str, str] = {**PAGE4_LABELS, P4_DATA: "🗂 資料"}

#: 順序＝導覽順序。
PAGE_IDS: tuple[str, ...] = tuple(PAGE_LABELS)

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

#: Real-data Preview（NUI2-REAL-FEED A2）的 `PageVM.scenario_id`。⛔ 加入 `SCENARIO_IDS`：FAKE 場景軸與
#: 真資料 feed 軸是兩條軸，不混（FAKE 六場景照舊當 regression）。
SCENARIO_REAL = "real"

#: Preview 資料來源（feed）切換：預設 FAKE（既有行為不變）；Real＝唯讀 real-data shadow（非 production default）。
FEED_FAKE = "fake"
FEED_REAL = "real"
FEED_IDS: tuple[str, ...] = (FEED_FAKE, FEED_REAL)

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
