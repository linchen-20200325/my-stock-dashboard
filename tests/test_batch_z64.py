"""批 Z64 — freshness F4：L3 引擎輸入組裝＋規則引擎執行＋與舊引擎 golden 對帳（⛔ 不接線）。

守：
1. **Golden**：完整且新鮮的輸入（PMI 前月存在且恰為前一月、舊 UI session 前值＝parquet 前月）下，
   新路徑 `run_rule_engine` 的引擎原有鍵與舊 UI（`section_news_ai.py` 原文切片 exec）逐鍵逐值相同。
   ≥ 2000 組，含所有紅線觸發／不觸發的邊界。
2. **刻意差異**（逐條標明）：PMI 前月來源、過期不計分、PCR 逐欄往回找、bool／字串判缺。
3. `red_lines`：各種缺值／過期組合；Sahm 永遠 no_source。
4. Freshness 邊界端到端（VIX 第 3／4 個平日、台股休市日、月頻、休市表 None、跨年）。
5. 型別：數值序列 bool → MISSING；MA5 numpy bool → Python bool。
6. `load_engine_inputs_from_session`：L1 全部 mock（休市表成功／失敗、parquet 有／無），不連網。
7. 純度：同輸入同結果；不讀 `date.today()`／`datetime.now()`（AST）。
8. 休市表跨年查證：L1 `taipei_year` 只是快取鍵，取不到去年的表。
"""
from __future__ import annotations

import ast
import copy
import json
import random
import textwrap
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shared.dated_value import DatedValue
from shared.freshness_policy import FRESHNESS_POLICY, FreshnessStatus
from shared.macro_provenance import m1b_m2_for_scoring
from shared.pcr_scale import normalize_pcr_to_ratio
from shared.trading_days import CalendarSets
from src.compute.macro import dated_inputs as DI
from src.services import macro_engine_inputs as M
from src.services.macro_state_locker import (
    MACRO_VETO_FUTURES_NET_SHORT_LOTS,
    MACRO_VETO_PMI_CONTRACTION_LEVEL,
    _ENGINE_NUMERIC_INPUTS,
    calculate_system_state,
)

REPO = Path(__file__).resolve().parents[1]
UTC = timezone.utc
TPE = timezone(timedelta(hours=8))

# 2026-10-14（週三）台北 10:00
NOW = datetime(2026, 10, 14, 2, 0, tzinfo=UTC)
TODAY = date(2026, 10, 14)


# ══════════════════════════════════════════════════════════════════════════
# 0. 舊 UI 組裝原文切片（`section_news_ai.py`，原文未改一字；同 Z62 作法）
# ══════════════════════════════════════════════════════════════════════════
_OLD_REL = "src/ui/tabs/macro/section_news_ai.py"
_OLD_START = "_vix_d  = _macro_info.get('vix') or {}"
_OLD_END = "_system_state = calculate_system_state(_macro_numbers)"


def _slice(rel: str, start: str, end: str) -> str:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    b = [i for i, ln in enumerate(lines) if start in ln]
    e = [i for i, ln in enumerate(lines) if end in ln]
    assert len(b) == 1 and len(e) == 1, (rel, start, end, b, e)
    return textwrap.dedent("\n".join(lines[b[0]:e[0] + 1]))


_OLD_SRC = _slice(_OLD_REL, _OLD_START, _OLD_END)
_OLD_CODE = compile(_OLD_SRC, "<section_news_ai 組裝段>", "exec")


class _Sess:
    def __init__(self, d):
        self.session_state = d


def _old_run(macro_info, *, bias_info, li, mkt, m1b, prev_pmi_session):
    """舊 UI 組裝段原文 exec → (舊 `_macro_numbers`, 舊 `_system_state`)。"""
    from src.ui.tabs.macro.section_long import _finite_yoy
    from src.ui.tabs.macro.section_news_ai import _finite_or_none

    sess = {"bias_info": bias_info, "li_latest": li, "mkt_info": mkt, "m1b_m2_info": m1b}
    if prev_pmi_session is not None:
        sess["_s10_prev_pmi_value"] = prev_pmi_session
    ns = {
        "_macro_info": macro_info, "st": _Sess(sess),
        "_normalize_pcr": normalize_pcr_to_ratio, "_finite_or_none": _finite_or_none,
        "_finite_yoy": _finite_yoy, "m1b_m2_for_scoring": m1b_m2_for_scoring,
        "calculate_system_state": calculate_system_state,
    }
    exec(_OLD_CODE, ns)
    return ns["_macro_numbers"], ns["_system_state"]


def _fixture_calendar() -> CalendarSets:
    from src.data.stock import twse_holiday_fetcher as hf
    payload = json.loads((REPO / "tests/fixtures/twse_holiday_schedule_115_synthetic.json")
                         .read_text(encoding="utf-8"))
    return hf.parse_holiday_schedule(payload, fetched_at=datetime(2026, 10, 2, tzinfo=UTC)).as_sets()


CAL = _fixture_calendar()   # 2026 涵蓋；10/09（五）國慶補假休市


def _hist(rows):
    return pd.DataFrame([{"date": d, "pmi": v, "source": "CIER"} for d, v in rows])


def _li(rows):
    return pd.DataFrame(rows)


