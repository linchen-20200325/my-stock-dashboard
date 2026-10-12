"""shared/sector_flow_thresholds.py — 板塊資金泡泡圖常數 SSOT(L0)。

板塊資金泡泡圖 Stage 1:把「per-stock 每日三大法人淨買超(張)× 收盤 × 產業別」
彙總成 per-sector 每日 net 金額,再由近 N 交易日序列算出每板塊四指標:
    X    = 近 WINDOW_X 交易日 Σ 金額(億)             — 漲潮/退潮軸
    Y    = 近段 5 日日均 − 前段 5 日日均(億/天)      — 動能/加速度軸
    size = 近 WINDOW_SIZE 交易日淨額絕對值(億)        — 規模

CLAUDE.md §3.3 反捏造:所有窗長 / 單位換算 / 象限標籤 / 門檻一律從本檔引入,
禁止 inline magic number。純常數模組,零 import 依賴(可被全層 import)。

單位換算鐵則(§4.1 量綱陷阱)
============================
T86 / TPEX 三大法人回傳單位是**張**(fetcher 已 `round((buy-sell)/1000, 1)`);
收盤價是**元/股**。金額換算必須:
    net_amt_yuan = net_lots(張) × SHARES_PER_LOT(1000 股/張) × close(元/股)   [元]
    net_amt_yi   = net_amt_yuan / YUAN_PER_YI(1e8)                            [億]
漏乘 SHARES_PER_LOT = 1000 倍低估;漏除 YUAN_PER_YI = 1e8 倍高估。
"""
from __future__ import annotations

# ── 單位換算(§4.1)────────────────────────────────────────────────────
SHARES_PER_LOT: int = 1000        # 1 張 = 1000 股(張 → 股 還原)
YUAN_PER_YI: float = 1e8          # 1 億 = 100,000,000 元(元 → 億)

# ── 交易日視窗(§4.5 交易日 ≠ 日曆日;下列全指「交易日」窗)──────────────
WINDOW_X: int = 5                 # X 軸:近 5 交易日金額「總和」(億)
WINDOW_Y_RECENT: int = 5          # Y 軸近段:最近 5 交易日
WINDOW_Y_PRIOR: int = 5           # Y 軸前段:再往前 5 交易日(第 6~10 交易日)
WINDOW_SIZE: int = 20             # size:近 20 交易日淨額(取絕對值)

#: Y 軸所需最少交易日 = 近段 + 前段(不足 → 動能不可算,標資料不足)。
WINDOW_Y_MIN_DAYS: int = WINDOW_Y_RECENT + WINDOW_Y_PRIOR   # 10

# ── 象限標籤(§3.3 具名 SSOT;與需求四象限一致)────────────────────────
#   X>0, Y>0 → 漲潮   |  X>0, Y<0 → 輪動
#   X<0, Y<0 → 退潮   |  X<0, Y>0 → 觀望
# 邊界慣例:X/Y **恰為 0** 視為「非負側」(>=0),
#   即 x>=0 為右半(漲潮/輪動)、y>=0 為上半(漲潮/觀望)。
#   實務上億級 float 幾乎不可能剛好 0.0,此慣例只為讓四象限**無縫、無第五態**。
QUADRANT_RISING: str = "漲潮"      # X>=0, Y>=0:資金持續流入且動能增強
QUADRANT_ROTATING: str = "輪動"    # X>=0, Y<0 :仍淨流入但動能轉弱(資金外移前兆)
QUADRANT_EBBING: str = "退潮"      # X<0,  Y<0 :資金流出且加速
QUADRANT_WATCHING: str = "觀望"    # X<0,  Y>=0:淨流出但動能回升(觸底觀察)
QUADRANT_INSUFFICIENT: str = "資料不足"   # 交易日 < WINDOW_Y_MIN_DAYS,動能無法判定
#: 批 Z39(客戶 Q-z26=A):板塊在 X/size 窗口內有缺值(未取得/未觀測)→ 不補 0、不畫泡泡,
#: 標此態。與 `QUADRANT_INSUFFICIENT`(窗口太短)並列;兩者同時成立時 `資料不足` 優先。
QUADRANT_UNAVAILABLE: str = "未取得"

