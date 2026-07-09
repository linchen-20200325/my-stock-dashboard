"""tests/test_shortage_screener.py — 缺貨選股 L2 純函式測試（v19.65）。

覆蓋:四訊號各級距、綜合分級、邊界（空/不足/金融股/無合約負債科目/除零）、
排序、輸出 schema、及「絕不拋 Exception」韌性。全用合成資料（容器內對外被 proxy 擋）。
"""
from __future__ import annotations

import pytest

from shared.shortage_screen_thresholds import (
    SHORTAGE_CL_GROWTH_SCORE,
    SHORTAGE_CL_SURGE_SCORE,
    SHORTAGE_GM_DUAL_UP_SCORE,
    SHORTAGE_GM_SINGLE_UP_SCORE,
    SHORTAGE_INV_DUAL_DOWN_SCORE,
    SHORTAGE_INV_SINGLE_DOWN_SCORE,
    SHORTAGE_REV_STEADY_SCORE,
    SHORTAGE_REV_STRONG_SCORE,
    SHORTAGE_W_CONTRACT_LIAB,
    TIER_INSUFFICIENT,
    TIER_MID,
    TIER_NA,
    TIER_STRONG,
    TIER_WEAK,
)
from src.compute.screener.shortage_screener import (
    ShortageScore,
    rank_shortage,
    score_shortage,
    to_rows,
)


# ════════════════════════════════════════════════════════════════
# 合成資料工廠
# ════════════════════════════════════════════════════════════════
def _q(rev, gp, cogs, cl, inv, label="Q"):
    return {"label": label, "revenue": rev, "gross_profit": gp,
            "cogs": cogs, "contract_liab": cl, "inventory": inv}


def _strong_quarters():
    """8 季（近→遠）：合約負債 YoY 33%/QoQ 25%、毛利率雙升、存貨天數雙降。"""
    return [
        _q(1000, 600, 400, 200, 300, "2025Q1"),  # idx0 t
        _q(1000, 550, 400, 160, 350, "2024Q4"),  # idx1 t-1
        _q(1000, 540, 400, 150, 360, "2024Q3"),
        _q(1000, 530, 400, 150, 380, "2024Q2"),
        _q(1000, 500, 400, 150, 400, "2024Q1"),  # idx4 t-4
        _q(1000, 500, 400, 140, 400, "2023Q4"),
        _q(1000, 500, 400, 140, 400, "2023Q3"),
        _q(1000, 500, 400, 140, 400, "2023Q2"),  # idx7
    ]


def _strong_stock(**over):
    base = {"stock_id": "2330", "name": "台積電", "is_finance": False,
            "quarters": _strong_quarters(), "revenue_yoy_last3": [16.0, 18.0, 22.0]}
    base.update(over)
    return base


# ════════════════════════════════════════════════════════════════
# Golden：全訊號滿分 → 100 / 強缺貨
# ════════════════════════════════════════════════════════════════
def test_golden_strong_shortage_full_score():
    r = score_shortage(_strong_stock())
    assert isinstance(r, ShortageScore)
    assert r.c1_contract_liab == SHORTAGE_W_CONTRACT_LIAB   # 35（surge 35 + qoq bonus 封頂）
    assert r.c2_gross_margin == SHORTAGE_GM_DUAL_UP_SCORE   # 25
    assert r.c3_inventory_days == SHORTAGE_INV_DUAL_DOWN_SCORE  # 20
    assert r.c4_revenue_yoy == SHORTAGE_REV_STRONG_SCORE    # 20
    assert r.total == 100.0
    assert r.tier == TIER_STRONG
    assert r.cl_na is False
    assert r.tier_icon == "🟥"


# ════════════════════════════════════════════════════════════════
# ① 合約負債各級距
# ════════════════════════════════════════════════════════════════
def test_cl_surge_yoy_gets_full():
    # YoY 200/150-1 = 33% ≥ 30 → surge 35
    r = score_shortage(_strong_stock())
    assert r.metrics["cl_yoy"] == pytest.approx(33.33, abs=0.1)
    assert r.c1_contract_liab == SHORTAGE_W_CONTRACT_LIAB


