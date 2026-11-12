# PROJECT_STATE 歷史分冊（2026-11-12 搬入；⛔ 非 SSOT、非現行規則、非接手點）

> **來源**：`docs/PROJECT_STATE.md`（main `a2926c8e`，完整 SHA `a2926c8e3f9962119f9c3ffbcb0903bd1eb500b1`）原 L394–L422、L594–L621、L661–L676、L709–L717、L749–L773、L885–L901、L916–L928、L940–L957、L1110–L1124，共 14 節、9 個連續區段；**逐字、依原順序**以 `## ` 標題切節、行切片搬入，未改字、未重排、未摘要。**搬移日**：2026-11-12。**依據**：客戶 DEC-173 Q2「PROJECT_STATE 指定歷史段可分冊歸檔。但不得只留下空標題而遺失仍有效的知識；有效架構、限制、產品狀態及 Decision 關係必須留在可直接查閱的現行內容。」與 Q6（逐字搬至 repo 內正式歷史分冊、保留 Git 歷史與可還原路徑）。
> **定位**：本檔為歷史分冊，非 SSOT、非現行規則、非接手點；現行狀態與仍有效的專案知識以 `docs/PROJECT_STATE.md`（其餘各節）、`docs/DECISIONS.md`、`docs/BACKLOG.md`、`docs/HANDOFF.md` 與 GitHub 實況為準。文中「本節」「上文」「見 §NN」等相對指涉，一律指搬移前的 `docs/PROJECT_STATE.md`。
> **還原**：每節以 `PROJECT_STATE_HISTORY_SEGMENT` 註解夾住、標原行號；把該節 BEGIN 註解與其後一個空行之後、END 註解之前的行，依原行號順序串接，放回主檔對應 `PROJECT_STATE_HISTORY_INDEX` 區塊（BEGIN 至 END 及其後一個空行；區塊上標 `lines=` 原行號）的位置，即逐位元組還原；或 `git show a2926c8e:docs/PROJECT_STATE.md`。

<a id="ps-hist-28"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=394-422 -->

## 28. Data Health 批 A＋1' 實作完成（2026-10-23；~~待 PR 合併~~ 已合併 #910，merge `066f461e`（2026-10-24 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實更新）））

> 2026-10-23 新增。裁示全文只在 `docs/DECISIONS.md` DEC-074／DEC-075；殘留與延後項只在 BACKLOG 5.1.8；現況與唯一下一步只在 `docs/HANDOFF.md` §0。本節只摘要。量測：分支 `ccr-310717b7-37xwl6`，HEAD `04a9bc2e`（commits `1f4f5b19`、`7ef52869`、`ee4bde01`、`04a9bc2e`；base＝main `b9ed892d`）。~~**PR 尚未開、尚未合併**~~ **PR 已開、尚未合併**（PR #910）；~~QA 第四輪複驗中~~ QA-1～QA-5 獨立複驗，QA-5 判定可合併（見 PR #910）（QA-5 後補的 SHOULD-1 測試 commit 為實作組自跑、未經第二組驗證）；CI：合併條件：PR #910 CI 綠（結果見 PR checks）（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管）。

- **狀態**：~~**實作完成、待 PR #910 合併**~~ **已合併 #910（2026-10-24 squash，merge `066f461e`；最後產品碼 commit `9714d0b3`）**（2026-10-24 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。⛔ 合併＋main CI＋main verification 完成前不得寫成「已上線」（📌 2026-10-24：合併＋main CI＋main verification **已成立**（main `066f461e` PR Check run 39995254045 success；`649f739` run 39999485112 success；`PROJECT_RULES.md` 第 7 節）⇒ 可寫「已上線 main」（2026-10-24 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實更新）））；⛔ 總管確認前不得寫「QA 通過」。
- **批 A（DEC-074 B 落地＋DEC-075 D-1(a)＋`DH-TWII-MA200`）**：
  - L0 旗標 `BREADTH_PROXY_SCORING_ENABLED=False`（`shared/signal_thresholds`）：代理廣度（`fetch_adl` 由 ^TWII 估算、`jingqi_calc` 大盤估算）**只顯示、不計分**；健康分算不出 ⇒「⬜ 未評估」；**無新權重、無重新歸一化**（DEC-074）。
  - 健康分因缺正式 breadth 未評估時，市場位階 ⬜、`is_loaded=False`、**不退** `macro_state.json` 規則引擎位階 ~~；含 ^TWII 全滅情境（`04a9bc2e` 補）~~；~~**限 warroom 存在的路徑**（含該路徑下的 ^TWII 全滅情境，`04a9bc2e` 補）；**冷啟動／warroom 不存在路徑未完成（見 `DH-REGIME-NOWARROOM`）**~~ **代理廣度不計分時涵蓋 warroom 存在（含 ^TWII 全滅，`04a9bc2e`）與不存在（冷啟動未載入、warroom 被移除；PR #910 `DH-REGIME-NOWARROOM`）兩條路徑**（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（依兩組獨立調查裁定冷啟動屬 DEC-075 D-1(a) 射程；客戶 2026-10-23 指示不得只登 BACKLOG 延後））（⚠️ 實作組自述、待 QA 複驗（`CLAUDE.md` §-2 規則 6））（DEC-075 D-1(a)）（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（QA-4 M-1：D-1(a) 只完成 warroom 存在的路徑））。
  - `DH-TWII-MA200`：MA200 不足 200 根時回 None＋`ma200_status`，不再以現價頂替；`MA200_WINDOW_DAYS=200` 移入 L0（與 `config.ANNUAL_MA=240` 是不同量測，不合併）。
  - 總經前進式驗證：`ruleset_hash` 納入旗標、schema 2→3；**v2 列與 v3 列不可混比**（健康分口徑不同）。
- **批 1'**：外資（大盤）FinMind 備援缺值不再 `fillna(0)`；台灣出口燈改名「台灣出口金額 YoY（海關）」（不換源）；台灣 PMI 教學對映改 TW_PMI（歷史數字來自 `data_cache/tw_pmi.parquet`）；`XTEXVA01TWM664S` 教學文字依實際來源鏈 DGBAS → OECD via FRED → 海關 6053 更正；`SPEC.md`／`DATASTATION.md` 以刪除線＋DEC-075 註記同步。⛔ 未新增資料來源、未改投資公式（DEC-075 第 3 點）。
- **客戶可見行為變更**（在正式 breadth 來源出現前持續有效）：
  1. 📊 大盤／🛡️ 持股等處的**健康分、市場位階、建議持股姿態帶通常顯示「⬜ 未評估／資料不足」**（DEC-072「首屏先給結論」在資料不足時以 DEC-074／075 為準，客戶送題時已知情）。~~「通常」而非「一律」：warroom 不存在的路徑仍有殘留（見下）。~~ 「通常」而非「一律」：旗標開啟（代理計分）或日後接上正式廣度來源時不成立；warroom 不存在路徑的殘留已併入本 PR 修正（見下第 6 項）（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（依兩組獨立調查裁定冷啟動屬 DEC-075 D-1(a) 射程；客戶 2026-10-23 指示不得只登 BACKLOG 延後））。
  2. 🎯 找標的頁（`page_find`）**空頭濾網通常不套用**（位階未評估 ⇒ 不套用）；⚠️ 目前畫面**沒有**註記告知使用者（`DH-FIND-UNEVAL-NOTE`）。
  3. 總經前進式驗證帳本：**健康欄為 None**；`ruleset_hash` 與 schema（2→3）變更，前後列不可混比。
  4. 台灣出口燈名改為「台灣出口金額 YoY（海關）」（待客戶驗收，`DH-EXPORT-LABEL-READING`）；台灣 PMI 燈的教學與歷史數字改為台灣 PMI（不再是美國 ISM）。
  5. 外資備援缺值時顯示為缺值、不再顯示假的 0 淨額（主要在舊 UI；新 UI 畫面不變）。
  6. 📌 **冷啟動（`DH-REGIME-NOWARROOM`，PR #910；2026-10-23 新增，有意識的更新，決策者 AI 總管）**：開新 session、尚未按「🚀 更新今日戰情」時（或更新時紅綠燈三源全空、warroom 被移除時），**不再顯示**由規則引擎快照 `macro_state.json` 推出的多空位階 —— 改為灰色「總經尚未載入」，並同句說明「正式廣度來源接上前，載入後位階仍為未評估」。具體：🚦 今天頁卡①③、狀態列「總經」、三欄摘要「位階」為灰色未載入（不是紅色錯誤）；~~🛡️ 持股頁卡④ **不再印 `bull`／`bear`**（灰）；~~ 🛡️ 持股頁卡④ 不再印 `bull`／`bear`，顯示灰色「總經本輪未評估」（⚠️ **QA-6 發現**：`c8e30d84` 時這張卡在 v2 卡面實際畫成**紅卡**「這一格畫不出來」—— 短句表 `V2_SHORT_ROWS` 的摘錄對不上新原文 ⇒ KeyError；卡⑤「建議持股水位」缺真實廣度那一支同型（`f3dd098c` 起即有）。修正 commit 後 AppTest 實測（旗標關、有效空頭檔、按「🚀 跑存股戰情室」）卡④ 為灰（#7），實作組自述、待 QA-7）（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（QA-6 MUST-1／S-2））；換股建議攻守 stance 冷啟動為「未評估」（只做汰弱、不套攻守）；🎯 找標的頁冷啟動不套空頭濾網；AI 多因子評分冷啟動拒評、AI 問答「市場狀態」回未評估。**系統風險上限（Risk Cap）不受影響**（7 天有效快照照舊）。**舊 UI 連帶**（共用契約，舊 UI 程式碼未改；DEC-019 揭露）：`app.py` 選股網濾網、`section_batch_fetcher`／`section_portfolio_summary` 評分、`section_op_recommendation`、`section_psy_checklist`、`macro_stock_link`、`tab_macro_v2` 等在冷啟動同樣變 unknown／未評估（走各自既有的未評估處理）。旗標開啟時行為同修前。⚠️ 實作組自述、待 QA 複驗（`CLAUDE.md` §-2 規則 6）
  7. 📌 **QA-6 補揭露（S-4；2026-10-23 新增，有意識的更新，決策者 AI 總管；數字為 QA-6 量測轉述，實作組未重跑）**：冷啟動自 #910 起還有兩處**方向變化**（都走各自既有的未評估路徑，屬實，但修前沒寫出）：(a) 舊 UI `section_op_recommendation`（凍結，DEC-019）冷啟動＋有效**空頭**檔：修前印「大盤空頭格局…先控制風險」，修後「大盤」項不計分（附既有 caption），結論可能變成「2個訊號共振，中性偏多，可小倉試水溫」—— **建議方向由保守轉為偏積極**；(b) 換股建議：修前空頭檔冷啟動攻守 stance＝defensive、換入候選 **3 檔**；修後 stance＝unknown（只做汰弱、不套攻守）、換入候選 **5 檔**（既有 `_in_n = 3 if _defense else 5`）。另：AI 個股評分冷啟動被擋時的字串（`ai_qa_service._regime_blocked_error`）不再附「按一鍵更新…再問一次」，改為屬實句「可以按更新載入，但正式廣度來源接上前載入後位階仍為未評估」（QA-6 MUST-2 修正；旗標開時舊句照舊）。⚠️ 實作組自述、待 QA-7 複驗（`CLAUDE.md` §-2 規則 6）
