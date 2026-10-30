# Phase 3 步驟 4 — D8 切換鈕與 `P1R-FLOOR-156-API` 在 floor 1.56.0 的實跑驗證

> 日期：2026-10-30　性質：**驗證紀錄**（唯讀；`src/**`、`tests/**`、`requirements.txt` 0 diff）
> 依據：`PRESENTATION_MIGRATION_PLAN_2026-10-29.md` §16.2 步驟 4；`PHASE3_SHARED_COMPONENTS_WIREFRAME_2026-10-30.md` §2.3 / D8（客戶 DEC-115 D8=B，不成立則直接退回 A，不再請示、不得升高 floor）。
> 腳本：`tools/phase3_verify/`（`appttest_floor156.py`、`pw_app*.py`、`pw_*.js`；**不被 app／tests import**）。

## 0. 結論（先講）

**D8=B（`st.segmented_control` 膠囊式）在 floor 1.56.0 上成立，不退回 A。** 但有 5 條**硬性使用約束**（§4），其中第 1 條（取消選取回退）若不做，會直接造成「無選取 → 空圖槽」。

另有一個與 D8 無關、但會打到 Phase 3 `compact.py` 計畫的**重大發現**：**`st.html()` 在 1.56.0 會把行內 `<svg>` 整段剝除**（§3.2），`sparkline_svg` 不得走 `st.html`。

## 1. 驗證環境（據實）

| 項 | 值 |
|---|---|
| venv | scratchpad 獨立 venv（`python -m venv`），**未動系統 site-packages、未動 repo 依賴** |
| `streamlit` | **1.56.0**（`streamlit.__version__` 實測；`pip install streamlit==1.56.0`） |
| Python | 3.13.17 |
| 其餘（pip 自動解析，**非 repo 的 pin**） | pandas 3.1.0、numpy 2.5.4、pyarrow 26.0.0、tornado 6.6、altair 6.3.0 |
| 瀏覽器 | 沙箱既有 Chromium（`/opt/pw-browsers/chromium-1243`），Playwright 1.63.0（node 全域，未重裝） |
| 手機模擬 | viewport 390×844 / 另掃 320、360、412；`isMobile`、`hasTouch`、DPR 2 |
| repo 守衛 | 系統環境（streamlit 1.59.2）下 `tests/test_macro_v2_tab.py -k TestStreamlitFloorCompatibility` → 3 passed（**這是 1.59.2 的結果，不是 1.56.0**） |

## 2. AppTest 結果（`appttest_floor156.py`，44 列，0 FAIL）

AppTest 只模擬後端 widget state，**不等於前端行為**；前端行為見 §3（Playwright 實跑）。

