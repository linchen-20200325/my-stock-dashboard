# Presentation Contract vNext＋Visual SSOT（新 UI 呈現契約）

- **狀態**：正式／現行（Phase 1 SSOT Reset／Contract Freeze 凍結版）
- **日期**：2026-10-29　**基準**：PR base＝main `978ecedc`（撰寫時基準 `55739129`＝`978ecedc`＋#970 commit `06a7a3e5` 的 merge；`src/`、`shared/` 與 main 相同）
- **決策來源**：原則、Visual Budget、第一屏五問、主圖 header、下沉清單、chips 家族、三要素遷移、Missing 不變、硬規則、IA 不變、各頁方向＝**客戶 2026-10-29 指示（`docs/DECISIONS.md` DEC-109，逐字收錄）**；本檔的量化上限、詞彙表、讀法 R2～R15＝**AI 總管內部決定（DEC-110，依 `CLAUDE.md` §-1.5.D v3 §03-1）**，客戶可推翻任何一條，推翻後以客戶為準。
- 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-115，Phase 3 步驟 0 裁示）**：客戶裁示 D1a=A／D1b=B／D3=A／D5=A／D6=B／D8=B／D10=(a)（`docs/DECISIONS.md` DEC-115）。**就地加註處**＝§4（D10(a)：圖 A 配額）、§6（D3：chip 三族）、§8-4（D6：Secondary 缺資料縮一行）、§11（D8：切換鈕）、§14（D1a／D1b：色彩收斂時程）、§19（D5：迷你圖不顯示數字；站殼量測）、§22（W1 已裁示；W2～W9 不變）。原文一律保留、舊句加刪除線或註記。
- 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-117，Phase 4 步驟 0 裁示）**：客戶就 📊 市場頁線框（`docs/vnext/PHASE4_MARKET_PAGE_WIREFRAME_2026-10-30.md` §6）裁示 Q1=B／Q2=A′／Q3=A／Q4=P-B／Q5=B／Q6=A／Q7=A／Q8 全 A（`docs/DECISIONS.md` DEC-117）。本檔原文一字未改，**就地加註**於 §3（手機五問③ mobile exception）、§12.1（📊 市場第一屏、Primary 擇一、風險 tile 形式）、§15 R4（W9 結案）、§16（DEC-081 Q2-1 位置）、§19 Q2（手機排法）、§22（W2／W3／W9 結案）。**衝突處以 DEC-117 為準**；施工驗收條件見線框 §10。
- **上位**：`CLAUDE.md`（§-2 > §-1.5 > §-1 > §0～§8）> `PROCESS.md` > `PROJECT_RULES.md`＋`docs/governance/*` > 最新有效 DEC > **本檔（正式契約／Visual SSOT 層）**（位階全文見 `PROJECT_RULES.md` 第 25 節）。本檔**不改 `CLAUDE.md` 一個字**；與憲法表面衝突時走讀法（§15）或送客戶。
- **配套**：閘門＝`docs/governance/UI_VISUAL_FIDELITY_GATE.md`；AI 決策輸入＝`docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md`；AI 邊界＝`docs/vnext/ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md`；取代關係＝`docs/vnext/PHASE1_SUPERSEDE_MAP_2026-10-29.md`；施工＝`docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md`；現況量測＝`docs/vnext/visual_fidelity/phase1_baseline/VISUAL_GAP_AUDIT_2026-10-29.md`；工具＝`tools/visual_fidelity/`。
- **Scope Guard（客戶 DEC-109 三十）**：本檔**只遷移呈現責任**。⛔ 新資料來源、新投資公式、台股／國際趨勢公式、Risk Cap 算法、EPS×PE production rule、投資語意變更、大量 production UI 實作、無關歷史技術債。發現 → `docs/BACKLOG.md`。
- **標記**：**FACT**＝讀碼／渲染實測（附 `檔::符號`，行號只作「約 L」參考）；**INFERENCE**＝推論；**未驗**＝沙箱做不到。
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：本檔由單一撰寫組依五份單組調查（Inv-1～Inv-5）＋總管規格撰寫，**未經第二組獨立驗證**；所有「沒有／只有／全部」的全稱句是待驗事項。量化上限是依 blueprint 量測推出的**建議值**，不是客戶逐條核准的數字。

---

## §1 最高原則（客戶 2026-10-29 逐字，DEC-109 三、十五、十六、十九、三十四末段）

1. **簡化 UI，不簡化判斷。**（核心目標原文：「簡單看懂，但不犧牲判斷力。」）
2. **圖表 > 數字 > 短句 > 長文字。**
3. **Visual Priority does not mean Visual Quantity.**（不是圖越多越好。）
4. **Simple Decision Dashboard, not Report Wall and not Chart Wall.**
5. **Presentation Simplification must never reduce AI Decision Context.**
6. **Data View ≠ Decision Context ≠ AI Output.**
7. **One AI Brain, Many Data Views.**
8. **Conversation 不是 SSOT；GitHub 才是 durable memory。**（治理落點：`PROJECT_RULES.md` 第 26 節。）

讀法（DEC-110，內部）：第 2 條是「同一資訊選最省力的表達形式」，**不是**「為了有圖而新造資料」—— 沒有既有資料源的圖位一律畫 Missing placeholder（§8），⛔ 示意線、⛔ 回推；第 3 條限制第 2 條：圖的**數量**受 §2 Visual Budget 約束。

## §2 Visual Budget（每頁正常預算；客戶原文＋可測判準）

**客戶原文（DEC-109 三）**：每頁 1 個 Primary Visual；最多 2～3 個 Secondary Visual；第一屏最多 3～5 個核心數字／status chips；最多 1 句主要判讀；詳細證據預設下沉。超過時依序優先：1 合併 → 2 切換 → 3 下沉 → 4 收合。禁止：Report Wall、Chart Wall、第一屏同時多張大型圖互搶視覺權重、每個欄位各自畫一張圖、用大量 donut／pie 填滿頁面、把文字牆單純換成圖表牆。

| # | 預算項 | 上限（判準） | 計數規則（DEC-110 內部） |
|---|---|---|---|
| B1 | Primary Visual | **恰 1 個／頁**，**在第一屏可見**（至少 header＋圖上緣）（R2） | 一組 segmented／switcher 內的多張候選圖算 1 個（一次只顯示一張）；small multiples 作為 Primary 時整組算 1 個 |
| B2 | Secondary Visual | **≤ 3 個／頁**（建議 2） | 一組 small multiples 算 1 個；L2 展開後才畫的大圖不計入外露預算，但「一次只展開一張」 |
| B3 | 第一屏核心數字／status chips | **3～5 個** | 計「判斷用」的數字與狀態 chip；metadata chip（資料日／來源／窗口／可讀性，§6）**不計入**，但每張圖 header 的 chip 上限見 §4 |
| B4 | 主要判讀句 | **第一屏 ≤ 1 句** | 各卡「1 句摘要」不是主要判讀；主要判讀＝頁級結論（例 📊 今日結論句，DEC-081 Q2-1） |
| B5 | 第一屏同時大型圖 | **≤ 1 張**（＝Primary） | 「大型」＝高於 §3 Q4 small multiple 上限的圖 |
| B6 | 圓餅／donut | 每頁 **≤ 1 個**，且不得為 Primary | 只在比例本身是判斷依據時使用 |

- **超標處理順序（客戶原文）**：**合併**（同一問題的兩張圖併成一張或 small multiples）→ **切換**（segmented／switcher，一次一張）→ **下沉**（移到 L2 展開層）→ **收合**（摺疊）。⛔ 以「刪掉資訊」解決超標（§9 硬規則）。
- **禁止清單**＝上列客戶原文六項；Gate 檢查項見 `docs/governance/UI_VISUAL_FIDELITY_GATE.md` §2.2 V1～V5。

## §3 第一屏五問＋三層

**客戶原文（DEC-109 四）**：正常決策頁第一屏必須優先回答：1 現在狀態 2 重要數字 3 主要圖 4 是否需要行動 5 下一步。如果一頁無法明確回答「第一眼看什麼？第二眼看什麼？第三層才看什麼？」，則 **Visual Fidelity FAIL**。

| 五問 | 第一屏須可見的元素（判準） | 經客戶裁示的豁免 |
|---|---|---|
| ① 現在狀態 | 一顆狀態 chip／一張狀態卡（含 Missing 狀態 ⬜） | — |
| ② 重要數字 | §2 B3 的 3～5 個核心數字／chip | 數字未核准者以 ⬜ chip 替代（例 建議總持股水位 `⬜ 尚未核准／無法判定`） |
| ③ 主要圖 | Primary Visual 的 header＋圖上緣（R2） | — |
| ④ 是否需要行動 | ⚡ 需處理計數 chip，或誠實的「⬜ 無警示來源」 | 🎯 標的頁不放 ⚡（DEC-107 3A）→ 本問改由「候選標的已出現／未載入」回答 |
| ⑤ 下一步 | 主 CTA 或一句下一步 | — |

**三層**（每頁的 Gate 報告必須逐頁寫出這三行，寫不出＝FAIL）：

| 層 | 內容 | 預設 |
|---|---|---|
| **第一眼（L1）** | 五問：狀態、核心數字、Primary Visual（compact）、是否需行動、下一步；metadata chips；Missing chip；AI 投資總結入口卡（R13） | 外露 |
| **第二眼（L2）** | Secondary Visuals、Top-N 之外的完整清單、分組明細、進階控制項（更新模式；選股條件是否收合待 Phase 5 線框拍板）、大圖（點開才畫，一次一張） | 收合或位於第一屏之下 |
| **第三層（L3）** | 摺疊（主圖下方字樣＝`▸ 為什麼／來源／限制／去哪補`；卡片摺疊沿用「▸ 詳細」直到線框拍板，R7）：為什麼、資料來源、as_of、口徑、公式、threshold、policy reference、限制、Missing／unavailable 原因、去哪補、provenance、工程術語 | **收合，不得預設展開**（DEC-091 §一 Level 3 同向） |

