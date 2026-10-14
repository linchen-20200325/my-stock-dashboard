"""批 Z54：新 UI 三張「⛔ 未接線」卡接上真實資料的守衛。

  ① 「🚦 今天」頂部狀態列「Sheet 綁定」← L3 `portfolio_binding_service.get_binding_presence()`
     （只讀登入／Sheet 識別碼，⛔ 不呼叫 list_portfolios —— QA D3）
  ② 「📖 憑什麼 › 進階診斷」「門檻校準」← L3 `calibration_status_service.get_calibration_status()`
     （數值＝判燈程式此刻實際使用的 L2 常數；檔內值不一致 ⇒ 紅 —— QA D1）
  ③ 「📖 憑什麼 › 進階診斷」「資料源清單」← L3 `data_registry_summary_service.summarize_data_registry()`

每一張卡：已接線正常態／未綁或未寫入的灰態／讀取失敗的紅態／邊界；
revert-pair 突變（把接線拔掉 ⇒ 守衛必須轉紅；測試內不呼叫 git）；正常路徑其他卡不變。
"""
from __future__ import annotations

import ast
import dataclasses
import json
import pathlib
import re
import sys
import textwrap

import pytest

from shared import ia_nav
from shared import macro_calibration as MC
from shared.ui_state import (
    UI_EMPTY,
    UI_FAILED,
    UI_LIVE,
    UI_MISSING_RETRYABLE,
    UI_UNWIRED,
)
from src.services import data_registry_summary_service as RS
from src.services import calibration_status_service as CS
from src.services import portfolio_binding_service as PB
from src.services.portfolio_binding_service import BindingPresence
from src.ui.tabs import tab_today as TT
from src.ui.views import page_today as T
from src.ui.views import page_why as P

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_WIREFRAME = (_ROOT / "docs" / "wireframes" / "stock_ia_v1.html").read_text(encoding="utf-8")
_E = "RuntimeError('boom')"

_BOUND = BindingPresence(logged_in=True, sheet_bound=True)
_UNBOUND = BindingPresence(logged_in=False, sheet_bound=False)
_LOGGED_NO_SHEET = BindingPresence(logged_in=True, sheet_bound=False)
_READ_ERR = BindingPresence(logged_in=False, sheet_bound=False,
                            read_error="KeyError('gsheet_tokens')")
#: 側欄實際入口的字面（取自 `app.py` 側欄原始碼；`test_sidebar_entry_literals_exist_in_app` 核對）。
_SIDEBAR_SECTION = "🔐 Google 帳號"
_SIDEBAR_FIELD = "Google Sheet ID 或完整 URL（系統會自動解析 ID）"


def _today_html(card) -> str:
    return T.v2_card_html(T._tiles_of_cards((card,))[0])


