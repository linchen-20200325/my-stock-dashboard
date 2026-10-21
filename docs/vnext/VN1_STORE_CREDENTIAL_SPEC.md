# VN1-STORE 憑證設定規格（System Risk Cap 系統歷史 Sheet：寫入端／讀取端身分）

> **狀態**：設定規格（docs-only）。**本檔不是施工授權、也不是 production 寫入核准。**
> 📌 2026-10-20：production 寫入的客戶裁示見 `docs/DECISIONS.md` **DEC-066**（首次人工寫入有條件核准、Daily Schedule NOT APPROVED）；其盤點、Environment 設定要求與首次寫入 Runbook 見本檔 **8.11**。本檔本身仍不是核准。
> **依據**：客戶 2026-10-19 裁示 G1／G2／G3 與共同權限原則 —— `docs/DECISIONS.md` **DEC-064**（保存方向見 DEC-063；BACKLOG 登記 DR-2026-10-19-2）。
> **本批沒有做的事**：⛔ 未改任何 code／workflow／test；⛔ 未建立任何 Google Cloud 資源、service account、key、pool、Sheet 或 GitHub secret；⛔ 未讀取或輸出任何 secret。
> ⚠️ **provenance（`CLAUDE.md` §-2 規則 6）**：本檔由單一撰寫組撰寫，**未經第二組獨立驗證**；gcloud 指令依撰寫組對 Google Cloud／GitHub 官方用法的理解寫成，**未在任何真實專案實跑**。客戶操作時若指令報錯，請把**錯誤訊息**（不含金鑰內容）回報，我們再修正本檔。

---

## 1. 客戶裁示摘要（原文全文見 DEC-064）

| 項目 | 裁示 | 本檔落點 |
|---|---|---|
| **G1** 寫入端 | 核准。GitHub OIDC ＋ Google Workload Identity Federation（WIF）；專用 `risk-cap-writer` SA；**禁止建立 writer JSON key** | 第 2、4 節步驟 2～4 |
| **G2** 讀取端 | 核准。獨立 `risk-cap-reader` SA ＋ 唯讀 JSON key；只讀 System Risk Cap 專用 Sheet；不與 writer 共用身分 | 第 2、4 節步驟 2、5、8 |
| **G3** 既有 `GCP_SERVICE_ACCOUNT_JSON` | **只核准調查，不核准修改**：確認 `client_email`／`project_id`、所屬專案與用途；不輸出 secret；不刪除／輪換／替換既有 key；不改每日持股推播 | 第 7 節（待辦，本批未調查） |
| 共同原則 | 兩支 SA 都不得取得個人持股 Sheet 權限；不得沿用 fund-nav；System Risk Cap Sheet 與 holdings Sheet 完全隔離；上線前必須做反向權限測試；**正式每日 production 寫入仍未核准** | 第 3、5 節 |

---

## 2. 架構

```
【寫入端（GitHub Actions，無 key）】
 GitHub Actions job（main 分支、指定 workflow 檔）
   │  1. 向 GitHub 要 OIDC ID token（workflow 宣告 permissions: id-token: write —— ~~未來批次~~ 2026-10-19 #886 已落地：job `wif_auth_only` 的 job 層級；有意識的變更，不是漏刪）
   ▼
 Google STS（sts.googleapis.com）
   │  2. WIF pool `github-pool` / provider `github-provider` 驗 token：
   │     issuer＝https://token.actions.githubusercontent.com，
   │     attribute-condition 限定 repository_id、repository_owner_id、ref＝main、workflow_ref
   ▼
 IAM Credentials（iamcredentials.googleapis.com）
   │  3. 以 principalSet（repository_id）身分 impersonate `risk-cap-writer`
   │     （writer SA 上只有一條 roles/iam.workloadIdentityUser 綁定；無專案層 IAM role）
   ▼
 短效 access token，scope＝https://www.googleapis.com/auth/spreadsheets
   │  4. 只對 System Risk Cap Sheet 有「編輯者」（Sheet 分享，不是 IAM role）
   ▼
 System Risk Cap Sheet（工作表 `risk_cap_daily`）

【讀取端（Streamlit Cloud，唯讀 key）】
 Streamlit secrets 內一份 `risk-cap-reader` JSON key（獨立 TOML 表格，見步驟 8）
   │  scope＝https://www.googleapis.com/auth/spreadsheets.readonly
   ▼
 只對 System Risk Cap Sheet 有「檢視者」（Sheet 分享）

【完全隔離】
 個人持股 Sheet：兩支新 SA 都 ⛔ 不被分享；⛔ 不沿用既有 `GCP_SERVICE_ACCOUNT_JSON`／`[gcp_service_account]`；⛔ 不沿用 fund-nav。
```

**設計要點**

- **writer 沒有任何 key**：憑證只在 job 執行期間以短效 token 存在；GitHub 端不放任何 Google 金鑰。
- **writer、reader 都沒有專案層 IAM role**：對 Sheet 的權限只靠 Google Sheet 的「分享」給予；專案 IAM policy 內不應出現這兩支 SA（驗證見第 5.3 節）。
- **scope 最小**：writer 只開 `spreadsheets`（⛔ 不開 Drive 系列，含 `drive.file` 也不用 —— Sheet 由客戶手動建立，寫入端不需要建檔權限）；reader 只開 `spreadsheets.readonly`。
- **reader 與 writer 身分完全分開**：兩支 SA、兩種憑證機制（WIF vs key）、兩種 Sheet 角色（編輯者 vs 檢視者）。

### 2.1 GitHub repository 識別值（公開資訊，可寫入文件）

| 值 | 內容 | 取得方式 |
|---|---|---|
| `REPO_ID`（repository_id） | **`1241930464`** | 撰寫組 2026-10-19 以 GitHub MCP `search_repositories`（`repo:linchen-20200325/my-stock-dashboard`）查得 `id` |
| `OWNER_ID`（repository_owner_id） | **`285537060`** | 同一查詢結果的 `owner.id`（owner `linchen-20200325`） |

自行複查：瀏覽 `https://api.github.com/repos/linchen-20200325/my-stock-dashboard`，看 `"id"` 與 `"owner": {"id": …}`。
⚠️ 用數字 ID 而非名稱的理由：repo／帳號改名或刪除後被他人重建同名，名稱會被重用，數字 ID 不會。

---

## 3. 共同權限原則（逐條對映）

| 原則（客戶原文） | 本規格如何落實 | 如何驗證 |
|---|---|---|
| 「risk-cap-writer / reader 都不得取得個人持股 Sheet 權限」 | 只把兩支 SA 分享到 System Risk Cap Sheet；個人持股 Sheet 的分享清單不得出現兩支 SA 的 email | 第 5.2 節反向測試 R1、R2＋分享清單人工檢查 |
| 「不得沿用 fund-nav」 | 不使用 fund-nav 的任何 SA、key、WIF pool／provider；兩支 SA 新建 | 第 5.3 節 C4 |
| 「System Risk Cap Sheet 與 holdings Sheet 完全隔離」 | 新建一本獨立 Sheet；不在持股 Sheet 內加工作表；Sheet ID 用獨立 secret 名稱 `RISK_CAP_HISTORY_SHEET_ID` | 第 5.2 節 R1、R2 |
| 「上線前必須做反向權限測試」 | 第 5.2 節 R1～R5 全部通過前，⛔ 不送 production 寫入核准題 | 第 5 節 |
| 「正式每日 production 寫入仍未核准」 | 本規格只到「身分與權限就緒」；程式端 `shared/risk_cap_history_policy.PRODUCTION_WRITE_APPROVED` 維持 `False`（本批未動） | — |

📌 「fund-nav」：本 repo `git grep -i fund-nav` 只有不相干的函式名 `fetch_fund_nav` 命中。客戶 2026-10-19 補充：既有 `GCP_SERVICE_ACCOUNT_JSON` **可能**屬於 fund-dashboard 專案的 fund-nav SA（客戶推測，未查證；見第 7 節第 1 點）。不論它是什麼，本規格**一律不碰**：⛔ 不修改／刪除／輪換／停用 fund-nav、⛔ 不影響每日持股推播、⛔ 不把 fund-nav 當 Risk Cap writer 或 reader。

---

## 4. 客戶手動設定步驟（Google Cloud Shell）

> **在哪裡跑**：Google Cloud Console 右上角「啟用 Cloud Shell」（`>_` 圖示）。所有指令可直接整段貼上。
> **先做 G3 嗎？** 不必等 G3。以步驟 0 確認的 Mystock20260823 專案為準；不要使用 fund-dashboard／fund-nav 所在專案。
> ⛔ **整個過程中，不要把任何 key 內容、`private_key`、完整 JSON 貼到聊天、AI、issue、PR 或 commit。**

### 步驟 0｜確認選到正確專案（顯示名稱 ≠ 專案 ID）

Google Cloud 專案有三個不同的值：**顯示名稱**（例：`Mystock20260823`）、**專案 ID**（全域唯一字串，常帶數字尾碼）、**專案編號**（純數字）。指令要的是**專案 ID** 與**專案編號**。

```bash
# 列出所有專案，找「NAME」欄是 Mystock20260823 的那一列，抄下它的 PROJECT_ID
gcloud projects list --format="table(projectId,name,projectNumber)"
```

```bash
# 把下一行的 PROJECT_ID 換成上面查到的「專案 ID」（不是顯示名稱）
export PROJECT_ID="PROJECT_ID"
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
export REPO_ID="1241930464"
export OWNER_ID="285537060"
export REPO_FULL="linchen-20200325/my-stock-dashboard"
export WRITER_SA="risk-cap-writer@${PROJECT_ID}.iam.gserviceaccount.com"
export READER_SA="risk-cap-reader@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"
# 確認：三行輸出應分別是 專案 ID／Mystock20260823／專案編號
gcloud projects describe "$PROJECT_ID" --format="value(projectId,name,projectNumber)"
echo "PROJECT_NUMBER=$PROJECT_NUMBER"
```

⚠️ Cloud Shell 斷線重連後 `export` 的變數會消失；重連後請重跑本步驟的 `export` 區塊。

### 步驟 1｜啟用 API

```bash
gcloud services enable \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  sheets.googleapis.com \
  cloudresourcemanager.googleapis.com
```

### 步驟 2｜建立兩支 service account（不給任何角色）

```bash
gcloud iam service-accounts create risk-cap-writer \
  --display-name="System Risk Cap writer (GitHub OIDC/WIF, no key)" \
  --description="Writes System Risk Cap history sheet only. NO JSON key allowed."

gcloud iam service-accounts create risk-cap-reader \
  --display-name="System Risk Cap reader (read-only)" \
  --description="Reads System Risk Cap history sheet only (Viewer)."
```

