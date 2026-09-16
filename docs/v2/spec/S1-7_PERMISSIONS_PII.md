# 階段 1 交付物 #7｜權限與機敏資料清單

**交付組**：權限與機敏資料組（單組）
**日期**：2026-09-14
**範圍**：`/home/user/my-stock-dashboard`（唯讀盤點，未修改 repo 任何檔案，未執行 git 寫入）
**方法**：靜態讀碼 + grep 全庫（`src/` `app.py` `scripts/` `infra/` `shared/` `.github/workflows/` `.streamlit/`）

> ⚠️ **本報告全部由單一組產出，未經第二組獨立複驗**（CLAUDE.md §-2 規則 6）。
> 凡標示「**確認會 / 確認不會**」者，均附 `file:line` 或 `file:符號名`，那些是**實測事實**；
> 但「**已窮舉、沒有其他路徑**」這類**全稱句**一律標為 **未複驗**，依 §-2 規則 6 只能當**待驗事項**，
> **不得**作為後續動作的前提，也**不得**寫進 commit message／PR 描述當成已完成的事實。

> ⛔ **本報告不含任何實際憑證內容**。所有條目只記「名稱 / 位置 / 取得管道 / 誰讀它」。
> 盤點過程中**未發現**任何真實金鑰被複製或需要複製的情形（詳見 §1.0）。

---

## §1 憑證與金鑰清單

### §1.0 先講最重要的一件事：**工作樹中查無硬編碼憑證**

實測四組 pattern，全庫（含 `.toml` / `.json` / `.yml`）掃描結果：

| Pattern | 意義 | 命中 |
|---|---|---|
| `eyJ[A-Za-z0-9_-]{20,}` | JWT（FinMind token 形態） | **0** |
| `AIza[A-Za-z0-9_-]{10,}` | Google API key | **5，全在 `tests/test_ai_qa_service.py:301-328`，值為明顯假值** |
| `googleusercontent.com` | OAuth client_id | **0** |
| `GOCSPX` | Google client_secret | **0** |

- `.streamlit/secrets.toml` **不存在於磁碟**，且 `git log --all -- .streamlit/secrets.toml` **0 命中**（從未被 commit）。
- `.gitignore:1-2` 已擋 `.streamlit/secrets.toml`。
- ⚠️ **一個值得追問的歷史線索**：`.gitignore:4-6` 有一條註解寫
  `# Notebook (contains hardcoded API keys)` + `*.ipynb`。實測：磁碟上 **0 個 `.ipynb`**，
  且 `git log --all --diff-filter=A -- '*.ipynb'` **0 命中**（本 repo 歷史中從未加入過 notebook）。
  → **本 repo 內無此問題**；該行可能是從姊妹 repo 沿用的樣板。**但這句 gitignore 註解的來歷本身未查證。**
- ✅ **良好實例**：`src/data/core/data_loader.py:349-350` 明確註明「不再印 token 前綴片段 —— 憑證材料不入 log」，只印長度。

> ⚠️ **未複驗的全稱句**：「工作樹中沒有硬編碼憑證」是上述四組 pattern 的掃描結果。
> **未掃 git 歷史的全部 blob**（只掃了 `.ipynb` / `secrets.toml` 兩個路徑的歷史）。
> 若要宣稱「歷史中也沒有洩漏過」，**必須另跑一次 full-history secret scan**（如 `gitleaks` / GitHub secret scanning），
> 本輪**沒有做**。

### §1.1 憑證清單

取得管道欄位說明：`S`=`st.secrets`、`E`=`os.environ`、`GH`=GitHub Actions Secret、`UI`=使用者在畫面輸入。

