# `docs/v2/wireframe/` — 線框稿**原始碼**（成品在 Artifact，來源在這裡）

> 先讀 `../README.md`（整批的索引與全域限制），再讀本頁。

---

## 0. 三十秒版本

- **已發布的互動線框成品在 Artifact 上**，那份是安全的，不會隨暫存容器消失。
- **但來源檔會消失** —— 所以它們在這裡。
- **組裝產物 `warroom_ia_v2_full.html`（866 KB）刻意不入庫**，
  因為它可以從本目錄的檔案**完整重建**（下方 §2 有實測驗證）。
- ⚠️ **線框稿 ≠ 已核准的畫面。** 依 `CLAUDE.md §-1.5`（v3 §03-2 ①）
  版面佈局／欄位增減／分頁動線異動**必須先出線框送客戶拍板**；
  線框本身就是**送審用的草稿**，不是拍板結果。

---

## 1. 檔案在這個結構裡各是什麼

| 角色 | 檔 | 說明 |
|---|---|---|
| **外殼** | `warroom_ia_v2.html` | 渲染器 ＋ CSS ＋ 互動邏輯。**不含線框資料**（資料靠組裝注入） |
| **資料（每頁一支）** | `wf_page_today.js` `wf_page_find.js` `wf_page_inspect.js` `wf_page_hold.js` `wf_page_why.js` `wf_page_fund.js` | 純資料，`push` 進 `window.WF_PAGES` |
| **資料（跨頁）** | `wf_global.js` `wf_questions.js` | 全站區塊／問題清單，同樣 `push` 進 `window.WF_*` |
| **資料（未組裝）** | `wf_onboarding.js` | ⚠️ **不在組裝清單裡** —— 見 §3 |
| **組裝腳本** | `assemble.js` | **自 scratchpad `_assemble2.js` 原樣複製，未改一個字**。沒有它就重建不出來，故破例入庫 |
| **說明文件** | `S1-3_IA_WIREFRAME.md` `S1-3B_FULL_DRAFT_SPEC.md` `UI-B_wireframe.md` `UI-C_wireframe.md` `UI-E_page3_wireframe.md` | 文字線框與內容規格（**不是視覺稿、不含前端代碼**） |

⚠️ **一個會讓人看錯的命名**：`wf_page_fund.js` 宣告的頁面 **`id` 是 `rebalance`**，**不是 `fund`**。
檔名是歷史殘留（客戶 2026-09-15 第二次明示「移除基金」），內容已是**再平衡**頁。
移出畫面的基金相關紀錄封存在 `../audit/wf_fund_archive.md`。

---

## 2. 重建步驟（**本組已實測，逐位元相符**）

環境：本組驗證時用 **Node v22.22.2** ＋ **Python 3.11.15**（`assemble.js` 只用 `require` / `fs`，無外部套件）。

```bash
cd docs/v2/wireframe
```

### 步驟 1 — 組裝資料 bundle

```bash
node assemble.js
```

產出 **`_wf_bundle.js`**（本組量測 711,729 bytes，量測日 2026-09-15）。
腳本本身會印出契約健檢結果，正常應為：

```
頁面: today(8) find(14) inspect(22) hold(23) why(22) rebalance(18) global(15) questions(18)
區塊合計 140｜決策 22｜偏離 29｜限制 31
✅ 契約健檢全過
```

> `assemble.js` 除了合併，還做兩件**機械正規化**（它自己的註解寫明「不動內容」）：
> ① 沒給 `layers` 只給 `blocks` 的頁包一層 `layers`；② 依固定順序排頁、對撞名的 `block.key` 加頁前綴。
> 它**只回報**契約缺漏（缺狀態欄、缺 `cols`），**不修改內容**。

### 步驟 2 — 把 bundle 注入外殼

在同一個目錄執行：

```bash
python3 - <<'PY'
import io
shell  = io.open('warroom_ia_v2.html', encoding='utf-8').read()
bundle = io.open('_wf_bundle.js',      encoding='utf-8').read()
anchor = 'window.WF_DEVIATIONS = [];\nwindow.WF_LIMITS = [];\n'
assert shell.count(anchor) == 1, 'anchor count = %d' % shell.count(anchor)
io.open('warroom_ia_v2_full.html', 'w', encoding='utf-8').write(
    shell.replace(anchor, anchor + bundle + '\n'))
print('OK')
PY
```

產出 **`warroom_ia_v2_full.html`** —— 單一檔、可直接用瀏覽器開啟。

### ✅ 實測驗證（本存檔組，2026-09-15）

照上面兩步重建出來的 `warroom_ia_v2_full.html` 與**當時已組裝好的那一份**
（scratchpad 內 866,671 bytes）**逐位元相同**：

```
sha256 = 5c2f8a478105a1a6a2e858af5c022bdee899c7f5169be82b62626151c4ba1350
```

⚠️ **這個 sha256 只對「當下這批來源檔」成立。** 任何一支 `wf_*.js` 或外殼被修改後，
重建結果就會不同（**那是正常的**）—— 它證明的是「**重建路徑正確、沒有遺失的隱藏步驟**」，
**不是**「以後每次重建都該得到這個值」。

⚠️ **`_wf_bundle.js` 與 `warroom_ia_v2_full.html` 都是派生物，不要 commit。**
（`_` 開頭的產物本來就不該入庫；`warroom_ia_v2_full.html` 刻意不入庫的理由即上述可重建性。）

---

## 3. ⚠️ `wf_onboarding.js` —— 它**不在**已發布的成品裡

**實測事實（不是判斷）**：

- `assemble.js` 的 `FILES` 清單**只有 8 支**（today / find / inspect / hold / why / fund / global / questions），
  **不含 `wf_onboarding.js`**；
- 因此已發布的 `warroom_ia_v2_full.html`（sha256 見上）**不含**「🧭 第一次使用」這一頁；
- 本組另做對照實驗：把 `wf_onboarding.js` 加進 `FILES` 後重組，得到
  **9 頁 / 146 區塊**（多出 `onboarding(6)`），與已發布版本不同。

⛔ **本組沒有判斷「這是遺漏還是刻意」** —— 那需要回查該頁的決策紀錄，屬新增查證，超出存檔範圍。
✅ **要把它納入成品的話**：這是**新增一個分頁**＝分頁動線異動，
依 `CLAUDE.md §-1.5`（v3 §03-2 ①）**必須先出草稿送客戶拍板**，
且依 `§-1` **沒有客戶指派就不要動工**。

---

## 4. 修改線框稿時的紀律

1. **改資料就改 `wf_*.js`，不要改組裝產物。** 產物是派生的，改了會被下次重建蓋掉。
2. **改外殼（渲染器 / CSS）就改 `warroom_ia_v2.html`。**
   ⚠️ 注入錨點 `window.WF_DEVIATIONS = [];` ＋ `window.WF_LIMITS = [];`（相鄰兩行）
   **必須維持全檔唯一** —— 步驟 2 的 `assert` 就是在守這件事。
3. **`assemble.js` 是原樣複製品。** 要改它請先確認不是在「順手優化」
   —— 它現在的行為（機械正規化 ＋ 只回報不修改）是已驗證過的。
4. **線框改完要送客戶拍板才准寫 UI code**（`CLAUDE.md §-1.5.A-8` ＋ v3 §03-2 ①）。
   唯一的例外是 **UI bug 修復**（把壞掉的畫面修回它本來就該長的樣子），
   那不算「改變設計」—— 判準見 `CLAUDE.md §-1.5.A-8`。