⛔ **不要**執行任何 `gcloud projects add-iam-policy-binding … --member=serviceAccount:risk-cap-…`。兩支 SA 在專案層**不需要任何 role**（包括 Editor／Viewer／Owner）。

### 步驟 3｜建立 Workload Identity Pool 與 GitHub OIDC Provider

```bash
gcloud iam workload-identity-pools create github-pool \
  --location="global" \
  --display-name="GitHub Actions pool"

gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub OIDC provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.ref=assertion.ref,attribute.workflow_ref=assertion.workflow_ref" \
  --attribute-condition="assertion.repository_id=='${REPO_ID}' && assertion.repository_owner_id=='${OWNER_ID}' && assertion.ref=='refs/heads/main' && assertion.workflow_ref=='${REPO_FULL}/.github/workflows/risk_cap_history_poc.yml@refs/heads/main'"
```

說明：

- `attribute-condition` 四個條件**同時**成立才發 token：本 repo（數字 ID）、本帳號（數字 ID）、`main` 分支、指定 workflow 檔。其他 repo／fork、其他分支、PR、其他 workflow 檔一律被拒。
- ⚠️ **workflow 檔名會變**：目前寫的是既有 PoC 檔 `risk_cap_history_poc.yml`。日後正式 production workflow 若用別的檔名（例：新建 `update_risk_cap_history.yml`），**必須同步更新此條件**，否則新 workflow 會被拒（安全方向的失敗，不會誤放行）。更新指令：
  ```bash
  gcloud iam workload-identity-pools providers update-oidc github-provider \
    --location="global" --workload-identity-pool="github-pool" \
    --attribute-condition="assertion.repository_id=='${REPO_ID}' && assertion.repository_owner_id=='${OWNER_ID}' && assertion.ref=='refs/heads/main' && assertion.workflow_ref=='${REPO_FULL}/.github/workflows/<新檔名>.yml@refs/heads/main'"
  ```
- 取得 provider 完整資源名稱（日後寫進 workflow；**不是 secret**）：
  ```bash
  gcloud iam workload-identity-pools providers describe github-provider \
    --location="global" --workload-identity-pool="github-pool" --format="value(name)"
  # 預期形如：projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github-pool/providers/github-provider
  ```

### 步驟 4｜只在 writer SA 上綁定 workloadIdentityUser

```bash
gcloud iam service-accounts add-iam-policy-binding "$WRITER_SA" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository_id/${REPO_ID}"
```

- 這條綁定**只做在 writer 上**；⛔ reader 上不做（reader 不得被 GitHub 冒用）。
- 綁定的是 SA 本身的 IAM policy，不是專案 IAM policy。

### 步驟 5｜只為 reader 建立 JSON key

⛔ **絕對不要對 writer 執行 `gcloud iam service-accounts keys create`**（G1：禁止建立 writer JSON key）。

```bash
gcloud iam service-accounts keys create "$HOME/risk-cap-reader-key.json" \
  --iam-account="$READER_SA"
```

把 key 轉成 Streamlit secrets 用的 TOML 片段（只在你自己的 Cloud Shell 畫面顯示，複製後貼到步驟 8）：

```bash
python3 - <<'PY'
import json, os
d = json.load(open(os.path.expanduser("~/risk-cap-reader-key.json")))
print("[risk_cap_history_reader]")
for k, v in d.items():
    print(f"{k} = {json.dumps(v)}")
PY
```

貼進 Streamlit secrets 後，**立刻刪除 Cloud Shell 上的檔案**（Cloud Shell 的 home 目錄會持久保存）：

```bash
shred -u "$HOME/risk-cap-reader-key.json" 2>/dev/null || rm -f "$HOME/risk-cap-reader-key.json"
ls -l "$HOME"/risk-cap-reader-key.json 2>&1   # 應顯示 No such file
```

⚠️ 這份 key **只放 Streamlit secrets**；⛔ 不放 GitHub secrets、⛔ 不存本機、⛔ 不寄信、⛔ 不貼到任何對話。
⚠️ 若 `keys create` 回報被組織政策（`iam.disableServiceAccountKeyCreation`）擋下：個人 Gmail 帳號建立、無組織的專案通常沒有此政策；若真的被擋，請停下回報，⛔ 不要自行關閉組織政策（屬 DEC-009 權限變更）。

### 步驟 6｜建立 System Risk Cap Sheet 並分享

1. 以客戶自己的 Google 帳號新建一本試算表（建議命名：`System Risk Cap History`）。
2. 把第一個工作表改名為 **`risk_cap_daily`**（大小寫須一致）。
3. 右上角「共用」：
   - 加入 `risk-cap-writer@<PROJECT_ID>.iam.gserviceaccount.com` → 角色 **編輯者**；
   - 加入 `risk-cap-reader@<PROJECT_ID>.iam.gserviceaccount.com` → 角色 **檢視者**；
   - **取消勾選「通知使用者」**；
   - 「一般存取權」維持 **「限制」**（⛔ 不要改成「知道連結的任何人」）。
4. 抄下網址中 `/d/` 與 `/edit` 之間那段字串 ＝ **Sheet ID**（步驟 7、8 用）。
5. ⛔ **不要**把這兩支 SA 分享到個人持股 Sheet；也不要在個人持股 Sheet 裡加這個工作表。

### 步驟 7｜GitHub 設定（只加一個 secret）

GitHub repo → Settings → Secrets and variables → Actions → New repository secret：

| 名稱 | 值 | 備註 |
|---|---|---|
| `RISK_CAP_HISTORY_SHEET_ID` | 步驟 6 的 Sheet ID | **唯一要新增的 GitHub secret** |

- ⛔ **`RISK_CAP_HISTORY_WRITER_SA_JSON` 已退役，不要建立**（G1 禁止 writer key ⇒ 沒有東西可以放進這個 secret）。
  ~~📌 該名稱目前仍保留在程式碼 `shared/risk_cap_history_policy.py` 第 177 行（`WRITER_SA_ENV_VAR`），並被 `src/data/macro/risk_cap_history.py` 的寫入前置檢查列為必填。**本批不改 code**；將於未來實作批次退役、改為檢查 WIF 設定（見第 6 節）。在那之前，PoC 的寫入路徑本來就被 `PRODUCTION_WRITE_APPROVED=False` 擋下，不受影響。~~
  📌 2026-10-19 更新（有意識的變更，不是漏刪）：#886（main `2c693a20`）已自 `shared/risk_cap_history_policy.py` 與 `src/data/macro/risk_cap_history.py` 退役 `WRITER_SA_ENV_VAR`；寫入 gate 仍一律 raise（`PRODUCTION_WRITE_APPROVED=False`）。gate 改為檢查 WIF 憑證屬未來批次（第 6 節第 4 項）。
  📌 `RISK_CAP_HISTORY_SHEET_ID` 尚未新增 —— 客戶刻意延到 Sheet 接線批（2026-10-19 客戶確認 (c)）。
- **不是 secret、日後直接寫在 workflow 裡**：WIF provider 完整資源名稱（步驟 3 末）、writer SA email。它們本身不構成可用憑證（沒有通過 attribute-condition 的 GitHub token 就換不到 access token）。
- ⛔ 不要修改、刪除既有 `GCP_SERVICE_ACCOUNT_JSON`（G3 只核准調查）。

### 步驟 8｜Streamlit secrets（reader）

Streamlit Cloud → App → Settings → Secrets，在**現有內容之後追加**（⛔ 不要改動既有段落）：

```toml
# System Risk Cap 系統歷史 Sheet 唯讀身分（DEC-064 G2）；與 [gcp_service_account] 完全分開
risk_cap_history_sheet_id = "<步驟 6 的 Sheet ID>"

[risk_cap_history_reader]
# ← 貼上步驟 5 轉出的整段（type / project_id / private_key_id / private_key / client_email / …）
```

- **名稱提案**：表格名 `[risk_cap_history_reader]`、頂層鍵 `risk_cap_history_sheet_id`。撰寫組 2026-10-19 對 repo 實查（`git grep` `gcp_service_account`、`google_oauth`、`st.secrets`）既有 secrets 段落為 `[gcp_service_account]`、`[google_oauth]` 與頂層鍵 `portfolio_sheet_id`、`FINMIND_TOKEN`、`FRED_API_KEY`、`GEMINI_API_KEY`、`PROXY_*` 等，**提案名稱與之不衝突**（單組 grep，非窮舉宣稱）。
- ⚠️ **必須與既有 `[gcp_service_account]` 不同名**：既有 SA 段落在 `SEC-3`（#877）後已不被網站匿名路徑使用，但仍可能存在；共用名稱會讓兩個身分混淆，重開 SEC-3 同類風險。
- ~~📌 程式碼 `shared/risk_cap_history_policy.py` 目前保留的讀取端名稱是環境變數式的 `RISK_CAP_HISTORY_READER_SA_JSON`（無任何程式路徑使用）；Streamlit secrets 實際採用的表格名將在未來讀取端實作批次定案並同步程式常數。**本批不改 code**。~~
  📌 2026-10-20 更新（VN1-STORE Production Wiring 批；有意識的變更，不是漏刪）：上列兩個提案名稱**照本節定案**為程式常數 `READER_SECRETS_TABLE`＝`risk_cap_history_reader`、`READER_SHEET_ID_SECRET_KEY`＝`risk_cap_history_sheet_id`（`shared/risk_cap_history_policy.py`）；環境變數式舊名稱已退役。讀取端 L3 `src/services/risk_cap_history_reader_service.py` **只**讀這兩個名稱（⛔ 沒有環境變數退路）。
- ~~現在貼進去**不會被任何程式讀取**（讀取端尚未實作），所以不影響網站。~~
  📌 2026-10-20 更新（有意識的變更，不是漏刪）：讀取端服務已實作，但**沒有任何畫面呼叫它**（UI 接線另案、須先出線框）⇒ 貼進去目前仍不影響網站。

---

## 5. 最小權限驗證計畫（**客戶完成第 4 節之後**才跑；~~本批未跑~~ **2026-10-20 P1／P2／R1～R5 全部 PASS，見 5.4**；有意識的變更，不是漏刪）

> 執行者：設定完成後由我們（AI 團隊）設計測試，需要時請客戶在 Cloud Shell／Actions 觸發；結果記錄於 PR 與本檔。
> ⛔ 第 5.2 節反向測試**全部通過前**，不送 production 寫入核准題。
> ⚠️ 正向測試 P1 需要「真的寫一列到 System Risk Cap Sheet」—— 這是**測試寫入**，不是正式每日 production 寫入；但仍屬寫入動作，執行前會先送客戶確認測試範圍（DEC-009）。

### 5.1 正向測試（應成功）

