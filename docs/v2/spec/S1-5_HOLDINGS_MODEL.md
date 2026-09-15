# 階段1 交付物 #5 — 持倉與交易資料模型（`v2_transactions` / `v2_holdings`）

> **狀態**：設計文件。**未建表、未寫 migration、未改動任何 repo、未執行任何 Google Sheets 寫入。**
> **量測日**：2026-09-14。本檔所有「實測」標記均為本輪親自跑過的指令結果。
> **§-2 規則 6**：本檔**全部判定由本組單組產出，未經第二組獨立複驗** —— 屬待驗事項，
> 不得被引用為「已查證的事實」去支撐下一步動工。逐項實測事實與由事實推出的判定，已在文中分開標記。

---

## 0. 先講三件事實（設計的地基，全部本輪實測）

| # | 實測事實 | 指令 / 位置 |
|---|---|---|
| F1 | `v2_transactions` / `v2_holdings` **兩個 repo 全域 0 命中** —— 是全新表，不是改既有表 | `grep -rn "v2_transactions\|v2_holdings" --include=*.py --include=*.md .`（兩 repo 各跑一次） |
| F2 | 台股 `portfolios` 分頁 header 為 `['name','ticker','lots','avg_price','updated_at']`，`updated_at` 在**最後一欄（index 4）** | `src/data/portfolio/gsheet_portfolio.py:82` |
| F3 | 基金站已有完整的 append-only 流水 + 移動加權平均實作 | `models/ledger.py`（`Transaction` / `FundPosition`）、`services/ledger_service.py`（`subscribe` / `dividend_cash` / `dividend_reinvest` / `Switch`） |

**推論（本組判定）**：基金站的 `Transaction` 五型（`subscribe` / `dividend_cash` / `dividend_reinvest` /
`switch_out` / `switch_in`）已經是 `v2_transactions` 的原型。本設計**不重新發明**，而是把它
**收斂成母法要求的四型**（買進／賣出／除息／匯入）＋ 補上基金站缺的「賣出已實現損益」，
再補上台股站缺的「幣別 / 買入匯率」。

---

## 1. `v2_transactions` 表結構

### 1.0 三條貫穿全表的鐵律

1. **欄名必帶單位**（`CLAUDE.md §4.1`；`shared/signal_thresholds.py:10` 自陳慣例 `_PCT / _RATIO / _DAYS / _LOTS / _TWD`）。
   本表新增兩個後綴：`_native`（該筆交易的**原幣**）、`_twd`（新台幣）。
2. ⛔ **`lots` / 張 一律不得出現在本表。** 數量欄只有 `quantity_units`，單位是**股（shares）／基金單位數**。
   - **理由（實測）**：`張→股` 的 `× SHARES_PER_LOT` 全站**至少三處**
     （`src/services/portfolio_deep_service.py::_lot_to_shares`、
     `src/services/dividend_station_service.py:887`、`src/compute/sector_flow.py:158`
     —— 該檔 docstring 自陳並有 `tests/test_p04_hold_view.py::TestTheLotToShareClaimIsMeasurable` 現場掃描守衛），
     且 `src/ui/etf/etf_tab_portfolio.py:282` 的 `_shares = _lots * 1000` **對美股 ETF 也無條件乘**。
   - **設計決定**：張→股 只在 **UI 輸入邊界換算一次**，寫進本表就已經是股。新資料從源頭消滅這個陷阱。
3. **原幣為權威、TWD 為衍生。** 本表存 `*_native` ＋ 一個匯率欄；**不存** `*_twd` 當唯一真相
   （存了就無法在匯率來源更正時重算，且會製造第二真相源，違 §2.1 SSOT）。

### 1.1 欄位表

型別採「邏輯型別」寫法；落到 Google Sheets 皆為字串/數字 cell，落到 parquet 依括號內 dtype。

#### A. 身分與路由（5 欄）

| 欄名 | 型別 | 單位 | 必填 | 說明 |
|---|---|---|---|---|
| `txn_id` | str (uuid4/ULID) | — | ✅ | 主鍵。**冪等鍵**（§5 冪等性）：重複匯入同一 id 直接略過，不產生重複筆 |
| `portfolio_name` | str | — | ✅ | 對應現有 `portfolios.name`（多組合共用一張表的既有慣例，`gsheet_portfolio.py:82` 同 pattern） |
| `asset_class` | enum | — | ✅ | **母法指定的嚴格區分欄**。值域 `stock` / `etf` / `fund`。⛔ 不得新增第四值而不同步更新 `v2_holdings` 聚合器 |
| `market` | enum | — | ✅ | `TW` / `US` / `OFFSHORE`。**與 `asset_class` 正交**（ETF 可以是 TW 也可以是 US）。存在理由見 §1.3 |
| `ticker` | str | — | ✅ | **必須帶市場後綴**（`0050.TW` / `BND`）。寫入前一律過 `normalize_etf_ticker`，且**與 `market` 交叉驗證**（見 §3.4） |

#### B. 交易本體（6 欄）

| 欄名 | 型別 | 單位 | 必填 | 說明 |
|---|---|---|---|---|
| `txn_type` | enum | — | ✅ | `BUY` / `SELL` / `DIVIDEND` / `TRANSFER_IN`（母法四型） |
| `trade_date` | date (ISO `YYYY-MM-DD`) | TW 曆日 | ⚠️ 見註 | 成交日。**遷移產生的期初列可為空**（§4.3 標缺） |
| `settle_date` | date | TW 曆日 | ➖ | 交割日。台股 T+2、美股 T+1。**目前不參與任何計算**，只存不用（§8.1 step 6：先不做，等真的需要再加） |
| `seq_no` | int | — | ✅ | **同日交易的決定性排序鍵**。理由見 §2.5（同日買賣順序會改變已實現損益） |
| `quantity_units` | Decimal(28,8) > 0 | **股 / 基金單位數** | ⚠️ 見註 | `DIVIDEND` 且 `dividend_treatment != 'reinvest'` 時為 0；其餘 > 0 |
| `price_native_per_unit` | Decimal(28,8) ≥ 0 | 原幣/股 | ⚠️ 見註 | 成交單價（未含費）。`DIVIDEND` 現金型時為 0 |

#### C. 金額與費用（4 欄，全為**原幣**）

| 欄名 | 型別 | 單位 | 必填 | 說明 |
|---|---|---|---|---|
| `gross_amount_native` | Decimal(28,8) ≥ 0 | 原幣 | ✅ | `= quantity_units × price_native_per_unit`（除息列為配息總額）。**冗餘存放但必須自洽**（§4.3 對帳，見 §3.3 不變量 I-1） |
| `fee_native` | Decimal(28,8) ≥ 0 | 原幣 | ✅（可 0） | 手續費 |
| `tax_native` | Decimal(28,8) ≥ 0 | 原幣 | ✅（可 0） | 證交稅 / 股利扣繳 / 二代健保補充保費 |
| `net_amount_native` | Decimal(28,8) **有號** | 原幣 | ✅ | **使用者口袋的實際淨流動**。BUY 為負、SELL/DIVIDEND(現金) 為正、TRANSFER_IN 為 0。見 §3.3 I-2 |

#### D. 幣別與匯率（5 欄 —— 台股站現在完全沒有的部分）

