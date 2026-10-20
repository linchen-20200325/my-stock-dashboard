# VN1-STORE 憑證設定規格（System Risk Cap 系統歷史 Sheet：寫入端／讀取端身分）

> **狀態**：設定規格（docs-only）。**本檔不是施工授權、也不是 production 寫入核准。**
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

📌 R1、R2 的錯誤碼不論是 403 還是 404 都算通過；**任何 2xx 都算失敗**，須立刻停下、移除該分享並回報。

### 5.3 設定檢查（Cloud Shell，唯讀）

| ID | 指令 | 預期 |
|---|---|---|
| C1 | `gcloud iam service-accounts keys list --iam-account="$WRITER_SA" --managed-by=user` | **空**（writer 沒有任何使用者管理的 key） |
| C2 | `gcloud iam service-accounts keys list --iam-account="$READER_SA" --managed-by=user` | **恰好 1 把** |
| C3 | `gcloud projects get-iam-policy "$PROJECT_ID" --flatten="bindings[].members" --filter="bindings.members:risk-cap-" --format="table(bindings.role,bindings.members)"` | **空**（兩支 SA 無專案層 role） |
| C4 | `gcloud iam service-accounts get-iam-policy "$WRITER_SA"`、`gcloud iam service-accounts get-iam-policy "$READER_SA"` | writer：只有步驟 4 那一條 `roles/iam.workloadIdentityUser`（principalSet＝本 repo ID）；reader：**無任何綁定**；兩者都不出現 fund-nav 相關成員 |
| C5 | `gcloud iam workload-identity-pools providers describe github-provider --location=global --workload-identity-pool=github-pool --format="value(attributeCondition)"` | 與步驟 3 的四條件一致 |
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

## 6. 日後仍需改 code／workflow 的事項（~~**未來實作批次，本批未做**~~ ~~**第 1～3 項 #886 已完成、第 4 項半完成，其餘未做**；2026-10-19 更新，有意識的變更，不是漏刪~~ **第 1～4 項已完成（第 4 項由 Production Wiring 批補完，分支未合併）、第 6 項結構已接線，其餘未做**；2026-10-20 更新，有意識的變更，不是漏刪）

本批只寫規格。下列項目要等客戶指派實作批次、且 **production 寫入仍須另行核准**（DEC-063、DEC-009）：

1. ✅ #886 已完成（job `wif_auth_only` job 層級 `id-token: write`；其他 job 不受影響）。寫入 workflow 宣告 `permissions: id-token: write`（目前 `risk_cap_history_poc.yml` 只有 `contents: read`）。
2. ✅ #886 已完成（`google-github-actions/auth` v3.0.0 `7c6bc770`；checkout v4.3.1 `34e11487`、setup-python v5.6.0 `a26af69b`，皆完整 SHA）。使用 `google-github-actions/auth` 以 WIF 取得 writer 憑證，**以完整 commit SHA 釘版**（不用 tag）；`workload_identity_provider` 與 `service_account` 直接寫在 workflow（非 secret）。
3. ✅ #886 已完成。`.gitignore` 加入 `gha-creds-*.json`（該 action 預設會在 workspace 產生暫存憑證檔；搭配 checkout 在 auth 之前、不 commit workspace）。
4. ◐ #886 半完成：`WRITER_SA_ENV_VAR` 已退役；寫入前置檢查改為檢查 WIF 憑證、reader 端命名與 Streamlit 接線**未做**。
   📌 2026-10-20 更新（Production Wiring 批；有意識的變更，不是漏刪）：寫入前置檢查已改為檢查 WIF `external_account` 憑證檔（`load_writer_credentials_or_refuse` 第 4 步；第 1 步仍是 `PRODUCTION_WRITE_APPROVED=False` ⇒ 一律拒絕）；reader 端命名已定案（步驟 8）、L3 讀取服務已實作。**仍未做**：畫面（Streamlit UI）接線、production 寫入核准。程式端政策常數改名：退役 `RISK_CAP_HISTORY_WRITER_SA_JSON`（`shared/risk_cap_history_policy.py:177` `WRITER_SA_ENV_VAR`），寫入前置檢查（`src/data/macro/risk_cap_history.py`）改為檢查 WIF 提供的憑證；讀取端名稱與 Streamlit secrets 表格名（步驟 8 提案）定案並同步；相關測試（`tests/test_vn1_store_poc.py`）同步更新。
