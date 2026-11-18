"""tests/test_a_likely_private_unknown.py — `_likely_private` 移除：ETF 身分一律「未知」。

GPT 核准 plan C+A（保守最小版）：程式內沒有任何可靠的正向身分證據（無私募名單、無投信揭露旗標），
⇒ 不得由「AUM／費用率／NAV 三項皆缺」推斷私募（缺值 ≠ 私募）。

驗收方式（離線、無網路）：
  1. 真實 `render_etf_single`（streamlit AppTest；所有 fetcher 以 monkeypatch 換成假資料；socket 全擋）
     → 產出真實 `st.session_state['etf_single_data']` payload；
  2. 再把該 payload 餵給真實 `render_data_health_raw`（第二個 AppTest）→ 讀實際畫出的資料表列文字＋燈號。
離線 harness 由獨立第二組驗證原型（lp2）改寫而來。
"""
from __future__ import annotations

import datetime as _dt
import socket
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]

# ── 預期句（逐字；同時釘住 shared 單一來源與兩頁實際輸出）─────────────────────────────
AUM_MISSING = "目前沒有可用 ETF 規模資料，暫時無法顯示。"
EXPENSE_TIP = "目前沒有可用的 ETF 費用率資料，暫時無法顯示。"
NAV_STALE = "淨值資料已過期，暫時無法顯示。"
NAV_NONE = "目前沒有可用淨值資料，暫時無法顯示。"
EXP_PASSIVE = "SITCA、yfinance 均未取得可用費用率，暫時無法顯示。"
IDENT_NOTE = "ETF 類型無法確認；資料未取得不代表私募。"
OVERSEA_MSG = "海外 ETF 不適用（本系統 5 源僅限台灣 ETF）"
ACTIVE_MSG = "主動式 ETF — 公開資料受限（投信官網有揭露但格式不一致，本系統暫無法穩定抓取）"
OLD_PRIVATE_MSG = "私募/特殊 ETF"

_ROW_NAMES = ("ETF 規模 AUM", "ETF 費用率", "NAV 淨值", "ETF Beta")


# ════════════════════════════════════════════════════════════
# 離線 fixture
# ════════════════════════════════════════════════════════════
def _last_bday() -> _dt.date:
    d = _dt.date.today()
    while d.weekday() >= 5:
        d -= _dt.timedelta(days=1)
    return d


def _price_df() -> pd.DataFrame:
    idx = pd.bdate_range(end=pd.Timestamp(_last_bday()), periods=320)
    rng = np.random.default_rng(1)
    c = 100 * np.cumprod(1 + rng.normal(0.0003, 0.008, len(idx)))
    return pd.DataFrame({"Open": c, "High": c * 1.005, "Low": c * 0.995, "Close": c,
                         "Volume": rng.integers(1_000_000, 5_000_000, len(idx))}, index=idx)


def _nav_df(mode: str, pdf: pd.DataFrame) -> pd.DataFrame:
    last = pdf.index[-1]
    if mode == "ok":
        return pd.DataFrame({"date": [last - pd.Timedelta(days=1), last],
                             "nav": [pdf.Close.iloc[-2] * .999, pdf.Close.iloc[-1] * .999]})
    if mode == "valuestale":  # NAV 日期同日但值過時（偏離市價 ~11% ⇒ 守門員 nav_value_stale，nav 值被保留）
        return pd.DataFrame({"date": [last - pd.Timedelta(days=1), last],
                             "nav": [pdf.Close.iloc[-2] * .90, pdf.Close.iloc[-1] * .90]})
    if mode == "stale":       # 最新 NAV 落後 4 天 ⇒ 折溢價守門員判 stale_nav 且不給 nav 值
        nd = last - pd.Timedelta(days=4)
        return pd.DataFrame({"date": [nd - pd.Timedelta(days=1), nd], "nav": [99.0, 99.5]})
    return pd.DataFrame()


