# New UI2 切換與回退操作手冊（Runbook；docs-only）— 2026-11-22

## 檔頭

- **目的**：把 A 線「New UI2 切換與回退操作手冊」（v0＋§4 補丁）落地為 repo 正式文件，供日後 `NUI2-CUTOVER`／`NUI2-ROLLBACK` 批使用；並補註撰稿後已過時的基線，以及 P1 查一檔旗標的停用與回退。
- **適用範圍**：Streamlit 入口 `app.py`（Legacy New UI nav4 預設／Old UI `?legacy=1`）與 `app_ui2.py`（New UI2 Preview）之間的切換前核對、停止條件、回退路徑、恢復後確認與 #1199 回存格式。
- **撰寫基準**：`origin/main` = `a035abfcdaeb3c4bc52cc4837739c4719c7c95af`（2026-11-22；本檔所有「當前 main」事實以此 SHA 實查，切換當下須重取）。
- **撰寫者／狀態**：B 線單一 writer；**單組撰寫，未經非作者 QA（`CLAUDE.md` §-2 規則 6）**。**不是 QA PASS，不是「可切換」**。
- **來源清單**（#1199 comment id，原文以 `gh api repos/linchen-20200325/my-stock-dashboard/issues/comments/<id> --jq .body` 取得）：
  - `7062619091`：A 線手冊 v0（§0 現況、§1 切換前核對、§2 切換／停止條件、§3 回退、§4 恢復確認、§5 缺口）。
  - `7063221555`：v0 §4 補丁（A. 修正 v0 §4 第二列；B. 逐路徑確認表；C. 現況可填 vs 不可填）。
  - `7063479541`：Work 對補丁之靜態文件差額 QA（PASS）。
  - `7063936439`：GPT 總管裁定——原則核准文件落地，B 為唯一 docs writer，須補註過時基線、Cloud 映射 NOT VERIFIED、R1～R4 NOT RUN，**不得視為切換授權**。
  - `7071155670`：GPT 總管 Batch NEXT 派工（B 段：#1257 結案後另開獨立 docs-only Draft PR；不得自行 merge）。
  - `7064531081`：B 線 #1257（P1 查一檔輸入）QA／CI 回存（供第 8 節引用）。
- 規則沿用 `docs/vnext/NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md`（下稱 **MC**）§1／§2；`docs/vnext/NEWUI2_CUTOVER_GAP_MATRIX_2026-11-10.md`（下稱 **GM**）只作基線。

## 全文狀態聲明（必讀）

| 項目 | 狀態 |
|---|---|
| Cloud 部署 SHA／Main file／entrypoint 映射 | **NOT VERIFIED**（repo 內無 Cloud 設定頁證據，僅客戶轉述） |
| R1～R4 實機回退演練 | **NOT RUN** |
| slow lane（`pr-check.yml` `slow-tests`） | `continue-on-error: true`，**紅燈不擋 merge，須人工核對**，不得以「CI 通過」代替 |
| 本文件落地 | **≠ 切換授權**；不改 runtime／Cloud／Secrets／OAuth、不刪碼 |
| 保留之 Gate | `NUI2-CUTOVER`、C1～C7、G11（未實作）、`?ui=1`（未實作）、P2（A2 來源權利／A3 I1144-DG-SCOPE 接線／A4 收盤口徑）、#1237（NAS，Draft／HOLD）、#1107、真持股／登入／Sheet、OneBrain 正式接線 |
| 本檔性質 | 單組撰寫、待非作者 QA；不得引用為「已驗」 |

---

## 0. 現況（含 2026-11-22 重驗）

> **舊基線處置**：v0 撰寫基準 `bf2a0a52`；補丁讀碼基準 `cca7a290`；v0 §0-7 寫「#1255 仍 Draft」。以上皆為「**撰稿時基線，已過時，現況見本節**」。其歷史意義保留於下表「v0 原文」欄，不刪除。

### 0.A 基線更正（逐項於 `origin/main` `a035abfc` 實查）

