"""src/ui/views/_target_blocks.py — 🎯 標的頁（UI-T，2026-10-29）頁內自有區塊（L5 UI）。

單一職責：把 `page_target.render_page_target()` 的各區（單檔入口、第一區產業機會、第二區候選標的、第三區單一股票、
進階分析）拆成「純函式（可單測）＋薄渲染」。`page_target.py` 只負責編排與逐區隔離。

規格出處：客戶 2026-10-29 已核准線框 `docs/vnext/NEWUI_D25_UIT_WIREFRAME_2026-10-29.md`（裁示 1A 2A 3A 4A 5A；全文即規格）
＋ `docs/vnext/d25_wireframes/target.html` ＋ A 規格 §4.2（DEC-092／DEC-099）。與線框的偏離逐項列在 PR 描述。

═══ 這個檔**不是**什麼 ═══════════════════════════════════════════════
- **不是新的取數／公式／投資語意**：選股、板塊地圖、單檔判型與三分支、批次，**全部**呼叫 `page_find` / `page_inspect`
  既有的 loader 與 builder（同一個輸入 ⇒ 同一張卡；`tests/test_uit_target_page.py` 以冷／熱 session parity 釘住）。
  本檔只負責「把它們排在同一頁、換掉工程字樣的指路句」。
- **只新增一支薄 L3**：`services.target_industry_service.get_ticker_sector_map()`（候選表「產業」欄；既有 `ticker_sector.json`
  的唯讀視圖，不新增來源）。⛔ 本檔不 import `src.data.*`。
- **不建快取**（無 `st.cache_*`）。但每個「使用者要求」的結果會在 session 內**記住到下一次要求**（`memoized`）：
  不是為了省時間，而是**操作隔離**（按「載入板塊地圖」「查看此檔」「下鑽」只是 rerun，不得重打選股或單檔 L3）與
  **失敗不被轟炸**（§1.A-3(b)：失敗的結果也只呈現到使用者再按一次，rerun 不會自動重打上游）。
  代價：同一 session 內，結果不會因 L1 TTL 到期自動更新 —— 要更新就再按一次該區的送出鈕。
- **舊檔不動**：`page_find.py` / `page_inspect.py` 一字未改（legacy D2 殼仍獨立渲染它們）；同名底線函式（`_render_one`、
  `_inject_v2_css`…）刻意**不合併**，兩族 v2 卡面各走各的 renderer，CSS 由本檔 `inject_css()` 一次吐齊並關掉 `page_find` 的重複注入。

§1／v3 §02：缺維度一律「⬜」顯式，⛔ 不當 0／中性／續抱；未載入＝灰、真出錯＝紅；狀態不只靠顏色（每個狀態都有文字）。
"""
from __future__ import annotations

import html as _html
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import streamlit as st

from shared import price_asof_label as PAL
from shared.fundamental_prescreen_thresholds import (
    DEBT_RATIO_MAX,
    EPS_MIN,
    PRESCREEN_REQUIRED_PASSES,
)
from shared.health_thresholds import HEALTH_GRADE_B_MIN
from shared.secret_scrub import scrub_secrets
from shared.sector_flow_thresholds import (
    QUADRANT_INSUFFICIENT,
    QUADRANT_ROTATING,
    QUADRANT_EBBING,
    QUADRANT_RISING,
    QUADRANT_WATCHING,
    SECTOR_FLOW_TWSE_ONLY_NOTE,
    SECTOR_UNCLASSIFIED,
    WINDOW_X,
    canonical_sector,
    format_unavailable_caption,
)
from shared.ttls import TTL_1DAY, TTL_1HOUR, TTL_30MIN
from shared.ui_state import UI_EMPTY, UI_IDLE, UI_LIVE, UI_PARTIAL, UI_STATE_META, UI_UNWIRED
from src.ui.tabs.tab_today import scrub_state_glyphs
from src.ui.views import page_find as F
from src.ui.views import page_inspect as I
from src.ui.views._ui_kit import MAX_COLS, grid, section_header
from src.ui_v2 import compact as cp
from src.ui_v2 import markup as v2_markup

# ══════════════════════════════════════════════════════════════════
# session key（本頁自有前綴 `ptg_`；widget 沿用 `p02v_*`／`p03v_*` 的既有 key —— 新版模式下舊頁不會同輪渲染）
# ══════════════════════════════════════════════════════════════════
#: 各「使用者要求」的世代計數器：只在對應的送出／按鈕 handler 內 +1。
SS_GEN_TICKER: str = "_ptg_gen_ticker"
SS_GEN_SCREEN: str = "_ptg_gen_screen"
SS_GEN_MAP: str = "_ptg_gen_map"
SS_GEN_BATCH: str = "_ptg_gen_batch"
#: 結果記憶（`memoized`）的 key 前綴。
SS_MEMO_PREFIX: str = "_ptg_memo_"
#: 候選表下方「選一檔＋🔍 查看此檔」。
SS_PICK_WIDGET: str = "ptg_pick_widget"
SS_PICK_BUTTON: str = "ptg_pick_button"
SS_CSV_BUTTON: str = "p02v_screen_csv"

# ══════════════════════════════════════════════════════════════════
# 字樣（客戶線框 S10；自擬處在 PR 描述的「文案」一節列出）
# ══════════════════════════════════════════════════════════════════
PAGE_TITLE: str = "🎯 標的"
PAGE_SUBTITLE: str = "目前市場裡有哪些值得研究的股票？"
HEALTH_CHIP: str = "⬜ 資料狀態：尚未彙總"
AI_PLACEHOLDER: str = "🤖 AI 投資總結：⬜ 尚未提供"
SEARCH_PLACEHOLDER: str = "輸入代碼（例：2330 或 00878）"
ADV_LABEL: str = "進階選項（判型・期間・均線）"
MA_ONLY_DISPLAY_NOTE: str = "僅顯示：勾選只會回顯在判型結果；K 線與均線圖新版尚未接上，不影響任何結論。"
MA_GROUP_LABEL: str = "**均線（僅顯示）**"
PERIOD_NOTE: str = "期間只決定籌碼載入多長的日線；近 20 日的判讀窗由上游決定，改期間不會改變籌碼結論。"
REAL_PRICE_NOTE: str = "K 線一律用還原價（已還原除權息）。"

ZONE1_TITLE: str = "第一區｜產業機會"
ZONE1_SAY: str = "先找正在變強的產業，再從產業裡找公司；避免只看單一股票短線漲跌。"
ZONE1_SORT_NOTE: str = "排序依據：法人資金動能，非產業趨勢。"
#: F9：這段說明收進第一區的「🔍 查看依據」（規則欄），首屏只留客戶原句＋排序依據。
ZONE1_NO_TREND_NOTE: str = "產業趨勢為研究中，尚未定義；本表不判斷產業興衰，沒有正式資料的維度一律顯示 ⬜，不補值、不由 AI 補。"
ZONE1_IDLE: str = "按下「🗺️ 載入板塊地圖」後顯示產業資料（在按之前不會取數）。"
MATRIX_COLS: tuple[str, ...] = ("產業", "基本面成長", "相對強弱", "法人／籌碼", "估值", "資料可信度")
NOT_BUILT: str = "⬜ 尚未建置"
STRENGTH_ONLY_FLOW: str = "⬜（僅有資金動能，非價格相對強弱）"
FLOW_MISSING: str = "⬜ 資料不足（窗口內缺值，不補 0）"
HEATMAP_EXPANDER: str = "產業漲跌熱力圖（單一代表股近似，非類股指數）"
BUBBLE_EXPANDER: str = "三大法人資金流泡泡圖（含持股⭐）"
HEATMAP_SWITCH_PLAIN: str = "本頁固定畫這一組；新版尚未提供切換市場或區間。"
#: P5-1（客戶 DEC-121 Q1=A／Q3=A；線框 §4／§10 C1-3／C1-4／C2-3／C3-2）第一區 Primary：產業 Top 5 橫條。
#: 排序鍵 ＝ 既有欄位 `x_yi`（近 `WINDOW_X` 日法人累計淨流入，億）由大到小 —— **僅是 Top 5 的顯示排序**，
#: ⛔ 不改候選池／個股排序／Risk Cap／趨勢定義；「查看全部」內的 6 欄表維持原順序（象限→產業名稱）。
ZONE1_RANK_FIELD: str = "x_yi"
ZONE1_TOP_N: int = 5
#: Primary 圖槽高（契約 §19 Q3：桌機 ≤220、手機 ≤140 ⇒ 兩者共用 140；冷啟動／無資料的槽同高，D6=B）。
ZONE1_CHART_HEIGHT_PX: int = 140
ZONE1_TITLE_FMT: str = "產業 Top {n}｜近 {w} 日法人累計淨流入（億）"
#: 缺值列在圖上的文字（⛔ 不畫 0、不畫條；完整原因「窗口內缺值」在『查看全部』的 6 欄表）。
ZONE1_ROW_MISSING: str = "⬜ 資料不足"
#: 區塊級 Missing（取代矩陣每列重複的三句；摺疊內的完整表仍逐列保留）。
ZONE1_MISSING_DIMS: str = "⬜ 基本面成長／相對強弱／估值：尚未建置"
ZONE1_ALL_LABEL_FMT: str = "▸ 查看全部（{n} 個產業）"
ZONE1_FOLD_WHERE_FMT: str = "完整產業清單（6 欄表、未取得名單、資料範圍與過期說明）請展開下方「{label}」。"
ZONE1_IDLE_REASON: str = ZONE1_IDLE
#: 圖表摺疊入口（客戶 DEC-109 五原文字樣；DEC-121 Q3=A：Primary 圖用四段，其餘區塊維持「🔍 查看依據」）。恰一個。
FOLD_LABEL: str = "▸ 為什麼／來源／限制／去哪補"
FOLD_SECTIONS: tuple[str, ...] = ("為什麼", "來源", "限制", "去哪補")
#: 六欄 Basis → 四段（Phase 4 §3.5 同一映射；「去哪補」六欄沒有對應欄，由各圖另給）。
BASIS_TO_FOLD: Mapping[str, tuple[str, ...]] = {
    "為什麼": ("rule", "ai"), "來源": ("sources", "as_of"), "限制": ("missing", "confidence"), "去哪補": ()}

ZONE2_TITLE: str = "第二區｜候選標的"
ZONE2_SAY: str = "優先看基本面，再看價格與技術面。選一檔，下方展開單一股票。"
SCREEN_EXPANDER: str = "選股條件"
#: P5-2（客戶 DEC-121 Q2=B；線框 §10 C1-7）：選股條件 expander **預設收合**＋外露一行摘要。
#: ⚠️ 收合只是畫面：form、🎯 開始選股鈕、所有 gate 都還在 expander 裡照常執行（收合≠少抓／少算）。
SCREEN_EXPANDER_EXPANDED: bool = False
#: 摘要只轉述「已套用條件；還沒按過 🎯 開始選股就轉述預設條件」，⛔ 新增任何條件。
SCREEN_SUMMARY_FMT: str = "{n} 項基本面全過{factors}；排序：綜合評分；顯示 {top} 筆"
#: P5-2（DEC-121 Q2=B；C1-5／C1-6）：候選外露 Top 10 —— **純顯示切片**（保序、不重算）。
#: ⛔ 與請求參數 `F.TOP_N_OPTIONS`／`F.DEFAULT_TOP_N`（20／50／100、預設 50）無關，兩者不動。
CANDIDATE_TOP_N: int = 10
#: 估值口徑外露 chip（護欄族；全文 `PE_COL_NOTE` 逐字在「說明」摺疊內，兩者必須同時存在）。
PE_BASIS_CHIP: str = "估值口徑≠第三區 357（不能互相驗證）"
CANDIDATE_NOTES_EXPANDER: str = "▸ 說明（估值口徑・籌碼未取・金融股）"
CANDIDATE_COLS: tuple[str, ...] = ("標的", "產業", "基本面", "估值", "籌碼", "狀態")
PICK_LABEL: str = "選擇標的"
PICK_BUTTON_LABEL: str = "🔍 查看此檔"
#: P5-3 A8：全文（`PICK_NOTE`）逐字下沉到「▸ 說明」摺疊（L3）；外露只留短句（非客戶原句，可縮）。
PICK_NOTE: str = "選一檔後按「🔍 查看此檔」才會取這一檔的資料；候選表本身不會自動逐檔取數。"
PICK_NOTE_SHORT: str = "按「🔍 查看此檔」才取該檔資料。"
CHIPS_NOT_FETCHED: str = "未取（展開後顯示）"
CHIPS_COL_HINT: str = "籌碼欄：點選一檔後才會取，其他候選顯示「未取」，不是沒有資料。"
PE_COL_NOTE: str = ("估值欄是當日本益比（資料日：⬜ 未提供）；第三區的估值是另一種算法（殖利率口徑），"
                    "兩者不同、不能互相驗證。")
