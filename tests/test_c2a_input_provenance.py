"""C2a-1 — 引擎輸入「資料身分 × 新鮮度」兩軸契約層（DEC-080；⛔ 不接線、不改計分）。

守：
1. L0 表一致性：enum 值集合、`INPUT_POLICY` 鍵集合／role 與 `risk_cap_policy`／`FRESHNESS_POLICY` 對齊、
   PCR 標籤與 L1 `leading_indicators` 一致、PMI 標籤涵蓋 L1 `macro_core` 台灣 PMI 全部 `source`
   字面值（AST）、前月標籤＝cron 字面值、L0 只 import stdlib／shared、檔內無天數常數。
2. L2 unit 正反例（BIAS 估算、PCR 混源、PMI 代理旗標不影響、stale-cache(X)、未知標籤、同日多列…）。
3. 窮舉 property：estimated／proxy／unavailable／stale 永不 eligible；carried_forward（窗為 None）永不 True；
   存在 exists=True 但 riskcap≠True；輸出 `json.dumps(allow_nan=False)` 可過。
4. Robustness：None、非 dict、NaN、NaT、numpy bool 不 raise、不改輸入（deepcopy 比對）；單項失敗隔離。
5. 讀者守衛：新模組／`PENDING_SPEC`／`infer_input_provenance` 只准出現在兩個新檔（C2a-1 階段）；
   兩個新檔不得出現 PMI 代理旗標字樣。
"""
from __future__ import annotations

import ast
import copy
import itertools
import json
import random
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import shared.input_provenance_policy as P
from shared.freshness_policy import FRESHNESS_POLICY
from shared.risk_cap_policy import (
    OPTIONAL_INPUTS,
    REQUIRED_CORE_INPUTS,
    RISK_CAP_RULESET_VERSION,
    RULESET_DISABLED_INPUTS,
)
from shared.trading_days import CalendarSets
from src.compute.macro import dated_inputs as DI
from src.compute.macro import input_provenance as IP
from src.services import macro_engine_inputs as M

REPO = Path(__file__).resolve().parents[1]
L0_REL = "shared/input_provenance_policy.py"
L2_REL = "src/compute/macro/input_provenance.py"
UTC = timezone.utc

# 2026-10-14（週三）台北 10:00
NOW = datetime(2026, 10, 14, 2, 0, tzinfo=UTC)

ALL_KEYS = tuple(FRESHNESS_POLICY)
BAD_PROV = {P.Provenance.ESTIMATED, P.Provenance.PROXY, P.Provenance.UNAVAILABLE}


def _fixture_calendar() -> CalendarSets:
    from src.data.stock import twse_holiday_fetcher as hf
    payload = json.loads((REPO / "tests/fixtures/twse_holiday_schedule_115_synthetic.json")
                         .read_text(encoding="utf-8"))
    return hf.parse_holiday_schedule(payload, fetched_at=datetime(2026, 10, 2, tzinfo=UTC)).as_sets()


CAL = _fixture_calendar()


def _inputs(*, vix=17.3, vix_date="2026-10-13", vix_src="yfinance:^VIX:3mo:1d",
            pmi=51.2, pmi_month="2026-09-01", pmi_src="CIER-EN", pmi_extra=None,
            prev_rows=None, bias=12.3, bias_date="2026-10-13", bias_extra=None,
            pcr=126.8, pcr_src="TAIFEX", fut=-21000.0, li_date="20261013", li_extra_rows=None,
            li_stale=None, below=True, ma5_date="2026-10-13", m1b_info=None):
    """一組輸入（預設完整且新鮮）。回傳 `build_engine_inputs` 的 kwargs（不含 now／calendar）。"""
    pmi_d = {"value": pmi, "date": pmi_month, "source": pmi_src}
    pmi_d.update(pmi_extra or {})
    bias_d = {"bias_240": bias, "as_of": bias_date, "is_estimated": False, "data_days": 480}
    bias_d.update(bias_extra or {})
    rows = [{"_date": "20261007", "選PCR": 100.0, "外資大小": -1000.0, P.PCR_SOURCE_COLUMN: "TAIFEX"},
            {"_date": li_date, "選PCR": pcr, "外資大小": fut, P.PCR_SOURCE_COLUMN: pcr_src}]
    rows += li_extra_rows or []
    li = pd.DataFrame(rows)
    if li_stale is not None:
        li["_is_stale"] = li_stale
    if prev_rows is None:
        prev_rows = [(date(2026, 7, 1), 49.5, "data.gov.tw:dataset:6100"),
                     (date(2026, 8, 1), 50.4, "data.gov.tw:dataset:6100")]
    hist = pd.DataFrame([{"date": d, "pmi": v, "source": s} for d, v, s in prev_rows])
    return dict(
        macro_info={"vix": {"current": vix, "date": vix_date, "source": vix_src}, "ism_pmi": pmi_d},
        bias_info=bias_d,
        m1b_m2_info=m1b_info if m1b_info is not None else
        {"m1b_yoy": 3.2, "m2_yoy": 5.1, "data_month": "2026-08", "source": "CBC-tier1"},
        li_latest=li,
        mkt_info={"index_below_ma5": below, "index_as_of": ma5_date,
                  "ma5": 22000.0, "index_price": 21900.0 if below else 22100.0},
        pmi_history=hist,
    )