# ══════════════════════════════════════════════════════════════════
# ① 今天頁「Sheet 綁定」
# ══════════════════════════════════════════════════════════════════
class TestSheetBindingCard:

    def test_bound_is_live_and_says_so(self):
        card = T.build_sheet_binding_card(_BOUND)
        assert card.state == UI_LIVE and card.value == T.SHEET_BOUND_VALUE
        out = _today_html(card)
        assert "已綁 Sheet" in out
        # 線框裡的 Sheet 名稱「我的持股」L3 沒有 ⇒ 不得捏造。
        assert "我的持股" not in out

    @pytest.mark.parametrize("state", [_UNBOUND, _LOGGED_NO_SHEET], ids=["logged_out", "no_sheet"])
    def test_unbound_is_grey_not_red(self, state):
        card = T.build_sheet_binding_card(state)
        assert card.state == UI_EMPTY, "未綁是有效結果，⛔ 不是紅"
        assert card.note.now == T.SHEET_UNBOUND_NOW
        assert card.note.where == T.SHEET_UNBOUND_WHERE
        assert T.v2_card_badge_n(card) != 6
        assert "尚未綁定 Sheet" in _today_html(card)

    def test_l3_exception_is_red_with_three_elements(self, monkeypatch):
        def _boom():
            raise RuntimeError("google down 🔴")
        monkeypatch.setattr(PB, "get_binding_presence", _boom)
        state, err = T.load_sheet_binding()
        assert state is None and "google down" in err
        card = T.build_sheet_binding_card(state, error=err)
        assert card.state == UI_FAILED
        assert card.note.now == T.SHEET_FAILED_NOW
        assert T.SRC_BINDING in card.note.why and "google down" in card.note.why
        assert card.note.where == T.SHEET_FAILED_WHERE
        out = _today_html(card)
        assert T.v2_card_badge_n(card) == 6 and "綁定狀態讀不出來" in out

    def test_swallowed_read_error_is_restored_to_red(self, monkeypatch):
        """L3 把「讀 token 拋例外」吞成 unbound ＋ read_error ⇒ 本頁還原成紅（⛔ 不畫成「你還沒綁」）。"""
        monkeypatch.setattr(PB, "get_binding_presence", lambda: _READ_ERR)
        state, err = T.load_sheet_binding()
        assert state is None and "gsheet_tokens" in err
        assert T.build_sheet_binding_card(state, error=err).state == UI_FAILED

    def test_secret_in_error_is_scrubbed_on_the_face(self):
        err = "OSError('/home/someone/.streamlit/secrets.toml not readable')"
        out = _today_html(T.build_sheet_binding_card(None, error=err))
        assert "/home/someone" not in out

    def test_copy_comes_from_wireframe_and_hold_page_not_new_wording(self):
        from src.ui.views import page_hold as H
        # 線框狀態列 live / grey 原文
        assert "🔗 已綁 Sheet「我的持股」" in _WIREFRAME and "🔗 尚未綁定 Sheet" in _WIREFRAME
        assert T.SHEET_BOUND_VALUE in "🔗 已綁 Sheet「我的持股」"
        assert T.SHEET_UNBOUND_NOW in "🔗 尚未綁定 Sheet"
        # 其餘四句 = 💼 我的持股頁同一件事的既有原文
        assert H.NOT_BOUND_WHY.startswith(T.SHEET_UNBOUND_WHY)
        assert H.NOT_BOUND_WHERE.startswith(T.SHEET_UNBOUND_WHERE)
        assert T.SHEET_FAILED_NOW == H.BINDING_FAILED_NOW
        assert T.SHEET_FAILED_WHERE == H._V2_CHECK_NET
        # 出處講對：本頁讀的是 `get_binding_presence`（頁4 讀 `get_binding_state`）。
        assert "get_binding_presence" in T.SRC_BINDING and "get_binding_state" in H.SRC_BINDING

    def test_unbound_pointer_is_the_sidebar_entry_not_the_hidden_tab(self):
        """新版模式 `app.py` 畫完側欄就 `st.stop()`，📁 組合管理分頁看不到 ⇒ 指路改指側欄（兩頁一起）。"""
        from src.ui.views import page_hold as H
        pick = dict(next(s.facts for s in H.SETUP_UNWIRED_SPECS
                         if s.key == "hold.setup.pick_sheet"))["現行入口"]
        for where in (T.SHEET_UNBOUND_WHERE, H.NOT_BOUND_WHERE, pick):
            assert _SIDEBAR_SECTION in where and _SIDEBAR_FIELD in where, where
            assert "組合管理" not in where, where

    def test_sidebar_entry_literals_exist_in_app(self):
        """側欄字面逐字取自 app.py，且畫在新版分支 `st.stop()` 之前（看得到）。"""
        src = (_ROOT / "app.py").read_text(encoding="utf-8")
        i_sec = src.index(f"st.markdown('### {_SIDEBAR_SECTION}')")
        i_field = src.index(f"'{_SIDEBAR_FIELD}'")
        i_stop = src.index("if _IA_PAGE is not None:")
        assert i_sec < i_field < i_stop
        assert src.index("st.stop()", i_stop) < src.index("'📁 組合管理'", i_stop), (
            "舊頁籤（含 📁 組合管理）應在新版分支 st.stop() 之後 —— 前提變了就要重看指路")

    def test_exit_phrases_are_excerpts_and_registered(self):
        _reg = {id(c): p for c, p in T.V2_EXIT_PHRASES}
        for where in (T.SHEET_UNBOUND_WHERE, T.SHEET_FAILED_WHERE):
            assert id(where) in _reg
            assert _reg[id(where)] in where and len(_reg[id(where)]) <= 30

    @staticmethod
    def _count_list_calls(monkeypatch) -> list:
        """已登入＋已設 Sheet；`list_portfolios` 換成**計次**替身（正常回空清單、⛔ 不拋例外 ——
        拋例外會被 L3 的 `except Exception` 吞掉，計不到「有沒有打」）。"""
        from src.data.portfolio import gsheet_portfolio as G
        monkeypatch.setattr(G, "_has_oauth_tokens", lambda: True)
        monkeypatch.setattr(G, "_get_active_sheet_id", lambda: "SHEET1")
        calls: list = []
        monkeypatch.setattr(G, "list_portfolios", lambda *a, **k: calls.append((a, k)) or [])
        return calls

    @staticmethod
    def _assert_today_card_lists_nothing(calls: list) -> None:
        state, err = T.load_sheet_binding()
        assert err == "" and T.build_sheet_binding_card(state, error=err).state == UI_LIVE
        assert calls == [], f"今天頁的 Sheet 綁定格讀了組合清單 {len(calls)} 次（不得連 Google）"

    def test_presence_never_lists_portfolios(self, monkeypatch):
        """QA D3：已登入＋已設 Sheet 時，今天頁這一格⛔ 不呼叫 list_portfolios（以呼叫次數驗）。"""
        calls = self._count_list_calls(monkeypatch)
        p = PB.get_binding_presence()
        assert p.sheet_bound and p.logged_in and p.read_error == ""
        self._assert_today_card_lists_nothing(calls)

    def test_presence_derived_from_binding_state_turns_red(self, monkeypatch):
        """突變 N12：presence 改由 `get_binding_state()` 推導 ⇒ 會讀組合清單 ⇒ 上一條守衛必須轉紅。"""
        calls = self._count_list_calls(monkeypatch)

        def _mutant():
            b = PB.get_binding_state()
            return PB.BindingPresence(logged_in=b.logged_in,
                                      sheet_bound=b.status != PB.STATUS_UNBOUND,
                                      read_error=b.read_error)
        monkeypatch.setattr(PB, "get_binding_presence", _mutant)
        with pytest.raises(AssertionError, match="讀了組合清單"):
            self._assert_today_card_lists_nothing(calls)
        assert len(calls) >= 1

    def test_presence_agrees_with_binding_state_on_bound_or_not(self, monkeypatch):
        """兩支共用同一份判定（`_read_login_and_sheet`）：有沒有綁、read_error 必須一致。"""
        from src.data.portfolio import gsheet_portfolio as G
        monkeypatch.setattr(G, "list_portfolios", lambda **_k: [])
        for logged, sid in ((True, "S"), (True, ""), (False, "S"), (False, "")):
            monkeypatch.setattr(G, "_has_oauth_tokens", lambda v=logged: v)
            monkeypatch.setattr(G, "_get_active_sheet_id", lambda v=sid: v)
            a, b = PB.get_binding_presence(), PB.get_binding_state()
            assert a.sheet_bound == (b.status != PB.STATUS_UNBOUND), (logged, sid)
            assert a.read_error == b.read_error

    def test_page_today_imports_only_the_presence_query(self):
        tree = ast.parse(pathlib.Path(T.__file__).read_text(encoding="utf-8"))
        names = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                 and (n.module or "").endswith("portfolio_binding_service") for a in n.names}
        assert names == {"get_binding_presence"}, names

    def test_only_the_sheet_card_is_replaced(self):
        bars = TT.build_status_bar_cards(None)
        sheet = T.build_sheet_binding_card(_BOUND)
        out = T.status_bar_cards_with_sheet(bars, sheet)
        assert [c.key for c in out] == [c.key for c in bars]
        for before, after in zip(bars, out):
            if before.key == "statusbar.sheet":
                assert after is sheet and before.state == UI_UNWIRED
            else:
                assert after is before, "交易日／總經兩格必須原物件照用"

    def test_missing_or_duplicate_slot_fails_loud(self):
        bars = TT.build_status_bar_cards(None)
        sheet = T.build_sheet_binding_card(_BOUND)
        with pytest.raises(KeyError):
            T.status_bar_cards_with_sheet([c for c in bars if c.key != "statusbar.sheet"], sheet)
        with pytest.raises(KeyError):
            T.status_bar_cards_with_sheet(list(bars) + [bars[-1]], sheet)

    def test_tab_today_skeleton_untouched(self):
        """`tab_today.py` 一個字都沒動：它的骨架（無 production caller）仍標未接線。"""
        _cards = {c.key: c for c in TT.build_status_bar_cards(None)}
        assert _cards["statusbar.sheet"].state == UI_UNWIRED


