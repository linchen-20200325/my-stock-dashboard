"""批 Z58：三項修正錯誤（客戶 2026-10-13 裁示 B 的延伸；正常路徑逐字不變）。

① Z50-n2（L2 共用層）：`dividend_station.health_b` 只擋 `None` —— Sharpe 是 NaN 時 `nan < 0` 為
   False → 亮 🟢「Sharpe nan ≥ 0」（還可能被列為換入）；-inf → 🔴「Sharpe -inf < 0」（被列為換出）。
   修後：非有限值 → ⚪、`Flag.invalid=True`、說明用核准句「夏普資料異常，無法計算，不下結論。」。
   L3 連帶：健檢 B 會亮 🔴 → 判不出來就判不出要不要換出 → 併入 `_SWITCH_OUT_INVALID_KEYS`
   （批 Z53 只收 A 的理由是「B 沒有資料異常路徑」，本批起不成立）。換入排除與 ⑦「資料異常未判」
   走既有的 `invalid_keys` → `_invalid_lights` / `_invalid_texts`，不另寫。
② Z53-n6（新 UI ④ 換股卡）：只有**觀察清單列**健檢資料異常、而這一輪換出換入都是 0 時，
   卡片仍寫「這是一個有效的結果 …沒有給出可換入的標的」。修後：同批 Z53 持有列的處置（紅、
   why 只用 L2 客戶句、where 沿用 Z53 那一句），⛔ 不新寫文案。
③ 三處過期註解／說明屬實化（零行為變更）：page_today `foreign_net` 已接線、page_find 估值已接線、
   reconcile 灰態 why「不存在或為空」→「不存在或為假值（如 …）」。

每項都附 revert-pair（修後 → 修前）變體，證明「拿掉修正 → 測試轉紅」。
"""
from __future__ import annotations

import functools
import pathlib
import re
import sys
import types

import numpy as np
import pandas as pd
import pytest

import src.services.dividend_station_service as S
import src.services.reconcile_service as RS
import src.ui.views.page_hold as PH
from shared import station_specs as SS
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_LIVE
from src.compute.etf import dividend_station as L2

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_L2 = "src/compute/etf/dividend_station.py"
_SVC = "src/services/dividend_station_service.py"
_PAGE = "src/ui/views/page_hold.py"

_BAD = {"nan": float("nan"), "pos_inf": float("inf"), "neg_inf": float("-inf")}
_BAD_S = {**_BAD, "np_nan": np.nan, "np_neg_inf": np.float64("-inf"), "text": "abc"}
_NONFINITE_RE = re.compile(r"(?i)(?<![a-z])(nan|inf|infinity)(?![a-z])")
_VALID_PHRASE = "有效的結果"
_SWITCH_INVALID_WHERE = f"{PH.NO_EXIT_MARKER} —— 請把上面那行訊息回報給維護者"


def _sentence(item: str) -> str:
    return f"{item}資料異常，無法計算，不下結論。"


_SHARPE_SENT = _sentence("夏普")


def _no_nonfinite(text: str) -> None:
    _hit = _NONFINITE_RE.search(text)
    assert _hit is None, f"出現 {_hit.group(0)!r}：…{text[max(0, _hit.start() - 40):_hit.end() + 40]}…"


# ══════════════════════════════════════════════════════════════════
# revert-pair（修後逐字, 修前逐字）與變體載入
# ══════════════════════════════════════════════════════════════════
#: ① L2：拿掉健檢 B 的非有限值閘門（＝修前）。
Z58_HB_PAIR = ('    if SS.is_invalid_number(sharpe):\n'
               '        return Flag("⚪", SS.invalid_data_text("夏普"), invalid=True)\n', "")
#: ① L3：健檢 B 不算換出異常（＝批 Z53 原狀）。
Z58_OUT_PAIR = ('_SWITCH_OUT_INVALID_KEYS |= {SS.KEY_HEALTH_B}\n'
                '_SWITCH_OUT_INVALID_LABELS += ("健檢B",)\n', "")
