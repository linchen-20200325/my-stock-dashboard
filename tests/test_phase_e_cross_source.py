"""v18.178 Phase E 跨資料源比對測試 — PMI 訊號 fetcher + 矩陣 UI 結構。

驗證重點：
1. PMI fetcher (fetch_pmi_below_50_series) 讀 tw_pmi.parquet 缺檔 graceful
2. PMI 在 TW_SIGNAL_FETCHERS / DEFAULT_TW_SIGNALS 註冊
3. cross-source matrix UI helper 源碼層存在 + 接 Phase 3 之後
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest


# ════════════════════════════════════════════════════════════════
# §1 PMI fetcher
# ════════════════════════════════════════════════════════════════
class TestPmiFetcher:
    def test_missing_parquet_returns_empty_series(self):
        from src.compute.macro import fetch_pmi_below_50_series
        with tempfile.TemporaryDirectory() as tmpdir:
            s = fetch_pmi_below_50_series(Path(tmpdir))
        assert s.empty
        assert s.name == "PMI_BELOW_50"

    def test_parses_valid_parquet(self):
        from src.compute.macro import fetch_pmi_below_50_series
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            df = pd.DataFrame({
                "date": pd.date_range("2024-01-01", periods=6, freq="MS"),
                "pmi": [52.0, 51.5, 49.0, 48.5, 50.5, 51.0],
            })
            df.to_parquet(tmp / "tw_pmi.parquet")
            s = fetch_pmi_below_50_series(tmp)
        assert len(s) == 6
        assert s.iloc[0] == 52.0
        assert s.iloc[2] == 49.0  # below 50
        assert s.name == "PMI_BELOW_50"

    def test_parquet_missing_pmi_column_returns_empty(self):
        from src.compute.macro import fetch_pmi_below_50_series
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # 缺 pmi 欄位
            df = pd.DataFrame({
                "date": pd.date_range("2024-01-01", periods=3, freq="MS"),
                "other": [1, 2, 3],
            })
            df.to_parquet(tmp / "tw_pmi.parquet")
            s = fetch_pmi_below_50_series(tmp)
        assert s.empty


# ════════════════════════════════════════════════════════════════
# §2 Registry / Spec 註冊
# ════════════════════════════════════════════════════════════════
class TestPmiSignalRegistration:
    def test_pmi_in_TW_SIGNAL_FETCHERS(self):
        from src.compute.macro import TW_SIGNAL_FETCHERS
        assert "PMI_BELOW_50" in TW_SIGNAL_FETCHERS
        assert callable(TW_SIGNAL_FETCHERS["PMI_BELOW_50"])

    def test_pmi_in_DEFAULT_TW_SIGNALS(self):
        from src.compute.macro import DEFAULT_TW_SIGNALS
        pmi_specs = [s for s in DEFAULT_TW_SIGNALS if s.key == "PMI_BELOW_50"]
        assert len(pmi_specs) == 1
        spec = pmi_specs[0]
        assert spec.threshold == 50.0
        assert spec.direction == "below"
        assert "PMI" in spec.label


# ════════════════════════════════════════════════════════════════
# §3 Cross-source matrix UI 源碼層測試
# ════════════════════════════════════════════════════════════════
class TestPhase4UiSource:
    def test_render_function_exists(self):
        import tab_macro_validation
        assert hasattr(tab_macro_validation, "_render_phase4_cross_source_matrix")
        assert callable(tab_macro_validation._render_phase4_cross_source_matrix)

    def test_render_wired_after_phase3(self):
        """確認 Phase E render 在 Phase 3 命中表之後 + 自動校準之前的順序。"""
        import inspect
        import tab_macro_validation
        src = inspect.getsource(tab_macro_validation._render_phase3_signal_section)
        p4 = src.find("_render_phase4_cross_source_matrix")
        auto = src.find("_render_phase3_auto_calibration")
        assert p4 != -1, "Phase 4 必須被 wire 進 Phase 3 section"
        assert auto != -1
        assert p4 < auto, "Phase 4 必須在自動校準之前渲染"

    def test_render_uses_evaluate_signal_at_event(self):
        """Phase 4 應該複用既有 evaluate_signal_at_event 邏輯（避免重新發明引擎）。"""
        import inspect
        import tab_macro_validation
        src = inspect.getsource(
            tab_macro_validation._render_phase4_cross_source_matrix)
        assert "evaluate_signal_at_event" in src

    def test_render_outputs_consensus_row(self):
        """矩陣末列必須是「多源共識」總計。"""
        import inspect
        import tab_macro_validation
        src = inspect.getsource(
            tab_macro_validation._render_phase4_cross_source_matrix)
        assert "多源共識" in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
