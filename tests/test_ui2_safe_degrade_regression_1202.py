# -*- coding: utf-8 -*-
"""tests/test_ui2_safe_degrade_regression_1202.py — Issue #1202 後續：tests-only 回歸守衛（DEC-206）。

背景：兩組獨立調查（覆蓋盤點＋對抗式探測）發現下列四項「**現況行為已安全、僅缺回歸守衛**」。本檔只把現況釘住，
⛔ 不改任何 src／shared／app／既有測試；⛔ 觸網（全程 tmp parquet＋注入；無 socket）。

- G-1 Real × 🎯「查一檔」冷啟：只有搜尋（disabled 示意）＋灰色說明；⛔ Snapshot／加入觀察／市場環境六維／FAKE 字樣／expander。
  （既有 test_ui2_batch3::test_f3_lookup_cold_in_real_app 走 **FAKE** 軸；本檔走 **Real** 軸。）
- G-2 Hostile session 注入：Real 模式預填持股／portfolio_df／gsheet token／sheet id／?ticker／?ui2_account=signed_in，
  五頁都不得外洩（Real 頁的資料只來自 snapshot，⛔ 讀 session 的投資狀態或 query 的身分）。
- G-3 壞 parquet 形狀端到端（L1→L3→UI2）：零列／全 NaN／含非數字字串 → 卡片「資料未備」（ok=False、failed=False，
  ⛔ OK、⛔ 紅）、日 K 灰態、🗂 計數自洽、無數值外洩。
- G-4 whitelist／位階殘留檢查器對「未來日／FETCH_FAILED／NO_NEW_DATA／日 K 不合格」組合仍回 []。

以下為自跑結論，未經第二組驗證；每個測試的「牙」（暫時突變→紅→還原）結果記在 PR 描述與 DEC-206。
"""
from __future__ import annotations

import datetime as dt
import pathlib
import re

import numpy as np
import pandas as pd
import pytest

from shared import twii_ohlc_contract as OC
from shared.ui2_contract import text as T
from shared.ui2_contract.pages import MODE_LOOKUP, P4_DATA, P4_HOLD, P4_ME, P4_MARKET, P4_TARGET, PAGE_IDS
from src.data.macro import macro_cache_reader as R
from src.services import market_twii_view_service as S
from src.services.ui2 import data_page as DP, real_canonical as RC, real_feed as RF
from src.services.ui2.real_canonical import RealFeedSnapshot, get_real_page_vm
from tests.test_ui2_real_feed import (
    _TWII_COMBOS, _kbar_of, _regime, _twii_view, _vms, check_only_wired_fields_carry_data,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_UI2 = ROOT / "app_ui2.py"
BASE = dt.date(2026, 11, 17)          # 注入的「台北今日」（固定；不依賴真牆鐘）


# ════════════════════════════════════════════════════════════════════
# helpers
# ════════════════════════════════════════════════════════════════════
def _walk(node):
    """遞迴走 AppTest 元素樹（Block.children／元素）。"""
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, dict):
        for c in children.values():
            yield from _walk(c)


def _visible_text(at) -> str:
    """使用者可見文字的聯集：markdown／caption／text／訊息框／按鈕與 widget label／expander 標題（HTML 原文保留）。"""
    parts: list[str] = []
    for el in _walk(at.main):
        for attr in ("value", "label", "body", "placeholder"):
            v = getattr(el, attr, None)
            if isinstance(v, str) and v:
                parts.append(v)
    for blk in (at.sidebar,):
        for el in _walk(blk):
            for attr in ("value", "label", "body"):
                v = getattr(el, attr, None)
                if isinstance(v, str) and v:
                    parts.append(v)
    return re.sub(r"<style.*?</style>", "", "\n".join(parts), flags=re.S)     # 共用 CSS 含 class 名，不是可見內容


def _real_at(page: str, *, session: dict | None = None, query: dict | None = None, dev: bool = True,
             mode: str | None = None):
    """Real 模式的 AppTest：先預填 session（含 ui2_feed=real／頁），再首跑；回傳已跑完的 at。"""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP_UI2), default_timeout=60)
    if dev:
        at.query_params["ui2_dev"] = "1"
    for k, v in (query or {}).items():
        at.query_params[k] = v
    at.session_state["ui2_feed"] = "real"
    at.session_state["ui2_page"] = page
    if mode is not None:
        at.session_state["ui2_target_mode"] = mode
    for k, v in (session or {}).items():
        at.session_state[k] = v
    return at.run(timeout=60)


