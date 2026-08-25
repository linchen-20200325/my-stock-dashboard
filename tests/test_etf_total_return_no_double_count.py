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

2026-08-25 補(G / H 節):A~F 節盯的是**函式**(簽章 / 本體 / 一個戰情室消費者),
獨立驗證組實測證明那樣有洞 —— 把 `+ div_sum` 加在**呼叫端**,全套件 0 紅。
這個 bug 是**管線**的 bug,不是函式的 bug。故:
  G 節 = 真實跑 `build_etf_score_row` 評分管線,盯出口的不變量(行為守衛);
  H 節 = 掃全部呼叫端(自動探,不寫死名單),擋回傳值就地被加減(結構守衛,
         它的極限寫在該節開頭,請一併讀)。
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


# ── G. 第 2 個 production 消費者:評分管線 build_etf_score_row ────────────
#
# 2026-08-25 獨立驗證組實測:上面 A~F 全部通過,**但**把 `+ div_sum` 加在
# `etf_scoring_helpers.build_etf_score_row` 的**呼叫端**(而不是函式本體),
# 全套件 0 紅 —— A/B 只盯 `calc_total_return_1y` 自己的簽章與本體,E/F 只覆蓋
# 三個 production 消費者裡的一個(`_compute_etf_warroom_row`)。
#
# 「這組守衛是**函式形狀**的守衛,但這個 bug 是**管線**的 bug。」
#
# 本節因此改盯**不變量**:同一組輸入餵進真實的 `build_etf_score_row`,
# 出口的 `total_ret_1y` / `dividend_health` / `composite` / 留觀換 verdict
# 必須是「沒有重複計息」該有的樣子。**刻意不**自己重算一次再比對 ——
# 那樣只是把 A 節的直呼測試換個地方寫,同一個洞會再出現一次。
#
# 判別帶只有 r≈0 附近(代數見檔頭):r=+10% 或 r=-10% 時重複計息只讓數字虛高,
# 燈不會翻面;唯有價格持平 + 有配息時 🔴/✅ 會整個顛倒。故主案例固定用它。

def _score_row(p_end: float, div_amount: float = 5.0, **kw) -> dict:
    """跑真實的 `build_etf_score_row`(只擋掉會走網路的折溢價)。

    ⚠️ 只 patch `calc_premium_discount`(它會打 TWSE / FinMind / yfinance),
    其餘 —— 含 `calc_total_return_1y` / `calc_current_yield` /
    `dividend_health_label` —— 全部走真貨,否則本節就退化成「盯函式」。
    """
    from src.compute.etf.etf_scoring_helpers import build_etf_score_row
    with patch('src.compute.etf.etf_calc.calc_premium_discount',
               return_value={'premium_pct': None, 'stale_nav': False}):
        return build_etf_score_row('TEST-SCORE', _flat_or_ramp(100.0, p_end),
                                   _divs(div_amount), {}, **kw)


def test_score_row_flat_price_with_dividend_is_zero_not_the_dividend():
    """價格持平 + 配息 5 元 → `total_ret_1y` 必須是 0.00,不是 5.00。

    重複計息版會得到 5.00(= 配息本身),因為還原價價差 0 又被加了一次現金配息。
    """
    row = _score_row(100.0)
    assert row['error'] is None, row['error']
    assert row['total_ret_1y'] == pytest.approx(0.0, abs=1e-9), (
        f"build_etf_score_row 出口的 1Y 總報酬 = {row['total_ret_1y']} —— "
        '價格持平時應為 0.00;得到 5.00 表示配息在呼叫端被加了第二次'
    )
    assert row['div_yield'] == pytest.approx(5.0, abs=1e-9)


def test_score_row_flat_price_with_dividend_labels_eats_capital():
    """同一列的 `dividend_health` 必須是 🔴 吃本金 −5.0pp,不是 ✅ 雙贏 +0.0pp。

    這是 UI 直接顯示的字串(多檔比較表「配息健康」欄 + 單檔頁研判卡)。
    重複計息版剛好得到 `✅ 雙贏 +0.0pp` —— 那個 `+0.0` 就是代數上殖利率被
    消掉的殘骸,看起來像「剛好打平」,其實是「本金被吃掉一整年的息」。
    """
    row = _score_row(100.0)
    assert row['dividend_health'] == '🔴 吃本金 -5.0pp', (
        f"配息健康標籤 = {row['dividend_health']!r};"
        "得到 '✅ 雙贏 +0.0pp' = 呼叫端重複計息(§1 錯的數字比沒有數字更危險)"
    )


