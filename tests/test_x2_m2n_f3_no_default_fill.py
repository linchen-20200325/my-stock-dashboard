"""批 X2：M2N-f3 —— L3 規則引擎 `calculate_system_state` 缺值不再代入預設值（客戶 2026-10-03 放行 L3-G2）。

病史
────────────────────────────────────────────────────────────────
修前 `_f(key, default)` 把缺鍵／None／非數值代成 VIX 20、PMI 50、PMI_Prev 50、M1B 0、M2 0、
BIAS240 0、PCR 1.0、Futures 0（HANDOFF 原列只記前六項；A 組查得 BIAS240、Futures 亦是 0.0），
再拿去算曝險上限（→ `macro_state.json` → 全站建議持股上限）。違 CLAUDE.md §1「缺值 ≠ 0」：
  · M1B、M2 只缺一邊 → spread 變單邊值（缺 M1B ⇒ −M2 扣分＋貼「資金緊縮」；缺 M2 ⇒ +M1B 加分）；
  · NaN／±inf 照樣進分支（VIX＝inf ⇒ 扣 30 分並貼「VIX高波動(inf)」）；
  · 缺了什麼，回傳裡看不出來。

修後契約（見 `calculate_system_state` docstring「缺值契約」）
────────────────────────────────────────────────────────────────
  · 8 個數值輸入任一不是有限數值 → 當缺：用到它的計分項／紅線整條不算；M1B、M2 任一缺 → 資金項整條不算；
  · 回傳多 `missing_inputs`（依 `_ENGINE_NUMERIC_INPUTS` 順序），只在有缺時才帶；
  · 8 個都是有限數值 → 回傳與修前逐字相同（本檔以修前函式逐字副本 `_pre_fix_css` 當對照組）。

本檔釘的東西
  A. 有限數值：隨機＋邊界值 2 萬組，新＝修前（逐字，含 dict 鍵集合）。
  B. 缺值：每個鍵 × 每種缺法（＋隨機多鍵同缺），計分結果＝「修前引擎、把缺的那項換成整條不起作用的值」
     （M1B／M2 任一缺 → 兩個一起換 0）；`missing_inputs` 照實。
  C. 修前確實出事的具體情境（在 origin/main 上這些斷言會紅）。
"""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from src.services import macro_state_locker as M
from src.services.macro_state_locker import (
    MACRO_EXPOSURE_BULLISH_MIN_PCT,
    MACRO_EXPOSURE_NEUTRAL_MIN_PCT,
    MACRO_VETO_FUTURES_EXPOSURE_CAP_PCT,
    MACRO_VETO_FUTURES_NET_SHORT_LOTS,
    MACRO_VETO_PMI_CONTRACTION_LEVEL,
    MACRO_VETO_PMI_EXPOSURE_CAP_PCT,
    MACRO_VETO_SAHM_EXPOSURE_CAP_PCT,
    calculate_system_state,
)

_KEYS = ("VIX_Index", "ISM_PMI_or_OECD_CLI", "PMI_Prev_Month", "M1B_YoY_pct", "M2_YoY_pct",
         "BIAS240_pct", "PCR", "Futures_Net_Short")


