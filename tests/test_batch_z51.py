"""批 Z51 —— 235 加碼燈：輸入資料異常（NaN／±inf／轉不成數字）→ 整盞不下結論（沿用批 Z49／Z50 客戶裁示）。

客戶裁示（2026-10-13，逐字）：統一採用「{項目}資料異常，無法計算，不下結論。」
  · NaN／±inf／其他無效數值一律視為異常；不顯示 nan／inf；不使用替代值繼續計算；
  · 該數值會影響結論時，該卡停止計算並不下結論；正常資料路徑不得改變。

病灶（獨立 QA，批 Z50 後實測重現，Z50-n1）：L2 `light_235` 的週線軸只要月／季／年線任一條有效
就算可用，但判燈條件 `weekly_close < ma13w` 沒有逐條看季線是不是有限值。13 週窗內有 +inf →
季線 inf → `30 < inf` 成立 → 亮 🟡「急跌加碼 30%：週收<季線」（state live），與同列健檢C 的
⚪「週收資料異常…」互相矛盾；新 UI ①「今天要看的：1 檔亮加碼燈」、待辦「加碼 1」、
⑦ prompt「235 加碼觸發」同步帶到。

呼叫鏈（新 UI）：`app._ia_view_hold` → `views.page_hold.render_page_hold` → `load_station`
→ L3 `get_station_rows` → `build_station_rows` → L2 `assess_holding` → `light_235`
→ L3 `row_from_assessment`（`加碼金`、`_detail["235觸發"]`、`_lights`、`_invalid_lights`）
→ `build_station_digest`（`adds`）→ ① `build_action_card`、`build_todo_card`；
`load_ai_summary` → L3 `build_ai_summary` → `build_summary_prompt`（⑦「235 加碼觸發」與「目前 VIX」）；
`load_switch` → L3 `build_switch_advice`（排除 `_invalid_lights` 的列）。

本檔驗：
  A. L2 `light_235`：六個純量輸入任一 NaN／±inf／轉不成數字 → ⚪、不加碼、不停利、客戶句、
     `invalid=True`、`axes_used=()`、`miss_reason` 留空。
  B. L2 `assess_holding`：235 實際用到的週收窗（最長 52 週）內任一筆異常 → 同上，且
     `invalid_keys` 帶 `light235`；窗外異常與正常資料與修前逐值相同。
  C. 新 UI 端到端：①／待辦／⑦ prompt 不出現加碼結論與 nan／inf；換入不推 235 異常列。
  D. 正常路徑與一般缺資料（週數不足、VIX 為 None）與修前**逐值相同**（修前＝現行原始碼套上本批
     全部 revert pair；該組 revert 與本批之前的 commit 版本等價性已在開發時另行驗過 ——
     測試本身不呼叫 git，見 `tests/test_zz_test_portability.py`）。
  E. revert-pair 突變：每一環一組，拔掉 → 修前的錯誤燈號／結論重現。
"""
from __future__ import annotations

import dataclasses
import functools
import itertools
import pathlib
import re
import sys
import types

import numpy as np
import pandas as pd
import pytest

import src.compute.etf.dividend_station as DSL2
import src.services.dividend_station_service as S
import src.ui.views.page_hold as PH
from shared import dividend_station_thresholds as T
from shared import station_specs as SS

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_L2 = "src/compute/etf/dividend_station.py"
_SVC = "src/services/dividend_station_service.py"

_BAD = {"nan": float("nan"), "pos_inf": float("inf"), "neg_inf": float("-inf")}
_BAD_ANY = {**_BAD, "np_nan": np.nan, "text": "abc", "obj": object()}
_NONFINITE_RE = re.compile(r"(?i)(?<![a-z])(nan|inf|infinity)(?![a-z])")


def _sentence(item: str) -> str:
    return f"{item}資料異常，無法計算，不下結論。"


def _no_nonfinite(text: str) -> None:
    _hit = _NONFINITE_RE.search(text)
    assert _hit is None, f"畫面出現 {_hit.group(0)!r}：…{text[max(0, _hit.start() - 40):_hit.end() + 40]}…"


# ══════════════════════════════════════════════════════════════════
# revert-pair（修後逐字, 修前逐字）與變體載入
# ══════════════════════════════════════════════════════════════════
#: L2 `light_235` 的異常閘門（純量 ＋ 呼叫端告知的窗內異常，一起拔）。
Z51_L2_GUARD_PAIR = ("    if _z51_bad:\n", "    if False:\n")
#: L2 `assess_holding` 逐筆看 235 實際用到的週收窗（只拔這一環 → 純量看不出的窗內異常漏網）。
Z51_L2_WINDOW_PAIR = ("                   weekly_window_invalid=_z51_wk_bad)\n",
                      "                   weekly_window_invalid=False)\n")
#: L2 `assess_holding` 把 235 異常彙整進 `invalid_keys`（只拔這一環 → 換入排除失效）。
Z51_L2_AGG_PAIR = ("    if lt.invalid:", "    if False:")
#: L3 `build_summary_prompt` 的 VIX 文字（只拔這一環 → ⑦ prompt 出現 nan／inf）。
Z51_L3_VIX_PAIR = ("    if SS.is_invalid_number(_vix):\n", "    if False:\n")
#: L3 `build_switch_advice`：235 異常不連帶排除換入（只拔這一環 → 回到「任一異常燈都排除」，
#: VIX 異常會讓整份觀察清單改由選股池遞補 —— QA D2）。
Z51_L3_SWITCH_PAIR = (
    "                     and not (set(r.get(SS.KEY_INVALID_LIGHTS) or ()) - _SWITCH_IN_IGNORED_INVALID)\n",
    "                     and not r.get(SS.KEY_INVALID_LIGHTS)\n")
#: L3 `build_station_digest`：把「資料異常未判」的列帶進 digest（只拔這一環 → ⑦ 看不到異常）。
Z51_L3_DIGEST_PAIR = ("    if _invalid_rows:\n", "    if False:\n")
#: L3 `build_summary_prompt`：有異常 → 附事實列、不送「續抱」指示（只拔這一環 → QA D1 重現）。
Z51_L3_PROMPT_PAIR = ('    _inv = digest.get("invalid") or []\n', "    _inv = []\n")
#: L3 `_SWITCH_IN_IGNORED_INVALID` 的 3-3-3 子項（只拔這一環 → 3-3-3 異常又連帶排除換入）。
Z51_L3_SWITCH_333_PAIR = (
    "_SWITCH_IN_IGNORED_INVALID |= {SS.KEY_SCREEN_INCEPTION, SS.KEY_SCREEN_RETURN, SS.KEY_SCREEN_PEER}\n",
    "")
