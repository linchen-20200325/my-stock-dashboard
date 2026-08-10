"""tests/test_sector_flow.py — 板塊資金泡泡圖 L2 純函式測試(Stage 1)。

全用合成資料(容器內對外被 proxy 擋,L2 本就零 I/O 可離線測)。覆蓋:
- 張 → 金額(億)換算(§4.1 SHARES_PER_LOT / YUAN_PER_YI)
- per-sector groupby 加總 + n_stocks
- 缺價的 (股,日) 顯式剔除 + coverage(§1 不補值)
- 無產業別 → 未分類桶(§4.6 不猜)
- X 近 5 日總和 / size 近 20 日絕對值 / Y 兩段 5 日日均之差(正負號)
- 四象限 + 邊界(x=0) + 交易日不足 → 資料不足
- 交易日軸缺格顯式補 0 + meta 計數
- 空輸入邊界 / map_tickers_to_sectors
"""
from __future__ import annotations

import math

import pandas as pd

from shared.sector_flow_thresholds import (
    QUADRANT_EBBING,
    QUADRANT_INSUFFICIENT,
    QUADRANT_RISING,
    QUADRANT_ROTATING,
    QUADRANT_WATCHING,
    SECTOR_UNCLASSIFIED,
    WINDOW_SIZE,
)
from src.compute.sector_flow import (
    classify_quadrant,
    compute_bubble,
    compute_sector_daily_net,
    map_tickers_to_sectors,
)


# ── 合成資料 helpers ──────────────────────────────────────────────────
def _inst_row(date, sid, f=0.0, t=0.0, d=0.0):
    return {"date": date, "stock_id": sid, "foreign_lots": f,
            "trust_lots": t, "dealer_lots": d}


def _bdays(n, end="2026-08-07"):
    """回 n 個交易日(工作日),由舊到新。"""
    return list(pd.bdate_range(end=end, periods=n).normalize())


# ══════════════════════════════════════════════════════════════════════
# 1. 張 → 金額換算(§4.1 單位陷阱:漏 ×1000 = 1000× 低估、漏 /1e8 = 1e8× 高估)
# ══════════════════════════════════════════════════════════════════════
def test_lots_to_yi_conversion_exact():
    day = pd.Timestamp("2026-08-07")
    inst = pd.DataFrame([_inst_row(day, "2330", f=500.0)])  # 500 張外資
    price = pd.DataFrame([{"date": day, "stock_id": "2330", "close": 600.0}])
    sd, cov = compute_sector_daily_net(inst, price, {"2330": "半導體業"})
    # 500 張 × 1000 股/張 × 600 元 = 3e8 元 = 3 億
    assert len(sd) == 1
    row = sd.iloc[0]
    assert math.isclose(row["net_amt_yi"], 3.0, rel_tol=1e-9, abs_tol=1e-12)
    assert math.isclose(row["foreign_yi"], 3.0, rel_tol=1e-9, abs_tol=1e-12)
    assert math.isclose(row["trust_yi"], 0.0, abs_tol=1e-12)
    assert row["sector"] == "半導體業"
    assert int(row["n_stocks"]) == 1


def test_three_camps_sum_no_double_count():
    """主力合計 = 外資+投信+自營,不重複加(§4.1 陷阱 5)。"""
    day = pd.Timestamp("2026-08-07")
    # 各 100 張,close=100 → 每分項 100*1000*100/1e8 = 0.1 億
    inst = pd.DataFrame([_inst_row(day, "2330", f=100.0, t=100.0, d=-100.0)])
    price = pd.DataFrame([{"date": day, "stock_id": "2330", "close": 100.0}])
    sd, _ = compute_sector_daily_net(inst, price, {"2330": "半導體業"})
    r = sd.iloc[0]
    assert math.isclose(r["foreign_yi"], 0.1, abs_tol=1e-12)
    assert math.isclose(r["dealer_yi"], -0.1, abs_tol=1e-12)
    # 0.1 + 0.1 + (-0.1) = 0.1
    assert math.isclose(r["net_amt_yi"], 0.1, abs_tol=1e-12)