# ── 板塊/產業(§4.6 邊界:無產業別的股票不猜產業)────────────────────────
#: ticker 無 industry_category(新上市未收錄 / ETF / 權證)→ 歸此桶,不臆造。
SECTOR_UNCLASSIFIED: str = "未分類"

# ── ETF 家族板塊別名正規化(§3.3 別名走 SSOT,不 inline)──────────────────
#: `fetch_industry_map_bulk` 對不同上市/上櫃 ETF 給的細分標籤不一致
#: (上市 → "ETF"、上櫃 → "上櫃ETF" 或 "上櫃指數股票型基金(ETF)")。
#: ~~但泡泡圖三大法人聚合桶只會出現單一 "ETF"~~ —— 批 Z43 更正(事實更正,不是漏刪):
#: 舊句不實,實際 daily_net 的原始桶同時有 "ETF"、"上櫃ETF"、"上櫃指數股票型基金(ETF)" 三個;
#: 自批 Z43 起泡泡改在**標準化軸**彙總(`SECTOR_CANONICAL_ALIASES` → 單一 "ETF" 泡泡)。
#: ⚠️ ETN / 受益證券 / 存託憑證屬不同商品,**不**併入 ETF。
SECTOR_ETF_CANONICAL: str = "ETF"
SECTOR_ETF_FAMILY_ALIASES: frozenset = frozenset({
    "ETF", "上市ETF", "上櫃ETF",
    "指數股票型基金(ETF)", "上市指數股票型基金(ETF)", "上櫃指數股票型基金(ETF)",
})

# ── 批 Z43(客戶 Q-z29＝A):板塊名稱標準化別名表 SSOT ─────────────────────────
#: 原始板塊標籤 → 標準板塊標籤。**資料層不覆寫**(daily_net.parquet `sector` 欄、ticker_sector.json
#: 維持原始標籤),只在 L2 `canonicalize_sector_daily`(泡泡彙總前)與持股高亮比對時套用。
#: 收錄原則:**只**收「官方定義或實際成分確認為同義」者,每項附證據;不因名稱相似就合併。
#: 證據來源:GitHub runner 探針第 7 輪 run 38191149822(官方 openapi 產業別代碼 × ISIN 公開頁)。
#: ❌ 刻意不收:「創新版股票/創新板股票」(官方「創新板」是**證券類別**不是產業別,個股各有官方產業別,
#:    由產業別取法改依官方代碼解決);「農業科技/農業科技業」(新 map 下「農業科技」3 檔成員**皆官方查無**、
#:    「農業科技業」4 檔為代碼 33 —— 無法證明同代碼,不得合併;舊 map 成員官方為 20/22 亦不同);
#:    ETN ⛔ 不併入 ETF(官方證券類別不同:ETF CFI CE、ETN CFI CM)。
SECTOR_CANONICAL_ALIASES: dict[str, str] = {
    # 證據分兩種(據實):「舊 map」＝批 Z43 前取第一列的 ticker_sector.json 成員 × 官方代碼(探針第 7 輪
    #   run 38191149822);「新 map」＝改依官方代碼選列後(探針第 8 輪 run 38193131712,
    #   tests/fixtures/z43_label_official_codes.json,'-' ＝ 官方查無)。
    # 代碼 16「觀光餐旅」:'觀光事業' **舊 map** 成員 → openapi 上市 16×17、上櫃 16×24(另 4 檔官方為別的產業)。
    #   ⚠️ 新 map 下這些股已直接選到 FinMind「觀光餐旅」列,'觀光事業' 只剩 1 檔且為官方查無 → 新 map 無法再
    #   以代碼佐證;保留理由:①舊取法寫入的歷史列(daily_net 回補前)仍帶此標籤;②FinMind 對官方查無標的
    #   仍可能給此名稱;同義性已由舊 map 的官方代碼證明。
    "觀光事業": "觀光餐旅",
    # 代碼 36「數位雲端」:'數位雲端類' 舊 map 成員 → 上櫃 36×2;新 map 36×18(與 '數位雲端' 36×22 同代碼)
    "數位雲端類": "數位雲端",
    # 代碼 35「綠能環保」:'綠能環保類' 舊 map → 上櫃 35×2;新 map 35×15(與 '綠能環保' 35×31 同代碼)
    "綠能環保類": "綠能環保",
    # 代碼 38「居家生活」:'居家生活類' 舊 map → 上櫃 38×2;新 map 38×21(與 '居家生活' 38×15 同代碼)
    "居家生活類": "居家生活",
    # 代碼 31「其他電子業」:'其他電子類' 舊 map → 上櫃 31×38;新 map 31×40(與 '其他電子業' 31×54 同代碼)
    "其他電子類": "其他電子業",
    # 代碼 17「金融保險業」(客戶已裁):'金融業' **舊 map** 成員 → 上櫃 17×9;上市 '金融保險' → 17×31。
    #   ⚠️ 新 map 下那 9 檔改選官方名 '金融保險業'(見下),'金融業' 只剩 6 檔且皆官方查無 → 新 map 無法再以
    #   代碼佐證;保留理由同 '觀光事業'(舊取法歷史列 + FinMind 對官方查無標的的命名),且為客戶明示裁示。
    "金融業": "金融保險",
    # ── 以下兩項:改依官方代碼選列後「同一官方代碼卻兩種標籤」(探針第 8 輪 run 38192607977 實測;
    #    證據＝成員官方代碼完全相同,見 tests/fixtures/z43_label_official_codes.json)──
    # 代碼 17:'金融保險業'(上櫃 9 檔,FinMind 只有「金融業」列、無相符列 → 取官方名)全為 17,'金融保險' 為 17×31
    "金融保險業": "金融保險",
    # 代碼 37「運動休閒」:'運動休閒類' 成員官方代碼 37×8、'運動休閒' 37×19
    "運動休閒類": "運動休閒",
    # ETF 家族(客戶已裁):官方同屬「ETF」證券類別、CFI 前 2 碼 CE、產業別欄空白(上市 241 / 上櫃 119 檔)。
    #   成員直接取自**既有**(批 Z43 前即存在、持股高亮已在用)的 `SECTOR_ETF_FAMILY_ALIASES`,不是本批新增;
    #   其中 '上市ETF' / '指數股票型基金(ETF)' / '上市指數股票型基金(ETF)' 在新舊 map 皆未出現(探針第 7/8 輪),
    #   保留只為維持既有 ETF 家族行為不變。實際出現者:'上櫃ETF'、'上櫃指數股票型基金(ETF)'。
    **{_a: SECTOR_ETF_CANONICAL for _a in sorted(SECTOR_ETF_FAMILY_ALIASES)
       if _a != SECTOR_ETF_CANONICAL},
    # ETN:官方同屬「ETN」證券類別、CFI 前 2 碼 CM(上市 15 / 上櫃 6 檔)
    "指數投資證券(ETN)": "ETN",
}
#: 別名表版本(寫進 bubble_latest.json `sector_aliases_version`;別名表任何增刪都要遞增)。
SECTOR_ALIASES_VERSION: str = "z43-v1"


