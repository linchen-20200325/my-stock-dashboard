# Presentation Migration Plan（Phase 2→7 施工計畫＋舊 presentation contract 盤點）

- **狀態**：正式／現行（施工計畫）
- **日期**：2026-10-29　**基準**：PR base＝main `978ecedc`（`src/`、`tests/` 與 main 相同）
- **決策來源**：Phase 1～7 劃分與「Decision Digest contract 未凍結前不得寫新 LLM prompt／glue」「舊 test 改驗資訊沒有遺失／可取得／可展開／provenance 可追溯／Missing 語意未改」「Model × Effort：規格凍結後 common components／chips／expander／layout／chart arrangement／routing／mechanical migration 推薦切 Sonnet 5.5＋Medium」＝**客戶 2026-10-29（DEC-109 七、三十一、三十二，逐字）**；具體步驟、DoD、還原鏈處理、Model／Effort 建議（R19）＝**AI 總管內部決定（DEC-110）**。
- **上位**：`CLAUDE.md` > `PROCESS.md`（§3 寫入端一次一檔序列化仍有效）> `PROJECT_RULES.md`（第 7、8、18、23、24 節）＋`docs/governance/*` > 最新有效 DEC > 本檔。
- **依據**：`docs/vnext/PRESENTATION_CONTRACT_vNext_2026-10-29.md`（契約）、`docs/governance/UI_VISUAL_FIDELITY_GATE.md`（Gate）、`docs/vnext/DECISION_DIGEST_CONTRACT_vNext_2026-10-29.md`、`docs/vnext/ONE_AI_BRAIN_BOUNDARY_vNext_2026-10-29.md`；Inv-1 helper 盤點、Inv-2 tests／還原鏈盤點（皆單組）；PR #970 §E 施工順序（吸收）。
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：caller 數、測試檔數、還原鏈覆蓋均為 grep／regex 粗估（Inv-1／Inv-2，單組），**每個 phase 開工前須以當時 main 重新實測**，⛔ 把本檔數字當前提。
- **Scope Guard**：只遷移呈現責任；⛔ 新資料源、新投資規則、Risk Cap 新公式、EPS×PE production rule、台股／國際趨勢正式定義、大規模 IA 重構、無關 legacy cleanup。發現 → `docs/BACKLOG.md`（P2，不插隊）。

---

## §1 總覽（客戶 DEC-109 三十一 Phase 1～7；PR #970 §E 順序吸收）

| Phase | 內容 | 性質 | 建議 Model／Effort（R19；開工時依 DEC-084／DEC-106 比對現況，符合即靜默繼續） | 前置 | Gate（UI phase 寫 UI code 前一律先出文字線框） |
|---|---|---|---|---|---|
| **1** SSOT Reset／Contract Freeze | 本 PR：契約、Gate、Digest、Brain、supersede、durable memory、migration plan、visual gap audit、工具入庫 | docs／governance＋非 production 工具 | Opus 5.5＋High（客戶 DEC-109 三十二） | DEC-109 | N/A（docs-only） |
| **2** Helper／Test Contract Migration | 舊 helper 加可選參數（預設 byte-identical）、`Note` contract 不動、`V2_SHORT_ROWS` 保留、tests 改寫為「資訊守恆」等強斷言；T23（欄數）**暫不動**，待 `CV1-DR-12` 裁示 | 共用層＋tests；**畫面零變更** | **Opus 5.5＋High**（R19：契約遷移仍屬判斷型工作） | Phase 1 合併 | 零變更證明（批前／批後截圖或量測值相同） |
| **3** Shared Visual Components | metadata／status chips、chart header、evidence expander、Missing placeholder、compact KPI card、sparkline、small multiples、Top-N 切片、segmented switcher；tokens 收斂；站殼間距子項 | 純加性新模組＋CSS；新元件未掛頁前畫面零變更（站殼子項例外） | 起判 Opus 5.5＋High；進入明確機械式 UI implementation 時切 Sonnet 5.5＋Medium（客戶 DEC-109 三十二；R19） | Phase 2 | 站殼子項動畫面前先出文字線框；零變更證明；站殼子項全 Gate |
| **4** 📊 市場 reference implementation | 依契約 §12.1 回修；作為 Visual Fidelity reference | 單頁 UI | 線框與規格判斷用 Opus 5.5＋High；線框拍板後機械式實作視情況切 Sonnet 5.5＋Medium | Phase 3 | **先出文字線框（含 W2、W3、W9、版面差異、總管推薦）→ 客戶拍板 → 寫 UI code**；全 Gate |
| **5** 🎯 標的 | 依契約 §12.2；線框先列待客戶拍板點 W4～W6（含選股條件預設展開 vs 收合） | 單頁 UI | 同 Phase 4 | Phase 4 | **先出文字線框（W3～W6、版面差異、總管推薦）→ 客戶拍板 → 寫 UI code**；全 Gate |
| **6** 💼 持股 | 依契約 §12.3（骨架 AI → ⚡ → 🌱／📈／⬜） | 單頁 UI（最大；可拆 2 PR） | 同 Phase 4，開工重判（`page_hold` 10 條還原鏈、骨架重排可能需 High） | Phase 5 | **先出文字線框（W3、W7、版面差異、總管推薦）→ 客戶拍板 → 寫 UI code**；全 Gate |
| **7** One AI Brain／Decision Digest／AI 投資總結 | Digest v2 A1～A8、headless 組裝點、Brain、R12 輸出格式、R13 入口 | L0／L3＋UI 入口 | **Opus 5.5＋High**（R19） | Phase 6；Digest 契約已凍結（Phase 1）；v2 schema（A1～A7）定案前不寫新 prompt／glue | **先出 AI 投資總結文字線框（含 W8、版面差異、總管推薦）→ 客戶拍板 → 寫 UI code**；全 Gate＋Brain 驗收 8 條 |

