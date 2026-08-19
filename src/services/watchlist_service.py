"""L3 Service — 選股網 → 觀察清單「加入」編排（#33 選股池閉環）。

app.py 選股網(L6)不直呼 L1 gsheet（會踩 §8.2 L6↛L1 + private symbol）,改走本 service：
解析「當前個股清單 Sheet」+ 讀既有清單名 + 併入選股結果。L3→L1(gsheet_portfolio)合法。

§1：Sheet 未選 / 讀取失敗 → 回空 or raise 誠實訊息,不靜默借別的 sheet、不捏造。
"""
from __future__ import annotations


def get_watchlist_add_context() -> tuple[str, list[str]]:
    """回 (個股清單 sheet_id, 現有觀察清單名稱清單)。

    無 stock sheet（未在組合管理選定）→ ('', [])。讀清單失敗 → (sid, [])（§1 不炸畫面）。
    """
    from src.data.portfolio import gsheet_portfolio as _gsp
    try:
        _sid = _gsp._get_active_stock_sheet_id()
    except Exception as _e:  # noqa: BLE001 — accessor 理應回 '' 不 raise,真炸也降級
        print(f"[watchlist_service] stock sheet id 讀取失敗: {type(_e).__name__}: {_e}")
        return "", []
    if not _sid:
        return "", []
    try:
        _names = _gsp.list_stock_watchlists(sheet_id=_sid) or []
    except Exception as _e:  # noqa: BLE001
        print(f"[watchlist_service] 觀察清單名稱讀取失敗: {type(_e).__name__}: {_e}")
        _names = []
    return _sid, _names


def add_picks_to_watchlist(name: str, tickers: list[str]) -> int:
    """把 tickers 併入指定觀察清單（用當前 active 個股清單 Sheet）。回合併後總檔數。

    §1：無 stock sheet → raise（caller 顯示錯誤,不假裝成功）。合併去重由 L1
    `add_to_stock_watchlist` 負責（讀現有 → 聯集 → 存,不覆蓋）。
    """
    from src.data.portfolio import gsheet_portfolio as _gsp
    _sid = _gsp._get_active_stock_sheet_id()
    if not _sid:
        raise RuntimeError("尚未選定個股清單 Sheet —— 請先到 📁 組合管理設定。")
    return _gsp.add_to_stock_watchlist(name, tickers, sheet_id=_sid)
