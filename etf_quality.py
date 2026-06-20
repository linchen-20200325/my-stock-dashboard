from data_config import CACHE_TTL
"""ETF ?芾ˊ?釭閰? ??4 ?????? 1-5 憿?

銝?鞈游??刻?蝑?瑽??冽??∪??API嚗???codebase 撌脫?鞈?嚗?
  - AUM 閬芋 30%嚗og10 scale嚗?00 ?? 皛踹?
  - 鞎餌??25%嚗0.3% 皛踹??1.5% ?嗅?
  - 畾?帘摰漲 25%嚗? 3Y 撟游漲? CV嚗0.15 皛踹??0.6 ?嗅?
  - Beta ????20%嚗帣-1|??.1 皛踹??帣-1|??.8 ?嗅?

閰??? rescale嚗撩銝???擗??飛銝??
"""
from __future__ import annotations
import datetime as _dt
import math

import pandas as pd
import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from etf_dashboard import (
    fetch_etf_info, fetch_etf_dividends, get_etf_expense_ratio_safe,
)

# ?? 甈?嚗? ???蜇 = 1.0嚗?????????????????????????????????
_WEIGHTS: dict[str, float] = {
    'aum':      0.30,
    'expense':  0.25,
    'yield_cv': 0.25,
    'beta':     0.20,
}

# ?? ???曉潘?皛踹? / ?嗅?嚗????????????????????????????????
# AUM in TWD嚗?e9 (10?? ??0嚗?e10 (100?? ??1
_AUM_LO_LOG = 9.0
_AUM_HI_LOG = 10.0
# Expense ratio嚗?.003 (0.3%) ??1嚗?.015 (1.5%) ??0
_EXP_HI = 0.003
_EXP_LO = 0.015
# Yield CV嚗?.15 ??1嚗?.6 ??0
_YCV_HI = 0.15
_YCV_LO = 0.6
# Beta deviation from 1嚗?.1 ??1嚗?.8 ??0
_BETA_HI = 0.1
_BETA_LO = 0.8


# ??????????????????????????????????????????????????????????????
# 4 ??pure 閰??賢?嚗?-1 瘚桅?嚗撩鞈???None嚗?
# ??????????????????????????????????????????????????????????????

def score_aum(aum: float | None) -> float | None:
    """AUM (?? ??0-1 ?og10 蝺改?10 ????0??00 ????1??""
    if aum is None or aum <= 0:
        return None
    _log = math.log10(float(aum))
    return max(0.0, min(1.0, (_log - _AUM_LO_LOG) / (_AUM_HI_LOG - _AUM_LO_LOG)))


def score_expense(expense_ratio: float | None) -> float | None:
    """鞎餌??瘥?敶Ｗ? 0.003=0.3%嚗? 0-1 ??雿?憟賬?""
    if expense_ratio is None or expense_ratio < 0:
        return None
    return max(0.0, min(1.0, (_EXP_LO - float(expense_ratio)) / (_EXP_LO - _EXP_HI)))


def _yield_cv(divs: pd.Series | None) -> float | None:
    """餈?3Y 撟游漲?霈靽嚗td/mean嚗?璅?銝雲??None???helper??""
    if divs is None or divs.empty:
        return None
    _cutoff = pd.Timestamp(_dt.date.today() - _dt.timedelta(days=3 * 365))
    _recent = divs[divs.index >= _cutoff]
    if len(_recent) < 4:
        return None
    _by_year = _recent.groupby(_recent.index.year).sum()
    if len(_by_year) < 2:
        return None
    _mean = float(_by_year.mean())
    if _mean <= 0:
        return None
    return float(_by_year.std() / _mean)


def score_yield_cv(divs: pd.Series | None) -> float | None:
    """畾?帘摰漲嚗V ??0.15?? / ??0.6??嚗???頞喳? None??""
    _cv = _yield_cv(divs)
    if _cv is None:
        return None
    return max(0.0, min(1.0, (_YCV_LO - _cv) / (_YCV_LO - _YCV_HI)))


