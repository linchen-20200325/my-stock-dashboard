"""v18.333 PR-H1 — 多檔 ETF Tab 補流動性 + 追蹤誤差 SSOT 守衛測試。

audit 起點:R-2 ETF 三 Tab 深度盤點報告 P1 — calc_liquidity_score / calc_tracking_error
SSOT 已寫但 grp_compare 無 caller(R-2 audit Task C2 評為「最低掛 SSOT」)。

本次新增:
- _fetch_one_etf 補 4 個 key:liquidity_level / liquidity_avg_vol_20d / liquidity_reasons / tracking_error
- render_etf_grp_compare 表格補 2 欄:「流動性」/「追蹤誤差%」
- column_config 補 help text
- import 補 calc_liquidity_score / calc_tracking_error / auto_detect_benchmark
"""
from __future__ import annotations


class TestImportContract:
    """import 行為契約 — SSOT 函式應從 etf_calc 引入。"""

    def test_grp_compare_imports_liquidity_score(self):
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert 'calc_liquidity_score' in src
        assert 'from etf_calc import' in src

    def test_grp_compare_imports_tracking_error(self):
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert 'calc_tracking_error' in src
        assert 'auto_detect_benchmark' in src


class TestFetchOneEtfShape:
    """_fetch_one_etf 結果 dict schema 新欄位。"""

    def test_default_dict_has_new_keys(self):
        """空 dict init 階段應預設新 4 個 key,線程安全保障。"""
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        # 確保 init dict 有設定 default(避免 KeyError)
        assert "'liquidity_level':" in src
        assert "'liquidity_avg_vol_20d':" in src
        assert "'liquidity_reasons':" in src
        assert "'tracking_error':" in src

    def test_default_liquidity_is_unknown_emoji(self):
        """資料不足 default 應為 ⚪(對齊 calc_liquidity_score 契約)。"""
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert "'liquidity_level': '⚪'" in src

    def test_default_tracking_error_is_none(self):
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert "'tracking_error': None" in src


class TestFetchOneEtfBody:
    """_fetch_one_etf 函式內 SSOT 呼叫 — 補欄邏輯實作。"""

    def test_calls_calc_liquidity_score(self):
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert 'calc_liquidity_score(_df, _r[\'aum\'])' in src

    def test_calls_auto_detect_benchmark(self):
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert 'auto_detect_benchmark(ticker)' in src

    def test_calls_calc_tracking_error(self):
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert 'calc_tracking_error(_df, _bench_df)' in src

    def test_bench_ticker_self_skip(self):
        """benchmark == ticker(0050.TW 自己 vs 自己 → 0 誤差無意義)應跳過。"""
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert '_bench != ticker' in src

    def test_liquidity_failure_has_log(self):
        """fail loud:流動性計算失敗須 log,不 silent。"""
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert '流動性評分失敗' in src

    def test_tracking_error_failure_has_log(self):
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert '追蹤誤差計算失敗' in src


class TestRenderTableColumns:
    """render 表格欄位與 column_config 完整對齊。"""

    def test_table_has_liquidity_column(self):
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert "'流動性':" in src
        assert "r.get('liquidity_level'" in src

    def test_table_has_tracking_error_column(self):
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert "'追蹤誤差%':" in src
        assert "r.get('tracking_error'" in src

    def test_column_config_liquidity_has_help(self):
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert "'流動性':" in src and 'TextColumn' in src
        # help text 應提到三色燈號契約
        assert '🟢' in src and '🟡' in src and '🔴' in src

    def test_column_config_tracking_error_has_help(self):
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert "'追蹤誤差%':" in src and 'NumberColumn' in src
        assert '1.5%' in src  # 警示門檻寫在 help

    def test_caption_updated_to_6_ssot_cols(self):
        """caption 由「4 SSOT 補欄」改「6 SSOT 補欄」。"""
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert '6 SSOT 補欄' in src
        assert '流動性' in src and '追蹤誤差' in src


class TestModuleImportable:
    """整個 module 須能正常 import — 防新 import 環依賴。"""

    def test_module_imports_clean(self):
        import etf_tab_grp_compare  # noqa: F401
