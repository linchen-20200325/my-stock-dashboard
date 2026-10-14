"""批 Z59：① markdown-it-py 補進依賴（客戶 Q-z33＝A）② 「🚦 今天」狀態列「交易日」格接線（Q-z31）。

① 22 個測試原本以 `pytest.importorskip("markdown_it")` skip（CommonMark 解析守衛：
   `tests/test_v2_card_blank_line_guard.py` 21 個 ＋ `tests/test_lamp_direction.py` 1 個）。
   補進 CI fast lane 的測試依賴（`pr-check.yml`，與 pytest 同列）之後，**這條守衛讓「套件又被拿掉 → 22 個靜默 skip」變成紅燈**，
   ⛔ 不能再退回 skip 掩蓋（客戶明示）。

② 狀態列「交易日」← L3 `services.trading_calendar_service.get_today_trading_status()`（批 D5）。
   三態：交易日＝綠 ／ 休市＝綠（有效結果）／ 判不出來（L3 回 error 或拋例外）＝紅。
   每一輪都讀（L1 有 `TTL_1DAY` 快取 ＋ `FailCooldown` 退避）⇒ ⛔ 沒有「尚未載入」灰態。
   revert-pair 突變（把接線拔掉 ⇒ 守衛必須轉紅；測試內不呼叫 git）；正常路徑其他卡不變。
"""
from __future__ import annotations

import contextlib
import importlib
import pathlib
import re
import socket
import threading
import time
from datetime import date, datetime, timezone
from unittest import mock

import pytest

from shared.ui_state import UI_FAILED, UI_IDLE, UI_LIVE, UI_UNWIRED
from src.data.proxy import proxy_helper as PH
from src.data.stock import twse_holiday_fetcher as HF
from src.services import trading_calendar_service as TCS
from src.services.trading_calendar_service import TradingDayStatus
from src.ui.tabs import tab_today as TT
from src.ui.views import page_today as T

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_KEY = "statusbar.trading_day"

_OPEN = TradingDayStatus(today=date(2026, 9, 4), is_trading_day=True,
                         next_trading_day=date(2026, 9, 7))
_CLOSED = TradingDayStatus(today=date(2026, 10, 10), is_trading_day=False,
                           next_trading_day=date(2026, 10, 12))
_UNDETERMINED = TradingDayStatus(
    today=date(2026, 10, 14), is_trading_day=None, next_trading_day=None,
    error="TWSE:openapi/holidaySchedule 無回應（proxy／直連／中繼皆失敗）")


def _hover(html: str) -> str:
    m = re.match(r'<div title="([^"]*)">', html)
    return m.group(1) if m else ""


def _face(html: str) -> str:
    """卡面上看得到的字（去掉 hover 屬性與標籤）。"""
    return re.sub(r"<[^>]+>", " ", re.sub(r'^<div title="[^"]*">', "", html))


# ══════════════════════════════════════════════════════════════════
# ① markdown-it-py
# ══════════════════════════════════════════════════════════════════
class TestMarkdownItDependency:

    def test_ci_fast_lane_installs_it(self):
        """測試依賴走 CI fast lane 的 `pip install pytest …` 那一行（production 0 import ⇒ ⛔ 不進 requirements.txt）。"""
        wf = (_ROOT / ".github" / "workflows" / "pr-check.yml").read_text(encoding="utf-8")
        fast = wf.split("slow-tests:")[0]
        # 先去掉 `#` 之後的內容：「同一行把套件註解掉」不得被當成有裝（批 Z59 QA 4）。
        code = [ln.split("#", 1)[0] for ln in fast.splitlines()]
        line = next(ln for ln in code if ln.strip().startswith("pip install pytest"))
        assert re.search(r'"markdown-it-py>=[\d.]+,<[\d.]+"', line), line
        req = (_ROOT / "requirements.txt").read_text(encoding="utf-8")
        assert not re.search(r"^markdown-it-py", req, re.M), "測試依賴不得裝上 production"

    def test_production_does_not_import_it(self):
        files = [_ROOT / "app.py"]
        for d in ("src", "shared", "scripts"):
            files += list((_ROOT / d).rglob("*.py"))
        hits = [p for p in files if "markdown_it" in p.read_text(encoding="utf-8")]
        assert not hits, f"production 開始 import markdown_it ⇒ 須改進 requirements.txt：{hits}"

    def test_importable_so_the_22_guards_really_run(self):
        """裝不起來時 22 個 CommonMark 守衛會**靜默 skip** —— 這裡改成紅燈。"""
        md = importlib.import_module("markdown_it")
        tokens = md.MarkdownIt("commonmark").parse("<div>\na\n</div>")
        assert [t.type for t in tokens] == ["html_block"]


