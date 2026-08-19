"""src/compute/macro/macro_forward_test.py — 總經燈號前進式驗證「純邏輯」(L2 Compute)。

職責一句話:把一次 `calc_traffic_light` 的輸出,轉成一列可落地的快照 dict;
以及事後拿價格序列對帳算命中。

§8.2 L2:純函式,零 I/O(不讀檔、不打網路、不取系統時間)。
時間戳與 git sha 由 caller 注入 —— 這是刻意的:取系統時間會讓函式不可重現,
而可重現性正是這整組模組存在的理由(§5)。

schema 從 L0 `shared.macro_forward_test_schema` 取(不在本檔自定),
避免重犯 `CLAUDE.md §8.2.A.2 V-FT-STORE-1` 那個「L1 為了拿常數而 import L2」的錯。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

import pandas as pd

from shared.macro_forward_test_schema import (
    FWD_EVAL_HORIZON_DAYS,
    FWD_EVAL_MDD_THR_PCT,
    FWD_EVAL_RET_MAX_PCT,
    MACRO_FWD_TEST_HEADERS,
    MACRO_FWD_TEST_SCHEMA_VERSION,
    MISSING_SEP,
)


def compute_ruleset_hash() -> str:
    """把「決定燈號的那組常數」壓成一個短 hash,寫進每一列。

    為什麼需要:2026-08-19 一天之內燈號規則改了三次。沒有這個欄位,
    三個月後看到一列 🔴 無法回答「當時跑的是哪一版規則」。
    `git_sha` 不夠 —— 門檻可能由 `macro_thresholds.json` 在 runtime 覆寫,
    那不會反映在 commit 上。

    納入的是**會改變燈號結論**的常數;純顯示用的(色票、文案)刻意不納入,
    否則改一個 emoji 就讓 hash 變動,反而失去指示性。
    """
    from shared.macro_calibration import load_calibrated_thresholds
    from shared.position_throttle import (
        THROTTLE_HEALTH_A, THROTTLE_HEALTH_B, THROTTLE_HEALTH_DEF,
        THROTTLE_VETO_REGIMES,
    )
    from shared.signal_thresholds import (
        CONFIDENCE_SOURCE_COUNT, CONFIDENCE_SOURCE_GROUPS,
        HEALTH_FNET_BONUS, HEALTH_WEIGHT_JQ, HEALTH_WEIGHT_SCORE,
        M1B_M2_LEG_ENABLED, MARKET_BREADTH_NEUTRAL_PCT,
    )
    _h_thr, _s_thr = load_calibrated_thresholds()
    payload = {
        'health_defense_threshold': _h_thr,
        'bull_min_score': _s_thr,
        'w_jq': HEALTH_WEIGHT_JQ,
        'w_score': HEALTH_WEIGHT_SCORE,
        'fnet_bonus': HEALTH_FNET_BONUS,
        'm1b_leg': M1B_M2_LEG_ENABLED,
        'breadth_neutral': MARKET_BREADTH_NEUTRAL_PCT,
        'conf_count': CONFIDENCE_SOURCE_COUNT,
        'conf_groups': {k: list(v) for k, v in sorted(CONFIDENCE_SOURCE_GROUPS.items())},
        'throttle': [THROTTLE_HEALTH_A, THROTTLE_HEALTH_B, THROTTLE_HEALTH_DEF],
        'throttle_veto': sorted(THROTTLE_VETO_REGIMES),
        'schema': MACRO_FWD_TEST_SCHEMA_VERSION,
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()[:12]


def build_signal_row(
    tl: dict,
    *,
    date: str,
    captured_at: str,
    twii_close: Optional[float] = None,
    inputs_as_of: Optional[str] = None,
    git_sha: str = '',
    ruleset_hash: str = '',
) -> dict[str, Any]:
    """把一次 `calc_traffic_light` 輸出轉成一列快照。

    Args:
        tl: `macro_helpers.calc_traffic_light` 的回傳 dict。
        date: 'YYYY-MM-DD' 交易日(TW)。唯一鍵。
        captured_at: ISO8601 跑批時刻(caller 注入,本層不取系統時間)。
        twii_close: 當日 ^TWII 收盤。**None 是允許的**,但該列日後無法對帳。
        inputs_as_of: 輸入腿的資料日(外資 T+1 / Yahoo EOD 可能 ≠ date)。
        git_sha / ruleset_hash: caller 注入(git 查詢是 I/O,不屬 L2)。

    Raises:
        ValueError: `tl` 為空 —— §1 寧可炸掉也不落一列空殼。落了空殼,
            日後統計會把它當成一個真實觀測,而它什麼都不是。
    """
    if not tl:
        raise ValueError('build_signal_row: tl 為空 —— 不落空殼列(§1)')
    if not date:
        raise ValueError('build_signal_row: date 必填(唯一鍵)')

    _groups = tl.get('conf_groups') or {}
    _missing = tl.get('missing_sources') or []
    row = {
        'date': str(date),
        'captured_at': str(captured_at or ''),
        'icon': str(tl.get('icon') or ''),
        'label': str(tl.get('label') or ''),
        'effective_regime': str(tl.get('effective_regime') or ''),
        'regime_source': str(tl.get('regime_source') or ''),
        'defense': bool(tl.get('defense')),
        'health': _opt_float(tl.get('health')),
        'health_partial': bool(tl.get('health_partial')),
        'score': _opt_float(tl.get('score')),
        'max_score': _opt_float(tl.get('max_score')),
        'jqavg': _opt_float(tl.get('jqavg')),
        'conf': int(tl.get('conf') or 0),
        # dict 直接進 parquet 會變成 struct 欄、跨版本讀寫易碎 → 存 JSON 字串。
        'conf_groups': json.dumps(_groups, sort_keys=True),
        'missing_sources': MISSING_SEP.join(str(m) for m in _missing),
        'twii_close': _opt_float(twii_close),
        'inputs_as_of': str(inputs_as_of) if inputs_as_of else None,
        'git_sha': str(git_sha or ''),
        'ruleset_hash': str(ruleset_hash or ''),
        'schema_version': MACRO_FWD_TEST_SCHEMA_VERSION,
    }
    _unknown = set(row) - set(MACRO_FWD_TEST_HEADERS)
    if _unknown:
        raise ValueError(f'build_signal_row 產出 schema 外的欄位:{sorted(_unknown)}')
    return row


def _opt_float(v) -> Optional[float]:
    """數值轉 float;None / NaN / 非數 → None(**不轉 0**)。

    0 在 health / score 都是合法觀測值(最強利空),拿它頂替缺值就是
    本輪一直在修的那類錯(§1)。
    """
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f      # NaN 自身不等於自身


def evaluate_rows(
    rows: list[dict],
    close: pd.Series,
    *,
    horizon_days: int = FWD_EVAL_HORIZON_DAYS,
    mdd_thr_pct: float = FWD_EVAL_MDD_THR_PCT,
    ret_max_pct: float = FWD_EVAL_RET_MAX_PCT,
) -> pd.DataFrame:
    """事後對帳:對每一列算「之後 N 個交易日是否真的出事」。

    真值定義**刻意與 `scripts/calibrate_macro_traffic` 同一份**(常數來自同一個
    L0 SSOT):`hit ⇔ (後 N 日路徑 MDD < mdd_thr_pct) AND (後 N 日報酬 < ret_max_pct)`。
    兩套真值 = 兩套結論,而且沒有人會發現它們不一樣。

    §2.3 無 lookahead:每一列只看**它自己之後**的價格;窗口不足 N 日的列
    `hit` 為 None(**不是 False**)—— 「還沒到期」與「沒出事」是兩件事,
    混在一起會讓最近幾個月的紅燈全被記成「沒中」,系統性低估 precision。

    Args:
        rows: `build_signal_row` 產出的列(需含 'date')。
        close: DatetimeIndex 的收盤序列(遞增)。

    Returns:
        原列 + `fwd_ret_pct` / `fwd_mdd_pct` / `hit` / `evaluable` 四欄。
    """
    if not rows:
        return pd.DataFrame(columns=list(MACRO_FWD_TEST_HEADERS)
                            + ['fwd_ret_pct', 'fwd_mdd_pct', 'hit', 'evaluable'])
    s = pd.Series(close).dropna()
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()

    out = []
    for r in rows:
        rec = dict(r)
        d = pd.to_datetime(rec.get('date'), errors='coerce')
        rec['fwd_ret_pct'] = None
        rec['fwd_mdd_pct'] = None
        rec['hit'] = None
        rec['evaluable'] = False
        if pd.isna(d) or s.empty:
            out.append(rec)
            continue
        # 只取「該日之後」——嚴格大於,不含當日,避免把當日收盤當成未來資訊。
        fut = s[s.index > d]
        if len(fut) < horizon_days:
            out.append(rec)          # 窗口未滿 → 留 None,不判 False
            continue
        w = fut.iloc[:horizon_days]
        base = float(w.iloc[0])
        if base <= 0:
            out.append(rec)
            continue
        ret_pct = (float(w.iloc[-1]) / base - 1.0) * 100.0
        mdd_pct = float((w / w.cummax() - 1.0).min()) * 100.0
        rec['fwd_ret_pct'] = round(ret_pct, 4)
        rec['fwd_mdd_pct'] = round(mdd_pct, 4)
        rec['hit'] = bool(mdd_pct < mdd_thr_pct and ret_pct < ret_max_pct)
        rec['evaluable'] = True
        out.append(rec)
    return pd.DataFrame(out)


def summarise(df: pd.DataFrame, icon: str = '🔴') -> dict:
    """對某個燈號算 precision / base rate / lift(只用 evaluable 的列)。

    回傳含 `n_evaluable` 與 `n_pending` —— **pending 必須看得見**,
    否則讀者無法分辨「樣本少」與「訊號差」。
    """
    if df is None or df.empty or 'hit' not in df.columns:
        return {'n_evaluable': 0, 'n_pending': 0, 'precision': None,
                'base_rate': None, 'lift': None, 'icon': icon}
    ev = df[df['evaluable'] == True]              # noqa: E712 — 明示布林比較,防 NaN 混入
    pend = int((df['evaluable'] != True).sum())   # noqa: E712
    if ev.empty:
        return {'n_evaluable': 0, 'n_pending': pend, 'precision': None,
                'base_rate': None, 'lift': None, 'icon': icon}
    base = float(ev['hit'].mean())
    sel = ev[ev['icon'] == icon]
    prec = float(sel['hit'].mean()) if not sel.empty else None
    return {
        'n_evaluable': int(len(ev)),
        'n_pending': pend,
        'n_signal': int(len(sel)),
        'precision': prec,
        'base_rate': base,
        'lift': (prec / base) if (prec is not None and base > 0) else None,
        'icon': icon,
    }
