"""src/services/valuation_service.py — 估值卡要的**原始輸入**（L3 Service）。

單一職責一句話：**把估值判斷需要的輸入從 L1 取回來，本身不做任何估值判斷。**

兩支函式回答兩個不同的問題，刻意放在同一支 service 是因為它們是同一件事的
兩個尺度（全市場 vs 單檔），而**不是**因為它們共用實作 —— 兩者走完全不同的
L1 fetcher，彼此沒有任何呼叫關係：

  · `get_pe_name_maps()`        全市場「代碼 → 本益比 / 名稱」對照表
                                （選股網的 `pe_low` 因子與結果表的「名稱」欄）
  · `get_stock_dividends(code)` 單檔個股近 5 年年現金股利（357 存股評價的輸入）

═══ 這一支為什麼存在 ═══════════════════════════════════════════════
兩個 SSOT 都住在 **L1**，而 IA v2 的頁 2 /頁 3 是 **L5**：

  · `src/data/stock/yield_pe_fetcher.fetch_pe_name_maps`
  · `src/data/stock/app_stock_fetchers.fetch_dividend_data`

`CLAUDE.md §8.2` 硬規則第 4 條禁止 L5 直呼 L1；而經另一個 L5 檔的 re-export
繞道（`app.py` 現行就是走 `src.ui.tabs.yield_screener` 的 re-export 拿 PE map）
**只是騙過靜態檢查、不改變性質**。頁 2 的前一組實作就是為此拒絕接線並把
理由寫進當時那個 `PE_UNWIRED_WHERE` 常數（**該常數已隨接線改名為
`PE_MISSING_WHERE` 並改寫內容** —— 未接線與「接了但這一輪沒資料」
是兩種不同的話）；本檔就是它指名要補的那一支。

⚠️ **這裡有一個既有的重複，本檔不解、據實登記**（`CLAUDE.md §-1`：不是本次
改動造成的，就登記不動；v3 §01-2 的「消除重複取數」要動到既有分頁，落在
§8.4 step 4 的範圍閘門外）：個股配息在 L1 有**兩份**取數實作 ——
  (a) `app_stock_fetchers.fetch_dividend_data`：FinMind（REST → SDK）→
      yfinance → TWSE 除權息，**四段嘗試 / 三個來源標籤**，回
      `(近5年均額, 逐年明細, 來源)`，**既有 🔬 個股分頁的 357 卡走的就是它**；
  (b) `dividend_fetcher.fetch_annual_dividends`（已有 L3 wrapper
      `yield_screener_service.get_annual_dividends`）：**只有 yfinance 一源**，
      回一個逐年 Series，沒有「近 5 年平均」與「有配息年數」。
本檔選 (a)，理由有二：**同源**（與既有 357 卡同一份數字，兩張卡不會打架）
與 **不重寫規則**（(b) 要在呼叫端自己算平均與年數 ＝ 第二把尺，§2.1）。
→ 也就是說：頁 3 原本寫的「全 repo 沒有任何 L3 介面回傳個股配息歷史」
**不精確** —— `get_annual_dividends` 是存在的，只是它給的東西餵不了 357。

═══ 分層 ═══════════════════════════════════════════════════════════
L3 → L1 是 `CLAUDE.md §8.2` 的正常方向（`holdings_service` /
`yield_screener_service` 皆為同型既成範式）。本檔**只呼叫 public 符號**，
零底線開頭的私有符號（V-PICKER-PRIV-1 的前車之鑑）。
L1 / L2 import **一律 late import**（函式體內）。

⚠️ **但 late import 買不到「本檔很輕」，據實更正**（實測 2026-09-07）：
`import src.services.valuation_service` 會拉進 **~90 個 `src.*` / `shared.*`
＋ pandas ＋ yfinance ＋ requests ＋ streamlit**，因為
`src/services/__init__.py` 是 **eager barrel**，任何 `src.services.*` 的
import 都會先跑它。這是 `src/services/` 的既有性質，本批不動（§-1）。
✅ 仍然有效的那一半：頁 2 / 頁 3（L5）對本檔是**函式體內** late import，
成本只在使用者真的送出之後才付 —— 實測 `import src.ui.views.page_find`
只帶進 6 個 `src.*`、**零 `src.services.*`**、零 pandas。

═══ §1 Fail Loud：哪一種「沒有」是哪一種 ═════════════════════════════
**本檔一律不吞例外。** 兩支函式都讓 L1 的例外原樣往上拋 —— 呼叫端要的是
一張紅卡，不是一個看起來很合理的空 dict（頁 2 / 頁 3 的 loader 各自
`try/except` 成 `repr(e)`）。

⚠️ **但「取不到」與「查得到、只是沒有」是兩件事，本檔用回傳值分開表達**：
  · `get_pe_name_maps()` 回**空 dict** ＝ 兩個市場都沒有給資料。
    ⚠️ **本檔看不出「只有一邊掛了」** —— L1 的 `fetch_pe_name_maps` 對
    上市/上櫃是各自 `try/except … continue` 的 fail-soft，半邊失敗時它
    回一份**只有另外半邊**的 map 且不留任何旗標。這是既有 L1 行為，
    本檔**不假裝知道**，也不去拆開兩支 fetcher 自己合併（那會複製
    `fetch_pe_name_maps` 的合併規則 ＝ 第二個 SSOT，§2.1）。
  · `get_stock_dividends()` 的 `avg_div_twd` 為 `None` ＝ **備援鏈跑完，
    沒有任何一段給出配息紀錄**，`source` 會是空字串。那**可能**是這一檔
    近 5 年真的沒有配息，也**可能**是每一段這一輪都沒拿到 —— L1 的回傳值
    分不出這兩者（它兩種情形都回 `avg_div=0.0`）。本檔**不猜**，把 `source`
    原樣帶上去，由呼叫端把兩種可能都講給使用者聽。
    **絕不回 `0.0`**：0 元股利是一個結論（「這檔不配息」），缺值不是。
"""
from __future__ import annotations

