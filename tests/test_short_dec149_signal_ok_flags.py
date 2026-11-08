"""tests/test_short_dec149_signal_ok_flags.py — DEC-149 Phase 3B（2026-11-08）缺貨「有效訊號旗標」與四項全缺排除。

客戶核准（DEC-149）：缺貨排名採至少兩項有效獨立證據的資格方向；四項全缺排除正式排名、保留無法評估診斷。
本批**只做**已核准且可由既有程式定義判定的最小修正：
  · score_shortage / ShortageScore / to_row 新增 n_signals_ok、c1_ok~c4_ok、miss_reason（schema-additive）；
  · n_signals_ok == 0 → 重用 TIER_INSUFFICIENT（無法評估）,不進正式排名,rank_shortage(include_na=True) 可查診斷。
⛔ 不測也不實作：『至少兩項有效獨立』資格、任何封頂、C4『valid 壓縮』計分語意（屬未裁定,另待客戶）。
全部合成資料,零網路。
"""
from __future__ import annotations

import copy

from shared.shortage_screen_thresholds import (
    TIER_INSUFFICIENT,
    TIER_MID,
    TIER_NA,
    TIER_STRONG,
    TIER_WEAK,
)
from src.compute.screener.shortage_screener import (
    rank_shortage,
    score_shortage,
    to_rows,
)
from tests.test_shortage_screener import _q, _strong_quarters, _strong_stock

_OLD_ROW_KEYS = ("代碼", "名稱", "缺貨分數", "訊號強度", "①合約負債", "②毛利率",
                 "③存貨天數", "④月營收", "理由", "_tier")
_YOY_OK = [16.0, 18.0, 22.0]


def _stock(quarters=None, yoy=_YOY_OK, sid="2330"):
    return {"stock_id": sid, "name": "x", "is_finance": False,
            "quarters": quarters if quarters is not None else _strong_quarters(),
            "revenue_yoy_last3": yoy}


def _null(quarters, *keys):
    qs = copy.deepcopy(quarters)
    for q in qs:
        for k in keys:
            q[k] = None
    return qs


# ── 四項完整且強缺貨 ────────────────────────────────────────────
def test_all_four_ok_strong():
    r = score_shortage(_stock())
    assert (r.c1_ok, r.c2_ok, r.c3_ok, r.c4_ok) == (True, True, True, True)
    assert r.n_signals_ok == 4 and r.miss_reason == ""
    assert r.total == 100.0 and r.tier == TIER_STRONG


# ── 僅兩項有效（C1、C4）,其餘缺值：旗標與原因正確,分數不變 ──────────
def test_only_two_ok_flags_and_scores_unchanged():
    qs = _null(_strong_quarters(), "gross_profit", "inventory")
    r = score_shortage(_stock(qs))
    assert (r.c1_ok, r.c2_ok, r.c3_ok, r.c4_ok) == (True, False, False, True)
    assert r.n_signals_ok == 2
    assert "②毛利率資料不足" in r.miss_reason and "③存貨天數資料不足" in r.miss_reason
    assert "①" not in r.miss_reason and "④" not in r.miss_reason
    # 分數數值照舊：C1 35（surge+bonus 封頂）、C4 20、C2/C3 缺值 0
    assert (r.c1_contract_liab, r.c2_gross_margin, r.c3_inventory_days, r.c4_revenue_yoy) == (35.0, 0.0, 0.0, 20.0)
    assert r.total == 55.0 and r.tier == TIER_MID      # 只有兩項有效仍照舊分級,不封頂、不排除


# ── 僅一項有效 ─────────────────────────────────────────────────
def test_only_one_ok_still_ranked_as_before():
    qs = _null(_strong_quarters(), "gross_profit", "inventory")
    r = score_shortage(_stock(qs, yoy=[None, None, None]))
    assert (r.c1_ok, r.c2_ok, r.c3_ok, r.c4_ok) == (True, False, False, False)
    assert r.n_signals_ok == 1
    assert r.total == 35.0 and r.tier == TIER_WEAK      # 本批不實作『至少兩項』資格 → 行為不變
    assert [x.stock_id for x in rank_shortage([_stock(qs, yoy=[None] * 3)])] == ["2330"]


# ── 四項全缺 → 不進正式排名；include_na=True 可查診斷 ─────────────
def _all_missing_stock(sid="9999"):
    qs = _null(_strong_quarters(), "contract_liab", "gross_profit", "inventory")
    return _stock(qs, yoy=[None, None, None], sid=sid)