| # | 名稱 | 讀取位置（`file:符號名`） | 用途（打哪） | 取得管道 | 缺它會怎樣 |
|---|---|---|---|---|---|
| 1 | `FINMIND_TOKEN` | `src/config/config.py::get_finmind_token`（+ 同檔 module-level `FINMIND_TOKEN`）<br>`src/data/core/data_loader.py:339`（`StockDataLoader.__init__`） | FinMind API（`api.finmindtrade.com`） | S > E；GH（多支 workflow） | ⚠️ **靜默降級**（見 §1.2-a） |
| 2 | `FM_TOKEN` | `src/data/stock/monthly_revenue_fetcher.py:47-49`<br>`src/data/stock/quarterly_financials_fetcher.py:58`<br>`src/data/core/data_loader.py:750` | 同上（#1 的 **別名** fallback） | E only | 回空 → 上游 fetcher 印 log 回空 dict |
| 3 | `FINMIND_USER` | `src/data/core/data_loader.py:341` | FinMind 帳密登入（token 缺時的第二路） | **E only（不讀 `st.secrets`）** | 落到匿名模式 |
| 4 | `FINMIND_PASSWORD` | `src/data/core/data_loader.py:342` | 同上 | **E only（不讀 `st.secrets`）** | 同上 |
| 5 | `GEMINI_API_KEY` | `src/services/app_ai_service.py::get_gemini_api_key`<br>`src/ui/pages/sidebar_health.py::_call_gemini_brief`<br>`src/ui/tabs/tab_ai_chat.py::_secret`<br>`scripts/push_holdings_daily.py::_maybe_ai_summary:136` | Google Gemini（`generativelanguage.googleapis.com`） | S > E；GH | 回警告字串（見 §1.2-b） |
| 6 | `GEMINI_API_KEY_2` … `_6` | `src/services/app_ai_service.py::GEMINI_KEY_NAMES` / `gemini_keys()` | **Gemini 金鑰池**（round-robin + 429/403 換 key） | S > E | 池變小，不影響功能 |
| 7 | `FRED_API_KEY` | `src/ui/tabs/tab_edu.py:294-295`<br>`src/ui/tabs/macro/section_long_term.py:90-91`<br>`src/ui/tabs/tab_macro.py:518,608`<br>`src/ui/pages/health_inspector.py:501-502` | FRED（美國聯準會經濟數據） | E > S | 回空字串 → 該資料源不可用 |
| 8 | `google_oauth.client_id` | `src/data/portfolio/oauth_state.py::_resolve_oauth_cfg` | Google OAuth 2.0 | **S 或 `st.session_state['custom_oauth_cfg']`（UI 精靈）** | `is_oauth_configured()` 回 False → 走 SA 或報錯 |
| 9 | `google_oauth.client_secret` | 同上 | 同上 | **S 或 UI（見 §1.2-c ⚠️）** | 同上 |
| 10 | `google_oauth.redirect_uri` | 同上 | 同上 | S 或 UI | 同上 |
| 11 | OAuth `access_token` / `refresh_token` / `id_token` | `src/data/portfolio/oauth_state.py:225`（寫 `st.session_state['gsheet_tokens']`）<br>`infra/oauth.py::exchange_code_for_tokens` / `refresh_access_token` | Google Sheets / Drive | **執行期由 Google 簽發**，存 `st.session_state`（**不落地**，見 §2.2） | 未登入 → `_oauth_active()` False |
| 12 | `gcp_service_account`（SA JSON，含 `private_key`） | `src/data/portfolio/gsheet_portfolio.py:205`（`_build_client`） | Google Sheets + **Drive 全權** | S | `_sa_configured()` False → `RuntimeError` **fail loud** ✅ |
| 13 | `GCP_SERVICE_ACCOUNT_JSON` | `src/data/portfolio/gsheet_sa_reader.py::load_sa_credentials` | 同上（cron headless 路徑） | GH（`push_holdings_daily.yml`） | 見該檔 fail-loud 邏輯 |
| 14 | `PROXY_URL` | `src/data/proxy/proxy_helper.py::get_proxy_config` | NAS Squid proxy（台灣 IP 出口） | S > E；GH | 回 `None` → **降級直連**（見 §1.2-d） |
| 15 | `NAS_PROXY_URL` | 同上（`PROXY_URL` 的別名） | 同上 | S > E | 同上 |
| 16 | `[proxy]` section：`username` / `password` / `endpoint` | `src/data/proxy/proxy_helper.py:84-86`（舊格式分支） | 同上 | S | 同上 |
| 17 | `HTTP_PROXY` / `http_proxy` | `src/data/proxy/proxy_helper.py:300-303`（最後 fallback） | 同上 | E | 同上 |
| 18 | `NAS_API_KEY` | `src/data/proxy/proxy_helper.py:301,307`（client 端）<br>`src/data/proxy/nas_server.py:53`（server 端 `_API_KEY`） | NAS 中繼站自建認證 | S/E；GH | ⚠️ **server 端變成無認證開放**（見 §1.2-e，**本報告最高風險項之一**） |
| 19 | `NAS_BASE_URL` / `NAS_RELAY_URL` | `src/data/proxy/proxy_helper.py:300,306` | NAS 中繼站位址 | S/E；GH | `nas_relay_fetch` 回 None → fallback 鏈 |
| 20 | `LINE_CHANNEL_ACCESS_TOKEN` | `src/data/notify/line_notify.py:32` | LINE Messaging API（`api.line.me`） | E；GH | **raise fail loud** ✅（`line_notify.py:36`） |
| 21 | `LINE_USER_ID` | `src/data/notify/line_notify.py:33` | LINE 推播收件人（**= 使用者識別碼，見 §2**） | E；GH | 同上 raise ✅ |
| 22 | `TELEGRAM_BOT_TOKEN` | `src/data/notify/telegram_notify.py:28` | Telegram Bot API | E；GH | raise ✅（`telegram_notify.py:32`） |
| 23 | `TELEGRAM_CHAT_ID` | `src/data/notify/telegram_notify.py:28-32` | Telegram 收件人（**使用者識別碼**） | E；GH | 同上 raise ✅ |
| 24 | `PORTFOLIO_SHEET_ID` | `src/data/portfolio/gsheet_portfolio.py::PORTFOLIO_SHEET_KEY`（`portfolio_sheet_id`） | 指向客戶持股帳本 | S / `session_state` / GH | 相關功能停用 |
| 25 | `STOCK_PORTFOLIO_SHEET_ID` | `src/data/portfolio/gsheet_portfolio.py::STOCK_PORTFOLIO_SHEET_KEY` | 指向客戶個股帳本 | `session_state` only / GH | 同上 |
| 26 | `WATCHLIST_CSV_URL` | `scripts/push_watchlist_signals.py:123` | **客戶「發布到網路」的觀察清單 CSV**（見 §2.5 ⚠️） | E；GH | exit 1 fail loud ✅ |
| 27 | `WEEKLY_WATCH_CSV_URL` | `scripts/push_weekly_report.py:150` | 同上 | E；GH | exit 1 ✅（`:152`） |
| 28 | `APP_BASE_URL` | `scripts/push_watchlist_signals.py:104` | 推播深連結網址 | E；GH | 不附連結（無害） |
| 29 | `GITHUB_TOKEN` | `.github/workflows/export_db.yml:26` | force-push `data` 分支 | GH 內建 | workflow 失敗 |

### §1.2 §1「Fail Loud」合規判定（逐項）

**(a) ⚠️ `FINMIND_TOKEN` 缺失 → 靜默降級（憲法 §1 邊緣違規）**
`src/data/core/data_loader.py:357-358`：
```
else:
    print('[FinMind] ℹ️  匿名模式（每小時600次）')
    self._token = ''
```
缺 token 時**不 raise**，改用匿名額度繼續跑。
**判定：技術上有 log，不算「沉默」，但屬「降級後照常回資料」** —— 使用者看到的畫面不會顯示
「這份資料是在額度受限模式下取得的」。同檔 `:359-361` 的 `except Exception as e: print(...)`
把**登入失敗**也吞成 log。⚠️ 這兩處**不是** `except: pass`（有 log，比 §1 明文禁止的形態好），
但**下游消費端無法區分「正常取得」與「降級取得」**。
**未複驗**：我**沒有**追完每個 FinMind consumer，不確定是否有某處會因此顯示不完整資料而不自知。

**(b) `GEMINI_API_KEY` 缺失 → 回警告字串而非 raise**
`src/services/app_ai_service.py::gemini_call` 開頭：無 key 時 `return '⚠️ 請設定 GEMINI_API_KEY…'`。
**判定：合規**（§1 允許「誠實回報失敗」；呼叫端如 `etf_tab_ai.py:326` 以
`if result and not result.startswith('⚠️')` 判別並顯示錯誤，不會把警告字串當成 AI 回答渲染）。
`scripts/push_holdings_daily.py::_maybe_ai_summary:136-139` 同理 —— 缺 key 只印 log、**規則式訊息照送**，
AI 是加值非主體。✅