| API | 行為 | 結果 | 備註 |
|---|---|---|---|
| segmented_control | 無 `default=` | PASS | 回 `None`（radio 則回 `options[0]`） |
| segmented_control / pills | `default="y"` | PASS | 回該值 |
| segmented_control | 選取 → 回選項值 | PASS | |
| segmented_control | **取消選取** | PASS | 回 `None`，**不會**回 `default`（見 §3.1 前端同結論） |
| 回退模式 A：`eff = v if v is not None else last_valid` | | PASS | widget 仍為 `None` |
| 回退模式 B：`on_change` 回呼把 key 寫回 `last_valid` | | PASS（AppTest + §3.1 真瀏覽器） | 首選 |
| key 跨無關 rerun 保持 | | PASS | |
| 該輪未渲染 widget | | PASS（行為＝標準 Streamlit） | key 自 `session_state` 移除；下次渲染回 default |
| `st.form` 內 segmented / pills | 值只在 submit 套用、submit 後取得暫存值 | PASS | |
| `st.form` 內取消選取後 submit | | PASS | 回 `None` |
| `st.form` 內 | proto `form_id` 非空 | PASS | widget 被 form 批次化 |
| form 內 `expander(icon=)` 內放 segmented | 收合時值仍隨 submit 送出 | PASS | |
| `format_func` + str options | 顯示名＝格式化文字、回傳值＝原 key | PASS | |
| tuple options + `format_func`（無 default） | 回傳整個 tuple | PASS | |
| tuple options + `default=<tuple>` | **raise**（tuple 被當成「多個 default」） | PASS（如預期會炸） | 要用 `default=[<tuple>]`；**建議根本不用 tuple options** |
| `label_visibility="collapsed"/"hidden"` | | PASS | |
| `default` 不在 options | raise `StreamlitAPIException` | PASS | fail loud，符合 §1 |
| 空 options | **不 raise** | 資訊 | 空 options 不會被擋 → 呼叫端要自己擋（`single_submit_form` 已有 `ValueError`） |
| 重複 key | raise `StreamlitDuplicateElementKey` | PASS | |
| `session_state[key]` 預先播種、不傳 default | 採播種值 | PASS | |
| 播種 **且** 傳 `default=` | 不 raise、值＝播種值 | 資訊 | AppTest 下有 log warning；**二選一，不要雙重指定** |
| 同 key 但 options 變動（選取值已不在新 options） | 不 raise，**靜默回 default** | 資訊 | options 參與 widget 身分；不得依賴「舊值保留」 |
| radio(horizontal=True) | 選取／取值 | PASS | A 方案對照 |
| `st.badge(color, icon)`、markdown `:green-badge[]` | 無 exception | PASS | 真瀏覽器亦渲染（§3.2） |
| `st.html`（含 `<style>`、`<svg>` 字串） | AppTest 無 exception | PASS | **但前端會剝 svg**，見 §3.2 |
| `st.html(unsafe_allow_javascript=)` | 參數存在 | PASS | 本案不用 |
| `st.metric(chart_data=, chart_type=line/area/bar, delta, border)` | 無 exception | PASS | |
| `st.metric(chart_data=[])` | 無 exception | PASS | 空 list 前端視覺未驗 |
| `st.metric(chart_data=[1,nan,3])` | 無 exception | PASS（**但前端壞**，§3.2） | |
| `st.metric(chart_data=)` 於 form 內 | 無 exception | PASS | |
| `st.bar_chart(horizontal=True, height=)` | | PASS | form 內亦可 |
| `st.line_chart(height=)` | | PASS | |
| `st.expander(icon=":material/..:")`（含於 form 內） | | PASS | |
| `st.container(height=200, border=True)`；`height="content"` | | PASS | |

**AppTest 的已知限制**：(a) `ButtonGroup.set_value(None)` 會被內部 `if self._value is not None` 當成「未設定」而讀回舊值 → 無法模擬取消選取；腳本以 monkeypatch（`_deselect`）送出空 `string_array_value`（與前端取消選取同形）；(b) AppTest 的 `at.expander` 在含 icon 的 expander 回 0 個，故該列只判定「無 exception」，不判定計數；(c) AppTest 證明不了「點擊是否立即 rerun」。

## 3. Playwright 真瀏覽器結果（streamlit 1.56.0 server + Chromium，390×844）

### 3.1 D8 關鍵行為

| 行為 | 結果 |
|---|---|
| form **外**點選項 | 立即 rerun（RUNS 1→2），值更新 ✅ |
| form **外**再點**已選中**的那顆 | **取消選取，回傳 `None`**（即使有 `default=`），並觸發 rerun ⚠️ 同 `st.pills` |
| `touchscreen.tap` 點膠囊 | 值正確更新 ✅ |
| **form 內**點選項 | **不 rerun**（RUNS 6→6），form 值不變；submit 後才套用 ✅ |
| form 內取消選取後 submit | 回 `None` ⚠️ |
| 回退模式 B（`on_change` 回呼把 key 寫回 last_valid；`pw_app4.py`） | 點已選項取消 → **畫面上膠囊立即恢復為原選取、值維持 last_valid** ✅（真瀏覽器驗證） |
| form 內取消選取 → submit 分支以 `None → previous/options[0]` 處理 | 套用值落回 fallback，無 `None` 外洩 ✅（見下「未驗」註） |