def _inputs(*, vix=17.3, vix_date="2026-10-13", pmi=51.2, pmi_month="2026-09-01",
            pmi_prev=50.4, prev_month=date(2026, 8, 1), m1b=3.2, m2=5.1, m_month="2026-08",
            bias=12.3, bias_date="2026-10-13", pcr=126.8, fut=-21000.0, li_date="20261013",
            below=True, ma5_date="2026-10-13"):
    """一組輸入（預設完整且新鮮）。回傳 build_engine_inputs 的 kwargs（不含 now／calendar）。"""
    return dict(
        macro_info={"vix": {"current": vix, "date": vix_date},
                    "ism_pmi": {"value": pmi, "date": pmi_month}},
        bias_info={"bias_240": bias, "as_of": bias_date},
        m1b_m2_info={"m1b_yoy": m1b, "m2_yoy": m2, "data_month": m_month, "source": "CBC-tier1"},
        li_latest=_li([{"_date": "20261007", "選PCR": 100.0, "外資大小": -1000.0},
                       {"_date": li_date, "選PCR": pcr, "外資大小": fut}]),
        mkt_info={"index_below_ma5": below, "index_as_of": ma5_date,
                  "ma5": 22000.0, "index_price": 21900.0 if below else 22100.0},
        pmi_history=_hist([(date(2026, 6, 1), 49.0), (date(2026, 7, 1), 49.5),
                           (prev_month, pmi_prev)]
                          if prev_month is not None else [(date(2026, 6, 1), 49.0)]),
    )


def _build(kw, *, now=NOW, calendar=CAL, calendar_error=None):
    return M.build_engine_inputs(**kw, now=now, calendar=calendar, calendar_error=calendar_error)


def _old_for(kw, prev_pmi_session):
    return _old_run(kw["macro_info"], bias_info=kw["bias_info"], li=kw["li_latest"],
                    mkt=kw["mkt_info"], m1b=kw["m1b_m2_info"], prev_pmi_session=prev_pmi_session)


def _assert_engine_keys_equal(old: dict, new: dict, ctx) -> None:
    extra = set(new) - set(old)
    assert extra == set(M.EXTRA_RESULT_KEYS), (ctx, extra)
    for k, v in old.items():
        assert k in new, (ctx, k)
        assert type(new[k]) is type(v) and new[k] == v, (ctx, k, v, new[k])


# ══════════════════════════════════════════════════════════════════════════
# 1. Golden：完整新鮮資料 → 引擎原有鍵逐鍵逐值相同
# ══════════════════════════════════════════════════════════════════════════
_VIX_EDGES = [10.0, 14.0, 14.01, 21.99, 22.0, 25.0, 25.01, 27.99, 28.0, 34.99, 35.0, 45.0]
_PMI_EDGES = [44.0, 45.99, 46.0, 47.99, 48.0, 48.01, 49.99, 50.0, 52.0, 52.01, 55.0, 55.01, 58.0]
_BIAS_EDGES = [-20.0, -10.01, -10.0, 0.0, 15.0, 15.01, 25.0]
_PCR_EDGES = [50.0, 69.99, 70.0, 100.0, 150.0, 150.01, 200.0]   # 百分比刻度（li 原值）
_FUT_EDGES = [MACRO_VETO_FUTURES_NET_SHORT_LOTS - 0.01, MACRO_VETO_FUTURES_NET_SHORT_LOTS,
              MACRO_VETO_FUTURES_NET_SHORT_LOTS + 0.01, -60000.0, -20000.0, 0.0, 5000.0]
_MSPREAD = [(5.0, 1.0), (3.0, 0.0), (3.01, 0.0), (1.0, 1.0), (1.0, 4.0), (0.0, 3.01), (2.0, 1.5)]
_VIX_DATES = ["2026-10-09", "2026-10-12", "2026-10-13", "2026-10-14"]   # 平日落後 ≤ 3
_TW_DATES = ["2026-10-08", "2026-10-12", "2026-10-13", "2026-10-14"]    # 10/09 休市 ⇒ 10/08 落後 3
_GOLDEN_N = 2400


def _pick(rng, edges, lo, hi):
    return rng.choice(edges) if rng.random() < 0.5 else round(rng.uniform(lo, hi), 2)


def _golden_cases():
    rng = random.Random(20261014)
    for i in range(_GOLDEN_N):
        m1b, m2 = (rng.choice(_MSPREAD) if rng.random() < 0.5
                   else (round(rng.uniform(-5, 15), 2), round(rng.uniform(-5, 15), 2)))
        li_d = rng.choice(_TW_DATES).replace("-", "")
        yield i, _inputs(
            vix=_pick(rng, _VIX_EDGES, 9.0, 50.0), vix_date=rng.choice(_VIX_DATES),
            pmi=_pick(rng, _PMI_EDGES, 40.0, 60.0), pmi_prev=_pick(rng, _PMI_EDGES, 40.0, 60.0),
            m1b=m1b, m2=m2, m_month=rng.choice(["2026-08", "2026-09"]),
            bias=_pick(rng, _BIAS_EDGES, -25.0, 35.0), bias_date=rng.choice(_TW_DATES),
            pcr=_pick(rng, _PCR_EDGES, 40.0, 220.0), fut=_pick(rng, _FUT_EDGES, -70000.0, 20000.0),
            li_date=li_d, below=rng.random() < 0.5, ma5_date=rng.choice(_TW_DATES))


