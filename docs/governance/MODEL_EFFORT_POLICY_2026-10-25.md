# DEC-084 補充規範｜Model × Effort 最低足夠配置＋雙向停手

> 日期：2026-10-25
> 性質：`PROJECT_RULES.md` 第 18 節／DEC-084 的規範性補充。
> 原則：**選擇能可靠完成「下一完整工作階段」的最低足夠模型＋最低足夠投入程度；不得固定預設某一模型或某一投入程度。**
> 模型版本：**不得在治理規則寫死版本號**；以客戶當下介面實際可選的 Haiku／Sonnet／Opus／Fable 對應最新版本為準。

## 1. Model × Effort 可直接執行規則

> 每個完整工作階段（完整 Batch）開始前，依本節 Rule 1～8 判斷；Rule 9～10 處理途中變更與切換。
> **模型名稱只寫家族名**（Haiku／Sonnet／Opus／Fable）；具體版本以客戶當下 Claude 介面實際可選的對應最新版本為準，治理文件不寫死版本號（見 PROJECT_RULES 第 18 節）。

### Rule 1｜先判斷是否屬機械性工作

只要本批主要工作是以下任一類：

- GitHub 狀態確認
- 讀取 SSOT
- HANDOFF／BACKLOG／DECISIONS 機械同步
- 改字、格式修正
- 小型文件修正
- commit／PR 收尾
- 已有明確答案的純落盤
- 不需要重新解釋規格的 targeted docs tests

→ **Haiku + Low**。

不得因文件很多、repo 很大、PR 很長，就自動升級模型。

### Rule 2｜低風險且規格明確的小修

工作需要少量理解或修改，且同時符合：

- 規格已經明確
- 不涉及跨模組架構
- 不涉及資安裁示
- 不涉及資料契約
- 不涉及投資核心語意
- 錯誤影響範圍小且可逆

例：一般文件整理、簡單 bug、低風險測試修正、小型 UI 文案／排版、明確規格的小修改。

→ **優先 Haiku + Low**。只有 Haiku 明顯不足時才升到 **Sonnet + Medium**。

不得一開始就預設 Sonnet。

### Rule 3｜一般開發工作

工作屬於：一般 UI／UX 實作、一般 coding、單模組 bug、tests、一般 wiring、一般 service／repository 接線、已有清楚規格的中等複雜實作。

→ **Sonnet + Medium**。Sonnet 是一般開發工作的主要模型。

### Rule 4｜OAuth／Google Sheet／跨模組不得因關鍵字直接升 Opus

OAuth、Google Sheet 或跨模組工作，若同時符合：

- 規格已經明確
- 主要是實作或 wiring
- 不需要重新裁示 credential／token／scope／callback
- 不涉及新的資料契約
- 不涉及不可逆操作
- 不涉及重大資安取捨

→ **先 Sonnet + Medium**。

不得只因工作名稱含 OAuth、Google Sheet、API、跨模組、architecture 就直接使用 Opus。

### Rule 5｜只有高風險推理才升 Opus

出現以下任一情況，才使用 Opus：

- OAuth scope／callback／credential storage／token persistence 的資安決策
- 新的資料契約或資料身分規則
- 多模組重大架構取捨
- correctness 難以局部驗證
- 高風險 migration
- 權限與敏感資料處理
- 既有 SSOT 出現真正語意衝突
- Sonnet 已嘗試但無法可靠完成

分級：

- 屬上述工作、但仍可逆且範圍受控 → **Opus + Medium**
- 涉及投資核心語意、Risk Cap、PIT、重大 data contract、不可逆操作、高風險 production architecture，或錯誤可能造成重大資料／決策影響 → **Opus + High**

### Rule 6｜Fable 不是日常模型

只有在以下情況才可建議：

- Opus 明顯不足
- 極端複雜問題
- 大型 red-team
- 多份 SSOT／治理規則發生重大衝突
- 需要最高能力模型才能可靠收斂

→ **Fable，或當下介面中明確更高能力的模型 + High／更高**。

Fable 不得作為一般開發、OAuth、文件、GitHub、UI 或一般架構工作的預設。

### Rule 7｜Effort 一律使用最低足夠值

判斷順序：

1. 能用 Low 安全完成 → **Low**
2. Low 不足、需要一般推理 → **Medium**
3. Medium 不足，且屬高風險／複雜 correctness → **High**
4. 不得因模型較強就自動把 Effort 一起拉高

**Model 與 Effort 必須分開判斷。**

### Rule 8｜每個完整 Batch 開始前必須執行一次

依序自問，必須從最低成本配置往上判斷，不得從最高模型往下降：

1. 這是機械性工作嗎？→ 是則 Haiku + Low
2. Haiku 能安全完成嗎？
3. 若不能，Sonnet + Medium 是否足夠？
4. 是否真的存在必須 Opus 才能處理的高風險推理？
5. 是否真的達到 Fable 等級？

### Rule 9｜工作途中只有「性質改變」才重判

只有以下情況才重新判斷 Model × Effort：

- 工作從文件同步變成實作
- 從一般 wiring 變成資安決策
- 從局部 bug 變成跨模組架構
- 從一般資料處理變成資料契約／投資核心語意
- 或原模型已證實不足

CI 等待、push、merge、PR 更新、測試排隊**不算**工作性質改變。

