"""src/ui/tabs/caisen_targets_ui.py — 蔡森型態目標價計算機 UI(L5,v19.162→v19.163)。

user 需求:「由技術線型計算甜蜜價與目標價」+「接在個股/組合裡,套用當前標的」。
核心 `render_caisen_for_ticker(code, *, key_prefix)` 可重用元件:輸入代碼 → 抓 1y K 線 →
ZigZag 自動偵測擺動點 → 機械對映蔡森關鍵位 → 可手動微調 → compute_caisen_targets →
報告 + 線圖標點。三處共用(獨立分頁 / 個股 Tab / 個股組合 Tab),session key 以 key_prefix
隔離互不干擾。

§1 誠實:抓不到 K 線 → fail loud(不編假);演算法只抓「機械擺動點」,型態是否成立由 user
看圖確認,每個關鍵點都可手動覆寫。§8.2.A EX-PASSTHRU-1:lazy import L1 fetch_stock_history_1y。
計算走 L2 SSOT `src.compute.strategy.caisen_targets`,UI 不自算。
"""
from __future__ import annotations

import streamlit as st

_LEVEL_FIELDS = (
    ("support", "前低/支撐"),
    ("breakdown_low", "甩轎破底低"),
    ("wave1_start", "第一波起漲"),
    ("wave1_high", "第一波高/頸線"),
    ("consolidation_low", "整理拉回低"),
    ("neckline", "頸線/突破價"),
)
_PATTERNS = ("破底翻", "N字整理", "型態未明")


def _run_detect(code: str, pct: float, prefix: str) -> None:
    """抓 K 線 + ZigZag 偵測 + 對映關鍵位 → 存 session[prefix](button handler)。"""
    dkey = f"_{prefix}_data"
    if not code:
        st.session_state[dkey] = {"error": "請先提供股票代碼。"}
        return
    try:
        from src.data.stock.picker_fetcher import fetch_stock_history_1y  # EX-PASSTHRU-1
        df, resolved = fetch_stock_history_1y(code)
    except Exception as e:  # noqa: BLE001 — 抓取失敗不炸 UI
        st.session_state[dkey] = {"error": f"抓取失敗:{type(e).__name__}"}
        return
    if df is None or getattr(df, "empty", True) or "Close" not in getattr(df, "columns", []):
        st.session_state[dkey] = {
            "error": f"抓不到「{code}」的 K 線(Yahoo/FinMind 皆無回應)。§1:不編造假資料,請確認代碼或稍後再試。"}
        return

    from src.compute.strategy import detect_swings, derive_caisen_levels
    current_price = float(df["Close"].iloc[-1])
    swings = detect_swings(df["High"], df["Low"], pct=pct)
    levels = derive_caisen_levels(swings, current_price)

    st.session_state[dkey] = {
        "df": df, "swings": swings, "levels": levels,
        "current_price": current_price, "resolved": resolved or code, "code": code, "pct": pct,
    }
    seed = levels or {}
    for field, _ in _LEVEL_FIELDS:
        v = seed.get(field)
        st.session_state[f"_{prefix}_ov_{field}"] = round(float(v), 2) if v is not None else round(current_price, 2)
    st.session_state[f"_{prefix}_ov_pattern"] = seed.get("pattern", "型態未明")


def _fnum(x, dash: str = "—") -> str:
    return f"{x:.2f}" if isinstance(x, (int, float)) else dash


