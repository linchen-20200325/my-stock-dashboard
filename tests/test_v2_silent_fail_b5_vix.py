"""批次 5：「💼 我的持股」VIX 卡 `hold.vix` —— 「抓不到」不得畫成灰卡「這是一個有效的結果」。

（客戶 2026-09-26：⛔ 只修這一張卡；其他卡／其他 caller 的輸出一律不動；⛔ 不新造文案；⛔ 不動版面。）

根因（兩段，都在本卡的取數線上）：
  1. L3 `dividend_station_service.fetch_vix()` 的契約是「**抓不到** → `None`」。`None` 只有這一個
     意思 —— 休市也拿得到最後一根收盤（底層抓 2 年、切 6 個月），「還沒去要」由頁面自己的
     gate 管。而 L1 `macro_core.fetch_yf_close` 一切抓取失敗都回**空 Series、不拋**，所以
     實際上的失敗（proxy／429／JSON 壞）全部以 `None` 抵達 L5。
     L5 `build_vix_card` 卻把 `None` 畫成 `UI_EMPTY`「**這一輪拿不到 VIX**／**這是一個有效的結果**」
     （#7 灰，「稍後再試」）—— 主因。
  2. `fetch_vix()` 另外 `except Exception` 吞掉一切例外並回 `None` —— 程式／部署層的錯
     （如 late import 失敗）也被併成「抓不到」。

修法：
  · L3：`fetch_vix(*, strict=False)`（同 PR #693 `get_switch_in_candidates(strict=)`）。
    strict=True 只做一件事：**例外不吞**；「抓不到」仍回 `None`。預設路徑一字不變
    （`get_station_rows` → v1 ETF 戰情室分頁／每日推播腳本／v2 戰情表都不傳 strict）。
  · L5：`load_vix` 呼叫 `fetch_vix(strict=True)`；回 `None`（或非數字）→ `VixReadout.fetch_failed`
    → `build_vix_card` 以 L0 `MISS_FETCH_FAILED` 升紅（`VIX_FAILED_NOW`）。文字全部沿用既有的：
    why ＝ L0 `MISS_TEXT[MISS_NO_INPUT]`（摘掉「這盞燈」）、where ＝ 本卡原本 empty 分支的重試句
    （上提成 `VIX_RETRY_WHERE`，一字未改）。例外那一則（既有）原文不動。

每條失敗路徑三件事（同批次 1～4）：
  (a) 上游失敗 → 紅卡 `VIX_FAILED_NOW`；⛔ 不得是灰卡 `VIX_EMPTY_NOW`／「有效的結果」；
  (b) 真的有值／沒按鈕 → 原封不動；其他卡、其他 caller 的輸出一字不變；
  (c) 突變：拿掉本批新加的任一條 → (a) 或 (b) 必須失敗。
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import pathlib
import sys
import types

import pandas as pd
import pytest

import src.data.macro.macro_core as MC
import src.services.dividend_station_service as S
from shared import dividend_station_thresholds as T
from shared import ia_nav
from shared.station_specs import MISS_NO_INPUT, MISS_TEXT
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_IDLE, UI_LIVE
from src.ui.views import page_hold as PH

_REPO = pathlib.Path(__file__).resolve().parents[1]
_VALID = "有效的結果"
#: 本批「抓不到」的 why（摘自 L0 `MISS_TEXT[MISS_NO_INPUT]`，只刪開頭主詞）。
_NO_CLOSE_WHY = MISS_TEXT[MISS_NO_INPUT].removeprefix("這盞燈")
#: 既有「例外」那一則的 where 開頭（本批⛔ 不動）。
_EXC_WHERE_HEAD = f"{PH.NO_EXIT_MARKER} —— 這不是取數失敗"
_SUBMITTED = PH.HoldRequest(submitted=True)


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    """把 `mod` 的原始碼裡每一組 `old` **恰好一處**換成 `new`，載成一個獨立的新模組。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_b5_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


# ── L1 替身：`fetch_yf_close` 的各種回法（L3 是在呼叫當下 late import，換模組屬性即生效）──
def _series(*vals: float) -> pd.Series:
    return pd.Series(list(vals), index=pd.date_range("2026-09-01", periods=len(vals), freq="B"),
                     dtype=float, name="^VIX")


