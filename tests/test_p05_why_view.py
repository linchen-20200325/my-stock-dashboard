"""tests/test_p05_why_view.py — FE-14 的頁 5 守衛（IA v2「📖 憑什麼」）。

守的是 `src/ui/views/page_why.py`。風格與粒度沿用
`tests/test_p04_hold_view.py`：**一條測試對應一個具體的說謊方式**，
不是補覆蓋率。對應表：

  · `TestLayerBoundary`          ← 分層：本頁只准碰**兩支** L3，其餘一律 L0。
    以 AST **白名單**釘住可以 import 哪些下游符號，再釘住「一支 L1 都沒有」、
    「一個 `src/ui/pages/` 的診斷面板都沒 import」（那幾支自己直呼 L1，
    拉進來等於把違憲一起繼承）。
  · `TestNoFakeGreenLight`       ← **本頁最重要的一類。** 這一頁的職責就是誠實
    報告哪些源是壞的，所以「把壞的畫成綠的」與「把壞的整個不畫」都是致命傷。
    兩種都各有守衛：未知狀態一律紅、非 Mapping 的列照樣畫成紅、
    `live` 只可能來自 `last_status == 'ok'`。
  · `TestUnmeasuredSourcesAreVisible` ← 第二種假綠燈（**更隱形**）：
    FRED / FinMind / TWSE 沒被量到，若不畫出來，畫面會是滿版綠。
  · `TestRequestedIsNotDerivedFromData` ← gate 從資料反推（頁 1 的恆真式事故）。
    做法與頁 2／3／4 相同：**白名單 AST 斷言**，不是一條越加越長的黑名單。
  · `TestLeafOneHasNoGate`       ← 葉1 教學**沒有 gate**：全檔**字面 `requested=`
    只有一處**，而且就在 L0-only 卡的共同入口裡。
  · `TestCallRecordIsTheGateNotTheRows` ← 來源燈的 gate 是 L0 的**呼叫紀錄**
    （`last_status`），不是它**抓回來的資料**（`last_rows`）。
  · `TestNothingIsCalledBeforeYouAsk` ← 「沒問就不呼叫 L3」只是 docstring 宣稱。
    把兩支下游 L3 下毒（毒藥**不繼承 `Exception`**，本頁的 try/except 吞不掉），
    再跑一次 loader —— 碰到就當場紅。
  · `TestThreeStatesNeverMix`    ← 「還沒打開進階診斷」／「打開了但某個源這輪
    沒回」／「診斷本身掛了」被畫成同一種。
  · `TestEngineerGateHasNoForm`  ← 線框葉2 明文「1 個 checkbox 全有全無 · **不加
    form**」＋ DECISIONS #7 撤回 `form_diag`。全檔 0 個 `st.form`、
    0 顆 `st.button`、**剛好 1 個** `st.checkbox`。
  · `TestThreeColumnGrid`        ← 鐵律 1：線框「原 `columns(7)` 降階」。
  · `TestUnwiredStaysUnwired`    ← 未接線卡被「按一次就變好」、三要素留空、
    或全部共用同一句「去哪補」（那會讓「補哪一層才會好」這個資訊消失）。
  · `TestSpecFlagsComeFromL0`    ← 線框葉2 note：`unwired_reason` /
    `degraded_reason` **直接讀自 SSOT**；旗標翻面，卡就跟著翻面。
  · `TestStatusLiteralsMatchL0`  ← 本檔重抄了 L0 的三個狀態字面值（已在檔內揭露
    為第二真相源）。這一條直接掃 L0 原始碼，**字面一漂移就 CI 紅燈**。
  · `TestQaLeaf`                 ← 沒金鑰→紅、上游回錯→紅、回空字串→灰（有效結果）、
    沒問→灰。四種**不可混**。
  · `TestNoSessionSubscriptWrite` ← 本頁的 gate 全是 widget 當下值，
    **沒有任何一個 gate 是 session key** → 結構上沒人能偽造「使用者問過了」。
  · `TestSignalChannelIsClean`   ← 鐵律 3：訊號頻道只出中文標籤。
  · `test_page_mounts_clean`（slow）← 這一頁真的畫得出來，不是半截死頁。

⚠️ **這些是護欄，不是證明**（同 `tests/test_p0{1,2,3,4}_*_view.py` 的自陳）：
釘住的是「已知的那幾種說謊方式不會再回來」，**不是**「這一頁不會再說謊」。
全綠不等於合規。特別是 `TestNoFakeGreenLight`：它證明的是**本檔的判態函式**
在幾種已知輸入下不會畫出綠燈，**不是**「這面牆看得到全站所有來源」——
後者本來就不成立，而且是本頁自己在 `COVERAGE_DISCLOSURE` 裡明說的。
"""
from __future__ import annotations

import ast
import pathlib
import sys

import pytest

from shared.station_specs import KEY_STOCK_TREND, SPECS_BY_KEY
from shared.ui_state import (
    UI_DEGRADED,
    UI_EMPTY,
    UI_FAILED,
    UI_IDLE,
    UI_LIVE,
    UI_UNWIRED,
)
from src.ui.tabs.tab_today import Note
from src.ui.views import page_why as P
from src.ui.views._ui_kit import banned_signal_glyphs

_VIEW = pathlib.Path(P.__file__)
_L0_MONITOR = pathlib.Path(
    sys.modules["shared.fetch_monitor"].__file__
    if "shared.fetch_monitor" in sys.modules
    else __import__("shared.fetch_monitor", fromlist=["x"]).__file__)


def _tree() -> ast.Module:
    return ast.parse(_VIEW.read_text(encoding="utf-8"))


def _src() -> str:
    return _VIEW.read_text(encoding="utf-8")


def _code_only() -> str:
    """把 docstring 與 `#` 註解拿掉之後的**程式碼**。

    ⚠️ 為什麼需要這支：本檔有好幾條是「某某東西不准出現在這一頁」，
    而本頁的 docstring 大量在**討論**那些東西（「零 `@st.cache_data`」、
    「規格表寫 1.5% 但實作用 2%」…）。拿整份檔案做子字串比對，
    會把**寫下禁令這件事本身**判成違規 —— 那條測試就變成「不准提到它」，
    而不是「不准用它」。兩者差很多。
    """
    _t = _tree()
    _skip: set[int] = set()
    for _n in ast.walk(_t):
        if isinstance(_n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                           ast.AsyncFunctionDef)):
            _body = getattr(_n, "body", None) or []
            if (_body and isinstance(_body[0], ast.Expr)
                    and isinstance(_body[0].value, ast.Constant)
                    and isinstance(_body[0].value.value, str)):
                _doc = _body[0]
                _skip.update(range(_doc.lineno, (_doc.end_lineno or _doc.lineno) + 1))
    _out: list[str] = []
    for _i, _line in enumerate(_src().splitlines(), start=1):
        if _i in _skip:
            continue
        _out.append(_line.split("#", 1)[0])
    return "\n".join(_out)


def _session_state_reads(tree: ast.Module) -> list[int]:
    """`st.session_state` 在**程式碼裡**被碰到的行號（docstring 不算）。"""
    return [_n.lineno for _n in ast.walk(tree)
            if isinstance(_n, ast.Attribute) and _n.attr == "session_state"
            and isinstance(_n.value, ast.Name) and _n.value.id == "st"]


def _note_triple(note: Note | None) -> tuple[str, str, str]:
    assert note is not None, "非 live 的卡一定要有 Note（鐵律 4）"
    return (note.now, note.why, note.where)


def _entry(status: str, **kw) -> dict:
    _e = {"category": "🇹🇼 台灣總經", "frequency": "monthly",
          "registry_key": None, "last_status": status, "last_error": None,
          "last_rows": None, "last_ms": None, "last_called_at": None}
    _e.update(kw)
    return _e


# ══════════════════════════════════════════════════════════════════
# 【1】分層 —— 本頁只准碰兩支 L3，其餘一律 L0
# ══════════════════════════════════════════════════════════════════
#: 本頁**唯一**可以取用的下游符號。白名單，不是黑名單：
#: 任何沒被列在這裡的 `from src.services...import X` 就是紅燈。
_ALLOWED_L3: frozenset[tuple[str, str]] = frozenset({
    ("src.services.app_ai_service", "get_gemini_api_key"),
    ("src.services.ai_qa_service", "run_agent"),
})

