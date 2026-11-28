"""src/compute/health/financial_health_evidence.py 單元測試（離線、決定性、無網路）。

涵蓋：手算一致 / 與既有引擎定義對照（引擎不可 import 時 skip，見 TestEngineParity）/
缺值（None、缺鍵、NaN、inf）/ 真 0 ≠ 缺值 / 分母 0 與負 / 適用性 / basis / PIT /
壞輸入 raise / 不改輸入、決定性、唯讀 / 禁字掃描 / 模組純度（AST）/ 突變防守。

突變防守（class TestMutationGuards）：把某個防線拔掉（monkeypatch），對應的
``_assert_*`` 輔助函式必須因此失敗，證明測試真的守得到該防線。
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import datetime as dt
import inspect
import math
import pathlib
import re

import pytest

import src.compute.health.financial_health_evidence as fhe
from src.compute.health.financial_health_evidence import (
    ITEM_NAMES,
    METRIC_NAMES,
    EvidenceMetric,
    FinancialEvidence,
    FinancialEvidenceInputError,
    FinancialPeriodInput,
    build_financial_evidence,
)

TZ = dt.timezone(dt.timedelta(hours=8))
FETCHED = dt.datetime(2026, 11, 1, 12, 0, tzinfo=TZ)

# 數值刻意取「引擎 1 位小數捨入後仍可區分」的非整除值，使對照有鑑別力。
BASE_ITEMS = {
    "revenue": 1_234_567.0, "cogs": 700_000.0, "gross_profit": 534_567.0,
    "operating_income": 187_654.0, "net_income": 143_210.0,
    "total_assets": 5_432_100.0, "current_assets": 2_345_678.0,
    "current_liabilities": 1_098_765.0, "total_liabilities": 2_468_024.0,
    "equity": 2_964_076.0, "cash": 812_345.0, "inventory": 345_678.0,
    "ocf": 198_765.0, "capex": 50_000.0, "dividends": 30_000.0,
}


def make_period(items_over: dict | None = None, drop: tuple[str, ...] = (), **over):
    items = dict(BASE_ITEMS)
    items.update(items_over or {})
    for k in drop:
        items.pop(k, None)
    kw = dict(period_end=dt.date(2026, 9, 30), source="FINMIND:TEST", fetched_at=FETCHED,
              unit="千元", basis="single_quarter", published_at=dt.date(2026, 11, 12),
              items=items)
    kw.update(over)
    return FinancialPeriodInput(**kw)


def ev(company_type: str = "general", **kw) -> FinancialEvidence:
    return build_financial_evidence(make_period(**kw), company_type=company_type)


def isc(a, b, tol=1e-9) -> bool:
    return math.isclose(a, b, rel_tol=tol, abs_tol=1e-9)


def _handcalc(i: dict) -> dict:
    return {
        "gross_margin_pct": i["gross_profit"] / i["revenue"] * 100,
        "operating_margin_pct": i["operating_income"] / i["revenue"] * 100,
        "net_margin_pct": i["net_income"] / i["revenue"] * 100,
        "cash_ratio_pct": i["cash"] / i["total_assets"] * 100,
        "debt_ratio_pct": i["total_liabilities"] / i["total_assets"] * 100,
        "current_ratio": i["current_assets"] / i["current_liabilities"],
        "quick_ratio": (i["current_assets"] - i["inventory"]) / i["current_liabilities"],
        "ocf_to_net_income": i["ocf"] / i["net_income"],
    }


# ── 正常 fixture ─────────────────────────────────────────────────────

class TestNormalAgainstHandCalc:
    def test_every_metric_matches_hand_calc(self):
        e = ev()
        exp = _handcalc(BASE_ITEMS)
        assert tuple(e.metrics) == METRIC_NAMES
        for name, want in exp.items():
            m = e.metrics[name]
            assert m.status == "ok" and m.reason_code is None
            assert isc(m.value, round(want, fhe.ROUND_DIGITS), 1e-12), name

    def test_literal_values_for_round_numbers(self):
        e = ev(items_over={
            "revenue": 1000.0, "gross_profit": 400.0, "operating_income": 150.0,
            "net_income": 120.0, "total_assets": 5000.0, "cash": 750.0,
            "total_liabilities": 2500.0, "current_assets": 2000.0,
            "current_liabilities": 1000.0, "inventory": 300.0, "ocf": 180.0})
        v = {n: m.value for n, m in e.metrics.items()}
        assert v == {"gross_margin_pct": 40.0, "operating_margin_pct": 15.0,
                     "net_margin_pct": 12.0, "cash_ratio_pct": 15.0,
                     "debt_ratio_pct": 50.0, "current_ratio": 2.0,
                     "quick_ratio": 1.7, "ocf_to_net_income": 1.5}

    def test_metric_metadata(self):
        e = ev()
        for name, m in e.metrics.items():
            assert m.name == name and m.formula_id and m.inputs
            assert all(x in ITEM_NAMES for x in m.inputs)
            assert m.unit_label == ("%" if name.endswith("_pct") else "倍")
        assert e.metrics["quick_ratio"].inputs == ("current_assets", "inventory",
                                                   "current_liabilities")

    def test_envelope_fields_carried_verbatim(self):
        e = ev()
        assert (e.period_end, e.source, e.fetched_at, e.unit, e.basis) == (
            dt.date(2026, 9, 30), "FINMIND:TEST", FETCHED, "千元", "single_quarter")
        assert e.published_at == dt.date(2026, 11, 12) and e.company_type == "general"
        assert set(e.items) == set(ITEM_NAMES)
        for k, v in BASE_ITEMS.items():
            assert e.items[k] == v

    def test_rounding_is_fixed_digits(self):
        e = ev(items_over={"gross_profit": 1.0, "revenue": 3.0})
        assert e.metrics["gross_margin_pct"].value == round(100 / 3, fhe.ROUND_DIGITS)

    def test_basis_cumulative_same_numbers(self):
        a, b = ev(basis="single_quarter"), ev(basis="cumulative")
        assert {n: m.value for n, m in a.metrics.items()} == {n: m.value for n, m in b.metrics.items()}


# ── 與既有引擎定義對照 ───────────────────────────────────────────────

_ENGINE_SRC = pathlib.Path(fhe.__file__).resolve().parents[2] / "data/core/financial_statements_fetcher.py"


def _engine():
    try:
        import src.services.financial_health_engine as eng
    except ImportError as exc:  # 缺 streamlit 等：CI 有真套件時會執行
        pytest.skip(f"引擎無法 import（{exc}）；對照測試需完整依賴")
    return eng


def _pct(s: str) -> float:
    return float(s.split("%")[0])


def _fd(i: dict) -> dict:
    """把型別化科目轉成引擎 legacy 字典（單位千元；比率欄用取數層同一公式預先算好）。"""
    return {
        "營業收入(千)": i["revenue"], "營業成本(千)": i["cogs"], "毛利(千)": i["gross_profit"],
        "毛利率(%)": round(i["gross_profit"] / i["revenue"] * 100, 1),
        "營業利益(千)": i["operating_income"], "稅後淨利(千)": i["net_income"],
        "總資產(千)": i["total_assets"], "流動資產(千)": i["current_assets"],
        "流動負債(千)": i["current_liabilities"], "總負債(千)": i["total_liabilities"],
        "股東權益(千)": i["equity"], "存貨(千)": i["inventory"], "OCF(千)": i["ocf"],
        "現金佔總資產(%)": round(i["cash"] / i["total_assets"] * 100, 1),
        # 0 → 觸發引擎「從原始欄位自行重算」兜底（總負債 / 總資產），以對照其實際定義
        "負債比率(%)": 0,
    }


_PARITY_SETS = [
    BASE_ITEMS,
    {**BASE_ITEMS, "revenue": 987_654.0, "operating_income": 23_456.0, "net_income": 17_890.0,
     "current_assets": 456_789.0, "current_liabilities": 678_901.0, "inventory": 123_456.0,
     "ocf": 9_876.0, "total_liabilities": 3_210_987.0, "total_assets": 4_321_098.0},
    {**BASE_ITEMS, "operating_income": -45_678.0, "net_income": 12_345.0, "ocf": 54_321.0},
]


class TestEngineParity:
    """本模組比率 vs 既有引擎 `_no_ai_*` 實際輸出。引擎 % 字串只取 1 位小數：
    pct 欄容差 0.05（半個末位）、倍數欄（引擎 % / 100）容差 0.0005。"""

    @pytest.mark.parametrize("items", _PARITY_SETS)
    def test_margins_current_quick_debt_ocf_match_engine(self, items):
        eng = _engine()
        fd = _fd(items)
        e = build_financial_evidence(make_period(items_over=items), company_type="general")
        prof = eng._no_ai_profitability(fd)["Profitability_Module"]
        sol = eng._no_ai_solvency(fd)["Solvency_Module"]
        fs = eng._no_ai_financial_structure(fd)["Financial_Structure_Module"]
        adv = eng._no_ai_advanced_diagnostic(fd)["Advanced_Diagnostic_Module"]
        m = e.metrics
        assert abs(m["operating_margin_pct"].value - _pct(prof["Operating_Margin"]["Value"])) <= 0.05 + 1e-9
        assert abs(m["net_margin_pct"].value - _pct(prof["Net_Margin"]["Value"])) <= 0.05 + 1e-9
        assert abs(m["current_ratio"].value - _pct(sol["Current_Ratio"]["Value"]) / 100) <= 0.0005 + 1e-9
        assert abs(m["quick_ratio"].value - _pct(sol["Quick_Ratio"]["Value"]) / 100) <= 0.0005 + 1e-9
        assert abs(m["debt_ratio_pct"].value - _pct(fs["Debt_Ratio"]["Value"])) <= 0.05 + 1e-9
        assert abs(m["ocf_to_net_income"].value - _pct(adv["Earnings_Quality"]["Value"]) / 100) <= 0.0005 + 1e-9

    def test_gross_margin_and_cash_ratio_passthrough_values_equal(self):
        """引擎對這兩項只是讀取數層算好的欄位再格式化 → 此處驗「讀到的值＝本包值」。"""
        eng = _engine()
        fd = _fd(BASE_ITEMS)
        prof = eng._no_ai_profitability(fd)["Profitability_Module"]
        e = ev()
        assert abs(e.metrics["gross_margin_pct"].value - _pct(prof["Gross_Margin"]["Value"])) <= 0.05 + 1e-9
        assert abs(e.metrics["cash_ratio_pct"].value - fd["現金佔總資產(%)"]) <= 0.05 + 1e-9

    def test_fetcher_source_defines_ratios_as_we_do(self):
        """gross_margin / cash_ratio / debt_ratio 的真正定義在取數層（內嵌於大函式，無法單獨呼叫）。
        以原始碼逐字守衛公式未漂移（取數層若改公式，此測試轉紅，須重新對照）。
        僅為漂移提醒：格式重排（如 black）造成的紅燈應視為提醒而非缺陷。"""
        src = _ENGINE_SRC.read_text(encoding="utf-8")
        for needle in ("round(cash / assets * 100, 1)", "round(liab / assets * 100, 1)",
                       "round(gp / rev * 100, 1)"):
            assert needle in src, needle

    def test_engine_formula_markers_unchanged(self):
        """引擎端公式字面守衛（可在無 streamlit 環境執行）：定義漂移時提醒重新對照。
        僅為漂移提醒：格式重排（如 black）造成的紅燈應視為提醒而非缺陷。"""
        path = pathlib.Path(fhe.__file__).resolve().parents[2] / "services/financial_health_engine.py"
        src = path.read_text(encoding="utf-8")
        for needle in ("round(oi / rev * 100, 1)", "round(ni / rev * 100, 1)",
                       "round(ca / cl * 100, 1)", "round((ca - inv) / cl * 100, 1)",
                       "round(ocf / ni * 100, 1)",
                       "round(_eff_liab / _eff_assets * 100, 1)"):
            assert needle in src, needle


# ── 缺值 ─────────────────────────────────────────────────────────────

def _variants():
    return [("none", None), ("absent", "ABSENT"), ("nan", float("nan")),
            ("inf", float("inf")), ("ninf", float("-inf"))]


class TestMissingValues:
    @pytest.mark.parametrize("name,variant", [(n, v) for n in ITEM_NAMES for v in _variants()],
                             ids=lambda x: x if isinstance(x, str) else None)
    def test_each_item_missing_only_affects_dependents(self, name, variant):
        _label, val = variant
        if val == "ABSENT":
            e = ev(drop=(name,))
            want_reason = "missing_input"
        else:
            e = ev(items_over={name: val})
            want_reason = ("missing_input" if val is None else "non_finite_input")
        assert e.items[name] is None                       # 絕不變 0、不保留 NaN
        for spec in fhe._SPECS:
            m = e.metrics[spec.name]
            if name in spec.inputs:
                assert m.status == "unknown" and m.value is None
                assert m.reason_code == want_reason
            else:
                assert m.status == "ok" and m.value is not None
        if want_reason == "non_finite_input":
            assert f"non_finite_item:{name}" in e.input_issues
            assert fhe.LIMITATION_NON_FINITE in e.limitations
        else:
            assert e.input_issues == ()

    def test_missing_is_not_zero_value(self):
        e = ev(drop=("cash",))
        assert e.metrics["cash_ratio_pct"].value is None
        assert e.metrics["cash_ratio_pct"].value != 0

    def test_all_items_missing(self):
        e = build_financial_evidence(make_period(items={}), company_type="general")
        assert all(m.status == "unknown" and m.reason_code == "missing_input"
                   for m in e.metrics.values())
        assert all(v is None for v in e.items.values())


class TestTrueZeroIsNotMissing:
    def test_zero_liabilities_is_zero_percent_ok(self):
        m = ev(items_over={"total_liabilities": 0.0}).metrics["debt_ratio_pct"]
        assert m.status == "ok" and m.value == 0.0

    def test_zero_cash_is_ok(self):
        m = ev(items_over={"cash": 0.0}).metrics["cash_ratio_pct"]
        assert m.status == "ok" and m.value == 0.0

    def test_zero_inventory_quick_equals_current(self):
        e = ev(items_over={"inventory": 0.0})
        assert e.metrics["quick_ratio"].status == "ok"
        assert e.metrics["quick_ratio"].value == e.metrics["current_ratio"].value

    def test_zero_gross_and_operating_income_ok(self):
        e = ev(items_over={"gross_profit": 0.0, "operating_income": 0.0})
        assert e.metrics["gross_margin_pct"].value == 0.0
        assert e.metrics["operating_margin_pct"].value == 0.0
        assert e.metrics["gross_margin_pct"].status == "ok"

    def test_zero_ocf_is_ok_zero(self):
        m = ev(items_over={"ocf": 0.0}).metrics["ocf_to_net_income"]
        assert m.status == "ok" and m.value == 0.0

    def test_zero_item_preserved_in_items(self):
        e = ev(items_over={"cash": 0.0})
        assert e.items["cash"] == 0.0 and e.items["cash"] is not None

    def test_negative_numerator_is_real_loss_not_missing(self):
        e = ev(items_over={"operating_income": -50_000.0, "net_income": -1.0})
        assert e.metrics["operating_margin_pct"].value < 0
        assert e.metrics["net_margin_pct"].status == "ok" and e.metrics["net_margin_pct"].value < 0


# ── 分母 0 / 負 / 荒謬值 ─────────────────────────────────────────────

class TestDenominators:
    @pytest.mark.parametrize("item,affected", [
        ("revenue", ("gross_margin_pct", "operating_margin_pct", "net_margin_pct")),
        ("total_assets", ("cash_ratio_pct", "debt_ratio_pct")),
        ("current_liabilities", ("current_ratio", "quick_ratio")),
    ])
    def test_zero_denominator_unknown_not_zero_or_inf(self, item, affected):
        e = ev(items_over={item: 0.0})
        for n in affected:
            m = e.metrics[n]
            assert m.status == "unknown" and m.reason_code == "zero_denominator"
            assert m.value is None
        others = set(METRIC_NAMES) - set(affected) - {
            s.name for s in fhe._SPECS if item in s.inputs}
        assert all(e.metrics[n].status == "ok" for n in others)

    @pytest.mark.parametrize("item,affected", [
        ("revenue", ("gross_margin_pct", "operating_margin_pct", "net_margin_pct")),
        ("total_assets", ("cash_ratio_pct", "debt_ratio_pct")),
        ("current_liabilities", ("current_ratio", "quick_ratio")),
    ])
    def test_negative_denominator_unknown(self, item, affected):
        e = ev(items_over={item: -100.0})
        for n in affected:
            assert e.metrics[n].status == "unknown"
            assert e.metrics[n].reason_code == "non_positive_denominator"
            assert e.metrics[n].value is None

    @pytest.mark.parametrize("ni", [0.0, -1.0, -143_210.0])
    def test_ocf_to_net_income_non_positive_net_income(self, ni):
        m = ev(items_over={"net_income": ni}).metrics["ocf_to_net_income"]
        assert m.status == "unknown" and m.reason_code == "non_positive_denominator"
        assert m.value is None

    @pytest.mark.parametrize("item", ["cash", "current_assets", "inventory", "total_liabilities"])
    def test_negative_balance_item_rejected_as_invalid(self, item):
        e = ev(items_over={item: -1.0})
        for spec in fhe._SPECS:
            if item in spec.inputs:
                assert e.metrics[spec.name].reason_code == "invalid_negative_input"
                assert e.metrics[spec.name].value is None

    def test_inventory_exceeding_current_assets_is_inconsistent(self):
        m = ev(items_over={"inventory": 9_999_999.0}).metrics["quick_ratio"]
        assert m.status == "unknown" and m.reason_code == "inconsistent_input"
        assert ev(items_over={"inventory": 9_999_999.0}).metrics["current_ratio"].status == "ok"

    def test_overflow_result_is_unknown_not_inf(self):
        e = ev(items_over={"gross_profit": 1e308, "revenue": 1e-5})
        m = e.metrics["gross_margin_pct"]
        assert m.status == "unknown" and m.reason_code == "non_finite_result" and m.value is None

    def test_tiny_but_positive_denominator_is_used(self):
        m = ev(items_over={"revenue": 1e-6, "gross_profit": 5e-7}).metrics["gross_margin_pct"]
        assert m.status == "ok" and isc(m.value, 50.0)


# ── 適用性 ───────────────────────────────────────────────────────────

class TestApplicability:
    @pytest.mark.parametrize("ct", ["financial", "etf"])
    def test_financial_and_etf_not_applicable(self, ct):
        e = ev(ct)
        assert tuple(e.metrics) == METRIC_NAMES
        for m in e.metrics.values():
            assert m.status == "not_applicable" and m.value is None
            assert m.reason_code == "not_applicable_company_type"
        assert fhe.LIMITATION_NOT_APPLICABLE in e.limitations
        assert e.items["revenue"] == BASE_ITEMS["revenue"]    # 原值仍保留

    def test_unknown_company_type_is_unknown(self):
        e = ev("unknown")
        for m in e.metrics.values():
            assert m.status == "unknown" and m.value is None
            assert m.reason_code == "unknown_company_type"
        assert fhe.LIMITATION_UNKNOWN_TYPE in e.limitations

    def test_company_type_has_no_default(self):
        p = inspect.signature(build_financial_evidence).parameters["company_type"]
        assert p.default is inspect.Parameter.empty and p.kind is inspect.Parameter.KEYWORD_ONLY
        with pytest.raises(TypeError):
            build_financial_evidence(make_period())          # type: ignore[call-arg]

    @pytest.mark.parametrize("bad", [None, "General", "bank", "", 1, ("general",)])
    def test_invalid_company_type_raises(self, bad):
        with pytest.raises(FinancialEvidenceInputError):
            build_financial_evidence(make_period(), company_type=bad)

    def test_not_applicable_still_records_nonfinite_issue(self):
        e = ev("financial", items_over={"revenue": float("nan")})
        assert "non_finite_item:revenue" in e.input_issues
        assert e.items["revenue"] is None


# ── basis ────────────────────────────────────────────────────────────

_FLOW = {"gross_margin_pct", "operating_margin_pct", "net_margin_pct", "ocf_to_net_income"}


class TestBasis:
    def test_basis_none_blocks_flow_metrics_only(self):
        e = ev(basis=None)
        for n in METRIC_NAMES:
            m = e.metrics[n]
            if n in _FLOW:
                assert m.status == "unknown" and m.reason_code == "basis_unknown" and m.value is None
            else:
                assert m.status == "ok" and m.value is not None
        assert fhe.LIMITATION_BASIS_UNKNOWN in e.limitations and e.basis is None

    @pytest.mark.parametrize("b", ["single_quarter", "cumulative"])
    def test_known_basis_computes_all(self, b):
        assert all(m.status == "ok" for m in ev(basis=b).metrics.values())

    @pytest.mark.parametrize("bad", ["quarterly", "", "Cumulative", 1])
    def test_invalid_basis_raises(self, bad):
        with pytest.raises(FinancialEvidenceInputError):
            ev(basis=bad)


# ── PIT ──────────────────────────────────────────────────────────────

class TestPit:
    def test_no_published_at_is_unknown(self):
        e = ev(published_at=None)
        assert e.pit_status == "unknown_publication_date" and e.published_at is None
        assert fhe.LIMITATION_PIT in e.limitations

    def test_declared_never_verified(self):
        e = ev()
        assert e.pit_status == "published_at_declared"
        assert fhe.LIMITATION_PIT_DECLARED in e.limitations
        assert fhe.LIMITATION_PIT in e.limitations

    def test_pit_values_are_closed_set_without_verified(self):
        assert {fhe.PIT_UNKNOWN, fhe.PIT_DECLARED} == {"unknown_publication_date", "published_at_declared"}
        for pa in (None, dt.date(2026, 11, 12)):
            assert "verified" not in ev(published_at=pa).pit_status.lower()

    def test_fixed_limitation_sentences_verbatim(self):
        e = ev()
        assert "財報口徑（單季或累計）由來源提供，未驗證時相關比率不輸出。" in e.limitations
        assert "未取得發布可得日時不聲稱時點正確，亦不可用於歷史判斷。" in e.limitations

    def test_excluded_list_documented(self):
        s = fhe.LIMITATION_EXCLUDED
        for w in ("DSO", "DPO", "DIO", "ROE", "100-100-10", "趨勢"):
            assert w in s

    def test_published_before_period_end_raises(self):
        with pytest.raises(FinancialEvidenceInputError):
            ev(published_at=dt.date(2026, 9, 29))


# ── 壞輸入 raise ─────────────────────────────────────────────────────

_NAIVE = dt.datetime(2026, 11, 1, 12, 0)


class TestBadInputRaises:
    @pytest.mark.parametrize("over", [
        dict(period_end="2026-09-30"),
        dict(period_end=dt.datetime(2026, 9, 30, 0, 0)),
        dict(period_end=None),
        dict(source=""), dict(source="   "), dict(source=None), dict(source=5),
        dict(unit=""), dict(unit="  "), dict(unit=None),
        dict(fetched_at=_NAIVE), dict(fetched_at=None), dict(fetched_at="2026-11-01"),
        dict(fetched_at=dt.date(2026, 11, 1)),
        dict(published_at=dt.datetime(2026, 11, 12, 0, 0)), dict(published_at="2026-11-12"),
        dict(items=None), dict(items=[("revenue", 1.0)]), dict(items="revenue"),
    ])
    def test_bad_envelope(self, over):
        with pytest.raises(FinancialEvidenceInputError):
            build_financial_evidence(make_period(**over), company_type="general")

    @pytest.mark.parametrize("val", [True, False, "100", b"1", [1], 1 + 2j, object()])
    def test_bad_item_value_type(self, val):
        with pytest.raises(FinancialEvidenceInputError):
            ev(items_over={"revenue": val})

    def test_unknown_item_name(self):
        with pytest.raises(FinancialEvidenceInputError) as ei:
            ev(items_over={"roe": 1.0})
        assert "roe" in str(ei.value)

    def test_wrong_period_type(self):
        with pytest.raises(FinancialEvidenceInputError):
            build_financial_evidence({"period_end": dt.date(2026, 9, 30)}, company_type="general")  # type: ignore[arg-type]

    def test_huge_int_raises(self):
        with pytest.raises(FinancialEvidenceInputError):
            ev(items_over={"revenue": 10 ** 400})

    def test_numpy_scalars_accepted(self):
        np = pytest.importorskip("numpy")
        e = ev(items_over={"revenue": np.float64(100.0), "gross_profit": np.int64(40)})
        assert e.metrics["gross_margin_pct"].value == 40.0

    def test_int_values_accepted(self):
        assert ev(items_over={"revenue": 100, "gross_profit": 40}).metrics["gross_margin_pct"].value == 40.0

    def test_metric_invariants_enforced(self):
        with pytest.raises(FinancialEvidenceInputError):
            EvidenceMetric("x", 1.0, "unknown", "missing_input", "f", (), "%")
        with pytest.raises(FinancialEvidenceInputError):
            EvidenceMetric("x", None, "ok", None, "f", (), "%")
        with pytest.raises(FinancialEvidenceInputError):
            EvidenceMetric("x", float("nan"), "ok", None, "f", (), "%")
        with pytest.raises(FinancialEvidenceInputError):
            EvidenceMetric("x", None, "unknown", "made_up", "f", (), "%")
        with pytest.raises(FinancialEvidenceInputError):
            EvidenceMetric("x", None, "weird", "missing_input", "f", (), "%")


# ── 不改輸入 / 決定性 / 唯讀 ────────────────────────────────────────

class TestPurityOfBehavior:
    def test_input_items_not_mutated(self):
        items = dict(BASE_ITEMS)
        items["cash"] = float("nan")
        items["cogs"] = None
        before = copy.deepcopy(items)
        p = make_period(items=items)
        build_financial_evidence(p, company_type="general")
        assert set(items) == set(before)
        for k in before:
            a, b = items[k], before[k]
            assert (a is None and b is None) or (a != a and b != b) or a == b

    def test_deterministic(self):
        assert ev() == ev()
        assert ev("etf") == ev("etf")

    def test_frozen(self):
        e = ev()
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.company_type = "financial"                       # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.metrics["current_ratio"].value = 0.0             # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            make_period().unit = "元"                          # type: ignore[misc]

    def test_outputs_read_only(self):
        e = ev()
        with pytest.raises(TypeError):
            e.items["cash"] = 1.0                              # type: ignore[index]
        with pytest.raises(TypeError):
            e.metrics["x"] = e.metrics["current_ratio"]        # type: ignore[index]
        with pytest.raises(TypeError):
            del e.items["cash"]                                # type: ignore[attr-defined]

    def test_output_not_aliased_to_input(self):
        items = dict(BASE_ITEMS)
        e = build_financial_evidence(make_period(items=items), company_type="general")
        items["cash"] = 1.0
        assert e.items["cash"] == BASE_ITEMS["cash"]

    def test_items_always_full_schema(self):
        e = build_financial_evidence(make_period(items={"revenue": 1.0}), company_type="general")
        assert tuple(e.items) == ITEM_NAMES
        assert e.items["revenue"] == 1.0 and e.items["cash"] is None


# ── 禁字 / 結構掃描 ──────────────────────────────────────────────────

_BANNED_WORDS = ("grade", "headline", "radar", "verified", "買進", "賣出", "加碼", "減碼",
                 "目標價", "停損", "信心", "機率", "看多", "看空", "評級", "燈號", "建議")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")
_SRC = pathlib.Path(fhe.__file__).read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)


def _all_strings(e: FinancialEvidence) -> list[str]:
    out = [e.source, e.unit, e.pit_status, e.company_type, *e.limitations, *e.input_issues]
    out += list(e.items)
    for m in e.metrics.values():
        out += [m.name, m.status, m.reason_code or "", m.formula_id, m.unit_label, *m.inputs]
    return out


class TestWording:
    @pytest.mark.parametrize("ct", ["general", "financial", "etf", "unknown"])
    def test_output_strings_clean(self, ct):
        e = ev(ct, items_over={"cash": float("nan")}, published_at=None, basis=None)
        for s in _all_strings(e):
            low = s.lower()
            for w in _BANNED_WORDS:
                assert w not in low, (w, s)
            assert not _EMOJI.search(s), s

    def test_no_forbidden_field_names(self):
        names = {f.name for f in dataclasses.fields(FinancialEvidence)}
        names |= {f.name for f in dataclasses.fields(EvidenceMetric)}
        names |= {f.name for f in dataclasses.fields(FinancialPeriodInput)}
        for n in names | set(METRIC_NAMES) | set(ITEM_NAMES):
            tokens = set(n.lower().split("_"))      # 以 token 比對（operating 含 rating 子字串）
            for w in ("grade", "score", "radar", "rating", "signal", "light", "headline"):
                assert w not in tokens, n

    def test_source_text_clean(self):
        low = _SRC.lower()
        for w in _BANNED_WORDS:
            assert w not in low, w
        assert not _EMOJI.search(_SRC)

    def test_excluded_metrics_not_emitted(self):
        for bad in ("dso", "dpo", "dio", "roe", "100_100_10", "trend", "score", "dna"):
            assert not any(bad in n for n in METRIC_NAMES), bad

    def test_metric_set_is_exactly_eight(self):
        assert METRIC_NAMES == ("gross_margin_pct", "operating_margin_pct", "net_margin_pct",
                                "cash_ratio_pct", "debt_ratio_pct", "current_ratio",
                                "quick_ratio", "ocf_to_net_income")


# ── 模組純度（AST）───────────────────────────────────────────────────

_BANNED_IMPORT_PREFIXES = ("streamlit", "requests", "yfinance", "FinMind", "time", "src.data",
                           "src.ui", "src.ui2", "src.services", "app", "shared.proxy_helper",
                           "proxy_helper", "google", "gemini", "openai", "pandas", "numpy",
                           "src.services.financial_health_engine", "financial_health_engine")
_CLOCK_ATTRS = {"now", "today", "utcnow", "utcfromtimestamp", "fromtimestamp",
                "monotonic", "perf_counter", "time", "sleep"}


def _imported_modules() -> list[str]:
    mods: list[str] = []
    for node in ast.walk(_TREE):
        if isinstance(node, ast.Import):
            mods += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods.append(node.module or "")
    return mods


class TestModulePurity:
    def test_no_banned_imports(self):
        for m in _imported_modules():
            for p in _BANNED_IMPORT_PREFIXES:
                assert not (m == p or m.startswith(p + ".")), f"禁止 import {m}"

    def test_only_stdlib_imports(self):
        assert set(_imported_modules()) <= {
            "__future__", "datetime", "math", "numbers", "dataclasses", "types", "typing"}

    def test_no_clock_calls(self):
        for n in ast.walk(_TREE):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                assert n.func.attr not in _CLOCK_ATTRS, n.func.attr
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                assert n.func.id not in _CLOCK_ATTRS

    def test_no_io_calls(self):
        for n in ast.walk(_TREE):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                assert n.func.id not in {"open", "print", "input", "exec", "eval", "__import__"}

    def test_no_float_equality_on_ratios(self):
        # §4.3：模組內不以 == / != 比較浮點量（零判定走 math.isclose 與 <=）
        for n in ast.walk(_TREE):
            if isinstance(n, ast.Compare):
                for op, comp in zip(n.ops, n.comparators):
                    if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comp, ast.Constant):
                        assert not isinstance(comp.value, float), ast.dump(n)


# ── 突變防守 ─────────────────────────────────────────────────────────

def _assert_zero_denominator_guard() -> None:
    e = ev(items_over={"revenue": 0.0, "total_assets": 0.0, "current_liabilities": 0.0})
    for n in ("gross_margin_pct", "operating_margin_pct", "net_margin_pct", "cash_ratio_pct",
              "debt_ratio_pct", "current_ratio", "quick_ratio"):
        m = e.metrics[n]
        assert m.status == "unknown" and m.value is None and m.reason_code == "zero_denominator"


def _assert_missing_not_zero_guard() -> None:
    e = ev(drop=("cash", "total_liabilities"))
    for n in ("cash_ratio_pct", "debt_ratio_pct"):
        assert e.metrics[n].status == "unknown" and e.metrics[n].value is None
    assert e.items["cash"] is None


def _assert_nonfinite_not_zero_guard() -> None:
    e = ev(items_over={"cash": float("nan"), "total_liabilities": float("inf")})
    for n in ("cash_ratio_pct", "debt_ratio_pct"):
        assert e.metrics[n].status == "unknown" and e.metrics[n].value is None
        assert e.metrics[n].reason_code == "non_finite_input"


def _assert_company_gate() -> None:
    for ct in ("financial", "etf"):
        assert all(m.status == "not_applicable" and m.value is None for m in ev(ct).metrics.values())
    assert all(m.status == "unknown" for m in ev("unknown").metrics.values())


def _assert_basis_gate() -> None:
    e = ev(basis=None)
    for n in _FLOW:
        assert e.metrics[n].status == "unknown" and e.metrics[n].value is None
    assert e.metrics["debt_ratio_pct"].status == "ok"


def _assert_no_negative_zero() -> None:
    e = ev(items_over={"gross_profit": -0.0, "operating_income": -1e-9, "cash": -0.0})
    assert math.copysign(1.0, e.items["gross_profit"]) == 1.0
    assert math.copysign(1.0, e.items["cash"]) == 1.0
    for n in ("gross_margin_pct", "operating_margin_pct", "cash_ratio_pct"):
        m = e.metrics[n]
        assert m.status == "ok" and m.value == 0.0
        assert math.copysign(1.0, m.value) == 1.0, n
    assert e.items["operating_income"] == -1e-9           # 微小負值的原值不被改動


def _assert_round_digits_is_four() -> None:
    # 1/3*100 = 33.33333…：第 5 位小數起才與其他位數不同
    v = ev(items_over={"gross_profit": 1.0, "revenue": 3.0}).metrics["gross_margin_pct"].value
    assert v == 33.3333, v
    v2 = ev(items_over={"gross_profit": 2.0, "revenue": 3.0}).metrics["gross_margin_pct"].value
    assert v2 == 66.6667, v2                              # 第 5 位進位


def _assert_true_zero_kept() -> None:
    e = ev(items_over={"total_liabilities": 0.0, "cash": 0.0})
    assert e.metrics["debt_ratio_pct"].status == "ok" and e.metrics["debt_ratio_pct"].value == 0.0
    assert e.metrics["cash_ratio_pct"].status == "ok" and e.metrics["cash_ratio_pct"].value == 0.0


class TestMutationGuards:
    """拔掉防線 → 對應斷言輔助函式必須失敗（AssertionError 或下游數學例外）。"""

    _RED = (AssertionError, ZeroDivisionError)

    def test_baseline_unmutated_passes(self):
        for f in (_assert_zero_denominator_guard, _assert_missing_not_zero_guard,
                  _assert_nonfinite_not_zero_guard, _assert_company_gate,
                  _assert_basis_gate, _assert_true_zero_kept):
            f()

    def test_zero_denominator_check_removed_goes_red(self, monkeypatch):
        monkeypatch.setattr(fhe, "_denominator_reason", lambda d, non_positive_only: None)
        with pytest.raises(self._RED):
            _assert_zero_denominator_guard()

    def test_none_coerced_to_zero_goes_red(self, monkeypatch):
        orig = fhe._normalize_items

        def mutant(items):
            vals, nf = orig(items)
            return {k: (0.0 if v is None else v) for k, v in vals.items()}, set()
        monkeypatch.setattr(fhe, "_normalize_items", mutant)
        with pytest.raises(self._RED):
            _assert_missing_not_zero_guard()

    def test_nonfinite_coerced_to_zero_goes_red(self, monkeypatch):
        orig = fhe._normalize_items

        def mutant(items):
            vals, nf = orig(items)
            return {k: (0.0 if k in nf else v) for k, v in vals.items()}, set()
        monkeypatch.setattr(fhe, "_normalize_items", mutant)
        with pytest.raises(self._RED):
            _assert_nonfinite_not_zero_guard()

    def test_financial_treated_as_general_goes_red(self, monkeypatch):
        monkeypatch.setattr(fhe, "_company_gate", lambda ct: None)
        with pytest.raises(self._RED):
            _assert_company_gate()

    def test_basis_none_still_emits_flow_metrics_goes_red(self, monkeypatch):
        monkeypatch.setattr(fhe, "_basis_gate", lambda spec, basis: None)
        with pytest.raises(self._RED):
            _assert_basis_gate()

    def test_true_zero_treated_as_missing_goes_red(self, monkeypatch):
        orig = fhe._normalize_items

        def mutant(items):
            vals, nf = orig(items)
            return {k: (None if v == 0 else v) for k, v in vals.items()}, nf
        monkeypatch.setattr(fhe, "_normalize_items", mutant)
        with pytest.raises(self._RED):
            _assert_true_zero_kept()

    def test_no_negative_zero_baseline(self):
        _assert_no_negative_zero()

    def test_negative_zero_normalisation_removed_goes_red(self, monkeypatch):
        monkeypatch.setattr(fhe, "_pos_zero", lambda x: x)
        with pytest.raises(self._RED):
            _assert_no_negative_zero()

    def test_round_digits_pinned_to_four(self):
        assert fhe.ROUND_DIGITS == 4
        _assert_round_digits_is_four()

    @pytest.mark.parametrize("digits", [1, 8])
    def test_round_digits_changed_goes_red(self, monkeypatch, digits):
        monkeypatch.setattr(fhe, "ROUND_DIGITS", digits)
        with pytest.raises(self._RED):
            _assert_round_digits_is_four()

    def test_zero_denominator_never_becomes_zero_or_inf(self):
        e = ev(items_over={"revenue": 0.0})
        for n in ("gross_margin_pct", "operating_margin_pct", "net_margin_pct"):
            v = e.metrics[n].value
            assert v is None and v != 0 and v != math.inf