class TestGolden:
    def test_slice_shape(self):
        assert "_macro_numbers = {" in _OLD_SRC and "'PMI_Prev_Month':" in _OLD_SRC
        assert "_s10_prev_pmi_value" in _OLD_SRC

    def test_golden_full_fresh_identical(self):
        seen = {"pmi_veto": 0, "no_pmi_veto": 0, "fut_veto": 0, "no_fut_veto": 0,
                "bias_hot": 0, "below_true": 0, "below_false": 0,
                "fut_lt_edge_not_below": 0, "pmi_under_prev_over": 0}
        vix_bands = set()
        n = 0
        for i, kw in _golden_cases():
            bundle = _build(kw)
            # 前提：完整且新鮮
            assert bundle.not_evaluated == (), (i, bundle.not_evaluated,
                                                {k: bundle.assessed[k].verdict.reason
                                                 for k in bundle.not_evaluated})
            assert bundle.red_lines[M.RL_PMI].status == "evaluable"
            assert bundle.red_lines[M.RL_FUTURES].status == "evaluable"
            assert bundle.red_lines[M.RL_SAHM].status == "no_source"
            prev = kw["pmi_history"]["pmi"].iloc[-1]
            old_nums, old = _old_for(kw, prev_pmi_session=prev)
            new = M.run_rule_engine(bundle)
            _assert_engine_keys_equal(old, new, i)
            # 送給引擎的每一個引擎讀的數值輸入，有效值也相同（PMI 前月同值）
            for k in _ENGINE_NUMERIC_INPUTS:
                assert float(old_nums[k]) == float(bundle.macro_numbers[k]), (i, k)
            assert bool(old_nums["Index_Below_MA5"]) == bundle.macro_numbers["Index_Below_MA5"]
            n += 1
            ph = old["Macro_Phase"]
            seen["pmi_veto" if "PMI連兩月" in ph else "no_pmi_veto"] += 1
            seen["fut_veto" if "期貨淨空" in ph else "no_fut_veto"] += 1
            seen["bias_hot"] += "均線過熱" in ph
            seen["below_true" if kw["mkt_info"]["index_below_ma5"] else "below_false"] += 1
            fut = kw["li_latest"]["外資大小"].iloc[-1]
            if fut < MACRO_VETO_FUTURES_NET_SHORT_LOTS and not kw["mkt_info"]["index_below_ma5"]:
                seen["fut_lt_edge_not_below"] += 1
            p, pp = kw["macro_info"]["ism_pmi"]["value"], prev
            if p < MACRO_VETO_PMI_CONTRACTION_LEVEL <= pp:
                seen["pmi_under_prev_over"] += 1
            v = kw["macro_info"]["vix"]["current"]
            vix_bands.add(0 if v <= 14 else 1 if v < 22 else 2 if v < 28 else 3 if v < 35 else 4)
        assert n >= 2000
        assert all(c > 20 for c in seen.values()), seen
        assert vix_bands == {0, 1, 2, 3, 4}

    @pytest.mark.parametrize("pmi,prev", [(47.99, 47.99), (48.0, 47.99), (47.99, 48.0),
                                          (48.0, 48.0), (45.0, 46.0)])
    @pytest.mark.parametrize("fut", _FUT_EDGES[:3])
    @pytest.mark.parametrize("below", [True, False])
    def test_golden_red_line_edges(self, pmi, prev, fut, below):
        kw = _inputs(pmi=pmi, pmi_prev=prev, fut=fut, below=below)
        _, old = _old_for(kw, prev_pmi_session=prev)
        new = M.run_rule_engine(_build(kw))
        _assert_engine_keys_equal(old, new, (pmi, prev, fut, below))
        assert ("PMI連兩月" in new["Macro_Phase"]) == (pmi < 48 and prev < 48)
        assert ("期貨淨空" in new["Macro_Phase"]) == (fut < -35000 and below)

    def test_65_score_rounds_to_60(self):
        """客戶：65 分 → 60%（Python round 銀行家捨入，引擎原樣）。VIX ≤ 14 (+10) − PMI < 50 (−10)
        ＋ spread 0~3 (+5) ＝ 65。"""
        kw = _inputs(vix=14.0, pmi=49.0, pmi_prev=49.5, m1b=2.0, m2=1.0, bias=0.0, pcr=100.0,
                     fut=0.0)
        new = M.run_rule_engine(_build(kw))
        assert new["exposure_limit_pct"] == 60