- **附帶行為變更（QA-4 S-2 揭露；2026-10-23 補，有意識的更新，決策者 AI 總管；`04a9bc2e` commit 訊息只寫了第 3 項）**：
  1. 🛡️ 持股頁 ④ 總經位階／⑤ 建議持股水位：warroom **存在**、健康分缺、舊 `macro_state.json` 讀壞時，由紅（讀不出來）轉灰（缺真實廣度 ⇒ 未評估）。這兩卡在 warroom 存在時本不讀舊檔（位階不靠舊檔、上限只讀 `risk_cap_state.json`），原本的紅屬假警報（v3 §02）；warroom **不存在**時讀壞**仍紅**（未改）。
  2. 🚦 今天頁卡① 能不能出手、卡③ 市場位階：F1（三源全滅、warroom 仍存在）／F3（^TWII 全滅）由「按更新會原地重抓」（灰）改為「更新資料不會改變、等正式廣度來源」（灰）；兩卡過去就不是紅，沒有紅色被拿掉；本輪取數失敗仍在更新報告逐條列出。
  3. strict 模式：warroom 有、但健康分缺＋舊檔損毀時**不再 raise**（rvrc 關時改帶 `file_error`、rvrc 開時不帶）；warroom 不存在＋損毀**仍 raise**。
  4. 本 PR（QA-4 S-1 回修）：新 UI 廣度未評估說明（今天頁卡①③／狀態列「總經」／三欄摘要「位階」、持股頁④⑤、AI 問答「市場狀態」工具）依「本輪紅綠燈輸入有沒有被擋下的代理值」給「目前只有代理值」或「這一輪連代理值也沒有」；拿不到區分訊號處（`allocation_decision` drivers、訊號讀不出來）改用兩種情境都屬實的中性句；今天頁／持股頁的出口句改為兩態皆屬實。更新報告「整理紅綠燈結論」步驟說明：旗標關時 warroom 在而健康分缺，一律寫缺真實廣度句（不再寫「位階若有可用的 macro_state.json 會改讀它」）。只改文案與選擇邏輯：⛔ 未增刪 st 元件、未改版面／公式／權重／門檻／Risk Cap、未動凍結舊 UI。
- **已知殘留**（登記於 BACKLOG 5.1.8，⛔ 不在此重複細節）：~~`DH-REGIME-NOWARROOM`（D-1(a) 殘留：warroom 不存在路徑仍回規則引擎位階、`is_loaded=True`；**下一安全段落第一個動作**）~~ `DH-REGIME-NOWARROOM` 本 PR #910 修正（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（依兩組獨立調查裁定冷啟動屬 DEC-075 D-1(a) 射程；客戶 2026-10-23 指示不得只登 BACKLOG 延後））、`DH-STATUSBAR-AI-SNAPSHOT-WORDING`、`DH-NOWR-COPY-RESIDUAL`（2026-10-23 新增登記）、`DH-CALIB-CRON`（季度校準在新旗標下健康恆 None、自動 PR 本文「無需調整」有誤導；**期限 2027-01-01 前**）、~~`DH-BREADTH-COPY-NOPROXY`~~ `DH-BREADTH-COPY-NOPROXY`（新 UI 本 PR 修正；殘留僅凍結舊 UI 的 F3 擋燈文案，只登記不改）（2026-10-23 更新，有意識的更新，不是漏刪，決策者 AI 總管（QA-4 S-1））、`DH-FIND-UNEVAL-NOTE`、`DH-OLDUI-PROXY-LABELS`、`DH-NONE-TO-ZERO-RENDER`、`DH-FT-SCHEMA-ASOF`、`DH-MKTSCORE-DENOM`、`DH-EXPORT-LABEL-READING`、`DH-M1B-COVERAGE`、`DH-RISKCAP-OLDFILE-NONRVRC`、`DH-TEST-Z8-ALLOC-NARROW`（2026-10-23 QA-4 新增登記）、`DH-JINGQI-STALE-SESSION`、`DH-REFRESH-HEALTH-NAN`（2026-10-23 QA-5 新增登記）。批 2／VN1-PG：依 DEC-075 第 4 點待重評邊界，**未開始**。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本節實作內容與殘留為**總管轉述**；撰寫組只以 `git grep` 抽查 `BREADTH_PROXY_SCORING_ENABLED`、`MA200_WINDOW_DAYS`、`ma200_status`、新燈名、`shared/macro_forward_test_schema` 的「v2 列與 v3 列不可混比」註記存在，**未重跑任何測試**。本機測試 Python 3.13、CI Python 3.11，以 CI 結果為準。
- 📌 **2026-10-23 Freeze 補註（append-only，上文一字未改；有意識的更新，不是漏刪，決策者 AI 總管（事實更新））**：本節開頭量測行「HEAD `04a9bc2e`」已過時 —— PR #910 其後又有 `0122eec1`（治理文件）、`3003bb3c`（QA-4 S-1 文案）、`f3dd098c`（QA-5 SHOULD-1 測試＋佔位）、**`c8e30d84`（冷啟動修正 `DH-REGIME-NOWARROOM`，最後一個產品碼 commit）**，以及 Freeze 文件 commit（以 PR #910 最新 commit 為準）。**客戶可見**：冷啟動（未按「🚀 更新今日戰情」／三源全空／warroom 被移除）**不再顯示規則引擎（`macro_state.json`）推出的多空位階**，改灰色「總經尚未載入」；Risk Cap `exposure_limit_pct` 不變（見上第 6 項）。QA-6 對 `c8e30d84` 的獨立複驗於 Freeze 撰寫時**進行中、結果未知**。耐久狀態總覽見 **§29**。
- 📌 **2026-10-24 #910 合併補註（append-only，上文一字未改；有意識的更新，不是漏刪，決策者 AI 總管（事實更新））**：PR #910 已於 2026-10-24 squash 合併進 main（merge `066f461e`）。上方 Freeze 補註「`c8e30d84`＝最後一個產品碼 commit」「QA-6 進行中」已過時 —— **最後產品碼 commit＝`9714d0b3`**（PR 最後 head）。QA 經過：QA-6 對 `c8e30d84` 判**不可合併**（2 MUST：MUST-1 持股頁卡④（冷啟動、缺真實廣度）與卡⑤（缺真實廣度）在 v2 卡面畫成紅卡；MUST-2 AI 個股評分被擋字串冷啟動附不實救法）→ `9714d0b3` 修正 → **QA-7 對 `9714d0b3` 判可合併（0 MUST）**；`9714d0b3` CI Fast＋Slow success；完整判定見 PR #910 留言。上文第 6、7 項「待 QA-7」自此讀作「QA-7 已判可合併」。**客戶可見行為（main 現行）**：正式廣度來源接上前，健康分／市場位階通常 ⬜ 未評估；冷啟動（尚未按更新）位階亦 ⬜（灰色「總經尚未載入」，不退規則引擎位階）；🛡️ 持股頁卡④⑤ 在冷啟動／缺真實廣度時為**灰卡、不是紅卡**；Risk Cap 不受影響。QA-7 SHOULD S-1（灰卡沿用 #7「缺漏 · 可重跑」徽章的語意張力）已登記 BACKLOG `DH-BADGE-RERUN-SEMANTICS`（視覺規格，待客戶裁示）。~~main CI 以 GitHub Actions 為準（撰寫組未查）。~~ main CI＋main verification **已成立**（main `066f461e` PR Check run 39995254045 success；`649f739` run 39999485112 success；`PROJECT_RULES.md` 第 7 節；總管 GitHub Actions API 實查＋撰寫組 `gh api` 獨立複查）（2026-10-24 更新，有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=394-422 -->

