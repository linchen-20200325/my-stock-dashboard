"""tests/test_b1a_portfolio_fx.py — ETF 組合 §4.1 幣別混算守衛（B1-a, v19.179）。

被修的 bug
==========
`src/ui/etf/etf_tab_portfolio.py` 把**美元計價 ETF 的原幣金額直接加進台幣總額**，
等於預設 1 USD = 1 TWD。實機（0050 / 00713 / BND 200股 / 00878）症狀：

| 項目 | 修前 | 真值 |
|---|---|---|
| 總現值 | 212,061 | ≈ 665,500 |
| BND 權重 | 6.8% | ≈ 70% |
| 股債比 | 股 93 / 債 7 | ≈ 股 30 / 債 70 |
| 組合殖利率 | **12.20%** | ≈ **3.89%** |

殖利率那條最毒：分子 `_sched['annual_total_twd']` **已經換過匯**，
分母 `total_value` **沒換** ⇒ 虛胖約 3.1 倍，且被拿去下
「殖利率優異、以息養股目標達成」的強結論（≥ YIELD_MID）。

本檔測什麼
==========
1. **行為**（主力）：`convert_rows_to_twd` 的混幣總計、缺匯率時的排除行為、
   殖利率分子分母同幣別、股債比。用固定匯率 fixture，零網路。
2. **原始碼守衛**（輔助）：確認「單一換匯點」的結構沒被後續改動搞回去
   —— 一律走 **AST**：
   * 註解天生不在 AST 內；docstring 以 `ast.get_docstring` 另行排除。
   * 位置比較用 `lineno`（真實節點），不用字串出現順序。
   * 失敗訊息一律印 `檔名:行號` + **該行原始碼原文**，紅燈可直接定位。
   （本專案先前多次被 naive 字串掃描守衛的假紅燈擋住，故此處刻意不用 regex。）
"""
from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

from shared.signal_thresholds import USDTWD_SANITY_MAX, USDTWD_SANITY_MIN
from shared.thresholds import YIELD_MID
from src.compute.etf.etf_dividend_schedule import build_monthly_dividend_rows
from src.compute.etf.portfolio_coherence import assess_stock_bond
from src.compute.etf.portfolio_fx import (
    CURRENCY_TWD,
    CURRENCY_USD,
    convert_rows_to_twd,
    fx_disclosure_caption,
    holding_currency,
    normalize_usdtwd_rate,
)

REPO = Path(__file__).resolve().parent.parent
_PORTFOLIO_TAB = 'src/ui/etf/etf_tab_portfolio.py'

#: 實機當下的 USD/TWD（總經頁顯示 32.30 附近）。測試固定值 → 可重現（§5）。
FX = 32.282


# ══════════════════════════════════════════════════════════════════
# fixtures — 實機那組持股（0050 / 00713 / BND / 00878）
# ══════════════════════════════════════════════════════════════════
def _row(ticker, shares, avg_price, cur_price, div_native, role='衛星'):
    """建一筆「原幣別」持股（換匯前的 rows 契約）。"""
    _cost = shares * avg_price
    _val = shares * cur_price
    return {
        'ticker': ticker,
        'lots': shares / 1000,
        'shares': shares,
        'avg_price': avg_price,
        'cost': _cost,
        'current_price': cur_price,
        'current_value': _val,
        'capital_gain': _val - _cost,
        'capital_gain_pct': (_val - _cost) / _cost * 100 if _cost else 0.0,
        'dividend_received': div_native,
        'total_pnl': _val - _cost + div_native,
        'target_pct': None,
        'role': role,
    }


@pytest.fixture()
def live_rows():
    """實機組合。台股三檔現值合計 197,565 TWD；BND 現值 14,496 **USD**。"""
    return [
        _row('0050.TW', 1000, 135.50, 100.0, 1600.0, role='核心'),   # 100,000 TWD
        _row('00713.TW', 500, 82.30, 90.13, 1670.0),                 #  45,065 TWD
        _row('BND', 200, 72.50, 72.48, 584.0, role='債券'),          #  14,496 USD
        _row('00878.TW', 2000, 20.10, 26.25, 3760.0),                #  52,500 TWD
    ]


def _twd_only_total(rows):
    return sum(r['current_value'] for r in rows
               if holding_currency(r['ticker']) == CURRENCY_TWD)


