"""tests/test_daily_signal_push.py — 每日選股訊號推播守衛(v20-PUSH)。

守純函式契約(技術快照 / 組字 / 分塊)+ Telegram 送信 fail-loud;全程隔絕網路。
orchestrator(scripts/push_daily_signals.py)為薄 glue,靠上述純函式 + 各 L1/L3
自身測試覆蓋,不在此重測。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


# ── 技術快照:趨勢 / 缺料不臆造 ─────────────────────────────────
def _uptrend_df(n=250):
    idx = pd.date_range("2025-07-01", periods=n, freq="D")
    base = np.linspace(80, 120, n)
    return pd.DataFrame({"Open": base, "High": base + 1, "Low": base - 1,
                         "Close": base, "Volume": 1000}, index=idx)


def test_technical_snapshot_uptrend():
    from src.compute.notify.technical_snapshot import build_technical_snapshot
    snap = build_technical_snapshot(_uptrend_df())
    assert snap["ok"] is True
    assert snap["ma_bull"] is True                 # price>ma5>ma20>ma60
    assert snap["bias20_pct"] > 0                  # 站上 MA20
    assert snap["ma20"] is not None and snap["macd_hist"] is not None


def test_technical_snapshot_empty_and_short():
    from src.compute.notify.technical_snapshot import build_technical_snapshot
    assert build_technical_snapshot(pd.DataFrame())["ok"] is False
    assert build_technical_snapshot(None)["ok"] is False
    short = build_technical_snapshot(_uptrend_df(10))
    assert short["ok"] is True
    assert short["ma20"] is None and short["rsi"] is None   # 不足 → None,不臆造


# ── 組字:正常 / 缺技術 / 空清單 ──────────────────────────────────
def test_format_signal_message():
    from src.compute.notify.signal_message import format_signal_message
    picks = [{"代碼": "2330", "名稱": "台積電", "綜合分": 88.0, "EPS分": 90.0},
             {"代碼": "2317", "名稱": "鴻海", "綜合分": 71.0}]
    tech = {"2330": {"ok": True, "price": 592.0, "ma_bull": True, "bias20_pct": 2.3,
                     "rsi": 61.0, "kd_gold": True, "macd_hist": 0.8},
            "2317": {"ok": False}}       # 缺技術
    msg = format_signal_message(picks, tech, as_of="2026-07-25 14:40")
    assert "2330 台積電" in msg and "綜合分 88" in msg
    assert "RSI 61" in msg and "距月線 +2.3%" in msg and "592元" in msg
    assert "技術資料不足" in msg          # 2317 缺技術 → 明示不臆造
    assert "🟢" in msg and "⚪" in msg     # 趨勢燈號(客觀 MA 排列)
    assert "基本面" not in msg            # 精簡:不列基本面內部分數(綜合分已代表)
    assert "MACD" not in msg              # 精簡:MACD 原始值(隨股價亂跳)不列


def test_no_nan_leak():
    """v20-PUSH.1 回歸釘:缺料因子在 pandas 裡是 NaN(非 None)→ 不得印出「nan」。"""
    from src.compute.notify.signal_message import format_signal_message
    picks = [{"代碼": "6223", "名稱": "", "綜合分": 85.8, "估值分": float("nan")}]
    tech = {"6223": {"ok": True, "price": 5705, "ma_bull": False,
                     "bias20_pct": float("nan"), "rsi": 43.0, "kd_gold": True}}
    msg = format_signal_message(picks, tech, as_of="x")
    assert "nan" not in msg.lower()       # NaN 一律不外流
    assert "距月線" not in msg             # bias=NaN → 該欄略過(不腦補)
    assert "RSI 43" in msg                 # 有值的照顯示
    assert "6223" in msg and "綜合分 85.8" in msg


def test_format_empty_message():
    from src.compute.notify.signal_message import format_empty_message
    msg = format_empty_message(as_of="2026-07-25 14:40", reason="季快照未就緒")
    assert "今日無訊號" in msg and "季快照未就緒" in msg


# ── 趨勢徽章:財報變好/變差 + 缺貨動能 ───────────────────────────
def test_fundamental_trend_badge():
    from src.compute.notify.signal_message import format_fundamental_trend
    assert format_fundamental_trend({"favorable_count": 4, "favorable_of": 4}) == "📈財報變好"
    assert format_fundamental_trend({"favorable_count": 0, "favorable_of": 4}) == "📉財報轉弱"
    assert format_fundamental_trend({"favorable_count": 2, "favorable_of": 4}) == "➡️財報持平"
    assert format_fundamental_trend({"favorable_count": 0, "favorable_of": 0}) == ""   # 無資料不臆造
    assert format_fundamental_trend(None) == ""


def test_shortage_badge():
    from shared.shortage_screen_thresholds import (
        TIER_INSUFFICIENT, TIER_MID, TIER_STRONG, TIER_WEAK,
    )

    from src.compute.notify.signal_message import format_shortage_badge
    assert format_shortage_badge(TIER_STRONG) == "缺貨強"
    assert format_shortage_badge(TIER_MID) == "缺貨中"
    assert format_shortage_badge(TIER_WEAK) == "缺貨弱"
    assert format_shortage_badge(TIER_INSUFFICIENT) == ""   # 資料不足 → 略(不臆造)
    assert format_shortage_badge(None) == ""


def test_format_message_with_trend_and_shortage():
    from shared.shortage_screen_thresholds import TIER_STRONG

    from src.compute.notify.signal_message import format_signal_message
    picks = [{"代碼": "6944", "名稱": "兆聯實業", "綜合分": 80.4}]
    tech = {"6944": {"ok": True, "price": 786, "ma_bull": True, "bias20_pct": 4.2,
                     "rsi": 55, "kd_gold": True}}
    msg = format_signal_message(
        picks, tech, as_of="2026-07-25 14:40",
        trend_by_code={"6944": {"favorable_count": 4, "favorable_of": 4}},
        shortage_by_code={"6944": TIER_STRONG})
    assert "📈財報變好" in msg          # 財報趨勢徽章(標題行)
    assert "缺貨強" in msg               # 缺貨徽章(技術行尾)
    assert "786元" in msg and "6944 兆聯實業" in msg


# ── 籌碼徽章:法人流向 + 大戶持股比例%(v20-PUSH.3)──────────────
def test_format_chip_line():
    from src.compute.notify.signal_message import format_chip_line
    # 法人流向(吸籌) + 大戶比例上升
    c = {"flow": {"signal": "🔥 大戶吸籌", "error": None}, "holder": {"pct": 45.23, "delta": 0.8}}
    assert format_chip_line(c) == "籌碼 🔥 大戶吸籌 · 大戶45.2%↑"
    # 只有大戶比例(下降)
    assert format_chip_line({"flow": None, "holder": {"pct": 30.0, "delta": -1.2}}) == "籌碼 大戶30.0%↓"
    # 只有法人流向(倒貨)
    assert format_chip_line({"flow": {"signal": "🔴 大戶倒貨", "error": None},
                             "holder": None}) == "籌碼 🔴 大戶倒貨"
    # 大戶比例平盤(|Δ|≤0.05 不加箭頭)、delta 缺
    assert format_chip_line({"flow": None, "holder": {"pct": 40.0, "delta": None}}) == "籌碼 大戶40.0%"
    assert format_chip_line({"flow": None, "holder": {"pct": 40.0, "delta": 0.02}}) == "籌碼 大戶40.0%"
    # 資料不足 / error 的 flow → 略(不臆造)
    assert format_chip_line({"flow": {"signal": "⚫ 資料不足", "error": "df法人欄全為0"},
                             "holder": None}) == ""
    # 全缺 / None → ''
    assert format_chip_line({"flow": None, "holder": None}) == ""
    assert format_chip_line(None) == ""
    # nan pct → 略(§1 不印 nan)
    assert format_chip_line({"flow": None, "holder": {"pct": float("nan"), "delta": None}}) == ""


def test_format_message_with_chips():
    from src.compute.notify.signal_message import format_signal_message
    picks = [{"代碼": "6223", "名稱": "旺矽", "綜合分": 84.2}]
    tech = {"6223": {"ok": True, "price": 5705, "ma_bull": False, "bias20_pct": -10.5,
                     "rsi": 43, "kd_gold": True}}
    chip = {"6223": {"flow": {"signal": "🔥 大戶吸籌", "error": None},
                     "holder": {"pct": 45.2, "delta": 0.8}}}
    msg = format_signal_message(picks, tech, as_of="x", chip_by_code=chip)
    assert "籌碼 🔥 大戶吸籌 · 大戶45.2%↑" in msg     # 第 3 行
    # 未傳 chip → 不印第 3 行(向後相容,舊 caller 無感)
    assert "籌碼" not in format_signal_message(picks, tech, as_of="x")


# ── AI 研判 prompt:餵事實、禁腦補、附免責(v20-PUSH.3)──────────
def test_ai_judgment_fact_lines():
    from src.compute.notify.ai_judgment import build_fact_lines
    picks = [{"代碼": "2330", "名稱": "台積電", "綜合分": 88.0}]
    tech = {"2330": {"ok": True, "price": 592.0, "ma_bull": True, "bias20_pct": 2.3,
                     "rsi": 61.0, "kd_gold": True}}
    lines = build_fact_lines(
        picks, tech,
        trend_by_code={"2330": {"favorable_count": 4, "favorable_of": 4}},
        chip_by_code={"2330": {"flow": {"signal": "🔥 大戶吸籌", "error": None},
                               "holder": {"pct": 45.2, "delta": 0.8}}})
    assert len(lines) == 1
    _l = lines[0]
    assert "2330 台積電" in _l and "均線多頭排列" in _l and "綜合分88" in _l
    assert "📈財報變好" in _l and "大戶45.2%" in _l and "🔥 大戶吸籌" in _l


def test_ai_judgment_prompt():
    from src.compute.notify.ai_judgment import build_ai_judgment_prompt
    picks = [{"代碼": "2330", "名稱": "台積電", "綜合分": 88.0}]
    tech = {"2330": {"ok": True, "price": 592.0, "ma_bull": True, "rsi": 61.0, "kd_gold": True}}
    prompt = build_ai_judgment_prompt(picks, tech, as_of="2026-07-25 17:00")
    assert "偏多" in prompt and "偏空" in prompt and "需觀察" in prompt
    assert "禁止" in prompt                 # 反捏造約束
    assert "非投資建議" in prompt            # 免責
    assert "<Data>" in prompt and "2330 台積電" in prompt
    # 空清單 → 明講,不硬掰
    assert "今日無入選股" in build_ai_judgment_prompt([], {}, as_of="x")


# ── orchestrator AI glue:缺 key 略過 / 有 key 附段(薄 glue,只守關鍵契約)──
def test_maybe_ai_judgment_no_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import scripts.push_daily_signals as ps
    out = ps._maybe_ai_judgment(
        [{"代碼": "2330", "名稱": "台積電", "綜合分": 88}], {},
        as_of="x", trend_by={}, short_by={}, chip_by={})
    assert out == ""            # §1:缺 key → 只送清單,不炸、不附段


def test_maybe_ai_judgment_with_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    import src.services.ai_fetcher as af
    monkeypatch.setattr(af, "post_gemini",
                        lambda *a, **k: ("🤖 AI 研判\n**偏多**\n- 2330 台積電:均線多頭",
                                         "gemini-2.5-flash"))
    import scripts.push_daily_signals as ps
    out = ps._maybe_ai_judgment(
        [{"代碼": "2330", "名稱": "台積電", "綜合分": 88}],
        {"2330": {"ok": True, "price": 592, "ma_bull": True, "rsi": 61, "kd_gold": True}},
        as_of="x", trend_by={}, short_by={}, chip_by={})
    assert out.startswith("\n\n") and "AI 研判" in out and "2330 台積電" in out


# ── 分塊(Telegram / LINE 共用)──────────────────────────────────
def test_split_chunks():
    from src.data.notify.chunk import split_chunks
    assert split_chunks("", 100) == []
    assert split_chunks("abc", 100) == ["abc"]
    long = "\n".join(["行" * 100 for _ in range(200)])   # ~20000 字
    chunks = split_chunks(long, 1000)
    assert len(chunks) > 1 and all(len(c) <= 1000 for c in chunks)


class _Resp:
    def __init__(self, code, text=""):
        self.status_code = code
        self.text = text


# ── Telegram(備援管道):fail-loud ─────────────────────────────────
def test_telegram_missing_token_raises(monkeypatch):
    from src.data.notify import telegram_notify as tn
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    with pytest.raises(ValueError):
        tn.send_telegram_message("hi")      # §1:缺 secret → raise,不靜默


def test_telegram_ok_and_http_error(monkeypatch):
    from src.data.notify import telegram_notify as tn
    monkeypatch.setattr(tn.requests, "post", lambda url, **kw: _Resp(200))
    assert tn.send_telegram_message("hello", token="T", chat_id="C") == 1
    monkeypatch.setattr(tn.requests, "post", lambda url, **kw: _Resp(403, "forbidden"))
    with pytest.raises(RuntimeError):
        tn.send_telegram_message("hello", token="T", chat_id="C")


# ── LINE(主管道,Messaging API):fail-loud ───────────────────────
def test_line_missing_token_raises(monkeypatch):
    from src.data.notify import line_notify as ln
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("LINE_USER_ID", raising=False)
    with pytest.raises(ValueError):
        ln.send_line_message("hi")          # §1:缺 secret → raise


def test_line_ok_and_http_error(monkeypatch):
    from src.data.notify import line_notify as ln
    _seen = {}

    def _ok(url, **kw):
        _seen["msgs"] = kw["json"]["messages"]     # 記錄 message 物件
        return _Resp(200)

    monkeypatch.setattr(ln.requests, "post", _ok)
    n = ln.send_line_message("hello", token="T", to="U")
    assert n == 1 and _seen["msgs"][0]["type"] == "text"
    monkeypatch.setattr(ln.requests, "post", lambda url, **kw: _Resp(401, "unauthorized"))
    with pytest.raises(RuntimeError):
        ln.send_line_message("hello", token="T", to="U")


# ── dispatch:依 NOTIFY_CHANNEL 路由 ─────────────────────────────
def test_dispatch_routes_by_channel(monkeypatch):
    import src.data.notify.line_notify as ln
    import src.data.notify.telegram_notify as tn
    from src.data.notify.dispatch import send_notification

    _hit = {"line": 0, "tg": 0}
    monkeypatch.setattr(ln, "send_line_message", lambda t, **k: _hit.__setitem__("line", _hit["line"] + 1) or 1)
    monkeypatch.setattr(tn, "send_telegram_message", lambda t, **k: _hit.__setitem__("tg", _hit["tg"] + 1) or 1)

    send_notification("x", channel="line")
    send_notification("x", channel="telegram")
    monkeypatch.setenv("NOTIFY_CHANNEL", "line")
    send_notification("x")                      # 讀 env 預設
    assert _hit == {"line": 2, "tg": 1}
    with pytest.raises(ValueError):
        send_notification("x", channel="sms")   # 未知管道 → raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
