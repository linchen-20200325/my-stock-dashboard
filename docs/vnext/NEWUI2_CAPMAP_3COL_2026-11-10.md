# NUI2-CAPMAP-3COL：Old UI → Legacy New UI → New UI2 三欄能力對照表（2026-11-10）

> **研究／證據紀錄，非施工授權、非新決策、非投資判斷。** 授權：Issue #1121（docs-only）。本檔只新增這一個檔案，未改任何程式、測試、資料、workflow，未連網，未執行 app 或測試。
> - **基準 SHA**：`origin/main` `f4d86b4f9b45832cb784895342cecd5f9305c48b`（短碼 `f4d86b4f`；撰寫時 working tree 即此 SHA）。cron 會推進 main，接手前請重新 `git fetch` 核對。
> - **量測日**：2026-11-10。
> - **作者揭露（`CLAUDE.md` §-2 規則 6）**：單組產出（文件撰寫＋證據查核 agent），**未經第二組獨立複驗**。下列全稱式陳述（「UI2 無此功能」「0 命中」）都附 grep 範圍，且只能當待驗事項，不得當作後續動作的前提。

## 0. 與既有文件的上下位關係

| 文件 | 性質 | 與本檔的關係 |
|---|---|---|
| `docs/vnext/FINAL_UI_CAPABILITY_MAP_2026-11-02.md`（T01~T29 等 85 列，M／T／H／E 編號） | **歷史**，部分已標 SUPERSEDED（DEC-128） | **上位索引、不修改**。本檔是 **2026-11-10 現行補充**：沿用其能力編號當索引（括號內 M／T／H／E），但「新 UI 現況」改為三欄，並以 2026-11-10 讀碼重新判定。兩者衝突時，以本檔「UI2 現況」欄（讀碼較新）為準；FINAL 的 critical 定義與落點決策仍由原檔承載 |
| `NEWUI2_REUSE_MATRIX_2026-11-02.md` | 分類（KEEP／WRAP／PORT…），2026-11-02 | 本檔不重新分類；只引用其「Legacy 內含 Gemini 直呼不得搬」等結論 |
| `NEWUI2_OLD_UI_FIRST_FIVE_PAGE_GAP_AUDIT_2026-11-09.md`、`NEWUI2_MARKET_TARGET_OLD_FIRST_DATA_CONTRACT_AUDIT_2026-11-09.md` | 2026-11-09 候選初審 | 本檔把它們的「候選處置」逐項轉成可核對的列；其「不得把歷史 ✅／❌ 當 UI2 現況」的提醒在此落實 |
| `ISSUE1110_DATA_AVAILABILITY_MATRIX_2026-11-10.md`（基準 `db04dac`） | Secrets／資料可用性證據 | 「真資料」欄與資料日引用其結論（標明「引自矩陣，未重驗」）；其 §5 資安發現已過期（見 §2） |

### 0.1 FINAL 能力表中，對 2026-11-10 已過期或需改讀之處（原檔不改）

| FINAL 項 | FINAL 原述（2026-11-02） | 2026-11-10 讀碼事實 | 證據 | F/I |
|---|---|---|---|---|
| **T11** 雙模式切換 | ❌ 無雙模式，單頁直排 | **UI2 已有**市場精選／即時查一檔雙模式；**Legacy 仍是單頁**（`page_target.py::render_page_target`） | `src/ui2/views/target.py::render`；`tests/test_ui2_batch3.py` | F |
| **M19** 一鍵更新、**E01／E02／E03** 登入／Sheet／選定 | ✅ 已承接 | 僅 **Legacy** 為真；UI2 的更新 CTA 為 disabled，我的頁為 FAKE 示意（Real 軸 `account=None`、cards 皆 `_not_provided`） | `src/services/ui2/real_canonical.py::_market`、`::_me` | F |
| **M09／T13** 大盤趨勢圖／K 線 | 新 UI（Legacy）只有收盤線＋MA 參考線；K 線為灰色占位 | **UI2 已有 TWII 日 K 主圖**（最近 20 根，無 MA／成交量）；個股 K 線仍無 | `real_canonical.py::kbar_chart_spec`；`src/ui2/components/html.py::kbar_chart_html` | F |
| **H04** 持股逐檔表 | ❌ 無逐檔表（只有燈牆） | Legacy 現有葉 2 **唯讀持股預覽卡**；UI2 有表格骨架（欄名＋原因，無資料） | `page_hold.py::build_holdings_preview_card`；`html.py::hold_table_html` | F |
| **M08** 核心指標卡 | L1 無指標卡 | UI2 有 6 張卡位（`twii／vix／us10y／spread／dxy／pmi`），**僅 `twii` 為真資料**，其餘 `not_provided` | `src/services/ui2/market_vm.py::MARKET_CARD_IDS`；`real_canonical.py::_market` | F |
| FINAL §5「路由現況」 | 描述 Legacy 四頁 | UI2 為**五頁**（加 🗂 資料；DEC-146）、入口 `app_ui2.py`，與 `app.py` 分離，`app.py` 不引用 | `shared/ui2_contract/pages.py::PAGE_IDS`；`app_ui2.py` | F |
| ISSUE1110 矩陣 §5「診斷頁顯示 Secret 前後 4 碼」 | 未修，待客戶授權 | **已修**：#1113（D6）移除；`api_diagnostic.py` 已無 `_mask`；`app.py` 側欄改只顯示布林 | `git log` 見 `da675689`；`tests/test_d6_diagnostic_no_secret_display.py` | F（grep `_mask` 命中 0） |

## 1. 方法、標示規則與欄位定義

- **方法（FACT 來源）**：讀碼為主——`app.py`（路由與 `?legacy=1`）、`src/ui/tabs/**`（Old）、`src/ui/views/page_*.py`／`_*_blocks.py`（Legacy New UI）、`app_ui2.py`、`src/ui2/**`、`src/services/ui2/**`、`shared/ui2_contract/**`（UI2）；文件為輔（見 §0）。每個 `path::symbol` 都以腳本核對**檔案存在且該符號字串出現在檔內**（子字串比對，不代表呼叫鏈已驗）。**未跑 runtime、未連網、未執行測試。**
- **FACT**：直接讀到的程式碼／檔案內容／grep 結果。**INFERENCE**：由事實推得，或引自他檔未重驗。**NOT VERIFIED**：沙箱無法驗（Streamlit Cloud 線上、外部 API、真瀏覽器）。查不到一律寫 NOT VERIFIED／UNAVAILABLE，**不補 0、不寫中性值**。表末欄「F/I｜備註」逐列標示。
- **三欄定義**
  - **Old UI**：`app.py` 在 `?legacy=1` 才走的舊 7 頁籤（🌍 市場環境／🔬 選股／🏦 ETF／🔧 工具箱／💼 我的持股戰情室／📁 組合管理／🧬 AI 問答）＋側欄；程式在 `src/ui/tabs/**`、`src/ui/etf/**`、`src/ui/pages/**`、`src/ui/render/**` 與 `app.py` 內嵌區塊。
  - **Legacy New UI**：`app.py` **預設**四頁主導覽（📊 市場／🎯 標的／💼 持股／👤 我的），程式在 `src/ui/views/page_*.py`、`_market_blocks.py`、`_target_blocks.py`。
  - **New UI2**：`app_ui2.py` 入口、五頁頂部兩列導覽（📊→🎯→💼→👤→🗂）；`src/ui2`（只吃 ViewModel）、`src/services/ui2`（VM builder、FAKE scenario、Real feed）、`shared/ui2_contract`（契約）。**預設資料源為 FAKE 示意**；Real-data Preview 只在 `?ui2_dev=1` 開發面切換。
