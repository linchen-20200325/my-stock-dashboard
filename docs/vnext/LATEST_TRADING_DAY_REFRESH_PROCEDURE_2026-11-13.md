# 台股資料更新到最新有效交易日：最小安全程序規劃 — 2026-11-13

> **性質**：證據＋程序規劃文件（docs-only，新增單檔）。**不是決策來源**：決策只在 `docs/DECISIONS.md`（DEC-181、DEC-182）；本文件不新增第二份 SSOT。
> **基準**：`origin/main`＝`138e081bbec24f5b20f1301c1da634d4ab8d9551`（`git rev-parse` 實查）；#1124 head `3cd3f525c345327ef9f90b71b28f2e262202d5dd`、#1125 head `cf4739c525052f38410d991eec24da83966f4738`、#1126 head `1654ae6096c31157417c0fe2731bb214d4a2b077`（本地 `origin/auto/*` ref 實查，與總管 2026-11-13 22:20 台北的 GitHub 查詢相同；皆時點快照，cron 每日推進，一律重查）。
> ⚠️ **`file:line` 皆為 2026-11-13、main `138e081` 時點的行號快照，會漂移**；引用前請重跑 `grep -n`。本地為淺層複製。
> **單組聲明**：本文件由寫入組單組撰寫（素材為總管整合的三組單組稽核＋寫入組對 file:line 與 parquet 的重新核對），**未經非作者獨立 QA**（`CLAUDE.md` §-2 規則 6）；**不是 QA PASS，不是授權，不是法律意見**。QA 結果由總管於 PR 補記。
> **客戶授權出處**：DEC-181（資料更新程序規劃、唯讀）、DEC-182（恢復 CI 續工；「可立即執行的已授權步驟」與「仍待核准事項」的分界）。

**TL;DR（5 行）**
1. **目前最新有效交易日**：Cloud 會讀到的 main 是 **2026-11-09**（收盤 41,661.70）；repo 內已存在的最新「價格欄位完整且自洽」日是 **2026-11-11**，但只在 #1124 分支（未進 main）；理論上今晚可信上限是 11-12，但**任何已知 ref 都沒有 11-12 的台股列**；11-10～11-12 是否為交易日仍 NOT VERIFIED（G-07）。
2. **最快安全做法**：不手動觸發、不 bootstrap；等下一輪 schedule（預期台北 11-13 約 23:30～11-14 約 03:45）把 11-12 寫進 `auto/data-macro-history`，AI 做 S0 唯讀檢核後，**在同一個 head** 上走既有路徑（客戶裁示→客戶觸發 CI→非作者審閱→客戶明示 merge→客戶手動 Reboot Cloud）。此為 RECOMMENDATION。
3. **必須先處理的 Gate**：客戶 HOLD（僅 #1124 的解除）、DPE-4＝B、DPE-5（同 head 的 CI 由客戶觸發）、DPE-3／DG-LIC 與 DG-PIT 的取捨；DG-SCOPE／DG-COV／WIRING-GATE 對「只更新台股卡資料檔」判讀不阻擋（INFERENCE）。
4. **是否需客戶裁示**：**需要**（§10 有可複製回覆範本）；其中「**可立即執行的步驟（視為已授權〔AI 解讀〕）**」僅 S0 唯讀檢核、文件與交接同步、非作者唯讀審閱 #1124 diff（依據見 §8），其餘皆「待核准」（§8 逐步標註）。
5. **本文件不構成授權**：不授權觸發任何抓取／bootstrap／回補、不授權合併／關閉／rebase #1124～#1126、不解除任何 Gate／HOLD。

## 0. 目的與禁止事項

| 項 | 內容 |
|---|---|
| 目的 | 回答客戶：台股卡資料如何從 2026-11-09 安全更新到最新有效交易日（抓取、PIT、來源授權、驗證、發布到 main、Cloud 重新部署、資料日確認），並區分已授權步驟與待核准事項 |
| 本文件**做**了什麼 | 唯讀檢視 repo 內碼、文件、`.github/workflows`、git 物件（`git show` 讀本地 `origin/main` 與 `origin/auto/data-macro-history`）；以 scratchpad 內的 pyarrow 唯讀讀取 parquet |
| 本文件**沒有**做 | **未連網**取資料；**未執行**任何 fetcher／streamlit／測試／`scripts/`；**未觸發**任何 workflow；未探測外部 API；未回補；未動 NAS／Proxy／Secrets；未讀取任何 Secrets 值 |
| 不宣稱 | 不宣稱 DG-LIC／DG-PIT 已解除；不宣稱部署追蹤 main 最新提交；不宣稱 Cloud 自動部署或不自動部署；不宣稱任何測試通過；不宣稱 QA PASS |
| 標籤 | **FACT**（可由 `file:line`／git 物件重現）／**INFERENCE**／**NOT VERIFIED**；客戶口述與程式碼推論分欄（§1） |

## 1. 客戶 Cloud 實測（口述）vs 程式碼推論

客戶原文全文在 `docs/DECISIONS.md` DEC-181 fence（本文件不重抄）。**客戶口述＝repo 內無法驗證**；右欄是寫入組由程式碼／資料得到的推論，**兩欄不得混成同一級證據**。

