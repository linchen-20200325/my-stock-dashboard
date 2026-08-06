"""tests/test_b2b_pcr_scale.py — PCR 刻度守衛（v19.180 B2-b）。

病史（本檔存在的理由）
────────────────────────────────────────────────────────────────
`li_latest['選PCR']` 是 `leading_indicators` 寫入時已 ×100 的**百分比刻度**
（實測 126.80，區間約 50~200）：

  · `src/data/macro/leading_indicators.py:1309`
    `pcr_dict[dk] = round(b["putV"] / b["callV"] * 100, 1)`   ← FinMind 估算
  · `src/data/macro/leading_indicators.py:969-971`
    `if 0.1 < val < 10: val = round(val * 100, 1)` → 只收 `20 < val < 500`
                                                     ← TAIFEX 精確值（覆蓋估算）

但 `macro_state_locker.calculate_system_state` 的判定是
`if pcr > 1.5: score -= 10`，用的是**標準比值刻度**（0.5~2.0，SSOT =
`config.MACRO_ALERT_RULES['pcr']`）。於是 `126.80 > 1.5` **恆真** ⇒ 曝險分數
系統性 −10 ⇒ 曝險上限（進而全站「建議持股」的天花板之一）恆低 10 個百分點。

v19.178 只修了 prompt 端（`section_news_ai` 的判讀句），
`_macro_numbers['PCR']` 仍送未換算值 —— 本檔釘死的就是那半條。

本檔釘死四件事
────────────────────────────────────────────────────────────────
  A. 舊 bug 的**行為重現**：同一份 PCR，百分比刻度比比值刻度整整少 10 分曝險。
  B. `shared.pcr_scale.normalize_pcr_to_ratio` 的邊界（含 §1 不猜的失敗路徑）。
  C. `calculate_system_state` 的**輸入契約**：它只認比值刻度，且刻意不自己猜。
  D. production wiring：`section_news_ai._macro_numbers['PCR']` 必須送換算後的
     變數。此條用 **AST**（不掃字串、不看註解 / docstring），失敗時印出該行原文。

⚠️ 本檔 docstring 與註解刻意寫滿 `> 1.5`、`126.80`、`× 100` 等字面 ——
   若哪天有人把 D 的守衛退化成字串掃描，這些誘餌會讓它自我引爆。
"""
from __future__ import annotations

import ast
import math
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared.allocation_decision import Cap, build_allocation_decision
from shared.pcr_scale import normalize_pcr_to_ratio
from shared.signal_thresholds import PCR_PERCENT_SCALE_MIN, PCR_PERCENT_VALID_MAX
from src.services.macro_state_locker import calculate_system_state

_REPO = Path(__file__).resolve().parent.parent
_SECTION = _REPO / "src/ui/tabs/macro/section_news_ai.py"


# ══════════════════════════════════════════════════════════════
# 共用 fixture — 除 PCR 外全部中性，讓分數差異只可能來自 PCR
# ══════════════════════════════════════════════════════════════
def _neutral(**over) -> dict:
    """除 PCR 外全中性的 macro_numbers（各項對分數的貢獻皆為 0）。

    對照 `calculate_system_state` 各段：
      VIX 17.1 → 14 < v < 22，不加不扣
      PMI 50.0 / prev 50.0 → 不加不扣，且不觸發「連兩月 < 48」硬否決
      M1B−M2 spread 0 → 不加不扣
      BIAS240 0 → 不加不扣
      Futures 0 / below_ma5 False / sahm False → 不觸發任何硬否決
    ⇒ 基準分 60 ⇒ 曝險 60。
    """
    base = {
        "VIX_Index": 17.1,
        "ISM_PMI_or_OECD_CLI": 50.0,
        "PMI_Prev_Month": 50.0,
        "M1B_YoY_pct": 0.0,
        "M2_YoY_pct": 0.0,
        "BIAS240_pct": 0.0,
        "Futures_Net_Short": 0.0,
        "Index_Below_MA5": False,
        "Sahm_Rule_Triggered": False,
    }
    base.update(over)
    return base


