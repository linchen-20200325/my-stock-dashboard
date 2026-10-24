# vNext 1.0 Decision Gate 收斂

> **日期**：2026-10-18｜**性質**：客戶指派的收斂批（研究整理），**只整理題目，不施工** —— 不改產品 code、UI、公式、門檻、資料來源。
> **來源**：`docs/vnext/VNEXT_PRODUCT_BLUEPRINT.md`（下稱 **BP**）第 23 節 `BP-DR-01`～`BP-DR-21`、`docs/BACKLOG.md` 第 5.1.1～5.1.2 節（`SEC-2`／`SEC-3`／`UIA-FU-2`／`UIA-FU-4`）。登記：`docs/BACKLOG.md` DR-2026-10-18-2。
> **請示格式**：依 `PROJECT_RULES.md` 第 4 節 —— 商業與功能語言＋總管推薦方案＋具體原因，可一鍵決策；已確認 bug、只有一個安全修法者**不包裝成裁示題**（反向禁令）。
> 📌 **2026-10-18 裁示（append-only；上下文一字未改）**：五題已由客戶裁示，見 **DEC-062**／DR-2026-10-18-3；各題下方加註，第 6 節為裁示後的建議小批次（建議，不是授權）。
> ⛔ **本檔不是實作授權**。各題裁示後，施工仍須客戶指派批次（`CLAUDE.md` §-1；DEC-057「不要開始 vNext 1.0 implementation。」）。
> 📌 **2026-10-24 追加（append-only；上文與第 1～6 節一字未改）**：第 7 節收錄 **`PROXY-SEMANTICS`／C2 Decision Gate**（BIAS240／PCR／台灣 PMI 的 proxy／estimated 資料契約與計分資格；DEC-077 第 3 點 B、第 5 點）—— 研究整理、~~**待客戶裁示**，⛔ 非授權~~ **已裁示 DEC-080**（2026-10-24 有意識的更新，不是漏刪，決策者 客戶；DEC-080）；所有推薦皆為「總管推薦，待客戶裁示」（送題時狀態）。C2a 已指派；C2b 為新的待裁示 Gate（§7.7）。

## 1. 摘要

本次共 5 個待裁示問題。

- Blueprint 的 21 題（`BP-DR-01`～`BP-DR-21`）加上 4 個相關 Backlog 項（`SEC-2`、`SEC-3`、`UIA-FU-2`、`UIA-FU-4`），收斂成 **5 題客戶問題**（`VN1-Q1`～`VN1-Q5`）。
- 其餘分三類，**本輪不問客戶**：
  - **建議延後到 2.0**（`BP-DR-02`、`07`、`08`、`09`、`10`、`12`、`15`）—— 延後只是總管建議；這些題在 Backlog 的狀態**不變**（仍 `blocked-on-customer`），客戶若想現在裁示仍可提出。
  - **1.0 維持現狀、不需要問**（`BP-DR-20`、`21`）—— 1.0 不改現行行為，沒有要客戶決定的事。
  - **內部技術決定**（`SEC-1-FU`、各項實作細節等）—— 屬 `CLAUDE.md` §-1.5 v3 §03-1 內部自決區，不做成選擇題。
  - ⚠️ `BP-DR-18`（`SEC-2` 修法）與 `AUD-C12`（上限紀錄保存）的**機制**屬內部決定，但涉及憑證保存／資料保存位置，依 DEC-009 保留客戶**同意**，分別併入 VN1-Q2、VN1-Q4 的附帶同意題（總管 2026-10-18 決定）。

## 2. 五題客戶問題

### VN1-Q1｜1.0 新畫面先核准哪些？

- **白話問題**：新版畫面的線框（Blueprint 裡標【1.0】的草稿）要一次全部核准，還是先核准你點名的 1.0 重點，其餘下一輪再看？
- **A**：一次核准全部 1.0 線框（Blueprint 原做法），包含持股頁「需要處理／值得注意／正常持有／無法判定」四組分組、機會頁細節。
- **B**：先核准 1.0 重點：
  - 四格導覽（今天／機會／持股／我的）；
  - 首屏一行 Google 登入晶片＋「我的」頁完整登入卡；
  - Sheet 選擇放在晶片彈窗與「我的」頁；
  - 持股頁維持唯讀，已綁定 Sheet 時一打開直接讀持股；
  - 新舊版並存，兩邊各放一個入口；**不把新版設為預設**（切換預設依 DEC-020 另送）；
  - 今天頁；
  - 「我的」頁（BP §13／§13.1；它承載完整登入卡與 Sheet 選擇）；
  - 狀態配色與資料狀態表（BP §2.1 色彩語意表、§15 資料狀態 UX 矩陣，一併納入核准範圍）。

  **B 案下，以下 1.0 線框留到 1.0 下一輪送審（仍屬 1.0，不是 2.0）**：機會頁 §9.2／§9.3／§9.6、個股／ETF 首屏 §10.2／§10.3、Evidence「為什麼」四層 §14.2、持股卡片列表 §11.3、Desktop 1440 線框（§6、§8.9、§10.8）。
  **只有**持股四組分組（`BP-DR-14`）延到 2.0。
- **註**：工程術語中文化新增的「技術資訊」層（把工程細節收進一層）屬視覺元件，隨本題線框核准；措辭改寫本身屬內部決定。
- **總管推薦：B**。理由：(1) 對齊客戶點名的 1.0 重點（看得懂、登入方便、手機好操作）；(2) 持股四組分組已接近「該怎麼做」的行動建議語意，而它依賴的 `AUD-C10`（同頁「上限 10%」與「崩盤加碼 50%」方向相反）尚未仲裁，現在核准等於先定了一個還沒有規則支撐的分組。
- **不裁示會擋住的 1.0 工作**：**所有 1.0 UI code**（DEC-003：版面／欄位／動線變更須先核准線框）。
- **涵蓋**：`BP-DR-01`、`BP-DR-03`、`BP-DR-05`、`BP-DR-16`、`BP-DR-17`、`BP-DR-14`（B 案下延到 2.0）、`UIA-FU-2`（資料體檢徽章屬視覺規格，隨本題的狀態配色一併核准）。

> 📌 **2026-10-18 客戶裁示（DEC-062；本題上文一字未改）**：「Q1：B。」→ 採 **B**：上列 B 案範圍為 1.0 線框**送審範圍**；機會頁 §9.2／§9.3／§9.6 等留 1.0 下一輪送審；`BP-DR-14` 延 2.0。⚠️ 核准的是**送審範圍**，不是線框本身 —— 依 DEC-003，線框依此範圍送審、客戶拍板後才可寫 1.0 UI code（見第 6 節建議批次 `1.0-B4`）。

### VN1-Q2｜重新整理頁面後，要不要保持登入？

- **白話問題**：現在重新整理網頁就會登出。1.0 要讓你重新整理後仍保持登入嗎？
- **A**：不保持，每次重新登入，畫面誠實說明「重新整理會登出」（Blueprint 原推薦）。
- **B**：保持登入。做法順序：先修好登入防偽造（`SEC-2`），再做可行性驗證；**驗證不過就退回 A**。個人設定、已讀狀態的保存延到 2.0。
- **總管推薦：B**。理由：客戶把登入持續性列為 1.0 重點。⚠️ **此推薦與 Blueprint 原推薦（A）不同**，特此明寫；B 案以「先修 `SEC-2`、驗證不過退回 A」控制風險。
- **附帶同意（是／否）**：「登入防偽造修正會在伺服器短期保存一次性驗證碼（不是密碼、不存 Google 憑證），驗不過就要求重新登入 —— 同意嗎？」**總管推薦：同意**。理由：這是修好 `SEC-2` 的前提，保存的只是幾分鐘失效的一次性碼。（不論本題選 A 或 B，`SEC-2` 都要修，故此同意題獨立成立。）
- **不裁示會擋住的 1.0 工作**：登入流程的施工範圍（BP-B2）；`SEC-2` 修復。
- **涵蓋**：`BP-DR-04`、`BP-DR-18`（附帶同意）。
- **註**：`SEC-2` 的具體機制（簽章 cookie／伺服器端短期儲存／PKCE 的取捨與實作）屬內部技術決定，**不做成選擇題**；但涉及憑證保存，依 DEC-009 保留上述客戶同意（總管 2026-10-18 決定）。修前須安全稽核，且不得重現 v19.63 的登入迴圈。

