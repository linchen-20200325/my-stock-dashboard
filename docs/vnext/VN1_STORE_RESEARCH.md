# VN1-STORE 每日系統風險上限紀錄保存方式研究（1.0-B3，2026-10-19）

> **性質**：研究報告，**只研究、不實作**（DEC-062；`docs/BACKLOG.md` `VN1-STORE`；`docs/vnext/VNEXT_1_0_DECISION_GATES.md` 第 6 節 `1.0-B3`）。本批**沒有改任何程式碼、測試、secrets 或雲端設定**。
> **來源**：兩組獨立研究（repo 端組：讀程式碼與既有文件；平台端組：查 Streamlit／GitHub／Google 平台行為），結論收斂一致；由撰寫組整併，並就「程式碼裡便宜可查」的事實逐項複查（標「撰寫組複查」）。
> **讀法**：**事實**（有出處、可重查）與**推論**（由事實推出）分開標示；平台行為若只來自論壇或研究組轉述、未在 Streamlit Cloud 實測，一律寫明。⛔ **本文推薦不是授權**：保存位置屬 DEC-009 須客戶同意事項（DEC-062 已明載「Q4 保存位置**未同意**，維持待客戶」）。

---

## 1. 背景與客戶裁示

**客戶裁示（DEC-062，2026-10-18，逐字摘錄）**：

- 簡短版：「Q4：A；但暫不核准「每日紀錄存 repo 追蹤檔」。先研究最小、可靠、可持久化且符合「資料層 ≠ AI 推理層」的保存方式，再提出建議；不要直接把 Git repo 當 production datastore。保存方式未定前可先採 B 顯示「從今天開始記錄」。」
- 正式詳細版：「VN1-Q4：方向選 A，但「每日紀錄直接存在 repo 追蹤檔」目前不核准。先研究並驗證最小、可靠、可持久化且符合「資料層 ≠ AI 推理層」的保存方案，包括 Streamlit Cloud persistence、restart/deployment、concurrency、寫入可靠性與資料責任。保存方式尚未決定前，1.0 UX 可先採「從今天開始記錄」，不得製造不存在的歷史比較。不得自行新增變動大小門檻。」

**由裁示得出的研究邊界**：

| 項目 | 要求 |
|---|---|
| 比較方向 | A：比上一份通過新鮮度、規則版本相同的紀錄；沿用期不算變化 |
| 禁止 | 存 repo 追蹤檔（暫不核准）；把 Git repo 當 production datastore；製造不存在的歷史；自行新增變動大小門檻 |
| 過渡 | 保存方式未定前顯示「從今天開始記錄」 |
| 研究範圍 | Streamlit Cloud persistence、restart/deployment、concurrency、寫入可靠性、資料責任 |
| 架構條件 | 最小、可靠、可持久化；資料層 ≠ AI 推理層（DEC-027） |

---

## 2. 現況事實

> 下表「撰寫組複查」＝本批撰寫組於 2026-10-19 在 `origin/main`＝`4ce2930b` 上以 grep／讀碼重查過；「研究組轉述」＝研究組回報、撰寫組未重查。