# ══════════════════════════════════════════════════════════════
# A. 舊 bug 行為重現 + 修後不再發生
# ══════════════════════════════════════════════════════════════
class TestOldBugReproduction:

    def test_baseline_without_pcr_is_60(self):
        """沒有 PCR 時的基準曝險 = 60（`_f('PCR', 1.0)` 預設 1.0 不加不扣）。"""
        assert calculate_system_state(_neutral())["exposure_limit_pct"] == 60

    def test_percent_scale_pcr_costs_exactly_10_points(self):
        """**舊 bug**：未換算的 126.80 直接進引擎 → `> 1.5` 恆真 → 整整少 10 分。"""
        percent = calculate_system_state(_neutral(PCR=126.80))
        ratio = calculate_system_state(_neutral(PCR=1.268))
        assert percent["exposure_limit_pct"] == 50
        assert ratio["exposure_limit_pct"] == 60
        assert ratio["exposure_limit_pct"] - percent["exposure_limit_pct"] == 10, (
            "PCR 百分比刻度直送引擎應該剛好吃掉 10 個百分點的曝險 —— "
            "這是本次要修掉的系統性偏差")

    def test_fix_removes_the_penalty(self):
        """**修後**：取值端換算完再進引擎 → 與無 PCR 的基準完全相同。"""
        ratio, _src = normalize_pcr_to_ratio(126.80)
        fixed = calculate_system_state(_neutral(PCR=ratio))
        assert fixed["exposure_limit_pct"] == 60
        assert fixed == calculate_system_state(_neutral()), (
            "126.80（≈1.27，落在 0.7~1.5 的中性帶）換算後不該對曝險有任何影響")

    @pytest.mark.parametrize("raw", [70.0, 80.0, 100.0, 126.80, 149.0])
    def test_whole_percent_band_was_systematically_penalised(self, raw):
        """整個百分比刻度值域都恆扣 10 —— 不是只有 126.80 這一個倒楣值。

        70~149 換算後是 0.70~1.49，全部落在比值刻度的「中性帶」[0.7, 1.5]，
        **沒有一個**該觸發 `> 1.5`；未換算時卻**全部**觸發。
        這就是「系統性」而非「偶發」的證據。
        """
        ratio, _src = normalize_pcr_to_ratio(raw)
        assert 0.7 <= ratio < 1.5
        assert (calculate_system_state(_neutral(PCR=ratio))["exposure_limit_pct"]
                - calculate_system_state(_neutral(PCR=raw))["exposure_limit_pct"]) == 10


