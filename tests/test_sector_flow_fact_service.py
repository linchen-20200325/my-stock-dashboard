"""tests/test_sector_flow_fact_service.py — 板塊事實(唯讀 L3)單元測試(Issue #1140 §B／G-3／G-10).

守的是 `src/services/sector_flow_fact_service.py::get_sector_flow_fact` 與 L1 新讀函式的合約:
  - 口徑:最新交易日各板塊「三大法人合計」淨額(億元)—— 不是 bubble 的近 5 日 x_yi,不是僅外資
  - 缺值 ≠ 0:最新日無列 = 未觀測,不補 0、不入合計;NaN/inf → UNAVAILABLE,不 fillna
  - 對帳 / 去重 / 計數恆等式;partial / unknown 不得給合計與計數;rows 固定依板塊名排序(無 Top-N)
  - 唯讀 / 零網路 / 不碰持股、gsheet、UI;無「全市場」欄位或碼
全部零網路:tmp_path + monkeypatch reader 路徑 + 注入 today。
"""
from __future__ import annotations

import ast
import dataclasses
import json
import math
import random
import socket
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# barrel / service import 在前(之後才 patch 網路,避免 import 副作用被誤判)
import src.services.sector_flow_fact_service as S
from shared.sector_flow_fact_thresholds import (
    SECTOR_NET_FLAT_EPS_YI,
    SECTOR_NET_RECONCILE_ABS_TOL_YI,
)
from shared.sector_flow_thresholds import SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS
from shared.ui2_contract.models import FieldState
from src.data.sector_flow import reader as R

REPO = Path(__file__).resolve().parents[1]
SERVICE_REL = "src/services/sector_flow_fact_service.py"
TODAY = date(2026, 11, 10)
OBS = "2026-11-09"
EXEC = "2026-11-09T09:00:00+00:00"        # cron 執行時間(台北同日 17:00)
EPS = SECTOR_NET_FLAT_EPS_YI

# 故意讓「bubble 列序 / 金額序 / 名稱序」三者互不相同
UNIVERSE = ["食品工業", "航運業", "水泥工業", "半導體業", "ETF"]            # bubble 依 size 排(≠ 名稱序)
NAME_ORDER = ["ETF", "半導體業", "水泥工業", "航運業", "食品工業"]            # sorted() 結果


# ═══════════════════════════════════════════════════════════════════════
# fixture 工廠
# ═══════════════════════════════════════════════════════════════════════
def drow(sector, f, t, d, *, date_="2026-11-09", n=5, twse=True, tpex=True, ind=True, net=None):
    return {"date": pd.Timestamp(date_), "sector": sector,
            "net_amt_yi": (f + t + d) if net is None else net,
            "foreign_yi": f, "trust_yi": t, "dealer_yi": d, "n_stocks": n,
            "twse_ok": twse, "tpex_ok": tpex, "industry_ok": ind}


def base_rows():
    return [
        # ETF 家族兩標籤 → 合併成「ETF」(-3.5 + -1.75 = -5.25;n 10+4)
        drow("ETF", -2.0, -1.0, -0.5, n=10),
        drow("上櫃ETF", -1.0, -0.5, -0.25, n=4),
        drow("半導體業", 8.0, 3.0, 1.0),
        drow("食品工業", 0.0, 0.0, 0.0),
        drow("水泥工業", -0.1, -0.1, -0.1),
        # 航運業:最新日無列(只出現在更早的日子)→ 未觀測
        drow("航運業", 1.0, 1.0, 1.0, date_="2026-11-06"),
        drow("半導體業", 99.0, 99.0, 99.0, date_="2026-11-06"),
    ]


def to_df(rows):
    df = pd.DataFrame(rows)
    for c in ("twse_ok", "tpex_ok", "industry_ok"):
        if c in df.columns:
            df[c] = pd.array(list(df[c]), dtype="boolean")
    return df


class Env:
    """可變的快取檔組;`.write()` 落檔並把 reader 路徑指向 tmp。"""

    def __init__(self, tmp_path, monkeypatch):
        self.tmp, self.mp = tmp_path, monkeypatch
        self.universe = list(UNIVERSE)
        self.members = {"ETF": ["ETF", "上櫃ETF"]}
        self.rows = base_rows()
        self.df = None                       # 設了就直接用(取代 rows)
        self.bubble_extra = {"tpex_complete": True, "n_absent_cells": 53}
        self.meta = {"updated_at": EXEC, "last_updated": OBS,
                     "coverage": {"n_excluded_foreign_ccy_stock_days": 4,
                                  "n_unclassified_stock_days": 0}}
        self.bubble_text = None              # 設了就原樣寫(測壞檔)
        self.bubble_names = {}               # 標準名 → bubble 內實際寫入的名稱(例:帶前後空白)
        self.omit_members = False            # True → bubble 板塊不帶 members 鍵
        self.write_bubble = self.write_meta = self.write_daily = True
        self.daily_bytes = None

    def write(self):
        R_ = R
        self.mp.setattr(R_, "BUBBLE_PATH", self.tmp / "bubble_latest.json")
        self.mp.setattr(R_, "META_PATH", self.tmp / "metadata.json")
        self.mp.setattr(R_, "TICKER_SECTOR_PATH", self.tmp / "ticker_sector.json")
        self.mp.setattr(R_, "DAILY_NET_PATH", self.tmp / "daily_net.parquet")
        if self.write_bubble:
            if self.bubble_text is not None:
                (self.tmp / "bubble_latest.json").write_text(self.bubble_text, encoding="utf-8")
            else:
                sectors = [{"sector": self.bubble_names.get(s, s), "x_yi": 123.0, "y_yi": 4.5,
                            "size_yi": 99.0, "quadrant": "X",
                            **({} if self.omit_members else {"members": self.members.get(s, [s])})}
                           for s in self.universe]
                (self.tmp / "bubble_latest.json").write_text(json.dumps(
                    {"updated_at": EXEC, "window_size": 20, "n_trading_days_used": 20,
                     "sectors": sectors, **self.bubble_extra}), encoding="utf-8")
        if self.write_meta:
            (self.tmp / "metadata.json").write_text(json.dumps(self.meta), encoding="utf-8")
        if self.write_daily:
            if self.daily_bytes is not None:
                (self.tmp / "daily_net.parquet").write_bytes(self.daily_bytes)
            else:
                (self.df if self.df is not None else to_df(self.rows)).to_parquet(
                    self.tmp / "daily_net.parquet")
        return self

    def fact(self, today=TODAY):
        return S.get_sector_flow_fact(today=today)