**(c) ⚠️ OAuth `client_secret` 可由**使用者在畫面輸入**並存進 `session_state`**
`src/data/portfolio/oauth_state.py::_resolve_oauth_cfg` 的第二順位是
`st.session_state.get("custom_oauth_cfg")`（in-app wizard）。
→ client_secret 會**以明文存在 Streamlit session 記憶體中**，且是**使用者自行貼上**的。
**判定：不是 bug，是設計取捨**（讓沒有部署權限的使用者也能自帶 OAuth Client），
但 v2 應評估是否保留（見 §6-G7）。

**(d) `PROXY_URL` 缺失 → 降級直連**
`src/data/proxy/proxy_helper.py::get_proxy_config` 回 `None` → 呼叫端直連。
**判定：合規且刻意** —— `proxy_helper.py:87-94` 已於 v18.343 把原本的 silent pass 改為印 stderr，
註解明確區分「(a) 合法降級」與「(b)(c) config 寫錯，admin 該看到」。✅ **這是本 repo 的正面實例。**

**(e) 🔴 `NAS_API_KEY` 缺失 → NAS 中繼站「無認證開放」（最高風險項）**
`src/data/proxy/nas_server.py:79`：
```
def _auth(x_api_key: str = Header(None)):
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
```
`_API_KEY` 為空字串時，`if _API_KEY and ...` 整個短路 → **`_auth` 變成 no-op，任何人都能通過**。
`nas_server.py:58-65` 會印一段大聲警告（✅ 符合 §1 精神），但**程式照常啟動並對外服務**。
檔內註解自陳這是**已知且刻意**的：「硬性『未設 key 拒絕啟動』屬部署行為變更，列 user 決定」。
**風險**：`/proxy` 與 `/api/fetch` 成為開放中繼（SSRF 跳板）。
**已有的緩解**：`_assert_public_url` 封鎖內網／metadata 目標（同註解所述，**我未逐行複驗該函式的完整性**）。
**判定：這是部署期風險，不是 code bug；但它是本次盤點中唯一「缺憑證 → 安全邊界消失」的項目。**

**(f) 推播憑證缺失 → raise，✅ 完全合規**
`line_notify.py:36` / `telegram_notify.py:32` 均在缺 token/收件人時 raise，
`push_holdings_daily.py:270` 註解明確寫「secret 缺 → raise → exit 1」。**cron 會紅燈，不會假裝送出。** ✅

---

## §2 使用者個人資料（PII）盤點

| # | 資料項 | 存在哪 | 誰能讀 | 有沒有離開本機 |
|---|---|---|---|---|
| 1 | **持股明細**：`ticker` / `lots`(張數) / `avg_price`(成本均價) / `updated_at` | 客戶自己的 **Google Sheet**，worksheet `portfolios`（schema 見 `gsheet_portfolio.py:_HEADERS`） | 客戶本人（OAuth）；**SA 的 `client_email`**（需客戶主動分享）；GitHub Actions runner | ✅ **會**（見 §3） |
| 2 | **個股觀察清單**：`name`/`ticker`/`updated_at`（**無價格**，物理隔離於獨立 worksheet） | 同上，worksheet `stock_watchlist`（`_STOCK_WATCHLIST_HEADERS`） | 同上 | ✅ **會**（見 §3.4） |
| 3 | **前進式驗證凍結紀錄** `cohort/stock_id/name/entry_price/factors/frozen_at` | ① Sheet worksheet `forward_test_picks`；② **git 追蹤的** `data_cache/forward_test/picks.parquet`（實測 60 列） | 凡能讀 repo 者 | ⚠️ **已 commit 進 git**（見 §2.4） |
| 4 | **OAuth token bundle**（access / refresh / id_token） | `st.session_state['gsheet_tokens']`（`oauth_state.py:225`） | 該 Streamlit session 的伺服器行程 | ❌ **不落地**（見 §2.2） |
| 5 | **客戶 Google 帳號 email** | `st.session_state['gsheet_email']`（`oauth_state.py:226`，來自 `decode_id_token_email`） | 同上；畫面顯示於 `app.py:347` | ❌ 未外送（見 §2.3） |
| 6 | **Sheet ID**（`portfolio_sheet_id` / `stock_portfolio_sheet_id`） | `st.secrets` / `session_state` / GH Secret / **OAuth `state` 參數（進 URL）** | 同上 + 瀏覽器歷史／中介 log | ⚠️ 見 §2.6 |
| 7 | **LINE 收件人 ID** `LINE_USER_ID` / **Telegram** `TELEGRAM_CHAT_ID` | GH Secret → runner 環境變數 | GitHub Actions | 送往 LINE／Telegram（本來就是收件端） |
| 8 | **健康度追蹤清單** `stocks[]` | `data_cache/health_watchlist.json`（**git 追蹤**） | 凡能讀 repo 者 | ⚠️ **目前 `stocks` 為空陣列**（見 §2.4） |
| 9 | **客戶「發布到網路」的觀察清單 CSV** | 客戶 Google Sheet 的 publish-to-web URL | ⚠️ **任何拿到該 URL 的人，無需 Google 登入** | 見 §2.5 |

### §2.1 持股明細的完整生命週期（本節核心）

```
客戶在 📁 組合管理頁輸入 張數/均價
    → src/ui/etf/etf_tab_portfolio.py:274-295（收 _lots / _avg_price）
    → gsheet_portfolio.save_portfolio()  → 客戶自己的 Google Sheet
    ↓（讀回）
   ┌─ 互動路徑：OAuth → _build_client() → Streamlit 行程記憶體
   └─ cron 路徑：gsheet_sa_reader.read_holdings()（Service Account）
                 → GitHub Actions runner（GitHub 代管，位於美國）
```
⚠️ **cron 路徑的意義**：`scripts/push_holdings_daily.py` 每個交易日（TW 06:30）在
**GitHub 的伺服器上**完整讀出客戶的 `ticker` + `lots` + `avg_price`
（`gsheet_sa_reader.py::read_holdings` 回 `[{ticker, lots, avg_price}, ...]`）。
→ **客戶的成本價每天都會存在於 GitHub Actions runner 的記憶體中**。這是既有設計的必然結果，不是 bug，
但它是「資料離開客戶掌控範圍」的**第一個**節點。

### §2.2 ✅ OAuth token **不落地**（正面發現）

實測：`grep -rn "gsheet_tokens|refresh_token" src/ app.py | grep -iE "json.dump|open\(|write|pickle|to_parquet|save"` → **0 命中**。
token 只存在於 `st.session_state`（行程記憶體），`app.py:351` 於登出時清除
`('gsheet_tokens', 'gsheet_email', '_oauth_state')`。
→ **App 重啟即失效，磁碟上不留 refresh_token。** ✅

