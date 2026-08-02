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
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TW_TZ = _dt.timezone(_dt.timedelta(hours=8))


def _tw_now() -> str:
    return _dt.datetime.now(_TW_TZ).strftime("%Y-%m-%d %H:%M")


def _build_pe_name_maps() -> tuple[dict, dict]:
    """全市場(上市 TWSE + 上櫃 TPEX)PE / 名稱 → (pe_map, name_map)。抓不到 → 空 dict。

    走 SSOT `fetch_pe_name_maps` —— 畫面 / 凍結 / MCP / 推播 四 orchestrator 同源,確保
    推播選股 = 畫面選股,且上櫃股同樣有估值分 + 中文名(原僅 TWSE → 上櫃股空白)(§8 SSOT)。
    """
    try:
        from src.ui.tabs.yield_screener import fetch_pe_name_maps
        return fetch_pe_name_maps()
    except Exception as _e:  # noqa: BLE001 — PE 抓不到 → pe_low 缺料,不炸
        print(f"[push_signals] PE 抓取失敗:{type(_e).__name__}: {_e}", file=sys.stderr)
        return {}, {}


def _fetch_chip_for(code: str, loader) -> dict:
    """單檔籌碼:法人 20 日流向 + 大戶持股比例%。全程 fail-soft(抓不到 → None,不炸)。

    回 {"flow": analyze_20d_chips_from_df 輸出 | None,
        "holder": {"pct": float, "delta": float | None} | None}。
    §1:任一路失敗只記 stderr + 回 None → 訊息端該徽章自動略,不影響其他股、不腦補。
    """
    out = {"flow": None, "holder": None}
    # (1) 法人 20 日流向:get_combined_data(價+法人+融資)→ analyze_20d_chips_from_df
    #     (上市走 TWSE T86、上櫃走 TPEX fallback;全 0 → analyze 自回 error → 略)
    try:
        from shared.macro_compute import analyze_20d_chips_from_df
        _df, _err, _ = loader.get_combined_data(code, 90)
        if _df is not None and not getattr(_df, "empty", True):
            out["flow"] = analyze_20d_chips_from_df(_df)
    except Exception as _e:  # noqa: BLE001 — 法人籌碼抓不到 → 無流向徽章,不炸
        print(f"[push_signals] {code} 法人籌碼失敗:{type(_e).__name__}: {_e}", file=sys.stderr)
    # (2) 大戶持股比例%:集保股權分散表(週更新;取最新 + 對前一筆的週變化)
    try:
        from src.data.stock.chip_concentration_fetcher import fetch_chip_concentration
        _res = fetch_chip_concentration(code)
        _cdf = _res.get("df") if isinstance(_res, dict) else None
        if (_cdf is not None and not getattr(_cdf, "empty", True)
                and "大戶比例" in _cdf.columns):
            _s = _cdf.sort_values("日期") if "日期" in _cdf.columns else _cdf
            _vals = _s["大戶比例"].dropna()
            if len(_vals) >= 1:
                _pct = float(_vals.iloc[-1])
                _delta = float(_vals.iloc[-1] - _vals.iloc[-2]) if len(_vals) >= 2 else None
                out["holder"] = {"pct": _pct, "delta": _delta}
    except Exception as _e:  # noqa: BLE001 — 大戶比例抓不到 → 無水位徽章,不炸
        print(f"[push_signals] {code} 大戶比例失敗:{type(_e).__name__}: {_e}", file=sys.stderr)
    return out


