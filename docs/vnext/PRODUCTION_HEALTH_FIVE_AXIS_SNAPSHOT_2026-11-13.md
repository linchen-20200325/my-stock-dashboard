# Quality Batch 2 ⑥：Production 健康度五軸 — 定義與唯讀快照 2026-11-13

> 📌 **這份文件是什麼、不是什麼（請先讀）**
> - **是快照文件**：DEC-178 Quality Batch 2 工作項 ⑥。定義「Production 健康」的五個軸、每軸的判讀規則，並附**一個時點**的唯讀實測。
> - **不是授權**：不解除任何 Gate／HOLD（`DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE`、`I1144-WIRING-GATE`、`DEC177` Q1～Q7、#1124～#1126、#1164、#1119 全部維持原狀）；不新增 API／cron／Secrets；不觸發 workflow；不寫入任何外部系統。
> - **不是 QA PASS**：單組撰寫（執行 AI），輸入為一份單組唯讀調查報告，撰寫者已重取關鍵事實（差異見 §7）；**尚未經非作者獨立 QA**。
> - **快照會漂移**：下列 MEASURED 只對「**2026-11-13 約 06:15 UTC（TW 約 14:15，收盤〔13:30〕後、官方盤後資料〔約 14:30〕尚未發布）、origin/main＝`25e1930d`**」成立。日後引用請重跑 §6 指令，不得直接引用本文數字。
> - **標註**：**FACT**＝本次讀檔／`git show`／`gh api` GET 直接確認；**MEASURED**＝FACT 且附時點／SHA／run id；**INFERENCE**＝由事實推論；**NOT VERIFIED**＝本沙箱無從查證。
> - **不得混讀的六組概念**：CI success ≠ Production success；抓取成功 ≠ 資料有效（空抓取不得讀成新鮮）；cron success ≠ 資料已進 main（發布 PR 未併入）；FAKE Preview ≠ 正式接線；workflow success ≠ 通知送達；沒有部署端證據一律 NOT VERIFIED。

## 0. 總表

| 軸 | 判定 | 一句話 |
|---|---|---|
| 1 CI | **OK（僅限 CI）** | main `25e1930d` 的 push run 與 5 個 check run 全 success；不代表 Production OK |
| 2 資料是否更新 | **FAIL（讀法 A：落後 4，超過上限 3）／邊界（讀法 B：落後 3，剛好在上限）；兩者共同事實＝發布 PR 未併入 main** | main 的 `data_cache` 停在 2026-11-09；cron 照跑且 success，但發布 PR #1124～#1126 仍 open；讀法 A／B 見 §3 日頻落後天數 |
| 3 資料是否有效 | **警示** | 3 個日頻 dataset 無 `last_error`；`finmind_m1m2`＝NO_NEW_DATA、`tw_pmi`＝UNDETERMINED（空抓取）；日頻已在 STALE 邊界 |
| 4 正式 UI 接線 | **OK＝「未接線」屬實；部署端 NOT VERIFIED** | `app.py` 對 ui2 引用 0；UI2 只在 `app_ui2.py` Preview |
| 5 決策與通知 | **警示；送達／Secrets NOT VERIFIED** | 持股推播 workflow success；其餘推播已停排程；Decision Digest 無非 digest 家族的 caller |

## 1. 軸 1：CI（對應 head SHA）

- **證據來源（唯讀）**：`gh api repos/linchen-20200325/my-stock-dashboard/commits/main/check-runs`；`gh api "repos/…/actions/workflows/pr-check.yml/runs?branch=main"`；`.github/workflows/pr-check.yml`。
- **判讀規則**：

| 判定 | 定義 |
|---|---|
| OK | **當前 head SHA** 的 push run 與全部 check run 為 success |
| FAIL | 當前 head 任一 check run 為 failure |
| 不算 success | 舊 head 的 success；action_required（**沒跑**）；cancelled 多半被新 commit 取代，需看後續 run |
| NOT VERIFIED | branch protection／required checks 清單（`gh api …/branches/main/protection` 回 403，本次重取確認） |

- **MEASURED（head `25e1930d`，2026-11-13 約 06:15 UTC 重取）**：