# ── 修前函式逐字副本（origin/main 501b45c；註解／docstring 拿掉，程式一字未改）──────────────
def _pre_fix_css(macro_numbers: dict) -> dict:  # noqa: C901 — 逐字副本
    def _b(key):
        v = macro_numbers.get(key)
        if isinstance(v, bool): return v
        return str(v).lower() in ('true', '1', 'yes') if v is not None else False
    def _f(key, default):
        v = macro_numbers.get(key)
        try:
            return float(v) if v is not None else default
        except (ValueError, TypeError):
            return default
    vix         = _f("VIX_Index", 20.0)
    pmi         = _f("ISM_PMI_or_OECD_CLI", 50.0)
    pmi_prev    = _f("PMI_Prev_Month", 50.0)
    m1b_yoy     = _f("M1B_YoY_pct", 0.0)
    m2_yoy      = _f("M2_YoY_pct", 0.0)
    bias240     = _f("BIAS240_pct", 0.0)
    pcr         = _f("PCR", 1.0)
    futures_net = _f("Futures_Net_Short", 0.0)
    sahm        = _b("Sahm_Rule_Triggered")
    below_ma5   = _b("Index_Below_MA5")
    score = 60
    if vix >= 35:    score -= 30
    elif vix >= 28:  score -= 20
    elif vix >= 22:  score -= 10
    elif vix <= 14:  score += 10
    if pmi < 46:     score -= 20
    elif pmi < 50:   score -= 10
    elif pmi > 55:   score += 10
    elif pmi > 52:   score += 5
    spread = m1b_yoy - m2_yoy
    if spread > 3:    score += 15
    elif spread > 0:  score += 5
    elif spread < -3: score -= 10
    if bias240 > 15 and (vix >= 22 or pmi < 50):
        score -= 15
    elif bias240 < -10:
        score += 10
    if pcr > 1.5:   score -= 10
    elif pcr < 0.7: score += 5
    exposure = max(0, min(100, round(score / 10) * 10))
    veto_labels: list[str] = []
    if sahm:
        exposure = min(exposure, MACRO_VETO_SAHM_EXPOSURE_CAP_PCT)
        veto_labels.append("🚨薩姆規則觸發")
    if pmi < MACRO_VETO_PMI_CONTRACTION_LEVEL and pmi_prev < MACRO_VETO_PMI_CONTRACTION_LEVEL:
        exposure = min(exposure, MACRO_VETO_PMI_EXPOSURE_CAP_PCT)
        veto_labels.append(f"⚠️PMI連兩月收縮({pmi_prev:.1f}→{pmi:.1f})")
    if futures_net < MACRO_VETO_FUTURES_NET_SHORT_LOTS and below_ma5:
        exposure = min(exposure, MACRO_VETO_FUTURES_EXPOSURE_CAP_PCT)
        veto_labels.append(f"🚨期貨淨空{abs(futures_net):.0f}口+破MA5")
    if exposure >= MACRO_EXPOSURE_BULLISH_MIN_PCT:   risk_level, regime = "安全", "多頭"
    elif exposure >= MACRO_EXPOSURE_NEUTRAL_MIN_PCT: risk_level, regime = "警告", "震盪"
    else:                                            risk_level, regime = "危險", "空頭"
    labels = veto_labels.copy()
    if pmi < 50 and not any("PMI" in l for l in labels):
        labels.append(f"PMI收縮({pmi:.1f})")
    if vix > 25:
        labels.append(f"VIX高波動({vix:.1f})")
    if spread < 0:
        labels.append("資金緊縮")
    if bias240 > 15 and (vix >= 22 or pmi < 50):
        labels.append("均線過熱")
    macro_phase = "、".join(labels) if labels else "環境正常"
    return {
        "market_regime": regime,
        "systemic_risk_level": risk_level,
        "exposure_limit_pct": exposure,
        "Macro_Phase": macro_phase,
    }


# ── 測資 ────────────────────────────────────────────────────────────────────
#: 各輸入的邊界值（每個門檻兩側＋門檻本身）
_EDGES = {
    "VIX_Index": [5.0, 13.99, 14.0, 14.01, 17.1, 20.0, 21.99, 22.0, 25.0, 25.01, 27.99, 28.0, 34.99, 35.0, 60.0],
    "ISM_PMI_or_OECD_CLI": [40.0, 45.99, 46.0, 47.99, 48.0, 49.99, 50.0, 51.0, 52.0, 52.01, 55.0, 55.01, 60.0],
    "PMI_Prev_Month": [40.0, 47.99, 48.0, 50.0, 56.0],
    "M1B_YoY_pct": [-8.0, -3.0, 0.0, 0.5, 2.0, 3.0, 3.01, 6.5],
    "M2_YoY_pct": [-2.0, 0.0, 0.5, 3.0, 5.0, 9.0],
    "BIAS240_pct": [-25.0, -10.01, -10.0, -9.99, 0.0, 15.0, 15.01, 33.0],
    "PCR": [0.4, 0.69, 0.7, 1.0, 1.268, 1.5, 1.51, 2.2],
    "Futures_Net_Short": [-60000.0, -35000.01, -35000.0, -34999.0, 0.0, 12000.0],
}
#: 「整條不起作用」的值（餵給修前引擎當對照組）：每一個都不碰任何分支／紅線／標籤
_INERT = {"VIX_Index": 20.0, "ISM_PMI_or_OECD_CLI": 50.0, "PMI_Prev_Month": 50.0,
          "M1B_YoY_pct": 0.0, "M2_YoY_pct": 0.0, "BIAS240_pct": 0.0, "PCR": 1.0,
          "Futures_Net_Short": 0.0}
