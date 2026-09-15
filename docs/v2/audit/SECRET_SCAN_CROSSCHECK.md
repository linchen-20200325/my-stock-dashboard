# 憑證外洩 — 第二組交叉驗證報告（獨立複驗）

- **執行者**：憑證外洩第二組（交叉驗證），唯讀
- **日期**：2026-09-14
- **標的**：`linchen-20200325/my-stock-dashboard`（**public**）
- **紀律聲明**：本組**未讀取**第一組的報告（`scratchpad/SECRET_SCAN_HISTORY.md` 全程未開啟），
  未沿用其樣式清單；改用**現成 secret scanning 工具**（gitleaks / trufflehog）＋ 本組自建的
  **provider 導向**樣式庫，方法與第一組不同。
- **對 repo 的寫入**：**零**。原 repo `/home/user/my-stock-dashboard/.git` 未執行任何寫入指令
  （複驗：仍 shallow、仍 129 commits、reflog 未變、無 fetch/gc/prune）。所有作業在 scratchpad 內的
  `--mirror` 副本上進行。

---

## §1 一句話結論

> **在我掃到的範圍內，沒有找到任何真實憑證 —— 這一點與第一組一致。**
> **但本組同時發現：如果只掃工作目錄，覆蓋率僅 5.4%（129 / 2,383 commits）**，
> 也就是說「掃過了」這句話的**證據基礎**可能遠比字面上弱。本組已用完整歷史（2,383 commits /
> 13,397 objects / 678 refs，含 673 個 `refs/pull/*`）重掃，結論仍然是**未發現真實憑證**。

⚠️ **依 CLAUDE.md §-2 規則 6 據實標明**：上面這句是**本組的單組結論**，沒有第三組驗過。
它成立的前提、以及它**沒有**涵蓋什麼，逐項列在 §2 與 §7。**請連同 §7 一起讀，不要只引用 §1。**

⚠️ **本結論有一個明確的效力邊界**：本組全程 `--no-verification`（理由見 §2），
所以我能說的是「**沒有任何東西長得像真憑證**」，**不能**說「所有金鑰都已確認無效／未外流」。
「這把 key 是不是還活著」本組**沒有驗，也不該由本組驗**。

---

## §2 使用的工具、版本與實際掃描規模

### 2.1 取得完整歷史（前置）

工作目錄是 **shallow clone**，直接掃會嚴重低估。故先在 scratchpad 做 `--mirror` 複製：

```
git clone --mirror https://github.com/linchen-20200325/my-stock-dashboard  <scratchpad>/audit-mirror.git
```

| 指標 | 工作目錄（shallow） | **本組 mirror（完整）** | 覆蓋率 |
|---|---:|---:|---:|
| commits | 129 | **2,383** | **5.4%** |
| git objects | 1,712 | **13,397** | **12.8%** |

mirror 內容分解（實測）：

| 項目 | 數量 |
|---|---:|
| commits | 2,383（非合併 2,041 / 合併 342） |
| blobs | **5,552** |
| trees | 5,462 |
| refs 總數 | **678** |
| └ `refs/heads/*` | 5（main / data / 3 個 feature 分支） |
| └ `refs/pull/*` | **673**（最高 PR #673，全部 `head` ref） |
| └ `refs/tags/*` | 0 |
| root commits | 2（`6e5a334` 主線 2026-05-07；`a6af07a` `data` 孤兒分支） |
| unreachable / dangling objects | **0**（`rev-list --objects --all` 13,397 == pack 內 13,397） |

✅ **`refs/pull/*` 全數取得**：673 個 PR head ref 都在，涵蓋**未合併 / 已關閉 PR 的 commit**。
開放中 PR = 0。

### 2.2 工具與版本

| 工具 | 版本 | 取得方式 |
|---|---|---|
| **gitleaks** | **8.28.0** | 官方 release binary（`gitleaks_8.28.0_linux_x64.tar.gz`） |
| **trufflehog** | **3.90.10** | 官方 release binary（`trufflehog_3.90.10_linux_amd64.tar.gz`） |
| 本組自建樣式庫 | — | 22 條 provider 導向 regex（見 2.4） |
| git | 2.43.0 | 系統 |