- **線框先行（`CLAUDE.md` §-1.5.D v3 §03-2 ①）**：Phase 3～7 每個會改畫面的 UI phase，**寫 UI code 前**都須先出文字線框草稿（含該頁 W 點、與現況的版面差異、總管推薦方案）送客戶拍板；拍板前只能做不改畫面的工作。
- 每個 phase：獨立 PR、可回滾；實作與稽核分離（≥2 組不同角度 QA，`CLAUDE.md` §-2 規則 4）；交付報告三段式落 PR 描述、對客戶 ≤5 行（DEC-060）。
- **UI 視覺實作凍結**（DEC-108 第 3 點，DEC-109 改寫解除條件）：Phase 1 契約合併後依 Phase 2→7 推進，**每個 UI phase 過 Visual Fidelity Gate** 才算該頁解凍完成。UI-H 其餘與 UI-ME 的正式視覺實作併入 Phase 6／後續，不另開。
- 「具體 dependency 可以調整」（客戶原文）：調整屬內部拍板，於 HANDOFF 與 BACKLOG 同步；⛔ 跳過 Phase 7 前置直接寫 prompt。

## §2 舊 presentation contract 盤點（程式碼面，Inv-1 #1～#35）

> 分類標記（為避免與客戶 DEC-109 二十八的清理 A／B／C／D 混淆，本表用 **P-**）：**P-A 淘汰**（只為舊卡面服務、資訊另有去處）／**P-B 資訊保留但可收合**／**P-C 仍有效**／**P-D 與新 Visual SSOT 衝突**（原文加註不刪，常伴隨守衛改寫）。Inv-2 自定分類已換算（Inv-2 A→P-A 或 P-D、B→P-B、C→P-C 機制改寫、D→P-C）；換算為單組判斷。

