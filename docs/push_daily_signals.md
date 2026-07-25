# 每日選股訊號推播（LINE / Telegram）

收盤後自動把**選股網綜合分前 N 名 + 技術面**推到你的手機。
選股走與網頁「🎯 開始選股」、每月凍結、MCP 同一支 `get_ranked_picks`（四處同源，數字一致）。

管道由環境變數 `NOTIFY_CHANNEL` 選：**`line`（預設）** 或 `telegram`。

## 訊息長這樣

```
📊 台股選股訊號 · 2026-07-25 17:00
綜合分前 10 名

🟢 2330 台積電  綜合分 88
  基本面: 估值 76 · EPS 90 · 跨季 82
  技術面: 現價 592 · 距MA20 +2.3% · RSI 61 · KD偏多 · MACD柱 +0.80
🟡 2317 鴻海  綜合分 71
  基本面: EPS 70 · RS 65
  技術面: 現價 105 · 距MA20 -0.8% · RSI 48 · KD偏空 · MACD柱 -0.10

⚠️ 清單訊號，非個人化買賣建議；🟢多頭排列 🟡未站上均線 ⚪資料不足。
```

- 🟢🟡⚪ = **客觀 MA 排列事實**（多頭排列 / 未站上均線 / 資料不足），**不是**買賣建議。
- 技術面純用價格算（MA / 乖離 / RSI / KD / MACD）；抓不到價的股標「技術資料不足」，**不腦補**。

---

## 方案 A：LINE（預設，Messaging API）

> ⚠️ **LINE Notify 已於 2025-03-31 停用**，那個一行推播的簡單服務沒了。現在推 LINE 要用 **Messaging API**，步驟比 Telegram 多幾步。

### 1. 建 LINE 官方帳號 + 拿 Channel access token
- 到 **[LINE Developers Console](https://developers.line.biz/)** 登入 → 建一個 **Provider** → 建一個 **Messaging API channel**（= 一個官方帳號，免費）。
- 在該 channel 的 **Messaging API** 頁 → 發一組 **Channel access token（long-lived）**。

### 2. 拿你自己的 userId
- 用手機 LINE **加這個官方帳號為好友**（掃 channel 頁的 QR code）。
- userId 取得方式（擇一）：
  - Developers Console → channel → **Basic settings** 底部「Your user ID」；或
  - 對官方帳號傳一句話 → 到 channel 的 webhook / [官方 Bot 設計工具](https://developers.line.biz/) 觀察傳入事件的 `source.userId`（形如 `U1234...`）。

### 3. 設 GitHub Secrets
GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**：

| Secret | 值 |
|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | 步驟 1 的 token |
| `LINE_USER_ID` | 步驟 2 的 userId（`U...`） |

（`NOTIFY_CHANNEL` 預設就是 `line`，不必設。）

---

## 方案 B：Telegram（備援，設定較簡單）

若覺得 LINE 太麻煩，可改用 Telegram：

1. Telegram 搜 **@BotFather** → `/newbot` → 拿 **bot token**。
2. 對新 bot 傳一句話 → 開 `https://api.telegram.org/bot<token>/getUpdates` → 找 `"chat":{"id":數字}` = **chat id**。
3. GitHub Secrets 新增 `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`。
4. GitHub repo → **Settings → Secrets and variables → Actions → Variables** 新增 **`NOTIFY_CHANNEL` = `telegram`**（切換到 Telegram）。

> 沒設對應管道的 secret，排程會 **fail-loud**（紅燈）提醒你；設好即每個交易日自動推。

---

## 執行時間

- 排程：**每週一～五 UTC 09:00 = 台灣 17:00**（收盤後、當日盤後資料齊）。
- 手動測：GitHub repo → **Actions → 每日選股訊號推播 → Run workflow**（可填 `top_n` / `factors`）。

## 本地測（不送、只印）

```bash
python scripts/push_daily_signals.py --dry-run --top-n 5
# 指定因子：--factors eps_high,trend,rs_leader
```

## 邊界與限制

- **fail-loud（§1）**：季快照未就緒 / 存活池空 → 推「今日無訊號 + 原因」，**不偽造清單**。
- **⚠️ 未濾國定假日**：排程 Mon–Fri，未排除台股國定假日（本專案無第三方 trading calendar）。假日會推一份「資料日期未更新」的清單 —— 訊息抬頭的 `as_of` 日期可辨識。
- **唯讀**：只推訊號，不下單。
