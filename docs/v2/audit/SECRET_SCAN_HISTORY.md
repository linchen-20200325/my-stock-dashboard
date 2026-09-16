# 憑證外洩稽核 — git 全歷史掃描報告

- **對象**：`https://github.com/linchen-20200325/my-stock-dashboard`（**PUBLIC**）
- **稽核日**：2026-09-14
- **模式**：唯讀。未修改 repo 任何檔案，未執行任何 git 寫入（無 commit / push / rebase / filter-branch / gc）。
- **掃描母體**：**2,383 commits**、**5,552 blobs**、**678 refs**（含 `refs/heads/*` 5 條 + **`refs/pull/*` 673 條**），歷史區間 **2026-05-07 ～ 2026-09-14**。
- ⚠️ 本報告**不含任何憑證內容值**。一律只寫類型 / 路徑 / commit / 日期 / 前 4 碼 / 長度 / 形狀簽章。

---

## §0. 先講一個會影響「先前所有稽核結論」的前提發現

**工作目錄 `/home/user/my-stock-dashboard` 是一個 shallow clone（淺複製）。**

```
git rev-parse --is-shallow-repository  ->  true
.git/shallow 存在，grafted 邊界 4 個 commit（ed00456 / f4650c3 / e4e03f6 / cd3ec21）
```

後果：在工作目錄裡直接下 `git log --all` / `git rev-list --all`，**只看得到 129 個 commit（2026-08-27 之後）**，
而真實歷史有 **2,383 個 commit（2026-05-07 起）**。**約 95% 的歷史在本機是看不到的。**
證據：`cd3ec21`（Merge PR #656）在本機被 `--max-parents=0` 判為 root commit，
但它實際有兩個 parent（`c240eec` / `d32aff6`），兩者都不在本機物件庫中。

➡️ **任何「只在工作目錄跑 git 掃描」的稽核，結論都只覆蓋最後 5%。**
本次為避免此陷阱，另在 scratchpad 取了一份 `--mirror` 完整複製
（`.../scratchpad/fullclone`，**未動原 repo 一個位元組**），全部結果以該完整歷史為準。

---

## §1. 結論（一句話）

**在我掃描的樣式與範圍內，沒有找到任何疑似真實的憑證**——全歷史 2,383 commits / 5,552 blobs 中，
所有 credential 形狀的命中，逐一驗證後**全部是 placeholder、測試 fixture 或文件範例**。

⚠️ **這句話的效力邊界（依 CLAUDE.md §-2 規則 6 誠實標註）**：
- 這是**單組掃描、未經第二組獨立複驗**的結論，**只能當待驗事項**，不得被引用為「已查證的事實」。
- 它是**樣式比對（pattern-based）**的結論，不是數學證明。掃描的樣式清單見 §6.1；
  **不符合任何已知樣式的憑證（例如自訂格式、被 base64/壓縮包過一層的字串）掃不到**。
- 「沒找到」≠「不存在」。若要把「本 repo 無憑證外洩」當成可依賴的事實，**必須另派一組獨立稽核**
  （建議用不同方法：GitHub 內建 Secret Scanning、gitleaks/trufflehog 等工具交叉比對）。

✅ **可以確定性較高地說的**：最危險的幾類——Google Service Account JSON、OAuth client secret、
OAuth refresh token、GitHub PAT、LINE/Telegram bot token、AWS 金鑰、JWT——在全歷史中
**命中數為 0**（非「命中後判定為假」，是**根本沒有任何字串符合該形狀**）。見 §2.3。

---

## §2. 命中清單

### 2.1 判定方法（先講依據，不只給結論）

每個命中用四項證據判真偽，不靠單一直覺：

| 證據 | 說明 |
|---|---|
| **長度比對** | 真憑證長度是固定的。Google API key = `AIza` + 35 = **39 碼**；Google Sheet ID = **44 碼**；publish-to-web token ≈ **70+ 碼**。長度不足 = 截斷假值。 |
| **dummy 標記字串** | 值裡面直接含 `fake` / `test` / `your` / `abc` / `123` / `xyz` / `xxx` / `你的` / `ci-` 等。 |
| **形狀簽章（shape）** | 把值逐字元轉成 `A`(大寫)/`a`(小寫)/`9`(數字)/`_`(其他)。真憑證是亂數 → 形狀無規律；手打假值 → 出現「連續 10 個 9」「連續 19 個 A」這種人工結構。 |
| **所在語境** | 檔案是 `*.example` / `tests/` / `.md` 文件 / docstring，且該測試的**目的本身**就是驗證「金鑰會被洗掉」。 |

