"""src/services/risk_cap_history_service.py — 每日系統風險上限歷史紀錄的組裝／比較（L3；VN1-STORE 最小 PoC）。

═══ 範圍（客戶 2026-10-19 裁示 A，逐點對應）═══════════════════════════════════
1. 無頭環境用**既有**正式資料層與規則算每日 System Risk Cap：`run_headless_refresh` 直接呼叫
   畫面同一支 `macro_refresh_service.refresh_macro_now`（同一條 L1 取數 → L3 編排 → 引擎 → 寫檔），
   只把寫檔目錄改成呼叫端給的暫存目錄。⛔ 沒有 `if headless:` 分支、沒有自算公式。
2. ⛔ 不另造公式／資料源、不補 0、不猜缺值、AI 不參與：本檔只**讀**引擎結果與官方讀端判定。
3. Required Core 不齊／過期／取數失敗 ⇒ 照實記狀態（`STATUS_*`），`exposure_limit_pct` 一律空白。
6. 每列可追溯：record_date、input_asof、狀態、正式上限值、規則版本、provenance（schema 見 L0）。
7. `compare_status`：沒有歷史 ⇒「從今天開始記錄」；預期日期沒紀錄／不是有效紀錄／已過期 ⇒ ⛔ 不比較。
8. 冪等見 L1 `src/data/macro/risk_cap_history.upsert_record`。
（第 4、5 點：本檔與個人持股 Sheet 路徑零交集；本 PoC 不寫任何真實 Sheet。）

「VALID」的唯一判準：這一輪真的寫出快照，**且**官方讀端
`macro_state_locker.get_macro_state(require_valid_risk_cap=True)` 對這個目錄讀得到上限 ——
與新 UI 卡①收件條件同一條（Required Core、規則版本、7 天有效期、上限格式），⛔ 本檔不另判。

分層（CLAUDE.md §8.2）：L3 —— import L0 與 L3（`macro_refresh_service` / `risk_cap_apply` /
`macro_state_locker` / `trading_calendar_service`）；不 import L1 寫入端以外的東西、零 L4/L5。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from shared import risk_cap_history_policy as P
from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION, RISK_CAP_STATE_FILE
from shared.secret_scrub import scrub_secrets

#: 暫存目錄裡的舊 UI 檔名（`compute_and_lock_risk_cap` 的 `state_file_path`；新 UI 檔落同目錄）。
MACRO_STATE_FILE_NAME: str = "macro_state.json"


def run_headless_refresh(state_dir: str) -> Any:
    """無頭跑一次畫面同一條「🚀 更新今日戰情」鏈；風險上限快照寫進 `state_dir`（⛔ 不碰 app 工作目錄的檔）。

    `MODE_WARM`：無頭行程本來就沒有暖快取；⛔ 不用 `MODE_FORCE`（它會清本機 pkl／proxy 快取，PoC 不該動它們）。
    """
    from src.services import macro_refresh_service as RS
    os.makedirs(state_dir, exist_ok=True)
    return RS.refresh_macro_now(
        mode=RS.MODE_WARM,
        risk_cap_state_file_path=os.path.join(state_dir, MACRO_STATE_FILE_NAME))


def headless_session() -> Any:
    """`run_headless_refresh` 寫入的那一份 session（`macro_refresh_service` 用的同一個 `st.session_state`）。

    只給 `build_record(session=...)` 讀上游 dict 自帶的 `is_stale` 旗標用（provenance）；⛔ 不寫。
    """
    from src.services import macro_refresh_service as RS
    return RS.st.session_state


#: Required Core 輸入 → 上游 session 原始 dict 的位置（只用來讀它**自帶的** `is_stale` 旗標）。
#: None ＝ 該輸入的上游輸出沒有 `is_stale` 這種欄位（PMI 前月來自 parquet、外資期貨來自先行指標表、
#: MA5 來自 mkt_info）⇒ provenance 一律記 "unknown"，⛔ 不推定。
_CORE_UPSTREAM_STALE_FLAG: Mapping[str, tuple[str, str] | None] = {
    "VIX_Index": ("macro_info", "vix"),
    "ISM_PMI_or_OECD_CLI": ("macro_info", "ism_pmi"),
    "PMI_Prev_Month": None,
    "Futures_Net_Short": None,
    "Index_Below_MA5": None,
}
UNKNOWN: str = "unknown"

# ══════════════════════════════════════════════════════════════════════
# 紀錄組裝
# ══════════════════════════════════════════════════════════════════════
def _s(v: Any) -> str:
    """一律序列化成字串（Sheets RAW 寫入、讀回仍是同一字串）。None ⇒ 空白（⛔ 不寫 0）。"""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (list, tuple)):
        return ",".join(str(x) for x in v)
    if isinstance(v, Mapping):
        return json.dumps(dict(v), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(v)


def _status_from_not_written(rc: Any) -> str:
    """`RiskCapApplyResult(written=False)` → 狀態。對映既有 `REASON_*`；對不上 ⇒ 拋（⛔ 不猜）。"""
    from src.services import risk_cap_apply as RC
    reason = str(rc.reason or "")
    if reason == RC.REASON_FAIL_SAFE:
        return P.STATUS_ENGINE_FAILSAFE
    if reason.startswith(RC.REASON_NOT_FINITE.split("{", 1)[0]):
        return P.STATUS_ENGINE_NOT_FINITE
    if rc.missing_core and reason.startswith(RC.REASON_CORE_MISSING.split("{", 1)[0]):
        return P.STATUS_REQUIRED_CORE_INCOMPLETE
    raise RuntimeError(f"無法對映的未寫檔原因（契約破損，⛔ 不猜）：{reason!r}")


def _step(report: Any, name: str) -> Any:
    hits = [s for s in report.steps if s.name == name]
    return hits[-1] if hits else None


def _refresh_failed_names(report: Any) -> list[str]:
    """失敗的來源／步驟**內部鍵名**（⛔ 不帶 detail 原文：例外訊息可能含 URL／token）。"""
    out = [s.name for s in report.sources if not s.ok]
    out += [t.name for t in report.steps if not t.ok and not t.skipped]
    return out


def _upstream_is_stale(session: Mapping[str, Any] | None, key: str) -> Any:
    where = _CORE_UPSTREAM_STALE_FLAG.get(key)
    if session is None or where is None:
        return UNKNOWN
    outer = session.get(where[0])
    inner = outer.get(where[1]) if isinstance(outer, Mapping) else None
    flag = inner.get("is_stale") if isinstance(inner, Mapping) else None
    return flag if isinstance(flag, bool) else UNKNOWN


def core_input_provenance(summary: Mapping[str, Any],
                          session: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Required Core 各輸入 → `{source, upstream_is_stale}`（全部取自既有輸出；取不到一律 "unknown"）。"""
    from shared.risk_cap_policy import REQUIRED_CORE_INPUTS
    src = summary.get("input_source") if isinstance(summary.get("input_source"), Mapping) else {}
    return {k: {"source": src.get(k) or UNKNOWN, "upstream_is_stale": _upstream_is_stale(session, k)}
            for k in REQUIRED_CORE_INPUTS}


