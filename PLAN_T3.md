# T3 架構規劃：Watchlist 訊號推播 + 深連結閉環

> **本文件禁止附帶 code**（`CLAUDE.md` §8.1）。核准後才進 Execute，一次一個模組（§8.5）。
> 建立日：2026-08-14　基準：v19.193（5753 passed）
>
> 目標：把流程圖**層次 3 的「觀察池追蹤進場訊號」**與**層次 4 的「進場訊號推播 / 停損警報 /
> 二次分析」**接通。這是整套系統從「你去看它」變成「它來找你」的那一步。

---

## §0 動工前的驗證結果（**兩個假設被推翻**）

我在上一輪對話中說過「技術性停損不需要成本價，而且 `risk_control.py` 已經寫好只差接線」。
實際讀完程式碼後，**後半句是錯的**：

| 函式 | 位置 | 能不能用在 watchlist |
|---|---|---|
| `atr_stop_price(buy_price, atr, ...)` | `risk_control.py:100` | ❌ **需要 `buy_price`** |
| `stop_loss_trigger(buy_price, current_price, ...)` | `:112` | ❌ **需要 `buy_price`** |
| `trailing_stop_trigger(buy_price, peak_price, ...)` | `:124` | ❌ **需要 `buy_price`** |
| `evaluate_exit_signals(tech, chip_signal, news)` | `exit_signals.py:236` | ✅ **零價格參數** |

⇒ 個股 watchlist 沒有成本價（`gsheet_portfolio.py:60` schema 只有三欄），
`risk_control` 那三支**一支都用不了**。這不是「接線」問題，是「那些函式的前提不成立」。

**這正是 T1-a 教訓的同一類錯誤**：憑既有描述寫規劃、沒讀簽章。故本規劃書所有「可重用」
的宣稱都附 `檔案:行號` 且已實讀。

---

## §1 單一職責（一句話）

> 每個交易日盤後掃一次你的觀察池，**只在有事發生時**發 LINE，訊息裡附一個能點回網頁的連結。

---

## §2 我先替你決定的三件事（**你可以直接推翻，改一行字就好**）

上一輪我用選項卡問，你沒選。以下是我的預設，理由都寫了；不同意的話告訴我哪一項要換。

### 2.1 cron 怎麼讀到你的觀察池 →「**發布成公開 CSV**」

沿用週報已在用的 `WEEKLY_WATCH_CSV_URL` 模式（`scripts/push_weekly_report.py:150`）。

**為什麼這個選項在你的情況下沒有隱私問題**：個股 watchlist 是**純代碼清單**
（`gsheet_portfolio.py:60`：`name | ticker | updated_at`，`:56-58` 註解明寫「無張數/均價」）。
發布出去只會讓人知道你在看哪幾檔，**不會洩漏任何部位大小**。
週報那支自己警告的「ETF 分頁含張數均價，整頁發布會公開部位」——
**只適用 `portfolios` 分頁，不適用 `stock_watchlist`**。

⚠️ 但你要發布的是**個股那張分頁**，不是整份試算表。設定時請確認範圍。

**推翻的時機**：日後若要做部位型停損（需要張數/成本），這條路就不夠了，
屆時再升級成 Service Account + GitHub Secret。現在做那個是 §8.1 step 6 的「用不到的抽象」。

### 2.2 推播頻率 →「**有訊號即推 + 每週一健康碼**」

- 平日盤後：**只在有觸發時發**。沒訊號完全不發。
- 每週一：固定一則「本週監控 N 檔，觸發 M 次」確認 cron 活著。

**為什麼不是每日都發**：每天一則「今日無觸發」會讓你在三週內訓練成不看它。
訊息的價值來自「收到 = 真的要看」。

**為什麼需要健康碼**：純事件驅動的最大盲點是「連續五天沒消息」你分不出
「市場很平靜」還是「cron 三天前就掛了」。一週一則的成本極低，換掉這個盲點很划算。

### 2.3 停損規則 →「**`evaluate_exit_signals` 三維 + 跌破 MA20**」

| 規則 | 為什麼選 | 現成嗎 |
|---|---|---|
| `evaluate_exit_signals` 三維 | 唯一零價格參數的現成引擎；技術+籌碼+新聞綜合 | ✅ `exit_signals.py:236` |
| 跌破 MA20 | 純價格、與你畫面上的 K 線圖一致、解釋成本最低 | ✅ 均線計算全站都有 |

