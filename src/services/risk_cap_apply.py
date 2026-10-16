"""src/services/risk_cap_apply.py — 新 UI「🚀 更新今日戰情」的系統風險上限寫入端（L3，批 Z65 / F5）。

═══ 為什麼有這個檔 ═══════════════════════════════════════════════════
卡①「建議持股」的最終值 ＝ 姿態帶與各條硬否決天花板取低；其中「系統風險上限」那一條
（`get_macro_state()` 的 `exposure_limit_pct`）只來自 `macro_state.json`。修前全 repo 只有舊 UI
`src/ui/tabs/macro/section_news_ai.py`（§十一「執行 AI 裁決」）寫得到它 —— 只用新 UI 的人，
這條天花板永遠是「上一次跑舊分頁留下的值」或根本沒有。
客戶 2026-10-14 題2＝A：「🚀 更新今日戰情」自動計算系統風險上限，沿用既有公式與條件，
不新增 AI 金鑰依賴；缺資料不補 0、不用前值；無法計算時要明示，⛔ 不得因此放寬風控。

═══ 做法（計算零複製）═════════════════════════════════════════════════
    load_engine_inputs_from_session(session, now)   ← L3 Z64（取值＋新鮮度＋型別檢查）
      → run_rule_engine(bundle, include_veto_flags=True)
                                                     ← 未改公式的 `calculate_system_state`
      → MacroStateLocker.lock_system_state_only(...) ← 與舊 UI 同一支寫檔 API（原子寫入）

═══ 無法計算 ⇒ 不寫檔、不覆寫（保住 7 天保留機制）══════════════════════════
判定（兩條任一成立）：
  1. 引擎回 fail-safe（`veto_flags["fail_safe"] is True`：**啟用中的**數值輸入全缺且薩姆未觸發；
     本路徑薩姆一律送 None ⇒ 等同「啟用中的數值輸入全缺」。批 Z66 起 M1B／M2 停用、不算在內）；
  2. `exposure_limit_pct` 不是有限數（含 bool）。
此時**一個位元組都不寫**：既有 `macro_state.json` 若仍在 `MACRO_VERDICT_MAX_AGE_DAYS` 內，
`get_macro_state()` 照舊讀到那一次的有效上限；過期或不存在時，`get_macro_state()` 不給上限，
新頁的建議持股顯示「無法判定」（客戶 Q-z34～36 規則；`src/ui/views/risk_cap_gate.py`）。
⛔ 不寫一份 fail-safe 檔去蓋掉它 —— 那等於把「這一輪沒資料」變成「上一次的有效上限被刪掉」。

═══ 與舊 UI 寫檔的關係 ═════════════════════════════════════════════════
- 同一支 `lock_system_state_only`：它**整份覆寫**檔案（`{**system_state, exposure_limit_pct（夾 0~100）,
  analysis_summary, timestamp}`），**不保留也不合併**既有檔內任何欄位 —— 與舊 UI 每次按鈕的行為相同。
  （`execute_and_lock` 才會寫 AI 解讀欄位；它 0 個 production 呼叫點。）
- 附帶欄位（舊 UI 沒有，讀端一律 `.get` 具名鍵，多了不影響 —— 消費端盤點見 tests/test_batch_z65.py）：
  `engine_source`、`input_asof`、`not_evaluated`、`red_lines`、`veto_flags`、`input_detail`、
  `risk_cap_ruleset_version`（批 Z66：L0 `shared.risk_cap_policy.RISK_CAP_RULESET_VERSION`）；
  `m1b_m2_data_month` 比照舊 UI（只在 M1B／M2 真的進了計分時才有值，否則 None —— 批 Z66 起 M1B-M2 腿
  停用 ⇒ 恆為 None）；引擎輸出另帶 `disabled_inputs`（停用、不計分的輸入；≠ `not_evaluated`）。
- 刻意差異（輸入端）沿用 Z64，逐條見 `macro_engine_inputs` 檔頭（PMI 前月取 parquet 真正前一資料月、
  過期不計分、PCR／外資期貨逐欄往回找、bool／字串判缺、薩姆送 None）。

═══ 例外 ══════════════════════════════════════════════════════════════
⛔ 不吞：取值／引擎／JSON 檢查／寫檔任一步拋例外 → 原樣往上拋，由 `refresh_macro_now` 記成失敗的步驟。
寫檔前的 JSON 檢查（`allow_nan=False`）先跑，炸了就不會碰檔案；`_write_state_lock` 是暫存檔＋
`os.replace`，寫到一半失敗也不會留下殘缺或被清空的 `macro_state.json`。⛔ 失敗時不清既有檔。

分層（CLAUDE.md §8.2）：L3 —— 依賴 L3（`macro_engine_inputs` / `macro_state_locker`），
零 L4 / L5 import、不 import streamlit、**不寫 session**（session 由呼叫端傳入，唯讀）。
"""
from __future__ import annotations