| 客戶口述（實測；repo 內不可驗） | 程式碼／資料推論（右欄不升級） |
|---|---|
| 預設畫面＝FAKE | FACT（程式碼層，承 DEC-180 假說 A）：`src/ui2/shell/app.py` 預設 `FEED_FAKE`。與口述一致 |
| 切換 Real-data Preview 成功 | 與 DEC-180 假說 B 一致：Real Feed 只讀 `data_cache`（INFERENCE：口述未說明切換方式） |
| 台股加權指數 41,661.70；畫面資料日 2026-11-09 | **FACT（資料）**：`origin/main` 的 `data_cache/twii_ohlcv.parquet` 最後一列＝2026-11-09、close＝41661.699219（寫入組以 pyarrow 重讀）。與口述**吻合**。INFERENCE：弱旁證「Cloud 目前部署的檔案至少含 main 的 11-09 資料」；**不能證明**部署 commit＝最新 main、也**不能證明**自動部署 |
| 日 K 正常顯示 | INFERENCE：main 的 20 根日 K 逐根通過契約（含 11-09 列的 `fetched_at`＝11-09T19:40Z，晚於該日台北 17:00）；未實機驗 |
| 其他指標多數尚未接線 | 與 DEC-180 §4 一致（FACT，程式碼層）：UI2 Real 軸只接台股＋位階 |
| 客戶未提過期警示 | 與推導一致：`age_days`＝4 ≤ 7，不標過期（§7） |
| Cloud 啟動日誌顯示 main／app_ui2.py | **客戶口述的日誌觀測**（日誌原文不在 repo；與 DEC-180 的轉述一致）；日期、commit、repo owner 仍 NOT VERIFIED |
| 部署更新需手動 Reboot | **客戶陳述**；非 Cloud 設定頁證據；**不證明**自動部署或不自動部署 |
| 採納資料優先架構方案 A | 客戶的**方向性採納**（DEC-181 (二)）；**不是**任何 Gate 的授權、不授權施工 |
| （仍 NOT VERIFIED） | Cloud 實際部署 commit、舊 App 現況、NAS Secrets 配置、repo owner |

## 2. 資料日期與欄位完整性（FACT；寫入組以 pyarrow 讀 `git show` 輸出，重新核對）

### 2.1 三資料集最新日不齊

| 資料集 | main 最後日（列數） | #1124 分支最後日（列數） | 分支多出的列 | 重疊列被修改格數 |
|---|---|---|---|---|
| `twii_ohlcv.parquet` | 2026-11-09（4913） | 2026-11-11（4915） | 11-10、11-11（**無 11-12**） | 0 |
| `finmind_inst.parquet` | 2026-11-09（4939） | 2026-11-12（4942） | 11-10、11-11、11-12 | 0 |
| `finmind_margin.parquet` | 2026-11-09（4939） | 2026-11-12（4942） | 11-10、11-11、11-12 | 0 |

11-12 的台股列缺席的原因 **NOT VERIFIED**（metadata 無錯誤記錄；兩個未區分的假說：抓取時點太早，或 Yahoo 間歇空缺）。入帳時點事實（FACT，`fetched_at`）：11-10 台股於 T+1（台北 11-11 00:55）即入帳，11-11 台股卻到 T+2（11-12T17:29Z＝台北 11-13 01:29）才入帳，故「早抓取不到」**不是穩定規律**，下一輪（台北約 23:30–03:45）能否帶出 11-12 不確定。

### 2.2 台股 `twii_ohlcv` 逐列（欄位：date, open, high, low, close, volume, source=`Yahoo:^TWII:chart`, fetched_at；**無** `as_of`／`is_imputed` 欄）

| 日 | open | high | low | close | volume | fetched_at（UTC） | 位置 |
|---|---|---|---|---|---|---|---|
| 11-09 | 40347.28 | 42349.36 | 40347.28 | **41661.70** | NaN | 11-09T19:40:31 | main 與分支皆有 |
| 11-10 | 42130.33 | 43135.92 | 41930.03 | 42711.92 | 4,766,000 | 11-10T16:55:08 | 只在分支 |
| 11-11 | 43135.76 | 44257.15 | 42708.05 | 44257.15（＝high） | 4,012,900 | 11-12T17:29:20 | 只在分支 |

- 完整性（FACT）：11-10、11-11 的 OHLC 全有值且非 0；全表 `high ≥ max(open,close)` 與 `low ≤ min(open,close)` 違反 0 列；日期唯一、遞增；價格量級合理；漲跌約 +2.52%（11-10）、+3.62%（11-11）。價格自洽**不等於**價格真實（外部真值未核對，G-01）。
- `volume`：全表 35 列 NaN、0 列為 0；2026-09-23 之後只有 11-05、11-10、11-11 有 volume。UI2 不讀 volume（`src/data/macro/macro_cache_reader.py` `TWII_OHLC_COLUMNS`＝open/high/low/close/fetched_at，L338）；**成交量不可當完整性判準**。
- **11-10 volume 先空後補寫**（FACT，分支提交歷史）：`d0f14437`（2026-11-10T16:55:23Z）該列 volume＝NaN；`fc447def`（2026-11-11T16:59:56Z）同列變 4,766,000，close 與 `fetched_at` 不變。INFERENCE：發布層 union 規則「舊 null、新有值→採新值；`fetched_at` 等揮發欄取舊值」（`scripts/publish_data_pr.py` docstring L48-53）加上增量起點＝main 最後日＋1（`scripts/update_macro_history.py` L1015），所以每輪都從 11-10 重抓並補填；provenance 缺口是 `fetched_at`＝首次寫入時間，不保證該列所有欄位已定稿。4,766,000 末三位為 000，可能是未完成或湊整量（INFERENCE；無 Yahoo 原始回應可驗）。

