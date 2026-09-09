"""tests/test_p01_macro_refresh.py — T3-1「頁1 原地重抓」的守衛（2026-09-09）。

守的是**這一批新增的那條平行路徑**：

    L5 `src/ui/views/page_today.py`（按鈕 / 文案 / status 收尾）
      → L3 `src/services/macro_refresh_service.py`（編排 + 逐步報告）
      → L3 `src/services/macro_session_apply.py`（寫 session）
      → L2 `src/compute/macro/macro_session_patch.py`（純函式算 patch）

⚠️ **每一條測試對應一個「動工條件」或一個已知的說謊方式，不是覆蓋率。**

  · `TestGoldenPatchMatchesTabMacro`  ← **golden**：同一份 bundle，純函式算出的
    patch 必須與 `tab_macro.py` 那段 in-line 寫入**逐鍵相等**。
    做法是**把 `tab_macro` 的原始碼切出來 exec**，不是抄一份到測試裡 ——
    抄一份只會證明「我抄得對」，證明不了「對面還是那樣寫」。
  · `TestJingqiGuard` / `TestMutationJingqiGuard`  ← 守衛④ ＋ 突變。
  · `TestStatusStateIsStrict` / `TestMutationStatusState` ← 部分成功不得標 complete ＋ 突變。
  · `TestExitCopyIsRouted` / `TestMutationExitCopy` ← 文案三分流 ＋ 突變。
  · `TestOnJobDoneIsOptional` ← 既有兩個 caller 不傳＝零行為變更。
  · `TestForceClearMatchesTheOldTab` ← 刻意重複的那份清快取不得漂開。
  · `TestOutOfReachIsMeasured` ← 「摸不到」那幾塊是**量**出來的，不是宣稱的。
  · `TestFailureCopyDoesNotSayRetry` / `TestNoHardcodedSecondsInPageCopy`
    ← 動工條件 ⑥ 與「失敗結果會被快取，不得叫人重試」。
  · `TestTimeoutWrapperDoesNotJoin` ← `with TPE` 的 `__exit__` 會 join，timeout 形同不存在。
  · `TestStageOneBoundaries` ← 本階段的硬範圍：不碰 `tabs/**`、不寫 `macro_alerts`、
    不搬 throttle。

⚠️ **這些是護欄，不是證明**（沿用 `tests/test_p01_today_view.py` 的自陳）：
它們釘住的是「已知的那幾種壞法不會再回來」，不是「這條路徑不會壞」。
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys
import textwrap
import types

import pytest

from src.compute.macro.macro_session_patch import (
    MACRO_PATCH_KEYS,
    MACRO_PATCH_POP_KEYS,
    build_macro_session_patch,
)
from src.services import macro_refresh_service as RS
from src.ui.views import page_today as P

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def _strip_docstrings(node):
    """就地拿掉 module / class / def 的 docstring。"""
    for _n in ast.walk(node):
        if isinstance(_n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                           ast.ClassDef)):
            _b = _n.body
            if (_b and isinstance(_b[0], ast.Expr)
                    and isinstance(_b[0].value, ast.Constant)
                    and isinstance(_b[0].value.value, str)):
                _n.body = _b[1:] or [ast.Pass()]
    return node


def _code_only(rel: str, *, func: str | None = None) -> str:
    """把一個檔（或其中一支函式）**去掉註解與 docstring** 之後的原始碼。

    ⚠️ 為什麼非這樣不可：本檔好幾條守衛是在問「這段 code 有沒有做 X」，
    而本批寫的註解**大量引用**了那些被禁的寫法本身
    （例：`_run_with_timeout` 的 docstring 明文寫「不得寫成
    `with ThreadPoolExecutor(...)`」）。直接 grep 原始碼會把**說明**
    誤判成**行為** —— 那正是 `CLAUDE.md §8.2.A.0` 規則 5「理由倒置」的
    測試版：守衛看起來紅了/綠了，但它看的根本不是那件事。
    """
    _tree = ast.parse(_src(rel))
    if func is not None:
        _tree = next(_n for _n in ast.walk(_tree)
                     if isinstance(_n, ast.FunctionDef) and _n.name == func)
    return ast.unparse(_strip_docstrings(_tree))


# ══════════════════════════════════════════════════════════════════
# 測試替身
# ══════════════════════════════════════════════════════════════════
class _FakeFrame:
    """`df_li_a` 的最小替身：只要有 `.empty` 就夠（純函式走 duck typing）。"""

    def __init__(self, empty: bool = False, tag: str = "df"):
        self.empty = empty
        self.tag = tag

    def __eq__(self, other):          # golden 比對要能判「是不是同一份」
        return isinstance(other, _FakeFrame) and other.tag == self.tag

    def __hash__(self):
        return hash(("_FakeFrame", self.tag))

    def __repr__(self):
        return f"_FakeFrame({self.tag!r}, empty={self.empty})"

    # ── 下面四支只為了讓 `tab_macro` 那段的 **log f-string** 跑得動 ──────
    # 它印 `len(df_li_a)` 與 `df_li_a.notna().any().sum()`；f-string 在
    # `print()` 被呼叫**之前**就求值，所以就算 print 被靜音也躲不掉。
    # ⚠️ 回傳值是什麼不重要（log 不是本測試的對象），**能跑**才重要 ——
    # 這幾支若拿掉，golden 會以 `TypeError` 收場而不是以「不相等」收場。
    def __len__(self):
        return 7

    def notna(self):
        return self

    def any(self):
        return self

    def sum(self):
        return 3


class _FakeSessionState(dict):
    """`st.session_state` 的最小替身（`[]` / `.get` / `.pop` / `in`）。"""


class _FakeST:
    def __init__(self, initial=None):
        self.session_state = _FakeSessionState(initial or {})


def _bundle(**over):
    """一份形狀正確的 `fetch_macro_bundle` 回傳。"""
    _b = {
        "intl_raw": {"道瓊工業 DJI": "DJI-DF"},
        "tw_raw": {"台股加權指數": "TWII-DF"},
        "tech_raw": {"台積電 ADR": "TSM-DF"},
        "inst": {"外資及陸資": {"net": 12.3}},
        "inst_date": "2026-09-09",
        "margin": 3123.4,
        "df_adl_raw": _FakeFrame(tag="adl"),
        "df_li_a": _FakeFrame(tag="li"),
        "adl_debug_msg": None,
        "elapsed_s": 12.3,
    }
    _b.update(over)
    return _b


# ══════════════════════════════════════════════════════════════════
# GOLDEN：純函式 vs `tab_macro.py` 那段真的 in-line 寫入
# ══════════════════════════════════════════════════════════════════
#: 從 `tab_macro.py` 切出來的那段的頭尾錨點（**用字面錨，不用行號** ——
#: 行號在任何一次重構後就失效，而重構不會觸發本測試更新，§8.2.A.0 規則 1）。
_TAB_BLOCK_START = "intl_raw   = _bundle['intl_raw']"
_TAB_BLOCK_END = "_fetch_ph.empty()"


def _tab_macro_write_block() -> str:
    """切出 `tab_macro.py` spinner 內的 session 寫入段（原始碼，未改一字）。"""
    _lines = _src("src/ui/tabs/tab_macro.py").splitlines()
    _b = next(i for i, l in enumerate(_lines) if _TAB_BLOCK_START in l)
    _e = next(i for i, l in enumerate(_lines) if _TAB_BLOCK_END in l)
    # `_e` 那行是 `_fetch_ph.empty()`，它上一行是包住它的 `try:` —— 兩行都不要。
    assert _lines[_e - 1].strip() == "try:", (
        "`tab_macro` 的寫入段結尾形狀變了（原本是 `try:` + `_fetch_ph.empty()`）"
        " —— 請重新確認本 golden 切出來的範圍還對不對，"
        "**不要**只把錨點改到能跑就算。")
    return textwrap.dedent("\n".join(_lines[_b:_e - 1]))


def _run_tab_macro_block(bundle, *, load_heavy: bool, session: dict,
                         now_str: str) -> dict:
    """真的把那段 code 跑一遍，回傳它寫完之後的 session。"""
    _st = _FakeST(session)
    _ns = {
        "_bundle": bundle,
        "_load_heavy": load_heavy,
        "st": _st,
        "_tw_now_str": lambda: now_str,
        "print": lambda *a, **k: None,     # 靜音；log 不是本測試的對象
    }
    exec(compile(_tab_macro_write_block(), "<tab_macro-block>", "exec"), _ns)
    return dict(_st.session_state)


def _apply_patch(session: dict, bundle, *, load_heavy: bool,
                 now_str: str) -> dict:
    """純函式版：算 patch → 套用到 session 的複本。"""
    _patch, _pops = build_macro_session_patch(
        bundle, load_heavy=load_heavy,
        prev_li_latest=session.get("li_latest"),
        prev_li_retain_meta=session.get("li_retain_meta"),
        now_str=now_str)
    _out = dict(session)
    _out.update(_patch)
    for _k in _pops:
        _out.pop(_k, None)
    return _out


#: golden 的情境矩陣。每一列都是一個**真的會發生**的組合。
_SCENARIOS = {
    "熱啟動 · 全部拿到": (True, {}, {}),
    "熱啟動 · 先行指標回 None（有舊快取可沿用）": (
        True, {"df_li_a": None}, {"li_latest": _FakeFrame(tag="old")}),
    "熱啟動 · 先行指標回空 df（有舊快取）": (
        True, {"df_li_a": _FakeFrame(empty=True, tag="empty")},
        {"li_latest": _FakeFrame(tag="old")}),
    "熱啟動 · 先行指標回 None（連舊快取都沒有）": (
        True, {"df_li_a": None}, {}),
    "熱啟動 · 已經沿用過兩輪（retain_meta 要累加）": (
        True, {"df_li_a": None},
        {"li_latest": _FakeFrame(tag="old"),
         "li_retain_meta": {"rounds": 2, "since": "2026-09-01 09:00"}}),
    "熱啟動 · retain_meta 被寫成不是 dict（要當成沒有）": (
        True, {"df_li_a": None},
        {"li_latest": _FakeFrame(tag="old"), "li_retain_meta": "壞掉的值"}),
    "熱啟動 · ADL 失敗（要設 adl_debug_msg）": (
        True, {"df_adl_raw": None, "adl_debug_msg": "來源均無回應"}, {}),
    "熱啟動 · 上一輪留著 adl_debug_msg，這輪成功（要 pop）": (
        True, {}, {"adl_debug_msg": "上一輪的錯誤"}),
    "熱啟動 · inst 全敗回空 dict（不得覆蓋 last-known-good）": (
        True, {"inst": {}, "inst_date": None},
        {"_last_inst": {"外資及陸資": {"net": 99.9}},
         "_last_inst_date": "2026-09-08"}),
    "熱啟動 · margin 回 None（不得覆蓋 last-known-good）": (
        True, {"margin": None}, {"_last_margin": 3000.0}),
    # ⚠️ 這一列是**突變測試逼出來的**：只有 `margin=None` 的話，
    #    把 truthy guard（`if bundle["margin"]:`）改成 `is not None` 兩邊仍相等，
    #    golden 照樣綠。`0.0` 是「falsy 但不是 None」的那個縫。
    "熱啟動 · margin 回 0.0（falsy 但不是 None —— truthy guard 的分界）": (
        True, {"margin": 0.0}, {"_last_margin": 3000.0}),
    "熱啟動 · inst_date 有值但 inst 是空的（truthy guard 的另一半）": (
        True, {"inst": {}, "inst_date": "2026-09-09"}, {}),
    "冷啟動 · li 沒跑（要沿用 session 的 li_latest）": (
        False, {"df_li_a": None}, {"li_latest": _FakeFrame(tag="old")}),
    "冷啟動 · li 沒跑且沒有舊快取": (False, {"df_li_a": None}, {}),
}


class TestGoldenPatchMatchesTabMacro:
    """同一份 bundle，兩條路徑寫出來的 session **逐鍵相等**。

    ⚠️ 這支測試的價值全在「右邊那一半是 `tab_macro.py` 的**原始碼**」——
    它是 exec 出來的，不是抄進測試檔的複本。對面改了寫法，這裡就會紅。
    """

    @pytest.mark.parametrize("name", sorted(_SCENARIOS))
    def test_every_key_matches(self, name):
        _load_heavy, _over, _session = _SCENARIOS[name]
        _b = _bundle(**_over)
        _now = "2026-09-09 13:45"
        _expected = _run_tab_macro_block(
            _b, load_heavy=_load_heavy, session=dict(_session), now_str=_now)
        _actual = _apply_patch(
            dict(_session), _b, load_heavy=_load_heavy, now_str=_now)
        assert _actual == _expected, (
            f"[{name}] 純函式與 tab_macro 的寫入不一致\n"
            f"  只有純函式有：{ {k: v for k, v in _actual.items() if k not in _expected} }\n"
            f"  只有 tab_macro 有：{ {k: v for k, v in _expected.items() if k not in _actual} }\n"
            f"  值不同：{ {k: (_actual[k], _expected[k]) for k in _actual if k in _expected and _actual[k] != _expected[k]} }")

    def test_the_golden_block_really_came_from_tab_macro(self):
        """假設檢查：切出來的真的是那一段（而不是切到空字串照樣「相等」）。"""
        _block = _tab_macro_write_block()
        for _needle in ("st.session_state['cl_data']", "st.session_state['cl_ts']",
                        "li_retain_meta", "_is_refreshing", "adl_debug_msg"):
            assert _needle in _block, f"切出來的區塊裡沒有 {_needle} —— 錨點失效了"

    def test_the_scenarios_actually_exercise_every_key(self):
        """假設檢查：情境矩陣真的碰得到契約上宣告的每一個 key。"""
        _seen: set[str] = set()
        _popped: set[str] = set()
        for _load_heavy, _over, _session in _SCENARIOS.values():
            _p, _q = build_macro_session_patch(
                _bundle(**_over), load_heavy=_load_heavy,
                prev_li_latest=_session.get("li_latest"),
                prev_li_retain_meta=_session.get("li_retain_meta"),
                now_str="2026-09-09 13:45")
            _seen |= set(_p)
            _popped |= set(_q)
        assert _seen == set(MACRO_PATCH_KEYS), (
            f"情境矩陣沒有碰到 {set(MACRO_PATCH_KEYS) - _seen}（或多寫了 "
            f"{_seen - set(MACRO_PATCH_KEYS)}）—— golden 的覆蓋面有洞")
        assert _popped == set(MACRO_PATCH_POP_KEYS)


class TestMutationGolden:
    """突變：把純函式的 `li_retain_meta` 累計拔掉 → golden **必須**轉紅。"""

    def test_removing_the_retain_counter_breaks_the_golden(self):
        _load_heavy, _over, _session = _SCENARIOS[
            "熱啟動 · 已經沿用過兩輪（retain_meta 要累加）"]
        _b = _bundle(**_over)
        _now = "2026-09-09 13:45"
        _expected = _run_tab_macro_block(
            _b, load_heavy=_load_heavy, session=dict(_session), now_str=_now)
        # 突變體：rounds 不累加（照抄上一輪）—— 這正是「沿用第 N 輪」會失真的那種 bug
        _mutant = _apply_patch(
            dict(_session), _b, load_heavy=_load_heavy, now_str=_now)
        _mutant["li_retain_meta"] = dict(
            _mutant["li_retain_meta"], rounds=_session["li_retain_meta"]["rounds"])
        assert _mutant != _expected, (
            "把 rounds 的累加拿掉之後 golden 還是綠的 —— "
            "這支 golden 沒有在守 li_retain_meta，請修測試而不是放過它")


# ══════════════════════════════════════════════════════════════════
# 突變工具：把服務 / 頁面的原始碼改一行，exec 成一個新 module
# ══════════════════════════════════════════════════════════════════
def _mutated_module(rel: str, *swaps: tuple[str, str]) -> types.ModuleType:
    """讀原始碼 → 套用字串替換（每一筆必須**恰好命中一次**）→ exec 成新 module。

    ⚠️ 為什麼要「恰好一次」：命中 0 次的替換 = 突變根本沒發生，
    而測試會照樣「通過」（因為它跑的是原版）—— 那是一支**假的突變測試**，
    比沒有更糟（它讓人以為那條守衛被驗過了）。
    """
    _text = _src(rel)
    for _old, _new in swaps:
        assert _text.count(_old) == 1, (
            f"突變目標在 {rel} 裡出現 {_text.count(_old)} 次（需要恰好 1 次）："
            f"{_old!r} —— 原始碼變了，請更新本測試的突變點")
        _text = _text.replace(_old, _new)
    _name = f"_mutant_{rel.replace('/', '_').replace('.', '_')}"
    _mod = types.ModuleType(_name)
    _mod.__file__ = str(_ROOT / rel)
    # ⚠️ 必須先掛進 `sys.modules`：`@dataclass` 會用
    # `sys.modules[cls.__module__].__dict__` 解型別註解，模組不在裡面就
    # `AttributeError: 'NoneType' object has no attribute '__dict__'`。
    sys.modules[_name] = _mod
    try:
        exec(compile(_text, f"<mutant:{rel}>", "exec"), _mod.__dict__)
    finally:
        sys.modules.pop(_name, None)
    return _mod


# ══════════════════════════════════════════════════════════════════
# 守衛④：沒有 ADL 就**不准**算旌旗
# ══════════════════════════════════════════════════════════════════
def _run_refresh_with_fakes(service, monkeypatch, *, df_adl,
                            report_jobs=("intl",), bundle=None):
    """把 `refresh_macro_now` 的每一個外部相依都換成替身，只看它呼叫了誰。

    `report_jobs`：假的 `fetch_macro_bundle` 會替哪些 job 回報結論。
    預設只回報一個 —— 那正是「報告漏收來源」的情境。
    `bundle`：整份 bundle 的內容（不給就用 `_bundle(df_adl_raw=df_adl)`）。
    ★1 的判空測試靠它注入「回空 / 只回一半」的桶。
    """
    _calls: list[str] = []

    import src.services.jingqi_calc as _JQ
    import src.services.macro_fetch_orchestrator as _ORCH
    import src.services.macro_session_apply as _APPLY
    import src.services.macro_trio_orchestrator as _TRIO
    import src.services.market_assessment_apply as _MKT
    import src.services.data_registry_scanner as _REG

    def _fake_bundle(**kw):
        _cb = kw.get("on_job_done")
        if _cb:
            for _n in report_jobs:
                _cb(_n, True, "1.0s")
        return _bundle(df_adl_raw=df_adl) if bundle is None else bundle

    monkeypatch.setattr(_ORCH, "fetch_macro_bundle", _fake_bundle)
    monkeypatch.setattr(_APPLY, "apply_macro_bundle",
                        lambda *a, **k: ({"cl_data": 1}, ()))
    monkeypatch.setattr(_JQ, "compute_and_store_jingqi",
                        lambda df: _calls.append(f"jingqi({df!r})"))
    monkeypatch.setattr(_TRIO, "run_macro_trio_and_persist",
                        lambda **k: _calls.append("trio"))
    monkeypatch.setattr(_MKT, "compute_and_apply_market_assessment",
                        lambda **k: _calls.append("market"))
    monkeypatch.setattr(_REG, "scan_and_write_data_registry",
                        lambda **k: _calls.append("registry"))
    _report = service.refresh_macro_now(mode=service.MODE_WARM)
    return _report, _calls


class TestJingqiGuard:
    """`compute_and_store_jingqi(None)` **不是 no-op** —— 沒 ADL 就不准叫它。"""

    def test_no_adl_means_jingqi_is_not_called(self, monkeypatch):
        _report, _calls = _run_refresh_with_fakes(RS, monkeypatch, df_adl=None)
        assert not [c for c in _calls if c.startswith("jingqi")], (
            "沒有 ADL 卻還是呼叫了 compute_and_store_jingqi —— "
            "它會走「大盤估算」備援生出一個假的廣度值，並清掉 health_partial")

    def test_with_adl_it_is_called(self, monkeypatch):
        _df = _FakeFrame(tag="adl")
        _report, _calls = _run_refresh_with_fakes(RS, monkeypatch, df_adl=_df)
        assert [c for c in _calls if c.startswith("jingqi")], \
            "有 ADL 卻沒算旌旗 —— 守衛寫反了"

    def test_the_skip_is_reported_as_skipped_not_as_success(self, monkeypatch):
        _report, _ = _run_refresh_with_fakes(RS, monkeypatch, df_adl=None)
        _jq = [s for s in _report.steps if s.name == RS.STEP_JINGQI]
        assert _jq and _jq[0].skipped, "跳過必須標成 skipped，不能混進成功裡"
        assert _report.skipped, "報告要讓呼叫端看得到「本輪有東西沒跑」"

    def test_it_matches_the_cron_guard(self):
        """本檔的守衛與 cron 是同一句話（cron 是它的出處）。"""
        _cron = _src("scripts/update_macro_forward_test.py")
        assert "if df_adl is not None:" in _cron and \
               "compute_and_store_jingqi(df_adl)" in _cron, \
            "cron 的守衛不見了 —— 那是本守衛的出處，兩邊要一起看"
        assert "if _df_adl is not None:" in _src(
            "src/services/macro_refresh_service.py")


class TestMutationJingqiGuard:
    """突變：拔掉守衛 → 上面那支必須轉紅。"""

    def test_removing_the_guard_makes_it_call_jingqi_with_none(self, monkeypatch):
        _mutant = _mutated_module(
            "src/services/macro_refresh_service.py",
            ('    _df_adl = _bundle.get("df_adl_raw")\n    if _df_adl is not None:',
             '    _df_adl = _bundle.get("df_adl_raw")\n    if True:'))
        _report, _calls = _run_refresh_with_fakes(_mutant, monkeypatch, df_adl=None)
        assert [c for c in _calls if c.startswith("jingqi")], (
            "突變體（拔掉守衛）居然沒有呼叫 jingqi —— "
            "表示上面那支測試守的不是這個守衛，請修測試")
        assert "jingqi(None)" in _calls


# ══════════════════════════════════════════════════════════════════
# 部分成功不得標 complete
# ══════════════════════════════════════════════════════════════════
def _report(**over):
    _kw = dict(mode=RS.MODE_WARM, started_at="2026-09-09 13:45", elapsed_s=1.0,
               sources=(RS.SourceResult("intl", True),), steps=())
    _kw.update(over)
    return RS.MacroRefreshReport(**_kw)


class TestStatusStateIsStrict:
    """只有「全成功 + 沒跳過」才 complete。"""

    def test_all_good_is_complete(self):
        assert P.refresh_status_state(_report()) == "complete"

    def test_one_failed_source_is_error(self):
        _r = _report(sources=(RS.SourceResult("intl", True),
                              RS.SourceResult("adl", False, "boom")))
        assert not _r.ok
        assert P.refresh_status_state(_r) == "error"

    def test_one_failed_step_is_error(self):
        _r = _report(steps=(RS.StepResult("market", False, "TimeoutError"),))
        assert P.refresh_status_state(_r) == "error"

    def test_a_skipped_step_is_also_error(self):
        """跳過 ≠ 成功：那盞燈這輪仍是上一輪的值，畫面必須看得出來。"""
        _r = _report(steps=(RS.StepResult("jingqi", True, "無 ADL", skipped=True),))
        assert _r.ok, "跳過不算失敗（`ok` 的語意）"
        assert P.refresh_status_state(_r) == "error", \
            "但它也不准收綠燈 —— 那會讓人以為整輪都更新到了"

    def test_partial_success_is_never_complete(self):
        _r = _report(sources=(RS.SourceResult("intl", True),
                              RS.SourceResult("tw", True),
                              RS.SourceResult("li", False, "TimeoutError")))
        assert P.refresh_status_state(_r) == "error"

    def test_a_half_filled_source_is_also_error(self):
        """★1：4 檔只拿到 2 檔 —— `ok` 是 True，但**不准**收綠燈。"""
        _r = _report(contents=(RS.SourceContent("intl", 2, 4, "檔",
                                                missing=("c", "d")),))
        assert _r.ok, "部分空刻意不進 failures（整桶標失敗是往另一邊說謊）"
        assert P.refresh_status_state(_r) == "error", \
            "只拿到半桶卻收綠燈 —— 那正是本批要修的那種說謊"


#: `refresh_is_clean` 的**三個**條件，一個一個拔掉都必須讓壞的一輪變綠。
#: 突變點寫成 `(要拔掉的片段, 拔掉後的樣子, 用哪一種壞輪次驗)`。
_CLEAN_MUTATIONS = [
    ("    return (bool(report.ok) and not report.skipped and not report.partials)",
     "    return (bool(report.ok) and not report.partials)", "skipped"),
    ("    return (bool(report.ok) and not report.skipped and not report.partials)",
     "    return (bool(report.ok) and not report.skipped)", "partial"),
    ("    return (bool(report.ok) and not report.skipped and not report.partials)",
     "    return True", "failed"),
]


class TestMutationStatusState:
    """突變：把判準放寬（少一個條件 / 恆真）→ 上面那些必須轉紅。"""

    @pytest.mark.parametrize("old,new,case", _CLEAN_MUTATIONS)
    def test_a_looser_rule_would_paint_a_bad_run_green(self, old, new, case):
        _mutant = _mutated_module("src/ui/views/page_today.py", (old, new))
        _r = {
            "skipped": _report(steps=(RS.StepResult("jingqi", True, "無 ADL",
                                                    skipped=True),)),
            "partial": _report(contents=(RS.SourceContent("intl", 2, 4, "檔"),)),
            "failed": _report(sources=(RS.SourceResult("adl", False, "boom"),)),
        }[case]
        assert _mutant.refresh_status_state(_r) == "complete", (
            "突變體居然沒有把壞的一輪畫成 complete —— "
            "表示上面那些測試守的不是這一行，請修測試")
        assert P.refresh_status_state(_r) == "error"


# ══════════════════════════════════════════════════════════════════
# 文案三分流
# ══════════════════════════════════════════════════════════════════
class TestExitCopyIsRouted:
    """三種出口對應三種**處置**，不是三種語氣。"""

    def test_the_three_are_distinct(self):
        _all = {P.EXIT_RETRY_HERE, P.EXIT_FIX_CODE,
                P.EXIT_OUT_OF_REACH, P.EXIT_ALERTS_PARTIAL}
        assert len(_all) == 4, "有兩句文案撞在一起了 —— 分流等於沒分"

    def test_only_the_retryable_one_promises_a_retry(self):
        assert "按一次就會重抓" in P.EXIT_RETRY_HERE
        for _c in (P.EXIT_FIX_CODE, P.EXIT_OUT_OF_REACH):
            assert "按一次就會重抓" not in _c, (
                "重抓沒用 / 摸不到的那兩句在承諾重抓 —— "
                "那是新的假指路（動工條件 4 明文禁止）")

    def test_the_unreachable_ones_say_so(self):
        for _c in (P.EXIT_FIX_CODE, P.EXIT_OUT_OF_REACH):
            assert "沒有你可以執行的出口" in _c, \
                "沒帶 `NO_EXIT_MARKER` —— 使用者不知道這一格按了沒用"

    def test_out_of_reach_lights_get_the_out_of_reach_copy(self):
        for _k in P.OUT_OF_REACH_LIGHT_KEYS:
            assert P.indicator_exit(_k) == P.EXIT_OUT_OF_REACH
        assert P.indicator_exit("vix") == P.EXIT_RETRY_HERE
        assert P.indicator_exit("adl") == P.EXIT_RETRY_HERE

    def test_the_news_bucket_is_out_of_reach_but_the_others_are_not(self):
        assert P.bucket_exit("news") == P.EXIT_OUT_OF_REACH
        for _b in ("long", "mid", "short", "chips"):
            assert P.bucket_exit(_b) == P.EXIT_RETRY_HERE

    def test_the_grey_indicator_note_actually_uses_the_router(self):
        """端到端：`health`（摸不到）與 `vix`（摸得到）拿到不同的 `where`。

        ⚠️ 兩邊都餵**有登記的**缺值原因：`reason` 空的那一種另有分流
        （★3 → `EXIT_FIX_CODE`），混在這裡會讓本測試守到別條規則上去。
        """
        from shared.macro_buckets import MISSING_NO_VALUE
        _rec = {"state": "missing", "reason": MISSING_NO_VALUE}
        _h = P.build_indicator_tile("health", _rec, requested=True, error="")
        _v = P.build_indicator_tile("vix", _rec, requested=True, error="")
        assert _h.card.note is not None and _v.card.note is not None
        assert _h.card.note.where == P.EXIT_OUT_OF_REACH
        assert _v.card.note.where == P.EXIT_RETRY_HERE

    def test_contract_drift_never_gets_the_retry_copy(self):
        """量綱漂移 / 沒有取值路徑 → 重抓沒用，必須是 `EXIT_FIX_CODE`。"""
        from shared.macro_buckets import MISSING_NO_EXTRACTION, MISSING_OUT_OF_RANGE
        for _reason in (MISSING_NO_EXTRACTION, MISSING_OUT_OF_RANGE):
            _t = P.build_indicator_tile(
                "vix", {"state": "missing", "reason": _reason},
                requested=True, error="")
            assert _t.card.note is not None
            assert _t.card.note.where == P.EXIT_FIX_CODE, (
                f"reason={_reason} 拿到的是「可以重抓」的文案 —— "
                "那是新的假指路：按一百次也一樣")


# ══════════════════════════════════════════════════════════════════
# ★3 同一張卡上的兩句話不得互相打臉
# ══════════════════════════════════════════════════════════════════
def _grey_note(key="vix", rec=None, *, requested=True):
    _t = P.build_indicator_tile(key, rec if rec is not None else {},
                                requested=requested, error="")
    assert _t.card.note is not None, "灰態卻沒有三要素"
    return _t.card.note


class TestUnknownReasonDoesNotPromiseARetry:
    """側車沒交代（或交代了沒登記的）原因 → `why` 與 `where` 必須同一個處置。"""

    @pytest.mark.parametrize("rec", [
        {},                                              # 側車跑了，這一盞沒紀錄
        {"state": "missing"},                            # 有紀錄，沒有 reason
        {"state": "missing", "reason": ""},              # reason 是空字串
        {"state": "missing", "reason": "_not_a_real_reason"},   # 沒登記的字串
    ])
    def test_it_sends_you_to_fix_the_code_not_to_press_again(self, rec):
        _n = _grey_note(rec=rec)
        assert _n.why == P.UNKNOWN_REASON_WHY, "本測試的前提：why 走「程式要修」"
        assert _n.where == P.EXIT_FIX_CODE, (
            "`why` 說「這是程式要修的訊號」，`where` 卻說「按一次就會重抓」—— "
            "同一張卡上兩句話互相打臉，而且照 `where` 做的人會白按")
        assert "按一次就會重抓" not in _n.where

    def test_the_two_halves_come_from_one_judgement(self):
        """`reason_is_unregistered` 與 `_miss_why` 必須是同一把尺。"""
        _t = _code_only("src/ui/views/page_today.py",
                        func="reason_is_unregistered")
        assert "_miss_why" in _t and "UNKNOWN_REASON_WHY" in _t, (
            "分流自己另寫了一條判斷式 —— 兩把尺遲早分岔，"
            "那正是本項要修的病")

    @pytest.mark.parametrize("reason", ["no_value", "not_loaded",
                                        "out_of_range", "no_extraction"])
    def test_a_registered_reason_keeps_its_own_routing(self, reason):
        """反向：**有登記**的原因照原本的分流走，不得被一路吸進「程式要修」。"""
        _n = _grey_note(rec={"state": "missing", "reason": reason})
        assert _n.why != P.UNKNOWN_REASON_WHY
        assert _n.where in (P.EXIT_RETRY_HERE, P.EXIT_FIX_CODE)
        if reason in ("no_value", "not_loaded"):
            assert _n.where == P.EXIT_RETRY_HERE, \
                "這兩種原因重抓真的有用 —— 全部改成「程式要修」是往另一邊說謊"

    def test_out_of_reach_still_wins(self):
        """摸不到的那兩盞：原因沒登記時仍給「摸不到」，那才是唯一可行的下一步。"""
        for _k in P.OUT_OF_REACH_LIGHT_KEYS:
            assert _grey_note(_k, {}).where == P.EXIT_OUT_OF_REACH


class TestColdStartIsNotACodeBug:
    """★3 的必要配套：冷啟動的「沒有原因」是**正常的**，處置正好相反。"""

    def test_idle_lights_do_not_say_the_code_is_broken(self):
        _n = _grey_note(requested=False)
        assert _n.why == P.IDLE_LIGHT_WHY
        assert "程式要修" not in _n.why, (
            "冷啟動被說成「程式要修」—— 那是叫使用者去修一個不存在的 bug"
            "（而且他該做的正是按那顆按鈕）")

    def test_idle_lights_point_at_the_button(self):
        assert _grey_note(requested=False).where == P.EXIT_RETRY_HERE

    def test_idle_says_not_loaded_not_no_value(self):
        _n = _grey_note(requested=False)
        assert "尚未載入" in _n.now and "無數值" not in _n.now, \
            "「還沒叫」與「叫了沒回」是兩種處置，不得共用一句話"

    def test_every_light_survives_a_cold_start(self):
        """整份冷啟動：16 盞燈沒有一盞說「程式要修」。"""
        _t = P.build_indicator_tiles(P.MacroReadout(requested=False))
        for _b, _tiles in _t.items():
            for _tile in _tiles:
                _n = _tile.card.note
                if _n is None or _tile.card.state == P.UI_UNWIRED:
                    continue
                assert _n.where != P.EXIT_FIX_CODE, (
                    f"{_tile.card.key} 在冷啟動被判成程式 bug —— "
                    "側車根本還沒跑，沒有原因是正常的")


class TestMutationUnknownReasonRouting:
    """突變：把 ★3 的分流拔掉 / 把冷啟動併回去 → 上面那些必須轉紅。"""

    def test_dropping_the_rec_argument_brings_back_the_retry_promise(self):
        _mutant = _mutated_module(
            "src/ui/views/page_today.py",
            ("                     where=indicator_exit(key, rec))",
             "                     where=indicator_exit(key))"))
        _n = _mutant.build_indicator_tile("vix", {}, requested=True,
                                          error="").card.note
        assert _n.where == P.EXIT_RETRY_HERE, (
            "突變體（不把側車那一筆傳給分流）居然沒有回到「可以重抓」—— "
            "表示上面那些測試守的不是這一段，請修測試")
        assert _grey_note().where == P.EXIT_FIX_CODE

    def test_folding_idle_back_in_would_call_a_cold_start_a_bug(self):
        _mutant = _mutated_module(
            "src/ui/views/page_today.py",
            ("    elif _state == UI_IDLE:", "    elif False:"))
        _n = _mutant.build_indicator_tile("vix", {}, requested=False,
                                          error="").card.note
        assert _n.where == P.EXIT_FIX_CODE and "程式要修" in _n.why, (
            "突變體（拿掉冷啟動那一支）居然沒有把冷啟動說成程式 bug —— "
            "表示 `TestColdStartIsNotACodeBug` 守的不是這一段，請修測試")
        assert _grey_note(requested=False).where == P.EXIT_RETRY_HERE


class TestMutationExitCopy:
    """突變：把分流函式改成一律「可以重抓」→ 上面那些必須轉紅。"""

    def test_collapsing_the_router_breaks_the_guard(self, monkeypatch):
        monkeypatch.setattr(P, "indicator_exit",
                            lambda _k, _rec=None: P.EXIT_RETRY_HERE)
        from shared.macro_buckets import MISSING_NO_VALUE
        _h = P.build_indicator_tile(
            "health", {"state": "missing", "reason": MISSING_NO_VALUE},
            requested=True, error="")
        assert _h.card.note.where == P.EXIT_RETRY_HERE, (
            "把分流拔掉之後 `health` 居然還是拿到「摸不到」的文案 —— "
            "表示 `build_indicator_tile` 根本沒在用 `indicator_exit`，請修 code")

    def test_collapsing_the_bucket_router_is_visible(self, monkeypatch):
        monkeypatch.setattr(P, "bucket_exit", lambda _b: P.EXIT_RETRY_HERE)
        _tiles = P.build_bucket_tiles(
            P.MacroReadout(requested=True, readiness={}, summary={}))
        _news = [t for t in _tiles if t.card.key == "summary.news"]
        assert _news and _news[0].card.note.where == P.EXIT_RETRY_HERE, \
            "`build_bucket_tiles` 沒有走 `bucket_exit`，分流是死的"


# ══════════════════════════════════════════════════════════════════
# `on_job_done`：不傳 = 零行為變更
# ══════════════════════════════════════════════════════════════════
class TestOnJobDoneIsOptional:

    def _run(self, **kw):
        from src.services.macro_fetch_orchestrator import fetch_macro_bundle
        return fetch_macro_bundle(
            load_heavy=False, prev_cl_data={}, fm_token="", li_token="",
            bps_session=object(),
            intl_map={"a": "A"}, tw_map={"b": "B"}, tech_map={"c": "C"},
            fetch_single=lambda s, **k: f"df:{s}",
            fetch_institutional=lambda: ({}, None),
            fetch_margin_balance=lambda: None,
            fetch_adl=lambda **k: None,
            **kw)

    def test_the_two_existing_callers_do_not_pass_it(self):
        """零行為變更的**前提**：既有 caller 一個都沒傳。"""
        for _rel in ("src/ui/tabs/tab_macro.py",
                     "scripts/update_macro_forward_test.py"):
            assert "on_job_done" not in _src(_rel), (
                f"{_rel} 開始傳 on_job_done 了 —— "
                "「既有 caller 不傳＝零行為變更」這句話要重新驗")

    def test_result_is_identical_with_and_without_the_callback(self):
        _a = self._run()
        _b = self._run(on_job_done=lambda *a: None)
        assert set(_a) == set(_b)
        for _k in ("intl_raw", "tw_raw", "tech_raw", "inst", "margin"):
            assert _a[_k] == _b[_k], f"{_k} 因為傳了回呼而不一樣了"

    def test_the_callback_sees_every_job(self):
        _seen = []
        self._run(on_job_done=lambda n, ok, d: _seen.append((n, ok)))
        assert {n for n, _ in _seen} == {"intl", "tw", "tech"}, \
            f"冷啟動應該回報 3 個 job，實得 {_seen}"

    def test_a_broken_callback_does_not_break_the_fetch(self):
        """§1：顯示壞掉不得擋取數。"""
        def _boom(*_a):
            raise RuntimeError("回呼自己炸了")
        _out = self._run(on_job_done=_boom)
        assert _out["intl_raw"] == {"a": "df:A"}, \
            "回呼拋例外把取數一起帶走了 —— 取數不該被 UI 拖累"


# ══════════════════════════════════════════════════════════════════
# 刻意重複的那份「清快取」不得漂開
# ══════════════════════════════════════════════════════════════════
class TestForceClearMatchesTheOldTab:
    """`clear_macro_caches` 是 `handlers._on_force_clear_click` 的刻意重複。

    本階段 `src/ui/tabs/**` 不准動 ⇒ 併不回去 ⇒ 只能靠這支盯著它們不要漂開。
    **第二階段收編舊分頁時，第一件事就是把這份併回去，然後刪掉這支測試。**
    """

    _MUST_CALL = ("_pkl_clear_all", "st.cache_data.clear",
                  "_URL_CACHE.clear", "reset_proxy_cache")

    def _old_tab_handler(self) -> str:
        return _code_only("src/ui/tabs/macro/handlers.py",
                          func="_on_force_clear_click")

    def _new_service(self) -> str:
        # ⚠️ code-only：本函式的 docstring 明文寫著「刻意不做
        # `_macro_session_reset()`」，直接 grep 會把那句**說明**判成**行為**。
        return _code_only("src/services/macro_refresh_service.py",
                          func="clear_macro_caches")

    @pytest.mark.parametrize("needle", _MUST_CALL)
    def test_both_clear_the_same_three_layers(self, needle):
        assert needle in self._old_tab_handler(), \
            f"舊分頁不再清 {needle} —— 新舊已經漂開，請重新對齊"
        assert needle in self._new_service(), \
            f"新服務沒有清 {needle} —— 兩份清快取的範圍不一樣了"

    def test_the_new_one_deliberately_does_not_reset_the_session(self):
        """新的**不做** `_macro_session_reset` —— 那會刪掉本路徑寫不回來的東西。"""
        assert "_macro_session_reset" in self._old_tab_handler()
        assert "_macro_session_reset" not in self._new_service()

    def test_no_session_key_is_popped_by_the_new_one(self):
        _new = self._new_service()
        assert "session_state.pop" not in _new, (
            "`clear_macro_caches` 開始 pop session key 了 —— "
            "其中 `warroom_summary` 本路徑寫不回來，pop 掉等於刪資料不是更新")


# ══════════════════════════════════════════════════════════════════
# 「摸不到」是量出來的，不是宣稱的
# ══════════════════════════════════════════════════════════════════
def _session_writers(key: str) -> set[str]:
    """全 repo 掃**真的**寫 `session_state['<key>']` 的檔（AST，不是 grep）。

    ⚠️ 用 AST 不用 grep 的實測理由：`src/services/allocation_service.py` 的
    docstring 裡逐字寫著 `st.session_state['warroom_summary'] = {...}`
    （它在**描述**另一支的 bug）。grep 會把那個檔算成寫入者，
    於是「寫得到它的只有舊分頁」這句話會被一段**說明文字**判成假的。
    """
    _out: set[str] = set()
    for _p in (list((_ROOT / "src").rglob("*.py"))
               + list((_ROOT / "scripts").rglob("*.py")) + [_ROOT / "app.py"]):
        try:
            _tree = ast.parse(_p.read_text(encoding="utf-8"))
        except SyntaxError:                     # 不該發生；發生了要看得見
            raise
        for _n in ast.walk(_tree):
            _tgts = (_n.targets if isinstance(_n, ast.Assign)
                     else [_n.target] if isinstance(_n, (ast.AugAssign,
                                                         ast.AnnAssign))
                     else [])
            for _t in _tgts:
                if (isinstance(_t, ast.Subscript)
                        and "session_state" in ast.unparse(_t.value)):
                    try:
                        if ast.literal_eval(_t.slice) == key:
                            _out.add(_p.relative_to(_ROOT).as_posix())
                    except (ValueError, TypeError):
                        pass                    # 動態 key，不在本掃描射程內
            if (isinstance(_n, ast.Call)
                    and isinstance(_n.func, ast.Attribute)
                    and _n.func.attr == "setdefault"
                    and "session_state" in ast.unparse(_n.func.value)
                    and _n.args):
                try:
                    if ast.literal_eval(_n.args[0]) == key:
                        _out.add(_p.relative_to(_ROOT).as_posix())
                except (ValueError, TypeError):
                    pass
    return _out


class TestOutOfReachIsMeasured:

    def test_written_keys_cover_every_module_this_path_calls(self):
        """`WRITES_SESSION_KEYS` 必須涵蓋這條路徑呼叫的每一支的 session 寫入。"""
        _mods = ("src/services/jingqi_calc.py",
                 "src/services/market_assessment_apply.py",
                 "src/services/macro_trio_orchestrator.py",
                 "src/services/data_registry_scanner.py")
        _keys: set[str] = set()
        for _rel in _mods:
            _tree = ast.parse(_src(_rel))
            for _n in ast.walk(_tree):
                _tgts = (_n.targets if isinstance(_n, ast.Assign)
                         else [_n.target] if isinstance(_n, (ast.AugAssign,
                                                             ast.AnnAssign))
                         else [])
                for _t in _tgts:
                    if isinstance(_t, ast.Subscript) and \
                            "session_state" in ast.unparse(_t.value):
                        _keys.add(ast.literal_eval(_t.slice))
        _missing = _keys - set(RS.WRITES_SESSION_KEYS)
        assert not _missing, (
            f"這條路徑呼叫的模組會寫 {_missing}，但 `WRITES_SESSION_KEYS` 沒列 —— "
            "畫面上的「有更新到 / 沒更新到」會少講一項")

    @pytest.mark.parametrize("key", ["warroom_summary", "_macro_news_items",
                                     "macro_alerts", "macro_state",
                                     "chips_loaded", "intl_snap", "ma_snap"])
    def test_the_untouched_keys_are_really_not_written_by_this_path(self, key):
        assert key not in RS.WRITES_SESSION_KEYS, (
            f"`{key}` 被接進本路徑了 —— "
            "`UNTOUCHED_BLOCKS` 與 `page_today.OUT_OF_REACH_*` 要一起改，"
            "否則畫面會說一件已經不成立的事")

    @pytest.mark.parametrize("key", ["warroom_summary", "_macro_news_items",
                                     "macro_alerts", "macro_state", "ma_snap"])
    def test_their_writers_are_all_inside_the_old_tabs(self, key):
        """「寫得到它的是舊分頁」這句話是**量**出來的。"""
        _w = _session_writers(key)
        assert _w, f"`{key}` 一個寫入點都沒有？請重新確認掃描式"
        _outside = {p for p in _w if not p.startswith("src/ui/tabs/")}
        assert not _outside, (
            f"`{key}` 在 `src/ui/tabs/**` 之外也有寫入點 {_outside} —— "
            "畫面上「寫得到它的是……」那句話要更新")

    @pytest.mark.parametrize("block", RS.UNTOUCHED_BLOCKS,
                             ids=[_b.session_key for _b in RS.UNTOUCHED_BLOCKS])
    def test_the_declared_writer_is_the_measured_writer(self, block):
        """★4：每一列的 `writer` **逐檔**對得上 AST 量到的寫入點。

        ⚠️ 這一條是 2026-09-09 獨立 QA 抓到的第四個洞的守衛：
        `chips_loaded` 原本宣稱寫入點是「app.py ＋ tab_macro.py」，
        實測只有 `tab_macro.py` —— `app.py` 那一處是**註解**
        （一段講舊 bug 的說明，含一行被註解掉的賦值）。
        照原文去 `app.py` 找的人會找不到東西，然後開始懷疑整份清單。
        比對用**後綴**：宣告寫短路徑（`macro/section_mid.py`）是可以的，
        寫一個根本沒有那個 key 的檔則不行。
        """
        _keys = [_k.strip() for _k in block.session_key.split("/") if _k.strip()]
        _measured = {_p for _k in _keys for _p in _session_writers(_k)}
        _declared = set(re.findall(r"[\w./]+\.py", block.writer))
        for _d in _declared:
            assert any(_m.endswith(_d) for _m in _measured), (
                f"`{block.session_key}` 宣稱 `{_d}` 寫得到它，"
                f"但 AST 量到的寫入點只有 {sorted(_measured) or '（無）'} —— "
                "照這句話去那個檔找的人會找不到東西")
        for _m in _measured:
            assert any(_m.endswith(_d) for _d in _declared), (
                f"`{block.session_key}` 有一個沒被宣告的寫入點 `{_m}` —— "
                "畫面上「寫得到它的是……」那句話少講了一個地方")

    def test_futures_net_still_has_no_writer_anywhere(self):
        """`UNTOUCHED_BLOCKS` 對 `futures_net` 的宣稱：全 repo 0 個寫入點。"""
        assert _session_writers("futures_net") == set(), (
            "`futures_net` 現在有寫入點了 —— "
            "`UNTOUCHED_BLOCKS` 裡「全 repo 沒有任何一處寫這個 key」那句已經過期")

    def test_the_untouched_list_names_every_out_of_reach_light(self):
        """16 盞燈裡判為摸不到的那兩盞，都在畫面列出的清單裡有交代。"""
        _blob = " ".join(f"{b.label} {b.session_key} {b.why}"
                         for b in RS.UNTOUCHED_BLOCKS)
        assert "warroom_summary" in _blob      # health 那盞
        assert "_macro_news_items" in _blob    # news_systemic 那盞

    def test_every_out_of_reach_light_key_is_a_real_spec(self):
        from shared.macro_buckets import SPECS_BY_KEY
        for _k in P.OUT_OF_REACH_LIGHT_KEYS:
            assert _k in SPECS_BY_KEY, f"{_k} 不是一盞真的燈 —— 名字打錯了？"

    def test_every_out_of_reach_bucket_is_a_real_bucket(self):
        from shared.macro_buckets import BUCKET_ORDER
        for _b in P.OUT_OF_REACH_BUCKETS:
            assert _b in BUCKET_ORDER


# ══════════════════════════════════════════════════════════════════
# ★2 「有更新到」要涵蓋每一步真的寫進去的 key
# ══════════════════════════════════════════════════════════════════
#: 哪一步由哪一支模組寫 session（`STEP_WRITES` 的出處，逐支 AST 比對）。
_STEP_MODULES = {
    RS.STEP_JINGQI: "src/services/jingqi_calc.py",
    RS.STEP_TRIO: "src/services/macro_trio_orchestrator.py",
    RS.STEP_MARKET: "src/services/market_assessment_apply.py",
    RS.STEP_REGISTRY: "src/services/data_registry_scanner.py",
}


def _assigned_session_keys(rel: str) -> set[str]:
    """一支模組**真的賦值**的 session key（AST，不是 grep）。"""
    _out: set[str] = set()
    for _n in ast.walk(ast.parse(_src(rel))):
        _tgts = (_n.targets if isinstance(_n, ast.Assign)
                 else [_n.target] if isinstance(_n, (ast.AugAssign, ast.AnnAssign))
                 else [])
        for _t in _tgts:
            if (isinstance(_t, ast.Subscript)
                    and "session_state" in ast.unparse(_t.value)):
                _out.add(ast.literal_eval(_t.slice))
    return _out


def _run_refresh_writing(service, monkeypatch, *, trio_keys=(
        "m1b_m2_info", "bias_info", "macro_info"), extra=None, bundle=None):
    """跑一輪，**替身真的會寫 session** —— 驗「有更新到」是量出來的。

    ⚠️ 與 `_run_refresh_with_fakes` 的差別只有一個：那邊的替身**什麼都不寫**
    （它守的是「呼叫了誰」），這邊的替身**照真模組的寫法賦值**
    （`st.session_state['x'] = 新物件`，AST 掃描確認過的同一種寫法）。
    兩支不合併：一支證明「有沒有叫」，一支證明「叫了之後畫面說了什麼」。
    """
    import src.services.jingqi_calc as _JQ
    import src.services.macro_fetch_orchestrator as _ORCH
    import src.services.macro_session_apply as _APPLY
    import src.services.macro_trio_orchestrator as _TRIO
    import src.services.market_assessment_apply as _MKT
    import src.services.data_registry_scanner as _REG

    _st = _FakeST({})
    monkeypatch.setattr(service, "st", _st)
    _b = bundle if bundle is not None else _content_bundle()

    def _fake_bundle(**kw):
        _cb = kw.get("on_job_done")
        if _cb:
            for _n in RS.SOURCE_LABELS:
                _cb(_n, True, "1.0s")
        return _b

    def _write(key, value=None):
        _st.session_state[key] = {"v": value} if value is None else value

    def _fake_apply(*a, **k):
        _patch = {"cl_data": {"x": 1}, "cl_ts": "2026-09-09 13:45"}
        _st.session_state.update(_patch)
        return _patch, ("adl_debug_msg",)

    def _fake_trio(**k):
        for _k in trio_keys:
            _write(_k)

    def _fake_registry(**k):
        _write("data_registry")
        for _k in (extra or ()):
            _write(_k)

    monkeypatch.setattr(_ORCH, "fetch_macro_bundle", _fake_bundle)
    monkeypatch.setattr(_APPLY, "apply_macro_bundle", _fake_apply)
    monkeypatch.setattr(_JQ, "compute_and_store_jingqi",
                        lambda df: _write("jingqi_info"))
    monkeypatch.setattr(_TRIO, "run_macro_trio_and_persist", _fake_trio)
    monkeypatch.setattr(_MKT, "compute_and_apply_market_assessment",
                        lambda **k: _write("mkt_info"))
    monkeypatch.setattr(_REG, "scan_and_write_data_registry", _fake_registry)
    return service.refresh_macro_now(mode=service.MODE_WARM)


class TestWrittenKeysMatchTheModules:
    """`STEP_WRITES` 的宣告 ＝ 那幾支模組**真的**賦值的 key（AST 比對）。"""

    @pytest.mark.parametrize("step,rel", sorted(_STEP_MODULES.items()))
    def test_each_step_declares_exactly_what_its_module_writes(self, step, rel):
        assert set(RS.STEP_WRITES[step]) == _assigned_session_keys(rel), (
            f"`STEP_WRITES[{step!r}]` 與 {rel} 實際寫的 key 對不上 —— "
            "畫面上的「有更新到 / 沒更新到」會少講（或多講）一項")

    def test_the_apply_step_follows_the_l2_contract(self):
        assert RS.STEP_WRITES[RS.STEP_APPLY] == MACRO_PATCH_KEYS

    def test_the_public_declaration_is_derived_not_retyped(self):
        _union = {_k for _ks in RS.STEP_WRITES.values() for _k in _ks}
        assert set(RS.WRITES_SESSION_KEYS) == _union, (
            "`WRITES_SESSION_KEYS` 又被寫成一份獨立的字面清單了 —— "
            "那正是它上一次漂掉的原因（§8.2.A.0 規則 2）")
        assert len(RS.WRITES_SESSION_KEYS) == len(_union), "有重複的 key"

    @pytest.mark.parametrize("key", ["jingqi_info", "mkt_info", "m1b_m2_info",
                                     "bias_info", "macro_info", "data_registry"])
    def test_the_six_step_keys_are_declared(self, key):
        """★2 的那六個 key —— 修前它們兩份清單都不在。"""
        assert key in RS.WRITES_SESSION_KEYS

    def test_the_declaration_is_read_by_production_code(self):
        """⚠️ 一份沒人讀的宣告就是下一個會漂掉的宣告。

        修前 `WRITES_SESSION_KEYS` **只有測試 import**；現在它被
        `refresh_macro_now`（對帳）與 `not_written_keys`（沒寫到的清單）讀。
        兩處都用**去掉註解與 docstring** 的原始碼比對 —— 註解裡提到不算數。
        """
        assert "WRITES_SESSION_KEYS" in _code_only(
            "src/services/macro_refresh_service.py", func="refresh_macro_now")
        assert "WRITES_SESSION_KEYS" in _code_only(
            "src/services/macro_refresh_service.py", func="not_written_keys")


class TestWrittenKeysAreMeasured:
    """★2 正向：每一步真的寫進去的 key 都要進「有更新到」。"""

    def test_the_six_step_keys_show_up(self, monkeypatch):
        _r = _run_refresh_writing(RS, monkeypatch)
        for _k in ("jingqi_info", "mkt_info", "m1b_m2_info", "bias_info",
                   "macro_info", "data_registry"):
            assert _k in _r.written_keys, (
                f"步驟真的寫了 `{_k}`，「有更新到」卻沒列 —— "
                "使用者想確認它更新了沒，兩份清單都找不到")

    def test_the_apply_patch_is_still_there(self, monkeypatch):
        _r = _run_refresh_writing(RS, monkeypatch)
        assert "cl_data" in _r.written_keys and "cl_ts" in _r.written_keys

    def test_every_declared_key_lands_in_exactly_one_list(self, monkeypatch):
        """宣告的 15 鍵**每一個**都要在「有更新到 / 沒寫到 / 刪掉了」其中一份。"""
        _r = _run_refresh_writing(RS, monkeypatch)
        _seen = set(_r.written_keys) | set(_r.not_written_keys) | set(_r.popped_keys)
        assert set(RS.WRITES_SESSION_KEYS) <= _seen
        assert not (set(_r.written_keys) & set(_r.not_written_keys)), \
            "同一個 key 同時說「有更新到」與「沒更新到」"

    def test_a_key_the_step_did_not_write_is_reported_as_not_written(
            self, monkeypatch):
        """trio 的 truthy guard：3 個子任務只成功 1 個 → 另 2 個要列在「沒寫到」。"""
        _r = _run_refresh_writing(RS, monkeypatch, trio_keys=("m1b_m2_info",))
        assert "m1b_m2_info" in _r.written_keys
        assert "bias_info" in _r.not_written_keys
        assert "macro_info" in _r.not_written_keys
        _trio = [_s for _s in _r.steps if _s.name == RS.STEP_TRIO]
        assert _trio and "1/3" in _trio[0].detail, \
            "一次只寫到 1 個 key 的 trio 卻沒在進度列上講 —— 那句「成功」會被讀成三個都更新了"

    def test_popped_keys_are_not_called_not_written(self, monkeypatch):
        _r = _run_refresh_writing(RS, monkeypatch)
        assert "adl_debug_msg" in _r.popped_keys
        assert "adl_debug_msg" not in _r.not_written_keys, \
            "同一個 key 同時說「沒寫到」與「刪掉了」—— 讀起來是兩件矛盾的事"


class TestTheWriteDeclarationIsReconciled:
    """★2 對帳：寫到沒宣告的 key ＝ 宣告過期，當場記成失敗。"""

    def test_an_undeclared_write_fails_the_run(self, monkeypatch):
        _r = _run_refresh_writing(RS, monkeypatch, extra=("_surprise_key",))
        _a = [_s for _s in _r.steps if _s.name == RS.STEP_WRITE_AUDIT]
        assert _a and not _a[0].ok, (
            "寫了沒宣告的 key 卻沒有被抓到 —— "
            "那份宣告會默默過期，而畫面上的「摸不到哪幾塊」建立在它上面")
        assert "_surprise_key" in _a[0].detail
        assert not _r.ok

    def test_a_clean_run_passes_the_audit(self, monkeypatch):
        _r = _run_refresh_writing(RS, monkeypatch)
        _a = [_s for _s in _r.steps if _s.name == RS.STEP_WRITE_AUDIT]
        assert _a and _a[0].ok, f"正常的一輪卻沒過對帳：{_a}"
        assert f"/{len(RS.WRITES_SESSION_KEYS)}" in _a[0].detail

    def test_writing_less_than_declared_is_not_a_failure(self, monkeypatch):
        """少寫不是錯（那叫「這一輪沒寫到」）—— 對帳只抓「超出宣告」。"""
        _r = _run_refresh_writing(RS, monkeypatch, trio_keys=())
        _a = [_s for _s in _r.steps if _s.name == RS.STEP_WRITE_AUDIT]
        assert _a and _a[0].ok
        assert "m1b_m2_info" in _r.not_written_keys


class TestMutationWrittenKeys:
    """突變：把「有更新到」改回只看 patch → 上面那些必須轉紅。"""

    def test_patch_only_would_hide_the_six_step_keys(self, monkeypatch):
        _mutant = _mutated_module(
            "src/services/macro_refresh_service.py",
            ("    _written = tuple(dict.fromkeys(_k for _ks in _writes.values() "
             "for _k in _ks))",
             "    _written = tuple(_writes.get(STEP_APPLY, ()))"))
        _r = _run_refresh_writing(_mutant, monkeypatch)
        assert "jingqi_info" not in _r.written_keys, (
            "突變體（只看 apply 的 patch）居然還是列出了 `jingqi_info` —— "
            "表示上面那些測試守的不是這一行，請修測試")
        assert "jingqi_info" in _run_refresh_writing(RS, monkeypatch).written_keys

    def test_dropping_the_reconciliation_lets_the_declaration_rot(
            self, monkeypatch):
        _mutant = _mutated_module(
            "src/services/macro_refresh_service.py",
            ("    _undeclared = tuple(_k for _k in _written "
             "if _k not in WRITES_SESSION_KEYS)",
             "    _undeclared = ()"))
        _r = _run_refresh_writing(_mutant, monkeypatch, extra=("_surprise_key",))
        assert _r.ok, "突變沒生效"
        assert not _run_refresh_writing(
            RS, monkeypatch, extra=("_surprise_key",)).ok


class TestTheReportAuditsItself:
    """報告漏收來源結論時**不得**表現成「其餘都成功」。"""

    def test_source_labels_match_the_orchestrator_jobs(self):
        """`SOURCE_LABELS` 的 key＝orchestrator 真的會跑的 job（實測，不是抄的）。"""
        _t = _code_only("src/services/macro_fetch_orchestrator.py",
                        func="fetch_macro_bundle")
        _jobs = set(re.findall(r"'(\w+)': _job_\w+", _t))
        assert _jobs == set(RS.SOURCE_LABELS), (
            f"orchestrator 的 job 集合是 {sorted(_jobs)}，"
            f"`SOURCE_LABELS` 是 {sorted(RS.SOURCE_LABELS)} —— "
            "對不上的話畫面會少講（或多講）一個來源")

    def test_a_full_report_passes_the_audit(self, monkeypatch):
        _report, _ = _run_refresh_with_fakes(
            RS, monkeypatch, df_adl=_FakeFrame(tag="adl"),
            report_jobs=tuple(RS.SOURCE_LABELS))
        _audit = [s for s in _report.steps if s.name == RS.STEP_SOURCE_AUDIT]
        assert _audit and _audit[0].ok, f"完整回報卻沒過稽核：{_audit}"

    def test_a_partial_report_is_flagged_not_silently_ok(self, monkeypatch):
        """只回報 1 個來源 → 稽核必須失敗，整份報告不得 `ok`。"""
        _report, _ = _run_refresh_with_fakes(RS, monkeypatch,
                                             df_adl=_FakeFrame(tag="adl"))
        assert not _report.ok, (
            "只收到 1/7 個來源結論，報告卻說成功 —— "
            "那就是「不知道有那幾項」被表現成「其餘都成功」")
        _audit = [s for s in _report.steps if s.name == RS.STEP_SOURCE_AUDIT]
        assert _audit and not _audit[0].ok
        assert "不完整" in _audit[0].detail


# ══════════════════════════════════════════════════════════════════
# ★1 判空：「來源回空」不得被記成成功
# ══════════════════════════════════════════════════════════════════
def _maps():
    from src.services.daily_checklist import INTL_MAP, TECH_MAP, TW_MAP
    return INTL_MAP, TW_MAP, TECH_MAP


_HEAVY_KEYS = {"inst": "inst", "margin": "margin",
               "adl": "df_adl_raw", "li": "df_li_a"}


def _content_bundle(*, intl=None, tw=None, tech=None, heavy_empty=()):
    """一份**內容**可控的 bundle。

    Args:
        intl / tw / tech: 那一桶填幾檔（`None` ＝ 填滿）。沒填到的一律是
            `None` —— 那是 `_parallel_fetch` 對失敗 / 逾時單檔的**真實寫法**
            （見 `TestTheOrchestratorReallyReturnsNones`，那支證明這不是稻草人）。
        heavy_empty: 哪幾個重桶是空的（`inst` / `margin` / `adl` / `li`）。

    ⚠️ 分母取**真正的 `*_MAP`**（服務判空時用的同一份），
    所以「填滿」在這裡的意思就是「畫面上那一桶真的是完整的」。
    """
    _i, _t, _e = _maps()

    def _fill(_m, _n):
        _n = len(_m) if _n is None else _n
        return {_k: (_FakeFrame(tag=_k) if _j < _n else None)
                for _j, _k in enumerate(_m)}

    return {
        "intl_raw": _fill(_i, intl), "tw_raw": _fill(_t, tw),
        "tech_raw": _fill(_e, tech),
        "inst": {} if "inst" in heavy_empty else {"外資及陸資": {"net": 12.3}},
        "inst_date": "2026-09-09",
        "margin": None if "margin" in heavy_empty else 3123.4,
        "df_adl_raw": None if "adl" in heavy_empty else _FakeFrame(tag="adl"),
        "df_li_a": None if "li" in heavy_empty else _FakeFrame(tag="li"),
        "adl_debug_msg": None, "elapsed_s": 12.3,
    }


def _content_run(monkeypatch, service=RS, **kw):
    """跑一輪、**所有來源結論都收得到**（把 `STEP_SOURCE_AUDIT` 排除在外）。

    ⚠️ 這一點很重要：預設的 `report_jobs=("intl",)` 本來就會讓報告失敗，
    那會讓「判空造成的紅燈」與「漏收結論造成的紅燈」分不開 ——
    測到最後守的是另一條守衛。
    """
    _b = _content_bundle(**kw)
    return _run_refresh_with_fakes(
        service, monkeypatch, df_adl=_b["df_adl_raw"],
        report_jobs=tuple(RS.SOURCE_LABELS), bundle=_b)[0]


class TestTheOrchestratorReallyReturnsNones:
    """**假設檢查**：QA 描述的那個形狀是真的（否則下面測的是不存在的病）。

    跑**真正的** `fetch_macro_bundle`（`load_heavy=False`，只有 3 個 yfinance
    job），注入一個每次都 raise 的 `fetch_single`。要證明兩件事：
      1. 它**不拋例外**、照樣回傳整包 dict，值全是 `None`；
      2. `on_job_done` 對那幾個 job 回報的是 **`ok=True`**。
    這兩件合起來就是「來源回空卻被記成成功」的成因。
    """

    def _run(self):
        from src.services.macro_fetch_orchestrator import fetch_macro_bundle
        _seen = []

        def _boom(_sym, **_kw):
            raise RuntimeError(f"injected: {_sym}")

        _b = fetch_macro_bundle(
            load_heavy=False, prev_cl_data={}, fm_token="", li_token="",
            bps_session=object(),
            intl_map={"道瓊工業 DJI": "^DJI", "那斯達克 IXIC": "^IXIC"},
            tw_map={"台股加權指數": "^TWII"}, tech_map={"台積電 ADR": "TSM"},
            fetch_single=_boom,
            fetch_institutional=lambda *a, **k: pytest.fail("不該被呼叫"),
            fetch_margin_balance=lambda *a, **k: pytest.fail("不該被呼叫"),
            fetch_adl=lambda *a, **k: pytest.fail("不該被呼叫"),
            on_job_done=lambda n, ok, d: _seen.append((n, ok)))
        return _b, _seen

    @pytest.mark.slow
    def test_every_ticker_comes_back_as_none_without_an_exception(self):
        _b, _ = self._run()
        assert _b["intl_raw"] == {"道瓊工業 DJI": None, "那斯達克 IXIC": None}, \
            "單檔失敗沒有被吞成 None —— QA 描述的形狀變了，請重看本測試"
        assert _b["tw_raw"] == {"台股加權指數": None}

    @pytest.mark.slow
    def test_and_the_progress_callback_still_says_ok(self):
        _, _seen = self._run()
        assert dict(_seen).get("intl") is True, (
            "`on_job_done` 沒有回報 ok=True —— 那本批的整個前提就不成立了")
        assert all(_ok for _n, _ok in _seen), \
            "全部 job 都該回報成功（它們確實沒有以例外收場）"


class TestEmptySourcesAreNotSuccess:
    """★1 正向：全空 → 紅燈，而且**列得出哪幾桶空**。"""

    def test_all_three_ticker_buckets_empty_is_error(self, monkeypatch):
        _r = _content_run(monkeypatch, intl=0, tw=0, tech=0)
        assert not _r.ok, "7 個 job 都回報成功、3 桶卻一筆資料都沒有 —— 不准算成功"
        assert P.refresh_status_state(_r) == "error", \
            "`st.status` 收綠燈 ＝ 拿沒有資料的畫面當今天的結論（§1）"

    def test_it_names_which_buckets_are_empty(self, monkeypatch):
        _r = _content_run(monkeypatch, intl=0, tw=0, tech=0)
        _blob = " ".join(_r.empties)
        for _k in ("intl", "tw", "tech"):
            assert RS.SOURCE_LABELS[_k] in _blob, \
                f"沒講「{_k} 這一桶是空的」—— 使用者不知道哪一塊是舊值"
        assert RS.SOURCE_LABELS["inst"] not in _blob, \
            "把有資料的桶也列成空的 —— 那是往另一個方向說謊"
        assert "0/5" in _blob and "0/2" in _blob and "0/7" in _blob, \
            "沒有 `N/M`：看不出來是「全空」還是「少一檔」"

    def test_the_failure_list_also_carries_it(self, monkeypatch):
        """紅燈的來源要在 `failures` 裡（畫面那段紅字讀的是它）。"""
        _r = _content_run(monkeypatch, intl=0, tw=0, tech=0)
        _blob = " ".join(_r.failures)
        assert RS.STEP_LABELS[RS.STEP_CONTENT_AUDIT] in _blob
        assert "全空 3 桶" in _blob

    def test_every_bucket_can_be_detected_empty(self, monkeypatch):
        """七桶都要判得出來 —— 少判一桶就是少一個看得見的洞。"""
        _r = _content_run(monkeypatch, intl=0, tw=0, tech=0,
                          heavy_empty=("inst", "margin", "adl", "li"))
        assert {_c.name for _c in _r.contents if _c.empty} == set(RS.SOURCE_LABELS)

    def test_the_source_result_still_says_ok(self, monkeypatch):
        """對照組：來源**結論**照樣是 ✅ —— 這正是為什麼要另外判空。"""
        _r = _content_run(monkeypatch, intl=0, tw=0, tech=0)
        assert all(_s.ok for _s in _r.sources), \
            "這一輪的 `on_job_done` 全部回報成功（本測試的前提）"
        assert not _r.ok, "而報告仍然必須是失敗的"


class TestPartialSourcesAreNeitherGreenNorRed:
    """★1 分寸：4 檔拿到 2 檔 —— 不准標全綠，也不准整桶標失敗。"""

    def test_a_half_filled_bucket_is_not_a_failure(self, monkeypatch):
        _r = _content_run(monkeypatch, intl=2)
        assert _r.ok, "兩檔有值卻整桶標失敗 —— 那是把「一半」講成「什麼都沒有」"
        assert not _r.empties, "部分空不得混進「全空」清單"

    def test_but_it_is_not_clean_either(self, monkeypatch):
        _r = _content_run(monkeypatch, intl=2)
        assert _r.partials, "部分空必須自己列得出來"
        assert P.refresh_status_state(_r) == "error", \
            "只拿到一半卻收綠燈 —— 使用者無從分辨哪幾格是舊的"

    def test_it_shows_the_n_over_m_shape(self, monkeypatch):
        _r = _content_run(monkeypatch, intl=2)
        _i, _, _ = _maps()
        assert f"2/{len(_i)}" in " ".join(_r.partials), \
            "沒有「2/5」這種形狀就分不出「拿到一半」與「全拿到」"

    def test_it_names_the_missing_ones(self, monkeypatch):
        _r = _content_run(monkeypatch, intl=2)
        _i, _, _ = _maps()
        _blob = " ".join(_r.partials)
        assert list(_i)[-1] in _blob, "沒講缺哪幾檔"
        assert list(_i)[0] not in _blob, "把拿到的那幾檔也講成缺 —— 反了"


class TestAGoodRunIsStillGreen:
    """★1 反向：真的有拿到資料時**必須**仍然是綠燈（不准為了誠實而全標失敗）。"""

    def test_a_full_run_is_complete(self, monkeypatch):
        _r = _content_run(monkeypatch)
        assert _r.ok and not _r.empties and not _r.partials
        assert P.refresh_status_state(_r) == "complete", (
            "全部拿到了卻不給綠燈 —— 那會讓紅燈失去意義"
            "（滿版假警報 ＝ 真的出事時沒人看得見，v3 §02）")

    def test_every_bucket_reads_full(self, monkeypatch):
        _r = _content_run(monkeypatch)
        assert {_c.name for _c in _r.contents} == set(RS.SOURCE_LABELS)
        assert all(_c.filled == _c.total for _c in _r.contents)

    def test_the_audit_step_is_a_pass(self, monkeypatch):
        _r = _content_run(monkeypatch)
        _a = [_s for _s in _r.steps if _s.name == RS.STEP_CONTENT_AUDIT]
        assert _a and _a[0].ok and not _a[0].partial
        assert "7/7 桶完整" in _a[0].detail


class TestContentAuditIsPure:
    """`audit_source_contents` 的邊界（純函式，不必跑整輪）。"""

    def test_a_scalar_zero_is_data_not_a_hole(self):
        """`0.0` 是一個合法的數值 —— 判成「沒資料」等於自己發明規則。"""
        _c = {_x.name: _x for _x in RS.audit_source_contents(
            {"margin": 0.0}, intl_map={}, tw_map={}, tech_map={})}
        assert _c["margin"].filled == 1

    def test_an_empty_frame_is_a_hole(self):
        _c = {_x.name: _x for _x in RS.audit_source_contents(
            {"df_adl_raw": _FakeFrame(empty=True)},
            intl_map={}, tw_map={}, tech_map={})}
        assert _c["adl"].empty, "空 DataFrame 是「沒資料」，不是「有一份表」"

    def test_a_missing_bundle_key_is_a_hole(self):
        _c = RS.audit_source_contents({}, intl_map={"a": 1}, tw_map={},
                                      tech_map={})
        assert all(_x.empty for _x in _c)

    def test_the_denominator_comes_from_the_map_not_the_result(self):
        """整個 job 失敗時回傳是 `{}` —— 拿它當分母會算出「0/0」。"""
        _c = {_x.name: _x for _x in RS.audit_source_contents(
            {"intl_raw": {}}, intl_map={"a": 1, "b": 2}, tw_map={},
            tech_map={})}
        assert _c["intl"].total == 2 and _c["intl"].text.startswith("0/2")

    def test_it_touches_no_session(self):
        """純函式：不得碰 streamlit / session（`refresh_macro_now` 才碰）。"""
        _t = _code_only("src/services/macro_refresh_service.py",
                        func="audit_source_contents")
        assert "session_state" not in _t and "st." not in _t


class TestMutationContentAudit:
    """突變：把判空拔掉 / 放寬 → 上面那些必須轉紅。"""

    _SCENARIO = dict(intl=0, tw=0, tech=0)

    @pytest.mark.parametrize("old,new,why", [
        ("        _contents = audit_source_contents(\n"
         "            _bundle, intl_map=INTL_MAP, tw_map=TW_MAP, tech_map=TECH_MAP)",
         "        _contents = ()", "整段判空被拔掉"),
        ("        _step(STEP_CONTENT_AUDIT,\n              not _empty_c,",
         "        _step(STEP_CONTENT_AUDIT,\n              True,",
         "判空還在，但結論永遠是成功"),
        ("    if value is None:\n        return False",
         "    if value is None:\n        return True",
         "`None` 被當成有資料"),
    ])
    def test_a_run_with_nothing_in_it_would_go_green(self, monkeypatch,
                                                     old, new, why):
        _mutant = _mutated_module("src/services/macro_refresh_service.py",
                                  (old, new))
        _r = _content_run(monkeypatch, service=_mutant, **self._SCENARIO)
        assert P.refresh_status_state(_r) == "complete", (
            f"突變體（{why}）居然沒有把「全空」畫成 complete —— "
            "表示上面那些測試守的不是這一段，請修測試")
        assert P.refresh_status_state(
            _content_run(monkeypatch, **self._SCENARIO)) == "error"

    def test_dropping_the_partial_flag_would_tick_the_progress_line(
            self, monkeypatch):
        """守的是**進度列的圖示**那一條（`st.status` 收尾另有 `partials` 守）。"""
        _mutant = _mutated_module(
            "src/services/macro_refresh_service.py",
            ("              partial=bool(_part_c))", "              partial=False)"))
        _r = _content_run(monkeypatch, service=_mutant, intl=2)
        _a = [_s for _s in _r.steps if _s.name == RS.STEP_CONTENT_AUDIT]
        assert _a and not _a[0].partial, "突變沒生效"
        assert P._event_icon(_a[0]) == "✅", (
            "突變體的進度列還是沒給 ✅ —— 表示 `_event_icon` 看的不是 `partial`")
        _real = [_s for _s in _content_run(monkeypatch, intl=2).steps
                 if _s.name == RS.STEP_CONTENT_AUDIT]
        assert P._event_icon(_real[0]) == "⚠️", \
            "真版的進度列必須看得出「只拿到一部分」"


class TestAStaleReportDoesNotBlankThePage:
    """熱重載後 session 留著舊格式的報告 → 要變成紅字，不是整頁空白。"""

    class _StaleReport:
        """少了新版會讀的欄位（模擬熱重載後留在 session 的舊物件）。"""

        mode = "warm"

    def test_the_renderer_itself_really_does_blow_up_on_it(self):
        """假設檢查：這個替身真的會炸 —— 否則下一支測的是一個不存在的病。"""
        with pytest.raises(AttributeError):
            P._render_refresh_report(self._StaleReport())

    @pytest.mark.slow
    def test_the_page_survives_it_end_to_end(self):
        """端到端：整頁還是畫得出來（不是空白），而且有紅字。"""
        from streamlit.testing.v1 import AppTest
        _probe = _ROOT / "tests" / "_p01_stale_report_probe.py"
        _probe.write_text(
            "import streamlit as st\n"
            "from src.ui.views.page_today import render_page_today, SS_REFRESH_REPORT\n"
            "class _Stale:\n"
            "    mode = 'warm'\n"
            "st.session_state[SS_REFRESH_REPORT] = _Stale()\n"
            "render_page_today()\n", encoding="utf-8")
        try:
            _at = AppTest.from_file(str(_probe), default_timeout=120)
            _at.run()
            assert not _at.exception, f"整頁炸了（＝空白畫面）：{_at.exception}"
            assert len(_at.markdown) > 20, "頁面內容大量消失 —— 半截死頁"
            assert any("畫不出來" in _e.value for _e in _at.error), \
                "舊格式報告被靜默略過了 —— 使用者不知道剛剛那份報告去哪了"
            assert "_p01_refresh_report" not in _at.session_state, \
                "壞掉的報告沒有被清掉 —— 下一輪還會再炸一次"
        finally:
            _probe.unlink(missing_ok=True)


class TestModeMappingMatchesTheService:
    """頁面那份**字面**模式對映與 L3 常數不得漂開（守衛 1/2）。"""

    def test_every_value_is_a_real_service_mode(self):
        assert set(P.UPDATE_MODE_TO_REFRESH_MODE.values()) == \
            {RS.MODE_WARM, RS.MODE_FORCE}

    def test_every_radio_option_is_mapped(self):
        from src.ui.tabs.tab_today import MODE_LABELS
        assert set(MODE_LABELS) == set(P.UPDATE_MODE_TO_REFRESH_MODE), (
            "radio 上的模式與對映表對不起來 —— "
            "沒對映到的那個模式按下去會炸（這是刻意的，但表要補）")

    def test_force_maps_to_force_and_warm_to_warm(self):
        from src.ui.tabs.tab_today import MODE_FORCE, MODE_WARM
        assert P.UPDATE_MODE_TO_REFRESH_MODE[MODE_FORCE] == RS.MODE_FORCE
        assert P.UPDATE_MODE_TO_REFRESH_MODE[MODE_WARM] == RS.MODE_WARM


# ══════════════════════════════════════════════════════════════════
# 文案不得說謊：不寫秒數、不說「請重試」
# ══════════════════════════════════════════════════════════════════
class TestFailureCopyDoesNotSayRetry:
    """失敗的取數結果會被快取 ⇒ 「請重試」是一句會讓人白按的假指路。"""

    @pytest.mark.parametrize("banned", ["請重試", "請再試一次", "再按一次試試",
                                        "稍後重試", "請重新整理"])
    def test_the_banned_phrases_are_absent(self, banned):
        assert banned not in P.REFRESH_FAILED_WHAT_NOW
        assert banned not in P.EXIT_RETRY_HERE

    def test_it_points_at_the_only_thing_that_bypasses_the_cache(self):
        assert "強制重抓" in P.REFRESH_FAILED_WHAT_NOW
        assert "快取" in P.REFRESH_FAILED_WHAT_NOW

    def test_it_says_the_stale_cells_are_stale(self):
        assert "上一輪" in P.REFRESH_FAILED_WHAT_NOW, (
            "沒講「沒更新到的那幾格顯示的是上一輪的值」—— "
            "使用者會把舊值當成今天的")


class TestNoHardcodedSecondsInPageCopy:
    """動工條件 ⑥：頁1 文案不准寫死秒數（沒有守衛在守那個數字）。"""

    #: 「宣告一個時間上界」的寫法。**排除** f-string 裡的執行期量測值。
    _BOUND = re.compile(r"(最長|約|上限|大約|預估)\s*\d+\s*(秒|分鐘)"
                        r"|\d+\s*[~～-]\s*\d+\s*秒")

    def test_the_page_declares_no_second_bound(self):
        _hits = [_l for _l in _src("src/ui/views/page_today.py").splitlines()
                 if self._BOUND.search(_l)]
        assert not _hits, (
            f"頁1 出現寫死的秒數上界：{_hits} —— "
            "`tests/test_p0a_key_alerts_and_spinner.py` 的上界守衛只涵蓋 "
            "`tab_macro`，這裡寫的數字沒有人在守，下一次有人調 timeout "
            "它就默默變成謊話。要嘛不寫，要嘛把那支守衛推廣過來。")

    def test_it_still_separates_warm_from_cold(self):
        """不寫秒數不等於什麼都不講 —— 體感差很多，要分開講。"""
        _blob = P.REFRESH_RUNNING_LABEL + P.REFRESH_SPEED_HINT
        assert "暖快取" in _blob and "冷啟動" in _blob

    def test_the_report_shows_the_measured_seconds(self):
        """真實耗時要顯示（那是量到的，不是宣告的）。"""
        assert "elapsed_s" in _src("src/ui/views/page_today.py")


# ══════════════════════════════════════════════════════════════════
# 逾時包裝不得 join
# ══════════════════════════════════════════════════════════════════
class TestTimeoutWrapperDoesNotJoin:
    """`with ThreadPoolExecutor(...)` 的 `__exit__` 會 join ⇒ timeout 形同不存在。"""

    def _fn_src(self) -> str:
        # ⚠️ code-only：本函式的 docstring 逐字寫著「不得寫成
        # `with ThreadPoolExecutor(...) as ex:`」，grep 原始碼會被它騙。
        return _code_only("src/services/macro_refresh_service.py",
                          func="_run_with_timeout")

    def test_it_uses_try_finally_not_a_with_block(self):
        _f = self._fn_src()
        assert "with ThreadPoolExecutor" not in _f, (
            "改成 `with TPE` 了 —— `__exit__` 會等那條卡住的 thread 跑完，"
            "`timeout=` 於是形同不存在（macro_fetch_orchestrator 記載過這個坑）")
        assert "finally:" in _f and "shutdown(wait=False, cancel_futures=True)" in _f

    def test_it_really_times_out(self):
        import time as _time
        with pytest.raises(Exception) as _e:
            RS._run_with_timeout(lambda: _time.sleep(5), timeout_s=1)
        assert "Timeout" in type(_e.value).__name__

    def test_it_returns_fast_when_the_worker_hangs(self):
        """逾時就要**準時回來**，不能被卡住的 worker 拖著。"""
        import time as _time
        _t0 = _time.time()
        with pytest.raises(Exception):
            RS._run_with_timeout(lambda: _time.sleep(8), timeout_s=1)
        assert _time.time() - _t0 < 4, "逾時之後還在等 worker —— 那就是被 join 了"

    def test_the_market_step_is_the_one_wrapped(self):
        _t = _code_only("src/services/macro_refresh_service.py",
                        func="refresh_macro_now")
        assert re.search(
            r"_run_with_timeout\(lambda: compute_and_apply_market_assessment",
            _t), "市場評估沒有被包進逾時 —— 它的備援分支會真的打 yfinance"
        assert "timeout_s=_MARKET_ASSESS_TIMEOUT_S" in _t, \
            "逾時值沒有從 SSOT 常數帶進去"


# ══════════════════════════════════════════════════════════════════
# 本階段的硬範圍
# ══════════════════════════════════════════════════════════════════
class TestStageOneBoundaries:
    """客戶明令：舊 7 頁籤保留原樣 ⇒ 本批不得碰 `src/ui/tabs/**` 的行為。"""

    _NEW_FILES = ("src/compute/macro/macro_session_patch.py",
                  "src/services/macro_session_apply.py",
                  "src/services/macro_refresh_service.py")

    @pytest.mark.parametrize("rel", _NEW_FILES)
    def test_the_new_files_do_not_import_the_old_tabs(self, rel):
        _tree = ast.parse(_src(rel))
        for _n in ast.walk(_tree):
            _mod = (_n.module if isinstance(_n, ast.ImportFrom) else None)
            _names = ([a.name for a in _n.names] if isinstance(_n, ast.Import)
                      else [])
            for _m in [_mod, *_names]:
                assert not (_m or "").startswith("src.ui."), (
                    f"{rel} import 了 {_m} —— L3 不得依賴 L5（§8.2 硬規則）")

    @pytest.mark.parametrize("rel", _NEW_FILES)
    def test_the_new_files_never_write_macro_alerts(self, rel):
        """動工條件 ②：`macro_alerts` 的唯一寫入者必須還是 `section_mid.py`。"""
        assert not re.search(r"session_state\[['\"]macro_alerts['\"]\]\s*=",
                             _code_only(rel)), (
            f"{rel} 寫了 macro_alerts —— "
            "`test_p0a_key_alerts_and_spinner.py::"
            "test_section_mid_is_still_the_only_writer` 會紅")

    @pytest.mark.parametrize("rel", _NEW_FILES + ("src/ui/views/page_today.py",))
    def test_no_second_throttle_implementation(self, rel):
        """動工條件 ③：throttle / 13-key warroom 契約不得在本批長出第二份。"""
        _t = _code_only(rel)
        assert "compute_position_throttle" not in _t, (
            f"{rel} 自己算了 throttle —— SSOT 在 `section_traffic_light.py`，"
            "`tests/test_position_throttle_ssot.py` 以字串釘住")
        assert not re.search(r"session_state\[['\"]warroom_summary['\"]\]\s*=", _t)

    def test_the_page_still_does_not_fetch_by_itself(self):
        """v3 §01「UI 純畫面調用」：取數一律走 L3，頁面自己不寫一行。

        ⚠️ code-only：檔頭的分層宣告本來就會提到 `requests` / `yfinance`
        （它在**否認**自己有那些東西）。看註解會把否認句判成違規。
        """
        _t = _code_only("src/ui/views/page_today.py")
        for _banned in ("requests", "yfinance", "read_csv", "FinMind",
                        "cache_data", "cache_resource"):
            assert _banned not in _t, \
                f"頁1 的 code 裡出現 {_banned} —— UI 層不得自己取數 / 自建 cache"

    def test_the_refresh_service_is_late_imported(self):
        """它會拉 `src.compute.macro` eager barrel ⇒ 不准擺在 module level。"""
        _tree = ast.parse(_src("src/ui/views/page_today.py"))
        for _n in _tree.body:                       # 只看 module level
            if isinstance(_n, ast.ImportFrom):
                assert "macro_refresh_service" not in (_n.module or ""), (
                    "`macro_refresh_service` 被搬到 module level import 了 —— "
                    "那會把 `src.compute.macro` barrel 一起拉進來，"
                    "又接回 FE-7 消掉的「不相干模組壞掉 ⇒ 整頁空白」")