- **UI2 目前事實（FACT，讀 `real_feed.py`／`real_canonical.py`）**：Real 軸只接 **三個事實**——TWII 卡片（`get_twii_trend_view(1)`）、TWII 日 K（同函式再讀一次、`with_ohlc=True`、20 根）、市場位階（`get_macro_regime(strict=True, require_valid_risk_cap=True)`）；其餘欄位皆 `_not_provided`（含 VIX／US10Y／利差／DXY／PMI、OneBrain、標的候選與查一檔結果、持股、帳戶、🗂 資料頁）。Risk Cap 恆為「無法判定」。UI2 不使用任何 Secret（引自 ISSUE1110 矩陣 §2；本檔對 `src/ui2`、`src/services/ui2`、`shared/ui2_contract`、`app_ui2.py` grep `st.secrets|os.environ|getenv` 0 命中，單組）。
- **欄位**
  - **功能存在**：UI2 是否有該能力的**可用實作**。`是`＝有；`部分`＝只有占位／骨架／disabled 示意；`否`＝完全沒有（含只在 VM 保留但 Human UI 不渲染的 evidence 區塊）。
  - **真資料**：UI2 該列是否讀真實資料。`是`／`否`；`N-A`＝該列不是資料（導覽、文案、守衛）或 UI2 無此功能。
  - **互動**：`是`＝可操作；`disabled`＝可見但明示不可按；`否`＝不可操作或不存在。
  - **缺值處理**：`誠實`＝缺值以「⬜ 尚未提供」等明示字樣＋原因顯示，不補 0／中性；`未驗證`＝有實作但無法由讀碼確認；`N-A`＝UI2 無此功能故無缺值處理（此時使用者畫面上**看不到缺口**，見備註）。
  - **測試證據**：與「UI2 現況」欄對應的測試路徑；UI2 無此功能者寫 `NONE（UI2）`，並可附「舊側參考」測試（**只證明該測試檔引用相關符號，未逐一檢視斷言，INFERENCE**）。測試是否通過未執行，NOT VERIFIED。
  - **缺口等級（本檔暫定，非客戶核准，客戶可推翻）**：
    - **critical**：FINAL 已標 critical 且 UI2 仍無真承接，或為「整頁真資料唯一前置」（本檔另新增 HD-03，標明於備註）。
    - **major**：Old 或 Legacy 有可用的真資料實作，UI2 沒有或只有占位，且不屬 critical。
    - **minor**：便利／輔助／已有替代、或舊側自己也只有占位／無實作（新能力、定義未訂）、或 UI2 已部分承接。
    - **none**：UI2 已承接並有測試，或屬 Research／刻意不做、非能力遺失（備註說明）。
- ⚠️ **誠實限制**：「UI2 有占位且標示尚未提供」的列，**功能存在＝部分、缺口仍計為 major／critical**——有誠實空槽只代表不誤導，不代表能力已承接。

## 2. 三欄對照表（共 100 列）

### 📊 市場（25 列）

