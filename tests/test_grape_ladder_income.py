"""葡萄串領息法 — evaluate_income_ladder / suggest_fill_for_gaps 純函式測試。

守衛「葡萄串主視圖改吃使用者持股」：evaluate_income_ladder 就 user 實際持有的
tickers 逐檔取配息 profile（get_pay_profile），算覆蓋 / 缺口 / 待觀察 / 每月配息名單。
§1 誠實原則：無配息歷史的 ETF 貢獻 0 月、不捏造；缺月誠實列出；**月配 ETF 新上市未滿
一年、某月尚未輪到 → 待觀察（黃），不誤標永久缺口（紅）、不亂建議補檔、也不塗綠假裝已配。**

以 monkeypatch get_pay_profile / get_pay_months 注入假資料，測純邏輯（不觸真 yfinance）。
"""
import src.ui.tabs.grape_ladder as gl


def _patch_pay_profile(monkeypatch, table: dict):
    """把 grape_ladder.get_pay_profile 換成查表。

    table value 可為:
      - set[int]           → {'months': set, 'n_payments': len(set)}（次數=不同月數）
      - (set[int], int)    → {'months': set, 'n_payments': n}（明確指定次數，用來測月配門檻）
    未知 ticker → 空 profile（months 空、n_payments 0）。
    """
    def _mk(v):
        if isinstance(v, tuple):
            _months, _n = v
            return {'months': set(_months), 'n_payments': int(_n)}
        return {'months': set(v), 'n_payments': len(set(v))}
    monkeypatch.setattr(gl, 'get_pay_profile',
                        lambda t, *a, **k: _mk(table.get(t, set())))


def _patch_pay_months(monkeypatch, table: dict[str, set[int]]):
    """補缺建議走 get_pay_months（未改動），單獨 patch 供 suggest_fill 測試。"""
    monkeypatch.setattr(gl, 'get_pay_months',
                        lambda t, *a, **k: set(table.get(t, set())))


def test_full_coverage_three_etfs(monkeypatch):
    """3 檔錯開（1/4/7/10、2/5/8/11、3/6/9/12）→ 覆蓋全 12 月、零缺口。"""
    _patch_pay_profile(monkeypatch, {
        'A.TW': {1, 4, 7, 10},
        'B.TW': {2, 5, 8, 11},
        'C.TW': {3, 6, 9, 12},
    })
    res = gl.evaluate_income_ladder(['A.TW', 'B.TW', 'C.TW'])
    assert res['covered_months'] == list(range(1, 13))
    assert res['gap_months'] == []
    assert res['pending_months'] == []
    assert res['coverage_pct'] == 100.0
    assert res['holdings_count'] == 3
    assert res['no_data_tickers'] == []
    assert res['month_map'][1] == ['A.TW']
    assert res['month_map'][2] == ['B.TW']
    assert res['month_map'][12] == ['C.TW']


def test_gaps_reported_honestly(monkeypatch):
    """只有季配（1/4/7/10）→ 缺 2,3,5,6,8,9,11,12 為**真缺口**（非月配 → 不待觀察）。"""
    _patch_pay_profile(monkeypatch, {'X.TW': {1, 4, 7, 10}})   # n_payments=4 → 季配
    res = gl.evaluate_income_ladder(['X.TW'])
    assert res['covered_months'] == [1, 4, 7, 10]
    assert res['gap_months'] == [2, 3, 5, 6, 8, 9, 11, 12]
    assert res['pending_months'] == []
    assert res['young_monthly_tickers'] == []
    assert res['coverage_pct'] == round(4 / 12 * 100, 1)
    assert res['per_ticker']['X.TW'] == [1, 4, 7, 10]


def test_young_monthly_missing_month_is_pending_not_gap(monkeypatch):
    """回歸（實機 bug）：月配 ETF 上市未滿一年、缺九月 → 待觀察，**非**紅缺口。

    00980D.TWO 是 2025-10 掛牌的月配主動 ETF，除息史 2025-10→2026-08 = 月份
    {10,11,12,1..8}，唯一缺 9（去年九月未上市、今年九月還沒到）。它是月配（≥10 次/年）
    但只觀察到 11 個月 → 九月應標待觀察，不該報永久缺口、不該亂建議補檔。"""
    _patch_pay_profile(monkeypatch, {
        '00980D.TWO': ({10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8}, 11),  # 月配、觀察 11 月
    })
    res = gl.evaluate_income_ladder(['00980D.TWO'])
    assert res['covered_months'] == [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12]
    assert res['gap_months'] == []                 # 無**結構性**缺口
    assert res['pending_months'] == [9]            # 九月＝待觀察
    assert res['young_monthly_tickers'] == ['00980D.TWO']
    # §1：待觀察不塗綠 → 覆蓋率仍誠實為 11/12
    assert res['coverage_pct'] == round(11 / 12 * 100, 1)