| 項 | v0／補丁原文（撰稿時基線，已過時） | 現況（2026-11-22 實查，SHA `a035abfc`） | 核實指令 |
|---|---|---|---|
| #1255 M-A2 Aggregator | 「Draft」（v0 §0-7、§5-3） | **已合併** `8b39f385`（2026-11-21）：L0 `shared/system_action_contract.py`＋L3 `src/services/system_action_aggregator.py`＋A-T1～A-T10 測試；**未接任何 consumer**（見 `docs/DECISIONS.md` DEC-222）。M-A3～M-A6、A-T11 未開始 | `git log -1 --format='%h %ad %s' --date=short 8b39f385`；`git show --stat --format= 8b39f385` |
| #1253 行情離線契約 | 「其後前進」 | 已合併 `7917a818`（2026-11-21；單檔公開行情畫面狀態離線契約，無 production caller） | `git log -1 7917a818` |
| #1254 OneBrain 持股輸入契約 | 同上 | 已合併 `cca7a290`（2026-11-21；離線契約＋合成驗收案例） | `git log -1 cca7a290` |
| #1257 P1 查一檔輸入 | v0 無此項 | 已合併 `a035abfc`（2026-11-22；旗標預設 OFF；DEC-223）＝**當前 main tip** | `git log -1 a035abfc` |
| 撰稿基準 `bf2a0a52`／`cca7a290` | 當時 main tip | 皆為歷史基線；`bf2a0a52` 在 `a035abfc` 之前（`git log --oneline -8` 可見順序 `bf2a0a52`→…→`cca7a290`→`7917a818`→`8b39f385`→`a035abfc`） | `git log --oneline -8` |

⚠️ 以下兩處 repo 內既有文件**仍寫舊狀態**，本檔不修改它們（任務限單檔），僅提醒讀者**以本節為準、以 git 實查為準**：
- `docs/BACKLOG.md` `NUI2-AGGREGATOR-IMPL` 列仍寫「M-A2 Draft PR，未接 consumer」；`B-UI2-LOOKUP-P1-INPUT-1` 列仍寫「PR OPEN／NOT VERIFIED」。
- GM §1／§3 仍寫「Aggregator 未實作（NOT FOUND）」（GM 基準 `f4d86b4f`，2026-11-10，早於 #1255）。**現況：Aggregator 的 L0／L3 已合併但未接 consumer**；UI2 動作欄仍為 capability marker `⬜ 尚未提供`，故 C2／C6／C7 的前置（M-A3、M-A4）**仍未完成**，結論不變。

### 0.B v0 §0-1～0-3 grep 事實逐項重驗（`a035abfc`，2026-11-22）

