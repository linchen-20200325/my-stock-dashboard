"""v18.280 tests — data_coverage 純函式覆蓋率計算(學 Fund Section ⓪)."""
from __future__ import annotations

import sys
import types


def _stub_st():
    # v18.281 — 不覆蓋既有 test stub(避免污染其他 test 檔的完整 stub)
    _existing = sys.modules.get("streamlit")
    if _existing is not None and (getattr(_existing, "_stub", False)
                                  or getattr(_existing, "_is_test_stub", False)):
        return
    m = types.ModuleType("streamlit")
    m._stub = True

    class _SS(dict):
        def get(self, k, d=None):
            return super().get(k, d)
    m.session_state = _SS()

    def _noop(*a, **k):
        return None
    for n in ("markdown", "caption"):
        setattr(m, n, _noop)
    sys.modules["streamlit"] = m


_stub_st()


class TestComputeTabCoverage:
    def test_empty_state_all_idle(self):
        from data_coverage import compute_tab_coverage
        rows = compute_tab_coverage(state={})
        assert len(rows) == 4
        # 全空 → 全部 ⬜ 未觸發
        assert all(r["emoji"] == "⬜" for r in rows)

    def test_returns_4_tabs(self):
        from data_coverage import compute_tab_coverage
        rows = compute_tab_coverage(state={})
        tabs = [r["tab"] for r in rows]
        assert any("總經" in t for t in tabs)
        assert any("個股" in t for t in tabs)
        assert any("籌碼" in t for t in tabs)
        assert any("ETF" in t for t in tabs)

    def test_each_row_has_required_fields(self):
        from data_coverage import compute_tab_coverage
        for r in compute_tab_coverage(state={}):
            for f in ("tab", "emoji", "color", "ratio_txt", "detail", "action"):
                assert f in r, f"缺欄位 {f}"

    def test_macro_full_coverage_green(self):
        from data_coverage import compute_tab_coverage
        _full_macro = {k: 1.0 for k in
                       ["pmi", "vix", "cpi", "us10y", "dxy", "hy_spread",
                        "yield_10y2y", "m2", "fed_bs", "sahm"]}
        rows = compute_tab_coverage(state={
            "macro_info": _full_macro,
            "m1b_m2_info": {"v": 1},
            "li_latest": {"v": 1},
        })
        macro_row = next(r for r in rows if "總經" in r["tab"])
        assert macro_row["emoji"] == "🟢"

    def test_macro_partial_yellow_or_red(self):
        from data_coverage import compute_tab_coverage
        # 只有 3/12 → 紅
        rows = compute_tab_coverage(state={
            "macro_info": {"pmi": 1, "vix": 1, "cpi": 1},
        })
        macro_row = next(r for r in rows if "總經" in r["tab"])
        assert macro_row["emoji"] == "🔴"

    def test_stock_loaded_green(self):
        from data_coverage import compute_tab_coverage
        rows = compute_tab_coverage(state={"t2_data": {"2330": {}, "2454": {}}})
        stock_row = next(r for r in rows if "個股" in r["tab"])
        assert stock_row["emoji"] == "🟢"
        assert "2" in stock_row["ratio_txt"]

    def test_chips_partial(self):
        from data_coverage import compute_tab_coverage
        rows = compute_tab_coverage(state={
            "cl_data": {"margin": 1, "foreign": 1}  # 2/4
        })
        chip_row = next(r for r in rows if "籌碼" in r["tab"])
        assert chip_row["emoji"] == "🟡"

    def test_render_no_raise(self):
        from data_coverage import render_data_coverage
        render_data_coverage()  # 空 session_state stub,不 raise
