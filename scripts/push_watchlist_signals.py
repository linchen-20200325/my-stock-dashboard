"""scripts/push_watchlist_signals.py — 觀察池訊號推播 cron CLI（T3 2026-08）。

流程圖層次 3「觀察池追蹤進場訊號」+ 層次 4「停損警報 / 二次分析」的接點。
與既有兩支推播的差別：**這支盯的是「你自己在追蹤的股票」**，
而 `push_daily_signals.py` 推的是全市場選股排名。

    公開 CSV（你的觀察池）
        → fetch_stock_history_1y（L1，逐檔）
        → watchlist_triggers.evaluate_ticker（L2 純函式）
        → watchlist_message.format_*（L2 純函式）
        → send_notification（L1）

§8.2：orchestrator（同 `push_daily_signals.py` / `update_forward_test_freeze.py`），
可跨層 import，但**只碰 L1/L2**，零 `src.ui.*` ——
headless cron 走 L5 會把整個 streamlit UI 鏈拉進來
（`push_daily_signals.py:46-48` 已踩過並修好，本檔沿用同樣紀律）。

§1 fail-loud 四態
─────────────────
  1. CSV URL 未設定           → exit 1（cron 紅燈，不靜默）
  2. 讀到 0 檔                → 推「觀察池是空的」，exit 0（讓你知道清單掉了）
  3. **全部**抓不到 K 線      → 推「掃描失敗」+ exit 1
     ⚠️ 絕不可推「今日無觸發」—— 那會把「全部失敗」說成「全部安全」
  4. 部分檔未評估             → 正常推播，但訊息末尾逐檔列出原因

⚠️ 已知限制（沿用 `push_daily_signals.py:14-15`）：cron 排 Mon-Fri，
   **未濾 TW 國定假日**（本專案無第三方 trading calendar，見 CLAUDE.md §4.5）。
   假日會跑到「資料日未更新」的清單 —— 訊息一律標資料日期供辨識。

環境變數
────────
  WATCHLIST_CSV_URL   你的觀察池 Google Sheet「發布為 CSV」連結（可多行）
  APP_BASE_URL        Streamlit app 網址（深連結用；未設定 → 不附連結）
  NOTIFY_CHANNEL      line / telegram（預設 line，由 dispatch 決定）
  LINE_*  /  TELEGRAM_*  推播憑證（缺 → send 端 raise → exit 1）

用法
────
  python scripts/push_watchlist_signals.py --dry-run       # 只印不送（本地測）
  python scripts/push_watchlist_signals.py                 # 有訊號才送
  python scripts/push_watchlist_signals.py --health-check  # 沒訊號也送狀態（週一用）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TW_TZ = _dt.timezone(_dt.timedelta(hours=8))

#: 預設檢查的均線期數。user 2026-08-14 裁示「跌破 MA20」。
#: 可用 --ma-windows 覆寫（例如 "20,60" 同時看月線與季線）。
_DEFAULT_MA_WINDOWS = "20"


def _tw_now() -> str:
    return _dt.datetime.now(_TW_TZ).strftime("%Y-%m-%d %H:%M")


def _collect_watchlist(csv_url: str) -> list[str]:
    """讀公開 CSV → 台股代號清單。

    **複用** `push_weekly_report` 的 CSV 解析（`_split_urls` / `collect_tickers`）——
    那支已處理 BOM、誤貼 pubhtml 網頁的偵測、多來源聯集去重保序等細節。
    複製一份等於製造第二套會漂移的解析邏輯（§2.1 SSOT）。
    """
    from scripts.push_weekly_report import _split_urls, collect_tickers

    _urls = _split_urls(csv_url)
    if not _urls:
        return []
    return collect_tickers(_urls)


def main(argv=None) -> int:
    from src.compute.notify.watchlist_message import (
        format_empty_watchlist,
        format_quiet_health_check,
        format_scan_failure,
        format_watchlist_alert,
    )
    from src.compute.notify.watchlist_triggers import evaluate_ticker, scan_watchlist
    from src.config import get_stock_name
    from src.data.stock.picker_fetcher import fetch_stock_history_1y
    # 注意：`send_notification` 不在此 import —— 它只在 `_emit()` 內用到，
    # 且 --dry-run 路徑完全不該碰推播模組（本地測試不需要 LINE 憑證）。

    ap = argparse.ArgumentParser(description="觀察池訊號推播（收盤後）")
    ap.add_argument("--dry-run", action="store_true", help="只印訊息不送（本地測）")
    ap.add_argument("--csv-url", default=None, help="覆寫 WATCHLIST_CSV_URL")
    ap.add_argument("--ma-windows", default=_DEFAULT_MA_WINDOWS,
                    help=f"逗號分隔的均線期數（預設 {_DEFAULT_MA_WINDOWS}）")
    ap.add_argument("--health-check", action="store_true",
                    help="沒訊號時也送一則狀態訊息（週一用，確認 cron 還活著）")
    ap.add_argument("--period-label", default="本週",
                    help="健康碼的期間用詞（預設「本週」）")
    args = ap.parse_args(argv)

    _as_of = _tw_now()
    _app_url = os.environ.get("APP_BASE_URL", "").strip()
    try:
        _windows = tuple(int(w.strip()) for w in args.ma_windows.split(",") if w.strip())
    except ValueError:
        print(f"[watchlist] ❌ --ma-windows 格式錯誤：{args.ma_windows!r}", file=sys.stderr)
        return 1
    if not _windows:
        print("[watchlist] ❌ --ma-windows 解析出 0 個期數", file=sys.stderr)
        return 1

    # ── §1 態 1：URL 未設定 → 硬錯（不是「沒訊號」）───────────
    # 來源優先序：--csv-url > WATCHLIST_CSV_URL > WEEKLY_WATCH_CSV_URL
    #
    # 為什麼 fallback 到週報那條：`push_weekly_report` 用的
    # `WEEKLY_WATCH_CSV_URL` 指的就是「使用者發布出來的追蹤清單」——
    # 與本支要的觀察池是**同一個東西**。若使用者已為週報設過，
    # 再要求他發布第二份 CSV 只會製造兩份會漂移的清單（§2.1 SSOT）。
    # 想讓兩者用不同清單時，才另設 WATCHLIST_CSV_URL 覆寫。
    _csv_url = (args.csv_url
                or os.environ.get("WATCHLIST_CSV_URL", "")
                or os.environ.get("WEEKLY_WATCH_CSV_URL", ""))
    if not str(_csv_url).strip():
        print("[watchlist] ❌ 未設定觀察池 CSV 連結"
              "（WATCHLIST_CSV_URL 或 WEEKLY_WATCH_CSV_URL 擇一；"
              "Google Sheet 的「發布為 CSV」連結，可多行，一行一個分頁）",
              file=sys.stderr)
        return 1
    _src = ("--csv-url" if args.csv_url
            else "WATCHLIST_CSV_URL" if os.environ.get("WATCHLIST_CSV_URL", "").strip()
            else "WEEKLY_WATCH_CSV_URL")
    print(f"[watchlist] 清單來源：{_src}")

    try:
        _tickers = _collect_watchlist(_csv_url)
    except Exception as _e:  # noqa: BLE001 — 訊息已被上游清成不含 URL
        print(f"[watchlist] ❌ 觀察池 CSV 抓取失敗：{_e}", file=sys.stderr)
        return 1

    # ── §1 態 2：讀到 0 檔 → 推「清單是空的」（不是「沒訊號」）──
    if not _tickers:
        _msg = format_empty_watchlist(
            as_of=_as_of, source_hint="公開 CSV 解析出 0 個台股代號")
        return _emit(_msg, dry_run=args.dry_run, tag="empty")

    print(f"[watchlist] 監控 {len(_tickers)} 檔　MA{_windows}：{', '.join(_tickers)}")

    # ── 逐檔判定 ─────────────────────────────────────────
    _verdicts = []
    for _code in _tickers:
        _df = None
        try:
            _df, _ = fetch_stock_history_1y(_code)
        except Exception as _e:  # noqa: BLE001 — 單檔失敗記為未評估，不中斷其餘
            print(f"[watchlist] {_code} K 線抓取失敗：{type(_e).__name__}: {_e}",
                  file=sys.stderr)
        _name = ""
        try:
            _n = get_stock_name(_code)
            _name = _n if (_n and _n != _code) else ""
        except Exception:  # noqa: BLE001 — 名稱只影響可讀性
            pass
        _verdicts.append(
            evaluate_ticker(_code, _df, name=_name, ma_windows=_windows))

    _scan = scan_watchlist(_verdicts)
    print(f"[watchlist] 已評估 {_scan.n_evaluated}/{len(_tickers)} 檔　"
          f"觸發 {len(_scan.fired)} 檔　未評估 {len(_scan.skipped)} 檔")

    # ── §1 態 3：全部抓不到 → 失敗訊息 + 紅燈 ─────────────
    #    這一格最危險：若走到「今日無觸發」，使用者會據此決定不看盤，
    #    而實際上系統這次完全沒有監控到任何東西。
    if _scan.all_skipped:
        _detail = "；".join(
            f"{v.ticker} {v.skipped_reason}" for v in _scan.skipped[:5])
        _msg = format_scan_failure(as_of=_as_of, n_total=len(_tickers), detail=_detail)
        _emit(_msg, dry_run=args.dry_run, tag="failure")
        return 1  # cron 紅燈：這是故障不是常態

    # ── 有觸發 → 推警報（§1 態 4：未評估清單已含在訊息內）──
    if _scan.fired:
        _msg = format_watchlist_alert(_scan, as_of=_as_of, app_url=_app_url)
        return _emit(_msg, dry_run=args.dry_run, tag="alert")

    # ── 沒觸發 → 預設完全不送（user 裁示：收到 = 真的要看）──
    if args.health_check:
        _msg = format_quiet_health_check(
            _scan, as_of=_as_of, period_label=args.period_label)
        return _emit(_msg, dry_run=args.dry_run, tag="health")

    print("[watchlist] 無觸發，依設定不推播（--health-check 可強制送狀態）")
    return 0


def _emit(msg: str, *, dry_run: bool, tag: str) -> int:
    """送出或乾跑。送出失敗 → exit 1（cron 紅燈，不靜默）。"""
    if dry_run:
        print(f"\n===== DRY RUN ({tag}) =====\n{msg}\n===== END =====\n")
        return 0
    try:
        from src.data.notify.dispatch import send_notification
        send_notification(msg)
    except Exception as _e:  # noqa: BLE001 — 推播失敗必須紅燈
        print(f"[watchlist] ❌ 推播失敗（{tag}）：{type(_e).__name__}: {_e}",
              file=sys.stderr)
        return 1
    print(f"[watchlist] ✅ 已推播（{tag}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