def _infer(kw, *, assessed=None, scored_keys="auto"):
    if assessed is None:
        b = M.build_engine_inputs(**kw, now=NOW, calendar=CAL)
        assessed = b.assessed
        if scored_keys == "auto":
            scored_keys = {k for k, v in b.macro_numbers.items() if v is not None}
    if scored_keys == "auto":
        scored_keys = None
    return IP.infer_input_provenance(assessed=assessed, scored_keys=scored_keys, **kw)


def _ast(rel: str) -> ast.Module:
    return ast.parse((REPO / rel).read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════════════
# 1. L0 表一致性
# ══════════════════════════════════════════════════════════════════════════
class TestL0Tables:
    def test_enum_values(self):
        assert {p.value for p in P.Provenance} == {
            "official", "secondary", "estimated", "proxy", "unavailable"}
        assert {f.value for f in P.FreshnessAxis} == {"fresh", "stale", "carried_forward"}
        assert P.PENDING_SPEC == "undetermined_pending_spec"
        assert P.SHADOW_POLICY_VERSION == "c2a-shadow-1"

    def test_risk_cap_version_not_bumped(self):
        assert RISK_CAP_RULESET_VERSION == "risk_cap.v2"
        assert P.SHADOW_POLICY_VERSION != RISK_CAP_RULESET_VERSION

    def test_key_set_aligned(self):
        disabled = set(RULESET_DISABLED_INPUTS[RISK_CAP_RULESET_VERSION])
        assert set(P.INPUT_POLICY) == set(FRESHNESS_POLICY)
        assert set(P.INPUT_POLICY) == set(REQUIRED_CORE_INPUTS) | set(OPTIONAL_INPUTS) | disabled
        assert set(P.INPUT_POLICY) == set(DI.COVERED_ENGINE_INPUTS)

    def test_roles_aligned(self):
        disabled = set(RULESET_DISABLED_INPUTS[RISK_CAP_RULESET_VERSION])
        by_role = {r: {k for k, v in P.INPUT_POLICY.items() if v.role == r} for r in P.ROLES}
        assert by_role[P.ROLE_REQUIRED_CORE] == set(REQUIRED_CORE_INPUTS)
        assert by_role[P.ROLE_DISABLED] == disabled
        assert by_role[P.ROLE_OPTIONAL] == set(OPTIONAL_INPUTS) - disabled
        assert all(v.role in P.ROLES for v in P.INPUT_POLICY.values())

    def test_rows_shape(self):
        for k, v in P.INPUT_POLICY.items():
            assert isinstance(v.normal_provenance, P.Provenance), k
            assert isinstance(v.provenance_basis, str) and v.provenance_basis, k
            assert v.riskcap_allowed_provenance == {P.Provenance.OFFICIAL, P.Provenance.SECONDARY}, k
            assert v.carried_forward_window is None, k   # 無正式定義 ⛔ 不得填天數

    def test_manager_rulings_secondary(self):
        for k in ("VIX_Index", "Index_Below_MA5", "Futures_Net_Short", "BIAS240_pct"):
            pol = P.INPUT_POLICY[k]
            assert pol.normal_provenance == P.Provenance.SECONDARY, k
            assert "轉載正式序列（總管判定，DEC-080 下 official/secondary 皆可滿足 Core，不影響資格）" \
                in pol.provenance_basis, k

    def test_pcr_labels_match_l1(self):
        from src.data.macro import leading_indicators as LI
        assert P.PCR_SOURCE_COLUMN == LI.PCR_SRC_COL
        assert set(P.PCR_LABEL_PROVENANCE) == set(LI.PCR_SRC_KIND)
        assert P.PCR_LABEL_PROVENANCE[LI.PCR_SRC_TAIFEX] == (P.Provenance.OFFICIAL, None)
        assert P.PCR_LABEL_PROVENANCE[LI.PCR_SRC_FINMIND_EST] == (P.Provenance.PROXY, "proxy_estimate")
        for lbl, kind in LI.PCR_SRC_KIND.items():
            prov, detail = P.PCR_LABEL_PROVENANCE[lbl]
            assert (prov == P.Provenance.OFFICIAL) == (kind == "official")
            if kind == "proxy_estimate":
                assert detail == P.DETAIL_PCR_PROXY_ESTIMATE == kind

    @staticmethod
    def _macro_core_tw_pmi_funcs():
        tree = _ast("src/data/macro/macro_core.py")
        return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)
                and (n.name == "fetch_tw_pmi" or n.name.startswith("_pmi_src_"))}, tree

    def test_pmi_registry_handlers_are_scanned(self):
        funcs, tree = self._macro_core_tw_pmi_funcs()
        reg = [n for n in tree.body if isinstance(n, ast.AnnAssign)
               and getattr(n.target, "id", None) == "PMI_SOURCE_REGISTRY"]
        assert len(reg) == 1
        handlers = {e.elts[1].id for e in reg[0].value.elts}
        assert handlers and handlers <= set(funcs)

    def test_pmi_labels_cover_macro_core_literals(self):
        funcs, _ = self._macro_core_tw_pmi_funcs()
        lits: set[str] = set()
        fstrings: list[ast.JoinedStr] = []
        for fn in funcs.values():
            for node in ast.walk(fn):
                if isinstance(node, ast.Dict):
                    for k, v in zip(node.keys, node.values):
                        if isinstance(k, ast.Constant) and k.value == "source":
                            if isinstance(v, ast.Constant):
                                lits.add(v.value)
                            else:
                                pytest.fail(f"非字面 source：{ast.dump(v)}")
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Subscript):
                    sl = node.targets[0].slice
                    if isinstance(sl, ast.Constant) and sl.value == "source":
                        if isinstance(node.value, ast.JoinedStr):
                            fstrings.append(node.value)
                        elif isinstance(node.value, ast.Constant):
                            lits.add(node.value.value)
        assert lits, "AST 沒掃到任何 PMI source 字面值"
        known = (P.PMI_OFFICIAL_SOURCE_LABELS | P.PMI_SECONDARY_SOURCE_LABELS
                 | P.PMI_FAILURE_SOURCE_LABELS)
        assert lits <= known, lits - known
        # 當期 8 源的實際字面值全部有登錄、且沒有多登（前月字樣除外）
        assert known - lits == {"data.gov.tw:dataset:6100"}
        # stale-cache 包裝：唯一一個 f-string，前後綴等於 L0 常數
        assert len(fstrings) == 1
        parts = fstrings[0].values
        assert isinstance(parts[0], ast.Constant) and parts[0].value == P.PMI_STALE_CACHE_PREFIX
        assert isinstance(parts[-1], ast.Constant) and parts[-1].value == P.PMI_STALE_CACHE_SUFFIX

    def test_pmi_official_secondary_per_dec080(self):
        assert {"CIER-EN", "CIER", "data.gov.tw/6100", "NDC", "data.gov.tw:dataset:6100"} \
            == P.PMI_OFFICIAL_SOURCE_LABELS
        assert {"StockFeel", "Cnyes", "MoneyDJ"} == P.PMI_SECONDARY_SOURCE_LABELS
        assert not (P.PMI_OFFICIAL_SOURCE_LABELS & P.PMI_SECONDARY_SOURCE_LABELS)
        for lbl in P.PMI_FAILURE_SOURCE_LABELS:
            assert P.PMI_LABEL_PROVENANCE[lbl] == P.Provenance.UNAVAILABLE

    def test_prev_month_label_equals_cron_literal(self):
        tree = _ast("scripts/update_macro_history.py")
        fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "fetch_tw_pmi_history"]
        assert len(fn) == 1
        lits = set()
        for node in ast.walk(fn[0]):
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Subscript):
                sl = node.targets[0].slice
                if isinstance(sl, ast.Constant) and sl.value == "source":
                    assert isinstance(node.value, ast.Constant)
                    lits.add(node.value.value)
        assert lits == {"data.gov.tw:dataset:6100"}
        assert lits <= P.PMI_OFFICIAL_SOURCE_LABELS

    def test_l0_imports_only_stdlib_and_shared(self):
        for node in ast.walk(_ast(L0_REL)):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""]
            for m in mods:
                top = m.split(".")[0]
                assert top in sys.stdlib_module_names or top == "shared" or m == "__future__", m

    def test_l2_imports_no_l1_l3(self):
        for node in ast.walk(_ast(L2_REL)):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""]
            for m in mods:
                top = m.split(".")[0]
                ok = (top in sys.stdlib_module_names or top == "shared" or m == "__future__"
                      or m.startswith("src.compute"))
                assert ok, m

    @pytest.mark.parametrize("rel", [L0_REL, L2_REL])
    def test_no_day_constants_no_staleness(self, rel):
        import shared.staleness as _stl
        text = (REPO / rel).read_text(encoding="utf-8")
        tree = ast.parse(text)
        # ⛔ 不得 import／引用 staleness 常數頂替（docstring 裡寫「不得引用」的說明不算）
        stl_consts = {n for n in vars(_stl) if n.isupper()}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert "staleness" not in (node.module or ""), node.module
            if isinstance(node, ast.Import):
                assert all("staleness" not in a.name for a in node.names)
            if isinstance(node, ast.Name):
                assert node.id not in stl_consts, node.id
            if isinstance(node, ast.Attribute):
                assert node.attr not in stl_consts, node.attr
        assert not re.search(r"[A-Za-z_]*DAYS?\b", "\n".join(
            n.id for n in ast.walk(tree) if isinstance(n, ast.Name)))
        if rel == L0_REL:   # L0：完全沒有數字常數
            nums = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                    and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
            assert nums == []

    @pytest.mark.parametrize("rel", [L0_REL, L2_REL])
    def test_no_clock_reads(self, rel):
        for node in ast.walk(_ast(rel)):
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"today", "now", "utcnow", "time"}, node.attr

    def test_import_has_no_side_effect_validation(self):
        # import 時不做驗證、不 raise（重新 import 一次也不 raise）
        import importlib
        importlib.reload(P)