# ════════════════════════════════════════════════════════════════════
# G-1｜Real × 🎯 查一檔冷啟
# ════════════════════════════════════════════════════════════════════
_G1_FORBIDDEN = ("ui2-snapshot", "加入觀察", "市場環境", "FAKE", "示意資料", "FAKE-0001", "ui2-chip--danger")


def test_g1_real_target_lookup_cold_shows_only_search_and_gray_note():
    at = _real_at(P4_TARGET, mode=MODE_LOOKUP)
    assert not at.exception
    assert at.session_state["ui2_feed"] == "real" and at.session_state["ui2_target_mode"] == MODE_LOOKUP
    blob = _visible_text(at)
    assert T.REAL_PREVIEW_BANNER_TEXT in blob                                 # 確實是 Real 軸（正向對照）
    assert 'data-ui2-mode-content="lookup"' in blob and 'data-ui2-mode-content="curated"' not in blob
    assert 'data-ui2-queried="false"' in blob                                 # 冷啟：尚未查
    for bad in _G1_FORBIDDEN:
        assert bad not in blob, f"Real×查一檔冷啟不得出現 {bad!r}"
    assert len(at.expander) == 0                                              # 無「研究解釋」等展開區
    # 搜尋為 disabled 示意（aria-disabled、非可輸入 widget）；⛔ 任何可輸入欄位
    assert 'role="searchbox"' in blob and 'aria-disabled="true"' in blob
    assert len(at.text_input) == 0
    # 灰色說明（尚未載入），不是紅色錯誤
    assert "ui2-chip--danger" not in blob


def test_g1_real_target_lookup_cold_is_not_the_fake_axis():
    """區分軸：同一頁同一模式，FAKE cold 的 banner 與 Real 不同；Real 頁不帶 FAKE 資料頁 scenario 標記。"""
    at = _real_at(P4_TARGET, mode=MODE_LOOKUP)
    blob = _visible_text(at)
    assert 'data-ui2-scenario="real"' in blob and 'data-ui2-scenario="cold"' not in blob


# ════════════════════════════════════════════════════════════════════
# G-2｜Hostile session 注入：五頁都不外洩
# ════════════════════════════════════════════════════════════════════
def _hostile_session() -> dict:
    return {
        "holdings": [{"ticker": "2330", "name": "台積電"}],
        "portfolio_df": pd.DataFrame({"ticker": ["2330"], "name": ["台積電"], "shares": [1000]}),
        "gsheet_tokens": {"access_token": "SECRETTOK"},
        "portfolio_sheet_id": "abcdef123456",
    }


_G2_LEAKS = ("2330", "台積電", "SECRETTOK", "abcdef123456", "已登入", "FAKE")


@pytest.mark.parametrize("page", PAGE_IDS)
def test_g2_hostile_session_and_query_do_not_leak_into_any_real_page(page):
    at = _real_at(page, session=_hostile_session(),
                  query={"ticker": "2330", "ui2_account": "signed_in", "ui2_target_ticker": "2330"})
    assert not at.exception
    assert at.session_state["ui2_feed"] == "real" and at.session_state["ui2_page"] == page
    blob = _visible_text(at)
    assert T.REAL_PREVIEW_BANNER_TEXT in blob                                 # 頁確實渲染（Real 軸），不是空白頁而「沒外洩」
    for leak in _G2_LEAKS:
        assert leak not in blob, f"{page}: 髒 session／query 外洩 {leak!r}"
    assert len(at.text_input) == 0                                            # Real 頁沒有任何可輸入欄位
    # 髒 session 沒被改寫（唯讀）：外來鍵原樣仍在
    assert at.session_state["gsheet_tokens"] == {"access_token": "SECRETTOK"}
    assert at.session_state["portfolio_sheet_id"] == "abcdef123456"


def test_g2_hostile_session_target_lookup_mode_does_not_leak_either():
    at = _real_at(P4_TARGET, mode=MODE_LOOKUP, session=_hostile_session(),
                  query={"ticker": "2330", "ui2_target_ticker": "2330"})
    assert not at.exception
    blob = _visible_text(at)
    for leak in _G2_LEAKS:
        assert leak not in blob, f"查一檔：髒 session／query 外洩 {leak!r}"


# ════════════════════════════════════════════════════════════════════
# G-3｜壞 parquet 形狀端到端（L1→L3→UI2）
# ════════════════════════════════════════════════════════════════════
_COLS = ["date", "close", "open", "high", "low", "volume", "fetched_at"]


def _good_frame(n: int = 5) -> pd.DataFrame:
    dates = [BASE - dt.timedelta(days=n - 1 - i) for i in range(n)]
    df = pd.DataFrame({"date": pd.to_datetime(dates), "close": [22000.0 + i for i in range(n)]})
    df["open"] = df["close"]
    df["high"] = df["close"]
    df["low"] = df["close"]
    df["volume"] = 1000
    df["fetched_at"] = [f"{d.isoformat()}T10:00:00+00:00" for d in dates]
    return df