✅ **兩個工具都成功安裝**，不需要降級方案。

⚠️ **`--no-verification` 是刻意的**：trufflehog 預設會拿候選值去打各家 provider API 做**活性驗證**。
那等於**把疑似憑證送到外部服務**，違反本次任務的禁令，故全程關閉。
**代價**：`Verified=0` 這個數字**不代表「驗過都是假的」**，而是「**根本沒驗**」。這點在 §7 再列一次。

### 2.3 實際掃描規模（五個獨立 pass）

| # | Pass | 範圍 | 實測規模 | 命中 |
|---|---|---|---|---:|
| 1 | gitleaks `git --log-opts="--all --full-history"` | 全 refs 的 **diff** | 2,013 commits / **28.77 MB** | 22 |
| 2 | gitleaks `dir`（**全 blob 展開**） | **5,552 blobs** | **275.24 MB** | 229 |
| 3 | trufflehog `git --bare` | 全 refs 歷史 | 24,653 chunks / **75.32 MB** | 3 |
| 4 | trufflehog `filesystem`（**全 blob 展開**） | **5,552 blobs** | 29,953 chunks / **348.87 MB** | 36 |
| 5 | 本組自建樣式庫（raw bytes） | **5,552 blobs** | **275,852,570 bytes** | 74 |

**補充 pass（工具預設不做的）**：

| # | Pass | 規模 | 命中 |
|---|---|---|---:|
| 6 | **commit message 全文**（工具只掃 diff，不掃 message） | 2,383 commits / **4.04 MB** | **0** |
| 7 | **base64 解碼後重掃**（憑證可能被編碼藏起來） | **1,698** 個 base64 run | **0** |
| 8 | **binary blob 專掃**（文字掃描器多半跳過） | **303** binary blobs（含 `stock.db`） | 0 真陽性 |
| 9 | **高熵 token 偵測**（無可辨識前綴的憑證） | 全 text blobs，entropy ≥ 4.3 + 大小寫+數字混合 | 27 候選，0 真陽性 |
| 10 | **本機 repo unreachable 物件**（`git fsck` on **副本**） | 17 個（2 blob / 8 commit / 7 tree） | **0** |
| 11 | **GitHub issue / PR 標題＋內文**（不在 git 裡的面向） | **673 筆 / 1.08 MB** | **0** |

⚠️ **pass 1 的 2,013 < 2,383 是正常的**：gitleaks 不 diff merge commit（342 個），
且少數 commit 無 diff。**pass 2 用全 blob 展開補掉這個缺口**，兩者結論一致（見 §3.4）。

### 2.4 本組自建樣式庫（22 條，**依本專案實際 provider 設計**）

從 `CLAUDE.md §2.1` 的 T1–T5 來源分級 + code 反推本專案真正會有的憑證型別，
而**不是**抄一份通用清單：

`AIza`(Google/Gemini) / Google OAuth client_id / `GOCSPX-` / `1//`(refresh token) /
`"type":"service_account"` / `private_key_id` / **JWT 三段式（FinMind token 就是 JWT）** /
`gh[pousr]_` / `github_pat_` / AWS `AKIA|ASIA|AGPA|AIDA|AROA|ANPA` / `sk-ant-` / `sk-`(OpenAI) /
`xox[baprs]-` / `glpat-` / Stripe / SendGrid / Telegram bot / **PEM private key header** /
**URL userinfo（NAS Squid proxy 帳密）** / **FRED API key**（32 字元 assign 式） /
**FinMind token assign 式** / 泛用 `key|token|secret|password =` + 長值

---

## §3 命中清單與真偽判定（**無任何內容值**）

**所有命中均判定為非真實憑證。** 以下逐類列出判定依據。

### 3.1 gitleaks — 12 個 unique 值（229 次出現）