<a id="ps-hist-33"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=594-612 -->

## 33. C2a-2 接線觀測（2026-10-24；append-only）

> 2026-10-24 新增（決策者 AI 總管（事實更新））。本節**不是新 SSOT**：裁示只在 `docs/DECISIONS.md` DEC-080（含執行紀錄 C2a-2 點）；待辦與新發現只在 `docs/BACKLOG.md` 5.1.10 C2a-2 列與 5.1.12；current／next 只在 `docs/HANDOFF.md`。量測：撰寫組 2026-10-24 21:47 台北 `git fetch`＋`gh api` 實查（會過期，引用前重查）。

| 主題 | 內容 | 性質 |
|---|---|---|
| 授權與停點 | DEC-080 C2a；客戶 2026-10-24：「同意，請切換到 Effort High 後開始 C2a-2…完成 C2a-2 後停手，不自動進 C2b。」 | 客戶指示（經總管轉交） |
| PR | #920（branch `claude/determined-euler-32xqjn`；首個 commit `981e2f69`＋QA 修正 commit，SHA 見 PR #920）；撰寫時 open、mergeable clean、`981e2f69` CI Fast＋Slow success；**合併狀態以 GitHub 為準** | 事實（撰寫組實查） |
| 做了什麼 | `src/services/risk_cap_apply.py::compute_and_lock_risk_cap` 只在三道閘門後的寫檔分支，於本機 `risk_cap_state.json`、`macro_state.json` 附加觀測欄 `input_provenance_shadow`（L2 `infer_input_provenance` 輸出，`shadow_policy_version`＝`c2a-shadow-1`）；未寫檔輪次不記錄。失敗 → `{"_error": <型別名>, "_stage": import／pmi_history／session／infer／sanitize／validate}`＋安全 log（`shared/na_drop_log` 公開別名 `safe_print` —— ⚠️ 該別名自 QA 修正 commit `dc2fa365` 起才存在，`981e2f69` 時為跨模組取 `_safe_print`（2026-10-24 有意識的更新，不是漏刪，決策者 AI 總管（事實更正））；log 失敗走 `_log_error`），⛔ 不改寫檔成敗 | 事實（PR #920 規格；總管轉述） |
| 六點稽核發現落實 | utf-8 encode 自驗；字串上限 `SHADOW_STR_MAX_LEN=512`（技術常數，非投資參數）；延遲 import；安全 log；呼叫點在閘門後；C2a 還原鏈頭在 `c1_revert_for` 前＋before／after 網格＋讀者守衛＋失敗注入 | 事實（總管轉述） |
| PMI 歷史 | 自同一本地 L1（`macro_cache_reader.load_tw_pmi_history`）再讀一次，無新來源。已知限制：cron 可能在兩次讀取之間替換 parquet（只影響觀測欄） | 事實＋已知限制 |
| 零投資輸出變更證據 | 實作組網格（22 具名＋120 隨機）；QA-A 獨立 harness 1937 情境（1183 寫檔／740 不寫檔／14 同例外）對 base `0a78f308` 0 差異（含落盤 bytes 扣除新欄、`get_macro_state` 三模式）；QA-B 對抗注入（怪型別、遞迴、surrogate、壞 stdout、cp950）皆照常寫檔且核心一致；突變測試。fast 30027 passed／28 skipped（base 29969）（`981e2f69` 時點；`dc2fa365` 後 30039 passed／28 skipped，實作組自測（2026-10-24 有意識的更新，不是漏刪，決策者 AI 總管（事實更正）））；slow 120 passed／5 skipped | 總管轉述（撰寫組未重跑） |
| 讀者 | production 無任何讀者讀新欄（grep＋讀碼；QA 單組結論） | ⚠️ 單組，未經第二組驗證 |
| 未變 | Risk Cap 數值、計分資格、Required Core、門檻／公式／權重、regime／燈號、`RISK_CAP_RULESET_VERSION`、`ENGINE_SOURCE`、`is_proxy`、`PRODUCTION_WRITE_APPROVED=False`（撰寫組 grep `shared/risk_cap_history_policy.py` 實查）、Google Sheet 寫入、UI | 事實（旗標實查；其餘總管轉述） |
| 下一步 | 合併後：取得真實寫檔輪次的觀測結果 → 準備 C2b Decision Gate（客戶裁示；⛔ 不得開始 C2b）；建議高能力模型／Effort High | 指標（`docs/HANDOFF.md`） |
| QA 修正（📌 2026-10-24 追加（2026-10-24 有意識的更新，不是漏刪，決策者 AI 總管（事實更正））） | `dc2fa365`：`shared/na_drop_log.py` 新增公開別名 `safe_print`（純別名）；錯誤標記讀端比對；BaseException 往外拋／非 str dict 鍵／list・tuple 分支補測；`_exc_type_name` 失敗時記 `<unrepresentable>`；`tests/test_c2a_risk_cap_shadow.py`（新檔，相對 main）70 tests（實作組自測，含參數化；撰寫組 grep `def test_` 35 個） | 事實（commit 實查）＋測試數總管轉述 |

⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本節由單一撰寫組撰寫；測試數字、QA 結論、讀者判斷為總管轉述，撰寫組只實查 PR 狀態、CI、旗標與 working tree，未重跑測試、未見 QA 原始報告。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=594-612 -->

<a id="ps-hist-34"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=613-621 -->

## 34. 📊 大盤頁 Decision Gate 草稿（2026-10-24；append-only；~~**非 Approved**~~ **Q1～Q4 已裁示 DEC-081**（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-081））

> 2026-10-24 新增（決策者 AI 總管（事實更新））。本節**只放 pointer**，不是新 SSOT、不是裁示。全文：`docs/vnext/MARKET_PAGE_DECISION_GATE_2026-10-24.md`（~~v2~~ v3，commit `ab8b8342`，v3.1 措辭修正進行中（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；基準 main `ea176b8d`）。

- **內容**：大盤相關舊→新能力覆蓋矩陣（§3，含 §3.15 舊 UI 結論句「首批一律不以結論承接」）、首屏文字線框與規則（§1）、可施工清單 W1～W13（§4，零語意變更）、被卡住清單 G*（§5~~，含 Risk Cap 卡位契約：卡面不顯示數字~~）；**Risk Cap 卡位**自 v3 起不再是 §5 預設契約，改為「刻意未接」併入 **Q2**、等客戶核准（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））、客戶裁示題 Q1～Q4（§6）、文件矛盾（附錄 B）、獨立複驗（附錄 C）。
- **狀態**：~~⛔ **未核准**；等客戶裁示 Q1～Q4 後才可開大盤頁實作批（DEC-003 ① 線框 gate）。未裁示前，該檔的推薦與「新版層級」欄只是 RECOMMENDATION。~~ **Q1～Q4 已裁示（DEC-081，客戶 2026-10-25）**；大盤頁實作批進行中（總管轉述）；Risk Cap 卡面措辭以客戶原文為準（見 §35）（2026-10-25 有意識的更新，不是漏刪，決策者 客戶；DEC-081）。
- **限制**（`CLAUDE.md` §-2 規則 6）：矩陣「沒有遺漏」**未證明**（撰寫組兩份單組盤點＋一組獨立複驗，皆單組）~~；v2 修訂未經第二輪複驗~~；已完成三輪獨立複驗（第三輪：剩餘項皆為措辭、修正中），每輪皆單組，完整性仍未證明（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。
- **待辦落點**：`docs/BACKLOG.md` `VN1-MT-IA`、`VN1-MT-HOME`、`UIM-INVENTORY`、`UIM-MAPPING`、`UIM-COVERAGE-MATRIX`（各列 2026-10-24 補註）、`UIM-MKTGATE-DOC-DRIFT`（附錄 B 未登記矛盾）。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=613-621 -->

<a id="ps-hist-38"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=661-676 -->

## 38. 👤 我的 P1（Stage D）實作狀態（PR #927，~~**待合併**~~ **已合併 `ab705fbf`**（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；2026-10-25；append-only）

> 2026-10-25 新增（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。本節只放摘要＋pointer，不是新 SSOT。以下 **FACT** 皆為撰寫組讀分支 `claude/determined-euler-32xqjn` @ `4e8c0876`（`git log 55601f42..HEAD`＋diff＋檔案）所得；**INFERENCE** 另標。~~PR #927 為 draft、尚未合併；撰寫組查時 head CI（Fast checks／Slow tests）in_progress。~~ PR #927 已合併（squash `ab705fbf` on main）（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。待辦見 `docs/BACKLOG.md` 5.1.13 `ME-P1` 與 `NAV-PERSIST` 起 11 列；裁示見 `docs/DECISIONS.md` DEC-083（及其下方 PR #927 註）。

