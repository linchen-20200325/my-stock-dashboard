# New UI2 手機抽屜：測試與驗收規格（治理採用版）— 2026-11-04

> **治理採用的施工規格（單組撰寫＋獨立 QA）；正式 JS 未核准；本批不授權施工；非客戶視覺驗收。**
> 配套：統一施工規格 `NEWUI2_MOBILE_DRAWER_UNIFIED_BUILD_SPEC_2026-11-04.md`（行為需求 R-xx、尺寸 §5）；JS 安全設計 `NEWUI2_MOBILE_DRAWER_JS_SAFETY_DESIGN_2026-11-04.md`。
> **改 workflow、加 pytest marker、改 conftest、改 `measure_viewport.py`、改任何既有測試——全部屬施工，不在本批。** 本檔只是規格。**CI required check 的設定需 user 在 GitHub 操作**，本 repo 的 AI 工作階段無權限讀寫 branch protection（也未能讀到現況內容）。
> 誠實揭露：沙箱耗時為 4 vCPU 沙箱的單組實測／推估，**未能實測 GitHub Actions runner**（無法執行 workflow、無法下載 Chromium、未測 `install-deps`）；行號為 2026-11-04、main `46967451` 的量測值，會漂移（`CLAUDE.md` §8.2.A.0 規則 4）。

## 1. 既有守衛依賴清單（施工時**必須同 PR 改寫**，不得只刪）

**改寫原則（寫死）**：同一個 PR；改寫後的判準**等價或更嚴格**；附**變異測試**證明舊違規形式（例如「把導覽放回底部」「多放第二組 radiogroup」「拿掉 `ui2_nav` 錨點」）仍轉紅；PR 摘要**逐條註明不再覆蓋的舊斷言**。**不得只刪、不得 skip／xfail 隱藏**（`CLAUDE.md` §-1.5.A 與 DEC-134「不得默默降測試」）。