# ── revert-pair：把接線拔掉 ⇒ 守衛轉紅 ─────────────────────────────────
_TODAY_SCRIPT = textwrap.dedent("""
    import src.services.portfolio_binding_service as B
    from src.services.portfolio_binding_service import BindingPresence
    B.get_binding_presence = lambda: BindingPresence(logged_in=True, sheet_bound=True)
    from src.ui.views import page_today as T
    if {unwire!r}:
        T.status_bar_cards_with_sheet = lambda bars, sheet: tuple(bars)
    T.render_page_today()
""")


def _run_today(tmp_path, *, unwire: bool) -> str:
    from streamlit.testing.v1 import AppTest
    import src.services.portfolio_binding_service as B
    import src.ui.views.page_today as _T

    _saved = (B.get_binding_presence, _T.status_bar_cards_with_sheet)
    script = tmp_path / f"_z54_today_{int(unwire)}.py"
    script.write_text(_TODAY_SCRIPT.format(unwire=unwire), encoding="utf-8")
    try:
        at = AppTest.from_file(str(script), default_timeout=180)
        at.run()
        assert not at.exception, at.exception
        return "\n".join(m.value for m in at.markdown)
    finally:
        B.get_binding_presence, _T.status_bar_cards_with_sheet = _saved


def _assert_sheet_wired(md: str) -> None:
    assert "已綁 Sheet" in md, "狀態列的 Sheet 綁定卡沒有接上 L3"
    assert "Sheet 綁定狀態尚未接線" not in md, "狀態列仍畫著未接線那一格"