- 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-117，Phase 4 步驟 0 裁示）**：**📊 市場頁手機版**的五問③「Primary Visual header＋圖上緣在第一屏」由客戶核准**合理 mobile exception**（Q7）：手機 Primary 可位於第一屏下方；手機第一屏優先序＝**今日結論 > 核心狀態 > 是否需行動 > Primary Visual**；⛔ 為塞主圖把結論或核心狀態擠出第一屏；**Primary 必須緊接 L1 決策區後方，不得被 L2／L3 長內容插隊**。桌機與其他頁不適用本例外（§2 B1 照舊）。Gate 登記見 `docs/governance/UI_VISUAL_FIDELITY_GATE.md` §8。

## §4 主圖 header 結構（客戶原文 DEC-109 五＋規格）

```
【圖表標題】                                                       ← 既有常數，不改字
〔資料 10/29〕〔來源 TWSE〕〔近 60 日〕〔✅ 可讀〕                   ← 3～5 顆 metadata／status chip（§6）
「近 60 日仍維持上升，但短線動能放緩。」                            ← 1 句白話說明
┌────────────── 圖（compact）──────────────┐
└──────────────────────────────────────────┘
▸ 為什麼／來源／限制／去哪補                                          ← 恰一個摺疊入口（預設收合）
```

- **順序固定**：標題 → chip 列 → 1 句 → 圖 → 摺疊。⛔ 圖上方放一整篇說明（客戶原文「不要在圖上方放一整篇說明」）。
- **chip 選擇（DEC-110）**：優先 metadata（資料日／來源／窗口）＋一顆可讀性（`✅ 可讀`／`⚠ 過期`／`⬜ 未提供`）＋必要的**語意護欄 chip**。超過 5 顆時，把語意護欄以外的 chip 移入摺疊；**語意護欄 chip 優先保留**。
  - 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-115，Phase 3 步驟 0 裁示）**：**D10=(a)**——圖 A（客戶範例 4 顆＋2 顆逐字護欄＝6 顆）外露 5 顆＝**資料日、窗口、可讀＋兩條護欄各自獨立**；範例中的「來源」chip **移入摺疊「來源」段**（資訊仍在、可追溯，不算刪除）。~~兩顆護欄合併成 1 顆、來源外露（草案 D10(b)）~~**未採用**；⛔ 為了把 6 顆壓成 5 顆而做出一顆過長、混合兩個語意的 chip。語意護欄優先於 metadata source（客戶要點）。
- **客戶逐字護欄**：`_market_blocks.CHART_A_MA_DISCLAIMER`「均線為參考，不等於正式台股趨勢判斷。」（DEC-092 Q2）作 chip 或作那 1 句時**逐字不縮寫**；趨勢結論位置固定 `_market_blocks.NOT_DEFINED`「⬜ 尚未定義」chip。⛔ mini 圖被讀成結論。 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-115，Phase 3 步驟 0 裁示）**：兩條護欄（`CHART_A_MA_DISCLAIMER`、`NOT_DEFINED`）**各自獨立成 chip、不合併**（DEC-115 D10(a)）。
- **那 1 句**：客戶原句（例 `CHART_A_SAY`、`CHART_B_SAY`）優先，**逐字、不截斷、不改寫**；沒有客戶原句時才由規則輸出／既有常數取，⛔ AI 生成、⛔ 自擬帶結論的句子（例「仍維持上升」若無既有正式規則輸出支撐，不得寫；客戶範例句只示範句型）。
- **摺疊內容**（固定四段，不適用寫「—」並說明）：為什麼（判讀說明、`Note.why`）／來源（source、as_of、TTL 說明引用 `shared/ttls.py` 等既有 SSOT）／限制（窗口、口徑、估算／代理、未驗）／去哪補（`Note.where`、`page_today.V2_EXIT_PHRASES` 對應短語或 `NO_EXIT_MARKER`）。

## §5 預設下沉清單（客戶原文 DEC-109 六）

**必須保留、正常情況預設收合**：為什麼、資料來源、as_of、計算口徑、公式、threshold、policy reference、限制、Missing 原因、unavailable 原因、去哪補、provenance、工程術語、service／helper／Lx 等工程資訊。

**主畫面只留**：狀態、關鍵數字、圖、1 句摘要。

- **例外（必須留在 L1 的 metadata）**：客戶既有裁示指定「卡面直接揭露」或「同位置顯示」者，以 chip 形式留在 L1（§16 對照表：價格旁資料時間＋來源 E17、Risk Cap 完整性 chip、外幣未納入逐字句等）。這些是**位置契約**，不受「預設下沉」吞沒（R5）。
- **工程字樣**（§18）在 L1／L2 一律 0；客戶自訂措辭例外（DEC-081 Q2-2「風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate」逐字保留）。

## §6 Shared metadata／status chips 家族（客戶 DEC-109 九＋R8）

**客戶原文**：優先建立共用呈現方式：source、as_of、retrieved_at（若既有）、stale、freshness、unavailable、estimated／proxy、coverage、data quality。不要每一張卡重複寫「這筆資料來自……目前資料日……可能因為……」，用 chip／metadata component 取代。

**R8（DEC-110）**：
1. metadata／status chips 是**獨立家族**，⛔ 不進 `src/ui_v2/components.BADGES`（封閉 11 種，禁第 12 種）。狀態徽章族（BADGES＋`shared/ui_state.UI_STATE_META` 十態）不動。
2. **🔴／紅色只給系統真錯誤**（`shared/ui_state` 的 failed 態；`CLAUDE.md` §1.A 第 4 點、v3 §02「系統真出錯才標紅」）。**stale 用 ⚠**（琥珀，非紅）。⚠️ **既有狀態徽章族優先**（既有徽章族沒有的「尚未定義／尚未核准」才用 metadata chip 既有字樣 ⬜）：凡 `shared/ui_state.UI_STATE_META` 已有的狀態，一律沿用其符號與文字——`⬜ 尚未載入`（idle）、`▨ 無資料`（empty）、`⟳ 缺漏 · 可重跑`／`⊘ 不適用 · 重跑無效`（客戶 2026-09-23 D-3(a) 三態 `⟳`／`⊘`／`◧`；`▨` 為既有 empty 態）、`◧ N／M 計入`、`⛔ 未接線`（unwired）、`🔴 取得失敗`；**⛔ 同一狀態出現兩種符號**（例：未接線不得另造 `⬜ 未接線`）。
3. **每個色塊都要有文字**（icon＋字，不只靠顏色；`PROJECT_RULES.md` §19.8）。
4. metadata chip 必須走**獨立渲染通道**：⛔ 塞進訊號文字頻道（`_ui_kit.assert_signal_text_clean` 以子字串比對狀態 glyph，⬜／⚠／🔴 進訊號文字會觸發 ValueError → 紅卡；FACT，Inv-1 #10）。PR #970 草稿 A.7「🔴 偏空」重用 🔴 為失敗態以外用途 → **不採用**。
   - 📌 **2026-10-30 事實更正（有意識的更正，不是漏刪；決策者 AI 總管（事實更正，依 v3 §03-1 內部自決））**：上句「⬜／⚠／🔴 進訊號文字會觸發 ValueError」中的「⚠」為假。實測（2026-10-30，`_ui_kit.assert_signal_text_clean`／`_BANNED_SIGNAL_GLYPHS` ＝ `UI_STATE_META` glyph ∪ `LEVEL_EMOJI`）：⬜、🔴 會 raise，⚠／⚠️ **不會** raise（`tests/test_p2_step1_shared_optional_params.py` 釘住此現況；現況不是承諾）。chip 走獨立通道的理由是**語意**（metadata 不是訊號文字），**不是**靠 ValueError 擋；⚠ 不被擋不改變本條結論。
5. 同一頁同一 metadata 事實在外露層**最多出現一次**（寫在最近的共同容器上），其他區塊不再重寫長句。
6. 取值**只能讀既有 SSOT**，⛔ 自算、⛔ 以按鈕時間冒充資料日（A 規格 §2.3）。
7. 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-115，Phase 3 步驟 0 裁示）**：**chip 外觀採三族（D3=A）**——**資訊**（資料日／來源／窗口）＝細外框膠囊、次要墨色；**狀態**（✅／⚠／⬜／⛔）＝淡底膠囊，icon＋字；**護欄**（`not_defined`、`not_approved`、`fx_*`、`data_quality`、`estimated`／`proxy`／`imputed`、逐字客戶句）＝**實線粗框**膠囊，不得收進摺疊。⛔ **不得新增會與既有 Missing／限制語意混淆的第四套視覺語言**；~~護欄用虛線外框~~（草案 D3 B）**未採用**——repo 內虛線已有「低層級／未接線／示意、未啟用」語意（低層級卡片、`⛔ 未接線`徽章），護欄不應長得像次要。紅色仍只給 `failed`、stale 用琥珀。兩條護欄各自獨立、不合併（D10(a)，見 §4）。

