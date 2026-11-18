"""tests/test_a_etf_diag_three_fixes.py — 舊 UI ETF 診斷三項最小安全修復（GPT 核准 A 線，2026-11-18）。

① NAV 有值但過期／日期不明 ⇒ 不得 🟢、不得以 date.today() 冒充資料日；只用 payload 內可信的 NAV 日期。
② 海外 ETF（SPY/VOO/QQQ）AUM 缺值 ⇒ 誠實缺值句，不可宣稱台灣主動式／投信官網揭露。
③ 台股主動式 ETF 有「失敗證據」（payload `_err_*`）⇒ 紅燈＋明示句；無證據（舊 session）維持 ⚪。

離線 harness 重用 tests/test_a_likely_private_unknown.py（真實 render_etf_single → 真實 render_data_health_raw，
fetcher 全 monkeypatch、socket 全擋）。
"""
from __future__ import annotations

import datetime as _dt

import pytest

from tests.test_a_likely_private_unknown import (
    ACTIVE_MSG, AUM_MISSING, EXP_PASSIVE, IDENT_NOTE, NAV_NONE, NAV_STALE, OVERSEA_MSG,
    _all_text, _lights, _run,
)

ACTIVE_EXP = "SITCA、元大投信（僅主動式 ETF）、yfinance 均未取得可用費用率，暫時無法顯示。"
NAV_DATE_UNKNOWN = "NAV 已取得，但資料日期無法確認，暫不判定新鮮度。"
_NAV, _AUM, _EXP = "NAV 淨值", "ETF 規模 AUM", "ETF 費用率"


# ───────────────────────── ① NAV 新鮮度 ─────────────────────────
class TestNavFreshnessHonest:
    def test_value_stale_nav_kept_is_not_green(self, monkeypatch):
        """S3b：nav 值被保留（stale_reason=nav_value_stale）⇒ 不可 🟢／「今天」。"""
        r = _run(monkeypatch, {"ticker": "00878.TW", "input": "00878", "nav": "valuestale"})
        prem = r["payload"]["premium"]
        assert prem.get("stale_nav") is True and prem.get("nav") is not None   # 前提：舊 bug 路徑
        row = r["rows"][_NAV]
        assert row["light"] != "🟢", row
        assert "今天" not in row["text"], row
        assert NAV_STALE in row["text"], row

    def test_fresh_nav_uses_payload_date_not_today(self, monkeypatch):
        """有可信 NAV 日期 ⇒ 沿用既有新鮮度契約；日期＝payload 日期（改成 10 天前 ⇒ 不再綠）。"""
        old = _dt.date.today() - _dt.timedelta(days=10)

        def _m(p):
            p["premium"] = {**p["premium"], "nav_date": old, "data_date": old}
        r = _run(monkeypatch, {"ticker": "0050.TW", "input": "0050", "aum": 2e12,
                               "expense": 0.0046, "nav": "ok"}, mutate=_m)
        assert r["rows"][_NAV]["light"] != "🟢", r["rows"][_NAV]
        assert "今天" not in r["rows"][_NAV]["text"]

    def test_nav_present_but_date_unknown_not_green(self, monkeypatch):
        def _m(p):
            p["premium"] = {k: v for k, v in p["premium"].items()
                            if k not in ("nav_date", "data_date")}
        r = _run(monkeypatch, {"ticker": "0050.TW", "input": "0050", "aum": 2e12,
                               "expense": 0.0046, "nav": "ok"}, mutate=_m)
        assert r["payload"]["premium"].get("nav") is not None
        row = r["rows"][_NAV]
        assert row["light"] == "🔴", row
        assert NAV_DATE_UNKNOWN in row["text"], row
        assert "今天" not in row["text"]

    def test_fresh_nav_with_real_date_still_green(self, monkeypatch):
        r = _run(monkeypatch, {"ticker": "0050.TW", "input": "0050", "aum": 2e12,
                               "expense": 0.0046, "nav": "ok"})
        assert r["payload"]["premium"].get("nav_date") or r["payload"]["premium"].get("data_date")
        assert _lights(r) == ("🟢", "🟢", "🟢")