def test_score_row_price_up_with_dividend_still_wins():
    """反向守衛:真的漲 10% 時不可被誤殺成 🔴 —— 綠燈路徑必須還在。"""
    row = _score_row(110.0)
    assert row['total_ret_1y'] == pytest.approx(10.0, abs=1e-9)
    assert row['dividend_health'].startswith('✅ 雙贏'), row['dividend_health']


@pytest.mark.parametrize('p_end,expected', [(110.0, 10.0), (100.0, 0.0), (90.0, -10.0)])
def test_score_row_agrees_with_the_station_baseline(p_end, expected):
    """評分管線出口 vs 存股戰情站基準(`dividend_station.total_return_pct`)。

    F 節釘的是 `calc_total_return_1y` 直呼 vs 基準;本條把**管線出口**也綁到
    同一個基準 —— 呼叫端做任何加工(不只 `+ div_sum`)都會讓兩邊分岔。
    ⚠️ 基準那條路不可動,它本來就是對的。
    """
    row = _score_row(p_end)
    baseline = _station_total_return(_flat_or_ramp(100.0, p_end))
    assert row['total_ret_1y'] == pytest.approx(expected, abs=1e-9)
    assert row['total_ret_1y'] == pytest.approx(baseline, abs=1e-9), (
        f"評分管線 {row['total_ret_1y']} vs 存股戰情站 {baseline} —— "
        '同一檔 ETF 在兩個畫面上的「近一年含息總報酬」不一樣'
    )


def test_score_row_feeds_switch_verdict_and_red_flag():
    """一路走到使用者真正看到的那句話:紅旗 + 留/觀察/換。

    `total_ret_1y` 在 `compute_etf_composite_score` 裡權重 0.25(7 維最大)、
    正規化跨距只有 15pp,所以虛高 5pp ≈ 綜合分 +0.083;`recommend_etf_action`
    又對「吃本金」設了 force downgrade 紅旗。兩者疊加 → 重複計息會把
    「考慮換」洗成「觀察」,而且連降級的理由都不會出現在畫面上。

    ⚠️ 這裡**不**寫死綜合分數值(它同時受 sharpe / mdd 正規化影響,別人調那些
    參數不該讓本檔變紅);只釘「修正版必須更保守」這個方向,以及紅旗必須存在。
    """
    from shared.etf_recommendation_thresholds import VERDICT_SWITCH
    from src.compute.etf.etf_helpers import dividend_health_label
    from src.compute.etf.etf_recommendation import recommend_etf_action
    from src.compute.etf.etf_scoring_helpers import compute_etf_composite_score

    row = _score_row(100.0)
    row['composite'], _stars = compute_etf_composite_score(row)
    verdict = recommend_etf_action(row)
    assert any('吃本金' in _f for _f in verdict['red_flags']), (
        f"「配息吃本金」紅旗沒有升起:{verdict['red_flags']}(row={row['dividend_health']!r})"
    )
    assert verdict['verdict'] == VERDICT_SWITCH, verdict

    # 對照組:只把 total_ret_1y 換成重複計息的值(其餘欄位一字不動),
    # 用來證明「差別確實來自這一個數字」,而不是本測試碰巧通過。
    _dbl = dict(row)
    _dbl['total_ret_1y'] = 5.0
    _dbl['dividend_health'] = dividend_health_label(
        _dbl['div_yield'], _dbl['total_ret_1y'], _dbl['cagr_3y'])
    _dbl['composite'], _ = compute_etf_composite_score(_dbl)
    assert row['composite'] < _dbl['composite'], '重複計息本來就會讓綜合分虛高'
    assert recommend_etf_action(_dbl)['verdict'] != VERDICT_SWITCH, (
        '對照組走樣:重複計息版本應該逃掉「考慮換」'
    )