| kind | icon＋文字（例） | 取值 SSOT（只讀既有） |
|---|---|---|
| `asof` | `🕒 資料 10/28`（跨年 `2025/12/31`） | `Series.attrs["as_of"]`、`shared/staleness.py`；價格類 `shared/price_asof_label`（DEC-102） |
| `asof_missing` | `⬜ 資料日未提供` | `_market_blocks.DATA_DATE_NOT_PROVIDED`／`ASOF_CONTRACT_MISSING` |
| `source` | `來源 TWSE`／`來源 Yahoo` | `shared/price_asof_label.SOURCE_DISPLAY`；各 fetcher 的 `source` 欄（`CLAUDE.md` §2.2） |
| `retrieved_at` | `抓取 10/29 14:05`（**若既有**） | `fetched_at`（例 `macro_core.fetch_fred()` 已帶）；不存在時不顯示，⛔ 補 |
| `window` | `近 60 日` | 呼叫端實際請求的 n（例 `market_twii_view_service.get_twii_trend_view(n)`） |
| `readable` | `✅ 可讀` | 只在 live 態出現；degraded／partial ⛔ 掛 ✅ |
| `stale` | `⚠ 過期 N 天`／`⚠ 可能已過期` | `shared/staleness`、`is_stale`；⛔ 塗紅 |
| `freshness` | `⚠ 沿用前次` 等 | DEC-080 freshness 軸（`shared/input_provenance_policy.py`；`carried_forward` 無正式定義不啟用） |
| `coverage` | `8／16 項有資料`、`N 項未評估` | 既有覆蓋計數（危險度覆蓋、`risk_cap_gate` 完整性）；⛔ 寫成 confidence |
| `unavailable` | **沿用既有徽章族** `⛔ 未接線`（`UI_STATE_META[UI_UNWIRED]`）；「尚未提供」沿用既有字樣 `🤖 AI 投資總結：⬜ 尚未提供`（`HERO_AI_PLACEHOLDER`） | metadata chip 不另造符號 |
| `not_defined` | `⬜ 尚未定義` | `_market_blocks.NOT_DEFINED` |
| `not_approved` | `⬜ 尚未核准／無法判定` | `_market_blocks.WATER_VALUE` |
| `estimated` / `proxy` | `≈ 估算值`／`≈ 代理值` | 既有 `is_estimated`、proxy 旗標（DEC-080、`PROJECT_RULES.md` §16.1） |
| `imputed` | `≈ 含補值` | `is_imputed`／`ffilled_last`（`CLAUDE.md` §1） |
| `data_quality` | `⚠ 資料疑義` | 既有疑義旗標（例 融資單位混用，`CLAUDE.md` §1.A 第 2 點） |
| `fx_partial` | **逐字** `FX_PARTIAL_TEXT`＋`（N 檔）` | `shared/asset_currency_gate.FX_PARTIAL_TEXT`（DEC-101(1)） |
| `fx_tp` | **逐字** `停利未判：外幣`／`停利未判：幣別未確認` | `shared/asset_currency_gate.FX_TP_UNJUDGED_*`（DEC-102(4)） |
| `pretax` | `稅前` | 股利卡既有字樣 |
| `ai` | `🤖 AI 生成·非投資建議` | 既有 AI 揭露（DEC-054／055）的濃縮；全文仍在正文旁 |

- 新增 kind 只能在本表登記（Phase 3 落地為封閉集合常數＋測試），⛔ 各頁自創字串。
  - 📌 **2026-10-30 就地加註（Phase 3 QA 輪；有意識的補充，不是漏刪；決策者 AI 總管〔v3 §03-1 內部自決，不改客戶裁示內容〕）**：`topn_more`（Top-N「另 K 筆見全部」chip，§10 第 4 點；`compact.TopN.more_chip()`、`compact.KIND_TOPN_MORE`）是**本 §6 META 表之外的非 META 家族**，與 `status`（狀態 chip）、`guard_text`（逐字客戶護欄句）**同類**：歸**資訊族**（細外框）、文字由 `TOPN_MORE_FMT` 推導（K≥1）、同列最多一顆、不進 `META_KINDS` 封閉集合（放 `_EXTRA_KINDS`）。**M2 對帳（META_KINDS 與本表一一相等）不含它**——M2 對的是本表登記的 kind 集合，不是 `Chip.kind` 的全部值域。上句「新增 kind 只能在本表登記」仍適用於 **META** kind；非 META 家族的登記處是 `compact.py` 的 `_EXTRA_KINDS` 與其測試。
- 逐字客戶句作 chip 時**豁免字數上限、逐字不截**（手機可換行）。

## §7 「現在／為什麼／去哪補」正式遷移（客戶 DEC-109 七）

**客戶原文**：舊 contract 中「現在／為什麼／去哪補」承載的資訊不能刪除，但正式取消「三者必須全部常駐主畫面」。新 contract：**資訊必須存在、可取得、可追溯、可展開，但不要求全部外露。**

| 面 | 新契約 | 判準（Phase 2 測試據此改寫） |
|---|---|---|
| 存在 | `src/ui/tabs/tab_today.py::Note(now, why, where)` 三段非空的**資料契約不變**；非 live 卡必附 Note（`tab_today.Card`） | 既有 `test_p01_today_skeleton::TestEachCardIsHonest`／`TestFailLoud` 照舊 |
| 可取得 | 三段全文在該判斷的 L3 摺疊內可取得；**⛔ hover-only（`title=`）不算可取得**（手機無 hover，必須可點開） | 資訊守恆：舊頁每段字串在新頁「卡面 ∪ 摺疊 ∪ 既有 expander」某處出現 |
| 可追溯 | 摺疊內標明 source／as_of（或誠實缺值字樣） | provenance 欄位存在 |
| 可展開 | 摺疊入口恰一個、預設收合 | `expanded=False`；點開後內容齊全 |
| 卡面 | 狀態＋關鍵數字＋**≤ 1 句**（該句須為 Note 原文子字串，**K1 維持**） | K1 逐格驗；⛔ 新造句 |

- **取消**：「三段常駐卡面」「卡面三列短句」（客戶 2026-09-24、2026-09-25 程式碼註解裁示的**位置**部分被 DEC-109 取代，內容契約保留；見 `PHASE1_SUPERSEDE_MAP_2026-10-29.md` §2）。
- **維持並擴及手機**：客戶 2026-09-25「⛔ 完整原文不得只剩 hover」→ 本契約所有層級都適用（R6）。
- **舊測試改寫原則（客戶原文）**：測試驗證「三段文字一定要顯示在頁面」者，改驗：**資訊沒有遺失、正確資料可取得、詳細說明可展開、provenance 可追溯、Missing 語意未改**（逐條對照見 Migration Plan §3）。

## §8 Missing Contract 不變（客戶 DEC-109 八）

**不變**：missing ≠ 0；missing ≠ neutral；unavailable ≠ neutral；not evaluated ≠ safe；missing ≠ HOLD；AI 不得補值。（同 `PROJECT_RULES.md` §19.8、DEC-026、DEC-031、DEC-101(2)。）

**UI 顯示改成**：placeholder／chip／compact status card，⛔ 拿大段文字填滿頁面。

1. 外露形式：短 chip，**符號與文字先沿用 `shared/ui_state.UI_STATE_META`**（`⬜ 尚未載入`、`▨ 無資料`、`⟳ 缺漏 · 可重跑`、`⊘ 不適用 · 重跑無效`、`◧ N／M 計入`、`⛔ 未接線`）；既有徽章族沒有的才用 metadata chip 的 ⬜（例 `_market_blocks.NOT_DEFINED`「⬜ 尚未定義」、`WATER_VALUE`「⬜ 尚未核准／無法判定」，皆為既有字樣）；主值槽留白，⛔ 放 0／—％／中性字。
2. 完整原因與去處：在該判斷 L3「去哪補」段，⛔ 刪除。
3. 未載入＝灰 ⬜；系統真出錯＝🔴＋1 句原因（`CLAUDE.md` §1.A 第 4 點）；⛔ 滿版假紅字。
4. 圖的 Missing：~~圖槽保留同一 compact 高度~~（📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-115，Phase 3 步驟 0 裁示）**：**D6=B 調整冷啟動字面**——**Primary Visual 圖槽仍保留正式的同一 compact 高度／位置**，避免載入前後 layout jump；**Secondary／small multiples／mini 圖缺資料時縮為一行誠實 placeholder**，載入後撐開，避免手機與桌機出現大片無資訊空槽。⛔ **不得因此隱藏 Missing／unavailable 狀態**：那一行仍須依 `UI_STATE_META` 畫出符號＋原因，完整原因與去處仍在摺疊「去哪補」。代價：載入後下方內容下移一次。），內畫「⬜ <原因>」，**不畫任何線／點**（Primary、Secondary 皆然，不變）。
5. 未接線功能：只在進階／查看依據以一顆 `⛔ 未接線`（既有徽章族）＋一句白話揭露。
6. missing ≠ HOLD：持股列缺資料＝`⬜ 資料不足／無法判定`，⛔ 以「續抱」頂替（DEC-101(2)）；可判定部分照實、不可判定部分局部降級（DEC-102(4)）。
7. 重複的 Missing 說明（例 🎯 矩陣每列「⬜（僅有資金動能，非價格相對強弱）」）→ 寫一次在欄頭或區塊 header chip。

## §9 硬規則：UI 簡化不得減少的清單（客戶 DEC-109 十五，逐字）

**UI 可以**：少顯示、聚合、Top-N、收合、隱藏工程細節、圖像化、用摘要取代長文字。

**但不得因此刪除或降低**：canonical data、normalized data、provenance、source、as_of、stale／freshness、missing／unavailable、deterministic rule outputs、indicator outputs、Risk Cap inputs／outputs、market data、international data、sector data、candidate data、holdings data、strategy classification、identity、relevant history、AI Decision Context。