| ID | 測試 | 預期 |
|---|---|---|
| P1 | 在 `main`、允許的 workflow 檔內，經 WIF 取得 writer token，對 System Risk Cap Sheet `risk_cap_daily` append 一列測試資料 | 成功；該列可在 Sheet 看到（測試後依約定清除或標記） |
| P2 | 以 reader key、scope `spreadsheets.readonly` 讀取 System Risk Cap Sheet | 成功讀到內容 |

### 5.2 反向測試（應失敗；「失敗」才是通過）

| ID | 測試 | 預期 |
|---|---|---|
| R1 | writer token 讀／寫**個人持股 Sheet**（以既有持股 Sheet ID 測試） | `403 PERMISSION_DENIED` 或 `404 NOT_FOUND` |
| R2 | reader key 讀**個人持股 Sheet** | `403` 或 `404` |
| R3 | reader key 對 System Risk Cap Sheet **寫入**（append／update） | `403`（檢視者 ＋ readonly scope 雙重阻擋） |
| R4 | 從**非 main 分支**（例：測試分支）觸發同一 workflow 嘗試 WIF 換 token | STS 拒絕（attribute condition 不符），拿不到 token |
| R5 | 從**另一個 workflow 檔**（`main` 上）嘗試 WIF 換 token | STS 拒絕（`workflow_ref` 不符） |

📌 2026-10-21 補註（有意識的變更，不是漏刪；上表原文不改）：WIF hardening（8.7）後，R4／R5 的 job 都沒有 environment ⇒ **仍預期被拒，但已無法隔離 ref／workflow_ref 變因**（被拒也可能只因缺 `environment` claim）；10-20 的 PASS 證據在當時條件下仍有效。P1（`permission_test_writer`）同理實質退役。

📌 R1、R2 的錯誤碼不論是 403 還是 404 都算通過；**任何 2xx 都算失敗**，須立刻停下、移除該分享並回報。

### 5.3 設定檢查（Cloud Shell，唯讀）

| ID | 指令 | 預期 |
|---|---|---|
| C1 | `gcloud iam service-accounts keys list --iam-account="$WRITER_SA" --managed-by=user` | **空**（writer 沒有任何使用者管理的 key） |
| C2 | `gcloud iam service-accounts keys list --iam-account="$READER_SA" --managed-by=user` | **恰好 1 把** |
| C3 | `gcloud projects get-iam-policy "$PROJECT_ID" --flatten="bindings[].members" --filter="bindings.members:risk-cap-" --format="table(bindings.role,bindings.members)"` | **空**（兩支 SA 無專案層 role） |
| C4 | `gcloud iam service-accounts get-iam-policy "$WRITER_SA"`、`gcloud iam service-accounts get-iam-policy "$READER_SA"` | writer：只有步驟 4 那一條 `roles/iam.workloadIdentityUser`（principalSet＝本 repo ID）；reader：**無任何綁定**；兩者都不出現 fund-nav 相關成員 |
| C5 | `gcloud iam workload-identity-pools providers describe github-provider --location=global --workload-identity-pool=github-pool --format="value(attributeCondition)"` | ~~與步驟 3 的四條件一致~~ 2026-10-21 起：四條件＋`environment=='production-risk-cap'`＋`event_name=='workflow_dispatch'`（8.7；pool／provider 實際名稱為 `stock-dashboard-github`／`github-actions`；有意識的變更，不是漏刪） |
| C6 | 人工檢查：個人持股 Sheet「共用」清單 | **不含** `risk-cap-writer@…`、`risk-cap-reader@…` |
| C7 | 人工檢查：System Risk Cap Sheet「一般存取權」 | 「限制」 |

### 5.4 執行結果（2026-10-20；總管自 GitHub Actions log 查證；皆跑在 main `c01b74b9`＝#888 merge，#888 新增權限測試 job／腳本）

| ID | 結果 | run／job | 觀測 |
|---|---|---|---|
| P1 | **PASS** | run 39372770704／`permission_test_writer` | WIF 身分 `risk-cap-writer`；append → readback → delete → verify_gone 皆 ok；測試列已刪除 |
| R1 | **PASS** | run 39372770704（同上） | 兩個持股 Sheet（`PORTFOLIO_SHEET_ID`、`STOCK_PORTFOLIO_SHEET_ID`）讀取 GET → `403 PERMISSION_DENIED`（無 reason） |
| P2 | **PASS** | run 39373289602／`permission_test_reader` | 身分 `risk-cap-reader`、readonly scope；metadata 200、values 200、rows＝0 |
| R2 | **PASS** | run 39373289602（同上） | 兩個持股 Sheet → `403 PERMISSION_DENIED`（無 reason） |
| R3 | **PASS** | run 39373289602（同上） | append → `403 PERMISSION_DENIED`，reason `ACCESS_TOKEN_SCOPE_INSUFFICIENT` |
| R4 | **PASS** | run 39374189381／`wif_negative_r4`（暫時分支 `perm-test-r4·`） | STS `400 unauthorized_client`「The given credential is rejected by the attribute condition.」 |
| R5 | **PASS** | run 39374562365／`risk_cap_wif_negative_r5.yml`（main） | 同 R4 的 STS 拒絕 |

⚠️ **限制（照實保留）**：
1. R3 只證明 **readonly scope** 擋下寫入；「reader 在該 Sheet 是檢視者（Viewer ACL）」由**客戶手動檢查共用清單**確認，不是本測試證明。
2. P2 執行時 `risk_cap_daily` 為空 → 只證明「讀得到、分頁存在」，**不證明**既有歷史可讀。
3. R1 只以讀取 GET 測（安全唯讀解讀，見 DEC-065）；未對持股 Sheet 做寫入嘗試。
4. P2／R2／R3 使用一次性測試例外 secret `RISK_CAP_READER_TEST_SA_JSON`（DEC-065；不是 production 設計變更，reader key 仍只放 Streamlit secrets）。**客戶回報已清理**：該 GitHub secret 已刪除；2026-10-20 為測試建立的 reader JSON key 已自 GCP 刪除（2026-10-19 的 Streamlit 用 key 保留）；R4 暫時分支已刪除。
5. 權限測試 harness 保留在 repo 以利重現；reader job 在該 secret 已刪除的狀態下會**拒絕執行**。
6. ⛔ 全部 PASS **不是** production 授權：`PRODUCTION_WRITE_APPROVED` 仍為 `False`。

---

## 6. 日後仍需改 code／workflow 的事項（~~**未來實作批次，本批未做**~~ ~~**第 1～3 項 #886 已完成、第 4 項半完成，其餘未做**；2026-10-19 更新，有意識的變更，不是漏刪~~ ~~**第 1～4 項已完成（第 4 項由 Production Wiring 批補完，分支未合併）、第 6 項結構已接線，其餘未做**；2026-10-20 更新，有意識的變更，不是漏刪~~ **第 1～4、6 項已完成（Production Wiring 批 #890 已合併、main `56904662`；第 6 項由 Pre-Hardening 批改為共用 group，見第 8 節），第 5、8 項未做**；2026-10-20 更新，有意識的變更，不是漏刪）

~~本批只寫規格。~~（2026-10-20：本檔已不是「只寫規格」的批次產物，下列多數項目已實作；有意識的變更，不是漏刪）下列項目要等客戶指派實作批次、且 **production 寫入仍須另行核准**（DEC-063、DEC-009）：

1. ✅ #886 已完成（job `wif_auth_only` job 層級 `id-token: write`；其他 job 不受影響）。寫入 workflow 宣告 `permissions: id-token: write`~~（目前 `risk_cap_history_poc.yml` 只有 `contents: read`）~~（2026-10-20：已不成立 —— 頂層仍只有 `contents: read`，`id-token: write` 只在需要 WIF 的 job 層級宣告；有意識的變更，不是漏刪）。
2. ✅ #886 已完成（`google-github-actions/auth` v3.0.0 `7c6bc770`；checkout v4.3.1 `34e11487`、setup-python v5.6.0 `a26af69b`，皆完整 SHA）。使用 `google-github-actions/auth` 以 WIF 取得 writer 憑證，**以完整 commit SHA 釘版**（不用 tag）；`workload_identity_provider` 與 `service_account` 直接寫在 workflow（非 secret）。
3. ✅ #886 已完成。`.gitignore` 加入 `gha-creds-*.json`（該 action 預設會在 workspace 產生暫存憑證檔；搭配 checkout 在 auth 之前、不 commit workspace）。
4. ◐ #886 半完成：`WRITER_SA_ENV_VAR` 已退役；寫入前置檢查改為檢查 WIF 憑證、reader 端命名與 Streamlit 接線**未做**。
   📌 2026-10-20 更新（Production Wiring 批；有意識的變更，不是漏刪）：寫入前置檢查已改為檢查 WIF `external_account` 憑證檔（`load_writer_credentials_or_refuse` 第 4 步；第 1 步仍是 `PRODUCTION_WRITE_APPROVED=False` ⇒ 一律拒絕）；reader 端命名已定案（步驟 8）、L3 讀取服務已實作。**仍未做**：畫面（Streamlit UI）接線、production 寫入核准。程式端政策常數改名：退役 `RISK_CAP_HISTORY_WRITER_SA_JSON`（`shared/risk_cap_history_policy.py:177` `WRITER_SA_ENV_VAR`），寫入前置檢查（`src/data/macro/risk_cap_history.py`）改為檢查 WIF 提供的憑證；讀取端名稱與 Streamlit secrets 表格名（步驟 8 提案）定案並同步；相關測試（`tests/test_vn1_store_poc.py`）同步更新。
5. 若正式 workflow 換檔名 → 依步驟 3 更新 attribute-condition。
6. 寫入端 `concurrency` 序列化（單一寫入者，見 `VN1_STORE_RESEARCH.md` 8.4 第 2 點）。
   📌 2026-10-20（Pre-Hardening 批；有意識的變更，不是漏刪）：✅ 碰 Sheet／拿得到 writer 身分的 job（`wif_auth_only`、`permission_test_writer`、`permission_test_reader`、`production_write`）共用字面 job 層 group `risk-cap-history-sheet-write`（見第 8 節 C）；「讀全表再追加不是原子操作」的限制仍在，只靠序列化＋單一寫入者前提。
7. ✅ 2026-10-20 已完成（P1／P2／R1～R5 全部 PASS，見 5.4）。第 5 節驗證計畫執行並記錄結果。（~~⚠️ 2026-10-19：P1／P2／R1～R5 **仍未執行**；WIF auth-only PASS 不算第 5 節任何一項。~~ 2026-10-20 已不成立，有意識的變更，不是漏刪）