| 能力 ID | 能力 | Old UI（path::symbol） | Legacy New UI（path::symbol） | New UI2 現況（path::symbol） | 功能存在 | 真資料 | 互動 | 缺值處理 | 測試證據 | 缺口等級 | F/I｜備註 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MK-01 | 今日結論句（大盤判斷；M01） | src/ui/tabs/macro/section_traffic_light.py::render_traffic_light_top | src/ui/views/page_market.py::render_page_market（呼叫 shared/market_conclusion.py::build_market_conclusion） | src/services/ui2/real_canonical.py::_market（conclusion＝_not_provided「今日結論」）；src/ui2/components/html.py::conclusion_row_html | 部分 | 否 | 否 | 誠實 | tests/test_ui2_batch3.py | major | F｜UI2 只有占位列，無句子來源；VM 規定逐字帶出、不自行推導 |
| MK-02 | 市場位階 Regime（紅綠燈多空的結論；M01） | src/ui/tabs/macro/section_traffic_light.py::render_traffic_light_top | src/ui/views/page_market.py::regime_clause | src/services/ui2/real_canonical.py::regime_spec；src/services/ui2/real_feed.py::_read_regime | 是 | 是 | 否 | 誠實 | tests/test_ui2_real_feed.py | major | F 路徑為真；I UI2 無任何入口寫入 warroom_summary（更新 CTA disabled），實值多半為「尚未載入」，未實機驗 |
| MK-03 | 台股加權指數最新收盤卡（M08 之台股） | src/ui/tabs/macro/section_short.py::render_section_short | src/ui/views/page_market.py::frame_last_close | src/services/ui2/real_canonical.py::twii_card_spec；src/services/ui2/real_feed.py::_read_twii | 是 | 是 | 否 | 誠實 | tests/test_ui2_real_feed.py | none | F 讀 git 追蹤的 data_cache/twii_ohlcv.parquet；含 stale／unavailable 分流；Cloud 線上實值 NOT VERIFIED |
| MK-04 | 台股走勢主圖（M09／T13 之大盤端） | src/ui/tabs/tab_macro_v2.py::_render_kline_card | src/ui/views/_market_blocks.py::render_chart_a（收盤線＋MA5/60/120/200 水平參考線） | src/services/ui2/real_canonical.py::kbar_chart_spec；src/ui2/components/html.py::kbar_chart_html（最近 20 根日 K，靜態 SVG） | 是 | 是 | 否 | 誠實 | tests/test_ui2_twii_kbar.py | minor | F UI2 無 MA／成交量／縮放（DEC-156 未核准）；Cloud 驗收 #1107 為 PARTIAL（引自資料可用性矩陣）→ 線上 NOT VERIFIED |
| MK-05 | Risk Cap／建議總持股水位（市場端；M02） | src/ui/tabs/macro/section_traffic_light.py::render_position_throttle | src/ui/views/_market_blocks.py::render_core_tiles（數值未核准，顯示 ⬜） | src/services/ui2/real_canonical.py::_risk_cap_row（恆 undeterminable） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_real_feed.py::test_regime_fact_never_carries_risk_cap_fields | critical | F FINAL 標 critical；UI2 刻意不收 Risk Cap 欄位，固定「無法判定」 |
| MK-06 | System Action State／是否需要行動（M03／M04） | src/ui/tabs/macro/section_warroom.py::render_section_warroom（今日作戰室）；src/ui/tabs/tab_today.py::build_today_blocks（該模組未掛在 app.py） | src/ui/views/_market_blocks.py::render_alerts_block | src/services/ui2/market_vm.py::build_market_page_vm（「是否需要行動」恆待 Aggregator） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_batch3.py | critical | F FINAL M03 critical（正式來源未建）；UI2 不推導動作 |
| MK-07 | 今日主要風險 3–5 項（M07） | 無（FINAL：舊無） | src/ui/views/_market_blocks.py::build_market_risks；src/ui/views/_market_blocks.py::render_chart_d | src/services/ui2/real_canonical.py::_market（main_risk＝_not_provided）；src/ui2/components/html.py::main_risk_html | 部分 | 否 | 否 | 誠實 | tests/test_ui2_batch3.py | major | F |
| MK-08 | 一鍵更新今日戰情 CTA（M19） | src/ui/tabs/macro/handlers.py::_on_refresh_click | src/ui/views/_market_blocks.py::render_update_cta | src/services/ui2/real_canonical.py::_market（cta disabled_reason「目前不提供更新」）；src/ui2/components/html.py::cta_html | 部分 | N-A | disabled | 誠實 | tests/test_ui2_batch3.py | major | F UI2 無法觸發任何更新 ⇒ 依賴 session 的項目（位階、16 燈、國際）無入口產生；Cloud 無 macro_state.json／risk_cap_state.json（引自資料可用性矩陣 §2） |
| MK-09 | VIX 指標卡（M08／M11） | src/ui/tabs/macro/section_mid.py::render_section_mid | src/ui/views/page_today.py::build_indicator_tiles | src/services/ui2/real_canonical.py::_market（vix＝_not_provided） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_real_feed.py::test_whitelist_checker_has_teeth_against_a_fabricated_vix | major | F 資料可用性矩陣：方案 C 維持空槽，待「只用已完成收盤」規則實作（D2） |
| MK-10 | US10Y 指標卡（M08） | src/ui/tabs/macro/section_long.py::render_section_long | src/ui/views/page_today.py::build_indicator_tiles | src/services/ui2/real_canonical.py::_market（us10y＝_not_provided） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_real_feed.py | major | F 矩陣：FRED DGS10 單一路徑 adapter（方案 B）待客戶選口徑 D1；Cloud 線上 NOT VERIFIED |
| MK-11 | 利差卡（10Y-2Y／10Y-3M；M08） | 無（repo 內僅 tab_edu 教學文字出現 T10Y2Y；本檔 grep 未見取數，單組） | 無 | src/services/ui2/real_canonical.py::_market（spread＝_not_provided「尚無正式定義」） | 部分 | N-A | 否 | 誠實 | tests/test_ui2_real_feed.py | minor | F/I 定義未訂（矩陣 D3）；舊側也無取數，故非遺失 |
| MK-12 | DXY 卡（M08） | src/ui/tabs/macro/section_long.py::render_section_long | src/ui/views/page_today.py::build_indicator_tiles | src/services/ui2/real_canonical.py::_market（dxy＝_not_provided） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_real_feed.py | major | F 矩陣：舊備援鏈可能落到 UUP（ETF）— 重用前須定單一口徑 |
| MK-13 | PMI／景氣卡（M08） | src/ui/tabs/macro/section_state.py::render_section_state | src/ui/views/page_today.py::build_indicator_tiles | src/services/ui2/real_canonical.py::_market（pmi＝_not_provided「用 PMI 或景氣燈號待定義」） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_real_feed.py | major | F 矩陣：tw_pmi 末列 2026-10-01，來源 is_proxy＝True，抓取結果 UNDETERMINED（引自矩陣，未重驗） |
| MK-14 | 國際趨勢 small multiples（M10） | src/ui/tabs/macro/section_long.py::render_section_long | src/ui/views/_market_blocks.py::render_chart_b | 無（Real Feed 只接 TWII＋位階） | 否 | N-A | 否 | N-A | NONE（UI2）；Primary 槽相關見 tests/test_ui2_p2_primary_slot.py | major | F 舊 chart_b 讀 session cl_data[intl]，UI2 G2F 守衛不允許直接讀（矩陣 §7） |
| MK-15 | 16 燈指標明細（M06） | src/ui/tabs/macro/section_overview.py::render_section_overview | src/ui/views/page_today.py::build_indicator_tiles | src/services/ui2/real_canonical.py::_market（section detail＝_not_provided，L3） | 否 | N-A | 否 | N-A | tests/test_ui2_p3_evidence_preservation.py | major | F VM 有占位，但 L2／L3 依 Active Contract 不渲染（view 層不畫） |
| MK-16 | 五桶摘要／指標危險度（OLD-2） | src/ui/tabs/macro/section_summary_bar.py::render_five_bucket_summary | src/ui/views/page_today.py::build_bucket_tiles | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | major | F |
| MK-17 | 景氣拐點六大面向／CPI×Fed／總經拼圖（M13） | src/ui/tabs/macro/section_state.py::render_section_state | src/ui/views/page_market.py（僅 caption 指回舊版） | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | major | F |
| MK-18 | 市場廣度／ADL（M14） | src/ui/tabs/macro/section_short.py::render_section_short | src/ui/views/page_market.py::_render_x5 | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | minor | F |
| MK-19 | 大盤籌碼：法人／融資／熱錢（M15） | src/ui/tabs/macro/section_chips.py::render_section_chips；src/ui/tabs/hot_money.py::render_hot_money_section | src/ui/views/page_market.py::_render_x8 | 無（finmind_inst／finmind_margin parquet 存在但 UI2 不接） | 否 | N-A | 否 | N-A | NONE（UI2） | major | F 矩陣：不在 #1110 範圍 |
| MK-20 | 風險雷達／攻擊發動／策略矩陣（M16） | src/ui/tabs/macro/section_mid.py::render_section_mid；src/ui/tabs/macro/section_cross_ai.py::render_section_cross_ai | 無（VIX 否決內生於 allocation_service） | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | major | F FINAL 註「或客戶裁示退場」 |
| MK-21 | 總經指南針（M17） | src/ui/render/app_render.py::render_macro_compass | 無（新模式刻意不畫） | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | minor | F |
| MK-22 | News AI 總裁決／新聞掃描（M18） | src/ui/tabs/macro/section_news_ai.py::render_section_news_ai | src/ui/views/page_market.py（「問 AI」expander＝新版尚未提供） | src/services/ui2/real_canonical.py::_market（onebrain＝_not_provided，Stage G） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_p2_primary_slot.py | major | F |
| MK-23 | OneBrain Outlook（新能力，舊無） | 無 | src/ui/views/_market_blocks.py::render_ai_status_line（僅 AI／資料狀態一行） | src/ui2/views/market.py::render（section_l1_html 渲染 onebrain 占位） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_p2_primary_slot.py | minor | F 屬 Stage G 新能力，非遺失 |
| MK-24 | 大盤 EPS×PE 模型（M20） | 無（FINAL：舊 UI 不存在） | src/ui/views/_market_blocks.py::render_chart_c（研究框架未啟用，不畫圖） | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | none | F 維持 Research，禁止以簡報假設造現值；非能力遺失 |
| MK-25 | 總經 v2 密度／搜尋／分類（M21） | src/ui/tabs/tab_macro_v2.py::render_tab_macro_v2 | 無 | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | minor | F |

### 🎯 標的（31 列）