#: 既有診斷面板。**一支都不准 import** —— 它們自己直接讀別頁的 session
#: 或直呼 L1／`scripts/`，拉進來等於把違憲一起繼承（本頁 docstring 已宣告）。
_FORBIDDEN_PANEL_MODULES: tuple[str, ...] = (
    "src.ui.pages",
    "src.ui.etf",
)


def _module_imports(tree: ast.Module) -> list[tuple[str, str, int]]:
    _out: list[tuple[str, str, int]] = []
    for _n in ast.walk(tree):
        if isinstance(_n, ast.ImportFrom):
            for _a in _n.names:
                _out.append((_n.module or "", _a.name, _n.lineno))
        elif isinstance(_n, ast.Import):
            for _a in _n.names:
                _out.append((_a.name, "", _n.lineno))
    return _out


def _identifiers(tree: ast.Module) -> set[str]:
    _out: set[str] = set()
    for _n in ast.walk(tree):
        if isinstance(_n, ast.Name):
            _out.add(_n.id)
        elif isinstance(_n, ast.Attribute):
            _out.add(_n.attr)
        elif isinstance(_n, ast.alias):
            _out.add((_n.asname or _n.name).split(".")[-1])
    return _out


class TestLayerBoundary:
    """L5 頁面的分層邊界。

    ⚠️ **這一類證明的是什麼、不證明什麼**：它證明**本檔的靜態文字裡**沒有
    L1 import、沒有自建快取、沒有直接對外連線；它**不**證明「執行時絕不會
    連到外面」—— 後者取決於它呼叫的那兩支 L3 自己的行為，不在本測試射程內。
    """

    def test_only_whitelisted_l3_symbols_are_imported(self):
        _bad = [(_m, _n, _l) for _m, _n, _l in _module_imports(_tree())
                if _m.startswith("src.services") and (_m, _n) not in _ALLOWED_L3]
        assert not _bad, (
            f"本頁 import 了白名單外的 L3 符號：{_bad}；"
            f"白名單：{sorted(_ALLOWED_L3)}")

    def test_the_whitelist_is_not_empty_and_is_actually_used(self):
        """反證：白名單本身要真的被用到，否則上一條會因為「一支都沒 import」而假綠。"""
        _used = {(_m, _n) for _m, _n, _l in _module_imports(_tree())
                 if _m.startswith("src.services")}
        assert _used == _ALLOWED_L3, (
            f"白名單與實際 import 不一致：實際 {sorted(_used)}")

    def test_no_l1_data_or_l2_compute_import(self):
        _bad = [(_m, _n, _l) for _m, _n, _l in _module_imports(_tree())
                if _m.startswith(("src.data", "src.compute", "scripts"))]
        assert not _bad, f"本頁 import 了 L1／L2／scripts：{_bad}"

    def test_no_import_from_app(self):
        _bad = [(_m, _n, _l) for _m, _n, _l in _module_imports(_tree())
                if _m == "app" or _m.startswith("app.")]
        assert not _bad, f"L5 不得上行 import L6：{_bad}"

    def test_no_existing_diagnostic_panel_is_imported(self):
        """既有六個診斷面板一支都不准拉進來（本頁 docstring 的宣告要有守衛）。"""
        _bad = [(_m, _n, _l) for _m, _n, _l in _module_imports(_tree())
                if _m.startswith(_FORBIDDEN_PANEL_MODULES)]
        assert not _bad, (
            f"本頁 import 了既有 UI 面板：{_bad} —— "
            "它們自己直接讀別頁 session 或直呼 L1，拉進來等於繼承違憲")

    def test_no_cross_module_private_symbol(self):
        _bad = [(_m, _n, _l) for _m, _n, _l in _module_imports(_tree())
                if _n.startswith("_")]
        assert not _bad, f"跨檔取用底線開頭的私有符號：{_bad}"

    def test_no_cache_decorator_and_no_inline_ttl(self):
        """⚠️ 用 AST，不是子字串 —— 本頁的 docstring 明文在**討論**這條禁令，

        整份檔案做子字串比對會把「寫下禁令」本身判成違規。
        """
        _t = _tree()
        _decorated = [
            f"{_fn.name}:{_d.lineno}"
            for _fn in ast.walk(_t)
            if isinstance(_fn, (ast.FunctionDef, ast.AsyncFunctionDef))
            for _d in _fn.decorator_list
            for _attr in ast.walk(_d)
            if isinstance(_attr, ast.Attribute)
            and _attr.attr in ("cache_data", "cache_resource")]
        assert not _decorated, (
            f"L5 自建快取層：{_decorated}（§8.2.A.2 V-SMART-CACHE-1 的前車之鑑）")
        _ttls = [_c.lineno for _c in ast.walk(_t) if isinstance(_c, ast.Call)
                 for _k in _c.keywords if _k.arg == "ttl"]
        assert not _ttls, (
            f"第 {_ttls} 行有 inline `ttl=`，未走 `shared/ttls.py` SSOT（§3.3）")
        assert "cache_data" not in _code_only(), "程式碼裡出現了 cache_data"

    def test_no_io_library_is_touched(self):
        _ids = _identifiers(_tree())
        for _bad in ("requests", "yfinance", "FinMind", "read_csv",
                     "read_parquet", "to_parquet", "sqlite3", "urlopen"):
            assert _bad not in _ids, f"L5 直接做 I/O：{_bad}"

    def test_the_l0_reads_are_declared(self):
        """本頁走 L0 是刻意的（不是忘了寫 L3）—— 檔頭必須把理由講出來。"""
        _s = _src()
        assert "為什麼葉1／葉2 走 L0 而不是 L3" in _s
        assert "「一律走 L3」規範的是「取數」" in _s


# ══════════════════════════════════════════════════════════════════
# 【2】不准有假綠燈（本頁的職責就是誠實報告壞掉的源）
# ══════════════════════════════════════════════════════════════════
class TestNoFakeGreenLight:
    """兩種假綠燈，兩種都要擋：**畫成綠的**、以及**整個不畫**。"""

    def test_only_ok_can_become_live(self):
        """`live` 只可能來自 `last_status == 'ok'`。其餘一律不是綠。"""
        for _status in (P.STATUS_NEVER_RUN, P.STATUS_FAILED,
                        "", "OK", "Ok", "success", "已完成", "未知"):
            _card, _facts, _sig = P.build_source_card(
                P.probe_from_entry("f", _entry(_status)))
            assert _card.state != UI_LIVE, (
                f"狀態 {_status!r} 被畫成綠燈了 —— "
                "本頁只認得 'ok'，其餘一律不當正常")

    def test_ok_really_can_become_live(self):
        """反證：真的 `ok` 要能變綠，否則上一條會因為「永遠不綠」而假綠。"""
        _card, _facts, _sig = P.build_source_card(
            P.probe_from_entry("f", _entry(P.STATUS_OK,
                                           last_called_at="2026-09-05 14:30")))
        assert _card.state == UI_LIVE and _card.value == "2026-09-05 14:30"

    def test_unknown_status_is_red_not_grey(self):
        """L0 多一個狀態或改字 → **紅**，不是靜默的灰（灰看起來像沒問題）。"""
        _probe = P.probe_from_entry("f", _entry("brand_new_state"))
        assert _probe.unknown_status == "brand_new_state"
        _card, _facts, _sig = P.build_source_card(_probe)
        assert _card.state == UI_FAILED
        _now, _why, _where = _note_triple(_card.note)
        assert "brand_new_state" in _now, "畫面上要看得到那個看不懂的字面值"
        assert "不會" in _where and "正常" in _where

    def test_a_failed_source_is_never_dropped_from_the_wall(self, monkeypatch):
        """**第二種假綠燈**：壞掉的那一列被跳過 → 牆上全綠、沒人發現。"""
        monkeypatch.setattr(P, "get_monitor_registry", lambda: {
            "good": _entry(P.STATUS_OK, last_called_at="2026-09-05 09:00"),
            "broken": _entry(P.STATUS_FAILED, last_error="HTTPError: 429"),
            "never": _entry(P.STATUS_NEVER_RUN),
        })
        _scan = P.load_sources()
        assert _scan.count == 3, "有一列不見了"
        _states = {_p.name: P.build_source_card(_p)[0].state
                   for _p in _scan.probes}
        assert _states == {"good": UI_LIVE, "broken": UI_FAILED,
                           "never": UI_IDLE}

    def test_a_malformed_row_is_drawn_red_not_skipped(self, monkeypatch):
        """形狀怪的一列**照畫成紅**。跳過就是本頁最隱形的那種假綠燈。"""
        monkeypatch.setattr(P, "get_monitor_registry", lambda: {
            "good": _entry(P.STATUS_OK),
            "weird": ["not", "a", "mapping"],
        })
        _scan = P.load_sources()
        assert _scan.count == 2, "形狀怪的那一列被跳過了"
        _weird = [_p for _p in _scan.probes if _p.name == "weird"][0]
        assert P.build_source_card(_weird)[0].state == UI_FAILED

    def test_the_error_message_reaches_the_screen(self):
        """上游的錯誤原文要看得到，不是只寫「失敗」。"""
        _card, _facts, _sig = P.build_source_card(
            P.probe_from_entry("f", _entry(P.STATUS_FAILED,
                                           last_error="HTTPError: 429 quota")))
        assert "429 quota" in _note_triple(_card.note)[1]

    def test_a_failed_source_with_no_message_still_says_something(self):
        """L0 記了 failed 卻沒給訊息 → 仍然是紅，而且畫面上不是空白。"""
        _card, _facts, _sig = P.build_source_card(
            P.probe_from_entry("f", _entry(P.STATUS_FAILED)))
        assert _card.state == UI_FAILED
        assert P.UNKNOWN_ERROR_TEXT in _note_triple(_card.note)[1]

    def test_an_empty_registry_is_grey_and_explained_not_blank(self, monkeypatch):
        """「讀到了、裡面沒有東西」是**有效結果**，要說得出來，不是一片空白。"""
        monkeypatch.setattr(P, "get_monitor_registry", dict)
        _scan = P.load_sources()
        assert _scan.readable and _scan.count == 0
        _card, _facts, _sig = P.build_empty_registry_card()
        assert _card.state in (UI_EMPTY, UI_IDLE)
        _now, _why, _where = _note_triple(_card.note)
        assert all((_now.strip(), _why.strip(), _where.strip()))
        assert "為什麼不顯示一片空白" in dict(_facts)

    def test_reading_the_registry_itself_failing_is_red(self, monkeypatch):
        def _boom():
            raise RuntimeError("registry exploded")

        monkeypatch.setattr(P, "get_monitor_registry", _boom)
        _scan = P.load_sources()
        assert not _scan.readable and "registry exploded" in _scan.error
        _card, _facts, _sig = P.build_engineer_card(
            P.EngineerRequest(opened=True), _scan)
        assert _card.state == UI_FAILED
        assert "registry exploded" in _note_triple(_card.note)[1]