- 判準（DEC-110）：任一呈現改動 PR 必須證明 (a) 上列資料在 L3／Decision Digest／既有 service 輸出中**仍可取得**；(b) UI 的 Top-N、收合、未載入**不改變** Decision Digest 的內容（`DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md` §6 不變性測試）；(c) ⛔ 以 UI 顯示狀態作為任何下游（AI、推播、報告）的輸入。
- 策略分類（存股／資本利得／未分類）：**保留**；⛔ AI 推論分類；沒有既有可追溯設定一律 `⬜ 未分類`（DEC-091(e)、DEC-092 Q1）。

## §10 Top-N（客戶 DEC-109 十二＋R9）

**客戶原文**：Top-N First：產業、候選、風險、排名預設 Top 5～10，其餘收合。

R9（DEC-110）：
1. **Top-N 只是顯示切片**：只取前 n 筆、保序、保物件同一性；⛔ 改排序、⛔ 改篩選、⛔ 重算分數。
2. **L3 請求參數不變**：`src/ui/views/page_find.TOP_N_OPTIONS=(20, 50, 100)`、`DEFAULT_TOP_N=50`（FACT）維持。
3. **Digest 與 AI 不受 Top-N 影響**：Decision Digest 由 canonical data＋正式規則結果建立，⛔ 讀 UI 切片（`ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md` §3）。
4. 外露 Top-N 之下恰一個「▸ 查看全部（N 筆）」入口；截斷時顯示「另 K 筆見全部」chip（沿用 `_market_blocks.HERO_RISK_MORE_FMT` 模式）。
   - 📌 **2026-10-30 就地加註（Phase 3 QA 輪；決策者 AI 總管，內部自決）**：「另 K 筆見全部」chip 的 builder＝`compact.TopN.more_chip()`，`Chip.kind="topn_more"`，是 §6 META 表**之外**的非 META 家族（與 `status`／`guard_text` 同類，見 §6 表後註），M2 對帳不含；`hidden=0` 時不產生（ValueError，⛔ 不出 K=0 的假 chip）。「查看全部」入口的**外觀**（現在只是文字，不像入口）待 Phase 4 線框。
5. 排序依據寫一次（例 `_target_blocks.ZONE1_SORT_NOTE`「排序依據：法人資金動能，非產業趨勢。」，DEC-092 Q5，字樣不改）；由現行說明句改為區塊 header chip 與否＝Phase 5 線框待客戶拍板點（§22）。
6. 沒有排序依據的清單（例 風險 hero 依五桶固定順序，`HERO_RISK_NO_RANKING_NOTE`）→ Top-N 只是「前 N 個依固定順序」，⛔ 自創重要性排序。
7. 建議預設 N（內部，可調）：產業 5、候選 10 列（表）或 5 張（卡）、風險 hero 3（既有 `HERO_RISK_MAX_ITEMS`）／圖 D 5、持股需處理 5、例外代號 5。

## §11 摺疊、標籤與運算（R7、R10）

- **R7 摺疊標籤（2026-10-29 總管改判後範圍）**：**主圖 header 下方**的依據入口用 **`▸ 為什麼／來源／限制／去哪補`**（客戶 DEC-109 五明確給定）。**卡片摺疊標籤**「▸ 詳細」（客戶 2026-09-25 核可線框逐字，`src/ui_v2/markup.FOLD_SUMMARY_TEXT`）與各頁「🔍 查看依據」**維持有效**；是否統一換成新字樣＝各頁 phase 線框待客戶拍板點（§22）；內容不變。客戶裁示或測試釘住字面的**具名 expander 不改名**（例 `_market_blocks.LAMP_DETAIL_EXPANDER_LABEL`「指標明細（16 項）」，DEC-105 指路目標）。
- **R10 expander 不省運算**：Streamlit expander body 每次 rerun 都會執行（FACT，Inv-2 T26）→ **收合 ≠ 省運算**；既有 button／checkbox／form gate **全部保留**，重運算仍走 gate。
- `st.form` 內放 `st.expander` 在 `requirements.txt` floor 1.56 的行為**未驗**（沙箱 1.59.2）；未驗前改用「form 外 expander 放進階控制項＋form 內只留主鍵」的保守排法。
- ⛔ 任何資訊只活在 `title=` 屬性（`page_today.V2_HOVER_ONLY_FACTS`／`V2_HOVER_OPTIONAL_FACTS` 於 Phase 4 起移入摺疊）。
- 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-115，Phase 3 步驟 0 裁示）**：**D8=B segmented／switcher 外觀＝膠囊式切換鈕**（取代舊總經頁圓點單選的樣式偏好；該偏好唯一出處為舊頁程式註解、無對應 DEC）。**前置條件**：必須先在最低支援 Streamlit 1.56（`requirements.txt` floor，現場讀取）**實跑驗證** API、行為與手機互動（`P1R-FLOOR-156-API`）；**不成立 → 直接退回 A 圓點單選（`st.radio(horizontal=True)`），不需再次請示客戶**；⛔ 不得為了 B 升高最低版本。退回時須在交付報告第 2 段揭露。D5 同屬 Phase 3 新增記錄見 §19。

## §12 IA：正式四頁不變＋各頁方向

**客戶原文（DEC-109 十）**：不要因這次改造自行增加或刪除頂層頁面。維持 1 📊 市場 2 🎯 標的 3 💼 持股 4 👤 我的。若發現現有正式 spec 與此不一致：先做 conflict analysis，不要自行改 IA。（FACT：`shared/ia_nav4.PAGE4_LABELS` 恰為此四頁，`reconcile_nav4` 強制恰好 4 頁；與 DEC-091 §二、DEC-097、`d25_wireframes/index.html` 一致。）

### 12.1 📊 市場 —「現在市場環境好不好？可以承擔多少風險？」

| 項 | 規格 |
|---|---|
| 第一屏 | 市場位階（DEC-105 2A 五態＋「市場位階，不是台股趨勢」）、Risk Cap／尚未核准狀態（`WATER_VALUE`＋Q2-2 逐字句）、今日主要風險（≤3 chip＋「指標危險度」指路，形式待 Phase 4 線框拍板）、是否需行動（⚡ 計數）、今日結論句（DEC-081 Q2-1）、**主要市場圖** |
| Primary Visual | **市場環境主圖**：一張 compact 圖＋segmented／switcher（台股｜海外市場｜利率｜美元，**只用既有序列**：圖 A 加權指數＋`_market_blocks.INTL_GROUPS` 既有 5 系列），預設台股；或改以 small multiples 呈現（擇一，Phase 4 依 Gate 決定）。⛔ 同時把全部畫成大型圖 |
| Secondary | ≤ 3：例 國際 small multiples（若 Primary 用 switcher）、圖 D 五桶風險 compact view、圖 C 大盤合理區間 placeholder |
| EPS×PE | 未核准 → 維持 placeholder（`CHART_C_EMPTY`）／`⬜ 尚未核准`；⛔ 為畫面完整自建公式或假圖 |
| 下沉 | 更新模式 radio 與長說明（L2 更新選項）、位階卡三列與 `REGIME_SCOPE_NOTE`（L3）、`WATER_WHY`／`WATER_REPORT_DISCLOSURE`（L3）、圖 D 完整表（L2）、「生效分支 warroom」等工程字 |

- 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-117，Phase 4 步驟 0 裁示）**（上表原文保留；衝突處以本註為準）：
  - **第一屏順序（Q5=B）**：頁首 → 更新 CTA → 今日結論 → 3 個核心狀態 → ⚡需要處理 → AI／資料狀態 → Primary Visual（取代 DEC-105 1A 在市場頁的舊相對順序）。
  - **核心狀態（Q1=B）**：桌機 3 個 tile（市場位階／建議總持股水位／今日主要風險）；「🚀 更新今日戰情」為**頁首主 CTA**、不占 tile；手機 2＋1。
  - **今日主要風險（Q6=A／Q2=A′）**：上表「≤3 chip」由**≤3 行縮短行「燈色＋桶名＋燈名＋方向」**承接（chip 無對應 kind，線框 F-2）；完整原句等進摺疊；退化／護欄句（未評估不等於安全、資料不足／無法判定、尚未載入、真錯誤）外露逐字；「指標危險度」指路**維持說明句**（縮短、保留三要素、不新增 chip）。
  - **Primary Visual（Q4=P-B）**：上表「segmented／switcher **或** small multiples（擇一）」定案為 **🇹🇼 台股趨勢（圖 A）＝Primary**（原生圖、MA 參考線、y 軸、圖例），**國際 5 系列＝Secondary small multiples**，**不做切換列**；小倍數不顯示數字；詳細數值留 L2；趨勢正式定義不變、未定義顯示 `⬜ 尚未定義`。
  - **下沉（Q8 全 A）**：圖 C 完整原句→「為什麼」；更新模式 radio＋長說明→「更新選項」；⚡→一行 bar＋展開清單；資訊只能下沉、不得刪除。
  - **摺疊標籤（Q3=A）**：圖用「▸ 為什麼／來源／限制／去哪補」；tile／⚡ 維持「🔍 查看依據」。

### 12.2 🎯 標的 —「現在有哪些值得看的產業與股票？」