def _install(monkeypatch, spec: dict) -> None:
    """封網＋把所有 fetcher（含各模組 import 時綁定的別名）換成離線假資料。全部由 monkeypatch 還原。"""
    def _deny(*a, **k):
        raise RuntimeError("NETWORK BLOCKED (test_a_likely_private_unknown)")
    monkeypatch.setattr(socket.socket, "connect", _deny)
    monkeypatch.setattr(socket, "create_connection", _deny)
    monkeypatch.setattr(socket, "getaddrinfo", _deny)

    import src.data.etf as EB
    import src.data.etf.etf_fetch as EF
    import src.compute.etf.etf_calc  # noqa: F401  先 import，讓其別名綁定發生在 patch 之前
    import src.ui.etf.etf_tab_single  # noqa: F401
    import src.ui.pages.health_inspector  # noqa: F401

    pdf = _price_df()
    nav = _nav_df(spec.get("nav", "none"), pdf)
    info = {}
    if spec.get("aum"):
        info["totalAssets"] = spec["aum"]
    if spec.get("beta"):
        info["beta"] = spec["beta"]
    repl = {
        "fetch_etf_price": lambda t, *a, **k: pdf.copy(),
        "fetch_etf_dividends": lambda t, *a, **k: pd.DataFrame(),
        "fetch_etf_info": lambda t, *a, **k: dict(info),
        "get_etf_expense_ratio_safe": lambda t, *a, **k: spec.get("expense"),
        "fetch_etf_nav_history": lambda t, *a, **k: nav.copy(),
        "fetch_etf_official_premium": lambda *a, **k: None,
        "_get_etf_launch_price": lambda *a, **k: None,
        "fetch_etf_zh_name": lambda t, *a, **k: None,
        "fetch_etf_holdings": lambda *a, **k: [],
        "_fetch_news_for": lambda *a, **k: [],
    }
    orig = {n: getattr(EF, n, None) for n in repl}
    for n in ("fetch_etf_zh_name", "fetch_etf_holdings", "_fetch_news_for"):
        if orig[n] is None:
            orig[n] = getattr(EB, n, None)
    for mname, mod in list(sys.modules.items()):
        if not (mname.startswith("src") or mname == "app"):
            continue
        for n, f in repl.items():
            if n in vars(mod) and orig.get(n) is not None and vars(mod)[n] is orig[n]:
                monkeypatch.setattr(mod, n, f)
    for n, f in repl.items():
        monkeypatch.setattr(EF, n, f, raising=False)
        monkeypatch.setattr(EB, n, f, raising=False)


def _stage1():
    import src.ui.etf.etf_tab_single as TS
    TS.render_etf_single()


def _stage2():
    import src.ui.pages.health_inspector as HI
    HI.render_data_health_raw()


def _run(monkeypatch, spec: dict, mutate=None) -> dict:
    """跑真實 ETF 單檔頁 → payload →（可選改 payload）→ 真實資料診斷 ETF Raw Data 區。"""
    from streamlit.testing.v1 import AppTest
    _install(monkeypatch, spec)
    tk = spec["ticker"]
    at = AppTest.from_function(_stage1, default_timeout=120)
    at.session_state["etf_s_ticker"] = spec.get("input", tk)
    at.session_state["etf_s_active"] = tk
    at.run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    assert "etf_single_data" in at.session_state, "ETF 單檔頁未產出 payload（fixture 失效）"
    payload = dict(at.session_state["etf_single_data"])
    metrics = {m.label: (m.value, m.help) for m in at.metric
               if m.label in ("內扣費用率", "AUM", "折溢價率")}
    if mutate:
        mutate(payload)
    at2 = AppTest.from_function(_stage2, default_timeout=120)
    at2.session_state["etf_single_data"] = payload
    at2.run()
    assert not at2.exception, [str(e.value)[:300] for e in at2.exception]
    rows = {}
    for d in at2.dataframe:
        df = d.value
        if "資料名稱" in df.columns:
            for _, r in df.iterrows():
                nm = str(r["資料名稱"])
                if nm in _ROW_NAMES:
                    rows[nm] = {"light": str(r["狀態"]), "text": str(r["最後更新"])}
    assert set(rows) == set(_ROW_NAMES), rows
    return {"payload": payload, "metrics": metrics, "rows": rows}


