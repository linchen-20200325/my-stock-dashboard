# PROBLEM_TRIAGE — 現有發現的重新分級（階段 A）

> **產出日**：2026-09-15｜**產出組**：問題分級組（技術文件撰寫，**單組**）
> **任務性質**：**唯讀、零新增查證**。本檔**不含**任何新的 grep / 實跑 / 探針結果 ——
> 它是把三份既有文件的發現**重新分類、去重、併讀、採用稽核更正後的版本**。
> **本 session 未動任何程式碼、未動任何既有檔案、未做任何 git 寫入。唯一寫入為本檔。**

---

## ⛔ 讀本檔前必須先知道的三件事

### 1. 分級是**判斷**，不是事實 —— **客戶可以推翻任何一條**

「緊急 / 重要 / 登記」這三個標籤**由本組依下方判準判定**，**不是**三份來源文件裡就有的欄位。
判準是本組對客戶口述的成文化，**判斷過程寫在每一條的理由欄裡，就是為了讓客戶能自己覆核並推翻**。
⚠️ 有 **2 條**客戶在任務書裡點名為「緊急」，本組依判準判為其他級（見 §0.4）；另有 **5 條**是本組在三份來源互相矛盾時做的裁決（見 §4.1）。**那 7 條都是本組的判斷，請優先覆核。**

### 2. 本檔**不是**全站問題清單

本檔是 **`INDICATOR_SSOT.md` + `DATA_LINEAGE.md` + `STAGE1_AUDIT.md` 三份文件的整併結果**，
而**三份都自陳是單組產出、未經第二組複驗**，且三份**都各自列了大段「我沒查到的」**：

| 來源 | 自陳的涵蓋率限制（逐字要點） |
|---|---|
| `INDICATOR_SSOT` §9.1 U-1 | 「本檔涵蓋了畫面上的全部指標」**不成立，也沒有宣稱成立**；是**定向盤點**，非從 UI 反向清點。**涵蓋率未量測。** |
| `DATA_LINEAGE` §F-6 | 「**本份的主表不是全集**」；**凡本份沒有出現的資料項，意思是「我沒查」，不是「不存在」。** |
| `STAGE1_AUDIT` §8.3 | AST 掃描 707 筆**只細看 88 筆**；104 筆引用**只做 31 筆語意複核**；**⛔ 不得把「只有 2 筆不存在」讀成「其餘 102 筆描述都正確」。** |

⇒ **⛔ 不得把本檔讀成「這就是全部的問題」。** 本檔只能宣稱「這是三份文件目前寫下來的問題，經重新分級後的樣子」。

### 3. 本檔**不對任何標的產生買賣建議**

本檔中凡出現行動語（加碼／減碼／買進／停利／持股 %），**一律是引用現行 code 的字串常數，作為稽核軌跡**，
且逐處標【**引用現行 code**】。**本檔本身不建議任何人買賣任何東西。**

---

## 一頁看完：本檔收了什麼

| 級別 | 條數 | 優先序 | 這一級的意思 |
|---|---|---|---|
| 🔴 **緊急** | **6**（`P1-01`~`P1-06`） | **1–6** | 現在、線上、畫面上就會顯示錯的東西給使用者 |
| 🟡 **重要** | **19**（`P2-01`~`P2-19`） | **7–25** | 會影響判斷正確性，但需要條件觸發／靠運氣沒炸／只讓防線變啞／誠實地失效 |
| ⚪ **登記** | **25**（`P3-01`~`P3-26`，中間有跳號） | **26–50** | 知道就好：孤兒常數、死碼、命名衛生、文件與實況不符、合規待處理、資料資產 |
| | **合計 50 條** | | |

**⚠️ 三個數字都不是「全部」** —— 見上方第 2 點與 §4。
**⚠️ 優先序是「先看哪個」的順序，不是施工順序** —— 它完全沒有考慮修復成本（見 §4.3 第 4 點）。

---

## §0. 先處理三件會讓分級出錯的事

### §0.1｜甲：來源前綴對照表（**編號撞名，全檔一律用新編號**）

三份來源各自有編號，**而且互相撞名**。下表是本檔的命名規則與**已知撞名點**。

| 來源文件 | 原編號體系 | 本檔沿用的**回查前綴** | ⚠️ 撞名狀況 |
|---|---|---|---|
| `INDICATOR_SSOT` §7.2 本次新增發現 | `N-1` ~ `N-14` | `SSOT-N1` ~ `SSOT-N14` | 🔴 **與 `AUDIT-N1~N7` 撞名，且完全不是同一件事** |
| `INDICATOR_SSOT` §7.1 客戶點名 8 項 | `#1` ~ `#8` | `SSOT-K1` ~ `SSOT-K8` | — |
| `INDICATOR_SSOT` §9 未查證項 | `U-1` ~ `U-24` | `SSOT-U1` ~ `SSOT-U24` | ⚠️ 與本檔的「優先序」數字無關，別混用 |
| `DATA_LINEAGE` §B 重複取數 | `B-1` ~ `B-6` | `DL-B1` ~ `DL-B6` | 🔴 **與 `AUDIT-B1~B3`（三條紅線複驗）撞名** |
| `DATA_LINEAGE` §C 缺值填 0 | `C-R1~R3` / `C-A1~A7` / `C-3` / `C-4` | `DL-CR1`… / `DL-CA1`… | 🔴 **與 `AUDIT-C2~C6` 撞名** |
| `DATA_LINEAGE` §D 不可重建資料 | `D-1` / `D-2` | `DL-D1` / `DL-D2` | 🔴 **與 `AUDIT-D1`（15 vs 7 裁決）撞名** |
| `DATA_LINEAGE` §E 血緣斷點 | `E-1` ~ `E-6` | `DL-E1` ~ `DL-E6` | 🔴 **與 `AUDIT-E1`（MDD 量綱）撞名** |
| `DATA_LINEAGE` §F 沒查到的 | `F-1` ~ `F-7` | `DL-F1` ~ `DL-F7` | 🔴 **與 `AUDIT-F1~F3` 撞名** |
| `STAGE1_AUDIT` §2 引用抽查 | `A1` ~ `A4` | `AUDIT-A1` ~ `AUDIT-A4` | — |
| `STAGE1_AUDIT` §1 三條紅線複驗 | `B1` ~ `B3` | `AUDIT-B1` ~ `AUDIT-B3` | 🔴 見上 |
| `STAGE1_AUDIT` §3-A 兩份都漏的缺值填 0 | `N1` ~ `N7` | `AUDIT-N1` ~ `AUDIT-N7` | 🔴 **最危險的一組，見下** |
| `STAGE1_AUDIT` §4 / §6 | `D1` / `E1` / `F1~F3` / `C1~C6` | `AUDIT-D1` / `AUDIT-E1` / … | 🔴 見上 |

**🔴 最危險的撞名（本檔存在的第一個理由）**：

| 編號 | 在 `INDICATOR_SSOT` 是 | 在 `STAGE1_AUDIT` 是 |
|---|---|---|
| **`N1`** | `calc_fundamental_score` **量綱錯誤**（元/股當 %）→ 本檔 **P1-02** | `shared/macro_compute.py` 的 **`or` 三連缺值偽裝** → 本檔 **P1-01** |
| **`N2`** | `calc_health_score` 缺值回 0 → 本檔 **P1-03** | `financial_health_engine` 的 `cash_pct` 填 0 → 本檔 **P2-03** |
| **`N3`** | `calc_sharpe` 回 0.0 → 本檔 **P1-04** | `financial_health_engine` 的 `debt/eq` 填 0 → 本檔 **P2-10** |
| **`N4`** | `final_recommendation` 四輸入 default 0 → 本檔 **P1-06** | `health_history_service` 的 `rsi or 0` → 本檔 **P2-04** |

⇒ **全檔一律使用 `P1-xx` / `P2-xx` / `P3-xx` 新編號**；原編號保留在「原編號」欄供回查。

### §0.2｜乙：稽核組已推翻／修正的結論 —— **本檔一律採「修正後」版本**

| # | 原文件怎麼寫 | 稽核組的更正 | 本檔怎麼處理 |
|---|---|---|---|
| **乙-1** | `DL-CR2`：`finmind_m1m2.parquet` 的 m1b/m2 負值，主表標「畫面落點＝🌍 總經 v2 › 走勢卡」 | `AUDIT-B2(c)` / `AUDIT-C5`：**`src/` + `app.py` 內 0 個讀取點**。`macro_cache_reader` 內唯一命中是 `CACHE_DATASET_CADENCE` 的**登錄項**（新鮮度對照表），不是讀取點；`load_v2_chart_series` **只讀 `twii_ohlcv` 與 `finmind_margin`**。線上燈號的 `m1b_m2_gap` 走**另一支實作** `tw_macro.fetch_cbc_m1b_m2`（讀 `ms1.json`，拿到的本來就是 YoY 率，量綱是 pp） | ⛔ **不列緊急**。降為 **P3-02（登記）**：資料檔本身壞掉、但**沒有進畫面**。<br>✅ **真正要分級的是稽核組同時指出的缺口** → **P2-08（重要）** |
| **乙-2** | `DL` 主表兩處把 `M1B_M2_GAP_DETERIORATION_THRESHOLD = -2.0` 當現行判定門檻 | `AUDIT-A4` / `AUDIT-C6`：**0 個非定義處引用**（鄰居三顆分別是 21/58/4 個引用 ⇒ 不是整批死掉、是單獨一顆），是 v19.181 detox 刪掉 `macro_signal_lookback_tw.py` 後**留下的孤兒常數**；且它的單位是 **pts/月（月差分）**，與被比較的 **level（pp）** 不是同一種東西。**現行門檻**是 `shared/macro_buckets.py` 的 `DangerSpec("m1b_m2_gap", yellow=1.0, red=0.0)` | 降為 **P3-01（登記）** |
| **乙-3** | `SSOT §5.2`：MDD「量綱雙胞胎、**比較時必須換算**」（標 🔴） | `AUDIT-E1`：**實測兩者從不相遇** —— `risk_control.py` **沒有 import `calc_mdd`**；`update_drawdown` 用自己算的比例比自己的比例常數，**量綱內部一致**；`MAX_PORTFOLIO_DRAWDOWN` 全部出現處與 `calc_mdd` **沒有任何一處相遇** | 降為 **P3-03（登記）—— 命名衛生問題，不是 100× bug**。⛔ 不得再引用「必須換算」與「→ `risk_control.update_drawdown` 對照」這兩句 |
| **乙-4** | `DL-F1 #1`：m1b/m2 負值「**本組沒有查出根因**」，列為承重待驗 | `AUDIT-B2(b)`：**根因 repo 自己早就寫下來了** —— `shared/signal_thresholds.py` 逐字記載「根因在 `scripts/update_macro_history.fetch_finmind_m1m2` 的 CBC PXWeb 解析把**月變動量（流量）當成餘額（存量）**，再對一個會變號的序列算 YoY」；`scripts/export_stock_db.py` 又寫了一次並補上更強證據（2006-12 的 325,888 vs 2007-04 的 22,383 差 15 倍）⇒ **連通過 sanity 的 38 列也不可信** | ✅ **該待驗項關掉**。`DL-F1 #1` 的兩半（根因＋有沒有進畫面）**都已被回答**，不必再派人查 |
| **乙-5** | `SSOT §2.6` 標題：「實測 **15 個 family，比回報的 7 份更多**」 | `AUDIT-D1`：**兩者在數不同的東西，都不算錯** ——「15」數的是**估值中文標籤字面的產生點**（含 ETF 7% 估值／PB／PE 河流／教學表），「7」數的是 **357 殖利率呼叫點有沒有走 SSOT 函式**。**但「更多」蘊含包含關係，而包含關係不成立**：`DL-B2` 的 ② `section_psy_checklist` 與 ⑥ `section_op_recommendation` **不在 15 裡** | 措辭錯 → **P3-07（登記）**。<br>**併讀規則（採用稽核組原文）**：「**7 ＝ 357 的呼叫點（誰繞過 SSOT 函式）；15 ＝ 估值標籤字面的產生點（誰各寫一套中文）。兩張表要併讀，不可互相取代。**」 |