#: ② L5 ④ 卡：不看觀察清單列的異常（＝修前：灰「有效的結果」）。
Z58_CARD_PAIR = ("    _invalid_blocks += () if (switch.error or switch.has_advice) "
                 "else switch.rows_invalid_in\n", "")
#: ② L5 `SwitchReadout.failed`：不看觀察清單列的異常。
Z58_FAILED_PAIR = ("        if self.rows_invalid_in and not self.has_advice:"
                   "   # 批 Z58：觀察清單列異常、這一輪 0 建議\n            return True\n", "")
#: ①② L5 v2 摘錄：不登記新出現的客戶句（→ `v2_short_rows` KeyError）。
Z58_V2_PAIR = ("                  *_V2_SWITCH_INVALID_WHY_Z58),     # 批 Z58：健檢 B（持有）／B·C·D（觀察清單）\n",
               "                  ),\n")

_ALL_PAIRS = {_L2: (Z58_HB_PAIR,), _SVC: (Z58_OUT_PAIR,),
              _PAGE: (Z58_CARD_PAIR, Z58_FAILED_PAIR, Z58_V2_PAIR)}


def _exec_module(name: str, path: pathlib.Path, code: str) -> types.ModuleType:
    m = types.ModuleType(name)
    m.__file__ = str(path)
    sys.modules[name] = m           # dataclass 解析註解需要模組已註冊
    exec(compile(code, str(path), "exec"), m.__dict__)
    return m


@functools.lru_cache(maxsize=None)
def _variant(rel: str, pairs: tuple[tuple[str, str], ...], name: str) -> types.ModuleType:
    """現行原始碼只套 `pairs`（修後 → 修前），載成獨立模組物件（不影響本尊）。"""
    path = _ROOT / rel
    code = path.read_text(encoding="utf-8")
    for new, old in pairs:
        assert code.count(new) == 1, f"替換點不唯一或已不存在：{new[:70]!r}"
        code = code.replace(new, old)
    return _exec_module(name, path, code)


def _l2_pre():
    return _variant(_L2, (Z58_HB_PAIR,), "_z58_pre_l2")


def _svc_pre():
    return _variant(_SVC, (Z58_OUT_PAIR,), "_z58_pre_svc")


def _page_pre():
    return _variant(_PAGE, (Z58_CARD_PAIR, Z58_FAILED_PAIR), "_z58_pre_page")


def test_revert_pairs_are_unique_anchors():
    for rel, pairs in _ALL_PAIRS.items():
        code = (_ROOT / rel).read_text(encoding="utf-8")
        for new, _old in pairs:
            assert code.count(new) == 1, new


def _ft(f) -> tuple:
    return (f.level, f.msg, f.miss_reason, getattr(f, "invalid", False))


# ══════════════════════════════════════════════════════════════════
# ① L2 health_b
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("bad", list(_BAD_S), ids=list(_BAD_S))
def test_health_b_invalid_is_white_with_approved_sentence(bad):
    f = L2.health_b(_BAD_S[bad])
    assert _ft(f) == ("⚪", _SHARPE_SENT, "", True)
    _no_nonfinite(f.msg)


def test_health_b_none_unchanged():
    assert _ft(L2.health_b(None)) == _ft(_l2_pre().health_b(None)) == (
        "⚪", "B 無夏普（週數不足或波動為零,算不出來）", SS.MISS_NOT_ENOUGH, False)


_NORMAL_SHARPE = (-5.0, -1.0, -0.01, -1e-12, -0.0, 0.0, 1e-12, 0.8, 3.2, 1e6,
                  np.float64(0.5), np.float64(-0.5), 1, -2)


@pytest.mark.parametrize("v", _NORMAL_SHARPE, ids=[repr(v) for v in _NORMAL_SHARPE])
def test_health_b_normal_identical_to_pre(v):
    assert _ft(L2.health_b(v)) == _ft(_l2_pre().health_b(v))
    assert L2.health_b(v).invalid is False


