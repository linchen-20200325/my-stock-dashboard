"""tests/test_etf_tab_imports.py — v18.438 hotfix 守衛。

production ImportError 根因:render_etf_single / render_etf_portfolio 的 late-import
互相從「對方 tab」拉 ETF 共用 helper(_colored_box / fetch_etf_* 等),但這些 helper
實際定義於 etf_render(L4)/ etf_calc(L2)/ etf_fetch(L1),tab 從不在 module level 提供
→ `ImportError: cannot import name '_colored_box' from etf_tab_portfolio`(整頁炸)。

本守衛:
1. render_* 函式可被呼叫且**不**拋 ImportError(直接觸發 late-import block)。
2. source-string:兩個 tab 不得再用 `from src.ui.etf.etf_tab_{single,portfolio} import`
   互拉 helper(防循環/錯誤來源回歸)。
"""
from __future__ import annotations

import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SINGLE = _ROOT / "src/ui/etf/etf_tab_single.py"
_PORTFOLIO = _ROOT / "src/ui/etf/etf_tab_portfolio.py"


class TestRenderImportBlocksResolve:
    """直接呼叫 render_*,確認 late-import block 不再 ImportError(production 炸點)。"""

    def test_render_etf_single_no_import_error(self):
        from src.ui.etf.etf_tab_single import render_etf_single
        try:
            render_etf_single()
        except ImportError as e:  # noqa: PERF203
            pytest.fail(f"render_etf_single late-import 仍 ImportError: {e}")
        except Exception:
            pass  # 無 Streamlit context 的其他例外可接受;只守 ImportError

    def test_render_etf_portfolio_no_import_error(self):
        from src.ui.etf.etf_tab_portfolio import render_etf_portfolio
        try:
            render_etf_portfolio()
        except ImportError as e:
            pytest.fail(f"render_etf_portfolio late-import 仍 ImportError: {e}")
        except Exception:
            pass


class TestNoCircularTabImport:
    """source-string:兩 tab 不得互拉 helper(回歸防護)。"""

    def test_single_not_import_from_portfolio(self):
        src = _SINGLE.read_text(encoding="utf-8")
        assert "from src.ui.etf.etf_tab_portfolio import" not in src, \
            "etf_tab_single 不得從 etf_tab_portfolio 互拉 helper(應從 etf_render/etf_calc/etf_fetch)"

    def test_portfolio_not_import_from_single(self):
        src = _PORTFOLIO.read_text(encoding="utf-8")
        assert "from src.ui.etf.etf_tab_single import" not in src, \
            "etf_tab_portfolio 不得從 etf_tab_single 互拉 helper(應從 etf_render/etf_calc/etf_fetch)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
