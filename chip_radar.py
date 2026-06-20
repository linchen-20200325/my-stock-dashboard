from data_config import CACHE_TTL
"""chip_radar.py ???? ??蝐Ⅳ憭扳?琿?嚗撱箇?脩?嚗?

鞈?靘?嚗orway.twsthr.info `StockHolders.aspx?stock={隞??}`嚗?靽?⊥??銵剁?瘥望?堆?

閮剛???
========
- ???嚗粥?Ｘ? `proxy_helper.fetch_url()`嚗AS Squid Proxy ???芸????湧?+
  3 甈⊿?閰?+ 20s timeout + Storm Shield 300s 敹怠?嚗?憭??冽? User-Agent ?脩??
- 閫??嚗pandas.read_html` ???”????**?芷??*?券??萄??菜葫?之?嗆?靘?/ ??鈭箸 /
  ?交???雿?銝′蝺刻?撘望???蝬脩??寧?銋?⊿?摮暑嚗?
- 敹怠?嚗@st.cache_data(ttl=CACHE_TTL["daily_snapshot"])` 銝?乩?????銝剔匱蝡???
- ?脣?嚗遙雿仃??敺??征 df + ?航炊閮 + 閮箸鞈???UI 蝡舫＊蝷箸?蝷綽?**銝?靘???甇餉艘??*??
- 閮箸嚗???read_html ??銵冽蝯?嚗hape / columns / ?嗾??嚗蝡航?銝甈∪??
  霈蝙?刻?????啣祕??雿?閬????芷?圾??移皞圾??

?憟?嚗ict嚗ache-safe ??銝?鞈?DataFrame.attrs ?典翰??摮暑嚗?
    {
        'df':        DataFrame嚗?雿??交? / 憭扳瘥? / ??鈭箸嚗仃?蝛綽?,
        'err':       str嚗?'=??嚗?
        'tables':    list[dict]嚗那?瘀?瘥?read_html 銵冽??shape/columns/preview嚗?
        'html_head': str嚗ead_html 憭望?????HTML ??挾嚗?
    }
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

TWSTHR_URL = 'https://norway.twsthr.info/StockHolders.aspx?stock={ticker}'

_UA_POOL = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 '
    '(KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
)


# ??????????????????????????????????????????????????????????????????????????????
# 閫??頛嚗??賢?嚗?
# ??????????????????????????????????????????????????????????????????????????????
def _flatten_cols(df: pd.DataFrame) -> pd.DataFrame:
    """?文像 MultiIndex 甈??撅文?銝莎?銝血?剖偏蝛箇??""
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [
            ' '.join(str(x) for x in tup if str(x) not in ('nan', 'None')).strip()
            for tup in out.columns
        ]
    else:
        out.columns = [str(c).strip() for c in out.columns]
    return out


