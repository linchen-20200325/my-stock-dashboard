"""src/data/portfolio/oauth_state.py — OAuth 設定解析 + Google client(v18.400 D4 歸位)

§8.2 layer:L1 Data — OAuth client + token management;與 gsheet_portfolio 同層。
原位於 `src/ui/pages/oauth_state.py`(命名錯誤,從未渲染 UI),v18.400 D4 搬正:
- 解除 `src/data/portfolio/gsheet_portfolio.py:50/104/121` 的 L1→L5 反向違憲
- `handle_oauth_callback()` 內含 st.success/st.error/st.rerun 屬 auth callback flash
  本質(類比 web framework middleware),允許在 L1(類比 EX-L0-1 streamlit lifecycle)

§8.2.A 例外:**EX-OAUTH-1**(v18.431 正式登錄,見 CLAUDE.md §8.2.A 例外清單表)
- L1 含真 UI 呼叫(st.success/st.error/st.rerun),超出 EX-CACHE-1 範圍
- 類比 EX-L0-1 將 streamlit lifecycle 視為部署框架特性(非業務 UI)
- 升級觸發條件:若未來新增多 OAuth provider → 升級 L4 framework adapter

外部 API
========
- _gsa_secret / _sheet_id_secret  (secrets 讀取)
- _resolve_oauth_cfg()             (config 優先序:secrets > session_state;每次呼叫動態解析)
- get_oauth_cfg() / is_oauth_configured()  (動態包裝;caller 必用這兩個,不要直接 import module-level)
- _get_oauth_client()              (建 gspread client)
- handle_oauth_callback()          (URL ?code= 換 token)

呼叫端
======
- app.py:sidebar 渲染前呼叫 handle_oauth_callback()
- src/data/portfolio/gsheet_portfolio.py:取 _get_oauth_client() 給 gspread 用(L1→L1 同層)
- src/ui/etf/etf_tab_portfolio.py:取 get_oauth_cfg / _gsa_secret / _sheet_id_secret 顯示登入狀態(L5→L1 EX-PASSTHRU-1)
"""
from __future__ import annotations

import re

import streamlit as st

from infra.oauth import (
    OAuthError,
    build_credentials_from_tokens,
    decode_id_token_email,
    ensure_fresh_tokens,
    exchange_code_for_tokens,
    generate_state,
)


def _safe_secret(key: str, default=None):
    """Streamlit 1.45+ secrets 缺失時 st.secrets.get() raise
    StreamlitSecretNotFoundError；try/except 包住避免 module load 即崩。"""
    try:
        if hasattr(st, "secrets"):
            return st.secrets.get(key, default)
    except Exception:
        pass
    return default


_gsa_secret      = _safe_secret("gcp_service_account")
_sheet_id_secret = _safe_secret("portfolio_sheet_id", "")


def _resolve_oauth_cfg() -> "dict | None":
    """OAuth Client 配置取得：secrets 優先；缺則用 session_state 的 in-app 設定。"""
    _from_secrets = _safe_secret("google_oauth")
    if _from_secrets and _from_secrets.get("client_id") \
            and _from_secrets.get("client_secret") \
            and _from_secrets.get("redirect_uri"):
        return dict(_from_secrets)
    try:
        _from_session = st.session_state.get("custom_oauth_cfg")
    except Exception:
        _from_session = None
    if _from_session and _from_session.get("client_id") \
            and _from_session.get("client_secret") \
            and _from_session.get("redirect_uri"):
        return dict(_from_session)
    return None


def get_oauth_cfg() -> "dict | None":
    """動態解析 OAuth config（每次呼叫都重算）。

    取代舊的 module-level `_oauth_cfg`。Streamlit 每次 rerun 都會看到最新的
    session_state['custom_oauth_cfg']，避免 in-app wizard 套用後 stale。
    """
    return _resolve_oauth_cfg()


def is_oauth_configured() -> bool:
    """OAuth Client 是否已備齊（secrets 或 session_state 二擇一即可）。"""
    return _resolve_oauth_cfg() is not None


def get_login_state() -> str:
    """回傳本 session 專屬的 OAuth state（沒有就產生一個並存進 session_state）。

    修「登入互相踢掉」核心：每個瀏覽器 session 各有一組隨機 state，寫進 authorize URL；
    Google 回呼帶回同一 state，`handle_oauth_callback()` 只認 state 相符者 →
    別的 session / 分頁發起的授權碼不會被本 session 吞掉，反之亦然。
    產一次後在本 session 內固定（跨 rerun 穩定），登入成功後清除。
    """
    _s = st.session_state.get("_oauth_state")
    if not _s:
        _s = generate_state()
        st.session_state["_oauth_state"] = _s
    return _s


