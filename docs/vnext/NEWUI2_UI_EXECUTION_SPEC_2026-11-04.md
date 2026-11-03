# New UI2 四頁 UI 施工說明（乾淨版；2026-11-04）

> **定位**：本文件是現行唯一 Active Presentation Contract 的**人類可讀施工附件**，不是第二套產品憲法。規則效力依序以客戶原文 DEC-128／129／130、[Active Presentation Contract](NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md) 為準。本文件只將其轉為可施工的版面與驗收清單；任何未核准的畫法均標「待線框核准／待 Gate」，**不藉施工附件創造新 Decision**。
>
> **新 UI2 施工只讀本文件＋Active Contract，勿再從 2026-11-02 舊線框中挑選 L2/L3 段落。** 舊線框、Freeze、Legacy 文件為歷史、差異查核與仍有效的非衝突語意參照；已被取代的呈現語句**不再是施工規則**。決策歷史維持 append-only。實際 src/UI 尚未因本文件改變。
>
> **本文 scope**：僅 presentation、文案、互動資訊架構；不授權修改 canonical、adapter、rule、threshold、Risk Cap、System Action、Decision Digest schema、OAuth／Sheet auth contract、正式資料來源或 OneBrain runtime。

## 0. 不可退化的六項設計原則

1. **Presentation Compression ≠ Information Loss**。Human UI 是精簡投影，OneBrain 讀完整、headless Decision Digest（不能以 UI ViewModel、top-N 卡片代替）；Data／Validation／Deterministic／Risk Cap／System Action／Complete Evidence 後分兩個 projection。
2. **簡單但不失判讀能力**：第一屏能回答「現在什麼狀態／是否需行動／依據／資料是否可信」。未有正式 action 或 Risk Cap 時顯示無法判定／未提供，禁止推算出假的結論。
3. **Chart-first 但不是 Chart Wall**：有正式資料與可解釋語意才畫圖；不混單位、不用誤導雙軸、不新造市場判斷。主要圖表附近放一行短 SPEC（標的／區間／頻率／單位／base／資料日／source／缺值，僅按該圖所需）；未知值顯示未提供，不手寫最新日。
4. **四頁不放整包 evidence**：不放「▸ 為什麼（L2）」、「▸ 指標明細（L3）」、「▸ 原始表／工程診斷（L3）」、raw JSON、traceback、PORT／Stage／Gate／Aggregator 等工程內文、全系統 Missing 清單。能留在 UI 的是少量可判讀 evidence／必要數字／一行 source-as_of-freshness；內部資料仍完整保存。
5. **資料健康度集中於「👤 我的」**：詳細來源／缺值／日期／freshness 與開發診斷集中，允許該專屬區內分層收合；不新增第五導航頁。
6. **桌機左側帳號、手機四格**：桌機 Logo／產品名稱→compact Login＋Auth Status→市場／標的／持股／我的；手機固定底部四項，登入由「我的」承接。狀態只能由正式 auth contract 提供，沒有時誠實標示未接線，不把 FAKE scenario／query string 當登入。

## 1. 橫跨四頁的版面／互動契約

| 區域 | 手機 390px | 桌機 1440px | 必驗 |
|---|---|---|---|
| 導覽 | 底部四格市場／標的／持股／我的，safe-area 不遮 CTA | 左側 compact rail，四主頁；Logo 下登入按鈕＋狀態 | 不出現第五格；auth 不是從 URL 推論 |
| 第一屏 | 狀態、正式行動／無法判定、主 CTA、資料可信度能看見或立即辨識 | 結論及狀態與主要圖上緣優先，不能被工程資訊推下 | 390／1440 截圖；不只依 DOM |
| 圖表 | 易讀高度、標軸／圖例、單行短 SPEC 可掃讀 | 主圖與輔圖分開，同單位比較 | 缺值不補 0、不偽造圖、來源與 as_of 真實 |
| 訊號／缺值 | 文字＋狀態，不以顏色單獨承載 | 同左 | OK／Missing／Stale／Unavailable／Not Evaluated，Capability 獨立 |
| 細節入口 | 能完成使用者任務的功能入口保留；工程原始資料不出現 | 同左 | UI 隱藏不能刪 VM sections／canonical／Digest evidence |
| Preview | 一般畫面 0 個 scenario／FAKE／Real 開發控制 | 同左，sidebar 不放 Preview | 僅 ?ui2_dev=1 或同等 dev surface，且不可當 auth |

> 首屏視覺排序依 DEC-127 與當頁有效契約；下表是內容責任、非逐像素 UI 核准。新區塊／重排版型依既有治理須先出文字線框草稿，不可假稱本文件已核准具體視覺設計。

## 2. 📊 市場

