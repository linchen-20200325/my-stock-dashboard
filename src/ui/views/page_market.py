"""src/ui/views/page_market.py — IA v2「📊 大盤」頁（L5 UI）。

單一職責（客戶 DEC-072／076 原文）::

    現在市場環境適不適合投資？目前可以承擔多少風險？

規格出處：`docs/vnext/MARKET_PAGE_DECISION_GATE_2026-10-24.md`（v4，§1 線框、§1.2 R1～R12、
§1.3 狀態字樣、§2 X1～X11、§4 W1～W13、§5.1 Risk Cap 卡位契約）＋ **客戶 2026-10-25 裁示**
（與文件不同處以裁示為準）：

  · Q1=C：本頁承接「🚦 今天」的大盤能力；作戰室日後移到 ⚡ 行動（本批不做）。
    **「🚦 今天」頁在驗收前原樣保留，⛔ 不刪、不改**（`app.py` 兩頁並存）。
  · Q2-1 放結論句：子句只用「；」並列（⛔ 但／因此／所以），缺值照實寫 →
    L0 `shared/market_conclusion.py`。
  · Q2-2 放 Risk Cap 卡位：卡面只有「風險上限」＋「獨立顯示待 C2b＋RC-VISIBILITY Gate」；
    ⛔ 本卡不讀、不推導、不顯示任何上限數字。
  · Q2-3 移除三欄摘要（本頁不畫；今天頁那一份不動）。
  · Q3=A：台股／國際趨勢卡只寫「尚未定義」＋一句說明；⛔ 無燈色、無多空字樣、無選定指標。
    原始資料只放第 3 層展開區，標題寫「原始資料，不構成趨勢判斷」。
  · Q4=C：舊 UI 的綜合結論句（Gate 文件 §3.15 S01～S14）⛔ 不帶入。

═══ 這個檔**不是**什麼 ═══════════════════════════════════════════════
- **不是新的計算**：卡①「能不能出手 · 出手到幾成」、指標危險度、市場位階、16 盞燈、今日關鍵、
  🚀 更新鈕與更新報告，**全部呼叫 `page_today` 的同一段程式**（`build_verdict_tiles` 等）。
  同一輸入 ⇒ 同一張卡（`tests/test_page_market.py` 釘住）。
  ⚠️ **刻意以 `today._xxx` 經模組屬性取用 `page_today` 的底線函式**（呼叫時才解析）：
  (a) `page_today.py` 受多條「還原鏈／基底指紋」守衛（`tests/test_batch_c21.py` 等）釘住，
  為了承接而改它＝動到「🚦 今天」頁（Q1=C：驗收前不改）；(b) 同為 L5 `src/ui/views/`、
  非跨層（V-PICKER-PRIV-1 講的是 L5 直取 L1 私有符號）；(c) 經模組屬性呼叫 ⇒ 測試對
  `page_today` 的 monkeypatch 兩頁同時生效。代價：`page_today` 改這些函式名時本頁會 AttributeError
  （由 `_render_tab_isolated` 紅框＋本檔測試當場轉紅，⛔ 不會靜默）。
- **不接新資料源**：第 3 層原始資料只讀本 session 裡**既有**的 key（「🚀 更新今日戰情」的
  L3 `macro_refresh_service` 寫入的那些）；⛔ 本檔不 import 任何 `src.data.*`。
- **不碰 Sheet**：本頁沒有任何 Sheet 讀寫。
- **不顯示 Risk Cap 獨立數字**：見上。⚠️ 揭露（Gate 文件 R6／X10，現行行為照舊）：卡①在系統風險上限
  有效時照今天頁顯示「硬否決天花板」列；更新報告的步驟說明也照舊會列出本次寫檔的值。
  兩者都是沿用今天頁同一段程式，本批不改（改它屬 RC-VISIBILITY）。

掛載：`app.py::_ia_view_market()` 於側欄「🆕 新版戰情室（試用中）」radio 選到本頁時
late import 並呼叫 `render_page_market()`；沒被選到時本檔連 import 都不發生。

分層：L5 —— 依賴 L0（`shared.*`）、L5（`page_today`／`_ui_kit`），以及函式體內 lazy 的
L3 `services.section_inputs`／L2 `compute.macro.macro_helpers`（X1 的缺漏來源清單，與 L3
`warroom_apply` 同一支 `calc_traffic_light`）。⛔ 零 `src.data.*`。
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import streamlit as st

from shared import ia_nav
from shared.inst_net import is_net_observed
from shared.market_conclusion import (
    CONCEPT_INTL_TREND,
    CONCEPT_RISK_CAP,
    CONCEPT_TW_TREND,
    RISK_CAP_PENDING_TEXT,
    TREND_UNDEFINED_TEXT,
    build_market_conclusion,
)
from shared.secret_scrub import scrub_secrets
from shared.ui_state import UI_DEGRADED, UI_FAILED, UI_IDLE, UI_LIVE, UI_PARTIAL
from src.ui.views import page_today as today
from src.ui.views._ui_kit import section_header

# ══════════════════════════════════════════════════════════════════
# session key（本頁自有前綴 `p00m_`，不與其他頁相撞）
# ══════════════════════════════════════════════════════════════════
#: 第 3 層「重」的區塊（走勢圖、逐日表）各自一顆 checkbox gate（勾選才畫）。
SS_GATE_TW_CHART: str = "p00m_gate_tw_chart"
SS_GATE_ADL: str = "p00m_gate_adl"
SS_GATE_INTL_CHART: str = "p00m_gate_intl_chart"
SS_GATE_LEADING: str = "p00m_gate_leading"

# ══════════════════════════════════════════════════════════════════
# 首屏字樣
# ══════════════════════════════════════════════════════════════════
PAGE_QUESTION: str = "現在市場環境適不適合投資？目前可以承擔多少風險？"
CONCLUSION_HEADING: str = "今日結論（五項各自判斷，只並列，不合成）"
#: 趨勢兩卡的說明（Q3=A：只說定義在等客戶，⛔ 不帶任何指標、燈色、多空字樣）。
TREND_PENDING_WHY: str = "怎麼判斷還在等您定義；定義之前本頁不給這一項結論。"
#: 第 3 層原始資料區的標題後綴（Q3=A 原文）。
RAW_DATA_SUFFIX: str = "原始資料，不構成趨勢判斷"
#: 狀態列：按更新的時間 ≠ 資料日（R8）。
REFRESH_TIME_NOTE: str = "按下更新的時間，不是資料日"
NO_REFRESH_YET: str = "本次使用中尚未按過更新"
AS_OF_NOT_PROVIDED: str = "逐項資料日：尚未提供（現行契約沒有逐指標的資料日欄位）"
MISSING: str = "無資料"

# ══════════════════════════════════════════════════════════════════
# 第 2／3 層固定說明（X3、X9；純文字，⛔ 無數字）
# ══════════════════════════════════════════════════════════════════
X3_TITLE: str = "風險上限：為什麼獨立卡位目前不顯示數字？"
X3_TEXT: str = (
    "- 客戶已裁示：風險上限目前**不恢復獨立顯示**，等 C2b 與 RC-VISIBILITY 的顯示方式 Gate 之後再做。\n"
    "- 哪些輸入可以計分，仍待 C2b 裁示。\n"
    "- 上限有效時，數字會出現在「能不能出手 · 出手到幾成」卡的「硬否決天花板」列（與「🚦 今天」頁同一段程式）。\n"
    "- 那張卡顯示「無法判定」時，常見原因之一是健康分因缺正式漲跌家數而未評估；"
    "但本頁**分不出**是尚未計算、本輪算不出、檔案過期還是讀不出。\n"
    "- 系統仍照常計算並寫檔；每次更新的報告（下方「資料來源與完整度」）會列出本次寫入的值。")
X9_TITLE: str = "研究中（Candidate／Research，不是判斷規則）"
X9_TEXT: str = (
    "- 「大盤 EPS×PE 情境估值」\n"
    "- 「長天期殖利率×景氣領先指標」\n"
    "- 「AI 資本支出→EPS」\n\n"
    "以上屬研究框架：目前沒有資料、也不是判斷規則，本頁不顯示任何相關數字。")

# ══════════════════════════════════════════════════════════════════
# 第 3 層原始資料規格（白名單：只列數值、日期、來源、代理／估算標示 —— R12）
# ══════════════════════════════════════════════════════════════════
#: (顯示名, session key, 路徑, 單位, 註記)。⛔ 不收任何 label／regime／score／action 類欄位。
RawSpec = tuple[str, str, tuple[str, ...], str, str]

X5_FIELDS: tuple[RawSpec, ...] = (
    ("加權指數收盤（市場評估輸入）", "mkt_info", ("index_price",), "", ""),
    ("加權指數資料日", "mkt_info", ("index_as_of",), "", ""),
    ("MA5", "mkt_info", ("ma5",), "", ""),
    ("MA60", "mkt_info", ("ma60",), "", ""),
    ("MA120", "mkt_info", ("ma120",), "", ""),
    ("MA200", "mkt_info", ("ma200",), "", ""),
    ("MA200 說明", "mkt_info", ("ma200_status",), "", ""),
    ("收盤是否低於 MA5", "mkt_info", ("index_below_ma5",), "", "事實，不是訊號"),
    ("乖離計算用收盤", "bias_info", ("price",), "", ""),
    ("MA240", "bias_info", ("ma240",), "", ""),
    ("月線乖離（BIAS20）", "bias_info", ("bias_20",), "%", ""),
    ("季線乖離（BIAS60）", "bias_info", ("bias_60",), "%", ""),
    ("年線乖離（BIAS240）", "bias_info", ("bias_240",), "%", ""),
    ("乖離計算用資料天數", "bias_info", ("data_days",), " 天", ""),
    ("乖離資料日", "bias_info", ("as_of",), "", ""),
    ("旌旗（上漲佔比 5 日均）", "jingqi_info", ("avg",), "%", ""),
    ("旌旗來源", "jingqi_info", ("source",), "", ""),
)

X6_FIELDS: tuple[RawSpec, ...] = (
    ("VIX", "macro_info", ("vix", "current"), "", ""),
    ("VIX 20 日均", "macro_info", ("vix", "ma20"), "", ""),
    ("VIX 資料日", "macro_info", ("vix", "date"), "", ""),
    ("VIX 來源", "macro_info", ("vix", "source"), "", ""),
)

X7_FIELDS: tuple[RawSpec, ...] = (
    ("台灣製造業 PMI", "macro_info", ("ism_pmi", "value"), "", "session key 名稱沿用 `ism_pmi`，內容是台灣 PMI"),
    ("台灣 PMI 資料日", "macro_info", ("ism_pmi", "date"), "", ""),
    ("台灣 PMI 來源", "macro_info", ("ism_pmi", "source"), "", ""),
    ("國發會景氣對策信號分數", "macro_info", ("ndc_signal", "score"), " 分", "官方原始值"),
    ("國發會景氣對策信號燈號", "macro_info", ("ndc_signal", "signal"), "", "官方原始值"),
    ("國發會資料日", "macro_info", ("ndc_signal", "date"), "", ""),
    ("國發會來源", "macro_info", ("ndc_signal", "source"), "", ""),
    ("台灣出口年增率", "macro_info", ("tw_export", "yoy"), "%", ""),
    ("出口資料日", "macro_info", ("tw_export", "date"), "", ""),
    ("出口來源", "macro_info", ("tw_export", "source"), "", ""),
    ("M1B 年增率", "m1b_m2_info", ("m1b_yoy",), "%", ""),
    ("M2 年增率", "m1b_m2_info", ("m2_yoy",), "%", ""),
    ("M1B−M2 差", "m1b_m2_info", ("gap",), " 個百分點", "已停用（不計分）"),
    ("M1B／M2 資料月", "m1b_m2_info", ("data_month",), "", ""),
    ("M1B／M2 來源", "m1b_m2_info", ("source",), "", ""),
    ("美國核心 CPI 年增率", "macro_info", ("us_core_cpi", "yoy"), "%", ""),
    ("美國核心 CPI 前期年增率", "macro_info", ("us_core_cpi", "prev_yoy"), "%", ""),
    ("美國核心 CPI 資料日", "macro_info", ("us_core_cpi", "date"), "", ""),
    ("Fed 利率", "macro_info", ("fed_funds", "current"), "%", ""),
    ("Fed 利率前期", "macro_info", ("fed_funds", "prev"), "%", ""),
    ("Fed 利率資料日", "macro_info", ("fed_funds", "date"), "", ""),
    ("美國 10 年債殖利率（FRED）", "macro_info", ("us10y", "current"), "%", "與國際市場區的 Yahoo ^TNX 不同源"),
    ("美國 10 年債資料日", "macro_info", ("us10y", "date"), "", ""),
)

#: 先行指標逐日表（`li_latest`）只取這幾欄。⛔ 不含融券（`DH-SHORT-UNIT`，首批不承接）。
LEADING_COLUMNS: tuple[tuple[str, str], ...] = (
    ("日期", ""),
    ("外資", "現貨"),
    ("投信", "現貨"),
    ("自營", "現貨"),
    ("外資大小", "外資期貨淨口"),
    ("選PCR", "法人估算"),
    ("外(選)", ""),
    ("韭菜指數", "散戶指標"),
    ("融資餘額", "門檻已失準；單位混用區間屬資料疑義"),
)

#: `cl_data` 各組 DataFrame 的來源標示（ticker 對照 SSOT 在 L3 `daily_checklist.*_MAP`，
#: 本頁只讀 session 裡的名字，⛔ 不另抄一份 ticker 表）。
FRAME_SOURCE_NOTE: dict[str, str] = {
    "tw": "Yahoo Finance（市場資料抓取組 `cl_data['tw']`）",
    "intl": "Yahoo Finance（`cl_data['intl']`；其中 10 年債殖利率是 ^TNX，與總經區的 FRED 10 年債不同源）",
    "tech": "Yahoo Finance（`cl_data['tech']`）",
}

#: ADL 區的必要註記（Gate 文件 X5）。
ADL_NOTE: str = ("此數字目前沒有接進位階與健康分的計算；能不能當正式廣度來源，屬 G4 待研究。")


# ══════════════════════════════════════════════════════════════════
# 純函式：原始值格式化（R12：只出數值／日期／來源；缺值照實寫）
# ══════════════════════════════════════════════════════════════════
def fmt_value(value: Any, unit: str = "") -> str:
    """原始值 → 顯示字串。None／空字串 → 「無資料」；非有限數 → 「無資料（非有限值）」。"""
    if value is None:
        return MISSING
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        _f = float(value)
        if not math.isfinite(_f):
            return f"{MISSING}（非有限值）"
        if isinstance(value, int):
            return f"{value:,}{unit}"
        return f"{_f:,.2f}{unit}"
    _s = str(value).strip()
    return _s if _s else MISSING


def dig(obj: Any, path: Sequence[str]) -> Any:
    """沿路徑取值；任何一層不是 Mapping 或缺 key → None（⛔ 不補預設值）。"""
    _cur = obj
    for _k in path:
        if not isinstance(_cur, Mapping) or _k not in _cur:
            return None
        _cur = _cur[_k]
    return _cur


def raw_rows(session: Mapping[str, Any], specs: Sequence[RawSpec]) -> list[tuple[str, str, str]]:
    """白名單欄位 → `(顯示名, 值, 註記)`。BIAS240 在資料不足 240 日時標「估算・N 天資料」。"""
    _rows: list[tuple[str, str, str]] = []
    for _label, _key, _path, _unit, _note in specs:
        _src = session.get(_key) if isinstance(session, Mapping) else None
        _v = dig(_src, _path)
        _n = _note
        if _key == "bias_info" and _path == ("bias_240",) and _v is not None:
            if dig(_src, ("is_estimated",)) is True:
                _days = dig(_src, ("data_days",))
                _n = f"估算・{fmt_value(_days)} 天資料"
        if _key == "jingqi_info" and dig(_src, ("is_proxy",)) is True:
            _n = (_n + "；" if _n else "") + "代理（估算）值，只顯示不計分"
        _rows.append((_label, fmt_value(_v, _unit), _n))
    return _rows


def frame_last_close(frame: Any) -> tuple[str, str, str]:
    """DataFrame → `(最後收盤, 最後一筆日期, 筆數)`。不是 DataFrame／空 → 三格皆「無資料」。"""
    _cols = getattr(frame, "columns", None)
    if _cols is None or getattr(frame, "empty", True):
        return MISSING, MISSING, MISSING
    _col = next((_c for _c in ("close", "Close") if _c in _cols), None)
    if _col is None:
        return MISSING, MISSING, f"{len(frame):,}"
    _series = frame[_col].dropna()
    if _series.empty:
        return MISSING, MISSING, f"{len(frame):,}"
    _last = _series.iloc[-1]
    _idx = _series.index[-1]
    _date = str(_idx)[:10] if _idx is not None else MISSING
    try:
        _val = fmt_value(float(_last))
    except (TypeError, ValueError):
        _val = MISSING
    return _val, _date, f"{len(frame):,}"


def frame_rows(session: Mapping[str, Any], group: str) -> list[tuple[str, str, str, str]]:
    """`cl_data[group]`（name → DataFrame）→ `(名稱, 最後收盤, 資料日, 筆數)`。"""
    _grp = dig(session.get("cl_data") if isinstance(session, Mapping) else None, (group,))
    if not isinstance(_grp, Mapping):
        return []
    return [(str(_name), *frame_last_close(_df)) for _name, _df in _grp.items()]


def inst_rows(session: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    """三大法人淨買賣超（億元）。未觀測的列寫「無資料（未觀測）」，⛔ 不印預填的 0。"""
    _cl = session.get("cl_data") if isinstance(session, Mapping) else None
    _inst = dig(_cl, ("inst",))
    _src = "本輪"
    if not _inst:
        _inst = session.get("_last_inst") if isinstance(session, Mapping) else None
        _src = "上一次有效值（本輪沒有）"
    if not isinstance(_inst, Mapping) or not _inst:
        return []
    _rows: list[tuple[str, str, str]] = []
    for _name, _rec in _inst.items():
        if not is_net_observed(_inst, _name):
            _rows.append((str(_name), f"{MISSING}（未觀測）", _src))
            continue
        _rows.append((str(_name), fmt_value(dig(_rec, ("net",)), " 億"), _src))
    return _rows


def regime_clause(tile: Any) -> str | None:
    """市場位階卡 → 結論句子句內容。None ＝ 缺（由 L0 照實寫「無資料（未評估）」）。"""
    _state = tile.card.state
    if _state == UI_LIVE:
        return str(tile.card.value)
    if _state == UI_DEGRADED:
        return f"{tile.signal_text}（門檻已失準）"
    if _state == UI_FAILED:
        return "讀取失敗（未評估）"
    if _state == UI_IDLE:
        return "尚未載入（未評估）"
    return None


def danger_clause(tile: Any) -> str | None:
    """指標危險度卡 → 子句內容（沿用卡面字樣：燈號＋`overall_verdict` 的說明）。"""
    _state = tile.card.state
    if _state == UI_LIVE:
        _detail = str(tile.card.value)
    elif _state == UI_PARTIAL:
        _detail = dict(tile.facts).get(today.DANGER_DETAIL_FACT_KEY, "")
    elif _state == UI_FAILED:
        return "讀取失敗（未評估）"
    elif _state == UI_IDLE:
        return "尚未載入（未評估）"
    else:
        return None
    _zh = str(tile.signal_text or "").strip()
    if not _detail:
        return _zh or None
    return f"{_zh}（{_detail}）" if _zh else _detail


def status_line(report: Any, danger: Any) -> str:
    """狀態列：更新時間（≠ 資料日）＋指標危險度覆蓋率（R8／R9）。"""
    _started = getattr(report, "started_at", None) if report is not None else None
    _time = (f"本頁更新於 {_started}（{REFRESH_TIME_NOTE}）" if _started
             else NO_REFRESH_YET)
    _cov = today.danger_completeness(danger) if danger is not None else None
    _cov_text = (f"指標危險度覆蓋：{_cov[0]}／{_cov[1]} 項有資料" if _cov is not None
                 else "指標危險度覆蓋：尚未載入")
    return f"{_time}｜{_cov_text}"


def _md_cell(text: Any) -> str:
    """表格儲存格：洗秘密＋跳脫 `|`、換行（避免把表格切壞）。"""
    return scrub_secrets(str(text)).replace("|", "／").replace("\n", " ")


def md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """純 Markdown 表格。"""
    _head = "| " + " | ".join(headers) + " |"
    _sep = "|" + "---|" * len(headers)
    _body = ["| " + " | ".join(_md_cell(_c) for _c in _r) + " |" for _r in rows]
    return "\n".join([_head, _sep, *_body])


# ══════════════════════════════════════════════════════════════════
# 渲染
# ══════════════════════════════════════════════════════════════════
def _render_plain_card(title: str, body: str, why: str = "") -> None:
    """不帶燈色、不帶狀態徽章的卡（趨勢兩卡、風險上限卡位用 —— Q2-2／Q3=A：只有文字）。"""
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.markdown(body)
        if why:
            st.caption(why)


def _render_raw_table(rows: Sequence[tuple[str, str, str]], *, empty_text: str) -> None:
    if not rows:
        st.caption(empty_text)
        return
    st.markdown(md_table(("項目", "原始值", "註記"), rows))


def _render_x1(session: Mapping[str, Any], regime: Mapping[str, Any] | None,
               regime_err: str, breadth_proxy: bool | None) -> None:
    """X1 市場位階：為什麼？—— 來源、健康分、信心度、缺哪些來源。⛔ 不顯示紅綠燈 label／action。"""
    _reg = dict(regime or {})
    if regime_err:
        st.error(f"市場位階契約讀不出來：`{scrub_secrets(regime_err)}`", icon="❌")
    _health = _reg.get("health")
    if _health is not None:
        _health_text = fmt_value(_health)
    elif today.regime_breadth_unevaluated(_reg):
        _health_text = f"未評估 —— {today.breadth_unevaluated_why(breadth_proxy)}"
    else:
        _health_text = "未評估（本輪沒有算出健康分）"
    _wr = session.get("warroom_summary") if isinstance(session, Mapping) else None
    _rows: list[tuple[str, str, str]] = [
        ("位階生效來源", fmt_value(_reg.get("source")), "契約自己的分支標記"),
        ("總經健康分", _health_text, ""),
        ("信心度", fmt_value(dig(_wr, ("confidence_pct",)), "%"), "紅綠燈資料來源的齊備程度"),
    ]
    _render_raw_table(_rows, empty_text="")
    # 缺哪些來源：與 L3 `warroom_apply` 同一支 `calc_traffic_light`、同一份輸入（只取 missing_sources）。
    try:
        from src.compute.macro.macro_helpers import calc_traffic_light
        from src.services.section_inputs import load_section_inputs
        _inp = load_section_inputs(session)
        if not _inp.mkt_info and not session.get("jingqi_info") and not _inp.cl_data:
            st.caption("缺哪些來源：尚未載入（本次使用中還沒有任何位階輸入）。")
            return
        _tl = calc_traffic_light(_inp.mkt_info or {}, _inp.jingqi_info or {},
                                 _inp.cl_data or {}, _inp.li_latest)
        _missing = list((_tl or {}).get("missing_sources") or [])
        st.markdown("**缺哪些來源**：" + ("、".join(_md_cell(_m) for _m in _missing)
                                       if _missing else "本輪沒有回報缺漏的來源"))
    except Exception as _e:  # noqa: BLE001 — 讀不出來就講出來（§1），⛔ 不畫成「沒有缺漏」
        print(f"[views/page_market] X1 缺漏來源清單算不出來：{_e!r}")
        st.error(f"缺哪些來源：算不出來（`{scrub_secrets(repr(_e))}`）", icon="❌")


def _render_frames_block(session: Mapping[str, Any], group: str, *, gate_key: str,
                         chart_label: str) -> None:
    _rows = frame_rows(session, group)
    st.caption(FRAME_SOURCE_NOTE[group])
    if not _rows:
        st.caption(f"{MISSING}：本次使用中還沒有這一組資料（請按上方更新）。")
        return
    st.markdown(md_table(("名稱", "最後收盤", "資料日", "筆數"), _rows))
    if st.checkbox(chart_label, key=gate_key):
        _grp = dig(session.get("cl_data"), (group,)) or {}
        for _name, _df in _grp.items():
            _cols = getattr(_df, "columns", None)
            _col = next((_c for _c in ("close", "Close") if _cols is not None and _c in _cols), None)
            if _col is None or getattr(_df, "empty", True):
                st.caption(f"{_name}：{MISSING}")
                continue
            st.markdown(f"**{_name}**（只畫走勢，不算燈）")
            st.line_chart(_df[_col].dropna())


def _render_x5(session: Mapping[str, Any]) -> None:
    _render_frames_block(session, "tw", gate_key=SS_GATE_TW_CHART,
                         chart_label="顯示加權指數／新台幣走勢圖")
    _render_raw_table(raw_rows(session, X5_FIELDS),
                      empty_text=f"{MISSING}：本次使用中還沒有市場評估輸入。")
    st.markdown("**市場廣度（ADL）**")
    st.caption(ADL_NOTE)
    if st.checkbox("顯示 ADL 逐日原始資料", key=SS_GATE_ADL):
        _adl = dig(session.get("cl_data"), ("adl",))
        if getattr(_adl, "empty", True) or getattr(_adl, "columns", None) is None:
            st.caption(f"{MISSING}：本次使用中沒有 ADL 資料。")
        else:
            st.dataframe(_adl.tail(20))


def _render_x6(session: Mapping[str, Any]) -> None:
    _render_frames_block(session, "intl", gate_key=SS_GATE_INTL_CHART,
                         chart_label="顯示國際指數／10 年債／美元走勢圖")
    st.markdown("**美股科技巨頭**")
    _tech = frame_rows(session, "tech")
    st.caption(FRAME_SOURCE_NOTE["tech"])
    if _tech:
        st.markdown(md_table(("名稱", "最後收盤", "資料日", "筆數"), _tech))
    else:
        st.caption(f"{MISSING}：本次使用中還沒有這一組資料。")
    _render_raw_table(raw_rows(session, X6_FIELDS), empty_text="")
    st.caption("全球資金流向、全球風險雷達本批未接到本頁（見「🌍 市場環境」舊分頁）；"
               "雙速合議、Risk-on／off 標籤、中國拖累不在本頁。")


def _render_x8(session: Mapping[str, Any]) -> None:
    st.markdown("**三大法人淨買賣超**")
    _render_raw_table(inst_rows(session), empty_text=f"{MISSING}：本次使用中還沒有法人資料。")
    _margin = dig(session.get("cl_data"), ("margin",))
    _margin_note = "融資燈門檻已失準；歷史單位混用區間屬資料疑義"
    if _margin is None and session.get("_last_margin") is not None:
        # §1：沿用上一次有效值時照實標出來，⛔ 不冒充本輪。
        _margin = session.get("_last_margin")
        _margin_note = "上一次有效值（本輪沒有）；" + _margin_note
    st.markdown(md_table(("項目", "原始值", "註記"), [(
        "融資餘額（大盤）",
        fmt_value(_margin if isinstance(_margin, (int, float)) else None, " 億"),
        _margin_note)]))
    st.markdown("**籌碼先行指標（逐日）**")
    if st.checkbox("顯示籌碼先行指標逐日原始資料", key=SS_GATE_LEADING):
        _li = session.get("li_latest")
        _cols = getattr(_li, "columns", None)
        if _cols is None or getattr(_li, "empty", True):
            st.caption(f"{MISSING}：本次使用中沒有先行指標資料。")
        else:
            _keep = [_c for _c, _ in LEADING_COLUMNS if _c in _cols]
            st.dataframe(_li[_keep])
            st.caption("　·　".join(f"{_c}：{_n}" for _c, _n in LEADING_COLUMNS if _n and _c in _keep))
    st.caption("外資連續買賣超天數、熱錢三角、融券本批未接到本頁。")


def _render_report_guarded(report: Any) -> None:
    """更新報告（與今天頁同一支）；舊格式畫不出來時講出來並清掉（同今天頁的處置）。"""
    try:
        today._render_refresh_report(report)
    except Exception as _e:  # noqa: BLE001 — 熱重載後的舊格式報告：紅字＋丟掉，⛔ 不靜默略過
        print(f"[views/page_market] 舊格式的更新報告畫不出來：{_e!r}")
        st.session_state.pop(today.SS_REFRESH_REPORT, None)
        st.error("上一次更新的報告畫不出來（多半是程式更新後留著舊格式的報告）。"
                 f"**它已經被清掉**，請重新按一次更新。原始例外：`{scrub_secrets(repr(_e))}`",
                 icon="⚠️")


def render_page_market() -> None:
    """📊 大盤（IA v2）。卡①～③、16 盞燈、今日關鍵、更新鈕都呼叫 `page_today` 的同一段程式。"""
    _session = st.session_state
    _session.pop(today.SS_V2_CSS_DONE, None)
    today._inject_v2_css()
    _readout = today.load_macro_readout(_session)
    _band_label, _thr_text, _band_zh, _l4_err = today._load_l4_labels()
    _alloc, _alloc_err = today._load_allocation()
    _regime, _regime_err = today._load_regime()
    _breadth_proxy = today._load_breadth_proxy()
    _danger, _danger_err, _danger_src = today._load_danger(_readout)
    _alerts, _scanned, _alerts_err = today._load_key_alerts(_session)
    _report = _session.get(today.SS_REFRESH_REPORT)
    try:
        _attempt = today.warroom_attempt(_report)
    except Exception as _e:  # noqa: BLE001 — 同今天頁：讀不出來就當沒有，log 出聲
        print(f"[views/page_market] 讀不出上一次更新的紅綠燈步驟：{_e!r} —— 當作沒有")
        _attempt = None

    # 卡①②③：與今天頁 `render_page_today()` 呼叫同一支、同一組引數。
    _exposure, _danger_tile, _regime_tile = today.build_verdict_tiles(
        alloc=_alloc, alloc_error=_alloc_err,
        danger=_danger, danger_error=_danger_err,
        danger_requested=_readout.requested, danger_source=_danger_src,
        regime=_regime, regime_error=_regime_err,
        band_zh_color=_band_zh, l4_error=_l4_err,
        macro_attempt=_attempt, breadth_proxy=_breadth_proxy)

    # ── 層 1：首屏 ───────────────────────────────────────────────
    st.markdown(f"## {ia_nav.page_label(ia_nav.PAGE_MARKET)}")
    st.caption(PAGE_QUESTION)
    st.markdown(status_line(_report, _danger))
    st.caption(f"{AS_OF_NOT_PROVIDED}｜🩺 資料健康：請到 "
               f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}")
    # 與今天頁同一支 form（⛔ 不另寫第二套更新流程）。form key 兩頁共用沒有衝突：側欄一次只選得到
    # 一頁（`app.py` 的 `_IA_PAGE` 分支＋`st.stop()`），兩頁不會出現在同一輪 script run。
    # 已套用模式與上一次的更新報告刻意共用 —— 按一次更新，兩頁看到的是同一份結果。
    today._render_update_form(_session)
    if _report is not None:
        _render_report_guarded(_report)

    section_header(CONCLUSION_HEADING)
    try:
        st.markdown(build_market_conclusion(regime_text=regime_clause(_regime_tile),
                                            danger_text=danger_clause(_danger_tile)))
    except ValueError as _e:  # §1：字樣不合規 ⇒ 講出來，⛔ 不自己改寫
        st.error(f"結論句組不出來：{_e}", icon="❌")

    # 今日關鍵警示（一行；與今天頁 ④ 同一支）。
    today._render_tiles((today.build_key_alert_tile(
        _alerts, requested=_readout.requested, threshold_scanned=_scanned,
        error=_alerts_err, band_zh_color=_band_zh),), cols=1)

    # 3 欄網格（窄螢幕由 Streamlit 自動改一欄，順序同下）。
    _r1 = st.columns(3)
    with _r1[0]:
        today._render_one(_regime_tile)
    with _r1[1]:
        _render_plain_card(CONCEPT_TW_TREND, TREND_UNDEFINED_TEXT, TREND_PENDING_WHY)
    with _r1[2]:
        _render_plain_card(CONCEPT_INTL_TREND, TREND_UNDEFINED_TEXT, TREND_PENDING_WHY)
    _r2 = st.columns(3)
    with _r2[0]:
        today._render_one(_danger_tile)
    with _r2[1]:
        _render_plain_card(CONCEPT_RISK_CAP, RISK_CAP_PENDING_TEXT)
    with _r2[2]:
        today._render_one(_exposure)

    # ── 層 2／3：可展開區（預設收合；重的部分勾選才畫）────────────────
    st.caption("以下為可展開區塊（預設收合）。")
    with st.expander("市場位階：為什麼？", expanded=False):
        _render_x1(_session, _regime, _regime_err, _breadth_proxy)
    with st.expander("指標危險度：為什麼？（五桶摘要）", expanded=False):
        today._render_tiles(today.build_bucket_tiles(_readout))
    with st.expander(X3_TITLE, expanded=False):
        st.markdown(X3_TEXT)
    with st.expander("指標明細（16 項）", expanded=False):
        _tiles_by_bucket = today.build_indicator_tiles(
            _readout, band_label=_band_label, thr_text=_thr_text, l4_error=_l4_err,
            directions=today._load_lamp_directions(_session))
        st.markdown(today.coverage(_tiles_by_bucket).text())
        st.caption(today.SEGMENT_COVERAGE_NOTE)
        st.caption(today.AS_OF_NOT_IN_CONTRACT)
        if _l4_err:
            st.warning(f"{today.L4_LABEL_UNAVAILABLE}`{scrub_secrets(_l4_err)}`", icon="⚠️")
        for _b in today.BUCKET_ORDER:
            _meta = today.BUCKET_META[_b]
            section_header(f"{_meta['emoji']} {_meta['title']}", str(_meta["sub"]))
            today._render_tiles(_tiles_by_bucket.get(_b, ()))
    with st.expander(f"台股盤勢（{RAW_DATA_SUFFIX}）", expanded=False):
        _render_x5(_session)
    with st.expander(f"國際市場（{RAW_DATA_SUFFIX}）", expanded=False):
        _render_x6(_session)
    with st.expander("總經／景氣（原始資料）", expanded=False):
        _render_raw_table(raw_rows(_session, X7_FIELDS),
                          empty_text=f"{MISSING}：本次使用中還沒有總經資料。")
        st.caption("景氣拐點六大面向本批未接到本頁。")
    with st.expander("籌碼（原始資料）", expanded=False):
        _render_x8(_session)
    with st.expander(X9_TITLE, expanded=False):
        st.markdown(X9_TEXT)
    with st.expander("資料來源與完整度", expanded=False):
        st.markdown(
            "- 本次更新的逐來源結果見上方「上一次更新的結果」（與「🚦 今天」頁同一份報告）。\n"
            f"- 各來源的健康狀態與根因：{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}。\n"
            "- ⚠️ 揭露：更新報告的「系統風險上限」步驟說明會列出本次寫檔的數值（現行行為，本批不改）。")
    with st.expander("問 AI／查看依據", expanded=False):
        st.markdown(f"AI 問答請到 {ia_nav.where_to_find(ia_nav.SECTION_WHY_QA)}"
                    "（沿用既有 AI 問答，本頁不另開一套）。")
