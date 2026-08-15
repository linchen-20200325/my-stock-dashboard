"""T2(2026-08)— 投組產業集中度 L2 純函式測試。

受測模組：`src/compute/risk/concentration.py`

測試設計原則
────────────
1. **浮點一律用 `math.isclose`，禁止 `==`**（CLAUDE.md §4.3）。
2. **每個邊界都斷言「不是 0」而不只是「不炸」** —— 本模組最危險的失效模式
   不是拋例外，是把「算不出來」渲染成「完美分散」（§1）。
3. Property-based 不引入 hypothesis（避免新依賴），改以構造式列舉：
   對一組涵蓋各種形狀的投組，驗證數學不變量恆成立。

§6 要求的「3 個最容易讓這段程式出錯的輸入」
──────────────────────────────────────────
① 全部同一產業      → HHI=1、n_eff=1；若程式對 1/HHI 沒 guard 而 HHI 浮點成 0 → 除零
② 產業名含全形/空白 → 同一產業被拆兩類 → 集中度**被低估**（偏誤方向是危險的那邊）
③ 空投組 / 全未分類 → 分母為 0；若回 hhi=0 會被畫面顯示成「完美分散」= 最糟的假訊號
三者各有獨立 test class，見下方 `TestErrorProne*`。
"""

from __future__ import annotations

import math

import pytest

from src.compute.risk.concentration import (
    BASIS_EQUAL_WEIGHT,
    ConcentrationResult,
    compute_industry_concentration,
    normalize_industry_name,
)


# ════════════════════════════════════════════════════════════════════
# 1. 名稱正規化
# ════════════════════════════════════════════════════════════════════
class TestNormalizeIndustryName:

    @pytest.mark.parametrize("raw", [None, "", "   ", "\t\n", 123, 4.5, float("nan"), [], {}])
    def test_invalid_becomes_none(self, raw):
        """None / 空白 / 非字串 一律「未分類」。

        特別注意 `float('nan')`：pandas 缺值常以 NaN 出現，若被 `str()` 硬轉
        會變成產業別 `'nan'` —— 那就憑空多出一個叫 nan 的產業（§1 捏造）。
        """
        assert normalize_industry_name(raw) is None

    def test_strips_and_collapses_whitespace(self):
        assert normalize_industry_name("  半導體  ") == "半導體"
        assert normalize_industry_name("電子 　 零組件") == "電子 零組件"

    def test_nfkc_folds_fullwidth(self):
        """全形英數 → 半形。FinMind 與 TWSE openapi 兩源寫法可能不同。"""
        assert normalize_industry_name("ＩＣ設計") == normalize_industry_name("IC設計")

    def test_normalization_is_idempotent(self):
        """正規化兩次結果不變（§5 冪等性）。"""
        for _raw in ("  半導體 ", "ＩＣ設計", "電子 　零組件"):
            _once = normalize_industry_name(_raw)
            assert normalize_industry_name(_once) == _once


# ════════════════════════════════════════════════════════════════════
# 2. §6「3 個最容易出錯的輸入」
# ════════════════════════════════════════════════════════════════════
class TestErrorProne1_AllSameIndustry:
    """① 全押同一產業 —— 除零風險最高的路徑。"""

    def test_hhi_and_neff_are_exactly_one(self):
        _r = compute_industry_concentration({f"{i}": "半導體" for i in range(10)})
        assert _r.is_computable
        assert math.isclose(_r.hhi, 1.0, rel_tol=1e-12)
        assert math.isclose(_r.n_eff, 1.0, rel_tol=1e-12)
        assert math.isclose(_r.top1_pct, 100.0, rel_tol=1e-12)
        assert _r.n_industries == 1

    def test_neff_is_finite(self):
        """1/HHI 必須是有限數，不得為 inf / nan。"""
        _r = compute_industry_concentration({"2330": "半導體"})
        assert _r.n_eff is not None and math.isfinite(_r.n_eff)


class TestErrorProne2_NameVariants:
    """② 名稱變體 —— 若未正規化會**低估**集中度（危險方向）。"""

    def test_variants_collapse_into_one_industry(self):
        _r = compute_industry_concentration({
            "2330": "半導體",
            "2454": " 半導體",      # 前導空白
            "3034": "半導體 ",      # 尾隨空白
            "2379": "半　導體",     # 全形空白 → NFKC 後成半形空格
        })
        # 前三檔必為同一類；第四檔含內部空白，正規化後是「半 導體」屬另一類。
        # 這裡斷言的是「空白變體不會製造假分散」，而非把所有變體都硬併。
        assert _r.counts["半導體"] == 3, f"空白變體未收斂：{_r.counts}"

    def test_unnormalized_would_understate_concentration(self):
        """對照組：證明正規化確實提高了偵測到的集中度。"""
        _with_variants = compute_industry_concentration({
            "a": "半導體", "b": " 半導體", "c": "半導體 ",
        })
        _clean = compute_industry_concentration({
            "a": "半導體", "b": "半導體", "c": "半導體",
        })
        assert math.isclose(_with_variants.hhi, _clean.hhi, rel_tol=1e-12), (
            "空白變體讓 HHI 與乾淨輸入不一致 → 集中度被低估"
        )