**本檔另外採用的稽核更正（乙 清單之外，稽核報告內還有的）**：

| # | 更正 | 影響 |
|---|---|---|
| **乙-6** | `AUDIT-A1`：`DL` 三處引用 **`macro_helpers.compute_macro_health`** —— **全站沒有這個函式**，`shared/signal_thresholds.py` 內 repo 自己已逐字記載「全站沒有這個函式…真正的實作是 `calc_traffic_light` 內的 `_health_parts` / `_w_sum` / `_health` 那段 inline 程式碼」 | ⛔ **本檔除本列與 `P3-04` 的稽核記錄外，0 次使用該名稱**（那兩處是在標記它是假的）。凡指涉總經健康評分，一律寫 **`src/compute/macro/macro_helpers.py:calc_traffic_light` 的 `health` 欄**（`SSOT §3.2` 的正確寫法）→ **P3-04** |
| **乙-7** | `AUDIT-A2`：`SSOT` 四處用 **`v5_modules.py:calc_357_valuation`**，真名是 **`calc_dividend_yield_357`**（內容描述**是對的**，錯的只有名字） | ⛔ 本檔一律用真名 → **P3-05** |
| **乙-8** | `AUDIT-A3`：`DL` 引用 **`risk_radar.py:vix_block`**，該檔無此符號；`fetch_vix_block` 在 `macro_snapshot.py` | → **P3-06** |
| **乙-9** | `AUDIT-C3`：`SSOT §6.2` 說 `bias_240` 的 `or 0` 是「死碼」—— **結論對，理由不夠強**。它的「死」建立在「上游不會出現 ≤0 的 close」這個**資料品質假設**上，函式內**沒有守衛**；而且一旦觸發，輸出是 `is_estimated=False` + `data_days=300`，**看起來是一個資料齊全、完全可信的讀數**，`classify_danger('bias_240', 0)` → **green**，**連一個旗標都沒有** | 併入 **P2-16**，理由改用稽核版本 |
| **乙-10** | `AUDIT-C2`：`SSOT-N5`（同一畫面「合理 3~5%」vs「🔴昂貴價」）的**病因不是字面耦合** —— 是 `shared/thresholds.py` 內**兩支 L0 SSOT 分級函式的分界本身就對不上**，而且其中一支的 docstring **自稱「等價」**。⇒ **就算把全站字串統一成 code 比對，這兩支仍然會給出相反的答案** | **P1-05 的理由整段改用稽核版本**（原文件的修法方向會修不到病因） |
| **乙-11** | `AUDIT-F3`：`SSOT §3.1`「五桶 **16** 盞燈」數字對，但**其中 `foreign_net` 的 `wired = False`** ⇒ **production 永遠只會亮 15 盞，第 16 盞恆 gray**。§3.1 門檻表 8 欄裡沒有 `wired` 欄 | → **P3-16** |
| **乙-12** | `DL-F4 #2`：`CLAUDE.md §8.2.A.2` **V-SMART-CACHE-1** 寫「5 個 `ttl=` 全是 inline 數字 → 同時違反 §3.3」——**該半句已不成立**，`etf_tab_smart.py` 已全部改走 `shared/ttls.py`。**L5 自建 cache 那一半仍成立** | → **P3-11** |

### §0.3｜丙：緊急級的第一位（客戶名單裡沒有，總管已親自實跑）

**`shared/macro_compute.py:evaluate_market_status_v4_final`** —— 見 **P1-01**，**優先序 1**。

### §0.4｜⚠️ 客戶點名為「緊急」、本組判為其他級的 —— **請優先覆核本組這 2 條裁決**

| 客戶點名 | 本組判定 | 理由（依 §0.5 的判準） |
|---|---|---|
| **`DL-CR3`** `_v()` 回 `0.0` | **重要（P2-02，優先序 8）** | `DATA_LINEAGE` **自己的原文**就寫：「引擎已改用領域規則（`_stmt_gap` / `gp <= 0` / `assets <= 0` / 分母 `> 0`）作為真正會觸發的守衛 —— **所以這條不是「現在正在出錯」，而是「防線少了一層、且那一層是啞的」**」。<br>依判準「緊急＝現在畫面上就會顯示錯的東西」，本條**不符**。<br>⚠️ **但它的下游有一條符合的** → `AUDIT-N2`（**P2-03**）與 `AUDIT-N3`（**P2-10**）。<br>⚠️ **如果客戶認為「一道 production 恆 False 的守衛」本身就該算緊急，本條立即升級** —— 那是個合理的判準，只是與客戶自己寫的判準不同。 |
| **`DL-CR1`** `twii_ohlcv.volume` 41 個假 0 | **重要（P2-01，優先序 7 — 重要級的第一位）** | `DATA_LINEAGE` 原文：「✅ **消費端已經防住**：`market_strategy.volume_window_stats` 把 `volume <= 0` **與** `NaN` 一律視為沒有觀測…**沒有送出假訊號**」。<br>⇒ 畫面上顯示的是誠實的「未評估」，**不是錯的數字** ⇒ 依判準不符「緊急」。<br>⚠️ **但它有一個很嚴重的實測後果**：「最近 20 個交易日**只有 2 筆有效觀測**」⇒ **瘋牛濾網目前是死的**。這是**現正發生的資料管線故障**，只是故障得很誠實。故給**重要級的最高優先序**。<br>⚠️ `DL` 自陳「**未查證是否還有第三個消費端直接吃這欄**」—— 若有，本條應升為緊急。 |

其餘 3 條客戶點名（`SSOT-N1` 量綱、`SSOT-N2` 缺值回 0、`SSOT-N3` Sharpe 回 0.0）**本組同意為緊急**，且**稽核組獨立複驗後全部維持或上修**。

### §0.5｜分級判準（寫在這裡，讓人能自己判、也能自己推翻）

```
【緊急】現在、線上、畫面上就會顯示「錯的東西」給使用者。
        必須三個條件同時成立：
          (1) 有 production caller（不是只有測試在呼叫）
          (2) 有渲染路徑（值真的會被畫到畫面上，或直接決定畫面上的結論）
          (3) 輸出的內容在事實上是錯的 —— 不是「誠實地說未評估」
        ⛔ 死碼不算緊急（例：SSOT-N8 的 valuation_level，production 0 caller）
        ⛔ 「誠實的未評估 / 空白 / 灰燈」不算緊急，即使功能因此失效（那會落到重要）

【重要】會影響判斷正確性，但至少符合下列一項：
        (a) 需要特定條件才觸發（例：只有資料壞掉時才爆）
        (b) 目前靠資料運氣沒炸（守衛不存在，但上游剛好沒吐出壞值）
        (c) 只影響內部一致性 / 只讓防線變啞，畫面暫時還是對的
        (d) 功能因缺資料而失效，但畫面誠實標示了「未評估」

【登記】知道就好，不一定要修，但要留在清單上：
        孤兒常數、命名衛生、文件與實況不符（含憲法自己過期）、
        已被取代的舊實作、死碼、合規待處理項（v1 凍結中）
```

**證據等級的定義（本檔通用）**：

| 等級 | 意思 |
|---|---|
| **實測** | 三種都算：① 有人**真的執行過程式並看到輸出**；② **直接讀取真實資料檔**（parquet / json）的內容；③ **逐字讀過原始碼本身**（「這一行確實這樣寫」是可驗證的事實，`grep` / `find` 的存在性結果同此） |
| **碼內自陳** | 註解 / docstring 自己說的（**沒有人驗過它說得對不對**） |
| **推論** | 由原碼的控制流推導出**執行時會發生什麼**（**沒有執行、沒有看到輸出**） |

⚠️ **這兩級常在同一條裡並存，本檔一律拆開寫**：
「`calc_sharpe` 裡確實寫了三個 `return 0.0`」是**實測**；
「因此一檔新 ETF 會少一顆星」如果沒跑過，就是**推論**（而這一條稽核組真的跑了 ⇒ 實測）。
⇒ **看到「實測」時請再讀一次括號裡寫的是哪一種。**

**「是否已複驗」的意思**：**有沒有第二組獨立看過同一件事**（原組 → 稽核組 → 總管）。
⚠️ 三份文件**全部**自陳單組未複驗；所以本欄寫「是」時，指的是**該條目已被兩組以上碰過**，
**不是**指「這件事已經被證實」。

---

## §1. 🔴 緊急（優先序 1–6）

> **⚠️ 全部 6 條都符合 §0.5 的三個條件**（production caller ∧ 渲染路徑 ∧ 輸出事實上是錯的）。
> 每一條額外附客戶要求的三欄：**影響哪個畫面 / 影響哪個指標 / 使用者的實際後果**。

### §1.1 總表

| 新編號 | 原編號 | 一句話 | 證據等級 | 已複驗 | 位置（`file:符號名`） | 優先序 |
|---|---|---|---|---|---|---|
| **P1-01** | `AUDIT-N1`（STAGE1_AUDIT §3-A）＋ 總管實跑 | 三個輸入**全部缺**時，市場狀態函式回「強勢多頭」＋一段部位建議＋「年線乖離 +0.0%」 | **實測（總管親自實跑）**＋稽核組 AST 掃描 | **是**（稽核組發現 → 總管親自實跑複驗） | `shared/macro_compute.py:evaluate_market_status_v4_final`（函式開頭三行的 `or` 預設值） | **1** |
| **P1-02** | `SSOT-N1`（§4.2）／稽核 `AUDIT-B1` | 基本面估值分把 **`avg_div`（元/股）當成殖利率 %** 去比 7/5/3 門檻 ⇒ 估值分與真實殖利率**完全顛倒** | **實測**（原組 `_probe_unit.py` ＋ 稽核組 `p1_fund.py` **兩組各自獨立實跑**） | **是**（稽核組複驗 → 嚴重性**不下修，反而上修**：追到 caller 與渲染、確認無 gate） | `src/compute/scoring/scoring_helpers.py:calc_fundamental_score` | **2** |
| **P1-03** | `SSOT-N2`（§4.1）／稽核 `AUDIT-B3` | 個股健康評分**全缺 → 0 分 → 🔴 弱勢危險**，型別上分不出「0 分」與「沒資料」 | **實測**（原組 `_probe_ind.py` ＋ 稽核組 `p3.py`） | **是**（稽核組複驗＋追下游，確認**無任何 gate**） | `src/compute/scoring/scoring_helpers.py:calc_health_score` | **3** |
| **P1-04** | `SSOT-N3`（§5.1）／稽核 `AUDIT-B3` | ETF 夏普值三條路**全部回 `0.0`**（含 `except` 吞例外），繞過綜合分本來設計好的缺值 rescale ⇒ **少一顆星** | **實測**（兩組各自獨立實跑，**機制一致、絕對數值不同** —— 見 §4.2） | **是**（稽核組複驗並量化） | `src/compute/etf/etf_calc.py:calc_sharpe` → `src/compute/etf/etf_scoring_helpers.py:build_etf_score_row` | **4** |
| **P1-05** | `SSOT-N5`（§4.2／§2.6）＋ **病因由 `AUDIT-C2` 更正** | 同一檔股票、同一個殖利率、**同一次 render**，畫面上三張卡給出互相矛盾的估值結論；根因是**兩支 L0 SSOT 分級函式的分界對不上，而其中一支 docstring 自稱「等價」** | **實測**（稽核組實跑兩支函式對照表）＋ **推論**（「三套同時出現在同一畫面」是讀 `tab_stock.py` 三個呼叫點推導） | **是**（原組摸到症狀 → 稽核組找到病因並推翻原病因診斷） | `shared/thresholds.py:classify_yield_zone` vs `shared/thresholds.py:classify_stock_357_price`；消費端 `src/ui/tabs/tab_stock.py` 三個呼叫點 | **5** |
| **P1-06** | `SSOT-N4`（§3.7） | 組合頁「綜合建議」四個輸入**全部 `default 0` / `default ''`** ⇒ **抓取失敗的股票拿 `pts=0` → 最差那一級**，且**沒有「未評估」這一級** | **推論**（逐字讀原碼＋讀 `section_batch_fetcher` 的錯誤列 literal；**未實跑**） | **否**（稽核組只複驗了符號存在與 §3.6 的 if-else 串與原碼一致，**未複驗本條**） | `src/ui/tabs/tab_helpers.py:final_recommendation`；錯誤列產生點 `src/ui/tabs/stock_grp_sections/section_batch_fetcher.py` | **6** |

