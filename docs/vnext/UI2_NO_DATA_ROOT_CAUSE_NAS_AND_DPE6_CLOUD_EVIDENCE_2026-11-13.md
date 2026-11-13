# New UI2「缺資料」根因與 NAS 路徑稽核、DPE-6 Cloud 證據補登 — 2026-11-13

> **性質**：證據文件（docs-only，新增單檔）。**不是決策來源**：決策只在 `docs/DECISIONS.md`（DEC-180）；本文件不新增第二份 SSOT。
> **基準**：`origin/main`＝`587e1944f546df142fb134578b3f64887b451026`（`git rev-parse` 實查）。文中 `file:line` 皆為 **2026-11-13、main `587e194` 時點**的行號快照，**會漂移**；引用時請重跑 `grep -n`。本地為淺層複製。
> **單組聲明**：寫入組單組撰寫，**未經非作者獨立 QA**（`CLAUDE.md` §-2 規則 6）；**不是 QA PASS，不是授權，不是法律意見**。QA 結果由總管於 PR 補記。
> **客戶授權出處**：DEC-180（唯讀稽核；**不施工正式接線**）。與 DEC-179（DPE-3＝D、DPE-6＝B）的關係見 DEC-180 (三)。

**TL;DR（5 行）**
1. **答客戶問題**：New UI2 不用 NAS＝設計並有 G2F 守衛強制，不是漏接；要更多真資料須走「資料發布」與「正式接線」兩個 Gate。
2. **「沒資料」最可能的直接原因**（INFERENCE，未實機驗）：預設 FAKE cold ＋ Real 僅接台股與位階 2 項 ＋ 位階狀態檔在 Cloud 不存在；資料落後 11-09 為次要，且不顯示成空白（11-17 起轉過期，屆時需重評）。
3. **四類原因分界**：資料未抓到（fetch 失敗）／資料尚未發布（main 落後 PR 分支）／尚未接線（UI2 沒接這欄）／部署版本未更新（NOT VERIFIED）——不得混為一談。
4. **全部待 Gate，本批不施工**：方案 A／B／C 皆為 RECOMMENDATION，未獲授權；不解除任何 Gate／HOLD。
5. **客戶可複製回覆範本在 §13**（排除 Secrets）。

## 0. 目的、禁止事項、證據方法

| 項 | 內容 |
|---|---|
| 目的 | 回答客戶問題「New UI2 抓不到資料，是否沒有使用 NAS 中繼站？請參考舊 UI 的方式」；補登 DPE-6 的客戶新資訊（分級）；提供最小資料流對照 |
| 本文件**做**了什麼 | 唯讀檢視 repo 內程式碼、文件、`.github/workflows`、`data_cache` 與 git 物件（含本地已有的 `origin/auto/data-*` 分支 ref） |
| 本文件**沒有**做 | **未連網**；**未執行任何 fetcher／streamlit／測試／腳本**；未探測任何外部 API；未回補資料；未動 NAS／Proxy／Secrets；未讀取任何 Secrets 值；**未修改 `app.py`／`app_ui2.py`** |
| 不宣稱 | 不宣稱 `DG-LIC`／`I1144-WIRING-GATE` 已解除；不宣稱部署追蹤 main 最新提交；不宣稱 Cloud 自動部署或不自動部署；不宣稱任何測試通過 |
| 證據方法 | 四組獨立唯讀稽核（舊 UI／NAS；New UI2 欄位；資料發布×parquet；假說 A–E 交叉）皆**單組**；總管另親驗 3 點：①UI2 四路徑（`src/ui2`、`src/services/ui2`、`shared/ui2_contract`、`app_ui2.py`）對網路／proxy／secrets 關鍵字 grep＝0 命中；②`src/ui2/shell/app.py:86-87` 預設 `FEED_FAKE`；③`.gitignore` 排除 `macro_state.json`／`risk_cap_state.json` 且 `git ls-files`＝0。**寫入組對本文件引用的每個 `file:line` 另行用 grep／sed 重核**；與稽核組回報不符處在 §14.2 如實列出 |
| 標籤 | **FACT**（可由 `file:line` 重現）／**INFERENCE**／**NOT VERIFIED** |

## 1. 客戶新資訊分級與 DPE-6 四欄位更新

**客戶訊息原文見 DEC-180 fence**（本文件不重抄）。三個級別不得混成同一級：

| 級別 | 內容 | 重現／限制 |
|---|---|---|
| **客戶陳述** | Cloud App 網址（子網域前綴 `fh2pfdgs2am…`，repo 內此前 0 命中，`git grep` 實查）；「部署更新需要手動 Reboot／重新部署」 | 客戶說的話；**不是** Cloud 設定頁實測 |
| **日誌觀測**（Cloud 啟動日誌；**原文不在 repo、經客戶訊息轉述；日期未給；無 commit SHA、無 repo owner**） | Repository＝`my-stock-dashboard`；Branch＝`main`；Main file＝`app_ui2.py`；Python 3.14.10；Streamlit 1.59.2 | 無法複驗日誌本身 |
| **NOT VERIFIED** | repo owner（可能 fork）；實際部署 commit；日誌日期；該 app 是否即客戶畫面所見 app；Cloud Secrets 是否配置 NAS；Cloud 是否自動部署；畫面實際版本 | 待客戶補件（§13） |

**一致性核對（FACT）**：`requirements.txt:60` 為 `streamlit>=1.56.0,<1.60.0`，1.59.2 在範圍內（只證明在範圍內）；`ARCHITECTURE.md:613` 記載「Streamlit Cloud · Python 3.14」、`STATE.md:3398` 記載「Streamlit Cloud 平台重啟潮（強制 Python 3.14）」，與日誌轉述的 3.14.10 方向一致；但 **`.python-version` 內容為 `3.12`、所有 `.github/workflows` 的 python-version 為 3.11**（逐檔 grep），CI 綠不證明 Cloud 3.14 行為；Cloud 是否採用 `.python-version` 無文件＝NOT VERIFIED。

