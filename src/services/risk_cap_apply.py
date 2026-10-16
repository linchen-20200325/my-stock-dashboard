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
判定（三條任一成立；批 Z66 加第 3 條，見下）：
  1. 引擎回 fail-safe（`veto_flags["fail_safe"] is True`：**啟用中的**數值輸入全缺且薩姆未觸發；
     本路徑薩姆一律送 None ⇒ 等同「啟用中的數值輸入全缺」。批 Z66 起 M1B／M2 停用、不算在內）；
  2. `exposure_limit_pct` 不是有限數（含 bool）；
  3. 批 Z66（客戶 2026-10-16 Q1）：**Required Core**（L0 `shared.risk_cap_policy.REQUIRED_CORE_INPUTS`：
     VIX、台灣 PMI 當月、台灣 PMI 前月、外資期貨淨空單＋加權指數跌破 MA5）任一無法評估 ⇒
     本輪**不產生新的系統風險上限**（`REASON_CORE_MISSING`，點名缺的核心項）。引擎本身的「缺項不計分」
     計算不改（Q1 是「能不能產生新上限」的閘門，不是引擎變更）；Optional（M1B／M2、PCR、BIAS240）
     缺時照寫、`not_evaluated` 揭露。核心齊全才寫，並蓋 `required_core_ok: True`＋規則版本 ——
     新 UI 讀端（`get_macro_state(require_valid_risk_cap=True)`）只認這種檔。
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

═══ AUD-C21：雙寫（客戶 2026-10-16 裁示；有意識的變更）═══════════════════════════
新 UI 自己的快照檔 `shared.risk_cap_policy.RISK_CAP_STATE_FILE`（`risk_cap_state.json`）——
舊 UI 每次寫 `macro_state.json` 都整份覆寫（兩個戳記一起洗掉），新 UI 的有效上限因此不能再住在那個檔裡。
寫入順序：**先新檔、再 `macro_state.json`**，內容逐位元組相同（`lock_system_state_only` 回傳的那一份，
經 `write_state_snapshot` 原樣寫第二份）。為什麼仍寫 `macro_state.json`：它是舊 UI 的上限來源、也是
`get_macro_state()` 位階的第 3 順位來源（warroom 缺席或沒有健康分時）—— 不寫就會改變位階與舊 UI 的資料流
（AUD-C22，客戶指示本批不動）。上方「無法計算 ⇒ 不寫檔」對**兩個檔**同樣成立（一個位元組都不動）。
全有或全無（盡力）：新檔寫成、`macro_state.json` 寫失敗 ⇒ 新檔還原成寫入前的內容（原本不存在就刪掉），
再把原例外往上拋（⛔ 不留下「新檔是本輪、舊檔是上一輪」的半套狀態）。逐檔結果見 `files_written`。

