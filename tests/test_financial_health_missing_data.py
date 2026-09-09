# -*- coding: utf-8 -*-
"""P0 回歸守衛：**半份財報不得產出結論**（CLAUDE.md §1 Fail Loud, Never Fake）。

被守住的那條鏈（2026-09-09 修）::

    損益表沒回來 → fetcher 把該表所有欄位寫成 0
      → financial_health_engine: `fd.get("營業收入(千)", 0) or 0` → rev = 0
      → om = 0 → Core_Business_Profitable = "No"
      → 畫面寫「本業虧損」；no_ai_overall_verdict 算成一項 Fail → 體質 C 級

**一份沒回來的損益表，被講成一家虧錢的公司** —— 而使用者可能拿它去交易。

三種輸入必須**分開斷言**（`get(k, 0) or 0` 正是把它們壓成同一個 0 的元凶）：
  (a) key 根本不存在、(b) 值是 `None`、(c) 值**真的**是 0。

⚠️ **鏡像失效模式也要守**：把「本業虧損」改成 N/A 之後，`fail_items` 會變空，
同一份半份財報會從「C 級」翻成「🟢 印鈔機！A+ 型企業」——
**假的正結論跟假的負結論一樣危險，而且更容易讓人買進。**

──────────────────────────────────────────────────────────────────
**P0-B（2026-09-09，見【7】）**：獨立 QA 抓出同一個病在**另外兩張表**上還活著 ——
資產負債表缺 → 兩張假的及格證 → A+「印鈔機」；現金流量表缺 → 100-100-10 三個
「0.0%」→ grade C →「🔴 建議換出」。並確認 `FIELD_ABSENT` 在現行 fetcher 契約下
恆不觸發（`_v()` 查無回 `0.0`），production 的守衛一律改走領域規則。
"""
from __future__ import annotations

import sys
import types

import pytest

# ── Minimal Streamlit stub（同 tests/test_financial_health_engine.py）───────
_st = types.ModuleType("streamlit")
_st.cache_data = lambda **kw: (lambda f: f)
_st.secrets = {}
sys.modules.setdefault("streamlit", _st)

from shared.colors import TRAFFIC_NEUTRAL, TRAFFIC_RED  # noqa: E402
from src.services import financial_health_engine as FHE  # noqa: E402

_prof_of = lambda fd: FHE._no_ai_profitability(fd)["Profitability_Module"]  # noqa: E731


# ══════════════════════════════════════════════════════════════════
# fixtures：資產負債表 + 現金流量表**都在**，只有損益表沒回來
# ══════════════════════════════════════════════════════════════════
#: 非損益表的欄位（BS + CF）—— 這一半**有回來**。
BALANCE_AND_CASHFLOW: dict = {
    "現金佔總資產(%)": 18.0, "負債比率(%)": 42.0, "OCF(千)": 1_200_000,
    "總資產(千)": 5_000_000, "總負債(千)": 2_100_000,
    "流動資產(千)": 3_000_000, "流動負債(千)": 900_000,
    "股東權益(千)": 2_900_000, "非流動負債(千)": 1_200_000,
    "存貨(千)": 400_000, "存貨前期(千)": 380_000,
    "固定資產(千)": 1_500_000, "長期投資(千)": 200_000,
    "資本支出(千)": 300_000, "現金股利(千)": 100_000,
    "應收帳款天數": 45.0, "應付帳款天數": 60.0,
    "OCF符號": "正", "ICF符號": "負", "籌資CF符號": "負", "is_finance": False,
}

#: 損益表六欄，**全部有值**（對照組）。
INCOME_OK: dict = {
    "毛利率(%)": 45.0, "營業收入(千)": 1_000_000, "毛利(千)": 450_000,
    "營業利益(千)": 250_000, "稅後淨利(千)": 200_000, "營業成本(千)": 550_000,
}

#: (c) 值**真的**是 0 —— 這正是 production 的形狀：
#: `financial_statements_fetcher._v()` 查無回 `0.0`，於是整張損益表變成一排 0。
INCOME_ALL_ZERO: dict = dict.fromkeys(INCOME_OK, 0)

#: (b) 值是 `None`（呼叫端自組 dict、或上游明確標「沒有」）。
INCOME_NONE: dict = {**INCOME_OK, "營業收入(千)": None}


def _fd(*parts: dict) -> dict:
    _out: dict = {}
    for _p in parts:
        _out.update(_p)
    return _out


#: 三種缺法 —— **必須分開跑**，不可合併成一個 case
#: （`get(k, 0) or 0` 的罪狀就是把它們合併）。
#: 這一組斷言的是「**吃營收的指標**一律未評估」。
REV_MISSING_CASES: list = [
    pytest.param(_fd(BALANCE_AND_CASHFLOW), id="a-key不存在"),
    pytest.param(_fd(BALANCE_AND_CASHFLOW, INCOME_NONE), id="b-值是None"),
    pytest.param(_fd(BALANCE_AND_CASHFLOW, INCOME_ALL_ZERO), id="c-值真的是0"),
]

