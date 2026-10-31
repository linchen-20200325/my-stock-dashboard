# Phase 4 P4-2（📊 市場頁圖區）— PR 描述素材（`CLAUDE.md` §-1.5 第三條五段＋第四條三段）

- **日期**：2026-10-31｜**分支**：`ccr-c8ef17de-9tw7yt`（基底＝P4-1 main `4c1546b5`＝#984 合併點；P4 還原鏈基底仍為 `7484c57b`）｜**本批狀態**：本地 commit，**未 push、未開 PR**
- **依據**：客戶 DEC-117（Q3=A／Q4=P-B／Q8a）＋DEC-118；線框 `docs/vnext/PHASE4_MARKET_PAGE_WIREFRAME_2026-10-30.md` §10（逐條狀態＝§10.8）；Migration Plan §20 P4-2
- **中間批**：Visual Fidelity Gate **未判**（正式 Gate 在 P4-3）；Stage ⛔ 標 complete
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：本檔與全部實作、量測、mutation 皆為**實作組單組產出，未經第二組驗證**。「其他頁 0 影響」「全鏈綠」「資訊守恆」等全稱句只涵蓋下方列出的實測範圍。
- 📌 **接手說明**：本批是前一組實作被中途停止後的**續做**。工作樹留下的 3 檔修改（`_market_blocks.py`、`page_market.py`、`compact.py`）經逐行審視、與規格一致且完整 ⇒ **沿用**；補了測試、還原鏈重產、量測、文件。

---

## 一、邏輯審查（是否符合核准線框）

| 客戶裁示／驗收條件 | 實作 | 落點 |
|---|---|---|
| Q4=P-B（C4-1）圖 A＝Primary、恰 1 | 圖 A＝整列寬、緊接 L1 決策區（AI 行）；正式原生 `st.line_chart(指數＋MA 水平參考線)`（y 軸、圖例保留，高 220＝契約上限 `compact.SLOT_HEIGHT_MAX_PX`）；冷啟動／讀不到＝同高 220 槽（D6=B） | `_market_blocks.render_chart_a`／`chart_a_chips` |
| Q4（C4-2／C4-3）國際 5 系列＝Secondary small multiples | 一組 5 格（桌 3 欄／手機 2 欄）、各自座標、無切換列、格內無任何數字；缺系列格＝既有字樣 `⬜ 本輪沒有這個系列`（`⬜ 沒有可用收盤`／`⬜ 資料不足／無法判定` 同為既有常數）；系列數固定 5，「其他（未分組）」系列不進格、在摺疊「來源」逐列列出；行內 svg 走 `st.markdown(unsafe_allow_html=True)`（`st.html` 會剝 svg，F-4） | `render_chart_b`／`chart_b_parts`／`intl_core_series` |
| P1R-P4-SM-NAME-LEN | 8 字上限（`compact.SM_NAME_MAX_CHARS`）只對 9 字的 `納斯達克 IXIC`→`那指 IXIC`、`費城半導體 SOX`→`費半 SOX` 做**顯示名**對映（簡稱取自已核准線框 Phase 3 §3.7／Phase 4 §4.1）；`INTL_GROUPS`／`INTL_MAP` 正式名未動，正式全名在摺疊「來源」與 L2「國際市場」表格 | `INTL_DISPLAY_NAMES` |
| Q4（C4-5）不得改趨勢定義；`⬜ 尚未定義` 必須顯示 | 圖 A、圖 B header 各一顆 `⬜ 尚未定義` chip（冷熱皆在、外露）；`CHART_A_MA_DISCLAIMER` 另成獨立 chip（D10(a)）；趨勢結論句（`台股趨勢結論：⬜ 尚未定義`／`國際趨勢結論：…`）逐字下沉「為什麼」；0 新公式（`src/services|compute|data`、`shared/` 0 diff；圖區函式 AST 無 rolling／統計運算） | `chart_a_chips`／`chart_b_parts` |
| Q3=A（C3-1）圖＝「▸ 為什麼／來源／限制／去哪補」 | 圖 A／B／C／D 各**恰一個**、預設收合、四段固定順序、不得留白（不適用寫「—（原因）」，沿用本檔既有句型）；六欄 Basis 依線框 §3.5 逐字分四段；「去哪補」指向頁上真的存在的 L2 展開區標題（`page_market` 算一次、與下方展開區共用同一個字串） | `ChartFold`／`chart_fold`／`render_chart_fold` |
| Q8a（C8-a）圖 C | 外露只剩標題＋「研究框架，未啟用」chip＋`CHART_C_EMPTY` 一行；`CHART_C_SAY`（客戶原句）逐字進「為什麼」、`CHART_C_BASIS` 逐字進「來源」；零數字、零圖形 | `render_chart_c`／`chart_c_fold` |
| 圖 D compact（C6-5／C2） | 「是否惡化：⬜ 尚未定義」由每列重複→header 護欄 chip 寫一次；表格兩欄（桶／方向，與 `risk_panel_rows` 前兩欄同源同字，第三欄若出現預期外內容即 `ValueError`）；**「N 項未評估（共 M 項燈；未評估不等於安全）」外露**；`DANGER_POINTER` 外露；未載入灰、算不出來紅；四類退化路徑保留；`CHART_D_ALL_LAMPS_POINTER` 下沉「去哪補」 | `render_chart_d`／`chart_d_table_rows` |
| C1-7 | Primary 緊接 AI／資料狀態行（P4-1 守衛 `test_c1_7_…` 綠；DOM 實量 AI 行底緣到 Primary 頂緣＝0px） | `page_market.render_page_market` |
| 圖區順序 | 線框 §4.1：Primary → 國際小倍數 → 圖 D → 圖 C，各整列寬，容器間距 16px、之間 0 個元素（測試＋DOM 實量） | `page_market` |

