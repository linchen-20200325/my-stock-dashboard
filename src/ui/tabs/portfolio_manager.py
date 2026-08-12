"""src/ui/tabs/portfolio_manager.py — 📁 投資組合管理(統一頁,L5).

一頁同時管「ETF 組合(含張數/成本)」+「個股清單(純代號)」,都存到你自己的 Google Sheet。
重用 L1 `gsheet_portfolio` 儲存層(list/load/save/delete),不重造;登入 + 設定 Sheet
沿用既有機制(sidebar / 各分頁面板已設好的 sheet_id + OAuth token),本頁只讀 session 狀態
+ 做 CRUD。

§8.2.A EX-PASSTHRU-1:L5 lazy import L1 `gsheet_portfolio`(pass-through、L1 內已集中緩存)。
§1:未登入 / 未設 Sheet → 誠實提示去哪設,不靜默借別的 sheet;存/讀失敗 → 顯示錯誤不捏造。
widget key 一律 `_mgmt_` 前綴,與 ETF/個股 分頁面板的 keys 物理隔離,不碰撞。
"""
from __future__ import annotations

try:
    import streamlit as st
except ImportError:            # 純 .py 測試環境
    st = None                  # noqa: N816


# ── 純資料轉換(可單測;st 無關)──────────────────────────────────────────
def etf_rows_to_records(rows) -> list[dict]:
    """gsheet load_portfolio 的 [{ticker,lots,avg_price}] → 表格顯示 records。"""
    return [{"代號": str(r.get("ticker", "") or ""),
             "張數": r.get("lots"), "均價": r.get("avg_price")}
            for r in (rows or [])]


def records_to_etf_rows(records) -> list[dict]:
    """表格 records → save_portfolio 期望的 [{ticker,lots,avg_price}](空代號略過)。"""
    out = []
    for r in (records or []):
        _tk = str(r.get("代號", "") or "").strip()
        if _tk:
            out.append({"ticker": _tk, "lots": r.get("張數"), "avg_price": r.get("均價")})
    return out


def codes_to_records(codes) -> list[dict]:
    return [{"代號": str(c or "").strip()} for c in (codes or []) if str(c or "").strip()]


def records_to_codes(records) -> list[str]:
    _seen, out = set(), []
    for r in (records or []):
        _c = str(r.get("代號", "") or "").strip().upper()
        if _c and _c not in _seen:
            _seen.add(_c)
            out.append(_c)
    return out


# ── UI ──────────────────────────────────────────────────────────────────
def render_portfolio_manager() -> None:
    """📁 投資組合管理主入口:ETF 組合 + 個股清單,存你的 Google Sheet。"""
    if st is None:
        return
    import pandas as pd
    from src.data.portfolio import gsheet_portfolio as _gsp   # EX-PASSTHRU-1

    st.markdown("### 📁 投資組合管理 — 一頁管 ETF 組合 + 個股清單（存你的 Google Sheet）")
    st.caption("在這裡新增/編輯/儲存/載入/刪除你的「ETF 組合」與「個股清單」。"
               "登入與 Sheet 設定沿用既有：ETF 在側欄「🔐 Google 帳號」、個股在「個股組合」分頁設定。")

    if not st.session_state.get("gsheet_tokens"):
        st.info("ℹ️ 尚未用 Google 登入 —— 左側 sidebar「🔐 Google 帳號」登入後，這裡就能存取你的 Sheet。")

    _etf_sid = _gsp._get_active_sheet_id() or None
    _stk_sid = _gsp._get_active_stock_sheet_id() or None

    _c1, _c2 = st.columns(2)
    with _c1:
        _render_etf_section(_gsp, pd, _etf_sid)
    with _c2:
        _render_stock_section(_gsp, pd, _stk_sid)