def test_cl_growth_yoy_gets_growth_score_no_qoq_bonus():
    qs = _strong_quarters()
    # 調成 YoY 20%（在 15~30 之間）、QoQ 微幅（<20 無 bonus）
    qs[0]["contract_liab"] = 180   # t
    qs[1]["contract_liab"] = 178   # QoQ = 180/178-1 = 1.1% < 20
    for i in range(4, 8):
        qs[i]["contract_liab"] = 150  # t-4 = 150 → YoY 20%
    r = score_shortage(_strong_stock(quarters=qs))
    assert r.metrics["cl_yoy"] == pytest.approx(20.0, abs=0.1)
    assert r.c1_contract_liab == SHORTAGE_CL_GROWTH_SCORE  # 20


def test_cl_below_threshold_scores_zero():
    qs = _strong_quarters()
    for i in range(8):
        qs[i]["contract_liab"] = 100  # 全平 → YoY 0 / QoQ 0
    r = score_shortage(_strong_stock(quarters=qs))
    assert r.c1_contract_liab == 0.0


# ════════════════════════════════════════════════════════════════
# ② 毛利率
# ════════════════════════════════════════════════════════════════
def test_gm_single_up_gets_half():
    qs = _strong_quarters()
    # gm_t=60 > gm_t1=55（季增）但 gm_t4=65（年增未過）→ 半分
    qs[4]["gross_profit"] = 650  # gm_t4 = 65
    r = score_shortage(_strong_stock(quarters=qs))
    assert r.c2_gross_margin == SHORTAGE_GM_SINGLE_UP_SCORE  # 12


def test_gm_no_up_scores_zero():
    qs = _strong_quarters()
    qs[0]["gross_profit"] = 400   # gm_t = 40 < gm_t1(55) 且 < gm_t4(50)
    r = score_shortage(_strong_stock(quarters=qs))
    assert r.c2_gross_margin == 0.0


# ════════════════════════════════════════════════════════════════
# ③ 存貨天數
# ════════════════════════════════════════════════════════════════
def test_inventory_single_down_with_5_quarters():
    """僅 5 季 → 無法算 t-4 的 DIO（需 cogs idx4..7）→ 只判 QoQ → 單降 10 分。"""
    qs = _strong_quarters()[:5]  # 只留 5 季
    r = score_shortage(_strong_stock(quarters=qs))
    assert r.metrics["dio_t4"] is None
    assert r.c3_inventory_days == SHORTAGE_INV_SINGLE_DOWN_SCORE  # 10


def test_inventory_no_down_scores_zero():
    qs = _strong_quarters()
    qs[0]["inventory"] = 500   # 存貨變高 → DIO 上升
    r = score_shortage(_strong_stock(quarters=qs))
    assert r.c3_inventory_days == 0.0


# ════════════════════════════════════════════════════════════════
# ④ 月營收 YoY
# ════════════════════════════════════════════════════════════════
def test_revenue_steady_not_increasing_gets_mid():
    # 皆 > 15 但非遞增 → 穩健 12
    r = score_shortage(_strong_stock(revenue_yoy_last3=[22.0, 18.0, 16.0]))
    assert r.c4_revenue_yoy == SHORTAGE_REV_STEADY_SCORE  # 12


def test_revenue_below_threshold_scores_zero():
    r = score_shortage(_strong_stock(revenue_yoy_last3=[2.0, 3.0, 1.0]))
    assert r.c4_revenue_yoy == 0.0


# ════════════════════════════════════════════════════════════════
# 邊界
# ════════════════════════════════════════════════════════════════
def test_insufficient_quarters_flagged():
    r = score_shortage(_strong_stock(quarters=_strong_quarters()[:4]))  # 4 < 5
    assert r.tier == TIER_INSUFFICIENT
    assert r.total == 0.0