# ── H. 第 3 個 production 消費者(etf_tab_single,L5)+ 未來新增的消費者 ────
#
# 為什麼這裡是**結構**守衛而不是像 G 節那樣的行為守衛 —— 誠實交代取捨:
#
# ⚠️ 2026-08-25 更新:本節原本描述的「② 獨立算式」**已經不存在了**(user 核准的
#    production 行為變更,見本節末 `test_single_tab_does_not_recompute_total_return`)。
#    以下這段保留原文,是為了讓後人看得懂那個洞長什麼樣、以及它是怎麼被封掉的。
#
# `etf_tab_single.render_etf_single` 是單一 924 行的 Streamlit render 函式。
# 它在**兩個地方**算同一個數字:
#   ① 🚦綜合研判卡 → `build_etf_score_row(ticker, df, divs, info, ...)`
#      → 已被 G 節行為覆蓋(同一份 df/divs,壞了 G 節會紅)
#   ② 策略一「近1年含息總報酬」→ 自己再呼一次 `calc_total_return_1y(df, ...)`
#      → 餵 st.metric + 🔴/🟢 警示框 + 「含息報酬 − 殖利率」pp 值 + 兩段 AI prompt
# ② 是獨立算式,G 節碰不到它。  ← **已於 2026-08-25 收掉:② 改讀 ① 那張 row**
#
# 要行為覆蓋 ② 必須真的跑 render:先過 session_state gate(`etf_s_active`)、
# 擋掉 4 個網路 fetcher + `get_macro_regime` + proxy secrets 探測 +
# `fetch_etf_zh_name` / `get_etf_expense_ratio_safe` / `calc_beta`,再讓它跑完
# 後面約 650 行(圖表 / 持股 / 新聞 / AI),最後還要用假的 `st.columns` 攔
# `st.metric` 才讀得回那個數字。約 150 行、且與 UI 排版順序強耦合 ——
# 任何版面調整都會讓它變紅,而「因為無關原因常常變紅的測試」正是會訓練後人
# 「改測試而不是改程式」的那種測試。加上本 repo 的 conftest 有一整套
# streamlit stub 汙染防治(`pytest_collection_finish` 身分還原 +
# `test_zz_streamlit_pollution_lock.py`),就是因為模組級 stub 曾經害 CI 全滅 ——
# 新增 stub 站點在這個 repo 是實測過的風險,不是假想。
#
# 折衷:本節只釘一件**呼叫端**的事 —— `calc_total_return_1y(...)` 的回傳值
# 不得就地被加減。這正是原 bug 最可能的復發寫法(原 commit 已寫明:這個 bug
# 能活下來,是因為沒有任何一行字擋住「怎麼沒加配息?我補一下」)。
#
# ⚠️ 本節的極限,講在前面:它是**形狀**守衛,拆成兩句就繞得過去 ——
#     t = calc_total_return_1y(df, require_full_period=True)
#     total_ret = t + div_sum / p_start * 100      ← 本節看不到
# 在 ① / 戰情室那兩條路上,G / E-F 節的行為守衛會接住這種寫法;
# 在 ② 這條路上**接不住**。要真正封死 ②,正解是讓它別自己再算一次
# (改讀研判卡那張 row 的 `total_ret_1y`)—— 那是 production 行為變更,
# 需要 user 核准,不在本次(只加測試)範圍內。
#
# ✅ **2026-08-25 已收**:user 核准後 ② 改讀 `_vrow['total_ret_1y']`,
#    `etf_tab_single` 不再呼叫 `calc_total_return_1y` —— 那條「拆成兩句」的繞法
#    在這條路上**沒有立足點了**(沒有回傳值可以就地加減)。要繞得改 L2 的
#    `build_etf_score_row` / `calc_total_return_1y` 本體,而那裡有 E/F/G 節的
#    **行為**守衛(真的比對數字)接住。下面 `test_single_tab_does_not_recompute_total_return`
#    釘住這件事不准回退。
#    ⚠️ 連帶降級:研判卡失敗時 `_vrow is None`,單檔頁**不退回自己算**,改顯示
#    「取不到」(§1 寧可炸掉不可造假)—— 退回自己算等於把洞留在最不容易被發現的
#    路徑上(研判卡都掛了,沒人會回頭查策略一的數字)。

def _production_files_calling_it() -> list:
    """自動探出所有呼叫 `calc_total_return_1y` 的 production 檔(不寫死名單)。

    §8.2.A.0 規則 2:窮舉名單只要漏一筆就變成沒人看守的軟例外。改成每次現場掃,
    將來第 4 個消費者出現時自動納管,不必有人記得回來改這份名單。
    """
    import pathlib
    _root = pathlib.Path(__file__).resolve().parents[1]
    return [_p for _p in sorted((_root / 'src').rglob('*.py'))
            if 'calc_total_return_1y' in _p.read_text(encoding='utf-8')]


