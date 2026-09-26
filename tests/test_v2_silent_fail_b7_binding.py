"""批次 7：「💼 我的持股」綁定狀態 —— 「讀失敗」不得畫成「你還沒有綁定持股 Sheet」（灰「有效的結果」）。

（客戶 2026-09-26：本批放行「失敗被當成沒結果」的所有卡；⛔ 不新造文案；⛔ 不動版面；
  L1/L3 只准為這幾張卡的失敗判定而動。）

根因（兩段，都在綁定這條取數線上）：
  1. L3 `portfolio_binding_service.get_binding_state()` 讀登入 token（`_has_oauth_tokens()`）或
     Sheet 識別碼（`_get_active_sheet_id()`）**拋例外**時，`except Exception` 吞掉、回 `unbound`。
     `unbound` 在 💼 我的持股 頁 = 「你還沒有綁定持股 Sheet」＋「這是一個有效的結果（…也不是故障）」
     —— 綁定卡 `hold.binding` 一張，另經 L3 `holdings_service.get_holdings()`（`bound=False` ＋
     空清單）傳到持股列預覽與整個戰情表家族（①結論三張／燈牆／停利／配置／核心衛星／④換股／
     ⑥深度三格／⑦AI），全部灰卡 `NOT_BOUND_NOW`。
  2. L1 `gsheet_portfolio._has_oauth_tokens()` 在 `oauth_state` **載不進來**時回 False —— 同樣把
     一次故障讀成「沒登入」。

修法（全部「只加不改」，既有 caller 一字不變）：
  · L1：新增 `_oauth_import_error()`（只重做同一行 import，失敗回 repr）；`_has_oauth_tokens()` 不動。
  · L3：`BindingState.read_error: str = ""`（新欄位、有預設值）。讀 token／讀 Sheet 識別碼拋例外，
    或 token 為 False 且 OAuth 模組載不進來 → `status` **照舊** `unbound`（全域狀態列不讀本欄 →
    一字不變），`read_error` 帶例外 repr。
  · L3：`holdings_service.get_holdings()` 見 `read_error` → 往上拋（同「投資組合那半 fail loud」）。
  · L5：`load_binding()` 見 `read_error` → 與既有 (d)「L3 拋例外」**同一個讀數** → 綁定兩張卡紅；
    `load_holdings()` 既有 except 接住 L3 例外 → 預覽卡與戰情表家族走各自既有的 `*_FAILED_NOW`。
    **沒有新 Note、沒有新字串**：紅卡全部是既有 (d)／既有例外分支產生的。

「沒設定」vs「失敗」的判定（寫死在 L3 docstring，本檔 (b) 釘住）：
  · token 不在 / Sheet 識別碼沒設 → 灰（有效結果，同修前）。
  · OAuth Client 沒設定（`is_oauth_configured()` 為 False）→ **灰**：讀到了，答案是「沒有設定」；
    沒有設定就不可能在本 session 登入過（token 只由 `handle_oauth_callback` 寫入，它沒設定時直接 return）。

每條失敗路徑三件事（同批次 1～6）：
  (a) 上游讀失敗 → 紅卡（各卡既有的 `*_FAILED_NOW`）；⛔ 不得是灰卡 `NOT_BOUND_NOW`／「有效的結果」；
  (b) 真的沒綁／真的綁了／沒按鈕 → 原封不動；全域狀態列與其他卡的輸出一字不變；
  (c) 突變：拿掉本批新加的任一條 → (a) 或 (b) 必須失敗。
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib.util
import pathlib
import sys
import types

import pandas as pd
import pytest

import src.data.portfolio.gsheet_portfolio as GSP
import src.data.portfolio.oauth_state as OS
import src.services.dividend_station_service as S
import src.services.holdings_service as HS
import src.services.portfolio_binding_service as SVC
import src.ui.tabs.portfolio_status_bar as BAR
from shared import dividend_station_thresholds as T
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_IDLE, UI_LIVE
from src.ui.views import page_hold as PH

_REPO = pathlib.Path(__file__).resolve().parents[1]
_VALID = "有效的結果"
_REQ = PH.HoldRequest(submitted=True, mode=PH.SCOPE_WITH_BINDING)
_SVC_NAME = "src.services.portfolio_binding_service"
_HS_NAME = "src.services.holdings_service"


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    """把 `mod` 的原始碼裡每一組 `old` **恰好一處**換成 `new`，載成一個獨立的新模組。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_b7_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