**刻意不做 ATR 移動停損（chandelier exit）**：它需要一個價格基準；沒有成本價就得改用
「近 N 日最高價 − k×ATR」，那是一支**全新的 L2 函式**（現有三支都以 `buy_price` 為基準，
改不了）。第一版先用現成的兩條，等你實際用過、覺得訊號不夠靈敏再加。§8.1 step 6。

---

## §3 §7 四點對齊

### 3.1 資料來源與單位

| 項目 | 來源 | 單位 |
|---|---|---|
| 觀察池代號 | 公開 CSV（Google Sheet 發布） | 字串 |
| 日 K（OHLCV） | `src.data.stock.picker_fetcher.fetch_stock_history_1y`（`picker_fetcher.py:37`，cron 已在用） | 價格＝**元**；量＝**股** |
| 技術轉空 | `compute_tech_bearish`（`exit_signals` 內） | bool + reasons |
| 20 日籌碼 | `analyze_20d_chips_from_df` | 字串 signal |
| 利空新聞 | `judge_news_sentiment` | label + confidence 0–100 |

⚠️ **單位陷阱**（§4.1）：`fetch_stock_history_1y` 回的是 `Close` 大寫欄名
（`tab_stock_grp.py:463` 實證），與部分 L1 回傳的小寫 `close` 不同。組字前要正規化。

### 3.2 發布延遲與 PIT

| 資料 | 延遲 | 對推播的意義 |
|---|---|---|
| TWSE 收盤 | 同日 ~14:30 TW，17:00 後完整 | cron 排 **UTC 09:00 = TW 17:00**，與 `update_macro_history.yml:15` 同步 |
| 三大法人 | 同日盤後 | 同上 |
| 新聞 RSS | 即時 | 無 |

**無 lookahead 風險**：推播只用「當下已發布」的資料做「當下的判斷」，不回填歷史。

⚠️ **已知限制沿用**（`push_daily_signals.py:14-15` 自陳）：cron 排 Mon–Fri，
**未濾台灣國定假日**（專案無第三方 trading calendar）。假日會推到「資料日未更新」的清單。
第一版沿用同樣行為，但訊息**必須標出資料日期**，讓你一眼看出是不是舊資料。

### 3.3 邊界條件

| 情境 | 處理 |
|---|---|
| CSV URL 未設定 | Fail loud：cron 直接 exit 1 + 明確錯誤訊息。**不可**靜默跳過 |
| CSV 抓到但空 | 推一則「觀察池是空的」而非靜默 —— 否則你分不出「沒訊號」與「清單掉了」 |
| 某檔抓不到 K 線 | 該檔記為「未評估」並列在訊息末尾，**不當作「沒訊號」** |
| **全部**抓不到 K 線 | Fail loud：推診斷訊息，不推「今日無觸發」 |
| 新上市（K 線 < MA20 所需長度） | 該檔標「歷史不足，未評估」（§4.6） |
| 停牌（連續無價） | 標「停牌」，**不可** ffill 後判斷（§1） |
| LINE token 缺 | `line_notify.py:34-37` 已 `raise ValueError`，沿用 |
| 訊息超過 LINE 上限 | `chunk.py` 已處理（4900 字 / 5 則） |

### 3.4 計算式

**規則 A：跌破 MA20**

設第 t 日收盤 $C_t$，20 日簡單移動平均：

$$MA20_t = \frac{1}{20}\sum_{i=0}^{19} C_{t-i}$$

觸發條件（**需要「昨天還在上面」以避免持續在下方時每天重複推播**）：

$$\text{trigger} = (C_t < MA20_t) \land (C_{t-1} \ge MA20_{t-1})$$

⚠️ 這個「**穿越**而非「**位於**」的設計是關鍵。若只判 $C_t < MA20_t$，
一檔跌破後盤整的股票會**連續數十天每天推一次**，三天內你就會關掉通知。

**規則 B：三維出場**

$$\text{score} = \mathbb{1}[\text{利空新聞}] + \mathbb{1}[\text{技術轉空}] + \mathbb{1}[\text{籌碼倒貨}]$$

（`exit_signals.py:266` 既有實作。）觸發門檻：**score ≥ 2**。

⚠️ **門檻 2 是我提的，需要你確認**。理由：score=1 太常見（三個維度任一都可能單獨亮），
會變成雜訊；score=3 太罕見，等到齊了通常已經跌完。但這**沒有實證依據** ——
`_LEVELS`（`exit_signals.py:267`）已有現成的分級語意，若你想直接用它的既有分界也可以。
確認後寫進 L0 `shared/`，docstring 註明來源為「user 裁示」。

**進場訊號**：第一版**不做**。理由見 §5。

---

## §4 模組切分與資料流