#: **整張損益表**都沒回來（production 真形狀 ＋ key 全缺）。
#: ⚠️ 與上面那組的差別很重要：`INCOME_NONE` 只有**營收**是 None，
#: 毛利率 45%／營業成本 55 萬**是真的在手上** —— 那幾格必須照常顯示
#: （一格壞不得把旁邊染色）。把它混進「整張表都缺」會測出假的期待。
WHOLE_IS_MISSING_CASES: list = [
    pytest.param(_fd(BALANCE_AND_CASHFLOW), id="a-key不存在"),
    pytest.param(_fd(BALANCE_AND_CASHFLOW, INCOME_ALL_ZERO), id="c-值真的是0"),
]

#: 吃營收當分母／分子的四項（毛利率不吃 —— 它是自帶百分比的獨立欄位）。
REV_DEPENDENT: tuple = ("Operating_Margin", "Margin_Of_Safety",
                        "Net_Margin", "ROE")


# ══════════════════════════════════════════════════════════════════
# 【1】`_read()` —— 三態本身
# ══════════════════════════════════════════════════════════════════
class TestReadThreeStates:
    """`get(k, 0) or 0` 把三件事壓成一個 0；`_read()` 必須把它們分開。"""

    def test_absent_key(self):
        assert FHE._read({}, "營業收入(千)") == (0.0, FHE.FIELD_ABSENT)

    def test_none_value(self):
        assert FHE._read({"x": None}, "x") == (0.0, FHE.FIELD_ABSENT)

    def test_real_zero_is_not_absent(self):
        """**這一條是整個修法的支點**：真的是 0 ≠ 沒有資料。"""
        _v, _s = FHE._read({"x": 0}, "x")
        assert (_v, _s) == (0.0, FHE.FIELD_ZERO)
        assert _s != FHE.FIELD_ABSENT

    def test_real_value(self):
        assert FHE._read({"x": 12.5}, "x") == (12.5, FHE.FIELD_VALUE)

    def test_negative_value_is_a_real_observation(self):
        """負的營業利益是**真的虧損**，不是缺值 —— 不可以被一起藏掉。"""
        assert FHE._read({"x": -3.0}, "x") == (-3.0, FHE.FIELD_VALUE)

    @pytest.mark.parametrize("bad", ["", "abc", float("nan"), True, False, []])
    def test_unparseable_is_absent_not_zero(self, bad):
        assert FHE._read({"x": bad}, "x")[1] == FHE.FIELD_ABSENT


# ══════════════════════════════════════════════════════════════════
# 【2】獲利能力：缺營收 → 五項「未評估」，**不得**回 0 / 不得下負面結論
# ══════════════════════════════════════════════════════════════════
class TestProfitabilityNeverFabricates:

    @pytest.mark.parametrize("fin", REV_MISSING_CASES)
    def test_never_claims_core_business_is_losing_money(self, fin):
        """P0 本體：缺營收**絕對不可以**得到「本業虧損」。"""
        _cbp = _prof_of(fin)["Operating_Margin"]["Core_Business_Profitable"]
        assert _cbp == "N/A", f"缺營收卻判了 {_cbp!r} —— 那是拿缺值下結論"
        assert _cbp != "No"

    @pytest.mark.parametrize("fin", REV_MISSING_CASES)
    def test_revenue_dependent_metrics_are_unevaluated(self, fin):
        _p = _prof_of(fin)
        for _k in REV_DEPENDENT:
            assert "N/A" in _p[_k]["Value"], f"{_k} 沒有標成未評估：{_p[_k]}"
            assert _p[_k]["Value"] != "0.0%"

    @pytest.mark.parametrize("fin", WHOLE_IS_MISSING_CASES)
    def test_whole_statement_missing_leaves_all_five_unevaluated(self, fin):
        _p = _prof_of(fin)
        for _k in ("Gross_Margin", *REV_DEPENDENT):
            assert "N/A" in _p[_k]["Value"], f"{_k} 沒有標成未評估：{_p[_k]}"

    def test_only_revenue_missing_does_not_dim_its_neighbours(self):
        """只有營收那一格是 None → **毛利率照常顯示**。

        毛利率是自帶百分比的獨立欄位，不經營收換算。把它一起洗成灰的，
        是**第二種說謊**：數字明明在手上，卻對使用者說沒有。
        """
        _p = _prof_of(_fd(BALANCE_AND_CASHFLOW, INCOME_NONE))
        assert _p["Gross_Margin"] == {"Value": "45.0%", "Status": "Good"}
        assert all("N/A" in _p[_k]["Value"] for _k in REV_DEPENDENT)

    @pytest.mark.parametrize("fin", REV_MISSING_CASES)
    def test_no_zero_percent_anywhere(self, fin):
        """「0% 毛利」是一個**結論**，不是「沒有資料」（線框原話）。"""
        _vals = [_v["Value"] for _v in _prof_of(fin).values()
                 if isinstance(_v, dict) and "Value" in _v]
        assert not [_v for _v in _vals if _v.startswith("0.0")], _vals

    @pytest.mark.parametrize("fin", REV_MISSING_CASES)
    def test_carries_machine_readable_flag(self, fin):
        """§1 三律之(3)：輸出帶旗標，UI 才能講出對的那一句灰態文案。"""
        _gap = _prof_of(fin)["Data_Gap"]
        assert _gap["missing"] == FHE.GAP_INCOME_STATEMENT
        assert _gap["field"] == "營業收入(千)"
        assert _gap["why"]

    def test_absent_and_real_zero_get_different_reasons(self):
        """**分開的是原因，不是結論。**

        兩者都回「未評估」（0 當分母同樣算不出任何一個「率」），
        但 log／旗標上的**原因必須不同** —— 否則「這一輪沒抓到」與
        「上游真的回 0」在事後查不出差別。
        """
        _why_absent = _prof_of(_fd(BALANCE_AND_CASHFLOW))["Data_Gap"]["why"]
        _why_zero = _prof_of(
            _fd(BALANCE_AND_CASHFLOW, INCOME_ALL_ZERO))["Data_Gap"]["why"]
        assert _why_absent != _why_zero
        assert "不存在" in _why_absent
        assert "0" in _why_zero

    def test_logs_loudly(self, capsys):
        """§1 三律之(2)：缺值要**寫 log**，不是安靜地換成 0。"""
        _prof_of(_fd(BALANCE_AND_CASHFLOW, INCOME_ALL_ZERO))
        _out = capsys.readouterr().out
        assert "損益表" in _out and "不以 0 頂替" in _out


