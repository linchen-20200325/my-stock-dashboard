# New UI2 — UI × Data × Evidence 串接規劃（2026-11-04）

> 本文件是唯讀「接線規劃附件」，不是新 Decision、不是第二套 Data SSOT，也不授權任何實作。基準 main de5f272e734bad0b5de48096586c7bd5aa0a19bd（#1006）。證據來源：NEWUI2_REAL_FEED_MAPPING_2026-11-03.md §3–§4、NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md、NEWUI2_UI_EXECUTION_SPEC_2026-11-04.md、已查的 real_feed.py/real_canonical.py。若資料／程式已變，以實際 GitHub code + CI 優先，不可依本規劃假定已接。
>
> **只有 TWII 最新收盤、Regime 市場位階兩個已接 Real Feed 事實**。其他 service 只是已存在候選，不代表正式可讀、已完成 PORT 或獲授權。完整資料與 Missing、provenance、反證保留供 headless Decision Digest；OneBrain 不讀 Human UI slice。

## 1. 串接分類

- A 已接：現行 UI2 real_feed/read_real_snapshot 已驗證的 TWII 收盤、Regime（一次 rerun 一份 snapshot）。
- B 已有 service 但未接：需檢查 I/O、Session 副作用、OAuth、as_of、契約。
- C PORT：仍在 L5 舊 UI 或 Session/readiness 的運算，須先轉正式純 canonical service，UI 不得複製算法。
- D Data Gap：無 canonical 欄／無正式公式、口徑或資料分母；不准補值或自造。
- E 正式限制：Risk Cap、System Action、OneBrain、寫入 CTA、研究框架尚未核准啟用。
- Data State 五態 OK/Missing/Stale/Unavailable/Not Evaluated ≠ Capability 尚未接線；請依 DEC-130 分開兩欄。

## 2. 📊 市場 — 畫面位置 → 真實讀點

| 位置 | 原 Mapping | 正式讀點／候選 | 狀態 | UI 與 Evidence 護欄 |
|---|---|---|---|---|
| 目前市場狀態、跨頁環境 | M1/M1b/T2/T18 | allocation_service.get_macro_regime(strict=True, require_valid_risk_cap=True) → 同一 RegimeFact | A | source 是規則分支 ID，非行情來源；無 as_of。冷啟動或廣度不足＝不可判定；完整 Explain 留 Evidence／健康度，不畫 L2 expander |
| 台股最新收盤卡 | M8 | market_twii_view_service.get_twii_trend_view(1) → TwiiFact | A | source、as_of、is_stale、age_days 可讀；retrieved_at 未提供；不可手填今天 |
| 台股歷史主圖、MA | 主圖 | 既有 TWII reader 目前只取 1 日；歷史序列／MA contract 待查 | B | 不複製收盤填圖，不自造 MA 算法；缺正式序列保留誠實空槽 |
| 今日結論／主要風險 | M6/M7 | shared.market_conclusion.build_market_conclusion；L5 page_market、_market_blocks 內的子句／風險 | C | 先 PORT 並保留逐字退化句；不只憑 Regime 編造結論 |
| Risk Cap／行動／下一步 | M2–M4 | 已核准無法判定文字；System Action Aggregator 待建；W-10 過渡警示 | E | 不把舊警示 N 當正式 System Action，不推出加碼、安全或今日無需調整 |
| VIX／US10Y／DXY | M9/M10/M12 | readiness、macro_info Session／compute_five_bucket_summary | C | 單一 canonical 入口待決；as_of 和 stale 必須獨立驗證，不直接從 UI 讀 Session |
| 利差 | M11 | 無正式 canonical spread 欄 | D | 不自行定 tenor 或算 US10Y－任意利率；先 Data Gate |
| PMI／景氣 | M13 | readiness ism_pmi（台灣 PMI）、ndc_signal（景氣）、tw_pmi.parquet | C/D | 台灣 PMI≠美國 ISM≠NDC 景氣燈號，須分來源及資料頻率 |
| 國際比較／VIX 帶／Macro mini | 各圖 | 逐圖待確認既有資料及時間軸 | B/C | 不混單位、不隱藏缺值；SPEC 含期間、base、as_of、來源 |
| EPS×PE 大盤 | 研究槽 | 研究框架，正式訊號尚未核准 | E | 不自動產生大盤目標價、Risk Cap 或正式動作 |
| 更新戰情／OneBrain | M5/M14 | macro_refresh_service.refresh_macro_now 會連網寫檔；Digest Stage G | E | Preview read-only 不直接呼叫 producer；AI 未啟用顯示未提供 |

## 3. 🎯 標的

| 位置 | 原 Mapping | 來源候選 | 狀態／施工限制 |
|---|---|---|---|
| W-4 市場環境 | T2/T18 | 與市場頁同一 RegimeFact | A；跨頁一致，不另算 |
| 精選候選 Top10 | T1/T7 | fundamental_screener_service.get_ranked_picks；L5 page_find；picks.parquet 為不同凍結語意 | C；A 成長/B 價值、排序規則、資料日必先核對，不能以歷史凍結值冒充即時 |
| 產業 Top5 | T6 | sector_flow_service.get_sector_flow_view(use_active_selection=False 等)＋L5 rank_industries | B/C；排序尚未 PORT，來源已有不等於排名獲核准 |
| 即時查一檔 | T10–T12 | stock_names、查詢服務待驗 | C/D；未真查詢不得顯示假 ticker；名稱搜尋未備明示 |
| 6 維基本面 | T13/T16–T18 | financial_health_engine；Regime；趨勢／產業仍有未定義契約 | C/E；先確認 EPS/財報年度、來源、有效性，不能自行新增評分 |
| 估值／EPS/PE | T14 | valuation_service.get_pe_name_maps/get_stock_dividends | B/C；PE 基期、負 EPS、價格與財報日期、預估性質，缺正式公式不得輸出合理價／目標價 |
| 籌碼與法人 | T15 | stock_chips_service.get_chips_readout | B/C；頻率、買賣單位、as_of、missing 要可追溯，不能推出正式買賣命令 |
| 全部候選／CSV／選股條件 | T8/T9 | L5 page_find | C；保留使用者功能但不要做 raw evidence wall |
| 加入觀察、研究解釋、跨季趨勢 | T19/T20 | watchlist write；OneBrain Stage G；趨勢使用者功能待裁示 | E；寫入 disabled，Pending 不冒充核准 |