| 項目 | id | 結論 |
|---|---|---|
| main push run（`pr-check.yml`，建立 05:31:17Z） | 43372553225 | success |
| Fast checks (pytest unit, ~30s) | 131711471252 | success |
| Slow tests (AppTest, informational) | 131711471304 | success |
| ui2-browser（streamlit 1.56.0／1.59.2） | 131711471245／131711470905 | success／success |
| ui2-browser-gate | 131713268002 | success |

- **MEASURED（資料發布分支的 PR Check，9 輪全為未執行）**：`auto/data-*` 三條分支最近 3 輪 `pr-check.yml`（event=pull_request）**全部 `action_required`**。最新一輪：

| PR／分支 | head | run id | 建立 | 結論 |
|---|---|---|---|---|
| #1124 `auto/data-macro-history` | `3cd3f525` | 43270012637 | 11-12T17:29:41Z | action_required |
| #1125 `auto/data-sector-flow` | `cf4739c5` | 43272198487 | 11-12T17:42:07Z | action_required |
| #1126 `auto/data-macro-forward-test` | `1654ae60` | 43272716523 | 11-12T17:45:08Z | action_required |

  三個 PR 的 `mergeable_state` 皆為 `behind`（FACT）。action_required 是否構成併入條件，取決於 branch protection（`ui2-browser-gate` 是否 required 亦同），NOT VERIFIED。
- **本次判定：OK（僅限 CI）**。CI success 只證明程式與測試，不證明資料新鮮、UI 已部署或通知送達。

## 2. 軸 2：資料是否更新

- **證據來源（唯讀）**：`git show origin/main:data_cache/metadata.json`；`git show origin/main:data_cache/sector_flow/metadata.json`；`git show origin/auto/data-*:…`（先 `git fetch origin <branch>`）；`gh api "repos/…/actions/workflows/<wf>.yml/runs"`；`gh api repos/…/pulls/{1124,1125,1126}`。
- **判讀規則**：

| 判定 | 定義 |
|---|---|
| OK | **main** 的 `last_updated` 不落後「預期最新交易日」超過 `shared/freshness_policy.DAILY_MAX_LAG_TRADING_DAYS`＝3（客戶 2026-10-14 Q-z37=A） |
| STALE | 落後超過 3 個交易日 |
| FAIL | cron 最近 run 為 failure，**或**資料已 STALE 且原因為發布未併入 |
| cron success | 只代表 job 沒報錯；**資料進 main 才算更新** |

- **MEASURED 1：dataset `last_updated`（main＝`25e1930d`；分支為 fetch 時的 tip）**

| dataset | main | `auto/data-macro-history` `3cd3f525` | `auto/data-sector-flow` `cf4739c5` | `auto/data-macro-forward-test` `1654ae60` |
|---|---|---|---|---|
| twii_ohlcv | 2026-11-09 | 2026-11-11 | 2026-11-09 | 2026-11-09 |
| finmind_inst／finmind_margin（兩列值相同） | 2026-11-09 | 2026-11-12 | 2026-11-09 | 2026-11-09 |
| sector_flow（`sector_flow/metadata.json`） | 2026-11-09（`per_day` 僅 20261109） | — | 2026-11-12（`per_day` 含 20261110／11／12） | — |
| finmind_m1m2 | 2026-09-01 | 2026-09-01 | 2026-09-01 | 2026-09-01 |
| tw_pmi | 2026-10-01 | 2026-10-01 | 2026-10-01 | 2026-10-01 |

  main 的 `metadata.json` `updated_at`＝2026-11-09T19:40:36Z；`sector_flow/metadata.json` `updated_at`＝2026-11-09T19:57:52Z。`macro_forward_test` 分支只改 `signals.parquet`（`git diff --stat` 對 merge-base `85c65dfc`）。
- **MEASURED 2：資料 cron 最近一輪（皆 event=schedule、head_branch=main；checkout SHA 只有前三列〔update_macro_history／update_sector_flow／update_macro_forward_test〕同為 `85c65dfc`，其餘各列不同：export_db `63da9515`、update_forward_test `acd1648c`、update_fundamentals `c07ae468`、update_etf_managers `1f3c4895`、recalibrate_macro `a9b327ef`；`gh api repos/…/actions/runs/<id>` 的 `head_sha` 親驗）**