### 2.2 全部命中（去重後的**相異值**，非重複 blob）

全歷史 754 筆 raw 命中，去重後只有 **下列相異值**。**全部判定為假值。**

| # | 類型 | 路徑 | 首次引入 commit / 日期 | 長度 | 前4碼 | 真偽判定 | 依據 |
|---|---|---|---|---|---|---|---|
| 1 | Google API key（**滿長度 39 碼**） | `tests/test_ai_qa_service.py` | `d3befc7` 2026-07-14 | 39 | `AIza` | **假值** | 值內含 `fake`+`abcdef`+`123456`；shape=`AAaaAaAAAA` + 連續10個`9` + 連續19個`A`（人工結構，非亂數）。所在函式是 `test_scrub_secrets_removes_api_key`，**其存在目的就是驗證金鑰會被洗掉** |
| 2 | Google API key（26 碼） | 同上 | `d3befc7` 2026-07-14 | 26 | `AIza` | **假值** | 長度不足 39；含 `abc`/`123` |
| 3 | Google API key（17 碼） | 同上 | `d3befc7` 2026-07-14 | 17 | `AIza` | **假值** | 長度不足 39；含 `abc`/`123`/`xyz` |
| 4 | PEM 私鑰區塊 | `tests/test_push_holdings_daily.py` | `e5fcac6` 2026-08-22 | 金鑰本體 **5 字元** | — | **假值** | `BEGIN/END PRIVATE KEY` 之間本體只有 `\nx\n`（單一字元 `x`）。真 RSA 私鑰 ≈ 1,600+ 字元 |
| 5 | PEM 私鑰區塊 | `tests/test_gsheet_sa_reader.py` | `e5fcac6` 2026-08-22 | 本體 `---KEY---` | — | **假值** | 本體是字面字串 `---KEY---` |
| 6 | Service account email | `tests/test_push_holdings_daily.py` | `e5fcac6` 2026-08-22 | 32 | `bot@` | **假值** | `bot@proj.iam.gserviceaccount.com`，`proj` 為佔位專案名 |
| 7 | Bearer token（assert 內） | `tests/test_review_fixes_v19_82.py` | `e3aa268` 2026-07-11 | 23 | `Bear` | **假值** | 值含 `test`；位於 `assert calls[0].get("Authorization") == ...` 的測試斷言 |
| 8 | Proxy URL 帳密 | `.streamlit/secrets.toml.example` | `6e5a334` 2026-05-07 | 17 | `user` | **假值** | 字面 `username:password@your.proxy.host` |
| 9 | Proxy URL 帳密 | `src/data/proxy/proxy_helper.py` | `07223a7` 2026-06-28 | 8 | `user` | **假值** | docstring 說明格式 `http://user:pwd@host:port` |
| 10 | Proxy URL 帳密 | `etf_dashboard.py`（舊路徑） | 2026 上半 | 9 | `user` | **假值** | 同上，文件字串 |
| 11 | FRED_API_KEY | `.github/workflows/pr-check.yml` | `9e1371a` 2026-06-25 | 11 | `ci-t` | **假值** | `ci-test-*` CI 佔位值 |
| 12 | FRED_API_KEY | `tests/test_china_macro_stock.py`, `tests/test_tw_macro_policy.py` | — | 8 | `fake` | **假值** | 值本身以 `fake` 開頭 |
| 13 | NAS_API_KEY | `src/data/proxy/nas_server.py` | `07223a7` 2026-06-28 | 27 | `your` | **假值** | `your_..._here` 形式，位於安裝說明 docstring |
| 14 | NAS_API_KEY | 同上（警告訊息） | 同上 | 9 | `<高強度…` | **假值** | 中文提示字串 `<高強度…>`，尖括號佔位 |
| 15–19 | FINMIND_TOKEN（5 種相異值） | `secrets.toml.example`, `.streamlit/secrets.toml.example`, `DATASTATION.md`, `src/ui/tabs/tab_macro.py`, `app.py` | `6e5a334` 2026-05-07 起 | 15–27 | `your` | **假值** | 全為 `your_finmind_token_here` 類字串 |
| 20 | FINMIND_TOKEN | `.github/workflows/pr-check.yml` | `9e1371a` 2026-06-25 | 13 | `ci-t` | **假值** | `ci-test-token` |
| 21–22 | FINMIND_TOKEN | `scripts/poc_finmind_bulk.py`, `etf_dashboard.py` | `adab34b` 2026-07-04 | 7 | `你的To` | **假值** | 中文字面「你的Token」 |
| 23 | GEMINI_API_KEY | `.streamlit/secrets.toml.example`, `DATASTATION.md`, `secrets.toml.example` | `6e5a334` 2026-05-07 | 15/24 | `your` | **假值** | `your_gemini_key` 類 |
| 24 | Google Sheet ID（編輯 URL） | `tests/test_portfolio_manager.py` | `ca9f30b` 2026-08-12 | **14**（需 44） | `1lFh` | **假值（截斷）** | 僅 14 碼，不足 44 碼無法使用。該測試在驗證 `parse_sheet_id()` 的 URL 解析 |
| 25–26 | publish-to-web token | `tests/test_portfolio_manager.py` | `ca9f30b` 2026-08-12 | 11 / 16（需 70+） | `2PAC` | **假值（截斷）** | 測試斷言「發布連結應回傳空字串」 |
| 27 | publish-to-web token | `docs/push_watchlist_signals.md` | `c0dedd5` 2026-08-15 | 11 | `2PAC` | **假值** | 值是 `2PACX-xxxxx`（連續 5 個相同字元 `x`） |
| 28 | OAuth client id 網域 | `src/ui/etf/etf_tab_portfolio.py` | `fee33d2` 2026-06-28 | 30 | `xxx.` | **假值** | 字面 `xxx.apps.googleusercontent.com` |