- **新頁（FACT）**：第 7 頁「👤 我的」`src/ui/views/page_me.py`（L5；session／widget key 前綴 `p07me_`）；L0 `shared/ia_nav.PAGE_ME`（`PAGE_LABELS` 最後一項 ⇒ 側欄 radio 最後一個）；`app.py::_ia_view_me()` late import。首屏三張卡：① Google 帳號 ② 目前 Sheet（含「🔄 切換 Sheet」：貼網址／ID、Drive 資料夾＋Sheet 清單、「✅ 使用這本」）③ 這本 Sheet 內容（組合／觀察清單選擇器、「取消選定」、哪些頁在用）；「▸ 詳細：切回舊版、已知限制」預設收合。畫面只露 Sheet ID 末 6 碼（L0 `sheet_id_tail`）、email 遮罩（`me_account_service.mask_email`）。不寫使用者 Sheet、不新增 OAuth scope。
- **L3 `src/services/me_account_service.py`（FACT）**：帳號四態（未設定／未登入／逾時／已登入，另有讀取失敗）、卡② 標題讀取（只有 `ACTIVE_OK` 才讀，用新增的 fail-loud L1 `gsheet_portfolio.read_sheet_title`）、卡③ 清單（`None`＝未知、⛔ 不寫 0）、`bind_sheet`（委派 L1 唯一寫入契約 `apply_sheet_binding`）、`select_portfolio`／`select_watchlist`（先對清單核對名稱存在才寫）、`reload_reads`（`reload_my_sheet_reads`，只本人×active Sheet）、`logout`。
- **`portfolio_binding_service.get_active_sheet()` 狀態（FACT；值 SSOT 在 L0 `shared/sheet_id.py`）**：兩格（組合／觀察清單）同一本 → `ACTIVE_OK`；兩格不同（含一格空）→ `ACTIVE_DIVERGED`；兩格都空、只有 secrets 部署預設 → `ACTIVE_DEPLOY_DEFAULT_ONLY`（**不當 active**）；都沒有 → `ACTIVE_NONE`（快照讀不出來時也回 `ACTIVE_NONE` 並帶 `read_error`）。`get_binding_state(ssot=True)` 與 `get_binding_presence()` 只在 `ACTIVE_OK` 時算綁；`get_binding_state()` 預設呼叫（舊 UI）一字不變。
- **active 選定（FACT）**：session key `_me_active_portfolio`／`_me_active_watchlist`（L0 `ACTIVE_SELECTION_SESSION_KEYS`），值 `{"sheet_id","name","skip"}`；唯一寫入者 L1 `oauth_state.set_active_selection`／`clear_active_selection`；讀取只認同一本 Sheet；Sheet ID 真的變了（`_write_binding_session`）或解除綁定（`clear_sheet_binding`）時清掉；**只活在 session**。消費端：L3 `holdings_service.get_holdings()` 改讀 `get_binding_state(ssot=True)`＋選定，沒選定 → `SELECTION_NOT_SELECTED`、**不讀任何一本**（只有一本也一樣），選定名稱不在清單 → `SELECTION_MISSING`、不讀；觀察清單改讀與組合同一本 active Sheet，另有「不使用」`SELECTION_SKIPPED`。🔍 板塊資金持股標示改為 `get_sector_flow_view(use_active_selection=True)`（同一份選定），不再讀 `etf_portfolio_rows`／個股通道整本觀察清單。
- **登出（FACT）**：L1 `oauth_state.logout_google_session()` 為側欄與 👤 我的共用的唯一一支：清 `gsheet_tokens`／`gsheet_email`／`_oauth_state` → `forget_silent_reauth()`（`?gs=` 記號）→ `clear_sheet_binding()`（兩格 session、`?sheet=`、記號、active 選定）→ 清 L0 `LOGOUT_EXTRA_SESSION_KEYS`（👤 我的 Drive 清單／選擇器／Drive 錯誤／貼 ID 框、側欄貼 ID 框）；不 rerun。新增 `build_login_url()` 的 state 夾帶的是本 session 綁定（不是 secrets 預設）⇒ 登出後再登入不夾帶舊 Sheet。限制：只管得到本分頁網址與本 session（同 `SHEET-MULTITAB`）。
- **DIVERGED 處理（FACT）**：不偷選、不覆寫。👤 我的卡② 白話警示＋兩顆明確按鈕（「✅ 使用『組合』那一本」／「✅ 使用『觀察清單』那一本」，空的一側不畫）；💼／🔍／🚦 都照實說「兩本不同」並指到「👤 我的 › 目前 Sheet」（殘留：💼 本數卡標題仍是「還沒有可以數的 Sheet」，見 `ME-HOLD-COUNT-DIVERGED`）。
- **dead-end 改寫（FACT）**：Sheet／登入／切換類指路改為 `ia_nav.where_to_find(SECTION_ME_*)` 組出的「👤 我的 › …」（💼 `page_hold`、🚦 `page_today.SHEET_UNBOUND_WHERE`、🔍 `page_find` 持股標示來源）；要改內容類（新增組合、補張數／均價、管理觀察清單、唯讀說明）改為客戶 D 段原句 `ia_nav.CONTENT_EDIT_OLD_UI_WHERE`「目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。」（💼 `_edit_where`；卡面只摘前半，見 `ME-HOLD-CARDFACE-PHRASE`）；`CASH_WATCHLIST_ONLY_WHERE` 不再指回自己的唯讀葉。側欄在新版模式：說明改指 👤 我的、`✅ Sheet ID` 只顯示末 6 碼、貼 ID 框不預填也留不住完整 ID；~~「不使用」模式一字不變。~~ 「不使用」模式畫面行為不變（只在從新版切回時把框重設為目前綁定 ID）（`075e8da7` 起以 Session State API 明確指定框值）（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。入口都是**文字**，沒有可點的跳頁按鈕。
- **未變（FACT）**：舊 UI 全部保留（側欄 🔐 Google 帳號、📁 組合管理、`portfolio_binder`、🔗 狀態列、Sheet CRUD）；舊 UI 仍經 `_get_active_sheet_id` 退回 secrets 預設；`restore_sheet_binding_from_query` 未改；`get_sheet_title` 未改（仍吞例外，0 production caller）；P2 CRUD 未開始；C2b 未開始。
- 📌 **head 前進**：本節讀碼基準 `4e8c0876`；撰寫組再查時 head 為 `075e8da7`，該 commit 只改 `app.py` 側欄貼 ID 框（改以 `st.session_state[key] = 值` 明確指定：新版模式指定為空字串、從新版切回「不使用」時指定為目前綁定 ID）＋2 個測試檔（`git diff --stat 6fd083e4..075e8da7`），本節其餘 FACT 不受影響（2026-10-25 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））。
- **INFERENCE／未驗**：撰寫組沒有在 Streamlit 實機看過 👤 我的；「最多 3 次 Google 讀取／rerun、失敗不退避」為讀碼推論（`ME-READ-BACKOFF`）。
- ⚠️ 揭露（`CLAUDE.md` §-2 規則 6）：本節由單一撰寫組產出，**沒有第二組驗過**；「舊 UI 全部保留」「入口都是文字」等全稱句為撰寫組 diff／grep 所得，未經第二組驗證。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=661-676 -->

<a id="ps-hist-43"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=709-717 -->

## 43. 新 UI Stage B 設計草稿（DEC-082 Stage B；2026-10-26；append-only；~~**草稿，待 Stage C 客戶 Gate**~~ **historical：已由 DEC-089 核准，其六向 IA 再被 DEC-091／092 四頁取代**（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新）；上一值刪除線保留））

- 交付物：`docs/vnext/NEWUI_STAGE_B_DRAFT_2026-10-26.md`（基準 main `0ad07fd7`）：IA 草稿（責任方向↔現行 nav 三個候選）、六個責任方向頁面責任卡、🛡️／🎯／⚡／🩺 文字線框與互動對映、跨頁互動、Old→New Interaction Coverage 202 列收斂、S1～S28 收斂（B9）、獨立 QA 修正紀錄（B10）。
- 狀態：Stage B **草稿已交付（待 PR）**；單組撰寫＋三組獨立 QA 複驗後已逐項修正（B10），**修正後尚未再經獨立複驗**；Stage C 正式客戶 Gate **尚未呈現**。
- 待客戶：**G1**（導覽架構：A 沿用／B 六向重組／C 六向殼）、**G2**（🎯 找＋查同頁 X／兩頁 Y）、**G3**（⚡ 是否建、最小版本）、**G4**（🩺 第一版範圍與全站一行狀態）、**G5**（可點跨頁跳轉）、**G6**（🛡️ 逐檔表）、**G7**（High 待開事項是否另開）；另需明確回覆「線框套件（B3～B7）整體核准／退回／指定修改處」與「⚑／結構性自決項確認表」逐項同意／推翻。**沉默不得視為同意**，未回覆＝維持現況／暫行。總管自決 D-1～D-41、輕量確認 Q1～Q4、High 待開清單 HI-1～HI-6（未決，不擬答案）。
- ⛔ **Stage C 核准前不得施工**：0 程式碼、0 測試、0 navigation 變更、不刪舊 UI、不開 P2、不改投資公式／門檻／Risk Cap／趨勢或估值定義、不新增資料來源或 Action 語彙。
- 規則落點／依據：DEC-082（Stage A→B→C→D）、DEC-085／`PROJECT_RULES.md` 第 19 節（責任方向≠現行 nav 命名、SSOT、Coverage 四狀態、Missing 語意）；DEC-088 已記於第 42 節。
- ⚠️ 草稿內的程式碼層級宣稱，除各處標 `FACT` 並附 `file::symbol` 者外，均為 `INFERENCE`／未複驗；總管推薦（RECOMMENDATION）不是已選。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=709-717 -->

