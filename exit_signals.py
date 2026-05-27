"""
exit_signals.py — 三維出場訊號綜合判斷（個股 / 個股組合共用）

三個維度（任一成立記 1 分，總分決定等級）：
  ① 利空新聞：LLM 情緒判讀（judge_news_sentiment，Gemini 由呼叫端傳入）
  ② 技術轉空：空頭排列 / 跌破季年線 / KD高檔死叉 / 週MACD翻負 / 高乖離
  ③ 籌碼倒貨：近 20 日大戶淨賣（analyze_20d_chips_from_df 回 '🔴 大戶倒貨'）

分級（命中維度數 0~3）：3→🔴強烈出場 / 2→🟠建議減碼 / 1→🟡留意 / 0→🟢清淡

本檔為純邏輯：不抓資料、不畫 UI。Gemini 呼叫沿用專案 gemini_fn 慣例（由呼叫端傳入），
新聞判讀結果以 st.cache_data 快取（TTL 6h），避免組合 tab 多檔重複打 API。
"""
from __future__ import annotations

import json
import re

import pandas as pd

# 命中維度數 → (圖示, 標籤, 色碼)
_LEVELS = {
    3: ('🔴', '強烈出場', '#f85149'),
    2: ('🟠', '建議減碼', '#f0883e'),
    1: ('🟡', '留意觀察', '#d29922'),
    0: ('🟢', '訊號清淡', '#3fb950'),
}


def _ma(close: pd.Series, n: int):
    if close is None or len(close) < n:
        return None
    return float(close.tail(n).mean())