FIN_STOCK_NOTE: str = "金融股沒有營收數字，會在基本面初篩被排除，不是資料壞了。"
STATUS_PASSED: str = "通過初篩"
STATUS_INSUFFICIENT: str = "資料不足"
MISSING_CELL: str = "⬜ 資料不足"
PE_FAILED_CELL: str = "⬜ 取不到"
PE_NOT_PROVIDED_CELL: str = "⬜ 未提供"
SECTOR_UNAVAILABLE_CELL: str = "⬜ 產業對映尚未產生"
SECTOR_READ_FAILED_CELL: str = "⬜ 產業對映讀取失敗"

ZONE3_TITLE: str = "第三區｜單一股票"
ZONE3_IDLE: str = "還沒選標的：在上方輸入代碼，或在候選表選一檔。"
EPS_BLOCK: str = "EPS／營收"
EPS_PLACEHOLDER: str = "⬜ 趨勢圖尚未建置"
TREND_BLOCK: str = "財報體檢（健康度）"
VALUATION_BLOCK: str = "估值（357 存股估值）"
CHIPS_BLOCK: str = "籌碼"
RISK_BLOCK: str = "風險"
RISK_PLACEHOLDER: str = "⬜ 個股風險指標尚未提供"
RISK_NOTE: str = "目前只有財報體檢未通過項目與籌碼的單日爆量檢查，分別列在「為什麼不能買／資料不足」與「籌碼」。"
WORTH_BLOCK: str = "為什麼值得看"
WORTH_EMPTY: str = "⬜ 目前沒有可列的命中項目（可能尚未載入選股結果，或資料不足）"
WORTH_NOTE: str = "只列已命中的既有檢查（通過／達標者），不構成買賣判斷。"
WHY_NOT_BLOCK: str = "為什麼不能買／資料不足"
FACTS_ONLY_NOTE: str = "僅列事實，不下買賣判斷"
RESEARCH_ONLY_NOTE: str = "本頁只呈現研究資訊，不提供交易操作"
WHY_NOT_EMPTY: str = "⬜ 目前沒有可列的未通過項目或資料缺漏"
PROFIT_HEADER: str = "💰 獲利能力診斷"
PROFIT_CAPTION: str = "缺值是灰的「資料缺漏」，不是紅的「辛苦生意」。"
ETF_HEADER: str = "ETF"
UNKNOWN_HINT: str = "這個代碼系統無法判定是個股或 ETF；可展開上方「進階選項」手動指定判型後再載入。"

#: P5-3（客戶 DEC-121／DEC-107 補充；線框 §3.4／§10 C2-5～C2-7）第三區「單一股票」：判型卡 → chip、≤4 摘要卡＋主圖槽、
#: 計數 chip（命中／未通過·缺漏，**分開兩顆**）、「▸ 完整分析」（七區塊＋獲利能力診斷）**預設收合且原樣**（資訊只下沉、不刪）。
#: ⛔ 摘要卡的值只取既有 builder／readout 欄位（不新增計算）；⛔ 不合成「單一結論／評分／HOLD／買賣」。
#: 暫名：判型 chip／計數 chip 現以 `guard_chip`（護欄族、實線粗框）承載，因 `META_KINDS` 封閉集無 info 族自由文字 kind
#: （登記 BACKLOG `P5-CHIP-KIND-NAMES`；待總管決定是否新增 kind）。
KIND_CHIP_STOCK: str = "🏢 個股"
KIND_CHIP_ETF: str = "ETF"
KIND_SRC_AUTO: str = "自動判型"
KIND_SRC_MANUAL: str = "手動指定"
KIND_DETAIL_EXPANDER: str = "▸ 判型明細"
SUMMARY_HEALTH_LABEL: str = "財報體檢"
SUMMARY_VALUATION_LABEL: str = "357 估值"
SUMMARY_CHIPS_LABEL: str = "近 20 日籌碼"
HIT_CHIP_FMT: str = "✅ 命中 {n} 項"
MISS_CHIP_FMT: str = "⬜ 未通過／缺漏 {m} 項"
NOT_EVALUATED_CHIP: str = "⬜ 尚未評估"
PARTIAL_NOT_EVALUATED_FMT: str = "⬜ {k} 塊尚未評估"
#: 主圖槽（誠實 placeholder：K 線新版尚未接上；`UI_UNWIRED`＝⛔ 未接線，灰、不是紅、不畫任何線）。
SINGLE_CHART_REASON: str = "K 線新版尚未接上"
SINGLE_CHART_HEIGHT_PX: int = 96
FULL_ANALYSIS_EXPANDER: str = "▸ 完整分析（七區塊＋獲利能力診斷）"

ADVANCED_EXPANDER: str = "進階分析"
BATCH_TITLE: str = "多檔比較（可混貼）"
UNCOVERED_TITLE: str = "仍未覆蓋的功能"
DEFAULT_MODE_NOT_YET: str = "新版尚未提供，後續批次處理"
UNCOVERED_ITEMS: tuple[tuple[str, str], ...] = (
    ("加入觀察清單", "會寫入您的 Google Sheet，新版尚未接上"),
    ("凍結前 20 名", "把當期前 20 名存檔留作日後對帳，新版尚未接上"),
    ("前進式驗證對帳", "凍結名單與事後真實股價的對帳，新版尚未接上"),
    ("跨季趨勢排行（含下載）", "新版尚未接上"),
    ("個股的 K 線與明細七段", "K 線＋均線、357 評價河流圖、財報領先指標、VCP／布林、月營收、什麼時候買賣、心理檢查；新版尚未接上"),
    ("ETF 的明細七段", "淨值 vs 市價走勢、折溢價帶、配息紀錄與以息養股試算、成分股與集中度、同儕 7 維評分、標準差買賣帶、破發檢查；新版尚未接上"),
    ("用名稱搜尋", "目前只能輸入代碼"),
    ("帶入我的持股", "新版尚未接上"),
)
UNCOVERED_LEAD: str = "這些功能目前尚未提供，不會出現在這一頁："
UNCOVERED_FOOT: str = f"以上功能：{DEFAULT_MODE_NOT_YET}。這不是資料壞了，也不是被刪除。"
BATCH_NOTE: str = ("批次表的每一列走的是與單檔同一支取數，所以個股給財報體檢分數、ETF 給折溢價／配息／同儕。"
                   "估值（357）與籌碼不在批次表裡 —— 一次 20 檔會把等待時間變成好幾倍，這是刻意不做；"
                   "要看那兩格，請在第三區載入同一個代碼。")
DRILL_FOOT: str = ("要看完整判決卡與明細，請在上方搜尋框輸入同一個代碼後按「🔍 載入完整分析」，"
                   "第三區會走完整的個股或 ETF 版型。")

BASIS_EXPANDER_LABEL: str = "🔍 查看依據"
BASIS_FIELDS: tuple[tuple[str, str], ...] = (
    ("使用的資料", "sources"), ("資料日期", "as_of"), ("規則", "rule"),
    ("missing", "missing"), ("confidence", "confidence"), ("AI 是否參與", "ai"))
AI_NOT_INVOLVED: str = "否（本區是既有規則與資料的直接呈現，沒有 AI 參與）"


