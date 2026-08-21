"""L5 UI — 共用「綁定持股 Sheet」元件（SSOT）。

順暢化 P1（v19.205）：把 📁 組合管理 的「Drive 挑選器 + 登入 CTA + 寫入契約」抽成
**單一來源**共用元件,讓「選 Sheet」能在**任何**需要的地方就地做（💼 戰情室空狀態、
日後 P3a 全域狀態列）,不必把使用者踢去 📁 組合管理 才能綁定 —— 這正是 user 反映的
「先繞組合管理才能分析」順序痛點的根。

為什麼是這裡（§8.2）
────────────────────
- 本檔屬 **L5 UI**（src/ui/tabs/）。呼叫它的 📁 組合管理（L5 tabs）與 💼 戰情室
  （L5 etf）都是同層,L5→L5 import 合規。
- 直呼 L1 `gsheet_portfolio` / `oauth_state`：§8.2.A **EX-PASSTHRU-1** —— L1 內已用
  `@st.cache_data` / OAuth session lifecycle 集中緩存,加一層 L3 wrapper 只是 pure
  pass-through（§8.1 step 6「用不到的抽象」）。與 `portfolio_manager` / `app.py` 側欄
  登入按鈕同範式。已登記於 `tests/test_c3_layering_guard.py` 白名單。

§1 誠實：未登入 / 讀取失敗 → 誠實提示,不靜默、不捏造清單。
key_prefix 參數化 → 同一次 render 內多處呼叫（Streamlit 會 render 所有 tab）不撞 widget key。
"""
from __future__ import annotations

import re

import streamlit as st

# 貼 URL 解析用（與 app.py 側欄同一條正則 → 行為一致,§4.1）
_SHEET_URL_RE = re.compile(r'/spreadsheets/d/([a-zA-Z0-9_-]+)')


def apply_active_sheet(_gsp, sid: str) -> None:
    """把選定的 sheet_id 同時套 ETF + 個股兩通道 + 寫 ?sheet= 持久化（**唯一寫入契約**）。

    v19.204 A+C 的兩通道 + query param 行為集中於此;`portfolio_manager._apply_active_sheet`
    與側欄改為呼叫本函式,不各自複製（原本散 3 份 → SSOT）。
    """
    st.session_state[_gsp.PORTFOLIO_SHEET_KEY] = sid
    st.session_state[_gsp.STOCK_PORTFOLIO_SHEET_KEY] = sid
    # Sheet ID 非憑證（存取仍需 OAuth + Sheet ACL）,僅「上次用哪本」的設定持久化。
    try:
        st.query_params['sheet'] = sid
    except Exception:  # noqa: BLE001 — query param 寫入失敗不擋設定主線（§1）
        pass


def render_login_cta(*, key_suffix: str = '', sheet_id: str = '') -> bool:
    """未登入時的**就地** Google 登入按鈕。回傳 True=已顯示登入鈕,False=OAuth 未設定（降級提示）。

    §8.2 EX-PASSTHRU-1：lazy import L1 oauth_state / infra.oauth 只為組授權 URL（同 app.py 側欄）。
    P2(v19.206)：把當前 sheet_id 夾帶進 state（`login_state_with_sheet`）→ 新登入轉跳回來自動回綁,
    不必再繞 📁 組合管理。sheet_id 由 caller 注入（戰情室空狀態傳 `_gsp._get_active_sheet_id()`）。
    """
    try:
        from src.data.portfolio.oauth_state import get_oauth_cfg, login_state_with_sheet
        from infra.oauth import build_authorize_url
        _cfg = get_oauth_cfg()
    except Exception:  # noqa: BLE001 — oauth 模組/設定缺 → 降級,不炸
        _cfg = None
    if not _cfg:
        st.caption('⚙️ 尚未設定 Google 登入（OAuth）。可用左側「🔐 Google 帳號」貼 Sheet 網址／ID。')
        return False
    _url = build_authorize_url(_cfg['client_id'], _cfg['redirect_uri'],
                               state=login_state_with_sheet(sheet_id))
    # 註:st.link_button 非 stateful widget,無 key 參數(同 app.py 側欄登入鈕);多顆同時
    # 存在也不撞(不像 button/text_input 需唯一 key)。key_suffix 保留供 P2/P3a 語意擴充。
    st.link_button('🔐 用 Google 登入', _url, use_container_width=True)
    return True


def render_paste_id_binder(_gsp, *, key_prefix: str) -> None:
    """貼 Sheet 網址／ID → 消毒解析 → apply（未登入也可用,如 SA 部署或手動情境）。"""
    _cur = _gsp._get_active_sheet_id()
    _raw = st.text_input(
        'Google Sheet 網址或 ID',
        value=_cur, key=f'{key_prefix}paste_sid',
        placeholder='貼上 https://docs.google.com/spreadsheets/d/...',
        help='貼 URL/ID 設為投組資料庫（ETF + 個股共用）')
    _m = _SHEET_URL_RE.search(_raw)
    _sid = _m.group(1) if _m else _raw.strip()
    if _sid and _sid != _cur:
        apply_active_sheet(_gsp, _sid)
        st.success(f'已設投組資料庫：`{_sid}`')
        st.rerun()


