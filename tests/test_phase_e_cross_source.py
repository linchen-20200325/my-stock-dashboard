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


# UI 源碼層測試已退役(v18.399 R6 真刪)
# tab_macro_validation.py 整檔已刪除;原 4 個 source-string 守衛測試
# (test_render_function_exists / test_render_wired_after_phase3 /
# test_render_uses_evaluate_signal_at_event / test_render_outputs_consensus_row)
# 因失去保護對象,同步退役。Backend 邏輯測試(本檔上方 PMI fetcher + registry
# 共 3 個 case)全保留。


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
