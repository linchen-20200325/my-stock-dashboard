"""tests/test_hotfix_v19_79.py — 2026-07-10 雲端倒站 hotfix 守護。

事故:Streamlit Cloud 平台遷 Python 3.14 + pyarrow 25.0.0 當日發布 →
兩儀表板 Segmentation fault;另 v19.74 融資餘額誤用「仟元」換算 →
FinMind 路徑全滅(production log 實證單位=元)。

TARGET:
- requirements.txt                       (pyarrow cap / FinMind 殭屍依賴移除)
- src/data/daily/daily_data_fetchers.py  (Money 列過濾 + 元→億)
- src/data/core/data_loader.py           (FinMind 雙路 import 錯誤都保留)
"""
from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]


class TestRequirementsHotfix:
    @property
    def _req(self) -> str:
        return (_REPO / "requirements.txt").read_text(encoding="utf-8")

    def test_pyarrow_capped_below_25(self):
        # pyarrow 25.0.0(2026-07-10 當日發布)= 雲端 segfault 兇手;顯式 cap
        assert "pyarrow>=14,<25" in self._req

    def test_finmind_sdk_removed(self):
        # FinMind 1.x pin pandas<2/numpy<2/lxml<5,與核心 pin 硬衝突(殭屍依賴)
        active = [ln for ln in self._req.splitlines()
                  if ln.strip() and not ln.strip().startswith("#")]
        assert not any(ln.startswith("FinMind") for ln in active)

    def test_core_pins_still_present(self):
        req = self._req
        for token in ("streamlit>=1.36.0,<1.60.0", "pandas>=2.0.0,<4.0.0",
                      "numpy>=1.24.0,<3.0.0"):
            assert token in req


class TestMarginMoneyRowParsing:
    @property
    def _src(self) -> str:
        return (_REPO / "src" / "data" / "daily" /
                "daily_data_fetchers.py").read_text(encoding="utf-8")

    def test_money_row_filter_present(self):
        src = self._src
        assert "_is_margin_money0" in src
        assert "'money' in _nm0_l" in src

    def test_yesterday_balance_excluded(self):
        assert "not c.lower().startswith('yes')" in self._src

    def test_conversion_is_yuan_not_qianyuan(self):
        src = self._src
        assert "raw_twd / 1e8" in src
        assert "raw / 1e5" not in src


class TestFinmindImportDiagnostics:
    def test_both_import_errors_logged(self):
        src = (_REPO / "src" / "data" / "core" /
               "data_loader.py").read_text(encoding="utf-8")
        # 第一段(FinMind 大寫)錯誤不可再被第二段覆蓋
        assert "_fm_err_cap" in src
        assert "FinMind={_fm_err_cap} / finmind={_e}" in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
