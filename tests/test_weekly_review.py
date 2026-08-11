"""tests/test_weekly_review.py — 每週組合週報 L2 prompt + L3 service。

L2:prompt 硬約束 + 逐檔事實組字。L3:大盤定調 headless、AI 失敗仍送真實數據(§1)、
訊息格式。AI/取價/體檢皆 monkeypatch(不觸網)。
"""
from __future__ import annotations

import pandas as pd

import src.services.weekly_review_service as svc
from src.compute.notify.weekly_review_prompt import (
    build_holding_fact_lines,
    build_weekly_review_prompt,
)


# ── L2 prompt ───────────────────────────────────────────────────────────
def test_fact_lines_from_rows():
    rows = [{"代號": "00980A", "類型": "ETF", "燈號": "🚨 連續3季輸盤",
             "相對基準%": -12.3, "連敗季數": 3}]
    lines = build_holding_fact_lines(rows)
    assert "00980A ETF" in lines[0]
    assert "🚨 連續3季輸盤" in lines[0]
    assert "相對基準-12.3%" in lines[0]
    assert "連敗3季" in lines[0]


def test_prompt_has_guardrails_and_blocks():
    p = build_weekly_review_prompt(
        ["加權指數 收 20,000｜站上年線"],
        [{"代號": "A", "類型": "個股", "燈號": "🟢 體質正常"}],
        as_of="2026-08-11")
    assert "絕對禁止" in p and "非投資建議" in p          # §1 硬約束
    assert "站上年線" in p                                # 有餵大盤
    assert "A 個股" in p                                  # 有餵逐檔
    assert "2026-08-11" in p


def test_prompt_empty_holdings_graceful():
    p = build_weekly_review_prompt([], [], as_of="x")
    assert "清單無標的或皆無資料" in p


# ── L3 macro-lite ───────────────────────────────────────────────────────
def _twii_df(n=300):
    idx = pd.bdate_range(end="2026-08-07", periods=n)
    return pd.DataFrame({"Close": [10000 + i * 10 for i in range(n)]}, index=idx)


def test_macro_lite_above_year_line(monkeypatch):
    monkeypatch.setattr(svc, "fetch_etf_price", lambda *a, **k: _twii_df())
    lines = svc._macro_lite_lines()
    assert any("加權指數 收" in l for l in lines)
    assert any("站上年線" in l for l in lines)
    assert any("近20交易日" in l for l in lines)


def test_macro_lite_unavailable_honest(monkeypatch):
    monkeypatch.setattr(svc, "fetch_etf_price", lambda *a, **k: None)
    assert svc._macro_lite_lines() == ["加權指數：資料暫時無法取得"]


# ── L3 build_weekly_review ──────────────────────────────────────────────
def _patch_common(monkeypatch, rows):
    monkeypatch.setattr(svc, "fetch_etf_price", lambda *a, **k: _twii_df())
    monkeypatch.setattr(svc, "get_watchlist_health_rows", lambda t, **k: rows)


def test_build_review_ai_success(monkeypatch):
    _patch_common(monkeypatch, [{"代號": "00980A", "類型": "ETF",
                                 "燈號": "🚨 連續3季輸盤", "相對基準%": -12.0, "連敗季數": 3}])
    monkeypatch.setattr(svc, "post_gemini", lambda key, prompt, **k: ("AI 建議內容", "gemini-x"))
    rv = svc.build_weekly_review(["00980A"], api_key="k", as_of="2026-08-11")
    assert rv["ai_text"] == "AI 建議內容"
    assert rv["rows"] and rv["macro_lines"]


def test_build_review_ai_failure_still_returns_real_data(monkeypatch):
    """§1:AI quota/失敗 → ai_text None,但真實數據(rows/macro)仍在。"""
    _patch_common(monkeypatch, [{"代號": "A", "類型": "個股", "燈號": "🟢 體質正常"}])
    monkeypatch.setattr(svc, "post_gemini", lambda key, prompt, **k: (None, "quota"))
    rv = svc.build_weekly_review(["A"], api_key="k")
    assert rv["ai_text"] is None and rv["ai_err"] == "quota"
    assert rv["rows"] and rv["macro_lines"]


def test_build_review_no_api_key_skips_ai(monkeypatch):
    _patch_common(monkeypatch, [])
    _calls = {"n": 0}

    def _pg(*a, **k):
        _calls["n"] += 1
        return ("x", "m")
    monkeypatch.setattr(svc, "post_gemini", _pg)
    rv = svc.build_weekly_review(["A"], api_key=None)
    assert rv["ai_text"] is None and _calls["n"] == 0


# ── L3 format_weekly_message ────────────────────────────────────────────
def test_format_message_laggards_ai_and_disclaimer():
    review = {"macro_lines": ["加權指數 收 20,000", "站上年線"],
              "rows": [{"代號": "00980A", "燈號": "🚨 連續3季輸盤", "相對基準%": -12.0},
                       {"代號": "B", "燈號": "🟢 體質正常"}],
              "ai_text": "AI 建議段落"}
    msg = svc.format_weekly_message(review, as_of="2026-08-11")
    assert "本週組合週報（2026-08-11）" in msg
    assert "00980A" in msg and "🚨" in msg and "亮警示 1/2" in msg
    assert "AI 建議段落" in msg
    assert "非投資建議" in msg


def test_format_message_ai_absent_still_sends_real_data():
    review = {"macro_lines": ["加權指數 收 20,000"],
              "rows": [{"代號": "00980A", "燈號": "🔴 雙向弱勢", "相對基準%": -5.0}],
              "ai_text": None}
    msg = svc.format_weekly_message(review)
    assert "00980A" in msg and "🔴" in msg              # 真實數據仍送
    assert "AI 研判本次未產生" in msg


def test_format_message_all_normal():
    review = {"macro_lines": ["加權指數 收 20,000"],
              "rows": [{"代號": "A", "燈號": "🟢 體質正常"}],
              "ai_text": None}
    msg = svc.format_weekly_message(review)
    assert "均無連續落後" in msg