# ── 本批的每一個新增點（突變與「修前」重建共用同一組字串）───────────────────
_SVC_TOKEN = ("        _errs.append(repr(_e))   # 仍視為未登入,但**記下來**:這不是「沒登入」,是讀不到\n",
              "")
_SVC_SHEET = ("        _sid = \"\"\n        _errs.append(repr(_e))\n", "        _sid = \"\"\n")
_SVC_PROBE = ("            _imp = _gsp._oauth_import_error()\n", "            _imp = \"\"\n")
_SVC_FIELD = (",\n                            read_error=_read_err)", ")")
_HS_RAISE = ("    if _bind_err:\n        raise RuntimeError(_bind_err)\n", "")
_PH_BLOCK = ("    if _read_err:\n", "    if False:\n")
_GSP_PROBE = ("        return repr(_e)\n    del is_oauth_configured", "        return ''\n    del is_oauth_configured")


# ── L1 替身（L3 在呼叫當下 `from src.data.portfolio import gsheet_portfolio`，換屬性即生效）──
def _val(v):
    def _f(*_a, **_k):
        if isinstance(v, BaseException):
            raise v
        return v
    return _f


@pytest.fixture
def l1(monkeypatch):
    """設定 L1 gsheet 讀取面：值或例外。未指定的一律用「真的沒有」的安全預設。"""
    import src.services.portfolio_deep_service as D
    import src.services.app_ai_service as A

    # 下游的網路面一律換成離線替身（有持股的情境才會走到；兩個版本吃同一組）。
    monkeypatch.setattr(S, "resolve_holding_names", lambda h: h)
    monkeypatch.setattr(S, "get_station_rows",
                        lambda hold: (S.build_station_rows(hold, vix=18.0, metrics_fn=_metrics), 18.0))
    monkeypatch.setattr(S, "get_switch_in_candidates", lambda **_k: [])
    for _fn in ("get_portfolio_stress", "get_portfolio_var", "get_dividend_cash_flow"):
        monkeypatch.setattr(D, _fn, lambda rows: None)
    monkeypatch.setattr(A, "gemini_call", lambda *_a, **_k: "推播文字")

    def _use(*, logged=False, sid="", portfolios=(), rows=(), stock_sid="", probe=None):
        if logged is not None:
            monkeypatch.setattr(GSP, "_has_oauth_tokens", _val(logged))
        monkeypatch.setattr(GSP, "_get_active_sheet_id", _val(sid))
        monkeypatch.setattr(GSP, "list_portfolios",
                            _val(list(portfolios) if isinstance(portfolios, tuple) else portfolios))
        monkeypatch.setattr(GSP, "load_portfolio", _val(list(rows)))
        monkeypatch.setattr(GSP, "_get_active_stock_sheet_id", _val(stock_sid))
        monkeypatch.setattr(GSP, "list_stock_watchlists", _val([]))
        monkeypatch.setattr(GSP, "load_stock_watchlist", _val([]))
        if probe is not None:
            monkeypatch.setattr(GSP, "_oauth_import_error", _val(probe))
    return _use


def _metrics(tk, ak):
    idx = pd.date_range("2020-01-03", periods=300, freq="W-FRI")
    if ak == T.KIND_ETF:
        return {"weekly_close": pd.Series([30 + (i % 7) * 0.3 for i in range(300)], index=idx),
                "current_price": 35.0}
    return {"mj_grade": "A", "mj_score_pct": 80, "mj_headline": "ok", "mj_fail_items": [],
            "kd_state": {"k": 50, "d": 40, "label": "中性"}, "name": tk,
            "trend_verdict": None, "current_price": 125.0}


_ROWS = ({"ticker": "0056", "lots": 3, "avg_price": 30.0},
         {"ticker": "2330", "lots": 1, "avg_price": 100.0})