def _weekly_macd_turn_negative(close: pd.Series) -> bool:
    """近 30 日 K 線每 5 根合成週 K，週 MACD(3/5/3) 由正翻負視為中線轉弱。"""
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
    """從 OHLC DataFrame 推導技術面空方訊號。

    df：需有 'close' 欄（high/low 非必要）。k/d：呼叫端已算好的 KD（避免重算）。
    回傳 {'bearish': bool, 'reasons': [str], 'hits': int, 'strong': bool}。
    bearish 判定：含強訊號（空頭排列 / 週MACD翻負）或 ≥2 條警示 → 技術面明顯轉空。
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
            reasons.append('空頭排列（股價<月線<季線）')
            strong = True
        elif ma60 and p < ma60:
            reasons.append('跌破季線 MA60')

        if ma240 and p < ma240:
            reasons.append('跌破年線 MA240')
        if ma20 and (p - ma20) / ma20 * 100 > 15:
            reasons.append(f'月線正乖離過大 {(p - ma20) / ma20 * 100:+.0f}%')
        if ma5 and p < ma5:
            reasons.append('跌破 5MA（短線轉弱）')

        if k is not None and d is not None:
            try:
                if float(k) < float(d) and float(k) > 70:
                    reasons.append(f'KD高檔死叉 K={float(k):.0f}')
            except (TypeError, ValueError):
                pass

        if _weekly_macd_turn_negative(close):
            reasons.append('週MACD翻負（中線轉弱）')
            strong = True

        out.update(bearish=(strong or len(reasons) >= 2),
                   reasons=reasons, hits=len(reasons), strong=strong)
    except Exception:
        pass
    return out


def build_news_prompt(name: str, headlines: list[str]) -> str:
    lines = '\n'.join(f'{i + 1}. {h}' for i, h in enumerate(headlines))
    return (
        f'你是台股風控分析師。以下是「{name}」近期新聞標題，請判斷整體對「持股人」的利空程度。\n'
        f'{lines}\n\n'
        '只輸出 JSON（不要任何多餘文字、不要 markdown）：\n'
        '{"label":"利空或中性或利多","confidence":0到100的整數,"reason":"30字內中文理由"}\n'
        '判斷原則：只有實質衝擊營運或股價的負面消息（財報衰退、訂單流失、裁罰、利空政策、'
        '法人調降目標價、重大意外或弊案）才算「利空」；一般中性報導、活動、正面消息勿誤判為利空。'
    )


def parse_news_sentiment(raw: str) -> dict:
    """解析 Gemini 回覆為 {label, confidence, reason, ok}。沿用專案 _extract_json 清洗慣例。"""
    try:
        text = re.sub(r'```json|```', '', raw or '').strip()
        m = re.search(r'\{[\s\S]*\}', text)
        if not m:
            return {'label': '中性', 'confidence': 0, 'reason': '無法解析 AI 回覆', 'ok': False}
        d = json.loads(m.group(0))
        label = str(d.get('label', '中性')).strip()
        if label not in ('利空', '中性', '利多'):
            label = '中性'
        try:
            conf = int(float(d.get('confidence', 0)))
        except (TypeError, ValueError):
            conf = 0
        return {'label': label, 'confidence': max(0, min(100, conf)),
                'reason': str(d.get('reason', ''))[:60], 'ok': True}
    except Exception as e:
        return {'label': '中性', 'confidence': 0, 'reason': f'解析失敗：{e}', 'ok': False}


def judge_news_sentiment(_gemini_call, name: str, headlines) -> dict:
    """組 prompt → 呼叫 Gemini → 解析。Gemini 失效時回中性（不阻斷流程）。"""
    items = [h for h in (headlines or []) if h][:8]
    if not items:
        return {'label': '中性', 'confidence': 0, 'reason': '無近期新聞', 'ok': False}
    raw = _gemini_call(build_news_prompt(name, items), max_tokens=256)
    if not raw or str(raw).startswith('⚠️'):
        return {'label': '中性', 'confidence': 0, 'reason': str(raw or 'AI 無回覆')[:60], 'ok': False}
    return parse_news_sentiment(raw)


def _build_cached_judge():
    """以 st.cache_data 包裝新聞判讀（TTL 6h）；無 streamlit 環境（如單元測試）則退回未快取版。"""
    try:
        import streamlit as st
    except Exception:
        return None

    @st.cache_data(ttl=21600, show_spinner=False)
    def _cached(_gemini_call, sid: str, name: str, headlines_key: tuple) -> dict:
        return judge_news_sentiment(_gemini_call, name, list(headlines_key))

    return _cached


_CACHED_JUDGE = _build_cached_judge()


def judge_news_sentiment_cached(_gemini_call, sid: str, name: str, headlines) -> dict:
    """快取版新聞判讀；key=股號+標題（gemini_call 以底線前綴排除於 hash 外）。"""
    key = tuple(h for h in (headlines or []) if h)[:8]
    if _CACHED_JUDGE is not None:
        return _CACHED_JUDGE(_gemini_call, sid, name, key)
    return judge_news_sentiment(_gemini_call, name, list(key))


def evaluate_exit_signals(tech: dict | None = None, chip_signal: str = '',
                          news: dict | None = None,
                          news_conf_threshold: int = 50) -> dict:
    """三維綜合判斷。

    tech：compute_tech_bearish 回傳（None=未提供）。
    chip_signal：analyze_20d_chips_from_df 的 'signal' 字串。
    news：judge_news_sentiment 回傳（None=尚未掃描，例如組合 tab 未按掃描鈕）。
    回傳 {score, icon, label, color, dims:[(名稱,命中,說明)], hit_names, headline}。
    """
    news_hit = bool(news) and news.get('label') == '利空' \
        and int(news.get('confidence', 0)) >= news_conf_threshold
    if news_hit:
        news_desc = f"利空（信心 {news.get('confidence')}）：{news.get('reason', '')}"
    elif news:
        news_desc = f"{news.get('label', '中性')}：{news.get('reason', '')}"
    else:
        news_desc = '未掃描'

    tech_hit = bool(tech) and tech.get('bearish')
    tech_desc = '、'.join(tech.get('reasons', [])) if tech and tech.get('reasons') else '—'

    chip_hit = '大戶倒貨' in (chip_signal or '')
    chip_desc = chip_signal or '—'

    dims = [
        ('利空新聞', news_hit, news_desc),
        ('技術轉空', tech_hit, tech_desc),
        ('籌碼倒貨', chip_hit, chip_desc),
    ]
    score = sum(1 for _, hit, _ in dims if hit)
    icon, label, color = _LEVELS[score]
    hit_names = [n for n, hit, _ in dims if hit]
    headline = f'{icon} {label}'
    headline += f'（{score}/3 維轉空：{"＋".join(hit_names)}）' if score else '（三維未轉空）'
    return {'score': score, 'icon': icon, 'label': label, 'color': color,
            'dims': dims, 'hit_names': hit_names, 'headline': headline}