| 項 | 規格 |
|---|---|
| 優先修（客戶原文） | 不要再：先攤開 30～40 個產業長卡；每個產業重複顯示相同 Missing 說明；候選標的被推到很後面 |
| Primary Visual | **產業強弱／資金動能／機會分布**：Top 5 ranking／heatmap／bubble／compact sector tiles 擇一，**資料＝既有 `target_industry_service` 矩陣列**，⛔ 新算法；排序依據句「排序依據：法人資金動能，非產業趨勢。」寫一次（DEC-092 Q5；說明句 vs chip＝Phase 5 待拍板） |
| 完整產業清單 | 收合／drill-down（L2） |
| 候選標的 | **提前**（客戶原文）；候選 Top-N（§10，DEC-109 十二）＋「查看全部」。在 DEC-107 1A 頁面順序內如何提前（例 第二區 header 是否須進 desktop 第一屏）＝Phase 5 線框待拍板（§22）。**選股條件維持 DEC-107「預設展開」**；在 Visual Budget 下是否改為預設收合＋一行條件摘要 chip＝Phase 5 線框待客戶拍板點（R3，總管 2026-10-29 改判） |
| 單一股票 | 先摘要卡（≤4）＋主圖，再展開完整分析（七區塊／ETF 三卡原樣）；「判型結果」卡縮為 chip `🏢 個股 · 自動判型`，明細入 L3 |
| 互動不變 | 「選一檔＋🔍 查看此檔」（DEC-107 2A）、籌碼只取選取檔（4A）、估值口徑揭露（chip＋L3 全文，⛔ 刪）、不放 ⚡（3A） |

### 12.3 💼 持股 —「我的持股該加、留、換、減什麼？」

| 項 | 規格 |
|---|---|
| 第一屏 | 目前該做什麼、需處理幾檔、加碼／留／換／減摘要（計數來源＝既有 `dividend_station_service.build_station_digest`，⛔ 新語彙）、主要風險、組合狀態、Primary Visual |
| Primary Visual | 依實際資料擇一：持股配置／風險分布／損益分布／核心衛星（**僅能標「依 ETF／個股種類近似，非投資目的」**）／主要曝險；資料不足 → placeholder |
| Secondary | ≤ 3（例 VIX sparkline、燈牆 compact grid、現金流 compact bar＋`稅前` chip） |
| 不得全部第一層外露 | VaR、壓力測試、配息、完整規則、門檻、分母（客戶原文） |
| 兩套刻度 | DEC-017 葉1 ②「兩套刻度…常駐揭露 · 非摺疊」**維持有效**；在 Visual Budget 下是否改為 L1 一顆 chip＋完整雙表可展開＝Phase 6 線框待客戶拍板點（§22） |
| 投資目的分類 | 存股／資本利得／未分類**保留**；⛔ AI 推論分類（客戶原文「AI 不得自行推測分類」） |
| 骨架 | blueprint `holdings.html`＝AI 摘要 → ⚡ → 🌱 → 📈 → ⬜ 未分類（A 規格 §4.3）；現況＝兩葉 tab＋①～⑦（FACT，Inv-3）；骨架重排屬 Phase 6 |

### 12.4 👤 我的 —「不是分析頁」

客戶原文：這頁不是分析頁，不用硬塞圖表。主要承載：Google／account、Sheet、portfolio、watchlist、strategy classification、低頻設定、資料健康／診斷入口。→ **Visual Budget 不適用 Primary Visual 要求**（Gate 第 1、3 項以「設定卡結構」判）。

## §13 IA 衝突分析（客戶 DEC-109 十、十四、二十；Inv-5 §5；稽核勘誤併入）

### 13.1 一致處（FACT）

- `shared/ia_nav4.py` `PAGE4_LABELS`＝📊 市場／🎯 標的／💼 持股／👤 我的；`reconcile_nav4` 強制恰 4 頁；與 DEC-091 §二、DEC-097、`d25_wireframes/index.html`（「桌面左側欄、手機底部列」）一致。

### 13.2 不一致處（FACT；本 phase 只登記，⛔ 改 IA）

| # | 不一致 | 處置 |
|---|---|---|
| 1 | `shared/ia_nav.py` legacy `PAGE_LABELS`（📊 大盤／💼 我的持股…）；新模式 💼 頁標題仍印「## 💼 我的持股」（`page_hold` 約 L5732） | 既有 `NAV1-WAYFINDING-I1`；Phase 6 一併處理 |
| 2 | A 規格 §3.2 推薦 N2「頂端控制列」、§3.4、E1／I-11 未標過期；DEC-098 第 7 點已判 A 規格才是偏離者 | supersede map 標記；A 規格不改內文 |
| 3 | `PROJECT_RULES.md` §11 仍把 `VNEXT_PRODUCT_BLUEPRINT.md` 當新 UI 必讀 | 本 phase 已改指本契約（刪除線＋現行） |
| 4 | blueprint `index.html` 圖例（「🟢偏多　🟡中性　🔴偏空　⬜無法判定」）與 `market.html` 首屏圖例「🟢偏多 🟡中性 🔴偏空」、A 規格 §4.1.1「市場狀態 🟢偏多／🟡中性／🔴偏空」、DEC-091 §四同字樣 | **被 DEC-105 2A 取代**（市場位階五態「多頭／震盪／轉守／空頭／未評估」，⛔ 映射成偏多／中性／偏空）。HTML 不改，取代關係登記於 supersede map 與本條 |

### 13.3 🤖 AI 投資總結入口（R13）

- FACT：DEC-091 §三／A 規格 §5：桌面頁首右上／上方明顯區、手機首屏 compact 卡、**不是第五個主導航頁**；`ai_summary.html` 為展開態；現 📊／🎯 為 `HERO_AI_PLACEHOLDER`／`AI_PLACEHOLDER`「🤖 AI 投資總結：⬜ 尚未提供」佔位，💼 為 ⑦ 付費按鈕（約頁面底部）。
- **R13**：AI 投資總結入口＝**各頁 L1 固定元素**（E2 卡＋展開面板；桌機展開面板、手機全螢幕面板），**計入 Visual Budget**（算 1 張卡，不算 Primary／Secondary Visual）。不是第五頁，**IA 不變** → 不需 page-count Decision Gate（客戶 DEC-109 二十）。
- 收合態只顯示本頁 slice（市場→市場段＋主要風險；標的→標的機會；持股→持股＋本期行動），slice 規則見 `ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md` §4。新輸出格式（R12）見同檔 §5。

### 13.4 👤 我的 Google login 位置（R14）

- FACT：`app.py` 側欄「🔐 Google 帳號」登入／登出／Sheet ID 區塊與 nav4 模式分支**同層**，預設 nav4 模式也會渲染（約 L430–531）；`mine.html` 把 Google 帳號放在 👤 我的主區卡①、左側欄只有 4 個導覽項；DEC-083 第 1 點（Q1：👤 我的為 Google 帳號、Sheet 綁定的**唯一**設定入口）與第 11 點（E 段 Removal Gate：Google 側欄**暫時保留**）並存 → **現況兩個入口並存**。手機側欄為收合抽屜（A 規格 §3.1；斷點約 640px，INFERENCE），「固定左側」在手機上看不到。`page_me` 約 L133／L233 的「請在側欄再選一次」等指路句在 nav4 預設與手機底部列下已過期。
- 衝突：把 Google login「固定左側」會同時違反 mockup、「唯一入口」原則與手機約束。
- **R14 處置**：正式位置維持 **👤 我的卡①**；舊側欄登入區塊是否在預設模式隱藏屬**版面異動**且碰 DEC-083 E 段 → 登 BACKLOG `P1R-GOOGLE-LOGIN-SIDEBAR-GATE`，為**未來客戶 Gate**（本 phase 不問、不改）。`page_me` 指路句歸 `NAV1-WAYFINDING` 類。
- 不直接照搬其他專案（客戶原文「不要直接照搬其他專案」）。

## §14 Visual SSOT：blueprint 與 tokens（R15）

### 14.1 定義（客戶 DEC-109 二十四原文）

核准 blueprint 不再只是參考圖。正式定義：**blueprint = Visual SSOT / visual acceptance baseline**。Production 可以因真資料、Streamlit 限制、mobile constraint 做合理調整；但不可自行改掉：第一屏資訊順序、主圖／次圖層級、資訊密度、圖文比例、card hierarchy。若必須明顯偏離：開 Gate。

- **blueprint 檔**＝`docs/vnext/d25_wireframes/{index,market,target,holdings,mine,ai_summary}.html`（DEC-092 設計方向核准）。**本 phase 不改任何 HTML。**
- **R15（DEC-110）**：blueprint＝**視覺驗收基準**；`src/ui_v2/tokens.py`＝**實作 token 來源**。兩者色值不一致時 **blueprint 為準**，~~tokens 於 Phase 3 收斂~~（BACKLOG `P1R-TOKENS-CONVERGE`）——**客戶裁示的色值除外**（下方 ⚠️；總管 2026-10-29 改判）。 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-115，Phase 3 步驟 0 裁示）**：**D1b=B**——**非客戶裁示的色與圓角延到 Phase 4～6 逐頁收斂**（各頁依核准線框重做時一併換，屆時有該頁完整 Gate）；Phase 3 **不全站換膚**：只加性新增幾何 token（chip 膠囊半徑、14px 卡圓角〔只新增、不套用〕、觸控區等），**不改任何既有色值**，`markup.page_css()` 輸出 byte-identical。**D1a=A**——客戶裁示色（CTA 主色 `#1f6feb`／light `#044cb6`；`--sig-neutral`／`-bg` dark `#8fa3b8`／`#26313d`；light 中性暫值照現況）**維持**，不因共用元件重做而改色。代價：過渡期既有頁與 blueprint 基準不一致（BACKLOG `P1R-P3-D1B-TRANSITION-PALETTE`）。
- **後續客戶裁示覆蓋 blueprint 的地方（不算偏離）**：DEC-105 2A（市場位階五態，取代 `index.html`／`market.html` 圖例的偏多／中性／偏空用語）；DEC-107 2A（「選一檔＋🔍 查看此檔」取代 `target.html`「點一列展開」）；DEC-107 3A（標的頁不放 ⚡）；DEC-109 R12（AI 投資總結新輸出格式取代 `ai_summary.html` 五段）。
- **允許的合理調整**（不需開 Gate，但 Gate 報告須逐項列出）：真資料字串長度／列數／缺值（示意數字一律以真值或 ⬜ 取代）；Streamlit 限制（`st.columns` 手機塌單欄→以 HTML／CSS grid 補 2×2（排法待 `CV1-DR-12`／W9）、無 hover、Vega 圖軸無法完全隱藏 INFERENCE）；誠實揭露 chip 比 blueprint 多。
- **明顯偏離（必須開 Gate）**：見 Gate 文件 §5。