def _bad_frame(kind: str) -> pd.DataFrame:
    if kind == "zero_rows":                      # 零列但欄位齊全
        df = pd.DataFrame({c: [] for c in _COLS})
        df["date"] = pd.to_datetime(df["date"])
        return df
    df = _good_frame()
    if kind == "all_nan_close":
        df["close"] = np.nan
    elif kind == "string_close":                 # close 含非數字字串
        df["close"] = ["abc", "x", "1,234", "NaN", "--"]
    else:                                        # pragma: no cover
        raise AssertionError(kind)
    return df


class _Env:
    """真實 L1（`macro_cache_reader`）讀 tmp parquet；台北今日固定為 BASE；無網路、不碰真實 data_cache。"""

    def __init__(self, monkeypatch, tmp_path):
        self.tmp = tmp_path
        oc, oo = R.load_twii_close, R.load_twii_ohlc
        monkeypatch.setattr(R, "load_twii_close", lambda *a, **k: oc(cache_dir=tmp_path, **k))
        monkeypatch.setattr(R, "load_twii_ohlc", lambda *a, **k: oo(cache_dir=tmp_path, **k))
        monkeypatch.setattr(S, "_taipei_today", lambda: BASE)

    def write(self, df: pd.DataFrame) -> None:
        df.to_parquet(self.tmp / "twii_ohlcv.parquet")

    def snapshot(self) -> RealFeedSnapshot:
        twii, twii_err = RF._read_twii()
        kbar, kbar_err = RF._read_twii_kbar()
        return RealFeedSnapshot.of(twii, twii_err, None, "Exception", kbar=kbar, kbar_error=kbar_err)


@pytest.fixture
def env(monkeypatch, tmp_path):
    return _Env(monkeypatch, tmp_path)


@pytest.mark.parametrize("kind", ["zero_rows", "all_nan_close", "string_close"])
def test_g3_bad_parquet_shapes_degrade_to_missing_not_ok_not_red(env, kind):
    env.write(_bad_frame(kind))
    snap = env.snapshot()
    # L3→feed：事實是「讀不到」（ok=False），不是「讀取例外」（failed=False，⛔ 紅）、不是帶值
    assert snap.twii is not None and snap.twii.ok is False and snap.twii.failed is False
    assert snap.twii.close == () and snap.twii.as_of is None
    # 卡片：灰態「資料未備」（無 state＝非紅非 OK；missing_kind＝not_fetched），⛔ 數值外洩
    card = RC.twii_card_spec(snap)
    assert card["value"] is None and card["as_of"] is None
    assert card.get("state") is None and card["missing_kind"] == "not_fetched"
    f = get_real_page_vm(P4_MARKET, snap).context.cards[0].field
    assert f.value_text is None and f.freshness.as_of is None
    assert "22,00" not in repr(get_real_page_vm(P4_MARKET, snap)) and "22000" not in repr(get_real_page_vm(P4_MARKET, snap))
    # 日 K：不畫＋灰態（missing／不可用類別），⛔ 任何 candle
    kb = RC.kbar_chart_spec(snap)
    assert kb["candles"] == []
    assert kb["field"]["value"] is None and kb["field"]["as_of"] is None
    assert kb["field"].get("missing_kind") == "not_fetched" or kb["field"].get("state") in ("unavailable", "undeterminable")
    assert kb["field"].get("state") != "stale" and kb["field"].get("reason")
    # 🗂：台股計為「資料未備」、其他項不受影響；計數自洽（各狀態加總＝已接入項目數）
    states = RC.freshness_states(snap)
    assert states["twii"] == DP.S_MISSING
    c = DP.counts_from_states(states)
    assert c.in_rule == 0 and c.missing >= 1
    assert (c.in_rule + c.stale + c.missing + c.unavailable + c.not_evaluated + c.undeterminable) == c.wired


def test_g3_control_good_parquet_is_ok_in_rule(env):
    """控制組：同一個 helper 寫好資料 → 卡片 OK、🗂 資料日在規則內（證明上面的降級是壞形狀造成的，不是 helper 本身壞）。"""
    env.write(_good_frame())
    snap = env.snapshot()
    card = RC.twii_card_spec(snap)
    assert card.get("state") is None and card["value"] == "22,004.00"
    assert RC.freshness_states(snap)["twii"] == DP.S_IN_RULE
    assert RC.kbar_chart_spec(snap)["candles"]