_PRE_L3_PAIRS = (Z51_L3_VIX_PAIR, Z51_L3_SWITCH_PAIR, Z51_L3_DIGEST_PAIR, Z51_L3_PROMPT_PAIR,
                 Z51_L3_SWITCH_333_PAIR)
_PRE_L2_PAIRS = (Z51_L2_GUARD_PAIR, Z51_L2_WINDOW_PAIR, Z51_L2_AGG_PAIR)


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


def _pre() -> types.ModuleType:
    """修前 L2：現行 L2 套上本批**全部** L2 revert pair。"""
    return _variant(_L2, _PRE_L2_PAIRS, "_z51_pre_dividend_station")


def _svc_pre() -> types.ModuleType:
    return _variant(_SVC, _PRE_L3_PAIRS, "_z51_pre_svc")


def test_revert_pairs_are_unique_anchors():
    for rel, pairs in ((_L2, _PRE_L2_PAIRS), (_SVC, _PRE_L3_PAIRS)):
        code = (_ROOT / rel).read_text(encoding="utf-8")
        for new, _old in pairs:
            assert code.count(new) == 1, new


# ══════════════════════════════════════════════════════════════════
# 合成資料（確定性）
# ══════════════════════════════════════════════════════════════════
_IDX = pd.date_range("2023-01-06", periods=120, freq="W-FRI")
_WK = pd.Series(np.linspace(20, 30, 120), index=_IDX)
_PEER_OK = {3: .2, 6: .2, 12: .2}


def _wk_at(pos: int, v, base: pd.Series = _WK) -> pd.Series:
    w = base.astype(object).copy() if isinstance(v, str) else base.copy()
    w.iloc[pos] = v
    return w


def _etf_metrics(**over) -> dict:
    base = dict(weekly_close=_WK, premium_pct=0.3, sharpe=0.8, total_return_1y_pct=10.0,
                annual_yield_pct=5.0, inception_years=5.0, ann_return_3y_pct=8.0,
                cum_return_3y_pct=25.0, peer_ranks=dict(_PEER_OK), current_price=30.0)
    base.update(over)
    return base


def _assess(mod, weekly, vix=15.0, **over):
    m = _etf_metrics(weekly_close=weekly, **over)
    m.pop("current_price")
    return mod.assess_holding(ticker="0056", name="x", asset_class=T.ASSET_CORE, vix=vix, **m)


def _norm(x):
    """深轉換：dataclass（兩個模組各自的類別）→ (類名, asdict)；pandas → 可比較形態。"""
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        return (type(x).__name__, _norm(dataclasses.asdict(x)))
    if isinstance(x, (pd.Series, pd.DataFrame)):
        return ("pd", x.to_json())
    if isinstance(x, dict):
        return tuple((k, _norm(v)) for k, v in x.items())
    if isinstance(x, (list, tuple)):
        return (type(x).__name__, tuple(_norm(v) for v in x))
    if isinstance(x, float) and x != x:
        return "NaN"
    return x


def _assert_light_unjudged(lt, items: tuple[str, ...]) -> None:
    txt = "".join(_sentence(_i) for _i in items)
    assert lt.invalid is True
    assert (lt.light, lt.icon, lt.deploy_pct) == (T.LIGHT_CRUISE, "⚪", 0.0), "不得觸發加碼"
    assert lt.take_profit is None and lt.deepwater_note is None, "不得停利／不得下深水結論"
    assert lt.label == txt and lt.reasons == [txt], "說明只能是客戶句"
    assert lt.axes_used == () and lt.miss_reason == "", "異常不是「沒有值」，不登記 MISS_*"
    _no_nonfinite(lt.label + "".join(lt.reasons))


# ══════════════════════════════════════════════════════════════════
# A. L2 light_235：純量輸入
# ══════════════════════════════════════════════════════════════════
#: 正常時會亮燈二（週收 90 < 季線 100）＋ 布林 -1.5σ（燈一）—— 異常時必須連這個都不講。
_GOOD = dict(vix=15.0, weekly_close=90.0, ma4w=95.0, ma13w=100.0, ma52w=110.0, z=-1.5)
_FIELDS = ("vix", "weekly_close", "ma4w", "ma13w", "ma52w", "z")


def test_l2_good_baseline_concludes():
    """前提：同一組輸入在正常時真的會下加碼結論（否則下面的「不下結論」沒有意義）。"""
    lt = DSL2.light_235(**_GOOD)
    assert (lt.light, lt.deploy_pct, lt.invalid) == (T.LIGHT_2, T.DEPLOY_LIGHT2_PCT, False)


@pytest.mark.parametrize("bad", list(_BAD_ANY), ids=list(_BAD_ANY))
@pytest.mark.parametrize("field", _FIELDS)
def test_l2_scalar_invalid_does_not_conclude(field, bad):
    lt = DSL2.light_235(**{**_GOOD, field: _BAD_ANY[bad]})
    _assert_light_unjudged(lt, ("VIX",) if field == "vix" else ("週收",))


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_l2_vix_and_weekly_both_invalid_listed_in_order(bad):
    lt = DSL2.light_235(**{**_GOOD, "vix": _BAD[bad], "ma13w": _BAD[bad]})
    _assert_light_unjudged(lt, ("VIX", "週收"))


def test_l2_window_flag_from_caller():
    lt = DSL2.light_235(**_GOOD, weekly_window_invalid=True)
    _assert_light_unjudged(lt, ("週收",))


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
@pytest.mark.parametrize("z", [2.5, 3.5])
def test_l2_invalid_suppresses_take_profit(z, bad):
    """VIX 異常時不停利（任一輸入異常即整盞不下結論，不拿其餘軸撐出結論）。"""
    assert DSL2.light_235(**{**_GOOD, "z": z}).take_profit is not None
    _assert_light_unjudged(DSL2.light_235(**{**_GOOD, "z": z, "vix": _BAD[bad]}), ("VIX",))


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_l2_invalid_vix_does_not_fall_back_to_other_axes(bad):
    """VIX 異常 ≠ VIX 缺資料：缺資料（None）照舊用其餘軸判燈二；異常則不下結論。"""
    assert DSL2.light_235(**{**_GOOD, "vix": None}).light == T.LIGHT_2
    _assert_light_unjudged(DSL2.light_235(**{**_GOOD, "vix": _BAD[bad]}), ("VIX",))