# ══════════════════════════════════════════════════════════════════
# 【3】量不到的來源必須看得見（第二種假綠燈的專屬守衛）
# ══════════════════════════════════════════════════════════════════
class TestUnmeasuredSourcesAreVisible:
    """FRED / FinMind / TWSE 沒被量到 —— **不畫，畫面就會是滿版綠**。"""

    def test_all_three_named_sources_are_drawn(self):
        _labels = " ".join(_c.label for _c, _f, _s in P.build_unmeasured_cards())
        for _name in ("FRED", "FinMind", "TWSE"):
            assert _name in _labels, f"線框具名的 {_name} 沒有被畫出來"

    def test_they_are_unwired_whatever_you_press(self):
        for _card, _facts, _sig in P.build_unmeasured_cards():
            assert _card.state == UI_UNWIRED
            assert not _card.value, "未接線卡不得帶結論文字"

    def test_each_has_its_own_where(self):
        """三顆卡住的位置不同 —— 共用一句「去哪補」會讓那個資訊消失。"""
        _wheres = [_c.note.where for _c, _f, _s in P.build_unmeasured_cards()]
        assert len(set(_wheres)) == len(_wheres), f"「去哪補」被複製貼上了：{_wheres}"

    def test_finmind_quota_says_it_is_stuck_one_step_deeper(self):
        """額度**比另外兩個更卡一層**（連 fetcher 都還沒有），文案要說得出來。"""
        _by_key = {_c.key: _c for _c, _f, _s in P.build_unmeasured_cards()}
        _quota = _by_key["why.source.unmeasured.finmind_quota"]
        assert "連 fetcher 都還沒有" in dict(
            P.build_unmeasured_cards()[1][1]).get("卡住的那一步", "")
        assert "帳號層級" in _quota.note.why

    def test_no_made_up_number_anywhere_in_the_three_cards(self):
        """⚠️ 額度那一格最容易被塞一個猜出來的百分比。"""
        for _card, _facts, _sig in P.build_unmeasured_cards():
            assert "62%" not in (_card.note.now + _card.note.why), (
                "線框示意圖上的 62% 是**示意**，不是資料 —— 不得出現在真畫面上")

    def test_the_coverage_disclosure_says_green_is_not_proof(self):
        """本頁最重要的一句話：**沒有紅燈不等於全站都好。**"""
        _d = P.COVERAGE_DISCLOSURE
        assert "不等於全站都好" in _d
        assert "FRED" in _d and "FinMind" in _d and "TWSE" in _d
        assert "data_registry" in _d, "要說得出全站清單的 SSOT 在哪一層"

    def test_the_disclosure_is_rendered_unconditionally(self):
        """它是**常駐**的 —— 不得躲在任何 if 裡。"""
        _fn = [_n for _n in ast.walk(_tree())
               if isinstance(_n, ast.FunctionDef)
               and _n.name == "_render_user_health_wall"][0]
        _guarded = {id(_c) for _if in ast.walk(_fn)
                    if isinstance(_if, ast.If)
                    for _c in ast.walk(_if) if isinstance(_c, ast.Name)}
        _hits = [_n for _n in ast.walk(_fn) if isinstance(_n, ast.Name)
                 and _n.id == "COVERAGE_DISCLOSURE"]
        assert _hits, "涵蓋率揭露沒有被畫出來"
        assert all(id(_h) not in _guarded for _h in _hits), (
            "涵蓋率揭露被包進 if 裡了 —— 它必須常駐")


# ══════════════════════════════════════════════════════════════════
# 【4】`requested=` 不得從資料反推（白名單 AST，照頁 2／3／4 那套）
# ══════════════════════════════════════════════════════════════════
#: ⚠️ 這是**白名單**，不是黑名單：任何沒被宣告成 gate 的東西出現在那裡就是紅燈，
#: 不必先想得到它的名字（頁 1 的恆真式 `(alloc is not None)` 就是想不到的那種）。
_GATE_ATTRS: frozenset[str] = frozenset({
    "requested", "called", "opened", "asked",
    # 容器名（讀的是它們的欄位，不是它們本身）
    "probe", "req", "qa", "spec", "scan", "self",
})

#: 明確的結果資料名 —— 一個都不准出現在 `requested=` 裡（黑名單，第二道）。
_PAYLOAD_TOKENS: frozenset[str] = frozenset({
    "ok", "readable", "answered", "scanned", "count", "probes", "rows",
    "last_rows", "last_status", "text", "error", "value", "has_value",
    "has_rows", "history", "question", "len", "any", "all", "empty",
    "wired", "discriminative",
})


def _leaf_names(node: ast.AST) -> set[str]:
    """運算式**實際讀出來的識別字**（容器名不算，讀的欄位才算）。"""
    _bases = {id(_n.value) for _n in ast.walk(node)
              if isinstance(_n, ast.Attribute)}
    _out: set[str] = set()
    for _n in ast.walk(node):
        if isinstance(_n, ast.Attribute):
            _out.add(_n.attr)
        elif isinstance(_n, ast.Name) and id(_n) not in _bases:
            _out.add(_n.id)
    return _out


def _classify_calls(tree: ast.Module):
    for _n in ast.walk(tree):
        if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
                and _n.func.id == "classify_ui_state"):
            yield _n