import json
import math
import numbers
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.services.macro_engine_inputs import (
    ENGINE_INPUT_KEYS,
    EngineInputBundle,
    load_engine_inputs_from_session,
    run_rule_engine,
)
from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION, RISK_CAP_RULESET_VERSION_KEY
from src.services.macro_state_locker import MacroStateLocker

#: 寫進檔案的來源標記。
#: ~~`"new_ui_risk_cap_v1"`~~ 📌 批 Z66（客戶 2026-10-16 Q2，有意識的變更，⛔ 不是漏改）：M1B-M2 腿停用、
#: 檔案多帶規則版本 ⇒ 升 v2。v1 字樣只出現在批 Z65～Z66 之間寫的舊檔裡（不改寫歷史檔）。
ENGINE_SOURCE: str = "new_ui_risk_cap_v2"

#: 附帶欄位（引擎原有鍵以外、本檔加進檔案的鍵）。⛔ 不得與引擎輸出重名。
ATTACHED_KEYS: tuple[str, ...] = ("engine_source", "input_detail", "m1b_m2_data_month",
                                  RISK_CAP_RULESET_VERSION_KEY)

#: 無法計算的兩種原因（步驟報告與回傳值共用，⛔ 不在呼叫端另寫一份）。
#: 📌 批 Z66：「8 項」→「啟用中的」（M1B／M2 停用後，fail-safe 只看啟用中的輸入；有意識的措辭更正）。
REASON_FAIL_SAFE: str = (
    "規則引擎啟用中的數值輸入本輪全部無法計分（未取得或已過期）→ 引擎回 fail-safe「系統異常」；"
    "本輪無法計算，不寫檔（既有檔若有，保留不動）")
REASON_NOT_FINITE: str = "引擎回傳的曝險上限不是有限數（{value!r}）；本輪無法計算，不寫檔（既有檔若有，保留不動）"

#: 紅線 reason 內的非有限值 repr（`nan` / `inf` / `-inf` / `infinity`）→ 改寫成這幾個字。
#: 只改字面、不改語意：上游值是 NaN 時，Z64 的 reason 會帶「（nan）」，落檔後讀者分不出那是
#: 「值是 NaN」還是一個字串 —— 檔案內一律不出現 nan／inf 字面。
NONFINITE_TEXT: str = "非有限值"
_NONFINITE_TOKEN = re.compile(r"(?<![A-Za-z])[-+]?(?:nan|inf(?:inity)?)(?![A-Za-z])", re.IGNORECASE)


@dataclass(frozen=True)
class RiskCapApplyResult:
    """這一步的結論（呼叫端照這份記報告，不自己判斷）。

    Attributes:
        written: 這一輪有沒有寫 `macro_state.json`。
        reason: 沒寫的原因（`written=True` 時為空字串）。
        bundle_summary: 取值結果摘要（可 JSON 化）：today / calendar_error / not_evaluated /
            disabled_inputs（批 Z66：停用、不計分；≠ 未評估）/ input_asof / red_lines（名稱 → status）。
        engine_result: 引擎輸出（含 `veto_flags` 與 Z64 附加鍵）；寫檔時就是落檔前的那份
            （不含 `analysis_summary` / `timestamp`，那兩個由 `lock_system_state_only` 補）。
    """

    written: bool
    reason: str
    bundle_summary: dict
    engine_result: dict | None


def _json_scalar(v: Any) -> Any:
    """輸入值 → 可 JSON 化的純量：bool 照留、有限實數 → int／float、其餘（含 NaN／±inf）→ None。"""
    if isinstance(v, bool):
        return v
    if type(v).__module__ == "numpy" and type(v).__name__ in ("bool", "bool_"):
        return bool(v)
    if isinstance(v, numbers.Integral):
        return int(v)
    if isinstance(v, numbers.Real):
        f = float(v)
        return f if math.isfinite(f) else None
    return None


def _input_detail(bundle: EngineInputBundle) -> dict:
    """逐項 `{value, status, as_of_or_month, lag, lag_unit}`（結構化、可 JSON 化；⛔ 不放 reason 字串）。"""
    out: dict[str, dict] = {}
    for k in ENGINE_INPUT_KEYS:
        av = bundle.assessed[k]
        lag = av.verdict.lag
        out[k] = {
            "value": _json_scalar(av.dv.value),
            "status": av.verdict.status.value,
            "as_of_or_month": bundle.input_asof.get(k),
            "lag": int(lag) if lag is not None else None,
            "lag_unit": str(av.verdict.lag_unit),
        }
    return out


