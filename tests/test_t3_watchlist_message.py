"""T3(2026-08)— 觀察池推播組字測試。

受測：`src/compute/notify/watchlist_message.py`

本檔的重點**不是**排版好不好看，而是四件 §1 的事：
  1. 「全部抓不到」絕不可被說成「今日無觸發」
  2. 「觀察池是空的」必須與「有清單但沒訊號」區分
  3. 未評估的檔必須逐檔列出原因，不靜默吞掉
  4. 三維出場只評到 1 維時，必須講出來（否則會被讀成三維綜合結論）

深連結是流程圖層次 4「二次分析」的接點，故也在此釘住格式。
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.compute.notify.watchlist_message import (
    build_deep_link,
    format_empty_watchlist,
    format_quiet_health_check,
    format_scan_failure,
    format_watchlist_alert,
)
from src.compute.notify.watchlist_triggers import evaluate_ticker, scan_watchlist

_URL = "https://my-stock-dashboard-namd8rh9b8sn3qzdjshzfa.streamlit.app/"


def _df(closes: list[float]):
    return pd.DataFrame(
        {"close": closes},
        index=pd.date_range("2026-08-01", periods=len(closes), freq="D"),
    )


def _fired_scan():
    return scan_watchlist([
        evaluate_ticker("2330", _df([100.0] * 21 + [80.0]), name="台積電"),
        evaluate_ticker("2454", _df([100.0] * 30), name="聯發科"),
    ])


# ════════════════════════════════════════════════════════════════════
# 1. 深連結（層次 4 接點）
# ════════════════════════════════════════════════════════════════════
class TestDeepLink:

    def test_basic(self):
        assert build_deep_link(_URL, "2330").endswith("?sid=2330")

    def test_no_trailing_slash(self):
        assert build_deep_link("https://x.app", "2330") == "https://x.app?sid=2330"

    def test_existing_query_uses_ampersand(self):
        assert build_deep_link("https://x.app/?a=1", "2330") == "https://x.app/?a=1&sid=2330"

    @pytest.mark.parametrize("url,ticker", [("", "2330"), (_URL, ""), ("", ""), (None, "2330")])
    def test_missing_parts_return_empty(self, url, ticker):
        """§1：寧可不印連結，也不要印一個壞掉的 URL。"""
        assert build_deep_link(url, ticker) == ""

    def test_alert_omits_link_when_no_url(self):
        _msg = format_watchlist_alert(_fired_scan(), as_of="2026-08-14 17:00", app_url="")
        assert "🔗" not in _msg


# ════════════════════════════════════════════════════════════════════
# 2. §1：全部失敗 ≠ 今日無觸發（最重要）
# ════════════════════════════════════════════════════════════════════
class TestScanFailureHonesty:

    def test_says_it_did_not_monitor(self):
        _msg = format_scan_failure(as_of="2026-08-14 17:00", n_total=12)
        assert "沒有做任何判斷" in _msg
        assert "不等於" in _msg and "沒事" in _msg, (
            "失敗訊息沒有明講『這不等於今天沒事』→ 使用者會據此不看盤"
        )

    def test_never_says_no_trigger(self):
        """失敗訊息**不得**出現任何「無觸發 / 無訊號」字樣。"""
        _msg = format_scan_failure(as_of="x", n_total=5)
        for _lie in ("無觸發", "無訊號", "一切正常", "運作正常"):
            assert _lie not in _msg, f"失敗訊息出現誤導字樣「{_lie}」"

    def test_includes_diagnosis_hint(self):
        assert "quota" in format_scan_failure(as_of="x", n_total=1).lower()

    def test_detail_is_appended(self):
        assert "ConnectionError" in format_scan_failure(
            as_of="x", n_total=1, detail="ConnectionError: timeout")


# ════════════════════════════════════════════════════════════════════
# 3. §1：空清單 ≠ 沒訊號
# ════════════════════════════════════════════════════════════════════
class TestEmptyWatchlist:

    def test_says_nothing_was_monitored(self):
        _msg = format_empty_watchlist(as_of="2026-08-14 17:00")
        assert "0 檔" in _msg and "沒有監控任何東西" in _msg

    def test_never_says_no_trigger(self):
        _msg = format_empty_watchlist(as_of="x")
        for _lie in ("無觸發", "無訊號", "運作正常"):
            assert _lie not in _msg

    def test_source_hint_appended(self):
        assert "CSV" in format_empty_watchlist(as_of="x", source_hint="公開 CSV 讀到 0 列")


# ════════════════════════════════════════════════════════════════════
# 4. §1：未評估逐檔列出
# ════════════════════════════════════════════════════════════════════
class TestSkippedDisclosure:

    def _scan_with_skips(self):
        return scan_watchlist([
            evaluate_ticker("2330", _df([100.0] * 21 + [80.0]), name="台積電"),
            evaluate_ticker("6666", _df([100.0] * 5), name="新上市"),
            evaluate_ticker("9999", None, name="抓不到"),
        ])

    def test_alert_lists_skipped(self):
        _msg = format_watchlist_alert(self._scan_with_skips(), as_of="x", app_url=_URL)
        assert "未評估 2 檔" in _msg
        assert "6666" in _msg and "9999" in _msg
        assert "歷史不足" in _msg and "抓不到" in _msg

    def test_skipped_marked_as_not_safe(self):
        """未評估區塊必須明講「不代表沒事」。"""
        _msg = format_watchlist_alert(self._scan_with_skips(), as_of="x")
        assert "不代表沒事" in _msg

    def test_health_check_also_lists_skipped(self):
        """健康碼也要帶未評估 —— 否則「監控 10 檔」本身就是誤導。"""
        _msg = format_quiet_health_check(self._scan_with_skips(), as_of="x")
        assert "未評估 2 檔" in _msg

    def test_no_skipped_block_when_all_evaluated(self):
        _msg = format_watchlist_alert(_fired_scan(), as_of="x")
        assert "未評估" not in _msg


# ════════════════════════════════════════════════════════════════════
# 5. §1：三維只評到部分維度時要講
# ════════════════════════════════════════════════════════════════════
class TestExitDimDisclosure:

    def test_partial_dims_disclosed(self):
        """籌碼+新聞皆缺 → 三維觸發時必須標「只評估了 N/3 維」。"""
        _scan = scan_watchlist([
            evaluate_ticker(
                "2330", _df([100.0] * 21 + [80.0]), name="台積電",
                news={"label": "利空", "confidence": 90, "reason": "測試"},
            ),
        ])
        _msg = format_watchlist_alert(_scan, as_of="x")
        assert "/3 維" in _msg, "三維出場觸發卻沒說明實際評估幾維"


# ════════════════════════════════════════════════════════════════════
# 6. 內容完整性
# ════════════════════════════════════════════════════════════════════
class TestAlertContent:

    def test_has_data_date(self):
        """假日跑 cron 時，使用者要能一眼看出是舊資料。"""
        assert "資料日 2026-" in format_watchlist_alert(_fired_scan(), as_of="x")

    def test_flags_unsynced_dates(self):
        _scan = scan_watchlist([
            evaluate_ticker("A", _df([100.0] * 30)),
            evaluate_ticker(
                "B",
                pd.DataFrame({"close": [100.0] * 30},
                             index=pd.date_range("2026-07-01", periods=30, freq="D")),
            ),
        ])
        assert "不同步" in format_quiet_health_check(_scan, as_of="x")

    def test_counts_are_reported(self):
        _msg = format_watchlist_alert(_fired_scan(), as_of="x")
        assert "監控 2 檔" in _msg and "觸發 1 檔" in _msg

    def test_only_fired_tickers_in_body(self):
        _msg = format_watchlist_alert(_fired_scan(), as_of="x", app_url=_URL)
        assert "2330" in _msg
        assert "sid=2454" not in _msg, "沒觸發的檔不該出現在觸發區塊"

    def test_disclaimer_present(self):
        assert "非買賣建議" in format_watchlist_alert(_fired_scan(), as_of="x")

    def test_reasons_are_included(self):
        assert "跌破 MA20" in format_watchlist_alert(_fired_scan(), as_of="x")

    def test_health_check_period_label(self):
        _msg = format_quiet_health_check(_fired_scan(), as_of="x", period_label="今日")
        assert "今日監控" in _msg


# ════════════════════════════════════════════════════════════════════
# 7. L2 純度
# ════════════════════════════════════════════════════════════════════
def test_module_has_no_io_or_ui_imports():
    import ast

    import src.compute.notify.watchlist_message as _m

    _tree = ast.parse(open(_m.__file__, encoding="utf-8").read())
    _mods: set[str] = set()
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Import):
            _mods.update(a.name for a in _n.names)
        elif isinstance(_n, ast.ImportFrom) and _n.module:
            _mods.add(_n.module)
    _banned = ("requests", "streamlit", "yfinance", "src.data", "src.ui")
    _hits = sorted(m for m in _mods
                   if any(m == b or m.startswith(b + ".") for b in _banned))
    assert not _hits, f"L2 純函式出現 I/O / UI import：{_hits}"