**另外 301 筆 `>=100 字元 base64` 命中：全部位於 `.parquet` 二進位檔內部**
（`data_cache/**`），為壓縮欄位資料中恰好落在 base64 字元集的位元組串，**不是 token**。
已逐筆確認副檔名 100% 為 `.parquet`。

### 2.3 命中數為 0 的樣式（明確的陰性結果）

下列樣式在全歷史 5,552 blobs 中**一筆都沒有**：

```
SVC_ACCT_TYPE ("type": "service_account")   0      ← 無 Service Account JSON 曾被 commit
OAUTH_CLIENT_SECRET (GOCSPX-)               0
OAUTH_REFRESH_TOKEN (1//...)                0
TELEGRAM_BOT_TOKEN (\d{8,12}:...)           0
LINE_CHANNEL_ACCESS_TOKEN                   0
LINE_USER_ID (U + 32 hex)                   0
SLACK_TOKEN (xox[baprs]-)                   0
GITHUB_PAT (ghp_/gho_/ghu_/ghs_/ghr_)       0
AWS_AKID (AKIA/ASIA)                        0
OPENAI_KEY (sk-)                            0
JWT (eyJ....eyJ.)                           0
WEBHOOK_URL (slack/discord/line-notify)     0
真實 Sheet ID / 2PACX token (>=20 碼)        0
GENERIC_SECRET/PASSWORD 指派                 0
OAuth client id (\d+-\w+.apps.google...)    0
```

### 2.4 Commit message 掃描

全歷史 **2,383 則 commit message（80,517 行）** 掃 credential 樣式 → **0 命中**。

### 2.5 CI 設定（正面確認）

全部 17 個 workflow 一律使用 `${{ secrets.X }}`，無硬編碼。
唯一的 inline env 是 `pr-check.yml` 的 `ci-test-*` 假值（§2.2 #11、#20）。

**目前 GitHub Secrets 內存在的憑證名稱（供 §5 輪替盤點用，值不在 repo 內）**：
`FINMIND_TOKEN`、`GEMINI_API_KEY`、`FRED_API_KEY`、`PROXY_URL`、`NAS_API_KEY`、`NAS_BASE_URL`、
`GCP_SERVICE_ACCOUNT_JSON`、`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_USER_ID`、
`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`、`PORTFOLIO_SHEET_ID`、`STOCK_PORTFOLIO_SHEET_ID`、
`WATCHLIST_CSV_URL`、`WEEKLY_WATCH_CSV_URL`、`APP_BASE_URL`、`GITHUB_TOKEN`(內建)。