| # | 規則 | 前綴 | 長度 | 代表位置（檔案） | 首見 commit / 日期 | 判定 | **判定依據** |
|---|---|---|---:|---|---|---|---|
| 1 | generic-api-key | `btn_…` | 15 | `app.py`, `tab_stock.py` | `6e5a334b09` / 2026-05-07 | **誤報** | 實測原始行為 `st.button('🗑️ 清除報告', key='btn_ai_sum2_clr')` —— **Streamlit widget key**。規則觸發點是 `key=`，與憑證無關 |
| 2 | generic-api-key | `v2_d…` | 14 | `tab_macro_v2.py`, `tests/test_print_layout.py` | `7ccc3e0a33` / 2026-08-26 | **誤報** | 原始行 `label_visibility="collapsed", key="v2_detail_chip"` —— widget key；test 檔那兩筆是 docstring 引用同一字串 |
| 3 | generic-api-key | `_mac…` | 22 | `tab_macro_validation.py` | `2a1c436e39` / 2026-06-03 | **誤報** | 原始行 `_PHASE1_CACHE_KEY = "_macro_tw_valid_phase1"` —— **cache key 常數名** |
| 4 | generic-api-key | `macr…` | 27 / 22 / 19 | `tab_macro_validation.py` | `2a1c436e39`,`a2b7dcdd1e` / 2026-06-03~04 | **誤報** | 原始行 `key="macro_tw_phase3_max_forward"` / `key="macro_tw_phase3_offset"` / `key="macro_tw_phase3_run"` —— 全為 widget key |
| 5 | generic-api-key | `FORE…` | 15 | `macro_signal_lookback_tw.py` | `2a1c436e39` / 2026-06-03 | **誤報** | 原始行 `key="FOREIGN_SELL_5D"` —— **dict key**（訊號名） |
| 6 | generic-api-key | `fore…` | 15 | `scripts/analyze_ring1_gate.py` | `9e29f1bea0` / 2026-08-06 | **誤報** | 原始行 `key="foreign_spot_5d"` —— dict key |
| 7 | generic-api-key | `CL_I…` | 17 | `src/ui/tabs/tab_edu.py` | `a8b05835ac` / 2026-08-07 | **誤報** | 原始行 `CL_INTL_KEY_DXY as _CL_INTL_KEY_DXY` —— **import 別名**（常數名含 `KEY`） |
| 8 | generic-api-key | `AIza…` | **17** | `tests/test_ai_qa_service.py` | `0e3a6534fc` / 2026-07-15 | **測試 fixture** | (a) 長度 17，**真 Google key 必為 39**（`AIza`+35），結構上不可能是真的；(b) 值內含字面字串 **`ABC`**；(c) 所在函式 `test_scrub_secrets_removes_api_key` 是**洗金鑰功能的 golden test**，該值存在的目的就是「**被洗掉**」 |
| 9 | **gcp-api-key** | `AIza…` | **39** | `tests/test_ai_qa_service.py` | `0e3a6534fc` / 2026-07-15 | **測試 fixture** | **本次風險最高的候選，已排除**：(a) 長度 39 **確實**符合真 Google API key 格式，故工具以高信心規則 `gcp-api-key` 命中；(b) **但值內同時嵌有字面字串 `FAKE`、`ABC`、`1234`**（本組以不揭露值的方式檢出）；(c) 上下文為 `KEY = "..."` 後傳入 `run_agent(api_key=KEY, gemini_http=_Boom())`，`_Boom` 是**假的 HTTP 物件、只負責 raise 429**，該值從未離開行程；(d) 該測試斷言 `assert KEY not in (r.error or "")` —— 它**測的就是金鑰不得外洩** |

⚠️ **第 9 項的意義**：這是一個「**格式完全合法、只靠內容標記字才能排除**」的案例。
**純長度／正則比對會把它判成真陽性；純長度比對也可能反過來把它放過。** 本組是靠
「解析值的字元組成、找出嵌入的 marker 字」＋「讀 caller 上下文」兩步才敢定案。

### 3.2 trufflehog — 3 個 unique 值（39 次出現），`Verified=0`

全部由 **URI detector** 命中（＝ URL 內嵌 `user:pass@`）。本專案確實使用 **NAS Squid proxy**
（`CLAUDE.md §2.1 T3` / `proxy_helper.py`），所以這一類**必須認真看**。