| # | 現況 | 標記與重驗結果 | 核實指令 → 結果 |
|---|---|---|---|
| 0-1 | `app.py` **0 個 UI2 路由**（無 `ui2`、無 `?ui=`） | **FACT（重驗仍成立）** | `git grep -c -i ui2 -- app.py` → 0 命中（rc=1）；`git grep -n 'ui=1\|"ui"' -- app.py` → 0 命中。`app.py` 唯一的 `st.query_params.get(...)` 路由參數為 `legacy`（`app.py:97`） |
| 0-2 | `app.py` 預設＝Legacy New UI（nav4）；`?legacy=1`＝Old UI | **FACT（重驗仍成立）** | `git grep -n _nav4_resolve_legacy -- app.py` → `app.py:94` 定義、`app.py:110` `_NAV4_LEGACY = _nav4_resolve_legacy()`；只認 `'1'`／`'0'`，旗標存 `session_state['_nav4_legacy']` |
| 0-3 | UI2 只從獨立 `app_ui2.py` 進入；`src/ui2`、`app_ui2.py` 無 `legacy` 字樣 | **FACT（重驗；須註明大小寫）**：區分大小寫 grep 為空 | `git grep -n 'legacy' -- app_ui2.py src/ui2` → 空（rc=1）。⚠️ **不區分大小寫則有命中**：`app_ui2.py:11`、`src/ui2/__init__.py:3,7` 含 `Legacy UI`／`Legacy New UI` 字樣，皆為「⛔ 不得 import Legacy UI」的守衛註解，**不是路由**；v0 的「無 `legacy` 字樣」應讀作「無小寫 `legacy` 路由字樣」 |
| 0-4 | 已知一個 Cloud App Main file＝`app_ui2.py`、Branch＝main；更新需手動 Reboot | **客戶陳述／轉述日誌，非設定頁證據**；本次未重驗（repo 外）。見 `docs/vnext/UI2_NO_DATA_ROOT_CAUSE_NAS_AND_DPE6_CLOUD_EVIDENCE_2026-11-13.md` §1（客戶陳述：`main`＋`app_ui2.py`＋Streamlit 1.59.2＋Python 3.14.10；無日期、無 commit、無 owner） | 無法由 repo 核實＝NOT VERIFIED |
| 0-5 | 是否仍有 Main file＝`app.py` 的正式 App、owner、部署 commit | **NOT VERIFIED** | 同上 |
| 0-6 | 切換前不存在「從 UI2 退回」的程式路徑（UI2 尚非任何入口預設） | INFERENCE（由 0-1～0-3；重驗後前提仍成立） | — |
| 0-7 | ~~Aggregator 未合併（#1255 Draft）；UI2 動作欄為 `⬜ 尚未提供`~~ **更正**：Aggregator L0／L3 **已合併**（#1255，`8b39f385`）但**未接任何 consumer**；UI2 動作欄仍為 `⬜ 尚未提供`（`CapabilityState.NOT_PROVIDED`） | FACT | `git grep -n NOT_PROVIDED -- src/ui2` 有命中（如 `src/ui2/components/html.py:61`）；consumer 接線屬 M-A3／M-A4，未開始 |
| 0-8 | `NUI2-CUTOVER`、`NUI2-ROLLBACK` open；C1～C7 依 GM 無一已滿足 | FACT（重驗；GM 基準為 2026-11-10，**未更新**） | `git grep -n -E 'NUI2-CUTOVER\|NUI2-ROLLBACK' -- docs/BACKLOG.md`：`docs/BACKLOG.md:1181` `NUI2-CUTOVER` **open**；`:1182` `NUI2-ROLLBACK` **open**（前置＝`NUI2-CUTOVER`；內容「`?ui=1`、`?legacy=1` 保留；回滾一行；⛔ 先刪程式」）。GM §1.1 結論「C2、C5、C6、C7 未滿足；C1、C3、C4 部分；無任何一條已滿足」未被其後任何文件推翻（本檔未重評 C1～C7） |

### 0.C 其他重驗項

| 項 | 結果 | 核實指令 |
|---|---|---|
| slow lane `continue-on-error: true` | **FACT（仍成立）**：`.github/workflows/pr-check.yml:53`（job `slow-tests`，名稱「Slow tests (AppTest, informational)」，註解「非阻擋(continue-on-error),作為 informational signal」；DEC-078） | `grep -n 'continue-on-error' .github/workflows/pr-check.yml` → 46、53、141（141 為 playwright 註解字樣，非設定） |
| `tests/test_nav1_app_routing.py` 引用的測試名 | **全部存在**：`TestLegacyMode::test_b3_query_param_enters_the_old_ui_and_never_touches_nav4_modules`、`test_b4_flag_survives_reruns_without_the_query_param`、`test_b4_legacy_zero_clears_the_flag`、`test_legacy_loads_fully_even_if_the_nav4_modules_cannot_be_imported`（`class TestLegacyMode` 在 `:410`，`@pytest.mark.slow`）；`TestLegacyPathRunsNoNav4Code::test_resolve_legacy_does_not_import_anything_from_nav4`（`:543`） | `git grep -c "def <name>" -- tests/test_nav1_app_routing.py` 五個名稱皆為 1 |
| G11 路由毒化測試 | **未實作**：`git grep -n G11 -- tests` 空 | 同左 |
| production 預設 VM 0 個 capability marker 的 runtime 斷言 | **未實作**：僅有 `tests/test_ui2_guards.py:1151` `CAPABILITY_MARKER_ALLOWLIST`（靜態白名單）；BACKLOG `NUI2-CAPABILITY-MARKER-CUTOVER-ZERO` 規定 cutover 前清零 | `git grep -n CAPABILITY_MARKER_ALLOWLIST -- tests` |
| UI2 畫面版本字串 | **0 命中**：`git grep -n -E 'GIT_SHA\|APP_VERSION\|build_id' -- src/ui2 shared/ui2_contract app_ui2.py app.py` 空 → UI2 畫面無法自證部署 commit | 同左 |
| MC／GM 引用處 | MC §1.1 C7 原文（「C1～C6 皆有 PR／報告證據＋獨立 QA；一次 PR 切換 `app.py` 預設；切換前 G11 路由毒化測試綠；前置必含 `NUI2-AGGREGATOR-IMPL`＋M-A3＋M-A4 完成（否則持股頁動作能力消失）（#997 稽核 M2）」）、MC §2（`?ui=1`、G11、OAuth 降級揭露）、MC §6／§7（`app_ui2.py` 登記 L6；capability marker 為 Preview-only、cutover 前須 0 個）**皆仍屬實**；GM 僅其「Aggregator 未實作」一語因 #1255 合併而過時（見 0.A） | `sed -n 34,46p`／`grep -n -E 'G11\|\?ui=\|NUI2-AGGREGATOR' docs/vnext/NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md` |

