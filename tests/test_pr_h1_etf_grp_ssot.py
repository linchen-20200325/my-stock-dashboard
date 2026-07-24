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
        # v19.166:流動性計算下沉 build_etf_score_row(etf_scoring_helpers),多檔頁不再直呼
        src = open('src/compute/etf/etf_scoring_helpers.py', encoding='utf-8').read()
        assert 'calc_liquidity_score' in src
        assert 'from src.compute.etf' in src

    def test_grp_compare_imports_tracking_error(self):
        src = open('src/ui/etf/etf_tab_grp_compare.py', encoding='utf-8').read()
        assert 'calc_tracking_error' in src
        assert 'auto_detect_benchmark' in src


class TestFetchOneEtfShape:
    """row schema 新欄位(v19.166:dict schema 下沉 build_etf_score_row)。"""

    def test_default_dict_has_new_keys(self):
        """row init dict 應含新 4 個 key,避免 KeyError(下沉 etf_scoring_helpers)。"""
        src = open('src/compute/etf/etf_scoring_helpers.py', encoding='utf-8').read()
        assert "'liquidity_level':" in src
        assert "'liquidity_avg_vol_20d':" in src
        assert "'liquidity_reasons':" in src
        assert "'tracking_error':" in src

    def test_default_liquidity_is_unknown_emoji(self):
        """資料不足 default 應為 ⚪(對齊 calc_liquidity_score 契約)。"""
        src = open('src/compute/etf/etf_scoring_helpers.py', encoding='utf-8').read()
        assert "'liquidity_level': '⚪'" in src

    def test_default_tracking_error_defaults_none(self):
        """tracking_error 由 caller 注入,參數預設 None(v19.166 依賴注入)。"""
        src = open('src/compute/etf/etf_scoring_helpers.py', encoding='utf-8').read()
        assert 'tracking_error=None' in src
        assert "'tracking_error': tracking_error" in src


class TestFetchOneEtfBody:
    """_fetch_one_etf 函式內 SSOT 呼叫 — 補欄邏輯實作。"""

    def test_calls_calc_liquidity_score(self):
        # v19.166:流動性計算移入 build_etf_score_row(etf_scoring_helpers)
        src = open('src/compute/etf/etf_scoring_helpers.py', encoding='utf-8').read()
        assert 'calc_liquidity_score(df, _r[\'aum\'])' in src

    def test_calls_auto_detect_benchmark(self):
        src = open('src/ui/etf/etf_tab_grp_compare.py', encoding='utf-8').read()
        assert 'auto_detect_benchmark(ticker)' in src

    def test_calls_calc_tracking_error(self):
        src = open('src/ui/etf/etf_tab_grp_compare.py', encoding='utf-8').read()
        assert 'calc_tracking_error(_df, _bench_df)' in src

    def test_bench_ticker_self_skip(self):
        """benchmark == ticker(0050.TW 自己 vs 自己 → 0 誤差無意義)應跳過。"""
        src = open('src/ui/etf/etf_tab_grp_compare.py', encoding='utf-8').read()
        assert '_bench != ticker' in src

    def test_liquidity_failure_has_log(self):
        """fail loud:流動性計算失敗須 log,不 silent(v19.166 移入 build_etf_score_row)。"""
        src = open('src/compute/etf/etf_scoring_helpers.py', encoding='utf-8').read()
        assert '流動性失敗' in src

    def test_tracking_error_failure_has_log(self):
        src = open('src/ui/etf/etf_tab_grp_compare.py', encoding='utf-8').read()
        assert '追蹤誤差計算失敗' in src


class TestRenderTableColumns:
    """render 表格欄位與 column_config 完整對齊。"""

    def test_table_has_liquidity_column(self):
        src = open('src/ui/etf/etf_tab_grp_compare.py', encoding='utf-8').read()
        assert "'流動性':" in src
        assert "r.get('liquidity_level'" in src

    def test_table_has_tracking_error_column(self):
        src = open('src/ui/etf/etf_tab_grp_compare.py', encoding='utf-8').read()
        assert "'追蹤誤差%':" in src
        assert "r.get('tracking_error'" in src

    def test_column_config_liquidity_has_help(self):
        src = open('src/ui/etf/etf_tab_grp_compare.py', encoding='utf-8').read()
        assert "'流動性':" in src and 'TextColumn' in src
        # help text 應提到三色燈號契約
        assert '🟢' in src and '🟡' in src and '🔴' in src

    def test_column_config_tracking_error_has_help(self):
        src = open('src/ui/etf/etf_tab_grp_compare.py', encoding='utf-8').read()
        assert "'追蹤誤差%':" in src and 'NumberColumn' in src
        assert '1.5%' in src  # 警示門檻寫在 help

    def test_caption_updated_to_6_ssot_cols(self):
        """caption 由「4 SSOT 補欄」改「6 SSOT 補欄」。"""
        src = open('src/ui/etf/etf_tab_grp_compare.py', encoding='utf-8').read()
        assert '6 SSOT 補欄' in src
        assert '流動性' in src and '追蹤誤差' in src


class TestModuleImportable:
    """整個 module 須能正常 import — 防新 import 環依賴。"""

    def test_module_imports_clean(self):
        from src.ui.etf import etf_tab_grp_compare  # noqa: F401