> 📌 **2026-10-18 客戶裁示（DEC-062；本題上文一字未改）**：「Q2：B，並同意短期保存一次性驗證碼；不得保存 Google 密碼或憑證。」→ 採 **B**（先修 `SEC-2` → 可行性驗證 → 不過退回 A）；附帶同意＝**同意**。⛔ **硬限制（客戶原文）：不得保存 Google 密碼或憑證。** 機制（簽章 cookie／伺服器端短期儲存／PKCE）仍屬內部決定，但必須在此限制內；修前安全稽核、不得重現 v19.63 登入迴圈。依客戶指示，登入／安全批開始前先做 Effort Check，若需 High 先停下提醒客戶切換。

### VN1-Q3｜沒登入的人，能不能看到你的持股？

- **白話問題**：目前如果有人沒登入、但知道你 Sheet 的網址代碼，在某些設定下可以透過系統帳號讀到分享給系統帳號的 Sheet。要關掉嗎？
- **A**：關掉。只有登入、且自己有該 Sheet 權限的人能讀；系統帳號只給排程任務用（關閉 `SEC-3`）。
- **B**：維持現狀（匿名訪客可透過系統帳號讀分享給系統帳號的 Sheet）。
- **總管推薦：A**。理由：持股是個人資產；以多人安全為準，不讓「知道代碼」等於「能看」。
- **同題附問**：正式環境（production）目前**有沒有設定系統帳號**？（repo 內查不到，**未知**；若沒設定，`SEC-3` 在正式環境實際不會發生，但 A 仍可防日後誤設。）
- **不裁示會擋住的 1.0 工作**：登入入口擴大（BP-B2）前的權限邊界；`SEC-3` 修復批。
- **涵蓋**：`BP-DR-06`、`SEC-3`。

> 📌 **2026-10-18 客戶裁示（DEC-062；本題上文一字未改）**：「Q3：A。正式環境是否有系統帳號，請自行檢查可取得的設定；無法確認再回報，不要猜。」→ 採 **A**（關閉匿名訪客經系統帳號讀 Sheet，`SEC-3`）。
>
> **正式環境系統帳號檢查（2026-10-18，撰寫組單組；結論：無法確認）**
> - **結論**：正式環境（Streamlit Cloud）是否設定 `[gcp_service_account]` **unknown（無法確認）**。Streamlit Cloud 的 secrets 不在 repo、也無法從本沙箱讀取；以下沒有任何一項能直接證明「有」或「沒有」。
> - **已檢查項目**：
>   1. repo 檔案：`.streamlit/secrets.toml` **不在 repo**（`.gitignore` 第一條即排除，`git ls-files` 無此檔）；`.streamlit/secrets.toml.example` 與根目錄 `secrets.toml.example` 只列 `FINMIND_TOKEN`、`PROXY_URL`、`GEMINI_API_KEY`，**沒有** `[gcp_service_account]` 範例。
>   2. 程式讀取路徑：`src/data/portfolio/gsheet_portfolio.py::_sa_configured` 要求 `portfolio_sheet_id` **與** `[gcp_service_account]` 兩個 secret 同時存在才進 SA 模式；`gsheet_portfolio.py::_build_client` 於 OAuth 不可用時才退回 SA；`src/data/portfolio/oauth_state.py` 以 `_safe_secret("gcp_service_account")` 讀取。→ 程式**支援** SA 模式，但支援 ≠ 已設定。
>   3. GitHub workflow：`.github/workflows/push_holdings_daily.yml` 以 GitHub Secret `GCP_SERVICE_ACCOUNT_JSON`（只看名稱）供排程讀 Sheet；`scripts/push_holdings_daily.py::main` 呼叫 `gsheet_sa_reader.load_sa_credentials`，該函式在 secret 缺／壞時 raise → workflow 失敗。該 workflow 2026-10-12～10-16 排程 run 皆 `success`（`gh run list` 實查）→ **推論** GitHub Actions 端設有系統帳號憑證。⚠️ 這是 **GitHub Actions 的 secret，不是 Streamlit Cloud 的 secret**，兩處各自設定，不能據此推論正式網站也有。`gh secret list` 被代理拒絕（HTTP 403），secret 是否存在未直接讀到。
>   4. 文件：`ARCHITECTURE.md`、`SPEC.md` 把 SA 模式寫為「管理員部署用、向後相容」，未記載正式環境實際是否設定。
> - **客戶可自行確認的方法**：Streamlit Cloud → 該 app → Settings → Secrets，看是否有 `[gcp_service_account]` 區段（以及 `portfolio_sheet_id`；兩者都有才會進 SA 模式）。輔助線索：若正式環境**未**設定 Google 登入（`[google_oauth]`），側欄會顯示「ℹ️ 使用 Service Account（舊版部署）」（`app.py` 側欄）；但若已設定 Google 登入，此提示不會出現，故不能當作判斷依據。
> - **對 A 案的影響**：不論正式環境有沒有設定，A 案（關閉匿名經 SA 讀取）都成立 —— 沒設定時防日後誤設，有設定時直接堵住。排程用的 SA 走 `gsheet_sa_reader`（環境變數、唯讀 scope），與網站匿名路徑分開。

### VN1-Q4｜今天頁的「和上次比」，比的是什麼？

- **白話問題**：今天頁要告訴你「和上次比有什麼變化」。「上次」要怎麼算？
- **A**：
  - 比上一份**通過新鮮度檢查、規則版本相同**的系統風險上限紀錄；
  - 7 天沿用期間（取不到新值、沿用舊值）**不算一次變化**；
  - 每天保存有效紀錄（保存方式屬內部技術決定，**尚未驗證**可行，見 `AUD-C12`）；
  - 1.0 只提醒兩件事：**資料取得失敗**、**系統風險上限正式值有變**（任何變動都提醒，不設大小門檻）。
- **B**：1.0 不做比較，只顯示「從今天開始記錄」。
- **附帶問題（是／否）**：「每日系統風險上限紀錄要存在 repo 追蹤檔（重啟不會遺失、可追溯）嗎？」**總管推薦：是**（沿用 repo 既有「排程落地到 git 追蹤檔」模式）。保存的技術細節（檔案格式、排程、寫入方式）仍屬內部決定。
- **總管推薦：A；保存方式驗證通過前先用 B**。理由：A 才有「沒事的日子可以安心關掉」的價值；但保存方式未驗證，先用 B 不會給出錯誤比較（`CLAUDE.md` §1：錯誤的數字比沒有數字更危險）。不設大小門檻是因為任何門檻都是新公式（DEC-046）。
- **不裁示會擋住的 1.0 工作**：今天頁「變化」區塊（BP-B4）。
- **涵蓋**：`BP-DR-13`、`BP-DR-11`（僅 1.0 部分：首頁只放兩種事件；四層觸發與推播範圍延 2.0）、`AUD-C12`（保存位置，併入附帶問題；首次送題）。

> 📌 **2026-10-18 客戶裁示（DEC-062；本題上文一字未改）**：「Q4：A；但暫不核准「每日紀錄存 repo 追蹤檔」。先研究最小、可靠、可持久化且符合「資料層 ≠ AI 推理層」的保存方式，再提出建議；不要直接把 Git repo 當 production datastore。保存方式未定前可先採 B 顯示「從今天開始記錄」。」
> - 比較規則採 **A**（上一份通過新鮮度、規則版本相同的紀錄；7 天沿用不算變化；只提醒取數失敗與上限正式值有變）。
> - 附帶問題：~~總管推薦：是（存 repo 追蹤檔）~~ → **客戶暫不核准**（2026-10-18；有意識的變更，不是漏刪）。⛔ 不得把 Git repo 當 production datastore。
> - 保存方式：**先研究、再提建議**（新研究項 `VN1-STORE`，`docs/BACKLOG.md` 5.1.2；只研究、不實作）；條件：最小、可靠、可持久化、符合「資料層 ≠ AI 推理層」；研究範圍（客戶正式文本）：Streamlit Cloud persistence、restart/deployment、concurrency、寫入可靠性、資料責任。⛔ 不得自行新增變動大小門檻。
> - **過渡**：保存方式未定前採 **B**，今天頁顯示「從今天開始記錄」，不做比較；⛔ 不得製造不存在的歷史比較。

### VN1-Q5｜資料不齊時，今天頁怎麼說？