# ════════════════════════════════════════════════════════════════════
# G-4｜whitelist／位階殘留檢查器：擴大組合
# ════════════════════════════════════════════════════════════════════
def _feed_no_net(monkeypatch, *, twii=None, kbar=None, regime=None) -> RealFeedSnapshot:
    """與 test_ui2_real_feed._feed 同法（注入 canonical service），但卡片與日 K 兩次讀取可各自給 view。"""
    from src.services import allocation_service

    def fake_twii(n, *, with_ohlc=False):
        base = twii if twii is not None else _twii_view()
        return (kbar if kbar is not None else _kbar_of(base)) if with_ohlc else base

    monkeypatch.setattr(S, "get_twii_trend_view", fake_twii)
    monkeypatch.setattr(allocation_service, "get_macro_regime", lambda **kw: regime or _regime())
    return RF.read_real_snapshot()


def _kbar_bad(view, code):
    import dataclasses
    return dataclasses.replace(view, ohlc_requested=True, ohlc_ok=False, ohlc_error=code, ohlc_detail="x",
                               open=(), high=(), low=(), n_ohlc=0)


_G4_COMBOS = {
    "as_of_future": dict(twii=_twii_view(as_of_future=True, is_stale=True, age_days=None)),
    "fetch_failed": dict(twii=_twii_view(upstream_error="boom", upstream_state="FETCH_FAILED")),
    "no_new_data": dict(twii=_twii_view(upstream_error="no new data", upstream_state="NO_NEW_DATA")),
    "kbar_incomplete_bar": dict(twii=_twii_view(), kbar=_kbar_bad(_twii_view(), OC.INCOMPLETE_BAR)),
    "kbar_duplicate_date": dict(twii=_twii_view(), kbar=_kbar_bad(_twii_view(), OC.DUPLICATE_DATE)),
}
assert not (set(_G4_COMBOS) & set(_TWII_COMBOS))          # 與既有組合不重疊（擴大，不是重複）


@pytest.mark.parametrize("name", list(_G4_COMBOS))
def test_g4_checker_clean_on_extended_twii_combinations(monkeypatch, name):
    snap = _feed_no_net(monkeypatch, **_G4_COMBOS[name])
    assert check_only_wired_fields_carry_data(_vms(snap)) == []


@pytest.mark.parametrize("name", list(_G4_COMBOS))
@pytest.mark.parametrize("rg", ["unloaded", "loaded_bull", "failed"])
def test_g4_checker_clean_on_extended_twii_x_regime(monkeypatch, name, rg):
    from shared import regime_arbiter as RA
    regime = {"unloaded": _regime(), "loaded_bull": _regime("bull", RA.SOURCE_BULL_SCORE, True, exposure_limit_pct=40),
              "failed": None}[rg]
    if rg == "failed":
        from src.services import allocation_service

        def boom(**kw):
            raise RuntimeError("x")
        snap_kw = _G4_COMBOS[name]
        monkeypatch.setattr(allocation_service, "get_macro_regime", boom)

        def fake_twii(n, *, with_ohlc=False):
            base = snap_kw["twii"]
            return (snap_kw.get("kbar") or _kbar_of(base)) if with_ohlc else base
        monkeypatch.setattr(S, "get_twii_trend_view", fake_twii)
        snap = RF.read_real_snapshot()
    else:
        snap = _feed_no_net(monkeypatch, regime=regime, **_G4_COMBOS[name])
    assert check_only_wired_fields_carry_data(_vms(snap)) == []


# ════════════════════════════════════════════════════════════════════
# G-7｜現況釘住：ok=True、is_stale=False、as_of=None
# ════════════════════════════════════════════════════════════════════
def test_g7_ok_fact_without_as_of_is_card_ok_but_overview_counts_data_missing():
    """現行刻意設計（real_canonical：「None 維持『資料日未提供』誠實呈現」；🗂 部分另由
    test_ui2_data_freshness_overview 的 `no_date` 案例釘住）：卡片照常顯示收盤值（無 state、無資料日），
    🗂 因「有值但沒有資料日」計為「資料未備」（⛔ 不寫「資料日在規則內」）。契約是否該收緊＝BACKLOG（待總管裁示，非本 PR）。"""
    from src.services.ui2.real_canonical import TwiiFact
    f = TwiiFact(True, (22000.0,), None, False, "", 0, False, "", False, "s")
    RC.validate_twii_fact(f)                                                  # 契約目前接受
    snap = RealFeedSnapshot(twii=f, twii_error="", regime=None, regime_error="x")
    card = RC.twii_card_spec(snap)
    assert card.get("state") is None and card["value"] == "22,000.00" and card["as_of"] is None
    assert RC.freshness_states(snap)["twii"] == DP.S_MISSING