# ══════════════════════════════════════════════════════════════════
# 小工具
# ══════════════════════════════════════════════════════════════════
def _fmt_f(value: Any, digits: int = 1) -> str | None:
    """數字 → 字串；缺值／NaN／inf／非數字 → None（⛔ 不寫 0）。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        _v = float(value)
    except (TypeError, ValueError):
        return None
    return f"{_v:.{digits}f}" if math.isfinite(_v) else None


def _md_safe(text: Any) -> str:
    """要放進 `st.caption/markdown` 的上游例外原文：先洗秘密與 glyph，再跳脫 `*`（同 page_find 作法）。"""
    return scrub_state_glyphs(scrub_secrets(str(text)))[0].replace("*", "\\*")


def guard(name: str, fn: Callable[[], None]) -> None:
    """逐區隔離：一區例外 ⇒ 就地一行**紅字**（看得見），其餘區照畫（⛔ 不吞）。"""
    try:
        fn()
    except Exception as _e:  # noqa: BLE001 — 轉成看得見的紅字，不吞
        _err = _md_safe(repr(_e))
        print(f"[views/page_target] 區塊 {name!r} 畫不出來：{_e!r}")
        st.error(f"🔴 「{name}」這一區畫不出來（其他區照常）：{_err or F.UNKNOWN_ERROR_TEXT}", icon="🔴")


TAIPEI = timezone(timedelta(hours=8))
#: 記住的結果的欄數：(世代, 結果, 載入時間)。
_MEMO_LEN = 3


def now_taipei() -> datetime:
    """台北時間現在。⚠️ 測試以 `monkeypatch.setattr(B, "now_taipei", ...)` 注入假時鐘（呼叫端查模組屬性）。"""
    return datetime.now(TAIPEI)


#: 各區「記住的結果」多久後改寫「可能已過期」。TTL 取 `shared/ttls` 的既有常數（對應該區上游最短的 L1 快取）：
#: 選股＝本益比／季快照日頻；地圖＝熱力圖 30 分鐘快取；單檔、批次＝行情／財報 1 小時。
FRESH_TTL_SEC: dict[str, int] = {"screen": TTL_1DAY, "map": TTL_30MIN, "single": TTL_1HOUR, "batch": TTL_1HOUR}
RELOAD_LABEL: dict[str, str] = {"screen": "🎯 開始選股", "map": "🗺️ 載入板塊地圖",
                                "single": "🔍 載入完整分析", "batch": "🚀 批次分析"}


def is_aged(fetched_at: datetime, now: datetime, ttl_sec: int) -> bool:
    """記住的結果是否已超過 TTL（`freshness_line` 與 header 的 stale chip 共用同一個判定，⛔ 兩套）。"""
    return (now - fetched_at).total_seconds() > ttl_sec


def freshness_line(fetched_at: datetime, now: datetime, ttl_sec: int, reload_label: str) -> str:
    """§2.4：記住的結果不得靜默過期 —— 一行灰字講「載入於幾點」與「怎麼重新載入」；超過 TTL 改寫「可能已過期」。"""
    _hm = fetched_at.astimezone(TAIPEI).strftime("%H:%M")
    _tail = f"（本次工作階段內不會自動更新；再按「{reload_label}」重新載入）"
    _aged = is_aged(fetched_at, now, ttl_sec)
    return f"此結果載入於 {_hm}，可能已過期{_tail}" if _aged else f"此結果載入於 {_hm}{_tail}"


def memo_loaded_at(session: Any, slot: str) -> datetime | None:
    _cur = session.get(f"{SS_MEMO_PREFIX}{slot}")
    if isinstance(_cur, tuple) and len(_cur) == _MEMO_LEN and isinstance(_cur[2], datetime):
        return _cur[2]
    return None


#: slot → 該區的世代計數器（只有使用者真的要求過，才有「載入於」可講；冷啟動的空殼不算）。
_SLOT_COUNTER: dict[str, str] = {"screen": SS_GEN_SCREEN, "map": SS_GEN_MAP, "single": SS_GEN_TICKER, "batch": SS_GEN_BATCH}


def freshness_text(session: Any, slot: str) -> str | None:
    """該區「載入於…」整句；使用者還沒要求過 ⇒ None（冷啟動的空殼不算）。"""
    _at = memo_loaded_at(session, slot)
    if _at is not None and own_gen(session, _SLOT_COUNTER[slot]) > 0:
        return freshness_line(_at, now_taipei(), FRESH_TTL_SEC[slot], RELOAD_LABEL[slot])
    return None


def render_freshness(session: Any, slot: str) -> None:
    _line = freshness_text(session, slot)
    if _line is not None:
        st.caption(_line)


def freshness_chips(session: Any, slot: str) -> list[Any]:
    """P5-3 A8（線框 T-18／C2-4）：外露只留 `抓取 HH:MM`（過 TTL 另加 `⚠ 可能已過期`）；整句 `freshness_text` 逐字下沉到該區
    「🔍 查看依據」摺疊（L3）。TTL 判定與整句**同一個** `is_aged`（⛔ 兩套）。冷啟動／使用者未要求過 ⇒ 空。"""
    _at = memo_loaded_at(session, slot)
    if _at is None or own_gen(session, _SLOT_COUNTER[slot]) <= 0:
        return []
    _chips: list[Any] = [cp.meta_chip("retrieved_at", _at.astimezone(TAIPEI).strftime("%H:%M"))]
    if is_aged(_at, now_taipei(), FRESH_TTL_SEC[slot]):
        _chips.append(cp.meta_chip("stale"))
    return _chips


def memoized(session: Any, slot: str, gen: Any, compute: Callable[[], Any]) -> Any:
    """依「使用者要求的世代」記住結果：同世代 ⇒ 不再呼叫 `compute`（不論成功或失敗），新世代 ⇒ 重算。

    ⛔ 不是快取層（無 TTL、不跨 session）：它是「這一次要求的答案」，隨使用者下一次送出而換。
    失敗結果也只呈現到使用者再按一次，**rerun 不會自動重打上游**（§1.A-3(b)）。
    """
    _key = f"{SS_MEMO_PREFIX}{slot}"
    _cur = session.get(_key)
    if isinstance(_cur, tuple) and len(_cur) == _MEMO_LEN and _cur[0] == gen:
        return _cur[1]
    _val = compute()
    session[_key] = (gen, _val, now_taipei())
    return _val


def _gen(session: Any, counter_key: str, applied_key: str) -> tuple[int, str]:
    """世代 ＝（計數器, 已套用值的內容）：兩者任一變就算新一次要求。"""
    return int(session.get(counter_key, 0) or 0), repr(session.get(applied_key))


def own_gen(session: Any, counter_key: str) -> int:
    return int(session.get(counter_key, 0) or 0)


def own_inspect_request(session: Any) -> Any:
    """本頁的單檔要求：**只認本頁 gate 寫入點的世代** —— legacy 殘留的 `_p03_applied_ticker` 不會觸發取數。"""
    return I.applied_inspect_request(session) if own_gen(session, SS_GEN_TICKER) > 0 else I.InspectRequest(submitted=False)


def own_screen_request(session: Any) -> Any:
    return F.applied_screen_request(session) if own_gen(session, SS_GEN_SCREEN) > 0 else F.ScreenRequest(submitted=False)


def own_batch_request(session: Any) -> Any:
    return I.applied_batch_request(session) if own_gen(session, SS_GEN_BATCH) > 0 else I.BatchRequest(submitted=False)


def own_map_requested(session: Any) -> bool:
    return F.map_requested(session) and own_gen(session, SS_GEN_MAP) > 0


def bump(session: Any, counter_key: str) -> None:
    session[counter_key] = int(session.get(counter_key, 0) or 0) + 1


#: P5-1 手機內部壓縮（線框 §4.3；總管裁示，內部自決）：窄螢幕把頁面主欄的元素間距由預設 1rem 收到 .5rem，
#: 讓第一區 Primary 圖上緣進第一屏。⚠️ 只排版：CSS 失效時＝Streamlit 預設間距，⛔ 沒有任何內容靠它才看得到；
#: 只掛在本頁（`inject_css` 只由 `render_page_target` 呼叫），不改搜尋卡結構、不改任何元件。
TARGET_LAYOUT_CSS: str = (
    "@media (max-width:768px){"
    '[data-testid="stMainBlockContainer"]>[data-testid="stVerticalBlock"]{gap:.125rem}'
    # QA P3：header 的 chip 列會溢出自己的容器（容器高 43、chip 列底部多出約 10px；main 基準已被圖頂蓋 2px，gap 收緊後蓋 6px）⇒ 補回下緣留白。
    '[data-testid="stMainBlockContainer"] .cp-chips{padding-bottom:.5rem}'
    # QA P3（cold 手機）：Primary 灰色佔位框溢出自己的容器，下方「為什麼／來源」摺疊疊在框底（main 基準同樣有）⇒ 補回下緣留白。
    '[data-testid="stMainBlockContainer"] .cp-slot-primary{margin-bottom:.75rem}'
    # P5-3 A2（線框 §4.3 內部壓縮；只排版）：元素間距收到 .125rem（原 .5rem），讓第一區 Primary 圖整張進第一屏。
    # （試過同時收 h2/h4 的 padding：標題會壓到下一行文字（實測截圖）⇒ 只收間距、不動標題。）
    '}')


def inject_css() -> None:
    """兩族 v2 卡面的樣式表**一次**吐齊（page_find 的 `_inject_v2_css` 與 page_inspect 的各吐一份 ⇒ 重複）。"""
    try:
        st.markdown(
            f"<style>{v2_markup.page_css(F.V2_CSS_MODE)}\n{F.V2_FOLD_WRAP_CSS}\n{I.V2_INSPECT_CARD_CSS}\n{cp.compact_css()}\n{TARGET_LAYOUT_CSS}</style>",
            unsafe_allow_html=True)
        st.session_state[F.SS_V2_CSS_DONE] = True    # 之後 page_find 的 `_render_one_v2` 不再重複吐
    except Exception as _e:  # noqa: BLE001 — 沒樣式卡片仍可讀；page_find 的 renderer 會自己再試一次
        print(f"[views/page_target] v2 樣式表產不出來（卡片仍照畫，只是沒有樣式）：{_e!r}")
        st.session_state[F.SS_V2_CSS_DONE] = False


# ══════════════════════════════════════════════════════════════════
# 「🔍 查看依據」六欄
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Basis:
    sources: str
    as_of: str
    rule: str
    missing: str
    confidence: str
    ai: str = AI_NOT_INVOLVED


def basis_rows(basis: Basis) -> list[tuple[str, str]]:
    _rows = []
    for _label, _attr in BASIS_FIELDS:
        _v = str(getattr(basis, _attr) or "").strip()
        if not _v:
            raise ValueError(f"查看依據「{_label}」不得留白（沒有就寫 ⬜ 與原因）")
        _rows.append((_label, _v))
    return _rows


def render_basis(basis: Basis, fresh_line: str | None = None) -> None:
    with st.expander(BASIS_EXPANDER_LABEL, expanded=False):
        st.markdown("\n".join(f"- **{_k}**：{scrub_secrets(_v)}" for _k, _v in basis_rows(basis)))
        if fresh_line:
            st.markdown(fresh_line)       # P5-3 A8：freshness 整句逐字（含「不會自動更新」「再按…重新載入」「可能已過期」）


# ══════════════════════════════════════════════════════════════════
# 單檔入口（搜尋框＋進階選項；同一個 form、一顆送出鈕）
# ══════════════════════════════════════════════════════════════════
def write_applied_ticker(session: Any, ticker: Any, *, kind_choice: Any = None) -> None:
    """**唯一**寫「已套用代碼」（單檔 gate 鍵 `_p03_applied_ticker`）的地方。

    呼叫者只有兩個（`tests/test_uit_target_page.py::TestGateWritePoints` 以 AST 白名單釘住）：
      ① 搜尋框 form 的送出分支（`handle_ticker_submit`）；
      ② 候選表「🔍 查看此檔」鈕的 on_click（`on_pick_click`）—— 使用者明確按下的動作，語意＝「使用者要求這一檔」。
    ⛔ 候選表列的選取／selectbox 變動本身**不**寫（只有按鈕才算要求）。
    """
    session[I.SS_APPLIED_TICKER] = {
        "ticker": ticker,
        "period_days": int(session.get(I.SS_PERIOD_WIDGET, I.DEFAULT_PERIOD_DAYS)),
        "mas": [_m for _m in I.MA_OPTIONS
                if session.get(f"{I.SS_MA_WIDGET_PREFIX}{_m}", _m in I.DEFAULT_MAS)],
        "kind_choice": (session.get(I.SS_KIND_WIDGET, I.KIND_CHOICE_AUTO) if kind_choice is None else kind_choice),
    }
    bump(session, SS_GEN_TICKER)


def handle_ticker_submit(session: Any) -> None:
    write_applied_ticker(session, session.get(I.SS_TICKER_WIDGET, ""))


def on_pick_click() -> None:
    """候選表「🔍 查看此檔」的 on_click（在 rerun 開頭、widget 實例化之前跑 ⇒ 可以同步搜尋框的顯示值）。"""
    _s = st.session_state
    _code = str(_s.get(SS_PICK_WIDGET) or "").strip()
    if not _code:
        return
    # 判型一律 auto：進階選項裡殘留的「強制當 ETF」是為上一個代碼設的，不得套到候選股身上（期間／均線沿用）。
    write_applied_ticker(_s, _code, kind_choice=I.KIND_CHOICE_AUTO)
    _s[I.SS_TICKER_WIDGET] = _code


def render_search_form(session: Any) -> None:
    with st.form(I.FORM_TICKER_KEY):
        st.text_input("代碼", key=I.SS_TICKER_WIDGET, placeholder=SEARCH_PLACEHOLDER,
                      label_visibility="collapsed")
        with st.expander(ADV_LABEL, expanded=False):
            st.selectbox("判型", list(I.KIND_CHOICE_LABELS),
                         format_func=lambda _k: I.KIND_CHOICE_LABELS[_k], key=I.SS_KIND_WIDGET)
            st.selectbox("期間（交易日）", I.PERIOD_OPTIONS,
                         index=I.PERIOD_OPTIONS.index(I.DEFAULT_PERIOD_DAYS), key=I.SS_PERIOD_WIDGET)
            st.caption(REAL_PRICE_NOTE)
            st.caption(PERIOD_NOTE)
            st.markdown(MA_GROUP_LABEL)
            st.caption(MA_ONLY_DISPLAY_NOTE)
            for _chunk, _columns in grid(I.MA_OPTIONS, MAX_COLS):
                for _ma, _col in zip(_chunk, _columns):
                    with _col:
                        st.checkbox(f"MA{_ma}", value=(_ma in I.DEFAULT_MAS),
                                    key=f"{I.SS_MA_WIDGET_PREFIX}{_ma}", help=MA_ONLY_DISPLAY_NOTE)
        _submitted = st.form_submit_button(I.ACTION_LOAD_INSPECT_LABEL, type="primary")
    if _submitted:
        handle_ticker_submit(session)


# ══════════════════════════════════════════════════════════════════
# 單檔載入（記住到使用者下一次要求）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class SingleBundle:
    """一次「單檔要求」的全部取數結果。未要求 ⇒ `req.submitted=False`，其餘皆 None（一行 L3 都沒呼叫）。"""

    req: Any
    verdict: Any
    stock: Any = None
    valuation: Any = None
    chips: Any = None
    profit: Any = None
    etf: Any = None
    errors: tuple[tuple[str, str], ...] = ()


def _try(errors: list, name: str, fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except Exception as _e:  # noqa: BLE001 — 轉成可見的紅字，不吞
        print(f"[views/page_target] 單檔取數 {name!r} 拋例外：{_e!r}")
        errors.append((name, repr(_e)))
        return None


def load_single(session: Any) -> SingleBundle:
    _req = own_inspect_request(session)
    if not _req.submitted:
        # 冷啟動：沒有人要求 ⇒ 連 loader 都不呼叫（比 loader 自己的 `requested=False` 早退更嚴）。
        return SingleBundle(req=_req, verdict=I.KindVerdict(requested=False))
    _errors: list[tuple[str, str]] = []
    _verdict = _try(_errors, "判型", lambda: I.classify_kind(_req))
    if _verdict is None:
        return SingleBundle(req=_req, verdict=I.KindVerdict(requested=_req.submitted, code=_req.ticker,
                                                            error=_errors[-1][1]),
                            errors=tuple(_errors))
    _stock = _val = _chips = _prof = _etf = None
    if _verdict.is_stock:
        _stock = _try(_errors, "健康度", lambda: I.load_stock_readout(_verdict))
        if _stock is not None:
            _val = _try(_errors, "357 估值", lambda: I.load_valuation(_verdict, _stock))
        _chips = _try(_errors, "籌碼", lambda: I.load_chips(_verdict, _req))
        _prof = _try(_errors, "獲利能力", lambda: I.load_profitability(_verdict))
    elif _verdict.is_etf:
        _etf = _try(_errors, "ETF", lambda: I.load_etf_readout(_verdict))
    return SingleBundle(req=_req, verdict=_verdict, stock=_stock, valuation=_val, chips=_chips, profit=_prof,
                        etf=_etf, errors=tuple(_errors))


def single_bundle(session: Any) -> SingleBundle:
    return memoized(session, "single", _gen(session, SS_GEN_TICKER, I.SS_APPLIED_TICKER),
                    lambda: load_single(session))


# ══════════════════════════════════════════════════════════════════
# 第一區：產業 × 維度矩陣
# ══════════════════════════════════════════════════════════════════
#: 象限排序（A 規格 §4.2.1：排序只能依既有法人資金動能象限）。其餘（含「未取得」）排最後，同組內依產業名。
QUADRANT_ORDER: tuple[str, ...] = (QUADRANT_RISING, QUADRANT_ROTATING, QUADRANT_EBBING,
                                   QUADRANT_WATCHING, QUADRANT_INSUFFICIENT)


@dataclass(frozen=True)
class MatrixRow:
    sector: str
    fundamentals: str
    strength: str
    flow: str
    valuation: str
    trust: str

    def as_record(self) -> dict[str, str]:
        return dict(zip(MATRIX_COLS, (self.sector, self.fundamentals, self.strength, self.flow,
                                      self.valuation, self.trust), strict=True))


def _quadrant_rank(q: str) -> int:
    return QUADRANT_ORDER.index(q) if q in QUADRANT_ORDER else len(QUADRANT_ORDER)


def build_industry_matrix(sectors: Sequence[Any]) -> tuple[MatrixRow, ...]:
    """板塊資金資料 → 產業×維度矩陣。**只有「法人／籌碼」有資料**，其餘維度整欄 ⬜；缺值一律 ⬜，⛔ 不填 0。

    沒有「變強／轉弱」字樣（只轉述 L2 既有象限名）；不合成任何分數；「資料可信度」只列各旗標原值。
    """
    _rows: list[tuple[int, str, MatrixRow]] = []
    for _s in sectors or ():
        if not isinstance(_s, Mapping):
            continue
        _name = str(_s.get("sector") or "").strip() or "（未命名）"
        _unavail = _s.get("unavailable") is True
        _quad = str(_s.get("quadrant") or "").strip()
        _x = None if _unavail else _fmt_f(_s.get("x_yi"))
        if _unavail:
            _flow = FLOW_MISSING
        elif _x is None:
            _flow = (f"{_quad}｜" if _quad else "") + "⬜ 淨流入資料不足（不補 0）"
        else:
            _flow = (f"{_quad}｜" if _quad else "") + f"近 {WINDOW_X} 日累計淨流入 {_x} 億"
        _flags = []
        if _s.get("insufficient"):
            _flags.append("交易日不足")
        if _unavail:
            _flags.append("窗口內有缺值")
        _nd = _s.get("n_days")
        if _nd not in (None, ""):
            _flags.append(f"交易日 {_nd}")
        _trust = "旗標：" + ("、".join(_flags) if _flags else "—")
        _rows.append((_quadrant_rank(_quad), _name,
                      MatrixRow(sector=_name, fundamentals=NOT_BUILT, strength=STRENGTH_ONLY_FLOW,
                                flow=_flow, valuation=NOT_BUILT, trust=_trust)))
    _rows.sort(key=lambda _t: (_t[0], _t[1]))
    return tuple(_r for _, _, _r in _rows)


#: F1：同一份 HTML 表格，窄螢幕（≤768px）以 CSS 變成「每產業一張卡片列」（每格前面帶欄名），桌機維持表格。
#: 單一 DOM（不是畫兩份）；樣式只掛在 `.ptg-mx` 底下，不影響其他頁。
MATRIX_CSS: str = (
    ".ptg-mx-t{width:100%;border-collapse:collapse;font-size:.9rem}"
    ".ptg-mx-t th,.ptg-mx-t td{border-bottom:1px solid rgba(128,128,128,.35);padding:.35rem .5rem;"
    "text-align:left;vertical-align:top;overflow-wrap:anywhere}"
    "@media (max-width:768px){"
    ".ptg-mx-t thead{display:none}"
    ".ptg-mx-t,.ptg-mx-t tbody,.ptg-mx-t tr,.ptg-mx-t td{display:block;width:100%;box-sizing:border-box}"
    ".ptg-mx-t tr{border:1px solid rgba(128,128,128,.45);border-radius:8px;margin:.5rem 0;padding:.3rem .6rem}"
    ".ptg-mx-t td{border:0;padding:.15rem 0}"
    ".ptg-mx-t td::before{content:attr(data-label) \"：\";font-weight:600}}")


def matrix_html(rows: Sequence[MatrixRow]) -> str:
    """矩陣 → 單行 HTML（無空白行，免得 CommonMark 在中間截斷）。所有格子先 escape。"""
    _e = lambda t: _html.escape(str(t), quote=True)   # noqa: E731
    _head = "".join(f"<th>{_e(c)}</th>" for c in MATRIX_COLS)
    _body = "".join(
        "<tr>" + "".join(f'<td data-label="{_e(c)}">{_e(v)}</td>'
                         for c, v in zip(MATRIX_COLS, (r.sector, r.fundamentals, r.strength, r.flow,
                                                       r.valuation, r.trust), strict=True)) + "</tr>"
        for r in rows)
    return f'<style>{MATRIX_CSS}</style><div class="ptg-mx"><table class="ptg-mx-t"><thead><tr>{_head}</tr></thead><tbody>{_body}</tbody></table></div>'


@dataclass(frozen=True)
class MapBundle:
    flow: Any
    heatmap: Any


def map_bundle(session: Any) -> MapBundle:
    def _compute() -> MapBundle:
        # loader 自己會把例外轉成 `error=`；這裡再包一層是為了「意外的例外」也被記住（失敗結果只呈現、不在 rerun 重打）。
        with st.spinner("載入板塊資料…"):
            try:
                _hm = F.load_heatmap(requested=True)
            except Exception as _e:  # noqa: BLE001 — 轉成紅態，不吞
                print(f"[views/page_target] 熱力圖 loader 拋例外：{_e!r}")
                _hm = F.HeatmapReadout(requested=True, error=repr(_e))
            try:
                _flow = F.load_sector_flow(session, requested=True)
            except Exception as _e:  # noqa: BLE001
                print(f"[views/page_target] 板塊資金 loader 拋例外：{_e!r}")
                _flow = F.SectorFlowReadout(requested=True, error=repr(_e))
        return MapBundle(flow=_flow, heatmap=_hm)
    return memoized(session, "map", (int(session.get(SS_GEN_MAP, 0) or 0), True), _compute)


def sanitize_facts(facts: Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    """熱力圖卡的「切換市場或區間」那一列原文指向舊分頁（🌍 市場環境），預設模式到不了 ⇒ 換成不指路的白話。"""
    _out = []
    for _k, _v in facts:
        _out.append((_k, HEATMAP_SWITCH_PLAIN) if _k == "切換市場或區間" else (_k, _v))
    return tuple(_out)


def _render_figure(draw: Callable[[], None], label: str) -> None:
    try:
        draw()
    except Exception as _e:  # noqa: BLE001 — 轉成看得見的紅字，不吞
        print(f"[views/page_target] {label}繪製失敗：{_e!r}")
        st.error(f"🔴 {label}畫不出來（資料讀到了，是繪圖層的問題）：{_md_safe(repr(_e)) or F.UNKNOWN_ERROR_TEXT}",
                 icon="🔴")


# ── P5-1 Primary：產業 Top 5 橫條（DEC-121 Q1=A）──────────────────────────────
@dataclass(frozen=True)
class RankRow:
    """Top 5 橫條的一列。`x_yi is None` ＝ 缺值（窗口內缺值／欄位缺／非有限數）：不補 0、不當最強或最弱。"""

    sector: str
    quadrant: str
    x_yi: float | None

    @property
    def missing(self) -> bool:
        return self.x_yi is None


def _finite(value: Any) -> float | None:
    """數字 → float；缺值／NaN／inf／bool／非數字 → None（⛔ 不寫 0）。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        _v = float(value)
    except (TypeError, ValueError):
        return None
    return _v if math.isfinite(_v) else None


