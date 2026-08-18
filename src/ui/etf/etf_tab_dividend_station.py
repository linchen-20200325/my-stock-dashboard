"""L5 UI — 💼 我的持股戰情室（個股 + ETF 統一分析,掛在 🏦 ETF）。

以息養股 / 3-3-3 挑三 / 235 加碼。逐檔（個股+ETF）跑健檢 + 235 燈 + 3-3-3,顏色高亮、
隱藏開高低收。§8.2 L5：只呼叫 L3 `dividend_station_service`,不自算。§1：抓取失敗
逐列誠實標記,不炸整表。抓取 button-gated（不每次 rerun 重抓）。
個股：D折溢價 / 3-3-3 標「—」不適用（§1 不硬套 ETF 規則）。
"""
from __future__ import annotations

import streamlit as st

from shared import dividend_station_thresholds as T

_CLASS_OPTIONS = ["核心", "衛星"]
_CLASS_MAP = {"核心": T.ASSET_CORE, "衛星": T.ASSET_SATELLITE}
_KIND_OPTIONS = ["ETF", "個股"]
_KIND_MAP = {"ETF": T.KIND_ETF, "個股": T.KIND_STOCK}
_MAIN_COLS = ["代號", "名稱", "種類", "類別", "健檢", "235 燈號", "加碼金", "3-3-3", "建議動作"]


def _holdings_from_editor(records) -> list[dict]:
    """data_editor records → [{ticker,name,asset_class,asset_kind}]（空代號略過）。"""
    out = []
    for r in (records or []):
        _tk = str(r.get("代號", "") or "").strip().upper()
        if not _tk:
            continue
        out.append({"ticker": _tk, "name": str(r.get("名稱", "") or ""),
                    "asset_class": _CLASS_MAP.get(str(r.get("類別", "核心")), T.ASSET_CORE),
                    "asset_kind": _KIND_MAP.get(str(r.get("種類", "ETF")), T.KIND_ETF)})
    return out


def _style_rows(df):
    """健檢/建議 有 🔴/🟡 → 背景高亮（紅/琥珀）。"""
    def _bg(val):
        s = str(val)
        if "🔴" in s:
            return "background-color:#3d1418"
        if "🟡" in s:
            return "background-color:#3a3416"
        return ""
    return df.style.map(_bg, subset=[c for c in ("健檢", "建議動作") if c in df.columns])


def render_dividend_station() -> None:
    import pandas as pd

    st.markdown("### 💼 我的持股戰情室 — 個股 + ETF 統一健檢 · 235 加碼")
    st.caption("把你的**個股與 ETF 持股**放一起逐檔看：健檢（A賺息賠本 / B夏普 / C季線轉弱 / "
               "D高溢價）＋ 235 加碼燈 ＋ 3-3-3。以息養股：核心 80% 領息、衛星 20% 賺價差嚴格停利。")
    st.caption("ℹ️ 個股：D折溢價 / 3-3-3 標「—」不適用（無 iNAV、非 ETF 挑選規則）。"
               "資料不足一律標「不判定」不猜（§1）。3-3-3③ 同儕排名 Phase 2 待接。")

    # ── 1️⃣ 你的清單（個股 + ETF）─────────────────────────────────────────
    st.markdown("#### 1️⃣ 你的持股清單（標 種類 + 🛡️核心 / 🚀衛星）")
    _dkey = "_station_df"
    if _dkey not in st.session_state:
        st.session_state[_dkey] = pd.DataFrame([
            {"代號": "0056", "名稱": "", "種類": "ETF", "類別": "核心"},
            {"代號": "00878", "名稱": "", "種類": "ETF", "類別": "核心"},
            {"代號": "2330", "名稱": "", "種類": "個股", "類別": "衛星"},
        ])

    if st.button("📥 帶入我的組合管理（ETF 組合 + 個股清單）", key="_station_import"):
        _imported = _try_import_from_portfolio(pd)
        if _imported is not None:
            st.session_state[_dkey] = _imported
            st.session_state.pop("_station_editor", None)
            st.rerun()

    _edited = st.data_editor(
        st.session_state[_dkey], num_rows="dynamic", key="_station_editor",
        use_container_width=True, hide_index=True,
        column_config={
            "代號": st.column_config.TextColumn("代號", help="ETF 或個股代號,如 0056 / 2330"),
            "名稱": st.column_config.TextColumn("名稱", help="可留空"),
            "種類": st.column_config.SelectboxColumn("種類", options=_KIND_OPTIONS, default="ETF"),
            "類別": st.column_config.SelectboxColumn("類別", options=_CLASS_OPTIONS,
                                                     default="核心"),
        })

    # ── 2️⃣ 執行 ────────────────────────────────────────────────────────
    st.markdown("#### 2️⃣ 執行戰情室")
    st.caption("按下方會抓 VIX + 逐檔週K / 折溢價等即時算（部署端網路才抓得到台股資料）。")
    if st.button("🚀 跑存股戰情室", type="primary", key="_station_run"):
        _holdings = _holdings_from_editor(_edited.to_dict("records"))
        if not _holdings:
            st.warning("清單是空的,請先填 ETF 代號。")
        else:
            try:
                from src.services.dividend_station_service import get_station_rows
                with st.spinner("戰情室運算中：抓 VIX + 逐檔週K / 折溢價 …"):
                    _rows, _vix = get_station_rows(_holdings)
                st.session_state["_station_rows"] = _rows
                st.session_state["_station_vix"] = _vix
            except Exception as _e:  # noqa: BLE001 — 整批失敗誠實報,不假裝成功
                st.error(f"戰情室運算失敗（Fail Loud）：{type(_e).__name__}: {_e}")

    # ── 3️⃣ 結果 ────────────────────────────────────────────────────────
    _rows = st.session_state.get("_station_rows")
    if not _rows:
        st.info("👆 填清單 → 按「🚀 跑存股戰情室」。台股 ETF 折溢價 / 週K 需部署端網路。")
        return

    _vix = st.session_state.get("_station_vix")
    _vix_txt = f"{_vix:.1f}" if isinstance(_vix, (int, float)) else "抓取失敗（235 的 VIX 條件本次不觸發）"
    st.markdown(f"#### 3️⃣ 戰情表　·　VIX：**{_vix_txt}**")

    _df = pd.DataFrame([{c: r.get(c, "") for c in _MAIN_COLS} for r in _rows])
    try:
        st.dataframe(_style_rows(_df), use_container_width=True, hide_index=True)
    except Exception:  # noqa: BLE001 — Styler 相容性問題退無樣式,不炸
        st.dataframe(_df, use_container_width=True, hide_index=True)

    # 汰弱紅燈摘要
    _reds = [r for r in _rows if r.get("健檢") == "🔴"]
    if _reds:
        st.error("🔴 **汰弱警訊**：" + "、".join(
            f"{r['代號']}（{r['建議動作']}）" for r in _reds))

    # 逐檔明細
    with st.expander("🔎 逐檔明細（健檢 A/B/C/D · 235 觸發 · 3-3-3）", expanded=False):
        for r in _rows:
            d = r.get("_detail", {})
            if d.get("error"):
                st.markdown(f"**{r['代號']} {r.get('名稱','')}** — ⚠️ {d['error']}")
                continue
            st.markdown(f"**{r['代號']} {r.get('名稱','')}**　{r.get('235 燈號','')}　"
                        f"3-3-3：{d.get('3-3-3明細','')}")
            st.caption(f"A：{d.get('健檢A','')}　｜　B：{d.get('健檢B','')}")
            st.caption(f"C：{d.get('健檢C','')}　｜　D：{d.get('健檢D','')}")
            if d.get("235觸發"):
                st.caption(f"235 觸發：{d['235觸發']}　深水：{d.get('深水防守','—')}")
            st.markdown("---")

    st.caption(f"💡 目標配置：🛡️核心 {T.CORE_TARGET_PCT:.0f}% / 🚀衛星 {T.SATELLITE_TARGET_PCT:.0f}%；"
               f"衛星獲利達 {T.SATELLITE_TAKE_PROFIT_PCT:.0f}% 嚴格停利、滾回核心。"
               "本區僅研究參考,非投資建議,盈虧自負。")


