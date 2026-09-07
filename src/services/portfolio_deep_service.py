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
  L1 `src.data.etf.fetch_etf_price`（VaR 的日報酬 ＋ 上市/上櫃後綴判定）
  L2 `compute.etf.etf_calc.calc_portfolio_stress_test` / `align_portfolio_returns`
  L2 `compute.etf.etf_helpers.normalize_etf_ticker`（代號 SSOT）
  L3 `dividend_station_service.compute_portfolio_totals`（**元**總市值，對帳用）
  L3 `dividend_tax_service.get_dividend_tax_view`（配息稅後試算）
  L0 `shared.sector_flow_thresholds.SHARES_PER_LOT` / `shared.signal_thresholds.*`

**不呼叫**任何 `save_*` / `delete_*` / `create_*` / `rename_*` / `append_*`，
不碰 `gsheet_portfolio`，不寫 `st.session_state`，不自建快取
（`@st.cache_data` 集中在 L1，`CLAUDE.md §8.2.A.2` V-SMART-CACHE-1）。
守衛：`tests/test_p04_hold_view.py::TestPortfolioDeepServiceIsReadOnly`。

═══ ⚠️ 張 → 股 的乘法住在**這裡**，而且**本檔**只有一個乘法點 ═══════════
本檔**只有一處**乘 `SHARES_PER_LOT` —— **`_lot_to_shares()`**；
`_total_value_twd()` / `_value_by_ticker()` / `_shares_of()` 都只是**呼叫**它，
自己不做那個乘法。（2026-09-07 更正：本行原本把乘法點寫成 `_total_value_twd()`，
指錯了函式 —— 名字寫錯的 SSOT 指標會讓下一個人去改錯的地方。）
`SHARES_PER_LOT` 取自 L0 `shared/sector_flow_thresholds`，**本檔不寫死 1000**
（§3.3；守衛會掃「本檔不得出現字面 1000」）。

⛔ **「本檔唯一」不等於「全站唯一」**（2026-09-07 實測，別再寫錯）：
全站**至少三處**拿每張股數做算術 —— 本檔 `_lot_to_shares()`、
`src/services/dividend_station_service.py:887`（`compute_portfolio_totals()` 內）、
`src/compute/sector_flow.py:158`（`SHARES_PER_LOT / YUAN_PER_YI` 的合併係數）。
本檔的保證**只涵蓋本檔**；把它讀成全站保證，就是 `CLAUDE.md §-2` 規則 6
點名的那種「用單檔證據撐全稱句」。
（守衛：`tests/test_p04_hold_view.py::TestTheLotToShareClaimIsMeasurable`
**現場掃整個 repo** 量測乘法點數量，數量變了會轉紅。）

**怎麼證明沒漏乘**（三道，不是靠自律）：
  1. **單一乘法點** —— `_lot_to_shares()` 之外，本檔沒有第二處張→股；配息那一路
     走 `_shares_of()`，它自己也只呼叫 `_lot_to_shares()` 這同一支換算。
     守衛：`TestPortfolioDeepServiceIsReadOnly::test_there_is_exactly_one_multiplication_site`
     （**單檔** AST 掃描 —— 它證得了「本檔唯一」，證不了「全站唯一」）。
  2. **§4.3 重算對帳** —— 每一次 `get_portfolio_stress()` / `get_portfolio_var()`
     都拿本檔算出來的 `total_value_twd` 與 **L3 既有的**
     `compute_portfolio_totals()["value_twd"]`（它自己也乘 `SHARES_PER_LOT`
     —— 2026-09-07 複查：該乘法在 `dividend_station_service.py:887`，
     就在 `compute_portfolio_totals()`（:853）函式體內，本句指涉正確；
     但納入條件是另外寫的）比對，`math.isclose` 不過就把 `reconciled=False`
     帶出去給畫面揭露 —— **不靜默採信任何一邊**。
     漏乘 1000 倍的差距遠大於 `rel_tol`，對帳當場就會紅。
  3. **數值單元測試** —— 給定 2 張 × 50 元，斷言 `total_value_twd == 100000.0`
     （不是 100.0）。

⚠️ **`row["市值"]` 是「張 · 元」不是「元」**（L3 `build_station_rows` 的註解已寫明）。
本檔拿它**只當權重**（比例對 ×1000 免疫），**絕不**拿它當金額。

═══ ⚠️ 上市 / 上櫃後綴：**本檔只有一處**決定要拿哪個字串去打 yfinance ════
L2 `normalize_etf_ticker` 一律補 `.TW`（上市），但 **yfinance 的上櫃股要 `.TWO`**。
`5314` / `8069` 這類上櫃存股補成 `.TW` 抓回來永遠是空的，於是同一個**格式問題**
會在三個地方各自被畫成一個**資料問題**：VaR 說「沒有歷史」、壓測說「查無 Beta」
（落進 `beta_imputed=1.0`）、配息說「近一年沒配息」。
本檔的處置：`_resolve_yf_ticker()` **單一入口**（先 `.TW`，抓空且結尾是 `.TW`
才試 `.TWO`，命中後三條路都改用 `.TWO`），規則**照 L3 既有的
`dividend_station_service.fetch_metrics()`**，不另立第二套（v3 §01-2）。
⚠️ **每檔最多多打一次**（`.TW` 抓到就不試 `.TWO`；非 `.TW` 結尾一次都不多打）——
無條件雙打會把上游流量乘二（§1.A-3「失敗要退避，不得轟炸上游」）。
⚠️ 對外一律講**正規化代號**（`.TW`）：後綴是打上游用的字串，不是這檔股票的身分。