| # | 位置 | host 部分 | 判定 | **判定依據** |
|---|---|---|---|---|
| 1 | `.streamlit/secrets.toml.example` | `your.proxy.host:3128` | **文件 placeholder** | 檔名即 `.example`；原文為註解 `# 例：PROXY_URL = "http://<帳號>:<密碼>@your.proxy.host:3128"`；host 本身就是 `your.proxy.host` |
| 2 | `etf_dashboard.py` | `host:3128` | **UI 說明文字** | 出現在 `st.warning(...)` 的使用說明字串內，教使用者去 Streamlit Cloud Secrets 填什麼；同一段上方還有 `_re_dh.sub(r'://[^@]+@', '://***@', _proxy_url)` —— **程式本身就在遮蔽密碼** |
| 3 | `proxy_helper.py` | `host` | **docstring** | 位於 `get_proxy_config()` 的 docstring，說明「新格式 / 舊格式」兩種設定寫法 |

### 3.3 本組自建樣式庫 — 74 命中 / 5 類（含 **2 項兩個工具都沒報的**）

| 類別 | unique 值 | 判定 | **判定依據** |
|---|---:|---|---|
| `google_api_key_AIza` | 1 | 同 §3.1 #9 | — |
| `url_userinfo` | **5** | **全為 placeholder** | ⭐ **比 trufflehog 多抓到 2 個**。5 個 host 分別是 `host`、`host`、`your.proxy.host`、**`yourname.synology.me`**、**`IP`** —— 全部是佔位字串；user/pass 長度 2–8 且含 `user`/`pass`/`your` 等佔位字。**特別確認：真實 NAS hostname 與帳密未曾進入版控** |
| `private_key_pem` | **1**（5 blobs） | **測試 fixture** | ⭐ **gitleaks 與 trufflehog 都沒報這一項**。位置 `tests/test_push_holdings_daily.py`，5 個歷史版本。實測 PEM 本體 = **`\nx\n`（5 字元）**，即 `"-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----"`，**完全沒有金鑰材料**；伴隨的 `client_email` 為 `bot@proj.iam.gserviceaccount.com`（佔位）。<br>⚠️ **但這條線索有價值**：它證實本專案**確實使用 Google service account**（`gsheet_sa_reader`）。本組因此**專門回頭查**真 SA JSON 是否曾進版控 → `"type":"service_account"` **0 命中**、`private_key_id` **0 命中**、歷史上**從未存在** `service_account*.json` / `credentials*.json` / `client_secret*.json`（見 §4） |
| `finmind_token_assign` | 2 | **placeholder** | 兩值皆以 `your` 開頭（`your_finmind_token_here` 型）；且 **JWT 三段式樣式全庫 0 命中** —— FinMind token 是 JWT，若真 token 曾進版控，必然命中該樣式 |
| `generic_secret_assign` | 2 | **placeholder** | 兩值皆以 `your` 開頭 |

### 3.4 兩種掃描模式的交叉驗證（本組內部自驗）

diff 模式（pass 1）與全 blob 模式（pass 2）各自算出的 unique 值集合：

```
unique in diff-mode : 12
unique in blob-mode : 12
ONLY in blob-mode (diff 漏掉的) : 0
ONLY in diff-mode              : 0
```

→ **兩種模式完全收斂**。229 vs 22 的差距**純粹是同一個值在多個檔案版本重複出現**，不是新發現。
（trufflehog 同理：36 vs 3，unique 值都是同 3 個。）

### 3.5 CI workflow 內的「硬寫值」（6 處，全部無害）

掃過 **47 個 workflow blob**（19 個 workflow 檔的全部歷史版本），
找出 6 處不走 `${{ secrets.* }}` 的硬寫值，全部位於 `.github/workflows/pr-check.yml`：

`FRED_API_KEY = "ci-test-key"` / `GEMINI_API_KEY = "ci-test-key"` / `FINMIND_TOKEN = "ci-test-token"`（各 2 次）

→ **判定：CI 佔位值**。字面即 `ci-test-*`，用途是讓測試在無真憑證時仍可跑。

---

## §4 歷史上被刪除的敏感檔（獨立檢查）

