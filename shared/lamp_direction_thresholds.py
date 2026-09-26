"""shared/lamp_direction_thresholds.py — 「變化方向」列的 L0 SSOT（2026-09-24）。

用途：v2「🚦 今天」→「指標明細（五桶逐段）」的燈卡，在判決行下方多一列
「變化方向」（↗ 上升 / → 持平 / ↘ 下降 / 無資料 / 計算失敗）。
2026-09-24 首批 4 盞（margin / bias_240 / ism_pmi / m1b_m2_gap）；
2026-09-26（客戶核准）擴到**全部 16 盞**：有乾淨歷史且持平帶量得到的燈算真方向
（新增 vix），其餘一律「無資料」（原因見下方「無資料的其餘盞」段）。
⚠️ 列只出現在 live / degraded 卡上；未接線（foreign_net）/ 尚未載入 / 失敗的卡不出列。

本檔只放常數（§8.2 L0：零 I/O、零 L1+ 依賴）。計算在
`src/compute/macro/lamp_direction.py`（L2 純函式），本檔不含任何判斷邏輯。

⚠️ 「變化方向」**不是燈號** —— 它不參與 `classify_danger()`、不改 `_band`、
不改燈色。持平帶只決定「箭頭畫 → 還是 ↗/↘」。

────────────────────────────────────────────────────────────────────
持平帶（|變化量| ≤ 帶寬 → 持平）的資料依據（§3.3：不腦補數字）
────────────────────────────────────────────────────────────────────
量測日 2026-09-24，本地 `data_cache/` parquet：

- **margin（融資餘額，%）** — 乾淨區間的 |20 交易日變化率| 分布：
  p10 = 0.72%，p25 = 1.85%。帶寬取 **1.0%**：落在 p10 與 p25 之間 ——
  只把「幾乎沒動」判成持平（約一成多的日子），不把一般波動吞掉。
- **bias_240（年線乖離率，百分點）** — |20 交易日變化| p25 = 1.5 個百分點。
  帶寬取 **1.0 個百分點**（< p25）：持平只保留給明顯小於常態波動的情形。
- **ism_pmi（台灣 PMI，點）** — |月變化| p25 = 0.5 點。帶寬取 **0.5 點**（= p25）。
  PMI 本身報到小數一位，±0.5 以內屬「幾乎沒動」。
- **m1b_m2_gap** — **不設帶寬**：它的歷史檔 `data_cache/finmind_m1m2.parquet`
  已知損壞（M1B 出現負值、gap 範圍達數千點，見 HANDOFF.md 既有缺陷登記），
  故這一列**恆為「無資料」**，連讀都不讀那個檔（§1：錯的數字比沒有數字更危險）。
  ⛔ 不要為了「讓它有箭頭」而補一個帶寬 —— 那等於假裝有乾淨的歷史可比。

量測日 2026-09-26（擴到 16 盞那一批）：
- **vix（VIX，點）** — 序列＝ session `macro_info['vix']` 的 `dates` / `values`
  （與燈值 `current` 同一次 Yahoo ^VIX 抓取，60 交易日、值已四捨五入到 0.1）。
  帶寬量測：CBOE VIX 日收盤鏡像 `datasets/finance-vix` 的 `data/vix-daily.csv`
  （sha256 570e0563…c082fb83，1990-01-02 ~ 2026-09-22，9,278 列；本機無 Yahoo / FRED
  連線，故用同一指數的公開鏡像），收盤先 round(1) 再取 |20 列差|：
  全期 p10 = 0.4、p25 = 0.9；2016+ p10 = 0.4、p25 = 1.0；2021+ p10 = 0.4、p25 = 1.0 點。
  帶寬取 **0.5 點**：落在 p10 與 p25 之間（同 margin 的取法）。
- **adl（ADL 上漲佔比）— 刻意「無資料」（2026-09-26 獨立 QA 否決真方向，量測留作排除依據）**：
  session 雖有 `cl_data['adl']` 的 60 列 `ad_ratio`，但它是由指數**單日**漲跌估算的家數比，
  **幾乎沒有自相關**。量測：本機 `data_cache/twii_ohlcv.parquet`（source = Yahoo:^TWII:chart，
  4,886 列，2006 ~ 2026-09-24），套 `fetch_adl` 的估算式（up = clip(900 + (close − open)/open
  × 15000, 50, 1750)、down = max(50, 1800 − up)、ratio = round(up / (up + down) × 100, 1)；
  **只在量測腳本裡重現，production 不複製**）：lag-1 自相關 = −0.028、lag-5 = 0.005、
  lag-20 = 0.016。⇒ 「近 20 交易日」的差只是**兩個互不相關的單日**相減，畫成 ↗ / ↘ 等於把
  雜訊講成趨勢（§1 / v3 §02「無誤導」）。⛔ 不要為了「讓它有箭頭」而加回帶寬。

無資料的其餘盞（mode = "none"，**不讀任何歷史**；原因寫在 `none_reason`，只進 log）：
- adl：單日估算、無自相關（量測見上方 adl 段）→ 20 日差是雜訊。
- dxy：session **有**約 60 天的序列（`cl_data['intl']['美元指數 DXY']`），但 (1) 持平帶量不到
  （本機無 DXY 歷史、無外網）→ 不猜數字；(2) 該序列走 DX-Y.NYB → DX=F → UUP 備援，
  UUP 的尺度完全不同，序列來源可能換手 → 不能拿一條帶寬套所有來源。
- us10y：燈值來自 FRED DGS10 單點（無歷史）；session 的 ^TNX 是另一個源 → 不混源。
- fut_net：先行指標只保留約 14 個交易日，20 交易日視窗做不到（且不另開「近 13 交易日」這種新文字）。
- us_core_cpi：只有 prev_yoy 沒有日期 → 不編日期。
- jingqi：見下方「2026-09-26 第二批複查」—— 量測後仍判無資料（5 日均的 20 日差是雜訊）。
- health / tw_export：見下方「2026-09-26 第二批複查」—— 逐盞查證後仍判無資料。
- （ndc_signal 已於同日第二批改為真方向，見下方該段。）
- news_systemic：session 裡沒有歷史序列。

2026-09-26 第二批複查（客戶核准嘗試接 health / jingqi / ndc_signal / tw_export；
逐盞查證後 **health / jingqi / tw_export 維持無資料**（只更新 `none_reason`，畫面文字不變），
**ndc_signal 改為真方向**（獨立 QA 複查後的結論，見 ndc_signal 段）：
- **jingqi（旌旗＝ad_ratio 5 日均）** — 量測腳本 `measure_jingqi_autocorr.py`（scratchpad，
  量測日 2026-09-26）：本機 `data_cache/twii_ohlcv.parquet`（sha256 c34b92e5…e2283，
  source = Yahoo:^TWII:chart，4,886 列，2006-09-29 ~ 2026-09-24），套 adl 段同一估算式後取
  rolling(5).mean()：lag-1 自相關 = 0.789（只是 5 日窗重疊造成的機械相關）、
  lag-5 = 0.007、**lag-20 = 0.025**（ad_ratio 本身 lag-20 = 0.016）。⇒ 「近 20 交易日」
  比的是兩段**不重疊**的 5 日窗，彼此幾乎不相關，差值仍是雜訊 → 同 adl 原則不出箭頭。
  （因此也**沒有**把 `jingqi_calc` 的 5 日均抽成純函式 —— 用不到就不動 L3。）
- **health（總經健康評分）** — 唯一的歷史是前進式驗證凍結檔
  `data_cache/macro_forward_test/signals.parquet`（唯讀，24 列，2026-08-20 ~ 09-25）。
  兩邊都讀 `calc_traffic_light(...)['health']`（ruleset_hash 全為 532c3a57698f），但：
  (1) `date` 是**cron 執行日**不是交易日（有 2026-08-29 週六列；`inputs_as_of` 24 列全為 None）。
      對照 twii 交易日曆，檔案區間內缺 **4** 個交易日（08-27 / 08-31 / 09-14 / 09-21）；
      09-22 不是交易日，且與 09-23 同值（73.3，過期重複列）
      ⇒「往前 20 列」≠「近 20 交易日」，視窗文字會說謊；
  (2) 燈值取自 `warroom_summary['health_score']`，該 dict **不帶 `health_partial`**；
      輸入也不同（cron 走 `fetch_macro_bundle` 自抓一輪、燈值走頁面 session）⇒ 末值一般
      對不上燈值；且 `page_today.OUT_OF_REACH_LIGHT_KEYS` 本來就列著 health（寫入點不在本頁路徑）。
- **tw_export（月資料，「較上月」）** — L1 只回最新一點（歷史在 `fetch_export_block` 內被丟掉），
  但持平帶**量不到**：本機 `data_cache/` 無出口 YoY 歷史檔，且 data.gov.tw / 海關 opendata /
  FRED 在本環境皆 403（2026-09-26 實測）⇒ 依 §3.3 不猜帶寬 → **L1 不改**。另記：5 路 fallback
  口徑不一（stat.gov.tw 單點、海關 6053 為新臺幣、FRED 為 OECD 美元序列），且 MOF 月資料會
  回溯修正（§2.3 ±5%），日後若要接，須限定同一條 fallback、同一次抓取的相鄰兩月。
- **ndc_signal（NDC 景氣對策信號分數，月資料，「較上月」）— 真方向，帶寬 0**：
  分數是國發會公布的**整數**（9~45），帶寬 0 是資料本身的解析度（相同分數＝持平，差 1 分
  就是官方分數真的動了），**不是**猜出來的數字 —— 不需要、也無從另外量測一條帶寬。
  前例：`src/data/macro/tw_macro.fetch_ndc_signal_history` 早就以 `cur > prev` / `cur < prev`
  / 相等 判斷拐點（同樣沒有容差帶）。
  序列來源：L1 `fetch_ndc_block` **只在** FinMind-TBI 與 data.gov.tw 6099-ZIP 兩條分支，從
  **同一次抓取、同一份 DataFrame** 的上一列帶出 additive 鍵 `prev_score` / `prev_date`
  （兩月不相鄰 → 不帶）；StockFeel / MacroMicro 分支只有單點 → 不帶 → 無資料。**無新增抓取**，
  既有鍵值逐字不變。L5 守衛：最新點就是燈值那個 `score`（同一個 dict）。
  ⚠️ §2.3：上月值是**本次發布版**（若官方回溯修正上月分數，拿到的是修正後的值），
  與本月燈號同一次發布對齊 ⇒ 無 lookahead；但它可能與上個月畫面當時顯示的數字不同。
  單位：顯示不帶單位（`unit = ""`，沿用既有字串，不新增「分」這個方向列文字）。
- foreign_net：決策端未接線（燈永遠不亮），卡上本來就不出這一列。
"""
from __future__ import annotations

