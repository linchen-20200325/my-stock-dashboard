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
import math

import numpy as np

from shared.signal_thresholds import FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD


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


def tw_now() -> datetime.datetime:
    """現在時刻(台灣時區 UTC+8,tz-aware)。

    F2(2026-08):原 `app.py::_tw_now`。放這裡是因為本檔已經持有 `_TW_TZ_DL`
    這個 UTC+8 常數(§4.5),再開一份 `timezone(timedelta(hours=8))` 就是第 N 份複本。
    """
    return datetime.datetime.now(_TW_TZ_DL)


def tw_now_str() -> str:
    """`tw_now()` 的 `'%Y-%m-%d %H:%M'` 字串(原 `app.py::_tw_now_str`,格式一字未改)。"""
    return tw_now().strftime('%Y-%m-%d %H:%M')


def _recent_date(fmt: str = "%Y%m%d"):
    """回最近一個交易日(週末退到週五),預設 YYYYMMDD 格式。"""
    d = _tw_today_dl()
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d.strftime(fmt)


# ── v4 大盤狀態評分 ──────────────────────────────────
def _is_finite_positive(x) -> bool:
    """價／年線可用 ⇔ 有限正實數(批 Z3,V2-n1)。

    None／0／負／NaN／±inf／字串(含數字字串)／bool(含 numpy bool 純量)／轉 float 溢位的超大 int
    ／複數(含 numpy complex 與 complex 陣列)→ False。判法參照 v1 唯一消費端 `section_warroom`
    判「可讀」所用的 `section_long._finite_yoy`(先排除 None／bool,再 `math.isfinite`),外加 > 0;
    差別是本函式連 numpy bool 與複數也排除,`_finite_yoy` 只排除 Python bool
    ⇒ 消費端讀 `Bias_240` 前須自行判 None(section_warroom 已加)。
    ⚠️ 未排除:0 維布林陣列 `np.array(True)` —— `math.isfinite` 與 `> 0` 都放行 ⇒ 另一邊合格時當 1
    參與運算;價與年線都是它時在相減拋 TypeError(與 fd989ae 同)。批 Z3 重驗時發現、已回報總管;
    該輪正式碼只准改 docstring,未修。
    ⚠️ 更正(批 Z3 驗收,兩度):原句「(numpy bool)修前它在算式裡就拋 TypeError」不實;第一次更正
    『只有價與年線「兩邊都是」numpy bool 才拋…單邊時是把 np.True_ 當 1、np.False_ 經 `or` 換成 1.0,
    算出假乖離』也不精確。fd989ae 實跑:先經 `or` 置換 —— 價是假值(含 np.False_)→ 1.0;年線是假值
    (含 np.False_)→ 置換後的價;np.True_ 是真值,不置換。numpy bool 引起的 TypeError(numpy bool
    不支援相減)只在置換後兩邊「都是布林(Python bool／numpy bool／0 維布林陣列)、且至少一邊是 numpy
    型別」時發生 —— 兩邊都給 numpy bool 的四種組合只有 (np.True_, np.True_)、(np.True_, np.False_) 拋;
    單邊也會拋:價給 np.True_、年線給 None／0／False／'' 等假值(被換成 np.True_)或 Python True,
    以及 (True, np.True_)。下列照算(np.True_ 當 1 參與運算,np.False_ 依上述置換):(np.False_,
    np.False_)、(np.False_, np.True_)、(20000, np.False_) 得乖離 0.0、判「🟢 強勢多頭」;
    (np.True_, 16000)、(np.False_, 16000) 得 -99.99;(20000, np.True_) 得 1999900.0。
    📌 批 Z3 驗收阻擋 3-7:複數不是實數 —— numpy complex 會讓 `math.isfinite` 丟掉虛部放行
    (只發 ComplexWarning),接著在 `round()` 拋 TypeError;依規格「不是有限正實數 → None、不拋」先行排除。
    只判斷、不轉型:合格時引擎照舊拿原物件計算 ⇒ 輸出逐位不變(Decimal 亦照舊,含修前就會拋的組合)。
    """
    if x is None or isinstance(x, (bool, np.bool_, complex, np.complexfloating)):
        return False
    if getattr(getattr(x, 'dtype', None), 'kind', None) == 'c':     # complex ndarray(含 0 維)
        return False
    try:
        return bool(math.isfinite(x) and x > 0)
    except (TypeError, ValueError, OverflowError):   # 非實數 / 轉不成 float / 超大 int 溢位 → 不可用
        return False


def evaluate_market_status_v4_final(current_price: float, ma_240: float,
                                    futures_net_oi: int) -> dict:
    """台股 AI 戰情室 v4.0 核心引擎(專注共同基金與總經)。

    批 Z3(V2-n1,併 V2-n10;§1 不捏值):原 `current_price or 1.0`／`ma_240 or current_price`
    把缺值捏成「價 1.0、年線＝價」⇒ (None,None,None)、(0,0,0) 回 `Bias_240` 0.0、`Is_Bull` True、
    強勢多頭那一組 Signal／建議;非數字價格(例 'N/A')則拋 TypeError。改為:價或年線不是有限正實數
    (`_is_finite_positive`)⇒ 依賴價格／年線的鍵(Signal／Action_Advice／Suggested_Holding／
    Bias_240／Is_Bull／Is_Overheated)一律 None、不拋;不依賴價格的 `Is_Foreign_Hedging` 照舊。
    有限正數輸入走原算式、原物件 ⇒ 全部輸出逐位不變。
    批 Z10(C8-n6,§1 不捏值):原 `futures_net_oi or 0` 把外資期貨缺值捏成 0 ⇒ `Is_Foreign_Hedging`
    回 False(「確定沒避險」)。改為:`futures_net_oi` 為 None ⇒ `Is_Foreign_Hedging` 回 None(未知);
    其餘依賴價格的鍵照舊(None 在多頭分支的 `or` 與 False 同為不成立 ⇒ Signal／建議／持股不變)。
    批 Z10(Z6-n2,§3.3):門檻改接 SSOT `FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD`(同值 30000)。
    批 Z10(Q-r10b,客戶 2026-10-09):剛好 −30000 歸「防禦」側,判式由 `<` 改 `<=`(全站統一)。
    其餘非 None 輸入 ⇒ 全部輸出(含型別、含會拋的組合)逐位不變 ——
    故非 None 那枝保留原 `or 0`(其餘假值如 0／0.0／False／空字串照修前處理,未擴大範圍)。
    """
    is_foreign_hedging = (None if futures_net_oi is None
                          else (futures_net_oi or 0) <= -FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD)

    if not (_is_finite_positive(current_price) and _is_finite_positive(ma_240)):
        return {
            "Signal": None,
            "Action_Advice": None,
            "Suggested_Holding": None,
            "Bias_240": None,
            "Is_Bull": None,
            "Is_Overheated": None,
            "Is_Foreign_Hedging": is_foreign_hedging,
        }

    bias_240 = ((current_price - ma_240) / ma_240) * 100
    is_bull_market = current_price >= (ma_240 * 0.99)
    is_overheated = bias_240 > 20.0

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