# ══════════════════════════════════════════════════════════════════════════
# 2. 刻意差異（逐條標明；不是 bug）
# ══════════════════════════════════════════════════════════════════════════
class TestIntendedDifferences:
    def test_d1_pmi_prev_from_parquet_not_session(self):
        """差異 1：舊 UI 用 session 前值（上次按按鈕的當期值）；新路徑用 parquet 真前一資料月。"""
        kw = _inputs(pmi=47.0, pmi_prev=47.5)
        _, old = _old_for(kw, prev_pmi_session=49.0)       # session 前值 ≠ parquet
        new = M.run_rule_engine(_build(kw))
        assert "PMI連兩月" not in old["Macro_Phase"]
        assert "PMI連兩月收縮(47.5→47.0)" in new["Macro_Phase"]
        assert new["exposure_limit_pct"] <= 40

    def test_d1_first_press_session_none(self):
        kw = _inputs(pmi=47.0, pmi_prev=47.5)
        old_nums, old = _old_for(kw, prev_pmi_session=None)
        assert old_nums["PMI_Prev_Month"] is None and "PMI_Prev_Month" in old["missing_inputs"]
        new = M.run_rule_engine(_build(kw))
        assert "missing_inputs" not in new and "PMI連兩月" in new["Macro_Phase"]

    def test_d2_stale_input_not_scored(self):
        """差異 2：VIX 落後 4 個平日 → 新路徑不計分；舊路徑照算。"""
        kw = _inputs(vix=40.0, vix_date="2026-10-08")
        _, old = _old_for(kw, prev_pmi_session=50.4)
        b = _build(kw)
        new = M.run_rule_engine(b)
        assert "VIX高波動(40.0)" in old["Macro_Phase"]
        assert b.macro_numbers["VIX_Index"] is None and "VIX_Index" in b.not_evaluated
        assert b.assessed["VIX_Index"].verdict.status == FreshnessStatus.STALE
        assert new["missing_inputs"] == ["VIX_Index"] and "VIX" not in new["Macro_Phase"]
        assert new["exposure_limit_pct"] > old["exposure_limit_pct"]   # 舊路徑多扣 30（以過期值計分）

    def test_d3_pcr_walk_back(self):
        """差異 3：最後一列 PCR 是 '-' → 舊路徑 PCR 缺；新路徑往回取前一列（該列日期判新鮮度）。"""
        kw = _inputs()
        kw["li_latest"] = _li([{"_date": "20261012", "選PCR": 160.0, "外資大小": -1000.0},
                               {"_date": "20261013", "選PCR": "-", "外資大小": -2000.0}])
        old_nums, old = _old_for(kw, prev_pmi_session=50.4)
        b = _build(kw)
        assert old_nums["PCR"] is None
        assert b.macro_numbers["PCR"] == 1.6 and b.input_asof["PCR"] == "2026-10-12"
        assert "PCR" in old["missing_inputs"] and "missing_inputs" not in M.run_rule_engine(b)

    @pytest.mark.parametrize("key,patch", [
        ("VIX_Index", lambda kw: kw["macro_info"]["vix"].update(current="40.5")),
        ("VIX_Index", lambda kw: kw["macro_info"]["vix"].update(current=True)),
        ("Futures_Net_Short", lambda kw: kw.update(li_latest=_li([
            {"_date": "20261012", "選PCR": 100.0, "外資大小": -1000.0},
            {"_date": "20261013", "選PCR": 126.8, "外資大小": True}]))),
    ])
    def test_d4_bool_or_string_missing(self, key, patch):
        """差異 4：數值欄是字串／bool → 舊路徑引擎 `float()` 照算；新路徑判缺。"""
        kw = _inputs()
        patch(kw)
        old_nums, _ = _old_for(kw, prev_pmi_session=50.4)
        assert old_nums[key] is not None
        b = _build(kw)
        assert b.macro_numbers[key] is None and key in b.not_evaluated
        assert b.assessed[key].verdict.status == FreshnessStatus.MISSING

    def test_d5_unread_keys_not_sent(self):
        b = _build(_inputs())
        assert set(b.macro_numbers) == set(M.ENGINE_INPUT_KEYS) | {M.KEY_SAHM}
        assert b.macro_numbers[M.KEY_SAHM] is None


