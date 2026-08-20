"""#2 v19.200(對稱性稽核)—— 個股多檔批次補「軋空加分」輸入(券資比 + 法人連買)。

病症
====
`calc_short_squeeze_bonus`(§5.2 軋空 +5 加分)早就存在,但多檔批次評分
(`section_batch_fetcher`)呼叫 `score_single_stock` 時**從未**餵入 `short_ratio` /
`inst_consec_buy` → 兩者恆用預設 0.0 / 0 → 軋空加分**永不觸發**(接了等於沒接)。

修法
====
新增純函式 `derive_short_squeeze_inputs(df)` 從 `get_combined_data` 的 df 導出:
  - 券資比 = 最新融券餘額 / 最新融資餘額(同「張」→ ratio)
  - 法人連買 = 尾端「主力合計 > 0」連續天數
批次主迴圈 df4 已在手 → 純函式導出零額外抓取 → 餵進 score_single_stock。

3 個最容易出錯的輸入(本檔涵蓋):
  1. 缺 融資/融券/主力合計 欄 —— 回保守 0/0(不觸發、不炸)。
  2. 融資餘額=0(data_loader fillna 補的空列)—— 必須排除,不可 0/0 除爆或誤判。
  3. 主力合計 尾端有 0(法人當日無資料被 fillna(0))—— 連買中斷,不可把「無資料」當「買超」。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from src.compute.scoring.scoring_engine import (
    derive_short_squeeze_inputs,
    score_single_stock,
)
from shared.signal_thresholds import (
    SQUEEZE_BONUS,
    SQUEEZE_INST_BUY_DAYS_MIN,
    SQUEEZE_SHORT_RATIO_MIN,
)

_REPO = Path(__file__).resolve().parents[1]
_BATCH_PY = _REPO / 'src' / 'ui' / 'tabs' / 'stock_grp_sections' / 'section_batch_fetcher.py'


def _df(**cols) -> pd.DataFrame:
    return pd.DataFrame(cols)


# ══════════════════════════════════════════════════════════════
# derive_short_squeeze_inputs 行為
# ══════════════════════════════════════════════════════════════
def test_none_or_empty_returns_zeros():
    assert derive_short_squeeze_inputs(None) == {'short_ratio': 0.0, 'inst_consec_buy': 0}
    assert derive_short_squeeze_inputs(pd.DataFrame()) == {'short_ratio': 0.0, 'inst_consec_buy': 0}


def test_missing_columns_returns_zeros():
    """只有價格欄,無融資/融券/主力合計 → 保守 0/0。"""
    out = derive_short_squeeze_inputs(_df(close=[10, 11, 12]))
    assert out == {'short_ratio': 0.0, 'inst_consec_buy': 0}


def test_short_ratio_basic():
    """券資比 = 融券 / 融資(取最後一列)。10000/50000 = 0.2。"""
    out = derive_short_squeeze_inputs(_df(
        融資餘額=[40000, 50000],
        融券餘額=[8000, 10000],
        主力合計=[0, 0],
    ))
    assert abs(out['short_ratio'] - 0.2) < 1e-9


def test_short_ratio_skips_fillna_zero_rows():
    """最後一列融資=0(fillna 補的空列)→ 取前一列有效值,不回 0、不除爆。"""
    out = derive_short_squeeze_inputs(_df(
        融資餘額=[50000, 0],       # 末列被 data_loader fillna(0)
        融券餘額=[10000, 0],
        主力合計=[0, 0],
    ))
    assert abs(out['short_ratio'] - 0.2) < 1e-9   # 用倒數第 2 列(有效)


def test_short_ratio_all_zero_fin_returns_zero():
    """全部融資=0 → 無有效列 → 0(不除以 0)。"""
    out = derive_short_squeeze_inputs(_df(
        融資餘額=[0, 0], 融券餘額=[0, 0], 主力合計=[0, 0]))
    assert out['short_ratio'] == 0.0


def test_inst_consec_buy_counts_trailing_positive():
    """尾端連續 3 天主力合計 > 0 → 連買 3。"""
    out = derive_short_squeeze_inputs(_df(
        融資餘額=[1, 1, 1, 1, 1],
        融券餘額=[0, 0, 0, 0, 0],
        主力合計=[-100, 50, 200, 300, 150],   # 尾端 4 天正,但第 2 列前是 -100
    ))
    assert out['inst_consec_buy'] == 4


def test_inst_consec_buy_zero_breaks_streak():
    """尾端主力合計=0(當日法人無資料被 fillna(0))→ 連買中斷為 0(§1 不假造)。"""
    out = derive_short_squeeze_inputs(_df(
        融資餘額=[1, 1, 1],
        融券餘額=[0, 0, 0],
        主力合計=[300, 300, 0],   # 末日 0
    ))
    assert out['inst_consec_buy'] == 0


# ══════════════════════════════════════════════════════════════
# 端到端:軋空加分實際觸發
# ══════════════════════════════════════════════════════════════
def _ohlcv_with_chips(n=120, *, fin, short, inst_tail_days):
    dates = pd.date_range('2025-01-01', periods=n, freq='B')
    base = [100 + i * 0.3 for i in range(n)]
    主力 = [0.0] * n
    for j in range(1, inst_tail_days + 1):
        主力[n - j] = 200.0   # 尾端 inst_tail_days 天皆正
    return pd.DataFrame({
        'date': dates,
        'open': [b - 0.2 for b in base], 'high': [b + 0.5 for b in base],
        'low': [b - 0.5 for b in base], 'close': base,
        'volume': [1_000_000] * n,
        '融資餘額': [fin] * n, '融券餘額': [short] * n, '主力合計': 主力,
    })


def test_score_gets_squeeze_bonus_when_triggered():
    """券資比 > 門檻 且 法人連買 ≥ 門檻 → 總分含 +SQUEEZE_BONUS。"""
    # 券資比 = short/fin 需 > SQUEEZE_SHORT_RATIO_MIN(0.3);連買 ≥ SQUEEZE_INST_BUY_DAYS_MIN
    fin, short = 10000, int(10000 * (SQUEEZE_SHORT_RATIO_MIN + 0.1))
    df = _ohlcv_with_chips(fin=fin, short=short,
                           inst_tail_days=SQUEEZE_INST_BUY_DAYS_MIN)
    _sq = derive_short_squeeze_inputs(df)
    assert _sq['short_ratio'] > SQUEEZE_SHORT_RATIO_MIN
    assert _sq['inst_consec_buy'] >= SQUEEZE_INST_BUY_DAYS_MIN

    with_sq = score_single_stock(df, '2330', '台積電', regime='neutral',
                                 short_ratio=_sq['short_ratio'],
                                 inst_consec_buy=_sq['inst_consec_buy'])
    assert with_sq['squeeze_bonus'] == SQUEEZE_BONUS


def test_score_no_bonus_when_short_ratio_low():
    """券資比低 → 無軋空加分(bonus=0)。"""
    df = _ohlcv_with_chips(fin=100000, short=1000,   # 券資比 0.01
                           inst_tail_days=SQUEEZE_INST_BUY_DAYS_MIN + 2)
    _sq = derive_short_squeeze_inputs(df)
    out = score_single_stock(df, '2330', '台積電', regime='neutral',
                             short_ratio=_sq['short_ratio'],
                             inst_consec_buy=_sq['inst_consec_buy'])
    assert out['squeeze_bonus'] == 0


# ══════════════════════════════════════════════════════════════
# AST wiring 守衛
# ══════════════════════════════════════════════════════════════
def _batch_tree() -> ast.Module:
    return ast.parse(_BATCH_PY.read_text(encoding='utf-8'))


def test_batch_calls_derive_and_passes_squeeze_kwargs():
    tree = _batch_tree()
    assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == 'derive_short_squeeze_inputs' for n in ast.walk(tree)), \
        'section_batch_fetcher 應呼叫 derive_short_squeeze_inputs'
    score_calls = [n for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == 'score_single_stock']
    assert score_calls
    kw = {kw.arg for c in score_calls for kw in c.keywords}
    assert 'short_ratio' in kw and 'inst_consec_buy' in kw, \
        'score_single_stock 呼叫應傳 short_ratio= 與 inst_consec_buy='