from dataclasses import dataclass


def get_pe_name_maps() -> tuple[dict, dict]:
    """全市場（上市 ＋ 上櫃）「代碼 → 本益比 / 名稱」對照表。

    Returns:
        `(pe_map, name_map)` —— 與 L1 SSOT `fetch_pe_name_maps()` **逐字同形**：
        `pe_map = {代碼: 本益比(float > 0)}`（本益比 ≤ 0 的不放 key ——
        那是缺值不是估值，L1 已擋）；`name_map = {代碼: 名稱}`。
        兩個都可能是空 dict（上市與上櫃都沒給資料）。

    Raises:
        Exception: L1 拋什麼就往上拋什麼（§1）。**注意 L1 本身是 fail-soft
            的**，實務上幾乎只會在 late import 失敗時走到這裡。

    ⚠️ **本檔是 pass-through，不做任何加工** —— `get_ranked_picks(pe_map=,
    name_map=)` 吃的就是這個形狀，中間多一層轉換只會製造第二種形狀。
    合併規則（上市先填、代碼空間互斥、不平均）住在 L1 那支的 docstring，
    本檔不複述、不改寫（§2.1）。
    """
    from src.data.stock.yield_pe_fetcher import fetch_pe_name_maps

    return fetch_pe_name_maps()