### §1.2 逐條細節（客戶指定的三欄）

---

#### 🔴 P1-01 ｜ 市場狀態函式在「什麼資料都沒有」時回最樂觀的結論

- **原編號**：`STAGE1_AUDIT §3-A N1`（⚠️ **不是** `SSOT-N1`）
- **位置**：`shared/macro_compute.py:evaluate_market_status_v4_final`
  ／production caller：`src/ui/tabs/macro/section_warroom.py`（呼叫該函式處）
- **證據等級**：**實測（總管親自實跑 `f(None, None, None)`）** ＋ 稽核組 AST 掃描命中
- **是否已複驗**：**是** —— 稽核組（AST 掃描發現、追 caller）→ 總管（親自實跑，拿到真實輸出）

**總管實跑的真實輸出（三個輸入全部缺）**【引用現行 code 的輸出，稽核軌跡】：

```
Signal            = 🟢 強勢多頭
Action_Advice     = 均線多頭排列且籌碼穩定。建議擴大核心部位，增加成長型股票基金曝險。
Suggested_Holding = 80% - 100%
Bias_240          = 0.0
Is_Bull           = True
```

**機制（稽核組逐行）**：函式開頭三行是 `current_price = current_price or 1.0` /
`ma_240 = ma_240 or current_price` / `futures_net_oi = futures_net_oi or 0`。
② 是關鍵：**缺年線 → 拿現價頂替 ⇒ `bias_240 = ((p − ma) / ma) × 100 = 0.0` 恆成立**
⇒ `is_bull_market = p >= ma × 0.99` **恆為 True**。
caller 端**又補了一次** `or 0`（`_wr_bias.get('price', 0) or 0` / `_wr_bias.get('ma240', 0) or 0`）⇒ **缺值一路暢通**。

| 客戶指定欄位 | 內容 |
|---|---|
| **影響哪個畫面** | 🌍 總經分頁的**戰情室區塊**（`src/ui/tabs/macro/section_warroom.py`） |
| **影響哪個指標** | `Signal`（市場狀態）／`Bias_240`（**年線乖離 %**）／`Is_Bull`／`Suggested_Holding`（持股水位）／`Action_Advice` |
| **使用者的實際後果** | 在**完全沒有資料**的情況下，使用者看到的是一個**看起來很正常、很有信心**的畫面：一句「🟢 強勢多頭」、一個具體的數字「**年線乖離 +0.0%**」（讀起來像「剛好站在年線上」這個真實觀測），外加一段**明確的部位指示**。<br>⇒ 使用者**沒有任何線索知道系統其實一個輸入都沒拿到**。<br>⇒ 最糟的組合是：**資料管線壞掉的那一天，畫面反而最樂觀**。 |

**這一條同時踩三條線**：
1. `CLAUDE.md §1`「**寧可炸掉，不可造假**」——「年線乖離 +0.0%」是一個**捏造的觀測值**；
2. **客戶紅線「缺失值不得填 0」** —— 源頭就是 `price or 1.0` / `ma_240 or current_price` / `futures_net_oi or 0` 三個 `or` 預設值；
3. **客戶合規紅線** ——「建議擴大核心部位」＋「持股 80%-100%」是**直接的部位建議**，
   而且是**在零資料的前提下**發出的。【上述引號內為引用現行 code 的字串，作稽核軌跡用】

**⚖️ 減輕情節（稽核組據實記錄，本檔照轉）**：主結論已於 v19.182（C1）改由
`src/compute/macro/macro_helpers.py:calc_traffic_light` 的 `effective_regime` 供給，
`_v4` 的 `Is_Bull` 已降為補充提示。**但 `Bias_240` 那個數字仍直接顯示。**
⚠️ 這段是**稽核組轉述的碼內自陳**，本組**未複驗**。

**📌 與 `DL-CA6` 的區別（容易混）**：`DATA_LINEAGE §C-A6` 列的是**同一個檔案**的**法人 `fillna(0)`**，
**不是**本條的這三行。兩條是不同的東西。

---

#### 🔴 P1-02 ｜ 基本面「估值分」把元/股當成 %

- **原編號**：`SSOT-N1`（INDICATOR_SSOT §4.2）／稽核複驗 `AUDIT-B1`
- **位置**：`src/compute/scoring/scoring_helpers.py:calc_fundamental_score`
  ／caller：`src/ui/tabs/stock_sections/section_health_score.py`
  ／渲染：`src/ui/render/app_render.py:render_health_score`（`fund_html` 區塊）
- **證據等級**：**實測** —— **兩組各自獨立實跑**（原組 `_probe_unit.py`；稽核組 `p1_fund.py`）
- **是否已複驗**：**是**（稽核組：「嚴重性**不下修，反而要上修**」）

**實測對照（原組）**：

| 情境 | **真實**殖利率 | ⚖️ 估值分 | 估值 check 的文字 |
|---|---|---|---|
| `avg_div=18.0` 元、現價 1000 元 | **1.80%** | **3/3** | `18.0% 便宜區 >7%` |
| `avg_div=2.0` 元、現價 20 元 | **10.00%** | **0/3** | `2.0% 偏貴 <3%` |

⇒ **兩者完全顛倒**。估值分實際上是 `avg_div_twd` 的單調函式，**與便宜貴無關**（`price` 根本不是這個函式的輸入）。

**稽核組追加的三件事**：
1. **`avg_div` 確實是元/股**（三段追到源頭）：`src/data/stock/app_stock_fetchers.py:fetch_dividend_data` 算的是近 5 年每年現金股利的算術平均；同一檔 `tab_stock.py` 內**同一個變數**要 `÷ 股價 × 100` 才變成 %，要 `÷ 0.07` 才變成價格。
2. **有 production caller、有渲染、呼叫鏈上沒有任何 gate**（`awk` 掃 `tab_stock.py` 303–900 行無 `st.stop`、無提前 `return`）⇒ **不是死碼，是每次「🔍 載入完整分析」都會畫出來的四張小卡之一**。
3. **畫面上看不到那個假的百分號** —— `render_health_score` 的迴圈把 `cv`（`'18.0%'` 那個字串）**unpack 了但沒有渲染**。

| 客戶指定欄位 | 內容 |
|---|---|
| **影響哪個畫面** | 🔬 個股分頁 › 🏥 健康度評分區塊的**四張小卡**（💰 獲利 / 📈 成長 / 🎁 股利 / **⚖️ 估值**） |
| **影響哪個指標** | 「⚖️ 估值」分（0~3）、「🎁 股利」分（0~3）、以及每一項 check 的 ✓/✗ |
| **使用者的實際後果** | 一檔**高價、低殖利率**的股票（真殖 1.8%）會拿到 **⚖️ 估值 3 分 ✓**；一檔**低價、高殖利率**的股票（真殖 10%）會拿到 **0 分 ✗**。<br>⚠️ **最難發現的地方**：畫面上**只印分數與 ✓/✗，不印那個假的 `18.0%` 字串** ⇒ 使用者看到的是一個**沒有明顯破綻的分數**，無從察覺方向反了。<br>⇒ 使用者會以為「這檔股票便宜」，而它其實是全場最貴的一類。 |

**📌 同一個 repo 已經修過一次的同型 bug**（碼內自陳，`section_health_score.py` 註解逐字）：
舊碼把 `avg_div2 / max(price2, 1)` 當第 3 個參數傳，函式內再除一次股價 ⇒ **除以股價兩次** ⇒
2330 實機顯示 0.01%（真值 0.59%）並被判成最貴那一段。
v19.179 B1-b 修好了 `src/compute/strategy/v5_modules.py:calc_dividend_yield_357`，
**但同一個 `avg_div2` 餵給 `calc_fundamental_score` 這條沒修**。

---

#### 🔴 P1-03 ｜ 個股健康評分：什麼都沒抓到 → 0 分 → 最差等第

- **原編號**：`SSOT-N2`（INDICATOR_SSOT §4.1）／稽核複驗 `AUDIT-B3`
- **位置**：`src/compute/scoring/scoring_helpers.py:calc_health_score`
  ／等第映射 `health_grade`
  ／消費端 `src/ui/tabs/stock_sections/section_health_score.py`
- **證據等級**：**實測**（原組 `_probe_ind.py`；稽核組 `p3.py`）
- **是否已複驗**：**是**（稽核組複驗 + 追下游 gate）

**實測輸出（稽核組）**：

```
     df=None, all None -> score=0  details={}  grade=('弱勢危險', '#ef4444', 'health-C', '🔴')
    empty df, all None -> score=0  details={}  grade=('弱勢危險', '#ef4444', 'health-C', '🔴')
```

`details = {}`（**空 dict，不是 `None`，也沒有任何缺值旗標**）⇒ **消費端在型別上分不出「0 分」與「沒資料」**。

**稽核組追加：下游沒有 gate**（實測呼叫鏈）——
`section_health_score.py` 的 `if health2 >= A / elif >= B / else`，
**`health2 = 0`（＝完全沒資料）落到 `else`**，輸出的是一個**有明確方向的結論**而不是「未評估」；
上游 `tab_stock.py` 呼叫前**沒有** `if df2 is None or df2.empty: return`。
順帶：`tab_stock.py` 的 `cur_price2 = float(df2['close'].iloc[-1]) if ... else 0` —— **股價也被填 0**。

| 客戶指定欄位 | 內容 |
|---|---|
| **影響哪個畫面** | 🔬 個股分頁 › 「🏥 A. 個股健康度評分（0~100）」 |
| **影響哪個指標** | 健康度分數（0~100）、健康度等第（優質優良 🟢 / 震盪盤整 🟡 / **弱勢危險 🔴**）；下游還有 §3.6 操作狀態燈、§3.7 綜合建議、選股網汰弱門檻 |
| **使用者的實際後果** | 一檔**什麼資料都沒抓到**的股票，畫面顯示「健康度 **0 分 · 🔴 弱勢危險**」，並附上一句有方向的結論【引用現行 code 的字串】：`健康度 0分，技術面偏弱，跳過` ／ `不要強求，另找更好標的`。<br>⇒ 使用者會以為「系統評估過這檔股票，結論是它很差」，實際上是「**系統一個因子都沒算到**」。<br>⇒ **抓取失敗與「真的很爛」在畫面上完全同形。** |

**⚠️ 對照組（同 repo 內做對的版本）**：`macro_helpers.calc_traffic_light` 的總經健康評分
**兩條腿都缺就回 `None`**，檔內原文逐字：「**不是 0 分（0 分會被判成最強利空）**」。
⇒ **同一個 repo、同一個叫「健康評分」的東西，兩種標準。**

**⚠️ 第二個缺值問題（同函式）**：`'無MA數據' → +15` 是**給一半的中性分**，且 `score` 這個數字**不帶旗標**。

**⚠️ 一個未複驗的下游推論（照 `SSOT-U8` 沿用其自標）**：`src/compute/screener/scorability.py` 自己**有**正確的防線
（`_as_float(r.get("健康度")) is None` → 進 `health_unknown_ids`，**既不算 kept 也不算 eliminated**），
但因為 `calc_health_score` 回的是 `0` 而不是 `None`，`_as_float(0)` 回 `0.0` ⇒ **那道防線接不到這個案例**。
**這是單組推導，未跑端到端反例。**

---

#### 🔴 P1-04 ｜ ETF 夏普值回 `0.0` 繞過綜合分的 rescale ⇒ 少一顆星

- **原編號**：`SSOT-N3`（INDICATOR_SSOT §5.1）／稽核複驗 `AUDIT-B3`
- **位置**：`src/compute/etf/etf_calc.py:calc_sharpe`
  → `src/compute/etf/etf_scoring_helpers.py:build_etf_score_row`
  → `src/compute/etf/etf_scoring_helpers.py:compute_etf_composite_score`
