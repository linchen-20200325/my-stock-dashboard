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

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import streamlit as st

from shared import price_asof_label as PAL
from shared.fundamental_prescreen_thresholds import (
    DEBT_RATIO_MAX,
    EPS_MIN,
    PRESCREEN_REQUIRED_PASSES,
)
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
from shared.ui_state import UI_LIVE
from src.ui.tabs.tab_today import scrub_state_glyphs
from src.ui.views import page_find as F
from src.ui.views import page_inspect as I
from src.ui.views._ui_kit import MAX_COLS, grid, section_header
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
MA_ONLY_DISPLAY_NOTE: str = "均線勾選目前只會顯示，不影響任何結論"
MA_GROUP_LABEL: str = "**均線（僅顯示）**"
PERIOD_NOTE: str = "期間只決定籌碼載入多長的日線；近 20 日的判讀窗由上游決定，改期間不會改變籌碼結論。"
REAL_PRICE_NOTE: str = "K 線一律用還原價（已還原除權息）。"

ZONE1_TITLE: str = "第一區｜產業機會"
ZONE1_SAY: str = "先找正在變強的產業，再從產業裡找公司；避免只看單一股票短線漲跌。"
ZONE1_SORT_NOTE: str = "排序依據：法人資金動能，非產業趨勢。"
ZONE1_NO_TREND_NOTE: str = "產業趨勢為研究中，尚未定義；本表不判斷產業興衰，沒有正式資料的維度一律顯示 ⬜，不補值、不由 AI 補。"
ZONE1_IDLE: str = "按下「🗺️ 載入板塊地圖」後顯示產業資料（在按之前不會取數）。"
MATRIX_COLS: tuple[str, ...] = ("產業", "基本面成長", "相對強弱", "法人／籌碼", "估值", "資料可信度")
NOT_BUILT: str = "⬜ 尚未建置"
STRENGTH_ONLY_FLOW: str = "⬜（僅有資金動能，非價格相對強弱）"
FLOW_MISSING: str = "⬜ 資料不足（窗口內缺值，不補 0）"
HEATMAP_EXPANDER: str = "產業漲跌熱力圖（單一代表股近似，非類股指數）"
BUBBLE_EXPANDER: str = "三大法人資金流泡泡圖（含持股⭐）"
HEATMAP_SWITCH_PLAIN: str = "本頁固定畫這一組；新版尚未提供切換市場或區間。"

ZONE2_TITLE: str = "第二區｜候選標的"
ZONE2_SAY: str = "優先看基本面，再看價格與技術面。選一檔，下方展開單一股票。"
SCREEN_EXPANDER: str = "選股條件"
CANDIDATE_COLS: tuple[str, ...] = ("標的", "產業", "基本面", "估值", "籌碼", "狀態")
PICK_LABEL: str = "選擇標的"
PICK_BUTTON_LABEL: str = "🔍 查看此檔"
PICK_NOTE: str = "選一檔後按「🔍 查看此檔」才會取這一檔的資料；候選表本身不會自動逐檔取數。"
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

ZONE3_TITLE: str = "第三區｜單一股票"
ZONE3_IDLE: str = "還沒選標的：在上方輸入代碼，或在候選表選一檔。"
EPS_BLOCK: str = "EPS／營收"
EPS_PLACEHOLDER: str = "⬜ 趨勢圖尚未建置"
TREND_BLOCK: str = "財報趨勢"
VALUATION_BLOCK: str = "估值（357 存股估值）"
CHIPS_BLOCK: str = "籌碼"
RISK_BLOCK: str = "風險"
RISK_PLACEHOLDER: str = "⬜ 個股風險指標尚未接線"
RISK_NOTE: str = "目前只有財報體檢未通過項目與籌碼的單日爆量檢查，分別列在「為什麼不能買／資料不足」與「籌碼」。"
WORTH_BLOCK: str = "為什麼值得看"
WORTH_EMPTY: str = "⬜ 目前沒有可列的命中項目（可能尚未載入選股結果，或資料不足）"
WORTH_NOTE: str = "只列已命中的既有檢查，不構成買賣判斷。"
WHY_NOT_BLOCK: str = "為什麼不能買／資料不足"
FACTS_ONLY_NOTE: str = "僅列事實，不下買賣判斷"
RESEARCH_ONLY_NOTE: str = "本頁只呈現研究資訊，不提供交易操作"
WHY_NOT_EMPTY: str = "⬜ 目前沒有可列的未通過項目或資料缺漏"
PROFIT_HEADER: str = "💰 獲利能力診斷"
ETF_HEADER: str = "ETF"
UNKNOWN_HINT: str = "這個代碼系統無法判定是個股或 ETF；可展開上方「進階選項」手動指定判型後再載入。"