# ══════════════════════════════════════════════════════════════
# B. 刻度守衛邊界（§1：判不出來就回 None，不猜、不填預設）
# ══════════════════════════════════════════════════════════════
class TestNormalizePcrToRatio:

    def test_ratio_scale_passthrough(self):
        val, src = normalize_pcr_to_ratio(1.268)
        assert math.isclose(val, 1.268, rel_tol=1e-9)
        assert "比值" in src

    def test_percent_scale_converted(self):
        val, src = normalize_pcr_to_ratio(126.80)
        assert math.isclose(val, 1.268, rel_tol=1e-9)
        assert "百分比" in src

    def test_boundary_is_inclusive_on_ratio_side(self):
        """邊界 10.0 判為比值刻度（`>` 而非 `>=`）。

        刻意與 `macro_alert.py` 既有的 `_pcr_val > PCR_PERCENT_SCALE_MIN` 對齊，
        **零行為位移** —— 收斂重複實作時不順手改語意。
        """
        assert PCR_PERCENT_SCALE_MIN == 10.0
        val, _src = normalize_pcr_to_ratio(10.0)
        assert math.isclose(val, 10.0, rel_tol=1e-9)

    def test_just_above_boundary_is_percent(self):
        val, _src = normalize_pcr_to_ratio(10.01)
        assert math.isclose(val, 0.1001, rel_tol=1e-9)

    def test_upper_bound_of_percent_scale(self):
        val, _src = normalize_pcr_to_ratio(PCR_PERCENT_VALID_MAX)
        assert math.isclose(val, 5.0, rel_tol=1e-9)

    @pytest.mark.parametrize("raw", [500.01, 9999.0, 1e9])
    def test_out_of_both_scales_returns_none(self, raw):
        """兩種刻度都解釋不通 → None（§1 不猜換算，caller 當「沒有這個指標」）。"""
        val, src = normalize_pcr_to_ratio(raw)
        assert val is None
        assert "刻度不明" in src

    @pytest.mark.parametrize("raw", [0.0, -0.5, -126.8])
    def test_non_positive_returns_none(self, raw):
        """PCR = putV/callV 恆為正。0 / 負值若當比值放行會命中「< 0.7 過度樂觀」
        → 憑空生出一個看多訊號（§1 反捏造）。"""
        val, src = normalize_pcr_to_ratio(raw)
        assert val is None
        assert "非正值" in src

    def test_nan_returns_none(self):
        val, src = normalize_pcr_to_ratio(float("nan"))
        assert val is None
        assert "NaN" in src

    def test_none_returns_none(self):
        val, src = normalize_pcr_to_ratio(None)
        assert val is None
        assert "未取得" in src

    @pytest.mark.parametrize("raw", ["-", "", "nan", "N/A", [1, 2], {}])
    def test_unparseable_returns_none(self, raw):
        """`選PCR` 欄位在缺值時真的會是 '-' / '' / 'nan'（見 leading_indicators 表格化）。"""
        val, _src = normalize_pcr_to_ratio(raw)
        assert val is None

    def test_numeric_strings_are_accepted(self):
        """欄位取值端是 `str(...)` 後再 float()，helper 也應吃得下字串數字。"""
        val, _src = normalize_pcr_to_ratio("126.8")
        assert math.isclose(val, 1.268, rel_tol=1e-9)

    def test_returns_two_tuple_for_every_input(self):
        """契約：**永遠**回 (value|None, str)，caller 可以無條件解包。"""
        for raw in (None, float("nan"), "-", 0, 1.0, 126.8, 1e9):
            out = normalize_pcr_to_ratio(raw)
            assert isinstance(out, tuple) and len(out) == 2
            assert out[0] is None or isinstance(out[0], float)
            assert isinstance(out[1], str) and out[1]