**網址前綴（INFERENCE）**：repo 內多處記載舊前綴 `namd8rh9b8s…`（`STATE.md:663`、`HANDOFF_2026-08-15.md:51`、`docs/audit-2026-08/LIVE_VERIFY_AND_DECLUTTER.md:3`、`tests/test_t3_watchlist_message.py:28`、`docs/push_watchlist_signals.md:73`），與客戶本次的 `fh2pfdgs2am…` 不同。**很可能是兩個不同的 app**（舊 `app.py` 站 vs 新建 `app_ui2.py` Preview 站）；無平台證據。舊 app 現況 NOT VERIFIED；`APP_BASE_URL`（T3 推播深連結）現值未知。

**DPE-6 四欄位更新讀法**（針對「產生該日誌的那個 app」；**取代**前一批證據文件 `DPE3_TERMS_AND_DPE6_CLOUD_CONFIG_EVIDENCE_2026-11-13.md` §2.3 的「全部 NOT VERIFIED」讀法，該文件原文不改）：

| 欄位 | 更新後讀法 | 仍缺 |
|---|---|---|
| Repository | 客戶轉述日誌：`my-stock-dashboard` | owner（排除 fork） |
| Branch | 客戶轉述日誌：`main` | 日誌日期、部署 commit |
| Main file path | 客戶轉述日誌：`app_ui2.py`；至少存在一個此入口的 app | 是否另有 `app.py` 的 app |
| 部署觸發方式 | **客戶陳述**「需手動 Reboot」 | Cloud 設定頁證據（性質 iv）；陳述不等於機制實測 |

**結論**：repo 內仍**沒有**性質 iv（Cloud 設定頁）證據。**仍不得宣稱部署追蹤 main 最新提交；不得宣稱 Cloud 自動部署，也不得宣稱不自動部署。**

## 2. 五假說判定