# ══════════════════════════════════════════════════════════════════════════
# 2. L2 unit 正反例
# ══════════════════════════════════════════════════════════════════════════
class TestInferBaseline:
    def test_all_fresh_baseline(self):
        r = _infer(_inputs())
        assert list(r) == list(P.INPUT_POLICY)
        exp = {"VIX_Index": "secondary", "ISM_PMI_or_OECD_CLI": "official",
               "PMI_Prev_Month": "official", "Futures_Net_Short": "secondary",
               "Index_Below_MA5": "secondary", "BIAS240_pct": "secondary", "PCR": "official",
               "M1B_YoY_pct": "official", "M2_YoY_pct": "official"}
        assert {k: v["provenance"] for k, v in r.items()} == exp
        for k, v in r.items():
            assert list(v) == list(IP.RECORD_FIELDS)
            assert v["freshness"] == "fresh", k
            assert v["exists"] is v["displayable"] is v["fresh"] is True, k
            want = P.INPUT_POLICY[k].role != P.ROLE_DISABLED
            assert v["scoring_eligible"] is want and v["riskcap_eligible"] is want, k
        assert r["VIX_Index"]["as_of"] == "2026-10-13"
        assert r["ISM_PMI_or_OECD_CLI"]["as_of"] == "2026-09"
        assert r["PMI_Prev_Month"]["as_of"] == "2026-08"
        assert r["ISM_PMI_or_OECD_CLI"]["source_id"] == "CIER-EN"
        assert r["PMI_Prev_Month"]["source_id"] == "data.gov.tw:dataset:6100"
        assert r["PCR"]["source_id"] == "TAIFEX"
        assert r["VIX_Index"]["source_id"] == "yfinance:^VIX:3mo:1d"
        # actual_scored：M1B／M2 停用 ⇒ 引擎送值（計分與否在引擎），其餘鍵皆有值
        assert all(v["actual_scored"] is True for v in r.values())
        json.dumps(r, allow_nan=False)

    def test_actual_scored_none_when_not_given(self):
        r = _infer(_inputs(), scored_keys=None)
        assert all(v["actual_scored"] is None for v in r.values())
        b = M.build_engine_inputs(**_inputs(), now=NOW, calendar=CAL)
        r2 = IP.infer_input_provenance(assessed=b.assessed, scored_keys="PCR", **_inputs())
        assert all(v["actual_scored"] is None for v in r2.values())
        r3 = IP.infer_input_provenance(assessed=b.assessed, scored_keys=["PCR"], **_inputs())
        assert r3["PCR"]["actual_scored"] is True and r3["VIX_Index"]["actual_scored"] is False