def _requested_offences(tree: ast.Module) -> list[str]:
    """本檔用的**單一**判定入口（測試與自證共用，不是兩把尺）。"""
    _bad: list[str] = []
    for _call in _classify_calls(tree):
        _kw = {_k.arg: _k.value for _k in _call.keywords if _k.arg}
        if "requested" not in _kw:
            _bad.append(f"line {_call.lineno}: 沒有傳 requested=")
            continue
        _req_expr = _kw["requested"]
        if isinstance(_req_expr, ast.Constant):
            continue          # 字面常數另由 `TestLeafOneHasNoGate` 管
        _names = _leaf_names(_req_expr)
        _illegal = {_x for _x in _names
                    if _x not in _GATE_ATTRS and not _x.endswith("requested")
                    and _x != "bool"}
        if _illegal:
            _bad.append(f"line {_call.lineno}: requested= 讀了非 gate 的東西 "
                        f"{sorted(_illegal)}")
        _payload = _names & _PAYLOAD_TOKENS
        if _payload:
            _bad.append(f"line {_call.lineno}: requested= 含結果資料名 "
                        f"{sorted(_payload)}")
        if "has_value" in _kw and ast.dump(_req_expr) == ast.dump(_kw["has_value"]):
            _bad.append(f"line {_call.lineno}: requested= 與 has_value= 是同一個運算式")
        if "has_value" in _kw:
            _overlap = (_names & _leaf_names(_kw["has_value"])) - {"bool"}
            if _overlap:
                _bad.append(f"line {_call.lineno}: requested= 與 has_value= "
                            f"讀同一個欄位 {sorted(_overlap)}")
    return _bad


class TestRequestedIsNotDerivedFromData:
    """L0 的鐵律：**`idle` 只能由上游帶下來，禁止由 `if not data:` 推導。**"""

    def test_there_are_calls_to_guard(self):
        _calls = list(_classify_calls(_tree()))
        assert len(_calls) >= 4, (
            "頁 5 至少有 4 個判態點（L0-only 卡 / 來源燈 / 進階診斷 / AI 問答），"
            f"實際找到 {len(_calls)}")

    def test_every_call_passes_requested(self):
        for _call in _classify_calls(_tree()):
            assert any(_k.arg == "requested" for _k in _call.keywords), (
                f"{_VIEW.name}:{_call.lineno} 沒有傳 `requested=`")

    def test_no_call_derives_requested_from_result_data(self):
        _bad = _requested_offences(_tree())
        assert not _bad, (
            "`requested=` 從資料反推了（idle 只能由上游帶下來）：\n  "
            + "\n  ".join(_bad))

    def test_a_result_with_data_but_no_gate_cannot_even_be_built(self):
        """**恆真式的直接反證**：這種卡在 L0 就**構造不出來**（§1 Fail Loud）。"""
        with pytest.raises(ValueError, match="requested=False"):
            P.build_source_card(P.SourceProbe(name="x", called=False, ok=True))
        with pytest.raises(ValueError, match="requested=False"):
            P.build_qa_card(P.QaReadout(asked=False, answered=True))

    def test_the_engineer_card_drops_a_result_it_should_not_have(self, capsys):
        """進階診斷那張卡走的是**第二道 belt**（丟棄 ＋ log），不是 raise。

        ⚠️ 兩者的差別要講清楚，免得被讀成漏了一條：
        `SourceProbe` / `QaReadout` 的矛盾是**上游把兩件事湊在一起**，
        L0 raise 是對的；而 `build_engineer_card` 收到的 scan 是
        **呼叫端已經 gate 過的東西**，這裡再收到就是有人繞過 gate ——
        對使用者而言正確的畫面仍是 idle（他確實沒勾），所以丟棄 ＋ log，
        **不是**把整頁炸掉。丟棄有沒有留下線索，就是這一條在守的。
        """
        _card, _facts, _sig = P.build_engineer_card(
            P.EngineerRequest(opened=False),
            P.SourceScan(scanned=True, error="boom"))
        assert _card.state == UI_IDLE
        assert "已丟棄" in capsys.readouterr().out, (
            "繞過 gate 的結果被靜默丟棄了 —— §1：不吞、不假裝沒發生")

    def test_the_page_never_produces_that_contradiction_itself(self):
        """本頁自己的 loader 走不到上面那個矛盾：沒叫 → 什麼都不帶回來。"""
        _qa = P.load_qa(P.QaRequest(asked=False))
        assert _qa.answered is False and _qa.error == "" and _qa.text == ""

    def test_the_closed_gate_really_drops_this_rounds_result(self):
        """沒勾 checkbox 時，即使把一個「有結果」的 scan 傳進去也不得被採用。"""
        _scan = P.SourceScan(scanned=True,
                             probes=(P.SourceProbe(name="a", called=True,
                                                   ok=True),))
        _card, _facts, _sig = P.build_engineer_card(
            P.EngineerRequest(opened=False), _scan)
        assert _card.state == UI_IDLE, (
            "沒勾卻採用了本輪結果 —— 那正是 L0 在防的「把殘留當事實」")


# ══════════════════════════════════════════════════════════════════
# 【5】葉1 無 gate：字面 `requested=` 只有一處
# ══════════════════════════════════════════════════════════════════
class TestLeafOneHasNoGate:
    """線框葉1：**靜態 · 無 gate**。它沒有取數，所以沒有「叫過 / 沒叫過」。"""

    def test_exactly_one_literal_requested(self):
        _lits = [(_c.lineno, _k.value.value)
                 for _c in _classify_calls(_tree())
                 for _k in _c.keywords
                 if _k.arg == "requested" and isinstance(_k.value, ast.Constant)]
        assert len(_lits) == 1, (
            f"字面 `requested=` 應該只有 L0-only 卡那一處，實際 {_lits}")
        assert _lits[0][1] is True, "那一處必須是字面 True（陳述『永遠開著』）"

    def test_the_literal_lives_in_the_shared_l0_builder(self):
        """它必須在 `build_l0_card()` 裡 —— 收斂到一支，才稽核得動。"""
        _fn = [_n for _n in ast.walk(_tree())
               if isinstance(_n, ast.FunctionDef) and _n.name == "build_l0_card"][0]
        _lits = [_k for _c in _classify_calls(_tree()) for _k in _c.keywords
                 if _k.arg == "requested" and isinstance(_k.value, ast.Constant)]
        assert _fn.lineno < _lits[0].value.lineno < (_fn.end_lineno or 10 ** 9)

    def test_leaf_one_cards_all_go_through_it(self):
        """葉1 四張卡全部是 L0-only —— 一張都不需要 gate。"""
        _cards = P.build_edu_cards(P.load_specs(), P.build_scale_disclosure())
        assert len(_cards) == 4
        for _card, _facts, _sig in _cards:
            assert _card.state != UI_IDLE, (
                f"葉1 的 {_card.key} 是 idle —— 它沒有 gate，不該有「還沒載入」")

    def test_leaf_one_never_calls_l3(self, poisoned):
        """毒藥全上，葉1 照樣建得出來（它一行 L3 都不碰）。"""
        _cards = P.build_edu_cards(P.load_specs(), P.build_scale_disclosure())
        assert len(_cards) == 4

    def test_leaf_one_declares_it_has_no_grey_state(self):
        """線框葉1 grey 原文：「靜態內容，永遠可讀 —— 這頁沒有灰態」。"""
        assert "靜態 · 無 gate" in _src()


# ══════════════════════════════════════════════════════════════════
# 【6】來源燈的 gate 是呼叫紀錄，不是抓回來的資料
# ══════════════════════════════════════════════════════════════════
class TestCallRecordIsTheGateNotTheRows:
    """`last_status` 是 `@monitored` **在呼叫當下寫下的紀錄**；

    `last_rows` 才是它抓回來的東西。本頁拿前者當 gate、**沒有**拿後者。
    """

    def test_called_tracks_the_status_not_the_rows(self):
        _never = P.probe_from_entry("f", _entry(P.STATUS_NEVER_RUN, last_rows=999))
        assert _never.called is False, (
            "有 rows 就被當成「叫過了」—— 那正是從資料反推")
        _ok_no_rows = P.probe_from_entry("f", _entry(P.STATUS_OK, last_rows=0))
        assert _ok_no_rows.called is True and _ok_no_rows.ok is True, (
            "回 0 列不代表沒被叫過，也不代表失敗（L0 的契約是看 status）")

    def test_called_and_ok_are_two_different_fields(self):
        _failed = P.probe_from_entry("f", _entry(P.STATUS_FAILED,
                                                 last_error="boom"))
        assert (_failed.called, _failed.ok) == (True, False), (
            "「叫過了」與「成功了」被綁成同一件事 —— "
            "那會讓失敗變成「沒叫過」（灰），真故障就消失了")

    def test_rows_never_appears_in_a_requested_expression(self):
        """AST：`requested=` 的運算式裡不得出現任何 rows 類的名字。"""
        for _call in _classify_calls(_tree()):
            _kw = {_k.arg: _k.value for _k in _call.keywords if _k.arg}
            _expr = _kw.get("requested")
            if _expr is None or isinstance(_expr, ast.Constant):
                continue
            _names = _leaf_names(_expr)
            assert not (_names & {"rows", "last_rows", "probes", "count"}), (
                f"line {_call.lineno}: requested= 讀了資料量 {sorted(_names)}")