### 3.2 版面與尺寸（手機 390 寬；以 `getBoundingClientRect` 量測）

| 項 | 量測 |
|---|---|
| 膠囊按鈕高度 | **32px**（segmented 與 pills 皆 32；**未達 44px**）。對照 `radio(horizontal)` 單列高度 **26px**，膠囊比 A 方案更好點 |
| 膠囊寬度 | 單顆約 48px（1 字）／62–69px（3 字 CJK，如「近1月」「全部」）／104–118px（5–6 字 CJK） |
| 5 顆 × 3 字（「近1月…全部」），form **外**，容器 358px | 390／412 寬：1 列（總寬 334px）；**360／320 寬：換 2 列** |
| 同 5 顆，form **內**（容器 326px） | 390 寬：**換 2 列**（第 5 顆「全部」孤立在第 2 列）；412 寬才 1 列 |
| 5 顆 × 5–6 字 CJK | 390 寬：2 列；320 寬：3 列 |
| 3 顆 × 1 字 | 全寬度 1 列 |
| 橫向溢出 | **0**：320／360／390／412 全部 `documentElement.scrollWidth == viewport`；**超出時換行，不橫向捲動、不裁切** |
| pills 5 顆 3 字 | 390／360 為 1 列（314px），320 為 2 列 |
| CSS 覆寫 `min-height:44px`（`st.markdown(<style>, unsafe_allow_html=True)`，選 `[data-testid="stBaseButton-segmented_control"]`／`...Active`） | **有效**：量到高度 44px，且不造成溢出；⚠️ 依賴 Streamlit 內部 `data-testid`，跨版本可能失效（失效時退化為 32px，不會壞版） |

### 3.3 其他 API 的真瀏覽器行為

| API | 結果 |
|---|---|
| `st.badge(..., color, icon)` | 渲染正常（`.stMarkdownBadge`，高 22px），圖示字型隨 bundle |
| `st.markdown(":green-badge[x]")` | 渲染正常 |
| **`st.html("<svg>…</svg>")`** | ❌ **`<svg>` 被整段剝除**（`#htmlbox` 內只剩文字）。同一 svg 以 **`st.markdown(unsafe_allow_html=True)` 保留**；以 `<img src="data:image/svg+xml;base64,...">` 於 `st.html` 與 `st.markdown` **皆保留** |
| `st.html` 的 `<style>`、行內 `style=`（含 `display:flex`） | 生效（computed color 驗證） |
| `st.markdown(unsafe_allow_html=True)` 的 `<style>` | 生效 |
| `st.metric(chart_data=[1,2,1.5,3], chart_type="line", delta=, border=True)` | 渲染正常（無座標軸、滿寬迷你線；`stMetricChart`） |
| `st.metric(chart_data=[1, nan, 3])` | ❌ **壞圖**：只剩零散點、無折線（無 exception）→ **必須先丟 NaN**（與計畫「sparkline 丟 NaN、⛔ 補 0」一致） |
| `st.bar_chart(horizontal=True, height=180)`／`st.line_chart(height=140)` | 渲染正常 |
| `st.expander(icon=)` | 渲染正常（`stExpanderIcon` 存在） |
| `st.container(height=120, border=True)` | 內容 431px、可視 118px → 內部捲動生效 |
| 全頁 `stException` 數 | 0 |

## 4. 結論：D8=B 成立；使用上的硬性約束

1. **取消選取回退（必做）**：`segmented_control`／`pills` 單選下，點已選項會回 `None`。**每個 caller 必須保證 `None` 不外洩到下游**，二選一：
   - **模式 B（首選）**：key 以 `session_state` 播種（**不傳 `default=`**，避免雙重指定），`on_change` 回呼在值為 `None` 時把 key **寫回 `last_valid`**、否則更新 `last_valid`（真瀏覽器驗證：畫面膠囊立即恢復）。
   - **模式 A**：`eff = v if v is not None else last_valid`；缺點＝畫面膠囊顯示「無選取」而內容顯示 last_valid，視覺不一致，**僅限回呼不便時使用**。
   - 兩者都**不得**用 `fillna`／靜默填一個自編值取代；`last_valid` 必須是**使用者上一次真實選擇**或 options 的**宣告預設**，並可追溯。