| 欄名 | 型別 | 單位 | 必填 | 說明 |
|---|---|---|---|---|
| `currency_code` | str (ISO-4217) | — | ✅ | `TWD` / `USD`。⛔ **不得由 ticker 後綴推斷後靜默寫入**（見 §3.4） |
| `fx_twd_per_native` | Decimal(18,8) > 0 \| **NULL** | **TWD / 1 單位原幣** | ➖ | **欄名即方向**：TWD per 1 native。設計成可 NULL 就是為了 §4.3 的「回填不了就標缺」 |
| `fx_rate_source` | str | — | ⚠️ | `user` / `broker_statement` / `yahoo:TWD=X` / `fred:DEXTAUS` / `MISSING`。§2.2 provenance |
| `fx_rate_as_of_date` | date | — | ⚠️ | 該匯率**歸屬日**（≠ 抓取日）。§2.3 PIT |
| `fx_is_imputed` | bool | — | ✅ | §1 旗標。**production 路徑恆為 `False`** —— 本設計不提供任何推估匯率的路徑（見 §3.5） |

> `currency_code == 'TWD'` 時 `fx_twd_per_native` 恆為 `1.0`、`fx_rate_source='identity'`。
> 這**不是**推估，是定義。

#### E. 除息專用（3 欄）

| 欄名 | 型別 | 單位 | 必填 | 說明 |
|---|---|---|---|---|
| `dividend_treatment` | enum \| NULL | — | ⚠️ | `cash` / `cost_reduction` / `reinvest`。**僅 `txn_type='DIVIDEND'` 時非空**；三者互斥，一筆配息只能選一 |
| `div_per_unit_native` | Decimal(28,8) ≥ 0 \| NULL | 原幣/股 | ➖ | 每股配息。供對帳（I-3）與「除權息前後」稽核 |
| `linked_txn_id` | str \| NULL | — | ➖ | 配息再投資的配對鍵（見 §2.4）。也用於「錯帳沖銷」配對 |

#### F. 血緣與生命週期（5 欄，§2.2）

| 欄名 | 型別 | 單位 | 必填 | 說明 |
|---|---|---|---|---|
| `source` | str | — | ✅ | `manual_ui` / `migration_v1_snapshot` / `broker_csv:<券商>` / `gsheet_paste` |
| `entered_at_utc` | datetime (UTC) | — | ✅ | 建檔時間。**與 `trade_date` 嚴格區分** —— 現行 `updated_at` 混用兩者正是 §4.3 回填不了的根因 |
| `entry_method` | enum | — | ✅ | `typed` / `imported` / `derived`（`derived` = 由另一筆推導，如再投資的 BUG 腿） |
| `is_void` | bool | — | ✅ | **Append-only 更正機制**：錯帳不刪不改，寫一筆 `is_void=True` 的沖銷列並用 `linked_txn_id` 指回原列 |
| `note` | str | — | ➖ | 自由文字 |

**合計 28 欄。**

> ⚠️ **實作卡點（實測，非推論）**：`gsheet_portfolio._col_letter()` 明文
> `if not 1 <= n_cols <= 26: raise ValueError`（`gsheet_portfolio.py:214-222`），
> 而 `_get_worksheet` 用它算 header 更新範圍。**28 欄的 worksheet 用現行 `_get_worksheet` 會直接 raise。**
> → 實作階段必須先把 `_col_letter` 擴成雙字母（A..ZZ）**或**讓 v2 走獨立的 worksheet helper。
> 這是本設計對現有程式碼的**唯一硬相依修改點**。

### 1.2 四種交易類型各自用到哪些欄

`✅`＝必填、`○`＝選填、`—`＝必須留空/0、`⚠️`＝有條件

| 欄 | `BUY` | `SELL` | `DIVIDEND` | `TRANSFER_IN` |
|---|---|---|---|---|
| `txn_id` / `portfolio_name` / `asset_class` / `market` / `ticker` | ✅ | ✅ | ✅ | ✅ |
| `trade_date` | ✅ | ✅ | ✅（除息基準日） | ⚠️ 期初列可空 |
| `seq_no` | ✅ | ✅ | ✅ | ✅ |
| `quantity_units` | ✅ >0 | ✅ >0 | ⚠️ `reinvest` 時 >0，否則 0 | ✅ >0 |
| `price_native_per_unit` | ✅ >0 | ✅ >0 | ⚠️ `reinvest` 時＝再投資價，否則 0 | ✅ >0（載入成本價） |
| `gross_amount_native` | ✅ | ✅ | ✅（配息總額） | ✅ |
| `fee_native` | ✅ | ✅ | ○ | — （0） |
| `tax_native` | ✅ | ✅ | ○（扣繳） | — （0） |
| `net_amount_native` | ✅ **負** | ✅ **正** | ⚠️ `cash` 正 / `cost_reduction` 正 / `reinvest` **0** | — （0） |
| `currency_code` | ✅ | ✅ | ✅ | ✅ |
| `fx_twd_per_native` | ✅ | ✅ | ✅ | ⚠️ **允許 NULL**（唯一允許的型別） |
| `fx_rate_source` / `fx_rate_as_of_date` | ✅ | ✅ | ✅ | ⚠️ NULL 時填 `MISSING` |
| `fx_is_imputed` | ✅ False | ✅ False | ✅ False | ✅ False |
| `dividend_treatment` | — | — | ✅ | — |
| `div_per_unit_native` | — | — | ○ | — |
| `linked_txn_id` | ⚠️ 再投資腿必填 | ○ | ⚠️ 再投資腿必填 | — |
| `source` / `entered_at_utc` / `entry_method` / `is_void` | ✅ | ✅ | ✅ | ✅ |

**`TRANSFER_IN`（匯入）的語意**（本組判定）：**部位從系統外進來，沒有對應的現金流出。**
涵蓋三種真實情境 —— (a) 券商轉倉、(b) 繼承/贈與、(c) **本次遷移產生的期初餘額**。
它與 `BUY` 的數學完全相同（見 §2.2），**唯一差別是 `net_amount_native ≡ 0`**（不計入 XIRR 現金流）
以及**允許 `fx_twd_per_native` 為 NULL**。

### 1.3 為什麼 `market` 要跟 `asset_class` 分開

母法只釘死 `asset_class`。本組**額外**加 `market`，理由是實測發現的 32× 事故根因：

- `src/compute/etf/portfolio_fx.py::holding_currency` 的 docstring 自陳
  「唯一可得的線索是代號後綴」「使用者少打 `.TW` → 換匯後金額**放大約 32 倍**，屬已知誤判方向」；
- `tests/test_b1a_portfolio_fx.py:122` 把這個行為**釘成測試**：`holding_currency('2330') == 'USD'`。

→ 只要幣別是**推斷**來的，這個事故就永遠可能重演。加 `market` 是為了讓
`currency_code` 有**第二個獨立來源**可以交叉驗證（§4.3 重算對帳），而不是繼續靠單一字串後綴。

---

## 2. `v2_holdings` 聚合邏輯（移動加權平均，寫成算式）

### 2.0 狀態變數與符號

對每一個 key `(portfolio_name, asset_class, ticker)` 維護：

| 符號 | `v2_holdings` 欄名 | 單位 | 意義 |
|---|---|---|---|
| $q$ | `qty_units` | 股/單位 | 持有數量 |
| $C$ | `avg_cost_native_per_unit` | 原幣/股 | **原幣**移動加權平均成本（**含**買進費稅） |
| $B$ | `cost_basis_twd` | TWD | **台幣**成本基底（**一等公民狀態，不是衍生值**） |
| $F$ | `avg_fx_twd_per_native` | TWD/原幣 | 平均買入匯率 —— **衍生欄**：$F \equiv \dfrac{B}{q \cdot C}$ |
| $R$ | `realized_pnl_twd` | TWD | 累計已實現損益 |
| $D$ | `dividend_cash_twd_cum` | TWD | 累計現金配息（TWD） |
| $C_{div}$ | `avg_cost_native_per_unit_after_div` | 原幣/股 | 含息成本（基金站 CHUBB 相容欄，**不參與**任何全站總計） |