**`compact.py` 只加不改**：`SmCell` 加性欄位 `missing_verbatim`（呼叫端的既有 placeholder 整句；與 `svg`／`missing_state`／`missing_text` 互斥；須以**一個** `UI_STATE_META` 符號＋空格開頭、單行、不含數字）＋唯一驗證點 `_check_missing_verbatim`；既有輸出（golden、既有 287 項 `test_compact`）不變。

**零資料語意證明 (a)～(g)**（FACT：`git diff 4c1546b5 --stat`）：(a) 新資料源 0；(b) schema 0；(c) 公式／門檻／TTL 0（`src/services|compute|data`、`shared/` 0 diff）；(d) Risk Cap 數字顯示 0（本批沒碰水位 tile）；(e) 趨勢定義 0（`⬜ 尚未定義` 照舊外露；圖 A 的 MA 仍是 `mkt_info` 既有純量畫成水平線）；(f) Digest／Brain import 0；(g) `page_today.py`、`app.py`、`requirements.txt`、`markup.py`（page_css）0 diff ⇒ z60 指紋、page_css sha 不變。

**清理項目（v3 §04 強制欄位，逐檔）**：**刪檔 0**。`_market_blocks.py` 內 `render_chart_a`／`render_chart_b`／`render_chart_c` 原地重寫（同名、簽名加 `where_label`），沒有因本批變成 0 caller 的孤兒（AST＋grep 全 repo 逐名檢查，結果 0 個）。舊的「🔍 查看依據」圖用入口、圖 B 的 5 張 350px 原生圖已隨重寫移除（行為取代，非孤兒檔）。

## 二、邊界測試（場景＝實跑）

| 場景 | 結果 |
|---|---|
| 冷啟動 | Primary 同高 220 槽＋灰字 `⬜ 尚未載入，請按更新`（不讀快取、不畫）；國際／圖 D 縮成一行灰字；圖 C 本來就一行；0 紅字 |
| 已載入（夾具） | Primary 原生圖 14 個 y 軸刻度、5 項圖例（指數＋4 MA）；小倍數 5 格、0 數字 |
| 缺系列／沒有收盤／1 點／非有限值 | 各用既有字樣 placeholder；非有限值＝log＋`⬜ 資料不足／無法判定`，⛔ 畫假線 |
| 圖 A 讀不到（灰）／真例外（紅）／過期（琥珀 chip＋摺疊「限制」內警告）／新鮮度未判定（不給 ✅） | 灰紅分離；過期不塗紅；錯誤字串經 `scrub_secrets`（摺疊內同） |
| 圖 D 未載入／算不出來／全部不足／部分不足 | 灰 caption／紅 `st.error`／表格內 `⬜ 資料不足／無法判定` 列；「未評估不等於安全」恆在外露層 |
| 更新報告（乾淨／含真錯誤） | 圖區順序與四段摺疊不變（D1 把報告放到結論下方，不影響圖區） |