### 2.3 法人與融資

- `finmind_inst.foreign_buy`（億，轉換過程 NOT VERIFIED）：11-05 −1024.61；11-06 −911.88；11-09 −900.56；11-10 −341.17；**11-11 −7.66；11-12 −6.85**。全表無 NaN／0。
  - 寫入組重算：最近 60 列 |值| 中位數約 **417**（有號中位數 −137）；11-11、11-12 比它小約兩個數量級。⚠️ 與素材「中位數 |137|」不符：137 是**有號**中位數，以重算為準（結論不變：偏小一個量級以上）。
  - 2025-01-01 起計歷史 22 列 |值| < 10（另加 11-11、11-12 共 24 列；例：2025-12-19、2026-01-15、2026-08-25），`fetched_at` 皆 2026-09-24 批次回補；11-11、11-12 是 cron 逐日抓取的新列。11-11 當日加權指數約 +3.6% 而外資僅個位數億——標為**可疑，NOT VERIFIED**（不能推斷是錯，也不能推斷是對；需外部真值）。
- `finmind_margin.margin_balance`（元）：11-09 539,915,741,000；11-10 536,678,732,000；11-11 541,158,093,000；11-12 533,474,629,000；無 NaN／≤0；量級一致。
- inst／margin 的 11-10 以後是否也有「先空後補寫」未查（NOT VERIFIED）。

### 2.4 metadata 與其他檔

- `metadata.json`：main `updated_at` 2026-11-09T19:40:36Z；分支 2026-11-12T17:29:27Z。twii／inst／margin 的 `last_updated` main 為 11-09，分支為 11-11／11-12／11-12，`last_error` 皆 null。
- `finmind_m1m2`：`last_updated` 2026-09-01、`fetch_outcome`＝`NO_NEW_DATA`、`last_error`「抓取結果為空」（請求窗口內無新月份，非抓取失敗）；`tw_pmi`：`last_updated` 2026-10-01、`fetch_outcome`＝`UNDETERMINED`（最近一次抓取結果無法判定，**不確認為已是最新**）。兩者在分支亦無改善、非 PR HOLD 造成。
- #1124 共 5 檔整包：twii／inst／margin parquet、`data_cache/macro_last_good/tw_pmi.json`（僅 `fetched_at`／`cached_at` 刷新，值 62.5、資料月 2026-10-01 不變——素材所述，寫入組未重讀此檔；`git diff --stat` 實查該檔 +2／−2）、`metadata.json`。`data_cache/tw_pmi.parquet` 本輪無變更（實查）。

### 2.5 交易日曆

repo 無靜態休市表（`tests/fixtures/twse_holiday_schedule_115_synthetic.json` 為合成資料，不含 11 月）。11-10／11-11／11-12 是否為交易日 **NOT VERIFIED**（GAPS 文件 G-07，L131）；間接旁證：三資料集有列且價格變動；sector-flow 分支 metadata 記 11-10／11-11／11-12 `holiday False`（我們自己管線的旗標，非權威曆）。10 月缺 10-09、10-23、10-26（三資料集一致缺，原因 repo 未載）。

## 3. 最新有效交易日：判準與推導

判準（至少同時滿足；缺一即不能稱「最新有效」）：

1. **是交易日**（G-07，NOT VERIFIED）。
2. **來源已發布**：Yahoo EOD 約翌日 04:00 台北（`CLAUDE.md` §2.3 表）；TWSE 17:00 後可信。
3. **通過 UI2 日 K 契約**：`shared/twii_ohlc_contract.py` L29 `TWII_BAR_TRUSTED_AFTER_TAIPEI_HOUR=17`；L187-189 判斷該列 `fetched_at`（台北）須晚於該日、或同日 ≥17:00，否則整段日 K 判 `INCOMPLETE_BAR`。該檔 L134 自述 `fetched_at` **不是** PIT 可得時間證據。CLAUDE.md 的 T+1 規則與此 17:00 契約文件未調和（INFERENCE）。
4. **OHLC 有效**（§2.2）。
5. 成交量**不可**當完整性判準。
6. 相關原則（Risk Cap 語境，僅供參考，不是日 K 顯示的 Gate）：DEC-070 Q2——Yahoo 缺 `^TWII` 必要 K 棒要 Fail-Stop，不以前一交易日頂替（`docs/DECISIONS.md` L1895 起）。

推導：

| 層級 | 日期 | 依據 |
|---|---|---|
| main（Cloud 所見） | **2026-11-09** | FACT |
| repo 內已存在的最新價格完整日 | **2026-11-11**（只在 #1124 分支） | FACT（價格自洽）；11-11 的 `fetched_at`＝11-12T17:29Z＝台北 11-13 01:29，晚於 11-11；11-10 的＝台北 11-11 00:55，晚於 11-10；兩者 INFERENCE 應通過契約（未執行驗證器） |
| 理論可信上限（2026-11-13 22:20 台北） | **2026-11-12** | INFERENCE：Yahoo T+1 約 11-13 04:00～05:00 台北已過；前提 G-07 成立且 Yahoo 產出有效收盤；**任何已知 ref 都沒有 11-12 台股列** |
| 11-13 | 不算完整 | 尚未滿 T+1 |

