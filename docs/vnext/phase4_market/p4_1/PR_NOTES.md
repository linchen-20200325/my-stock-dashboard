# Phase 4 P4-1（📊 市場頁第一屏）— PR 描述素材（`CLAUDE.md` §-1.5 第三條五段＋第四條三段）

- **日期**：2026-10-30｜**分支**：`ccr-c8ef17de-9tw7yt`（基底 main `7484c57b`）｜**本批狀態**：本地 commit，**未 push、未開 PR**
- **依據**：客戶 DEC-117（Q1=B／Q2=A′／Q3=A／Q5=B／Q6=A／Q7=A／Q8b／Q8c）；線框 `docs/vnext/PHASE4_MARKET_PAGE_WIREFRAME_2026-10-30.md` §10（逐條狀態＝§10.7）；Migration Plan §20 P4-1
- **中間批**：Visual Fidelity Gate **未判**（正式 Gate 在 P4-3）；Stage ⛔ 標 complete
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：本檔與全部實作、量測、mutation 皆為**實作組單組產出，未經第二組驗證**。「其他頁 0 影響」「全鏈綠」等全稱句只涵蓋下方列出的實測範圍。

---

## 一、邏輯審查（是否符合核准線框）

| 客戶裁示／驗收條件 | 實作 | 落點 |
|---|---|---|
| Q5=B 新順序（C1-1） | 頁首（H2＋副標＋更新時間｜加權指數資料日）＋右側主 CTA → 更新報告（若有，預設收合）→ 今日結論（逐字）→ 3 tile → ⚡ bar → AI／資料狀態 → 圖 A～D（未動） | `page_market.render_page_market` |
| Q1=B（C1-3～C1-5） | 桌機 `st.columns(3)`（位階｜水位｜風險）；手機 2＋1 由具名容器 `.st-key-p4m_core_tiles` 的窄螢幕 CSS 排（失效＝退化單欄堆疊，⛔ 藏內容）；「🚀 更新今日戰情」字樣不改，改在頁首（桌機與 H2 同列右側、手機 H2 下方） | `_market_blocks.render_core_tiles`／`render_update_cta`／`P4M_LAYOUT_CSS` |
| Q8b（C8-b） | radio＋「已套用的更新模式…」＋`PAGE_REFRESH_SCOPE_WHY`／`REFRESH_SPEED_HINT` 整句收進預設收合的「更新選項」；form key／radio widget key／已套用 key／模式對映／重抓函式／報告 key 全部沿用 `page_today` 的同一組 SSOT；只按 🚀 才重抓 | `_ui_kit.single_submit_form(options_note=)`（加性）＋`render_update_cta` |
| C1-9／U1 | 更新報告（`_render_report_guarded`→`today._render_refresh_report`，主體本來就是預設收合 expander，用既有字樣）緊接更新鈕下方 | 同上 |
| Q5／C1-2 | 結論句與標題逐字、組句 `try` 區塊與 P4 前 AST 相同；只改位置 | `page_market` |
| Q6（C6-1～C6-5） | 外露＝縮短行「燈色＋桶名＋燈名＋方向」（`risk_item_short_text`）；整句版、排列說明、UI-M 原指路句 → 風險 tile 唯一「🔍 查看依據」；退化／護欄句（未載入灰、算不出來紅、全部不足、部分不足、全綠「不代表安全」、另 N 桶不足）**外露逐字**；tile 不新增「未評估不等於安全」；圖 D 該句照舊外露 | `hero_risk_face_lines`／`hero_risk_fold_lines` |
| C6-4 | `status_line()` 原樣呼叫、以「｜」逐字拆兩半：更新時間在頁首、`指標危險度覆蓋：N／M 項有資料`（冷啟動＝`尚未載入`）在風險 tile | `page_market` |
| Q2=A′（C2） | `指標危險度：見下方「指標明細（16 項）」最上方`（24 字；三字面釘死）；風險 tile 與圖 D 各一；未新增 chip kind；UI-M 原句保留在風險 tile 摺疊 | `DANGER_POINTER`／`DANGER_POINTER_UIM` |
| Q3=A／U6（C3-2） | tile 與 ⚡ 各**恰一個**「🔍 查看依據」；位階原卡標題「市場位階（總經契約）」、「生效分支」、原 hover-only「位階的出處」（`REGIME_SCOPE_NOTE`）全部寫進位階 tile 六欄（可見文字），原卡整張畫在同一摺疊 | `basis_regime` |
| Q8c（C8-c） | ⚡＝一行 bar：字取自既有「今日關鍵」卡（live＝label＋value；其餘＝卡上 `now`），有衝突提示時加計數，沒有可列來源同一行寫 `ALERTS_NO_SOURCE`；完整清單（原卡整張、衝突提示原文、數字說明）在同一「🔍 查看依據」內、六欄之前 | `alerts_bar_line`／`render_alerts_block`／`render_basis(lead=)` |
| N1～N3 | 水位主值槽仍是 `**⬜ 尚未核准／無法判定**`＋Q2-2 句逐字；`WATER_WHY` 與原有出手區間只在摺疊；位階 tile 外露字＝結論句同一支 `regime_clause`（⛔ 映射偏多／中性／偏空）；真錯誤紅、未載入灰 | `render_core_tiles` |
| N4 | P4 還原鏈頭節（基底 `7484c57b`，3 組 pair，difflib 最小唯一上下文，產生時驗「套用後逐字等於基底／新寫法現行恰 1 次、套用後 0 次」），接在 `uim_revert_for` 開頭；全部 30＋條鏈實跑綠 | `tests/test_p4_revert_chain.py`、`tests/test_uim_revert_chain.py`（只動函式本體，舊表／舊 sha 未動） |