class TestErrorProne3_EmptyAndUnclassified:
    """③ 空投組 / 全未分類 —— 絕不可回 0（0 會被渲染成「完美分散」）。"""

    def test_empty_portfolio(self):
        _r = compute_industry_concentration({})
        assert _r.n_total == 0
        assert not _r.is_computable
        assert _r.hhi is None and _r.n_eff is None, (
            "空投組回了數值 —— 畫面會顯示成一個看似有效的集中度"
        )
        assert _r.top1_pct is None and _r.top3_pct is None

    def test_all_unclassified(self):
        _r = compute_industry_concentration({"2330": None, "2454": "", "3034": "  "})
        assert _r.n_total == 3
        assert _r.n_classified == 0
        assert _r.n_unclassified == 3
        assert not _r.is_computable
        assert _r.hhi is None, "全未分類卻回了 HHI —— 那是無中生有"
        assert math.isclose(_r.coverage_pct, 0.0, abs_tol=1e-12)

    def test_hhi_is_never_zero_when_computable(self):
        """可計算時 HHI 必 > 0 —— 0 是「不知道」的偽裝值，不該出現。"""
        for _case in (
            {"a": "X"},
            {"a": "X", "b": "Y"},
            {"a": "X", "b": "Y", "c": "Z", "d": None},
        ):
            _r = compute_industry_concentration(_case)
            assert _r.is_computable and _r.hhi > 0.0


# ════════════════════════════════════════════════════════════════════
# 3. 數學正確性（手算對照 = golden test）
# ════════════════════════════════════════════════════════════════════
class TestMath:

    def test_known_case_6_semi_4_others(self):
        """10 檔：6 半導體 + 4 檔各自不同產業。

        手算：w = [0.6, 0.1, 0.1, 0.1, 0.1]
              HHI  = 0.36 + 4×0.01 = 0.40
              Neff = 1 / 0.40 = 2.5
              Top1 = 60%，Top3 = 60 + 10 + 10 = 80%
        """
        _p = {f"s{i}": "半導體" for i in range(6)}
        _p.update({"a": "金融", "b": "航運", "c": "鋼鐵", "d": "食品"})
        _r = compute_industry_concentration(_p)

        assert _r.n_total == 10 and _r.n_classified == 10 and _r.n_industries == 5
        assert math.isclose(_r.hhi, 0.40, rel_tol=1e-12)
        assert math.isclose(_r.n_eff, 2.5, rel_tol=1e-12)
        assert math.isclose(_r.top1_pct, 60.0, rel_tol=1e-12)
        assert math.isclose(_r.top3_pct, 80.0, rel_tol=1e-12)

    def test_perfectly_diversified(self):
        """K 類各 1 檔 → HHI = 1/K、Neff = K。"""
        _k = 5
        _r = compute_industry_concentration({f"s{i}": f"ind{i}" for i in range(_k)})
        assert math.isclose(_r.hhi, 1.0 / _k, rel_tol=1e-12)
        assert math.isclose(_r.n_eff, float(_k), rel_tol=1e-12)

    def test_top3_caps_at_total_when_fewer_than_3_industries(self):
        """產業數 < 3 時，前三大 = 全部 = 100%。"""
        _r = compute_industry_concentration({"a": "X", "b": "Y"})
        assert math.isclose(_r.top3_pct, 100.0, rel_tol=1e-12)

    def test_unclassified_excluded_from_denominator(self):
        """未分類不進分母 —— 4 檔中 2 檔未分類 → 分母是 2 不是 4。"""
        _r = compute_industry_concentration({
            "a": "半導體", "b": "半導體", "c": None, "d": "",
        })
        assert _r.n_classified == 2 and _r.n_unclassified == 2
        assert math.isclose(_r.top1_pct, 100.0, rel_tol=1e-12), (
            "未分類被算進分母了 → 集中度被稀釋"
        )
        assert math.isclose(_r.coverage_pct, 50.0, rel_tol=1e-12)


# ════════════════════════════════════════════════════════════════════
# 4. Property-based（構造式，不引入 hypothesis）
# ════════════════════════════════════════════════════════════════════
_SHAPES = [
    {"a": "X"},
    {"a": "X", "b": "X"},
    {"a": "X", "b": "Y"},
    {"a": "X", "b": "Y", "c": "Y", "d": "Z"},
    {f"s{i}": f"ind{i % 3}" for i in range(11)},
    {f"s{i}": f"ind{i}" for i in range(33)},          # TWSE 產業別約 33 類
    {**{f"s{i}": "半導體" for i in range(20)}, "z": None},
    {**{f"s{i}": f"ind{i % 7}" for i in range(50)}, **{f"u{i}": None for i in range(5)}},
]