_UPSTREAM_MISSING = {
    "none": lambda *_a, **_k: None,
    "empty": lambda *_a, **_k: pd.Series(dtype=float, name="^VIX"),
    "all_nan": lambda *_a, **_k: _series(float("nan"), float("nan")),
}


def _raises(*_a, **_k):
    raise RuntimeError("yf contract broken")


@pytest.fixture
def yf(monkeypatch):
    """把 L1 `fetch_yf_close` 換成指定的替身；回傳呼叫次數計數器。"""
    calls = {"n": 0}

    def _use(fn):
        def _wrapped(*a, **k):
            calls["n"] += 1
            return fn(*a, **k)
        monkeypatch.setattr(MC, "fetch_yf_close", _wrapped)
        return calls
    return _use


def _card(P, readout):
    return P.build_vix_card(readout)


# ══════════════════════════════════════════════════════════════════
# 根因釘住：`None` 只有「抓不到」一個意思；L1 失敗是空 Series、不拋
# ══════════════════════════════════════════════════════════════════
class TestRootCause:
    def test_a_real_l1_network_failure_arrives_as_none_not_an_exception(self, monkeypatch):
        """真的走 L1 `fetch_yf_close` → `_fetch_yf_close_base`：`fetch_url` 失敗回 None。"""
        monkeypatch.setattr(MC, "_YF_CLOSE_CACHE", {})
        monkeypatch.setattr(MC, "fetch_url", lambda *_a, **_k: None)
        assert MC.fetch_yf_close("^VIX", range_="6mo").empty, "L1 契約：失敗回空序列、不拋"
        assert S.fetch_vix() is None
        assert S.fetch_vix(strict=True) is None, "strict 也不把「抓不到」變成例外"

    def test_a_real_l1_failure_turns_the_card_red(self, monkeypatch):
        monkeypatch.setattr(MC, "_YF_CLOSE_CACHE", {})
        monkeypatch.setattr(MC, "fetch_url", lambda *_a, **_k: None)
        card = _card(PH, PH.load_vix(_SUBMITTED))[0]
        assert card.state == UI_FAILED and card.note.now == PH.VIX_FAILED_NOW
        assert _VALID not in card.note.why

    def test_a_closed_market_still_has_a_last_close(self, yf):
        """休市／假日不是 `None` 的另一個意思：序列最後一根就是最近的收盤。"""
        yf(lambda *_a, **_k: _series(15.0, 16.5))      # 最後一根是上週五也一樣
        assert S.fetch_vix() == pytest.approx(16.5)
        assert S.fetch_vix(strict=True) == pytest.approx(16.5)


# ══════════════════════════════════════════════════════════════════
# L3 `fetch_vix(strict=)` —— 預設路徑一字不變；strict 只讓例外穿過
# ══════════════════════════════════════════════════════════════════
class TestL3:
    def test_b_default_still_swallows_and_logs_the_same_line(self, yf, capsys):
        yf(_raises)
        assert S.fetch_vix() is None
        assert capsys.readouterr().out == (
            "[dividend_station] VIX 抓取失敗: RuntimeError: yf contract broken\n")

    def test_a_strict_lets_the_exception_through_without_the_log(self, yf, capsys):
        yf(_raises)
        with pytest.raises(RuntimeError, match="yf contract broken"):
            S.fetch_vix(strict=True)
        assert "VIX 抓取失敗" not in capsys.readouterr().out

    @pytest.mark.parametrize("kind", sorted(_UPSTREAM_MISSING))
    @pytest.mark.parametrize("strict", [False, True])
    def test_missing_close_is_none_in_both_modes(self, yf, capsys, kind, strict):
        yf(_UPSTREAM_MISSING[kind])
        assert S.fetch_vix(strict=strict) is None
        assert capsys.readouterr().out == "", "沒有例外就沒有那行 log（修前也是）"

    @pytest.mark.parametrize("strict", [False, True])
    def test_b_a_genuine_value_is_the_last_non_nan_close(self, yf, strict):
        calls = yf(lambda *_a, **_k: _series(15.0, 17.2, float("nan")))
        assert S.fetch_vix(strict=strict) == pytest.approx(17.2)
        assert calls["n"] == 1

    def test_b_same_upstream_call_in_both_modes(self, monkeypatch):
        seen = []
        monkeypatch.setattr(MC, "fetch_yf_close",
                            lambda *a, **k: seen.append((a, k)) or _series(18.0))
        S.fetch_vix()
        S.fetch_vix(strict=True)
        assert seen == [(("^VIX",), {"range_": "6mo"})] * 2

    def test_b_strict_is_keyword_only(self):
        with pytest.raises(TypeError):
            S.fetch_vix(True)      # noqa: FBT003 —— 位置參數 ⛔（舊 caller 的呼叫形狀不變）

    @pytest.mark.parametrize("upstream,expected", [
        (_raises, None), (_UPSTREAM_MISSING["empty"], None),
        (lambda *_a, **_k: _series(21.5), 21.5)])
    def test_b_get_station_rows_the_other_callers_entry_is_unchanged(self, yf, upstream,
                                                                     expected):
        """v1 ETF 戰情室分頁／每日推播腳本／v2 戰情表都經 `get_station_rows` → 非 strict。"""
        yf(upstream)
        rows, vix = S.get_station_rows([])
        assert rows == [] and vix == expected