| 假說 | 判定 | 證據（file:line，已重核） |
|---|---|---|
| **A. New UI2 預設為 FAKE Preview** | **FACT（程式碼層）** | `src/ui2/shell/app.py:86-87`（`KEY_FEED` 不在 session → `FEED_FAKE`）；預設場景 `src/services/ui2/preview_feed.py:14`（`DEFAULT_SCENARIO = SCENARIO_COLD`）；切換 selectbox 在 `?ui2_dev=1`（`app.py:59`、`:67`、`:100-101`；`app_ui2.py:1-8` docstring）；無環境變數／secrets／其他 query param 可切（稽核組結論）。每個新 session 回到 FAKE＝INFERENCE（ui2_ key 只在 session_state）。頂部標示：FAKE＝「示意資料（FAKE）」「非真實行情、持股或建議」（`shared/ui2_contract/text.py:62-63`）；Real＝「Real-data Preview（非正式 production default）」「僅台股與市場位階為真資料」（`text.py:67-68`）。**Cloud 實際畫面是否為 FAKE＝NOT VERIFIED**（需客戶看頂部標示） |
| **B. Real Feed 不連網，只讀已發布資料** | **FACT（UI2 呼叫路徑）** | `src/services/ui2/real_feed.py:104-109` `read_real_snapshot` 只呼叫 `_read_twii`／`_read_regime`／`_read_twii_kbar`（`:49`、`:71`）；前者讀 `data_cache/twii_ohlcv.parquet`＋`metadata.json`（經 `market_twii_view_service.get_twii_trend_view`），位階讀本機狀態檔（`allocation_service.get_macro_regime`→`macro_state_locker`）。寫入組重跑 grep `requests\|yfinance\|FinMind\|proxy_helper\|fetch_url\|nas_relay\|urlopen\|st.secrets\|getenv\|os.environ` 於 `src/ui2`、`src/services/ui2`、`shared/ui2_contract`、`app_ui2.py`（排除註解行）＝**0 命中**。守衛 `tests/test_ui2_guards.py:173-221`（G2F、`G2F_IMPORT_ALLOWLIST`）；測試 `tests/test_ui2_real_feed.py`（`no_network` fixture 約 `:631`、`test_default_feed_is_still_fake` `:664`），**測試是否 PASS＝NOT VERIFIED（未執行）**。限制：進程 import 鏈（`src/data/macro/__init__`、`src/services/__init__` 為 eager barrel）會載入 `proxy_helper`／`requests`，但 UI2 從不呼叫（INFERENCE：import 時無網路動作）。**UI2 不使用 NAS＝設計並有守衛強制，不是漏接配置** |
| **C. NAS 未配置或不通造成舊 UI 部分資料失敗** | **NOT VERIFIED** | repo 內所有「NAS 變數皆未設定」的 2026-11 紀錄（`UI2_RUNTIME_PREGATE_EVIDENCE_SUPPLEMENT_2026-11-11.md` §9.3 約 `:264-277`、DEC-168 等）描述的是 **AI 沙箱**，不是客戶 Cloud，**不可外推**。最後一筆 Cloud 側「NAS 狀態」紀錄在 2026-07-14（`STATE.md:2859-2873`；`:2953-2955` 為 07-13）雲端 proxy 對 FRED 回 403 且 `_block>=2` 降級 bug 已修＝Cloud 上 PROXY_URL 曾配置的間接證據；`:2953-2955` 使用者以診斷證明 NAS 正常、真因為 timeout；`:3893` 區分 Squid `PROXY_URL` 與 FastAPI `NAS_BASE_URL`，並記載使用者實際設的是 Squid `PROXY_URL`〔v18.443/444 時點〕）；其後 2026-08 的 Cloud 紀錄（`STATE.md:663` 實機驗收、`HANDOFF_2026-08-15.md`）未涉及 NAS 配置（寫入組 grep 兩處皆無 NAS／PROXY 配置內容）。距今約 4 個月。2026-11 `data_cache/metadata.json` 顯示 cron 取數 `last_error` 為 null（twii／finmind_inst／finmind_margin，寫入組以 `git show` 讀取）。即使 NAS 完全正常 UI2 也不呼叫它，故 C 與「UI2 空白」的因果無法由 repo 建立 |
| **D. 資料 PR HOLD 使 main 快取過期** | **分層** | ①「main 資料停在 2026-11-09」**FACT**：`data_cache/metadata.json` `updated_at`＝`2026-11-09T19:40:36Z`，twii_ohlcv／finmind_inst／finmind_margin `last_updated`＝2026-11-09；`sector_flow/metadata.json` `last_updated`＝2026-11-09（寫入組讀 `origin/main`）。②「較新資料在 PR 分支」**FACT**（本地 ref）：`origin/auto/data-macro-history`（`3cd3f52`）twii 到 11-11、inst／margin 到 11-12；`origin/auto/data-sector-flow`（`cf4739c`）sector_flow `last_updated`＝11-12；`origin/auto/data-macro-forward-test`（`1654ae6`）signals 觀測日 11-11＝稽核組回報，**寫入組未重核（無 pyarrow）**。③「PR 未併入是原因」**INFERENCE**（PR Check `action_required`／branch protection 回 403 NOT VERIFIED，見 `PRODUCTION_HEALTH_FIVE_AXIS_SNAPSHOT_2026-11-13.md` §2）。④「因此畫面完全沒資料」**不成立**（INFERENCE）：台股卡讀 main 的 11-09，距今 4 天 ≤ `STALE_DAYS_DAILY`＝7（時點註記：僅 2026-11-13 成立；2026-11-17 起 age_days＝8 將轉為過期；UI2 實際 as_of 來自 parquet 最後一列〔未直接讀，沙箱無 pyarrow〕，此處用 metadata 自陳值）（`shared/staleness.py:135`；`src/data/macro/macro_cache_reader.py:196-201` 以 `age_days > 門檻` 判過期）→ `is_stale=False`，卡片只顯示「資料日」微標（`src/ui2/components/html.py:99-101`；映射 `src/services/ui2/real_canonical.py:385-405`），**不出現過期警示**。另有 `shared/freshness_policy` 的 `DAILY_MAX_LAG_TRADING_DAYS=3` 另一套門檻，UI2 卡片走哪套未逐條追到（NOT VERIFIED）。`finmind_m1m2`（`datasets.finmind_m1m2.fetch_outcome`＝`NO_NEW_DATA`〔請求窗口內無新月份，非連線／抓取失敗〕，`last_updated` 2026-09-01，`last_error`「抓取結果為空」）與 `tw_pmi`（`fetch_outcome`＝`UNDETERMINED`〔最近一次抓取結果無法判定：無新資料或 parser 略過，`fetch_evidence` 寫「parser 略過列數無從核對」；定義見 `shared/upstream_state.py:37`；故不歸入「資料未抓到」，也不確認為「資料已是最新」〕，`last_updated` 2026-10-01，`last_error`「抓取結果為空」），PR 分支也沒改善，**非 PR HOLD 造成** |
| **E. Cloud 未重新部署造成畫面版本落後** | **NOT VERIFIED** | repo 無 deploy／webhook workflow（`.github/workflows` grep）；UI2 畫面無 commit／build／版本字串（grep `GIT_SHA\|commit_sha\|APP_VERSION\|__version__\|build_id` 於 `src/ui2`、`shared/ui2_contract`、`app_ui2.py`＝0 命中），唯一可辨識依據是卡片「資料日」與間接版面線索。**使用者與稽核者都無法從畫面分辨「舊部署」與「新部署但資料舊」**。客戶陳述需手動 Reboot，與 `HANDOFF_2026-08-15.md:32-33`（舊文件）方向一致，但仍是陳述 |

## 3. NAS 實際位置（**只列名稱，無任何值**）

### 3.1 舊 UI（`app.py` 一族）

| 位置 | 內容 |
|---|---|
| ① NAS Squid 正向代理（家用台灣 IP） | repo 內**無 server 碼**。client 在 L1 `src/data/proxy/proxy_helper.py`；使用者：`fetch_url`（第一步）、`yf_proxy._proxy_env`（寫 env 給 yfinance；`etf_fetch.py:49` import）、`tw_stock_data_fetcher.build_proxy_session`（`:133`）、`macro_snapshot._make_proxy_session`（`:141`） |
| ② NAS FastAPI 中繼站 | server＝`src/data/proxy/nas_server.py`（部署於 NAS，不在 Cloud；讀環境變數 `NAS_API_KEY`，`:54`）；client＝`proxy_helper.nas_relay_fetch`（`:326`），為 `fetch_url` 的**最後手段**（`proxy_helper.py:290-304`）；`etf_fetch.py:107/121` 與 `news_fetcher.py:215` 另優先呼叫它。未設 `NAS_BASE_URL` 時回 None＝等同沒有 |
| 設定名稱（三套解析器，集合不一致） | `proxy_helper.get_proxy_config`（`:70-113`）：`PROXY_URL`／`NAS_PROXY_URL`／`[proxy]` 表／`HTTP_PROXY`；`tw_stock_data_fetcher._load_proxy_config`（def 於 `:100`）：`PROXY_URL`→`PROXY_HOST`／`PROXY_PORT`／`PROXY_USER`／`PROXY_PASS`（含 2 秒 TCP 探測、結果快取 60 秒，稽核組回報）；`proxy_helper.get_nas_relay`（`:307-323`）：`NAS_BASE_URL`（或 `NAS_RELAY_URL`）、`NAS_API_KEY`。`app.py:547-551` 側欄燈號看 `PROXY_HOST`，否則看 `PROXY_URL` |
| Cloud 側設定樣板 | `.streamlit/secrets.toml.example` 只列 `PROXY_URL`（含範例形式，本文件不重抄），**未列 `NAS_BASE_URL`**；`SPEC.md:376` 文字說明需設 `NAS_BASE_URL`＋`NAS_API_KEY`。**Cloud Secrets 實際內容 repo 讀不到＝NOT VERIFIED** |
| 舊 UI 診斷入口 | `app.py` 側欄燈號；工具箱→資料診斷→進階診斷→「🛰️ 測試 NAS 代理 + 成分股」按鈕（`src/ui/pages/health_inspector.py:419`；稽核組稱會在畫面印出 NAS 中繼站 base URL 原文——**截圖前須遮蔽**，見 P8） |