# ══════════════════════════════════════════════════════════════════
# ② 交易日格：三態 ＋ L3 拋例外 ＋ 冷啟動
# ══════════════════════════════════════════════════════════════════
class TestTradingDayTile:

    def test_trading_day_is_live_in_wireframe_format(self):
        t = T.build_trading_day_tile(_OPEN)
        assert t.card.state == UI_LIVE and t.card.key == _KEY
        assert t.card.label == "交易日"
        # 線框 live 原文格式「09/05 週五 ✅ 交易日」；日期換成 L3 的台北當日。
        assert t.card.value == "09/04 週五 ✅ 交易日"
        html = T.v2_card_html(t)
        assert "09/04 週五 ✅ 交易日" in _face(html)
        assert T.v2_card_badge_n(t.card) != T.v2_card_badge_n(
            T.build_trading_day_tile(None, error="x").card)

    def test_closed_is_green_valid_result_not_red(self):
        t = T.build_trading_day_tile(_CLOSED)
        assert t.card.state == UI_LIVE, "休市是判得出來的有效結果，⛔ 不是紅"
        assert t.card.value == "10/10 週六 休市"
        assert "✅" not in t.card.value
        # L3 沒有休市原因欄位 ⇒ ⛔ 不捏造（例：「國慶日」）。
        assert "國慶" not in T.v2_card_html(t)

    def test_l3_reports_undetermined_is_red_with_reason_on_face(self):
        t = T.build_trading_day_tile(_UNDETERMINED)
        assert t.card.state == UI_FAILED and t.card.value == ""
        n = t.card.note
        assert n.now == T.TRADING_DAY_FAILED_NOW
        assert n.where == T.TRADING_DAY_FAILED_WHERE
        assert _UNDETERMINED.error in n.why
        assert T.TRADING_DAY_UNDETERMINED_WHY in n.why and T.SRC_TRADING_CALENDAR in n.why
        face = _face(T.v2_card_html(t))
        # 卡面的「為什麼」那一列要看得到**原因**，⛔ 不是只剩出處前綴。
        assert "TWSE:openapi/holidaySchedule 無回應" in face
        assert "以證交所公告為準" in face

    def test_contract_drift_none_without_error_is_red_not_guessed(self):
        bad = TradingDayStatus(today=date(2026, 10, 14), is_trading_day=None,
                               next_trading_day=None, error=None)
        t = T.build_trading_day_tile(bad)
        assert t.card.state == UI_FAILED
        assert "契約漂移" in t.card.note.why

    def test_l3_raises_becomes_red_via_loader(self, monkeypatch):
        def _boom(now=None):
            raise RuntimeError("calendar exploded")
        monkeypatch.setattr(TCS, "get_today_trading_status", _boom)
        status, err = T.load_trading_day_status()
        assert status is None and "calendar exploded" in err
        t = T.build_trading_day_tile(status, error=err)
        assert t.card.state == UI_FAILED
        assert "拋出例外" in t.card.note.why and "calendar exploded" in t.card.note.why
        T.v2_card_html(t)   # 畫得出來（⛔ 不炸成補救紅卡）

    def test_glyph_in_upstream_error_still_draws_red_card(self):
        st = TradingDayStatus(today=date(2026, 10, 14), is_trading_day=None,
                              next_trading_day=None, error="🔴 上游壞了")
        t = T.build_trading_day_tile(st)
        assert t.card.state == UI_FAILED and "🔴" not in t.card.note.why
        T.v2_card_html(t)

    def test_secret_in_error_is_scrubbed(self):
        st = TradingDayStatus(today=date(2026, 10, 14), is_trading_day=None,
                              next_trading_day=None,
                              error="token=AIzaSyA1234567890abcdefghijklmnopqrstuv 失敗")
        t = T.build_trading_day_tile(st)
        assert "AIzaSyA1234567890abcdefghijklmnopqrstuv" not in T.v2_card_html(t)

    @pytest.mark.parametrize("st_err", [(_OPEN, ""), (_CLOSED, ""), (_UNDETERMINED, ""),
                                        (None, "RuntimeError('x')")],
                             ids=["open", "closed", "undetermined", "raised"])
    def test_known_limit_disclosed_in_hover_not_on_face(self, st_err):
        """L2 檔頭：臨時休市不在年度表內，呼叫端顯示時須自行揭露 —— 每一態都在 hover。"""
        html = T.v2_card_html(T.build_trading_day_tile(st_err[0], error=st_err[1]))
        assert T.TRADING_DAY_LIMIT_TEXT in _hover(html)
        assert "臨時休市" not in _face(html), "已知限制只進 hover，⛔ 不增卡面欄位"

    @pytest.mark.parametrize("d,expect", [
        (date(2026, 10, 12), "10/12 週一"), (date(2026, 10, 13), "10/13 週二"),
        (date(2026, 10, 14), "10/14 週三"), (date(2026, 10, 15), "10/15 週四"),
        (date(2026, 10, 16), "10/16 週五"), (date(2026, 10, 17), "10/17 週六"),
        (date(2026, 10, 18), "10/18 週日"), (date(2027, 1, 1), "01/01 週五")])
    def test_weekday_chars(self, d, expect):
        st = TradingDayStatus(today=d, is_trading_day=False, next_trading_day=None)
        assert T.build_trading_day_tile(st).card.value == f"{expect} 休市"


