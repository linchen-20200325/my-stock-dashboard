"""src/ui/tabs/tab_macro_v2.py — L5 總經 v2 分頁(位階評估 + 五桶)。

現行「🌍 總經」分頁把同一組數字重講很多次,而且畫面上「從沒亮過的燈」與
「正常的綠燈」長得一模一樣。本分頁用三層結構重新呈現**同一批資料**:

    第 1 層 · 結論     位階 verdict + 訊號可信度 + 五桶卡
    第 2 層 · 為什麼   有真實歷史序列的指標畫走勢 + 門檻線
    第 3 層 · 全部明細 16 盞燈總表(可搜尋 + 分類篩選),點任一列右側就地展開

⚠️ **範圍**(2026-08-25 user 核准):只做「位階評估 + 五桶」。
   戰情室 / 新聞 AI / 跨市場 AI / 短中長期分區仍在舊「🌍 總經」分頁,
   本頁**不重做**也**不取代**它們 —— 兩個分頁並排,舊版原封不動。

§3.3 反捏造 —— 本檔不維護任何指標名單、不寫死任何門檻:
  · 16 盞燈與門檻 ← `shared.macro_buckets.BUCKET_DANGER_SPECS`(L0 SSOT)
  · 判燈         ← `shared.macro_buckets.classify_danger`(用上游函式,不重寫)
  · 值 / 可信度   ← `compute_five_bucket_summary(readiness_out=...)` 側車
    **刻意走側車而不自己從 session_state 抽** —— 自己抽就會出現第二條取數
    路徑,必然與上游漂移。側車的 `value` 欄與 `wired`/`state` 同源同刻。

§1 Fail Loud —— 沒按更新鈕時 16 盞全部誠實顯示「無資料」,不代任何預設值;
  沒有落地歷史序列的指標**不畫圖**,改用純數值卡。

§8.2 分層 —— L5。取數走 L3 `services.section_inputs` + L2 `macro_helpers`,
  長歷史序列與教學文案走 L3 `services.macro_v2_service`(該層負責 cache —— parquet
  是 4,900+ 列,Streamlit 每次 rerun 重讀不可接受);渲染全部下放 L4
  `render.macro_v2_cards`。**本檔與 L4 都不直接 import 任何 L1 模組**(§8.2 R4)。
"""
from __future__ import annotations

import streamlit as st

from shared.macro_buckets import (
    BUCKET_DANGER_SPECS,
    MISSING_NO_EXTRACTION,
    MISSING_NO_VALUE,
    MISSING_NOT_LOADED,
    MISSING_OUT_OF_RANGE,
    SPECS_BY_KEY,
    classify_danger,
)
from src.compute.macro.macro_helpers import compute_five_bucket_summary
from src.services.macro_v2_service import get_chart_series, get_edu
from src.services.section_inputs import load_section_inputs
from src.ui.render.macro_v2_cards import (
    BAND_META,
    CSS,
    STATE_META,
    Row,
    fmt_value,
    print_table_html,
    render_bucket_cards,
    render_chart_card,
    render_detail,
    render_signal_health,
    render_value_card,
    threshold_text,
)

#: 桶 key → 中文名(對齊現行五桶用語)
_BUCKET_ZH = {
    "long": "長期", "mid": "中期", "short": "短線急殺",
    "chips": "籌碼", "news": "新聞",
}
_BUCKET_ORDER = ["long", "mid", "short", "chips", "news"]

#: state=missing 時給使用者的「該做什麼」。與資料看板同一組 MISSING_* 常數,
#: 文案在此獨立寫是因為兩處的語境不同(這裡是總經頁,那裡是診斷頁)。
_REASON_TXT = {
    MISSING_NOT_LOADED: "尚未載入 —— 到「🌍 總經」分頁按「🚀 一鍵更新全部數據」。",
    MISSING_NO_VALUE: "上游來源這輪沒有回值 —— 到「🔎 資料診斷」看 API 根因。",
    MISSING_OUT_OF_RANGE: "取到的值超出合理範圍,已被擋下 —— 通常是上游換了標的或報價慣例"
                          "(如 DXY→UUP、殖利率×10)。**不猜換算**,故顯示無資料。",
    MISSING_NO_EXTRACTION: "這盞燈的 spec 沒有對應的取值路徑 —— 這是程式 bug,不是資料問題。",
}