@dataclass(frozen=True)
class StockDividends:
    """單檔個股的配息歷史 —— **357 估值的兩個輸入，外加它們的來歷。**

    Attributes:
        avg_div_twd: 近 5 年**平均年現金股利（元／股）**。
            `None` ＝ 備援鏈跑完、沒有任何一段給出配息紀錄
            （**不寫 0**，見檔頭 §1 段）。
            ⚠️ 單位是**金額**，不是配發率、不是殖利率 —— 參數名的 `_twd`
            後綴即 `CLAUDE.md §4.1` 的量綱標記，餵給
            `calc_dividend_yield_357(avg_div_twd=)` 時對得上。
            （既有分頁踩過這個坑：舊碼把**殖利率**當配發率傳，函式內再除一次
            股價 ⇒ 2330 顯示 0.01%、真值 0.59%，並被判成「超貴」。）
        paying_years: 近 5 年**實際有配息的年數**（0~5）。
            `None` ＝ 未知（沒有逐年明細、或明細形狀不符）——
            下游會顯示「配息年數未知」而**不是** 0 年。
            算法走 L2 SSOT `v5_modules.count_dividend_paying_years()`，
            本檔**不自己數**（那支的 docstring 記著一個已修的事故：
            舊 caller 讀一個全站零寫入點的 session key ⇒ 年數恆為 0
            ⇒ 卡片永遠宣稱「連續配息 0 年」＝ 把「沒去查」講成「查到沒有」）。
        years: 逐年明細 `({'year': int, 'cash': float}, …)`，最多 5 筆。
            空 tuple ＝ 沒有任何一年的紀錄。
        source: 這一份數字是哪一段備援給的（L1 的來源標籤只有三種：
            `'FinMind'` / `'yfinance'` / `'TWSE'`）。**空字串 ＝ 每一段
            都沒有給** —— 呼叫端必須把「可能真的沒配息／可能每一段這一輪
            都沒拿到」兩種可能都講出來（§1）。
    """

    avg_div_twd: float | None = None
    paying_years: int | None = None
    years: tuple[dict, ...] = ()
    source: str = ""

    @property
    def has_record(self) -> bool:
        """有沒有拿到可以餵 357 的平均股利。**`None` 與 0 都算沒有。**"""
        return bool(self.avg_div_twd)


def get_stock_dividends(code: str) -> StockDividends:
    """單檔個股近 5 年配息 → 357 估值要的兩個輸入。

    路徑：L1 `app_stock_fetchers.fetch_dividend_data(sid)`
    （FinMind REST → FinMind SDK → yfinance → TWSE 除權息，四段嘗試）
    → L2 `v5_modules.count_dividend_paying_years(yearly)`。

    Args:
        code: 台股代碼。**不帶 `.TW` / `.TWO` 後綴** —— L1 那支吃的是純代碼，
            本檔只做 `strip()` ＋ `upper()`，**不補後綴、不補零**
            （正規化規則住在取數端，抄一份到這裡就是第二個 SSOT）。

    Returns:
        `StockDividends`。**備援鏈跑完、沒有任何一段給出紀錄，是一個有效
        結果**（`avg_div_twd=None` ＋ `source=""`），不是故障。

    Raises:
        Exception: L1 / L2 拋什麼就往上拋什麼（§1）。
            ⚠️ L1 那支對**每一段備援**都自己 `try/except` 並落 log，
            所以「某一段掛了」不會走到這裡 —— 走到這裡代表的是
            late import 失敗、或四段嘗試之外的東西壞了。

    ⚠️ **本檔不呼叫 `calc_dividend_yield_357`**：357 的位階判定需要**現價**，
    而現價是呼叫端從**另一支** L3（`dividend_station_service.fetch_metrics`）
    拿到的。把價格再繞回本檔只會讓「這個數字是哪一輪的」變得說不清楚。
    本檔的職責到「輸入」為止，判定由呼叫端餵 L2 純函式做（§8.1 step 1）。
    """
    from src.compute.strategy.v5_modules import count_dividend_paying_years
    from src.data.stock.app_stock_fetchers import fetch_dividend_data

    _sid = str(code or "").strip().upper()
    _avg, _yearly, _source = fetch_dividend_data(_sid)

    # §1：L1 用 `0.0` 當「什麼都沒找到」的哨兵值 —— 轉成 `None`。
    # 留著 0.0 會讓下游看到「平均股利 0 元」這個**結論**，而事實是「沒有數字」。
    try:
        _avg_f: float | None = float(_avg)
    except (TypeError, ValueError):
        _avg_f = None
    if _avg_f is not None and _avg_f <= 0:
        _avg_f = None

    _rows = tuple(_r for _r in (_yearly or ()) if isinstance(_r, dict))
    return StockDividends(
        avg_div_twd=_avg_f,
        # 逐年明細為空時 L2 回 `None`（未知），**不是** 0 —— 沿用它的契約。
        paying_years=count_dividend_paying_years(list(_rows)),
        years=_rows,
        source=str(_source or ""))
