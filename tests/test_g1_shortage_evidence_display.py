"""DEC-154 G1：缺貨『資料資格』顯示層（原始分數與資料資格分離）。合成資料，不代表真實市場。

守住：分數／tier／composite／百分位／排序不變；n_ok<4 的低分不寫成確定『缺貨弱』；
n_ok=0 無徽章；舊 row／舊呼叫相容；推播文案。G2/G3（入榜門檻／分流）未核准 → 本檔不測也不實作。
"""
from __future__ import annotations

import copy
import datetime as dt
import random

import pandas as pd
import pytest

from shared.shortage_screen_thresholds import TIER_INSUFFICIENT, TIER_MID, TIER_STRONG, TIER_WEAK
from src.compute.notify.signal_message import format_shortage_badge, format_signal_message
from src.compute.screener.shortage_screener import (
    EVID_FULL, EVID_NONE, EVID_PARTIAL, EVID_UNASSESSED, SHORTAGE_NO_ROW_TEXT,
    ShortageScore, evidence_status, evidence_text, rank_shortage, score_shortage, to_rows,
)
from tests.test_short_dec149_signal_ok_flags import (
    _all_missing_stock, _null, _real_low_quarters, _stock, _strong_quarters,
)

_LOW_YOY = [-5.0, -3.0, -8.0]


def _row(stock):
    return score_shortage(stock).to_row()


def _partial_weak(n):
    """造 n_ok=n(1~3) 且 TIER_WEAK 的合成股：以真低分季報為底，逐項挖掉資料。"""
    qs = _real_low_quarters()
    if n == 3:      # 只缺 C1（合約負債）
        return _stock(_null(qs, "contract_liab"), yoy=_LOW_YOY)
    if n == 2:      # 缺 C1+C3
        return _stock(_null(qs, "contract_liab", "inventory"), yoy=_LOW_YOY)
    if n == 1:      # 只剩 C4
        return _stock(_null(qs, "contract_liab", "gross_profit", "inventory"), yoy=_LOW_YOY)
    raise ValueError(n)


# ── 顯示規則表：n_ok 0~4 ───────────────────────────────────────
@pytest.mark.parametrize("n", [1, 2, 3])
def test_partial_weak_not_declared_as_definite_weak(n):
    r = score_shortage(_partial_weak(n))
    assert r.n_signals_ok == n and r.tier == TIER_WEAK          # _tier 不動
    row = r.to_row()
    assert row["_evidence_status"] == EVID_PARTIAL
    assert f"部分有效證據 {n}/4" in row["資料資格"] and "缺：" in row["資料資格"]
    assert "非確定" in row["訊號強度"] and f"{n}/4" in row["訊號強度"]
    badge = format_shortage_badge({"tier": r.tier, "n_ok": r.n_signals_ok})
    assert "缺貨弱" not in badge and f"部分證據 {n}/4" in badge


def test_n0_no_badge_and_text_distinguishes_not_zero():
    r = score_shortage(_all_missing_stock())
    assert r.n_signals_ok == 0 and r.tier == TIER_INSUFFICIENT
    assert format_shortage_badge({"tier": r.tier, "n_ok": 0}) == ""
    assert format_shortage_badge({"tier": TIER_WEAK, "n_ok": 0}) == ""     # 即使被誤傳 WEAK 也不印
    t = r.to_row()["資料資格"]
    assert "無法評估" in t and "不是 0 分" in t


def test_n4_real_low_score_still_weak():
    r = score_shortage(_stock(_real_low_quarters(), yoy=_LOW_YOY))
    assert r.n_signals_ok == 4 and r.tier == TIER_WEAK
    row = r.to_row()
    assert row["訊號強度"] == f"{r.tier_icon} {TIER_WEAK}"                 # 完整證據下維持原樣
    assert row["_evidence_status"] == EVID_FULL and "證據完整 4/4" in row["資料資格"]
    assert format_shortage_badge({"tier": r.tier, "n_ok": 4}) == "缺貨弱"


def test_strong_mid_badge_annotated_when_partial():
    assert format_shortage_badge({"tier": TIER_STRONG, "n_ok": 3}) == "缺貨強（部分證據 3/4）"
    assert format_shortage_badge({"tier": TIER_MID, "n_ok": 2}) == "缺貨中（部分證據 2/4）"
    assert format_shortage_badge({"tier": TIER_STRONG, "n_ok": 4}) == "缺貨強"


