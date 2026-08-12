"""scripts/push_weekly_report.py — 每週組合週報 → LINE 推播(cron entrypoint)。

流程(對齊 scripts/push_daily_signals.py 範式):
  發布的 Google Sheet CSV(WEEKLY_WATCH_CSV_URL) → 解析追蹤代號
    → weekly_review_service.build_weekly_review(總經定調 + 逐檔體檢 + AI 建議)
    → format_weekly_message → send_notification(LINE)

為何用「發布 CSV」而非 gsheet SA:cron 無使用者 session、OAuth 拿不到私有 Sheet;
使用者把追蹤清單分頁「發布到網路」→ 公開 CSV 連結,plain HTTP 即可讀,零認證、零 GCP 設定。

§1 Fail Loud:
- 無 CSV URL / 抓不到 / 解析 0 代號 → 印錯 + 非零 exit,不送空/假訊息。
- 取價/AI 失敗由 service 端誠實降級(AI 缺席仍送真實數據摘要)。
- LINE 憑證缺 → send_notification raise → workflow 紅燈(不靜默)。

CLI:
    python scripts/push_weekly_report.py            # 正式推播
    python scripts/push_weekly_report.py --dry-run  # 只印訊息不送(本地驗證)
    python scripts/push_weekly_report.py --csv-url URL  # 覆寫來源(測試用)
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import io
import os
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

#: 台股代號 token:個股 4 碼(首位 1-9,可帶字母)或 ETF/受益證券 00 開頭。排除數量(如 30000)。
_TICKER_RE = re.compile(r"^(?:00\d{2,4}[A-Za-z]?|[1-9]\d{3}[A-Za-z]?)$")
#: 「代號」欄位表頭關鍵字(以**包含**判定,故 `股票代號`/`證券代碼`/`stock code` 等變體皆命中,
#: 優先鎖定該欄 → 避免退回 scan-all 把 4 位數量誤當代號)。
_TICKER_HEADERS = ("ticker", "代號", "代碼", "股號", "symbol", "code")
_TW_NOW_TZ = _dt.timezone(_dt.timedelta(hours=8))


def _strip_suffix(tok: str) -> str:
    _t = str(tok).replace("\ufeff", "").strip().upper()   # 去 BOM(utf-8-sig 首格)
    for _s in (".TWO", ".TW"):
        if _t.endswith(_s):
            return _t[: -len(_s)]
    return _t


def extract_tickers_from_csv(text: str) -> list[str]:
    """從 CSV 文字抽出台股代號(去重保序)。

    優先:有表頭且含「代號/ticker」欄 → 只讀該欄。否則:掃全表每個 cell 內的 token,
    取符合台股代號樣式者(排除數量/日期等雜訊)。裸碼與 .TW/.TWO 視為同碼。
    """
    _rows = list(csv.reader(io.StringIO(text)))
    if not _rows:
        return []
    _seen: set[str] = set()
    out: list[str] = []

    def _add(tok: str) -> None:
        _c = _strip_suffix(tok)
        if _TICKER_RE.match(_c) and _c not in _seen:
            _seen.add(_c)
            out.append(_c)

    _header = [str(h).replace("\ufeff", "").strip().lower() for h in _rows[0]]
    # 以「包含」判定:`股票代號`/`證券代碼`/`stock code` 等變體皆命中,鎖定該欄 → 避免退回
    # scan-all 把 4 位數量(如持股數 1101/3000)誤當代號(稽核 item 3b)。
    _col = next((i for i, h in enumerate(_header)
                 if any(_k in h for _k in _TICKER_HEADERS)), None)
    if _col is not None:
        for _r in _rows[1:]:
            if _col < len(_r):
                _add(_r[_col])
        if out:
            return out
    # 無表頭代號欄 → 掃全表 token(cell 可能是 "2330 台積電" → 拆 token;含全形逗號)
    for _r in _rows:
        for _cell in _r:
            for _tok in re.split(r"[\s,、，]+", str(_cell)):
                _add(_tok)
    return out


def _fetch_csv(url: str, timeout: int = 30) -> str:
    import requests
    _r = requests.get(url, timeout=timeout)
    if _r.status_code != 200:
        raise RuntimeError(f"CSV 抓取 HTTP {_r.status_code}")
    _r.encoding = _r.apparent_encoding or "utf-8"
    return _r.text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只印訊息不送")
    ap.add_argument("--csv-url", default=None, help="覆寫 WEEKLY_WATCH_CSV_URL")
    args = ap.parse_args(argv)

    _url = args.csv_url or os.environ.get("WEEKLY_WATCH_CSV_URL", "").strip()
    if not _url:
        print("[weekly_report] ❌ 未設定 WEEKLY_WATCH_CSV_URL(發布的追蹤清單 CSV 連結)")
        return 1

    try:
        _csv_text = _fetch_csv(_url)
    except Exception as _e:
        # 只印例外類型,不印 {_e}(requests 例外訊息常內嵌完整 URL → 避免 log 洩漏清單連結)
        print(f"[weekly_report] ❌ 追蹤清單 CSV 抓取失敗:{type(_e).__name__}")
        return 1

    _tickers = extract_tickers_from_csv(_csv_text)
    if not _tickers:
        print("[weekly_report] ❌ CSV 解析出 0 個台股代號 → 不送(§1 不送空訊息)")
        return 1
    print(f"[weekly_report] 追蹤 {len(_tickers)} 檔:{', '.join(_tickers)}")

    _as_of = _dt.datetime.now(_TW_NOW_TZ).strftime("%Y-%m-%d")
    from src.services.weekly_review_service import (
        build_weekly_review, format_weekly_message,
    )
    _api_key = os.environ.get("GEMINI_API_KEY") or None
    _review = build_weekly_review(_tickers, api_key=_api_key, as_of=_as_of)
    _msg = format_weekly_message(_review, as_of=_as_of)

    if args.dry_run:
        print("─" * 40 + "\n" + _msg + "\n" + "─" * 40)
        print(f"[weekly_report] (dry-run)AI:{'有' if _review.get('ai_text') else '無'}")
        return 0

    from src.data.notify.dispatch import send_notification
    _n = send_notification(_msg)
    print(f"[weekly_report] ✅ 已送出 {_n} 則")
    return 0


if __name__ == "__main__":
    sys.exit(main())
