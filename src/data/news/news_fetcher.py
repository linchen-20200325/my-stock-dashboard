"""src/data/news/news_fetcher.py — 新聞 RSS L1 fetcher(v18.398 P5-B3-β R8; v18.460 CNYES→CNA).

從 app.py:1052-1297 抽出(EX-CACHE-1 pattern,@st.cache_data 條件 import)。

§3.3 對齊:`SYSTEMIC_RISK_KEYWORDS` 為「為關鍵字配置 data」,非 magic number。
原 app.py module-level 定義,單一 consumer(`fetch_macro_news`);抽 L1 後改為
本檔 module-level + 對外 export(若 fund / 其他模組需共享可直接 import)。

§8.2.A EX-CACHE-1 letter-compliant:try/except + _NoOpST fallback。
"""
from __future__ import annotations

import logging as _news_log

_logger = _news_log.getLogger(__name__)

try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa

from shared.ttls import TTL_30MIN


# v18.284:系統性風險關鍵字(戰爭/地緣/銀行倒閉/崩盤/黑天鵝)— 總經五桶「新聞桶」燈號用。
# 命中者標 is_systemic=True 並排序最優先;對齊 Fund news_repository.SYSTEMIC_RISK_KEYWORDS。
SYSTEMIC_RISK_KEYWORDS = [
    # 戰爭 / 地緣政治
    "war", "invasion", "ukraine", "russia", "israel", "gaza", "iran",
    "taiwan strait", "south china sea", "north korea", "missile",
    "drone strike", "sanctions", "embargo", "geopolitical", "nuclear",
    # 金融危機 / 破產
    "bankrupt", "bankruptcy", "collapse", "default", "bailout",
    "lehman", "credit suisse", "svb", "silicon valley bank",
    "signature bank", "first republic",
    "bank failure", "bank run", "deposit run", "liquidity crisis",
    "systemic risk", "contagion", "meltdown",
    # 央行緊急動作
    "emergency rate", "qt halt", "qe restart", "discount window",
    "fdic", "bail-in", "bail in",
    # 市場崩盤訊號
    "circuit breaker", "trading halt", "vix spike",
    "credit spread widening", "yield curve invert",
    "flight to safety", "panic selling", "rout", "selloff",
    # 中文
    "戰爭", "戰事", "侵略", "倒閉", "破產", "雷曼", "金融危機",
    "信用緊縮", "崩盤", "黑天鵝", "系統性風險", "流動性危機",
    "兌付危機", "擠兌", "違約",
]