class TestRealNumbersAreStillReported:
    """⚠️ 反向守衛：**不可以為了不說謊就變成什麼都不說**。"""

    def test_real_loss_is_still_called_a_loss(self):
        _fin = _fd(BALANCE_AND_CASHFLOW, INCOME_OK,
                   {"營業利益(千)": -50_000, "稅後淨利(千)": -60_000})
        _p = _prof_of(_fin)
        assert _p["Operating_Margin"]["Core_Business_Profitable"] == "No"
        assert _p["Operating_Margin"]["Value"] == "-5.0%"
        assert "Data_Gap" not in _p

    def test_genuine_zero_gross_margin_is_shown(self):
        """毛利率**真的**是 0（毛利＝成本，rev 在手上）→ 照實顯示 0.0%。

        把它也畫成「資料缺漏」是**第二種說謊**：數字明明在手上。
        """
        _fin = _fd(BALANCE_AND_CASHFLOW, INCOME_OK,
                   {"毛利率(%)": 0, "毛利(千)": 0})
        _gm = _prof_of(_fin)["Gross_Margin"]
        assert _gm["Value"] == "0.0%" and _gm["Status"] == "Average"

    def test_full_statements_are_unchanged(self):
        _p = _prof_of(_fd(BALANCE_AND_CASHFLOW, INCOME_OK))
        assert _p["Gross_Margin"] == {"Value": "45.0%", "Status": "Good"}
        assert _p["Operating_Margin"] == {"Value": "25.0%",
                                          "Core_Business_Profitable": "Yes"}
        assert "Data_Gap" not in _p


# ══════════════════════════════════════════════════════════════════
# 【3】只缺損益表、資產負債表在 → **一格壞不得把旁邊染色**
# ══════════════════════════════════════════════════════════════════
class TestOnlyIncomeStatementMissing:

    @pytest.mark.parametrize("fin", REV_MISSING_CASES)
    def test_balance_sheet_metrics_still_conclude(self, fin):
        """負債比／以長支長／流動比率**照常給結論** —— 它們不吃損益表。"""
        _fh = FHE.analyze_financial_health("", "T", fin)
        assert _fh["financial_structure_module"]["Debt_Ratio"]["Status"] == "Pass"
        assert _fh["solvency_module"]["Current_Ratio"]["Status"] == "Pass"
        assert "42.0%" in _fh["financial_structure_module"]["Debt_Ratio"]["Value"]

    @pytest.mark.parametrize("fin", WHOLE_IS_MISSING_CASES)
    def test_operating_metrics_do_not_fake_zero(self, fin):
        """DIO 0 天／翻桌率 0.00x 看起來都像觀測值，其實是分母沒回來。"""
        _o = FHE._no_ai_operating(fin)["Operating_Module"]
        assert "N/A" in _o["Asset_Turnover"] and _o["Asset_Turnover"] != "0.00x"
        assert "N/A" in _o["DIO"]

    @pytest.mark.parametrize("fin", REV_MISSING_CASES)
    def test_advanced_diagnostic_does_not_invent_a_loss(self, fin):
        """缺淨利時不得輸出「⚠️ ROE 為負，本業虧損」這種憑空的看空敘事。"""
        _a = FHE._no_ai_advanced_diagnostic(fin)["Advanced_Diagnostic_Module"]
        assert "虧損" not in _a["DuPont_Health"]
        assert "虧損" not in _a["Earnings_Quality"]["Value"]


