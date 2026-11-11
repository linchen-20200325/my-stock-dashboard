# Digest `market.regime`／`market.light` 詞彙相容性 Gate（唯讀研究）

> **基準**：main `1e5542a8`（#1142 合併後；#1141 為 `907322aa`）　**量測日**：2026-11-11
> **授權來源**：GitHub Issue #1140 §D（客戶裁示轉錄；見 `docs/DECISIONS.md` DEC-164）。「Digest regime/light 先做相容性 Gate，不改凍結 Schema。」
> **本檔性質**：docs-only 研究。**不是施工授權**；不改 `src/services/decision_digest_builder.py`、`shared/decision_digest*.py`、`macro_state_locker.py`、任何測試。不升 Digest v2、不建 production caller、不建 OneBrain runtime。
> **查證方式（據實）**：多組獨立研究與複驗（過程見 session，非 repo 證據）；§2–§5 為已複驗 FACT；§6 的測試轉紅數為作者端原型實測（未複驗，INFERENCE）。未跑全 repo 測試；環境 Python 3.13（非 CI 3.11）。

## 0. 結論先行

| 項目 | 結論 |
|---|---|
| 缺口是否存在 | **是（FACT）**：builder 對 `market.regime`／`market.light` 只做**非對稱黑名單**，名單外任何非空字串都會逐字成為 `status=OK` 的 Fact；下游（schema 檢查、validator、grounding、coverage、assembly、summary）都不檢查其值 |
| 現行線上是否已出錯 | **目前不是（INFERENCE）**：production 對 `build_decision_digest`／`assemble_digest` 為 **0 caller**，且已知寫入端皆為封閉集合；屬**防禦性缺口，非現行線上錯誤**（未窮舉所有寫入點） |
| AI 推薦（**RECOMMENDATION，非客戶裁示**） | **方案 A2**：在 builder 輸入邊界以由 `REGIME_LIGHT` 推導的白名單驗證（比對用 `strip().lower()`，Fact.text 仍逐字保留）；名單外 → `INVALID`，既有佔位字 → 仍 `MISSING`。不碰任何 `shared/decision_digest*.py` 凍結檔 |
| 本批是否實作 | **否**。Issue 授權僅限研究；實作 builder 屬改動 Digest 家族行為，**須客戶裁示（Decision Gate）** |
| 另登記 | `get_macro_state` 對非 canonical `effective_regime` 洗成 `neutral` 且 `is_loaded=True`、`light` 直通、`market.health` 無範圍檢查——**已知缺口，本批不動**（見 §7） |

## 1. 標示規則

| 標示 | 意義 |
|---|---|
| **FACT** | 對照程式／實測所得，並經獨立複驗 |
| **INFERENCE** | 由 FACT 推得；未窮舉或單組判斷 |
| **RECOMMENDATION** | AI 總管建議，**不是客戶裁示** |
| **NOT VERIFIED** | 未實測 |

## 2. 成因（FACT）

| 位置 | 行為 |
|---|---|
| `src/services/decision_digest_builder.py::_market_section`（內部 `text_fact`）、`_text_or_none` | `market.regime` 僅擋 `{'unknown'}`（`_UNEVALUATED_REGIME`）＋AB-0 `PLACEHOLDER_TEXTS`；`market.light` 僅擋 `{'⬜'}`（`_UNEVALUATED_LIGHT`）＋`PLACEHOLDER_TEXTS`。實測 `regime="⬜"` 仍為 OK（regime 的黑名單不含 `⬜`） |
| 名單外輸入 | 載入中／待評估／pending／loading／foo／TBD／Bull／多頭… 等任何非空字串，**逐字**成為 `status=OK` 的 `Fact.text` |
| `shared/decision_digest.py::_check_fact`、`decision_digest_rules.py`、`decision_digest_validator.py::assess_digest`／`_own_checks`、grounding、coverage、assembly（只看 `_all_ok`／證據）、summary | **皆不檢查** regime／light 的值 |
| 下游實測 | `build_rule_summary` 會印出「市場位階：載入中（資料日 …）」；`assemble_digest` 市場段 `used=True` |

## 3. 上游（FACT）

| 位置 | 行為 |
|---|---|
| `src/services/macro_state_locker.py::get_macro_state` 快路徑 | 對非 canonical `effective_regime` 經 `normalize_regime` 洗成 `'neutral'`（`is_loaded=True`）；`light` 直通 `warroom['light']`、不驗，可與 regime 矛盾。**`get_macro_state` 快路徑須 warroom 帶 `health_score` 鍵；缺此鍵會落入 unknown／is_loaded=False** |
| `macro_state_locker._REGIME_EN` | `("bull","neutral","caution","bear")` 共 4 個＝`REGIME_LIGHT` 去掉 `unknown`（設計如此） |

