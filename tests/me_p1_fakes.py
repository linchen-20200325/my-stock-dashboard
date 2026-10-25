"""👤 我的 P1（DEC-083 Q6／Q7）共用測試替身：讓「新版 Sheet SSOT」看到一本 active Sheet ＋ 使用者的明確選定。

不是測試檔（檔名不以 `test_` 開頭 ⇒ pytest 不收集）。

為什麼需要它：自 👤 我的 P1 起，新版 UI 的 L3（`holdings_service.get_holdings`、`get_binding_state(ssot=True)`）
只認「兩格綁定同一本」的 active Sheet，且只讀**使用者選定**的那一本組合 / 那一份觀察清單（⛔ 不再取名稱排序
第一本）。既有測試以 L1 `_get_active_sheet_id` / `_get_active_stock_sheet_id` 替身表達「已綁」、以「清單裡第一本」
表達「讀到的那一本」—— 那兩件事現在分別改由 `get_active_sheet()` 與 `get_active_selection()` 決定，故以本檔
**明確**表達（測試裡寫出「使用者選了哪一本」，而不是讓程式替使用者挑）。
"""
from __future__ import annotations


def bind_ssot(monkeypatch, sheet_id: str = "SID", *, portfolio: str = "", watchlist: str = "",
              watchlist_skip: bool = False) -> None:
    """L3 `portfolio_binding_service.get_active_sheet` → `ACTIVE_OK(sheet_id)`（`sheet_id` 空 → `ACTIVE_NONE`）；
    `get_active_selection` → 給定選定。"""
    from src.services import portfolio_binding_service as PB

    if not sheet_id:
        monkeypatch.setattr(PB, "get_active_sheet", lambda: PB.ActiveSheet(state=PB.ACTIVE_NONE))
        monkeypatch.setattr(PB, "get_active_selection", lambda sid=None: PB.ActiveSelection())
        return
    monkeypatch.setattr(PB, "get_active_sheet", lambda: PB.ActiveSheet(
        state=PB.ACTIVE_OK, sheet_id=sheet_id, portfolio_channel=sheet_id, stock_channel=sheet_id))
    monkeypatch.setattr(PB, "get_active_selection", lambda sid=None: PB.ActiveSelection(
        sheet_id=sheet_id, portfolio=portfolio, watchlist=watchlist, watchlist_skip=watchlist_skip))