#: 有「變化方向」列的燈（`DangerSpec.key`）。2026-09-26 起＝**全部 16 盞**
#: （前 4 盞為 2026-09-24 首批，順序不動）。沒有歷史的燈 mode = "none" → 恆為「無資料」。
LAMP_DIRECTION_KEYS: tuple[str, ...] = (
    "margin", "bias_240", "m1b_m2_gap", "ism_pmi",
    # 2026-09-26：有歷史、持平帶量得到 → 真方向
    "vix",
    # 2026-09-26：有序列但單日估算無自相關 → 恆為無資料（見檔頭）
    "adl",
    # 2026-09-26：無歷史 / 量不到帶寬 / 會混源 → 恆為無資料（原因見檔頭）
    "health", "ndc_signal", "us_core_cpi", "tw_export", "us10y", "dxy",
    # （ndc_signal 2026-09-26 第二批改真方向；位置不動，避免既有順序漂移）
    "fut_net", "jingqi", "foreign_net", "news_systemic",
)

#: 變化量的計算方式。
#:   "pct"  → (新 / 舊 − 1) × 100，單位 %（舊值 ≤ 0 → 無資料，不除以零）
#:   "diff" → 新 − 舊，單位同原序列（百分點 / 點）
#:   "none" → 恆為無資料（不讀歷史）
DIRECTION_MODE_PCT: str = "pct"
DIRECTION_MODE_DIFF: str = "diff"
DIRECTION_MODE_NONE: str = "none"