**零資料語意證明 (a)～(g)**（FACT：`git diff 7484c57b --stat`）：(a) 新資料源 0；(b) schema 0；(c) 公式／門檻／TTL 0（`src/services|compute|data`、`shared/` 0 diff）；(d) Risk Cap 數字顯示 0（水位 tile 外露 0 個 %，`test_n1`）；(e) 趨勢定義 0（圖區未動，`⬜ 尚未定義` 照舊）；(f) Digest／Brain import 0（`test_layering_no_data_layer_and_no_digest_import`）；(g) `page_today.py`、`app.py`、`requirements.txt`、`compact.py`、`markup.py`（page_css）0 diff ⇒ z60 指紋、page_css sha 不變。

**清理項目（v3 §04 強制欄位，逐檔）**：`src/ui/views/_market_blocks.py::render_hero` —— 被 `render_core_tiles`／`render_update_cta`／`render_ai_status_line` 取代後 0 caller ⇒ 本批刪除。其餘無刪檔。

## 二、邊界測試（場景＝實跑）

| 場景 | 結果 |
|---|---|
| 冷啟動（無 session） | 第一屏 0 紅；風險 tile `⬜ 尚未載入，請按更新`（灰）；覆蓋率 `尚未載入`（⛔ 0／16）；⚡ bar 灰＋`⬜ 目前沒有可列的警示來源` |
| 已載入（夾具） | 順序正確；縮短行 ≤3、與摺疊整句與圖 D 三方逐項一致 |
| 更新報告（乾淨）／（有失敗） | 乾淨：CTA→結論之間只有預設收合的報告標題列；有失敗：報告的真錯誤 `st.error` 依 2026-09-24 客戶裁示留在收合區外（見第五段停點 2） |
| 五桶算不出來／位階契約讀不出來／結論句組不出來／圖 A 讀取失敗 | 四者皆紅、外露、原字串逐字 |
| 全綠／全部不足／部分不足／有項目＋不足 | 各分支句外露逐字（含「不代表安全」） |
| ⚡：live 有警示／live 無異常且無來源／degraded／未載入／門檻未掃完／failed／有衝突提示 | bar 字取自卡；failed 紅、未載入灰；無來源明寫；衝突計數＋原文在摺疊 |
| 選 radio 不按鈕 → 按鈕 | 不重抓 → 以所選模式重抓一次、報告落 session、rerun 後報告出現在更新鈕下方 |

## 三、效能評估

