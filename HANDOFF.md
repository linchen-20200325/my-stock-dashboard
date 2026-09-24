# HANDOFF — my-stock-dashboard 專案交接

> **建立日期 2026-09-24**。客戶因額度用罄，將專案交由另一個 AI 接手。
> **本檔的讀者是「一個完全沒有前一個 session 上下文的 AI」** —— 因此每個宣稱都附
> **檔案路徑 + 符號名**，讓你能自己去查證（依 `CLAUDE.md` §8.2.A.0 規則 1，**本檔不寫行號**）。
> 會漂移的量測值一律標「（量測日 2026-09-24）」（§8.2.A.0 規則 4）。
> **我實測過的事實**與**未經第二組驗的判斷**分開標示，後者逐條標 ⚠️（§-2 規則 6）。

---

## 0. 給接手 AI 的第一件事

**先讀 `CLAUDE.md`（專案憲法，約 700 行）與 `PROCESS.md`。** 最要緊的五條：

| 條號 | 內容 |
|---|---|
| **§-2** | 每件任務都要派 subagent 執行，總管不自己寫實作，且**必須自己複驗** subagent 的關鍵宣稱；調查／稽核要多組獨立派工。 |
| **§-1** | 沒有客戶指派、沒有實際 bug 觸發 → **停手等指令**，不主動找事做。 |
| **§-1.2** | 分支政策 —— **`main` 保留 v1，v2 完成前不合併**；v2 上線時才直接併 `main`。資料層凍結。 |
| **§-1.5.D v3 §03** | 唯二能問客戶的事 —— ① UI 版面／欄位／分頁動線異動（**須先出文字線框草稿**）② 商業衝突與不可逆操作。其餘（欄名、TTL、取數路徑、目錄命名、死碼何時刪）**一律內部拍板，且嚴禁拋選擇題**（要問必須附推薦方案）。 |
| **§-1.5.H 回覆紀律** | 每輪回覆 ≤ 15 行、表格優先、結尾必加 `⏸ 等待你回覆：【明確問題】` 或 `✅ 本輪完成，無需回覆。` |
| **§1 Fail Loud** | ⛔ 禁 `fillna(0)`／沉默 `ffill`／dummy 資料／`except: pass`／自己估一個合理值。**錯的數字比沒有數字更危險。** |

⚠️ **客戶的工作模式**：每輪發一張 **【本輪：…】工單**，含範圍、⛔ 約束、回報格式。
**嚴格照工單邊界做，超出即停手回報。**

---

## 1. 目前狀態（量測日 2026-09-24）

| 項目 | 值 |
|---|---|
| 工作分支 | `claude/stock-dashboard-handoff-g9dtm0` |
| HEAD | `f42577d`（與 `origin` 同步，工作樹乾淨） |
| PR | **#675**（open / **draft**），base `v2`。⚠️ commit 數／changed files／`mergeable_state`／CI 狀態**本質會漂移**（本分支每推一次就變，含本交接檔自身的 commit），依 §8.2.A.0 規則 4 **不寫死** —— 請**現場查證**：`GET /repos/linchen-20200325/my-stock-dashboard/pulls/675` 或 GitHub MCP `pull_request_read`。**已知**：head `f42577d` 當時 CI 全綠、`mergeable_state=clean`（量測日 2026-09-24）；其後推入的交接 commit 會觸發 CI 重跑。 |
| 既有交接檔 | `HANDOFF_MARGIN_RELATIVE.md`（本檔的前身，內容更細，**接手請一併讀**） |

⚠️ **PR #675 要不要轉 ready 併進 `v2`，客戶尚未裁示 —— ⛔ 不要自行 merge。**

---

## 2. 客戶當前要解的問題（主線）

客戶要的是「**趨勢**」，不是「**水位**」。

實測：`shared/macro_buckets.py` 全檔 `pct_change|rolling|quantile|.diff(|.shift(|ewm`
**命中數 = 0**（量測日 2026-09-24）⇒ 「憑什麼」頁的 **28 盞燈（總經 16 ＋ 持股 12）全部只判水位**。

---

## 3. 已查明的事實（🔴 這些我實測過）

1. **解法早就寫好但沒接線**：`shared/relative_thresholds.py`（448 行）含
   `classify_by_pct_rank(series, *, window=756, yellow=0.75, red=0.90, high_bad=True, min_periods=None)`、
   `margin_leverage_ratio(margin_yi, market_cap_yi)`、`vol_normalized_bias`、`foreign_futures_share`；
   `tests/test_relative_thresholds.py` **33 測試綠**；**0 production caller**。
   `macro_buckets` 自陳「尚未接線，屬行為變更需另案」。

2. **🔴 但預覽證明「接線」解決不了問題**：2026 年 122 個有結論日，
   **絕對門檻與相對分位都是 122/122 恆紅、0 轉態**。
   原因：融資餘額 2026 單邊創新高（3,509.5 → 5,878.7 億），
   **單調上升序列的滾動分位恆等於 1.0**（2026 pct_rank 中位數 0.9954、40/122 天 =1.0）。
   ⇒ `relative_thresholds.py` docstring 宣稱的「改相對分位才有鑑別力」
   **在本 repo 實測資料上不成立**。唯一增益是早約一個月轉紅（靈敏度，非鑑別力）。

