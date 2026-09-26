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
- jingqi：燈值的來源有三條（ADL 5 日均 / 大盤估算 / TWSE 即時單日），且 5 日均的算式只寫在
  會寫 session 的 L3 函式裡（沒有可重用的純函式）→ 不複製算式、不猜是哪一條。
- health / ndc_signal / tw_export / news_systemic：session 裡沒有歷史序列。
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
    # ── 2026-09-26：恆為無資料（`none_reason` 只進 log / 物件，畫面只顯示「無資料」）──
    **{_k: {"lookback_rows": 0, "mode": DIRECTION_MODE_NONE,
            "unit": "", "window_text": "", "monthly": False, "none_reason": _r}
       for _k, _r in (
           ("health", "session 無總經健康評分的歷史序列"),
           ("ndc_signal", "session 無 NDC 燈號分數的歷史序列"),
           ("us_core_cpi", "只有 prev_yoy、沒有日期 —— 不編日期"),
           ("tw_export", "session 無出口 YoY 的歷史序列"),
           ("us10y", "燈值來自 FRED DGS10 單點；session 的 ^TNX 是另一個源，不混源"),
           ("adl", "ad_ratio 是單日估算、幾乎無自相關（lag-1 −0.028 / lag-20 0.016，"
                   "twii_ohlcv.parquet 4,886 列，2026-09-26 量測）—— 20 日差是雜訊不是趨勢"),
           ("dxy", "session 有序列，但本機量不到持平帶，且 DX-Y.NYB→DX=F→UUP 備援尺度不同 —— 不猜帶寬"),
           ("fut_net", "先行指標只保留約 14 個交易日，湊不滿 20 交易日視窗"),
           ("jingqi", "燈值有三條來源、5 日均算式無可重用的純函式 —— 不複製算式"),
           ("foreign_net", "決策端未接線（燈永遠不亮）"),
           ("news_systemic", "session 無新聞則數的歷史序列"),
       )},
}

#: 持平帶（|變化量| ≤ 帶寬 → 持平；等於帶寬也算持平）。依據見檔頭。
#: ⚠️ mode = "none" 的燈（m1b_m2_gap 與 2026-09-26 那 11 盞）**刻意不在表內**（恆為無資料）。
LAMP_DIRECTION_FLAT_BAND: dict[str, float] = {
    "margin": 1.0,     # %
    "bias_240": 1.0,   # 百分點
    "ism_pmi": 0.5,    # 點
    "vix": 0.5,        # 點（2026-09-26 量測，見檔頭）
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
