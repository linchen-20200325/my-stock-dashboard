# 修 shared/position_throttle.py 假引用（資料工程組）

## 1. 查證結果（實測，非轉述）

### 現行常數（`shared/position_throttle.py`）
| 常數 | 實際值 | 行 |
|---|---|---|
| `THROTTLE_HEALTH_A` | **70** | 51 |
| `THROTTLE_HEALTH_B` | 50 | 84 |
| `THROTTLE_HEALTH_DEF` | 35 | 85 |

**掃描組寫 70 = 正確。行內註解寫 65 也不是錯的 —— 兩者描述不同階段：**
- L20（2026-08-19）：第一次調整 `80 → 65`（尺度借用錯誤修正，user 核准）
- L53（同日下午）：第二次調整 `65 → 70`（`M1B_M2_LEG_ENABLED=False` 讓 health 分布右移，P90 由 65.6 → 70.5）
- 兩次都在同一個 commit `ff5f00d` 落地 ⇒ **終值 70**，L20 的「65」是中途值、不是現值。
  ⚠️ 這本身是可讀性陷阱：L20 的大標題只寫「自 80 改為 65」，讀者不往下讀 33 行不會知道已經再改成 70。

### 三重錯誤複查
1. ✅ **數字錯**：docstring L9 寫「健康分界 80」，實際 `THROTTLE_HEALTH_A = 70`。
2. ✅ **零 import**：全檔唯一 import 是 `from __future__ import annotations`。
   L18 自陳「此處複寫值而非 import…**以註解釘一致**」—— 但沒有任何測試釘它。
3. ✅ **同檔自我推翻**：L20-26 明文「舊值 80 註解寫『對齊 HEALTH_GRADE_A_MIN』，但那是個股六因子健康分的 A 級線」，
   直接推翻 L9-10 的 docstring。

### 出處（git blame）
- docstring L8-11：`7d76267`（2026-08-11），寫的時候 A **確實**是 80 → 當時正確。
- 常數改動：`ff5f00d`（2026-08-19 19:53），80→65→70，**docstring 未同步** ⇒ 假引用自此產生。

### 尺度不同的實證（引用自檔內既有推導 + 交叉查證）
- `HEALTH_GRADE_A_MIN=80`（`shared/health_thresholds.py:19`）；該檔 docstring **自己明文禁止**跨尺度借用
  （「本模組僅收個股健康度評分 0~100 …不收市場曝險…那些屬不同維度」）。
- 該常數所有 production consumer 皆為**個股**評分路徑：`scoring_helpers.py:281`、`stock_buckets.py:164`、
  `unified_verdict.py:25` —— `position_throttle`（總經）是唯一的例外，也就是唯一的誤用。
- 總經 health ≡ 29.8 + 0.4×score_pct，值域被壓成 [21.6, 78.1] ⇒ 照 80 切，「積極」帶 4,769 個交易日 **0 次觸發**。

## 2. 追加發現（任務第 4 點：同檔其他矛盾）

- **F-1（真矛盾）**：`THROTTLE_HEALTH_B` L84 註解「對齊 `HEALTH_GRADE_B_MIN`」＝**與 A 完全同源的尺度借用**，
  只是還沒被抓到。L22-26 才剛宣告該借用非法，L84 又照做一次 ⇒ 檔內自我矛盾。
  ⛔ 依指示**不動常數值**；改為誠實標註「數值巧合、非有效背書」，並留待另案校準。
- **F-2（單位陷阱）**：docstring L11 / L88 寫「對齊 EXPOSURE_BULL/NEUTRAL/BEAR(80/50/20,config.py)」，
  但 `src/config/config.py:70-72` 存的是**比例** `0.80/0.50/0.20`，本模組用**百分比**。差 100×（§4.1 量綱陷阱）。
- **F-3（測試 false-green）**：`tests/test_position_throttle.py::test_boundary_values_align_ssot` 註解寫
  「恰在分界:80 → 積極」並斷言 `compute_position_throttle(80)['posture'] == '積極'`。
  A 改 70 後，80 **不再是分界**（80 只是帶內任一點）⇒ 該案例名為「boundary」實際已不測 A 的邊界。
  斷言仍綠 ⇒ 典型 false green。
- **F-4（可讀性，不改）**：L20 標題只寫「80 改為 65」，現值 70 在 33 行之後。已於新 docstring 就地指路。

## 3. 處置
- 改 docstring（只改文件，**零常數變更**），保留追溯：曾寫什麼、何時、為何改、user 核准。
- 加守衛 `tests/test_position_throttle_docstring_honesty.py`（設計見下）。
- 修 F-3 的 false-green（補真正的 A 邊界斷言；不動常數）。

## 4. 守衛設計（`tests/test_position_throttle_docstring_honesty.py`，6 條）