📌 2026-10-19 正式寫入前另需（已記錄、未做）：pip 安裝 hash-pin；GitHub environment（required reviewers）＋WIF condition 加 environment claim；WIF condition 加 `event_name`。另：checkout／setup-python 釘版觸發 Node 20 deprecation 警告（被強制以 Node 24 執行），屬日後 pin bump、不阻擋。
📌 2026-10-20 現況（有意識的變更，不是漏刪）：pip hash-pin 已完成（寫入 job，8.1；compute job 未鎖、列 LATER 候選）；GitHub environment＋WIF environment claim＋`event_name` 由客戶裁示 **DEC-066 C** 定為**首寫前 MUST**、固定順序見 8.11；Node pin bump 仍不阻擋。
8. `PRODUCTION_WRITE_APPROVED`（`shared/risk_cap_history_policy.py`）改為 `True` **只能在客戶另一次裁示後**（⛔ 不得自行改）。
   📌 2026-10-20：該次裁示已作出 —— **DEC-066 A**：核准**未來以獨立 PR** 一次性改為 `True`（前提：DEC-066 C Step 1～3 完成），首次人工寫入後不論成敗立即以獨立 PR 改回 `False`；⛔ 本項至今**未執行**（旗標仍 `False`）。

---

## 7. 未決／未驗證項目

1. **G3 調查待辦（本批未調查；只核准調查，不核准修改）**：
   - **客戶補充（2026-10-19）**：既有 `GCP_SERVICE_ACCOUNT_JSON` 可能屬於 fund-dashboard 專案的 **fund-nav** SA（推測，未查證）。
   - **要確認的事**：(a) 是否就是 fund-nav（`client_email`／`project_id`）；(b) 股票 repo 哪些功能用它 —— 撰寫組 2026-10-19 `git grep` 實查：`.github/workflows/push_holdings_daily.yml` ＋ `scripts/push_holdings_daily.py`（經 `src/data/portfolio/gsheet_sa_reader.py`，scope `spreadsheets.readonly`），以及手動診斷腳本 `scripts/diagnose_etf_total_return_fix.py`（`src/data/portfolio/gsheet_portfolio.py` 只在註解提及；單組 grep，非窮舉宣稱）；(c) 跨專案共用／權限過大風險評估；(d) 日後是否遷移到股票專用 SA —— **另案**評估，本批不做。
   - **repo 端無法判定所屬專案**：GitHub secrets 只能寫入、不能讀回。建議客戶開**個人持股 Sheet → 共用**對話框，看清單中 `*@<專案ID>.iam.gserviceaccount.com` 的那一列，`@` 後的專案 ID 即所屬專案（只需回報 email 或專案 ID，⛔ 不要貼 key）。
   - ⛔ 禁止：修改／刪除／輪換／停用 fund-nav 或既有 key；影響每日持股推播；沿用 fund-nav 作為 Risk Cap writer 或 reader；輸出 `private_key`／完整 JSON／其他 secret。若調查唯一可行方式需要改 workflow，先停下請示。
2. **`drive.file` 不使用**：writer 只用 `spreadsheets` scope；Sheet 由客戶手動建立，故寫入端不需要建檔／Drive 權限。
3. **quota project**：Sheets API 呼叫的配額計在哪個專案（預期為 SA 所屬的 Mystock20260823 專案，需在該專案啟用 Sheets API，即步驟 1）**未實測**。
4. **STS／IAM Credentials 費用**：撰寫組**未查證**官方計價頁；預期每日一次換 token 的量極低，但「免費」未經驗證，不得當成事實引用。
5. **Streamlit Cloud 無 workload identity**：撰寫組在 Streamlit Cloud 文件中**未找到**可對 Google 做 workload identity federation 的機制，故讀取端採 key（G2）。這是「文件中找不到」，**不是官方明文否定**。
6. **attribute-condition 與 `google.subject` 長度**：GitHub `sub` 形如 `repo:linchen-20200325/my-stock-dashboard:ref:refs/heads/main`，預期不超過 Google 的 subject 長度上限；**未實測**。
7. **PoC Actions 實跑**：客戶回報 run 39249934107 success（dry-run：狀態 VALID、`exposure_limit_pct` 30、同日重跑 APPENDED→NOOP_DUPLICATE）；撰寫組**未重查** run log／artifact。
8. ~~本檔所有 gcloud 指令**未在真實專案實跑**；~~（2026-10-19：客戶已依本檔在真實專案完成設定並確認 (a)～(f)，有意識的變更，不是漏刪）本檔 gcloud 指令以客戶實跑為準；第一次照做時若有錯，以實際錯誤訊息修正本檔。
9. **WIF auth-only 實跑紀錄（2026-10-19）**：run 39336051675（客戶手動 dispatch，main `2c693a20`，`mode`＝`wif-auth-only`）—— job `wif_auth_only` success；步驟「Authenticate to Google Cloud (WIF, no key)」「Verify impersonated identity」success；`poc-dry-run` skipped。log：GitHub OIDC → WIF STS → impersonation PASS；impersonated_email＝`risk-cap-writer@mystock20260823.iam.gserviceaccount.com`；project `mystock20260823`；token lifetime 約 3599s；scope 僅 `userinfo.email`；**未讀寫任何 Sheet**；憑證檔於 post step 移除（總管 GitHub API 查證）。⚠️ 這**不是**第 5 節 P1／P2／R1～R5；writer 仍未分享給 Sheet、Streamlit reader 未接線、production 寫入未核准。
10. **權限測試實跑紀錄（2026-10-20）**：P1／P2／R1～R5 全部 PASS（run 39372770704、39373289602、39374189381、39374562365；細節與限制見 5.4）。`VN1-STORE` 憑證／權限邊界 Gate **正式關閉**（⛔ 不是 production 授權）。仍未做（正式寫入前）：hash-pin pip；GitHub environment＋required reviewers＋WIF environment claim；WIF condition 加 `event_name`；Node 20 action pin bump；Streamlit reader 接線未實作；第 6 節第 4 項仍半完成。下一 Decision Gate（未指派）：是否開始 production writer／reader 接線批與 production 寫入核准。
11. **Production Wiring 批（2026-10-20）**：Production Wiring 批（分支 `claude/jolly-mccarthy-sonbl8`，commits `67701562`、`ef905cf0`（回修第 1 輪）；兩組獨立 QA 對 `67701562` 均 0 MUST-FIX（總管轉述）；~~**未開 PR、未合併**~~ **#890 已合併**，main `56904662`，PR Check run 39389812753 success（2026-10-20 撰寫組 `gh run view` 實查；有意識的變更，不是漏刪））。reader：L3 `src/services/risk_cap_history_reader_service.read_history` 已接線（只讀 Streamlit secrets `[risk_cap_history_reader]`＋`risk_cap_history_sheet_id`；只快取成功讀取；VALID 列缺上限值 ⇒ `CONTENT_SUSPECT`、不比較；**沒有任何 UI 呼叫端**）；writer：workflow `risk_cap_history_poc.yml` 新增 `production-write` mode（compute job 無 id-token → main-only 寫入 job），寫入 job 在任何 auth 之前先檢查核准旗標 ⇒ **目前恆紅、什麼都不寫**；`PRODUCTION_WRITE_APPROVED` 仍為 `False`；無 schedule；未變更 IAM／WIF／Sheet 分享。
    - **送交 production 每日寫入最終核准前仍需**：(1) write job 依賴 hash-pin＋精簡（目前裝完整 `requirements.txt`、經 `src.data.macro` barrel eager 載入；QA-A S1）；(2) GitHub Environment＋required reviewers＋WIF attribute condition 加 environment claim 與 `event_name`（目前核准只剩 L0 常數；QA-A S3）；(3) 首次實跑驗證計畫（核准後路徑 —— WIF 憑證 → gspread → `upsert_record` —— 未端到端實跑；QA-A S2）；(4) WIF 憑證檔 `audience` 未核對（QA-A N1）；(5) 只重跑寫入 job 會沿用舊 artifact（QA-A N2）；(6) 畫面顯示歷史須先過線框（DEC-003 ①）；(7) 每日 schedule 本身須另行核准（目前只有 workflow_dispatch）；(8) Streamlit secrets 實際內容（`[risk_cap_history_reader]`、`risk_cap_history_sheet_id`）為客戶回報、未查證；(9) Node 20 action pin bump —— **不阻擋核准**（理由見 `docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md` 第 6 節 📌：Node 20 deprecation 警告、runner 已強制以 Node 24 執行，屬日後 pin bump）；📌 2026-10-20 補列（有意識的調整，不是漏刪）：舊清單（規格第 7 節第 10 點）有此項、本清單初版漏列，現補回並標明不阻擋；(10) 寫入併發限制：L1 `src/data/macro/risk_cap_history.py` 檔頭記載「讀全表再追加不是原子操作，兩個寫入者同時跑仍可能各追加一筆」，目前只靠 workflow／job `concurrency` 序列化＋單一寫入者前提 —— 正式化前須處理或由客戶明確接受。
    - **刻意設計（2026-10-20 補記）**：`CONTENT_SUSPECT` 判定為**全表範圍**（任一 VALID 列不符 ⇒ 整次讀取不回傳），只要求上限值是「有限數字」、⛔ 不新增任何範圍門檻（`-5`、`1e3` 等數值仍算可解析、不判疑義）。
    - **本批限制**：Google／Streamlit 實際連線**未測**（全以假物件）；本機 Python 3.13、CI 3.11；QA-B NIT-2／NIT-4 依總管裁定不處理（內容見該輪 QA 回報，本檔未轉錄）。
    - ⚠️ 上一則（第 10 點）「Streamlit reader 接線未實作；第 6 節第 4 項仍半完成」「下一 Decision Gate（未指派）」自本批起不再成立（有意識的變更，不是漏刪）；production 每日寫入核准**仍未送題、未核准**。
    - 📌 2026-10-20（Pre-Hardening 批；有意識的變更，不是漏刪）：上列前置清單各項的現況見**第 8 節 8.8**（(1) 已做；(3) 程式已備、未實跑；(4) 已查證；(5) 已加 sha256 比對；(10) 已改共用 group、限制仍在；(2)(6)(7) 仍是客戶 Gate）。L1 儲存端已由 `src/data/macro/risk_cap_history.py` 搬到 `src/data/risk_cap/history.py`（本節與第 6 節較早的舊路徑是當時紀錄，不改寫）。
    - 📌 2026-10-20（DEC-066；有意識的變更，不是漏刪）：上方「production 每日寫入核准**仍未送題、未核准**」自本日起不再成立 —— 客戶已裁示 DEC-066：首次人工寫入有條件核准、每日排程 NOT APPROVED；(8) reader smoke 空表狀態 PASS（8.10）；(10) 客戶已接受（DEC-066 D）。現況以 8.8、8.11 為準。

---

## 8. Pre-Hardening 結果（2026-10-20；~~production 寫入**仍未核准**、~~ 現況：首次人工寫入已有條件核准（DEC-066，前提未完成、旗標仍 `False`）；Daily Schedule 未核准；`PRODUCTION_WRITE_APPROVED` 仍為 `False`；2026-10-20 更新，有意識的變更，不是漏刪）

