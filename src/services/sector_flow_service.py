"""src/services/sector_flow_service.py — 板塊資金潮汐編排(L3 service).

編排:L1 reader(讀本地快取三檔) + L1 gsheet(個股 watchlist) + L2 map_tickers_to_sectors
(持股 → 板塊)→ UI-ready view。§8.2 L3:合法組合 L1 fetcher/reader + L2 純函式
(對齊 `forward_test_service` / `fundamental_screener_service` pattern);L5 UI 只呼叫本層,
**不直呼** L1 reader / gsheet。

為什麼 gsheet 收集在 L3 而非 L5
--------------------------------
CLAUDE.md 硬規則:L5 UI 不得直呼 L1 fetcher。個股 watchlist 走 gsheet_portfolio(L1,
遠端 Google Sheet 抓取,非本地讀檔),故收集邏輯下沉本層;L5 只負責從 session_state 取
ETF 組合的 ticker + 個股 sheet_id 傳入(session_state 是 UI 專屬,只能在 L5 讀)。

§1 Fail Loud, Never Fake:reader 缺檔回 ok=False sentinel,本層原樣透傳(不偽造空圖、
不編板塊)。gsheet 未設定 / 未登入 / quota / 網路失敗 → graceful 跳過(該來源的持股
highlight 就少那部分,不炸全頁);未知代號 → 對映「未分類」且**不** highlight(避免亂標)。
"""
from __future__ import annotations


def _normalize_code(ticker) -> str:
    """持股 ticker → 對映 ticker_sector.json 的裸股號。

    §4.1:ETF 組合的 ticker 常帶 `.TW` / `.TWO` 後綴(如 `0050.TW`),但 industry_map /
    ticker_sector.json 的 key 是裸碼(`0050`)。去後綴才對得上,否則全落「未分類」。
    """
    s = str(ticker or "").strip().upper()
    for _suf in (".TWO", ".TW"):
        if s.endswith(_suf):
            return s[: -len(_suf)].strip()
    return s


def _collect_stock_watchlist_tickers(stock_sheet_id) -> list[str]:
    """讀個股 gsheet 所有 watchlist 的代號(graceful)。

    未提供 sheet_id / gsheet 未設定 / 未登入 / 抓取失敗 → 回 [](不炸),caller 端持股
    highlight 就少 gsheet 這部分。走 L1 gsheet_portfolio(late import,對齊
    forward_test_service:避 module load 拉整條 gsheet/OAuth 依賴鏈)。
    """
    if not stock_sheet_id:
        return []
    try:
        from src.data.portfolio import gsheet_portfolio as _gsp
        if not _gsp.is_configured():
            return []
        out: list[str] = []
        for _name in (_gsp.list_stock_watchlists(sheet_id=stock_sheet_id) or []):
            out.extend(_gsp.load_stock_watchlist(_name, sheet_id=stock_sheet_id) or [])
        return out
    except Exception as _e:  # noqa: BLE001 — gsheet 未登入/quota/網路 → 當無個股持股
        print(f"[sector_flow_service] 讀個股 watchlist 失敗(略過): "
              f"{type(_e).__name__}: {_e}")
        return []


def _active_selection_tickers() -> "tuple[list[str], dict]":
    """👤 我的 P1(DEC-083 Q7):持股標示來源 ＝ 使用者在「👤 我的」選定的組合 ＋ 觀察清單的代號。

    走 L3 `holdings_service.get_holdings()`(與 💼 我的持股 同一份選定;⛔ 不再讀整本全部觀察清單、
    也⛔ 不讀 L5 session 的 ETF 組合列)。回 `(代號, 來源說明)`;讀取例外**不上拋**(板塊圖本身照畫,
    只是少了持股標示)—— 但記在來源說明的 `error`(⛔ 不靜默,呼叫端要講出來)。
    """
    _src = {"portfolio_name": "", "watchlist_name": "", "portfolio_selection": "",
            "watchlist_selection": "", "bound": False, "active_state": "", "error": ""}
    try:
        from src.services.holdings_service import get_holdings
        _h = get_holdings(resolve_names=False)
    except Exception as _e:  # noqa: BLE001 — 持股標示是附加資訊,失敗不擋板塊圖,但要回報(§1)
        print(f"[sector_flow_service] 讀選定組合／觀察清單失敗(持股標示略過): {type(_e).__name__}: {_e}")
        _src["error"] = repr(_e)
        return [], _src
    _src.update(portfolio_name=_h.portfolio_name, watchlist_name=_h.watchlist_name,
                portfolio_selection=_h.portfolio_selection, watchlist_selection=_h.watchlist_selection,
                bound=bool(_h.bound), active_state=_h.active_state, error=_h.watchlist_error)
    return [str(_r.get("ticker") or "") for _r in _h.holdings], _src