| 層 | 測試 | 釘什麼 | 擋哪種失效 |
|---|---|---|---|
| L1 | `test_docstring_declared_values_match_constants` | docstring 內 machine-readable 行 `現行健康分界:A=70 / B=50 / DEF=35` regex 抽值 == 實際常數 | **本次事故成因**：常數動了、文件沒動 |
| L2 | `test_throttle_a_must_not_be_realigned_to_health_grade_a_min` | `THROTTLE_HEALTH_A != HEALTH_GRADE_A_MIN` | L1 擋不住「**兩邊一起改回 80**」的好心收斂；L2 釘**值**不釘措辭，改寫註解繞不過 |
| L3 | `test_docstring_never_asserts_a_aligns_...` | docstring 內凡提及 `HEALTH_GRADE_A_MIN` 的行必須帶否定/說明標記 | 那句肯定句以任何形式被寫回來 |
| L4 | `test_docstring_keeps_the_scale_explanation` | docstring 必須含「個股六因子」「不同尺度」 | 只把數字改對、刪掉理由 → 下一個人還是會去對齊 |
| — | `test_docstring_pct_band_claim_matches_tiers` | 持股帶 80/50/20 宣稱 == `THROTTLE_TIERS` | 同一種腐爛方式換個欄位再來一次 |
| — | `test_def_cut_really_aligns_with_defense_threshold_default` | `THROTTLE_HEALTH_DEF == HEALTH_DEFENSE_THRESHOLD_DEFAULT` | 三個切點裡**唯一的真對齊**脫鉤 |

⚠️ **刻意不釘 `THROTTLE_HEALTH_B == HEALTH_GRADE_B_MIN`** —— 那會用測試把同一個尺度借用錯誤**固化**。
已在測試 docstring 明文寫「請不要順手補上這條 pin」。

### 突變測試（兩發，皆轉紅）
- **M1 把舊 docstring 放回去** → `4 failed, 2 passed`（L1/L3/L4 + 持股帶宣稱）。
- **M2 常數與 docstring 一起改回 80**（模擬「恢復對齊」，L1 因同步而通過）→ `1 failed, 5 passed`，
  由 **L2** 攔下。⇒ L1、L2 各自守到不同的失效模式，兩者皆非冗餘。
- 兩發之後還原，重跑皆綠。

## 5. 兩條 lane
- `python -m pytest -q` → **7144 passed, 17 skipped, 49 deselected**（4:19）
- `python -m pytest -q -m slow --tb=short` → **47 passed, 5 skipped**（27s）
- ⚠️ 首跑曾出現 1 紅：`test_macro_classroom.py::TestTabMacroWiring::test_explainer_after_traffic_light_render`。
  **非本次改動所致**：該測試 runtime 讀 `src/ui/tabs/macro/section_state.py`（我的⛔禁區）原始碼字串，
  該檔 mtime 16:14:37 落在我那 4:24 的 suite 執行區間內 —— **別組 agent 併發寫入**造成的競態。
  以「還原我的改動 → 該測試綠 / 放回我的改動 → 該測試仍綠 / 重跑全 suite → 全綠」三步排除。

## 6. ⚠️ commit 撞車（據實揭露，非我方失誤但必須記錄）

我的三個檔案**已進入 `a76efe8`（16:23:32，標題「真故障被說成「你還沒點」…」）**，
但**那不是我開的 commit**：本 worktree 的 git index 為多組 agent 共用，
另一組在 16:23 執行了**不帶 pathspec** 的 `git commit`，把當時 index 內所有檔案
（含我剛 `git add` 的三個）一起掃進他們的 commit。我隨後的 pathspec commit 因此回報
`nothing added to commit`。

**已驗證內容完好**：`git show HEAD:<file>` 對三個檔案逐一 diff 我的本地版本 → **全部一致**；
`THROTTLE_HEALTH_A/B/DEF = 70/50/35` 未被更動。

**後果（要讓總管知道）**：我寫的 commit message（含問題描述、git blame 成因、突變測試結果）
**沒有落地**，`a76efe8` 的訊息完全沒有描述本次 docstring 修正 —— 對後人而言，
這個修正在 history 上是「藏在一個講別的事的 commit 裡」。

**我沒有做的事（刻意）**：不 amend、不 rebase、不改寫 `a76efe8`
—— 那會改寫別組 agent 的 commit，且逾越我的檔案邊界。
改以本檔（doc-only）補上完整理由並指回 `a76efe8`，把可追溯性補回來。

## 7. 更正上一節（§6 已過時，不刪、就地更正）

§6 寫「內容已於 `a76efe8` 落地」—— **該敘述在寫下後隨即失效**，據實更正：

1. 16:23 別組 agent 的無 pathspec commit `a76efe8` 掃入我的三個檔案（§6 所述，屬實）。
2. 我隨後 commit `4fc0c63`（scratchpad）。
3. **之後別組 agent 改寫了歷史**：`a76efe8` 已不在分支上（`git merge-base --is-ancestor` 為否），
   被同標題的 `d43292a` 取代，而**該重寫把我的三個檔案從 branch 上拿掉了** ——
   HEAD 版 `shared/position_throttle.py` 一度回到 line 9 的假引用原文。
   ⚠️ 工作區檔案未受影響（三檔逐一 diff 我的備份 → 完好），所以無資料遺失。
4. **處置**：重新以 pathspec 提交我的三個檔案為 **`fb7f695`**（我自己的 commit message）。
   已驗證 HEAD 版三檔與我的版本逐檔一致、常數 70/50/35 未動、24 tests 綠。

**現行有效 commit：`fb7f695`**（§6 提到的 `a76efe8` 已不存在於分支，請勿再引用）。

📌 **方法論教訓（值得寫進總管的併發規則）**：多組 agent 共用同一個 worktree 與 git index 時，
`git add` + 無 pathspec `git commit` 會互相掃檔，且**後續的 amend/rebase 會靜默移除別組已提交的檔案**。
本次是靠「提交後回頭 `git show HEAD:<file>` 逐檔比對」才發現，
若只看「commit 成功」就收工，這個修正會在毫無徵兆下消失。
⇒ **併發情境下，commit 之後必須再驗一次 HEAD 內容，commit 成功不等於改動還在。**