方法：從 `rev-list --objects --all` 取出**歷史上曾經存在過的每一個路徑**（**3,501 個**），
再以敏感檔名樣式比對 —— 不依賴「現在看得到什麼」。

### 4.1 從未存在過（實測 0 命中）— 這是好消息

`.env` / `credentials*.json` / `client_secret*.json` / `service_account*.json` /
`*.pem` / `*.key` / `*.p12` / `*.pfx` / `*.jks` / `id_rsa` / `id_ed25519` /
`.npmrc` / `.pypirc` / `.netrc` / `htpasswd` / `authorized_keys` / `*.kdbx` /
**`*.ipynb`（notebook）** / **真正的 `secrets.toml`（無 `.example`）** / `macro_state.json` / `*.pkl` / `*.xlsx`

⭐ **notebook 這條特別查過**：`.gitignore` 第 4 行寫著
`# Notebook (contains hardcoded API keys)` —— 這句話本身就是一條線索，暗示曾有內含硬寫金鑰的
notebook 存在。**實測結果：`*.ipynb` 自 repo 第一個 commit（`6e5a334`, 2026-05-07）起就已被
`.gitignore` 擋掉，且全歷史 3,501 個路徑中 0 個 `.ipynb`** → **該 notebook 從未進入版控**。

### 4.2 曾經存在、已刪除（3 類，均**非憑證外洩**）

| 檔案 | 加入 | 刪除 | 判定 | 依據 |
|---|---|---|---|---|
| **11 個 `*.vbs`**<br>`check_status.vbs`, `do_git_stock.vbs`, `git_push_v18458.vbs`, `push_stock_v18460.vbs`, `push_v18459.vbs`, `push_v18461.vbs`, `push_v18462.vbs`, `push_v18463_debug.vbs`, `push_v18463_ui_restructure.vbs`, `push_v18464_etf_smart.vbs`, `push_v18465_mk333.vbs` | 2026-07-03 ~ 07-04 | **`40b636e` 2026-07-16** | **非憑證**，但屬輕微資訊揭露 | ⭐ **值得單獨講**：`.gitignore` 自己寫 `# Local push helper scripts (contain local paths / account names — never commit)`，而 `*.vbs` 這條 ignore 規則**正是在刪除它們的同一個 commit（`40b636e`）才加上去的** —— 也就是「**先 commit 了，才想到要擋**」。<br>本組逐一解開全部 11 個 blob 實測內容：**只含本機 Windows 路徑**（`D:\01.Github\...`、`C:\Program Files\...`），**`credential_assignments = NONE`（11/11）**，**未找到任何本機使用者名稱**。<br>→ **不是憑證外洩**；殘留在歷史中的是**本機目錄結構**。 |
| **4 個 `*.bak`**<br>`data_loader.py.bak`, `etf_dashboard.py.bak`, `leading_indicators.py.bak`, `scoring_engine.py.bak` | 2026-05-07（首 commit） | 2026-05-31 / 2026-06-28 | **無憑證** | 4 個 blob 全數納入 pass 2/4/5 掃描；憑證樣式 **0 命中** |
| `secrets.toml.example` / `.streamlit/secrets.toml.example` | 2026-05-07 | 仍在（`.streamlit/` 版） | **範本，無真值** | 全檔實測，3 個欄位皆為佔位：`FINMIND_TOKEN = "your_finmind_token_here"`、`PROXY_URL = "http://<帳號>:<密碼>@your.proxy.host:3128"`、`# GEMINI_API_KEY = "your_gemini_key"`（註解掉） |

### 4.3 `.gitignore` 防護健全度（正面認定）

自 **第一個 commit 起**即含：`.streamlit/secrets.toml`、`*.ipynb`、`.ipynb_checkpoints/`、`.env`、
`*.pkl`、`*.csv`、`*.xlsx`。後續補上 `macro_state.json`、`*.vbs`、`*.bak`、tooling cache。
→ **敏感檔防線在專案起點就已就位**，這與「歷史上 0 個 `.env` / 0 個 notebook」的實測互相印證。

### 4.4 `shared/edu_tokens.py`（檔名含 `token`，已排除）

