# 📊 市場｜台股歷史主圖（TWII）接線＋視覺 施工前 SPEC（2026-11-09）

> **研究候選，非授權、非投資判斷。** 基準 main `ca5fdc9`（唯讀 `git show origin/main:…`）。僅讀程式碼／文件；**未連網、未跑 Streamlit／pytest、未驗部署端資料**；未驗證處標 **NOT VERIFIED**。
> **客戶核准「視覺契約」與「接線契約」之前不得施工**（含不得動 `src/ui2/**`、`src/services/**`、`tests/**`）。以下全部為研究候選。

## 0. 先講結論
1. 資料面可走 **A（重用 `get_twii_trend_view(n)`）**，G2F 白名單**不必改**；但 `TwiiFact` 現只帶 `close`、**沒有 `xs`**，要畫圖必須加欄（加性改動，見 §3）。
2. 舊主圖的 **MA5/60/120/200 是 session「市場評估」的最新純量畫成水平線**，UI2 不能讀 session → **MA 線無法照搬**；自算歷史 MA＝新公式/趨勢定義，須另立 Gate。這是與 DEC-119 保留清單的**實質差異**，必問客戶（Q2）。
3. 建議：視覺選 P1（僅收盤折線）＋誠實狀態列；接線選 A；MA／量／區間切換一律不做。

## 1. Old UI First 五步驟狀態（Gate §1）
| 步 | 狀態 | 證據／缺口 |
|---|---|---|
| 1 目標與已核准規格 | 本檔補；使用者任務＝「看加權指數近一年走勢與資料日」。已核准：五頁、Dark-only、Mobile-first、頂部兩列導覽、首屏 ≥160px、📊 Primary 誠實空槽（DEC-133，依內容高度）、手機 Primary≈220px 例外（DEC-119，**舊 Legacy 市場頁**，是否沿用於 UI2＝NOT VERIFIED，列 Q3） | 台股主圖**尚無**核准 UI2 Wireframe；`NEWUI2_MARKET_TARGET_OLD_FIRST_DATA_CONTRACT_AUDIT_2026-11-09.md` §A2 明寫「設計決定尚待、不能以研究文取代 User Visual Gate」 |
| 2 舊 UI／資料層盤點 | **已完成（本檔 §1.1＋既有三份 audit）**；caller→L3→L1 已讀；實測成功＝NOT VERIFIED | 見下 |
| 3 保留/改善/捨棄＋≥3 方案 | 本檔 §1.2、§4 | — |
| 4 設計最適合 UI2 | 本檔 §5（候選，待客戶） | — |
| 5 授權施工→非作者 QA→CI→合併 | **未啟動**，等 §7 客戶裁示 | — |

### 1.1 舊畫面實際畫了什麼（`src/ui/views/_market_blocks.py`）
- 窗口：`TWII_CHART_TRADING_DAYS = TRADING_DAYS_PER_YEAR`（252 個**交易日列**）；呼叫 `twii_svc.get_twii_trend_view(252)`。
- `twii_chart_frame`：收盤欄「加權指數收盤」＋ 4 條 **MA 水平參考線**（MA5/60/120/200，值＝`mkt_info` 最新純量；非歷史 MA 曲線，見 `CHART_A_MA_NOTE`）；缺值 MA 不補（`ma_reference_values` 非有限／≤0 → 列入缺）。
- `twii_chart_spec`：Vega-Lite（`st.vega_lite_chart`）；有 y 軸刻度、x 時間軸、圖例置底 3 欄、tooltip 帶完整系列名；⛔ 正規化／sparkline／mini；色：主線 `#2563eb`、MA 四色（偏 Light 主題配色，Dark 對比＝NOT VERIFIED）。
- **無成交量**（grep 0 命中）；量欄歷史上連續為 0 且稀疏（既有 audit a2），故不畫是對的。