ADVANCED_EXPANDER: str = "進階分析（預設收合；功能保留，只降階）"
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


def memoized(session: Any, slot: str, gen: Any, compute: Callable[[], Any]) -> Any:
    """依「使用者要求的世代」記住結果：同世代 ⇒ 不再呼叫 `compute`（不論成功或失敗），新世代 ⇒ 重算。

    ⛔ 不是快取層（無 TTL、不跨 session）：它是「這一次要求的答案」，隨使用者下一次送出而換。
    失敗結果也只呈現到使用者再按一次，**rerun 不會自動重打上游**（§1.A-3(b)）。
    """
    _key = f"{SS_MEMO_PREFIX}{slot}"
    _cur = session.get(_key)
    if isinstance(_cur, tuple) and len(_cur) == 2 and _cur[0] == gen:
        return _cur[1]
    _val = compute()
    session[_key] = (gen, _val)
    return _val


def _gen(session: Any, counter_key: str, applied_key: str) -> tuple[int, str]:
    """世代 ＝（計數器, 已套用值的內容）：兩者任一變就算新一次要求。"""
    return int(session.get(counter_key, 0) or 0), repr(session.get(applied_key))


def bump(session: Any, counter_key: str) -> None:
    session[counter_key] = int(session.get(counter_key, 0) or 0) + 1


def inject_css() -> None:
    """兩族 v2 卡面的樣式表**一次**吐齊（page_find 的 `_inject_v2_css` 與 page_inspect 的各吐一份 ⇒ 重複）。"""
    try:
        st.markdown(
            f"<style>{v2_markup.page_css(F.V2_CSS_MODE)}\n{F.V2_FOLD_WRAP_CSS}\n{I.V2_INSPECT_CARD_CSS}</style>",
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


def render_basis(basis: Basis) -> None:
    with st.expander(BASIS_EXPANDER_LABEL, expanded=False):
        st.markdown("\n".join(f"- **{_k}**：{scrub_secrets(_v)}" for _k, _v in basis_rows(basis)))


# ══════════════════════════════════════════════════════════════════
# 單檔入口（搜尋框＋進階選項；同一個 form、一顆送出鈕）
# ══════════════════════════════════════════════════════════════════
def write_applied_ticker(session: Any, ticker: Any) -> None:
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
        "kind_choice": session.get(I.SS_KIND_WIDGET, I.KIND_CHOICE_AUTO),
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
    write_applied_ticker(_s, _code)
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
                                    key=f"{I.SS_MA_WIDGET_PREFIX}{_ma}", help="僅顯示，不影響任何結論")
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
    _req = I.applied_inspect_request(session)
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


@dataclass(frozen=True)
class MapBundle:
    flow: Any
    heatmap: Any


def map_bundle(session: Any) -> MapBundle:
    def _compute() -> MapBundle:
        with st.spinner("載入板塊資料…"):
            _hm = F.load_heatmap(requested=True)
            _flow = F.load_sector_flow(session, requested=True)
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


def render_zone_industry(session: Any) -> None:
    section_header(ZONE1_TITLE, ZONE1_SAY)
    st.caption(ZONE1_SORT_NOTE)
    st.caption(ZONE1_NO_TREND_NOTE)
    # 板塊地圖的**唯一** gate 寫入點（單顆 st.button，不在 form 內）。
    if st.button(F.ACTION_LOAD_MAP_LABEL, key=F.SS_MAP_BUTTON, type="primary"):
        session[F.SS_MAP_REQUESTED] = True
        bump(session, SS_GEN_MAP)
    if not F.map_requested(session):
        st.caption(ZONE1_IDLE)
        render_basis(basis_industry(None))
        return
    _mb = map_bundle(session)
    _flow, _hm = _mb.flow, _mb.heatmap
    if not _flow.ok:
        # 快取還沒產生（灰）／取數失敗（紅）：狀態卡放在區塊外面，不收進展開區。
        _card, _facts = F.build_sector_flow_card(_flow)
        F._render_one(_card, _facts)
    else:
        _matrix = build_industry_matrix(_flow.sectors)
        if _matrix:
            st.dataframe([_r.as_record() for _r in _matrix], hide_index=True, width="stretch")
        if _flow.stale:
            st.caption("⚠️ 資料過期：畫的是最後一次成功凍結的快照"
                       + (f"（{_md_safe(_flow.stale_reason)}）" if _flow.stale_reason else "") + "。")
        if _flow.tpex_complete is not True:
            st.caption(SECTOR_FLOW_TWSE_ONLY_NOTE)
        _unav = format_unavailable_caption(_flow.sectors)
        if _unav:
            st.caption(_unav)
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
    render_basis(basis_industry(_flow))


