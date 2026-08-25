"""src/ui/tabs/tab_macro_v2.py — L5 總經 v2 分頁(位階評估 + 五桶)。

現行「🌍 總經」分頁把同一組數字重講很多次,而且畫面上「從沒亮過的燈」與
「正常的綠燈」長得一模一樣。本分頁用三層結構重新呈現**同一批資料**:

    第 1 層 · 結論     位階 verdict + 訊號可信度 + 五桶卡
    第 2 層 · 為什麼   有真實歷史序列的指標畫走勢 + 門檻線
    第 3 層 · 全部明細 16 盞燈總表,點任一列右側就地展開(不跳頁)

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
    Row,
    fmt_value,
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
    tbl, panel = st.columns([7, 5], gap="medium")

    with tbl:
        table = {
            "桶": [_BUCKET_ZH.get(r.bucket, r.bucket) for r in rows],
            "指標": [r.label for r in rows],
            "目前值": [fmt_value(r.value, r.unit, r.decimals) for r in rows],
            "燈": [BAND_META[r.band][0] for r in rows],
            "狀態": [
                {"live": "運作中", "degraded": "門檻已失準",
                 "unwired": "未接線", "missing": "無資料"}[r.state]
                for r in rows
            ],
            "門檻帶": [r.thr_text for r in rows],
        }
        sel = st.dataframe(
            table, hide_index=True, width='stretch',
            on_select="rerun", selection_mode="single-row",
            key="v2_detail_table",
        )

    with panel, st.container(border=True):
        idxs = (sel.selection.rows if sel and getattr(sel, "selection", None)
                else [])
        if idxs and 0 <= idxs[0] < len(rows):
            row = rows[idxs[0]]
            render_detail(row, SPECS_BY_KEY[row.key], edu=get_edu(row.key),
                          reason_text=_REASON_TXT.get(row.reason or "", ""))
        else:
            st.markdown("#### 點左表任一列")
            st.caption(
                "右側會就地展開該指標的完整資訊:目前值、門檻帶、命中來源、"
                "教學文案(門檻數字即時代入,不是抄的)、以及**為什麼這盞燈不能信**"
                "(未接線 / 門檻已失準的原因,直接讀自 SSOT)。"
            )