---

## 1. 切換前核對（缺任一＝停止）

| 類 | 核對項 | 提供者 | 現況（2026-11-22） |
|---|---|---|---|
| 版本 | GitHub main SHA／切換 PR merge SHA | AI | main 可取（撰寫時 `a035abfc`，隨時前進）；切換 PR 不存在 |
| 入口 | 每個 Cloud App 的網址、Repository（含 owner）、Branch、Main file、部署觸發 | 客戶／Cloud 管理員（貼設定頁，**不貼 Secrets**） | **NOT VERIFIED** |
| 部署 | 最近成功部署 commit 與時間 | 客戶／Cloud 管理員 | **NOT VERIFIED**；UI2 畫面無版本字串（見 0.C） |
| 證據 | C1～C6 各自 PR／報告＋獨立 QA | AI 彙整、獨立 QA | 位置：MC §1.1、GM §1.1、`docs/vnext/NEWUI2_AUDIT_ACCEPTANCE_CHECKLIST_2026-11-02.md` §3／§4／§9／§10／§11（v0 稱 §11 全 `[ ]`；本次**未重驗**該檔勾選狀態） |
| 守衛 | G11 路由毒化（毒化 UI2 → `?ui=1`／`?legacy=1` 仍完整載入） | AI（cutover PR） | **未實作** |
| 守衛 | production 預設 VM 0 個 capability marker 的 runtime 斷言 | AI（cutover PR） | **未實作** |
| 回退 | `?ui=1` | — | **未實作** |
| 回退 | R1～R4 演練紀錄 | 客戶＋Cloud 管理員＋AI | **NOT RUN** |

## 2. 切換條件與停止條件

**切換條件（MC §1.1 C7 原文）**：「C1～C6 皆有 PR／報告證據＋獨立 QA；一次 PR 切換 `app.py` 預設；切換前 G11 路由毒化測試綠；**前置必含 `NUI2-AGGREGATOR-IMPL`＋M-A3＋M-A4 完成**（否則持股頁動作能力消失）（#997 稽核 M2）」。另 MC §7：production 預設 VM 須 0 個 `⬜ 尚未提供`；MC §1：不得先刪程式，切換後另進 Removal Gate。（#1255 僅合併 M-A2，**M-A3、M-A4 未完成**，C7 前置仍不滿足。）

**停止條件（任一成立即不切；已切則依第 3 節回退）**：
1. C1～C7 或 MC §1.2 任一前置缺證據或無獨立 QA（現況：全缺）。
2. **部署 SHA 不可證**（0-4／0-5 任一 NOT VERIFIED；現況成立）。
3. **回退未演練**（R1～R4 無紀錄；現況成立）。
4. G11 不存在或非綠；或 cutover PR 的 slow lane 未綠——⚠️ slow lane 為 `continue-on-error: true`（informational），紅燈**不擋 merge**，須人工核對（逐 step 看 Run AppTest 終態），不得以「CI 通過」代替。**核對方式**：slow lane 為 informational，須在該 head 的 PR Check run 中逐 step 檢視 `Run AppTest (slow lane)` 的 conclusion（例如 `gh api repos/<owner>/<repo>/actions/runs/<run_id>/jobs`），不得以整體 run 成功代替。
5. 切換方式不是「一次 PR 切 `app.py` 預設」（例如把正式 App 的 Main file 改指 `app_ui2.py`）→ 停，另送客戶 Gate（INFERENCE：該方式繞過 `?ui=1`／`?legacy=1`）。**這是保守規則（INFERENCE，非 MC 原文）**。