def test_today_page_apptest_draws_the_wired_sheet_card(tmp_path):
    _assert_sheet_wired(_run_today(tmp_path, unwire=False))


def test_today_page_unwiring_turns_the_guard_red(tmp_path):
    with pytest.raises(AssertionError):
        _assert_sheet_wired(_run_today(tmp_path, unwire=True))


def test_today_page_cold_start_real_binding_service_has_no_red_sheet_card(tmp_path):
    """冷啟動、真的 L3（沙箱沒有 Google 登入）→ 整頁無例外，Sheet 那一格是灰的「尚未綁定 Sheet」。"""
    from streamlit.testing.v1 import AppTest

    script = tmp_path / "_z54_today_cold.py"
    script.write_text("from src.ui.views.page_today import render_page_today\n"
                      "render_page_today()\n", encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=180)
    at.run()
    assert not at.exception, at.exception
    md = "\n".join(m.value for m in at.markdown)
    assert "Sheet 綁定" in md
    _sheet = [m for m in md.split('<div class="blk blk-') if "Sheet 綁定" in m]
    assert _sheet and all("綁定狀態讀不出來" not in s for s in _sheet), _sheet
    assert any("尚未綁定 Sheet" in s or "已綁 Sheet" in s for s in _sheet), _sheet


# ══════════════════════════════════════════════════════════════════
# ② 門檻校準（L0 唯讀 metadata）
# ══════════════════════════════════════════════════════════════════
def _write(tmp_path, obj, raw: str | None = None) -> str:
    _p = tmp_path / "macro_thresholds.json"
    _p.write_text(raw if raw is not None else json.dumps(obj), encoding="utf-8")
    return str(_p)


_GOOD = {"HEALTH_DEFENSE_THRESHOLD": 35, "BULL_MIN_SCORE": 4,
         "last_calibrated": None, "method": "default (uncalibrated)"}