| # | 守衛／判定器（出處，2026-11-04 行號） | 現在守什麼 | 抽屜版對等判準（規格方向） |
|---|---|---|---|
| D-1 | `tests/test_ui2_batch2.py::test_w1_mobile_nav_is_bottom_fixed_53px`（~:57）：斷言 `.st-key-ui2_nav{left:0;right:0;bottom:0;height:53px` 與 `padding-bottom:5rem` | 手機底部固定 53px | 手機：抽屜寬 `min(82vw,320px)`、☰ `top:0;left:0` 且高 44px、關閉態 `visibility:hidden`、內容底部留白仍存在；**無** `bottom:0;height:53px` 的主導覽（突變：放回底部必紅） |
| D-2 | `test_ui2_batch2.py::test_w1_desktop_nav_is_left_column`（~:65） | 桌機左欄 `top:0;left:0;bottom:0`、`padding-left:12.5rem` | 不變；另加「桌機 ☰／toggle／遮罩 `display:none`」「rail 176px」 |
| D-3 | `test_ui2_batch2.py::test_w1_current_page_is_marked_beyond_color`（~:72） | 當前頁不單靠顏色 | 保持；抽屜內同樣成立（粗體＋左色條＋●） |
| D-4 | `test_ui2_batch2.py::test_w1_nav_css_does_not_depend_on_streamlit_internal_classes`（~:79）：掃 `/* ── W-1` 區段之後 | 導覽 CSS 不得含 `emotion`／`data-baseweb`／`stRadioOption` | 保持＋加嚴（建議再禁 `stSidebar`／`stToolbar`）。⚠️ 零 JS 修法 `.st-key-ui2_nav *{visibility:inherit !important}` 用 `*` 不含這些字樣，但須驗不踩此守衛 |
| D-5 | `test_ui2_batch2.py::test_w1_nav_is_exactly_four_fixed_pages_no_fifth`（~:38）、`…keyed_container_with_ui2_prefixed_radio`（~:43）、`…page_switch_still_works_via_app_test`（~:85） | 恰四項、`ui2_nav` 容器、`ui2_page` radio、AppTest 換頁 | **原封不動**（抽屜保留同一容器與 radio） |
| D-6 | `test_ui2_batch2.py:337`：`NAV_MOBILE_H == 53 and 844 - NAV_MOBILE_H == 791`；`tests/ui2_viewport/measure_viewport.py:40` | 第一屏可用高＝791 | 常數保留，改註為「底部保留帶（Manage app／家的指示條遮擋區），非導覽高」；可用高維持 791 |
| D-7 | `measure_viewport.py` 判定器：`first_screen_within_usable_height`（:49 定義、:146 起）、`first_screen_above_nav`（:53、:156）、`nav_fixed_four`（:172 檢查「導覽貼底 53px、四格同列」）；`test_ui2_batch2.py:357` 附近評估器 teeth | 手機第一屏元素底緣 ≤ 791、不與底部導覽相交；導覽恰 4 項貼底 | 改為：第一屏元素不與 ☰ 矩形相交；**關閉態**抽屜完全在視窗外且不可見；**展開態**抽屜內 `radiogroup` 恰 4 項、全 DOM 僅 **1** 個頁面 radiogroup；視窗底部 0 個 `position:fixed` 主導覽。評估器 teeth（突變：導覽放回底部／多放第二組 radio）須轉紅 |
| D-8 | `measure_viewport.py` 的點 label 換頁流程 | 對導覽 radio 的 label 做 click | ⚠️ **抽屜收合時 radio 不可見，點 label 會逾時**——量測流程須先開抽屜（點 ☰）再點，或改走 `ui2_page` 的程式路徑（二選一，由施工批決定並寫進測試） |
| D-9 | `tests/test_ui2_batch3.py`：`test_nav_margin_content_bottom_reserve_covers_nav_height_and_safe_area`（~:959）、`test_nav_margin_cta_row_puts_reason_beside_button_not_below`（~:972）、`test_nav_margin_thresholds_registered_and_stress_evaluator_has_teeth`（~:981）、`test_nav_margin_evidence_json_locks_real_browser_numbers`（~:999）；`THRESHOLDS` id 釘值（~:704–773） | 內容底部留白 ≥ 導覽 53px＋`env()`；`market_main_risk_nav_margin` 等 id 釘值 | 留白改為「≥ Manage app／家的指示條保留量」（暫維持 `5rem + env(safe-area-inset-bottom)`，數值待真機），仍斷言帶 `env()`；**THRESHOLDS 的 id 不得悄悄改名或消失**（釘值測試） |
| D-10 | `nav_margin_after_risk`／`market_main_risk_nav_margin`（`measure_viewport.py:80、383、624`；`test_ui2_batch3.py:798、981、999`）與證據 JSON | 風險後第一區塊頂緣距導覽上緣 ≥ 1 行行高 | 改為距「視窗底扣底部保留帶（53px）＝線 791」≥ 1 行行高；證據 JSON 以新量測**另存新檔**，⛔ 覆寫舊證據 |
| D-11 | `p2_nav_margin_160`（`measure_viewport.py:129、229`；`tests/test_ui2_p2_primary_slot.py:286` `test_viewport_nav_margin_160_applies_to_mobile_stale_and_unavailable_only`、:302） | 手機 stale／unavailable：風險後第一區塊頂緣距導覽上緣 ≥160px | **等價**：距線 791 ≥160px（不放寬）；基準 stale 181.6／unavailable 162.5 須逐位相同。未達＝停手回報（客戶 (19)） |
| D-12 | `tests/test_ui2_contract_teeth_pending.py::test_mobile_nav_stays_four_cells_in_css`（~:96，名稱寫「四格」，內容很弱：只斷言 `ui2_nav` 與 `position: fixed` 存在） | 錨點與 fixed 存在 | 保留；施工批改名並補斷言（手機 `@media` 內抽屜隱藏態存在、☰ 規則存在、**無** `bottom:0;height:53px`）。⛔ 刪除 |
| D-13 | `tests/test_ui2_real_feed.py`：`_full_from_evidence`（~:729）依賴證據 JSON 的 nav 欄位形狀；`MV.evaluate` 驅動 `test_real_banner_evaluator_has_teeth`（~:715）、`test_real_me_evaluator_rejects_a_pretend_account`（~:743） | evaluator 有牙齒 | 若 evaluator 的 nav 欄位形狀改變，`_full_from_evidence` 要同步；teeth 測試仍須轉紅 |
| D-14 | `test_ui2_real_feed.py::test_real_viewport_evidence_passed_and_is_real_mode`（~:695，parametrize 兩檔 `viewport_measurements.json`／`viewport_measurements_streamlit156.json`，讀 `docs/vnext/newui2_realfeed/`）：斷言 feed=real、`failed==[]`、`states==11` | 證據存在且全綠 | ⚠️ **舊檔可沉默通過**（meta 無 git_sha／source_hash／時間戳，CSS／JS 改了也不會紅）→ 見 §2.5 |
| D-15 | `tests/test_ui2_active_contract_docs.py:391、402`：逐字守 DEC-129 fence「手機仍固定四格導航」「11. Mobile 仍只有四格導航」與 Active Contract 開頭「11. **手機仍只有四格導航**」 | 文件字面 | ⚠️ **改這些文字會紅**。因此本批與施工批對 DEC-129／Active Contract **只能追加註記，不能改原文**；DEC-134 已在 DECISIONS 以 📌 取代其「位置與顯示方式」 |
| D-16 | `tests/test_ui2_active_contract_docs.py:293`：`PENDING_UI_CORRECTION_TESTS` 的檔名須以 `test_ui2_` 開頭（或 `measure_viewport.py`） | 待改測試登記 | 新增的抽屜行為測試檔**檔名必須 `test_ui2_` 開頭**（例：`tests/test_ui2_drawer_browser.py`、`tests/test_ui2_drawer_js_guard.py`）；若這些檔屬「待改清單」須登記 |
| D-17 | `ALLOWED_UI2_WRITES`（`test_ui2_real_feed.py:503`，目前 5 個 key）／G9 `check_not_a_producer`／`tests/test_ui2_guards.py` 的 `check_axis_separation`（:1212）、`check_ui2_dev_not_auth`（:1301 附近）、`T_new_9` | session key 限 `ui2_` 且白名單；軸分離；`ui2_dev`／query 不得當登入證據 | C+JS **不新增 session key → 不動**（若改走 B 案才需擴白名單）。**新增**：抽屜／帳戶摘要原始碼不得讀 `ui2_account`／`st.query_params`（AST 守衛，沿用 `check_ui2_dev_not_auth` 風格）；殼內 raw `<input>` 僅准白名單（抽屜 toggle）一處；JS 守衛（JS 設計 §6～§9） |
| D-18 | 現有 `tests/test_ui2_batch2.py::test_real_browser_viewport_acceptance`（~:389，`@slow`、`pytest.importorskip("playwright.sync_api")`、缺 Chromium 時 `pytest.skip`） | 真瀏覽器量測 | ⚠️ **現況沒有任何 CI 強制執行真瀏覽器**（slow lane 本就 `continue-on-error`，缺 playwright／Chromium＝skip＝綠）。skip 分支須改用共用 `require_browser()`（§2.3） |

