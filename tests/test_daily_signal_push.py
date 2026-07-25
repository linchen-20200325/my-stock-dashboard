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