**手機內容順序（有效讀法）**
1. 頁首／「🚀 更新今日戰情」及不可用原因；更新時間須與**資料日期**分開。
2. 今日結論 → 市場目前狀態（正式五態）→ Risk Cap（未核准數值＝「⬜ 無法判定」）→ 是否需行動（只能沿正式 Action State；Aggregator 未備不得造 N）→ 今日主要風險；維持 DEC-127 已核准手機首屏順序與例外。
3. 「🤖 OneBrain Outlook」精簡槽；未啟用＝「⬜ 尚未提供」，coverage 不得叫 confidence。
4. 台股 Primary 主圖（真資料未接＝誠實 ⬜ 槽）＋一行 SPEC。
5. 台股／VIX／US10Y／利差／DXY／PMI·景氣等核心卡；每卡短狀態、source、as_of；國際 small multiples、VIX 帶、Macro mini、圖 C 研究空槽依正式來源可用程度展現，不得為填滿版面假造資料。

**桌機**：同一套語意；狀態／Risk Cap／今日主要風險可按仍有效 W-1／W-11、DEC-127 排為精簡 tiles，Primary 主圖優先露出；不得把完整 16 指標與位階診斷搬入桌機側欄。

**從投資主頁完全退役的舊 UI**：「▸ 為什麼（L2）」、「▸ 指標明細（16 項）（L3）」、「▸ 原始資料表／工程診斷（L3）」；位階規則分支、資料來源健康與完整 Missing 明細進資料健康度／Evidence；移除可見 ①②③④ 題號鷹架但保留必要測試錨點。圖與正式風險警示絕不可因移除明細而消失。

## 3. 🎯 標的

**手機**：頁首 →「市場精選／即時查一檔」模式 → 代碼／名稱搜尋（名稱未支援時明說）→ 精選候選或查單檔摘要。
- **市場精選**：產業機會 Top 5、候選 Top 10（沒有可靠來源則誠實缺值）；選股條件用**人類可讀的一行摘要**；保留「查看全部候選／CSV／查看此檔」作為次層**使用者功能**，不得當 raw evidence dump。
- **查一檔**：名稱／代碼 Header、六維 snapshot → 價格主圖＋SPEC → 基本面、EPS basis、估值、籌碼、產業、風險的簡短可判讀圖卡 →「🤖 研究解釋」槽。缺正式資料時不得假設數值或圖表；加觀察等寫入功能遵守既有禁寫 Gate。
- **基本面優先**：先判公司品質／成長／估值／產業，再用價格圖輔助進出場，不因 Chart-first 變成單靠技術線圖篩選。

**桌機**：可雙模式對應排列；內容不新增新選股規則，不用舊 L2/L3 expander。
**待裁示**：跨季趨勢／完整分析是否成為獨立**使用者功能**（不等於 L3 raw evidence）仍未核准。不得擅自刪除 backend evidence；UI 若尚未核准，標 backlog，不新增功能入口冒充核准。

## 4. 💼 持股

**手機**：頁首＋主 CTA → portfolio 狀態／Risk Cap／今日需處理（只用正式系統動作）→ 組合績效、benchmark、產業曝險、策略分布、集中度的少量必要圖 → 持股表／卡（股票、比例、成本、現價、報酬、策略、System Action，資料不足誠實未提供）→ 建議持股水位（若尚未正式可判定則 ⬜）→ OneBrain 持股摘要。
**桌機**：有效 W-11 三個 tiles 及主 CTA 在 header；圖表與持股列表避免資料牆。新增布局仍先文字線框。
**不可退化**：80/20、停利、換股、VaR、兩套刻度等*已核准使用者判讀能力*須維持精簡呈現；完整 rule IDs、判讀明細與原始資料仍存 Evidence／Digest，不在持股頁重新長回 L2/L3 expander。
**Gate**：P5 首屏與 Risk Cap／Action 語意牽連，依現有 Opus High Gate；本文件不授權實作。

## 5. 👤 我的／設定／資料健康度

**一般區**：登入與 Google／Sheet 連線摘要及主要 CTA **各只顯示一次**；portfolio／watchlist／策略／通知／顯示偏好；資料健康度入口；Audit／Decision Digest Viewer／Rule Registry **可保留但預設收合**，不搶主畫面。
**桌機**：側欄 compact Account Area 提供登入按鈕、狀態；頁內設定仍顯示較完整連線／選擇資訊，但**同一 auth contract**，不得出現兩種登入真相。真正 OAuth 仍需另案 auth contract Gate。
**手機**：「我的」為帳號與資料健康度入口；不新增底部項目。

**資料健康度範圍**：台股／國際市場、VIX、利率／DXY／PMI、景氣／產業／市場廣度／法人籌碼融資、個股價格／EPS 基本面／估值、持股／portfolio、Risk Cap／System Action inputs、Sheet 等已核准資料來源。若 canonical 尚無，顯示 capability 未接線而不是假 Missing。

