"""批 Z66 —— 系統風險上限 Q2：M1B-M2 腿在正式計分停用（客戶 2026-10-16 裁示）。

客戶裁示（逐意轉錄）：System Risk Cap 正式計分停用 M1B-M2 腿，與
`shared/signal_thresholds.M1B_M2_LEG_ENABLED = False` 同步 —— 它已有正式停用語意、現有證據區分力不足，
⛔ 不得讓已停用的訊號繼續默默抬高風險上限；保留歷史版本與版本化、不改寫歷史決策；
日後 DL-f1-s8 若支持重新啟用，屬另一次裁示。

守：
1. 引擎（`calculate_system_state`，新舊 UI 共用）：開關 False ⇒ spread 不計分、不貼「資金緊縮」；
   M1B／M2 回報 `disabled_inputs`、⛔ 不算 `missing_inputs`／「N 項未評估」；
   「全缺」fail-safe ＝ 啟用中的輸入全缺（只有 M1B／M2 的檔逃不過 fail-safe）。
   開關 True ⇒ 與修前（f9a5248c）逐字相同（以還原體實跑對照）。
2. 突變：開關翻 True ⇒ +15／+5／−10 與「資金緊縮」回來。
3. L3 `macro_engine_inputs`：停用 ≠ 未評估（`not_evaluated` 不含 M1B／M2，另列 `disabled_inputs`）。
4. `risk_cap_apply`：`engine_source` v2、檔案帶 L0 規則版本；`m1b_m2_data_month` 恆 None。
5. 步驟報告：停用另起一句、不算進「未評估 N 項」。
6. `allocation_decision` 系統風險上限說明不再宣稱 M1B-M2 計分。
7. 還原鏈：本批對 L3 引擎的改動換回 f9a5248c 寫法（舊批次 golden 串接用）。
L1 一律 mock；不連網。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# ══════════════════════════════════════════════════════════════════════════
# 0. 還原鏈（同 Z62／Z63／Z65 慣例）：把本批改動換回 f9a5248c 寫法
#    ⚠️ 本段必須在任何 `from tests...` import 之前（舊批次測試檔會回頭 import 這裡）
# ══════════════════════════════════════════════════════════════════════════
_MSL_REL = "src/services/macro_state_locker.py"
#: f9a5248c 原檔 sha256（`git show f9a5248c:<rel> | sha256sum`）。
Z66_BASE_SHA = {_MSL_REL: "480bded6832cfb243d4ae2eb0a396317379f094d195a44997f699b02a97b7f48"}
Z66_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    _MSL_REL: (
        ('from shared import signal_thresholds as _ST\n',
         ''),
        ('#: M1B-M2 資金項（spread）用到的兩個輸入（批 Z66，客戶 2026-10-16 Q2）。\n_M1B_M2_LEG_INPUTS: tuple = ("M1B_YoY_pct", "M2_YoY_pct")\n\n#: M1B-M2 腿停用時寫進 `Macro_Phase` 的揭露字（措辭比照 `market_strategy` 的「M1B-M2 資金活水已停用…不計分」）。\nM1B_M2_LEG_DISABLED_LABEL: str = "M1B-M2 資金活水已停用（不計分）"\n\n\ndef engine_disabled_inputs() -> tuple:\n    """規則引擎**目前停用**（不計分、也不算「未評估」）的數值輸入，依 `_ENGINE_NUMERIC_INPUTS` 順序。\n\n    批 Z66（客戶 2026-10-16 Q2）：M1B-M2 腿與 `shared.signal_thresholds.M1B_M2_LEG_ENABLED` 同步 ——\n    False ⇒ `("M1B_YoY_pct", "M2_YoY_pct")`；True ⇒ `()`。**呼叫當下**才讀 L0 開關（不在 import 時綁死），\n    引擎與 L3 `macro_engine_inputs`（`not_evaluated`）共用這一支，⛔ 不各自判斷。\n    """\n    return () if _ST.M1B_M2_LEG_ENABLED else _M1B_M2_LEG_INPUTS\n\n',
         ''),
        ('    M1B-M2 腿停用（批 Z66，客戶 2026-10-16 Q2；開關 `shared.signal_thresholds.M1B_M2_LEG_ENABLED`）\n    ────────────────────────────────────────────────────────────────\n    開關為 False（現行）→ M1B／M2 **停用、不計分**：\n      · spread 計分（＞3 → +15、＞0 → +5、＜−3 → −10）與「資金緊縮」標記整條不算 ——\n        客戶：已有正式停用語意、現有證據區分力不足，⛔ 不得讓停用的訊號繼續默默抬高風險上限；\n      · M1B／M2 **不算缺值**（不進 `missing_inputs`、不算進「N 項未評估」）；改回報\n        `disabled_inputs`（停用的鍵名，依上表順序；**只在開關為 False 時才帶**）；\n      · 上游兩邊都給了有限值時，`Macro_Phase` 多一個 `M1B_M2_LEG_DISABLED_LABEL` 揭露（停用 ≠ 缺資料）；\n      · 「全缺」fail-safe 改為「**啟用中**的數值輸入全缺」—— 只有 M1B／M2 有值的輸入照樣 fail-safe。\n    開關為 True → 與修前逐字相同（M1B-M2 照舊計分；無 `disabled_inputs`）。計分程式碼刻意保留不刪\n    （同 `market_strategy` 的處置；重新啟用是另一次裁示，且須升 `shared.risk_cap_policy.RISK_CAP_RULESET_VERSION`）。\n\n',
         ''),
        ('    # 批 Z66（Q2）：停用的輸入不計分、也不算缺（開關 True 時 `_disabled` 為空 ⇒ 與修前逐字相同）\n    _disabled = engine_disabled_inputs()\n    _enabled = tuple(k for k in _ENGINE_NUMERIC_INPUTS if k not in _disabled)\n    missing_inputs = [k for k in _enabled if _nums[k] is None]\n',
         '    missing_inputs = [k for k in _ENGINE_NUMERIC_INPUTS if _nums[k] is None]\n'),
        ('    #   批 Z66（Q2）：「全缺」＝**啟用中**的數值輸入全缺（停用的 M1B／M2 有值也不能讓它逃過 fail-safe）。\n    if len(missing_inputs) == len(_enabled) and not sahm:\n',
         '    if len(missing_inputs) == len(_ENGINE_NUMERIC_INPUTS) and not sahm:\n'),
        ('        if _disabled:\n            _fs_out["disabled_inputs"] = list(_disabled)\n',
         ''),
        ('    # 批 Z66（Q2）：腿停用 ⇒ spread 不算（不計分、不貼「資金緊縮」）；兩邊都有值時只做停用揭露\n    _leg_on = not _disabled\n    _m1b_m2_both = m1b_yoy is not None and m2_yoy is not None\n    spread = (m1b_yoy - m2_yoy) if (_leg_on and _m1b_m2_both) else None\n',
         '    spread = (m1b_yoy - m2_yoy) if (m1b_yoy is not None and m2_yoy is not None) else None\n'),
        ('    if not _leg_on and _m1b_m2_both:                       # 批 Z66：停用 ≠ 缺資料，要說出來\n        labels.append(M1B_M2_LEG_DISABLED_LABEL)\n',
         ''),
        ('    if _disabled:\n        # 批 Z66（Q2）：停用的輸入（開關 False 時一律帶；True 時不帶 ⇒ 與修前逐字相同）\n        _out["disabled_inputs"] = list(_disabled)\n',
         ''),
    ),
}


def z66_revert_for(file_path, code: str) -> str:
    """舊批次還原鏈串接用：給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批之前的寫法（無 pair 則原樣）。"""
    p = Path(file_path)
    rel = (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()
    for new, old in Z66_REVERT_PAIRS.get(rel, ()):
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    return code


@__import__("pytest").mark.parametrize("rel", sorted(Z66_REVERT_PAIRS))
def test_z66_revert_is_exact_base_source(rel):
    code = z66_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == Z66_BASE_SHA[rel]


# ══════════════════════════════════════════════════════════════════════════
# 以下才 import 專案與舊批次測試（舊批次測試檔會回頭 import 上面的還原鏈）
# ══════════════════════════════════════════════════════════════════════════
import copy  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402
import sys  # noqa: E402

import pytest  # noqa: E402

import shared.signal_thresholds as ST  # noqa: E402
from shared import risk_cap_policy as RP  # noqa: E402
from src.services import macro_engine_inputs as M  # noqa: E402
from src.services import macro_refresh_service as RS  # noqa: E402
from src.services import macro_state_locker as MSL  # noqa: E402
from src.services import risk_cap_apply as RC  # noqa: E402
from src.services.macro_state_locker import _ENGINE_NUMERIC_INPUTS, calculate_system_state  # noqa: E402
from tests.test_batch_z64 import NOW, _build, _inputs, _session_from  # noqa: E402
from tests.test_batch_z65 import _BAD, _EDGE_NUM, _run_refresh, _step, l1  # noqa: E402,F401

_LEG = ("M1B_YoY_pct", "M2_YoY_pct")
_ENABLED = tuple(k for k in _ENGINE_NUMERIC_INPUTS if k not in _LEG)


def _pre_z66_engine():
    """f9a5248c 的 `calculate_system_state`（本批還原體實跑；還原後 sha256 ＝ 基底，見上方 test）。"""
    rel = _MSL_REL
    code = z66_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
    name = "_z66_pre_msl"
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    m.__file__ = str(REPO / rel)
    sys.modules[name] = m
    exec(compile(code, str(REPO / rel), "exec"), m.__dict__)
    return m.calculate_system_state


def _grid(n=3000, seed=66):
    rng = random.Random(seed)
    for i in range(n):
        d: dict = {}
        all_missing = rng.random() < 0.05
        for k in _ENGINE_NUMERIC_INPUTS:
            r = rng.random()
            if all_missing or r < 0.15:
                v = rng.choice(_BAD)
                if v is not None or rng.random() < 0.5:
                    d[k] = v
            elif r < 0.55:
                d[k] = rng.choice(_EDGE_NUM[k])
            else:
                d[k] = round(rng.uniform(-80000, 80000) if k == "Futures_Net_Short"
                             else rng.uniform(-30, 70), 3)
        d["Sahm_Rule_Triggered"] = rng.choice([None, False, True])
        d["Index_Below_MA5"] = rng.choice([True, False, None])
        yield i, d


# ══════════════════════════════════════════════════════════════════════════
# 1. 引擎：開關 False（現行）
# ══════════════════════════════════════════════════════════════════════════
class TestEngineLegOff:
    def test_flag_is_off_and_version_bound(self):
        """現行開關 False ⇔ 規則版本 v2。改開關卻沒升版本 ⇒ 紅（客戶：重新啟用是另一次裁示）。"""
        assert ST.M1B_M2_LEG_ENABLED is False
        assert RP.RISK_CAP_RULESET_VERSION == "risk_cap.v2"
        assert MSL.engine_disabled_inputs() == _LEG

    @pytest.mark.parametrize("m1b,m2", [(8.0, 4.0), (4.0, 3.5), (1.0, 5.0), (0.0, 0.0), (-5.0, 6.0)])
    def test_spread_not_scored_and_no_tightening(self, m1b, m2):
        base = {"VIX_Index": 18.0, "ISM_PMI_or_OECD_CLI": 51.0, "PMI_Prev_Month": 51.0,
                "BIAS240_pct": 0.0, "PCR": 1.0, "Futures_Net_Short": 0.0}
        with_leg = calculate_system_state({**base, "M1B_YoY_pct": m1b, "M2_YoY_pct": m2})
        without = calculate_system_state(base)
        assert with_leg["exposure_limit_pct"] == without["exposure_limit_pct"] == 60
        assert "資金緊縮" not in with_leg["Macro_Phase"]
        assert with_leg["Macro_Phase"] == MSL.M1B_M2_LEG_DISABLED_LABEL
        assert without["Macro_Phase"] == "環境正常"
        assert with_leg["disabled_inputs"] == without["disabled_inputs"] == list(_LEG)
        assert "missing_inputs" not in with_leg and "missing_inputs" not in without

    def test_disabled_is_not_missing(self):
        out = calculate_system_state({"VIX_Index": 18.0})
        assert out["missing_inputs"] == [k for k in _ENABLED if k != "VIX_Index"]
        assert out["Macro_Phase"] == "5 項未評估（缺資料不計分）"
        assert out["disabled_inputs"] == list(_LEG)

    @pytest.mark.parametrize("only", [{"M1B_YoY_pct": 8.0, "M2_YoY_pct": 4.0},
                                      {"M1B_YoY_pct": 8.0}, {}])
    def test_only_leg_inputs_still_fail_safe(self, only):
        """只有 M1B／M2 的輸入（啟用中的全缺）⇒ fail-safe；⛔ 不得靠停用的腿逃過 fail-safe。"""
        out = calculate_system_state(dict(only), include_veto_flags=True)
        assert out["market_regime"] == "系統異常" and out["exposure_limit_pct"] == 0
        assert out["missing_inputs"] == list(_ENABLED)
        assert out["disabled_inputs"] == list(_LEG)
        assert out["veto_flags"]["fail_safe"] is True

    def test_grid_equals_pre_engine_without_leg(self):
        """開關 False 的輸出 ＝ 修前引擎（f9a5248c）「把 M1B／M2 拿掉」的輸出 ——
        差別只有：`disabled_inputs`、`missing_inputs` 不含 M1B／M2、「N 項未評估」不數 M1B／M2、
        兩邊都有值時多一個停用揭露。曝險上限／regime／風險等級／紅線逐例相同。"""
        pre = _pre_z66_engine()
        n_fs = n_label = n_cap_diff_vs_leg_on = 0
        for i, d in _grid():
            new = calculate_system_state(copy.deepcopy(d), include_veto_flags=True)
            ref = pre({k: v for k, v in d.items() if k not in _LEG}, include_veto_flags=True)
            leg_on_ref = pre(copy.deepcopy(d))
            assert new.pop("disabled_inputs") == list(_LEG), i
            both = all(MSL._is_finite_number(d.get(k)) for k in _LEG)
            ref_missing = [k for k in ref.pop("missing_inputs", []) if k not in _LEG]
            new_missing = new.pop("missing_inputs", [])
            assert new_missing == ref_missing, (i, d)
            new_phase, ref_phase = new.pop("Macro_Phase"), ref.pop("Macro_Phase")
            if new["veto_flags"]["fail_safe"]:
                n_fs += 1
                assert new_phase == ref_phase == "系統異常" and len(new_missing) == len(_ENABLED)
            else:
                parts = [p for p in ref_phase.split("、") if p != "環境正常"]
                parts = [p for p in parts if not p.endswith("項未評估（缺資料不計分）")]
                if both:
                    n_label += 1
                    k = next((j for j, p in enumerate(parts) if p == "均線過熱"), len(parts))
                    parts.insert(k, MSL.M1B_M2_LEG_DISABLED_LABEL)
                if new_missing:
                    parts.append(f"{len(new_missing)} 項未評估（缺資料不計分）")
                assert new_phase == ("、".join(parts) if parts else "環境正常"), (i, d, new_phase, ref_phase)
            assert new == ref, (i, d)
            n_cap_diff_vs_leg_on += new["exposure_limit_pct"] != leg_on_ref["exposure_limit_pct"]
        # 前提自證：網格真的含 fail-safe、停用揭露，且真的有「修前腿開啟時上限不同」的例子
        assert n_fs > 20 and n_label > 500 and n_cap_diff_vs_leg_on > 300, (n_fs, n_label,
                                                                             n_cap_diff_vs_leg_on)

    def test_old_ui_shared_engine_also_off(self):
        """舊 UI §十一 呼叫的是同一個 L3 函式（不另寫一份）⇒ 開關 False 對舊 UI 寫的檔同樣生效。"""
        import ast
        src = (REPO / "src/ui/tabs/macro/section_news_ai.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        names = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                 and (n.module or "").endswith("macro_state_locker") for a in n.names}
        assert "calculate_system_state" in names
        assert "def calculate_system_state" not in src


# ══════════════════════════════════════════════════════════════════════════
# 2. 突變：開關翻 True ⇒ +15／+5／−10 與「資金緊縮」回來；與修前引擎逐字相同
# ══════════════════════════════════════════════════════════════════════════
class TestMutationFlagOn:
    #: 基準分 70（VIX 14 → +10）。腿開啟：spread +4 → +15 ⇒ 85 → 80；+0.5 → +5 ⇒ 75 → 80；
    #: −4 → −10 ⇒ 60；−1 → 0 分但貼「資金緊縮」⇒ 70。腿停用 ⇒ 一律 70、⛔ 無「資金緊縮」。
    @pytest.mark.parametrize("m1b,m2,cap_on,tight", [(8.0, 4.0, 80, False), (4.0, 3.5, 80, False),
                                                     (1.0, 5.0, 60, True), (2.0, 3.0, 70, True)])
    def test_flip_restores_leg(self, monkeypatch, m1b, m2, cap_on, tight):
        base = {"VIX_Index": 14.0, "ISM_PMI_or_OECD_CLI": 51.0, "PMI_Prev_Month": 51.0,
                "BIAS240_pct": 0.0, "PCR": 1.0, "Futures_Net_Short": 0.0}
        off = calculate_system_state({**base, "M1B_YoY_pct": m1b, "M2_YoY_pct": m2})
        monkeypatch.setattr(ST, "M1B_M2_LEG_ENABLED", True)
        on = calculate_system_state({**base, "M1B_YoY_pct": m1b, "M2_YoY_pct": m2})
        assert off["exposure_limit_pct"] == 70 and on["exposure_limit_pct"] == cap_on
        assert ("資金緊縮" in on["Macro_Phase"]) is tight
        assert "資金緊縮" not in off["Macro_Phase"]
        assert "disabled_inputs" not in on and MSL.M1B_M2_LEG_DISABLED_LABEL not in on["Macro_Phase"]

    def test_flag_on_is_byte_identical_to_pre_engine(self, monkeypatch):
        monkeypatch.setattr(ST, "M1B_M2_LEG_ENABLED", True)
        pre = _pre_z66_engine()
        for i, d in _grid(2000, seed=661):
            assert calculate_system_state(copy.deepcopy(d)) == pre(copy.deepcopy(d)), i
            assert (calculate_system_state(copy.deepcopy(d), include_veto_flags=True)
                    == pre(copy.deepcopy(d), include_veto_flags=True)), i

    def test_flag_on_m1b_only_escapes_fail_safe_like_before(self, monkeypatch):
        """反向對照：開關 True（修前語意）時只有 M1B／M2 ⇒ 不是 fail-safe —— 證明上面那條守到東西。"""
        monkeypatch.setattr(ST, "M1B_M2_LEG_ENABLED", True)
        out = calculate_system_state({"M1B_YoY_pct": 8.0, "M2_YoY_pct": 4.0})
        assert out["market_regime"] != "系統異常" and out["exposure_limit_pct"] == 80


# ══════════════════════════════════════════════════════════════════════════
# 3. L3 macro_engine_inputs：停用 ≠ 未評估
# ══════════════════════════════════════════════════════════════════════════
class TestEngineInputs:
    def test_full_inputs(self):
        b = _build(_inputs())
        assert b.disabled_inputs == _LEG and b.not_evaluated == ()
        r = M.run_rule_engine(b)
        assert r["not_evaluated"] == [] and r["disabled_inputs"] == list(_LEG)
        assert "missing_inputs" not in r

    def test_m1b_missing_is_not_reported(self):
        b = _build(_inputs(m1b=None, m2=None))
        assert b.not_evaluated == () and b.disabled_inputs == _LEG
        assert b.assessed["M1B_YoY_pct"].scoring_value is None   # 資料面照實評估

    def test_flag_on_restores_not_evaluated(self, monkeypatch):
        monkeypatch.setattr(ST, "M1B_M2_LEG_ENABLED", True)
        b = _build(_inputs(m1b=None, m2=None))
        assert b.disabled_inputs == () and set(b.not_evaluated) == set(_LEG)


# ══════════════════════════════════════════════════════════════════════════
# 4. risk_cap_apply：規則版本、v2 來源、資料月
# ══════════════════════════════════════════════════════════════════════════
class TestRiskCapApply:
    def test_payload_stamped(self, l1, tmp_path):
        kw = _inputs()
        l1(kw["pmi_history"])
        f = tmp_path / "macro_state.json"
        res = RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(f))
        assert res.written
        state = json.loads(f.read_text(encoding="utf-8"))
        assert state["engine_source"] == RC.ENGINE_SOURCE == "new_ui_risk_cap_v2"
        assert state[RP.RISK_CAP_RULESET_VERSION_KEY] == RP.RISK_CAP_RULESET_VERSION
        assert RP.RISK_CAP_RULESET_VERSION_KEY in RC.ATTACHED_KEYS
        assert state["disabled_inputs"] == list(_LEG) and state["not_evaluated"] == []
        assert state["m1b_m2_data_month"] is None
        assert res.bundle_summary["disabled_inputs"] == list(_LEG)
        assert "資金緊縮" not in state["Macro_Phase"]

    def test_leg_on_month_restored(self, l1, tmp_path, monkeypatch):
        monkeypatch.setattr(ST, "M1B_M2_LEG_ENABLED", True)
        kw = _inputs()
        l1(kw["pmi_history"])
        f = tmp_path / "macro_state.json"
        RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(f))
        assert json.loads(f.read_text(encoding="utf-8"))["m1b_m2_data_month"] == "2026-08"

    def test_m1b_8_m2_4_does_not_raise_cap(self, l1, tmp_path):
        """客戶情境：M1B 8／M2 4（spread +4，修前 +15）⇒ 上限與「沒有 M1B／M2」相同。"""
        caps = []
        for m1b, m2 in ((8.0, 4.0), (None, None)):
            kw = _inputs(m1b=m1b, m2=m2)
            l1(kw["pmi_history"])
            f = tmp_path / f"m_{m1b}.json"
            assert RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(f)).written
            caps.append(json.loads(f.read_text(encoding="utf-8"))["exposure_limit_pct"])
        assert caps[0] == caps[1]


# ══════════════════════════════════════════════════════════════════════════
# 5. 步驟報告：停用另起一句，⛔ 不算進「未評估 N 項」
# ══════════════════════════════════════════════════════════════════════════
class TestRefreshReport:
    def test_written_report_says_disabled(self, monkeypatch, tmp_path):
        kw = _inputs()
        r, _, _ = _run_refresh(monkeypatch, tmp_path, session=_session_from(kw),
                               pmi_hist=kw["pmi_history"])
        s = _step(r, RS.STEP_RISK_CAP)
        assert s.ok and "未評估 0 項" in s.detail
        assert "M1B-M2 資金活水已停用、不計分（M1B_YoY_pct、M2_YoY_pct；不屬未評估）" in s.detail
        assert "M1B_YoY_pct；缺項不計分" not in s.detail

    def test_flag_on_no_disabled_sentence(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ST, "M1B_M2_LEG_ENABLED", True)
        kw = _inputs()
        r, _, _ = _run_refresh(monkeypatch, tmp_path, session=_session_from(kw),
                               pmi_hist=kw["pmi_history"])
        assert "已停用" not in _step(r, RS.STEP_RISK_CAP).detail


# ══════════════════════════════════════════════════════════════════════════
# 6. allocation_decision：系統風險上限說明不再宣稱 M1B-M2 計分
# ══════════════════════════════════════════════════════════════════════════
class TestAllocationBasis:
    def _basis(self):
        from shared.allocation_decision import build_allocation_decision
        d = build_allocation_decision({"is_loaded": True, "health": 60.0, "regime": "neutral",
                                       "defense": False, "exposure_limit_pct": 50},
                                      throttle=None, caps=(), conflicts=())
        (c,) = [c for c in d.caps if c.name == "系統風險上限"]
        return c.reason

    def test_off_wording(self):
        from shared.allocation_decision import SYSTEM_RISK_CAP_BASIS_LEG_OFF
        txt = self._basis()
        assert txt == SYSTEM_RISK_CAP_BASIS_LEG_OFF
        assert "VIX／PMI／M1B-M2" not in txt and "M1B-M2 資金活水已停用、不計分" in txt

    def test_on_wording_mutation(self, monkeypatch):
        monkeypatch.setattr(ST, "M1B_M2_LEG_ENABLED", True)
        assert "VIX／PMI／M1B-M2／BIAS240" in self._basis()


# ══════════════════════════════════════════════════════════════════════════
# 7. 源碼突變自驗（恰一次字面替換；突變體上，上面的守衛必紅）
# ══════════════════════════════════════════════════════════════════════════
class TestSourceMutations:
    _BASE = {"VIX_Index": 18.0, "ISM_PMI_or_OECD_CLI": 51.0, "PMI_Prev_Month": 51.0,
             "BIAS240_pct": 0.0, "PCR": 1.0, "Futures_Net_Short": 0.0,
             "M1B_YoY_pct": 8.0, "M2_YoY_pct": 4.0}

    def test_spread_gate_removed_raises_cap(self):
        from tests.test_p01_macro_refresh import _mutated_module
        mod = _mutated_module(_MSL_REL, ("if (_leg_on and _m1b_m2_both) else None",
                                         "if _m1b_m2_both else None"))
        assert calculate_system_state(dict(self._BASE))["exposure_limit_pct"] == 60
        assert mod.calculate_system_state(dict(self._BASE))["exposure_limit_pct"] == 80

    def test_fail_safe_counting_all_eight_lets_leg_escape(self):
        from tests.test_p01_macro_refresh import _mutated_module
        mod = _mutated_module(_MSL_REL, ("    if len(missing_inputs) == len(_enabled) and not sahm:",
                                         "    if len(missing_inputs) == len(_ENGINE_NUMERIC_INPUTS) and not sahm:"))
        only = {"M1B_YoY_pct": 8.0, "M2_YoY_pct": 4.0}
        assert calculate_system_state(dict(only))["market_regime"] == "系統異常"
        assert mod.calculate_system_state(dict(only))["market_regime"] != "系統異常"

    def test_disabled_counted_as_missing(self):
        from tests.test_p01_macro_refresh import _mutated_module
        mod = _mutated_module(_MSL_REL, ("    missing_inputs = [k for k in _enabled if _nums[k] is None]",
                                         "    missing_inputs = [k for k in _ENGINE_NUMERIC_INPUTS if _nums[k] is None]"))
        out = mod.calculate_system_state({"VIX_Index": 18.0})
        assert "M1B_YoY_pct" in out["missing_inputs"]          # 突變體 ⇒ test_disabled_is_not_missing 會紅
        assert "M1B_YoY_pct" not in calculate_system_state({"VIX_Index": 18.0})["missing_inputs"]