## 4. `update_macro_history.yml` 行為（FACT；讀碼，未執行；行號對 138e081）

| 項 | 行為 | 出處 |
|---|---|---|
| 觸發 | schedule `cron '0 9 * * *'`（UTC 09:00，含週末）；`workflow_dispatch` 存在 | yml L20、L4-17 |
| 實際執行延遲 | 6.5～10.7 小時：11-06 16:39、11-07 15:33、11-08 15:52、11-09 19:39、11-10 16:54、11-11 16:59、11-12 17:28（UTC）。來源：總管 GitHub 查詢（本組未重取）；本地可核對的只有分支上三筆提交（11-10T16:55Z、11-11T16:59Z、11-12T17:29Z） | 總管轉述＋`git log` |
| 手動 inputs | `bootstrap`（字串，預設 'false'）、`years`（預設 '20'，只在 bootstrap 用）、`dry_run`（預設空）；**無**起訖日／force／job 選擇 input | yml L6-17 |
| 判定字面 | 只有 `bootstrap=='true'` 才 bootstrap；只有 `dry_run=='true'` 才加 `--dry-run` | yml L66、L114 |
| concurrency／timeout | group `data-publish-macro-history`、`cancel-in-progress: false`；**無** `timeout-minutes` | yml L23-25 |
| 權限／token | `contents: write`＋`pull-requests: write`；**無** `actions: write`；token＝`GITHUB_TOKEN`（非 PAT） | yml L31-33、L74 |
| 腳本回傳 | **一律 `return 0`**；失敗只寫 metadata `last_error` 與 PR body | `scripts/update_macro_history.py` L1138 |
| 增量 | `start = last_date(checkout 的 main parquet)+1`，抓 [start, today(UTC)]；腳本層只追加不覆寫 | 同檔 L1011-1022 |
| volume 規則 | volume==0 且 high>low 設為 NaN（物理上不可能的觀測） | 同檔 L258-264 |
| 有無「收盤後才抓」檢查 | **無**；早抓的 K 棒之後不會被覆寫（start＝last+1），讀取端以 `fetched_at` 早於 17:00 台北判 `INCOMPLETE_BAR` | INFERENCE（素材讀碼）＋契約 L187 |
| 寫入範圍 | `metadata.json`、`twii_ohlcv`／`finmind_inst`／`finmind_margin`／`finmind_m1m2`／`tw_pmi` parquet、`macro_last_good/`；與 sector-flow、forward-test 路徑不重疊；守衛 `tests/test_cron_workflows_no_direct_push.py` | yml L115-120 |
| 發布分支 | 固定 `auto/data-macro-history`（`BRANCH_PREFIX="auto/data-"` L119、`branch=f"{BRANCH_PREFIX}{job}"` L824）；一般 git push；禁 force／`+refspec`／rebase／`reset --hard`／`gh workflow`／`gh pr merge`／dispatch（`_guard` L690-724） | `scripts/publish_data_pr.py` |
| 分支已存在 | `checkout -B <branch> origin/<branch>`＋一般 `merge --no-edit origin/main`（不 rebase、不 force，commit 累積；衝突則 abort exit 1）；PR `--base main`、非 draft | docstring L41-60 |
| union（fail-closed） | 舊非 null 而新為 null／缺欄，或兩邊皆非 null 但不同 → `PublishError` exit 1；舊 null→新值採新；揮發欄取舊值 | docstring L48-60 |
| head 漂移 | **只有出現實質變動才會 commit**：`metadata.json` 的 `updated_at`、`macro_last_good/tw_pmi.json` 的 `cached_at`／`fetched_at`、parquet 列級 `fetched_at` 被登記為揮發欄（`VOLATILE_JSON_KEYS` L126-139、`VOLATILE_PARQUET_COLS` L141），僅揮發欄位變動時「還原工作樹、不開 PR」（L833-851）。故 #1124 的 head 只在有新資料列、新 `last_error` 或 `fetch_outcome` 變化時前進；沒有新交易日的執行（如週末）預期不 commit（INFERENCE，未實測）；手動 dispatch 同理，有實質新資料時才會使 head 前進 | `scripts/publish_data_pr.py` L125-141、L833-851 |
| NAS／Proxy（只列名稱） | Fetch 步驟注入 `PROXY_URL`、`FINMIND_TOKEN`、`NAS_BASE_URL`、`NAS_API_KEY`；Publish 步驟只有 `GITHUB_TOKEN`。Yahoo／CBC／data.gov.tw／durable PMI 走 `proxy_helper.fetch_url`；FinMind 直連。缺 `PROXY_URL`→靜默直連（任何 200 都印「已透過 Synology NAS 成功抓取」，不能當有走 NAS 證據）；缺 `NAS_BASE_URL`→中繼回 None；缺 `FINMIND_TOKEN`→inst／margin 跳過並寫 `last_error`，**皆不使 job fail**。GitHub secrets 是否有值 NOT VERIFIED | yml L59-64 |

### 4.1 pr-check 與 `GITHUB_TOKEN`

