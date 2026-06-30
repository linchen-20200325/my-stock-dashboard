"""tests/test_news_fetcher_coverage.py — L1 news_fetcher pure-helper 覆蓋。

TARGET: src/data/news/news_fetcher.py (kind: fetcher)

只測 deterministic pure helper `rss_items_from_bytes`(crafted in-memory RSS bytes,
feedparser 主 → ElementTree 備援,兩條路徑都回 dict-like 物件可 .get()）。
network fetcher（fetch_macro_news / fetch_stock_news）僅 SMOKE import + callable,
**絕不**觸發網路 I/O。

斷言皆走 `.get('title')` / `.get('link')` / `.get('published')` 共通介面,
故無論執行環境是否安裝 feedparser 都成立。
"""
from __future__ import annotations

import pytest

from src.data.news.news_fetcher import (
    rss_items_from_bytes,
    fetch_macro_news,
    fetch_stock_news,
    SYSTEMIC_RISK_KEYWORDS,
)


def _rss(items_xml: str, encoding_decl: bool = True) -> bytes:
    head = '<?xml version="1.0" encoding="UTF-8"?>\n' if encoding_decl else ''
    return (
        f'{head}<rss version="2.0"><channel><title>Feed</title>'
        f'{items_xml}</channel></rss>'
    ).encode('utf-8')


_TWO_ITEMS = _rss(
    '<item><title>War breaks out in region</title>'
    '<link>http://example.com/1</link>'
    '<description>some news</description>'
    '<pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate></item>'
    '<item><title>Calm market day</title>'
    '<link>http://example.com/2</link>'
    '<description>nothing</description>'
    '<pubDate>Tue, 02 Jan 2024 12:00:00 GMT</pubDate></item>'
)


class TestRssItemsFromBytes:
    def test_parses_two_items(self):
        out = rss_items_from_bytes(_TWO_ITEMS)
        assert len(out) == 2
        titles = [it.get('title') for it in out]
        assert 'War breaks out in region' in titles
        assert 'Calm market day' in titles

    def test_link_extracted(self):
        out = rss_items_from_bytes(_TWO_ITEMS)
        links = {it.get('title'): it.get('link') for it in out}
        assert links['War breaks out in region'] == 'http://example.com/1'
        assert links['Calm market day'] == 'http://example.com/2'

    def test_published_extracted(self):
        out = rss_items_from_bytes(_TWO_ITEMS)
        pubs = {it.get('title'): it.get('published') for it in out}
        assert pubs['War breaks out in region'] == 'Mon, 01 Jan 2024 12:00:00 GMT'

    def test_empty_bytes_returns_empty_list(self):
        assert rss_items_from_bytes(b'') == []

    def test_none_returns_empty_list(self):
        assert rss_items_from_bytes(None) == []

    def test_no_item_tag_returns_empty_list(self):
        # 無 <item 標籤 → ET 備援 early-return []（feedparser 也回空 entries）
        assert rss_items_from_bytes(b'<rss version="2.0"><channel></channel></rss>') == []

    def test_str_input_is_encoded_and_parsed(self):
        # 非 bytes 輸入應被 encode 後解析，不報錯
        out = rss_items_from_bytes(_TWO_ITEMS.decode('utf-8'))
        assert len(out) == 2

    def test_item_without_title_is_skipped(self):
        # ET 備援路徑：缺 title 的 item 應被略過（feedparser 路徑同樣不會回無 title）
        rss = _rss(
            '<item><title>Has a title</title><link>http://e/1</link></item>'
            '<item><link>http://e/2</link><description>no title</description></item>'
        )
        out = rss_items_from_bytes(rss)
        titles = [it.get('title') for it in out]
        assert 'Has a title' in titles
        # 缺 title 者不應以空字串標題混入
        assert all((it.get('title') or '').strip() for it in out)

    def test_malformed_xml_returns_empty_list_not_raise(self):
        # 未閉合標籤 → ET 解析失敗，graceful 回 []（§1 fail-safe，不 raise）
        out = rss_items_from_bytes(b'<rss><channel><item><title>x</title>')
        assert out == []

    def test_returns_list_type(self):
        assert isinstance(rss_items_from_bytes(_TWO_ITEMS), list)
        assert isinstance(rss_items_from_bytes(b''), list)

    def test_single_item(self):
        rss = _rss(
            '<item><title>Lonely headline</title>'
            '<link>http://e/only</link></item>'
        )
        out = rss_items_from_bytes(rss)
        assert len(out) == 1
        assert out[0].get('title') == 'Lonely headline'

    def test_title_whitespace_handling(self):
        # title 前後空白應被 strip（ET 路徑明確 .strip()；feedparser 亦 trim）
        rss = _rss('<item><title>  Spaced  </title><link>http://e/s</link></item>')
        out = rss_items_from_bytes(rss)
        assert out[0].get('title') == 'Spaced'


class TestSystemicRiskKeywords:
    def test_is_non_empty_list_of_str(self):
        assert isinstance(SYSTEMIC_RISK_KEYWORDS, list)
        assert len(SYSTEMIC_RISK_KEYWORDS) > 0
        assert all(isinstance(k, str) for k in SYSTEMIC_RISK_KEYWORDS)

    def test_contains_expected_keywords(self):
        # 中英雙語關鍵字皆應存在（系統性風險偵測用）
        assert 'war' in SYSTEMIC_RISK_KEYWORDS
        assert 'bankruptcy' in SYSTEMIC_RISK_KEYWORDS
        assert '崩盤' in SYSTEMIC_RISK_KEYWORDS


class TestNetworkFetchersSmoke:
    """SMOKE only：確認 import + callable，絕不觸發網路 I/O。"""

    def test_fetch_macro_news_is_callable(self):
        assert callable(fetch_macro_news)

    def test_fetch_stock_news_is_callable(self):
        assert callable(fetch_stock_news)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