### 3.2 GitHub Actions 注入的 secret **名稱**（寫入組逐檔 grep `secrets.<NAME>`；GitHub 端是否有值 NOT VERIFIED；全部 workflow Python 3.11）

| 注入組合 | workflow |
|---|---|
| `PROXY_URL`＋`NAS_BASE_URL`＋`NAS_API_KEY` | `probe_tw_sources`、`push_weekly_report`、`risk_cap_history_poc`、`update_forward_test`、`update_macro_forward_test`、`update_macro_history`、`update_sector_flow` |
| 只 `PROXY_URL` | `export_db`、`recalibrate_macro`、`update_etf_managers` |
| 皆無 | `calibrate_health_weights`、`pr-check`、`probe_finmind_monthrev`、`push_daily_signals`、`push_holdings_daily`、`push_watchlist_signals`、`risk_cap_wif_negative_r5`、`update_fundamentals`、`update_health_history` |

### 3.3 New UI2：**無 NAS 位置**

NAS 只存在於 **L1 取數端**（舊 UI runtime）與 **cron 產生資料端**（§3.2）；UI2 只讀 cron 發布到 main 的 `data_cache` 與本機狀態檔。

## 4. UI2 欄位接線表（Real 軸）

| 類別 | 欄位 | 狀態 | 依據 |
|---|---|---|---|
| **REAL（僅三事實）** | 📊 台股加權卡；20 根日 K 主圖；市場位階（📊 市場目前狀態＋🎯 市場位階 context／查一檔「市場環境」，同一次 RegimeFact） | 已接線 | `real_feed.py:104-109`、`real_canonical.py` |
| 位階（Cloud 預期） | 位階狀態 | **INFERENCE：恆為灰「⬜ 尚未載入」**——`BREADTH_PROXY_SCORING_ENABLED=False`（`shared/signal_thresholds.py:277`）；UI2 目錄無寫入 `warroom_summary` 者（`real_feed.py:11` 僅描述讀取）；`macro_state.json`／`risk_cap_state.json` 被 `.gitignore:22`、`:25` 排除、`git ls-files`＝0，**全新 Cloud 部署不存在**（`ISSUE1110_DATA_AVAILABILITY_MATRIX_2026-11-10.md` §2；BACKLOG `NUI2-PREVIEW-CLOUD-STATE-FILES`〔BACKLOG.md:1410，open 未驗〕）；Cloud CWD／檔案實況 NOT VERIFIED |
| Risk Cap | 恆「⬜ 無法判定」 | `real_canonical.py:493-497`（`_risk_cap_row`） |
| **NP「⬜ 尚未提供」** | VIX／US10Y／利差／DXY／PMI 五卡；今日結論／風險；OneBrain；為什麼／指標明細／原始資料表；精選摘要／產業 Top5／候選／選股條件；基本面／估值／籌碼；趨勢／產業；搜尋／查詢 CTA／加入觀察；💼 組合狀態／持股／曝險；👤 帳戶／Sheet／設定／Digest／Rule Registry；🗂 資料頁（固定空殼，無任何來源狀態與資料日） | 未接線（稽核組結論） | — |
| 不在 VM／畫面 | 資金與籌碼（融資、板塊、外資、三大法人） | 未接線 | `src/services/sector_flow_fact_service.py`、`margin_fact_service.py` 在 `src`／`app`／`scripts` 無 import caller，只有 `tests/` 與 `shared/sector_flow_fact_thresholds.py` 的 docstring 提及其名稱（寫入組 grep）；`finmind_inst` 在 UI2 無 reader |
| 未實作 | 「資料新鮮度總覽」 | grep 無 `.py` 命中；決策單 Q1～Q7 待客戶（DEC-177） |
| 守衛 | `WIRED_PATHS` | 鎖定「只有已接線欄位可帶資料」（`tests/test_ui2_real_feed.py`） |

**畫面狀態可區分性**：資料未取得（灰「⬜ 資料未取得」／「資料格式異常」紅）、尚未提供（「此項目／功能尚未開放」）、位階尚未載入（灰＋「尚缺正式的市場廣度（漲跌家數）資料」）、FAKE（頂部標示）——彼此**可區分**；**「部署版本未更新」完全不可區分**（見 §2 E）。