---

## §3. 歷史上被刪除的敏感檔

全歷史共 132 個路徑曾被刪除。以敏感命名篩選後，**只有兩類**：

### 3.1 ⚠️ 11 個 `*.vbs` 本機推送腳本（**這是本次最實質的發現**）

| 項目 | 內容 |
|---|---|
| 檔案 | `check_status.vbs`, `do_git_stock.vbs`, `git_push_v18458.vbs`, `push_stock_v18460.vbs`, `push_v18459.vbs`, `push_v18461.vbs`, `push_v18462.vbs`, `push_v18463_debug.vbs`, `push_v18463_ui_restructure.vbs`, `push_v18464_etf_smart.vbs`, `push_v18465_mk333.vbs` |
| 加入 | `d85ea1f` 起，2026-07-03 ～ 2026-07-04 |
| 刪除 | `40b636e` 2026-07-16（commit 標題：`🔐 刪除本機推送腳本(*.vbs)+ gitignore`） |
| 現況 | HEAD 已無；**但 11 個版本仍完整留在 public git 歷史中，任何人可取回** |
| **內容判定** | **不含任何憑證** |

**依據（逐一 grep 全部 11 個 blob 版本）**：內容只有
(a) 本機 Windows 路徑（`E:\` 開頭的個人資料夾、`C:\Program Files\...\git.exe`）、
(b) `git add` / `git commit -m` / `git push origin main` 指令、
(c) commit 訊息字串。
`push origin main` **不帶任何 token**，靠本機 credential helper → **無金鑰可外洩**。

**但仍有低度個資曝險**：洩漏使用者本機的**磁碟機代號與個人資料夾命名**。
這正是 `.gitignore` 裡那句註解（`Local push helper scripts (contain local paths / account names — never commit)`）
所要防的東西——**該註解是在檔案已經被 commit 之後才加的**。

### 3.2 `data_cache/metadata.json`

曾被刪除又加回；**目前仍被追蹤**。內容為總經資料集的更新時間戳與資料集清單（`updated_at` / `datasets`），
**非憑證、非個資**。

### 3.3 明確的陰性結果

`.env`、`credentials*.json`、`client_secret*.json`、`*.pem` / `*.p12` / `*.key`、
`service_account*`、`id_rsa`、`.netrc`、`.npmrc`、`.pypirc`、`htpasswd`、`*.keystore`
—— **全歷史（含 673 條 PR ref）從未出現任何一個**。

⭐ **特別查證 `.ipynb`**：`.gitignore` 寫著 `# Notebook (contains hardcoded API keys)` + `*.ipynb`，
這是最值得懷疑的一條線索（暗示曾有一個含硬編碼金鑰的 notebook）。
**實測：全歷史 1,118 個曾存在路徑中，`.ipynb` 命中數為 0 —— 該 notebook 從未被 commit 進這個 repo。**

---

## §4. `.gitignore` 有效性（只擋未來，不擋歷史）

逐條比對「現在被忽略的敏感路徑」vs「歷史上有沒有被 commit 過」：

| `.gitignore` 規則 | 歷史上曾被 commit？ | 判定 |
|---|---|---|
| `.streamlit/secrets.toml` | **否**（0 次） | ✅ 從未外洩。只有 `*.example` 版本（假值） |
| `.env` | **否** | ✅ |
| `*.ipynb` | **否** | ✅ 見 §3.3 |
| `macro_state.json` | **否** | ✅ |
| `*.pkl` / `*.csv` / `*.xlsx` | **否** | ✅ |
| `temp/` / `.coverage` / `*_snapshots/` | **否** | ✅ |
| **`*.vbs`** | **是 —— 11 個檔，2026-07-03 commit、2026-07-16 才加規則** | ⚠️ **典型的「規則來得太晚」**，見 §3.1。所幸內容無憑證 |
| **`data_cache/metadata.json`** | **是，且現在仍被追蹤** | ⚠️ 規則存在但**對已追蹤檔無效**（git 的 `.gitignore` 不作用於已追蹤檔）。內容無敏感性，且被 CI 每日更新 —— 屬規則與現實不一致，非安全問題 |