class TestCallSites:
    """全 repo 的 `fetch_vix(...)` 呼叫：只有 v2 VIX 卡傳 strict=True，其餘不傳任何參數。"""

    @staticmethod
    def _calls():
        out = []
        for base in ("src", "scripts", "app.py"):
            p = _REPO / base
            files = [p] if p.is_file() else sorted(p.rglob("*.py"))
            for f in files:
                tree = ast.parse(f.read_text(encoding="utf-8"))
                for n in ast.walk(tree):
                    if isinstance(n, ast.Call):
                        fn = n.func
                        name = (fn.id if isinstance(fn, ast.Name) else
                                fn.attr if isinstance(fn, ast.Attribute) else "")
                        if name == "fetch_vix":
                            out.append((str(f.relative_to(_REPO)), n.args,
                                        {k.arg: getattr(k.value, "value", k.value)
                                         for k in n.keywords}))
        return out

    def test_only_the_v2_vix_card_asks_for_strict(self):
        calls = self._calls()
        strict = [(f, kw) for f, _a, kw in calls if kw]
        assert strict == [("src/ui/views/page_hold.py", {"strict": True})]
        plain = sorted(f for f, a, kw in calls if not kw and not a)
        assert plain == ["src/services/dividend_station_service.py"], (
            "get_station_rows 那一處仍是無參數呼叫")
        assert len(calls) == 2


