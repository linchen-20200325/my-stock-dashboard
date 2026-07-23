# tab_stock.py 拆檔 Audit(v18.404 U4 Phase 1)

## 規模

| 度量 | 值 |
|---|---|
| 總 LOC | 3477 |
| `render_tab_stock()` 巨型函式長度 | L219-3481 ≈ **3262 LOC**(單一 def 內) |
| Module-level def | 1(就是 render_tab_stock) |
| 內部 section markers(`####`) | **17 個** |

## 結構切分(內部 section 列表)

| 區段 | 起始行 | 預估 LOC | 性質 | 拆檔難度 |
|---|---|---|---|---|
| 操作列 + 均線選擇 | L284 | ~350 | UI control,session state | 中(session_state 依賴) |
| 操作雷達(stopwin / stoploss / 支壓) | L639 | ~25 | 純展示 + 公式 | 低 |
| 多因子評分 | L722 | ~105 | 計算 + 卡片 | 中 |
| 心理檢查 + 勝利方程式 | L828 | ~57 | 純文案 + decision | 低 |
| 禁止操作 + 買賣訊號 | L885 | ~265 | 邏輯密集 | 高 |
| **A. 健康度評分** | L1177 | ~270 | 多 column / chart | 中 |
| 操作建議規則引擎 | L1698 | ~60 | 純規則 | 低 |
| **B. 357殖利率** | L1759 | ~423 | 計算 + 圖表 | 中 |
| **C. 財報領先指標** | L2183 | ~78 | 純展示 | 低 |
| **D. 月營收趨勢** | L2261 | ~42 | 純展示 | 低 |
| 策略1 結論 | L2303 | ~170 | 邏輯 | 中 |
| **D2. 基本面先行 6 指標** | L2473 | ~234 | 計算密集 | 中-高 |
| **AI 財報體檢(MJ 6 子段)** | L2708 | ~490 | 最複雜,跨多 expander | 高 |
| 新聞區 | L3196 | ~280 | RSS 抓取 + 顯示 | 中 |

## 關鍵障礙(為何不能像 tab_macro 簡單抽)

| 因素 | 詳情 |
|---|---|
| **無 inner def** | tab_macro 有 `_job_macro` / `_render_*` inner def 可直接 move,tab_stock 是純 inline render |
| **locals 高度耦合** | 17 個 section 共用 `df2, sid2, name2, price2, health2, rsi2, vcp2, bb2, _cur_p, _ma20_now, t2_inst, ...` 30+ locals |
| **session_state 跨段** | `_score_hist_*`, `t2_data`, `mkt_info`, `cl_data` 等多處跨段讀寫 |
| **expander 嵌套** | AI 財報體檢段內含 8+ 層 `st.expander` / `st.tabs`,結構難拆 |
| **共享 fail-safe pattern** | `_msg = _msg if '_msg' in dir() else ...` 跨段引用 |

## 拆檔藍圖(類比 tab_macro 5387→488 經驗,需 4-5 PR)

### Phase 1:Audit + 子目錄 prep(本回合,已交付)
- ✅ 結構掃描 + 17 section 清單
- ✅ 障礙文件化
- ⏳ 子目錄 prep:**待 Phase 2 啟動才建**(避免空目錄)

### Phase 2:低風險 section 抽出(1 PR / ~200-300 LOC,user 明確授權後)
- 操作雷達(L639,~25 LOC)
- 心理檢查 + 勝利方程式(L828,~57 LOC)
- 操作建議規則引擎(L1698,~60 LOC)
- C. 財報領先指標(L2183,~78 LOC)
- D. 月營收趨勢(L2261,~42 LOC)

### Phase 3:中風險 section 抽出(2-3 PR)
- 多因子評分 / 健康度評分 / B 殖利率 / 策略 1 結論

### Phase 4:高風險 section 抽出(2 PR,需 visual 驗證)
- AI 財報體檢(MJ 6 子段,~490 LOC)
- 禁止操作 + 買賣訊號(邏輯密集)
- D2. 基本面先行 6 指標
- 新聞區

### Phase 5:render_tab_stock 收尾 = orchestrator(1 PR)
類比 tab_macro 收完只剩 488 LOC `render_tab_macro()`。

## §-1 對齊

| 觸發條件 | 滿足? |
|---|---|
| user 主動要求拆檔 | ✅(藍圖 U4 + "P4" 授權) |
| 真實 bug 觸發 | ❌(現況 work,純結構性技術債) |
| 改動單元小且可驗 | ❌ 每 section 拆檔需手動驗 UI(無 unit test 可守) |
| ROI vs 風險 | ⚠️ 中(類比 tab_macro 成功經驗,但 risk 高於 U5 B3-γ) |

## 判定

✅ **Phase 1 audit 已交付**(本檔)

⏳ **Phase 2-5 動工建議**:每 phase 由 user 明確授權 + 跑完 streamlit 視覺驗證後再進下一 phase。
單次 session 內不再連續推進,避免「視覺驗證盲點」造成 UI 隱性破壞。

**目前 tab_stock.py 保持 3478 LOC,等 user 啟動 Phase 2 命令再單獨動工。**

## v18.405 進度補註

- U5 B3-δ(app.py L1 fetcher 抽 src/data/stock/app_stock_fetchers.py)已交付(獨立工作,-376 LOC)
- U4 Phase 2 真實 section 抽出仍**未啟動** — 因抽 1 段需傳 10-30+ args 並手動驗 UI,
  風險顯著高於 U5 B3-δ 的 L1 fetcher 抽出(L1 純 I/O 函式無 UI 副作用)
- Phase 2 動工時建議:每 section 一次 commit,push 後手動跑 streamlit 視覺驗收,再進下一段