**結論**：`.gitignore` 對「真正的憑證檔」（secrets.toml / .env / notebook）是**有效的**——
這三者從未進過歷史。唯一真的「先 commit、後補規則」的案例是 `*.vbs`，而該案例**沒有造成憑證外洩**。

---

## §5. 目前被追蹤的個人資料檔與公開曝險

> ⚠️ 以下**只描述欄位與性質，不含任何內容值**。

### 5.1 屬於「使用者個人決策」的檔案（唯一一個）

**`data_cache/forward_test/picks.parquet`**（60 列 × 6 欄，2026-07-22 起每月凍結）

| 欄位 | 性質 |
|---|---|
| `cohort` | 凍結批次（目前 3 批：2026-07-22 / 08-02 / 09-02） |
| `stock_id` / `name` | 被選中的台股代號與名稱 |
| `entry_price` | 凍結當下價格 |
| `factors` | 該檔入選的因子分數 |
| `frozen_at` | 凍結時間戳 |

**公開之後別人能知道什麼**：這個選股系統**在哪一天、選了哪 20 檔、當時價格多少、依據什麼因子分數**。
即「**策略的實際輸出與時點**」。
⚠️ **但這不是持股**——沒有張數、沒有成本、沒有損益、沒有帳戶資訊。
它是**演算法推薦清單**，不是「這個人買了什麼」。
（副作用：策略邏輯的有效性可被外部復盤；對投資策略而言屬 IP 洩漏，而非個資洩漏。）

### 5.2 偏好訊號（低敏感）

- **`src/data/etf/etf_manager_watchlist.json`** — 28 檔 ETF 代號清單。洩漏「追蹤哪些 ETF」的偏好。
- **`data_cache/health_watchlist.json`** — ⭐ `stocks` 陣列**長度為 0（空的）**，實際上沒有洩漏任何自選股。

### 5.3 非個資：公開市場資料（可放心公開）

`data_cache/` 其餘全部被追蹤的檔案都是**公開市場資料的快取**，任何人本來就能從 TWSE / FinMind / FRED 取得：

| 檔案 | 內容 |
|---|---|
| `twii_ohlcv.parquet`（4,932 列） | 加權指數 OHLCV |
| `finmind_inst.parquet` / `finmind_margin.parquet`（各 4,957 列） | 三大法人買賣超 / 大盤融資餘額 |
| `finmind_m1m2.parquet`（240 列） | M1B / M2 貨幣總計數 |
| `tw_pmi.parquet`（170 列） | 台灣 PMI |
| `fundamentals/*.parquet`（12 檔，各 ~1,000 列） | 上市櫃公司財報（營收 / EPS / 資產負債） |
| `sector_flow/*`、`macro_forward_test/signals.parquet`、`macro_last_good/tw_pmi.json` | 類股資金流 / 總經燈號快照 |

### 5.4 commit metadata 中的個資（公開 repo 一律可見）

git 作者欄位含**兩個真實 Gmail 位址**（`cheng10029@…` 與 `cheng10022@…`，共 5 種作者身分別名）。
這是 GitHub 公開 repo 的常態（除非啟用 noreply email），**非本次「憑證外洩」範疇**，但屬個資曝險，一併列出供判斷。

### 5.5 沒有的東西（正面確認）

**全歷史沒有任何檔案含持股張數 / 成本 / 損益 / 帳戶 / 保單資料。**
持股與帳本存在 Google Sheets（由 `secrets.PORTFOLIO_SHEET_ID` 指向，**Sheet ID 本身不在 repo 內**），
`scripts/push_holdings_daily.py` 等只是讀取程式碼，不含資料。

---

## §6. 若真的有外洩該怎麼處理（**本次沒有觸發，僅供備查；我沒有執行任何一步**）

> 本次結論是「未發現真實憑證」，故**以下不需要執行**。寫在這裡是為了兩件事：
> (a) 萬一 §1 的待驗結論被後續獨立稽核推翻時，有現成的處置順序；
> (b) 說明為什麼「把 commit 刪掉」這個直覺做法**不夠**。