分層（CLAUDE.md §8.2）：L3 —— 依賴 L3（`macro_engine_inputs` / `macro_state_locker`），
零 L4 / L5 import、不 import streamlit、**不寫 session**（session 由呼叫端傳入，唯讀）。
"""
from __future__ import annotations

import json
import math
import numbers
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from shared.risk_cap_policy import REQUIRED_CORE_LABELS, REQUIRED_CORE_OK_KEY
from src.services.macro_engine_inputs import (
    ENGINE_INPUT_KEYS,
    EngineInputBundle,
    load_engine_inputs_from_session,
    required_core_gaps,
    run_rule_engine,
)
from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION, RISK_CAP_RULESET_VERSION_KEY
from shared.risk_cap_policy import RISK_CAP_STATE_FILE
from src.services.macro_state_locker import MacroStateLocker

#: 寫進檔案的來源標記。
#: ~~`"new_ui_risk_cap_v1"`~~ 📌 批 Z66（客戶 2026-10-16 Q2，有意識的變更，⛔ 不是漏改）：M1B-M2 腿停用、
#: 檔案多帶規則版本 ⇒ 升 v2。v1 字樣只出現在批 Z65～Z66 之間寫的舊檔裡（不改寫歷史檔）。
ENGINE_SOURCE: str = "new_ui_risk_cap_v2"

#: 附帶欄位（引擎原有鍵以外、本檔加進檔案的鍵）。⛔ 不得與引擎輸出重名。
ATTACHED_KEYS: tuple[str, ...] = ("engine_source", "input_detail", "m1b_m2_data_month",
                                  RISK_CAP_RULESET_VERSION_KEY, REQUIRED_CORE_OK_KEY)

#: 無法計算的兩種原因（步驟報告與回傳值共用，⛔ 不在呼叫端另寫一份）。
#: 📌 批 Z66：「8 項」→「啟用中的」（M1B／M2 停用後，fail-safe 只看啟用中的輸入；有意識的措辭更正）。
REASON_FAIL_SAFE: str = (
    "規則引擎啟用中的數值輸入本輪全部無法計分（未取得或已過期）→ 引擎回 fail-safe「系統異常」；"
    "本輪無法計算，不寫檔（既有檔若有，保留不動）")
#: 批 Z66（Q1）：Required Core 缺 ⇒ 不產生新上限。`{items}` ＝ 缺的核心項（客戶語言名稱＋鍵名＋狀態）。
REASON_CORE_MISSING: str = (
    "Required Core 無法評估：{items} → 本輪不產生新的系統風險上限，不寫檔（既有檔若有，保留不動）")
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
        missing_core: 批 Z66（Q1）：無法評估的 Required Core 鍵名（依 `REQUIRED_CORE_INPUTS` 順序；
            核心齊全 ⇒ `()`）。不論有沒有寫檔都照實帶（fail-safe 時通常也是全缺）。
        files_written: AUD-C21：這一輪**實際寫成**的檔（檔名、依寫入順序：新 UI 檔在前、`macro_state.json` 在後）。
            `written=True` ⇔ 兩個都在；沒寫 ⇒ `()`。
    """

    written: bool
    reason: str
    bundle_summary: dict
    engine_result: dict | None
    missing_core: tuple[str, ...] = ()
    files_written: tuple[str, ...] = ()


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


def _core_items_text(gaps: tuple[tuple[str, str], ...]) -> str:
    """`required_core_gaps` → 「VIX（VIX_Index：未取得（…））、…」。"""
    return "、".join(f"{REQUIRED_CORE_LABELS.get(k, k)}（{k}：{why}）" for k, why in gaps)


def _is_finite_cap(v: Any) -> bool:
    if isinstance(v, bool) or not isinstance(v, numbers.Real):
        return False
    return math.isfinite(float(v))


def _restore_file(path: str, previous: bytes | None) -> None:
    """把 `path` 還原成 `previous`（None ⇒ 原本不存在 ⇒ 刪掉）。暫存檔＋`os.replace`，⛔ 不留半截檔。"""
    if previous is None:
        if os.path.exists(path):
            os.remove(path)
        return
    _tmp = path + ".tmp"
    with open(_tmp, "wb") as f:
        f.write(previous)
    os.replace(_tmp, path)


