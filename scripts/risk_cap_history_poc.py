#!/usr/bin/env python3
"""scripts/risk_cap_history_poc.py — VN1-STORE 最小 PoC：無頭計算每日系統風險上限 → 組一列歷史紀錄（**不寫 production**）。

客戶 2026-10-19 裁示 A：「採用系統專用 Google Sheet……但先不要直接進入正式 production 寫入，下一步先做最小 PoC」；
「本次只核准保存方向 A 與最小 PoC；尚未核准正式 production 排程寫入。」

做什麼
------
1. 跑**畫面同一條**「🚀 更新今日戰情」鏈（`refresh_macro_now`），只把風險上限快照寫到**本輪新開的暫存目錄**
   （⛔ 不覆寫 app 工作目錄的 `risk_cap_state.json`／`macro_state.json`；跑前跑後比對雜湊，有變就 exit 1）。
2. 以 L3 `risk_cap_history_service.build_record` 組一列紀錄（狀態照實；非 VALID 不寫上限值），印成 JSON。
3. `--simulate-rerun`：對**記憶體假表**寫兩次同一列，示範同日重跑不重複，並印出讀端比較結論。

4. `--check-write-gate`（workflow `production-write` 寫入 job 的**第一個 Python 步驟**，在任何 auth 之前）：
   只看 L0 `PRODUCTION_WRITE_APPROVED`；False ⇒ 印 `::error::` 並 exit 2（紅燈），⛔ 不 import 任何 src 模組
   （系統 python3、未裝套件也能跑）。
5. `--write --record <JSON>`（VN1-STORE Production Wiring 批 2026-10-20）：**閘門第一**
   （`load_writer_credentials_or_refuse`；`PRODUCTION_WRITE_APPROVED=False` ⇒ 一律 exit 2）→
   `build_writer_client`（只吃 WIF `external_account` 憑證檔）→ 以 `RISK_CAP_HISTORY_SHEET_ID` 開
   `risk_cap_daily` → `upsert_record` 寫 compute job 產出的那一列。⛔ 不在寫入 job 裡重算、⛔ 不跑取數。
   📌 2026-10-20（Pre-Hardening 批；有意識的擴充，不是漏改）：閘門之後改為
   **寫前檢查**（L1 `precheck_target`，writer 身分的唯讀 token）→ `upsert_record` → **寫後讀回驗證**
   （L1 `verify_written`，同樣唯讀 token）；任何一步失敗 ⇒ exit 非 0，⛔ 永不刪除任何列（自動回滾未經客戶核准）。
   只印固定文字、例外類別名、計數與 sha256（`precheck:`／`verify:` 各一行證據 JSON）。
6. `--precheck --record <JSON>`／`--verify-written --record <JSON>`：只做寫前檢查／只做寫後驗證（唯讀、⛔ 不寫）；
   同樣**閘門第一** ⇒ 未核准期間一律 exit 2。
7. dry-run 輸出多一個 `record_sha256`（一列紀錄的指紋，L1 `record_sha256`）。

⛔ 不做
------
- 不寫任何真實 Sheet：`PRODUCTION_WRITE_APPROVED=False` 期間 `--write` 一律失敗（exit 2）。
- 不讀任何新 secret；只用既有取數環境變數（FINMIND_TOKEN、PROXY_URL…，與既有總經 cron 相同）。
- ⛔ 沒有 `if headless:` 分支、沒有自算公式（維護守則同 `scripts/update_macro_forward_test.py`）。

結束碼：0 ＝ PoC 跑完（**不論紀錄狀態是不是 VALID** —— 照實的非有效狀態也是合格結果）；
1 ＝ 契約破損／app 狀態檔被動到；2 ＝ `--write`／`--check-write-gate` 被閘門或憑證拒絕（含紀錄檔不合格）；
3 ＝ 寫入結果為同日有效紀錄衝突（`CONFLICT_KEPT_EXISTING`；稽核修正 2026-10-19：衝突必須讓排程顯示失敗，
    ⛔ 不能只留在會過期的 Actions log —— 衝突列另記在表裡）。
4 ＝ 寫前檢查不過（什麼都沒寫）；5 ＝ 寫後讀回驗證不過（⛔ 不刪任何列，需人工查看）。

用法::

    python scripts/risk_cap_history_poc.py                      # 預設 dry-run
    python scripts/risk_cap_history_poc.py --simulate-rerun --out record.json
    python scripts/risk_cap_history_poc.py --check-write-gate   # 寫入 job 第一步（未核准 ⇒ exit 2）
    python scripts/risk_cap_history_poc.py --write --record record.json   # 未核准 ⇒ exit 2
    python scripts/risk_cap_history_poc.py --precheck --record record.json        # 未核准 ⇒ exit 2
    python scripts/risk_cap_history_poc.py --verify-written --record record.json  # 未核准 ⇒ exit 2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

#: app 工作目錄裡不得被本 PoC 動到的狀態檔（相對 cwd；與 app 預設相對路徑同一條規則）。
APP_STATE_FILES: tuple[str, ...] = ("risk_cap_state.json", "macro_state.json")


def _fingerprint(base: Path) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for name in APP_STATE_FILES:
        p = base / name
        out[name] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    return out


def _git_sha() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                           text=True, timeout=10, cwd=str(_REPO))
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception as e:  # noqa: BLE001
        print(f"[risk_cap_history_poc] git sha 取不到（{type(e).__name__}），留空")
        return ""


def _now_utc() -> datetime:
    """抽成函式只為讓測試能注入時鐘。"""
    return datetime.now(timezone.utc)


def _check_write_gate() -> int:
    """寫入 job 的第一道 Python 檢查：只讀 L0 核准旗標（stdlib-only 模組），⛔ 不 import src、⛔ 不碰任何憑證。"""
    from shared.risk_cap_history_policy import PRODUCTION_WRITE_APPROVED
    if PRODUCTION_WRITE_APPROVED is not True:
        print("::error::production write is not approved (PRODUCTION_WRITE_APPROVED=False); "
              "nothing was authenticated or written")
        print("[risk_cap_history_poc] ❌ production 寫入尚未核准（DEC-063／DEC-009）→ 寫入 job 停在這裡（紅燈）")
        return 2
    print("[risk_cap_history_poc] production 寫入核准旗標為 True")
    return 0


def _today_tw() -> str:
    """寫入當下的台北日期（寫前檢查用；時鐘同 `_now_utc`，測試可注入）。"""
    from shared.risk_cap_history_policy import RECORD_DATE_TZ
    return _now_utc().astimezone(RECORD_DATE_TZ).date().isoformat()


def _load_record(record_path: str, flag: str) -> dict | None:
    """compute job 產出的紀錄 JSON → record dict；不合格 ⇒ None（已印原因）。⛔ 不補欄位、⛔ 不印值。"""
    from shared.risk_cap_history_policy import HISTORY_COLUMNS
    if not record_path:
        print(f"[risk_cap_history_poc] ❌ {flag} 需要 --record（compute job 的紀錄 JSON）→ 拒絕")
        return None
    try:
        data = json.loads(Path(record_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"[risk_cap_history_poc] ❌ 紀錄檔讀不到或不是 JSON（{type(e).__name__}）→ 拒絕")
        return None
    record = data.get("record") if isinstance(data, dict) else None
    if not isinstance(record, dict) or tuple(record) != HISTORY_COLUMNS \
            or not all(isinstance(v, str) for v in record.values()):
        print("[risk_cap_history_poc] ❌ 紀錄檔沒有欄位與 schema 一致的 record → 拒絕（⛔ 不補欄位）")
        return None
    return record


def _open_target(scopes):
    """閘門已過之後：WIF writer 身分（`scopes` 只准讀寫或唯讀）→ 以 `RISK_CAP_HISTORY_SHEET_ID` 開 `risk_cap_daily`。

    ⛔ Sheet ID 只取自環境變數（GitHub secret）、⛔ 永不印出；⛔ 不印任何憑證內容。
    """
    from shared.risk_cap_history_policy import HISTORY_SHEET_ID_ENV_VAR
    from src.data.risk_cap.history import build_writer_client, open_history_worksheet
    return open_history_worksheet(build_writer_client(scopes=scopes), os.environ[HISTORY_SHEET_ID_ENV_VAR])


def _emit(kind: str, payload: dict) -> None:
    """一行固定格式的證據 JSON（只含固定字彙、計數、sha256、日期／狀態；⛔ 不含任何儲存格值或 Sheet ID）。"""
    print(f"[risk_cap_history_poc] {kind}: " + json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _readonly_values():
    """以 writer 身分的**唯讀** token 讀全表原樣。"""
    from shared.risk_cap_history_policy import READER_SCOPES
    from src.data.risk_cap.history import read_history_values
    return read_history_values(_open_target(READER_SCOPES))


def _run_precheck(record: dict, run_id: str) -> bool:
    """寫前檢查（唯讀 token）：L1 `precheck_target` ＋ 本輪 run id 必須等於紀錄裡的 run id。印證據行。"""
    from shared.risk_cap_history_policy import COL_RUN_ID, PRECHECK_FAIL_RUN_ID_MISMATCH
    from src.data.risk_cap.history import precheck_target, record_sha256
    res = precheck_target(_readonly_values(), record, today_tw=_today_tw())
    failures = list(res.failures)
    if not run_id or record.get(COL_RUN_ID) != run_id:
        failures.append(PRECHECK_FAIL_RUN_ID_MISMATCH)
    _emit("precheck", {"ok": not failures, "failures": failures, "header_state": res.header_state,
                       "data_rows": res.data_rows, "record_sha256": record_sha256(record)})
    return not failures


def _run_verify(record: dict, run_id: str) -> bool:
    """寫後讀回驗證（唯讀 token）：L1 `verify_written`。印證據行。⛔ 失敗也不刪任何列。"""
    from src.data.risk_cap.history import record_sha256, verify_written
    res = verify_written(_readonly_values(), record, run_id)
    _emit("verify", {"ok": res.ok, "failures": list(res.failures), "matches": res.matches,
                     "mismatched_columns": list(res.mismatched_columns),
                     "record_sha256": record_sha256(record), "readback_sha256": res.readback_sha256})
    return res.ok


def _guarded(step: str, fn, *args) -> bool | None:
    """Google I/O 步驟：例外只印類別名（例外原文可能帶 Sheet ID／回應內文），回 None ＝ 這一步沒有結論。"""
    try:
        return fn(*args)
    except Exception as e:  # noqa: BLE001 —— 照樣失敗（呼叫端 exit 非 0）；⛔ 不印原文
        print(f"[risk_cap_history_poc] ❌ {step} 失敗（{type(e).__name__}）")
        return None


def _write_record(record_path: str) -> int:
    """閘門已過之後的真實寫入路徑：寫前檢查 → `upsert_record` → 寫後讀回驗證。任何一步失敗 ⇒ exit 非 0。

    結束碼：1 ＝ I/O 失敗／寫入結果與寫前檢查不一致（未確認是否寫入 ⇒ 仍跑一次讀回驗證留證據）；2 ＝ 紀錄檔不合格；
    3 ＝ 同日有效紀錄衝突；4 ＝ 寫前檢查不過（**什麼都沒寫**）；5 ＝ 寫後驗證不過（⛔ 不刪任何列，需人工查看）。
    """
    from shared.risk_cap_history_policy import UPSERT_APPENDED, UPSERT_CONFLICT_KEPT_EXISTING, WRITER_SCOPES
    from src.data.risk_cap.history import upsert_record

    record = _load_record(record_path, "--write")
    if record is None:
        return 2
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    pre = _guarded("寫前檢查", _run_precheck, record, run_id)
    if pre is None:
        return 1
    if not pre:
        print("[risk_cap_history_poc] ❌ 寫前檢查不過 → exit 4（什麼都沒寫）")
        return 4
    outcome = _guarded("寫入系統歷史 Sheet", lambda: upsert_record(_open_target(WRITER_SCOPES), record))
    if outcome is None or outcome != UPSERT_APPENDED:
        print(f"[risk_cap_history_poc] ❌ 寫入結果不是 {UPSERT_APPENDED}（{outcome}）→ 讀回一次留證據；⛔ 不刪任何列，需人工查看")
        _guarded("寫後讀回驗證", _run_verify, record, run_id)
        return 3 if outcome == UPSERT_CONFLICT_KEPT_EXISTING else 1
    print(f"[risk_cap_history_poc] 寫入結果：{outcome}")
    ok = _guarded("寫後讀回驗證", _run_verify, record, run_id)
    if ok is None:
        return 1
    if not ok:
        print("[risk_cap_history_poc] ❌ 寫後驗證不過 → exit 5（⛔ 不刪任何列；自動回滾未經客戶核准，需人工查看）")
        return 5
    print("[risk_cap_history_poc] 寫入並讀回驗證通過")
    return 0


def _precheck_only(record_path: str) -> int:
    """`--precheck`（閘門已過之後）：只做寫前檢查，⛔ 不寫。0 ＝ 可以寫；4 ＝ 不過；1 ＝ I/O 失敗；2 ＝ 紀錄檔不合格。"""
    record = _load_record(record_path, "--precheck")
    if record is None:
        return 2
    pre = _guarded("寫前檢查", _run_precheck, record, os.environ.get("GITHUB_RUN_ID", ""))
    return 1 if pre is None else (0 if pre else 4)


def _verify_only(record_path: str) -> int:
    """`--verify-written`（閘門已過之後）：只做寫後讀回驗證，⛔ 不寫、⛔ 不刪。0 ＝ 通過；5 ＝ 不過；1 ＝ I/O 失敗。"""
    record = _load_record(record_path, "--verify-written")
    if record is None:
        return 2
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not run_id:
        print("[risk_cap_history_poc] ❌ --verify-written 需要 GITHUB_RUN_ID（以 run id 找寫入的那一列）→ 拒絕")
        return 2
    ok = _guarded("寫後讀回驗證", _run_verify, record, run_id)
    return 1 if ok is None else (0 if ok else 5)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="VN1-STORE 最小 PoC（不寫 production）")
    ap.add_argument("--dry-run", action="store_true", default=True, help="預設即 dry-run（只印不寫）")
    ap.add_argument("--write", action="store_true",
                    help="寫真實 Sheet（需 --record）—— PRODUCTION_WRITE_APPROVED=False 期間一律拒絕")
    ap.add_argument("--record", default="",
                    help="--write／--precheck／--verify-written 用的紀錄 JSON（compute job 的 --out 產物）")
    ap.add_argument("--precheck", action="store_true",
                    help="只做寫前檢查（唯讀，需 --record）—— PRODUCTION_WRITE_APPROVED=False 期間一律拒絕")
    ap.add_argument("--verify-written", action="store_true",
                    help="只做寫後讀回驗證（唯讀，需 --record）—— PRODUCTION_WRITE_APPROVED=False 期間一律拒絕")
    ap.add_argument("--check-write-gate", action="store_true",
                    help="只檢查 production 寫入核准旗標（False ⇒ exit 2）；不 import 任何 src 模組")
    ap.add_argument("--simulate-rerun", action="store_true", help="對記憶體假表示範同日重跑冪等")
    ap.add_argument("--out", default="", help="另把紀錄 JSON 寫到這個路徑（artifact 用）")
    ap.add_argument("--state-dir", default="", help="快照暫存目錄（留空＝自動開新暫存目錄；必須是空目錄）")
    args = ap.parse_args(argv)

    if args.check_write_gate:
        return _check_write_gate()

    from src.data.risk_cap.history import (
        InMemoryWorksheet, ProductionWriteNotApproved, load_writer_credentials_or_refuse,
        record_sha256, rows_as_records, upsert_record,
    )
    from shared.risk_cap_history_policy import UPSERT_CONFLICT_KEPT_EXISTING

    sheet_flows = [(args.write, "--write", _write_record), (args.precheck, "--precheck", _precheck_only),
                   (args.verify_written, "--verify-written", _verify_only)]
    chosen = [(flag, fn) for on, flag, fn in sheet_flows if on]
    if chosen:
        try:
            load_writer_credentials_or_refuse()       # 閘門第一（核准旗標是它的第一個檢查）
        except ProductionWriteNotApproved as e:
            print(f"[risk_cap_history_poc] ❌ {'／'.join(f for f, _ in chosen)} 拒絕：{e}")
            return 2
        if len(chosen) > 1:
            print("[risk_cap_history_poc] ❌ --write／--precheck／--verify-written 一次只能選一個 → 拒絕")
            return 2
        return chosen[0][1](args.record)

    import src.services.risk_cap_history_service as H

    cwd = Path.cwd()
    before = _fingerprint(cwd)
    state_dir = args.state_dir or tempfile.mkdtemp(prefix="risk_cap_history_poc_")
    if os.path.isdir(state_dir) and os.listdir(state_dir):
        print(f"[risk_cap_history_poc] ❌ 快照目錄不是空的：{state_dir}（無法分辨「這一輪寫的」）")
        return 1
    if Path(state_dir).resolve() == cwd.resolve():
        print("[risk_cap_history_poc] ❌ 快照目錄不得是 app 工作目錄")
        return 1

    report = H.run_headless_refresh(state_dir)
    now = _now_utc()
    record = H.build_record(report, state_dir=state_dir, now_utc=now,
                            run_id=os.environ.get("GITHUB_RUN_ID", "local"), git_sha=_git_sha(),
                            session=H.headless_session())

    out: dict = {
        "record": record,
        "state_dir": state_dir,
        "refresh": {
            "ok": report.ok,
            "sources": [{"name": s.name, "ok": s.ok} for s in report.sources],
            "steps": [{"name": t.name, "ok": t.ok, "skipped": t.skipped, "partial": t.partial}
                      for t in report.steps],
        },
    }
    outcomes: list[str] = []
    if args.simulate_rerun:
        ws = InMemoryWorksheet()
        first = upsert_record(ws, record)
        second = upsert_record(ws, record)
        outcomes += [first, second]
        rows = rows_as_records(ws.get_all_values())
        cmp = H.compare_status(rows, expected_date=record["record_date"], now=now)
        out["simulate_rerun"] = {
            "first_upsert": first, "second_upsert": second,
            "data_rows_after": len(rows),
            "compare_status": cmp.status, "compare_reason": cmp.reason,
        }

    after = _fingerprint(cwd)
    out["app_state_files_untouched"] = before == after
    out["record_sha256"] = record_sha256(record)
    text = json.dumps(out, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    if before != after:
        print(f"[risk_cap_history_poc] ❌ app 工作目錄的狀態檔被動到：{before} → {after}")
        return 1
    if UPSERT_CONFLICT_KEPT_EXISTING in outcomes:
        print("[risk_cap_history_poc] ❌ 同日有效紀錄衝突（首筆不動、衝突列已另記）→ exit 3，需人工查看")
        return 3
    print(f"[risk_cap_history_poc] 完成：status={record['status']}（dry-run，未寫任何真實 Sheet）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