_ABSENT = object()
#: 缺值的各種樣子（_ABSENT ＝ 鍵不在）
_MISSING_FORMS = {"absent": _ABSENT, "none": None, "nan": float("nan"), "np_nan": np.nan,
                  "inf": float("inf"), "neg_inf": float("-inf"), "str_nan": "nan",
                  "str_word": "abc", "empty_str": "", "list": [1.0]}


def _rand_value(rnd: random.Random, k: str):
    r = rnd.random()
    if r < 0.6:
        return rnd.choice(_EDGES[k])
    lo, hi = min(_EDGES[k]), max(_EDGES[k])
    x = rnd.uniform(lo, hi)
    if r < 0.8:
        return x
    if r < 0.9:
        return np.float64(x)
    return str(round(x, 3))                     # 修前也收得下的數字字串（float("17.5")）


def _rand_inputs(rnd: random.Random) -> dict:
    d = {k: _rand_value(rnd, k) for k in _KEYS}
    d["Sahm_Rule_Triggered"] = rnd.random() < 0.15
    d["Index_Below_MA5"] = rnd.random() < 0.5
    return d


def _scored(state: dict) -> dict:
    return {k: v for k, v in state.items() if k != "missing_inputs"}


def _oracle(inputs: dict, missing: set) -> dict:
    """修前引擎、把缺的那幾項換成整條不起作用的值（M1B／M2 任一缺 → 兩個都換）。"""
    d = dict(inputs)
    gone = set(missing)
    if gone & {"M1B_YoY_pct", "M2_YoY_pct"}:
        gone |= {"M1B_YoY_pct", "M2_YoY_pct"}
    for k in gone:
        d[k] = _INERT[k]
    out = _pre_fix_css(d)
    if missing:   # 批 Z9 X2-n1：N>0 才加「N 項未評估」，接在既有標籤後（N 為實際缺的鍵數）
        tag = f"{len(set(missing))} 項未評估（缺資料不計分）"
        ph = out["Macro_Phase"]
        out["Macro_Phase"] = tag if ph == "環境正常" else f"{ph}、{tag}"
    return out


def _with_missing(inputs: dict, key: str, form) -> dict:
    d = dict(inputs)
    if form is _ABSENT:
        d.pop(key, None)
    else:
        d[key] = form
    return d


# ══════════════════════════════════════════════════════════════════════════
# A. 有限數值：與修前逐字相同
# ══════════════════════════════════════════════════════════════════════════
class TestFinitePresentUnchanged:
    def test_reference_copy_is_faithful_on_all_present(self):
        """對照組自身的健全性：8 個都給、走到每一種結果（多頭／震盪／空頭、三條紅線）。"""
        rnd = random.Random(1)
        seen = set()
        for _ in range(4000):
            o = _pre_fix_css(_rand_inputs(rnd))
            seen.add(o["market_regime"])
            seen.update(t for t in ("薩姆", "PMI連兩月", "期貨淨空", "資金緊縮", "均線過熱", "VIX高波動")
                        if t in o["Macro_Phase"])
        assert seen == {"多頭", "震盪", "空頭", "薩姆", "PMI連兩月", "期貨淨空", "資金緊縮", "均線過熱", "VIX高波動"}

    @pytest.mark.parametrize("seed", range(4))
    def test_random_and_edge_inputs_identical_to_pre_fix(self, seed):
        rnd = random.Random(20261003 + seed)
        for _ in range(5000):
            d = _rand_inputs(rnd)
            assert calculate_system_state(d) == _pre_fix_css(d), d

    def test_extra_keys_are_ignored_as_before(self):
        d = {k: _EDGES[k][1] for k in _KEYS} | {"TW_Export_YoY_pct": None, "US_Core_CPI_YoY_pct": "x"}
        assert calculate_system_state(d) == _pre_fix_css(d)
        assert "missing_inputs" not in calculate_system_state(d)