> **狀態**：程式＋文件批（分支 `claude/jolly-mccarthy-sonbl8`，基於 main `56904662`）。⛔ 無 schedule、⛔ 無新 workflow 檔、⛔ 未加 `environment:`、⛔ 未改 IAM／WIF／Sheet 分享／OAuth／fund-nav、⛔ 未改 Risk Cap 公式／門檻／語意／資料源、⛔ 畫面零變化。
> 下文 8.6、8.7、8.9 是**未執行的設計提案**，每一步都是**客戶人工 Gate**；⛔ 本批一步都沒做。
> 📌 2026-10-20（DEC-066）：8.6／8.7 已由客戶裁示為**首寫前 MUST**（固定順序 Environment → workflow `environment:` → WIF condition → 首寫，見 8.11）；8.9 已裁示為**延後、另案**（Daily Schedule NOT APPROVED）。各步仍**未執行**。
> ⚠️ provenance（`CLAUDE.md` §-2 規則 6）：本節由實作組單組撰寫；8.6／8.7 的修正依總管轉交之第二組獨立覆核意見（經總管轉述、非逐字）；其餘未經第二組驗證。

### 8.1 A｜寫入依賴（hash 鎖定、精簡）

- **搬移**：L1 儲存端 `src/data/macro/risk_cap_history.py` → `src/data/risk_cap/history.py`（`git mv`）；新套件 `__init__` 只有 docstring（⛔ barrel／re-export shim）。理由：`src.data.macro` 是 eager barrel，一 import 就載入 `macro_core`（pandas／streamlit…）。
- **鎖定檔**：`requirements-risk-cap-writer.txt`（輸入 `requirements-risk-cap-writer.in`：gspread／google-auth／requests，版本範圍＝`requirements.txt` 同名行）。
  產生方法：`uv pip compile requirements-risk-cap-writer.in --generate-hashes --python-version 3.11 --python-platform x86_64-unknown-linux-gnu --exclude-newer 2026-10-06 -o requirements-risk-cap-writer.txt`（uv 0.11.32；2026-10-20）。結果 15 個套件全部 `==` 釘版＋sha256（gspread 6.2.1、google-auth 2.60.0、requests 2.34.2 與其遞移依賴）；⛔ 無 pandas／numpy／streamlit。
- **workflow**：寫入 job 改為 `pip install --require-hashes --no-deps -r requirements-risk-cap-writer.txt`（⛔ 不裝 `requirements.txt`）；compute job 照舊裝完整 `requirements.txt`。
- **本機驗證（實作組，2026-10-20）**：乾淨 Python 3.11 venv —— `uv pip sync --require-hashes` 成功；`pip install --require-hashes --no-deps -r …` 成功；`--write`／`--precheck`／`--verify-written` 皆到閘門 exit 2，且 pandas／numpy／streamlit 一個都沒載入（該 venv 根本沒有裝）。守衛：`tests/test_vn1_prehardening.py`。
- ⚠️ 限制：沒在 GitHub runner 上實跑安裝（寫入 job 在閘門就停，本批也不能觸發）。

### 8.2 B｜WIF audience 證據（唯讀查證；⛔ 未改任何設定）

- `google-github-actions/auth` v3.0.0（本 repo 釘 `7c6bc770dae815cd3e89ee6cdf493a5fab2cc093`）`src/main.ts` 第 80–81 行：`oidcTokenAudience = getInput('audience') || 'https://iam.googleapis.com/${workloadIdentityProvider}'` —— 沒給 `audience` 時，預設 aud＝`https://iam.googleapis.com/` ＋ provider 完整資源名稱（2026-10-20 實作組讀 raw 原始碼實查）。
- 本 repo workflow **沒有** `audience:` 輸入（`grep audience .github/workflows/*.yml` 0 命中）。
- 以預設 aud 的 STS 交換**已成功**：run 39336051675（wif-auth-only）、run 39372770704（permission-test-writer P1），兩者 conclusion＝success、皆在 main（2026-10-20 實作組 `gh run view` 實查 conclusion；log 內容見第 7 節第 9 點與 5.4）。
- **客戶唯讀確認指令**（Cloud Shell；預期輸出為**空**＝只接受預設 aud）：
  ```bash
  gcloud iam workload-identity-pools providers describe github-actions \
    --location=global --workload-identity-pool=stock-dashboard-github \
    --format="value(oidc.allowedAudiences)"
  ```
  ⚠️ 這一步**未執行**（我們沒有 GCP 存取）；屬客戶唯讀確認。

### 8.3 C｜併發

- 碰 Sheet 或拿得到 writer 身分的 job —— `wif_auth_only`、`permission_test_writer`、`permission_test_reader`、`production_write` —— 共用**字面** job 層 group `risk-cap-history-sheet-write`（`cancel-in-progress: false`）。原 `production_write` 自己的 group `risk-cap-history-production-write` 已改名（workflow 內加刪除線註記）。
- workflow 層 group `risk-cap-history-poc` 不變、與上者不同名。
- 守衛：`tests/test_vn1_prehardening.py`（用 auth action／跑權限驗證腳本／`--write` 的 job 一律要有該 group；workflow group 字面且不同名；任何 job 不得有 `environment:`；拿掉 group ⇒ 紅燈）。
- ⚠️ 限制照舊：讀全表再追加不是原子操作；序列化只保證「這個 repo 的這些 job」彼此不同時跑。~~GitHub 的 concurrency 對**排隊中**的 job 只保留最新一個（較早的排隊 job 會被取消 ⇒ 不寫、紅燈，安全方向）。~~（回修第 1 輪 2026-10-20 措辭更正，有意識的變更，不是漏刪：GitHub concurrency 沒有「排隊」）同一 group 同時最多一個執行中＋一個 pending；**新的 pending 取代舊的 pending、舊的被取消**＝fail-closed（被取消的那次什麼都不寫、紅燈）。
- ⚠️ 照實：workflow 層 group `risk-cap-history-poc` 已讓本檔所有 run 彼此序列化 ⇒ 現況下這個 job 層共用 group **不增加額外保護**；它的用途是日後拆檔或改 workflow 層 group 時，碰 Sheet 的 job 仍互斥。

### 8.4 D｜首次 production 寫入的驗證計畫（程式已備、**未執行**；只在閘門之後才走得到）

- **寫入的紀錄**：就是 compute job 真算出來的那一列（與 dry-run 同一支腳本）；⛔ 不寫測試列。
- **順序**（`scripts/risk_cap_history_poc.py --write`）：閘門（`PRODUCTION_WRITE_APPROVED`）→ 紀錄檔合 schema → **寫前檢查**（writer 身分的**唯讀** token 讀全表；L1 `precheck_target`）→ `upsert_record`（讀寫 token）→ **寫後讀回驗證**（唯讀 token；L1 `verify_written`）。
- **寫前檢查**（全部列出、不短路）：表是空的或第一列逐字等於 schema 表頭；沒有第二列表頭／超長列；表內沒有 `PERMISSION_TEST…` 殘留（去頭尾空白、不分大小寫）；同（record_date, ruleset_version）沒有任何一列（去頭尾空白後比；只用於寫前檢查，`upsert_record` 語意不變）；`record_date`＝寫入當下台北日期；規則版本／schema 版本＝現行；本輪 `GITHUB_RUN_ID`＝紀錄裡的 run_id。
- **寫後驗證**：表頭在第一列且唯一；run_id＋record_date 相符的列**恰好一列**；逐欄等於紀錄。
- **fail closed、⛔ 不自動刪除**：任何一步失敗 ⇒ exit 非 0（4＝寫前檢查不過、什麼都沒寫；5＝寫後驗證不過；1＝I/O 失敗；3＝同日衝突）。~~**自動回滾（刪列）未經客戶核准** —— 需要的話須另行裁示；~~ 📌 2026-10-20 **DEC-066 E 定案**（有意識的變更，不是漏刪）：自動刪列／自動 rollback／自動覆寫／盲目 retry **永久禁止**；需刪無效列只能由客戶在 Google Sheets UI 人工執行、刪前先存證；production 程式永久不得因此新增自動刪列功能。首筆真實紀錄寫進去後**保留**（含不可抗力留下的非 VALID 列，DEC-066 B）。
- **artifact 完整性**：compute job 印出並輸出紀錄檔 sha256；寫入 job 下載後（任何 auth 之前）以 `sha256sum --check --strict` 比對，不一致或空值 ⇒ 紅燈不寫（處理 QA-A N2「只重跑寫入 job 會沿用舊 artifact」的**完整性**面；重跑本身仍會沿用同一 run 的 artifact）。
- **證據**（首次實跑時收集）：run id、artifact sha256、`precheck:` 與 `verify:` 兩行 JSON（只含固定字彙、計數、sha256）。
- **讀回兩條路**：(1) writer 身分唯讀 token（同一次 run 內）；(2) 網站 reader smoke（8.5，另一個身分）—— 兩者的最新列 sha256 應一致。
- ⛔ **任何一步失敗 ⇒ 不開排程**（8.9）。
- 守衛：`tests/test_vn1_first_write_verify.py`（空表、只有表頭、表頭錯、同鍵、殘留、日期、版本、0／1／2 列相符、欄位不同、突變自驗；workflow 內寫前／寫後步驟都在閘門之後）。

### 8.5 R｜網站 reader 真連線 smoke（log-only、⛔ 畫面零變化；**未在 Streamlit Cloud 實跑**）

- `app.py` 開機呼叫一次 `run_smoke_if_flagged()`；**只有** Streamlit secrets 頂層 `risk_cap_history_smoke = true`（TOML 布林，恰好 `True`）才跑，每個行程一次；沒設／字串 `"true"`／其他值 ⇒ 零 Google 呼叫。
- smoke 走與畫面讀取同一條路徑（secrets → L1 reader client → `risk_cap_daily`），但**繞過快取**。印**一行** smoke log（讀取失敗時另會多一行既有的 `[risk_cap_history_reader]` 分類 log，固定文字＋類別名）：`[risk_cap_history_smoke] read_status=… identity_ok=… header_state=ABSENT|MATCH|MISMATCH|NOT_READ data_rows=… latest_record_date=… latest_run_id=… latest_row_sha256=… compare_status=…`；⛔ 不印任何儲存格值、Sheet ID、例外原文。smoke 本身若有程式 bug ⇒ 只印例外類別名、⛔ 不讓網站掛掉（全 repo 唯一刻意不往上拋的地方；只接 `Exception`、⛔ 不接 KeyboardInterrupt／SystemExit；⛔ 不保護 import 失敗）。Google API 請求一律設逾時（L0 `SHEETS_HTTP_TIMEOUT_S`＝connect 5 秒、read 10 秒；reader 與 writer 皆然），逾時歸 `API_ERROR`。
- **客戶步驟（人工 Gate、未執行）**：(1) Streamlit Cloud → Secrets 頂層加 `risk_cap_history_smoke = true` → 儲存（app 會重啟）；(2) 開一次網站；(3) Manage app → Logs 找 `[risk_cap_history_smoke]` 那一行回報（整行可貼，不含 secret）；(4) 看完把該行改回 `false` 或刪除。首次寫入前預期 `read_status=EMPTY`、`header_state=ABSENT` 或 `MATCH`。
- 守衛：`tests/test_vn1_reader_smoke.py`；app.py 只准一行 import＋一行無參數呼叫（`tests/test_vn1_store_poc.py::assert_app_only_smoke_hook`）。