def test_pre_bug_reproduced_by_revert_pair():
    """修前（拿掉閘門）：NaN／+inf 亮 🟢、-inf 亮 🔴，說明直接印 nan／inf → 本批前 4 個測試都會紅。"""
    P = _l2_pre()
    assert _ft(P.health_b(float("nan")))[:2] == ("🟢", "Sharpe nan ≥ 0")
    assert _ft(P.health_b(float("inf")))[:2] == ("🟢", "Sharpe inf ≥ 0")
    assert _ft(P.health_b(float("-inf")))[:2] == ("🔴", "Sharpe -inf < 0：承擔風險卻無超額報酬")
    assert P.health_b(float("nan")).invalid is False


# ── assess_holding / light_cells / suggest_action ─────────────────────
_IDX = pd.date_range("2023-01-06", periods=120, freq="W-FRI")
_WK = pd.Series(np.linspace(20, 30, 120), index=_IDX)


def _assess(L=L2, **over):
    kw = dict(ticker="0056", name="0056", asset_class="core", weekly_close=_WK, vix=15.0,
              premium_pct=0.3, sharpe=0.8, total_return_1y_pct=10.0, annual_yield_pct=5.0,
              inception_years=5.0, ann_return_3y_pct=8.0, cum_return_3y_pct=25.0,
              peer_ranks={3: .2, 6: .2, 12: .2})
    kw.update(over)
    return L.assess_holding(**kw)


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_assess_marks_health_b_invalid_and_no_red_action(bad):
    a = _assess(sharpe=_BAD[bad])
    assert a.invalid_keys == (SS.KEY_HEALTH_B,)
    assert a.health_b.level == "⚪"
    _act = L2.suggest_action(a)
    assert not _act.startswith("🔴 汰弱"), _act
    _no_nonfinite(_act)
    _cell = {c.key: c for c in L2.light_cells(a)}[SS.KEY_HEALTH_B]
    assert _cell.level == "⚪"


def test_assess_neg_inf_pre_was_red_switch_out():
    """修前 -inf → 建議動作「🔴 汰弱：Sharpe -inf < 0」（被當成換出），修後不再如此。"""
    P = _l2_pre()
    assert P.suggest_action(_assess(P, sharpe=float("-inf"))).startswith("🔴 汰弱：Sharpe -inf")
    assert not L2.suggest_action(_assess(sharpe=float("-inf"))).startswith("🔴")


@pytest.mark.parametrize("v", (-1.0, 0.0, 0.8, None), ids=["neg", "zero", "pos", "none"])
def test_assess_normal_identical_to_pre(v):
    a, p = _assess(sharpe=v), _assess(_l2_pre(), sharpe=v)
    assert a.invalid_keys == p.invalid_keys == ()
    assert (_ft(a.health_b), a.worst_health, L2.suggest_action(a)) == \
        (_ft(p.health_b), p.worst_health, _l2_pre().suggest_action(p))
    assert repr(L2.light_cells(a)).replace("_z58_pre_l2", "x") == \
        repr(_l2_pre().light_cells(p)).replace("_z58_pre_l2", "x")


# ── L3 列 / 換股 ─────────────────────────────────────────────────────
def _etf_metrics(**over) -> dict:
    base = dict(weekly_close=_WK, premium_pct=0.3, sharpe=0.8, total_return_1y_pct=10.0,
                annual_yield_pct=5.0, inception_years=5.0, ann_return_3y_pct=8.0,
                cum_return_3y_pct=25.0, peer_ranks={3: .2, 6: .2, 12: .2}, current_price=30.0)
    base.update(over)
    return base


def _hold_pair(held_0056: bool = True) -> list[dict]:
    return [{"ticker": "0056", "name": "0056", "asset_kind": "etf", "lots": 1.0,
             "avg_price": 25.0, "held": held_0056},
            {"ticker": "0050", "name": "0050", "asset_kind": "etf", "lots": 3.0,
             "avg_price": 25.0, "held": True}]


def _rows(over56: dict, over50: dict | None = None, *, held_0056: bool = True,
          Smod=S, vix=15.0) -> list[dict]:
    def mf(tk, kind):
        return _etf_metrics(**(over56 if tk == "0056" else (over50 or {})))
    return Smod.build_station_rows(_hold_pair(held_0056), vix=vix, metrics_fn=mf)