- **白話問題**：總經資料只到了一部分時，今天頁的彙總燈要怎麼顯示？
- **A**：
  - 燈色維持「最差的那一顆燈」，並註明「只根據 N／M 項」；
  - 「資料正常」定義為：系統風險上限的必要資料（Required Core：VIX、PMI 當期、PMI 前月、外資期貨＋MA5，DEC-048）**都到齊且新鮮**；其他缺的項目逐項列出；
  - 分母沿用既有裁示：代理值只顯示不計分（DEC-037）、已停用的標「已停用」不算缺（DEC-049／DEC-051）、無資料來源的項目不得宣稱通過、明示缺漏（延伸 DEC-044，請確認）。
  - **請確認**：上述既有裁示原本是針對系統風險上限，是否**同樣適用於總經彙總燈**？
- **B**：只要有任何一項缺，燈改灰色「資料不足」。
- **總管推薦：A**。理由：(1) 不新增「缺幾項算不足」的門檻（DEC-046 已拒絕無證據的 N/M 門檻；DEC-048 已用 Required Core 定義必要資料）；(2) 延續 2026-08-27 已核准的最差燈語意；(3) B 會讓一項選用資料缺失就把整盞燈變灰，等於「選用資料缺就讓判斷停擺」（DR-2026-10-15-2 方向原則不允許）。
- **不裁示會擋住的 1.0 工作**：今天頁彙總燈與「資料健康」列（BP-B4）；`UIA-FU-4` 修復；`UIA-01` (b) 燈色語意。
- **涵蓋**：`BP-DR-19`、`UIA-FU-4`。

> 📌 **2026-10-18 客戶裁示（DEC-062；本題上文一字未改）**：「Q5：A，並確認代理值不計分、停用項明示停用、無資料來源不得宣稱通過。」→ 採 **A**；上文「請確認」兩處 → **客戶已確認**：代理值不計分（DEC-037）、停用項明示停用（DEC-049／DEC-051）、無資料來源不得宣稱通過（延伸 DEC-044）**同樣適用於總經彙總燈**。`UIA-FU-4` 依此裁示另批修（須客戶指派批次／依 9.2 Effort Check）。

## 3. 全表：`BP-DR-01`～`BP-DR-21` 與相關項的 1.0 處置

| ID | 主題 | 1.0 處置 | 依據 |
|---|---|---|---|
| `BP-DR-01` | 四格主頁取代 DEC-017 五頁 | **VN1-Q1** | BP §4.2、§5.1 |
| `BP-DR-02` | V3 永久排除條款是否仍有效 | 延後 2.0（1.0 不顯示方向性 Action，不觸及） | BP §23 |
| `BP-DR-03` | 首屏登入晶片＋「我的」登入卡 | **VN1-Q1** | BP §7.2～7.3 |
| `BP-DR-04` | 重新整理後保持登入、設定／已讀持久化 | **VN1-Q2**（設定／已讀延 2.0） | BP §7.1、§23 |
| `BP-DR-05` | Sheet 選擇位置、持股頁唯讀、預設讀持股 | **VN1-Q1** | BP §7.4、§11.1 |
| `BP-DR-06` | 單人／多人；匿名能否經系統帳號讀 Sheet | **VN1-Q3** | BP §23；BACKLOG `SEC-3` |
| `BP-DR-07` | 雙軌選股條件與門檻 | 延後 2.0（1.0 沿用現行規則只改呈現） | BP §9.1、§9.4 |
| `BP-DR-08` | 七種 Action 正式規則 | 延後 2.0（Action 規格批；1.0 不顯示七種 Action） | BP §16 |
| `BP-DR-09` | Thesis 規格 | 延後 2.0 | BP §17 |
| `BP-DR-10` | 判斷可信度三級 | 延後 2.0（隨 Action 規格批） | BP §10.7 |
| `BP-DR-11` | 四層 Attention 觸發與推播 | **VN1-Q4**（僅 1.0 兩種事件）；其餘延 2.0 | BP §8.1、§12.1 |
| `BP-DR-12` | 官方／第三方數字衝突容差 | 延後 2.0 | BP §14.5 |
| `BP-DR-13` | 「和上次比」的上次定義 | **VN1-Q4** | BP §8.5、§8.7 |
| `BP-DR-14` | 持股四組分組對映 | **VN1-Q1**（B 案下延後；依賴 `AUD-C10`） | BP §11.2 |
| `BP-DR-15` | 「接近機會」定義 | 延後 2.0 | BP §9.5 |
| `BP-DR-16` | 【1.0】線框核准範圍 | **VN1-Q1** | BP §23（範圍清單） |
| `BP-DR-17` | 新舊並存兩入口、何時切預設 | **VN1-Q1**（切預設依 DEC-020 另送） | BP §5.3 |
| `BP-DR-18` | `SEC-2` 修法機制 | **VN1-Q2 附帶同意**（機制內部，依 DEC-009 保留客戶同意；總管 2026-10-18 決定）；修前安全稽核、不重現登入迴圈 | BP §7.8；BACKLOG `SEC-2` |
| `BP-DR-19` | 部分資料時彙總燈、「資料正常」定義 | **VN1-Q5** | BP §8.4、§15 |
| `BP-DR-20` | AI 解釋放哪、能否轉述買賣判斷 | 1.0 維持現狀、不需問（只保留現有兩個 AI 呼叫點） | BP §14.3 |
| `BP-DR-21` | 系統風險上限名稱與新說法 | 1.0 維持現狀、不需問（沿用「系統風險上限」、一卡一數字） | BP §11.5 |
| `SEC-2` | 登入防偽造不生效 | VN1-Q2 附帶同意後修（機制屬內部決定） | BACKLOG 5.1.1 |
| `SEC-3` | 匿名經系統帳號讀分享 Sheet | **VN1-Q3** | BACKLOG 5.1.1 |
| `UIA-FU-2` | 資料體檢空來源徽章 | **VN1-Q1**（狀態配色／§15 一併核准） | BACKLOG 5.1.1 |
| `UIA-FU-4` | 代理值計入分母仍印「五桶全綠」 | **VN1-Q5** | BACKLOG 5.1.1 |
| `AUD-C12` | 系統風險上限快照保存位置 | **VN1-Q4 附帶問題**（技術細節內部） | BACKLOG 第 2 節 |
| `SEC-1-FU` | 撤銷授權後自身快取 TTL 內仍命中 | 內部決定（已知限制） | BACKLOG 5.1.1 |

## 4. 內部自決、不問客戶

以下屬 `CLAUDE.md` §-1.5 v3 §03-1 內部自決區，**不做成選擇題**；但**仍須客戶指派批次**才施工（`CLAUDE.md` §-1），並照常派工、獨立稽核、CI。

- `SEC-2` 修法機制（簽章 cookie／伺服器端短期儲存／PKCE 的選擇）—— 機制內部；依 DEC-009 保留的客戶同意見 VN1-Q2 附帶同意題。
- 底部導覽在 Streamlit 中的實作方式（版面本身由 VN1-Q1 核准）。
- `AUD-C12` 保存的技術細節（格式、排程、寫入方式）—— 保存位置（repo 追蹤檔與否）見 VN1-Q4 附帶問題。
- 工程術語中文化的措辭改寫（在 S1-6 規則內只改措辭；超出去術語範圍依 DEC-055 程序另送）；新增的「技術資訊」層屬視覺元件，隨 VN1-Q1 線框核准。
- 已確認 bug 的技術部分：`UIA-14`（根因未查，施工前先確認修法單一）、`UIA-FU-1`（失敗與未載入分兩態）、`UIA-FU-3` 技術部分（吞例外、快取命中記 ok、跨 session 共用；「哪些來源回空＝失敗」屬資料語意，不在此列）。

## 5. 證據與限制（`CLAUDE.md` §-2 規則 6）

- **分析方式**：兩組獨立分析（A 組：產品／UX；B 組：資料／安全）各自對 21 題做分群，**分群結果一致**；差異由總管裁決：
  - VN1-Q1 範圍：A 組推薦 B、B 組推薦 A → **總管採 B**（理由見該題）。
  - VN1-Q2：兩組皆推薦 B，與 Blueprint 原推薦 A 不同 → 採 B 並在題目內明寫差異。