repo 刻意不繞過：發布腳本不 dispatch、無 `actions: write`（理由：workflow_dispatch 產生的 jobs 不算 PR 的 required checks；PR body 寫警語，需有權限者 Close→Reopen 或 Update branch 後見 `ui2-browser-gate` 同 head 綠燈才可合併）。實測引自 docs（未重查）：#1124 每個 head 有一筆 event=pull_request、發起者 `github-actions[bot]`、結論 `action_required`、jobs 0 的 pr-check run（最新 run 43270012637，head 3cd3f525）；commit check-runs API 回 `total_count` 0 與此一致但不具鑑別力。為何停在 `action_required`（Actions 核准設定）與 branch protection（403）NOT VERIFIED。先例：#1103 由客戶手動觸發後 `ui2-browser-gate` 約 5 分鐘綠燈、約 5 小時內合併。

### 4.2 Actions 可用性（依 DEC-182；帳單頁本身 AI 仍讀不到）

- **客戶陳述**（DEC-182，repo 內無法驗證）：本專案是公開 Repository，GitHub Actions 可正常執行；其他私有專案的帳務限制不得套用於本專案。
- **INFERENCE（支持，不升級）**：schedule 最近 6 次（run #193～#198，最近 2026-11-12T17:28Z）皆 success；pr-check 2026-11-13 多次正常啟動並完成（含 main push run 43437741216 success，總管查）；run 43434257213 為 #1188 head `a18b4815` 的 pull_request run，五項 check 皆 success（總管查）。本組只能在本地核對到 `a18b4815` 提交存在（`git log` 實查），**run id 與結論＝總管轉述，本組未連網重取**。
- AI 讀不到 repo 設定頁與帳單頁；但依 DEC-182，**不再列為阻擋事項，不得因「帳務」停工**。保留原則：**若 CI 因任何平台原因無法啟動，保留證據、勿反覆重跑**。#1124 的 `action_required`／jobs 0 是核准機制，不是啟動失敗。

## 5. 手動觸發對照（**僅說明行為；本批不觸發任何一種**）

| 輸入 | 抓資料 | 發布層 | 寫入／影響 | 風險 |
|---|---|---|---|---|
| `dry_run=true` | **照常連外抓取**（Yahoo、FinMind、CBC EF15M01、data.gov.tw、durable PMI 8 源） | 只跑 detect／classify 與 `git ls-remote`（唯讀）；跳過 fetch／checkout／merge／union／commit／push／PR | 僅 runner 暫存工作樹，結束即丟；無 upload-artifact | dry-run 綠燈**不能**推出真實執行不會 `PublishError`；仍多一次 Yahoo／FinMind／NAS 取數 |
| 全預設（`dry_run` 空、`bootstrap=false`） | 同上 | **真實發布**：commit／push／開或更新 PR | 寫 `auto/data-macro-history`、重寫 PR body 的 data-status 區塊；**#1124 head 前進**；main 不前進 | 若來源對已入庫日期給不同值或新值為空→之後每次排程皆紅，須人工關 PR 並刪分支（**不可逆**，`PROJECT_RULES.md` §4 #8，L243）；早於收盤後手動執行可能鎖入未完成 K 棒；merge 衝突 exit 1 |
| `bootstrap=true`（可帶 `years`） | 不讀既有檔，整段重抓 | 整檔覆寫；`finmind_inst` 新舊口徑以 `source` 欄分界（2017-12-18 前）；分支已存在時口徑差異 fail-closed | 改寫全歷史 `fetched_at` | **禁止路徑**：本批與日後都不得用於「更新到最新日」；隱性重建（`finmind_m1m2` sanity 不過、既有檔讀取失敗）亦會重抓 |

另：sector-flow（`update_sector_flow.yml`）與 macro-forward-test（`update_macro_forward_test.yml`）為獨立 workflow，同一 publish helper，互不牽動；cron 與手動共用 concurrency group（平台行為，repo 無證據）。

## 6. Gate 對照（對「只更新台股卡資料日」；多為 INFERENCE，依文件適用範圍）