- 每輪 script run 不新增任何 I/O 或計算：tile／bar 只重排既有物件；`regime_clause` 多呼叫一次（純函式，O(1)）；`status_line` 仍只算一次。
- 多一個 `<style>`（約 1.3KB，只含 `@media (max-width:640px)` 排版規則）；不動 `page_css()`。
- 全頁高（夾具）：桌機 5575 → **5005**、手機 7966 → **6726**（loaded；冷啟動 3060→2409、4404→3220）——圖區未動，主要差在 Hero／⚡ 收合。

## 四、Debug 與修正（本批內部發現並已修）

1. **bare mode 的 `st.form` 會把 form 狀態漏到同一 process 的後續 AppTest**（「Forms cannot be nested」）：`test_verdict_cards_identical_to_today` 在 bare mode 直接呼叫兩頁；修法＝比照它對今天頁 `_render_update_form` 的處置，把市場頁新 CTA 一併換成 no-op（測試面；production 不受影響）。
2. **Streamlit 1.59.2 的有框容器沒有 `stVerticalBlockBorderWrapper`**：改用具名 key 前綴（`.st-key-p4m_box_*`）縮內距；選擇器失效＝退回預設內距，不影響內容。
3. **harness 不重載 `src/`**：Streamlit 只監看主程式目錄；量測前一律重啟 harness（已寫進量測流程）。
4. `uim_revert_for` 錨點在 P4 改動後漂移 ⇒ 依計畫在鏈頭接 P4 節（只動函式本體）；實跑 uim／nav1／xvext 與其餘鏈全綠。

## 五、最終（交付）

### 5.1 變更檔

| 檔 | 變更 |
|---|---|
| `src/ui/views/_ui_kit.py` | `single_submit_form` 加性參數 `options_note`（None 時逐呼叫不變；Phase 2 golden 照綠） |
| `src/ui/views/_market_blocks.py` | 第一屏區塊（見第一段）；刪 `render_hero` |
| `src/ui/views/page_market.py` | 區塊順序、頁首 CTA、狀態列拆兩處、逐項資料日句下沉 |
| `tests/test_p4_1_market_first_screen.py` | 新增 ~~49~~ 72 項（線框 §10 P4-1 條目；QA 修正輪＋23） |
| `tests/test_market_blocks.py`／`tests/test_uim_market_page.py`／`tests/test_page_market.py` | 改寫為等強或加嚴（皆附 📌 有意識的修改註） |
| `tests/test_p4_revert_chain.py`（新）／`tests/test_uim_revert_chain.py` | P4 還原鏈頭節 |
| `docs/vnext/phase4_market/p4_1/` | 量測腳本、JSON、第一屏截圖 8 張（皆 <300KB）、本檔 |
| 線框 §10.7、`docs/HANDOFF.md`、`docs/PROJECT_STATE.md`、`docs/BACKLOG.md` | 狀態同步（append-only） |

### 5.2 Mutation（17 項，逐一實跑；全部轉紅）

M1 結論移回 tile 後（C1-1）／M2 退化句刪「不代表安全」（C6-3）／M3 指路句拿掉「最上方」（C2）／M4 CTA 與結論之間插外露內容（C1-9）／M5 更新報告移到 AI 行與圖區之間（C1-7／C1-9）／M6 位階 tile 第二摺疊入口（C3-2）／M7 水位主值改 0%（N1）／M8 ⚡ bar 拿掉「沒有來源」（C8-c）／M9 外露改回整句（C6-1）／M10 摺疊不放整句（C6-2）／M11 更新說明不進「更新選項」（C8-b）／M12 加回第 4 欄（C1-3）／M13 位階六欄丟掉 hover 出處（C3-2／N3）／M14 覆蓋率不外露（C6-4）／M15 位階 tile 映射成偏多（N3）／M16 送出時不照所選模式（C1-4）／M17 radio 移出摺疊（C8-b）。每項的首個紅燈測試名如下（腳本：逐項改 src → 跑 4 個測試檔 `-x` → 還原；實跑後 `git status` 確認 src 已還原）。