def build_record(report: Any, *, state_dir: str, now_utc: datetime,
                 run_id: str, git_sha: str,
                 session: Mapping[str, Any] | None = None) -> dict[str, str]:
    """一次 `refresh_macro_now` 的結果 → 一列歷史紀錄（全字串、欄位＝`HISTORY_COLUMNS`）。

    Args:
        report: `MacroRefreshReport`（`run_headless_refresh` 的回傳）。
        state_dir: 那一輪寫快照的目錄（`run_headless_refresh` 的同一個；**必須是這一輪新開的空目錄**，
            否則「檔案存在」不代表「這一輪寫的」—— 本函式只認 `risk_cap_result.written`，不靠檔案存在判斷）。
        now_utc: 帶時區的 UTC 時刻（`written_at_utc`；VALID 判定的「現在」）。
        run_id / git_sha: provenance（取不到傳空字串，⛔ 不編造）。
        session: 那一輪的 session（`headless_session()`）；只讀上游 `is_stale` 旗標。None ⇒ 全記 "unknown"。
    """
    from src.services import macro_refresh_service as RS
    from src.services.macro_state_locker import get_macro_state
    from src.services.trading_calendar_service import taipei_today

    if now_utc.tzinfo is None:
        raise ValueError("now_utc 必須帶時區")
    rc = getattr(report, "risk_cap_result", None)
    fetch = _step(report, RS.STEP_FETCH)
    rc_step = _step(report, RS.STEP_RISK_CAP)

    snapshot: dict = {}
    exposure: Any = None
    reason_detail = ""
    summary: Mapping[str, Any] = (rc.bundle_summary or {}) if rc is not None else {}
    missing_core: Sequence[str] = tuple(rc.missing_core) if rc is not None else ()

    if fetch is not None and not fetch.ok:
        status = P.STATUS_FETCH_FAILED
        reason_detail = f"取數鏈整條失敗（例外類型：{fetch.detail.split(':', 1)[0]}）"
    elif rc_step is None:
        raise RuntimeError("報告裡沒有系統風險上限步驟、抓取步驟也沒失敗（契約破損，⛔ 不猜）")
    elif not rc_step.ok:
        status = P.STATUS_COMPUTE_ERROR
        reason_detail = f"系統風險上限步驟拋例外（例外類型：{rc_step.detail.split(':', 1)[0]}）"
    elif rc is None:
        raise RuntimeError("系統風險上限步驟成功但報告沒帶結構化結果（契約破損，⛔ 不猜）")
    elif not rc.written:
        status = _status_from_not_written(rc)
        reason_detail = scrub_secrets(str(rc.reason))
    else:
        rc_path = os.path.join(state_dir, RISK_CAP_STATE_FILE)
        with open(rc_path, encoding="utf-8") as f:
            snapshot = json.load(f)
        state = get_macro_state(None, state_file_path=os.path.join(state_dir, MACRO_STATE_FILE_NAME),
                                now=now_utc, require_valid_risk_cap=True)
        exposure = state.get("exposure_limit_pct")
        if exposure is None:
            status = P.STATUS_SNAPSHOT_REJECTED
            reason_detail = "這一輪寫出了快照，但官方讀端（require_valid_risk_cap=True）不收它的上限"
        else:
            status = P.STATUS_VALID

    record_date = summary.get("today") or taipei_today(now_utc).isoformat()
    if status != P.STATUS_VALID:
        exposure = None    # ⛔ 非有效紀錄一律不寫上限值（不補 0、不沿用前值）
    row = {
        P.COL_RECORD_DATE: _s(record_date),
        P.COL_RULESET_VERSION: _s(snapshot.get("risk_cap_ruleset_version") or RISK_CAP_RULESET_VERSION),
        P.COL_STATUS: status,
        P.COL_REASON_CODE: P.STATUS_REASON_CODE[status],
        P.COL_REASON_DETAIL: reason_detail,
        P.COL_EXPOSURE_LIMIT_PCT: _s(exposure),
        P.COL_REQUIRED_CORE_OK: _s(snapshot.get("required_core_ok")) if snapshot else "",
        P.COL_MISSING_CORE: _s(missing_core),
        P.COL_NOT_EVALUATED: _s(snapshot.get("not_evaluated", summary.get("not_evaluated"))),
        P.COL_DISABLED_INPUTS: _s(snapshot.get("disabled_inputs", summary.get("disabled_inputs"))),
        P.COL_INPUT_ASOF: _s(snapshot.get("input_asof", summary.get("input_asof")) or {}),
        P.COL_ENGINE_SOURCE: _s(snapshot.get("engine_source")),
        P.COL_SNAPSHOT_TIMESTAMP: _s(snapshot.get("timestamp")),
        # 沒有引擎輸入（抓取鏈整條失敗）⇒ 全記 "unknown"：session 裡可能是更早的殘值，⛔ 不拿來充當本輪來源。
        P.COL_CORE_INPUT_PROVENANCE: _s(core_input_provenance(summary, session if rc is not None else None)),
        P.COL_REFRESH_OK: _s(bool(report.ok)),
        P.COL_REFRESH_FAILED: _s(_refresh_failed_names(report)),
        P.COL_WRITTEN_AT_UTC: now_utc.isoformat(timespec="seconds"),
        P.COL_RUN_ID: _s(run_id),
        P.COL_GIT_SHA: _s(git_sha),
        P.COL_SCHEMA_VERSION: P.HISTORY_SCHEMA_VERSION,
    }
    assert tuple(row) == P.HISTORY_COLUMNS, "欄位順序與 L0 schema 不一致"
    return row