| Gate | 現況 | 是否阻擋 | 解除條件／出處 |
|---|---|---|---|
| 客戶 HOLD（#1124～#1126） | DEC-179 方案 A（維持 HOLD）；禁止 Merge／Close／Rebase；三 PR 聯合表述 | **阻擋（最直接）** | 客戶另行明示；DEC-176(a)、DEC-179、DEC-180、DEC-182 |
| DPE-4（三 PR 處置方向） | 未裁示；沒答覆＝三 PR 全 HOLD | **阻擋** | 客戶選 B；GAPS 文件 L274。⚠️ GAPS 原 B 範本是「#1124、#1125 進評估」，本程序要的是「**僅 #1124**」變體，**客戶須明示** |
| DPE-5（`ui2-browser-gate` 同 head 與進 main） | 未裁示；三 PR 近 3 輪 pr-check 全 `action_required`、jobs 0；mergeable_state behind | **阻擋** | 客戶在目前 head 觸發 CI（AI 不代做）；GAPS L286 |
| DPE-1 | 未裁示 | 部分（DPE-4 的文件依賴） | 客戶回覆 DPE-1 |
| DPE-2（#1126） | 未裁示 | 不阻擋台股卡（#1126 與 #1124 檔案不重疊） | — |
| DPE-3＝D | 已裁示 D；BLOCKED（缺條款原文／法務／網域放行） | **部分**（也擋外部真值對帳） | 條款原文／法務；客戶另行明示 |
| DPE-6＝B | 部分補件（本批客戶口述再補） | 不阻擋合併；擋「Cloud 會前進」的設定頁證明 | Cloud 設定頁證據、owner、部署 commit |
| DPE-7 | 維持 A，11-19 為檢查點，非自動放行 | 不阻擋 | — |
| DG-SCOPE／DG-COV／I1144-WIRING-GATE | 未裁示 | 不阻擋（INFERENCE：範圍是融資／板塊／外資與 runtime 接線；台股卡已是 REAL 接線，資料檔更新不碰施工面） | 連新欄位接線才需要 |
| DG-PIT | 未裁示 | **部分**（正式 Gate 對象是融資／板塊最新值時間語意；台股卡／日 K 時間顯示不受影響；但台股 PIT 缺口 G-01／03／04／07／08 開著） | 客戶裁示；外部真值或 DPE-1 |
| DG-LIC | HOLD；Yahoo 條款原文零頁；FinMind 僅部分；客戶三問未答 | **部分**（INFERENCE：無文件說它擋「合併資料 PR」；但合併 #1124 會把 FinMind 外資／融資新列併入公開 main） | 客戶三問＋條款原文／法務；或客戶明示風險自負（非 AI 認定已授權；效力以客戶原文與 DEC 為準） |
| DEC-156 A | 不核准新 live API、cron、publisher 或第二個 writer（`docs/DECISIONS.md` L7957） | 對現行 producer 路徑不阻擋；對「只含 twii 的新發布流程」阻擋 | 客戶授權流程變更 |
| branch protection（GH006） | main 要 `ui2-browser-gate`；4 次直推失敗 | 阻擋直推 main（設定本身 403＝NOT VERIFIED） | — |
| PROJECT_RULES §4 #8 | 刪 branch 屬不可逆 | 擋「關 PR＋刪分支重建」 | 客戶裁示 |

**「等 cron」本身不會讓 main 前進**（cron 只推 `auto/data-*` 分支、無自動合併）。#1124 是 5 檔整包，合併會連帶把 inst／margin 11-10～11-12（含可疑外資值）與 `tw_pmi.json` 時間戳刷新帶入 main；Legacy 畫面也讀 inst／margin／twii，資料日會一併改變。只含台股一檔的 PR 需另案流程變更（`DAILY_DATA_PR_PIT_CRON_INVESTIGATION_2026-11-12.md` §5.1 方案 C 所述；DEC-156 A 邊界；獨立 PR＋非作者 QA）——不建議。

## 7. UI2 行為（純資料檔更新）

- 路徑：`real_feed._read_twii`（`src/services/ui2/real_feed.py` L49）→`market_twii_view_service.get_twii_trend_view`→`load_twii_close`→`compute_cache_staleness`；`as_of` 取自 parquet `date` 欄最大值（非 metadata）；`age_days = date.today() − as_of`（主機日，非台北日；BACKLOG `I1140-TODAY-TZ`）（`macro_cache_reader.py` L134、L169）；`age_days > 7` 才 `is_stale`（L197；`shared/staleness.py` L135 `STALE_DAYS_DAILY=7`）。
- 目前 `as_of`＝11-09：2026-11-13 `age_days`＝4 不標過期；**2026-11-17（週二）起 `age_days`＝8 轉過期**。若 #1124 現 head（as_of 11-11）進 main：轉過期日推遲到 **11-19**；若進來的 as_of 是 11-10 則 11-18；若 S0 看到 11-12 列且進 main，則 11-20。（日期為曆法推算，Python 核對星期；主機日以 Cloud 時區為準，NOT VERIFIED。）
- 日 K：20 根每根過契約，任一根不合格→整張日 K 降級為灰色字樣，卡片不受影響。新列價格自洽（FACT）；`fetched_at` 皆晚於各自交易日（§3，INFERENCE 應通過）。
- 純資料更新**不需改 code／測試／守衛**（INFERENCE）：viewport 證據 `source_hash` 涵蓋 `src/ui2/**/*.py`、`app_ui2.py`、`tests/ui2_viewport/measure_viewport.py`，不含 `data_cache`（`measure_viewport.py` L824-829；`tests/test_ui2_real_feed.py` L982-992）。相關測試多為相對斷言，`test_margin_fact_service` 的釘住快照遇最後日不同會 skip 而非紅（均未執行）；決定性證據是 PR 同 head 的原生 CI。`ui2-browser` 在 Real feed 下對資料日是否敏感 NOT VERIFIED。
- Cloud 需客戶手動 Reboot 後才讀到新 main（客戶陳述，非實測）。

## 8. 最小一次性更新程序 S0–S6（RECOMMENDATION；AI 不觸發任何抓取／bootstrap／回補，不合併不關閉不 rebase #1124～#1126）

總管推薦（路徑 B）：**不手動 dispatch、不做 bootstrap；等下一輪 schedule 把 11-12 的台股列寫進 `auto/data-macro-history` 後，在「同一個 head」上走既有路徑。**