#: 每盞燈的視窗設定。
#:   lookback_rows: 與「往前第幾列」比（每列 = 一個交易日 / 一個月）
#:   mode:          見上
#:   unit:          顯示用的變化量單位
#:   window_text:   顯示在括號內的視窗說明
#:   monthly:       True → 比較的兩點必須是**相鄰的兩個月份**；中間缺月 → 無資料
#:                  （否則「較上月」其實是較三個月前，文字就說謊了）
LAMP_DIRECTION_WINDOWS: dict[str, dict] = {
    "margin": {
        "lookback_rows": 20, "mode": DIRECTION_MODE_PCT,
        "unit": "%", "window_text": "近 20 交易日", "monthly": False,
    },
    "bias_240": {
        "lookback_rows": 20, "mode": DIRECTION_MODE_DIFF,
        "unit": " 個百分點", "window_text": "近 20 交易日", "monthly": False,
    },
    "ism_pmi": {
        "lookback_rows": 1, "mode": DIRECTION_MODE_DIFF,
        "unit": " 點", "window_text": "較上月", "monthly": True,
    },
    "m1b_m2_gap": {
        "lookback_rows": 0, "mode": DIRECTION_MODE_NONE,
        "unit": "", "window_text": "", "monthly": False,
    },
    # ── 2026-09-26：真方向（持平帶量測見檔頭）──
    "vix": {
        "lookback_rows": 20, "mode": DIRECTION_MODE_DIFF,
        "unit": " 點", "window_text": "近 20 交易日", "monthly": False,
    },
    # ── 2026-09-26 第二批：整數官方分數，帶寬 0＝資料解析度（見檔頭 ndc_signal 段）──
    "ndc_signal": {
        "lookback_rows": 1, "mode": DIRECTION_MODE_DIFF,
        "unit": "", "window_text": "較上月", "monthly": True,
    },
    # ── 2026-09-26：恆為無資料（`none_reason` 只進 log / 物件，畫面只顯示「無資料」）──
    **{_k: {"lookback_rows": 0, "mode": DIRECTION_MODE_NONE,
            "unit": "", "window_text": "", "monthly": False, "none_reason": _r}
       for _k, _r in (
           ("health", "唯一歷史是前進式驗證凍結檔：date 為 cron 執行日非交易日（區間內缺 4 個交易日、"
                      "含週六列與 09-22 過期重複列）；兩邊都讀 calc_traffic_light(...)['health']，"
                      "但燈值 dict 不帶 health_partial、輸入不同（cron fetch_macro_bundle vs session），"
                      "且 OUT_OF_REACH_LIGHT_KEYS 列著 health（2026-09-26 查證）"),
           ("us_core_cpi", "只有 prev_yoy、沒有日期 —— 不編日期"),
           ("tw_export", "L1 只回最新一點；本機無出口 YoY 歷史、外部源 403 —— 持平帶量不到，不猜；"
                         "且 5 路 fallback 口徑不一、月資料會回溯修正（2026-09-26 查證）"),
           ("us10y", "燈值來自 FRED DGS10 單點；session 的 ^TNX 是另一個源，不混源"),
           ("adl", "ad_ratio 是單日估算、幾乎無自相關（lag-1 −0.028 / lag-20 0.016，"
                   "twii_ohlcv.parquet 4,886 列，2026-09-26 量測）—— 20 日差是雜訊不是趨勢"),
           ("dxy", "session 有序列，但本機量不到持平帶，且 DX-Y.NYB→DX=F→UUP 備援尺度不同 —— 不猜帶寬"),
           ("fut_net", "先行指標只保留約 14 個交易日，湊不滿 20 交易日視窗"),
           ("jingqi", "5 日均的 20 日差仍是雜訊（lag-20 自相關 0.025，twii_ohlcv.parquet 4,886 列，"
                      "2026-09-26 量測）—— 同 adl 不出箭頭"),
           ("foreign_net", "決策端未接線（燈永遠不亮）"),
           ("news_systemic", "session 無新聞則數的歷史序列"),
       )},
}

