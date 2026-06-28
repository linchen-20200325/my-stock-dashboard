"""v18.344 PR-N1 — daily_checklist.py 跨層拆檔守衛測試。

驗證:
1. 3 個新模組 (shared/cache_layer / shared/macro_compute / macro_ui_components) 可獨立 import
2. daily_checklist re-export 全綠(caller 用 `from daily_checklist import X` 不受影響)
3. Re-export 指向新模組(identity check,確保不是 stale copy)
4. shared/* 純函式不依賴 streamlit / requests / IO(L0/L2 純函式合規)

§8.2 分層:
- shared/cache_layer.py: L0 IO (pickle wrapper)
- shared/macro_compute.py: L2 純函式
- macro_ui_components.py: L4 Render (plotly + HTML)
"""
from __future__ import annotations

import unittest


class TestNewModulesImportable(unittest.TestCase):
    """3 個新模組獨立可 import,L0/L2/L4 合規。"""

    @staticmethod
    def _has_import_stmt(src: str, mod: str) -> bool:
        """判斷 src 是否有實際 import statement (非 docstring/comment 出現)。"""
        import ast
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name.split('.')[0] == mod for alias in node.names):
                    return True
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] == mod:
                    return True
        return False

    def test_cache_layer_imports(self):
        from shared import cache_layer  # noqa
        from shared.cache_layer import _pkl_get, _pkl_put, _pkl_clear_all, _CACHE_SENTINEL  # noqa
        with open('shared/cache_layer.py', encoding='utf-8') as f:
            src = f.read()
        assert not self._has_import_stmt(src, 'streamlit'), 'L0 cache_layer 不得 import streamlit'

    def test_macro_compute_imports(self):
        from shared import macro_compute  # noqa
        from shared.macro_compute import (  # noqa
            _num, _TW_TZ_DL, _tw_today_dl, _recent_date,
            evaluate_market_status_v4_final, analyze_20d_chips_from_df,
        )
        with open('shared/macro_compute.py', encoding='utf-8') as f:
            src = f.read()
        assert not self._has_import_stmt(src, 'streamlit'), 'L2 macro_compute 不得 import streamlit'
        assert not self._has_import_stmt(src, 'requests'), 'L2 macro_compute 不得 import requests'

    def test_macro_ui_components_imports(self):
        import macro_ui_components  # noqa
        from macro_ui_components import (  # noqa
            COLORS_7, _hex2rgba, _base_layout,
            sparkline, multi_chart, bar_chart_institutional,
            stat_card, margin_card, section_header,
        )
        with open('macro_ui_components.py', encoding='utf-8') as f:
            src = f.read()
        assert not self._has_import_stmt(src, 'requests'), 'L4 ui_components 不得 import requests'
        # session_state 寫入檢測(import 不算):用 AST 找 Attribute access st.session_state
        # 簡化用字串檢測但排除 docstring/comment
        import ast
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == 'session_state':
                self.fail(f'L4 ui_components 不得碰 session_state @ line {node.lineno}')