@pytest.fixture
def env(tmp_path, monkeypatch):
    return Env(tmp_path, monkeypatch)


def row_of(fact, name):
    return next(r for r in fact.rows if r.sector == name)


# ═══════════════════════════════════════════════════════════════════════
# 1. 快樂路徑:口徑 / 合併 / 排序 / 衍生聚合
# ═══════════════════════════════════════════════════════════════════════
def test_happy_path_facts_and_derived(env):
    f = env.write().fact()
    assert (f.state, f.reason, f.completeness) == (FieldState.OK, "ok", "complete")
    assert f.data_date == OBS and f.is_stale is False and f.stale_reason is None
    # 口徑常數:三大法人合計、最新交易日、億元(⛔ 不是僅外資)
    assert f.basis.institutions == ("foreign", "trust", "dealer")
    assert f.basis.window == "latest_trading_day" and f.basis.unit == "yi_twd"
    # ETF 家族兩標籤合併成一列;只取最新日(半導體 99 的舊日列不得進來)
    etf = row_of(f, "ETF")
    assert etf.net_yi == pytest.approx(-5.25) and etf.n_stocks == 14
    assert etf.members == ("ETF", "上櫃ETF") and etf.sign == "negative"
    assert row_of(f, "半導體業").net_yi == pytest.approx(12.0)
    assert row_of(f, "食品工業").sign == "flat" and row_of(f, "食品工業").net_yi == 0.0
    nc = row_of(f, "航運業")
    assert nc.net_yi is None and nc.n_stocks is None and nc.sign == "unobserved"   # 未觀測 ≠ 0
    d = f.derived
    assert d.is_derived is True and d.reconciled is True
    assert (d.n_positive, d.n_negative, d.n_flat, d.n_unobserved, d.n_universe) == (1, 2, 1, 1, 5)
    assert d.n_positive + d.n_negative + d.n_flat + d.n_unobserved == d.n_universe
    assert d.total_net_yi == pytest.approx(12.0 - 5.25 - 0.3) and d.raw_total_yi == pytest.approx(d.total_net_yi)
    cov = f.coverage
    assert (cov.n_universe, cov.n_observed, cov.n_unobserved) == (5, 4, 1)
    assert cov.unobserved_sectors == ("航運業",) and cov.n_absent_cells_window == 53
    assert cov.n_excluded_foreign_ccy == 4 and cov.tpex_complete_window is True
    assert cov.tpex_ok_on_data_date is True
    assert S.CAVEAT_SCOPE_INCLUDES_NON_COMMON_LABELS in f.caveats      # 合計含 ETF/ETN 等標籤,必揭露
    assert S.CAVEAT_FOREIGN_CCY_EXCLUDED in f.caveats and S.CAVEAT_SECTORS_UNOBSERVED in f.caveats
    assert all(r.is_derived is False for r in f.rows)


def test_rows_sorted_by_name_not_amount_and_not_bubble_order(env):
    f = env.write().fact()
    names = [r.sector for r in f.rows]
    assert names == NAME_ORDER == sorted(UNIVERSE)
    nets = [r.net_yi for r in f.rows if r.net_yi is not None]
    assert nets != sorted(nets) and nets != sorted(nets, reverse=True)      # 確實不是依金額
    assert names != UNIVERSE                                                # 也不是 bubble 的 size 序


def test_only_latest_day_used_not_window_sum(env):
    f = env.write().fact()
    assert row_of(f, "半導體業").net_yi == pytest.approx(12.0)              # 不含 11-06 的 297


def test_stale_state_still_computes_derived(env):
    f = env.write().fact(today=date(2026, 11, 14))                          # 距觀測日 5 日 > 4
    assert (f.state, f.reason, f.is_stale) == (FieldState.STALE, "stale", True)
    assert "超過" in f.stale_reason and f.derived is not None and len(f.rows) == 5


@pytest.mark.parametrize("today,stale", [(date(2026, 11, 13), False), (date(2026, 11, 14), True)])
def test_stale_boundary_4_days(env, today, stale):
    assert SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS == 4
    f = env.write().fact(today=today)
    assert f.is_stale is stale and f.reason == ("stale" if stale else "ok")