# ── P2(v19.206 順暢化):Sheet ID 搭 OAuth `state` 便車 ─────────────────────
# 全新登入時 Google 轉跳會用 GCP 註冊死的 redirect_uri 回來,把書籤帶的 ?sheet= 沖掉
# (+ callback 收尾 query_params.clear() 再清一次)→ 上次用哪本 Sheet 失憶,被迫再繞
# 📁 組合管理。解法:讓 Sheet ID **搭 state 的便車**過去(state 本就會原封不動繞 Google
# 回來,是 CSRF 用的往返通道);Sheet ID 非憑證(存取仍需 OAuth token + Sheet ACL),可公開。
#
# 安全前提(對照 §1 + P2 架構說明):
#   1. **只有 Sheet ID 上車,refresh_token 等憑證永遠不進 state/URL**(那是 A-full,未做)。
#   2. **CSRF 不被稀釋**:nonce 仍是唯一被 _oauth_state_ok 驗證的部分;Sheet ID 是乘客,
#      不參與比對,無法放行任何原本會被擋的 callback。
#   3. **Sheet ID 當不可信輸入**:寫回 session/URL 前先過 _sanitize_sheet_id。
# 分隔符用 '.':nonce 是 token_urlsafe(base64url,無 '.'),Sheet ID 是 [A-Za-z0-9_-](無 '.')
# → partition('.') 零歧義。§3.3:分隔符 + 字母集/長度界抽成具名常數,不散 inline。
_STATE_SEP = "."
# Google Drive fileId 實測 44 字元;{1,120} 留餘裕又擋濫用(F2:防超長字串灌爆 URL/session)。
_SHEET_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,120}")


def _sanitize_sheet_id(raw) -> str:
    """Sheet ID 消毒:只放行純 [A-Za-z0-9_-](Google Sheet ID 字母集);其餘一律回空字串。

    純函式,易測。**不可信輸入**專用(state 便車帶回的乘客),擋任何注入怪字元。
    """
    s = str(raw or "").strip()
    return s if s and _SHEET_ID_RE.fullmatch(s) else ""


def login_state_with_sheet(sheet_id: str = "") -> str:
    """組 authorize URL 的 state = `nonce.sheetid`(sheetid 消毒後);無 sheetid → 純 nonce。

    nonce 仍走 get_login_state()(本 session CSRF 密鑰,跨 rerun 穩定);Sheet ID 只是搭便車
    讓它撐過 Google 轉跳。呼叫端:app.py 側欄登入鈕 + portfolio_binder.render_login_cta。
    """
    _nonce = get_login_state()
    _sid = _sanitize_sheet_id(sheet_id)
    return f"{_nonce}{_STATE_SEP}{_sid}" if _sid else _nonce


def _split_login_state(state) -> "tuple[str, str]":
    """把回呼帶回的 state 拆成 (nonce, sheet_id)。純函式,易測。

    partition 只切**第一個** '.' → nonce 一定完整(即使 sheetid 端有多餘字元,消毒也會擋掉)。
    無 '.'(舊書籤 / 純 nonce)→ (整串, "")。sheetid 一律經 _sanitize_sheet_id。
    """
    _nonce, _sep, _rest = str(state or "").partition(_STATE_SEP)
    return _nonce, _sanitize_sheet_id(_rest)


def _get_oauth_client():
    """從 session_state 的 tokens 建一個 gspread client，順便 ensure 過期前 refresh。"""
    cfg = _resolve_oauth_cfg()
    toks = st.session_state.get("gsheet_tokens")
    if not toks or not cfg:
        return None
    toks = ensure_fresh_tokens(dict(toks),
        cfg["client_id"], cfg["client_secret"])
    st.session_state["gsheet_tokens"] = toks
    creds = build_credentials_from_tokens(toks,
        cfg["client_id"], cfg["client_secret"])
    import gspread
    return gspread.authorize(creds)


