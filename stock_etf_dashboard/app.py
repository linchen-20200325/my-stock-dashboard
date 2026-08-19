"""L3 UI — Stock & ETF 智慧投資儀表板（Streamlit）。

佈局：頂部總經風控列 + 左右雙池工作區（觀察池｜持股組合）+ 側欄行動中心。
執行：`streamlit run stock_etf_dashboard/app.py`

本層只呼叫 L2 services / L1 repositories，不自行運算（§8.2 分層）。
所有外部抓取 button-gated 且 Fail Loud：失敗以 st.error 顯示，絕不捏造資料。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 讓 `streamlit run` 時能 import 到套件（script 目錄為套件內,需補上父層）
_PARENT = Path(__file__).resolve().parent.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

from datetime import date  # noqa: E402

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from stock_etf_dashboard.core import constants as C  # noqa: E402
from stock_etf_dashboard.core.circuit_breaker import FailLoudError  # noqa: E402
from stock_etf_dashboard.core.line_dispatcher import send_line_message  # noqa: E402
from stock_etf_dashboard.repositories import chip_repo, market_repo  # noqa: E402
from stock_etf_dashboard.repositories.sheets_repo import (  # noqa: E402
    GoogleSheetsStore, InMemoryStore)
from stock_etf_dashboard.services import etf_overlap_calc as ov  # noqa: E402
from stock_etf_dashboard.services import exposure_service as exs  # noqa: E402
from stock_etf_dashboard.services import stock_scoring_engine as se  # noqa: E402
from stock_etf_dashboard.services.pool_state_service import (  # noqa: E402
    PoolStateService, check_exit)

st.set_page_config(page_title="Stock & ETF 智慧投資儀表板",
                   page_icon="📈", layout="wide")


# ── 狀態初始化 ──────────────────────────────────────────────────────────
def _get_store():
    if "store" not in st.session_state:
        st.session_state.store = _build_store()
    return st.session_state.store


def _build_store():
    """優先用部署端 Google Sheets（st.secrets），否則記憶體後端（可即開即用）。"""
    try:
        gcfg = st.secrets.get("gsheets", {})
        sheet_id = gcfg.get("sheet_id")
        creds = gcfg.get("service_account")
        if sheet_id and creds:
            return GoogleSheetsStore.from_service_account(sheet_id, dict(creds))
    except Exception as e:  # noqa: BLE001 - 連不上就退記憶體,並在側欄告知
        st.session_state["_store_err"] = str(e)
    return InMemoryStore()


def _svc() -> PoolStateService:
    return PoolStateService(_get_store())


# ── 頂部總經風控列 ──────────────────────────────────────────────────────
def render_risk_bar():
    st.markdown("### 📊 總經風控列")
    c1, c2, c3, c4 = st.columns(4)
    fetch = st.session_state.get("_risk_snapshot")
    if c1.button("🔄 更新總經", use_container_width=True):
        st.session_state["_risk_snapshot"] = _fetch_macro_snapshot()
        fetch = st.session_state["_risk_snapshot"]
    if not fetch:
        c2.metric("大盤 vs 年線", "—"); c3.metric("VIX", "—")
        c4.metric("投組集中警戒", _portfolio_alert_count())
        st.caption("點『更新總經』抓取 ^TWII / ^VIX（button-gated，避免每次 rerun 都打網路）")
        return
    c2.metric("大盤 vs 年線", fetch["twii_vs_ma"], fetch["twii_note"])
    c3.metric("VIX 恐慌", fetch["vix"])
    c4.metric("投組集中警戒", _portfolio_alert_count())


def _fetch_macro_snapshot() -> dict:
    out = {"twii_vs_ma": "—", "twii_note": "", "vix": "—"}
    try:
        twii = market_repo.fetch_ohlcv("^TWII", period="2y", auto_adjust=True)
        last = float(twii["close"].iloc[-1])
        ma = float(twii["close"].rolling(240).mean().iloc[-1])
        out["twii_vs_ma"] = "站上" if last > ma else "跌破"
        out["twii_note"] = f"{last:.0f} / MA240 {ma:.0f}"
    except (FailLoudError, Exception) as e:  # noqa: BLE001
        out["twii_note"] = f"抓取失敗：{e}"
    try:
        vix = market_repo.fetch_ohlcv("^VIX", period="1mo", auto_adjust=True)
        out["vix"] = f"{float(vix['close'].iloc[-1]):.1f}"
    except (FailLoudError, Exception):  # noqa: BLE001
        out["vix"] = "抓取失敗"
    return out


def _portfolio_alert_count() -> str:
    rep = st.session_state.get("_exposure_report")
    if not rep:
        return "未計算"
    return f"{len(rep.alerts)} 檔超標" if rep.alerts else "無"


# ── 左欄：觀察池 ────────────────────────────────────────────────────────
def render_watchlist():
    st.subheader("👀 觀察池 Watchlist")
    store = _get_store()
    with st.form("add_watch", clear_on_submit=True):
        cols = st.columns([2, 2, 1])
        tk = cols[0].text_input("代碼", placeholder="2330.TW")
        nm = cols[1].text_input("名稱", placeholder="台積電")
        if cols[2].form_submit_button("➕ 加入") and tk:
            try:
                _svc().add_to_watchlist(tk, name=nm)
                st.success(f"{tk} 已加入觀察池")
            except FailLoudError as e:
                st.error(str(e))

    rows = store.list_watchlist()
    if not rows:
        st.info("觀察池為空。加入代碼後可跑評分、確認進場。")
        return
    for r in rows:
        tk = r.get("ticker", "")
        with st.expander(f"🔎 {tk} {r.get('name','')}", expanded=False):
            if st.button("跑量化評分", key=f"score_{tk}"):
                _render_score(tk)
            _render_buy_form(tk)


def _render_score(ticker: str):
    try:
        ohlcv = market_repo.fetch_ohlcv(ticker, period="2y")
        val = market_repo.fetch_valuation(ticker, ohlcv)
        try:
            chip = chip_repo.fetch_chip_history(ticker, days=20)
        except FailLoudError:
            chip = None
        sc = se.score_stock(ticker, ohlcv, valuation=val, chip=chip, as_of=date.today())
    except (FailLoudError, Exception) as e:  # noqa: BLE001
        st.error(f"{ticker} 評分失敗（Fail Loud，不捏造）：{e}")
        return
    st.session_state[f"_conf_{ticker}"] = sc.confidence.score
    m = st.columns(4)
    m[0].metric("綜合分", f"{sc.total_score:.0f}")
    m[1].metric("估值", sc.valuation.zone if sc.valuation else "N/A")
    m[2].metric("技術", sc.trend.label)
    m[3].metric("籌碼", sc.chip.label)
    st.progress(min(1.0, sc.total_score / 100.0))
    (st.warning if sc.confidence.is_locked else st.info)(
        f"{sc.confidence.as_badge()}｜{sc.verdict}")


def _render_buy_form(ticker: str):
    conf = st.session_state.get(f"_conf_{ticker}")
    with st.form(f"buy_{ticker}", clear_on_submit=True):
        cc = st.columns([1, 1, 1, 1])
        lots = cc[0].number_input("張數", min_value=1.0, step=1.0, key=f"bl_{ticker}")
        price = cc[1].number_input("買入價", min_value=0.01, step=0.5, key=f"bp_{ticker}")
        ts = cc[2].number_input("移動停損%", value=C.DEFAULT_TRAILING_STOP_PCT, key=f"bts_{ticker}")
        tp = cc[3].number_input("停利%", value=C.DEFAULT_TAKE_PROFIT_PCT, key=f"btp_{ticker}")
        submitted = st.form_submit_button("✅ 確認買入 → 移入持股")
    if submitted:
        if conf is None:
            st.error("請先『跑量化評分』取得置信度，再確認買入（confidence gate）")
            return
        try:
            r = _svc().confirm_buy(ticker, lots=lots, price=price,
                                   confidence_score=conf,
                                   trailing_stop_pct=ts, take_profit_pct=tp)
            st.success(r.message)
            st.rerun()
        except FailLoudError as e:
            st.error(str(e))


# ── 右欄：持股組合 ──────────────────────────────────────────────────────
def render_portfolio():
    st.subheader("💼 持股組合 Portfolio")
    store = _get_store()
    rows = store.list_holdings()
    if not rows:
        st.info("尚無持股。於左側觀察池『確認買入』後標的會移到這裡。")
        return
    for r in rows:
        tk = r.get("ticker", "")
        with st.expander(f"📌 {tk} {r.get('name','')}｜{r.get('lots')} 張 @ {r.get('avg_price')}",
                         expanded=True):
            cc = st.columns(3)
            cc0 = cc[0]
            cc0.metric("成本", r.get("avg_price"))
            cc[1].metric("移動停損%", r.get("trailing_stop_pct"))
            cc[2].metric("停利%", r.get("take_profit_pct"))
            if st.button("檢查出場訊號", key=f"exit_{tk}"):
                _render_exit_check(r)
            _render_sell_form(r)


def _render_exit_check(holding: dict):
    tk = holding.get("ticker", "")
    try:
        ohlcv = market_repo.fetch_ohlcv(tk, period="1y", auto_adjust=False)
        div = market_repo.fetch_dividends(tk)
    except (FailLoudError, Exception) as e:  # noqa: BLE001
        st.error(f"{tk} 出場檢查失敗：{e}")
        return
    entry = float(holding.get("avg_price"))
    hwm = float(ohlcv["close"].max())
    last = ohlcv.iloc[-1]
    prev_close = float(ohlcv["close"].iloc[-2]) if len(ohlcv) >= 2 else float(last["open"])
    # 當日若為除息日，取當日配息額
    div_amt = 0.0
    if len(div) > 0:
        last_day = pd.to_datetime(last["date"]).normalize()
        hit = div[pd.to_datetime(pd.Series(div.index)).dt.normalize().values == last_day]
        div_amt = float(hit.iloc[0]) if len(hit) else 0.0
    sig = check_exit(
        avg_price=entry, high_watermark=hwm,
        trailing_stop_pct=float(holding.get("trailing_stop_pct", C.DEFAULT_TRAILING_STOP_PCT)),
        take_profit_pct=float(holding.get("take_profit_pct", C.DEFAULT_TAKE_PROFIT_PCT)),
        prev_close=prev_close, today_open=float(last["open"]),
        today_low=float(last["low"]), today_high=float(last["high"]),
        dividend_amount=div_amt,
    )
    (st.error if (sig.stop_triggered or sig.take_triggered) else st.info)(sig.suggestion)
    st.caption(f"停損線 {sig.stop_price}｜停利線 {sig.take_price}｜{sig.guard.note}")


def _render_sell_form(holding: dict):
    tk = holding.get("ticker", "")
    held = float(holding.get("lots", 0))
    with st.form(f"sell_{tk}", clear_on_submit=True):
        cc = st.columns([1, 1, 1])
        lots = cc[0].number_input("賣出張數", min_value=1.0, max_value=held,
                                  step=1.0, key=f"sl_{tk}")
        price = cc[1].number_input("賣出價", min_value=0.01, step=0.5, key=f"sp_{tk}")
        back = cc[2].checkbox("退回觀察池", value=True, key=f"sb_{tk}")
        submitted = st.form_submit_button("🔻 確認賣出")
    if submitted:
        try:
            r = _svc().confirm_sell(tk, lots=lots, price=price, back_to_watchlist=back)
            st.success(r.message)
            st.rerun()
        except FailLoudError as e:
            st.error(str(e))


# ── 穿透曝險總覽 ────────────────────────────────────────────────────────
def _render_exposure_report(rep):
    """共用：把 ExposureReport 畫成表 + 警戒。"""
    (st.success if rep.is_complete else st.warning)(rep.note)
    df = pd.DataFrame([{
        "標的": r.name, "曝險%": r.exposure_pct, "市值": r.market_value,
        "直接": r.via_direct, "ETF穿透": r.via_etf,
        "警戒": "⚠️" if r.breach else ""} for r in rep.rows])
    st.dataframe(df, use_container_width=True, hide_index=True)
    if rep.alerts:
        st.error(f"🚨 集中度超標：{', '.join(rep.alerts)}（>"
                 f"{C.SINGLE_NAME_EXPOSURE_ALERT_PCT:.0f}%）")


def render_exposure():
    st.subheader("🔬 ETF 成分穿透 × 重疊曝險")
    st.caption("直接持股 + ETF 內含成分穿透到底層標的（去重複計數）；"
               f"單一標的 > {C.SINGLE_NAME_EXPOSURE_ALERT_PCT:.0f}% 觸發集中度警戒。")

    # ── 自動穿透：讀「我的持股」→ 真實抓 ETF 成分 ──────────────────────
    st.markdown("**🔓 從我的持股自動穿透**（讀持股組合 → yfinance 抓 ETF 成分）")
    if st.button("計算我的持股穿透曝險"):
        try:
            res = exs.build_portfolio_exposure(_get_store())
        except (FailLoudError, Exception) as e:  # noqa: BLE001
            st.error(f"自動穿透失敗（Fail Loud，不捏造）：{e}")
        else:
            st.session_state["_exposure_report"] = res.report
            st.caption(f"納入 {len(res.priced)} 檔（ETF {len(res.etf_tickers)} 檔）"
                       f"｜總市值 {res.report.total_value:,.0f}")
            if res.skipped_no_price:
                st.warning("無現價被跳過（未捏造市值）："
                           + "、".join(x["ticker"] for x in res.skipped_no_price))
            _render_exposure_report(res.report)
    st.caption("💡 台股 ETF 成分在部署端才抓得到（沙箱代理擋 yfinance）；"
               "抓不到的 ETF 會標『成分未知』並把曝險列為下限。")

    st.divider()
    st.markdown("**✍️ 手動輸入試算**（免抓取，驗證穿透邏輯用）")
    cold, cole = st.columns(2)
    direct_txt = cold.text_area("直接持股（代碼,市值 每行一筆）",
                                "2330,300000", height=120)
    etf_txt = cole.text_area("ETF（代碼,市值,成分JSON 每行一筆）",
                             '0050,700000,{"2330":47,"2317":4.5,"2454":3}', height=120)
    if st.button("計算穿透曝險"):
        try:
            direct = _parse_direct(direct_txt)
            etfs = _parse_etf(etf_txt)
            rep = ov.compute_penetrated_exposure(direct, etfs)
        except (FailLoudError, Exception) as e:  # noqa: BLE001
            st.error(f"穿透計算失敗：{e}")
            return
        st.session_state["_exposure_report"] = rep
        _render_exposure_report(rep)


def _parse_direct(txt: str) -> list[dict]:
    out = []
    for line in txt.strip().splitlines():
        if not line.strip():
            continue
        code, mv = [x.strip() for x in line.split(",")[:2]]
        out.append({"ticker": code, "market_value": float(mv)})
    return out


def _parse_etf(txt: str) -> list[dict]:
    import json
    out = []
    for line in txt.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split(",", 2)
        code, mv = parts[0].strip(), float(parts[1].strip())
        holdings = json.loads(parts[2]) if len(parts) > 2 and parts[2].strip() else None
        out.append({"ticker": code, "market_value": mv, "holdings": holdings})
    return out


# ── 側欄行動中心 ────────────────────────────────────────────────────────
def render_action_center():
    st.sidebar.title("🎛️ 行動中心")
    store = _get_store()
    backend = type(store).__name__
    st.sidebar.caption(f"儲存後端：**{backend}**")
    if "_store_err" in st.session_state:
        st.sidebar.warning(f"Sheets 連線退回記憶體：{st.session_state['_store_err']}")
    if backend == "InMemoryStore":
        st.sidebar.info("目前為記憶體模式（重整即清空）。部署端於 secrets 設定 "
                        "[gsheets].sheet_id + service_account 可持久化。")

    st.sidebar.divider()
    st.sidebar.subheader("📒 交易帳本")
    ledgers = store.list_ledgers()
    if ledgers:
        st.sidebar.dataframe(pd.DataFrame(ledgers), use_container_width=True,
                             hide_index=True)
    else:
        st.sidebar.caption("尚無交易紀錄。")

    st.sidebar.divider()
    st.sidebar.subheader("🔔 LINE 推播測試")
    msg = st.sidebar.text_input("訊息", "儀表板測試推播")
    if st.sidebar.button("推播"):
        try:
            send_line_message(msg)
            st.sidebar.success("已推播")
        except FailLoudError as e:
            st.sidebar.error(str(e))


# ── 主佈局 ──────────────────────────────────────────────────────────────
def main():
    st.title("📈 Stock & ETF 智慧投資儀表板")
    render_risk_bar()
    st.divider()
    left, right = st.columns(2, gap="large")
    with left:
        render_watchlist()
    with right:
        render_portfolio()
    st.divider()
    render_exposure()
    render_action_center()


if __name__ == "__main__":
    main()