def _scrub_nonfinite_text(text: str) -> str:
    return _NONFINITE_TOKEN.sub(NONFINITE_TEXT, str(text))


def _bundle_summary(bundle: EngineInputBundle) -> dict:
    return {
        "today": bundle.today.isoformat(),
        "calendar_error": bundle.calendar_error,
        "not_evaluated": list(bundle.not_evaluated),
        "disabled_inputs": list(bundle.disabled_inputs),
        "input_asof": dict(bundle.input_asof),
        "red_lines": {k: v.status for k, v in bundle.red_lines.items()},
    }


def _m1b_m2_data_month(bundle: EngineInputBundle) -> str | None:
    """比照舊 UI：M1B 與 M2 **都真的進了計分**才回資料月（'YYYY-MM'）；否則 None。

    批 Z66（Q2）：M1B-M2 腿停用時兩者都不進計分 ⇒ 一律 None（⛔ 不寫一個「本次計分用到的資料月」假象）。
    """
    if any(k in bundle.disabled_inputs for k in ("M1B_YoY_pct", "M2_YoY_pct")):
        return None
    nums = bundle.macro_numbers
    if nums.get("M1B_YoY_pct") is None or nums.get("M2_YoY_pct") is None:
        return None
    return bundle.input_asof.get("M1B_YoY_pct")


def _is_finite_cap(v: Any) -> bool:
    if isinstance(v, bool) or not isinstance(v, numbers.Real):
        return False
    return math.isfinite(float(v))


def compute_and_lock_risk_cap(session: Any, *, now: datetime,
                              state_file_path: str = "macro_state.json") -> RiskCapApplyResult:
    """算一次系統風險上限；算得出來才寫 `macro_state.json`（經 `lock_system_state_only`）。

    Args:
        session: 讀 `macro_info`／`bias_info`／`m1b_m2_info`／`li_latest`／`mkt_info` 的 mapping
            （通常是 `st.session_state`）。**唯讀**。
        now: 帶時區的 `datetime`（naive → `ValueError`，見 Z64）。
        state_file_path: 與 `get_macro_state()` 預設同一個相對路徑。

    Returns:
        `RiskCapApplyResult`。無法計算 → `written=False`，檔案一個位元組都不動。

    Raises:
        任何取值／引擎／JSON 檢查／寫檔例外 —— ⛔ 不吞、不清既有檔。
    """
    bundle = load_engine_inputs_from_session(session, now=now)
    engine = run_rule_engine(bundle, include_veto_flags=True)
    summary = _bundle_summary(bundle)

    veto = engine.get("veto_flags")
    if not isinstance(veto, dict) or "fail_safe" not in veto:
        raise RuntimeError(f"規則引擎輸出缺 `veto_flags`（契約破損，⛔ 不猜）：{veto!r}")
    if veto["fail_safe"] is True:
        print(f"[risk_cap_apply] ⚠️ {REASON_FAIL_SAFE}")
        return RiskCapApplyResult(False, REASON_FAIL_SAFE, summary, engine)
    cap = engine.get("exposure_limit_pct")
    if not _is_finite_cap(cap):
        why = REASON_NOT_FINITE.format(value=cap)
        print(f"[risk_cap_apply] ⚠️ {why}")
        return RiskCapApplyResult(False, why, summary, engine)

    clash = [k for k in ATTACHED_KEYS if k in engine]
    if clash:
        raise RuntimeError(f"引擎輸出已含附帶欄位名 {clash}，⛔ 不覆寫")
    payload = dict(engine)
    payload["red_lines"] = {
        name: {**rl, "reason": _scrub_nonfinite_text(rl.get("reason", ""))}
        for name, rl in engine["red_lines"].items()}
    payload["engine_source"] = ENGINE_SOURCE
    payload["input_detail"] = _input_detail(bundle)
    payload["m1b_m2_data_month"] = _m1b_m2_data_month(bundle)
    payload[RISK_CAP_RULESET_VERSION_KEY] = RISK_CAP_RULESET_VERSION   # 批 Z66：規則版本（L0 SSOT）
    # 寫檔前先驗：任何 NaN／±inf 數值 → ValueError（此時尚未碰檔案）。
    json.dumps(payload, ensure_ascii=False, allow_nan=False)

    # ⚠️ 寫檔之後不再做任何可能拋例外的事（含 print）：例外 ⇔ 這一輪沒有寫成功，呼叫端據此報告。
    MacroStateLocker(state_file_path=state_file_path).lock_system_state_only(payload)
    return RiskCapApplyResult(True, "", summary, payload)