def test_production_callers_exist_so_this_guard_is_not_vacuous():
    """先證明掃得到東西 —— 否則下面那條會在「找不到任何檔案」時假通過。

    ⚠️ 2026-08-25 起 `etf_tab_single.py` **不再是呼叫端**(② 已改讀研判卡那張 row),
    故不再列入必須掃到的名單。它現在仍會被 `_production_files_calling_it()` 掃出來,
    但那只是因為檔內註解提到這個函式名 —— 掃不掃得到它都不影響本守衛的有效性,
    真正的呼叫端是下面兩個 L2 檔。
    """
    _files = _production_files_calling_it()
    _names = {_f.name for _f in _files}
    assert _names >= {'etf_calc.py', 'etf_scoring_helpers.py'}, (
        f'兩個已知 production 呼叫端沒被掃到(掃到:{sorted(_names)})—— '
        '守衛失效或檔案被搬走'
    )


def test_no_production_caller_adds_anything_to_the_return_value():
    """呼叫端不得就地對 `calc_total_return_1y(...)` 的回傳值做加減。

    回傳值已經是「近一年含息總報酬 %」;在呼叫端再 `+ 配息` 就是把同一筆息
    算第二次(2026-08-25 的 production bug 本體)。任何合法的單位換算都該
    發生在函式**內部**,不該散在三個呼叫端各寫一次。
    """
    _offenders = []
    for _f in _production_files_calling_it():
        _tree = ast.parse(_f.read_text(encoding='utf-8'), filename=str(_f))
        for _node in ast.walk(_tree):
            if not isinstance(_node, ast.BinOp):
                continue
            for _side in (_node.left, _node.right):
                if (isinstance(_side, ast.Call)
                        and getattr(_side.func, 'id', getattr(_side.func, 'attr', None))
                        == 'calc_total_return_1y'):
                    _offenders.append(
                        f'{_f.name}:{_node.lineno}: {ast.unparse(_node)}')
    assert not _offenders, (
        '有呼叫端對 calc_total_return_1y 的回傳值就地做算術 —— '
        '重複計息 bug 從呼叫端回歸:\n  ' + '\n  '.join(_offenders)
    )


# ── H-2. 單檔頁不准再自己算一次(2026-08-25 收掉 ② 之後的反向守衛)──────────
#
# 上面 H 節那段長註解描述的「② 獨立算式」已經被移除:`etf_tab_single` 的策略一
# 改讀 🚦 研判卡那張 row 的 `total_ret_1y`。本節釘住它**不准長回來**。
#
# 為什麼這條比 H 節的 BinOp 守衛強:H 節擋的是「回傳值就地加減」這個**形狀**,
# 拆成兩句就繞得過;本節擋的是「這個檔裡根本不該有第二次呼叫」——
# 沒有回傳值,就沒有東西可以被偷偷加減。


def _single_tab_tree():
    import pathlib
    _p = (pathlib.Path(__file__).resolve().parents[1]
          / 'src/ui/etf/etf_tab_single.py')
    return _p, ast.parse(_p.read_text(encoding='utf-8'), filename=str(_p))


def test_single_tab_does_not_recompute_total_return():
    """`etf_tab_single` 不得再呼叫 `calc_total_return_1y`(同頁第二套算式)。

    ⚠️ 後人看到本條紅燈:要修的是**程式**,不是測試。單檔頁的「近1年含息總報酬」
    只有一個合法來源 —— 🚦 研判卡的 `build_etf_score_row(...)['total_ret_1y']`。
    再開第二個入口,就是把 2026-08-25 修掉的那個 bug 的地形重新造出來
    (同一份 df、同一個數字、相隔約 100 行的兩個算式,而只有其中一個有行為守衛)。
    """
    _p, _tree = _single_tab_tree()
    _calls = [
        f'{_p.name}:{_n.lineno}: {ast.unparse(_n)}'
        for _n in ast.walk(_tree)
        if isinstance(_n, ast.Call)
        and getattr(_n.func, 'id', getattr(_n.func, 'attr', None)) == 'calc_total_return_1y'
    ]
    assert not _calls, (
        'etf_tab_single 又自己呼叫 calc_total_return_1y 了 —— 同頁第二套算式復活:\n  '
        + '\n  '.join(_calls)
    )