# ══════════════════════════════════════════════════════════════════════
# 讀端：能不能說「和上次比」
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class CompareResult:
    """`compare_status` 的結論。`current`／`previous` 是原列（dict，全字串）；不比較時為 None。"""

    status: str
    reason: str = ""
    current: Mapping[str, str] | None = None
    previous: Mapping[str, str] | None = None
    excluded_other_version: int = 0


def _expired(row: Mapping[str, str], now: datetime) -> bool:
    """沿用既有 7 天有效期（`macro_state_is_expired`，看快照自己的 timestamp）；⛔ 不另寫一條。"""
    from src.services.macro_state_locker import macro_state_is_expired
    return macro_state_is_expired({"timestamp": row.get(P.COL_SNAPSHOT_TIMESTAMP, "")}, now=now)


def previous_valid_record(rows: Sequence[Mapping[str, str]], *, before_date: str,
                          ruleset_version: str) -> Mapping[str, str] | None:
    """同規則版本、`record_date` 早於 `before_date` 的最後一筆 VALID（每個日期取最早寫入的那筆）。"""
    best: Mapping[str, str] | None = None
    for r in rows:
        if (r.get(P.COL_RULESET_VERSION) == ruleset_version and r.get(P.COL_STATUS) == P.STATUS_VALID
                and r.get(P.COL_RECORD_DATE, "") < before_date):
            if best is None or r[P.COL_RECORD_DATE] > best[P.COL_RECORD_DATE]:
                best = r
    return best