> 研究組在**撰寫組副本**實測：`tests/test_ui2_*.py` 1263 過／37 失敗／3 xfailed（C 類含 JS；B 類 session 控制約 33 失敗來自 G9）。**僅副本、單組、未重跑**，只用來示意衝擊面。

## 2. Playwright CI 強制 Gate 設計

### 2.1 事實（讀檔／沙箱實測）

- `pr-check.yml`：`fast-checks`（`pytest -v`，addopts `--strict-markers -m "not slow"`，blocking）＋`slow-tests`（`pytest -v -m slow`，`continue-on-error: true`，informational）。兩 job 都沒裝 playwright；`requirements.txt` 無 playwright（Z59 先例：測試依賴只在 workflow `pip install`，不進 requirements.txt）。
- `pytest.ini` 只註冊 `slow` marker；`--strict-markers` 開啟 ⇒ 新增 marker 必須註冊（屬施工）。
- 沙箱實測（4 vCPU、Python 3.13、playwright 1.64.1、streamlit 1.59.2）：Streamlit 啟動到 health OK 1.0 s（暖）；Chromium launch 0.19 s；390 首屏渲染 2.6 s／1440 1.6 s；Tab×20 0.13 s；現有完整 viewport 量測（2 viewport×~50 狀態）**66.7 s**（單一 Streamlit 版本）；1.56 venv 新裝約 50 s（有本機 pip cache，runner 冷裝推估 60–90 s）；chromium 393 MB、headless_shell 261 MB（解壓）、playwright wheel 47 MB。
- 單一抽屜行為測試推估 5–15 s／case；一組 8–10 case × 2 viewport 約 1–2.5 min（推估）。業界經驗 `playwright install --with-deps chromium-headless-shell` 冷裝約 30–60 s，ms-playwright cache 命中約 5–10 s（+ `install-deps` apt 約 10–20 s；**推估，非實測**）。
- 沙箱 playwright 要 chromium 1248 但只有 1243，靠 `launch_chromium` fallback 才過；CI 用 `playwright install` 會裝對版本。playwright 目前**未 pin** → 版本漂移風險。