## 3. 回退：誰執行、怎麼退

**角色**：客戶＝決定是否切換／回退／進 Removal Gate，未另指派時也執行 Cloud 操作；Cloud 管理員（身分 NOT VERIFIED，預設＝客戶）＝Reboot／重新部署／改 Main file／確認部署 commit；**AI＝只準備 revert PR、彙整證據、回存，不操作 Cloud、不改 Secrets／OAuth、不刪碼**（PR 走 PR＋非作者 QA＋同 head CI）。

| 級 | 路徑 | 狀態 | 依據與限制 |
|---|---|---|---|
| R1 | Old UI：`?legacy=1`（`?legacy=0` 清除） | **已實作＋已測（測試層）／未實機** | `app.py::_nav4_resolve_legacy` 刻意 0 import、旗標存 `session_state['_nav4_legacy']`、耐 OAuth callback 清 query。測試見 0.C（slow 為主；fast 為 `TestLegacyPathRunsNoNav4Code`）。毒化對象是 nav4、**不是 UI2**；⚠️ 只在 Main file＝`app.py` 的 App 有效，`app_ui2.py` App 加 `?legacy=1` 無作用 |
| R2 | Legacy New UI：`?ui=1` | **未實作** | MC §2 暫定；切換前 Legacy New UI 即 `app.py` 預設 |
| R3 | G11 毒化守衛 | **未實作** | MC §2、§6；cutover PR 必備 |
| R4-a | revert 切換 PR（`app.py` 預設一行切回） | **未實作**（尚無切換 PR） | AI 開 revert PR → fast lane 綠＋人工核 slow lane＋非作者 QA → merge → Cloud 管理員 Reboot（需手動屬客戶陳述，未實測）→ 第 4 節確認。INFERENCE：未 Reboot 則畫面不回退；UI2 不寫投資狀態、session key 限 `ui2_` → 預期無殘留，**未實測** |
| R4-b | Cloud 端指回舊 Main file／舊 App 網址／Reboot 至舊 commit | **未實作**（repo 外，無程序紀錄） | 前提是知道舊 App 設定與舊 commit（現況 NOT VERIFIED）；最快但**不留 repo 證據**，事後須補第 4 節 |

**OAuth 揭露**（MC §2，未實機）：切換後登入回呼落地即預設入口，帶 `?ui=1`／`?legacy=1` 者登入後可能回到 UI2；R1 的 session 旗標設計可緩解，Cloud 實機 NOT VERIFIED。

## 4. 原入口恢復後的確認與證據

### 4.1 通用確認項

| 確認項 | 應留證據 | 由誰 |
|---|---|---|
| 正式網址（不加參數）呈現預期 UI；`?legacy=1` 呈現 Old UI | 兩張截圖（遮蔽 NAS 網址／主機名） | 客戶 |
| 部署 commit（**依路徑不同，見 4.2**） | Manage app 的 commit 前 7 碼＋時間；AI 附 `git rev-parse origin/main` | Cloud 管理員＋AI |
| 資料日與回退前一致或更新 | 截圖或文字 | 客戶 |
| 持股頁動作欄、OAuth 登入態、側欄連線狀態正常 | 截圖；異常逐項列出 | 客戶 |
| UI2 未寫入 Sheet／投資狀態 | 讀碼依據 MC §2；實機 NOT VERIFIED 須明寫 | AI |

### 4.2 補丁 A：修正 v0 §4 第二列

v0 §4 第二列原寫「Cloud 部署 commit＝revert 後 main SHA」——**僅適用 R4-a**。更正為：
- **R1**：核「**原 `app.py` 部署 commit**」（R1 不產生新 commit）。
- **R4-a**：核 **revert PR merge 後的 `main` SHA**。
- **R4-b**：核「**實際恢復之 App／entrypoint／目標 commit**」（不假設等於 `main` SHA）。