| 能力 ID | 能力 | Old UI（path::symbol） | Legacy New UI（path::symbol） | New UI2 現況（path::symbol） | 功能存在 | 真資料 | 互動 | 缺值處理 | 測試證據 | 缺口等級 | F/I｜備註 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TG-01 | 市場精選／即時查一檔 雙模式切換（T11） | 無（舊為分頁堆疊） | src/ui/views/page_target.py::render_page_target（單頁直排，無雙模式） | src/ui2/views/target.py::render（radio ui2_target_mode） | 是 | N-A | 是 | 誠實 | tests/test_ui2_batch3.py::test_target_has_exactly_two_modes_curated_default | none | F FINAL T11「無雙模式」對 UI2 已過期；Legacy 仍單頁 |
| TG-02 | 單檔代碼搜尋輸入（T09） | src/ui/tabs/tab_stock.py::render_tab_stock | src/ui/views/_target_blocks.py::render_search_form | src/ui2/components/html.py::search_html（disabled Preview） | 部分 | 否 | disabled | 誠實 | tests/test_ui2_batch3.py::test_search_box_and_cta_present_in_both_modes_and_not_actionable | major | F 解封前須先查舊 load_single 副作用（Old-First 稽核 TGT-01） |
| TG-03 | 名稱搜尋（T10） | 無（舊只收代碼） | 無（UNCOVERED_ITEMS 自陳只能輸入代碼） | src/services/ui2/real_canonical.py::_target（name_search＝_not_provided；placeholder 寫「代碼／名稱」） | 否 | N-A | 否 | 誠實 | tests/test_ui2_batch3.py | minor | F 新能力、舊也無；FINAL 標 major；I placeholder 提到「名稱」但實際未提供，靠旁註說明，使用者可能誤讀 |
| TG-04 | 單檔結果 Header＋6 維 Snapshot（T12） | src/ui/tabs/stock_sections/section_health_score.py::render_health_score_section | src/ui/views/_target_blocks.py::render_summary_tiles | src/services/ui2/real_canonical.py::_target（lookup.snapshot；僅 dim_market_env 為真位階）；src/ui2/components/html.py::snapshot_html | 部分 | 否 | 否 | 誠實 | tests/test_ui2_batch3.py::test_six_dim_snapshot_order_and_semantics | major | F Real 軸 lookup.queried 恆 False ⇒ 查詢結果區塊不渲染；FAKE 軸才有示意 |
| TG-05 | 產業機會 Top 5／熱力圖／資金泡泡（T01） | src/ui/tabs/tab_sector_flow.py::render_tab_sector_flow；src/ui/render/etf_render.py::render_sector_heatmap | src/ui/views/_target_blocks.py::render_zone_industry | src/services/ui2/real_canonical.py::_target（industry_top＝_not_provided） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_real_feed.py | major | F 矩陣 B4：sector_flow_service 可帶私有 Sheet 參數，重用須固定不傳 |
| TG-06 | 產業趨勢（基本面成長／相對強弱／估值；T02） | 無（舊無正式定義） | src/ui/views/_target_blocks.py::ZONE1_MISSING_DIMS（「尚未建置」） | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | minor | F 定義未核准，屬研究項 |
| TG-07 | 候選標的 Top N＋完整清單＋CSV（T03） | app.py::tab_screener（選股網內嵌區塊，V-APP-1） | src/ui/views/_target_blocks.py::render_zone_candidates；src/ui/views/_target_blocks.py::build_candidate_rows；src/ui/views/_target_blocks.py::candidate_csv_bytes | src/services/ui2/real_canonical.py::_target（candidates＝_not_provided） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_real_feed.py（UI2: 僅 Real 軸占位）；舊側參考 tests/test_p5_2_target_candidates.py | major | F |
| TG-08 | 選股條件 5 因子＋開始選股（T05） | app.py::tab_screener（選股網內嵌區塊） | src/ui/views/_target_blocks.py::render_screen_form | src/services/ui2/real_canonical.py::_target（section conditions＝_not_provided，L2 預設收合 expander） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_p3_evidence_preservation.py | major | F src/ui2/views/_page.py::SHOWN_FOLDS 允許此 expander |
| TG-09 | 基本面初篩逐檔明細＋涵蓋率警示（T04） | src/ui/tabs/tab_stock_picker.py::render_prescreen_panel | 部分（只有條件說明＋存活池檔數） | 無 | 否 | N-A | 否 | N-A | NONE（UI2）；舊側參考 tests/test_screener_candidates.py | major | F/I FINAL 該列自標 INFERENCE |
| TG-10 | 加入觀察清單（寫 Sheet；T06） | src/ui/tabs/portfolio_manager.py::_render_stock_section；src/services/watchlist_service.py::add_picks_to_watchlist | 無（UNCOVERED_ITEMS 列出） | src/services/ui2/real_canonical.py::_target（add_watch disabled「加入觀察（尚未提供）」） | 部分 | N-A | disabled | 誠實 | tests/test_ui2_batch3.py::test_add_to_watch_cta_is_disabled_and_has_no_write_logic | major | F 寫入類，需 OAuth／Sheet 寫入 Gate；UI2 明文隔離不寫入 |
| TG-11 | 凍結前 20 名＋前進式驗證對帳（T07） | app.py::tab_screener（內嵌「前進式驗證：凍結本次選股」區塊）；src/services/forward_test_service.py | 無（UNCOVERED_ITEMS） | 無 | 否 | N-A | 否 | N-A | NONE（UI2）；舊側參考 tests/test_forward_test_freeze.py | major | F 凍結由 cron 每月自動；picks.parquet 為無法重建的凍結快照 |
| TG-12 | 全台股跨季趨勢排行＋CSV（T08） | src/services/fundamental_screener_service.py::get_cross_quarter_trends | 無 | src/services/ui2/real_canonical.py::_target（section full＝_not_provided，L3 不渲染） | 否 | N-A | 否 | N-A | tests/test_ui2_p3_evidence_preservation.py | minor | F |
| TG-13 | 個股 K 線＋均線（T13） | src/ui/tabs/stock_sections/section_kline_chart.py::render_kline_chart_section | src/ui/views/_target_blocks.py::SINGLE_CHART_REASON（灰色占位「K 線新版尚未接上」） | 無（日 K 僅限 TWII 大盤，見 MK-04） | 否 | N-A | 否 | N-A | NONE（UI2） | major | F |
| TG-14 | 基本面：財報體檢／財報領先／月營收／龍頭預警（T14） | src/ui/tabs/stock_sections/section_health_score.py::render_health_score_section；src/ui/tabs/stock_sections/section_financial_leading.py::render_financial_leading_section；src/ui/tabs/stock_sections/section_revenue.py::render_revenue_trend_section | src/ui/views/_target_blocks.py::render_stock_blocks（財報體檢卡） | src/services/ui2/real_canonical.py::_target（lookup 基本面 lk_f1＝_not_provided） | 部分 | 否 | 否 | 誠實 | NONE（UI2）；舊側參考 tests/test_d1_stock_tab.py | major | F |
| TG-15 | 估值現況：357 殖利率／PE／PB（T15） | src/ui/tabs/stock_sections/section_357_valuation.py::render_357_valuation_section | src/ui/views/_target_blocks.py::render_stock_blocks | src/services/ui2/real_canonical.py::_target（lookup 估值 lk_f2＝_not_provided） | 部分 | 否 | 否 | 誠實 | NONE（UI2） | major | F Legacy 無 PB |
| TG-16 | 歷史估值區間：殖利率／PE／PB 河流圖（T16） | src/ui/tabs/stock_sections/section_357_valuation.py::_render_pe_river | 無 | 無 | 否 | N-A | 否 | N-A | NONE（UI2）；舊側參考 tests/test_pe_river_merge_dtype.py | critical | F FINAL critical；357 倍數帶屬 HI-3 未核准 |
| TG-17 | Forward EPS／Fair Value（T17） | 無（FINAL grep 0 命中） | 無 | src/services/ui2/real_canonical.py::_target（估值標籤「EPS basis／PE 口徑」＝_not_provided） | 否 | N-A | 否 | 誠實 | NONE（UI2） | minor | F/I 資料源不存在，屬研究 Gate；FINAL 標 major（資料源 Gate） |
| TG-18 | 單檔籌碼：近 20 日／爆量／集保大戶（T18） | src/ui/tabs/stock_sections/section_chips_20d.py::render_chips_20d_section；src/ui/tabs/chip_radar.py::render_chip_radar | src/ui/views/_target_blocks.py::render_stock_blocks（stock_chips_service；無集保大戶） | src/services/ui2/real_canonical.py::_target（dim_chips＝_not_provided） | 部分 | 否 | 否 | 誠實 | NONE（UI2） | major | F |
| TG-19 | 單檔所屬產業脈絡（T19） | 無 | 無（僅候選表產業欄） | src/services/ui2/real_canonical.py::_target（dim_industry＝not_evaluated） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_batch3.py | minor | F 舊也無單檔產業區 |
| TG-20 | 單檔風險：VCP／布林／心理檢查（T20） | src/ui/tabs/stock_sections/section_vcp_bollinger.py::render_vcp_bollinger_section；src/ui/tabs/stock_sections/section_psy_checklist.py::render_psy_checklist_section | src/ui/views/_target_blocks.py::RISK_PLACEHOLDER（「個股風險指標尚未提供」） | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | major | F |
| TG-21 | 個股買賣語意：停利停損／目標價／三維出場（T21） | src/ui/tabs/stock_sections/section_when_buy_sell.py::render_when_buy_sell_section；src/ui/tabs/stock_sections/section_op_recommendation.py::render_op_recommendation_section；src/ui/tabs/stock_sections/section_strategy_conclusion.py::render_strategy_conclusion_section | 無（RESEARCH_ONLY_NOTE） | 無（UI2 明文不產生買賣判斷） | 否 | N-A | 否 | N-A | tests/test_ui2_batch3.py::test_target_creates_no_buy_judgement_or_action_authority | critical | F FINAL critical：保留或正式退場為客戶 Gate；UI2 現狀＝等同「未承接」 |
| TG-22 | 型態目標價 ZigZag（T22） | src/ui/tabs/pattern_targets_ui.py::render_pattern_targets_for_ticker | 無 | 無 | 否 | N-A | 否 | N-A | NONE（UI2）；舊側參考 tests/test_pattern_targets_ui_mounted.py | major | F 與 T21 同屬目標價語意，需裁示 |
| TG-23 | AI 首席顧問／AI 財報體檢（T23） | src/ui/tabs/tab_stock.py::render_tab_stock | src/ui/views/_target_blocks.py::AI_PLACEHOLDER | src/services/ui2/real_canonical.py::_target（lookup 研究解釋 lk_f3＝_not_provided，Stage G） | 部分 | 否 | 否 | 誠實 | NONE（UI2） | major | F |
| TG-24 | 個股↔總經／持倉 banner、相關新聞（T24） | src/ui/tabs/macro_stock_link.py；src/ui/tabs/portfolio_linkage.py | 無 | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | minor | F 模組以路徑核對，未指定符號 |
| TG-25 | ETF 單檔三判決卡（T25） | src/ui/etf/etf_tab_single.py::render_etf_single | src/ui/views/_target_blocks.py::render_etf_blocks | 無 | 否 | N-A | 否 | N-A | NONE（UI2）；舊側參考 tests/test_etf_tab_imports.py | major | F |
| TG-26 | ETF 明細七段／3-3-3／標準差帶（T26／T27） | src/ui/etf/etf_tab_single.py::render_etf_single；src/ui/etf/etf_tab_smart.py::render_333_section | 無（UNCOVERED_ITEMS） | 無 | 否 | N-A | 否 | N-A | NONE（UI2）；舊側參考 tests/test_etf_smart_ticker_wiring.py | major | F V-SMART-CACHE-1 自建 cache 屬既有待修，重用前須先處理 |
| TG-27 | 多檔比較（個股≤10、ETF 7 維；T28） | src/ui/tabs/tab_stock_grp.py::render_stock_grp；src/ui/etf/etf_tab_grp_compare.py::render_etf_grp_compare | src/ui/views/_target_blocks.py::render_batch（進階分析批次表≤20） | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | minor | F |
| TG-28 | 三階段濾網＋AI 報告／組合體檢（T29） | src/ui/tabs/stock_grp_sections/section_ai_portfolio.py::render_ai_portfolio_section | 無 | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | minor | F/I FINAL 註舊 UI 內可能不可達，未重驗 |
| TG-29 | 帶入我的持股（T30） | NOT VERIFIED（FINAL 記為舊持股頁；本檔未逐檔核對） | 無（UNCOVERED_ITEMS） | 無（UI2 明文查一檔不加入持股） | 否 | N-A | 否 | N-A | NONE（UI2） | minor | I |
| TG-30 | 市場位階 context 一行（新增，W-4） | 無 | 無 | src/services/ui2/real_canonical.py::_target（context_rows＝regime_spec＋Risk Cap） | 是 | 是 | 否 | 誠實 | tests/test_ui2_batch3.py::test_target_market_regime_follows_the_same_market_context | none | F 與 📊 同一份 snapshot；實值情況同 MK-02 |
| TG-31 | 查一檔 session 隔離聲明（新增） | 無 | 無 | src/services/ui2/real_canonical.py::_target（lookup.isolation_note） | 是 | N-A | 否 | 誠實 | tests/test_ui2_batch3.py::test_lookup_writes_only_ui2_prefixed_session_state | none | F 僅文字聲明＋守衛；功能本體尚未啟用 |

