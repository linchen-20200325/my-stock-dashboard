"""#1 v19.200(對稱性稽核)—— 個股「多檔頁」批次評分補月營收 → 六因子基本面真計分。

病症
====
個股**單檔**深度分析有抓月營收(基本面維度真算),但**多檔**批次
(`section_batch_fetcher.run_batch_fetch`)呼叫 `score_single_stock` 時**沒傳**
`revenue_df` → `calc_revenue_yoy_score(None)` 一律回中性 50 → 同一支股票在單檔頁
與多檔頁的「基本面」分數不對稱、多檔頁排名少了一整個維度的鑑別力。

修法
====
批次 worker 補 `fetch_revenue(sid4)` → 存 `rev_df` → 主迴圈把 `revenue_df=rev_df4`
餵給 `score_single_stock`。抓不到月營收 → None → 下游仍中性 50(§1 graceful,不假造)。

守衛策略
========
1. **AST 守衛**(排 docstring/註解):`score_single_stock(...)` 呼叫帶 `revenue_df=` 關鍵字;
   worker 有 `fetch_revenue(` 呼叫。—— 釘「wiring 存在」,不照抄實作字面。
2. **行為守衛**:同一份 df,`revenue_df=`(強勁 YoY 成長)的總分 > `revenue_df=None`,
   證明基本面維度**真的會動**(不是接了但被權重歸零)。

3 個最容易出錯的輸入(本檔涵蓋):
  1. revenue_df=None(抓不到月營收)—— 必須回中性 50,不可炸、不可假造。
  2. 月營收只有 <13 個月 —— pct_change(12) 全 NaN,基本面應回中性,不可誤判。
  3. 強勁成長月營收 —— 基本面應 > 50 並拉高總分(維度有效性)。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd

from src.compute.scoring.scoring_engine import (
    calc_revenue_yoy_score,
    score_single_stock,
)

_REPO = Path(__file__).resolve().parents[1]
_BATCH_PY = _REPO / 'src' / 'ui' / 'tabs' / 'stock_grp_sections' / 'section_batch_fetcher.py'


# ── 測試素材 ───────────────────────────────────────────────────
def _make_ohlcv(n: int = 120) -> pd.DataFrame:
    """合成一段溫和上行的日 K(所有子評分器都能吃,兩次呼叫共用 → 只有 revenue 差)。"""
    dates = pd.date_range('2025-01-01', periods=n, freq='B')
    base = [100 + i * 0.3 for i in range(n)]
    return pd.DataFrame({
        'date': dates,
        'open':  [b - 0.2 for b in base],
        'high':  [b + 0.5 for b in base],
        'low':   [b - 0.5 for b in base],
        'close': base,
        'volume': [1_000_000 + (i % 5) * 10_000 for i in range(n)],
    })


def _make_growing_revenue(months: int = 18) -> pd.DataFrame:
    """月營收:YoY 逐月加速、全正、最新月 > 15% —— calc_revenue_yoy_score 應給高分。"""
    dates = pd.date_range('2024-01-01', periods=months, freq='MS')
    # 年增率遞增:前 12 個月當基準,後幾個月加速成長
    rev = []
    for i in range(months):
        # 基準線性 + 後段乘一個 >1.15 的成長因子(對 12 個月前)
        rev.append(1_000_000 * (1.0 + 0.02 * i) * (1.30 if i >= 12 else 1.0))
    return pd.DataFrame({'date': dates, 'revenue': rev})


# ══════════════════════════════════════════════════════════════
# 行為守衛 —— 基本面維度真的會動
# ══════════════════════════════════════════════════════════════
def test_revenue_df_none_is_neutral_50():
    """抓不到月營收(None)→ 中性 50(§1:不炸、不假造)。"""
    assert calc_revenue_yoy_score(None) == 50.0


def test_revenue_df_short_history_is_neutral():
    """月營收 < 13 個月 → pct_change(12) 全 NaN → 中性(不誤判)。"""
    short = pd.DataFrame({
        'date': pd.date_range('2025-01-01', periods=6, freq='MS'),
        'revenue': [1_000_000 * (1 + 0.05 * i) for i in range(6)],
    })
    assert calc_revenue_yoy_score(short) == 50.0


def test_growing_revenue_scores_above_neutral():
    """強勁 YoY 成長 → 基本面分數 > 50(維度有效)。"""
    assert calc_revenue_yoy_score(_make_growing_revenue()) > 50.0


def test_score_single_stock_moves_with_revenue():
    """同一份 df:傳強勁成長 revenue_df 的總分 > 不傳(revenue_df=None)。

    證明多檔頁補上 revenue_df 之後,基本面維度**真的**影響排名,
    而非「接了但被權重歸零」。
    """
    df = _make_ohlcv()
    rev = _make_growing_revenue()
    total_with = score_single_stock(df, '2330', '台積電',
                                    regime='neutral', revenue_df=rev)['total']
    total_without = score_single_stock(df, '2330', '台積電',
                                       regime='neutral', revenue_df=None)['total']
    assert total_with > total_without, (
        f'基本面維度未生效:with={total_with} 應 > without={total_without}')


# ══════════════════════════════════════════════════════════════
# AST 守衛 —— wiring 存在(排 docstring/註解,只釘呼叫形狀)
# ══════════════════════════════════════════════════════════════
def _batch_tree() -> ast.Module:
    return ast.parse(_BATCH_PY.read_text(encoding='utf-8'))


def test_worker_calls_fetch_revenue():
    """批次 worker 有 fetch_revenue(...) 呼叫(補抓月營收)。"""
    tree = _batch_tree()
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'fetch_revenue']
    assert calls, 'section_batch_fetcher 應呼叫 fetch_revenue 補月營收'


def test_score_single_stock_call_passes_revenue_df():
    """score_single_stock(...) 呼叫帶 revenue_df= 關鍵字(把月營收餵進六因子)。"""
    tree = _batch_tree()
    score_calls = [n for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == 'score_single_stock']
    assert score_calls, '找不到 score_single_stock 呼叫'
    assert any(any(kw.arg == 'revenue_df' for kw in c.keywords) for c in score_calls), \
        'score_single_stock 呼叫應傳 revenue_df=(多檔頁基本面真計分)'