**FAKE cold 的文案／互動語意缺口（INFERENCE，屬 UI 文案 Gate，非本批可改）**：FAKE cold 時非 fixed 卡片與「市場目前狀態」顯示「⬜ 尚未載入」，理由句預設為「按 🚀 更新後載入（FAKE 示意）」（`src/services/ui2/scenarios.py:289`、`:296`、`:310`、`:340`）；但主 CTA 在 VM 固定 `enabled=False`（`src/services/ui2/vm_common.py:181`），disabled 理由預設「此功能尚未開放」（`:182`）。**理由句叫人按更新、更新鍵卻永遠 disabled**，容易被讀成「資料抓不到」。

## 5. 資料發布 × parquet

| 產物 | 產生者／排程 | 發布方式 | main 資料日 | PR 分支資料日 | 讀者 |
|---|---|---|---|---|---|
| `twii_ohlcv`／`finmind_inst`／`finmind_margin`／`finmind_m1m2`／`tw_pmi`／`metadata.json` | `scripts/update_macro_history.py`（Yahoo `^TWII` chart API，`:207`，經 `proxy_helper`；FinMind `TaiwanStockTotalInstitutionalInvestors`／`TaiwanStockTotalMarginPurchaseShortSale`）；`.github/workflows/update_macro_history.yml:20` cron `0 9 * * *`（UTC） | `scripts/publish_data_pr.py --job macro-history`→分支 `auto/data-macro-history`→**PR #1124**（不直推 main；`publish_data_pr.py:119` `BRANCH_PREFIX`） | 2026-11-09 | twii 11-11；inst／margin 11-12 | UI2 讀 twii；舊 UI 讀 `macro_cache_reader`／`macro_v2_service`／`market_strategy`；`finmind_inst` UI2 未讀 |
| `sector_flow/*` | `scripts/update_sector_flow.py`；`update_sector_flow.yml:24` cron `30 9 * * *` | `auto/data-sector-flow`→**#1125** | 2026-11-09 | 2026-11-12 | `src/data/sector_flow/reader.py`；UI2 無 |
| `macro_forward_test/signals.parquet` | `scripts/update_macro_forward_test.py`；`update_macro_forward_test.yml:34` cron `40 9 * * 1-5` | `auto/data-macro-forward-test`→**#1126** | 觀測日約 11-03／04（啟發式，稽核組） | 觀測日 11-11（稽核組） | UI 讀者未見（NOT VERIFIED）；本欄兩項寫入組**未重核（無 pyarrow）** |
| `forward_test/picks.parquet`、`fundamentals/*` | `update_forward_test.yml`、`update_fundamentals.yml` 的裸 `git push` | 直接 push（是否被 branch protection 擋 NOT VERIFIED） | 最近落地 2026-11-02／2026-09-18（稽核組） | 不在 #1124～#1126 | — |

三個 PR head（本地 ref，`git for-each-ref` 實查）：`1654ae6`（forward-test）、`3cd3f52`（macro-history）、`cf4739c`（sector-flow）；base `85c65df`。**PR 當前狀態以 GitHub 為準**（總管 2026-11-13 查：仍 open，#1164 draft；本組未重取）。cron 宣告 UTC 09:00／09:30／09:40，但三分支 head commit 時間約 UTC 17:29–17:45（`git log -1` 實查，差約 8 小時，原因未驗）。資料日為 `metadata.json` 自陳值，parquet 最後一列日期未直接讀。

## 6. 最小資料流對照表

來源 → NAS／Proxy → L1 → L3 → 快取／資料契約 → New UI2 → 畫面

| 資料 | 來源 | NAS／Proxy | L1 | L3 | 快取／資料契約 | New UI2 | 畫面 |
|---|---|---|---|---|---|---|---|
| 台股加權 | Yahoo `^TWII`（T2） | **僅 cron**：`fetch_url`→Squid→直連→NAS 中繼；Cloud runtime 不碰 | `update_macro_history.py`（producer）；`macro_cache_reader`（讀） | `market_twii_view_service.get_twii_trend_view` | `data_cache/twii_ohlcv.parquet`＋`metadata.json`（main 11-09；PR 11-11） | `real_feed._read_twii`／`_read_twii_kbar`→`real_canonical` | 需切 Real 才見；顯示「資料日」，4 天未超 7 天門檻故不標過期（時點註記：僅 2026-11-13 成立；2026-11-17 起 age_days＝8 將轉為過期；UI2 實際 as_of 來自 parquet 最後一列〔未直接讀，沙箱無 pyarrow〕，此處用 metadata 自陳值） |
| 市場位階 | 舊 UI warroom／`macro_state_locker` | 不經過 | `macro_state_locker`（讀本機 JSON） | `allocation_service.get_macro_regime` | `macro_state.json`／`risk_cap_state.json`（gitignore、不在 git） | `real_feed._read_regime` | Cloud 預期「⬜ 尚未載入」（INFERENCE） |
| 外資／融資／板塊 | FinMind／TWSE／TPEX | 僅 cron | `update_macro_history`／`update_sector_flow`（producer） | `*_fact_service` 存在但 UI2 0 caller | `data_cache` parquet（main 11-09；PR 11-12） | **未接線** | 無此區塊（資料頁空殼） |
| VIX／US10Y／DXY／PMI | Yahoo／FRED／data.gov.tw 等 | 舊 UI runtime 經 `fetch_url`；PMI 另有 durable fallback | `macro_snapshot`／`macro_core`／`tw_macro` | 無 UI2 adapter | VIX／US10Y／DXY 無落地檔；`tw_pmi` 停 10-01 | **未接線**（NP） | 「⬜ 尚未提供」 |
| 持股／帳戶 | Google Sheet／OAuth | 不經過 | `gsheet_portfolio` | — | — | FAKE／NP | 「需登入…尚未開放」 |

## 7. 舊 UI `fetch_url` 行為與繞過清單（輔助說明，供判讀「舊 UI 抓不到」）

`src/data/proxy/proxy_helper.py:186-304`（寫入組逐點對照原碼）：