- **證據等級**：**實測**（兩組各自獨立實跑）
- **是否已複驗**：**是**（稽核組獨立量化）

**三條路全部回 `0.0`**（原碼逐字）：`len(ret) < 20` → `0.0`；`ann_vol <= 0` → `0.0`；
`except` → `print('[calc_sharpe] swallow: ...')` 後 `return 0.0`。
第三條**同時違反** `CLAUDE.md §1`（吞例外後回假值）**與**客戶紅線（缺值填 0）。
⚠️ 函式的**回傳型別標註就是 `float`**，不是 `float | None` ⇒ **永不回 `None`**。

**機制**：`compute_etf_composite_score` 的 docstring 自陳「**缺項 rescale 有效權重**」——
也就是**它本來就設計成吃得下 `None`**。但上游寫 `_r['sharpe'] = calc_sharpe(df)`，
而 `calc_sharpe` 永不回 `None` ⇒ **rescale 永遠不會對 sharpe 生效**。

**兩組實測（其餘六維固定，但兩組固定的值不同）**：

| 組別 | `sharpe = 0.0`（現況） | `sharpe = None`（誠實缺值） | 差距 |
|---|---|---|---|
| 原組（`_probe_ind.py`） | composite **0.563** → **3 ★** | composite **0.669** → **4 ★** | **少一顆星** |
| 稽核組（`p3b.py`） | composite **0.767** → **4 ★** | composite **0.911** → **5 ★** | **少一顆星** |

⇒ **兩組一致的部分：少一顆星。** ⚠️ **不一致的部分見 §4.2（本組未消歧義）。**

| 客戶指定欄位 | 內容 |
|---|---|
| **影響哪個畫面** | 📦 ETF 分頁 › 綜合分 / 星等 / 多檔比較表 |
| **影響哪個指標** | 夏普值（顯示為 `0.00`）、ETF 綜合分、**星等**；再往下餵 `src/compute/etf/etf_recommendation.py:recommend_etf_action` 的 `composite` 門檻 |
| **使用者的實際後果** | 一檔**上市未滿 20 個交易日**的新 ETF，畫面上會顯示「**夏普 0.00**」——**那看起來是一個完全合法的觀測值**（「報酬恰等於無風險利率」），而不是「算不出來」。<br>⇒ 使用者會以為這檔 ETF 的風險調整後報酬很差，實際上是**它太年輕、樣本不夠**。<br>⇒ 而且它因此**被扣掉整整一顆星**，在多檔比較表上排在不該排的位置。 |

**⚠️ 一個條件性的後果，本組不把它當定論**：原組實測的 0.669 / 0.563 **剛好跨過**
`shared/etf_recommendation_thresholds.py:KEEP_COMPOSITE_MIN = 0.65` ⇒ 結論會翻。
但稽核組那組的 0.911 / 0.767 **兩個都在 0.65 以上** ⇒ **不會翻**。
⇒ **「結論翻轉」是條件性的（取決於其餘六維的值），不是必然。** 見 §4.2。

**✅ 對照組（同 repo 做對的版本）**：`src/compute/etf/dividend_station.py:sharpe_weekly` ——
週數不足 / 波動 ≈ 0 → **`return None`**，下游 `health_b(None)` → `Flag("⚪", "B 無夏普（週數不足或波動為零,算不出來）", miss_reason=...)`。
⇒ **同一個指標、兩支實作，一支誠實一支填 0。** 使用者在「多檔比較」與「存股健檢 B」會看到**兩個不同的夏普**。

---

#### 🔴 P1-05 ｜ 同一頁、同一個殖利率，三張卡給出互斥的估值結論

- **原編號**：`SSOT-N5`（§4.2／§2.6）；**病因由 `AUDIT-C2` 更正**（原文件的病因診斷已被推翻）
- **位置**：`shared/thresholds.py:classify_yield_zone` ／ `shared/thresholds.py:classify_stock_357_price`
  ／`src/compute/scoring/scoring_helpers.py:calc_fundamental_score`
  ／消費端 `src/ui/tabs/tab_stock.py`（三個呼叫點）、`src/ui/tabs/stock_sections/section_357_valuation.py`
- **證據等級**：**實測**（稽核組實跑兩支函式的九點對照表）＋ **推論**（「三套同時在同一畫面」是讀碼推導）
- **是否已複驗**：**是**（原組摸到症狀 → 稽核組找到病因，並**推翻了原病因診斷**）

**🔴 `AUDIT-C2` 的核心發現**：`shared/thresholds.py:classify_stock_357_price` 的 docstring **逐字自稱**
「**與 `classify_yield_zone()` 等價(都用同 SSOT 常數)**」—— **實跑否證**：

| 殖利率 | `classify_yield_zone` | `classify_stock_357_price` → UI 標籤 | 一致？ |
|---|---|---|---|
| 8.0% / 7.0% | `strong_buy` | `cheap` | ✅ |
| **6.0%** | **`neutral`（⚪ 中性）** | **`fair`（🟡 合理）** | ❌ 顏色與動作都不同 |
| **5.0%** | **`reduce`（🟡）** | **`fair`（🟡 合理）** | ❌ **方向相反** |
| 4.5% / 4.0% | `reduce`（🟡） | `dear`（🔴 昂貴） | ❌ 🟡 vs 🔴 |
| **3.0%** | **`sell`（🔴）** | **`overpriced`（🔴 超過昂貴）** | ❌ 動作不同 |

**根因（兩層，都在同一個檔案裡）**：
1. **邊界含入方向相反** —— `classify_yield_zone` 用 `cur_yield <= YIELD_MID` 把 **5.0% 歸到差的一側**；`classify_stock_357_price` 用 `price <= targets['fair']`（等價於 `yield >= 5%`）把 **5.0% 歸到好的一側**。**兩支對同一顆常數採了相反的開閉區間。**
2. **級距語意整體錯開一格** —— 5–7% 在一支是「中性」、在另一支是「合理」；3–5% 在一支是「🟡」、在另一支是「🔴」。

**⭐ 同一個個股頁同時跑三套**（稽核組追鏈，**讀碼推導**）：

| 呼叫點 | 走哪一支 | 一檔 5.0% 殖利率的股票會被說成 |
|---|---|---|
| `tab_stock.py` 的 `_valuation_simple` | `classify_yield_zone` → `classify_stock_status_lamp` | code=`reduce` → `'偏貴'` |
| `tab_stock.py` → `render_357_valuation_section` | `classify_stock_357_price` | **🟡合理價**【引用現行 code 的 label】 |
| `tab_stock.py` → `render_health_score_section` | `calc_fundamental_score` | **完全無關的第三種答案**（＝ P1-02 的量綱錯誤） |

| 客戶指定欄位 | 內容 |
|---|---|
| **影響哪個畫面** | 🔬 個股分頁（**同一次 render** 內的三個區塊：357 估值卡、健康度估值小卡、操作狀態燈） |
| **影響哪個指標** | 357 估值分級標籤／健康度的「⚖️ 估值」分／「操作狀態」燈 |
| **使用者的實際後果** | 同一檔股票、同一個殖利率、同一個畫面，使用者會**同時**看到兩到三個互相矛盾的估值說法（一張卡說偏貴、另一張卡說合理）。<br>⇒ 使用者**無法知道哪一個才算數**，而且沒有任何線索告訴他這是同一件事的兩種算法。<br>⇒ 更糟的是：**修字面修不好這個 bug** —— 就算把全站中文統一成 code 比對，這兩支函式**仍然會給出相反的答案**。 |

**⚠️ 這條的分級理由要精確**：函式**不等價**是**實測**；**三套同時出現在同一畫面**是**推論**
（稽核組 §8.1 #3 自標：「沒有實機跑過一檔 5.0% 的股票，結論是推導不是實測畫面」）。
⇒ 本組仍判緊急，因為**三個呼叫點都在同一個檔案的同一支 tab 渲染流程裡**，
但**如果客戶要求緊急級一律要有實機證據，本條應退回重要**。

---

#### 🔴 P1-06 ｜ 組合頁「綜合建議」：抓取失敗與「四項都差」長得一模一樣

- **原編號**：`SSOT-N4`（INDICATOR_SSOT §3.7）
- **位置**：`src/ui/tabs/tab_helpers.py:final_recommendation`
  ／錯誤列產生點 `src/ui/tabs/stock_grp_sections/section_batch_fetcher.py`
- **證據等級**：**推論**（逐字讀原碼 + 讀錯誤列的 dict literal；**沒有實跑**）
- **是否已複驗**：**否** —— 稽核組只複驗了「符號存在」與「§3.6 的 if-else 串與原碼一致」，**沒有複驗本條**

**機制**（原碼逐字）：`health = row.get('_health', 0)` / `mf_total = score_map.get(...).get('total', 0)` /
`val = row.get('_val', '')` / `trend = row.get('_trend', '')`
⇒ **四個輸入全部 `default 0` / `default ''`**，缺值一律當「最差」計分。
`section_batch_fetcher.py` 的錯誤列寫的是 `{'_health': 0, '_val': '-', '_trend': '-'}`
⇒ 一檔抓取失敗的股票 `pts = 0` → 落到最差那一級【label 引用現行 code：`'🔴 等待'`】。
⚠️ **沒有「⚪ 未評估」這一級**（對照 `dividend_station` 的 `Flag` 有 `⚪` ＋ `miss_reason`）。

| 客戶指定欄位 | 內容 |
|---|---|
| **影響哪個畫面** | 🏆 個股組合分頁 › 「綜合建議」欄 |
| **影響哪個指標** | 綜合建議三級（含一個帶行動語的最差級）；上游的 `pts` 累計分（理論 0~9） |
| **使用者的實際後果** | 使用者在組合表裡看到一檔股票被標成最差那一級，會以為「系統看過它、判它現在不該碰」。<br>實際上可能是「**這檔股票的資料一項都沒抓到**」。<br>⇒ 使用者會因此**把一檔其實沒被評估過的股票排除掉**，而畫面上沒有任何地方告訴他資料是空的。 |

**⚠️ 本條的證據等級只到「推論」** —— 若客戶要求緊急級一律要有實測，本條應退回重要（見 §4.1）。
**建議下一步**：這條是**最便宜的一次實測**（跑一次 `final_recommendation({}, {}, ...)` 即可證實或否證）。

---

## §2. 🟡 重要（優先序 7–25）

> **判準**：會影響判斷正確性，但 (a) 需要特定條件才觸發、或 (b) 目前靠資料運氣沒炸、
> 或 (c) 只影響內部一致性 / 讓防線變啞、或 (d) 功能失效但畫面誠實標了「未評估」。

