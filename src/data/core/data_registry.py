"""data_registry.py — 資料源中央註冊表 (Single Source of Truth)

設計目的：
  • 集中管理所有第一手資料端點的 metadata
  • 支援「資料診斷」Tab 動態渲染
  • 支援「即時 Ping 測試」(限核心端點)
  • 純宣告式：未來新增資料源只要加一筆 dict，無需改診斷頁

使用方式：
    from src.data.core import DATA_REGISTRY, get_state_value, ping_endpoint
    for entry in DATA_REGISTRY:
        ...

註冊表欄位定義：
  category:      分類（用於分組顯示）
  name:          資料中文名稱
  source:        資料來源（FRED / FinMind / TWSE / yfinance ...）
  endpoint:      API endpoint（簡化顯示用）
  identifier:    Ticker / dataset / series_id
  frequency:     daily / monthly / quarterly / yearly / event
  requires_key:  None / 'FRED_API_KEY' / 'FINMIND_TOKEN' / 'GEMINI_API_KEY'
  usage:         用途說明（一句話）
  state_key:     從 session_state 取狀態的 dot 路徑（None=未連動）
  pingable:      是否支援即時測試（True/False）
  ping_url:      測試用完整 URL（None=不測試）

教學內容（EDU_GUIDE，依 identifier 對應）：
  meaning:           白話定義（這是什麼）
  how_to_read:       判讀規則 list[(門檻, 訊號)]
  pair_with:         搭配看的指標清單
  historical_anchor: 歷史錨點對照
  upstream:          上游因（誰會影響它）
  downstream:        下游果（它會影響誰）

⚠️ EDU_GUIDE 撰寫鐵律（v19.181 D3/B7）：
  **任何可被 code 證實或證偽的門檻數字，一律不得手打**，寫成 `§§TOKEN§§`，
  由 `shared/edu_tokens.py`（L0）在 `render_edu_card_html()` 期從 SSOT 取值。
  未登記的 token 會**原樣印在畫面上**（不是靜默消失）= 自帶 §1 fail-loud。
  可用 token 清單見 `shared.edu_tokens.edu_tokens()`；新增門檻請先加常數再加 token。

  這條鐵律的由來：稽核實測「融資餘額 2600 億」時，🌍 總經頁的融資卡印
  **🟡 警戒**，本檔的 `MI_MARGN` 教學卡卻印 **🔴 散戶過熱** —— 因為教學卡手寫
  「> 2500 億 = 🔴」，而判定 SSOT 是「2500 黃線 / 3400 紅線」。同一 block 的
  `historical_anchor` 又手寫「健康區 1500–2000 億」，是第三個版本。
  手寫數字沒有任何機制與判定式綁定 ⇒ 每次調門檻文案都不會跟著動，只會愈漂愈遠。

  同樣鐵律：**沒有對應判定式的門檻不准寫**。舊版「前十大留倉」寫了 4 條線，
  但全站對該欄位零判定式，那 4 條線其實是從「外資期貨」搬來的（同數字不同義）。
  沒有判定式就誠實寫「本系統不亮燈」，不得為了版面對稱而發明一條。
"""
from __future__ import annotations
from typing import Any
from shared.colors import TRAFFIC_GREEN, TRAFFIC_YELLOW
# D3/B7:教學卡的門檻一律走 `§§TOKEN§§` → render 期從 L0 SSOT 取值(見下方 EDU_GUIDE 說明)。
# L1 → L0 為合法下行 import(§8.2)。
from shared.edu_tokens import (
    edu_tokens as _edu_tokens,
    resolve_edu_rules as _resolve_edu_rules,
    resolve_edu_tokens as _resolve_edu_tokens,
)
from shared.fred_series import FRED_NAPM