@pytest.mark.parametrize("portfolio", _SHAPES)
class TestInvariants:

    def test_weights_sum_to_100(self, portfolio):
        _r = compute_industry_concentration(portfolio)
        assert math.isclose(sum(_r.weights_pct.values()), 100.0, rel_tol=1e-9)

    def test_hhi_within_bounds(self, portfolio):
        """1/K ≤ HHI ≤ 1（K = 相異產業數）。"""
        _r = compute_industry_concentration(portfolio)
        _lo = 1.0 / _r.n_industries
        assert _lo - 1e-12 <= _r.hhi <= 1.0 + 1e-12, (
            f"HHI={_r.hhi} 超出 [{_lo}, 1]"
        )

    def test_neff_within_bounds(self, portfolio):
        """1 ≤ Neff ≤ K。"""
        _r = compute_industry_concentration(portfolio)
        assert 1.0 - 1e-9 <= _r.n_eff <= _r.n_industries + 1e-9

    def test_counts_sum_to_classified(self, portfolio):
        _r = compute_industry_concentration(portfolio)
        assert sum(_r.counts.values()) == _r.n_classified
        assert _r.n_classified + _r.n_unclassified == _r.n_total

    def test_ordering_is_descending(self, portfolio):
        """weights_pct / counts 必須由大到小 —— UI 直接依序取前 N 大。"""
        _vals = list(compute_industry_concentration(portfolio).counts.values())
        assert _vals == sorted(_vals, reverse=True)

    def test_top1_equals_max_weight(self, portfolio):
        _r = compute_industry_concentration(portfolio)
        assert math.isclose(_r.top1_pct, max(_r.weights_pct.values()), rel_tol=1e-12)

    def test_deterministic(self, portfolio):
        """同輸入必得同結果（§5 冪等性）—— 含 tie-break 的排序穩定性。"""
        _a = compute_industry_concentration(portfolio)
        _b = compute_industry_concentration(dict(reversed(list(portfolio.items()))))
        assert list(_a.counts.items()) == list(_b.counts.items()), (
            "輸入順序改變導致輸出順序改變 → 排序 tie-break 不穩定"
        )
        assert math.isclose(_a.hhi, _b.hhi, rel_tol=1e-12)


# ════════════════════════════════════════════════════════════════════
# 5. 契約：等權假設不得隱形
# ════════════════════════════════════════════════════════════════════
class TestHonestyContract:

    def test_basis_is_declared(self):
        """回傳物件必須自報權重基礎，UI 才有東西可標註。

        個股組合沒有張數資料（gsheet_portfolio.py:60 只存三欄），
        集中度必然建立在等權假設上。若這個假設沒被帶到畫面，
        使用者會誤以為那是他的真實部位集中度（§1）。
        """
        _r = compute_industry_concentration({"a": "X", "b": "Y"})
        assert _r.basis == BASIS_EQUAL_WEIGHT

    def test_result_is_frozen(self):
        """結果不可變 —— 防止 UI 層就地竄改後再傳給別處。"""
        _r = compute_industry_concentration({"a": "X"})
        with pytest.raises(Exception):
            _r.hhi = 0.5  # type: ignore[misc]

    def test_no_io_imports(self):
        """L2 純函式守衛：本模組不得 import 任何 I/O 或 UI 套件（§8.2）。

        `test_c3_layering_guard.py` 已涵蓋全 repo 掃描，這裡再釘一次是因為
        本模組**最容易**被後人「順手加個 fetch 進去」—— 產業別就在隔壁 L1。

        ⚠️ **走 AST 而非字串比對**：本模組的 docstring 為了說明資料從哪來，
        本來就會提到 `src.data.core.data_loader` 之類的字樣；字串掃描 =
        保證假紅燈。同 `test_f2_app_decomposition.py` 設計原則 #2。
        """
        import ast
        import src.compute.risk.concentration as _m

        assert _m.__file__ is not None
        _tree = ast.parse(open(_m.__file__, encoding="utf-8").read())

        _imported: set[str] = set()
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.Import):
                _imported.update(a.name for a in _n.names)
            elif isinstance(_n, ast.ImportFrom) and _n.module:
                _imported.add(_n.module)

        _banned_prefixes = ("requests", "streamlit", "yfinance", "FinMind", "src.data", "src.ui")
        _hits = sorted(
            _mod for _mod in _imported
            if any(_mod == _p or _mod.startswith(_p + ".") for _p in _banned_prefixes)
        )
        assert not _hits, (
            f"L2 純函式出現 I/O 或 UI import：{_hits}\n"
            "→ 產業別必須由 caller（L3）查好再傳入，本模組不得自己抓資料。"
        )


def test_dataclass_is_exported():
    """`ConcentrationResult` 需可被 L3/L5 型別標註引用。"""
    assert ConcentrationResult is not None
