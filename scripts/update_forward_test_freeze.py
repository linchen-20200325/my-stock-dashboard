"""scripts/update_forward_test_freeze.py — 前進式驗證「每月自動凍結」cron CLI(v19.147)。

解 forward-test 卡在 0 樣本的根因:原本凍結只能手動按 + 只存私人 Google Sheet(headless
cron 無 OAuth 用不了)。本腳本每月自動跑「完整選股網」→ 取綜合評分前 N 名 → 抓當下進場價
→ 存本地 git 追蹤 parquet(data_cache/forward_test/picks.parquet),workflow 再 commit 進 repo。
這樣數據會自己累積、可稽核,日後對帳看「這套選股實際贏不贏 0050」(零 lookahead/存活者偏誤)。

同源保證(§8 SSOT):選股走 L3 `get_ranked_picks` —— 與 app.py 選股網畫面**同一支函式**,
所以「自動凍結的清單 = 使用者畫面按『開始選股』會看到的清單」。

用法(GitHub Actions / 本地):
  python scripts/update_forward_test_freeze.py                 # 用全 5 因子、今天(TW)當 cohort、前 20 名
  python scripts/update_forward_test_freeze.py --cohort 2026-07-01 --top-n 20   # 指定批次日/檔數
  python scripts/update_forward_test_freeze.py --factors pe_low,eps_high        # 只用部分因子

§1 fail-loud:存活池空 / 綜合排名空(季快照未就緒)→ log + exit 0(該月不凍結,非錯誤,
不讓 workflow 紅燈);真實例外 → exit 1。§5 冪等:同 (cohort, stock_id) 重跑不重複新增。
§8.2:本檔為 orchestrator(同 app.py / update_fundamentals_snapshot),可跨層 import。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# TW 時區(UTC+8):cohort 標籤用 TW 日,對齊 app.py 手動凍結(_tw_now)。
_TW_TZ = _dt.timezone(_dt.timedelta(hours=8))


def _tw_today() -> str:
    return _dt.datetime.now(_TW_TZ).strftime("%Y-%m-%d")


def _build_pe_name_maps() -> tuple[dict, dict]:
    """自 TWSE BWIBBU 抓全市場本益比 / 名稱 → (pe_map, name_map)。抓不到 → 兩個空 dict。

    PE fetcher 在 L5(fetch_twse_yield_pe),本腳本為 orchestrator 可直呼;抓不到時 pe_low
    因子自然缺料(composite 不計入、不記 0),不炸(§1)。
    """
    try:
        from src.ui.tabs.yield_screener import fetch_twse_yield_pe
        _df = fetch_twse_yield_pe()
    except Exception as _e:  # noqa: BLE001 — PE 抓不到 → pe_low 缺料,不炸整體
        print(f"[ft_freeze] TWSE 本益比抓取失敗:{type(_e).__name__}: {_e}")
        return {}, {}
    if _df is None or _df.empty or "代碼" not in _df.columns:
        return {}, {}
    _codes = _df["代碼"].astype(str)
    _pe = dict(zip(_codes, _df["本益比"])) if "本益比" in _df.columns else {}
    _nm = dict(zip(_codes, _df["名稱"].astype(str))) if "名稱" in _df.columns else {}
    return _pe, _nm


def main(argv=None) -> int:
    from shared.forward_test_thresholds import FORWARD_TEST_FREEZE_TOP_N
    from src.services.forward_test_service import freeze_current_picks_local
    from src.services.fundamental_screener_service import (
        SCREEN_ANGLE_LABELS,
        get_ranked_picks,
    )

    _all_factors = list(SCREEN_ANGLE_LABELS.values())   # ['pe_low','eps_high','shortage','rs_leader','trend']

    ap = argparse.ArgumentParser(description="前進式驗證每月自動凍結(完整選股網 → 前 N 名)")
    ap.add_argument("--cohort", default="", help="批次標籤(YYYY-MM-DD);留空=今天(TW)")
    ap.add_argument("--top-n", type=int, default=FORWARD_TEST_FREEZE_TOP_N,
                    help=f"凍結綜合評分前 N 名(預設 {FORWARD_TEST_FREEZE_TOP_N})")
    ap.add_argument("--factors", default="",
                    help="逗號分隔因子 key(留空=全 5 因子;如 pe_low,eps_high)")
    args = ap.parse_args(argv)

    _cohort = args.cohort.strip() or _tw_today()
    _factors = ([f.strip() for f in args.factors.split(",") if f.strip()]
                if args.factors.strip() else _all_factors)
    print(f"[ft_freeze] cohort={_cohort} top_n={args.top_n} factors={_factors}")

    # 完整選股網(同 app.py 畫面同源):auto_fetch=True → 缺貨/RS/跨季自動掃;PE 由本層注入。
    _pe_map, _name_map = _build_pe_name_maps()
    try:
        _cands, _note = get_ranked_picks(
            _factors, top_n=max(args.top_n, 300),
            pe_map=_pe_map, name_map=_name_map, auto_fetch=True,
        )
    except Exception as _e:  # noqa: BLE001 — 選股整體失敗才走這;視為硬錯
        print(f"[ft_freeze] ❌ 選股失敗:{type(_e).__name__}: {_e}")
        return 1
    if _note:
        print(f"[ft_freeze] note: {_note}")

    if _cands is None or _cands.empty or "代碼" not in _cands.columns:
        print("[ft_freeze] ⚠️ 綜合排名為空(季快照未就緒 / 存活池空)→ 本月不凍結,exit 0。")
        return 0

    _top = _cands.head(int(args.top_n))
    _codes = [str(c) for c in _top["代碼"].tolist()]
    _names = (dict(zip(_codes, _top["名稱"].astype(str)))
              if "名稱" in _top.columns else {})

    _n, _miss = freeze_current_picks_local(
        _codes, factors=_factors, cohort=_cohort, names=_names)
    print(f"[ft_freeze] ✅ 凍結 {_n} 檔(cohort {_cohort});"
          f"{_miss} 檔抓不到進場價已略過;候選 {len(_codes)} 檔。")
    if _n == 0 and _codes:
        # 有候選卻 0 檔存入:通常是這批已凍結過(冪等)或全抓不到價。log 但不算失敗。
        print("[ft_freeze] (0 檔新增:該 cohort 可能已凍結過,或全數抓不到進場價)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
