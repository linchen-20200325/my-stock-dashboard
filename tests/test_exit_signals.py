"""
tests/test_exit_signals.py
--------------------------
exit_signals 三維出場訊號單元測試（純邏輯，無 HTTP、無 Gemini）。
涵蓋：evaluate_exit_signals 計分分級 / compute_tech_bearish / parse_news_sentiment 清洗。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.compute.scoring import (
    compute_tech_bearish,
    evaluate_exit_signals,
    parse_news_sentiment,
)

_BEAR_TECH = {'bearish': True, 'reasons': ['空頭排列'], 'hits': 1, 'strong': True}
_OK_TECH = {'bearish': False, 'reasons': [], 'hits': 0, 'strong': False}
_NEWS_BAD = {'label': '利空', 'confidence': 80, 'reason': '訂單流失', 'ok': True}
_NEWS_OK = {'label': '中性', 'confidence': 60, 'reason': '無重大消息', 'ok': True}


# ── evaluate_exit_signals：計分與分級 ──────────────────────────
def test_three_dims_all_hit_is_red():
    ev = evaluate_exit_signals(_BEAR_TECH, '🔴 大戶倒貨', _NEWS_BAD)
    assert ev['score'] == 3
    assert ev['icon'] == '🔴'
    assert set(ev['hit_names']) == {'利空新聞', '技術轉空', '籌碼倒貨'}


def test_two_dims_is_orange():
    ev = evaluate_exit_signals(_BEAR_TECH, '🔴 大戶倒貨', _NEWS_OK)
    assert ev['score'] == 2
    assert ev['icon'] == '🟠'


def test_one_dim_chip_only_is_yellow():
    ev = evaluate_exit_signals(_OK_TECH, '🔴 大戶倒貨', None)
    assert ev['score'] == 1
    assert ev['icon'] == '🟡'
    assert ev['hit_names'] == ['籌碼倒貨']


def test_zero_dim_is_green():
    ev = evaluate_exit_signals(_OK_TECH, '🔥 大戶吸籌', _NEWS_OK)
    assert ev['score'] == 0
    assert ev['icon'] == '🟢'
    assert ev['hit_names'] == []


def test_low_confidence_bad_news_does_not_count():
    _weak = {'label': '利空', 'confidence': 30, 'reason': '小道消息', 'ok': True}
    ev = evaluate_exit_signals(_OK_TECH, '', _weak)
    assert ev['score'] == 0


def test_none_news_shows_unscanned():
    ev = evaluate_exit_signals(_OK_TECH, '', None)
    news_dim = next(d for d in ev['dims'] if d[0] == '利空新聞')
    assert news_dim[1] is False
    assert news_dim[2] == '未掃描'


def test_chip_dispersing_is_not_distribution():
    ev = evaluate_exit_signals(_OK_TECH, '🟡 籌碼發散', None)
    assert ev['score'] == 0


# ── compute_tech_bearish ──────────────────────────────────────
def test_bear_df_is_bearish(bear_df):
    out = compute_tech_bearish(bear_df)
    assert out['bearish'] is True
    assert out['strong'] is True  # 空頭排列為強訊號


def test_bull_df_not_bearish(bull_df):
    out = compute_tech_bearish(bull_df)
    assert out['bearish'] is False


def test_kd_high_dead_cross_adds_reason(bull_df):
    out = compute_tech_bearish(bull_df, k=80, d=85)
    assert any('KD高檔死叉' in r for r in out['reasons'])


def test_short_or_empty_df_is_safe():
    assert compute_tech_bearish(None)['bearish'] is False
    import pandas as pd
    assert compute_tech_bearish(pd.DataFrame({'close': [1, 2, 3]}))['bearish'] is False


# ── parse_news_sentiment：清洗 / 防呆 ─────────────────────────
def test_parse_clean_json():
    r = parse_news_sentiment('{"label":"利空","confidence":90,"reason":"裁罰"}')
    assert r['label'] == '利空' and r['confidence'] == 90 and r['ok'] is True


def test_parse_markdown_fenced_json():
    r = parse_news_sentiment('```json\n{"label":"利多","confidence":70,"reason":"接單"}\n```')
    assert r['label'] == '利多' and r['ok'] is True


def test_parse_invalid_label_falls_back_to_neutral():
    r = parse_news_sentiment('{"label":"超級大利空","confidence":50}')
    assert r['label'] == '中性'


def test_parse_confidence_clamped():
    r = parse_news_sentiment('{"label":"利空","confidence":200}')
    assert r['confidence'] == 100


def test_parse_garbage_is_not_ok():
    r = parse_news_sentiment('這不是 JSON')
    assert r['ok'] is False and r['label'] == '中性'