| ID | 位置（檔::符號） | 強制的呈現 | 類 | 處置 | 施工 Phase |
|---|---|---|---|---|---|
| H1 | `src/ui/tabs/tab_today.py::Note(now,why,where)` | 非 live 卡必附三段非空 prose | P-C | 資料契約不變 | — |
| H2 | `tab_today.Card` | degraded 值只能進 facts | P-C | compact KPI 從 facts 取值 | — |
| H3 | `tab_today.MAX_COLS=3`／`_ui_kit.grid`；`render_hero` `st.columns(4)` | ≤3 欄 | P-C／P-D | **維持現狀**；v3 §00「固定 3 欄」vs DEC-091 §四「3～4」／Hero 4 欄的牴觸待客戶裁示（`CV1-DR-12`，Phase 4 線框 W9）；手機版排法同待拍板 | 待 `CV1-DR-12` |
| H4 | `_ui_kit.render_note()` | 三段常駐外露 | P-B | 收進摺疊 | 4～6 |
| H5 | `_ui_kit.render_card()` | facts＋Note 外露 | P-B | facts 與 Note 下沉；🔴 碰撞守衛保留 | 2（參數）／4～6 |
| H6 | `_ui_kit.render_card_isolated()` | 失敗紅卡含 `repr(e)` | P-C | 隔離不弱化；紅卡卡面 1 句、`repr(e)` 進摺疊 | 4～6 |
| H7 | `_ui_kit.section_header`；`page_hold._render_warroom_leaf`「線框：…」「常駐揭露 · 非摺疊…」 | caption 工程字 | P-C／P-A | 工程字樣移除或改白話入 L3 | 6 |
| H8 | `_ui_kit.single_submit_form()` | radio 永遠外露 | P-B | 加 `options_label=None` 可選收合（預設 byte-identical）；1.56 form 內 expander 未驗 | 2 |
| H9 | `_ui_kit._chip()` | pill HTML | P-C | 升 public status chip | 3 |
| H10 | `_ui_kit.assert_signal_text_clean`／`banned_signal_glyphs` | 訊號頻道禁狀態 glyph | P-C | 保留；metadata chip 獨立通道 | 3 |
| H11 | `shared/ui_state.classify_ui_state`／`UI_STATE_META`／`NO_VALUE_STATES`／`EMPTY_STATE_BY_REASON` | 十態 | P-C | 不動 | — |
| H12 | `page_today::v2_level_line`＋`V2_NOW/WHY/GUIDE_FACT_KEY` | 卡面三列（客戶 2026-09-24） | P-A | 三列移入摺疊（位置被 DEC-109 取代） | 4（新頁組裝）／legacy 不動 |
| H13 | `page_today::_v2_why_phrase`＋`V2_WHY_CLAUSE_SEPARATORS`＋`V2_WHY_MAX_CHARS(46)` | 截斷 why | P-A | 0 caller 後清理（逐檔列出） | 清理批 |
| H14 | `page_today::V2_EXIT_PHRASES`＋`_v2_exit_phrase`（未登記 KeyError→紅卡） | 去哪補短語 | P-B | 作摺疊「去哪補」段；KeyError 守衛保留 | 3～6 |
| H15 | `page_today::V2_HOVER_ONLY_FACTS`／`V2_HOVER_OPTIONAL_FACTS`（`REGIME_SCOPE_NOTE` 193 字） | 只在 hover | P-D | 移入摺疊（手機無 hover） | 4 |
| H16 | `page_today::V2_FOLD_CARD_PREFIX`＋`V2_FOLDED_FACT_KEYS` | 只 16 燈卡摺疊 | P-B | 泛化 | 3～6 |
| H17 | `page_today::v2_card_html`／`_render_one_v2`／`_render_one`（`V2_CARD_BLOCKS`） | 卡面＝三列＋facts＋hover | P-B | 在 `_market_blocks` 新增組裝器重用同一 Tile；⛔ 動 `page_today`（sha 守衛最重） | 4 |
| H18 | `page_find/page_hold/page_inspect/page_why::V2_SHORT_ROWS`＋`v2_short_rows()` | 每則 Note 三列上卡面 | P-A（外露三列）／P-B（表） | 表保留作卡面 1 句或摺疊段標籤；KeyError、K1 保留 | 2（測試）／5～6 |
| H19 | `page_hold/page_inspect::V2_FOLD_ONLY_FACT_KEYS` | 部分 facts 只進摺疊 | P-C | 泛化 | 5～6 |
| H20 | `_v2_pick_excerpt/_v2_pick_short`、`page_hold::_v2_face_value`／`V2_FACE_TOKEN_MAX=12`／`V2_HOLD_CARD_CSS` | 長字變通 | P-B→P-A | 0 caller 後清理 | 清理批 |
| H21 | `v2_plain`／`_V2_BLANK_LINE_RE`／`_inject_v2_css`（約 5 份近似複本） | 基礎設施 | P-C | 不在本遷移合併（`P1R-LEGACY-DUP`） | — |
| H22 | `src/ui_v2/markup.card_html()` | 無 chip 列／摘要句／spark 槽 | P-C／P-B | 加可選 `chips=()`、`summary=None`、`fold_label=FOLD_SUMMARY_TEXT`、`spark=None`，預設 byte-identical | 2 |
| H23 | `markup.FACT_VALUE_MAX_CHARS=46`＋`FACT_VALUE_ELLIPSIS`（全文在 `title=`）；`PAL.FACE_MAX_CHARS=46` | 截斷＋全文只在 hover | P-B／P-D | 截斷後全文另在摺疊可取得 | 2（測試）／4～6 |
| H24 | `markup.FOLD_SUMMARY_TEXT="▸ 詳細"`（客戶核可線框字樣） | 單一摺疊標籤 | P-C（字樣為客戶核可） | 加可選 `label` 參數（預設＝「▸ 詳細」不變）；各頁是否換字＝線框待客戶拍板（契約 §22 W3） | 2（參數）／4～6（待拍板） |
| H25 | `markup.grid_html`／`layer_html` | 0 caller | P-C | 不動 | — |
| H26 | `src/ui_v2/components`：`CARD_TIERS`、`CARD_BASE`(radius 2px)、`CARD_VALUE` 24px、`BADGES`（封閉 11）、`MAX_COLS=3` | 幾何與狀態徽章 | P-C（徽章）／P-D（幾何） | metadata chip 另族（R8）；幾何加性 token | 3 |
| H27 | `src/ui_v2/tokens`；`SERIES_DARK/LIGHT`（0 consumer） | 色彩 | P-C／P-D | R15 收斂；客戶裁示色值另議 | 3 |
| H28 | `src/ui_v2/blocks.PAGES` | 依 block 查 tier | P-C | 市場／標的 compact 卡加性登記 | 3～5 |
| H29 | `src/ui_v2/render.py`＋`app_today.py` | 原型 | 範圍外 | 不動 | — |
| H30 | `_market_blocks.Basis`＋`render_basis` | 收合依據 | P-C | 標籤維持；換字待線框拍板（W3） | 4 |
| H31 | `_target_blocks.Basis`／`render_basis`（第二份） | 同目的 | P-D-minor | 合併為超集（舊名 alias） | 3 |
| H32 | `_market_blocks.render_chart_a/render_chart_b`（`st.line_chart` 預設高；B 每系列一張） | 大圖上主畫面 | P-A（大圖）；主圖仍外露 | compact 高度／switcher／small multiples（R2） | 4 |
| H33 | `_market_blocks.render_chart_d`／`render_hero`（`WATER_WHY` 長字、更新卡） | 表與長字 | P-B | chip 列；`HERO_RISK_MAX_ITEMS=3` 為 Top-N 先例 | 4 |
| H34 | `_target_blocks.render_zone_candidates`（`SCREEN_EXPANDER expanded=True`＋整張 `st.dataframe`）／`matrix_html` | 長表先出 | P-B | Top-N 先、全表收合；`TOP_N_OPTIONS`／`DEFAULT_TOP_N` 不動（R9）；**選股條件維持預設展開**，收合與否待 Phase 5 線框拍板（W4，R3 總管改判） | 5 |
| H35 | `page_hold`「② 兩套刻度」（設計上不摺疊） | 常駐揭露 | P-C（客戶核准線框；DEC-109 未點名） | **維持常駐非摺疊**；改 chip＋可展開與否待 Phase 6 線框拍板（W7） | 6（待拍板） |