| workflow | run id | 建立（UTC） | 結論 |
|---|---|---|---|
| update_macro_history | 43269793901 | 11-12T17:28 | success |
| update_sector_flow | 43271978485 | 11-12T17:40 | success |
| update_macro_forward_test | 43272452189 | 11-12T17:43 | success |
| export_db | 43345750788 | 11-13T01:33 | success |
| update_forward_test（月頻）／update_fundamentals（季頻） | 41463933846／35335472538 | 11-02／09-18 | success／success |
| update_etf_managers | 42743389479 | 11-10T02:31 | **failure**（job 129589651938，步驟「Commit and Push Changes」） |
| recalibrate_macro | 36814252244 | 10-01 | **failure**（job 110215756849，步驟「Create PR for Review」；歷史紀錄） |

  `update_etf_managers` 修復 #1117（`aa69d99e`）已在 main，但其後尚無排程 run，**修復是否生效 NOT VERIFIED**。
- **MEASURED 3：發布 PR（`gh api repos/…/pulls/N`，2026-11-13 約 06:15 UTC）**

| PR | head ref（SHA） | base | state／merged | 建立 | 最近更新 |
|---|---|---|---|---|---|
| #1124 | `auto/data-macro-history`（`3cd3f525`） | main | open／false | 11-10T16:55Z | 11-12T17:29Z |
| #1125 | `auto/data-sector-flow`（`cf4739c5`） | main | open／false | 11-10T17:13Z | 11-12T17:42Z |
| #1126 | `auto/data-macro-forward-test`（`1654ae60`） | main | open／false | 11-10T17:17Z | 11-12T17:45Z |

- **「台股資料停在 2026-11-09」——只記 FACT／INFERENCE，不下處置**：
  - **FACT**：cron 沒停擺，11-10～11-12 皆有 success run（MEASURED 2）；發布路徑是推 `auto/data-*` 分支並開 PR，不 push main（`update_macro_history.yml` 第 32、78 行註解）。
  - **FACT**：#1124～#1126 仍 open；其分支 metadata 已前進（macro-history 到 11-11／11-12、sector-flow 到 11-12），main 未前進。
  - **INFERENCE**：main 停在 11-09 的直接原因是資料 PR 未併入 main。PR Check 為 action_required 是否卡住併入，NOT VERIFIED（branch protection 403）。
  - **FACT（觀察，不解釋）**：macro-history 分支上 `twii_ohlcv` 為 11-11，而 `finmind_inst`／`finmind_margin` 為 11-12；原因未查，NOT VERIFIED。
  - **處置待客戶裁示**：本文件**不建議** merge／close／rebase #1124～#1126，亦不建議任何外部對帳。決策節點為 DPE-3（外部對帳是否牽涉資料來源使用條款）、DPE-6（Streamlit Cloud 追蹤分支確認）、DPE-7（其他直推 main 的 workflow，下次排程 11-21）。已親驗存在於 `docs/BACKLOG.md`：`DEC176-DATA-PR-EVIDENCE-DECISIONS`、`DEC174-DATA-PR-1124-1126-DISPOSITION`、`DEC176-DPE7-1119-CHECKPOINT`；決策內容見 `docs/vnext/DAILY_DATA_PR_EVIDENCE_GAPS_AND_DECISION_ORDER_2026-11-12.md`。沒答覆＝維持 HOLD。
- **本次判定：FAIL（讀法 A：以 11-13 為評估日、落後 4 個交易日，超過上限 3）／邊界（讀法 B：以 11-12 為預期最新日、落後 3，剛好在上限）；兩者共同事實＝發布 PR #1124～#1126 未併入 main**（兩種讀法差在評估日取哪天，詳見 §3；無休市日曆故不擇一）。這是「資料沒進 main」的判定，不是「cron 壞了」。

## 3. 軸 3：資料是否有效（有效 ≠ 抓取成功）

