"""tests/test_etf_total_return_no_double_count.py — 2026-08-25

釘住 `etf_calc.calc_total_return_1y` **不得重複計息**。

背景(production bug):原式為

    (p_end - p_start + div_sum) / p_start

但 `df['Close']` 一路來自 `etf_fetch._fetch_etf_price_max` 的
`yf.Ticker(t).history(period='max', auto_adjust=True)` —— **已還原權息**,
`(p_end - p_start) / p_start` 本身就已經是含息總報酬。再加現金配息 = 算兩次。

代數後果(r = 真實總報酬,y = 殖利率,分母同為最新收盤價):

    畫面值 = r + y(1 + r)
    「賺息賠本」判定式 `畫面值 < y` ⟺ r(1 + y) < 0 ⟺ **r < 0**

→ 殖利率被代數消掉,紅燈實際問的是「總報酬是不是負的」,而 UI 寫「總報酬 <
殖利率」—— 那句話從來沒被執行過。既有測試只驗 `is None` / `is not None`,
不驗數值,所以這個 bug 活了下來;本檔專釘**數值**。

⚠️ 給後人:本檔任一測試變紅,最可能的原因就是有人把 `+ div_sum` 加回去了。
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from unittest.mock import patch

import pandas as pd
import pytest

from src.compute.etf.etf_calc import calc_current_yield, calc_total_return_1y


def _flat_or_ramp(p_start: float, p_end: float, n_days: int = 400) -> pd.DataFrame:
    """日頻還原價序列:窗內第一列 = p_start、最後一列 = p_end。

    用 freq='D' 是為了讓 `cutoff = index[-1] - 365d` 剛好落在某一列上,
    使 1 年窗的 p_start 完全可預測(整段常數 + 最後一列改值)。
    """
    idx = pd.date_range(end='2026-08-01', periods=n_days, freq='D')
    close = [p_start] * n_days
    close[-1] = p_end
    return pd.DataFrame({'Close': close}, index=idx)


def _divs(amount: float, days_ago: int = 100) -> pd.Series:
    """單筆現金配息(yfinance `Ticker(t).dividends` 口徑:原始配息,未還原)。"""
    return pd.Series([amount], index=pd.to_datetime(['2026-08-01'])
                     - pd.Timedelta(days=days_ago))


def _legacy_value(df: pd.DataFrame, divs: pd.Series) -> float:
    """修正前的舊算式(重複計息)—— 測試用來證明「新值 ≠ 舊值」。"""
    cutoff = df.index[-1] - pd.Timedelta(days=365)
    d1 = df[df.index >= cutoff]
    p_start = float(d1['Close'].iloc[0])
    p_end = float(d1['Close'].iloc[-1])
    _didx = divs.index.tz_localize(None) if (not divs.empty and divs.index.tz is not None) else divs.index
    div_sum = float(divs[_didx >= cutoff].sum()) if not divs.empty else 0.0
    return round((p_end - p_start + div_sum) / p_start * 100, 2)


# ── A. 數值:有配息時,配息不得再被加一次 ──────────────────────────────

def test_with_dividend_and_price_up_does_not_add_dividend_again():
    """有配息 + 價格上漲:還原價漲 10% → 10.00%,不是 15.00%。"""
    df = _flat_or_ramp(100.0, 110.0)
    divs = _divs(5.0)
    r = calc_total_return_1y(df, require_full_period=True)
    assert r == pytest.approx(10.0, abs=1e-9), f'還原價報酬應為 10.00%,得到 {r}'
    assert _legacy_value(df, divs) == pytest.approx(15.0, abs=1e-9), '舊算式基準走樣'
    assert r != pytest.approx(_legacy_value(df, divs), abs=1e-9), '配息被算了兩次'


def test_with_dividend_and_flat_price_is_zero_not_the_yield():
    """有配息 + 價格持平(r≈0)—— 最容易變色的區間,也是燈號會反轉的證據。

    修正前:畫面值 = 0 + y(1+0) = y → `y < y` 為 False → 假🟢綠燈。
    修正後:畫面值 = 0 → `0 < y` 為 True → 🔴 賺息賠本(這才是 UI 寫的那句)。
    """
    df = _flat_or_ramp(100.0, 100.0)
    divs = _divs(5.0)
    r = calc_total_return_1y(df, require_full_period=True)
    y = calc_current_yield(df, divs)
    assert r == pytest.approx(0.0, abs=1e-9), f'價格持平的還原價報酬應為 0.00%,得到 {r}'
    assert y == pytest.approx(5.0, abs=1e-9)
    assert r < y, '價格持平 + 有配息 → 判定式必須成立(修正前恰好相等而不成立)'
    assert _legacy_value(df, divs) == pytest.approx(y, abs=1e-9), \
        '舊算式在此恰好等於殖利率 —— 正是紅燈從不觸發的原因'


def test_with_dividend_and_price_down_still_red_but_value_changes():
    """有配息 + 價格下跌:修前修後都紅,但數值不同(修前虛高)。"""
    df = _flat_or_ramp(100.0, 90.0)
    divs = _divs(5.0)
    r = calc_total_return_1y(df, require_full_period=True)
    assert r == pytest.approx(-10.0, abs=1e-9), f'還原價跌 10% → -10.00%,得到 {r}'
    assert _legacy_value(df, divs) == pytest.approx(-5.0, abs=1e-9)


# ── B. 無配息:修前修後必須完全相同(div_sum = 0)──────────────────────

def test_no_dividend_value_unchanged_by_the_fix():
    """無配息 → div_sum=0 → 新舊算式必須逐位相同(這條不該因本次修正而變)。"""
    df = _flat_or_ramp(100.0, 110.0)
    empty = pd.Series(dtype=float)
    r = calc_total_return_1y(df, require_full_period=True)
    assert r == pytest.approx(10.0, abs=1e-9)
    assert r == pytest.approx(_legacy_value(df, empty), abs=1e-9), \
        '無配息時新舊算式應完全一致'


# ── C. 邊界:require_full_period 年輕 ETF 路徑不受影響 ────────────────

def test_require_full_period_young_etf_still_returns_none():
    """跨度 300 天(< 365×0.9)+ require_full_period=True → 仍回 None(§1 寧缺勿假)。"""
    df = _flat_or_ramp(100.0, 110.0, n_days=300)
    assert calc_total_return_1y(df, require_full_period=True) is None


def test_require_full_period_mature_etf_still_computes():
    """跨度足夠 → 照常算,不誤殺老牌 ETF。"""
    df = _flat_or_ramp(100.0, 110.0, n_days=500)
    assert calc_total_return_1y(df, require_full_period=True) == pytest.approx(10.0, abs=1e-9)


def test_default_require_full_period_false_keeps_short_window_behaviour():
    """預設 False → 短窗仍算得出數字(既有呼叫端行為不變)。"""
    df = _flat_or_ramp(100.0, 110.0, n_days=300)
    r = calc_total_return_1y(df)
    assert r is not None and r == pytest.approx(10.0, abs=1e-9)


def test_empty_and_single_row_edges():
    """空集 / 單筆 → 0.0(§4.6 邊界,行為與修正前相同)。"""
    assert calc_total_return_1y(pd.DataFrame({'Close': []})) == 0.0
    _one = pd.DataFrame({'Close': [100.0]}, index=pd.to_datetime(['2026-08-01']))
    assert calc_total_return_1y(_one) == 0.0


# ── D. 反向守衛:讓「把配息加回來」這件事做不到 / 做了就紅 ──────────────

def test_legacy_positional_divs_call_fails_loud():
    """舊簽章 `f(df, divs)` 必須當場 TypeError(§1 Fail Loud)。

    `require_full_period` 刻意設為 keyword-only:否則漏改的呼叫端會把 Series
    綁到旗標,`if require_full_period:` 觸發 ValueError 後被函式內的
    `except Exception` 吞成 0.0 —— 靜默的錯數字比炸掉更危險。
    """
    df = _flat_or_ramp(100.0, 110.0)
    with pytest.raises(TypeError):
        calc_total_return_1y(df, _divs(5.0))          # type: ignore[misc]


def test_signature_has_no_dividend_parameter():
    """簽章不得再出現配息參數 —— 擋「以 keyword 偷偷加回來」這種最刁鑽的回歸。

    (實測:只有數值斷言的話,`divs` 若以 `divs=None` 可選參數加回來,
     不傳 divs 的直呼測試全部照過;本條 + AST 本體掃描 + 端到端戰情室三者
     合起來才封得住。)
    """
    assert list(inspect.signature(calc_total_return_1y).parameters) == \
        ['df', 'require_full_period'], \
        f'簽章被改動:{inspect.signature(calc_total_return_1y)}'


def test_function_body_mentions_no_dividend_term():
    """實作本體(不含 docstring)不得再出現任何配息項。

    docstring 會刻意提到 div_sum(解釋為何不能加),所以只掃 AST 的 body。
    """
    _fn = ast.parse(textwrap.dedent(inspect.getsource(calc_total_return_1y))).body[0]
    _body = _fn.body
    if _body and isinstance(_body[0], ast.Expr) and isinstance(_body[0].value, ast.Constant):
        _body = _body[1:]                              # 去掉 docstring
    _src = '\n'.join(ast.unparse(n) for n in _body).lower()
    assert 'div' not in _src, f'實作又出現配息項 —— 重複計息 bug 回歸:\n{_src}'


# ── E. 端到端:戰情室核心燈號真的會變色(UI 可見後果)────────────────────

@patch('src.compute.etf.etf_calc._get_etf_launch_price', return_value=None)
@patch('src.compute.etf.etf_calc.calc_premium_discount', return_value={'premium_pct': None})
@patch('src.compute.etf.etf_calc.fetch_etf_info', return_value={})
@patch('src.compute.etf.etf_calc.fetch_etf_dividends')
@patch('src.compute.etf.etf_calc.fetch_etf_price')
def test_warroom_core_flat_price_with_dividend_turns_red(mock_price, mock_divs, *_):
    """價格持平 + 有配息 → 🔴 賺息賠本。修正前此情境恰為 y<y=False → 假🟢。"""
    from src.compute.etf.etf_calc import _compute_etf_warroom_row
    mock_price.return_value = _flat_or_ramp(100.0, 100.0)
    mock_divs.return_value = _divs(5.0)
    row = _compute_etf_warroom_row('TEST-FLAT-DIV', '持平配息', '核心')
    assert row['1年含息報酬%'] == pytest.approx(0.0, abs=1e-9)
    assert row['年化配息率%'] == pytest.approx(5.0, abs=1e-9)
    assert '🔴 賺息賠本' in row['健康燈號'], row['健康燈號']


@patch('src.compute.etf.etf_calc._get_etf_launch_price', return_value=None)
@patch('src.compute.etf.etf_calc.calc_premium_discount', return_value={'premium_pct': None})
@patch('src.compute.etf.etf_calc.fetch_etf_info', return_value={})
@patch('src.compute.etf.etf_calc.fetch_etf_dividends')
@patch('src.compute.etf.etf_calc.fetch_etf_price')
def test_warroom_core_price_up_with_dividend_stays_green(mock_price, mock_divs, *_):
    """價格上漲 10% + 殖利率 4.5% → 10 ≥ 4.5 → 🟢(確認沒有把綠燈一起殺掉)。"""
    from src.compute.etf.etf_calc import _compute_etf_warroom_row
    mock_price.return_value = _flat_or_ramp(100.0, 110.0)
    mock_divs.return_value = _divs(5.0)
    row = _compute_etf_warroom_row('TEST-UP-DIV', '上漲配息', '核心')
    assert row['1年含息報酬%'] == pytest.approx(10.0, abs=1e-9)
    assert '🟢' in row['健康燈號'], row['健康燈號']


# ── F. 兩座戰情室對稱性:同一檔 ETF 不得給出相反的「吃本金」結論 ──────────
#
# 2026-08-25 稽核最有價值的發現:修正前兩條路對同一輸入會**互相打臉** ——
#   存股戰情站 `dividend_station.total_return_pct`(end/start − 1,還原價,本來就對)
#     → 判 🔴 吃本金
#   ETF 追蹤戰情室 `etf_calc.calc_total_return_1y`(多加一次配息,虛高)
#     → 判 🟢 體質健康
# 修正後兩者定義收斂。⚠️ `dividend_station.total_return_pct` 那條路**不可以動**,
# 它本來就是對的;本節是拿它當**不動的基準**來釘 etf_calc。

def _station_total_return(df: pd.DataFrame) -> float:
    """存股戰情站那條路的總報酬(`dividend_station.total_return_pct`)。

    站端取 `_close_before(365)` = 「≤ cutoff 的最後一筆」,etf_calc 取
    「≥ cutoff 的第一筆」—— 日頻下兩者相鄰;本檔合成序列在該區間為常數,
    故兩者同值,可直接比對定義本身。
    """
    from src.compute.etf import dividend_station as ds
    cutoff = df.index[-1] - pd.Timedelta(days=365)
    _sub = df['Close'].loc[:cutoff]
    return ds.total_return_pct(float(_sub.iloc[-1]), float(df['Close'].iloc[-1]))


@pytest.mark.parametrize('p_end,expected', [(110.0, 10.0), (100.0, 0.0), (90.0, -10.0)])
def test_two_warrooms_agree_on_total_return_definition(p_end, expected):
    """兩條路的「近一年含息總報酬」必須是同一個數 —— 加回 div_sum 就會分岔。"""
    df = _flat_or_ramp(100.0, p_end)
    etf_side = calc_total_return_1y(df, require_full_period=True)
    station_side = _station_total_return(df)
    assert etf_side == pytest.approx(expected, abs=1e-9)
    assert etf_side == pytest.approx(station_side, abs=1e-9), (
        f'ETF 追蹤戰情室 {etf_side} vs 存股戰情站 {station_side} —— '
        '兩座戰情室對同一檔 ETF 給出不同的總報酬'
    )


@pytest.mark.parametrize('p_end,expect_eats_capital', [(110.0, False), (100.0, True), (90.0, True)])
@patch('src.compute.etf.etf_calc._get_etf_launch_price', return_value=None)
@patch('src.compute.etf.etf_calc.calc_premium_discount', return_value={'premium_pct': None})
@patch('src.compute.etf.etf_calc.fetch_etf_info', return_value={})
@patch('src.compute.etf.etf_calc.fetch_etf_dividends')
@patch('src.compute.etf.etf_calc.fetch_etf_price')
def test_two_warrooms_agree_on_eats_capital_verdict(
        mock_price, mock_divs, _m_info, _m_prem, _m_launch, p_end, expect_eats_capital):
    """同一組輸入 → 兩座戰情室的「吃本金與否」結論必須一致。"""
    from src.compute.etf import dividend_station as ds
    from src.compute.etf.etf_calc import _compute_etf_warroom_row

    df = _flat_or_ramp(100.0, p_end)
    divs = _divs(5.0)
    mock_price.return_value = df
    mock_divs.return_value = divs
    _y = calc_current_yield(df, divs)

    # 存股戰情站(基準,不動)
    station_flag = ds.health_a(_station_total_return(df), _y)
    station_eats = (station_flag.level == '🔴')

    # ETF 追蹤戰情室
    row = _compute_etf_warroom_row(f'TEST-SYM-{p_end}', '對稱性', '核心')
    etf_eats = ('賺息賠本' in row['健康燈號'])

    assert station_eats == expect_eats_capital, f'基準走樣:{station_flag.msg}'
    assert etf_eats == station_eats, (
        f'兩座戰情室結論相反 —— ETF 戰情室「{row["健康燈號"]}」 '
        f'vs 存股戰情站「{station_flag.msg}」'
    )


@pytest.mark.parametrize('p_end,expected_action', [
    (110.0, '正常續抱領息'),
    (100.0, '考慮換股（核心紀律不容侵蝕本金）'),
])
@patch('src.compute.etf.etf_calc._get_etf_launch_price', return_value=None)
@patch('src.compute.etf.etf_calc.calc_premium_discount', return_value={'premium_pct': None})
@patch('src.compute.etf.etf_calc.fetch_etf_info', return_value={})
@patch('src.compute.etf.etf_calc.fetch_etf_dividends')
@patch('src.compute.etf.etf_calc.fetch_etf_price')
def test_warroom_action_hint_follows_the_lamp(
        mock_price, mock_divs, _m_info, _m_prem, _m_launch, p_end, expected_action):
    """『動作建議』是獨立欄位(也進 AI prompt),必須與燈號同步翻面。"""
    from src.compute.etf.etf_calc import _compute_etf_warroom_row
    mock_price.return_value = _flat_or_ramp(100.0, p_end)
    mock_divs.return_value = _divs(5.0)
    row = _compute_etf_warroom_row(f'TEST-ACT-{p_end}', '動作建議', '核心')
    assert row['動作建議'] == expected_action, (row['健康燈號'], row['動作建議'])