<a id="ps-hist-45"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=749-756 -->

## 45. UI-M 📊 市場頁完成~~待合併~~已合併（PR #965，main `3dad82e0`）（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））（DEC-105，客戶 2026-10-29；append-only）

- **狀態**：UI-M 已實作（~~PR #965 待合併~~ 已合併（PR #965，main `3dad82e0`）（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；非 done-verified，待客戶實機點驗）。客戶裁示 1A（結論句位置）／2A（市場位階五態字樣，不映射偏多／中性／偏空）／3A（指標危險度降階到「指標明細（16 項）」最上方，首屏需指路），見 `docs/DECISIONS.md` DEC-105。
- **架構**：L2 `compute_five_bucket_summary` 加性 `main_key`；L3 `market_twii_view_service`（圖 A，attrs 透傳）；L5 `src/ui/views/_market_blocks.py`（Hero 4 卡／⚡／圖 A～D／「查看依據」六欄）；`page_market.py` 只編排並保留既有展開區。還原鏈新頭節 `tests/test_uim_revert_chain.py`。
- **未動**：`PAGE_LABELS`／`ia_nav`／`app.py`／`page_today`／L1。
- **下一個主線 P1**：`docs/vnext/NEWUI_D25_PLAN_2026-10-27.md` §5 序 7 剩餘頁（UI-T → UI-H → UI-ME）與序 8（AB-5／AB-6）；唯一下一步＝UI-T；開工前依 DEC-084 重判 Model×Effort、等客戶切換。⚠️ 「UI-T 先」為計畫表列序讀法，單組。
- **P2 登記**：`UIM-LAYOUT-DEVIATIONS`、`UIM-MA-FLAT-REFERENCE`、`UIM-UPDATE-BUTTON-WORDING`、`UIM-HERO-MAX-ITEMS-SSOT`（`UIM-REGIME-WORDING` 已由 DEC-105 結案為維持現狀）。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=749-756 -->

<a id="ps-hist-46"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=757-765 -->

## 46. UI-T 🎯 標的頁整合（找標的＋查一檔）~~已實作，PR #968~~ 已合併（PR #968，main `9ec555e7`）（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））（DEC-107，客戶 2026-10-29；append-only）

- **狀態**：~~已實作於分支 `uit-impl`（基準 `4521fc39`）；PR #968（合併 SHA 由總管同步）~~ 已合併（PR #968，main `9ec555e7`）（2026-10-29 有意識的更新，不是漏刪，決策者 AI 總管（事實更新））；非 done-verified（待客戶實機點驗，見 `UIT-CLOUD-MOBILE-VERIFY`）。客戶線框五題 1A 2A 3A 4A 5A，見 `docs/DECISIONS.md` DEC-107。
- **架構**：新增 L5 `src/ui/views/page_target.py`（編排）＋`_target_blocks.py`（區塊）、薄 L3 `src/services/target_industry_service.py`；重用 `page_find`／`page_inspect` 既有 loader／builder（兩檔一字未改）；`shared/ia_nav4` 移除過渡切換並新增 `MERGED_VIEWS`；`app.py` 僅 `_ia_view_find()` 依旗標分流。
- **清理**：NAV-1 過渡切換（`NAV4_TARGET_LEAF_KEY`、`NAV4_WIDGET_LEAF_KEY`、`render_target_leaf_selector`、`has_leaves`、`leaf_options`、`leaf_from_label`、`current_leaf`、`_on_leaf_change`）已移除。
- **待客戶**：`UIT-S9-NO-POINTER` 一句話確認（非阻擋，總管推薦同意）。
- **下一個主線 P1**：`NEWUI_D25_PLAN_2026-10-27.md` §5 序 7 剩餘頁 UI-H（💼 持股）→ UI-ME，再序 8；開工前依 DEC-084／DEC-106 比對目前 Model×Effort，符合即靜默繼續。


<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=757-765 -->

<a id="ps-hist-47"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=766-773 -->

## 47. UI-CORRECTION 新 UI 視覺修正線框草稿（DEC-108，客戶 2026-10-29；append-only；**SUPERSEDED BY DEC-109**（2026-10-29 有意識的更新，不是漏刪，決策者 客戶（DEC-109）；上一值刪除線保留））

- **狀態**：~~線框草稿 `docs/vnext/NEWUI_D25_UI_CORRECTION_WIREFRAME_2026-10-29.md` 已撰寫（docs-only；截圖 `docs/vnext/ui_correction_assets/`），**待客戶核准**（`waiting_for_customer＝true`，僅限此線框 5 題）；未回覆＝不核准、不動工。~~ **現行**：被 DEC-109 取代——5 題撤回、`waiting_for_customer＝false`；線框檔與截圖已自本分支移除（原貌只保存在 PR #970 commit `06a7a3e5`）；有效部分已吸收（見 §48）（2026-10-29 有意識的更新，不是漏刪，決策者 客戶（DEC-109）；上一值刪除線保留）。
- **凍結**：~~UI-H 其餘與 UI-ME 的正式視覺實作暫停，直到線框核准（DEC-108）。~~ **現行**：凍結解除條件已由 DEC-109 改寫為「Phase 1 契約合併後依 Phase 2→7 推進，每個 UI phase 過 Visual Fidelity Gate」（見 §48）（2026-10-29 有意識的更新，不是漏刪，決策者 客戶（DEC-109 一）；上一值刪除線保留）。已合併的 UI-M／UI-T 不自動回退。
- **內容摘要**：全站首屏結構／卡片／圖表／文字／圖示規則（§A）、三頁 BEFORE／AFTER 線框（§B）、偏差對照（§C）、能力守恆（§D）、施工順序 E0→E4（§E）、客戶 5 題（A 推薦／B）。
- **限制**：偏差量測為冷啟動 FACT（沙箱無真資料；已載入後圖／表高度為 INFERENCE）；手機實機、Streamlit Cloud 未驗；單組撰寫未經第二組驗。
- **下一步**：~~客戶回覆「1 A｜2 A｜…」→ 依 §E 順序施工，每批獨立 QA 對照 §D。~~ 見 §48（2026-10-29 有意識的更新，不是漏刪，決策者 客戶（DEC-109）；上一值刪除線保留）。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=766-773 -->

<a id="ps-hist-52"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=885-901 -->

## 52. New UI2 Batch 1：Guard 登記／VM boundary 骨架／Preview 入口骨架（2026-11-02；append-only；實作組單組、待總管複驗）

- **依據**：客戶 (7)（Sonnet 5.5＋Medium 後第一個 implementation batch，≤3 項；`docs/vnext/NEWUI2_ARCHITECTURE_GATE_2026-11-02.md` §4／§6／§7／§9）。基準 `origin/main`＝`ebb093be`（#997 合併點；實作組 `git fetch` 實查）。**未 commit／push（由總管處理）**。
- **做了什麼（0 投資語意）**：
  - **L0** `shared/ui2_contract/`：frozen dataclass VM（`FieldVM`／`CardVM`／`FirstScreenVM`／`PageVM`＝`context`＋`slice`）、`FieldState`（OK＋Freeze 四態＋`NOT_PROVIDED`）、`ChipTone` 四族、L1 字樣常數（逐字取 Freeze §5.1）；四頁 id／顯示名**重用** `shared.ia_nav4`（未複製第二份）。
  - **L3** `src/services/ui2/`：`vm_common`（canonical spec→VM，純函式）、`market_vm`（市場頁第一屏 builder）、`skeleton_vm`（標的／持股／我的）、`scenarios`（**FAKE**：四頁×六場景 cold／loaded／missing／stale／unavailable／not_evaluated）、`preview_feed`（Preview 期 FAKE feed）。**不聚合動作、不實作 System Action Aggregator**：市場／持股動作欄恆 `⬜ 尚未提供（待 System Action Aggregator）`；canonical 若夾帶 `action_needed` → raise。
  - **L5** `src/ui2/{shell,components,views}`：四頁 nav（📊🎯💼👤，只此四頁）、metric card／狀態 chip／freshness micro-tag／Preview banner／disabled CTA、第一屏四問（① 現在狀態 ② 是否需要行動 ③ 下一步 ④ 主 CTA）、L1／L2／L3 區塊。頁首固定標示「New UI2 Preview（fake data）」。
  - **L6** `app_ui2.py`（repo 根）：`set_page_config` 後只 `from src.ui2.shell import run`；`app.py` 不引用（測試釘住）、無 `?ui=2`、無路由。
  - **c3 guard**（加性）：`_PATH_LAYERS` `src/ui2/`→L5、`_MODULE_LAYERS` `src.ui2`→L5／`app_ui2`→L6、`_SCAN_FILES` 納入 `app_ui2.py`、`_layer_of_file` 認 `app_ui2.py`＝L6；**既有斷言一字未改**。
  - **新測試**：`tests/test_ui2_guards.py`（G2 VM 純度、G4 獨立性、G4b L5 只讀 `src.services.ui2`、G9 producer／`ui2_` key、chip 語意、G5 四態、G3 切片獨立、動作字樣／術語／Risk Cap／FAKE 標示）、`tests/test_ui2_registration_and_boot.py`（G1 meta＋c3 規則對 UI2 有牙、`app.py` 0 引用 ui2、G10 floor 掃 `app_ui2.py`、AppTest 四頁×六場景、乾淨行程冷啟動）。檢查器皆吃原始碼字串／callable，並有「注入違規必紅」的 teeth 測試。
  - **文件**：`CLAUDE.md` §8.2 七層表既有四列（L0／L3／L5／L6）的代表檔儲存格追加內容（未動既有條文）；BACKLOG §5.1.20＋三列狀態更新；`docs/vnext/NEWUI2_MIGRATION_CUTOVER_CONTRACT_2026-11-02.md` §6；`docs/vnext/NEWUI2_AUDIT_ACCEPTANCE_CHECKLIST_2026-11-02.md` §14；HANDOFF Safe Handoff（Batch 1）。