def test_l2_numeric_string_keeps_previous_type_error():
    """轉得成數字的字串不是「資料異常」，維持修前行為（`TypeError`，不被轉型救回來）。"""
    for mod in (DSL2, _pre()):
        with pytest.raises(TypeError):
            mod.light_235(**{**_GOOD, "vix": "15"})


# ══════════════════════════════════════════════════════════════════
# B. L2 assess_holding：235 實際用到的週收窗
# ══════════════════════════════════════════════════════════════════
#: 長度 120：窗 ＝ 最後 52 筆（月 4／季 13／布林 20／年 52 取最長）。
_IN_WINDOW = (-1, -4, -5, -13, -14, -20, -21, -30, -52)
_OUT_WINDOW = (-53, -60, -120)


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
@pytest.mark.parametrize("pos", _IN_WINDOW)
def test_assess_window_invalid_does_not_conclude(pos, bad):
    a = _assess(DSL2, _wk_at(pos, _BAD[bad]))
    _assert_light_unjudged(a.light, ("週收",))
    assert SS.KEY_LIGHT235 in a.invalid_keys and a.invalid_keys[-1] == SS.KEY_LIGHT235
    cell = {c.key: c for c in DSL2.light_cells(a)}[SS.KEY_LIGHT235]
    assert (cell.level, cell.state, cell.miss_reason, cell.axes_used) == \
        ("⚪", SS.STATE_MISSING, "", ())


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_assess_qa_repro_inf_in_quarter_window(bad):
    """QA 重現：週收 iloc[-5] 異常、VIX=15 → 修前亮 🟡 急跌加碼 30%（+inf）。"""
    a = _assess(DSL2, _wk_at(-5, _BAD[bad]), vix=15.0)
    _assert_light_unjudged(a.light, ("週收",))
    assert a.invalid_keys == (SS.KEY_HEALTH_C, SS.KEY_LIGHT235)
    assert a.health_c.msg == _sentence("週收"), "與健檢C 同一句，不再互相矛盾"


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_assess_last_close_invalid_matches_health_c(bad):
    a = _assess(DSL2, _wk_at(-1, _BAD[bad]))
    assert a.health_c.invalid and a.light.invalid
    assert a.invalid_keys == (SS.KEY_HEALTH_C, SS.KEY_LIGHT235)


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_assess_nan_hole_is_invalid_not_skipped(bad):
    """NaN 洞（-3）：均線 skipna、布林 z 照算 → 純量全是有限值，靠逐筆看窗才抓得到。"""
    w = _wk_at(-3, _BAD[bad])
    a = _assess(DSL2, w)
    _assert_light_unjudged(a.light, ("週收",))


@pytest.mark.parametrize("bad", list(_BAD_ANY), ids=list(_BAD_ANY))
def test_assess_invalid_vix(bad):
    a = _assess(DSL2, _WK, vix=_BAD_ANY[bad])
    _assert_light_unjudged(a.light, ("VIX",))
    assert a.invalid_keys == (SS.KEY_LIGHT235,)
    p = _assess(_pre(), _WK, vix=15.0)
    for _k in ("health_a", "health_b", "health_c", "health_d", "screen"):
        assert _norm(getattr(a, _k)) == _norm(getattr(p, _k)), "其他燈照常判定"


@pytest.mark.parametrize("n,pos,judged", [
    (10, -4, False), (10, -5, True),        # 窗 ＝ 最後 4 筆（只有月線）
    (19, -13, False), (19, -14, True),      # 窗 ＝ 最後 13 筆（布林要 20 週）
    (30, -20, False), (30, -21, True),      # 窗 ＝ 最後 20 筆（年線要 52 週）
    (3, -1, False), (3, -2, True),          # 均線都算不出：只剩最後一筆
])
def test_assess_window_length_follows_available_periods(n, pos, judged):
    base = _WK.iloc[-n:]
    w = _wk_at(pos, float("inf"), base)
    a, p = _assess(DSL2, w), _assess(_pre(), w)
    if judged:
        assert _norm(a) == _norm(p), "窗外異常：與修前逐值相同"
    else:
        _assert_light_unjudged(a.light, ("週收",))


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
@pytest.mark.parametrize("pos", _OUT_WINDOW)
def test_assess_out_of_window_identical_to_pre(pos, bad):
    w = _wk_at(pos, _BAD[bad])
    a, p = _assess(DSL2, w), _assess(_pre(), w)
    assert _norm(a) == _norm(p)
    assert DSL2.suggest_action(a) == _pre().suggest_action(p)


@pytest.mark.parametrize("pos", [-1, -5, -60])
def test_assess_text_in_weekly_series_keeps_previous_path(pos):
    """週收序列混入字串：窗內 → 均線算不出（型別錯，L3 整列記抓取失敗，既有路徑）；
    窗外 → 照舊判定。兩者皆與修前相同。"""
    w = _wk_at(pos, "abc")
    try:
        p = _assess(_pre(), w)
    except (TypeError, ValueError) as _e:
        with pytest.raises(type(_e)):
            _assess(DSL2, w)
        return
    assert _norm(_assess(DSL2, w)) == _norm(p)


# ══════════════════════════════════════════════════════════════════
# C. 新 UI 端到端：①／待辦／⑦ prompt ／換入
# ══════════════════════════════════════════════════════════════════
def _hold(held: bool = True) -> list[dict]:
    return [{"ticker": "0056", "name": "0056", "asset_kind": "etf", "lots": 1.0,
             "avg_price": 25.0, "held": held},
            {"ticker": "0050", "name": "0050", "asset_kind": "etf", "lots": 3.0,
             "avg_price": 25.0, "held": True}]


_ORIG_PROMPT = S.build_summary_prompt
_ORIG_DIGEST = S.build_station_digest
_ORIG_SWITCH = S.build_switch_advice