def _try_import_from_portfolio(pd):
    """從 📁 組合管理帶入 ETF 組合（種類=ETF）+ 個股清單（種類=個股）。

    best-effort：任一份讀不到就略過該份;兩份都空 → 提示 + None（未登入/未設）。
    """
    try:
        from src.data.portfolio import gsheet_portfolio as _gsp   # EX-PASSTHRU-1
    except Exception as _e:  # noqa: BLE001
        st.error(f"帶入失敗：{type(_e).__name__}: {_e}")
        return None

    _out: list[dict] = []
    # ETF 組合（種類=ETF,預設核心）
    _etf_sid = _gsp._get_active_sheet_id()
    if _etf_sid:
        try:
            _names = _gsp.list_portfolios(sheet_id=_etf_sid)
            if _names:
                _n0 = len(_out)
                for _r in (_gsp.load_portfolio(_names[0], sheet_id=_etf_sid) or []):
                    _c = str(_r.get("ticker", "") or "").strip()
                    if _c:
                        _out.append({"代號": _c, "名稱": "", "種類": "ETF", "類別": "核心"})
                # §1 不靜默:明講帶入哪一本(list_portfolios 是排序後取 [0])
                _more = "；此 Sheet 有多本組合,只取第一本" if len(_names) > 1 else ""
                st.caption(f"✅ 帶入 ETF 組合「{_names[0]}」（{len(_out) - _n0} 檔){_more}")
        except Exception as _e:  # noqa: BLE001
            st.caption(f"（ETF 組合讀取略過：{type(_e).__name__}）")
    # 個股清單（種類=個股,預設衛星）
    _stk_sid = _gsp._get_active_stock_sheet_id()
    if _stk_sid:
        try:
            _snames = _gsp.list_stock_watchlists(sheet_id=_stk_sid)
            if _snames:
                _n0 = len(_out)
                for _c in (_gsp.load_stock_watchlist(_snames[0], sheet_id=_stk_sid) or []):
                    _c = str(_c or "").strip()
                    if _c:
                        _out.append({"代號": _c, "名稱": "", "種類": "個股", "類別": "衛星"})
                _more = "；此 Sheet 有多份清單,只取第一份" if len(_snames) > 1 else ""
                st.caption(f"✅ 帶入 個股清單「{_snames[0]}」（{len(_out) - _n0} 檔){_more}")
        except Exception as _e:  # noqa: BLE001
            st.caption(f"（個股清單讀取略過：{type(_e).__name__}）")

    if not _out:
        st.warning("組合管理沒有可帶入的持股 —— 請先到 📁 組合管理選 Sheet 並存 ETF 組合 / 個股清單。")
        return None
    return pd.DataFrame(_out)