# ══════════════════════════════════════════════════════════════
# C. 引擎輸入契約：只認比值刻度，且刻意不自己猜
# ══════════════════════════════════════════════════════════════
class TestEngineContractIsRatioScale:

    @pytest.mark.parametrize("pcr,expected", [
        (1.60, 50),   # > 1.5 極度恐慌 → −10 分 → 60→50
        (1.51, 50),
        (1.50, 60),   # 邊界：嚴格大於才扣（`pcr > 1.5`）
        (1.20, 60),
        (1.00, 60),
        (0.70, 60),   # 邊界：嚴格小於才加（`pcr < 0.7`）
    ])
    def test_thresholds_are_on_ratio_scale(self, pcr, expected):
        """引擎的 1.5 / 0.7 斷點只在**比值刻度**下才有意義。"""
        got = calculate_system_state(_neutral(PCR=pcr))["exposure_limit_pct"]
        assert got == expected, f"PCR={pcr}（比值刻度）的曝險不如契約"

    def test_low_pcr_adds_score_but_exposure_is_quantised_to_10s(self):
        """PCR < 0.7 加 5 分，但曝險是 `round(score/10)*10` 的 10 級距。

        Python `round()` 是**四捨六入五成雙**：60→65 時 `round(6.5)=6` ⇒ 曝險仍 60，
        看起來像「沒生效」；把基準墊到 70（VIX ≤14 加 10 分）才看得到
        `round(7.5)=8` ⇒ 80。此測試把這個量化行為釘住，避免日後誤判為 bug。
        """
        assert calculate_system_state(_neutral(PCR=0.69))["exposure_limit_pct"] == 60
        hot = _neutral(VIX_Index=13.0)
        assert calculate_system_state(hot)["exposure_limit_pct"] == 70
        assert calculate_system_state({**hot, "PCR": 0.69})["exposure_limit_pct"] == 80

    def test_engine_does_not_guess_scale(self):
        """引擎**不得**自己偵測刻度（§1：掩蓋 ≠ 解決）。

        若哪天有人在引擎內部塞 `if pcr > 10: pcr /= 100`，本測試會紅 ——
        那會讓 caller 永遠發現不到自己送錯刻度。守衛屬於取值端。
        """
        base = calculate_system_state(_neutral())["exposure_limit_pct"]
        assert calculate_system_state(
            _neutral(PCR=126.80))["exposure_limit_pct"] == base - 10, (
            "引擎似乎自行換算了刻度 —— 契約要求它照收、由取值端負責換算")

    def test_none_pcr_falls_back_to_neutral_default(self):
        """刻度不明 → 取值端送 None → 引擎 `_f('PCR', 1.0)` 退回中性，不加不扣。"""
        assert (calculate_system_state(_neutral(PCR=None))["exposure_limit_pct"]
                == calculate_system_state(_neutral())["exposure_limit_pct"])


# ══════════════════════════════════════════════════════════════
# D. production wiring 守衛（AST；不掃字串、不看註解 / docstring）
# ══════════════════════════════════════════════════════════════
def _pcr_value_node(source: str, dict_name: str = "_macro_numbers"):
    """回傳 `<dict_name> = {... 'PCR': <此節點> ...}` 的 value AST 節點。

    只走 AST：註解在 AST 裡根本不存在，docstring 也不可能被誤認為 Dict 賦值，
    因此本守衛天生不會被「註解裡寫了 _pcr_v」之類的誘餌騙到。
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == dict_name
                   for t in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for k, v in zip(node.value.keys, node.value.values):
            if isinstance(k, ast.Constant) and k.value == "PCR":
                return v
    return None


def _names_used(root: ast.AST) -> set[str]:
    """子樹內出現過的識別字（Name / Attribute / import 原名與別名）。"""
    out: set[str] = set()
    for node in ast.walk(root):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.alias):
            out.add(node.name.split(".")[-1])
            if node.asname:
                out.add(node.asname)
    return out


class TestProductionWiring:

    def test_macro_numbers_pcr_is_not_the_raw_percent_variable(self):
        """`_macro_numbers['PCR']` 不得是未換算的 `_pcr_v`（就是舊 bug 本身）。"""
        src = _SECTION.read_text(encoding="utf-8")
        node = _pcr_value_node(src)
        assert node is not None, (
            f"{_SECTION} 內找不到 `_macro_numbers = {{... 'PCR': ...}}` 賦值 —— "
            "wiring 被改名或搬走了，請同步更新本守衛（ANCHOR-MISSING）")
        line = src.splitlines()[node.lineno - 1]
        assert isinstance(node, ast.Name), (
            f"{_SECTION}:{node.lineno}: 'PCR' 的值不是單純變數，請人工確認刻度。"
            f"\n    該行原文：{line.strip()}")
        assert node.id != "_pcr_v", (
            f"{_SECTION}:{node.lineno}: 'PCR' 又送了未換算的百分比刻度 `_pcr_v` "
            f"→ `pcr > 1.5` 恆真 → 曝險恆 −10（B2-b 回歸）。"
            f"\n    該行原文：{line.strip()}")

    def test_section_references_the_shared_normalizer(self):
        """必須實際引用 SSOT helper（防「換算又被 inline 寫回去」）。"""
        src = _SECTION.read_text(encoding="utf-8")
        used = _names_used(ast.parse(src))
        assert "normalize_pcr_to_ratio" in used, (
            f"{_SECTION} 未引用 shared.pcr_scale.normalize_pcr_to_ratio —— "
            "PCR 刻度換算可能又被寫成 inline 的 `/ 100`")

    def test_pcr_scale_module_uses_ssot_constants(self):
        """`shared/pcr_scale.py` 的判別線必須引 SSOT，不得 inline 10 / 500。"""
        path = _REPO / "shared/pcr_scale.py"
        used = _names_used(ast.parse(path.read_text(encoding="utf-8")))
        for name in ("PCR_PERCENT_SCALE_MIN", "PCR_PERCENT_VALID_MAX"):
            assert name in used, f"pcr_scale 未引用 SSOT 常數 {name}（§3.3）"


class TestWiringGuardItself:
    """守衛的自我驗證（§6）—— 證明它抓得到真違規、且不被註解/docstring 騙。"""

    def test_guard_catches_the_old_wiring(self):
        bad = (
            "_pcr_v = 126.8\n"
            "_macro_numbers = {'VIX_Index': 17.1, 'PCR': _pcr_v}\n"
        )
        node = _pcr_value_node(bad)
        assert isinstance(node, ast.Name) and node.id == "_pcr_v", (
            "守衛認不出舊 wiring → 它是假綠的")

    def test_guard_accepts_the_fixed_wiring(self):
        good = (
            "_pcr_ratio, _src = normalize_pcr_to_ratio(_pcr_v)\n"
            "_macro_numbers = {'PCR': _pcr_ratio}\n"
        )
        node = _pcr_value_node(good)
        assert isinstance(node, ast.Name) and node.id == "_pcr_ratio"

    def test_guard_not_fooled_by_comments_and_docstrings(self):
        """註解 / docstring 裡寫滿 `'PCR': _pcr_v` 也不得誤判。"""
        decoy = (
            '"""舊碼長這樣：_macro_numbers = {\'PCR\': _pcr_v}（126.8 > 1.5 恆真）。"""\n'
            "# _macro_numbers = {'PCR': _pcr_v}\n"
            "_note = \"_macro_numbers = {'PCR': _pcr_v}\"\n"
            "_macro_numbers = {'PCR': _pcr_ratio}\n"
        )
        node = _pcr_value_node(decoy)
        assert isinstance(node, ast.Name) and node.id == "_pcr_ratio"


