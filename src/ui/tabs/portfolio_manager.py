"""src/ui/tabs/portfolio_manager.py — 📁 投資組合管理(統一頁,L5).

一頁同時管「投資組合 Portfolio(含張數/成本)」+「觀察清單 Watchlist(純代號)」,都存到你自己的 Google Sheet。
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


def _classify_sheet_api_error(e) -> str | None:
    """把 Google Sheets 讀取例外歸類成可行動提示（純函式,可單測）。

    回傳提示字串;無法歸類 → None。§1：不吞錯,只是把 gspread 的原始碼況翻成使用者看得懂的下一步。
    """
    _s = str(e)
    if any(k in _s for k in ("429", "RESOURCE_EXHAUSTED", "Quota exceeded", "quota")):
        return ("↑ 這是 Google Sheets 讀取配額暫時用罄（429）—— 免費配額約每分鐘 60 次讀取。"
                "請等 1 分鐘再按一次;若頻繁發生,回報我加讀取快取（降低 API 呼叫次數）根治。")
    if any(k in _s for k in ("401", "UNAUTHENTICATED", "invalid_grant", "Token has been expired")):
        return "↑ Google 登入憑證過期或失效（401）—— 請到側欄重新「🔐 用 Google 登入」再試。"
    if any(k in _s for k in ("403", "PERMISSION_DENIED", "does not have permission")):
        return "↑ 沒有這本 Sheet 的存取權（403）—— 確認登入的 Google 帳號就是該 Sheet 的擁有者/協作者。"
    if "404" in _s or "NOT_FOUND" in _s:
        return "↑ 找不到這本 Sheet（404）—— 可能已被刪除或改了共用設定,請重新從 Drive 挑一本。"
    return None


def _sheet_api_error_hint(e) -> None:
    """有可行動提示就顯示（§1：讓錯誤可被使用者處理,不只是丟型別名）。"""
    _hint = _classify_sheet_api_error(e)
    if _hint:
        st.caption(_hint)


def records_to_codes(records) -> list[str]:
    _seen, out = set(), []
    for r in (records or []):
        _c = str(r.get("代號", "") or "").strip().upper()
        if _c and _c not in _seen:
            _seen.add(_c)
            out.append(_c)
    return out


def parse_sheet_id(raw) -> str:
    """由貼上的內容取 Google Sheet ID。

    - 完整編輯 URL `/spreadsheets/d/<id>/edit` → 抓 <id>
    - 純 ID(含 _ / -) → 原樣去空白
    - **發布連結** `/spreadsheets/d/e/<token>/pubhtml|pub?...` → 回 ""(空):
      發布 token(`2PACX-…`)**不是** spreadsheet key,無法用 gspread `open_by_key` 開啟;
      管理頁需要「編輯用」網址或 Sheet ID。回空讓 caller 提示使用者改貼正確連結,避免舊行為
      抓到 `/d/` 後單字元 `e` → `open_by_key("e")` 拋錯的誤導(稽核 A 低度缺失修正)。
    - 空 / None → ""
    """
    import re
    _s = str(raw or "").strip()
    if re.search(r"/spreadsheets/d/e/", _s):          # 發布連結(pubhtml/pub)→ 非可用 key
        return ""
    _m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", _s)
    return _m.group(1) if _m else _s


# ── UI ──────────────────────────────────────────────────────────────────
def render_portfolio_manager() -> None:
    """📁 投資組合管理主入口:投資組合 Portfolio（持有部位）+ 觀察清單 Watchlist（純代號）,存你的 Google Sheet。"""
    if st is None:
        return
    import pandas as pd
    from src.data.portfolio import gsheet_portfolio as _gsp   # EX-PASSTHRU-1

    st.markdown("### 📁 投資組合管理 — 一頁管 投資組合 Portfolio + 觀察清單 Watchlist（存你的 Google Sheet）")
    st.info("👉 **這裡放的是「你自己的持股 / 追蹤清單」**，不是選股建議。"
            "想找**系統幫你篩的候選股**請去『🔬 選股 → 🔭 選股網』。")
    st.caption("先用下方「🚀 從 Drive 挑一本 Sheet」選定投組資料庫（Portfolio + Watchlist 共用一本）；"
               "選好後左欄管 🏦 **投資組合 Portfolio**（你持有的部位，含張數/均價）、"
               "右欄管 📈 **觀察清單 Watchlist**（只追蹤的純代號）。")

    if not st.session_state.get("gsheet_tokens"):
        st.info("ℹ️ 尚未用 Google 登入 —— 左側 sidebar「🔐 Google 帳號」登入後，這裡就能從 Drive 挑 Sheet。")

    # 🚀 唯一入口:從 Drive 挑選 / 新建 Sheet(v19.166;手動貼網址已移除 —— 與挑選器重複)。
    # 若需純手動貼 Sheet ID(SA/未登入情境),走左側 sidebar「🔐 Google 帳號」的 Sheet ID 欄。
    _render_drive_picker(_gsp)

    _c1, _c2 = st.columns(2)
    with _c1:
        _render_etf_section(_gsp, pd)
    with _c2:
        _render_stock_section(_gsp, pd)


def _render_drive_picker(_gsp) -> None:
    """🚀 從 Google Drive 列出 / 新建 Sheet,一鍵設為投組資料庫（ETF + 個股共用）。

    §8.2.A EX-PASSTHRU-1:L5 直呼 L1 gsheet_portfolio 的 Drive 函式(list_user_folders /
    list_user_sheets / create_new_sheet)。§1:未登入 / 讀取失敗 → 誠實提示,不靜默。
    設定同時寫 ETF(PORTFOLIO_SHEET_KEY)與個股(STOCK_PORTFOLIO_SHEET_KEY)兩通道。
    """
    st.markdown("#### 🚀 從 Drive 挑一本 Sheet（設為投組資料庫）")
    if not _gsp._has_oauth_tokens():
        st.caption("ℹ️ 用左側 sidebar「🔐 Google 帳號」登入後，這裡就能直接從 Drive 列出並挑選 Sheet。")
        return

    _cur_etf = _gsp._get_active_sheet_id()
    _cur_stk = _gsp._get_active_stock_sheet_id()
    if _cur_etf or _cur_stk:
        _same = bool(_cur_etf) and _cur_etf == _cur_stk
        st.caption(f"目前投組資料庫 — ETF：`{_cur_etf or '未設'}`　個股：`{_cur_stk or '未設'}`"
                   + ("　（同一本 ✅）" if _same else "　（兩本不同）" if (_cur_etf and _cur_stk) else ""))

    # 限定資料夾(可選)
    _fmap = {"整個帳號（不限資料夾）": ""}
    try:
        for _f in _gsp.list_user_folders():
            _fmap[_f["name"]] = _f["id"]
    except Exception as _e:                       # §1 誠實:資料夾讀不到就只列全部
        st.caption(f"（資料夾列表讀取失敗：{type(_e).__name__}，可直接列全部）")
    _fsel = st.selectbox("限定資料夾（可選）", list(_fmap.keys()), key="_mgmt_drive_folder")

    _lc, _nc = st.columns([3, 2])
    if _lc.button("📂 從 Drive 列出 Sheets", key="_mgmt_drive_list", use_container_width=True):
        try:
            st.session_state["_mgmt_drive_sheets"] = _gsp.list_user_sheets(_fmap.get(_fsel, ""))
        except Exception as _e:                   # §1 列檔失敗誠實報,不捏造清單
            st.error(f"列出 Sheets 失敗：{type(_e).__name__}")
            st.session_state.pop("_mgmt_drive_sheets", None)
    if _nc.button("🆕 建立新投組 Sheet", key="_mgmt_drive_new", use_container_width=True):
        try:
            _sid, _url = _gsp.create_new_sheet()
            _apply_active_sheet(_gsp, _sid)
            st.success(f"已建立新 Sheet 並設為投組資料庫（ETF + 個股共用）。")
            st.rerun()
        except Exception as _e:
            st.error(f"建立新 Sheet 失敗：{_e}")

    _sheets = st.session_state.get("_mgmt_drive_sheets")
    if _sheets is None:
        return
    if not _sheets:
        st.info("此範圍找不到 Sheets。可按「🆕 建立新投組 Sheet」，或用「⚙️ 進階」手動貼網址。")
        return

    # C(v19.204 順暢化):清單只有 1 本且尚未設定 → 自動選用,省一次點擊(首次設定更順;
    # 之後由 A 的 ?sheet= 持久化,回訪不必再進本頁)。已設定則不動(尊重使用者當前選擇)。
    if len(_sheets) == 1 and not _gsp._get_active_sheet_id():
        _apply_active_sheet(_gsp, _sheets[0]["id"])
        st.success(f"清單只有 1 本,已自動設為投組資料庫「{_sheets[0]['name']}」。")
        st.rerun()

    _smap = {f'{s["name"]}（{s["id"][:12]}…）': s["id"] for s in _sheets}
    _pick = st.selectbox(f"清單共 {len(_sheets)} 本 — 選一本", list(_smap.keys()),
                         key="_mgmt_drive_pick")
    if st.button("✅ 使用此 Sheet 作為投組資料庫（ETF + 個股共用）", key="_mgmt_drive_use",
                 type="primary", use_container_width=True):
        _sid = _smap.get(_pick, "")
        if _sid:
            _apply_active_sheet(_gsp, _sid)
            st.success(f"已設定投組資料庫為「{_pick}」（ETF + 個股共用此本）。")
            st.rerun()


def _apply_active_sheet(_gsp, sid: str) -> None:
    """把選定的 sheet_id 同時套到 ETF 與個股兩通道（共用一本）。"""
    st.session_state[_gsp.PORTFOLIO_SHEET_KEY] = sid
    st.session_state[_gsp.STOCK_PORTFOLIO_SHEET_KEY] = sid
    # A(v19.204 順暢化):同步寫入 URL query param → 重整/斷線重連/直接開任一頁(戰情室/選股)
    # 自動還原 Sheet 源(app.py 開機 gate 讀 ?sheet=),不必再回本頁重挑。Sheet ID 非憑證,
    # 存取仍需 OAuth + Sheet ACL;僅是「上次用哪本」的設定持久化(同 sid 個股代號既有做法)。
    try:
        st.query_params['sheet'] = sid
    except Exception:  # noqa: BLE001 — query param 寫入失敗不該擋設定主線
        pass


def _render_etf_section(_gsp, pd) -> None:
    st.markdown("#### 🏦 我的投資組合 Portfolio（你持有的部位，含張數 / 均價）")
    sid = _gsp._get_active_sheet_id()
    if not sid:
        st.caption("⚠️ 先用上方「🚀 從 Drive 挑一本 Sheet」選定。")
        return
    try:
        _names = _gsp.list_portfolios(sheet_id=sid)
    except Exception as _e:                        # §1 讀取失敗誠實報,不捏造清單
        st.error(f"讀取投資組合清單失敗：{type(_e).__name__}：{_e}")
        _sheet_api_error_hint(_e)
        return

    _dkey = "_mgmt_etf_df"
    if _dkey not in st.session_state:
        st.session_state[_dkey] = pd.DataFrame(
            [{"代號": "", "張數": None, "均價": None}])
    _pick = st.selectbox("載入我的投資組合 Portfolio（選一個 → 按下方 📂 載入）", ["—"] + _names,
                         key="_mgmt_etf_pick")
    _lc, _dc = st.columns(2)
    if _lc.button("📂 載入", key="_mgmt_etf_load", use_container_width=True) and _pick != "—":
        try:
            _rows = _gsp.load_portfolio(_pick, sheet_id=sid)
            st.session_state[_dkey] = pd.DataFrame(
                etf_rows_to_records(_rows) or [{"代號": "", "張數": None, "均價": None}])
            st.session_state["_mgmt_etf_name"] = _pick
            # ⚠️ 必須清掉 data_editor 的 widget-state,否則 Streamlit 會把「載入前的舊編輯」
            # 以 delta 疊回新載入的資料 → 存回 Sheet 就是髒資料(§1)。對齊 etf_tab_portfolio。
            st.session_state.pop("_mgmt_etf_editor", None)
            st.rerun()
        except Exception as _e:
            st.warning(f"載入失敗：{type(_e).__name__}")
    if _dc.button("🗑️ 刪除", key="_mgmt_etf_del", use_container_width=True) and _pick != "—":
        st.session_state["_mgmt_etf_pending_del"] = _pick     # 兩段式:先標記待刪
        st.rerun()
    _pend = st.session_state.get("_mgmt_etf_pending_del")
    if _pend:
        st.warning(f"確定刪除組合「{_pend}」？此動作無法復原。")
        _yc, _nc = st.columns(2)
        if _yc.button("✅ 確認刪除", key="_mgmt_etf_del_yes", use_container_width=True):
            try:
                _gsp.delete_portfolio(_pend, sheet_id=sid)
            except Exception as _e:
                st.warning(f"刪除失敗：{type(_e).__name__}")
            st.session_state.pop("_mgmt_etf_pending_del", None)
            st.rerun()
        if _nc.button("取消", key="_mgmt_etf_del_no", use_container_width=True):
            st.session_state.pop("_mgmt_etf_pending_del", None)
            st.rerun()

    _edited = st.data_editor(
        st.session_state[_dkey], num_rows="dynamic", key="_mgmt_etf_editor",
        use_container_width=True, hide_index=True,
        column_config={
            "代號": st.column_config.TextColumn("代號", help="如 00980A（可帶 .TW/.TWO）"),
            "張數": st.column_config.NumberColumn("張數", min_value=0.0, format="%.2f"),
            "均價": st.column_config.NumberColumn("均價", min_value=0.0, format="%.2f"),
        })
    _name = st.text_input("投資組合名稱", key="_mgmt_etf_name", placeholder="例：核心配置")
    if st.button("💾 儲存投資組合 Portfolio", key="_mgmt_etf_save", type="primary",
                 use_container_width=True):
        try:
            _rows = records_to_etf_rows(_edited.to_dict("records"))
            _n = _gsp.save_portfolio(_name, _rows, sheet_id=sid)
            st.success(f"已儲存「{_name}」共 {_n} 檔到你的 Google Sheet。")
        except Exception as _e:                    # ValueError(空名/無效) 等 → 誠實提示
            st.warning(f"儲存失敗：{_e}")


def _render_stock_section(_gsp, pd) -> None:
    st.markdown("#### 📈 我的觀察清單 Watchlist（純代號，只追蹤不一定持有，供週報 / 體檢用）")
    sid = _gsp._get_active_stock_sheet_id()
    if not sid:
        st.caption("⚠️ 先用上方「🚀 從 Drive 挑一本 Sheet」選定。")
        return
    try:
        _names = _gsp.list_stock_watchlists(sheet_id=sid)
    except Exception as _e:
        st.error(f"讀取觀察清單失敗：{type(_e).__name__}：{_e}")
        _sheet_api_error_hint(_e)
        return

    _dkey = "_mgmt_stk_df"
    if _dkey not in st.session_state:
        st.session_state[_dkey] = pd.DataFrame([{"代號": ""}])
    _pick = st.selectbox("載入我的觀察清單 Watchlist（選一個 → 按下方 📂 載入）", ["—"] + _names,
                         key="_mgmt_stk_pick")
    _lc, _dc = st.columns(2)
    if _lc.button("📂 載入", key="_mgmt_stk_load", use_container_width=True) and _pick != "—":
        try:
            _codes = _gsp.load_stock_watchlist(_pick, sheet_id=sid)
            st.session_state[_dkey] = pd.DataFrame(codes_to_records(_codes) or [{"代號": ""}])
            st.session_state["_mgmt_stk_name"] = _pick
            st.session_state.pop("_mgmt_stk_editor", None)   # 同 ETF:清舊 delta,不疊髒資料(§1)
            st.rerun()
        except Exception as _e:
            st.warning(f"載入失敗：{type(_e).__name__}")
    if _dc.button("🗑️ 刪除", key="_mgmt_stk_del", use_container_width=True) and _pick != "—":
        st.session_state["_mgmt_stk_pending_del"] = _pick
        st.rerun()
    _pend = st.session_state.get("_mgmt_stk_pending_del")
    if _pend:
        st.warning(f"確定刪除清單「{_pend}」？此動作無法復原。")
        _yc, _nc = st.columns(2)
        if _yc.button("✅ 確認刪除", key="_mgmt_stk_del_yes", use_container_width=True):
            try:
                _gsp.delete_stock_watchlist(_pend, sheet_id=sid)
            except Exception as _e:
                st.warning(f"刪除失敗：{type(_e).__name__}")
            st.session_state.pop("_mgmt_stk_pending_del", None)
            st.rerun()
        if _nc.button("取消", key="_mgmt_stk_del_no", use_container_width=True):
            st.session_state.pop("_mgmt_stk_pending_del", None)
            st.rerun()

    _edited = st.data_editor(
        st.session_state[_dkey], num_rows="dynamic", key="_mgmt_stk_editor",
        use_container_width=True, hide_index=True,
        column_config={"代號": st.column_config.TextColumn(
            "代號", help="個股或 ETF 代號（純代號，不需張數/成本）")})
    _name = st.text_input("觀察清單名稱", key="_mgmt_stk_name", placeholder="例：週報追蹤")
    if st.button("💾 儲存觀察清單 Watchlist", key="_mgmt_stk_save", type="primary",
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