def compare_status(rows: Sequence[Mapping[str, str]], *, expected_date: str,
                   ruleset_version: str = RISK_CAP_RULESET_VERSION, now: datetime) -> CompareResult:
    """這一刻能不能顯示「和上次比」。⛔ 沒有任何變動大小門檻；只決定「能不能比、跟誰比」。

    判定順序（稽核修正 2026-10-19 後的現行版）：
      1. 同規則版本**一列都沒有** ⇒ `START_RECORDING`（從今天開始記錄）。
      2. 預期日期沒有紀錄 ⇒ `STALE`（排程沒跑／失敗；最新有效紀錄已超過既有 7 天有效期時原因另標）。
         📌 修前「從來沒有 VALID、今天也沒紀錄 ⇒ START_RECORDING」—— 有意識的變更，不是漏刪：
         已經有紀錄（即使全是失敗列）就代表排程開跑過，今天沒紀錄是「排程沒跑／失敗」，
         說成「從今天開始記錄」會把失敗講成正常起點（客戶裁示第 7 點）。
      3. 預期日期有紀錄、但沒有 VALID ⇒ `CURRENT_NOT_VALID`（照實帶最後一列的狀態）。
      4. 預期日期有 VALID ⇒ 用**當天首筆 VALID**（同日較晚的失敗列／衝突列不影響它）；已過期 ⇒ `STALE`。
      5. 沒有更早的同版本 VALID ⇒ `START_RECORDING`（第一筆有效紀錄）。
      6. 與上一筆 VALID 的 `input_asof` **且** `exposure_limit_pct` 都相同 ⇒ `NO_NEW_DATA`（沿用期，不算變化）。
         📌 修前只比 `input_asof` —— 有意識的變更：資料日相同但正式上限值不同（例如上游修正值）是真實的
         官方值變化，客戶要求「任何變化都提醒、不設門檻」⇒ 必須 `COMPARABLE`。
      7. 其餘 ⇒ `COMPARABLE`。

    Args:
        rows: 歷史表的列（`rows_as_records` 的輸出）。
        expected_date: 「應該要有紀錄」的台北日期（'YYYY-MM-DD'）。⚠️ 排程跑之前的時段要不要往前推一天，
            屬正式化時的設計決定（呼叫端決定，本函式不藏一個時刻門檻）。
        ruleset_version: 只比同版本；其他版本的列排除並計數。
        now: 帶時區的「現在」（7 天有效期用）。
    """
    same = [r for r in rows if r.get(P.COL_RULESET_VERSION) == ruleset_version]
    excluded = len(rows) - len(same)
    if not same:
        return CompareResult(P.COMPARE_START_RECORDING, "no_history", excluded_other_version=excluded)
    today = [r for r in same if r.get(P.COL_RECORD_DATE) == expected_date]
    if not today:
        latest = previous_valid_record(same, before_date="9999-12-31", ruleset_version=ruleset_version)
        why = (P.STALE_LATEST_VALID_EXPIRED if latest is not None and _expired(latest, now)
               else P.STALE_TODAY_RUN_MISSING)
        return CompareResult(P.COMPARE_STALE, why, excluded_other_version=excluded)
    today_valid = [r for r in today if r.get(P.COL_STATUS) == P.STATUS_VALID]
    if not today_valid:
        return CompareResult(P.COMPARE_CURRENT_NOT_VALID, today[-1].get(P.COL_STATUS, ""),
                             current=today[-1], excluded_other_version=excluded)
    current = today_valid[0]
    if _expired(current, now):
        return CompareResult(P.COMPARE_STALE, P.STALE_LATEST_VALID_EXPIRED,
                             excluded_other_version=excluded)
    previous = previous_valid_record(same, before_date=expected_date, ruleset_version=ruleset_version)
    if previous is None:
        return CompareResult(P.COMPARE_START_RECORDING, "first_valid_record", current=current,
                             excluded_other_version=excluded)
    if (previous.get(P.COL_INPUT_ASOF) == current.get(P.COL_INPUT_ASOF)
            and previous.get(P.COL_EXPOSURE_LIMIT_PCT) == current.get(P.COL_EXPOSURE_LIMIT_PCT)):
        return CompareResult(P.COMPARE_NO_NEW_DATA, "same_input_asof_and_value", current=current,
                             excluded_other_version=excluded)
    return CompareResult(P.COMPARE_COMPARABLE, "", current=current, previous=previous,
                         excluded_other_version=excluded)