class TestZeroIsAValueNotMissing:
    """有限的 0 是真值，不是缺值（QA 突變：`is not None` 守衛改成真值判斷 `if vix:` 會把 0 當缺）。"""

    #: 其餘輸入都在「不起作用」的值上，只看被測那一項的 0 造成的效果
    _BASE = {**_INERT, "Sahm_Rule_Triggered": False, "Index_Below_MA5": False}

    @pytest.mark.parametrize("zero", [0.0, 0, -0.0, np.float64(0.0), "0"], ids=["float", "int", "neg0", "np", "str"])
    @pytest.mark.parametrize("key", _KEYS)
    def test_zero_matches_pre_fix_and_is_not_flagged(self, key, zero):
        d = {**self._BASE, key: zero}
        got = calculate_system_state(d)
        assert got == _pre_fix_css(d), (key, zero)
        assert "missing_inputs" not in got

    def test_vix_zero_scores_plus_ten(self):
        got = calculate_system_state({**self._BASE, "VIX_Index": 0})
        assert got["exposure_limit_pct"] == 70 and got["market_regime"] == "多頭"
        assert got == _pre_fix_css({**self._BASE, "VIX_Index": 0})

    def test_pcr_zero_scores_plus_five(self):
        # 基準 60 ＋5 ＝ 65 → round(6.5) 銀行家捨入回 60，看不出 +5；故墊 VIX 10（+10）：70 ＋5 ＝ 75 → 80
        d = {**self._BASE, "VIX_Index": 10.0, "PCR": 0}
        got = calculate_system_state(d)
        assert got == _pre_fix_css(d)
        assert got["exposure_limit_pct"] == 80                              # pcr < 0.7 → +5
        assert calculate_system_state({**d, "PCR": None})["exposure_limit_pct"] == 70

    def test_pmi_zero_triggers_bias_resonance(self):
        """PMI＝0（< 50）讓 BIAS240 高乖離共振成立：扣 15 並貼「均線過熱」（VIX 在 20 → 只靠 PMI 成立）。"""
        d = {**self._BASE, "ISM_PMI_or_OECD_CLI": 0, "BIAS240_pct": 20.0}
        got = calculate_system_state(d)
        assert got == _pre_fix_css(d)
        assert "均線過熱" in got["Macro_Phase"]
        assert "均線過熱" not in calculate_system_state({**d, "ISM_PMI_or_OECD_CLI": None})["Macro_Phase"]

    def test_pmi_zero_scores_and_labels(self):
        d = {**self._BASE, "ISM_PMI_or_OECD_CLI": 0, "PMI_Prev_Month": 0}
        got = calculate_system_state(d)
        assert got == _pre_fix_css(d)
        assert "PMI連兩月收縮(0.0→0.0)" in got["Macro_Phase"]               # 兩月都 0 → 紅線觸發
        got1 = calculate_system_state({**self._BASE, "ISM_PMI_or_OECD_CLI": 0})
        assert got1 == _pre_fix_css({**self._BASE, "ISM_PMI_or_OECD_CLI": 0})
        assert "PMI收縮(0.0)" in got1["Macro_Phase"] and got1["exposure_limit_pct"] == 40


# ══════════════════════════════════════════════════════════════════════════
# B. 缺值：當缺（整條不算），不代預設值；`missing_inputs` 照實
# ══════════════════════════════════════════════════════════════════════════
class TestMissingIsMissing:
    @pytest.mark.parametrize("form", sorted(_MISSING_FORMS))
    @pytest.mark.parametrize("key", _KEYS)
    def test_single_missing_key(self, key, form):
        rnd = random.Random(_KEYS.index(key) * 100 + sorted(_MISSING_FORMS).index(form))
        for _ in range(400):
            d = _rand_inputs(rnd)
            got = calculate_system_state(_with_missing(d, key, _MISSING_FORMS[form]))
            assert got["missing_inputs"] == [key]
            assert _scored(got) == _oracle(d, {key}), (key, form, d)

    def test_random_subsets_missing(self):
        rnd = random.Random(7)
        for _ in range(3000):
            d = _rand_inputs(rnd)
            gone = {k for k in _KEYS if rnd.random() < 0.35}
            x = dict(d)
            for k in gone:
                x = _with_missing(x, k, _MISSING_FORMS[rnd.choice(sorted(_MISSING_FORMS))])
            got = calculate_system_state(x)
            if gone:
                assert got["missing_inputs"] == [k for k in _KEYS if k in gone]
            else:
                assert "missing_inputs" not in got
            assert _scored(got) == _oracle(d, gone), (gone, x)

    def test_all_missing_lists_all_eight_in_order(self):
        got = calculate_system_state({})
        assert got["missing_inputs"] == list(_KEYS)
        assert tuple(M._ENGINE_NUMERIC_INPUTS) == _KEYS
        assert got == calculate_system_state({k: None for k in _KEYS})