## §3 Tests 盤點與等強替代（Inv-2 T1～T26）

> 原則（客戶原文）：測試驗證「三段文字一定要顯示在頁面」者，改驗：**資訊沒有遺失、正確資料可取得、詳細說明可展開、provenance 可追溯、Missing 語意未改**。誠實不變量照原強度保留，只把「在卡面」改成「在卡面 ∪ 摺疊 ∪ 既有 expander」；每條改寫在測試內寫理由。
> Phase 2 只改「可在現行畫面下等強成立」的斷言（改寫後新舊畫面都綠）；**依賴頁面新位置的斷言**在該頁 Phase（4～6）改。

| T | 檔::測試 | 舊斷言 | 守護的不變量 | 等強替代 | Phase |
|---|---|---|---|---|---|
| T1 | `test_p02_find_v2_cards::test_short_rows_are_first_and_come_from_the_table`；p03／p04／p05 `test_every_state_renders_through_the_v2_face` 相關段 | 卡面前 3 列＝三要素 | K1；每 Note 必登記 | 卡面＝徽章＋主值＋≤1 句（K1 逐格驗）；why／where 與全文入摺疊；保留 `test_short_phrase_table_covers_every_note_and_has_no_dead_rows`、`test_every_note_now_in_the_module_is_a_registered_constant` | 2（登記類）／5～6（位置） |
| T2 | p02 `test_existing_facts_are_all_still_on_the_card`；p03～p05 `test_existing_facts_all_stay_on_the_face_after_the_short_rows` | facts 全在卡面 | 不靜默丟 fact | 「卡面 ∪ 摺疊 ＝ 原 facts」（標籤逐字） | 2 |
| T3 | p03／p05 `test_face_rows_keep_the_qualifiers_of_their_full_text`（`_MUST_KEEP`）；p04 `test_qa_flagged_qualifiers_are_kept` | 限定詞在卡面 | missing≠0 | `_MUST_KEEP` 逐字在摺疊；反向：非 live 卡面無 0／中性／正常／續抱／安全 | 2 |
| T4 | p02～p05 `test_no_exit_stays_no_exit` | 卡面去哪補＝`NO_EXIT_MARKER` | 無出口不改寫成指路 | 摺疊「去哪補」＝`NO_EXIT_MARKER`；卡面 chip 不是指路 | 2 |
| T5 | 約 36 檔 `v2_short_rows` 斷言族（`test_v2_silent_fail_b1`…`b13`、`test_batch_z39/z48/z53/z55/z56/z57/z58`、`test_xv_h3_fx_not_summed`、`test_me_p1_deadends`、`test_sheet_safety_qa_fixes`、`test_v2_sa2f2/f4/f7`、`test_v2_batch_w_0928`、`test_v2_easy3_fake_stuck` 等） | 精確字句（隱含上卡面） | DEC-031；missing≠HOLD；客戶逐字句 | 同字串、換容器（「卡面那 1 句或摺疊」）；只做 KeyError 者不動 | 2 |
| T6 | `test_v2_client_words_0927` | 長句＋卡面短句都印 | 客戶逐字句 | 常數逐字可取得；作 1 句時不截 | 2 |
| T7 | p02～p05 `test_red_cards_*`、`test_full_*_in_the_fold`、`test_nothing_lives_only_in_a_title_attribute`、`test_fold_is_collapsed_by_default…` 等 | 原文在摺疊、預設收合、不只 hover | §1 看得見；手機無 hover | 保留並擴及新元件 | 2（保留）／3（擴及） |
| T8 | `test_xv_asof::TestFaceLength::*` | 價格旁時間＋來源不截 | DEC-102 | 價格 chip 在 E17 同位置；字數守衛照舊 | 6 |
| T9 | `test_xv_asof::test_hold_codes_complete_on_face` | 15 例外代號全在卡面 | 例外不得藏 | 卡面 ∪ 摺疊 ＝ 完整代號集合 | 6 |
| T10 | `test_xv_asof::TestBasisInExistingFold` | 依據在摺疊 | — | 照舊 | — |
| T11 | `test_batch_c21::TestDisclosure::test_both_cards`、`test_face_length_item_list_always_visible` | Risk Cap 完整性句在卡面 | DR-2026-10-16-4；禁「上限可能偏寬」；M1B 不列入 | 「上限數字容器相鄰兄弟＝完整性 chip」；禁字／M1B 守衛照舊 | 4／6 |
| T12 | `test_batch_z59::test_l3_reports_undetermined_is_red_with_reason_on_face`（沙箱已知環境失敗 markdown_it） | 紅卡原因在卡面 | 紅態看得見 | 卡面 🔴＋≤1 句；摺疊全文 | 4～6 |
| T13 | `test_p01_today_view::TestLiveCardKeepsItsNote` | live 卡帶 Note 也要畫 | 不丟上游說明 | 摺疊含 Note 三段 | 2 |
| T14 | `test_p04_hold_view`：`test_the_dividend_card_always_says_it_excludes_income_tax`；`TestTheAiIsAlwaysDisclosedAsAi` | 但書與 AI 揭露在卡面 | 稅前；DEC-054／055 | 卡面 chip 存在＋正文旁全文仍在 | 6 |
| T15 | `test_p04_hold_view` 掛載、`TestScaleDisclosureComesFromL0::test_it_needs_no_gate_and_is_always_on` | 存在 | 兩套刻度不互比 | 照舊（兩套刻度揭露恆在；若 W7 拍板改 chip，再改讀為 L1 chip 恆在） | 6 |
| T16 | `test_uim_market_page::test_danger_card_demotion_is_signposted_from_hero_and_chart_d` | `DANGER_POINTER` 展開區外恰 2 次 | DEC-105 | 指路（句或 chip，依 W2 拍板）字面含「指標危險度」×2、冷／熱 session、目標 expander 標題字面存在 | 4 |
| T17 | `test_uim_market_page::test_chart_a_draws_by_default…`、`test_chart_b_groups…`、`test_cold_start_first_row_is_grey…` | 均線聲明與 ⬜ 在展開區外；圖預設直接畫 | DEC-092 Q2 | 同字串在 Primary header；圖仍預設直接畫（compact）；粗體不 pin | 4 |
| T18 | `test_uim_market_page::test_loaded_hero_items_match_panel_rows`、`test_chart_c_block_is_text_only…` | 長表外露；段數寫死 | 同源；不寫「無風險」；圖 C 零數字 | chip＋完整表 L2；守衛照舊；段數不寫死 | 4 |
| T19 | `test_uim_market_page::test_all_retained_toplevel_definitions_are_byte_identical_to_pre_uim`、`test_conclusion_sentence_and_expanders_are_identical_to_pre_uim`；`test_page_market::test_verdict_cards_identical_to_today` | byte／AST 相同 | 能力守恆；結論句逐字 | 接新鏈頭節、更新 `_INTENTIONALLY_CHANGED`；今天頁 parity 改資料層對帳 | 4 |
| T20 | `test_uit_target_page::TestColdParity`、`TestParityWithLegacyPages`；`test_uit_target_page_qa::TestParityEdgeStates`、`TestNonCardElementDiff` | 卡 HTML 逐 byte 相同 | 能力守恆 | 資料層 parity（card.key／state／value／note／facts 集合） | 5 |
| T21 | `test_uit_target_page::TestTextScans::test_first_screen_order_is_chip_search_ai`；`test_uit_target_page_qa::test_first_zone_is_lean…` | 首屏順序、元素型別 | DEC-092 Q5 | 依 Phase 5 線框拍板結果（W5、W6）重訂順序斷言；「非產業趨勢」字面恆在 | 5 |
| T22 | `test_uit_target_page` 其餘（工程字／死路字、`TestUnwired`、`TestScreening`、`TestMobileMatrixCards`） | 禁工程字等 | §1、v3 §02 | 照舊（擴及新元件） | — |
| T23 | `test_market_blocks::TestStructure::test_hero_has_four_cards…` vs `test_p01_today_skeleton::TestThreeColumnGrid`、p02～p05 `MAX_COLS==3` | 4 欄 hero 與 3 欄上限並存 | DEC-105 第 5 點（P2 偏離） | **暫不動**；改寫方式依 `CV1-DR-12` 裁示結果（W9） | 待 `CV1-DR-12` |
| T24 | `test_p01_today_skeleton::TestEachCardIsHonest`、`TestFailLoud` | Note 三段非空 | 非 live 必附原因與去處 | 照舊 | — |
| T25 | `test_market_blocks::TestWaterAndBasis`、`TestWording`；`test_page_me`；`test_nav1_default_mode_text`；`test_views_no_unverified_universal_claims`；`test_p0x_view_mount_claims` 等 | 逐字內容、首屏無 %、依據 6 欄、全稱句登記 | 各自語意 | 照舊；文字搬檔時機械更新 registry | 4～6 |
| T26 | `test_dividend_station_mounted::test_light_detail_layer_renders_without_expander`（legacy，DEC-019 凍結） | 明細禁放 expander | 效能 | legacy 不動；新 UI：下沉 ≠ 省運算（R10），重運算仍走 gate | — |