### 4.3 補丁 B：逐路徑確認表

| 項 | R1 `?legacy=1` | R4-a revert 切換 PR | R4-b Cloud 端指回舊 Main file／舊 App |
|---|---|---|---|
| 適用前提 | Main file＝`app.py` 的 App（FACT：`app.py::_nav4_resolve_legacy`）；在 `app_ui2.py` App 無作用（FACT：`app_ui2.py`、`src/ui2` 無小寫 `legacy` 路由）。該 App 是否存在＝NOT VERIFIED | 已有「切換 `app.py` 預設」的 merge PR（MC §1.1 C7、§2）。**現況不存在**，無可 revert 對象 | 知道舊 App／舊 Main file／舊 Branch 設定（UI2 證據文件 §13 第 3 項）；現況 NOT VERIFIED |
| 操作者與參數 | 使用者／客戶於網址加 `?legacy=1`；清除用 `?legacy=0`（只認 `'1'`／`'0'`，空值亂值維持現旗標）。無 Cloud 操作 | AI 開 `git revert <切換 merge SHA>` PR（`PROCESS.md` §4：非作者 QA＋同 head CI＋branch protection）；merge 後由 Cloud 管理員 Reboot（客戶陳述需手動，未實測） | Cloud 管理員於 Cloud 設定改 Main file／Branch，或改用舊 App 網址；僅用既有文件名詞（Repository／Branch／Main file path／Reboot），不新增介面細節 |
| 預期入口 | Old UI：側欄 D2 雙層 radio（**INFERENCE**）＋舊 7 頁籤 `tab_market, tab_stocks, tab_etf_main, tab_tools, tab_warroom, tab_mgmt, tab_ai`；側欄初始 collapsed（FACT：`app.py` `_NAV4_LEGACY` 分支、`initial_sidebar_state`）。`?legacy=0` 回預設 Legacy New UI 四頁 nav4 | revert 後 `app.py` 預設回切換前行為＝Legacy New UI 四頁 nav4（INFERENCE：由現行預設；切換 PR 內容未知）；`?legacy=1` 仍為 Old UI（MC §2 規定保留） | 取決於恢復到哪個 Main file：`app.py`→同左兩欄；`app_ui2.py`→New UI2 Preview（Real-data、唯讀、無 `?legacy`）。實際指向 NOT VERIFIED |
| 目標 SHA 定義 | **無 SHA 變更**；核「原 `app.py` 部署 commit」＝切換前 `main` SHA 或現部署 commit，來源＝Cloud 管理員（Manage app 畫面）；切換未發生時＝現部署 commit | revert PR 的 merge SHA＝回退後 `main` SHA（`git rev-parse origin/main`）；另記被 revert 的切換 merge SHA | 舊 App 的 Main file／Branch 與其最近成功部署 commit（含時間）；`main` SHA 不必然等於部署 commit。現況 NOT VERIFIED |
| 確認證據 | 截圖：無參數入口、`?legacy=1` 入口（遮蔽 NAS 網址）；Manage app 部署 commit 前 7 碼＋時間；資料日 | 截圖同左；revert PR 號與 merge SHA；Manage app 部署 commit 前 7 碼須＝merge SHA 前 7 碼（看不到則 NOT VERIFIED）；資料日 | Cloud 設定頁（遮蔽 Secrets）顯示 Repository／Branch／Main file；部署 commit 前 7 碼＋時間；入口截圖；資料日；事後 #1199 回存 |
| 狀態標記 | 已實作＋已測（測試層）／未實機（測試名見 0.C）；slow lane informational；毒化對象是 nav4、非 UI2。演練＝**NOT RUN** | 未實作（無切換 PR）；演練＝**NOT RUN** | 未實作（repo 外操作，無程序紀錄）；演練＝**NOT RUN** |

附註：`?ui=1` 與 G11 毒化測試同為未實作（MC §2、§6 為規格），不納入上表。

### 4.4 #1199 回存格式（⛔ Secrets／API Key／Token／密碼）

