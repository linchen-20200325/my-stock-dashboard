# OneBrain／Decision Digest 匿名離線示意（C-OB-USABLE）— 2026-11-20

> 授權脈絡：Issue #1199 comment 7025346343（C-OB-USABLE：沿用現有 OB-1／Digest／rule-only fallback，交付匿名／離線／不付費的最小可執行流程）與 7022254385。
> 本文件是**說明**，不是規格、不是授權擴張；沒有修改任何 Digest schema／詞彙／簽章、守衛常數或 UI2 檔案。

## 0. 先講清楚（不得誤讀）

- 這是**離線 CLI 示意**，輸出在終端機。**使用者在 UI2 畫面上看不到任何 OneBrain 內容**：UI2 的 OneBrain／Digest 位置仍是硬編的「⬜ 尚未提供」空殼。
- 輸入全是**匿名合成資料**（代號 `T0..Tn`、行動文字 `txt-…` 為示意識別字）。不是真實持股、**不是投資建議**。
- 沒有啟用真 Provider／SDK／付費 API／正式 caller／W8；不碰個人持股／Google Sheet／OAuth／Risk Cap／Secrets／workflow。
- Stage F production caller Gate 仍關閉（`ALLOWED_CALLERS = frozenset()`）。

## 1. 如何執行

```bash
python -m tests.onebrain_anon_demo                       # 全部情境，人可讀文字
python -m tests.onebrain_anon_demo --scenario C          # 單一情境（A～F，大小寫不拘）
python -m tests.onebrain_anon_demo --scenario all --format json   # 機器對照（欄位如實，不含 Digest 本體）
```

純離線、零網路、零 Secrets、零時鐘（`generated_at` 為固定常數）、輸出決定性（同輸入同輸出）。
注意：`src.services` 套件初始化會**傳遞性載入 streamlit**（現況，未為此改 src），stderr 可能出現 streamlit 的 config／`FinMind` 警告與 `onebrain shadow: provider error …`（影子層刻意留下的 warning log）；stdout 乾淨。demo 檔本身不 import streamlit。

檔案：`tests/onebrain_anon_demo.py`（非 `test_` 開頭，不被 pytest 收集；比照 `tests/onebrain_fake_provider.py`）、測試 `tests/test_onebrain_anon_demo.py`。
**放在 tests/ 是刻意的**：已實證放在 `scripts/` 會讓 `test_decision_digest_invariants_guard`（Digest caller 守衛）轉紅。

## 2. 每個情境輸出四區

| 區 | 內容 |
|---|---|
| ① 來源 | coverage 四段（market／risk_cap／holdings／actions）是否採用、source、資料日；行動 total／shown／omitted；`is_complete` |
| ② 缺值 | 未採用段的 withheld 原因、摘要中「資料不足／未產出可引用依據」的缺值句；未知計數顯示「未知（None，不是 0）」 |
| ③ 規則判斷 | 規則式摘要五段（市場／產業／存股／資本利得／本期行動），文字逐字來自 `build_rule_summary` |
| ④ fallback | `effective` 是哪一份、Provider 輸出是否被採用 |

每頁頁首標示「示意：匿名合成輸入，非真實持股、非投資建議」。

## 3. 各情境意義（實測輸出重點）

| 情境 | 輸入 | 重點結果 |
|---|---|---|
| A | macro＋站內證據皆 fresh、2 筆行動 | 四段 used、`as_of=2026-10-26`、`is_complete=True`；行動段列 2 筆 `txt-…` |
| B | 零證據 | 四段 `no_stamp`；所有可判斷句皆「⬜ …資料不足，無法判定（尚無輸入）」；total／omitted 為 None；`is_complete=False`；state=unavailable |
| C | macro 證據 stale | market／risk_cap `withheld=stale`（仍帶 source 與資料日）；**摘要仍寫「尚無輸入」**——如實呈現，並加註「摘要字面未區分過期與無輸入」 |
| D | 站內證據 `FETCH_FAILED` | holdings／actions `fetch_failed`；摘要寫「規則層未產出可引用依據」；加註摘要未點出抓取失敗 |
| E | 7 筆合格行動 | coverage `total=7／shown=3／omitted=4`、`is_complete=False`；摘要只列 Top-3；加註 OB-1-D3 |
| F | 影子執行 × FakeProvider | `timeout`→error_kind=timeout；垃圾輸出→invalid_response；echo→`shadow_accepted=True`；**三種的 effective 都等於規則式摘要、Provider 輸出一律不被採用** |

## 4. 誠實分區

**已實作（本 PR）**
- 匿名／離線／不付費的最小可執行流程：`assemble_digest → build_rule_summary →（run_shadow＋FakeProvider）`，四區輸出、text／json 兩格式、6 情境，與 30 個測試（含突變驗證）。

**docs-only（只有文件、沒有程式）**
- 本文件；OneBrain 更廣的架構／證據覆蓋藍圖（`docs/vnext/ONEBRAIN_*`）仍是藍圖。

**缺 caller（管線存在、但沒有任何正式呼叫者）**
- `shared/decision_digest*.py`、`src/services/decision_digest_{builder,assembly,summary}.py`、`shared/onebrain_provider.py`、`src/services/onebrain_shadow.py` 的 production caller 為 0（DEC-195；`ALLOWED_CALLERS=∅`、`OFFLINE_SHADOW_CALLERS` 恰兩檔）。本示意只在 tests/ 與命令列使用它們。
- UI2 沒有接 OneBrain／Digest；沒有真 Provider。

## 5. 已知缺口（如實標示，本批不修）

1. **OB-1-D3**：規則式摘要只列 Top-N 行動，**未揭露其餘被省略的筆數**；省略數只存在 coverage 側車。修法需新增詞彙與簽章（摘要需讀 coverage），屬 Digest 詞彙／簽章變更，Gate-needed。
2. **缺值原因缺口（stale／fetch_failed）**：Digest v1 沒有缺值原因欄，摘要字面無法區分「過期」「抓取失敗」與「尚無輸入」；原因只在 coverage 的 `withheld_reason`。C／D 情境輸出會如實加註，不美化。
3. 摘要的 `⬜ 台股趨勢／國際趨勢／產業趨勢：尚未定義`、`大盤合理區間：研究框架，未啟用` 為 Digest 既有固定句，不是缺資料。

## 6. 下一個最小 Gate（推論，**不是授權**）

「OneBrain rule-only 摘要掛入 UI2 FAKE feed」：需要
1. 客戶核准；
2. UI 線框草稿（CLAUDE.md §-1.5.D §03-2 ①，畫面位置／元件異動）；
3. 在 `tests/test_decision_digest_invariants_guard.py` 登記 `ALLOWED_CALLERS`（附核准依據），並過 UI2 既有守衛（no-second-AI、evidence preservation、SHOWN_FOLDS／WIRED_PATHS 等）。

在上述核准前，本示意是唯一的可執行入口。