_RED = {"sharpe": -1.0}
_CAND = ({"代碼": "00878", "名稱": "國泰永續", "綜合分": 80},)


@pytest.mark.parametrize("bad", list(_BAD_S), ids=list(_BAD_S))
def test_l3_row_carries_health_b_invalid(bad):
    r = _rows({"sharpe": _BAD_S[bad]})[0]
    assert r[SS.KEY_INVALID_LIGHTS] == (SS.KEY_HEALTH_B,)
    assert r[SS.KEY_INVALID_TEXTS] == (("健檢B", _SHARPE_SENT),)
    assert r["_detail"]["健檢B"] == _SHARPE_SENT
    _no_nonfinite(repr(r["_detail"]) + r["建議動作"] + repr(r[SS.KEY_INVALID_TEXTS]))


@pytest.mark.parametrize("bad", list(_BAD_S), ids=list(_BAD_S))
def test_l3_switch_out_invalid_includes_health_b(bad):
    adv = S.build_switch_advice(_rows({"sharpe": _BAD_S[bad]}), {"loaded": False}, [])
    assert adv["switch_out"] == []
    assert adv["switch_out_invalid"] == [{"代號": "0056", "項目": (("健檢B", _SHARPE_SENT),)}]
    _no_nonfinite(repr(adv))


def test_l3_switch_out_invalid_a_and_b_in_order():
    adv = S.build_switch_advice(
        _rows({"sharpe": float("nan"), "annual_yield_pct": float("inf")}), {"loaded": False}, [])
    assert adv["switch_out_invalid"] == [{"代號": "0056", "項目": (
        ("健檢A", _sentence("配息率")), ("健檢B", _SHARPE_SENT))}]


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_l3_red_row_with_b_invalid_not_marked(bad):
    """A 已 🔴（正常值）→ 換出結論成立；B 異常不另列。"""
    adv = S.build_switch_advice(
        _rows({"sharpe": _BAD[bad], "total_return_1y_pct": 1.0}), {"loaded": False}, [])
    assert [d["代號"] for d in adv["switch_out"]] == ["0056"]
    assert "switch_out_invalid" not in adv


def test_mut_l3_without_b_drops_switch_out_invalid():
    """revert-pair：拿掉 B（＝批 Z53 原狀）→ 健檢 B 異常的持有列沒被標出 → 上面的測試會紅。"""
    adv = _svc_pre().build_switch_advice(_rows({"sharpe": float("nan")}), {"loaded": False}, [])
    assert "switch_out_invalid" not in adv


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
@pytest.mark.parametrize("cands", [(), _CAND], ids=["no_cands", "cands"])
def test_l3_watchlist_b_invalid_not_switched_in(bad, cands):
    adv = S.build_switch_advice(_rows({"sharpe": _BAD[bad]}, held_0056=False),
                                {"loaded": False}, list(cands))
    assert "0056" not in [d["代號"] for d in adv["switch_in"]]


def test_pre_l2_nan_watchlist_was_switched_in_and_neg_inf_switched_out(monkeypatch):
    """修前（L2 無閘門）：觀察清單 NaN → 🟢 被推薦換入；持有 -inf → 🔴 被列換出。"""
    monkeypatch.setattr(S, "ds", _l2_pre())
    adv = S.build_switch_advice(_rows({"sharpe": float("nan")}, held_0056=False),
                                {"loaded": False}, [])
    assert [d["代號"] for d in adv["switch_in"]] == ["0056"]
    adv = S.build_switch_advice(_rows({"sharpe": float("-inf")}), {"loaded": False}, [])
    assert [d["代號"] for d in adv["switch_out"]] == ["0056"]