def _to_num(v) -> float:
    """??'12.3%' / '1,234' / ' 56 ' 銋?摮葡頧 float嚗瘜圾?? NaN??""
    import re as _re
    s = str(v).strip()
    if not s or s.lower() in ('nan', 'none', '-', '--'):
        return float('nan')
    s = _re.sub(r'[^0-9.\-]', '', s)
    if s in ('', '-', '.', '-.'):
        return float('nan')
    try:
        return float(s)
    except ValueError:
        return float('nan')


def _find_col(cols: list[str], keywords: tuple[str, ...]) -> str | None:
    for c in cols:
        if any(k in str(c) for k in keywords):
            return c
    return None


def _find_major_col(cols: list[str]) -> str | None:
    """憭扳???靘?嚗???憭扳?摮?+ 瘥?/??% 摮見嚗?????嗆活??""
    _major = ('憭扯??, '憭扳', '400撘?, '1000撘?, '?撐', '?葉')
    _ratio = ('瘥?', '??, '%', '??, '雿?, '?曉?瘥?, '?曉?暺?)
    # pass1嚗之??+ 瘥?
    for c in cols:
        cl = str(c)
        if any(m in cl for m in _major) and any(r in cl for r in _ratio):
            return c
    # pass2嚗?憭扳?摮??航撠望瘥?甈?
    return _find_col(cols, _major)


def _parse_date_series(s: pd.Series) -> pd.Series:
    """?⊿????頧?datetime嚗?銝?祈圾???賭葉??? %Y%m%d嚗??詨?嚗?""
    raw = s.astype(str).str.strip()
    out = pd.to_datetime(raw, errors='coerce')
    if out.notna().sum() < max(1, len(raw)) * 0.5:
        digits = raw.str.replace(r'[^0-9]', '', regex=True)
        out2 = pd.to_datetime(digits, format='%Y%m%d', errors='coerce')
        if out2.notna().sum() > out.notna().sum():
            out = out2
    return out


def _adaptive_parse(tables: list[pd.DataFrame]) -> pd.DataFrame:
    """敺?read_html ???”?潔葉???甈????摨?銝撘萎蒂?賭?甈?

    ?甈?嚗??/ 憭扳瘥? / ??鈭箸嚗撩??鋆?NaN嚗??曆??啣?蝛?DataFrame??
    """
    best = None
    best_score = -1.0
    for t in tables:
        if t is None or getattr(t, 'empty', True) or t.shape[1] < 2:
            continue
        ft = _flatten_cols(t)
        # read_html ?芣??啗”?剜?甈??舀?貊揣撘?'0','1',?佗????函洵銝?銵券
        # 嚗wsthr ??摨?銵典甇斗?瘜??祕甈??????/ >400撘萄之?⊥???曉?瘥擐?嚗?
        if len(ft) >= 2 and all(str(c).strip().isdigit() for c in ft.columns):
            ft = ft.copy()
            ft.columns = [str(x).strip() for x in ft.iloc[0].tolist()]
            ft = ft.iloc[1:].reset_index(drop=True)
        cols = list(ft.columns)
        c_major = _find_major_col(cols)
        c_retail = _find_col(cols, ('?⊥鈭箸', '??', '50撘?, '鈭箸'))
        if not (c_major or c_retail):
            continue
        c_date = _find_col(cols, ('?交?', '??, 'date', '??')) or cols[0]
        # ???交?瘥?嚗?????璅???????銵????⊥?????◤憯??
        _date_valid = 0.0
        if c_date in ft.columns:
            _dts = _parse_date_series(ft[c_date])
            _date_valid = float(_dts.notna().mean()) if len(_dts) else 0.0
        # 閰?嚗??????) > 憭扳瘥? > ??鈭箸 > ?
        score = (_date_valid * 3.0 + (2.0 if c_major else 0)
                 + (1.0 if c_retail else 0) + min(len(ft), 300) / 1000.0)
        if score > best_score:
            best_score = score
            best = (ft, c_date, c_major, c_retail)

    if best is None:
        return pd.DataFrame()

    ft, c_date, c_major, c_retail = best
    out = pd.DataFrame()
    out['?交?'] = _parse_date_series(ft[c_date]) if c_date in ft.columns else pd.NaT
    out['憭扳瘥?'] = ft[c_major].map(_to_num) if c_major else float('nan')
    out['??鈭箸'] = ft[c_retail].map(_to_num) if c_retail else float('nan')

    # 皜?嚗????潮蝻箇????交?蝻箇???銝?
    out = out.dropna(how='all', subset=['憭扳瘥?', '??鈭箸'])
    if out['?交?'].notna().any():
        out = out.dropna(subset=['?交?']).sort_values('?交?')
    out = out.reset_index(drop=True)
    return out


def _table_diag(tables: list[pd.DataFrame]) -> list[dict]:
    """憯葬?敹怠????那?瑞?瑽?shape / columns / ??5 ????""
    diag = []
    for i, t in enumerate(tables):
        try:
            ft = _flatten_cols(t)
            diag.append({
                'idx': i,
                'shape': list(t.shape),
                'columns': [str(c) for c in ft.columns][:30],
                'preview': ft.head(5),
            })
        except Exception:
            diag.append({'idx': i, 'shape': list(getattr(t, 'shape', [0, 0])),
                         'columns': [], 'preview': pd.DataFrame()})
    return diag


# ??????????????????????????????????????????????????????????????????????????????
# ?詨???嚗st.cache_data ????dict嚗ache-safe嚗?
# ??????????????????????????????????????????????????????????????????????????????
@st.cache_data(ttl=CACHE_TTL["daily_snapshot"], show_spinner=False)
def fetch_chip_concentration(ticker: str) -> dict:
    """??靽甈???”銝西?拇?閫???仃??蝛?df + ?航炊閮嚗???憭???""
    import io as _io
    import random as _rnd

    _empty = {'df': pd.DataFrame(), 'err': '', 'tables': [], 'html_head': ''}

    _tk = ''.join(c for c in str(ticker) if c.isalnum()).strip()
    if not _tk:
        _empty['err'] = '?∠巨隞???箇征'
        return _empty

    _url = TWSTHR_URL.format(ticker=_tk)
    try:
        from proxy_helper import fetch_url
        _resp = fetch_url(_url, headers={'User-Agent': _rnd.choice(_UA_POOL)},
                          timeout=15, attempts=3)
    except Exception as _fe:
        _empty['err'] = f'???靘?嚗歇?岫嚗?{type(_fe).__name__}: {_fe}'
        return _empty

    if _resp is None:
        _empty['err'] = 'NAS 隞??????憭望?嚗?閰?3 甈∪??征嚗?
        return _empty
    if getattr(_resp, 'status_code', 0) != 200:
        _empty['err'] = f'HTTP ??200嚗tatus={getattr(_resp, "status_code", None)}嚗?蝬脩?/隞???啣虜'
        return _empty

    # ?? 閫?Ⅳ嚗? .text嚗??剖??岫憭楊蝣潘???
    try:
        _html = _resp.text or ''
        if len(_html) < 200 and getattr(_resp, 'content', None):
            for _enc in ('utf-8', 'big5', 'cp950'):
                try:
                    _html = _resp.content.decode(_enc)
                    break
                except Exception:
                    continue
    except Exception:
        _empty['err'] = '???批捆閫?Ⅳ憭望?'
        return _empty

    if not _html or len(_html) < 50:
        _empty['err'] = '???批捆?箇征????
        return _empty

    # ?? read_html ??
    try:
        _tables = pd.read_html(_io.StringIO(_html))
    except ValueError:
        _empty['err'] = 'pandas.read_html ?券??Ｘ銝隞颱? HTML 銵冽嚗雯蝡?賣?????航炊??'
        _empty['html_head'] = _html[:600]
        return _empty
    except Exception as _pe:
        _empty['err'] = f'read_html 靘?嚗type(_pe).__name__}: {_pe}'
        _empty['html_head'] = _html[:600]
        return _empty

    if not _tables:
        _empty['err'] = 'read_html ?蝛箸???
        _empty['html_head'] = _html[:600]
        return _empty

    _parsed = _adaptive_parse(_tables)
    _diag = _table_diag(_tables)
    _err = '' if not _parsed.empty else \
        '?曉銵冽雿瘜儘霅之?嗆?靘?/ ??鈭箸??雿???隢????寡那?琿?輻?撖阡?甈?蝯?'
    return {'df': _parsed, 'err': _err, 'tables': _diag, 'html_head': ''}


# ??????????????????????????????????????????????????????????????????????????????
# Streamlit UI
# ??????????????????????????????????????????????????????????????????????????????
def _plot_chip(df: pd.DataFrame, ticker: str) -> None:
    """Plotly ??Y 頠賂?撌???鈭箸(bar)?=憭扳瘥?(line)??""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    _fig = make_subplots(specs=[[{'secondary_y': True}]])
    _has_retail = df['??鈭箸'].notna().any()
    _has_major = df['憭扳瘥?'].notna().any()
    _x = df['?交?'] if df['?交?'].notna().any() else list(range(len(df)))

    if _has_retail:
        _fig.add_trace(
            go.Bar(x=_x, y=df['??鈭箸'], name='???鈭箸',
                   marker_color='#4a9eff', opacity=0.55),
            secondary_y=False)
    if _has_major:
        _fig.add_trace(
            go.Scatter(x=_x, y=df['憭扳瘥?'], name='憭扳?瘥? (%)',
                       mode='lines+markers',
                       line=dict(color='#ff6b6b', width=2)),
            secondary_y=True)

    _fig.update_layout(
        title=f'{ticker} ??蝐Ⅳ??嚗?嗡犖??vs 憭扳瘥?嚗?,
        height=440, hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(t=60, b=40, l=10, r=10))
    _fig.update_yaxes(title_text='???鈭箸', secondary_y=False)
    _fig.update_yaxes(title_text='憭扳?瘥? (%)', secondary_y=True)
    st.plotly_chart(_fig, use_container_width=True)


def _render_diag(result: dict) -> None:
    """閫??閮箸?Ｘ嚗ead_html ??銵冽蝯?嚗??脩垢撠?甈?嚗?""
    with st.expander('? 閫??閮箸嚗ead_html ??蝯?嚗?, expanded=False):
        if result.get('html_head'):
            st.caption('HTML ??挾嚗ead_html 憭望?????嚗?)
            st.code(result['html_head'][:600])
        _tables = result.get('tables') or []
        if not _tables:
            st.info('?∪?憪”?潸???憭??舫???挾撠勗仃???芷脣 read_html嚗?)
            return
        st.caption(f'read_html ?梯圾? **{len(_tables)}** ?”?潘?')
        for _t in _tables:
            st.markdown(f"**銵?#{_t['idx']}** ??shape = {tuple(_t['shape'])}")
            if _t.get('columns'):
                st.write('甈?嚗?, _t['columns'])
            _pv = _t.get('preview')
            if isinstance(_pv, pd.DataFrame) and not _pv.empty:
                st.dataframe(_pv, use_container_width=True, hide_index=True)


def render_chip_radar(ticker: str = '') -> str:
    """?? ??蝐Ⅳ憭扳?琿???

    ticker ?勗?怎垢嚗 tab 銝颱誨蝣?sid2嚗葆?伐?銝??芸遣頛詨獢?
    ?銝畾萇策?I 擐葉憿批?蝮賜????函?蝐Ⅳ??摮葡嚗鞈???''嚗?
    """
    st.markdown('### ?? ??蝐Ⅳ憭扳?琿?')
    st.caption('鞈?靘?嚗orway.twsthr.info ???嗉甈???”嚗??望?堆?嚗銝?隞?Ⅳ?芸??亥岷??)

    _tk = ''.join(c for c in str(ticker) if c.isalnum())
    if not _tk:
        st.info('? 隢?銝頛詨?隞?Ⅳ銝艾??亙??游????ㄐ??＊蝷箄府瑼?靽?蝣潦?)
        return ''

    with st.spinner(f'?? {_tk} ???⊥??銵其葉?佗?NAS 隞?? + 3 甈⊿?閰佗?'):
        _result = fetch_chip_concentration(_tk)

    _df = _result.get('df', pd.DataFrame())
    _err = _result.get('err', '')

    if _df is None or _df.empty:
        st.warning('?? ?⊥?閫??蝐Ⅳ鞈?嚗?蝣箄??格?蝬脩?蝯???????)
        if _err:
            st.caption(f'?? 閮箸閮嚗_err}')
        if st.button('??儭?皜翰??閰?, key='chip_radar_clear'):
            fetch_chip_concentration.clear()
            st.rerun()
        _render_diag(_result)
        return ''

    # ?? ?? metric ??
    _latest = _df.iloc[-1]
    _m1, _m2, _m3 = st.columns(3)
    with _m1:
        _d = _latest['?交?']
        st.metric('??啗??', _d.strftime('%Y-%m-%d') if pd.notna(_d) else '??)
    with _m2:
        _mj = _latest['憭扳瘥?']
        st.metric('憭扳?瘥?', f'{_mj:.2f}%' if pd.notna(_mj) else '??)
    with _m3:
        _rt = _latest['??鈭箸']
        st.metric('???鈭箸', f'{int(_rt):,}' if pd.notna(_rt) else '??)

    # ?? ??Y 頠詨? ??
    _plot_chip(_df, _tk)

    with st.expander('?? ??閫??鞈?銵?, expanded=False):
        st.dataframe(_df, use_container_width=True, hide_index=True)

    _render_diag(_result)

    # ?? 蝯艾I 擐葉憿批?蝮賜????函?蝐Ⅳ??摮葡 ??
    _summary = ''
    try:
        _bits = []
        _mj_v = _latest['憭扳瘥?']
        _rt_v = _latest['??鈭箸']
        if pd.notna(_mj_v):
            _trend = ''
            if len(_df) >= 5 and pd.notna(_df['憭扳瘥?'].iloc[-5]):
                _delta = float(_mj_v) - float(_df['憭扳瘥?'].iloc[-5])
                _trend = f'嚗?5?"??" if _delta > 0 else "??" if _delta < 0 else "?像"}{_delta:+.2f}%嚗?
            _bits.append(f'??憭扳?瘥?={float(_mj_v):.2f}%{_trend}')
        if pd.notna(_rt_v):
            _bits.append(f'??鈭箸={int(_rt_v):,}')
        if _bits:
            _summary = '??蝐Ⅳ嚗? + ' | '.join(_bits)
    except Exception:
        _summary = ''
    return _summary