#: 持平帶（|變化量| ≤ 帶寬 → 持平；等於帶寬也算持平）。依據見檔頭。
#: ⚠️ mode = "none" 的燈（m1b_m2_gap 與 2026-09-26 那 10 盞）**刻意不在表內**（恆為無資料）。
LAMP_DIRECTION_FLAT_BAND: dict[str, float] = {
    "margin": 1.0,     # %
    "bias_240": 1.0,   # 百分點
    "ism_pmi": 0.5,    # 點
    "vix": 0.5,        # 點（2026-09-26 量測，見檔頭）
    "ndc_signal": 0.0,  # 分（整數官方分數；0＝資料解析度，不是猜的，見檔頭）
}

#: 變化量顯示的小數位數。
LAMP_DIRECTION_DECIMALS: int = 1

#: 「變化方向」fact 列的標籤。
LAMP_DIRECTION_FACT_KEY: str = "變化方向"

#: 無資料時的完整文字（⛔ 不帶箭頭）。
LAMP_DIRECTION_NODATA_TEXT: str = "無資料"

#: 方向**計算本身失敗**（L3 取數 / L2 計算丟例外、或結果沒回傳）時的文字（⛔ 不帶箭頭）。
#: 與「無資料」刻意分開（2026-09-25，客戶核准）：「無資料」＝序列不夠 / 不可信，
#: 「計算失敗」＝程式這一輪沒跑完 —— 兩者原因不同，畫面不得混為一談（§1）。
#: 修前這種情形是整列**靜默消失**（`except` → `return {}`）。
LAMP_DIRECTION_ERROR_TEXT: str = "計算失敗"

#: 帶簡短原因的版本（原因只放例外型別名，⛔ 不放 stack trace / 訊息全文）。
LAMP_DIRECTION_ERROR_TEMPLATE: str = LAMP_DIRECTION_ERROR_TEXT + "（{reason}）"

#: directions mapping 裡**缺了**某一盞燈的 key 時用的原因（判為計算失敗，不判無資料）。
LAMP_DIRECTION_MISSING_REASON: str = "未回傳"

#: 方向 → (箭頭, 中文)。⛔ 只用 ↗ → ↘；⛔ 不用 ▲▼、⛔ 不上紅綠色。
LAMP_DIRECTION_LABELS: dict[str, tuple[str, str]] = {
    "up": ("↗", "上升"),
    "flat": ("→", "持平"),
    "down": ("↘", "下降"),
}