# ══════════════════════════════════════════════════════════════════
# 端到端：新 UI load_station → load_switch → ④ 卡 → ⑦ prompt（外部全部替身）
# ══════════════════════════════════════════════════════════════════
def _switch_run(monkeypatch, over56: dict, over50: dict | None = None, *, held_0056=True,
                Smod=S, Pmod=PH, cands=(), vix=15.0, l2=None):
    with monkeypatch.context() as mp:
        if l2 is not None:
            mp.setattr(Smod, "ds", l2)
            mp.setattr(S, "ds", l2)
        _rs = _rows(over56, over50, held_0056=held_0056, Smod=Smod, vix=vix)
        mp.setattr("src.services.dividend_station_service.get_station_rows", lambda h: (_rs, vix))
        mp.setattr("src.services.dividend_station_service.build_switch_advice",
                   Smod.build_switch_advice)
        mp.setattr("src.services.dividend_station_service.get_switch_in_candidates",
                   lambda **k: [dict(_c) for _c in cands])
        _cap: dict = {}

        def _gem(prompt, max_tokens=None, **k):
            _cap["prompt"] = prompt
            return "摘要OK"
        mp.setattr("src.services.app_ai_service.gemini_call", _gem)
        h = Pmod.HoldingsReadout(requested=True, submitted=True, bound=True,
                                 holdings=tuple(_hold_pair(held_0056)))
        st = Pmod.load_station(h)
        sw = Pmod.load_switch(st, Pmod.MacroReadout(requested=True, loaded=False), h)
        built = Pmod.build_switch_card(sw, st)
        Pmod.load_ai_summary(True, st, sw)
        return st, sw, built, _cap.get("prompt", ""), _rs


def _pre_run(monkeypatch, over56, over50=None, **kw):
    return _switch_run(monkeypatch, over56, over50, Smod=_svc_pre(), Pmod=_page_pre(),
                       l2=_l2_pre(), **kw)


def _blob(built) -> str:
    card, facts, sig = built
    return repr(card) + repr(tuple(facts)) + sig + PH.v2_card_html(card, facts, sig)


def _norm(x) -> str:
    return re.sub(r"_z58_pre_\w+", "M", repr(x))


@pytest.mark.parametrize("bad", list(_BAD_S), ids=list(_BAD_S))
def test_card_held_b_invalid_does_not_conclude(bad, monkeypatch):
    st, sw, built, prompt, _r = _switch_run(monkeypatch, {"sharpe": _BAD_S[bad]})
    card, facts, sig = built
    assert card.state == UI_FAILED and sig == ""
    assert card.note.now == PH.SWITCH_FAILED_NOW
    assert card.note.why == f"0056：{_SHARPE_SENT}"
    assert card.note.where == _SWITCH_INVALID_WHERE
    assert dict(PH.v2_short_rows(card)[0])[PH.V2_WHY_FACT_KEY] == _SHARPE_SENT
    assert _VALID_PHRASE not in _blob(built)
    _no_nonfinite(_blob(built))
    _no_nonfinite(prompt)
    assert "── 換股建議 ──" not in prompt
    assert f"- 資料異常未判：0056（健檢B：{_SHARPE_SENT}" in prompt


def test_card_held_neg_inf_pre_was_switch_out(monkeypatch):
    """修前全鏈（L2／L3／L5 三處都 revert）：-inf → ④「換出 1 檔」、facts 印出「Sharpe -inf」。"""
    _st, _sw, built, prompt, _r = _pre_run(monkeypatch, {"sharpe": float("-inf")})
    assert built[0].state == UI_LIVE and "-inf" in _blob(built)


_NORMAL_CASES = {
    "all_green": ({}, None),
    "red_0050": ({}, _RED),
    "red_0056_b": (_RED, None),
    "sharpe_none": ({"sharpe": None}, None),
    "sharpe_zero": ({"sharpe": 0.0}, None),
    "a_invalid_z53": ({"annual_yield_pct": float("nan")}, None),
}