## §4 Phase 2 步驟（Helper／Test Contract Migration）

| 步 | 內容 | 產出 | 守衛 |
|---|---|---|---|
| **0**（唯一下一安全接手點） | 以當時 main 重新實測：T1～T26 檔清單與 grep 計數、`v2_short_rows` 引用、還原鏈 sha 守衛覆蓋（§5）、H 系列 caller；與本檔差異寫回本檔（append-only）；⛔ 改產品程式 | 實測清單（docs／test-only） | — |
| 1 | `src/ui_v2/markup.card_html()` 加可選參數（H22）、`_ui_kit.single_submit_form(options_label=None)`（H8）、`render_card(compact=False)`（H5）、`FOLD_SUMMARY_TEXT` 外加 `label` 參數（H24）——**預設輸出逐 byte 不變** | 共用層可選參數 | `test_block_registry`、`test_lamp_card_fold` **不改**；新 golden 覆蓋新參數 |
| 2 | 改寫 T2～T7、T13、T5（同字串換容器）為資訊守恆斷言（現行畫面下仍綠） | tests | 每條改寫寫理由 |
| 3 | ~~T23 拆兩條~~（本 PR 第二輪 QA 改寫：欄數待 `CV1-DR-12` 裁示，Phase 2 不動 T23） | — | — |
| 4 | 新增「hover-only 0 項」「摺疊預設收合」通用斷言（T7 擴及） | tests | — |
| 5 | mutation：§6 清單逐一拔守衛必紅 | PR 描述 | — |