| # | 事實 | 出處 | 查證 |
|---|---|---|---|
| F1 | 新 UI 的上限檔是 `risk_cap_state.json`（常數 `shared/risk_cap_policy.py::RISK_CAP_STATE_FILE`），並同步寫一份 `macro_state.json`（舊 UI／regime 退路用） | `shared/risk_cap_policy.py`；`src/services/macro_refresh_service.py` 的 `STEP_RISK_CAP` 寫檔清單 | 撰寫組複查 |
| F2 | 兩檔都在 `.gitignore`、**未被 git 追蹤** | `.gitignore`（`macro_state.json`、`risk_cap_state.json`、`risk_cap_state.json.tmp`）；`git ls-files` 無命中 | 撰寫組複查 |
| F3 | **唯一寫入時機**：使用者按今天頁「🚀 更新今日戰情」→ `page_today` 呼叫 `macro_refresh_service.refresh_macro_now` → `STEP_RISK_CAP` → `risk_cap_apply.compute_and_lock_risk_cap` → `MacroStateLocker.lock_system_state_only` | `src/ui/views/page_today.py`、`src/services/macro_refresh_service.py`、`src/services/risk_cap_apply.py`、`src/services/macro_state_locker.py` | 撰寫組複查 |
| F4 | 寫法：先寫 `.tmp` 再 `os.replace`（原子替換）、**整檔覆寫、不留歷史** | `MacroStateLocker._write_state_lock` | 撰寫組複查 |
| F5 | **沒有任何排程寫這個檔**：`scripts/`、`.github/` 內 grep `risk_cap`／`compute_and_lock`／`lock_system_state` 皆 0 命中 | grep | 撰寫組複查 |
| F6 | **不經 AI**：固定規則引擎（`ENGINE_SOURCE="new_ui_risk_cap_v2"`）；符合 DEC-027「資料層 ≠ AI 分析層」 | `src/services/risk_cap_apply.py` | 撰寫組複查（讀碼；未逐行窮舉呼叫鏈） |
| F7 | 欄位含 `risk_cap_ruleset_version`（現值 `"risk_cap.v2"`）、`required_core_ok`（核心齊全才寫且蓋 `True`）、`input_asof`（各輸入的資料日）、`timestamp` | `shared/risk_cap_policy.py`、`src/services/risk_cap_apply.py`、`macro_state_locker` | 撰寫組複查 |
| F8 | `timestamp` 是**寫入當下的時鐘**，不是資料日 ⇒ 比較「是否同一份資料」應以 `input_asof` 為準，不以 `timestamp` | `macro_state_locker`（`_now_str()`） | 撰寫組複查；「應以 `input_asof` 比較」為推論 |
| F9 | 有效性：`is_valid_risk_cap_snapshot` ＋ 7 天有效期（`shared/staleness.py::MACRO_VERDICT_MAX_AGE_DAYS`）；算不出來時不覆寫、沿用 7 天內最近一次有效快照 | `shared/risk_cap_policy.py`、`shared/staleness.py`、`risk_cap_apply` 檔頭 | 撰寫組複查 |
| F10 | 回傳 `written`（這一輪有沒有寫）與 `files_written` | `risk_cap_apply` 結果型別 docstring | 撰寫組複查 |
| F11 | 每筆約 3.5 KB | 研究組以測試資料量測 | 研究組轉述（**非 production 實測**） |
| F12 | Streamlit Cloud 磁碟為 ephemeral（容器重啟／重新部署即消失） | repo 內註解：`src/data/macro/macro_core.py`（v19.118 durable 快照層說明）、`ARCHITECTURE.md`；Streamlit 論壇官方人員回覆 | ⚠️ **非官方文件、未在 Cloud 實測**；論壇出處為研究組轉述 |

**結論（推論）**：目前缺兩塊 ——
1. **只增不改的歷史紀錄**（現在整檔覆寫，沒有「上一份」可比）；
2. **不依賴使用者造訪的每日寫入者**（現在沒人按按鈕那天就沒有紀錄；且寫在 ephemeral 磁碟上，重啟即失）。

---

## 3. 候選方案比較