## 三、效能評估

- 每輪 script run 不新增 I/O／計算：圖 A 照舊讀本地 parquet（毫秒級）；小倍數 `sparkline_svg` 對 5 個序列各 O(n≤120)；圖 B 不再建 5 張 vega 圖（前端渲染大幅減少）。
- 多注入 `compact_css()`（併進 P4-1 既有的那個 `<style>`，不多一個元素，C1-7 不被插隊）。
- 全頁高（harness 夾具，1.59.2；P4-1→P4-2）：桌機 loaded **5005→3061**、手機 loaded **6726→3747**（圖 B 5 張 350px 原生圖→一組小倍數、摺疊收斂）；cold 桌機 2409→**2573（+164）**、手機 3220→3029（Primary 冷啟動槽依 D6=B 維持 220px 不縮＝設計代價，載入前後 Primary 不跳動）。

## 四、Debug 與修正（本批內部發現並已修）

1. **圖 B 冷啟動時趨勢結論句會掉**：試著去重（`basis_chart_b` 規則欄已含結論句）時發現未載入分支的規則欄**沒有**該句 ⇒ 改為「規則欄沒有才另列一行」（`chart_b_fold`）；`test_c4_5_…[cold]` 與 `tests/test_page_market.py::test_page_mounts_clean` 守住。
2. **自己的守衛有洞（mutation M19 一度綠燈）**：「圖 C 外露不得有 `CHART_C_SAY`」原用 `in list`（整列相等）⇒ header HTML 夾帶原句時比不出來；改子字串比對後 M19 轉紅。
3. **測試環境相依**：圖 A 的指數線來自本地 `data_cache`，新測試檔以 autouse fixture 固定 3 點視圖（個別測試可覆寫），避免 CI／本機差異。
4. 還原鏈：`page_market.py` 有改 ⇒ 以**同一基底 `7484c57b`** 重產 pair（sha `59c9801b…` 不變；4 組；產生時驗「套用後逐字等於基底、每組新寫法現行恰 1 次、基底 0 次」）。
5. **已知、非本批引入**（`P1R-P4-PRIMARY-LEGEND-MOBILE`）：手機 390px 圖 A 圖例單行、後 3 項被裁掉（P4-1 基底同樣；Streamlit 原生圖行為）。

## 五、最終（交付）

### 5.1 變更檔

| 檔 | 變更 |
|---|---|
| `src/ui/views/_market_blocks.py` | 圖區重寫（Primary／小倍數／圖 D compact／圖 C 一行）＋四段摺疊元件（`ChartFold`）；`INTL_DISPLAY_NAMES`；P4-2 常數 |
| `src/ui/views/page_market.py` | 圖區編排（順序＋`where_label`）；L2 展開區標題改用同一變數（字串不變）；docstring 補註 |
| `src/ui_v2/compact.py` | **加性**：`SmCell.missing_verbatim`＋`_check_missing_verbatim` |
| `tests/test_p4_2_market_charts.py`（新） | 55 項（線框 §10 P4-2 條目） |
| `tests/test_p4_1_market_first_screen.py`／`test_uim_market_page.py`／`test_page_market.py`／`ui_v2/test_compact.py` | 改寫為等強或加嚴（皆附 📌 有意識的修改註） |
| `tests/test_p4_revert_chain.py` | 同基底重產 pair |
| `docs/vnext/phase4_market/p4_2/` | 量測腳本、JSON（1.59.2＋floor 1.56.0）、截圖 16 張、本檔 |
| 線框 §10.8、`docs/HANDOFF.md`、`docs/PROJECT_STATE.md`、`docs/BACKLOG.md` | 狀態同步（append-only） |

### 5.2 下沉清單（外露 → 摺疊；全部只下沉、未刪；C8-0）