# ══════════════════════════════════════════════════════════════════
# 【4】總結論：既不得判 C 級，也不得發 A+（鏡像失效模式）
# ══════════════════════════════════════════════════════════════════
class TestOverallVerdict:

    @staticmethod
    def _verdict(fin: dict) -> dict:
        return FHE.no_ai_overall_verdict(
            fin, FHE.analyze_financial_health("", "T", fin))

    @pytest.mark.parametrize("fin", REV_MISSING_CASES)
    def test_not_downgraded_to_c(self, fin):
        _ov = self._verdict(fin)
        assert _ov["grade"] not in ("C", "F"), _ov["headline"]
        assert "本業獲利" not in _ov["fail_items"]

    @pytest.mark.parametrize("fin", REV_MISSING_CASES)
    def test_not_awarded_a_grade_either(self, fin):
        """半份財報**不得**換到一張體質等級 —— 含 A+。"""
        _ov = self._verdict(fin)
        assert _ov["grade"] == "N/A", f"半份財報被評成 {_ov['grade']}"
        assert _ov["score_pct"] is None
        assert _ov["grade_color"] == TRAFFIC_NEUTRAL
        assert "不評等" in _ov["headline"]
        assert "印鈔機" not in _ov["headline"]

    @pytest.mark.parametrize("fin", REV_MISSING_CASES)
    def test_says_what_is_missing_and_what_still_holds(self, fin):
        _ov = self._verdict(fin)
        assert "損益表" in _ov["comment"]
        assert "不拿 0 頂替" in _ov["comment"] or "不拿 0" in _ov["comment"]

    def test_full_statements_still_graded(self):
        _ov = self._verdict(_fd(BALANCE_AND_CASHFLOW, INCOME_OK))
        assert _ov["grade"] == "A+" and _ov["score_pct"] is not None

    def test_partial_coverage_is_disclosed(self):
        """有評到、但只評到一部分 → 等級照給，但**必須說有幾項沒評到**。"""
        _fin = _fd(BALANCE_AND_CASHFLOW, INCOME_OK, {"應收帳款天數": 0})
        _ov = self._verdict(_fin)
        assert _ov["grade"] != "N/A"
        assert "未評估" in _ov["comment"] and "收現速度" in _ov["comment"]


# ══════════════════════════════════════════════════════════════════
# 【5】新頁3（page_inspect）：灰態要講**客戶核准的那一句**
# ══════════════════════════════════════════════════════════════════
class TestInspectViewGreyCopy:

    @staticmethod
    def _cards(**kw):
        from shared.ui_state import UI_EMPTY
        from src.ui.views import page_inspect as P
        _r = P.ProfitabilityReadout(requested=True, cells=(), **kw)
        _built = P.build_profit_cards(_r)
        assert all(_c.state == UI_EMPTY for _c, _, _ in _built)
        return P, _built

    def test_income_statement_gap_uses_the_approved_wireframe_copy(self):
        _P, _built = self._cards(income_statement_missing=True,
                                 gap_why="損益表這一輪沒有回來（測試）")
        _why = _built[0][0].note.why
        assert _why == _P.PROFIT_GAP_WHY
        # 客戶核准的原文要點，逐項釘住（改寫這句話就會紅）
        assert "只拿到一半的財報" in _why
        assert "損益表這一輪沒有回來" in _why
        assert "不會拿 0 頂替" in _why
        assert "是一個結論" in _why

    def test_plain_field_gap_uses_the_other_copy(self):
        """單一欄位缺 ≠ 整張損益表缺。**共用一句等於對其中一邊說謊。**"""
        _P, _built = self._cards()
        assert _built[0][0].note.why == _P.PROFIT_MISS_WHY
        assert _built[0][0].note.why != _P.PROFIT_GAP_WHY

    def test_grey_never_carries_a_verdict_label(self):
        _P, _built = self._cards(income_statement_missing=True)
        for _card, _, _signal in _built:
            assert _signal == "", "缺值不得帶任何結論標籤"
            assert "虧損" not in (_card.note.now + _card.note.why)

    def test_upstream_reason_is_shown_as_a_fact(self):
        _P, _built = self._cards(income_statement_missing=True,
                                 gap_why="營業收入讀到 0")
        assert dict(_built[0][1])["缺漏原因"] == "營業收入讀到 0"


# ══════════════════════════════════════════════════════════════════
# 【6】舊分頁（section_financial_health）：缺值畫灰，不畫紅
# ══════════════════════════════════════════════════════════════════
class _FakeCol:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _FakeSt:
    """只夠 `_render_profitability_module` 跑起來的 streamlit 替身。"""

    def __init__(self):
        self.html: list[str] = []

    def markdown(self, body, **_kw):
        self.html.append(str(body))

    def caption(self, body, **_kw):
        self.html.append(str(body))

    def columns(self, n, **_kw):
        return [_FakeCol() for _ in range(n)]


