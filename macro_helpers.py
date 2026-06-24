"""tab_macro.py 共用純函式 — Phase 7A-Ext（2026-05-16）。

零 Streamlit / Plotly 依賴，純資料計算。從 tab_macro.render_tab_macro
抽出供 unit test 與未來模組共用。

設計原則：
- pure function：相同輸入恆等輸出
- 防呆優先：所有 helper 對 None / 空 dict / 缺欄位皆有 fallback
- 易測：對應 tests/test_macro_helpers.py 完整 coverage
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
# v18.241 E1+E2: 抽 inline magic 到 shared SSOT（CLAUDE.md §3.3）
from shared.signal_thresholds import (
    HEALTH_WEIGHT_JQ, HEALTH_WEIGHT_SCORE, HEALTH_FNET_BONUS, CONFIDENCE_SOURCE_COUNT,
)

# 季末日對照（DataFrame 內「季度標籤 2024Q4」→「2024-12-31」用）
_QE_MAP = {'1': '03-31', '2': '06-30', '3': '09-30', '4': '12-31'}

# v18.140 校準收斂門檻：health 低於此值觸發 🔴 防禦；regime=bull 需 score ≥ 此值才升 🟢
# v18.143+：優先讀 macro_thresholds.json（由季度 recalibrate workflow 經 PR 審閱後寫入），
# 缺檔則 fall back 至模組預設常數
# S-GRAY-1 v18.244:loader I/O 已下沉 `shared/macro_calibration.py`(L0 Infra),
# 本檔僅做 module-level call 後 expose 常數,符合 L2 「純函式 / 無 I/O」邊界。
from shared.macro_calibration import load_calibrated_thresholds as _load_calibrated_thresholds

HEALTH_DEFENSE_THRESHOLD, BULL_MIN_SCORE = _load_calibrated_thresholds()


def calc_traffic_light(
    mkt_info: Optional[dict],
    jingqi_info: Optional[dict],
    cl_data: Optional[dict],
    li_latest: Any,
    *,
    health_defense_threshold: Optional[int] = None,
    bull_min_score: Optional[int] = None,
) -> Optional[dict]:
    """根據當前數據計算紅綠燈狀態，回傳 dict。無數據時回傳 None。

    取代 tab_macro.render_tab_macro._calc_traffic_light closure。

    決策樹（v18.140 校準後收斂門檻，常數見模組 HEALTH_DEFENSE_THRESHOLD / BULL_MIN_SCORE）：
      1. 三來源全空 → None（由 placeholder 顯示等待）
      2. defense 觸發（score<2 且外資期貨大空單）或 health<HEALTH_DEFENSE_THRESHOLD → 🔴 空頭防禦
      3. regime=='bull' AND score>=BULL_MIN_SCORE → 🟢 多頭積極
      4. regime in ('caution','bear') → 🔴 保守防禦
      5. 其他 → 🟡 震盪整理

    Args:
        mkt_info:    market_regime() 回傳，含 'score' / 'regime'
        jingqi_info: 景氣指標，含 'avg'
        cl_data:     籌碼資料，含 'inst'（外資 net）/ 'adl'
        li_latest:   先行指標 DataFrame，含 '外資大小' / '韭菜指數' 欄

    Returns:
        dict (color, icon, label, action, sub, health, defense,
              score, jqavg, leek, fnet, fk, fut_net, conf, regime) 或 None
    """
    if not mkt_info and not jingqi_info and not cl_data:
        return None
    _mkt    = mkt_info   or {}
    _jq     = jingqi_info or {}
    _cd     = cl_data    or {}
    _score  = _mkt.get('score', 0)
    _jqavg  = _jq.get('avg', 50)
    _inst   = _cd.get('inst', {})
    _fk     = next((k for k in _inst if '外資' in k), None)
    _fnet   = _inst.get(_fk, {}).get('net', 0) if _fk else 0

    # 先行指標：期貨外資大小、韭菜指數
    _fut_net = 0
    _leek = 50
    if li_latest is not None and not li_latest.empty:
        if '外資大小' in li_latest.columns:
            try:
                _fut_net = float(li_latest.iloc[-1].get('外資大小', 0))
            except Exception:
                pass
        if '韭菜指數' in li_latest.columns:
            try:
                _leek = float(li_latest.iloc[-1].get('韭菜指數', 50))
            except Exception:
                pass

    _regime  = _mkt.get('regime', 'neutral')
    _defense = (_score < 2 and abs(_fut_net) > 30000 and _fut_net < 0)
    # v18.241 E1: 健康評分權重從 SSOT 引入（原 0.4/0.4/20 inline）
    _health  = round(
        _jqavg * HEALTH_WEIGHT_JQ
        + min(_score / CONFIDENCE_SOURCE_COUNT * 100, 100) * HEALTH_WEIGHT_SCORE
        + (HEALTH_FNET_BONUS if _fnet > 0 else 0), 1
    )

    # 校準腳本可注入測試門檻；正式呼叫不傳 → 用模組常數
    _h_thr = health_defense_threshold if health_defense_threshold is not None else HEALTH_DEFENSE_THRESHOLD
    _s_thr = bull_min_score if bull_min_score is not None else BULL_MIN_SCORE

    if _defense or _health < _h_thr:
        _color, _icon  = TRAFFIC_RED, '🔴'
        _label  = '空頭防禦｜降低部位'
        _action = '⛔ 大環境惡化，系統已啟動資金保護機制'
        _sub    = '建議持有現金，等待市場明確訊號，禁止追買任何個股'
    elif _regime == 'bull' and _score >= _s_thr:
        _color, _icon  = TRAFFIC_GREEN, '🟢'
        _label  = '多頭市場｜積極操作'
        _action = '✅ 市場健康，籌碼乾淨，可積極尋找強勢標的'
        _sub    = '可積極尋找強勢標的，留意趨勢延續性'
    elif _regime in ('caution', 'bear'):
        _color, _icon  = TRAFFIC_RED, '🔴'
        _label  = '保守防禦｜縮減部位'
        _action = '⛔ 市場走弱，建議縮減持股比例，等待多頭確認'
        _sub    = '降低風險暴露，避免新開倉，等待多頭重啟'
    else:
        _color, _icon  = TRAFFIC_YELLOW, '🟡'
        _label  = '震盪整理｜謹慎觀望'
        _action = '⚠️ 市場處於整理期，謹慎操作，降低部位'
        _sub    = '持有現有倉位觀望，不追高，等待更明確信號'

    _conf_sources = [
        ('大盤趨勢評分 (market_regime)', bool(mkt_info)),
        ('旌旗指數 (站上均線比例)',       bool(jingqi_info)),
        ('外資買賣超 (三大法人)',         bool(_fk)),
        ('先行指標 (期貨/PCR/韭菜)',      bool(li_latest is not None and not li_latest.empty)),
        ('ADL 騰落指標',                  bool(_cd.get('adl') is not None)),
    ]
    # v18.241 E2: confidence 分子分母從 SSOT 引入
    _conf = round(sum(_ok for _, _ok in _conf_sources) / CONFIDENCE_SOURCE_COUNT * 100)
    _missing = [_name for _name, _ok in _conf_sources if not _ok]
    return {
        'color': _color, 'icon': _icon, 'label': _label,
        'action': _action, 'sub': _sub, 'health': _health,
        'defense': _defense, 'score': _score, 'jqavg': _jqavg,
        'leek': _leek, 'fnet': _fnet, 'fk': _fk, 'fut_net': _fut_net,
        'conf': _conf, 'missing_sources': _missing, 'regime': _regime,
    }


def rp_ts(df: Any) -> str:
    """取 DataFrame 最新日期字串（與 _reg_add 邏輯一致）。

    支援來源（依序嘗試）：
      1. DatetimeIndex → 直接取 max
      2. 「季度標籤」欄（'2024Q4' → '2024-12-31'，依 _QE_MAP）
      3. 「年度」欄（int → 'YYYY-12-31'）
      4. _date / date / datetime / timestamp / 日期 / quarter / period 欄
         （_date 強制 '%Y%m%d' format，其他自動推斷）

    任何例外或無法解析 → 回 'N/A'。
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return 'N/A'
    if isinstance(df.index, pd.DatetimeIndex):
        try:
            return pd.Timestamp(df.index.max()).strftime('%Y-%m-%d')
        except Exception:
            pass
    for c in df.columns:
        cl = str(c)
        cll = cl.lower()
        if cl == '季度標籤':
            try:
                lq = str(df[c].dropna().iloc[-1])
                yr_q, qn = lq.split('Q')
                return f'{yr_q}-{_QE_MAP.get(qn, "12-31")}'
            except Exception:
                pass
        if cl == '年度':
            try:
                yr = int(df[c].dropna().iloc[-1])
                return f'{yr}-12-31'
            except Exception:
                pass
        fmt = '%Y%m%d' if cll == '_date' else None
        if cll in ('_date', 'date', 'datetime', 'timestamp', '日期', 'quarter', 'period'):
            try:
                lat = pd.to_datetime(df[c], format=fmt, errors='coerce').max()
                if lat is not None and not pd.isna(lat):
                    return lat.strftime('%Y-%m-%d')
            except Exception:
                pass
    return 'N/A'