- **還原鏈 sha 守衛處理原則**：Phase 2 **不碰任何受鏈守衛的檔**（`page_today.py`、`page_hold.py`、`page_why.py`、`page_market.py`、`page_me.py`、`page_find.py`、`page_inspect.py`、`risk_cap_gate.py`）；只改不受守衛者（`_ui_kit.py`、`_market_blocks.py`、`_target_blocks.py`、`src/ui_v2/markup.py`、`tab_today.py`）與 tests。若某斷言只能在受鏈檔改動後成立 → 移到該頁 phase。
- **零資料語意證明**（每個 phase PR 描述必附）：(a) diff 僅 `src/ui/**`、`src/ui_v2/**`、`tests/**`、docs；`src/services/**`、`src/compute/**`、`src/data/**`、`shared/` 語意模組 0 行；(b) builder parity（同輸入 card.key／state／value／note／facts 集合相同，基底＝批前 main）；(c) 資訊守恆（舊頁每段字串在新頁卡面 ∪ 摺疊 ∪ 既有 expander 出現；AppTest 攤平；冷／熱 session）；(d) mutation；(e) AST：新模組不 import `src.data`／`src.services`、不加 `st.cache_*`；(f) Top-N：切片物件同一性、全表在摺疊、`TOP_N_OPTIONS`／`DEFAULT_TOP_N` 與 L3 請求參數不變；(g) `classify_ui_state`、`v2_card_badge_n`、`NO_VALUE_STATES` 輸出不變。
- **DoD**：CI 綠（fast＋slow）；零畫面變更證明（批前／批後 1440＋390 三頁第一屏截圖或量測值相同）；獨立 QA ≥2 組；BACKLOG／HANDOFF 同步。

