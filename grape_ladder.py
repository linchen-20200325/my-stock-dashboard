from data_config import CACHE_TTL
"""?∟?銝脤??舀?嚗rape Ladder嚗?擃??ETF ??蝯??雿喳?

?銝??斗?遢???⊥ ETF 蝯???嚗?瘥??賣??臬??

?拙???
- recommend_income_ladder(): 敺?etf_categories['擃??] 10 瑼???撠?ETF cover ?憭?
- evaluate_income_ladder(): 閰摯雿輻?撓?亦????遢閬????暸?瘚?

鞈?皞?yfinance via etf_dashboard.fetch_etf_dividends嚗??cache嚗?
"""
from __future__ import annotations
import datetime as _dt
from itertools import combinations
import pandas as pd
import streamlit as st

from etf_categories import ETF_PEER_GROUPS
from etf_dashboard import fetch_etf_dividends
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED

# ?? Constants ?????????????????????????????????????????????????
LOOKBACK_DAYS = 400         # ?? ~13 ???荔?蝯行???ETF ?嗥撩銝?楨銵?
MAX_COMBO_SIZE = 5          # ?游???銝?
MIN_PAYMENTS_FOR_VALID = 2  # ?喳? 2 甈⊿??舀?蝞?鞈???
TARGET_MONTHS_FULL = 12

# ?? ETF 皜嚗lider ??賊??剁?
_MONTHLY_ETFS = {'00929.TW', '00940.TW', '00939.TW'}


# ??????????????????????????????????????????????????????????????
# Pure Logic嚗 Streamlit ?臭??剁??臬皜穿?
# ??????????????????????????????????????????????????????????????

@st.cache_data(ttl=CACHE_TTL["daily_snapshot"], show_spinner=False)
def get_pay_months(ticker: str, lookback_days: int = LOOKBACK_DAYS) -> set[int]:
    """?? ticker 餈?lookback_days ?批祕??舀?隞賡???1-12嚗?

    Returns
    -------
    set[int]  靘?{1, 4, 7, 10}嚗???頞單???憭望???set()??
    """
    _divs = fetch_etf_dividends(ticker)
    if _divs is None or _divs.empty:
        return set()
    _cutoff = pd.Timestamp(_dt.date.today() - _dt.timedelta(days=lookback_days))
    _recent = _divs[_divs.index >= _cutoff]
    if len(_recent) < MIN_PAYMENTS_FOR_VALID:
        return set()
    return set(_recent.index.month.tolist())


@st.cache_data(ttl=CACHE_TTL["daily_snapshot"], show_spinner=False)
def get_avg_monthly_cash(ticker: str, shares: int = 1000) -> dict[int, float]:
    """{?遢: 閰脫?撟喳?瘥? ? shares}??

    Returns
    -------
    dict[int, float]  蝻箸?隞賭??箇??key 銝准?
    """
    _divs = fetch_etf_dividends(ticker)
    if _divs is None or _divs.empty:
        return {}
    _cutoff = pd.Timestamp(_dt.date.today() - _dt.timedelta(days=LOOKBACK_DAYS))
    _recent = _divs[_divs.index >= _cutoff]
    if _recent.empty:
        return {}
    _by_month = _recent.groupby(_recent.index.month).mean()
    return {int(_m): round(float(_v) * shares, 2) for _m, _v in _by_month.items()}