def canonical_sector(label) -> str:
    """原始板塊標籤 → 標準板塊標籤(`SECTOR_CANONICAL_ALIASES` SSOT;不在表內 → 原樣)。

    批 Z43 前只正規化 ETF 家族;起改以別名表為 SSOT(ETF 家族照舊對到 "ETF",持股高亮比對與泡泡
    標準化軸一致)。純函式、零 I/O。
    """
    s = str(label or "").strip()
    return SECTOR_CANONICAL_ALIASES.get(s, s)

# ── 批 Z41(客戶 Q-z27＝A):外幣交易 ETF 幣別混用防護(§4.1 Level 1 單位錯誤)──────────
#: 板塊金額 = 張 × 1000 × 收盤(元)。外幣交易 ETF 的收盤是**外幣**報價,乘進去＝把美元/人民幣
#: 當新台幣加總(不可比值)。官方 notes 原文:
#:   TPEx「ETF證券代號第六碼為K、C者，表示該ETF以外幣交易」;TWSE 為 K、M、S、C。
#: ⇒ 上市上櫃共用:代號第六碼(0-based index 5)落在下列集合 → L2 排除該股日(計數、log),
#: **不是補值、不動個股法人張數本身**。
FOREIGN_CCY_CODE_CHAR_INDEX: int = 5
FOREIGN_CCY_CODE_6TH_CHARS: frozenset = frozenset({"K", "C", "M", "S"})