- **驗證（實作組實測；單組）**：新測試與 c3／`test_views_no_unverified_universal_claims.py` 綠；`streamlit==1.56.0` venv 跑 UI2 測試綠；mutation 15 項（拔 c3 登記、移出 `_SCAN_FILES`、VM 層 import streamlit、L5 import Legacy views、寫非 `ui2_` session key、`top_n` 影響 context、缺值補 0、四態字樣重複、未評估塗紅、拔動作注入防線、L5 用 `guard_chip`、Risk Cap 改字樣、拿掉 Preview 標示、`app.py` 引用 ui2、`app_ui2` import `app`）**全部轉紅**後已還原。截圖證據：`docs/vnext/newui2_batch1/`（390×844＋1440×900；cold／loaded／stale；**僅存證據，非 Visual Fidelity Gate 判定**；FAKE 資料）。
- **限制（誠實揭露）**：(1) 未實機（手機真機、Streamlit Cloud、真登入）；(2) 第一屏「不用滑」**未量測 y 座標**，只目視；(3) 導覽用 Streamlit 原生頂部水平 radio，**與已核准 W-1（底部固定列／左側欄）有落差**（`NUI2-NAV-W1-FIDELITY`）；(4) `src/services/__init__.py` eager import 使 Preview 行程載入 L1 模組（不呼叫；`NUI2-SERVICES-INIT-EAGER`）；(5) 第 6 態 `NOT_PROVIDED` 與 Risk Cap→Not evaluated 歸類為 AI 總管暫定（`NUI2-STATE-NOT-PROVIDED-AUDIT`）；(6) 截圖腳本為一次性、不在 repo（`tools/` 禁動；`NUI2-VF-UI2-SUPPORT`）；(7) 守衛是 AST／原始碼層級，非 import graph／runtime 層級；(8) 全部 FAKE，無真資料驗證（Stage I）。
- **未碰（硬限制）**：`app.py`、`requirements.txt`、`src/ui/**`、`src/ui_v2/**`、`src/data`、`src/compute`、`tools`、`scripts`、`.github`；System Action Aggregator／Risk Cap／Decision Digest／OneBrain runtime；LINE production。
- **下一步**：見 HANDOFF Safe Handoff（Batch 1）；`NUI2-PREVIEW-APP-MANUAL` **未發** Manual Action Gate（客戶：需要時才通知，⛔ 提前要求）。
- 📌 **2026-11-02 DEC-124 後註（append-only；本節上文一字未改）**：上文「`FieldState`（OK＋Freeze 四態＋`NOT_PROVIDED`）」「第 6 態 `NOT_PROVIDED` 與 Risk Cap→Not evaluated 歸類」已由客戶 (8) 裁示修正——`⬜ 尚未提供`＝capability state（⛔ 第 6 資料態）、Risk Cap `⬜ 無法判定`＝Unable to Determine；現況見 §53（有意識的更新，不是漏刪；決策者 客戶（DEC-124））。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=885-901 -->

<a id="ps-hist-54"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=916-928 -->

## 54. New UI2 Batch 2（W-1 導覽保真／共用元件三軸呈現／Mobile-first 第一屏＋viewport 量測；2026-11-03；append-only；實作組單組、待總管複驗）

- **依據**：客戶 (9) 指示（2026-11-03；Sonnet 5.5＋Medium；最多 3 項；純 presentation）。基準 `origin/main`＝`830e8ad3`（含 #998 Batch 1 與 #999 DEC-124 語意修正；分支 `ccr-a0b4e085-ijdaio`，實作組 `git status` 實查與之一致；cron 會推進 tip，以當下 `git fetch` 為準）。本批變更在工作樹，**commit／push／PR 由總管處理**（實作組未 commit）。**本批無新 DEC。**
- **做了什麼（0 投資語意；未新增 Risk Cap 規則或數值；未動 Aggregator／Digest／OneBrain／LINE／real-data／production default）**：
  - **① W-1 Navigation Fidelity**：`src/ui2/shell/app.py` 以 `st.container(key="ui2_nav")` 包 `st.radio(key="ui2_page")`（四頁固定、⛔ 第五頁；session key 仍 `ui2_` 前綴；AppTest 可 `set_value` 切頁）；`src/ui2/shell/css.py` 以 CSS 定位——手機（≤768px）底部固定列 53px（= Freeze §16／Gate §3 的 53px）、桌機左側欄 176px；內容區手機 `padding-bottom:5rem`、桌機 `padding-left:12.5rem`；當前頁＝粗體＋`● ` 符號（pseudo-element）＋色條＋原生 radio `checked`（⛔ 只靠顏色）。選擇器**不依賴** Streamlit 內部 emotion class／`data-baseweb`／`stRadioOption`（1.56 與 1.59 DOM 不同），只用 `.st-key-ui2_nav`＋`[role="radiogroup"] > label`＋`input:checked`／`:has()`。導覽放在內容之後（DOM 順序＝手機底部列 Tab 順序）。Batch 1 的頂部水平 radio 呈現已移除；`temporary implementation gap` 收斂。
  - **② 共用 Presentation Components**（`src/ui2/components/html.py`）：三語意軸 chip 加**樣式**第二載體——資料語意＝實線框、判定結果（無法判定）＝雙線框、capability（尚未提供）＝虛線框，並輸出 `data-axis`／`data-state` 屬性；字樣三表仍互斥（DEC-124）。新增 `empty_state_html`（空／冷／未提供區塊，取代空白）；卡片／列／第一屏列加 `data-axis`／`data-state`；第一屏加量測錨點 `data-ui2-q`（q1～q4／ctx）、頁標題加 `data-ui2-page`／`data-ui2-scenario`；disabled CTA 加 `role="button"`＋`aria-disabled="true"`（⛔ `<a>`／`<button>`／`href`／`onclick`）。source／as_of 維持 field-level（既有；測試證明 ⛔ 全域更新時間）。
  - **③ Mobile-first 第一屏＋viewport 量測**：版面沿既有四問（① 現在狀態／② 是否需要行動／③ 下一步／④ 主 CTA）＋Risk Cap／目前曝險 context 列；動作欄維持 `⬜ 尚未提供（待 System Action Aggregator）`（capability，⛔ 可行動）、Risk Cap 維持 `⬜ 無法判定`（判定結果，⛔ safe）。量測腳本 `tests/ui2_viewport/measure_viewport.py`（可重現；`python -m tests.ui2_viewport.measure_viewport --out docs/vnext/newui2_batch2`；`--python /tmp/v156/bin/python --json-name viewport_measurements_streamlit156.json --shots none` 驗 floor）；判定器 `evaluate()` 為純函式（對真量測綠、對注入違規的量測 dict 紅）；**門檻全部引用既有條文，未自創**（`THRESHOLDS` 逐條標出處：Freeze §16「可用高約 791px＝844−53」、§0.1.6-2、Gate §3、Wireframes §0.4／§7 W-1、Freeze §4.1）。
