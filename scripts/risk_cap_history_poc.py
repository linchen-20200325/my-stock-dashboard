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

⛔ 不做
------
- 不寫任何真實 Sheet：`--write` 一律失敗（production 寫入未核准、憑證未設定）。
- 不讀任何新 secret；只用既有取數環境變數（FINMIND_TOKEN、PROXY_URL…，與既有總經 cron 相同）。
- ⛔ 沒有 `if headless:` 分支、沒有自算公式（維護守則同 `scripts/update_macro_forward_test.py`）。

結束碼：0 ＝ PoC 跑完（**不論紀錄狀態是不是 VALID** —— 照實的非有效狀態也是合格結果）；
1 ＝ 契約破損／app 狀態檔被動到；2 ＝ `--write`（拒絕）。

用法::

    python scripts/risk_cap_history_poc.py                      # 預設 dry-run
    python scripts/risk_cap_history_poc.py --simulate-rerun --out record.json
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="VN1-STORE 最小 PoC（不寫 production）")
    ap.add_argument("--dry-run", action="store_true", default=True, help="預設即 dry-run（只印不寫）")
    ap.add_argument("--write", action="store_true", help="寫真實 Sheet —— 本 PoC 一律拒絕")
    ap.add_argument("--simulate-rerun", action="store_true", help="對記憶體假表示範同日重跑冪等")
    ap.add_argument("--out", default="", help="另把紀錄 JSON 寫到這個路徑（artifact 用）")
    ap.add_argument("--state-dir", default="", help="快照暫存目錄（留空＝自動開新暫存目錄；必須是空目錄）")
    args = ap.parse_args(argv)

    from src.data.macro.risk_cap_history import (
        InMemoryWorksheet, ProductionWriteNotApproved, load_writer_credentials_or_refuse,
        rows_as_records, upsert_record,
    )

    if args.write:
        try:
            load_writer_credentials_or_refuse()
        except ProductionWriteNotApproved as e:
            print(f"[risk_cap_history_poc] ❌ --write 拒絕：{e}")
            return 2
        print("[risk_cap_history_poc] ❌ --write 意外通過憑證閘門（不應發生）→ 拒絕")
        return 2

    from src.services import risk_cap_history_service as H

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
                            run_id=os.environ.get("GITHUB_RUN_ID", "local"), git_sha=_git_sha())

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
    if args.simulate_rerun:
        ws = InMemoryWorksheet()
        first = upsert_record(ws, record)
        second = upsert_record(ws, record)
        rows = rows_as_records(ws.get_all_values())
        cmp = H.compare_status(rows, expected_date=record["record_date"], now=now)
        out["simulate_rerun"] = {
            "first_upsert": first, "second_upsert": second,
            "data_rows_after": len(rows),
            "compare_status": cmp.status, "compare_reason": cmp.reason,
        }

    after = _fingerprint(cwd)
    out["app_state_files_untouched"] = before == after
    text = json.dumps(out, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    if before != after:
        print(f"[risk_cap_history_poc] ❌ app 工作目錄的狀態檔被動到：{before} → {after}")
        return 1
    print(f"[risk_cap_history_poc] 完成：status={record['status']}（dry-run，未寫任何真實 Sheet）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