| 新編號 | 原編號 | 一句話 | 證據等級 | 已複驗 | 位置（`file:符號名`） | 落在哪一款 | 優先序 |
|---|---|---|---|---|---|---|---|
| **P2-01** | `DL-CR1`（§C-1） | 大盤日 K 的 `volume` 欄有 **41 個假 0 ＋ 11 個 NaN，兩種缺值表示法並存**；writer 在 2026-08-25→08-28 之間改了行為、**舊資料沒回填**。實測**最近 20 個交易日只剩 2 筆有效觀測** ⇒ 瘋牛濾網目前是死的 | **實測**（原組 `read_parquet`；稽核組**逐字複驗數字**：n=4,932、n_zero=41、n_nan=11、close n_zero=0） | **是**（稽核組逐一複驗） | `data_cache/twii_ohlcv.parquet` 的 `volume` 欄；消費端 `src/services/market_strategy.py:volume_window_stats` | (d) | **7** |
| **P2-02** | `DL-CR3`（§C-1）／稽核 §7.1 確認 | 財報取數的 `_v()` **迴圈跑完 `return 0.0`、永不回 `None`** ⇒ 下游特地做的三態 `FIELD_ABSENT` **production 恆為 False**（一道啞掉的守衛） | **實測**（讀原碼＋稽核組確認）＋ **碼內自陳**（`financial_health_engine` 註解自己寫「`FIELD_ABSENT` 對 production 資料永遠不會發生」） | **是**（稽核組 §7.1 複驗「描述屬實」） | `src/data/core/financial_statements_fetcher.py:_v` | (c) | **8** |
| **P2-03** | `AUDIT-N2`（STAGE1_AUDIT §3-A） | 財報體檢的**現金佔比**缺值 → **0%** ⇒ 直接判成「現金最枯竭」那一級並拿最低分。**同一支函式的隔壁兩行就有正確的三態機制 `_stmt_gap`** | **推論**（稽核組 AST 掃描命中 + 讀分支；**未實跑**） | **否**（稽核組單組） | `src/services/financial_health_engine.py`（`cash_pct = fd.get("現金佔總資產(%)", 0) or 0`，4 處） | (c) | **9** |
| **P2-04** | `AUDIT-N4`（STAGE1_AUDIT §3-A） | 健康度歷史的 **RSI 缺值 → 0**，而 RSI=0 是「理論上的極端超賣」不是「沒資料」。**同一個 dict literal 的上一行 `"health"` 就沒有加 `or 0`** ⇒ 兩行之間兩套標準 | **推論**（稽核組讀碼 + 追 caller；**未實機 render**） | **否**（稽核組單組） | `src/services/health_history_service.py`（歷史列 dict 的 `"rsi"` 欄）；caller `src/ui/tabs/stock_sections/section_kline_chart.py` | (a) | **10** |
| **P2-05** | `SSOT-K2`（§2.7，客戶點名 #2） | 同一支 ETF 判定函式裡**三個欄位、兩種字串耦合**（`'🔴' in liquidity` 是 emoji、`'吃本金' in div_health` 是中文）。**實測反例：只改中文措辭 → 紅旗消失、結論翻面** | **實測**（原組 `_probe_ind.py` 跑出反例） | **否**（稽核組只確認符號存在與引用標示紀律，**未複驗反例**） | `src/compute/etf/etf_recommendation.py:recommend_etf_action` | (a) | **11** |
| **P2-06** | `SSOT-N13`（§6.3） | 出場訊號在**三維全缺**時輸出「訊號清淡（**三維未轉空**）」—— 那句話宣稱「我看過三個維度、都沒事」，實際可能一個都沒評估到。`compute_tech_bearish` 更是 `len(df) < 20` 就直接 `return {'bearish': False}`，**與「查過了、沒轉空」完全同形、無旗標** | **推論**（讀碼；`SSOT-U23` 自標「沒有實際餵三個 None 進去跑」） | **否** | `src/compute/scoring/exit_signals.py:evaluate_exit_signals` / `compute_tech_bearish` | (a) | **12** |
| **P2-07** | `SSOT-K7`（§3.6，客戶點名 #7，**客戶陳述已被更正**） | 操作狀態燈**不是「永遠點不亮」，是「半盲」**：殖利率 ≤3% 兩頁都亮；**3% < 殖利率 ≤ 5% 只有組合頁會亮**。根因是個股頁傳的 `'偏貴'` 既不含「昂貴」也不含「超貴」⇒ **該字面在全站沒有任何消費端會匹配，是死值** | **實測**（原組 `_probe_ind.py` 四種 label 逐一實跑） | **否**（稽核組只確認 §3.6 的 if-else 串與原碼一致） | `src/ui/tabs/tab_helpers.py:classify_stock_status_lamp`；兩個呼叫端 `src/ui/tabs/tab_stock.py` / `src/ui/tabs/stock_grp_sections/section_batch_fetcher.py` | (a) | **13** |
| **P2-08** ⭐ | `AUDIT-B2(e)`（稽核組在推翻 m1b/m2 緊急性的**同時**指出的真缺口） | 五桶燈的 `m1b_m2_gap` 那一盞**沒有合理值域守衛**（`DangerSpec` 的 `valid_min` / `valid_max` 皆為 `None`；16 盞裡只有 `us10y` [0,20] 與 `dxy` [70,130] 有）⇒ **若線上路徑哪天吐出量綱壞掉的值，`CLAUDE.md §3.2` 的範圍守衛不會攔，會直接判成紅燈而不是誠實的灰燈** | **實測**（稽核組 `p2d.py` 實跑：`gap=-13976.5` → `within_valid_range=True` → `classify_danger=red`） | **否**（稽核組單組；且稽核組**明確不宣稱**線上會發生，**只宣稱那道守衛不存在**） | `shared/macro_buckets.py:BUCKET_DANGER_SPECS` 的 `DangerSpec("m1b_m2_gap", ...)` | (b) | **14** |
| **P2-09** | `SSOT-N9`（§3.3）＋ `DL-D1`（signals.parquet） | **前進式驗證資料集驗不了它要驗的東西**：`max_score` / `twii_close` / `inputs_as_of` **三欄從第一筆起 100% 全 NULL**（16 列），而 schema 註解**自陳「必存」**；`max_score` 會浮動（4/5/6）⇒ **無法重建當日的 `score_pct`**；`twii_close` 全空 ⇒ **無法對帳「燈號 vs 大盤實際走勢」** | **實測**（兩組各自 `read_parquet`：rows=16、`max_score notna = 0/16`） | **是**（原組與稽核組各自實測，數字一致） | `src/compute/macro/macro_helpers.py:calc_traffic_light`（return dict 內 0 個 `max_score`）→ `src/compute/macro/macro_forward_test.py:build_signal_row`（用 `.get()` ⇒ 靜默回 None）；schema `shared/macro_forward_test_schema.py` | (c) | **15** |
| **P2-10** | `AUDIT-N3`（STAGE1_AUDIT §3-A） | 財報體檢的**負債比率**缺值 → 0% ⇒ **「零負債」是最好的讀數**。有 `debt == 0 and not is_finance` 的兜底重算，**但兜底本身也是 `.get(..., 0) or 0` 疊起來的** ⇒ 四個原始欄同樣缺→0 時**兜底靜默失效** | **推論**（稽核組讀碼；自標「未追到 debt=0 最終會不會變成一個 Pass」） | **否** | `src/services/financial_health_engine.py`（`debt` / `eq` / `lt_liab` / `ppe` 的 `.get(...,0) or 0`） | (a) | **16** |
| **P2-11** | `SSOT-N6`（§2.4） | **PE 河流圖的三組 preset 是 UI 檔內的 inline dict**（`_PE_BANDS`），而 **PB 河流圖走 L0 SSOT 且有產業分帶**、PE 沒有 ⇒ **金融股的 PB 用金融帶、PE 用製造業通用帶**，兩張並排的圖標準不一 | **實測**（grep 存在性；稽核組 §2 複驗 `_PE_BANDS` 為函式區域變數且內容吻合） | **是**（稽核組人工複核） | `src/ui/tabs/stock_sections/section_357_valuation.py:_PE_BANDS`（`render_357_valuation_section` 的函式區域變數）；對照 `shared/stock_buckets.py:classify_pb_level` | (c) | **17** |
| **P2-12** | `SSOT-K4` ＋ `SSOT-K5`（客戶點名 #4 / #5） | **① PE 取數層把 NaN 與 ≤0 丟進同一條路**（`if _pe != _pe or _pe <= 0: continue`）⇒ 畫面上「來源沒給」與「虧損」長得一模一樣，**沒有「N/A（虧損）」這個標籤**；**② 缺 PE 會讓整檔股票從榜單上消失** —— production 入口 `get_ranked_picks` 明確傳 `drop_unscored=True`（函式簽章預設是 `False`＝排最後）⇒ 使用者只看得到一行「N 檔未列入」的**數量**，看不到是哪幾檔 | **實測**（原碼逐字複驗；稽核組 §7.2 確認客戶陳述成立） | **是**（客戶點名 → 原組複驗 → 稽核組確認） | `src/data/stock/yield_pe_fetcher.py:fetch_pe_name_maps`；`src/services/fundamental_screener_service.py:get_ranked_picks`；門檻 `shared/signal_thresholds.py:SCREENER_MIN_FACTOR_COVERAGE_RATIO` | (c) | **18** |
| **P2-13** | `SSOT-N7`（§0.3／§3.6／§6） | **`⚪` 符號超載** —— 同時代表「未評估」與「中性、有結論」（`classify_stock_status_lamp` 的 docstring **自陳**「`⚪ 中性:其餘 / 資料不足`」，**兩種語意明文共用一個符號**）。顏色版同病：`classify_rs_zone` 的 `⚪ 無資料` 與 `🟡 中性` **同為黃色** | **碼內自陳**（docstring 逐字）＋ **實測**（`_probe_ind.py` 跑出全 None → `'⚪'`） | **否** | `src/ui/tabs/tab_helpers.py:classify_stock_status_lamp`；`shared/thresholds.py:classify_yield_zone`（`'⚪ 中性持有'`） | (c) | **19** |
| **P2-14** | `SSOT-N10`（§5.6） | ETF 流動性評分的 **AUM 段用 `except (TypeError, ValueError): pass`** —— AUM 型別異常被**靜默吞掉**，`level` 仍回量能單軸的結果、**無旗標**（`CLAUDE.md §1` 明文「`except: pass` 一律違憲」） | **實測**（讀原碼；稽核組 §7.2 複驗「屬實」） | **是** | `src/compute/etf/etf_calc.py:calc_liquidity_score` | (a) | **20** |
| **P2-15** | `SSOT §6.1` | **KD 的 `.replace(0, 1)`** —— period 內完全無波動（例：連續跌停鎖死）時分母 0 被換成 1 ⇒ `RSV = 0` ⇒ K/D 向 0 收斂 ⇒ **被讀成「極度超賣」**。<br>⚠️ **同一個檔案裡有兩種標準**：`calc_bollinger` 面對同一個問題（分母 0）是 `ma.replace(0, nan)` → `return None`（對）。<br>✅ 而 `shared/station_specs.py` **已經有**這個情況的專屬缺值原因常數 `MISS_NO_VARIATION` —— **KD 沒有用它** | **實測**（讀原碼逐字） | **否**；**觸發頻率完全未量測**（`SSOT-U18`） | `src/compute/strategy/tech_indicators.py:calc_kd`（`rsv` 那一行）；對照同檔 `calc_bollinger`；常數 `shared/station_specs.py:MISS_NO_VARIATION` | (b) | **21** |
| **P2-16** | `SSOT §6.2` ＋ **`AUDIT-C3` 更正** ＋ `AUDIT-C4` | **`bias_240` 在資料不足時不是年線乖離** —— `_maN = mean(tail(min(240, n)))`，n=90 時 `ma240` 其實是 MA90。碼內自陳「**只做揭露**，燈號／門檻／桶判定**仍直接套用這個估算值**」，且「10 個消費點裡只有少數帶揭露，其餘拿到的都是裸數字」。<br>**`AUDIT-C3` 的更正**：`macro_snapshot` 的 `or 0` **不是結構死碼，是「條件成立的死碼」** —— 函式內**沒有守衛**擋 ≤0 的 close；一旦觸發，輸出是 `is_estimated=False` + `data_days=300`，**看起來完全可信**，`classify_danger` 判 **green**，**連一個旗標都沒有**。⚖️ 現況沒在燒（實測 close `n_zero=0, n_neg=0, n_nan=0`）。<br>**`AUDIT-C4`：修法不必發明** —— 同一層的隔壁檔 `macro_cache_reader.load_v2_chart_series` 已經做對了（`len < DEFAULT_BIAS_MA_LEN` ⇒ **拒畫**，並 print「**不以較短均線冒充年線**」） | **實測**（稽核組實跑反例＋讀 parquet）＋ **碼內自陳**（`macro_helpers` 的 I2 區塊） | **是**（原組沿用 S1-2 推導未跑反例 → **稽核組跑了反例並修正結論**） | `src/data/macro/macro_snapshot.py:compute_twii_bias`；對照 `src/data/macro/macro_cache_reader.py:load_v2_chart_series` | (b) | **22** |
| **P2-17** | `DL-E2`（§E 血緣斷點） | **代理值的旗標在 L1→L1 打包時掉了** —— `tw_macro.fetch_cbc_m1b_m2` 有 `is_proxy_tier`，但 `macro_snapshot.fetch_m1b_m2_block` 重新打包 dict 時丟掉。<br>碼內自陳兩個具體後果：① KPI 卡的「（大盤動能代理估算）」註記**一次都沒顯示過**；② 拐點面板的守門 `if not _m1b2.get('is_proxy')` —— **`is_proxy` 這個鍵從來沒被寫入過**，守門**恆為 True、一次都沒擋到**。<br>🟡 已**繞道修補**（v19.183 建立 L0 SSOT `shared/macro_provenance.py:is_m1b_m2_proxy`，同時吃布林旗標與 `source` 標籤）；🔴 **producer 仍未補旗標**，現況靠比對 `source` 字面值 | **碼內自陳**（逐字）＋ **實測**（稽核組讀 `fetch_cbc_m1b_m2` 全文，確認三 Tier 且僅 Tier3 設旗標；讀 `is_m1b_m2_proxy` 全文確認 docstring 吻合） | **是**（稽核組 §2 逐條複驗） | `src/data/macro/tw_macro.py:fetch_cbc_m1b_m2` → `src/data/macro/macro_snapshot.py:fetch_m1b_m2_block`；繞道 `shared/macro_provenance.py:is_m1b_m2_proxy` | (c) | **23** |
| **P2-18** | `DL-E1` ＋ `DL-E3` | **失敗被快取** —— ① `macro_snapshot` 的 9 支 block 中**有 3 支沒走 `_cache_success_only`**（`m1b_m2` / `twii_2y_for_ma240` / `us10y`），失敗會被快取 1 小時；且 `fetch_us10y_block` 的失敗 dict 頂層鍵是 `us10y`（**不帶 `_` 前綴**）⇒ **即使改掛 `_cache_success_only`，`_is_block_failure` 也判不出它是失敗**。<br>② `fetch_price_data` 的 docstring 宣稱「刻意回錯誤字串**讓暫時性失敗不進 `st.cache_data`**」——**後半段不成立**：它掛的是 plain `@st.cache_data`，且是 `return` 不是 `raise` ⇒ **失敗 tuple 會被快取 30 分鐘**。<br>⚠️ 同一個 repo 裡，`page_today.py:REFRESH_FAILED_WHAT_NOW` 的**使用者文案講的才是實況**（逐字告訴使用者「失敗會連同失敗一起被快取一段時間」）—— **一份文案講對、一份 docstring 講反** | **實測**（原組逐 decorator 比對；稽核組**逐支複驗 6/3 分佈，一支不多一支不少**） | **是**（稽核組 §7.1 逐 decorator 複驗） | `src/data/macro/macro_snapshot.py:fetch_us10y_block` / `_cache_success_only` / `_is_block_failure`；`src/data/stock/app_stock_fetchers.py:fetch_price_data`；文案 `src/ui/views/page_today.py:REFRESH_FAILED_WHAT_NOW` | (a) | **24** |
| **P2-19** | `SSOT §6`（技術指標 kernel 表，標 🔴） | **ATR 缺 `high`/`low` 欄時靜默退回 `close`** —— `TR` 退化成 `abs(ΔClose)`，**回傳型別與正常路徑完全相同、不帶旗標** ⇒ 呼叫端**無從得知已降級**（違 `CLAUDE.md §1`「任何填補必須在輸出帶旗標」）。docstring 只寫了「不炸」。<br>⚠️ 下游是 **ATR 停損**（`risk_control.ATR_MULTIPLIER=1.5`，🔴 inline in L2） | **實測**（讀原碼逐字）；⚠️ **觸發頻率完全未量測**（`SSOT-U19` 自標「哪些 fetcher 會給出只有 `close` 的 df，沒查」） | **否** | `src/compute/scoring/scoring_engine.py:compute_atr`；adapter `src/compute/strategy/tech_indicators.py` | (b) | **25** |