| 圖 | 原外露內容 | 新位置 |
|---|---|---|
| 圖 A | 趨勢結論 `台股趨勢結論：⬜ 尚未定義` | 外露：header `⬜ 尚未定義` chip；原句逐字→「為什麼」（規則欄內） |
| 圖 A | 來源 caption「近 N 日，資料至…·來源」 | 「來源」 |
| 圖 A | `CHART_A_MA_NOTE`、`TREND_DEFINITION_NOTE`、缺均線清單、新鮮度未判定、過期警告、`⬜ 均線：尚未載入` | 「限制」 |
| 圖 A | 粗體 `CHART_A_MA_DISCLAIMER` | **仍外露**（改成獨立 chip，逐字） |
| 圖 A | 「🔍 查看依據」六欄 | 四段（規則／AI→為什麼；資料／日期→來源；missing／confidence→限制；去哪補＝`請展開下方「台股盤勢（原始資料，不構成趨勢判斷）」`） |
| 圖 B | 5 張 350px 原生圖、y 軸數值 | 小倍數（外露、無數字）；數值（最後收盤、資料日、筆數）＋走勢圖 gate＝L2「國際市場」展開區（原樣未動） |
| 圖 B | 分組小標、每系列「名稱　·　近 N 日，資料至…」、來源 caption | 「來源」（正式全名） |
| 圖 B | `CHART_B_NOTE`、`TREND_DEFINITION_NOTE`；`國際趨勢結論：⬜ 尚未定義` | 「限制」；結論句→外露 chip＋「為什麼」 |
| 圖 C | `CHART_C_SAY`（客戶原句） | 「為什麼」（Q8a，逐字） |
| 圖 C | `CHART_C_BASIS` | 「來源」（逐字） |
| 圖 D | 每列「是否惡化：⬜ 尚未定義」 | header 護欄 chip 寫一次（方向欄資料不足列本來就同字） |
| 圖 D | `CHART_D_ALL_LAMPS_POINTER`「查看全部指標 › …」 | 「去哪補」 |
| 圖 D | 六欄 | 四段 |
| 圖 D | `CHART_D_NOTE`、`N 項未評估（…未評估不等於安全）`、`DANGER_POINTER` | **仍外露** |

### 5.3 Mutation（24 項，逐一實跑；全部轉紅；腳本＝逐項改 src → 跑 6 個測試檔 `-x` → 還原，並驗證檔案 sha 還原）