### 6.1 正確順序：**先撤銷，再清歷史**（順序不可顛倒）

1. **第一步永遠是「讓外洩的金鑰失效」，不是「把它從 git 刪掉」。**
   憑證一旦推上 public repo，必須假設**已經被抓走**——GitHub 上有大量機器人在即時掃 public commit，
   平均數十秒內就會被索引。刪 commit 只是讓**你自己**看不到，攻擊者手上那份不會消失。
2. **依爆炸半徑排序輪替**（本 repo 若真有事，建議順序）：
   1. `GCP_SERVICE_ACCOUNT_JSON`（可讀寫 Google Sheets 帳本 → 直接碰到個人資產資料）→ 到 GCP Console 刪金鑰、建新金鑰
   2. `LINE_CHANNEL_ACCESS_TOKEN` / `TELEGRAM_BOT_TOKEN`（可冒名對本人發訊息 → 釣魚風險）
   3. `PROXY_URL` / `NAS_API_KEY`（含家用 NAS 帳密與位址 → 可被當跳板，且 `nas_server.py` 自陳未設 key 時 `/proxy` 無認證）
   4. `GEMINI_API_KEY` / `FINMIND_TOKEN` / `FRED_API_KEY`（帳務損失為主）
   5. `PORTFOLIO_SHEET_ID` 等（非憑證，但知道 ID 才能嘗試存取 → 連帶檢查該 Sheet 的共用設定）
3. **輪替完才動歷史**：`git filter-repo`（或 BFG）重寫歷史 → force push → **通知所有協作者重新 clone**。
4. **請 GitHub Support 清 cache**：重寫歷史後，舊 commit 仍可能透過
   `https://github.com/<owner>/<repo>/commit/<sha>` 直連存取（GitHub 會保留 unreachable object 一段時間），
   且**所有 fork 都各自保有一份完整歷史**。必須另外請 GitHub Support 清除，並確認 fork 狀況。

### 6.2 為什麼「刪 commit」不夠（四個獨立理由）

1. **已經被看到了**——自動化掃描機器人的速度遠快於人的反應。
2. **`git revert` / 後續 commit 刪檔完全無效**——舊 blob 仍在物件庫，`git show <sha>:<path>` 直接取回。
   （本 repo 的 `*.vbs` 就是活生生的例子：2026-07-16 已刪，但 11 個版本今天仍可完整還原。）
3. **fork 與 PR ref 會留存**——本 repo 光是 `refs/pull/*` 就有 **673 條**；
   PR 分支上的 commit 即使從未合併，**依然公開可讀**（本次掃描已涵蓋這 673 條）。
4. **第三方鏡像**——GHArchive、各種 code search 服務可能已經存有快照。

### 6.3 要不要把 repo 改成 private？

**本次結論是「未發現憑證外洩」，所以「為了憑證」而轉 private 並不必要。**
真正該問的是 §5.1 那個問題——**「我願不願意公開我的選股決策與時點？」**
這是**業務判斷，不是技術判斷**，應由你決定：

- **維持 public 的代價**：`picks.parquet` 讓任何人能復盤你的策略輸出（IP 層面，非個資）；
  commit 作者欄的 Gmail 位址公開（§5.4）。
- **轉 private 的代價**：GitHub Actions 免費額度受限（本 repo 有 17 個排程 workflow，用量不低）；
  Streamlit Cloud 若由此 repo 部署，需重新授權。
- **中間選項**：repo 維持 public，但把 `data_cache/forward_test/picks.parquet` 改存到私有位置。
  ⚠️ **注意**：依 `CLAUDE.md` §-1.5.F 判定 3(5)，此檔是**無法重建的凍結歷史快照**
  （重抓只會得到今天的排名，那正是 §2.3 要防的 lookahead），
  屬「刪除正式生產資料」類 → **必須先請示 user，不得逕行處理**。

**建議（總管推薦方案）**：**不需要為了憑證轉 private**。
若對 §5.1 的策略曝險在意，優先處理該單一檔案的存放位置，而非整個 repo 轉 private——
成本低得多，且不影響現有 17 個 CI 排程。

---

## §7. 我沒查到的 / 取樣範圍（誠實揭露）