═══ ⚠️ 覆蓋率：不准拿「算得出來的那批」去代表「全部」 ═══════════════════
三支 public 函式**都**回一個 `coverage_pct`（VaR 另回 `covered_value_twd` /
`excluded_tickers`，配息另回 `excluded_tickers` / `no_payout_tickers`，
壓測另回 `imputed_value_twd`）。理由是同一個：
**部分抓不到卻照樣給總額，是一次沒有寫成 `fillna` 的補值**（§1）——
它不會出現在任何缺值統計裡，只會讓數字看起來剛好。
  · **VaR**：分位數只講得動「抓得到報酬 ＋ 有共同交易日」的子集 → 元金額乘的是
    **子集的市值**（`covered_value_twd`），不是全組合市值。覆蓋率 100% 時兩者相等。
  · **壓測**：每一檔都進了計算，但查不到 Beta 的那幾檔用的是**假設值 1.0**
    → `coverage_pct` ＝ Beta 是真的那部分佔多少市值。
  · **配息**：海外標的**不算進** `gross_twd`（§4.6 不混算）→ `coverage_pct`
    ＝ 納入計算的檔數佔比（**檔數口徑**，本檔手上沒有配息那一路的市值，不假裝有）。
畫面的義務：`full_coverage` 為 `False` 時**必須**把覆蓋率講出來，
不得只寫「你的組合 VaR ＝ X 元」。

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
   估算並回 `beta_imputed_tickers` —— 本檔透傳（**代號換回 `.TW` 身分**），
   另附 `imputed_value_twd` / `coverage_pct`：「幾檔是估的」講不出嚴重度，
   「估掉的是多少錢」才講得出。⚠️ 上櫃股的 Beta 缺值有一部分是**後綴問題**，
   已由 `_resolve_yf_ticker()` 修掉；剩下的才是真的查無 Beta。
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
   ⚠️ **後綴判定會多打一次 `fetch_etf_price`**（壓測與配息這兩條路原本不取價）。
   代價是拿得到的：不判後綴，上櫃股在這三格**永遠**是「查無 Beta ／ 沒有歷史 ／
   沒有配息」。三條路刻意共用**同一個 `period`（`_VAR_PRICE_PERIOD`）**，
   所以同一次渲染裡 VaR 與另外兩格打的是 L1 **同一個快取鍵**，實際只多一次往返。
5. **配息覆蓋率是「檔數」不是「金額」**：配息那一路刻意不要求均價／現價
   （沒填均價的持股，配息還是會入帳），所以本檔手上沒有它們的市值 ——
   `coverage_pct` 用檔數口徑並在 dataclass 明說，**不假裝有金額權重**。
6. **上游把「真的沒配息」與「抓不到配息」回成同一個空序列**
   （L3 `dividend_tax_service._recent_payments_twd`）。本檔分不出來，
   只能把「貢獻 0 元」的代號列進 `no_payout_tickers` 並在 dataclass 說清楚 ——
   **不得**由畫面自行解讀成「這幾檔沒有配息」。
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
    VAR_Z_SCORE_95,
    VAR_Z_SCORE_99,
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

#: 常態分位數（95% / 99% 單尾）。參數法 VaR 用，**不是門檻**是數學常數 ——
#: 但仍然**不准 inline**（§3.3）：它與 L0 `PORTFOLIO_VAR_9x_PERCENTILE` 是同一個
#: 信心水準的兩種表示法，寫死在這裡等於讓「歷史法的 95%」與「參數法的 95%」
#: 可以各自漂移。SSOT ＋ 兩者的耦合說明 ＋ 舊 Tab 未收斂複本的登記，
#: 都在 `shared/signal_thresholds.py`（本檔只 import，不重寫）。
#: v19.20x FIX-3：原本這裡是 `_Z_95 = 1.645` / `_Z_99 = 2.326` 兩個 inline 字面值，
#: 且與 `ui/etf/etf_tab_portfolio.py:1123-1124` **逐字重複**。

#: VaR 抓多長的歷史。`fetch_etf_price` 的 `period` 字面值（不是門檻）。
#: ⚠️ **全檔只有這一個 period**：後綴判定（`_resolve_yf_ticker()`）與真正取報酬
#: 走的是**同一個 `period`** —— 不同 period 會是 L1 `@st.cache_data` 的不同快取鍵，
#: 等於為了判一個後綴多打一次上游（§1.A-3）。要改請只改這一行。
_VAR_PRICE_PERIOD: str = "1y"

#: 上市（TWSE）／上櫃（TPEx）在 yfinance 的後綴。**不是門檻，是外部介面的固定字串**。
#: L2 `normalize_etf_ticker` 一律補 `.TW`（上市）；上櫃股要 `.TWO` 才抓得到 —— 見
#: `_resolve_yf_ticker()` 的 docstring。
_SUFFIX_TWSE: str = ".TW"
_SUFFIX_TPEX: str = ".TWO"

