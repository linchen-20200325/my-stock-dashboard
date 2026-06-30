"""tests/test_etf_categories_coverage.py — L2 純函式 ETF 同儕分類測試。

對應 src/compute/etf/etf_categories.py:
- get_peers(ticker) → 同類清單(排除自己,多類合併去重)
- get_category_name(ticker) → 所屬第一類別名稱

涵蓋 edge:ticker 格式正規化(.TW / .TWO / 純數字)、未知 ticker、
空/None 輸入、多類別重疊去重。
"""
from __future__ import annotations

import pytest

from src.compute.etf.etf_categories import (
    ETF_PEER_GROUPS,
    get_peers,
    get_category_name,
)


class TestGetPeers:
    def test_basic_peers_exclude_self(self):
        # 0050 屬市值型,回該類其餘成員,且不含自己
        peers = get_peers('0050.TW')
        assert '0050.TW' not in peers
        assert '006208.TW' in peers
        assert '00692.TW' in peers
        # 應等於市值型其餘 6 檔(僅單一類別命中)
        assert len(peers) == 6

    def test_bare_digit_normalized_to_tw(self):
        # '0050' 無後綴 → 正規化為 '0050.TW',結果應與帶後綴相同
        assert get_peers('0050') == get_peers('0050.TW')

    def test_two_suffix_normalized_to_tw(self):
        # 上櫃 '.TWO' 後綴應被替換為 '.TW'
        assert get_peers('0050.TWO') == get_peers('0050.TW')

    def test_unknown_ticker_returns_empty(self):
        # 不在任何分類 → 空 list(呼叫端顯示同儕不足)
        assert get_peers('9999.TW') == []
        assert get_peers('2330.TW') == []  # 台積電個股非 ETF

    def test_empty_string_returns_empty(self):
        assert get_peers('') == []

    def test_none_returns_empty(self):
        # None 輸入不應爆,回空 list
        assert get_peers(None) == []

    def test_whitespace_stripped(self):
        # 前後空白應被 strip
        assert get_peers('  0050.TW  ') == get_peers('0050.TW')

    def test_multi_category_merge_dedup(self):
        # 00713.TW 同屬「高股息」與「Smart Beta」→ 兩類合併去重
        peers = get_peers('00713.TW')
        assert '00713.TW' not in peers  # 排除自己
        # 高股息其他成員
        assert '0056.TW' in peers
        # Smart Beta 其他成員
        assert '00930.TW' in peers
        # 去重:結果無重複
        assert len(peers) == len(set(peers))

    def test_multi_category_overlap_member_not_double_counted(self):
        # 00701.TW 同屬高股息+Smart Beta,而 00713.TW 也同屬兩類。
        # 查 00701 時,00713 在兩類都出現但只應出現一次
        peers = get_peers('00701.TW')
        assert peers.count('00713.TW') == 1
        assert len(peers) == len(set(peers))
        assert '00701.TW' not in peers

    def test_single_category_member_count_matches_group(self):
        # 0056 僅屬高股息(單類),peers 數應為該類 - 1
        peers = get_peers('0056.TW')
        expected = [p for p in ETF_PEER_GROUPS['高股息'] if p != '0056.TW']
        assert sorted(peers) == sorted(expected)

    def test_bond_etf_b_suffix_ticker(self):
        # 含字母的 ticker(00679B.TW)有 '.' → 不觸發純數字補後綴邏輯
        peers = get_peers('00679B.TW')
        assert '00679B.TW' not in peers
        assert '00687B.TW' in peers
        assert len(peers) == len(ETF_PEER_GROUPS['債券']) - 1


class TestGetCategoryName:
    def test_basic_category(self):
        assert get_category_name('0050.TW') == '市值型'

    def test_bare_digit_normalized(self):
        assert get_category_name('0050') == '市值型'

    def test_two_suffix_normalized(self):
        assert get_category_name('0050.TWO') == '市值型'

    def test_unknown_returns_empty_string(self):
        assert get_category_name('9999.TW') == ''
        assert get_category_name('') == ''

    def test_multi_category_returns_first_match(self):
        # 00713.TW 同屬高股息+Smart Beta;dict 插入序高股息在前 → 回首匹配
        assert get_category_name('00713.TW') == '高股息'

    def test_bond_category(self):
        assert get_category_name('00679B.TW') == '債券'

    def test_consistency_with_get_peers(self):
        # 有分類名稱者必有同儕(該類至少 3 檔);反之未知者兩者皆空
        assert get_category_name('0050.TW') != '' and get_peers('0050.TW')
        assert get_category_name('9999.TW') == '' and get_peers('9999.TW') == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