def _oauth_state_ok(expected_state, got_state) -> bool:
    """OAuth state 檢查(v19.63 修「登入無限迴圈」)。純函式,易測。

    只有『本 session 確實發起過 OAuth(有 expected_state)且 URL 回傳 state 不符』
    才拒絕(= 別的 session 發起的授權碼)。session_state 在外部轉跳 / Streamlit Cloud
    app 重啟間可能遺失(expected=None)——此時**放行**,否則正常使用者會卡在
    「登入→回來又說沒登入」的無限迴圈(舊 v18.462 嚴格版把 expected=None 也拒絕)。

    truth table:
      expected=ABC, got=ABC  → True (正常登入)
      expected=None, got=ABC → True (session 遺失 → 放行,修迴圈)
      expected=ABC, got=XYZ  → False(真·別的 session → 擋)
      expected=ABC, got=None → True (URL 未帶 state)
    """
    if expected_state and got_state and got_state != expected_state:
        return False
    return True


def handle_oauth_callback() -> None:
    """OAuth callback：URL 帶 ?code=... 時自動換 token。

    app.py module body 在 sidebar 渲染前呼叫一次。
    """
    # v18.136 動態解析；session 設定變動時也要看得到
    cfg = _resolve_oauth_cfg()
    if cfg is None:
        return
    _qp = st.query_params
    if "code" in _qp and "gsheet_tokens" not in st.session_state:
        # state 檢查(v19.63 修「登入無限迴圈」):只有『本 session 有發起(expected)
        # 且 URL state 不符』才拒絕;session_state 在外部轉跳/app 重啟間遺失
        # (expected=None)時放行,避免正常登入卡死。詳見 _oauth_state_ok docstring。
        # P2(v19.206):state 現為 `nonce.sheetid`,只用 **nonce** 做 CSRF 檢查(語意不變),
        # sheetid 是搭便車的乘客,不參與比對。
        _expected_state = st.session_state.get("_oauth_state")
        _got_nonce, _got_sheet = _split_login_state(_qp.get("state"))
        if not _oauth_state_ok(_expected_state, _got_nonce):
            return  # 別的 session 發起的授權碼 → 不吞
        # R1(v19.206 安全硬化,順手併入 P2):本 session 確實發起過 OAuth(有 _expected_state)
        # 卻收到**空 nonce** 的 callback → 絕非本 session 的合法回呼(我們一定把 nonce 塞進
        # authorize URL 的 state,Google 一定原樣帶回)。擋掉 login-CSRF / session-fixation 的
        # 空 nonce 變體(`state=.xxx` / 無 state)。**不動** expected=None 的迴圈修正
        # (session 遺失時仍放行,見 _oauth_state_ok row 2)—— 只收「有自己的 nonce 卻收到空」這條。
        if _expected_state and not _got_nonce:
            return
        # P2 F1(安全稽核 blocker 修正):**回綁 Sheet 只在 CSRF 強驗通過時執行**。
        # `_oauth_state_ok` 為修「登入無限迴圈」刻意保留放行路徑(expected=None / nonce 空 → True),
        # 但那條路徑下 state 載荷**不可信**(攻擊者可構造 `state=.<自己的Sheet>` 空 nonce 繞檢查)。
        # 若在放行路徑也回綁 → 跨帳號 Sheet 注入(受害者後續寫入可能落到攻擊者的可寫 Sheet)。
        # 故:登入照舊放行(不動迴圈修正),但 Sheet 回綁只信「本 session 自己的 nonce 相符」。
        _strong_state = bool(_expected_state) and _got_nonce == _expected_state
        try:
            _tokens = exchange_code_for_tokens(
                _qp["code"], cfg["client_id"],
                cfg["client_secret"], cfg["redirect_uri"])
            st.session_state["gsheet_tokens"] = _tokens
            st.session_state["gsheet_email"] = decode_id_token_email(_tokens)
            st.session_state.pop("_oauth_state", None)  # 用完即棄，下次登入重新產
            # P2:把 state 便車帶回的 Sheet ID 回綁兩通道 + 重掛 ?sheet=(取代原本的
            # blanket clear —— 那正是把 ?sheet= 沖掉、逼使用者再繞組合管理的元凶之一)。
            # sheetid 已於 _split_login_state 消毒;非憑證,回綁只是「還原上次用哪本」。
            st.query_params.clear()
            if _got_sheet and _strong_state:
                st.session_state["portfolio_sheet_id"] = _got_sheet
                st.session_state["stock_portfolio_sheet_id"] = _got_sheet
                try:
                    st.query_params["sheet"] = _got_sheet
                except Exception:  # noqa: BLE001 — query param 寫入失敗不擋登入主線(§1)
                    pass
            _email = st.session_state.get("gsheet_email", "")
            st.success(f"✅ Google 登入成功{('：' + _email) if _email else ''}")
            st.rerun()
        except OAuthError as _oe:
            st.error(f"❌ OAuth 失敗：{_oe}")
