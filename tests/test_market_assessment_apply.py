"""tests/test_market_assessment_apply.py — v18.449 市場廣度 ad_ratio 接線守衛。

`compute_and_apply_market_assessment` 新增 `df_adl` 參數，從其最後一列的 `ad_ratio`
欄位(0-100% 上漲家數佔比，來自 `fetch_adl`)萃取真值傳給 `get_market_assessment`。
本測試釘死：正常萃取、df_adl=None/空/缺欄位時安全降級為 None(不炸例外、不假造值)。
"""
from __future__ import annotations

import pandas as pd
import pytest

import streamlit as st

from src.services import market_assessment_apply as maa


def _fake_inst():
    return {'外資': {'net': 10.0}}


def _fake_tw_raw():
    _idx = pd.date_range(end=pd.Timestamp.now(), periods=130, freq='D')
    return {'台股加權指數': pd.DataFrame({'Close': [17000.0] * 130,
                                       'Volume': [1000.0] * 130}, index=_idx)}


def test_ad_ratio_extracted_from_df_adl_last_row(monkeypatch):
    """df_adl 有效 → 取最後一列 ad_ratio,轉發給 get_market_assessment。"""
    captured = {}

    def _fake_gma(**kw):
        captured.update(kw)
        return {'signals': [], 'label': 'x', 'score': 1}
    monkeypatch.setattr('src.services.get_market_assessment', _fake_gma)
    df_adl = pd.DataFrame({'ad_ratio': [40.0, 55.5, 67.7]})
    maa.compute_and_apply_market_assessment(
        inst=_fake_inst(), tw_raw=_fake_tw_raw(), margin=None, df_adl=df_adl)
    assert captured.get('ad_ratio') == pytest.approx(67.7), \
        '應取最後一列(最新一筆),不是第一列'


def test_ad_ratio_none_when_df_adl_is_none(monkeypatch):
    """df_adl=None(未提供)→ ad_ratio=None,不假造中性值。"""
    captured = {}

    def _fake_gma(**kw):
        captured.update(kw)
        return {'signals': [], 'label': 'x', 'score': 1}
    monkeypatch.setattr('src.services.get_market_assessment', _fake_gma)
    maa.compute_and_apply_market_assessment(
        inst=_fake_inst(), tw_raw=_fake_tw_raw(), margin=None, df_adl=None)
    assert captured.get('ad_ratio') is None


def test_ad_ratio_none_when_df_adl_empty_or_missing_column(monkeypatch):
    """df_adl 空 DataFrame 或缺 ad_ratio 欄位 → 安全降級 None,不拋例外。"""
    captured = []

    def _fake_gma(**kw):
        captured.append(kw.get('ad_ratio'))
        return {'signals': [], 'label': 'x', 'score': 1}
    monkeypatch.setattr('src.services.get_market_assessment', _fake_gma)

    maa.compute_and_apply_market_assessment(
        inst=_fake_inst(), tw_raw=_fake_tw_raw(), margin=None, df_adl=pd.DataFrame())
    maa.compute_and_apply_market_assessment(
        inst=_fake_inst(), tw_raw=_fake_tw_raw(), margin=None,
        df_adl=pd.DataFrame({'other_col': [1, 2]}))
    assert captured == [None, None]


def test_ad_ratio_nan_last_row_treated_as_none(monkeypatch):
    """最後一列 ad_ratio 為 NaN(資料尚未補齊)→ 視為 None,不傳 NaN 進評分。"""
    captured = {}

    def _fake_gma(**kw):
        captured.update(kw)
        return {'signals': [], 'label': 'x', 'score': 1}
    monkeypatch.setattr('src.services.get_market_assessment', _fake_gma)
    df_adl = pd.DataFrame({'ad_ratio': [50.0, float('nan')]})
    maa.compute_and_apply_market_assessment(
        inst=_fake_inst(), tw_raw=_fake_tw_raw(), margin=None, df_adl=df_adl)
    assert captured.get('ad_ratio') is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