| 突變 | 轉紅？ | 首個紅燈（`-x`） |
|---|---|---|
| M1 結論移回 tile 之後（C1-1） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestC1Order::test_c1_1_block_order_is_dec117_q5[cold]` |
| M2 退化句刪「不代表安全」（C6-3） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestC6RiskTile::test_c6_3_degenerate_and_guard_sentences_are_exposed_verbatim[all_green]` |
| M3 指路句拿掉「最上方」（C2） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestC2Pointer::test_c2_three_literal_elements_and_length` |
| M4 CTA 與結論之間插外露內容（C1-9） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestC1Order::test_c1_9_between_cta_and_conclusion_only_collapsed_report_expander[loaded]` |
| M5 更新報告移到 AI 行與圖區之間（C1-7／C1-9） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestC1Order::test_c1_9_between_cta_and_conclusion_only_collapsed_report_expander[loaded]` |
| M6 位階 tile 第二個摺疊入口（C3-2） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestC3Basis::test_c3_2_each_tile_and_alerts_has_exactly_one_basis_expander` |
| M7 水位主值 missing→0%（N1） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestInvariants::test_n1_water_tile_has_no_number_and_verbatim_guards[cold]` |
| M8 ⚡ bar 拿掉「沒有來源」（C8-c） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestC8::test_c8_c_bar_line_states` |
| M9 外露改回整句（C6-1） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestC6RiskTile::test_c6_1_short_line_is_lamp_color_bucket_lamp_direction` |
| M10 摺疊不放整句（C6-2） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestC6RiskTile::test_c6_2_full_sentences_are_in_the_risk_basis_on_the_page` |
| M11 更新說明不進「更新選項」（C8-b） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestC8::test_c8_b_radio_and_long_note_are_inside_update_options_collapsed` |
| M12 加回第 4 欄（C1-3） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestC1Structure::test_c1_3_exactly_three_core_tiles_and_update_is_not_a_tile` |
| M13 位階六欄丟掉 hover 出處（C3-2／N3） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestC3Basis::test_c3_2_hover_only_regime_provenance_is_visible_text_in_the_basis` |
| M14 覆蓋率不外露（C6-4） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestC6RiskTile::test_c6_4_coverage_is_exposed_in_the_risk_tile_and_split_is_lossless` |
| M15 位階 tile 映射成偏多（N3） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestInvariants::test_n3_regime_tile_face_equals_conclusion_clause[cold]` |
| M16 送出時不照使用者選的模式（C1-4） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestC1Structure::test_c1_4_only_submit_triggers_refresh_radio_does_not` |
| M17 radio 移出摺疊（C8-b） | ✅ 紅 | `tests/test_p4_1_market_first_screen.py::TestC1Order::test_c1_1_block_order_is_dec117_q5[cold]` |


### 5.3 量測（harness 夾具、Streamlit 1.59.2；floor 1.56.0 另量一份＝`_measure_p4_1_floor156.json`，數字差 ≤32px；y＝頁面絕對座標，H2 y135；手機可用高 791＝844−底部導覽 53）

| 量 | 桌機 1440 loaded／cold／report | 手機 390 loaded／cold／report／partial |
|---|---|---|
| 結論句頂端（相對 H2） | 340（+205）／340（+205）／418（+283） | 427（+292）／404（+269）／514（+379）／**896（+761，第一屏外）** |
| 3 tile 列 y／高 | 407／334；382／251；486／334 | 位階｜水位 537／204、風險 749／250；冷 489／204、701／183 |
| ⚡ bar 頂端（外框底緣） | 773（871）／665（759）／852（949） | **1016（1098）／900（1002）／1102（1185）／1485（1567）** ⇒ 皆第一屏外 |
| 頁首動作列（form）實高 | 128 | 106 |
| 第一屏 `title=` 承載資訊 | 0 | 0 |

### 5.4 其他頁與 legacy 0 影響（實測）

`compare_other_pages.js`：現行分支 harness vs 開工前基底（`git worktree` @`7484c57b`）harness，🎯 標的、💼 持股、`?legacy=1`（市場／標的）× 1440／390 共 8 組，主內容＋側欄可見文字與按鈕／expander 標題**逐字相同**（正規化 repo 路徑與「現在時刻」後）。⚠️ harness 下 `?legacy=1&p=market` 兩邊都顯示同一個既有例外 traceback（夾具限制，非本批引入；未追查）。👤 我的頁 harness 不支援，未比對（由 `tests/test_p0*`／全量測試涵蓋）。

