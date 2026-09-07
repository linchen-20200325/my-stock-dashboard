"""src/services/portfolio_deep_service.py — 「⑥ 組合深度分析」的**唯讀** L3 介面。

═══ 這一支為什麼存在 ═══════════════════════════════════════════════
IA v2 頁 4「💼 我的持股」⑥ 有六格：再平衡 / 核心衛星 / 壓力測試 / VaR /
配息現金流 / 葡萄串。其中**壓力測試 · VaR · 配息現金流**三格的運算都已經有了，
但住的地方讓 L5 拿不到：

  · **壓力測試** — L2 `compute.etf.etf_calc.calc_portfolio_stress_test` 是純函式，
    但它吃的是 `[{ticker, actual_pct}]` ＋ **元**為單位的 `total_value`。
    把「持股列 → 權重 ＋ 總市值」這一步留在畫面層，就是把 §4.1 的
    **張 → 股 → 元** 換算散到 UI 各處。
  · **VaR** — L2 只有 `align_portfolio_returns`（誠實對齊共同交易日），
    分位數那一段目前**是 inline 在 L5** `ui/etf/etf_tab_portfolio.py` 裡的
    （逐檔 `fetch_etf_price` → `quantile` → `× total_value`）。
    第二個畫面要用它，只有兩條路：抄一份（第二套實作，v3 §01-2 明文禁止），
    或把它抽到 L3。**本檔是第二條路。**
  · **配息現金流** — L3 `dividend_tax_service.get_dividend_tax_view()` 已經在了，
    但它吃的是 `[{'ticker','shares'}]`（**股**），而持股帳本記的是**張**。
    那個 `1 張 = 1000 股` 的乘法**必須住 L3** —— L3
    `dividend_station_service.compute_portfolio_totals()` 的 docstring 已經點名
    這件事（「留在畫面層等於讓同一個乘法散在 UI 各處」，§4.1 漏乘 = 1000 倍低估）。

⚠️ **既有的 L5 實作本批一個字都沒有動。** `ui/etf/etf_tab_portfolio.py` 的壓測 /
VaR 區塊仍然是線上那一份。本檔**不是**它的替換品，兩者暫時並存 —— 併檔屬
v3 §01-2 的「消除重複實作」，但那要動既有分頁，落在 `CLAUDE.md §-1`
（沒有 user 指派／沒有 bug 觸發就不動）與 §8.4 step 4 的範圍閘門，**不在本批**。
（誠實揭露，不是漏做。）

═══ 這個檔**一律唯讀** ═════════════════════════════════════════════
本檔只呼叫**取數**與**純函式**：
  L1 `src.data.etf.fetch_etf_price`（VaR 的日報酬）
  L2 `compute.etf.etf_calc.calc_portfolio_stress_test` / `align_portfolio_returns`
  L2 `compute.etf.etf_helpers.normalize_etf_ticker`（代號 SSOT）
  L3 `dividend_station_service.compute_portfolio_totals`（**元**總市值，對帳用）
  L3 `dividend_tax_service.get_dividend_tax_view`（配息稅後試算）
  L0 `shared.sector_flow_thresholds.SHARES_PER_LOT` / `shared.signal_thresholds.*`

**不呼叫**任何 `save_*` / `delete_*` / `create_*` / `rename_*` / `append_*`，
不碰 `gsheet_portfolio`，不寫 `st.session_state`，不自建快取
（`@st.cache_data` 集中在 L1，`CLAUDE.md §8.2.A.2` V-SMART-CACHE-1）。
守衛：`tests/test_p04_hold_view.py::TestPortfolioDeepServiceIsReadOnly`。

═══ ⚠️ 張 → 股 的乘法住在**這裡**，而且只有一個乘法點 ═══════════════
本檔全檔**只有一處**乘 `SHARES_PER_LOT`（`_total_value_twd()`）；
`SHARES_PER_LOT` 取自 L0 `shared/sector_flow_thresholds`，**本檔不寫死 1000**
（§3.3；守衛會掃「本檔不得出現字面 1000」）。

**怎麼證明沒漏乘**（三道，不是靠自律）：
  1. **單一乘法點** —— `_total_value_twd()` 之外沒有第二處張→股；配息那一路
     走 `_shares_of()`，它自己也只呼叫 `_lot_to_shares()` 這同一支換算。
  2. **§4.3 重算對帳** —— 每一次 `get_portfolio_stress()` / `get_portfolio_var()`
     都拿本檔算出來的 `total_value_twd` 與 **L3 既有的**
     `compute_portfolio_totals()["value_twd"]`（它自己也乘 `SHARES_PER_LOT`，
     但納入條件是另外寫的）比對，`math.isclose` 不過就把 `reconciled=False`
     帶出去給畫面揭露 —— **不靜默採信任何一邊**。
     漏乘 1000 倍的差距遠大於 `rel_tol`，對帳當場就會紅。
  3. **數值單元測試** —— 給定 2 張 × 50 元，斷言 `total_value_twd == 100000.0`
     （不是 100.0）。

⚠️ **`row["市值"]` 是「張 · 元」不是「元」**（L3 `build_station_rows` 的註解已寫明）。
本檔拿它**只當權重**（比例對 ×1000 免疫），**絕不**拿它當金額。

═══ §1 Fail Loud：算不出來就說算不出來，不填 0 ═══════════════════════
三支 public 函式都回一個 `computed: bool` ＋ `reason: str`：
  · `computed=False` → **畫面必須顯示「算不出來」並印出 `reason`**，不得顯示 0。
  · `computed=True` 但數字是 0（例如近一年真的沒有配息）→ 那是**有效結果**，
    與「算不出來」是兩件事，`reason` 為空字串。
**本檔不 raise**：頁 4 的 ⑥ 是六個並列格，一格算不出來不該把另外五格染紅
（線框：逐格獨立判態）。呼叫端的 `try/except` 仍在，擋的是真的例外。

⚠️ **觀察清單那些列沒有張數／均價**（`stock_watchlist` 分頁 schema 只有三欄）。
本檔一律**排除**它們，**不當成「持有 0 張、成本 0 元」**（§1 不猜、不填 0）。

═══ 已知限制（誠實列，不是漏做）═══════════════════════════════════
1. **壓力測試的 Beta 缺值**：L2 `calc_portfolio_stress_test` 查不到 Beta 時以 1.0
   估算並回 `beta_imputed_tickers` —— 本檔**原樣透傳**，由畫面揭示哪幾檔是估的。
2. **VaR 只有台幣口徑**：日報酬是「原幣別」報酬，美元計價持股未含匯率
   （同 L2 `compute_portfolio_vs_benchmark` 的自陳）。本檔**不做**匯率換算，
   由畫面加註。
3. **配息現金流不含綜所稅**：`marginal_rate` 一律傳 `None` —— 稅率是**使用者輸入**，
   而新增輸入元件要先出線框草稿給客戶拍板（`CLAUDE.md §-1.5` A-8）。
   L3 `after_tax_dividend` 明文支援 `marginal_rate=None`（只算二代健保），
   本檔用的就是那一半。`income_tax_included=False` 會帶出去，**畫面必須講**。
4. **每一次呼叫都會打 L1**（壓測逐檔 `fetch_etf_info`、VaR 逐檔
   `fetch_etf_price`、配息逐檔 `fetch_etf_dividends`）。三支在 L1 都有
   `@st.cache_data`，本檔**不自建第二層快取**。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# L3 → L0（正常方向）。張→股 的 1000 一律取自這裡，本檔不寫死（§3.3）。
from shared.sector_flow_thresholds import SHARES_PER_LOT
from shared.signal_thresholds import (
    PORTFOLIO_STRESS_TEST_DROP_PCT,
    PORTFOLIO_STRESS_TEST_LOSS_WARN_PCT,
    PORTFOLIO_VAR_95_PERCENTILE,
    PORTFOLIO_VAR_99_PERCENTILE,
    PORTFOLIO_VAR_MONTHLY_WARN_PCT,
    TRADING_DAYS_PER_YEAR,
)

#: 一個月的交易日數。**由 L0 `TRADING_DAYS_PER_YEAR` 推導，不是另立一個門檻**
#: —— 它同時是 (a) 月度 VaR 的 √N 放大係數、(b) 「共同交易日至少要有一個月」
#: 這個樣本下限。兩者用同一個數字是**刻意的**：月度 VaR 的定義就是「一個月」，
#: 樣本連一個月都不到就報月度 VaR，等於用不存在的觀測外推。
#:
#: ⚠️ 既有 L5（`ui/etf/etf_tab_portfolio.py`）那一份寫的是字面 `20` 與 `21`。
#: 本檔**刻意不抄那兩個字面值**（§3.3），也**刻意不借用**
#: `EFFICIENT_FRONTIER_MIN_COMMON_DAYS`（同樣是 20，但語意是效率前緣的樣本下限
#: —— 借用會造成 SPEC §14 點名的「同數字不同義耦合」，日後改一邊就錯另一邊）。
TRADING_DAYS_PER_MONTH: float = TRADING_DAYS_PER_YEAR / 12.0

#: 常態分位數（95% / 99% 單尾）。參數法 VaR 用，**不是門檻**是數學常數。
_Z_95: float = 1.645
_Z_99: float = 2.326

#: VaR 抓多長的歷史。`fetch_etf_price` 的 `period` 字面值（不是門檻）。
_VAR_PRICE_PERIOD: str = "1y"

# ── `computed=False` 的原因（機器可讀；畫面另有自己的文案）─────────────
REASON_NO_PRICED_ROWS: str = (
    "沒有任何一列同時有張數、均價與現價 —— 沒有市值就算不出組合層的風險")
REASON_NO_LOTS_ROWS: str = (
    "沒有任何一列有張數 —— 觀察清單那幾列本來就沒有張數（那份分頁只有三欄）")
REASON_NO_RETURNS: str = "一檔的歷史價格都抓不到，沒有日報酬可以算"
REASON_NO_COMMON_DAYS: str = "各檔沒有共同交易日（不補值、不 ffill）"
REASON_SHORT_SAMPLE: str = "共同交易日不足一個月，樣本太短的尾部估計會過度樂觀"


# ══════════════════════════════════════════════════════════════════
# 單位換算（**全檔唯一的張 → 股乘法點**）
# ══════════════════════════════════════════════════════════════════
def _lot_to_shares(lots: float) -> float:
    """張 → 股。**全檔唯一乘 `SHARES_PER_LOT` 的地方**（§4.1 SSOT）。

    漏乘就是 1000 倍低估 —— 壓測虧損、VaR 元金額、配息現金流三者**全部**
    以它為分母／乘數，所以它只准有一個實作。
    """
    return float(lots) * SHARES_PER_LOT


def _total_value_twd(priced: list[dict]) -> float:
    """組合總市值（**元**）＝ Σ 張數 × 股/張 × 現價。"""
    return sum(_lot_to_shares(_r["lots"]) * _r["price"] for _r in priced)


# ══════════════════════════════════════════════════════════════════
# 納入條件（**與 `compute_portfolio_totals()` 同一把尺**）
# ══════════════════════════════════════════════════════════════════
def _pos(value) -> float | None:
    """> 0 的數才回 float；`None` / 非數 / ≤0 → `None`（**不捏 0**）。"""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    _v = float(value)
    if _v != _v or _v <= 0:     # NaN 或非正
        return None
    return _v


def _row_failed(row: dict) -> bool:
    """這一列在戰情表逐檔抓取時就失敗了（`_detail.error`）。"""
    return bool((row.get("_detail") or {}).get("error"))


def _ticker_of(row: dict) -> str:
    """代號 → L2 SSOT `normalize_etf_ticker`（`0056` → `0056.TW`）。

    ⚠️ **一定要正規化**：L1 的三支 fetcher 直接把字串丟給 yfinance，
    裸代號 `0056` 抓回來的是空資料 —— 而空資料在 §1 之下會被誠實地報成
    「抓不到」，於是一個**單純的格式問題**會被畫成「這檔沒有資料」。
    """
    from src.compute.etf.etf_helpers import normalize_etf_ticker   # L3 → L2

    return normalize_etf_ticker(row.get("代號"))


def priced_rows(rows) -> list[dict]:
    """可計價的持有列 → `[{ticker, lots, price, weight_basis}]`。

    納入條件**逐條對齊** L3 `compute_portfolio_totals()`：
    `held` 為真、`_detail.error` 為空、**張數／均價／現價三者皆 > 0**。
    多一條本檔自己的：**代號要正規化得出來**（沒有代號就沒辦法抓 Beta／價格，
    也沒辦法算它的權重）。這一條會讓本檔的納入集合**可能小於**
    `compute_portfolio_totals()` 的 —— 所以兩邊的總市值要**對帳**，見檔頭。

    ⚠️ `weight_basis` 是 `張數 × 現價`（**張·元**），只當**權重**用：
    比例對 ×1000 免疫，故不必先換成元。**它不是金額，不要拿去顯示。**
    """
    _out: list[dict] = []
    for _r in (rows or []):
        if not isinstance(_r, dict) or not _r.get("held") or _row_failed(_r):
            continue
        _lots, _avg, _cur = (_pos(_r.get("張數")), _pos(_r.get("均價")),
                             _pos(_r.get("現價")))
        if _lots is None or _avg is None or _cur is None:
            continue
        _tk = _ticker_of(_r)
        if not _tk:
            continue
        _out.append({"ticker": _tk, "lots": _lots, "price": _cur,
                     "weight_basis": _lots * _cur})
    return _out


def _held_n(rows) -> int:
    """有幾列是「持有」（含算不出金額的）—— 給畫面講 `valued/held`。"""
    return sum(1 for _r in (rows or [])
               if isinstance(_r, dict) and _r.get("held") and not _row_failed(_r))


def _weights(priced: list[dict]) -> dict[str, float]:
    """`{ticker: 實際權重%}`。同一檔出現兩列時**相加**（不是後者覆蓋前者）。"""
    _total = sum(_r["weight_basis"] for _r in priced)
    if _total <= 0:
        return {}
    _out: dict[str, float] = {}
    for _r in priced:
        _out[_r["ticker"]] = (_out.get(_r["ticker"], 0.0)
                              + _r["weight_basis"] / _total * 100.0)
    return _out


def _reconcile(rows, mine: float) -> tuple[bool, float | None]:
    """§4.3 重算對帳：本檔的總市值 vs L3 既有 `compute_portfolio_totals()`。

    兩邊都乘 `SHARES_PER_LOT`，但**納入條件是各寫各的** —— 對得起來才代表
    「權重的分母」與「金額的分母」是同一批列。對不起來（例如某列沒有代號、
    被本檔排除）就把 `reconciled=False` 帶給畫面，**不靜默採信任何一邊**。

    Returns:
        `(reconciled, 對照值)`。對照值算不出來（L3 回 `None`）時回 `(False, None)`。
    """
    from src.services.dividend_station_service import (      # L3 → L3
        compute_portfolio_totals,
    )

    try:
        _totals = compute_portfolio_totals(list(rows or []))
    except Exception as _e:      # noqa: BLE001 — 對帳失敗不擋主計算，但要說
        print(f"[portfolio_deep] 對帳用的 compute_portfolio_totals 失敗："
              f"{type(_e).__name__}: {_e}")
        return False, None
    if not isinstance(_totals, dict):
        return False, None
    _ref = _totals.get("value_twd")
    if not isinstance(_ref, (int, float)):
        return False, None
    _ref = float(_ref)
    return math.isclose(mine, _ref, rel_tol=1e-9, abs_tol=1e-6), _ref


# ══════════════════════════════════════════════════════════════════
# ⑥-c 壓力測試
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class StressResult:
    """指定跌幅情境下，這個組合大約會回撤多少（**元**）。

    Attributes:
        computed: 算出來了沒。`False` → 畫面顯示「算不出來」＋ `reason`，**不顯示 0**。
        reason: `computed=False` 的機器可讀原因（`REASON_*`）。空字串 = 有算出來。
        drop_pct: 假設的市場跌幅（%，負數）。L0 SSOT，本檔不寫死。
        loss_twd: 預估總虧損（**元**，與 `drop_pct` 同號 → 負數）。
        loss_pct: `|loss| / 總市值 × 100`。
        warn: `loss_pct` 是否超過 L0 的警示門檻。
        total_value_twd: 納入計算的組合總市值（**元**，已乘 `SHARES_PER_LOT`）。
        beta_imputed: 查無 Beta、以 1.0 估算的代號（**畫面必須揭示**，§1）。
        valued_n / held_n: 納入 / 持有列數。`valued_n < held_n` → `partial`。
        reconciled: 總市值與 `compute_portfolio_totals()` 對得起來（§4.3）。
        reference_value_twd: 對照值本身（對不起來時給畫面看差在哪）。
    """

    computed: bool = False
    reason: str = ""
    drop_pct: float = 0.0
    loss_twd: float = 0.0
    loss_pct: float = 0.0
    warn: bool = False
    warn_pct: float = 0.0
    total_value_twd: float = 0.0
    beta_imputed: tuple[str, ...] = ()
    valued_n: int = 0
    held_n: int = 0
    reconciled: bool = True
    reference_value_twd: float | None = None

    @property
    def partial(self) -> bool:
        """有持有列沒被納入（缺張數／均價／現價）—— 畫面必須講出來。"""
        return self.valued_n < self.held_n


def get_portfolio_stress(rows, *, drop_pct: float | None = None) -> StressResult:
    """戰情表列 → 壓力測試。**純讀不寫。**

    Args:
        rows: L3 `get_station_rows()` 的逐檔列（要有 `代號` / `held` / `張數` /
            `均價` / `現價`）。**觀察清單那些列會被排除**（沒有張數）。
        drop_pct: 假設跌幅（%）。`None` → L0 `PORTFOLIO_STRESS_TEST_DROP_PCT`。

    Returns:
        `StressResult`。算不出來 → `computed=False` ＋ `reason`（**不回 0 當答案**）。

    ⚠️ 逐檔會打一次 L1 `fetch_etf_info`（L2 `calc_portfolio_stress_test` 內部做的）
    —— 那一支在 L1 有 `@st.cache_data`，本檔不自建第二層。
    """
    from src.compute.etf.etf_calc import calc_portfolio_stress_test   # L3 → L2

    _drop = float(PORTFOLIO_STRESS_TEST_DROP_PCT if drop_pct is None else drop_pct)
    _priced = priced_rows(rows)
    _held = _held_n(rows)
    if not _priced:
        return StressResult(reason=REASON_NO_PRICED_ROWS, drop_pct=_drop,
                            held_n=_held,
                            warn_pct=float(PORTFOLIO_STRESS_TEST_LOSS_WARN_PCT))
    _total = _total_value_twd(_priced)
    _ok, _ref = _reconcile(rows, _total)
    _w = _weights(_priced)
    _res = calc_portfolio_stress_test(
        [{"ticker": _t, "actual_pct": _p} for _t, _p in _w.items()],
        _total, drop_pct=_drop)
    return StressResult(
        computed=True, drop_pct=float(_res.get("drop_pct", _drop)),
        loss_twd=float(_res.get("total_loss", 0.0)),
        loss_pct=float(_res.get("loss_pct", 0.0)),
        warn=float(_res.get("loss_pct", 0.0)) > PORTFOLIO_STRESS_TEST_LOSS_WARN_PCT,
        warn_pct=float(PORTFOLIO_STRESS_TEST_LOSS_WARN_PCT),
        total_value_twd=_total,
        beta_imputed=tuple(str(_t) for _t in (_res.get("beta_imputed_tickers") or ())),
        valued_n=len(_w), held_n=_held,
        reconciled=_ok, reference_value_twd=_ref)


# ══════════════════════════════════════════════════════════════════
# ⑥-d VaR（歷史模擬法 ＋ 參數法）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class VarResult:
    """組合的單日 / 月度風險值（**元**，正數＝可能虧掉多少）。

    Attributes:
        computed / reason: 同 `StressResult`。
        hist_95_twd / hist_99_twd: 歷史模擬法（近一年共同交易日的分位數）。
        param_95_twd / param_99_twd: 參數法（常態假設）。
        monthly_99_twd / monthly_99_pct: 月度 99%（√一個月交易日 近似）。
        warn: `monthly_99_pct` 是否超過 L0 門檻。
        n_common / n_union / dropped: 共同交易日 / 聯集 / 被剔除的非共同日。
        first_day / last_day: 樣本區間（`YYYY-MM-DD`；算不出來為空字串）。
        limiter / limiter_start: 壓縮視窗的最晚上市那一檔（**畫面要講**）。
        tickers_used: 真的進了組合日報酬的代號。
        no_price: 一筆日報酬都抓不到的代號（§1：不當成 0% 報酬）。
        fetch_errors: 取價時**拋了例外**的代號 ＋ 例外文字。
            ⚠️ 它與 `no_price` **不是同一件事**（v3 §02「介面狀態嚴格分離」）：
            回一份空資料是「這檔沒有歷史」（灰），**拋例外是上游掛了**（紅）。
            混成一種，Yahoo 整個掛掉的那一天使用者會以為「我的股票太新」。
    """

    computed: bool = False
    reason: str = ""
    hist_95_twd: float = 0.0
    hist_99_twd: float = 0.0
    param_95_twd: float = 0.0
    param_99_twd: float = 0.0
    monthly_99_twd: float = 0.0
    monthly_99_pct: float = 0.0
    warn: bool = False
    warn_pct: float = 0.0
    total_value_twd: float = 0.0
    n_common: int = 0
    n_union: int = 0
    dropped: int = 0
    min_days: int = 0
    first_day: str = ""
    last_day: str = ""
    limiter: str = ""
    limiter_start: str = ""
    tickers_used: tuple[str, ...] = ()
    no_price: tuple[str, ...] = ()
    fetch_errors: tuple[str, ...] = ()
    valued_n: int = 0
    held_n: int = 0
    reconciled: bool = True
    reference_value_twd: float | None = None

    @property
    def partial(self) -> bool:
        return self.valued_n < self.held_n

    @property
    def upstream_down(self) -> bool:
        """**上游真的掛了**（有例外，而且一檔都沒抓成）→ 呼叫端應判紅，不是灰。

        只有例外、沒有任何成功 → 這不是「你的持股沒有歷史」，是取價那一層壞了。
        有一部分抓成功時**不算掛掉**（那是部分缺料，由 `fetch_errors` 揭露即可）。
        """
        return bool(self.fetch_errors) and not self.tickers_used

    @property
    def window_squeezed(self) -> bool:
        """視窗被最晚上市的那一檔壓縮了（樣本短 → 尾部估計偏樂觀）。"""
        return bool(self.limiter and self.dropped > 0)


def _daily_returns(tickers) -> tuple[dict, list[str], list[str]]:
    """`{ticker: 日報酬 Series}` ＋ 沒有資料的代號 ＋ **拋了例外**的代號。

    §1：抓不到就**不放進去**（不是放一條 0% 報酬）—— 補 0 會稀釋波動、
    讓尾部 VaR 看起來比實際小，那正是「錯的數字比沒有數字更危險」。

    ⚠️ **「空資料」與「拋例外」分開回**（v3 §02 灰 vs 紅）：
    前者是「這一檔沒有那段歷史」（有效結果），後者是「取價那一層壞了」（真出錯）。
    L1 `fetch_etf_price` 大多數失敗會**自己吞掉並回空 DataFrame**，所以
    例外那一路不常走到 —— 但走到的時候它是唯一分得出「上游掛了」的訊號。
    """
    from src.data.etf import fetch_etf_price     # L3 → L1（正常方向）

    _rets: dict = {}
    _missing: list[str] = []
    _errors: list[str] = []
    for _tk in tickers:
        try:
            _df = fetch_etf_price(_tk, period=_VAR_PRICE_PERIOD)
        except Exception as _e:     # noqa: BLE001 — 單檔失敗不擋整組，但要記
            print(f"[portfolio_deep/var] {_tk} 價格抓取失敗："
                  f"{type(_e).__name__}: {_e}")
            _errors.append(f"{_tk}：{type(_e).__name__}: {_e}")
            continue
        if _df is None or getattr(_df, "empty", True) or "Close" not in _df:
            _missing.append(_tk)
            continue
        _s = _df["Close"].pct_change().dropna()
        if len(_s) == 0:
            _missing.append(_tk)
            continue
        _rets[_tk] = _s
    return _rets, _missing, _errors


def _day_str(value) -> str:
    """`Timestamp` → `'YYYY-MM-DD'`；拿不到 → 空字串（**不編一個日期**）。"""
    try:
        return value.strftime("%Y-%m-%d")
    except Exception:       # noqa: BLE001 — 只是顯示用，拿不到就留空
        return ""


def get_portfolio_var(rows) -> VarResult:
    """戰情表列 → VaR（歷史模擬法 ＋ 參數法）。**純讀不寫。**

    Args:
        rows: 同 `get_portfolio_stress()`。

    Returns:
        `VarResult`。共同交易日不足一個月 → `computed=False` ＋
        `REASON_SHORT_SAMPLE`（**不報一個樣本 3 天的 VaR**）。

    ⚠️ 對齊方式**完全交給 L2** `align_portfolio_returns`：只取「全員皆有交易」
    的共同日，**絕不** ffill／fillna(0)。本檔不自己對齊（那會是第二套規則）。
    """
    from src.compute.etf.etf_calc import align_portfolio_returns   # L3 → L2

    _priced = priced_rows(rows)
    _held = _held_n(rows)
    _min_days = int(TRADING_DAYS_PER_MONTH)
    _base = {"warn_pct": float(PORTFOLIO_VAR_MONTHLY_WARN_PCT),
             "min_days": _min_days, "held_n": _held}
    if not _priced:
        return VarResult(reason=REASON_NO_PRICED_ROWS, **_base)

    _total = _total_value_twd(_priced)
    _ok, _ref = _reconcile(rows, _total)
    _w = _weights(_priced)
    _base = {**_base, "total_value_twd": _total, "valued_n": len(_w),
             "reconciled": _ok, "reference_value_twd": _ref}

    _rets, _missing, _errors = _daily_returns(list(_w))
    if not _rets:
        # 一檔都沒抓成：有例外 → `upstream_down` 為真（呼叫端判紅）；
        # 全是空資料 → 灰（「這幾檔沒有那段歷史」是有效結果）。
        return VarResult(reason=REASON_NO_RETURNS, no_price=tuple(_missing),
                         fetch_errors=tuple(_errors), **_base)

    _al = align_portfolio_returns(_rets, _w)
    _port = _al.get("port_ret")
    _n_common = int(_al.get("n_common") or 0)
    _diag = {
        "n_common": _n_common, "n_union": int(_al.get("n_union") or 0),
        "dropped": int(_al.get("dropped") or 0),
        "limiter": str(_al.get("limiter") or ""),
        "limiter_start": _day_str(_al.get("limiter_start")),
        "tickers_used": tuple(str(_t) for _t in (_al.get("tickers_used") or ())),
        "no_price": tuple(_missing),
        "fetch_errors": tuple(_errors),
    }
    if _port is None or len(_port) == 0:
        return VarResult(reason=REASON_NO_COMMON_DAYS, **_base, **_diag)
    if len(_port) < _min_days:
        return VarResult(reason=REASON_SHORT_SAMPLE, **_base, **_diag)

    # 歷史模擬法：近一年共同日的最差分位數 × 總市值（元）。
    _h95 = abs(float(_port.quantile(PORTFOLIO_VAR_95_PERCENTILE)) * _total)
    _h99 = abs(float(_port.quantile(PORTFOLIO_VAR_99_PERCENTILE)) * _total)
    # 參數法：常態假設 μ − zσ。與歷史法並陳（肥尾時歷史法通常更保守）。
    _mu, _sig = float(_port.mean()), float(_port.std())
    _p95 = abs((_mu - _Z_95 * _sig) * _total)
    _p99 = abs((_mu - _Z_99 * _sig) * _total)
    # 月度 99%：√（一個月交易日）近似，係數與樣本下限**同一個數字**（見檔頭常數）。
    _m99 = _h99 * math.sqrt(TRADING_DAYS_PER_MONTH)
    _m99_pct = (_m99 / _total * 100.0) if _total > 0 else 0.0
    return VarResult(
        computed=True,
        hist_95_twd=_h95, hist_99_twd=_h99,
        param_95_twd=_p95, param_99_twd=_p99,
        monthly_99_twd=_m99, monthly_99_pct=_m99_pct,
        warn=_m99_pct > PORTFOLIO_VAR_MONTHLY_WARN_PCT,
        first_day=_day_str(_port.index.min()),
        last_day=_day_str(_port.index.max()),
        **_base, **_diag)


# ══════════════════════════════════════════════════════════════════
# ⑥-e 配息現金流（**張 → 股 的換算住這裡**）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class DividendCashResult:
    """近一年**實際入帳**的配息（稅前 → 扣二代健保）。

    ⚠️ **不含綜所稅**：`income_tax_included` 恆為 `False`。稅率是使用者輸入，
    而新增輸入元件要先出線框草稿給客戶拍板（`CLAUDE.md §-1.5` A-8）。
    畫面**必須把這件事講出來**，否則「稅後」兩個字就是在說謊。

    Attributes:
        computed / reason: 同 `StressResult`。
        gross_twd: 近一年稅前配息合計（元）。**0 且 `payouts_n=0` 是有效結果**
            （近一年真的沒有配息），與 `computed=False` 不同。
        nhi_twd: 二代健保補充保費合計（逐筆過門檻才收，L2 `nhi_premium` 判）。
        net_after_nhi_twd: 扣掉二代健保之後（**不是**最終稅後）。
        payouts_n: 逐筆配息筆數（0 = 近一年沒有配息紀錄）。
        per_ticker: `[{代號, 幣別, 近1年稅前配息, 二代健保, 配息筆數}]`（原樣透傳）。
        overseas: 外幣／海外標的（**已排除稅務計算，僅標記**，§4.6 不混算）。
        lots_n / held_n: 有張數 / 持有的列數。
        shares_total: 換算後的總股數（**張 × `SHARES_PER_LOT`**，給畫面對帳看）。
    """

    computed: bool = False
    reason: str = ""
    gross_twd: float = 0.0
    nhi_twd: float = 0.0
    net_after_nhi_twd: float = 0.0
    payouts_n: int = 0
    per_ticker: tuple[dict, ...] = ()
    overseas: tuple[str, ...] = ()
    tw_n: int = 0
    lots_n: int = 0
    held_n: int = 0
    shares_total: float = 0.0
    income_tax_included: bool = False

    @property
    def has_payouts(self) -> bool:
        """近一年**真的有**配息紀錄。`False` ＋ `computed=True` = 有效的「沒有」。"""
        return self.payouts_n > 0

    @property
    def partial(self) -> bool:
        return self.lots_n < self.held_n


def _shares_of(rows) -> list[dict]:
    """持有列 → `[{ticker, shares}]`。**張 → 股 就在這一步**（唯一乘法點）。

    ⚠️ 與 `priced_rows()` 的納入條件**刻意不同**：配息只需要**張數**
    （每股配息 × 股數），不需要均價與現價。用同一把尺會把「有張數但沒填均價」
    的持股整檔漏掉 —— 那些股票的配息是真的會入帳的。
    ⚠️ 觀察清單那些列 `張數` 是 `None` → 自然被排除，**不是**當成 0 股。
    """
    _out: list[dict] = []
    for _r in (rows or []):
        if not isinstance(_r, dict) or not _r.get("held") or _row_failed(_r):
            continue
        _lots = _pos(_r.get("張數"))
        _tk = _ticker_of(_r)
        if _lots is None or not _tk:
            continue
        _out.append({"ticker": _tk, "shares": _lot_to_shares(_lots)})
    return _out


def get_dividend_cash_flow(rows) -> DividendCashResult:
    """戰情表列 → 近一年配息現金流（稅前 ＋ 二代健保）。**純讀不寫。**

    Args:
        rows: 同 `get_portfolio_stress()`。只需要 `代號` / `held` / `張數`。

    Returns:
        `DividendCashResult`。**綜所稅不算**（`marginal_rate=None`）——
        `income_tax_included=False` 帶給畫面，**必須講出來**。

    ⚠️ 逐檔會打一次 L1 `fetch_etf_dividends`（L3 `dividend_tax_service` 內部做的）。
    """
    from src.services.dividend_tax_service import (        # L3 → L3
        get_dividend_tax_view,
    )

    _held = _held_n(rows)
    _shares = _shares_of(rows)
    if not _shares:
        return DividendCashResult(reason=REASON_NO_LOTS_ROWS, held_n=_held)

    # ⚠️ `marginal_rate=None` 是**刻意的**，不是忘了傳 —— 見 dataclass docstring。
    _view = get_dividend_tax_view(
        [{"ticker": _s["ticker"], "shares": _s["shares"]} for _s in _shares],
        marginal_rate=None)
    _summary = (_view or {}).get("summary") or {}
    _per = tuple(dict(_p) for _p in ((_view or {}).get("per_etf") or ()))
    return DividendCashResult(
        computed=True,
        gross_twd=float(_summary.get("gross") or 0.0),
        nhi_twd=float(_summary.get("nhi_premium") or 0.0),
        net_after_nhi_twd=float(_summary.get("net_after_nhi") or 0.0),
        payouts_n=sum(int(_p.get("配息筆數") or 0) for _p in _per),
        per_ticker=_per,
        overseas=tuple(str(_t) for _t in ((_view or {}).get("overseas") or ())),
        tw_n=int((_view or {}).get("n_tw") or 0),
        lots_n=len(_shares), held_n=_held,
        shares_total=sum(_s["shares"] for _s in _shares),
        income_tax_included=False)


#: 本檔 public 介面（`from ... import *` 不是本 repo 的用法，這裡只作自我說明）。
__all__ = [
    "DividendCashResult", "StressResult", "VarResult",
    "get_dividend_cash_flow", "get_portfolio_stress", "get_portfolio_var",
    "priced_rows",
    "REASON_NO_COMMON_DAYS", "REASON_NO_LOTS_ROWS", "REASON_NO_PRICED_ROWS",
    "REASON_NO_RETURNS", "REASON_SHORT_SAMPLE",
    "TRADING_DAYS_PER_MONTH",
]