#: 有**落地長歷史序列**、可畫走勢的指標。
#: 名單來自 2026-08-25 對 16 盞燈的歷史資料盤點:只有這幾個有真序列。
#: `parquet` = 走 L1 `load_v2_chart_series`;`session` = 當輪抓取的記憶體內短窗。
_CHART_SPECS: list[tuple[str, str, str]] = [
    # (DangerSpec.key, 來源種類, 序列說明)
    ("bias_240", "parquet", "台股日線 2007 迄今,年線乖離由收盤價即時算出"),
    ("margin", "parquet", "融資餘額日資料 2006 迄今(原始單位元,此處已換算為億)"),
    ("us10y", "session", "本輪抓取的近 60 個交易日(即時取得,不落地)"),
]

#: 有值有燈、但**完全沒有歷史序列**可畫者 —— 顯示純數值卡。
#: VIX 是最典型的:天天在用,卻沒有任何落地序列。
_VALUE_CARD_KEYS: list[str] = ["vix"]

#: ── 第 3 層篩選 chip ──────────────────────────────────────────────────
#: 兩個**跨桶** chip 的 key;其餘 5 個 chip 的 key **就是桶 key 本身**。
_CHIP_ALL = "all"
_CHIP_PROBLEM = "problem"

#: chip key → 顯示名。5 個桶名一律**取自既有 `_BUCKET_ZH`**,不另寫一份中文
#: 字串 —— 兩份字串就是兩把尺,上游改桶名時必然有一邊沒跟上(§3.3)。
CHIP_LABELS: dict[str, str] = {
    _CHIP_ALL: "全部",
    _CHIP_PROBLEM: "只看有問題的",
    **{b: _BUCKET_ZH[b] for b in _BUCKET_ORDER},
}
#: chip 顯示順序。桶的先後同樣沿用 `_BUCKET_ORDER`,不在此另排一次。
CHIP_ORDER: list[str] = [_CHIP_ALL, _CHIP_PROBLEM, *_BUCKET_ORDER]


# ══════════════════════════════════════════════════════════════════════
# 組資料(無 st.* 副作用,純轉換)
# ══════════════════════════════════════════════════════════════════════

def build_rows(readiness: dict) -> list[Row]:
    """把 readiness 側車攤平成畫面用的列。

    值、可信度旗標、缺值原因全部來自側車 —— 本函式**不碰 session_state**,
    所以不存在第二條取數路徑。
    """
    out: list[Row] = []
    for spec in BUCKET_DANGER_SPECS:
        rec = readiness.get(spec.key, {})
        value = rec.get("value")
        # 判燈用上游 SSOT 函式,不自己重寫一套(§3.3)
        band = classify_danger(value, spec)

        if not rec.get("wired", True):
            state = "unwired"
        elif not rec.get("discriminative", True):
            state = "degraded"
        elif rec.get("state") == "ok" and value is not None:
            state = "live"
        else:
            state = "missing"

        out.append(Row(
            key=spec.key,
            label=spec.label,
            bucket=spec.bucket,
            unit=spec.unit or "",
            value=value,
            band=band,
            state=state,
            reason=rec.get("reason"),
            hit_source=rec.get("hit_source"),
            thr_text=threshold_text(spec),
            source=spec.source or "—",
            note=spec.note or "",
            decimals=spec.decimals,
        ))
    order = {b: i for i, b in enumerate(_BUCKET_ORDER)}
    out.sort(key=lambda r: (order.get(r.bucket, 99), r.label))
    return out


