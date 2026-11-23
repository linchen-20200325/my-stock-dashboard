# 判定等級（正式／無法判定）DEC 草案（無編號；未生效）

## 0. 狀態
- **DRAFT，不生效**。須客戶於 #1199 正式裁示後才成為 DEC；本檔**不是** `docs/DECISIONS.md` 條目，未編 DEC 號。
- **不授權**：程式、Enum、schema、UI 文字、新來源、workflow、caller、Gate 解除、Ready／merge。
- **參考（非 DEC）**：總管裁示 #1199 comment 7101496340、7102624975；A 決策包 7101878581、7102518086；Work 非作者 QA 7101082181。
- 標記：FACT＝已在 origin/main `913dd759` 實讀；PROPOSED＝擬定條文；HOLD＝維持不變；NOT VERIFIED＝未驗證。
- 原則：missing≠0；unknown≠safe；not evaluated≠safe（DEC-054 第 3 點，docs/DECISIONS.md:1588-1598）。

## 1. 已裁示方向（FACT，非 DEC）
D-a=A（詞表）、D-b=A（僅 FORMAL／UNDETERMINABLE）、D-c=A（先 docs）：#1199 comment 7101496340。O-1=A、O-2=有條件 A、O-3=A，並允許 docs-only Draft PR：comment 7102624975。

## 2. 擬定條文（PROPOSED）
**第 1 條 詞表**：「正式／研究參考／無法判定」僅為概念詞表，避開 L0/L1/L2；不批准任何 Enum、文案或實作。
**第 2 條 兩級**：首版正式判定軸僅 FORMAL（正式）與 UNDETERMINABLE（無法判定）。**研究參考不是判定級別**。FORMAL＝§3 該功能前提全數成立；任一缺、過期逾限、為代理值、as_of 不明、持有為 None → UNDETERMINABLE，顯示既有「⬜ 無法判定」，不得為 0／中性／安全／預設。
**第 3 條 推導**：等級由既有狀態推導，不是輸入、不入庫；不新增第六個資料態（DEC-124，:6254）、不新增公式／分數／信心數字。`UNDETERMINABLE` 已存在於 `shared/ui2_contract/models.py:42`（`JudgementState`）；UNDETERMINABLE≠NOT_EVALUATED（:3170 對映列，記錄 DEC-124 的取代語意）。
**第 4 條 AI**：AI 不得提升等級；AI 不可用≠SAFE／HOLD／中性（`docs/vnext/ONEBRAIN_ARCHITECTURE_DECISION_2026-10-31.md:16` 第 8 點）。
**第 5 條 比較與日期**：無同口徑當期＋前次正式快照時只能標「不可比較」，⛔「今日無重大訊號變更」（Work QA 7101082181）；`fetched_at` 不得替代資料日（DEC-205，:10809 起）。
**第 6 條 文案**：本草案不授權任何字樣變更；新字樣另走文案 Gate 與線框先行。

## 3. 逐功能 FORMAL 前提（PROPOSED；**非單一總門檻**，各列只依自己的原 DEC）
| 功能 | 原依據 | 必要條件 | 現況 |
|---|---|---|---|
| 市場位階 | DEC-074 B（:2173）、DEC-075（:2198）、DEC-161（:8078） | 代理廣度不計分；位階須有 as_of（INFERENCE，由 SG-10 推得） | 否：`RegimeFact` 無 as_of（`src/services/ui2/real_canonical.py:160`） |
| Risk Cap | `shared/risk_cap_policy.py`（Core 5、`required_core_ok`）、`shared/staleness.py:163`（≤7 曆日） | Core 5 齊備且新鮮，缺則無法判定 | 否（UI2 數值 Gate 前恆 ⬜ 無法判定） |
| TWII 日 K（僅事實顯示） | DEC-156（:7955）、DEC-081 Q3=A（:2709）、DEC-160（:8067）、DEC-214（:10948） | 揭露來源／資料日／stale；正式趨勢維持「尚未定義」 | 事實顯示已定；資料日是否在 7 曆日內 NOT VERIFIED |
| 個股 | DEC-215（:10967）、DEC-213（:10932） | 母體＝可評分全集，排除列另行揭露 | 無接線；各前提逐項 NOT VERIFIED |
| 持股 | DEC-215 §一第 2 點、DEC-218（:11085）、Holdings 契約 §C-6（:119） | UNKNOWN 不得為 0／中性／SAFE；重複代號揭露；缺獨立母體須標不完整 | 無接線；各前提逐項 NOT VERIFIED |
| Digest／OneBrain | ADR-OB-001（`docs/vnext/ONEBRAIN_ARCHITECTURE_DECISION_2026-10-31.md:10,16`）、DEC-054 | 上游規則鏈成立；OneBrain 僅解釋 | 否（無可驗的當期＋前次正式快照） |
| ETF 動作 | DEC-054、DEC-222 §二第 1 點（:11222；該節屬 AI 總管內部決定，非客戶裁示） | 規則須既有可追溯；資料不足不硬給方向 | 無接線；NOT VERIFIED |
| System Action | DEC-222（:11214；客戶核准的是 M-A1） | 沿用既有規則；unjudged 不計入 | 否（未接任何 consumer） |

