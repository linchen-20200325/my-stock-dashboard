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

# 季末日對照（DataFrame 內「季度標籤 2024Q4」→「2024-12-31」用）
_QE_MAP = {'1': '03-31', '2': '06-30', '3': '09-30', '4': '12-31'}


def calc_traffic_light(
    mkt_info: Optional[dict],
    jingqi_info: Optional[dict],
    cl_data: Optional[dict],
    li_latest: Any,
) -> Optional[dict]:
    """根據當前數據計算紅綠燈狀態，回傳 dict。無數據時回傳 None。

    取代 tab_macro.render_tab_macro._calc_traffic_light closure。

    決策樹：
      1. 三來源全空 → None（由 placeholder 顯示等待）
      2. defense 觸發（score<2 且外資期貨大空單）或 health<40 → 🔴 空頭防禦
      3. regime=='bull' → 🟢 多頭積極
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
    _health  = round(
        _jqavg * 0.4 + min(_score / 5 * 100, 100) * 0.4 + (20 if _fnet > 0 else 0), 1
    )

    if _defense or _health < 40:
        _color, _icon  = '#f85149', '🔴'
        _label  = '空頭防禦｜降低部位'
        _action = '⛔ 大環境惡化，系統已啟動資金保護機制'
        _sub    = '建議持有現金，等待市場明確訊號，禁止追買任何個股'
    elif _regime == 'bull':
        _color, _icon  = '#3fb950', '🟢'
        _label  = '多頭市場｜積極操作'
        _action = '✅ 市場健康，籌碼乾淨，可積極尋找強勢標的'
        _sub    = '可積極尋找強勢標的，留意趨勢延續性'
    elif _regime in ('caution', 'bear'):
        _color, _icon  = '#f85149', '🔴'
        _label  = '保守防禦｜縮減部位'
        _action = '⛔ 市場走弱，建議縮減持股比例，等待多頭確認'
        _sub    = '降低風險暴露，避免新開倉，等待多頭重啟'
    else:
        _color, _icon  = '#d29922', '🟡'
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
    _conf = round(sum(_ok for _, _ok in _conf_sources) / 5 * 100)
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