class TestThroughRealL3:
    """L1 換成假休市表，走**真的** L3 → L2 → 本頁 builder。"""

    @staticmethod
    def _cal():
        E = HF.HolidayEntry
        return HF.HolidayCalendar(
            entries=(E(date(2026, 1, 1), "開國紀念日", "依規定放假1日。", "closed"),
                     E(date(2026, 2, 28), "和平紀念日", "依規定放假1日。", "closed"),
                     E(date(2026, 10, 9), "國慶日補假", "補假1日。", "closed"),
                     E(date(2026, 10, 10), "國慶日", "依規定放假1日。", "closed")),
            covered_years=frozenset({2026}), source=HF.SOURCE_ID,
            fetched_at=datetime(2026, 10, 1, tzinfo=timezone.utc))

    @pytest.mark.parametrize("now,state,value", [
        (datetime(2026, 10, 8, 2, tzinfo=timezone.utc), UI_LIVE, "10/08 週四 ✅ 交易日"),
        (datetime(2026, 10, 9, 2, tzinfo=timezone.utc), UI_LIVE, "10/09 週五 休市"),
        # 台北 10/10 00:30 ＝ UTC 10/09 16:30 —— 日期一律台北
        (datetime(2026, 10, 9, 16, 30, tzinfo=timezone.utc), UI_LIVE, "10/10 週六 休市"),
        (datetime(2027, 1, 4, 2, tzinfo=timezone.utc), UI_FAILED, ""),   # 表未涵蓋 2027
    ])
    def test_end_to_end(self, monkeypatch, now, state, value):
        monkeypatch.setattr(HF, "fetch_twse_holiday_calendar", lambda *, taipei_year: self._cal())
        t = T.build_trading_day_tile(TCS.get_today_trading_status(now))
        assert t.card.state == state and t.card.value == value
        if state == UI_FAILED:
            assert "未涵蓋 2027" in t.card.note.why

    def test_l1_unavailable_is_red_with_l1_message(self, monkeypatch):
        def _fail(*, taipei_year):
            raise HF.HolidayCalendarUnavailable("TWSE:openapi/holidaySchedule HTTP 503")
        monkeypatch.setattr(HF, "fetch_twse_holiday_calendar", _fail)
        status, err = T.load_trading_day_status()
        assert err == "" and status is not None and status.error
        t = T.build_trading_day_tile(status, error=err)
        assert t.card.state == UI_FAILED and "HTTP 503" in t.card.note.why