def test_single_tab_reads_total_return_from_the_verdict_row():
    """而且它必須**真的**改讀那張 row —— 不是把整段刪掉了事。

    只驗「沒有第二次呼叫」會在「有人把整個總報酬區塊刪掉」時假通過,
    所以這裡正面驗:檔內確實從 row 取 `total_ret_1y`。
    """
    _p, _ = _single_tab_tree()
    _src = _p.read_text(encoding='utf-8')
    assert "total_ret_1y" in _src, (
        '單檔頁找不到 total_ret_1y —— 策略一應改讀研判卡那張 row 的欄位'
    )
    assert "_vrow" in _src, '單檔頁找不到 _vrow(研判卡 row 變數)'


def test_single_tab_initialises_verdict_row_before_the_try_block():
    """降級不可以 NameError:`_vrow` 必須在 try 之外先綁定。

    研判卡整段包在 `try/except` 內,失敗時 `_vrow` 不會被賦值;策略一若直接讀它
    就是 `NameError` 炸掉整頁(比舊行為更糟)。這裡用 AST 確認 `_vrow` 的第一次
    賦值發生在**任何 Try 節點之外**,而不是靠讀註解相信它有做。
    """
    _p, _tree = _single_tab_tree()
    _fn = next(_n for _n in ast.walk(_tree)
               if isinstance(_n, ast.FunctionDef) and _n.name == 'render_etf_single')
    # 收集所有 Try 節點內部的 node id,用來判斷某個賦值是否落在 try 內
    _in_try = set()
    for _n in ast.walk(_fn):
        if isinstance(_n, ast.Try):
            for _sub in ast.walk(_n):
                _in_try.add(id(_sub))
    _binds = [_n for _n in ast.walk(_fn)
              if isinstance(_n, (ast.Assign, ast.AnnAssign))
              and any(getattr(_t, 'id', None) == '_vrow'
                      for _t in (_n.targets if isinstance(_n, ast.Assign) else [_n.target]))]
    assert _binds, 'render_etf_single 內找不到 _vrow 的賦值'
    _first = min(_binds, key=lambda _n: _n.lineno)
    assert id(_first) not in _in_try, (
        f'_vrow 的第一次賦值(line {_first.lineno})落在 try 區塊內 —— '
        '研判卡失敗時策略一會 NameError。請在 try 之前先 `_vrow = None`。'
    )


def test_single_tab_does_not_do_arithmetic_on_the_row_field():
    """收掉 ② 之後,「加回配息」唯一剩下的寫法是對 row 欄位動手 —— 也擋掉。

    誠實交代這條的**極限**(與 H 節同一類):這是**形狀**守衛。
    `_vrow['total_ret_1y'] + div` 會被抓到;先存成中間變數再加就抓不到:
        t = _vrow['total_ret_1y']
        total_ret = t + div_sum / p * 100        ← 本條看不到
    真正能接住任意寫法的只有「跑完 render 再讀畫面上那個數字」的行為守衛,
    而 H 節已經評估過:約 150 行 streamlit stub、與版面順序強耦合,且本 repo
    有 module 級 stub 汙染害 CI 全滅的實績(見 `test_zz_streamlit_pollution_lock.py`)。
    所以這裡的定位是「把最可能的復發寫法變貴」,不是「證明不可能復發」——
    別把它當成後者。
    """
    _p, _tree = _single_tab_tree()
    _bad = []
    for _n in ast.walk(_tree):
        if not isinstance(_n, ast.BinOp):
            continue
        for _side in (_n.left, _n.right):
            _hit = (
                # _vrow['total_ret_1y'] + x
                (isinstance(_side, ast.Subscript)
                 and isinstance(_side.slice, ast.Constant)
                 and _side.slice.value == 'total_ret_1y')
                # _vrow.get('total_ret_1y') + x
                or (isinstance(_side, ast.Call)
                    and getattr(_side.func, 'attr', None) == 'get'
                    and _side.args
                    and isinstance(_side.args[0], ast.Constant)
                    and _side.args[0].value == 'total_ret_1y')
            )
            if _hit:
                _bad.append(f'{_p.name}:{_n.lineno}: {ast.unparse(_n)}')
    assert not _bad, (
        '單檔頁對研判卡 row 的 total_ret_1y 就地做算術 —— '
        '重複計息 bug 換個入口回歸:\n  ' + '\n  '.join(_bad)
    )