def render_drive_picker(_gsp, *, key_prefix: str) -> None:
    """🚀 從 Google Drive 列出 / 新建 Sheet,一鍵設為投組資料庫（key_prefix 參數化,可多處共用）。

    §8.2.A EX-PASSTHRU-1：直呼 L1 gsheet_portfolio 的 Drive 函式（list_user_folders /
    list_user_sheets / create_new_sheet）。§1：未登入靜默不畫（由 caller 決定顯示登入 CTA）;
    讀取失敗誠實報,不捏造清單。設定同時寫 ETF + 個股兩通道（apply_active_sheet）。
    """
    if not _gsp._has_oauth_tokens():
        return
    _fmap = {'整個帳號（不限資料夾）': ''}
    try:
        for _f in _gsp.list_user_folders():
            _fmap[_f['name']] = _f['id']
    except Exception as _e:  # noqa: BLE001 — §1 誠實：讀不到資料夾就只列全部
        st.caption(f'（資料夾列表讀取失敗：{type(_e).__name__}，可直接列全部）')
    _fsel = st.selectbox('限定資料夾（可選）', list(_fmap.keys()), key=f'{key_prefix}folder')

    _lc, _nc = st.columns([3, 2])
    if _lc.button('📂 從 Drive 列出 Sheets', key=f'{key_prefix}list', use_container_width=True):
        try:
            st.session_state[f'{key_prefix}sheets'] = _gsp.list_user_sheets(_fmap.get(_fsel, ''))
        except Exception as _e:  # noqa: BLE001 — §1 列檔失敗誠實報,不捏造清單
            st.error(f'列出 Sheets 失敗：{type(_e).__name__}')
            st.session_state.pop(f'{key_prefix}sheets', None)
    if _nc.button('🆕 建立新投組 Sheet', key=f'{key_prefix}new', use_container_width=True):
        try:
            _sid, _url = _gsp.create_new_sheet()
            apply_active_sheet(_gsp, _sid)
            st.success('已建立新 Sheet 並設為投組資料庫（ETF + 個股共用）。')
            st.rerun()
        except Exception as _e:  # noqa: BLE001 — 建立失敗誠實報
            st.error(f'建立新 Sheet 失敗：{_e}')

    _sheets = st.session_state.get(f'{key_prefix}sheets')
    if _sheets is None:
        return
    if not _sheets:
        st.info('此範圍找不到 Sheets。可按「🆕 建立新投組 Sheet」,或改用貼網址／ID。')
        return

    # 清單只有 1 本且尚未設定 → 自動選用,省一次點擊（C v19.204;之後由 A 的 ?sheet= 持久化）。
    if len(_sheets) == 1 and not _gsp._get_active_sheet_id():
        apply_active_sheet(_gsp, _sheets[0]['id'])
        st.success(f'清單只有 1 本,已自動設為投組資料庫「{_sheets[0]["name"]}」。')
        st.rerun()

    _smap = {f'{s["name"]}（{s["id"][:12]}…）': s['id'] for s in _sheets}
    _pick = st.selectbox(f'清單共 {len(_sheets)} 本 — 選一本', list(_smap.keys()),
                         key=f'{key_prefix}pick')
    if st.button('✅ 使用此 Sheet 作為投組資料庫（ETF + 個股共用）', key=f'{key_prefix}use',
                 type='primary', use_container_width=True):
        _sid = _smap.get(_pick, '')
        if _sid:
            apply_active_sheet(_gsp, _sid)
            st.success(f'已設定投組資料庫為「{_pick}」（ETF + 個股共用此本）。')
            st.rerun()


def render_holdings_binder(_gsp, *, key_prefix: str) -> None:
    """就地綁定持股 Sheet 的完整入口（供 💼 戰情室空狀態 / 日後 P3a 狀態列共用）。

    兩態：
      · 未登入 → 就地 Google 登入 CTA + 「不綁表也能用的頁」引導（去死路化）。
      · 已登入未綁 → Drive 挑選器 +（展開）貼網址／ID。
    「已綁但空表」由 caller 依 holdings 自行判斷提示,不在本元件（見 §1 三態區分）。
    """
    if not _gsp._has_oauth_tokens():
        st.markdown('##### 🔗 綁定一次,之後這頁自動載入')
        st.caption('綁定 Google Sheet 後,戰情室會自動抓你的持股做健檢 / 235 加碼 / AI 總結,'
                   '不必每次再來設定。')
        # P2:把當前(若曾綁過)的 Sheet ID 夾帶進登入 state → 新登入回來自動回綁。
        render_login_cta(key_suffix=key_prefix, sheet_id=_gsp._get_active_sheet_id())
        st.caption('想先看不用綁表也能用的? → 🔬 個股 / 📊 多檔比較：直接打代碼就能分析。')
        return
    st.markdown('##### 🔗 選一份持股表就開工')
    render_drive_picker(_gsp, key_prefix=key_prefix)
    with st.expander('或：直接貼 Google Sheet 網址／ID'):
        render_paste_id_binder(_gsp, key_prefix=key_prefix)