### 8.6 GitHub Environment 設計（📌 2026-10-21：**Step 1～3 ✅、Step 4 未做**；下方括號為前版狀態，保留追溯；~~**提案、未執行；客戶人工 Gate**~~ ~~**DEC-066 C：首寫前 MUST、仍未執行；客戶人工 Gate**；2026-10-20 更新，有意識的變更，不是漏刪~~ **DEC-066 C：Step 1 已完成（客戶建立）、Step 2 ~~本 PR~~ PR #894（workflow wiring；合併後完成）；Step 3／4 未做**；2026-10-21 更新，有意識的變更，不是漏刪）

- 名稱 `production-risk-cap`；required reviewer＝owner（唯一 reviewer）；**prevent self-review 關閉**（唯一 reviewer 就是觸發者，打開會永遠無法核准）；**關閉 admin bypass**（📌 2026-10-20 盤點：GitHub 預設**開**、須手動取消勾選；DEC-066 C：取當下 UI 可達成的最嚴格設定，UI 與盤點不同 ⇒ 不猜、停下回報）；deployment branches＝~~只限 `main`~~ **Selected branches → `main`**（2026-10-20 DEC-066 C 指定選項，有意識的變更，不是漏刪：main 未受保護，選「Protected branches only」會讓**所有分支**可部署）；environment secret `RISK_CAP_HISTORY_SHEET_ID`（之後可移除 repo 層同名 secret —— 另行確認）。
- ⚠️ **誠實定位**：這個 Gate 是「**刻意多按一次**」—— 唯一 reviewer＝觸發者，**不是職責分離、不是兩人控管**，也**防不了帳號被盜**（盜得到帳號就按得到核准）。它擋的是「誤觸發」與「沒有 environment 的 job 換到 writer token」（後者要配合 8.7）。
- **順序（每一步都是客戶手動；⛔ 本批一步都沒做）**：
  1. 客戶建立 environment（上列設定）；
  2. 合併在 `production_write` job 加 `environment: production-risk-cap` 的 workflow 變更（⚠️ 先後不可顛倒：引用不存在的 environment 會**自動建立一個沒有保護的** environment）；
  3. 客戶更新 WIF attribute condition（8.7）；
  4. 反向測試：`wif-auth-only` 被 STS 拒絕（新的預期結果）；
  5. `production-write` 觸發 ⇒ 停在等待核准 ⇒ 核准後在閘門紅燈（`PRODUCTION_WRITE_APPROVED` 仍 False）。
- 📌 2026-10-20 **DEC-066 C**（客戶裁示；有意識的變更，不是漏刪）：上列 1～3 步即 DEC-066 C Step 1～3，**順序固定**；Step 3 須先由客戶提供 provider **現行 describe 原文**、⛔ 不得猜測現行 condition。第 4、5 步為 Step 3 之後、Step 4（首寫）之前的驗證（撰寫組讀法）。總管上一輪推薦「首寫先跳過 Environment」**已被客戶否決**。設定細節與首寫 Runbook 見 8.11。
- 📌 2026-10-21（DEC-066 C Step 1／2；有意識的變更，不是漏刪）：上列「⛔ 本批一步都沒做」描述的是 Pre-Hardening 批當時，仍屬實；自本日起現況為 ——
  - **第 1 步 ✅**：客戶已在 GitHub UI 建立 `production-risk-cap`（客戶畫面逐項確認、總管轉述；實際設定見 8.11.2 末段）。
  - **第 2 步：~~✅ 本 PR~~ PR #894（合併後完成）**（2026-10-21 更新，有意識的變更，不是漏刪）：`.github/workflows/risk_cap_history_poc.yml` 只有 job `production_write`（needs compute、有 id-token、執行 `--write` 的唯一 production 寫入 job）加 job 層純字串 `environment: production-risk-cap`；compute／dry-run／`wif_auth_only`／三個權限驗證 job／R4 與 R5 檔一律沒有。守衛：`tests/test_vn1_prehardening.py` E 節。
  - **第 3～5 步 ⏳ 未做**（下一 Gate＝客戶提供 WIF provider 現行完整 describe 原文；⛔ 不得猜測現行 condition）。
  - 📌 2026-10-21（有意識的變更，不是漏刪）：**第 3、4 步 ✅**（WIF condition 已更新；反向驗證 run 39589906182 `wif-auth-only` 被拒 ⇒ 預期結果）；第 5 步正向（`production-write` 換 token）**未實測**，將於首次人工 production write 發生。下一則「第 3 步完成前只擋 `production_write`」自本日起不再成立 —— 現況：無 environment 的 job 一律取不到 writer token。
  - ⚠️ **第 3 步（WIF environment condition）完成前，Environment 只擋 `production_write`**：`wif_auth_only` 與 `permission_test_writer` 在 main 上仍可**不經核准**取得 writer token（後者 P1 會以 writer 身分 append 再刪除一列測試列）；兩者依 DEC-066 C 範圍不掛 environment，等第 3 步讓 STS 拒絕無 environment 的 job 才收口（見 8.7「後果」）。
  - ⚠️ 掛上後 `production_write` 的 OIDC `sub` 由 `repo:linchen-20200325/my-stock-dashboard:ref:refs/heads/main` 變為 `repo:linchen-20200325/my-stock-dashboard:environment:production-risk-cap`（GitHub 官方文件：有 environment 的 job，`sub` 用 environment 形式），並多一個 `environment` claim。現行 WIF condition（依本檔第 4 節與 BACKLOG 紀錄）比對 repository_id／repository_owner_id／ref／workflow_ref、**不比對 sub**；`principalSet` 綁的是 `attribute.repository_id` ⇒ **預期**仍可換 token —— **依官方文件推論、未實測**（`PRODUCTION_WRITE_APPROVED`＝False，閘門在 auth 之前紅燈，本批不會實際換 token）。`google.subject` 對映 `assertion.sub`（第 4 節步驟 3），新值長度遠低於 127 bytes 上限。
  - 掛上 environment 後，`production-write` 觸發時寫入 job 會先**停在等待核准**（compute job 不受影響、照常先跑）；核准後第一步閘門照舊紅燈。

### 8.7 WIF attribute condition 更新提案（📌 2026-10-21：**DEC-066 C Step 3 ✅ 完成**（客戶執行）；下方括號為前版狀態，保留追溯；~~**提案、未執行；客戶人工 Gate**~~ **DEC-066 C Step 3：首寫前 MUST、仍未執行；客戶人工 Gate**；2026-10-20 更新，有意識的變更，不是漏刪）

> 📌 2026-10-20 DEC-066 C：客戶點名新增 `environment == production-risk-cap`、`event_name == workflow_dispatch` 兩條；下方建議中的 `runner_environment`、`ref_type` **不在客戶點名範圍**，列 backlog 候選（`docs/BACKLOG.md` 5.1.4 `VN1-PG-L-CLAIMS`），⛔ 未經客戶另裁示不併入 Step 3。修改前以客戶提供的 describe 原文為準。

- 📌 **2026-10-21 實際執行（有意識的變更，不是漏刪）**：客戶於 Cloud Shell 以 `gcloud iam workload-identity-pools providers update-oidc github-actions --location=global --workload-identity-pool=stock-dashboard-github`（project `mystock20260823`）**只傳 `--attribute-condition`**。實際條件＝
  ```
  assertion.repository_id=='1241930464' && assertion.repository_owner_id=='285537060' && assertion.ref=='refs/heads/main' && assertion.workflow_ref=='linchen-20200325/my-stock-dashboard/.github/workflows/risk_cap_history_poc.yml@refs/heads/main' && assertion.environment=='production-risk-cap' && assertion.event_name=='workflow_dispatch'
  ```
  （總管提供字串；修改後 describe 由客戶確認一致，**撰寫組未見 describe 原文**）。attribute mapping 5 項（`attribute.ref`／`attribute.repository_id`／`attribute.repository_owner_id`／`attribute.workflow_ref`＝對應 assertion、`google.subject=assertion.sub`）**完全保留**、state ACTIVE。
  - ⚠️ **未採用** 下方建議中的 `runner_environment`、`ref_type`（不在 DEC-066 點名範圍，`VN1-PG-L-CLAIMS`）；下方 8 條指令**保留作追溯、未執行**。
  - mapping 未新增 `attribute.environment`／`attribute.event_name` 的依據：IAM API 允許 condition 直接引用 `assertion.*`；`google-github-actions/auth` 文件曾稱需映射，但 update 成功、無報錯（撰寫組讀法；未另行實測）。
  - **反向驗證**：客戶在 main 手動 run 39589906182（`mode=wif-auth-only`、main、event `workflow_dispatch`、head `17e8ee44`、conclusion failure、2026-10-21 11:09Z；撰寫組 GitHub API 實查）；annotation 顯示 `google-github-actions/auth` 在產生 federated token 階段失敗、其他 job 未執行 ⇒ 預期結果。STS 回應原文撰寫組未見。
  - **未驗證**：claim 缺席時 STS 的回應字樣；Environment 核准後 claim 不變；SA 綁定逐字內容；`production_write` 正向換 token（首次正向驗證＝Step 4 首次人工 production write）。
  - 決策紀錄：總管撤回「暫時讓 `wif_auth_only` 掛 environment 做正向驗證」建議，改採靜態比對＋反向驗證；客戶依此執行（不是新 DEC）。
- **建議條件**：既有四條 `&& assertion.event_name=='workflow_dispatch' && assertion.environment=='production-risk-cap' && assertion.runner_environment=='github-hosted' && assertion.ref_type=='branch'`。
  ```bash
  gcloud iam workload-identity-pools providers update-oidc github-actions \
    --location=global --workload-identity-pool=stock-dashboard-github \
    --attribute-condition="assertion.repository_id=='1241930464' && assertion.repository_owner_id=='285537060' && assertion.ref=='refs/heads/main' && assertion.workflow_ref=='linchen-20200325/my-stock-dashboard/.github/workflows/risk_cap_history_poc.yml@refs/heads/main' && assertion.event_name=='workflow_dispatch' && assertion.environment=='production-risk-cap' && assertion.runner_environment=='github-hosted' && assertion.ref_type=='branch'"
  ```
  ⚠️ 執行前先以 5.3 C5 唯讀指令印出現行條件逐字比對前四條，⛔ 以現行字串為準（上面四條依本檔與 BACKLOG 紀錄重組，未對 GCP 實查）。