# ── `computed=False` 的原因（機器可讀；畫面另有自己的文案）─────────────
REASON_NO_PRICED_ROWS: str = (
    "沒有任何一列同時有張數、均價與現價 —— 沒有市值就算不出組合層的風險")
REASON_NO_LOTS_ROWS: str = (
    "沒有任何一列有張數 —— 觀察清單那幾列本來就沒有張數（那份分頁只有三欄）")
REASON_NO_RETURNS: str = "一檔的歷史價格都抓不到，沒有日報酬可以算"
REASON_NO_COMMON_DAYS: str = "各檔沒有共同交易日（不補值、不 ffill）"
REASON_SHORT_SAMPLE: str = "共同交易日不足一個月，樣本太短的尾部估計會過度樂觀"
REASON_NO_COVERED_VALUE: str = (
    "進到分布裡的那幾檔算不出市值 —— 沒有分子就沒有元金額（不拿全組合市值頂替）")
REASON_DIVIDEND_CONTRACT_DRIFT: str = (
    "上游 `get_dividend_tax_view()` 的 summary 少了必要欄位 —— "
    "契約漂移了，這一格不給數字（缺欄不補 0）")


# ══════════════════════════════════════════════════════════════════
# 單位換算（**本檔唯一的張 → 股乘法點**；⚠️ 全站另有兩處，見檔頭）
# ══════════════════════════════════════════════════════════════════
def _lot_to_shares(lots: float) -> float:
    """張 → 股。**本檔唯一乘 `SHARES_PER_LOT` 的地方**（§4.1 SSOT）。

    漏乘就是 1000 倍低估 —— 壓測虧損、VaR 元金額、配息現金流三者**全部**
    以它為分母／乘數，所以**在本檔**它只准有一個實作。

    ⛔ **「本檔唯一」≠「全站唯一」**：全站另有
    `dividend_station_service.py:887` 與 `compute/sector_flow.py:158`
    （2026-09-07 實測）。詳見檔頭。
    """
    return float(lots) * SHARES_PER_LOT


def _value_by_ticker(priced: list[dict]) -> dict[str, float]:
    """`{ticker: 市值（**元**）}`。同一檔出現兩列 → **相加**（同 `_weights()`）。

    **覆蓋率的分子就從這裡來**：VaR 只能對「真的抓得到報酬」的那幾檔講話，
    要講出「那幾檔佔多少市值」就必須逐檔留著金額，而不是只留一個總數。
    """
    _out: dict[str, float] = {}
    for _r in priced:
        _out[_r["ticker"]] = (_out.get(_r["ticker"], 0.0)
                              + _lot_to_shares(_r["lots"]) * _r["price"])
    return _out


def _total_value_twd(priced: list[dict]) -> float:
    """組合總市值（**元**）＝ Σ 張數 × 股/張 × 現價。"""
    return sum(_value_by_ticker(priced).values())


# ══════════════════════════════════════════════════════════════════
# 納入條件（**與 `compute_portfolio_totals()` 同一把尺**）
# ══════════════════════════════════════════════════════════════════
def _is_full(coverage_pct: float) -> bool:
    """覆蓋率算不算「100%」—— **用容差比，不用 `==` / `>=`**（§4.3）。

    ⚠️ 這不是吹毛求疵：`total` 與 `covered` 是**同一組浮點數用不同順序加起來的**
    （`total` 照 dict 順序、`covered` 照 `tickers_used` 順序），
    全員都抓到時兩者仍可能差在最後一個 bit → `99.99999999999999`。
    用 `>= 100.0` 判，會讓一個**完全沒有缺料**的組合被標成「部分覆蓋」，
    畫面因此掛上一句不存在的警告 —— 那和捏造缺料是同一種錯（§1，反方向）。
    """
    return (coverage_pct >= 100.0
            or math.isclose(coverage_pct, 100.0, rel_tol=1e-9, abs_tol=1e-9))