2. **form 內處理**：form 內點膠囊**不 rerun**（符合防重繪鐵律），值在 submit 才送出；submit 分支必須同樣處理 `None`（`None → 上一次已套用值 ?? options[0]`）。⚠️ **`single_submit_form` 現行 `st.session_state.get(widget_key, options[0])` 只在 key **不存在**時才落到 `options[0]`；膠囊取消選取時 key 存在且值為 `None`，會寫出 `{"mode": None}`** → 日後若把該 kit 的 radio 換成膠囊，submit 分支須改為「`None` 視同缺值」（本驗證**唯讀、未改該檔**）。form 內的回呼模式 B 無法即時回寫（form 內元件不觸發 `on_change` 回呼直到 submit），故 form 內一律用 submit 分支處理。
3. **最小點擊尺寸**：預設 32px（< 44px）。若須 ≥44px，用 CSS 覆寫 `min-height:44px`（§3.2，已驗證有效、無溢出），並接受它依賴內部 `data-testid`（失效＝退化為 32px，不壞版）。若不覆寫，須在交付報告揭露「膠囊 32px，高於 A 方案 radio 的 26px、低於 44px 準則」。
4. **選項數／字數**：必須容忍**換行**（不橫向溢出、無捲動）。想保 **1 列**：form 外 ≤5 顆×3 字 CJK 於 ≥390 寬；**form 內 ≤4 顆×3 字**於 390 寬；≥5 顆或長標籤（5–6 字）會 2–3 列。設計稿須畫換行態，且 form 內 5 顆會留下孤立的第 5 顆。
5. **選項型別與預設**：options 用 **str key + `format_func`**（顯示名放映射、不拿 key 當畫面字，符合 `single_submit_form` 慣例）；**不要用 tuple options**（`default=<tuple>` 會被當多個 default 而 raise）。`default` 必須在 options 內（否則 raise，這是好事）；空 options 不會被 Streamlit 擋，呼叫端要自擋。options 變動會讓 widget 身分改變、**靜默回 default**。

> **成立的邊界**：上述 5 條全做到 → B 成立。任一條無法做到（例如某處必須允許「無選取」且無合理 last_valid）→ **該處**退回 A（`st.radio(horizontal=True)`，永遠有選取），不需請示。

## 5. 與 `single_submit_form`（`src/ui/views/_ui_kit.py`）的相容性（只讀碼分析）

- 現行：`st.form(form_key)` 內一組 `st.radio(options, format_func=lambda k: option_labels[k], key=widget_key, horizontal=True)`，submit 後 `st.session_state[applied_key] = {"mode": st.session_state.get(widget_key, options[0])}`。
- **API 層相容**：`options`（str）／`format_func`／`key`／`label_visibility` 在膠囊皆可用；form 內不即時 rerun 的結構不變；`options_label` 的 form 內 expander 路徑 AppTest 驗證可用。
- **語意層不相容（需改）**：(1) `radio` 永遠有值、膠囊可為 `None`（§4 約束 1、2）；(2) `radio` 無 `default=` 時取 `options[0]`，膠囊需顯式 `default=options[0]`（或播種 key）；(3) 上述 `.get(widget_key, options[0])`。**這些是「換元件時要改」，不是「現況有 bug」**——現行 radio 路徑不受影響。
- 本驗證未改 `_ui_kit.py`；既有 4 個 caller（`page_today`／`page_hold` 直接呼叫；`page_find`／`page_inspect` 為自有 form）未動。

## 6. 誠實揭露：限制與未驗項