### §2.3 ✅ email 未外送

`gsheet_email` 僅 4 處引用（`oauth_state.py:226,239`、`app.py:347,351`），全部是
「存進 session」「顯示在 sidebar」「登出清除」。**確認不會**進任何 prompt 或推播。

### §2.4 ⚠️ git 追蹤的兩份使用者相關檔案

`git ls-files data_cache/` 實測含：
- **`data_cache/forward_test/picks.parquet`** — 60 列，欄位 `cohort/stock_id/name/entry_price/factors/frozen_at`。
  **這是選股演算法的輸出（凍結排名），不是客戶持股**。但它揭露「這個系統在哪些月份挑了哪些股票」。
  ⚠️ CLAUDE.md §-1.5.F 判定 3(5) 已明文把此檔列為「**無法重建、刪除須請示**」的凍結歷史快照。
- **`data_cache/health_watchlist.json`** — 實測 `stocks: []`（**目前為空**）。
  檔內 `_說明` 自陳「清單為空 = 功能待命不跑（不會腦補您的持股）」。
  ⚠️ **設計上就是要 user 把代碼填進去再 commit**（`update_health_history.yml:14,17,22` 確認此流程）。
  → **一旦客戶填入，他關注的股票清單就會被 commit 進 git 歷史（不可撤回）。**

### §2.5 🔴 觀察清單以「發布到網路」方式對外（重要發現）

`scripts/push_weekly_report.py:4` 與 `scripts/push_watchlist_signals.py:32` 明文寫：
> `WATCHLIST_CSV_URL  你的觀察池 Google Sheet「發布為 CSV」連結`
> `追蹤清單來源 = 使用者「發布到網路」的 Google Sheet CSV`

Google 的「發布到網路（Publish to web）」會產生一個 **無需任何驗證即可存取** 的公開 URL。
→ **客戶的觀察清單實質上是公開的**，只是 URL 不易猜到（security by obscurity）。
URL 本身存為 GitHub Secret（受保護），但**被發布的那份 Sheet 內容本身不受 Google ACL 保護**。
**判定：確認為現行架構（非 bug），但這是 v2 最該重新檢討的隱私決策之一**（見 §6-G3）。

### §2.6 ⚠️ Sheet ID 會進入 URL query string

`src/data/portfolio/oauth_state.py`（`_STATE_SEP` 附近的 P2 v19.206 區塊）讓 Sheet ID
「搭 OAuth `state` 的便車」往返 Google。程式碼**自己已經評估過風險**並寫明三條前提：
① 只有 Sheet ID 上車，**refresh_token 等憑證永不進 state/URL**；② CSRF nonce 不被稀釋；
③ Sheet ID 當不可信輸入，經 `_sanitize_sheet_id` 過濾。
**判定：風險已被主動識別並緩解，屬可接受的設計。** 但 Sheet ID 仍會出現在
瀏覽器歷史、Google 的 OAuth 請求 log、以及任何中介的 access log 中。

---

## §3 ⚠️ 個人資料的外流路徑（本節最重要）

> **結論先講**：**客戶的持股明細（含成本均價、絕對金額損益、組合總現值）確認會被送到 Google Gemini。**
> 最嚴重的單一出口是 `src/ui/etf/etf_tab_ai.py::_generate_report`。

### §3.1 🔴 出口點 A — ETF 組合 AI 報告（**完整財務揭露，本報告最高風險發現**）

**位置**：`src/ui/etf/etf_tab_ai.py::_generate_report`（prompt 組裝 `:117-124`、`:218-224`、`:240-241`；送出 `:294`）
**接收方**：Google Gemini（`generativelanguage.googleapis.com`，經 `app_ai_service.gemini_call`）
**觸發**：使用者點「生成 AI 組合戰情研判報告」按鈕（非自動）

**確認會送出的欄位**（逐字自 code）：

| 來源行 | 欄位 | 敏感度 |
|---|---|---|
| `:218` | **組合總現值 `{total_value}` 元**（絕對新台幣金額） | 🔴 **等同揭露這個組合的淨值** |
| `:119` | 每檔 **持有股數 `shares`** | 🔴 部位大小 |
| `:119` | 每檔 **均價 `avg_price`**（成本價） | 🔴 **成本基礎** |
| `:120` | 每檔現價 `current_price` | 🟡 公開市場資料 |
| `:121` | 每檔 **資本利得 `capital_gain_pct` %　+　`capital_gain` 元**（絕對金額） | 🔴 **絕對損益金額** |
| `:122` | 每檔 **近1年已領配息 `dividend_received` 元**（絕對金額） | 🔴 **股利收入** |
| `:123` | 目標比例／實際比例／偏離 pp | 🟡 |
| `:117` | ticker + `role`（核心／衛星） | 🟡 |
| `:240-241` | **再平衡指令含 `金額(元)`**（絕對新台幣金額） | 🔴 |
| `:219-220` | 壓力測試 `loss_pct` | 🟡 |

→ **判定：確認會。** 這是本 repo 中**唯一**把「股數 + 成本價 + 絕對金額」同時送出的路徑。

### §3.2 🟠 出口點 B — 存股戰情室 AI 摘要（部分財務資料）

**位置**：`src/services/dividend_station_service.py::build_summary_prompt`（`:988-1040`）
**兩個呼叫端**：
- 互動：`src/ui/views/page_hold.py:3076-3077`（`build_ai_summary` + 注入 `gemini_call`）
- **cron**：`scripts/push_holdings_daily.py::_maybe_ai_summary:144-149`（`post_gemini`）
  → ⚠️ **這條是自動的**，每交易日 TW 06:30 無人值守執行。

**確認會送出**：

| 行 | 欄位 | 敏感度 |
|---|---|---|
| `:1005` | 健檢紅燈持股的 **代號 + 建議動作** | 🔴 **揭露持有哪些股票** |
| `:1006` | 235 加碼觸發的 代號 + 燈號 + `加碼金` | 🟡 |
| `:1004` | **有效判斷檔數**（＝持股檔數） | 🟡 組合規模 |
| `:1013-1015` | **實際配置：核心 X% / 衛星 Y% / 偏離 Z%** | 🟠 資產配置比例 |
| `:1019` | 停利清單：**代號 +（+損益%）** | 🔴 **逐檔報酬率** |
| `:1023-1025` | 換出（你持有的紅燈汰弱）／換入 代號 | 🔴 |

