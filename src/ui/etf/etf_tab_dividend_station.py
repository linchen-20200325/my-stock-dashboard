"""L5 UI — 💰 存股戰情室（掛在 🏦 ETF）。

以息養股 / 3-3-3 挑三 / 235 加碼。逐檔跑健檢 ABCD + 235 燈 + 3-3-3,顏色高亮、
隱藏開高低收。§8.2 L5：只呼叫 L3 `dividend_station_service`,不自算。§1：抓取失敗
逐列誠實標記,不炸整表。抓取 button-gated（不每次 rerun 重抓）。
"""
from __future__ import annotations

import streamlit as st

from shared import dividend_station_thresholds as T

_CLASS_OPTIONS = ["核心", "衛星"]
_CLASS_MAP = {"核心": T.ASSET_CORE, "衛星": T.ASSET_SATELLITE}
_MAIN_COLS = ["代號", "名稱", "類別", "健檢", "235 燈號", "加碼金", "3-3-3", "建議動作"]


def _holdings_from_editor(records) -> list[dict]:
    """data_editor records → [{ticker,name,asset_class}]（空代號略過）。"""
    out = []
    for r in (records or []):
        _tk = str(r.get("代號", "") or "").strip().upper()
        if not _tk:
            continue
        out.append({"ticker": _tk, "name": str(r.get("名稱", "") or ""),
                    "asset_class": _CLASS_MAP.get(str(r.get("類別", "核心")), T.ASSET_CORE)})
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

    st.markdown("### 💰 存股戰情室 — 以息養股 · 3-3-3 挑三 · 235 加碼")
    st.caption("以息養股存股法：核心 80% 領息自動停利、衛星 20% 賺價差嚴格停利。"
               "逐檔跑健檢（A賺息賠本 / B夏普 / C季線轉弱 / D高溢價）＋ 235 加碼燈 ＋ 3-3-3 挑三。")
    st.caption("ℹ️ 健檢/235/3-3-3①②（成立·3年報酬）即時算；**3-3-3③ 同儕排名 Phase 2 待接**"
               "（顯示「❔ 待資料」）。資料不足一律標「不判定」,不猜（§1）。")

    # ── 1️⃣ 你的清單 ────────────────────────────────────────────────────
    st.markdown("#### 1️⃣ 你的清單（標 🛡️核心 / 🚀衛星）")
    _dkey = "_station_df"
    if _dkey not in st.session_state:
        st.session_state[_dkey] = pd.DataFrame([
            {"代號": "0056", "名稱": "", "類別": "核心"},
            {"代號": "00878", "名稱": "", "類別": "核心"},
            {"代號": "0050", "名稱": "", "類別": "衛星"},
        ])

    if st.button("📥 帶入我的組合管理 ETF 清單", key="_station_import"):
        _imported = _try_import_from_portfolio(pd)
        if _imported is not None:
            st.session_state[_dkey] = _imported
            st.session_state.pop("_station_editor", None)
            st.rerun()

    _edited = st.data_editor(
        st.session_state[_dkey], num_rows="dynamic", key="_station_editor",
        use_container_width=True, hide_index=True,
        column_config={
            "代號": st.column_config.TextColumn("代號", help="ETF 代號,如 0056 / 00878"),
            "名稱": st.column_config.TextColumn("名稱", help="可留空"),
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
    """從 📁 組合管理的 ETF 組合帶入代號（best-effort;未登入/未設 → None）。"""
    try:
        from src.data.portfolio import gsheet_portfolio as _gsp   # EX-PASSTHRU-1
        _sid = _gsp._get_active_sheet_id()
        if not _sid:
            st.warning("尚未設定 ETF 組合 Sheet —— 請先到 📁 組合管理選一本。")
            return None
        _names = _gsp.list_portfolios(sheet_id=_sid)
        if not _names:
            st.warning("你的 ETF 組合 Sheet 內沒有已存的組合。")
            return None
        _rows = _gsp.load_portfolio(_names[0], sheet_id=_sid)
        _codes = [str(r.get("ticker", "") or "").strip() for r in (_rows or [])]
        _codes = [c for c in _codes if c]
        if not _codes:
            st.warning("組合內沒有代號。")
            return None
        return pd.DataFrame([{"代號": c, "名稱": "", "類別": "核心"} for c in _codes])
    except Exception as _e:  # noqa: BLE001
        st.error(f"帶入失敗：{type(_e).__name__}: {_e}")
        return None