def _lights(r):
    return tuple(r["rows"][n]["light"] for n in ("ETF 規模 AUM", "ETF 費用率", "NAV 淨值"))


def _all_text(r):
    return "\n".join(v["text"] for v in r["rows"].values())


# ════════════════════════════════════════════════════════════
# 場景
# ════════════════════════════════════════════════════════════
class TestAllPresent:
    def test_0050_all_present_green(self, monkeypatch):
        r = _run(monkeypatch, {"ticker": "0050.TW", "input": "0050", "aum": 2e12,
                               "expense": 0.0046, "nav": "ok"})
        assert _lights(r) == ("🟢", "🟢", "🟢")
        assert "私募" not in _all_text(r)
        assert r["payload"]["_err_expense"] is None and r["payload"]["_err_nav"] is None


class TestThreeMissingIsUnknownNotPrivate:
    @pytest.mark.parametrize("ticker,inp", [
        ("0050.TW", "0050"),        # 一般被動
        ("00999.TW", "00999"),      # 新上市
        ("00631L.TW", "00631L"),    # 槓桿 L
        ("00720B.TW", "00720B"),    # 債券 B
        ("00679B.TWO", "00679B.TWO"),   # 上櫃債券
    ])
    def test_red_with_failure_sentences_no_private_claim(self, monkeypatch, ticker, inp):
        r = _run(monkeypatch, {"ticker": ticker, "input": inp})
        rows = r["rows"]
        assert _lights(r) == ("🔴", "🔴", "🔴"), rows
        assert OLD_PRIVATE_MSG not in _all_text(r)
        assert "私募/特殊" not in _all_text(r)
        assert AUM_MISSING in rows["ETF 規模 AUM"]["text"]
        assert IDENT_NOTE in rows["ETF 規模 AUM"]["text"]       # 沒被 55/50 字截斷吃掉
        assert EXP_PASSIVE in rows["ETF 費用率"]["text"]
        assert NAV_NONE in rows["NAV 淨值"]["text"]
        # 身分說明只出現在 AUM 列，且只有一次
        assert _all_text(r).count(IDENT_NOTE) == 1
        assert "_likely_private" not in r["payload"]

    def test_stale_nav_three_missing(self, monkeypatch):
        r = _run(monkeypatch, {"ticker": "00878.TW", "input": "00878", "nav": "stale"})
        assert r["payload"]["premium"].get("stale_nav") is True
        assert r["payload"]["premium"].get("nav") is None
        assert r["payload"]["_err_nav"] == NAV_STALE
        assert _lights(r) == ("🔴", "🔴", "🔴")
        assert NAV_STALE in r["rows"]["NAV 淨值"]["text"]
        assert NAV_NONE not in r["rows"]["NAV 淨值"]["text"]    # 不可說成「沒資料／抓取失敗」
        assert OLD_PRIVATE_MSG not in _all_text(r)