實測 docstring：`教學文案「活門檻」token SSOT` —— 指的是**教學文案的門檻數值 token**
（融資餘額 1500/2500/3400 億那類），**與憑證無關**。

---

## §5 Fork 狀況（第一組未做的項目）

透過 GitHub API 唯讀查詢：

| 欄位 | 值 |
|---|---|
| `full_name` | `linchen-20200325/my-stock-dashboard` |
| `private` / `visibility` | `false` / **`public`** ← 全歷史對所有人公開 |
| **`forks_count`** | **0** |
| **`network_count`** | **0** |
| `stargazers_count` / `watchers_count` | 0 / 0 |
| `created_at` | 2026-05-18T01:22:29Z |
| `archived` / `disabled` | false / false |
| `GET /forks` | **空陣列（0 筆）** |

### 判讀

✅ **沒有任何 fork。** 這是**對補救方案最有利的事實**：
fork 會複製完整歷史，而且**原 repo 轉 private、或用 filter-repo 改寫歷史，都救不回已存在的 fork**
（fork 會被提升為獨立 repo，其 object 仍留在 GitHub 的 fork network 裡）。
本 repo **沒有這個問題** —— 若日後決定改寫歷史或轉 private，**不會有 fork 殘留**。

⚠️ **但 fork=0 不等於沒有人抓過**：`stargazers=0 / watchers=0` 只說明**互動**為零，
public repo 仍可能被匿名 `git clone`、被第三方程式碼搜尋引擎或 LLM 訓練爬蟲索引，
而這些**不會**在任何 GitHub 計數器上留下痕跡。**本組無法量測這一項**（見 §7）。

📌 **附帶事實**：repo 建立於 2026-05-18，但最早的 commit 是 2026-05-07 ——
歷史是從本機既有 repo 推上來的。**該 2026-05-07 之前的本機歷史（若有）不在 GitHub 上，本組掃不到。**

---

## §6 與第一組不一致之處（**本節最重要**）

⚠️ **前提**：本組**未讀第一組報告**，因此**無法逐條比對**。以下只陳述**本組自己量到的結構性事實**，
以及「若第一組是在工作目錄上用自訂正則掃的，會結構性漏掉什麼」。
**這不是指控第一組做錯**，而是指出「這句全稱句能站多穩」。

### 6.1 結論本身：**一致**

「沒有找到任何疑似真實憑證」—— 本組用不同工具、不同樣式庫、10 倍以上的掃描量，**得到相同結論**。
這是一次**有意義的獨立印證**，不是互相抄。

### 6.2 但覆蓋率有數量級差距（**這是本組最有價值的產出**）

| | 若掃工作目錄 | 本組（mirror） | 倍數 |
|---|---:|---:|---:|
| commits | 129 | **2,383** | **18.5×** |
| git objects | 1,712 | **13,397** | **7.8×** |
| `refs/pull/*`（未合併 PR） | **0**（shallow clone 不含） | **673** | **∞** |

**以下檔案在工作目錄中「一個版本都看不到」**（實測 `working_dir_blobs = 0`）：

| 檔案 | 工作目錄 blob 數 | mirror blob 數 |
|---|---:|---:|
| `tab_stock.py` | **0** | 63 |
| `tab_macro_validation.py` | **0** | 11 |
| `macro_signal_lookback_tw.py` | **0** | 7 |
| `check_status.vbs`（及其餘 10 個 `.vbs`） | **0** | 1 each |
| `etf_dashboard.py.bak` | **0** | 1 |

→ **§3.1 的 #1/#3/#4/#5 與 §4.2 的全部 `.vbs`、`.bak`，在 shallow 工作目錄中結構上不可能被掃到。**
本組實測它們**也都不含真實憑證**，所以**最終結論不變** —— 但如果第一組是在工作目錄上掃的，
那句「沒有找到任何疑似真實憑證」的**證據基礎只有 5.4%**，而報告若未標明這一點，
就落在 CLAUDE.md §-2 規則 6 所說的「**沒查證的宣稱比沒有宣稱更危險**」。

### 6.3 純自訂正則**結構上**會漏掉的三類（本組實測補上）