class TestOldPageGreyNotRed:

    @staticmethod
    def _render(fin: dict, monkeypatch) -> str:
        from src.ui.tabs.stock_grp_sections import section_financial_health as S
        _fake = _FakeSt()
        monkeypatch.setattr(S, "st", _fake, raising=True)
        S._render_profitability_module(
            {"profitability_module":
             FHE._no_ai_profitability(fin)["Profitability_Module"]})
        return "\n".join(_fake.html)

    def test_is_missing_helper(self):
        from src.ui.tabs.stock_grp_sections import section_financial_health as S
        assert S._is_missing("N/A (損益表缺漏)")
        assert S._is_missing("") and S._is_missing(None)
        assert not S._is_missing("0.0%")   # 真的是 0 → **不是**缺值

    @pytest.mark.parametrize("fin", REV_MISSING_CASES)
    def test_missing_cards_are_neutral_and_never_say_loss(self, fin, monkeypatch):
        _html = self._render(fin, monkeypatch)
        assert TRAFFIC_NEUTRAL in _html, "缺值卡沒有畫成灰態"
        assert TRAFFIC_RED not in _html, "缺值被畫成紅色的故障／負面結論"
        assert "本業虧損" not in _html
        assert "辛苦" not in _html

    def test_real_loss_still_renders_red(self, monkeypatch):
        """反向守衛：真的虧損仍要是紅的 ——**不可以整片洗成灰**。"""
        _html = self._render(
            _fd(BALANCE_AND_CASHFLOW, INCOME_OK,
                {"營業利益(千)": -50_000, "稅後淨利(千)": -60_000}), monkeypatch)
        assert TRAFFIC_RED in _html and "本業虧損❌" in _html


# ══════════════════════════════════════════════════════════════════
# 【7】P0-B（2026-09-09）：同一個病在**另外兩張表**上還活著
# ══════════════════════════════════════════════════════════════════
# P0 只修好「損益表沒回來」那一條路。獨立 QA 抓出：
#   ① 資產負債表整張沒回來 → `cl == 0` 換到「Pass (無短期債務)」、
#      `ppe == 0` 換到「Pass (輕資產)」 —— **一張沒回來的表換到兩張及格證**，
#      總評被推到 A+「印鈔機」。**假的正結論比假的負結論更容易讓人買進。**
#   ② 現金流量表整張沒回來 → 100-100-10 三項算成「0.0%」→ Fail → grade C
#      →`dividend_station` 據此輸出「🔴 建議換出」。而**同一份輸出**裡
#      盈餘含金量已經正確地說「N/A (現金流量表缺漏)」—— 自相矛盾。
#   ③ `FIELD_ABSENT` 在現行 fetcher 契約下恆不觸發（`_v()` 查無回 0.0）。
#
# ⚠️ **兩個方向都要守**：缺值不得產出假的**負**結論，也不得產出假的**正**結論。

#: 資產負債表六欄以外的另外兩張表（IS + CF）—— 這兩張**有回來**。
INCOME_AND_CASHFLOW: dict = {
    **INCOME_OK,
    "OCF(千)": 1_200_000, "資本支出(千)": 300_000, "現金股利(千)": 100_000,
    "OCF符號": "正", "ICF符號": "負", "籌資CF符號": "負", "is_finance": False,
}

#: 資產負債表本身（對照組）。
BALANCE_ONLY: dict = {
    "現金佔總資產(%)": 18.0, "負債比率(%)": 42.0,
    "總資產(千)": 5_000_000, "總負債(千)": 2_100_000,
    "流動資產(千)": 3_000_000, "流動負債(千)": 900_000,
    "股東權益(千)": 2_900_000, "非流動負債(千)": 1_200_000,
    "存貨(千)": 400_000, "存貨前期(千)": 380_000,
    "固定資產(千)": 1_500_000, "長期投資(千)": 200_000,
    "應收帳款天數": 45.0, "應付帳款天數": 60.0,
}

#: production 真形狀：整張表沒回來 → 該表所有欄位一起變 0（`_v()` 回 0.0）。
BALANCE_ALL_ZERO: dict = dict.fromkeys(BALANCE_ONLY, 0)

#: 現金流量表三欄（對照組）／整張沒回來。
CASHFLOW_OK: dict = {"OCF(千)": 1_200_000, "資本支出(千)": 300_000,
                     "現金股利(千)": 100_000, "OCF符號": "正",
                     "ICF符號": "負", "籌資CF符號": "負"}
CASHFLOW_ALL_ZERO: dict = {"OCF(千)": 0, "資本支出(千)": 0, "現金股利(千)": 0,
                           "OCF符號": "負", "ICF符號": "負", "籌資CF符號": "負"}

