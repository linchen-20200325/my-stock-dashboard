> **歷史／適用性引言（2026-11-07 抽出）**：本檔自 Draft PR #1030（head 1e5afee1） 原內容抽出保存（來源分支 `docs/newui2-data-page-trend-onebrain-pdf-20261106`），抽出日期 2026-11-07。
> 此為歷史草案／研究材料，**不是現行施工依據**；現行方向以 DEC-142／DEC-146 與 `NEWUI2_TOP_FIVE_APPROVED_VISUAL_AND_SAFETY_GATE_2026-11-07.md` 為準。

# 第一版 Old UI → New UI2｜資料/方法/規則獨立覆核（2026-11-06）
> 來源：GitHub main `343f0e0e4072362c45bff1ccc25b61014d15c691` 的真實 code＋`docs/vnext/NEWUI2_REUSE_MATRIX_2026-11-02.md`、`docs/vnext/FINAL_UI_CAPABILITY_MAP_2026-11-02.md`、`docs/vnext/NEWUI2_REAL_FEED_MAPPING_2026-11-03.md`；後兩者僅供差距清單，不等於已完成新 UI2 接線。此文件為 read-only code audit 結果／docs-only，不修改 Old UI、不允許未核准公式或新資料源，也不聲稱逐函式窮舉。

## 一、最值得承接
| 優先 | 功能 | 實際 code 依據 | 建議 | 需驗證 |
|---|---|---|---|---|
| P0 | 財報體檢：存活能力、OCF/FCF、毛利/淨利/ROE、負債、現金流 | `src/services/financial_health_engine.py`、`shared/financial_health_thresholds.py`、`src/ui/tabs/stock_grp_sections/section_financial_health.py` | 🎯 UI 只顯示關鍵體質/失敗/趨勢、完整証據給 headless Digest/OneBrain；中性命名 | 風險：舊引擎含 LLM prompt，同一 SSOT 須回查，不應直接導入所有舊 AI 敘事 |
| P0 | 月營收＋季財報加權、跨期轉好/轉壞 | `src/compute/health/fin_trend_score.py`（legacy 65/35）；`fin_health_diff.py` | 分離 deterministic 計算與 AI 解釋，保存各期財報/現金流、改善/惡化與缺值 | 65/35 只屬**既有邏輯 FACT**，不視為新買賣門檻批准；不足資料時不得把 no_data 當中性真值 |
| P0 | 外資/投信/自營、融資、外資期貨/PCR | `src/ui/tabs/macro/section_chips.py`、`src/services/macro_refresh_service.py` | 📊 短期籌碼卡與完整 OneBrain domain pack | 資料時點、外資來源、期貨估算欄與未觀測 0 問題 |
| P0 | 集保大戶/散戶 | `src/ui/tabs/chip_radar.py`、`src/data/stock/chip_concentration_fetcher.py` | 🎯 顯示散戶人數＋大戶持股比例 | **散戶持股比例**非現有散戶人數，需另定 source/denominator |
| P0 | 美股前夜領先市場 | `shared/global_lead_markets.py`、`src/ui/tabs/macro/section_long.py` | 📊 SOX/IXIC/SPX/DJI 與台股下個交易日對齊，供 OneBrain 背景研判 | 小樣本、假日、SOX 單獨波動、現貨/期貨、no lookahead；不能直接搬「重壓/減碼」文字 |
| P0 | Risk Cap/Regime/系統動作與證據來源 | `shared/risk_cap_policy.py`、`shared/regime_arbiter.py`、`shared/decision_digest*.py`、`allocation_service` | 保持既有 Single Action Authority，不讓新 AI 敘事修改政策 | Risk Cap unavailable≠安全；顯示與實際允許執行需 QA |
| P1 | 產業熱力與法人資金流 | `shared/sector_heatmap.py`、`src/services/target_industry_service.py`、相關 `sector_flow` 服務 | 🎯 產業機會＋候選池的 Context Overlay | 資金流≠產業基本面改善、產業趨勢正式定義仍 Pending |
| P1 | 跨季基本面選股與前進式驗證 | `src/services/fundamental_screener_service.py`、`forward_test_service.py` | 🎯 候選池清單保留完整 universe 及已核准前進式結果，不只 Top10 | 凍結/Sheet 寫入為高風險，禁止默默接 |
| P1 | 市場廣度、ADL、總經 16 燈 | `src/ui/views/page_market.py`、`src/ui/tabs/macro/section_short.py`、`shared/macro_buckets.py` | 📊 UI 聚焦一屏摘要，Headless 完整資料/理由/反證 | 來源及 as_of 並非每項都有、market trend 正式定義 Pending |
| P1 | 財報前瞻：合約負債、CAPEX、營收/毛利序列 | `src/ui/tabs/tab_stock.py` 及拆分各 sections | 🎯 產業/訂單假設依實際公司證據驗證 | 訂單傳聞不是確定合約、資料/新聞來源未核准不能擅增 |
| P1 | 持股曝險與集中度、ETF 檢視 | `src/compute/risk/concentration.py`、`src/services/holdings_service.py`、ETF 既有資料服務 | 💼 直接持股與可得的 ETF 穿透分開呈現 | 穿透成分及更新日不可靠時必標 coverage 缺口 |