- **替代方案與取捨**：(a) 更新既有 provider 條件 —— **推薦**；(b) 只靠 GitHub Environment、不改 WIF —— 否決：Environment 只管 workflow 層，STS 仍會發 token 給任何沒有 environment 的 job；(c) 另開 provider／pool —— 否決：**同一 pool 另開 provider 不行**（`principalSet` 綁定是 pool 範圍，舊 provider 仍可冒用）；**另開 pool 可行但目前不必要**（客戶已確認 pool 只有一個 provider）。
- **後果（照實）**：條件更新後，同 workflow 的 `wif_auth_only`、`permission_test_writer` **會被 STS 拒絕**（除非也掛 environment）—— 屆時二擇一：退役，或保留為「預期被拒」的反向測試。**R4 語意改變**：沒有 environment 的 job 一律被拒，R4 不再單獨測「分支條件」。條件更新後須實測「無 environment 的 job 被 STS 拒」作為**新反向測試**。
- **CEL 讀法**：缺席的 claim（例如沒有 environment 的 job 沒有 `environment`）在 CEL 下是 error；`&&` 下結果只會是 false 或 error，**不會是 true**。「GCP 把 error 視為拒絕」—— **官方文件未取得、待實測**（上一點的新反向測試即用來證明）。

### 8.8 `VN1-STORE-PROD` 前置清單現況（對照 `docs/BACKLOG.md` 1.1）

| # | 項目 | 現況 |
|---|---|---|
| (1) | write job 依賴 hash-pin＋精簡 | ✅ 本批（8.1） |
| (2) | GitHub Environment＋WIF environment／event_name claim | ⏳ 設計已備（8.6／8.7），**客戶人工 Gate、未執行**；📌 2026-10-20 **DEC-066 C：首寫前 MUST**，順序 Environment（`VN1-PG-ENV`）→ workflow `environment:`（`VN1-PG-WIRE`）→ WIF condition（`VN1-PG-WIF`）→ 首寫；📌 2026-10-21：Environment ✅（客戶建立）、workflow `environment:` ~~✅ 本 PR~~ PR #894（合併後完成）；WIF condition ⏳、首寫 ⏳ |
| (3) | 首次實跑驗證計畫 | ◐ 程式已備（8.4），**未實跑**（須翻旗標才走得到）；📌 2026-10-20 Runbook 見 8.11（DEC-066 A／B／E） |
| (4) | WIF 憑證檔 `audience` | ✅ 原始碼＋實跑證據（8.2）；allowedAudiences 為空待客戶唯讀確認 |
| (5) | 只重跑寫入 job 沿用舊 artifact | ◐ 加 sha256 比對（完整性）；沿用同一 run artifact 的行為不變 |
| (6) | 畫面顯示歷史須先過線框 | ⏳ 未動（DEC-003 ①） |
| (7) | 每日 schedule 另行核准 | ⏳ 未動；與 environment 核准互斥，見 8.9；📌 2026-10-20 **DEC-066 F：NOT APPROVED**、獨立 Gate、⛔ 禁止新增 `schedule:` |
| (8) | Streamlit secrets 實際內容未查證 | ◐ smoke 已備（8.5），~~**未實跑**~~ ✅ 2026-10-20 空表狀態真連線 **PASS**（8.10；有意識的變更，不是漏刪）；有資料狀態待首寫後（`VN1-PG-READBACK`，不是 blocker） |
| (9) | Node 20 action pin bump | 不阻擋（未動） |
| (10) | 寫入併發 | ◐ 共用 group（8.3）；非原子限制仍在，~~須處理或客戶明確接受~~ ✅ 2026-10-20 **客戶已接受**（DEC-066 D：單一 workflow writer＋concurrency；⛔ distributed lock、⛔ 第二 writer；出現第二 writer 重開 Decision Gate） |
| (11) | 每日排程 vs environment 人工核准（8.9） | 📌 2026-10-20 DEC-066 F：延後到首次人工寫入驗證完成後另案裁示 |
| (12) | 失敗政策 | 📌 2026-10-20 DEC-066 E：FAIL-STOP（見 8.11） |

### 8.9 新 Decision Gate：每日排程 vs environment 人工核准（~~**未送題**~~ **已裁示 DEC-066 F：延後、另案**；2026-10-20 更新，有意識的變更，不是漏刪）

- 兩者**互斥**：掛了 required reviewer 的 environment，`schedule` 觸發的 run **每天都會停下等核准**（最長 30 天後失效）；且 8.7 的 `event_name=='workflow_dispatch'` 也必須放行 `schedule`。
- ⇒ **開排程前必須客戶裁示信任模型**（例：每天人工按一次／排程不掛 reviewer 改靠其他控制／不開排程）。總管推薦方案待前置清單完成後一併附上；⛔ 本批不送題、不開排程。
- 📌 2026-10-20 **DEC-066 F**：Daily Schedule＝**NOT APPROVED**；首次人工寫入與每日排程是兩個獨立 Gate；⛔ 禁止新增 `schedule:`；排程設計、Environment 分流、unattended write 全部延後到首次人工寫入驗證完成後另案裁示。上句「待前置清單完成後一併附上」自本日起改為「待首次人工寫入驗證完成後另案送題」（有意識的變更，不是漏刪）。

### 8.10 reader 真連線 smoke 結果與空白分頁修正（2026-10-20）

- **smoke 結果**（客戶於 Streamlit Cloud 實跑、總管轉述；撰寫組未見 log 原文）：`read_status=SCHEMA_MISMATCH header_state=MISMATCH data_rows=0`。⇒ 真實讀取路徑（Streamlit secrets → reader 身分 → 以 ID 開 `risk_cap_daily` → 讀全表）**已證明可連**；錯的是對空表的判讀。
- **根因**：gspread 6.2.1 `gspread/worksheet.py:962` `values = response.get("values", [[]])`（Sheets API 對空範圍省略 `values` 鍵），`:964-967` `fill_gaps` 對 `[[]]`／`[]` 都回 `[[]]`（`gspread/utils.py:668-678`）；`get_all_values` 是別名。L1 只把 `[]` 當空表 ⇒ `[[]]` 被當成「表頭是空列」⇒ MISMATCH。舊測試假物件只用 `[]`，所以沒抓到。
- **修正（~~本批~~ #892 已合併，merge `35f67c0c`；2026-10-20 更新，有意識的變更，不是漏刪）**：L1 `src/data/risk_cap/history.py::normalize_sheet_values` 單一真相源，**只**把 `[]`／`[[]]` 收斂成空表；`[[""]]`、第 1 列空白但下面有資料（`[["",…],[…]]`）仍判 MISMATCH（schema 守衛不放寬）。套用於 adapter 讀取邊界、`read_history_values`、`rows_as_records`、`header_state`、`precheck_target`、`verify_written`、`upsert_record`／`_append`、reader smoke 列數。守衛：`tests/test_vn1_empty_sheet_normalization.py`（含以真 gspread `Worksheet`＋假 HTTP client 驅動的契約測試與突變自驗）。
- 客戶指示（總管轉述）：修程式，⛔ 不要用手動輸入表頭的方式掩蓋。
- ~~**下一次 smoke 預期**（修正合併後、**尚未重跑**）：`read_status=EMPTY header_state=ABSENT data_rows=0 compare_status=START_RECORDING`。~~（2026-10-20：已重跑並符合預期，見下一點；有意識的變更，不是漏刪）`PRODUCTION_WRITE_APPROVED` 仍為 `False`；⛔ 無 schedule、⛔ 無 `environment:`。
- **修正後 smoke 結果（2026-10-20）**（#892 合併後客戶於 Streamlit Cloud 實跑、總管轉述；撰寫組未見 log 原文）：`read_status=EMPTY identity_ok=True header_state=ABSENT data_rows=0 latest_record_date=- latest_run_id=- latest_row_sha256=- compare_status=START_RECORDING` ⇒ **PASS**。#892 PR Fast＋Slow success；合併後 main push run 39428438762 success（head `35f67c0c`；總管查證）；獨立 QA 0 MUST-FIX、突變測試轉紅（總管轉述）。
- **旗標清理**：客戶已刪除 Streamlit secrets 的 `risk_cap_history_smoke = true`；保留 `risk_cap_history_sheet_id` 與 `[risk_cap_history_reader]`（客戶回報）。
- **結論**：reader 後端 production readiness **完成**（空表狀態真連線 PASS）。⛔ **不是**「有資料的 reader 已真實驗證」—— 有資料狀態 smoke 待首次 production write 後執行（`docs/BACKLOG.md` `VN1-PG-READBACK`），不是首寫 blocker。

### 8.11 Production Gate 盤點與客戶裁示（DEC-066；2026-10-20）

> **裁示**：`docs/DECISIONS.md` **DEC-066**（客戶提示語原文經總管轉交；要點整理、**非逐字**；BACKLOG DR-2026-10-20-3）。**盤點**：本 session 四組獨立唯讀稽核，總管彙整、撰寫組未重查（`CLAUDE.md` §-2 規則 6）。
> ⛔ 本節不含任何 Sheet ID、secret、私鑰。⛔ 本節登記批未翻旗標、未加 `environment:`／`schedule:`、未改 IAM／WIF。

#### 8.11.1 盤點要點（事實；總管轉述）

- **寫入鏈已具備**：閘門（`PRODUCTION_WRITE_APPROVED`）→ artifact sha256 比對 → hash 鎖定安裝 → WIF（無 key）→ 寫前檢查 → append → 寫後讀回驗證 → fail-stop（8.1～8.4）。
- **正式路徑沒有 delete／rollback**；寫前檢查只要同鍵（record_date, ruleset_version）已有**任何一列（不論 status）**即 exit 4、什麼都不寫。
- `RISK_CAP_HISTORY_WRITE_ENABLED: '1'` 在 workflow 寫入步驟**寫死** ⇒ 核准實質只剩 L0 常數（＋日後的 Environment）；架構是否調整列 LATER 候選（`docs/BACKLOG.md` 5.1.4 `VN1-PG-L-WRITE-ENABLED`）。
- GitHub repo **public**、**個人帳號**；main **無分支保護、無 rulesets**。
- ~~Environment `production-risk-cap` **現存與否 UNKNOWN**（GitHub API 被代理擋）。~~（2026-10-21：客戶已建立，見 8.11.2 末段；有意識的變更，不是漏刪）
- ~~WIF provider **現行 attribute condition 在 repo 內沒有逐字原文**（只有客戶口頭回報＋實跑反推）⇒ 即時無法查證。~~（2026-10-21：修改前逐字原文已由客戶提供 —— `assertion.repository_id=='1241930464' && assertion.repository_owner_id=='285537060' && assertion.ref=='refs/heads/main' && assertion.workflow_ref=='linchen-20200325/my-stock-dashboard/.github/workflows/risk_cap_history_poc.yml@refs/heads/main'`；mapping 5 項、ACTIVE、issuer `https://token.actions.githubusercontent.com`；修改後見 8.7；有意識的變更，不是漏刪）
- GitHub Environment 的 required reviewer 對 `schedule` 觸發**同樣要人工核准** ⇒ 與無人值守排程衝突（8.9）。