#: 三種缺法分開跑（同【2】的理由：`get(k,0) or 0` 的罪狀就是把它們壓成一個 0）。
BS_MISSING_CASES: list = [
    pytest.param(_fd(INCOME_AND_CASHFLOW), id="a-key不存在"),
    pytest.param(_fd(INCOME_AND_CASHFLOW, BALANCE_ALL_ZERO), id="c-值真的是0"),
]
CF_MISSING_CASES: list = [
    pytest.param(_fd({"is_finance": False}, INCOME_OK, BALANCE_ONLY),
                 id="a-key不存在"),
    pytest.param(_fd({"is_finance": False}, INCOME_OK, BALANCE_ONLY,
                     CASHFLOW_ALL_ZERO), id="c-值真的是0"),
]

_FULL: dict = _fd({"is_finance": False}, INCOME_OK, BALANCE_ONLY, CASHFLOW_OK)


def _verdict_of(fin: dict) -> dict:
    return FHE.no_ai_overall_verdict(
        fin, FHE.analyze_financial_health("", "T", fin))


class TestBalanceSheetMissingNeverEarnsAPass:
    """① 資產負債表沒回來 → **不得**換到任何一張及格證。"""

    @pytest.mark.parametrize("fin", BS_MISSING_CASES)
    def test_solvency_is_not_called_debt_free(self, fin):
        """`流動負債 == 0` 是「這張表沒回來」，不是「這家公司沒有短期負債」。"""
        _s = FHE._no_ai_solvency(fin)["Solvency_Module"]
        assert _s["Current_Ratio"]["Status"] == "N/A", _s
        assert _s["Quick_Ratio"]["Status"] == "N/A", _s
        assert _s["Final_Solvency_Verdict"] == "N/A"
        _blob = str(_s)
        assert "無短期債務" not in _blob
        assert "資金壓力極低" not in _blob

    @pytest.mark.parametrize("fin", BS_MISSING_CASES)
    def test_long_term_funding_is_not_called_asset_light(self, fin):
        """`固定資產 == 0` 是那一格沒解析出來，不是「輕資產的好公司」。"""
        _f = FHE._no_ai_financial_structure(fin)["Financial_Structure_Module"]
        assert _f["Long_Term_Funding_Ratio"]["Status"] == "N/A", _f
        assert "輕資產" not in str(_f)

    @pytest.mark.parametrize("fin", BS_MISSING_CASES)
    def test_those_two_never_reach_pass_items_or_score(self, fin):
        """**不得計分、不得進 pass_items**（否則缺值會把等級往上推）。"""
        _ov = _verdict_of(fin)
        assert "流動比率" not in _ov["pass_items"]
        assert "以長支長" not in _ov["pass_items"]

    @pytest.mark.parametrize("fin", BS_MISSING_CASES)
    def test_no_grade_is_issued_at_all(self, fin):
        """**方向一：不得產出假的正結論。** 半份財報不得換到 A+「印鈔機」。

        ⚠️ 只把那兩格改成 N/A **不夠**（實測：改完仍是 A+）——
        因為 `fail_items` 一樣是空的，**少評幾項不會讓等級變差，只會變好**。
        gate 必須設在「整張表在不在」。
        """
        _ov = _verdict_of(fin)
        assert _ov["grade"] == "N/A", f"缺整張資產負債表卻評成 {_ov['grade']}"
        assert _ov["score_pct"] is None
        assert _ov["grade_color"] == TRAFFIC_NEUTRAL
        assert "印鈔機" not in _ov["headline"]
        assert "不評等" in _ov["headline"]

    @pytest.mark.parametrize("fin", BS_MISSING_CASES)
    def test_not_downgraded_either(self, fin):
        """**方向二：也不得產出假的負結論。** 不得掉成 C / F。"""
        _ov = _verdict_of(fin)
        assert _ov["grade"] not in ("C", "F"), _ov["headline"]
        assert _ov["fail_items"] == [], _ov["fail_items"]

    @pytest.mark.parametrize("fin", BS_MISSING_CASES)
    def test_says_which_statement_is_missing(self, fin):
        _ov = _verdict_of(fin)
        assert "資產負債表" in _ov["comment"]
        assert "不拿 0 頂替" in _ov["comment"]

    def test_a_missing_numerator_is_not_a_failing_ratio(self):
        """**分子側也要擋。** `流動資產 == 0`（流動負債在）→ `cr = 0.0%`
        → `Fail_Initial`，那是**假的負結論**（資產負債表只解析出一半）。

        ⚠️ 這一條是突變測試 M8 補出來的：只擋分母（cl）時全套件仍全綠 ——
        **沒有測試守住的修復，等於沒有修**（CLAUDE.md §-2 規則 6 / v3 §03-1）。
        """
        _s = FHE._no_ai_solvency(
            {**_FULL, "流動資產(千)": 0})["Solvency_Module"]
        assert _s["Current_Ratio"]["Status"] == "N/A", _s
        assert _s["Current_Ratio"]["Status"] != "Fail_Initial"
        assert _s["Final_Solvency_Verdict"] == "N/A"
        assert FHE.NA_NO_CURRENT_ASSET in _s["Current_Ratio"]["Value"]

    @pytest.mark.parametrize("fin", BS_MISSING_CASES)
    def test_carries_machine_readable_flag(self, fin):
        _f = FHE._no_ai_financial_structure(fin)["Financial_Structure_Module"]
        assert _f["Data_Gap"]["missing"] == FHE.GAP_BALANCE_SHEET
        assert _f["Data_Gap"]["field"] == "總資產(千)"
        assert _f["Data_Gap"]["why"]