### 7.1 掃描範圍（**窮舉，非取樣**）

本次**沒有取樣**——全部掃完：

| 項目 | 數量 |
|---|---|
| commits | **2,383**（全部，含 673 條 PR ref 上的 commit） |
| blobs | **5,552**（`git cat-file --batch-all-objects`，**含 unreachable / dangling 物件**） |
| refs | **678**（`refs/heads/*` 5 + `refs/pull/*` 673） |
| 曾存在的路徑 | **1,118** |
| commit message | **2,383 則 / 80,517 行** |
| 跳過的 blob | **0**（無大小截斷） |

掃描的樣式清單（共 27 條）：
`AIza` / `GOCSPX-` / `1//` refresh token / `"type":"service_account"` / `BEGIN PRIVATE KEY` / `private_key` /
`Bearer` / Sheet ID / `2PACX-` / LINE channel & notify token / LINE user id / Telegram bot token & chat id /
`xox[baprs]-` / `ghp_|gho_|ghu_|ghs_|ghr_` / `AKIA|ASIA` / `sk-` / JWT / slack+discord+line webhook /
URL 內嵌帳密 / `api_key=` / `token=` / `secret|password|pwd=` / `NAS_API_KEY` / `FINMIND_TOKEN` /
`FRED_API_KEY` / `*.apps.googleusercontent.com` / 泛用高熵字串（len>=20、shannon>=4.0、含大小寫+數字）。

### 7.2 已知盲點（**不要當成「全都查過了」**）

1. ⭐ **單組未複驗。** §1 的結論、§2 每一筆真偽判定、§3/§4 的全稱句，**全部由本組單獨產出**，
   **沒有第二組獨立驗過**。依 `CLAUDE.md` §-2 規則 6，這些只能當**待驗事項**，
   **不得作為後續動作的前提，也不得寫進 commit message / PR 描述當成已完成的事實**。
2. **樣式比對的結構性盲點。** 自訂格式的憑證（例如一段沒有固定前綴的隨機字串當密碼）、
   或被 base64 / gzip / parquet 壓縮包過一層的憑證，**我的樣式掃不到**。
   泛用高熵掃描只覆蓋「被引號包住、>=20 字元、含大小寫+數字」的字面值，**不覆蓋二進位檔內部**。
3. **`.parquet` 內部未做語意檢查。** 301 筆 base64 命中我確認了副檔名全為 `.parquet` 就判定為壓縮雜訊，
   **沒有逐一解壓比對每個欄位值**。若有人把憑證寫進 parquet 的某個字串欄，本次掃不到。
   （不過 §5.3 已逐檔列出 schema，欄位都是市場資料，無存放憑證的合理位置。）
4. **只掃這一個 repo。** 姊妹 repo `my-Fund-dashboard`、Streamlit Cloud 的 secrets 設定、
   GitHub Secrets 的**實際值**、NAS 上的設定檔，**全部不在本次範圍**。
5. **GitHub 端的殘留未查。** 我沒有查 GitHub 是否留有已被刪除 commit 的 web 快取、
   也**沒有查有沒有 fork**（有 fork 的話歷史會再多幾份副本）。
6. **未使用第二種工具交叉驗證。** 沒有跑 gitleaks / trufflehog / GitHub 內建 Secret Scanning。
   §1 若要升級為「可依賴的事實」，**這是最划算的下一步**（不同工具的樣式庫不同，正好補 7.2.2 的盲點）。
7. **§0 的 shallow clone 發現改變了先前結論的效力。** 先前標註「未做 git 全歷史 secret scan」的權限盤點，
   即使當時做了，**在工作目錄裡也只會掃到 5% 的歷史**。本次是第一次涵蓋完整歷史。

### 7.3 產物位置

- 完整歷史複製（唯讀用途，未動原 repo）：`…/scratchpad/fullclone/`
- 原始掃描輸出：`…/scratchpad/scan/`、`…/scratchpad/full_hits.txt`、`…/scratchpad/values_out.txt`
- ⚠️ `full_hits.txt` / `values_out.txt` 內的值**已在產生時即遮罩**（只存前 4 碼 + 長度 + 形狀），
  但 `fullclone/` 是完整 repo 複製，**與 public repo 內容相同**，不含額外敏感資訊。