def rank_industries(sectors: Sequence[Any]) -> tuple[RankRow, ...]:
    """板塊資金資料 → 產業顯示排序（DEC-121 Q1=A）：`x_yi`（近 N 日法人累計淨流入）**由大到小**；
    缺值列（`unavailable`／`x_yi` 缺或非有限）一律排最後。同值／同為缺值者依產業名稱（僅為讓畫面穩定的決定性次序）。
    ⛔ 純顯示排序：不改輸入、不補值、不增刪列；候選池／個股排序／Risk Cap／趨勢定義都不經過這裡。
    """
    _valued: list[RankRow] = []
    _missing: list[RankRow] = []
    for _s in sectors or ():
        if not isinstance(_s, Mapping):
            continue
        _name = str(_s.get("sector") or "").strip() or "（未命名）"
        _quad = str(_s.get("quadrant") or "").strip()
        _x = None if _s.get("unavailable") is True else _finite(_s.get(ZONE1_RANK_FIELD))
        (_missing if _x is None else _valued).append(RankRow(sector=_name, quadrant=_quad, x_yi=_x))
    _valued.sort(key=lambda _r: (-_r.x_yi, _r.sector))    # type: ignore[operator]  # _valued 的 x_yi 皆非 None
    _missing.sort(key=lambda _r: _r.sector)
    return tuple(_valued + _missing)


def rank_row_label(index: int, row: RankRow) -> str:
    """橫條的列標：名次、產業、象限名、數值全是文字 ⇒ 顏色不是唯一資訊；缺值寫 ⬜，不寫數字。"""
    _quad = row.quadrant or "—"
    _val = ZONE1_ROW_MISSING if row.x_yi is None else f"{row.x_yi:.1f} 億"
    return f"{index}. {row.sector}｜{_quad}｜{_val}"


def rank_chart_frame(rows: Sequence[RankRow]) -> pd.DataFrame:
    """橫條圖的資料：缺值列的 `x_yi` 是空值（NaN）⇒ 圖上不畫條（⛔ 不是 0）。"""
    return pd.DataFrame({
        "row": [rank_row_label(_i, _r) for _i, _r in enumerate(rows, start=1)],
        "x_yi": pd.Series([_r.x_yi for _r in rows], dtype="float64"),
    })


def rank_chart_spec(row_labels: Sequence[str], *, height: int = ZONE1_CHART_HEIGHT_PX) -> dict[str, Any]:
    """橫條 Vega-Lite spec：列順序＝資料順序（`scale.domain` 明列、`sort: null`，⛔ 由圖自己重排）；x 軸有刻度；
    條色單一（正負看位置與列標文字）。⚠️ `scale.domain` 必須明列：x 空值（缺值列）會被 Vega-Lite 當無效值濾掉，
    不明列的話該列連列標都消失（缺值列「⬜ 資料不足」就被藏起來了）。
    `labelOverlap: False`：窄螢幕列距小時 Vega 會自動隱藏「疑似重疊」的列標（實測手機 5 列時第 2、4 列列標被吃掉 ⇒ 名次、
    象限名、數值全看不到）；列標就是這張圖的文字資訊，一列都不能被自動藏起來。"""
    return {
        "height": height,
        "autosize": {"type": "fit", "contains": "padding"},
        "mark": {"type": "bar", "color": "#2563eb"},
        "encoding": {
            "y": {"field": "row", "type": "ordinal", "sort": None, "title": "",
                  "scale": {"domain": list(row_labels)},
                  "axis": {"labelLimit": 220, "labelFontSize": 11, "labelOverlap": False,
                           "ticks": False, "domain": False}},
            "x": {"field": ZONE1_RANK_FIELD, "type": "quantitative", "title": "",
                  "axis": {"grid": True, "labelFontSize": 10, "tickCount": 4}},
            "tooltip": [{"field": "row", "type": "nominal", "title": "產業"},
                        {"field": ZONE1_RANK_FIELD, "type": "quantitative", "title": "近 5 日累計淨流入（億）",
                         "format": ",.1f"}],
        },
    }


def render_industry_chart(frame: pd.DataFrame) -> None:
    st.vega_lite_chart(frame, rank_chart_spec(list(frame["row"])), width="stretch", height=ZONE1_CHART_HEIGHT_PX)