class TestCashFlowMissingIsNotAFailedRule:
    """② 現金流量表沒回來 → 100-100-10 未評估，**不是三個 0.0% 的 Fail**。"""

    @staticmethod
    def _rule(fin: dict) -> dict:
        return FHE._no_ai_survival(fin)["Survival_Module"]["Rule_100_100_10"]

    @pytest.mark.parametrize("fin", CF_MISSING_CASES)
    def test_three_cells_are_not_zero_percent(self, fin):
        _r = self._rule(fin)
        for _k in ("Cash_Flow_Ratio", "Cash_Flow_Adequacy", "Cash_Reinvestment"):
            assert "N/A" in _r[_k], f"{_k} = {_r[_k]!r}"
            assert not str(_r[_k]).startswith("0.0"), f"{_k} 畫成 0.0% 的結論"

    @pytest.mark.parametrize("fin", CF_MISSING_CASES)
    def test_rule_status_is_unevaluated_not_failed(self, fin):
        assert self._rule(fin)["Status"] == "N/A"

    @pytest.mark.parametrize("fin", CF_MISSING_CASES)
    def test_one_output_does_not_contradict_itself(self, fin):
        """**同一份輸出不得自相矛盾。**

        `_no_ai_advanced_diagnostic` 對同一個 `OCF == 0` 早就正確回
        「N/A (現金流量表缺漏)」，正上方的 100-100-10 卻說「0.0% Fail」。
        同一個 0 不能有兩種讀法（§2.1 SSOT）。
        """
        _fh = FHE.analyze_financial_health("", "T", fin)
        _eq = _fh["advanced_diagnostic_module"]["Earnings_Quality"]
        _rule = _fh["survival_module"]["Rule_100_100_10"]
        assert _eq["Status"] == "N/A" and _rule["Status"] == "N/A"
        assert FHE.NA_NO_CASHFLOW in _eq["Value"]
        assert FHE.NA_NO_CASHFLOW in _rule["Cash_Flow_Ratio"]

    @pytest.mark.parametrize("fin", CF_MISSING_CASES)
    def test_no_sell_signal_from_a_missing_statement(self, fin):
        """**方向二：假的負結論。** grade C/F 會變成「🔴 建議換出」。"""
        _ov = _verdict_of(fin)
        assert _ov["grade"] not in ("C", "F"), _ov["headline"]
        assert "100-100-10" not in _ov["fail_items"]
        assert "盈餘含金量" not in _ov["fail_items"]

    @pytest.mark.parametrize("fin", CF_MISSING_CASES)
    def test_but_does_not_hand_out_a_pass_either(self, fin):
        """**方向一：假的正結論。** 未評估的兩項不得進 pass_items。"""
        _ov = _verdict_of(fin)
        assert "100-100-10" not in _ov["pass_items"]
        assert "盈餘含金量" not in _ov["pass_items"]
        assert "未評估" in _ov["comment"]

    @pytest.mark.parametrize("fin", CF_MISSING_CASES)
    def test_carries_machine_readable_flag(self, fin):
        """§1 三律之(3)：輸出帶旗標，UI 才畫得出對的那一句灰態文案。"""
        _s = FHE._no_ai_survival(fin)["Survival_Module"]
        assert _s["Data_Gap"]["missing"] == FHE.GAP_CASH_FLOW
        assert _s["Data_Gap"]["field"] == "OCF(千)"
        assert _s["Data_Gap"]["why"]

    def test_no_flag_when_the_statement_is_there(self):
        """反向：現金流量表在 → **不得**掛旗標（否則全站永遠灰）。"""
        assert "Data_Gap" not in FHE._no_ai_survival(_FULL)["Survival_Module"]

    def test_all_three_na_is_not_a_pass(self):
        """三項全 N/A ＝ 零筆資料，**不得**開一張 100-100-10 及格證。"""
        _r = self._rule(_fd({"is_finance": False}, INCOME_OK))
        assert _r["Status"] == "N/A"
        assert "單季估算" not in _r["Insight"]