### 2.1 ⭐ 最重要的一個設計決定：`F` 是衍生值，不是獨立平均

**基金站現行做法（實測 `services/ledger_service.py:84-86`）是把 `fx_avg` 用「單位數」加權**：

$$F' = \frac{q\cdot F + \Delta q\cdot f}{q + \Delta q}$$

然後用 `net_investment_twd = cost_unit × units × fx_avg`（`models/ledger.py:69-71`）回推台幣成本。

**這個做法在「單價與匯率同時變動」時不守恆**（本組數值反例，可手算複驗）：

- 第一筆：100 單位 @ nav 10、fx 30 → 真實台幣成本 $100\times10\times30=30{,}000$
- 第二筆：100 單位 @ nav 20、fx 32 → 真實台幣成本 $100\times20\times32=64{,}000$
- **真值合計 94,000**
- 單位數加權：$C=\frac{100\cdot10+100\cdot20}{200}=15$，$F=\frac{100\cdot30+100\cdot32}{200}=31$
- $\Rightarrow q\cdot C\cdot F = 200\times15\times31 = \mathbf{93{,}000}$ ❌ **短少 1,000（1.06%）**

根因是 $\mathbb{E}[XY]\neq\mathbb{E}[X]\mathbb{E}[Y]$ —— 三個各自平均的數相乘會吃掉共變異項。

**本設計的解法**：把 $B$（台幣成本）當**累加的一等狀態**，$F$ 改為**輸出時反推**：

$$\boxed{F \equiv \frac{B}{q\cdot C}}\qquad\Longrightarrow\qquad q\cdot C\cdot F \equiv B \text{（恆等，無誤差）}$$

等價於把匯率用**原幣成本金額**加權（而非單位數加權）：

$$F' = \frac{q C F + \Delta q\, c_{\text{eff}}\, f}{q C + \Delta q\, c_{\text{eff}}}$$

上例代入：$F' = \frac{30000 + 64000}{100\cdot10 + 100\cdot20} = \frac{94000}{3000} = 31.33\overline{3}$，
$q\cdot C\cdot F' = 200\times15\times31.333 = 94{,}000$ ✅。

> ⚠️ **這是與基金站現行實作的實質差異，屬母法層級議題** → 已列入 §6 修正提案 P-1。

### 2.2 `BUY` / `TRANSFER_IN`

令 $\Delta q$ = `quantity_units`、$p$ = `price_native_per_unit`、$\phi$ = `fee_native`、$\tau$ = `tax_native`、$f$ = `fx_twd_per_native`。

$$
\begin{aligned}
A_{\text{native}} &= \Delta q\cdot p + \phi + \tau &&\text{(取得成本，原幣，費稅滾入)}\\[2pt]
c_{\text{eff}} &= A_{\text{native}}\,/\,\Delta q &&\text{(本筆有效單位成本)}\\[2pt]
q' &= q + \Delta q\\[2pt]
C' &= \frac{q\cdot C + \Delta q\cdot c_{\text{eff}}}{q'} &&\text{(原幣移動加權平均)}\\[2pt]
B' &= B + A_{\text{native}}\cdot f &&\text{(台幣成本累加，精確)}\\[2pt]
C'_{div} &= \frac{q\cdot C_{div} + \Delta q\cdot c_{\text{eff}}}{q'}\\[2pt]
R' &= R,\qquad D' = D
\end{aligned}
$$

**`TRANSFER_IN` 且 $f$ = NULL 時**（遷移期初列）：

$$B' = \mathrm{NaN}\quad\text{並置 } \texttt{cost\_twd\_is\_partial}=\mathbf{True}$$

⛔ **不得**以任何方式補上 $f$（§1）。NaN 具**傳染性**：一旦某部位的 $B$ 為 NaN，
該部位的 `unrealized_pnl_twd` / `cost_basis_twd` / `avg_fx` 一律輸出 NaN，
畫面顯示「—（買入匯率未知）」，**不得顯示 0**（0 會讓報酬率變成 +∞%）。

### 2.3 `SELL`

$$
\begin{aligned}
\text{前置檢查:}\quad &\Delta q \le q + \varepsilon \;\; \text{否則 } \mathbf{raise}\;\text{（§1：不 clamp、不允許負持股）}\\[4pt]
P_{\text{native}} &= \Delta q\cdot p - \phi - \tau &&\text{(淨賣出價款，原幣)}\\[2pt]
K_{\text{twd}} &= B\cdot\frac{\Delta q}{q} \;\;\left(= \Delta q\cdot C\cdot F\right) &&\text{(按比例解除的台幣成本)}\\[4pt]
\Delta R &= P_{\text{native}}\cdot f - K_{\text{twd}} &&\text{(本筆已實現損益，TWD)}\\[6pt]
q' &= q - \Delta q\\
C' &= C,\qquad C'_{div} = C_{div} &&\text{(移動加權平均：賣出不動單位成本)}\\
B' &= B - K_{\text{twd}}\\
R' &= R + \Delta R,\qquad D'=D
\end{aligned}
$$

**$F$ 在賣出後不變**（可驗證，非宣稱）：
$$F' = \frac{B'}{q'C'} = \frac{B(1-\Delta q/q)}{(q-\Delta q)C} = \frac{B(q-\Delta q)/q}{(q-\Delta q)C} = \frac{B}{qC} = F \;\checkmark$$

**已實現損益的價／匯拆解**（這是台股站現在「明文匯兌損益故不估」的直接解法）：

$$
\underbrace{\left(\Delta q\cdot p - \phi - \tau - \Delta q\cdot C\right)\cdot f}_{\text{價格損益 }\Delta R_{\text{price}}}
\;+\;
\underbrace{\Delta q\cdot C\cdot\left(f - F\right)}_{\text{匯兌損益 }\Delta R_{\text{fx}}}
\;=\;\Delta R
$$

代數驗證：$\Delta q p f - \phi f-\tau f - \Delta q C f + \Delta q C f - \Delta q C F = P_{\text{native}}f - \Delta q C F = P_{\text{native}}f - K_{\text{twd}}$ ✅

→ `v2_holdings` 因此可以多出 `realized_fx_pnl_twd` 與 `realized_price_pnl_twd` 兩欄，
**而且是算出來的，不是估的**。⚠️ 但只有在 $F$ 非 NaN 時才成立；遷移期初列的部位拿不到拆解，
兩欄一律 NaN（見 §4.3）。

**$q' = 0$ 的邊界**：$B'$ 應為 0（浮點上以 `math.isclose(B', 0, abs_tol=1e-6)` 判定，
不過就 raise 並 log 差額）。$C'$ / $F$ **保留最後值不歸零** —— 歸零會讓後續 `TRANSFER_IN`
再買回時的加權起點錯誤，且會抹掉「這檔曾經的平均成本」這個事實。
部位標 `is_closed=True`，**仍留在 `v2_holdings`**（否則已實現損益會憑空消失）。
⚠️ 對照實測：現行 `parse_portfolio_records` 是 `if lots <= 0 ... continue`（`gsheet_portfolio.py:297`）
—— 清倉即整列消失。v2 **不沿用**這個行為。

### 2.4 `DIVIDEND` —— 三種處理，互斥