## §5 還原鏈／基底 sha 守衛（FACT，Inv-2 regex 掃描，可能漏）

`page_hold.py`：asof、d2_shell、dec074、me_p1、nav1、xvext、sheet_safety、batch_c21、batch_z66b、vn1_b2_silent_reauth（10）；`page_today.py`：dec074、me_p1、c21、z66b、uia_01_02_07（5）；`page_why.py`：c21、z66b、uia（3）；`page_market.py`：nav1、uim（2）；`page_me.py`：nav1；`page_find.py`：me_p1；`page_inspect.py`：asof（z46／z47／z48 引用路徑常數，是否 sha 鏈未確認）；`risk_cap_gate.py`：c21。**不受守衛**：`_ui_kit.py`、`_market_blocks.py`、`_target_blocks.py`、`src/ui_v2/markup.py`、`tab_today.py`。

- **接新鏈頭節慣例**（比照 `tests/test_uim_revert_chain.py`）：改到受鏈守衛的檔時，新增 `tests/test_p<phase>_revert_chain.py`：基底 sha 寫死、`*_REVERT_PAIRS` 由最小唯一上下文產生並驗證「套用後逐字等於基底、新寫法在現行檔恰 1 次、套用後 0 次」、idempotent；在最上游既有鏈入口第一步呼叫；⛔ 動舊表與舊基底 sha。
- **最低成本切點（INFERENCE）**：卡面組裝下沉到 `_market_blocks`／`_target_blocks`／`ui_v2.markup`／Phase 3 新模組；Phase 6 優先以既有 `build_*` 組新頁組裝器，避免改 `_render_warroom_leaf`（10 條鏈）。

## §6 Mutation 清單（Phase 2／3）

M1 sparkline 把 NaN 補 0｜M2 metadata chip 接受未登記 kind｜M3 新 kind 與 `BADGES` 重名｜M4 Top-N 切片回傳複製或改序｜M5 `card_html` 新參數改變預設輸出 1 byte｜M6 摺疊預設 `expanded=True`｜M7 chart header 把說明句放在 chip 之前｜M8 新模組 import `src.services`｜M9 stale chip 用紅色 class｜M10 metadata chip 經訊號文字頻道輸出｜M11／M12（欄數）待 `CV1-DR-12` 裁示後再訂｜M13 摺疊內容只留在 `title=`。

各頁 phase 另列（至少）：Primary 被放進 expander、Primary 超高、≥2 張大型圖同屏、主要判讀句離開第一屏、Top-N 改 L3 參數、Missing 冒充 0、工程字樣外露、價格 chip 離開 E17、完整性 chip 與上限數字拆開、指路字面缺「指標危險度」、hover-only 回歸、Digest 受 UI Top-N 影響（Phase 7）。

## §7 Phase 3～7 要點

- **Phase 3**：新純字串模組（建議 `src/ui_v2/compact.py`，無 streamlit）：`meta_chip_html(kind, text)`（kind 封閉集＝契約 §6）、`sparkline_svg(values, w, h)`（丟 NaN、⛔ 補 0、全 NaN→placeholder）、`mini_card_html(...)`、`chart_header_html(title, chips, say)`、`topn_view(rows, n)`、`segmented` 呈現 helper、`compact_css()`（與既有 page CSS 分開，保今天頁 CSS byte-identical）；`_ui_kit.status_chip()`、`render_fold(label, rows)`；`Basis` 合併（H31）；tokens 收斂（`P1R-TOKENS-CONVERGE`，客戶裁示色值先判）；站殼間距子項（只動站標高度與頂部留白；⛔ 改 `PAGE_LABELS`／導覽殼語意／legacy 入口；若獨立 QA 判屬 IA／殼變更 → 停手送客戶）。`requirements.txt` floor 1.56 下 `st.metric(chart_data=)`、`st.bar_chart(horizontal=)`、form 內 expander 先以 floor wheel 實跑，未驗前不使用（`P1R-FLOOR-156-API`）。
- **Phase 4（📊 reference）**：改動檔預期 `_market_blocks.py`（無鏈）、`page_market.py`（nav1／uim 鏈 → 新頭節）；⛔ 動 `page_today.py`。重點守衛：結論句逐字、Q2-2 逐字、均線聲明逐字、⬜ 尚未定義、指標危險度指路、圖 C 零數字、hero 與圖 D 同源、EPS×PE placeholder、更新 form／gate 語意不變。版面骨架若偏離 blueprint → 草稿先行。
- **Phase 5（🎯）**：`_target_blocks.py`、`page_target.py`；`page_find.py`／`page_inspect.py` 不改。重點守衛：DEC-107 2A／3A／4A／5A 互動不變；R9；估值口徑揭露不刪；**選股條件維持 `expanded=True`**，除非 Phase 5 線框中客戶拍板改為收合（W4）；W5、W6 同依線框拍板。
- **Phase 6（💼）**：新頁組裝器（新檔，無鏈）＋最小必要 `page_hold.py` 掛載點（新頭節）；重點守衛：外幣排除逐字、E17、missing≠HOLD、停利未判、AI 揭露與付費 gate、`build_station_digest` 計數來源不變、兩套刻度揭露恆在（形式依 W7 拍板）；建議拆 (i) 骨架＋第一屏 (ii) 卡片 compact 化與下沉。
- **Phase 7（Brain）**：依 Digest 契約 §8 依賴順序；AI 投資總結線框先行（R12 新格式）；AB-2b Gate 未裁示前 AI 出口不接 production。