def score_beta(beta: float | None) -> float | None:
    """Beta ???改?|帣-1| 頞?頞末??""
    if beta is None:
        return None
    _dev = abs(float(beta) - 1.0)
    return max(0.0, min(1.0, (_BETA_LO - _dev) / (_BETA_LO - _BETA_HI)))


# ??????????????????????????????????????????????????????????????
# 銝餃???compute_etf_quality()
# ??????????????????????????????????????????????????????????????

@st.cache_data(ttl=CACHE_TTL["daily_snapshot"], show_spinner=False)
def compute_etf_quality(ticker: str) -> dict:
    """4 ?????? ETF ?釭閰???

    Returns
    -------
    dict
      ??嚗stars: 1-5, score: float, factors: {...}, weakest: str, coverage: float}
      憭望?嚗stars: None, _err: str}
    """
    try:
        _info = fetch_etf_info(ticker) or {}
        _aum = _info.get('totalAssets')
        _beta = _info.get('beta') or _info.get('beta3Year')
        _exp = get_etf_expense_ratio_safe(ticker)
        _divs = fetch_etf_dividends(ticker)
    except Exception as _e:
        return {'stars': None, '_err': f'??憭望? {type(_e).__name__}'}
    # _yield_cv ?芰? 1 甈∴?score_yield_cv ?舐?頧?銝???groupby
    _ycv_raw = _yield_cv(_divs)
    _factors = {
        'aum':      {'val': _aum,  'score': score_aum(_aum)},
        'expense':  {'val': _exp,  'score': score_expense(_exp)},
        'yield_cv': {'val': round(_ycv_raw, 3) if _ycv_raw is not None else None,
                     'score': score_yield_cv(_divs)},
        'beta':     {'val': _beta, 'score': score_beta(_beta)},
    }
    # ?? ?株艘??銝嚗alid_w / weighted_score / weakest 銝甈∟?摰???
    _valid_w = 0.0
    _weighted = 0.0
    _valid_pairs: list[tuple[str, float]] = []
    for _k, _v in _factors.items():
        _s = _v['score']
        if _s is None:
            continue
        _w = _WEIGHTS[_k]
        _valid_w += _w
        _weighted += _w * _s
        _valid_pairs.append((_k, _s))
    if _valid_w <= 0:
        return {'stars': None, '_err': '4 ???函撩鞈?', 'factors': _factors}
    _score = _weighted / _valid_w
    _weakest = min(_valid_pairs, key=lambda x: x[1])[0]
    # 5 憿???
    if _score >= 0.80:
        _stars = 5
    elif _score >= 0.65:
        _stars = 4
    elif _score >= 0.50:
        _stars = 3
    elif _score >= 0.35:
        _stars = 2
    else:
        _stars = 1
    return {
        'stars': _stars,
        'score': round(_score, 3),
        'factors': _factors,
        'weakest': _weakest,
        'coverage': round(_valid_w, 2),
    }


# ??????????????????????????????????????????????????????????????
# UI Helper
# ??????????????????????????????????????????????????????????????

_FACTOR_NAMES = {
    'aum':      'AUM 閬芋',
    'expense':  '鞎餌??,
    'yield_cv': '畾?帘摰漲',
    'beta':     'Beta ????,
}


def _fmt_factor_val(key: str, val) -> str:
    if val is None:
        return 'N/A'
    if key == 'aum':
        return f'{val / 1e8:.1f} ??
    if key == 'expense':
        return f'{val * 100:.2f}%'
    if key == 'yield_cv':
        return f'CV {val:.2f}'
    if key == 'beta':
        return f'帣 {val:.2f}'
    return str(val)


def render_quality_badge(quality: dict | None) -> None:
    """皜脫? ETF ?釭敺賜?嚗??渡?嚗?蝑?+ 4 ???? + ?撘梢??內嚗?""
    if quality is None or quality.get('stars') is None:
        _msg = quality.get('_err', '?芾?蝑?) if quality else '?芾?蝑?
        st.caption(f'???釭閰?嚗_msg}')
        return
    _stars = quality['stars']
    _score = quality['score']
    _cov = quality['coverage']
    _color = (TRAFFIC_GREEN if _stars >= 4 else
              TRAFFIC_YELLOW if _stars == 3 else TRAFFIC_RED)
    _star_str = '?? * _stars + '?? * (5 - _stars)
    st.markdown(
        f"#### 潃??釭閰??"
        f"<span style='color:{_color};font-weight:700;font-size:22px'>{_star_str}</span>?"
        f"<span style='color:#8b949e;font-size:13px'>"
        f"{_stars}/5 ??蝬???{_score:.2f}嚚?????{_cov * 100:.0f}%</span>",
        unsafe_allow_html=True)
    _cols = st.columns(4)
    for _i, (_k, _name) in enumerate(_FACTOR_NAMES.items()):
        _f = quality['factors'][_k]
        with _cols[_i]:
            _s = _f['score']
            if _s is None:
                _icon = '??
                _scol = '#8b949e'
                _bar = 0
            else:
                _icon = ('?' if _s >= 0.7 else
                         '?' if _s >= 0.4 else '?')
                _scol = (TRAFFIC_GREEN if _s >= 0.7 else
                         TRAFFIC_YELLOW if _s >= 0.4 else TRAFFIC_RED)
                _bar = int(_s * 100)
            _val_str = _fmt_factor_val(_k, _f['val'])
            st.markdown(
                f"<div style='border:1px solid #30363d;border-radius:6px;"
                f"padding:8px;background:#0d1117'>"
                f"<div style='color:#8b949e;font-size:11px'>{_icon} {_name}</div>"
                f"<div style='color:{_scol};font-weight:700;font-size:14px;margin-top:2px'>"
                f"{_val_str}</div>"
                f"<div style='background:#30363d;height:4px;border-radius:2px;"
                f"margin-top:6px'>"
                f"<div style='background:{_scol};height:100%;width:{_bar}%;"
                f"border-radius:2px'></div>"
                f"</div></div>", unsafe_allow_html=True)
    if quality.get('weakest'):
        st.caption(
            f"? ?撘梢?嚗?*{_FACTOR_NAMES[quality['weakest']]}**"
            f"嚗??迨???舀???蝑?")

