"""健康度評分純函式 — 從 app.py:L600-823 抽出（PR P2-B Phase 3）

零 Streamlit / 零 session state 依賴，可在 CLI / pytest 環境直接 import。

收錄函式
========
- calc_fundamental_score(qtr_df, yearly_df, avg_div) -> dict
  基本面四維評分：獲利 / 成長 / 股利 / 估值，各 0-3 分

- calc_health_score(df, rsi, ibs, vr, k_val, d_val, bb) -> tuple[int, dict]
  綜合健康度評分（0-100），含趨勢/RSI/量比/IBS/KD/布林 6 因子

- health_grade(score) -> tuple[str, str, str, str]
  分數 → (等級標籤, 顏色 hex, css class, emoji)

呼叫端
======
- app.py:render_health_score, render_etf_single 等多處
"""
from __future__ import annotations

import pandas as _pd_fs

from shared.thresholds import YIELD_HIGH, YIELD_MID, YIELD_LOW


def calc_fundamental_score(qtr_df, yearly_df, avg_div):
    """基本面四維評分：獲利/成長/股利/估值，各 0-3 分"""
    # 防呆：list 或非 DataFrame 型別 → 視為無資料
    if isinstance(qtr_df, list) or not hasattr(qtr_df, 'empty'):
        qtr_df = None
    if isinstance(yearly_df, list) or not hasattr(yearly_df, 'empty'):
        yearly_df = None
    result = {
        'profit':   {'score':0,'max':3,'label':'獲利','checks':[]},
        'growth':   {'score':0,'max':3,'label':'成長','checks':[]},
        'dividend': {'score':0,'max':3,'label':'股利','checks':[]},
        'valuation':{'score':0,'max':3,'label':'估值','checks':[]},
    }
    try:
        if qtr_df is not None and not qtr_df.empty:
            def _gcol(*keys):
                for k in keys:
                    for c in qtr_df.columns:
                        if k in str(c):
                            return c
                return None
            def _num(c, row=-1):
                if c is None:
                    return None
                v = _pd_fs.to_numeric(qtr_df[c].iloc[row], errors='coerce')
                return None if _pd_fs.isna(v) else float(v)
            # 獲利
            eps_c = _gcol('EPS','eps')
            np_c  = _gcol('稅後淨利率','淨利率')
            op_c  = _gcol('營業利益率','營益率')
            if eps_c:
                es = _pd_fs.to_numeric(qtr_df[eps_c].tail(4), errors='coerce').dropna()
                sm = float(es.sum()) if len(es)>=2 else 0
                ok = sm >= 1
                result['profit']['score'] += int(ok)
                result['profit']['checks'].append(('近4季EPS>=1', f'{sm:.2f}', ok))
            if np_c:
                v = _num(np_c)
                ok = v is not None and v >= 5
                result['profit']['score'] += int(ok)
                result['profit']['checks'].append(('稅後淨利率>=5%', f'{v:.1f}%' if v else 'N/A', ok))
            if op_c:
                v = _num(op_c)
                ok = v is not None and v >= 10
                result['profit']['score'] += int(ok)
                result['profit']['checks'].append(('營業利益率>=10%', f'{v:.1f}%' if v else 'N/A', ok))
            # 成長
            rev_c = _gcol('營收','revenue')
            gp_c  = _gcol('毛利率')
            eps_c2= _gcol('EPS','eps')
            if rev_c and len(qtr_df)>=2:
                v1,v2 = _num(rev_c,-1),_num(rev_c,-2)
                ok = v1 and v2 and v1>v2
                result['growth']['score'] += int(ok)
                result['growth']['checks'].append(('營收季增', '成長中' if ok else '未成長', ok))
            if eps_c2 and len(qtr_df)>=5:
                v1,v5 = _num(eps_c2,-1),_num(eps_c2,-5)
                ok = v1 and v5 and v1>v5
                result['growth']['score'] += int(ok)
                result['growth']['checks'].append(('EPS年增', '成長中' if ok else '衰退', ok))
            if gp_c:
                v = _num(gp_c)
                ok = v is not None and v >= 20
                result['growth']['score'] += int(ok)
                result['growth']['checks'].append(('毛利率>=20%', f'{v:.1f}%' if v else 'N/A', ok))
        # 股利
        if avg_div and avg_div > 0:
            ok = avg_div >= 4
            result['dividend']['score'] += 2 if avg_div>=4 else (1 if avg_div>=2 else 0)
            result['dividend']['checks'].append(('平均殖利率', f'{avg_div:.1f}%', ok))
        if yearly_df is not None and not yearly_df.empty:
            dc = next((c for c in yearly_df.columns if '現金股利' in str(c) or '配息' in str(c)), None)
            if dc:
                ds = _pd_fs.to_numeric(yearly_df[dc].tail(4), errors='coerce').dropna()
                ok = len(ds)>=3 and (ds>0).all()
                result['dividend']['score'] += int(ok)
                result['dividend']['checks'].append(('近4年配息', '穩定' if ok else '不穩定', ok))
        # 估值 357
        if avg_div and avg_div > 0:
            if avg_div>=YIELD_HIGH:
                sc,lb=3,'便宜區 >7%'
            elif avg_div>=YIELD_MID:
                sc,lb=2,'合理 5~7%'
            elif avg_div>=YIELD_LOW:
                sc,lb=1,'合理 3~5%'
            else:
                sc,lb=0,'偏貴 <3%'
            result['valuation']['score'] = sc
            result['valuation']['checks'].append(('357殖利率估值', f'{avg_div:.1f}% {lb}', sc>=2))
    except Exception as _e:
        print(f'[calc_fundamental_score] {_e}')
    return result