### 1.2 舊功能 → UI2 目標 → 保留／改善／捨棄
| 舊功能 | UI2 目標 | 判斷與理由 |
|---|---|---|
| 252 日收盤折線＋y 軸＋時間軸 | 同 | **保留**（核心任務） |
| 資料日／stale／上游狀態（`basis_chart_a`） | 圖下狀態列（沿用 `spec_line_text` 家族） | **改善**：三態文案已有 `upstream_state_text` |
| MA 水平參考線×4＋5 項圖例 | — | **捨棄（待客戶確認）**：來源為 session，UI2 G9/G2F 禁；補歷史 MA 曲線＝新計算（Q2） |
| 讀不到同高空槽（D6=B） | 空槽依內容高度（DEC-133 G-1=A） | **改善**：沿用 UI2 已核准 |
| 量能 | 不畫 | **捨棄**（量欄不可信） |

### 1.3 UI2 現況（main `ca5fdc9`）
- `src/ui2/views/market.py` → `primary_slot_html(twii_card)`：標題「🇹🇼 台股趨勢」＋Capability chip「⬜ 尚未提供」＋「此項目尚未開放」＋ SPEC 行（`SPEC｜最新收盤參考｜來源｜資料日｜缺值不補`）；明文 ⛔ svg/polyline/canvas/img/MA。
- `real_feed._read_twii`：`TWII_CARD_DAYS = 1`，只取 1 日；`TwiiFact` 欄位＝ok/close/as_of/is_stale/stale_reason/age_days/has_upstream_error/error_type/failed/source/upstream_state，**無 xs、無 n_available**。
- FAKE／scenarios 的台股數值為示意，不得當歷史序列來源（`FAKE` 標示 NOT VERIFIED 逐檔細節）。
- 約束 DEC：DEC-117 Q4（台股＝Primary Visual）、DEC-119（手機約 220px、5 項圖例、不得 sparkline/mini/正規化/改趨勢定義；**Legacy 頁**）、DEC-125（兩條產品主軸、中性命名）、DEC-128（Human UI 不放完整 L2/L3 evidence）、DEC-133（空槽誠實＋SPEC「最新收盤參考」）、DEC-146（頂部導覽、首屏≥160px）。

## 2. 資料契約核實
- `get_twii_trend_view(n_trading_days:int)->TwiiTrendView`；`n<1` 拋 `ValueError`。欄位：`ok, xs(tuple[str]), close(tuple[float]), n_available, as_of, is_stale(bool|None), stale_reason, age_days(int|None), upstream_error, upstream_state, error, failed, source`（皆已核對原始碼）。**無 fetched_at、無 volume。**
- L1 `load_twii_close`：`dropna`（NaN 已清並 log）、`sort_index`升序；**未去重、未檢 inf、未檢未來日期**（NOT VERIFIED 其他守衛，僅讀該函式）。
- `get_twii_trend_view` 已在 `G2F_IMPORT_ALLOWLIST`（`src.services.market_twii_view_service: {get_twii_trend_view}`）；**傳 n>1 不需改守衛**（名稱不變，改的是呼叫引數）。⚠️ **已有測試鎖 `TWII_CARD_DAYS` 值**（讀 `tests/test_ui2_real_feed.py` on origin/main）：`test_twii_reads_exactly_one_trading_day` 斷言 `calls["twii_args"] == RF.TWII_CARD_DAYS == 1`；另約 L118 以 `TWS.get_twii_trend_view(1)` 作為「同一 canonical service 的直接結果」相對斷言基準。方案 A 若改讀 N 日，這些斷言須刻意改寫（見 §6）。其餘測試是否也鎖定＝NOT VERIFIED 全量。
- **不能做的**：不得改白名單；feed 禁 pandas/datetime → 排序／日期檢核需放 `real_canonical` 純函式（只准 `math` 等；是否允許 `datetime` 於 canonical＝NOT VERIFIED，須看 G2 規則）。
- PIT：TWII 日收盤收盤後才完整（TWSE ~13:30 收盤、CLAUDE §2.3 標「17:00 後可信」）；快取由 `update_macro_history.yml` cron `0 9 * * *` UTC（＝TW 17:00）更新並 commit；Yahoo 盤中棒是否可能入檔＝NOT VERIFIED。**觀測日（as_of＝最後一筆交易日）≠ 抓取時間**；本 L3 不提供 fetched_at，故畫面只能寫「資料日」，**不得**以 cron 時刻或今天日期冒充。

