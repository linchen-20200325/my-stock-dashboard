# New UI2｜台股加權指數日 K 視覺選項 B（2026-11-09）

> **客戶已指定：取代 P1 收盤折線，改為 K 棒、紅漲綠跌；選 B＝先看手機／桌機 HTML 視覺草稿。** 本文件是**設計候選與差異記錄**，並非視覺最終驗收、OHLC 資料契約核准或程式施工授權。基準 main `5588a72b996a4494705d81c8ee7e0ef4096387a3`；當次 Open PR=0。主檔：`docs/vnext/NEWUI2_TWII_CANDLESTICK_VISUAL_PREVIEW_2026-11-09.html`。

## 1. 已確定／未確定
| 類型 | 狀態 | 處置 |
|---|---|---|
| 圖型 | **客戶明確選日 K 候選，取代 #1096 的 P1 收盤折線** | 先視覺審查 |
| 顏色 | **紅漲綠跌**（台灣常用配色） | 用紅／綠 K 身及同色上下影線；增加文字/圖例不依賴顏色 |
| 導航/主題 | 既核准五頁頂部兩列、Dark-only、Mobile-first | 不重審、不施工 |
| 施工許可 | **未給** | 不改任何 UI/service/tests/source/Schema/Risk Cap |
| K 棒漲跌基準 | **候選：收盤 >= 開盤為紅；收盤 < 開盤為綠；十字線用中性符號** | 「紅漲綠跌」沒有明定前收 vs 當日開收，需日後確認，不得自行把漲跌幅/動作訊號綁定 K 色 |
| 歷史視窗 | 初稿 252 交易日的**資料上限**；手機截圖用少量可見棒作視覺示意 | 252 根擠在手機單屏不可辨識。是否允許可視視窗/捲動/縮放與預設顯示根數，另交 Visual Gate |
| MA、量 | 第一版視覺示意不含 MA／量 | 沒授權捨棄未來功能；既有 MA session 純量無法直接合法接 UI2 |
| 圖高 | 約 200–220px 設計意向 | 需驗證 390×844 首屏 ≥160px、DEC-119 僅舊頁適用性及 1440×900 |
| 資料／真機 | HTML 全為可辨識的 **FAKE 示意**；未實測來源／部署端 | 機器截圖與 QA NOT VERIFIED |

## 2. 舊 UI／L3／UI2 的真實差異
| 層 | 已查程式證據 | 缺口／安全要件 |
|---|---|---|
| 來源 | `data_cache/twii_ohlcv.parquet` 既有欄 `date,open,high,low,close`；歷史 volume 不可靠 | 資料行為／完結 bar 日界／前收關係仍 NOT VERIFIED |
| 舊 L3 | `src/services/macro_v2_service.py::get_twii_ohlc(n_trading_days)` 回五個等長 list（xs/OHLC），有 Streamlit cache、dropna 整根丟失 | **這支不是目前 G2F 白名單**，亦未保證帶 `is_stale/as_of/source/upstream_state`，不可逕接 UI2 |
| 目前核准 L3 | `src/services/market_twii_view_service.py::get_twii_trend_view(n)` 保留 freshness/as_of/upstream_state，但**只回 close** | 不能僅更改 n 就畫合法 K 棒；#1096 的方案 A 只適用收盤線 |
| UI2 | `src/services/ui2/real_feed.py::TWII_CARD_DAYS=1`、`real_canonical.py::TwiiFact`、`src/ui2/views/market.py::primary_slot_html` | 附加 OHLC 五序列需重新審核 G2/G2F、加性 Schema、日期／價關係及卡圖一致性；保留既有卡 1 日語意 |
| 風險 | 一個 K 棒須 `low<=min(open,close)<=max(open,close)<=high` 且皆有限、正值；xs 唯一升序，日期與 as_of 一致 | 亂序/重複/未來日期/不完整棒/NaN/inf/盤中未完成棒、灰/紅/stale 需 fail-closed；不能填 0 或假成正常 |

## 3. 三種合法接線候選（不等於授權）
| 方案 | 技術路徑 | 風險 | 速度／Token | 判斷 |
|---|---|---|---|---|
| **A（推薦研究）** | 在既有白名單 `market_twii_view_service` 增加**獨立 OHLC 純讀輸出**，共用 L1 parquet 與 L0 freshness，feed 仍只呼叫既有白名單內的具名方法（是否需要更新 G2F 測試，須證實） | 中；新增 schema／時間與 OHLC 驗證，不能只靠 close | 相對最快，較省 Token | 先做無副作用及 G2F 可行性 proof |
| **B** | 包裹 `macro_v2_service.get_twii_ohlc` 的新 L3 thin adapter，補 provenance/age/upstream/pit | 中高；新 L3 白名單、Streamlit cache/例外路徑與雙份讀取 | 中／中高 | A 不可行才考慮 |
| **C** | 維持 UI2 誠實空槽，先只保存 K 棒視覺方向 | 最低 | 即刻／零施工 | Gate 無法通過時安全備案 |

注意 A 的具名方法怎麼擴充要過 G2F 負測；**禁止**以刪除或放寬守衛換綠燈。不得修改資料源/公式/買賣語意/權限。

## 4. HTML 草稿應審什麼
1. 手機 390×844、桌機 1440×900：K 棒可看清上/下影線，紅綠以文字或圖例補充；不強迫顯示全部 252 根。
2. 台股日 K 的標題、資料日、來源、stale/failed/missing 狀態位置清楚；FAKE 的假資料標註不得省略。
3. K 棒價格為「指數點」，有時間軸與數字縱軸；不因圖高把現有首屏結論、Risk Cap 誠實狀態、主要 CTA 擠出安全空間。
4. 空/錯/單點等不能繪成正常 K 線；無量、不加 MA、不擅自加入 buy/sell。
5. 由客戶看過草稿後，確認 K 色基準、可視根數／捲動、尺寸；**未確認前不施工**。

## 5. 後續 Gate
僅本次「選 B」足以授權 docs-only 視覺方案記錄；**不授權 UI2 圖表資料接線**。後續先由非作者 QA 驗文案、程式事實、三方案；最新 PR head 五項 CI；再 docs merge。接著要客戶對實際草稿做視覺核准，才另開程式施工 PR。不能把 docs merge 或 preview screenshot 當成正式 K 線上線。