# ══════════════════════════════════════════════════════════════════
# (a) 上游失敗 → 紅
# ══════════════════════════════════════════════════════════════════
class TestFetchFailureIsRed:
    @pytest.mark.parametrize("kind", sorted(_UPSTREAM_MISSING))
    def test_a_missing_close_is_red_not_a_valid_empty(self, yf, kind):
        yf(_UPSTREAM_MISSING[kind])
        r = PH.load_vix(_SUBMITTED)
        assert (r.requested, r.vix, r.error, r.fetch_failed) == (True, None, "", True)
        built = _card(PH, r)
        card = built[0]
        assert card.state == UI_FAILED and card.state != UI_EMPTY
        assert card.note.now == PH.VIX_FAILED_NOW and card.note.now != PH.VIX_EMPTY_NOW
        assert card.note.why == _NO_CLOSE_WHY
        assert card.note.where == PH.VIX_RETRY_WHERE
        assert _VALID not in card.note.why and card.value == ""
        html = PH.v2_card_html(*built)
        assert PH.VIX_EMPTY_NOW.strip("*") not in html
        assert PH.VIX_FAILED_NOW.strip("*") in html

    def test_a_face_rows_are_existing_excerpts(self, yf):
        yf(_UPSTREAM_MISSING["empty"])
        face = dict(PH.v2_short_rows(_card(PH, PH.load_vix(_SUBMITTED))[0])[0])
        assert face[PH.V2_WHY_FACT_KEY] == "需要的數字沒抓到 —— 通常是上游來源這輪失敗"
        assert face[PH.V2_GUIDE_FACT_KEY] == (
            "稍後" + PH.press(PH.ACTION_RUN_WARROOM_LABEL) + "再試一次")

    def test_a_the_exception_path_does_not_say_it_is_a_fetch_failure_retry(self, yf):
        """L3 例外（strict 不再吞）→ 既有那一則紅卡：例外原文看得見、指路是回報維護者。"""
        yf(_raises)
        r = PH.load_vix(_SUBMITTED)
        assert r.error and "yf contract broken" in r.error and r.fetch_failed is False
        card = _card(PH, r)[0]
        assert card.state == UI_FAILED and card.note.now == PH.VIX_FAILED_NOW
        assert card.note.why == PH._error_why(PH.SRC_VIX, r.error)
        assert "yf contract broken" in card.note.why
        assert card.note.where.startswith(_EXC_WHERE_HEAD)
        face = dict(PH.v2_short_rows(card)[0])
        assert face[PH.V2_WHY_FACT_KEY] == PH._v2_raised(PH.SRC_VIX)

    def test_a_non_numeric_from_l3_is_not_a_valid_empty_either(self, monkeypatch):
        """L3 若回了 NaN（契約外）→ `_num()` 之後沒有值 → 同樣是紅，⛔ 不落到灰卡。"""
        monkeypatch.setattr(S, "fetch_vix", lambda **_k: float("nan"))
        r = PH.load_vix(_SUBMITTED)
        assert r.vix is None and r.fetch_failed is True
        assert _card(PH, r)[0].state == UI_FAILED

    def test_a_the_page_asks_l3_to_be_strict(self, monkeypatch):
        seen = []
        monkeypatch.setattr(S, "fetch_vix", lambda **k: seen.append(k) or 18.0)
        PH.load_vix(_SUBMITTED)
        assert seen == [{"strict": True}]

    def test_a_the_p04_enumeration_really_produces_this_note(self):
        """`test_p04_hold_v2_cards._enumerate()` 的短句／摘錄／摺疊區窮舉**真的走到**本批這一則。

        沒有這一條，拿掉 test_p04 那一個 `fetch_failed=True` 案例仍全綠（`(key, now)` 已被例外那一則
        佔住，死列檢查看不出來）—— 本批這一則就從 test_p04 的逐則檢查裡消失。
        """
        from tests import test_p04_hold_v2_cards as E

        assert ("hold.vix", PH.VIX_FAILED_NOW, _NO_CLOSE_WHY, PH.VIX_RETRY_WHERE) in E._NOTES

    def test_a_retry_where_is_the_old_empty_where_verbatim(self):
        """上提成常數時一字未改：用同一組原料重組一次，逐字相等。"""
        assert PH.VIX_RETRY_WHERE == (
            f"稍後{PH.press(PH.ACTION_RUN_WARROOM_LABEL)}再試一次；"
            "持續拿不到請到"
            f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"
            "看 Yahoo 那一源的狀態")


# ══════════════════════════════════════════════════════════════════
# (b) 真的有值／沒按鈕／直接構造的空讀數 → 原封不動
# ══════════════════════════════════════════════════════════════════
#: 把本批的判定整段中和掉（＝本批之前的行為）。
_REVERT_B5 = (
    ("_v = fetch_vix(strict=True)", "_v = fetch_vix()"),
    ("return VixReadout(requested=True, vix=_vx, fetch_failed=_vx is None)",
     "return VixReadout(requested=True, vix=_vx)"),
    ("        has_value=(vix.vix is not None),\n"
     "        reason=MISS_FETCH_FAILED if vix.fetch_failed else \"\")",
     "        has_value=(vix.vix is not None))"),
)


def _fp(P, built) -> str:
    card, facts, sig = built
    return repr((card, tuple(facts), sig)) + P.v2_card_html(card, facts, sig)