3. **`data_cache/finmind_margin.parquet` 單位混用**（4,957 列）：
   **1,982 列**量級 1e11~1e12 ＝ 元（`MarginPurchaseMoney`，通過 sanity `[500,10000]` 億）；
   **2,975 列**量級 1e5~1e7 ＝ **張數**（`MarginPurchaseVolume`）。
   ⚠️ **任何吃這份 parquet 的分析結論都不可信。**

4. **🔴 但 cron 的 code 已經修好了** —— `scripts/update_macro_history.py::fetch_finmind_margin`
   已實際 import 並呼叫 `shared.margin_schema` 的 `extract_margin_money_series` /
   `margin_twd_sanity_mask`；守衛 `tests/test_b3_margin_schema.py`（33 測試）。
   修復後寫入的 27 列（`2026-08-06→2026-09-11`，`fetched_at` 自 2026-08-07 起）**全部乾淨**。
   ⇒ **髒的是 2026-08-07 之前舊 code 留下的 4,930 列歷史積欠，不是現在的程式。**

---

## 4. 🔴 卡關點（接手第一個要處理的）

**重抓歷史需要 FinMind token，容器內沒有** —— `FINMIND_TOKEN` / `FINMIND_API_TOKEN`
環境變數皆無，`.streamlit/secrets.toml` 不存在（量測日 2026-09-24）。

客戶尚未回答的二選一：

- **(A) 客戶提供 token** → 用已修好的 cron 重抓 20 年歷史，真正修好。**←（前一位總管的推薦）**
- **(B) 清掉不合 sanity 的 2,975 列** → 留 1,982 列乾淨資料，但那 60% 歷史**無法從程式重建**，
  且 parquet 受 git 追蹤 ⇒ 屬不可逆刪資料，落在 v3 §03-2 ② **須客戶拍板**。

⛔ **沒有第三條路**：張數無法換算成金額（要靠價格，等於捏造，違 §1）。

---

## 5. 主線的後續選項（預覽已否決「純接線」之後）

- **(a′) 換分母**：`margin_leverage_ratio(margin_yi, market_cap_yi)` ——
  ⚠️ **本地無上市總市值資料源**（`data_cache/` 只有 margin／inst／m1m2／pmi／twii；
  TWII 是指數點位，經除權息調整、不含股本成長，**拿來當分母＝捏造**）⇒ 需新資料源。
- **(b) 改判變化率／動能**而非水位分位（計算層；`relative_thresholds` 現成函式不直接支援）。
- **(c) 先修第 3、4 節的資料污染**（因為 (a′)(b) 都吃同一份 parquet）。

---

## 6. 28 盞燈的歷史可得性分級（⚠️ 單組窮舉，未經第二組驗）

**總經 16 盞**

| 級別 | 盞數 | 明細 |
|---|---|---|
| **A**（序列已在手，純計算層可加） | 8 | `bias_240`／`margin`／`vix`／`dxy`／`adl`／`fut_net`／`jingqi`／`us10y`（走 `cl_data['intl']` 次源） |
| **A−**（本地 parquet 有月頻序列，缺一行 loader） | 2 | `m1b_m2_gap`（240 月）／`ism_pmi`（170 月） |
| **B**（上游有歷史但只取最新值） | 4 | `health`／`ndc_signal`／`us_core_cpi`／`tw_export` |
| **C** | 2 | `foreign_net`（卡單位未確認）／`news_systemic`（真的沒歷史） |

⚠️ **真能做「三年分位」的只有 2 盞**（`margin`／`bias_240`，唯二 20 年序列）；
其餘 A 級窗只有 14~60 個交易日，**只做得了「近 N 日方向」**。

**持股 12 盞**：A 8／B 3／N/A 1（`screen_inception` 成立年數，變化率無意義）／C 0。

⚠️ **資料新鮮度**：parquet 最新資料日 **2026-09-11**（量測日 2026-09-24，落後 13 天）。

---

## 7. 登記但未動工的既有缺陷（依 §-1，⛔ 沒有指派就不要碰）

- `data_cache/finmind_margin.parquet` 歷史積欠污染（第 3、4 節）。
- `shared/macro_buckets.py` 自陳融資燈「絕對門檻已被市值成長淹沒 → 燈號恆紅、鑑別力歸零」。
- 其餘見 `CLAUDE.md` **§8.2.A.2 待修違憲清單**與 **§8.3 灰色地帶**、根目錄 `DEAD_CODE.md`。

⚠️ `CLAUDE.md` **§8.2.A.2 前言明文**：「本表不構成主動動工的授權」。

---

## 8. 本 session 的誠實揭露（§-2 規則 6）

- 第 2、3、4 節的數字**前一位總管已親自實測複驗**（`macro_buckets` 關鍵字計數、
  `relative_thresholds` 行數與測試數、parquet 量級分布與 sanity 計數、2026 分位分布、
  cron 是否真走 schema、token 是否存在），**非僅轉述 subagent**。
- ⚠️ **未經第二組獨立驗**：第 6 節的 A/B/C 分級、「口徑判準＝通過 sanity 就是 Money 列」、
  以及「cron 已修好」這個全稱判斷。**⛔ 不得當既定前提使用，請接手後自行複驗。**
- 預覽腳本與圖只存在於前一個 session 的 sandbox，**未進 repo，已隨容器消失**；
  要重現請依第 3 節第 2 點的參數自行重跑。
