# New UI2｜TWII 日 K A／B／A 已核准視覺與接線方向（2026-11-09）

> **客戶明確核准的設計／資料來源方向；正式施工尚未授權。** 決策 SSOT：`docs/DECISIONS.md` 的 DEC-156；本文件只是該裁示的實作前資料與視覺契約，不等於執行 gate。原 #1096 收盤折線是歷史候選；#1097 docs/HTML FAKE 並非上線證據。

## 一、客戶已裁示

| 議題 | 契約 |
|---|---|
| K 棒漲跌色 | **close > open：紅**；**close < open：綠**；**close == open：灰十字線**。當日開收基準，非相對前日收盤；顏色以圖例與文字同步呈現，不只靠色相 |
| 手機預設可見數 | **最近 20 根**符合合法契約的已完成日 K；沒有 20 根時**不填補、不偽造、不內插**；顯示不足及可得期間 |
| 圖高 | **約 220px** 目標；390×844 視窗不得水平溢出、不得把已核准首屏重要狀態／CTA 擠出契約。1440×900 桌機驗收 |
| 主來源 | 現有 `data_cache/twii_ohlcv.parquet`（Yahoo `^TWII` 日 OHLC），優先重用；**FinMind** 僅未來備援與對帳研究，不能默認已具權限／已接大盤 |
| 擴充範圍 | 只在未來**另行授權施工**後，研究最小加性唯讀 L3 → feed → canonical VM → UI2 的資料橋接；不可寫資料、重算進出場／投資訊號或碰資料發布 |

## 二、來源差異與不可繞過的契約

`src/services/macro_v2_service.py::get_twii_ohlc(n_trading_days)` 目前以 parquet 讀 xs/open/high/low/close，但**不帶 is_stale/as_of/upstream_state**；`src/services/market_twii_view_service.py::get_twii_trend_view(n)` 帶新鮮度等事實但**只提供 close**；`src/services/ui2/real_feed.py` 目前只准已列 G2F 白名單的 `get_twii_trend_view`，卡片 `TWII_CARD_DAYS=1` 有既有測試釘住。

**資料契約候選（施工前須驗證）：**
- 日期 x 唯一升序、無未來日、不得把盤中未完成 K 棒作已收盤；每根 `open/high/low/close` 必須有限、正值且 `low <= min(open,close) <= max(open,close) <= high`。
- 來源、更新／觀測日期、is_stale、upstream_state、as_of 需與卡片一致；讀取資料與 freshness 要同快照／可追溯，不能把分開呼叫的不同版本假裝一致；`fetched_at` 是抓取時間，**不是歷史 PIT 可得時間證據**。
- stale、failed、missing、partial 都需要明確的不同狀態；不以 0、灰色正常線或假的 K 棒補缺。過期不等於 fresh；尚未評估不等於安全。
- HTML 在 #1097 的 FAKE 資料標示必須保留作為視覺預覽；正式 Real 路徑嚴禁合成值。成交量已有 NaN，不畫量、不把缺量當零；MA 與其他疊加線未核准。
- 不得逕 import `macro_v2_service` 至 `real_feed`，不得未審改 `G2F_IMPORT_ALLOWLIST`；如果加性 schema 不能安全滿足契約，應停在 Design Gate，不要為綠燈放寬守衛。

## 三、三條實作路徑（尚未授權）

| 方案 | 內容 | 風險 | 速度／Token | 判斷 |
|---|---|---|---|---|
| A｜**推薦** | 基於既有 `market_twii_view_service` 的合法資料入口，擴出具 attrs/freshness、完整 OHLC、同日收盤卡對帳的**加性唯讀 schema**；保持現有卡片 1 日語意 | 中：新 schema、PIT/stale/當日未完成棒需充分負測 | 最快／最省 | 先評估能否不新增 G2F 具名方法而安全達成 |
| B | 另做薄 L3 包裝 `macro_v2_service.get_twii_ohlc`，補 provenance、freshness、同快照，新增白名單須審核 | 中高：多一層、快取/IO/守衛 | 中／較高 | A 不可行時研究 |
| C | 暫時保留誠實空槽，等來源日期／stale 契約健全再接 | 最低；功能延期 | 最快／最省 | contract 失敗時的安全降級 |

**B 在「#1097 的視覺稿先看」和本表「資料路徑 B」不是同一選項**。客戶 A／B／A 分別是 K 色／手機可見根數與圖高／Yahoo OHLC 路線，非授權資料路徑 B。

## 四、未授權與下一步

本次 PR **只准改 docs/**，不修改 `src/`、`tests/`、workflow、auth、sheet、Risk Cap、OneBrain、cron 或任何來源 API。客戶若另行授權施工，再在最新 main SHA 基礎上建最小程式 PR，覆蓋：單元負向契約、G2/G2F/G4/G9、20 根可見與不足情形、fake 不可流入 Real、桌機與手機 browser 390×844／1440×900、獨立 QA、最新 head 五項 CI 全綠。具體視窗切換/縮放/拖動、252 根是否提供與機制，仍待單獨視覺互動契約。