| 方案 | 做法 | 持久性 | 併發／重複寫 | 主要問題 | 判定 |
|---|---|---|---|---|---|
| **(a)** app 內本地檔 | 沿用現行檔案，改成追加 | ✗（ephemeral，F12） | 多 session 同寫有競態 | 不持久、有沒人造訪的空洞 | ✗ |
| **(b1)** commit 到 main 的追蹤檔 | cron 寫檔並 commit | ✓ | 可控 | **客戶已否決**（DEC-062） | ✗（已否決） |
| **(b2)** 獨立 data branch／**(b4)** Releases／Gist | 仍用 Git 物件存資料 | ✓ | 可控 | 本質仍是「把 Git 當 production datastore」，**很可能違反裁示本意** | ✗（推論） |
| **(b3)** Actions artifacts | 每次 run 上傳 artifact | ✗（保留期最長 90 天） | — | 過期**靜默消失**＝歷史悄悄變少 | ✗ |
| **(c)** 系統專用 Google Sheet | **只由** GitHub Actions cron 寫；app 唯讀 | ✓ | 單一寫入者＋workflow `concurrency` group；寫前讀既有日期、已存在就不追加（冪等）；`value_input_option="RAW"`（不讓 Sheets 自動轉型） | 平台層**無不可竄改保證**：有編輯權者可改歷史 → 以「保護工作表／範圍、只有擁有者＋寫入 SA 可編輯」緩解 | **推薦** |
| **(d)** NAS 端點 | app／cron 打家中 NAS API | 依 NAS | 需自建 | 新增對外 API 面；家用網路可用性 | ✗ |
| **(e)** GCS bucket | 每天一個不可變物件 `risk_cap/v1/YYYY-MM-DD.json`，以 `ifGenerationMatch=0` 建立 | ✓ | **平台保證只建立一次**（重跑即失敗、天然冪等） | 需 GCP bucket、兩支 SA（寫入 `objectCreator`／app `objectViewer`）；免費額度**可能需綁定帳單帳戶（未驗證）** | 次選 |
| Firestore／託管 Postgres | DB | ✓ | ✓ | 依賴與新廠商較重；Supabase 免費專案閒置會暫停、Neon scale-to-zero（研究組轉述） | ✗（過重） |

**(c) 的細節要求**（研究組建議，撰寫組未實作）：
- app 讀取用**新的唯讀** service account，**只分享在這一本 Sheet**，Sheet ID 固定寫在 secrets。
- ⛔ **不得**沿用既有 `GCP_SERVICE_ACCOUNT_JSON`（`src/data/portfolio/gsheet_sa_reader.py` 使用）—— 那支帳號可能被分享到使用者的持股 Sheet，沿用＝重新打開 `SEC-3`（匿名經 SA 讀 Sheet，#877 才關閉）的同類風險。
- ⛔ **不得**用「發佈到網路」CSV —— 那是公開網址。
- 零新增套件（`requirements.txt` 已有 `gspread`、`google-auth`，撰寫組複查）、零費用、不需帳單帳戶（研究組轉述）。

**(e) 的細節**：可用 `google-auth` 的 `AuthorizedSession` 直接打 GCS JSON API，**不需新增套件**（研究組轉述）；費用約 0。

**共同風險（c、e 都有）**：
- GitHub 排程 workflow **可能延遲或被丟棄**；**公開 repo 連續 60 天無活動會自動停用排程**（研究組轉述 GitHub 文件）。
- ⇒ app 必須**偵測過期**：最新紀錄日期 < 預期日期時顯示「過期」，**絕不顯示比較結果**。
- cron 排在非整點（避開整點擁塞）。

---

## 4. 寫入者設計（c、e 共用）

- 無頭（headless）cron，比照 `scripts/update_macro_forward_test.py` 的模式，跑**同一條 L3 鏈**（`refresh_macro_now` → `STEP_RISK_CAP` → `compute_and_lock_risk_cap`），不另寫一套公式。
- **只有 `compute_and_lock` 實際寫了（`written=True`）才追加一筆**。
- 7 天沿用期間不會產生新紀錄 ⇒ 不會被當成「變化」（符合 A：沿用期不算變化）。
- 取數失敗以**狀態**呈現／記錄，**絕不以數值**呈現（§1 Fail Loud）。
- ⛔ 不新增任何變動大小門檻（DEC-062）。

⚠️ **未驗證（需 PoC）**：`refresh_macro_now` 與引擎輸入（`macro_info`、`bias_info`、`m1b_m2_info`、`li_latest`，見 `src/services/macro_engine_inputs.py`）能否在**無頭環境完整產出**。既有 `scripts/update_macro_forward_test.py` **並沒有**填這些輸入（它走 `fetch_macro_bundle` ＋ `calc_traffic_light`），所以「照抄就能跑」**不成立**，須實測。

