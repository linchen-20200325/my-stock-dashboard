"""v18.142：3 個指標 fetcher 修法 — series id / endpoint 校正回歸測試。

驗證 production blocker 修法：
- 美國核心 CPI 改 series id CPILFESL（原誤用 CPIAUCSL 總體 CPI）
- 台灣出口 YoY 改 FRED series XTEXVA01TWM664S（原 VALEXPTWM052N IMF 餵慢 13 月）
- 台灣製造業 PMI 確認首源為 data.gov.tw dataset 6100
- tab_edu.py 教育卡 identifier 同步

Source-level 驗證（不發 HTTP），確保下次重構不會 silently 改回去。
"""
from pathlib import Path


_ROOT = Path(__file__).parent.parent
_TAB_MACRO = (_ROOT / "tab_macro.py").read_text(encoding="utf-8")
_DATA_REG = (_ROOT / "data_registry.py").read_text(encoding="utf-8")
_MACRO_CORE = (_ROOT / "macro_core.py").read_text(encoding="utf-8")
_TAB_EDU = (_ROOT / "tab_edu.py").read_text(encoding="utf-8")


class TestCpiSeriesIdFix:
    """v18.142：CPI fetcher 用 CPILFESL（核心）不再用 CPIAUCSL（總體）。"""

    def test_fred_api_uses_core_cpi(self):
        # FRED API path 用 CPILFESL
        assert "'series_id': 'CPILFESL'" in _TAB_MACRO
        # tab_macro.py 內 fetcher 不再用 CPIAUCSL
        # （診斷腳本 test_fetch.py/final_check.py 不在 production 路徑，可保留）
        assert "'series_id': 'CPIAUCSL'" not in _TAB_MACRO

    def test_fredgraph_csv_fallback_added(self):
        """方案 0：FRED 公開 fredgraph.csv（無需 API key）。"""
        assert "fredgraph.csv" in _TAB_MACRO
        assert "params={'id': 'CPILFESL'}" in _TAB_MACRO

    def test_bls_uses_core_series(self):
        """BLS 核心 CPI SA = CUSR0000SA0L1E（原誤用 CPIAUCSL）。"""
        assert "'seriesid': ['CUSR0000SA0L1E']" in _TAB_MACRO
        assert "'seriesid': ['CPIAUCSL']" not in _TAB_MACRO


class TestExportSeriesIdFix:
    """v18.142：台灣出口 FRED series 改 XTEXVA01TWM664S，新增 data.gov.tw 6053。"""

    def test_fred_uses_oecd_mei_series(self):
        # 新 series id：OECD MEI 月延遲 2-3 月
        assert "'id': 'XTEXVA01TWM664S'" in _TAB_MACRO
        # 不再用 IMF IFS VALEXPTWM052N（延遲 13 月、user 看到「91 天前」根因）
        assert "'id': 'VALEXPTWM052N'" not in _TAB_MACRO

    def test_data_gov_tw_6053_added(self):
        """新增 data.gov.tw dataset 6053 海關進出口貿易統計 方案。"""
        assert "data.gov.tw/api/v2/rest/dataset/6053" in _TAB_MACRO
        # log 標籤
        assert "Export/data.gov.tw-6053" in _TAB_MACRO

    def test_data_registry_export_backup_updated(self):
        """data_registry 備援 series id 同步 + 新增 6053 註冊。"""
        assert "'identifier':'XTEXVA01TWM664S'" in _DATA_REG
        assert "'identifier':'dataset/6053'" in _DATA_REG
        # 舊備援 identifier 已刪
        assert "'identifier':'VALEXPTWM052N'" not in _DATA_REG


class TestPmiPrimarySource:
    """v18.142：PMI 主源為 data.gov.tw dataset 6100，9 段並行。"""

    def test_dgtw_6100_in_macro_core(self):
        """_pmi_src_dgtw 用 dataset/6100（國發會 NDC 官方）。"""
        assert "data.gov.tw/api/v2/rest/dataset/6100" in _MACRO_CORE

    def test_registry_label_updated(self):
        """來源欄改成「data.gov.tw 6100 + CIER + 8 段並行」反映真實架構。"""
        assert "data.gov.tw 6100" in _DATA_REG


class TestEduCardSync:
    """v18.142：tab_edu.py 教育卡 identifier 同步更新。"""

    def test_tab_edu_uses_new_series_id(self):
        assert "XTEXVA01TWM664S" in _TAB_EDU
        assert "VALEXPTWM052N" not in _TAB_EDU

    def test_data_registry_edu_entry_updated(self):
        # data_registry.py L742 edu dict key 也改
        assert "'XTEXVA01TWM664S': {" in _DATA_REG
        assert "'VALEXPTWM052N': {" not in _DATA_REG