def _num(value) -> float | None:
    """數就回 float，**不是數就回 `None`**（含 `bool` 與 NaN）。

    與 `_pos()` 的差別：本函式**允許 0 與負數** —— 用在「上游回來的欄位是不是
    一個數」這種契約檢查上（配息 0 元是有效答案，缺欄不是）。
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    _v = float(value)
    return None if _v != _v else _v      # NaN


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


# ══════════════════════════════════════════════════════════════════
# 上市 / 上櫃後綴判定（**本檔唯一一處決定要拿哪個後綴去打 yfinance**）
# ══════════════════════════════════════════════════════════════════
def _fetch_price_with_otc_fallback(ticker: str):
    """`(真的有資料的代號, 價格 DataFrame)`；`.TW` / `.TWO` 都空 → `(None, None)`。

    ⚠️ **「本檔唯一」而已**：同樣的 `.TW` → `.TWO` 規則在
    `src/services/dividend_station_service.py`（`fetch_metrics()`）也有一份 ——
    本檔是**照它抄的**，不是全站唯一實作。合併兩份屬跨檔重構，不在本批。

    ⚠️ **為什麼一定要有這一段**：L2 `normalize_etf_ticker` 一律補 `.TW`（上市），
    但 **yfinance 的上櫃股要 `.TWO`** —— `5314` / `8069` 這類上櫃存股補成
    `5314.TW` 抓回來永遠是空的。少了這一段，那些持股會：
      · VaR：進不了分布（被算成「沒有歷史」）→ 覆蓋率悄悄變低；
      · 壓測：`fetch_etf_info` 查無 Beta → 落進 `beta_imputed=1.0`（拿假設當事實）；
      · 配息：`fetch_etf_dividends` 回空 → 被當成「近一年沒配息」。
    三者都是**格式問題被畫成資料問題**，正是 §1 說的「錯的數字比沒有數字更危險」。

    做法**照抄 L3 既有的正確實作**（`dividend_station_service.fetch_metrics()`：
    先 `.TW`，抓空且結尾是 `.TW` 才改試 `.TWO`，命中後**後續全部改用 `.TWO`**），
    **本檔不另立第二套規則**（v3 §01-2 消除重複實作）。

    ⚠️ **每檔最多多打一次**：`.TW` 抓到就**不會**去打 `.TWO`；非 `.TW` 結尾
    （`SPY` 這種）**一次都不多打**。無條件雙打會把上游流量直接乘二（§1.A-3
    「失敗要退避，不得轟炸上游」）。

    ⚠️ 例外**往上拋**（本函式不吞）—— 呼叫端要分得出「這檔沒有歷史」（灰）
    與「取價那一層掛了」（紅），見 `_daily_returns()`（v3 §02 介面狀態嚴格分離）。
    """
    from src.data.etf import fetch_etf_price     # L3 → L1（正常方向）

    _df = fetch_etf_price(ticker, period=_VAR_PRICE_PERIOD)
    if _df is not None and not getattr(_df, "empty", True):
        return ticker, _df
    if not ticker.endswith(_SUFFIX_TWSE):
        return None, None                       # 美股 / 已是 .TWO → 沒有第二個猜法
    _alt = ticker[:-len(_SUFFIX_TWSE)] + _SUFFIX_TPEX
    _df2 = fetch_etf_price(_alt, period=_VAR_PRICE_PERIOD)
    if _df2 is not None and not getattr(_df2, "empty", True):
        return _alt, _df2
    return None, None


def _resolve_yf_ticker(ticker: str) -> str | None:
    """正規化代號 → **真的抓得到歷史價**的 yfinance 代號；都抓不到 → `None`。

    **本檔要打 yfinance 的地方一律走這裡**（單一入口）—— 取價、Beta、配息三條路
    共用同一個後綴判定，才不會出現「VaR 用 `.TWO`、配息用 `.TW`」這種同一檔股票
    在同一頁上被當成兩檔的情形。

    回 `None` ＝「這個代號在 yfinance 兩個後綴都沒有資料」。**不是**「這檔不存在」
    —— 沙箱無外網時每一檔都會是 `None`。所以呼叫端**不得**拿 `None` 當「代號有錯」
    的結論，只能當「這一檔這次沒抓到」（§1 誠實）。
    """
    try:
        return _fetch_price_with_otc_fallback(ticker)[0]
    except Exception as _e:     # noqa: BLE001 — 判後綴失敗不擋主計算，但要記
        print(f"[portfolio_deep] {ticker} 後綴判定時取價失敗："
              f"{type(_e).__name__}: {_e}")
        return None


def _yf_tickers(tickers) -> dict[str, str]:
    """`{正規化代號: 真的拿去打 yfinance 的代號}`。

    解不出來（兩個後綴都沒資料）→ **原樣保留正規化代號**，不從結果裡刪掉：
    刪掉會讓那一檔的市值悄悄從分母消失，而「這檔抓不到」該由**下游的覆蓋率欄位**
    誠實講出來，不是在這裡偷偷抹掉（§1）。
    """
    return {_t: (_resolve_yf_ticker(_t) or _t) for _t in dict.fromkeys(tickers)}


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
        imputed_value_twd: 那幾檔的市值合計（**元**）—— 「幾檔是估的」講不出嚴重度，
            「估掉的是多少錢」才講得出。
        coverage_pct: `(總市值 − imputed_value_twd) / 總市值 × 100`
            ＝ **Beta 是真的**那部分佔多少市值。
            ⚠️ 與 VaR 的 `coverage_pct` **不是同一種缺料**：VaR 那邊是
            「這幾檔沒進到計算裡」，這裡是「這幾檔進來了，但**用的是假設值**」。
            兩者都會讓數字看起來完整，但後者更隱蔽 —— 總額看不出任何缺口。
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
    imputed_value_twd: float = 0.0
    coverage_pct: float = 0.0
    valued_n: int = 0
    held_n: int = 0
    reconciled: bool = True
    reference_value_twd: float | None = None

    @property
    def partial(self) -> bool:
        """有持有列沒被納入（缺張數／均價／現價）—— 畫面必須講出來。"""
        return self.valued_n < self.held_n

    @property
    def full_coverage(self) -> bool:
        """**每一檔的 Beta 都是真的**（沒有任何一檔用 1.0 頂替）。

        `False` → 這個虧損金額裡有一部分是假設出來的，畫面必須把
        `coverage_pct` ／ `imputed_value_twd` ／ `beta_imputed` 講出來。
        """
        return bool(self.computed) and _is_full(self.coverage_pct)


def get_portfolio_stress(rows, *, drop_pct: float | None = None) -> StressResult:
    """戰情表列 → 壓力測試。**純讀不寫。**

    Args:
        rows: L3 `get_station_rows()` 的逐檔列（要有 `代號` / `held` / `張數` /
            `均價` / `現價`）。**觀察清單那些列會被排除**（沒有張數）。
        drop_pct: 假設跌幅（%）。`None` → L0 `PORTFOLIO_STRESS_TEST_DROP_PCT`。

    Returns:
        `StressResult`。算不出來 → `computed=False` ＋ `reason`（**不回 0 當答案**）。

    ⚠️ 逐檔會打一次 L1 `fetch_etf_info`（L2 `calc_portfolio_stress_test` 內部做的）
    ＋ 一次 `fetch_etf_price`（`_resolve_yf_ticker()` 判上市/上櫃後綴，FIX-1）——
    兩支在 L1 都有 `@st.cache_data`，本檔不自建第二層。
    ⚠️ **Beta 是估的那幾檔要看 `coverage_pct` / `imputed_value_twd`**：
    虧損總額**看不出任何缺口**，缺口只在這兩個欄位裡。
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
    _value = _value_by_ticker(_priced)
    # 上市 / 上櫃後綴：L2 內部會拿這個字串去 `fetch_etf_info` 查 Beta ——
    # 上櫃股補成 `.TW` 查不到，就會靜靜落進 `beta_imputed=1.0`（FIX-1）。
    _yf = _yf_tickers(_w)
    _back = {_v: _k for _k, _v in _yf.items()}      # L2 回來的名字 → 本檔的身分
    _res = calc_portfolio_stress_test(
        [{"ticker": _yf[_t], "actual_pct": _p} for _t, _p in _w.items()],
        _total, drop_pct=_drop)
    # ⚠️ 換回正規化代號再交給畫面：同一頁上「VaR 講 5314.TW、壓測講 5314.TWO」
    #    會被讀成兩檔股票。後綴是打上游用的，不是身分。
    _imputed = tuple(dict.fromkeys(_back.get(str(_t), str(_t))
                                   for _t in (_res.get("beta_imputed_tickers") or ())))
    _imputed_value = sum(_value.get(_t, 0.0) for _t in _imputed)
    return StressResult(
        computed=True, drop_pct=float(_res.get("drop_pct", _drop)),
        loss_twd=float(_res.get("total_loss", 0.0)),
        loss_pct=float(_res.get("loss_pct", 0.0)),
        warn=float(_res.get("loss_pct", 0.0)) > PORTFOLIO_STRESS_TEST_LOSS_WARN_PCT,
        warn_pct=float(PORTFOLIO_STRESS_TEST_LOSS_WARN_PCT),
        total_value_twd=_total,
        beta_imputed=_imputed,
        imputed_value_twd=_imputed_value,
        coverage_pct=(((_total - _imputed_value) / _total * 100.0)
                      if _total > 0 else 0.0),
        valued_n=len(_w), held_n=_held,
        reconciled=_ok, reference_value_twd=_ref)