def rp_entry(df: Any, cat: str, freq: str) -> dict:
    """DataFrame → registry entry dict（last_updated + rows + cat + freq）。

    空 / None → missing=True；有資料 → 用 rp_ts 取最後日期。
    """
    if isinstance(df, pd.DataFrame) and not df.empty:
        return {'last_updated': rp_ts(df), 'rows': len(df), 'category': cat, 'frequency': freq}
    return {'last_updated': 'N/A', 'rows': 0, 'category': cat, 'frequency': freq, 'missing': True}


def rp_scalar(val: Any, cat: str, freq: str, proxy_date: str) -> dict:
    """純量值（健康度評分 / RSI / 殖利率等）→ registry entry dict。

    有值（非 None）→ rows=1 + last_updated=proxy_date（呼叫端傳入今天或總經更新時間）
    None → missing=True。
    """
    if val is not None:
        return {'last_updated': proxy_date, 'rows': 1, 'category': cat, 'frequency': freq}
    return {'last_updated': 'N/A', 'rows': 0, 'category': cat, 'frequency': freq, 'missing': True}


# v18.169: MK 黃金拐點（CPI × Fed Funds 雙頂回落）— 純函式 helper
def detect_mk_golden_inflection(
    cpi_yoy: Optional[float],
    cpi_prev_yoy: Optional[float],
    fed_rate: Optional[float],
    fed_prev_rate: Optional[float],
) -> Optional[dict]:
    """MK 黃金拐點偵測 — CPI YoY × Fed Funds Rate 雙頂回落判讀（鏡像 fund _detect_inflection）。

    參數
    ----
    cpi_yoy        : 最新月度美國核心 CPI 年增率（%）
    cpi_prev_yoy   : 上月度美國核心 CPI 年增率（%）
    fed_rate       : 最新月度 Fed Funds Rate（%，月均有效利率）
    fed_prev_rate  : 上月度 Fed Funds Rate（%）

    回傳
    ----
    None  — 資料不足（任一參數為 None）或無 MK 訊號
    dict  — {'label', 'icon', 'color', 'detail', 'strength'}
            strength: 'strong'（雙明確回落）/ 'weak'（CPI 弱降+Fed 持平）

    判讀規則（防雜訊：±0.05ppt 視為持平）
    --------
    - CPI 月降 ≥ 0.2ppt AND Fed 持平或月降      → ⭐ 強訊號（MK 黃金拐點 ＝ 多頭最佳買點）
    - CPI 月降 ∈ [0.05, 0.2)ppt AND Fed 持平或月降 → ✅ 弱訊號（MK 拐點觀察中）
    - 任一上升 (> 0.05ppt) 或 CPI 未降          → None（無訊號）
    """
    if cpi_yoy is None or cpi_prev_yoy is None:
        return None
    if fed_rate is None or fed_prev_rate is None:
        return None

    try:
        cpi_delta = float(cpi_yoy) - float(cpi_prev_yoy)      # 負值 = 通膨降溫
        fed_delta = float(fed_rate) - float(fed_prev_rate)    # 負/零 = 降息或暫停
    except (TypeError, ValueError):
        return None

    # 任一指標明確上升 → 無 MK 訊號
    if cpi_delta > 0.05 or fed_delta > 0.05:
        return None
    # CPI 須至少出現降溫（>= 0.05ppt 月降）
    if cpi_delta > -0.05:
        return None

    _fed_desc = '持平' if abs(fed_delta) < 0.05 else f'月降 {abs(fed_delta):.2f}ppt'

    if cpi_delta <= -0.2:
        return {
            'label': 'MK 黃金拐點 ⭐',
            'icon': '⭐',
            'color': TRAFFIC_GREEN,
            'detail': (
                f'核心 CPI {cpi_prev_yoy:+.2f}% → {cpi_yoy:+.2f}% '
                f'（月降 {abs(cpi_delta):.2f}ppt） + Fed Funds '
                f'{fed_prev_rate:.2f}% → {fed_rate:.2f}% （{_fed_desc}） '
                f'→ ⭐ 通膨+利率雙頂回落，景氣多頭最佳買點（歷史勝率最高）'
            ),
            'strength': 'strong',
        }
    return {
        'label': 'MK 拐點觀察中',
        'icon': '✅',
        'color': TRAFFIC_YELLOW,
        'detail': (
            f'核心 CPI {cpi_prev_yoy:+.2f}% → {cpi_yoy:+.2f}% + '
            f'Fed Funds {fed_prev_rate:.2f}% → {fed_rate:.2f}% '
            f'→ 通膨初步降溫，待 CPI 加速回落或 Fed 確認暫停升息'
        ),
        'strength': 'weak',
    }