# ══════════════════════════════════════════════════════════════════════
# 2. sector groupby 加總 + n_stocks
# ══════════════════════════════════════════════════════════════════════
def test_sector_groupby_sum():
    day = pd.Timestamp("2026-08-07")
    inst = pd.DataFrame([
        _inst_row(day, "2330", f=100.0),   # 半導體
        _inst_row(day, "2454", f=50.0),    # 半導體
        _inst_row(day, "2881", f=200.0),   # 金融
    ])
    price = pd.DataFrame([
        {"date": day, "stock_id": "2330", "close": 100.0},
        {"date": day, "stock_id": "2454", "close": 100.0},
        {"date": day, "stock_id": "2881", "close": 100.0},
    ])
    imap = {"2330": "半導體業", "2454": "半導體業", "2881": "金融保險業"}
    sd, cov = compute_sector_daily_net(inst, price, imap)
    semi = sd[sd["sector"] == "半導體業"].iloc[0]
    fin = sd[sd["sector"] == "金融保險業"].iloc[0]
    # 半導體:150 張 × 1000 × 100 / 1e8 = 0.15 億;2 檔
    assert math.isclose(semi["net_amt_yi"], 0.15, abs_tol=1e-12)
    assert int(semi["n_stocks"]) == 2
    assert math.isclose(fin["net_amt_yi"], 0.2, abs_tol=1e-12)
    assert cov["n_sectors"] == 2


# ══════════════════════════════════════════════════════════════════════
# 3. 缺價剔除(§1 不補值)
# ══════════════════════════════════════════════════════════════════════
def test_missing_price_dropped_and_counted():
    day = pd.Timestamp("2026-08-07")
    inst = pd.DataFrame([
        _inst_row(day, "2330", f=100.0),
        _inst_row(day, "9999", f=999.0),   # 停牌:有淨額無收盤
    ])
    price = pd.DataFrame([{"date": day, "stock_id": "2330", "close": 100.0}])
    sd, cov = compute_sector_daily_net(inst, price, {"2330": "半導體業",
                                                     "9999": "其他"})
    # 9999 缺價 → 剔除,不出現
    assert set(sd["sector"]) == {"半導體業"}
    assert cov["n_dropped_missing_price"] == 1
    assert cov["n_stock_days_with_net"] == 2


def test_nonpositive_close_treated_as_missing():
    day = pd.Timestamp("2026-08-07")
    inst = pd.DataFrame([_inst_row(day, "2330", f=100.0)])
    price = pd.DataFrame([{"date": day, "stock_id": "2330", "close": 0.0}])
    sd, cov = compute_sector_daily_net(inst, price, {"2330": "半導體業"})
    assert sd.empty
    assert cov["n_dropped_missing_price"] == 1


# ══════════════════════════════════════════════════════════════════════
# 4. 無產業別 → 未分類桶(§4.6 不猜)
# ══════════════════════════════════════════════════════════════════════
def test_unknown_industry_to_unclassified():
    day = pd.Timestamp("2026-08-07")
    inst = pd.DataFrame([_inst_row(day, "1234", f=100.0)])
    price = pd.DataFrame([{"date": day, "stock_id": "1234", "close": 100.0}])
    sd, cov = compute_sector_daily_net(inst, price, {})   # 空 map
    assert sd.iloc[0]["sector"] == SECTOR_UNCLASSIFIED
    assert cov["n_unclassified_stock_days"] == 1


def test_blank_industry_value_to_unclassified():
    day = pd.Timestamp("2026-08-07")
    inst = pd.DataFrame([_inst_row(day, "1234", f=100.0)])
    price = pd.DataFrame([{"date": day, "stock_id": "1234", "close": 100.0}])
    sd, cov = compute_sector_daily_net(inst, price, {"1234": "  "})  # 空白
    assert sd.iloc[0]["sector"] == SECTOR_UNCLASSIFIED
    assert cov["n_unclassified_stock_days"] == 1


# ══════════════════════════════════════════════════════════════════════
# 5. X 近5日總和 / size 近20日絕對值 / Y 兩段5日日均差
# ══════════════════════════════════════════════════════════════════════
def _sector_series(sector, dates, vals):
    return pd.DataFrame({"date": dates, "sector": sector, "net_amt_yi": vals})