**⚠️ P2-04 的一個跨文件張力（本組不裁決，見 §4.1）**：`DL-F5` 沿用上游材料記載
「`health_watchlist.json` 為空 ⇒ `health_history.parquet` 不存在 ⇒ **健康度走勢 0 樣本**」（**該組自標未複驗**）。
若那是實況，P2-04 的畫面後果**目前不會發生**（圖上根本沒有點）；
若健康度走勢其實是即時算的，P2-04 就該升級為緊急。**兩種可能本組都沒有查證。**

---

## §3. ⚪ 登記（優先序 26–50）

> **判準**：知道就好，不一定要修，但要留在清單上。
> 📌 **`P3-xx` 編號按主題分組，不按數字順序排** —— 同一個編號在全檔唯一，但 §3.1~§3.4 之間會跳號（例：§3.1 收 `P3-01`/`P3-02`/`P3-03`/`P3-08`/`P3-16`…）。**要照順序看請看「優先序」欄。**
> ⛔ **本節不構成動工授權**（`CLAUDE.md §-1`：沒有客戶指派 / 沒有實際 bug 觸發就不要碰）。

### §3.1 程式面（孤兒 / 死碼 / 命名衛生）

| 新編號 | 原編號 | 一句話 | 證據等級 | 已複驗 | 位置 | 優先序 |
|---|---|---|---|---|---|---|
| **P3-01** | `AUDIT-A4` / `AUDIT-C6`（⚠️ 客戶指定降級） | `M1B_M2_GAP_DETERIORATION_THRESHOLD = -2.0` 是 **0 consumer 的孤兒常數**（v19.181 detox 刪 `macro_signal_lookback_tw.py` 的遺留）；且它吃的是 `gap.diff()`（**pts/月**），與被比較的 level（**pp**）**不是同一種東西**。**現行門檻**是 `DangerSpec("m1b_m2_gap", yellow=1.0, red=0.0)` | **實測**（稽核組 grep：0 個非定義處引用；並量了鄰居三顆 21/58/4 做對照） | **否**（稽核組單組；**且自標 `getattr` 動態取用掃不到**） | `shared/signal_thresholds.py:M1B_M2_GAP_DETERIORATION_THRESHOLD` | **26** |
| **P3-02** | `DL-CR2` + `AUDIT-B2(c)` / `AUDIT-C5`（⚠️ 客戶指定降級） | `finmind_m1m2.parquet` 的 **m1b 73/240 筆為負、m2 47/240 筆為負**（貨幣供給不可能為負），**根因已知**（CBC PXWeb 解析把**月變動量當成餘額**，再對會變號的序列算 YoY —— 連通過 sanity 的 38 列也不可信）。<br>**但它在 `src/` + `app.py` 內 0 個讀取點** ⇒ **沒有進畫面**；線上燈號走另一支實作。<br>🔴 **壞消息**：git 追蹤著一份 240 列、36% 的列在物理上不可能、最後更新停在 2026-07-01 的資料檔，**而 app 根本沒在用它** —— 它的存在只會讓下一個人（含 AI）以為那是活的資料源 | **實測**（兩組各自 `read_parquet`，數字逐字一致；根因為**碼內自陳**，出處 `shared/signal_thresholds.py` 與 `scripts/export_stock_db.py` 註解） | **是**（原組實測數字 → 稽核組逐字複驗 + 找到根因 + 推翻畫面落點） | `data_cache/finmind_m1m2.parquet`；writer `scripts/update_macro_history.py:fetch_finmind_m1m2`；離線消費端 `scripts/export_stock_db.py`（**有** `_money_supply_sanity_gate`）／ `scripts/calibrate_health_weights.py`（**有** staleness gate） | **27** |
| **P3-03** | `AUDIT-E1`（⚠️ 稽核組推翻原 🔴 判定） | **MDD「量綱雙胞胎」降級為命名衛生問題** —— `MAX_PORTFOLIO_DRAWDOWN = 0.15`（比例）與 `calc_mdd`（百分比）**實測從不相遇**：`risk_control.py` **沒有 import `calc_mdd`**，`update_drawdown` 用自己算的比例比自己的比例常數（量綱內部一致）。⛔ **不是「一條會算錯 100 倍的比較路徑」** | **實測**（稽核組讀 import 區 + 追全部出現處） | **是**（稽核組推翻原組判定） | `src/config/config.py:MAX_PORTFOLIO_DRAWDOWN`；`src/compute/risk/risk_control.py:update_drawdown`；`src/compute/etf/etf_calc.py:calc_mdd` | **28** |
| **P3-08** | `SSOT-N8`（§2.6 C5） | `risk_radar` 的 **`valuation_level` 估值疊加是死碼** —— production **0 個 caller** 傳這個參數（5 處全在 `tests/test_dual_verdict_ui.py`）⇒ 兩個分支永不執行。留著會讓人以為已接線（`CLAUDE.md §-2` 的 `db4c139` 型態） | **實測**（grep：production 0 命中；稽核組 §7.2 複驗屬實） | **是** | `src/compute/risk/risk_radar.py:_apply_third_axis_overlay` | **29** |
| **P3-16** | `AUDIT-F3` | 五桶「16 盞燈」數字對，但 **`foreign_net` 的 `wired = False`** ⇒ **production 永遠只會亮 15 盞，第 16 盞恆 gray**。`SSOT §3.1` 的門檻表 8 欄裡沒有 `wired` 欄，標題會讓讀者以為 16 盞都在跑。<br>⚖️ 稽核組評語：那顆 `unwired_reason` 寫得**非常好**（「FinMind inst net 單位未確認…確認前填值會直接誤判紅綠燈，故決策端刻意回 None」）—— **是本 repo 缺值治理的正面範例** | **實測**（稽核組程式列印所有 spec） | **否** | `shared/macro_buckets.py:BUCKET_DANGER_SPECS` 的 `foreign_net` | **30** |
| **P3-17** | `AUDIT-B2(f)` | `M1B_M2_LEG_ENABLED = False` ⇒ `market_strategy.market_regime` 的 M1B-M2 **評分腿**已於 2026-08-19 校準後停用（AUC 0.5366），`_max` 從 6 降 5。⚠️ **但五桶燈那一盞仍 `wired=True`** —— 停用的只有評分腿 | **實測**（稽核組讀常數 + 讀 spec） | **否** | `shared/signal_thresholds.py:M1B_M2_LEG_ENABLED`；`src/services/market_strategy.py:market_regime` | **31** |
| **P3-24** | `SSOT §3.8` | 3-3-3 挑三原則的 **`passed` 欄是兩態** —— 三個 `*_ok` 旗標是三態（`True`/`False`/`None`，`detail` 顯示 `✅`/`❌`/`❔`），但 `passed = bool(None and ...)` → `False` ⇒ **「未判定」與「未通過」在 `passed` 欄同形**。docstring 自陳這是**刻意的 fail-closed**（「不足不放行」）⇒ 消費端**只讀 `passed` 就分不出** ❔ 與 ❌ | **實測**（讀原碼）＋ **碼內自陳** | **是**（稽核組 §2 確認符號存在） | `src/compute/etf/dividend_station.py:screen_333` | **32** |
| **P3-25** | `DL-CA5` | 板塊資金流的上游**丟掉 91.96% 的股票日**（找不到收盤價），被丟掉的那些在 pivot 上**也會呈現為 0** ⇒ **「沒交易」與「配不到價所以被剔除」在結果表上分不出來** | **實測**（原組讀原碼 + 百分比數字） | **否** | `src/compute/sector_flow.py`（pivot 的 `fillna(0.0)` 兩處） | **33** |

### §3.2 文件 / 憲法與實況不符（**不是程式缺陷**）

