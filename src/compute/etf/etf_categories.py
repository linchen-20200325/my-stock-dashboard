"""ETF 同儕分類表 — 用於同儕近 3M/6M/1Y 報酬排名比較。

維護原則：
- 每類至少 3 檔（少於 3 檔將顯示「同儕不足」）。
- 含上市 + 上櫃；不含已下市 ETF（避免 yfinance 抓不到）。
- 同一 ticker 可同時屬於多類（例：00919 = 高股息 ∩ 0050 衛星）。

更新頻率：發行新主流 ETF 或下市時手動維護。
"""

ETF_PEER_GROUPS: dict[str, list[str]] = {
    # 市值型（追蹤大盤 / 台灣 50 / 中型 100 等）
    '市值型': [
        '0050.TW',   # 元大台灣50
        '006208.TW', # 富邦台50
        '00692.TW',  # 富邦公司治理100
        '00850.TW',  # 元大臺灣ESG永續
        '0051.TW',   # 元大中型100
        '00922.TW',  # 國泰台灣領袖50
        '00923.TW',  # 群益台ESG低碳50
    ],
    # 高股息（核心配息族群）
    '高股息': [
        '0056.TW',   # 元大高股息
        '00878.TW',  # 國泰永續高股息
        '00713.TW',  # 元大台灣高息低波
        '00919.TW',  # 群益台灣精選高息
        '00929.TW',  # 復華台灣科技優息
        '00940.TW',  # 元大台灣價值高息
        '00939.TW',  # 統一台灣高息動能
        '00918.TW',  # 大華優利高填息30
        '00731.TW',  # 復華富時高息低波
        '00701.TW',  # 國泰股利精選30
    ],
    # 半導體 / 科技
    '半導體科技': [
        '00891.TW',  # 中信關鍵半導體
        '00892.TW',  # 富邦台灣半導體
        '00904.TW',  # 新光臺灣半導體30
        '00941.TW',  # 中信上游半導體
        '00935.TW',  # 野村臺灣新科技50
        '00881.TW',  # 國泰台灣5G+
        '00876.TW',  # 元大全球5G
        '00911.TW',  # 兆豐洲際半導體
    ],
    # Smart Beta（價值 / 動能 / 低波）
    'Smart Beta': [
        '00701.TW',  # 國泰股利精選30
        '00713.TW',  # 元大台灣高息低波
        '00731.TW',  # 復華富時高息低波
        '00850.TW',  # 元大臺灣ESG永續
        '00692.TW',  # 富邦公司治理100
        '00930.TW',  # 永豐ESG低碳高息
    ],
    # 債券 ETF（投資級公司債 / 美債）
    '債券': [
        '00679B.TW', # 元大美債20年
        '00687B.TW', # 國泰20年美債
        '00696B.TW', # 富邦美債20年
        '00720B.TW', # 元大投資級公司債
        '00772B.TW', # 中信高評級公司債
        '00773B.TW', # 中信優先金融債
        '00751B.TW', # 元大AAA-A公司債
    ],
}


def get_peers(ticker: str) -> list[str]:
    """查同類 ETF 清單，排除自己；同時屬多類則合併去重。

    ticker 接受 '0050' / '0050.TW' / '0050.TWO'；統一回 '.TW' 後綴格式。
    找不到分類回空 list（呼叫端應顯示「同儕資料不足」）。
    """
    _t = (ticker or '').replace('.TWO', '.TW').strip()
    if not _t:
        return []
    if '.' not in _t and _t.isdigit():
        _t = f'{_t}.TW'
    _result: list[str] = []
    _seen: set[str] = {_t}
    for _peers in ETF_PEER_GROUPS.values():
        if _t in _peers:
            for _p in _peers:
                if _p not in _seen:
                    _result.append(_p)
                    _seen.add(_p)
    return _result


def get_category_name(ticker: str) -> str:
    """回傳 ticker 所屬第一類別名稱（多類則回首匹配）；查無回 ''。"""
    _t = (ticker or '').replace('.TWO', '.TW').strip()
    if '.' not in _t and _t.isdigit():
        _t = f'{_t}.TW'
    for _name, _peers in ETF_PEER_GROUPS.items():
        if _t in _peers:
            return _name
    return ''