def test_window_x_size_y_positive():
    dates = _bdays(20)
    # 前 10 天各 1;prior5(第 6~10 近)各 1、recent5 各 3 → Y=3-1=2>0
    # 最近 10 天:index 10..19。prior5 = idx10..14 = 1,recent5 = idx15..19 = 3
    vals = [1.0] * 15 + [3.0] * 5
    sd = _sector_series("A", dates, vals)
    bubble, meta = compute_bubble(sd)
    r = bubble.iloc[0]
    assert r["sector"] == "A"
    # X = 近5日 = 3*5 = 15
    assert math.isclose(r["x_yi"], 15.0, abs_tol=1e-9)
    # size = |sum 20| = |1*15 + 3*5| = 30
    assert math.isclose(r["size_yi"], 30.0, abs_tol=1e-9)
    # Y = mean(recent5=3) - mean(prior5=1) = 2
    assert math.isclose(r["y_yi"], 2.0, abs_tol=1e-9)
    assert r["quadrant"] == QUADRANT_RISING
    assert not bool(r["insufficient"])
    assert meta["n_trading_days_used"] == 20


def test_window_y_negative_rotating():
    dates = _bdays(20)
    # recent5 低於 prior5 → Y<0;X 仍 >0 → 輪動
    vals = [1.0] * 10 + [5.0] * 5 + [2.0] * 5   # prior5=5, recent5=2 → Y=-3
    sd = _sector_series("A", dates, vals)
    bubble, _ = compute_bubble(sd)
    r = bubble.iloc[0]
    assert math.isclose(r["y_yi"], -3.0, abs_tol=1e-9)
    assert r["x_yi"] > 0
    assert r["quadrant"] == QUADRANT_ROTATING


def test_quadrant_ebbing_and_watching():
    dates = _bdays(20)
    # 退潮:X<0, Y<0 —— recent5=-3, prior5=-1 → Y=-2<0;X=sum recent5=-15<0
    vals_ebb = [-1.0] * 15 + [-3.0] * 5
    b1, _ = compute_bubble(_sector_series("E", dates, vals_ebb))
    assert b1.iloc[0]["quadrant"] == QUADRANT_EBBING
    # 觀望:X<0, Y>0 —— prior5=-3, recent5=-1 → Y=+2>0;X=sum recent5=-5<0
    vals_watch = [-1.0] * 10 + [-3.0] * 5 + [-1.0] * 5
    b2, _ = compute_bubble(_sector_series("W", dates, vals_watch))
    r = b2.iloc[0]
    assert r["y_yi"] > 0 and r["x_yi"] < 0
    assert r["quadrant"] == QUADRANT_WATCHING


def test_only_last_20_days_used():
    """超過 20 交易日 → 只取最近 20(size 不含更早)。"""
    dates = _bdays(30)
    vals = [100.0] * 10 + [1.0] * 20   # 最早 10 天各 100 應被忽略
    sd = _sector_series("A", dates, vals)
    bubble, meta = compute_bubble(sd)
    r = bubble.iloc[0]
    assert meta["n_trading_days_used"] == WINDOW_SIZE == 20
    # size 只算最近 20 天(全 1)= 20,非含最早 100
    assert math.isclose(r["size_yi"], 20.0, abs_tol=1e-9)


# ══════════════════════════════════════════════════════════════════════
# 6. 交易日不足 → Y NaN + quadrant 資料不足(§1 不硬編 0)
# ══════════════════════════════════════════════════════════════════════
def test_insufficient_history_flags():
    dates = _bdays(8)   # < 10(WINDOW_Y_MIN_DAYS)
    vals = [2.0] * 8
    sd = _sector_series("A", dates, vals)
    bubble, _ = compute_bubble(sd)
    r = bubble.iloc[0]
    assert bool(r["insufficient"])
    assert pd.isna(r["y_yi"])
    assert r["quadrant"] == QUADRANT_INSUFFICIENT
    # X / size 仍以現有天數計:X = 近5日 = 2*5 = 10;size = |2*8| = 16
    assert math.isclose(r["x_yi"], 10.0, abs_tol=1e-9)
    assert math.isclose(r["size_yi"], 16.0, abs_tol=1e-9)