def test_true_zero_vs_none_distinguishable():
    full_low = _row(_stock(_real_low_quarters(), yoy=_LOW_YOY))            # 有資料的低分
    missing = _row(_partial_weak(1))
    assert full_low["資料資格"] != missing["資料資格"]
    assert full_low["_c1_ok"] is True and missing["_c1_ok"] is False


# ── 來源失敗／月份鍵未驗證／單一來源失敗 ─────────────────────────
def test_fail_closed_source_failure_labelled():
    from src.compute.health.monthly_revenue_month_contract import mark_upstream_failed
    from tests.test_shortage_screener import _verified_contract
    stk = _stock(_strong_quarters(), yoy=[16.0, 18.0, 22.0])
    stk["revenue_month_contract"] = mark_upstream_failed(_verified_contract([16.0, 18.0, 22.0]))
    r = score_shortage(stk)
    assert r.c4_ok is False and r.n_signals_ok == 3
    row = r.to_row()
    assert "來源失敗" in row["資料資格"] and "FAIL_CLOSED" in row["資料資格"]


def test_key_unverified_note_on_full_evidence():
    stk = _stock(_strong_quarters(), yoy=[16.0, 18.0, 22.0])
    stk.pop("revenue_month_contract")                                      # 舊輸入＝月份鍵未驗證
    r = score_shortage(stk)
    assert r.n_signals_ok == 4
    assert "月份鍵未驗證" in r.to_row()["資料資格"]
    # 已驗證契約則無該註記
    assert "月份鍵未驗證" not in _row(_stock(_strong_quarters()))["資料資格"]


def test_single_source_failure_quarter_hole_is_partial():
    qs = _null(_strong_quarters(), "gross_profit")
    row = _row(_stock(qs))
    assert row["_evidence_status"] == EVID_PARTIAL and "②" in row["資料資格"]


# ── 不同路徑對相同資料顯示一致（批次帶 yoy3 vs 單股逐檔） ──────────
def test_batch_and_single_paths_same_display(monkeypatch):
    from src.compute.health.monthly_revenue_calc import compute_yoy_mom
    from src.compute.health.monthly_revenue_month_contract import MONTH_CONTRACT_KEY, extract_month_contract
    from src.services import shortage_screener_service as SVC
    from tests.test_c4e_unverified_key_cap import ASOF, INC, mk_df
    qs = _null(_strong_quarters(), "inventory")
    monkeypatch.setattr(SVC, "fetch_quarterly_shortage_frame", lambda sid: qs)
    monkeypatch.setattr(SVC, "_as_of_today", lambda: ASOF)
    monkeypatch.setattr(SVC, "fetch_monthly_revenue", lambda sid, months=18: mk_df(INC))
    st = compute_yoy_mom(mk_df(INC), as_of=ASOF)
    rows_a, _ = SVC._score_and_diagnose([("2330", st["yoy_last3"], extract_month_contract(st))])
    rows_b, _ = SVC._score_and_diagnose([("2330", None)])
    assert rows_a and rows_b
    for k in ("缺貨分數", "_tier", "資料資格", "訊號強度", "_n_signals_ok"):
        assert rows_a[0][k] == rows_b[0][k], k
    assert rows_a[0]["_n_signals_ok"] == 3 and "③" in rows_a[0]["資料資格"]


# ── 舊 row／舊呼叫相容 ────────────────────────────────────────
def test_legacy_row_and_legacy_calls():
    legacy = ShortageScore(stock_id="1", name="", total=50.0, tier=TIER_MID, tier_icon="",
                           c1_contract_liab=0, c2_gross_margin=0, c3_inventory_days=0,
                           c4_revenue_yoy=0, cl_na=False).to_row()
    assert legacy["_evidence_status"] == EVID_UNASSESSED and "未記錄" in legacy["資料資格"]
    assert legacy["訊號強度"] == f" {TIER_MID}"                            # 無 tier_icon：與修前同形
    # 舊簽章：純 tier 字串、n_ok 缺 → 行為與修前逐字相同
    assert format_shortage_badge(TIER_WEAK) == "缺貨弱"
    assert format_shortage_badge(TIER_STRONG) == "缺貨強"
    assert format_shortage_badge(None) == "" and format_shortage_badge(TIER_INSUFFICIENT) == ""
    assert format_shortage_badge({"tier": TIER_WEAK, "n_ok": None}) == "缺貨弱"   # 舊 row 無 n_ok
    assert format_shortage_badge({"tier": TIER_WEAK, "n_ok": float("nan")}) == "缺貨弱"
    assert format_shortage_badge({"tier": TIER_WEAK, "n_ok": 9}) == "缺貨弱"      # 越界不猜 → 舊行為
    assert evidence_status(True) == EVID_UNASSESSED