# ══════════════════════════════════════════════════════════════════════════════
# 中央註冊表
# ══════════════════════════════════════════════════════════════════════════════
DATA_REGISTRY: list[dict[str, Any]] = [
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🌍 一、美國總經（FRED）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {'category':'🌍 美國總經', 'name':'美國核心 CPI 年增率', 'source':'FRED',
     'endpoint':'fred.stlouisfed.org/graph/fredgraph.csv', 'identifier':'CPILFESL',
     'frequency':'monthly', 'requires_key':'FRED_API_KEY',
     'usage':'通膨判讀、Fed 升降息預測',
     'state_key':'macro_info.us_core_cpi.date', 'pingable':True,
     'ping_url':'https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPILFESL'},
    {'category':'🇹🇼 台灣總經', 'name':'台灣製造業 PMI (CIER)', 'source':'CIER-EN + data.gov.tw 6100 + 8 段並行',
     'endpoint':'cier.edu.tw/en/eco (首選) / data.gov.tw/api/v2/rest/dataset/6100 / index.ndc / macromicro.me / stockfeel / cnyes / moneydj',
     'identifier':'cier-pmi',
     'frequency':'monthly', 'requires_key':None,
     'usage':'台灣製造業景氣領先指標 (>50 擴張，CIER 中華經濟研究院每月第一個工作日公布；v18.142 確認首源為 data.gov.tw dataset 6100)',
     'state_key':'macro_info.ism_pmi.date', 'pingable':True,
     'ping_url':'https://www.macromicro.me/charts/22/taiwan-pmi'},
    {'category':'🌍 美國總經', 'name':'BLS CPI 備援', 'source':'BLS',
     'endpoint':'api.bls.gov/publicAPI/v2/timeseries/data', 'identifier':'CUUR0000SA0',
     'frequency':'monthly', 'requires_key':None,
     'usage':'FRED CPI 失敗時的備援來源',
     'state_key':None, 'pingable':False, 'ping_url':None},

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🌐 二、國際金融指數（yfinance）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {'category':'🌐 國際金融', 'name':'道瓊工業指數', 'source':'yfinance',
     'endpoint':'query1.finance.yahoo.com', 'identifier':'^DJI',
     'frequency':'daily', 'requires_key':None,
     'usage':'美股大盤代表指數',
     'state_key':'cl_data.intl', 'pingable':False, 'ping_url':None},
    {'category':'🌐 國際金融', 'name':'S&P 500', 'source':'yfinance',
     'endpoint':'query1.finance.yahoo.com', 'identifier':'^GSPC',
     'frequency':'daily', 'requires_key':None,
     'usage':'美股大盤指標',
     'state_key':'cl_data.intl', 'pingable':False, 'ping_url':None},
    {'category':'🌐 國際金融', 'name':'那斯達克', 'source':'yfinance',
     'endpoint':'query1.finance.yahoo.com', 'identifier':'^IXIC',
     'frequency':'daily', 'requires_key':None,
     'usage':'科技股指標',
     'state_key':'cl_data.intl', 'pingable':False, 'ping_url':None},
    {'category':'🌐 國際金融', 'name':'費城半導體 SOX', 'source':'yfinance',
     'endpoint':'query1.finance.yahoo.com', 'identifier':'^SOX',
     'frequency':'daily', 'requires_key':None,
     'usage':'半導體景氣領先（與台股高度連動）',
     'state_key':'cl_data.intl', 'pingable':False, 'ping_url':None},
    {'category':'🌐 國際金融', 'name':'美元指數 DXY', 'source':'yfinance',
     'endpoint':'query1.finance.yahoo.com', 'identifier':'DX-Y.NYB',
     'frequency':'daily', 'requires_key':None,
     'usage':'美元強弱、外資流向判讀',
     'state_key':'cl_data.intl', 'pingable':False, 'ping_url':None},
    {'category':'🌐 國際金融', 'name':'美債 10Y 殖利率', 'source':'yfinance',
     'endpoint':'query1.finance.yahoo.com', 'identifier':'^TNX',
     'frequency':'daily', 'requires_key':None,
     'usage':'長天期利率、市場避險情緒',
     'state_key':'cl_data.intl', 'pingable':False, 'ping_url':None},
    {'category':'🌐 國際金融', 'name':'VIX 恐慌指數', 'source':'yfinance',
     'endpoint':'query1.finance.yahoo.com', 'identifier':'^VIX',
     'frequency':'daily', 'requires_key':None,
     'usage':'市場恐慌程度（>30 警戒）',
     'state_key':'macro_info.vix.current', 'pingable':False, 'ping_url':None},
    {'category':'🌐 國際金融', 'name':'銅博士', 'source':'yfinance',
     'endpoint':'query1.finance.yahoo.com', 'identifier':'HG=F',
     'frequency':'daily', 'requires_key':None,
     'usage':'全球景氣領先指標',
     'state_key':None, 'pingable':False, 'ping_url':None},

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🇹🇼 三、台股大盤（TWSE / yfinance）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {'category':'🇹🇼 台股大盤', 'name':'加權指數 OHLCV', 'source':'yfinance',
     'endpoint':'query1.finance.yahoo.com', 'identifier':'^TWII',
     'frequency':'daily', 'requires_key':None,
     'usage':'台股大盤主指數',
     'state_key':'cl_data.tw', 'pingable':True,
     'ping_url':'https://query1.finance.yahoo.com/v8/finance/chart/^TWII?range=1d&interval=1d'},
    {'category':'🇹🇼 台股大盤', 'name':'櫃買指數 OHLCV', 'source':'yfinance',
     'endpoint':'query1.finance.yahoo.com', 'identifier':'^TWOII',
     'frequency':'daily', 'requires_key':None,
     'usage':'OTC 市場指數',
     'state_key':'cl_data.tw', 'pingable':False, 'ping_url':None},
    {'category':'🇹🇼 台股大盤', 'name':'大盤成交統計', 'source':'TWSE OpenAPI',
     'endpoint':'/v1/exchangeReport/FMTQIK', 'identifier':'FMTQIK',
     'frequency':'daily', 'requires_key':None,
     'usage':'每日成交量、成交筆數',
     'state_key':None, 'pingable':True,
     'ping_url':'https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK'},
    {'category':'🇹🇼 台股大盤', 'name':'個股本益比/殖利率/PBR', 'source':'TWSE OpenAPI',
     'endpoint':'/v1/exchangeReport/BWIBBU_d', 'identifier':'BWIBBU_d',
     'frequency':'daily', 'requires_key':None,
     # v19.181 D3:原寫「💎 高息網漏斗篩選資料源」。「💎 高息網」這個模組**已不存在**
     # (`render_yield_screener` 全 repo 零定義,分頁真名是「🔭 選股網」)。
     'usage':'🔭 選股網的殖利率 / 本益比 / PBR 篩選資料源',
     'state_key':None, 'pingable':True,
     'ping_url':'https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d'},
    {'category':'🇹🇼 台股大盤', 'name':'個股日均價', 'source':'TWSE OpenAPI',
     'endpoint':'/v1/exchangeReport/STOCK_DAY_AVG_ALL', 'identifier':'STOCK_DAY_AVG_ALL',
     'frequency':'daily', 'requires_key':None,
     'usage':'全市場個股日均價',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🇹🇼 台股大盤', 'name':'上市公司基本資料', 'source':'TWSE OpenAPI',
     'endpoint':'/v1/opendata/t187ap03_L', 'identifier':'t187ap03_L',
     'frequency':'event', 'requires_key':None,
     'usage':'公司名稱、產業類別查詢',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🇹🇼 台股大盤', 'name':'漲跌家數 ADL', 'source':'yfinance ^TWII 估算(主)+精確源覆蓋',
     'endpoint':'^TWII 反推(is_proxy=True) / MI_INDEX 逐日精確覆蓋', 'identifier':'MI_INDEX',
     'frequency':'daily', 'requires_key':None,
     'usage':'市場廣度（旌旗指數計算用）⚠️ v19.85 正名:主值為 ^TWII 漲跌幅反推的'
             '估算家數(fetch_adl 帶 is_proxy 旗標),非真實統計;精確值抓到才逐日覆蓋',
     'state_key':'cl_data.adl', 'pingable':False, 'ping_url':None},
    {'category':'🇹🇼 台股大盤', 'name':'除權息預告', 'source':'TWSE',
     'endpoint':'/rwd/zh/exRight/TWT49U', 'identifier':'TWT49U',
     'frequency':'event', 'requires_key':None,
     'usage':'除權息日期查詢',
     'state_key':None, 'pingable':False, 'ping_url':None},

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 💰 四、籌碼資料（TWSE / TPEX / TAIFEX）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {'category':'💰 籌碼', 'name':'三大法人現貨買賣超', 'source':'TWSE',
     'endpoint':'/rwd/zh/fund/BFI82U', 'identifier':'BFI82U',
     'frequency':'daily', 'requires_key':None,
     'usage':'外資/投信/自營買賣超（核心籌碼指標）',
     'state_key':'cl_data.inst', 'pingable':False, 'ping_url':None},
    {'category':'💰 籌碼', 'name':'個股法人買賣超', 'source':'TWSE',
     'endpoint':'/fund/T86', 'identifier':'T86',
     'frequency':'daily', 'requires_key':None,
     'usage':'個股級法人籌碼',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'💰 籌碼', 'name':'融資餘額', 'source':'TWSE',
     'endpoint':'/rwd/zh/marginTrading/MI_MARGN', 'identifier':'MI_MARGN',
     'frequency':'daily', 'requires_key':None,
     'usage':'散戶情緒指標（>2500 億過熱）',
     'state_key':'cl_data.margin', 'pingable':False, 'ping_url':None},
    {'category':'💰 籌碼', 'name':'OTC 主板每日報價', 'source':'TPEX OpenAPI',
     'endpoint':'/openapi/v1/tpex_mainboard_daily_close_quotes',
     'identifier':'tpex_mainboard',
     'frequency':'daily', 'requires_key':None,
     'usage':'櫃買市場全市場報價',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'💰 籌碼', 'name':'OTC 三大法人', 'source':'TPEX',
     'endpoint':'/web/stock/3insti/daily_report/3itrade_hedge_result.php',
     'identifier':'3itrade_hedge',
     'frequency':'daily', 'requires_key':None,
     'usage':'櫃買法人籌碼',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'💰 籌碼', 'name':'外資期貨留倉', 'source':'TAIFEX',
     'endpoint':'/cht/3/largeTraderFutQryTbl', 'identifier':'largeTraderFutQry',
     'frequency':'daily', 'requires_key':None,
     'usage':'外資期貨多空（先行指標）',
     'state_key':'li_latest', 'pingable':False, 'ping_url':None},
    {'category':'💰 籌碼', 'name':'期貨契約日資料', 'source':'TAIFEX',
     'endpoint':'/cht/3/futContractsDate', 'identifier':'futContractsDate',
     'frequency':'daily', 'requires_key':None,
     'usage':'期貨未平倉、結算日',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'💰 籌碼', 'name':'期貨日盤行情', 'source':'TAIFEX',
     'endpoint':'/cht/3/futDailyMarketReport', 'identifier':'futDailyMarketReport',
     'frequency':'daily', 'requires_key':None,
     'usage':'期貨成交、未平倉',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'💰 籌碼', 'name':'選擇權契約日資料', 'source':'TAIFEX',
     'endpoint':'/cht/3/callsAndPutsDate', 'identifier':'callsAndPutsDate',
     'frequency':'daily', 'requires_key':None,
     'usage':'選擇權成交、未平倉',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'💰 籌碼', 'name':'PCR Put/Call Ratio', 'source':'TAIFEX',
     'endpoint':'/cht/3/pcRatio', 'identifier':'pcRatio',
     'frequency':'daily', 'requires_key':None,
     'usage':'選擇權多空情緒（>1 偏空）',
     'state_key':None, 'pingable':True,
     'ping_url':'https://www.taifex.com.tw/cht/3/pcRatio'},
    {'category':'💰 籌碼', 'name':'前五大留倉', 'source':'TAIFEX',
     'endpoint':'/cht/3/largeTraderFutQryTbl', 'identifier':'前五大留倉',
     'frequency':'daily', 'requires_key':None,
     'usage':'前五大主力期貨多空（最強領先籌碼）',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'💰 籌碼', 'name':'前十大留倉', 'source':'TAIFEX',
     'endpoint':'/cht/3/largeTraderFutQryTbl', 'identifier':'前十大留倉',
     'frequency':'daily', 'requires_key':None,
     'usage':'前十大主力期貨多空（含反向 ETF 避險）',
     'state_key':None, 'pingable':False, 'ping_url':None},

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🏢 五、個股財報（FinMind / MOPS / Goodinfo）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {'category':'🏢 個股財報', 'name':'個股 K線 OHLCV', 'source':'FinMind',
     'endpoint':'api.finmindtrade.com', 'identifier':'TaiwanStockPrice',
     'frequency':'daily', 'requires_key':'FINMIND_TOKEN',
     'usage':'個股日線資料（含成交量）',
     'state_key':'t2_data.df', 'pingable':False, 'ping_url':None},
    {'category':'🏢 個股財報', 'name':'月營收', 'source':'FinMind',
     'endpoint':'api.finmindtrade.com', 'identifier':'TaiwanStockMonthRevenue',
     'frequency':'monthly', 'requires_key':'FINMIND_TOKEN',
     'usage':'每月 10 日公布的營收',
     'state_key':'t2_data.rev', 'pingable':False, 'ping_url':None},
    {'category':'🏢 個股財報', 'name':'季財報（IS）', 'source':'FinMind',
     'endpoint':'api.finmindtrade.com', 'identifier':'TaiwanStockFinancialStatement',
     'frequency':'quarterly', 'requires_key':'FINMIND_TOKEN',
     'usage':'EPS / 毛利率 / 營業利益率',
     'state_key':'t2_data.qtr', 'pingable':False, 'ping_url':None},
    {'category':'🏢 個股財報', 'name':'季資產負債表', 'source':'FinMind',
     'endpoint':'api.finmindtrade.com', 'identifier':'TaiwanStockBalanceSheet',
     'frequency':'quarterly', 'requires_key':'FINMIND_TOKEN',
     'usage':'存貨 / 合約負債 / 總負債',
     'state_key':'t2_data.qtr_extra', 'pingable':False, 'ping_url':None},
    {'category':'🏢 個股財報', 'name':'季現金流量表', 'source':'FinMind',
     'endpoint':'api.finmindtrade.com', 'identifier':'TaiwanStockCashFlowsStatement',
     'frequency':'quarterly', 'requires_key':'FINMIND_TOKEN',
     'usage':'CapEx 資本支出 / FCF 自由現金流',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🏢 個股財報', 'name':'個股法人買賣超', 'source':'FinMind',
     'endpoint':'api.finmindtrade.com',
     'identifier':'TaiwanStockInstitutionalInvestorsBuySell',
     'frequency':'daily', 'requires_key':'FINMIND_TOKEN',
     'usage':'個股級三大法人買賣超',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🏢 個股財報', 'name':'三大法人合計', 'source':'FinMind',
     'endpoint':'api.finmindtrade.com',
     'identifier':'TaiwanStockTotalInstitutionalInvestors',
     'frequency':'daily', 'requires_key':'FINMIND_TOKEN',
     'usage':'大盤總計法人買賣',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🏢 個股財報', 'name':'配息歷史', 'source':'FinMind',
     'endpoint':'api.finmindtrade.com', 'identifier':'TaiwanStockDividend',
     'frequency':'yearly', 'requires_key':'FINMIND_TOKEN',
     'usage':'歷年現金/股票股利',
     'state_key':'t2_data.yearly', 'pingable':False, 'ping_url':None},
    {'category':'🏢 個股財報', 'name':'公司基本資料', 'source':'FinMind',
     'endpoint':'api.finmindtrade.com', 'identifier':'TaiwanStockInfo',
     'frequency':'event', 'requires_key':'FINMIND_TOKEN',
     'usage':'產業分類、上市日期',
     'state_key':None, 'pingable':True,
     'ping_url':'https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo&stock_id=2330&date=2024-01-01'},
    {'category':'🏢 個股財報', 'name':'MOPS 財報 備援', 'source':'MOPS',
     'endpoint':'mops.twse.com.tw/mops/web/ajax_t164sb03',
     'identifier':'ajax_t164sb03',
     'frequency':'quarterly', 'requires_key':None,
     'usage':'FinMind 失敗時的財報備援',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🏢 個股財報', 'name':'MOPS 月營收彙總 備援', 'source':'MOPS',
     'endpoint':'mops.twse.com.tw/nas/t21/sii/t21sc03_*.html',
     'identifier':'t21sc03',
     'frequency':'monthly', 'requires_key':None,
     'usage':'全市場月營收彙總',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🏢 個股財報', 'name':'Goodinfo 財報 備援', 'source':'Goodinfo',
     'endpoint':'goodinfo.tw/tw/StockFinDetail.asp',
     'identifier':'StockFinDetail',
     'frequency':'quarterly', 'requires_key':None,
     'usage':'IFRS 命名異常時的備援',
     'state_key':None, 'pingable':False, 'ping_url':None},

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🇹🇼 六、台灣總經
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {'category':'🇹🇼 台灣總經', 'name':'M1B / M2 貨幣供給', 'source':'CBC',
     'endpoint':'cbc.gov.tw/public/Attachment/ms1.json', 'identifier':'ms1.json',
     'frequency':'monthly', 'requires_key':None,
     'usage':'資金動能（M1B-M2 黃金交叉）',
     'state_key':'m1b_m2_info.m1b_yoy', 'pingable':True,
     'ping_url':'https://www.cbc.gov.tw/public/Attachment/ms1.json'},
    {'category':'🇹🇼 台灣總經', 'name':'央行貨幣供給 API', 'source':'CBC',
     'endpoint':'cpx.cbc.gov.tw/API/DataAPI/Get', 'identifier':'cpx-api',
     'frequency':'monthly', 'requires_key':None,
     'usage':'CBC 官方 API 備援',
     'state_key':None, 'pingable':False, 'ping_url':None},
    # NDC 景氣燈號 v19.85 三源:FinMind TaiwanBusinessIndicator(官方鏡像,首選)
    # → StockFeel → MacroMicro(v10.57.0 雙源降級為 fallback;StockFeel 文章有
    # 1~2 月更新延遲,2026-07 實測停在 4 月號 → 曾致 101 天 stale)
    {'category':'🇹🇼 台灣總經', 'name':'NDC 景氣燈號（FinMind 官方鏡像）', 'source':'FinMind',
     'endpoint':'api.finmindtrade.com/api/v4/data?dataset=TaiwanBusinessIndicator',
     'identifier':'TaiwanBusinessIndicator',
     'frequency':'monthly', 'requires_key':'FINMIND_TOKEN',
     'usage':'景氣對策信號分數+燈號+領先指標(國發會官方鏡像,月後數日更新;v19.85 首選)',
     'state_key':'macro_info.ndc_signal.score', 'pingable':False, 'ping_url':None},
    {'category':'🇹🇼 台灣總經', 'name':'NDC 景氣燈號（StockFeel）', 'source':'StockFeel',
     'endpoint':'stockfeel.com.tw/景氣對策信號-景氣指標-編制-國發會',
     'identifier':'NDC_signal_v2',
     'frequency':'monthly', 'requires_key':None,
     'usage':'台灣景氣綜合分數（45 分制;⚠️ 文章更新落後 1~2 月,fallback 用）',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🇹🇼 台灣總經', 'name':'NDC 景氣燈號（MacroMicro）', 'source':'MacroMicro',
     'endpoint':'macromicro.me/collections/10/tw-monitoring-indicators-relative',
     'identifier':'NDC_signal_v2_fallback',
     'frequency':'monthly', 'requires_key':None,
     'usage':'NDC 雙源 fallback',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🇹🇼 台灣總經', 'name':'財政部出口統計', 'source':'MOF',
     'endpoint':'service.mof.gov.tw/public/Data/statistic/trade',
     'identifier':'trade-csv',
     'frequency':'monthly', 'requires_key':None,
     'usage':'台灣月出口金額',
     'state_key':'macro_info.tw_export.yoy', 'pingable':False, 'ping_url':None},
    {'category':'🇹🇼 台灣總經', 'name':'MOF 出口 API', 'source':'MOF',
     'endpoint':'mof.gov.tw/API/statistics/trade/total', 'identifier':'trade-api',
     'frequency':'monthly', 'requires_key':None,
     'usage':'財政部出口備援',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🇹🇼 台灣總經', 'name':'FRED 台灣出口 備援', 'source':'FRED',
     'endpoint':'fred.stlouisfed.org/graph/fredgraph.csv',
     'identifier':'XTEXVA01TWM664S',
     'frequency':'monthly', 'requires_key':None,
     'usage':'MOF 失敗時的台灣出口備援（v18.142：原 VALEXPTWM052N IMF 餵慢 13 月 → 改 OECD MEI 落後 2-3 月）',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🇹🇼 台灣總經', 'name':'data.gov.tw 海關進出口', 'source':'data.gov.tw',
     'endpoint':'data.gov.tw/api/v2/rest/dataset/6053',
     'identifier':'dataset/6053',
     'frequency':'monthly', 'requires_key':None,
     'usage':'v18.142 新增：MOF 海關進出口貿易統計 CSV 直接讀（出口 YoY 主源）',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🇹🇼 台灣總經', 'name':'IMF M1B 備援', 'source':'IMF',
     'endpoint':'imf.org/external/datamapper/api/v1/MABMM301/TW',
     'identifier':'IMF-M1B',
     'frequency':'monthly', 'requires_key':None,
     'usage':'CBC 失敗時的 M1B 備援',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🇹🇼 台灣總經', 'name':'政府開放資料', 'source':'data.gov.tw',
     'endpoint':'data.gov.tw/api/3/action/package_search',
     'identifier':'package_search',
     'frequency':'event', 'requires_key':None,
     'usage':'通用備援查詢',
     'state_key':None, 'pingable':False, 'ping_url':None},
    # v18.270 — TW 央行政策階段判讀 4 項補完
    # ⚠️ v19.85 診斷:dataset=TaiwanMacroEconomics 不存在於 FinMind(SDK 2.0.4
    # 枚舉 + 官方文件皆無此名),下二項 fetcher 自建立起從未回資料;FinMind 亦無
    # CPI/失業率替代 dataset → 待新源設計(列入待核准清單),registry 先如實標註。
    {'category':'🇹🇼 台灣總經', 'name':'TW CPI 年增率', 'source':'FinMind',
     'endpoint':'api.finmindtrade.com/api/v4/data?dataset=TaiwanMacroEconomics（⚠️ dataset 不存在）',
     'identifier':'TaiwanCPI_YoY',
     'frequency':'monthly', 'requires_key':'FINMIND_TOKEN',
     'usage':'TW 通膨 YoY(判讀央行升降息週期)⚠️ v19.85:來源 dataset 不存在,現況恆無資料,待新源',
     'state_key':'macro_info.tw_cpi_yoy.value', 'pingable':False, 'ping_url':None},
    {'category':'🇹🇼 台灣總經', 'name':'TW 失業率', 'source':'FinMind',
     'endpoint':'api.finmindtrade.com/api/v4/data?dataset=TaiwanMacroEconomics（⚠️ dataset 不存在）',
     'identifier':'TaiwanUnemployment',
     'frequency':'monthly', 'requires_key':'FINMIND_TOKEN',
     'usage':'TW 勞動市場熱度 ⚠️ v19.85:來源 dataset 不存在,現況恆無資料,待新源',
     'state_key':'macro_info.tw_unemp.value', 'pingable':False, 'ping_url':None},
    {'category':'🇹🇼 台灣總經', 'name':'CBC 重貼現率', 'source':'FRED',
     'endpoint':'fred.stlouisfed.org/series/INTDSRTWM193N',
     'identifier':'INTDSRTWM193N',
     'frequency':'monthly', 'requires_key':'FRED_API_KEY',
     'usage':'CBC 政策利率(% level,判讀升降息週期),v18.270 新增',
     'state_key':'macro_info.cbc_rate.value', 'pingable':True,
     'ping_url':'https://fred.stlouisfed.org/graph/fredgraph.csv?id=INTDSRTWM193N'},
    {'category':'🇹🇼 台灣總經', 'name':'USDTWD 匯率', 'source':'Yahoo',
     'endpoint':'query1.finance.yahoo.com/v8/finance/chart/TWD=X',
     'identifier':'TWD=X',
     'frequency':'daily', 'requires_key':None,
     'usage':'USD/TWD 收盤(數字大=台幣貶,影響外資進出),v18.270 新增',
     'state_key':'macro_info.usdtwd.value', 'pingable':True,
     'ping_url':'https://query1.finance.yahoo.com/v8/finance/chart/TWD=X?range=5d&interval=1d'},

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🇨🇳 China macro(v18.271 方向 B,服務台積電終端需求 + 全球流動性判讀)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {'category':'🇨🇳 中國總經', 'name':'中國 OECD 領先指標', 'source':'FRED',
     'endpoint':'fred.stlouisfed.org/series/CHNLOLITONOSTSAM',
     'identifier':'CHNLOLITONOSTSAM',
     'frequency':'monthly', 'requires_key':'FRED_API_KEY',
     'usage':'OECD 中國綜合領先指標(PMI 替代,trend=100;月後 ~60 天),v18.271 新增',
     'state_key':'macro_info.chn_cli.value', 'pingable':True,
     'ping_url':'https://fred.stlouisfed.org/graph/fredgraph.csv?id=CHNLOLITONOSTSAM'},
    {'category':'🇨🇳 中國總經', 'name':'中國商業信心(PMI proxy)', 'source':'FRED',
     'endpoint':'fred.stlouisfed.org/series/BSCICP03CNM665S',
     'identifier':'BSCICP03CNM665S',
     'frequency':'monthly', 'requires_key':'FRED_API_KEY',
     'usage':'OECD 中國商業信心(對稱 US BSCICP02;月後 ~60 天),v18.271 新增',
     'state_key':'macro_info.chn_pmi.value', 'pingable':True,
     'ping_url':'https://fred.stlouisfed.org/graph/fredgraph.csv?id=BSCICP03CNM665S'},
    {'category':'🇨🇳 中國總經', 'name':'中國 CPI 年增率', 'source':'FRED',
     'endpoint':'fred.stlouisfed.org/series/CPALTT01CNM659N',
     'identifier':'CPALTT01CNM659N',
     'frequency':'monthly', 'requires_key':'FRED_API_KEY',
     'usage':'OECD 中國 CPI YoY(% YoY,月後 ~30 天),v18.271 新增',
     'state_key':'macro_info.chn_cpi.value', 'pingable':True,
     'ping_url':'https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPALTT01CNM659N'},
    {'category':'🇨🇳 中國總經', 'name':'中國 M2 廣義貨幣', 'source':'FRED',
     'endpoint':'fred.stlouisfed.org/series/MABMM301CNM189S',
     'identifier':'MABMM301CNM189S',
     'frequency':'monthly', 'requires_key':'FRED_API_KEY',
     'usage':'M2 廣義貨幣(信貸脈衝 proxy;月後 ~30 天),v18.271 新增',
     'state_key':'macro_info.chn_m2.value', 'pingable':True,
     'ping_url':'https://fred.stlouisfed.org/graph/fredgraph.csv?id=MABMM301CNM189S'},
    {'category':'🇨🇳 中國總經', 'name':'USDCNY 匯率', 'source':'FRED',
     'endpoint':'fred.stlouisfed.org/series/DEXCHUS',
     'identifier':'DEXCHUS',
     'frequency':'daily', 'requires_key':'FRED_API_KEY',
     'usage':'CNY/USD 日匯率(已在 Fund 端 FX 換匯生產驗證),v18.271 新增',
     'state_key':'macro_info.usdcny.value', 'pingable':True,
     'ping_url':'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXCHUS'},

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🏦 七、ETF / 基金
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {'category':'🏦 ETF / 基金', 'name':'ETF K線 OHLCV', 'source':'yfinance',
     'endpoint':'query1.finance.yahoo.com', 'identifier':'(各 ETF .TW)',
     'frequency':'daily', 'requires_key':None,
     'usage':'ETF 日線資料 (auto_adjust=True)',
     'state_key':'etf_single_data.price_df', 'pingable':False, 'ping_url':None},
    {'category':'🏦 ETF / 基金', 'name':'ETF 規模/Beta/費用率', 'source':'yfinance',
     'endpoint':'query1.finance.yahoo.com', 'identifier':'Ticker.info',
     'frequency':'daily', 'requires_key':None,
     'usage':'ETF AUM、Beta、Expense Ratio',
     'state_key':'etf_single_data.aum', 'pingable':False, 'ping_url':None},
    {'category':'🏦 ETF / 基金', 'name':'ETF NAV 淨值', 'source':'FinMind',
     'endpoint':'api.finmindtrade.com',
     'identifier':'TaiwanETFNetAssetValue',
     'frequency':'daily', 'requires_key':'FINMIND_TOKEN',
     'usage':'ETF 折溢價計算',
     'state_key':'etf_single_data.premium', 'pingable':False, 'ping_url':None},
    {'category':'🏦 ETF / 基金', 'name':'TWSE ETF API', 'source':'TWSE OpenAPI',
     'endpoint':'/v1/ETF/{op_id}', 'identifier':'ETF/v1',
     'frequency':'daily', 'requires_key':None,
     'usage':'ETF NAV 備援',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🏦 ETF / 基金', 'name':'MoneyDJ ETF 基本資料', 'source':'MoneyDJ',
     'endpoint':'moneydj.com/ETF/X/Basic/Basic0004.xdjhtm',
     'identifier':'Basic0004',
     'frequency':'event', 'requires_key':None,
     'usage':'ETF 成分股、追蹤指數',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🏦 ETF / 基金', 'name':'基金淨值', 'source':'MoneyDJ',
     'endpoint':'moneydj.com/funddj/yb/YP010001.djhtm',
     'identifier':'YP010001',
     'frequency':'daily', 'requires_key':None,
     'usage':'基金淨值查詢',
     'state_key':None, 'pingable':False, 'ping_url':None},

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 📰 八、新聞 RSS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {'category':'📰 新聞 RSS', 'name':'Google News (中文)', 'source':'Google News',
     'endpoint':'news.google.com/rss/search', 'identifier':'gnews-tw',
     'frequency':'event', 'requires_key':None,
     'usage':'個股/總經中文新聞',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'📰 新聞 RSS', 'name':'Google News (英文)', 'source':'Google News',
     'endpoint':'news.google.com/rss/search', 'identifier':'gnews-en',
     'frequency':'event', 'requires_key':None,
     'usage':'國際財經新聞',
     'state_key':None, 'pingable':False, 'ping_url':None},
    # v18.458: Reuters feeds.reuters.com dead since June 2020 — removed from news_fetcher.py (all 404)
    # {'category':'📰 新聞 RSS', 'name':'Reuters 商業新聞', 'source':'Reuters',
    #  'endpoint':'feeds.reuters.com/reuters/businessNews', 'identifier':'reuters-business',
    #  'frequency':'event', 'requires_key':None, 'usage':'國際財經事件追蹤',
    #  'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'📰 新聞 RSS', 'name':'CNBC 新聞', 'source':'CNBC',
     'endpoint':'search.cnbc.com/rs/search/combinedcms/view.xml',
     'identifier':'cnbc-rss',
     'frequency':'event', 'requires_key':None,
     'usage':'美股/國際新聞',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'📰 新聞 RSS', 'name':'Yahoo Finance 新聞', 'source':'Yahoo Finance',
     'endpoint':'finance.yahoo.com/news/rssindex',
     'identifier':'yahoo-finance-rss',
     'frequency':'event', 'requires_key':None,
     'usage':'美股相關新聞',
     'state_key':None, 'pingable':False, 'ping_url':None},

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🔄 九、三方備援
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {'category':'🔄 三方備援', 'name':'HiStock 融資餘額', 'source':'HiStock',
     'endpoint':'histock.tw/stock/margin.aspx', 'identifier':'margin.aspx',
     'frequency':'daily', 'requires_key':None,
     'usage':'融資餘額第 3 段備援',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🔄 三方備援', 'name':'Goodinfo 融資餘額', 'source':'Goodinfo',
     'endpoint':'goodinfo.tw/tw/ShowMarginChart.asp',
     'identifier':'goodinfo-margin',
     'frequency':'daily', 'requires_key':None,
     'usage':'融資餘額第 4 段備援（v10.55.0 新增）',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🔄 三方備援', 'name':'TWSE rwd dayMargin', 'source':'TWSE',
     'endpoint':'/rwd/zh/marginTrading/dayMargin', 'identifier':'dayMargin',
     'frequency':'daily', 'requires_key':None,
     'usage':'融資餘額第 5 段備援（v10.55.0 新增）',
     'state_key':None, 'pingable':False, 'ping_url':None},
    {'category':'🔄 三方備援', 'name':'Wearn 早期資料', 'source':'Wearn',
     'endpoint':'stock.wearn.com/margin.asp', 'identifier':'wearn-margin',
     'frequency':'daily', 'requires_key':None,
     'usage':'多層備援的最後一線',
     'state_key':None, 'pingable':False, 'ping_url':None},

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🤖 十、AI 服務
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    {'category':'🤖 AI 服務', 'name':'Google Gemini', 'source':'Google',
     'endpoint':'generativelanguage.googleapis.com/v1beta',
     'identifier':'gemini-2.5-flash',
     'frequency':'event', 'requires_key':'GEMINI_API_KEY',
     'usage':'AI 整合報告、總經摘要',
     'state_key':None, 'pingable':False, 'ping_url':None},
]