| # | 類別 | 本組怎麼抓到 | 結果 |
|---|---|---|---|
| 1 | **PEM private key**（`tests/test_push_holdings_daily.py`，5 blobs） | 自建樣式庫的 `private_key_pem` | **連 gitleaks 與 trufflehog 都沒報**。若自訂樣式庫沒放 PEM header，就會整個看不見。實測為 fixture（本體 `\nx\n`） |
| 2 | **base64 編碼後的憑證** | 全 blob base64 解碼 pass（1,698 個 run） | 0 命中。**但沒做這個 pass 的話，編碼過的憑證對任何純文字正則都是隱形的** |
| 3 | **binary blob**（parquet / SQLite） | 303 個 binary blob 專掃 + raw-bytes 正則 | 278 個 parquet 命中 `eyj`（JWT 前綴）→ **逐一解碼後證實為 pandas 欄位 metadata 的 base64**（`eyJ` = `{"` 的 base64），**非 JWT**。⚠️ 這是一個**很容易誤判成重大外洩**的陷阱：FinMind token 正是 JWT，若只看「parquet 裡有 `eyJ`」就報警，會製造假警報；若只用 case-sensitive JWT 三段式樣式（本組也有），則正確得到 0 |

### 6.4 沒有發現任何「第一組說安全、實際危險」的項目

本組**未推翻**第一組的任何結論。若要用一句話總結差異：
**不是結論錯了，是證據不夠厚 —— 本組把它加厚了 18.5 倍，結論撐住了。**

---

## §7 我沒掃到的（**請不要把 §1 當成全稱保證**）

依 CLAUDE.md §-2 規則 6，以下逐項據實列出。**本節任一項都可能推翻 §1。**

### 7.1 方法上的硬限制

1. ⭐ **全程 `--no-verification`，沒有做活性驗證。**
   依任務禁令（不得把發現送到外部服務）刻意關閉。
   → 我能說「**沒有東西長得像真憑證**」，**不能**說「**所有金鑰都確認未外流／已失效**」。
   `Verified=0` 的意思是「**沒驗**」，不是「驗過是假的」。
2. ⭐ **GitHub 原生 secret scanning 告警讀不到。**
   `GET /secret-scanning/alerts` 被 agent proxy 擋下（**HTTP 403**：
   `Access to this GitHub API path is not permitted through this proxy`）。
   → **GitHub 自己有沒有對這個 public repo 發過告警，本組完全不知道。**
   **建議 user 自行到 repo → Security → Secret scanning 頁面看一眼**，那是本組拿不到、
   但對 user 一鍵可得的資訊。
3. **未使用 GitHub 官方 secret scanning 引擎做第三方交叉驗證。**
   環境內有 `run_secret_scanning` 工具可用，但它需要把**原始檔案內容送出**；
   基於同一條禁令，本組**選擇不用**。→ 少了一個獨立引擎的第三意見。
4. **`--mirror` 只能取得 GitHub 願意提供的 reachable 物件。**
   GitHub 端若有 **force-push 後變成 unreachable、且未被任何 `refs/pull/*` 保留**的 commit，
   `clone --mirror` **取不到**（本組 mirror 實測 unreachable = 0，但那只證明「我拿到的這份裡沒有」，
   **不證明 GitHub 端沒有**）。這類物件仍可能透過 GitHub 網頁以 SHA 直接存取。

### 7.2 範圍上沒碰到的面向

5. **Wiki repo 未掃。** repo `has_wiki=true`，而 wiki 是**另一個獨立 git repo**。
   `git clone .../my-stock-dashboard.wiki.git` 失敗（要求帳密，通常代表 wiki 未初始化）。
   → **本組無法確認 wiki 是空的**，只能說「clone 不到」。
6. **issue / PR 的「留言」未掃。** 本組掃了 **673 筆 issue/PR 的 title + body**（1.08 MB，0 命中），
   **但沒有掃 comments / review comments** —— 那是另一組 API endpoint，量級更大。
   **貼在留言裡的金鑰是很常見的外洩途徑**，這塊是空白。