### 5.5 停下來請總管判斷（實作組未自行改核准結構）

1. **C1-10 ❌（手機第一屏放不下 ⚡ bar）**：已做完不改結構的壓縮（L1 容器內間距 16→8、框內距、expander 標題列內距、結論小標字級；說明句下沉），手機 ⚡ bar 頂端仍在 y900（cold）～y1016（loaded），差 109～225px＋bar 本身高度。主要佔高：頁首（H2＋副標＋時間行 ≈ 160）、CTA form 106、結論 4～5 行 ≈ 140、位階｜水位列 204、風險 tile 183～250。
   **推薦方案（總管拍板；若屬版面異動則附推薦送客戶）**：
   - **R-A（推薦）手機專用：⚡ 一行 bar 移到 3 tile 之前**（結論 → ⚡ → tile），桌機順序不變。理由：bar 只有一行（~46px），移前後手機第一屏可同時含結論＋⚡＋位階｜水位列；風險 tile 被推到第一屏下緣。代價：桌手機順序不同（Q5 原文是單一順序、客戶 Q7 優先序「結論 > 核心狀態 > 是否需行動」與此相反）⇒ **屬改核准順序，須送客戶**。
   - R-B：手機風險 tile 預設只外露 1 行（最差桶）＋「另 K 項見圖 D」，其餘縮短行下沉。代價：Q6「≤3 行縮短行外露」在手機打折 ⇒ 須送客戶。
   - R-C：維持現狀，總管改判 U4（接受手機 ⚡ 在第一屏下方、與 Primary 同屬 Q7 例外）。代價：與 DEC-109 四④「是否需要行動」須在第一屏的客戶原文衝突 ⇒ 須送客戶。
2. **C1-9 與 2026-09-24 客戶裁示衝突**：更新報告有失敗時，`_render_refresh_report` 把真錯誤 `st.error` 留在收合區外（客戶 2026-09-24：真錯誤不得藏進收合區），因此會落在 CTA 與結論之間；partial 態手機結論句被推到 y896（第一屏外，違 C1-6）。實作組未改（`page_today.py` 禁改；且收進摺疊＝違反既有客戶裁示）。
   實作組看過的替代位置都會撞到另一條：收進摺疊＝違 2026-09-24 裁示與 §1（假平安）；移到結論之後、tile 之前＝在 L1 決策區中間插長內容；移到 AI 行與 Primary 之間＝違 C1-7。另一個方向是在市場頁自寫「一行紅字摘要＋完整清單照舊」，但真錯誤清單仍得外露在某處，且須另寫 page_today 那段的複本（禁改 `page_today.py`）。
   **推薦（R-D）**：真錯誤外露優先，C1-9 加註「報告有真錯誤時例外」（現況即此，`test_c1_9_true_errors_of_a_failed_report_stay_outside_the_fold` 已釘住）。這是在兩條規則之間排優先序，總管判斷是否屬內部自決或須送客戶。

### 5.6 品管驗收結果（v3 §04 第 2 段；含未驗揭露）

- **全量快測**（CI Fast 等價 `pytest`＝`-m "not slow"`，1.59.2）：**35709 passed、46 skipped、185 deselected、0 failed**（16 分 47 秒）。
- **全量 slow lane**（CI Slow 等價 `pytest -m slow`）：**183 passed、5 skipped、0 failed**（16 分 26 秒）。
- 以上兩次實跑時工作樹已含 P4 還原鏈頭節（本 PR 最後一個 commit）。
- **floor 1.56.0（獨立 venv，`--system-site-packages`＋`pip install streamlit==1.56.0`）**：AppTest `test_p4_1_market_first_screen`＋`test_uim_market_page`＋`test_market_blocks`＋`test_page_market`（含 slow）＋Phase 2 golden **293 passed**；瀏覽器量測（`_measure_p4_1_floor156.json`）四態兩 viewport 區塊順序與 1.59.2 相同，手機 2＋1 規則生效（位階｜水位各寬 175），form 實高同為 128／106，手機 ⚡ bar 同樣在第一屏外（loaded y1016、cold y900）。
- **未驗**：1.57～1.58；真資料態與真冷啟動（harness cold 仍由假 L3 提供位階「多頭」）；手機實機、Streamlit Cloud、Safari／Firefox；`?legacy=1` 在 harness 下的既有例外原因。
- **資料真實性**：本批 0 資料語意變更（第一段 (a)～(g)）；missing≠0≠neutral≠HOLD≠safe 由 N1／N2／C6-3／C6-4 守衛。

