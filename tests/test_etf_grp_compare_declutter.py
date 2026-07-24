"""tests/test_etf_grp_compare_declutter.py — v19.166 守衛:多檔比較表版面重排。

多檔比較主表原本一次攤 24 欄(user 反映太雜)。版面重排改「主表 11 個決策核心欄
+ 完整 24 欄收進 expander」——「整理不減料」:所有欄位仍在(expander 內完整呈現),
主視圖只是不再一次攤 24 欄。本測試釘住:(1) 核心欄子集存在、(2) 完整表仍 render
(零減料)、(3) expander 掛載。
"""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SRC = (_REPO / "src/ui/etf/etf_tab_grp_compare.py").read_text(encoding="utf-8")


def test_core_subset_table_exists():
    """主表只餵 11 個決策核心欄(不是整個 24 欄 df)。"""
    assert "_CORE_COLS" in _SRC, "缺核心欄子集定義"
    assert "df[_core_cols_present]" in _SRC, "主表未改餵核心欄子集"
    # 11 核心欄應含最關鍵的 建議 / 綜合分 / 費用率 / 殖利率
    for col in ("'🚦 建議'", "'綜合分'", "'費用率%'", "'殖利率%'", "'建議理由'"):
        assert col in _SRC, f"核心欄缺 {col}"


def test_full_detail_still_rendered_no_data_loss():
    """§整理不減料:完整 24 欄 df 仍在 expander 內完整 render,零減料。"""
    assert "st.expander(" in _SRC, "缺完整指標 expander"
    assert "完整指標" in _SRC, "expander 標題缺失"
    # 完整表用共享的 _full_col_config,且餵整個 df(非子集)
    assert "_full_col_config" in _SRC, "缺共享 column_config"
    assert "column_config=_full_col_config," in _SRC, "完整表未用共享 config"


def test_secondary_metrics_preserved_in_full_config():
    """被移出主表的次要欄(σ 買賣帶 / 追蹤誤差 / 折溢價 / 5Y均殖)仍在完整 config,不得刪。"""
    for col in ("'σ強買≤'", "'追蹤誤差%'", "'折溢價%'", "'5Y均殖%'", "'配息健康'"):
        assert col in _SRC, f"次要欄 {col} 被誤刪(應保留於完整指標 expander)"


def test_module_imports_clean():
    from src.ui.etf import etf_tab_grp_compare  # noqa: F401


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