### 14.2 blueprint vs tokens 差異表（FACT，讀檔；量測日 2026-10-29）

| 面 | blueprint（`market.html` `:root` 與規則） | `src/ui_v2/tokens.py`／`components.py`（dark） | 處置（R15） |
|---|---|---|---|
| 頁底 | `--bg #0a0e16` | `--paper #0e141b` | blueprint 為準，~~Phase 3 收斂~~ Phase 4～6 逐頁收斂（📌 見本表下方註記／DEC-115 D1b=B） |
| 面板 | `--panel #0f1521` | `--panel #151d26` | 同上 |
| 卡片 | `--card #151d2c`、`--card2 #1a2437` | `--panel-2 #1b242f` | 同上 |
| 線 | `--line #26334a` | `--rule #2e3b48`、`--rule-2 #46545f` | 同上 |
| 主文字／次文字 | `--tx #e8edf7`／`--mu #a9b5ca` | `--ink #dbe5ef`／`--ink-2 #9fb0c1`／`--ink-3 #7d8d99` | 同上 |
| 強調／好／警／壞 | `--ac #5aa9ff`／`--ok #5fd18a`／`--wn #f2b84b`／`--bd #ff7a7a` | `--sig-blue #4b8efe`／`--sig-green #57b985`／`--sig-amber #d3a43c`／`--sig-red #e8706b` | 同上 |
| 卡片圓角 | `border-radius:14px`；chip `999px` | `components` 卡 `radius_px 2.0`、徽章 `3.0` | blueprint 為準（幾何以加性 token 新增，不改既有值） |
| 字級 | 頁標 22px／卡標 13px／大數 26px | 卡值 24px（`CARD_VALUE`） | 同上 |
| hero 網格 | `repeat(auto-fit,minmax(170px,1fr))`，gap 12px；手機 `@media(max-width:500px)` | `MAX_COLS=3` | 欄數牴觸見 §15 R4（`CV1-DR-12`，待客戶裁示） |

- 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-115，Phase 3 步驟 0 裁示）**：上表「處置（R15）」欄的「blueprint 為準，Phase 3 收斂」＝~~Phase 3 收斂~~，**現行讀作「blueprint 為準，Phase 4～6 逐頁收斂」**（D1b=B；**指向 DEC-115 D1b：未裁示的顏色與圓角延到 Phase 4～6 逐頁收斂，Phase 3 不改任何既有色值，上表各列「同上」一併適用**）；「卡片圓角」列的加性 token 於 Phase 3 新增、**不套用**（Phase 4 線框確認）。
- ⚠️ **待總管處理的事實（FACT，不改判 R15）**：`tokens.py` 內至少兩組值的註解自陳為**客戶裁示**：`--sig-neutral`／`--sig-neutral-bg`（「客戶 2026-09-21 裁示」）、`--cta-primary-bg #1f6feb`（「客戶 2026-09-22 裁示逐字：接受 Streamlit config 的 primaryColor #1f6feb」）；blueprint 無對應 token。依 `PROJECT_RULES.md` §0.1「對既有裁示的任何變更需要新的客戶 Decision」，**這幾個客戶裁示色值維持有效、不在 R15 射程內**；是否改為 blueprint 色值＝Phase 3 草稿待客戶拍板點（`P1R-P3-WF-CUSTOMER-COLORS`；§22）。 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-115，Phase 3 步驟 0 裁示）**：**已裁示＝維持**（D1a=A）。「哪些 token 屬客戶裁示」為撰寫組讀碼所見，**未經第二組驗證**。

## §15 呈現位階與讀法（R4、R16 摘要）

- **呈現 precedence**：舊 helper／test／wireframe 的**呈現要求**與本契約衝突時，以本契約＋blueprint（新 Visual SSOT）為準（客戶原文範圍）；**客戶 DEC 的呈現裁示只有在 DEC-109 或同日前序指示（2026-10-29T15:18Z，DEC-109 附錄）明確點名處才被取代，其餘一律「維持＋列入該頁 phase 線框待拍板」**（§22）；**只遷移呈現責任**。**資料、投資、安全規則仍取較嚴者**（Missing 語意、DEC-031、Risk Cap、AI 揭露、No Look-ahead、Sheet Safety…）。客戶既有裁示的**內容**保留、只換位置（§16）。完整兩軸位階見 `PROJECT_RULES.md` 第 25 節。
- **PROJECT_RULES §19.11「衝突時以較嚴者為準」的呈現讀法**：「較嚴」在資料／投資／安全面照舊；在**呈現位置**面以 Visual SSOT 為準（「外露」不因字面較多就算「較嚴」）。
- **R4（2026-10-29 總管改判；本行為本 PR 內撰寫之文字，直接改寫）**：`CLAUDE.md` v3 §00「固定 3 欄自適應網格」與 DEC-091 §四客戶指定「第一列只放 3～4 個核心狀態」／現行市場 Hero 4 欄（DEC-105 第 5 點登記為 P2 偏離）之間的牴觸，**本檔與 DECISIONS 不重新解釋 `CLAUDE.md`**：登 BACKLOG `CV1-DR-12` 待客戶裁示，並列為 Phase 4 線框待拍板點 W9（§22）。裁示前**維持現狀**（Hero 4 欄照舊、卡片網格 `MAX_COLS=3` 照舊），Visual Fidelity Gate 對 **KPI 列欄數暫不判定**；手機 KPI 2×2 同屬此題。
- 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-117，Phase 4 步驟 0 裁示）**：上一條 R4 所登的牴觸已由客戶裁示結案（DEC-117 Q1；BACKLOG `CV1-DR-12`）：📊 市場頁**桌機 3 個核心狀態 tile、手機 2＋1**；客戶明示「**「固定 3 欄」是桌機核心狀態網格要求，不代表手機必須硬排 3 欄；手機應依可讀性自適應。**」——此為**客戶本人**的解釋（記於 DEC-117），**`CLAUDE.md` 一字不改**；R4「本檔與 DECISIONS 不以總管讀法重新解釋 `CLAUDE.md`」仍有效。Visual Fidelity Gate 自此對 📊 市場頁 **判定 KPI 列欄數**（桌機 3、手機 2＋1）；其他頁的 KPI 列仍依各頁線框。

## §16 既有客戶裁示：內容保留、只換位置（R5、R6）