## 4. 曝險與 SSOT

**曝險（FACT＋INFERENCE）**

| 項目 | 內容 |
|---|---|
| FACT | production 對 `build_decision_digest`／`assemble_digest` **0 caller**；`tests/test_decision_digest_invariants_guard.py` C2 釘住（僅掃 `.py`／`.yml`／`.json`／`.toml` 與 importlib） |
| INFERENCE | production 寫入端（`calc_traffic_light`→arbiter 等）皆為封閉集合 → 目前是**防禦性缺口**；**未窮舉所有寫入點** |
| 風險情境 | 未來有人建 caller、或上游新增寫入點／手動餵入時，垃圾字串會以 OK 事實進入摘要（§1 Fail Loud 精神：把「未知」偽裝成值） |

**SSOT 現況（FACT）**

| 集合 | 內容 |
|---|---|
| `shared/regime_arbiter.py::REGIME_LIGHT` | bull/neutral/caution/bear/unknown → 🟢/🟡/🔴/🔴/⬜ |
| `allocation_decision.REGIME_LABEL`、`decision_digest_terms.STATE_WORDS_LATIN` | key 集合與 `REGIME_LIGHT` 相同 |
| `macro_state_locker._REGIME_EN` | `REGIME_LIGHT` 去 `unknown` |
| 互相釘住的測試 | **無**（四份集合無等式測試） |

## 5. 受影響清單與既有測試覆蓋／缺口（FACT）

| 編號 | 項目 | 現況 |
|---|---|---|
| G1 | 名單外字串反例測試 | **無** |
| G2 | **反向**測試：有測試釘住「任意字串逐字保留」 | builder 測試 `regime="Bull"` 逐字斷言；summary 的 `tests/test_decision_digest_summary.py::test_unusual_but_legal_digest_texts_are_carried_verbatim_and_pass_self_check` |
| G3 | regime／light 配對一致性 | **無測試** |
| G4 | assembly 對垃圾值的反例 | **無** |
| G5 | `get_macro_state` 非 canonical 輸入測試 | **無** |
| G6 | 四份 regime 集合等式守衛 | **無** |

**Issue #1140 §D 要求的三項對照（皆已在本檔其他節，此處僅索引）**

| 要求 | 所在 |
|---|---|
| 既有拒用位置 | §2（`_text_or_none`／`_UNEVALUATED_*`／AB-0 `PLACEHOLDER_TEXTS`；其餘層皆不檢查值） |
| 輸入來源 | §3（`get_macro_state` 快路徑、`warroom['light']`、`_REGIME_EN`） |
| 受影響 caller | §4（production 0 caller，C2 守衛釘住；風險為日後新增 caller） |

## 6. 三方案比較

| 面向 | **A 上游輸入邊界驗證（builder 白名單）** | **B 強化 validator（`_own_checks`）** | **B' 放 `validate_strict`** | **C 等 Digest v2 正式驗證（Stage F G-F4）** |
|---|---|---|---|---|
| 作法 | `decision_digest_builder.py::_market_section` 內 `text_fact` 新增 `_VALID_REGIMES`／`_VALID_LIGHTS`（由 `REGIME_LIGHT` 推導）；名單外→`INVALID`；既有佔位字仍→`MISSING` | 在 `shared/decision_digest_validator.py::_own_checks` 檢查值 | 在 `validate_strict` 檢查 | 待 v2 schema／compat／PIT Gate |
| 正確性／安全 | 源頭攔截，壞值不進 Digest | **事後**攔截：builder 仍產出 OK Fact；`assemble_digest` 不呼叫 validator，coverage 仍 `used=True` | builder 對垃圾改 raise；`assess_digest` 路徑無保護 | 缺口持續到 v2 |
| 向後相容 | **嚴格相等版**：1 條既有測試轉紅（`Bull` 逐字斷言）；**A2（`strip().lower()` 比對、text 仍逐字保留）：0 條轉紅**（**INFERENCE／作者端原型實測，未複驗**；約 1641 條相關測試） | **INFERENCE／作者端原型實測，未複驗**：**16～17 條**既有測試轉紅；且一個壞字串會讓整份 Digest 輸出 **0 段** | 同上類風險，且與 builder「降級不崩潰」衝突 | 不適用 |
| 改動範圍／凍結契約 | 單檔（builder）；**不碰 `shared/decision_digest*.py`** | 碰凍結 validator 家族 | 碰凍結 validator 家族 | 需 v2 Gate（本批不授權） |
| 速度／Token／維護 | O(1) 集合比對；白名單由 `REGIME_LIGHT` 推導，**不新增第六份真相源** | 規則散在 validator | 同左 | — |
| 風險 | 低；INVALID 語意與既有先例一致（`market.health` 非有限、`risk_cap.*_pct` 越界 → `_invalid`） | 中高：大範圍測試轉紅、整份 Digest 歸零 | 中高 | 缺口持續（目前無 caller，風險可控） |