# ══════════════════════════════════════════════════════════════════════
# 7. 交易日軸缺格顯式補 0(§1 顯式 + meta 計數)
# ══════════════════════════════════════════════════════════════════════
def test_absent_sector_day_filled_zero_counted():
    dates = _bdays(12)
    # A 每天都有;B 只有最後 2 天 → 前 10 天缺格應被顯式補 0
    dfa = _sector_series("A", dates, [1.0] * 12)
    dfb = _sector_series("B", dates[-2:], [5.0, 5.0])
    sd = pd.concat([dfa, dfb], ignore_index=True)
    bubble, meta = compute_bubble(sd)
    # 12 交易日 × 2 板塊 = 24 格,實有 12(A) + 2(B) = 14 → 補 10 格
    assert meta["n_filled_absent_cells"] == 10
    b = bubble[bubble["sector"] == "B"].iloc[0]
    # B size = |0*10 + 5*2| = 10
    assert math.isclose(b["size_yi"], 10.0, abs_tol=1e-9)


# ══════════════════════════════════════════════════════════════════════
# 8. classify_quadrant 直接測(含 x=0 邊界)
# ══════════════════════════════════════════════════════════════════════
def test_classify_quadrant_direct():
    assert classify_quadrant(1.0, 1.0) == QUADRANT_RISING
    assert classify_quadrant(1.0, -1.0) == QUADRANT_ROTATING
    assert classify_quadrant(-1.0, -1.0) == QUADRANT_EBBING
    assert classify_quadrant(-1.0, 1.0) == QUADRANT_WATCHING
    # 邊界:x=0 視為右半(>=0);y=0 視為上半 → 漲潮
    assert classify_quadrant(0.0, 0.0) == QUADRANT_RISING
    # y 不可算 → 資料不足
    assert classify_quadrant(1.0, float("nan")) == QUADRANT_INSUFFICIENT
    assert classify_quadrant(1.0, None) == QUADRANT_INSUFFICIENT


# ══════════════════════════════════════════════════════════════════════
# 9. 空輸入邊界
# ══════════════════════════════════════════════════════════════════════
def test_empty_inst_returns_empty():
    sd, cov = compute_sector_daily_net(pd.DataFrame(), pd.DataFrame(), {})
    assert sd.empty
    assert cov["n_stock_days_with_net"] == 0


def test_empty_price_all_dropped():
    day = pd.Timestamp("2026-08-07")
    inst = pd.DataFrame([_inst_row(day, "2330", f=100.0)])
    sd, cov = compute_sector_daily_net(inst, pd.DataFrame(), {"2330": "半導體業"})
    assert sd.empty
    assert cov["n_dropped_missing_price"] == 1


def test_empty_sector_daily_bubble():
    bubble, meta = compute_bubble(pd.DataFrame())
    assert bubble.empty
    assert meta["n_sectors"] == 0


# ══════════════════════════════════════════════════════════════════════
# 10. map_tickers_to_sectors
# ══════════════════════════════════════════════════════════════════════
def test_map_tickers_to_sectors():
    imap = {"2330": "半導體業", "2881": "金融保險業"}
    out = map_tickers_to_sectors(["2330", "2881", "9999", "2330"], imap)
    assert out == {
        "2330": "半導體業",
        "2881": "金融保險業",
        "9999": SECTOR_UNCLASSIFIED,   # 未收錄 → 未分類(不猜)
    }


def test_map_tickers_empty():
    assert map_tickers_to_sectors([], {"2330": "半導體業"}) == {}


# ══════════════════════════════════════════════════════════════════════
# 11. 端到端:換算 → 彙總 → 泡泡(sort by size desc)
# ══════════════════════════════════════════════════════════════════════
def test_end_to_end_sort_by_size():
    dates = _bdays(20)
    inst_rows, price_rows = [], []
    for d in dates:
        inst_rows.append(_inst_row(d, "2330", f=100.0))   # 半導體
        inst_rows.append(_inst_row(d, "2881", f=10.0))    # 金融(規模小)
        price_rows.append({"date": d, "stock_id": "2330", "close": 100.0})
        price_rows.append({"date": d, "stock_id": "2881", "close": 100.0})
    imap = {"2330": "半導體業", "2881": "金融保險業"}
    sd, _ = compute_sector_daily_net(pd.DataFrame(inst_rows),
                                     pd.DataFrame(price_rows), imap)
    bubble, _ = compute_bubble(sd)
    # size desc → 半導體(每日 0.1 億 ×20 = 2 億)排第一
    assert bubble.iloc[0]["sector"] == "半導體業"
    assert bubble.iloc[-1]["sector"] == "金融保險業"
    assert math.isclose(bubble.iloc[0]["size_yi"], 2.0, abs_tol=1e-9)