#: 讀失敗的五種樣子（L1 設定 → 期待在 read_error 裡看得到的例外原文）。
_FAILURES = {
    "token_raises": (dict(logged=RuntimeError("token boom"), sid="SHEET1", portfolios=("核心",),
                          rows=_ROWS), "token boom"),
    "token_raises_no_sheet": (dict(logged=RuntimeError("token boom"), sid=""), "token boom"),
    "sheet_raises": (dict(logged=True, sid=KeyError("sid boom"), portfolios=("核心",)), "sid boom"),
    "sheet_raises_logged_out": (dict(logged=False, sid=KeyError("sid boom")), "sid boom"),
    "oauth_module_broken": (dict(logged=False, sid="SHEET1",
                                 probe="ImportError('oauth_state broken')"), "oauth_state broken"),
}

#: 真的結果（修前修後必須一字不變）。
_GENUINE = {
    "not_logged_in": dict(logged=False, sid="SHEET1", portfolios=("核心",), rows=_ROWS),
    "logged_in_no_sheet": dict(logged=True, sid=""),
    "nothing_at_all": dict(logged=False, sid=""),
    "bound_empty": dict(logged=True, sid="SHEET1", portfolios=()),
    "bound_no_rows": dict(logged=True, sid="SHEET1", portfolios=("核心",)),
    "bound_with_rows": dict(logged=True, sid="SHEET1", portfolios=("核心", "衛星"), rows=_ROWS),
    "bound_list_fails": dict(logged=True, sid="SHEET1", portfolios=RuntimeError("quota")),
}


@contextlib.contextmanager
def _l3(svc: types.ModuleType, hs: types.ModuleType):
    """讓頁面／狀態列 late import 到指定版本的兩支 L3。"""
    _old = {n: sys.modules.get(n) for n in (_SVC_NAME, _HS_NAME)}
    sys.modules[_SVC_NAME], sys.modules[_HS_NAME] = svc, hs
    try:
        yield
    finally:
        for n, m in _old.items():
            sys.modules[n] = m


def _old_world():
    """修前的三支（本批新增點全部中和）。"""
    return (_mutant(SVC, _SVC_FIELD), _mutant(HS, _HS_RAISE), _mutant(PH, _PH_BLOCK))


def _page(P, req=_REQ) -> list[tuple]:
    """整頁的綁定家族：葉2 兩張 ＋ 預覽 ＋ 戰情表家族全部（AI 按下）。"""
    b = P.load_binding(req)
    h = P.load_holdings(req)
    st_ = P.load_station(h)
    sw = P.load_switch(st_, P.MacroReadout(requested=True), h)
    dp = P.load_deep(st_)
    ai = P.load_ai_summary(True, st_, sw)
    return ([P.build_binding_card(b), P.build_portfolio_count_card(b),
             P.build_holdings_preview_card(h)]
            + list(P.build_conclusion_cards(st_))
            + [P.build_lightwall_card(st_), P.build_take_profit_card(st_),
               P.build_allocation_split_card(st_), P.build_core_satellite_card(st_),
               P.build_switch_card(sw, st_), P.build_stress_card(dp), P.build_var_card(dp),
               P.build_dividend_cash_card(dp), P.build_ai_summary_card(ai, st_)])


def _fp(P, built) -> str:
    card, facts, sig = built
    return repr((card, tuple(facts), sig)) + P.v2_card_html(card, facts, sig)


#: 讀失敗時，每張卡該落到的**既有**紅卡 `now`（沒有一則是本批新寫的）。
_EXPECTED_RED_NOW = {
    "hold.binding": PH.BINDING_FAILED_NOW,
    "hold.portfolio_count": PH.COUNT_FAILED_NOW,
    "hold.setup.preview": PH.PREVIEW_FAILED_NOW,
    PH.CONCLUSION_ACTION_KEY: PH.ACTION_FAILED_NOW,
    PH.CONCLUSION_CONFIDENCE_KEY: PH.CONF_FAILED_NOW,
    PH.CONCLUSION_TODO_KEY: PH.TODO_FAILED_NOW,
    "hold.lightwall": PH.LIGHTWALL_FAILED_NOW,
    "hold.take_profit": PH.TP_FAILED_NOW,
    "hold.alloc_split": PH.SPLIT_FAILED_NOW,
    "hold.deep.core_satellite": PH.SPLIT_FAILED_NOW,
    "hold.switch": PH.SWITCH_FAILED_NOW,
    "hold.deep.stress": PH.STRESS_FAILED_NOW,
    "hold.deep.var": PH.VAR_FAILED_NOW,
    "hold.deep.dividend_cash": PH.CASH_FAILED_NOW,
    "hold.ai_summary": PH.AI_UPSTREAM_NOW,
}