# ══════════════════════════════════════════════════════════════════
# 1. 幣別判斷 + 匯率正規化
# ══════════════════════════════════════════════════════════════════
class TestCurrencyAndRate:
    @pytest.mark.parametrize('ticker,expected', [
        ('0050.TW', CURRENCY_TWD),
        ('0050.tw', CURRENCY_TWD),        # 大小寫不敏感
        ('  00878.TW ', CURRENCY_TWD),    # 前後空白
        ('006208.TWO', CURRENCY_TWD),
        ('BND', CURRENCY_USD),
        ('voo', CURRENCY_USD),
    ])
    def test_holding_currency(self, ticker, expected):
        assert holding_currency(ticker) == expected

    def test_no_suffix_documented_as_usd(self):
        """已知限制（docstring 有寫）：沒後綴一律當 USD，包含 None / 空字串。

        這**不是**測試在背書這個行為正確，而是把脆弱假設釘住 ——
        未來若改成用 `info['currency']` 或支援第三個市場，這條會紅，
        逼改動者回頭讀 `holding_currency` 的限制說明。
        """
        assert holding_currency(None) == CURRENCY_USD
        assert holding_currency('') == CURRENCY_USD
        assert holding_currency('2330') == CURRENCY_USD  # 少打 .TW → 已知誤判方向

    @pytest.mark.parametrize('bad', [
        None, '', 'abc', float('nan'), 0, -5, 1.0, 0.031,
        USDTWD_SANITY_MIN - 0.01, USDTWD_SANITY_MAX + 0.01,
    ])
    def test_invalid_rate_returns_none_never_one(self, bad):
        """§1：任何可疑匯率一律回 None —— **絕不**退回 1.0、也不夾到邊界。"""
        assert normalize_usdtwd_rate(bad) is None

    @pytest.mark.parametrize('good', [USDTWD_SANITY_MIN, 32.282, USDTWD_SANITY_MAX])
    def test_valid_rate_passthrough(self, good):
        assert normalize_usdtwd_rate(good) == pytest.approx(float(good))


