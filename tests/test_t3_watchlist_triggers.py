"""T3(2026-08)— 觀察池訊號判定 L2 純函式測試。

受測：`src/compute/notify/watchlist_triggers.py`

§6 要求的「3 個最容易讓這段程式出錯的輸入」
────────────────────────────────────────────
① **連續在均線下方** —— 若把規則寫成「位於下方」而非「穿越」，一檔跌破後盤整的
   股票會連續數十個交易日每天推播一次。使用者三天內就會關掉通知，
   整套推播系統的價值歸零。這是本模組**最重要**的一條測試。
② **K 線剛好 = window 根** —— 判「昨天還在線上」需要 t-1 的均線，
   故需 window+1 根。差一根時必須回 None（「算不出來」），
   **不可**回 `crossed=False`（那是「沒跌破」，是不同的事實）。
③ **大寫欄名** —— `fetch_stock_history_1y` 回 `Close`，但
   `compute_tech_bearish` 檢查小寫 `'close'`。不正規化的話下游**靜默**
   回「無訊號」而不是報錯 → 整個觀察池安靜地永遠不觸發。
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.compute.notify.watchlist_triggers import (
    EXIT_SIGNAL_ACTIONABLE_SCORE,
    TRIGGER_MA_CROSS,
    ScanResult,
    TickerVerdict,
    evaluate_ma_cross,
    evaluate_ticker,
    normalize_ohlcv,
    scan_watchlist,
)


def _series_df(closes: list[float], *, upper: bool = False, dates: bool = True):
    _col = "Close" if upper else "close"
    _idx = pd.date_range("2026-01-01", periods=len(closes), freq="D") if dates else None
    return pd.DataFrame({_col: closes}, index=_idx)


# ════════════════════════════════════════════════════════════════════
# ① 穿越 vs 位於 —— 本模組最重要的一條
# ════════════════════════════════════════════════════════════════════
class TestErrorProne1_CrossNotBelow:

    def test_fires_on_the_cross_day(self):
        """平盤 20 天後單日重挫 → 當天觸發。"""
        _df = _series_df([100.0] * 21 + [80.0])
        _r = evaluate_ma_cross(_df, 20)
        assert _r is not None and _r["crossed"] is True

    def test_does_not_fire_while_staying_below(self):
        """跌破後在均線下方**盤整**，不得每天重複觸發。

        構造：前 21 天 100，之後連續 10 天 80。第一根 80 是穿越日，
        但到了第 10 根 80，均線早已被拉下來且前一日也在線下 → 不該再觸發。
        """
        _df = _series_df([100.0] * 21 + [80.0] * 10)
        _r = evaluate_ma_cross(_df, 20)
        assert _r is not None
        assert _r["crossed"] is False, (
            "持續位於均線下方仍判觸發 → 會連續數十天每天推播一次"
        )

    def test_does_not_fire_when_above(self):
        _df = _series_df([100.0] * 21 + [120.0])
        assert evaluate_ma_cross(_df, 20)["crossed"] is False

    def test_does_not_fire_on_upward_cross(self):
        """由下往上穿越是**好事**，本規則只管跌破。"""
        _df = _series_df([80.0] * 21 + [200.0])
        assert evaluate_ma_cross(_df, 20)["crossed"] is False


# ════════════════════════════════════════════════════════════════════
# ② 資料長度邊界
# ════════════════════════════════════════════════════════════════════
class TestErrorProne2_Length:

    def test_exactly_window_bars_returns_none(self):
        """剛好 window 根 → 算不出 t-1 的均線 → None，不是 False。"""
        assert evaluate_ma_cross(_series_df([100.0] * 20), 20) is None

    def test_window_plus_one_works(self):
        assert evaluate_ma_cross(_series_df([100.0] * 21), 20) is not None

    @pytest.mark.parametrize("n", [0, 1, 5])
    def test_too_few_bars(self, n):
        assert evaluate_ma_cross(_series_df([100.0] * n), 20) is None

    def test_none_is_distinct_from_no_cross(self):
        """§1：「算不出來」與「沒跌破」必須可區分。"""
        _insufficient = evaluate_ma_cross(_series_df([100.0] * 10), 20)
        _sufficient = evaluate_ma_cross(_series_df([100.0] * 21), 20)
        assert _insufficient is None
        assert _sufficient is not None and _sufficient["crossed"] is False


# ════════════════════════════════════════════════════════════════════
# ③ 欄名正規化
# ════════════════════════════════════════════════════════════════════
class TestErrorProne3_ColumnNames:

    def test_uppercase_is_normalized(self):
        _out = normalize_ohlcv(pd.DataFrame({
            "Close": [1.0], "Open": [1.0], "High": [1.0],
            "Low": [1.0], "Volume": [10],
        }))
        for _c in ("close", "open", "high", "low", "volume"):
            assert _c in _out.columns

    def test_lowercase_untouched(self):
        _in = pd.DataFrame({"close": [1.0]})
        assert list(normalize_ohlcv(_in).columns) == ["close"]

    def test_does_not_mutate_input(self):
        _in = pd.DataFrame({"Close": [1.0]})
        normalize_ohlcv(_in)
        assert "Close" in _in.columns, "正規化污染了 caller 手上的 df"

    def test_existing_lowercase_wins(self):
        """同時有 Close 與 close → 不覆蓋既有小寫欄（避免資料被悄悄換掉）。"""
        _in = pd.DataFrame({"Close": [1.0], "close": [2.0]})
        assert float(normalize_ohlcv(_in)["close"].iloc[0]) == 2.0

    def test_uppercase_df_still_triggers(self):
        """端到端：大寫欄的 df 丟進 evaluate_ticker 仍要能觸發。

        這是③真正的危害所在 —— 不正規化不會報錯，只會安靜地永不觸發。
        """
        _df = _series_df([100.0] * 21 + [80.0], upper=True)
        _v = evaluate_ticker("2330", _df, ma_windows=(20,))
        assert _v.evaluated, f"大寫欄 df 被判為無法評估：{_v.skipped_reason}"
        assert any(t.startswith(TRIGGER_MA_CROSS) for t in _v.triggers)


# ════════════════════════════════════════════════════════════════════
# 4. evaluate_ticker：三態（觸發 / 沒事 / 沒評估）
# ════════════════════════════════════════════════════════════════════
class TestVerdictTriState:

    def test_fired(self):
        _v = evaluate_ticker("2330", _series_df([100.0] * 21 + [80.0]))
        assert _v.fired and _v.evaluated
        assert _v.reasons and "MA20" in _v.reasons[0]

    def test_quiet_is_not_skipped(self):
        """沒事 ≠ 沒評估 —— 兩者必須可區分（§1）。"""
        _v = evaluate_ticker("2330", _series_df([100.0] * 30))
        assert not _v.fired
        assert _v.evaluated and _v.skipped_reason is None

    @pytest.mark.parametrize("df,expect", [
        (None, "抓不到"),
        (pd.DataFrame(), "抓不到"),
        (pd.DataFrame({"其他": [1] * 30}), "close"),
    ])
    def test_skipped_reasons(self, df, expect):
        _v = evaluate_ticker("2330", df)
        assert not _v.evaluated and expect in (_v.skipped_reason or "")

    def test_insufficient_history_is_skipped_not_quiet(self):
        """新上市（§4.6）→ 標「歷史不足」，**不可**當成「今天沒事」。"""
        _v = evaluate_ticker("6666", _series_df([100.0] * 10))
        assert not _v.evaluated
        assert "歷史不足" in (_v.skipped_reason or "")

    def test_never_raises(self):
        """單一檔的問題不該讓整份推播失敗。"""
        for _bad in (None, pd.DataFrame(), pd.DataFrame({"close": ["x"] * 30})):
            assert isinstance(evaluate_ticker("X", _bad), TickerVerdict)

    def test_data_date_is_reported(self):
        """訊息要標資料日期 —— 假日跑 cron 時使用者才看得出是舊資料。"""
        _v = evaluate_ticker("2330", _series_df([100.0] * 25))
        assert _v.data_date and _v.data_date.startswith("2026-")


# ════════════════════════════════════════════════════════════════════
# 5. 三維出場：誠實回報評估了幾維
# ════════════════════════════════════════════════════════════════════
class TestExitDimsHonesty:

    def test_dims_counted_when_only_tech(self):
        """v1 常態：籌碼無欄、新聞無 Gemini → 只評到 1 維。"""
        _v = evaluate_ticker("2330", _series_df([100.0] * 30))
        assert _v.evaluated_dims == 1, (
            "只有技術面可評時卻宣稱評了多維 → score 會被誤讀成三維結論"
        )

    def test_dims_counted_with_chip_and_news(self):
        _v = evaluate_ticker(
            "2330", _series_df([100.0] * 30),
            chip_signal="🔴 大戶倒貨",
            news={"label": "利空", "confidence": 80, "reason": "x"},
        )
        assert _v.evaluated_dims == 3

    def test_actionable_score_matches_existing_levels(self):
        """門檻必須是既有 `_LEVELS` 裡「需要行動」的那一級（🟠 建議減碼）。

        user 裁示：沿用既有分級，不另立新常數。這條釘住兩者一致 ——
        若哪天 `_LEVELS` 的語意改了，這裡要跟著重新對齊。
        """
        from src.compute.scoring.exit_signals import _LEVELS

        assert EXIT_SIGNAL_ACTIONABLE_SCORE in _LEVELS
        _icon, _label, _ = _LEVELS[EXIT_SIGNAL_ACTIONABLE_SCORE]
        assert _label == "建議減碼", (
            f"門檻對應的既有語意已變成「{_label}」，"
            "請重新確認推播分界是否仍在對的地方"
        )
        # 且下一級（1）必須是「不需行動」的觀察級，否則門檻設太高
        assert _LEVELS[EXIT_SIGNAL_ACTIONABLE_SCORE - 1][1] == "留意觀察"


# ════════════════════════════════════════════════════════════════════
# 6. ScanResult 聚合：全部失敗 ≠ 全部安全
# ════════════════════════════════════════════════════════════════════
class TestScanResult:

    def test_all_skipped_flag(self):
        """§1 最危險的一格：全部抓不到時**不可**推「今日無觸發」。"""
        _r = scan_watchlist([
            evaluate_ticker("A", None),
            evaluate_ticker("B", None),
        ])
        assert _r.all_skipped is True
        assert _r.n_evaluated == 0
        assert len(_r.skipped) == 2

    def test_partial_failure_is_not_all_skipped(self):
        _r = scan_watchlist([
            evaluate_ticker("A", None),
            evaluate_ticker("B", _series_df([100.0] * 30)),
        ])
        assert _r.all_skipped is False and _r.n_evaluated == 1

    def test_empty_watchlist_is_not_all_skipped(self):
        """空清單不是「全部失敗」—— 是「你根本沒在追蹤任何東西」。"""
        _r = scan_watchlist([])
        assert _r.all_skipped is False and _r.verdicts == ()

    def test_fired_subset(self):
        _r = scan_watchlist([
            evaluate_ticker("A", _series_df([100.0] * 21 + [80.0])),
            evaluate_ticker("B", _series_df([100.0] * 30)),
            evaluate_ticker("C", None),
        ])
        assert [v.ticker for v in _r.fired] == ["A"]
        assert _r.n_evaluated == 2

    def test_data_dates_deduped(self):
        _r = scan_watchlist([
            evaluate_ticker("A", _series_df([100.0] * 30)),
            evaluate_ticker("B", _series_df([100.0] * 30)),
        ])
        assert len(_r.data_dates) == 1, "同一資料日應去重"


# ════════════════════════════════════════════════════════════════════
# 7. L2 純度守衛
# ════════════════════════════════════════════════════════════════════
def test_module_has_no_io_or_ui_imports():
    """L2：不得 import requests / streamlit / src.data / src.ui（§8.2）。

    走 AST —— 本模組 docstring 大量引用 `src.data.stock.picker_fetcher` 等
    路徑說明資料從哪來，字串掃描保證假紅燈。
    """
    import ast

    import src.compute.notify.watchlist_triggers as _m

    _tree = ast.parse(open(_m.__file__, encoding="utf-8").read())
    _mods: set[str] = set()
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Import):
            _mods.update(a.name for a in _n.names)
        elif isinstance(_n, ast.ImportFrom) and _n.module:
            _mods.add(_n.module)

    _banned = ("requests", "streamlit", "yfinance", "FinMind", "src.data", "src.ui")
    _hits = sorted(m for m in _mods
                   if any(m == b or m.startswith(b + ".") for b in _banned))
    assert not _hits, f"L2 純函式出現 I/O / UI import：{_hits}"


def test_scan_result_is_frozen():
    with pytest.raises(Exception):
        ScanResult().verdicts = ()  # type: ignore[misc]