def _run(monkeypatch, over: dict, *, vix=15.0, held: bool = True, ds_mod=None, svc_mod=None,
         cands=()):
    """走新 UI 真的 `load_station` → ①／待辦 → `load_switch` → ④ → `load_ai_summary` → ⑦。"""
    monkeypatch.setattr(S, "ds", ds_mod or DSL2)
    _svc = svc_mod or S
    if svc_mod is not None:
        monkeypatch.setattr(svc_mod, "ds", ds_mod or DSL2)

    def mf(tk, kind):
        return _etf_metrics(**(over if tk == "0056" else {}))
    monkeypatch.setattr("src.services.dividend_station_service.get_station_rows",
                        lambda h: (S.build_station_rows(h, vix=vix, metrics_fn=mf), vix))
    # ⚠️ 用載入時存下的本尊，不讀 `S.<名>`：同一個測試內前一次 `_run` 的 monkeypatch 尚未還原。
    monkeypatch.setattr("src.services.dividend_station_service.build_summary_prompt",
                        _svc.build_summary_prompt if svc_mod is not None else _ORIG_PROMPT)
    monkeypatch.setattr("src.services.dividend_station_service.build_switch_advice",
                        _svc.build_switch_advice if svc_mod is not None else _ORIG_SWITCH)
    monkeypatch.setattr("src.services.dividend_station_service.build_station_digest",
                        _svc.build_station_digest if svc_mod is not None else _ORIG_DIGEST)
    monkeypatch.setattr("src.services.dividend_station_service.get_switch_in_candidates",
                        lambda **k: [dict(_c) for _c in cands])
    _cap: dict = {}

    def _gem(prompt, max_tokens=None, **k):
        _cap["prompt"] = prompt
        return "摘要OK"
    monkeypatch.setattr("src.services.app_ai_service.gemini_call", _gem)
    h = PH.HoldingsReadout(requested=True, submitted=True, bound=True,
                           holdings=tuple(_hold(held)))
    st = PH.load_station(h)
    sw = PH.load_switch(st, PH.MacroReadout(requested=True, loaded=False), h)
    swc = PH.build_switch_card(sw, st)
    PH.load_ai_summary(True, st, sw)
    return st, sw, swc, _cap.get("prompt", "")


def _blob(built) -> str:
    card, facts, sig = built
    return repr(card) + repr(tuple(facts)) + sig + PH.v2_card_html(card, facts, sig)


def _cards(st):
    return (PH.build_action_card(st), PH.build_confidence_card(st),
            PH.build_lightwall_card(st), PH.build_todo_card(st))


def _prompt_line(prompt: str, head: str) -> str:
    assert prompt, "⑦ 沒有被呼叫"
    _l = [ln for ln in prompt.splitlines() if ln.startswith(head)]
    assert len(_l) == 1, prompt
    return _l[0]


#: 情境：(覆寫, VIX, 0056 的 235 說明, 兩列都異常?)
_PAGE_CASES = {
    **{f"wk_last_{b}": ({"weekly_close": _wk_at(-1, v)}, 15.0, ("週收",), False)
       for b, v in _BAD.items()},
    **{f"wk_m5_{b}": ({"weekly_close": _wk_at(-5, v)}, 15.0, ("週收",), False)
       for b, v in _BAD.items()},
    **{f"wk_m30_{b}": ({"weekly_close": _wk_at(-30, v)}, 15.0, ("週收",), False)
       for b, v in _BAD.items()},
    "wk_hole_nan": ({"weekly_close": _wk_at(-3, float("nan"))}, 15.0, ("週收",), False),
    # VIX 是全站同一個值 → 兩列的 235 都不下結論。VIX=35 時修前會亮 🔴 崩盤加碼。
    **{f"vix_{b}": ({}, v, ("VIX",), True) for b, v in _BAD_ANY.items() if b != "obj"},
}


@pytest.mark.parametrize("case", list(_PAGE_CASES))
def test_page_235_invalid_does_not_conclude(case, monkeypatch):
    over, vix, items, both = _PAGE_CASES[case]
    st, sw, swc, prompt = _run(monkeypatch, over, vix=vix)
    _txt = "".join(_sentence(_i) for _i in items)
    rows = {r["代號"]: r for r in st.rows}
    _bad_rows = ("0056", "0050") if both else ("0056",)
    for _code in _bad_rows:
        r = rows[_code]
        assert r["_detail"]["235觸發"] == _txt and r["加碼金"] == ""
        assert r["_detail"]["深水防守"] == "—"
        assert SS.KEY_LIGHT235 in r[SS.KEY_INVALID_LIGHTS]
        cell = {c.key: c for c in r["_lights"]}[SS.KEY_LIGHT235]
        assert (cell.level, cell.state, cell.miss_reason) == ("⚪", SS.STATE_MISSING, "")
        _no_nonfinite(repr(r["_detail"]) + repr(r["_lights"]) + r["235 燈號"])
    assert st.add_n == 0 and not st.digest["adds"]
    assert st.judged < st.total_lights and st.unjudged_rows >= 1
    action, _f, sig = PH.build_action_card(st)
    assert "加碼燈" not in action.value and "巡航" not in action.value and sig == ""
    todo = PH.build_todo_card(st)[0]
    assert todo.value.startswith("加碼 0 · ")
    assert _prompt_line(prompt, "- 235 加碼觸發：") == "- 235 加碼觸發：無"
    if both:
        assert _prompt_line(prompt, "- 目前 VIX：") == "- 目前 VIX：" + _sentence("VIX")
    for _b in _cards(st) + (swc,):
        _no_nonfinite(_blob(_b))
    _no_nonfinite(prompt)


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_page_qa_repro_no_add_signal(bad, monkeypatch):
    """QA h50/extra 情境：持有 0056 週收 iloc[-5] 異常、VIX=15。"""
    st, _sw, _swc, prompt = _run(monkeypatch, {"weekly_close": _wk_at(-5, _BAD[bad])})
    assert st.add_n == 0
    assert "1 檔亮加碼燈" not in PH.build_action_card(st)[0].value
    assert "急跌加碼" not in prompt and "0056 🟡" not in prompt


_POOL = ({"代碼": "00878", "名稱": "池子候選", "綜合分": 80},)
#: 只有 235 異常的情境（健檢 A–D 照常 🟢）：(覆寫, VIX)。
_SW_235_ONLY = {
    **{f"vix_{b}": ({}, v) for b, v in _BAD_ANY.items() if b != "obj"},
    **{f"wk_m30_{b}": ({"weekly_close": _wk_at(-30, v)}, 15.0) for b, v in _BAD.items()},
}