# ══════════════════════════════════════════════════════════════════
# 整頁 render：冷啟動（未載入）、只換那一格、其他卡逐字不變、revert-pair
# ══════════════════════════════════════════════════════════════════
def _drive(monkeypatch, *, status=_OPEN, err="", unwire=False, session=None):
    drawn: list = []
    calls: list = []
    fake = mock.MagicMock(name="st")
    fake.session_state = dict(session or {})
    fake.tabs.side_effect = lambda labels: [mock.MagicMock() for _ in labels]
    monkeypatch.setattr(T, "st", fake)
    for name, val in [
            ("_inject_v2_css", lambda: None), ("_render_update_form", lambda _s: None),
            ("section_header", lambda *a, **k: None), ("render_note", lambda *a, **k: None),
            ("load_macro_readout", lambda _s: T.MacroReadout(requested=False)),
            ("_load_l4_labels", lambda: (None, None, None, "")),
            ("_load_allocation", lambda: (None, "")), ("_load_regime", lambda: (None, "")),
            ("_load_danger", lambda _r: (None, "", "")),
            ("_load_key_alerts", lambda _s: (None, False, "")),
            ("_load_lamp_directions", lambda _s=None: {}),
            ("load_sheet_binding", lambda: (None, "")),
            ("_render_tiles", lambda tiles, cols=None: drawn.extend(tiles))]:
        monkeypatch.setattr(T, name, val)

    def _load():
        calls.append(1)
        return status, err
    monkeypatch.setattr(T, "load_trading_day_status", _load)
    if unwire:
        monkeypatch.setattr(T, "status_bar_tiles_with_trading_day", lambda tiles, _t: tuple(tiles))
    T.render_page_today()
    return drawn, calls


def _assert_trading_wired(drawn) -> None:
    cells = [t for t in drawn if t.card.key == _KEY]
    assert len(cells) == 1, "狀態列的交易日格應恰畫一次"
    assert cells[0].card.state != UI_UNWIRED, "狀態列仍畫著未接線那一格"
    # ⚠️ 未接線那張舊卡沒有「已知限制」列 —— 真的走到 v2 卡面會因 hover 登記而炸成補救紅卡
    #    （§1 Fail Loud，見 `V2_HOVER_ONLY_FACTS`）；這裡先以狀態判，再畫 HTML。
    html = T.v2_card_html(cells[0])
    assert "09/04 週五 ✅ 交易日" in html, "狀態列的交易日格沒有接上 L3"


class TestPageRender:

    def test_cold_start_session_reads_l3_once_no_idle_state(self, monkeypatch):
        """未載入（空 session）：本格**每一輪都讀**，冷啟動就直接有結論 —— ⛔ 不出現「尚未載入」灰態。"""
        drawn, calls = _drive(monkeypatch, session={})
        assert calls == [1], "每一輪恰讀一次 L3"
        cell = next(t for t in drawn if t.card.key == _KEY)
        assert cell.card.state not in (UI_IDLE, UI_UNWIRED)
        _assert_trading_wired(drawn)

    @pytest.mark.parametrize("status,err,state", [
        (_OPEN, "", UI_LIVE), (_CLOSED, "", UI_LIVE), (_UNDETERMINED, "", UI_FAILED),
        (None, "RuntimeError('boom')", UI_FAILED)], ids=["open", "closed", "undetermined", "raised"])
    def test_page_draws_each_state(self, monkeypatch, status, err, state):
        drawn, _ = _drive(monkeypatch, status=status, err=err)
        cell = next(t for t in drawn if t.card.key == _KEY)
        assert cell.card.state == state
        T.v2_card_html(cell)

    def test_only_the_trading_cell_changes_others_byte_identical(self, monkeypatch):
        wired, _ = _drive(monkeypatch)
        with monkeypatch.context() as m2:
            unwired, _ = _drive(m2, unwire=True)
        assert [t.card.key for t in wired] == [t.card.key for t in unwired]
        for a, b in zip(wired, unwired):
            if a.card.key == _KEY:
                assert b.card.state == UI_UNWIRED and a.card.state == UI_LIVE
            else:
                assert T.v2_card_html(a) == T.v2_card_html(b), a.card.key

    def test_unwiring_turns_the_guard_red(self, monkeypatch):
        drawn, _ = _drive(monkeypatch, unwire=True)
        with pytest.raises(AssertionError):
            _assert_trading_wired(drawn)

    def test_status_bar_order_unchanged(self, monkeypatch):
        drawn, _ = _drive(monkeypatch)
        assert [t.card.key for t in drawn[:3]] == [
            "statusbar.trading_day", "statusbar.macro", "statusbar.sheet"]