| 行為 | 依據 |
|---|---|
| URL 快取 300 秒，只存 200 | `:186` docstring「API Storm Shield」；`:290-304` 回傳前 `_url_cache_put` |
| 407 立即結束，不進 NAS 中繼 | `:234-236`；docstring `:194` |
| 403 累計後降級；ProxyError／Timeout 各 sleep 2 秒重試 | 403 處理 `:237-241`；ProxyError／Timeout 重試 `:259-267` |
| **Timeout 不觸發降級直連** | `:264-267` 僅 sleep；降級條件見下 |
| 降級直連只在 `_proxy` 存在且 (`_perr>0` 或 `_block>=1`) | `:279`（`_block>=1` 為 v19.120 修，`:273-277` 註解） |
| 最後手段 `nas_relay_fetch`；全敗回 **None**（無 is_stale、無 token、不 raise） | `:290-304` |
| `:245` 任何 200 皆印「已透過 Synology NAS 成功抓取」（即使直連）→ **該 log 不能當「有走 NAS」證據** | `:245` |
| 200＋錯誤頁會快取 300 秒（不驗 body）；失敗不快取 | 稽核組結論 |

**舊 UI 繞過 `proxy_helper` 的取數鏈**（單組 grep，可能漏；寫入組逐行確認存在）：`src/data/core/finmind_client.py:124`（`requests.get`）；`src/data/macro/leading_indicators.py:225`、`:561`（TAIFEX 裸 `requests.Session`）；`src/data/macro/macro_snapshot.py:514`（`yf.download`，稽核組稱沒套 `_proxy_env`）；`src/data/stock/mops_bulk_fetcher.py:141`；`src/data/stock/market_close_fetcher.py:298`。→ 舊 UI 的「抓不到」**不能一律歸因 NAS**。

## 8. 四類原因對照（不得混為一談；四類不互斥）

| # | 原因 | 判定 | 判讀依據 |
|---|---|---|---|
| ① 資料未抓到 | `metadata` `last_error` 非空／FETCH_FAILED | 目前台股三項 `last_error` 為 null（無此類問題）。`finmind_m1m2`＝`fetch_outcome` NO_NEW_DATA（請求窗口內無新月份）、`tw_pmi`＝UNDETERMINED（最近一次抓取結果無法判定：無新資料或 parser 略過，`fetch_evidence` 寫「parser 略過列數無從核對」；不確認為「資料已是最新」），**二者不放進本類**，也非 PR HOLD 造成 | `origin/main:data_cache/metadata.json` |
| ② 資料尚未發布 | main 11-09 落後 PR 分支 11-11／11-12 | **成立**（台股／外資／融資／板塊）；PR 未併入的原因為 INFERENCE | §2 D、§5 |
| ③ 尚未接線 | UI2 設計只接台股＋位階 | **成立，範圍最大，與 PR 無關** | §4 |
| ④ 部署版本未更新 | Cloud 跑舊 commit | **NOT VERIFIED**（畫面無版本標記） | §2 E |

另：預設 FAKE cold 本身也會呈現「尚未載入」（§4），與上列四類並行。

## 9. 對客戶問題「是否沒有使用 NAS 中繼站？」的答覆

New UI2 **沒有用 NAS，這是設計並有守衛（G2F）強制，不是漏接**；Cloud 上的 UI2 即使有配好 NAS 也不會用。要讓 UI2 顯示更多真資料，路徑不是「讓 UI2 走 NAS」，而是 **(1) 資料發布**（cron 用 NAS 抓→PR 併入 main），**(2) 正式接線**（L3 唯讀 adapter＋白名單），兩者皆是 Gate 項。畫面「沒資料」最可能的直接原因（INFERENCE，未實機驗）：預設 FAKE cold 的「尚未載入」＋Real 模式下絕大多數欄位尚未接線＋位階狀態檔在 Cloud 不存在；資料落後（11-09）是次要，且不會顯示成空白（11-17 起轉過期，屆時需重評）。

**哪些只需資料發布，哪些需要正式接線**：只需資料發布（併入 main）即可讓**既有接線的**台股卡資料日前進（11-09→11-11）；外資／融資／板塊／VIX／US10Y 等**需正式接線**（發布了也不會出現在 UI2）；位階需**狀態檔發布方式**（§11 A③）。

## 10. 版本可辨識性

UI2 畫面無 commit／build／版本字串（§2 E）。除非客戶回報頂部標示與台股資料日，無法判斷「Cloud 跑哪一版」。建議（RECOMMENDATION）加「版本＋資料日」小標，屬 UI 版面變更，**需先出線框草稿**（`CLAUDE.md` §-1.5.D §03-2 ①），本批不做。

## 11. 建議架構方案 A／B／C（**RECOMMENDATION，非裁示；全部未獲授權**）

原則：Data≠AI；UI runtime 不連網；NAS／Proxy 只留在 L1 producer 端（cron 發布）；每個新欄位走 producer→`data_cache`→L3 唯讀 adapter→`real_feed` 白名單→VM（含 as_of／is_stale／provenance／missing≠0）。