- **證據來源（唯讀）**：`shared/freshness_policy.py`（`FreshnessStatus`：fresh／stale／missing／undetermined）；`shared/staleness.py`；`shared/fetch_outcome.py`（NO_NEW_DATA／FETCH_FAILED／UNDETERMINED）；`data_cache/metadata.json` 的 `last_error`／`fetch_outcome`／`fetch_evidence`；`shared/schemas.py`（pandera，opt-in）。
- **判讀規則**：

| 判定 | 定義 |
|---|---|
| OK | `last_error` 為 null、日期未超過 `DAILY_MAX_LAG_TRADING_DAYS`、欄位通過 schema 與不變量 |
| STALE | 日期超過上限 |
| NO_NEW_DATA | 已解析、已 sanity，窗口內無新資料；月頻在發布延遲內屬正常，可信度高於 UNDETERMINED |
| UNDETERMINED／FETCH_FAILED | **不得當有效**；空抓取不得被讀成「資料新鮮」 |
| NOT VERIFIED | pandera 在 production 路徑是否實際擋過資料；parquet 實際最大日期（本沙箱無 pyarrow） |

- **MEASURED（`origin/main:data_cache/metadata.json`，metadata 時點 2026-11-09）**：

| dataset | last_updated | row_count | last_error | fetch_outcome／evidence |
|---|---|---|---|---|
| twii_ohlcv | 2026-11-09 | 4913 | null | （無欄位） |
| finmind_inst | 2026-11-09 | 4939 | null | （無欄位） |
| finmind_margin | 2026-11-09 | 4939 | null | （無欄位） |
| finmind_m1m2 | 2026-09-01 | 239 | 抓取結果為空 | NO_NEW_DATA；「CBC EF15M01: 解析與 sanity 通過,請求窗口內無新月份」 |
| tw_pmi | 2026-10-01 | 172 | 抓取結果為空 | UNDETERMINED；「data.gov.tw 6100: CSV 解析出歷史列,窗口內 0 列,但 parser 略過列數無從核對」 |

- **MEASURED（用 repo 自己的工具，`assess_daily(as_of=2026-11-09, calendar=None)`）**：`today=2026-11-12` → FRESH，落後「至多 3」；`today=2026-11-13` → **UNDETERMINED**，「休市表取不到，落後 0～4 個交易日，上限 3」。`count_weekdays_after(2026-11-09, 2026-11-13)`＝4。
- **日頻落後天數＝自推，未接 TWSE 休市日曆**：沙箱取不到 TWSE 休市表，`calendar=None`。若 11-10～11-13 皆為交易日，以 11-13 為評估日落後 4 個交易日（> 3，會是 STALE）；若把「11-13 官方盤後資料（約 14:30）在快照時點（TW 約 14:15）尚未發布」納入考量、以 11-12 為預期最新日，則落後 3，剛好壓在邊界。**這兩種讀法的差別在於評估日取哪天，不是資料有變**；`freshness_policy` 本身沒有盤中／盤後概念。
- **INFERENCE**：`finmind_m1m2` 停在 09-01 需對照 CBC M1B／M2「月後約 27 天才上架」（`CLAUDE.md` §2.3，2026-09-28 更正；程式端 SSOT `shared/staleness.MACRO_PUBLICATION_LAG_DAYS["m1b_m2"]`）判讀，不能單看日期；`tw_pmi` 的 UNDETERMINED 表示「窗口內 0 列」是否真為無新資料**無從核對**。
- **本次判定：警示**。三個日頻資料沒有錯誤紀錄但已在 STALE 邊界；`tw_pmi` 有效性未決；`m1m2` 為已核對的 NO_NEW_DATA。

## 4. 軸 4：正式 UI 是否真正接線

- **證據來源（唯讀）**：`git grep -c ui2 origin/main -- app.py`；`app_ui2.py`；`src/services/ui2/data_page.py`；`src/services/ui2/real_feed.py`；`tests/test_ui2_registration_and_boot.py::test_production_app_does_not_reference_ui2`。
- **判讀規則**：

| 判定 | 定義 |
|---|---|
| OK（已接線） | 正式入口 `app.py` 確實 import 並呈現該 UI，**且有部署端證據** |
| 未接線 | 正式入口無引用；Preview 或 REAL feed **都不算**正式。Streamlit Cloud 實際分支／入口檔／版本／是否在線＝NOT VERIFIED |