#### (a) `cash`（現金入帳）

$$
D_{\text{net}} = \underbrace{\Delta q_{\text{held}}\cdot d}_{\text{gross}} - \tau - \phi,
\qquad
\begin{cases}
q'=q,\;C'=C,\;B'=B,\;F'=F &\text{(部位完全不動)}\\
D' = D + D_{\text{net}}\cdot f\\
\text{XIRR 現金流}: \;+\,D_{\text{net}}\cdot f \;\text{於 } \texttt{trade\_date}
\end{cases}
$$

#### (b) `cost_reduction`（成本扣減）

$$
\begin{aligned}
q' &= q &&\text{(數量不動)}\\
C' &= \max\!\left(0,\; C - \frac{D_{\text{net}}}{q}\right) &&\text{(原幣單位成本下修)}\\
B' &= \max\!\left(0,\; B - D_{\text{net}}\cdot f\right) &&\text{⭐ 用}\textbf{本筆匯率 } f \textbf{ 扣，不是 } F\\
F' &= \frac{B'}{q\,C'} &&\text{(自動漂移 —— 這是對的，見下)}\\
D' &= D &&\text{(不計入現金配息累計，避免雙重計算)}\\
\text{XIRR 現金流}&: \;+\,D_{\text{net}}\cdot f &&\text{(錢確實進了口袋，仍是現金流)}
\end{aligned}
$$

> ⭐ **為什麼扣 $B$ 要用 $f$ 而不是 $F$**：配息是在**除息日**那天換成台幣的，
> 不是在**當初買進**那天。用 $F$ 扣等於假裝配息也用買入匯率結匯 —— 那是捏造一個沒發生的換匯。
> 扣完後 $F'$ 會自然偏離 $F$，**這個偏離本身就是真實的匯率資訊**，不該被抹平。

> **地板保護（`cost_floor_hit`）**：若 $C - D_{\text{net}}/q < 0$（高配息 ETF 長年持有後真的會發生），
> 溢出的部分 $\left(D_{\text{net}} - qC\right)\cdot f$ **轉入 $R$（已實現損益）**，並置
> `cost_floor_hit=True` ＋ 寫 log（§1：顯式處理 + 寫 log + 帶旗標）。
> ⛔ **不得**讓 $C$ 或 $B$ 變成負數（負成本會讓報酬率無意義）。
> **$C'=0$ 時 $F'=0/0$** → 定義 $F' := F$ 且強制 $B'=0$（此為定義，非推估；須在 code 註解標明）。

#### (c) `reinvest`（配息再投資 —— 滾入邏輯）

**設計決定：不寫第二套加權平均。** 一筆再投資落地為**兩列 append-only、以 `linked_txn_id` 配對**：

| 列 | `txn_type` | `dividend_treatment` | `quantity_units` | `net_amount_native` | `entry_method` |
|---|---|---|---|---|---|
| ① | `DIVIDEND` | `reinvest` | 0 | $+D_{\text{net}}$ | `typed` |
| ② | `BUY` | NULL | $\Delta q_{\text{re}}$ | $-D_{\text{net}}$ | `derived` |

$$
\Delta q_{\text{re}} = \frac{D_{\text{net}}}{p_{\text{re}}}
\qquad(p_{\text{re}} = \text{再投資買進價，原幣})
$$

② 之後**完全走 §2.2 的 BUY 算式**，滾入結果即：

$$
C' = \frac{q\cdot C + D_{\text{net}}/p_{\text{re}}\cdot p_{\text{re}}}{q + D_{\text{net}}/p_{\text{re}}}
   = \frac{q\,C + D_{\text{net}}}{q + D_{\text{net}}/p_{\text{re}}},
\qquad
B' = B + D_{\text{net}}\cdot f
$$

**兩列的好處（三個，都是實質的）**：
1. **加權平均只有一份實作** —— 不會出現「再投資的滾入」和「一般買進」算法漂移（§2.1 SSOT）。
2. **XIRR 自動正確** —— ①的 $+D$ 與 ②的 $-D$ 在同一天相互抵銷，淨外部現金流 = 0，
   與基金站 `calculate_xirr` 對 `dividend_reinvest` 記 0 現金流的處置一致（`ledger_service.py:478`）。
3. **可稽核** —— 使用者在流水上看得到「我領了多少、用什麼價買回多少股」，不是一個黑箱的數字變動。

⛔ **互斥性是硬規則**：同一筆配息**只能**選 (a)(b)(c) 之一。
`cash` + `cost_reduction` 同時做＝配息被計兩次（一次進 $D$、一次減 $B$）→ 總報酬虛增。
須由 §3.3 不變量 I-4 機械擋住。

### 2.5 聚合順序（同日順序會改結果，必須釘死）

**排序鍵**：`(trade_date ASC NULLS FIRST, seq_no ASC, txn_id ASC)`

- `NULLS FIRST` —— 遷移產生的期初列（`trade_date` 空）永遠排最前，這是它的語意。
- **為什麼需要 `seq_no`（本組判定）**：移動加權平均下，同日「先買後賣」與「先賣後買」的
  已實現損益**不同**（先買會拉動 $C$，改變賣出時解除的成本）。沒有決定性排序鍵 ⇒
  同一份流水重跑兩次可能得到不同的 $R$ ⇒ 違反 §5 冪等性 / 可重現性。
- `txn_id` 作為最後的 tie-break，保證全序。

**聚合是純函式重放（pure replay）**：
$$\text{state}_n = \mathrm{fold}\big(\text{apply},\;\text{state}_0,\;[\,t_1,\dots,t_n\,]\big)$$
`v2_holdings` **永遠可以從 `v2_transactions` 完整重建**，本身是 cache/物化視圖而非真相源。
→ 落在 **L2 `src/compute/portfolio/holdings_ledger.py`（純函式、零 I/O）**，
由 **L3 `src/services/holdings_service.py`**（已存在，245 行，現為唯讀 L3 介面）取數後呼叫。

### 2.6 `v2_holdings` 欄位表

| 欄名 | 單位 | 來源 | 說明 |
|---|---|---|---|
| `portfolio_name` / `asset_class` / `market` / `ticker` | — | key | 聚合主鍵 |
| `qty_units` | 股/單位 | $q$ | |
| `currency_code` | — | 流水 | 部位幣別；**流水內幣別不一致 → raise**（I-5） |
| `avg_cost_native_per_unit` | 原幣/股 | $C$ | |
| `cost_basis_twd` | TWD | $B$ | **可為 NaN**（期初列缺匯率） |
| `avg_fx_twd_per_native` | TWD/原幣 | $F=B/(qC)$ | 衍生欄 |
| `avg_cost_native_per_unit_after_div` | 原幣/股 | $C_{div}$ | 基金站相容，不進全站總計 |
| `realized_pnl_twd` | TWD | $R$ | |
| `realized_price_pnl_twd` / `realized_fx_pnl_twd` | TWD | §2.3 拆解 | $F$ 為 NaN 時兩欄皆 NaN |
| `dividend_cash_twd_cum` | TWD | $D$ | |
| `is_closed` | bool | $q\approx0$ | 清倉部位**保留不刪** |
| `cost_twd_is_partial` | bool | §2.2 | ⭐ **NaN 傳染旗標**，畫面必須讀它 |
| `cost_floor_hit` | bool | §2.4(b) | |
| `first_txn_date` / `last_txn_date` | date | 流水 | |
| `txn_count` | int | 流水 | |
| `rebuilt_at_utc` | datetime | 聚合器 | 物化時戳（§2.2 provenance） |
| `source_txn_ids_hash` | str | sha256 | ⭐ **快取失效鍵**：流水變了 hash 就變，強制重算 |

**未實現損益不存進表**（$V$ 依現價與**今日**匯率而變，屬 §2.4 TTL 資料）：

$$
\text{unrealized\_pnl\_twd} = \underbrace{q\cdot P_{\text{now}}\cdot f_{\text{now}}}_{\text{現值}} - B
\qquad(B=\mathrm{NaN}\Rightarrow \text{結果 NaN，畫面顯示「—」})
$$

$$
\text{fx\_pnl\_unrealized\_twd} = q\cdot C\cdot\left(f_{\text{now}} - F\right)
$$

---

## 3. 多幣別：原幣／台幣怎麼存、匯率錨在哪、換算在哪一層

### 3.1 存法（結論先講）

| 存什麼 | 存在哪 | 為什麼 |
|---|---|---|
| **原幣金額** | `v2_transactions.*_native` | 這是**觀測值**（券商對帳單上印的數字），不可失真 |
| **當筆匯率** | `v2_transactions.fx_twd_per_native` + 3 個 provenance 欄 | 這是**第二個觀測值**，與金額正交 |
| **台幣金額** | ⛔ **不存進流水**；只存進 `v2_holdings.cost_basis_twd`（$B$，聚合狀態） | 存了＝第二真相源（§2.1）。匯率來源日後更正時無法重算 |
| **今日匯率** | 完全不存（`@st.cache_data(ttl=...)`，走 `shared/ttls.py` SSOT） | 它是 §2.4 的 freshness 資料，不是帳務資料 |

### 3.2 匯率錨定點（本組判定，含理由）

**錨在 `trade_date`（成交日），不是 `settle_date`（交割日）。**

| 候選 | 判定 | 理由 |
|---|---|---|
| **成交日即期** | ✅ **採用** | 與 `gross_amount_native` 同一天，兩個觀測值時點一致；台股 T+2 / 美股 T+1 的交割日在多數券商實務上**不是**結匯日 |
| 交割日 | ❌ 不採為預設 | 會讓「成交金額」與「換匯」錯開 1–2 天，且各券商規則不同 → 製造一個**看似精確、實則猜測**的時點 |
| 今日即期 | ⛔ **明文禁止** | 用今天匯率回推歷史成本＝**造假**（§1 + §2.3 lookahead）。本設計不提供此路徑 |

**三段優先序（§2.1 衝突裁決風格，取第一命中、禁止平均）**：

1. **`user` / `broker_statement`** —— 使用者實際換匯匯率（含價差）。**最權威**，因為這是真的發生過的數字。
2. **`yahoo:TWD=X` 於 `trade_date`** —— 官方即期收盤。填 `fx_rate_as_of_date = trade_date`。
3. **`fred:DEXTAUS` 於 `trade_date`** —— 備援（`shared/fred_series.py:27` 自陳「Yahoo TWD=X 主、本條備援」，已是既有 SSOT）。
4. **全敗 → `fx_rate_source='MISSING'`、`fx_twd_per_native=NULL`**，該筆的 TWD 成本為 NaN。
   ⛔ **不進第 5 順位**。沒有第 5 順位。

**Sanity gate**：一律過 `portfolio_fx.normalize_usdtwd_rate()`（已存在的 L2 SSOT），
落在 `[USDTWD_SANITY_MIN=25.0, USDTWD_SANITY_MAX=40.0]`（`shared/signal_thresholds.py:1370,1376`）外 → 視同 `MISSING`。
⚠️ 注意該函式**寫死 USD/TWD 語意**；若日後出現第三種幣別必須擴充，不可沿用（見 §7 未驗事項 U-4）。

> ⚠️ **一個誠實的限制**：`trade_date` 官方即期 **≠** 使用者真實成交匯率（券商買賣價差常 0.1–0.3%）。
> 這是**已知且可量化的近似**，必須寫進交付報告與畫面 caption，
> 沿用既有的 `portfolio_fx.fx_disclosure_caption()`（已含匯率值 + as-of + 來源三件套）。
> 它與「用今天匯率回推」的差別是：**一個是有 as-of 的近似，另一個是無中生有。**

### 3.3 不變量（§4.2，每次聚合後斷言）

| ID | 斷言 | 違反時 |
|---|---|---|
| **I-1** | `gross_amount_native ≈ quantity_units × price_native_per_unit`（`math.isclose(rel_tol=1e-9)`） | raise（§4.3 禁 `==`） |
| **I-2** | `net_amount_native` 正負號符合 §1.2 表 | raise |
| **I-3** | `DIVIDEND` 且 `div_per_unit_native` 非空 → `gross ≈ q_held × div_per_unit` | log + 標疑義（配息基準日持股數可能因 T+2 而差一天，不 raise） |
| **I-4** | 同一 `(ticker, trade_date, div_per_unit_native)` 的 `DIVIDEND` 列 **≤ 1** | raise（擋雙重計算） |
| **I-5** | 同一部位的所有流水 `currency_code` 一致 | raise（幣別混用 = 帳本毀損） |
| **I-6** | $q \ge 0$ 恆成立（每一步之後） | raise（不 clamp） |
| **I-7** | $B \approx q\cdot C\cdot F$（$B$ 非 NaN 時；`isclose(rel_tol=1e-9)`） | raise —— 這條是 §2.1 那個設計決定的機械守衛 |
| **I-8** | $q\approx0 \Rightarrow B\approx0$ | raise + log 差額 |
| **I-9** | 總資產 $=\sum$ 各部位現值；**唯一加總點**（母法：嚴禁各儀表板各算一套） | CI 守衛 |
| **I-10** | `cost_twd_is_partial=True` 的部位，其 `cost_basis_twd` / `unrealized_pnl_twd` / `avg_fx` **必須為 NaN**，不得為 0 | raise |

### 3.4 `currency_code` 不得靜默推斷（§1 + 32× 事故的直接防線）

寫入 `v2_transactions` 時：

1. 由 `ticker` 後綴推出 `ccy_inferred`（沿用 `portfolio_fx.holding_currency`）；
2. 由 `market` 欄推出 `ccy_from_market`（`TW→TWD`、`US→USD`）；
3. **兩者一致** → 寫入，`fx_rate_source` 正常流程；
4. **兩者不一致 或 ticker 無後綴** → ⛔ **拒絕寫入並 raise**，
   訊息明講「`2330` 沒有市場後綴，請確認是台股 `2330.TW` 還是美股；
   猜錯會讓金額差約 32 倍」。

**這是把一個已知會靜默放大 32 倍的推斷，改成一個吵鬧的拒絕**（§1 Fail Loud）。

### 3.5 換算在哪一層

```
L1  src/data/portfolio/v2_txn_store.py        取流水（Sheets / parquet）— 只回原幣 + 匯率欄，不換算
L1  src/data/macro/  fetch_yf_close('TWD=X')  取今日即期（已有 @st.cache_data，EX-CACHE-1）
        │
L2  src/compute/portfolio/holdings_ledger.py  ⭐ 純函式重放 → v2_holdings（含 B、F）。零 I/O
L2  src/compute/etf/portfolio_fx.py           ⭐ 既有的**單一換匯點**，現值換算沿用不新寫
        │
L3  src/services/holdings_service.py          編排：取流水 → 重放 → 取今日匯率 → 算現值。**全系統唯一出口**
        │
L4/L5 各儀表板                                 ⛔ 唯讀引用 L3，嚴禁自己乘匯率、自己加總
```

- **成本換算**（歷史）：發生在 L2 重放時，用**每筆自己的 $f$**。
- **現值換算**（今日）：發生在 L3，用**今日即期**，走既有 `convert_rows_to_twd()`
  （該檔 docstring 自陳「整頁只呼叫一次」的設計原則，本設計沿用不改）。
- ⚠️ **既有 `portfolio_fx` 的已知限制自此可以解除**：它的 docstring 明寫
  「成本與現值都用同一個今日匯率 → `capital_gain` 不含匯兌損益，本頁沒有那筆資料，故不估」。
  **`v2_transactions` 補上的就是「那筆資料」。** 但解除須等資料真的有了 —— 期初列仍為 NaN。

---

## 4. 遷移路徑：台股 5 欄快照 → 流水模型

### 4.1 現況寫入路徑的實測風險（這一段決定了整個遷移方案）

| # | 實測 | 位置 | 風險 |
|---|---|---|---|
| M1 | `save_portfolio` = `ws.clear()` → `append_row(_HEADERS)` → `append_rows(keep_rows)` → `append_rows(new_rows)` | `gsheet_portfolio.py:384-388` | 全表重寫 |
| M2 | `new_rows.append([name, tk, lots, avg, ts])` —— **位置式、寫死 5 寬** | `gsheet_portfolio.py:379` | ⭐ **最危險**：header 長成 6/7 欄而此處沒同步改，**每次存檔都會把剛編輯的那些列的新欄位清空** |
| M3 | `keep_rows = [r for r in existing[1:] ...]`，`existing = ws.get_all_values()` | `gsheet_portfolio.py:366` | gspread 6.2.1 `get_all_values(pad_values=True)`（實測 `worksheet.py:482`）→ keep_rows 會被**補齊到表寬**，故**其他組合的新欄位會被原樣保留** ✅ |
| M4 | `_get_worksheet` 在 `first_row != headers` 時 `ws.update(f'A1:{_col_letter(len(headers))}1', [headers])` | `gsheet_portfolio.py:250-252` | 只覆蓋前 N 欄 → **尾端加欄在版本落差下是冪等的**（見 §4.2 分析） |
| M5 | `_col_letter` 硬限 1..26 欄 | `gsheet_portfolio.py:220-221` | 28 欄的 v2 表用現行 helper 會 **raise** |
| M6 | `parse_portfolio_records` 丟掉 `lots<=0 or avg_price<=0` 的列 | `gsheet_portfolio.py:297` | 髒列會**靜默消失**，遷移時必須先盤點有幾列會被丟 |

### 4.2 ⭐ 方案選擇：兩條路都滿足總管裁定，推薦第二條

總管裁定是「**新增欄位、不清表重寫**」。以下兩案**都**符合，差別在風險。

#### 方案 A｜就地在 `portfolios` 尾端加欄

**具體到「怎麼加欄而不讓舊列錯位」**（本組實測推導）：

1. **新欄一律接在 `updated_at` 之後**，前 5 欄的**名稱與順序一個字都不動**：
   `['name','ticker','lots','avg_price','updated_at', 'currency_code','avg_fx_twd_per_native','fx_source']`
2. **為什麼尾端加就不會錯位**（三條實測依據）：
   - 讀：`get_all_records()` 走 `self.get(pad_values=True)`（實測 `worksheet.py:562-565`）
     → 舊 5 格列被補成 8 格，新欄讀回 `''` ＝**標缺**，正是 §1 要的；
   - 舊碼回寫 header：`ws.update('A1:E1', [舊 5 欄])` **只碰 A1:E1**，
     而前 5 欄名稱未變 ⇒ **寫回去的內容與現況相同，F1/G1/H1 原封不動**（M4）；
   - 中間插欄則相反：舊列的 `lots` 會被讀成 `currency_code` —— **這是唯一真正會錯位的做法，禁止**。
3. ⛔ **M2 必須在同一個 commit 一起改**：`new_rows` 由寫死 5 元素改為
   `[row_dict.get(h, '') for h in _HEADERS]`（依 header 取值，非位置）。
   **不改就是資料損失**：使用者每存一次檔，該組合的幣別/匯率欄就被清空一次，而且**沒有任何錯誤訊息**。
4. **殘留風險（無法用程式消除）**：舊版本 app（使用者另一台裝置、Streamlit Cloud 尚未 redeploy）
   仍跑 M2 舊碼 → 它存檔時一樣會清空新欄。**這是部署期間的真實視窗，設計上無解**，
   只能靠「同一次 deploy」與「遷移後立刻驗一次」壓縮。

#### 方案 B｜**開新 worksheet，完全不碰 `portfolios`** ⭐ 推薦

新增兩個獨立分頁 `v2_transactions` / `v2_holdings`，`portfolios` 分頁**一個 cell 都不動**，
降級為唯讀 legacy 來源。

**推薦理由（四條）**：
1. **M2 那個風險直接歸零** —— 不改 `_HEADERS`，舊寫入路徑行為 byte-for-byte 不變，
   也就沒有「版本落差清空新欄」的視窗。
2. **28 欄本來就塞不進 `portfolios` 的心智模型**（它是持倉快照，不是流水），
   硬塞會得到一張半快照半流水的表 —— 那正是母法要消滅的東西。
3. **本 repo 已有同款先例**：`stock_watchlist` 分頁的註解明寫
   「與 `portfolios`(5 欄含價格)**物理隔離**(獨立 worksheet),互不污染」（`gsheet_portfolio.py:86-88`）。
   本方案是同一個判斷的第二次套用。
4. **可回滾**：v2 出問題就停用新分頁，舊功能毫髮無傷。方案 A 一旦回滾，
   已寫入新欄的資料就變成孤兒欄。

**兩案共同仍需處理**：M5（`_col_letter` 只支援 26 欄）—— 28 欄必須先擴 helper 或另寫。

### 4.3 遷移步驟（逐步驟；本階段只設計，不執行）

> ⚠️ **全程唯讀直到 S6。S1–S5 都不寫使用者的 Sheet。**

**S0｜盤點（唯讀）**
- 讀 `portfolios` 全表，逐列輸出：`name / ticker / lots / avg_price / updated_at`
- 統計三件事並**列印給使用者看**：
  (a) 總列數；(b) 會被 `parse_portfolio_records` 丟掉的髒列數（M6）；
  (c) **`ticker` 無市場後綴的列數** —— 這些就是 32× 地雷。

**S1｜幣別確認（需要使用者，不可自動）**
- 對每個無後綴 ticker，**必須**由使用者確認市場（§3.4）。
- ⛔ 不得用 `holding_currency` 推斷後靜默寫入。
- ⛔ 此步涉及新增畫面元件 → 落在 `CLAUDE.md §-1.5` A-8 **UI 草稿先行**，須先出線框給客戶拍板。

**S2｜數量語意確認（需要使用者）**
- `lots` 對台股 = 張（×1000 = 股）。**對美股部位，`lots` 的語意是未定義的**
  —— 實測 `etf_tab_portfolio.py:282` 對所有 ticker 無條件 `× 1000`，
  使用者若持有 100 股 BND，可能填了 `0.1` 也可能填了 `100`。**兩種都合理，程式分不出來。**
- → 美股部位一律**逐檔問使用者「你持有幾股」**，不做任何推斷。

**S3｜產生期初列（純函式，輸出到 scratchpad，不寫 Sheet）**
每個有效持倉 → **恰好一列** `TRANSFER_IN`：

| 欄 | 值 | 註 |
|---|---|---|
| `txn_type` | `TRANSFER_IN` | |
| `quantity_units` | S2 確認後的**股數** | 台股 = `lots × 1000` |
| `price_native_per_unit` | `avg_price` | 原樣搬；它已經是某種平均，不再分解 |
| `currency_code` | S1 確認值 | |
| `fx_twd_per_native` | **NULL** | ⭐ 見 §4.4 |
| `fx_rate_source` | `MISSING` | |
| `fx_is_imputed` | `False` | 沒填就是沒填，**不是**填了一個推估值 |
| `trade_date` | **NULL** | ⭐ 見 §4.4 |
| `seq_no` | 0 | 期初列排最前 |
| `source` | `migration_v1_snapshot` | |
| `entered_at_utc` | 遷移執行時間 | |
| `note` | `期初餘額（由 5 欄快照遷移，買入日期與買入匯率結構上不可得）` | |

**S4｜乾跑聚合（唯讀）**
- 跑 §2 重放 → 產生 `v2_holdings`
- **§4.3 重算對帳**：新表的 `qty_units × avg_cost_native` 必須與舊表的
  `lots × 1000 × avg_price` 逐檔 `math.isclose(rel_tol=1e-9)`。
  **不過就中止遷移**，不得「差一點點就算了」。

**S5｜差異報告給使用者**（§-1.5 §04 交付報告第 2 段）
- 逐檔列出：搬了幾檔、丟了幾列、幾檔的 `cost_basis_twd` 是 NaN、原因是什麼。

**S6｜寫入（⛔ 本階段不執行）**
- **只新增分頁 / 只在尾端加欄，不呼叫 `ws.clear()`**。
- 先寫 `v2_transactions`，確認讀得回來、聚合結果與 S4 一致，**才**啟用 v2 讀取路徑。
- `portfolios` 分頁**保留不刪**（`CLAUDE.md §-1.5.F 判定 3(5)`：
  它是使用者資產且無法從程式重建，屬「不能重建」那一側 → **刪除須請示客戶**，不在 GC 內部自決範圍）。

### 4.4 ⭐ 結構上回填不了的東西（一律標缺，禁止估算）

| # | 缺什麼 | 為什麼**結構上**回不來 | 處置 |
|---|---|---|---|
| **G1** | **買入匯率 $f$** | 5 欄裡從來沒存過。要回推需要「買入日期」，而 G2 說明那也沒有 | `fx_twd_per_native = NULL`、`cost_twd_is_partial=True`。**台幣成本與匯兌損益一律 NaN** |
| **G2** | **買入日期** | `updated_at` 是**整組合最後一次存檔的時戳**（`save_portfolio` 對**所有** `new_rows` 寫同一個 `ts`，實測 `gsheet_portfolio.py:371,379`）。它是**寫檔時間，不是成交時間** | `trade_date = NULL`。⛔ **絕不可拿 `updated_at` 當成交日** —— 那會讓「用當天匯率查回歷史成本」看起來合法，實際是拿存檔日的匯率冒充成交日的匯率 |
| **G3** | **交易筆數與各筆價格** | `avg_price` 是 N 筆買進的平均，N 未知。一個平均數無法唯一分解 | 只產生**一列**期初，`txn_count=1`。⛔ 不捏造分筆 |
| **G4** | **已實現損益歷史** | 賣掉的部位早已不在快照裡，沒留任何痕跡 | `realized_pnl_twd` 從遷移點**歸零起算**。畫面須標「已實現損益自 YYYY-MM-DD 起算」 |
| **G5** | **已領配息** | 現況是**估的**：`_div_amt = 近365天每股配息總和 × 今天的股數`（實測 `etf_tab_portfolio.py:341-342`）。買進不到一年的部位會被灌上整年配息 | `dividend_cash_twd_cum = 0` 起算。⛔ **不得**把那個估計值搬進帳本 —— 搬進去就從「畫面上的粗估」升級成「帳本裡的事實」 |
| **G6** | **手續費 / 證交稅** | 從未記錄 | `fee_native = tax_native = 0`，並在 note 標明「期初成本未含費稅」 |
| **G7** | **幣別** | 可由後綴推斷，但那正是 32× 事故（§3.4） | **不推斷，問使用者**（S1） |

> 🔒 **明文禁止的方案（總管已裁定，本設計同意並補上理由）**：
> 「用今天的 USD/TWD 回推歷史成本」。它同時違反
> §1（自行估一個合理值）、§2.3（lookahead：用未來資訊改寫過去決策）、
> §2.2（provenance：會產生一個 `as_of` 是今天、卻聲稱代表三年前的數字）。
> 而且它**不會炸** —— 算得出一個看起來很合理的數字，**這正是它最危險的地方**。
> 對照 `CLAUDE.md §1`：「錯誤的數字比沒有數字更危險」。

### 4.5 NaN 怎麼在畫面上活下去（否則使用者會以為系統壞了）

| 情境 | 顯示 | ⛔ 禁止 |
|---|---|---|
| `cost_twd_is_partial=True` | 台幣成本 `—`，旁邊 ⓘ「期初部位未記錄買入匯率，台幣成本無法計算」 | 顯示 `0` 或 `NT$0` |
| 該部位未實現損益 | `—` | 顯示 `+∞%` 或 `0%` |
| **總資產** | ⭐ **正常顯示**，但加註「其中 N 檔因缺買入匯率未計入成本比較」 | 整頁 NaN（現值本身是完整的，只有**成本**缺） |
| 匯兌損益 | `—（需要買入匯率）` | 估一個 |

> 對照 `CLAUDE.md §1.A` 第 4 點（v3 §02）：「未載入」＝灰色說明、「真出錯」＝紅色警示。
> **缺買入匯率屬「資料就是沒有」，是灰色 ⓘ，不是紅色錯誤** —— 標紅會讓整頁假警報淹掉真問題。

---

## 5. FIFO 差異說明文案草稿（第四層展開區用）

> **本站成本採「加權平均法」：每次買進後把新舊成本重算成一個平均價，賣出時不指定賣哪一批。
> 券商對帳單多採「先進先出（FIFO）」，先賣最早買的。兩者長期總損益一致，但單筆賣出的
> 已實現損益與剩餘成本會不同，數字有差屬正常。**

（91 字，未超過 100 字）

**備用較短版（56 字，若版位更窄）**：
> **本站用「加權平均」算成本，券商對帳單多用「先進先出（FIFO）」。
> 總損益長期相同，但單筆賣出的已實現損益會有差，屬正常。**

⚠️ **這兩段是 UI 文案 → 落在 `CLAUDE.md §-1.5` A-8 / v3 §03-2 ①（新增視覺元件），
須隨線框一起送客戶拍板，本階段不得直接寫進畫面。**

---

## 6. 母法修正提案

> 依 `§-1.5` C5：每項附**商業語言描述** ＋ **總管推薦方案** ＋ **具體原因**。
> 本組是執行 AI，以下為**建議**，決定權在總管／客戶。

### P-1 ⭐（最重要）「加權移動平均」需要補一句：平均的**權重是金額，不是單位數**

- **問題**：母法只說「統一採加權移動平均法」，**沒說權重是什麼**。基金站現行實作把匯率用
  **單位數**加權，在單價與匯率同時變動時**台幣成本不守恆**。
- **數值實證（本輪跑過，可複現）**：兩筆各 100 單位、nav 10→20、fx 30→32，
  真值 94,000、單位數加權算出 **93,000（少 1.064%）**、金額加權算出 **94,000（精確）**。
- **逐路徑實測（U-3 已於本輪複驗完畢，以下取代原「未驗」標記）**：

  | 路徑 | 實測位置 | 守恆? |
  |---|---|---|
  | `subscribe`（一般申購） | `services/ledger_service.py:84-86` 單位數加權 `fx_avg` | ❌ **不守恆** |
  | `_do_switch` → B 端**原本無持倉** | `cost_unit_b_new = twd_cost_basis / (n_added × fx_avg_b_new)` 反推後**直接指派** | ✅ 守恆（就那一步而言） |
  | `_do_switch` → B 端**已有持倉** | 反推後又做 `(old_units×cost_unit + n_added×cost_unit_b)/tot` 與同式的 `fx_avg` 單位數合併 | ❌ **再次不守恆** |

  → 精確說法是「**switch 的反推是守恆寫法，但緊接著的單位數合併把它吃回去了**」，
  而不是「全部路徑都不守恆」。⚠️ 另外 `twd_cost_basis = n_redeem × cost_unit_a × fx_avg_a`
  本身是三個各自平均值相乘，**會把 A 端既有的誤差原封不動搬到 B 端**。
- **商業影響**：兩個站對同一筆持倉會給出**不同的台幣成本**，違反母法「全系統單一事實來源」。
- **推薦**：母法補一句「**台幣成本基底 `cost_basis_twd` 為累加的一等狀態；平均買入匯率為
  `cost_basis_twd ÷ (數量 × 原幣平均成本)` 之衍生值**」。基金站現行實作需同步（另案，本階段不動）。
- **不做的代價**：兩站數字對不起來，而且差距小到不會被發現。

### P-2 除息的第三種處理（再投資）需要在母法明確為「**兩列**」

- 母法寫「配息再投資之移動平均滾入邏輯」。本設計落地為 DIVIDEND + BUY 兩列配對（§2.4c）。
- **推薦**：母法確認此形，並明訂**三種處理互斥**（避免配息被計兩次）。

### P-3 `v2_transactions` 需要第五種類型 `TRANSFER_OUT`（**建議但可延後**）

- **現況缺口**：母法四型涵蓋不了「轉倉出去」「基金轉換（switch）」。
  基金站現有 `switch_out` / `switch_in` 兩型（實測 `models/ledger.py:26-32`）在四型下**無處可去**。
- **推薦：本階段不加。** 台股站沒有這個需求，加了就是 §8.1 step 6 的「用不到的抽象」。
  **但要在文件標明**：基金站併入時**必然**會撞到，屆時再依 §8.4 step 4 提案。
- **理由**：現在加＝為一個還沒發生的需求付設計成本；現在不標明＝下一個人會以為四型夠用。

### P-4 「全系統唯讀引用」需要一條機械守衛，否則會退化

- 母法說「嚴禁各儀表板各算一套」。**實測顯示這件事在本 repo 已經發生過**：
  `張→股` 的乘法全站至少三處（`portfolio_deep_service` / `dividend_station_service:887` /
  `sector_flow.py:158`）。靠自律擋不住。
- **推薦**：比照既有的 `tests/test_p04_hold_view.py::TestTheLotToShareClaimIsMeasurable`
  （**現場掃 repo 量測乘法點數量，數量變了就紅燈**），為 `v2_holdings` 寫一條
  「除 L3 `holdings_service` 外，任何檔案不得自行加總持倉市值」的 AST 守衛。
- **理由**：`CLAUDE.md §8.2.A.0` 規則 3 的同一個教訓 —— 靠人工維護的清單一定會漂。

### P-5 `settle_date` / `market` 兩欄是本組自行加的，請確認

- 母法沒提。`market` 的理由是 32× 防線（§1.3、§3.4），**建議保留**。
- `settle_date` 目前**存而不用**，**建議保留但標明「先不做」**（§8.1 step 6）。

---

## 7. 我沒能驗到的事（§-2 規則 6，據實揭露）

> ⚠️ 以下每一條都**不是**「應該沒問題」，而是「**我沒驗**」。引用時請照此打折。

| ID | 沒驗到什麼 | 為什麼沒驗 | 風險方向 |
|---|---|---|---|
| **U-1** | **真實 Google Sheets 的行為**。M3/M4 的「尾端加欄安全」全部是**讀 gspread 6.2.1 原始碼 + 讀本 repo 程式碼推導**，**沒有對真的 Sheet 做過一次讀寫** | 本階段禁止任何 Sheets 寫入（不可逆） | 若真實 API 的 padding 行為與原始碼預期不同，§4.2 方案 A 的安全性宣稱**會垮**。**方案 B（開新分頁）不依賴這個推導**，這是推薦 B 的第五個理由 |
| **U-2** | **`portfolios` 分頁的實際內容**。S0 盤點的三個統計（髒列數、無後綴 ticker 數）**完全沒跑** | 無憑證、且屬使用者資料 | 無法預估遷移會丟幾列、會有幾檔要問使用者 |
| ~~**U-3**~~ | ~~基金站 `Switch` 路徑是否守恆~~ **← 本輪已複驗完畢，結論已寫進 P-1**（三條路徑逐一實測：`subscribe` 不守恆、switch 反推守恆、switch 合併再度不守恆）。⚠️ 仍屬**單組**結論 | — | — |
| **U-4** | **`normalize_usdtwd_rate` 對非 USD 幣別的行為**。它的 sanity 範圍寫死 `[25,40]`（USD/TWD 語意） | 本設計目前只有 TWD/USD | 若日後加第三幣別，直接沿用會把合法匯率判成 MISSING |
| **U-5** | **`v2_transactions` / `v2_holdings` 全域 0 命中**這個全稱句，是本組**單次 grep** 的結果，關鍵字只有這兩個字串 | 單組窮舉 | 若曾以別的措辭部分存在（如 `txn_ledger`），本輪掃不到 |
| **U-6** | **`_col_letter` 26 欄上限會擋住 28 欄表** —— 我讀了程式碼（`raise ValueError`），**但沒有實際建一個 28 欄 worksheet 驗證** | 需寫入 | 方向應該沒錯（它是無條件 raise），但「28 欄在 Sheets 端還會撞到什麼」未知 |
| **U-7** | **兩個 repo 的 `asset_class` 值域是否已有既存約定** | 只掃了本 repo | 基金站併入時可能需要第四個值 |
| **U-8** | **本檔 §2 的全部算式皆為紙上推導 + 手算驗證，未寫成可執行測試** | 本階段禁寫 code | §2.3 的 $F$ 不變性與價／匯拆解我做了代數驗證，但**沒有跑過數值測試**。實作時必須先補 property-based test |

---

## 8. 紀律自驗

- **唯讀**：全程只用 `git status` / `ls` / `grep` / `sed -n` / `cat` / `python3 -c "import gspread"` 讀取。
  **未建立、未修改、未刪除兩個 repo 內任何檔案。** 本檔寫在 scratchpad（session 隔離目錄），不在任何 repo 內。
- **未執行任何 Google Sheets 寫入**：全程未 import `gspread` 以外的憑證模組，未呼叫任何 `ws.*` 方法。
- **§1 Fail Loud**：本設計**不含**任何「用今天匯率回推歷史成本」的路徑；
  `fx_is_imputed` 欄存在的唯一目的是讓「有沒有被估過」可稽核，其 production 值恆為 `False`。
- **§-2 規則 6**：§7 已逐條標明未驗事項；§2.1、§4.2、§4.4 的判定均為**單組結論**。