# ══════════════════════════════════════════════════════════════════
# 根因釘住：修前，讀失敗 = 整個綁定家族灰卡「你還沒有綁定持股 Sheet」
# ══════════════════════════════════════════════════════════════════
class TestRootCause:
    @pytest.mark.parametrize("case", sorted(_FAILURES))
    def test_before_this_batch_a_read_failure_was_the_grey_not_bound(self, l1, case):
        l1(**_FAILURES[case][0])
        svc, hs, ph = _old_world()
        with _l3(svc, hs):
            builts = _page(ph, ph.HoldRequest(submitted=True, mode=ph.SCOPE_WITH_BINDING))
        by_key = {b[0].key: b[0] for b in builts}
        assert by_key["hold.binding"].state == UI_EMPTY
        assert by_key["hold.binding"].note.now == PH.NOT_BOUND_NOW
        assert _VALID in by_key["hold.binding"].note.why
        assert by_key["hold.setup.preview"].note.now == PH.NOT_BOUND_NOW
        assert by_key["hold.lightwall"].note.now == PH.NOT_BOUND_NOW

    def test_the_real_l1_swallows_a_broken_oauth_module_into_false(self, monkeypatch):
        """L1 `_has_oauth_tokens()` 的既有行為（⛔ 本批不改）：import 失敗 → False、不拋。"""
        monkeypatch.setitem(sys.modules, "src.data.portfolio.oauth_state", None)
        assert GSP._has_oauth_tokens() is False
        assert "oauth_state halted" in GSP._oauth_import_error()


# ══════════════════════════════════════════════════════════════════
# (a) 讀失敗 → 紅（每張卡各自既有的紅卡）
# ══════════════════════════════════════════════════════════════════
class TestReadFailureIsRed:
    @pytest.mark.parametrize("case", sorted(_FAILURES))
    def test_a_l3_keeps_unbound_but_records_the_error(self, l1, case):
        cfg, needle = _FAILURES[case]
        l1(**cfg)
        bs = SVC.get_binding_state()
        assert bs.status == SVC.STATUS_UNBOUND, "全域狀態列看的 status 照舊（它不讀 read_error）"
        assert bs.portfolio_count is None
        assert needle in bs.read_error

    @pytest.mark.parametrize("case", sorted(_FAILURES))
    def test_a_every_binding_family_card_is_its_existing_red(self, l1, case):
        cfg, needle = _FAILURES[case]
        l1(**cfg)
        builts = _page(PH)
        assert {b[0].key for b in builts} == set(_EXPECTED_RED_NOW), "整個綁定家族每一張都要驗"
        for card, facts, sig in builts:
            if card.key not in _EXPECTED_RED_NOW:
                continue
            assert card.state == UI_FAILED, f"{card.key} 不是紅卡：{card.state}"
            assert card.note.now == _EXPECTED_RED_NOW[card.key], card.key
            assert card.note.now != PH.NOT_BOUND_NOW, card.key
            assert _VALID not in card.note.why, card.key
            html = PH.v2_card_html(card, facts, sig)
            assert PH.NOT_BOUND_NOW.strip("*") not in html, card.key

    @pytest.mark.parametrize("case", sorted(_FAILURES))
    def test_a_the_binding_readout_is_the_existing_l3_raised_readout(self, l1, case):
        """與既有 (d)「L3 拋例外」**同一個讀數形狀** —— 所以產生的 Note 全是既有的。"""
        cfg, needle = _FAILURES[case]
        l1(**cfg)
        b = PH.load_binding(_REQ)
        assert b == PH.BindingReadout(requested=True, submitted=True, count_requested=True,
                                      error=SVC.get_binding_state().read_error)
        card = PH.build_binding_card(b)[0]
        assert card.note.why == PH._error_why(PH.SRC_BINDING, b.error)
        assert needle in card.note.why, "例外原文要看得見（回報維護者用）"

    @pytest.mark.parametrize("case", sorted(_FAILURES))
    def test_a_holdings_l3_raises_instead_of_an_empty_unbound_list(self, l1, case):
        cfg, needle = _FAILURES[case]
        l1(**cfg)
        with pytest.raises(RuntimeError, match=needle):
            HS.get_holdings()
        h = PH.load_holdings(_REQ)
        assert h.error and needle in h.error and h.holdings == () and h.bound is False

    def test_a_both_reads_failing_reports_both(self, l1):
        l1(logged=RuntimeError("token boom"), sid=KeyError("sid boom"))
        err = SVC.get_binding_state().read_error
        assert "token boom" in err and "sid boom" in err

    def test_a_a_real_broken_oauth_module_turns_red_end_to_end(self, l1, monkeypatch):
        """真的走 L1：`oauth_state` 載不進來 → 真 `_has_oauth_tokens()` 回 False → 探針分出來 → 紅。"""
        l1(logged=None, sid="SHEET1")
        monkeypatch.setitem(sys.modules, "src.data.portfolio.oauth_state", None)
        bs = SVC.get_binding_state()
        assert (bs.status, bs.logged_in) == (SVC.STATUS_UNBOUND, False)
        assert "oauth_state halted" in bs.read_error
        card = PH.build_binding_card(PH.load_binding(_REQ))[0]
        assert card.state == UI_FAILED and card.note.now == PH.BINDING_FAILED_NOW