| 裁示 | 必須保留的內容（⭐＝逐字） | 舊位置 | 新位置 |
|---|---|---|---|
| DEC-081 Q2-1 | 今日結論句（`shared/market_conclusion.build_market_conclusion`；「；」並列、缺值明寫、⛔ 缺值當中性）⭐ 句子不改 | Hero 與 ⚡ 之間（DEC-105 1A） | **L1 第一屏**（作為頁級主要判讀句，B4）；Hero／⚡ 相對順序可維持，但必須進第一屏 |
| DEC-081 Q2-2 | ⭐「風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate」 | 建議總持股水位卡面 | 該卡的那 1 句，**逐字**（客戶自訂措辭，工程字樣例外） |
| DEC-092 Q2 | ⭐「均線為參考，不等於正式台股趨勢判斷。」；趨勢＝⬜ 尚未定義 | 圖 A 旁、展開區外 | Primary 主圖 header chip 或那 1 句（逐字）＋`⬜ 尚未定義` chip |
| DEC-092 Q5 | 「排序依據：法人資金動能，非產業趨勢。」 | 第一區 caption | 字樣逐字、寫一次；形式（說明句 vs header chip）＝Phase 5 線框待拍板 |
| DEC-101(3)／DEC-102 Q1～Q3 | 價格旁「資料時間＋來源」；⛔ 猜收盤；不只靠顏色；💼 沿用 **E17**（總市值下方「價格資料日」） | E17 小字 | **同位置（E17）metadata chip**。PR #970 線框 B.3 ② 把價格時間改放頁首 chip＝**錯誤、更正回 E17** |
| DEC-105 第 4 點 | 首屏「今日主要風險」與圖 D 必須指路到指標危險度，字面含「指標危險度」 | caption（`DANGER_POINTER`） | **維持指路句**（字面含「指標危險度」，指向「指標明細（16 項）」expander，冷／熱 session 皆有）；改為 chip 與否＝Phase 4 線框待拍板 |
| DEC-051（DR-2026-10-16-4） | Risk Cap 完整性（「未評估：…」）卡面直接揭露 | 卡面一列 | **緊鄰上限數字的 coverage chip**；⛔ 與數字拆開（移位時一起走） |
| DEC-101(1) | ⭐ `FX_PARTIAL_TEXT`「⬜ 部分外幣資產未納入，總市值／配置比例無法完整判定」＋未納入標的與原因 | 卡面 fact | **逐字 chip**＋`（N 檔）`＋前 5 代號；完整清單與原因在 L2 |
| DEC-102(4) | ⭐「停利未判：外幣」 | 列內文字 | 列內 chip |
| DEC-101(2) | missing ≠ HOLD；⭐「⬜ 資料不足／無法判定」 | 列狀態 | 列狀態 chip |
| DEC-054／055 | AI 生成、非投資建議揭露 | 卡面全文 | `🤖 AI 生成·非投資建議` chip＋正文旁全文照舊 |
| 股利卡 | 「稅前」但書 | 卡面句 | `稅前` chip＋摺疊全文 |
| DEC-107 第 1 點（UIT 線框「▾ 選股條件（預設展開）」） | 選股條件表單（因子、門檻）與 🎯 開始選股鍵 | 預設展開（`_target_blocks` `SCREEN_EXPANDER` `expanded=True`） | **維持預設展開**（客戶核准線框裁示；DEC-108 記「改此點須客戶明確回覆」）。在 Visual Budget 下是否改為預設收合＋一行條件摘要 chip＝**Phase 5 線框待客戶拍板點**（R3，總管 2026-10-29 改判；依草稿先行，本 phase 不另開 Gate、不改） |
| DEC-017 鐵律 4（2026-09-05） | 三要素「現況一句話／為什麼沒有／去哪補」**內容**必填 | 卡面常駐 | 內容契約不變（`Note` 三段非空）；位置改 L3 摺疊 |
| DEC-017 葉1 ②「兩套刻度…常駐揭露 · 非摺疊」 | 兩套刻度不得互比的警示 | 常駐雙表 | **維持常駐非摺疊**（DEC-109 原文未點名）；改為 L1 一顆 chip（例「健檢兩套刻度，不能互比」）＋完整雙表可展開與否＝Phase 6 線框待客戶拍板點 |
| 客戶 2026-09-24「三要素要在卡面上看得到」（程式碼註解 `page_today.py` 約 L2933） | — | 卡面三列 | **位置被 DEC-109 取代**；內容契約保留 |
| 客戶 2026-09-25「v2 卡面三列短句」（`page_find.py` 約 L769）＋K1 | K1：卡面那 1 句須為 Note 原文子字串、不新造 | 卡面三列 | 三列上卡面**被取代**；K1 **維持** |
| 客戶 2026-09-25「⛔ 不得只剩 hover」（`page_find.py` 約 L774／L2098／L2134） | 原文可取得 | — | **維持並延伸到手機**（必須可點開） |
| 客戶 2026-09-25「16 燈卡三列出處收進 ▸ 詳細」（`page_today.py` 約 L3014） | 純 CSS 摺疊機制與「▸ 詳細」字樣 | — | 機制與字樣維持；換字與否＝線框待拍板（R7） |
| DEC-091 §一／DEC-108 十項 | 三層資訊、L3 不得預設展開、第一列 3～4、圖表縮小、明細收合 | — | 同向；本契約為其具體化（DEC-108 ③「圖表縮小」讀為**主圖外露但縮小**，R2） |

- 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-117，Phase 4 步驟 0 裁示）**：上表 **DEC-081 Q2-1** 列「新位置」中的「Hero／⚡ 相對順序可維持」在 **📊 市場頁失效**——客戶 Q5=B 明確同意取代 DEC-105 1A 的舊相對順序，今日結論**提前到 3 個核心狀態 tile 之前**（順序見 §12.1 註）；「L1 第一屏、頁級主要判讀句、句子不改」照舊。DEC-081 Q2-2、DEC-092 Q2 兩列不變（逐字）。

## §17 能力守恆表（吸收自 PR #970 §D，依本契約更新；⛔ 能力消失、⛔ 語意改變）

> 原表出處：PR #970 commit `06a7a3e5` 的 `docs/vnext/NEWUI_D25_UI_CORRECTION_WIREFRAME_2026-10-29.md` §D（該檔已自本分支移除，見 supersede map §4）。單組讀碼所列，**非窮舉**；各施工 phase 須以機械 parity 測試逐項驗。

| 頁 | 既有能力 | 新去向（本契約） | 動作 |
|---|---|---|---|
| 📊 | 今日結論句（DEC-081 Q2-1） | L1 第一屏主要判讀句 | 改位置，句子不改 |
| 📊 | 市場位階卡（三段 Note） | 位階 tile（主值＋chip）＋L3 | 改形式 |
| 📊 | 建議總持股水位＋Q2-2 逐字句 | tile＋那 1 句逐字；`WATER_WHY` 進 L3 | 改形式（客戶措辭不動） |
| 📊 | 今日主要風險（≤3）＋指標危險度指路 | tile 內 chip；指路句維持（chip 化待 Phase 4 線框拍板） | 改形式（風險項）／維持（指路） |
| 📊 | 更新 form（模式 radio＋🚀 主鍵＋報告 caption＋「更新時間≠資料日」） | 主鍵留 L1；radio 與長 caption 進 L2；一句留 tile | 部分下沉（form／gate 語意不變） |
| 📊 | `status_line`、`AS_OF_NOT_PROVIDED` | metadata chip | 改形式 |
| 📊 | ⚡ 需要處理（含 `ALERTS_NO_SOURCE`） | 計數 chip＋L2 清單；「沒有來源不寫沒事」不變 | 改形式 |
| 📊 | 圖 A（未載入灰字、過期警告、MA 參考與免責、⬜ 尚未定義） | **Primary 市場環境主圖（compact，外露）**＋header chip | 縮小，資料與口徑不動 |
| 📊 | 圖 B（5 系列、窗口、資料日、⬜ 尚未定義） | Primary switcher 的分頁或 Secondary small multiples（每系列各一格，⛔ 疊軸／正規化） | 縮小／合併，口徑不動 |
| 📊 | 圖 C（研究框架，未啟用，零數值） | Secondary placeholder 或 L2 | 零數值不變 |
| 📊 | 圖 D 五桶＋N 項未評估 | Secondary compact view／chip 列＋完整表 L2 | 改形式 |
| 📊 | 既有 L3 expander（位階／危險度／風險上限／16 項／原始資料／來源完整度／問 AI） | 原樣，預設收合 | 保留 |
| 🎯 | 代碼搜尋 form＋進階選項（判型／期間／MA「僅顯示」） | 不變（DEC-107） | 保留 |
| 🎯 | 資料狀態、AI 佔位；不放 ⚡ | chip 列；AI 入口卡（R13） | 保留 |
| 🎯 | 第一區矩陣、🗺️ 載入板塊地圖 gate、熱力圖／泡泡圖（含持股 ⭐） | Primary compact 產業 view（Top 5）＋L2 完整矩陣與兩圖；gate 不變 | 改形式＋部分下沉 |
| 🎯 | 選股條件 form＋🎯 開始選股＋💾 CSV | **維持預設展開**；收合＋摘要 chip 與否待 Phase 5 線框拍板（R3）；按鈕與 CSV 原樣 | 維持（待拍板） |
| 🎯 | 候選表 6 欄＋估值口徑說明＋籌碼只取選取檔 | Top-N＋全表展開；說明 chip＋L3 | 改形式 |
| 🎯 | 選一檔＋🔍 查看此檔 | **不變** | 保留 |
| 🎯 | 第三區個股七區塊／ETF 三卡／判不出灰卡／價格時間 | 摘要卡 ≤4＋主圖＋展開完整分析；價格 chip 原位 | 改形式＋下沉 |
| 🎯 | 進階分析（多檔比較、仍未覆蓋） | 不變 | 保留 |
| 💼 | ① 三張結論卡 | 第一屏「該做什麼／需處理 N 檔」摘要（同一 `build_conclusion_cards`／`build_station_digest` 結果）；全文進 L3 | 改形式 |
| 💼 | ② 兩套刻度（常駐非摺疊） | **維持**；chip＋可展開與否待 Phase 6 線框拍板 | 維持（待拍板） |
| 💼 | ③ 燈牆＋VIX、④ 換股、⑤ 80/20＋衛星停利、⑥ 深度（VaR／壓測） | compact chart／card（Secondary ≤3）＋進階分析（⑤ 標題改「依種類近似，非投資目的」） | 改形式＋下沉 |
| 💼 | ⑦ AI 戰情總結（付費、點擊才生成、唯一推播出口） | AI 投資總結入口卡（R13）；付費 gate 不變；Phase 7 前不接新 Brain | 位置調整 |
| 💼 | 🚀 跑存股戰情室 form、組合設定葉、價格資料時間 E17、外幣排除、資料不足 ⬜ | 見 §16 | 保留（位置調整） |
| 👤 | Google 帳號、Sheet、組合、觀察清單、策略分類、資料健康入口 | 不變（R14） | 保留 |

**守恆聲明**：⛔ 新資料源、⛔ 新 schema、⛔ 改公式／門檻／TTL、⛔ 改 `PAGE_LABELS`／導覽殼／舊 UI、⛔ 新投資語意、⛔ 接新 AI、⛔ 寫 Sheet；只有位置、尺寸、卡片化、文字長度、預設展開／收合改變。

## §18 工程字樣清單（吸收自 PR #970 §A.5＋Inv-3 實測；L1／L2 一律 0）

- **一律下沉或改白話**：`線框`、`L0`～`L6`、`Lx`、`SSOT`、`digest`、`widget`、`expander`、`service`、`helper`、函式／常數名、`葉1`／`葉2`、`鐵律`、Gate 代號（客戶自訂措辭除外）、`unwired`、`取數接線揭露`、`judged_count`、`eps_high`、「生效分支 warroom」、「本次條件 eps_high」、「判型來源…（L2 判型」、「實作住在 L5…widget key」、「在你送出之前，本頁一次 L3 取數都不會發」。
- FACT（Inv-3 瀏覽器計數，💼 持股已載入可見文字）：線框 ×6、L3 ×8、L0 ×6、SSOT ×5、digest ×3、expander ×3、widget ×2、L5 ×2、judged_count ×1 等。
- **客戶自訂措辭例外**：DEC-081 Q2-2「風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate」逐字保留在 L1。
- 量測工具：`tools/visual_fidelity/count_eng_words.js`。