### 2.2 方式比較

| 項目 | A pr-check.yml 新增 `ui2-browser` job | B 獨立 workflow＋path filter | C 本機／手動 lane＋meta 測試 | D = A＋固定名稱 gate job（`needs:` matrix） |
|---|---|---|---|---|
| 真的執行？ | 是（env 強制、缺瀏覽器 fail） | 是，但 path filter 的 required check **未觸發時永遠 Pending 卡 merge**（GitHub 已知坑）；要變 always-run＋內部判斷＝退化成 A | **否**：CI 永不跑，違反 skip≠PASS；meta 測試只能看「有沒有被 skip」 | 是 |
| Streamlit 1.56／1.59 | matrix `streamlit: [1.56.0, 1.59.2]` | 同 | 本機兩 venv，易漏 | 同 A |
| 390／1440 | 測試內 parametrize | 同 | 同 | 同 |
| 對 Fast 的 wall-clock | 與 Fast 平行；每 matrix 格估 **3–6 min**（安裝 1.5–2.5 min＋抽屜測試 1–2.5 min），runner 分鐘 +6–12 | 同 | 0 | 同 A |
| required check 維護 | 需把 matrix job 名（含版本）加入 branch protection；matrix 改名要同步改 | 同＋path filter 坑 | 不需 | **固定名稱 gate job 作唯一 required**，matrix 名稱不綁死 |
| 失敗診斷 | 上傳 trace／screenshot／evidence JSON artifact | 同 | 靠 PR 貼輸出，不可重現 | 同 A |
| 維護／Token 成本 | 低–中（1 job＋1 env＋1 meta 守衛） | 中 | 最低但風險最高 | 低–中 |
| 正確性 | 高 | 中（Pending 坑） | **低** | 高 |

### 2.3 推薦：**A＋D**（最小充分）

- 在 `pr-check.yml` 新增 `ui2-browser`（matrix streamlit **1.56.0／1.59.2**；缺 Chromium 即失敗）＋一個**固定名稱** `ui2-browser-gate` job（`needs: ui2-browser`，`if: always()` 並檢查 matrix 結果），**只把 gate job 設為 required**。不新增獨立 workflow。
- **備案**（若 runner 分鐘是瓶頸）：job 內先 `git diff --name-only origin/main...HEAD` 判斷是否碰 `src/ui2/`、`app_ui2.py`、`tests/ui2_*`、`tests/test_ui2_*`、css；**未碰**則只跑約 5 s smoke（仍回報綠）。另一個取捨：1.56 格只在 push main／nightly 跑、PR 只跑 1.59——**不建議**（1.56／1.59 selectbox 行為已實測不同，PR 層放棄 floor 回歸）。
- 以上是**單組研究結論**，runner 實際耗時未驗。

### 2.4 強制不可 skip 機制（規格）

1. workflow 設 `UI2_BROWSER_LANE=required`；共用 helper `require_browser()`：env＝required 時缺 playwright／缺 Chromium → `pytest.fail`（**不** `importorskip`、不 skip）；env 未設（本機）才 skip 並印警示。
2. 行為測試用獨立 marker **`ui2_browser`**（`pytest.ini` 註冊；`--strict-markers`），預設 `-m "not slow and not ui2_browser"`（本機不被拖慢）；browser job 以 `pytest -m ui2_browser -rs --junitxml=…` 執行。
3. job 結尾解析 junit：**`skipped > 0` 或 `tests < 預期下限` → 紅**（不靠 pytest 自身）。
4. **meta 守衛**（進 fast lane，純 AST／文字，**不需瀏覽器**）：①New UI2 行為測試檔不得裸 `pytest.importorskip("playwright…")`／`pytest.skip(`（唯一許可在 `require_browser()`）；②帶 `ui2_browser` marker 的測試名單必須涵蓋 §3 清單每個 ID（漏登＝紅，仿 §8.2.A.0 規則 3）；③讀 workflow YAML 斷言：含 `UI2_BROWSER_LANE: required`、**pin 的 playwright 版本**、matrix 兩個 streamlit 版本、gate job 存在（防有人悄悄刪）。
5. 現有 `test_real_browser_viewport_acceptance` 的 skip 分支（D-18）改用 `require_browser()`，否則它仍可靜默 skip。
6. **playwright 版本 pin**（workflow 或 `requirements-browser-lane.txt`；不進 `requirements.txt`）。
7. 測試內斷言 `streamlit.__version__ == 該格 matrix 期望`（防 matrix 裝錯版本仍綠）。
8. 快取：setup-python pip cache；`actions/cache` key＝`playwright-${{ hash(版本 pin) }}`，路徑 `~/.cache/ms-playwright`（命中仍需 `install-deps`）。

