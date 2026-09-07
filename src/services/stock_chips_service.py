"""src/services/stock_chips_service.py — 個股「近 20 日籌碼」（L3 Service）。

單一職責一句話：**把個股日線取回來、交給 L0 判讀，回一份攤平好的結果。**

═══ 這一支為什麼存在 ═══════════════════════════════════════════════
判讀那一半**早就有了**，而且是 L0 純函式（吃 df、免 I/O）：

    `shared.macro_compute.analyze_20d_chips_from_df(df) -> dict`

缺的是**餵給它的那份 df**。產出「日線 ＋ 三大法人」同一張表的是
L1 `StockDataLoader.get_combined_data()`（其 public 包裝為
`src/data/stock/app_stock_fetchers.fetch_price_data`）——
⚠️ 前一組寫的是「**唯一**產得出」，本檔**不沿用那個全稱句**：
它沒有被窮舉驗證過（`CLAUDE.md §-2` 規則 6）。**已查證的是**：既有
🔬 個股分頁的近 20 日籌碼走的就是這一支（`tab_stock.py` 從
`app_stock_fetchers` 取 `fetch_price_data`，其 `df` 直接餵
`analyze_20d_chips_from_df`），所以本檔與它**同源**。
而 IA v2 的頁 3 是
**L5** —— `CLAUDE.md §8.2` 硬規則第 4 條禁止 L5 直呼 L1，經其他 L5 檔
re-export 繞道只是騙過靜態檢查、不改性質。頁 3 的前一組實作就是為此拒絕
接線並把理由寫進 `CHIPS_WHERE`；本檔就是它指名要補的那一支。

⚠️ **前一組寫的那句 `where` 有一個事實錯誤，本檔據實更正**：它說要「回含
`主力合計` ＋ `volume` 的 df」。實測（2026-09-07，讀 `macro_compute.py` 原始碼）
`analyze_20d_chips_from_df` 檢查的是 **`外資` / `投信` / `volume` 三欄**，
**完全沒有用到 `主力合計`**（`主力合計` 是另一支 —— L2
`compute/risk/inst_sanity.flag_latest_inst_outlier_from_df` 的異常值徽章 ——
所吃的欄位，兩者被混為一談了）。本檔照**實際**的欄位需求寫。

═══ 為什麼判讀也在這一層做（而不是把 df 交出去）════════════════════
把 `DataFrame` 回給 L5，等於把「怎麼從 df 得到結論」這件事開放給每一個
呼叫端各做一次（第二把尺，§2.1）。本檔改成：**df 不出這一層**，
只出「L0 已經判好的結論 ＋ 它用了哪些原始數字」。
⚠️ 這是**編排**不是**判讀** —— 集中度 / 連續性 / 三種訊號字面全部由 L0
`analyze_20d_chips_from_df` 決定，本檔一個門檻都沒有、一個字面都不寫。

⚠️ **判讀窗長度（近 20 日）由 L0 自己決定**（它內部 `df.tail(20)`）。
本檔的 `days` 參數只決定**載入多長的日線**，不決定判讀窗 —— 兩者不同，
呼叫端把期間從 120 改成 500 **不會**改變籌碼結論。這一句必須講給使用者聽，
否則他會以為調期間就能看「近 60 日籌碼」。

═══ 分層 ═══════════════════════════════════════════════════════════
L3 → L1（`app_stock_fetchers`）與 L3 → L0（`shared.macro_compute`）都是
`CLAUDE.md §8.2` 的正常方向。本檔**只呼叫 public 符號**（零底線開頭的
跨層私有符號 —— V-PICKER-PRIV-1 的前車之鑑）；L1 / L0 import 一律
late import（函式體內）。

⚠️ **但 late import 買不到「本檔很輕」這件事，據實更正**（實測 2026-09-07）：
`import src.services.stock_chips_service` 實際會拉進 **~90 個 `src.*` /
`shared.*` 模組 ＋ pandas ＋ yfinance ＋ requests ＋ streamlit** ——
因為 `src/services/__init__.py` 是 **eager barrel**（module level 就 import
`market_strategy` / `daily_checklist` / `financial_health_engine` … 六支），
**任何** `src.services.*` 的 import 都會先跑它。這是 `src/services/` 的
既有性質，不是本檔造成的，本批也不動它（`CLAUDE.md §-1`）。

✅ **對呼叫端仍然有效的那一半**：頁 3（L5）對本檔是**函式體內** late import，
所以上面那筆成本只在**使用者真的按了載入之後**才付；
「打開這一頁」的故障半徑不含它（實測：`import src.ui.views.page_inspect`
只帶進 11 個 `src.*`，**零 `src.services.*`**、零 pandas）。
本檔內部再做一次 late import 的實益因此只剩「不在 barrel 之外再多拉東西」，
**不是**「本檔很輕」。

═══ §1 Fail Loud：三種「沒有籌碼結論」是三件不同的事 ═══════════════
本檔用**三個不同的欄位**表達，呼叫端才畫得出三種不同的狀態：

  1. `error` 有值 → **取數失敗**（L1 回了錯誤字串，或整段拋例外）。
     呼叫端該畫**紅**的。⚠️ 本檔**不吞**例外：`fetch_price_data` 拋什麼就
     往上拋什麼；只有它自己回傳的 `err` 字串會被裝進 `error`。
  2. `miss_reason` 有值 → **日線回來了，但判不出籌碼**（法人欄缺、法人欄
     全為 0、成交量為 0、筆數不足）。那是**資料缺漏**，呼叫端該畫**灰**的
     —— 沒有人壞掉（`CLAUDE.md §1.A` 第 4 點：把缺漏畫成故障是捏造）。
  3. 兩者皆空 → 有結論，`signal` / `concentration` / `continuity` 都有值。

**任何一種情形都不回 0。** 集中度 0% 是一個結論（「買賣超剛好抵銷」），
缺值不是；故缺值一律 `None`。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChipsReadout:
    """一檔個股近 20 日籌碼的判讀結果。**欄位與 L0 回傳的 dict 一一對應。**

    Attributes:
        signal: L0 給的訊號字面（例：`'🔥 大戶吸籌'` / `'🔴 大戶倒貨'` /
            `'🟡 籌碼發散'`）。**原樣透傳，本檔不改寫、不去圖示** ——
            「訊號頻道只准出中文」是**畫面**的鐵律，該由畫面自己處理
            （L3 不知道呼叫端有沒有那條規則）。
        concentration: 近 20 日法人淨買賣超 ÷ 成交量（%）。`None` = 判不出。
            ⚠️ 分子分母**同為「張」**（L1 已在 `_normalize_inst_pivot` 統一
            `/1000`），故這個比值是無量綱的 %，不是金額（`CLAUDE.md §4.1`）。
        continuity: 近 20 日裡「法人淨買超」的日數佔比（%）。`None` = 判不出。
        days: L0 實際用了幾個交易日（**通常是 20，資料不足時會更少**）。
        pos_days: 其中淨買超的日數。
        total_net_k: 期間法人淨買賣超合計（**千張**，L0 已 `/1e3`）。
        total_vol_k: 期間成交量合計（**千張**，同上）。
        name: L1 回的中文名（查無 → 空字串，**不拿代號頂替**）。
        rows: 這一輪抓到幾列日線。`None` = 讀不出來。
        miss_reason: L0 說「判不出來」的原因原文（`'df缺法人/量欄'` /
            `'df法人欄全為0'` / `'成交量為0'` / `'df資料不足'` …）。
            空字串 = 判得出來。**這不是故障**（見檔頭 §1 段第 2 點）。
        error: 取數失敗的訊息。空字串 = 沒有失敗。
    """

    signal: str = ""
    concentration: float | None = None
    continuity: float | None = None
    days: int | None = None
    pos_days: int | None = None
    total_net_k: float | None = None
    total_vol_k: float | None = None
    name: str = ""
    rows: int | None = None
    miss_reason: str = ""
    error: str = ""

    @property
    def has_verdict(self) -> bool:
        """L0 判出結論了沒有。**只看訊號** —— 缺原因或取數失敗都算沒有。"""
        return bool(self.signal) and not self.miss_reason and not self.error


def _num(value) -> float | None:
    """任何東西 → float，或 `None`。**不猜 0**（0 是結論，不是缺值）。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value) -> int | None:
    """任何東西 → int，或 `None`。**不猜 0**（同上）。"""
    _f = _num(value)
    return None if _f is None else int(_f)


