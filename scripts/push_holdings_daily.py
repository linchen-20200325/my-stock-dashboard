"""scripts/push_holdings_daily.py — 收盤後「每日持股續抱 / 換股」推播 cron CLI（#35）。

經 Service Account 讀你私有 Google Sheet 的持股（`portfolios`）+ 個股觀察清單
（`stock_watchlist`）→ 沿用「💼 持股戰情室」既有引擎（`get_station_rows` /
`get_switch_in_candidates` / `build_switch_advice`）逐檔算 續抱 / 換出,並挑換入候選 →
L2 純函式組訊息（`format_holdings_message`）→（選配）Gemini AI 潤稿 → 推 LINE / Telegram
（`NOTIFY_CHANNEL`,預設 line）。

與 `push_daily_signals.py` 的分工:那支推「選股網清單」(公開資料);本支推「你的持股」
(私有 Sheet,需 SA)。兩支各自獨立 cron,互不影響。

§8.2:orchestrator（同 push_daily_signals / update_forward_test_freeze）,可跨層 import。
§1 Fail-Loud:
  - GCP SA 憑證 / sheet id 缺 → raise → exit 1（cron 紅燈,不靜默）;
  - 持股 + 觀察清單全空 → 推「讀不到清單 + 檢查項」提醒（exit 0,**不偽造**持股）;
  - 單檔抓不到 → 戰情引擎該列標「資料不足」（不腦補）,不影響其他檔;
  - AI 潤稿失敗 → 只送規則式訊息（AI 是附加,非主體）;
  - 推播 secret 缺 → send 端 raise → exit 1。

⚠️ 已知限制:cron 排 Mon-Fri,未濾 TW 國定假日（本專案無第三方 trading calendar,
   見 CLAUDE.md §4.5）;假日會推一份「資料日期未更新」的訊息（帶 as_of 可辨識）。

用法:
  python scripts/push_holdings_daily.py
  python scripts/push_holdings_daily.py --dry-run    # 只印不送（仍需 SA + 網路讀 Sheet / 抓價）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TW_TZ = _dt.timezone(_dt.timedelta(hours=8))

# 兩條 sheet 通道（對齊 gsheet_portfolio 的 session channel 命名）:
#   PORTFOLIO_SHEET_ID       — ETF / legacy 組合（portfolios 分頁）
#   STOCK_PORTFOLIO_SHEET_ID — 個股組合 + 個股觀察清單（portfolios + stock_watchlist 分頁）
# 兩者皆選填,但至少要有一個（§1:皆缺 → raise）。
_PORTFOLIO_SHEET_ENV = "PORTFOLIO_SHEET_ID"
_STOCK_SHEET_ENV = "STOCK_PORTFOLIO_SHEET_ID"


def _tw_now() -> str:
    return _dt.datetime.now(_TW_TZ).strftime("%Y-%m-%d %H:%M")


def _build_entries(hold_raw: list[dict], wl_raw: list[str]) -> list[dict]:
    """持股 raw + 觀察清單 raw → 戰情引擎期望的 entries（純函式,離線可測）。

    - 持股（held=True,帶 lots/avg_price）優先;觀察清單（held=False,無價格）補上未持有者。
    - 以 ticker 去重（大寫比對）:持股 > 觀察清單（已持有的不重複列為觀察）。
    - asset_kind 用 `classify_asset_kind`（代號規則,與「在哪個清單」脫鉤）決定 stock/etf 分流;
      asset_class 僅供 80/20 顯示（個股→衛星、ETF→核心,對齊郭俊宏核心配息/衛星成長近似）。
    """
    from shared import dividend_station_thresholds as T

    entries: list[dict] = []
    seen: set[str] = set()
    _drop_hold: list[str] = []
    _drop_wl: list[str] = []

    def _kind_class(tk: str):
        _ak = T.classify_asset_kind(tk)
        _ac = T.ASSET_SATELLITE if _ak == T.KIND_STOCK else T.ASSET_CORE
        return _ak, _ac

    for h in (hold_raw or []):
        tk = str(h.get("ticker", "") or "").strip()
        if not tk:
            continue
        key = T.normalize_ticker(tk)   # 2330 與 2330.TW 同一檔（後綴 SSOT,跨兩 sheet 通道亦然）
        if key in seen:
            _drop_hold.append(tk)
            continue
        seen.add(key)
        _ak, _ac = _kind_class(tk)
        entries.append({"ticker": tk, "name": "", "asset_kind": _ak, "asset_class": _ac,
                        "held": True, "lots": h.get("lots"), "avg_price": h.get("avg_price")})

    for _t in (wl_raw or []):
        tk = str(_t or "").strip()
        if not tk:
            continue
        key = T.normalize_ticker(tk)
        if key in seen:                # 已在持股（或觀察清單自身）出現 → 不重列（持股優先,§1 去重要 log）
            _drop_wl.append(tk)
            continue
        seen.add(key)
        _ak, _ac = _kind_class(tk)
        entries.append({"ticker": tk, "name": "", "asset_kind": _ak, "asset_class": _ac,
                        "held": False, "lots": None, "avg_price": None})

    if _drop_hold:
        print(f"[push_holdings] 持股跨來源去重:略過重複 {len(_drop_hold)} 筆 → {'、'.join(_drop_hold)}")
    if _drop_wl:
        print(f"[push_holdings] 觀察清單與持股重複:略過 {len(_drop_wl)} 筆 → {'、'.join(_drop_wl)}")

    return entries


def _read_inputs(creds: dict) -> tuple[list[dict], list[str]]:
    """讀兩條 sheet 通道 → (持股 raw, 觀察清單 raw)。皆缺 sheet id → raise（§1）。"""
    from src.data.portfolio.gsheet_sa_reader import read_holdings, read_watchlist

    _pf = os.environ.get(_PORTFOLIO_SHEET_ENV, "").strip()
    _stk = os.environ.get(_STOCK_SHEET_ENV, "").strip()
    if not _pf and not _stk:
        raise ValueError(
            f"{_PORTFOLIO_SHEET_ENV} / {_STOCK_SHEET_ENV} 皆未設定 —— 請於 GitHub Secrets "
            "設定至少一個你的 Google Sheet ID（並已分享給 service account）。")
    hold_raw: list[dict] = []
    wl_raw: list[str] = []
    for _sid in (_pf, _stk):
        if _sid:
            hold_raw += read_holdings(_sid, creds)
            wl_raw += read_watchlist(_sid, creds)
    return hold_raw, wl_raw


def _maybe_ai_summary(digest: dict, switch: dict | None) -> str:
    """有 GEMINI_API_KEY → 回「\\n\\n──\\n🤖 AI 總結\\n{潤稿}」;缺 key / AI 失敗 → 回 ''。

    §1:AI 是加值、非主體 —— 缺 key 或失敗只記 log,規則式訊息照送。
    prompt 走 `build_summary_prompt`（純字串,數字全來自 digest/switch,禁腦補;§2.1 T5）。
    """
    _key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not _key:
        print("[push_holdings] 未設 GEMINI_API_KEY → 略過 AI 潤稿（只送規則式訊息）")
        return ""
    try:
        from src.compute.notify.ai_judgment import AI_JUDGMENT_MODELS
        from src.services.ai_fetcher import post_gemini
        from src.services.dividend_station_service import build_summary_prompt
        _prompt = build_summary_prompt(digest, switch=switch)
        _text, _model = post_gemini(
            _key, _prompt, models=AI_JUDGMENT_MODELS,
            temperature=0.2, max_tokens=700, timeout=120,
            retries_per_model=1, retry_after_parse=False, inter_model_sleep=0)
    except Exception as _e:  # noqa: BLE001 — AI 整段失敗 → 只送規則式,不炸
        print(f"[push_holdings] AI 潤稿失敗（略過只送規則式）：{type(_e).__name__}: {_e}",
              file=sys.stderr)
        return ""
    if not _text:
        print(f"[push_holdings] AI 潤稿無輸出（略過）：{_model}", file=sys.stderr)
        return ""
    print(f"[push_holdings] ✅ AI 潤稿已附加（model={_model}）")
    return "\n\n" + "─" * 12 + "\n🤖 AI 總結\n" + _text.strip()


def _empty_notice(as_of: str) -> str:
    return (f"💼 持股戰情室｜{as_of}\n\n"
            "讀不到任何持股 / 觀察清單。請確認：\n"
            "1) 你的 Google Sheet 已『分享』給 service account 的 client_email\n"
            "2) PORTFOLIO_SHEET_ID / STOCK_PORTFOLIO_SHEET_ID 設定正確\n"
            "3) Sheet 內 portfolios / stock_watchlist 分頁有資料\n"
            "（§1：不偽造持股清單，寧可提醒你檢查設定。）")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="每日持股續抱/換股推播（收盤後）")
    ap.add_argument("--dry-run", action="store_true", help="只印訊息不送（本地測）")
    args = ap.parse_args(argv)

    _as_of = _tw_now()
    print(f"[push_holdings] as_of={_as_of}")

    from src.compute.notify.holdings_digest_message import format_holdings_message
    from src.data.notify.dispatch import send_notification
    from src.data.portfolio.gsheet_sa_reader import load_sa_credentials

    _creds = load_sa_credentials()          # 缺 / 壞 JSON → raise → exit 1（§1）
    _hold_raw, _wl_raw = _read_inputs(_creds)   # 兩通道皆缺 sheet id → raise → exit 1
    _entries = _build_entries(_hold_raw, _wl_raw)
    print(f"[push_holdings] 持股 {sum(1 for e in _entries if e['held'])} 檔、"
          f"觀察 {sum(1 for e in _entries if not e['held'])} 檔")

    if not _entries:
        _msg = _empty_notice(_as_of)
        if args.dry_run:
            print("----- DRY RUN（未送）-----")
            print(_msg)
            return 0
        send_notification(_msg)
        print("[push_holdings] 空清單提醒已送出。")
        return 0

    # ── 沿用「💼 持股戰情室」引擎（逐檔續抱/換出 + 換入候選 + 總經攻守）──
    from src.services.dividend_station_service import (
        build_station_digest,
        build_switch_advice,
        get_station_macro,
        get_station_rows,
        get_switch_in_candidates,
        resolve_holding_names,
    )
    resolve_holding_names(_entries)             # best-effort 補中文名（抓不到留空,§1）
    _rows, _vix = get_station_rows(_entries)    # 逐檔抓價/財報/KD（單檔失敗標資料不足,不炸）
    _macro = get_station_macro()                # 總經位階（讀不到 → unknown,不瞎給攻守）
    _held = [e["ticker"] for e in _entries if e.get("held")]
    _cands = get_switch_in_candidates(regime=_macro.get("regime"), exclude=_held)  # 內含 fail→[]
    _switch = build_switch_advice(_rows, _macro, _cands)   # 純函式
    _digest = build_station_digest(_rows, _vix)            # 純函式

    _msg = format_holdings_message(_digest, _switch, as_of=_as_of)
    _msg += _maybe_ai_summary(_digest, _switch)

    if args.dry_run:
        print("----- DRY RUN（未送）-----")
        print(_msg)
        return 0

    _n = send_notification(_msg)   # NOTIFY_CHANNEL（預設 line）;secret 缺 → raise → exit 1
    print(f"[push_holdings] ✅ 已送出 {_n} 則訊息。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