# ═══════════════════════════════════════════════════════════════════════
# 2. 判定順序:每個 reason 一個情境(窮舉 REASON_STATE)
# ═══════════════════════════════════════════════════════════════════════
def _bubble_missing(e):
    e.write_bubble = False


def _bubble_bad_json(e):
    e.bubble_text = "{not json"


def _bubble_bad_schema(e):
    e.bubble_text = json.dumps({"sectors": "oops"})


def _bubble_entry_bad(e):
    e.bubble_text = json.dumps({"sectors": [{"sector": ""}]})


def _daily_missing(e):
    e.write_daily = False


def _daily_empty(e):
    e.df = to_df(base_rows()).iloc[0:0]


def _daily_missing_col(e):
    e.df = to_df(base_rows()).drop(columns=["dealer_yi"])


def _daily_corrupt(e):
    e.daily_bytes = b"this is not parquet"


def _obs_none(e):
    e.meta.pop("last_updated")


def _obs_future(e):
    e.meta["last_updated"] = "2026-11-20"


def _date_disagree_older(e):
    e.meta["last_updated"] = "2026-11-06"


def _date_disagree_newer(e):
    e.rows.append(drow("半導體業", 1.0, 1.0, 1.0, date_="2026-11-10"))


def _dup(e):
    e.rows.append(drow("半導體業", 1.0, 1.0, 1.0))


def _nan(e):
    e.rows[2]["foreign_yi"] = float("nan")


def _inf(e):
    e.rows[2]["net_amt_yi"] = float("inf")


def _component(e):
    e.rows[2]["net_amt_yi"] += 0.5


def _universe_extra_label(e):
    e.rows.append(drow("玻璃陶瓷", 1.0, 1.0, 1.0))


def _universe_dup_in_bubble(e):
    e.universe.append("ETF")


def _universe_empty(e):
    e.universe = []


SCENARIOS = [
    ("bubble_missing", _bubble_missing, "bubble_not_produced"),
    ("bubble_bad_json", _bubble_bad_json, "reader_exception"),
    ("bubble_bad_schema", _bubble_bad_schema, "reader_exception"),
    ("bubble_entry_bad", _bubble_entry_bad, "reader_exception"),
    ("daily_missing", _daily_missing, "daily_net_unreadable"),
    ("daily_empty", _daily_empty, "daily_net_unreadable"),
    ("daily_missing_col", _daily_missing_col, "daily_net_unreadable"),
    ("daily_corrupt", _daily_corrupt, "daily_net_corrupt"),
    ("obs_none", _obs_none, "observation_date_unknown"),
    ("obs_future", _obs_future, "observation_date_unknown"),
    ("date_disagree_older", _date_disagree_older, "date_disagreement"),
    ("date_disagree_newer", _date_disagree_newer, "date_disagreement"),
    ("duplicate_rows", _dup, "integrity_duplicate_rows"),
    ("nan", _nan, "integrity_nonfinite"),
    ("inf", _inf, "integrity_nonfinite"),
    ("component", _component, "integrity_component_mismatch"),
    ("universe_extra_label", _universe_extra_label, "integrity_universe_mismatch"),
    ("universe_dup", _universe_dup_in_bubble, "integrity_universe_mismatch"),
    ("universe_empty", _universe_empty, "integrity_universe_mismatch"),
]


