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
- (SEC-3 審計:原 `_gsa_secret` / `_sheet_id_secret` module global 已刪 —— 前者在 import 時把整份
  SA secret(含私鑰)常駐記憶體,而網頁端已不再用 SA;唯一 caller app.py 側欄 caption 分支一併刪除)
- _resolve_oauth_cfg()             (config 優先序:secrets > session_state;每次呼叫動態解析)
- get_oauth_cfg() / is_oauth_configured()  (動態包裝;caller 必用這兩個,不要直接 import module-level)
- _get_oauth_client()              (建 gspread client)
- handle_oauth_callback()          (URL ?code= 換 token;SEC-2 起只認 server 端 nonce ＋ 同一瀏覽器;
                                    1.0-B2 起另處理 Google 帶回的 ?error=)
- maybe_silent_reauth()            (1.0-B2:重新整理後靜默恢復登入 —— 網址有記號才整頁轉去 Google prompt=none)
- forget_silent_reauth()           (1.0-B2:登出時拿掉網址記號,否則重新整理又登回去)
- sync_silent_marker()             (1.0-B2 稽核第二輪:登入後換了 Sheet → 以本 session 自己的 sub 重算記號)

SEC-2(login CSRF)
==================
修前:Google 轉跳回來是整頁載入 ⇒ 新 session ⇒ `session_state` 裡的期望 state 幾乎一定不在,
而舊 `_oauth_state_ok` 對「沒有期望值」**放行**(v19.63 修迴圈)⇒ 任何 `?code=`(含攻擊者自己的
授權碼)都會被吞下,受害者被登入成攻擊者帳號、之後的寫入落進攻擊者的 Sheet。
修後:nonce 存在 server 端 `oauth_nonce_store`(process 級),綁定發起者瀏覽器的
`_streamlit_xsrf` cookie(解遮罩後的 token bytes 取 sha256);callback **唯一**成功路徑 =
`consume()` 回 ok(一次性、未過期、同一瀏覽器)。失敗:清 query params、顯示中文錯誤、
**不** rerun、**不**自動轉跳(不會迴圈),只記 reason code(⛔ 不記任何值)。
安全閥:secrets `oauth_csrf_enforce = false` → 驗證失敗仍放行登入但照記 reason code
(預設嚴格;量測方法見 docs/OAUTH_SETUP.md「SEC-2 量測」)。

1.0-B2(重新整理後靜默恢復 Google 登入;DEC-062 Q2＝B)
=====================================================
客戶硬性條件(原文):「不得保存 Google 密碼或 Google 憑證」⇒ token **只**住在 `st.session_state`,
沒有任何 token 活得比 session 久。重新整理 ＝ 新 session ＝ 沒 token。恢復方式:
1. 登入成功且 **consume ok(強驗)** 時,在網址掛非憑證記號 `?gs=<MAC>`(與 `?sheet=` 並列)。
   MAC ＝ HMAC-SHA256(client_secret, 網域字串＋sub＋Sheet ID) 截斷 —— 綁「這個 Google 帳號＋這本 Sheet」,
   不含任何憑證或帳號原文。安全閥放行的登入**不**掛(退回「重新整理後再按一次登入」)。
2. 重新整理 → `maybe_silent_reauth()` 看到記號、且本 session 沒 token、不是回呼、讀得到瀏覽器
   cookie、本 session 沒試過 ⇒ 標記本 session 已試過 → 走原本的 nonce 發放(state ＝ `nonce.sheet.MAC`)
   → script 先在要導的那個視窗上 `history.replaceState` 拿掉 `gs`(**不留**帶記號的歷史紀錄 ⇒
   按「上一頁」不會又轉一次)→ 整個分頁轉去 Google `prompt=none`。
3. 回呼:consume ok → 換 token → 以**新的** sub 與 state 帶回的 Sheet 重算 MAC,對不上就丟掉 token、
   不登入(防攻擊者帶自己的 Sheet、防同台電腦換了 Google 帳號)。Google 做不到就帶 `?error=` 回來 →
   藍色提示(st.info)「請按側欄登入」,落地網址沒有記號 ⇒ **不會迴圈**。
4. 靜默恢復拿不到 refresh_token ⇒ 約 1 小時後 access_token 過期 → `gsheet_portfolio` 清掉 session
   token、標記「登入已逾時」並請使用者重新整理(session 中途**絕不**自動轉跳)。
5. 稽核第二輪(MUST-1):登入後才綁 / 換 Sheet → `sync_silent_marker()` 重算記號(只對強驗登入的 session、
   只用本 session 自己的 sub);靜默恢復沒成功(記號不符 / Google 回 error / 回呼被 SEC-2 拒絕 / 換 token 失敗)
   時,state 帶回的 Sheet 寫回 `?sheet=`(**網址層級**,與 app.py v19.204 的 `?sheet=` 還原同一個信任等級)
   ⇒ 手動登入時照常回綁,不會把 Sheet 弄丟。
常數見 `shared/oauth_session_policy.py`。

呼叫端
======
- app.py:sidebar 渲染前呼叫 handle_oauth_callback(),緊接著 maybe_silent_reauth()、sync_silent_marker();
  側欄登出呼叫 forget_silent_reauth();側欄寫入新的 ?sheet= 之後呼叫 sync_silent_marker()