### 2.5 證據 JSON 防沉默通過

- `measure_viewport` 輸出 `meta` 增：`git_sha`（HEAD）、`source_hash`（sha256 of `src/ui2/**`＋`app_ui2.py`＋`measure_viewport.py`）、`generated_at`、`playwright_version`、`chromium_version`。
- `test_ui2_real_feed` 的證據測試比對 `meta.source_hash == 現算 hash`，不符＝紅，訊息「證據過期，請重跑 measure_viewport」；**兩個檔（1.59／1.56）都驗**。（新增 hash 後所有現存證據檔需重生一次。）
- CI browser job 另**現場重跑**量測（輸出到臨時目錄）並上傳 artifact，不依賴 commit 的舊檔；committed 證據只作人讀存證。

> ⚠️ §2.3～§2.5 的 workflow／marker／conftest／measure_viewport 修改**全部是施工**，不在本批，需治理核准；required check 設定需 **user 在 GitHub 做**。

## 3. 測試清單（施工批須全部落地；每項 **390 與 1440**、**Streamlit 1.56 與 1.59**）

> 本節選擇器、事件名稱以統一施工規格 R-xx 與 JS 設計為準；DOM 選擇器待實作後定。除特別註明外為 `ui2_browser` marker（Playwright，Chromium）。**背景可聚焦／a11y 的驗證一律用 CDP `Accessibility.getFullAXTree`；Playwright `aria_snapshot()` 不反映 `inert`，不可作證據。**

| ID | 測試（對應 R） | 390（手機） | 1440（桌機） |
|---|---|---|---|
| T-01 Tab 連按 | 開啟後 **Tab ×20**，`document.activeElement` 每次皆在 {抽屜, ☰} 內，背景元素 0 次聚焦（R-07）。⚠️ 已知允許：`section.stMain` 可拿一次焦點，須在白名單內明列，否則紅 | 必測 | ☰ 不存在 → 斷言無 inert、Tab 可進內容 |
| T-02 Shift+Tab 反向 | **Shift+Tab ×20** 同上 | 必測 | 同上 |
| T-03 a11y 背景歸零 | CDP AXTree：開啟後「背景具名節點」數＝0（研究組實測 13→0）；關閉後恢復 | 必測 | 無 inert |
| T-04 當前頁收合 | 點目前所在頁 → 收合（R-05），focus 回 ☰ | 必測 | n/a |
| T-05 他頁收合 | 點他頁 → 立即收合、頁面換、focus 回 ☰（R-04）；四頁各一次；**server 人為延遲 1.5 s** 下仍立即收合 | 必測 | n/a |
| T-06 Esc | 開啟中 Esc → 關、focus 回 ☰（R-08） | 必測 | n/a |
| T-07 焦點返回 | 以 Esc／遮罩／切頁／當前頁／方向鍵五種方式關閉，`document.activeElement` 皆為 ☰（R-09） | 必測 | n/a |
| T-08 監聽去重 | 開關 N 次＋Streamlit rerun 數次後，document 上 keydown／change 監聽數、MutationObserver 數**不增**；以注入計數器 wrap `addEventListener`（headless 無 `getEventListeners`），輔以行為驗證（Esc 一次只觸發一次關閉）（R-13） | 必測 | 必測（JS 在桌機也載入） |
| T-09 inert 殘留 | (a) 開著抽屜 rerun；(b) **連續 30 次**切頁（每次先開）；(c) 快速連點 ☰ ×9／Esc ×5；(d) 頁面重載（開啟中）；(e) **開啟中改視窗 1440、再縮回 390**。每種結束後 inert 計數為 0（或抽屜為關閉態）、無 pageerror | 必測 | (e) 的 1440 端 |
| T-10 方向鍵／Enter／Space | 焦點在抽屜 radio：方向鍵選取並關；Enter／Space 關（R-10）。另斷言 **Enter 在 ☰ 上不開**（已知限制，防日後被誤認為 bug 或被默默改行為） | 必測 | n/a |
| T-11 遮罩關閉 | 點遮罩 → 關、focus 在 ☰（R-06） | 必測 | n/a |
| T-12 第一屏餘裕 | 市場頁 stale／unavailable，風險後第一區塊頂緣距線 791 ≥160px；**基準 stale 181.6／unavailable 162.5 逐位相同**（R-14）；`measure_viewport` 正式量測，不用副本外推 | 必測（FAKE＋Real） | n/a |
| T-13 關閉態 a11y 乾淨 | CDP AXTree：關閉態不含「Google」登入區塊與「📊 市場」抽屜文字（L-4 修法後）；`.st-key-ui2_nav` 內無可聚焦元素 | 必測 | n/a |
| T-14 桌機 | ☰、toggle、遮罩 `display:none`；rail 寬 176px；`.block-container` 讓出 12.5rem；無水平捲動 | n/a | 必測 |
| T-15 無水平捲動／邊界視窗 | 390／360×640／320×568／740×360；`document` 無水平捲動；844×390 走桌機 rail（可捲動） | 必測 | n/a |
| T-16 reduced motion | `emulate_media(reduced_motion='reduce')` → 抽屜無 transition | 必測 | n/a |
| T-17 version 斷言 | `st.__version__` 等於 matrix 期望 | 必測 | 必測 |
| T-18 單一主導覽 | 全 DOM 頁面 radiogroup 恰 1 個、含 4 radio；視窗底部 0 個 fixed 主導覽（防雙導航） | 必測 | 必測 |
| T-19 帳戶區塊固定占位 | 抽屜／rail 帳戶區：`⬜ 尚未提供`（能力軸）、登入鈕 `disabled`/`aria-disabled`、原因句；**切換 FAKE `ui2_account` 三態（開發面）後文字不變**；FAKE 預設 signed_in 時抽屜不顯示「已登入」 | 必測（FAKE＋Real） | 必測 |
| T-20 JS 被擋降級 | 以 CSP／攔截讓 script 不執行：切頁仍收合（輪替 hack）；此時 inert／Esc／焦點管理缺席——**測試記錄為「降級」，不得標 PASS 為完整行為** | 必測 | n/a |