## 二、不能直接沿用/風險
1. **舊 UI action/strategy 文案混用不同權威**：`section_chips.py` 有籌碼建議姿態；`section_long.py` SOX×DXY 有「重壓/減碼」；不能升成正式 New UI2 Action，應當 Context 或依現有 Single Action Authority。
2. **缺資料冒充中性/安全**：舊系統本身留下修復註解（法人 missing 被預填 0、財報缺營業現金流及負債分母等）；任何 readout 都須現場檢查缺值完整性和 fallback 是否污染判定。
3. **前夜美股預測有實證限制**：`global_lead_markets.py` 既有研究與回測明確顯示 SOX 單跌不等於台股必跌，市場共振才可能更有意義；樣本不足做無條件概率。
4. **大盤 EPS×PE**：舊 UI 沒有正式大盤 forward EPS 可持續來源，僅研究方法／提案；不可用 PDF 機構情境點數填正式行情或價格目標。
5. **財報評級專業適用性**：負債/流動比等固定門檻對金融業、不同商業模式未必同義；`FH_*` 是 existing contract，若提出跨產業改法必須獨立 Domain Gate、OOS／回歸測試。
6. **舊 AI 外部資料能力**：`financial_health_engine.analyze_financial_health` 內曾直接呼叫模型；UI2 OneBrain 必須只吃核准 Evidence，不應直接讓該服務取得自由搜尋工具或外部來源。

## 三、三路線比較與建議
| 方法 | 速度/Token | 風險 | 建議 |
|---|---|---|---|
| A 整段複製舊 UI 渲染/Prompt | 初期快，之後返工高 | 舊缺值、動作文案、Streamlit 耦合帶入 | 不採 |
| B 逐模組全重寫 | 高成本 | 公式漂移、破壞舊介面及測試 | 不採 |
| **C 沿用確定性核心＋薄的 headless read-only feed＋UI 精簡 projection** | 可逐項搬、token 可控 | 仍需每項 lineage QA | **推薦** |

## 四、實作前 Gate
- 各 feature 做 production producer → canonical → domain rule → Existing Digest → UI2 VM → OneBrain consumer 的雙向核查；具名 source/date/denominator/缺值行為。
- 分頁 OneBrain scoped evidence packs＋全域複查；Required Evidence coverage 可驗證，不因前端少畫項目而漏給 AI。
- 與既有 #1022/#1027/#1029/#1030 及 Work A 資料清理 PR 協調，Claude 實作優先，避開其當前檔案。
- 先 docs/視覺 Gate、後 presentation-only 實作，再資料接線；Risk Cap/投資公式/AI runtime 權限另走 High Gate。
- 不要改 Old UI；真正舊功能可復用的接口需由新薄層承接，禁止新增重複事實。
