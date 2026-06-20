from data_config import CACHE_TTL
"""
exit_signals.py ??銝雁?箏閮?蝬??斗嚗 / ?蝯??梁嚗?

銝雁摨佗?隞颱???閮?1 ??蝮賢?瘙箏?蝑?嚗?
  ???拍征?啗?嚗LM ???方?嚗udge_news_sentiment嚗emini ?勗?怎垢?喳嚗?
  ???銵?蝛綽?蝛粹?? / 頝摮?僑蝺?/ KD擃?甇餃? / ?專ACD蝧餉? / 擃???
  ??蝐Ⅳ?疏嚗? 20 ?亙之?嗆楊鞈??analyze_20d_chips_from_df ??'? 憭扳?疏'嚗?

??嚗銝剔雁摨行 0~3嚗?3??游撥???/ 2??遣霅唳?蝣?/ 1??∠???/ 0??Ｘ?瘛?

?祆??箇??摩嚗???????UI?emini ?澆瘝輻撠? gemini_fn ???嚗?澆蝡臬?伐?嚗?
?啗??方?蝯?隞?st.cache_data 敹怠?嚗TL 6h嚗??踹?蝯? tab 憭?????API??
"""
from __future__ import annotations

import json
import re

import pandas as pd
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW

# ?賭葉蝬剖漲????(?內, 璅惜, ?脩Ⅳ)
_LEVELS = {
    3: ('?', '撘瑞??箏', TRAFFIC_RED),
    2: ('??', '撱箄降皜Ⅳ', '#f0883e'),
    1: ('?', '??閫撖?, TRAFFIC_YELLOW),
    0: ('?', '閮?皜楚', TRAFFIC_GREEN),
}


def _ma(close: pd.Series, n: int):
    if close is None or len(close) < n:
        return None
    return float(close.tail(n).mean())


def _weekly_macd_turn_negative(close: pd.Series) -> bool:
    """餈?30 ??K 蝺? 5 ?孵???K嚗?MACD(3/5/3) ?望迤蝧餉?閬銝剔?頧摹??""
    try:
        if close is None or len(close) < 30:
            return False
        vals = [float(close.iloc[min(i + 4, len(close) - 1)])
                for i in range(0, min(30, len(close)), 5)]
        if len(vals) < 6:
            return False
        s = pd.Series(vals)
        macd = s.ewm(span=3, adjust=False).mean() - s.ewm(span=5, adjust=False).mean()
        hist = (macd - macd.ewm(span=3, adjust=False).mean()).tolist()
        return len(hist) >= 2 and hist[-2] > 0 and hist[-1] <= 0
    except Exception:
        return False


def compute_tech_bearish(df, k=None, d=None) -> dict:
    """敺?OHLC DataFrame ?典??銵蝛箸閮???

    df嚗???'close' 甈?high/low ??閬??/d嚗?怎垢撌脩?憟賜? KD嚗??蝞???
    ? {'bearish': bool, 'reasons': [str], 'hits': int, 'strong': bool}??
    bearish ?文?嚗撘瑁???蝛粹?? / ?專ACD蝧餉?嚗? ?? 璇郎蝷????銵?＊頧征??
    """
    out = {'bearish': False, 'reasons': [], 'hits': 0, 'strong': False}
    try:
        if df is None or len(df) < 20 or 'close' not in getattr(df, 'columns', []):
            return out
        close = df['close'].astype(float)
        p = float(close.iloc[-1])
        ma5, ma20, ma60, ma240 = (_ma(close, n) for n in (5, 20, 60, 240))
        reasons: list[str] = []
        strong = False

        if ma20 and ma60 and p < ma20 < ma60:
            reasons.append('蝛粹??嚗????<摮??嚗?)
            strong = True
        elif ma60 and p < ma60:
            reasons.append('頝摮?? MA60')

        if ma240 and p < ma240:
            reasons.append('頝撟渡? MA240')
        if ma20 and (p - ma20) / ma20 * 100 > 15:
            reasons.append(f'??甇???ａ?憭?{(p - ma20) / ma20 * 100:+.0f}%')
        if ma5 and p < ma5:
            reasons.append('頝 5MA嚗蝺?撘梧?')

        if k is not None and d is not None:
            try:
                if float(k) < float(d) and float(k) > 70:
                    reasons.append(f'KD擃?甇餃? K={float(k):.0f}')
            except (TypeError, ValueError):
                pass

        if _weekly_macd_turn_negative(close):
            reasons.append('?專ACD蝧餉?嚗葉蝺?撘梧?')
            strong = True

        out.update(bearish=(strong or len(reasons) >= 2),
                   reasons=reasons, hits=len(reasons), strong=strong)
    except Exception:
        pass
    return out


def build_news_prompt(name: str, headlines: list[str]) -> str:
    lines = '\n'.join(f'{i + 1}. {h}' for i, h in enumerate(headlines))
    return (
        f'雿?啗憸冽??撣怒誑銝?name}?????憿?隢?瑟擃????∩犖???拍征蝔漲?n'
        f'{lines}\n\n'
        '?芾撓??JSON嚗?閬遙雿?擗?摮?閬?markdown嚗?\n'
        '{"label":"?拍征?葉?扳??拙?","confidence":0??00???"reason":"30摮銝剜??"}\n'
        '?斗??嚗?祕鞈芾??????∪???Ｘ??荔?鞎∪銵圈???格?憭晞?蝵啜蝛箸蝑?
        '瘜犖隤輸??格??嫘?憭扳?憭?撘?嚗?蝞蝛箝?銝?砌葉?批撠暑?迤?Ｘ??臬隤文?箏蝛箝?
    )


def parse_news_sentiment(raw: str) -> dict:
    """閫?? Gemini ????{label, confidence, reason, ok}?窒?典?獢?_extract_json 皜??????""
    try:
        text = re.sub(r'```json|```', '', raw or '').strip()
        m = re.search(r'\{[\s\S]*\}', text)
        if not m:
            return {'label': '銝剜?, 'confidence': 0, 'reason': '?⊥?閫?? AI ??', 'ok': False}
        d = json.loads(m.group(0))
        label = str(d.get('label', '銝剜?)).strip()
        if label not in ('?拍征', '銝剜?, '?拙?'):
            label = '銝剜?
        try:
            conf = int(float(d.get('confidence', 0)))
        except (TypeError, ValueError):
            conf = 0
        return {'label': label, 'confidence': max(0, min(100, conf)),
                'reason': str(d.get('reason', ''))[:60], 'ok': True}
    except Exception as e:
        return {'label': '銝剜?, 'confidence': 0, 'reason': f'閫??憭望?嚗e}', 'ok': False}


def judge_news_sentiment(_gemini_call, name: str, headlines) -> dict:
    """蝯?prompt ???澆 Gemini ??閫???emini 憭望???銝剜改?銝?瑟?蝔???""
    items = [h for h in (headlines or []) if h][:8]
    if not items:
        return {'label': '銝剜?, 'confidence': 0, 'reason': '?∟????, 'ok': False}
    raw = _gemini_call(build_news_prompt(name, items), max_tokens=256)
    if not raw or str(raw).startswith('??'):
        return {'label': '銝剜?, 'confidence': 0, 'reason': str(raw or 'AI ?∪?閬?)[:60], 'ok': False}
    return parse_news_sentiment(raw)


def _build_cached_judge():
    """隞?st.cache_data ???啗??方?嚗TL 6h嚗???streamlit ?啣?嚗??桀?皜祈岫嚗???敹怠???""
    try:
        import streamlit as st
    except Exception:
        return None

    @st.cache_data(ttl=CACHE_TTL["daily_snapshot"], show_spinner=False)
    def _cached(_gemini_call, sid: str, name: str, headlines_key: tuple) -> dict:
        return judge_news_sentiment(_gemini_call, name, list(headlines_key))

    return _cached


_CACHED_JUDGE = _build_cached_judge()


def judge_news_sentiment_cached(_gemini_call, sid: str, name: str, headlines) -> dict:
    """敹怠???霈嚗ey=?∟?+璅?嚗emini_call 隞亙?蝺?蝬湔??斗 hash 憭???""
    key = tuple(h for h in (headlines or []) if h)[:8]
    if _CACHED_JUDGE is not None:
        return _CACHED_JUDGE(_gemini_call, sid, name, key)
    return judge_news_sentiment(_gemini_call, name, list(key))


def evaluate_exit_signals(tech: dict | None = None, chip_signal: str = '',
                          news: dict | None = None,
                          news_conf_threshold: int = 50) -> dict:
    """銝雁蝬??斗??

    tech嚗ompute_tech_bearish ?嚗one=?芣?靘???
    chip_signal嚗nalyze_20d_chips_from_df ??'signal' 摮葡??
    news嚗udge_news_sentiment ?嚗one=撠??嚗?憒???tab ?芣???????
    ? {score, icon, label, color, dims:[(?迂,?賭葉,隤芣?)], hit_names, headline}??
    """
    news_hit = bool(news) and news.get('label') == '?拍征' \
        and int(news.get('confidence', 0)) >= news_conf_threshold
    if news_hit:
        news_desc = f"?拍征嚗縑敹?{news.get('confidence')}嚗?{news.get('reason', '')}"
    elif news:
        news_desc = f"{news.get('label', '銝剜?)}嚗news.get('reason', '')}"
    else:
        news_desc = '?芣???

    tech_hit = bool(tech) and tech.get('bearish')
    tech_desc = '??.join(tech.get('reasons', [])) if tech and tech.get('reasons') else '??

    chip_hit = '憭扳?疏' in (chip_signal or '')
    chip_desc = chip_signal or '??

    dims = [
        ('?拍征?啗?', news_hit, news_desc),
        ('?銵?蝛?, tech_hit, tech_desc),
        ('蝐Ⅳ?疏', chip_hit, chip_desc),
    ]
    score = sum(1 for _, hit, _ in dims if hit)
    icon, label, color = _LEVELS[score]
    hit_names = [n for n, hit, _ in dims if hit]
    headline = f'{icon} {label}'
    headline += f'嚗score}/3 蝬剛?蝛綽?{"嚗?.join(hit_names)}嚗? if score else '嚗?蝬剜頧征嚗?
    return {'score': score, 'icon': icon, 'label': label, 'color': color,
            'dims': dims, 'hit_names': hit_names, 'headline': headline}