# ══════════════════════════════════════════════════════════════════
# 2. 混合幣別總計正確性（固定匯率 fixture）
# ══════════════════════════════════════════════════════════════════
class TestMixedCurrencyTotals:
    def test_usd_row_scaled_twd_row_untouched(self, live_rows):
        out = convert_rows_to_twd(live_rows, usdtwd_rate=FX)
        assert out['excluded'] == []
        assert out['rate_used'] == pytest.approx(FX)
        _by = {r['ticker']: r for r in out['rows']}

        _bnd = _by['BND']
        assert _bnd['currency'] == CURRENCY_USD
        assert _bnd['fx_rate'] == pytest.approx(FX)
        assert _bnd['current_value'] == pytest.approx(14496.0 * FX)
        assert _bnd['cost'] == pytest.approx(200 * 72.50 * FX)
        assert _bnd['dividend_received'] == pytest.approx(584.0 * FX)
        # 原幣別必須保留（畫面要印「72.48 USD」而不是台幣化的 2,340）
        assert _bnd['current_price_native'] == pytest.approx(72.48)
        assert _bnd['current_value_native'] == pytest.approx(14496.0)

        _tw = _by['0050.TW']
        assert _tw['currency'] == CURRENCY_TWD
        assert _tw['fx_rate'] == 1.0
        assert _tw['current_value'] == pytest.approx(100_000.0)
        assert _tw['current_value_native'] == pytest.approx(100_000.0)

    def test_ratio_fields_not_scaled(self, live_rows):
        """比率欄（利得%）匯率在分子分母相消 —— 換了就是錯（§4.1）。"""
        _before = {r['ticker']: r['capital_gain_pct'] for r in live_rows}
        out = convert_rows_to_twd(live_rows, usdtwd_rate=FX)
        for r in out['rows']:
            assert r['capital_gain_pct'] == pytest.approx(_before[r['ticker']])

    def test_total_and_weight_match_reality(self, live_rows):
        out = convert_rows_to_twd(live_rows, usdtwd_rate=FX)
        _rows = out['rows']
        _total = sum(r['current_value'] for r in _rows)
        _bnd = next(r for r in _rows if r['ticker'] == 'BND')
        _w = _bnd['current_value'] / _total * 100

        # 修前總現值 212,061（BND 以 1:1 混入）；修後約 665,500
        _buggy_total = _twd_only_total(live_rows) + 14496.0
        assert _buggy_total == pytest.approx(212_061.0, rel=1e-3)
        assert _total == pytest.approx(665_500.0, rel=5e-3)
        assert _total > _buggy_total * 3       # 不再是「差一點點」的誤差

        # 修前權重 6.8%；修後約 70%
        assert 68.0 < _w < 72.0
        # ⚠️ 重現「修前 6.8%」時,分子**必須**用未換匯的原幣值 —— `_buggy_total` 本身
        # 就是「BND 以 1:1 混入」的口徑,分子若用已換匯的 `current_value`(≈467,920)
        # 就變成拿換匯後的分子除未換匯的分母 ⇒ 220.67%,兩邊口徑不一致。
        # 這正是本檔要防的那個 bug 的**測試版**:混幣別相除與混幣別相加同樣是 §4.1 錯誤。
        assert (_bnd['current_value_native'] / _buggy_total * 100
                == pytest.approx(6.8, abs=0.2))

    def test_stock_bond_split_flips(self, live_rows):
        """股債比 93/7 → 約 30/70（BND 是債券，佔比被低估 10 倍）。"""
        _conv = convert_rows_to_twd(live_rows, usdtwd_rate=FX)['rows']
        _sb_fixed = assess_stock_bond(
            [{'ticker': r['ticker'], 'value': r['current_value']} for r in _conv])
        _sb_buggy = assess_stock_bond(
            [{'ticker': r['ticker'], 'value': r['current_value']} for r in live_rows])
        assert _sb_buggy['bond_pct'] == pytest.approx(6.8, abs=0.3)
        assert 68.0 < _sb_fixed['bond_pct'] < 72.0
        assert _sb_fixed['stock_pct'] + _sb_fixed['bond_pct'] == pytest.approx(100.0, abs=0.2)

    def test_all_twd_portfolio_is_bit_identical(self, live_rows):
        """全台股組合：有沒有匯率都不該讓任何數字改變（回歸保險）。"""
        _tw_rows = [r for r in live_rows if holding_currency(r['ticker']) == CURRENCY_TWD]
        _a = convert_rows_to_twd(_tw_rows, usdtwd_rate=None)
        _b = convert_rows_to_twd(_tw_rows, usdtwd_rate=FX)
        assert _a['excluded'] == [] and _b['excluded'] == []
        for _ra, _rb, _orig in zip(_a['rows'], _b['rows'], _tw_rows):
            assert _ra['current_value'] == _rb['current_value'] == _orig['current_value']
            assert _ra['cost'] == _rb['cost'] == _orig['cost']

    def test_input_rows_not_mutated(self, live_rows):
        """純函式：不得就地改 caller 的 dict（否則重跑會二次換匯 = 1000 倍）。"""
        _snapshot = [dict(r) for r in live_rows]
        convert_rows_to_twd(live_rows, usdtwd_rate=FX)
        assert live_rows == _snapshot


# ══════════════════════════════════════════════════════════════════
# 3. §1 匯率缺失 → 不得靜默用 1.0
# ══════════════════════════════════════════════════════════════════
class TestFailLoudWhenRateMissing:
    @pytest.mark.parametrize('bad_rate', [None, 0, -1, 1.0, float('nan'), 'x'])
    def test_usd_row_excluded_not_summed_as_one_to_one(self, live_rows, bad_rate):
        out = convert_rows_to_twd(live_rows, usdtwd_rate=bad_rate)

        # ① 該檔被排除、且帶得出警示所需資訊
        assert out['any_needs_fx'] is True
        assert [r['ticker'] for r in out['excluded']] == ['BND']
        assert out['excluded'][0]['needs_fx'] is True
        assert out['excluded'][0]['fx_rate'] is None
        assert out['rate_used'] is None
        assert out['usd_tickers'] == ['BND']

        # ② 排除後的 rows 不含 BND → 任何總計都吃不到它
        assert 'BND' not in [r['ticker'] for r in out['rows']]
        _total = sum(r['current_value'] for r in out['rows'])
        assert _total == pytest.approx(_twd_only_total(live_rows))

        # ③ 這是本測試的核心：**絕不**等於「1 USD = 1 TWD 硬加」的結果
        _one_to_one = _twd_only_total(live_rows) + 14496.0
        assert not math.isclose(_total, _one_to_one, rel_tol=1e-9), (
            'USD 持股在沒有匯率時被以 1:1 併入 TWD 總額 —— 這正是 B1-a 的原始 bug'
        )

        # ④ 排除的那筆仍保有原幣值，畫面才能顯示「⚠️ 未納入」而不是憑空消失
        assert out['excluded'][0]['current_value'] == pytest.approx(14496.0)

    def test_no_disclosure_caption_without_rate(self):
        assert fx_disclosure_caption(None) == ''
        assert fx_disclosure_caption(1.0) == ''   # sanity 外 → 不得宣稱換過匯

    def test_disclosure_caption_carries_rate_and_as_of(self):
        _msg = fx_disclosure_caption(FX, as_of='2026-08-05', source='Yahoo:TWD=X:Close')
        assert '32.282' in _msg
        assert '2026-08-05' in _msg
        assert 'Yahoo:TWD=X:Close' in _msg