```
公開 CSV（觀察池代號）
      │
      ▼
scripts/push_watchlist_signals.py          [L6 cron entrypoint，新檔]
      │  · 讀 CSV → 代號清單
      │  · 逐檔 fetch_stock_history_1y     [L1，既有]
      │  ▼
src/compute/notify/watchlist_triggers.py   [L2 純函式，新檔]
      │  · evaluate_ma_cross(df)           ← 規則 A
      │  · 彙整 evaluate_exit_signals 結果 ← 規則 B（既有 L2）
      │  · 回 TriggerResult（含資料日期、未評估清單）
      ▼
src/compute/notify/watchlist_message.py    [L2 純函式，新檔]
      │  · 組 LINE 文字 + 深連結
      ▼
src/data/notify/dispatch.send_notification [L1，既有]
```

**依賴方向**：L6 → L1/L2，L2 之間同層互用，**零上行**。
**不碰 `src/ui/**`** —— headless cron 走 L5 會把整個 streamlit UI 鏈拉進來
（`push_daily_signals.py:46-48` 已踩過這個坑並修好，本檔沿用同樣紀律）。

### 深連結（層次 4「二次分析」的接點）

訊息中每檔附：

```
https://<你的 app>.streamlit.app/?sid=2330
```

`app.py` 開機閘門的 `_qp_sid` 還原（S1 那批**刻意保留**的那段）會讓使用者點進去
直接落在該股頁面。**閉環用一個 URL 就收，不需要 LINE webhook、不需要另架服務。**

⚠️ 需要一個新的 GitHub Secret 存 app base URL（不寫死在 code 裡）。

---

## §5 自評過度設計 —— 三件刻意不做的事

- ❌ **進場訊號**：第一版只做「你已經在看的股票出事了」。進場訊號牽涉
  `section_when_buy_sell` 的多條件組合，且誤報成本高（你會去買）。
  先讓停損警報跑一個月、確認訊號品質與推播節奏，再加進場。
- ❌ **LINE webhook 雙向互動**：需要公開 HTTPS 端點（Cloud Functions / Vercel），
  Streamlit 做不到。深連結已能達成「回網頁做二次分析」，先用它。
- ❌ **ATR chandelier 停損**：見 §2.3。

---

## §6 測試計畫

| 類型 | 內容 |
|---|---|
| 單元 | `evaluate_ma_cross` 的穿越判定（含「昨天在上、今天在下」與「連續兩天都在下」） |
| 邊界 | 空清單 / 單檔 / K 線不足 / 全部抓不到 / 停牌 / 資料日過舊 |
| 訊息 | 組字含資料日期、含深連結、未評估檔有列出；超長時分塊正確 |
| 分層 | 新檔不得 import `src.ui.*`（AST，比照 `test_t2_industry_concentration.py`） |
| 守衛 | cron script 不得 import streamlit UI 模組 |

### 三個最容易出錯的輸入（§6）

1. **連續在 MA20 下方** → 若寫成「位於」而非「穿越」，會每天重複推播直到你關通知。
2. **K 線剛好 20 根** → `MA20_{t-1}` 需要 21 根才算得出；差一根就 `IndexError` 或靜默回 NaN。
3. **CSV 有 BOM / 全形逗號 / 代號帶 `.TW` 後綴** → 代號對不上，整份清單靜默變成「查無資料」。
   必須正規化 + 對「一檔都沒對上」大聲報錯。

---

## §7 交付順序（§8.5 一次一個模組）

| 序 | 模組 | 產出 |
|---|---|---|
| 1 | L2 `watchlist_triggers.py` + 測試 | 純函式，可完整單測 |
| 2 | L2 `watchlist_message.py` + 測試 | 組字，含深連結 |
| 3 | L6 `scripts/push_watchlist_signals.py` | `--dry-run` 先跑通 |
| 4 | `.github/workflows/push_watchlist_signals.yml` | `workflow_dispatch` 手動先測 |
| 5 | 文件：`docs/` 設定步驟（CSV 發布 + Secret） | 你照著設定 |

---

## §8 需要你回覆的三件事

1. **§2 的三個預設**（CSV 來源 / 有訊號即推＋週一健康碼 / 兩條停損規則）—— 同意還是要換？
2. **三維出場的觸發門檻 `score ≥ 2`** —— 用我提的，還是沿用 `exit_signals._LEVELS` 的既有分界？
3. **你的 Streamlit app 正式網址** —— 深連結需要它（會存成 GitHub Secret，不寫進 repo）。

回覆後我開始跑 §7 的序 1。