7. **GitHub Actions 執行 log 未掃。** 19 個 workflow、大量排程 cron run。
   **log 內若曾把 secret 印出來（echo / 錯誤訊息帶 `?key=`），會留在 Actions log 裡**，
   而那不在 git 歷史中。⚠️ 本專案**有前科意識**：`tests/test_ai_qa_service.py` 整支就是在測
   「429 錯誤訊息把 `?key=<GEMINI_KEY>` 印到 UI」這個 bug（v19.128 修）。
   **同一個 bug 在被修好之前，是否曾把金鑰寫進 Actions log，本組沒查。**
8. **同一 owner 的其他 repo / gist 未掃。** 例如姊妹 repo `my-Fund-dashboard`（CLAUDE.md 多次提及）。
   金鑰常在專案間共用 —— 那邊漏了，這邊也一起完蛋。**不在本次範圍。**
9. **2026-05-07 之前的本機歷史未掃**（repo 建立於 2026-05-18，最早 commit 2026-05-07）。

### 7.3 本報告自身的效力限制

10. ⭐ **本報告是單組結論，沒有第三組驗過。**
    §3 的「全部命中皆非真實憑證」是**全稱句**。它建立在
    「我用的樣式庫 + 這兩個工具的規則庫」的**聯集**上；**任何一種樣式庫都有盲點**，
    這正是本組被派來補第一組盲點的理由 —— **同樣的道理也適用於本組。**
11. **「fork=0」只涵蓋 GitHub 的 fork 機制**，不涵蓋匿名 clone、第三方程式碼搜尋引擎、
    以及 public repo 被爬蟲索引的情形。**這些無法量測。**

---

## §8 給 user 的實務建議（依風險排序，非動工提案）

> 依 CLAUDE.md §-1，本節**不構成動工提案**，僅為交付報告的判讀指引。

| 優先 | 事項 | 理由 |
|---|---|---|
| **1** | **自行查看 repo → Security → Secret scanning 告警頁** | 本組被 proxy 擋住（§7.1-2），這是唯一的認知缺口，而 user 一鍵可得 |
| **2** | **檢查 GitHub Actions 歷史 log 是否印出過金鑰** | §7.2-7：本專案確實修過「429 錯誤把 `?key=` 印出來」的 bug；修好之前的 log 可能留有金鑰，且 log 不在 git 歷史裡 |
| **3** | 若曾在 issue/PR **留言**貼過設定值，回頭看一眼 | §7.2-6 未掃 |
| **4** | **不需要**為了本次結果改寫 git 歷史 | 未發現真實憑證；且 fork=0，即使日後需要改寫也沒有 fork 殘留問題 |
| **5** | 11 個 `.vbs` 仍在歷史中（含本機目錄結構，非憑證） | 若在意本機路徑揭露可評估；**風險等級低** |

---

## 附錄：本次產出的稽核材料（均在 scratchpad，未進 repo）

```
<scratchpad>/g2-crosscheck/
├── bin/{gitleaks(8.28.0), trufflehog(3.90.10)}
├── audit-mirror.git/          完整 mirror（2,383 commits / 678 refs）
├── blobs/, blobs_txt/         5,552 個 blob 全展開（276 MB）
├── gitleaks_all.json          pass 1（22）
├── gitleaks_blobs2.json       pass 2（229 → 12 unique）
├── trufflehog_all.jsonl       pass 3（3）
├── trufflehog_blobs.jsonl     pass 4（36 → 3 unique）
├── indep_scan.py / indep_summary.json   pass 5（自建 22 條樣式）
├── commit_msgs.txt            pass 6（2,383 commits / 4.04 MB）
├── all_paths.txt              §4 的 3,501 個歷史路徑
├── issues_all.json            pass 11（673 筆 issue/PR）
└── localgit/                  原 .git 的副本（fsck 用，原檔零寫入）
```

**複驗指令（任何人可重跑）**：

```bash
git clone --mirror https://github.com/linchen-20200325/my-stock-dashboard m.git
gitleaks git m.git --log-opts="--all --full-history" -f json -r out.json --exit-code 0
trufflehog git file://$PWD/m.git --bare --no-verification --results=verified,unverified,unknown --json
```