- **未驗證事項**（只能當待驗事項，不得當成施工前提）：
  - VN1-Q2 B 案的可行性；Streamlit 的 cookie 限制；
  - `AUD-C12` 保存方式；
  - 正式環境是否設定系統帳號；（2026-10-18 檢查：unknown／無法確認，見 VN1-Q3 節）
  - DEC-037／DEC-049／DEC-051／DEC-044 是否適用於總經彙總燈（VN1-Q5 請客戶確認）。
- **稽核修正（2026-10-18）**：獨立稽核 PASS-WITH-FIXES；依其 MUST 項把 `BP-DR-18`、`AUD-C12` 由「純內部決定」改為併入 VN1-Q2／VN1-Q4 的附帶同意（DEC-009 credentials／資料保存）。
- **未在 Streamlit Cloud 實測**；本檔內容為讀文件與讀碼的整理。
- 本檔由單一撰寫組依總管規格撰寫，題目分群經上述兩組分析；本檔文字本身未經第二組逐字複驗。

## 6. 裁示後狀態與建議小批次順序（2026-10-18，DEC-062／DR-2026-10-18-3）

> ⛔ **本節是總管建議，不是授權**。客戶原文：「不要一次施工整個 vNext 1.0」「後續按安全小 Batch 推進」「建議第一個 implementation Batch 優先處理安全前置依賴（SEC-2／SEC-3），但請先依最新 repo、依賴與風險自行確認最小安全批次」。每批開始前依 `PROJECT_RULES.md` 9.2 做 Effort Check（DEC-061）；若需 High，先停下提醒客戶切換。~~**目前尚未開始任何實作。**~~ 📌 2026-10-18 更新：~~`1.0-B1` 已開工（in-progress，PR 未合併；總管轉述；有意識的變更，不是漏刪）。~~ `1.0-B1` **完成**（#877、`a9ba83c1`、main CI run 39132620519 success；有意識的變更，不是漏刪）；~~其餘批次尚未開始。~~ 📌 2026-10-19 更新：`1.0-B2` 已開工（in-progress，PR 未合併；總管轉述；有意識的變更，不是漏刪）；`1.0-B3` 起尚未開始。