# ══════════════════════════════════════════════════════════════
# E. 行為變更的實際幅度（釘住「天花板會不會吃掉改善」這個結論）
# ══════════════════════════════════════════════════════════════
_LIVE_HEALTH = 55.0          # 實測總經健康分
_RING1_CAP = Cap("三環第一環", 20, "外資期貨 -87,455 口 ≤ -15,000")


def _decide(exposure_limit_pct: int, caps=()):
    ms = {
        "is_loaded": True, "regime": "neutral", "health": _LIVE_HEALTH,
        "defense": False, "exposure_limit_pct": exposure_limit_pct,
    }
    return build_allocation_decision(ms, throttle=None, caps=caps)


class TestAllocationImpact:

    def test_live_scenario_headline_is_unchanged_because_of_ring1_ceiling(self):
        """**本次最重要的結論**：線上實測條件下，修 PCR **不會**改變畫面數字。

        外資期貨 −87,455 口 ≤ −15,000 → 三環第一環 Cap 20%，
        它比「系統風險上限」(50 → 60) 更低 ⇒ 生效的天花板始終是 20% ⇒
        `final_mid` 20%、`range_text` '20%' 都不動。
        改善被天花板整個吃掉 —— 這條測試就是防止有人事後以為「修了就會變」。
        """
        before = _decide(50, caps=(_RING1_CAP,))
        after = _decide(60, caps=(_RING1_CAP,))
        assert before.final_mid == after.final_mid == 20
        assert before.range_text == after.range_text == "20%"
        assert before.cap_name == after.cap_name == "三環第一環"

    def test_without_ring1_ceiling_the_fix_moves_the_number(self):
        """三環第一環一旦解除（外資期貨回到 > −15,000 口），改善就會現形。"""
        before = _decide(50)
        after = _decide(60)
        assert (before.final_lo, before.final_hi, before.final_mid) == (50, 50, 50)
        assert (after.final_lo, after.final_hi, after.final_mid) == (50, 60, 55)
        assert before.range_text == "50%"
        # `_fmt_range` 的區間分隔字元是 U+2013 EN DASH（不是一般 hyphen）。
        # 用 chr(0x2013) 組字串而非直接打字元，杜絕「檔案被編輯器 / 剪貼簿
        # 換成 hyphen → 測試假紅」這種與程式邏輯無關的失敗。
        assert after.range_text == "50" + chr(0x2013) + "60%"

    def test_exposure_limit_written_to_state_does_change(self):
        """即使畫面數字不動，寫進 macro_state.json 的曝險上限 50 → 60 是真的變了
        （AI prompt 的 `<System_State>`、「為何是這個數字」明細都會跟著改）。"""
        live = dict(VIX_Index=17.1, ISM_PMI_or_OECD_CLI=50.0, PMI_Prev_Month=50.0,
                    M1B_YoY_pct=0.0, M2_YoY_pct=0.0, BIAS240_pct=33.0,
                    Futures_Net_Short=-87455.0, Index_Below_MA5=False,
                    Sahm_Rule_Triggered=False)
        assert calculate_system_state({**live, "PCR": 126.80})[
            "exposure_limit_pct"] == 50
        assert calculate_system_state({**live, "PCR": 1.268})[
            "exposure_limit_pct"] == 60

    def test_futures_veto_swallows_everything_when_index_below_ma5(self):
        """若指數同時跌破 MA5 → 外資期貨硬否決把曝險壓到 30%，改前改後都一樣。"""
        live = dict(VIX_Index=17.1, ISM_PMI_or_OECD_CLI=50.0, PMI_Prev_Month=50.0,
                    M1B_YoY_pct=0.0, M2_YoY_pct=0.0, BIAS240_pct=33.0,
                    Futures_Net_Short=-87455.0, Index_Below_MA5=True,
                    Sahm_Rule_Triggered=False)
        assert calculate_system_state({**live, "PCR": 126.80})[
            "exposure_limit_pct"] == 30
        assert calculate_system_state({**live, "PCR": 1.268})[
            "exposure_limit_pct"] == 30