# ══════════════════════════════════════════════════════════════════
# 4. 殖利率：分子分母同幣別
# ══════════════════════════════════════════════════════════════════
class TestYieldSameCurrency:
    @staticmethod
    def _annual_twd(live_rows, rate):
        """跑真正的配息彙整路徑（build_monthly_dividend_rows）拿 TWD 年現金流。"""
        _holdings = []
        for r in live_rows:
            _d = r['dividend_received']
            _holdings.append({
                'ticker': r['ticker'],
                'name': r['ticker'],
                # 全年一次配完 —— 只驗幣別，不驗月份分配（那條在
                # test_etf_dividend_schedule.py）
                'monthly_distribution': {m: (_d if m == 1 else 0.0) for m in range(1, 13)},
                'n_payments': 4,
                'shares': r['shares'],
            })
        return build_monthly_dividend_rows(_holdings, usdtwd_rate=rate)

    def test_yield_numerator_and_denominator_are_both_twd(self, live_rows):
        _sched = self._annual_twd(live_rows, FX)
        _rows = convert_rows_to_twd(live_rows, usdtwd_rate=FX)['rows']
        _total_value = sum(r['current_value'] for r in _rows)
        _yoc = _sched['annual_total_twd'] / _total_value * 100

        # 分子 = 台股 7,030 + BND 584 USD × 匯率
        assert _sched['annual_total_twd'] == pytest.approx(7030.0 + 584.0 * FX)
        # 分母 = 已換匯總現值
        assert _total_value == pytest.approx(665_500.0, rel=5e-3)
        assert _yoc == pytest.approx(3.89, abs=0.15)

    def test_mixed_denominator_produces_the_1220_pct_lie(self, live_rows):
        """重現修前的 12.20%：分子換匯、分母沒換 → 虛胖約 3.1 倍。"""
        _sched = self._annual_twd(live_rows, FX)
        _buggy_denom = _twd_only_total(live_rows) + 14496.0      # 1:1 混算
        _buggy_yoc = _sched['annual_total_twd'] / _buggy_denom * 100

        _rows = convert_rows_to_twd(live_rows, usdtwd_rate=FX)['rows']
        _fixed_yoc = _sched['annual_total_twd'] / sum(
            r['current_value'] for r in _rows) * 100

        assert _buggy_yoc == pytest.approx(12.20, abs=0.2)
        # 關鍵行為變更：舊值越過 YIELD_MID → 觸發「殖利率優異、以息養股達成」強結論；
        # 新值不越過 → 該強結論不該再出現。
        assert _buggy_yoc > YIELD_MID
        assert _fixed_yoc < YIELD_MID
        assert _buggy_yoc / _fixed_yoc == pytest.approx(3.14, abs=0.15)

    def test_dividend_dropped_when_rate_missing(self, live_rows):
        """沒匯率時，USD 配息不得進 TWD 年現金流（分子也要 fail loud）。"""
        _sched = self._annual_twd(live_rows, None)
        assert _sched['any_needs_fx'] is True
        assert _sched['annual_total_twd'] == pytest.approx(7030.0)

    def test_rate_outside_sanity_rejected_by_schedule(self, live_rows):
        """1.0 這種「看起來是數字」的髒匯率也要被擋（原碼只擋 <= 0）。"""
        _sched = self._annual_twd(live_rows, 1.0)
        assert _sched['rate_used'] is None
        assert _sched['any_needs_fx'] is True
        assert _sched['annual_total_twd'] == pytest.approx(7030.0)