def calc_health_score(df, rsi, ibs, vr, k_val, d_val, bb):
    """
    綜合健康度評分，各因子分述：
    - 趨勢（MA20/MA100）    : 30分
    - RSI動能              : 20分
    - 量比                 : 15分
    - IBS位置              : 10分
    - KD排列               : 15分
    - 布林位置              : 10分
    """
    score = 0
    details = {}

    if df is not None and not df.empty:
        price  = float(df['close'].iloc[-1])
        ma20   = float(df['MA20'].iloc[-1])  if 'MA20'  in df.columns else None
        ma100  = float(df['MA100'].iloc[-1]) if 'MA100' in df.columns else None

        # 趨勢 (30分)
        if ma20 and ma100:
            if price > ma20 > ma100:
                score += 30
                details['趨勢'] = ('多頭排列', 30, 30)
            elif price > ma100 and price > ma20:
                # P6修正: 需同時站上ma20和ma100才算「多箱整理」
                score += 18
                details['趨勢'] = ('多箱整理(站上雙均)', 18, 30)
            elif price > ma20 and price < ma100:
                # 站上短均但低於長均 → 反彈初期，偏謹慎
                score += 10
                details['趨勢'] = ('短線反彈(低於長均)', 10, 30)
            elif price < ma20 and price > ma100:
                # 短均跌破但長均支撐 → 整理中
                score += 8
                details['趨勢'] = ('整理中(長均支撐)', 8, 30)
            else:
                score += 0
                details['趨勢'] = ('空頭排列', 0,  30)
        else:
            score += 15
            details['趨勢'] = ('無MA數據', 15, 30)

    # RSI (20分) — C-1 v18.382:50/40 inline 補抽(70/30 已在 config.py SSOT)
    if rsi is not None:
        from shared.signal_thresholds import RSI_STRONG_LOW, RSI_NEUTRAL_WEAK_LOW
        from src.config import RSI_OVERBOUGHT, RSI_OVERSOLD
        if RSI_STRONG_LOW <= rsi <= RSI_OVERBOUGHT:
            score += 20
            details['RSI'] = (f'{rsi}（強勢區間）', 20, 20)
        elif RSI_NEUTRAL_WEAK_LOW <= rsi < RSI_STRONG_LOW:
            score += 12
            details['RSI'] = (f'{rsi}（中性偏弱）', 12, 20)
        elif RSI_OVERSOLD <= rsi < RSI_NEUTRAL_WEAK_LOW:
            score += 8
            details['RSI'] = (f'{rsi}（超賣邊緣）', 8,  20)
        elif rsi < RSI_OVERSOLD:
            score += 14
            details['RSI'] = (f'{rsi}（超賣反彈機會）', 14, 20)
        else:  # >70
            score += 8
            details['RSI'] = (f'{rsi}（超買注意）', 8,  20)

    # 量比 (15分)
    if vr is not None:
        # P2-3 v18.381:3.0 inline → shared SSOT
        from shared.signal_thresholds import VOLUME_RATIO_SURGE_HIGH
        if vr > VOLUME_RATIO_SURGE_HIGH:
            # P7修正: 量比>3.0是重大消息/主力介入，給高分
            score += 12
            details['量比'] = (f'{vr}（主力介入）', 12, 15)
        elif 1.5 <= vr <= 3.0:
            score += 15
            details['量比'] = (f'{vr}（異常放量）', 15, 15)
        elif 1.0 <= vr < 1.5:
            score += 10
            details['量比'] = (f'{vr}（溫和放量）', 10, 15)
        elif 0.5 <= vr < 1.0:
            score += 5
            details['量比'] = (f'{vr}（量縮整理）', 5,  15)
        else:
            score += 2
            details['量比'] = (f'{vr}（極度縮量）', 2,  15)

    # IBS (10分)
    if ibs is not None:
        if ibs <= 0.2:
            score += 10
            details['IBS'] = (f'{ibs}（收低≤20%，隔日易反彈）', 10, 10)
        elif ibs >= 0.8:
            score += 2
            details['IBS'] = (f'{ibs}（收高≥80%，隔日易賣壓）', 2,  10)
        else:
            score += 6
            details['IBS'] = (f'{ibs}（中性）', 6, 10)

    # KD (15分)
    if k_val is not None and d_val is not None:
        if k_val > d_val and k_val < 80:
            score += 15
            details['KD'] = (f'K={k_val} D={d_val}（黃金交叉）', 15, 15)
        elif k_val > d_val and k_val >= 80:
            score += 8
            details['KD'] = (f'K={k_val} D={d_val}（高檔黃叉注意）', 8, 15)
        elif k_val < d_val and k_val > 20:
            score += 5
            details['KD'] = (f'K={k_val} D={d_val}（死亡交叉）', 5, 15)
        else:
            score += 10
            details['KD'] = (f'K={k_val} D={d_val}（低檔死叉可守）', 10, 15)

    # 布林 (10分)
    if bb is not None:
        if bb['near_upper']:
            score += 8
            details['布林'] = ('黏近上軌（強勢）', 8, 10)
        elif bb['price'] > bb['ma']:
            score += 6
            details['布林'] = ('站上中軌', 6, 10)
        elif bb['bw'] < bb['bw_mean'] * 0.7:
            score += 9
            details['布林'] = ('帶寬極度收縮（即將爆發）', 9, 10)
        else:
            score += 3
            details['布林'] = ('低於中軌', 3, 10)

    return min(score, 100), details


def health_grade(score):
    # v18.210 K4：走 shared/colors SSOT
    # v18.214 K7：走 shared/health_thresholds SSOT 閾值常數
    from shared.colors import TRAFFIC_GREEN, TRAFFIC_YELLOW, TRAFFIC_RED
    from shared.health_thresholds import HEALTH_GRADE_A_MIN, HEALTH_GRADE_B_MIN
    if score >= HEALTH_GRADE_A_MIN:
        return '優質優良', TRAFFIC_GREEN, 'health-A', '🟢'
    if score >= HEALTH_GRADE_B_MIN:
        return '震盪盤整', TRAFFIC_YELLOW, 'health-B', '🟡'
    return '弱勢危險', TRAFFIC_RED, 'health-C', '🔴'
