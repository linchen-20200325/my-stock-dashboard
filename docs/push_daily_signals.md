# 每日選股訊號推播（LINE / Telegram）

收盤後自動把**選股網綜合分前 N 名 + 技術面**推到你的手機。
選股走與網頁「🎯 開始選股」、每月凍結、MCP 同一支 `get_ranked_picks`（四處同源，數字一致）。

管道由環境變數 `NOTIFY_CHANNEL` 選：**`line`（預設）** 或 `telegram`。

## 訊息長這樣（每檔 2~3 行 + 選填 AI 研判）

```
📊 台股選股訊號 · 2026-07-25 17:00 · 前 10 名

🟢 6944 兆聯實業  綜合分 80.4 📈財報變好
  786元 · 距月線 +4.2% · RSI 55 · KD偏多 · 缺貨強
  籌碼 🔥 大戶吸籌 · 大戶45.2%↑
🟡 2316 楠梓電  綜合分 79.7 📉財報轉弱
  156元 · 距月線 -17.7% · RSI 38 · KD偏多 · 缺貨中
  籌碼 🔴 大戶倒貨

⚠️ 清單訊號，非買賣建議；🟢多頭排列 🟡未站上均線 ⚪資料不足。

────────────
🤖 AI 研判（僅整理上面客觀資料，非投資建議）
偏多：6944 兆聯實業（均線多頭 + 財報變好 + 大戶吸籌）…
偏空：2316 楠梓電（未站上均線 + 大戶倒貨）…
需觀察：…
```

- **行 1**：`趨勢燈 代碼 名稱  綜合分 財報趨勢徽章`
  - 🟢🟡⚪ = **客觀 MA 排列事實**（多頭排列 / 未站上均線 / 資料不足），**不是**買賣建議。
  - 📈財報變好 / ➡️財報持平 / 📉財報轉弱 = 近 5 季**毛利率↑ / 營益率↑ / 負債比↓ / 營收YoY↑** 的方向趨勢（favorable_count ÷ favorable_of ≥0.75 / ≤0.25）。資料不足 → 不顯示。
  - **中文名**：上市股走 TWSE 名稱表；上櫃股補 `get_stock_name`（涵蓋上市+上櫃）；真的查無 → 只顯代碼。
- **行 2**：`現價元 · 距月線% · RSI · KD方向 · 缺貨強/中/弱`
  - 技術面純用價格算；抓不到價 → 「技術資料不足」，**不腦補**。
  - 缺貨強/中/弱 = **當期缺貨動能強度**（合約負債增溫 / 存貨去化 / 毛利改善 / 營收成長）；非「vs 上次的增減」。資料不足 → 不顯示。
- **行 3（籌碼）**：`籌碼 {法人流向} · 大戶{比例}%{↑↓}` — 兩者皆抓不到 → **不印此行**（不佔版面）。
  - **法人流向** 🔥大戶吸籌 / 🔴大戶倒貨 / 🟡籌碼發散 = 近 20 日**外資+投信淨買 ÷ 總量**的集中度（TWSE T86 / 上櫃 TPEX，單位張）。
  - **大戶XX.X%↑↓** = 集保股權分散表 **>400 張大股東持股比例**（週更新；↑↓ 為對前一筆的週變化，平盤不加箭頭）。
- **🤖 AI 研判（選填）**：把上面**同一份客觀事實**餵 Gemini，分成 **偏多 / 偏空 / 需觀察** 各附一句理由。
  - **只研判餵進去的事實**、prompt 內硬性**禁止腦補任何數字/價位/新聞**、不下買賣點、結尾附非投資建議聲明（§2.1 Tier-5「AI 僅 synthesis」）。
  - 需設 `GEMINI_API_KEY`（見下方）；**未設 / AI 失敗 → 自動略過，只送清單**（AI 是加值、非主體）。

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

## 選填：開啟「🤖 AI 研判」

想在清單後面附一段 Gemini 幫你分 **偏多 / 偏空 / 需觀察**，多設一個 secret：

1. 到 **[Google AI Studio](https://aistudio.google.com/apikey)** 拿一組 **Gemini API key**（免費額度足夠每日一次）。
2. GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**：

| Secret | 值 |
|---|---|
| `GEMINI_API_KEY` | 步驟 1 的 API key |

- **沒設也沒關係**：排程會印一行「未設 GEMINI_API_KEY → 略過 AI 研判」然後只送清單，**不會紅燈**。
- AI **只研判推播裡那幾檔的客觀事實**（均線 / RSI / KD / 財報趨勢 / 缺貨 / 籌碼），prompt 內硬性禁止它腦補數字或建議買賣。

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
