# PR #1038 macro-forward-test｜Parquet 逐列比較與 PIT 靜態驗收（2026-11-07）

> **結論：BLOCK / 不得合併 #1038 作為 2026-11-05 時點合格快照。** 本證據是 ChatGPT 透過 GitHub 直接讀取 main 與 PR head 的 Parquet 二進位、解碼資料頁、對照現有資料契約的獨立唯讀稽核。不是 producer 即時網路重跑、不是全部外部來源授權／可得時刻認證、不是金融模型新裁示。此報告 docs-only；不得藉此新增正式投資門檻、Risk Cap、Schema 或重新寫入凍結帳本。

## 1. GitHub 取證定位

- Repo：`linchen-20200325/my-stock-dashboard`。
- 比對 main：`10159688a7495dc554e545fbe9992f8863ba7886`。
- PR：[#1038](https://github.com/linchen-20200325/my-stock-dashboard/pull/1038)，head `9e7014c70a2fcda42d4bb14e2a044e6ec4b4057e`，branch `auto/data-macro-forward-test`，Draft。
- 相對本次 main：ahead 1／behind 6；PR 只改 `data_cache/macro_forward_test/signals.parquet`；binary patch 無文字 diff。
- main 該 blob SHA：`4748f3f0709dcf507ef790278ce1c8ddface7e82`；PR head blob SHA：`989d40302209d6ed15cb6f301e65b2b529769e26`。
- PR head 的 `PR Check（pytest fast + AppTest slow）` run `42257100931` success；review threads 0。**CI 綠燈不代表資料逐欄／PIT 正確。**

## 2. 二進位實檔解析與 diff

- 兩檔均具 `PAR1` header/footer；解讀 Parquet FileMetaData、row group/column chunk、dictionary + Snappy data page。
- main 47 列 → head 48 列；欄位均為 25 個，欄位名稱／物理型別／nullable 結構未見變更。
- 23 個 dictionary-encoded 欄位逐欄／逐行解碼，**原有前 47 列全部值一致**（含 null）；另外 2 個布林欄（`defense`, `health_partial`）解碼 PLAIN bit-packed data page，既有 47 列位元未變。新列 `defense=False`、`health_partial=True`。
- 只新增觀測鍵 `2026-11-05`；既有記錄未被本 PR 更改。這是資料完整性方向的 PASS，不表示新列 PIT 合格。

## 3. 新增的第 48 列（直接由實際 Parquet 解碼）

| 欄位 | 值 |
|---|---|
| `date` | `2026-11-05` |
| `captured_at` | `2026-11-07T00:56:24+08:00` |
| `date_source` | `live_as_of` |
| `inputs_as_of` | `2026-11-05` |
| `score_index_as_of` | `2026-11-05` |
| `inst_as_of` | **`2026-11-06`** |
| `adl_as_of` | `2026-11-05` |
| `li_as_of` | **`2026-11-06`** |
| `icon` / `label` | `⬜` / `總經未評估｜資料不足` |
| `effective_regime` / `regime_source` | `unknown` / `unevaluated:breadth_unavailable` |
| `health` / `health_partial` | `null` / `True` |
| `score` / `max_score` | `0` / `null` |
| `jqavg` / `conf` | `null` / `60` |
| `twii_close` | `41574.71875` |
| `git_sha` / `ruleset_hash` / `schema_version` | `8d95847f` / `6c716f5411fb` / `3` |
| `missing_sources` | 明示官方市場廣度未有有效來源，代理 ADL 不計分（DEC-074） |

`conf_groups` 三項為 true，但不等於正式資料完備；本輪不自行推論其語意有效性。PR body 寫 `fetched_at=n/a`、`published_at=n/a`（來源未提供），不能據此推知每項來源確切公開時刻。

## 4. 風險判定

1. **PIT FAIL / 不准作 2026-11-05 當時可知的預測快照**：該行 `date=inputs_as_of=2026-11-05`，但 `inst_as_of=li_as_of=2026-11-06`，同時 `captured_at=2026-11-07T00:56:24+08:00`。依 `src/compute/macro/macro_forward_test.py::leg_as_of_from_inputs`，四腿資料日是實際取得腿的觀測日期（其中 `inst_date` 僅在 `inst` 非空時採用）。若將這筆作 11/05 時點回測或模型訓練，存在未來資訊混入風險。只有進一步證明研究視窗與可得時點合規，才能限定用途；不可把事後抓取的多腿資料當成 11/05 已知。
2. **未評估／0 分語意需獨立下游驗證**：新增列 `effective_regime=unknown`、`health=null`、`max_score=null`、`score=0`；`build_signal_row` 原樣保留合法的零值，不能直接斷言是公式 bug。但下游必須確保 `score=0` 不被渲染成已完成 0 分／安全／中性，也不進需要完整評估的正式 action/precision 統計。
3. **另有真實程式風險（待工程故障注入）**：`src/data/macro/macro_fwd_test_store.py::load_signals` 遇到已存在但不可讀的 Parquet 會 `return []`；`append_signals` 可能視為無歷史，`to_parquet` 覆寫原檔。此為靜態可達路徑，未做 fault-injection，不得宣稱已在真環境發生；修復應 fail-closed、保留 bytes。

## 5. 原有程式契約與本輪限制

- `scripts/update_macro_forward_test.py` 原已要求 TWII 日期及收盤後條件；現行程式讀取 bundle 的當下各腿，並未證明所有腿皆 `<= date`。
- `src/compute/macro/macro_forward_test.py::build_signal_row` 僅保證 `date_source=live_as_of` 時 `date==inputs_as_of`；其 `leg_as_of` 描述是「純觀測，不參與判斷」。這不構成歷史 PIT 驗證。
- `scripts/publish_data_pr.py` 設 `LEDGER_PATHS` 保護同 key 不被覆寫，但不足以保證 producer 自己載入既有壞檔時不覆寫。
- 本輪以 GitHub 來源檔及 Parquet 二進位快照做靜態比較，**未有外部發布時刻原始證據、未執行官方 live API、未執行 production pipeline、未驗 Cloud 真機**。

## 6. 安全下一步（工程需獨立 branch/PR，無合併權）

A. **P0 最小 code patch**：保護 `load_signals`／`append_signals` 的既有損壞/不可讀檔，拒絕寫入並保留原始 bytes；測正常首次建立、重複日期、追加日期、損壞與權限異常；targeted、mutation、非作者 QA、CI。

B. **P0 PIT gate 方案**：先為 `macro_forward_test` 定義清楚「交易日觀測」與「多腿實際可得時間」的資格／降級契約。對有未來腿的列，禁止用於按 `date` 的歷史預測統計；可選研究-only 獨立標示或阻止發布，**不可自行改金融公式、Risk Cap、計分權重、schema 或重寫 frozen ledger**。此部分需 Decision Gate 後再動 producer/code。

C. **PR #1038 處置**：保留 Draft；不可直接合併。若確認新增資料不符合帳本用途，先提出關閉而非覆蓋歷史列或偷偷刪檔。寫入 main 前重新驗當下 GitHub、head、required CI、獨立 QA、資料日期與 producer 合約。

> 本報告只記錄已證明的差異與尚需驗證的風險；不代替客戶新的投資語意或正式架構裁示。