@pytest.mark.parametrize("name,tweak,reason", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_failure_scenarios(env, name, tweak, reason):
    tweak(env)
    f = env.write().fact()
    assert f.reason == reason, (f.reason, f.diagnostic)
    assert f.state is S.REASON_STATE[reason]
    # 非 OK/STALE 一律不帶 rows / derived / coverage(缺值 ≠ 0;不給半套數字)
    assert f.rows == () and f.derived is None and f.coverage is None and f.completeness == "unknown"


def test_state_split_missing_vs_unavailable(env):
    # 缺檔 → MISSING;壞檔 → UNAVAILABLE(同一個 daily_net 兩種不同態)
    _daily_missing(env)
    assert env.write().fact().state is FieldState.MISSING
    env.write_daily = True
    env.daily_bytes = b"garbage"
    assert env.write().fact().state is FieldState.UNAVAILABLE


def test_reconcile_failure_when_canonicalization_changes_total(env, monkeypatch):
    real = S.canonicalize_sector_daily

    def tampered(raw):
        canon, meta = real(raw)
        canon = canon.copy()
        canon.loc[canon.index[0], "net_amt_yi"] += 1.0
        return canon, meta

    monkeypatch.setattr(S, "canonicalize_sector_daily", tampered)
    f = env.write().fact()
    assert f.reason == "integrity_reconcile" and f.state is FieldState.UNAVAILABLE


def test_reconcile_failure_when_canonical_drops_a_row(env, monkeypatch):
    real = S.canonicalize_sector_daily
    monkeypatch.setattr(S, "canonicalize_sector_daily",
                        lambda raw: (real(raw)[0].iloc[1:], real(raw)[1]))
    assert env.write().fact().reason == "integrity_reconcile"


def test_component_identity_tolerance_edges(env):
    # 偏移 ≥ 1 個量化單位以上 → 失敗;遠小於容差的浮點雜訊 → 通過
    env.rows[2]["net_amt_yi"] += SECTOR_NET_RECONCILE_ABS_TOL_YI * 10
    assert env.write().fact().reason == "integrity_component_mismatch"
    env.rows = base_rows()
    env.rows[2]["net_amt_yi"] += 1e-12
    assert env.write().fact().reason == "ok"


def test_count_identity_failure_is_unavailable(env, monkeypatch):
    @dataclasses.dataclass(frozen=True)
    class LenientRow:                        # 拿掉 SectorNetRow 的自檢,模擬分類漏接
        sector: str
        net_yi: float | None
        n_stocks: int | None
        members: tuple
        sign: str
        is_derived: bool = False

    monkeypatch.setattr(S, "SectorNetRow", LenientRow)
    monkeypatch.setattr(S, "_sign_of", lambda net: "weird" if net == 0.0 else S.SIGN_POSITIVE)
    f = env.write().fact()
    assert f.reason == "integrity_count_identity" and f.state is FieldState.UNAVAILABLE


def test_unexpected_exception_becomes_unavailable_not_raise(env, monkeypatch):
    monkeypatch.setattr(S, "_sign_of", lambda net: (_ for _ in ()).throw(RuntimeError("boom")))
    f = env.write().fact()
    assert f.reason == "compute_exception" and f.state is FieldState.UNAVAILABLE
    assert "RuntimeError" in f.diagnostic


def test_reason_state_table_is_exhaustively_exercised(env, monkeypatch):
    """REASON_STATE 的每個 reason 至少有一個情境產出它(新增 reason 卻沒測 ⇒ 紅燈)。"""
    produced = {s[2] for s in SCENARIOS}
    produced |= {"ok", "stale", "integrity_reconcile", "integrity_count_identity", "compute_exception"}
    assert produced == set(S.REASON_STATE)
    assert {S.REASON_STATE[r] for r in S.REASON_STATE} <= set(FieldState)
    assert S.REASON_STATE["ok"] is FieldState.OK and S.REASON_STATE["stale"] is FieldState.STALE


def test_fact_rejects_inconsistent_reason_state():
    with pytest.raises(ValueError):
        S.SectorFlowFact(state=FieldState.OK, reason="reader_exception", data_date=None, is_stale=False,
                         stale_reason=None, source=S.SOURCE, basis=S.SECTOR_FLOW_BASIS,
                         completeness="unknown", caveats=(), coverage=None, rows=(), derived=None)
    with pytest.raises(ValueError):                    # 非 OK/STALE 不得帶 rows
        S.SectorFlowFact(state=FieldState.MISSING, reason="bubble_not_produced", data_date=None,
                         is_stale=False, stale_reason=None, source=S.SOURCE, basis=S.SECTOR_FLOW_BASIS,
                         completeness="unknown", caveats=(), coverage=None,
                         rows=(S.SectorNetRow("a", 1.0, None, (), "positive"),), derived=None)


# ═══════════════════════════════════════════════════════════════════════
# 3. 去重 / NaN / 零值 / 未觀測
# ═══════════════════════════════════════════════════════════════════════
def test_duplicate_rows_are_not_silently_summed_nor_dropped(env):
    env.rows.append(drow("半導體業", 1.0, 1.0, 1.0))
    f = env.write().fact()
    assert f.reason == "integrity_duplicate_rows" and f.derived is None and f.rows == ()


def test_duplicate_with_whitespace_label_also_caught(env):
    env.rows.append(drow("半導體業 ", 1.0, 1.0, 1.0))
    assert env.write().fact().reason == "integrity_duplicate_rows"


@pytest.mark.parametrize("col", ["net_amt_yi", "foreign_yi", "trust_yi", "dealer_yi"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_in_any_amount_column_is_unavailable_and_never_flat(env, col, bad):
    env.rows[2][col] = bad
    f = env.write().fact()
    assert f.reason == "integrity_nonfinite" and f.state is FieldState.UNAVAILABLE
    assert f.derived is None and f.rows == ()                      # NaN 不得被當 0 進持平計數


def test_nan_never_converted_to_zero(env):
    env.rows[3]["net_amt_yi"] = float("nan")                       # 食品工業(本來是 0.0)
    f = env.write().fact()
    assert f.reason == "integrity_nonfinite"


@pytest.mark.parametrize("x,sign", [
    (0.0, "flat"), (-0.0, "flat"), (EPS, "flat"), (-EPS, "flat"), (EPS / 10, "flat"),
    (EPS * 1.0001, "positive"), (EPS * 2, "positive"), (-EPS * 1.0001, "negative"),
    (-EPS * 2, "negative"), (1e-7, "positive"), (-1e-7, "negative"),
])
def test_zero_and_eps_sign_classification(env, x, sign):
    env.rows = [r for r in base_rows() if r["sector"] != "食品工業"] + [drow("食品工業", x, 0.0, 0.0)]
    f = env.write().fact()
    assert f.reason == "ok"
    r = row_of(f, "食品工業")
    assert r.sign == sign and r.net_yi == x
    d = f.derived
    assert d.n_positive + d.n_negative + d.n_flat + d.n_unobserved == d.n_universe
    expected_flat = 1 if sign == "flat" else 0
    assert d.n_flat == expected_flat


def test_zero_is_valid_observation_counted_flat_not_unobserved(env):
    f = env.write().fact()
    assert row_of(f, "食品工業").sign == "flat"
    assert f.derived.n_flat == 1 and f.derived.n_unobserved == 1


def test_unobserved_sectors_not_in_total_or_signs(env):
    f = env.write().fact()
    assert row_of(f, "航運業").sign == "unobserved"
    total = sum(r.net_yi for r in f.rows if r.net_yi is not None)
    assert f.derived.total_net_yi == pytest.approx(total)
    assert f.derived.n_positive + f.derived.n_negative + f.derived.n_flat == f.coverage.n_observed == 4


# ═══════════════════════════════════════════════════════════════════════
# 4. partial / unknown:不得給合計與計數;rows 照給
# ═══════════════════════════════════════════════════════════════════════
def _tpex_window_false(e):
    e.bubble_extra["tpex_complete"] = False


def _tpex_window_none(e):
    e.bubble_extra.pop("tpex_complete")


def _tpex_ok_false(e):
    e.rows[2]["tpex_ok"] = False


def _twse_ok_false(e):
    e.rows[2]["twse_ok"] = False


def _industry_ok_false(e):
    e.rows[3]["industry_ok"] = False


def _tpex_ok_na(e):
    e.rows[2]["tpex_ok"] = pd.NA


def _industry_ok_na(e):
    e.rows[2]["industry_ok"] = pd.NA


PARTIALS = [("tpex_window_false", _tpex_window_false), ("tpex_window_none", _tpex_window_none),
            ("tpex_ok_false", _tpex_ok_false), ("twse_ok_false", _twse_ok_false),
            ("industry_ok_false", _industry_ok_false), ("tpex_ok_na", _tpex_ok_na),
            ("industry_ok_na", _industry_ok_na)]


@pytest.mark.parametrize("name,tweak", PARTIALS, ids=[p[0] for p in PARTIALS])
def test_partial_gives_rows_but_no_derived(env, name, tweak):
    tweak(env)
    f = env.write().fact()
    assert f.state is FieldState.OK and f.completeness == "partial"
    assert f.derived is None                                       # 不給合計與計數
    assert len(f.rows) == 5 and row_of(f, "半導體業").net_yi == pytest.approx(12.0)   # rows 照給
    assert f.coverage is not None
    assert any(c.startswith(("tpex_window", "data_date_flag")) for c in f.caveats)


def test_flag_columns_absent_is_unknown_and_no_derived(env):
    env.df = to_df(base_rows()).drop(columns=["twse_ok", "tpex_ok", "industry_ok"])
    f = env.write().fact()
    assert f.completeness == "unknown" and f.derived is None and len(f.rows) == 5
    assert S.CAVEAT_FLAG_COLUMNS_ABSENT in f.caveats


@pytest.mark.parametrize("n_absent", [0, 53, None])
def test_absent_cells_do_not_affect_completeness(env, n_absent):
    if n_absent is None:
        env.bubble_extra.pop("n_absent_cells")
    else:
        env.bubble_extra["n_absent_cells"] = n_absent
    f = env.write().fact()
    assert f.completeness == "complete" and f.derived is not None
    assert (S.CAVEAT_ABSENT_CELLS in f.caveats) == bool(n_absent)


def test_disclose_only_conditions_never_block(env):
    env.meta["coverage"] = {"n_excluded_foreign_ccy_stock_days": 7, "n_unclassified_stock_days": 3}
    f = env.write().fact()
    assert f.completeness == "complete" and f.derived is not None
    assert S.CAVEAT_FOREIGN_CCY_EXCLUDED in f.caveats and S.CAVEAT_UNCLASSIFIED_STOCK_DAYS in f.caveats
    assert (f.coverage.n_excluded_foreign_ccy, f.coverage.n_unclassified_stock_days) == (7, 3)


# ═══════════════════════════════════════════════════════════════════════
# 4b. QA 補測(存活突變 M35/M32/M27/M26/M18)、F1/F2/F3/F4/F5
# ═══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("tweak", [_obs_none, _obs_future], ids=["obs_none", "obs_future"])
def test_observation_date_unknown_is_stale_true(env, tweak):          # M35
    tweak(env)
    f = env.write().fact()
    assert f.reason == "observation_date_unknown" and f.is_stale is True
    assert f.data_date is None


def test_observation_date_unknown_forces_stale_even_if_reader_says_fresh(env, monkeypatch):   # M35
    """防禦:即使 reader 回 is_stale=False 卻無觀測日,fact 仍必須 is_stale=True(未知觀測日 ≠ 新鮮)。"""
    env.write()
    real = R.read_sector_flow_cache

    def lying(**kw):
        return {**real(**kw), "observation_date": None, "is_stale": False, "stale_reason": None}

    monkeypatch.setattr(R, "read_sector_flow_cache", lying)
    f = env.fact()
    assert f.reason == "observation_date_unknown" and f.is_stale is True


def test_tpex_ok_on_data_date_tristate(env):                          # M32
    assert env.write().fact().coverage.tpex_ok_on_data_date is True
    env.rows[2]["tpex_ok"] = False
    assert env.write().fact().coverage.tpex_ok_on_data_date is False
    env.rows[2]["tpex_ok"] = pd.NA
    assert env.write().fact().coverage.tpex_ok_on_data_date is None
    env.rows = base_rows()
    env.df = to_df(base_rows()).drop(columns=["tpex_ok"])
    assert env.write().fact().coverage.tpex_ok_on_data_date is None


def test_bubble_sector_names_with_surrounding_whitespace_are_stripped(env):   # M27
    env.bubble_names = {"半導體業": " 半導體業 ", "ETF": "ETF\t"}
    f = env.write().fact()
    assert f.reason == "ok" and [r.sector for r in f.rows] == NAME_ORDER
    assert row_of(f, "半導體業").net_yi == pytest.approx(12.0)
    assert f.coverage.n_observed == 4 and f.derived is not None


def test_members_fall_back_to_canonical_meta_when_bubble_has_none(env):       # M26
    env.omit_members = True
    f = env.write().fact()
    assert f.reason == "ok"
    assert row_of(f, "ETF").members == ("ETF", "上櫃ETF")          # 來自 canonicalize meta
    assert row_of(f, "半導體業").members == ("半導體業",)
    assert row_of(f, "航運業").members == ()                        # 未觀測且 bubble 無 members → 空,不臆測


@pytest.mark.parametrize("raw,expect", [(True, None), (False, None), (3.7, None), (-1, None), ("5", None),
                                        (3.0, 3), (3, 3), (0, None)])
def test_n_absent_cells_strict_count(env, raw, expect):               # M18
    env.bubble_extra["n_absent_cells"] = raw
    f = env.write().fact()
    got = f.coverage.n_absent_cells_window
    if type(raw) is int and raw == 0:
        assert got == 0
    else:
        assert got == expect
    if raw is True:
        assert got is None and S.CAVEAT_ABSENT_CELLS not in f.caveats     # True 不得被當 1
    if raw == 3:
        assert S.CAVEAT_ABSENT_CELLS in f.caveats


def test_completeness_is_flag_completeness_not_coverage(env):         # F1
    assert "不代表板塊全覆蓋" in S.SectorFlowFact.__doc__ and "不代表板塊全覆蓋" in S.__doc__
    # 最新日 N=5 只有 1 個板塊有列;旗標全 True → 仍是 complete,覆蓋度只看 coverage / derived
    env.rows = [drow("半導體業", 8.0, 3.0, 1.0)] + \
               [drow(n, 1.0, 1.0, 1.0, date_="2026-11-06") for n in ("ETF", "食品工業", "水泥工業", "航運業")]
    f = env.write().fact()
    assert f.reason == "ok" and f.completeness == "complete"
    c, d = f.coverage, f.derived
    assert (c.n_universe, c.n_observed, c.n_unobserved) == (5, 1, 4)
    assert d is not None and (d.n_observed, d.n_unobserved, d.n_universe) == (1, 4, 5)
    assert d.n_positive == 1 and d.n_negative == 0 and d.n_flat == 0
    assert d.n_positive + d.n_negative + d.n_flat == d.n_observed
    assert d.total_net_yi == pytest.approx(12.0)
    assert S.CAVEAT_SECTORS_UNOBSERVED in f.caveats
    assert len(f.rows) == 5 and sum(r.sign == "unobserved" for r in f.rows) == 4
    blob = repr(f).lower()
    assert "market" not in blob and "全市場" not in blob


def test_derived_carries_as_of_and_is_stale(env):                     # F5
    f = env.write().fact()
    assert f.derived.as_of == OBS == f.data_date and f.derived.is_stale is False
    fs = env.fact(today=date(2026, 11, 14))
    assert fs.reason == "stale" and fs.derived.is_stale is True and fs.derived.as_of == OBS


def test_derived_rejects_bad_identity_or_missing_as_of():
    ok = dict(is_derived=True, total_net_yi=1.0, n_positive=1, n_negative=0, n_flat=0, n_unobserved=1,
              n_universe=2, reconciled=True, raw_total_yi=1.0, n_observed=1, as_of="2026-11-09", is_stale=False)
    S.SectorFlowDerived(**ok)
    for bad in ({"as_of": ""}, {"n_observed": 2}, {"n_universe": 3}, {"is_stale": None}):
        with pytest.raises(ValueError):
            S.SectorFlowDerived(**{**ok, **bad})


def test_cron_scope_caveats_and_n_days(env):                          # F2 / F3
    env.meta["coverage"] = {"n_excluded_foreign_ccy_stock_days": 4, "n_unclassified_stock_days": 2,
                            "n_days": 1}
    f = env.write().fact()
    assert f.coverage.cron_coverage_n_days == 1
    assert S.CAVEAT_FOREIGN_CCY_EXCLUDED.endswith("_last_cron_run_scope")
    assert S.CAVEAT_UNCLASSIFIED_STOCK_DAYS.endswith("_last_cron_run_scope")
    assert S.CAVEAT_FOREIGN_CCY_EXCLUDED in f.caveats and S.CAVEAT_UNCLASSIFIED_STOCK_DAYS in f.caveats
    env.meta["coverage"].pop("n_days")
    assert env.write().fact().coverage.cron_coverage_n_days is None
    env.meta["coverage"]["n_days"] = True                              # bool 不當 1
    assert env.write().fact().coverage.cron_coverage_n_days is None
    assert "last_cron_run" in (S.__doc__ or "") or "上一次 cron" in S.__doc__


@pytest.mark.parametrize("bad", [3.7, -2.0, float("inf"), float("-inf")])
def test_invalid_n_stocks_is_none_with_caveat_not_truncated(env, bad):       # F4
    env.rows[2]["n_stocks"] = bad                                      # 半導體業
    f = env.write().fact()
    assert f.reason == "ok"
    assert row_of(f, "半導體業").n_stocks is None                       # 不得截斷成 3 / 4
    assert S.CAVEAT_N_STOCKS_INVALID in f.caveats
    assert row_of(f, "半導體業").net_yi == pytest.approx(12.0)           # 金額不受影響


def test_sum_n_stocks_rejects_bool_and_garbage_directly():
    raw = pd.DataFrame({"sector": ["a", "b", "c"], "n_stocks": pd.Series([True, "x", 4], dtype="object")})
    out, invalid = S._sum_n_stocks(raw, {"a": "A", "b": "B", "c": "C"})
    assert out == {"C": 4} and invalid is True                          # bool / 亂字 → 無效;不當 0 / 1


def test_n_stocks_missing_is_none_without_invalid_caveat(env):
    env.rows[2]["n_stocks"] = pd.NA
    f = env.write().fact()
    assert row_of(f, "半導體業").n_stocks is None and S.CAVEAT_N_STOCKS_INVALID not in f.caveats
    assert row_of(f, "ETF").n_stocks == 14                             # ETF 家族成員加總仍正確
    env.df = to_df(base_rows()).drop(columns=["n_stocks"])
    f = env.write().fact()
    assert all(r.n_stocks is None for r in f.rows) and S.CAVEAT_N_STOCKS_INVALID not in f.caveats


def test_n_stocks_one_invalid_member_invalidates_merged_sector(env):
    env.rows[1]["n_stocks"] = 2.5                                      # 上櫃ETF
    f = env.write().fact()
    assert row_of(f, "ETF").n_stocks is None and S.CAVEAT_N_STOCKS_INVALID in f.caveats


def test_cron_coverage_missing_is_disclosed_not_zero(env):
    env.meta.pop("coverage")
    f = env.write().fact()
    assert f.coverage.n_excluded_foreign_ccy is None and f.coverage.n_unclassified_stock_days is None
    assert S.CAVEAT_CRON_COVERAGE_UNAVAILABLE in f.caveats and f.derived is not None


# ═══════════════════════════════════════════════════════════════════════
# 5. 計數恆等式 fuzz(固定 seed)
# ═══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("seed", range(40))
def test_count_identity_and_total_fuzz(env, seed):
    rnd = random.Random(seed)
    n = rnd.randint(3, 14)
    names = [f"板塊{i:02d}" for i in range(n)]
    rnd.shuffle(names)
    obs_mask = [rnd.random() > 0.25 for _ in names]
    if not any(obs_mask):
        obs_mask[0] = True
    rows, expected = [], {}
    for name, ob in zip(names, obs_mask):
        if not ob:
            rows.append(drow(name, 1.0, 1.0, 1.0, date_="2026-11-06"))     # 只有舊日 → 未觀測
            continue
        pick = rnd.choice(["zero", "neg0", "eps", "-eps", "big", "small", "normal"])
        f_ = {"zero": 0.0, "neg0": -0.0, "eps": EPS, "-eps": -EPS, "big": 1500.0 * rnd.choice([-1, 1]),
              "small": rnd.uniform(-1e-6, 1e-6), "normal": rnd.uniform(-80, 80)}[pick]
        rows.append(drow(name, f_, 0.0, 0.0))
        expected[name] = f_
    env.universe, env.members, env.rows = names, {}, rows
    f = env.write().fact()
    assert f.reason == "ok" and f.derived is not None
    d = f.derived
    exp_pos = sum(1 for v in expected.values() if v > EPS)
    exp_neg = sum(1 for v in expected.values() if v < -EPS)
    exp_flat = len(expected) - exp_pos - exp_neg
    assert (d.n_positive, d.n_negative, d.n_flat) == (exp_pos, exp_neg, exp_flat)
    assert d.n_unobserved == n - len(expected) and d.n_universe == n
    assert d.n_positive + d.n_negative + d.n_flat + d.n_unobserved == n == len(f.rows)
    assert d.total_net_yi == pytest.approx(math.fsum(expected.values()), abs=1e-9)
    assert [r.sector for r in f.rows] == sorted(names)
    assert f.coverage.n_observed == len(expected)


# ═══════════════════════════════════════════════════════════════════════
# 6. 契約形狀:無全市場 / 無 quadrant 等欄位;diagnostic 不是文案
# ═══════════════════════════════════════════════════════════════════════
_CONTRACT_CLASSES = (S.SectorFlowFact, S.SectorNetRow, S.SectorFlowCoverage, S.SectorFlowDerived,
                     S.SectorFlowBasis)
_FORBIDDEN_FIELD_PARTS = ("market", "全市場", "quadrant", "x_yi", "y_yi", "size_yi", "highlight",
                          "holding", "rank", "top", "bottom", "inflow", "outflow", "momentum")


def test_no_market_wide_or_forbidden_fields():
    for cls in _CONTRACT_CLASSES:
        for fld in dataclasses.fields(cls):
            low = fld.name.lower()
            assert not any(p in low for p in _FORBIDDEN_FIELD_PARTS), (cls.__name__, fld.name)


def test_no_market_wide_in_reason_caveat_codes(env):
    codes = list(S.REASON_STATE) + [getattr(S, n) for n in dir(S) if n.startswith("CAVEAT_")]
    for c in codes:
        assert "market" not in c.lower() and "全市場" not in c
    f = env.write().fact()
    blob = repr(f).lower()
    assert "market" not in blob and "全市場" not in blob and "quadrant" not in blob


def test_sign_vocabulary_is_neutral():
    assert {S.SIGN_POSITIVE, S.SIGN_NEGATIVE, S.SIGN_FLAT, S.SIGN_UNOBSERVED} == \
        {"positive", "negative", "flat", "unobserved"}


def test_fact_is_frozen(env):
    f = env.write().fact()
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.reason = "x"                                             # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════
# 7. 唯讀 / 零網路 / 不碰持股、UI(範圍守衛)
# ═══════════════════════════════════════════════════════════════════════
def test_zero_network_and_no_writes(env, monkeypatch):
    env.write()

    def boom(*a, **k):
        raise AssertionError("網路被呼叫")

    import requests
    import urllib.request
    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(requests.sessions.Session, "request", boom)
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    before = {p.name: p.stat().st_mtime_ns for p in env.tmp.iterdir()}
    f = env.fact()
    assert f.reason == "ok"
    assert {p.name: p.stat().st_mtime_ns for p in env.tmp.iterdir()} == before      # 沒寫任何檔


def test_holdings_and_gsheet_never_called(env, monkeypatch):
    import importlib

    def boom(*a, **k):
        raise AssertionError("持股 / gsheet / sector_flow_view 不得被呼叫")

    for modname, attrs in (("src.services.holdings_service", ("get_holdings",)),
                           ("src.services.sector_flow_service", ("get_sector_flow_view",)),
                           ("src.data.portfolio.gsheet_portfolio",
                            ("is_configured", "list_stock_watchlists", "load_stock_watchlist"))):
        mod = importlib.import_module(modname)
        for a in attrs:
            monkeypatch.setattr(mod, a, boom)
    assert env.write().fact().reason == "ok"


_BANNED_IMPORT_PREFIXES = ("streamlit", "src.ui", "src.ui2", "src.ui_v2", "src.services.ui2", "app",
                           "app_ui2", "requests", "urllib", "src.services.holdings_service",
                           "src.services.sector_flow_service", "src.data.portfolio", "src.data.proxy")


def _imports_of(path: Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "禁相對 import"
            out.append(node.module or "")
    return out


def test_service_ast_has_no_streamlit_ui_or_network_imports():
    mods = _imports_of(REPO / SERVICE_REL)
    assert mods, "AST 沒掃到任何 import(掃描失效)"
    for m in mods:
        for p in _BANNED_IMPORT_PREFIXES:
            assert not (m == p or m.startswith(p + ".")), f"禁止的 import: {m}"
    src_text = (REPO / SERVICE_REL).read_text(encoding="utf-8")
    used = {n.id for n in ast.walk(ast.parse(src_text)) if isinstance(n, ast.Name)} | \
           {n.attr for n in ast.walk(ast.parse(src_text)) if isinstance(n, ast.Attribute)}
    assert not used & {"get_sector_flow_view", "get_holdings", "highlight_sectors"}   # 程式碼層面不引用(docstring 不算)


def test_new_reader_functions_are_pure_reads():
    text = (REPO / "src/data/sector_flow/reader.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    fn = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in ("read_sector_daily_net_latest", "read_sector_flow_cron_coverage"):
        calls = {ast.unparse(c.func) for c in ast.walk(fn[name]) if isinstance(c, ast.Call)}
        assert not any(w in c for c in calls for w in ("write", "to_parquet", "requests", "urlopen",
                                                       "fetch", "dump", "mkdir", "unlink")), calls


def test_no_ui_or_vm_references_the_new_service():
    """範圍守衛:本批只落 L3 + 測試,不接 UI / VM / real_feed / app。"""
    needle = "sector_flow_fact_service"
    roots = [REPO / "src/ui", REPO / "src/ui2", REPO / "src/ui_v2", REPO / "src/services/ui2"]
    files = [p for r in roots if r.is_dir() for p in r.rglob("*.py")]
    files += list(REPO.glob("app*.py"))
    assert files, "沒掃到任何 UI 檔(掃描失效)"
    hits = [str(p.relative_to(REPO)) for p in files if needle in p.read_text(encoding="utf-8")]
    assert hits == [], hits


# ═══════════════════════════════════════════════════════════════════════
# 8. 真實 data_cache(一次;檔案不存在則 skip)
# ═══════════════════════════════════════════════════════════════════════
def test_real_data_cache_once():
    for p in (R.BUBBLE_PATH, R.META_PATH, R.DAILY_NET_PATH):
        if not p.exists():
            pytest.skip(f"{p.name} 不存在")
    last = json.loads(R.META_PATH.read_text(encoding="utf-8")).get("last_updated")
    today = datetime.strptime(last, "%Y-%m-%d").date() + pd.Timedelta(days=1).to_pytimedelta()
    f = S.get_sector_flow_fact(today=today)
    assert f.state is FieldState.OK and f.reason == "ok", (f.reason, f.diagnostic)
    d, cov = f.derived, f.coverage
    assert d is not None and f.completeness == "complete"
    assert d.n_positive + d.n_negative + d.n_flat + d.n_unobserved == d.n_universe == len(f.rows)
    assert [r.sector for r in f.rows] == sorted(r.sector for r in f.rows)
    if f.data_date == "2026-11-09":                                 # 凍結的當日快照;之後更新則只驗不變量
        assert (cov.n_universe, cov.n_observed, cov.n_unobserved) == (41, 38, 3)
        assert set(cov.unobserved_sectors) == {"化學生技醫療", "未分類", "電子工業"}
        assert d.total_net_yi == pytest.approx(-920.248, abs=5e-4)
        assert S.CAVEAT_SCOPE_INCLUDES_NON_COMMON_LABELS in f.caveats