### 5.7 成品操作指引

- 頁首右側（手機在標題下）按「🚀 更新今日戰情」更新；要切「強制重抓」先展開上方「更新選項」。
- 第一屏讀法：今日結論 → 市場位階｜建議總持股水位｜今日主要風險 → ⚡ 需要處理（一行；展開「🔍 查看依據」看完整清單）。每張卡只有一個「🔍 查看依據」，原本只在滑鼠停留時看得到的出處說明也在裡面。


---

## 六、QA 修正輪（2026-10-30；兩組獨立 QA 無 BLOCKER；append-only）

> 結構與區塊順序**未動**：C1-10（手機第一屏 ⚡ bar）與 partial 態結論被擠出手機第一屏，總管已送客戶裁示。逐條見線框 §10.7.1。

### 6.1 修正
1. **C6-3 真錯誤外露（MAJOR）**：位階 tile failed＝紅框內「外露值＋原因」；讀契約失敗的原因＝X1 既有句「市場位階契約讀不出來：`…`」逐字（`page_market` 傳入），其他 failed＝卡上既有 `why`；⚡ failed＝紅 bar 帶卡上既有 `why`（「L2 `compute.macro.daily_key_alerts`（今日關鍵）拋出例外：…」）逐字；結論紅字確認在外露層（緊接結論標題）。⚠️ ⚡ 的 `why` 是**卡片資料**原句，v2 卡面渲染時另加的「為什麼：」前綴屬卡面版型，bar 上未加。
2. **目視 bug**：L1 內 expander 內容可任意處換行（`overflow-wrap:anywhere`、`word-break:break-word`、`min-width:0`；@media 外）。實量：修前手機位階摺疊右溢 155px、`scrollWidth 318 > 151`；修後五個摺疊×2 viewport×cold／loaded 右溢 0。
3. **CSS 白名單守衛**、4. **degraded**（位階粗體＋徽章；⚡ 帶「N 紅 · M 黃」，格式同既有 live 態 value）、5. **狀態列拆分 fail loud**、6. **語意守衛**（位階徽章、結論紅字外露），見線框 §10.7.1。
7. `page_market.py` 有改 ⇒ 以同一基底 `7484c57b` 重產還原鏈 pair（基底 sha 不變）。

### 6.2 下沉清單（外露 → 摺疊；全部只下沉、未刪；QA 要求明列）
| 原外露內容 | 新位置 |
|---|---|
| 「正式 Risk Cap 尚未核准，此卡不顯示任何百分比。」（`WATER_WHY`） | 水位 tile「🔍 查看依據」內（外露仍有 `⬜ 尚未核准／無法判定`＋Q2-2 句逐字） |
| 原有出手區間卡（含 risk_cap.v2；UI-M 起就在摺疊） | 同上（未變） |
| 風險項整句（燈說明、「｜方向：」、「｜同級並列 N 項」）、`HERO_RISK_NO_RANKING_NOTE`、UI-M 原指路句 `DANGER_POINTER_UIM` | 風險 tile「🔍 查看依據」 |
| 位階原卡（標題「市場位階（總經契約）」、生效分支、hover-only「位階的出處」） | 位階 tile「🔍 查看依據」六欄＋原卡整張（工程字樣維持原文，已登 BACKLOG `P1R-P4-REGIME-FOLD-ENG-WORDS`） |
| 更新模式 radio、已套用模式句、`PAGE_REFRESH_SCOPE_WHY`＋`REFRESH_SPEED_HINT` | 「更新選項」 |
| 「今日關鍵」原卡整張、衝突提示原文、`ALERTS_CONFLICTS_NUMBER_NOTE` | ⚡「🔍 查看依據」（bar 外露計數與「沒有來源」） |
| 「逐項資料日：尚未提供…」＋資料健康指路 | 「資料來源與完整度」展開區最上方 |

