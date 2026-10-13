"""批 Z50 —— 新 UI 持股頁燈牆的健檢C 與 3-3-3：數值異常（NaN／±inf）防呆（沿用批 Z49 客戶裁示）。

客戶裁示（2026-10-13，逐字）：統一採用「{項目}資料異常，無法計算，不下結論。」
  · NaN／±inf／其他無效數值一律視為異常；不顯示 nan／inf；不使用替代值繼續計算；
  · 該數值會影響結論時，該卡停止計算並不下結論；正常資料路徑不得改變。

兩處（獨立 QA 在批 Z49 後實測重現）：
  1. L2 `health_c`：最後一筆週收／13 週季線為 NaN／inf → 亮 🟢「週收 inf vs 季線 inf」。
  2. L2 `screen_333`：近三年年化報酬 NaN → 3 年報酬判 ✅（由累積撐過）；
     成立年數、同儕排名 NaN → 判 ❌。

呼叫鏈（新 UI）：`app._ia_view_hold` → `views.page_hold.render_page_hold` → `load_station`
→ L3 `get_station_rows` → `build_station_rows` → L2 `assess_holding` → `health_c`／`screen_333`
→ L3 `row_from_assessment`（`_detail`、`_lights`＝L2 `light_cells`）→ ① `build_action_card`／
`build_confidence_card`、③ `build_lightwall_card`／`_render_light_wall`。

本檔驗：
  A. L2 兩項各自：NaN／+inf／-inf → 該燈不判定、說明是逐字客戶句、`miss_reason` 留空。
  B. 走新 UI 真的 `load_station()`：燈牆該格 missing、`_detail` 是客戶句、① 與燈牆／可信度／
     待辦卡不出現 nan／inf，也不出現巡航／汰弱結論。
  C. 正常路徑：與修前**逐值相同**（修前＝現行原始碼套上本批 revert pair；該組 revert 與
     `git show 30029a35:src/compute/etf/dividend_station.py`（本批之前）的等價性已在開發時另以
     git 版本跑同一組 C 類測試驗過 —— 測試本身不呼叫 git，見 `tests/test_zz_test_portability.py`）。
  D. revert-pair 突變：每項一組，拔掉本批防呆 → 修前的錯誤燈號／結論重現。
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
from shared import station_specs as SS

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_L2 = "src/compute/etf/dividend_station.py"

_BAD = {"nan": float("nan"), "pos_inf": float("inf"), "neg_inf": float("-inf")}
_NONFINITE_RE = re.compile(r"(?i)(?<![a-z])(nan|inf|infinity)(?![a-z])")


def _sentence(item: str) -> str:
    return f"{item}資料異常，無法計算，不下結論。"


def _no_nonfinite(text: str) -> None:
    _hit = _NONFINITE_RE.search(text)
    assert _hit is None, f"畫面出現 {_hit.group(0)!r}：…{text[max(0, _hit.start() - 40):_hit.end() + 40]}…"


# ══════════════════════════════════════════════════════════════════
# revert-pair（修後逐字, 修前逐字）與變體載入
# ══════════════════════════════════════════════════════════════════
Z50_L2_C_PAIR = (
    "    if any(SS.is_invalid_number(_v) for _v in (close, ma13, slope)):\n"
    "        return Flag(\"⚪\", SS.invalid_data_text(\"週收\"))\n", "")
Z50_L2_333_PAIR = ("        if any(SS.is_invalid_number(_v) for _v in _vs)]",
                   "        if False]")
_PRE_PAIRS = (Z50_L2_C_PAIR, Z50_L2_333_PAIR)


def _exec_module(name: str, path: pathlib.Path, code: str) -> types.ModuleType:
    m = types.ModuleType(name)
    m.__file__ = str(path)
    sys.modules[name] = m           # dataclass 解析註解需要模組已註冊
    exec(compile(code, str(path), "exec"), m.__dict__)
    return m


@functools.lru_cache(maxsize=None)
def _variant(pairs: tuple[tuple[str, str], ...], name: str) -> types.ModuleType:
    """現行 L2 原始碼只套 `pairs`（修後 → 修前），載成獨立模組物件（不影響本尊）。"""
    path = _ROOT / _L2
    code = path.read_text(encoding="utf-8")
    for new, old in pairs:
        assert code.count(new) == 1, f"替換點不唯一或已不存在：{new[:70]!r}"
        code = code.replace(new, old)
    return _exec_module(name, path, code)


def _pre() -> types.ModuleType:
    """修前行為：現行 L2 套上本批**全部** revert pair。"""
    return _variant(_PRE_PAIRS, "_z50_pre_dividend_station")


# ══════════════════════════════════════════════════════════════════
# 合成資料（確定性）
# ══════════════════════════════════════════════════════════════════
_IDX = pd.date_range("2023-01-06", periods=120, freq="W-FRI")
_WK = pd.Series(np.linspace(20, 30, 120), index=_IDX)
_PEER_OK = {3: .2, 6: .2, 12: .2}


def _wk_last(v) -> pd.Series:
    w = _WK.copy()
    w.iloc[-1] = v
    return w


def _etf_metrics(**over) -> dict:
    base = dict(weekly_close=_WK, premium_pct=0.3, sharpe=0.8, total_return_1y_pct=10.0,
                annual_yield_pct=5.0, inception_years=5.0, ann_return_3y_pct=8.0,
                cum_return_3y_pct=25.0, peer_ranks=dict(_PEER_OK), current_price=30.0)
    base.update(over)
    return base


def _hold() -> list[dict]:
    return [{"ticker": "0056", "name": "0056", "asset_kind": "etf", "lots": 1.0,
             "avg_price": 25.0, "held": True}]


def _load(monkeypatch, over: dict):
    """走 L5 真的 `load_station()`（只把 L3 的抓取換成合成指標）。"""
    monkeypatch.setattr(
        "src.services.dividend_station_service.get_station_rows",
        lambda hs: (S.build_station_rows(hs, vix=15.0,
                                         metrics_fn=lambda t, k: _etf_metrics(**over)), 15.0))
    h = PH.HoldingsReadout(requested=True, submitted=True, bound=True, holdings=tuple(_hold()))
    return PH.load_station(h)


def _blob(built) -> str:
    card, facts, sig = built
    return repr(card) + repr(tuple(facts)) + sig + PH.v2_card_html(card, facts, sig)


def _cards(st):
    return (PH.build_action_card(st), PH.build_confidence_card(st),
            PH.build_lightwall_card(st), PH.build_todo_card(st))


def _assert_page_does_not_conclude(st, *, key: str, detail_key: str, want_detail_part: str,
                                   unjudged_level: str):
    row = st.rows[0]
    assert want_detail_part in row["_detail"][detail_key]
    cell = {c.key: c for c in row["_lights"]}[key]
    assert cell.level == unjudged_level and cell.state == SS.STATE_MISSING
    assert cell.miss_reason == "", "異常不是「沒有值」，不登記 MISS_*"
    assert st.cut_n == 0, "異常燈不得計入汰弱"
    assert st.judged < st.total_lights and st.tally[SS.STATE_MISSING] >= 1
    card, _f, sig = PH.build_action_card(st)
    assert "巡航" not in card.value and "今天沒有" not in card.value and sig == "", \
        "異常燈不得打開巡航／不得說有動作"
    assert "汰弱" not in card.value
    for _b in _cards(st):
        _no_nonfinite(_blob(_b))
    _no_nonfinite(repr(row["_detail"]))
    _no_nonfinite(repr(row["_lights"]))


# ══════════════════════════════════════════════════════════════════
# A. L2
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_l2_health_c_invalid_last_close_is_unjudged(bad):
    f = DSL2.health_c(_wk_last(_BAD[bad]))
    assert f.level == "⚪" and f.msg == _sentence("週收") and f.miss_reason == ""


@pytest.mark.parametrize("bad", ["pos_inf", "neg_inf"])
def test_l2_health_c_invalid_ma13_is_unjudged(bad):
    """季線窗內有 ±inf（最後一筆有限）→ 季線／斜率非有限 → 同樣不判定。"""
    w = _WK.copy()
    w.iloc[-5] = _BAD[bad]
    f = DSL2.health_c(w)
    assert f.level == "⚪" and f.msg == _sentence("週收") and f.miss_reason == ""


_333_BASE = dict(inception_years=5.0, ann_return_3y_pct=8.0, cum_return_3y_pct=25.0,
                 peer_ranks=_PEER_OK)
_333_CASES = {
    # 欄位 → (覆寫, 子項屬性, 子項 key, 項目名)
    "inception": (lambda v: {"inception_years": v}, "inception_ok", SS.KEY_SCREEN_INCEPTION,
                  "成立年數"),
    "ann3y": (lambda v: {"ann_return_3y_pct": v}, "return_ok", SS.KEY_SCREEN_RETURN,
              "近三年年化報酬"),
    "cum3y": (lambda v: {"cum_return_3y_pct": v}, "return_ok", SS.KEY_SCREEN_RETURN,
              "近三年累積報酬"),
    "peer_all": (lambda v: {"peer_ranks": {3: v, 6: v, 12: v}}, "peer_ok", SS.KEY_SCREEN_PEER,
                 "同儕排名"),
    "peer_one": (lambda v: {"peer_ranks": {3: .2, 6: v, 12: .2}}, "peer_ok", SS.KEY_SCREEN_PEER,
                 "同儕排名"),
}


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
@pytest.mark.parametrize("case", list(_333_CASES))
def test_l2_screen_333_invalid_input_is_unjudged(case, bad):
    over, attr, key, item = _333_CASES[case]
    sc = DSL2.screen_333(**{**_333_BASE, **over(_BAD[bad])})
    assert getattr(sc, attr) is None, "異常子項不得判 ✅／❌"
    for _other in {"inception_ok", "return_ok", "peer_ok"} - {attr}:
        assert getattr(sc, _other) is True, "其他子項照常判定"
    assert sc.passed is False
    assert key not in sc.miss_reasons, "異常不是「沒有值」，不登記 MISS_*"
    assert sc.detail.endswith(_sentence(item))
    _no_nonfinite(sc.detail)


def test_l2_screen_333_multiple_invalid_listed_in_order():
    n = float("nan")
    sc = DSL2.screen_333(inception_years=n, ann_return_3y_pct=n, cum_return_3y_pct=n,
                         peer_ranks={3: n, 6: n, 12: n})
    assert (sc.inception_ok, sc.return_ok, sc.peer_ok, sc.passed) == (None, None, None, False)
    assert sc.miss_reasons == {}
    assert sc.detail == ("成立❔　3年報酬❔　同儕前1/3❔　" + _sentence("成立年數")
                         + _sentence("近三年年化報酬") + _sentence("近三年累積報酬")
                         + _sentence("同儕排名"))


# ══════════════════════════════════════════════════════════════════
# B. 新 UI 持股頁：燈牆 ＋ ① 該做什麼／可信度
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
def test_page_health_c_does_not_conclude(bad, monkeypatch):
    st = _load(monkeypatch, {"weekly_close": _wk_last(_BAD[bad])})
    assert st.rows[0]["_detail"]["健檢C"] == _sentence("週收")
    _assert_page_does_not_conclude(st, key=SS.KEY_HEALTH_C, detail_key="健檢C",
                                   want_detail_part=_sentence("週收"), unjudged_level="⚪")


_PAGE_333 = {
    "inception": ("inception_years", SS.KEY_SCREEN_INCEPTION, "成立年數"),
    "ann3y": ("ann_return_3y_pct", SS.KEY_SCREEN_RETURN, "近三年年化報酬"),
    "peer": ("peer_ranks", SS.KEY_SCREEN_PEER, "同儕排名"),
}


@pytest.mark.parametrize("bad", list(_BAD), ids=list(_BAD))
@pytest.mark.parametrize("case", list(_PAGE_333))
def test_page_screen_333_does_not_conclude(case, bad, monkeypatch):
    field, key, item = _PAGE_333[case]
    v = _BAD[bad]
    st = _load(monkeypatch, {field: ({3: v, 6: v, 12: v} if field == "peer_ranks" else v)})
    _assert_page_does_not_conclude(st, key=key, detail_key="3-3-3明細",
                                   want_detail_part=_sentence(item), unjudged_level="❔")
    assert st.tally[SS.STATE_MISSING] == 1 and st.judged == st.total_lights - 1


# ══════════════════════════════════════════════════════════════════
# C. 正常路徑與修前逐值相同
# ══════════════════════════════════════════════════════════════════
def _normal_weeklies():
    rng = np.random.default_rng(50)
    out = [_WK, _WK[::-1].set_axis(_IDX), pd.Series(25.0, index=_IDX),
           _WK.iloc[:12], _WK.iloc[:13], _WK.iloc[:14], _WK.iloc[:1]]
    for _ in range(12):
        out.append(pd.Series(30 + np.cumsum(rng.normal(0, 1, 60)),
                             index=pd.date_range("2024-01-05", periods=60, freq="W-FRI")))
    # 窗內有 NaN 破洞（skipna 照算，本批不動）：
    w = _WK.copy()
    w.iloc[-5] = float("nan")
    out.append(w)
    return out


@pytest.mark.parametrize("i", range(len(_normal_weeklies())))
def test_normal_health_c_identical_to_pre(i):
    w = _normal_weeklies()[i]
    assert dataclasses.asdict(DSL2.health_c(w)) == dataclasses.asdict(_pre().health_c(w))


_INC = (None, 0.0, 2.9, 3.0, 5.0, -1.0)
_ANN = (None, -5.0, 6.9, 7.0, 12.0)
_CUM = (None, 0.0, 20.9, 21.0, 40.0)
_PEER = (None, {}, {3: .2}, {3: .2, 6: .2, 12: .2}, {3: .5, 6: .2, 12: .2},
         {3: 1 / 3, 6: 1 / 3, 12: 1 / 3}, {3: .2, 6: None, 12: .2}, {3: 0.0, 6: 1.0, 12: .1})


@pytest.mark.parametrize("inc,ann,cum,peer", list(itertools.product(_INC, _ANN, _CUM, _PEER)),
                         ids=repr)
def test_normal_screen_333_identical_to_pre(inc, ann, cum, peer):
    kw = dict(inception_years=inc, ann_return_3y_pct=ann, cum_return_3y_pct=cum, peer_ranks=peer)
    assert dataclasses.asdict(DSL2.screen_333(**kw)) == dataclasses.asdict(_pre().screen_333(**kw))


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
    return x


_NORMAL_OVERS = [{}, {"weekly_close": _WK[::-1].set_axis(_IDX)}, {"inception_years": 2.0},
                 {"ann_return_3y_pct": 5.0, "cum_return_3y_pct": 10.0},
                 {"peer_ranks": {3: .5, 6: .2, 12: .2}}, {"peer_ranks": None},
                 {"inception_years": None, "ann_return_3y_pct": None, "cum_return_3y_pct": None},
                 {"weekly_close": _WK.iloc[:10]}]


@pytest.mark.parametrize("over", _NORMAL_OVERS, ids=repr)
def test_normal_rows_and_page_identical_to_pre(over, monkeypatch):
    st_new = _load(monkeypatch, over)
    rows_new = S.build_station_rows(_hold(), vix=15.0, metrics_fn=lambda t, k: _etf_metrics(**over))
    monkeypatch.setattr(S, "ds", _pre())
    st_pre = _load(monkeypatch, over)
    rows_pre = S.build_station_rows(_hold(), vix=15.0, metrics_fn=lambda t, k: _etf_metrics(**over))
    assert _norm(rows_new) == _norm(rows_pre)
    for _a, _b in zip(_cards(st_new), _cards(st_pre)):
        assert _blob(_a) == _blob(_b)


# ══════════════════════════════════════════════════════════════════
# D. revert-pair 突變：每項一組
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("bad,pre_level", [("nan", "🟢"), ("pos_inf", "🟢"), ("neg_inf", "🟢")])
def test_mut_health_c(bad, pre_level):
    m = _variant((Z50_L2_C_PAIR,), "_z50_no_health_c")
    f = m.health_c(_wk_last(_BAD[bad]))
    assert f.level == pre_level, "拔掉 → 修前的錯誤燈號重現"
    assert _NONFINITE_RE.search(f.msg), "拔掉 → 修前的 nan／inf 字樣重現"
    assert DSL2.health_c(_wk_last(_BAD[bad])).level == "⚪"


@pytest.mark.parametrize("case,attr,pre_val", [
    ("ann3y", "return_ok", True), ("inception", "inception_ok", False),
    ("peer_all", "peer_ok", False)])
def test_mut_screen_333(case, attr, pre_val):
    m = _variant((Z50_L2_333_PAIR,), "_z50_no_screen_333")
    over = _333_CASES[case][0](float("nan"))
    assert getattr(m.screen_333(**{**_333_BASE, **over}), attr) is pre_val, \
        "拔掉 → 修前的錯誤判定重現"
    assert getattr(DSL2.screen_333(**{**_333_BASE, **over}), attr) is None


def test_mut_screen_333_page_reopens_cruise(monkeypatch):
    """拔掉 → 年化 NaN 被累積撐成 ✅、整面燈判定齊全 → ① 打開巡航（修前的錯誤結論）。"""
    over = {"ann_return_3y_pct": float("nan")}
    monkeypatch.setattr(S, "ds", _variant((Z50_L2_333_PAIR,), "_z50_no_screen_333"))
    st = _load(monkeypatch, over)
    assert st.judged == st.total_lights
    assert "3年報酬✅" in st.rows[0]["_detail"]["3-3-3明細"]
    monkeypatch.setattr(S, "ds", DSL2)
    st2 = _load(monkeypatch, over)
    assert st2.judged == st2.total_lights - 1
    _pre_card = PH.build_action_card(st)[0].value
    _new_card = PH.build_action_card(st2)[0].value
    assert _pre_card == st.cruise_text and _pre_card != _new_card, "拔掉 → ① 巡航結論重現"