# ══════════════════════════════════════════════════════════════════
# (b) 真的結果 ／ 沒按鈕 → 原封不動；全域狀態列與其他卡一字不變
# ══════════════════════════════════════════════════════════════════
class TestGenuineUnchanged:
    @pytest.mark.parametrize("case", sorted(_GENUINE))
    def test_b_whole_binding_family_is_byte_identical_to_before(self, l1, case):
        l1(**_GENUINE[case])
        new = [_fp(PH, b) for b in _page(PH)]
        svc, hs, ph = _old_world()
        with _l3(svc, hs):
            old = [_fp(ph, b) for b in _page(ph, ph.HoldRequest(submitted=True,
                                                                mode=ph.SCOPE_WITH_BINDING))]
        assert new == old
        assert SVC.get_binding_state().read_error == ""

    def test_b_genuine_unbound_is_still_the_grey_valid_result(self, l1):
        l1(**_GENUINE["not_logged_in"])
        by_key = {b[0].key: b[0] for b in _page(PH)}
        assert by_key["hold.binding"].state == UI_EMPTY
        assert by_key["hold.binding"].note.now == PH.NOT_BOUND_NOW
        assert _VALID in by_key["hold.binding"].note.why
        assert by_key["hold.lightwall"].note.now == PH.NOT_BOUND_NOW

    def test_b_the_real_probe_is_empty_when_the_module_loads(self):
        assert GSP._oauth_import_error() == ""

    def test_b_oauth_not_configured_is_not_set_up_not_a_failure(self, l1, monkeypatch):
        """判定：OAuth Client 沒設定 ＝「還沒設定」（灰），⛔ 不是讀取失敗（紅）。真的走 L1。"""
        l1(logged=None, sid="SHEET1")
        monkeypatch.setattr(OS, "is_oauth_configured", lambda: False)
        bs = SVC.get_binding_state()
        assert (bs.status, bs.logged_in, bs.read_error) == (SVC.STATUS_UNBOUND, False, "")
        card = PH.build_binding_card(PH.load_binding(_REQ))[0]
        assert card.state == UI_EMPTY and card.note.now == PH.NOT_BOUND_NOW

    def test_b_not_requested_touches_nothing(self, l1):
        l1(logged=RuntimeError("must not be read"), sid=KeyError("must not be read"))
        for req in (PH.HoldRequest(submitted=False),
                    PH.HoldRequest(submitted=True, mode=PH.SCOPE_MARKET)):
            b = PH.load_binding(req)
            assert b.requested is False and b.error == ""
            assert PH.build_binding_card(b)[0].state == UI_IDLE
            assert PH.load_holdings(req).error == ""

    def test_b_live_binding_still_live(self, l1):
        l1(**_GENUINE["bound_with_rows"])
        by_key = {b[0].key: b[0] for b in _page(PH)}
        assert by_key["hold.binding"].state == UI_LIVE
        assert by_key["hold.portfolio_count"].value == "2 本"

    def test_b_list_failure_keeps_its_pr690_shape(self, l1):
        """組合清單讀失敗 ⛔ 不記進 read_error：綁定卡 live、本數卡紅（PR #690 的 MISS_FETCH_FAILED）。"""
        l1(**_GENUINE["bound_list_fails"])
        bs = SVC.get_binding_state()
        assert (bs.status, bs.portfolio_count, bs.read_error) == (SVC.STATUS_BOUND, None, "")
        b = PH.load_binding(_REQ)
        assert b.error == "" and b.count_missing_reason == PH.MISS_FETCH_FAILED
        assert PH.build_binding_card(b)[0].state == UI_LIVE
        assert PH.build_portfolio_count_card(b)[0].state == UI_FAILED