# ══════════════════════════════════════════════════════════════════════════
# C. 修前確實出事的具體情境（origin/main 上會紅）
# ══════════════════════════════════════════════════════════════════════════
_SCN = {"VIX_Index": 17.0, "ISM_PMI_or_OECD_CLI": 51.0, "PMI_Prev_Month": 50.5,
        "BIAS240_pct": 5.0, "PCR": 1.0, "Futures_Net_Short": -1000.0}


class TestPreFixFabrications:
    def test_only_m2_missing_does_not_add_points(self):
        both = calculate_system_state({**_SCN})
        only = calculate_system_state({**_SCN, "M1B_YoY_pct": 4.2})
        assert _pre_fix_css({**_SCN, "M1B_YoY_pct": 4.2})["exposure_limit_pct"] > both["exposure_limit_pct"]
        # 批 Z9 X2-n1：「N 項未評估」隨缺值數變（only 缺 1、both 缺 2）→ 標籤另驗，其餘計分相同
        assert only["Macro_Phase"] == "1 項未評估（缺資料不計分）"
        assert both["Macro_Phase"] == "2 項未評估（缺資料不計分）"
        assert ({k: v for k, v in _scored(only).items() if k != "Macro_Phase"}
                == {k: v for k, v in _scored(both).items() if k != "Macro_Phase"})
        assert only["missing_inputs"] == ["M2_YoY_pct"]

    def test_only_m1b_missing_no_funding_squeeze(self):
        got = calculate_system_state({**_SCN, "M2_YoY_pct": 5.0})
        assert "資金緊縮" in _pre_fix_css({**_SCN, "M2_YoY_pct": 5.0})["Macro_Phase"]
        assert "資金緊縮" not in got["Macro_Phase"]
        assert got["missing_inputs"] == ["M1B_YoY_pct"]

    def test_infinite_vix_is_not_scored(self):
        d = {**_SCN, "M1B_YoY_pct": 1.0, "M2_YoY_pct": 1.0, "VIX_Index": float("inf")}
        assert "VIX高波動(inf)" in _pre_fix_css(d)["Macro_Phase"]
        got = calculate_system_state(d)
        assert "VIX" not in got["Macro_Phase"]
        assert got["exposure_limit_pct"] == _pre_fix_css({**d, "VIX_Index": 20.0})["exposure_limit_pct"]
        assert got["missing_inputs"] == ["VIX_Index"]

    def test_nan_bias_with_resonance_not_scored(self):
        d = {**_SCN, "M1B_YoY_pct": 1.0, "M2_YoY_pct": 1.0, "VIX_Index": 30.0, "BIAS240_pct": float("nan")}
        got = calculate_system_state(d)
        assert "均線過熱" not in got["Macro_Phase"]
        assert got["missing_inputs"] == ["BIAS240_pct"]

    @pytest.mark.parametrize("key", _KEYS)
    def test_missing_is_flagged(self, key):
        d = {**_SCN, "M1B_YoY_pct": 1.0, "M2_YoY_pct": 1.0}
        d.pop(key)
        assert calculate_system_state(d)["missing_inputs"] == [key]

    def test_inputs_mapping_not_mutated(self):
        d = {**_SCN, "M2_YoY_pct": None}
        before = dict(d)
        calculate_system_state(d)
        assert d == before and math.isfinite(d["VIX_Index"])
