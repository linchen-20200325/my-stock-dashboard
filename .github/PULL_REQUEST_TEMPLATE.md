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

## 風險評估

<!--
LOW / MED / HIGH。HIGH 風險 PR 必須:
- 寫 rollback plan
- 補 regression test
-->

🤖 Generated with [Claude Code](https://claude.com/claude-code)