class TestGlobalStatusBarByteIdentical:
    """全域「🔗 我的組合」狀態列（app.py 每頁最頂）：讀失敗時照舊 ⚪ 未綁定 —— 一字不變。"""

    @staticmethod
    def _render(monkeypatch, svc):
        from tests.test_portfolio_status_bar import _FakeSt
        import src.ui.tabs.portfolio_binder as pb

        fst = _FakeSt()
        monkeypatch.setattr(BAR, "st", fst)
        seen = []
        monkeypatch.setattr(pb, "render_holdings_binder", lambda *a, **k: seen.append(k))
        with _l3(svc, HS):
            BAR.render_portfolio_status_bar()
            bs = svc.get_binding_state()
        return fst.calls, seen, (bs.logged_in, bs.sheet_id, bs.portfolio_count, bs.status)

    @pytest.mark.parametrize("case", sorted(_FAILURES) + sorted(_GENUINE))
    def test_b_status_bar_is_byte_identical_with_or_without_this_batch(self, l1, monkeypatch,
                                                                       case):
        l1(**(_FAILURES[case][0] if case in _FAILURES else _GENUINE[case]))
        new = self._render(monkeypatch, SVC)
        old = self._render(monkeypatch, _mutant(SVC, _SVC_FIELD))
        assert new == old
        assert new[0], "狀態列真的畫了東西（否則比對沒意義）"

    def test_b_positional_four_field_construction_still_works(self):
        bs = SVC.BindingState(False, "", None, SVC.STATUS_UNBOUND)
        assert bs.read_error == ""
        assert BAR._label_for(bs) == ("⚪ 我的組合：未綁定",
                                      "點開登入 + 選一份 Google Sheet,之後各頁自動載入")


class TestOtherHoldCardsByteIdentical:
    def test_b_p04_enumeration_is_byte_identical_with_or_without_this_batch(self):
        """test_p04 `_enumerate()` 全窮舉（所有 build_* × readout 組合）：修前修後逐卡 hash 相同。"""
        from tests import test_p04_hold_v2_cards as E

        def _hashes(P):
            _orig = E.P
            E.P = P
            try:
                _notes, builts = E._enumerate()
            finally:
                E.P = _orig
            return [(b[0].key, hashlib.sha256(_fp(P, b).encode()).hexdigest()) for b in builts]

        before = _hashes(_old_world()[2])
        after = _hashes(PH)
        assert len(before) == len(after) > 1000
        assert before == after