@pytest.mark.parametrize("case", list(_SW_235_ONLY))
def test_switch_235_invalid_does_not_change_switch_in(case, monkeypatch):
    """QA D2：換入規則只看健檢，不看 235／VIX → 235 異常**不**連帶排除換入。
    選股池**有候選**，才驗得到「不會改推選股池」：仍推觀察清單 0056，與正常時（修前）相同。"""
    over, vix = _SW_235_ONLY[case]
    st, sw, (card, facts, _s), prompt = _run(monkeypatch, over, vix=vix, held=False,
                                            cands=_POOL)
    row = next(_r for _r in st.rows if _r["代號"] == "0056")
    assert row["健檢"] == "🟢" and SS.KEY_LIGHT235 in row[SS.KEY_INVALID_LIGHTS]
    assert row[SS.KEY_INVALID_LIGHTS] == (SS.KEY_LIGHT235,), "健檢類沒有異常"
    assert (sw.switch_in_src, [d["代號"] for d in sw.switch_in]) == ("watchlist", ["0056"])
    _n_st, n_sw, (n_card, n_facts, _n_s), _n_p = _run(monkeypatch, {}, vix=15.0, held=False,
                                                       cands=_POOL)
    assert (sw.switch_in, sw.switch_in_src) == (n_sw.switch_in, n_sw.switch_in_src)
    assert card.value == n_card.value
    assert dict(facts)["建議換入（來源：你的觀察清單）"] == dict(n_facts)["建議換入（來源：你的觀察清單）"]
    assert "00878" not in prompt


#: 只有 3-3-3 異常的情境（健檢 A–D 照常 🟢）：(覆寫, 預期 `_invalid_lights`)。
_SW_333_ONLY = {
    **{f"inception_{b}": ({"inception_years": v}, (SS.KEY_SCREEN_INCEPTION,))
       for b, v in _BAD_ANY.items()},
    **{f"ann_{b}": ({"ann_return_3y_pct": v}, (SS.KEY_SCREEN_RETURN,)) for b, v in _BAD.items()},
    **{f"peer_{b}": ({"peer_ranks": {3: .2, 6: v, 12: .2}}, (SS.KEY_SCREEN_PEER,))
       for b, v in _BAD.items()},
    "all_three": ({"inception_years": float("nan"), "cum_return_3y_pct": float("inf"),
                   "peer_ranks": {3: float("-inf"), 6: .2, 12: .2}},
                  (SS.KEY_SCREEN_INCEPTION, SS.KEY_SCREEN_RETURN, SS.KEY_SCREEN_PEER)),
    "333_and_235": ({"inception_years": float("nan"), "weekly_close": _wk_at(-30, float("inf"))},
                    (SS.KEY_SCREEN_INCEPTION, SS.KEY_LIGHT235)),
}


@pytest.mark.parametrize("case", list(_SW_333_ONLY))
def test_switch_333_invalid_does_not_change_switch_in(case, monkeypatch):
    """⚠️ 有意的規則修正（總管 2026-10-13 裁定）：換入規則本來就不看 3-3-3 → 3-3-3 異常**不**
    連帶排除換入（Z50 曾一併排除，屬判斷過寬）。選股池有候選：仍推觀察清單 0056，與正常時相同。"""
    over, want = _SW_333_ONLY[case]
    st, sw, (card, facts, _s), prompt = _run(monkeypatch, over, held=False, cands=_POOL)
    row = next(_r for _r in st.rows if _r["代號"] == "0056")
    assert row["健檢"] == "🟢" and row[SS.KEY_INVALID_LIGHTS] == want
    assert (sw.switch_in_src, [d["代號"] for d in sw.switch_in]) == ("watchlist", ["0056"])
    _n_st, n_sw, (n_card, _nf, _ns), _np = _run(monkeypatch, {}, held=False, cands=_POOL)
    assert (sw.switch_in, sw.switch_in_src, card.value) == \
        (n_sw.switch_in, n_sw.switch_in_src, n_card.value)
    assert "00878" not in prompt


@pytest.mark.parametrize("case", ["A_yield", "D_premium", "C_last"])
def test_switch_health_invalid_with_333_still_excluded(case, monkeypatch):
    """健檢 A／C／D 異常照舊排除換入，即使同列也有 3-3-3／235 異常。"""
    over = {"A_yield": {"annual_yield_pct": float("nan")},
            "D_premium": {"premium_pct": float("inf")},
            "C_last": {"weekly_close": _wk_at(-1, float("-inf"))}}[case]
    _st, sw, _c, _p = _run(monkeypatch, {**over, "inception_years": float("nan")}, held=False,
                           cands=_POOL)
    assert (sw.switch_in_src, [d["代號"] for d in sw.switch_in]) == ("screener", ["00878"])


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_switch_health_c_invalid_still_excluded(bad, monkeypatch):
    """健檢C 會直接影響換入（`健檢` 欄）→ 異常時照舊排除（Z50），改由選股池遞補。"""
    st, sw, _c, _p = _run(monkeypatch, {"weekly_close": _wk_at(-1, _BAD[bad])}, held=False,
                          cands=_POOL)
    row = next(_r for _r in st.rows if _r["代號"] == "0056")
    assert row[SS.KEY_INVALID_LIGHTS] == (SS.KEY_HEALTH_C, SS.KEY_LIGHT235)
    assert (sw.switch_in_src, [d["代號"] for d in sw.switch_in]) == ("screener", ["00878"])


# ══════════════════════════════════════════════════════════════════
# D. 正常路徑與一般缺資料：與修前逐值相同
# ══════════════════════════════════════════════════════════════════
_VIXES = (None, 15.0, 22.0, 27.0, 35.0)
_CLOSE_MA = ((None, None, None, None), (110.0, 105.0, 100.0, 95.0), (90.0, 95.0, 100.0, 110.0),
             (80.0, 95.0, 90.0, 100.0), (90.0, None, 100.0, None), (100.0, 95.0, None, None),
             (None, 95.0, 100.0, 110.0), (96.0, 95.0, 97.0, 120.0))
_ZS = (None, -3.5, -2.5, -1.5, -0.5, 0.0, 2.5, 3.5)


