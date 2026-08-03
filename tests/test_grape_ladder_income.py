"""葡萄串領息法 — evaluate_income_ladder / suggest_fill_for_gaps 純函式測試。

守衛「葡萄串主視圖改吃使用者持股」：evaluate_income_ladder 就 user 實際持有的
tickers 逐檔取配息月份（get_pay_months），算覆蓋 / 缺口 / 每月配息名單。
§1 誠實原則：無配息歷史的 ETF 貢獻 0 月、不捏造；缺月誠實列出。

以 monkeypatch get_pay_months 注入假配息月份，測純邏輯（不觸真 yfinance）。
"""
import src.ui.tabs.grape_ladder as gl


def _patch_pay_months(monkeypatch, table: dict[str, set[int]]):
    """把 grape_ladder.get_pay_months 換成 table 查表（未知 ticker → 空 set）。"""
    monkeypatch.setattr(gl, 'get_pay_months',
                        lambda t, *a, **k: set(table.get(t, set())))


def test_full_coverage_three_etfs(monkeypatch):
    """3 檔錯開（1/4/7/10、2/5/8/11、3/6/9/12）→ 覆蓋全 12 月、零缺口。"""
    _patch_pay_months(monkeypatch, {
        'A.TW': {1, 4, 7, 10},
        'B.TW': {2, 5, 8, 11},
        'C.TW': {3, 6, 9, 12},
    })
    res = gl.evaluate_income_ladder(['A.TW', 'B.TW', 'C.TW'])
    assert res['covered_months'] == list(range(1, 13))
    assert res['gap_months'] == []
    assert res['coverage_pct'] == 100.0
    assert res['holdings_count'] == 3
    assert res['no_data_tickers'] == []
    # 每月恰一檔貢獻
    assert res['month_map'][1] == ['A.TW']
    assert res['month_map'][2] == ['B.TW']
    assert res['month_map'][12] == ['C.TW']


def test_gaps_reported_honestly(monkeypatch):
    """只有 Q 配息月（1/4/7/10）→ 缺 2,3,5,6,8,9,11,12。"""
    _patch_pay_months(monkeypatch, {'X.TW': {1, 4, 7, 10}})
    res = gl.evaluate_income_ladder(['X.TW'])
    assert res['covered_months'] == [1, 4, 7, 10]
    assert res['gap_months'] == [2, 3, 5, 6, 8, 9, 11, 12]
    assert res['coverage_pct'] == round(4 / 12 * 100, 1)
    assert res['per_ticker']['X.TW'] == [1, 4, 7, 10]


def test_per_month_contributors_multiple_and_sorted(monkeypatch):
    """同月多檔配息 → month_map 該月列出全部且排序。"""
    _patch_pay_months(monkeypatch, {
        'B.TW': {2, 5, 8, 11},
        'A.TW': {2, 8},          # 與 B 在 2/8 月重疊
    })
    res = gl.evaluate_income_ladder(['B.TW', 'A.TW'])
    assert res['month_map'][2] == ['A.TW', 'B.TW']   # 排序後 A 在前
    assert res['month_map'][8] == ['A.TW', 'B.TW']
    assert res['month_map'][5] == ['B.TW']


def test_no_dividend_history_contributes_nothing(monkeypatch):
    """無配息歷史（空 set）的 ETF → no_data_tickers，不貢獻任何月份（§1 不捏造）。"""
    _patch_pay_months(monkeypatch, {
        'A.TW': {1, 7},
        'DEAD.TW': set(),        # 無配息歷史
    })
    res = gl.evaluate_income_ladder(['A.TW', 'DEAD.TW'])
    assert res['no_data_tickers'] == ['DEAD.TW']
    assert res['covered_months'] == [1, 7]
    assert res['per_ticker']['DEAD.TW'] == []
    # DEAD 不出現在任何 month_map 名單
    for _m, _ts in res['month_map'].items():
        assert 'DEAD.TW' not in _ts


def test_empty_holdings_all_gap(monkeypatch):
    """空持股 → 全 12 月皆缺口、覆蓋 0。"""
    _patch_pay_months(monkeypatch, {})
    res = gl.evaluate_income_ladder([])
    assert res['covered_months'] == []
    assert res['gap_months'] == list(range(1, 13))
    assert res['month_map'] == {}
    assert res['coverage_pct'] == 0.0
    assert res['holdings_count'] == 0


def test_duplicate_holdings_deduped(monkeypatch):
    """重複 ticker 去重（不雙列於 month_map、holdings_count 不重複計）。"""
    _patch_pay_months(monkeypatch, {'A.TW': {3, 9}})
    res = gl.evaluate_income_ladder(['A.TW', 'A.TW', ' A.TW '])
    assert res['holdings_count'] == 1
    assert res['month_map'][3] == ['A.TW']


def test_suggest_fill_for_gaps_picks_covering_etf(monkeypatch):
    """補缺建議：從高股息 10 檔中挑「配息月份含該缺月」的一檔；查無回 None。"""
    # 讓高股息清單第一檔（0056.TW）配 2 月，其餘查無 → 只有缺 2 月能補
    _patch_pay_months(monkeypatch, {'0056.TW': {2}})
    sugg = gl.suggest_fill_for_gaps([2, 3])
    assert sugg[2] == '0056.TW'
    assert sugg[3] is None


def test_suggest_fill_excludes_held(monkeypatch):
    """exclude（＝使用者持股）內的 ticker 不被推薦。"""
    _patch_pay_months(monkeypatch, {'0056.TW': {2}})
    sugg = gl.suggest_fill_for_gaps([2], exclude=['0056.TW'])
    assert sugg[2] is None