class TestBias:
    def test_estimated(self):
        r = _infer(_inputs(bias_extra={"is_estimated": True, "data_days": 100}))["BIAS240_pct"]
        assert r["provenance"] == "estimated" and r["provenance_detail"] == P.DETAIL_BIAS_SHORT_WINDOW
        assert r["exists"] is True and r["freshness"] == "fresh"
        assert r["scoring_eligible"] is False and r["riskcap_eligible"] is False
        # C2a 不改計分：估算值照樣被引擎計分（shadow 觀察到的差異）
        assert r["actual_scored"] is True

    @pytest.mark.parametrize("flag", [None, 1, 0, "True", np.True_, np.False_, float("nan")])
    def test_flag_type_mismatch(self, flag):
        r = _infer(_inputs(bias_extra={"is_estimated": flag}))["BIAS240_pct"]
        assert r["provenance"] is None and "is_estimated" in r["provenance_basis"]
        assert r["scoring_eligible"] is False

    def test_flag_missing(self):
        kw = _inputs()
        del kw["bias_info"]["is_estimated"]
        r = _infer(kw)["BIAS240_pct"]
        assert r["provenance"] is None and "無 is_estimated" in r["provenance_basis"]

    def test_value_missing_is_unavailable(self):
        r = _infer(_inputs(bias=None))["BIAS240_pct"]
        assert r["provenance"] == "unavailable" and r["exists"] is False and r["freshness"] is None