**✅ 確認不會送出**（實測 `:993-1040` 全段）：
`張數`、`均價`、`市值`、以及 `compute_allocation_split` 算出的 **`total_value`**
（`dividend_station_service.py:933` 有算，但 `:1013-1015` 的 prompt **只取百分比，未取 `total_value`**）。
⚠️ **一處措辭澄清**：`加碼金` 這個欄名容易誤讀為金額，實測
`dividend_station_service.py:51` 為 `f"{a.light.deploy_pct:.0f}%"` → **是百分比，不是絕對金額**。

### §3.3 🟡 出口點 C — 個股組合 AI 判讀

**位置**：`src/ui/tabs/stock_grp_sections/section_ai_portfolio.py::_build_portfolio_prompt`（`:110-200`），送出於 `:79`
**確認會送出**：ticker + 名稱、健康度、多因子評分與五維、RSI／趨勢／VCP、外資買賣超張數、
EPS／毛利／殖利率／P-B、財報體檢 DNA／現金水位／OCF／負債比、排名順序。
**✅ 確認不會送出**：張數、均價、市值、損益（全段實測無此欄位）。
→ 揭露的是**「持有／關注哪些標的」**，不含金額。

### §3.4 🟡 出口點 D — 每週組合週報

**位置**：`src/compute/notify/weekly_review_prompt.py::build_weekly_review_prompt`
**確認會送出**（`build_holding_fact_lines:20-36`）：代號、類型、燈號、**相對基準 %**、連敗季數。
prompt 本文 `:49` 明確標示 `<Holdings> 是使用者持股`。
**✅ 確認不會送出**：張數、均價、金額。

### §3.5 ✅ 確認**不會**夾帶使用者資料的 AI 路徑

| 路徑 | 送出什麼 | 判定 |
|---|---|---|
| `src/ui/tabs/macro/section_news_ai.py:446-460` | 總經市場狀態、熱錢、拐點訊號、新聞 | ✅ **確認不會**（全為市場資料） |
| `src/ui/pages/sidebar_health.py::_render_data_health_ai` | 各資料源新鮮度狀態字串 | ✅ **確認不會** |
| `src/ui/etf/etf_tab_ai.py::_render_free_qa:316-325` | **只有使用者自己打的問題字串**，無組合資料注入 | ✅ **確認不會**（但使用者可能自行輸入敏感內容） |
| `src/compute/scoring/exit_signals.py::judge_news_sentiment:200-205` | 股名 + 新聞標題 | 🟡 間接揭露關注標的 |

### §3.6 推播（LINE／Telegram）會不會帶出持股內容？→ **確認會**

**位置**：`src/compute/notify/holdings_digest_message.py::format_holdings_message`
→ `src/data/notify/dispatch.py::send_notification` → `line_notify.py` / `telegram_notify.py`

**確認會送出**：換出持股代號（`:79`）、235 加碼代號 + `加碼金`%（`:128-131`）、
**停利清單代號 +（+損益%）**（`:139-145`）、**配置 核心%/衛星%/偏離**（`:148-160`）、
抓取失敗代號（`:163-168`）、今日選股 Top N。
**接收方**：LINE Platform（`api.line.me`）／Telegram（`api.telegram.org`）。
→ 這是**刻意的產品功能**（推到客戶自己手機），但訊息內容會經過 LINE／Telegram 的伺服器。

### §3.7 第三方 API 會不會收到可識別的使用者資訊？

| 服務 | 收到什麼 | 判定 |
|---|---|---|
| **Google Gemini** | 見 §3.1-3.4 —— **持股明細、成本、絕對損益金額** | 🔴 **確認會** |
| **LINE / Telegram** | 見 §3.6 + 收件人 ID | 🔴 **確認會** |
| **Google Sheets / Drive** | 持股帳本本體（資料原本就存在那裡） | 🟡 本來就是儲存端 |
| **GitHub**（Actions runner） | cron 期間記憶體持有完整 `lots`/`avg_price`；`picks.parquet` 已 commit | 🟠 **確認會** |
| **FinMind / TWSE / TPEX / FRED / Yahoo** | 只收到**個股代號查詢**，不含部位 | 🟡 **由查詢模式可間接推測關注標的** |
| **NAS Squid proxy** | 所有經其轉發的請求 URL | 🟡 客戶自有設備 |
| **「發布到網路」的 Sheet** | 觀察清單本體對公開 URL 開放 | 🔴 見 §2.5 |

### §3.8 ⚠️ 我沒追到／未查證的部分（依 §-2 規則 6 據實標明）

1. **「§3.1-3.6 已是全部出口點」是單組結論，未複驗。**
   方法：`grep -rn "generativelanguage|gemini_call|post_gemini|generateContent"` 找出所有 LLM 呼叫點，
   再逐一回溯其 prompt 來源。**若某個出口是透過多層注入（`gemini_call_fn` 參數傳遞）且我沒追到底，就會漏。**
   實測我確實追了 `gemini_call_fn` 的注入鏈（`section_ai_portfolio` / `section_portfolio_summary` / `etf_tab_ai`），
   但**不保證窮舉**。
2. **`src/ui/tabs/tab_stock.py:1873` 的 `_ai_sum_prompt` 內容我未逐行展開**（單一個股摘要，
   從 grep 結果看不含持股欄位，但**未確認**）。
3. **`src/services/ai_qa_service.py::run_agent` 的 tool-calling 路徑未完整評估**：
   LLM 可自行決定呼叫 `_tool_get_risk_plan(stock_id, capital_twd=1_000_000)`（`:307`）。
   預設值是 100 萬（假值），但**若有呼叫端傳入客戶真實資金，該數字會進 Gemini**。
   **我沒有追出是否存在這樣的呼叫端。**
4. **未評估 Streamlit 本身的遙測**：`.streamlit/config.toml` 已設 `gatherUsageStats = false` ✅，
   但 Streamlit Cloud 平台端的行為**無法從 repo 判斷**。
5. **未做 git 全歷史 secret scan**（見 §1.0）。

---

## §4 權限分層

### §4.1 三套憑證 profile，scope 寬度差異極大