def basis_industry(flow: Any) -> Basis:
    if flow is None or not getattr(flow, "requested", False):
        return Basis(
            sources="三大法人資金流快取（板塊資金潮汐）；產業分類用官方產業別。尚未載入。",
            as_of="尚未載入", rule="尚未載入；載入後以近 N 日累計淨流入與動能變化分象限，不做綜合強弱分數。",
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
        as_of=(flow.updated_at or "⬜ 未提供"),
        rule=(f"近 {WINDOW_X} 個交易日累計淨流入與動能變化 → 漲潮／輪動／退潮／觀望；"
              "交易日不足者標「資料不足」。本表不做綜合強弱分數。"),
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


def _load_screen_bundle(req: Any) -> ScreenBundle:
    if not req.submitted:
        # 冷啟動：沒有人要求 ⇒ 連 loader 都不呼叫。
        return ScreenBundle(req=req, result=F.ScreenResult(requested=False))
    _result = F.load_screen_result(req)
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
    if _result.pe_n:
        _m, _n, _err, _fm = F._load_pe_name_maps()
        if _m is not None and not _err:
            _pe_map, _pe_failed = _m, False
    return ScreenBundle(req=req, result=_result, sector=_sector, sector_error=_sec_err,
                        pe_map=_pe_map, pe_failed=_pe_failed)


def screen_bundle(session: Any) -> ScreenBundle:
    _req = F.applied_screen_request(session)
    return memoized(session, "screen", _gen(session, SS_GEN_SCREEN, F.SS_APPLIED_SCREEN),
                    lambda: _load_screen_bundle(_req))


def peek_screen_bundle(session: Any) -> ScreenBundle | None:
    """只讀：第二區已記住的選股結果（同世代才算）；沒有就 None。⛔ 不取數、不觸發選股。"""
    _cur = session.get(f"{SS_MEMO_PREFIX}screen")
    if (isinstance(_cur, tuple) and len(_cur) == 2
            and _cur[0] == _gen(session, SS_GEN_SCREEN, F.SS_APPLIED_SCREEN)
            and isinstance(_cur[1], ScreenBundle)):
        return _cur[1]
    return None


def _code_of(row: Mapping) -> str:
    return str(row.get("代碼") or "").strip()


def chips_cell(code: str, single: SingleBundle | None) -> str:
    """候選表「籌碼」格：**只有使用者選取（已載入）的那一檔**有值；其餘「未取」（⛔ 不填 0、不推定中性）。"""
    if single is None or not single.req.submitted or single.chips is None:
        return CHIPS_NOT_FETCHED
    if single.verdict is None or not single.verdict.is_stock or single.req.ticker != code:
        return CHIPS_NOT_FETCHED
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
            _ind = SECTOR_UNAVAILABLE_CELL
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
            _pe = _pv if _pv is not None else PE_NOT_PROVIDED_CELL
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


def render_zone_candidates(session: Any) -> None:
    section_header(ZONE2_TITLE, ZONE2_SAY)
    with st.expander(SCREEN_EXPANDER, expanded=True):
        render_screen_form(session)
    _sb = screen_bundle(session)
    _card, _facts = F.build_screen_result_card(_sb.result, _sb.req)
    F._render_one(_card, _facts)
    if _card.state != UI_LIVE:
        render_basis(basis_candidates(_sb))
        return
    st.caption("本次因子：" + (" · ".join(_sb.result.hits) if _sb.result.hits else "僅基本面四項全過"))
    _single = single_bundle(session) if I.applied_inspect_request(session).submitted else None
    _records = build_candidate_rows(_sb, _single)
    st.dataframe(_records, hide_index=True, width="stretch")
    st.caption(PE_COL_NOTE)
    st.caption(CHIPS_COL_HINT)
    st.caption(FIN_STOCK_NOTE)
    # CSV 鈕在 form 外；內容＝L3 排名原表（與舊選股網相同）。
    try:
        _csv = _sb.result.df.to_csv(index=False).encode("utf-8-sig")
    except Exception as _e:  # noqa: BLE001 — 下載不可用不該炸掉整張表
        print(f"[views/page_target] CSV 匯出失敗：{_e!r}")
        st.caption(f"（CSV 匯出暫不可用：{_md_safe(repr(_e))}）")
    else:
        st.download_button("💾 下載選股結果 CSV", data=_csv, file_name="screener_result.csv",
                           mime="text/csv", key=SS_CSV_BUTTON)
    # 選一檔＋查看此檔：維持「使用者明確操作後才取數」（不用 dataframe 點列）。
    _opts = pick_options(_sb)
    if _opts:
        _names = {_code_of(_r): str(_r.get("名稱") or "").strip() for _r in _sb.result.df.to_dict("records")}
        st.selectbox(PICK_LABEL, _opts, format_func=lambda _c: f"{_c} {_names.get(_c, '')}".strip(),
                     key=SS_PICK_WIDGET)
        st.button(PICK_BUTTON_LABEL, key=SS_PICK_BUTTON, on_click=on_pick_click)
        st.caption(PICK_NOTE)
    render_basis(basis_candidates(_sb))


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
    """「為什麼值得看」：只列**已命中的既有檢查**（事實），不產生新語意。"""
    _out: list[str] = []
    if pick is not None:
        _sc = _fmt_f(pick.get("綜合分"))
        _head = "入選本次選股（通過基本面四項初篩）"
        _out.append(_head + (f"，綜合分 {_sc}" if _sc is not None else ""))
        for _col in ("估值分", "EPS分", "缺貨分", "RS分", "跨季分"):
            _v = _fmt_f(pick.get(_col))
            if _v is not None:
                _out.append(f"{_col} {_v}")
    _st = single.stock
    if _st is not None and _st.score_pct is not None and not _st.error and not _st.health_error:
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
        section_header(PROFIT_HEADER, "缺值是灰的「資料缺漏」，不是紅的「辛苦生意」。")
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


def render_zone_single(session: Any, sb: ScreenBundle | None) -> None:
    section_header(ZONE3_TITLE)
    if not I.applied_inspect_request(session).submitted:
        st.caption(ZONE3_IDLE)
        return
    _single = single_bundle(session)
    _v = _single.verdict
    for _name, _err in _single.errors:
        st.error(f"🔴 {_name}這一區取數拋例外（其他區照常）：{_md_safe(_err)}", icon="🔴")
    _render_built(I.build_kind_card(_v, _single.req))
    if _v.is_stock:
        st.markdown(f"**{_v.code}" + (f" {_single.stock.name}" if _single.stock is not None and _single.stock.name else "")
                    + "（個股）**")
        render_stock_blocks(_single, sb)
    elif _v.is_etf:
        st.markdown(f"**{_v.code}（{ETF_HEADER}）**")
        render_etf_blocks(_single)
    elif _v.is_unknown:
        # 沿用既有灰卡原樣（v2 短句表與 Note 原文綁定，改字會讓卡面轉紅）；指路另補一行白話。
        _render_built(I.build_unknown_card(_v))
        st.caption(UNKNOWN_HINT)
    render_basis(basis_single(_single))


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


def render_batch(session: Any) -> None:
    st.markdown(f"**{BATCH_TITLE}**")
    render_batch_form(session)
    _req = I.applied_batch_request(session)
    _readout = memoized(session, "batch", _gen(session, SS_GEN_BATCH, I.SS_APPLIED_BATCH),
                        lambda: I.load_batch_rows(_req) if _req.submitted else I.BatchReadout(requested=False))
    _card, _facts, _signal = I.build_batch_card(_readout, _req)
    I._render_one((_card, _facts, _signal))
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
    st.caption("這些功能舊畫面有、新畫面還沒接上，本次不會出現在這一頁：")
    st.markdown("\n".join(f"- **{_k}**：{_v}" for _k, _v in UNCOVERED_ITEMS))
    st.caption(UNCOVERED_FOOT)


def render_advanced(session: Any) -> None:
    with st.expander(ADVANCED_EXPANDER, expanded=False):
        guard(BATCH_TITLE, lambda: render_batch(session))
        guard(UNCOVERED_TITLE, render_uncovered)
