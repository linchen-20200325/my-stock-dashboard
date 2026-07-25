"""scripts/push_daily_signals.py — 收盤後「每日選股訊號推播」cron CLI(v20-PUSH)。

kevin801221/stock-strategies-only 啟發(每日收盤後把選股清單推到手機)。本專案版:
選股走與**網頁 / 凍結 / MCP 同源** 的 `get_ranked_picks`(§8 SSOT)→ 逐檔抓價算純
價格衍生技術面(`build_technical_snapshot`)→ 組字 → 推播(LINE / Telegram,由
`NOTIFY_CHANNEL` 環境變數選,預設 line;LINE Notify 已停用改走 Messaging API)。

§8.2:orchestrator(同 app.py / update_forward_test_freeze),可跨層 import。
§1 fail-loud:
  - 季快照未就緒 / 存活池空 → 推「今日無訊號 + 原因」(非錯誤,exit 0,不偽造清單);
  - 某股抓不到價 → 技術面標「資料不足」(不腦補),不影響其他股;
  - 推播 secret 缺 → send 端 raise → exit 1(cron 紅燈,不靜默)。

⚠️ 已知限制:cron 排 Mon-Fri,未濾 TW 國定假日(本專案無第三方 trading calendar,
   見 CLAUDE.md §4.5);假日會推一份「資料日期未更新」的清單(訊息帶 as_of 可辨識)。

用法:
  python scripts/push_daily_signals.py                    # 全 5 因子、前 10 名
  python scripts/push_daily_signals.py --top-n 15 --factors eps_high,trend
  python scripts/push_daily_signals.py --dry-run          # 只印訊息不送(本地測)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TW_TZ = _dt.timezone(_dt.timedelta(hours=8))


def _tw_now() -> str:
    return _dt.datetime.now(_TW_TZ).strftime("%Y-%m-%d %H:%M")


def _build_pe_name_maps() -> tuple[dict, dict]:
    """自 TWSE BWIBBU 抓 PE / 名稱 → (pe_map, name_map)。抓不到 → 空 dict。

    鏡像 scripts/update_forward_test_freeze.py + mcp_server —— 三處 orchestrator 走同一支
    L5 `fetch_twse_yield_pe`,確保推播選股 = 畫面 / 凍結 / MCP 選股(§8 SSOT)。
    """
    try:
        from src.ui.tabs.yield_screener import fetch_twse_yield_pe
        _df = fetch_twse_yield_pe()
    except Exception as _e:  # noqa: BLE001 — PE 抓不到 → pe_low 缺料,不炸
        print(f"[push_signals] TWSE PE 抓取失敗:{type(_e).__name__}: {_e}", file=sys.stderr)
        return {}, {}
    if _df is None or _df.empty or "代碼" not in _df.columns:
        return {}, {}
    _codes = _df["代碼"].astype(str)
    _pe = dict(zip(_codes, _df["本益比"])) if "本益比" in _df.columns else {}
    _nm = dict(zip(_codes, _df["名稱"].astype(str))) if "名稱" in _df.columns else {}
    return _pe, _nm


def main(argv=None) -> int:
    from src.compute.notify.signal_message import (
        format_empty_message,
        format_signal_message,
    )
    from src.compute.notify.technical_snapshot import build_technical_snapshot
    from src.data.notify.dispatch import send_notification
    from src.data.stock.picker_fetcher import fetch_stock_history_1y
    from src.services.fundamental_screener_service import (
        SCREEN_ANGLE_LABELS,
        get_cross_quarter_trends,
        get_ranked_picks,
    )

    _all = list(SCREEN_ANGLE_LABELS.values())
    ap = argparse.ArgumentParser(description="每日選股訊號推播(收盤後)")
    ap.add_argument("--top-n", type=int, default=10, help="推播綜合分前 N 名(預設 10)")
    ap.add_argument("--factors", default="", help="逗號分隔因子(留空=全 5 因子)")
    ap.add_argument("--dry-run", action="store_true", help="只印訊息不送(本地測)")
    args = ap.parse_args(argv)

    _factors = ([f.strip() for f in args.factors.split(",") if f.strip()]
                if args.factors.strip() else _all)
    _as_of = _tw_now()
    print(f"[push_signals] as_of={_as_of} top_n={args.top_n} factors={_factors}")

    _pe, _nm = _build_pe_name_maps()
    # 缺貨掃描 + 跨季財報趨勢:明確抓一次(供訊息徽章;缺貨並傳入選股避免重掃)
    _shortage_rows = None
    if "shortage" in _factors:
        try:
            from src.services.shortage_screener_service import run_shortage_scan
            _shortage_rows = run_shortage_scan()[0]
        except Exception as _es:  # noqa: BLE001 — 缺貨掃描失敗 → 無徽章,不炸
            print(f"[push_signals] 缺貨掃描失敗:{type(_es).__name__}: {_es}", file=sys.stderr)
    try:
        _trend_df = get_cross_quarter_trends()
    except Exception as _et:  # noqa: BLE001 — 跨季快照缺 → 無財報趨勢徽章,不炸
        print(f"[push_signals] 跨季趨勢不可用:{type(_et).__name__}: {_et}", file=sys.stderr)
        _trend_df = None
    try:
        _cands, _note = get_ranked_picks(_factors, top_n=max(int(args.top_n), 300),
                                         pe_map=_pe, name_map=_nm,
                                         shortage_rows=_shortage_rows, auto_fetch=True)
    except Exception as _e:  # noqa: BLE001 — 選股整體失敗 → 硬錯
        print(f"[push_signals] ❌ 選股失敗:{type(_e).__name__}: {_e}", file=sys.stderr)
        return 1

    if _cands is None or _cands.empty or "代碼" not in _cands.columns:
        _msg = format_empty_message(as_of=_as_of, reason=(_note or "綜合排名為空"))
    else:
        _picks = _cands.head(int(args.top_n)).to_dict("records")
        _tech: dict = {}
        for _p in _picks:
            _code = str(_p.get("代碼", "")).strip()
            if not _code:
                continue
            try:
                _df, _ = fetch_stock_history_1y(_code)
                _tech[_code] = build_technical_snapshot(_df)
            except Exception as _e:  # noqa: BLE001 — 單檔失敗 → 技術資料不足,不影響其他
                print(f"[push_signals] {_code} 抓價/技術失敗:{type(_e).__name__}: {_e}",
                      file=sys.stderr)
                _tech[_code] = {"ok": False, "note": "抓價失敗"}
        # 財報趨勢 / 缺貨 tier 查表(§1:缺料的股不在表 → 徽章自動略)
        _trend_by: dict = {}
        if _trend_df is not None and not _trend_df.empty:
            for _r in _trend_df.to_dict("records"):
                _trend_by[str(_r.get("stock_id"))] = _r
        _short_by = {str(_r.get("代碼")): _r.get("_tier") for _r in (_shortage_rows or [])}
        _msg = format_signal_message(_picks, _tech, as_of=_as_of,
                                     trend_by_code=_trend_by, shortage_by_code=_short_by)

    if args.dry_run:
        print("----- DRY RUN(未送)-----")
        print(_msg)
        return 0

    _n = send_notification(_msg)   # NOTIFY_CHANNEL(預設 line);secret 缺 → raise → exit 1
    print(f"[push_signals] ✅ 已送出 {_n} 則訊息。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