class TestUnchanged:
    def test_b_a_genuine_value_is_live_and_byte_identical(self, yf):
        yf(lambda *_a, **_k: _series(15.0, 17.2))
        old = _mutant(PH, *_REVERT_B5)
        new_b = _card(PH, PH.load_vix(_SUBMITTED))
        old_b = _card(old, old.load_vix(old.HoldRequest(submitted=True)))
        assert new_b[0].state == UI_LIVE and new_b[0].value == "17.20"
        assert _fp(PH, new_b) == _fp(old, old_b)

    def test_b_not_requested_is_idle_byte_identical_and_touches_nothing(self, yf):
        calls = yf(_raises)
        old = _mutant(PH, *_REVERT_B5)
        r = PH.load_vix(PH.HoldRequest(submitted=False))
        assert r == PH.VixReadout(requested=False) and calls["n"] == 0
        new_b = _card(PH, r)
        assert new_b[0].state == UI_IDLE and new_b[0].note.now == PH.IDLE_NOW
        assert _fp(PH, new_b) == _fp(old, _card(old, old.VixReadout(requested=False)))

    @pytest.mark.parametrize("kw", [
        {"requested": True},                                   # 直接構造的空讀數（既有契約）
        {"requested": True, "error": "ImportError('x')"},       # late import 失敗（既有那一則）
        {"requested": True, "vix": 31.0}])
    def test_b_readouts_without_the_new_flag_render_as_before(self, kw):
        old = _mutant(PH, *_REVERT_B5)
        assert _fp(PH, _card(PH, PH.VixReadout(**kw))) == _fp(old, _card(old, old.VixReadout(**kw)))

    def test_b_the_directly_built_empty_readout_is_still_the_grey_empty(self):
        card = _card(PH, PH.VixReadout(requested=True, vix=None))[0]
        assert card.state == UI_EMPTY and card.note.now == PH.VIX_EMPTY_NOW
        assert card.note.where == PH.VIX_RETRY_WHERE

    def test_b_late_import_failure_keeps_its_own_note(self, monkeypatch):
        """頁面自己 late import L3 失敗 → 既有那一則（⛔ 不被本批的重試句取代）。"""
        monkeypatch.setitem(sys.modules, "src.services.dividend_station_service", None)
        r = PH.load_vix(_SUBMITTED)
        assert r.error and r.fetch_failed is False
        card = _card(PH, r)[0]
        assert card.state == UI_FAILED and card.note.where.startswith(_EXC_WHERE_HEAD)


# ── 其他卡：輸出一字不變（test_p04 `_enumerate` 全窮舉 ＋ 真的 L3 戰情表）──────────
def _prod_station(P):
    idx = pd.date_range("2020-01-03", periods=300, freq="W-FRI")

    def _metrics(tk, ak):
        if ak == T.KIND_ETF:
            return {"weekly_close": pd.Series([30 + (i % 7) * 0.3 for i in range(300)],
                                              index=idx), "current_price": 35.0}
        return {"mj_grade": "A", "mj_score_pct": 80, "mj_headline": "ok", "mj_fail_items": [],
                "kd_state": {"k": 50, "d": 40, "label": "中性"}, "name": tk,
                "trend_verdict": None, "current_price": 125.0}

    hold = [{"ticker": "0056", "name": "高股息", "asset_class": T.ASSET_CORE,
             "asset_kind": T.KIND_ETF, "held": True, "lots": 3, "avg_price": 30.0},
            {"ticker": "2330", "name": "2330", "asset_class": T.ASSET_SATELLITE,
             "asset_kind": T.KIND_STOCK, "held": True, "lots": 1, "avg_price": 100.0}]
    rows = S.build_station_rows(hold, vix=18.0, metrics_fn=_metrics)
    dg = S.build_station_digest(rows, 18.0)
    return P.StationReadout(
        requested=True, submitted=True, bound=True, holdings_n=len(hold), rows=tuple(rows),
        digest=P._digest_map(dg), totals=P._digest_map(S.compute_portfolio_totals(rows)),
        split=P._digest_map(dg.get("allocation")),
        take_profit=tuple(dict(x) for x in (dg.get("take_profit") or ())),
        add_n=len(dg.get("adds") or ()), cut_n=len(dg.get("reds") or ()),
        err_n=len(dg.get("errors") or ()), judged=1, total_lights=2)


def _other_card_fingerprints(P) -> list[tuple[str, str]]:
    from tests import test_p04_hold_v2_cards as E

    _orig = E.P
    E.P = P
    try:
        _notes, builts = E._enumerate()
    finally:
        E.P = _orig
    st_ = _prod_station(P)
    builts = list(builts) + list(P.build_conclusion_cards(st_)) + [
        P.build_lightwall_card(st_), P.build_take_profit_card(st_),
        P.build_switch_card(P.SwitchReadout(requested=True, submitted=True, stance="neutral"),
                            st_),
        P.build_allocation_split_card(st_), P.build_core_satellite_card(st_),
        P.build_ai_summary_card(P.AiSummaryReadout(requested=True, text="x"), st_)]
    seen: dict[str, str] = {}
    out: list[tuple[str, str]] = []
    for card, facts, sig in builts:
        if card.key == "hold.vix":
            continue
        _k = repr((card, tuple(facts), sig))
        if _k not in seen:
            seen[_k] = P.v2_card_html(card, facts, sig)
        out.append((card.key, hashlib.sha256((_k + seen[_k]).encode()).hexdigest()))
    return out