- **量測結果（Chromium headless，390×844 與 1440×900；四頁 × cold／loaded／missing／stale／unavailable／not_evaluated＝每 viewport 24 態、共 48 態；FAKE 資料）**：Streamlit 1.59.2 **48/48 通過**、Streamlit 1.56.0（`/tmp/v156` venv，floor）**48/48 通過**。手機各頁各元素底緣 y（px，跨六場景範圍；可用高 791）：📊 市場 ① 248–268、Risk Cap 304–324、② 399–419、③ 471–491、④ 562–582；🎯 標的 ① 248–272、Risk Cap 304–328、② 375–400、③ 428–453、④ 518–543；💼 持股 ① 248–268、目前曝險 358–378、② 454–474、③ 526–546、④ 616–636（全站最大）；👤 我的 ① 248–272、② 301–339、③ 354–411、④ 444–502。元素高度最大：①～③ ≤ 96px、④ ≤ 90px。導覽：手機 top=791／bottom=844／全寬／四格同列（各 97.5px 寬）；桌機 left=0、寬 176px、四項垂直。水平捲動：document／stMain `scrollWidth` = `clientWidth`（390／1440），第一屏區塊無橫向裁切。頁底內容不被導覽遮住。完整原始數值見 `docs/vnext/newui2_batch2/viewport_measurements.json`（及 `_streamlit156.json`）；截圖（手機全部 24 張＋桌機 cold／loaded 8 張）同目錄 `*.png`，**手機截圖已逐張目視**：標題無重疊、chip 列完整、底部列未遮內容。
- **驗證（實作組實測；單組）**：新測試 `tests/test_ui2_batch2.py`（94 passed＋1 slow 真瀏覽器）；`tests/test_ui2_*.py`＋既有守衛於 Streamlit 1.59.2 與 1.56.0 皆綠；mutation 10 項實測轉紅後還原（拔底部固定導覽［靜態＋真瀏覽器］、導覽第五頁、chip 無文字（只靠顏色）、capability 字樣併入資料五態、判定結果 chip 以資料軸渲染、chip 軸別樣式拔除、disabled CTA 變可行動、頁面注入全域假更新時間、拔頁底留白［靜態；真瀏覽器以 Playwright 例外轉紅，見 BACKLOG `NUI2-VIEWPORT-M8-NOISY-RED`］、第一屏下移 300px［真瀏覽器斷言式轉紅］）。**注意：這 10 項 mutation 中部分為靜態／單元層轉紅，並非全部由真瀏覽器斷言轉紅**（真瀏覽器斷言式轉紅僅「拔底部固定導覽」「第一屏下移」兩項；「拔頁底留白」為 Playwright 例外轉紅）；且僅單組驗證，獨立 QA 未全數重跑。全 repo 序列結果見 HANDOFF Safe Handoff（Batch 2）。
- **限制（誠實揭露）**：(1) 量測全在 **FAKE 字串**；真資料文字較長會改變高度（餘裕：手機 ④ 最大 636 vs 791）；(2) 只測 Chromium headless 兩個 viewport；Safari／Firefox／真機／iOS 安全區／360px 未測；(3) 無螢幕閱讀器驗證，「aria-current 類」以原生 radio `checked`＋符號等價實現；(4) 導覽自帶深色底（Streamlit 無公開主題變數），使用者切 Light theme 時不一致；(5) 凍結線框第一屏的「今日結論」「mode 切換＋搜尋」等**未做**（BACKLOG `NUI2-WIREFRAME-FIRST-SCREEN-EXTRAS`）；(6) CI slow lane 是否有 Chromium 未確認；(7) 導覽 CSS 依賴 `.st-key-*` class 與 `:has()`，Streamlit 升版需重量。
- **未碰（硬限制；`git diff --name-only HEAD -- app.py requirements.txt tools scripts .github src/ui src/ui_v2 src/data src/compute` 實查為空）**：`app.py`、`requirements.txt`、`tools/`、`scripts/`、`.github/`、`src/ui/**`、`src/ui_v2/**`、`src/data`、`src/compute`；System Action Aggregator、Risk Cap 規則／數值／runtime、Decision Digest、OneBrain、LINE、real-data wiring、production default、Old UI／Legacy New UI。
- **§27 檢查**：新 Rule＝無（既有 Freeze §4.1／DEC-124 三軸邊界原樣適用；量測門檻不自創屬既有 PROJECT_RULES 精神）；新 Decision＝無（實作選擇屬 `CLAUDE.md` v3 §03-1 內部自決）；Audit finding／Limitation／Backlog／Migration debt／Acceptance item 已寫入 BACKLOG §5.1.22、Audit Checklist §16、Migration Contract §8、HANDOFF Safe Handoff。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=916-928 -->

<a id="ps-hist-56"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=940-957 -->

## 56. New UI2 Batch 3（📊 今日結論＋今日主要風險／🎯 雙模式＋搜尋＋查一檔 FAKE／👤 帳戶 skeleton；2026-11-03；append-only；實作組單組、待總管複驗）

- **依據**：客戶 (10) B～F（2026-11-03；Sonnet 5.5＋Medium；最多 3 項；純 presentation）。基準 `origin/main`＝`e5f9a0d7`（#1000 `a726b05e` 之後僅純資料 bot commit；分支 `ccr-a0b4e085-ijdaio` 含 A 段 docs `f683e0d9`；cron 會推進 tip，以當下 `git fetch` 為準）。本批變更在工作樹，**commit／push／PR 由總管處理**（實作組未 commit）。**本批無新 DEC**（今日結論句型＝DEC-081 Q2-1 規則；主要風險退化句＝DEC-117 Q6 逐字；皆既有裁示）。
- **做了什麼（0 投資語意；未新增 Risk Cap 規則／數值／門檻／公式／probability；未動 Aggregator／Action Authority／Digest／OneBrain／LINE／real-data／production default）**：
  - **① 📊 市場**：`FirstScreenVM.conclusion`（今日結論，第一屏**首列**）與 `PageContext.main_risk`（今日主要風險，L1，**緊接第一屏四問之後**，同一個 `.ui2-m-l1` 容器內、⛔ 被卡片／L2／L3 插隊）。桌機（≥769px）以 CSS grid 把 ①市場目前狀態／Risk Cap／今日主要風險排成**三 tile**（Wireframes §2.2／DEC-117 Q1 桌機），手機同 DOM 順序堆疊。**今日結論**＝canonical 提供的 FAKE 示意句（`FAKE 示意結論：市場目前狀態 …；〈非 OK 指標逐一明寫〉；各項判斷並列、互不推導`）：各判斷獨立並列以「；」相接、缺值／Stale／Unavailable／未評估**明寫**、⛔「但／因此」、⛔ 方向與動作字樣；**VM 原樣帶出**，不由位階／指標推導（`market_vm`／`vm_common` 無任何結論生成碼）；冷啟動＝灰色 `⬜ 尚未載入`。**今日主要風險**：只放退化／護欄句（DEC-117 Q6 逐字，常數在 `shared/ui2_contract/text.py` `RISK_SENTENCE_*`／`RISK_NOTE_UNEVALUATED_NOT_SAFE`／`RISK_ERROR_FMT`，與 Legacy `_market_blocks.py` 原始碼逐字比對）：cold＝`⬜ 尚未載入，請按更新`（灰；不列風險項列）、missing＝`⬜ 無法判定（五桶資料皆不足）`（判定結果軸）、unavailable＝`🔴 來源目前不可用`＋`五桶風險摘要算不出來：…`（真錯誤才紅）、not_evaluated＝`⬜ 尚未評估`＋`未評估不等於安全`、loaded／stale＝capability `⬜ 尚未提供`（Preview：風險項尚未接線，**不產生任何風險項**）。
  - **② 🎯 標的**：`TargetVM`（`PageContext.target`）＋`PresentationSlice.active_mode`。**雙模式**（`市場精選｜即時查一檔`，`st.radio(key="ui2_target_mode")`＋`st.container(key="ui2_target_mode_box")`＋CSS 膠囊；只寫 `ui2_` 前綴 UI 狀態）：兩模式內容**都在 `context`**，切換只改 slice（`visible_card_ids`＝查一檔時 `()`、`active_mode`）→ 不同時完整展開（Presentation Slice ≠ Decision Context；測試證明 context 逐欄相等）。**搜尋框＋搜尋 CTA**＝disabled 示意（`role="searchbox" aria-disabled="true"`＋disabled CTA；⛔ `<input>`／`<form>`／real-data fetch；兩模式都外露；名稱搜尋＝capability `⬜ 尚未提供`＋「請輸入代碼」）。**fake ticker／fake result**：`FAKE-0001 FAKE 示意公司`＋Neutral chip；6 維 Snapshot（基本面／估值／籌碼＝`FAKE 占位`、趨勢／產業＝`⬜ 尚未定義`〔DEC-092 Q2 固定〕、市場環境排最後且 Neutral）；**加入觀察 CTA 恆 disabled**（`尚未提供：正式加入觀察流程僅舊 UI；Preview 不寫入…`，DEC-083）；session 隔離說明句。**W-4**：市場位階＋Risk Cap 為一行輕量 chip（置於查詢摘要之下、字級 .78rem＜摘要）；位階與市場頁同一份 FAKE market context（各場景同步）。**本頁不產生持股動作**（動作欄維持 capability，動作權威＝💼 持股）。
  - **③ 👤 我的**：`AccountVM`（`PageContext.account`）；`get_preview_page_vm(..., account=)`／`fake_canonical(..., account=)`（FAKE 連線事實維度；預設 `signed_in`＝Batch 2 內容不變）。**三態**：signed-out（Google 卡 `尚未登入`〔OK 事實值〕、Sheet／組合／觀察清單＝Missing `⬜ 資料未備`〔不適用〕、主 CTA `Google 登入`）、signed-in（主 CTA `切換 Sheet`；動作列 切換 Sheet／選組合／選觀察清單／Google 登出）、unavailable（Sheet＝Unavailable `🔴 來源目前不可用`＋「Sheet 讀取失敗（FAKE 示意）」、組合／觀察清單＝Missing `⬜ 資料未取得`、主 CTA `重新讀取`）。全部動作 CTA disabled；Preview 控制新增 selectbox `ui2_account`（僅 👤 我的頁有效）。**無** OAuth／Sheet／secrets／`src.data`（AST／import 守衛含 mutation）。
  - **量測腳本擴充**（`tests/ui2_viewport/measure_viewport.py`）：新增 6 條判定（`market_conclusion_in_first_screen`／`market_main_risk_follows_first_screen`／`target_mode_search_first_screen`／`target_mode_exclusive`／`target_w4_context_light`／`me_account_state_first_screen`），**門檻全部引用既有條文**（Freeze §0.1.6-3／-5、§16、Wireframes §2.1／§2.2／§3.1／§9／§1／§5.1，未自創 px）；🎯 每場景另量『即時查一檔』、👤 另量 signed-out／unavailable（每 viewport 32 態、共 64 態）。