@pytest.mark.parametrize("case", list(_NORMAL_CASES), ids=list(_NORMAL_CASES))
@pytest.mark.parametrize("held", [True, False], ids=["held", "watch"])
@pytest.mark.parametrize("cands", [(), _CAND], ids=["no_cands", "cands"])
def test_normal_path_identical_to_pre(case, held, cands, monkeypatch):
    """Sharpe 有限值／None（含批 Z53 既有的健檢 A 異常）→ L3 列、換股、④ 卡、⑦ prompt 逐字同修前。

    例外一處（設計如此）：觀察清單列健檢 A 異常 ＋ 無候選 ＋ 無 🔴 —— 正是 ② 要修的情境，另測。"""
    o56, o50 = _NORMAL_CASES[case]
    if case == "a_invalid_z53" and not held and not cands:
        pytest.skip("② 的修正情境（見 test_card_watchlist_only_invalid_*）")
    _now = _switch_run(monkeypatch, o56, o50, held_0056=held, cands=cands)
    _pre = _pre_run(monkeypatch, o56, o50, held_0056=held, cands=cands)
    assert _norm(_now[4]) == _norm(_pre[4]), "L3 列逐鍵同修前"
    assert repr(_now[2]) == repr(_pre[2]), "④ 卡同修前"
    assert _now[3] == _pre[3], "⑦ prompt 逐字同修前"


# ══════════════════════════════════════════════════════════════════
# ② ④ 卡：只有觀察清單列健檢資料異常 → ⛔ 不宣稱「有效的結果」
# ══════════════════════════════════════════════════════════════════
_WATCH_CASES = {
    "A_yield": ({"annual_yield_pct": float("nan")}, _sentence("配息率")),
    "A_ret": ({"total_return_1y_pct": float("inf")}, _sentence("近一年總報酬")),
    "B": ({"sharpe": float("nan")}, _SHARPE_SENT),
    "B_neg_inf": ({"sharpe": float("-inf")}, _SHARPE_SENT),
    "C": ({"weekly_close": _WK.where(_WK.index != _WK.index[-1], float("nan"))},
          _sentence("週收")),
    "D": ({"premium_pct": float("-inf")}, _sentence("折溢價")),
}


@pytest.mark.parametrize("case", list(_WATCH_CASES), ids=list(_WATCH_CASES))
def test_card_watchlist_only_invalid_does_not_claim_valid(case, monkeypatch):
    over, sentence = _WATCH_CASES[case]
    st, sw, built, prompt, rows = _switch_run(monkeypatch, over, held_0056=False)
    assert rows[0]["held"] is False and rows[0]["健檢"] == "🟢", "前提：被排除的是一列看似綠燈的觀察清單"
    assert sw.switch_out == () and sw.switch_in == () and sw.rows_invalid == ()
    assert sw.rows_invalid_in == (("0056", (sentence,)),)
    card, facts, sig = built
    assert card.state == UI_FAILED and sig == ""
    assert card.note.now == PH.SWITCH_FAILED_NOW
    assert card.note.why == f"0056：{sentence}"
    assert card.note.where == _SWITCH_INVALID_WHERE
    assert dict(PH.v2_short_rows(card)[0])[PH.V2_WHY_FACT_KEY] == sentence
    assert _VALID_PHRASE not in _blob(built)
    _no_nonfinite(_blob(built))
    assert sw.failed is True
    assert "── 換股建議 ──" not in prompt


def test_card_watchlist_only_invalid_pre_claimed_valid(monkeypatch):
    """重現（修前 L5）：同一情境 ④ 是灰卡「這是一個有效的結果 …沒有給出可換入的標的」。"""
    _st, _sw, built, _p, _r = _switch_run(monkeypatch, {"annual_yield_pct": float("nan")},
                                          held_0056=False, Pmod=_page_pre())
    assert built[0].state == UI_EMPTY and _VALID_PHRASE in built[0].note.why
    assert "沒有給出可換入的標的" in built[0].note.why


def test_mut_card_pair_reopens_valid_result(monkeypatch):
    P0 = _variant(_PAGE, (Z58_CARD_PAIR,), "_z58_mut_card")
    _st, _sw, built, _p, _r = _switch_run(monkeypatch, {"sharpe": float("nan")},
                                          held_0056=False, Pmod=P0)
    assert built[0].state == UI_EMPTY and _VALID_PHRASE in built[0].note.why


def test_mut_failed_pair_ignores_watchlist_invalid():
    P0 = _variant(_PAGE, (Z58_FAILED_PAIR,), "_z58_mut_failed")
    assert P0.SwitchReadout(requested=True, rows_invalid_in=(("0056", (_SHARPE_SENT,)),)).failed is False