| 建議批次 | 內容 | 預期 Effort | 前提／限制 |
|---|---|---|---|
| **1.0-B1** 安全地基 | `SEC-2` 登入防偽造（只存一次性驗證碼、不存 Google 密碼／憑證）＋`SEC-3` 關閉匿名經系統帳號讀取（＋`SEC-1-FU` 登出清該使用者快取，是否併入由開工前依最新 repo 確認） | **High** | 開工前先依最新 repo／依賴／風險確認最小安全批次；修前安全稽核；不得重現 v19.63 登入迴圈<br>📌 2026-10-18 狀態（append-only，總管轉述）：**in-progress**（`SEC-2`＋`SEC-3`；`SEC-1-FU` 刻意未併入；commits `abb44a90`、`5be0e9dd`；PR 未合併）；後續 `B1-FU-1`～`3` 見 `docs/BACKLOG.md` 5.1.1<br>📌 2026-10-18 收尾（append-only）：**完成**（#877、`a9ba83c1`、main CI run 39132620519 success；`SEC-2`／`SEC-3` 已移入 BACKLOG「3. 已結案」）；⚠️ 未在 Streamlit Cloud 實測真實登入（`B1-FU-2`，屬 `1.0-B2`）；production SA／`[google_oauth]` 仍 unknown |
| **1.0-B2** 登入持續性 PoC | 重新整理後維持登入的可行性驗證；不可可靠實作則退回 A | **High** | 依賴 B1（`SEC-2`）；同一硬限制<br>📌 2026-10-19 狀態（append-only，總管轉述）：**in-progress**（commits `23596359` 靜默恢復登入（Google `prompt=none`、網址記號；⛔ 不保存任何 Google 憑證，session 以外不留）、`1d169927`／`e7c2cba7` 稽核修正第 1／2 輪、`efd3d369` 第 3 輪；PR 未合併）。第 3 輪為 DEC-010 上限外、客戶 2026-10-19 核准（`docs/BACKLOG.md` DR-2026-10-19-1）：「裁示：A。核准依 DEC-010 進行第三輪小修，但範圍嚴格限定」—— 已登入 session 只信任 session 自身的 Sheet；已登入時 error 分支不寫 state 帶回的 Sheet。⛔ 客戶原文：「完成第三輪後不得再自行進入第四輪；若仍發現需要修改同一批檔案，重新停下裁示」。⚠️ 未在 Streamlit Cloud／真瀏覽器實測（`B2-FU-1`，客戶動作；本地測試不能替代）；可行性結論未定；後續 `B2-FU-1`～`5` 見 `docs/BACKLOG.md` 5.1.1 <br>📌 2026-10-19 狀態（append-only）：上一則「in-progress」自本日起不再成立（有意識的變更，不是漏刪）；`1.0-B2 程式已合併（#879、`cef52c2e`、main CI run 39203796408 success（Fast＋Slow；總管轉述））；**待客戶正式網站驗收（`B2-FU-1`）**；驗不過依裁示退回 A（可先以 secrets `oauth_silent_reauth=false` 關閉）；`B2-FU-1`～`5` 仍 open；⚠️ 可行性結論未定，不得視為已結案 |
| **1.0-B3** `VN1-STORE` 保存方式研究 | 研究並驗證（不實作）：Streamlit Cloud persistence、restart/deployment、concurrency、寫入可靠性、資料責任；不把 Git repo 當 production datastore | **Medium** | 結果送客戶裁示（附推薦方案）<br>📌 2026-10-19 狀態（append-only）：研究完成（`docs/vnext/VN1_STORE_RESEARCH.md`；只研究、未實作）；總管推薦系統專用 Google Sheet（GitHub Actions cron 單一寫入、app 以新唯讀 SA 讀取），次選 GCS；**待客戶裁示保存位置（DEC-009）**；無頭寫入 PoC 未驗證<br>📌 2026-10-19（append-only）：DEC-063 已裁示方向 A；最小 PoC 已合併（#882、`a45c7405`、main CI run 39234825821 success）；待客戶手動觸發 `risk_cap_history_poc` workflow 並建立 Sheet／帳號／secrets；production 寫入未核准。上一則「待客戶裁示保存位置」「無頭寫入 PoC 未驗證」自本日起不再成立（有意識的變更，不是漏刪） |
| **1.0-B4** 線框送審 | 依 Q1-B 範圍出文字線框送客戶拍板（DEC-003） | **Medium** | 拍板前不寫 1.0 UI code |
| 後續批 | 線框核准後的 UI 實作（今天頁先採「從今天開始記錄」、彙總燈依 Q5-A 等），逐批送 | 依批而定 | 線框核准後；每批 Effort Check |

## 7. `PROXY-SEMANTICS`／C2 Decision Gate（2026-10-24；研究整理，~~**待客戶裁示**，⛔ 非授權~~ **已裁示 DEC-080**）

> ✅ **狀態：已裁示 2026-10-24，DEC-080**（2026-10-24 有意識的更新，不是漏刪，決策者 客戶；DEC-080）。客戶裁示逐字全文見 `docs/DECISIONS.md` **DEC-080**；本節 7.1～7.3、7.6 的研究證據**原文不動**，7.4 各題加「✅ 已裁示（DEC-080）」摘要，7.5 加現行禁止範圍，新增 **7.7 C2b Decision Gate**（新的待裁示 Gate，C2a 取得實際觀測結果後送）。⚠️ 下方各處「總管推薦，待客戶裁示」字樣是**送題當時**的狀態紀錄，自 DEC-080 起以裁示為準。

> **日期**：2026-10-24｜**性質**：DEC-077 第 3 點 B／第 5 點要求的 C2 前置研究，**只研究、只整理題目，不實作** —— 不改產品 code、tests、workflow、data、公式、門檻、權重、資料來源。
> **承載處**：`docs/BACKLOG.md` `PROXY-SEMANTICS`／C2 列（5.1.10）原本沒有獨立的 Decision Gate 檔；本節沿用本檔（vNext 1.0 Decision Gate 承載檔）收錄 C2 Gate 全文。**本檔第 1～6 節一字未改**；本節與 vNext 1.0 的 VN1-Q1～Q5 是不同題組。新發現登記在 `docs/BACKLOG.md` 5.1.11；耐久摘要在 `docs/PROJECT_STATE.md` §31；現況在 `docs/HANDOFF.md` §0。
> **研究方法**（`CLAUDE.md` §-2 規則 4／6）：三組獨立唯讀研究，基準 main `f48b30bf`、量測日 2026-10-24 —— **A 組**：程式路徑盤點（讀碼＋grep）；**B 組**：治理文件盤點（DECISIONS／BACKLOG／HANDOFF／PROJECT_STATE／PROJECT_RULES／Data Health 稽核與計畫檔）；**C 組**：紅隊行為實證（mock session 實際呼叫 production 函式 `build_engine_inputs` → `run_rule_engine` → `compute_and_lock_risk_cap` → `get_macro_state` → `build_allocation_decision`，檔案只寫進 scratch；既有 pytest 子集 z64／z65／z66／z66b／i2_bias／c1_observability **571 passed**）。三份原始報告留在總管 scratchpad、**不入庫**；本節只收錄事實與出處。
> **標記**：「**兩組交叉**」＝至少兩組獨立得到同一事實；「**單組**」＝只有一組看到（只能當待驗事項，`CLAUDE.md` §-2 規則 6）。行號為 2026-10-24 `f48b30bf` 實測，會過期。
> ⛔ **本節任何方案都不是 Approved／已裁示**；所有推薦一律是「**總管推薦，待客戶裁示**」。客戶裁示前，DEC-077 第 3 點 B「不得先建立『proxy 一律不能計分』或『proxy 一律可以計分』的通則」與 `CV1-DR-11` 的暫行讀法照舊有效。
> 📌 上一行為送題時狀態；自 2026-10-24 起**已裁示（DEC-080）**：資料身分／計分契約採方案 2；`CV1-DR-11` 由 DEC-080 裁示、暫行讀法退場；DEC-077 3B 仍有效（DEC-080 為逐指標裁示，未立通則）（2026-10-24 有意識的更新，不是漏刪，決策者 客戶；DEC-080）。

### 7.1 現行真實契約（研究結論，非裁示）

| # | 項目 | 現況 | 出處 | 驗證 |
|---|---|---|---|---|
| 1 | Required Core | VIX、台灣 PMI 當期＋前月、外資期貨淨空單＋加權指數跌破 MA5 | DEC-048 客戶原文「{VIX、PMI 當期、PMI 前月、外資期貨＋MA5}」；`shared/risk_cap_policy.py:56-62` `REQUIRED_CORE_INPUTS` | 兩組交叉（A、B；C 實跑一致） |
| 2 | 不寫檔條件 | 依序三道閘門，任一成立即不產生新 cap：(a) fail-safe（啟用中數值輸入全缺）、(b) cap 為非有限數、(c) Required Core 任一無效（`REASON_CORE_MISSING`）；`risk_cap_state.json`／`macro_state.json` 兩檔一位元組不動；讀端沿用 7 天內有效快照，超過 →「無法判定」 | DEC-048／DEC-044／DEC-040；`src/services/risk_cap_apply.py:262-278`（三道閘門）；`src/services/macro_state_locker.py:662-697,962-990`；`shared/staleness.py:135,163`（`MACRO_VERDICT_MAX_AGE_DAYS = STALE_DAYS_DAILY = 7`）。C 組實測：VIX／PMI 當期／PMI 前月／外資期貨／MA5 缺、VIX 過期 6 種情境皆 `written=False`；快照 6.9 天 → 沿用 40%、7.1 天 → None | 兩組交叉（A 讀碼、C 實測；B 治理一致） |
| 3 | 7 天的起算點 | 以**快照寫入時間** `timestamp` 計，不看輸入 as-of ⇒ 沿用期末的實際資料年齡可 >10 天（日頻） | `macro_state_locker.py:962-985` | 單組推論（A）＋C 讀碼／實測 6.9／7.1 天；「>10 天」為推論、未實測 |
| 4 | Optional（BIAS240、PCR）缺 | 照算、寫檔，卡面揭露「未評估：PCR、BIAS240；部分訊號未納入，本次上限資訊不完整」 | DEC-046／DEC-051；`macro_engine_inputs.py:364-367`；`src/ui/views/risk_cap_gate.py:85-95`；C 組實測 `written=True`、`not_evaluated=['BIAS240_pct','PCR']` | 兩組交叉（A、C；B 治理一致） |
| 5 | proxy／estimated 對 Risk Cap 的正式契約 | **不存在**；程式對 proxy／estimated／stale-cache 完全無處置 | B：DEC-062 Q5、DEC-037、DEC-074 皆非針對這三項；DEC-077 3B 列為待裁示。A：`dated_inputs.py`／`macro_engine_inputs.py`／`risk_cap_apply.py` 不讀 `is_estimated`／`is_proxy`／`is_stale`／`_pcr_src` | 兩組交叉（A、B、C） |
| 6 | BIAS240 <240 日 | `macro_snapshot.compute_twii_bias` 以可得天數均線頂替（`_cs.tail(min(240,_n)).mean()`，`is_estimated = _n < 240`）；估算值與正式值同欄 `bias_240`、旗標另欄；`extract_bias240` 不讀旗標 → 估算值進 Risk Cap 計分 | `src/data/macro/macro_snapshot.py:461,491`；`src/compute/macro/dated_inputs.py:160-167`；`macro_state_locker.py:870-876` | 兩組交叉（A、C） |
| 6a | BIAS240 估算的實際影響 | +20% 估算值使上限 40% → 20%（扣 15 分須共振條件 VIX≥22 或 PMI<50，`macro_state_locker.py:870-876`；probe 用 VIX 25／PMI 47）；`not_evaluated` 為空 ⇒ 卡面「必要與選用訊號皆已評估」。反方向：估算值 <−10 也會觸發加 10 分而**放寬**上限（讀碼，未實測） | C 組 probe；`macro_state_locker.py:870-876` | 單組實測（C） |
| 6b | BIAS240 在 16 燈 | 原樣用值判燈，只在顯示字串加「（估算）」徽章 | `src/compute/macro/macro_helpers.py:1949,1989,2035-2038,2049`；I2 註解「只揭露，不改判定」 | 兩組交叉（A、C） |
| 6c | BIAS240 新 UI 圖表 | 另一條路徑：`macro_cache_reader.load_v2_chart_series` 足 240 才算、不足不畫（不估算） | `src/data/macro/macro_cache_reader.py:544-566` | 單組（A） |
| 7 | PCR 混源 | 先以 FinMind TXO 三大法人 OI 估算填 `選PCR`，TAIFEX 探測通過才逐日覆蓋 ⇒ 同欄逐日混源；估算值進 Risk Cap（>1.5 −10、<0.7 +5） | `src/data/macro/leading_indicators.py:1384-1412,1580-1596`；`dated_inputs.py:248-260`；`macro_state_locker.py:878-881`；C 組實測估算值與 TAIFEX 值結果完全相同 | 兩組交叉（A、C） |
| 7a | `_pcr_src` | 零讀者，且由測試強制：`tests/test_c1_observability.py::test_new_fields_have_no_readers`（約 :1693-1716）⇒ 任何接線都須同批改該測試（＝政策變更） | `leading_indicators.py:283-293`；同上測試 | 兩組交叉（A、C） |
| 7b | 新 UI 的 PCR | 無 PCR 燈、無來源顯示；16 燈不含 PCR | `src/ui/views/*.py` grep 只命中 `risk_cap_gate.py:86` docstring | 單組（A） |
| 8 | 台灣 PMI 當期 | 8 源賽跑取第一命中；data.gov.tw/6100 標 `is_proxy=True`、NDC 標 `True`，第三方 StockFeel／Cnyes／MoneyDJ 反標 `False`（語意倒置）；`is_proxy`／`is_stale` 無讀者 | `src/data/macro/macro_core.py:1424,1494,1572,1612,1693`（`PMI_SOURCE_REGISTRY` `:1707-1716`）；同檔 `:1213-1225` 註解稱 data.gov.tw 是「同一份官方數字」 | 兩組交叉（A、C；B 亦記） |
| 8a | 台灣 PMI 前月 | 恆取 cron parquet `data_cache/tw_pmi.parquet`，來源 data.gov.tw dataset 6100 —— 即當期路徑被標 proxy 的同一資料集 | `dated_inputs.py:391-458`；`scripts/update_macro_history.py:783-`（約 `:871` `source="data.gov.tw:dataset:6100"`） | 單組（A） |
| 8b | 台灣 PMI stale-cache | 8 源全敗 → 90 天 stale-cache，保留原資料月；資料月仍在發布期內即判 FRESH、可滿足 Core；`stale-cache(…)` 字樣不進快照、不上 UI | `macro_core.py:1174-1188`；`shared/freshness_policy.py:37-45,185`；`risk_cap_apply.py:178-181`；C 組實測 `stale-cache(StockFeel)` → FRESH、`core_gaps=[]`、cap 40 | 兩組交叉（A 讀碼、C 實測） |
| 8c | 台灣 PMI 的治理身分 | 無任何 DEC 指定 PMI 正式來源，也沒有核准它是 proxy 例外；`CLAUDE.md` §2.1 列 data.gov.tw 為 T1 官方，但屬 §0 Bootstrap 依程式證據填寫、非客戶裁示；DEC-030 要求前月用「官方值」 | B：DECISIONS grep「PMI」只見 DEC-030／048／070／077 | 單組（B） |
| 9 | 跨輸入同日比對 | 各 input 各自判新鮮、無跨 input 同日比對 | `macro_engine_inputs.py:351-357`；`dated_inputs.py:251-252` | 兩組交叉（A、C） |
| 9a | VIX 燈 vs Risk Cap | 同一 session：VIX 10/14 的 36.0 在 16 燈 `state=ok`，Risk Cap 判 stale 不計分 | C 組 probe2 | 單組實測（C） |
| 9b | 外資期貨燈 vs Risk Cap | 16 燈／交通燈取末列（`_df_last`／`iloc[-1]`），Risk Cap 逐欄往回取 ⇒ 同輪可取不同列（實測燈 missing、Risk Cap 10/22 fresh） | `macro_helpers.py:374,1742-1750`；`dated_inputs.py:207-260` | 兩組交叉（A、C） |
| 9c | 盤中未收 K 棒 | `drop_in_progress_bar` 只用在領先市場；VIX／BIAS240／MA5 取數未排除 | `macro_cache_reader.py:399,467` | 單組（A） |
| 9d | 16 燈新鮮度 | 無新鮮度閘門、無逐燈 as_of；readiness 側車無 as_of／stale 欄 | `macro_helpers.py` 五桶段 grep 0 命中；`page_today.py:89-93,960-966` `AS_OF_NOT_IN_CONTRACT` | 兩組交叉（A、C） |
| 9e | 混日揭露 | 快照有 `input_asof`／`input_detail`，UI 不揭露；實測 VIX 10/20、PCR 10/20、期貨 10/23、PMI 2026-09 同一快照，UI 只寫「必要與選用訊號皆已評估」 | `risk_cap_apply.py:283-291`；`shared/risk_cap_policy.py:153-190`；`risk_cap_gate.py:56,93-94` | 兩組交叉（A、C） |
| 10 | forward ledger | `macro_forward_test` 驗的是交通燈，不含 Risk Cap；若要驗 Risk Cap 還缺 VIX 日期、PMI 當期／前月資料月與來源、BIAS240 估算旗標、PCR 逐日來源、MA5 日期、`veto_flags` | `shared/macro_forward_test_schema.py:39-81`；`src/compute/macro/macro_forward_test.py:182-218` | 單組（A） |
| 11 | 新 UI 看不到 Risk Cap 的根因 | `BREADTH_PROXY_SCORING_ENABLED=False` → 健康分恆 None → `build_allocation_decision` 回未評估 →「系統風險上限」不進 `caps` ⇒ 快照有效上限 40%，卡①／卡⑤ 仍顯示「尚未評估」 | `shared/signal_thresholds.py:277`；`macro_helpers.py:437-447`；`shared/allocation_decision.py:281-298,316-333`；C 組實測 `exposure_limit_pct=40`、`has_system_risk_cap=False` | 單組實測（C；A 組未提此機制；BACKLOG `RC-VISIBILITY` 既有記載同一判斷式） |
| 12 | 系統間共用 | 健康分是 16 燈第一盞（`BUCKET_DANGER_SPECS` 首鍵 `health`）；位階第 3 順位來源＝Risk Cap 引擎輸出的 `market_regime`，目前被 `BREADTH_PROXY_SCORING_ENABLED=False` 封住 | `macro_helpers.py:1932`；`macro_state_locker.py:348-372` | 健康分＝16 燈：單組（C）；位階第 3 順位：兩組交叉（A、C） |
| 13 | 已驗證行為正確（原風險不成立） | Optional 無效不會讓整體失效；Core 無效不產生新 cap | C 組實測（見 #2、#4） | 單組實測（C）＋B 治理一致 |

### 7.2 Decision Gate 題目（Q1～Q6；推薦一律「總管推薦，待客戶裁示」）

#### Q1｜資料身分怎麼分級？

| 選項 | 內容 | 缺點 |
|---|---|---|
| A | 單軸四類：`official`／`real`／`proxy_estimate`／`unavailable` | `official` 與 `real` 的界線不清 |
| B | 單軸三類：`real`／`estimated`／`unavailable` | 失去「proxy＝不同量的替代」與「estimated＝同一個量的近似」的區別 |
| **C（總管推薦，待客戶裁示）** | **兩軸正交**：provenance ∈ {`observed_official`, `observed_secondary`（同一序列、非主要發布者，例：第三方轉載的 CIER PMI）, `estimated`（同量近似算法，例：BIAS240 短窗均線）, `proxy`（不同量替代，例：TXO 法人 OI 比）, `unavailable`} × freshness ∈ {`fresh`, `stale`, `carried_forward`}；另帶 `as_of`、`source_id`；計分資格由**逐指標 policy table** 推導，不壓成單一 boolean；UI 以文字標籤揭露（不只靠顏色）；欄位 additive、schema 可演進 | policy table 多一層維護 |

#### Q2｜逐指標計分資格

> 選項代碼：**1** 可計分／**2** 可計分＋降 confidence＋揭露／**3** 不計分、只顯示／**4** unavailable。

| 指標／情境 | 總管推薦（待客戶裁示） | 理由 | 影響 |
|---|---|---|---|
| BIAS240 `estimated` | **3**：Risk Cap 不計分 → 列入未評估並寫明「歷史不足、估算」；16 燈顯示保留估算標籤 | Optional，不計分不阻斷 cap；估算值在共振條件（VIX≥22 或 PMI<50）下已實證可讓上限下修 20 點，且 <−10 時會加 10 分而**放寬**上限（7.1 #6a） | Risk Cap 輸出在估算情境改變（＝投資輸出變更）；16 燈是否同步，由 DEC-076 ① 一併決定 |
| PCR `proxy`（FinMind TXO 法人估算） | **3**：只有 TAIFEX 官方值計分；法人估算顯示為 proxy | 不同量；門檻 1.5／0.7 依官方 PCR 語意設定 | TAIFEX 失敗日 PCR 列未評估；須同批改 `test_new_fields_have_no_readers`（零讀者守衛） |
| 台灣 PMI | **1**：`observed_official` 與 `observed_secondary` 皆可計分並揭露來源；`carried_forward`（stale-cache）在發布期內可計分但須揭露「沿用」，超出即 `unavailable`（Core 無效 → 不產生新 cap） | Required Core；若一律剔除會讓 Risk Cap 不產生新上限（`PROXY-SEMANTICS` (1)） | 前提：先修正 `is_proxy` 倒置語意（見 Q5）；⛔ 不得以 blanket rule 把 PMI 拿掉計分（DEC-077 3B） |
| 選項 2（降權計分） | **列出但不推薦** | 需要新的權重／confidence 規則；與 DEC-074 B 客戶原文「不得自行創造新權重重新正規化」同向衝突，且新權重屬須送客戶裁示的正式 scoring／weight 變更（`PROJECT_RULES.md` 第 4 節 #1） | — |

#### Q3｜freshness × eligibility 矩陣

> 分開判斷五件事：`exists`（有值）／`fresh`（新鮮）／`score_eligible`（可計分）／`displayable`（可顯示）／`riskcap_usable`（可用於 Risk Cap）。

| provenance × freshness | 計分 | 顯示 | 總管推薦（待客戶裁示） |
|---|---|---|---|
| observed（official／secondary）＋fresh | ✅ | ✅ | eligible |
| observed＋stale | ❌ | ✅ 標 stale | 不計分、可顯示 |
| observed＋carried_forward | 僅 PMI 在發布期內 ✅ | ✅ 標「沿用」 | 只有 PMI 例外，須揭露 |
| estimated／proxy＋fresh | Risk Cap ❌ | ✅ 標籤 | 不計分、可顯示並標籤 |
| estimated／proxy＋stale | ❌ | 可選 | 不計分 |
| unavailable | ❌ | — | ineligible |

#### Q4｜Core vs Optional

- **總管推薦（待客戶裁示）**：Core 只接受 observed（official 或 secondary）且 fresh（PMI `carried_forward` 例外如 Q2）；proxy／estimated **不得**滿足 Core → 不產生新 cap、依 DEC-048 沿用 7 天。Optional 的 proxy／estimated 不計分、只揭露、不阻斷。
- **7 天規則維持**；改以「輸入 as-of」起算屬公式／門檻變更（`PROJECT_RULES.md` 第 4 節 #1），**另列題、本次不提**；先做「沿用 N 天前的上限＋最舊輸入日期」揭露（揭露上卡屬欄位增減，須線框草稿先行，與 `RC-VISIBILITY` 一起處理）。

#### Q5｜台灣 PMI 的身分

- **研究判定**：「**目前語意不一致，需新的 Decision Gate**」—— 既不是已核准的正式例外，也不是一般 proxy：程式 `is_proxy` 標記與 `CLAUDE.md` §2.1、DEC-030 衝突，且無讀者，也無 DEC 指定正式來源（7.1 #8、#8a、#8c）。
- **總管推薦（待客戶裁示）**：確認 data.gov.tw／NDC／CIER 為 `observed_official`、第三方轉載（StockFeel／Cnyes／MoneyDJ）為 `observed_secondary`、stale-cache 為 `carried_forward`；**需客戶確認「第三方轉載可否滿足 Required Core」**。
- ⛔ 不得以 blanket rule 把 PMI 拿掉計分（DEC-077 3B）。⛔ 修正 `is_proxy` 語意屬資料語意變更（`PROJECT_RULES.md` 第 4 節 #2），裁示前不動。

#### Q6｜C2 與 VN1-PG 的邊界（DEC-077 方案 C）

- **C2**＝資料契約＋eligibility policy＋Risk Cap 依 policy 篩選（投資輸出變更，High＋完整 QA，DEC-078 A-2）＋揭露。
- **總管推薦（待客戶裁示）**：C2 拆兩段 ——
  - **C2a shadow**：只計算並記錄 provenance／eligibility／as_of，**不改計分**；可接 ledger 補欄（7.1 #10）。
  - **C2b**：實際套用 eligibility、改變計分。
- **VN1-PG**＝Risk Cap history production write，必須在 C2 契約裁示之後（寫入紀錄須帶 provenance 欄，schema 先定）。
- ⛔ **不得同一 PR**：(1) eligibility 計分變更＋production write；(2) 任何 UI 版面變更（`RC-VISIBILITY` 須線框草稿先行）＋計分變更；(3) 改 `is_proxy` 語意＋改計分。

### 7.3 三套方案比較（推薦＝總管推薦，待客戶裁示）

| 面向 | 方案 1｜嚴格 | **方案 2｜分層兩軸（總管推薦，待客戶裁示）** | 方案 3｜降權計分（不推薦，僅供比較） |
|---|---|---|---|
| data contract | Q1-A 單軸四類 | Q1-C 兩軸（provenance × freshness）＋`as_of`＋`source_id` | 兩軸＋每項 confidence 係數 |
| scoring eligibility | 只有 official 計分 | 逐指標 policy table（Q2：BIAS240 估算 3、PCR 法人估算 3、PMI 1） | proxy／estimated 乘 confidence 係數計分 |
| freshness eligibility | 只有 fresh 計分；不承認 carried_forward | Q3 矩陣；PMI carried_forward 在發布期內可計分＋揭露 | 依 freshness 再降權 |
| Core policy | 只接受 official（第三方轉載 PMI 不行）＋fresh | observed（official／secondary）＋fresh；PMI carried_forward 例外 | 降權後仍可滿足 Core |
| Optional policy | proxy／estimated 一律不計分 | proxy／estimated 不計分、只揭露、不阻斷 | 降權計分 |
| UI disclosure | 未評估清單變長；文字標籤 | 文字標籤（官方／轉載／估算／代理／沿用）＋未評估原因；上卡須線框 | 須顯示權重／信心，畫面最複雜 |
| provenance／as-of | 逐輸入記錄 | 逐輸入 `provenance`／`freshness`／`as_of`／`source_id`（additive） | 同方案 2＋係數 |
| Risk Cap 影響 | PMI 官方源失敗日 → Core 無效 → 「無法判定」天數增加；BIAS／PCR 估算日不計分 | BIAS／PCR 估算日不計分（上限可能改變）；PMI 可用性大致維持 | 每個估算日的上限都變，且數值取決於新係數 |
| migration | 先修 `is_proxy` → 改計分；`RISK_CAP_RULESET_VERSION` 升一次 | C2a shadow（不改計分）→ 客戶看 shadow 結果 → C2b 改計分；`RISK_CAP_RULESET_VERSION` 至多升一次（BACKLOG C2 列既有約束） | 須先另行裁示權重 → 改計分 |
| test impact | z66b `TestWriteGate`（第三方 PMI → Core 缺）、z63 `TestCacheVsFreshness`（stale-cache 不再滿足 Core）、z64 PCR 往回找、z62／z65 抽取與寫檔、c1_observability 零讀者守衛須改（政策變更）、i2_bias `TestFiveBucketZeroBehaviourChange`（若 16 燈同步，依 DEC-076 ①） | C2a：新增 additive 欄位測試；若 shadow 讀 `_pcr_src`，零讀者守衛須同批改；C2b：同方案 1 但 z63／z66b 的 PMI secondary／carried_forward 案例維持可計分；i2_bias 視 DEC-076 ① | 所有計分 golden 值改變；z64／z65／z66b 大改；新增權重測試 |
| backward compatibility | schema additive；歷史 parquet／快照不回填 | schema additive；歷史 parquet／快照不回填；舊快照缺欄讀為「未記錄」（不推定為 official） | 同左，但新舊上限不可比 |
| 風險 | 「無法判定」變多；第三方轉載 PMI 被排除可能讓 Core 常態性不足 | secondary 是否可滿足 Core 判錯；policy table 維護成本 | 違反「不得自行創造權重」；結果難稽核 |
| 優點 | 最保守、最易稽核 | 區分同量近似與不同量替代；Core 可用性與真實性平衡；additive schema；可先 shadow 再改計分 | 資料利用率最高 |
| 缺點 | 「無法判定」天數增加；仍需修 `is_proxy` | 多一層 policy table；secondary 能否滿足 Core 須客戶拍板 | 需新權重／門檻，違反治理（`PROJECT_RULES.md` 第 4 節 #1） |

> ⚠️ 推論（總管，未實測）：`is_valid_risk_cap_snapshot` 要求 `risk_cap_ruleset_version == "risk_cap.v2"`（`shared/risk_cap_policy.py:30,88-99`），所以 C2b 升版本號時，既有 v2 快照會立即失去「7 天沿用」資格，直到第一份新版有效快照寫入。C2b 設計時要明示這段空窗。

### 7.4 需客戶裁示的題目

~~本次共 6 個待裁示問題。~~ **6 題已於 2026-10-24 裁示（DEC-080）**（2026-10-24 有意識的更新，不是漏刪，決策者 客戶；DEC-080）。（商業語言；推薦一律「總管推薦，待客戶裁示」—— 送題時原文，保留）

1. **每筆資料要怎麼標示「官方、轉載、估算、代理、沿用」，以及哪些可以算分？（資料身分規則：方案 1／2／3，見 7.3）** —— 總管推薦：**方案 2（分層兩軸）**。理由：能分清「同一個量的近似值」和「另一個量的替代品」，必要指標不會因此常態性失效，也能先觀察再改分數。
   - ✅ **已裁示（DEC-080 第 1 點）**：**採方案 2**。provenance 與 freshness 分開表示；provenance 至少區分 official／secondary／estimated／proxy／unavailable；freshness 至少區分 fresh／stale／carried_forward；同時保留 `as_of` 與 `source_id`；⛔ 不得把 data exists、fresh、displayable、scoring eligible、Risk Cap eligible 壓成同一 boolean。`CV1-DR-11` 隨本題裁示。
2. **年線乖離（BIAS240）在歷史不足、用較短均線估算時，要不要退出系統風險上限的計分？** —— 總管推薦：**退出**（列「未評估：歷史不足、估算」；16 燈照樣顯示並標「估算」）。理由：它是選用指標，退出不會讓上限算不出來；而估算值已實證能讓上限從 40% 掉到 20%，反過來也可能讓上限被放寬。
   - ✅ **已裁示（DEC-080 第 2 點）**：**不參與 Risk Cap 計分**；可顯示、明確標示 estimated／歷史不足；對 Risk Cap 視為 Optional 未評估；⛔ 不得因此阻斷整個 Risk Cap。⚠️ 計分實際改變屬 **C2b**（未經另行裁示不得開始）；16 燈是否同步仍等 DEC-076 ①（客戶明令不併入本批）。
3. **PCR 在期交所抓不到、改用「三大法人未平倉」估算時，要不要退出計分？** —— 總管推薦：**退出**（只顯示、標「估算」）。理由：那是另一個量，原門檻是照期交所全市場 PCR 訂的。
   - ✅ **已裁示（DEC-080 第 3 點）**：**不參與 Risk Cap 計分**；可顯示、明確標示 `proxy_estimate`；只有符合正式 PCR 契約的資料才可用原 PCR 門檻計分；⛔ 不得把不同量直接套用官方 PCR 的既有 threshold。⚠️ 計分實際改變屬 **C2b**。
4. **台灣 PMI 來自第三方轉載網站、或八個來源都失敗時用的「沿用快照」，可以算數嗎？** —— 總管推薦：**可以，但畫面要寫出來源與「沿用」**；超出發布期就算「無法評估」（不產生新上限）。理由：PMI 是必要指標，一律排除會讓上限常常算不出來。
   - ✅ **已裁示（DEC-080 第 4 點）**：⛔ 不可套用 blanket「proxy 不計分」規則；data.gov.tw／國發會等正式來源修正為正確 provenance；**同一正式序列**的 secondary／republished value 可在契約允許下滿足 Required Core、須揭露來源；`carried_forward` 只允許在**正式定義**的發布期／freshness window 內暫時滿足 Core 並顯示「沿用」，超過 → unavailable → Core 無效 → 不產生新 Risk Cap。⛔ 不得自行發明發布期長度；repo 若無正式定義，先提具證據規格／Decision Gate（`docs/BACKLOG.md` `DH-PMI-PUBLICATION-WINDOW-SPEC`）。
5. **上限沿用前一份（最多 7 天）時，要不要在畫面寫明「沿用 N 天前的上限＋最舊資料日期」？（不改計算）** —— 總管推薦：**要**。理由：現在沿用時的實際資料可能已超過 10 天，畫面看不出來。⚠️ 上卡屬欄位增減，須先出線框（與 `RC-VISIBILITY` 一起送）。
   - ✅ **已裁示（DEC-080 第 5 點）**：**要揭露**（沿用的是 N 天前的 Risk Cap、本次判斷中最舊一筆有效資料日期、必要的 freshness／carried-forward 狀態）。屬 `RC-VISIBILITY` UI 規格：先出線框／文字草稿，⛔ 未經客戶確認不得直接改正式畫面。
6. **要不要先做一版「只記錄資料來源與是否可算分、不改任何分數」的觀察版，看過實際結果再決定改分數？（C2a shadow → C2b）** —— 總管推薦：**要**。理由：先看估算／轉載實際出現的頻率與影響，再決定改分數，風險最小、可隨時回退。
   - ✅ **已裁示（DEC-080 第 6 點）**：**先 C2a，再 C2b**。C2a＝observability／contract implementation（記 provenance、freshness、as_of、eligibility；建立 policy table／schema；⛔ 不得改任何 Risk Cap 分數、門檻、權重或投資輸出）；C2a 完成並取得實際觀測結果後，再送 **C2b Decision Gate**（見 7.7）；C2b 未經客戶另行裁示不得開始 scoring 行為修改。

> 📌 相關但**不在本題組**：`DEC076-CONFIRM` ①（指標危險度口徑）②（⚡ 行動例示射程）**仍未裁示**（DEC-080 額外邊界：維持 pending、分開處理，不與 C2 混批（2026-10-24 有意識的更新，不是漏刪，決策者 客戶；DEC-080））；第 2 題「16 燈是否同步不計分」與 ① 直接相關，C1′ 仍等 ①。`CV1-DR-11`（`PROJECT_RULES.md` 16.1／DEC-062 Q5 vs DEC-077 3B）隨第 1 題一併裁示。

### 7.5 仍禁止施工（裁示前，⛔）

> 📌 **2026-10-24 DEC-080 後現行範圍**（2026-10-24 有意識的更新，不是漏刪，決策者 客戶；DEC-080）（下列原文保留為裁示前紀錄）：**C2a 已指派**（observability／contract implementation；零投資輸出變更）。仍禁止：C2b（scoring 行為修改，須另行裁示）、C1′、DEC-076 ①②、VN1-PG production write（`PRODUCTION_WRITE_APPROVED=False`）、Daily Schedule、Risk Cap 公式／門檻／權重、Required Core 數量、新增或替換 production 資料來源、`RC-VISIBILITY` 正式 UI 改動（須線框／文字草稿先經客戶確認）。PMI provenance 修正（DEC-080 第 4 點）屬 C2a 的資料契約層記錄、計分行為不得改變；若修正會改變任何計分 → 延到 C2b。完整 ⛔ 清單見 `docs/BACKLOG.md` 5.1.10 C2a 列。

- C1′；C2 實作（~~**含 C2a**~~ C2a 已由 DEC-080 指派；C2b 仍禁止（2026-10-24 有意識的更新，不是漏刪，決策者 客戶；DEC-080））；VN1-PG production write（`PRODUCTION_WRITE_APPROVED=False` 不變）；
- Risk Cap 公式／門檻／權重；~~`is_proxy` 語意修正~~（DEC-080 第 4 點：正式來源修正為正確 provenance，屬 C2a 資料契約層、不得改計分（2026-10-24 有意識的更新，不是漏刪，決策者 客戶；DEC-080））；新增或替換 production 資料來源；
- `RC-VISIBILITY` 的任何 UI 改動（須線框草稿先行，`PROJECT_RULES.md` 第 4 節 #7）。

### 7.6 證據與限制（`CLAUDE.md` §-2 規則 6）

- 三組研究全部唯讀；C 組實跑用 mock session、外部 API 未打；未在 Streamlit Cloud／GitHub Actions 實測。
- 標「單組」者（7.1 #3、#6a、#6c、#7b、#8a、#8c、#9a、#9c、#10、#11、#12 前半、#13）只能當待驗事項，不得當施工前提。
- 「無讀者」「只有這些路徑」類全稱句來自 grep，屬單組或兩組窮舉宣稱，非形式化證明。
- 本節文字由單一撰寫組依總管規格整理，未經第二組逐字複驗；方案比較與推薦是總管判斷，**不是客戶裁示**。

### 7.7 C2b Decision Gate（新的待裁示 Gate；2026-10-24 新增，append-only）

> 依 DEC-080 第 6 點新增。**狀態：未送題（blocked：等 C2a 完成並取得實際觀測結果）**；⛔ 非授權。

- **送題時點**：C2a 合併＋main CI 綠＋取得實際觀測結果（例：BIAS240 估算、PCR `proxy_estimate`、PMI secondary／carried_forward 在 production 的實際出現頻率與對 Risk Cap 的影響）之後。
- **題目範圍（預定，待送題時定稿）**：依 DEC-080 已定方向（第 2、3、4 點）實際套用 eligibility、改變 Risk Cap 計分的時點與方式；`RISK_CAP_RULESET_VERSION` 升版與既有 v2 快照 7 天沿用空窗（7.3 末段推論，未實測）；揭露文字。
- ⛔ C2b 未經客戶另行裁示不得開始 scoring 行為修改；⛔ 不得與 production write、`RC-VISIBILITY` UI 改動同一 PR（7.2 Q6）。
- PMI 發布期／freshness window 的正式定義若仍未確認，須先依 `docs/BACKLOG.md` `DH-PMI-PUBLICATION-WINDOW-SPEC` 送具證據規格／Decision Gate，⛔ 不得在 C2b 自定數字。