# ══════════════════════════════════════════════════════════════════════════
# 3. red_lines
# ══════════════════════════════════════════════════════════════════════════
class TestRedLines:
    def test_keys_and_inputs(self):
        b = _build(_inputs())
        assert set(b.red_lines) == {M.RL_PMI, M.RL_FUTURES, M.RL_SAHM}
        assert b.red_lines[M.RL_PMI].inputs == ("ISM_PMI_or_OECD_CLI", "PMI_Prev_Month")
        assert b.red_lines[M.RL_FUTURES].inputs == ("Futures_Net_Short", "Index_Below_MA5")

    @pytest.mark.parametrize("kw_patch", [
        {}, {"vix": None}, {"pmi": None}, {"fut": None}, {"below": None}, {"prev_month": None},
        {"vix_date": "2026-09-01"},
    ])
    def test_sahm_always_no_source(self, kw_patch):
        b = _build(_inputs(**kw_patch))
        rl = b.red_lines[M.RL_SAHM]
        assert rl.status == "no_source" and rl.reason == M.SAHM_NO_SOURCE_REASON
        assert "不代表紅線已通過" in rl.reason
        assert b.macro_numbers["Sahm_Rule_Triggered"] is None
        assert "薩姆" not in M.run_rule_engine(b)["Macro_Phase"]

    def test_pmi_prev_missing_undetermined_and_no_veto(self):
        b = _build(_inputs(pmi=45.0, prev_month=None))
        rl = b.red_lines[M.RL_PMI]
        assert rl.status == "undetermined" and "PMI_Prev_Month" in rl.reason and "未取得" in rl.reason
        assert "ISM_PMI_or_OECD_CLI" not in rl.reason
        r = M.run_rule_engine(b)
        assert "PMI連兩月" not in r["Macro_Phase"] and "PMI收縮(45.0)" in r["Macro_Phase"]
        assert "PMI_Prev_Month" in r["missing_inputs"]

    def test_pmi_prev_wrong_month_undetermined(self):
        b = _build(_inputs(pmi=45.0, pmi_prev=44.0, prev_month=date(2026, 7, 1)))
        assert b.red_lines[M.RL_PMI].status == "undetermined"
        assert b.macro_numbers["PMI_Prev_Month"] is None

    def test_pmi_stale_makes_prev_undetermined(self):
        b = _build(_inputs(pmi=45.0, pmi_month="2026-08-01", pmi_prev=44.0,
                           prev_month=date(2026, 7, 1)))
        assert b.assessed["ISM_PMI_or_OECD_CLI"].verdict.status == FreshnessStatus.STALE
        assert b.assessed["PMI_Prev_Month"].verdict.status == FreshnessStatus.UNDETERMINED
        rl = b.red_lines[M.RL_PMI]
        assert rl.status == "undetermined" and "已過期" in rl.reason and "無法判定" in rl.reason
        assert "PMI" not in M.run_rule_engine(b)["Macro_Phase"]

    @pytest.mark.parametrize("kw_patch,bad", [
        ({"fut": None}, "Futures_Net_Short"),
        ({"fut": float("nan")}, "Futures_Net_Short"),
        ({"li_date": "20261001"}, "Futures_Net_Short"),
        ({"below": None}, "Index_Below_MA5"),
        ({"ma5_date": "2026-10-01"}, "Index_Below_MA5"),
        ({"ma5_date": None}, "Index_Below_MA5"),
    ])
    def test_futures_ma5_undetermined(self, kw_patch, bad):
        kw = _inputs(**{"fut": -50000.0, "below": True, **kw_patch})
        b = _build(kw)
        rl = b.red_lines[M.RL_FUTURES]
        assert rl.status == "undetermined" and bad in rl.reason
        assert "期貨淨空" not in M.run_rule_engine(b)["Macro_Phase"]

    def test_ma5_stale_sends_none_not_true(self):
        b = _build(_inputs(fut=-50000.0, below=True, ma5_date="2026-10-01"))
        assert b.assessed["Index_Below_MA5"].verdict.status == FreshnessStatus.STALE
        assert b.macro_numbers["Index_Below_MA5"] is None
        assert "Index_Below_MA5" in b.not_evaluated

    def test_evaluable_not_triggered_is_not_called_passed(self):
        b = _build(_inputs(fut=0.0, below=False))
        rl = b.red_lines[M.RL_FUTURES]
        assert rl.status == "evaluable" and "由規則引擎判定" in rl.reason

    def test_run_rule_engine_json_serializable(self):
        r = M.run_rule_engine(_build(_inputs(vix=None, prev_month=None)))
        s = json.dumps(r, ensure_ascii=False)
        back = json.loads(s)
        assert back["red_lines"]["sahm"]["status"] == "no_source"
        assert isinstance(r["not_evaluated"], list) and isinstance(r["input_asof"], dict)
        assert r["not_evaluated"] == ["VIX_Index", "PMI_Prev_Month"]