```
【UI2 回退回存】日期時間（台北）：…
觸發原因：…（停止條件 §2 第 _ 項／實機異常）
回退級別：R1／R4-a／R4-b（R2＝`?ui=1` 現未實作、不可選；R3 為守衛、非回退級別）；執行者：…
GitHub main SHA：…；revert PR：#…（無則寫「無」）
Cloud App 網址前綴：…；Main file：…；部署 commit 前 7 碼：…（看不到寫 NOT VERIFIED）
資料日：…；截圖：入口／?legacy=1／持股頁
未驗項目：…
```

## 5. 最重要缺口（未解除前不得切換）

1. **部署真相不可證**：Cloud 設定頁（owner／Main file／部署 commit）只有轉述，且不確定是否仍有 `app.py` 正式 App；UI2 畫面無版本字串。**Owner：客戶／Cloud 管理員；解阻證據：設定頁四欄＋最近成功部署 commit／時間（非敏感）。**
2. **回退程式路徑未建**：`?ui=1`、UI2 版 G11、可 revert 的切換 PR 皆未實作；R1 只在 `app.py` App 有效、守的是 nav4；slow lane 不擋 merge → 屬 `NUI2-CUTOVER` 批，需授權。
3. **前置與演練全缺**：~~Aggregator 未合併（#1255 Draft）~~（**撰稿時基線，已過時**：#1255 已合併 `8b39f385`，但**未接 consumer，M-A3／M-A4 未做**，動作欄仍 `⬜ 尚未提供`）、C1～C6 無一已滿足；R1～R4 全 NOT RUN、Cloud Reboot 未實測。

## 6. 補丁 C：現況可填 vs 不可填

| 欄位 | 現況 |
|---|---|
| GitHub `main` SHA（R4-a 目標值） | **可填**：本檔撰寫時 `origin/main`＝`a035abfcdaeb3c4bc52cc4837739c4719c7c95af`（補丁撰稿時為 `cca7a290deef8d4d46b2ffe68c5fe4ab149d774c`，**已過時**）；隨時前進，切換當下重取 |
| 切換 merge SHA／revert PR 號 | **不可填**：切換 PR 尚不存在 |
| 各 Cloud App 的 Repository（含 owner）／Branch／Main file／部署觸發 | **NOT VERIFIED**：僅客戶轉述日誌（見 0-4）；是否仍有 `app.py` 正式 App＝NOT VERIFIED |
| 最近成功部署 commit 與時間 | **NOT VERIFIED**：UI2 畫面無版本字串，無法自證 |
| R1 目標「原 `app.py` 部署 commit」／R4-b 目標 App、entrypoint、commit | **不可填**（依賴 Cloud 管理員） |

**需 Cloud 管理員提供（⛔ 不含 Secrets／Token）**：各 App 設定頁四欄（Repository＋owner、Branch、Main file path、網址前綴）＋最近成功部署 commit 前 7 碼與時間。未取得前，R1／R4-a／R4-b 的 SHA 映射全標 NOT VERIFIED，R1～R4 演練全標 NOT RUN，不得宣稱已驗。

---

## 7. （保留）與本手冊相關的未解 Gate 一覽

`NUI2-CUTOVER`（open）、`NUI2-ROLLBACK`（open，前置＝`NUI2-CUTOVER`）、C1～C7（無一已滿足，依 GM；未重評）、G11（未實作）、`?ui=1`（未實作）、M-A3／M-A4／M-A5／M-A6（未開始）、P2（A2 來源權利／A3 I1144-DG-SCOPE 接線／A4 收盤口徑）、#1237（NAS，Draft／HOLD）、#1107、真持股／登入／Sheet、OneBrain 正式接線。**本文件對以上任何一項皆無授權效力。**

## 8. UI2 查一檔旗標（P1）的停用與回退

> 來源：#1257（`a035abfc`，DEC-223；B-UI2-LOOKUP-P1-INPUT-1；#1199 comment `7064531081`）。以下旗標讀取位置為 `a035abfc` 實查。

**旗標與讀取位置（FACT，讀碼）**