### 💼 持股（16 列）

| 能力 ID | 能力 | Old UI（path::symbol） | Legacy New UI（path::symbol） | New UI2 現況（path::symbol） | 功能存在 | 真資料 | 互動 | 缺值處理 | 測試證據 | 缺口等級 | F/I｜備註 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| HD-01 | Portfolio Risk Cap＋目前曝險 vs Cap（H01） | 無（FINAL：無 exposure-vs-cap 比較） | src/ui/views/page_hold.py::build_position_cap_card（僅市場端區間；無目前曝險） | src/services/ui2/real_canonical.py::_hold（context_rows：Risk Cap＝undeterminable；目前曝險＝「無現金／總資產來源」）；src/ui2/components/html.py::hold_l1_v2_html | 部分 | 否 | 否 | 誠實 | tests/test_ui2_hold_w11_batch1.py | critical | F FINAL critical；Sheet 表頭無現金／總資產（FINAL 單組 grep，未重驗） |
| HD-02 | System Action／今日需處理（H02／H03） | src/ui/etf/etf_tab_dividend_station.py::render_dividend_station（compute/etf/dividend_station.action_branch） | src/ui/views/page_hold.py::build_action_card；src/ui/views/page_hold.py::build_todo_card | src/ui2/components/html.py::hold_action_row_html（今日需處理單行占位） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_hold_header.py | critical | F FINAL critical；動作詞彙（減碼 1/2、全出）與 Risk Cap 封鎖尚無正式規則 |
| HD-03 | 讀取持股（Google 登入＋Sheet；整頁真資料前置） | src/ui/tabs/portfolio_binder.py::render_holdings_binder | src/ui/views/page_hold.py::load_holdings；src/ui/views/page_hold.py::load_binding | src/services/ui2/real_canonical.py::_hold（portfolio／holdings_table＝_not_provided「需登入並讀取 Sheet」） | 否 | N-A | 否 | 誠實 | tests/test_ui2_hold_w11_batch1.py | critical | F 本檔暫定：持股頁其餘各列皆依賴此前置，故升 critical；UI2 明文不接 OAuth／Sheet |
| HD-04 | 持股清單／逐檔表（H04） | src/ui/etf/etf_tab_dividend_station.py::_render_layer1 | src/ui/views/page_hold.py::build_holdings_preview_card（葉2 唯讀預覽） | src/ui2/components/html.py::hold_table_html（桌機八欄／手機四欄；無資料＝欄名＋原因） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_hold_w11_batch1.py | major | F FINAL H04「無逐檔表」對 Legacy 已部分過期（葉2 有預覽卡） |
| HD-05 | 235 燈牆／逐盞明細（H07） | src/ui/etf/etf_tab_dividend_station.py::_render_light_detail | src/ui/views/page_hold.py::build_lightwall_card | 無 | 否 | N-A | 否 | N-A | NONE（UI2）；舊側參考 tests/test_p04_hold_view.py | major | F |
| HD-06 | 80/20 配置偏離＋衛星停利（H08） | src/ui/etf/etf_tab_dividend_station.py::_render_allocation_take_profit | src/ui/views/page_hold.py::build_allocation_split_card；src/ui/views/page_hold.py::build_take_profit_card | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | major | F |
| HD-07 | 換股建議（H09） | src/ui/etf/etf_tab_dividend_station.py::_render_switch_advice | src/ui/views/page_hold.py::build_switch_card | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | major | F |
| HD-08 | VaR／壓測／配息現金流（H10） | src/ui/etf/etf_tab_portfolio.py::render_etf_portfolio | src/ui/views/page_hold.py::build_var_card；src/ui/views/page_hold.py::build_stress_card；src/ui/views/page_hold.py::build_dividend_cash_card | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | major | F |
| HD-09 | 再平衡／Overlap／效率前緣／對 0050／稅後（H11） | src/ui/etf/etf_tab_portfolio.py::render_etf_portfolio | src/ui/views/page_hold.py::build_deep_cards（再平衡為 UnwiredSpec） | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | major | F |
| HD-10 | 建議持股水位（市場端區間；H01 之一部） | 無 | src/ui/views/page_hold.py::build_position_cap_card | src/ui2/components/html.py::hold_body_html（cap 空槽；⛔ 讀 Risk Cap／區間數字） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_hold_w11_batch1.py | major | F 數值啟用屬 RC Gate；與 MK-05／HD-01 同案 |
| HD-11 | 產業曝險／集中度（H05） | src/ui/tabs/stock_grp_sections/section_industry_concentration.py::render_industry_concentration_section | 無（FINAL 列為 Legacy 無） | src/ui2/components/html.py::hold_body_html（Primary 空槽） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_hold_w11_batch1.py | major | F |
| HD-12 | 策略分類：存股／資本利得（H06） | 無 | 無（無 UI consumer） | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | minor | F FINAL：strategy_class_reader 僅 L1 自用 |
| HD-13 | AI 戰情總結（H13） | src/ui/etf/etf_tab_dividend_station.py::_render_ai_summary | src/ui/views/page_hold.py::build_ai_summary_card（付費 Gemini 直呼，無 Digest grounding） | src/services/ui2/real_canonical.py::_hold（OneBrain 持股摘要＝_not_provided，Stage G） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_hold_w11_batch1.py | major | F Legacy 的 Gemini 直呼不得搬入 UI2（Reuse Matrix V5） |
| HD-14 | 葡萄串領息（H12） | src/ui/tabs/grape_ladder.py::render_grape_ladder | src/ui/views/page_hold.py::build_deep_cards（UnwiredSpec） | 無 | 否 | N-A | 否 | N-A | NONE（UI2）；舊側參考 tests/test_etf_smart_ticker_wiring.py | minor | F |
| HD-15 | 同名兩套刻度揭露（H14） | 無 | src/ui/views/page_hold.py::build_scale_card | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | minor | F |
| HD-16 | 持股↔Sheet 綁定狀態／組合設定（H15） | src/ui/tabs/portfolio_binder.py::render_holdings_binder | src/ui/views/page_hold.py::build_binding_card | 無（歸 👤 我的，見 ME-02） | 否 | N-A | 否 | N-A | NONE（UI2） | minor | F |