class TestReplaceAndBoundaries:

    def test_only_the_trading_tile_is_replaced(self):
        tiles = T._tiles_of_cards(TT.build_status_bar_cards(None))
        new = T.build_trading_day_tile(_OPEN)
        out = T.status_bar_tiles_with_trading_day(tiles, new)
        assert [t.card.key for t in out] == [t.card.key for t in tiles]
        for before, after in zip(tiles, out):
            assert (after is new) if before.card.key == _KEY else (after is before)

    def test_missing_or_duplicate_slot_fails_loud(self):
        tiles = T._tiles_of_cards(TT.build_status_bar_cards(None))
        new = T.build_trading_day_tile(_OPEN)
        with pytest.raises(KeyError):
            T.status_bar_tiles_with_trading_day([t for t in tiles if t.card.key != _KEY], new)
        with pytest.raises(KeyError):
            T.status_bar_tiles_with_trading_day(list(tiles) + [tiles[0]], new)

    def test_tab_today_skeleton_untouched(self):
        """`tab_today.py` 一個字都沒動：它的骨架（無 production caller）仍標未接線。"""
        cards = {c.key: c for c in TT.build_status_bar_cards(None)}
        assert cards[_KEY].state == UI_UNWIRED
        assert cards[_KEY].note.now == "今天是不是交易日，尚未接線"

    def test_v2_registrations(self):
        assert T.V2_CARD_BLOCKS[_KEY] == "today.statusbar"
        assert T._v2_exit_phrase(T.TRADING_DAY_FAILED_WHERE) == "以證交所公告為準"
        assert T.V2_HOVER_ONLY_FACTS[_KEY] == frozenset({T.TRADING_DAY_LIMIT_FACT_KEY})

    def test_wireframe_format_is_the_source(self):
        wf = (_ROOT / "docs" / "wireframes" / "stock_ia_v1.html").read_text(encoding="utf-8")
        assert "09/05 週五 ✅ 交易日" in wf
        assert T.TRADING_DAY_OPEN_TEXT in wf

    def test_page_today_has_no_module_level_service_import(self):
        """檔頭：module-level import 失敗 ＝ 整頁空白 ⇒ L3 一律 late import。"""
        src = (_ROOT / "src" / "ui" / "views" / "page_today.py").read_text(encoding="utf-8")
        assert not re.search(r"^from src\.services\.trading_calendar_service", src, re.M)


# ══════════════════════════════════════════════════════════════════
# 批 Z59 QA 1：狀態列每輪都讀 ⇒ L1 走精簡路徑，最壞阻塞時間有上限（黑洞伺服器實測）
# ══════════════════════════════════════════════════════════════════
class _Holes:
    """本機假上游（只綁 127.0.0.1，⛔ 不碰外網）。

    · `blackhole()`：接受連線、永遠不回一個 byte ⇒ 對方吃滿**讀取**逾時（TLS 握手亦同）。
    · `syndrop()`：listen backlog 0 且先塞滿 ⇒ 新 SYN 被丟 ⇒ 對方吃滿**連線**逾時。
      用在 proxy 那一段：連不上 proxy 會被 requests 報成 `ProxyError` ⇒ `fetch_url`
      才會再走「降級直連」—— 三段（proxy／直連／NAS 中繼）全部各吃滿一次逾時＝最壞情境。
    """

    def __init__(self):
        self._socks: list = []
        self.accepted: dict[int, int] = {}

    def blackhole(self) -> int:
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        s.listen(64)
        port = s.getsockname()[1]
        self._socks.append(s)
        self.accepted[port] = 0

        def _loop():
            while True:
                try:
                    c, _ = s.accept()
                except OSError:
                    return
                self._socks.append(c)
                self.accepted[port] += 1
        threading.Thread(target=_loop, daemon=True).start()
        return port

    def syndrop(self) -> int:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(0)
        port = s.getsockname()[1]
        self._socks.append(s)
        for _ in range(4):
            c = socket.socket()
            c.setblocking(False)
            with contextlib.suppress(BlockingIOError):
                c.connect(("127.0.0.1", port))
            self._socks.append(c)
        time.sleep(0.2)
        return port

    def close(self):
        for s in self._socks:
            with contextlib.suppress(OSError):
                s.close()