## §19 建議量化上限（DEC-110 內部；依 blueprint 量測 FACT；可調，調整須在 Gate 報告寫理由）

> PR #970 草稿 §A.5 的字數上限（區塊說明 ≤28 字、首屏每區 ≤60 字、卡標 ≤8 字等）**不吸收**，改用本表 Q6～Q9；#970 §A.5 只吸收工程字樣清單（§18）。

| # | 項目 | 上限 | 依據 |
|---|---|---|---|
| Q1 | KPI tile 高（desktop） | 96～160px，同列高差 ≤ 16px | mockup tile 內容約 120–160px；現況 213／277／504／641 不等高 |
| Q2 | KPI 首列（mobile 390） | 整塊 ≤ 340px（2×2 排法待 `CV1-DR-12`／W9 裁示，裁示前不判欄數） | mockup 2×2＝324px |
| Q3 | Primary 主圖本體高 | desktop ≤ 220px、mobile ≤ 140px | mockup svg 204／128 |
| Q4 | small multiple／mini 圖 | ≤ 96px／格；mobile 2 欄 | mockup mini 78–93px |
| Q5 | sparkline | ≤ 64px，無軸無圖例 | 既有 inline SVG gauge 先例（`app_render.py`） |
| Q6 | 主卡卡面可見字數 | ≤ 60 字（客戶原句另計、不截） | mockup tile 29–55 字 |
| Q7 | 主值字數 | ≤ 12 字（超過改 chip） | 既有 `page_hold.V2_FACE_TOKEN_MAX=12` |
| Q8 | 1 句字數 | ≤ 32 字（客戶原句豁免、不截不改） | `CHART_A_SAY` 31 字 |
| Q9 | chip 文字 | ≤ 12 字／顆（逐字客戶句豁免） | — |
| Q10 | 第一屏可見字數（主欄） | desktop ≤ 420、mobile ≤ 380 | mockup 約 400／370；現況市場 592 |
| Q11 | 頁級主要判讀句頂端 | 相對頁面 H2：desktop ≤ +200px、mobile ≤ +260px，且在第一屏內 | 現況市場 +998 |
| Q12 | 全頁高（已載入） | ≤ 1.3× blueprint＝✅、≤ 2×＝🟡、> 2×＝❌ | mockup contentH 市場 1517／2480、標的 2193／3185、持股 1643／2501 |

- 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-115，Phase 3 步驟 0 裁示）**：**D5=A**——sparkline（Q5）與 small multiples／mini 圖（Q4）**不額外顯示最新／最高／最低數字**；重要數字由 KPI 主值或 status chip 承擔，避免圖表再次數字化（單色中性線、窗口以可見 chip 標明，不變）。**站殼間距**：客戶同意 AI 總管原方案——**先內部實測**取得實際像素差與最小改動方案，**若屬整體 layout 變更再送客戶裁示**；實測前不改 `app.py`（Migration Plan §16 步驟 3 僅量測）。
- 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-117，Phase 4 步驟 0 裁示）**：**Q2**「2×2 排法待 `CV1-DR-12`／W9 裁示，裁示前不判欄數」→ 📊 市場頁已裁示：手機 **2＋1**（位階｜水位並排、風險整列），KPI 區塊仍以 ≤340px 判；桌機 3 tile 以 **Q1** 判。**Q11** 不變（Q5=B 同向；真值待 Gate 實量）。手機 Primary 依 Q7 mobile exception（§3 註），**Q3** 尺寸上限照舊。
- ⚠️ 站殼限制（FACT，Inv-3）：`app.py` 站標＋Streamlit 頂欄使頁面 H2 起於 y≈223（約占第一屏 25%），Q10～Q11 在不壓縮站殼時可能達不到 → 站殼間距屬 Phase 3 子項（Migration Plan），⛔ 因此改 `PAGE_LABELS`／導覽殼語意／legacy 入口（DEC-097）。

## §20 Phase 3 共用元件（客戶 DEC-109 三十一 Phase 3 清單）

metadata chips、status chips、chart header、evidence expander（`▸ 為什麼／來源／限制／去哪補`）、Missing placeholder、compact KPI card（＋sparkline、small multiples 排列、Top-N 切片、segmented／switcher）。規格見本檔 §4、§6、§8、§10、§11；施工步驟與守衛見 Migration Plan Phase 3。

## §21 未驗與限制

- 已載入狀態量測依賴夾具（產業數、持股檔數、文字長度）；真資料下候選表預設 50 列**未渲染**；手機實機、Streamlit Cloud、`requirements.txt` floor 1.56 未驗。
- 「主圖」選擇（§12）是撰寫組依客戶方向指定；Phase 4～6 依 Gate 與真資料再定，屬內部拍板；**寫 UI code 前一律先出文字線框**（Migration Plan §1；`CLAUDE.md` §-1.5.D v3 §03-2 ①）。
- 本檔所有判定單組產出，**未經第二組驗證**。

## §22 各頁 phase 線框待客戶拍板點（2026-10-29 總管改判：AI 總管讀法不得推翻客戶核准過的呈現；Phase 3～7 每個 UI phase 寫 UI code 前都須先出文字線框）

> 原則：凡「改變客戶核准過的呈現」、且 DEC-109 客戶原文**沒有明確點名**者，一律**維持現行**，並列入該頁 phase 的線框草稿，由客戶拍板（`CLAUDE.md` §-1.5.D v3 §03-2 ① 草稿先行；**本 phase 不另開 Gate、不改**）。每點須附總管推薦方案與理由。

| # | Phase | 維持中的客戶核准呈現 | 待拍板的替代方案（總管提案方向） | BACKLOG |
|---|---|---|---|---|
| W1 | 3 | tokens 客戶裁示色值（CTA 主色 `#1f6feb`／light `#044cb6`；`--sig-neutral`／`-bg`） | 改為 blueprint 色值或保留 | `P1R-P3-WF-CUSTOMER-COLORS`（📌 2026-10-30 已解決：客戶裁示 D1a=A **維持**，DEC-115） |
| W2 | 4 | DEC-105 第 4 點「指標危險度」指路**說明句** | 改為指路 chip（字面不變） | `P1R-P4-WF-POINTS` |
| W3 | 4～6 | 卡片摺疊標籤「▸ 詳細」（客戶 2026-09-25 核可線框逐字）、「🔍 查看依據」 | 統一為「▸ 為什麼／來源／限制／去哪補」 | `P1R-WF-FOLD-LABEL` |
| W4 | 5 | **DEC-107「選股條件預設展開」** | 預設收合＋一行條件摘要 chip | `P1R-P5-WF-SCREEN-COND` |
| W5 | 5 | DEC-107 1A 頁面順序 | 在原順序內讓候選更早出現（例 第二區 header 進 desktop 第一屏、第一區 Top 5 壓高度） | `P1R-P5-WF-POINTS` |
| W6 | 5 | DEC-092 Q5 排序依據**說明句**（`ZONE1_SORT_NOTE`） | 改為區塊 header chip（字樣不變） | `P1R-P5-WF-POINTS` |
| W7 | 6 | DEC-017 葉1 ②「兩套刻度…常駐揭露 · 非摺疊」 | L1 一顆 chip＋完整雙表可展開 | `P1R-P6-WF-TWO-SCALES` |
| W8 | 7 | （無既有正式規則）AI 投資總結「最大的 1～3 個變化」的選取規則 | 候選：DEC-092 Q3 五桶規則＋既有方向值；沒有則 MISSING；或依變化幅度排序（需客戶定義）——**不作內部預設** | `P1R-P7-WF-CHANGE-RANK` |
| W9 | 4 | 現行 Hero 4 欄（DEC-105 第 5 點 P2 偏離）＋卡片網格 3 欄；`CLAUDE.md` v3 §00「固定 3 欄自適應網格」 | KPI 首列 4 格、手機 2×2，或 3＋1 排（須客戶裁示 `CV1-DR-12`） | `CV1-DR-12` |

- 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-115，Phase 3 步驟 0 裁示）**：**W1 已裁示（維持，D1a=A）**；客戶明示 **W2～W9 維持原 Gate、不提前處理**。Phase 3 另有 D1b／D3／D5／D6／D8／D10 六題已裁示（非 W 系列，見 DEC-115），不增加新 W。
- 📌 **2026-10-30 有意識的更新，不是漏刪；決策者 客戶（DEC-117，Phase 4 步驟 0 裁示）**：**W2 已裁示**（Q2=A′：維持說明句、縮短、保留「指標危險度」「指標明細（16 項）」與指向最上方的關係，不新增 chip；`P1R-P4-WF-POINTS`）；**W3 在 📊 市場頁已裁示**（Q3=A：圖用四段字樣、tile／⚡ 維持「🔍 查看依據」；Phase 5～6 仍待；`P1R-WF-FOLD-LABEL`）；**W9 已裁示**（Q1=B：桌機 3 tile＋頁首主 CTA、手機 2＋1；`CV1-DR-12` 結案）。W4～W8 不變。
- 本表為撰寫組依總管改判原則逐條複查的結果（單組，未經第二組驗證）；維持原判、因客戶原文明確點名者見 `docs/DECISIONS.md` DEC-110「同原則複查」。