def test_all_four_missing_unassessable_and_excluded_from_formal_ranking():
    r = score_shortage(_all_missing_stock())
    assert r.n_signals_ok == 0
    assert (r.c1_ok, r.c2_ok, r.c3_ok, r.c4_ok) == (False, False, False, False)
    assert r.tier == TIER_INSUFFICIENT and r.cl_na is True
    assert r.total == 0.0                       # 分數數值不改
    assert "無法評估" in r.reason_text
    assert all(k in r.miss_reason for k in ("①", "②", "③", "④"))
    assert rank_shortage([_all_missing_stock()]) == []                       # 預設不含
    diag = rank_shortage([_all_missing_stock()], include_na=True)            # 診斷列仍可查
    assert len(diag) == 1 and diag[0].n_signals_ok == 0
    row = diag[0].to_row()
    assert row["_n_signals_ok"] == 0 and row["_tier"] == TIER_INSUFFICIENT and row["缺貨分數"] == 0.0


def test_formal_ranking_and_diagnostics_split():
    stocks = [_stock(sid="1111"), _all_missing_stock("9999"), _stock(sid="2222")]
    formal = rank_shortage(stocks)
    both = rank_shortage(stocks, include_na=True)
    assert [s.stock_id for s in formal] == ["1111", "2222"] or [s.stock_id for s in formal] == ["2222", "1111"]
    assert [s.stock_id for s in both][-1] == "9999" and len(both) == 3     # 無法評估沉底
    assert all(s.n_signals_ok == 4 for s in formal)


# ── 月營收缺、其他完整：分數不變、c4_ok False、n_ok 3 ────────────────
def test_monthly_revenue_missing_others_complete():
    with_rev = score_shortage(_stock())
    r = score_shortage(_stock(yoy=[None, None, 20.0]))        # 只有 1 個有效月 → C4 既有資料不足分支
    assert r.c4_ok is False and (r.c1_ok, r.c2_ok, r.c3_ok) == (True, True, True)
    assert r.n_signals_ok == 3 and "④月營收有效月數<2" in r.miss_reason
    assert (r.c1_contract_liab, r.c2_gross_margin, r.c3_inventory_days) == (
        with_rev.c1_contract_liab, with_rev.c2_gross_margin, with_rev.c3_inventory_days)
    assert r.c4_revenue_yoy == 0.0 and r.total == with_rev.total - with_rev.c4_revenue_yoy


# ── 合約負債不適用（cl_na）→ c1_ok False ───────────────────────────
def test_cl_na_marks_c1_not_ok():
    qs = _null(_strong_quarters(), "contract_liab")
    r = score_shortage(_stock(qs))
    assert r.cl_na is True and r.c1_ok is False
    assert (r.c2_ok, r.c3_ok, r.c4_ok) == (True, True, True) and r.n_signals_ok == 3
    assert "①合約負債無科目" in r.miss_reason
    assert r.tier == TIER_MID                  # 既有 cl_na 強訊號降中度封頂,照舊（非本批新增）


# ── 季報日期不齊（缺 t-4 那一季）──────────────────────────────────
def test_quarter_hole_marks_yoy_signals_not_ok():
    qs = _strong_quarters()
    assert qs[4]["label"] == "2024Q1"
    del qs[4]                                   # 缺去年同季 2024Q1 → 季序對齊後 t-4 查不到
    r = score_shortage(_stock(qs))
    assert r.metrics["quarter_aligned"] is True
    assert r.c2_ok is False                      # gm_t4 None
    # dio_t1 的 TTM 要 offset 1..4 四季,offset 4 缺 → dio_t1 None（既有 _dio_at 行為）→ C3 既有資料不足分支
    assert r.c3_ok is False
    assert r.c1_ok is True                       # QoQ 仍可算
    assert r.n_signals_ok == 2 and "②毛利率資料不足" in r.miss_reason and "③存貨天數資料不足" in r.miss_reason


# ── 真實四項低分但資料完整 → n_ok=4、不明顯、仍在榜 ─────────────────
def _real_low_quarters():
    # 合約負債持平、毛利率下滑、存貨天數上升 → 四項都算得出來,但都沒得分
    rows = []
    labels = ["2025Q1", "2024Q4", "2024Q3", "2024Q2", "2024Q1", "2023Q4", "2023Q3", "2023Q2"]
    for i, lab in enumerate(labels):
        rows.append(_q(1000, 300 + 30 * i, 700 - 30 * i, 100, 400 - 20 * i, lab))
    return rows