class TestOverseasAndActiveUnchanged:
    """與修改前逐字相同（before.json 取得的實際輸出）。"""

    @pytest.mark.parametrize("ticker", ["SPY", "VOO"])
    def test_overseas_identical_to_before(self, monkeypatch, ticker):
        r = _run(monkeypatch, {"ticker": ticker, "input": ticker})
        rows = r["rows"]
        # AUM 列：既有行為（is_active_etf 對 SPY/VOO 為 True ⇒ 顯示主動式句；屬另案 OPEN 發現 #2，不在本修範圍）
        assert rows["ETF 規模 AUM"] == {"light": "⚪", "text": "⚪ " + ACTIVE_MSG[:55]}
        assert rows["ETF 費用率"] == {"light": "⚪", "text": "⚪ " + OVERSEA_MSG}
        assert rows["NAV 淨值"] == {"light": "⚪", "text": "⚪ " + OVERSEA_MSG}
        assert "私募" not in _all_text(r)
        assert IDENT_NOTE not in _all_text(r)

    def test_tw_active_three_missing_identical_to_before(self, monkeypatch):
        r = _run(monkeypatch, {"ticker": "00981A.TW", "input": "00981A"})
        for n in ("ETF 規模 AUM", "ETF 費用率", "NAV 淨值"):
            assert r["rows"][n] == {"light": "⚪", "text": "⚪ " + ACTIVE_MSG[:55]}, n
        assert IDENT_NOTE not in _all_text(r)

    def test_tw_active_only_aum_identical_to_before(self, monkeypatch):
        r = _run(monkeypatch, {"ticker": "00981A.TW", "input": "00981A", "aum": 5e10})
        assert r["rows"]["ETF 規模 AUM"]["light"] == "🟢"
        assert r["rows"]["ETF 費用率"] == {"light": "⚪", "text": "⚪ " + ACTIVE_MSG[:55]}
        assert r["rows"]["NAV 淨值"] == {"light": "⚪", "text": "⚪ " + ACTIVE_MSG[:55]}


class TestOldPayloadFlagIgnored:
    def test_old_flag_over_three_missing(self, monkeypatch):
        def _old(p):
            p["_likely_private"] = True
            p.pop("_err_expense", None)
            p.pop("_err_nav", None)
        r = _run(monkeypatch, {"ticker": "0050.TW", "input": "0050"}, mutate=_old)
        assert "⚪" not in _lights(r)                  # 不再被舊旗標壓成「不適用」
        assert _lights(r) == ("🔴", "🔴", "🔴")
        assert OLD_PRIVATE_MSG not in _all_text(r)
        assert "私募/特殊" not in _all_text(r)

    def test_old_flag_over_complete_data(self, monkeypatch):
        def _old(p):
            p["_likely_private"] = True
        r = _run(monkeypatch, {"ticker": "0050.TW", "input": "0050", "aum": 2e12,
                               "expense": 0.0046, "nav": "ok"}, mutate=_old)
        assert _lights(r) == ("🟢", "🟢", "🟢")

    def test_old_flag_over_partial_data(self, monkeypatch):
        def _old(p):
            p["_likely_private"] = True
            p.pop("_err_nav", None)
        r = _run(monkeypatch, {"ticker": "0050.TW", "input": "0050", "aum": 2e12,
                               "expense": 0.0046}, mutate=_old)
        assert _lights(r) == ("🟢", "🟢", "🔴")        # 只有真正缺的 NAV 紅燈
        assert OLD_PRIVATE_MSG not in _all_text(r)
        assert IDENT_NOTE not in _all_text(r)         # 非三缺 ⇒ 不附身分說明


class TestPartialAvailabilityLightsUnchanged:
    """S10a–e：燈號與修改前相同；身分說明只在三缺時出現。"""

    @pytest.mark.parametrize("name,spec,lights,nav_text", [
        ("a 僅AUM", {"ticker": "00878.TW", "input": "00878", "aum": 1e11}, ("🟢", "🔴", "🔴"), NAV_NONE),
        ("b 僅費用率", {"ticker": "00878.TW", "input": "00878", "expense": 0.0025}, ("🔴", "🟢", "🔴"), NAV_NONE),
        ("c 僅NAV", {"ticker": "00878.TW", "input": "00878", "nav": "ok"}, ("🔴", "🔴", "🟢"), None),
        ("d AUM+費用率", {"ticker": "0050.TW", "input": "0050", "aum": 2e12, "expense": 0.0046}, ("🟢", "🟢", "🔴"), NAV_NONE),
        ("e 費用率+NAV", {"ticker": "0050.TW", "input": "0050", "expense": 0.0046, "nav": "ok"}, ("🔴", "🟢", "🟢"), None),
    ])
    def test_partial(self, monkeypatch, name, spec, lights, nav_text):
        r = _run(monkeypatch, spec)
        assert _lights(r) == lights, (name, r["rows"])
        assert IDENT_NOTE not in _all_text(r)
        assert OLD_PRIVATE_MSG not in _all_text(r)
        if nav_text:
            assert nav_text in r["rows"]["NAV 淨值"]["text"]
        if lights[0] == "🔴":
            assert AUM_MISSING in r["rows"]["ETF 規模 AUM"]["text"]