| 新編號 | 原編號 | 一句話 | 證據等級 | 已複驗 | 位置 | 優先序 |
|---|---|---|---|---|---|---|
| **P3-04** ⭐ | `AUDIT-A1` | `DATA_LINEAGE` **三處**引用 **`macro_helpers.compute_macro_health`** —— **全站沒有這個函式**，而且 **repo 自己早就把這件事寫下來了**（`shared/signal_thresholds.py` 逐字：「全站沒有這個函式…真正的實作是 `calc_traffic_light` 內的 `_health_parts` / `_w_sum` / `_health` 那段 inline 程式碼」）。<br>⚠️ **這是客戶紅線「不得發明不存在的資料源」的直接違反**，且是「**一次 grep 即可否證**」的那一種。<br>✅ **對照組（對 `INDICATOR_SSOT` 有利，據實記）**：`INDICATOR_SSOT` **0 次**使用這個假名 | **實測**（稽核組 `grep -rn "def compute_macro_health"` → 無輸出） | **是** | 文件缺陷：`DATA_LINEAGE.md` L107 / L167 / L170。**正確寫法**：`src/compute/macro/macro_helpers.py:calc_traffic_light` 的 `health` 欄 | **34** |
| **P3-05** | `AUDIT-A2` | `INDICATOR_SSOT` **四處**使用 **`v5_modules.py:calc_357_valuation`** —— **真名是 `calc_dividend_yield_357`**。⚠️ 要精確區分：**它描述的內容是真的**（docstring 與六個 signal 字串逐字吻合），**錯的只有名字**。<br>⚠️ 而 §9.2「只讀了 `calc_357_valuation`」這句**自我揭露也因此指向一個不存在的符號** —— 連盲點清單都錯了名字 | **實測**（稽核組 grep：假名 0 命中、真名命中） | **是** | 文件缺陷：`INDICATOR_SSOT.md`（4 處）。**真名**：`src/compute/strategy/v5_modules.py:calc_dividend_yield_357` | **35** |
| **P3-06** | `AUDIT-A3` | `DATA_LINEAGE` 引用 **`risk_radar.py:vix_block`** —— 該檔無此符號（檔內 VIX 相關符號是 `_signal_vix_level` / `_signal_vix_term_struct` / `_resolve_vix3m`）；**`fetch_vix_block` 在 `macro_snapshot.py`，不在 `risk_radar`** | **實測**（稽核組 grep） | **是** | 文件缺陷：`DATA_LINEAGE.md` | **36** |
| **P3-07** | `AUDIT-D1`（⚠️ 客戶指定採用） | `INDICATOR_SSOT §2.6` 標題「實測 15 個 family，**比回報的 7 份更多**」—— **「更多」蘊含包含關係，而包含關係不成立**（`DL-B2` 的 ② `section_psy_checklist` 與 ⑥ `section_op_recommendation` **不在 15 裡**，而那兩個**恰恰是**「走了 SSOT」與「只用單一門檻自算」兩個 `DATA_LINEAGE` 特別關心的形態）。<br>**⚠️ 這兩個之所以不在 15 裡，其實是 `INDICATOR_SSOT` 判對了**（它們不產生中文標籤）⇒ **問題不在內容，在措辭** | **實測**（稽核組逐項比對兩張表） | **是** | 文件缺陷：`INDICATOR_SSOT.md §2.6` 標題 | **37** |
| **P3-09** | `SSOT-N14`（§6.3） | `CLAUDE.md §8.2` 的 L2 代表檔把 `exit_signals.py` 寫在 `src/compute/strategy/`，**實際在 `src/compute/scoring/`** | **實測**（`find`；稽核組 §7.2 複驗「屬實 —— 憲法的 L2 代表檔列錯了，這份改對了」） | **是** | `CLAUDE.md §8.2` 的 L2 列 | **38** |
| **P3-10** | `SSOT-N12` | `CLAUDE.md §3.3` 宣告「❌ 標記 **0 項**」**與實況不符** —— 本輪在 `calc_fundamental_score`（6 個）、`final_recommendation`（7 個）、`etf_scoring_helpers._WEIGHTS/_NORM`（13 個）、`_PE_BANDS`（9 個）、財報等第樹（4 個）等處找到 inline magic number。<br>（憲法自己寫過「**會說謊的憲法比沒有憲法更危險**」） | **實測**（讀原碼逐處；稽核組 §2 複驗 `_WEIGHTS` / `_NORM` 全 inline 屬實） | **部分**（`_WEIGHTS`/`_NORM` 已複驗；其餘未逐項複驗） | `CLAUDE.md §3.3` 的「❌ 標記 0 項」句 | **39** |
| **P3-11** | `DL-F4 #2` | `CLAUDE.md §8.2.A.2` **V-SMART-CACHE-1** 寫「5 個 `ttl=` **全是 inline 數字**（1800/3600/3600/7200/86400）→ 同時違反 §3.3」——**該半句已不成立**（已全部改走 `shared/ttls.py`；檔頭註解亦自陳「**原有**」）。🔴 **另一半仍成立**：cache 仍在 L5，沒有下沉 L1 | **實測**（原組讀原碼） | **否** | `CLAUDE.md §8.2.A.2` V-SMART-CACHE-1；`src/ui/etf/etf_tab_smart.py` | **40** |
| **P3-12** | `DL-B5` | `CLAUDE.md §8.2.A.2` **只登記了 `etf_tab_smart.py` 一檔**，但另有 **`src/ui/tabs/grape_ladder.py`（3 個）** 與 **`src/ui/tabs/tab_edu.py`（1 個）** 同屬 L5 自建 cache 模式。<br>⚠️ **原組自標單組 grep、未窮舉，⛔ 不得讀成「就這三檔」** | **實測**（原組 grep `cache_data`，範圍 `src/ui/`） | **否** | `CLAUDE.md §8.2.A.2`；`src/ui/tabs/grape_ladder.py` / `src/ui/tabs/tab_edu.py` | **41** |
| **P3-13** | `DL-F4 #1` | `shared/ttls.py` **有 `TTL_10MIN = 600`**（碼內自陳「tw_macro 7 處 fetcher，v18.402 D3 新增」），但 **`CLAUDE.md §2.4` 的 Freshness 表從 `TTL_15MIN` 開始列，漏列了它** | **實測**（原組讀 `ttls.py`） | **是**（原組自陳與上游材料 `S1-1` 提案 #3 獨立複驗一致） | `CLAUDE.md §2.4` 表 | **42** |
| **P3-14** | `DL-F4 #3` | `CLAUDE.md §2.1` 寫 TW 融資餘額是「TWSE 主 → HiStock → Wearn」，**實際順序是 FinMind → TWSE `MI_MARGN` → HiStock → Goodinfo → Yahoo → 鉅亨網（6 層，且 FinMind 排第一**，理由是海外 IP 可達性）。**「Wearn」在該函式 docstring 中沒有出現** | **實測**（原組讀 `fetch_margin_balance`） | **否** | `CLAUDE.md §2.1` 的融資餘額列 | **43** |
| **P3-15** | `DL-F4 #4` | `CLAUDE.md §0` 寫「27 個外部資料來源 endpoint」，上游材料 AST 解析 registry = **78 筆**。<br>⚖️ **§0 是 2026-06-22 的填寫紀錄（歷史值），非現況** —— 嚴格說不算錯，但會被當成現況引用 | **推論**（原組**未重跑** AST，沿用上游材料並沿用其標註） | **否** | `CLAUDE.md §0` | **44** |

### §3.3 合規待處理（**v1 凍結中，客戶已知**）

| 新編號 | 原編號 | 一句話 | 證據等級 | 已複驗 | 位置 | 優先序 |
|---|---|---|---|---|---|---|
| **P3-19** | `SSOT-K3`（客戶點名 #3） | `SATELLITE_TAKE_PROFIT_PCT = 15.0` 是寫死常數，**沒有任何使用者設定路徑**（14 個命中：1 定義 / 1 控制流 / 5 顯示 / 4 測試 / 3 其他）。全站門檻覆寫機制只有 `macro_thresholds.json`（只 2 個 key），該常數不在其中 | **實測**（原組逐一分類 14 個命中） | **否**（`SSOT-U14` 自標：未掃 `st.selectbox` / `st.radio` / `st.toggle` / 環境變數 / `st.secrets`） | `shared/dividend_station_thresholds.py:SATELLITE_TAKE_PROFIT_PCT` | **45** |
| **P3-20** | `SSOT-K8`（客戶點名 #8） | 235 加碼燈的**名字本身帶動作語**（四個 label 三個含「加碼」、一個含「停利」），且 `deploy_pct` 直接給出資金比例數字 | **實測**（讀 `LIGHT_META` 逐字） | **否** | `shared/dividend_station_thresholds.py:LIGHT_META`；`src/compute/etf/dividend_station.py:light_235` | **46** |
| **P3-21** | `SSOT §8.1` | **判定層（L0/L2 純函式）裡就帶行動語的標籤 —— 影響最廣**：`shared/thresholds.py:classify_yield_zone` 是 **L0 SSOT 函式**、個股/ETF 三個 Tab 共用，而它的四個回傳標籤全是行動語。同類還有 `src/compute/etf/etf_helpers.py`、`src/compute/etf/etf_recommendation.py`、`src/compute/etf/etf_calc.py`、`src/compute/risk/risk_control.py`、`src/compute/screener/scorability.py`、`src/ui/tabs/tab_helpers.py`，以及**落在 L1 資料層的教學對照表** `src/data/core/data_registry.py`。<br>⚠️ **`src/services/app_ai_service.py` 那一組特別值得注意**：它是**規則式**產生的（不是 LLM 產的），條件是 `score >= 85 and '便宜' in val and '多頭' in trend` ⇒ **字面耦合 ＋ 直接輸出最強的那一句** ⇒ **改一個估值字面，會讓那句話出現或消失** | **實測**（原組全站 grep 行動語；稽核組 §5.1 複驗**兩份文件都沒有產生買賣建議**，16 筆行動語全在反引號內且標示為引用） | **是**（稽核組複驗引用標示紀律） | 見左欄逐檔【**本列全部為引用現行 code 的字串常數，作稽核軌跡用；本檔不建議任何買賣**】 | **47** |

### §3.4 資料資產登記（**⛔ GC 一律不得碰**）

| 新編號 | 原編號 | 一句話 | 證據等級 | 已複驗 | 位置 | 優先序 |
|---|---|---|---|---|---|---|
| **P3-22** | `DL-D1` | **不能重建、刪了就沒了的四類資產**：① `data_cache/forward_test/picks.parquet`（60 列 / 3 cohort —— 唯一的無 lookahead 驗證樣本）；② Google Sheets 端的持倉 / 帳本 / 保單（**使用者資產**）；③ `data_cache/macro_last_good/tw_pmi.json`（**上游現在拿不到了**，`metadata.json` 記 `last_error="抓取結果為空"`）；④ `data_cache/macro_forward_test/signals.parquet`（含 `git_sha` / `ruleset_hash`，重跑就不同）。<br>🔴 **①附帶一個完整性陷阱**：`name` 欄 **24/60 = 40% 是空字串**（前兩個 cohort；09-02 已修但**沒有回填**）——**空字串不是 `null`，`isna()` 掃不到** ⇒ **任何用 `isna()` 做完整性檢查的下游，這 40% 會靜默通過**。<br>🔴 **③ 的 LKG 本身 `is_proxy: true`** —— 連這個「最後拿到的好值」都不是原始值 | **實測**（原組逐檔 `read_parquet` / `json.load`） | **否**（稽核組只複驗了 `FORWARD_TEST_STORE_PATH` 存在與 picks.parquet 實體存在） | `src/data/portfolio/forward_test_store.py:FORWARD_TEST_STORE_PATH`；`src/data/portfolio/gsheet_portfolio.py`；`data_cache/macro_last_good/tw_pmi.json`；`data_cache/macro_forward_test/signals.parquet` | **48** |
| **P3-23** | `DL-E4` ＋ `DL-E6` | **兩個「畫面上看不到來歷」的斷點**：① parquet 的**過期旗標**在 L1→L3 掉了（`macro_v2_service.get_chart_series` 把 Series 轉成 `[(iso_date, value)]` 送進 `@st.cache_data`，**`.attrs` 在那一步就掉了**）—— **L1 已誠實算出「這份 parquet 多舊」並 print 出來，但畫面上看不到**（碼內自陳「這是待辦，不是已完成」）；② **`as_of` 根本不在 L3 契約裡** ⇒ **五頁 IA 的畫面上，使用者無法知道任何一個數字的資料歸屬日**。<br>✅ ② 的處理方式是**對的**（`page_today.py:AS_OF_NOT_IN_CONTRACT` 逐字寫「**寧可什麼都不寫，也不編一個時間出來**」）—— 它是「查不到就不編」的正面範例 | **碼內自陳**（兩處逐字）＋ **實測**（稽核組確認兩個常數存在） | **部分** | `src/services/macro_v2_service.py:get_chart_series`；`src/data/macro/macro_cache_reader.py`（檔頭自陳）；`src/ui/views/page_today.py:AS_OF_NOT_IN_CONTRACT` | **49** |
| **P3-26** | `DL-B1` ＋ `DL-B3` | **同源多套取數實作（登記，不動）**：① **Yahoo Finance 有兩套獨立實作** —— `macro_core` 直打 Chart API v8（自己解 JSON，module-level dict cache）vs `yf_proxy` 用 `yfinance` 套件（`@st.cache_data`）⇒ **兩套互不相通的快取**；② **US10Y 是兩次獨立取數** —— `macro_snapshot.fetch_us10y_block` 打 `fredgraph.csv` vs `risk_radar` 呼 `macro_core.fetch_fred("DGS10")`。<br>⚠️ **兩者的存在都有記錄在案的理由**（`macro_core` 不得 import streamlit；統一 proxy env 解 Cloud IP 403）—— **不是有人偷懶，是兩個約束在打架**。<br>⚠️ **匯率（USDTWD / DXY）本輪與前輪都沒掃** ⇒ ⛔ 不得讀成「三個來源都確認過」 | **實測**（原組讀原碼 + grep caller） | **否** | `src/data/macro/macro_core.py:fetch_yf_close` / `fetch_fred`；`src/data/proxy/yf_proxy.py:cached_history`；`src/data/macro/macro_snapshot.py:fetch_us10y_block` | **50** |

