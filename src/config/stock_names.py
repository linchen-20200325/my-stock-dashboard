"""
台股股票名稱查詢模組(L0 Config — 純 const + thin shim)

P0-1 v18.371 深層拔毒:fetch + cache I/O 邏輯抽至 src/data/core/stock_names_fetcher.py(L1)。
本檔留 _STATIC_NAMES const + get_stock_name 介面,lazy import fetcher。

優先級:動態快取(TWSE/TPEx OpenAPI)> 靜態字典 > yfinance > 回傳代碼
"""
from __future__ import annotations


# ── 靜態備援字典(常用股,動態快取失敗時使用)────────────────
_STATIC_NAMES = {
    '2330': '台積電', '2454': '聯發科', '2317': '鴻海', '2382': '廣達',
    '2308': '台達電', '2303': '聯電', '2882': '國泰金', '2881': '富邦金',
    '2886': '兆豐金', '2891': '中信金', '2603': '長榮', '2609': '陽明',
    '2615': '萬海', '3711': '日月光投控', '2357': '華碩', '2376': '技嘉',
    '6669': '緯穎', '3017': '奇鋐', '6770': '力積電', '6239': '力成',
    '2344': '華邦電', '2337': '旺宏', '3034': '聯詠', '5274': '信驊',
    '3661': '世芯-KY', '2409': '友達', '3481': '群創', '2327': '國巨',
    '2301': '光寶科', '3008': '大立光', '2412': '中華電', '2379': '瑞昱',
    '1301': '台塑', '1303': '南亞', '2002': '中鋼', '1519': '華城',
    '2884': '玉山金', '2885': '元大金', '2890': '永豐金', '5880': '合庫金',
    '2383': '台光電', '3533': '嘉澤', '6488': '環球晶', '6269': '台郡',
    '2049': '上銀', '1590': '亞德客-KY', '2207': '和泰車',
    # ETF
    '0050': '元大台灣50', '0056': '元大高股息', '006208': '富邦台50',
    '00878': '國泰永續高股息', '00919': '群益台灣精選高息',
    '00929': '復華台灣科技優息', '00940': '元大台灣價值高息',
    '00713': '元大台灣高息低波', '00982A': '中信優先金融債',
    '00720B': '元大投資級公司債', '00751B': '元大美債20年',
}


def get_stock_name(stock_id: str) -> str:
    """根據股票代碼取得中文名稱。
    優先級:動態快取(TWSE/TPEx)> 靜態字典 > yfinance > 代碼本身

    P0-1 v18.371:動態快取邏輯 lazy import 自 L1 fetcher。
    """
    # 1. 動態快取(L1 fetcher,lazy import 避 L0 啟動時拉 requests)
    try:
        from src.data.core.stock_names_fetcher import _ensure_cache, lookup_via_yfinance
        cache = _ensure_cache(static_fallback=_STATIC_NAMES)
        if stock_id in cache:
            return cache[stock_id]
    except Exception:
        cache = {}
        lookup_via_yfinance = None  # type: ignore

    # 2. 靜態備援
    if stock_id in _STATIC_NAMES:
        return _STATIC_NAMES[stock_id]

    # 3. yfinance 最終備援(慢,僅在前兩層都失敗時觸發)
    if lookup_via_yfinance is not None:
        _n = lookup_via_yfinance(stock_id)
        if _n:
            return _n

    return stock_id  # 最終 fallback


def refresh_name_cache() -> int:
    """強制重新抓取並更新快取。回傳新快取大小。
    P0-1 v18.371:thin shim,delegated to L1 fetcher。"""
    from src.data.core.stock_names_fetcher import refresh_name_cache as _refresh
    return _refresh(static_fallback=_STATIC_NAMES)