# v18.170: 長期總經位階分類（12M 視角，景氣大循環）— 純函式 helper
def _safe_float(x: Any) -> Optional[float]:
    """容錯轉浮點：None/字串/NaN → None。"""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN guard
        return None
    return f


def classify_long_term_regime(
    cpi_yoy: Any,
    fed_rate: Any,
    fed_prev_rate: Any,
    ndc_score: Any,
    pmi: Any,
    mk_signal: Optional[dict] = None,
) -> dict:
    """長期總經位階判讀（12M 視角，景氣大循環）。

    參數
    ----
    cpi_yoy        : 美國核心 CPI YoY（%）
    fed_rate       : 最新 Fed Funds Rate（%）
    fed_prev_rate  : 上月 Fed Funds Rate（%）
    ndc_score      : 台灣景氣對策信號分數（9-45）
    pmi            : 台灣製造業 PMI 指數（CIER）
    mk_signal      : detect_mk_golden_inflection() 回傳值（None 或 dict）

    回傳
    ----
    dict 含 regime / score / color / detail / suggest_pct / components
    components 為 list[tuple(name, score_pts, weight_pct)]，便於 UI 拆解顯示

    評分（每項 ∈ [-2, +2]，加權加總）
    --------
    - CPI YoY (25%)：≤2%+2 / 2-3%+1 / 3-4% 0 / 4-5%-1 / ≥5%-2
    - Fed 方向 (20%)：月降+2 / 持平+1 / 月升-2
    - NDC (20%)：紅(≥38)+2 / 黃紅(32-37)+1 / 綠(23-31) 0 / 黃藍(17-22)-1 / 藍(<17)-2
    - PMI (20%)：≥55+2 / 52-55+1 / 50-52 0 / 48-50-1 / <48-2
    - MK 拐點 (15%)：⭐強+2 / ✅弱+1 / None 0
    """
    cpi_v = _safe_float(cpi_yoy)
    fed_v = _safe_float(fed_rate)
    fed_p = _safe_float(fed_prev_rate)
    ndc_v = _safe_float(ndc_score)
    pmi_v = _safe_float(pmi)

    components: list = []
    weighted_sum = 0.0
    weight_total = 0.0

    # 1. CPI YoY 趨勢（25%）
    if cpi_v is not None:
        if cpi_v <= 2.0:
            cpi_pts = 2
        elif cpi_v <= 3.0:
            cpi_pts = 1
        elif cpi_v <= 4.0:
            cpi_pts = 0
        elif cpi_v <= 5.0:
            cpi_pts = -1
        else:
            cpi_pts = -2
        components.append(('美 CPI YoY', cpi_pts, 25))
        weighted_sum += cpi_pts * 25
        weight_total += 25

    # 2. Fed Funds 方向（20%）
    if fed_v is not None and fed_p is not None:
        fed_delta = fed_v - fed_p
        if fed_delta < -0.05:
            fed_pts = 2
        elif fed_delta <= 0.05:
            fed_pts = 1
        else:
            fed_pts = -2
        components.append(('Fed 方向', fed_pts, 20))
        weighted_sum += fed_pts * 20
        weight_total += 20

    # 3. NDC 景氣對策（20%）
    if ndc_v is not None:
        if ndc_v >= 38:
            ndc_pts = 2
        elif ndc_v >= 32:
            ndc_pts = 1
        elif ndc_v >= 23:
            ndc_pts = 0
        elif ndc_v >= 17:
            ndc_pts = -1
        else:
            ndc_pts = -2
        components.append(('NDC 景氣燈號', ndc_pts, 20))
        weighted_sum += ndc_pts * 20
        weight_total += 20

    # 4. PMI 水準（20%）
    if pmi_v is not None:
        if pmi_v >= 55:
            pmi_pts = 2
        elif pmi_v >= 52:
            pmi_pts = 1
        elif pmi_v >= 50:
            pmi_pts = 0
        elif pmi_v >= 48:
            pmi_pts = -1
        else:
            pmi_pts = -2
        components.append(('台 PMI', pmi_pts, 20))
        weighted_sum += pmi_pts * 20
        weight_total += 20

    # 5. MK 黃金拐點訊號（15%）— 僅當至少一個主指標存在時才計入
    if weight_total > 0:
        if mk_signal is not None and isinstance(mk_signal, dict):
            _s = mk_signal.get('strength')
            mk_pts = 2 if _s == 'strong' else (1 if _s == 'weak' else 0)
        else:
            mk_pts = 0
        components.append(('MK 拐點', mk_pts, 15))
        weighted_sum += mk_pts * 15
        weight_total += 15

    if weight_total == 0:
        return {
            'regime': '⚪ 資料不足',
            'score': 0.0,
            'color': '#8b949e',
            'detail': '所有長期指標皆缺失，無法判讀',
            'suggest_pct': 'N/A',
            'components': components,
        }

    score = weighted_sum / weight_total  # ∈ [-2, +2]

    if score >= 1.0:
        regime, color, suggest = '🟢 成長期', TRAFFIC_GREEN, '80%+'
        detail = '景氣擴張+通膨溫和+資金寬鬆 → 多頭主升段，可積極做多'
    elif score >= 0.0:
        regime, color, suggest = '🔵 復甦期', '#58a6ff', '60-80%'
        detail = '景氣由谷底回升 → 加碼基本面好的標的，留意通膨變化'
    elif score >= -1.0:
        regime, color, suggest = '🟡 過熱/震盪期', TRAFFIC_YELLOW, '40-60%'
        detail = '景氣高檔震盪或通膨壓力 → 謹慎觀望，等待方向確認'
    else:
        regime, color, suggest = '🔴 衰退期', TRAFFIC_RED, '<30%'
        detail = '景氣下行+通膨壓力或政策緊縮 → 保守減倉，現金為王'

    return {
        'regime': regime,
        'score': round(score, 2),
        'color': color,
        'detail': detail,
        'suggest_pct': suggest,
        'components': components,
    }


