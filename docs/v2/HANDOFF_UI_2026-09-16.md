# 交接索引 — UI 設計與原型（2026-09-16 session）

> ⚠️ **本檔由 AI 總管自己寫，未經第二組複驗**（§-2 規則 6）。
> 為降低 token 用量（客戶當下使用量將盡）刻意未派工。
> **本檔不含任何新結論** —— 每一條都指向一個已 commit 的產出，
> 真正的依據與複驗分級**寫在各該 commit message 與各該檔案的「複驗分級」段**，
> ⛔ 請以那些為準，不要把本索引當前提。

## 分支現況
- 開發線：`claude/stock-dashboard-handoff-g9dtm0`（**已全部 push，工作區乾淨**）
- `v2` ＝ `8f4a060`｜`main` ＝ `5808c03`（§-1.2 分支政策：v1 凍結於 main、v2 開發於 v2 分支）
- ⚠️ 開發線的內容**尚未合併進 `v2`**。

## 本 session 產出（11 個 commit，全部零 `.py` 變更）

| commit | 產出 |
|---|---|
| `2e9fc36` | `UI_PAGE_TODAY.md` — `today.verdict` 形狀結案 |
| `25a1426` | `UI_PAGE_FIND.md` — 第 4 份 找標的頁 |
| `9b2812d` | 推翻「結果表保留原始值本益比欄」 |
| `fa351a1` | 紅隊 17 項發現收斂（→145 行）|
| `80c35da` | `--ink-3` 卡面對比 AA 修正（六格三格 FAIL → 全 PASS）|
| `9bd2ef5` | 客戶三件裁示落地 |
| `0b74191` | `UI_PAGE_INSPECT.md` — 第 5 份 查一檔頁 |
| `e3b41bd` | `UI_PAGE_HOLD.md` — 第 6 份 我的持股頁 |
| `2efef3b` | 客戶六件裁示落地 |
| `0d8a709` | `UI_PAGE_WHY.md` — 第 7 份 為什麼頁 ＋ 更正 INSPECT 一項誤判 |
| `d21d1ca` | `docs/v2/prototype/ui_prototype_today.html` — 今天頁視覺原型 |

**七份 UI 設計已齊**：`UI_TOKENS.md`／`UI_COMPONENTS.md`／`UI_PAGE_TODAY.md`／
`UI_PAGE_FIND.md`／`UI_PAGE_INSPECT.md`／`UI_PAGE_HOLD.md`／`UI_PAGE_WHY.md`（皆在 `docs/v2/spec/`）。

## 下一步（客戶已表明的路線）
1. **客戶確認今天頁原型的視覺方向** ← **停在這裡**
2. 確認後：其他四頁的 HTML 原型
3. 再下一輪：進 Streamlit 實作

## 等客戶裁示的開放項（⛔ 未決，不得逕自決定）
- **`today.verdict` 的 `exposure`／`regime` 兩卡去向** —— 客戶只說「不搬」，未說刪（`2efef3b`）
- **AI 問答無金鑰的落點** —— 規格要求「本頁就地顯示設定入口」vs 線框「不在畫面上收憑證」（`0d8a709`）
- **原型 `#9` 徽章的刻意偏離** —— summary 卡頭畫 `◧ 1／3 計入`，但規格規定 fail-safe 恆降級 `#7`（`d21d1ca`）

## 已登記、尚未動工的待修（受 §-1 拘束：無指派不主動動工）
- 實作端結論三卡 label 待改（`page_hold.py:1671`）；線框 26 處 `▨` 與兩塊四段斷點待同步（`2efef3b`）
- `D-08` 本益比兩種「沒有」需 L1 補旗標 ＋ **排序端必須同批擋非正值**（否則虧損股排名第一）（`fa351a1`）
- `D-2` 成本口徑逐字文案：**L1 未補前不得放**（`2efef3b`）
- 查一檔頁：5 指標只有 3 格、`on_select` 未落地（`0b74191`）
- 為什麼頁：葉1 四張教學卡實跑三張為 unwired／degraded，與「這頁沒有灰態」不符（`0d8a709`）

## 給下一個 session 的三條方法論（本輪實證，非空談）
1. **不得拿註解／docstring 當實作事實** —— 本 session 撞到三次（`page_inspect.py:50`、
   `page_hold.py DEEP_CAPTION` 同段自相矛盾、`page_why.py _render_edu_leaf` docstring）。
2. **能執行就不要用讀的** —— 為什麼頁最關鍵的發現是直接跑 `build_edu_cards()` 得到的；
   原型的三斷點是用 Chromium 實際渲染量測的（`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`，
   ⛔ 不要跑 `playwright install`）。
3. **調查與稽核要派多組、且不可自己查自己** —— 本 session 有四次是獨立組推翻了總管或前一組的
   結論（`0.00` 恆不觸發、streamlit 斷點反引號、`try` 13 vs 14、頁尾誤判）。