def _maybe_ai_judgment(picks, tech_by, *, as_of, trend_by, short_by, chip_by) -> str:
    """有 GEMINI_API_KEY → 回「\\n\\n──\\n{AI 研判段}」;缺 key / AI 失敗 → 回 ''。

    §1:AI 是加值、非主體 —— 缺 key 或全 model 失敗只記 log,清單照送。
    §2.1 Tier-5:prompt(見 ai_judgment.py)已硬性要求只依 Data、禁腦補數字、非投資建議。
    """
    _key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not _key:
        print("[push_signals] 未設 GEMINI_API_KEY → 略過 AI 研判(只送清單)")
        return ""
    try:
        from src.compute.notify.ai_judgment import (
            AI_JUDGMENT_MODELS,
            build_ai_judgment_prompt,
        )
        from src.services.ai_fetcher import post_gemini
        _prompt = build_ai_judgment_prompt(
            picks, tech_by, as_of=as_of,
            trend_by_code=trend_by, shortage_by_code=short_by, chip_by_code=chip_by)
        _text, _model = post_gemini(
            _key, _prompt, models=AI_JUDGMENT_MODELS,
            temperature=0.2, max_tokens=1200, timeout=120,
            retries_per_model=1, retry_after_parse=False, inter_model_sleep=0)
    except Exception as _e:  # noqa: BLE001 — AI 整段失敗 → 只送清單,不炸
        print(f"[push_signals] AI 研判失敗(略過只送清單):{type(_e).__name__}: {_e}",
              file=sys.stderr)
        return ""
    if not _text:
        print(f"[push_signals] AI 研判無輸出(略過):{_model}", file=sys.stderr)
        return ""
    print(f"[push_signals] ✅ AI 研判已附加(model={_model})")
    return "\n\n" + "─" * 12 + "\n" + _text.strip()


def main(argv=None) -> int:
    from src.compute.notify.signal_message import (
        format_empty_message,
        format_signal_message,
    )
    from src.compute.notify.technical_snapshot import build_technical_snapshot
    from src.config import get_stock_name
    from src.data.core import StockDataLoader
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
        # 中文名 fallback:選股用的 name_map 只有上市(TWSE),上櫃股空名 → 補 get_stock_name
        # (涵蓋上市+上櫃;回傳=代碼代表查無 → 留空,不印「6223 6223」)。
        for _p in _picks:
            _c = str(_p.get("代碼", "") or "").strip()
            if _c and not str(_p.get("名稱", "") or "").strip():
                try:
                    _n = get_stock_name(_c)
                    if _n and _n != _c:
                        _p["名稱"] = _n
                except Exception as _e:  # noqa: BLE001 — 名稱補不到 → 只顯代碼,不炸
                    print(f"[push_signals] {_c} 名稱 fallback 失敗:{type(_e).__name__}: {_e}",
                          file=sys.stderr)
        _loader = StockDataLoader()
        _tech: dict = {}
        _chip_by: dict = {}
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
            _chip_by[_code] = _fetch_chip_for(_code, _loader)   # 法人流向 + 大戶比例(fail-soft)
        # 財報趨勢 / 缺貨 tier 查表(§1:缺料的股不在表 → 徽章自動略)
        _trend_by: dict = {}
        if _trend_df is not None and not _trend_df.empty:
            for _r in _trend_df.to_dict("records"):
                _trend_by[str(_r.get("stock_id"))] = _r
        _short_by = {str(_r.get("代碼")): _r.get("_tier") for _r in (_shortage_rows or [])}
        _msg = format_signal_message(_picks, _tech, as_of=_as_of,
                                     trend_by_code=_trend_by, shortage_by_code=_short_by,
                                     chip_by_code=_chip_by)
        # AI 研判(偏多/偏空/需觀察):有 GEMINI_API_KEY 才接;缺 key / AI 失敗 → 略過只送清單
        _msg += _maybe_ai_judgment(_picks, _tech, as_of=_as_of,
                                   trend_by=_trend_by, short_by=_short_by, chip_by=_chip_by)

    if args.dry_run:
        print("----- DRY RUN(未送)-----")
        print(_msg)
        return 0

    _n = send_notification(_msg)   # NOTIFY_CHANNEL(預設 line);secret 缺 → raise → exit 1
    print(f"[push_signals] ✅ 已送出 {_n} 則訊息。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