### Rule 10｜只要建議配置有變，就執行 Change Gate

重新判斷後，若 **Model 不同，或 Effort 不同**（不論升級或降級）：

1. 立即在安全 checkpoint 停手；
2. 告知客戶建議的新 Model + Effort，並說明一句原因；
3. 等客戶手動調整並回覆「改好了」；
4. 才開始下一完整工作階段。

相同則不回報，直接維持 Silent Autonomous Cruise。

### Rule 11｜成本優先順序

預設優先順序：

**Haiku + Low → Haiku + Medium → Sonnet + Medium → Opus + Medium → Opus + High → Fable／更高模型**

只有前一級無法安全完成時才往下一級。不得為了「比較保險」無理由使用更高模型。

### Rule 12｜正確性是底線

省 token／使用量不得造成：

- 錯誤投資語意
- 錯誤資料契約
- 資安風險
- Missing 被當成 0／False／safe
- 未驗證資訊被當成已確認
- 自動 fallback 到錯誤資料源
- 不可逆操作缺少 Stop Gate

若最低成本配置無法可靠避免以上風險，就必須升級。

### 一句執行原則

每批從 **Haiku + Low** 開始判斷；只有工作本身證明需要更高能力時才逐級升級；只要建議 Model 或 Effort 與目前不同，就停手讓客戶切換。


## 2. 雙向切換：任何變更都必須停手等待

在每個完整工作階段邊界做一次 Model／Effort Check：

- **目前模型＝建議模型，且目前投入程度＝建議投入程度** → 維持 Silent Autonomous Cruise，直接繼續，不回報 Check 結果。
- **任一項不同** → 到最近安全停點後**立即停手**，不得開始下一完整階段。

此規則不分方向，全部適用：

- Haiku → Sonnet／Opus／Fable：停手。
- Opus／Fable → Sonnet／Haiku：停手。
- 低 → 中／高／超高／最高：停手。
- 高／超高／最高 → 中／低：停手。
- 模型不變、只改投入程度：停手。
- 投入程度不變、只改模型：停手。
- 模型與投入程度同時改：停手。

停手後：

1. 告知客戶「下一階段、目前模型、建議模型、目前投入程度、建議投入程度、原因」。
2. **不得自行假設客戶已切換。**
3. **不得繼續下一完整階段。**
4. 等客戶手動修改設定。
5. 客戶明確回覆「改好了」後才可繼續。
6. 若客戶只改了其中一項，而另一項仍與建議不同，維持停手。

固定格式：

```text
⏸️ 建議切換模型／投入程度，已停手
下一階段：___
目前模型：___
建議模型：___
目前投入程度：___
建議投入程度：___
原因：___
請修改完成後回覆「改好了」。
```

## 3. 只在完整階段邊界重評，避免反而浪費 token

至少在以下時點重評：

1. 新 Batch／下一完整工作階段開始前。
2. 客戶完成 Decision Gate 裁示、正式施工前。
3. 一個高風險子批完成，準備進入不同性質的下一階段時。
4. 工作風險／複雜度實質改變，且已到 Safe Checkpoint 時。
5. 實作／驗證完成，準備轉為單純文件／收尾工作時。

以下**不是**新的完整階段，不應因此頻繁切換：

- 等 CI／workflow。
- 等 QA／audit。
- commit／push。
- PR 開啟。
- 同一不可分割原子工作內的小步驟。
- 同一修復流程中的短暫狀態。

不得為了省一點模型額度，把一個完整 Batch 人為切成大量小段，導致反覆重讀 context、增加 token 消耗。**節省原則是降低不必要的模型／投入程度，不是增加切換次數。**

## 4. 與既有治理的關係

- 本補充與 `PROJECT_RULES.md` 第 18 節共同構成 DEC-084 的現行執行規則。
- **部分取代 DEC-073** 中「目前能力高於所需時，可以不提醒降級並保持靜默直接工作」的方向：自 DEC-084 起，只要下一完整階段的建議模型或投入程度不同，無論升級或降級都必須停手等待客戶修改。
- **加嚴 DEC-059／DEC-061**：由「雙向提醒」提升為「雙向停手＋等待客戶改好」。
- **DEC-014 續有效**：客戶回覆「改好了」後直接繼續，不重新摘要、不重問、不重做。
- `PROJECT_RULES.md` 第 17 節 Minimum Sufficient Effort／Test Scope 續有效；本補充不降低 Risk Cap、投資語意、PIT、資料有效性等高風險工作的 QA 要求。
- Silent Autonomous Cruise 續有效；**Model／Effort 需要切換是正式例外**。

## 5. 客戶裁示來源

客戶 2026-10-25 明確要求：

> 「更換時候都需要等我修改好才能繼續，不管是換低到高或是高到底都需要等我修改」

並再次確認：

> 「可以都停下來等我改完再繼續嗎？ 我不想浪費token」

其後客戶以 Anthropic 官方定價資料再次收斂省量策略，確認：

> Haiku 當機械／低風險工作的優先起點；Sonnet 當主要開發模型；OAuth／Google Sheet／一般跨模組先 Sonnet＋中；Opus 只處理真正高風險／高推理工作；Fable 原則上不用，除非 Opus 明顯不足；Effort 一律採最低足夠值。

本檔只把該策略正式化為本 repo 的治理規範；不構成任何產品功能、投資語意或資料層修改授權。
