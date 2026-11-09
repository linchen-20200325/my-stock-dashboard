# New UI2｜台股日 K 來源補充：舊 UI FinMind 證據（2026-11-09）

> **使用者方向**：台股大盤日 K 採紅漲綠跌；來源優先既有 Yahoo 加權指數日 OHLC 快取，FinMind 作後續對帳／備援候選。此前選 B「先看手機／桌機 HTML 視覺稿」依然有效；此文件**不授權**修改 UI2、資料、測試、排程、公式或付費升級。本文只讀 main `5588a72` 原碼，沒有執行 API/Token 請求；使用者實際 FinMind 權限 **NOT VERIFIED**。

## 1. 舊 UI FinMind 實際做什麼
| 能力 | Repo 證據 | 結論 |
|---|---|---|
| 個股 K 線 Yahoo 備援 | `src/data/stock/picker_fetcher.py::_finmind_raw_to_close_df` 與 `src/data/core/data_loader.py::_fetch_finmind_price_raw`，後者呼叫 `dataset=TaiwanStockPrice`, `data_id=stock_id`；原始 open/max/min/close，並標 source/fetched_at | **確有 FinMind 個股日 K**，但不可誤稱已接 FinMind 加權指數日 K |
| 加權指數日 OHLC | `src/services/macro_v2_service.py::get_twii_ohlc(n_trading_days)` 從 `data_cache/twii_ohlcv.parquet` 回 xs/open/high/low/close | 本地資料已可形成大盤 K 棒，但該 service **未帶** is_stale/as_of/upstream_state，不是 UI2 現行准入 L3 |
| UI2 已接 | `src/services/market_twii_view_service.py::get_twii_trend_view` 僅 close 與新鮮度；`src/services/ui2/real_feed.py::TWII_CARD_DAYS=1` | 不可把「已接收盤價」當「已接 OHLC」；加性 canonical schema/G2F/負向測試須重新核准 |

## 2. FinMind 官方資料集為研究候選（未測使用者帳戶）
- `TaiwanStockPrice` 用於個股價格資料；不能直接當 TAIEX。
- `TaiwanStockKBar` 配合 `data_id=TAIEX` 有加權指數分鐘 K 研究路線；若要當日 K，需確認 API 資格/配額、分鐘資料完整、開盤/收盤時點及日線彙總口徑。不得將不完整盤中 K 當已收盤。
- 以上資料集、等級和成本須以最新官方規格及使用者帳戶實際回應核實，**不假設已可用，也不自動開通付費**。
- 官方查證入口：https://finmind.github.io/tutor/TaiwanMarket/Technical/ 。

## 3. 三方案比較
| 方案 | 正確性/風險 | 速度/Token | 建議 |
|---|---|---|---|
| **A：既有 Yahoo 日 OHLC parquet → 增量唯讀 L3+freshness → UI2** | 既有 daily history/cron，新增面最小；需驗 OHLC 四欄、未完成棒、資料日、stale 與 TWII 卡一致性 | **最快、最省** | **首選作為後續施工提案，不是目前施工授權** |
| B：FinMind TAIEX 分鐘 K 經驗證後彙總日 K | 要查權限/額度/資料完整度/時區，來源口徑與 Yahoo 可能不同 | 中慢、較高 | 後續對帳/備援研究 |
| C：研究 TWSE 官方加權指數日 OHLC | 權威性有潛力，但 API 能力和 PIT 仍 NOT VERIFIED | 中慢、中 | 並行研究 |

## 4. 下一個 Gate
#1097 是 docs-only 視覺 Gate。客戶先審 390×844、1440×900 的 FAKE HTML 草稿，確認 K 色語意（收>開？或對前收？）、手機預設可見棒數、220px 圖高及操作；之後方可核准施工。需要新 L3、VM OHLC、fail-closed、stale、當日未完成 K 棒阻擋、G2/G2F 負測、獨立 QA、最新 head 五項 CI。不動 Risk Cap、OneBrain、交易訊號或 OAuth/Sheet。