class TestPcr:
    def test_finmind_estimate_is_proxy(self):
        r = _infer(_inputs(pcr_src="FinMind-TXO-inst-est"))["PCR"]
        assert r["provenance"] == "proxy" and r["provenance_detail"] == "proxy_estimate"
        assert r["source_id"] == "FinMind-TXO-inst-est"
        assert r["scoring_eligible"] is False and r["riskcap_eligible"] is False
        assert r["actual_scored"] is True

    def test_unknown_label(self):
        r = _infer(_inputs(pcr_src="SomethingElse"))["PCR"]
        assert r["provenance"] is None and "未登錄" in r["provenance_basis"]
        assert r["source_id"] == "SomethingElse" and r["scoring_eligible"] is False

    @pytest.mark.parametrize("lbl", [None, float("nan"), "", 3])
    def test_bad_label(self, lbl):
        r = _infer(_inputs(pcr_src=lbl))["PCR"]
        assert r["provenance"] is None and r["scoring_eligible"] is False

    def test_missing_column(self):
        kw = _inputs()
        kw["li_latest"] = kw["li_latest"].drop(columns=[P.PCR_SOURCE_COLUMN])
        r = _infer(kw)["PCR"]
        assert r["provenance"] is None and "來源欄" in r["provenance_basis"]

    def test_same_date_multiple_rows(self):
        dup = [{"_date": "20261013", "選PCR": 90.0, "外資大小": -20000.0,
                P.PCR_SOURCE_COLUMN: "TAIFEX"}]
        r = _infer(_inputs(li_extra_rows=dup))["PCR"]
        assert r["provenance"] is None and "2 列" in r["provenance_basis"]

    def test_walk_back_reads_that_rows_label(self):
        # 最後一列 PCR 空、往回取到 10/07 的值 ⇒ 讀 10/07 那一列的來源
        kw = _inputs(pcr=None, pcr_src=None)
        kw["li_latest"].loc[0, P.PCR_SOURCE_COLUMN] = "FinMind-TXO-inst-est"
        r = _infer(kw)["PCR"]
        assert r["as_of"] == "2026-10-07" and r["provenance"] == "proxy"

    def test_stale_pickle_is_carried_forward(self):
        r = _infer(_inputs(li_stale=True))
        assert r["PCR"]["freshness"] == "carried_forward"
        assert r["PCR"]["scoring_eligible"] == P.PENDING_SPEC
        assert r["Futures_Net_Short"]["freshness"] == "carried_forward"
        assert r["Futures_Net_Short"]["riskcap_eligible"] == P.PENDING_SPEC
        assert r["Futures_Net_Short"]["fresh"] is False

    def test_numpy_bool_stale_marker(self):
        kw = _inputs()
        kw["li_latest"]["_is_stale"] = np.array([True, True], dtype=bool)
        assert _infer(kw)["PCR"]["freshness"] == "carried_forward"

    def test_unavailable_when_value_missing(self):
        kw = _inputs()
        kw["li_latest"]["選PCR"] = None
        r = _infer(kw)["PCR"]
        assert r["provenance"] == "unavailable" and r["exists"] is False


class TestPmi:
    @pytest.mark.parametrize("src", ["data.gov.tw/6100", "NDC"])
    def test_proxy_flag_ignored_official(self, src):
        r = _infer(_inputs(pmi_src=src, pmi_extra={"is_proxy": True}))["ISM_PMI_or_OECD_CLI"]
        assert r["provenance"] == "official" and r["riskcap_eligible"] is True

    @pytest.mark.parametrize("src", ["StockFeel", "Cnyes", "MoneyDJ"])
    def test_secondary_satisfies(self, src):
        r = _infer(_inputs(pmi_src=src))["ISM_PMI_or_OECD_CLI"]
        assert r["provenance"] == "secondary" and r["riskcap_eligible"] is True

    def test_stale_cache_strip_one_layer(self):
        r = _infer(_inputs(pmi_src="stale-cache(StockFeel)",
                           pmi_extra={"is_stale": True}))["ISM_PMI_or_OECD_CLI"]
        assert r["provenance"] == "secondary" and r["freshness"] == "carried_forward"
        assert r["provenance_detail"] == P.DETAIL_PMI_STALE_CACHE
        assert r["scoring_eligible"] == P.PENDING_SPEC == r["riskcap_eligible"]
        assert r["source_id"] == "stale-cache(StockFeel)"
        assert r["actual_scored"] is True   # C2a 不改計分

    def test_stale_cache_label_alone_is_carried(self):
        r = _infer(_inputs(pmi_src="stale-cache(CIER-EN)"))["ISM_PMI_or_OECD_CLI"]
        assert r["provenance"] == "official" and r["freshness"] == "carried_forward"

    def test_is_stale_flag_alone_is_carried(self):
        r = _infer(_inputs(pmi_extra={"is_stale": True}))["ISM_PMI_or_OECD_CLI"]
        assert r["provenance"] == "official" and r["freshness"] == "carried_forward"

    @pytest.mark.parametrize("src", ["stale-cache(?)", "stale-cache(stale-cache(CIER))", "stale-cache(",
                                     "stale-cache()", "cier-en", "CIER-EN ", "xStockFeel",
                                     "StockFeel-mirror", 5, None])
    def test_unknown_or_malformed(self, src):
        r = _infer(_inputs(pmi_src=src))["ISM_PMI_or_OECD_CLI"]
        assert r["provenance"] is None and r["riskcap_eligible"] is False

    def test_failure_label_unavailable(self):
        kw = _inputs(pmi=None, pmi_src="TW_PMI:all_tiers_failed")
        r = _infer(kw)
        assert r["ISM_PMI_or_OECD_CLI"]["provenance"] == "unavailable"
        assert r["PMI_Prev_Month"]["freshness"] is None   # 當期不可用 ⇒ 前月 UNDETERMINED

    def test_prev_inconsistent_sources(self):
        rows = [(date(2026, 8, 1), 50.4, "data.gov.tw:dataset:6100"), (date(2026, 8, 1), 50.4, "CIER")]
        r = _infer(_inputs(prev_rows=rows))["PMI_Prev_Month"]
        assert r["provenance"] is None and "不一致" in r["provenance_basis"]
        assert r["exists"] is True and r["riskcap_eligible"] is False

    def test_prev_duplicate_consistent(self):
        rows = [(date(2026, 8, 1), 50.4, "data.gov.tw:dataset:6100")] * 2
        assert _infer(_inputs(prev_rows=rows))["PMI_Prev_Month"]["provenance"] == "official"

    def test_prev_nan_source(self):
        rows = [(date(2026, 8, 1), 50.4, float("nan"))]
        assert _infer(_inputs(prev_rows=rows))["PMI_Prev_Month"]["provenance"] is None

    def test_prev_no_source_column(self):
        kw = _inputs()
        kw["pmi_history"] = kw["pmi_history"].drop(columns=["source"])
        assert _infer(kw)["PMI_Prev_Month"]["provenance"] is None

    def test_prev_missing_month(self):
        r = _infer(_inputs(prev_rows=[(date(2026, 6, 1), 49.0, "CIER")]))["PMI_Prev_Month"]
        assert r["provenance"] == "unavailable" and r["exists"] is False

    def test_prev_cross_year(self):
        kw = _inputs(pmi_month="2026-01-01",
                     prev_rows=[(date(2025, 12, 1), 48.0, "data.gov.tw:dataset:6100")])
        b = M.build_engine_inputs(**kw, now=datetime(2026, 2, 3, 2, 0, tzinfo=UTC), calendar=None)
        r = IP.infer_input_provenance(assessed=b.assessed, scored_keys=None, **kw)["PMI_Prev_Month"]
        assert r["provenance"] == "official" and r["as_of"] == "2025-12"