# ══════════════════════════════════════════════════════════════════
# 【7】沒問之前一行 L3 都不呼叫（下毒實測，不是讀 docstring）
# ══════════════════════════════════════════════════════════════════
class _L3Touched(BaseException):
    """毒藥。**刻意不繼承 `Exception`** —— 本頁的 loader 是 `except Exception`，

    繼承 `Exception` 的話會被吞成一則錯誤字串，測試照樣綠、
    而 L3 其實已經被呼叫過了。不繼承才穿得出來。
    """


class _PoisonModule:
    """任何屬性取用都當場引爆的假模組。"""

    def __init__(self, name: str) -> None:
        self.__name__ = name

    def __getattr__(self, item: str):
        raise _L3Touched(f"{self.__name__}.{item} 在 requested=False 時被碰到了")


#: 頁 5 檔頭「取數接線表」列出的全部下游（兩支 L3 模組）。
_DOWNSTREAM = ("src.services.app_ai_service", "src.services.ai_qa_service")


@pytest.fixture()
def poisoned(monkeypatch):
    """把全部下游換成毒藥模組。碰到就 `_L3Touched`，穿過所有 try/except。"""
    for _m in _DOWNSTREAM:
        monkeypatch.setitem(sys.modules, _m, _PoisonModule(_m))
    return _DOWNSTREAM


class TestNothingIsCalledBeforeYouAsk:
    """檔頭宣稱「`requested=False` 時本檔一行 L3 都不呼叫」——

    在本條之前那是一句**沒有人驗過的自我宣稱**。idle 態的 Note 還把它
    寫給使用者看；宣稱與實作若不一致，那就是對使用者說謊（§1）。
    """

    def test_qa_touches_nothing_before_you_ask(self, poisoned):
        _qa = P.load_qa(P.QaRequest(asked=False))
        assert _qa.asked is False and _qa.error == ""

    def test_not_even_the_api_key_is_read_before_you_ask(self, poisoned):
        """⚠️ 連「有沒有金鑰」都不先問 —— 先問會讓沒用過 AI 的人一進頁面就見紅。"""
        assert P.load_qa(P.QaRequest(asked=False)).key_missing is False

    def test_the_poison_really_would_have_fired(self, poisoned):
        """**反證**：同一組毒藥下，`asked=True` 一定炸。"""
        with pytest.raises(_L3Touched):
            P.load_qa(P.QaRequest(asked=True, question="2330 健康度多少？"))

    def test_the_data_health_leaf_needs_no_l3_at_all(self, poisoned):
        """葉2 全部走 L0 —— 毒藥全上，它照樣算得出來。"""
        _scan = P.load_sources()
        assert _scan.readable
        _specs = P.load_specs()
        assert _specs.has_rows and _specs.error == ""

    def test_the_closed_engineer_gate_reads_nothing(self):
        """沒勾 checkbox 時，連 L0 登錄表都不讀（AST：讀取被 gate 包住）。"""
        _fn = [_n for _n in ast.walk(_tree())
               if isinstance(_n, ast.FunctionDef)
               and _n.name == "_render_engineer_block"][0]
        _calls = [_n for _n in ast.walk(_fn) if isinstance(_n, ast.Call)
                  and isinstance(_n.func, ast.Name)
                  and _n.func.id == "load_sources"]
        assert len(_calls) == 1, f"進階診斷區讀了 {len(_calls)} 次登錄表"
        _guards = [_n for _n in ast.walk(_fn) if isinstance(_n, ast.IfExp)]
        assert _guards, (
            "`load_sources()` 沒有被 gate 條件包住 —— "
            "沒勾就不該讀（線框：預設不跑）")

    def test_idle_note_promise_matches_the_code(self):
        """畫給使用者看的那句承諾，與上面實測到的行為必須是同一件事。"""
        assert "送出本身就是啟動" in P.QA_IDLE_WHERE
        assert "不自行上網查" in P.QA_IDLE_WHY


# ══════════════════════════════════════════════════════════════════
# 【8】三態不得混
# ══════════════════════════════════════════════════════════════════
class TestThreeStatesNeverMix:
    """「還沒打開」／「打開了但某個源這輪沒回」／「診斷本身掛了」。"""

    def test_not_opened_is_idle_grey(self):
        _card, _facts, _sig = P.build_engineer_card(
            P.EngineerRequest(opened=False), P.SourceScan())
        assert _card.state == UI_IDLE
        assert "**進階診斷未載入**" == _card.note.now

    def test_opened_with_a_dead_source_is_still_live_overall(self, monkeypatch):
        """⚠️ **一格壞不把整段染色。** 這一條是本類的核心。"""
        monkeypatch.setattr(P, "get_monitor_registry", lambda: {
            "broken": _entry(P.STATUS_FAILED, last_error="boom"),
        })
        _scan = P.load_sources()
        _card, _facts, _sig = P.build_engineer_card(
            P.EngineerRequest(opened=True), _scan)
        assert _card.state == UI_LIVE, (
            "某一個源掛了就把整段診斷判成壞掉 —— "
            "那讓「來源壞了」與「診斷壞了」在畫面上長得一樣")
        _one = P.build_source_card(_scan.probes[0])[0]
        assert _one.state == UI_FAILED, "那一盞自己必須是紅的"

    def test_only_the_registry_being_unreadable_is_red(self, monkeypatch):
        def _boom():
            raise RuntimeError("nope")

        monkeypatch.setattr(P, "get_monitor_registry", _boom)
        _card, _facts, _sig = P.build_engineer_card(
            P.EngineerRequest(opened=True), P.load_sources())
        assert _card.state == UI_FAILED
        assert "不是某一個資料來源壞掉" in _card.note.where

    def test_the_three_are_pairwise_distinguishable_on_screen(self):
        """三種狀態的畫面文字兩兩不同 —— 否則使用者無從分辨。"""
        _idle = P.build_engineer_card(P.EngineerRequest(opened=False),
                                      P.SourceScan())[0]
        _live = P.build_engineer_card(
            P.EngineerRequest(opened=True),
            P.SourceScan(scanned=True))[0]
        _fail = P.build_engineer_card(
            P.EngineerRequest(opened=True),
            P.SourceScan(scanned=True, error="RuntimeError('x')"))[0]
        _texts = [
            _idle.note.now if _idle.note else _idle.value,
            _live.value,
            _fail.note.now if _fail.note else _fail.value,
        ]
        assert len({_idle.state, _live.state, _fail.state}) == 3
        assert len(set(_texts)) == 3, f"三種狀態的文字撞在一起：{_texts}"

    def test_source_level_idle_is_not_the_same_as_source_level_failure(self):
        """單盞燈的「未檢查」與「抓失敗」也不可混。"""
        _idle = P.build_source_card(
            P.probe_from_entry("f", _entry(P.STATUS_NEVER_RUN)))[0]
        _fail = P.build_source_card(
            P.probe_from_entry("f", _entry(P.STATUS_FAILED, last_error="e")))[0]
        assert _idle.state == UI_IDLE and _fail.state == UI_FAILED
        assert _idle.note.now != _fail.note.now
        assert "快取命中不算" in _idle.note.why, (
            "「未執行」的語意（快取命中不計）沒有講給使用者聽")


# ══════════════════════════════════════════════════════════════════
# 【9】工程師版：1 個 checkbox 全有全無 · 不加 form
# ══════════════════════════════════════════════════════════════════
def _st_calls(tree: ast.Module, attr: str) -> list[ast.Call]:
    return [_n for _n in ast.walk(tree)
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
            and _n.func.attr == attr]