# ───────────────────────── ② 海外 AUM ─────────────────────────
class TestOverseasAumNoActiveClaim:
    @pytest.mark.parametrize("tk", ["SPY", "VOO", "QQQ"])
    def test_overseas_aum_missing_honest(self, monkeypatch, tk):
        r = _run(monkeypatch, {"ticker": tk, "input": tk})
        aum = r["rows"][_AUM]
        assert "主動式" not in aum["text"] and "投信官網" not in aum["text"], aum
        assert AUM_MISSING in aum["text"], aum
        assert IDENT_NOTE not in _all_text(r)
        # 費用率／NAV 真正不適用列保留
        assert r["rows"][_EXP] == {"light": "⚪", "text": "⚪ " + OVERSEA_MSG}
        assert r["rows"][_NAV] == {"light": "⚪", "text": "⚪ " + OVERSEA_MSG}

    def test_overseas_aum_present_green(self, monkeypatch):
        r = _run(monkeypatch, {"ticker": "SPY", "input": "SPY", "aum": 5e11})
        assert r["rows"][_AUM]["light"] == "🟢"

    def test_is_active_etf_not_rewritten_globally(self):
        from src.data.etf import is_active_etf
        assert is_active_etf("SPY") is True      # 全域分類刻意不動；僅診斷措辭改以海外身分優先


# ───────────────────────── ③ 台股主動式真失敗不被灰色遮蔽 ─────────────────────────
class TestTwActiveFailureNotMasked:
    def test_three_missing_evidenced_red(self, monkeypatch):
        r = _run(monkeypatch, {"ticker": "00981A.TW", "input": "00981A"})
        assert r["payload"]["_err_expense"] == ACTIVE_EXP
        assert _lights(r) == ("🔴", "🔴", "🔴"), r["rows"]
        assert ACTIVE_MSG[:20] not in _all_text(r)
        assert AUM_MISSING in r["rows"][_AUM]["text"]
        assert ACTIVE_EXP[:30] in r["rows"][_EXP]["text"]
        assert NAV_NONE in r["rows"][_NAV]["text"]
        assert "網路" not in _all_text(r)                 # 未知不虛稱網路錯誤

    def test_only_aum_present(self, monkeypatch):
        r = _run(monkeypatch, {"ticker": "00981A.TW", "input": "00981A", "aum": 5e10})
        assert _lights(r) == ("🟢", "🔴", "🔴")

    def test_complete_active_all_green(self, monkeypatch):
        r = _run(monkeypatch, {"ticker": "00981A.TW", "input": "00981A", "aum": 5e10,
                               "expense": 0.009, "nav": "ok"})
        assert _lights(r) == ("🟢", "🟢", "🟢")

    def test_old_session_payload_without_evidence_stays_grey(self, monkeypatch):
        def _old(p):
            for k in ("_err_expense", "_err_nav", "_err_aum"):
                p.pop(k, None)
        r = _run(monkeypatch, {"ticker": "00981A.TW", "input": "00981A"}, mutate=_old)
        for n in (_AUM, _EXP, _NAV):
            assert r["rows"][n] == {"light": "⚪", "text": "⚪ " + ACTIVE_MSG[:55]}, n

    def test_passive_three_missing_unchanged(self, monkeypatch):
        r = _run(monkeypatch, {"ticker": "0050.TW", "input": "0050"})
        assert _lights(r) == ("🔴", "🔴", "🔴")
        assert EXP_PASSIVE in r["rows"][_EXP]["text"]


# ───────────────────── QA NOTE-1／NOTE-2：NAV 有值時的措辭（台股主動式／海外）─────────────────────
def _strip_evidence(p):
    for k in ("_err_expense", "_err_nav", "_err_aum"):
        p.pop(k, None)


def _stale_keep_nav(p):
    p["premium"] = {**p["premium"], "stale_nav": True, "stale_reason": "nav_value_stale"}


def _no_date(p):
    p["premium"] = {k: v for k, v in p["premium"].items() if k not in ("nav_date", "data_date")}


def _old_date(p):
    old = _dt.date.today() - _dt.timedelta(days=10)
    p["premium"] = {**p["premium"], "nav_date": old, "data_date": old}


_ACT = {"ticker": "00981A.TW", "input": "00981A", "aum": 5e10, "expense": 0.009, "nav": "ok"}


class TestNavPresentWordingTwActiveAndOverseas:
    """NAV 有值時，台股主動式（新／舊 payload 皆同）顯示真實原因，不得顯示「公開資料受限」。"""

    @pytest.mark.parametrize("old_payload", [False, True])
    @pytest.mark.parametrize("name,mut,sentence", [
        ("stale", _stale_keep_nav, NAV_STALE),
        ("nodate", _no_date, NAV_DATE_UNKNOWN),
    ])
    def test_active_nav_present_reason(self, monkeypatch, old_payload, name, mut, sentence):
        def _m(p):
            mut(p)
            if old_payload:
                _strip_evidence(p)
        r = _run(monkeypatch, _ACT, mutate=_m)
        row = r["rows"][_NAV]
        assert row["light"] == "🔴", row
        assert sentence in row["text"], row
        assert "公開資料受限" not in row["text"] and "投信官網" not in row["text"], row

    @pytest.mark.parametrize("old_payload", [False, True])
    def test_active_nav_old_date_not_green_no_restricted_claim(self, monkeypatch, old_payload):
        def _m(p):
            _old_date(p)
            if old_payload:
                _strip_evidence(p)
        r = _run(monkeypatch, _ACT, mutate=_m)
        row = r["rows"][_NAV]
        assert row["light"] != "🟢" and "公開資料受限" not in row["text"], row

    def test_active_nav_genuinely_missing_old_payload_stays_grey(self, monkeypatch):
        spec = {**_ACT}
        spec.pop("nav")
        r = _run(monkeypatch, spec, mutate=_strip_evidence)
        assert r["rows"][_NAV] == {"light": "⚪", "text": "⚪ " + ACTIVE_MSG[:55]}

    @pytest.mark.parametrize("mut", [_stale_keep_nav, _no_date])
    def test_overseas_nav_present_stale_keeps_not_applicable_wording(self, monkeypatch, mut):
        r = _run(monkeypatch, {"ticker": "SPY", "input": "SPY", "aum": 5e11, "nav": "ok"}, mutate=mut)
        assert r["rows"][_NAV] == {"light": "⚪", "text": "⚪ " + OVERSEA_MSG}