| 步 | 誰 | 做什麼 | 授權狀態 |
|---|---|---|---|
| S0 | AI（唯讀） | 下一輪 cron 後重查分支：twii 是否出現 11-12 列、OHLC 自洽、`fetched_at` 晚於該日、inst／margin 值與單位、metadata `last_error`、PR 狀態；產出「head SHA＋資料檢核表」交客戶。**不連外抓資料**。**決策規則**：若 11-12 列存在但 `fetched_at` 早於該日台北 17:00（`INCOMPLETE_BAR`，且增量 start＝last+1 不會覆寫），或 11-12 仍缺列→S0 結論為「**不建議放行該 head**」，改「再等一輪」或客戶改選路徑 A（合併現 head，twii 到 11-11）並重新取得其裁示 | **視為已授權（解讀）**（唯讀；head 變動時重做；依據見下方註） |
| S1 | 客戶 | 裁示 DPE-4＝B（僅 #1124 進放行評估，#1125／#1126 維持 HOLD）；DPE-3／DG-LIC 與 DG-PIT 二選一（等條款確認，或明示承擔風險）；表態 inst 11-11／11-12 可疑值是否整包進 main | **待核准**（客戶） |
| S2 | 客戶 | DPE-5：在 S0 的 head 上 Close→Reopen（或 Update branch）觸發 pr-check，確認 `ui2-browser-gate` 與 head SHA 一致綠燈；head 若再前進則重來。**註**：Close→Reopen 僅限客戶操作、保留分支、不刪分支，**不等於** §8.2 禁止的「關 PR＋刪分支重建」；優先 Close→Reopen（head 不變）；Update branch 會產生新 head（merge main）→S3／CI 須在新 head 上重做；Close 期間若 cron 跑到，找不到 open PR 可能另開新 PR，請避開 cron 時段（台北約 23:30–03:45）；main 前進（含本 docs PR 合併）後 #1124 會 behind、需 Update branch，視同 head 前進 | **待核准**（客戶動作；AI 不得代做） |
| S3 | AI（唯讀、非作者） | 獨立審閱 #1124 diff（5 檔；重點：twii 新列、inst 可疑值、metadata、`tw_pmi.json` 僅時間戳）＋核對 CI、review threads、mergeable；head 漂移時重做 | **視為已授權（解讀）**（唯讀；依據見下方註） |
| S4 | 客戶明示後 | merge #1124；AI 不得自行合併資料 PR | **待核准**（merge 須客戶明示） |
| S5 | 客戶 | 手動 Reboot Cloud App | **待核准**（客戶動作；非 AI 步驟） |
| S6 | AI | 依客戶畫面回報核對「資料日前進、無過期警示」並登錄；Cloud 實際部署 commit 仍 NOT VERIFIED | 客戶回報後才執行；登錄屬**已授權**的文件與交接同步 |
| — | AI | 文件與交接同步（證據／HANDOFF／BACKLOG／PROJECT_STATE），沿用非作者 QA、同 head CI、Merge Gate | **已授權**（DEC-182 第 3 項客戶原文「證據及交接同步」） |

> **授權依據註（S0、S3 的「視為已授權（解讀）」）**：AI 解讀為落在客戶「唯讀稽核與更新程序規劃」授權內（DEC-181 限制段；DEC-182 第 3 項「證據及交接同步」）；客戶未逐項點名 S0／diff 審閱；不含任何抓取或 Gate 動作。DEC-182 (五) 是 AI 整理表，**不可**當作授權出處。

### 8.1 替代路徑 A／B／C／D 比較

> 代號對照（防混淆；各字母只在所屬決策內有效）：本節路徑 A–D ≠ DPE-3／DPE-4／DPE-5 的 A–D ≠ DEC-180 的架構方案 A／B／C。

| 路徑 | 做法 | 正確性 | 風險 | 速度 | Token／成本 | 授權狀態 |
|---|---|---|---|---|---|---|
| A | 合併 #1124 **現** head（twii 到 11-11） | 價格自洽；缺 11-12 | 須在同一 head 內完成 CI→審閱→合併（head 有新資料時才前進，不必然每天）；整包帶入 inst 可疑值 | 最快 | 低 | 待核准（同 S1～S5） |
| **B（推薦）** | 等下一輪 cron 後，S0→S1～S6 在**同一 head** | 較新（可能含 11-12）；零新 Gate；不違 DEC-156 | 慢約半天；若 11-12 又缺列則退回 A 或再等一輪 | 中 | 低（無額外取數） | S0／S3 視為已授權（解讀），其餘待核准 |
| C | 客戶手動 dispatch `update_macro_history`（建議台北 11-14 05:00 後、先 `dry_run=true`） | 可能較早取到 11-12 | dry-run 仍連外且不驗發布層；真實執行使 #1124 head 再漂移並重寫 body；**main 不前進**；多一次 Yahoo／FinMind／NAS 取數；fail-closed 風險（§5） | 中 | 中（多一輪外部取數） | **待核准**（是否授權客戶端手動 workflow_dispatch；不建議） |
| D | 不處理 | main 停 11-09 | 2026-11-17 起 UI2 台股卡轉過期警示 | 0 | 0 | 預設維持 |

### 8.2 禁止路徑

直推 main（branch protection）；關 PR＋刪分支重建（不可逆，§4 #8）；只含 twii 的新發布流程（DEC-156 A）；bootstrap／回補；讓 New UI2 呼叫 NAS 或 L1 抓取程式；AI 自行觸發任何抓取。**授權狀態：禁止。**

