"""tests/test_asset_lag.py — 資產分類 / 基準對映 / 落後燈號 純函式測試(L2)。

守衛「組合體檢」判定核心:個股 vs ^TWII、ETF vs 0050;落後燈號對 ETF 與個股共用同一份
SSOT(不再因 is_active gate 讓個股拿不到燈號);§1 缺資料誠實回「無法判定」不猜。
"""
from __future__ import annotations

from shared.signal_thresholds import (
    PORTFOLIO_BENCHMARK_TICKER,
    STOCK_BENCHMARK_TICKER,
)
from src.compute.etf.asset_lag import (
    ASSET_ETF,
    ASSET_STOCK,
    ASSET_UNKNOWN,
    classify_asset_kind,
    classify_lag_verdict,
    pick_benchmark,
)


# ── classify_asset_kind ────────────────────────────────────────────────
def test_classify_etf_00_prefix():
    for t in ["0050", "0050.TW", "00878.TW", "00980A.TW", "00980D.TWO", "006208.TW"]:
        assert classify_asset_kind(t) == ASSET_ETF, t


def test_classify_stock_four_digit():
    for t in ["2330", "2330.TW", "2454", "6488.TWO", "1101", "9910.TW"]:
        assert classify_asset_kind(t) == ASSET_STOCK, t


def test_classify_unknown_non_tw():
    for t in ["^TWII", "^GSPC", "SPY", "", None]:
        assert classify_asset_kind(t) == ASSET_UNKNOWN, t


# ── pick_benchmark ─────────────────────────────────────────────────────
def test_pick_benchmark_mapping():
    assert pick_benchmark(ASSET_ETF) == PORTFOLIO_BENCHMARK_TICKER == "0050.TW"
    assert pick_benchmark(ASSET_STOCK) == STOCK_BENCHMARK_TICKER == "^TWII"
    assert pick_benchmark(ASSET_UNKNOWN) is None


def test_benchmark_end_to_end_user_intent():
    """使用者要求:ETF 只跟 0050、個股只看大盤(^TWII)。"""
    assert pick_benchmark(classify_asset_kind("00980A.TW")) == "0050.TW"
    assert pick_benchmark(classify_asset_kind("2330.TW")) == "^TWII"


# ── classify_lag_verdict ───────────────────────────────────────────────
def _m(down=0.0, up=0.0, streak=0):
    return {"down_ratio": down, "up_ratio": up, "quarter_lose_streak": streak}


def test_verdict_streak_alert_stock_and_etf():
    """連續 ≥2 季輸盤 → 🚨,建議換大盤被動(ETF/個股同一份 SSOT)。"""
    v4 = classify_lag_verdict(_m(streak=4))
    assert v4["燈號"] == "🚨 連續4季輸盤"
    assert "0050" in v4["動作建議"]
    v2 = classify_lag_verdict(_m(streak=2))
    assert v2["燈號"] == "🚨 連續2季輸盤"
    assert "0050" in v2["動作建議"]


def test_verdict_streak_has_no_new_manager_exception():
    """Issue #1208:「新經理人 <6 月 → 再給時間」例外已移除(客戶取消換手策略)。

    連敗 ≥2 季一律建議換大盤被動,不存在任期輸入、也不存在「再給時間」文案。
    """
    v = classify_lag_verdict(_m(streak=3))
    assert "再給時間" not in v["動作建議"]
    assert "經理人" not in v["動作建議"]
    assert "0050" in v["動作建議"]


def test_verdict_dual_and_single_weakness():
    assert classify_lag_verdict(_m(down=80, up=80))["燈號"] == "🔴 雙向弱勢"
    assert classify_lag_verdict(_m(down=80, up=10))["燈號"] == "🟡 大跌弱勢"
    assert classify_lag_verdict(_m(down=10, up=80))["燈號"] == "🟡 反彈無力"


def test_verdict_normal():
    assert classify_lag_verdict(_m(down=10, up=10))["燈號"] == "🟢 體質正常"


def test_verdict_streak_takes_priority_over_ratios():
    """連敗季數優先於單日弱勢率(與原 etf_calc 判定順序一致)。"""
    v = classify_lag_verdict(_m(down=80, up=80, streak=3))
    assert v["燈號"].startswith("🚨")


def test_verdict_insufficient_or_bad_metrics_unknown():
    """§1:_err / 缺鍵 → ⚪ 無法判定,不猜。"""
    assert classify_lag_verdict({"_err": "insufficient_data", "sample": 5})["燈號"] == "⚪ 無法判定"
    assert classify_lag_verdict({})["燈號"] == "⚪ 無法判定"
    assert classify_lag_verdict(None)["燈號"] == "⚪ 無法判定"
    assert classify_lag_verdict({"down_ratio": 10})["燈號"] == "⚪ 無法判定"  # 缺鍵