class TestCalibrationMeta:

    def test_real_file_and_running_constants(self):
        """真檔：檔內原值照實；卡上數值來源是 L2 執行中常數。"""
        from src.compute.macro import macro_helpers as MH
        _raw = json.loads((_ROOT / "macro_thresholds.json").read_text(encoding="utf-8"))
        meta = MC.read_calibration_meta()
        assert meta.last_calibrated == _raw["last_calibrated"] and meta.method == _raw["method"]
        st = CS.get_calibration_status()
        assert (st.effective_health_defense_threshold, st.effective_bull_min_score) == (
            MH.HEALTH_DEFENSE_THRESHOLD, MH.BULL_MIN_SCORE)
        assert (st.file_health_defense_threshold, st.file_bull_min_score) == (
            _raw["HEALTH_DEFENSE_THRESHOLD"], _raw["BULL_MIN_SCORE"])

    def test_null_and_uncalibrated_are_not_beautified(self, monkeypatch, tmp_path):
        monkeypatch.setattr(MC, "_CALIBRATION_PATH", _write(tmp_path, _GOOD))
        card, facts, _s = P.build_calibration_card(
            P.load_calibration(P.EngineerRequest(opened=True)))
        assert card.state == UI_LIVE and card.value == "default (uncalibrated)"
        f = dict(facts)
        assert f["last_calibrated"] == "null"
        assert f["HEALTH_DEFENSE_THRESHOLD"] == "35" and f["BULL_MIN_SCORE"] == "4"
        out = P.v2_card_html(card, facts, "")
        assert "default (uncalibrated)" in out and "null" in out
        assert "已校準" not in out

    def test_numbers_are_the_running_constants_not_the_file(self, monkeypatch, tmp_path):
        """QA D1：檔案改成 40（範圍內）但執行中常數仍 35 ⇒ 紅，兩組值都寫出，⛔ 不印 40 當生效值。"""
        from src.compute.macro import macro_helpers as MH
        monkeypatch.setattr(MC, "_CALIBRATION_PATH", _write(tmp_path, {
            **_GOOD, "HEALTH_DEFENSE_THRESHOLD": 40, "last_calibrated": "2026-10-01",
            "method": "youden_j"}))
        monkeypatch.setattr(MH, "HEALTH_DEFENSE_THRESHOLD", 35)
        monkeypatch.setattr(MH, "BULL_MIN_SCORE", 4)
        card, facts, _s = P.build_calibration_card(
            P.load_calibration(P.EngineerRequest(opened=True)))
        assert card.state == UI_FAILED
        assert card.note.now == P.L0_FAILED_NOW_TEMPLATE.format(label="門檻校準")
        assert "寫 HEALTH_DEFENSE_THRESHOLD=40 / BULL_MIN_SCORE=4" in card.note.why
        assert "實際使用 HEALTH_DEFENSE_THRESHOLD=35 / BULL_MIN_SCORE=4" in card.note.why
        assert "HEALTH_DEFENSE_THRESHOLD" not in dict(facts), "⛔ 不另列一組數字冒充生效值"
        out = P.v2_card_html(card, facts, "")
        assert "檔內寫的不是判燈程式實際使用的值" in out and P.v2_card_badge_n(card) == 6

    def test_consistent_running_constants_show_live(self, monkeypatch, tmp_path):
        from src.compute.macro import macro_helpers as MH
        monkeypatch.setattr(MC, "_CALIBRATION_PATH", _write(tmp_path, {
            **_GOOD, "HEALTH_DEFENSE_THRESHOLD": 40, "last_calibrated": "2026-10-01",
            "method": "youden_j"}))
        monkeypatch.setattr(MH, "HEALTH_DEFENSE_THRESHOLD", 40)
        monkeypatch.setattr(MH, "BULL_MIN_SCORE", 4)
        card, facts, _s = P.build_calibration_card(
            P.load_calibration(P.EngineerRequest(opened=True)))
        assert card.state == UI_LIVE and card.value == "youden_j"
        assert dict(facts)["HEALTH_DEFENSE_THRESHOLD"] == "40"
        assert dict(facts)["last_calibrated"] == "2026-10-01"

    def test_mismatch_guard_revert_pair(self, monkeypatch):
        """突變：`consistent` 恆真 ⇒ 不一致時會畫綠卡 —— 守衛必須抓到。"""
        bad = CS.CalibrationStatus(35, 4, 40, 4, None, "m")

        def _guard(status):
            card, _f, _s = P.build_calibration_card(
                P.CalibrationReadout(requested=True, status=status))
            assert card.state == UI_FAILED, "檔內值≠生效值卻沒有轉紅"
        _guard(bad)
        monkeypatch.setattr(CS.CalibrationStatus, "consistent", property(lambda _s: True))
        with pytest.raises(AssertionError):
            _guard(bad)

    @pytest.mark.parametrize("obj,raw,exc", [
        (None, None, FileNotFoundError),                        # 缺檔
        (None, "{not json", json.JSONDecodeError),              # 壞 JSON
        ([1, 2], None, ValueError),                             # 頂層不是物件
        ({k: v for k, v in _GOOD.items() if k != "method"}, None, ValueError),  # 缺欄位
        ({**_GOOD, "BULL_MIN_SCORE": True}, None, ValueError),  # bool 不是整數
        ({**_GOOD, "last_calibrated": 20261001}, None, ValueError),  # 型別不對
    ], ids=["missing", "bad_json", "not_object", "missing_key", "bool", "bad_type"])
    def test_every_anomaly_fails_loud_and_draws_red(self, monkeypatch, tmp_path, obj, raw, exc):
        if obj is None and raw is None:
            _path = str(tmp_path / "nope.json")
        else:
            _path = _write(tmp_path, obj, raw)
        monkeypatch.setattr(MC, "_CALIBRATION_PATH", _path)
        with pytest.raises(exc):
            MC.read_calibration_meta()
        card, _f, _s = P.build_calibration_card(
            P.load_calibration(P.EngineerRequest(opened=True)))
        assert card.state == UI_FAILED and card.note.now == P.CALIBRATION_FAILED_NOW
        assert P.SRC_CALIBRATION in card.note.why and "拋出例外" in card.note.why
        P.v2_card_html(card, _f, "")   # 短句表查得到、摘錄對得上

    def test_out_of_range_file_is_red_because_running_value_is_the_default(
            self, monkeypatch, tmp_path):
        """檔內 99（越界）⇒ 判燈程式用的是預設（35）⇒ 不一致 ⇒ 紅，兩組值都寫出。"""
        from src.compute.macro import macro_helpers as MH
        monkeypatch.setattr(MC, "_CALIBRATION_PATH",
                            _write(tmp_path, {**_GOOD, "HEALTH_DEFENSE_THRESHOLD": 99}))
        monkeypatch.setattr(MH, "HEALTH_DEFENSE_THRESHOLD", MC.HEALTH_DEFENSE_THRESHOLD_DEFAULT)
        card, _f, _s = P.build_calibration_card(
            P.load_calibration(P.EngineerRequest(opened=True)))
        assert card.state == UI_FAILED and "HEALTH_DEFENSE_THRESHOLD=99" in card.note.why

    def test_production_loader_behaviour_unchanged(self, monkeypatch, tmp_path):
        """判燈用的 `load_calibrated_thresholds()` 照舊靜默退回預設值（本批一字未動）。"""
        monkeypatch.setattr(MC, "_CALIBRATION_PATH", str(tmp_path / "nope.json"))
        assert MC.load_calibrated_thresholds() == (
            MC.HEALTH_DEFENSE_THRESHOLD_DEFAULT, MC.BULL_MIN_SCORE_DEFAULT)

    def test_l0_module_stays_pure(self):
        tree = ast.parse((_ROOT / "shared" / "macro_calibration.py").read_text(encoding="utf-8"))
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
            a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert mods <= {"__future__", "json", "os", "dataclasses", "typing"}, mods

    def test_l3_calibration_service_layering(self):
        tree = ast.parse(pathlib.Path(CS.__file__).read_text(encoding="utf-8"))
        mods = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not {m for m in mods if m.startswith(("streamlit", "src.ui", "src.data", "app"))}