def test_mut_v2_pair_breaks_excerpt(monkeypatch):
    """不登記「夏普」等新客戶句 → v2 摘錄對不上 → KeyError（看得見的紅卡，不靜默）。"""
    P0 = _variant(_PAGE, (Z58_V2_PAIR,), "_z58_mut_v2")
    built = _switch_run(monkeypatch, {"sharpe": float("nan")}, Pmod=P0)[2]
    with pytest.raises(KeyError):
        P0.v2_short_rows(built[0])


@pytest.mark.parametrize("cands", [(), _CAND], ids=["no_cands", "cands"])
def test_watchlist_invalid_with_any_advice_unchanged(cands, monkeypatch):
    """有任何換出（0050 🔴）或換入（選股池）→ 卡片照修前下結論（同 Z51：不過度封鎖）。"""
    o50 = _RED if not cands else None
    _now = _switch_run(monkeypatch, {"annual_yield_pct": float("nan")}, o50,
                       held_0056=False, cands=cands)
    _pre = _switch_run(monkeypatch, {"annual_yield_pct": float("nan")}, o50,
                       held_0056=False, cands=cands, Pmod=_page_pre())
    assert _now[2][0].state == UI_LIVE
    assert repr(_now[2]) == repr(_pre[2]) and _now[3] == _pre[3]
    assert _now[1].failed is False


def test_watchlist_invalid_on_yellow_row_not_listed(monkeypatch):
    """列上已是 🟡（D 高溢價）→ 補回異常那盞也不會變 🟢 → 「沒有可換入」成立 → 同修前灰卡。"""
    over = {"annual_yield_pct": float("nan"), "premium_pct": 5.0}
    _now = _switch_run(monkeypatch, over, held_0056=False)
    _pre = _switch_run(monkeypatch, over, held_0056=False, Pmod=_page_pre())
    assert _now[4][0]["健檢"] == "🟡" and _now[1].rows_invalid_in == ()
    assert repr(_now[2]) == repr(_pre[2]) and _now[2][0].state == UI_EMPTY


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_watchlist_only_235_invalid_not_listed(bad, monkeypatch):
    """235（VIX）異常不參與換入（Z51）→ 不列、卡片同修前。"""
    _now = _switch_run(monkeypatch, {}, held_0056=False, vix=_BAD[bad])
    _pre = _switch_run(monkeypatch, {}, held_0056=False, vix=_BAD[bad], Pmod=_page_pre())
    assert _now[1].rows_invalid_in == ()
    assert repr(_now[2]) == repr(_pre[2])


def test_switch_in_invalid_rows_unit():
    base = {"held": False, "健檢": "🟢", "_detail": {},
            SS.KEY_INVALID_LIGHTS: (SS.KEY_HEALTH_C, SS.KEY_LIGHT235),
            SS.KEY_INVALID_TEXTS: (("健檢C", _sentence("週收")), ("235", _sentence("VIX")))}
    rows = [
        {**base, "代號": "A1"},                                            # 列
        {**base, "代號": "A2", "健檢": "⚪"},                               # 列（⚪ 可能本該 🟢）
        {**base, "代號": "X1", "held": True},                              # 持有 → 不列
        {**base, "代號": "X2", "健檢": "🟡"},                               # 🟡 → 不列
        {**base, "代號": "X3", "健檢": "🔴"},                               # 🔴 → 不列
        {**base, "代號": "X4", "_detail": {"error": "x"}},                 # 整批失敗 → 不列
        {**base, "代號": "X5", SS.KEY_INVALID_LIGHTS: (SS.KEY_LIGHT235,)},  # 只有 235 → 不列
        {"代號": "X6", "held": False, "健檢": "🟢", "_detail": {}},         # 正常 → 不列
    ]
    assert S.switch_in_invalid_rows(rows) == [
        {"代號": "A1", "項目": (("健檢C", _sentence("週收")),)},
        {"代號": "A2", "項目": (("健檢C", _sentence("週收")),)}]
    assert S.switch_in_invalid_rows([]) == [] and S.switch_in_invalid_rows(None) == []


