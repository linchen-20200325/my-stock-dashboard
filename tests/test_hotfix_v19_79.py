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
    """v19.79 hotfix 迴歸：融資彙總 dataset 必須只吃 Money 列的當日餘額，且以「元」換算。

    ⚠️ v19.181 B3 改寫（第 6 次「掃原始碼字面」假紅燈的處置）
    ------------------------------------------------------------------
    原本三條斷言掃的是 `daily_data_fetchers.py` 的**字面**：
        `_is_margin_money0` / `'money' in _nm0_l` / `not c.lower().startswith('yes')`
        / `raw_twd / 1e8`
    B3 把這些 inline 實作抽到 L0 SSOT `shared/margin_schema.py`（讓 cron 的
    `scripts/update_macro_history.py` 與本檔共用同一份，根治「同一件事兩個實作、
    只有一個是對的」），字面自然從原檔消失 → 三條全紅。

    **行為完全沒變，是實作搬家了。** 所以不把字串改指到新檔案 —— 那只是把同一個
    脆弱性搬個位置，下次再重構還會再紅一次。改成**行為斷言**：直接呼叫函式驗結果，
    重構到哪裡都不會假紅，而真的改壞判定邏輯時一定會紅。
    另加一條**委派斷言**，確保本檔真的走 SSOT 而不是又長出第三份 inline 實作。
    """

    def test_money_row_filter_present(self):
        """只認 Money 列；Volume 列（單位=張）必須被排除。

        v19.79 的事故就是 Volume 列被當金額用 —— production log 實測
        `MarginPurchaseVolume = 9,614,955`（張）與
        `MarginPurchaseMoney  = 619,648,244,000`（元＝6,196 億）同組並存。
        """
        from shared.margin_schema import (MARGIN_MONEY_NAME_ZH,
                                          MARGIN_MONEY_ROW_NAME,
                                          MARGIN_VOLUME_ROW_NAME,
                                          is_margin_money_row)
        assert is_margin_money_row(MARGIN_MONEY_ROW_NAME) is True
        assert is_margin_money_row(MARGIN_MONEY_NAME_ZH) is True
        assert is_margin_money_row(MARGIN_VOLUME_ROW_NAME) is False
        # 大小寫不敏感（FinMind 欄位大小寫曾變動過）
        assert is_margin_money_row(MARGIN_MONEY_ROW_NAME.lower()) is True
        # None / 非字串不得炸，且一律不認
        assert is_margin_money_row(None) is False

    def test_yesterday_balance_excluded(self):
        """只取當日餘額；`Yesterday*` 必須排除 —— 抓錯會讓整條序列日期錯位一天（§2.3 PIT）。"""
        from shared.margin_schema import (is_today_balance_col,
                                          pick_today_balance_cols)
        assert is_today_balance_col("MarginPurchaseTodayBalance") is True
        assert is_today_balance_col("TodayBalance") is True
        assert is_today_balance_col("YesterdayBalance") is False
        assert is_today_balance_col("MarginPurchaseYesterdayBalance") is False
        picked = pick_today_balance_cols(
            ["date", "name", "TodayBalance", "YesterdayBalance", "Note"])
        assert "TodayBalance" in picked
        assert not any("esterday" in c for c in picked)

    def test_conversion_is_yuan_not_qianyuan(self):
        """單位是「元」（÷1e8 → 億），不是「仟元」（÷1e5）。

        以 production 實測值對帳：619,648,244,000 元 = 6,196 億（2026 年量級）。
        若誤當仟元則會得到 6,196,482 億 —— 落在 sanity 之外，函式必須回 None 而非硬給值。
        """
        from shared.margin_schema import margin_money_to_yi
        # 函式回傳前 round(,1)：619,648,244,000 / 1e8 = 6196.48244 → 6196.5
        assert margin_money_to_yi(619_648_244_000) == pytest.approx(6196.5, abs=0.05)
        # 若誤當「仟元」(÷1e5) 會得到 6,196,482 億 —— 遠超 sanity 上界，
        # 這裡順帶釘住「量級對，不是碰巧數字接近」
        assert 500 < margin_money_to_yi(619_648_244_000) < 10_000
        # 張數（9,614,955）誤入時 ÷1e8 ≈ 0.096 億，遠低於 sanity 下界 → 必須回 None，
        # 不得回 0 或原值（§1：寧可沒有數字，不可給錯數字）
        assert margin_money_to_yi(9_614_955) is None

    def test_daily_fetchers_delegates_to_ssot(self):
        """本檔的 helper 必須是 SSOT 的薄 wrapper，不得再長出第三份 inline 實作（§2.1）。"""
        import shared.margin_schema as _ms
        from src.data.daily import daily_data_fetchers as _ddf
        # 行為等價（同輸入同輸出），而非比對實作字面
        for _v in (619_648_244_000, 9_614_955, 0, -1):
            assert _ddf._finmind_margin_to_yi(_v) == _ms.margin_money_to_yi(_v)
        for _v in (6196.48, 0.096, 499.9, 10_000.1):
            assert _ddf._margin_sanity_ok(_v) == _ms.margin_sanity_ok(_v)


class TestFinmindImportDiagnostics:
    def test_both_import_errors_logged(self):
        src = (_REPO / "src" / "data" / "core" /
               "data_loader.py").read_text(encoding="utf-8")
        # 第一段(FinMind 大寫)錯誤不可再被第二段覆蓋
        assert "_fm_err_cap" in src
        assert "FinMind={_fm_err_cap} / finmind={_e}" in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