# ══════════════════════════════════════════════════════════════════
# ③ 資料源清單（L3 彙總）
# ══════════════════════════════════════════════════════════════════
_REG = {
    "VIX": {"category": "🌐 國際金融", "last_updated": "2026-10-09", "rows": 200,
            "frequency": "daily"},
    "DXY": {"category": "🌐 國際金融", "last_updated": "2026-10-10 00:00", "rows": 200,
            "frequency": "daily"},
    "台股加權": {"category": "🇹🇼 台股大盤", "last_updated": "N/A", "rows": 0,
              "frequency": "daily", "missing": True},
    "無分類": {"last_updated": "2026-01-01", "rows": 1},
    "新分類": {"category": "🧪 實驗", "last_updated": "", "rows": 1},
}


class TestRegistrySummary:

    def test_not_written_is_grey_retryable_not_red(self):
        s = RS.summarize_data_registry({})
        assert s.written is False and s.total == 0
        card, facts, _s = P.build_registry_card(
            P.load_registry(P.EngineerRequest(opened=True), {}))
        assert card.state == UI_MISSING_RETRYABLE
        assert card.note.now == P.REGISTRY_NOT_WRITTEN_NOW
        assert card.note.where == P.REGISTRY_NOT_WRITTEN_WHERE == (
            f"到{ia_nav.where_to_find(ia_nav.PAGE_TODAY)}更新")
        assert "到「🚦 今天」更新" in _WIREFRAME
        out = P.v2_card_html(card, facts, "")
        assert P.v2_card_badge_n(card) == 7

    def test_groups_counts_latest_missing(self):
        s = RS.summarize_data_registry({"data_registry": _REG})
        g = {x.category: x for x in s.groups}
        assert s.written and s.total == 5
        assert g["🌐 國際金融"].count == 2 and g["🌐 國際金融"].latest == "2026-10-10"
        assert g["🇹🇼 台股大盤"].missing == 1 and g["🇹🇼 台股大盤"].latest == RS.NO_DATE
        assert g[RS.CAT_FALLBACK].count == 1
        assert g["🧪 實驗"].latest == RS.NO_DATE
        card, facts, _s = P.build_registry_card(
            P.load_registry(P.EngineerRequest(opened=True), {"data_registry": _REG}))
        assert card.state == UI_LIVE and card.value == "5 筆"
        f = dict(facts)
        assert f["🌐 國際金融"] == "2 筆 · 最後更新 2026-10-10"
        assert f["🇹🇼 台股大盤"] == "1 筆 · 最後更新 N/A · 缺 1"
        P.v2_card_html(card, facts, "")

    def test_m14_latest_ignores_na_mixed_with_real_dates(self):
        """M14：同一分類混 'N/A' 與真日期 ⇒ 最新時間戳取真日期（⛔ 不讓 'N/A' 字串比較勝出）。"""
        reg = {"a": {"category": "🌐 國際金融", "last_updated": "N/A", "missing": True},
               "b": {"category": "🌐 國際金融", "last_updated": "2026-09-30"},
               "c": {"category": "🌐 國際金融", "last_updated": ""}}
        g = RS.summarize_data_registry({"data_registry": reg}).groups[0]
        assert g.latest == "2026-09-30" and g.count == 3 and g.missing == 1

    def test_m14_revert_pair(self, monkeypatch):
        """突變：拿掉日期解析（原樣取 max）⇒ 'N/A' > '2026…' 勝出 —— 斷言必須抓到。"""
        reg = {"a": {"category": "🌐 國際金融", "last_updated": "N/A"},
               "b": {"category": "🌐 國際金融", "last_updated": "2026-09-30"}}
        monkeypatch.setattr(RS, "_date_prefix", lambda v: str(v or ""))
        g = RS.summarize_data_registry({"data_registry": reg}).groups[0]
        assert g.latest != "2026-09-30"

    def test_m17_category_none_goes_to_fallback(self):
        """M17：`category=None`（與缺欄位同）⇒ 歸 `CAT_FALLBACK`，⛔ 不另開一組 None。"""
        reg = {"x": {"category": None, "last_updated": "2026-01-02"},
               "y": {"last_updated": "2026-01-01"}}
        g = {x.category: x for x in RS.summarize_data_registry({"data_registry": reg}).groups}
        assert set(g) == {RS.CAT_FALLBACK} and g[RS.CAT_FALLBACK].count == 2

    def test_m17_revert_pair(self, monkeypatch):
        """突變：把 `or CAT_FALLBACK` 拿掉 ⇒ 出現一組 None —— 上一條的斷言必須抓到。"""
        import types
        src = pathlib.Path(RS.__file__).read_text(encoding="utf-8")
        old = '_cat = _meta.get("category") or CAT_FALLBACK'
        assert src.count(old) == 1
        mod = types.ModuleType("_z54_rs_mutant")
        monkeypatch.setitem(sys.modules, mod.__name__, mod)
        exec(compile(src.replace(old, '_cat = _meta.get("category")'), "rs_mutant", "exec"),
             mod.__dict__)
        groups = mod.summarize_data_registry(
            {"data_registry": {"x": {"category": None, "last_updated": "2026-01-02"}}}).groups
        assert {g.category for g in groups} != {RS.CAT_FALLBACK}

    def test_grouping_reconciles_with_the_old_panel(self):
        """與舊面板 `compute_registry_groups` 同組同序（舊檔只讀不改；測試端 import 合法）。"""
        from src.ui.pages.data_registry_panel import compute_registry_groups
        old = compute_registry_groups({"data_registry": _REG})
        new = RS.group_registry_entries(_REG)
        assert list(old) == list(new)
        for cat in old:
            assert [e["name"] for e in old[cat]] == [n for n, _m in new[cat]]
            assert sum(bool(e["missing"]) for e in old[cat]) == next(
                g.missing for g in RS.summarize_data_registry({"data_registry": _REG}).groups
                if g.category == cat)

    @pytest.mark.parametrize("reg", [{}, {"x": 3}, ["not", "a", "dict"]],
                             ids=["empty_written", "row_not_mapping", "registry_not_mapping"])
    def test_malformed_registry_fails_loud_and_draws_red(self, reg):
        with pytest.raises(ValueError):
            RS.summarize_data_registry({"data_registry": reg})
        card, facts, _s = P.build_registry_card(
            P.load_registry(P.EngineerRequest(opened=True), {"data_registry": reg}))
        assert card.state == UI_FAILED and card.note.now == P.REGISTRY_FAILED_NOW
        assert P.SRC_REGISTRY in card.note.why
        P.v2_card_html(card, facts, "")

    def test_closed_gate_touches_no_l3(self, monkeypatch):
        class _Poison:
            def __getattr__(self, item):
                raise AssertionError(f"沒勾卻碰到 L3：{item}")
        monkeypatch.setitem(sys.modules, "src.services.data_registry_summary_service", _Poison())
        monkeypatch.setitem(sys.modules, "src.services.calibration_status_service", _Poison())
        r = P.load_registry(P.EngineerRequest(opened=False), {"data_registry": _REG})
        assert r.requested is False and r.summary is None
        c = P.load_calibration(P.EngineerRequest(opened=False))
        assert c.requested is False and c.status is None
        with pytest.raises(ValueError):
            P.build_registry_card(r)
        with pytest.raises(ValueError):
            P.build_calibration_card(c)

    def test_l3_module_has_no_streamlit_or_upward_import(self):
        tree = ast.parse(pathlib.Path(RS.__file__).read_text(encoding="utf-8"))
        mods = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
            a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not {m for m in mods if m.startswith(("streamlit", "src.ui", "src.data", "app"))}