# ══════════════════════════════════════════════════════════════════
# ⑥-d VaR（歷史模擬法 ＋ 參數法）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class VarResult:
    """組合的單日 / 月度風險值（**元**，正數＝可能虧掉多少）。

    ⚠️ **元金額的分子是 `covered_value_twd`，不是 `total_value_twd`**（FIX-2）。
    分位數是從「**真的抓得到日報酬、而且有共同交易日**」的那個子集算出來的；
    拿它去乘**全部**持股的市值，等於默認抓不到的那幾檔「報酬分布跟抓得到的那批一樣」
    —— 那是一次**沒有寫成 `fillna` 的補值**（§1），而且是最貴的一種：
    它不會出現在任何缺值統計裡，只會讓風險數字看起來剛好。
    改法（本檔選的是「(c) 混合」）：
      · 覆蓋率 100% → `covered_value_twd == total_value_twd`，數字與修前**完全相同**；
      · 覆蓋率 < 100% → 給**子集**的真實金額，並把 `coverage_pct` /
        `excluded_tickers` 一起帶出去，由畫面講清楚「這是哪一部分的風險」。
    為什麼**不**選「(b) 覆蓋率不足就整段拒答」：一檔抓不到就讓整格變成缺資料，
    會把一個**可以誠實表達**的結果丟掉；而子集 VaR 只要標明分母就是真話。
    `full_coverage` 屬性把這個判斷做成一個布林值，畫面不必自己比大小。

    Attributes:
        computed / reason: 同 `StressResult`。
        hist_95_twd / hist_99_twd: 歷史模擬法（近一年共同交易日的分位數）。
        param_95_twd / param_99_twd: 參數法（常態假設）。
        monthly_99_twd / monthly_99_pct: 月度 99%（√一個月交易日 近似）。
        warn: `monthly_99_pct` 是否超過 L0 門檻。
        covered_value_twd: **元金額真正的分子** —— 進到分布裡那幾檔的市值合計。
            上面五個元金額全部乘的是**它**，不是 `total_value_twd`（見 dataclass 說明）。
        coverage_pct: `covered_value_twd / total_value_twd × 100`。
            **100 以外的任何值畫面都必須講出來**，否則使用者會把一個子集的風險
            讀成整個組合的風險。
        excluded_tickers: 有市值、但**沒進到分布**的代號（抓不到價 / 無共同交易日）。
            與 `no_price` 的差別：`no_price` 是「一筆日報酬都抓不到」，
            本欄還包含「抓到了但被共同交易日對齊剔掉」的那幾檔。
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
    covered_value_twd: float = 0.0
    coverage_pct: float = 0.0
    excluded_tickers: tuple[str, ...] = ()
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

    @property
    def full_coverage(self) -> bool:
        """分布涵蓋了**全部**有市值的持股 → 這個 VaR 講的才是「整個組合」。

        `False` ＝ 這是**子集的** VaR。畫面必須把 `coverage_pct` ／
        `excluded_tickers` 講出來，不得只寫「你的組合 99% VaR ＝ X 元」。
        """
        return bool(self.computed) and _is_full(self.coverage_pct)


def _daily_returns(tickers) -> tuple[dict, list[str], list[str]]:
    """`{ticker: 日報酬 Series}` ＋ 沒有資料的代號 ＋ **拋了例外**的代號。

    §1：抓不到就**不放進去**（不是放一條 0% 報酬）—— 補 0 會稀釋波動、
    讓尾部 VaR 看起來比實際小，那正是「錯的數字比沒有數字更危險」。

    ⚠️ **「空資料」與「拋例外」分開回**（v3 §02 灰 vs 紅）：
    前者是「這一檔沒有那段歷史」（有效結果），後者是「取價那一層壞了」（真出錯）。
    L1 `fetch_etf_price` 大多數失敗會**自己吞掉並回空 DataFrame**，所以
    例外那一路不常走到 —— 但走到的時候它是唯一分得出「上游掛了」的訊號。

    ⚠️ **回傳的 key 一律是「正規化代號」（`.TW`）**，即使實際是用 `.TWO` 抓到的：
    下游 `align_portfolio_returns(rets, weights)` **靠 key 去查權重**，
    key 用 `.TWO`、權重用 `.TW` 會讓那一檔的權重查成 0 → 悄悄掉出組合。
    後綴只是「拿去打上游的字串」，**不是**這檔股票在本檔的身分。
    """
    _rets: dict = {}
    _missing: list[str] = []
    _errors: list[str] = []
    for _tk in tickers:
        try:
            _used, _df = _fetch_price_with_otc_fallback(_tk)     # .TW → 空才試 .TWO
        except Exception as _e:     # noqa: BLE001 — 單檔失敗不擋整組，但要記
            print(f"[portfolio_deep/var] {_tk} 價格抓取失敗："
                  f"{type(_e).__name__}: {_e}")
            _errors.append(f"{_tk}：{type(_e).__name__}: {_e}")
            continue
        if _df is None or getattr(_df, "empty", True) or "Close" not in _df:
            _missing.append(_tk)
            continue
        if _used and _used != _tk:
            print(f"[portfolio_deep/var] {_tk} 上市代號抓不到，改用上櫃 {_used}")
        _s = _df["Close"].pct_change().dropna()
        if len(_s) == 0:
            _missing.append(_tk)
            continue
        _rets[_tk] = _s
    return _rets, _missing, _errors


def _day_str(value) -> str:
    """`Timestamp` → `'YYYY-MM-DD'`；拿不到 → 空字串（**不編一個日期**）。

    ⚠️ **`None` 是正常的、不記 log**：沒有 limiter（只有一檔、或全員同時上市）
    時 L2 本來就回 `None`。把它記成錯誤等於捏造一個不存在的故障
    （v3 §02「未載入 ≠ 系統出錯」的同一條）。
    ⚠️ **其他型別轉不出來才是意外，一定要記**（§3.3：`except Exception` 至少要
    log ＋ 回 fail token）。空字串就是這裡的 fail token —— 但沒有 log 的話，
    「日期欄一直是空的」會安靜到沒有人查得出原因。
    """
    if value is None:
        return ""
    try:
        return value.strftime("%Y-%m-%d")
    except Exception as _e:     # noqa: BLE001 — 只是顯示用，拿不到就留空（但要說）
        print(f"[portfolio_deep] 日期格式化失敗（{type(value).__name__}）："
              f"{type(_e).__name__}: {_e}")
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

    ⚠️ **元金額乘的是 `covered_value_twd`（子集市值），不是全組合市值**（FIX-2）——
    完整理由見 `VarResult` 的 docstring。`coverage_pct < 100` 時畫面必須講。
    ⚠️ 逐檔取價走 `_resolve_yf_ticker()` 的後綴判定：上櫃股（`5314` / `8069` …）
    補成 `.TW` 抓回來是空的，少了它們**不會報錯，只會讓覆蓋率悄悄變低**。
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

    _value = _value_by_ticker(_priced)
    _rets, _missing, _errors = _daily_returns(list(_w))
    if not _rets:
        # 一檔都沒抓成：有例外 → `upstream_down` 為真（呼叫端判紅）；
        # 全是空資料 → 灰（「這幾檔沒有那段歷史」是有效結果）。
        return VarResult(reason=REASON_NO_RETURNS, no_price=tuple(_missing),
                         fetch_errors=tuple(_errors),
                         excluded_tickers=tuple(sorted(_w)), **_base)

    _al = align_portfolio_returns(_rets, _w)
    _port = _al.get("port_ret")
    _n_common = int(_al.get("n_common") or 0)
    _used = tuple(str(_t) for _t in (_al.get("tickers_used") or ()))
    # ⚠️ **覆蓋率**：分位數只講得動 `_used` 這幾檔，元金額的分子就只能是它們的市值。
    #    `_total` 仍原樣帶出去（`total_value_twd`），但它是**分母**不是分子。
    _covered = sum(_value.get(_t, 0.0) for _t in _used)
    _diag = {
        "n_common": _n_common, "n_union": int(_al.get("n_union") or 0),
        "dropped": int(_al.get("dropped") or 0),
        "limiter": str(_al.get("limiter") or ""),
        "limiter_start": _day_str(_al.get("limiter_start")),
        "tickers_used": _used,
        "no_price": tuple(_missing),
        "fetch_errors": tuple(_errors),
        "covered_value_twd": _covered,
        "coverage_pct": (_covered / _total * 100.0) if _total > 0 else 0.0,
        "excluded_tickers": tuple(sorted(set(_w) - set(_used))),
    }
    if _port is None or len(_port) == 0:
        return VarResult(reason=REASON_NO_COMMON_DAYS, **_base, **_diag)
    if len(_port) < _min_days:
        return VarResult(reason=REASON_SHORT_SAMPLE, **_base, **_diag)
    if _covered <= 0:
        # 進了分布卻算不出市值（理論上不會走到 —— 權重就是從市值來的）。
        # 走到了就是上面某個對映壞了，**寧可不給數字也不拿 `_total` 頂替**（§1）。
        print("[portfolio_deep/var] 進入分布的代號查不到市值："
              f"used={_used} 有市值的={sorted(_value)}")
        return VarResult(reason=REASON_NO_COVERED_VALUE, **_base, **_diag)

    # 歷史模擬法：近一年共同日的最差分位數 ×**納入分布那幾檔**的市值（元）。
    _h95 = abs(float(_port.quantile(PORTFOLIO_VAR_95_PERCENTILE)) * _covered)
    _h99 = abs(float(_port.quantile(PORTFOLIO_VAR_99_PERCENTILE)) * _covered)
    # 參數法：常態假設 μ − zσ（z 取自 L0，§3.3）。與歷史法並陳（肥尾時歷史法通常更保守）。
    _mu, _sig = float(_port.mean()), float(_port.std())
    _p95 = abs((_mu - VAR_Z_SCORE_95 * _sig) * _covered)
    _p99 = abs((_mu - VAR_Z_SCORE_99 * _sig) * _covered)
    # 月度 99%：√（一個月交易日）近似，係數與樣本下限**同一個數字**（見檔頭常數）。
    _m99 = _h99 * math.sqrt(TRADING_DAYS_PER_MONTH)
    # ⚠️ 百分比的分母也是 `_covered`（**與分子同一批持股**）—— 拿子集的虧損去除
    #    全組合市值會系統性低估這個比率，那正是本次要修掉的口徑混用。
    _m99_pct = (_m99 / _covered * 100.0) if _covered > 0 else 0.0
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
        excluded_tickers: 有張數、但**完全沒進到 `gross_twd`** 的代號
            ＝ `overseas` ＋ 上游直接略過的（例如四捨五入後股數為 0）。
            ⚠️ 少了這一欄，「海外那幾檔的配息沒被算進去」這件事只會表現成
            **總額偏小**，而偏小的總額看起來跟正確的總額一模一樣。
        coverage_pct: 納入計算的檔數 / 有張數的檔數 × 100。
            ⚠️ **是「檔數」口徑不是「金額」口徑** —— 配息這一路刻意不要求均價／現價
            （見 `_shares_of()`），所以本檔手上根本沒有每一檔的市值，
            **不假裝有金額權重**（§1 寧可講清楚口徑，不給一個看起來更精緻的假數字）。
        no_payout_tickers: 納入計算、但近一年 **0 筆**配息的代號。
            ⚠️ 上游 `_recent_payments_twd()` 把「**真的沒配息**」與「**抓不到**」
            回成同一個空序列，**本層分不出來** —— 所以這一欄的語意只能是
            「這幾檔貢獻 0 元」，畫面**不得**把它寫成「這幾檔沒有配息」。
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
    excluded_tickers: tuple[str, ...] = ()
    no_payout_tickers: tuple[str, ...] = ()
    coverage_pct: float = 0.0
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

    @property
    def full_coverage(self) -> bool:
        """**每一檔有張數的持股都進了這個總額**（沒有被排除在外的）。

        `False` → 這是**一部分持股**的配息，畫面必須把 `coverage_pct` ／
        `excluded_tickers` 講出來，不得只寫「你的組合近一年配息 X 元」。
        """
        return bool(self.computed) and _is_full(self.coverage_pct)


def _shares_of(rows) -> list[dict]:
    """持有列 → `[{ticker, shares}]`。**張 → 股 就在這一步**
    （呼叫 `_lot_to_shares()`，本檔唯一的乘法點 —— 這裡自己不乘）。

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

    ⚠️ 逐檔會打一次 L1 `fetch_etf_dividends`（L3 `dividend_tax_service` 內部做的）
    ＋ 一次 `fetch_etf_price`（後綴判定，FIX-1；上櫃股用 `.TW` 抓配息會回空序列，
    而空序列在上游等於「近一年沒有配息」）。
    ⚠️ **海外標的不算進 `gross_twd`**（§4.6 不混算）→ 看 `coverage_pct` /
    `excluded_tickers`，不要把這個總額讀成「整個組合的年配息」。
    ⚠️ **上游 summary 缺欄 → `computed=False`**（`REASON_DIVIDEND_CONTRACT_DRIFT`），
    不補 0：補 0 之後「契約漂移」會長得跟「你真的沒有配息」一模一樣。
    """
    from src.services.dividend_tax_service import (        # L3 → L3
        get_dividend_tax_view,
    )

    _held = _held_n(rows)
    _shares = _shares_of(rows)
    if not _shares:
        return DividendCashResult(reason=REASON_NO_LOTS_ROWS, held_n=_held)

    # 上市 / 上櫃後綴：L3 `dividend_tax_service` 會拿這個字串去 `fetch_etf_dividends`
    # —— 上櫃股補成 `.TW` 抓回空序列，會被算成「近一年沒有配息」（FIX-1）。
    _yf = _yf_tickers(_s["ticker"] for _s in _shares)
    _back = {_v: _k for _k, _v in _yf.items()}      # 上游回來的名字 → 本檔的身分
    _base = {"lots_n": len(_shares), "held_n": _held,
             "shares_total": sum(_s["shares"] for _s in _shares),
             "income_tax_included": False}

    # ⚠️ `marginal_rate=None` 是**刻意的**，不是忘了傳 —— 見 dataclass docstring。
    _view = get_dividend_tax_view(
        [{"ticker": _yf[_s["ticker"]], "shares": _s["shares"]} for _s in _shares],
        marginal_rate=None)
    _summary = ((_view or {}).get("summary")
                if isinstance(_view, dict) else None) or {}
    # §3.3 契約檢查：三個金額欄位**缺一個就不給數字**。原本是
    # `float(_summary.get("gross") or 0.0)` —— 上游改欄名時會靜靜變成 0 元，
    # 而 `computed=True` 照樣帶出去 → 畫面顯示「近一年配息 0 元」，
    # 看起來跟「你真的沒有配息」一模一樣（§1：錯的數字比沒有數字更危險）。
    _amounts = {_k: _num(_summary.get(_k))
                for _k in ("gross", "nhi_premium", "net_after_nhi")}
    _lost = sorted(_k for _k, _v in _amounts.items() if _v is None)
    if _lost:
        print(f"[portfolio_deep/dividend] summary 欄位缺漏或非數值：{_lost}"
              f"（拿到的 keys={sorted(_summary)}）")
        return DividendCashResult(
            reason=f"{REASON_DIVIDEND_CONTRACT_DRIFT}（缺：{'、'.join(_lost)}）",
            **_base)

    _per = tuple(dict(_p) for _p in ((_view or {}).get("per_etf") or ()))
    for _p in _per:                     # 後綴換回本檔的身分（同壓測的理由）
        _p["代號"] = _back.get(str(_p.get("代號")), _p.get("代號"))
    _overseas = tuple(_back.get(str(_t), str(_t))
                      for _t in ((_view or {}).get("overseas") or ()))
    # 覆蓋率：有張數的每一檔，要嘛出現在 `per_etf`（算進總額）、要嘛被標成海外
    # （**沒有**算進總額）、要嘛被上游整筆略過（股數四捨五入成 0）。
    # 後兩者都不在 `gross_twd` 裡 —— 那正是「部分沒算到卻照樣給總額」。
    _counted = tuple(str(_p.get("代號")) for _p in _per)
    _accounted = set(_counted) | set(_overseas)
    _excluded = tuple(sorted(set(_overseas)
                             | {_s["ticker"] for _s in _shares
                                if _s["ticker"] not in _accounted}))
    return DividendCashResult(
        computed=True,
        gross_twd=_amounts["gross"],
        nhi_twd=_amounts["nhi_premium"],
        net_after_nhi_twd=_amounts["net_after_nhi"],
        payouts_n=sum(int(_p.get("配息筆數") or 0) for _p in _per),
        per_ticker=_per,
        overseas=_overseas,
        excluded_tickers=_excluded,
        no_payout_tickers=tuple(str(_p.get("代號")) for _p in _per
                                if not int(_p.get("配息筆數") or 0)),
        coverage_pct=(len(_counted) / len(_shares) * 100.0) if _shares else 0.0,
        tw_n=int((_view or {}).get("n_tw") or 0),
        **_base)


#: 本檔 public 介面（`from ... import *` 不是本 repo 的用法，這裡只作自我說明）。
__all__ = [
    "DividendCashResult", "StressResult", "VarResult",
    "get_dividend_cash_flow", "get_portfolio_stress", "get_portfolio_var",
    "priced_rows",
    "REASON_DIVIDEND_CONTRACT_DRIFT", "REASON_NO_COMMON_DAYS",
    "REASON_NO_COVERED_VALUE", "REASON_NO_LOTS_ROWS", "REASON_NO_PRICED_ROWS",
    "REASON_NO_RETURNS", "REASON_SHORT_SAMPLE",
    "TRADING_DAYS_PER_MONTH",
]