### 👤 我的（14 列）

| 能力 ID | 能力 | Old UI（path::symbol） | Legacy New UI（path::symbol） | New UI2 現況（path::symbol） | 功能存在 | 真資料 | 互動 | 缺值處理 | 測試證據 | 缺口等級 | F/I｜備註 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ME-01 | Google 登入／登出／重新登入（E01） | src/ui/tabs/portfolio_binder.py::render_login_cta | src/ui/views/page_me.py::build_account_card | src/ui2/views/me.py::render；src/ui2/components/html.py::account_actions_html（FAKE 示意；Real 軸 account＝None） | 部分 | 否 | disabled | 誠實 | tests/test_ui2_batch3.py::test_me_three_account_states_have_the_right_primary_cta_and_disabled_actions | major | F FINAL E01「已承接」僅指 Legacy；UI2 為 FAKE 帳戶態，非登入證據 |
| ME-02 | Sheet URL／ID、Drive 清單、使用這本（E02） | src/ui/tabs/portfolio_binder.py::render_drive_picker；src/ui/tabs/portfolio_binder.py::render_paste_id_binder | src/ui/views/page_me.py::build_sheet_card | src/services/ui2/real_canonical.py::_me（sheet＝_not_provided） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_batch3.py | major | F |
| ME-03 | active portfolio／watchlist 選定（E03） | 無（隱性取第一本） | src/ui/views/page_me.py::build_content_card | src/services/ui2/real_canonical.py::_me（portfolio／watchlist＝_not_provided） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_batch3.py | minor | F |
| ME-04 | Sheet／組合／觀察清單／持股列 CRUD（E04） | src/ui/tabs/portfolio_manager.py::render_portfolio_manager | 無（page_me 檔頭「不搬 CRUD」） | 無（UI2 明文 ⛔ 讀寫 Sheet） | 否 | N-A | 否 | N-A | tests/test_ui2_batch3.py::test_ui2_has_no_oauth_sheet_or_secrets_call | major | F 需 HI-5／OAuth Gate |
| ME-05 | Strategy 設定（E05） | 無 | 無 | src/services/ui2/real_canonical.py::_me（settings strategy＝_not_provided） | 部分 | N-A | 否 | 誠實 | tests/test_ui2_batch3.py | minor | F |
| ME-06 | Notifications 設定（E06） | 無（只有 cron／scripts/push_*） | 無 | src/services/ui2/real_canonical.py::_me（settings notify＝_not_provided） | 部分 | N-A | 否 | 誠實 | tests/test_ui2_batch3.py | minor | F |
| ME-07 | Display preference（E07） | 無 | 無 | src/services/ui2/real_canonical.py::_me（settings display＝_not_provided） | 部分 | N-A | 否 | 誠實 | tests/test_ui2_batch3.py | minor | F |
| ME-08 | Decision Digest Viewer（E08） | 無 | 無（builder／summary 0 production caller；本檔 grep src／scripts／shared／app.py 僅見自身與 decision_digest_terms 提及） | src/services/ui2/real_canonical.py::_me（Audit：Decision Digest＝_not_provided，預設收合 expander） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_p3_evidence_preservation.py | critical | F FINAL critical（Stage F 前置）；UI2 僅占位 |
| ME-09 | Rule Registry 唯讀（E09） | src/ui/tabs/tab_edu.py::render_tab_edu（逐盞門檻對照表） | src/ui/views/page_why.py::load_specs（僅 ?legacy=1 可達） | src/services/ui2/real_canonical.py::_me（Audit：Rule Registry＝_not_provided，預設收合 expander） | 部分 | 否 | 否 | 誠實 | tests/test_ui2_p3_evidence_preservation.py | major | F |
| ME-10 | Data Freshness 資料健康牆（E10） | src/ui/pages/data_coverage.py::render_data_coverage | src/ui/pages/sidebar_health.py::render_sidebar_data_health（兩模式側欄） | src/services/ui2/real_canonical.py::_me（Audit：Data Freshness＝_not_provided，L2 不渲染） | 否 | N-A | 否 | N-A | tests/test_ui2_p3_evidence_preservation.py | major | F 完整對應見 🗂 DT-01 |
| ME-11 | System Information（E11） | 無 | 無 | src/services/ui2/real_canonical.py::_me（System Information＝_not_provided，L2 不渲染） | 否 | N-A | 否 | N-A | tests/test_ui2_p3_evidence_preservation.py | minor | F |
| ME-12 | AI 問答（E15） | src/ui/tabs/tab_ai_chat.py::render | src/ui/views/page_why.py::render_page_why（僅 ?legacy=1 可達） | 無（OneBrain Stage G） | 否 | N-A | 否 | N-A | NONE（UI2）；舊側參考 tests/test_sec_r19_ai_panel_scrub.py | major | F |
| ME-13 | 教學：策略說明書／總經小教室（E14） | src/ui/tabs/tab_edu.py::render_tab_edu | 無 | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | minor | F |
| ME-14 | 免責聲明 footer（E17） | app.py::_render_footer | app.py::_render_footer（兩模式皆呼叫） | 無（src/ui2、shared/ui2_contract、src/services/ui2 grep 免責／compliance／非投資建議／僅供參考 0 命中） | 否 | N-A | 否 | N-A | NONE（UI2） | major | F 無；I 是否為 cutover 必備由客戶決定，未見裁示，NOT VERIFIED |

