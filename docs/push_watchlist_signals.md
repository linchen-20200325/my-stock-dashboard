# 觀察池訊號推播 — 設定步驟

盯**你自己在追蹤的股票**，有事才發 LINE。與 `push_daily_signals`（全市場選股排名）不同。

- 判定：`src/compute/notify/watchlist_triggers.py`（L2 純函式）
- 組字：`src/compute/notify/watchlist_message.py`（L2 純函式）
- 入口：`scripts/push_watchlist_signals.py`
- 排程：`.github/workflows/push_watchlist_signals.yml`

---

## 0. 先確認你是不是已經設好了

如果你**已經在跑週報**（`push_weekly_report`），那 CSV 與 LINE 憑證都設過了 ——
本支會自動沿用，你**只需要補 `APP_BASE_URL` 一個 secret**。

| Secret | 週報已設？ | 本支要不要另設 |
|---|---|---|
| `WEEKLY_WATCH_CSV_URL` | ✅ | 不用，自動沿用 |
| `LINE_CHANNEL_ACCESS_TOKEN` / `LINE_USER_ID` | ✅ | 不用，共用 |
| `FINMIND_TOKEN` | ✅ | 不用，共用 |
| **`APP_BASE_URL`** | ❌ | **要**（深連結用；不設則訊息不附連結） |
| `WATCHLIST_CSV_URL` | — | 只有在你想讓「週報」與「觀察池提醒」盯**不同清單**時才需要 |

清單來源優先序：`--csv-url` > `WATCHLIST_CSV_URL` > `WEEKLY_WATCH_CSV_URL`。
執行時 log 會印出這次用的是哪一條，可據此確認。

> 為什麼沿用而不是另發一份：`WEEKLY_WATCH_CSV_URL` 指的就是「你發布出來的追蹤清單」，
> 與觀察池是同一個東西。要求你發布第二份只會製造兩份會漂移的清單。

**若以上都已設好 → 直接跳到 §3 手動跑一次。**

---

## 1. 把觀察池發布成 CSV（**尚未設過週報才需要**）

系統無法用你網頁上的 Google 登入身分去讀 Sheet —— OAuth token 活在瀏覽器 session，
GitHub Actions 拿不到。所以走「發布為 CSV」這條公開唯讀連結。

**這對你沒有隱私問題**：個股觀察池的 schema 是
`name | ticker | updated_at`（`gsheet_portfolio.py:60`，`:56-58` 註解明寫
「§1 反捏造：只存三欄，**無張數/均價**」）。發布出去只會讓人知道你在看哪幾檔，
**不會洩漏任何部位大小**。

> ⚠️ 只發布 **`stock_watchlist`** 這一個分頁。
> **不要**整份試算表發布 —— `portfolios` 分頁含張數與均價，那個發布出去等於公開部位。

步驟：

1. 開啟你的觀察池 Google Sheet
2. 檔案 → 共用 → **發布到網路**
3. 左邊下拉選 **`stock_watchlist` 分頁**（不是「整份文件」）
4. 右邊格式選 **逗號分隔值 (.csv)**
5. 按「發布」，複製產生的連結

連結長這樣（結尾是 `output=csv`）：

```
https://docs.google.com/spreadsheets/d/e/2PACX-xxxxx/pub?gid=0&single=true&output=csv
```

> 如果複製到的是 `pubhtml` 結尾，那是網頁版不是 CSV —— script 會偵測到並報錯，
> 不會靜默送出殘缺清單。

---

## 2. 設定 GitHub Secrets

Repo → Settings → Secrets and variables → Actions → New repository secret

| Secret | 值 | 必要 |
|---|---|---|
| `APP_BASE_URL` | `https://my-stock-dashboard-namd8rh9b8sn3qzdjshzfa.streamlit.app/` | **這個要新設** |
| `WEEKLY_WATCH_CSV_URL` | 追蹤清單 CSV 連結 | ✅（週報已設，共用） |
| `WATCHLIST_CSV_URL` | 只有想盯不同清單時才設 | 選填 |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API token | ✅（已有） |
| `LINE_USER_ID` | 你的 LINE user id | ✅（已有） |
| `FINMIND_TOKEN` | FinMind token | 建議（已有） |