| Profile | 定義位置 | Scopes | 寫入能力 |
|---|---|---|---|
| **① 互動 OAuth** | `infra/oauth.py::GOOGLE_OAUTH_SCOPES`（`:32-38`） | `spreadsheets`（**全部試算表讀寫**）、`drive.file`（僅 app 建立的檔）、`drive.metadata.readonly`（**列出全 Drive 中繼資料**）、`openid`、`userinfo.email` | 🔴 **可寫、可覆蓋客戶的任何一張試算表** |
| **② SA（App 內）** | `src/data/portfolio/gsheet_portfolio.py:206-209` | `spreadsheets` + **`https://www.googleapis.com/auth/drive`（完整 Drive 權限）** | 🔴🔴 **本 repo 最寬的 scope** —— 完整 Drive 讀／寫／**刪除** |
| **③ SA（cron 唯讀）** | `src/data/portfolio/gsheet_sa_reader.py:45`（`_SCOPES`） | **`spreadsheets.readonly`** | ✅ **唯讀，最小權限** |

**判定**：
- ③ **是正面典範** —— 檔內 `:44` 註解明寫「唯讀 scope：cron 只讀你的持股/觀察清單，不需要寫入或 Drive（§1 最小權限）」，
  且有測試 `tests/test_gsheet_sa_reader.py:154` 釘住它。✅
- ② **是最該檢討的一項**：`auth/drive` 是 Google 最寬的 Drive scope。
  對照 ① 只用 `drive.file`（僅限自己建的檔），② 卻要了整個 Drive。
  ⚠️ **我未查證 ② 的 `auth/drive` 是否為 `client.create()` 建檔所必需** —— 從 ① 的註解
  （`gsheet_portfolio.py:689`「OAuth 模式下 `drive.file` scope 已允許 app 建立並擁有此檔」）
  推測 `drive.file` 應該就夠，但**這是推測，不是查證**。

### §4.2 🔴 寫入客戶 Google Sheet 的**所有路徑**（含「整表清空再重寫」高風險寫法）

| # | 路徑（`file:符號名`） | 寫法 | 風險 |
|---|---|---|---|
| 1 | `gsheet_portfolio.py::save_portfolio`（`:384-388`） | **`ws.clear()` → `append_row(表頭)` → `append_rows(keep_rows)` → `append_rows(new_rows)`** | 🔴 **整表清空再重寫** |
| 2 | `gsheet_portfolio.py::save_stock_watchlist`（`:429-433`） | 同上 | 🔴 同上 |
| 3 | `gsheet_portfolio.py::delete_portfolio`（`:786-789`） | 同上（無 new_rows） | 🔴 同上 |
| 4 | `gsheet_portfolio.py::delete_stock_watchlist`（`:813-816`） | 同上 | 🔴 同上 |
| 5 | `gsheet_portfolio.py::_get_worksheet`（`:247-253`） | `add_worksheet` / `append_row(headers)` / `ws.update('A1:…1', [headers])` | 🟡 只動表頭列 |
| 6 | `gsheet_portfolio.py::append_forward_test_picks`（`:529`） | **純 `append_rows`（不 clear）** | ✅ 安全 |
| 7 | `gsheet_portfolio.py::_ft_worksheet`（`:513-517`） | 建分頁 + 寫表頭 | 🟡 |
| 8 | `gsheet_portfolio.py::create_new_sheet`（`:706`） | `client.create(title)` | 🟡 新建，不覆蓋 |
| 9 | `gsheet_portfolio.py::rename_sheet`（`:741`） | 改試算表標題 | 🟡 |
| 10 | `gsheet_portfolio.py::_get_or_create_app_folder`（`:636`）+ `create_new_sheet` 內搬移 | Drive 建資料夾 + 改 parents | 🟡 已標 best-effort、失敗不炸 |

**🔴 #1-#4 的具體風險（本節重點）**：

四處都是 **read → `ws.clear()` → 分多次 `append_*` 寫回** 的 **非原子**操作，且**沒有備份**。
以 `save_portfolio:383-388` 為例：
```
existing = ws.get_all_values()
keep_rows = [r for r in existing[1:] if (r and r[0].strip() != name)]
...
ws.clear()                    # ← 此刻客戶整張分頁被清空
ws.append_row(_HEADERS)
if keep_rows: ws.append_rows(keep_rows)   # ← 若這裡失敗，其他組合全數消失
ws.append_rows(new_rows)
```
**失敗窗口**：`ws.clear()` 成功之後、`append_rows(keep_rows)` 完成之前，若發生
網路中斷 / Google API 429 配額滿 / Streamlit session 被中止 / 行程被回收 →
**客戶「其他所有組合」的持股資料（含成本均價）永久遺失**，且**程式沒有留任何副本**。
⚠️ 這正是 Google Sheets 配額最容易出事的地方 —— 同檔 `:60-63` 的註解自陳
「根治 429：list/load 每次呼叫對 Sheets 打 4~5 個 read request…撞『每分鐘每使用者 60 讀取』配額」，
**說明此 API 在本專案確實會撞配額**。
**⚠️ 未查證**：Google Sheets 的版本歷史（File → Version history）理論上可還原，
但**我沒有驗證本專案的寫入模式是否會產生可用的還原點**，也沒有驗證客戶是否知道這條退路。

### §4.3 有沒有不可逆的操作？

| 操作 | 可逆性 | 說明 |
|---|---|---|
| `ws.clear()` + 重寫（#1-#4） | ⚠️ **程式端不可逆** | 本專案不留備份；僅能依賴 Google 端版本歷史（**未驗證**） |
| **刪除 Google Sheet 檔案** | — | ✅ **不存在** —— 實測 `grep "del_spreadsheet\|files().delete\|\.delete(\|trash"` 在 `src/` `infra/` `scripts/` **0 命中**（`trashed=false` 那 4 處是**查詢過濾條件**，不是刪除動作）。**程式沒有刪除客戶 Sheet 的能力。** |
| `del_worksheet`（刪分頁） | — | ✅ **0 命中，不存在** |
| `data_cache/forward_test/picks.parquet` 寫入 | ✅ 冪等 | `forward_test_store.py::append_picks_local` 同 `(cohort, stock_id)` 不覆蓋（`:49-51` 註解 §5 冪等） |
| `export_db.yml` **force-push `data` 分支** | ⚠️ **不可逆** | `.github/workflows/export_db.yml`（標題行即寫 force-push）。但推的是**市場資料 stock.db**，`STOCK_IDS` 未在該 workflow 設定 → 用 `export_stock_db.py:424` 的預設市場代號清單，**不含客戶持股** |
| `git commit` 客戶清單到 `health_watchlist.json` | ⚠️ **git 歷史不可逆** | 見 §2.4 |
| 憑證輪替 | — | ⚠️ **repo 內無任何金鑰輪替 / 撤銷機制**（未查證是否有 repo 外的流程） |

---