class TestTooltipsAndPayload:
    def test_tooltips_no_private_no_overseas_ip(self, monkeypatch):
        r = _run(monkeypatch, {"ticker": "0050.TW", "input": "0050"})
        m = r["metrics"]
        assert m["內扣費用率"][0] == "N/A" and m["AUM"][0] == "N/A"
        assert m["內扣費用率"][1] == EXPENSE_TIP
        assert m["AUM"][1] == AUM_MISSING
        for _lbl in ("內扣費用率", "AUM"):
            assert "私募" not in (m[_lbl][1] or "")
            assert "海外 IP" not in (m[_lbl][1] or "")

    def test_payload_has_no_likely_private_key(self, monkeypatch):
        for spec in ({"ticker": "0050.TW", "input": "0050"},
                     {"ticker": "0050.TW", "input": "0050", "aum": 2e12, "expense": 0.0046, "nav": "ok"},
                     {"ticker": "SPY", "input": "SPY"}):
            r = _run(monkeypatch, spec)
            assert "_likely_private" not in r["payload"], spec


# ════════════════════════════════════════════════════════════
# 靜態守衛（原始碼層）＋ 單一來源
# ════════════════════════════════════════════════════════════
class TestSourceGuards:
    def test_no_likely_private_in_production_code(self):
        # 舊旗標的讀寫與推斷全數移除；僅允許本測試檔／文件以字串提及。
        for rel in ("src/ui/etf/etf_tab_single.py", "src/ui/pages/health_inspector.py",
                    "src/ui/pages/data_coverage.py"):
            src = (REPO / rel).read_text(encoding="utf-8")
            assert "_likely_private" not in src, rel
            assert "_is_private_etf" not in src, rel
            assert "_private_msg" not in src, rel
            assert OLD_PRIVATE_MSG not in src, rel
            assert "海外 IP 受限" not in src, rel

    def test_single_source_strings(self):
        import shared.etf_missing_text as T
        import src.ui.etf.etf_tab_single as TS
        assert T.ETF_AUM_MISSING_TEXT == AUM_MISSING
        assert T.ETF_EXPENSE_MISSING_TEXT == EXPENSE_TIP
        assert T.ETF_NAV_STALE_TEXT == NAV_STALE
        assert T.ETF_IDENTITY_UNKNOWN_NOTE == IDENT_NOTE
        assert TS._ERR_NAV_STALE == NAV_STALE          # 單檔頁 _err_nav 與診斷頁引用同一來源
        assert TS._ERR_NAV_NO_ATTEMPT_EVIDENCE == NAV_NONE
        src = (REPO / "src/ui/etf/etf_tab_single.py").read_text(encoding="utf-8")
        assert "else _ERR_NAV_NO_ATTEMPT_EVIDENCE" in src      # 與 test_issue1208 釘住的子字串一致

    def test_identity_note_fits_row_truncation(self):
        # 診斷表 🔴 列 error_msg 截斷 50 字：AUM 缺值句＋空白＋身分說明必須完整放得下
        full = AUM_MISSING + " " + IDENT_NOTE
        assert len(full) <= 50, len(full)

    def test_shared_module_is_pure_l0(self):
        src = (REPO / "shared/etf_missing_text.py").read_text(encoding="utf-8")
        assert "import streamlit" not in src and "from src" not in src and "import src" not in src