### 🗂 資料（6 列）

| 能力 ID | 能力 | Old UI（path::symbol） | Legacy New UI（path::symbol） | New UI2 現況（path::symbol） | 功能存在 | 真資料 | 互動 | 缺值處理 | 測試證據 | 缺口等級 | F/I｜備註 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| DT-01 | 資料健康牆／來源覆蓋率／資料日（E10；CV-58） | src/ui/pages/data_coverage.py::render_data_coverage | src/ui/pages/sidebar_health.py::render_sidebar_data_health（側欄總覽） | src/services/ui2/data_page.py::data_page_canonical；src/ui2/views/data.py::render（全為 Capability「尚未提供」空殼） | 部分 | 否 | disabled | 誠實 | tests/test_ui2_guards.py（P4_DATA 登記；無專屬頁面測試，NOT VERIFIED） | major | F DEC-146 第一批僅空殼；CTA「查看資料健康度」disabled |
| DT-02 | 資料源清單／Fetcher 監控（E12） | src/ui/pages/data_registry_panel.py::render_data_registry_panel；src/ui/pages/data_registry_panel.py::render_fetch_monitor_panel | 無（legacy-only） | 無 | 否 | N-A | 否 | N-A | NONE（UI2）；舊側參考 tests/test_fetch_monitor.py | minor | F |
| DT-03 | §4.3 雙演算法對帳（E12） | src/ui/pages/reconcile_panel.py::render_reconcile_panel | 無 | 無 | 否 | N-A | 否 | N-A | NONE（UI2）；舊側參考 tests/test_reconcile_panel.py | minor | F |
| DT-04 | API 根因診斷（E12） | src/ui/pages/api_diagnostic.py::render_api_diagnostic | 無 | 無 | 否 | N-A | 否 | N-A | NONE（UI2）；舊側參考 tests/test_d6_diagnostic_no_secret_display.py | minor | F 該頁 Secret 片段顯示已於 #1113／D6 移除（api_diagnostic.py 已無 _mask）；資料可用性矩陣 §5 對此已過期 |
| DT-05 | 門檻校準面板（E12） | src/ui/pages/calibration_ui.py::render_calibration_panel | 無 | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | minor | F |
| DT-06 | 副作用控制：測試連線／強制刷新／清快取（E13） | src/ui/pages/health_inspector.py::render_data_health_raw | 側欄兩顆控制（兩模式） | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | minor | F FINAL：不進四頁，維持既有處置 |

### 跨頁／系統（8 列）