# v18.170: 短期總經分類（1Q 視角，對齊台股財報季）— 純函式 helper
def classify_short_term_regime(
    export_yoy: Any,
    pmi: Any,
    vix_current: Any,
    fi_streak_days: Any,
    cpi_yoy: Any,
    cpi_prev_yoy: Any,
) -> dict:
    """短期總經偏向判讀（1Q 視角，對齊台股財報季 Q1/Q2/Q3/Q4）。

    參數
    ----
    export_yoy      : 台灣出口 YoY（%）
    pmi             : 台灣製造業 PMI（CIER 指數）
    vix_current     : VIX 收盤
    fi_streak_days  : 外資連續買賣超天數（+正=連買，負=連賣）
    cpi_yoy         : 美 CPI YoY（%）
    cpi_prev_yoy    : 上月 CPI YoY（%）

    回傳
    ----
    dict 含 regime / score / color / detail / action / components

    評分（每項 ∈ [-2, +2]，加權加總）
    --------
    - 出口 YoY (25%)：≥15%+2 / 5-15%+1 / 0-5% 0 / -5-0%-1 / <-5%-2
    - PMI 水準 (25%)：≥55+2 / 52-55+1 / 50-52 0 / 48-50-1 / <48-2
    - VIX 水準 (15%)：<15+2 / 15-20+1 / 20-25 0 / 25-30-1 / ≥30-2
    - 外資連續 (20%)：連買≥5+2 / 1-4+1 / 0 0 / 連賣1-4-1 / 連賣≥5-2
    - CPI 月降 (15%)：降≥0.3+2 / 0.1-0.3+1 / ±0.1 0 / 升0.1-0.3-1 / 升≥0.3-2
    """
    exp_v = _safe_float(export_yoy)
    pmi_v = _safe_float(pmi)
    vix_v = _safe_float(vix_current)
    fi_v  = _safe_float(fi_streak_days)
    cpi_v = _safe_float(cpi_yoy)
    cpi_p = _safe_float(cpi_prev_yoy)

    components: list = []
    weighted_sum = 0.0
    weight_total = 0.0

    # 1. 出口 YoY（25%）
    if exp_v is not None:
        if exp_v >= 15:
            exp_pts = 2
        elif exp_v >= 5:
            exp_pts = 1
        elif exp_v >= 0:
            exp_pts = 0
        elif exp_v >= -5:
            exp_pts = -1
        else:
            exp_pts = -2
        components.append(('出口 YoY', exp_pts, 25))
        weighted_sum += exp_pts * 25
        weight_total += 25

    # 2. PMI 水準（25%）
    if pmi_v is not None:
        if pmi_v >= 55:
            pmi_pts = 2
        elif pmi_v >= 52:
            pmi_pts = 1
        elif pmi_v >= 50:
            pmi_pts = 0
        elif pmi_v >= 48:
            pmi_pts = -1
        else:
            pmi_pts = -2
        components.append(('台 PMI', pmi_pts, 25))
        weighted_sum += pmi_pts * 25
        weight_total += 25

    # 3. VIX 水準（15%）
    if vix_v is not None:
        if vix_v < 15:
            vix_pts = 2
        elif vix_v < 20:
            vix_pts = 1
        elif vix_v < 25:
            vix_pts = 0
        elif vix_v < 30:
            vix_pts = -1
        else:
            vix_pts = -2
        components.append(('VIX 波動', vix_pts, 15))
        weighted_sum += vix_pts * 15
        weight_total += 15

    # 4. 外資連續日數（20%）
    if fi_v is not None:
        if fi_v >= 5:
            fi_pts = 2
        elif fi_v >= 1:
            fi_pts = 1
        elif fi_v > -1:
            fi_pts = 0
        elif fi_v > -5:
            fi_pts = -1
        else:
            fi_pts = -2
        components.append(('外資籌碼', fi_pts, 20))
        weighted_sum += fi_pts * 20
        weight_total += 20

    # 5. CPI 月降幅（15%）
    if cpi_v is not None and cpi_p is not None:
        cpi_delta = cpi_v - cpi_p   # 負值 = 通膨降溫
        if cpi_delta <= -0.3:
            cpi_pts = 2
        elif cpi_delta <= -0.1:
            cpi_pts = 1
        elif cpi_delta <= 0.1:
            cpi_pts = 0
        elif cpi_delta <= 0.3:
            cpi_pts = -1
        else:
            cpi_pts = -2
        components.append(('CPI 月降', cpi_pts, 15))
        weighted_sum += cpi_pts * 15
        weight_total += 15

    if weight_total == 0:
        return {
            'regime': '⚪ 資料不足',
            'score': 0.0,
            'color': '#8b949e',
            'detail': '所有短期指標皆缺失，無法判讀',
            'action': 'N/A',
            'components': components,
        }

    score = weighted_sum / weight_total  # ∈ [-2, +2]

    if score >= 0.8:
        regime, color = '⚡ 偏多', TRAFFIC_GREEN
        detail = '下個財報季正向動能 → 加碼績優股、波段佈局好時機'
        action = '建議：擇強做多、留意外資連續買超的個股'
    elif score >= -0.3:
        regime, color = '⚖️ 中性', TRAFFIC_YELLOW
        detail = '訊號分歧或多空交織 → 觀望為主、留意個股輪動'
        action = '建議：區間操作、避免追高殺低、續抱長期持股'
    else:
        regime, color = '⚠️ 偏空', TRAFFIC_RED
        detail = '下個財報季承壓 → 防守為主、現金為王'
        action = '建議：減碼高估值、停利出場、留意外資連續賣超'

    return {
        'regime': regime,
        'score': round(score, 2),
        'color': color,
        'detail': detail,
        'action': action,
        'components': components,
    }