- src/data/portfolio/gsheet_portfolio.py:取 _get_oauth_client() 給 gspread 用(L1→L1 同層)
"""
from __future__ import annotations

import binascii
import hashlib
import hmac
import json
import re

import streamlit as st

from shared.oauth_csrf_policy import (
    OAUTH_CSRF_ENFORCE_SECRET_KEY,
    STREAMLIT_XSRF_COOKIE_NAME,
)
from shared.oauth_session_policy import (
    OAUTH_CALLBACK_QUERY_KEYS,
    OAUTH_DISPLAYABLE_ERROR_CODES,
    OAUTH_LOGIN_EXPIRED_SESSION_KEY,
    OAUTH_PROMPT_NONE,
    OAUTH_SILENT_ATTEMPTED_SESSION_KEY,
    OAUTH_SILENT_ELIGIBLE_SESSION_KEY,
    OAUTH_SILENT_FAILURE_ERROR_CODES,
    OAUTH_SILENT_MAC_DOMAIN,
    OAUTH_SILENT_MARKER_PARAM,
    OAUTH_SILENT_REAUTH_SECRET_KEY,
    OAUTH_SILENT_TAG_HEX_LEN,
    SECRET_FLAG_OFF_STRINGS,
)
from src.data.portfolio import oauth_nonce_store as _nonce_store

from infra.oauth import (
    GOOGLE_AUTH_URL,
    OAuthError,
    build_authorize_url,
    build_credentials_from_tokens,
    decode_id_token_email,
    decode_id_token_sub,
    ensure_fresh_tokens,
    exchange_code_for_tokens,
    generate_state,
    sanitize_error_code,
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


#: XSRF cookie v2 格式的段數 / 版本字首 / mask 長度(§3.3:對照 streamlit 1.59
#: `generate_xsrf_token_string`:`"2|" + mask(4 bytes hex) + "|" + masked token hex + "|" + ts`)。
_XSRF_V2_PREFIX = "2"
_XSRF_V2_PARTS = 4
_XSRF_MASK_BYTES = 4


def _decode_xsrf_token(raw) -> "bytes | None":
    """`_streamlit_xsrf` cookie 原文 → 解遮罩後的 token bytes;解析不了 → None。純函式,易測。

    ⚠️ 不能比 cookie **字串**:Streamlit 每個 HTTP 回應都換一個隨機 mask 重發 cookie,
    同一瀏覽器的字串會變;不變的是 `masked XOR mask`(＝ token bytes)。
    只認 v2(`2|mask|masked|timestamp`);自寫解碼,⛔ 不 import streamlit 內部模組。
    """
    if not isinstance(raw, str):
        return None
    _v = raw.strip().strip("\"'")
    _parts = _v.split("|")
    if len(_parts) != _XSRF_V2_PARTS or _parts[0] != _XSRF_V2_PREFIX:
        return None
    try:
        _mask = binascii.a2b_hex(_parts[1].encode("ascii"))
        _masked = binascii.a2b_hex(_parts[2].encode("ascii"))
        int(_parts[3])
    except (binascii.Error, ValueError, UnicodeEncodeError):
        return None
    if len(_mask) != _XSRF_MASK_BYTES or not _masked:
        return None
    return bytes(_b ^ _mask[_i % _XSRF_MASK_BYTES] for _i, _b in enumerate(_masked))


def _browser_binding() -> "str | None":
    """目前這個瀏覽器的綁定值 = sha256(XSRF token bytes) 的 hex;讀不到 / 解析不了 → None。

    `st.context.cookies` 是本 session 建立時(websocket 握手)瀏覽器送來的 cookie,
    同一瀏覽器跨整頁載入(含 Google 轉跳回來)不變;攻擊者讀不到也寫不進受害者的 cookie。
    只交雜湊出去(nonce 表只存雜湊),⛔ 不記錄 / 不存 cookie 原文。
    """
    try:
        _raw = st.context.cookies.get(STREAMLIT_XSRF_COOKIE_NAME)
    except Exception:  # noqa: BLE001 — 無 script run context / 舊版無 st.context → 當作沒有 cookie
        return None
    _tok = _decode_xsrf_token(_raw)
    return hashlib.sha256(_tok).hexdigest() if _tok else None


def _secret_flag_on(key: str) -> bool:
    """secrets 布林開關:沒設 → True;只有 False / `SECRET_FLAG_OFF_STRINGS`(含整數 0)才 False。"""
    _v = _safe_secret(key, True)
    if isinstance(_v, bool):
        return _v
    return str(_v).strip().lower() not in SECRET_FLAG_OFF_STRINGS


def _csrf_enforced() -> bool:
    """安全閥:secrets `oauth_csrf_enforce` 明確設成 false 才放寬;沒設 / 其他值一律嚴格。"""
    return _secret_flag_on(OAUTH_CSRF_ENFORCE_SECRET_KEY)


def _silent_reauth_enabled() -> bool:
    """1.0-B2 開關:secrets `oauth_silent_reauth` 明確設成 false 才停用;沒設 / 其他值一律啟用。"""
    return _secret_flag_on(OAUTH_SILENT_REAUTH_SECRET_KEY)


#: session_state 旗標:本 session 已記過「發 nonce 時讀不到 cookie」(每 session 只記一次)。
_NO_COOKIE_LOGGED_KEY = "_oauth_no_cookie_logged"


def get_login_state() -> str:
    """回傳本 session 專屬的 OAuth nonce,並在 server 端登記 / 延長(綁定目前瀏覽器)。

    修「登入互相踢掉」:每個瀏覽器 session 各有一組隨機 nonce,寫進 authorize URL。
    SEC-2:每次呼叫(每次 rerun 畫登入鈕)都 `issue()` 一次 → nonce 活到最後一次畫鈕後
    `OAUTH_STATE_TTL_SEC`;callback 時以 `consume()` 驗「登記過、未過期、同一瀏覽器」。
    讀不到瀏覽器 cookie → 不登記(callback 會以 `no_cookie` 拒絕,fail closed)。
    產一次後在本 session 內固定(跨 rerun 穩定),callback 處理後清除。
    """
    _s = st.session_state.get("_oauth_state")
    if not _s:
        _s = generate_state()
        st.session_state["_oauth_state"] = _s
    _binding = _browser_binding()
    if _binding is None and not st.session_state.get(_NO_COOKIE_LOGGED_KEY):
        # SEC-2 審計 SA1-S2:沒 cookie 時不登記是刻意的(fail closed),但不能靜默 ——
        # 每個 session 記一次 reason code(⛔ 不記任何值),供 docs/OAUTH_SETUP.md 量測對照。
        print(f"[oauth_state] SEC-2 login nonce 未登記 reason={_nonce_store.REASON_NO_COOKIE}")
        st.session_state[_NO_COOKIE_LOGGED_KEY] = True
    _nonce_store.issue(_s, _binding)
    return _s


# ── P2(v19.206 順暢化):Sheet ID 搭 OAuth `state` 便車 ─────────────────────
# 全新登入時 Google 轉跳會用 GCP 註冊死的 redirect_uri 回來,把書籤帶的 ?sheet= 沖掉
# (+ callback 收尾 query_params.clear() 再清一次)→ 上次用哪本 Sheet 失憶,被迫再繞
# 📁 組合管理。解法:讓 Sheet ID **搭 state 的便車**過去(state 本就會原封不動繞 Google
# 回來,是 CSRF 用的往返通道);Sheet ID 非憑證(存取仍需 OAuth token + Sheet ACL),可公開。
#
# 安全前提(對照 §1 + P2 架構說明):
#   1. **只有 Sheet ID 上車,refresh_token 等憑證永遠不進 state/URL**(那是 A-full,未做)。
#   2. **CSRF 不被稀釋**:nonce 仍是唯一被驗證的部分(SEC-2 起由 oauth_nonce_store.consume
#      驗);Sheet ID 是乘客,不參與比對,無法放行任何原本會被擋的 callback。
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


#: 1.0-B2 靜默恢復記號(＝ MAC 截斷)的字母集與長度(§3.3;長度 SSOT 在 L0)。
_SILENT_TAG_RE = re.compile(rf"[0-9a-f]{{{OAUTH_SILENT_TAG_HEX_LEN}}}")


def _sanitize_silent_tag(raw) -> str:
    """記號值消毒:只放行恰好 `OAUTH_SILENT_TAG_HEX_LEN` 個小寫 hex;其餘回空字串。純函式。"""
    s = str(raw or "").strip()
    return s if _SILENT_TAG_RE.fullmatch(s) else ""


def login_state_with_sheet(sheet_id: str = "", silent_tag: str = "") -> str:
    """組 authorize URL 的 state = `nonce.sheetid`(sheetid 消毒後);無 sheetid → 純 nonce。

    nonce 仍走 get_login_state()(本 session CSRF 密鑰,跨 rerun 穩定);Sheet ID 只是搭便車
    讓它撐過 Google 轉跳。呼叫端:app.py 側欄登入鈕 + portfolio_binder.render_login_cta。

    1.0-B2:`silent_tag`(靜默恢復記號,消毒後非空)→ `nonce.sheetid.tag`(sheetid 可為空:
    `nonce..tag`)。三段 ＝ 靜默恢復;一般登入鈕不傳 ⇒ 格式與修前逐字相同。
    """
    _nonce = get_login_state()
    _sid = _sanitize_sheet_id(sheet_id)
    _tag = _sanitize_silent_tag(silent_tag)
    if _tag:
        return f"{_nonce}{_STATE_SEP}{_sid}{_STATE_SEP}{_tag}"
    return f"{_nonce}{_STATE_SEP}{_sid}" if _sid else _nonce


def _split_login_state(state) -> "tuple[str, str]":
    """把回呼帶回的 state 拆成 (nonce, sheet_id)。純函式,易測。

    partition 只切**第一個** '.' → nonce 一定完整(即使 sheetid 端有多餘字元,消毒也會擋掉)。
    無 '.'(舊書籤 / 純 nonce)→ (整串, "")。sheetid 一律經 _sanitize_sheet_id。
    """
    _nonce, _sep, _rest = str(state or "").partition(_STATE_SEP)
    return _nonce, _sanitize_sheet_id(_rest)


def _split_silent_state(state) -> "tuple[str, str, str, bool]":
    """回呼 state → `(nonce, sheet_id, silent_tag, is_silent)`。純函式,易測。

    兩段以內(`nonce` / `nonce.sheet`)→ 與 `_split_login_state` **完全相同**,`is_silent=False`。
    三段(`nonce.sheet.tag`)→ `is_silent=True`;sheet 照樣消毒,tag 不合格(長度 / 字母集)→ 空字串
    ⇒ 之後的 MAC 比對必然不過(被竄改的 state 不會登入)。nonce 一律取第一個 '.' 之前。
    """
    _nonce, _sep, _rest = str(state or "").partition(_STATE_SEP)
    _sheet_part, _sep2, _tag_part = _rest.partition(_STATE_SEP)
    if not _sep2:
        return _nonce, _sanitize_sheet_id(_rest), "", False
    return _nonce, _sanitize_sheet_id(_sheet_part), _sanitize_silent_tag(_tag_part), True


def _silent_tag(client_secret: str, sub: str, sheet_id: str) -> str:
    """靜默恢復記號 ＝ HMAC-SHA256(client_secret, 網域‖sub‖sheet) 的前 N 個 hex。缺金鑰或 sub → 空字串。

    ⛔ 不是憑證:單向、截斷,不含 sub / email 原文;沒有 client_secret 算不出來 ⇒ 攻擊者無法偽造。
    """
    if not client_secret or not sub:
        return ""
    _msg = f"{OAUTH_SILENT_MAC_DOMAIN}\x00{sub}\x00{sheet_id or ''}".encode("utf-8")
    return hmac.new(str(client_secret).encode("utf-8"), _msg,
                    hashlib.sha256).hexdigest()[:OAUTH_SILENT_TAG_HEX_LEN]


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


#: callback 驗證失敗時給使用者看的訊息(§3.3 具名常數;不含任何技術值)。
OAUTH_STATE_REJECTED_MSG = (
    "Google 登入驗證未通過（連結過期、已使用或非本瀏覽器發起），"
    "請按側欄『🔐 用 Google 登入』重新登入")

# ── 1.0-B2 使用者訊息(§3.3 具名常數)──────────────────────────────────────────────
# ⚠️ 顏色據實寫(稽核修正):`st.caption` 是灰字;`st.info` 是**藍色**提示框 —— 兩者都不是紅色錯誤
# (v3 §02:「系統真出錯」才紅)。
#: 發出靜默轉跳時畫在頁首的灰字(st.caption)(轉跳成功的話使用者幾乎看不到;被擋住時它就是出口)。
OAUTH_SILENT_REAUTH_PENDING_MSG = (
    "正在恢復 Google 登入…若幾秒內沒有反應，請按側欄「🔐 用 Google 登入」。")
#: Google 回 `OAUTH_SILENT_FAILURE_ERROR_CODES` 之一(需要使用者互動)。藍色 st.info。
OAUTH_SILENT_REAUTH_FAILED_MSG = (
    "未能自動恢復登入（Google 需要你再確認一次），請按側欄「🔐 用 Google 登入」。")
#: 其他 `?error=`,且代碼在 `OAUTH_DISPLAYABLE_ERROR_CODES` 裡(例:access_denied)。藍色 st.info。
OAUTH_LOGIN_INCOMPLETE_MSG = "Google 登入未完成（{code}）。"
#: 其他 `?error=`,代碼**不在**標準表裡 → ⛔ 不把網址上的字搬上畫面(稽核 SA1 NIT-1)。
OAUTH_LOGIN_INCOMPLETE_GENERIC_MSG = "Google 登入未完成。"
#: 靜默恢復換到的帳號 / state 帶回的 Sheet 與記號綁定的不同(或記號被竄改)→ 丟掉 token、不登入。
OAUTH_SILENT_MISMATCH_MSG = (
    "自動恢復登入的帳號或 Sheet 與上次不同，請按「🔐 用 Google 登入」手動登入。")

# ── 1.0-B2 log reason codes(§3.3;⛔ 只記代碼,不記 nonce / token / email / URL / 記號值)──────
SILENT_REDIRECT = "redirect"
SILENT_SKIP_NO_MARKER = "no_marker"
SILENT_SKIP_DISABLED = "disabled"
SILENT_SKIP_ATTEMPTED = "already_attempted"
SILENT_SKIP_LOGGED_IN = "logged_in"
SILENT_SKIP_CALLBACK = "callback_params"
SILENT_SKIP_NOT_CONFIGURED = "not_configured"
SILENT_SKIP_NO_CLIENT_SECRET = "no_client_secret"
SILENT_SKIP_NO_COOKIE = "no_cookie"
SILENT_SKIP_BAD_URL = "bad_url"
SILENT_REJECT_TAG_MISMATCH = "tag_mismatch"
SILENT_REJECT_NO_SUB = "no_sub"
SILENT_MARKER_NOT_SET_NO_SUB = "marker_not_set_no_sub"
SILENT_MARKER_SET_FAILED = "marker_set_failed"
SILENT_MARKER_REMOVE_FAILED = "marker_remove_failed"
SILENT_MARKER_RESYNCED = "marker_resynced"
#: 值得記 log 的略過原因(網址**有**記號、使用者期待恢復,卻因設定 / 環境做不到)。
#: 其餘(沒記號、已登入…)是每次 rerun 的常態,記了只會洗版。每 session 只記一次。
_SILENT_LOGGED_SKIP_REASONS = frozenset({
    SILENT_SKIP_DISABLED, SILENT_SKIP_NOT_CONFIGURED, SILENT_SKIP_NO_COOKIE,
    SILENT_SKIP_NO_CLIENT_SECRET})


def _silent_marker_value() -> str:
    """網址上的記號值(消毒後);沒有 / 不合格 → 空字串(＝ 沒有記號)。"""
    try:
        return _sanitize_silent_tag(st.query_params.get(OAUTH_SILENT_MARKER_PARAM))
    except Exception:  # noqa: BLE001 — 讀不到 query params ⇒ 當作沒有記號(不轉跳 = 安全側)
        return ""


def forget_silent_reauth() -> None:
    """登出時呼叫:拿掉網址記號、清「登入已逾時」旗標、標記本 session 不再靜默恢復。

    ⚠️ 已知限制(據實):伺服器端改 query params 在前端是**新增**一筆歷史紀錄,只管得到**這個分頁現在的
    網址**;其他分頁、或「上一頁」回到帶記號的舊網址,在 Google 仍登入時會再靜默登入一次 —— 但記號綁
    帳號＋Sheet(MAC),只會登回**同一個帳號、同一本 Sheet**。見 docs/OAUTH_SETUP.md。
    """
    try:
        st.query_params.pop(OAUTH_SILENT_MARKER_PARAM, None)
    except Exception as _e:  # noqa: BLE001 — 拿不掉要講出來(§1),但不擋登出主線
        print(f"[oauth_state] 1.0-B2 silent_reauth={SILENT_MARKER_REMOVE_FAILED} "
              f"({type(_e).__name__})")
    st.session_state.pop(OAUTH_LOGIN_EXPIRED_SESSION_KEY, None)
    st.session_state.pop(OAUTH_SILENT_ELIGIBLE_SESSION_KEY, None)
    st.session_state[OAUTH_SILENT_ATTEMPTED_SESSION_KEY] = True


def _url_sheet() -> str:
    """網址上的 `?sheet=`(消毒後)。記號一律跟「網址上的 sheet」一起算(那是重新整理後唯一留下來的)。"""
    try:
        return _sanitize_sheet_id(st.query_params.get("sheet"))
    except Exception:  # noqa: BLE001 — 讀不到 query params ⇒ 當作沒有
        return ""


def sync_silent_marker() -> bool:
    """1.0-B2 稽核第二輪(MUST-1):登入後換了 Sheet → 重算網址記號。回是否改寫了 `gs`。

    修前:登入時記號 ＝ MAC(sub, 當時的 Sheet,常是空的),之後在側欄 / 📁 組合管理綁了 Sheet,網址變成
    `?sheet=SID` 但記號沒變 → 下一次重新整理靜默恢復時 MAC(sub, SID) ≠ 記號 → 不登入、Sheet 也一起丟了,
    而且**每一次**都這樣。
    **全部**成立才改寫:開關啟用、有 client_secret、本 session 已登入、本 session 的登入是**強驗**掛過記號的
    (`OAUTH_SILENT_ELIGIBLE_SESSION_KEY`;安全閥放行 / 開關停用時的登入沒有)、網址不是回呼、本 session 的
    id_token 解得出 sub、新值與網址現值不同。
    ⛔ 只用**本 session 自己的** sub(token 是本 server 向 Google 換來的)⇒ 永遠不會替別的帳號算出記號,
    攻擊面不變;Sheet 取網址上的 `?sheet=`(消毒後,與 `maybe_silent_reauth` 同一個來源)。
    """
    if not st.session_state.get(OAUTH_SILENT_ELIGIBLE_SESSION_KEY):
        return False
    _toks = st.session_state.get("gsheet_tokens")
    if not _toks or not isinstance(_toks, dict) or not _silent_reauth_enabled():
        return False
    try:
        if any(_k in st.query_params for _k in OAUTH_CALLBACK_QUERY_KEYS):
            return False
        _cur = st.query_params.get(OAUTH_SILENT_MARKER_PARAM)
    except Exception:  # noqa: BLE001
        return False
    _cfg = _resolve_oauth_cfg() or {}
    _tag = _silent_tag(_cfg.get("client_secret", ""), decode_id_token_sub(_toks), _url_sheet())
    if not _tag or _tag == _cur:
        return False
    try:
        st.query_params[OAUTH_SILENT_MARKER_PARAM] = _tag
    except Exception as _e:  # noqa: BLE001 — 寫不進去要講出來(§1),不擋主線
        print(f"[oauth_state] 1.0-B2 silent_reauth={SILENT_MARKER_SET_FAILED} "
              f"({type(_e).__name__})")
        return False
    print(f"[oauth_state] 1.0-B2 silent_reauth={SILENT_MARKER_RESYNCED}")
    return True


def _clear_query_keep_sheet(fallback_sheet: str = "") -> None:
    """清掉網址 query(code / state / error / 記號…),但保留 `?sheet=`:網址原本有就留,否則用 `fallback_sheet`。

    ⛔ 不碰 session(不回綁、不登入)、⛔ 不寫 `gs`。`fallback_sheet` 只在**靜默恢復**沒成功時傳入
    (state 帶回的那本,已消毒):信任等級＝ app.py v19.204 的 `?sheet=` 網址還原 —— 有人能塞這個 state,
    就一樣能直接寄 `?sheet=` 的連結(既有信任模型,另案追蹤),本函式沒有放大它。
    """
    _keep = _url_sheet() or _sanitize_sheet_id(fallback_sheet)
    st.query_params.clear()
    if _keep:
        try:
            st.query_params["sheet"] = _keep
        except Exception:  # noqa: BLE001 — query param 寫入失敗不擋主線(§1:同成功路徑)
            pass


def _silent_reauth_skip_reason() -> "str | None":
    """回 None ＝ 全部條件成立、可以轉跳;否則回略過原因代碼。順序:便宜的先查。"""
    if not _silent_marker_value():
        return SILENT_SKIP_NO_MARKER
    if not _silent_reauth_enabled():
        return SILENT_SKIP_DISABLED
    if st.session_state.get(OAUTH_SILENT_ATTEMPTED_SESSION_KEY):
        return SILENT_SKIP_ATTEMPTED
    if st.session_state.get("gsheet_tokens"):
        return SILENT_SKIP_LOGGED_IN
    if any(_k in st.query_params for _k in OAUTH_CALLBACK_QUERY_KEYS):
        return SILENT_SKIP_CALLBACK
    _cfg = _resolve_oauth_cfg()
    if _cfg is None:
        return SILENT_SKIP_NOT_CONFIGURED
    if not _cfg.get("client_secret"):
        # 沒有 MAC 金鑰 ⇒ 回呼無從驗記號 ⇒ 整個靜默恢復停用(fail closed)
        return SILENT_SKIP_NO_CLIENT_SECRET
    if _browser_binding() is None:
        # 發得出 nonce 也綁不到瀏覽器 ⇒ 回呼必以 no_cookie 被拒 —— 不如別轉
        return SILENT_SKIP_NO_COOKIE
    return None


def _silent_redirect_script(url: str) -> str:
    """整頁(最上層視窗)轉去 `url` 的 script。純函式,易測。

    - URL 以 `json.dumps` 編成 JS 字串常值,再把 `<` `>` `&` 轉成 `\\uXXXX`
      ⇒ 任何內容都跳不出字串、也關不掉 `</script>`(⛔ 不用字串串接組 JS)。記號參數名同樣 JSON 編碼。
    - **只導最上層視窗**:本頁就是最上層 → 直接導;在 iframe 裡(Streamlit Cloud 外框)→
      先讀 `top.location.href` 探同源,同源才導最上層;跨來源讀取會丟例外 → 什麼都不做(網址原封不動 ⇒
      下次重新整理再試一次,仍是「每個使用者動作最多一次」)。
      ⛔ 絕不導 iframe 自己去 Google(Google 拒絕被框 → 白畫面),畫面上的灰字就是出口。
    - **上一頁陷阱(稽核 SA2 SHOULD-1)**:伺服器端 `st.query_params.pop` 在前端是 pushState(**新增**一筆
      歷史),`location.replace` 只會換掉那一筆,帶記號的舊紀錄還在 → 按上一頁又轉一次、走不出去。
      所以改成:在**要導的那個視窗**上先 `history.replaceState` 把**同一筆**紀錄的網址改成拿掉記號的版本
      (`URL` ＋ `searchParams.delete`,由該視窗自己的 location 算),成功後才 `location.replace`(也不留紀錄)。
      replaceState 失敗 → 不導(寧可停在灰字,也不製造走不出去的上一頁)。
    """
    def _js(v: str) -> str:
        return (json.dumps(str(v))
                .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
    return (
        "<script>(function(){"
        f"var u={_js(url)};var k={_js(OAUTH_SILENT_MARKER_PARAM)};"
        "var t;"
        "try{t=window.top;if(t!==window){void t.location.href;}}catch(e){return;}"
        "try{var l=new URL(t.location.href);l.searchParams.delete(k);"
        "t.history.replaceState(null,'',l.toString());}catch(e){return;}"
        "try{t.location.replace(u);}catch(e){}"
        "})();</script>"
    )


def maybe_silent_reauth() -> bool:
    """1.0-B2:重新整理後靜默恢復 Google 登入。回是否發出了轉跳。

    app.py 在 `handle_oauth_callback()` 之後立刻呼叫。**全部**成立才轉跳:開關啟用、OAuth 已設定且有
    client_secret、本 session 沒 token、網址有合格記號、網址沒有 code/error/state、讀得到瀏覽器 cookie、
    本 session 還沒試過。轉跳前**先**標記本 session 已試過 ⇒ 同一個 session 最多一次。
    記號**不在伺服器端拿掉**(那會多一筆帶記號的歷史紀錄 → 上一頁陷阱),改由 script 在導頁前以
    `history.replaceState` 拿掉;Google 回呼落地的網址(固定 redirect_uri)本來就沒有記號 ⇒ 不會迴圈。
    """
    _reason = _silent_reauth_skip_reason()
    if _reason is not None:
        if (_reason in _SILENT_LOGGED_SKIP_REASONS
                and not st.session_state.get(OAUTH_SILENT_ATTEMPTED_SESSION_KEY)):
            print(f"[oauth_state] 1.0-B2 silent_reauth=skip reason={_reason}")
            st.session_state[OAUTH_SILENT_ATTEMPTED_SESSION_KEY] = True   # 每 session 只記一次
        return False
    # 先標記,再做任何可能失敗的事(同 session 不再試)。
    st.session_state[OAUTH_SILENT_ATTEMPTED_SESSION_KEY] = True
    cfg = _resolve_oauth_cfg()
    _tag = _silent_marker_value()
    # 記號一律跟「網址上的 ?sheet=」一起算(`sync_silent_marker` 同一個來源)→ 只讀網址。
    # (稽核第二輪:修前會退回 session 的 Sheet,與記號的來源可能不同 → 平白對不上。)
    _url = build_authorize_url(cfg["client_id"], cfg["redirect_uri"],
                               state=login_state_with_sheet(_url_sheet(), silent_tag=_tag),
                               prompt=OAUTH_PROMPT_NONE)
    if not _url.startswith(GOOGLE_AUTH_URL + "?"):
        # 防禦:轉跳目標只可能是 Google authorize 端點(實務上不會發生;發生就講出來,不轉)
        print(f"[oauth_state] 1.0-B2 silent_reauth=skip reason={SILENT_SKIP_BAD_URL}")
        return False
    st.caption(OAUTH_SILENT_REAUTH_PENDING_MSG)
    st.html(_silent_redirect_script(_url), unsafe_allow_javascript=True)
    print(f"[oauth_state] 1.0-B2 silent_reauth={SILENT_REDIRECT}")
    return True


def _set_silent_marker(cfg: dict, tokens: dict, sheet_id: str) -> None:
    """登入強驗成功 → 網址掛記號 ＝ MAC(這個帳號的 sub, 回綁的 Sheet)。開關停用時不掛。

    算不出來(id_token 沒有 sub / 沒 client_secret)→ 不掛、記代碼。寫入失敗不擋登入主線,但要講出來(§1)。
    算得出來 → 本 session 記為「可重算記號」(`OAUTH_SILENT_ELIGIBLE_SESSION_KEY`,給 `sync_silent_marker`)。
    """
    if not _silent_reauth_enabled():
        return
    _tag = _silent_tag(cfg.get("client_secret", ""), decode_id_token_sub(tokens), sheet_id)
    if not _tag:
        print(f"[oauth_state] 1.0-B2 silent_reauth={SILENT_MARKER_NOT_SET_NO_SUB}")
        return
    st.session_state[OAUTH_SILENT_ELIGIBLE_SESSION_KEY] = True
    try:
        st.query_params[OAUTH_SILENT_MARKER_PARAM] = _tag
    except Exception as _e:  # noqa: BLE001
        print(f"[oauth_state] 1.0-B2 silent_reauth={SILENT_MARKER_SET_FAILED} "
              f"({type(_e).__name__}) —— 重新整理後需再按登入")


def _displayable_error_code(raw) -> str:
    """`?error=` → 標準代碼(在 `OAUTH_DISPLAYABLE_ERROR_CODES` 裡)原樣;其他 → 空字串。"""
    _code = sanitize_error_code(raw)
    return _code if _code in OAUTH_DISPLAYABLE_ERROR_CODES else ""


def _handle_oauth_error_callback(qp) -> None:
    """Google 帶 `?error=`(有或沒有 state)回來:清網址(保留網址上原有的 sheet)、藍色提示。

    **不** rerun、**不**轉跳、**不**換 token。網址記號此時本來就不在(redirect_uri 是固定的)
    ⇒ 下一次重新整理不會再靜默轉跳 —— 這是「Google 一直回 login_required 也不迴圈」的關鍵。

    燒不燒 nonce(稽核 SA2 SHOULD-2):**只有**靜默恢復(state 是三段)才 consume —— 那個 nonce 是靜默
    轉跳專用、不會再被誰用。~~只在「靜默失敗代碼」時 consume~~(稽核第二輪改為**任何**代碼:
    server_error / temporarily_unavailable 等也是同一個用過即丟的靜默 nonce;有意識的修改)。
    一般登入(兩段 state;例:在新分頁按了取消 → access_denied)**不** consume、不回綁 —— 否則原分頁上那顆
    登入鈕(同一個 nonce)再按一次會被當成重放擋下(紅字)。
    稽核第二輪 SHOULD-A:靜默 state 的任何錯誤都把 state 帶回的 Sheet 寫回 `?sheet=`(網址層級,
    見 `_clear_query_keep_sheet`)—— 修前非靜默代碼會連 Sheet 一起丟掉。
    """
    _code = _displayable_error_code(qp.get("error"))
    _reason = "absent"
    _ok, _got_sheet = False, ""
    if "state" in qp:
        _reason = "kept"
        _got_nonce, _sheet_in_state, _tag, _is_silent = _split_silent_state(qp.get("state"))
        if _is_silent:
            _ok, _reason = _nonce_store.consume(_got_nonce, _browser_binding())
            _got_sheet = _sheet_in_state
            st.session_state.pop("_oauth_state", None)
    st.session_state[OAUTH_SILENT_ATTEMPTED_SESSION_KEY] = True
    # 只記代碼(不在標準表的記成 other;state 只記 consume 的 reason / kept / absent)。
    # ⛔ 不記 nonce / sheet / 記號 / URL。
    print(f"[oauth_state] 1.0-B2 callback error={_code or 'other'} state={_reason}")
    # 回綁 session 只在「靜默 state 強驗通過」(與成功路徑同一個「只有 consume ok 才信 state 載荷」規則,
    # P2 F1);網址則保留 `?sheet=`:原本有就留,否則用靜默 state 帶回的那本(網址層級,見上)。
    if _ok and _got_sheet:
        st.session_state["portfolio_sheet_id"] = _got_sheet
        st.session_state["stock_portfolio_sheet_id"] = _got_sheet
    _clear_query_keep_sheet(_got_sheet)
    if _code in OAUTH_SILENT_FAILURE_ERROR_CODES:
        st.info(OAUTH_SILENT_REAUTH_FAILED_MSG)
    elif _code:
        st.info(OAUTH_LOGIN_INCOMPLETE_MSG.format(code=_code))
    else:
        st.info(OAUTH_LOGIN_INCOMPLETE_GENERIC_MSG)


def handle_oauth_callback() -> None:
    """OAuth callback：URL 帶 ?code=... 時自動換 token。

    app.py module body 在 sidebar 渲染前呼叫一次。
    """
    # v18.136 動態解析；session 設定變動時也要看得到
    cfg = _resolve_oauth_cfg()
    if cfg is None:
        return
    _qp = st.query_params
    if "error" in _qp and "code" not in _qp:
        _handle_oauth_error_callback(_qp)
        return
    if "code" in _qp and "gsheet_tokens" not in st.session_state:
        # SEC-2:唯一成功路徑 = server 端 nonce 表 consume ok(登記過、未過期、同一瀏覽器、一次性)。
        # 修前的 `_oauth_state_ok` 對「session 沒有期望值」(整頁轉跳後幾乎必然)與「URL 沒帶 state」
        # 一律放行 —— 那兩條放行路徑已刪除。P2:state = `nonce.sheetid`,只有 nonce 參與驗證。
        # 1.0-B2:靜默恢復的 state 是 `nonce.sheetid.記號`(三段);兩段以內與修前完全相同。
        _got_nonce, _got_sheet, _got_tag, _is_silent = _split_silent_state(_qp.get("state"))
        _ok, _reason = _nonce_store.consume(_got_nonce, _browser_binding())
        # 本 session 的 nonce 不論成敗都換新(已燒掉;下一個登入鈕用新的)。
        st.session_state.pop("_oauth_state", None)
        _enforce = _csrf_enforced()
        if not _ok:
            # 只記 reason code(⛔ 不記 nonce / cookie / code / token 值)。
            print(f"[oauth_state] SEC-2 callback state 驗證未通過 reason={_reason} "
                  f"enforce={'on' if _enforce else 'off'}")
            if _enforce:
                # 不 rerun、不自動轉跳 → 不會迴圈;清掉 ?code= 讓下一輪不再處理同一個授權碼。
                # 稽核第二輪:靜默恢復的回呼被拒(例:process 重啟 → unknown)→ Sheet 寫回網址(網址層級),
                # 一般登入照舊全清(⛔ 不信未驗證的 state 載荷,與修前相同)。
                _clear_query_keep_sheet(_got_sheet if _is_silent else "")
                st.error(OAUTH_STATE_REJECTED_MSG)
                return
        # P2 F1:**回綁 Sheet 只在 CSRF 強驗通過時執行** —— state 載荷只有 consume ok 才可信
        # (否則攻擊者可構造 `state=<任意>.<自己的Sheet>` 造成跨帳號 Sheet 注入)。
        # SEC-2 更正:修前 `_strong_state` 要求「本 session 有期望值」,而整頁轉跳後 session 是新的
        # ⇒ 正常登入路徑上幾乎恆為 False,P2 #639 的回綁實際上沒生效;現在 = consume ok,正常登入就會回綁。
        # 安全閥(enforce=off)放行的登入**不**回綁。
        _strong_state = _ok
        try:
            _tokens = exchange_code_for_tokens(
                _qp["code"], cfg["client_id"],
                cfg["client_secret"], cfg["redirect_uri"])
            if _is_silent:
                # 1.0-B2(稽核 SA1):靜默恢復 → 用**新換到的** sub 與 state 帶回的 Sheet 重算記號,
                # 定時比對。對不上(換了帳號 / 攻擊者的 Sheet / 記號被竄改)→ token 丟掉、不登入、不回綁、不掛記號。
                _sub = decode_id_token_sub(_tokens)
                _expect = _silent_tag(cfg.get("client_secret", ""), _sub, _got_sheet)
                if not (_expect and _got_tag
                        and hmac.compare_digest(_expect.encode("ascii"), _got_tag.encode("ascii"))):
                    del _tokens
                    print(f"[oauth_state] 1.0-B2 silent_reauth=reject reason="
                          f"{SILENT_REJECT_TAG_MISMATCH if _sub else SILENT_REJECT_NO_SUB}")
                    # 稽核第二輪 MUST-1(b):不登入、不回綁 session,但 Sheet 寫回網址 → 手動登入時照常回綁。
                    # 只有 consume ok 時才用 state 帶回的那本(安全閥放行的不信)。⛔ 不寫 `gs`。
                    _clear_query_keep_sheet(_got_sheet if _ok else "")
                    st.info(OAUTH_SILENT_MISMATCH_MSG)
                    return
            st.session_state["gsheet_tokens"] = _tokens
            st.session_state["gsheet_email"] = decode_id_token_email(_tokens)
            st.session_state.pop(OAUTH_LOGIN_EXPIRED_SESSION_KEY, None)   # 重新登入了 → 不再是「已逾時」
            st.session_state.pop(OAUTH_SILENT_ELIGIBLE_SESSION_KEY, None)  # 下面強驗掛記號時才重設
            # P2:把 state 便車帶回的 Sheet ID 回綁兩通道 + 重掛 ?sheet=(取代原本的
            # blanket clear —— 那正是把 ?sheet= 沖掉、逼使用者再繞組合管理的元凶之一)。
            # sheetid 已於 _split_silent_state 消毒;非憑證,回綁只是「還原上次用哪本」。
            st.query_params.clear()
            if _got_sheet and _strong_state:
                st.session_state["portfolio_sheet_id"] = _got_sheet
                st.session_state["stock_portfolio_sheet_id"] = _got_sheet
                try:
                    st.query_params["sheet"] = _got_sheet
                except Exception:  # noqa: BLE001 — query param 寫入失敗不擋登入主線(§1)
                    pass
            # 1.0-B2:只有 consume ok(強驗)的登入才掛靜默恢復記號;安全閥放行的不掛(退回 A 行為)。
            # 記號綁「這個帳號＋回綁的這本 Sheet」。
            if _strong_state:
                _set_silent_marker(cfg, _tokens, _got_sheet)
            _email = st.session_state.get("gsheet_email", "")
            st.success(f"✅ Google 登入成功{('：' + _email) if _email else ''}")
            st.rerun()
        except OAuthError as _oe:
            # 授權碼在 Google 端已是一次性;清掉 ?code= 免得下一輪拿已燒掉的 nonce 再報一次錯。
            # 稽核第二輪:靜默恢復且 consume ok → Sheet 寫回網址(網址層級);其他照舊全清。
            _clear_query_keep_sheet(_got_sheet if (_is_silent and _ok) else "")
            st.error(f"❌ OAuth 失敗：{_oe}")