# ══════════════════════════════════════════════════════════════════
# 憑什麼頁：五張面板卡的排列與 revert-pair
# ══════════════════════════════════════════════════════════════════
_PANEL_ORDER = ("why.engineer.registry", "why.engineer.reconcile", "why.engineer.api_root",
                "why.engineer.raw", "why.engineer.calibration")


def _assert_panels_wired(builts) -> None:
    keys = tuple(b[0].key for b in builts)
    assert keys == _PANEL_ORDER, keys
    states = {b[0].key: b[0].state for b in builts}
    assert states["why.engineer.registry"] != UI_UNWIRED, "資料源清單沒接上"
    assert states["why.engineer.calibration"] != UI_UNWIRED, "門檻校準沒接上"
    # 📌 批 Z56（有意識的更正，⛔ 不是漏改）：雙演算法對帳於批 Z56 接線 ⇒ 自「應維持未接線」移出
    #    （原句：`for k in ("why.engineer.reconcile", "why.engineer.api_root", "why.engineer.raw")`）。
    assert states["why.engineer.reconcile"] != UI_UNWIRED, "雙演算法對帳沒接上（批 Z56）"
    for k in ("why.engineer.api_root", "why.engineer.raw"):
        assert states[k] == UI_UNWIRED, f"{k} 不在本批範圍，應維持未接線"


def _real_row():
    req = P.EngineerRequest(opened=True)
    # 批 Z56：`build_engineer_panel_row` 多一個必填的雙演算法對帳讀數。
    return P.build_engineer_panel_row(P.load_registry(req, {"data_registry": _REG}),
                                      P.load_calibration(req),
                                      P.load_reconcile(req, {"mkt_info": {"score": 3}}))


def test_panel_row_is_wired_in_the_original_order():
    _assert_panels_wired(_real_row())
    assert len(P.build_engineer_panel_cards()) == 2   # 其餘兩張仍是未接線（批 Z56：原為 3，雙演算法對帳接線）