## 4. 💼 持股

| 位置 | 原 Mapping | 來源候選 | 狀態／施工限制 |
|---|---|---|---|
| Portfolio 與持股表 | H1/H7 | holdings_service.get_holdings（OAuth/Sheet）、portfolio_binding_service、dividend_station_service.get_station_rows（網路） | B，OAuth／Sheet Gate；讀取副作用和原資料時間必查 |
| 績效／benchmark／產業曝險／集中度 | Portfolio Overview | 持倉、價格、成本等候選；尚未逐圖完成 canonical 驗證 | B/D；不自行定幣別、分母、現金、報酬基準 |
| Risk Cap／目前曝險 | H2/H3 | Risk Cap 固定無法判定；現金／總資產分母尚無 | E/D；不以持股成本冒充總資產，不以未知當未超限 |
| 今日需處理／加減碼／下一步 | H4/H5 | System Action Aggregator 未備 | E；不可在 UI 生「減碼 1/2」「全出」，須有單一正式動作權威 |
| 更新持股、OneBrain、規則明細 | H6/H8–H10 | 更新 producer、Digest、既有 80/20/停利/VaR | E/B/C；寫入需 Gate，使用者分析保留精簡呈現，完整 RuleID/Evidence 留 Digest |

## 5. 👤 我的與左側帳號

| 位置 | 原 Mapping | 來源候選 | 狀態／施工限制 |
|---|---|---|---|
| 桌機 rail Login/Auth Status | E1/E7 | me_account_service.get_account；已知部分 OAuth 讀路徑可能寫 _oauth_state | B，需正式 Auth Gate；FAKE／query parameter 不是登入證據 |
| Sheet／portfolio／watchlist | E2–E7 | get_sheet_view、get_sheet_contents、portfolio_binding_service | B；不得暴露 Sheet ID 全碼，session 語意依正式 contract |
| 設定、通知、顯示偏好 | E8–E10 | 正式 settings canonical 未找到，尚非窮舉結論 | D；不新增第二個 storage |
| Decision Digest Viewer／Rule Registry | E11/E12 | decision_digest_builder、shared.decision_digest_rules.RULE_ID_ALLOWLIST | E/B；稽核面預設收合，完整 Digest 不從 UI sections 構成 |
| Data Freshness／健康度 | E13/E14 | data_registry_summary_service.summarize_data_registry(session)、metadata.json reader、calibration_status_service | B/C；canonical 缺 retrieved_at/source health 時顯示未提供，不能拿 now() 補 |
| 資料健康度 Level1/2/3 | Active Contract §5.1 | 正式 health facts 的唯讀 projection | P6；Data State 與 Capability 分欄；L3 預設收合並 scrub secrets；L1/L2 預設展開仍 Pending |
| 統一重新取數 | 健康度 CTA | 既有 refresh/cooldown pipeline | E；只有正式安全契約才啟用 |

## 6. 每一張主要圖都要填寫 Data Contract

chart_id／位置／visual rank；正式 canonical service + field/type；是否 I/O 或寫 Session；實際序列長度與 trading-date/frequency；單位／幣別／基準日和 normalized base；正式算法及 RuleID；source/as_of/retrieved_at/freshness；Missing/Stale/Unavailable 的斷線策略；Human UI 的 SPEC 行；Decision Digest 對應 evidence/反證；390px/1440px 截圖、no-write、跨頁一致性、倒序時間與缺值測試。缺任何正式必要欄位時先誠實空槽，不能讓 UI 畫假圖。

## 7. 三路徑比較和安全交付

對每個 B/C/D 缺口先比較：A 沿用安全的既有 canonical；B 將舊 L5/session/readiness PORT 成可驗的正式 L3 service；C 增加新 API／資料源（需新來源 Gate）。排序先「投資語意正確與不造成副作用」，再比較速度、維護成本與 Token。不能因 A 最快而用錯來源。

**協作邊界**：此文件是 docs-only 規劃，不動 src/shared/tests/BACKLOG/HANDOFF/PROJECT_STATE（P1 agent 正在施工），也不授權新增 Real Feed。本表只有 A 類為已證實 New UI2 Real Feed；每個後續接線批必須再由 Claude 雙向驗證「UI→VM→canonical」與「canonical→所有消費者」，報出 Ready/Blocked/Need Decision，逐批 ≤3 項；涉及 Auth、Risk Cap、System Action、Digest schema、新算法／來源，先 STOP → Opus High／Decision Gate。

**尚待補的優先缺口**：TWII 圖歷史期數／MA、VIX US10Y DXY 唯一入口及 as_of、利差 tenor、PMI 口徑、候選 A/B 排序、EPS/PE 時間基礎、OAuth side effects、現金／總資產分母、資料健康來源時間。來源或語意未驗不填零、不填 neutral、不冒充 safe。
