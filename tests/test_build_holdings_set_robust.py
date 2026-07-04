"""build_holdings_set 防彈測試(v18.467 自動計算後,分散度自動跑不得因格式異常 crash)。"""
import pandas as pd
from src.compute.etf.etf_smart_analysis import build_holdings_set


def test_list_of_dict():
    hs = [{'symbol': '2330'}, {'code': '2317'}, {'Symbol': '2454'}]
    assert build_holdings_set(hs) == {'2330', '2317', '2454'}


def test_dataframe_input_no_crash():
    # 原 bug:DataFrame 進 `if not holdings` 會 ValueError;現應安全
    df = pd.DataFrame([{'symbol': '2330'}, {'symbol': '2317'}])
    out = build_holdings_set(df)
    assert out == {'2330', '2317'}


def test_empty_dataframe():
    assert build_holdings_set(pd.DataFrame()) == set()


def test_none_and_empty():
    assert build_holdings_set(None) == set()
    assert build_holdings_set([]) == set()


def test_dict_input_no_crash():
    # 非預期 dict 也不得 raise(退化成拿 key 當代號,但不 crash)
    out = build_holdings_set({'2330': 1, '2317': 2})
    assert isinstance(out, set)


def test_list_of_strings():
    assert build_holdings_set(['2330', '2317']) == {'2330', '2317'}


def test_top_n_limit():
    hs = [{'symbol': str(i)} for i in range(30)]
    assert len(build_holdings_set(hs, top_n=5)) == 5
