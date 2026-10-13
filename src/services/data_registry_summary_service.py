"""L3 Service — 資料源清單（`session_state['data_registry']`）的唯讀彙總。批 Z54。

給「📖 憑什麼 › 資料體檢 › 🔧 進階診斷」的「資料源清單」卡用：那張卡原本標未接線，
它自己寫的補法是「在 `src/services/` 補一支回傳來源清單的唯讀 L3（把 `data_registry`
轉出來即可，不需要新的取數）」—— 本檔就是那一支。

**做什麼**：把呼叫端傳進來的 session mapping 裡的 `data_registry`
（寫入端：L3 `data_registry_scanner.scan_and_write_data_registry` ／
`macro_registry_patch`；新 UI 由「🚀 更新今日戰情」的「資料登錄中心掃描」那一步觸發）
**依 SSOT 分類分組**，回傳每組的筆數、缺漏筆數與最後更新。

**不做什麼**：⛔ 不取數、⛔ 不寫 session、⛔ 不 import streamlit（session 由呼叫端傳入）、
⛔ 不判新鮮度燈號（舊面板 `_freshness_emoji` 那把尺量的是混合語意的 `last_updated`，
見舊檔 docstring；本檔只原樣轉出最後更新字串，不下判斷）。

**分組規則與舊面板 `src/ui/pages/data_registry_panel.compute_registry_groups` 等價**
（缺 `category` 歸 `CAT_FALLBACK`、分組順序先 `ALL_CATEGORIES` 後依出現順序、空組不回傳）——
⚠️ 舊面板是**舊 UI 檔，不得修改、也不得由 L3 import**（L3 → L5 上行違憲），
故在此實作等價純函式，由 `tests/test_batch_z54.py` 對同一份輸入逐組對帳。
**唯一刻意的差異（§1）**：舊面板遇到「不是 dict 的一列」會 `continue` 靜默跳過；
本檔改成 `raise ValueError`（登錄表契約漂移要看得見，不是少一列）。

分層：L3 → L0（`shared.data_categories`）。無 L1 依賴。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from shared.data_categories import ALL_CATEGORIES, CAT_FALLBACK

#: session 裡登錄表的 key（寫入端 `data_registry_scanner` / `macro_registry_patch` 用的同一個字面；
#: `macro_refresh_service.WRITES_SESSION_KEYS[STEP_REGISTRY]` 也登記了它）。
SESSION_KEY: str = "data_registry"

#: 一列沒有可解析的最後更新日（寫入端對缺漏列寫的是 `'N/A'`）時，回傳的字面。
#: ⚠️ 沿用寫入端自己的字面，⛔ 不另造「無」「—」之類的說法。
NO_DATE: str = "N/A"


@dataclass(frozen=True)
class RegistryGroup:
    """一個 SSOT 分類底下的彙總。

    Attributes:
        category: 分類顯示名（`shared.data_categories` 的常數值，含 emoji）。
        count: 這一組有幾筆。
        missing: 其中幾筆被寫入端標 `missing=True`。
        latest: 這一組可解析（`YYYY-MM-DD` 開頭）的 `last_updated` 裡最新的那一個（取前 10 字元）；
            一筆都不可解析 → `NO_DATE`。
    """

    category: str
    count: int
    missing: int
    latest: str


@dataclass(frozen=True)
class RegistrySummary:
    """`summarize_data_registry()` 的回傳。

    Attributes:
        written: session 裡**有沒有** `data_registry` 這個 key（這個 session 有沒有人寫過它）。
        groups: 依分類分組的彙總（`written=False` 時為空）。
    """

    written: bool
    groups: tuple[RegistryGroup, ...] = ()

    @property
    def total(self) -> int:
        return sum(_g.count for _g in self.groups)


def _date_prefix(value: Any) -> str:
    """`last_updated` → `YYYY-MM-DD`（可解析時）或空字串。**不猜格式**：只認前 10 字元是 ISO 日期。"""
    import datetime as _dt

    _s = str(value or "")[:10]
    try:
        _dt.datetime.strptime(_s, "%Y-%m-%d")
    except ValueError:
        return ""
    return _s


def group_registry_entries(registry: Mapping[str, Any]) -> dict[str, list[tuple[str, Mapping[str, Any]]]]:
    """`{name: meta}` → `{category: [(name, meta), ...]}`。與舊面板 `compute_registry_groups` 同序同組。

    Raises:
        ValueError: 某一列不是 Mapping（§1：⛔ 不靜默跳過，見檔頭）。
    """
    _groups: dict[str, list[tuple[str, Mapping[str, Any]]]] = {c: [] for c in ALL_CATEGORIES}
    _groups.setdefault(CAT_FALLBACK, [])
    for _name, _meta in registry.items():
        if not isinstance(_meta, Mapping):
            raise ValueError(
                f"`{SESSION_KEY}` 的 {_name!r} 那一列不是 dict（實際 {type(_meta).__name__}）"
                " —— 登錄表的寫入端與讀取端契約漂開了")
        _cat = _meta.get("category") or CAT_FALLBACK
        _groups.setdefault(_cat, []).append((_name, _meta))
    return {_c: _rows for _c, _rows in _groups.items() if _rows}


def summarize_data_registry(session: Mapping[str, Any]) -> RegistrySummary:
    """讀 `session[SESSION_KEY]`，回分組彙總。**純讀不寫、零網路。**

    邊界：
      · key 不存在 → `RegistrySummary(written=False)`（這個 session 還沒有人寫過，**有效結果**）。
      · key 存在但不是 Mapping → `ValueError`。
      · key 存在、是空的 Mapping → `ValueError`：寫入端對固定清單**一律寫列**
        （抓不到的寫 `missing`），寫成空的代表寫入端壞了，⛔ 不把它講成「沒有資料源」。
      · 某一列不是 Mapping → `ValueError`（見 `group_registry_entries`）。
    """
    if SESSION_KEY not in session:
        return RegistrySummary(written=False)
    _reg = session[SESSION_KEY]
    if not isinstance(_reg, Mapping):
        raise ValueError(
            f"`session_state[{SESSION_KEY!r}]` 不是 dict（實際 {type(_reg).__name__}）")
    if not _reg:
        raise ValueError(
            f"`session_state[{SESSION_KEY!r}]` 已寫入但一筆都沒有 —— 寫入端對固定清單一律寫列"
            "（抓不到的寫 missing），空的代表寫入端出錯")
    _out: list[RegistryGroup] = []
    for _cat, _rows in group_registry_entries(_reg).items():
        _dates = [_d for _d in (_date_prefix(_m.get("last_updated")) for _n, _m in _rows) if _d]
        _out.append(RegistryGroup(
            category=str(_cat),
            count=len(_rows),
            missing=sum(1 for _n, _m in _rows if bool(_m.get("missing"))),
            latest=max(_dates) if _dates else NO_DATE))
    return RegistrySummary(written=True, groups=tuple(_out))