def bucket_summary(rows: list[Row]) -> list[dict]:
    """每桶:最差燈 + 指標數 + 不可信數。worst-of rollup,與現行五桶同語意。"""
    rank = {"green": 0, "yellow": 1, "red": 2, "gray": -1}
    out = []
    for bkey in _BUCKET_ORDER:
        members = [r for r in rows if r.bucket == bkey]
        if not members:
            continue
        graded = [r for r in members if r.band != "gray"]
        worst = max(graded, key=lambda r: rank[r.band]) if graded else None
        out.append({
            "name": _BUCKET_ZH.get(bkey, bkey),
            "band": worst.band if worst else "gray",
            "worst_label": worst.label if worst else "全部無資料",
            "worst_value": (fmt_value(worst.value, worst.unit, worst.decimals)
                            if worst else "—"),
            "n": len(members),
            "n_bad": sum(1 for r in members if r.state != "live"),
        })
    return out


def overall_verdict(summary: list[dict]) -> tuple[str, str]:
    """全域位階 = 五桶取最差(worst-of),與現行五桶 rollup 同語意。

    Returns: (band, 說明文字)
    """
    rank = {"green": 0, "yellow": 1, "red": 2}
    graded = [b for b in summary if b["band"] in rank]
    if not graded:
        return "gray", "尚未載入資料"
    worst = max(graded, key=lambda b: rank[b["band"]])
    n_red = sum(1 for b in graded if b["band"] == "red")
    n_yellow = sum(1 for b in graded if b["band"] == "yellow")
    bits = []
    if n_red:
        bits.append(f"{n_red} 桶紅")
    if n_yellow:
        bits.append(f"{n_yellow} 桶黃")
    detail = "、".join(bits) or "五桶全綠"
    return worst["band"], f"{detail}　·　最差是「{worst['name']}」"


# ══════════════════════════════════════════════════════════════════════
# 第 3 層 · 篩選(全部是純 Python,對**已經算好的 rows** 過濾,不重新取數)
#
# ⚠️ 效能:app.py 是 7 個頂層 `st.tabs`,每次 rerun **所有 tab body 都會執行**
#    (STATE.md 產業熱力圖冷抓事故)。所以篩選一律在記憶體內做,這一段
#    **不得**出現任何取數 / `@st.cache_data` / 網路呼叫。
# ══════════════════════════════════════════════════════════════════════

def is_problem(row: Row) -> bool:
    """「只看有問題的」的判定:**市場有問題 ∪ 系統有問題**(取聯集)。

        市場有問題 = 燈是黃或紅            → `band in {"yellow", "red"}`
        系統有問題 = 這盞燈不能信          → `state != "live"`
                     (未接線 / 無資料 / 門檻已失準)

    **為什麼取聯集,而不是只認黃紅燈**:本分頁存在的第一個理由,就是
    「從沒亮過的燈」與「正常的綠燈」在舊畫面上長得一模一樣。若「有問題」
    只認黃紅燈,使用者按下這個 chip 會看到一張很短的清單,然後合理推論
    「其他都沒事」—— 但其他之中有一部分**不是沒事,是根本沒在回報**。
    那正是本頁要消滅的誤解;把它做成預設篩選等於把 bug 產品化(§1:
    灰燈不是綠燈,沒有數字比錯的數字安全,但**假裝沒問題**兩者都輸)。

    **「未接線」算不算有問題**:算。它確實不是**市場**的問題,是**系統**的
    問題(決策端刻意沒接取值)。但這個 chip 的語意是「**還需要我看一眼的**」,
    不是「市場現在很糟」—— 一盞永遠不會亮的燈,正是最需要被看見的那種。
    想「只看市場黃紅燈」的人改點對應的桶 chip 即可,資訊沒有損失;
    反過來若把未接線藏起來,那個資訊在整頁上就再也沒有入口了。

    ⚠️ 本函式只做**分類**,判燈完全沿用上游 `classify_danger` 的結果,
    不重新判定任何門檻(§3.3;本次是純顯示層改動)。
    """
    return row.band in ("yellow", "red") or row.state != "live"