@pytest.mark.parametrize("vix,cm,z", list(itertools.product(_VIXES, _CLOSE_MA, _ZS)), ids=repr)
def test_normal_light_235_identical_to_pre(vix, cm, z):
    wc, m4, m13, m52 = cm
    kw = dict(vix=vix, weekly_close=wc, ma4w=m4, ma13w=m13, ma52w=m52, z=z)
    assert _norm(DSL2.light_235(**kw)) == _norm(_pre().light_235(**kw))


def _normal_weeklies():
    rng = np.random.default_rng(51)
    out = [_WK, _WK[::-1].set_axis(_IDX), pd.Series(25.0, index=_IDX)]
    out += [_WK.iloc[-n:] for n in (1, 3, 4, 5, 12, 13, 14, 19, 20, 21, 51, 52, 53)]
    for _ in range(10):
        n = int(rng.choice([14, 30, 60, 120]))
        out.append(pd.Series(30 + np.cumsum(rng.normal(0, 1.5, n)),
                             index=pd.date_range("2024-01-05", periods=n, freq="W-FRI")))
    return out


@pytest.mark.parametrize("vix", _VIXES)
@pytest.mark.parametrize("i", range(len(_normal_weeklies())))
def test_normal_assessment_identical_to_pre(i, vix):
    w = _normal_weeklies()[i]
    a, p = _assess(DSL2, w, vix=vix), _assess(_pre(), w, vix=vix)
    assert _norm(a) == _norm(p)
    assert _norm(DSL2.light_cells(a)) == _norm(_pre().light_cells(p))
    assert DSL2.suggest_action(a) == _pre().suggest_action(p)
    assert a.light.invalid is False


_NORMAL_OVERS = [{}, {"weekly_close": _WK[::-1].set_axis(_IDX)},
                 {"weekly_close": _WK.iloc[-10:]}, {"weekly_close": _WK.iloc[-3:]},
                 {"weekly_close": pd.Series(np.linspace(30, 20, 120), index=_IDX)},
                 {"premium_pct": None}, {"sharpe": -0.3}]


@pytest.mark.parametrize("vix", [None, 15.0, 22.0, 35.0])
@pytest.mark.parametrize("held", [True, False])
@pytest.mark.parametrize("over", _NORMAL_OVERS, ids=repr)
def test_normal_page_identical_to_pre(over, held, vix, monkeypatch):
    new = _run(monkeypatch, over, vix=vix, held=held)
    pre = _run(monkeypatch, over, vix=vix, held=held, ds_mod=_pre(), svc_mod=_svc_pre())
    assert all(SS.KEY_INVALID_LIGHTS not in _r for _r in new[0].rows)
    assert _norm(new[0].rows) == _norm(pre[0].rows)
    for _a, _b in zip(_cards(new[0]), _cards(pre[0])):
        assert _blob(_a) == _blob(_b)
    assert new[1] == pre[1] and _blob(new[2]) == _blob(pre[2])
    assert new[3] == pre[3]


@pytest.mark.parametrize("vix", [None, 0.0, 15.0, 15.04, 99.95])
def test_normal_prompt_vix_text_identical_to_pre(vix):
    d = {"vix": vix, "total": 1, "reds": [], "adds": [], "errors": []}
    assert S.build_summary_prompt(d) == _svc_pre().build_summary_prompt(d)


# ══════════════════════════════════════════════════════════════════
# E. revert-pair 突變：每一環一組
# ══════════════════════════════════════════════════════════════════
def test_mut_guard_reopens_add_signal(monkeypatch):
    """拔掉 L2 閘門 → QA 重現：🟡 急跌加碼 30%「週收<季線」、① 1 檔亮加碼燈、⑦ 帶到。"""
    m = _variant(_L2, (Z51_L2_GUARD_PAIR,), "_z51_no_guard")
    a = _assess(m, _wk_at(-5, float("inf")), vix=15.0)
    assert (a.light.light, a.light.deploy_pct, a.light.reasons) == \
        (T.LIGHT_2, T.DEPLOY_LIGHT2_PCT, ["週收<季線"]), "拔掉 → 修前的錯誤加碼燈重現"
    st, _sw, _swc, prompt = _run(monkeypatch, {"weekly_close": _wk_at(-5, float("inf"))},
                                 ds_mod=m)
    assert st.add_n == 1 and "1 檔亮加碼燈" in PH.build_action_card(st)[0].value
    assert "加碼 1 · " in PH.build_todo_card(st)[0].value
    assert "0056 🟡 急跌加碼 加碼30%" in _prompt_line(prompt, "- 235 加碼觸發：")
    st2, *_r = _run(monkeypatch, {"weekly_close": _wk_at(-5, float("inf"))})
    assert st2.add_n == 0


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_mut_guard_reopens_vix_light(bad):
    """拔掉 L2 閘門 → VIX 異常時回到修前：+inf 亮 🔴 崩盤加碼；NaN／-inf 當缺軸照判其餘軸。"""
    m = _variant(_L2, (Z51_L2_GUARD_PAIR,), "_z51_no_guard")
    lt = m.light_235(**{**_GOOD, "vix": _BAD[bad]})
    assert lt.invalid is False and lt.deploy_pct > 0, "拔掉 → 修前的加碼結論重現"
    assert DSL2.light_235(**{**_GOOD, "vix": _BAD[bad]}).deploy_pct == 0.0


@pytest.mark.parametrize("w", [_wk_at(-3, float("nan")),
                               _wk_at(-15, float("inf"), _WK.iloc[-30:])],
                         ids=["nan_hole", "inf_only_in_boll_window"])
def test_mut_window_reopens_conclusion(w):
    """只拔「逐筆看窗」→ 純量看不出的窗內異常（NaN 被 skipna 跳過／布林 z 回 None）漏網。"""
    m = _variant(_L2, (Z51_L2_WINDOW_PAIR,), "_z51_no_window")
    a_m = _assess(m, w)
    assert a_m.light.invalid is False and a_m.light.axes_used, "拔掉 → 修前照判（或當缺軸）重現"
    _assert_light_unjudged(_assess(DSL2, w).light, ("週收",))