def test_failed_property_direct():
    _inv = (("0056", (_SHARPE_SENT,)),)
    assert PH.SwitchReadout(requested=True, rows_invalid_in=_inv).failed is True
    assert PH.SwitchReadout(requested=True, rows_invalid_in=_inv,
                            switch_in=({"代號": "00878"},)).failed is False
    assert PH.SwitchReadout(requested=True, rows_invalid_in=_inv,
                            switch_out=({"代號": "0050"},)).failed is False
    assert PH.SwitchReadout(requested=True).failed is False


def test_held_and_watch_invalid_both_told(monkeypatch):
    """持有列與觀察清單列同時異常（無 🔴、無候選）→ 兩列都講，同一句併代號。"""
    built = _switch_run(monkeypatch, {"sharpe": float("nan")}, {"sharpe": float("inf")},
                        held_0056=False)[2]
    assert built[0].state == UI_FAILED
    assert built[0].note.why == f"0050、0056：{_SHARPE_SENT}"


def test_v2_new_item_names_match_l2():
    """④ v2 新摘錄候選的項目名與 L2 健檢 B／C／D 實際寫進客戶句的一致（L2 改名 → 這裡紅）。"""
    _wk_bad = _WK.copy()
    _wk_bad.iloc[-1] = float("nan")
    assert (L2.health_b(float("nan")).msg, L2.health_c(_wk_bad).msg,
            L2.health_d(float("nan")).msg) == PH._V2_SWITCH_INVALID_WHY_Z58


# ══════════════════════════════════════════════════════════════════
# ③ 過期註解／說明屬實化（零行為變更）
# ══════════════════════════════════════════════════════════════════
def _src(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def test_page_today_docstring_no_longer_says_foreign_net_unwired():
    from shared.macro_buckets import SPECS_BY_KEY
    assert SPECS_BY_KEY["foreign_net"].wired is True, "前提：foreign_net 已接線"
    assert not [k for k, v in SPECS_BY_KEY.items() if not v.wired], "前提：現行無 wired=False 的燈"
    text = _src("src/ui/views/page_today.py")
    assert "讀 `spec` 讓 `foreign_net`（`wired=False`）\n" not in text
    assert "讀 `spec` 讓 `wired=False` 的燈照樣畫成「未接線」" in text


def test_page_find_comment_no_longer_says_valuation_unwired():
    from src.services.fundamental_screener_service import SCREEN_ANGLE_LABELS
    from src.ui.views.page_find import PE_FACTOR_KEY
    assert next(iter(SCREEN_ANGLE_LABELS.values())) == PE_FACTOR_KEY, "前提：第一項是估值因子"
    text = _src("src/ui/views/page_find.py")
    assert "第一項正好是估值因子 `PE_FACTOR_KEY`" in text
    # 舊句只剩更正註記裡的引述那一次。
    assert text.count("本頁未接線的估值因子") == 1
    assert "原寫「第一項正好是本頁未接線的估值因子」" in text


@pytest.mark.parametrize("falsy", [None, {}, 0, "", [], False],
                         ids=["none", "empty_dict", "zero", "empty_str", "empty_list", "false"])
def test_reconcile_any_falsy_jingqi_info_reads_warroom(falsy):
    """程式條件 `if _jq_info:` → 任何假值都改讀 warroom（措辭「假值」才屬實）。"""
    s = {"jingqi_info": falsy, "warroom_summary": {"jingqi_avg": 50.0}}
    assert RS.health_inputs(s)["jq"] == 50.0
    assert RS.health_inputs({"jingqi_info": {"avg": 33.0},
                             "warroom_summary": {"jingqi_avg": 50.0}})["jq"] == 33.0


def test_reconcile_wording_says_falsy():
    _desc = [e.desc for e in RS.RECONCILE_SESSION_KEYS if "jingqi_info" in e.desc][0]
    assert "`jingqi_info` 不存在或為假值（如 `None`、空 dict）時改讀" in _desc
    assert "不存在或為空（" not in _desc
    text = _src("src/services/reconcile_service.py")
    assert text.count("不存在或為假值（如 `None`、空 dict）") == 3