## §5 沙箱／部署差異（誠實標明「未實測」）

**本次盤點為純靜態讀碼，以下項目一律「未實測」，不得當成已驗證的事實。**

| 項目 | 只有部署環境才有 | 本次狀態 |
|---|---|---|
| `st.secrets` 實際內容 | Streamlit Cloud Secrets 管理介面 | **未實測** —— 磁碟無 `.streamlit/secrets.toml`，無從得知實際設了哪幾把 key |
| OAuth 完整流程（authorize → callback → token） | 需真實 `redirect_uri` + 瀏覽器 | **未實測** —— 只讀了 `infra/oauth.py` 與 `oauth_state.py` 的程式邏輯 |
| Google Sheets 實際讀寫、429 配額行為 | 需真實 SA / OAuth 憑證 | **未實測** —— §4.2 的失敗窗口是**程式碼推論**，非實機重現 |
| **`ws.clear()` 中斷後是否真能從 Google 版本歷史還原** | 需真實 Sheet | **未實測（重要缺口）** |
| GitHub Actions cron（16 支 workflow） | GitHub 代管 runner | **未實測** —— 未查 run history，不知實際執行成敗 |
| NAS 中繼站 `nas_server.py` | 客戶家中 Synology NAS | **未實測** —— §1.2-e 的「無認證開放」是**讀碼判定**；`_assert_public_url` 的防護完整性**未逐行複驗** |
| NAS Squid proxy 連線 | 客戶 NAS + 台灣 IP | **未實測** |
| LINE / Telegram 實際推播 | 需真實 token | **未實測** |
| Gemini 實際請求內容 | 需真實 API key | **未實測** —— §3 的欄位清單來自**讀 prompt 組裝程式碼**，非攔截實際 HTTP payload |
| **repo 是公開還是私有** | GitHub | 🔴 **未實測（關鍵缺口）** —— remote 為 `github.com/linchen-20200325/my-stock-dashboard`；環境無 `gh` CLI，無法查 visibility。**§2.4 的嚴重性完全取決於此**：若 repo 公開，`picks.parquet` 與（未來填入的）`health_watchlist.json` 即為公開資料。**請 user 直接確認。** |
| FinMind SDK 行為 | — | 本機 `FinMind` **未安裝**（實測 import 失敗）；`streamlit`/`gspread`/`google.oauth2`/`requests`/`pandas` 均可 import |

**另一項文件缺口**：`infra/oauth.py:11` 指向 `docs/OAUTH_SETUP.md`，實測**該檔不存在**
（`ls docs/OAUTH_SETUP.md` → No such file）。GCP 設定步驟目前只存在於 `infra/oauth.py:10-20` 的 docstring。

---

## §6 v2 改版的建議護欄

> ⚠️ **本節只給建議，本階段不實作**（依指派範圍 + CLAUDE.md §-1）。
> 每條的「現況」均附 `file:符號名`；「建議」與「為什麼」是本組判斷，**未經第二組複驗**。
> 涉及 UI 版面者另受 CLAUDE.md §-1.5.D §03-2 ① 草稿先行拘束。

### 🔴 P0（建議優先處理）

**G1｜送 LLM 前一律去識別化（對應 §3.1）**
- **現況**：`src/ui/etf/etf_tab_ai.py::_generate_report:117-124,218,240` 把
  **股數、成本均價、絕對資本利得(元)、已領配息(元)、組合總現值(元)、再平衡金額(元)** 直送 Gemini。
- **建議**：在 prompt 組裝與 LLM transport 之間加一層**唯一出口** `sanitize_for_llm()`，
  預設**只放行比例與相對值**（%、pp、排名、燈號），**阻擋所有絕對金額與成本價**。
  AI 要做的事（強弱排序、再平衡建議、汰弱留強）**用百分比就足夠** ——
  §3.2 的 `build_summary_prompt` 已經證明這條路走得通（它只送 %，功能照樣完整）。
- **為什麼**：這是本次盤點唯一「客戶完整財務狀況離開自有系統」的路徑。
  且風險與收益不對等 —— 送出絕對金額**並沒有換到更好的 AI 輸出**。

**G2｜寫 Google Sheet 一律先備份，並取消「整表清空」（對應 §4.2）**
- **現況**：`save_portfolio:384` / `save_stock_watchlist:429` / `delete_portfolio:786` /
  `delete_stock_watchlist:813` 四處皆 `ws.clear()` 後分多次 `append_*`，**無備份、非原子**。
- **建議**：兩者擇一或並用 ——
  ① 改用 `ws.batch_update()` 單次原子寫入（不經過「空表」中間態）；
  ② 在 `clear()` 前先把 `existing` 寫進一個 `_backup_<ts>` 分頁或本地檔，成功後再清。
  並補一個「寫入後讀回驗證列數」的 post-condition 檢查。
- **為什麼**：這是**唯一會讓客戶永久失去自有資料**的程式路徑，
  而同檔 `:60-63` 註解自陳本專案**確實會撞 Sheets 429 配額** —— 失敗窗口不是理論風險。

**G3｜觀察清單改走 API 讀取，停用「發布到網路」（對應 §2.5）**
- **現況**：`scripts/push_watchlist_signals.py:32` / `push_weekly_report.py:4`
  以客戶 publish-to-web 的 CSV URL 為資料源。
- **建議**：改走既有的 `gsheet_sa_reader`（Service Account + `spreadsheets.readonly`）——
  **這套機制已經存在且已用於持股推播**（`push_holdings_daily.yml`），
  等於**不必新建任何東西**，只要把兩支 script 的資料源換掉。
- **為什麼**：publish-to-web 讓該 Sheet 對**任何拿到 URL 的人**開放，不受 Google ACL 保護；
  而同 repo 內已有更安全且權限更小的等價方案。

### 🟠 P1

**G4｜scope 降到最小（對應 §4.1）**
- **現況**：`gsheet_portfolio.py:206-209` 的 Service Account 要 `auth/drive`（完整 Drive）；
  `infra/oauth.py:32-38` 的互動 OAuth 要 `spreadsheets`（全部試算表讀寫）。
- **建議**：① SA 路徑先驗證能否降為 `drive.file`（互動路徑已證明 `drive.file` 足以建檔 —— 見
  `gsheet_portfolio.py:689` 註解）；② 互動 OAuth 評估 `spreadsheets` → `drive.file` +
  只對 app 自建的 Sheet 操作；③ 沿用 `gsheet_sa_reader.py:45` 的做法，
  **把 scope 常數用測試釘住**（`tests/test_gsheet_sa_reader.py:154` 已有先例）。