## 4. 事實不升格清單（O-1=A；PROPOSED）
下列事實**不得**升格為正式趨勢／Regime／Risk Cap／System Action／交易訊號／隱含信心。**本清單不是全面禁顯資料，也不是任何新取數許可**；各項只在其原 DEC 範圍內成立。
| # | 事實項 | 許可依據與範圍 | 狀態 |
|---|---|---|---|
| 1 | TWII 日 K 序列（K 色以開收比） | DEC-156（:7955-7960） | 照原 DEC 顯示 |
| 2 | TWII 資料日、來源、is_stale 揭露 | DEC-156「來源／唯讀」 | 照原 DEC 顯示 |
| 3 | TWII 最新收盤值 | DEC-081 Q3=A「原始客觀資料可放第 3 層」（:2709） | 第 3 層已許可；首屏 NOT VERIFIED |
| 4 | 既有指數／均線參考線，須帶固定句「均線為參考，不等於正式台股趨勢判斷。」 | DEC-092 Q2（:1250；句 :1095） | 照原 DEC 顯示 |
| 5 | 國際既有可追溯資料系列 | DEC-092 Q2 圖 B | 照原 DEC 顯示 |
| 6 | 與前收比較的日漲跌幅 | DEC-156 稱須另取合法前收與獨立語意；DEC-081 Q3=A 禁以漲跌幅代趨勢 | NOT PERMITTED／NOT VERIFIED |
| 7 | 外資或其他單一指標當趨勢 | DEC-081 Q3=A 明禁 | NOT PERMITTED |
| 8 | 三大法人／融資／板塊於 **UI2** 顯示（範圍僅 UI2；舊 UI 既有顯示不受本案影響） | DEC-162 僅唯讀盤點；DEC-163（:8094）僅文字線框草案；DEC-164 僅授權唯讀 L3 service 與單元測試、不接 UI | UI2 顯示 NOT PERMITTED／NOT VERIFIED |
| 9 | stale／未來日／重複日的值 | DEC-160（:8067）：不得當 fresh 進決策／Risk Cap／排序／摘要；DEC-214（:10948）：「⚠ 過期 N 天」＋資料日＋來源；DEC-201／207 | 僅限上列 DEC 已定的降級呈現；不得當 fresh、不得升格 |

## 5. 正式輸出可用性（O-2=有條件 A；**PROPOSED 新增治理條件，非既有核准條文**）
區分兩件事：
- **(a) 上游規則與輸入證據已具正式判定條件**：即 §3 該功能前提成立。
- **(b) 經核准的 production caller／consumer 真正部署且可交付**。
(b) 缺失 ⇒ **不得對使用者宣稱「正式生產輸出可用」**；但**不得**反過來說 (a) 因無 consumer 而不成立。本條**不授權** Stage F 或任何新 caller；`ALLOWED_CALLERS = frozenset()`（`tests/test_decision_digest_invariants_guard.py:286`，:422 斷言）維持不變。

## 6. READ_FIRST 第 24 行修訂提案（O-3=A；與本草案同批、非作者 QA，不直接改主幹）
現行（`docs/vnext/READ_FIRST_UI2_ONEBRAIN_VERSION_AND_DEC_DRAFT_2026-11-23.md` 第 24 行整行）：
> 3. **L0/L1/L2 僅候選顯示分級**：L2 必要正式條件全部滿足；L1 部分輔助證據缺失時只顯示可信研究參考及缺口，不得形成簡化正式位階/動作；L0 核心證據不可用時無法判定。不是新演算法/風險分數的授權。

擬替換（單行）：
> 3. **正式判定首版僅 FORMAL／UNDETERMINABLE 兩級**：必要正式條件全部成立才為 FORMAL；核心證據不可用時為 UNDETERMINABLE（無法判定）；研究事實可依既有 DEC 展示，但不得升格為正式位階/動作/趨勢；不使用 L0/L1/L2 作新判定級別。不是新演算法/風險分數的授權。

理由：舊句 L1「可信研究參考」與 D-b=A 衝突，且 L0/L1/L2 與 CLAUDE.md §8.2、`docs/v2/spec/S1-6_COMPLIANCE_COPY_GUIDE.md` 用語相撞。

## 7. HOLD 不變
DEC-081／092／124／160；DG-LIC／PIT／COV／SCOPE／I1144（DEC-205 已裁 PIT＝B＋X、LIC＝A，DEC-215 已定 COV 母體口徑，皆「已裁示但未接線」，非解除）；Stage F／正式 caller；v1.1；NAS #1237；Cloud、Secrets、production LLM caller。

## 8. 開放項／NOT VERIFIED
DG-LIC 現況；TWII 資料日與 Risk Cap／Real VM 狀態（Work QA 之說）；DEC-092／156／215／218 內文逐字、DEC-161 逐字；Risk Cap 行號；Cloud 實況；ADR-OB-001 僅讀第 2、8 點；Holdings 契約 :54／:80；舊 UI 是否已顯示三大法人／融資／板塊；§3 各列「現況」非逐項實測。本文未經新一輪非作者 QA。

## 9. 唯一下一步
非作者 QA（本文＋READ_FIRST 第 24 行替換）→ 客戶於 #1199 正式 DEC 裁示。裁示前不動程式、文案、來源、workflow、caller 或 Gate。