def test_mut_agg_drops_structured_flag(monkeypatch):
    """只拔「彙整進 invalid_keys」→ 列上的結構化旗標 `_invalid_lights` 不再標出 235 異常。"""
    m = _variant(_L2, (Z51_L2_AGG_PAIR,), "_z51_no_agg")
    over = {"weekly_close": _wk_at(-30, float("inf"))}
    st, *_r = _run(monkeypatch, over, held=False, ds_mod=m)
    assert SS.KEY_INVALID_LIGHTS not in next(_x for _x in st.rows if _x["代號"] == "0056")
    st2, *_r2 = _run(monkeypatch, over, held=False)
    assert next(_x for _x in st2.rows if _x["代號"] == "0056")[SS.KEY_INVALID_LIGHTS] == \
        (SS.KEY_LIGHT235,)


@pytest.mark.parametrize("over", [{"inception_years": float("nan")},
                                  {"ann_return_3y_pct": float("inf")},
                                  {"peer_ranks": {3: .2, 6: float("-inf"), 12: .2}}], ids=repr)
def test_mut_switch_333_reopens_over_exclusion(over, monkeypatch):
    """只拔 L3「3-3-3 不連帶排除」→ Z50 的過寬排除重現：觀察清單 0056 改由選股池遞補。"""
    m = _variant(_SVC, (Z51_L3_SWITCH_333_PAIR,), "_z51_no_switch_333")
    _st, sw, _c, _p = _run(monkeypatch, over, held=False, svc_mod=m, cands=_POOL)
    assert (sw.switch_in_src, [d["代號"] for d in sw.switch_in]) == ("screener", ["00878"]), \
        "拔掉 → 3-3-3 異常連帶排除換入重現"
    _st2, sw2, _c2, _p2 = _run(monkeypatch, over, held=False, cands=_POOL)
    assert (sw2.switch_in_src, [d["代號"] for d in sw2.switch_in]) == ("watchlist", ["0056"])


@pytest.mark.parametrize("bad", ["nan", "pos_inf", "text"])
def test_mut_switch_reopens_over_exclusion(bad, monkeypatch):
    """只拔 L3「235 不連帶排除」→ QA D2 重現：VIX 異常讓觀察清單 0056 改由選股池遞補。"""
    m = _variant(_SVC, (Z51_L3_SWITCH_PAIR,), "_z51_no_switch_ignore")
    _st, sw, _c, _p = _run(monkeypatch, {}, vix=_BAD_ANY[bad], held=False, svc_mod=m,
                           cands=_POOL)
    assert (sw.switch_in_src, [d["代號"] for d in sw.switch_in]) == ("screener", ["00878"]), \
        "拔掉 → 修前的過度排除重現"
    _st2, sw2, _c2, _p2 = _run(monkeypatch, {}, vix=_BAD_ANY[bad], held=False, cands=_POOL)
    assert (sw2.switch_in_src, [d["代號"] for d in sw2.switch_in]) == ("watchlist", ["0056"])


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_mut_l3_vix_text_reopens_nonfinite(bad, monkeypatch):
    m = _variant(_SVC, (Z51_L3_VIX_PAIR,), "_z51_no_vix_text")
    d = {"vix": _BAD[bad], "total": 1, "reds": [], "adds": [], "errors": []}
    assert _NONFINITE_RE.search(m.build_summary_prompt(d)), "拔掉 → ⑦ prompt 出現 nan／inf"
    _no_nonfinite(S.build_summary_prompt(d))
    _st, _sw, _swc, prompt = _run(monkeypatch, {}, vix=_BAD[bad], svc_mod=m)
    assert _NONFINITE_RE.search(prompt)


# ══════════════════════════════════════════════════════════════════
# F. ⑦ AI 輸入：資料異常未判 → 附事實列、不送「續抱」指示（QA D1／Z50-n3）
# ══════════════════════════════════════════════════════════════════
#  呼叫鏈（新 UI）：`page_hold.load_ai_summary` → L3 `build_ai_summary(digest, …)` →
#  `build_summary_prompt`；digest ＝ `load_station` 裡 L3 `build_station_digest(rows, vix)`。
#  旗標鏈：L2 `invalid_keys` ＋ 各燈客戶句 → L3 `row_from_assessment` 的
#  `SS.KEY_INVALID_TEXTS`（只有異常才有）→ digest `invalid`（只有異常才有）→ prompt。
_KEEP = "沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。"
_FACT_HEAD = "- 資料異常未判："


def _fact(*rows: tuple[str, tuple[tuple[str, str], ...]]) -> str:
    return _FACT_HEAD + "、".join(
        f"{_c}（" + "　".join(f"{_l}：{_t}" for _l, _t in _items) + "）" for _c, _items in rows)


_WK_C_235 = (("健檢C", _sentence("週收")), ("235", _sentence("週收")))
_PROMPT_CASES = {
    **{f"wk_last_{b}": ({"weekly_close": _wk_at(-1, v)}, 15.0, (("0056", _WK_C_235),))
       for b, v in _BAD.items()},
    **{f"wk_m5_{b}": ({"weekly_close": _wk_at(-5, v)}, 15.0, (("0056", _WK_C_235),))
       for b, v in _BAD.items()},
    **{f"wk_m30_{b}": ({"weekly_close": _wk_at(-30, v)}, 15.0,
                       (("0056", (("235", _sentence("週收")),)),)) for b, v in _BAD.items()},
    **{f"vix_{b}": ({}, v, tuple((_c, (("235", _sentence("VIX")),)) for _c in ("0056", "0050")))
       for b, v in _BAD_ANY.items() if b != "obj"},
    "health_d": ({"premium_pct": float("nan")}, 15.0,
                 (("0056", (("健檢D", _sentence("折溢價")),)),)),
    "health_a": ({"annual_yield_pct": float("inf")}, 15.0,
                 (("0056", (("健檢A", _sentence("配息率")),)),)),
    "333_ann": ({"ann_return_3y_pct": float("nan")}, 15.0,
                (("0056", (("3-3-3", _sentence("近三年年化報酬")),)),)),
    "333_two": ({"inception_years": float("nan"), "peer_ranks": {3: .2, 6: float("inf"), 12: .2}},
                15.0, (("0056", (("3-3-3", _sentence("成立年數") + _sentence("同儕排名")),)),)),
    "d_and_235": ({"premium_pct": float("-inf"), "weekly_close": _wk_at(-30, float("inf"))}, 15.0,
                  (("0056", (("健檢D", _sentence("折溢價")), ("235", _sentence("週收")))),)),
}