@pytest.fixture
def holes(monkeypatch):
    h = _Holes()
    px, dc, rl = h.syndrop(), h.blackhole(), h.blackhole()
    monkeypatch.setattr(PH, "get_proxy_config",
                        lambda: {"http": f"http://127.0.0.1:{px}", "https": f"http://127.0.0.1:{px}"})
    monkeypatch.setattr(PH, "get_nas_relay", lambda: (f"http://127.0.0.1:{rl}", "k"))
    monkeypatch.setattr(HF, "TWSE_HOLIDAY_URL", f"https://127.0.0.1:{dc}/v1/holidaySchedule/holidaySchedule")
    h.ports = (px, dc, rl)
    yield h
    h.close()


def _timed_fetch() -> float:
    t0 = time.monotonic()
    with pytest.raises(HF.HolidayCalendarUnavailable):
        HF._fetch_json()
    return time.monotonic() - t0


class TestBlockingBound:
    """最壞阻塞 ≈ 3 × `HOLIDAY_FETCH_TIMEOUT_SEC`（proxy／直連／NAS 中繼各一次逾時，單次嘗試）。

    **量測（2026-10-14，沙箱，本機黑洞：proxy 丟 SYN、直連與中繼接了不回）**：
      · 修前（timeout=20、attempts=2）：proxy 接了不回 **101.9 秒**；proxy 丟 SYN **267.7 秒**；
      · 修後（timeout=6、attempts=1；proxy 丟 SYN ⇒ 三段全走）：**18.05 秒**（理論上限 18 秒 ＋ 開銷）。
    fast lane 這一條把逾時壓到 1 秒驗**結構**（三段、各一次、無重試、無層間 sleep）；
    真實常數（6 秒）那一條在 slow lane。
    """

    def test_lean_constants(self):
        assert HF.HOLIDAY_FETCH_ATTEMPTS == 1
        assert 5 <= HF.HOLIDAY_FETCH_TIMEOUT_SEC <= 8

    def test_fetch_json_uses_the_lean_constants(self, monkeypatch):
        seen = {}

        def _spy(url, headers=None, params=None, timeout=None, attempts=None):
            seen.update(timeout=timeout, attempts=attempts)
            return None
        monkeypatch.setattr(PH, "fetch_url", _spy)
        with pytest.raises(HF.HolidayCalendarUnavailable):
            HF._fetch_json()
        assert seen == {"timeout": HF.HOLIDAY_FETCH_TIMEOUT_SEC,
                        "attempts": HF.HOLIDAY_FETCH_ATTEMPTS}

    def test_worst_case_is_three_timeouts_structure(self, holes, monkeypatch):
        monkeypatch.setattr(HF, "HOLIDAY_FETCH_TIMEOUT_SEC", 1)
        elapsed = _timed_fetch()
        _px, dc, rl = holes.ports
        # 主斷言是**結構**：三段都真的走到了，直連、中繼各恰被連一次（＝無重試、無多跑一輪）。
        assert holes.accepted[dc] == 1 and holes.accepted[rl] == 1, holes.accepted
        # 計時只當輔助（CI 忙碌時會慢）：下界證明三段確實各等滿一次逾時；上界放寬到
        # 3×逾時 ＋ 10 秒，只擋「多了一整輪重試」那種量級的回歸（修前情境是數十倍）。
        assert 2.7 <= elapsed <= 3 * 1 + 10.0, elapsed

    @pytest.mark.slow
    def test_worst_case_bound_with_real_timeout(self, holes):
        elapsed = _timed_fetch()
        assert elapsed <= 3 * HF.HOLIDAY_FETCH_TIMEOUT_SEC + 2.0, elapsed
