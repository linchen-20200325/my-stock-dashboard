"""v18.337 PR-H5 — 個股 Tab 多因子評分卡 + RS SSOT 守衛測試。

R-1 audit P2 收尾 — 個股 Tab 補 SQ/FGMS/RS 三維度 0-100 評分卡(對標個股組合)。

新增 SSOT:
- tab_helpers.classify_rs_zone(rs_val, slope_up) — RS 數值評級(STOCK_RS_*)

個股 Tab 新增「⚙️ 多因子評分」3 卡:
- SQ 獲利品質(calc_quality_score → SQ_GOOD/STABLE_MIN 三色)
- FGMS 前瞻動能(calc_forward_momentum_score → FGMS_LABEL_T1/T2 三色)
- RS 相對強度(classify_rs_zone 統一分級)
"""
from __future__ import annotations


# ─────────── classify_rs_zone SSOT ───────────

class TestClassifyRsZone:
    """RS 數值評級 SSOT(對應 STOCK_RS_STRONG_MIN=75 / NEUTRAL_MIN=50)。"""

    def test_none_returns_no_data(self):
        from tab_helpers import classify_rs_zone
        label, color = classify_rs_zone(None)
        assert '無資料' in label

    def test_strong_above_75(self):
        from tab_helpers import classify_rs_zone
        label, color = classify_rs_zone(85.0)
        assert '強勢' in label
        assert '85' in label

    def test_neutral_between_50_and_75(self):
        from tab_helpers import classify_rs_zone
        label, color = classify_rs_zone(60.0)
        assert '中性' in label

    def test_weak_below_50(self):
        from tab_helpers import classify_rs_zone
        label, color = classify_rs_zone(30.0)
        assert '弱勢' in label

    def test_boundary_exact_75(self):
        from tab_helpers import classify_rs_zone
        label, color = classify_rs_zone(75.0)
        assert '強勢' in label

    def test_boundary_exact_50(self):
        from tab_helpers import classify_rs_zone
        label, color = classify_rs_zone(50.0)
        assert '中性' in label

    def test_slope_up_appends_arrow(self):
        from tab_helpers import classify_rs_zone
        label, color = classify_rs_zone(80, rs_slope_up=True)
        assert '↑強勢' in label

    def test_slope_down_appends_arrow(self):
        from tab_helpers import classify_rs_zone
        label, color = classify_rs_zone(80, rs_slope_up=False)
        assert '↓弱勢' in label

    def test_slope_none_no_arrow(self):
        from tab_helpers import classify_rs_zone
        label, color = classify_rs_zone(80, rs_slope_up=None)
        # 不應有箭頭(避免空白尾)
        assert '↑' not in label
        assert '↓' not in label


# ─────────── Caller migration ───────────

class TestCallerMigration:
    """個股 Tab 新增「⚙️ 多因子評分」3 卡 + import classify_rs_zone。"""

    def test_tab_stock_imports_rs_zone(self):
        src = open('tab_stock.py', encoding='utf-8').read()
        assert 'classify_rs_zone' in src

    def test_tab_stock_has_multifactor_section(self):
        src = open('tab_stock.py', encoding='utf-8').read()
        assert '⚙️ 多因子評分' in src

    def test_tab_stock_uses_sq_score(self):
        src = open('tab_stock.py', encoding='utf-8').read()
        assert 'calc_quality_score' in src
        # SQ 分級走 SSOT 三色
        assert 'SQ_GOOD_MIN' in src
        assert 'SQ_STABLE_MIN' in src

    def test_tab_stock_uses_fgms_score(self):
        src = open('tab_stock.py', encoding='utf-8').read()
        assert 'calc_forward_momentum_score' in src
        # FGMS 分級走 SSOT 三色(LABEL_T1/T2)
        assert 'FGMS_LABEL_T1' in src
        assert 'FGMS_LABEL_T2' in src

    def test_tab_stock_renders_rs_via_classify(self):
        """個股 Tab 多因子卡 3 用 classify_rs_zone(不再 inline 75/50 比較)。"""
        src = open('tab_stock.py', encoding='utf-8').read()
        assert 'classify_rs_zone(_rs_v_card' in src

    def test_three_cards_in_section(self):
        """確保 _mf_c1/c2/c3 都呈現"""
        src = open('tab_stock.py', encoding='utf-8').read()
        assert '_mf_c1, _mf_c2, _mf_c3' in src
        assert 'SQ 獲利品質' in src
        assert 'FGMS 前瞻動能' in src
        assert 'RS 相對強度' in src


class TestModulesImportable:
    def test_tab_helpers_clean(self):
        import tab_helpers  # noqa: F401

    def test_tab_stock_clean(self):
        import tab_stock  # noqa: F401