def test_real_low_scores_with_complete_data_stay_ranked():
    r = score_shortage(_stock(_real_low_quarters(), yoy=[-5.0, -3.0, -8.0]))
    assert r.n_signals_ok == 4 and r.miss_reason == ""
    assert r.total == 0.0 and r.tier == TIER_WEAK      # 真 0 分 ≠ 缺值
    assert [s.stock_id for s in rank_shortage([_stock(_real_low_quarters(), yoy=[-5.0, -3.0, -8.0])])] == ["2330"]
    # 與「四項全缺」同為 total 0.0：只有旗標能區分
    miss = score_shortage(_all_missing_stock())
    assert (r.total, miss.total) == (0.0, 0.0) and r.n_signals_ok != miss.n_signals_ok


# ── 早退路徑（輸入錯誤／金融股／季數不足）：旗標一致 ──────────────────
def test_early_exit_paths_flags():
    for bad, tier in ((None, TIER_NA), ({"stock_id": "2880", "is_finance": True}, TIER_NA),
                      (_stock(_strong_quarters()[:3]), TIER_INSUFFICIENT)):
        r = score_shortage(bad)
        assert r.tier == tier and r.n_signals_ok == 0
        assert (r.c1_ok, r.c2_ok, r.c3_ok, r.c4_ok) == (False,) * 4 and r.miss_reason


# ── 舊 consumer 相容：row 欄位只增不減;舊建構（無新欄位）仍可 to_row ──────
def test_row_is_superset_of_old_schema_and_legacy_construction_ok():
    row = to_rows(rank_shortage([_stock()]))[0]
    for k in _OLD_ROW_KEYS:
        assert k in row
    for k in ("有效訊號數", "缺值原因", "_n_signals_ok", "_c1_ok", "_c2_ok", "_c3_ok", "_c4_ok"):
        assert k in row
    from src.compute.screener.shortage_screener import ShortageScore
    legacy = ShortageScore(stock_id="1", name="", total=50.0, tier=TIER_MID, tier_icon="",
                           c1_contract_liab=0, c2_gross_margin=0, c3_inventory_days=0,
                           c4_revenue_yoy=0, cl_na=False)
    lr = legacy.to_row()
    assert lr["_n_signals_ok"] is None and lr["_c1_ok"] is None      # 未評估 ≠ 缺值(False)
    assert lr["缺貨分數"] == 50.0


# ── 消費者：被排除的股票缺貨因子視為『無資料』,不是 0 分墊底 ──────────────
def _service_rows(stocks):
    from src.services.shortage_screener_service import _RANKABLE_TIERS
    return [s.to_row() for s in rank_shortage(stocks, include_na=True) if s.tier in _RANKABLE_TIERS]


def test_l3_row_filter_drops_unassessable():
    rows = _service_rows([_stock(sid="1111"), _all_missing_stock("9999")])
    assert [r["代碼"] for r in rows] == ["1111"]


def test_composite_treats_excluded_as_no_data_not_zero():
    import pandas as pd

    from src.services.fundamental_screener_service import composite_rank_candidates
    rows = _service_rows([_stock(sid="1111"), _stock(_real_low_quarters(), yoy=[-5.0, -3.0, -8.0], sid="2222"),
                          _all_missing_stock("9999")])
    surv = pd.DataFrame({"stock_id": ["1111", "2222", "9999"], "eps": [5.0, 4.0, 3.0]})
    df, _ = composite_rank_candidates(surv, factors=["shortage"], shortage_rows=rows)
    sc = dict(zip(df["代碼"], df["缺貨分"]))
    assert sc["1111"] == 100.0 and sc["2222"] == 50.0       # 真 0 分仍是有資料的最低百分位
    assert sc["9999"] is None or sc["9999"] != sc["9999"]    # 被排除者:空白(無資料),不是 0 也不是墊底百分位


# ── 推播徽章：排除列不顯示『缺貨弱』 ────────────────────────────────
def test_badge_not_shown_for_unassessable():
    from src.compute.notify.signal_message import format_shortage_badge
    r = score_shortage(_all_missing_stock())
    assert format_shortage_badge(r.tier) == ""
    assert format_shortage_badge(TIER_WEAK) == "缺貨弱"       # 真低分仍顯示（對照）


# ── forward_test 凍結 schema 不變 ───────────────────────────────────
def test_forward_test_frozen_schema_unchanged():
    from src.compute.screener.forward_test import PICK_SNAPSHOT_HEADERS
    assert PICK_SNAPSHOT_HEADERS == ("cohort", "stock_id", "name", "entry_price", "factors", "frozen_at")