class TestEngineerGateHasNoForm:
    """線框葉2 原文：「內含 **1 個 checkbox 全有全無** · **不加 form**」。

    DECISIONS #7 更明文**撤回**了 v1 的 `form_diag` 提案，理由是實測
    `app.py` 只有 1 個 checkbox —— **要解的問題不存在**。
    """

    def test_the_page_owns_no_form_at_all(self):
        _t = _tree()
        assert not _st_calls(_t, "form"), "本頁不得有 `st.form`（線框：不加 form）"
        assert not _st_calls(_t, "form_submit_button")
        assert "single_submit_form" not in _src(), (
            "共用層的表單入口也不該出現在本頁")

    def test_exactly_one_checkbox(self):
        _cbs = _st_calls(_tree(), "checkbox")
        assert len(_cbs) == 1, f"應該只有一顆 checkbox，實際 {len(_cbs)} 顆"

    def test_no_stray_button(self):
        _t = _tree()
        assert not _st_calls(_t, "button"), (
            "葉3 是 chat_input 天然 gate、葉2 是 checkbox —— 本頁不需要任何按鈕")
        assert not _st_calls(_t, "download_button")

    def test_the_two_labels_are_two_different_things(self):
        """線框 N5：上一輪把「摺疊標題」與「要勾的 checkbox」混成一個。"""
        assert P.ENGINEER_EXPANDER_LABEL != P.ENGINEER_CHECKBOX_LABEL
        assert "一般使用者不需要打開" in P.ENGINEER_EXPANDER_LABEL, (
            "摺疊標題的後半句被截掉了（線框 N5 點名的那個錯）")
        assert "較耗時" in P.ENGINEER_CHECKBOX_LABEL

    def test_the_where_names_both_steps(self):
        """指路句要寫**兩步**：先展開、再勾。production 就是兩步。"""
        assert "展開" in P.ENGINEER_WHERE and "勾" in P.ENGINEER_WHERE
        assert P.ENGINEER_EXPANDER_LABEL in P.ENGINEER_WHERE
        assert P.ENGINEER_CHECKBOX_LABEL in P.ENGINEER_WHERE

    def test_the_idle_note_uses_that_where(self):
        _card, _facts, _sig = P.build_engineer_card(
            P.EngineerRequest(opened=False), P.SourceScan())
        assert _card.note.where == P.ENGINEER_WHERE

    def test_it_is_inside_an_expander(self):
        assert _st_calls(_tree(), "expander"), "工程師版必須是摺疊的（預設收合）"

    def test_the_reason_for_no_form_is_written_down(self):
        """撤回 form 的理由要留在檔裡 —— 否則下一個人會再加一次。"""
        _s = _src()
        assert "不加 form" in _s and "撤回" in _s


# ══════════════════════════════════════════════════════════════════
# 【10】3 欄上限（線框：原 columns(7) 降階）
# ══════════════════════════════════════════════════════════════════
class TestThreeColumnGrid:
    def test_no_bare_columns_at_all(self):
        _bad = [_c.lineno for _c in _st_calls(_tree(), "columns")]
        assert not _bad, (
            f"第 {_bad} 行有裸 `st.columns()` —— 一律走 `_ui_kit.grid()`")

    def test_every_row_goes_through_the_grid(self):
        _fn = [_n for _n in ast.walk(_tree())
               if isinstance(_n, ast.FunctionDef) and _n.name == "_render_row"][0]
        _grid = [_n for _n in ast.walk(_fn) if isinstance(_n, ast.Call)
                 and isinstance(_n.func, ast.Name) and _n.func.id == "grid"]
        assert _grid, "`_render_row` 沒有走 `grid()`"

    def test_the_wall_wraps_instead_of_widening(self):
        """動態格子數 → 換行，不是加欄（`grid()` 內部硬夾 `MAX_COLS`）。"""
        from src.ui.views._ui_kit import MAX_COLS
        _items = tuple(range(7))
        _rows = [len(_chunk) for _chunk, _cols in
                 __import__("src.ui.views._ui_kit", fromlist=["grid"]).grid(
                     _items, MAX_COLS)]
        assert max(_rows) <= MAX_COLS and sum(_rows) == 7


# ══════════════════════════════════════════════════════════════════
# 【11】未接線的卡
# ══════════════════════════════════════════════════════════════════
def _all_unwired_builts():
    return (P.build_unmeasured_cards()
            + P.build_engineer_panel_cards()
            + (P.build_health6_card(), P.build_legacy_edu_card()))


#: ⚠️ **唯一一張「有出口」的未接線卡**，據實登記為例外。
#: 既有的 📚 教學分頁**沒有下架**，所以叫使用者去那裡是**真的指路**，
#: 不是頁 1／2／3／4 要防的那種「按了也不會發生任何事」的假出口。
_UNWIRED_WITH_A_REAL_EXIT: frozenset[str] = frozenset({"why.edu.legacy"})


class TestUnwiredStaysUnwired:
    def test_they_are_all_unwired(self):
        for _card, _facts, _sig in _all_unwired_builts():
            assert _card.state == UI_UNWIRED, f"{_card.key} 不是未接線態"

    def test_each_has_all_three_elements(self):
        for _card, _facts, _sig in _all_unwired_builts():
            _now, _why, _where = _note_triple(_card.note)
            assert all(_x.strip() for _x in (_now, _why, _where)), _card.key

    def test_the_wheres_are_not_copy_pasted(self):
        _wheres = [_c.note.where for _c, _f, _s in _all_unwired_builts()]
        assert len(set(_wheres)) == len(_wheres), (
            "有兩張未接線卡共用同一句「去哪補」—— "
            f"那會讓「補哪一層才會好」這個資訊消失：{_wheres}")

    def test_no_user_exit_except_the_one_declared(self):
        from src.ui.tabs.tab_today import NO_EXIT_MARKER
        for _card, _facts, _sig in _all_unwired_builts():
            _has_exit_marker = NO_EXIT_MARKER in _card.note.where
            if _card.key in _UNWIRED_WITH_A_REAL_EXIT:
                assert not _has_exit_marker, (
                    f"{_card.key} 被登記為「有真出口」卻寫了沒有出口")
                assert "沒有下架" in _card.note.where, (
                    "宣稱有出口就要說得出那個出口在哪、還在不在")
            else:
                assert _has_exit_marker, (
                    f"{_card.key} 沒有標明「沒有你可以執行的出口」—— "
                    "未接線卡不得給一句按了也沒用的指路")

    def test_none_of_them_pretends_to_have_a_conclusion(self):
        for _card, _facts, _sig in _all_unwired_builts():
            assert not _card.value, f"{_card.key} 未接線卻帶了結論文字"

    def test_every_unwired_card_carries_facts(self):
        for _card, _facts, _sig in _all_unwired_builts():
            assert _facts, f"{_card.key} 沒有任何 facts（接線後長什麼樣要看得見）"

    def test_the_health_six_factor_card_refuses_to_copy_the_weights(self):
        """⚠️ 在「解釋數字怎麼來」的頁面上貼一份沒有出處的權重 = 造第三份。"""
        _card, _facts, _sig = P.build_health6_card()
        _text = _card.note.now + _card.note.why + _card.note.where
        for _w in ("30", "20", "15", "10"):
            assert f"{_w}分" not in _text and f"+{_w}" not in _text
        assert "抄第三份" in _card.note.why