5. 若正式 workflow 換檔名 → 依步驟 3 更新 attribute-condition。
6. 寫入端 `concurrency` 序列化（單一寫入者，見 `VN1_STORE_RESEARCH.md` 8.4 第 2 點）。
7. ✅ 2026-10-20 已完成（P1／P2／R1～R5 全部 PASS，見 5.4）。第 5 節驗證計畫執行並記錄結果。（~~⚠️ 2026-10-19：P1／P2／R1～R5 **仍未執行**；WIF auth-only PASS 不算第 5 節任何一項。~~ 2026-10-20 已不成立，有意識的變更，不是漏刪）

📌 2026-10-19 正式寫入前另需（已記錄、未做）：pip 安裝 hash-pin；GitHub environment（required reviewers）＋WIF condition 加 environment claim；WIF condition 加 `event_name`。另：checkout／setup-python 釘版觸發 Node 20 deprecation 警告（被強制以 Node 24 執行），屬日後 pin bump、不阻擋。
8. `PRODUCTION_WRITE_APPROVED`（`shared/risk_cap_history_policy.py`）改為 `True` **只能在客戶另一次裁示後**（⛔ 不得自行改）。

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
11. **Production Wiring 批（2026-10-20）**：Production Wiring 批（分支 `claude/jolly-mccarthy-sonbl8`，commits `67701562`、`ef905cf0`（回修第 1 輪）；兩組獨立 QA 對 `67701562` 均 0 MUST-FIX（總管轉述）；**未開 PR、未合併**）。reader：L3 `src/services/risk_cap_history_reader_service.read_history` 已接線（只讀 Streamlit secrets `[risk_cap_history_reader]`＋`risk_cap_history_sheet_id`；只快取成功讀取；VALID 列缺上限值 ⇒ `CONTENT_SUSPECT`、不比較；**沒有任何 UI 呼叫端**）；writer：workflow `risk_cap_history_poc.yml` 新增 `production-write` mode（compute job 無 id-token → main-only 寫入 job），寫入 job 在任何 auth 之前先檢查核准旗標 ⇒ **目前恆紅、什麼都不寫**；`PRODUCTION_WRITE_APPROVED` 仍為 `False`；無 schedule；未變更 IAM／WIF／Sheet 分享。
    - **送交 production 每日寫入最終核准前仍需**：(1) write job 依賴 hash-pin＋精簡（目前裝完整 `requirements.txt`、經 `src.data.macro` barrel eager 載入；QA-A S1）；(2) GitHub Environment＋required reviewers＋WIF attribute condition 加 environment claim 與 `event_name`（目前核准只剩 L0 常數；QA-A S3）；(3) 首次實跑驗證計畫（核准後路徑 —— WIF 憑證 → gspread → `upsert_record` —— 未端到端實跑；QA-A S2）；(4) WIF 憑證檔 `audience` 未核對（QA-A N1）；(5) 只重跑寫入 job 會沿用舊 artifact（QA-A N2）；(6) 畫面顯示歷史須先過線框（DEC-003 ①）；(7) 每日 schedule 本身須另行核准（目前只有 workflow_dispatch）；(8) Streamlit secrets 實際內容（`[risk_cap_history_reader]`、`risk_cap_history_sheet_id`）為客戶回報、未查證。
    - **本批限制**：Google／Streamlit 實際連線**未測**（全以假物件）；本機 Python 3.13、CI 3.11；QA-B NIT-2／NIT-4 依總管裁定不處理（內容見該輪 QA 回報，本檔未轉錄）。
    - ⚠️ 上一則（第 10 點）「Streamlit reader 接線未實作；第 6 節第 4 項仍半完成」「下一 Decision Gate（未指派）」自本批起不再成立（有意識的變更，不是漏刪）；production 每日寫入核准**仍未送題、未核准**。
