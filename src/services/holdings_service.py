"""src/services/holdings_service.py — 「你持有哪幾檔」的**唯讀** L3 介面（L3 Service）。

═══ 這一支為什麼存在 ═══════════════════════════════════════════════
在本檔之前，`src/services/` 底下**沒有任何一支**回傳「你持有哪幾檔、各幾張、
均價多少」（AUD-5 稽核組窮舉 `src/services/` 全部 public 函式後證實）。
唯一產得出那份 list 的是 L5 私有函式
`src/ui/etf/etf_tab_dividend_station._load_holdings_from_portfolio()` ——
住在一個 UI 檔裡、名字底線開頭、而且會直接 `st.caption` / `st.warning`。
別的畫面要用它只有兩條路：跨檔取用底線開頭的私有符號（`CLAUDE.md §8.2.A.2`
**V-PICKER-PRIV-1** 登記的那種違憲），或再抄一份（第二套取數實作，v3 §01-2 明文禁止）。
**本檔就是第三條路：把那份清單抽成一支住在 L3 的公開唯讀介面。**

⚠️ **既有的 L5 私有版本本批一個字都沒有動。** 它仍是既有 🏦 ETF ›存股戰情室
分頁在用的實作。本檔**不是**它的替換品，兩者暫時並存 —— 併檔屬 v3 §01-2 的
「消除重複取數」，但那要動既有分頁，落在 `CLAUDE.md §-1`（沒有 user 指派
／沒有 bug 觸發就不動）與 §8.4 step 4 的範圍閘門，**不在本批**。
（誠實揭露，不是漏做：見本檔「已知差異」。）

═══ 這個檔**一律唯讀** ═════════════════════════════════════════════
本檔只呼叫 L1 `gsheet_portfolio` 的**讀取面**：
`list_portfolios` / `load_portfolio` / `list_stock_watchlists` / `load_stock_watchlist`。
**不呼叫**任何 `save_*` / `delete_*` / `create_*` / `rename_*` / `add_to_*`，
也**不呼叫** `clear_read_cache()`（那會清掉別的頁正在用的讀取快取 —— 雖然不寫
Google，卻是對別人可見的副作用）。
守衛：`tests/test_p04_hold_view.py::TestHoldingsServiceIsReadOnly`。

═══ 分層 ═══════════════════════════════════════════════════════════
L3 → L1（`gsheet_portfolio`）是 §8.2 的正常方向。
⚠️ 本檔取「個股清單 Sheet id」時呼叫 L1 的**私有** accessor
`_get_active_stock_sheet_id()`。這**不是** V-PICKER-PRIV-1：
  · V-PICKER-PRIV-1 登記的違憲是 **L5 → L1 私有**（實例 `tab_stock_picker.py`），
    它同時踩到「L5 不得直呼 L1」與「EX-PASSTHRU-1 不涵蓋 private symbol」兩條；
  · 本檔是 **L3 → L1**，那條硬規則不適用，且 repo 內已有兩處同型既成範式：
    `src/services/watchlist_service.py`（`_get_active_stock_sheet_id`）與
    `src/services/portfolio_binding_service.py`（`_get_active_sheet_id`）。
  · 「投資組合 Sheet」那一側**連私有 accessor 都不碰** —— 走 L3 public
    `portfolio_binding_service.get_binding_state().sheet_id`（見下一段）。
**這是判定，不是全稱句**：本檔沒有查證過「repo 內只有那兩處」。

═══ 為什麼一定要**顯式**把 `sheet_id` 傳下去（踩過的坑）═══════════════
L1 的四支讀取函式都是 `@st.cache_data(ttl=TTL_15MIN)`，而 `sheet_id` 是**參數**
＝ 快取鍵的一部分。傳 `None` 時鍵**恆為空**、真正的 sheet 在函式內部才解析 ——
於是**換一本 Sheet 之後 15 分鐘內會拿到上一本的資料**（張冠李戴）。
`portfolio_binding_service.get_binding_state()` 的註解已把這個坑寫明白
（「§ P3a 稽核 #3」）。本檔照辦：**每一次呼叫都顯式帶 `sheet_id=`。**

═══ §1 Fail Loud：哪一半炸了、要不要往上拋 ═══════════════════════════
**投資組合（你真正持有的部位）讀取失敗 → `raise`。** 不 best-effort、不回半份。
理由不是潔癖：80/20 配置偏離、未實現損益、停利判定的**分母都是整份清單**，
少一半算出來的百分比看起來完全正常、實際上是錯的 —— 那正是 §1「錯誤的數字比
沒有數字更危險」。呼叫端要的是一張紅卡，不是一個看起來很合理的假比例。

**觀察清單（你還沒買的候選）讀取失敗 → 不 raise，記在 `watchlist_error`。**
它不進任何金額計算（`held=False`），只影響「換入優先從你的觀察清單挑」這一項；
為了它把整個戰情室變紅，就是把「一格壞」放大成「整頁壞」。
⚠️ **但它不可以被靜默吞掉** —— 呼叫端拿得到 `watchlist_error`，必須顯示。

**沒有綁 Sheet ≠ 失敗。** 回 `bound=False` ＋ 空清單，由呼叫端畫成灰的
「你還沒綁」（`CLAUDE.md §1.A` 第 4 點：把「還沒做」畫成紅色錯誤是捏造故障）。

═══ 已知差異（與 L5 既有版本逐項對照，誠實列出）═════════════════════
1. **本檔會去重**：同一檔同時出現在 Portfolio（held）與 Watchlist（觀察）時，
   **只留 held 那一列**。既有 L5 版本會產出兩列。去重的理由是下游：
   `get_switch_in_candidates(exclude=…)` 與 `build_switch_advice` 的
   「換入優先觀察清單綠燈」若看到你已持有的那一檔，就會**叫你買你已經有的東西**。
   比對用 L0 `T.normalize_ticker()`（去 `.TW` / `.TWO` 再比），否則
   `2330` 與 `2330.TW` 會被當兩檔。
2. **本檔不呼叫任何 `st.*`**：既有 L5 版本用 `st.caption` / `st.warning` 報告
   每一半的結果；那是 UI 行為，L3 不該有。本檔改成「把事實放進回傳值」，
   由呼叫端決定怎麼講（`portfolio_name` / `more_portfolios` / `watchlist_error` …）。
3. **本檔對投資組合那半 fail loud**（上一段），既有 L5 版本是 best-effort。

⚠️ 上面三點是**本檔與那一支的差異**，不是「repo 內只有這兩份」的全稱句。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HoldingsResult:
    """一次唯讀讀取的結果。**空清單是有效結果，不是故障。**

    Attributes:
        holdings: `[{'ticker','name','held','asset_kind','asset_class',
            'lots','avg_price'}, …]`。欄位與既有 L5 版本**逐欄同構**（下游
            `dividend_station_service` 的一整排函式吃的就是這個形狀）。
            ⚠️ `lots` / `avg_price` 對**觀察清單**那些列一律是 `None` ——
            `stock_watchlist` 分頁的 schema 只有 `name` / `ticker` / `updated_at`
            三欄，**根本沒有張數與均價**。填 0 會讓 80/20 與停利把它算成
            「持有 0 張、成本 0 元」（§1 不猜、不填 0）。
        bound: 有沒有綁到「投資組合」那本 Sheet（＝ 有沒有可讀的來源）。
            `False` ＋ 空清單 = 你還沒綁，**這是有效結果**。
        logged_in: Google 有沒有登入（由 L3 `get_binding_state()` 帶下來）。
        portfolio_name: 實際讀的那一本組合名。空 = 沒讀到任何一本。
        watchlist_name: 實際讀的那一份觀察清單名。
        more_portfolios: 那本 Sheet 裡還有**別本**組合沒有被讀（本檔只取第一本，
            與既有 L5 版本同行為）。呼叫端必須講出來，否則使用者會以為
            畫面上就是他的全部部位。
        more_watchlists: 同上，觀察清單那一側。
        watchlist_error: 觀察清單那半讀取失敗的 `repr(e)`；空字串 = 沒有失敗。
            **不得被呼叫端吞掉**（§1）。
    """

    holdings: tuple[dict, ...] = ()
    bound: bool = False
    logged_in: bool = False
    portfolio_name: str = ""
    watchlist_name: str = ""
    more_portfolios: bool = False
    more_watchlists: bool = False
    watchlist_error: str = ""

    @property
    def held(self) -> tuple[dict, ...]:
        """真正**持有**的那些列（`held=True`）。觀察清單不算持有。"""
        return tuple(_h for _h in self.holdings if _h.get("held"))

    @property
    def held_tickers(self) -> tuple[str, ...]:
        """已持有代號（原樣，未去後綴）—— 給 `get_switch_in_candidates(exclude=…)`。

        ⚠️ 這裡**刻意不做正規化**：L3 `get_switch_in_candidates()` 自己會用
        `T.normalize_ticker()` 把 exclude 與候選兩邊都正規化後再比對
        （它的註解把「後綴盲 → 已持有卻被推換入」這個 bug 寫得很清楚）。
        在這裡先去一次後綴，等於把同一個規則寫成兩份（§2.1 SSOT）。
        """
        return tuple(str(_h.get("ticker") or "") for _h in self.held)


def _row(ticker: str, *, held: bool, lots=None, avg_price=None) -> dict:
    """組一列。種類／類別**由代號規則判**，與「它躺在哪一份清單裡」脫鉤。

    這一條沿用既有 L5 版本的行為（user 2026-08 裁示）：一檔 ETF 就算被放進
    觀察清單，它仍然是 ETF，不會因為換一個分頁就變成個股。
    核心／衛星以「ETF ↔ 個股」近似（郭俊宏：核心＝配息 ETF、衛星＝成長股）——
    **這是近似，主題型 ETF 會被算成核心**，下游 UI 已在卡面註記此限制。
    """
    from shared import dividend_station_thresholds as T   # L3 → L0（正常方向）

    _kind = T.classify_asset_kind(ticker)
    return {
        "ticker": ticker,
        "name": "",
        "held": held,
        "asset_kind": _kind,
        "asset_class": (T.ASSET_CORE if _kind == T.KIND_ETF else T.ASSET_SATELLITE),
        "lots": lots,
        "avg_price": avg_price,
    }


def get_holdings() -> HoldingsResult:
    """讀出目前的持股清單（投資組合 ＋ 觀察清單）。**純讀不寫。**

    Returns:
        `HoldingsResult`。沒有綁 Sheet → `bound=False` ＋ 空清單（**有效結果**）。

    Raises:
        Exception: **投資組合那半**讀取失敗時原樣往上拋（§1 Fail Loud）——
            半份清單算出來的 80/20 與損益看起來正常、實際是錯的。
            觀察清單那半失敗**不會**走到這裡，改記在 `watchlist_error`。

    ⚠️ 一次呼叫最多打 Google 四次（列組合名 / 讀組合 / 列清單名 / 讀清單），
    四支在 L1 都是 `@st.cache_data(ttl=TTL_15MIN)`，且本檔**顯式帶 `sheet_id=`**
    讓快取鍵隨 Sheet 變動（見檔頭「為什麼一定要顯式傳 sheet_id」）。
    """
    from src.data.portfolio import gsheet_portfolio as _gsp    # L3 → L1（正常方向）
    from src.services.portfolio_binding_service import (       # L3 → L3
        STATUS_UNBOUND,
        get_binding_state,
    )

    _state = get_binding_state()
    _sid = str(getattr(_state, "sheet_id", "") or "")
    _bound = bool(_sid) and str(getattr(_state, "status", "")) != STATUS_UNBOUND
    _logged = bool(getattr(_state, "logged_in", False))

    _out: list[dict] = []
    _pf_name = ""
    _more_pf = False
    if _bound:
        # ⚠️ 這一段**不包 try/except**：投資組合讀取失敗要往上拋（§1，見 docstring）。
        _names = _gsp.list_portfolios(sheet_id=_sid) or []
        if _names:
            _pf_name, _more_pf = _names[0], len(_names) > 1
            for _rec in (_gsp.load_portfolio(_pf_name, sheet_id=_sid) or []):
                _tk = str(_rec.get("ticker", "") or "").strip().upper()
                if not _tk:
                    continue
                # `parse_portfolio_records` 已保證 lots>0 / avg_price>0 才進來；
                # 這裡原樣搬運，**不補值、不四捨五入**（§1 不加工使用者的成本）。
                _out.append(_row(_tk, held=True, lots=_rec.get("lots"),
                                 avg_price=_rec.get("avg_price")))

    # ── 觀察清單（held=False）。失敗不擋持股本身，但**記下來**、不靜默吞 ──────
    _wl_name = ""
    _more_wl = False
    _wl_err = ""
    try:
        # L3 → L1 私有 accessor：**不是** V-PICKER-PRIV-1（那條管 L5→L1），
        # 沿用 `watchlist_service` / `portfolio_binding_service` 既成範式。見檔頭。
        _stk_sid = str(_gsp._get_active_stock_sheet_id() or "")
        if _stk_sid:
            _wnames = _gsp.list_stock_watchlists(sheet_id=_stk_sid) or []
            if _wnames:
                _wl_name, _more_wl = _wnames[0], len(_wnames) > 1
                _seen = {_norm(_h["ticker"]) for _h in _out}
                for _tk in (_gsp.load_stock_watchlist(_wl_name,
                                                      sheet_id=_stk_sid) or []):
                    _tk = str(_tk or "").strip().upper()
                    # 去重：已持有的那一檔不再當「觀察候選」——否則換股建議會
                    # 叫你買你已經有的東西（見檔頭「已知差異」第 1 點）。
                    if not _tk or _norm(_tk) in _seen:
                        continue
                    _seen.add(_norm(_tk))
                    # 觀察清單 schema 只有三欄 → 張數／均價**誠實留 None**，不填 0。
                    _out.append(_row(_tk, held=False, lots=None, avg_price=None))
    except Exception as _e:  # noqa: BLE001 — 觀察清單失敗不擋持股，但要回報（§1）
        _wl_err = repr(_e)
        print(f"[holdings_service] 觀察清單讀取失敗（持股本身不受影響）：{_wl_err}")

    # 中文名 best-effort（§1 抓不到留空不捏造）。失敗不擋整份清單。
    try:
        from src.services.dividend_station_service import resolve_holding_names
        resolve_holding_names(_out)
    except Exception as _e:  # noqa: BLE001 — 名稱只是顯示用，抓不到留空
        print(f"[holdings_service] 名稱解析略過：{type(_e).__name__}: {_e}")

    return HoldingsResult(
        holdings=tuple(_out), bound=_bound, logged_in=_logged,
        portfolio_name=_pf_name, watchlist_name=_wl_name,
        more_portfolios=_more_pf, more_watchlists=_more_wl,
        watchlist_error=_wl_err)


def _norm(ticker: str) -> str:
    """去重比對用的正規化 —— 走 L0 SSOT，本檔不自己 strip 後綴。"""
    from shared import dividend_station_thresholds as T

    return T.normalize_ticker(ticker)