class TestPureFunctionBehavior(unittest.TestCase):
    """純函式行為等價(從原 daily_checklist 抽出後不應改變語義)。"""

    def test_num_parse(self):
        from shared.macro_compute import _num
        self.assertEqual(_num('1,234.5'), 1234.5)
        self.assertEqual(_num('+12.3'), 12.3)
        self.assertEqual(_num('  100 '), 100.0)
        self.assertIsNone(_num('abc'))
        self.assertIsNone(_num(None))

    def test_tw_today_returns_date(self):
        import datetime
        from shared.macro_compute import _tw_today_dl
        self.assertIsInstance(_tw_today_dl(), datetime.date)

    def test_recent_date_skips_weekend(self):
        from shared.macro_compute import _recent_date
        import datetime
        d = _recent_date()
        # 結果應為 8 digit YYYYMMDD
        self.assertEqual(len(d), 8)
        # 解析後應為週一到週五
        _parsed = datetime.datetime.strptime(d, '%Y%m%d').date()
        self.assertLess(_parsed.weekday(), 5, '週末應退到週五')

    def test_evaluate_v4_strong_bull(self):
        from shared.macro_compute import evaluate_market_status_v4_final
        r = evaluate_market_status_v4_final(20000.0, 19000.0, -10000)
        self.assertTrue(r['Is_Bull'])
        self.assertFalse(r['Is_Foreign_Hedging'])  # -10000 > -30000
        self.assertEqual(r['Suggested_Holding'], '80% - 100%')

    def test_evaluate_v4_overheated(self):
        from shared.macro_compute import evaluate_market_status_v4_final
        r = evaluate_market_status_v4_final(25000.0, 19000.0, 0)  # bias 31% > 20%
        self.assertTrue(r['Is_Overheated'])
        self.assertIn('過熱', r['Signal'])

    def test_evaluate_v4_bear(self):
        from shared.macro_compute import evaluate_market_status_v4_final
        r = evaluate_market_status_v4_final(18000.0, 19000.0, 0)
        self.assertFalse(r['Is_Bull'])
        self.assertIn('空頭', r['Signal'])

    def test_analyze_20d_chips_empty(self):
        from shared.macro_compute import analyze_20d_chips_from_df
        r = analyze_20d_chips_from_df(None)
        self.assertEqual(r['signal'], '⚫ 資料不足')

    def test_hex2rgba(self):
        from macro_ui_components import _hex2rgba
        self.assertEqual(_hex2rgba('#58a6ff'), 'rgba(88,166,255,0.12)')
        self.assertEqual(_hex2rgba('#58a6ff', alpha=0.5), 'rgba(88,166,255,0.5)')
        # invalid input fallback
        self.assertEqual(_hex2rgba('invalid'), 'rgba(88,166,255,0.12)')


class TestReExportIdentity(unittest.TestCase):
    """daily_checklist re-export 必須 IS 新模組同物件(不是 copy)。"""

    def test_pkl_helpers_reexported(self):
        from src.services import _pkl_get, _pkl_put, _pkl_clear_all, _CACHE_SENTINEL
        from shared.cache_layer import (
            _pkl_get as _g, _pkl_put as _p, _pkl_clear_all as _c,
            _CACHE_SENTINEL as _s,
        )
        self.assertIs(_pkl_get, _g)
        self.assertIs(_pkl_put, _p)
        self.assertIs(_pkl_clear_all, _c)
        self.assertIs(_CACHE_SENTINEL, _s)

    def test_compute_reexported(self):
        from src.services import (
            _num, _tw_today_dl, evaluate_market_status_v4_final,
            analyze_20d_chips_from_df,
        )
        from shared.macro_compute import (
            _num as _n, _tw_today_dl as _t,
            evaluate_market_status_v4_final as _e,
            analyze_20d_chips_from_df as _a,
        )
        self.assertIs(_num, _n)
        self.assertIs(_tw_today_dl, _t)
        self.assertIs(evaluate_market_status_v4_final, _e)
        self.assertIs(analyze_20d_chips_from_df, _a)

    def test_ui_components_reexported(self):
        from src.services import (
            COLORS_7, sparkline, multi_chart, bar_chart_institutional,
            stat_card, margin_card, section_header,
        )
        from macro_ui_components import (
            COLORS_7 as _C, sparkline as _sp, multi_chart as _mc,
            bar_chart_institutional as _bc, stat_card as _sc,
            margin_card as _mg, section_header as _sh,
        )
        self.assertIs(COLORS_7, _C)
        self.assertIs(sparkline, _sp)
        self.assertIs(multi_chart, _mc)
        self.assertIs(bar_chart_institutional, _bc)
        self.assertIs(stat_card, _sc)
        self.assertIs(margin_card, _mg)
        self.assertIs(section_header, _sh)


if __name__ == "__main__":
    unittest.main()
