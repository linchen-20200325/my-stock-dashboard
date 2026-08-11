"""src/ui/tabs/tab_sector_flow.py — 🌊 板塊資金潮汐分頁(L5 UI).

三大法人資金在產業間的流向泡泡圖。資料入口 = L3 `sector_flow_service`(它讀 L1 本地快取
reader + L2 持股→板塊對映),繪圖交 L4 `build_sector_flow_figure`。

§8.2 L5:只組裝、不直呼 L1 fetcher。本頁唯一資料入口是 L3 service;唯一 L1 觸點是
「讀 session_state 取 ETF 組合 ticker + 個股 sheet_id」——但那是**讀 UI 狀態**,不是抓資料,
且 gsheet 個股 watchlist 的實際抓取已下沉 L3(見 sector_flow_service docstring)。
§1:資料缺 / 過期 → st.info / st.warning 誠實訊息,不畫空圖冒充。
"""
from __future__ import annotations

try:
    import streamlit as st
except ImportError:            # 純 .py 測試環境:import 不炸
    st = None                  # noqa: N816


def _collect_etf_tickers(session_state) -> list[str]:
    """從 session_state['etf_portfolio_rows'](ETF 組合按「計算組合」後寫入)取 ticker。

    graceful:未載入 / 格式異常 → []。ticker 常帶 .TW/.TWO 後綴,由 L3 service 正規化。
    """
    rows = session_state.get("etf_portfolio_rows", []) or []
    if not isinstance(rows, list):
        return []
    return [str(r.get("ticker")).strip() for r in rows
            if isinstance(r, dict) and r.get("ticker")]


def render_tab_sector_flow() -> None:
    """🌊 板塊資金潮汐分頁主入口。"""
    if st is None:             # 無 streamlit(測試 import)→ no-op
        return

    st.markdown("### 🌊 板塊資金潮汐 — 三大法人資金在產業間的流向")
    st.caption(
        "X = 近 5 交易日累計淨流入(億)｜Y = 動能變化(近 5 日均 − 前 5 日均, 億/天)｜"
        "泡泡大小 = 近 20 交易日淨額規模(億)。資料由每交易日 GitHub Actions "
        "「Update Sector Flow」凍結,盤後更新。")

    # L5 只讀 UI 狀態(session_state),抓取全部交給 L3 service
    _etf_tickers = _collect_etf_tickers(st.session_state)
    _stock_sid = str(st.session_state.get("stock_portfolio_sheet_id", "") or "").strip() or None

    from src.services.sector_flow_service import get_sector_flow_view
    view = get_sector_flow_view(etf_tickers=_etf_tickers, stock_sheet_id=_stock_sid)

    # ── §1:資料缺 → 誠實訊息,不畫圖 ──────────────────────────────────
    if not view.get("ok"):
        st.info(
            f"📭 板塊資金資料尚未產生({view.get('reason', '缺快取')})——"
            "請先到 GitHub Actions 執行一次「Update Sector Flow」工作流程,"
            "盤後就會出現板塊資金泡泡圖。")
        return

    # ── §1:過期 → 誠實警示,但仍顯示最後一次成功快照 ─────────────────
    if view.get("is_stale"):
        st.warning(
            f"⚠️ 資料可能過期:上次更新 {view.get('meta_updated_at') or '未知'}"
            f"({view.get('stale_reason') or ''})。以下為最後一次成功凍結的快照。")

    _highlight = view.get("highlight_sectors") or set()
    from src.ui.render.sector_flow_render import build_sector_flow_figure
    fig = build_sector_flow_figure(view["sectors"], highlight_sectors=_highlight)
    st.plotly_chart(fig, use_container_width=True)

    # ── 持股板塊摘要 ─────────────────────────────────────────────────
    if _highlight:
        st.caption("⭐ 你的持股所在板塊:" + "、".join(sorted(_highlight)))
    else:
        st.caption(
            "（未偵測到持股所在板塊 —— 於「🏦 ETF」→「ETF 組合」按「計算組合」,"
            "或設定「🏆 個股組合」雲端清單後,本圖會用 ⭐ 金框標出你的持股板塊。）")

    # ── 資料不足板塊(不硬塞象限,只列名)─────────────────────────────
    _insuf = [str(s.get("sector")) for s in view["sectors"] if s.get("insufficient")]
    if _insuf:
        st.caption("🕓 資料不足(交易日 < 10,未列入象限):" + "、".join(_insuf))

    st.caption(
        f"📅 快取更新於 {view.get('updated_at') or '?'}｜"
        f"採 {view.get('n_trading_days_used') or '?'} 交易日｜"
        f"紅=漲潮 黃=輪動 藍=觀望 綠=退潮")