# ══════════════════════════════════════════════════════════════════════════
# 4. Freshness 邊界端到端
# ══════════════════════════════════════════════════════════════════════════
class TestFreshnessEndToEnd:
    @pytest.mark.parametrize("vix_date,fresh", [("2026-10-09", True), ("2026-10-08", False),
                                                ("2026-10-14", True), ("2026-10-15", False)])
    def test_vix_third_vs_fourth_weekday(self, vix_date, fresh):
        b = _build(_inputs(vix=30.0, vix_date=vix_date))
        assert (b.macro_numbers["VIX_Index"] == 30.0) is fresh
        assert ("VIX_Index" in b.not_evaluated) is (not fresh)

    @pytest.mark.parametrize("bias_date,status", [
        ("2026-10-08", FreshnessStatus.FRESH),     # 10/09 休市 ⇒ 10/12、13、14 共 3
        ("2026-10-07", FreshnessStatus.STALE),     # 10/08、12、13、14 共 4
        ("2026-10-05", FreshnessStatus.STALE),
    ])
    def test_tw_daily_holiday(self, bias_date, status):
        b = _build(_inputs(bias_date=bias_date))
        assert b.assessed["BIAS240_pct"].verdict.status == status
        assert (b.macro_numbers["BIAS240_pct"] is not None) is (status == FreshnessStatus.FRESH)

    @pytest.mark.parametrize("bias_date,status", [
        ("2026-10-13", FreshnessStatus.FRESH),          # 上界 1 ≤ 3
        ("2026-10-09", FreshnessStatus.UNDETERMINED),   # 上界 5 > 3、下界 0
        ("2026-09-01", FreshnessStatus.UNDETERMINED),   # cal=None 下界恆 0 ⇒ 判不出 STALE
    ])
    def test_calendar_none_interval(self, bias_date, status):
        b = _build(_inputs(bias_date=bias_date), calendar=None)
        assert b.assessed["BIAS240_pct"].verdict.status == status
        assert b.calendar_error == M.CALENDAR_NOT_PROVIDED
        assert b.assessed["VIX_Index"].verdict.status == FreshnessStatus.FRESH  # 平日日曆不需休市表

    def test_calendar_error_passthrough_and_conflict(self):
        b = _build(_inputs(), calendar=None, calendar_error="休市表取不到：X")
        assert b.calendar_error == "休市表取不到：X"
        assert _build(_inputs()).calendar_error is None
        with pytest.raises(ValueError):
            _build(_inputs(), calendar=CAL, calendar_error="x")

    @pytest.mark.parametrize("pmi_month,m_month,pmi_ok,m_ok", [
        ("2026-09-01", "2026-08", True, True),
        ("2026-08-01", "2026-07", False, False),
        ("2026-10-01", "2026-10", False, False),   # 當月未結束 ⇒ UNDETERMINED
    ])
    def test_monthly(self, pmi_month, m_month, pmi_ok, m_ok):
        b = _build(_inputs(pmi_month=pmi_month, m_month=m_month))
        assert (b.macro_numbers["ISM_PMI_or_OECD_CLI"] is not None) is pmi_ok
        assert (b.macro_numbers["M1B_YoY_pct"] is not None) is m_ok
        assert (b.macro_numbers["M2_YoY_pct"] is not None) is m_ok

    def test_cross_year_uncovered_previous_year(self):
        """1 月初、休市表只涵蓋今年：去年 12 月的資料日依區間法判。"""
        cal27 = CalendarSets(closed=frozenset({date(2027, 1, 1)}), trading=frozenset(),
                             unclassified=frozenset(), covered_years=frozenset({2027}))
        now = datetime(2027, 1, 5, 2, tzinfo=UTC)   # 台北 2027-01-05（二）
        kw = _inputs(vix_date="2026-12-31", bias_date="2026-12-31",
                     pmi_month="2026-11-01", prev_month=date(2026, 10, 1), m_month="2026-11")
        b = _build(kw, now=now, calendar=cal27)
        assert b.today == date(2027, 1, 5)
        assert b.assessed["BIAS240_pct"].verdict.status == FreshnessStatus.FRESH   # 01/04、01/05
        kw2 = _inputs(bias_date="2026-12-29")
        b2 = _build(kw2, now=now, calendar=cal27)
        v = b2.assessed["BIAS240_pct"].verdict
        assert v.status == FreshnessStatus.UNDETERMINED and "未涵蓋 2026" in v.reason
        assert "BIAS240_pct" in b2.not_evaluated

    def test_today_is_taipei_date(self):
        now = datetime(2026, 10, 13, 17, 0, tzinfo=UTC)   # 台北 10/14 01:00
        b = _build(_inputs(vix_date="2026-10-08"), now=now)
        assert b.today == date(2026, 10, 14)
        assert b.macro_numbers["VIX_Index"] is None   # 以 UTC 日期（10/13）算會是 3 個平日 ⇒ 計分
        b2 = _build(_inputs(vix_date="2026-10-08"), now=now.astimezone(TPE))
        assert b2.today == date(2026, 10, 14)

    def test_naive_now_raises(self):
        with pytest.raises(ValueError):
            _build(_inputs(), now=datetime(2026, 10, 14, 10))
        with pytest.raises(TypeError):
            _build(_inputs(), now=date(2026, 10, 14))