#### 8.11.2 Environment 實際能力與設定要求（DEC-066 C Step 1；客戶手動）

| 設定 | 要求 | 理由／盤點 |
|---|---|---|
| 名稱 | `production-risk-cap` | 與 8.6、8.7 一致；workflow 與 WIF condition 都會引用這個字面值 |
| Required reviewers | **客戶本人**（唯一 reviewer） | 單人專案；誠實定位＝「刻意多按一次」，**不是**職責分離、也防不了帳號被盜（8.6） |
| Prevent self-review | **關閉** | 唯一 reviewer 就是觸發者；打開會永遠無法核准 |
| Deployment branches | **Selected branches → `main`** | ⛔ **不選「Protected branches only」**：main 未受保護，選它會讓**所有分支**可部署 |
| Admin bypass（允許管理員略過保護規則） | **取當下 UI 可達成的最嚴格設定**（盤點：預設**開**，須手動取消勾選） | 個人帳號的 owner 即 admin；不關等於核准可被略過 |
| 核准逾時 | 盤點：reviewer **30 天**未核准，run 自動失敗 | GitHub 行為，非設定項；失敗＝什麼都沒寫 |

- ⚠️ 若 GitHub 當下 UI 的選項、名稱或能力與上表不同 ⇒ **不猜、停下回報**（DEC-066 C）。
- ⛔ Environment 必須**先建好**，workflow 才能引用；先引用不存在的 Environment 會**自動建立一個無保護的** environment。
- 8.6 提及的 environment secret（把 `RISK_CAP_HISTORY_SHEET_ID` 搬到 environment 層）**不在** DEC-066 範圍，維持「另行確認」。
- 📌 **2026-10-21 客戶實際設定（DEC-066 C Step 1 完成；客戶 GitHub UI 畫面逐項確認、總管轉述；撰寫組未見畫面原件）**：

  | 設定 | 實際值 | 對照上表要求 |
  |---|---|---|
  | 名稱 | `production-risk-cap` | 一致 |
  | Required reviewers | `linchen-20200325`（客戶本人、唯一） | 一致 |
  | Prevent self-review | OFF | 一致 |
  | Wait timer | OFF | 上表未要求（無等待時間） |
  | Allow administrators to bypass | OFF | 一致（最嚴格） |
  | Deployment branches and tags | Selected branches and tags；allowed branch＝`main`；allowed tags＝0 | 一致 |
  | Environment secrets | 0 | `RISK_CAP_HISTORY_SHEET_ID` 仍在 repo 層（上一點，另行確認） |
  | Environment variables | 0 | — |

  ⇒ 與上表要求一致，未發現「UI 能力與盤點不同」的情形。

#### 8.11.3 正式順序（DEC-066 C；⛔ 不得跳步、不得調換）

| Step | 誰 | 做什麼 | 完成判準 | 對應待辦 |
|---|---|---|---|---|
| 1 | 客戶 | 依 8.11.2 建立 Environment `production-risk-cap` | 客戶回報已建好（含各設定實際值） | `VN1-PG-ENV` —— ✅ 2026-10-21 完成（實際值見 8.11.2 末段） |
| 2 | 開發批（PR） | `production_write` job 加 `environment: production-risk-cap`＋同步測試守衛 | PR CI 綠、合併 | `VN1-PG-WIRE` —— ~~✅ 本 PR~~ PR #894（合併後完成；依本表完成判準「PR CI 綠、合併」）（2026-10-21 更新，有意識的變更，不是漏刪）（只有 `production_write`） |
| 3 | 客戶（＋我們比對） | 客戶提供 WIF provider **完整 describe 原文**（唯讀；⚠️ 5.3 C5 指令以 `--format` 只印 `attributeCondition`，**不足**，須去掉 `--format` 取完整輸出；pool／provider 名稱以 8.2／8.7 所用實際名稱為準）→ 確認原始 condition → 才修改 provider，新增 `environment == production-risk-cap`、`event_name == workflow_dispatch` | 新 condition 生效；實測無 environment 的 job 被 STS 拒（8.7） | `VN1-PG-WIF` —— ~~⏳ 未做（下一 Gate）~~ ✅ 2026-10-21 完成（反向驗證 run 39589906182；見 8.7；有意識的變更，不是漏刪） |
| 4 | 開發批＋客戶 | （Step 4 為撰寫組依 DEC-066 A／B 整理，非客戶另立的步驟）首次寫入：開旗標 PR → 當天 dry-run → production-write → readback → 立即改回 `False` 的 PR | 見 8.11.4 | `VN1-PG-FIRST` —— ⏳ 未做（**下一 Gate**，尚未開始） |

#### 8.11.4 首次寫入 Runbook（DEC-066 A／B／E；**未執行**）

**寫入前核對（任一不符 ⇒ 當天不寫）**
1. Step 1～3 已完成；開旗標 PR（`PRODUCTION_WRITE_APPROVED` → `True`＋政策測試同步）**已合併到 main**、main CI 綠。
2. **當天**先在 `main` 跑 `mode=dry-run`：紀錄 `status=VALID`，且 `exposure_limit_pct` 等必要輸出正常。⛔ 非 VALID ⇒ 當天不觸發 production-write（DEC-066 B）。
3. **避開台北時間 23:30–00:30**：寫前檢查要求 `record_date`＝寫入當下的台北日期；compute 與寫入跨過午夜會在寫前檢查被擋（exit 4）。Environment 核准若拖過台北午夜，同樣會在寫前檢查 exit 4 ⇒ **觸發後須即時核准**。
4. Actions 頁確認**沒有其他** `risk_cap_history_poc` run 在執行或等待中（concurrency 只保留一個 pending）。📌 2026-10-21 補：掛上 Environment 後，**等待核准中的 run 會佔住 workflow 層 concurrency group**（最長 30 天才逾時失敗），後續觸發會卡在 pending ⇒ 不打算核准的 run **立刻 Reject／Cancel**。

**觸發**
- Actions → `risk_cap_history_poc` → Run workflow → branch **`main`** → `mode`＝**`production-write`** → 停在 Environment 等待核准 → 客戶本人核准。

**預期 log（全部符合才算成功）**
1. 閘門：`production 寫入核准旗標為 True`。
2. artifact：compute job 印 `record artifact sha256=<x>`；寫入 job `sha256sum --check --strict` 印 `OK`。
3. 寫前檢查：`precheck:` 那行 JSON 為 `ok: true`、`failures: []`、`header_state: ABSENT`、`data_rows: 0`。
4. 寫入：`寫入結果：APPENDED`。
5. 寫後驗證：`verify:` 那行 JSON 為 `ok: true`、`matches: 1`、`mismatched_columns: []`。
6. **三處列指紋一致**：`precheck.record_sha256`＝`verify.record_sha256`＝`verify.readback_sha256`。
7. 最後一行：`寫入並讀回驗證通過`；job exit 0。

**寫入後核對（人工）**
1. Sheet `risk_cap_daily` 恰好 **2 列 × 20 欄**（表頭＋1 筆；欄序＝`HISTORY_COLUMNS`）。
2. 欄值：`record_date`＝當天台北日期、`status` 與 `exposure_limit_pct` 與本次 compute job 紀錄一致（寫後驗證已逐欄比對）；與當天 dry-run 不同時**照實記錄、不改**（兩次 run 間輸入可能更新）。
3. `run_id`＝本次 production-write run id；`git_sha`＝本次 main head。
4. 表內**無** `PERMISSION_TEST` 殘留列。
5. **存證據**：run id／URL、兩個 job 的完整 log、record artifact（**retention 7 天**，過期即消失 ⇒ 當天下載）、Sheet 截圖（分享時勿露出網址列 Sheet ID）。
6. **立即**以獨立 PR 把 `PRODUCTION_WRITE_APPROVED` 改回 `False`（DEC-066 A；不論成功或失敗中斷，這都是下一個動作）。⚠️ 第 1～5 點的核對與存證可與本點**並行**，但**下一個改 code 的動作一定是改回 `False`**（必要時把本點提到最前）。
7. 之後：網站 reader 有資料狀態 smoke（`VN1-PG-READBACK`；預期 `read_status=OK header_state=MATCH data_rows=1`、`latest_row_sha256`＝`verify.readback_sha256`）。

**失敗處置（DEC-066 E：FAIL-STOP）**

| 結束碼／情況 | 意思 | 處置 |
|---|---|---|
| exit 4 | 寫前檢查阻擋（什麼都沒寫） | 維持原狀、**當天不再重跑**；保留 log；改回 `False` 的 PR 照開 |
| exit 1／3／5 | I/O 失敗／同日衝突／寫後驗證不過（**可能已寫入**） | **改回 `False` 的獨立 PR 照開（DEC-066 A）**；其餘停下：保留完整 logs／evidence、人工檢查 Sheet、**停下等客戶裁示**；⛔ 自動刪列／rollback／覆寫／盲目 retry |
| exit 2、Environment 被拒、逾時、取消；以及腳本之前的 step 失敗（artifact sha256 比對、hash 鎖定安裝、WIF auth） | 閘門未過、紀錄檔不合格、或寫入腳本根本沒跑到等（DEC-066 未個別點名） | **改回 `False` 的獨立 PR 照開（DEC-066 A）**；其餘依撰寫組讀法落在 E 總則 —— 保留證據、停下回報等裁示、不重試（**讀法，不是新裁示**） |
| 留下非 VALID 列（dry-run VALID 但寫入時不可抗力） | 真實系統歷史 | **保留、不刪、不覆寫、當天不重寫**（DEC-066 B） |

- 需刪無效列：**只能由客戶在 Google Sheets UI 人工執行**，刪前保存證據／截圖；production 程式**永久不得**因此新增自動刪列功能。

#### 8.11.5 Daily Schedule：**NOT APPROVED**（DEC-066 F）

- 首次人工寫入與 daily schedule 是**兩個獨立 Gate**；「Production Write 授權 ≠ Daily Schedule 授權」。
- ⛔ 禁止新增 `schedule:`；排程設計、Environment 分流、unattended write 全部延後到首次人工寫入驗證完成後**另案裁示**（`docs/BACKLOG.md` 5.1.4 `VN1-PG-SCHED`）。