class TestOtherCardsByteIdentical:
    def test_b_every_other_hold_card_is_byte_identical_with_or_without_this_batch(self):
        before = _other_card_fingerprints(_mutant(PH, *_REVERT_B5))
        after = _other_card_fingerprints(PH)
        assert len(before) == len(after) > 1000
        assert {k for k, _ in after} >= {
            "hold.lightwall", "hold.switch", "hold.take_profit", "hold.alloc_split",
            "hold.macro_stage", "hold.position_cap", "hold.deep.dividend_cash",
            "hold.ai_summary", "hold.conclusion.action"}
        assert before == after

    def test_b_the_vix_card_really_differs_between_the_two_versions(self, yf):
        """前提自證：上面那一組排除的 `hold.vix`，在兩個版本下**確實**不同（否則比對沒意義）。"""
        yf(_UPSTREAM_MISSING["empty"])
        old = _mutant(PH, *_REVERT_B5)
        old_c = _card(old, old.load_vix(old.HoldRequest(submitted=True)))[0]
        new_c = _card(PH, PH.load_vix(_SUBMITTED))[0]
        assert old_c.state == UI_EMPTY and _VALID in old_c.note.why, "修前就是灰卡（根因重現）"
        assert new_c.state == UI_FAILED


# ══════════════════════════════════════════════════════════════════
# (c) 突變 —— 拿掉本批的任一條，(a)／(b) 必須失敗
# ══════════════════════════════════════════════════════════════════
class TestMutations:
    def test_c_dropping_the_flag_turns_a_grey_again(self, yf):
        yf(_UPSTREAM_MISSING["none"])
        m = _mutant(PH, _REVERT_B5[1])
        card = _card(m, m.load_vix(m.HoldRequest(submitted=True)))[0]
        assert card.state == UI_EMPTY and _VALID in card.note.why

    def test_c_dropping_the_reason_turns_a_grey_again(self):
        m = _mutant(PH, _REVERT_B5[2])
        card = _card(m, m.VixReadout(requested=True, fetch_failed=True))[0]
        assert card.state == UI_EMPTY and _VALID in card.note.why

    def test_c_calling_l3_without_strict_hides_the_exception(self, yf):
        """頁面不傳 strict → 例外又被 L3 吞成 None → 例外原文從卡上消失、指路變成「重跑」。"""
        yf(_raises)
        m = _mutant(PH, _REVERT_B5[0])
        card = _card(m, m.load_vix(m.HoldRequest(submitted=True)))[0]
        assert "yf contract broken" not in card.note.why
        assert not card.note.where.startswith(_EXC_WHERE_HEAD)

    def test_c_l3_strict_ignored_swallows_again(self, yf):
        m = _mutant(S, ("    if strict:\n        return _latest_vix_close()\n", ""))
        yf(_raises)
        assert m.fetch_vix(strict=True) is None, "拿掉 strict 分支後例外又被吞 —— L3 測試必須抓到"

    def test_c_flag_from_raw_none_instead_of_num_misses_nan(self, monkeypatch):
        m = _mutant(PH, ("fetch_failed=_vx is None)", "fetch_failed=_v is None)"))
        monkeypatch.setattr(S, "fetch_vix", lambda **_k: float("nan"))
        card = _card(m, m.load_vix(m.HoldRequest(submitted=True)))[0]
        assert card.state == UI_EMPTY, "NaN 又落回灰卡 —— (a) 的 NaN 那一條必須抓到"

    def test_c_routing_a_fetch_failure_to_the_exception_note_is_caught(self):
        """抓不到卻用「例外」那一則 → 它會說「拋出例外」「這不是取數失敗」—— 兩句都是假的。"""
        m = _mutant(PH, ("elif _state == UI_FAILED and not vix.error:",
                         "elif False:"))
        card = _card(m, m.VixReadout(requested=True, fetch_failed=True))[0]
        assert card.note.why != _NO_CLOSE_WHY and "拋出例外" in card.note.why
        assert card.note.where.startswith(_EXC_WHERE_HEAD)

    def test_a_the_old_empty_why_is_not_reused_for_the_red(self):
        card = _card(PH, PH.VixReadout(requested=True, fetch_failed=True))[0]
        assert "上游這一輪沒有回最新收盤" not in card.note.why and _VALID not in card.note.why