@st.cache_data(ttl=TTL_30MIN, show_spinner=False, max_entries=10)
def fetch_macro_news(n: int = 5) -> list:
    """抓取全球總經財經新聞 — 中英雙語多源(系統性風險偵測用)。

    來源：中央社財經 / 經濟日報 / Google News(中) / Google News(英) /
          Yahoo Finance / CNBC Economy
          (v18.458: Reuters feeds.reuters.com removed — dead since June 2020)
          (v18.459: Bloomberg feeds.bloomberg.com removed — blocked for non-subscribers)
          (v18.460: CNYES 鉅亨 www.cnyes.com/rss/cat/headline removed — dead 404 redirect)
    策略：每源最多取 3 則 → 全池去重(依標題)→ 不依時間排序(部分 RSS 無 published),
          採「每源 round-robin」混合產出,確保中英來源都被納入 AI 判讀。
    ttl=TTL_30MIN:每 30 分鐘自動更新一次快取。
    """
    try:
        import feedparser as _fp
        import html as _h
        import re as _re2
    except ImportError:
        _logger.warning('[AI-News] feedparser 未安裝，跳過新聞抓取')
        return []
    try:
        from src.data.proxy import fetch_url as _furl_news
    except ImportError:
        _furl_news = None

    # 中文優先(在地系統性風險解讀),英文補強(黑天鵝國際同步)
    _feeds = [
        # v18.460: 鉅亨網 https://www.cnyes.com/rss/cat/headline 已死亡(重定向至 /twstock/error.htm 404)
        # 改用中央社財經 RSS(台灣官方通訊社,最具公信力的中文財經來源)
        ('中央社財經',   'https://www.cna.com.tw/rssfeed/news/afe.aspx'),
        ('經濟日報',     'https://money.udn.com/rssfeed/news/1001/5589/12017?ch=money'),
        ('Google中文',   'https://news.google.com/rss/search'
                         '?q=%E5%8F%B0%E8%82%A1+%E8%81%AF%E6%BA%96%E6%9C%83+%E5%88%A9%E7%8E%87+%E5%B9%B3%E5%84%B9'
                         '&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'),
        ('Google英文',   'https://news.google.com/rss/search'
                         '?q=stock+market+economy+fed+interest+rate'
                         '&hl=en-US&gl=US&ceid=US:en'),
        ('Yahoo Finance','https://finance.yahoo.com/news/rssindex'),
        # v18.457: Reuters feeds.reuters.com dead since June 2020 (all 404) — removed
        ('CNBC Economy', 'https://search.cnbc.com/rs/search/combinedcms/view.xml'
                         '?partnerId=wrss01&id=20910258'),
        # v18.459: Bloomberg feeds.bloomberg.com/markets/news.rss dead — blocked for non-subscribers — removed
    ]
    _per_src = 3  # 每源上限,避免單一來源洗版
    _by_src: dict[str, list] = {}
    for _src, _url in _feeds:
        _by_src[_src] = []
        try:
            # 走 NAS Squid proxy 抓 RSS 文字(Streamlit Cloud IP 多被 RSS 來源封鎖)
            _fd = None
            if _furl_news is not None:
                _r_rss = _furl_news(_url, timeout=10)
                if _r_rss is not None:
                    _fd = _fp.parse(_r_rss.content)
            if _fd is None or not getattr(_fd, 'entries', None):
                # 降級直連(proxy 失效時)
                _fd = _fp.parse(_url)
            for _e in _fd.entries:
                _title = _h.unescape(_e.get('title', '')).strip()
                _summ  = _h.unescape(_e.get('summary', _e.get('description', ''))).strip()
                _summ  = _re2.sub(r'<[^>]+>', '', _summ)[:300].strip()
                _pub   = str(_e.get('published', ''))[:16]
                if _title:
                    # v18.284:系統性風險偵測(title+summary 命中關鍵字 → is_systemic)
                    _txt_chk = (_title + ' ' + _summ).lower()
                    _is_sys = any(_kw in _txt_chk for _kw in SYSTEMIC_RISK_KEYWORDS)
                    _by_src[_src].append({'title': _title, 'summary': _summ,
                                          'source': _src, 'published': _pub,
                                          'is_systemic': _is_sys})
                if len(_by_src[_src]) >= _per_src:
                    break
            _logger.debug('[AI-News/%s] %d 則', _src, len(_by_src[_src]))
        except Exception as _ne:
            _logger.warning('[AI-News/%s] 抓取失敗: %s', _src, _ne)

    # round-robin 混合各源,依序去重 → 先收齊全池(不提早截斷)
    _seen: set[str] = set()
    _pool: list = []
    _max_round = max((len(v) for v in _by_src.values()), default=0)
    for _i in range(_max_round):
        for _src, _items in _by_src.items():
            if _i < len(_items):
                _t = _items[_i]['title']
                if _t and _t not in _seen:
                    _seen.add(_t)
                    _pool.append(_items[_i])
    # v18.284:系統性風險新聞永遠排前(戰爭/倒閉/崩盤命中),其餘維持 round-robin 來源混合序,
    # 再截斷至 n。→ AI 與「新聞桶」燈號皆優先看到系統性事件,避免被一般財經洗版漏看。
    _sys = [x for x in _pool if x.get('is_systemic')]
    _gen = [x for x in _pool if not x.get('is_systemic')]
    return (_sys + _gen)[:n]


def rss_items_from_bytes(_content) -> list:
    """從 RSS bytes 抽 item:feedparser 主、ElementTree 備援(規避 feedparser 對
    含 encoding 宣告 / 特殊命名空間 RSS 的怪癖)。回傳 dict list。

    契約(v19.76 統一雙後端):無 title / 空 title 條目一律略過 — ET 備援本就如此,
    feedparser 對缺 title 條目寬容原樣回傳,會讓空標題新聞流入下游渲染與關鍵字
    統計(CI 環境有 feedparser 時 test_news_fetcher_coverage 抓到此分歧)。
    malformed feed:feedparser 寬容解析(real-world RSS 常輕微 malformed,全丟
    = 掉真新聞),ET 備援嚴格回 [] — 兩後端此處刻意不同,絕不 raise。
    """
    if not _content:
        return []
    _cb = _content if isinstance(_content, bytes) else str(_content).encode('utf-8', 'ignore')
    try:
        import feedparser as _fp2
        _e = list(getattr(_fp2.parse(_cb), 'entries', []) or [])
        _e = [_it for _it in _e if str(_it.get('title') or '').strip()]
        if _e:
            return _e
    except Exception:
        pass
    if b'<item' not in _cb:
        return []
    try:
        import xml.etree.ElementTree as _ET
        import email.utils as _eu
        _items = []
        for _it in _ET.fromstring(_cb).iter('item'):
            _title = (_it.findtext('title') or '').strip()
            if not _title:
                continue
            _pub = (_it.findtext('pubDate') or '').strip()
            _items.append({'title': _title, 'link': (_it.findtext('link') or '').strip(),
                           'summary': (_it.findtext('description') or '').strip(),
                           'published': _pub, 'published_parsed': _eu.parsedate(_pub) if _pub else None})
        return _items
    except Exception:
        return []