class TestOthers:
    def test_vix_stale(self):
        r = _infer(_inputs(vix_date="2026-10-05"))["VIX_Index"]
        assert r["provenance"] == "secondary" and r["freshness"] == "stale"
        assert r["exists"] is True and r["fresh"] is False and r["riskcap_eligible"] is False
        assert r["actual_scored"] is False

    def test_vix_missing(self):
        r = _infer(_inputs(vix=None))["VIX_Index"]
        assert r["provenance"] == "unavailable" and r["freshness"] is None

    def test_vix_no_date_unavailable(self):
        r = _infer(_inputs(vix_date=None))["VIX_Index"]
        assert r["provenance"] == "unavailable" and "無資料日期" in r["provenance_basis"]

    def test_ma5(self):
        r = _infer(_inputs())["Index_Below_MA5"]
        assert r["provenance"] == "secondary" and r["exists"] is True and r["riskcap_eligible"] is True

    def test_m1b_proxy(self):
        info = {"m1b_yoy": 4.0, "m2_yoy": 5.0, "data_month": None, "source": "TWII-proxy"}
        r = _infer(_inputs(m1b_info=info))
        for k in ("M1B_YoY_pct", "M2_YoY_pct"):
            assert r[k]["provenance"] == "proxy" and r[k]["provenance_detail"] == P.DETAIL_M1B_TWII_PROXY
            assert r[k]["exists"] is True and r[k]["scoring_eligible"] is False
            assert r[k]["source_id"] == "TWII-proxy"

    def test_m1b_proxy_raw_nan_is_unavailable(self):
        info = {"m1b_yoy": float("nan"), "m2_yoy": 5.0, "source": "TWII-proxy"}
        r = _infer(_inputs(m1b_info=info))
        assert r["M1B_YoY_pct"]["provenance"] == "unavailable"
        assert r["M2_YoY_pct"]["provenance"] == "proxy"

    def test_disabled_never_eligible_even_fresh_official(self):
        r = _infer(_inputs())
        for k in RULESET_DISABLED_INPUTS[RISK_CAP_RULESET_VERSION]:
            assert r[k]["provenance"] == "official" and r[k]["fresh"] is True
            assert r[k]["scoring_eligible"] is False and r[k]["riskcap_eligible"] is False


# ══════════════════════════════════════════════════════════════════════════
# 3. 窮舉／隨機 property
# ══════════════════════════════════════════════════════════════════════════
_PROVS = list(P.Provenance) + [None, "bogus", 3]
_FRESH = list(P.FreshnessAxis) + [None, "bogus"]
_EXISTS = [True, False, None, 1, np.True_, np.False_]
_KEYS = list(ALL_KEYS) + ["Unknown_Key", None, 5]