- **MEASURED（origin/main `25e1930d`）**：
  - `git grep -c ui2 -- app.py`＝**無命中**（exit 1）。
  - `app_ui2.py:17`：`from src.ui2.shell import run`（獨立 Preview 入口）。
  - `R_DATA_NOT_WIRED`＝「資料健康度尚未開放；這裡不顯示任何來源狀態與資料日」，定義於 `src/services/ui2/data_page.py:12`，🗂 頁 3 個欄位（`data_state`、`src_health`、`data_asof`）都用它。
  - `real_feed.py` 的 `_read_*` 函式＝3 個（`_read_twii`、`_read_twii_kbar`、`_read_regime`），對外 `read_real_snapshot`。「REAL reader 數」在此指函式數；`real_canonical` 區塊數另計，未查。
  - `shared/`、`src/` 下 `freshness_overview` 字樣 0 命中；文件記載的正式 URL（`docs/push_watchlist_signals.md` 的 `APP_BASE_URL`）本次未連線，不可證當下在線。
- **本次判定**：「UI2 未接線」**屬實**（OK＝如實陳述）。**Streamlit Cloud 部署版本、追蹤分支、是否在線＝NOT VERIFIED**。

## 5. 軸 5：投資決策與通知是否可用

- **證據來源（唯讀）**：`git show origin/main:.github/workflows/push_*.yml` 的 `on:` 區塊；`gh api …/actions/workflows/push_*.yml/runs`；`scripts/push_watchlist_signals.py`；`tests/test_decision_digest_invariants_guard.py`（`ALLOWED_CALLERS`）；`git grep -l decision_digest_builder`。
- **判讀規則**：

| 判定 | 定義 |
|---|---|
| OK | workflow 最近 run success **且有送達證據**（收訊截圖／log 內 API 回應） |
| 警示 | workflow success 但無送達證據，或推播內容引用的資料已 STALE |
| 排程停用 | 「不會推」，**不是失敗** |
| NOT VERIFIED | LINE／Telegram 實際送達、Secrets 有效性 |

- **MEASURED（`on:` 區塊讀自 `origin/main`；最近 run 為 `gh api` GET）**：

| workflow | `on:` 現況 | 最近 run | 結論 |
|---|---|---|---|
| push_holdings_daily | schedule `30 22 * * 0-4` ＋ workflow_dispatch | 43354622083，11-13T02:47Z（job「Push holdings review」131653580831） | success |
| push_weekly_report | schedule `0 21 * * 0` ＋ workflow_dispatch | 42541029038，11-09T00:35Z | success |
| push_daily_signals／push_watchlist_signals | **只有 workflow_dispatch**（註解：排程已停用 user 2026-08-23） | 32467759881／32468140799，2026-08-21 | success／success（停排程前） |

- **`--health-check` 心跳**：腳本有該參數（`scripts/push_watchlist_signals.py` 第 97、188 行），原設計週一自動帶；但該 workflow 排程已停，**目前沒有任何排程中的 `--health-check` 心跳**。
- **Decision Digest**：`git grep -l decision_digest_builder origin/main -- src app.py app_ui2.py scripts shared`（親驗，origin/main＝`25e1930d`）實際命中**僅 1 檔**：`src/services/decision_digest_assembly.py`（digest 家族自身的組裝層；`app.py`、`app_ui2.py`、`scripts/`、`shared/` 命中 0）；`tests/test_decision_digest_invariants_guard.py:286` 的 `ALLOWED_CALLERS: frozenset = frozenset()`。**無非 digest 家族的 production caller**（其餘引用只在 `tests/`）；推播目前不經 Digest。
- **INFERENCE**：持股推播吃 main 上的資料（軸 2：停在 11-09）；訊息內是否標示資料日，**未讀 run log，NOT VERIFIED**。
- **本次判定：警示**。workflow success 只代表 job 沒報錯；LINE／Telegram 實際送達、Secrets 有效性＝**NOT VERIFIED**。