`APP_BASE_URL` 是深連結用的。沒設定的話訊息照送，只是**不附連結** ——
不會印一個壞掉的 URL。

LINE 憑證的申請步驟見既有的 `docs/push_daily_signals.md`，這支共用同一組。

---

## 3. 先手動跑一次確認

Repo → Actions → 「觀察池訊號推播」→ Run workflow：

- `dry_run` 勾 **true** → 只在 Actions log 印訊息，**不送 LINE**
- 確認 log 裡的清單、資料日期、觸發判定都合理
- 再取消勾選跑一次真的送

本地測試（不需要 LINE 憑證）：

```powershell
$env:WATCHLIST_CSV_URL = "你的 CSV 連結"
python scripts/push_watchlist_signals.py --dry-run
```

---

## 4. 排程與觸發規則

| 排程 | 時間 | 行為 |
|---|---|---|
| 平日 | `0 9 * * 1-5`（TW 17:00） | **只在有觸發時推**，沒事完全不發 |
| 週一 | `30 9 * * 1`（TW 17:30） | 加 `--health-check`，沒訊號也送一則狀態 |

**為什麼平日沒事不發**：收到 = 真的要看。每天發「今日無觸發」會在三週內
把你訓練成不看它。

**為什麼週一要發健康碼**：純事件驅動的盲點是「連續五天沒消息」時，
你分不出是市場平靜還是 cron 三天前就掛了。一週一則成本極低，換掉這個盲點很划算。

### 觸發條件

| 規則 | 說明 |
|---|---|
| 跌破 MA20 | 用「**穿越**」判定（昨天在線上、今天在線下），不是「位於線下」。否則跌破後盤整的股票會連續數十天每天推一次 |
| 技術面轉空 | `compute_tech_bearish`：含強訊號（空頭排列 / 週 MACD 翻負）或 ≥2 條警示 |
| 三維出場 | 技術 + 籌碼 + 新聞，達「🟠 建議減碼」（score ≥ 2）才推 |

> **v1 的已知限制**：三維出場通常只評得到 1 維（技術面）——
> 籌碼維度需要 `外資`/`投信` 欄，而 cron 用的 K 線來源不回這兩欄；
> 新聞維度需要 Gemini。訊息會明確標示「只評估了 N/3 維」，不會假裝評過三維。

---

## 5. 訊息會告訴你什麼

四種訊息型態，**刻意區分**：

| 情況 | 訊息 |
|---|---|
| 有觸發 | 🔔 逐檔列原因 + 深連結 + 未評估清單 |
| 沒觸發（僅週一） | ✅ 「本週監控 N 檔，目前無觸發」 |
| **全部抓不到 K 線** | 🚨 「**沒有做任何判斷**，這不等於今天沒事」+ exit 1（cron 紅燈） |
| **觀察池是空的** | ⚠️ 「讀到 0 檔，**沒有監控任何東西**」 |

後兩種是 §1 的重點：**「全部失敗」絕不可被說成「全部安全」**。
你會依據那句話決定今天不看盤，而實際上系統根本沒監控到任何東西。

未評估的檔（新上市歷史不足、停牌、抓不到）會逐檔列在訊息末尾，
標註「**不代表沒事**」，不會被靜默吞掉。

---

## 6. 深連結

訊息中每檔附 `{APP_BASE_URL}?sid={代號}`。點進去直接落在該股頁面 ——
`app.py` 開機閘門的 `_qp_sid` 還原會接住它。

這是「收到提醒 → 回網頁做二次分析 → 自己決定買賣」的閉環，
**用一個 URL 就收，不需要 LINE webhook、不需要另架任何服務**。