# ── 推播文案 ─────────────────────────────────────────────────
def test_push_message_lines():
    picks = [{"代碼": c, "名稱": "x", "綜合分": 80} for c in ("1111", "2222", "3333", "4444")]
    sb = {"1111": {"tier": TIER_WEAK, "n_ok": 2}, "2222": {"tier": TIER_WEAK, "n_ok": 4},
          "3333": {"tier": TIER_STRONG, "n_ok": 3}}
    msg = format_signal_message(picks, {}, as_of="t", shortage_by_code=sb)
    assert "缺貨：部分證據 2/4" in msg and msg.count("缺貨弱") == 1
    assert "缺貨強（部分證據 3/4）" in msg
    assert msg.count(SHORTAGE_NO_ROW_TEXT) == 1                              # 4444 無列 → 明講
    # 沒勾缺貨（空 map）→ 不加任何缺貨字樣（與修前相同）
    assert "缺貨" not in format_signal_message(picks, {}, as_of="t")


def test_ai_fact_lines_use_same_badge():
    from src.compute.notify.ai_judgment import build_fact_lines
    out = build_fact_lines([{"代碼": "1111", "名稱": "x", "綜合分": 80}], {},
                           shortage_by_code={"1111": {"tier": TIER_WEAK, "n_ok": 1}})
    assert "缺貨弱" not in out[0] and "部分證據 1/4" in out[0]


# ── parity：composite／百分位／排序與『不帶新欄位的舊 row』逐位元相同 ─────
def _synth(seed=7, n=150):
    rnd = random.Random(seed)
    stocks = []
    for i in range(n):
        qs = copy.deepcopy(_strong_quarters() if rnd.random() < .6 else _real_low_quarters())
        drop = [k for k in ("contract_liab", "gross_profit", "inventory") if rnd.random() < .35]
        qs = _null(qs, *drop) if drop else qs
        yoy = [rnd.choice([None, rnd.uniform(-20, 40)]) for _ in range(3)]
        stocks.append(_stock(qs, yoy=yoy, sid=f"{1101 + i}"))
    return stocks, rnd


def test_composite_parity_new_columns_not_in_ranking():
    from src.services.fundamental_screener_service import composite_rank_candidates
    stocks, rnd = _synth()
    rows = to_rows(rank_shortage(stocks))
    _new_keys = ("資料資格", "_evidence_status", "有效訊號數", "缺值原因", "_n_signals_ok",
                 "_c1_ok", "_c2_ok", "_c3_ok", "_c4_ok")    # 修前 row 只有 10 個舊鍵
    old_style = [{k: v for k, v in r.items() if k not in _new_keys} for r in rows]
    surv = pd.DataFrame({"stock_id": [s["stock_id"] for s in stocks],
                         "eps": [rnd.uniform(1, 9) for _ in stocks]})
    a, na = composite_rank_candidates(surv, factors=["shortage", "eps_high"], shortage_rows=rows)
    b, nb = composite_rank_candidates(surv, factors=["shortage", "eps_high"], shortage_rows=old_style)
    pd.testing.assert_frame_equal(a, b, check_exact=True)
    assert na == nb
    # 顯示變化檔數 > 0（確認測試真的涵蓋部分證據列），但分數欄與 tier 完全一致
    assert sum(1 for r in rows if r["_evidence_status"] == EVID_PARTIAL) > 0
    assert [(r["缺貨分數"], r["_tier"]) for r in rows] == [(r["缺貨分數"], r["_tier"]) for r in old_style]


def test_scores_unchanged_by_display_layer():
    """分數／tier 與『同輸入的各分項加總』一致（顯示層不改 total）。"""
    for s in _synth(3, 60)[0]:
        r = score_shortage(s)
        assert r.total == r.c1_contract_liab + r.c2_gross_margin + r.c3_inventory_days + r.c4_revenue_yoy
        assert evidence_text(r.n_signals_ok, r.miss_reason)  # 永遠有字樣