# ══════════════════════════════════════════════════════════════════
# 5. AST 原始碼守衛（單一換匯點結構）
# ══════════════════════════════════════════════════════════════════
#: 金額欄位 —— 這些欄的跨檔加總必須發生在換匯之後
_FX_MONEY_FIELDS = frozenset({
    'current_value', 'cost', 'capital_gain', 'dividend_received', 'total_pnl',
})


def _load(rel_path):
    """讀檔 → `(原始碼字串, AST)`。守衛一律走 AST，不做 regex/naive 字串掃描。"""
    _src = (REPO / rel_path).read_text(encoding='utf-8')
    return _src, ast.parse(_src)


def _at(rel_path, src, lineno):
    """失敗訊息用：`檔名:行號: <該行原始碼原文>`。"""
    _lines = src.splitlines()
    _text = _lines[lineno - 1].strip() if 0 < lineno <= len(_lines) else '<行號超出範圍>'
    return f'{rel_path}:{lineno}: {_text}'


def _func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f'找不到函式 {name}()')


def _calls_named(node, name):
    """回傳 node 內所有呼叫 `name(...)` 或 `x.name(...)` 的 Call 節點。"""
    out = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        _f = sub.func
        if (isinstance(_f, ast.Name) and _f.id == name) or \
           (isinstance(_f, ast.Attribute) and _f.attr == name):
            out.append(sub)
    return out


def _money_sum_calls(node):
    """`sum(r['current_value'] for r in rows)` 這類金額加總的 Call 節點。

    以 AST `Subscript` 的常數 key 判斷，不做字串比對 → 註解與 docstring
    天生不可能命中。
    """
    out = []
    for sub in ast.walk(node):
        if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                and sub.func.id == 'sum'):
            continue
        for inner in ast.walk(sub):
            if (isinstance(inner, ast.Subscript)
                    and isinstance(inner.slice, ast.Constant)
                    and inner.slice.value in _FX_MONEY_FIELDS):
                out.append(sub)
                break
    return out


