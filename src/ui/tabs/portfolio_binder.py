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

Sheet Safety 批（DEC-083）:
- B3/B4:~~本檔自帶 `/spreadsheets/d/(...)` 正則 + 自己寫兩格 session / `?sheet=`~~(有意識的移除,
  ⛔ 不是漏刪:發布連結 `/d/e/…` 會被那條正則解析成 `e` 再綁上去)。解析與寫入一律委派 L1
  `oauth_state` 的唯一寫入契約 `apply_sheet_binding`(解析器 SSOT 在 L0 `shared/sheet_id.py`)。
- C 段:~~Drive 清單只有 1 本且尚未設定 → 自動選用~~(客戶原文:「唯一本 Sheet 自動綁 取消。
  就算 Drive 只有一本：仍要使用者明確按『使用這本』。不要替使用者做綁定決策。」)。
"""
from __future__ import annotations

import streamlit as st
from shared.secret_md import scrub_md  # SEC-3：例外原文上畫面前先洗金鑰／識別碼／路徑
from shared.sheet_id import SHEET_INPUT_EMPTY

#: 明確選的那本早就是目前綁定(兩通道與網址都已是它)時的說法(QA B-1:⛔ 不得顯示成「已設定」)。
ALREADY_CURRENT_MSG = '已是目前使用的 Sheet（ETF + 個股共用此本），不用再設定。'


def apply_active_sheet(_gsp, sid: str):
    """使用者明確選定的 sheet_id → 綁定(委派 L1 `oauth_state.apply_sheet_binding`,**唯一寫入契約**)。

    契約同時寫 ETF + 個股兩通道 + `?sheet=` 並重算靜默恢復記號;解析不過(發布連結 / 怪字元)
    → 什麼都不寫。回傳契約的 `SheetBindResult`(既有 caller 不讀回傳值,行為不變)。
    `_gsp` 參數保留只為既有 caller 介面相容(`portfolio_manager._apply_active_sheet`)。
    """
    from src.data.portfolio.oauth_state import apply_sheet_binding   # EX-PASSTHRU-1(同 render_login_cta)
    return apply_sheet_binding(sid)


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
    """貼 Sheet 網址／ID → 消毒解析 → apply（未登入也可用,如 SA 部署或手動情境）。

    QA BLK-2(2026-10-25,有意識的修改):~~每輪 rerun 都拿框裡的值呼叫寫入契約~~ —— 有 key 的
    text_input 會保留舊值,使用者剛用 Drive 選了別本,下一輪框裡的舊 ID 又把綁定改回去。
    現行:只有使用者**真的改了文字**(on_change)才呼叫契約;綁定一變,框重新顯示現值。
    """
    from src.data.portfolio.oauth_state import (   # EX-PASSTHRU-1(同 render_login_cta)
        on_sheet_input_change,
        pop_sheet_input_result,
        prepare_sheet_input,
    )
    _key = f'{key_prefix}paste_sid'
    prepare_sheet_input(_key)
    st.text_input(
        'Google Sheet 網址或 ID',
        value=_gsp._get_active_sheet_id(), key=_key,
        on_change=on_sheet_input_change, args=(_key,),
        placeholder='貼上 https://docs.google.com/spreadsheets/d/...',
        help='貼 URL/ID 後按 Enter，設為投組資料庫（ETF + 個股共用）')
    _r = pop_sheet_input_result(_key)
    if _r is None:
        return
    if _r.error and _r.error != SHEET_INPUT_EMPTY:
        st.error(_r.message)   # B3:發布連結 / 看不懂的輸入 → 白話拒絕,⛔ 不猜、不綁
    elif _r.changed:
        st.success(f'已設投組資料庫：`{_r.sheet_id}`')
    elif _r.already_current:
        st.info(ALREADY_CURRENT_MSG)


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
            _r = apply_active_sheet(_gsp, _sid)
            if _r.error:   # 建出來的 ID 解析不過(實務上不會)→ 照實講,⛔ 不顯示成功
                st.error(f'已建立新 Sheet，但無法設為投組資料庫：{_r.message}')
            else:
                st.success('已建立新 Sheet 並設為投組資料庫（ETF + 個股共用）。')
                st.rerun()
        except Exception as _e:  # noqa: BLE001 — 建立失敗誠實報
            st.error(f'建立新 Sheet 失敗：{scrub_md(_e)}')

    _sheets = st.session_state.get(f'{key_prefix}sheets')
    if _sheets is None:
        return
    if not _sheets:
        st.info('此範圍找不到 Sheets。可按「🆕 建立新投組 Sheet」,或改用貼網址／ID。')
        return

    # ~~清單只有 1 本且尚未設定 → 自動選用~~:DEC-083 C 段取消(見檔頭)—— 只有 1 本也照樣
    # 下拉 + 按「✅ 使用此 Sheet」才綁定。
    _smap = {f'{s["name"]}（{s["id"][:12]}…）': s['id'] for s in _sheets}
    _pick = st.selectbox(f'清單共 {len(_sheets)} 本 — 選一本', list(_smap.keys()),
                         key=f'{key_prefix}pick')
    if st.button('✅ 使用此 Sheet 作為投組資料庫（ETF + 個股共用）', key=f'{key_prefix}use',
                 type='primary', use_container_width=True):
        _sid = _smap.get(_pick, '')
        if _sid:
            # QA B-1:成功訊息只在**真的寫了**時顯示;早就是這本 → 照實說,⛔ 不假裝設定成功。
            _r = apply_active_sheet(_gsp, _sid)
            if _r.changed:
                st.success(f'已設定投組資料庫為「{_pick}」（ETF + 個股共用此本）。')
                st.rerun()
            elif _r.already_current:
                st.info(ALREADY_CURRENT_MSG)
            else:
                st.error(_r.message)


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