def filter_rows(rows: list[Row], *, chip: str = _CHIP_ALL,
                query: str = "") -> list[Row]:
    """第 3 層總表的篩選。`chip` 與 `query` 是 AND(先分類,再搜尋)。

    `query` 比對 `Row.label`(指標名稱),**不分大小寫、部分字串即命中**;
    空字串 / 純空白 → 不篩(顯示全部),不當成「查無此指標」。

    ⚠️ 只比對 `label`、不比對 `key`:key 是內部識別字(`ism_pmi` 之類),
    畫面上從不出現。拿它當搜尋目標會出現「打了看得見的字找不到、打了
    看不見的字反而找得到」這種無法解釋的行為。

    §1:未知的 `chip` 直接 `raise`。若默默回傳全部,畫面會長得跟「全部」
    一模一樣 —— 一個永遠不會被發現的 bug。
    """
    if chip not in CHIP_LABELS:
        raise ValueError(
            f"未知的篩選 chip:{chip!r}(可用:{list(CHIP_LABELS)})")
    out = list(rows)
    if chip == _CHIP_PROBLEM:
        out = [r for r in out if is_problem(r)]
    elif chip != _CHIP_ALL:          # 其餘 chip 的 key 就是桶 key
        out = [r for r in out if r.bucket == chip]
    q = query.strip().casefold()
    if q:
        out = [r for r in out if q in r.label.casefold()]
    return out


def _table_columns(visible: list[Row]) -> dict[str, list]:
    """`st.dataframe` 用的欄位 dict。**吃什麼就畫什麼**,不在此再篩一次。

    狀態中文字取自 L4 `STATE_META`(與訊號可信度卡同一份),不在本層再抄
    一份四態字串 —— 抄了就是第二把尺(§3.3)。
    """
    return {
        "桶": [_BUCKET_ZH.get(r.bucket, r.bucket) for r in visible],
        "指標": [r.label for r in visible],
        "目前值": [fmt_value(r.value, r.unit, r.decimals) for r in visible],
        "燈": [BAND_META[r.band][0] for r in visible],
        "狀態": [STATE_META[r.state][0] for r in visible],
        "門檻帶": [r.thr_text for r in visible],
    }


def visible_table(rows: list[Row], *, chip: str = _CHIP_ALL,
                  query: str = "") -> tuple[list[Row], dict[str, list]]:
    """回 `(畫面上的列, st.dataframe 的欄位)` —— **同一份、同一刻**。

    刻意把「篩選」與「組表」綁進同一個回傳值:兩者一旦拆成兩次呼叫,就
    有機會餵到不同的 list,而那正是「右側面板顯示另一個指標」的成因
    (見 `selected_row`)。綁在一起之後,那個錯誤在呼叫端寫不出來。
    """
    visible = filter_rows(rows, chip=chip, query=query)
    return visible, _table_columns(visible)


def selected_row(visible: list[Row], idxs) -> Row | None:
    """把 `st.dataframe` 回傳的選取列索引解析成 `Row`。

    ⚠️ **這是本頁最容易寫錯的一行。** `selection.rows` 給的是「**畫面上那
    張表的列序**」,不是 `build_rows()` 的原始 16 列序。一旦有了篩選,兩者
    就不再相等 —— 拿原始清單去索引,右側面板會顯示**另一個指標**的值、
    門檻與教學文案:畫面說 A、內容是 B,而且兩邊都看起來很正常(§1)。
    故本函式**只吃 `visible`**,也就是與 `st.dataframe` 同一份的那個 list。

    索引越界(改了篩選、舊選取殘留在 widget state)→ 回 `None`,由 caller
    顯示「請重新點一列」。**不回退到第 0 列** —— 那等於默默換一個指標給
    使用者看,正是本函式要防的那個錯。
    """
    if not idxs:
        return None
    try:
        i = int(idxs[0])
    except (TypeError, ValueError):
        return None
    if not 0 <= i < len(visible):
        return None
    return visible[i]