class TestSingleConversionPointStructure:
    def test_convert_is_called_before_any_money_sum(self):
        _src, _tree = _load(_PORTFOLIO_TAB)
        _fn = _func(_tree, 'render_etf_portfolio')

        _conv = _calls_named(_fn, 'convert_rows_to_twd')
        assert _conv, (
            f'{_PORTFOLIO_TAB}:render_etf_portfolio() 沒有呼叫 convert_rows_to_twd '
            '—— 單一換匯點不見了，跨幣別加總會回到 1 USD = 1 TWD（§4.1）。')
        _conv_line = min(c.lineno for c in _conv)

        _sums = _money_sum_calls(_fn)
        assert _sums, '找不到任何金額加總 —— 測試假設過期，請更新 _FX_MONEY_FIELDS'
        _early = [s for s in _sums if s.lineno < _conv_line]
        assert not _early, (
            '以下金額加總發生在換匯之前（會把 USD 當 TWD 加）：\n  '
            + '\n  '.join(_at(_PORTFOLIO_TAB, _src, s.lineno) for s in _early)
            + f'\n換匯點在 {_at(_PORTFOLIO_TAB, _src, _conv_line)}')

    def test_no_second_fx_fetch_inside_render(self):
        """匯率只能在 `_fetch_usdtwd_spot()` 抓一次。

        原碼在配息段又自己抓了一次 `fetch_etf_price('TWD=X')`，導致
        「分子用 A 匯率、分母沒用匯率」的口徑分裂。
        """
        _src, _tree = _load(_PORTFOLIO_TAB)
        _fn = _func(_tree, 'render_etf_portfolio')
        _bad = []
        for _c in _calls_named(_fn, 'fetch_etf_price'):
            for _a in _c.args:
                if isinstance(_a, ast.Constant) and _a.value == 'TWD=X':
                    _bad.append(_c)
        assert not _bad, (
            'render_etf_portfolio() 內出現第二條匯率抓取路徑：\n  '
            + '\n  '.join(_at(_PORTFOLIO_TAB, _src, c.lineno) for c in _bad)
            + '\n匯率請統一走 _fetch_usdtwd_spot()（整頁同一個 rate + 同一個 as-of）。')

    def test_fx_fetcher_never_returns_a_fabricated_rate(self):
        """`_fetch_usdtwd_spot()` 的「匯率」欄位不得是寫死的數字（§1）。

        只看**回傳 tuple 的第 0 個元素**（＝匯率本身），不用 `ast.walk` 掃整棵樹
        —— 否則 `.iloc[-1]` 裡的 `1` 會變成假紅燈。
        """
        _src, _tree = _load(_PORTFOLIO_TAB)
        _fn = _func(_tree, '_fetch_usdtwd_spot')
        _returns = [n for n in ast.walk(_fn)
                    if isinstance(n, ast.Return) and n.value is not None]
        assert _returns, '_fetch_usdtwd_spot() 沒有 return —— 測試假設過期'
        _bad = []
        for _r in _returns:
            _rate_node = (_r.value.elts[0]
                          if isinstance(_r.value, ast.Tuple) and _r.value.elts
                          else _r.value)
            if isinstance(_rate_node, ast.Constant) and \
                    isinstance(_rate_node.value, (int, float)) and \
                    not isinstance(_rate_node.value, bool):
                _bad.append(_r)
        assert not _bad, (
            '_fetch_usdtwd_spot() 回傳了寫死的匯率常數（＝把美元當台幣的溫床）：\n  '
            + '\n  '.join(_at(_PORTFOLIO_TAB, _src, r.lineno) for r in _bad))

    def test_yield_numerator_and_denominator_from_same_conversion(self):
        """`_yoc` 的分子必須源自 `annual_total_twd`、分母必須是 `total_value`。

        分子在 production 是經過一層區域變數別名的（`_x = _sched['annual_total_twd']`
        → `_yoc = _x / total_value`），所以這裡**解析一層 Name 別名**再比對，
        不做整段字串比對（否則改個變數名就假紅）。
        """
        _src, _tree = _load(_PORTFOLIO_TAB)
        _fn = _func(_tree, 'render_etf_portfolio')

        # 函式內所有 `名稱 = 值` 的來源段（供別名解析）
        _amap = {}
        for _n in ast.walk(_fn):
            if isinstance(_n, ast.Assign) and len(_n.targets) == 1 and \
                    isinstance(_n.targets[0], ast.Name):
                _amap[_n.targets[0].id] = ast.get_source_segment(_src, _n.value) or ''

        _assigns = [n for n in ast.walk(_fn)
                    if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == '_yoc'
                            for t in n.targets)]
        assert _assigns, f'{_PORTFOLIO_TAB} 找不到 _yoc 指派 —— 測試假設過期'
        for _a in _assigns:
            _names = {n.id for n in ast.walk(_a.value) if isinstance(n, ast.Name)}
            _seg = ast.get_source_segment(_src, _a.value) or ''
            assert 'total_value' in _names, (
                '組合殖利率的分母不是已換匯的 total_value：\n  '
                + _at(_PORTFOLIO_TAB, _src, _a.lineno) + f'\n  expr = {_seg}')
            _num_ok = any('annual_total_twd' in _amap.get(_n, '') for _n in _names) \
                or 'annual_total_twd' in _seg
            assert _num_ok, (
                '組合殖利率的分子未追溯到已換匯的 annual_total_twd '
                '（分子分母混幣 = B1-a 的 12.20% 假殖利率）：\n  '
                + _at(_PORTFOLIO_TAB, _src, _a.lineno) + f'\n  expr = {_seg}')

    def test_l2_fx_module_has_no_io(self):
        """`portfolio_fx` 屬 L2 純函式：不得 import requests / yfinance / streamlit。"""
        _rel = 'src/compute/etf/portfolio_fx.py'
        _src, _tree = _load(_rel)
        _banned = {'requests', 'yfinance', 'streamlit', 'FinMind'}
        _bad = []
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.Import):
                _names = [a.name.split('.')[0] for a in _n.names]
            elif isinstance(_n, ast.ImportFrom):
                _names = [(_n.module or '').split('.')[0]]
            else:
                continue
            if _banned & set(_names):
                _bad.append(_n)
        assert not _bad, (
            'L2 純函式模組出現 I/O import（§8.2）：\n  '
            + '\n  '.join(_at(_rel, _src, n.lineno) for n in _bad))