# ══════════════════════════════════════════════════════════════════════════════
# 工具函式
# ══════════════════════════════════════════════════════════════════════════════


def get_categories() -> list[str]:
    """回傳所有類別（依註冊順序去重）"""
    _seen, _out = set(), []
    for _e in DATA_REGISTRY:
        _c = _e.get('category', '其他')
        if _c not in _seen:
            _seen.add(_c)
            _out.append(_c)
    return _out


def get_by_category(category: str) -> list[dict]:
    """取得指定類別的所有資料源"""
    return [e for e in DATA_REGISTRY if e.get('category') == category]


# 📖 EDU_GUIDE — 指標解讀手冊（依 identifier 對應）
# ══════════════════════════════════════════════════════════════════════════════
# 設計原則：新人看了就懂。每筆指標回答 6 個問題：
#   1. meaning           — 白話這是什麼？
#   2. how_to_read       — 數字到了哪個門檻代表什麼訊號？
#   3. pair_with         — 不能只看單一指標，要搭配誰一起看？
#   4. historical_anchor — 歷史上的關鍵數字定錨（讓人有比例尺）
#   5. upstream          — 上游：誰會影響這個指標？
#   6. downstream        — 下游：這個指標會影響誰？
EDU_GUIDE: dict[str, dict[str, Any]] = {
    # ── 美國總經 ──────────────────────────────────────────────────
    'CPILFESL': {
        'meaning': '美國「核心」消費者物價指數年增率（剔除能源、食物波動），是 Fed 升降息最看重的通膨溫度計。',
        'how_to_read': [
            ('< §§CPI_MID_YELLOW§§%', '🟢 通膨受控，降息可期'),
            ('§§CPI_MID_YELLOW§§ ~ §§CPI_YELLOW§§%',
             '🟡 通膨黏性，降息路徑放緩（🌍 總經「中期」卡片自此轉黃）'),
            ('> §§CPI_YELLOW§§%', '🟠 外資提款風險（五桶危險門檻黃線）'),
            ('> §§CPI_RED§§%', '🔴 通膨嚴峻，升息壓力大、股債雙殺風險（五桶紅線）'),
        ],
        'pair_with': ['ISM PMI（NAPM）', '美債 10Y（^TNX）', '美元指數（DXY）'],
        'historical_anchor': '2022 通膨高峰 6.6%（40 年新高）｜2008 雷曼 2.5%｜Fed 目標 2.0%',
        'upstream': '油價、薪資成長、住房成本（OER）、供應鏈成本',
        'downstream': '影響 Fed 利率決策 → 美元 → 美債殖利率 → 美股估值（殖利率上 1%，PE 下調約 10–15%）',
    },
    FRED_NAPM: {
        'meaning': 'ISM 製造業採購經理人指數，採購主管問卷彙總，領先 GDP 約 3–6 個月。',
        # F1 v19.184 §3.3：原本這 4 條是手打的 `50 / 50 / 50 / 45`。
        # 前三條的 50 與 SSOT 相同（巧合，不是引用）；第 4 條的 **45 是錯的** ——
        # 五桶危險門檻 `ism_pmi` 的紅線是 **46**（`MACRO_THRESHOLDS.PMI.red_below`），
        # 且同一張卡上方的 sparkline 危險線自 F1 起就是畫在 46。
        # 兩個數字並排在同一張卡上互相打臉 → 改吃同一組 token。
        'how_to_read': [
            ('> §§PMI_YELLOW§§', '🟢 製造業擴張'),
            ('= §§PMI_YELLOW§§', '🟡 中性線（榮枯分水嶺）'),
            ('< §§PMI_YELLOW§§', '🔴 製造業萎縮（通常伴隨股市修正）'),
            ('< §§PMI_RED§§ 持續 3 月', '🚨 衰退強烈訊號（五桶「中期」紅線）'),
        ],
        'pair_with': ['美國核心 CPI（CPILFESL）', '台灣出口 YoY', '費半 SOX'],
        'historical_anchor': '2008 雷曼跌至 33.1｜2020 疫情 41.5｜2021 復甦高點 63.7',
        'upstream': '訂單能見度、企業 CapEx、全球需求',
        'downstream': '台灣出口（領先 1–2 季）→ 台股科技股獲利 → ^SOX & ^TWII',
    },
    # ── 國際金融 ──────────────────────────────────────────────────
    '^VIX': {
        'meaning': 'CBOE 用 S&P 500 選擇權隱含波動度算出的「市場恐慌指數」，俗稱華爾街的恐慌計。',
        'how_to_read': [
            ('< §§VIX_YELLOW§§', '🟢 未達警戒線，市場平靜／正常波動'),
            ('§§VIX_YELLOW§§ ~ §§VIX_RED§§',
             '🟡 警戒區，留意修正（五桶「短線急殺」自此轉黃）'),
            ('> §§VIX_RED§§', '🔴 流動性危機，紅綠燈系統強制空手（通常已是底部區）'),
            ('> §§VIX_V4_YELLOW§§ / > §§VIX_V4_RED§§',
             '⚠️ 另一把尺：🌍 總經「§三 籌碼」的 v4 引擎風險燈用較早的 '
             '§§VIX_V4_YELLOW§§ 黃線／§§VIX_V4_RED§§ 紅線（該燈只看 VIX + 外資期貨）'),
        ],
        'pair_with': ['S&P 500（^GSPC）', '美元指數（DXY）', 'Put/Call Ratio'],
        'historical_anchor': '2008 雷曼 89.5｜2020 疫情 82.7｜2022 通膨高峰 36｜平時 12–18',
        'upstream': 'S&P 500 選擇權買方需求、地緣政治事件、Fed 政策意外',
        'downstream': 'VIX 急升 → 風險資產拋售 → 美元/日圓避險買盤 → 新興市場資金外流',
    },
    'DX-Y.NYB': {
        'meaning': '美元對六大主要貨幣（歐元 57.6% + 日圓 13.6% + 英鎊 11.9% + 加幣/瑞典克朗/瑞郎）的加權匯率指數。',
        'how_to_read': [
            ('< §§DXY_YELLOW§§', '🟢 未達警戒線，新興市場資金壓力小、原物料有撐'),
            ('§§DXY_YELLOW§§ ~ §§DXY_RED§§', '🟡 警戒區，外資對台股轉保守'),
            ('> §§DXY_RED§§', '🔴 強勢美元壓力，外資撤離新興市場、全球流動性緊縮'),
        ],
        'pair_with': ['美債 10Y（^TNX）', '台幣匯率', 'VIX', '銅博士（HG=F）'],
        'historical_anchor': '2008 雷曼避險高 88｜2014 升息循環 100｜2022 強勢美元 114｜歷史平均 ~95',
        'upstream': 'Fed 利率（升息 → 美元強）、美國經濟相對其他國強弱、避險需求',
        'downstream': '直接影響：原物料（負相關）、新興市場資產、外資對台股流入流出',
    },
    '^TNX': {
        'meaning': '美國 10 年期公債殖利率，全球資產定價的「無風險錨」，被稱為金融市場的引力。',
        'how_to_read': [
            ('< §§TNX_NEUTRAL§§%', '🟢 寬鬆有利，成長股估值放大'),
            ('§§TNX_NEUTRAL§§ ~ §§US10Y_YELLOW§§%', '🟡 中性區間'),
            ('> §§US10Y_YELLOW§§%',
             '🟠 估值壓力（總經羅盤自此判 🔴，五桶危險門檻自此轉黃 —— '
             '同一條 §§US10Y_YELLOW§§ 線，兩個畫面的顏色刻意不同：羅盤較嚴）'),
            ('> §§US10Y_RED§§%', '🔴 緊縮／估值殺戮區（2022/10、2023/10 雙頂歷史）'),
        ],
        'pair_with': ['美國核心 CPI', '美元指數（DXY）', 'S&P 500'],
        'historical_anchor': '2008 雷曼 2.04%｜2020 疫情低 0.51%｜2023 高點 4.99%｜歷史平均 4.5%',
        'upstream': 'Fed 利率預期、通膨預期、美債供需（QT）、財政赤字',
        'downstream': '殖利率 +1% → 科技股 PE 縮水 ~15%（DCF 折現率敏感）→ 那斯達克／台股科技權值股下殺',
    },
    '^SOX': {
        'meaning': '費城半導體指數，全球半導體景氣最領先的籌碼面溫度計，與台股權值股（台積電/聯發科）連動 0.85+。',
        'how_to_read': [
            ('（本欄無自動判定式）',
             '⚪ 只抓 OHLCV 供你自己看走勢；下列三條是**人工觀察要點**，'
             '不是系統會亮的燈 —— 畫面上不會因為它們變色'),
            ('創新高', '🟢 半導體景氣熱絡，台股科技股有撐'),
            ('跌破年線（240 日均）', '🟠 趨勢轉弱，外資對台股科技股減碼'),
            ('SOX vs ^TWII 背離', '⚠️ 費半轉弱常領先台股數週（**經驗說法，本系統未回測**）'),
        ],
        'pair_with': ['台股加權指數（^TWII）', '台積電 ADR（TSM）', 'ISM PMI'],
        'historical_anchor': '2018/12 中美貿易戰低點｜2022/10 庫存修正低｜2024 AI 狂熱新高',
        'upstream': 'NVDA / AMD / AVGO / 台積電 ADR 權值股價 → 全球半導體訂單能見度',
        'downstream': '台股科技權值股（台積電 / 聯發科 / 鴻海）→ ^TWII 加權指數',
    },
    # ── 台股大盤 ──────────────────────────────────────────────────
    'BWIBBU_d': {
        'meaning': 'TWSE 每日盤後公布的全市場個股基本面三劍客：本益比（PE）／股價淨值比（PB）／殖利率（Y）。',
        'how_to_read': [
            ('殖利率 ≥ §§YIELD_HIGH§§%', '🟢 便宜價／強烈買進（357 殖利率估值法則）'),
            ('殖利率 §§YIELD_MID§§ ~ §§YIELD_HIGH§§%', '⚪ 合理價／中性持有'),
            ('殖利率 §§YIELD_LOW§§ ~ §§YIELD_MID§§%', '🟡 昂貴，適度減碼'),
            ('殖利率 ≤ §§YIELD_LOW§§%', '🔴 過貴，獲利了結'),
            ('PB < 1 ／ PE > 30',
             '⚠️ 通則參考 —— 本系統**沒有**用 PB／PE 絕對值做自動判定，'
             '個股估值一律走上方 357 殖利率四段（`shared/thresholds.classify_yield_zone`）'),
        ],
        'pair_with': ['月營收 YoY', '個股法人買賣超', 'M1B-M2 利差'],
        'historical_anchor': '台股長期殖利率 ~3.5%｜PE 中位數 ~14｜2008 低點 PB 約 1.2',
        'upstream': '盤後收盤價 + 公司公告殖利率（現金股利）',
        'downstream': '提供 🔭 選股網的殖利率／本益比篩選資料源；散戶基本面選股依據',
    },
    # ── 籌碼 ──────────────────────────────────────────────────────
    'BFI82U': {
        'meaning': 'TWSE 每日盤後公布的「外資 + 投信 + 自營」三大法人現貨買賣超總計，台股最權威的籌碼面風向。',
        'how_to_read': [
            ('外資單日淨買賣 > §§FOREIGN_NET_YELLOW_YI§§ 億', '🟢 買超（五桶「籌碼」綠燈）'),
            ('外資單日淨賣超 < §§FOREIGN_NET_RED_YI§§ 億', '🔴 單日大賣（五桶「籌碼」紅燈，軟線）'),
            ('外資 5 日累積 ≤ §§FOREIGN_5D_YI§§ 億', '🚨 這條才是真正會亮的警訊 —— '
             '且須與加權指數 20 日跌幅同時成立才觸發紅旗，單看一天不算數'),
            ('外資 + 投信同向買超', '🟢 法人聯手作多（人工觀察，系統未自動判定同向）'),
            ('外資投信對作', '🟡 訊號雜訊，看大盤方向決定（同上，人工觀察）'),
        ],
        'pair_with': ['外資期貨留倉', '融資餘額（散戶反向指標）', '台幣匯率'],
        'historical_anchor': '單日歷史最大買超 ~600 億｜單日最大賣超 ~700 億（2022/10/24）',
        'upstream': '外資匯入匯出（看美元指數）、MSCI 權重調整、季底作帳',
        'downstream': '影響加權指數、權值股股價、台幣匯率（買超台股需先換台幣 → 台幣升值）',
    },
    'MI_MARGN': {
        'meaning': '融資餘額 = 散戶向券商借錢買股的未還金額，是「散戶情緒」最直接的反向指標。',
        'how_to_read': [
            ('< §§MARGIN_WARN_YI§§ 億', '🟢 安全水位（🌍 總經的融資卡顯示綠）'),
            ('§§MARGIN_WARN_YI§§ ~ §§MARGIN_OVERHEAT_YI§§ 億',
             '🟡 警戒（融資卡自此轉黃 —— 舊版教學卡在這一段寫成紅，正是本次修掉的矛盾）'),
            ('> §§MARGIN_OVERHEAT_YI§§ 億', '🔴 散戶槓桿極危，注意主力出貨（融資卡轉紅）'),
            ('融資快速增加但指數不漲',
             '⚠️ 多殺多前兆（人工觀察 —— 本系統只判上面三段絕對水位，未自動判「量價背離」）'),
        ],
        'pair_with': ['三大法人買賣超（反向看）', '台股年線乖離（^TWII）'],
        # ⚠️ 這裡刻意**不寫「健康區 X~Y 億」** —— 舊文案手寫「健康區 1500–2000 億」，
        # 與上表判定線（§§MARGIN_WARN_YI§§/§§MARGIN_OVERHEAT_YI§§）是完全獨立的第三個版本。
        # 歷史高點是可查證的事實，保留；「健康區」是規範性判斷，必須與判定線同源。
        'historical_anchor': '2007 高峰 4400 億（2008 崩盤前）｜2022/4 高點 2900 億'
                             '｜⚠️ 絕對門檻正被市值成長稀釋：v19.170 稽核實測 5,148 億，'
                             '已同時穿透 §§MARGIN_WARN_YI§§ 與 §§MARGIN_OVERHEAT_YI§§ 兩線，'
                             '燈號鑑別力下降 —— 相對分位見 shared/relative_thresholds',
        'upstream': '散戶看多情緒、券商融資利率、金管會限制',
        'downstream': '融資擴張 → 散戶進場 → 大戶通常開始減碼；急殺時融資斷頭加速跌勢',
    },
    '前五大留倉': {
        'meaning': '期交所每日公布的「台指期前五大交易人」未平倉淨部位（多單-空單，單位：口）。代表市場頂級主力（投信、外資、自營）對未來方向的下注，是台股最強的領先籌碼指標之一。',
        # ⚠️ B7 修正紀錄：舊文案寫「> +5,000 🟢 / ±5,000 內 🟡 / < -5,000 🟠 /
        #    接近 -10,000 🔴（策略3 警戒線）」。逐條查證後：
        #    (a) ±5,000 這條線**全站不存在**，是憑空寫的；
        #    (b) -10,000 確實存在，但那是 `FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS`
        #        ——**外資期貨淨口**的黃線，不是大額交易人留倉的線。兩者同數字不同義，
        #        正是 `src/config/config.py` 反覆警告的耦合陷阱；
        #    (c) 「策略3 警戒線」這個出處也不對：策略代號是選股邏輯分類，不是籌碼門檻。
        #    本系統對「前五大留倉」**唯一**的自動判定在 🌍 總經 §三「🎯 籌碼綜合判斷」
        #    的加減分計分器（淨多 → +1 分；淨空超過一萬口 → -1 分），
        #    畫面 caption 也是這麼寫的（「前五大>1萬⚠️」）。文案照這個寫。
        'how_to_read': [
            ('淨多（> §§TOP5_BULL_LOTS§§ 口）', '🟢 +1 分（🎯 籌碼綜合判斷計分器）'),
            ('§§TOP5_BULL_LOTS§§ ~ §§TOP5_WARN_LOTS§§ 口',
             '⚪ 不計分 —— 本系統在這區間**不亮任何燈**，'
             '舊文案的「±5,000 中性 / -5,000 轉空」是憑空寫的，已移除'),
            ('淨空超過 §§TOP5_WARN_LOTS§§ 口',
             '🔴 -1 分（🌍 總經 §三 先行指標表下方的 caption 也標了這條線）'),
            ('⚠️ 別跟外資期貨的線搞混',
             '外資期貨淨口另有自己的黃線 §§FUT_YELLOW_LOTS§§ 口／紅線 §§FUT_RED_LOTS§§ 口 —— '
             '黃線數字**剛好與本欄的警戒線相同**，但量的是不同東西（外資 vs 前五大交易人），'
             '別互相套用'),
        ],
        'pair_with': ['外資期貨留倉（外資大小）', '前十大留倉', '選 PCR'],
        # 歷史區間數字無可查證來源，且與上表判定線無關 → 移除，只留可驗證的資料特性。
        'historical_anchor': '⚠️ 本欄原本寫「健康多頭區 +3,000~+8,000 口」等區間，'
                             '查無出處也無對應判定式，已移除。'
                             '可驗證的事實：本欄靠 TAIFEX 網頁爬取，FinMind 免費版無此資料，'
                             'v19.170 稽核曾實測連續 9 個交易日數值完全不變（管線凍結）—— '
                             '看數字前請先確認 🔎 資料診斷頁的凍結偵測沒亮紅',
        'upstream': '外資匯出匯入、月底季底結算、突發地緣事件、Fed 利率決議',
        'downstream': '領先大盤 1-3 日；當前五大空單擴大且加權指數仍高 → 出貨訊號 → 短中期回檔',
    },
    '前十大留倉': {
        'meaning': '期交所每日公布的「台指期前十大交易人」未平倉淨部位（口）。涵蓋更廣的主力與部分中型法人，**注意：包含反向 ETF（如 00632R）的避險空單**，因此真實方向性空單通常少於帳面顯示。',
        # ⚠️ B7 修正紀錄：舊文案寫 4 條門檻（±10,000 / -20,000「策略3 警戒線」）。
        #    全站掃過一遍：「前十大留倉」**沒有任何自動判定式** ——
        #    它只出現在 (1) 先行指標表格的一欄、(2) 🔎 資料診斷的凍結偵測監看欄。
        #    -20,000 的出處是 `FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS`（**外資期貨**紅線），
        #    被搬來套在完全不同的統計母體上。四條門檻全部移除，不另立新線
        #    （立新門檻 = 行為變更，需 user 核准 + 校準，不是文案修正該做的事）。
        'how_to_read': [
            ('（本欄無自動判定式）',
             '⚪ 只呈現數字，不亮燈。舊文案的 ±10,000／-20,000 四條線是把**外資期貨**的'
             '門檻（黃 §§FUT_YELLOW_LOTS§§ 口／紅 §§FUT_RED_LOTS§§ 口）搬來套在'
             '不同統計母體上，已移除'),
            ('改看「前五大留倉」',
             '🟢/🔴 前五大才有計分（> §§TOP5_BULL_LOTS§§ 口 +1 分 / '
             '< §§TOP5_WARN_LOTS§§ 口 -1 分）'),
            ('前十大 − 前五大 差額',
             '⚠️ 這段差額主要是中型法人 + **反向 ETF（如 00632R）的避險空單**，'
             '方向性意義低 —— 這也是本欄不設判定線的原因'),
        ],
        'pair_with': ['前五大留倉（更純粹）', '外資期貨留倉', '反向 ETF 規模'],
        'historical_anchor': '⚠️ 本欄原本寫「健康區 +5,000~+15,000 口」等區間，'
                             '查無出處也無對應判定式，已移除。'
                             '可驗證的事實：資料來自 TAIFEX 網頁爬取（FinMind 免費版無此資料），'
                             'v19.170 稽核曾實測連續 9 個交易日凍結不動',
        'upstream': '頂級主力部位 + 反向 ETF 避險需求 + 投信季底調整',
        'downstream': '與前五大背離時通常是反向 ETF 在動 → 不必過度解讀單日數字，須看 5 日均量與流向',
    },
    # ── 台灣總經 ─────────────────────────────────────────────────
    'ms1.json': {
        'meaning': '央行每月公布的貨幣供給：M1B = 通貨 + 活存（活錢），M2 = M1B + 定存。M1B-M2 利差代表「活錢比例變化」。',
        'how_to_read': [
            ('M1B−M2 利差 ≥ §§M1B_M2_YELLOW§§%', '🟢 黃金交叉，資金寬鬆，多頭啟動'),
            ('利差 §§M1B_M2_RED§§ ~ §§M1B_M2_YELLOW§§%', '🟡 利差收斂，留意趨勢轉折'),
            ('利差 < §§M1B_M2_RED§§%', '🔴 死亡交叉，資金緊縮，熊市風險'),
        ],
        'pair_with': ['NDC 景氣燈號', '加權指數（^TWII）', '融資餘額'],
        'historical_anchor': '2009 復甦 M1B YoY 26%｜2020 疫情寬鬆 21%｜2022 緊縮跌至 4%以下',
        'upstream': '央行利率政策、外匯存底變動（外資匯入 → M1B 升）、企業現金流',
        'downstream': '錢從定存搬到活存 → 股市資金動能（領先大盤 6–9 個月）',
    },
    'NDC_signal': {
        'meaning': '國發會每月公布的景氣綜合判斷分數（9 項指標加總，總分 45），用顏色燈號表示景氣熱度。',
        'how_to_read': [
            ('38–45 分（紅燈）', '🔴 景氣過熱，股市相對高點警示'),
            ('32–37 分（黃紅燈）', '🟠 趨熱，留意過熱風險'),
            ('23–31 分（綠燈）', '🟢 穩定成長，最佳持股期'),
            ('17–22 分（黃藍燈）', '🟡 趨穩，謹慎觀望'),
            ('9–16 分（藍燈）', '🔵 低迷，但股市常領先觸底反彈'),
        ],
        'pair_with': ['台灣出口 YoY', 'M1B-M2 利差', 'ISM PMI'],
        'historical_anchor': '2008 金融風暴連 9 個月藍燈｜2021 連 10 個月紅燈（出口爆發）｜健康區 24–34',
        'upstream': '出口、工業生產、批發零售、就業 9 大指標加總',
        'downstream': '常被視為股市的「同時指標」，但藍燈轉黃藍時股市已反彈過了',
    },
    'XTEXVA01TWM664S': {
        'meaning': '台灣每月出口金額年增率，全球景氣與台廠訂單能見度的核心指標（台灣 GDP 60% 來自出口）。v18.142 改 OECD MEI 來源，比 IMF IFS（VALEXPTWM052N）月延遲短 10 個月。',
        'how_to_read': [
            ('YoY > §§TW_EXPORT_YELLOW§§%', '🟢 出口擴張，基本面有撐'),
            ('YoY §§TW_EXPORT_RED§§ ~ §§TW_EXPORT_YELLOW§§%',
             '🟡 出口轉弱（舊文案只有紅綠兩段，漏了這條黃帶）'),
            ('YoY < §§TW_EXPORT_RED§§%',
             '🔴 明顯衰退（也是「總經基本面否決檢查」的觸發條件之一）'),
        ],
        'pair_with': ['ISM PMI', '費半 SOX', '台積電 ADR'],
        'historical_anchor': '2009 雷曼後 -41%｜2021 復甦 +49%｜2023 修正 -16%｜長期均值 +5%',
        'upstream': '美國 ISM PMI（領先 1–2 季）、全球半導體景氣、AI 訂單能見度',
        'downstream': '台股企業獲利 → ^TWII 走勢、台幣匯率（出口好台幣升）、月營收',
    },
}