def compute_and_lock_risk_cap(session: Any, *, now: datetime,
                              state_file_path: str = "macro_state.json",
                              risk_cap_state_file_path: str | None = None) -> RiskCapApplyResult:
    """算一次系統風險上限；算得出來才寫（AUD-C21：先寫新 UI 的 `risk_cap_state.json`，再寫 `macro_state.json`）。

    Args:
        session: 讀 `macro_info`／`bias_info`／`m1b_m2_info`／`li_latest`／`mkt_info` 的 mapping
            （通常是 `st.session_state`）。**唯讀**。
        now: 帶時區的 `datetime`（naive → `ValueError`，見 Z64）。
        state_file_path: 與 `get_macro_state()` 預設同一個相對路徑。
        risk_cap_state_file_path: AUD-C21 新 UI 快照檔；None ⇒ `state_file_path` 同目錄的
            `RISK_CAP_STATE_FILE`（與 `get_macro_state()` 讀端同一條預設規則）。

    Returns:
        `RiskCapApplyResult`。無法計算 → `written=False`，檔案一個位元組都不動。

    Raises:
        任何取值／引擎／JSON 檢查／寫檔例外 —— ⛔ 不吞、不清既有檔。
    """
    bundle = load_engine_inputs_from_session(session, now=now)
    engine = run_rule_engine(bundle, include_veto_flags=True)
    summary = _bundle_summary(bundle)
    gaps = required_core_gaps(bundle)
    missing_core = tuple(k for k, _ in gaps)

    veto = engine.get("veto_flags")
    if not isinstance(veto, dict) or "fail_safe" not in veto:
        raise RuntimeError(f"規則引擎輸出缺 `veto_flags`（契約破損，⛔ 不猜）：{veto!r}")
    if veto["fail_safe"] is True:
        print(f"[risk_cap_apply] ⚠️ {REASON_FAIL_SAFE}")
        return RiskCapApplyResult(False, REASON_FAIL_SAFE, summary, engine, missing_core)
    cap = engine.get("exposure_limit_pct")
    if not _is_finite_cap(cap):
        why = REASON_NOT_FINITE.format(value=cap)
        print(f"[risk_cap_apply] ⚠️ {why}")
        return RiskCapApplyResult(False, why, summary, engine, missing_core)
    # 批 Z66（客戶 2026-10-16 Q1）：Required Core 任一無法評估 ⇒ 不產生新上限、不寫檔（⛔ 不因缺資料放寬風控）。
    #   排在 fail-safe／非有限數之後：那兩條是「引擎根本沒給出可用上限」，原因照舊報；本條是「給得出、但不准用」。
    if gaps:
        why = REASON_CORE_MISSING.format(items=_scrub_nonfinite_text(_core_items_text(gaps)))
        print(f"[risk_cap_apply] ⚠️ {why}")
        return RiskCapApplyResult(False, why, summary, engine, missing_core)

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
    payload[REQUIRED_CORE_OK_KEY] = True     # 批 Z66（Q1）：走到這裡 ⇔ Required Core 全部可評估
    # 寫檔前先驗：任何 NaN／±inf 數值 → ValueError（此時尚未碰檔案）。
    json.dumps(payload, ensure_ascii=False, allow_nan=False)

    # ~~# ⚠️ 寫檔之後不再做任何可能拋例外的事（含 print）：例外 ⇔ 這一輪沒有寫成功，呼叫端據此報告。~~
    # ~~MacroStateLocker(state_file_path=state_file_path).lock_system_state_only(payload)~~
    # ~~return RiskCapApplyResult(True, "", summary, payload)~~
    # 📌 AUD-C21（客戶 2026-10-16，有意識的變更，⛔ 不是漏刪）：單寫 `macro_state.json` → 雙寫（新檔在前）。
    #   舊寫法「寫檔後不再做可能拋例外的事」的理由仍然成立，照守：第二個檔寫完之後同樣什麼都不做。
    _rc_path = (risk_cap_state_file_path if risk_cap_state_file_path is not None
                else os.path.join(os.path.dirname(state_file_path), RISK_CAP_STATE_FILE))
    try:
        with open(_rc_path, "rb") as _f:
            _rc_before: bytes | None = _f.read()
    except FileNotFoundError:
        _rc_before = None
    _final = MacroStateLocker(state_file_path=_rc_path).lock_system_state_only(payload)   # ① 新 UI 檔
    try:
        MacroStateLocker(state_file_path=state_file_path).write_state_snapshot(_final)     # ② macro_state.json
    except BaseException:
        _restore_file(_rc_path, _rc_before)      # 盡力全有或全無；還原本身失敗會蓋過原例外往上拋（⛔ 不吞）
        raise
    return RiskCapApplyResult(True, "", summary, payload, files_written=(
        os.path.basename(_rc_path), os.path.basename(state_file_path)))