def _render_report(r: dict, current_price: float) -> None:
    sweet, stop = r.get("sweet"), r.get("stop")
    t1, t2 = r.get("target1"), r.get("target2")
    rr = r.get("rr")
    pattern = r.get("pattern", "型態未明")

    st.markdown(f"#### 📋 蔡森分析報告　`型態:{pattern}`　`現價:{current_price:.2f}`")
    a, b, c = st.columns(3)
    a.metric("🎯 甜蜜價(進場)", _fnum(sweet),
             help=f"區間 {_fnum(r.get('sweet_low'))} ~ {_fnum(r.get('sweet_high'))}(量縮拉回踩頸線不破更甜)")
    b.metric("🛡️ 止損價", _fnum(stop),
             help="破底翻→破底低下方;突破/N字→整理低或頸線下方,跌破型態失效")
    _rr_ok = isinstance(rr, (int, float)) and rr >= 2
    c.metric("⚖️ 風報比", f"{rr:.2f}" if isinstance(rr, (int, float)) else "—",
             delta=("划算(>2)" if _rr_ok else "偏低(<2)") if isinstance(rr, (int, float)) else None,
             delta_color="normal" if _rr_ok else "inverse")

    st.markdown(
        f"🚀 **目標價(等幅滿足)**：第一波 **{_fnum(t1)}**"
        + (f"（N字 {_fnum(r.get('target_n'))} / 底型 {_fnum(r.get('target_box'))}）" if r.get("target_n") is not None
           else f"（底型 {_fnum(r.get('target_box'))}）")
        + (f"　｜　第二波(強勢) **{_fnum(t2)}**" if t2 is not None else "")
    )

    if pattern == "破底翻":
        tip = "破底翻要**站回支撐/頸線且帶量**才算數;停損貼破底低,跌破＝甩轎失敗。到第一波滿足先減碼。"
    elif pattern == "N字整理":
        tip = "N 字須**帶量突破第一波高**才確認;拉回踩頸線要**量縮**才是好洗盤,量放大下殺別接。跌破整理低型態失效。"
    else:
        tip = "型態未明:擺動點不足或非典型,請自行看圖確認關鍵點後再參考數字。"
    st.info(f"💡 **專家叮嚀**：{tip}　量價配合是蔡森核心 —— **突破必帶量、拉回宜量縮**。")
    if isinstance(rr, (int, float)) and rr < 2:
        st.caption("⚠️ 風報比 < 2:賺賠不划算。可等更甜的進場(貼近整理低)或放棄這筆。")


def _render_chart(data: dict, r: dict, chart_key: str) -> None:
    import plotly.graph_objects as go
    df = data["df"]
    swings = data["swings"] or []
    idx = df.index

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=idx, y=df["Close"], name="收盤", line=dict(color="#58a6ff", width=1.5)))
    hi_x, hi_y, lo_x, lo_y = [], [], [], []
    for s in swings:
        i = s.get("idx")
        if i is None or i >= len(idx):
            continue
        (hi_x if s.get("kind") == "high" else lo_x).append(idx[i])
        (hi_y if s.get("kind") == "high" else lo_y).append(s["price"])
    if hi_x:
        fig.add_trace(go.Scatter(x=hi_x, y=hi_y, mode="markers", name="擺動高",
                                 marker=dict(symbol="triangle-down", size=10, color="#ef4444")))
    if lo_x:
        fig.add_trace(go.Scatter(x=lo_x, y=lo_y, mode="markers", name="擺動低",
                                 marker=dict(symbol="triangle-up", size=10, color="#3fb950")))
    for val, txt, color, dash in (
        (r.get("sweet"), "甜蜜價", "#58a6ff", "solid"),
        (r.get("stop"), "止損", "#ef4444", "dash"),
        (r.get("target1"), "目標①", "#3fb950", "solid"),
        (r.get("target2"), "目標②", "#3fb950", "dot"),
    ):
        if isinstance(val, (int, float)):
            fig.add_hline(y=val, line=dict(color=color, dash=dash, width=1),
                          annotation_text=f"{txt} {val:.1f}", annotation_position="right")
    fig.update_layout(height=380, margin=dict(l=8, r=8, t=8, b=8), template="plotly_dark",
                      showlegend=True, legend=dict(orientation="h", y=1.02, x=0))
    st.plotly_chart(fig, use_container_width=True, key=f"_cs_chart_{chart_key}")