def get_edu(identifier: str | None) -> dict | None:
    """依 identifier 取得教學資料；無對應則回 None。
    e.g. get_edu('CPILFESL') → {'meaning': ..., 'how_to_read': [...], ...}
    """
    if not identifier:
        return None
    return EDU_GUIDE.get(identifier)


def get_edu_count() -> int:
    """已撰寫教學內容的指標數"""
    return len(EDU_GUIDE)


def _esc(s: Any) -> str:
    """HTML escape（防止指標名稱含 < > & 時破版）"""
    if s is None:
        return ''
    return (str(s)
            .replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def render_edu_card_html(entry: dict, edu: dict) -> str:
    """渲染單一指標的教學卡 HTML 字串。
    使用 dark theme（GitHub 風格），可直接 st.markdown(html, unsafe_allow_html=True)。
    """
    _name = _esc(entry.get('name', ''))
    _id = _esc(entry.get('identifier', ''))
    _source = _esc(entry.get('source', ''))
    _freq = _esc(entry.get('frequency', ''))

    # ── D3/B7:`§§TOKEN§§` → SSOT 實值(先解 token,再 HTML escape)────────────
    # 順序很重要:token 值可能含 `<` / `>`(如「< 2500 億」不會,但未來新增的可能會),
    # 先解再逸出才不會把逸出後的 `&lt;` 當成 token 的一部分。
    # token 表**取一次**重複用,避免每個欄位都重跑一次 SSOT 讀取。
    _tk = _edu_tokens()
    _meaning = _esc(_resolve_edu_tokens(edu.get('meaning', ''), _tk))
    _hist = _esc(_resolve_edu_tokens(edu.get('historical_anchor', ''), _tk))
    _up = _esc(_resolve_edu_tokens(edu.get('upstream', ''), _tk))
    _down = _esc(_resolve_edu_tokens(edu.get('downstream', ''), _tk))
    _pairs = [_resolve_edu_tokens(str(_p), _tk) for _p in (edu.get('pair_with') or [])]
    _rules = _resolve_edu_rules(edu.get('how_to_read'), _tk)

    # 判讀規則 → 表格
    _rules_html = ''
    if _rules:
        _rule_rows = ''.join(
            f'<tr><td style="padding:6px 10px;font-family:monospace;color:#a5d6ff;'
            f'border-bottom:1px solid #21262d;white-space:nowrap;">{_esc(_th)}</td>'
            f'<td style="padding:6px 10px;color:#e6edf3;border-bottom:1px solid #21262d;">'
            f'{_esc(_sig)}</td></tr>'
            for _th, _sig in _rules
        )
        _rules_html = (
            '<div style="margin:8px 0 4px;font-size:11px;color:#8b949e;font-weight:600;">'
            '📐 怎麼判讀（門檻 → 訊號）</div>'
            f'<table style="width:100%;border-collapse:collapse;font-size:12px;'
            f'background:#0d1117;border-radius:6px;overflow:hidden;'
            f'border:1px solid #21262d;">{_rule_rows}</table>'
        )

    # 搭配指標 → chip
    _pair_html = ''
    if _pairs:
        _chips = ' '.join(
            f'<span style="display:inline-block;background:#161b22;border:1px solid #30363d;'
            f'color:#79c0ff;padding:2px 9px;margin:2px;border-radius:11px;font-size:11px;">'
            f'{_esc(_p)}</span>'
            for _p in _pairs
        )
        _pair_html = (
            '<div style="margin:8px 0 2px;font-size:11px;color:#8b949e;font-weight:600;">'
            '🔗 搭配看的指標</div>'
            f'<div>{_chips}</div>'
        )

    # 上下游關係（只在有資料時顯示）
    _flow_html = ''
    if _up or _down:
        _up_block = (
            f'<div style="flex:1;min-width:0;"><div style="font-size:10px;color:#8b949e;'
            f'margin-bottom:2px;">⬆️ 上游因（誰影響它）</div>'
            f'<div style="font-size:12px;color:#c9d1d9;line-height:1.5;">{_up}</div></div>'
            if _up else ''
        )
        _down_block = (
            f'<div style="flex:1;min-width:0;"><div style="font-size:10px;color:#8b949e;'
            f'margin-bottom:2px;">⬇️ 下游果（它影響誰）</div>'
            f'<div style="font-size:12px;color:#c9d1d9;line-height:1.5;">{_down}</div></div>'
            if _down else ''
        )
        _flow_html = (
            '<div style="margin-top:8px;display:flex;gap:14px;flex-wrap:wrap;">'
            f'{_up_block}{_down_block}</div>'
        )

    # 歷史錨點
    _hist_html = ''
    if _hist:
        _hist_html = (
            f'<div style="margin-top:8px;background:#1c2128;border-left:3px solid {TRAFFIC_YELLOW};'
            f'padding:6px 10px;border-radius:0 4px 4px 0;font-size:11px;color:#c9d1d9;">'
            f'<b style="color:{TRAFFIC_YELLOW};">📊 歷史錨點：</b>{_hist}</div>'
        )

    return (
        f'<div style="background:#0d1117;border:1px solid #30363d;border-radius:10px;'
        f'padding:14px 16px;margin:10px 0;">'
        # 標題列
        f'<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;'
        f'border-bottom:1px solid #21262d;padding-bottom:8px;margin-bottom:10px;">'
        f'<span style="font-size:14px;font-weight:700;color:#e6edf3;">{_name}</span>'
        f'<code style="background:#161b22;color:#a5d6ff;padding:1px 8px;border-radius:4px;'
        f'font-size:11px;">{_id}</code>'
        f'<span style="font-size:10px;color:#8b949e;">{_source} ｜ {_freq}</span>'
        f'</div>'
        # 白話定義
        f'<div style="font-size:12px;color:#c9d1d9;line-height:1.6;">'
        f'<b style="color:{TRAFFIC_GREEN};">💡 是什麼：</b>{_meaning}</div>'
        # 判讀
        f'{_rules_html}'
        # 搭配
        f'{_pair_html}'
        # 上下游
        f'{_flow_html}'
        # 歷史
        f'{_hist_html}'
        f'</div>'
    )