## 3. 圖表資料狀態矩陣（每格＝畫面必須顯示什麼）
| 狀態 | 判定 | 圖 | 文字（人話，不放例外型別名／路徑） | 色調／軸 |
|---|---|---|---|---|
| OK | ok∧is_stale=False∧upstream_state="" | 折線 | 資料日 {as_of}｜來源｜缺值不補 | 中性 |
| Stale | is_stale=True | 照畫（資料真實但舊） | 「資料日 {as_of}，已 {age_days} 天未更新」＋`stale_reason` | Warning＋⚠（顏色非唯一載體） |
| 新鮮度未判定 | is_stale=None | 照畫 | 「新鮮度未判定」（⛔ 當新鮮） | Warning，Judgement 軸 |
| 上游三態 | upstream_state∈NO_NEW_DATA/FETCH_FAILED/UNDETERMINED | 照畫既有序列 | 沿用 `upstream_state_text` 三句；⛔ 把「無新資料」稱「失敗」 | 與 stale 正交，分列 |
| 讀不到 | ok=False∧failed=False | **不畫**，空槽 | 「讀不到加權指數歷史」類固定句；⛔ 紅 | 灰（Data：missing） |
| 系統出錯 | failed=True | 不畫 | 固定句，⛔ 型別名 | 紅（Data：unavailable） |
| 部分窗口 | 實際點數 < 目標 N（n_available<N） | 畫現有 | 「僅 {k} 個交易日（目標 {N}）」；⛔ 補齊／拉伸 | Neutral 註記 |
| 單點 | 點數=1 | **不畫線**（單點非走勢） | 顯示該點數值＋資料日＋「歷史不足」 | Neutral |
| 0 點 | 點數=0 且 ok | 視為契約違反→Unavailable | fail loud | 紅 |
| 序列含 NaN／inf | 不應出現（L1 已 dropna） | 出現＝契約違反：**整圖不畫** | 固定句；⛔ 靜默丟點後照畫 | 紅 |
| 未來日期 | any xs > 今日(TW)（VM 層無法讀時鐘：G2 禁 now／today，故「未來日期」偵測需由殼注入參考日期；注入方式與可行性＝**NOT VERIFIED**） | 不畫或截斷並標註（候選：不畫） | 「資料日異常」 | 紅 |
| 非升序／重複日 | 契約違反 | 不畫 | 固定句 | 紅 |
| len(xs)≠len(close) | 契約違反 | 不畫 | 固定句 | 紅 |
| 代理／示意 | FAKE 或 Preview 資料 | 照既有橫幅 | 沿用 FAKE／Real Preview 標示；⛔ proxy≠real | 沿用 |
- 通則：缺≠0；不填補、不內插、不 ffill；x 軸為交易日列（假日留白不補點）；y 軸**不從 0 起**但須顯示刻度（避免誤導需標軸範圍＝候選，Q 項）；單位「點」。