# ══════════════════════════════════════════════════════════════════
# 【12】規格層面的旗標與原因**直接讀自 L0**
# ══════════════════════════════════════════════════════════════════
class TestSpecFlagsComeFromL0:
    """線框葉2 note：「`unwired_reason` / `degraded_reason` **直接讀自 SSOT**」。"""

    def test_the_repo_currently_has_something_to_show(self):
        """反證：L0 現在真的有被標記的燈，否則下面幾條會空轉而假綠。"""
        _scan = P.load_specs()
        assert _scan.unwired, "L0 現在一盞未接線的燈都沒有？先確認掃描有掃到東西"
        assert _scan.degraded

    def test_flags_track_l0_not_a_hardcoded_list(self, monkeypatch):
        """把 L0 的旗標翻回 `True`，這張卡就該消失 —— 本檔沒有寫死哪一盞。"""
        _before = {_r.key for _r in P.load_specs().degraded}
        assert KEY_STOCK_TREND in _before

        _spec = SPECS_BY_KEY[KEY_STOCK_TREND]
        _patched = [
            _s if _s.key != KEY_STOCK_TREND
            else type(_s)(**{**_s.__dict__, "discriminative": True,
                             "degraded_reason": ""})
            for _s in P.STATION_SPECS]
        monkeypatch.setattr(P, "STATION_SPECS", _patched)
        _after = {_r.key for _r in P.load_specs().degraded}
        assert KEY_STOCK_TREND not in _after, (
            "L0 旗標翻回 True，本頁卻還在說它已失準（＝寫死了）")
        assert _spec.discriminative is False, "原始 L0 規格不該被這條測試改到"

    def test_the_l0_reason_reaches_the_screen(self):
        _scan = P.load_specs()
        for _row in _scan.unwired + _scan.degraded:
            _card, _facts, _sig = P.build_spec_flag_card(_row)
            _reason = _row.unwired_reason or _row.degraded_reason
            # 洗掉狀態 glyph 之後，原文的頭一段仍必須在畫面上。
            _head = P._clean_reason(_reason)[:12]
            assert _head and _head in _card.note.why, (
                f"{_row.key} 的 L0 原因沒有出現在畫面上")
            assert dict(_facts)[P.L0_REASON_FACT_LABEL] == P.L0_REASON_FACT_TEXT

    def test_a_reason_with_state_glyphs_does_not_blow_up_the_note(self):
        """實測：L0 `stock_kd.no_level_reason` 裡就有 2 個狀態 glyph。

        不洗 → `Note.__post_init__` 直接 `ValueError` → **整段揭露消失**，
        而畫面上一句解釋都沒有（§1：紅態要看得見，不是換一種炸法）。
        """
        _dirty = "抓不到 🔴 而且 🟢 也不對"
        _clean = P._clean_reason(_dirty)
        assert "🔴" not in _clean and "🟢" not in _clean
        assert "已移除" in _clean, "洗過就要說（修改過的訊息不能假裝是原文）"
        Note(now="x", why=_clean, where="y")          # 不得 raise

    def test_no_level_lights_get_no_state_chip(self):
        """`emits_level=False` **刻意不給狀態燈** —— 七態裡沒有一態講得對它。"""
        _scan = P.load_specs()
        assert _scan.no_level, "L0 現在沒有 emits_level=False 的燈？"
        _flagged = {_c.key for _c, _f, _s in P.build_spec_flag_cards(_scan)}
        for _row in _scan.no_level:
            if _row.wired and _row.discriminative:
                assert f"why.spec.{_row.key}" not in _flagged, (
                    f"{_row.key} 被硬塞了一個狀態燈 —— "
                    "unwired／degraded／empty 三句都不是它的實情")
        assert "依規格就不出等級的燈" in _src()

    def test_thresholds_are_never_written_in_this_page(self):
        """本頁一個門檻數字都不寫（全部逐欄讀 L0）。

        ⚠️ 掃的是 `_code_only()`（拿掉 docstring 與註解）—— 本頁的註解
        **在討論**「規格表寫 1.5% 但實作用 2%」那種漂移，
        拿整份檔案比對會把那句警語本身判成違規。
        """
        _code = _code_only()
        for _needle in ("3400", "22.0", "30.0", "1.5%", "0.07", "HEALTH_GRADE"):
            assert _needle not in _code, f"門檻數字 {_needle} 被寫死在本頁的程式碼裡"

    def test_the_spec_table_passes_l0_columns_through(self):
        _rows = P._spec_table_rows(P.load_specs().rows[:3])
        assert _rows and set(_rows[0]) == {
            "這一盞", "分組", "方向", "門檻", "值從哪來", "在防什麼", "已知限制"}

    def test_an_unknown_direction_is_shown_verbatim(self):
        """L0 多一個方向字面值 → 原樣顯示，不編一個看起來合理的說法。"""
        _row = P.SpecRow(key="k", label="l", family="總經", group="g",
                         direction="sideways_bad", unit="", threshold_text="",
                         source="", why="")
        assert _row.direction_text == "sideways_bad"


# ══════════════════════════════════════════════════════════════════
# 【13】重抄自 L0 的狀態字面值 —— 漂移就 CI 紅燈
# ══════════════════════════════════════════════════════════════════
class TestStatusLiteralsMatchL0:
    """本檔已誠實揭露這三個字面值是**第二真相源**（L0 沒有匯出常數）。

    這一條就是那句揭露的可執行版本：**直接掃 L0 的原始碼**。
    L0 哪天改字或多一態，這裡當場紅 —— 不是靠自律。
    """

    def test_all_three_literals_exist_in_l0_source(self):
        _l0 = _L0_MONITOR.read_text(encoding="utf-8")
        for _lit in (P.STATUS_NEVER_RUN, P.STATUS_OK, P.STATUS_FAILED):
            assert f"'{_lit}'" in _l0 or f'"{_lit}"' in _l0, (
                f"L0 `shared/fetch_monitor.py` 裡找不到狀態字面值 {_lit!r} —— "
                "本頁重抄的那一份已經漂移了（見本頁 `STATUS_NEVER_RUN` 的交接註記）")

    def test_the_page_declares_it_is_a_second_source_of_truth(self):
        _s = _src()
        assert "第二真相源" in _s and "交接事項" in _s

    def test_l0_still_has_no_exported_constants(self):
        """⚠️ 這一條是**提醒**：L0 哪天真的匯出了常數，本頁就該改成 import 它。"""
        import shared.fetch_monitor as _fm
        assert not hasattr(_fm, "STATUS_OK"), (
            "L0 已經匯出 `STATUS_OK` 了 —— 請把本頁改成 import 它，"
            "並刪掉本頁重抄的那三個常數與本條測試")


# ══════════════════════════════════════════════════════════════════
# 【14】葉3 AI 問答
# ══════════════════════════════════════════════════════════════════
class _FakeQA:
    def __init__(self, ok=True, text="", error=None, model="m", tool_calls=()):
        self.ok, self.text, self.error = ok, text, error
        self.model, self.tool_calls = model, list(tool_calls)


class TestQaLeaf:
    """四種情況**不可混**：沒問（灰）／沒金鑰（紅）／上游錯（紅）／回空（灰）。"""

    def test_not_asked_is_idle_grey(self):
        _card, _facts, _sig = P.build_qa_card(P.load_qa(P.QaRequest(asked=False)))
        assert _card.state == UI_IDLE and _card.note.now == "**尚未提問**"

    def test_missing_key_is_red_only_after_you_ask(self, monkeypatch):
        _mod = type(sys)("src.services.app_ai_service")
        _mod.get_gemini_api_key = lambda: ""
        monkeypatch.setitem(sys.modules, "src.services.app_ai_service", _mod)
        _qa = P.load_qa(P.QaRequest(asked=True, question="q"))
        assert _qa.key_missing and _qa.error
        _card, _facts, _sig = P.build_qa_card(_qa)
        assert _card.state == UI_FAILED
        assert "AI 問答未啟用" in _card.note.now
        assert "其他分頁的功能完全不受影響" in _card.note.where

    def test_the_key_entry_point_is_declared_unwired_not_faked(self):
        """線框 F5：不得把使用者指去改 `secrets.toml`；也不得就地收憑證。"""
        assert "secrets.toml" not in _src(), (
            "把客戶指去改一個他不碰的檔案（線框 F5 點名的錯）")
        assert "收憑證" in P.NO_KEY_WHERE and "客戶拍板" in P.NO_KEY_WHERE

    def test_upstream_error_is_red_and_quoted(self, monkeypatch):
        _key = type(sys)("src.services.app_ai_service")
        _key.get_gemini_api_key = lambda: "k"
        _agent = type(sys)("src.services.ai_qa_service")
        _agent.run_agent = lambda *_a, **_k: _FakeQA(ok=False,
                                                     error="429 quota")
        monkeypatch.setitem(sys.modules, "src.services.app_ai_service", _key)
        monkeypatch.setitem(sys.modules, "src.services.ai_qa_service", _agent)
        _card, _facts, _sig = P.build_qa_card(
            P.load_qa(P.QaRequest(asked=True, question="q")))
        assert _card.state == UI_FAILED and "429 quota" in _card.note.why

    def test_an_empty_answer_is_grey_not_red(self, monkeypatch):
        """`ok=True` 但沒有文字 = **有效結果**（模型真的沒話說），不是故障。"""
        _key = type(sys)("src.services.app_ai_service")
        _key.get_gemini_api_key = lambda: "k"
        _agent = type(sys)("src.services.ai_qa_service")
        _agent.run_agent = lambda *_a, **_k: _FakeQA(ok=True, text="   ")
        monkeypatch.setitem(sys.modules, "src.services.app_ai_service", _key)
        monkeypatch.setitem(sys.modules, "src.services.ai_qa_service", _agent)
        _card, _facts, _sig = P.build_qa_card(
            P.load_qa(P.QaRequest(asked=True, question="q")))
        assert _card.state == UI_EMPTY, "沒話說被畫成故障（假性錯誤）"

    def test_a_real_answer_is_live_and_the_tools_are_disclosed(self, monkeypatch):
        _key = type(sys)("src.services.app_ai_service")
        _key.get_gemini_api_key = lambda: "k"
        _agent = type(sys)("src.services.ai_qa_service")
        _agent.run_agent = lambda *_a, **_k: _FakeQA(
            ok=True, text="偏強。",
            tool_calls=[{"name": "get_stock_score"}])
        monkeypatch.setitem(sys.modules, "src.services.app_ai_service", _key)
        monkeypatch.setitem(sys.modules, "src.services.ai_qa_service", _agent)
        _qa = P.load_qa(P.QaRequest(asked=True, question="q"))
        _card, _facts, _sig = P.build_qa_card(_qa)
        assert _card.state == UI_LIVE
        assert dict(_facts)["這一輪用到的工具"] == "get_stock_score", (
            "AI 用了哪些工具要揭露 —— 那是「數字怎麼來」的一部分")

    def test_history_is_never_the_gate(self):
        """`len(history)` 當 gate 會讓上一輪問過被誤判成這一輪問了。"""
        _req = P.QaRequest(asked=False, history=({"role": "user",
                                                  "content": "舊的"},))
        assert P.load_qa(_req).asked is False, (
            "上一輪的對話紀錄讓這一輪被當成「問了」")
        _code = _code_only()
        assert "len(history)" not in _code and "len(_history)" not in _code, (
            "程式碼裡出現了用 history 長度做判斷的寫法")

    def test_history_reader_refuses_weird_shapes(self):
        assert P.read_history({}) == ()
        assert P.read_history({P.SS_QA_HISTORY: "not a list"}) == ()
        assert P.read_history({P.SS_QA_HISTORY: [1, {"role": "user"}]}) == (
            {"role": "user"},)


