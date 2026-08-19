#!/usr/bin/env python3
"""scripts/update_macro_forward_test.py — 總經燈號每日 headless 落地(cron CLI)。

為什麼有這支
------------
2026-08-19 實測發現:`calc_traffic_light` 的輸出(燈號 / 健康分 / 信心分數)
**從來沒有離開過瀏覽器 session**。每天算一次、渲染、消失。於是「紅燈準不準」
在本 repo 從來沒有樣本外證據,而唯一能離線重算的
`scripts/calibrate_macro_traffic.py` 是**重建版**,實測至少兩處與線上系統性不同
(`conf` 恆 60 vs 可達 100;`m1b_m2_prev` 有真值 vs 恆 None)。

本腳本補上那條缺的 headless 入口。

刻意的設計:**呼叫與畫面完全同一組 L3 函式**
-------------------------------------------
`fetch_macro_bundle` / `compute_and_store_jingqi` /
`compute_and_apply_market_assessment` / `calc_traffic_light` 全部照原樣呼叫,
**一行公式都不重寫**。streamlit 的 `st.session_state` 在無 runtime 的 bare
模式可正常讀寫(實測),所以那幾個「會寫 session_state」的 L3 函式在這裡照用。

這一點是本腳本最重要的性質:任何「為了 headless 而另寫一份簡化版計算」的做法,
都會製造第二份真相,而第二份真相正是這整件事要解決的問題(見上一段)。
⇒ **維護守則:未來若這裡開始出現 `if headless:` 分支或自算公式,就是走錯了。**

§1 Fail Loud:
- 資料全敗 / 燈號算不出來 → **exit 0 且不寫列**(不落空殼;空殼會被日後統計
  當成一個真實觀測)。exit 0 而非 1 —— 休市日走的是同一條路,不該讓 cron 紅燈。
- 部分腿缺 → 照樣寫列並記 `missing_sources`(缺失本身就是要驗的東西之一)。

§2.3 對齊:cron 排 TW 17:40(收盤後)。外資 T+1、Yahoo EOD 使得部分腿的資料日
可能早於 `date`,故另存 `inputs_as_of` 供事後分辨。

用法::

    python scripts/update_macro_forward_test.py            # 寫入今天(TW)
    python scripts/update_macro_forward_test.py --dry-run  # 只印不寫
    python scripts/update_macro_forward_test.py --date 2026-08-18
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TW = timezone(timedelta(hours=8))


def _git_sha() -> str:
    """短 commit sha;取不到回 ''(不編造)。"""
    try:
        out = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                             capture_output=True, text=True, timeout=10,
                             cwd=str(Path(__file__).resolve().parents[1]))
        return out.stdout.strip() if out.returncode == 0 else ''
    except Exception as _e:  # noqa: BLE001
        print(f'[macro_fwd] git sha 取不到({type(_e).__name__}),留空')
        return ''


def _fetch_live_bundle(fm_token: str) -> dict:
    """跑與畫面同一條抓取鏈,回 `fetch_macro_bundle` 的 bundle。"""
    from src.services.daily_checklist import INTL_MAP, TECH_MAP, TW_MAP
    from src.services.macro_fetch_orchestrator import fetch_macro_bundle
    from src.data.daily.daily_data_fetchers import (
        fetch_adl, fetch_institutional, fetch_margin_balance, fetch_single,
    )
    return fetch_macro_bundle(
        load_heavy=True,            # cron 一定抓重資料(沒有暖 session 可沿用)
        prev_cl_data={},
        fm_token=fm_token,
        li_token=fm_token,
        intl_map=INTL_MAP, tw_map=TW_MAP, tech_map=TECH_MAP,
        fetch_single=fetch_single,
        fetch_institutional=fetch_institutional,
        fetch_margin_balance=fetch_margin_balance,
        fetch_adl=fetch_adl,
    )


def _twii_close_and_asof(tw_raw: dict):
    """從 bundle 的 tw_raw 取 ^TWII 收盤 + 該筆的資料日。

    取不到 → (None, None)。**不猜、不用前一日頂替** —— 沒有收盤價的列
    日後無法對帳,那是它真實的狀態,不該被掩蓋。
    """
    df = (tw_raw or {}).get('台股加權指數')
    try:
        if df is None or getattr(df, 'empty', True) or 'Close' not in df.columns:
            return None, None
        s = df['Close'].dropna()
        if s.empty:
            return None, None
        _asof = s.index[-1]
        return float(s.iloc[-1]), str(getattr(_asof, 'date', lambda: _asof)())
    except Exception as _e:  # noqa: BLE001
        print(f'[macro_fwd] twii 收盤解析失敗:{type(_e).__name__}: {_e}')
        return None, None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='總經燈號每日 headless 落地')
    ap.add_argument('--date', default='', help="交易日 YYYY-MM-DD(留空 = 今天 TW)")
    ap.add_argument('--dry-run', action='store_true', help='只印不寫檔')
    args = ap.parse_args(argv)

    import streamlit as st
    from src.compute.macro import calc_traffic_light
    from src.compute.macro.macro_forward_test import build_signal_row, compute_ruleset_hash
    from src.data.macro.macro_fwd_test_store import MACRO_FWD_TEST_PATH, append_signals
    from src.services.jingqi_calc import compute_and_store_jingqi
    from src.services.market_assessment_apply import compute_and_apply_market_assessment

    _now = datetime.now(_TW)
    _date = args.date.strip() or _now.strftime('%Y-%m-%d')

    from src.config import get_finmind_token
    _fm = get_finmind_token() or os.environ.get('FINMIND_TOKEN', '')
    if not _fm:
        print('[macro_fwd] ⚠️ 無 FinMind token —— 先行指標與外資 rescue 會缺,'
              '仍繼續(缺失會記進 missing_sources)')

    try:
        bundle = _fetch_live_bundle(_fm)
    except Exception as _e:  # noqa: BLE001
        print(f'[macro_fwd] ❌ 抓取鏈整條失敗:{type(_e).__name__}: {_e}')
        traceback.print_exc()
        return 0                       # 不寫列、不讓 cron 紅燈

    tw_raw = bundle.get('tw_raw') or {}
    inst = bundle.get('inst') or {}
    df_adl = bundle.get('df_adl_raw')
    df_li = bundle.get('df_li_a')

    # ── 走與畫面同一組 L3(它們寫 session_state,bare 模式可用)──────────
    st.session_state['cl_data'] = dict(
        intl=bundle.get('intl_raw'), tw=tw_raw, tech=bundle.get('tech_raw'),
        inst=inst, inst_date=bundle.get('inst_date'), margin=bundle.get('margin'),
        adl=df_adl)
    if df_adl is not None:
        compute_and_store_jingqi(df_adl)
    compute_and_apply_market_assessment(
        inst=inst, tw_raw=tw_raw, margin=bundle.get('margin'), df_adl=df_adl)

    tl = calc_traffic_light(
        st.session_state.get('mkt_info') or {},
        st.session_state.get('jingqi_info') or {},
        st.session_state.get('cl_data') or {},
        df_li,
    )
    if not tl:
        print(f'[macro_fwd] {_date} 三來源全空 → 不寫列(§1 不落空殼)')
        return 0

    _close, _asof = _twii_close_and_asof(tw_raw)
    row = build_signal_row(
        tl, date=_date, captured_at=_now.isoformat(timespec='seconds'),
        twii_close=_close, inputs_as_of=_asof,
        git_sha=_git_sha(), ruleset_hash=compute_ruleset_hash(),
    )
    print(f"[macro_fwd] {_date} {row['icon']} {row['label']} | "
          f"health={row['health']} score={row['score']}/{row['max_score']} "
          f"conf={row['conf']}% | twii={row['twii_close']} as_of={row['inputs_as_of']} "
          f"| ruleset={row['ruleset_hash']}")
    if row['missing_sources']:
        print(f"[macro_fwd] 缺失來源:{row['missing_sources']}")
    if row['twii_close'] is None:
        print('[macro_fwd] ⚠️ 無 ^TWII 收盤 —— 本列日後無法對帳(仍寫入,誠實記錄狀態)')

    if args.dry_run:
        print('[macro_fwd] --dry-run:不寫檔')
        return 0
    n = append_signals([row])
    print(f'[macro_fwd] ✅ 寫入 {n} 列 → {MACRO_FWD_TEST_PATH}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