| 方案 | 做法 | 正確性 | 風險 | 速度 | Token／成本 |
|---|---|---|---|---|---|
| **A（總管推薦）** | 維持 UI2 無網路架構：①先解資料發布（DPE-1／2／4／5 的 Gate 處置，另案）②逐欄位走 WIRING-GATE 接線，已有 `*_fact_service` 者優先重用（外資／融資／板塊）③位階狀態檔改由 cron 發布到 `data_cache`（而非 gitignore 本機檔）④UI2 加「版本＋資料日」小標（需線框草稿 Gate）。**前置 Gate**：②外資／融資／板塊接線除 `I1144-WIRING-GATE` 外，另受 `DG-COV`／`DG-PIT`／`DG-LIC`／`DG-SCOPE` 阻塞（見 BACKLOG「Quality Batch 1 完成同步」段）；③位階狀態檔改由 cron 發布涉及新增發布流程＝「新增 API／cron／Secrets」類 HOLD，需另行裁示，且單獨**不保證**位階顯示——位階還需 session `warroom_summary` 來源（`real_feed.py:11`、ISSUE1110）且 `BREADTH_PROXY_SCORING_ENABLED=False`（`shared/signal_thresholds.py:277`；`real_canonical.py:303-305`），即使狀態檔發布，位階仍可能是灰「尚缺市場廣度」，需另案裁示 | 最高：無執行期外抓，缺值明示，可追溯 | 低：每步可逆、有守衛；但需多個客戶裁示 | 慢（受 Gate 限制） | 低～中 |
| B | 讓 UI2 Real Feed 在 Cloud 直接呼叫 L1 fetcher（走 `proxy_helper`／NAS） | 中：較即時，但失敗模式多（timeout、403、快取 200 錯誤頁） | **高**：違反 G2F 守衛與「UI 不抓資料」；NAS 配置未驗；牽涉 `DG-LIC`（公開呈現與自動化存取）。A 與 B 呈現的 TWSE／FinMind／Yahoo 資料同樣受 `DG-LIC` 約束（呈現與再散布面）；B 的額外問題是 Cloud 執行期自動化存取（Cloud 側可能被來源擋〔`STATE.md:2859-2873` 記載 2026-07-14 雲端 proxy 對 FRED 回 403〕、timeout 64 秒〔`ISSUE1110_DATA_AVAILABILITY_MATRIX_2026-11-10.md` 的 `fetch_url` 順序段〕、200 錯誤頁被快取 300 秒）與需放寬 G2F 守衛（放寬 allowlist 屬禁區） | 快但需放寬守衛 | 中～高 |
| C | 只改文案／標示（FAKE cold 理由句與 CTA、加部署版本標）不接新資料 | 中：解決「看起來像抓不到」的誤導，不增加資料 | 低；但屬 UI 文案／版面 Gate，需草稿 | 快 | 低 |

**AI 總管推薦 A（C 的版本標與文案修正可併入 A 的草稿）。B 與 `DG-LIC`、G2F 守衛有衝突，不建議。** A／B／C 皆為 RECOMMENDATION，**客戶未授權任何一項**。

## 12. 尚待客戶裁示的 Gate（本批不授權、不施工）

| Gate | 內容 |
|---|---|
| `DG-LIC` | TWSE／TPEX／FinMind／Yahoo 呈現與自動化存取條款；DPE-3＝D 進行中，**BLOCKED**（待條款原文／法務／網域放行） |
| `I1144-WIRING-GATE` | 逐欄位正式接線 |
| `DG-COV`／`DG-PIT`／`DG-SCOPE` | 外資／融資／板塊等資料接線的前置 Gate（與 `DG-LIC`、`I1144-WIRING-GATE` 並列阻塞，見 BACKLOG「Quality Batch 1 完成同步」段） |
| DPE-1／2／4／5 | 三個資料 PR 的證據、處置、`ui2-browser-gate` 執行路徑——**不得自行推進、不得 merge #1124～#1126** |
| UI 草稿 Gate | FAKE cold 理由句與 disabled CTA 文案／互動語意；UI2 版本＋資料日標示；🗂 資料新鮮度總覽 Q1～Q7（DEC-177）。**註**：純文字理由句不一定落在 `CLAUDE.md` §-1.5.D §03-2 ①；但「CTA enabled／disabled」互動語意變更涉及版面行為，保守起見走線框草稿 |
| 位階狀態檔發布方式（涉及新增發布流程＝「新增 API／cron／Secrets」類 HOLD） | 關聯 BACKLOG `NUI2-PREVIEW-CLOUD-STATE-FILES`；`ISSUE1110` §8 的「B 最小唯讀 adapter」類比（見 §14.2 說明） |
| 其他 | `DEC178-QB3-*` P3 候選仍未授權 |

## 13. 需客戶再提供的資訊（最小；**全部排除 Secrets／API Key／Token／密碼**）

> **請勿開啟或貼上 Secrets 分頁、API Key、Token、密碼；第 4 項只要「是／否」，不要貼任何值；截圖只截含下列欄位的部分，且須遮蔽 NAS 中繼站網址（若畫面有顯示）。**

```
【DPE-6 補件／UI2 缺資料稽核回覆】
（截圖前請遮蔽 NAS 網址／任何主機名；不要貼 Secrets、API Key、Token、密碼）
1) 打開該 Cloud 網址（不加 ?ui2_dev=1），頂部第一列寫的是：〈示意資料（FAKE）／Real-data Preview／其他：…〉
   （或截圖頂部＋台股卡；請寫台股卡上的「資料日」：…）
2) 啟動日誌的日期：…；Manage app 內可見的 repo owner（owner/repo）：…；部署 commit 前 7 碼（看得到才填）：…
3) 舊 app（網址前綴 namd8rh9b8s…）是否仍存在：〈是／否／不確定〉；若存在，Main file 是否 app.py：〈是／否／不確定〉
4) （選填，舊 UI 用）Cloud Secrets 內下列名稱是否「非空」，只填 是／否：
   PROXY_URL：〈是／否〉  NAS_PROXY_URL：〈是／否〉  PROXY_HOST：〈是／否〉
   NAS_BASE_URL：〈是／否〉  NAS_API_KEY：〈是／否〉
```

## 14. 盲點與 NOT VERIFIED