@st.cache_data(ttl=TTL_30MIN, show_spinner=False, max_entries=50)
def fetch_stock_news(stock_id: str, stock_name: str = "", n: int = 5,
                     recency: str = "", _diag=None) -> list:
    """抓取個股相關新聞(Google News RSS 中英文雙搜尋)。失敗時回傳空串列。

    透過 NAS Squid proxy 路由(Streamlit Cloud IP 易被 Google News RSS 限速/封鎖)。
    recency:Google News 時間運算子(如 '6m' 近半年 / '7d'),空字串=不限。
    每則含 link 與排序用 _ts,並依發布時間新→舊排序。
    _diag:傳入 list 時逐 feed 記錄抓取狀態(proxy/直連 · HTTP · entries · 錯誤)供 UI 診斷。
        (underscore-prefix 命名:streamlit cache_data 自動跳過此 arg hash)
    """
    try:
        import feedparser as _fp
        import html as _h
        import re as _re2
        import time as _time_sn
        from urllib.parse import quote as _uq
    except ImportError:
        if _diag is not None:
            _diag.append('feedparser/urllib 匯入失敗')
        return []
    try:
        from src.data.proxy import fetch_url as _furl_sn, nas_relay_fetch as _nas_rf
    except ImportError:
        _furl_sn = None
        _nas_rf = None
        if _diag is not None:
            _diag.append('proxy_helper 未載入 → 僅能直連(雲端易 403)')
    # 不用 Google News `when:` 運算子(RSS 不穩、常回空 channel);改吃預設近期排序
    _q_tw = f"{stock_id} {stock_name}".strip()
    _q_en = f"Taiwan stock {stock_id} {stock_name}".strip()
    _feeds = [
        ('Google新聞(中文)', f'https://news.google.com/rss/search?q={_uq(_q_tw)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'),
        ('Google新聞(英文)', f'https://news.google.com/rss/search?q={_uq(_q_en)}&hl=en-US&gl=US&ceid=US:en'),
    ]
    _news_hdr = {
        'Cookie': 'CONSENT=YES+cb; SOCS=CAI',  # 繞過 Google 同意頁(保險)
        'Accept': 'application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5',
    }
    _out = []
    for _src, _url in _feeds:
        _via = ''
        _content = None
        try:
            # 路徑①:NAS FastAPI 中繼站(家用台灣 IP)
            if _nas_rf is not None:
                _rr = _nas_rf(_url, timeout=15)
                if _rr is not None:
                    _content = _rr.content
                    _via = f'NAS中繼 HTTP {getattr(_rr, "status_code", "?")}'
                else:
                    _via = 'NAS中繼未設定或失敗'
            # 路徑②:Squid proxy
            if not _content and _furl_sn is not None:
                _rs = _furl_sn(_url, headers=_news_hdr, timeout=10)
                if _rs is not None:
                    _content = _rs.content
                    _via += f' | Squid HTTP {getattr(_rs, "status_code", "?")}'
                else:
                    _via += ' | Squid回None'
            # 解析:feedparser → ElementTree 備援(餵 bytes)
            _items = rss_items_from_bytes(_content)
            # 路徑③:直連(前兩路徑都沒 item 才試;雲端機房 IP 多 403)
            if not _items:
                try:
                    _items = list(getattr(_fp.parse(_url, request_headers=_news_hdr), 'entries', []) or [])
                    _via += f' | 直連{len(_items)}則'
                except Exception:
                    _via += ' | 直連失敗'
            _itag = _content.count(b'<item') if _content else 0
            _via += f'｜item標籤={_itag}/解析{len(_items)}則'
            if not _items and _content:
                _via += f'｜body[:100]={_content[:100].decode("utf-8", "ignore").strip()!r}'
            for _e in _items:
                _title = _h.unescape(_e.get('title', '')).strip()
                _summ  = _h.unescape(_e.get('summary', _e.get('description', ''))).strip()
                _summ  = _re2.sub(r'<[^>]+>', '', _summ)[:150].strip()
                _pub   = str(_e.get('published', ''))[:16]
                _pp    = _e.get('published_parsed')
                try:
                    _ts = _time_sn.mktime(_pp) if _pp else 0.0
                except Exception:
                    _ts = 0.0
                if _title:
                    _out.append({'title': _title, 'summary': _summ, 'source': _src,
                                 'published': _pub, 'link': _e.get('link', ''), '_ts': _ts})
                if len(_out) >= n:
                    break
            if _diag is not None:
                _diag.append(f'{_src}: {_via} → 收 {len(_out)} 則')
            _logger.debug('[StockNews/%s] %s 累計 %d 則', _src, stock_id, len(_out))
        except Exception as _ne:
            if _diag is not None:
                _diag.append(f'{_src}: ❌ {_via} {type(_ne).__name__}: {str(_ne)[:80]}')
            _logger.warning('[StockNews/%s] 抓取失敗: %s', _src, _ne)
        if len(_out) >= n:
            break
    _out.sort(key=lambda _x: _x.get('_ts', 0.0), reverse=True)  # 新→舊
    return _out[:n]
