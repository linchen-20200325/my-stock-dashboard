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

═══ 異常值徽章（2026-09-07 FE-28 接線）═══════════════════════════════
線框對「籌碼」這一格寫的是「近 20 日主力買賣超與集中度，**含異常值徽章**」。
徽章走的是 **L2** `compute.risk.inst_sanity.flag_latest_inst_outlier_from_df`
（最新一日 `主力合計` vs 均量窗，門檻 SSOT 在 L0
`shared.signal_thresholds.INST_NET_OUTLIER_VOLUME_RATIO`）。

**它為什麼算在這一層**：徽章與判讀吃的是**同一份 df**，在這裡算等於零額外
取數；交給 L5 算則要把 `DataFrame` 交出這一層（第二把尺），而且 L5 直接
import L2 會讓每個呼叫端各自維護一份門檻讀法。**本檔一個門檻數字都不寫**，
`threshold` 讓 L2 用它自己的預設（＝同一個 L0 常數），只把它**讀回來報給畫面**。

⚠️ **徽章與近 20 日判讀是兩支獨立的函式、吃兩組不同的欄位**，
因此**分別判、分別報**：
  · 判讀吃 `外資` / `投信` / `volume`（L0 `analyze_20d_chips_from_df`）；
  · 徽章吃 `主力合計` / `volume`，且要求均量窗內**每一天都有量**。
所以「判讀出得來、徽章判不出來」是**正常且會發生**的組合（期間 120 天、
但這一檔上市不足均量窗長度時就是）。把兩者綁在一起報，等於拿一支的結果
替另一支背書。

⚠️ **三態，不是布林**（`OUTLIER_ANOMALY` / `OUTLIER_NORMAL` /
`OUTLIER_UNKNOWN`）。少了 `UNKNOWN` 這一格，畫面只剩「顯示徽章」與
「不顯示」兩種選擇，而**不顯示會被讀成「沒有異常」** —— 那正是
`CLAUDE.md §1` 的失效模式（既有 🔬 個股分頁
`ui/tabs/stock_sections/section_chips_20d.py` 的 `if _inst_flag.is_outlier`
就是這個寫法：判不出來與沒異常在畫面上長得一模一樣）。