---

## §4. 我沒做到的（`CLAUDE.md §-2` 規則 6 誠實揭露）

> ⛔ 本節每一條都只能當「**待查證 / 待覆核事項**」，**不得作為後續動作的前提**，
> **不得寫進 commit message / PR 描述當成已完成的事實。**

### §4.1 ⚠️ 三份來源互相矛盾、由本組做了裁決的（**請優先覆核這 5 條**）

| # | 矛盾點 | 三份來源各說什麼 | **本組的裁決** | 風險 |
|---|---|---|---|---|
| **裁決-1** ⭐ | `DL-CR3`（`_v()` 回 0.0）**現在到底有沒有在出錯** | `DATA_LINEAGE` 標 🔴「本份最嚴重的一條」，但**同一格的末句**又寫「**這條不是「現在正在出錯」，而是「防線少了一層、且那一層是啞的」**」；`STAGE1_AUDIT §7.1` 只複驗「描述屬實」，**沒有判嚴重度**；**客戶任務書把它列為緊急的例子** | **判「重要」（P2-02）** —— 依客戶自己寫的判準（緊急＝現在畫面上就會顯示錯的東西），並**採信 `DATA_LINEAGE` 自己的末句** | 🔴 **高**。若客戶認為「production 恆 False 的守衛」本身就是緊急，本條要升級。**本組沒有實跑任何一條經過 `_v()` 的端到端路徑。** |
| **裁決-2** ⭐ | `DL-CR1`（volume 假 0）**現在到底有沒有在出錯** | `DATA_LINEAGE` 標 🔴，但同格寫「✅ 消費端已經防住…**沒有送出假訊號**」，同時又寫「🔴 但這一欄的原始值仍是 0 冒充觀測」且「**未查證是否還有第三個消費端直接吃這欄**」；**客戶任務書把它列為緊急的例子** | **判「重要」但給重要級的最高優先序（P2-01，優先序 7）** —— 畫面顯示的是誠實的「未評估」，不符緊急判準；但「最近 20 個交易日只剩 2 筆有效觀測」是**現正發生的資料管線故障** | 🔴 **高**。**若存在第三個直接吃 `volume` 欄的消費端，本條立即升為緊急** —— 而那正是原組自陳沒查的事 |
| **裁決-3** | `P1-04`（Sharpe）的**絕對數值**：兩組實測不同 | 原組：`0.0` → composite **0.563 / 3★**；`None` → **0.669 / 4★**（並主張**剛好跨過 `KEEP_COMPOSITE_MIN=0.65`** ⇒ 結論會翻）。<br>稽核組：`0.0` → **0.767 / 4★**；`None` → **0.911 / 5★**（兩個都 > 0.65 ⇒ **不會翻**） | **兩組都不算錯，因為「其餘六維固定在什麼值」不同** ⇒ 本組**只採信兩組一致的部分：「少一顆星」**；**⛔ 把「留下 ↔ 觀察 會翻面」降為「條件性後果」，不列為必然** | 🟡 中。**本組沒有回 code 確認兩組 fixture 的差異**（那會是新增查證）。⚠️ 若客戶要引用「結論會翻面」，**必須先確認是在哪一組 fixture 下** |
| **裁決-4** | `P2-04`（`rsi or 0` 畫成觸底）**畫面上到底有沒有點** | `STAGE1_AUDIT §3-A N4` 說有 production caller `section_kline_chart`（健康度歷史走勢圖）；`DL-F5` 沿用上游材料記「`health_watchlist.json` 為空 ⇒ `health_history.parquet` 不存在 ⇒ **健康度走勢 0 樣本**」（**該組自標未複驗**） | **判「重要」（P2-04）而非緊急** —— 因為「圖上有沒有點」在兩份來源之間沒有一致答案 | 🟡 中。**若健康度走勢其實是即時算的，本條應升為緊急。本組沒有查證。** |
| **裁決-5** | `P1-05`（三套估值結論）的**病因** | `INDICATOR_SSOT §2.6 / §3.6` 把病因歸給**字面耦合**（中文標籤字串不一致）；`AUDIT-C2` 實跑後說「**字面只是表層，`yellow/red` 的分界本身就對不上**，而且 docstring 還寫了『等價』」⇒ **就算把全站字串統一成 code 比對，這兩支仍然會給出相反的答案** | **採用稽核組的病因**（`AUDIT-C2`），並**據此重寫 P1-05 的理由欄** | 🟡 中。⚠️ **後果**：`INDICATOR_SSOT §2.6` 推薦的修法樣板（統一成 code 比對）**修不到這個病因**。任何人若照原文件的修法動手，會以為修好了 |

### §4.2 ⚠️ 證據等級只到「推論」的條目（**沒有人跑過、沒有人看過輸出**）

下列條目的行為宣稱**完全來自讀原碼**，**沒有任何一次執行、沒有任何一張截圖**：

| 新編號 | 為什麼只到推論 |
|---|---|
| **P1-06** | `final_recommendation` 的四個 `default 0` 是讀原碼看到的；「抓取失敗的股票會落到最差那一級」是推導。**⚠️ 這是唯一一條被本組列入緊急、但證據只到推論的。** |
| **P1-05**（一半） | 「函式不等價」是稽核組**實測**；「三套同時出現在同一畫面」是**讀 `tab_stock.py` 三個呼叫點推導**（稽核組 §8.1 #3 自標「沒有實機跑過一檔 5.0% 的股票」） |
| **P2-03 / P2-10** | 稽核組 AST 掃描命中 + 讀分支；**未實跑**，且 P2-10 自標「未追到 `debt=0` 最終會不會變成一個 Pass」 |
| **P2-04** | 讀碼 + 追 caller；**未實機 render**（另見 §4.1 裁決-4） |
| **P2-06** | `SSOT-U23` 自標「**沒有實際餵三個 None 進去跑**」，也**沒有查 UI 有沒有展開 `dims` 把「未掃描」顯示出來」** ⇒ **實際畫面是否真的會誤導，未確認** |
| **P2-15**（一半） | 「`.replace(0, 1)` 那一行確實這樣寫」是實測；「會被讀成極度超賣」是推論，且 **`SSOT-U18` 自標觸發頻率完全未量測** |
| **P2-19**（一半） | 「缺 `high`/`low` 會靜默退回 `close`」是讀原碼推導；**`SSOT-U19` 自標「哪些 fetcher 會給出只有 `close` 的 df，沒查」** |
| **P3-15** | 原組**未重跑** AST，沿用上游材料 |

**⚠️ 全域限制（三份來源共同的）**：**沒有任何一份跑過實機 Streamlit**。
`INDICATOR_SSOT §9.3 U-22` 逐字：「**完全沒有。**…畫面上實際印出什麼數字、標什麼文案、哪些區塊預設收合，**沒有跑起來看過**」；
`STAGE1_AUDIT §8.2 #4` 逐字：「**所有「畫面會顯示 X」的判斷都是讀 render 函式推導的，沒有一張截圖。**」
⇒ **本檔所有「影響哪個畫面 / 使用者的實際後果」欄位，除 P1-01 的函式回傳值（總管實跑）外，都繼承這個限制。**

### §4.3 本組自己沒做的（範圍取捨，據實列出）

1. **⛔ 本組沒有做任何新增查證** —— 這是任務的硬約束。本檔**沒有**跑過任何 grep / 探針 / 實機，
   **沒有**讀過任何 `.py` 原始碼。**全部內容來自三份來源文件的文字。**
   ⇒ **凡三份來源都寫錯的東西，本檔也會照錯。**（`AUDIT-A1` 就是這種錯被抓到的實例。）
2. **本組沒有處理三份來源的「未查證清單」本身** —— `SSOT-U1~U24`（24 條）、
   `DL-F1~F7`（含 F-3 的 8 項「有能力查但沒做」）、`AUDIT §8.1~8.3`（12 條）
   **合計 40+ 條待查事項，本檔一條都沒有分級**（它們是「不知道」，不是「問題」）。
   **唯一的例外是客戶指定的 `DL-F1 #1`，已依 §0.2 乙-4 關閉。**
3. **本組沒有去重到「一個病一條」的程度** —— 例如 P1-02 / P1-03 / P1-06 / P2-03 / P2-04 / P2-10
   在機制上**都是同一個病**（缺值用 0 / '' 表達，沒有第三態）。本檔**按檔案與消費端拆開列**，
   因為修的時候是分開修的；但**如果客戶要的是「幾個根因」而不是「幾個症狀」，這份分級要重做。**
4. **本組沒有驗證「優先序」是否真的按 ROI 排** —— 優先序是依
   「(1) 是否緊急 → (2) 證據等級 → (3) 是否已複驗 → (4) 影響面大小」四層排的，
   **完全沒有考慮修復成本**（本組不知道任何一條要花多久）。
   ⇒ **⛔ 這不是施工順序，是「先看哪個」的順序。實際排程需由總管重排。**
5. **本組沒有查證任何一個「影響哪個畫面」的分頁名稱** —— 例如「🌍 總經」「🔬 個股」
   「🏆 個股組合」「📦 ETF」這些分頁名，是從三份來源的文字裡抄的，
   **本組沒有打開 app 確認分頁真的叫這些名字**。

### §4.4 ⛔ 本檔**不**宣稱的事

- ⛔ **不宣稱「這就是全部的問題」** —— 本檔是三份文件的整併結果，而三份都自陳不是全集（見 §0 第 2 點）。
- ⛔ **不宣稱「緊急只有 6 條」** —— 只能說「三份文件寫下來的東西裡，符合本組判準的有 6 條」。
- ⛔ **不宣稱任何一條「已經確認會在畫面上發生」** —— 除 P1-01 的函式回傳值外，全部沒有實機證據。
- ⛔ **不宣稱本檔的分級是對的** —— 分級是判斷，客戶可推翻；本組已在 §0.4 與 §4.1 主動列出最可能被推翻的 7 條。

### §4.5 📌 唯讀紀律

| 項 | 狀態 |
|---|---|
| 程式碼 | **未動任何一行** |
| 既有檔案 | **未動任何一個**（含三份來源文件） |
| git | **未執行任何寫入操作** |
| 本 session 唯一寫入 | 本檔 `scratchpad/PROBLEM_TRIAGE.md` |
| 新增查證 | **0 次**（未跑 grep / 未跑探針 / 未讀任何 `.py`） |

---

*本檔由問題分級組（單組）產出，**未經第二組獨立複驗**。*
*⛔ 引用本檔任何一條之前，請先讀 §0 第 2 點、§0.4 與 §4。*