def _score_combo(combo: tuple, month_map: dict[str, set[int]]) -> tuple[int, int]:
    """(閬??, -??? ??tuple comparison ??閬???瘥??∪???""
    _covered = set().union(*(month_map[t] for t in combo))
    return (len(_covered), -len(combo))


def recommend_income_ladder(
    candidates: list[str] | None = None,
    target_months: int = TARGET_MONTHS_FULL,
    max_etfs: int = 4,
    min_etfs: int = 1,
    exclude_monthly: bool = False,
    min_stars: int = 1,
) -> dict:
    """?游? itertools.combinations ???雿喟???

    Parameters
    ----------
    min_stars : int
        ?雿?鞈芣?蝑?瞈暸?瑼鳴?1-5嚗? = 銝?瞈橘?3+ ??etf_quality ?????

    Returns
    -------
    dict
      best_combo, covered_months, missing_months, coverage_pct,
      month_map, all_candidates_evaluated, skipped_tickers, low_quality, alternatives
    """
    _cands = list(candidates) if candidates else list(ETF_PEER_GROUPS.get('擃??, []))
    if exclude_monthly:
        _cands = [t for t in _cands if t not in _MONTHLY_ETFS]
    # ?釭???蕪嚗in_stars >= 2 ?????踹? 1=銝?瞈暹??賣?嚗?
    _low_quality: list[str] = []
    if min_stars >= 2:
        try:
            from etf_quality import compute_etf_quality
            _filtered: list[str] = []
            for _t in _cands:
                _q = compute_etf_quality(_t)
                _s = _q.get('stars') if _q else None
                if _s is None or _s >= min_stars:
                    # ?芾?蝑????踹?鞈?蝻箸?隤斗捏嚗?
                    _filtered.append(_t)
                else:
                    _low_quality.append(_t)
            _cands = _filtered
        except Exception as _e_q:
            print(f'[grape_ladder/min_stars] ??{type(_e_q).__name__}: {_e_q}')
    # ??瑼??舀?隞踝?蝛?set 閬?∟???
    _month_map: dict[str, set[int]] = {}
    _skipped: list[str] = []
    for _t in _cands:
        _m = get_pay_months(_t)
        if _m:
            _month_map[_t] = _m
        else:
            _skipped.append(_t)
    _valid = list(_month_map.keys())
    if len(_valid) < min_etfs:
        return {
            'best_combo': [], 'covered_months': set(), 'missing_months': set(range(1, 13)),
            'coverage_pct': 0.0, 'month_map': {},
            'all_candidates_evaluated': 0, 'skipped_tickers': _skipped,
            'low_quality': _low_quality, 'alternatives': [],
            '_err': f'?? ETF ??{len(_valid)} 瑼?撠 min_etfs={min_etfs}',
        }
    _max_k = min(max_etfs, len(_valid), MAX_COMBO_SIZE)
    _best_score: tuple[int, int] | None = None
    _best_combo: tuple = ()
    _evaluated = 0
    _all_top: list[tuple] = []  # ??蝯?
    for _k in range(min_etfs, _max_k + 1):
        for _combo in combinations(_valid, _k):
            _evaluated += 1
            _sc = _score_combo(_combo, _month_map)
            if _best_score is None or _sc > _best_score:
                _best_score = _sc
                _best_combo = _combo
                _all_top = [_combo]
            elif _sc == _best_score:
                _all_top.append(_combo)
    _best_covered = set().union(*(_month_map[t] for t in _best_combo))
    _missing = set(range(1, target_months + 1)) - _best_covered
    # 瘥? ???芸嗾瑼?
    _by_month: dict[int, list[str]] = {}
    for _t in _best_combo:
        for _m in _month_map[_t]:
            _by_month.setdefault(_m, []).append(_t)
    # alternatives嚗 best 憭???3 ??
    _alts = [list(_c) for _c in _all_top if _c != _best_combo][:3]
    return {
        'best_combo': list(_best_combo),
        'covered_months': _best_covered,
        'missing_months': _missing,
        'coverage_pct': round(len(_best_covered) / target_months * 100, 1),
        'month_map': _by_month,
        'all_candidates_evaluated': _evaluated,
        'skipped_tickers': _skipped,
        'low_quality': _low_quality,
        'alternatives': _alts,
    }


def evaluate_income_ladder(
    tickers: list[str],
    shares_map: dict[str, int] | None = None,
) -> dict:
    """閰摯雿輻?撓?亦????遢閬???+ 瘥??暸?瘚?

    Returns
    -------
    dict
      tickers, covered_months, missing_months, month_etfs,
      monthly_cashflow (1..12 摰 key), annual_cashflow, invalid_tickers
    """
    if not tickers:
        return {'_err': '隢撠撓??1 瑼?ETF', 'tickers': [], 'invalid_tickers': []}
    # ?駁?靽?
    _seen: set[str] = set()
    _clean: list[str] = []
    for _t in tickers:
        _t = (_t or '').strip().upper()
        if _t and _t not in _seen:
            _seen.add(_t)
            _clean.append(_t)
    # ?啗隞?Ⅳ撽?
    _valid: list[str] = []
    _invalid: list[str] = []
    for _t in _clean:
        if _t.endswith('.TW') or _t.endswith('.TWO'):
            _valid.append(_t)
        else:
            _invalid.append(_t)
    _shares = shares_map or {}
    _month_etfs: dict[int, list[str]] = {}
    _monthly_cf: dict[int, float] = {m: 0.0 for m in range(1, 13)}
    for _t in _valid:
        _m_set = get_pay_months(_t)
        for _m in _m_set:
            _month_etfs.setdefault(_m, []).append(_t)
        _cash = get_avg_monthly_cash(_t, shares=_shares.get(_t, 1000))
        for _m, _v in _cash.items():
            _monthly_cf[_m] = round(_monthly_cf.get(_m, 0.0) + _v, 2)
    _covered = {m for m, lst in _month_etfs.items() if lst}
    _missing = set(range(1, 13)) - _covered
    return {
        'tickers': _valid,
        'covered_months': _covered,
        'missing_months': _missing,
        'month_etfs': _month_etfs,
        'monthly_cashflow': _monthly_cf,
        'annual_cashflow': round(sum(_monthly_cf.values()), 2),
        'invalid_tickers': _invalid,
    }


# ??????????????????????????????????????????????????????????????
# UI Helpers
# ??????????????????????????????????????????????????????????????

def _render_month_grid(month_etfs: dict[int, list[str]], missing: set[int]) -> None:
    """12 ?遢 3?4 grid嚗府??????蝬? + ETF chips嚗撩????蝝? ??""
    _MONTH_NAMES = ['銝??, '鈭?', '銝?', '??', '鈭?', '?剜?',
                    '銝?', '?急?', '銋?', '??', '????, '????]
    for _row in range(3):
        _cols = st.columns(4)
        for _i in range(4):
            _m = _row * 4 + _i + 1
            with _cols[_i]:
                _etfs = month_etfs.get(_m, [])
                _has = bool(_etfs)
                _bg = '#0d2818' if _has else '#2d0e0e'
                _border = TRAFFIC_GREEN if _has else TRAFFIC_RED
                _icon = '?? if _has else '??
                _content = ('<br>'.join(
                    f"<span style='background:#1f6feb22;color:#79c0ff;"
                    f"padding:2px 6px;border-radius:8px;font-size:10px;"
                    f"margin:2px 0;display:inline-block'>{_e}</span>"
                    for _e in _etfs)
                    if _has else '<span style="color:#8b949e">??ETF</span>')
                st.markdown(
                    f"<div style='background:{_bg};border:1px solid {_border};"
                    f"border-radius:6px;padding:8px;min-height:80px'>"
                    f"<div style='color:#e6edf3;font-weight:700;font-size:12px'>"
                    f"{_icon} {_MONTH_NAMES[_m - 1]}</div>"
                    f"<div style='margin-top:4px;line-height:1.6'>{_content}</div>"
                    f"</div>", unsafe_allow_html=True)