def get_chips_readout(code: str, *, days: int) -> ChipsReadout:
    """一檔個股的近 20 日籌碼判讀。

    路徑：L1 `app_stock_fetchers.fetch_price_data(sid, days)`
    → L0 `shared.macro_compute.analyze_20d_chips_from_df(df)`。

    Args:
        code: 台股代碼。**不帶 `.TW` / `.TWO` 後綴**（L1 那支吃純代碼；
            補後綴的規則住在取數端，抄一份到這裡就是第二個 SSOT）。
        days: 要載入幾個交易日的日線。**keyword-only 且沒有預設值**是刻意的
            —— 這個數字是呼叫端的畫面參數（使用者選的期間），本層不替它
            決定一個「看起來合理」的值。⚠️ **它不是判讀窗**：近 20 日那個
            窗長度由 L0 自己決定（見檔頭）。

    Returns:
        `ChipsReadout`。三種結果各自可辨（有結論 / 判不出 / 取數失敗），
        見檔頭 §1 段。

    Raises:
        Exception: L1 / L0 拋什麼就往上拋什麼（§1，**不吞**）。
            ⚠️ L1 那支對「暫時性失敗」是回 `err` **字串**而不是拋例外
            （它刻意這麼做，讓失敗不進 `st.cache_data`）——
            那條路會落進 `error` 欄，不會走到這裡。
    """
    from shared.macro_compute import analyze_20d_chips_from_df
    from src.data.stock.app_stock_fetchers import fetch_price_data

    _sid = str(code or "").strip().upper()
    _df, _name, _err = fetch_price_data(_sid, int(days))
    if _err or _df is None:
        # L1 已經說了它為什麼失敗 —— 原樣帶上去，本檔不改寫（§2.1）。
        # `_df is None` 而 `_err` 為空是理論上的契約漂移，也一併當失敗處理，
        # **不**退化成「查得到但沒有籌碼」（那會把故障說成缺漏）。
        return ChipsReadout(name=str(_name or ""),
                            error=str(_err or "").strip()
                            or "L1 沒有回傳日線，也沒有說原因（回傳契約漂移）")

    _rows = None
    try:
        _rows = int(len(_df))
    except (TypeError, ValueError):     # 形狀不對就是 unknown，不猜 0
        _rows = None

    _chip = analyze_20d_chips_from_df(_df)
    _chip = _chip if isinstance(_chip, dict) else {}
    _miss = str(_chip.get("error") or "")
    if _miss:
        # 判不出來 ≠ 壞掉。訊號字面（`'⚫ 資料不足'`）照樣帶回去，
        # 讓呼叫端在灰態裡也能顯示 L0 自己的說法。
        return ChipsReadout(signal=str(_chip.get("signal") or ""),
                            name=str(_name or ""), rows=_rows,
                            miss_reason=_miss)

    return ChipsReadout(
        signal=str(_chip.get("signal") or ""),
        concentration=_num(_chip.get("concentration")),
        continuity=_num(_chip.get("continuity")),
        days=_int(_chip.get("days")),
        pos_days=_int(_chip.get("pos_days")),
        total_net_k=_num(_chip.get("total_net_k")),
        total_vol_k=_num(_chip.get("total_vol_k")),
        name=str(_name or ""), rows=_rows)