@dataclass(frozen=True)
class ChartFold:
    """圖表摺疊的四段內容（每段 ≥1 行；空段 ⇒ `ValueError`：不適用必須寫「—」並說明，⛔ 留白）。"""

    why: tuple[str, ...]
    source: tuple[str, ...]
    limit: tuple[str, ...]
    where: tuple[str, ...]

    def sections(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        _out = tuple(zip(FOLD_SECTIONS, (self.why, self.source, self.limit, self.where), strict=True))
        for _name, _lines in _out:
            if not _lines or not all(str(_t).strip() for _t in _lines):
                raise ValueError(f"圖表摺疊「{_name}」不得留白（不適用寫「—」並說明）")
        return _out


def chart_fold(basis: Basis, *, limit: Sequence[str] = (), where: Sequence[str] = ()) -> ChartFold:
    """六欄 Basis 依 `BASIS_TO_FOLD` 分到四段（「- **欄名**：內容」、逐字、洗秘密），再接各段額外行。
    資訊守恆：原「🔍 查看依據」的每一欄都落在某一段，一字不改。"""
    _rows = dict(zip((_a for _, _a in BASIS_FIELDS), basis_rows(basis), strict=True))
    _sec: dict[str, tuple[str, ...]] = {}
    for _name in FOLD_SECTIONS:
        _attrs = [_a for _a in BASIS_TO_FOLD[_name] if _a in _rows]
        _md = "\n".join(f"- **{_rows[_a][0]}**：{scrub_secrets(_rows[_a][1])}" for _a in _attrs)
        _sec[_name] = ((_md,) if _md else ())
    return ChartFold(why=_sec["為什麼"], source=_sec["來源"],
                     limit=_sec["限制"] + tuple(limit), where=tuple(where))


def render_chart_fold(fold: ChartFold) -> None:
    """Primary 圖下方**恰一個**摺疊（預設收合）：四段依序「**段名**」＋內容。"""
    _sections = fold.sections()          # 先驗（留白就紅），再畫
    with st.expander(FOLD_LABEL, expanded=False):
        for _name, _lines in _sections:
            st.markdown(f"**{_name}**")
            for _text in _lines:
                st.markdown(_text)


def _asof_chip(observation_date: Any) -> Any:
    """資料日 chip（`MM/DD`）；吃 L1 可信**觀測日**（D1，DEC-148；~~原吃 `updated_at`＝cron 執行日~~ 有意識的修改，⛔ 不是漏刪）。
    不是 `YYYY-MM-DD…` ⇒ `⬜ 資料日未提供`（⛔ 猜一個日期、⛔ 以執行時間頂替）。"""
    _s = str(observation_date or "").strip()[:10]
    try:
        _d = datetime.strptime(_s, "%Y-%m-%d").date()
    except ValueError:
        return cp.meta_chip("asof_missing")
    return cp.meta_chip("asof", f"{_d:%m/%d}")


def industry_chips(flow: Any, rows: Sequence[RankRow], *, fetched_at: datetime | None, aged: bool) -> list[Any]:
    """Primary header 的 chip：資料日、抓取時間、窗口、（過期才有）過期、（有缺值才有）覆蓋。每個事實外露層最多一次。"""
    _chips: list[Any] = [_asof_chip(getattr(flow, "observation_date", ""))]
    if fetched_at is not None:
        _chips.append(cp.meta_chip("retrieved_at", fetched_at.astimezone(TAIPEI).strftime("%H:%M")))
    _chips.append(cp.meta_chip("window", f"近 {WINDOW_X} 日"))
    _n_ok = sum(1 for _r in rows if not _r.missing)
    if getattr(flow, "stale", False) or aged:
        # 狀態類 chip 同列互斥（契約 §6）：過期優先外露；覆蓋數仍在摺疊「限制」逐字可查（`industry_fold`）。
        _chips.append(cp.meta_chip("stale"))
    elif rows and _n_ok < len(rows):
        _chips.append(cp.meta_chip("coverage", f"{_n_ok}／{len(rows)} 項有資料"))
    return _chips


def industry_fold(flow: Any, *, fresh_line: str | None, n_total: int, n_ok: int | None = None) -> ChartFold:
    """Primary 摺疊：六欄依據分四段；整句 freshness、資料範圍／過期說明、清單指路都在這（只下沉）。"""
    _limit: list[str] = []
    if flow is not None and getattr(flow, "requested", False) and getattr(flow, "ok", False):
        if getattr(flow, "stale", False):
            _limit.append("⚠️ " + _stale_caption(flow))
        if getattr(flow, "tpex_complete", None) is not True:
            _limit.append(SECTOR_FLOW_TWSE_ONLY_NOTE)
        if n_ok is not None and n_total and n_ok < n_total:
            _limit.append(f"有資料的產業：{n_ok}／{n_total}（其餘為窗口內缺值或交易日不足，名單見「查看全部」）")
    if fresh_line:
        _limit.append(fresh_line)
    if flow is None or not getattr(flow, "requested", False):
        _where = [ZONE1_IDLE]
    elif not getattr(flow, "ok", False):
        _where = [f"請再按「{RELOAD_LABEL['map']}」重新載入；快取要等盤後凍結任務產生。"]
    else:
        _where = [ZONE1_FOLD_WHERE_FMT.format(label=ZONE1_ALL_LABEL_FMT.format(n=n_total))]
    return chart_fold(basis_industry(flow), limit=_limit, where=_where)


def _stale_caption(flow: Any) -> str:
    return ("資料過期（載入當下判定）：畫的是最後一次成功凍結的快照"
            + (f"（{_md_safe(flow.stale_reason)}）" if flow.stale_reason else "") + "。")


def render_all_industries(flow: Any, matrix: Sequence[MatrixRow]) -> None:
    """「▸ 查看全部（N 個產業）」：原 6 欄表逐列（維持象限→名稱的原順序）、過期註、TWSE-only 註、未取得名單 —— 只下沉、不刪。"""
    with st.expander(ZONE1_ALL_LABEL_FMT.format(n=len(matrix)), expanded=False):
        if matrix:
            st.markdown(matrix_html(matrix), unsafe_allow_html=True)
        if flow.stale:
            st.caption("⚠️ " + _stale_caption(flow))
        if flow.tpex_complete is not True:
            st.caption(SECTOR_FLOW_TWSE_ONLY_NOTE)
        _unav = format_unavailable_caption(flow.sectors)
        if _unav:
            st.caption(_unav)


def render_zone_industry(session: Any) -> None:
    section_header(ZONE1_TITLE, ZONE1_SAY)
    st.caption(ZONE1_SORT_NOTE)
    # 板塊地圖的**唯一** gate 寫入點（單顆 st.button，不在 form 內）。
    if st.button(F.ACTION_LOAD_MAP_LABEL, key=F.SS_MAP_BUTTON, type="primary"):
        session[F.SS_MAP_REQUESTED] = True
        bump(session, SS_GEN_MAP)
    if not own_map_requested(session):
        # 冷啟動零取數：Primary 槽放同高的灰色 placeholder（⬜ 尚未載入；不是空白、不是假圖、不是紅）。
        st.markdown(cp.chart_slot_missing_html(UI_IDLE, ZONE1_IDLE_REASON, height_px=ZONE1_CHART_HEIGHT_PX),
                    unsafe_allow_html=True)
        render_chart_fold(industry_fold(None, fresh_line=None, n_total=0))
        return
    _mb = map_bundle(session)
    _flow, _hm = _mb.flow, _mb.heatmap
    _fresh = freshness_text(session, "map")
    if not _flow.ok:
        # 快取還沒產生（灰）／取數失敗（紅）：狀態卡放在區塊外面，不收進展開區。
        _card, _facts = F.build_sector_flow_card(_flow)
        F._render_one(_card, _facts)
        render_chart_fold(industry_fold(_flow, fresh_line=_fresh, n_total=0))
    else:
        _matrix = build_industry_matrix(_flow.sectors)
        _ranked = rank_industries(_flow.sectors)
        _top = cp.topn_view(_ranked, ZONE1_TOP_N)
        _at = memo_loaded_at(session, "map")
        _aged = _at is not None and is_aged(_at, now_taipei(), FRESH_TTL_SEC["map"])
        _hdr, _overflow = cp.chart_header_html(
            title=ZONE1_TITLE_FMT.format(n=len(_top.shown) or ZONE1_TOP_N, w=WINDOW_X),
            chips=industry_chips(_flow, _ranked, fetched_at=_at, aged=_aged), say=None, title_verbatim=True)
        st.markdown(_hdr, unsafe_allow_html=True)
        if _top.empty:
            st.markdown(cp.chart_slot_missing_html(UI_EMPTY, "板塊資料沒有任何產業列", height_px=ZONE1_CHART_HEIGHT_PX),
                        unsafe_allow_html=True)
        else:
            _render_figure(lambda: render_industry_chart(rank_chart_frame(_top.shown)), "產業橫條圖")
            st.caption(ZONE1_MISSING_DIMS)
        _fold = industry_fold(_flow, fresh_line=_fresh, n_total=len(_ranked),
                          n_ok=sum(1 for _r in _ranked if not _r.missing))
        if _overflow:
            _fold = ChartFold(why=_fold.why, source=_fold.source + tuple(_c.text for _c in _overflow),
                              limit=_fold.limit, where=_fold.where)
        render_chart_fold(_fold)
        render_all_industries(_flow, _matrix)
    # 熱力圖／泡泡圖降為展開區；有狀態異常（紅／橘）時預設展開，避免把問題藏在收合裡。
    _hm_card, _hm_facts = F.build_heatmap_card(_hm)
    with st.expander(HEATMAP_EXPANDER, expanded=(_hm_card.state != UI_LIVE)):
        F._render_one(_hm_card, sanitize_facts(_hm_facts))
        if _hm.figure is not None:
            _render_figure(lambda: st.plotly_chart(_hm.figure, width="stretch"), "熱力圖")
    if _flow.ok:
        _fl_card, _fl_facts = F.build_sector_flow_card(_flow)
        with st.expander(BUBBLE_EXPANDER, expanded=(_fl_card.state != UI_LIVE)):
            F._render_one(_fl_card, _fl_facts)
            if _flow.sectors:
                def _bubble() -> None:
                    from src.ui.render.sector_flow_render import build_sector_flow_figure
                    st.plotly_chart(build_sector_flow_figure(list(_flow.sectors),
                                                             highlight_sectors=set(_flow.highlight)),
                                    width="stretch")
                _render_figure(_bubble, "泡泡圖")
                for _chunk, _columns in grid(_flow.quadrant_counts, MAX_COLS):
                    for (_q, _n), _col in zip(_chunk, _columns):
                        with _col:
                            st.markdown(f"**{_q}**　{_n} 個板塊")
            st.caption(F.SECTOR_FLOW_AXIS_NOTE)


def basis_industry(flow: Any) -> Basis:
    if flow is None or not getattr(flow, "requested", False):
        return Basis(
            sources="三大法人資金流快取（板塊資金潮汐）；產業分類用官方產業別。尚未載入。",
            as_of="尚未載入",
            rule=f"尚未載入；載入後以近 N 日累計淨流入與動能變化分象限，不做綜合強弱分數。{ZONE1_NO_TREND_NOTE}",
            missing="基本面成長、相對強弱（價格）、估值：尚未建置；其餘待載入後列出。",
            confidence="尚未載入")
    if not flow.ok:
        return Basis(
            sources="三大法人資金流快取（板塊資金潮汐）", as_of="⬜ 未提供（沒有可用的快取）",
            rule="（無資料可套用）", missing=f"整份板塊資金資料：{_md_safe(flow.reason or flow.error or '尚未產生')}",
            confidence="⬜ 無法判定")
    _tp = "是" if flow.tpex_complete is True else ("否（僅含上市）" if flow.tpex_complete is False else "⬜ 未提供（僅含上市）")
    return Basis(
        sources="三大法人資金流快取（板塊資金潮汐）；產業分類用官方產業別",
        as_of=(flow.observation_date or "⬜ 未提供（資料日未知）"),   # D1：資料日只取可信觀測日（~~flow.updated_at＝執行時間~~）
        rule=(f"近 {WINDOW_X} 個交易日累計淨流入與動能變化 → 漲潮／輪動／退潮／觀望；"
              f"交易日不足者標「資料不足」。本表不做綜合強弱分數。{ZONE1_NO_TREND_NOTE}"),
        missing=("基本面成長、相對強弱（價格）、估值：尚未建置"
                 + (f"；窗口內缺值的板塊：{'、'.join(flow.unavailable)}" if flow.unavailable else "")),
        confidence=(f"上櫃資料完整：{_tp}；資料過期：{'是' if flow.stale else '否'}；"
                    f"使用交易日數：{flow.n_days or '⬜ 未提供'}"))


# ══════════════════════════════════════════════════════════════════
# 第二區：選股條件＋候選標的表
# ══════════════════════════════════════════════════════════════════
def render_screen_form(session: Any) -> None:
    """選股條件 form：一個 form、一顆送出鈕、form 內無 button；widget 當下值與已套用值分家（同 page_find）。"""
    _labels, _labels_err = F.load_factor_labels()
    if _labels is None:
        F._render_one(F.build_form_unavailable_card(_labels_err))
        return
    _all = list(_labels)
    _default = [_l for _l in _all if _labels[_l] == F.DEFAULT_FACTOR_KEY]
    if not _default:
        st.warning(f"⚠️ 預設因子 `{F.DEFAULT_FACTOR_KEY}` 不在選股因子清單裡 —— 本次表單**不預選任何因子**，"
                   "請自行勾選；請把這行訊息回報給維護者。", icon="⚠️")
    with st.form(F.FORM_KEY):
        for _chunk, _columns in grid(("①", "②", "③"), MAX_COLS):
            for _slot, _col in zip(_chunk, _columns):
                with _col:
                    if _slot == "①":
                        st.markdown("**① 基本面優選**")
                        st.caption(
                            f"{PRESCREEN_REQUIRED_PASSES} 項全過（自動，不需勾選）："
                            f"負債比<{DEBT_RATIO_MAX * 100:g}% · 三率三升 YoY · 淨流動值>0 · EPS>{EPS_MIN:g}。"
                            "四項全過才入選股網候選池。")
                    elif _slot == "②":
                        st.markdown("**② 勾條件**")
                        st.multiselect("要用哪些條件？（可複選）", _all, default=_default,
                                       key=F.SS_FACTORS_WIDGET, label_visibility="collapsed")
                    else:
                        st.markdown("**③ 排序與筆數**")
                        st.caption("排序：綜合評分（各因子百分位平均）")
                        st.selectbox("顯示筆數", F.TOP_N_OPTIONS, index=F.TOP_N_OPTIONS.index(F.DEFAULT_TOP_N),
                                     key=F.SS_TOPN_WIDGET, label_visibility="collapsed")
        _submitted = st.form_submit_button(F.ACTION_RUN_SCREEN_LABEL, type="primary")
    if _submitted:
        # 唯一的寫入點：widget 當下值 → 已套用值（選股結果的 `requested=` gate）。
        _picked = session.get(F.SS_FACTORS_WIDGET) or []
        session[F.SS_APPLIED_SCREEN] = {
            "factors": [_labels[_l] for _l in _picked if _l in _labels],
            "top_n": int(session.get(F.SS_TOPN_WIDGET, F.DEFAULT_TOP_N)),
        }
        bump(session, SS_GEN_SCREEN)


@dataclass(frozen=True)
class ScreenBundle:
    req: Any
    result: Any
    sector: Any = None          # TickerSectorMap | None
    sector_error: str = ""
    pe_map: Mapping | None = None
    pe_failed: bool = False
    #: 第二次讀本益比時 L1 回報「本輪沒給出任何有效本益比」的市場（`'上市 TWSE'`／`'上櫃 TPEX'`）。
    pe_failed_markets: tuple[str, ...] = ()


def _load_screen_bundle(req: Any) -> ScreenBundle:
    if not req.submitted:
        # 冷啟動：沒有人要求 ⇒ 連 loader 都不呼叫。
        return ScreenBundle(req=req, result=F.ScreenResult(requested=False))
    try:
        _result = F.load_screen_result(req)
    except Exception as _e:  # noqa: BLE001 — loader 自己會轉 error=；意外的例外也要被記住（不在 rerun 重打）
        print(f"[views/page_target] 選股 loader 拋例外：{_e!r}")
        _result = F.ScreenResult(requested=True, error=repr(_e))
    if not _result.requested or not _result.has_rows:
        return ScreenBundle(req=req, result=_result)
    _sector = None
    _sec_err = ""
    try:
        from src.services.target_industry_service import get_ticker_sector_map
        _sector = get_ticker_sector_map()
    except Exception as _e:  # noqa: BLE001 — 產業欄轉 ⬜，不吞也不拖垮候選表
        print(f"[views/page_target] 產業對映讀取失敗：{_e!r}")
        _sec_err = repr(_e)
    # 估值欄要的是「當日本益比」本身；ranked df 只有百分位分，本益比的值要再讀一次同一支 L3（L1 成功結果有快取）。
    # 選股那一輪確定沒拿到本益比（pe_n 為 None／0）⇒ 不再重打（失敗不被轟炸）。
    _pe_map = None
    _pe_failed = True
    _pe_fm: tuple[str, ...] = ()
    if _result.pe_n:
        try:
            _m, _n, _err, _fm = F._load_pe_name_maps()
        except Exception as _e:  # noqa: BLE001 — 估值欄轉 ⬜，不拖垮候選表
            print(f"[views/page_target] 本益比再讀失敗：{_e!r}")
            _m, _err, _fm = None, repr(_e), ()
        if _m is not None and not _err:
            _pe_map, _pe_failed, _pe_fm = _m, False, tuple(_fm or ())
    return ScreenBundle(req=req, result=_result, sector=_sector, sector_error=_sec_err,
                        pe_map=_pe_map, pe_failed=_pe_failed, pe_failed_markets=_pe_fm)


def screen_bundle(session: Any) -> ScreenBundle:
    _req = own_screen_request(session)
    return memoized(session, "screen", _gen(session, SS_GEN_SCREEN, F.SS_APPLIED_SCREEN),
                    lambda: _load_screen_bundle(_req))


def peek_screen_bundle(session: Any) -> ScreenBundle | None:
    """只讀：第二區已記住的選股結果（同世代才算）；沒有就 None。⛔ 不取數、不觸發選股。"""
    _cur = session.get(f"{SS_MEMO_PREFIX}screen")
    if (isinstance(_cur, tuple) and len(_cur) == _MEMO_LEN
            and _cur[0] == _gen(session, SS_GEN_SCREEN, F.SS_APPLIED_SCREEN)
            and isinstance(_cur[1], ScreenBundle)):
        return _cur[1]
    return None


def _code_of(row: Mapping) -> str:
    return str(row.get("代碼") or "").strip()


def chips_cell(code: str, single: SingleBundle | None) -> str:
    """候選表「籌碼」格：**只有使用者選取（已載入）的那一檔**有值；其餘「未取」（⛔ 不填 0、不推定中性）。"""
    if single is None or not single.req.submitted:
        return CHIPS_NOT_FETCHED
    if single.verdict is None or not single.verdict.is_stock or single.req.ticker != code:
        return CHIPS_NOT_FETCHED
    if single.chips is None:
        # 選取的是這一檔、判型個股、本輪已嘗試取數，但沒有結果物件 ⇒ 取數拋了例外（`load_single._try`）：是「失敗」，不是「還沒取」。
        return "⬜ 取數失敗"
    _c = single.chips
    if _c.error:
        return "⬜ 取數失敗"
    if _c.has_verdict:
        _conc = _fmt_f(_c.concentration, 2)
        return f"{I._signal_label(_c.signal)}" + (f"（集中度 {_conc}%）" if _conc is not None else "")
    return "⬜ 資料不足"


def build_candidate_rows(bundle: ScreenBundle, single: SingleBundle | None) -> list[dict[str, str]]:
    """ranked df → 候選表紀錄（標的｜產業｜基本面｜估值｜籌碼｜狀態）。零新算法：全部轉述既有欄位。"""
    _df = bundle.result.df
    if _df is None or getattr(_df, "empty", True):
        return []
    _out: list[dict[str, str]] = []
    _sec_map = bundle.sector.mapping if (bundle.sector is not None and bundle.sector.available) else None
    for _row in _df.to_dict("records"):
        _code = _code_of(_row)
        _name = str(_row.get("名稱") or "").strip()
        # 產業
        if bundle.sector is None or not bundle.sector.available:
            # 讀取拋例外（含 strict 的壞檔）≠ 快取尚未產生：兩句話不同。
            _ind = SECTOR_READ_FAILED_CELL if bundle.sector_error else SECTOR_UNAVAILABLE_CELL
        else:
            _raw = _sec_map.get(_code)
            _lab = canonical_sector(_raw) if _raw not in (None, "") else ""
            _ind = _lab if _lab and _lab != SECTOR_UNCLASSIFIED else "⬜ 未分類"
        # 基本面（通過初篩＋綜合分）
        _score = _fmt_f(_row.get("綜合分"))
        _base = f"{STATUS_PASSED}・綜合分 {_score}" if _score is not None else MISSING_CELL
        # 估值（當日本益比；≤0 L1 已不放 key）
        if bundle.pe_failed or bundle.pe_map is None:
            _pe = PE_FAILED_CELL
        else:
            _pv = _fmt_f(bundle.pe_map.get(_code), 1)
            # 某個市場本輪整個沒給本益比 ⇒ 缺的代碼可能就是那個市場的 ⇒ 寫「取不到」，不寫「未提供」（兩者不是一件事）。
            _pe = _pv if _pv is not None else (PE_FAILED_CELL if bundle.pe_failed_markets else PE_NOT_PROVIDED_CELL)
        _out.append({
            "標的": f"{_code} {_name}".strip(),
            "產業": _ind,
            "基本面": _base,
            "估值": _pe,
            "籌碼": chips_cell(_code, single),
            "狀態": STATUS_PASSED if _score is not None else STATUS_INSUFFICIENT,
        })
    return _out


def pick_options(bundle: ScreenBundle) -> list[str]:
    _df = bundle.result.df
    if _df is None or getattr(_df, "empty", True):
        return []
    return [_code_of(_r) for _r in _df.to_dict("records") if _code_of(_r)]


def screen_summary(labels: Mapping[str, str] | None, req: Any) -> str | None:
    """「選股條件」收合時外露的一行摘要（DEC-121 Q2=B）。**只轉述**已套用條件（尚未送出 ⇒ 轉述預設條件）：
    因子名稱走 L3 的 label SSOT 反查；排序固定「綜合評分」（與 form ③ 同一句）；筆數＝已套用／預設。
    ⛔ 不新增條件、不推測；label 清單讀不到、或已套用 key 不在清單內 ⇒ None（form 會自己畫紅卡，摘要不編）。"""
    if labels is None:
        return None
    if getattr(req, "submitted", False):
        _keys = tuple(getattr(req, "factors", ()) or ())
        _top = int(getattr(req, "top_n", F.DEFAULT_TOP_N))
    else:
        _keys = (F.DEFAULT_FACTOR_KEY,) if F.DEFAULT_FACTOR_KEY in labels.values() else ()
        _top = F.DEFAULT_TOP_N
    _by_key = {_k: _l for _l, _k in labels.items()}
    if any(_k not in _by_key for _k in _keys):
        return None          # 已套用的 key 不在 label SSOT 裡：不外露原始 key、不猜名稱 ⇒ 整句不畫摘要
    _names = [_by_key[_k] for _k in _keys]
    _fac = ("＋" + "、".join(_names)) if _names else ""
    return SCREEN_SUMMARY_FMT.format(n=PRESCREEN_REQUIRED_PASSES, factors=_fac, top=_top)


def candidate_csv_bytes(df: Any) -> bytes:
    """💾 CSV 內容＝L3 排名原表**全量**（⛔ 受 Top 10 切片影響；與舊選股網相同）。"""
    return df.to_csv(index=False).encode("utf-8-sig")


def render_chip_row(chips: Sequence[Any]) -> None:
    _html, _ = cp.chips_html(list(chips))
    if _html:
        st.markdown(_html, unsafe_allow_html=True)


def render_candidate_notes() -> None:
    """估值口徑全文／籌碼未取／金融股 —— 逐字（只下沉、不刪）。"""
    with st.expander(CANDIDATE_NOTES_EXPANDER, expanded=False):
        st.caption(PE_COL_NOTE)
        st.caption(PICK_NOTE)
        st.caption(CHIPS_COL_HINT)
        st.caption(FIN_STOCK_NOTE)


def render_zone_candidates(session: Any) -> None:
    section_header(ZONE2_TITLE, ZONE2_SAY)
    # 摘要版位在 expander 上方，但內容要等 form 跑完才填：送出鈕的 handler 在 form 內才把「已套用條件」寫進 session，
    # 先算會慢一拍（顯示上一輪的條件）。
    _summary_slot = st.empty()
    with st.expander(SCREEN_EXPANDER, expanded=SCREEN_EXPANDER_EXPANDED):
        render_screen_form(session)
    _labels, _ = F.load_factor_labels()
    _summary = screen_summary(_labels, own_screen_request(session))
    if _summary:
        _summary_slot.caption(_summary)
    _sb = screen_bundle(session)
    _card, _facts = F.build_screen_result_card(_sb.result, _sb.req)
    F._render_one(_card, _facts)
    if _card.state != UI_LIVE:
        render_chip_row(freshness_chips(session, "screen"))
        render_basis(basis_candidates(_sb), freshness_text(session, "screen"))
        return
    st.caption("本次因子：" + (" · ".join(_sb.result.hits) if _sb.result.hits else "僅基本面四項全過"))
    _single = single_bundle(session) if own_inspect_request(session).submitted else None
    _records = build_candidate_rows(_sb, _single)
    _top = cp.topn_view(_records, CANDIDATE_TOP_N)       # 純顯示切片：保序、不重算
    if _top.empty:
        st.caption(MISSING_CELL)
    else:
        st.dataframe(list(_top.shown), hide_index=True, width="stretch")
    if _top.hidden > 0:
        render_chip_row([_top.more_chip()])
        with st.expander(_top.all_label, expanded=False):
            st.dataframe(_records, hide_index=True, width="stretch")
    render_chip_row([cp.guard_chip(PE_BASIS_CHIP)])
    render_candidate_notes()
    # CSV 鈕在 form 外；內容＝L3 排名原表（與舊選股網相同，全量）。
    try:
        _csv = candidate_csv_bytes(_sb.result.df)
    except Exception as _e:  # noqa: BLE001 — 下載不可用不該炸掉整張表
        print(f"[views/page_target] CSV 匯出失敗：{_e!r}")
        st.caption(f"（CSV 匯出暫不可用：{_md_safe(repr(_e))}）")
    else:
        st.download_button("💾 下載選股結果 CSV", data=_csv, file_name="screener_result.csv",
                           mime="text/csv", key=SS_CSV_BUTTON)
    # 選一檔＋查看此檔：維持「使用者明確操作後才取數」（不用 dataframe 點列）。選項是**全部**候選，不只 Top 10。
    _opts = pick_options(_sb)
    if _opts:
        _names = {_code_of(_r): str(_r.get("名稱") or "").strip() for _r in _sb.result.df.to_dict("records")}
        st.selectbox(PICK_LABEL, _opts, format_func=lambda _c: f"{_c} {_names.get(_c, '')}".strip(),
                     key=SS_PICK_WIDGET)
        st.button(PICK_BUTTON_LABEL, key=SS_PICK_BUTTON, on_click=on_pick_click)
        st.caption(PICK_NOTE_SHORT)
    render_chip_row(freshness_chips(session, "screen"))
    render_basis(basis_candidates(_sb), freshness_text(session, "screen"))


def basis_candidates(sb: ScreenBundle) -> Basis:
    _r = sb.result
    if not _r.requested:
        return Basis(
            sources="基本面存活池（全市場季快照）、當日本益比；勾選的因子可能再用缺貨、抗跌、跨季趨勢掃描。尚未選股。",
            as_of="尚未選股",
            rule=(f"基本面四項初篩（負債比<{DEBT_RATIO_MAX * 100:g}%、三率三升 YoY、淨流動值>0、EPS>{EPS_MIN:g}），"
                  "再依勾選因子的百分位平均排序。"),
            missing="尚未選股", confidence="尚未選股")
    _miss = []
    if _r.pe_n is None:
        _miss.append("本益比：這一輪取不到")
    elif _r.pe_n == 0:
        _miss.append("本益比：上游今天沒有給資料")
    if _r.aux_errors:
        _miss.extend(f"{_k}：{_md_safe(_v)}" for _k, _v in _r.aux_errors)
    _miss.append("籌碼：只對選取的那一檔取數，其他候選未取")
    return Basis(
        sources="基本面存活池（全市場季快照）、當日本益比（上市＋上櫃）；產業對映用官方產業別",
        as_of="季快照與本益比的資料日：⬜ 未提供",
        rule=(f"基本面四項初篩（負債比<{DEBT_RATIO_MAX * 100:g}%、三率三升 YoY、淨流動值>0、EPS>{EPS_MIN:g}），"
              "再依勾選因子的百分位平均排序；缺料的因子不計入、不當 0 分。"),
        missing="；".join(_miss),
        confidence=(f"存活池 {'⬜ 未提供' if _r.survivors_n is None else str(_r.survivors_n) + ' 檔'}；"
                    f"選出 {'⬜ 未提供' if _r.rows is None else str(_r.rows) + ' 檔'}"))


# ══════════════════════════════════════════════════════════════════
# 第三區：單一股票（個股七區塊／ETF 版型／判不出型別灰卡）
# ══════════════════════════════════════════════════════════════════
def picked_row(sb: ScreenBundle | None, code: str) -> Mapping | None:
    if sb is None or sb.result is None or sb.result.df is None or getattr(sb.result.df, "empty", True):
        return None
    for _r in sb.result.df.to_dict("records"):
        if _code_of(_r) == code:
            return _r
    return None


def worth_facts(single: SingleBundle, pick: Mapping | None) -> list[str]:
    """「為什麼值得看」：只列**已通過／達標**的既有檢查（事實），不產生新語意、不列低分。

    · 入選本次選股 ＝ 通過基本面四項初篩（候選列存在即成立）；
    · 財報體檢綜合分 **≥ `HEALTH_GRADE_B_MIN`**（L0 既有等第下界，不另立門檻）才列。分數與各因子百分位分留在候選表／健康度卡。
    """
    _out: list[str] = []
    if pick is not None:
        _out.append("入選本次選股（通過基本面四項初篩）")
    _st = single.stock
    if (_st is not None and _st.score_pct is not None and not _st.error and not _st.health_error
            and _st.score_pct >= HEALTH_GRADE_B_MIN):
        _s = f"財報體檢綜合分 {_fmt_f(_st.score_pct, 0)} / 100" + (f"（{_st.grade} 級）" if _st.grade else "")
        _out.append(_s + ("；沒有不及格項目" if not _st.fail_items else ""))
    return _out


def why_not_facts(single: SingleBundle) -> list[str]:
    """「為什麼不能買／資料不足」：只列未通過的檢查項與資料缺漏（事實），不下買賣判斷。"""
    _out: list[str] = []
    _st, _val, _ch = single.stock, single.valuation, single.chips
    if _st is not None:
        if _st.fail_items:
            _out.append("財報體檢未通過的項目：" + "、".join(_md_safe(_i) for _i in _st.fail_items))
        if _st.error or _st.health_error:
            _out.append("財報體檢：取數失敗，這一輪算不出來")
        elif _st.score_pct is None:
            _out.append("財報體檢：資料缺漏，這一檔算不出來（不是 0 分）")
        if _st.price is None:
            _out.append("現價：這一輪沒有取到")
    if _val is not None:
        if _val.error or _val.invalid_items:
            _out.append("357 估值：取數或計算失敗，這一輪算不出來")
        elif not _val.has_zone:
            _out.append("357 估值：未評估（缺股價或配息紀錄，不是 0%）")
    if _ch is not None:
        if _ch.error:
            _out.append("近 20 日籌碼：取數失敗，這一輪算不出來")
        elif _ch.miss_reason:
            _out.append(f"近 20 日籌碼：判不出來（{_md_safe(_ch.miss_reason)}）")
    for _name, _err in single.errors:
        _out.append(f"{_name}：這一區取數拋例外，這一輪算不出來")
    return _out


def _bullets(items: Sequence[str]) -> str:
    return "\n".join(f"- {_i}" for _i in items)


def _render_built(built: Any) -> None:
    I._render_one(built)


def _block_title(title: str) -> None:
    st.markdown(f"**{title}**")


def render_stock_blocks(single: SingleBundle, sb: ScreenBundle | None) -> None:
    """個股七區塊（桌面 3 欄網格；手機單欄）。缺維度一律 ⬜。"""
    _st, _val, _ch = single.stock, single.valuation, single.chips

    def _eps() -> None:
        _block_title(EPS_BLOCK)
        st.caption(EPS_PLACEHOLDER)
        _tv = (_st.trend_verdict if _st is not None else None) or {}
        _verdict = str(_tv.get("verdict") or "").strip() if isinstance(_tv, Mapping) else ""
        st.caption("現有文字判讀（跨季財報趨勢）：" + (_md_safe(_verdict) if _verdict else "⬜ 資料不足"))

    def _trend() -> None:
        _block_title(TREND_BLOCK)
        if _st is not None:
            _render_built(I.build_health_card(_st))

    def _valuation() -> None:
        _block_title(VALUATION_BLOCK)
        if _val is not None:
            _render_built(I.build_valuation_card(_val))

    def _chips() -> None:
        _block_title(CHIPS_BLOCK)
        if _ch is not None:
            _render_built(I.build_chips_card(_ch))

    def _risk() -> None:
        _block_title(RISK_BLOCK)
        st.caption(RISK_PLACEHOLDER)
        st.caption(RISK_NOTE)

    pick = picked_row(sb, single.req.ticker)

    def _worth() -> None:
        _block_title(WORTH_BLOCK)
        _f = worth_facts(single, pick)
        st.markdown(_bullets(_f) if _f else WORTH_EMPTY)
        st.caption(WORTH_NOTE)

    _cells = (_eps, _trend, _valuation, _chips, _risk, _worth)
    for _chunk, _columns in grid(_cells, MAX_COLS):
        for _fn, _col in zip(_chunk, _columns):
            with _col:
                guard("單一股票區塊", _fn)

    _block_title(WHY_NOT_BLOCK)
    st.caption(FACTS_ONLY_NOTE)
    _wf = why_not_facts(single)
    st.markdown(_bullets(_wf) if _wf else WHY_NOT_EMPTY)
    st.caption(RESEARCH_ONLY_NOTE)

    if single.profit is not None:
        section_header(PROFIT_HEADER, PROFIT_CAPTION)
        for _chunk, _columns in grid(tuple(I.build_profit_cards(single.profit)), MAX_COLS):
            for _built, _col in zip(_chunk, _columns):
                with _col:
                    _render_built(_built)


def render_etf_blocks(single: SingleBundle) -> None:
    """ETF 版型：折溢價／配息／同儕三卡（不套個股七區塊）。"""
    if single.etf is None:
        return
    _cards = (I.build_premium_card(single.etf), I.build_dividend_card(single.etf), I.build_peer_card(single.etf))
    for _chunk, _columns in grid(_cards, MAX_COLS):
        for _built, _col in zip(_chunk, _columns):
            with _col:
                _render_built(_built)


def basis_single(single: SingleBundle) -> Basis:
    if not single.req.submitted:
        return Basis(sources="個股：財報體檢、357 存股估值、近 20 日籌碼；ETF：折溢價、配息、同儕。尚未載入。",
                     as_of="尚未載入", rule="尚未載入", missing="尚未載入", confidence="尚未載入")
    _v = single.verdict
    _asof = "⬜ 未提供（沒有取到價格）"
    _price_src = ""
    if single.stock is not None and single.stock.price is not None:
        _pf = dict(PAL.price_basis_facts(single.stock.price_asof))
        _asof = _pf.get("資料日期（價格）") or PAL.price_asof_label(single.stock.price_asof)
        _price_src = _pf.get("使用的資料（價格）", "")
    _miss = why_not_facts(single) if _v.is_stock else []
    return Basis(
        sources=(("個股：財報體檢、357 存股估值（配息＋現價）、近 20 日籌碼" + (f"；{_price_src}" if _price_src else "")) if _v.is_stock
                 else "ETF：折溢價、配息紀錄、同儕排名" if _v.is_etf else "（判型未通過，沒有取數）"),
        as_of=str(_asof),
        rule="判型依代碼規則（00 開頭為 ETF、4 碼首位 1–9 為個股）；各格的判定規則與門檻由既有計算層提供，本頁不重算。",
        missing="；".join(_miss) if _miss else "沒有已知缺項（缺值一律顯示 ⬜，不補 0）",
        confidence=("判型：" + (_v.kind_label or "⬜ 無法判定") + ("（手動指定）" if _v.overridden else "（系統自動）")))


def kind_chip_text(verdict: Any) -> str:
    """判型 chip 文字（`🏢 個股 · 自動判型`／`ETF · 手動指定`…）。只轉述 `KindVerdict`，⛔ 自行判型。"""
    _kind = KIND_CHIP_STOCK if verdict.is_stock else KIND_CHIP_ETF if verdict.is_etf else ""
    if not _kind:
        raise ValueError("判型 chip 只給已判出個股／ETF 的結果（判不出型別走外露灰卡）")
    return f"{_kind} · {KIND_SRC_MANUAL if verdict.overridden else KIND_SRC_AUTO}"


def _tile_state(state: str) -> str:
    """空槽原因 chip 的狀態：沿用 `UI_STATE_META`；`live` 不是缺資料、`partial` 需 N／M ⇒ 一律退 `empty`（灰）。"""
    return state if state in UI_STATE_META and state not in (UI_LIVE, UI_PARTIAL) else UI_EMPTY


def _summary_tile(label: str, value: str | None, *, say: str | None = None, blank_state: str = UI_EMPTY) -> str:
    """一張摘要卡（compact KPI tile）。`value=None` ⇒ 主值留白＋說明原因的狀態 chip（⛔ 不補 0／—）。"""
    if value is None:
        return cp.kpi_tile_html(label=label, value=None, chips=[cp.status_chip(_tile_state(blank_state))])
    return cp.kpi_tile_html(label=label, value=value, say=say or None)


def summary_tiles(single: SingleBundle) -> list[str]:
    """個股摘要卡（≤4；目前 3 張）。**值只取既有 builder／readout 欄位**：財報體檢＝`StockReadout.score_pct`／`grade`，
    357 估值與籌碼＝各自 builder 的 `Card.value`（`殖利率 x%`／`集中度 x%`）與訊號標籤。⛔ 合成、⛔ 重算、⛔ 評分。"""
    _st, _val, _ch = single.stock, single.valuation, single.chips
    _tiles: list[str] = []
    # 財報體檢
    if _st is None:
        _tiles.append(_summary_tile(SUMMARY_HEALTH_LABEL, None))
    else:
        _c = I.build_health_card(_st)[0]
        _score = _fmt_f(_st.score_pct, 0) if _c.state == UI_LIVE else None
        _tiles.append(_summary_tile(SUMMARY_HEALTH_LABEL, f"{_score} / 100" if _score is not None else None,
                                    say=(f"{_st.grade} 級" if _st.grade else None), blank_state=_c.state))
    # 357 估值（標題必帶 357：與候選表「估值（本益比）」是兩種口徑）
    if _val is None:
        _tiles.append(_summary_tile(SUMMARY_VALUATION_LABEL, None))
    else:
        _c, _, _sig = I.build_valuation_card(_val)
        _tiles.append(_summary_tile(SUMMARY_VALUATION_LABEL, _c.value if _c.state == UI_LIVE and _c.value else None,
                                    say=_sig, blank_state=_c.state))
    # 近 20 日籌碼
    if _ch is None:
        _tiles.append(_summary_tile(SUMMARY_CHIPS_LABEL, None))
    else:
        _c, _, _sig = I.build_chips_card(_ch)
        _tiles.append(_summary_tile(SUMMARY_CHIPS_LABEL, _c.value if _c.state == UI_LIVE and _c.value else None,
                                    say=_sig, blank_state=_c.state))
    return _tiles


def why_not_count(single: SingleBundle) -> int:
    """「未通過／缺漏」的**真項數**：體檢未通過項目逐項計（`fail_items` 每項 1），其餘缺漏／失敗各 1。
    ⛔ 不是 `why_not_facts` 的列數（那一列「財報體檢未通過的項目：A、B、C」會把 3 項算成 1 項）。"""
    _facts = why_not_facts(single)
    _fails = len(single.stock.fail_items) if single.stock is not None and single.stock.fail_items else 0
    return len(_facts) - (1 if _fails else 0) + _fails


def count_chips(single: SingleBundle, pick: Mapping | None) -> list[Any]:
    """計數 chip：「✅ 命中 N 項」與「⬜ 未通過／缺漏 M 項」**兩顆分開**（⛔ 合併成一個分數／結論／HOLD）。
    N＝`worth_facts` 列數（每項 1 列）、M＝`why_not_count` 真項數。
    三塊（體檢／357／籌碼）全為 None＝這一輪什麼都沒評估到：⛔ 不得顯示「命中 0 項／缺漏 0 項」（missing≠0），
    改一顆 `⬜ 尚未評估`（取數例外的紅字另在上方外露）；只有部分塊為 None ⇒ 另加 `⬜ k 塊尚未評估`。"""
    if single.stock is None and single.valuation is None and single.chips is None:
        return [cp.guard_chip(NOT_EVALUATED_CHIP)]
    _chips = [cp.guard_chip(HIT_CHIP_FMT.format(n=len(worth_facts(single, pick)))),
              cp.guard_chip(MISS_CHIP_FMT.format(m=why_not_count(single)))]
    # 部分整塊為 None（例如只有體檢有值）：「缺漏 N 項」只數得到已評估那幾塊的缺項，⛔ 不得讓 0 讀成「沒有缺漏」
    # ⇒ 另補明確一顆「⬜ k 塊尚未評估」（missing≠0；與缺漏數分開、不合併）。
    _k = sum(1 for _x in (single.stock, single.valuation, single.chips) if _x is None)
    if _k:
        _chips.append(cp.guard_chip(PARTIAL_NOT_EVALUATED_FMT.format(k=_k)))
    return _chips


def render_summary_tiles(single: SingleBundle) -> None:
    _tiles = summary_tiles(single)
    for _chunk, _columns in grid(tuple(_tiles), MAX_COLS):
        for _html_tile, _col in zip(_chunk, _columns):
            with _col:
                st.markdown(_html_tile, unsafe_allow_html=True)


def render_zone_single(session: Any, sb: ScreenBundle | None) -> None:
    section_header(ZONE3_TITLE)
    if not own_inspect_request(session).submitted:
        st.caption(ZONE3_IDLE)
        return
    _single = single_bundle(session)
    _v = _single.verdict
    for _name, _err in _single.errors:
        st.error(f"🔴 {_name}這一區取數拋例外（其他區照常）：{_md_safe(_err)}", icon="🔴")
    _resolved = _v.is_stock or _v.is_etf
    if _resolved:
        # 判型結果卡 → chip；原卡逐字下沉到「▸ 判型明細」（L3，預設收合）。
        render_chip_row([cp.guard_chip(kind_chip_text(_v))])
        with st.expander(KIND_DETAIL_EXPANDER, expanded=False):
            _render_built(I.build_kind_card(_v, _single.req))
    else:
        # 判不出型別／判型失敗／沒填代碼＝真狀態，不是明細：灰（或紅）卡維持外露。
        _render_built(I.build_kind_card(_v, _single.req))
    if _v.is_stock:
        st.markdown(f"**{_v.code}" + (f" {_single.stock.name}" if _single.stock is not None and _single.stock.name else "")
                    + "（個股）**")
        guard("摘要卡", lambda: render_summary_tiles(_single))
        render_chip_row(count_chips(_single, picked_row(sb, _single.req.ticker)))
        st.markdown(cp.chart_slot_missing_html(UI_UNWIRED, SINGLE_CHART_REASON, height_px=SINGLE_CHART_HEIGHT_PX),
                    unsafe_allow_html=True)
        with st.expander(FULL_ANALYSIS_EXPANDER, expanded=False):
            render_stock_blocks(_single, sb)
    elif _v.is_etf:
        st.markdown(f"**{_v.code}（{ETF_HEADER}）**")
        render_etf_blocks(_single)
    elif _v.is_unknown:
        # 沿用既有灰卡原樣（v2 短句表與 Note 原文綁定，改字會讓卡面轉紅）；指路另補一行白話。
        _render_built(I.build_unknown_card(_v))
        st.caption(UNKNOWN_HINT)
    render_chip_row(freshness_chips(session, "single"))
    render_basis(basis_single(_single), freshness_text(session, "single"))


# ══════════════════════════════════════════════════════════════════
# 進階分析：多檔比較＋仍未覆蓋
# ══════════════════════════════════════════════════════════════════
def render_batch_form(session: Any) -> None:
    with st.form(I.FORM_BATCH_KEY):
        st.text_area("貼一串代碼（可混 個股／ETF；逗號、空白或換行分隔）", key=I.SS_BATCH_WIDGET, height=90,
                     placeholder="例：2330 00878 2317 0050")
        st.selectbox("型別篩選（**只影響顯示，不影響取數**）", list(I.BATCH_FILTER_LABELS),
                     format_func=lambda _k: I.BATCH_FILTER_LABELS[_k], key=I.SS_BATCH_FILTER_WIDGET)
        _submitted = st.form_submit_button(I.ACTION_RUN_BATCH_LABEL, type="primary")
    if _submitted:
        session[I.SS_APPLIED_BATCH] = {
            "raw": session.get(I.SS_BATCH_WIDGET, ""),
            "kind_filter": session.get(I.SS_BATCH_FILTER_WIDGET, I.BATCH_FILTER_ALL),
        }
        bump(session, SS_GEN_BATCH)
    st.caption(BATCH_NOTE)


def _load_batch(req: Any) -> Any:
    if not req.submitted:
        return I.BatchReadout(requested=False)
    try:
        return I.load_batch_rows(req)
    except Exception as _e:  # noqa: BLE001 — 轉成紅態並記住（不在 rerun 重打）
        print(f"[views/page_target] 批次 loader 拋例外：{_e!r}")
        return I.BatchReadout(requested=True, error=repr(_e))


def render_batch(session: Any) -> None:
    st.markdown(f"**{BATCH_TITLE}**")
    render_batch_form(session)
    _req = own_batch_request(session)
    _readout = memoized(session, "batch", _gen(session, SS_GEN_BATCH, I.SS_APPLIED_BATCH),
                        lambda: _load_batch(_req))
    _card, _facts, _signal = I.build_batch_card(_readout, _req)
    I._render_one((_card, _facts, _signal))
    render_freshness(session, "batch")
    if _card.state != UI_LIVE:
        return
    _rows = I.visible_batch_rows(_readout, _req)
    if not _rows:
        st.caption("（這個型別篩選底下沒有任何一列 —— **失敗的列不會被篩掉**，所以這裡是空的就代表真的沒有。）")
        return
    # XV-ASOF（客戶 Q1＝A）：表頭下一行共同時間，例外列在明細標示。
    _asof = I.batch_price_asof_view(_rows)
    if _asof.header:
        st.caption(_asof.header)
    st.dataframe(
        [{"代碼": _r.code, "型別": _r.kind_label,
          "狀態": ("失敗" if not _r.ok else ("判不出型別" if _r.is_unknown else "已算出")),
          "明細": (scrub_state_glyphs(scrub_secrets(_r.error))[0] if not _r.ok else
                   " · ".join(f"{_k}：{_v}" for _k, _v in I.batch_detail_metrics(_r, _sfx))
                   or "（此型別不取數）")}
         for _r, _sfx in zip(_rows, _asof.suffix)],
        hide_index=True, width="stretch")
    # 下鑽：在 form 外，且零額外取數（換一列看的是上面那一輪已算完的結果）。
    _pickable = [_r.code for _r in _rows if _r.ok and not _r.is_unknown]
    if not _pickable:
        st.caption("（沒有可以下鑽的列 —— 失敗與判不出型別的列沒有明細可展開。）")
        return
    _picked = st.selectbox("下鑽看某一檔的判決卡", _pickable, key=I.SS_DRILL_WIDGET)
    _row = next((_r for _r in _rows if _r.code == _picked), None)
    if _row is None:
        return
    section_header(f"{_row.code} · {_row.kind_label}",
                   "依型別走個股或 ETF 的欄位。這一段沒有再發任何取數 —— 顯示的是上面那一輪批次已經算完的同一份結果。")
    _sfx = next((_s for _r2, _s in zip(_rows, _asof.suffix) if _r2 is _row), "")
    for _chunk, _columns in grid(I.batch_detail_metrics(_row, _sfx), MAX_COLS):
        for (_k, _v), _col in zip(_chunk, _columns):
            with _col:
                st.markdown(f"**{_k}**　{_v}")
    if _row.headline:
        st.caption(f"總結：{_row.headline}")
    st.caption(DRILL_FOOT)


def render_uncovered() -> None:
    st.markdown(f"**{UNCOVERED_TITLE}**")
    st.caption(UNCOVERED_LEAD)
    st.markdown("\n".join(f"- **{_k}**：{_v}" for _k, _v in UNCOVERED_ITEMS))
    st.caption(UNCOVERED_FOOT)


def render_advanced(session: Any) -> None:
    with st.expander(ADVANCED_EXPANDER, expanded=False):
        guard(BATCH_TITLE, lambda: render_batch(session))
        guard(UNCOVERED_TITLE, render_uncovered)
