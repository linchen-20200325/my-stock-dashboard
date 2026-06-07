"""v18.177 tw_macro NDC OpenAPI 遷移測試 — dgtw PRIMARY + FinMind FALLBACK chain。

驗證 fetch_ndc_signal_history / fetch_ndc_leading_index：
1. dgtw 命中時不打 FinMind（PRIMARY 路徑）
2. dgtw 失敗時自動退 FinMind（FALLBACK 路徑）
3. dgtw + FinMind 皆敗 graceful 回 error
4. source 欄位正確標示資料源
5. dgtw helper（search / CSV parse / probe candidate）獨立驗證
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

import tw_macro


def _mk_resp(json_data=None, content: bytes | None = None,
              status: int = 200) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    if json_data is not None:
        m.json.return_value = json_data
    if content is not None:
        m.content = content
    return m


def _mk_search_resp(ids: list[str]) -> MagicMock:
    return _mk_resp(json_data={
        'result': {'results': [{'id': i} for i in ids]}
    })


def _mk_meta_resp(csv_url: str) -> MagicMock:
    return _mk_resp(json_data={
        'result': {'resources': [{'format': 'CSV', 'url': csv_url}]}
    })


def _mk_csv_resp(csv_text: str) -> MagicMock:
    return _mk_resp(content=csv_text.encode('utf-8'))


def _csv_signal_12_months() -> str:
    """12 月遞增信號分數，最後 3 月 22 → 25 → 28（連 2 月翻多）。"""
    vals = [20, 19, 20, 21, 19, 20, 22, 21, 23, 22, 25, 28]
    rows = ['年月,景氣對策信號分數']
    for i, v in enumerate(vals, start=1):
        rows.append(f'2024-{i:02d},{v}')
    return '\n'.join(rows) + '\n'


def _csv_leading_12_months() -> str:
    """12 月遞增領先指標 → 6M smoothed change 正、拐點 🟢 持續擴張。"""
    rows = ['年月,領先指標綜合指數']
    for i in range(1, 13):
        rows.append(f'2024-{i:02d},{100 + i * 0.5}')
    return '\n'.join(rows) + '\n'


# ════════════════════════════════════════════════════════════════
# §1 dgtw helper unit tests
# ════════════════════════════════════════════════════════════════
class TestDgtwSearchDatasetIds:
    def test_extracts_dataset_ids_from_results(self, monkeypatch):
        monkeypatch.setattr(tw_macro, 'fetch_url',
                             lambda *a, **kw: _mk_search_resp(['6097', '6098']))
        ids = tw_macro._dgtw_search_dataset_ids('景氣對策信號')
        assert '6097' in ids
        assert '6098' in ids

    def test_skips_non_numeric_ids(self, monkeypatch):
        monkeypatch.setattr(tw_macro, 'fetch_url',
                             lambda *a, **kw: _mk_search_resp(['abc', '6100']))
        ids = tw_macro._dgtw_search_dataset_ids('test')
        assert ids == ['6100']

    def test_search_500_returns_empty(self, monkeypatch):
        monkeypatch.setattr(tw_macro, 'fetch_url',
                             lambda *a, **kw: _mk_resp(status=500))
        ids = tw_macro._dgtw_search_dataset_ids('test')
        assert ids == []


class TestDgtwFetchDatasetCsv:
    def test_parses_signal_csv(self, monkeypatch):
        responses = iter([
            _mk_meta_resp('https://example.tw/signal.csv'),
            _mk_csv_resp(_csv_signal_12_months()),
        ])
        monkeypatch.setattr(tw_macro, 'fetch_url',
                             lambda *a, **kw: next(responses))
        df = tw_macro._dgtw_fetch_dataset_csv(
            '6097', tw_macro._DGTW_NDC_SIGNAL_VALUE_KEYWORDS)
        assert df is not None
        assert len(df) == 12
        assert df.iloc[-1]['value'] == 28

    def test_no_csv_resource_returns_none(self, monkeypatch):
        bad_meta = _mk_resp(json_data={
            'result': {'resources': [{'format': 'PDF', 'url': 'x.pdf'}]}
        })
        monkeypatch.setattr(tw_macro, 'fetch_url',
                             lambda *a, **kw: bad_meta)
        df = tw_macro._dgtw_fetch_dataset_csv('6097', ('test',))
        assert df is None


class TestDgtwNdcIndicatorSeries:
    def test_search_path_hits(self, monkeypatch):
        """search 找到 ID → fetch CSV 成功 → 返 DataFrame，不 probe。"""
        responses = iter([
            _mk_search_resp(['6097']),
            _mk_meta_resp('https://example.tw/signal.csv'),
            _mk_csv_resp(_csv_signal_12_months()),
        ])
        monkeypatch.setattr(tw_macro, 'fetch_url',
                             lambda *a, **kw: next(responses))
        df = tw_macro._dgtw_ndc_indicator_series(
            ('景氣對策信號',), tw_macro._DGTW_NDC_SIGNAL_VALUE_KEYWORDS,
            ('6097',))
        assert df is not None
        assert not df.empty

    def test_all_paths_fail_returns_none(self, monkeypatch):
        monkeypatch.setattr(tw_macro, 'fetch_url',
                             lambda *a, **kw: _mk_resp(status=500))
        df = tw_macro._dgtw_ndc_indicator_series(
            ('test',), ('val',), ('9999',))
        assert df is None


# ════════════════════════════════════════════════════════════════
# §2 fetch_ndc_signal_history chain
# ════════════════════════════════════════════════════════════════
class TestNdcSignalHistoryChain:
    def test_dgtw_primary_skips_finmind(self, monkeypatch):
        """dgtw 命中 → source='data.gov.tw'，FinMind 不該被打。"""
        dgtw_df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=12, freq='MS')
                    .strftime('%Y-%m-%d'),
            'value': [20, 19, 20, 21, 19, 20, 22, 21, 23, 22, 25, 28],
        })
        monkeypatch.setattr(tw_macro, '_dgtw_ndc_indicator_series',
                             lambda *a, **kw: dgtw_df)
        # finmind 路徑若被 call 會炸
        def _explode(*a, **kw):
            raise AssertionError('FinMind 不該被呼叫')
        monkeypatch.setattr(tw_macro, '_finmind_macro_series', _explode)
        result = tw_macro.fetch_ndc_signal_history()
        assert result['source'] == 'data.gov.tw'
        assert result['score_latest'] == 28
        assert result['error'] is None

    def test_dgtw_empty_falls_back_to_finmind(self, monkeypatch):
        """dgtw 失敗 → FinMind 被呼叫 → source='FinMind'。"""
        monkeypatch.setattr(tw_macro, '_dgtw_ndc_indicator_series',
                             lambda *a, **kw: None)
        finmind_df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=12, freq='MS')
                    .strftime('%Y-%m-%d'),
            'value': [20, 19, 20, 21, 19, 20, 22, 21, 23, 22, 25, 28],
        })
        monkeypatch.setattr(tw_macro, '_finmind_macro_series',
                             lambda *a, **kw: finmind_df)
        result = tw_macro.fetch_ndc_signal_history()
        assert result['source'] == 'FinMind'
        assert result['score_latest'] == 28

    def test_both_fail_graceful_error(self, monkeypatch):
        monkeypatch.setattr(tw_macro, '_dgtw_ndc_indicator_series',
                             lambda *a, **kw: None)
        monkeypatch.setattr(tw_macro, '_finmind_macro_series',
                             lambda *a, **kw: None)
        result = tw_macro.fetch_ndc_signal_history()
        assert result['error'] is not None
        assert 'dgtw + FinMind 皆無' in result['error']
        assert result['source'] is None

    def test_sanity_filters_out_of_range_score(self, monkeypatch):
        """信號分數 ∉ [9, 45] 視為髒值濾掉。"""
        dirty_df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=12, freq='MS')
                    .strftime('%Y-%m-%d'),
            'value': [200, 19, 20, 999, 19, 20, 22, 21, 23, 22, 25, 28],  # 200/999 髒
        })
        monkeypatch.setattr(tw_macro, '_dgtw_ndc_indicator_series',
                             lambda *a, **kw: dirty_df)
        monkeypatch.setattr(tw_macro, '_finmind_macro_series',
                             lambda *a, **kw: None)
        result = tw_macro.fetch_ndc_signal_history()
        # 髒值被砍後仍 ≥3 月，邏輯能跑
        assert result['error'] is None
        assert result['score_latest'] == 28


# ════════════════════════════════════════════════════════════════
# §3 fetch_ndc_leading_index chain
# ════════════════════════════════════════════════════════════════
class TestNdcLeadingIndexChain:
    def test_dgtw_primary_skips_finmind(self, monkeypatch):
        dgtw_df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=12, freq='MS')
                    .strftime('%Y-%m-%d'),
            'value': [100 + i * 0.5 for i in range(1, 13)],
        })
        monkeypatch.setattr(tw_macro, '_dgtw_ndc_indicator_series',
                             lambda *a, **kw: dgtw_df)
        def _explode(*a, **kw):
            raise AssertionError('FinMind 不該被呼叫')
        monkeypatch.setattr(tw_macro, '_finmind_macro_series', _explode)
        result = tw_macro.fetch_ndc_leading_index()
        assert result['source'] == 'data.gov.tw'
        assert result['error'] is None
        # 連續遞增 → smooth6m > 0
        assert result['smooth6m'] > 0

    def test_dgtw_empty_falls_back_to_finmind(self, monkeypatch):
        monkeypatch.setattr(tw_macro, '_dgtw_ndc_indicator_series',
                             lambda *a, **kw: None)
        finmind_df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=12, freq='MS')
                    .strftime('%Y-%m-%d'),
            'value': [100 + i * 0.5 for i in range(1, 13)],
        })
        monkeypatch.setattr(tw_macro, '_finmind_macro_series',
                             lambda *a, **kw: finmind_df)
        result = tw_macro.fetch_ndc_leading_index()
        assert result['source'] == 'FinMind'

    def test_both_fail_graceful_error(self, monkeypatch):
        monkeypatch.setattr(tw_macro, '_dgtw_ndc_indicator_series',
                             lambda *a, **kw: None)
        monkeypatch.setattr(tw_macro, '_finmind_macro_series',
                             lambda *a, **kw: None)
        result = tw_macro.fetch_ndc_leading_index()
        assert result['error'] is not None
        assert 'dgtw + FinMind 皆無' in result['error']


# ════════════════════════════════════════════════════════════════
# §4 配置常數防呆
# ════════════════════════════════════════════════════════════════
class TestConstants:
    def test_dgtw_search_urls_complete(self):
        assert len(tw_macro._DGTW_SEARCH_URLS) >= 2

    def test_candidate_ids_around_pmi_6100(self):
        """候選 ID 應該包含 PMI 6100 附近的鄰居（國發會序列）。"""
        ids = tw_macro._DGTW_NDC_SIGNAL_CANDIDATE_IDS
        assert '6097' in ids and '6109' in ids

    def test_value_keywords_present(self):
        assert '景氣對策' in tw_macro._DGTW_NDC_SIGNAL_VALUE_KEYWORDS
        assert '領先指標' in tw_macro._DGTW_NDC_LEADING_VALUE_KEYWORDS


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
