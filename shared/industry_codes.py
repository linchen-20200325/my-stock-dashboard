"""shared/industry_codes.py — 證交所／櫃買中心官方「產業別代碼 ↔ 名稱」SSOT(L0)。

批 Z43(客戶 Q-z29＝A):板塊資金泡泡圖的產業別改依**官方產業別代碼**選列(見
`src/data/stock/market_close_fetcher.fetch_industry_map_bulk`)。本檔只放「代碼 → 官方名稱」
與選列用的寬鬆比對函式,純常數 + 純函式、零 import 依賴(可被全層 import)。

出處(§2.2 provenance;**不是猜的**)
------------------------------------
- 代碼 ↔ 名稱:臺灣證券交易所 ISIN 查詢頁 `https://isin.twse.com.tw/isin/class_i.jsp?kind=1`
  「產業別」下拉選單原文(GitHub runner 探針第 7 輪 run 38191149822,2026-10-12)。
- 上市 `openapi.twse.com.tw/v1/opendata/t187ap03_L` 的 `產業別` 欄、上櫃
  `www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O` 的 `SecuritiesIndustryCode` 欄皆為**兩位數代碼**,
  上市上櫃**共用同一代碼體系**:探針以代號 join ISIN 公開頁(上市 1095／1095、上櫃 893／893 檔)
  逐碼交叉,每個代碼只對到一個 ISIN 產業別名稱(例:上市 '24'→'半導體業'×96、上櫃 '24'→'半導體業'×111)。
- '13' 電子工業:下拉選單有此項,但官方「依產業別查詢」上市 ic=13 → class_nofind(無個股);
  探針兩份 openapi 皆無 '13'。保留在表內只因下拉原文有,**不代表**有個股屬之。
- '07':官方代碼表**沒有** 07(上市 ic=07 → class_nofind)→ 不列。
- '91':上市 openapi 出現(10 檔,皆為臺灣存託憑證 TDR),ISIN 產業別欄**空白** → 名稱 `None`
  (官方沒有給產業名稱,⛔ 不臆造)。
"""
from __future__ import annotations

#: 官方產業別代碼 → 官方名稱(class_i 下拉原文,逐字)。`None` = 官方代碼存在但無產業名稱。
OFFICIAL_INDUSTRY_CODE_NAMES: dict[str, str | None] = {
    "01": "水泥工業",
    "02": "食品工業",
    "03": "塑膠工業",
    "04": "紡織纖維",
    "05": "電機機械",
    "06": "電器電纜",
    "08": "玻璃陶瓷",
    "09": "造紙工業",
    "10": "鋼鐵工業",
    "11": "橡膠工業",
    "12": "汽車工業",
    "13": "電子工業",
    "14": "建材營造業",
    "15": "航運業",
    "16": "觀光餐旅",
    "17": "金融保險業",
    "18": "貿易百貨業",
    "19": "綜合",
    "20": "其他業",
    "21": "化學工業",
    "22": "生技醫療業",
    "23": "油電燃氣業",
    "24": "半導體業",
    "25": "電腦及週邊設備業",
    "26": "光電業",
    "27": "通信網路業",
    "28": "電子零組件業",
    "29": "電子通路業",
    "30": "資訊服務業",
    "31": "其他電子業",
    "32": "文化創意業",
    "33": "農業科技業",
    "35": "綠能環保",
    "36": "數位雲端",
    "37": "運動休閒",
    "38": "居家生活",
    "91": None,   # 臺灣存託憑證(TDR):官方產業別名稱空白
}

#: 產業別取法版本(寫進 daily_net.parquet 每列 `industry_scheme`;cron 據此回補舊取法寫入的日子)。
#: 取法改版時遞增;字串完全相等才視為「已是現行取法」。
INDUSTRY_SCHEME_VERSION: str = "z43-official-code-v1"
#: 某市場官方端點本次失敗 → 該次寫入列的 scheme 加此後綴(≠ 現行版本 → 官方恢復後自動回補重算)。
INDUSTRY_SCHEME_DEGRADED_SUFFIX: str = "+official_unavailable"

#: 寬鬆比對只去掉**一個**尾字,且只在去掉後仍 ≥ 2 字時去(避免「其他」→「其」)。
_LOOSE_SUFFIXES: tuple[str, ...] = ("業", "類")
_LOOSE_MIN_LEN: int = 3


def official_industry_name(code) -> str | None:
    """官方代碼 → 官方名稱;代碼不在表內 / 官方名稱空白 → None(⛔ 不臆造)。"""
    return OFFICIAL_INDUSTRY_CODE_NAMES.get(str(code or "").strip())


def loose_industry_name(name) -> str:
    """選列用寬鬆形:去空白(含全形)後,若長度 ≥ 3 且以「業」或「類」結尾 → 去掉該一個尾字。

    例:'建材營造業'→'建材營造'、'其他業'→'其他'、'居家生活類'→'居家生活'、'其他'→'其他'。
    ⚠️ 只用於「FinMind 某列是否就是官方那個產業」的比對,**不是**同義判定
    (同義合併只走 `shared.sector_flow_thresholds.SECTOR_CANONICAL_ALIASES`)。
    """
    s = str(name or "").strip().replace(" ", "").replace("　", "")
    if len(s) >= _LOOSE_MIN_LEN and s.endswith(_LOOSE_SUFFIXES):
        s = s[:-1]
    return s