---

## 5. 總管推薦

**推薦：(c) 系統專用 Google Sheet**（單一寫入者＝GitHub Actions cron；app 以新的唯讀 SA 讀取）。

理由：
1. **零新增套件、零費用、不需帳單帳戶**。
2. **資料責任清楚**：客戶可以直接打開 Sheet 看每一天的紀錄。
3. Sheets 配額遠超需求：每專案每分鐘 300 次、每使用者每分鐘 60 次讀寫（Google 官方配額，研究組轉述）；本需求一天一筆。
4. 弱點（有編輯權者可改歷史）**接受並緩解**：保護工作表／範圍、只有擁有者＋寫入 SA 可編輯、單一寫入者。

**次選：(e) GCS** —— 不可竄改性更強（平台保證每天只能建立一次）；代價是要開 GCP bucket、可能要綁帳單帳戶、要兩支 SA。

**兩案都需客戶同意（DEC-009）**：新增保存位置，以及在 Streamlit secrets／GitHub secrets 放新的 service account 憑證。

---

## 6. 需要客戶裁示的事

**裁示題（商業語言）**：

> 「每天的系統風險上限紀錄，要存在一本**只給系統用的 Google 試算表**裡嗎？每天由 GitHub 自動寫一筆，網站只讀不寫；您隨時可以打開看。」
> **總管推薦：是**（理由見第 5 節）。若您希望紀錄「連您自己都無法修改」，改選次選 GCS（要開 Google Cloud 儲存空間，可能需要綁信用卡帳戶）。

**需要客戶動手的事**（擇一）：
- 由客戶在自己的 Google 帳號建立該試算表與 service account；或
- 核准開發端先寫一份「設定步驟文件」，客戶照著做。
（⛔ 開發端不得自行建立、不得取得客戶 Google 帳號權限。）

**上線前必須在真實環境驗證**：
1. Streamlit Cloud 連得到 Google Sheets API。
2. **反向測試**：新的唯讀 SA **讀不到**任何使用者的持股 Sheet。
3. GitHub cron 實際延遲／漏跑情形；過期偵測會正確顯示「過期」。
4. 無頭 PoC：cron 能完整產出引擎輸入並寫出 `written=True` 的紀錄（第 4 節）。
5. Streamlit 休眠／喚醒後讀取正常。
6. repo 是公開還是私有（決定 60 天無活動停用規則是否適用）。

---

## 7. 未經第二組驗證／推論

- F11「每筆約 3.5 KB」為研究組以測試資料量測，非 production 值；撰寫組未重量。
- F12「Streamlit Cloud 磁碟 ephemeral」只依 repo 內註解與論壇官方人員回覆，**非官方文件、未在 Cloud 實測**。
- 平台行為（Actions artifacts 90 天、排程延遲與 60 天停用、Sheets 配額數字、GCS `ifGenerationMatch=0` 語意、GCS 免費額度是否需帳單帳戶、Supabase／Neon 免費層行為）皆為**平台端研究組單組轉述**，撰寫組未逐一重查官方文件；GCS 帳單帳戶需求明確**未驗證**。
- 「(b2)／(b4) 違反裁示本意」是**推論**，非客戶明示；客戶若認為 data branch 不算「把 Git 當 production datastore」，判定可翻。
- 「沿用既有 SA 會重現 `SEC-3` 同類風險」是依 `SEC-3` 性質推論，未實測 production SA 被分享到哪些 Sheet（production SA 現況本就 unknown，見 DEC-062）。
- F6「不經 AI」依讀碼，未窮舉整條呼叫鏈的所有分支。
- 第 4 節「無頭能否完整產出引擎輸入」**完全未驗證**，是推薦方案能否落地的最大不確定點。
- 「兩組結論收斂」與本文整體推薦為研究組＋撰寫組產出，**未經第三組獨立稽核**；送客戶前視為待驗。