def empty_hint(*, chip: str, query: str, total: int) -> str:
    """篩選後 0 筆時的說明 —— §1:不留一張空表讓人以為頁面壞了。

    必須把**目前的篩選條件原樣講出來**:0 筆的原因永遠是「條件太窄」或
    「打錯字」,而使用者未必看得出自己選了什麼(chip 在表格上方、搜尋字
    可能只差一個字)。只寫「沒有資料」等於把原因藏起來。
    """
    bits = [f"分類「{CHIP_LABELS.get(chip, chip)}」"]
    q = query.strip()
    if q:
        bits.append(f"搜尋「{q}」")
    # 沒打搜尋字時不要叫人「清掉搜尋字」—— 那會讓人去找一個不存在的東西。
    fix = "清掉搜尋字或改選" if q else "改選"
    return (f"沒有符合的指標。目前篩選:{'、'.join(bits)}。"
            f"{fix}「{CHIP_LABELS[_CHIP_ALL]}」即可看回全部 {total} 盞燈。")


def print_caption(*, chip: str, query: str, shown: int, total: int) -> str:
    """列印版表格的抬頭 —— **必須把目前的篩選條件講出來**。

    §1:一張印出來只有 3 列的表,若沒寫「16 盞裡篩了 3 盞」,拿到紙本的人
    (含幾個月後的自己)會理所當然地以為總共只有 3 盞燈。螢幕上還有 chip
    與搜尋框可以看出自己篩了什麼,紙上**什麼都沒有** —— 所以條件要跟著印。
    """
    bits = [f"分類「{CHIP_LABELS.get(chip, chip)}」"]
    q = query.strip()
    if q:
        bits.append(f"搜尋「{q}」")
    return (f"第 3 層 · 全部明細 —— 顯示 {shown} / {total} 盞燈"
            f"({'、'.join(bits)})")


def _session_series(inputs, key: str):
    """從當輪抓取結果取記憶體內短窗序列。取不到回 (None, None)。

    §1:取不到就回 None 讓消費端顯示「歷史序列取得失敗」,不生成替代序列。
    """
    if key != "us10y":
        return None, None
    cl = getattr(inputs, "cl_data", None) or {}
    intl = cl.get("intl") if isinstance(cl, dict) else None
    if not isinstance(intl, dict):
        return None, None
    df = intl.get("10Y公債殖利率")
    try:
        if df is None or getattr(df, "empty", True):
            return None, None
        s = df["Close"] if "Close" in df.columns else df.iloc[:, 0]
        s = s.dropna()
        if s.empty:
            return None, None
        return list(s.index), [float(v) for v in s.tolist()]
    except Exception as e:  # noqa: BLE001 — 單張圖取不到不該讓整頁炸
        print(f"[tab_macro_v2/_session_series] {key} 取序列失敗:{e}")
        return None, None


# ══════════════════════════════════════════════════════════════════════
# 渲染
# ══════════════════════════════════════════════════════════════════════