# ══════════════════════════════════════════════════════════════════════════
# 5. 型別
# ══════════════════════════════════════════════════════════════════════════
class TestTypes:
    @pytest.mark.parametrize("bad", [True, False, np.bool_(True), np.bool_(False)])
    @pytest.mark.parametrize("key", ["VIX_Index", "ISM_PMI_or_OECD_CLI", "BIAS240_pct"])
    def test_session_numeric_bool_missing(self, key, bad):
        kw = _inputs()
        if key == "VIX_Index":
            kw["macro_info"]["vix"]["current"] = bad
        elif key == "ISM_PMI_or_OECD_CLI":
            kw["macro_info"]["ism_pmi"]["value"] = bad
        else:
            kw["bias_info"]["bias_240"] = bad
        b = _build(kw)
        av = b.assessed[key]
        assert av.verdict.status == FreshnessStatus.MISSING and "bool" in av.verdict.reason
        assert b.macro_numbers[key] is None and key in b.not_evaluated

    @pytest.mark.parametrize("bad", [True, np.bool_(False)])
    @pytest.mark.parametrize("which", ["m1b_yoy", "m2_yoy"])
    def test_m1b_m2_bool_both_missing(self, which, bad):
        kw = _inputs()
        kw["m1b_m2_info"][which] = bad
        b = _build(kw)
        for k in ("M1B_YoY_pct", "M2_YoY_pct"):
            assert b.macro_numbers[k] is None
            assert "bool" in b.assessed[k].verdict.reason

    @pytest.mark.parametrize("bad", [True, np.bool_(True)])
    @pytest.mark.parametrize("col,key", [("選PCR", "PCR"), ("外資大小", "Futures_Net_Short")])
    def test_li_bool_cell_missing_not_walk_back(self, col, key, bad):
        kw = _inputs()
        rows = [{"_date": "20261012", "選PCR": 100.0, "外資大小": -1000.0},
                {"_date": "20261013", "選PCR": 126.8, "外資大小": -2000.0}]
        rows[-1][col] = bad
        kw["li_latest"] = _li(rows)
        b = _build(kw)
        av = b.assessed[key]
        assert av.verdict.status == FreshnessStatus.MISSING and "bool" in av.verdict.reason
        assert b.macro_numbers[key] is None

    def test_pmi_prev_bool_missing(self):
        kw = _inputs()
        kw["pmi_history"] = pd.DataFrame({"date": [date(2026, 7, 1), date(2026, 8, 1)],
                                          "pmi": [True, True]})
        b = _build(kw)
        assert b.macro_numbers["PMI_Prev_Month"] is None
        assert "bool" in b.assessed["PMI_Prev_Month"].verdict.reason
        assert b.red_lines[M.RL_PMI].status == "undetermined"

    def test_numeric_bool_after_extract_fallback(self, monkeypatch):
        """兜底：抽取器回 numpy bool（未來改動）→ 本層仍判缺。"""
        monkeypatch.setattr(M._di, "extract_vix", lambda mi: {
            "VIX_Index": DatedValue(np.bool_(True), "VIX_Index", "t", as_of=date(2026, 10, 13))})
        b = _build(_inputs())
        assert b.macro_numbers["VIX_Index"] is None
        assert "bool" in b.assessed["VIX_Index"].verdict.reason

    @pytest.mark.parametrize("raw,expect", [(np.bool_(True), True), (np.bool_(False), False),
                                            (True, True)])
    def test_ma5_numpy_bool_converted(self, raw, expect):
        kw = _inputs()
        kw["mkt_info"]["index_below_ma5"] = raw
        b = _build(kw)
        v = b.macro_numbers["Index_Below_MA5"]
        assert type(v) is bool and v is expect

    def test_ma5_non_bool_after_extract_missing(self, monkeypatch):
        monkeypatch.setattr(M._di, "extract_ma5", lambda mi: {
            "Index_Below_MA5": DatedValue(1, "Index_Below_MA5", "t", as_of=date(2026, 10, 13))})
        b = _build(_inputs())
        assert b.macro_numbers["Index_Below_MA5"] is None
        assert b.red_lines[M.RL_FUTURES].status == "undetermined"

    def test_ma5_numpy_bool_after_extract_converted(self, monkeypatch):
        monkeypatch.setattr(M._di, "extract_ma5", lambda mi: {
            "Index_Below_MA5": DatedValue(np.bool_(True), "Index_Below_MA5", "t",
                                             as_of=date(2026, 10, 13))})
        v = _build(_inputs()).macro_numbers["Index_Below_MA5"]
        assert type(v) is bool and v is True


# ══════════════════════════════════════════════════════════════════════════
# 6. load_engine_inputs_from_session（L1 全部 mock，不連網）
# ══════════════════════════════════════════════════════════════════════════
def _session_from(kw):
    return {"macro_info": kw["macro_info"], "bias_info": kw["bias_info"],
            "m1b_m2_info": kw["m1b_m2_info"], "li_latest": kw["li_latest"],
            "mkt_info": kw["mkt_info"], "unrelated": 1}


class TestLoadFromSession:
    def _hf_cal(self):
        from src.data.stock import twse_holiday_fetcher as hf
        payload = json.loads((REPO / "tests/fixtures/twse_holiday_schedule_115_synthetic.json")
                             .read_text(encoding="utf-8"))
        return hf.parse_holiday_schedule(payload, fetched_at=datetime(2026, 10, 2, tzinfo=UTC))

    def test_calendar_ok_parquet_ok(self, monkeypatch):
        kw = _inputs()
        calls = []
        cal = self._hf_cal()

        def fake_cal(*, taipei_year):
            calls.append(taipei_year)
            return cal

        monkeypatch.setattr(M._hf, "fetch_twse_holiday_calendar", fake_cal)
        monkeypatch.setattr(M._mcr, "load_tw_pmi_history", lambda: kw["pmi_history"])
        sess = _session_from(kw)
        snap = copy.deepcopy({k: v for k, v in sess.items() if k != "li_latest"})
        li_snap = sess["li_latest"].copy()
        b = M.load_engine_inputs_from_session(sess, now=NOW)
        assert calls == [2026]
        assert b.calendar_error is None and b.not_evaluated == ()
        direct = _build(kw)
        assert b.macro_numbers == direct.macro_numbers and b.red_lines == direct.red_lines
        # 唯讀：session 沒被寫
        assert {k: v for k, v in sess.items() if k != "li_latest"} == snap
        pd.testing.assert_frame_equal(sess["li_latest"], li_snap)
        assert set(sess) == set(snap) | {"li_latest"}

    def test_calendar_fail_parquet_missing(self, monkeypatch):
        from src.data.stock import twse_holiday_fetcher as hf
        kw = _inputs(bias_date="2026-10-09")

        def boom(*, taipei_year):
            raise hf.HolidayCalendarUnavailable("TWSE 無回應（測試）")

        monkeypatch.setattr(M._hf, "fetch_twse_holiday_calendar", boom)
        monkeypatch.setattr(M._mcr, "load_tw_pmi_history", lambda: None)
        b = M.load_engine_inputs_from_session(_session_from(kw), now=NOW)
        assert b.calendar_error and "TWSE 無回應（測試）" in b.calendar_error
        assert b.assessed["BIAS240_pct"].verdict.status == FreshnessStatus.UNDETERMINED
        assert b.macro_numbers["PMI_Prev_Month"] is None
        assert "讀不到" in b.assessed["PMI_Prev_Month"].verdict.reason
        assert b.red_lines[M.RL_PMI].status == "undetermined"

    def test_parquet_real_loader_via_tmp(self, monkeypatch, tmp_path):
        """L1 原函式（讀 tmp 檔）→ 前月取到。"""
        kw = _inputs(pmi_prev=47.2)
        kw["pmi_history"].to_parquet(tmp_path / "tw_pmi.parquet")
        real = M._mcr.load_tw_pmi_history
        monkeypatch.setattr(M._mcr, "load_tw_pmi_history", lambda: real(tmp_path))
        monkeypatch.setattr(M._hf, "fetch_twse_holiday_calendar",
                            lambda *, taipei_year: self._hf_cal())
        b = M.load_engine_inputs_from_session(_session_from(kw), now=NOW)
        assert b.macro_numbers["PMI_Prev_Month"] == 47.2

    def test_empty_session(self, monkeypatch):
        monkeypatch.setattr(M._hf, "fetch_twse_holiday_calendar",
                            lambda *, taipei_year: self._hf_cal())
        monkeypatch.setattr(M._mcr, "load_tw_pmi_history", lambda: None)
        b = M.load_engine_inputs_from_session({}, now=NOW)
        assert set(b.not_evaluated) == set(M.ENGINE_INPUT_KEYS)
        r = M.run_rule_engine(b)
        assert r["Macro_Phase"] == "系統異常"   # 引擎既有全缺 fail-safe

    def test_naive_now(self, monkeypatch):
        monkeypatch.setattr(M._hf, "fetch_twse_holiday_calendar",
                            lambda *, taipei_year: pytest.fail("不應呼叫"))
        with pytest.raises(ValueError):
            M.load_engine_inputs_from_session({}, now=datetime(2026, 10, 14))