# ════════════════════════════════════════════════════════════════════════════
# v18.270 — TW 央行政策階段衍生函式
# Spec(§7 對齊):純函式無 I/O,搭配 tw_macro.fetch_* 上游
# ════════════════════════════════════════════════════════════════════════════

def calc_real_rate(rate_pct: Optional[float],
                   cpi_yoy_pct: Optional[float]) -> Optional[float]:
    """實質利率(%) = 名目政策利率(%) − CPI YoY(%)。

    Args
    ----
    rate_pct: CBC 重貼現率或銀行間隔夜拆款 (% level)
    cpi_yoy_pct: CPI 年增率 (% YoY)

    Returns
    -------
    float | None
        實質利率;任一輸入為 None / NaN → None(§1 不偽造)。

    Notes
    -----
    經濟學上,實質利率為負(rate < CPI)= 寬鬆;為正且 > 1% = 緊縮。
    """
    if rate_pct is None or cpi_yoy_pct is None:
        return None
    try:
        rr = float(rate_pct) - float(cpi_yoy_pct)
        if pd.isna(rr):
            return None
        return round(rr, 3)
    except (TypeError, ValueError):
        return None


def classify_rate_cycle(rate_series: Optional[pd.Series],
                        lookback_months: int = 6,
                        epsilon: float = 0.05) -> str:
    """依政策利率近 N 月變化分類「升息中 / 持平 / 降息中」。

    Args
    ----
    rate_series: 時間序 % level(date index ascending),最少需 2 筆。
    lookback_months: 比較窗口,預設 6 月(對齊台灣央行季度理監事會節奏)。
    epsilon: 視為「持平」的容差(% pts),預設 0.05% = 5bp。

    Returns
    -------
    str: '🟢 升息中' / '⚪ 持平' / '🔴 降息中' / '⬜ 資料不足'
    """
    if rate_series is None:
        return '⬜ 資料不足'
    try:
        s = pd.Series(rate_series).dropna()
    except (TypeError, ValueError):
        return '⬜ 資料不足'
    if len(s) < 2:
        return '⬜ 資料不足'
    s_tail = s.tail(min(lookback_months, len(s)))
    delta = float(s_tail.iloc[-1]) - float(s_tail.iloc[0])
    if abs(delta) < epsilon:
        return '⚪ 持平'
    return '🟢 升息中' if delta > 0 else '🔴 降息中'