def _render_etf_section(_gsp, pd, sid) -> None:
    st.markdown("#### 🏦 ETF 組合（含張數 / 均價）")
    if not sid:
        st.caption("⚠️ 尚未設定 ETF Google Sheet —— 到側欄或「🏦 ETF」分頁設定後回來。")
        return
    try:
        _names = _gsp.list_portfolios(sheet_id=sid)
    except Exception as _e:                        # §1 讀取失敗誠實報,不捏造清單
        st.error(f"讀取 ETF 組合清單失敗：{type(_e).__name__}")
        return

    _dkey = "_mgmt_etf_df"
    if _dkey not in st.session_state:
        st.session_state[_dkey] = pd.DataFrame(
            [{"代號": "", "張數": None, "均價": None}])
    _pick = st.selectbox("載入既有組合", ["—"] + _names, key="_mgmt_etf_pick")
    _lc, _dc = st.columns(2)
    if _lc.button("📂 載入", key="_mgmt_etf_load", use_container_width=True) and _pick != "—":
        try:
            _rows = _gsp.load_portfolio(_pick, sheet_id=sid)
            st.session_state[_dkey] = pd.DataFrame(
                etf_rows_to_records(_rows) or [{"代號": "", "張數": None, "均價": None}])
            st.session_state["_mgmt_etf_name"] = _pick
            st.rerun()
        except Exception as _e:
            st.warning(f"載入失敗：{type(_e).__name__}")
    if _dc.button("🗑️ 刪除", key="_mgmt_etf_del", use_container_width=True) and _pick != "—":
        try:
            _n = _gsp.delete_portfolio(_pick, sheet_id=sid)
            st.success(f"已刪除組合「{_pick}」（{_n} 檔）")
            st.rerun()
        except Exception as _e:
            st.warning(f"刪除失敗：{type(_e).__name__}")

    _edited = st.data_editor(
        st.session_state[_dkey], num_rows="dynamic", key="_mgmt_etf_editor",
        use_container_width=True, hide_index=True,
        column_config={
            "代號": st.column_config.TextColumn("代號", help="如 00980A（可帶 .TW/.TWO）"),
            "張數": st.column_config.NumberColumn("張數", min_value=0.0, format="%.2f"),
            "均價": st.column_config.NumberColumn("均價", min_value=0.0, format="%.2f"),
        })
    _name = st.text_input("組合名稱", key="_mgmt_etf_name", placeholder="例：核心配置")
    if st.button("💾 儲存 ETF 組合", key="_mgmt_etf_save", type="primary",
                 use_container_width=True):
        try:
            _rows = records_to_etf_rows(_edited.to_dict("records"))
            _n = _gsp.save_portfolio(_name, _rows, sheet_id=sid)
            st.success(f"已儲存「{_name}」共 {_n} 檔到你的 Google Sheet。")
        except Exception as _e:                    # ValueError(空名/無效) 等 → 誠實提示
            st.warning(f"儲存失敗：{_e}")


def _render_stock_section(_gsp, pd, sid) -> None:
    st.markdown("#### 📈 個股清單（純代號，供週報/體檢用）")
    if not sid:
        st.caption("⚠️ 尚未設定個股 Google Sheet —— 到「📊 比較 × 排行 → 個股組合」分頁設定後回來。")
        return
    try:
        _names = _gsp.list_stock_watchlists(sheet_id=sid)
    except Exception as _e:
        st.error(f"讀取個股清單失敗：{type(_e).__name__}")
        return

    _dkey = "_mgmt_stk_df"
    if _dkey not in st.session_state:
        st.session_state[_dkey] = pd.DataFrame([{"代號": ""}])
    _pick = st.selectbox("載入既有清單", ["—"] + _names, key="_mgmt_stk_pick")
    _lc, _dc = st.columns(2)
    if _lc.button("📂 載入", key="_mgmt_stk_load", use_container_width=True) and _pick != "—":
        try:
            _codes = _gsp.load_stock_watchlist(_pick, sheet_id=sid)
            st.session_state[_dkey] = pd.DataFrame(codes_to_records(_codes) or [{"代號": ""}])
            st.session_state["_mgmt_stk_name"] = _pick
            st.rerun()
        except Exception as _e:
            st.warning(f"載入失敗：{type(_e).__name__}")
    if _dc.button("🗑️ 刪除", key="_mgmt_stk_del", use_container_width=True) and _pick != "—":
        try:
            _n = _gsp.delete_stock_watchlist(_pick, sheet_id=sid)
            st.success(f"已刪除清單「{_pick}」（{_n} 檔）")
            st.rerun()
        except Exception as _e:
            st.warning(f"刪除失敗：{type(_e).__name__}")

    _edited = st.data_editor(
        st.session_state[_dkey], num_rows="dynamic", key="_mgmt_stk_editor",
        use_container_width=True, hide_index=True,
        column_config={"代號": st.column_config.TextColumn(
            "代號", help="個股或 ETF 代號（純代號，不需張數/成本）")})
    _name = st.text_input("清單名稱", key="_mgmt_stk_name", placeholder="例：週報追蹤")
    if st.button("💾 儲存個股清單", key="_mgmt_stk_save", type="primary",
                 use_container_width=True):
        try:
            _codes = records_to_codes(_edited.to_dict("records"))
            if not _codes:
                st.warning("清單是空的，請先填代號。")
            else:
                _n = _gsp.save_stock_watchlist(_name, _codes, sheet_id=sid)
                st.success(f"已儲存「{_name}」共 {_n} 檔到你的 Google Sheet。")
        except Exception as _e:
            st.warning(f"儲存失敗：{_e}")