## 6. 最短重現指令清單（全唯讀；需 `gh` 已登入）

```
cd /home/user/my-stock-dashboard && date -u && git fetch origin main && git rev-parse origin/main
R=repos/linchen-20200325/my-stock-dashboard
gh api $R/commits/main/check-runs --jq '.check_runs[]|[.name,.id,.conclusion,.head_sha[0:8]]|@tsv'            # 軸1
for b in main auto/data-macro-history auto/data-sector-flow auto/data-macro-forward-test; do gh api "$R/actions/workflows/pr-check.yml/runs?branch=$b&per_page=1" --jq '.workflow_runs[]|[.id,.event,.head_sha[0:8],.conclusion]|@tsv'; done
git show origin/main:data_cache/metadata.json; git show origin/main:data_cache/sector_flow/metadata.json | head -12   # 軸2
git fetch origin auto/data-macro-history auto/data-sector-flow auto/data-macro-forward-test; git show origin/auto/data-macro-history:data_cache/metadata.json | head -30
for n in 1124 1125 1126; do gh api $R/pulls/$n --jq '[.number,.state,.merged,.head.sha[0:8],.mergeable_state]|@tsv'; done
for w in update_macro_history update_sector_flow update_macro_forward_test update_etf_managers export_db push_holdings_daily push_weekly_report; do gh api "$R/actions/workflows/$w.yml/runs?per_page=1" --jq '.workflow_runs[]|[.id,.event,.conclusion,.created_at]|@tsv'; done
python3 -c "import sys;sys.path.insert(0,'.');from datetime import date;from shared.freshness_policy import assess_daily;print(assess_daily(date(2026,11,9),today=date.today(),calendar=None))"   # 軸3
git grep -c ui2 origin/main -- app.py; git grep -n R_DATA_NOT_WIRED origin/main -- src                         # 軸4
for w in push_holdings_daily push_weekly_report push_daily_signals push_watchlist_signals; do git show origin/main:.github/workflows/$w.yml | sed -n '/^on:/,/^concurrency:/p' | head -8; done   # 軸5
git grep -l decision_digest_builder origin/main -- src app.py app_ui2.py scripts shared   # 預期僅 src/services/decision_digest_assembly.py
git grep -n "ALLOWED_CALLERS: frozenset" origin/main -- tests
```
- 注意：`gh pr view`／GraphQL 與 `…/branches/main/protection` 在此環境皆 403，一律用 REST。讀 main 請用 `git show origin/main:<path>`（本工作樹在 `ccr-6ca9d77e-90ji2g`，不是 main）。

## 7. 與調查報告的差異、未驗證與限制

- **差異**：(1) `auto/data-*` PR Check 的 run id 調查報告不完整，已刪除並以 §1 重取值取代（macro-forward-test＝43272716523）；(2) sector-flow 分支 `per_day` 報告記 20261110／11，本次重取為 **20261110／11／12**；(3) 日頻落後天數報告以 11-12 為預期最新日算 3，本次另用 `assess_daily` 跑 11-13 評估日得 UNDETERMINED（0～4），兩種讀法並陳於 §3，均為自推；(4) main 的 sector_flow 日期取自 `sector_flow/metadata.json`（不在主 `metadata.json` 內），值與報告一致；(5) 其餘 MEASURED 值（`last_updated`／`last_error`／`fetch_outcome`、run id 與結論、PR 狀態、ui2 引用、`R_DATA_NOT_WIRED`、`ALLOWED_CALLERS`）皆與報告一致。
- **工作樹**：本分支 HEAD 領先 origin/main（含尚未併入 main 的 Batch 2 ④⑤）；本文所有 MEASURED 一律以 `origin/main` 為準。
- **仍 NOT VERIFIED**：Streamlit Cloud 部署（追蹤分支、入口檔、在線）；Secrets 有效性；LINE／Telegram 實際送達；branch protection／required checks；`update_etf_managers` 修復 #1117 是否生效；TWSE 休市日曆；parquet 實際最大日期（無 pyarrow）；pandera 在 production 路徑是否實際擋過資料；推播訊息是否標示資料日；本文單組撰寫，未經非作者 QA。