## 4. 接線方案比較
| 方案 | 做法 | 風險 | 速度 | Token | 備註 |
|---|---|---|---|---|---|
| **A（推薦）** | `real_feed` 改以 `TWII_CHART_DAYS` 呼叫 `get_twii_trend_view`；`TwiiFact` 末尾加 `xs: tuple[str,...]=()`、`n_available:int=0`（預設值＝既有 positional 建構與測試不破）；`real_canonical` 新增 chart spec 純函式＋`validate_twii_chart`（長度、升序、唯一、有限、非未來） | 低；G2F 白名單不變；影響 `TwiiFact` 建構點與 VM contract | 最快 | 最省 | 卡片仍取尾端 1；一次讀 N、尾端取最新 |
| B | `src/services/ui2/` 新薄 adapter 回 chart VM | 中；新增 I/O 入口須納 G2F 白名單（本檔**不提議改白名單**，若走 B 須客戶另核）；多一層與 `real_feed` 重複讀取 | 中 | 中 | 僅在要畫量／OHLC 時才有理由 |
| C | 維持空槽，延後 | 零新風險 | 立即 | 零 | 使用者仍看不到走勢；空槽文案永久「尚未開放」 |
- 若 `real_feed` 一次讀 N 日而卡片只用最後 1 筆，需確保卡片與圖的 `as_of`／最新收盤**同一次呼叫、逐字一致**（防兩處各讀）。

## 5. 呈現方案（Dark-only、Mobile-first、無量）
共通：沿用空槽的標題「🇹🇼 台股趨勢」、狀態列＝`spec_line_text` 家族；色用既有 chip 色（Positive `#3fb950`／Warning `#d29922`／Danger `#ff7b72`／底 `#0e1117`、虛線框 rgba(128,128,128,.55)）。**src/ui2 沒有圖表色 token**（僅 `--ui2-nav-*`）；折線主色 token 需新增＝設計決定（Q4），舊 `#2563eb` 在深底對比 NOT VERIFIED。
| 方案 | 內容 | 390×844（手機） | 1440×900（桌機） | 風險 |
|---|---|---|---|---|
| **P1（推薦）收盤折線＋狀態列** | 單線、y 刻度、x 月份刻度、末點標示值＋資料日；無 MA／無量；最後一點圓點 | 寬＝內容區（無水平捲動）；高約 220px（若沿用 DEC-119 例外，Q3；否則 ≤140 契約）；x 刻度 ≤4 個；狀態列兩行內；首屏不擠掉 ≥160px 優先內容 | 同欄寬；高 ≤220px（Q3 契約）；y 刻度 5 格 | 單線不足以回應「MA 參考」期待（Q2） |
| P2 折線＋stale 橫幅＋停用區間切換 | 同 P1＋頂部 stale 橫幅＋disabled 1M/3M/1Y 鈕 | 多一列，吃首屏高度；disabled 控制項易被誤讀成可用 | 同 | 觸發 Layout＋互動新增；DEC-146 Capability 軸「⬜尚未提供」可表達，但屬新 UI 元件 |
| P3 sparkline 卡 | 縮成卡內迷你線 | 省高度 | 省 | **違反 DEC-119「⛔ sparkline／mini」（Legacy 市場頁）**；不推薦 |
- 空/錯態沿用現空槽版型（依內容高度，G-1=A），不預留 220px 灰框。
- 驗收量測沿用 `tests/ui2_viewport/measure_viewport.py`（VIEWPORTS：390×844、1440×900；手機可用高 844−53=791）與 `tests/ui2_browser.py`（`UI2_BROWSER_LANE=required` 時缺瀏覽器＝fail，CI `ui2-browser` job；Streamlit matrix）。PR 須附 desktop 1440×900＋mobile 390×844 截圖（PR template）。