⚠️ **`reason='inst_net_zero'` 一律歸 `UNKNOWN`，不歸 `NORMAL`**（刻意）：
L1 `src/data/core/data_loader.py` 的 `fill_cols` 對 `主力合計` 做了
`fillna(0)`，所以「最新一日 0」**分不出**「真的沒有法人買賣超」與「那一天的
法人資料還沒到」（TWSE 盤後 ~14:30 才給，日線先到是常態）。分不出來就不判
—— 這與 L0 `analyze_20d_chips_from_df` 把「法人欄全為 0」判成
`'df法人欄全為0'`（缺漏）是**同一個判準**，不是本檔自創的第二套。
`ratio` 在這一格一併清成 `None`：L2 對 `inst_net == 0` 會回 `ratio=0.0`，
把那個 0 報出去等於說「量到了，是 0 倍」。
"""
from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass

#: 異常值徽章的三種結果。**「判不出來」與「判過了沒有異常」是兩件事**（§1）。
#: 空字串（欄位預設值）是第四種：**這一輪根本沒跑到**（連 df 都沒拿到）。
OUTLIER_ANOMALY: str = "anomaly"
OUTLIER_NORMAL: str = "normal"
OUTLIER_UNKNOWN: str = "unknown"


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
        outlier_verdict: 異常值徽章的三態（`OUTLIER_ANOMALY` / `OUTLIER_NORMAL`
            / `OUTLIER_UNKNOWN`）。**空字串 = 這一輪沒跑到**（連 df 都沒拿到，
            必然伴隨 `error`）。⚠️ `UNKNOWN`（判不出來）與 `NORMAL`
            （判過了、沒有超過門檻）**是兩件事**，呼叫端不得混為一談。
        outlier_ratio: `|最新一日主力合計| ÷ 均量窗均量`（倍）。
            **`UNKNOWN` 時一律 `None`**（見檔頭：L2 對 `inst_net == 0`
            會回 `0.0`，報出去等於說「量到了，是 0 倍」）。
        outlier_threshold: 判定門檻（倍）。**讀自 L0 SSOT
            `shared.signal_thresholds.INST_NET_OUTLIER_VOLUME_RATIO`**
            —— 本檔與呼叫端都不得自己寫這個數字（§3.3）。
        outlier_window: 均量窗長度（交易日）。**讀自 L2 那支的簽章預設值**，
            同樣不在本檔寫死；讀不到 → `None`（畫面就不報數字，不猜一個）。
        outlier_reason: L2 給的原因原文（`'ok'` / `'outlier'` /
            `'vol_unavailable'` / `'inst_net_zero'`）。**原樣透傳**（§2.1）。
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
    outlier_verdict: str = ""
    outlier_ratio: float | None = None
    outlier_threshold: float | None = None
    outlier_window: int | None = None
    outlier_reason: str = ""

    @property
    def has_verdict(self) -> bool:
        """L0 判出結論了沒有。**只看訊號** —— 缺原因或取數失敗都算沒有。

        ⚠️ **不看徽章**：徽章是另一支函式、另一組欄位（見檔頭），
        把它算進來會讓「判讀出得來、徽章判不出來」這個正常組合被判成無結論。
        """
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


def _outlier_window() -> int | None:
    """L2 那支用幾日均量 —— **從它的簽章預設值讀回來，本檔不寫這個數字**。

    §3.3 反捏造：畫面要對使用者講「N 日均量」，那個 N 必須是**上游真的用的
    那一個**。在這裡（或在畫面上）抄一個 `30`，就是第二把尺 —— 上游改窗長度
    時它不會跟著動，而且沒有任何測試會紅。

    讀不到（簽章改了、參數改名）→ 回 `None`，畫面就**不報數字**。
    **不 fallback 到一個猜的值**（§1：寧可少講一句，不可講錯）。
    """
    from src.compute.risk.inst_sanity import flag_latest_inst_outlier_from_df

    try:
        _p = inspect.signature(flag_latest_inst_outlier_from_df).parameters
        return _int(_p["window"].default)
    except (KeyError, TypeError, ValueError) as _e:
        # §5 可觀測性：**不靜默**。回 `None` 是誠實的缺值（畫面會說「讀不到」），
        # 但「上游簽章改了」這件事本身要留跡，否則沒有人會發現那一列變模糊了。
        print(f"[stock_chips_service] 讀不到 L2 的均量窗長度 → 不報數字："
              f"{type(_e).__name__}: {_e}", file=sys.stderr)
        return None


def _outlier_fields(df) -> dict:
    """最新一日主力買賣超 vs 均量的異常值判定 → 攤平成 `ChipsReadout` 的欄位。

    **判定全部由 L2 `inst_sanity` 做**（門檻來自 L0 SSOT）；本函式只做兩件事：
    把 L2 的 `(is_outlier, ratio, reason)` 翻成三態，以及把門檻與窗長度**讀回來**
    給畫面顯示。**一個門檻數字都不寫**（§3.3）。

    ⚠️ **不傳 `threshold_ratio` / `window`**：讓 L2 用它自己的預設，那個預設就是
    L0 常數。傳一份進去等於在本層多一個可以漂移的入口。

    ⚠️ **不吞例外**（§1）：L2 那支自陳 fail-soft（`df` 為 None / 空 / 缺欄都回
    `vol_unavailable` 而不拋），所以這裡沒有 `try`。它若真的拋了，就是它破壞了
    自己的契約 —— 那要**看得見**（一路往上到呼叫端的紅態），不是被翻成
    「判不出來」的灰態藏起來。
    """
    from shared.signal_thresholds import INST_NET_OUTLIER_VOLUME_RATIO
    from src.compute.risk.inst_sanity import flag_latest_inst_outlier_from_df

    _res = flag_latest_inst_outlier_from_df(df)
    _reason = str(getattr(_res, "reason", "") or "")
    _ratio = _num(getattr(_res, "ratio", None))

    if bool(getattr(_res, "is_outlier", False)):
        _verdict = OUTLIER_ANOMALY
    elif _reason == "ok":
        _verdict = OUTLIER_NORMAL
    else:
        # `vol_unavailable`（缺欄／均量窗不足／df 空）與 `inst_net_zero`
        # （最新一日為 0 或 NaN —— 上游 fillna(0) 之後這兩者分不出來，見檔頭）
        # 都是**判不出來**。ratio 一併清掉，見檔頭最後一段。
        _verdict, _ratio = OUTLIER_UNKNOWN, None

    return {
        "outlier_verdict": _verdict,
        "outlier_ratio": _ratio,
        "outlier_threshold": _num(INST_NET_OUTLIER_VOLUME_RATIO),
        "outlier_window": _outlier_window(),
        "outlier_reason": _reason,
    }


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
        見檔頭 §1 段。異常值徽章的三態（`outlier_*` 那組欄位）**獨立於上面
        三種**：只要 df 回得來就一定會判一次，判讀本身判不判得出來都一樣。
        取數失敗那條路 `outlier_verdict` 留空（沒有 df 可判）。

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

    # ⚠️ 徽章**在判讀之前算，而且不受判讀結果影響**：兩支吃的欄位不同
    # （見檔頭），「判讀判不出來、徽章判得出來」與其反面都是正常組合。
    # 綁在一起算 = 拿一支的結果替另一支背書。
    _badge = _outlier_fields(_df)

    _chip = analyze_20d_chips_from_df(_df)
    _chip = _chip if isinstance(_chip, dict) else {}
    _miss = str(_chip.get("error") or "")
    if _miss:
        # 判不出來 ≠ 壞掉。訊號字面（`'⚫ 資料不足'`）照樣帶回去，
        # 讓呼叫端在灰態裡也能顯示 L0 自己的說法。
        return ChipsReadout(signal=str(_chip.get("signal") or ""),
                            name=str(_name or ""), rows=_rows,
                            miss_reason=_miss, **_badge)

    return ChipsReadout(
        signal=str(_chip.get("signal") or ""),
        concentration=_num(_chip.get("concentration")),
        continuity=_num(_chip.get("continuity")),
        days=_int(_chip.get("days")),
        pos_days=_int(_chip.get("pos_days")),
        total_net_k=_num(_chip.get("total_net_k")),
        total_vol_k=_num(_chip.get("total_vol_k")),
        name=str(_name or ""), rows=_rows, **_badge)