## 7. 推薦、測試規格與已知缺口

### 7.1 推薦（RECOMMENDATION，非客戶裁示）：方案 A2

| 項目 | 內容 |
|---|---|
| 理由 | (1) 唯一不碰凍結檔；(2) 與 builder「降級不崩潰」一致；(3) 與 UI2 `validate_regime_fact` 白名單前例概念同向（`validate_regime_fact` 為違反即 raise `RealFeedContractError`，A2 為降級成 INVALID，語意不同，僅概念同向）；(4) 白名單由 `REGIME_LIGHT` 推導，不新增真相源；(5) INVALID 語意與既有先例一致，MISSING 保留給既有佔位字 |
| 落點 | `decision_digest_builder.py::_market_section` 內 `text_fact`；新增 `_VALID_REGIMES`／`_VALID_LIGHTS` |
| 可選 A3 | 配對一致性（`light == REGIME_LIGHT[regime]`）；**未原型** |
| 狀態 | **本批不實作，等客戶裁示** |

### 7.2 需新增的獨立反例測試規格（若日後獲裁示實作；8～10 條）

| # | 測試 | 目的 |
|---|---|---|
| 1 | 垃圾值參數化（載入中／待評估／pending／loading／foo／TBD／⚪ 等）→ `market.regime`／`market.light` 為 `INVALID` | G1 |
| 2 | 正向對照：`regime='caution'` 配 `light='🔴'` → OK 且 text 逐字 | 防誤殺 |
| 3 | 大小寫／空白變體（`' Bull '`）：比對通過、`Fact.text` 逐字保留（A2 語意） | 相容 G2 |
| 4 | 未載入（`is_loaded=False`）／無 stamp → 仍 `MISSING`（非 INVALID） | 語意不變 |
| 5 | 既有佔位字（AB-0 `PLACEHOLDER_TEXTS`）→ 仍 `MISSING` | 語意不變 |
| 6 | 端到端：垃圾值餵入後 `build_rule_summary` 輸出**不含**該垃圾字串 | 下游 |
| 7 | assembly：垃圾值時 `market.used=False` | G4 |
| 8 | SSOT 守衛：`_VALID_REGIMES == set(REGIME_LIGHT) - {'unknown'}`；四份 regime 集合等式守衛 | G6 |
| 9 | （若採 A3）配對不一致 → INVALID；`unknown`／`⬜` 配對仍 MISSING | G3 |
| 10 | 突變測試：拔掉白名單檢查，上述反例必須轉紅（v3 §03-1） | 守衛有效性 |

### 7.3 已知缺口登記（本批不動；不建議動 `normalize_regime`）

| 缺口 | 說明 |
|---|---|
| `get_macro_state` 洗 neutral | 非 canonical `effective_regime` 經 `normalize_regime`「寧中性」洗成 `'neutral'`，且 `is_loaded=True`（§1「不知道偽裝成震盪」）；該行為**被測試釘住、舊 UI 大量使用**，不建議改 |
| `light` 直通 | `warroom['light']` 不驗，可與 regime 矛盾 |
| `market.health` 範圍 | 僅檢查有限數，`150`、`-5` 仍 OK |

## 8. 查證範圍與未驗證項（據實）

| 項目 | 狀態 |
|---|---|
| 成因、上游、SSOT、覆蓋表（§2–§5） | 多組獨立研究與複驗（過程見 session，非 repo 證據）（FACT） |
| 方案 A／A2／B 原型測試轉紅數（§6） | INFERENCE：作者端原型實測，未複驗（約 1641 條相關測試；**未跑全 repo 測試**） |
| 執行環境 | Python 3.13，**非 CI 3.11** |
| 「0 caller」範圍 | 僅 `.py`／`.yml`／`.json`／`.toml` 與 importlib |
| 全形字元／VS16 emoji 變體 | **NOT VERIFIED**（行為未驗） |
| 其他 regime／light 寫入點 | **未窮舉**（INFERENCE） |
| 瀏覽器／Cloud／真機 | 不適用／NOT VERIFIED |

## 9. Decision Gate（待客戶裁示）

| Gate | 問題 | AI 推薦（非裁示） |
|---|---|---|
| **DG-DIGEST-A2** | 是否授權在 `decision_digest_builder.py` 實作方案 A2（含 §7.2 反例測試）？ | 授權 A2；A3 配對一致性另議；不動 `normalize_regime` |
| 附帶 | `market.health` 加範圍檢查（0..100）是否同批納入？ | 另議，不夾帶 |

> 無客戶裁示前不動工（`CLAUDE.md` §-1）。
