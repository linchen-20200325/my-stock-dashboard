"""shared/sector_flow_thresholds.py — 板塊資金泡泡圖常數 SSOT(L0)。

板塊資金泡泡圖 Stage 1:把「per-stock 每日三大法人淨買超(張)× 收盤 × 產業別」
彙總成 per-sector 每日 net 金額,再由近 N 交易日序列算出每板塊四指標:
    X    = 近 WINDOW_X 交易日 Σ 金額(億)             — 漲潮/退潮軸
    Y    = 近段 5 日日均 − 前段 5 日日均(億/天)      — 動能/加速度軸
    size = 近 WINDOW_SIZE 交易日淨額絕對值(億)        — 規模

CLAUDE.md §3.3 反捏造:所有窗長 / 單位換算 / 象限標籤 / 門檻一律從本檔引入,
禁止 inline magic number。純常數模組,零 import 依賴(可被全層 import)。

單位換算鐵則(§4.1 量綱陷阱)
============================
T86 / TPEX 三大法人回傳單位是**張**(fetcher 已 `round((buy-sell)/1000, 1)`);
收盤價是**元/股**。金額換算必須:
    net_amt_yuan = net_lots(張) × SHARES_PER_LOT(1000 股/張) × close(元/股)   [元]
    net_amt_yi   = net_amt_yuan / YUAN_PER_YI(1e8)                            [億]
漏乘 SHARES_PER_LOT = 1000 倍低估;漏除 YUAN_PER_YI = 1e8 倍高估。
"""
from __future__ import annotations

# ── 單位換算(§4.1)────────────────────────────────────────────────────
SHARES_PER_LOT: int = 1000        # 1 張 = 1000 股(張 → 股 還原)
YUAN_PER_YI: float = 1e8          # 1 億 = 100,000,000 元(元 → 億)

# ── 交易日視窗(§4.5 交易日 ≠ 日曆日;下列全指「交易日」窗)──────────────
WINDOW_X: int = 5                 # X 軸:近 5 交易日金額「總和」(億)
WINDOW_Y_RECENT: int = 5          # Y 軸近段:最近 5 交易日
WINDOW_Y_PRIOR: int = 5           # Y 軸前段:再往前 5 交易日(第 6~10 交易日)
WINDOW_SIZE: int = 20             # size:近 20 交易日淨額(取絕對值)

#: Y 軸所需最少交易日 = 近段 + 前段(不足 → 動能不可算,標資料不足)。
WINDOW_Y_MIN_DAYS: int = WINDOW_Y_RECENT + WINDOW_Y_PRIOR   # 10

# ── 象限標籤(§3.3 具名 SSOT;與需求四象限一致)────────────────────────
#   X>0, Y>0 → 漲潮   |  X>0, Y<0 → 輪動
#   X<0, Y<0 → 退潮   |  X<0, Y>0 → 觀望
# 邊界慣例:X/Y **恰為 0** 視為「非負側」(>=0),
#   即 x>=0 為右半(漲潮/輪動)、y>=0 為上半(漲潮/觀望)。
#   實務上億級 float 幾乎不可能剛好 0.0,此慣例只為讓四象限**無縫、無第五態**。
QUADRANT_RISING: str = "漲潮"      # X>=0, Y>=0:資金持續流入且動能增強
QUADRANT_ROTATING: str = "輪動"    # X>=0, Y<0 :仍淨流入但動能轉弱(資金外移前兆)
QUADRANT_EBBING: str = "退潮"      # X<0,  Y<0 :資金流出且加速
QUADRANT_WATCHING: str = "觀望"    # X<0,  Y>=0:淨流出但動能回升(觸底觀察)
QUADRANT_INSUFFICIENT: str = "資料不足"   # 交易日 < WINDOW_Y_MIN_DAYS,動能無法判定

# ── 板塊/產業(§4.6 邊界:無產業別的股票不猜產業)────────────────────────
#: ticker 無 industry_category(新上市未收錄 / ETF / 權證)→ 歸此桶,不臆造。
SECTOR_UNCLASSIFIED: str = "未分類"

#: 一個板塊在某交易日「有效成分股」數量下限;低於此該板塊當日流入代表性不足。
#: 目前僅作為 coverage 診斷欄位輸出(不濾除),Stage 2 畫圖可據此決定是否淡化顯示。
MIN_SECTOR_STOCKS: int = 1

# ── Stage 2 UI:快取新鮮度門檻(§3.3 具名常數;§4.1 交易日≠日曆日)──────────
#: bubble/metadata 快取「過期」的 wall-clock 上限(日曆日)。cron 每個「交易日」凍結一次,
#: 業務語意是「允許落後 2 個交易日」;但跨週末 2 個交易日最長 = 週五→週二 = 4 個日曆日,
#: 故以 4 個日曆日作為 metadata.updated_at 距今的 staleness wall-clock 門檻(超過 → is_stale)。
SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS: int = 4