def test_finance_stock_not_applicable():
    r = score_shortage(_strong_stock(is_finance=True))
    assert r.tier == TIER_NA
    assert "金融股" in r.reason_text


def test_no_contract_liability_flags_cl_na_and_downgrades():
    """無合約負債科目：C1=0、cl_na=True，且原本會達強訊號者降級為中度。"""
    qs = _strong_quarters()
    for q in qs:
        q["contract_liab"] = None
    r = score_shortage(_strong_stock(quarters=qs))
    assert r.cl_na is True
    assert r.c1_contract_liab == 0.0
    # c2+c3+c4 = 25+20+20 = 65 → 原判強，因無合約負債降級為中度
    assert r.total == 65.0
    assert r.tier == TIER_MID
    assert any("降級" in x for x in r.reasons)


def test_zero_revenue_and_zero_cogs_no_crash_no_fake():
    qs = _strong_quarters()
    for q in qs:
        q["revenue"] = 0    # gm 除零 → None
        q["cogs"] = 0       # DIO 除零 → None
    r = score_shortage(_strong_stock(quarters=qs))
    assert r.c2_gross_margin == 0.0
    assert r.c3_inventory_days == 0.0
    assert r.metrics["gm_t"] is None
    assert r.metrics["dio_t"] is None


def test_weak_tier_low_total():
    # 只有月營收部分達標，其餘全 0 → 低分 → 不明顯
    qs = _strong_quarters()
    for q in qs:
        q["contract_liab"] = 100          # CL 全平 → 0
        q["gross_profit"] = 500           # gm 全平 → 未走揚 0
        q["inventory"] = 400              # DIO 全平 → 未降 0
    r = score_shortage(_strong_stock(quarters=qs, revenue_yoy_last3=[20.0, 5.0, 3.0]))
    assert r.tier == TIER_WEAK
    assert r.total < 40.0


# ════════════════════════════════════════════════════════════════
# 韌性：任何 garbage 不拋
# ════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("bad", [None, "x", 123, [], {}, {"quarters": "nope"}])
def test_score_never_raises_on_garbage(bad):
    r = score_shortage(bad)
    assert isinstance(r, ShortageScore)
    assert r.tier in {TIER_NA, TIER_INSUFFICIENT}


# ════════════════════════════════════════════════════════════════
# 批次排序 + 輸出 schema
# ════════════════════════════════════════════════════════════════
def test_rank_sorts_desc_and_excludes_na_by_default():
    strong = _strong_stock(stock_id="2330")
    weakish = _strong_stock(stock_id="1111", revenue_yoy_last3=[2.0, 3.0, 1.0])  # 少 20 分
    insufficient = _strong_stock(stock_id="9999", quarters=_strong_quarters()[:3])
    out = rank_shortage([weakish, strong, insufficient])
    ids = [s.stock_id for s in out]
    assert ids == ["2330", "1111"]          # 強在前，資料不足被排除
    assert out[0].total >= out[1].total


def test_rank_include_na_puts_them_last():
    strong = _strong_stock(stock_id="2330")
    insufficient = _strong_stock(stock_id="9999", quarters=_strong_quarters()[:3])
    out = rank_shortage([insufficient, strong], include_na=True)
    assert out[0].stock_id == "2330"
    assert out[-1].tier == TIER_INSUFFICIENT


def test_rank_empty_returns_empty():
    assert rank_shortage([]) == []
    assert rank_shortage("not a list") == []


def test_to_rows_schema():
    rows = to_rows(rank_shortage([_strong_stock()]))
    assert len(rows) == 1
    row = rows[0]
    for col in ["代碼", "名稱", "缺貨分數", "訊號強度",
                "①合約負債", "②毛利率", "③存貨天數", "④月營收", "理由"]:
        assert col in row
    assert row["代碼"] == "2330"
    assert row["缺貨分數"] == 100.0
    assert "🟥" in row["訊號強度"]
