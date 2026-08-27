# VIX 誠實化（資料工程組）工作紀錄

⛔ 邊界：**不改任何 VIX 門檻數值**（user 2026-06-26 已撤銷過「harmonize 統一值」）。
本輪只修「文件說謊」與「死參數／死碼沒標明」。

## 0｜基線（動工前）
- fast lane 7031 passed / 17 skipped；slow lane 45 passed / 5 skipped。
- 實跑：classify_danger 15~21 全 green、22~29.9 yellow、30+ red；
  vix_veto_cap 24.9 / 25 / 25.1 輸出**完全相同**（25 不是任何一刀）。

## 1｜allocation_decision.vix_veto_cap 假 SSOT ✅ fb31a20
判定：**註解誤引**（不是漏實作）。25 是 v4_strategy_engine 的持股上限門檻，
語意不同；`>=20` 分支自己印的字就是「進入 20–30 警戒帶」＝兩刀設計。
處置：刪幻影 25 + 真 import 兩個 SSOT。10 個取樣點輸出逐字相同。
一處刻意寫法：警戒帶字串收成 module-level 具名常數，避開 test_p0b_spec_wiring
的 en-dash AST 守衛（第一版寫 inline f-string 時該守衛實測紅燈）——不去守衛上開洞。

## 2｜section_mid 假 SSOT ✅ 68331c4
同一張圖裡 add_danger_hlines 讀 SSOT 畫線、標題文字用字面值 → SSOT 一改就自打嘴巴。
處置：改讀 SPECS_BY_KEY['vix']（與畫線同一個 spec 物件）；順帶收掉「待取得」KPI 副標。
四個邊界點判燈與本版前完全一樣。

## 3｜MACRO_THRESHOLDS['VIX']['green_below']=18 死參數 ✅ 66855e4
四項可否證檢查全部重驗通過。依指派**不刪**（對外 schema 契約），改為加註 + 釘守衛。
~~⚠️ **要轉給憲法組**：CLAUDE.md §3.2 把 VIX 的 18 列在範圍表上 → 讀憲法的人會以為~~
~~「全站綠線是 18」。~~ **← 2026-08-27 更正，有意識的修改，不是漏刪。**
這句是本組自己沒查證就寫下的。實地讀過 `CLAUDE.md` §3.2 後確認：範圍表的 VIX 那列只寫
`| VIX | [5, 100] | macro_core.py:215 thresholds |`，**並沒有列 18**
（全檔 grep `green_below` / `全站綠線` 皆 0 命中）。這句錯誤宣稱的**來源尚未查證** ——
總管轉述時提過可能出自 `stock_truth_spec.md`，但**該檔在本 repo 內找不到**
（`find . -name "stock_truth_spec.md" -not -path "./.git/*"` → 0 命中），
故**出處歸屬未經證實，不得引用為事實**。
**要轉給憲法組的真正內容**是這個事實本身：**`green_below=18` 是死參數、全站綠線並不是 18**——
而不是「憲法列錯了」。本次未動 CLAUDE.md 一個字。
⚠️ 本次更正的第一版**又夾帶了一個未查證的出處歸屬**，由執行組實測 `find` 0 命中後指出。
**兩次都是同一種病** —— 用轉述當事實。留此紀錄。

## 4｜classify_short_term_regime 死碼 ✅ ce8c551
五種查法（原文 grep 不限副檔名 / AST 掃 363 個 production .py / barrel PEP 562 /
動態呼叫向量 / 死因考古 v18.190）→ 確認 0 production caller，刪除。
它藏著本 repo 第 8 套 VIX 門檻（15/20/25/30）。
⚠️ 超出指派檔案清單一處：section_long_term.py:37 那行指向它的註解一併改掉
（不改就是用刪除製造一句新的假話）。

## 收尾（乾淨 worktree @ ce8c551，不含另兩組在飛的改動）
- fast lane：**7079 passed, 17 skipped, 49 deselected**
- slow lane：**47 passed, 5 skipped, 7093 deselected**
- ruff：各檔錯誤數與 HEAD 完全相同；新測試檔 tests/test_vix_honesty.py 全綠。
