# New UI2 Active Presentation Contract｜v1.0 核准產品目標對齊差額（docs-only）

**版本**：`UI2-ONEBRAIN-PRODUCT-V1.0-APPROVED-2026-11-23`；**狀態：DIFF / NOT A CONTRACT OVERRIDE**。客戶已核准產品目標，**並非授權直接修改 Active Presentation Contract、FieldVM、新 UI 文案／規則／來源**。本文件可作各 owner 對帳入口；遇衝突沿用**當前有效** DEC/Contract 並在既有 Gate 補核准。依 [DEC-224](../DECISIONS.md)、[完整 v1.0](UI2_ONEBRAIN_FULL_PRODUCT_SPEC_V1_0_2026-11-23.md)、[核准證據](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7110182570)。

| 位置/議題 | 當前仍應遵守的有效邊界 | v1.0 新產品目標差額 | Owner / Gate |
|---|---|---|---|
| 五頁與 390 首屏 | 不擅動 navigation／PageVM／原已通過視覺證據；Real/FAKE 隔離。**現行 📊 順序（DEC-157）＝日 K 主圖／空槽 → 核心指標卡 → OneBrain Outlook**（取代 DEC-133 G-3 僅 OneBrain 位置；Active §3.1 該列文字仍為舊序、原文保留）。**Active §3／DEC-130**：📊🎯💼 無完整 evidence expander，👤 稽核入口預設收合；**DEC-209 例外僅 🗂 Real 資料頁「各項明細」** | 📊/💼 Delta Strip，三核心狀態及 OneBrain 四鏡頭；先做 390/1280 線框。**OneBrain 移首屏、「證據預設展開」為新目標，與現行契約不同**；保留「完整證據可追溯」與新首屏目標 | B 只做線框/視覺與 Copy Gate，不直接施工；新位置／展開方式須原 Active Contract／線框 Gate |
| Level 0–2 | 正式判定與 DataStatus/DEC-124 已有定義，不能新增第三正式結果或第六資料態；FORMAL／UNDETERMINABLE 二分是 #1275 DRAFT **擬議**軸（現行 `JudgementState` 無 `FORMAL` 成員）；#1275 Draft、DEC 未生效，四 Must-Fix 已修、§3A 對照已加（head `6d4c9f2f`），均過非作者差額 QA | L1＝核心價格證據有效、輔助證據（例如廣度）不足時最多是有來源與缺口揭露的研究參考；與正式 L2／無結論 L0 的**呈現區分**；L1 不改 Risk Cap/System Action | 客戶對 #1275 的正式 DEC Gate；正式文案與狀態須原 DEC/Contract Gate |
| Delta Strip 比較 | TWII published_at/PIT/授權與前次同口徑快照未證可比較；不拿 missing 當 0 | 只有有效同源/口徑、可追溯、訊號完整才可顯示「無重大變更」；否則「⬜ 暫無足夠資料比較今日變化」**目標 copy** | C M1/M2 設計、Work PIT QA；B Copy Gate；不能插新正式 compare path |
| 欄位語意 | 原 FieldVM 能力、狀態、判定分開；DEC-124 不可新添第六態 | 對「過期/缺/來源失敗/未評估/尚未提供/無法判定」誠實短語映射 | B Copy/Contract Gate；正式詞不可因本文直接替換 |
| OneBrain 首屏 | 完整 Digest v1 frozen，不放行正式 OneBrain production caller；現行 OneBrain Outlook 位於日 K 主圖與核心指標卡之後（DEC-157） | 四膠囊，≤3句、<100字，evidence trace 和反證展開；字元計數與 badge 預算口徑待設計 Gate | C Topic Lens Contract；B 視覺，不重寫 Digest |
| Cache/開頁 | 無正式 LLM caller；G-F3=A2-i, G-F4 S1 僅設計 | 證據、coverage、origin/source/as_of、schema/ruleset/contract、topic/lens、model/prompt key；重新判 freshness，開頁零同步 LLM | C 契約差額，不新 provider/cache producer |
| 🎯 What-If | 真持股/OAuth/Sheet HOLD；不可創造 Risk Cap | 唯讀記憶體合成規劃；未接持股顯示「⬜ 需先接入持股」目標詞 | 設計階段，正式文案/功能原 Gate |
| LINE 與 v1.1 | 無正式 LINE／News／Secrets／模型或 Canonical Evidence Store Gate | LINE v1.0 四類事件僅設計；Radar/Signal Log/Store 全 v1.1 HOLD | 不施工 |

## 任何 Contract 差額都不得默默被視為 PASS

1. **權威**：確定性 Rules→Risk Cap→System Action 唯一正式來源；UI/AI 只呈現/解釋，不覆蓋原公式。
2. **缺值**：None/NaN/STALE/PROXY/不可比較/缺 source/as_of 需按有效契約 fail closed；不可用「0、正常、安全、續抱、無變化」遮掩；Real 不拿 FAKE 補畫。
3. **一致性**：新產品文案是目標 wording，非當前正式 Active Presentation Contract 新 enum/FieldVM 授權；不得增加第六狀態。OneBrain topic lens 的研究語句不得形成正式交易判斷。
4. **G-F3=A2-i**：Digest v1 的 MISSING/NO_INPUT/schema 保持；stale/fetch_failed 原因在 coverage/audit，不可支持正式 Risk Cap/System Action。G-F4 S1 等另 Gate。
5. **狀態**：差額索引不是 QA PASS、CI PASS、Design Gate PASS 或施工許可。任何新程式、資料抓取、Cloud、PR Ready/merge/部署仍原本核准流程。

## Owner 與回存

- **A**：#1275 後續（四 Must-Fix 與 §3A 對照已完成並過差額 QA；僅餘客戶正式 DEC Gate 後的呈現／文案對帳）。
- **B**：手機/桌機 Delta Strip／四膠囊、六態、字數／不可比較／未接入文案的線框及 Copy Gate。
- **C**：Topic Lens、Digest/Coverage、完整快取鍵、G-F3/G-F4 設計；What Changed M1/M2 限研究。
- **Work**：非作者獨立差額 QA、授權/PIT/快照可比性與既有 Contract 檢核。

**每張派工卡固定保留**：
- 【範圍鎖定】只改本卡授權檔案／指定差額；不順手重構、不跨線共編、不解鎖 HOLD、不自行新增 Gate。
- 【誠實降級】缺值、NaN、STALE、不可比較等依有效契約顯示或標 NOT VERIFIED；不得補 0、冒充 fresh／安全／續抱，Real 不以 FAKE 補畫。
- 【退回門檻】遇最新 DEC/Contract 衝突、授權缺失、指定 Must-Fix 未清、有效 QA FAIL／CI FAIL、head/base 改變而證據失效，停在現有 Gate，明列阻塞及最小解除證據；不得硬上 Ready/merge/deploy。
