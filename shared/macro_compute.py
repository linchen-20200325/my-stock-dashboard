"""shared/macro_compute.py — 總經頁面用的純 L2 compute helper。

v18.344 PR-N1 從 daily_checklist.py 抽出純函式部分(無 IO):
- _num: 文字 → float 安全轉換
- _TW_TZ_DL / _tw_today_dl / _recent_date: TW 時區日期 helper
- evaluate_market_status_v4_final: 大盤狀態評分引擎(v4 純函式)
- analyze_20d_chips_from_df: 近 20 日籌碼集中度(直接吃 df,免 IO)

§8.2 L2 純函式層,不得 import streamlit / requests / 任何 IO。
"""
from __future__ import annotations

import datetime


# ── 文字 → 數字安全轉換 ────────────────────────────────
def _num(s):
    try:
        return float(str(s).replace(',', '').replace(' ', '').replace('+', ''))
    except Exception:
        return None


# ── TW 時區日期 ──────────────────────────────────────
_TW_TZ_DL = datetime.timezone(datetime.timedelta(hours=8))


def _tw_today_dl():
    return datetime.datetime.now(_TW_TZ_DL).date()


def _recent_date(fmt: str = "%Y%m%d"):
    """回最近一個交易日(週末退到週五),預設 YYYYMMDD 格式。"""
    d = _tw_today_dl()
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d.strftime(fmt)


# ── v4 大盤狀態評分 ──────────────────────────────────
def evaluate_market_status_v4_final(current_price: float, ma_240: float,
                                    futures_net_oi: int) -> dict:
    """台股 AI 戰情室 v4.0 核心引擎(專注共同基金與總經)。"""
    current_price = current_price or 1.0
    ma_240 = ma_240 or current_price
    futures_net_oi = futures_net_oi or 0

    bias_240 = ((current_price - ma_240) / ma_240) * 100
    is_bull_market = current_price >= (ma_240 * 0.99)
    is_overheated = bias_240 > 20.0
    is_foreign_hedging = futures_net_oi < -30000

    if is_bull_market:
        if is_overheated or is_foreign_hedging:
            signal = "🟡 多頭過熱 / 震盪警戒"
            action = "大盤乖離與外資避險過高。建議暫停積極型基金單筆申購，轉為定期定額，並拉高防禦型/平衡型基金權重。"
            hold_ratio = "50% - 70%"
        else:
            signal = "🟢 強勢多頭"
            action = "均線多頭排列且籌碼穩定。建議擴大核心部位，增加成長型股票基金曝險。"
            hold_ratio = "80% - 100%"
    else:
        signal = "🔴 空頭防禦"
        action = "跌破年線，趨勢偏空。維持既有定期定額，單筆操作宜觀望。"
        hold_ratio = "20% - 40%"

    return {
        "Signal": signal,
        "Action_Advice": action,
        "Suggested_Holding": hold_ratio,
        "Bias_240": round(bias_240, 2),
        "Is_Bull": is_bull_market,
        "Is_Overheated": is_overheated,
        "Is_Foreign_Hedging": is_foreign_hedging,
    }


# ── 近 20 日籌碼集中度(從 df,免 IO) ──────────────────
def analyze_20d_chips_from_df(df) -> dict:
    """近 20 日籌碼集中度 — 直接複用個股 K 線已載入的 df(含 外資/投信/volume 欄,
    單位皆為張),免重複呼叫 FinMind(規避 quota 失敗)。
    回傳格式與 analyze_20d_chips 完全相同;欄位不足時回 error 供呼叫端退回 API 版。"""
    try:
        import pandas as _pd
        if df is None or len(df) < 5:
            return {'error': 'df資料不足', 'signal': '⚫ 資料不足'}
        if not all(c in df.columns for c in ('外資', '投信', 'volume')):
            return {'error': 'df缺法人/量欄', 'signal': '⚫ 資料不足'}
        _d = df.tail(20)
        _net = (_pd.to_numeric(_d['外資'], errors='coerce').fillna(0)
                + _pd.to_numeric(_d['投信'], errors='coerce').fillna(0))
        _vol = _pd.to_numeric(_d['volume'], errors='coerce').fillna(0)
        if not (_net != 0).any():  # 法人欄全為 0 → df 未載到籌碼,退回 API 版
            return {'error': 'df法人欄全為0', 'signal': '⚫ 資料不足'}
        _tot_net = float(_net.sum())
        _tot_vol = float(_vol.sum())
        if _tot_vol <= 0:
            return {'error': '成交量為0', 'signal': '⚫ 資料不足'}
        _concentration = _tot_net / _tot_vol * 100
        _pos_days = int((_net > 0).sum())
        _continuity = _pos_days / len(_d) * 100
        if _concentration > 5 and _continuity > 50:
            _signal = '🔥 大戶吸籌'
        elif _concentration < -5:
            _signal = '🔴 大戶倒貨'
        else:
            _signal = '🟡 籌碼發散'
        return {
            'concentration': round(_concentration, 2),
            'continuity': round(_continuity, 1),
            'signal': _signal,
            'days': len(_d),
            'pos_days': _pos_days,
            'total_net_k': round(_tot_net / 1e3, 1),
            'total_vol_k': round(_tot_vol / 1e3, 1),
            'error': None,
        }
    except Exception as _edf:
        return {'error': str(_edf), 'signal': '⚫ 計算失敗'}