## 6. 施工後驗收清單（候選；未授權）
- [ ] 有 xs；`len(xs)==len(close)`、升序、唯一、全部有限、末點＝TWII 卡值＝`as_of` 同值（同次呼叫）。
- [ ] §3 每一列各有一個單元測試＋一個 browser 狀態截圖（390／1440）。
- [ ] 390：無水平捲動；x 刻度不重疊；狀態列文字不被截斷；首屏既有項目底緣仍 ≤791；1440：不退化。
- [ ] 畫面不含：例外型別名、路徑、token、「0」補值、MA 線、量能、sparkline、假走勢。
- [ ] G2F／G2／G4／G9 守衛全綠；白名單未動（diff 可證）。
- [ ] 若採方案 A（讀 N 日）：`tests/test_ui2_real_feed.py` 的 `test_twii_reads_exactly_one_trading_day`（`== RF.TWII_CARD_DAYS == 1`）與約 L118 對 `get_twii_trend_view(1)` 的比較，必須**刻意改寫**並在 PR 說明，不得放任其失敗當作意外。
- [ ] 文案不含投資建議語氣；SPEC 保留「缺值不補」「最新收盤參考」改為「歷史收盤」之文案變更需客戶核（Q5）。
- [ ] **突變／負向測試建議**：(1) 拔掉升序檢查→亂序序列必須轉紅；(2) 把 NaN 改成 0 填補→必須紅；(3) 拔 stale 標示→stale 夾具必須紅；(4) 把 `failed` 畫成灰→必須紅；(5) 將 `TWII_CHART_DAYS` 改回 1→圖必須回空槽且測試紅；(6) 夾具含未來日→必須不畫；(7) FAKE 資料不得出現在 Real 路徑。
- [ ] 非作者 QA、最新 head 原生 CI 綠；CI 綠≠真實資料／部署驗收（部署 cron／Cloud 資料＝NOT VERIFIED，須據實寫限制）。

## 7. 需客戶核准的問題（建議答案皆為 AI 候選）
| # | 問題 | 選項 | 優點 | 缺點 | 風險 | AI 建議 |
|---|---|---|---|---|---|---|
| Q1 | 圖的內容 | P1 收盤線 / P2 +stale 橫幅+disabled 切換 / P3 sparkline | P1 最小；P2 預告功能；P3 省空間 | P1 無參考線；P2 假控制項；P3 違 DEC-119 | P2 新增互動元件 | **P1** |
| Q2 | MA 參考線 | 不畫 / 自算歷史 MA 曲線 / 另開接線讀「市場評估」最新值 | 不畫＝零新計算 | 與 Legacy 差異 | 自算＝新公式、改趨勢定義（High Gate）；讀 session＝違 G9 | **不畫**，列「尚未提供」，另案研究 |
| Q3 | 高度契約 | 手機約 220px 例外沿用 / 回 ≤140 / 內容高度 | 220 可讀；140 省首屏 | 220 擠首屏 | 首屏 ≥160px、P2 邊界 | **手機≈200~220、桌機 ≤220，先出線框送審**（DEC-119 是否適用 UI2＝NOT VERIFIED） |
| Q4 | 窗口與色 | 252 交易日（同舊）/ 120 / 60；折線色新 token | 252 與舊一致 | 手機點密 | 新增色 token＝視覺核准 | **252**；折線色另送色票 |
| Q5 | 空槽→圖的文案 | 保留「最新收盤參考」SPEC 並增「歷史收盤」/ 改寫 | 保真 | 文案同步 DEC-133 鎖定字樣 | DEC-133 文案由 sha256 守衛釘住（`tests/test_ui2_active_contract_docs.py`；其中 `test_customer_fences_are_pinned_by_sha256` 釘的是客戶原文 fence 整段 sha256，是否涵蓋 DEC-133 逐字文案＝NOT VERIFIED）＝改字需客戶 | 先**不改既有字樣**，新增圖下一行 |
| Q6 | 接線 | A / B / C | 見 §4 | — | — | **A** |
| Q7 | 資料不足/單點/stale 呈現 | 如 §3 / 更簡 | 誠實 | 狀態多 | 文案量 | 如 §3 |
> **再次聲明：客戶核准視覺契約與接線契約前，不施工；本檔所有內容均為研究候選。**
> NOT VERIFIED 彙整：部署端 cron／資料、Yahoo 盤中棒、Dark 對比、DEC-119 對 UI2 的適用性、G2 對 `datetime` 的限制、全量測試對 `TWII_CARD_DAYS` 的鎖定、FAKE/scenarios 逐檔細節、任何 runtime 行為。