# ══════════════════════════════════════════════════════════════════
# 【15】本頁沒有任何 session 下標指派（gate 偽造不了）
# ══════════════════════════════════════════════════════════════════
class TestNoSessionSubscriptWrite:
    def test_no_subscript_assignment_at_all(self):
        _writes = [_n.lineno for _n in ast.walk(_tree())
                   if isinstance(_n, ast.Assign) and _n.targets
                   and isinstance(_n.targets[0], ast.Subscript)]
        assert not _writes, (
            f"本檔出現了下標指派（第 {_writes} 行）—— "
            "本頁的 gate 全是 widget 當下值，沒有任何 gate 是 session key；"
            "留一條寫入 session 的路等於留一條偽造 gate 的路")

    def test_the_only_session_write_is_the_chat_history(self):
        """⚠️ 用 AST 數**程式碼裡**的 `st.session_state`（docstring 不算）。"""
        assert "st.session_state.setdefault(SS_QA_HISTORY" in _code_only()
        _hits = _session_state_reads(_tree())
        assert len(_hits) <= 2, (
            f"本頁碰 session_state 的地方變多了（第 {_hits} 行）—— "
            "每多一處就多一個偽造 gate 的點")


# ══════════════════════════════════════════════════════════════════
# 【16】訊號頻道（鐵律 3）
# ══════════════════════════════════════════════════════════════════
def _every_built():
    _specs = P.load_specs()
    return (P.build_edu_cards(_specs, P.build_scale_disclosure())
            + P.build_unmeasured_cards()
            + P.build_spec_flag_cards(_specs)
            + P.build_engineer_panel_cards()
            + (P.build_empty_registry_card(),
               P.build_engineer_card(P.EngineerRequest(opened=False),
                                     P.SourceScan()),
               P.build_qa_card(P.load_qa(P.QaRequest(asked=False))),
               P.build_source_card(
                   P.probe_from_entry("f", _entry(P.STATUS_OK))),
               P.build_source_card(
                   P.probe_from_entry("f", _entry(P.STATUS_FAILED,
                                                  last_error="e")))))


class TestSignalChannelIsClean:
    """狀態頻道出 glyph ＋ 中文；訊號頻道**只出中文標籤**。"""

    def test_no_card_carries_a_banned_glyph_in_its_signal(self):
        for _card, _facts, _sig in _every_built():
            assert not banned_signal_glyphs(_sig), (
                f"{_card.key} 的 signal_text 帶了狀態 glyph／燈號 emoji：{_sig!r}")

    def test_this_page_uses_no_signal_channel_at_all(self):
        """本頁畫的**就是狀態本身**，沒有第二個頻道 —— 全部空字串是刻意的。"""
        assert all(_sig == "" for _c, _f, _sig in _every_built())
        assert "本頁全部的 `signal_text` 都是空字串" in _src()

    def test_every_note_survives_construction(self):
        """所有 Note 都建得起來（含 L0 原因那幾張）—— 不是半截死頁。"""
        for _card, _facts, _sig in _every_built():
            if _card.note is not None:
                _note_triple(_card.note)

    def test_states_are_all_legal(self):
        _legal = {UI_IDLE, UI_FAILED, UI_EMPTY, UI_DEGRADED, UI_UNWIRED, UI_LIVE}
        for _card, _facts, _sig in _every_built():
            assert _card.state in _legal, f"{_card.key} 用了非法狀態"


# ══════════════════════════════════════════════════════════════════
# 冒煙（slow lane）：這一頁真的畫得出來
# ══════════════════════════════════════════════════════════════════
@pytest.mark.slow
def test_page_mounts_clean(tmp_path):
    """冷啟動整頁 mount：**沒有 uncaught exception、不是半截頁面**。

    ⚠️ 這一條看得到的只有「畫得出來」；它**看不到**畫出來的東西是不是真的 ——
    那些由上面的單元測試守。冷啟動不會發任何 L3 取數（葉3 沒問、葉2 走 L0），
    所以本條不需要網路。

    ⚠️ 本條**刻意不斷言燈牆上有幾格**：登錄表的內容取決於這個 process 裡
    有沒有別的測試 import 過掛了 `@monitored` 的 L1 模組 —— 那是測試順序的
    副作用，拿它當斷言會得到一條時好時壞的測試。
    """
    import textwrap

    from streamlit.testing.v1 import AppTest

    _script = tmp_path / "_p05_view.py"
    _script.write_text(textwrap.dedent("""
        from src.ui.views.page_why import render_page_why
        render_page_why()
    """), encoding="utf-8")

    _at = AppTest.from_file(str(_script), default_timeout=180)
    _at.run()
    assert not _at.exception, (
        f"page_why mount 有 uncaught exception: {_at.exception}")

    _all = ("\n".join(_m.value for _m in _at.markdown)
            + "\n" + "\n".join(_c.value for _c in _at.caption))

    # 葉2 工程師版：**一顆** checkbox、**零**按鈕、零 form。
    assert [_c.label for _c in _at.checkbox] == [P.ENGINEER_CHECKBOX_LABEL]
    assert not _at.button, f"本頁不該有按鈕，實際 {[_b.label for _b in _at.button]}"

    # 葉3：chat_input 是唯一的送出入口（天然 gate）。
    assert len(_at.chat_input) == 1

    # 葉1：兩張門檻對照表（總經 ＋ 持股）真的畫出來了。
    assert len(_at.dataframe) == 2, (
        f"逐盞門檻對照表應有兩張，實際 {len(_at.dataframe)} 張")

    # 冷啟動 = idle，**不是** empty、**不是**紅。
    assert "**進階診斷未載入**".strip("*") in _all
    assert "**尚未提問**".strip("*") in _all
    assert "AI 問答未啟用" not in _all, (
        "還沒問就宣稱沒有金鑰了 —— 那要問過才知道（假性錯誤）")

    # 常駐揭露（不隨狀態消失）—— 畫不出來就是半截死頁。
    assert "不等於全站都好" in _all, "涵蓋率揭露沒畫出來"
    for _name in ("FRED", "FinMind", "TWSE"):
        assert _name in _all, f"線框具名的 {_name} 沒被畫出來（會變成滿版綠）"

    # 葉1 的三塊教學內容。
    assert "逐盞門檻對照表" in _all
    assert "健康評分六因子" in _all
    assert "兩套刻度" in _all


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
