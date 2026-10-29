<!-- v18.402 PR template — 對齊本專案 commit message 風格 + CLAUDE.md 治理 -->

## Summary

<!--
本 PR 在做什麼?用 1-3 句講「改了什麼 + 為什麼」(不是「改了哪些檔」)。
範例:
- 修 §十一 News AI render NameError(D-12 抽 trio 後 _macro_info 變數懸空,5 commit 沒抓到)
- §3.3 反捏造:reconcile health weights 對齊 macro_helpers SSOT(原 inline 0.4/0.4/20)
-->


## §-1 工作準則對齊

<!-- 勾選或留空 -->
- [ ] user 主動指派
- [ ] 真實 bug 觸發(寫出 reproduce)
- [ ] 既有功能維護(security / 依賴升級)
- [ ] 其他:______

## SSOT / §8.2 / §3.3 影響

<!--
本 PR 是否涉及:
- 新增 SSOT 常數? 抽到哪裡?
- 新增 §8.2.A 例外? 是否登錄表?
- 新增 inline magic number? 為何不抽 SSOT?
不涉及 → 寫「無」
-->


## Test plan

- [ ] pytest 全綠(列出 case 數變化:before / after)
- [ ] 新增 test(可選):防止此 PR 修的 bug 再犯
- [ ] Streamlit 实機驗(slow lane / user 端):______

## §6 自審 checklist(挑相關項目)

<!-- 對齊 CLAUDE.md §6 11 項自審清單 -->
- [ ] 無 fillna(0) / 沉默 ffill / except:pass
- [ ] 量綱一致(% vs ratio / TWD vs USD / YoY vs MoM)
- [ ] 無 lookahead(release_date vs observation_date)
- [ ] 浮點比較用容差(math.isclose / np.isclose)
- [ ] 向量化,無隱性逐列迴圈
- [ ] 不變量斷言(OHLC / date monotonic / 權重和=1)
- [ ] N/A(本 PR 純文件)

## Visual Fidelity Gate（UI PR 必填；非 UI PR 寫「N/A：理由」）

<!--
2026-10-29 新增（客戶 DEC-109；PROJECT_RULES.md 第 24 節；docs/governance/UI_VISUAL_FIDELITY_GATE.md）。
CI / QA / tests / mutation 全綠 ≠ UI Stage complete；明顯偏離 blueprint＝Visual Fidelity FAIL，不得標 complete。
截圖：desktop 1440×900＋mobile 390×844；第一屏＋全頁；冷啟動＋已載入；單張 < 300KB；工具 tools/visual_fidelity/。
-->
- [ ] N/A（理由：______）
- [ ] 已附截圖（desktop 1440／mobile 390；第一屏＋全頁；冷啟動＋已載入）：______
- [ ] blueprint 並排（docs/vnext/d25_wireframes/<page>.html）：______
- [ ] 三層寫得出：第一眼＝___；第二眼＝___；第三層＝___
- 資料來源（夾具／真資料）＋ Streamlit 版本（1.56 floor 是否實驗）：
- 客戶 11 項（✅／🟡／❌）：A1 第一屏結構 _｜A2 Primary 突出 _｜A3 圖文比例 _｜A4 卡片密度 _｜A5 空白比例 _｜A6 圖表大小 _｜A7 Top-N _｜A8 文字下沉 _｜A9 Missing placeholder _｜A10 CTA／行動首屏 _｜A11 mobile 不被塞滿 _
- 補充 V1～V11（Primary 數／Secondary 數／首屏數字 chip 數／主判讀句數／禁止清單／五問／三層／chip 文字化／Missing 符號／工程字樣／手機無 hover 依賴）：
- 判定 PASS／FAIL；判定者（獨立 QA 組）／總管複驗項：
- 偏離與處置／未驗（手機實機、Streamlit Cloud、1.56 floor）：

## 風險評估

<!--
LOW / MED / HIGH。HIGH 風險 PR 必須:
- 寫 rollback plan
- 補 regression test
-->

🤖 Generated with [Claude Code](https://claude.com/claude-code)