- **模擬非實機**：手機驗證為 Chromium 行動模擬（viewport／`isMobile`／`hasTouch`）；**未在 iOS Safari／Android Chrome 實機驗證**；觸控「命中面積」只量元素尺寸、未做 iOS 對 32px 目標的誤觸統計。
- ~~**只跑 1.56.0**：本驗證的結論**只對 1.56.0**。`st.html` 剝 `<svg>` 在 1.57–1.59 是否改變**未驗**（若新版不剝，`sparkline_svg` 在 floor 與 latest 會**行為不一致**，反而更要以 floor 為準）。~~
  **📌 2026-10-30 QA 輪更正（有意識的更正，不是漏刪）**：**1.59.2 亦實測相同**——取消選取回 `None`、`st.html` 剝行內 `<svg>`（QA 於系統環境 streamlit 1.59.2 實跑）。**1.57～1.58 仍未驗**（floor 1.56.0 與 1.59.2 兩端一致，中間版本行為變化的可能性低但未證實）。原句「若新版不剝會不一致」的疑慮在 1.59.2 不成立；`sparkline_svg` 不經 `st.html` 的規則兩端皆適用。
- **依賴版本非 repo pin**：venv 的 pandas／numpy／pyarrow 為 pip 自動解析值，與 repo `requirements.txt` 的 pin（如 pyarrow 24.x、starlette 1.3.x）不同；影響膠囊／metric 行為的機率低，但**未用 repo 完整依賴組合驗**。
- **未驗**：repo 真實頁面（`page_today` 等）在 1.56.0 下的整頁行為（本驗證只用最小 app）；`metric(chart_data=[])` 的視覺；深色主題下膠囊對比；表單 submit 後膠囊焦點／鍵盤操作；Streamlit Cloud 部署環境。
- **form 內取消選取＋submit 的回退**只驗到「值不外洩 `None`」；因該輪預設選項恰被我點掉，**無法區分「落回上次套用值」與「落回 options[0]」**（兩者在該測例同值 `'a'`）。
- **AppTest 以 monkeypatch 模擬取消選取**（§2 限制 a）；真取消行為以 §3.1 Playwright 為準。
- `TestStreamlitFloorCompatibility` 僅在系統 1.59.2 環境跑過（3 passed）；**未於 1.56.0 venv 跑**（venv 無 repo 依賴、也不該裝）。
- ~~本檔結論為**單組實測，未經第二組獨立複驗**（CLAUDE.md §-2 規則 6）；承重結論（§4 約束 1 的取消選取行為、§3.2 的 `st.html` 剝 svg）建議由總管另派一組以同腳本重跑複驗後，才作為 caller 設計前提。~~
  **📌 2026-10-30 QA 輪：已有獨立重現註記**——兩組 QA 獨立重跑（含 1.59.2），承重結論（取消選取回 `None`、`st.html` 剝 `<svg>`、`st.markdown(unsafe_allow_html=True)`／data-URI `<img>` 保留）**重現一致**（回報轉錄，本檔作者未自行重跑）。⚠️ 重現範圍＝floor 1.56.0（原驗）＋1.59.2；1.57～1.58 未驗；仍非實機、非 repo 完整依賴組合。

## 7. 重現

```bash
python -m venv /tmp/v156 && /tmp/v156/bin/pip install streamlit==1.56.0
/tmp/v156/bin/python tools/phase3_verify/appttest_floor156.py        # AppTest，應見 SUMMARY 44 rows; 0 FAIL
# Playwright（node 全域 playwright + 既有 chromium）：先啟 app 再量測
/tmp/v156/bin/streamlit run tools/phase3_verify/pw_app.py --server.port 8561 --server.headless true &
NODE_PATH=<global node_modules> PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node tools/phase3_verify/pw_measure.js http://localhost:8561 shot.png
# pw_app2（svg／style／img 渲染）、pw_app3（44px CSS 覆寫，配 pw_sweep.js 掃寬度）、pw_app4（回退模式，配 pw_fallback.js）
```