def render_tab_macro_v2() -> None:
    """總經 v2 分頁進入點。由 app.py 的「🌍 市場環境」子分頁呼叫。"""
    st.markdown(CSS, unsafe_allow_html=True)

    inputs = load_section_inputs(st.session_state)
    readiness: dict = {}
    compute_five_bucket_summary(
        macro_info=inputs.macro_info, mkt_info=inputs.mkt_info,
        warroom_summary=inputs.warroom_summary, m1b_m2_info=inputs.m1b_m2_info,
        bias_info=inputs.bias_info, cl_data=inputs.cl_data,
        li_latest=inputs.li_latest, jingqi_info=inputs.jingqi_info,
        news_items=inputs.news_items,
        readiness_out=readiness,
    )
    rows = build_rows(readiness)
    summary = bucket_summary(rows)

    st.caption(
        "本頁與「🌍 總經」讀**同一份資料**(同一個 `compute_five_bucket_summary`),"
        "只是換一種呈現。要更新數字請到「🌍 總經」按「🚀 一鍵更新全部數據」。"
    )

    # ── 第 1 層 · 結論 ────────────────────────────────────────────────
    st.subheader("第 1 層 · 結論", divider="gray")
    left, right = st.columns([7, 5], gap="medium")

    band, detail = overall_verdict(summary)
    zh, color = BAND_META[band]
    with left, st.container(border=True):
        st.markdown('<p class="v2-t">總經位階</p>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="v2-hero" style="color:{color}">{zh}</div>',
            unsafe_allow_html=True)
        st.markdown(f'<p style="opacity:.75;margin-top:6px">{detail}</p>',
                    unsafe_allow_html=True)
        st.caption("五桶取最差(worst-of)—— 與現行總經頁同一套判定，不是另一套演算法。")
    with right, st.container(border=True):
        render_signal_health(rows)

    render_bucket_cards(summary)

    # ── 第 2 層 · 為什麼 ──────────────────────────────────────────────
    st.subheader("第 2 層 · 為什麼", divider="gray")
    st.caption(
        "只有**具備真實歷史序列**的指標才畫走勢。16 盞燈裡多數沒有落地序列"
        "(如 VIX、台灣 PMI),那些改用純數值卡 —— 不以合成資料充當走勢(§1)。"
    )

    by_key = {r.key: r for r in rows}
    # L3 取數(內含 @st.cache_data —— parquet 是 4,900+ 列,不能每次 rerun 重讀)
    parquet_series: dict = get_chart_series() if any(
        kind == "parquet" for _, kind, _ in _CHART_SPECS) else {}

    cards = [(k, kind, note) for k, kind, note in _CHART_SPECS if k in by_key]
    cols = st.columns(max(len(cards), 1), gap="medium")
    for col, (key, kind, note) in zip(cols, cards):
        row, spec = by_key[key], SPECS_BY_KEY[key]
        if kind == "parquet":
            pts = parquet_series.get(key) or []
            xs = [d for d, _ in pts]
            ys = [v for _, v in pts]
        else:
            xs, ys = _session_series(inputs, key)
            xs, ys = xs or [], ys or []
        with col:
            render_chart_card(row, spec, xs, ys, series_note=note)

    vcards = [k for k in _VALUE_CARD_KEYS if k in by_key]
    if vcards:
        vcols = st.columns(max(len(vcards), 1), gap="medium")
        for col, key in zip(vcols, vcards):
            with col:
                render_value_card(by_key[key], SPECS_BY_KEY[key])

    # ── 第 3 層 · 全部明細 ────────────────────────────────────────────
    st.subheader("第 3 層 · 全部明細", divider="gray")

    # 搜尋 + 分類 chip。**兩者都只做純 Python 篩選,不重新取數** —— app.py 是
    # 7 個頂層 `st.tabs`,每次 rerun 所有 tab body 都會執行,任何因篩選而觸發
    # 的取數都會被乘上 7(STATE.md 產業熱力圖冷抓事故)。
    #
    # ⚠️ widget 選型受 `requirements.txt` 的 floor 綁死:宣告是
    # `streamlit>=1.36.0`,故 `st.pills`(1.40+)/ `st.segmented_control`(1.42+)
    # / `st.fragment`(1.37+)**一律不得使用** —— 沙箱裝的是 1.61,測起來會過,
    # 部署端解析到 1.36 就直接 AttributeError。此處用 1.36 就有的
    # `st.text_input` + `st.radio(horizontal=True)`。
    fcol_q, fcol_chip = st.columns([4, 8], gap="medium")
    with fcol_q:
        query = st.text_input(
            "搜尋指標", value="", placeholder="搜尋指標… 例如 VIX、融資",
            label_visibility="collapsed", key="v2_detail_query",
        )
    with fcol_chip:
        chip = st.radio(
            "分類", CHIP_ORDER, index=0, horizontal=True,
            format_func=lambda c: CHIP_LABELS[c],
            label_visibility="collapsed", key="v2_detail_chip",
        )

    # 篩選 + 組表**同一次呼叫、同一份 list** —— 見 `selected_row` 的警告。
    visible, table = visible_table(rows, chip=chip, query=query)

    tbl, panel = st.columns([7, 5], gap="medium")

    with tbl:
        if visible:
            sel = st.dataframe(
                table, hide_index=True, width='stretch',
                on_select="rerun", selection_mode="single-row",
                key="v2_detail_table",
            )
        else:
            # §1:不留一張空表讓人以為頁面壞了,把目前的篩選條件講出來。
            sel = None
            st.warning(empty_hint(chip=chip, query=query, total=len(rows)))
        st.caption(f"顯示 {len(visible)} / {len(rows)} 盞燈")

        # ── 列印雙軌:螢幕看上面那張互動表,列印看這一份純 HTML 表 ──────
        # 為什麼一定要多畫一份:`st.dataframe` 走 glide-data-grid,整張表畫在
        # <canvas> 上而且**虛擬捲動** —— 捲出視窗的列根本不在 DOM 裡,列印時
        # 沒有東西可以被印出來。這是 CSS 救不了的,只能另外給一份真表格。
        #
        # **為什麼選「常駐隱藏」而不是加一顆「列印版」toggle**:
        #   · 使用者的動作就是直接按 Ctrl+P。toggle 只幫得到「知道要先去點
        #     那顆 toggle」的人;沒點就按 Ctrl+P 的人拿到的還是壞掉的輸出 ——
        #     那正是這次要修的那個 bug,等於沒修。
        #   · toggle 是一個 widget,切一次 = 一次 rerun = app.py 七個頂層 tab
        #     的 body 全部重跑(STATE.md v19.132 產業熱力圖冷抓事故的同一個
        #     性質)。常駐隱藏零互動、零 rerun。
        #   · 互動表與右側面板完全不動,既有的「面板顯示的就是表格那一列」
        #     守衛一行都不用改。
        #
        # **餵的是同一個 `table`**(= 上面 `st.dataframe` 吃的那一個 dict),
        # 不是重新篩一次 —— 兩張表要分岔,得先有人在這裡換掉這個變數。
        #
        # **跟著篩選走**:印出來的必須就是螢幕上看到的那幾列。若印全部 16 盞,
        # 同一頁的螢幕與紙本會說不一樣的話(§1);抬頭會把篩選條件寫進紙裡,
        # 所以「只有 3 列」不會被誤讀成「總共只有 3 盞燈」。想印全部 → 把
        # chip 切回「全部」再印,那是一次點擊。
        #
        # 螢幕代價:多一個 `display:none` 的元素容器,在這一欄底部留下一段
        # 約 1rem 的空白(Streamlit 垂直區塊是 flex + gap,零高度子元素仍佔一個
        # gap)。它在**欄位底部的空白區**,沒有任何內容因此位移。
        if visible:
            st.markdown(
                print_table_html(
                    table,
                    print_caption(chip=chip, query=query,
                                  shown=len(visible), total=len(rows)),
                ),
                unsafe_allow_html=True,
            )

    with panel, st.container(border=True):
        idxs = (sel.selection.rows if sel and getattr(sel, "selection", None)
                else [])
        # ⚠️ 一定要用 `visible`(= 畫面那張表)去解析,不是原始 `rows`。
        row = selected_row(visible, idxs)
        if row is not None:
            render_detail(row, SPECS_BY_KEY[row.key], edu=get_edu(row.key),
                          reason_text=_REASON_TXT.get(row.reason or "", ""))
        elif idxs:
            st.markdown("#### 選取已失效")
            st.caption(
                "剛才點的那一列已經不在目前的篩選結果裡。**這裡刻意不自動改選"
                "別列** —— 那會讓右側悄悄換成另一個指標,畫面說 A 內容是 B(§1)。"
                "請在左表重新點一列。"
            )
        else:
            st.markdown("#### 點左表任一列")
            st.caption(
                "右側會就地展開該指標的完整資訊:目前值、門檻帶、命中來源、"
                "教學文案(門檻數字即時代入,不是抄的)、以及**為什麼這盞燈不能信**"
                "(未接線 / 門檻已失準的原因,直接讀自 SSOT)。"
            )