class TestClassifyExhaustive:
    def test_exhaustive(self):
        saw_exists_not_riskcap = False
        for key, prov, fr, ex in itertools.product(_KEYS, _PROVS, _FRESH, _EXISTS):
            out = P.classify_eligibility(input_key=key, provenance=prov, freshness=fr, exists=ex)
            assert tuple(out) == P.ELIGIBILITY_FIELDS
            json.dumps(out, allow_nan=False)
            assert out["displayable"] is out["exists"]
            assert out["exists"] is (ex is True or ex is np.True_)
            assert out["fresh"] is (fr == P.FreshnessAxis.FRESH)
            assert out["scoring_eligible"] == out["riskcap_eligible"]
            v = out["riskcap_eligible"]
            assert v in (True, False, P.PENDING_SPEC)
            if prov in BAD_PROV or fr == P.FreshnessAxis.STALE or fr is None:
                assert v is False, (key, prov, fr, ex)
            if fr == P.FreshnessAxis.CARRIED_FORWARD:
                assert v is not True
            if not isinstance(key, str) or key not in P.INPUT_POLICY \
                    or P.INPUT_POLICY[key].role == P.ROLE_DISABLED:
                assert v is False
            if prov not in list(P.Provenance):
                assert v is False
            if v is True:
                assert prov in P.RISKCAP_ALLOWED_PROVENANCE and fr == P.FreshnessAxis.FRESH
                assert out["exists"] is True
            if out["exists"] and v is not True:
                saw_exists_not_riskcap = True
        assert saw_exists_not_riskcap

    def test_carried_forward_window_none_never_true(self):
        for key in ALL_KEYS:
            assert P.INPUT_POLICY[key].carried_forward_window is None
            for prov in P.Provenance:
                out = P.classify_eligibility(input_key=key, provenance=prov,
                                             freshness="carried_forward", exists=True)
                assert out["riskcap_eligible"] is not True
                if prov in P.RISKCAP_ALLOWED_PROVENANCE and P.INPUT_POLICY[key].role != P.ROLE_DISABLED:
                    assert out["riskcap_eligible"] == P.PENDING_SPEC


def _random_inputs(rng: random.Random):
    pick = rng.choice
    return _inputs(
        vix=pick([17.3, None, float("nan"), "20", True]),
        vix_date=pick(["2026-10-13", "2026-10-01", None, "bad"]),
        pmi=pick([51.2, 45.0, None, float("inf")]),
        pmi_src=pick(sorted(P.PMI_LABEL_PROVENANCE) + ["stale-cache(StockFeel)", "stale-cache(?)",
                                                         "Unknown", None]),
        pmi_extra=pick([None, {"is_stale": True}, {"is_proxy": True}]),
        pmi_month=pick(["2026-09-01", "2026-08-01", "2026-10-01", None]),
        bias=pick([12.3, 20.0, None]),
        bias_extra=pick([None, {"is_estimated": True}, {"is_estimated": "x"}]),
        pcr=pick([126.8, None, "-", 0.9]),
        pcr_src=pick(["TAIFEX", "FinMind-TXO-inst-est", None, "X"]),
        fut=pick([-21000.0, None, float("nan")]),
        li_date=pick(["20261013", "20261001", "bad"]),
        li_stale=pick([None, True, False]),
        below=pick([True, False, None]),
        ma5_date=pick(["2026-10-13", None]),
        m1b_info=pick([None, {"m1b_yoy": 1.0, "m2_yoy": 2.0, "source": "TWII-proxy"}, {}]),
    )


class TestInferProperty:
    def test_random_invariants(self):
        rng = random.Random(20261024)
        for _ in range(400):
            kw = _random_inputs(rng)
            r = _infer(kw)
            json.dumps(r, allow_nan=False)
            assert list(r) == list(P.INPUT_POLICY)
            for k, v in r.items():
                assert list(v) == list(IP.RECORD_FIELDS)
                assert not str(v["provenance_basis"]).startswith(IP.CLASSIFICATION_FAILED_PREFIX), (k, v)
                rc = v["riskcap_eligible"]
                assert v["scoring_eligible"] == rc
                if v["provenance"] in {"estimated", "proxy", "unavailable", None}:
                    assert rc is False, (k, v)
                if v["freshness"] in {"stale", None}:
                    assert rc is False, (k, v)
                if v["freshness"] == "carried_forward":
                    assert rc is not True
                if P.INPUT_POLICY[k].role == P.ROLE_DISABLED:
                    assert rc is False
                if v["provenance"] == "unavailable":
                    assert v["exists"] is False
                assert v["displayable"] is v["exists"]


# ══════════════════════════════════════════════════════════════════════════
# 4. Robustness
# ══════════════════════════════════════════════════════════════════════════
_JUNK = [None, [], "abc", 5, float("nan"), pd.NaT, np.True_, {"x": 1}, pd.DataFrame()]