## §8 風險

| 風險 | 緩解 |
|---|---|
| `V2_SHORT_ROWS`／`V2_EXIT_PHRASES` KeyError → 紅卡；Note now 字串變動也會紅 | 只換容器、不改字串；登記／死列對帳測試保留 |
| glyph 碰撞（⬜／⚠／🔴 進訊號文字） | metadata chip 獨立通道；M10 |
| BADGES 封閉集被擴 | 族分離測試（M3） |
| 1.56 floor 未驗 API | floor wheel 實跑；未驗前不用 |
| mini 圖被讀成結論 | `⬜ 尚未定義` chip 必留；均線聲明逐字 |
| hover-only | 移入摺疊；M13 |
| `st.columns` 手機塌單欄 | HTML／CSS grid |
| 還原鏈成本（page_hold 10、page_today 5、page_why 3、page_market 2，粗估） | 卡面組裝下沉無鏈檔；新頭節慣例 |
| 測試檔量（約 67 檔引用 v2 卡 helper、約 40 檔 187 處 `v2_short_rows`，grep 粗估） | 頁面層斷言分批到各頁 phase |
| 線框待拍板點（W1～W9）未獲客戶拍板 | 維持現行呈現；不阻擋其餘不改畫面的施工 |
| 站殼改動被判 IA | 停手條件（§7 Phase 3） |
| Digest 依賴 session warroom | Phase 7 前置 headless 組裝點 |

## §9 BACKLOG 去處

各 phase 與已知候選見 `docs/BACKLOG.md` §5.1.16（`P1R-*`）。⛔ 本計畫不授權：新資料源、新規則、Risk Cap 公式、EPS×PE、趨勢定義、`PAGE_LABELS`／導覽殼改名、`src/ui/tabs`→`views` 改名、舊 UI 任何修改（DEC-019）。

## §10 各 phase 線框待客戶拍板點（2026-10-29 總管改判）

原則：AI 總管讀法不得推翻客戶核准過的呈現。凡「改變客戶核准呈現」且 DEC-109 客戶原文未明確點名者，**維持現行**，並在該 phase 的線框草稿（`CLAUDE.md` §-1.5.D v3 §03-2 ① 草稿先行）列為待客戶拍板點，附總管推薦方案；**本 phase 不另開 Gate、不改**。清單＝Presentation Contract §22：

| Phase | 待拍板點 |
|---|---|
| 3 | W1 tokens 客戶裁示色值是否改 blueprint 色值（`P1R-P3-WF-CUSTOMER-COLORS`） |
| 4 | W2 指標危險度指路說明句維持 vs 改 chip（`P1R-P4-WF-POINTS`）；W3 卡片摺疊標籤（`P1R-WF-FOLD-LABEL`）；**W9** KPI／Hero 欄數（`CV1-DR-12`，v3 §00「固定 3 欄」vs DEC-091 §四「3～4」／Hero 4 欄；裁示前維持現狀） |
| 5 | **W4 選股條件預設展開 vs 預設收合＋摘要 chip**（`P1R-P5-WF-SCREEN-COND`）；W5 1A 順序內候選如何提前；W6 排序依據說明句 → chip（`P1R-P5-WF-POINTS`）；W3 |
| 6 | W7 兩套刻度常駐非摺疊 vs L1 chip＋可展開（`P1R-P6-WF-TWO-SCALES`）；W3 |
| 7 | **W8**「主要風險／變化 1～3 項」的選取規則（`P1R-P7-WF-CHANGE-RANK`）；拍板前誠實 MISSING，⛔ 內部預設 |