def get_sector_flow_view(*, etf_tickers=None, stock_sheet_id=None,
                         include_stock_watchlists: bool = True,
                         strict: bool = False,
                         use_active_selection: bool = False) -> dict:
    """讀快取 + 疊加持股 → 板塊 highlight,回 UI-ready view。

    Args:
        etf_tickers: ETF 組合持股 ticker(由 L5 從 session_state['etf_portfolio_rows'] 取,
                     可能帶 .TW/.TWO 後綴)。
        stock_sheet_id: 個股組合 gsheet 的 sheet_id(由 L5 從 session_state 取);None → 跳過。
        include_stock_watchlists: 是否額外抓個股 gsheet watchlist(預設 True)。
        strict: 透傳 reader 的 `strict`(預設 False = 既有行為一字不變)。True →
                快取檔**存在但壞掉**時例外往上拋,不回「尚未產生」的 ok=False。
        use_active_selection: 👤 我的 P1(加性參數,預設 False ＝ 既有行為一字不變;舊 `tab_sector_flow` 照舊)。
                True(新版「🔍 找標的」)→ 忽略 `etf_tickers` / `stock_sheet_id` / `include_stock_watchlists`,
                持股標示改用「👤 我的」選定的組合 ＋ 觀察清單(見 `_active_selection_tickers`);
                view 另加 `'holding_source'`(來源說明 dict,含讀取錯誤)。

    Returns:
        reader.read_sector_flow_cache() 的 dict 疊加兩欄:
          'highlight_sectors': set[str]  # 使用者持股所在、且確實出現在泡泡圖的板塊(去「未分類」)
          'holding_sectors':   dict      # {裸股號: 板塊}(含未分類,供除錯/摘要)
        reader ok=False → 原樣透傳(附空 highlight_sectors / holding_sectors)。
    """
    from src.data.sector_flow.reader import read_sector_flow_cache
    from src.compute.sector_flow import map_tickers_to_sectors
    from shared.sector_flow_thresholds import SECTOR_UNCLASSIFIED, canonical_sector

    view = read_sector_flow_cache(strict=True) if strict else read_sector_flow_cache()
    if not view.get("ok"):
        view.setdefault("highlight_sectors", set())
        view.setdefault("holding_sectors", {})
        return view

    if use_active_selection:
        _tickers, view["holding_source"] = _active_selection_tickers()
    else:
        _tickers = list(etf_tickers or [])
        if include_stock_watchlists:
            _tickers += _collect_stock_watchlist_tickers(stock_sheet_id)
    _codes = [c for c in (_normalize_code(t) for t in _tickers) if c]

    _ticker_sector = view.get("ticker_sector") or {}
    _holding_map = map_tickers_to_sectors(_codes, _ticker_sector)

    # 持股板塊(canonical:ETF 家族細分標籤 上櫃ETF/… → "ETF"),去未分類。
    _holding_canon = {canonical_sector(s) for s in _holding_map.values()
                      if s != SECTOR_UNCLASSIFIED}
    # 只 highlight「確實出現在泡泡圖」的板塊;回傳泡泡的**原始 label**(canonical 後比對),
    # 讓 render 直接以原 sector 字串比對即可,免動 L4。ETF 標籤不一致由 canonical 消弭。
    _highlight = {str(s.get("sector")) for s in view.get("sectors", [])
                  if canonical_sector(str(s.get("sector"))) in _holding_canon}

    view["holding_sectors"] = _holding_map
    view["highlight_sectors"] = _highlight
    return view