class TestImpossibleZerosAreTreatedAsGaps:
    """③ 領域規則要**真的會觸發** —— `FIELD_ABSENT` 在 production 恆為 False。"""

    @staticmethod
    def _prof(**over) -> dict:
        return _prof_of({**_FULL, **over})

    def test_zero_operating_income_is_not_a_loss(self):
        """`營業利益 == 0`（rev 在手上）＝ 那一列沒解析出來，不是「本業虧損」。

        這正是 P0 修好的那條鏈換一個欄位重演：原式寫
        `oi_state == FIELD_ABSENT`，而 fetcher 查無回 `0.0` → 恆為 False。
        """
        _om = self._prof(**{"營業利益(千)": 0})["Operating_Margin"]
        assert _om["Core_Business_Profitable"] == "N/A", _om
        assert _om["Core_Business_Profitable"] != "No"
        assert not _om["Value"].startswith("0.0")

    def test_zero_net_income_is_not_a_zero_margin(self):
        _nm = self._prof(**{"稅後淨利(千)": 0})["Net_Margin"]
        assert _nm["Status"] == "N/A" and not _nm["Value"].startswith("0.0")

    def test_zero_operating_income_blanks_margin_of_safety(self):
        _mos = self._prof(**{"營業利益(千)": 0})["Margin_Of_Safety"]
        assert _mos["Status"] == "N/A"

    def test_zero_net_income_blanks_roe_and_dupont(self):
        _fin = {**_FULL, "稅後淨利(千)": 0}
        assert "N/A" in _prof_of(_fin)["ROE"]["Value"]
        _a = FHE._no_ai_advanced_diagnostic(_fin)["Advanced_Diagnostic_Module"]
        assert "虧損" not in _a["DuPont_Health"]
        assert "虧損" not in _a["Earnings_Quality"]["Value"]

    # ── 反向守衛：**真的**虧損／真的難看的數字仍要照實下結論 ──────
    def test_a_real_loss_is_still_a_loss(self):
        _p = self._prof(**{"營業利益(千)": -50_000, "稅後淨利(千)": -60_000})
        assert _p["Operating_Margin"]["Core_Business_Profitable"] == "No"
        assert _p["Operating_Margin"]["Value"] == "-5.0%"
        assert _p["Net_Margin"]["Status"] == "Loss"

    def test_a_real_zero_inventory_is_still_zero_days(self):
        """存貨真的是 0（純服務業）是**真實觀測** —— 不可以一起洗成灰。"""
        _o = FHE._no_ai_operating({**_FULL, "存貨(千)": 0})["Operating_Module"]
        assert _o["DIO"] == "0.0 天"


class TestRealNumbersStillConclude:
    """⚠️ 反向總守衛：**不可以為了不說謊就變成什麼都不說。**"""

    def test_full_statements_are_unchanged(self):
        _ov = _verdict_of(_FULL)
        assert _ov["grade"] == "A+" and _ov["score_pct"] is not None
        assert "以長支長" in _ov["pass_items"]
        assert "流動比率" in _ov["pass_items"]
        assert "100-100-10" in _ov["pass_items"]

    def test_a_genuinely_weak_balance_sheet_still_fails(self):
        """流動負債**真的**很大 → 流動比率照樣 Fail_Initial，不因本次改動變 N/A。"""
        _s = FHE._no_ai_solvency({**_FULL, "流動負債(千)": 5_000_000})
        _m = _s["Solvency_Module"]
        assert _m["Current_Ratio"]["Status"] == "Fail_Initial"
        assert _m["Final_Solvency_Verdict"] == "Fail"

    def test_a_genuinely_short_funded_company_still_fails(self):
        """以長支長**真的**不足 → 照樣 Fail。"""
        _f = FHE._no_ai_financial_structure(
            {**_FULL, "固定資產(千)": 90_000_000})["Financial_Structure_Module"]
        assert _f["Long_Term_Funding_Ratio"]["Status"] == "Fail"

    def test_a_genuinely_bad_cash_flow_still_fails(self):
        """OCF **真的**很小（非 0）→ 100-100-10 照樣 Fail。"""
        _r = FHE._no_ai_survival(
            {**_FULL, "OCF(千)": 1_000})["Survival_Module"]["Rule_100_100_10"]
        assert _r["Status"] == "Fail"

    def test_a_genuinely_bad_company_is_still_downgraded(self):
        _ov = _verdict_of({**_FULL, "OCF(千)": 1_000, "固定資產(千)": 90_000_000,
                           "流動負債(千)": 5_000_000, "負債比率(%)": 85.0})
        assert _ov["grade"] in ("C", "F"), _ov["headline"]
        assert _ov["fail_items"]

    def test_the_dead_score_key_is_never_produced(self):
        """`_pts` 的 `"Pass (無短期債務)"` 已移除 —— 沒有任何路徑再產出它。"""
        for _fin in (_FULL, _fd(INCOME_AND_CASHFLOW),
                     _fd({"is_finance": False}, INCOME_OK, BALANCE_ONLY)):
            _fh = FHE.analyze_financial_health("", "T", _fin)
            assert "Pass (無短期債務)" not in str(_fh)
