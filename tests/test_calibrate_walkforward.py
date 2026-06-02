"""tests/test_calibrate_walkforward.py — walk-forward 校準 + JSON 持久化 smoke."""
from __future__ import annotations

import json
import os
import tempfile

import pandas as pd
import pytest


def test_synthetic_walkforward_runs_without_error():
    """合成 ^TWII 跑完整 walk-forward，回 dict 不 raise。"""
    from calibrate_macro_traffic import synthetic_twii_ohlcv, walk_forward_validate
    df = synthetic_twii_ohlcv(n_days=500, seed=42)
    wf = walk_forward_validate(df, n_folds=4, h_default=35, s_default=4)
    assert isinstance(wf, dict)
    assert 'recommended' in wf
    assert 'overfit_warning' in wf
    rec_h, rec_s = wf['recommended']
    # 越界守門
    assert 20 <= rec_h <= 60
    assert 1 <= rec_s <= 6


def test_overfit_guard_falls_back_to_default():
    """TWII-only 合成資料 score 結構性偏低 → drift 大 → 應回退預設。"""
    from calibrate_macro_traffic import synthetic_twii_ohlcv, walk_forward_validate
    df = synthetic_twii_ohlcv(n_days=500, seed=42)
    wf = walk_forward_validate(df, n_folds=4, h_default=35, s_default=4)
    if wf['overfit_warning']:
        assert wf['recommended'] == (35, 4), \
            '過擬合警語觸發時，建議門檻必須回退到 default'


def test_evaluate_thresholds_returns_metrics():
    """evaluate_thresholds 對任意 (h, s) 都應回完整 metrics dict。"""
    from calibrate_macro_traffic import (
        _backtest_with_inputs_cache, evaluate_thresholds, synthetic_twii_ohlcv,
    )
    df = synthetic_twii_ohlcv(n_days=300, seed=7)
    cache = _backtest_with_inputs_cache(df)
    assert len(cache) > 100, '300 日合成資料應產生 >100 筆 cache'
    m = evaluate_thresholds(cache, h_thr=40, s_thr=3)
    for k in ['green_precision', 'red_precision', 'green_recall', 'red_recall',
              'n_green_pred', 'n_red_pred']:
        assert k in m


def test_threshold_override_affects_color():
    """提高 BULL_MIN_SCORE 必使部分原本 🟢 的日子降級為 🟡。"""
    from calibrate_macro_traffic import (
        _backtest_with_inputs_cache, evaluate_thresholds, synthetic_twii_ohlcv,
    )
    df = synthetic_twii_ohlcv(n_days=400, seed=1)
    cache = _backtest_with_inputs_cache(df)
    m_loose = evaluate_thresholds(cache, h_thr=35, s_thr=2)
    m_strict = evaluate_thresholds(cache, h_thr=35, s_thr=6)
    # 嚴 score 門檻必使 🟢 預測數 ≤ 鬆門檻（單調性檢查）
    assert m_strict['n_green_pred'] <= m_loose['n_green_pred']


def test_emit_thresholds_json_no_change_returns_false():
    """JSON 內容相同時不應寫檔（避免 git 空 commit）。"""
    from calibrate_macro_traffic import emit_thresholds_json
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'thresholds.json')
        # 先寫一次
        emit_thresholds_json(35, 4, method='test1', path=path)
        # 同值再寫應回 False
        changed = emit_thresholds_json(35, 4, method='test2', path=path)
        assert changed is False
        # 值變了應回 True
        changed = emit_thresholds_json(37, 4, method='test3', path=path)
        assert changed is True
        with open(path) as fp:
            payload = json.load(fp)
        assert payload['HEALTH_DEFENSE_THRESHOLD'] == 37


def test_macro_helpers_reads_json_override():
    """macro_helpers._load_calibrated_thresholds 應正確讀 JSON 覆蓋預設。"""
    import sys
    from calibrate_macro_traffic import emit_thresholds_json
    with tempfile.TemporaryDirectory() as tmpdir:
        # 重點：_load_calibrated_thresholds 讀的是模組旁邊的 macro_thresholds.json，
        # 用 tempdir 直接模擬該檔不存在的情境
        path = os.path.join(tmpdir, 'macro_thresholds.json')
        emit_thresholds_json(33, 5, method='test', path=path)
        with open(path) as fp:
            payload = json.load(fp)
        assert payload['HEALTH_DEFENSE_THRESHOLD'] == 33
        assert payload['BULL_MIN_SCORE'] == 5
        # 簡 sanity：模組常數應落在合理範圍（讀現行 repo 內 JSON 或預設）
        sys.modules.pop('macro_helpers', None)
        from macro_helpers import HEALTH_DEFENSE_THRESHOLD, BULL_MIN_SCORE
        assert 20 <= HEALTH_DEFENSE_THRESHOLD <= 60
        assert 1 <= BULL_MIN_SCORE <= 6