### 8.3 時序注意

2026-11-14 為週六、11-15 為週日（台股無新 K 棒）；cron 含週末每日執行，但沒有新交易日時預期不 commit（INFERENCE，未實測），head 可能穩定；仍須同一 head 內完成 CI→審閱→合併。客戶若在 S0 前先完成 S1，可在 S0 當下立即做 S2，縮短 head 變動窗口。

## 9. 尚待客戶裁示的 Gate（本批不授權、不施工）

DPE-4＝B（僅 #1124）；DPE-3／DG-LIC 與 DG-PIT 取捨；DPE-5（客戶於同 head 觸發 CI）；merge 明示；是否整包接受 inst 11-11／11-12 可疑值；是否授權客戶端手動 workflow_dispatch（路徑 C）；Cloud 手動 Reboot 後回報資料日。DPE-1／2、`I1144-WIRING-GATE`、DG-SCOPE／DG-COV、DEC-177 Q1～Q7 等與台股卡資料檔更新無直接關係者，維持原狀。

## 10. 客戶需回覆項與可複製回覆範本

> **請勿貼 Secrets、API Key、Token、密碼；截圖請遮蔽 NAS 網址與主機名。** 以下任一項沒回覆＝維持現狀（HOLD／不觸發）。

```
【最新交易日資料更新程序回覆】
1) DPE-4：〈選 B：僅 #1124 進放行評估，#1125／#1126 維持 HOLD（仍不是合併指令）／維持 A（全部 HOLD）〉
2) DPE-3／DG-LIC 與 DG-PIT 取捨：〈等條款確認再放行／明示承擔風險先放行（請寫明範圍）〉
3) inst 11-11、11-12 外資可疑值（−7.66、−6.85 億，NOT VERIFIED）隨 #1124 整包進 main：〈接受並標註 NOT VERIFIED／要求先查證再併入〉
4) DPE-5：我會在 AI 回報的 head（SHA：…）上自行 Close→Reopen 或 Update branch：〈同意／不同意〉
5) merge #1124：〈待 S3 審閱後，我會另行明示「同意合併 #1124（head SHA：…）」〉
6) 路徑 C（客戶端手動 workflow_dispatch update_macro_history）：〈不授權（預設）／授權，且我自行操作〉
7) 確認 DG-SCOPE／DG-COV／I1144-WIRING-GATE 對「僅台股資料檔更新」不適用：〈同意／不同意〉（AI 的解讀為 INFERENCE，客戶未明文）
8) Cloud 手動 Reboot 後我會回報：畫面頂部標示（FAKE／Real-data Preview）與台股卡「資料日」：…（截圖請遮蔽 NAS 網址／主機名）
```

## 11. 盲點與 NOT VERIFIED

- 11-12 能否在下一輪入帳不確定（11-10 為 T+1、11-11 為 T+2 才入帳，見 §2.1）；S0 決策規則見 §8。
- **全部單組**。未讀 GitHub 帳單頁、Actions 核准設定、branch protection（403）；secrets 是否有值；排程延遲與 concurrency pending 行為屬平台；本地 `origin/auto/*` 為 fetch 時點快照；11-13 排程是否已跑 NOT VERIFIED；Yahoo／FinMind 原始回應與外部行情未核對（價格、法人、融資真實性未驗證）；inst／margin 的 11-10 以後是否也有先空後補寫未查；11-12 twii 缺列原因未知；交易日曆 NOT VERIFIED；測試未執行；「DG-SCOPE／COV／WIRING 不阻擋」為依文件適用範圍的解讀，無客戶或文件明文；`tw_pmi.json` 內容寫入組未重讀。
- GitHub 端事實（PR 狀態、CI run id 與結論、Actions run 清單）＝**總管轉述**，本組未連網重取。
- **與素材不符或需說明之處**：(1) inst「最近 60 列中位數 |137|」→ 重算 |值| 中位數約 417（137 是有號中位數）；(2) 「9 月下旬後僅 11-05、11-10、11-11 有 volume」→ 精確為 09-23 之後；(3) yml 行號略有位移，本文以實查為準（Fetch 步驟 L59-70、Publish L72-120、`DRY_RUN` 判斷 L114）；(4) 素材「DEC-156 (d2)」本組無法定位對應條目，改引 DEC-156 A（L7957）；(5) 素材「INV §5.1 C」本組讀作 `DAILY_DATA_PR_PIT_CRON_INVESTIGATION_2026-11-12.md` §5.1 方案 C；(6) 「約台北 01:00 抓太早／Yahoo 間歇空缺」兩假說未區分。

## 12. 本文件不構成授權（逐條）

1. 不授權觸發任何抓取、bootstrap、回補或手動 workflow_dispatch。
2. 不授權合併、關閉、rebase #1124～#1126；不授權 DPE-4／DPE-5 任何選項。
3. **不解除 DG-LIC、DG-PIT、DG-COV、DG-SCOPE、`I1144-WIRING-GATE` 或其他 Gate／HOLD**。
4. 不授權修改 NAS／Proxy／Secrets、Branch Protection、GitHub Actions 設定、`app.py`／`app_ui2.py`、資料契約或 UI。
5. 不得被引用為「部署追蹤 main 最新提交」「Cloud 自動部署」「已 QA PASS」「資料已更新」。