def calc_china_credit_impulse_proxy(m2_series: Optional[pd.Series],
                                    lag_months: int = 12) -> Optional[float]:
    """中國信貸脈衝 proxy:M2 YoY 與 N 月前 M2 YoY 的差(% pts)。

    真正信貸脈衝 = Δ(信貸/GDP),需社融存量 + GDP,無乾淨 FRED 來源;
    M2 YoY 變化是粗略貨幣寬鬆代理。對稱 Fund 端同名函式。

    Args
    ----
    m2_series: M2 YoY % 月頻時間序(date index ascending,**需已 YoY**)。
    lag_months: 比較期,預設 12 月。

    Returns
    -------
    float | None
        正值 = 12 月內 M2 加速(寬鬆中)、負值 = 緊縮中;
        資料不足 N+1 筆 → None(§1 不偽造)。
    """
    if m2_series is None:
        return None
    try:
        s = pd.Series(m2_series).dropna()
    except (TypeError, ValueError):
        return None
    if len(s) < lag_months + 1:
        return None
    cur = float(s.iloc[-1])
    prev = float(s.iloc[-(lag_months + 1)])
    return round(cur - prev, 3)


def calc_twd_trend(usdtwd_series: Optional[pd.Series],
                   window_days: int = 60) -> Optional[dict]:
    """USDTWD 60 日趨勢:回 latest / 60D MA / 斜率(% pts/月)。

    Args
    ----
    usdtwd_series: USD/TWD 日序列(數字越大 = 台幣越貶)。
    window_days: 滾動窗口,預設 60(約 2 個月)。

    Returns
    -------
    dict | None
        {
          'latest': float,                # 最新匯率
          'ma_60d': float | None,         # 60 日均線(資料不足回 None)
          'slope_per_month': float|None,  # 線性斜率 (TWD/USD per 月,正=台幣貶)
          'direction': str,               # '🔴 台幣貶' / '🟢 台幣升' / '⚪ 持平'
        }
        輸入無效回 None。
    """
    if usdtwd_series is None:
        return None
    try:
        s = pd.Series(usdtwd_series).dropna()
    except (TypeError, ValueError):
        return None
    if s.empty:
        return None
    latest = float(s.iloc[-1])
    out: dict = {
        'latest': round(latest, 4),
        'ma_60d': None,
        'slope_per_month': None,
        'direction': '⚪ 持平',
    }
    if len(s) < window_days:
        return out
    tail = s.tail(window_days)
    out['ma_60d'] = round(float(tail.mean()), 4)
    # 線性斜率(per trading day → per month ≈ 21 交易日)
    xs = list(range(len(tail)))
    ys = tail.values
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    if den == 0:
        return out
    slope_per_day = num / den
    slope_per_month = slope_per_day * 21
    out['slope_per_month'] = round(slope_per_month, 4)
    # 月斜率 > 0.1 (~0.3%) 算貶值方向;< -0.1 算升值
    if slope_per_month > 0.1:
        out['direction'] = '🔴 台幣貶'
    elif slope_per_month < -0.1:
        out['direction'] = '🟢 台幣升'
    return out