# ───────────────────── NOTE-3（#1217）：NAV 日期在未來 ⇒ fail-closed，不得 🟢「今天」─────────────────────
NAV_FUTURE = "NAV 資料日期不可信，暫不判定新鮮度。"


def _set_date(days):
    def _m(p):
        d = _dt.date.today() + _dt.timedelta(days=days)
        p["premium"] = {**p["premium"], "nav_date": d, "data_date": d}
    return _m


_FUT_SPECS = {
    "passive": {"ticker": "0050.TW", "input": "0050", "aum": 2e12, "expense": 0.0046, "nav": "ok"},
    "active": _ACT,
}


class TestNavFutureDateFailClosed:
    @pytest.mark.parametrize("kind", ["passive", "active"])
    @pytest.mark.parametrize("days", [1, 3, 30])
    def test_future_date_red_untrusted(self, monkeypatch, kind, days):
        r = _run(monkeypatch, _FUT_SPECS[kind], mutate=_set_date(days))
        row = r["rows"][_NAV]
        assert row["light"] == "🔴", row
        assert NAV_FUTURE in row["text"], row
        assert "今天" not in row["text"] and "昨天" not in row["text"], row

    @pytest.mark.parametrize("days", [1, 3])
    def test_future_date_overseas_stays_not_applicable(self, monkeypatch, days):
        r = _run(monkeypatch, {"ticker": "SPY", "input": "SPY", "aum": 5e11, "nav": "ok"},
                 mutate=_set_date(days))
        assert r["rows"][_NAV] == {"light": "⚪", "text": "⚪ " + OVERSEA_MSG}

    @pytest.mark.parametrize("kind", ["passive", "active"])
    def test_today_still_green(self, monkeypatch, kind):
        r = _run(monkeypatch, _FUT_SPECS[kind], mutate=_set_date(0))
        row = r["rows"][_NAV]
        # 週末時 today 仍屬合法日期（非未來）⇒ 不得被誤擋為「不可信」
        assert NAV_FUTURE not in row["text"], row
        assert row["light"] in ("🟢", "🟡"), row

    @pytest.mark.parametrize("kind", ["passive", "active"])
    def test_yesterday_not_flagged_future(self, monkeypatch, kind):
        r = _run(monkeypatch, _FUT_SPECS[kind], mutate=_set_date(-1))
        assert NAV_FUTURE not in r["rows"][_NAV]["text"]
        assert r["rows"][_NAV]["light"] != "🔴" or "天前" in r["rows"][_NAV]["text"]

    @pytest.mark.parametrize("kind", ["passive", "active"])
    def test_old_date_not_regressed(self, monkeypatch, kind):
        r = _run(monkeypatch, _FUT_SPECS[kind], mutate=_old_date)
        row = r["rows"][_NAV]
        assert row["light"] != "🟢" and NAV_FUTURE not in row["text"], row

    @pytest.mark.parametrize("kind", ["passive", "active"])
    def test_no_date_keeps_unknown_sentence(self, monkeypatch, kind):
        r = _run(monkeypatch, _FUT_SPECS[kind], mutate=_no_date)
        row = r["rows"][_NAV]
        assert row["light"] == "🔴" and NAV_DATE_UNKNOWN in row["text"], row
        assert NAV_FUTURE not in row["text"]

    def test_freshness_light_global_unchanged(self):
        """不得全域改 freshness_light：未來日期於該函式仍是原行為（max(0,age)），修復只在 NAV caller。"""
        from src.ui.pages.health_inspector import freshness_light
        d = _dt.date.today() + _dt.timedelta(days=3)
        assert freshness_light(str(d), "daily")[0] in ("🟢", "🟡", "🔴")   # 契約：不 raise、不改簽名