# ══════════════════════════════════════════════════════════════════════════
# 7. 純度／一致性／不覆寫
# ══════════════════════════════════════════════════════════════════════════
class TestPurity:
    def test_stable(self):
        a, b = _build(_inputs()), _build(_inputs())
        assert a.macro_numbers == b.macro_numbers and a.red_lines == b.red_lines
        assert dict(a.input_asof) == dict(b.input_asof) and a.not_evaluated == b.not_evaluated

    def test_no_clock_reads_ast(self):
        tree = ast.parse((REPO / "src/services/macro_engine_inputs.py").read_text(encoding="utf-8"))
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in ("today", "now", "utcnow", "time"):
                bad.append((node.lineno, node.attr))
        assert not bad, bad

    def test_no_l4_l5_imports(self):
        tree = ast.parse((REPO / "src/services/macro_engine_inputs.py").read_text(encoding="utf-8"))
        mods = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        mods += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not [m for m in mods if m and (m.startswith("src.ui") or m == "app"
                                              or m.startswith("streamlit"))], mods

    def test_keys_aligned(self):
        assert set(M.ENGINE_INPUT_KEYS) == set(FRESHNESS_POLICY)
        assert M.ENGINE_INPUT_KEYS == DI.COVERED_ENGINE_INPUTS
        assert set(M.NUMERIC_SERIES) == set(_ENGINE_NUMERIC_INPUTS)
        assert M.BOOL_SERIES == ("Index_Below_MA5",)

    def test_run_rule_engine_does_not_overwrite(self, monkeypatch):
        monkeypatch.setattr(M, "calculate_system_state", lambda d: {"red_lines": "engine"})
        with pytest.raises(RuntimeError):
            M.run_rule_engine(_build(_inputs()))

    def test_run_rule_engine_passes_copy(self, monkeypatch):
        got = []
        monkeypatch.setattr(M, "calculate_system_state",
                            lambda d: got.append(d) or calculate_system_state(d))
        b = _build(_inputs())
        M.run_rule_engine(b)
        assert got[0] == b.macro_numbers and got[0] is not b.macro_numbers

    def test_engine_unmodified_signature(self):
        import inspect
        src = inspect.getsource(calculate_system_state)
        assert "MACRO_VETO_PMI_CONTRACTION_LEVEL and pmi_prev < MACRO_VETO_PMI_CONTRACTION_LEVEL" in src


# ══════════════════════════════════════════════════════════════════════════
# 8. 休市表跨年查證（L1 `taipei_year` 只是快取鍵）
# ══════════════════════════════════════════════════════════════════════════
class TestHolidayCrossYear:
    def test_previous_year_key_returns_same_table(self, monkeypatch):
        from src.data.stock import twse_holiday_fetcher as hf
        payload = json.loads((REPO / "tests/fixtures/twse_holiday_schedule_115_synthetic.json")
                             .read_text(encoding="utf-8"))
        hits = []
        monkeypatch.setattr(hf, "_fetch_json", lambda: hits.append(1) or payload)
        hf.fetch_twse_holiday_calendar.clear()
        try:
            last = hf.fetch_twse_holiday_calendar(taipei_year=2025)
            this = hf.fetch_twse_holiday_calendar(taipei_year=2026)
        finally:
            hf.fetch_twse_holiday_calendar.clear()
        assert last.covered_years == this.covered_years == frozenset({2026})
        assert len(hits) == 2   # 年份只是快取鍵：同一端點抓兩次、同一份表
        assert "taipei_year" not in hf.TWSE_HOLIDAY_URL