class TestRobustness:
    @pytest.mark.parametrize("junk", _JUNK, ids=lambda j: type(j).__name__)
    def test_junk_everywhere_no_raise(self, junk):
        r = IP.infer_input_provenance(macro_info=junk, bias_info=junk, li_latest=junk, mkt_info=junk,
                                      m1b_m2_info=junk, pmi_history=junk, assessed=junk,
                                      scored_keys=junk)
        json.dumps(r, allow_nan=False)
        assert list(r) == list(P.INPUT_POLICY)
        for v in r.values():
            assert v["riskcap_eligible"] in (False, None)

    def test_nat_and_nan_cells(self):
        kw = _inputs()
        kw["macro_info"]["vix"]["date"] = pd.NaT
        kw["macro_info"]["ism_pmi"]["date"] = pd.NaT
        kw["li_latest"].loc[1, "_date"] = pd.NaT
        kw["pmi_history"].loc[1, "date"] = pd.NaT
        r = _infer(kw)
        json.dumps(r, allow_nan=False)
        assert r["VIX_Index"]["provenance"] == "unavailable"

    def test_assessed_junk_values(self):
        assessed = {k: object() for k in ALL_KEYS}
        r = IP.infer_input_provenance(assessed=assessed, scored_keys={"VIX_Index"}, **_inputs())
        json.dumps(r, allow_nan=False)
        assert all(v["provenance"] == "unavailable" for v in r.values()
                   if v["provenance"] is not None)
        assert all(v["riskcap_eligible"] is False for v in r.values())

    def test_inputs_not_mutated(self):
        kw = _inputs(li_stale=True, pmi_src="stale-cache(StockFeel)")
        b = M.build_engine_inputs(**kw, now=NOW, calendar=CAL)
        snap = copy.deepcopy(kw)
        scored = {"VIX_Index", "PCR"}
        scored_snap = set(scored)
        IP.infer_input_provenance(assessed=b.assessed, scored_keys=scored, **kw)
        for k in ("macro_info", "bias_info", "m1b_m2_info", "mkt_info"):
            assert kw[k] == snap[k], k
        pd.testing.assert_frame_equal(kw["li_latest"], snap["li_latest"])
        pd.testing.assert_frame_equal(kw["pmi_history"], snap["pmi_history"])
        assert kw["li_latest"].attrs == snap["li_latest"].attrs
        assert scored == scored_snap

    def test_deterministic(self):
        kw = _inputs()
        b = M.build_engine_inputs(**kw, now=NOW, calendar=CAL)
        a1 = IP.infer_input_provenance(assessed=b.assessed, scored_keys=None, **kw)
        a2 = IP.infer_input_provenance(assessed=b.assessed, scored_keys=None, **kw)
        assert a1 == a2

    def test_single_item_failure_isolated(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("secret upstream text")
        monkeypatch.setitem(IP._CLASSIFIERS, "PCR", boom)
        r = _infer(_inputs())
        assert r["PCR"]["provenance_basis"] == "classification_failed:RuntimeError"
        assert "secret" not in json.dumps(r, ensure_ascii=False)
        assert all(r["PCR"][f] is None for f in IP.RECORD_FIELDS if f != "provenance_basis")
        assert r["VIX_Index"]["provenance"] == "secondary"


# ══════════════════════════════════════════════════════════════════════════
# 5. 讀者守衛（C2a-1 階段：不接線）
# ══════════════════════════════════════════════════════════════════════════
_GUARD_NAMES = ("input_provenance_policy", "input_provenance", "PENDING_SPEC",
                "infer_input_provenance", "undetermined_pending_spec")
_GUARD_ALLOWED = {L0_REL, L2_REL}
#: C2a-1 階段明列不得出現上述名稱的檔（亦被下方全掃描涵蓋；明列是為了讓意圖可讀）。
_GUARD_FORBIDDEN_EXPLICIT = (
    "shared/risk_cap_policy.py", "src/services/macro_state_locker.py",
    "src/services/allocation_service.py", "shared/allocation_decision.py",
    "src/services/ai_qa_service.py", "shared/risk_cap_history_policy.py",
    "src/services/risk_cap_history_service.py", "src/services/risk_cap_history_reader_service.py",
    "src/services/macro_engine_inputs.py", "src/compute/macro/dated_inputs.py",
    "src/services/risk_cap_apply.py",
)
_GUARD_PAT = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(map(re.escape, _GUARD_NAMES)) + r")(?![A-Za-z0-9_])")


def _guard_hits(text: str) -> set[str]:
    hits = set(_GUARD_PAT.findall(text))
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and "input_provenance" in node.module:
            hits.add(node.module)
        elif isinstance(node, ast.Import):
            hits |= {a.name for a in node.names if "input_provenance" in a.name}
    return hits


class TestReaderGuard:
    def test_explicit_files_exist_and_clean(self):
        for rel in _GUARD_FORBIDDEN_EXPLICIT:
            p = REPO / rel
            assert p.exists(), rel
            assert not _guard_hits(p.read_text(encoding="utf-8")), rel
        for p in (REPO / "src/ui").rglob("*.py"):
            assert not _guard_hits(p.read_text(encoding="utf-8")), p

    def test_only_new_files_reference(self):
        files = [REPO / "app.py"] + [p for d in ("src", "shared", "scripts") for p in (REPO / d).rglob("*.py")]
        hits = {}
        for p in files:
            rel = p.relative_to(REPO).as_posix()
            if "__pycache__" in rel:
                continue
            h = _guard_hits(p.read_text(encoding="utf-8"))
            if h:
                hits[rel] = h
        assert set(hits) <= _GUARD_ALLOWED, {k: v for k, v in hits.items() if k not in _GUARD_ALLOWED}
        assert L2_REL in hits

    @pytest.mark.parametrize("rel", [L0_REL, L2_REL])
    def test_no_pmi_proxy_flag_in_new_files(self, rel):
        assert "is_proxy" not in (REPO / rel).read_text(encoding="utf-8")

    def test_l2_does_not_spell_l1_pcr_names(self):
        # 欄名只准取自 L0 常數；L2 檔內不得出現 L1 的欄名字面／常數名（C1 零讀者守衛的白名單只加 L0）
        text = (REPO / L2_REL).read_text(encoding="utf-8")
        for name in ("_pcr_src", "PCR_SRC_COL", "PCR_SRC_KIND", "PCR_SRC_TAIFEX", "PCR_SRC_FINMIND_EST"):
            assert not re.search(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", text), name