- **量測結果（Chromium headless，390×844／1440×900；FAKE）**：Streamlit **1.59.2：64/64 通過**；Streamlit **1.56.0（`/tmp/v156` venv，floor）：64/64 通過**（`docs/vnext/newui2_batch3/viewport_measurements_streamlit156.json`；1.56 venv 的 `test_ui2_*`＋`test_c3_layering_guard` 615 passed）。手機底緣 y（px，跨全部場景範圍；可用高 791）：📊 市場 今日結論 268–293、① 322–365、Risk Cap 378–421、② 474–517、③ 543–588、④ 633–679、**今日主要風險 top 650–696／bottom 708–772**（皆在導覽上緣 791 之上、且緊接 ④ 之後）；🎯 標的 模式切換 bottom 223、搜尋列（＝④）bottom 284、① 398–423、W-4 context 434–464、② 505–536、③ 558–588；👤 我的 ① 248–272、② 300–339、③ 354–411、④ 444–502、帳戶動作列 bottom 566–654。桌機三 tile：①、Risk Cap、今日主要風險頂緣同為 y=238（差 0px）。
- **驗證（實作組實測；單組）**：新測試 `tests/test_ui2_batch3.py`（180 項；含 AppTest 整頁渲染順序／模式互斥／session 隔離、AST 守衛含注入、判定器 21 條 teeth）；既有 `tests/test_ui2_*.py`（guards／batch2／registration）仍綠（`_all_fields` 掃描範圍只增不減；batch2 slow 測試的預期態數隨覆蓋擴大改為 `2×(4×6＋6＋2)`）。**mutation 12 項實測轉紅後還原**：結論句改「，但」、今日主要風險被卡片插隊、兩模式同時展開、標的頁寫非 `ui2_` session key、我的頁 import `oauth_state`、signed-out Sheet 掛判定結果軸、加入觀察 CTA 變 enabled、冷啟動主要風險畫成紅色、退化句改寫、模式切換改變 context、VM 夾帶方向字樣、搜尋框變可互動。
- **限制（誠實揭露）**：(1) 量測全在 **FAKE 字串**，真資料長度未測（手機今日主要風險 bottom 最大 772 vs 導覽上緣 791，餘裕僅 19px；真資料只會更長 → `NUI2-VIEWPORT-FAKE-ONLY`）；(2) 只測 Chromium headless 兩個 viewport；Safari／Firefox／真機／螢幕閱讀器未測；(3) 搜尋＝disabled 示意，**W-3 送出即切換、名稱搜尋、真查詢全未做**；(4) 今日結論是 **FAKE 示意句，非逐字結論句**（DEC-081 Q2-1 只有句型規則；真結論句＝`NUI2-CONCLUSION-REAL-FEED`）；(5) 冷啟動「主要風險不出列」為單組解讀（`NUI2-COLD-MAIN-RISK-READING`）；(6) 「尚未登入」歸類與 W-4／紅色兩義交會為單組判讀（`NUI2-ME-SIGNEDOUT-CLASSIFICATION-REVIEW`、`NUI2-TARGET-W4-RED-ON-UNAVAILABLE`）；(7) 桌機三 tile 依賴 `display:contents`＋`grid-row` 明確放置（`NUI2-MARKET-DESKTOP-3TILE-CSS`）；(8) 截圖手機全部態＋桌機 cold／loaded；其餘桌機態以 JSON 為準；(9) 本 repo 無 `SESSION_LOG` 檔（grep／find 0 命中），session 紀錄以本節＋HANDOFF 為準。
- **未碰（硬限制；`git diff --name-only HEAD -- app.py requirements.txt tools scripts .github src/ui src/ui_v2 src/data src/compute` 與 `shared`（非 `ui2_contract`）實查為空）**：同 Batch 2；另 System Action Aggregator runtime／Action Authority／Decision Digest／OneBrain／LINE／real-data canonical wiring／新 source／新 threshold／新公式／新 probability。
- **§27 檢查**：新 Rule＝無（既有 DEC-124 三軸、DEC-117 Q6、DEC-081 Q2-1、PROJECT_RULES §28 原樣適用）；新 Decision＝無；Audit finding／Limitation／Backlog／Migration debt／Acceptance item 已寫入 BACKLOG §5.1.24、Audit Checklist §17、Migration Contract §9、Wireframes §10、HANDOFF Safe Handoff。

- **§56 補（獨立 QA 修正；append）**：F3 查一檔 cold 只畫搜尋框＋灰色說明（`LookupResultVM.queried`）；F2 W-4 context／『市場環境』改 Neutral＋文字狀態（只放寬此二處；`NUI2-TARGET-W4-RED-ON-UNAVAILABLE` 更新）；F4 預設道補「市場 L1 之前無 L2／L3」AppTest（mutation 轉紅）；F5 三個自證式 teeth 測試改真實 mutation／刪除；新登記 `NUI2-MARKET-REFRESH-CTA-ORDER`（Batch 2 起的未登記偏離）、`NUI2-ME-DUP-LOGIN-BUTTON`、`NUI2-Q21-RISKCAP-MISSING-WORDING`、`NUI2-MAIN-RISK-NAV-MARGIN`（BACKLOG §5.1.24 末）。證據 JSON／截圖已重量（1.59.2 與 1.56.0）。

- **索引（DEC-126／PROJECT_RULES 第 29 節；append）**：客戶 2026-11-03 新增「多元解法與最小成本決策規則」，逐字見 `docs/DECISIONS.md` DEC-126、規則本體 `PROJECT_RULES.md` 第 29 節（第 9 點為併用 `CLAUDE.md` v3 §03、第 11／12 點為 AI 總管增添，均非客戶原文，已於該處明註）。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=940-957 -->

<a id="ps-hist-69"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=1110-1116 -->

## 69. New UI2 視覺完善 Batch 1（2026-11-05；presentation-only；實作組單組；獨立 QA 待做）

- **已做**：① chip 文字色對比（`src/ui2/shell/css.py`；對深色底與疊 tint 皆 ≥4.5:1；`tests/test_ui2_chip_contrast.py`，含負向突變）。② 💼 持股桌機首屏依 Wireframes §4.2／W-11 重排（`src/ui2/components/html.py::hold_l1_html`／`page_title_html`、`src/ui2/views/hold.py`、`css.py` `.ui2-h-l1`；`tests/test_ui2_hold_header.py`）。手機版面不變（`hold_loaded` 與「只換 chip 色」基準逐像素相同）。
- **實測（FAKE；Chromium headless）**：measure_viewport 70/70（1.59.2）、70/70（1.56.0）；Real 11/11（兩版）；📊 手機 stale 181.6／unavailable 162.5（與 before 逐位相同，≥160 守衛未退化）；`UI2_BROWSER_LANE=required` `ui2_browser` lane 52 passed（1.56.0）／52 passed（1.59.2）；`tests/test_ui2_*`＋c3＋portability 1470 passed。證據 JSON（`newui2_batch3b`／`newui2_realfeed`）因 source_hash 重生，僅 `p4_hold` 結果改變。
- **未動**：JS（`drawer_js.py`、JS_V4 hash、`tests/test_ui2_drawer_js_guard.py`）、資料來源、公式、Risk Cap、OneBrain、OAuth、A2／A3／B／C 類；DEC 未新增。
- **未驗**：iOS／Android 真機、Streamlit Cloud／Manage app、Firefox／WebKit、Light theme、Real feed 視覺截圖、1.56／1.59 以外版本；非 pixel parity（無原圖）。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=1110-1116 -->

<a id="ps-hist-69-note1"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=1117-1121 -->

## 補註（2026-11-05｜#1020 視覺完善 Batch 1）
- 獨立 QA 通過（0 FAIL），待合併（draft）；DEC-138 維持 Dark-only，不新增 Light 支援。
- 局部修正、非整頁完成：W-11 Primary 圖／⑤ 建議持股區間／持股表未做（B 類，需草稿裁示）；限制保留於 BACKLOG／HANDOFF。
- 下一個安全工作：💼 完整 W-11 與 🎯 精選線框草稿（須先出草稿裁示）。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=1117-1121 -->

<a id="ps-hist-69-note2"></a>
<!-- PROJECT_STATE_HISTORY_SEGMENT:BEGIN src=docs/PROJECT_STATE.md base=a2926c8e lines=1122-1124 -->

## 補註（2026-11-05｜💼 W-11 批 1 版面空槽）
- draft PR `ui2/hold-w11-batch1`：純版面空槽（狀態行／需處理單行／Primary 與建議持股水位空槽／持股表欄名）。W-11 仍 open（待獨立 QA＋資料接線）。守衛與證據見 BACKLOG `NUI2-HOLD-W11-BATCH1`。

<!-- PROJECT_STATE_HISTORY_SEGMENT:END lines=1122-1124 -->