#: 批 Z41 修正(QA L3):官方 notes 只說「**ETF** 證券代號第六碼…」⇒ 只對 ETF 代號(以 "00" 開頭)
#: 判定;`03001C`、`02001S` 等非 ETF 代號不排除。
FOREIGN_CCY_ETF_CODE_PREFIX: str = "00"


def is_foreign_ccy_code(code) -> bool:
    """ETF 代號(以 "00" 開頭、長度 ≥ 6)且第六碼 ∈ {K, C, M, S}(外幣交易 ETF)→ True;其餘 False。"""
    s = str(code).strip().upper()
    return (s.startswith(FOREIGN_CCY_ETF_CODE_PREFIX)
            and len(s) > FOREIGN_CCY_CODE_CHAR_INDEX
            and s[FOREIGN_CCY_CODE_CHAR_INDEX] in FOREIGN_CCY_CODE_6TH_CHARS)


# ── 批 Z41 修正(QA H1):產業別對映可信度門檻 ─────────────────────────────────
#: 本次 `fetch_industry_map_bulk` 清洗後代號數相對上一份 ticker_sector.json **縮水超過**本比例
#: → 視為來源部分失敗(例:FinMind 被 gate、openapi 只回一個市場),cron 不改寫任何既有日。
#: 理由:全市場上市櫃(含 ETF)約 3,000+ 檔,日常增減(新上市/下市)每日僅數檔、一年 < 5%;
#: 20% 遠高於正常波動、遠低於「少掉整個市場」(上櫃約佔 1/3)的故障幅度,兩側都有餘裕。
INDUSTRY_MAP_MAX_SHRINK_RATIO: float = 0.20


#: 一個板塊在某交易日「有效成分股」數量下限;低於此該板塊當日流入代表性不足。
#: 目前僅作為 coverage 診斷欄位輸出(不濾除),Stage 2 畫圖可據此決定是否淡化顯示。
MIN_SECTOR_STOCKS: int = 1

# ── Stage 2 UI:快取新鮮度門檻(§3.3 具名常數;§4.1 交易日≠日曆日)──────────
#: bubble/metadata 快取「過期」的 wall-clock 上限(日曆日)。cron 每個「交易日」凍結一次,
#: 業務語意是「允許落後 2 個交易日」;但跨週末 2 個交易日最長 = 週五→週二 = 4 個日曆日,
#: 故以 4 個日曆日作為 metadata.updated_at 距今的 staleness wall-clock 門檻(超過 → is_stale)。
SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS: int = 4

# ── 批 Z39(客戶 Q-z28=A):上櫃(TPEx)未納入時的提示文字(兩個 UI 消費點共用,逐字)──
#: 泡泡圖窗口內只要有一個交易日 TPEx 沒成功納入 → bubble_latest.json `tpex_complete` 非 True
#: → `tab_sector_flow` 與 v2「🔍 找標的」葉2 在圖下方以灰字 caption 顯示本句;
#: TPEx 恢復且整個窗口皆驗證成功 → `tpex_complete is True` → 自動不顯示(資料驅動)。
SECTOR_FLOW_TWSE_ONLY_NOTE: str = "目前僅含上市資料"
#: 缺值板塊列名的前綴(沿用 `src/ui/tabs/macro/section_chips.py` 既有「⬜ 未取得：」字樣)。
SECTOR_FLOW_UNAVAILABLE_PREFIX: str = "⬜ 未取得："


def format_unavailable_caption(sectors) -> str | None:
    """「⬜ 未取得：A、B」;沒有未取得板塊 → None(L5 不畫 caption)。

    批 Z39:兩個 UI 消費點(`tab_sector_flow` / v2 `page_find`)共用同一份格式(純函式、零 I/O)。
    只列 `unavailable` 為 True 的板塊;交易日不足(insufficient)
    的板塊另有既有「🕓 資料不足」說明,不在此重複。
    批 Z42:只輸出核准前綴＋板塊名(以「、」串接)。原「（缺 N 日）」片段無客戶核准出處 → 移除;
    `n_missing_days` 資料欄位仍由 L2 計算並保留於 metadata,只是不顯示。
    """
    _items = []
    for r in sectors or ():
        if not hasattr(r, "get") or r.get("unavailable") is not True or r.get("insufficient"):
            continue
        _items.append(str(r.get("sector")))
    return (SECTOR_FLOW_UNAVAILABLE_PREFIX + "、".join(_items)) if _items else None
