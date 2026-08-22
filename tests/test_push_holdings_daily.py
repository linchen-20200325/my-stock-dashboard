"""守衛 — 每日持股續抱/換股推播 cron（scripts/push_holdings_daily.py,#35）。

涵蓋:_build_entries 去重/分流/held 旗標、憑證/ sheet id fail-loud、空清單提醒、
populated 沿用引擎 orchestration（真 build_switch_advice/build_station_digest）、
AI 缺 key 略過、workflow 結構 + headless（無 top-level streamlit）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.push_holdings_daily as P
import src.data.notify.dispatch as D
import src.data.portfolio.gsheet_sa_reader as R
import src.services.dividend_station_service as DS

_REPO = Path(__file__).resolve().parents[1]
_VALID_SA = json.dumps({"client_email": "bot@proj.iam.gserviceaccount.com",
                        "private_key": "-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----"})


# ── _build_entries 純邏輯 ────────────────────────────────────────────────
def test_build_entries_dedup_classify_held():
    hold = [{"ticker": "0050", "lots": 2, "avg_price": 130},
            {"ticker": "2330", "lots": 1, "avg_price": 600},
            {"ticker": "0050", "lots": 9, "avg_price": 1}]      # 重複 → 去
    wl = ["2317", "2330", "00878"]                              # 2330 已持有 → 不重列
    ent = P._build_entries(hold, wl)
    _by = {e["ticker"]: e for e in ent}
    assert set(_by) == {"0050", "2330", "2317", "00878"}
    assert _by["0050"]["asset_kind"] == "etf" and _by["0050"]["held"] is True
    assert _by["2330"]["asset_kind"] == "stock" and _by["2330"]["held"] is True
    assert _by["2317"]["asset_kind"] == "stock" and _by["2317"]["held"] is False
    assert _by["00878"]["asset_kind"] == "etf" and _by["00878"]["held"] is False
    # 持股帶 lots/avg,觀察清單不帶（§1 無價格）
    assert _by["0050"]["lots"] == 2 and _by["2317"]["lots"] is None


def test_build_entries_empty():
    assert P._build_entries([], []) == []


# ── fail-loud（§1）──────────────────────────────────────────────────────
def test_main_missing_credentials_raises(monkeypatch):
    monkeypatch.delenv("GCP_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.setenv("STOCK_PORTFOLIO_SHEET_ID", "S1")
    with pytest.raises(ValueError, match="未設定"):
        P.main([])


def test_main_missing_all_sheet_ids_raises(monkeypatch):
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", _VALID_SA)
    monkeypatch.delenv("PORTFOLIO_SHEET_ID", raising=False)
    monkeypatch.delenv("STOCK_PORTFOLIO_SHEET_ID", raising=False)
    with pytest.raises(ValueError, match="皆未設定"):
        P.main([])


# ── 空清單 → 提醒（不偽造持股）─────────────────────────────────────────
def test_main_empty_lists_sends_notice(monkeypatch):
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", _VALID_SA)
    monkeypatch.setenv("STOCK_PORTFOLIO_SHEET_ID", "S1")
    monkeypatch.delenv("PORTFOLIO_SHEET_ID", raising=False)
    monkeypatch.setattr(R, "read_holdings", lambda sid, creds: [])
    monkeypatch.setattr(R, "read_watchlist", lambda sid, creds: [])
    _sent = {}
    monkeypatch.setattr(D, "send_notification", lambda text, **k: _sent.setdefault("t", text) and 1 or 1)
    rc = P.main([])
    assert rc == 0
    assert "讀不到任何持股" in _sent["t"] and "分享" in _sent["t"]


# ── populated → 沿用引擎 orchestration（真純函式）──────────────────────
def _red_held_row():
    return {"代號": "2412", "名稱": "中華電", "種類": "個股", "健檢": "🔴",
            "建議動作": "財報C 建議換出", "held": True, "加碼金": "", "235 燈號": "—",
            "市值": None, "損益%": None, "_detail": {}}


def _wire_populated(monkeypatch, *, with_ai_key=False):
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", _VALID_SA)
    monkeypatch.setenv("STOCK_PORTFOLIO_SHEET_ID", "S1")
    monkeypatch.delenv("PORTFOLIO_SHEET_ID", raising=False)
    if with_ai_key:
        monkeypatch.setenv("GEMINI_API_KEY", "k")
    else:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(R, "read_holdings", lambda sid, creds: [{"ticker": "2412", "lots": 5, "avg_price": 100}])
    monkeypatch.setattr(R, "read_watchlist", lambda sid, creds: [])
    monkeypatch.setattr(DS, "resolve_holding_names", lambda hs: hs)
    monkeypatch.setattr(DS, "get_station_rows", lambda hs: ([_red_held_row()], 21.5))
    monkeypatch.setattr(DS, "get_station_macro",
                        lambda: {"regime": "bull", "loaded": True, "defense": False,
                                 "posture_label": "🟢 積極", "posture_range": "70–90%"})
    monkeypatch.setattr(DS, "get_switch_in_candidates",
                        lambda **k: [{"代碼": "2330", "名稱": "台積電", "綜合分": 88}])
    _sent = {}
    monkeypatch.setattr(D, "send_notification",
                        lambda text, **k: (_sent.setdefault("t", text), 1)[1])
    return _sent


def test_main_populated_sends_switch_message(monkeypatch):
    _sent = _wire_populated(monkeypatch)
    rc = P.main([])
    assert rc == 0
    _t = _sent["t"]
    assert "建議換出" in _t and "2412" in _t          # 持有紅燈 → 換出
    assert "建議換入" in _t and "2330" in _t          # 選股池候選 → 換入
    assert "AI 總結" not in _t                        # 無 GEMINI_API_KEY → 無 AI 段
    assert "非投資建議" in _t


def test_main_dry_run_does_not_send(monkeypatch, capsys):
    _sent = _wire_populated(monkeypatch)
    rc = P.main(["--dry-run"])
    assert rc == 0
    assert "t" not in _sent                            # dry-run 不送
    assert "DRY RUN" in capsys.readouterr().out


def test_main_ai_appended_when_key_present(monkeypatch):
    _sent = _wire_populated(monkeypatch, with_ai_key=True)
    # 攔 post_gemini(避免真連網),回固定潤稿
    import src.services.ai_fetcher as AF
    monkeypatch.setattr(AF, "post_gemini", lambda *a, **k: ("今日續抱為主,汰弱2412。", "gemini-x"))
    rc = P.main([])
    assert rc == 0
    assert "🤖 AI 總結" in _sent["t"] and "汰弱2412" in _sent["t"]


def test_main_ai_failure_degrades_to_rule_message(monkeypatch):
    _sent = _wire_populated(monkeypatch, with_ai_key=True)
    import src.services.ai_fetcher as AF

    def _boom(*a, **k):
        raise RuntimeError("gemini down")
    monkeypatch.setattr(AF, "post_gemini", _boom)
    rc = P.main([])
    assert rc == 0
    assert "AI 總結" not in _sent["t"]                 # AI 失敗 → 只送規則式
    assert "建議換出" in _sent["t"]                    # 規則式主體仍在


# ── workflow 結構 + headless ─────────────────────────────────────────────
def test_workflow_file_structure():
    y = (_REPO / ".github/workflows/push_holdings_daily.yml").read_text(encoding="utf-8")
    assert 'cron: "15 9 * * 1-5"' in y                # TW 17:15,錯開選股推
    assert "scripts/push_holdings_daily.py" in y
    for _sec in ("GCP_SERVICE_ACCOUNT_JSON", "PORTFOLIO_SHEET_ID",
                 "STOCK_PORTFOLIO_SHEET_ID", "LINE_CHANNEL_ACCESS_TOKEN",
                 "FINMIND_TOKEN", "GEMINI_API_KEY"):
        assert _sec in y, f"workflow 缺 secret env: {_sec}"


def test_script_no_toplevel_streamlit():
    """headless cron:腳本本體不得 top-level import streamlit（沿用 push_daily_signals 慣例）。"""
    src = (_REPO / "scripts/push_holdings_daily.py").read_text(encoding="utf-8")
    assert "import streamlit" not in src
