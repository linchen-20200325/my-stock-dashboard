# 🗂 資料新鮮度總覽「首屏」設計與實作紀錄（方案 C，已核准施工）— 2026-11-18

> **狀態**：使用者 2026-11-18 明示「核准方案 C、Q1=A、D-5 精確局部守衛例外，依 ChatGPT 定稿施工，其他安全 Gate 全部保留」
> （[#1199 留言 6964576511](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-6964576511)）；GPT 定稿見
> [#1199 留言 6964559744](https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-6964559744)。
> **本文件＝施工紀錄，不是驗收。** 未 IMPLEMENTED/VERIFIED：尚缺非作者 QA、exact-head 五項原生 CI、main push CI；Cloud 實況 NOT VERIFIED。
> **單組產出**（作者單組，`CLAUDE.md` §-2 規則 6）；標籤：**FACT**＝作者實測／讀碼；**INFERENCE**＝推論；**NOT VERIFIED**＝未驗，不得當前提。
> **不變**：DG-LIC／DG-PIT／DG-COV／DG-SCOPE、I1144-WIRING-GATE、Auth、Risk Cap、OneBrain、資料發布、NAS／Secrets、Cloud 變更、六項真值、
> 第二階段明細、新來源／網路——全部未授權、未動。TWII 卡「每日更新」文案為獨立項目，**本變更未動**。

## 1. 最終畫面（方案 C；`first/context_rows` 四列，`src/ui2/**` 零改動）

Real 軸（390×844 實測 DOM 順序，N=8、K=2；數字為示意狀態「台股過期＋位階無法判定」）：

```
[Real-data Preview（非正式 production default）]
🗂 資料
資料健康度 ⬜ 尚未提供   完整資料健康度尚未開放；本頁先顯示資料新鮮度摘要                 ← Q3
資料新鮮度總覽  固定清單 8 項                                                           ← row 0
接入狀態        已接入畫面 2 項｜尚未提供 6 項                                           ← row 1
新鮮度          資料日在規則內 0 項｜⚠ 過期或可能已過期 1 項｜⬜ 資料未備 0 項           ← row 2
其他狀態        🔴 來源目前不可用或資料異常 0 項｜⬜ 尚未評估 0 項                         ← row 3
                資料日在規則內只表示資料日未超過規則，不是買賣訊號。                        ← row 3 detail（固定）
                另有 1 項判定結果為無法判定，不計入上列                                    ← 僅 n>0，同一 detail 內以全形空格分隔
是否需要行動 ⬜ 尚未提供   本頁不產生持股動作；動作權威＝💼 持股
下一步 ⬜ 尚未提供          完整資料健康度開放後才可查看                                    ← Q3
[查看資料健康度]（停用）  完整資料健康度尚未開放                                          ← Q3
🔌 連線診斷  僅供檢查連線；連線成功不代表行情已更新。（既有 TEXT_DIAG_NOTE，未動）
資料來源與連線：來源健康度／資料日 ⬜ 尚未提供  完整資料健康度尚未開放；資料日與新鮮度請看『資料新鮮度總覽』   ← Q3
```
**FAKE 軸**：`counts=None` → 原本誠實空殼與**原文案**（現在狀態原因＝「…本區僅檢查連線…」、下一步「資料健康度清單開放後才可查看」、CTA「資料健康度尚未開放」），
`context_rows` 為空、無任何摘要／計數；ui2_p3 baseline 的 FAKE 6 筆因此**一字未變**。

## 2. 計數導出規則（FACT；實作：`real_canonical.item_state_of_spec`／`freshness_states`、`data_page.counts_from_states`）

- **N=8**（`FRESHNESS_ITEMS`，台股、外資、融資、M1B／M2、PMI、板塊、位階、基本面）；**K＝清單中有已接入事實的項數**（台股、位階＝2），N−K 不計入任何狀態、不是失敗。
- 台股項只讀 `twii_card_spec(snap)`，位階項只讀 `regime_spec(snap, …)`——**不重算新鮮度規則、不讀時鐘**；日 K（`snap.kbar`）不算第 9 項、不影響計數（有測試）。
- 狀態映射（互斥）：`unavailable`→d（含讀取例外、契約違反、**未來資料日 #1206**）；`not_evaluated`→e（位階未載入）；`undeterminable`→n（另列，不入五態）；
  `stale`→b（含 `is_stale=None`，**絕不算 OK**）；無值→c；**有值但無資料日→c**（位階已載入恆屬此項）；有值且有資料日→a。其他 state 字串 → `ValueError`。
- 不變量（`FreshnessCounts.__post_init__`）：`a+b+c+d+e+n == K`、`K ≤ N`、非負整數；`counts_from_states` 要求 key 恰等於已接入項目。連線診斷不計入。

## 3. 實作範圍（FACT：`git diff b06a7eca --stat`）

| 類別 | 檔案 | 內容 |
|---|---|---|
| production | `src/services/ui2/data_page.py` | 計數模型、四列、Q3 文案；`data_page_canonical(counts=None)` |
| production | `src/services/ui2/real_canonical.py` | `_data(snap)`、`item_state_of_spec`、`freshness_states` |
| 守衛 Q1=A | `tests/test_ui2_real_feed.py::WIRED_PATHS` | **僅**加 `(P4_DATA,"first/context_rows/0"|"/1"|"/2"|"/3")` 四個精確 tuple（對最終 VM 核對：4 列即 index 0–3） |
| 守衛 D-5 | `tests/test_ui2_real_feed.py`：新 helper `regime_label_residue(blob, page)`，`test_1202_g1_shell_survives_read_real_snapshot_raising` 改呼叫它 | 見 §5 |
| T3 | `tests/test_ui2_connection_diag_view.py::test_localized_copy_correction_is_minimal` | 示意軸原文案不動；Real 軸釘 Q3 新文案；`TEXT_DIAG_NOTE` 不動 |
| baseline | `tests/fixtures/ui2_p3_evidence_baseline.json`＋`tests/test_ui2_active_contract_docs.py::_P3_BASELINE_SHA256`（→ `fedfa62d…b2a6`） | **FACT：只有 `real/p4_data` 9 筆變動**，僅 `first_screen`／`context_rows`／`sections` 三欄；FAKE 與其他頁 78 筆未變 |
| 新測試 | `tests/test_ui2_data_freshness_overview.py` | 145 個測試（§4） |
| 文件 | 本檔 | — |

**零改動（FACT）**：`src/ui2/**`、`SHOWN_FOLDS`、renderer／CSS／schema、`shared/ui2_contract/*`、`real_feed.py`、G2／G2F／G4B／G9 與 `CAPABILITY_MARKER_ALLOWLIST`、`tests/ui2_viewport/**`、4 份 viewport 證據 JSON（`source_hash` `25c1f27f…` 與現算相同，故未重生、未手改）。

## 4. D-4 補償控制與反向驗證（FACT）

`check_only_wired_fields_carry_data` 對 `WIRED_PATHS` 內路徑整個放行，所以新測試精確鎖定四列：path（恰 4 列、順序）＋canonical key（`fresh_total/wired/a/b`）＋label＋
OK 純文字（無狀態字樣、capability PROVIDED）＋四條固定正規式＋**僅**第 4 列可有 detail 且須為核准兩句＋無 `as_of`／`source`／規則名／時間戳／日期／原始值。
另有：9 台股組合×5 位階組合＝45 個 snapshot 的算式測試（四列數字 == 由卡片／位階 VM **獨立另算**的結果，且 a+b+c+d+e+n=K）、FAKE 無摘要測試。
反向注入（皆被擋）：舊區塊「資料日」「來源健康度」帶值、第 5 列、S 路徑 `sections/data_freshness/0`、第一屏「現在狀態」「下一步」帶值、👤／💼 頁同索引帶值、📊 VIX 卡帶值、
12 種同路徑非法形狀（as_of／source／日期／原始收盤值／fetched_at／改字／缺免責／row0 帶 detail／label 被改／STALE 態／capability／規則名）、列數與順序錯誤；拔掉 allowlist 條目 ≥4 紅。
**突變 18 組全擊殺**（`item_state` 5、位階漏算、K 硬寫、免責改字、n 句不輸出、標籤改字、示意軸輸出摘要、列帶 as_of、多第 5 列、allowlist 少／多一條、D-5 放寬兩種、Q3 退回舊句；M6／M7 以 collection error 擊殺）。

## 5. D-5 精確 guard diff
```diff
# tests/test_ui2_real_feed.py
-    assert not any(lbl in blob for lbl in REGIME_LABEL.values() if lbl)          # 無位階字樣殘留
+    assert regime_label_residue(blob, page) == []                                # 無位階字樣殘留（🗂 第 4 列核准文案為唯一精確例外）
+def regime_label_residue(blob, page):
+    if page == P4_DATA:
+        row4 = freshness_rows(counts_from_states({"twii": S_UNAVAILABLE, "regime": S_UNAVAILABLE}))[3]["value"]
+        blob = blob.replace(row4, "")          # 只剪掉「該整串」核准文案（降級頁 d=2、e=0）
+    return [lbl for lbl in REGIME_LABEL.values() if lbl and lbl in blob]
```
原因：`REGIME_LABEL['unknown']="未評估"` 是第 4 列核准文案「⬜ 尚未評估」的子字串。測試 ID：正向 `test_d5_positive_data_page_row4_wording_is_excepted`；
反向注入 `test_d5_reverse_injection_everything_else_still_fails[8 組]`（🗂 同頁其他位置多一個「⬜ 尚未評估」、🗂 位階字殘留、第 4 列被改字、同一串出現在 📊／🎯／💼／👤、📊 位階字）全紅；
受影響既有測試 `test_1202_g1_shell_survives_read_real_snapshot_raising[p4_data]`（其餘四頁行為不變）。

## 6. 驗證結果（FACT，作者環境；非 CI、非獨立 QA）

| 項目 | 結果 |
|---|---|
| `tests/test_ui2_*.py`（worktree） | 2097 passed／43 deselected／3 xfailed |
| 全 repo `python -m pytest -q -p no:cacheprovider`，自 `git archive HEAD` 乾淨匯出（Python 3.13、streamlit 1.59.2） | **40159 passed／21 failed**／38 skipped／3 xfailed（17 分 21 秒）。21 個失敗全為 `tests/test_sec_*`、`test_vn1_*` 的 git 索引／歷史 commit 依賴測試（`tests._git_tracked`）；**在未修改的 `b06a7eca` 匯出重跑這 9 個檔同樣 21 failed**（＝匯出無 `.git` 的環境因素，與本變更無關）；同 9 檔在 worktree（有 git 索引）**1475 passed／0 failed** |
| ui2_browser 車道（CI 同指令，playwright 1.64.1，`UI2_BROWSER_LANE=required`） | streamlit **1.59.2**：43 passed／0 skipped；streamlit **1.56.0**：43 passed／0 skipped（≥40、skipped=0） |
| `measure_viewport.py`（既有門檻，未動；390×844＋1440×900；`--shots none`；匯出目錄） | 1.59.2：fake 82／82、real 13／13 通過；1.56.0：fake 82／82、real 13／13 通過；`failed=[]`。證據 JSON `source_hash` 未變 → **未重生、未手改** |
| 最終 DOM 證據（Real 正常／n>0／未來日／全新鮮／降級＋FAKE；兩 viewport；兩 streamlit 版本） | 12 組全：無橫向捲動、無列重疊、無截斷（`scrollWidth/Height` 檢查）、四問＋停用 CTA 全在摺線上方（390：CTA 底 ≤584 < 844）、context 列 Real＝4／FAKE＝0；n 句只在 n>0 出現；降級頁警示在、四列為 d=2、CTA 停用 |
| 突變 | 18／18 擊殺 |

**審視過的截圖**（`scratchpad/evidence/<ver>/*.png`；repo 外、易失）：`n_Real_m390.png` 確認四列、免責與 n 句分行清楚、四問與停用 CTA 可見、無截斷。

### 6.1 合併 origin/main（ca12825e，#1210）後複驗（2026-11-18；FACT，**作者環境**；**非 CI、非非作者 QA**；只追加，§6 上表原文不改）
| 項目 | 結果 |
|---|---|
| 全 fast lane，自 git 初始化的 `git archive` 匯出（有 git 索引，故 §6 的 21 個索引相依失敗不再出現） | **40209 passed／0 failed／38 skipped／3 xfailed** |
| ui2_browser | streamlit **1.59.2**：43 passed；streamlit **1.56.0**：43 passed |
| `measure_viewport.py` | 兩版本皆 fake 82／82、real 13／13，`failed=[]` |
| `tests/test_ui2_*.py`＋z60＋#1208 兩條還原鏈 | 2260 passed |
| 證據 JSON | `source_hash` 輸入未變 → viewport 證據 JSON **未重生** |
| ui2_p3 baseline | 僅 real／p4_data 變動 |

以上皆為作者環境結果；非作者 QA、exact-head 原生 CI、main CI、Cloud 仍 NOT VERIFIED。

## 7. 限制／NOT VERIFIED
- 非作者 QA、exact-head 五項原生 CI、main push CI **均未做**；ui2_browser 與 measure 是用本沙箱 chromium 153（符號連結至 rev 1243 以滿足 playwright 1.64.1 的路徑，**CI 容器為官方 v1.64.1 映像，瀏覽器版本不同**）。
- 全 repo 套件在匯出環境有 21 個與 git 索引相關的失敗（見 §6；已證明與本變更無關，但**CI 上實際結果未知**）。
- 第 4 列兩句 detail 以全形空格分隔、同一 `div`：390 寬度下實測換行分開；其他字型／裝置未測。
- 位階載入後恆「資料未備」係依位階契約無 `as_of`（INFERENCE：若日後位階契約新增資料日，須重審此歸類）。
- 未來資料日歸「🔴 來源目前不可用或資料異常」＝依 GPT 定稿文案；卡片文案「資料日期不可信」未改。
- Cloud 實況、#1107 Cloud 驗收：NOT VERIFIED，與本變更獨立。
- **口徑補註（2026-11-19；DEC-202；append-only；docs-only，不改任何 UI 字串／四列文案／口徑）**：
  - (a) 「資料新鮮度總覽」計的是**資料日相對規則**（資料日對基準日的新舊），**不等於**本次抓取成功。`upstream_state=FETCH_FAILED` 是**獨立事實**（見 `shared/upstream_state.py`），本計數不反映；兩者可並存且不矛盾。
  - (b) regime 有值但**無可驗證 as_of** 時，仍歸「資料未備」；畫面上「多頭」等顯示**不構成已確認資料日期**。
  - 判定依據與授權：#1199 comment 6995401840／6995747146；BACKLOG 2026-11-19 UI2-PRODUCT-CLOSURE（O1／O2）。