| 能力 ID | 能力 | Old UI（path::symbol） | Legacy New UI（path::symbol） | New UI2 現況（path::symbol） | 功能存在 | 真資料 | 互動 | 缺值處理 | 測試證據 | 缺口等級 | F/I｜備註 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SY-01 | 主導覽：五頁頂部兩列（UI2）／四頁（Legacy）／7 頁籤＋側欄（Old） | app.py::tab_market（st.tabs 7 頁籤） | src/ui/views/shell_nav4.py（四頁導覽） | src/ui2/shell/app.py::_render_nav | 是 | N-A | 是 | 誠實 | tests/test_ui2_guards.py；tests/test_ui2_registration_and_boot.py | none | F 頁序＝📊→🎯→💼→👤→🗂（DEC-146）；導覽專屬測試是否涵蓋五頁未逐項檢視 NOT VERIFIED |
| SY-02 | 資料源標示：預設 FAKE 示意／Real-data Preview 單行 banner | 無 | 無 | src/ui2/shell/app.py::run；src/ui2/shell/app.py::_render_dev_surface | 是 | 否 | 是 | 誠實 | tests/test_ui2_p1_human_text.py | none | F 預設 FAKE；Real 只在 ?ui2_dev=1 開發面切換；一般畫面無切換控制 |
| SY-03 | 欄位級資料日／來源／新鮮度 chip | src/ui/tabs/macro/helpers.py（散見） | src/ui/views/_market_blocks.py::data_date_text | src/ui2/components/html.py::freshness_html | 是 | 是 | 否 | 誠實 | tests/test_ui2_real_feed.py | minor | F 目前只有 TWII 與位階有真 as_of／source；其餘欄位為 None |
| SY-04 | 狀態詞彙：stale／unavailable／not_provided／undeterminable 等 | shared/ui_state.py::UI_STATE_META | shared/ui_state.py::UI_STATE_META | src/services/ui2/vm_common.py；shared/ui2_contract/text.py | 是 | N-A | 否 | 誠實 | tests/test_ui2_guards.py；tests/test_ui2_p1_human_text.py | none | F 缺值不補 0／中性 |
| SY-05 | 全域置底常駐條：多空＋建議持股（M22） | app.py::_gl_slot | 無（刻意不畫，避免假訊息） | 無 | 否 | N-A | 否 | N-A | NONE（UI2） | minor | F FINAL：以 L1 取代 |
| SY-06 | 側欄連線狀態／Proxy 只顯示布林（D6） | app.py::_px_set（側欄「Proxy 已設定／未設定」布林） | 同左（兩模式側欄） | 無 | 否 | N-A | 否 | N-A | NONE（UI2）；舊側參考 tests/test_d6_diagnostic_no_secret_display.py | minor | F 側欄已改只顯示布林（app.py 註解 D6） |
| SY-07 | 唯讀與隔離邊界守衛（無 src.data import、無寫入、session key 限 ui2_ 前綴） | 無 | EX-PASSTHRU-1（Legacy 可直呼 public L1 fetcher） | src/services/ui2/real_feed.py（唯一 I/O 檔）；tests/test_ui2_guards.py（G2F） | 是 | N-A | 否 | 誠實 | tests/test_ui2_guards.py | none | F |
| SY-08 | 手機／桌機響應式版面 | 無 | src/ui/views/_market_blocks.py::render_layout_css | src/ui2/shell/css.py | 是 | N-A | 否 | 未驗證 | tests/ui2_viewport/measure_viewport.py；tests/test_ui2_p2_primary_slot.py | minor | I 真瀏覽器量測屬 slow 測試，是否納入 CI／Cloud 實機 NOT VERIFIED |

## 3. 統計（腳本逐列計數，與上方表格實際列數一致）

| 缺口等級 | 列數 |
|---|---|
| critical | **8** |
| major | **49** |
| minor | **34** |
| none | **9** |
| **合計** | **100** |

| 分組 | critical | major | minor | none | 小計 |
|---|---|---|---|---|---|
| 📊 市場 | 2 | 15 | 6 | 2 | 25 |
| 🎯 標的 | 2 | 17 | 9 | 3 | 31 |
| 💼 持股 | 3 | 9 | 4 | 0 | 16 |
| 👤 我的 | 1 | 7 | 6 | 0 | 14 |
| 🗂 資料 | 0 | 1 | 5 | 0 | 6 |
| 跨頁／系統 | 0 | 0 | 4 | 4 | 8 |

- **功能存在**：是 12／部分 38／否 50。**真資料**：是 5／否 33／N-A 62。
- **真資料為「是」的列只有 5 列**，其中 UI2 實質讀取來源只有 TWII（卡片、日 K）與市場位階；位階路徑為真，但 UI2 內沒有任何入口寫入 `warroom_summary`，實值多半為「尚未載入」（INFERENCE，未實機驗）。
- **critical 8 列**：MK-05、MK-06、TG-16、TG-21、HD-01、HD-02、HD-03、ME-08。其中 7 列對應 FINAL 的 critical 7 項（M02→MK-05、M03→MK-06、T16→TG-16、T21→TG-21、H01→HD-01、H02→HD-02、E08→ME-08），**另 1 列 HD-03 為本檔新增判定**（持股頁整頁真資料前置，暫定）。FINAL 原結論「Stage J 第 6 條『無 critical gap』不成立」在 UI2 上**仍然成立**。
- 本檔列數（100）**不等於** FINAL 的 85 列：本檔把 FINAL 部分合併列拆開（如 M08 拆為 VIX／US10Y／利差／DXY／PMI），也新增 UI2 才有的列（五頁導覽、資料源標示、🗂 資料頁、位階 context 等），也未涵蓋 FINAL 的每一列（如 H16 推播腳本無 UI，本檔未列）；**不得**拿兩個列數相減當作差異。

## 4. NOT VERIFIED 清單

1. **Streamlit Cloud 線上實況**：`app_ui2.py` 是否已以最新 main 部署、各 Secret 是否載入、日 K／位階實際顯示——全部 NOT VERIFIED（Issue #1107 UI2 Cloud 日 K 驗收引自矩陣為 PARTIAL，未重驗）。
2. **未執行任何測試或 app**：「測試證據」欄只證明測試檔存在且（多數列）含相關名稱，**不證明通過**。舊側參考測試是否真的斷言對應行為，未逐一檢視。
3. **UI2 位階實值**：UI2 單獨執行時 `warroom_summary` 是否永遠為空（⇒ 位階恆未載入）未實機驗（MK-02、TG-30）。
4. **外部資料可用性**：FRED／Yahoo／FinMind／TWSE／Gemini 的可達性與認證、`^TNX` 刻度、DXY 備援鏈是否落到 UUP、tw_pmi 的 proxy 性質與資料日——全部引自 ISSUE1110 矩陣，本檔未重驗。
5. **「UI2 無此功能」類全稱結論的搜尋範圍**僅限 `src/ui2`、`src/services/ui2`、`shared/ui2_contract`、`app_ui2.py`，單組、未窮舉；免責聲明（ME-14）另以 `免責／compliance／非投資建議／僅供參考` 關鍵字 grep，0 命中，可能漏掉不含這些字樣的等價文案。
6. **Old UI 實機渲染**：`?legacy=1` 的各 tab 實際呈現與行為未跑；Old 欄僅依 `app.py` 路由與 section 檔讀碼。`tab_today.py` 在 `app.py` 未被掛載（grep 0 命中），其 `build_today_blocks` 是否有其他入口未查。
7. **FINAL 表中本檔未逐項重讀者**：M05（月虧損停機）、T24、T29、T30，以及 H05／H06／H12 之 Legacy 側細節——僅依 FINAL 轉錄並核對符號存在，標 INFERENCE 或 NOT VERIFIED。
8. **導覽測試是否涵蓋五頁**：`tests/test_ui2_guards.py` 含 `P4_DATA` 字樣，但專屬五頁導覽斷言未逐項檢視；`tests/test_ui2_batch2.py` 檔頭仍描述「導覽恰四頁、手機底部固定」，是否已與 DEC-146 對齊未查。
9. **響應式／真瀏覽器量測**（SY-08）：`tests/ui2_viewport` 屬 slow 測試，是否納入 CI、是否通過 NOT VERIFIED。
10. **免責聲明是否為 UI2 切換必備**：未見客戶裁示，NOT VERIFIED。

## 5. 聲明

**本表不是施工授權。** 它是 2026-11-10 的讀碼證據與缺口盤點：不新增資料來源、不改公式、不授權接線或啟用任何 disabled 控制項，也不取代各缺口所需的 Source／Model／OAuth／Visual Gate 與客戶裁示。缺口等級為本檔暫定，非客戶核准。依 `CLAUDE.md` §-1，沒有客戶指派不得據此動工。缺值≠0，未驗≠PASS，Proxy≠正式。