**非瀏覽器（fast lane，AST／文字）**：JS 雜湊釘住與白名單（JS 設計 §6～§8）、兩範圍全域掃描（§7）、JS／CSS 斷點交叉比對（§9）、AccountVM 不讀 `ui2_account`／query（D-17）、meta 守衛（§2.4-4）。

## 4. 突變 teeth（拔掉修復邏輯必須轉紅；`CLAUDE.md` v3 §03-1 第四項）

| 突變 | 必紅的測試 |
|---|---|
| 拿掉 inert（`hold()` 空或不設屬性） | T-01／T-02／T-03 |
| 拿掉 focus-return（`t.focus()`） | T-07 |
| 拿掉去重旗標 | T-08（＋雜湊測試） |
| `release()` 改空函式 | T-09 |
| `sync()` 拿掉桌機 release 分支 | T-09(e)／T-14 |
| `click` 改 bubble 或拿掉點當前頁委派 | T-04 |
| 拿掉 Esc 分支 | T-06 |
| 把導覽放回底部固定／多放第二組 radio | D-1／D-7／T-18 |
| 抽屜標記移到內容前或另開 `<style>` | T-12（餘裕 <160） |
| 帳戶區塊改為讀 `ui2_account` | T-19／AST 守衛 |
| JS 常數多一個字元、加 `fetch`、`unsafe_allow_javascript` 第二處 | 雜湊／白名單／AST／全域掃描測試 |

研究組在原型上完成其中 JS 端的 31 種守衛變異＋4 種行為變異（單組結果）；**施工後必須在真實測試上重做一遍**，不得引用原型結果當作交付證據。

## 5. 驗收門檻與回報格式

- 通過條件：§3 全部在 **1.56 與 1.59、FAKE 與 Real** 綠；`skipped == 0`（browser lane）；§4 突變全紅；D-1～D-18 已同 PR 改寫並附「不再覆蓋的舊斷言」清單。
- 回報（交付報告第 2 段）必須逐項列出 §6 未驗。

## 6. 未驗（持續標示，永不宣稱 PASS）

iOS Safari；Android 真機；Streamlit Community Cloud／**Manage app 浮層**（本規格不宣稱已解決遮擋）；CSP 對 `st.html` JS；VoiceOver；TalkBack；Firefox；WebKit；GitHub Actions runner 的實際耗時與 `install-deps`；branch protection 現況；`inert` 不支援瀏覽器的實際降級；真機觸控手感；Real feed 下開關延遲。
