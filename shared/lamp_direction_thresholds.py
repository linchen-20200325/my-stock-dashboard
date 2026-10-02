"""shared/lamp_direction_thresholds.py — 「變化方向」列的 L0 SSOT（2026-09-24）。

用途：v2「🚦 今天」→「指標明細（五桶逐段）」的燈卡，在判決行下方多一列
「變化方向」（↗ 上升 / → 持平 / ↘ 下降 / 無資料）。**只**有下列 4 盞燈有這一列，
其餘 12 盞燈一個字都不變。

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
"""
from __future__ import annotations

#: 有「變化方向」列的燈（`DangerSpec.key`）。**只有這 4 盞**；其餘燈不出這一列。
LAMP_DIRECTION_KEYS: tuple[str, ...] = ("margin", "bias_240", "m1b_m2_gap", "ism_pmi")

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
}

#: 持平帶（|變化量| ≤ 帶寬 → 持平；等於帶寬也算持平）。依據見檔頭。
#: ⚠️ `m1b_m2_gap` **刻意不在表內**（恆為無資料，見檔頭）。
LAMP_DIRECTION_FLAT_BAND: dict[str, float] = {
    "margin": 1.0,     # %
    "bias_240": 1.0,   # 百分點
    "ism_pmi": 0.5,    # 點
}

#: 變化量顯示的小數位數。
LAMP_DIRECTION_DECIMALS: int = 1

#: 「變化方向」fact 列的標籤。
LAMP_DIRECTION_FACT_KEY: str = "變化方向"

#: 無資料時的完整文字（⛔ 不帶箭頭）。
LAMP_DIRECTION_NODATA_TEXT: str = "無資料"

#: 方向 → (箭頭, 中文)。⛔ 只用 ↗ → ↘；⛔ 不用 ▲▼、⛔ 不上紅綠色。
LAMP_DIRECTION_LABELS: dict[str, tuple[str, str]] = {
    "up": ("↗", "上升"),
    "flat": ("→", "持平"),
    "down": ("↘", "下降"),
}