# ── 呼叫點：新欄位／新探針只有這幾處在讀；其他 caller 一行都沒碰 ───────────────
class TestCallSites:
    @staticmethod
    def _refs(name: str) -> set[str]:
        out = set()
        for base in ("src", "scripts", "app.py"):
            p = _REPO / base
            for f in ([p] if p.is_file() else sorted(p.rglob("*.py"))):
                tree = ast.parse(f.read_text(encoding="utf-8"))
                for n in ast.walk(tree):
                    hit = ((isinstance(n, ast.Attribute) and n.attr == name)
                           or (isinstance(n, ast.Name) and n.id == name)
                           or (isinstance(n, ast.alias) and n.name == name)
                           or (isinstance(n, ast.Constant) and n.value == name)
                           or (isinstance(n, ast.keyword) and n.arg == name)
                           or (isinstance(n, ast.FunctionDef) and n.name == name))
                    if hit:
                        out.add(str(f.relative_to(_REPO)))
        return out

    def test_only_the_hold_page_path_reads_read_error(self):
        assert self._refs("read_error") == {
            "src/services/portfolio_binding_service.py", "src/services/holdings_service.py",
            "src/ui/views/page_hold.py"}

    def test_only_l3_binding_calls_the_new_l1_probe(self):
        assert self._refs("_oauth_import_error") == {
            "src/data/portfolio/gsheet_portfolio.py", "src/services/portfolio_binding_service.py"}

    def test_get_binding_state_callers_are_the_known_three(self):
        assert self._refs("get_binding_state") - {"src/services/portfolio_binding_service.py"} == {
            "src/services/holdings_service.py", "src/ui/tabs/portfolio_status_bar.py",
            "src/ui/views/page_hold.py"}


# ══════════════════════════════════════════════════════════════════
# (c) 突變 —— 拿掉本批的任一條，(a)／(b) 必須失敗
# ══════════════════════════════════════════════════════════════════
def _binding_card_under(svc, hs=HS, ph=PH):
    with _l3(svc, hs):
        return ph.build_binding_card(ph.load_binding(
            ph.HoldRequest(submitted=True, mode=ph.SCOPE_WITH_BINDING)))[0]


class TestMutations:
    @pytest.mark.parametrize("pair,case", [
        (_SVC_TOKEN, "token_raises"),
        (_SVC_SHEET, "sheet_raises"),
        (_SVC_PROBE, "oauth_module_broken"),
        (_SVC_FIELD, "token_raises"),
        (_SVC_FIELD, "sheet_raises")])
    def test_c_each_l3_addition_is_load_bearing(self, l1, pair, case):
        l1(**_FAILURES[case][0])
        card = _binding_card_under(_mutant(SVC, pair))
        assert card.state == UI_EMPTY and _VALID in card.note.why

    def test_c_dropping_the_page_block_turns_the_binding_card_grey(self, l1):
        l1(**_FAILURES["token_raises"][0])
        card = _binding_card_under(SVC, ph=_mutant(PH, _PH_BLOCK))
        assert card.state == UI_EMPTY and card.note.now == PH.NOT_BOUND_NOW

    def test_c_dropping_the_holdings_raise_turns_the_station_family_grey(self, l1):
        l1(**_FAILURES["token_raises"][0])
        with _l3(SVC, _mutant(HS, _HS_RAISE)):
            by_key = {b[0].key: b[0] for b in _page(PH)}
        assert by_key["hold.binding"].state == UI_FAILED, "綁定卡仍紅（page 那一條還在）"
        for k in ("hold.setup.preview", "hold.lightwall", PH.CONCLUSION_ACTION_KEY,
                  "hold.deep.var"):
            assert by_key[k].note.now == PH.NOT_BOUND_NOW, k

    def test_c_a_probe_that_swallows_again_turns_grey(self, l1, monkeypatch):
        l1(logged=None, sid="SHEET1")
        monkeypatch.setitem(sys.modules, "src.data.portfolio.oauth_state", None)
        m = _mutant(GSP, _GSP_PROBE)
        monkeypatch.setattr(GSP, "_oauth_import_error", m._oauth_import_error)
        assert SVC.get_binding_state().read_error == ""
        assert _binding_card_under(SVC).state == UI_EMPTY

    def test_c_a_probe_that_calls_not_configured_a_failure_breaks_b(self, l1, monkeypatch):
        """反向突變：把「OAuth 沒設定」也判成失敗 → (b) 的「沒設定＝灰」必須抓到。"""
        l1(logged=None, sid="SHEET1")
        monkeypatch.setattr(OS, "is_oauth_configured", lambda: False)
        m = _mutant(GSP, ("    del is_oauth_configured   # 只驗「載不載得進來」（與 `_has_oauth_tokens()` 同一行 import）\n"
                          "    return ''",
                          "    return '' if is_oauth_configured() else 'not configured'"))
        monkeypatch.setattr(GSP, "_oauth_import_error", m._oauth_import_error)
        assert _binding_card_under(SVC).state == UI_FAILED