class TestRegimeFlipBoundaries:
    """哪些情境下這 10 分會**翻轉 market_regime**（不只是數字位移）。"""

    def test_flip_neutral_to_bull_at_the_70_boundary(self):
        """真實分數落在 70 一格：改前 60（震盪/警告）、改後 70（多頭/安全）。"""
        # VIX ≤14 (+10) 讓基準來到 70
        common = _neutral(VIX_Index=13.0)
        before = calculate_system_state({**common, "PCR": 126.80})
        after = calculate_system_state({**common, "PCR": 1.268})
        assert (before["exposure_limit_pct"], before["market_regime"]) == (60, "震盪")
        assert (after["exposure_limit_pct"], after["market_regime"]) == (70, "多頭")

    def test_flip_bear_to_neutral_at_the_40_boundary(self):
        """真實分數落在 40 一格：改前 30（空頭/危險）、改後 40（震盪/警告）。"""
        # VIX ≥22 (−10) + PMI 47 (−10) → 基準 40
        common = _neutral(VIX_Index=23.0, ISM_PMI_or_OECD_CLI=47.0)
        before = calculate_system_state({**common, "PCR": 126.80})
        after = calculate_system_state({**common, "PCR": 1.268})
        assert (before["exposure_limit_pct"], before["systemic_risk_level"]) == (30, "危險")
        assert (after["exposure_limit_pct"], after["systemic_risk_level"]) == (40, "警告")