| 突變 | 首個紅燈（`-x`） |
|---|---|
| M1 小倍數格顯示最新值 | `test_p4_2_market_charts.py::TestC42C43::test_c4_2_five_cells_in_fixed_order_even_when_series_are_missing` |
| M2 少一系列 | 同上 |
| M3 圖 B 加切換列 | `TestZone::test_chart_zone_contains_no_widgets_and_no_l2_expanders` |
| M4 拿掉 MA 線 | `TestC41::test_c4_1_primary_is_the_native_line_chart_with_ma_lines_legend_and_y_axis` |
| M5 隱藏 y 軸（改 vega_lite_chart axis=None） | 同上 |
| M6 `⬜ 尚未定義` 改「⬜ 中性」 | `TestC45::test_c4_5_not_defined_is_shown_outside_the_fold_…[cold]` |
| M7 刪 `CHART_C_SAY` | `TestC8a::test_c8_a_say_is_verbatim_in_why_and_basis_verbatim_in_source` |
| M8 圖 D「未評估不等於安全」移入摺疊 | `TestChartD::test_c6_5_unevaluated_is_not_safe_stays_outside_the_fold_in_chart_d` |
| M9 圖區插入 L2 長內容 | `TestZone::test_chart_zone_order_and_nothing_between[cold]` |
| M10 四段缺一 | `TestC31::test_c3_1_each_chart_has_exactly_one_four_section_fold[cold]` |
| M11 `CHART_C_BASIS` 放「限制」 | `TestC8a::test_c8_a_say_is_verbatim_in_why_and_basis_verbatim_in_source` |
| M12 取消 9 字名顯示名對映 | `TestC31::…four_section_fold[loaded]`（元件拒收 9 字名） |
| M13 小倍數改 `st.html` | `TestC41::test_c4_1_exactly_one_native_chart_on_the_page_…` |
| M14 合併兩護欄 chip | `TestC41::test_c4_1_chart_a_header_chips_are_two_guards_…` |
| M15 Primary 冷啟動槽縮矮 | `TestC41::test_c4_1_primary_height_is_the_contract_cap_and_the_cold_slot_uses_the_same_height` |
| M16 「去哪補」指向不存在的展開區 | `TestC31::test_c3_1_where_points_at_the_real_l2_expander_of_each_chart` |
| M17 圖 B 拿掉 `⬜ 尚未定義` chip | `TestC42C43::test_c4_5_group_chips_say_not_defined_once_…` |
| M18 compact 不再擋 missing_verbatim 數字 | `TestC42C43::test_c4_3_cell_with_a_value_text_is_rejected_by_the_component` |
| M19 圖 C 外露客戶原句 | `TestC8a::test_c8_a_chart_c_outside_is_title_tag_and_one_line_only[cold]`（**初版綠燈 ⇒ 守衛有洞，已補強後重跑轉紅**） |
| M20 圖 A「趨勢定義說明」從摺疊掉了 | `TestC80::test_c8_0_chart_a_source_caption_ma_gaps_and_stale_warning_are_in_the_fold` |
| M21 圖 C 外露一行被刪 | `TestC8a::test_c8_a_chart_c_outside_is_title_tag_and_one_line_only[cold]` |
| M22 圖 A 未載入也讀快取 | `TestC41::test_c4_1_primary_cold_and_unreadable_keep_a_slot_not_a_missing_chart` |
| M23 圖 C 擺到圖 D 前 | `TestZone::test_chart_zone_order_and_nothing_between[cold]` |
| M24 缺系列格被丟掉 | `TestC42C43::test_c4_2_five_cells_in_fixed_order_even_when_series_are_missing` |

### 5.4 量測（harness 夾具、Streamlit 1.59.2；floor 1.56.0 另量一份；y＝頁面絕對座標；腳本 `measure_p4_2.js`）

| 量 | 桌機 1440×900（loaded） | 手機 390×844（loaded） |
|---|---|---|
| 圖區順序／容器間距 | A→B→D→C；16／16／16px | 同 |
| Primary 頂端 y／是否在第一屏 | 760（可見約 140px，圖本體在其下）／是 | 1167／否（Q7 mobile exception，附條件：緊接 AI 行＝0px、不被 L2／L3 插隊） |
| Primary 圖高／y 軸刻度／圖例 | 220／14 個／5 項 | 220／14／5 項（**圖例單行，手機後 3 項被裁，P4-1 基底同**） |
| 小倍數 格數／欄數／單格最高／格內數字 | 5／3／85px／0 | 5／2／53px／0 |
| 圖 A／B／D／C 容器高 | 400／343／493／171 | 454／365／723／216 |
| 橫向捲動（頁面與 4 容器） | 0 | 0 |
| cold：圖 B／D 容器高 | 203／241（一行灰字＋摺疊入口） | 228／267 |

四態（loaded／cold／report／partial）× 兩 viewport 全量：圖區順序皆 A→B→D→C、容器間距皆 16px、橫向捲動皆 0、小倍數皆 5 格 0 數字（`_measure_p4_2.json`）。floor 1.56.0（獨立 venv）：順序與 1.59.2 一致、Primary y 座標差 ≤10px（report／partial 手機）、5 個 svg 皆畫出、圖高 220、刻度 14、圖例 5 項（`_measure_p4_2_floor156.json`）。
- ⚠️ 圖 D 手機容器 723px 仍偏高（表格兩欄，窄螢幕「方向」欄換行成 2～3 行；表格本身約 437px，線框 §3.3 提到的舊三欄版約 668px）：**量到、未再壓**（再壓＝改核准的表格形式，屬 P4-3 Gate 判斷／必要時送客戶）。
- 瀏覽器內 `title=` 屬性：圖區 1 個 `Click to view actions`＝Vega 內建動作選單，**非本頁承載資訊的 hover-only 出處**。

### 5.5 其他頁與 legacy 0 影響（實測）