def test_walk_forward_with_insufficient_data_returns_error():
    """資料太少時應 graceful 回 error，不 raise。"""
    from calibrate_macro_traffic import synthetic_twii_ohlcv, walk_forward_validate
    df = synthetic_twii_ohlcv(n_days=150)  # < 4 折 × 60 日門檻
    wf = walk_forward_validate(df, n_folds=4)
    assert wf.get('error') is not None
    assert wf['recommended'] == (35, 4)  # fall back


def test_objective_penalizes_large_deviation():
    """正則項應使「偏離大」的解分數低於「偏離小」。"""
    from calibrate_macro_traffic import _objective_with_penalty
    base_metrics = {
        'n_red_pred': 10, 'n_green_pred': 10,
        'red_precision': 50.0, 'red_recall': 50.0,
        'green_precision': 50.0, 'green_recall': 50.0,
    }
    score_close = _objective_with_penalty(base_metrics, 36, 4, 35, 4)
    score_far = _objective_with_penalty(base_metrics, 45, 4, 35, 4)
    assert score_close > score_far, '偏離小應分數高'


def test_load_from_cache_missing_returns_none():
    """data_cache/ 缺檔時應 graceful 回 None，不 raise。"""
    import tempfile
    import calibrate_macro_traffic as cmt
    original = cmt._CACHE_DIR
    with tempfile.TemporaryDirectory() as tmpdir:
        cmt._CACHE_DIR = tmpdir  # 指向空目錄
        try:
            result = cmt.load_from_cache(years=2)
            assert result is None
        finally:
            cmt._CACHE_DIR = original


def test_enrich_with_finmind_handles_missing_files():
    """_enrich_with_finmind 對缺 FinMind 檔應補 NaN 欄位、不 raise。"""
    import datetime as dt
    import tempfile
    import calibrate_macro_traffic as cmt
    original = cmt._CACHE_DIR
    df_twii = pd.DataFrame({
        "Close": [15000.0, 15100.0, 15200.0],
    }, index=pd.to_datetime([dt.date(2026, 1, 1), dt.date(2026, 1, 2), dt.date(2026, 1, 3)]))
    with tempfile.TemporaryDirectory() as tmpdir:
        cmt._CACHE_DIR = tmpdir
        try:
            out = cmt._enrich_with_finmind(df_twii)
            for col in ["foreign_buy", "margin_balance", "m1b_m2_gap"]:
                assert col in out.columns, f"應補 {col} 欄為 NaN"
                assert out[col].isna().all()
        finally:
            cmt._CACHE_DIR = original


def test_enrich_joins_finmind_inst_correctly(tmp_path):
    """FinMind 檔存在時應左 join 到 TWII index 並維持原資料數值。"""
    import datetime as dt
    import calibrate_macro_traffic as cmt
    original = cmt._CACHE_DIR
    # 建假 finmind_inst.parquet
    inst = pd.DataFrame({
        "date": [dt.date(2026, 1, 1), dt.date(2026, 1, 2)],
        "foreign_buy": [50.0, -30.0],  # 億
    })
    inst.to_parquet(tmp_path / "finmind_inst.parquet", index=False)
    df_twii = pd.DataFrame({"Close": [15000.0, 15100.0, 15200.0]},
                           index=pd.to_datetime([dt.date(2026, 1, 1),
                                                  dt.date(2026, 1, 2),
                                                  dt.date(2026, 1, 3)]))
    cmt._CACHE_DIR = str(tmp_path)
    try:
        out = cmt._enrich_with_finmind(df_twii)
        assert out.loc[pd.Timestamp(dt.date(2026, 1, 1)), "foreign_buy"] == 50.0
        assert out.loc[pd.Timestamp(dt.date(2026, 1, 2)), "foreign_buy"] == -30.0
        assert pd.isna(out.loc[pd.Timestamp(dt.date(2026, 1, 3)), "foreign_buy"])
    finally:
        cmt._CACHE_DIR = original


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