### 6.3 新增 mutation（全部轉紅）
| 突變 | 首個紅燈 |
|---|---|
| M18 位階 tile 失敗不帶原因 | `TestInvariants::test_n3_regime_contract_failure_is_red` |
| M19 ⚡ 失敗 bar 不帶原因 | `TestC8::test_c8_c_bar_line_states` |
| M20 ⚡ degraded 不帶紅黃計數 | `TestC8::test_c8_c_bar_line_states` |
| M21 拿掉摺疊換行規則 | `TestC1Structure::test_c1_5_fold_contents_wrap_instead_of_overflowing` |
| M22 狀態列拆分不 fail loud | `TestC6RiskTile::test_c6_4_status_line_with_extra_separator_fails_loud`（排除還原鏈 AST 測試後） |
| M23 位階 tile 不帶徽章 | `TestInvariants::test_n3_live_regime_tile_shows_the_card_badge` |
| M24 結論紅字收進 expander | `TestC1Structure::test_c1_2_conclusion_failure_is_red_and_named`（排除還原鏈 AST 測試後） |
| M25 位階 tile 外露錯誤句不傳入 | `TestInvariants::test_n3_regime_contract_failure_is_red`（排除還原鏈 AST 測試後） |
| CSS 源碼突變 ×6：font-size:0／position:absolute／clip／transform:scale(0)／color:transparent／left:-9999px | `test_c1_5_layout_css_declarations_are_whitelisted` |

### 6.4 本輪測試
- 相關子集（市場頁 4 檔＋鏈守衛＋Phase 2 golden＋views 守衛，含 slow）：370 passed、4 skipped。
- 全量 Fast／slow：**Fast（`pytest`）35732 passed、46 skipped、185 deselected、0 failed**（16 分 18 秒）；**slow（`pytest -m slow`）183 passed、5 skipped、0 failed**（16 分 05 秒）。
- 第一屏量測未重跑：本輪 CSS 只加 expander 內換行規則（收合時不影響版面），其餘修改只在 failed／degraded 態加字；第一屏數字沿用 §5.3（夾具各態皆非 failed）。


---

## 七、DEC-118 後（2026-10-30；append-only）

- 落盤：DEC-118（客戶原文 fence）、`PROJECT_RULES.md` 第 2／3／21.2 節、Gate §8 手機 ⚡ mobile exception、線框 §10 C1-9／C1-10 改寫。
- 已做：C1-10 新條件守衛（⚡ 緊接 3 tile、中間無他物）＋mutation M26／M27 必紅。
- 手機 390×844 實量（1.59.2 夾具）：結論＋位階｜水位列——loaded ✅、cold ✅、report 🟡（列底部 🔍 標題列被截 37px）、partial ❌（待 D1）。
- **D1 實作停點（實作組未動結構、未改 `page_today.py`）**：① `page_today._render_refresh_report` 一次畫完「真錯誤 `st.error`」與「預設收合的報告 expander」，沒有可單獨呼叫的 API；要把真錯誤放到今日結論下方、報告標題留在 CTA 下方，只能 (X) 改 `page_today.py`（拆成兩支、今天頁輸出逐字不變，但受多條還原鏈守衛且 DEC-081 Q1=C「驗收前不改」）、(Y) 在 `page_market` 複寫約 90 行報告渲染（第二套、需逐字 parity 測試防漂移）、或 (Z) 只在「報告有真錯誤」時把整份既有報告（真錯誤＋收合標題）改畫在今日結論正下方（零複寫，但 X3／X10「頁首更新鈕下方」指路句在該態不準）；② 即使 D1 落地，partial 態真錯誤區塊在手機約 330px 高，放在結論下方會把位階｜水位列推出第一屏（結論底 ≈632＋330 ≈ 960 > 可用 791），與 DEC-118 理由 1「第一屏優先維持今日結論＋核心狀態」互相牽制。
- 本輪測試：市場頁 4 檔＋鏈守衛（p4／uim／nav1／xvext）＋z60＋floor 相容：420 passed；floor 1.56.0 venv 市場頁 4 檔 AppTest：249 passed。Fast／slow 全量待 D1 定案後重跑（本輪未改 `src/`）。