| 層 | 畫面 | 邊界 |
|---|---|---|
| Level 1 | 總健康摘要；資料名稱、**狀態(Data State)** 與**接線(Capability)** 兩欄 | Data State 僅 OK／Missing／Stale／Unavailable／Not Evaluated；「⬜ 尚未接線」只在 Capability；不可混成第六態 |
| Level 2 | source、as_of、retrieved_at、freshness、missing／failed reason、provenance、proxy 標記 | 只顯示 canonical 真有的資料；無欄位寫未提供，不自行新增 contract |
| Level 3 | 開發／診斷（預設收合） | scrubbing；不曝光 key、token、env var、raw traceback／exception、module path、敏感訊息 |

**資料健康度不是另一個登入頁或第五主頁**。重新取數入口只能調用已核准 service／cache／cooldown／refresh pipeline；沒有安全 refresh contract 必須 disabled 並講原因。一般四頁仍可保留**一行資料可信度摘要／入口**，不能放完整 health list。

**仍待核准的撰寫組四項讀法**：Level 1／2 預設展開或收合、Level 3 是否限遮罩後診斷碼、Unavailable 在資料健康度使用紅色是否妥當、🎯 跨季趨勢使用者功能。任何人不得把它們自動升成客戶裁示。

## 6. OneBrain 與完整資料的邊界

\`Sources → Validation／Normalization → Deterministic Rules → Risk Cap／System Action → Complete Evidence → {UI VM, Decision Digest}\`。

- UI 只顯示短總結／圖表／主要 evidence／重要反證／限制；OneBrain 必須經由**完整、headless、機器可讀的 Decision Digest**讀所有已核准正式資料，不可只讀目前頁面或 Top N。
- Missing／Not Evaluated／Stale／Unavailable、source／as_of／freshness、counter-evidence、rules trace 不因 UI 隱藏而消失；Digest 應有的缺欄另案 Gate，**不能直接把所有 raw blob 丟給 LLM**。
- OneBrain 不得創造 objective facts、回寫 canonical、改 deterministic rules、覆寫 System Action／Risk Cap 或建立第二套動作權威；runtime 未正式核准前僅顯示「尚未提供」。

## 7. 過時規則清理清單（有效施工指令）

| 舊讀法／舊內容 | 現行處理（不能繼續施工） |
|---|---|
| 四頁強制 L2／L3 expander、16 項明細、原始表、全頁工程診斷 | **REMOVE FROM ACTIVE UI**；詳細證據維持 backend 或資料健康度 |
| 「資料中心」第五頁／第五導覽 | **REMOVE**；統一「👤 我的 → 資料健康度」 |
| 把 FAKE／Real／帳戶 scenario 放一般 UI 或 sidebar | **REMOVE FROM PRODUCT UI**；僅 developer surface |
| 把 Preview query parameter 當 auth | **FORBID**；auth 只能正式 contract |
| UI 能見欄位＝OneBrain 唯一輸入 | **REMOVE**；Digest 讀完整 evidence |
| 以缺值推算安全、HOLD、中性、Risk Cap 數值或「今日無需調整」 | **FORBID**；保留不可判定與能力分離 |
| 仍鎖死舊 expander／工程字樣的 tests／guards | **REPLACE** 成新 Active 行為測試；不得降低真正的資料／語意守衛 |
| Legacy 凍結／歷史 Decisions／先前已核准不衝突能力 | **PRESERVE HISTORICAL / KEEP**；不做破壞性刪除 |

**物理清理界線**：Active 施工文案應刪除／改寫失效語句；原始決策、歷史線框、歷史驗收證據受 append-only／freeze 保護，不能直接覆寫成新歷史。新 session **不得**把那些舊段落當有效指令。本文件中沒有任何「請恢復 L2／L3」的施工步驟。

## 8. 施工／驗收與 Safe Handoff

1. **此文件批次只處理文字，未修改 src／tests；也不表示 UI 已完成。** 已知 UI deviation 仍留給 P1～P7；不得為了視覺填空而改公式、資料或 VM schema。
2. UI PR 必須附真實手機 390px 與桌機 1440px 截圖、可判讀性、SPEC、缺資料場景、功能 parity、無敏感診斷曝險、正式資料未退化等證據。CI 綠只是必要條件，不等於 Visual Fidelity PASS。
3. 補齊 P1 控制隔離、P3 去 expander、P6 資料健康度、P7 左側登入，再處理其他已核准圖表／卡片；順序仍以最新 BACKLOG 和 GitHub 現況為準。
4. **禁止將本文視為 client approval for pending layout**：新的兩欄、Account Area、資料健康度細部版型仍先出文字線框送既有 Gate。
5. 下個 session 先讀 Active Contract 與本施工附件，再查 GitHub main、PR、CI、BACKLOG；不要以舊線框取代本文件。