@pytest.mark.parametrize("held", [True, False])
@pytest.mark.parametrize("case", list(_PROMPT_CASES))
def test_prompt_lists_invalid_and_drops_keep_instruction(case, held, monkeypatch):
    over, vix, want = _PROMPT_CASES[case]
    _st, _sw, _swc, prompt = _run(monkeypatch, over, vix=vix, held=held, cands=_POOL)
    assert "續抱、定期定額即可" not in prompt, "資料異常未判時不得引導 AI 說續抱"
    assert _prompt_line(prompt, _FACT_HEAD) == _fact(*want)
    _no_nonfinite(prompt)
    # 除了拿掉那句指示、加上事實列之外，prompt 其餘逐字同修前（不新增任何指示或文案）。
    _st_p, _sw_p, _swc_p, pre = _run(monkeypatch, over, vix=vix, held=held, cands=_POOL,
                                     svc_mod=_variant(_SVC, (Z51_L3_PROMPT_PAIR,),
                                                      "_z51_no_prompt"))
    assert _FACT_HEAD not in pre
    if _st.digest.get("data_short"):
        # 複驗 C MAJOR-1/2（XV-H1-EXT 單一判定，取代 Z51 該部分語意）：持有列燈資料異常 ⇒ 組合層
        # 資料不足（例：VIX 異常 ⇒ 持有列 235 燈異常）⇒ 修前（拔 Z51 prompt 環）與修後都帶資料不足指示、都不帶續抱句。
        assert _KEEP not in pre and S._INSUFFICIENT_INSTRUCTION in pre
        assert S._INSUFFICIENT_INSTRUCTION in prompt
    else:
        assert _KEEP in pre
    assert prompt == pre.replace(_KEEP, "").replace(
        _prompt_line(pre, "- 抓取失敗未納入：") + "\n",
        _prompt_line(pre, "- 抓取失敗未納入：") + "\n" + _fact(*want) + "\n")


def test_prompt_digest_carries_structured_rows(monkeypatch):
    st, *_r = _run(monkeypatch, {"weekly_close": _wk_at(-1, float("inf"))})
    assert st.digest["invalid"] == [{"代號": "0056", "項目": _WK_C_235}]
    row = next(_x for _x in st.rows if _x["代號"] == "0056")
    assert row[SS.KEY_INVALID_TEXTS] == _WK_C_235


@pytest.mark.parametrize("vix", [None, 15.0, 35.0])
@pytest.mark.parametrize("over", _NORMAL_OVERS + [{"premium_pct": None}, {"sharpe": None},
                                                  {"weekly_close": _WK.iloc[-2:]}], ids=repr)
def test_prompt_normal_identical_and_keeps_instruction(over, vix, monkeypatch):
    """沒有異常（含一般缺資料）：digest 沒有 `invalid` 鍵、prompt 與修前逐字相同、仍帶「續抱」指示。

    XV-H1-EXT（客戶 2026-10-28 裁示，取代 Z51 該部分語意）：本參數組都是「部分燈缺、但不是
    每一盞都判不出、持有列有現價」⇒ 依新規則仍屬可下結論 ⇒ 續抱句斷言保留；
    「燈全判不出／缺現價／抓取失敗」改由下方 `test_prompt_missing_price_drops_instruction` 等斷言不出現。
    """
    st, _sw, _swc, prompt = _run(monkeypatch, over, vix=vix)
    assert "invalid" not in st.digest
    assert all(SS.KEY_INVALID_TEXTS not in _x for _x in st.rows)
    _st2, _sw2, _swc2, pre = _run(monkeypatch, over, vix=vix, ds_mod=_pre(), svc_mod=_svc_pre())
    assert prompt == pre and _KEEP in prompt and _FACT_HEAD not in prompt
    assert "insufficient" not in st.digest


@pytest.mark.parametrize("vix", [None, 15.0])
def test_prompt_missing_price_drops_instruction(vix, monkeypatch):
    """XV-H1-EXT（客戶 2026-10-28 裁示，取代 Z51 該部分語意）：持有列缺現價 → 不帶續抱句。"""
    st, _sw, _swc, prompt = _run(monkeypatch, {"current_price": None}, vix=vix)
    assert st.digest["insufficient"] == [{"代號": "0056", "原因": (SS.INSUFF_NO_PRICE,), "held": True}]
    assert _KEEP not in prompt and S._INSUFFICIENT_INSTRUCTION in prompt
    assert "- 資料不足／無法判定（持有）：0056（缺現價）" in prompt


def test_mut_prompt_reopens_keep_instruction(monkeypatch):
    """只拔 prompt 那一環 → QA D1 重現：235 判不出來，AI 仍被要求說「續抱、定期定額即可」。"""
    m = _variant(_SVC, (Z51_L3_PROMPT_PAIR,), "_z51_no_prompt")
    _st, _sw, _c, prompt = _run(monkeypatch, {}, vix=float("nan"), svc_mod=m)
    # 複驗 C（XV-H1-EXT 單一判定）：持有列燈異常另有一道防線（`data_short`）⇒ 續抱句不再重現；
    # 突變仍看得到：異常事實列消失。
    assert _KEEP not in prompt and _FACT_HEAD not in prompt, "拔掉 → 異常事實列消失"
    assert _prompt_line(prompt, "- 235 加碼觸發：") == "- 235 加碼觸發：無"


def test_mut_digest_hides_invalid_from_prompt(monkeypatch):
    m = _variant(_SVC, (Z51_L3_DIGEST_PAIR,), "_z51_no_digest")
    st, _sw, _c, prompt = _run(monkeypatch, {"weekly_close": _wk_at(-30, float("inf"))},
                               svc_mod=m)
    # 複驗 C（XV-H1-EXT 單一判定）：同上，續抱句不再重現；突變看「異常事實列消失」。
    assert "invalid" not in st.digest and _KEEP not in prompt and _FACT_HEAD not in prompt, \
        "拔掉 → ⑦ 看不到資料異常"


def test_mut_l2_agg_hides_235_from_prompt(monkeypatch):
    m = _variant(_L2, (Z51_L2_AGG_PAIR,), "_z51_no_agg")
    _st, _sw, _c, prompt = _run(monkeypatch, {"weekly_close": _wk_at(-30, float("inf"))},
                                ds_mod=m)
    assert _KEEP in prompt and _FACT_HEAD not in prompt, "拔掉 → 235 異常不進 ⑦、續抱引導重現"