`compare_other_pages.js`：現行分支 harness vs **P4-2 前基底（git worktree @`4c1546b5`）** harness，🎯 標的、💼 持股、`?legacy=1`（市場／標的）× 1440／390 共 8 組，主內容＋側欄可見文字與按鈕／expander 標題**逐字相同**（正規化 repo 路徑與時間後）。⚠️ 沿用 P4-1 已知限制：harness 下 `?legacy=1&p=market` 兩邊都顯示同一個既有例外 traceback（夾具限制，非本批引入）；👤 我的頁 harness 不支援，未比對。

### 5.6 品管驗收結果（v3 §04 第 2 段；含未驗揭露）

- **全量 Fast lane**（CI 等價 `python -m pytest -q`＝`-m "not slow"`，1.59.2；與 slow 平行跑）：**35802 passed、46 skipped、185 deselected、1 failed**（19 分 31 秒）。唯一失敗＝`tests/test_zz_test_portability.py::test_no_external_shell_tools`：**本批新測試檔自己違規**（`TestScope` 用 `subprocess` 呼叫外部 `git`，Windows 沒有）⇒ 已改為純 Python 的 import 範圍守衛；之後**未重跑整個 Fast lane**，改跑：該守衛＋市場頁 8 檔＋讀 `docs/vnext`／HANDOFF／PROJECT_STATE／BACKLOG 的 11 個測試檔（含 slow）**3994 passed、6 skipped、0 failed**——⚠️ 這不等於整包重跑，Fast 全綠為**推論**，以 PR CI 為準。
- **全量 slow lane**（CI 等價 `pytest -m slow`）：**183 passed、5 skipped、0 failed**（15 分 37 秒）。
- **鏈與守衛**：`test_p4_revert_chain`／`test_uim_revert_chain`／`test_nav1_revert_chain`／`test_xvext_revert_chain`／`test_c3_layering_guard`／`test_batch_z60`／`test_views_no_unverified_universal_claims`（REGISTRY：本批無新增全稱關鍵詞，免新增）皆綠。
- **floor 1.56.0（獨立 venv，`--system-site-packages`＋`pip install streamlit==1.56.0`）**：市場頁相關 8 檔（含 slow）AppTest 最終 **769 passed、0 failed**（中途一次 `test_page_mounts_clean` 紅＝去重後的測試斷言需改寫，已改為等強＋加嚴）；瀏覽器量測見 5.4。
- **未驗**：1.57～1.58；真資料態與真冷啟動（harness cold 仍由假 L3 提供位階「多頭」，`P1R-P4-HARNESS-COLD-NOT-TRUE`）；手機實機、Streamlit Cloud、Safari／Firefox；`?legacy=1` 在 harness 下的既有例外；圖 A 在真 `data_cache` 的實值（測試與量測皆為固定夾具）。
- **資料真實性**：本批 0 資料語意變更（第一段 (a)～(g)）；missing≠0≠neutral≠HOLD≠safe 由 C4-2／C4-5／C6-5／既有 N2 守衛。

### 5.7 停下來請總管判斷

**無（未碰 Risk Cap、趨勢正式定義、資料契約、missing 投資語意、DEC 衝突，亦未新造客戶可見文案）**。需留意（內部自決已處理，列此供 P4-3 Gate 一併呈現）：
1. 小倍數顯示名「那指 IXIC」「費半 SOX」取自**已核准線框**字樣，非新造。
2. 圖 D 手機高度 723px、Primary 手機在第一屏下方（Q7 例外）——屬 P4-3 Gate 判斷。
3. 圖例手機被裁＝P4-1 既有（登 `P1R-P4-PRIMARY-LEGEND-MOBILE`）。

### 5.8 成品操作指引

向下捲到「圖 A 台股趨勢」：上方三顆 chip 是護欄與資料日；圖本身可看指數與均線參考線；「▸ 為什麼／來源／限制／去哪補」展開看依據與補資料的去處。其後依序是國際趨勢（5 個小圖，只看形狀、不顯示數字；要看數值去下方「國際市場（原始資料…）」展開區）、主要風險、大盤合理區間（研究框架，未啟用）。