### 14.1 盲點（全部單組）

無 Cloud 側原文；未讀 Issue #1107／#1108 與 GitHub Deployments／Environments；本地為淺層複製；無 pyarrow，parquet 最後一列日期未直接讀；**未執行任何測試／程式（測試存在≠通過）**；UI2 卡片走哪套新鮮度門檻未逐條追；`sector_flow` reader 在 age=4 邊界的比較運算子（`>` 或 `>=`）未讀；「繞過 proxy_helper 清單」與「0 caller」為 grep 結論，可能漏；ETF／選股網逐檔 proxy 鏈只抽樣；TWSE／TPEX OpenAPI 是否擋海外 IP 在 repo 內互相矛盾（`market_close_fetcher.py:47-48` 稱「全球可達、免 proxy」vs `etf_tab_single.py:121` 稱「MoneyDJ／TWSE 封鎖海外資料中心 IP」，寫入組確認兩處字面相反，未判誰對）；`curl_cffi`／`yfinance` 是否吃 env proxy 未驗；Python 3.14 下 pyarrow／pandas 行為未驗（`requirements.txt:77-81` 有 cp314／pyarrow 註解，寫入組確認存在）。

### 14.2 核對時與稽核組回報不符（或需說明）之處

| 項 | 稽核組回報 | 寫入組核對 |
|---|---|---|
| `finmind_m1m2` 的狀態 | 「NO_NEW_DATA」 | 核對後**確認** `datasets.finmind_m1m2.fetch_outcome`＝`NO_NEW_DATA`（`last_updated` 2026-09-01、`last_error`「抓取結果為空」；`datasets.tw_pmi.fetch_outcome`＝`UNDETERMINED`）；先前「與素材不符」之說為誤讀欄位（metadata 無 `upstream_state` 這個 key，狀態欄位是 `fetch_outcome`）。稽核組回報正確 |
| `tw_stock_data_fetcher._load_proxy_config` 行號 | `:82-127` | `def` 於 `:100`（函式約 `:100-131`）；本文件只引 `:100` |
| 新鮮度「不出現過期警示」的行號 | `html.py:99-101、438-447`；`real_canonical.py` 約 385-405 | `html.py:99-101` 為「資料日」微標、`:438-447` 為 SPEC 行；判定過期的實際門檻在 `macro_cache_reader.py:196-201`，映射在 `real_canonical.py:385-405`；本文件並列引用 |
| `scenarios.py:296-298` | 理由句位置 | 理由句預設字串在 `:289`、`:310`、`:340`，`:296` 為使用處；本文件並列 |
| 「ISSUE1110 方案 B」 | 位階狀態檔發布方式關聯 ISSUE1110 方案 B | `ISSUE1110_…` §8 的「B 最小唯讀 adapter」原指 VIX／US10Y 等缺口項；套用到位階狀態檔是類比，並非該文件原文結論 |
| 「P2」編號 | 素材僅列 P1、P3～P9 | **定論**：P2＝本文件補的編號（稽核素材僅列 P1、P3–P9；繞過 `proxy_helper` 的取數鏈〔§7〕歸為 P2） |
| `etf_fetch.py` NAS 中繼呼叫 | `:121` | `:107` 為 import、`:121` 為呼叫（`_nasf(_url…)`），一致 |

### 14.3 其餘 NOT VERIFIED

Cloud 啟動日誌原文、日期、commit、owner；客戶畫面頂部標示與實際版本；Cloud 是否自動部署；Cloud Secrets 內容；GitHub 端 secret 是否有值；舊 app 現況；`APP_BASE_URL` 現值；PR 狀態（以 GitHub 為準）；`macro_forward_test` 觀測日（未重核）。

## 15. 舊 UI 觀察到的資料問題 P1–P9（**僅登記為 backlog 候選觀察；本批不修；不登為授權工作**）

| # | 觀察 | 依據 |
|---|---|---|
| P1 | 三套 proxy 設定解析器名稱集合不一致（`app.py:547-551` 側欄燈號看 `PROXY_HOST` 否則 `PROXY_URL`） | §3.1 |
| P2 | 多條取數鏈繞過 `proxy_helper`（本文件補的編號，見 §14.2） | §7 |
| P3 | `leading_indicators.py:53` 的 `_TWSE_S = _bps()` 於 import 時綁定 | 寫入組確認該行存在 |
| P4 | `yf_proxy._proxy_env` 無鎖（稽核組） | 未重核 |
| P5 | 失敗結果可能被 `st.cache_data` 快取 30 分（稽核組） | 未重核 |
| P6 | `fetch_url` 的成功 log 誤導（`:245`） | §7 |
| P7 | `src/compute/etf/etf_calc.py:419` 註解（「NAS_BASE_URL 缺→回 None」）過期（稽核組） | 寫入組確認該行註解存在，「過期」判斷未重核 |
| P8 | `health_inspector` 診斷印出 NAS host（稽核組） | §3.1 |
| P9 | CI／cron 3.11 vs Cloud 3.14.10 | §1 |

## 16. 本文件不構成授權（逐條）

1. 不授權任何正式接線、UI 施工、資料契約或 allowlist 變更；不授權方案 A／B／C 任何一項。
2. 不授權外部 API 探測、資料回補、對帳；不授權修改 NAS／Proxy／Secrets、`app.py`／`app_ui2.py`。
3. **不解除 `DG-LIC`、`I1144-WIRING-GATE` 或其他 Gate／HOLD**；不授權合併／關閉／rebase #1124～#1126。
4. 不授權 DPE-4／DPE-5；不授權施工 `DEC178-QB3-*`。
5. 不得被引用為「部署追蹤 main 最新提交」「Cloud 自動部署」「已 QA PASS」。