def test_mature_monthly_full_coverage(monkeypatch):
    """月配且已觀察滿 12 月 → 全覆蓋，無缺口無待觀察（不會誤判為新上市）。"""
    _patch_pay_profile(monkeypatch, {
        'M.TW': (set(range(1, 13)), 13),   # 月配、13 次、12 個月全到
    })
    res = gl.evaluate_income_ladder(['M.TW'])
    assert res['covered_months'] == list(range(1, 13))
    assert res['gap_months'] == []
    assert res['pending_months'] == []
    assert res['young_monthly_tickers'] == []


def test_young_monthly_absorbs_quarterly_gaps(monkeypatch):
    """組合含月配新上市 ETF → 所有未覆蓋月皆待觀察（月配成熟後必補齊每月）。"""
    _patch_pay_profile(monkeypatch, {
        'MON.TW': ({6, 7, 8}, 3 + 7),   # 月配（n=10）但只觀察到 6/7/8（很新）
    })
    res = gl.evaluate_income_ladder(['MON.TW'])
    assert res['covered_months'] == [6, 7, 8]
    assert res['gap_months'] == []
    assert res['pending_months'] == [1, 2, 3, 4, 5, 9, 10, 11, 12]


def test_per_month_contributors_multiple_and_sorted(monkeypatch):
    """同月多檔配息 → month_map 該月列出全部且排序。"""
    _patch_pay_profile(monkeypatch, {
        'B.TW': {2, 5, 8, 11},
        'A.TW': {2, 8},
    })
    res = gl.evaluate_income_ladder(['B.TW', 'A.TW'])
    assert res['month_map'][2] == ['A.TW', 'B.TW']
    assert res['month_map'][8] == ['A.TW', 'B.TW']
    assert res['month_map'][5] == ['B.TW']


def test_no_dividend_history_contributes_nothing(monkeypatch):
    """無配息歷史（空）的 ETF → no_data_tickers，不貢獻任何月份（§1 不捏造）。"""
    _patch_pay_profile(monkeypatch, {
        'A.TW': {1, 7},
        'DEAD.TW': set(),
    })
    res = gl.evaluate_income_ladder(['A.TW', 'DEAD.TW'])
    assert res['no_data_tickers'] == ['DEAD.TW']
    assert res['covered_months'] == [1, 7]
    assert res['per_ticker']['DEAD.TW'] == []
    for _m, _ts in res['month_map'].items():
        assert 'DEAD.TW' not in _ts


def test_empty_holdings_all_gap(monkeypatch):
    """空持股 → 全 12 月皆缺口（無月配 → 非待觀察）、覆蓋 0。"""
    _patch_pay_profile(monkeypatch, {})
    res = gl.evaluate_income_ladder([])
    assert res['covered_months'] == []
    assert res['gap_months'] == list(range(1, 13))
    assert res['pending_months'] == []
    assert res['month_map'] == {}
    assert res['coverage_pct'] == 0.0
    assert res['holdings_count'] == 0


def test_duplicate_holdings_deduped(monkeypatch):
    """重複 ticker 去重（不雙列於 month_map、holdings_count 不重複計）。"""
    _patch_pay_profile(monkeypatch, {'A.TW': {3, 9}})
    res = gl.evaluate_income_ladder(['A.TW', 'A.TW', ' A.TW '])
    assert res['holdings_count'] == 1
    assert res['month_map'][3] == ['A.TW']


def test_suggest_fill_for_gaps_picks_covering_etf(monkeypatch):
    """補缺建議：從高股息 10 檔中挑「配息月份含該缺月」的一檔；查無回 None。"""
    _patch_pay_months(monkeypatch, {'0056.TW': {2}})
    sugg = gl.suggest_fill_for_gaps([2, 3])
    assert sugg[2] == '0056.TW'
    assert sugg[3] is None


def test_suggest_fill_excludes_held(monkeypatch):
    """exclude（＝使用者持股）內的 ticker 不被推薦。"""
    _patch_pay_months(monkeypatch, {'0056.TW': {2}})
    sugg = gl.suggest_fill_for_gaps([2], exclude=['0056.TW'])
    assert sugg[2] is None