| 項目 | 內容 | 位置 |
|---|---|---|
| 旗標名稱 | secrets 鍵 `ui2_lookup_input`；環境變數 `UI2_LOOKUP_INPUT` | `app_ui2.py::_read_lookup_flag`（`app_ui2.py:31-43`） |
| 讀取順序 | 先 `st.secrets`（`"ui2_lookup_input" in st.secrets`），否則環境變數；任何讀取失敗＝視為該來源不存在，**不會因失敗而開啟** | 同上 |
| 判讀 | 只有字串 `'1'`／`'true'`（大小寫不拘、去首尾空白）才開；None、空、`'0'`、`'false'`、亂字、非字串一律關 | `src/ui2/shell/app.py::lookup_flag_on`（`:77`） |
| 預設 | **OFF** | `run(diag_check=None, lookup_input: bool = False)`（`src/ui2/shell/app.py:83`）；入口 `app_ui2.py:46` `run(..., lookup_input=_read_lookup_flag())` |
| 注入與分支 | 開關只經參數注入 L5；L5 自己不讀 secrets／環境。僅在 `page == P4_TARGET and lookup_input is True` 時才走新路徑 | `src/ui2/shell/app.py:117`；`src/ui2/views/target.py`（`render_with_lookup`／`_render`） |
| 設定檔現況 | repo 內 `.streamlit/`、`.github/`、`requirements.txt` 皆**未設定**此旗標 | `git grep -n 'ui2_lookup_input\|UI2_LOOKUP' -- .streamlit .github requirements.txt` → 空 |

**停用與回退程序**
- **回退＝關閉旗標，不需改 code**：移除（或設為非 `'1'`／`'true'`）Cloud Secrets 的 `ui2_lookup_input` 與環境變數 `UI2_LOOKUP_INPUT`，Reboot／重新部署使其生效（Reboot 需求屬客戶陳述，未實測）。這是 Cloud 管理員操作，AI 不改 Secrets。
- **關閉後的現行畫面**：與 #1257 合併前**逐元素相同**。依據為兩條**各自獨立**的證據：(a) **flag-off golden**：`tests/test_ui2_lookup_p1.py` 對照 `tests/fixtures/ui2_lookup_p1_flag_off_golden.json`，該檔共 **8 筆**（`cold|curated`、`cold|lookup`、`loaded|curated`、`loaded|lookup`、`missing|curated`、`missing|lookup`、`unavailable|curated`、`unavailable|lookup`；以 `python3 -c "import json;print(len(json.load(open(...))))"` 實數），為改動前以 AppTest 擷取，來源＝repo 內測試；(b) **112 組 AppTest base＝head 逐元素比對**：由非作者 QA 另做，**不是 golden**，來源＝#1199 comment `7064531081`，repo 內無對應測試檔。皆為測試層證據，**非 Cloud 實機驗證**。
- ⛔ **不得在任何正式環境啟用旗標**。開啟旗標本身需另行裁示（`7064531081`：「開啟旗標本身需另行裁示」；P1 無資料來源、不顯示價格；真報價屬 P2，HOLD）。
- **Cloud 上實際旗標狀態＝NOT VERIFIED**（repo 讀不到 Cloud Secrets／環境變數）。
- 旗標 ON 時的行為（僅供辨識，非授權）：標的頁頂端 `st.form`（`ui2_` 前綴）輸入、提交時驗證代號、灰態「尚未查詢／代號無效」；不接資料、不產生 OK／STALE／MISSING／FETCH_FAILED、不顯示價格。

## 9. 已知限制與揭露（`CLAUDE.md` §-2 規則 6）

- 本檔**單組撰寫、未經非作者 QA**；第 0 節各項重驗為本組於 `a035abfc` 以 `git`／`grep` 實查，**無第二組複驗**。
- 舊 UI 側欄 D2 雙層 radio 的「預期入口」描述僅依註解與位置推論＝INFERENCE。
- 未重驗：Audit／Acceptance Checklist §11 勾選狀態、C1～C7 各關最新狀態（GM 基準 2026-11-10）、Cloud 任何設定。
- 本檔未修改任何既有檔；BACKLOG／GM 內的過時敘述（見 0.A）留待後續獨立批次同步。
- CI：本檔為 docs-only；slow lane 非阻擋，合併前須人工核對；**文件落地不等於切換授權、不等於可切換**。