def _render_propose_subtab() -> None:
    """? 蝟餌絞?降 sub-tab"""
    st.markdown('##### ? 敺??⊥ 10 瑼???豢?雿喟???)
    _c1, _c2, _c3 = st.columns([1, 1, 1])
    with _c1:
        _max_etfs = st.slider('?憭?ETF ??, 1, 5, value=4, key='_grape_max_etfs')
    with _c2:
        _min_stars = st.slider('?雿?鞈芣?蝑?潃?, 1, 5, value=3,
                               key='_grape_min_stars',
                               help='1 = 銝?瞈橘?3+ ??etf_quality 4 ?????雿?鞈?ETF')
    with _c3:
        _excl = st.checkbox('???擃嚗?0929/00940/00939嚗?,
                            value=False, key='_grape_excl_monthly')
    if not st.button('?? ???降', key='_grape_btn_propose', type='primary'):
        st.caption('暺??寞???遣霅啁???霅啣????岫???1~N 瑼????憭?C(10,5)=252 蝔殷???)
        return
    with st.spinner('???雿喟??葉?佗?< 10 蝘?'):
        _res = recommend_income_ladder(
            max_etfs=_max_etfs, min_etfs=1,
            exclude_monthly=_excl, min_stars=_min_stars)
    if _res.get('_err'):
        st.error(f'??{_res["_err"]}')
        return
    _combo = _res['best_combo']
    _cover_pct = _res['coverage_pct']
    _missing = sorted(_res['missing_months'])
    if _cover_pct >= 100:
        st.success(f'????{len(_combo)} 瑼?cover ?券 12 ??嚗???{", ".join(_combo)}')
    else:
        st.warning(f'?? ??{len(_combo)} 瑼?cover {len(_res["covered_months"])}/12 ??'
                   f'({_cover_pct}%)嚗撩?遢嚗_missing}')
    _m1, _m2, _m3, _m4 = st.columns(4)
    _m1.metric('閬??', f'{len(_res["covered_months"])}/12')
    _m2.metric('蝻箏', len(_missing))
    _m3.metric('ETF ??, len(_combo))
    _m4.metric('?岫蝯?', _res['all_candidates_evaluated'])
    st.markdown('##### ?? 12 ?遢閬???)
    _render_month_grid(_res['month_map'], _res['missing_months'])
    if _res.get('skipped_tickers'):
        st.caption(f'???仿?嚗??航???頞喉?嚗", ".join(_res["skipped_tickers"])}')
    if _res.get('low_quality'):
        st.caption(f'潃??釭???蕪嚗? {_min_stars}???嚗", ".join(_res["low_quality"])}')
    if _res.get('alternatives'):
        st.markdown('##### ?? ??甈∪蝯?')
        _alt_rows = [{'蝯?': ', '.join(_a), 'ETF ??: len(_a)}
                     for _a in _res['alternatives']]
        st.dataframe(pd.DataFrame(_alt_rows),
                     use_container_width=True, hide_index=True)


def render_grape_ladder(gemini_fn=None) -> None:
    """Streamlit UI 撠??亙 ??銝餉???? 蝟餌絞?降嚗?擃??10 瑼???豢?雿喟?????

    閮鳴?閰摯雿???∠????臬?撣??賢歇銝??etf_tab_portfolio ?????交? ? 撟游漲?暸?瘚?隡啜?PR #6 ?駁?嚗?
    """
    st.markdown('### ?? ?∟?銝脤??舀?')
    st.caption('??????ETF???耦??葡??霈????賣??臬??
               '?砍?敺??⊥ 10 瑼???豢?雿喟???'
               '?交???Ｘ???????嚗?閬??嫘????交? ? 撟游漲?暸?瘚?隡啜?)
    with st.expander('? ?∟?銝脤??舀??臭?暻潘??獐?剁?', expanded=False):
        st.markdown(
            '**?詨?璁艙**嚗????⊥ ETF ???箏?**??遢**嚗? 0056 ??1/4/7/10 ??0878 ??2/5/8/11 ?佗???
            '?株眺銝瑼???銝撟游?嗾甈～???葉嚗?*?餅??剝????舀?隞賭?鋆??豢?**嚗停?賭葡??葡?? '
            '**撟曆?瘥??賣??臬撣?*嚗??撟單??n\n'
            '**?獐???寧???*嚗n'
            '- **閬??遢/閬???*嚗???撟?12 ??銝剜?撟曉????唳嚗??亥? 12 頞末嚗n'
            '- **蝻箸??遢**嚗撟曉?瘝 ???臬??曇府???舐? ETF 鋆??n'
            '- **?釭???蕪**嚗???etf_quality 4 ???雿?鞈?ETF嚗??鞎瑕???n\n'
            '? ?拙??唾?**蝛拙????**?????隡?????? ??鞈粹 ??畾??雿?寡??游?嚗竟?航??研?隞???舐蜇?梢??
        )
    _render_propose_subtab()