- **為什麼**：`auth/drive` 讓這支程式有能力讀寫／刪除客戶 Drive 中的**任何**檔案，
  遠超「管理一張持股表」所需。§4.1-③ 已證明本專案做得到最小權限。

**G5｜LLM 出口收斂成單一 transport（對應 §3）**
- **現況**：至少三套各自獨立的 Gemini 呼叫實作 ——
  `app_ai_service.py::gemini_call`（金鑰池）、`services/ai_fetcher.py::post_gemini`、
  `src/ui/pages/sidebar_health.py::_call_gemini_brief`（L5 自建、自己讀 key、自己組 HTTP）。
- **建議**：v2 統一為**一個** L3 transport，G1 的去識別化閘門掛在該處。
  ⚠️ 注意 `app_ai_service.py:20-26` 已明確記載 `gemini_call` 與 `post_gemini`
  **行為不等價**（endpoint 版本 / sleep 策略不同），**合併屬行為變更，需另案量測**（該檔原註即如此警告）。
- **為什麼**：三個出口 = 三個要各自記得去識別化的地方 = 一定會漏一個。

**G6｜補一個「PII 不得進 prompt」的守衛測試**
- **現況**：實測 `tests/` 中**無**任何防止使用者資料進入 prompt 的測試
  （現有的 `去識別化` 相關改動 v19.174 針對的是**第三方作者姓名**，非客戶財務資料）。
- **建議**：加一個 AST／字串層守衛，對 prompt 組裝函式禁止出現
  `avg_price` / `shares` / `lots` / `capital_gain` / `total_value` / `dividend_received` 等欄位，
  並依 CLAUDE.md §-1.5.E A7 做**突變測試**（拔掉去識別化 → 測試必須轉紅）。
- **為什麼**：G1 若只靠自律，下一個加功能的人不會知道這條規矩。

### 🟡 P2

**G7｜OAuth client_secret 不再經由畫面輸入（對應 §1.2-c）**
- **現況**：`oauth_state.py::_resolve_oauth_cfg` 接受 `st.session_state['custom_oauth_cfg']`。
- **建議**：v2 評估是否只留 `st.secrets` 一條路；若須保留 in-app wizard，至少加明確警語。
- **為什麼**：client_secret 以明文存在 session 記憶體，且來自使用者手動貼上。

**G8｜`health_watchlist.json` 改為不進 git（對應 §2.4）**
- **現況**：git 追蹤，設計上要 user 填代碼後 commit（`update_health_history.yml:14,17,22`）。
- **建議**：改由 GitHub Secret／Variable 提供清單，或移入已被 gitignore 的路徑。
- **為什麼**：git 歷史不可撤回；客戶一旦填入，關注清單就永久留存。
  ⚠️ **本條的嚴重性取決於 repo 是否公開 —— 見 §5，該項未查證。**

**G9｜補 `docs/OAUTH_SETUP.md`**
- **現況**：`infra/oauth.py:11` 指向該檔，實測不存在。
- **建議**：補齊，或把指標改向 `infra/oauth.py:10-20` 的 docstring。
- **為什麼**：憑證設定步驟是安全關鍵路徑，指向一個不存在的檔會讓人自行猜測設定方式。

**G10｜NAS 中繼站未設 key 時拒絕啟動（對應 §1.2-e）**
- **現況**：`nas_server.py:58-65` 大聲警告但照常啟動；`:79` 的 `_auth` 在無 key 時為 no-op。
  檔內註解自陳「硬性拒絕啟動屬部署行為變更，列 user 決定」。
- **建議**：v2 由 user 拍板是否改為「未設 `NAS_API_KEY` → 拒絕啟動」。
- **為什麼**：這是本次盤點中唯一「缺憑證 → 安全邊界直接消失」的項目。
  ⚠️ 這屬**部署行為變更**，依 CLAUDE.md §-1.5.D §03-2 ② 應請示客戶，不由內部逕行拍板。

---

## 附錄｜本報告的方法與已知盲點（依 §-2 規則 6）

**方法**
1. 正向枚舉：`grep -rhoE "os\.environ(\.get)?[\(\[][\"'][A-Z0-9_]+[\"']"` 取全部環境變數名；
   `grep -rn "st\.secrets"` 取全部 secrets 讀取點；`grep -rhoE "secrets\.[A-Z0-9_]+" .github/workflows/` 取 GH Secrets。
2. 硬編碼掃描：四組憑證 pattern（JWT / AIza / googleusercontent / GOCSPX）+ 賦值式 pattern。
3. 外流追蹤：`grep -rn "generativelanguage|gemini_call|post_gemini|generateContent"` 找出 LLM 出口，
   逐一回溯 prompt 組裝函式並**實際讀該段 code**（不採信 docstring 轉述）。
4. 寫入面追蹤：`grep -n "\.clear()|append_row|batch_update|add_worksheet|del_worksheet|\.create("` 於 portfolio 模組。
5. 落地面：`ls -laR data_cache/` + `git ls-files data_cache/` 比對哪些進了版控。

**已知盲點（不要當成「全都查過了」）**
1. ⭐ **§3 的「已窮舉全部外流路徑」是單組結論，未經第二組獨立複驗。** 依 §-2 規則 6 只能當待驗事項。
2. ⭐ **repo 公開/私有未查證**（環境無 `gh`）—— 這會直接改變 §2.4 / G8 的嚴重性等級。
3. **未做 git 全歷史 secret scan** —— §1.0 的「無硬編碼憑證」只涵蓋**當前工作樹**。
4. **未實測任何部署環境行為**（§5 全表）—— 包含 §4.2 的失敗窗口、§1.2-e 的開放中繼，皆為讀碼推論。
5. **`tab_stock.py:1873`、`ai_qa_service.run_agent` 的 tool-calling 參數來源未追到底**（§3.8-2、§3.8-3）。
6. **`_assert_public_url`（NAS SSRF 防護）未逐行複驗**，只採信 `nas_server.py:54-57` 的註解自述。
7. **未掃** `ARCHITECTURE.md` / `SPEC.md` / `STATE.md` / `DATASTATION.md` / `docs/*` ——
   本報告只讀 code 與 workflow，未比對文件宣稱與實作是否一致。
8. **`§4.1-②` 的 `auth/drive` 是否為建檔所必需**屬推測（依 §4.1 註），**未實測降級後是否仍可運作**。