def render_caisen_for_ticker(code: str, *, key_prefix: str = "cs", default_pct: int = 8) -> None:
    """可重用核心:對單一代碼跑蔡森型態目標價分析(自動偵測 + 可手動覆寫)。

    key_prefix 隔離 session(獨立分頁 / 個股 / 組合 三處共用不衝突)。
    """
    st.caption("⚠️ **演算法推導,非型態判定**：系統只機械抓「擺動轉折點」，型態是否成立請自行看圖確認，"
               "並可下方**手動微調每個關鍵點**。僅供研究，風險自負。")
    prefix = key_prefix
    code = (code or "").strip()

    cc1, cc2 = st.columns([3, 1.3])
    pct = cc1.slider("ZigZag 靈敏度（反轉 %）", 3, 15, default_pct, key=f"_{prefix}_pct",
                     help="越小抓越多小轉折;越大只抓大波段。") / 100.0
    cc2.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    if cc2.button(f"🔍 抓 K 線並計算（{code or '—'}）", type="primary",
                  use_container_width=True, key=f"_{prefix}_go", disabled=not code):
        _run_detect(code, pct, prefix)

    data = st.session_state.get(f"_{prefix}_data")
    if not data:
        st.info(f"👆 按「抓 K 線並計算」，系統會抓 **{code or '該標的'}** 近一年 K 線並偵測型態關鍵點。")
        return
    if data.get("error"):
        st.error(f"🔴 {data['error']}")
        return

    current_price = data["current_price"]
    levels = data.get("levels")
    from src.config.stock_names import get_stock_name
    _name = get_stock_name(data["code"])
    st.success(f"✅ {data['code']} {_name}（{data['resolved']}）　現價 {current_price:.2f}　"
               f"偵測 {len(data['swings'] or [])} 擺動點　自動判型：**{(levels or {}).get('pattern', '型態未明')}**")
    if not levels:
        st.warning("擺動點不足以對映關鍵位（可調低靈敏度或換波動較明確的）。下方仍可手動輸入計算。")

    with st.expander("✏️ 型態關鍵點（自動偵測值，可手動微調覆寫）", expanded=True):
        cols = st.columns(3)
        for i, (field, label) in enumerate(_LEVEL_FIELDS):
            cols[i % 3].number_input(label, key=f"_{prefix}_ov_{field}", step=0.1, format="%.2f")
        st.selectbox("型態（影響止損邏輯）", _PATTERNS, key=f"_{prefix}_ov_pattern",
                     help="破底翻→止損貼破底低(較寬);N字→止損貼整理低/頸線(較緊)")

    from src.compute.strategy import compute_caisen_targets
    r = compute_caisen_targets(
        pattern=st.session_state.get(f"_{prefix}_ov_pattern", "型態未明"),
        support=st.session_state.get(f"_{prefix}_ov_support"),
        breakdown_low=st.session_state.get(f"_{prefix}_ov_breakdown_low"),
        wave1_start=st.session_state.get(f"_{prefix}_ov_wave1_start"),
        wave1_high=st.session_state.get(f"_{prefix}_ov_wave1_high"),
        consolidation_low=st.session_state.get(f"_{prefix}_ov_consolidation_low"),
        neckline=st.session_state.get(f"_{prefix}_ov_neckline"),
        current_price=current_price,
    )
    _render_report(r, current_price)
    _render_chart(data, r, prefix)
    with st.expander("🔬 計算軌跡（notes：用了哪條公式、缺哪些值）", expanded=False):
        for n in r.get("notes", []):
            st.caption(f"• {n}")


def render_caisen_targets_tab() -> None:
    """獨立分頁:自行輸入代碼 → 蔡森型態目標價分析。"""
    st.markdown("## 🎯 蔡森型態目標價計算機")
    st.caption("由技術線型(ZigZag 擺動點)**自動偵測**破底低/起漲/波高/整理低/頸線 → 算 甜蜜價·止損·目標·風報比。")
    code = st.text_input("股票代碼", value="2330", key="_cstab_code")
    render_caisen_for_ticker((code or "").strip(), key_prefix="cstab")