def test_unwiring_the_panels_turns_the_guard_red(monkeypatch):
    _unwired = P.build_l0_card(P.L0CardSpec(
        key="why.engineer.registry", label="資料源清單", wired=False,
        now=P.ENGINEER_RAW_NOW, why="x", where="y"))
    monkeypatch.setattr(P, "build_registry_card", lambda _r: _unwired)
    with pytest.raises(AssertionError):
        _assert_panels_wired(_real_row())


def test_other_panel_cards_unchanged():
    """沒動到的~~三張（雙演算法對帳／API 根因／原始資料表）~~兩張（API 根因／原始資料表；批 Z56 雙演算法對帳已接線）
    三要素與 facts 逐字不變。"""
    by_key = {b[0].key: b for b in P.build_engineer_panel_cards()}
    for spec in P.ENGINEER_PANEL_SPECS:
        card, facts, _s = by_key[spec.key]
        assert (card.note.now, card.note.why, card.note.where) == (spec.now, spec.why, spec.where)
        assert facts == spec.facts


def _engineer_caption(src: str) -> str:
    """`_render_engineer_block` 裡「**六個面板** —— …」那一句的字面（AST 取，⛔ 不比行號）。"""
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "_render_engineer_block")
    for c in ast.walk(fn):
        if (isinstance(c, ast.Call) and getattr(c.func, "attr", "") == "caption" and c.args
                and isinstance(c.args[0], ast.Constant) and "六個面板" in str(c.args[0].value)):
            return str(c.args[0].value)
    raise AssertionError("找不到「六個面板」那一句 caption")


def _assert_caption_matches_wiring(caption: str) -> None:
    """caption 宣稱接得上的面板 ＝ 實際接線的那幾張（＋ Fetcher 監控）；「其餘 N 個」也要對。"""
    row = _real_row()
    wired = [b[0].label for b in row if b[0].state != UI_UNWIRED]
    n_unwired = sum(1 for b in row if b[0].state == UI_UNWIRED)
    for label in ["Fetcher 監控", *wired]:
        assert f"「{label}」" in caption, f"caption 沒提到已接線的「{label}」：{caption}"
    assert "只有「Fetcher 監控」" not in caption, caption
    # 批 Z56：量詞前的 2 讀「兩」（「其餘兩個」），原表 '零一二三四五六' 的「二」在中文裡不這樣用；
    #   批 Z54 時 n=3 用不到這一格，本批 n=2 才踩到 —— 只改這一個字。
    assert f"其餘{'零一兩三四五六'[n_unwired]}個" in caption, caption


def test_m27_caption_matches_the_wiring():
    _assert_caption_matches_wiring(
        _engineer_caption(pathlib.Path(P.__file__).read_text(encoding="utf-8")))


def test_m27_reverting_the_caption_turns_red():
    """M27：caption 回舊句（只有 Fetcher 監控、其餘五個）⇒ 守衛必須轉紅。"""
    old = ("**六個面板** —— 目前只有「Fetcher 監控」接得上；"
           "其餘五個各自卡在不同的地方，逐項寫在下面。")
    with pytest.raises(AssertionError):
        _assert_caption_matches_wiring(old)


_WHY_SCRIPT = textwrap.dedent("""
    import streamlit as st
    st.session_state["data_registry"] = {reg!r}
    from src.ui.views import page_why as P
    P.render_page_why()
""")


def _run_why(tmp_path, reg) -> list[str]:
    from streamlit.testing.v1 import AppTest

    script = tmp_path / "_z54_why.py"
    script.write_text(_WHY_SCRIPT.format(reg=reg), encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=180)
    at.session_state[P.SS_ENGINEER_GATE] = True
    at.run()
    assert not at.exception, at.exception
    return [m.value for m in at.markdown]


def test_why_page_apptest_with_engineer_gate_ticked(tmp_path):
    md = "\n".join(_run_why(tmp_path, _REG))
    assert "資料源清單" in md and "5 筆" in md and "🌐 國際金融" in md
    assert "門檻校準" in md and "default (uncalibrated)" in md
    assert "全站來源清單本頁讀不到" not in md and "門檻校準本頁跑不了" not in md
    assert "這一格畫不出來" not in md


def test_why_page_apptest_registry_not_written_is_grey(tmp_path):
    from streamlit.testing.v1 import AppTest

    script = tmp_path / "_z54_why_cold.py"
    script.write_text("from src.ui.views import page_why as P\nP.render_page_why()\n",
                      encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=180)
    at.session_state[P.SS_ENGINEER_GATE] = True
    at.run()
    assert not at.exception, at.exception
    md = "\n".join(m.value for m in at.markdown)
    assert "尚未觸發 data_registry 載入" in md
    assert "資料源清單讀不出來" not in md and "這一格畫不出來" not in md
