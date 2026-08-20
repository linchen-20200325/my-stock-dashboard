"""統一裁決 — 個股組合批次接線守衛(v19.201)。

多檔頁「體檢摘要比較表」補「🧭統一裁決」欄:技術健康分(results_t3)× 財報 grade
(批次體檢順帶算的 _overall_grade)→ assess_unified(技術主軸)。
streamlit render 不易單測 → 以 AST 釘「wiring 存在」+ import 完整。
"""
from __future__ import annotations

import ast
from pathlib import Path

_SEC = (Path(__file__).resolve().parents[1]
        / 'src' / 'ui' / 'tabs' / 'stock_grp_sections' / 'section_financial_health.py')


def _tree() -> ast.Module:
    return ast.parse(_SEC.read_text(encoding='utf-8'))


def test_worker_attaches_overall_grade():
    """批次 worker 用 no_ai_overall_verdict 算 grade 附到結果(_overall_grade)。"""
    src = _SEC.read_text(encoding='utf-8')
    assert 'no_ai_overall_verdict' in src
    assert "_overall_grade" in src


def test_summary_table_calls_assess_unified_with_both_axes():
    """摘要表呼叫 assess_unified 且傳 technical_health + fundamental_grade。"""
    tree = _tree()
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'assess_unified']
    assert calls, '應呼叫 assess_unified'
    kw = {k.arg for c in calls for k in c.keywords}
    assert 'technical_health' in kw and 'fundamental_grade' in kw, \
        '統一裁決應同時餵技術健康分與財報 grade'
    assert 'profile' in kw


def test_summary_table_has_unified_column():
    src = _SEC.read_text(encoding='utf-8')
    assert '🧭統一裁決' in src


def test_module_imports():
    import src.ui.tabs.stock_grp_sections.section_financial_health  # noqa: F401
