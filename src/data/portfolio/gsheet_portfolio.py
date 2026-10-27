"""Google Sheet 持股組合雲端儲存 (PR #5 + OAuth 擴充)

⚠️ §8.2.A EX-OAUTH-1(v19.159 團隊稽核擴充):本檔 L1 讀 `st.session_state`
(gsheet_tokens / portfolio_sheet_id,見下方 ready 檢查)屬 OAuth session lifecycle
(token 取用),非業務 UI。例外正式登錄於 CLAUDE.md §8.2.A EX-OAUTH-1。

Schema
======
- worksheet `portfolios`(ETF / legacy 持股組合)：
    name | ticker | lots | avg_price | updated_at
- worksheet `forward_test_picks`(前進式驗證選股凍結,見 _FT_HEADERS)
- worksheet `stock_watchlist`(個股**純代碼**觀察清單,Option B)：
    name | ticker | updated_at
  ⚠️ §1 反捏造:純代碼清單**不**寫張數/均價/任何價格,與 `portfolios` schema
  物理隔離(獨立分頁),避免哨兵假價污染。

多組命名 = 多列共用同一 worksheet；同一個 name 多列 = 該組合的所有持股 / 代碼。

認證（只有 OAuth；SEC-3 起網頁端**不再**以 Service Account 讀寫）
==========
- OAuth：使用者在 sidebar 用 Google 登入，自帶 Sheet
  - secrets：`[google_oauth]` 或 in-app wizard 設定（client_id/secret/redirect_uri）
  - 個人 Sheet ID：UI 輸入 → session_state['portfolio_sheet_id']
  - secrets `portfolio_sheet_id` 仍可當**預設 Sheet ID**（Sheet ID 不是憑證，存取仍要
    本人 OAuth token ＋ Sheet ACL）
- 未登入 → `_build_client()` 拋 `LoginRequiredError`，所有讀 / 寫 / Drive 函式一律 fail closed。
- ⚠️ SEC-3（修前）：未登入時 `_build_client()` 退回 secrets `[gcp_service_account]`，
  任何匿名訪客（含 `?sheet=` 任意 Sheet ID）都能以 SA 身分讀到 SA 有權限的私人 Sheet。
  Service Account 現在**只**給排程用（`gsheet_sa_reader` 讀 `os.environ`，與本檔無關）。

依賴
====
- gspread>=6.0
- google-auth>=2.0

呼叫端
======
- src/ui/tabs/portfolio_manager.py（📁 組合管理頁）— ETF 組合 + 個股清單的唯一管理入口

設計
====
- 純函式 API：is_configured / list_portfolios / load_portfolio / save_portfolio / delete_portfolio
- 例外不吞，往上拋給 caller（UI 層用 try/except 顯示 st.error）
- **讀取真正唯讀**（Sheet Safety 批 B1，客戶 2026-10-25 DEC-083）：list_* / load_* **零寫入** ——
  分頁不存在 ⇒ `SheetWorksheetMissingError`（或 `raise_if_missing=False` 時回 []，⛔ 不建分頁）；
  第一列欄名不符 ⇒ `SheetSchemaMismatchError`（⛔ 不改寫第一列）；空表 ⇒ []；權限 / 網路錯誤原樣上拋。
  修前讀取經 `_get_worksheet()`：分頁不存在就 `add_worksheet` + 寫表頭、表頭不符就覆寫第一列。
  建分頁只剩**明確寫入動作**（save_*）經 `_ws_for_write(create_if_missing=True)` 才會發生；
  delete_* 分頁不存在 → 回 0、不建。表頭不符時寫入一律在**任何寫入之前**拋錯（⛔ 不修表頭）。
- OAuth client 由 src.data.portfolio.oauth_state._get_oauth_client() 提供
  (v18.400 D4:原 oauth_state 誤放 src/ui/pages/,已歸位 src/data/portfolio/ 同層)
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import itertools
import math
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

try:
    import streamlit as st
except ImportError:
    st = None

from shared.oauth_session_policy import OAUTH_LOGIN_EXPIRED_MSG   # L0 SSOT:1.0-B2 逾時訊息
from shared.ttls import TTL_15MIN   # L0 SSOT(§3.3):Google Sheet 讀取快取 TTL


def _cache_data(**kwargs):
    """§8.2.A EX-CACHE-1:取 st.cache_data 當讀取快取;無 streamlit(純 .py)→ 退化 identity。

    根治 429:list/load 每次呼叫對 Sheets 打 4~5 個 read request,Streamlit 每次 rerun
    重跑 → 撞「每分鐘每使用者 60 讀取」配額。快取讓 rerun 命中快取(0 API),TTL 到期或
    寫入清快取才重抓。
    """
    if st is None:
        return lambda _f: _f
    return st.cache_data(**kwargs)


def clear_read_cache() -> None:
    """清掉 Google Sheet 讀取快取(list/load × Portfolio/Watchlist)。

    §5 可觀測性 + §1:寫入(save/delete)一律清 → 使用者自己的編輯即時可見,不服務髒資料;
    外部直接改 Sheet 者靠 TTL_15MIN 過期,或 UI 的「🔄 重新載入」手動呼叫本函式。
    SEC-1:快取住在 `_*_cached` 內部函式(鍵含身分),public 四支本身不再帶快取。
    ⚠️ B5(DEC-083):本函式清的是**所有使用者、所有 Sheet**。既有 caller(寫入後、側欄 🔄、舊戰情室 🔄)
    本批未改;新的「重新讀取」一律改用 `invalidate_my_read_cache()`(只失效本人 × 那本 Sheet)。
    """
    for _fn in (_list_portfolios_cached, _load_portfolio_cached,
                _list_stock_watchlists_cached, _load_stock_watchlist_cached,
                _read_sheet_title_cached):          # 👤 我的 P1:Sheet 標題(read_sheet_title)
        _clear = getattr(_fn, 'clear', None)
        if callable(_clear):
            _clear()


_WORKSHEET_NAME = 'portfolios'
_HEADERS = ['name', 'ticker', 'lots', 'avg_price', 'updated_at']

# ── Option B:個股**純代碼**觀察清單(§3.3 worksheet 名稱 + headers 具名常數)──────
# §1 反捏造:此分頁**只**存 name/ticker/updated_at 三欄,無張數/均價/哨兵/任何價格;
# 與 `portfolios`(5 欄含價格)物理隔離(獨立 worksheet),互不污染。
_STOCK_WATCHLIST_WORKSHEET = 'stock_watchlist'
_STOCK_WATCHLIST_HEADERS = ['name', 'ticker', 'updated_at']

# §3.3 SSOT:個股 新建 Sheet 的專屬 Drive 資料夾名稱(與 ETF 建的 Sheet 物理分隔)。
_STOCK_DRIVE_FOLDER_NAME = '台股 Dashboard（個股組合）'

# ── §3.3 session-key SSOT:個股 / ETF 雲端儲存分家(Phase 1)──────────────
# 兩條 session channel,各自獨立指向不同 Google Sheet,互不污染:
#   PORTFOLIO_SHEET_KEY       — ETF 組合 + legacy(含 secrets 預設 Sheet ID fallback;
#                               Sheet ID 非憑證,讀寫仍須 OAuth 登入,SEC-3);
#                               forward-test 亦沿用此 legacy 通道(_get_active_sheet_id)。
#   STOCK_PORTFOLIO_SHEET_KEY — 個股組合專用(session-only,無 secrets fallback)。
PORTFOLIO_SHEET_KEY = 'portfolio_sheet_id'
STOCK_PORTFOLIO_SHEET_KEY = 'stock_portfolio_sheet_id'


def _oauth_active() -> bool:
    """OAuth 模式:已設 OAuth Client + 已登入 + 有 sheet id。"""
    if st is None:
        return False
    try:
        from src.data.portfolio.oauth_state import is_oauth_configured
    except Exception:
        return False
    if not is_oauth_configured():
        return False
    if not st.session_state.get('gsheet_tokens'):
        return False
    if not _get_active_sheet_id():
        return False
    return True


#: SEC-3:未登入時所有讀 / 寫 / Drive 呼叫的唯一錯誤訊息(§3.3 具名常數)。
LOGIN_REQUIRED_MSG = '請先登入 Google 才能讀取持股'

#: 1.0-B2:access_token 過期且沒有 refresh_token(靜默恢復登入的常態,約 1 小時)時的訊息。
#: ⛔ session 中途**不**自動轉跳 Google(v19.63 迴圈教訓);網址記號留著 ⇒ 重新整理即可靜默恢復。
#: SSOT 在 L0(`shared.oauth_session_policy`,L5 畫灰卡也用同一句);此名保留給既有 caller / 測試。
LOGIN_EXPIRED_MSG = OAUTH_LOGIN_EXPIRED_MSG


class LoginRequiredError(RuntimeError):
    """SEC-3:沒有 OAuth 登入(或 OAuth client 建不起來)就不碰 Google。

    繼承 RuntimeError ⇒ 既有 `except RuntimeError` / `except Exception` 的 caller 行為不變
    (照舊顯示錯誤 / graceful 跳過),只是**不會再**以 Service Account 讀到資料。
    """


def is_configured() -> bool:
    """OAuth 已登入＋有 Sheet ID 才算可用(SEC-3:不再因 SA secrets 存在就回 True)。"""
    return _oauth_active()


def _get_active_sheet_id() -> str:
    """取使用者輸入的 sheet id；沒有則回 secrets `portfolio_sheet_id`(預設 Sheet ID)。

    Sheet ID 不是憑證:回傳值只決定「讀哪一本」,讀不讀得到仍由 `_build_client()`
    (必須 OAuth 登入,SEC-3)＋ Google ACL 決定。

    ⚠️ 這是 **ETF / legacy** 通道(PORTFOLIO_SHEET_KEY + secrets fallback);
    forward-test(_ft_worksheet)亦沿用。個股組合請改用 `_get_active_stock_sheet_id()`。
    """
    if st is None:
        return ''
    sid = str(st.session_state.get(PORTFOLIO_SHEET_KEY, '') or '').strip()
    if sid:
        return sid
    try:
        return str(st.secrets.get(PORTFOLIO_SHEET_KEY, '') or '').strip()
    except (KeyError, FileNotFoundError, AttributeError):
        return ''


def _get_active_stock_sheet_id() -> str:
    """個股組合專用 sheet id — 只讀 session channel `STOCK_PORTFOLIO_SHEET_KEY`。

    與 ETF/legacy 分家(Phase 1):**不** fallback 到 secrets(SA/secrets 仍屬
    ETF-legacy 專用),也**不**讀 `PORTFOLIO_SHEET_KEY`。未設定 → 回空字串
    (由 caller 依 §1 fail-loud 處理,不靜默借用 ETF sheet)。
    """
    if st is None:
        return ''
    return str(st.session_state.get(STOCK_PORTFOLIO_SHEET_KEY, '') or '').strip()


@dataclass(frozen=True)
class SessionBindingSnapshot:
    """本 session 的綁定原始值(👤 我的 P1;消毒後)。**純讀**,⛔ 不判定哪一本是 active(那是 L3 的事)。

    Attributes:
        portfolio_channel: ETF / legacy 那一格(`PORTFOLIO_SHEET_KEY`)。
        stock_channel: 個股那一格(`STOCK_PORTFOLIO_SHEET_KEY`)。
        deploy_default: secrets `portfolio_sheet_id`(部署預設;⛔ 不是使用者的選擇,新版 UI 不當 active)。
    """

    portfolio_channel: str = ''
    stock_channel: str = ''
    deploy_default: str = ''


def session_binding_snapshot() -> SessionBindingSnapshot:
    """讀本 session 兩格綁定與 secrets 部署預設(都經 L0 `sanitize_sheet_id`)。**純讀,不碰網路 / Google。**

    secrets 讀不到的處理與 `_get_active_sheet_id()` 相同(沒有檔 / 沒有 key ＝ 沒設定);格式錯誤等由
    呼叫端另以 `_secrets_read_error()` 分辨(同 L3 `get_binding_state`)。
    唯一 caller:L3 `portfolio_binding_service.get_active_sheet()`。
    """
    if st is None:
        return SessionBindingSnapshot()
    from shared.sheet_id import sanitize_sheet_id
    _etf = sanitize_sheet_id(st.session_state.get(PORTFOLIO_SHEET_KEY))
    _stk = sanitize_sheet_id(st.session_state.get(STOCK_PORTFOLIO_SHEET_KEY))
    try:
        _dflt = sanitize_sheet_id(st.secrets.get(PORTFOLIO_SHEET_KEY, ''))
    except (KeyError, FileNotFoundError, AttributeError):
        _dflt = ''
    return SessionBindingSnapshot(portfolio_channel=_etf, stock_channel=_stk, deploy_default=_dflt)


def _has_oauth_tokens() -> bool:
    """是否已透過 OAuth 登入（不要求 Sheet ID 已設定）。

    `_oauth_active()` 額外要求 sheet_id，會擋掉「列檔挑 Sheet」的場景；
    建構 client 只需要看「有沒有登入 + OAuth Client 有設」。

    用 `is_oauth_configured()` 動態解析（取代 stale module-level `_oauth_configured`）—
    in-app wizard 套用 OAuth config 後不必重啟 streamlit 也能立刻生效。
    """
    if st is None:
        return False
    try:
        from src.data.portfolio.oauth_state import is_oauth_configured
    except Exception:
        return False
    if not is_oauth_configured():
        return False
    if not st.session_state.get('gsheet_tokens'):
        return False
    return True


def _oauth_import_error() -> str:
    """`_has_oauth_tokens()` 回 False 時，分出「OAuth 模組根本載不進來」這一種（純讀）。

    `_has_oauth_tokens()` 在 `oauth_state` import 失敗時回 False —— 既有行為，
    其他 caller（binder / 組合管理 / `_build_client` / list_* 系列）依賴它，**一字不動**。
    但那會把一次**故障**讀成「沒登入」。本函式只重做同一個 import（沒有 streamlit →
    同 `_has_oauth_tokens()` 的第一道 gate，回空字串），把被吞掉的例外以 `repr` 交回；
    載得進來 → 空字串。**不碰 session / secrets / 網路。**

    ⚠️ 「OAuth Client 沒設定」（`is_oauth_configured()` 為 False）**不在這裡** ——
    那是「還沒設定」，不是讀取失敗（見 `portfolio_binding_service.get_binding_state`）。
    唯一 caller：L3 `portfolio_binding_service.get_binding_state()`。
    """
    if st is None:
        return ''
    try:
        from src.data.portfolio.oauth_state import is_oauth_configured
    except Exception as _e:  # noqa: BLE001 — 交回字串給 caller 判紅，不吞
        return repr(_e)
    del is_oauth_configured   # 只驗「載不載得進來」（與 `_has_oauth_tokens()` 同一行 import）
    return ''


def _secrets_read_error() -> str:
    """分出「secrets 檔**格式錯誤**／**讀取例外**」與「真的沒有 secrets 檔」（純讀）。

    `_get_active_sheet_id()` 把 `FileNotFoundError` 吞成「沒設定」、`oauth_state._safe_secret()`
    把**所有**例外吞成預設值 —— 兩者都是既有行為、其他 caller 依賴它們，**一字不動**。
    但 Streamlit 在 secrets.toml **解析失敗**時丟的 `StreamlitSecretNotFoundError` 正是
    `FileNotFoundError` 的子類（與「檔案不存在」同一類），於是一次**設定壞掉**被讀成「還沒設定」。

    分法**只看 Streamlit 自己的例外鏈，不比對訊息字串**（訊息可被部署端客製）：
      · 檔案不存在 → Streamlit 直接 `raise`（`__cause__` 為 None）→ 空字串（**真的沒設定**）；
      · TOML 解析失敗 → Streamlit `raise ... from <TomlDecodeError/TypeError>`（`__cause__` 非 None）
        → 交回例外**型別名**；
      · 其他例外（例：編碼錯、權限錯）→ 讀取例外，交回例外**型別名**。
    ⚠️ **只交型別名、⛔ 不交 `repr` / 訊息**（這一支讀的是金鑰檔）：實測（2026-09-26，
    streamlit 1.59.2 ＋ toml）TOML 解析器有些錯誤訊息會把**已解析的內容**（含金鑰值）整包串進去；
    檔案裡有一個非 UTF-8 位元組時，`UnicodeDecodeError` 的 `repr` 會帶出**整段檔案原文**；
    Streamlit 的訊息本文另含檔案路徑。交回值會被畫在紅卡上，故一律只留型別名。
    ⚠️ 分不出、照舊當「沒設定」的（據實記錄，不猜）：Streamlit 以 `.format()` 組訊息時
    訊息本身含大括號（例：TOML 重複的表頭）→ 它自己丟 `KeyError`，被 `Mapping.get` 吞成預設值；
    以及目錄型 secrets 的路徑錯誤（沒有 `__cause__`）。
    **不碰 session / 網路。** 唯一 caller：L3 `portfolio_binding_service.get_binding_state()`。
    """
    if st is None:
        return ''
    try:
        st.secrets.get(PORTFOLIO_SHEET_KEY, '')
    except FileNotFoundError as _e:
        return type(_e).__name__ if _e.__cause__ is not None else ''
    except (KeyError, AttributeError):
        return ''   # 同 `_get_active_sheet_id()`：沒有這個 key / 沒有 secrets 物件 ＝ 沒設定
    except Exception as _e:  # noqa: BLE001 — 交回字串給 caller 判紅，不吞
        return type(_e).__name__
    return ''


def _login_needs_reauth() -> bool:
    """session 的 token 已過期(或沒有 expires_at)且**沒有 refresh_token** ⇒ 無法續期。純讀。

    1.0-B2:靜默恢復登入(`prompt=none`)Google 通常不發 refresh_token ⇒ 約 1 小時後會走到這裡。
    判斷與 `infra.oauth.ensure_fresh_tokens` 一致(同一支 `is_token_expired`,沒 expires_at 視為過期),
    只是在它丟出原始 `OAuthError` 之前先攔下,改成看得懂的 `LoginRequiredError`。
    """
    if st is None:
        return False
    _toks = st.session_state.get('gsheet_tokens')
    if not isinstance(_toks, Mapping) or not _toks or _toks.get('refresh_token'):
        return False
    from infra.oauth import is_token_expired
    return is_token_expired(dict(_toks))


def _expire_session_login() -> None:
    """清掉本 session 的登入(token / email),並標記本 session 不再自動靜默恢復。

    ⚠️ 網址記號**刻意保留**:使用者重新整理 ⇒ 新 session ⇒ 靜默恢復一次。
    標記 `OAUTH_SILENT_ATTEMPTED_SESSION_KEY` ⇒ 本 session 下一輪 rerun **不會**自動轉跳(session 中途不轉)。
    標記 `OAUTH_LOGIN_EXPIRED_SESSION_KEY` ⇒ 之後「沒有 token」的 `LoginRequiredError` 仍帶逾時訊息、
    頁面畫灰色「登入已逾時」卡(稽核 SA2 MUST-1);下一次登入成功 / 登出時由 oauth_state 清掉。
    """
    from shared.oauth_session_policy import (
        OAUTH_LOGIN_EXPIRED_SESSION_KEY,
        OAUTH_SILENT_ATTEMPTED_SESSION_KEY,
    )
    for _k in ('gsheet_tokens', 'gsheet_email'):
        st.session_state.pop(_k, None)
    st.session_state[OAUTH_SILENT_ATTEMPTED_SESSION_KEY] = True
    st.session_state[OAUTH_LOGIN_EXPIRED_SESSION_KEY] = True
    print('[gsheet_portfolio] 1.0-B2 login_expired reason=no_refresh_token')


def login_expired() -> bool:
    """本 session 的登入是否因「token 過期且無 refresh_token」被清掉、且之後還沒重新登入。純讀。

    唯一用途:讓 L3 / 頁面把「沒有 token」分成「從沒登入」與「登入已逾時」兩種說法(都是灰色有效態)。
    """
    if st is None:
        return False
    from shared.oauth_session_policy import OAUTH_LOGIN_EXPIRED_SESSION_KEY
    try:
        return bool(st.session_state.get(OAUTH_LOGIN_EXPIRED_SESSION_KEY))
    except Exception:  # noqa: BLE001 — 讀不到 session ⇒ 當作沒有逾時(退回一般「請先登入」說法)
        return False


def _login_required_message() -> str:
    """「沒有 token」時該說哪一句:逾時旗標在 → 逾時訊息;否則 → 請先登入。"""
    return LOGIN_EXPIRED_MSG if login_expired() else LOGIN_REQUIRED_MSG


def _build_client():
    """以**本人 OAuth** 建一個 gspread client;沒登入 / client 建不起來 → `LoginRequiredError`。

    1.0-B2:token 過期且無 refresh_token → 清掉 session 登入並拋 `LoginRequiredError(LOGIN_EXPIRED_MSG)`
    (取代深處的原始 `OAuthError`)。

    OAuth 判斷只看「有 token + 有 OAuth Client」，不綁 sheet_id —
    讓「列檔挑 Sheet」流程能在 sheet_id 還沒設定前先建 client。

    SEC-3:修前此處在 OAuth 不可用時退回 secrets `[gcp_service_account]` —— 匿名訪客因此能以
    SA 身分讀到 SA 有權限的任何 Sheet(含 `?sheet=` 帶進來的、與 secrets 預設的那本)。
    現在**沒有任何退路**:所有讀 / 寫 / Drive 函式都經過這裡,故一律 fail closed。
    """
    if not _has_oauth_tokens():
        raise LoginRequiredError(_login_required_message())
    if _login_needs_reauth():
        _expire_session_login()
        raise LoginRequiredError(LOGIN_EXPIRED_MSG)
    from src.data.portfolio.oauth_state import _get_oauth_client
    cli = _get_oauth_client()
    if cli is None:
        raise LoginRequiredError(LOGIN_REQUIRED_MSG)
    return cli


# ── SEC-1:讀取快取依「實際呼叫 Google 的身分」隔離 ──────────────────────────────
# `st.cache_data` 是 **server 級、跨 session 共用** 的快取。修前四支讀取函式的快取鍵只有
# (name, sheet_id, keep_blank),不含身分 → A 讀過後,B / 未登入者 / 失效 token 以相同參數
# 呼叫就直接拿到 A 的資料,完全不經 Google ACL;`sheet_id=None` 時鍵還與 session 的 Sheet 無關。
# 修法:public 函式先解析 (身分, 實際 sheet_id),再呼叫鍵含兩者的 `_*_cached` 內部函式;
# 解析不出身分 → **不碰快取**,直接走原讀取路徑(`_build_client` 照舊 fail loud)。
#: 身分種類前綴(§3.3 具名常數)。SEC-3 起只剩 OAuth 一種身分(SA 前綴與「釘住身分種類」的
#: ContextVar 隨 SA fallback 一併移除 —— 只有一種 client,不再有「鍵與實際 client 種類不符」的可能)。
_IDENTITY_KIND_OAUTH = 'oauth'
#: 1.0-B2:沒有 refresh_token 時改用 id_token 的 `sub`(Google 帳號永久 ID)。與上面分開的前綴 ⇒
#: 兩種憑證來源的指紋空間互不重疊。
_IDENTITY_KIND_OAUTH_SUB = 'oauth_sub'


def _identity_fingerprint(kind: str, credential: str) -> str:
    """`<kind>:<sha256>` —— 快取鍵只放單向雜湊,⛔ 不放 token / 帳號原文(st 快取鍵可被他處觀察)。"""
    _digest = hashlib.sha256(f'{kind}\x00{credential}'.encode('utf-8')).hexdigest()
    return f'{kind}:{_digest}'


def _cache_identity() -> str:
    """回傳 `_build_client()` **此刻會用來呼叫 Google 的身分** 的指紋;定不出身分 → 空字串。

    判斷與 `_build_client()` 相同(只有 OAuth;SEC-3 起沒有 SA 身分):
      · OAuth:指紋取 `refresh_token`(同一授權在 access_token refresh 後**不變** ⇒ refresh 只是
        同一身分,照常命中);沒有 refresh_token(1.0-B2 靜默恢復登入的常態)→ 取 id_token 的 `sub`
        (同一人每次靜默恢復都相同、不同人必不同 ⇒ **仍是每人一格**,不會落進共用格);
        連 `sub` 都沒有才退用 `access_token`(每次換新 ⇒ 只是 cache miss,安全側)。
        全無 → 空字串(此時 `_get_oauth_client` 本來就會拋 OAuthError)。
      · token 已過期且無 refresh_token(`_login_needs_reauth`)→ 空字串 ⇒ 不碰快取、走原路徑,
        由 `_build_client` 清掉 session 並拋 `LoginRequiredError(LOGIN_EXPIRED_MSG)`。
      · 未登入 → 空字串(`_build_client` 會拋 `LoginRequiredError`)。
    ⚠️ 空字串的意思是「**不准用快取**」,不是「匿名身分」—— caller 必須繞過快取(見
    `_identity_scoped_read`),否則未登入者會命中彼此的快取項。
    """
    if st is None:
        return ''
    if _has_oauth_tokens():
        _toks = st.session_state.get('gsheet_tokens')
        if not isinstance(_toks, Mapping):
            return ''
        _rt = str(_toks.get('refresh_token') or '')
        if _rt:
            return _identity_fingerprint(_IDENTITY_KIND_OAUTH, _rt)
        if _login_needs_reauth():
            return ''
        from infra.oauth import decode_id_token_sub
        _sub = decode_id_token_sub(dict(_toks))
        if _sub:
            return _identity_fingerprint(_IDENTITY_KIND_OAUTH_SUB, _sub)
        _cred = str(_toks.get('access_token') or '')
        return _identity_fingerprint(_IDENTITY_KIND_OAUTH, _cred) if _cred else ''
    return ''


def _require_identity(identity: str) -> None:
    """快取 miss 真要打 Google 前,再確認身分沒在解析後變掉(防禦:鍵與實際呼叫者必須一致)。"""
    if _cache_identity() != identity:
        raise RuntimeError('Google Sheet 讀取身分在解析後改變 —— 拒絕寫入快取,請重新整理頁面')


def _run_as_identity(identity: str, raw_fn, **kwargs):
    """快取 miss 時執行 `raw_fn`:先驗身分未變(鍵上的身分 ＝ 實際呼叫 Google 的身分)。

    SEC-3 起 `_build_client` 只會建本人 OAuth client(無 SA 退路),故不再需要把身分種類
    釘進 ContextVar;OAuth client 建不起來 → `LoginRequiredError`(例外不入快取)。
    """
    _require_identity(identity)
    return raw_fn(**kwargs)


def _identity_scoped_read(cached_fn, raw_fn, **kwargs):
    """有身分 → `cached_fn(identity, **kwargs, read_gen=…)`(鍵含身分 ＋ 本人×本 Sheet 的失效世代);
    無身分 → `raw_fn(**kwargs)`(不碰快取)。"""
    _identity = _cache_identity()
    if not _identity:
        return raw_fn(**kwargs)
    return cached_fn(_identity, **kwargs,
                     read_gen=_read_generation(_identity, str(kwargs.get('sheet_id') or '')))


# ── Sheet Safety 批 B5（DEC-083）:只失效「本人 × 這本 Sheet」的讀取快取 ─────────────────
# 客戶原文:「重新讀取不得默認清除所有使用者的全域 cache。……只失效目前使用者／active Sheet／
# 相關 read cache。……不得用全域 `.clear()` 假裝完成。」
# 做法:`st.cache_data` 沒有「只清某些鍵」的 API(`.clear()` 只能清整支函式的**所有**項目),
# 所以不清 —— 改把一個「失效世代」放進快取鍵:四支 `_*_cached` 多收一個**不加底線**的參數
# `read_gen`(底線參數不進快取鍵),值由下表決定。「重新讀取」＝ 把 (本人指紋, 那本 Sheet) 的世代
# 換成全域遞增計數器的新值 ⇒ 本人讀那本 Sheet 時鍵變了 ⇒ 重抓;別人、本人的別本 Sheet 鍵不變 ⇒ 照舊命中。
# 舊世代的快取項不會再被讀到,15 分鐘(TTL)後由 Streamlit 自然淘汰。
# 表的鍵:(身分指紋, sheet_id) ＝ 本人那本;(`_READ_GEN_ANY_IDENTITY`, sheet_id) ＝ 那本 Sheet 的所有人。
# ⚠️ 已知限制(據實):表在**本 process 記憶體**;多 replica 部署時各 replica 的 `st.cache_data` 本來也各自
# 獨立,失效只作用於收到這次請求的那一台(與全域 `clear_read_cache()` 同一個範圍)。process 重啟 ⇒
# 表與快取一起歸零。
_READ_GEN_ANY_IDENTITY = '*'
_READ_GEN_LOCK = threading.Lock()
_READ_GEN_COUNTER = itertools.count(1)
#: (身分指紋 / '*', sheet_id) → (世代, 換代時刻 time.monotonic())。
_READ_GEN: dict[tuple[str, str], tuple[int, float]] = {}


def _read_generation(identity: str, sheet_id: str) -> str:
    """本人 × 這本 Sheet 目前的快取世代字串(`<本人世代>.<全體世代>`;沒換過代 → `0.0`)。"""
    with _READ_GEN_LOCK:
        _mine = _READ_GEN.get((identity, sheet_id))
        _all = _READ_GEN.get((_READ_GEN_ANY_IDENTITY, sheet_id))
    return f'{_mine[0] if _mine else 0}.{_all[0] if _all else 0}'


def _bump_read_generation(identity: str, sheet_ids) -> int:
    """把 (identity, sid) 換新世代;順手清掉換代超過 TTL_15MIN 的舊表項。回換代的筆數。

    清舊表項是安全的:某鍵換代時刻 t0 超過 TTL ⇒ 世代 0 的快取項全都建於 t0 之前、早已過期
    ⇒ 該鍵退回 0 不會讀到任何舊資料;計數器全域遞增、不重用 ⇒ 之後再換代必是沒見過的新值。
    """
    _now = time.monotonic()
    _n = 0
    with _READ_GEN_LOCK:
        for _k in [k for k, (_g, _t) in _READ_GEN.items() if _now - _t > TTL_15MIN]:
            del _READ_GEN[_k]
        for _sid in sheet_ids:
            _READ_GEN[(identity, _sid)] = (next(_READ_GEN_COUNTER), _now)
            _n += 1
    return _n


def _target_sheet_ids(sheet_ids) -> list[str]:
    """明確給的 sheet_ids;沒給 → 目前 session 綁的兩通道(去空白、去重、保序)。"""
    _raw = list(sheet_ids) or [_get_active_sheet_id(), _get_active_stock_sheet_id()]
    _out: list[str] = []
    for _s in _raw:
        _s = str(_s or '').strip()
        if _s and _s not in _out:
            _out.append(_s)
    return _out


def invalidate_my_read_cache(*sheet_ids: str) -> int:
    """「重新讀取」:只讓**目前這位使用者**讀這幾本 Sheet(沒給 → 目前綁定的那本 / 兩通道)時重抓。

    別的使用者、本人的其他 Sheet、forward-test 以外的快取一律不動;⛔ 不呼叫任何 `.clear()`。
    沒有身分(未登入 / 登入已逾時)→ no-op 回 0(那時讀取本來就不經快取)。回換代筆數。
    """
    _identity = _cache_identity()
    if not _identity:
        return 0
    return _bump_read_generation(_identity, _target_sheet_ids(sheet_ids))


def invalidate_sheet_read_cache(*sheet_ids: str) -> int:
    """讓**所有使用者**讀這幾本 Sheet 時重抓(例:寫入那本之後)。只動指定的 Sheet;⛔ 不 `.clear()`。

    本批尚無 caller 改用(寫入路徑仍呼叫既有的全域 `clear_read_cache()`,B5 指派「不動既有全域清除」),
    提供給後續把寫入後的全域清除收斂成「只清那本」時使用(見交付報告殘留項)。
    """
    _ids = _target_sheet_ids(sheet_ids)
    return _bump_read_generation(_READ_GEN_ANY_IDENTITY, _ids) if _ids else 0


# ── Sheet Safety 批 B1（DEC-083）:讀取真正唯讀 ───────────────────────────────────
# 客戶原文:「禁止:read → worksheet 不存在 → create worksheet;禁止:read → header/schema 不符 →
# rewrite 第一列。……任何初始化／migration／repair:必須拆成明確 write action,不得藏在 read helper。」
# ~~`_get_worksheet()`(取得或建立分頁並確保表頭)＋ `_col_letter()`~~(有意識的移除,⛔ 不是漏刪:
# 前者正是被禁的「讀取時建分頁 / 覆寫第一列」;後者只服務它的表頭覆寫範圍,移除後 0 caller)。
#: 讀取狀態(§3.3;快取存 `(狀態, 內容)` ⇒ 「分頁不存在」也進快取,不會每輪 rerun 重打 Google)。
READ_OK = 'ok'
READ_EMPTY = 'empty'                          # 分頁在、但整張表是空的(連表頭都沒有)
READ_WORKSHEET_MISSING = 'worksheet_missing'  # 這本 Sheet 沒有該分頁(⛔ 讀取不建)
READ_SCHEMA_MISMATCH = 'schema_mismatch'      # 第一列欄名與預期不符(⛔ 讀取不修)

#: 表頭狀態(`_header_state` 回傳)。
_HEADER_EMPTY = 'empty'
_HEADER_OK = 'ok'
_HEADER_MISMATCH = 'mismatch'


class SheetWorksheetMissingError(RuntimeError):
    """這本 Sheet 沒有指定分頁。讀取時**不**建立(B1);繼承 RuntimeError ⇒ 既有 `except` 行為不變。"""

    def __init__(self, worksheet_name: str):
        self.worksheet_name = worksheet_name
        super().__init__(
            f'這本 Sheet 裡沒有「{worksheet_name}」分頁。讀取時系統不會自動建立分頁，'
            f'也不會改動你的 Sheet；之後用「儲存」寫入時才會建立。')


class SheetSchemaMismatchError(RuntimeError):
    """分頁第一列欄名與預期不符。讀取 / 寫入都**不**修表頭(B1);訊息⛔ 不回顯使用者的表頭內容。"""

    def __init__(self, worksheet_name: str, expected_headers, *, writing: bool = False):
        self.worksheet_name = worksheet_name
        self.expected_headers = tuple(expected_headers)
        _tail = '這次沒有寫入任何東西，Sheet 維持原狀。' if writing else '系統不會自動修改你的資料。'
        super().__init__(
            f'這本 Sheet 的「{worksheet_name}」分頁第一列欄名和系統預期的不一樣，{_tail}'
            f'請把第一列從 A 欄起依序改成：{"、".join(self.expected_headers)}'
            f'（右邊可以自己加欄）。')


class SheetNotConfiguredError(RuntimeError):
    """還沒選 Sheet(session 與 secrets 都沒有 Sheet ID)。訊息與修前的 RuntimeError 逐字相同。"""


def _open_spreadsheet(sheet_id: str | None):
    """開 Spreadsheet(唯讀動作)。sheet_id=None / 空 → legacy `_get_active_sheet_id()`。"""
    _sid = sheet_id or _get_active_sheet_id()
    if not _sid:
        raise SheetNotConfiguredError('尚未設定 Sheet ID（OAuth 模式請在雲端儲存區塊輸入）')
    return _build_client().open_by_key(_sid)


def _ws(*, sheet_id: str | None = None, worksheet_name: str = _WORKSHEET_NAME):
    """**只開不建**:取得 worksheet handle;分頁不存在 → `SheetWorksheetMissingError`。⛔ 零寫入。

    每次重新建立（OAuth token 可能 refresh）。sheet_id=None(或空)→ legacy active sheet
    (ETF / forward-test);非空 → 開 **那本** sheet(個股組合分家用)。表頭**不**在這裡檢查
    (讀取端 `_read_records`、寫入端各 save/delete 自己以 `_header_state` 判)。
    """
    import gspread

    sh = _open_spreadsheet(sheet_id)
    try:
        return sh.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        raise SheetWorksheetMissingError(worksheet_name) from None


def _ws_for_write(*, sheet_id: str | None = None, worksheet_name: str = _WORKSHEET_NAME,
                  create_if_missing: bool):
    """寫入用 worksheet:先 `_ws`(只開);分頁不存在時 `create_if_missing=True` 才建(明確寫入動作),
    否則回 None(caller 自己決定「沒東西可刪」)。

    建出來的是**空**分頁:表頭由 caller 的整表寫入(`_write_whole_sheet`)一次寫上,不另寫一次。
    """
    try:
        return _ws(sheet_id=sheet_id, worksheet_name=worksheet_name)
    except SheetWorksheetMissingError:
        if not create_if_missing:
            return None
    print(f'[gsheet_portfolio] B1 寫入建立分頁 worksheet={worksheet_name}')
    return _open_spreadsheet(sheet_id).add_worksheet(title=worksheet_name, rows=200, cols=10)


def _header_state(values: list[list[Any]], headers: list[str]) -> str:
    """整張表的原字串 → `_HEADER_EMPTY` / `_HEADER_OK` / `_HEADER_MISMATCH`(純函式)。

    - 整張表沒有任何非空白格 → EMPTY。
    - 第一列整列空白、下面卻有資料 → MISMATCH(不知道哪一列才是表頭,⛔ 不猜)。
    - 本分頁的欄(`headers`)在第一列重複 → MISMATCH(不知道該讀哪一欄,同批 Z12 D1-n6)。
    - 第一列從 A 欄起 ＝ `headers` → OK(右邊使用者自加欄不影響)。
    - 第一列只是 `headers` 的**前段**(例:只有 name/ticker/lots,批 M12 窄表)且沒有任何資料
      落在表頭寬度之外 → OK(缺的欄讀成缺值;寫入時補齊表頭 —— 那是明確寫入動作)。
    - 其他 → MISMATCH。
    """
    rows = [list(r) for r in (values or [])]
    if not any(not _is_blank_cell(c) for r in rows for c in r):
        return _HEADER_EMPTY
    first = rows[0]
    _filled = [i for i, c in enumerate(first) if not _is_blank_cell(c)]
    if not _filled:
        return _HEADER_MISMATCH
    if _header_has_duplicates(first, headers):
        return _HEADER_MISMATCH
    n = len(headers)
    if list(first[:n]) == list(headers):
        return _HEADER_OK
    width = _filled[-1] + 1
    if (width < n and list(first[:width]) == list(headers[:width])
            and not any(not _is_blank_cell(c) for r in rows[1:] for c in r[width:])):
        return _HEADER_OK
    return _HEADER_MISMATCH


def _require_writable_header(existing: list[list[Any]], headers: list[str],
                             worksheet_name: str) -> None:
    """寫入前的表頭關卡:MISMATCH → **任何寫入之前** `SheetSchemaMismatchError`(⛔ 不修表頭)。"""
    if _header_state(existing, headers) == _HEADER_MISMATCH:
        raise SheetSchemaMismatchError(worksheet_name, headers, writing=True)


def _write_header(old_header: list[Any], headers: list[str]) -> list[Any]:
    """寫入時的表頭:前段釘 `headers`(表頭狀態已過關 ⇒ 與原表頭相同,或原表頭是它的前段),
    使用者在右邊自加的表頭格原樣保留。"""
    return list(headers) + list(old_header[len(headers):])


#: 讀取時保留原字串、**不**轉數字的欄（批 Z12 D1-n1:名稱／代號是字串,`0050` 不可讀成 50）。
_TEXT_COLS = ('name', 'ticker')


def _all_records(*, sheet_id: str | None = None,
                 worksheet_name: str = _WORKSHEET_NAME,
                 headers: list[str] = _HEADERS) -> list[dict[str, Any]]:
    """回傳全表（含 header 後的所有列）為 dict list（預設 portfolios 分頁）。**零寫入。**

    逐列轉換同 `_sheet_record`（即 gspread `get_all_records()`,但名稱／代號保留原字串）。
    空表（連表頭都沒有）→ []。分頁不存在 → `SheetWorksheetMissingError`;第一列欄名不符 →
    `SheetSchemaMismatchError`(兩者都⛔ 不修;由 `_read_status` 轉成可快取的狀態)。
    批 Z12（D1-n6）:只有**本分頁的欄**（`headers`）重複才算錯 —— 使用者自加欄或多欄空白
    表頭重名不影響;本分頁的欄重複 ＝ 不知該讀哪一欄 → 表頭不符（§1:不讀錯欄）。
    （修前那一種交 gspread `get_all_records()` 拋它自己的錯;現改為具名例外,同樣讀不到任何列。）
    權限 / 網路 / 找不到 Sheet 等例外原樣上拋(不進快取)。
    """
    ws = _ws(sheet_id=sheet_id, worksheet_name=worksheet_name)
    values = ws.get_all_values()
    _state = _header_state(values, headers)
    if _state == _HEADER_EMPTY:
        return []
    if _state == _HEADER_MISMATCH:
        raise SheetSchemaMismatchError(worksheet_name, headers)
    return [_sheet_record(values[0], r) for r in values[1:]]


def _read_status(fn, **kwargs) -> tuple[str, list]:
    """`fn(**kwargs)` → `(讀取狀態, 內容)`:分頁不存在 / 表頭不符轉成狀態(可進快取,不每輪重打);
    其餘例外原樣上拋(st.cache_data 不快取例外)。"""
    try:
        return READ_OK, fn(**kwargs)
    except SheetWorksheetMissingError:
        return READ_WORKSHEET_MISSING, []
    except SheetSchemaMismatchError:
        return READ_SCHEMA_MISMATCH, []


def _unwrap_read(result, *, raise_if_missing: bool, worksheet_name: str,
                 headers: list[str]) -> list:
    """`(狀態, 內容)` → public 回傳值。表頭不符一律拋;分頁不存在 → 依 `raise_if_missing`。"""
    _status, _payload = result
    if _status == READ_SCHEMA_MISMATCH:
        raise SheetSchemaMismatchError(worksheet_name, headers)
    if _status == READ_WORKSHEET_MISSING:
        if raise_if_missing:
            raise SheetWorksheetMissingError(worksheet_name)
        return []
    return list(_payload)


#: `classify_read_error` 的分類代碼(§3.3)。
READ_ERROR_LOGIN_REQUIRED = 'login_required'
READ_ERROR_PERMISSION_DENIED = 'permission_denied'
READ_ERROR_SHEET_NOT_FOUND = 'sheet_not_found'
READ_ERROR_QUOTA_EXCEEDED = 'quota_exceeded'
READ_ERROR_NETWORK = 'network'
#: 分不出來 → `error:<例外型別名>`(只交型別名,⛔ 不交訊息 —— 訊息可能含識別碼)。
READ_ERROR_OTHER_PREFIX = 'error:'


def classify_read_error(exc: BaseException) -> str:
    """讀取例外 → 分類代碼(純函式;給 L3 回報「為什麼讀不到」,⛔ 不吞、不改例外本身)。

    只看例外**型別**與 gspread `APIError.code`,⛔ 不比對訊息字串。
    """
    if isinstance(exc, SheetWorksheetMissingError):
        return READ_WORKSHEET_MISSING
    if isinstance(exc, SheetSchemaMismatchError):
        return READ_SCHEMA_MISMATCH
    if isinstance(exc, LoginRequiredError):
        return READ_ERROR_LOGIN_REQUIRED
    _code = None
    try:
        from gspread.exceptions import APIError, SpreadsheetNotFound
    except Exception:  # noqa: BLE001 — 沒有 gspread ⇒ 只能看內建型別
        APIError = SpreadsheetNotFound = ()   # type: ignore[assignment]
    if SpreadsheetNotFound and isinstance(exc, SpreadsheetNotFound):
        return READ_ERROR_SHEET_NOT_FOUND
    if APIError and isinstance(exc, APIError):
        _code = getattr(exc, 'code', None)
    if isinstance(exc, PermissionError) or _code == 403:
        return READ_ERROR_PERMISSION_DENIED
    if _code == 404:
        return READ_ERROR_SHEET_NOT_FOUND
    if _code == 429:
        return READ_ERROR_QUOTA_EXCEEDED
    if isinstance(exc, (ConnectionError, TimeoutError)) or _is_requests_network_error(exc):
        return READ_ERROR_NETWORK
    return f'{READ_ERROR_OTHER_PREFIX}{type(exc).__name__}'


def _is_requests_network_error(exc: BaseException) -> bool:
    try:
        from requests.exceptions import ConnectionError as _RCE, Timeout as _RTO
    except Exception:  # noqa: BLE001
        return False
    return isinstance(exc, (_RCE, _RTO))


# ── 純解析器（§2.1 SSOT + §4 無 I/O 離線可測）───────────────────────────
# `portfolios` / `stock_watchlist` 分頁 records → 乾淨清單。抽出讓 load_portfolio /
# load_stock_watchlist（OAuth/streamlit 路徑）與 headless SA reader（gsheet_sa_reader,
# cron 用）共用**同一套** 欄位鍵 + 完整性規則,避免兩邊 schema/濾值邏輯漂移。
#: `_cell_or_none()` 的「這一列要丟」記號（與 `None`＝缺值 分開;不外流）。
_UNUSABLE = object()


def _is_blank_cell(value: Any) -> bool:
    """Sheet 的**空白格**:`None` 或只含空白的字串（`get_all_records()` 對空白格回 `''`）。"""
    return value is None or (isinstance(value, str) and not value.strip())


def _cell_or_none(value: Any) -> Any:
    """`keep_blank=True` 用:空白 → `None`（缺值）;非空白 → 與預設路徑**同一條**規則。

    非空白時:轉不成 float 或 `<= 0` → `_UNUSABLE`（整列照舊丟）;否則回 float。
    ⚠️ 比較式刻意與預設路徑相同（`<= 0` 才丟）—— 兩種模式對「有填值的格子」
    必須得到同一個結果,只差在空白格。
    """
    if _is_blank_cell(value):
        return None
    try:
        _v = float(value)
    except (TypeError, ValueError):
        return _UNUSABLE
    return _UNUSABLE if _v <= 0 else _v


def parse_portfolio_records(records: list[dict[str, Any]], *,
                            keep_blank: bool = False) -> list[dict[str, Any]]:
    """`portfolios` records → `[{ticker, lots, avg_price}, ...]`（純函式,不分 name）。

    §1 資料完整性:ticker 非空、lots>0、avg_price>0,否則丟棄（不納入零值/髒列,不捏造）。
    ticker 保留原樣（不改大小寫,與 load_portfolio 既有行為一致）。

    keep_blank（加性參數,預設 False ＝ 既有行為一字不變;Q4 2026-09-26）:
        True 時,張數／均價是**空白格**的列**不丟**,該欄回 `None`（缺值,⛔ 不是 0）。
        理由:預設路徑把空白讀成 0 再丟 ⇒ 一本每列都缺張數或均價的組合會**整本消失**,
        下游看到的是「一列持股都沒有」—— 那是把「有內容但缺欄位」講成「空的」(§1)。
        ⚠️ **只放寬「空白」這一種**:有填值但讀不出正數（`0`／負數／非數字）照舊丟 ——
        那是使用者寫了一個值,本層不替它猜意思。
    """
    out: list[dict[str, Any]] = []
    for rec in (records or []):
        tk = str(rec.get('ticker', '')).strip()
        if not tk:
            continue
        if keep_blank:
            _lots = _cell_or_none(rec.get('lots'))
            _avg = _cell_or_none(rec.get('avg_price'))
            if _lots is not _UNUSABLE and _avg is not _UNUSABLE:
                out.append({'ticker': tk, 'lots': _lots, 'avg_price': _avg})
            continue
        try:
            lots = float(rec.get('lots') or 0)
            avg = float(rec.get('avg_price') or 0)
        except (TypeError, ValueError):
            continue
        if lots <= 0 or avg <= 0:
            continue
        out.append({'ticker': tk, 'lots': lots, 'avg_price': avg})
    return out


def parse_watchlist_records(records: list[dict[str, Any]]) -> list[str]:
    """`stock_watchlist` records → 純代碼 `list[str]`（保序、去重;純函式,不分 name）。

    §1 反捏造:只取 ticker 欄,**不**觸碰任何價格。ticker 保留原樣（與
    load_stock_watchlist 既有行為一致;save 端已存大寫）。
    """
    out: list[str] = []
    seen: set[str] = set()
    for rec in (records or []):
        tk = str(rec.get('ticker', '')).strip()
        if tk and tk not in seen:
            seen.add(tk)
            out.append(tk)
    return out


def list_portfolios(*, sheet_id: str | None = None,
                    raise_if_missing: bool = False) -> list[str]:
    """列出所有不重複的組合名稱（按字母排序）。**純讀,零寫入**(B1)。

    sheet_id=None → legacy active sheet(ETF);非空 → 指定 sheet(個股組合)。
    raise_if_missing:加性參數(B1)。False(預設,既有 UI 相容)→ 分頁不存在回 [](⛔ 不再建分頁);
        True → 拋 `SheetWorksheetMissingError`(讓 L3 把「沒有分頁」與「有分頁但沒資料」分開說)。
    第一列欄名不符 → 一律 `SheetSchemaMismatchError`;權限 / 網路錯誤原樣上拋。
    ⚠️ 讀取快取 TTL_15MIN(§3.3 SSOT):寫入後由 clear_read_cache() 失效;快取存 `(狀態, 內容)`。
    SEC-1:快取鍵含 (身分指紋, 實際 sheet_id);無身分不用快取(見 `_identity_scoped_read`)。
    """
    return _unwrap_read(
        _identity_scoped_read(_list_portfolios_cached, _list_portfolios_raw,
                              sheet_id=sheet_id or _get_active_sheet_id()),
        raise_if_missing=raise_if_missing, worksheet_name=_WORKSHEET_NAME, headers=_HEADERS)


@_cache_data(ttl=TTL_15MIN, show_spinner=False)
def _list_portfolios_cached(identity: str, *, sheet_id: str,
                            read_gen: str = '') -> tuple[str, list[str]]:
    # ⚠️ 參數名**不可**加底線前綴:st.cache_data 會把 `_` 開頭的參數排除在快取鍵外。
    # read_gen(B5 失效世代)只為進快取鍵,函式本體不用它。
    return _run_as_identity(identity, _list_portfolios_raw, sheet_id=sheet_id)


def _list_portfolios_raw(*, sheet_id: str) -> tuple[str, list[str]]:
    return _read_status(_list_portfolios_names, sheet_id=sheet_id)


def _list_portfolios_names(*, sheet_id: str) -> list[str]:
    names: set[str] = set()
    for rec in _all_records(sheet_id=sheet_id):
        n = str(rec.get('name', '')).strip()
        if n:
            names.add(n)
    return sorted(names)


def load_portfolio(name: str, *, sheet_id: str | None = None,
                   keep_blank: bool = False,
                   raise_if_missing: bool = False) -> list[dict[str, Any]]:
    """讀取指定名稱的組合，回傳 `[{ticker, lots, avg_price}, ...]`。**純讀,零寫入**(B1)。

    sheet_id=None → legacy active sheet(ETF);非空 → 指定 sheet(個股組合)。
    keep_blank:透傳 `parse_portfolio_records`（預設 False ＝ 既有行為;True → 張數／均價
        空白的列保留、該欄 `None`）。它是參數 ⇒ 屬快取鍵,兩種模式不共用快取項。
    raise_if_missing / 表頭不符 / 例外:同 `list_portfolios`。
    ⚠️ 讀取快取 TTL_15MIN(§3.3 SSOT):寫入後由 clear_read_cache() 失效。
    SEC-1:快取鍵含 (身分指紋, 實際 sheet_id);無身分不用快取(見 `_identity_scoped_read`)。
    """
    name = (name or '').strip()
    if not name:
        return []
    return _unwrap_read(
        _identity_scoped_read(_load_portfolio_cached, _load_portfolio_raw,
                              name=name, sheet_id=sheet_id or _get_active_sheet_id(),
                              keep_blank=keep_blank),
        raise_if_missing=raise_if_missing, worksheet_name=_WORKSHEET_NAME, headers=_HEADERS)


@_cache_data(ttl=TTL_15MIN, show_spinner=False)
def _load_portfolio_cached(identity: str, *, name: str, sheet_id: str,
                           keep_blank: bool, read_gen: str = '') -> tuple[str, list[dict[str, Any]]]:
    # identity / read_gen 不加底線:底線參數不進 st.cache_data 快取鍵(B5 失效世代必須在鍵裡)
    return _run_as_identity(identity, _load_portfolio_raw,
                            name=name, sheet_id=sheet_id, keep_blank=keep_blank)


def _load_portfolio_raw(*, name: str, sheet_id: str,
                        keep_blank: bool) -> tuple[str, list[dict[str, Any]]]:
    return _read_status(_load_portfolio_rows, name=name, sheet_id=sheet_id, keep_blank=keep_blank)


def _load_portfolio_rows(*, name: str, sheet_id: str,
                         keep_blank: bool) -> list[dict[str, Any]]:
    recs = [r for r in _all_records(sheet_id=sheet_id)
            if str(r.get('name', '')).strip() == name]
    if keep_blank:
        return parse_portfolio_records(recs, keep_blank=True)
    return parse_portfolio_records(recs)   # §2.1 共用純解析器（同 headless SA reader）


def _sheet_record(header: list[Any], row: list[Any]) -> dict[str, Any]:
    """一列原字串 → dict:同 gspread `get_all_records()` 的轉換（預設參數 `numericise_all`
    —— `"1,050"`→1050、`"1e3"`→1000.0、`"NaN"`→nan、含底線不轉、空白留 `''` —— 再以
    `to_records` 依表頭組 dict;表頭**不**轉）,但 `_TEXT_COLS` 保留原字串（D1-n1）。
    `_all_records` 與 `_editor_loaded_row` 共用 ⇒ 讀取與存檔判準恆一致。
    """
    from gspread.utils import numericise_all, to_records
    _ignore = [i + 1 for i, h in enumerate(header) if h in _TEXT_COLS]
    return to_records(header, [numericise_all(list(row), ignore=_ignore)])[0]


def _editor_loaded_row(header: list[str], row: list[Any], name: str) -> bool:
    """這一列是不是「📁 組合管理」編輯器按 📂 載入 時**會被讀進表格**的那種列（純函式）。

    判準與 `load_portfolio(name)`（預設模式,即編輯器的讀取路徑）**逐條相同**:
    同一支 `_sheet_record` 轉列（名稱保留原字串,批 Z12 D1-n1）→ name 去空白後相等 →
    交給同一支 `parse_portfolio_records()` 判定。
    ⇒ 回 False 的列 ＝ 編輯器**看不到**的列（別的組合、0／負數／空白／非數字、空白列…）,
    save 時必須原封保留（Q4-r5-f1,客戶 2026-10-02 頁1①）;回 True 的列由編輯器內容取代。
    ⚠️ 兩邊判準若不一致會出事:編輯器載得進來、這裡卻判「沒載入」⇒ 存檔時舊列保留
    **又**接上編輯器那份 ⇒ 每存一次多一份（QA 2026-10-02 抓到的 "1,050" 迴歸）。
    ⚠️ 若日後編輯器改用 `keep_blank=True` 載入,本判準須同步改,否則空白列會被讀進表格、
    卻在存檔時因張數／均價不是正數而不寫回 ⇒ 被刪。
    """
    rec = _sheet_record(header, row)
    if str(rec.get('name', '')).strip() != name:
        return False
    return bool(parse_portfolio_records([rec]))


def _header_has_duplicates(header: list[Any], headers: list[str] = _HEADERS) -> bool:
    """本分頁的欄（`headers`）在表頭出現不只一次 ⇒ 表頭狀態 MISMATCH（讀取 / 寫入都拒絕）。"""
    return any(list(header).count(h) > 1 for h in headers)


def save_portfolio(name: str, rows: list[dict[str, Any]], *,
                   sheet_id: str | None = None) -> int:
    """儲存（覆蓋）指定名稱的組合，回傳寫入的列數。

    rows 預期格式：每筆含 `ticker` / `lots` / `avg_price`。其它欄位忽略。
    sheet_id=None → legacy active sheet(ETF);非空 → 指定 sheet(個股組合)。

    覆蓋範圍（Q4-r5-f1,客戶 2026-10-02 頁1①「存檔時保留沒載入的列」）:
        只取代本組合中**編輯器載得進來**的列（判準見 `_editor_loaded_row`）;
        其餘每一列（別的組合、本組合裡張數／均價為 0／負數／空白／非數字、代號空白、
        整列空白…）**原位、原字串**寫回,⛔ 不丟、⛔ 不正規化。新列照舊接在最後。
    寫入方式:整張表（表頭 + 保留列 + 新列,不足舊高度／寬度處補空字串以清掉殘留）
        以**單一** `ws.update` 一次寫完,取代原本 `clear()` → `append_*` 三步 ——
        原寫法若在 clear 之後斷線,整張 Sheet 會被清空。現寫法失敗時 Sheet 維持原狀,
        例外照常往上拋（§1）。值以 RAW 寫入（與原 `append_rows` 預設相同）。
    分頁 / 表頭(Sheet Safety 批 B1):分頁不存在 → 本次**明確寫入**才建立(`_ws_for_write`);
        第一列欄名不符 → 在任何寫入之前 `SheetSchemaMismatchError`,⛔ 不覆寫第一列。
        ~~本分頁的欄重複 → 每列都當「沒載入」全保留、照寫~~(有意識的修改:那是在表頭不明時
        仍改寫第一列;現與讀取同判 MISMATCH → 拒寫,Sheet 一格不動)。
    """
    name = (name or '').strip()
    if not name:
        raise ValueError('組合名稱不可為空')
    if not rows:
        raise ValueError('組合內容不可為空')

    ts = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_rows = []
    for r in rows:
        tk = str(r.get('ticker', '')).strip().upper()
        if not tk:
            continue
        try:
            lots = float(r.get('lots') or 0)
            avg = float(r.get('avg_price') or 0)
        except (TypeError, ValueError):
            continue
        except OverflowError:
            # 批 Y2(V2-n8):超大整數 float() 溢位 ＝ 非有限值 → 與下方同一句既有 ValueError、
            #   任何寫入之前 fail loud(修前 OverflowError 直接外洩)。
            raise ValueError('有張數或均價空白／無效的列，Sheet 維持原狀（檢查張數、均價）') from None
        # 批 V2(D1-n2,§1 擋非有限值):NaN 會通過下一行 `<= 0` 篩選、一路帶到
        #   `ws.update` 才炸。改在**任何寫入之前**(含下方 add_rows／add_cols)
        #   fail loud,沿用同函式既有的 ValueError 字句;Sheet 一格不動。
        if not (math.isfinite(lots) and math.isfinite(avg)):
            raise ValueError('有張數或均價空白／無效的列，Sheet 維持原狀（檢查張數、均價）')
        if lots <= 0 or avg <= 0:
            continue
        new_rows.append([name, tk, lots, avg, ts])

    if not new_rows:
        raise ValueError('無有效持股可儲存（檢查代號、張數、均價）')

    # 輸入驗證全過才開分頁(B1:無效輸入⛔ 不因此建出空分頁)。
    ws = _ws_for_write(sheet_id=sheet_id, create_if_missing=True)
    existing = ws.get_all_values()
    _require_writable_header(existing, _HEADERS, _WORKSHEET_NAME)
    _old_header = list(existing[0]) if existing else []
    # 表頭:前 5 欄釘 _HEADERS（表頭已過關 ⇒ 與原表頭相同或是其前段）;右邊自加的表頭格原樣保留。
    header = _write_header(_old_header, _HEADERS)
    keep_rows = [list(r) for r in existing[1:]
                 if not _editor_loaded_row(_old_header, r, name)]

    _write_whole_sheet(ws, existing, [header] + keep_rows + new_rows)
    clear_read_cache()          # 寫入即清:使用者自己的編輯即時可見(§1)
    return len(new_rows)


def _write_whole_sheet(ws, existing: list[list[Any]], grid: list[list[Any]]) -> None:
    """把 `grid`（含表頭）以**單一** `ws.update` 寫成整張表 —— 取代 `clear()` → `append_*`。

    原寫法若在 clear 之後斷線,整張 Sheet 會被清空;本寫法失敗時 Sheet 維持原狀,
    例外照常往上拋（§1）。值以 RAW 寫入（與原 `append_rows` 預設相同）。
    批 Z12（D1-n5）:自 `save_portfolio` 抽出,`save_stock_watchlist`／`delete_portfolio`／
    `delete_stock_watchlist` 共用同一寫法。
    """
    n_cols = max(len(r) for r in (grid + existing))
    n_rows = max(len(grid), len(existing))
    # 補空字串到舊表的高／寬:舊資料比新內容長的部分一併在同一次寫入中清掉,不留殘列。
    grid = [r + [''] * (n_cols - len(r)) for r in grid]
    grid += [[''] * n_cols for _ in range(n_rows - len(grid))]

    # 表格格數不夠時先擴（只加空列／空欄,不動既有內容;失敗則 Sheet 原狀、例外上拋）。
    if n_rows > ws.row_count:
        ws.add_rows(n_rows - ws.row_count)
    if n_cols > ws.col_count:
        ws.add_cols(n_cols - ws.col_count)

    from gspread.utils import rowcol_to_a1
    ws.update(values=grid, range_name=f'A1:{rowcol_to_a1(n_rows, n_cols)}')


# ── Option B:個股**純代碼**觀察清單 API(獨立 `stock_watchlist` 分頁,無價格)──────
# §1 反捏造:save 只寫 [name, ticker.upper(), updated_at],**絕無**張數/均價/哨兵。
# 與 portfolios(5 欄含價格)物理隔離,pure watchlist 讀寫時不接觸任何價格欄位。
def save_stock_watchlist(name: str, tickers: list[str], *,
                         sheet_id: str | None = None) -> int:
    """儲存(覆蓋)指定名稱的**純代碼**觀察清單到 `stock_watchlist` 分頁,回寫入列數。

    §1:每列僅 `[name, ticker.upper(), updated_at]` 三欄 —— **無**張數/均價/哨兵/任何
    捏造價格。tickers 去空 + 去重(保序,大寫正規化)。同名覆蓋(保留其它 name,
    與 `save_portfolio` 的 keep_rows 同 pattern)。name/代碼皆空 → raise ValueError。
    sheet_id=None → legacy active sheet;非空 → 指定 sheet(個股組合分家用)。
    分頁 / 表頭(B1):同 `save_portfolio` —— 分頁不存在 → 本次寫入才建;第一列欄名不符 →
    任何寫入之前 `SheetSchemaMismatchError`。表頭右邊使用者自加的表頭格原樣保留
    (~~修前整列寫成 3 欄表頭、右邊自加的表頭格被補空字串清掉~~,有意識的修改:寫入不改使用者自加欄)。
    """
    name = (name or '').strip()
    if not name:
        raise ValueError('組合名稱不可為空')
    if not tickers:
        raise ValueError('代碼清單不可為空')

    clean: list[str] = []
    seen: set[str] = set()
    for _t in tickers:
        tk = str(_t or '').strip().upper()
        if tk and tk not in seen:
            seen.add(tk)
            clean.append(tk)
    if not clean:
        raise ValueError('無有效代碼可儲存')

    ws = _ws_for_write(sheet_id=sheet_id, worksheet_name=_STOCK_WATCHLIST_WORKSHEET,
                       create_if_missing=True)
    existing = ws.get_all_values()
    _require_writable_header(existing, _STOCK_WATCHLIST_HEADERS, _STOCK_WATCHLIST_WORKSHEET)
    _old_header = list(existing[0]) if existing else []
    keep_rows = [r for r in existing[1:] if (r and r[0].strip() != name)]

    ts = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_rows = [[name, tk, ts] for tk in clean]  # ← 無價格欄,§1 反捏造

    _write_whole_sheet(ws, existing, [_write_header(_old_header, _STOCK_WATCHLIST_HEADERS)]
                       + keep_rows + new_rows)
    clear_read_cache()          # 寫入即清:使用者自己的編輯即時可見(§1)
    return len(new_rows)


def add_to_stock_watchlist(name: str, tickers: list[str], *,
                           sheet_id: str | None = None) -> int:
    """把 tickers **併入**既有觀察清單（讀現有 → 聯集去重保序 → 存),回合併後總檔數。

    與 `save_stock_watchlist`(覆蓋)不同:此為「加入」語意 —— 選股網勾選後不覆蓋你既有的
    清單。§1:name/代碼皆空 → raise;既有清單不存在 → 視同從空開始(等同新建)。
    大寫正規化 + 去重(同 save_stock_watchlist)。內部呼 save → clear_read_cache 已含。
    合併前的讀取(B1 / B5):直接讀 Sheet 最新內容、**不經**讀取快取 ——
    ~~先呼 `clear_read_cache()` 再讀~~(有意識的修改:那會清掉**所有使用者**的讀取快取,
    只為了自己讀一次最新值;B5「不得默認清除所有使用者的全域 cache」)。
    分頁不存在 → 從空開始(save 時才建);第一列欄名不符 → `SheetSchemaMismatchError`、不寫。
    """
    name = (name or '').strip()
    if not name:
        raise ValueError('清單名稱不可為空')
    _add = [str(_t or '').strip().upper() for _t in (tickers or []) if str(_t or '').strip()]
    if not _add:
        raise ValueError('沒有可加入的代碼')
    # 合併前讀「最新」既有清單(不經 15 分快取,避免漏併他處剛加的;稽核 low-sev)。
    _status, _existing = _load_stock_watchlist_raw(name=name,
                                                   sheet_id=sheet_id or _get_active_sheet_id())
    if _status == READ_SCHEMA_MISMATCH:
        raise SheetSchemaMismatchError(_STOCK_WATCHLIST_WORKSHEET, _STOCK_WATCHLIST_HEADERS,
                                       writing=True)
    _merged = list(_existing)
    _seen = set(_existing)
    for _t in _add:
        if _t not in _seen:
            _seen.add(_t)
            _merged.append(_t)
    return save_stock_watchlist(name, _merged, sheet_id=sheet_id)


def list_stock_watchlists(*, sheet_id: str | None = None,
                          raise_if_missing: bool = False) -> list[str]:
    """列出 `stock_watchlist` 分頁內所有不重複的清單名稱(字母排序)。**純讀,零寫入**(B1)。

    sheet_id=None → legacy active sheet;非空 → 指定 sheet(個股組合)。
    raise_if_missing / 表頭不符 / 例外:同 `list_portfolios`。
    ⚠️ 讀取快取 TTL_15MIN(§3.3 SSOT):寫入後由 clear_read_cache() 失效。
    SEC-1:快取鍵含 (身分指紋, 實際 sheet_id);無身分不用快取(見 `_identity_scoped_read`)。
    """
    return _unwrap_read(
        _identity_scoped_read(_list_stock_watchlists_cached, _list_stock_watchlists_raw,
                              sheet_id=sheet_id or _get_active_sheet_id()),
        raise_if_missing=raise_if_missing, worksheet_name=_STOCK_WATCHLIST_WORKSHEET,
        headers=_STOCK_WATCHLIST_HEADERS)


@_cache_data(ttl=TTL_15MIN, show_spinner=False)
def _list_stock_watchlists_cached(identity: str, *, sheet_id: str,
                                  read_gen: str = '') -> tuple[str, list[str]]:
    # identity / read_gen 不加底線:底線參數不進 st.cache_data 快取鍵(B5 失效世代必須在鍵裡)
    return _run_as_identity(identity, _list_stock_watchlists_raw, sheet_id=sheet_id)


def _list_stock_watchlists_raw(*, sheet_id: str) -> tuple[str, list[str]]:
    return _read_status(_list_stock_watchlist_names, sheet_id=sheet_id)


def _list_stock_watchlist_names(*, sheet_id: str) -> list[str]:
    names: set[str] = set()
    for rec in _all_records(sheet_id=sheet_id,
                            worksheet_name=_STOCK_WATCHLIST_WORKSHEET,
                            headers=_STOCK_WATCHLIST_HEADERS):
        n = str(rec.get('name', '')).strip()
        if n:
            names.add(n)
    return sorted(names)


def load_stock_watchlist(name: str, *, sheet_id: str | None = None,
                         raise_if_missing: bool = False) -> list[str]:
    """讀取指定名稱的**純代碼**清單(保序、去重),回傳 `list[str]`,**無**價格欄位。**純讀**(B1)。

    sheet_id=None → legacy active sheet;非空 → 指定 sheet(個股組合)。
    raise_if_missing / 表頭不符 / 例外:同 `list_portfolios`。
    ⚠️ 讀取快取 TTL_15MIN(§3.3 SSOT):寫入後由 clear_read_cache() 失效。
    SEC-1:快取鍵含 (身分指紋, 實際 sheet_id);無身分不用快取(見 `_identity_scoped_read`)。
    """
    name = (name or '').strip()
    if not name:
        return []
    return _unwrap_read(
        _identity_scoped_read(_load_stock_watchlist_cached, _load_stock_watchlist_raw,
                              name=name, sheet_id=sheet_id or _get_active_sheet_id()),
        raise_if_missing=raise_if_missing, worksheet_name=_STOCK_WATCHLIST_WORKSHEET,
        headers=_STOCK_WATCHLIST_HEADERS)


@_cache_data(ttl=TTL_15MIN, show_spinner=False)
def _load_stock_watchlist_cached(identity: str, *, name: str, sheet_id: str,
                                 read_gen: str = '') -> tuple[str, list[str]]:
    # identity / read_gen 不加底線:底線參數不進 st.cache_data 快取鍵(B5 失效世代必須在鍵裡)
    return _run_as_identity(identity, _load_stock_watchlist_raw, name=name, sheet_id=sheet_id)


def _load_stock_watchlist_raw(*, name: str, sheet_id: str) -> tuple[str, list[str]]:
    return _read_status(_load_stock_watchlist_codes, name=name, sheet_id=sheet_id)


def _load_stock_watchlist_codes(*, name: str, sheet_id: str) -> list[str]:
    recs = [r for r in _all_records(sheet_id=sheet_id,
                                    worksheet_name=_STOCK_WATCHLIST_WORKSHEET,
                                    headers=_STOCK_WATCHLIST_HEADERS)
            if str(r.get('name', '')).strip() == name]
    return parse_watchlist_records(recs)   # §2.1 共用純解析器（同 headless SA reader）


# ── 前進式驗證:選股凍結紀錄(獨立 worksheet,不污染 portfolios)── FT-2 v19.142
_FT_WORKSHEET_NAME = 'forward_test_picks'
_FT_HEADERS = ['cohort', 'stock_id', 'name', 'entry_price', 'factors', 'frozen_at']


#: B2:讀取狀態另一種 ——「還沒選 Sheet / 還沒登入」(前進式驗證只用本地紀錄,不是故障)。
READ_NOT_CONFIGURED = 'not_configured'


def _ft_header_state(values: list[list[Any]]) -> str:
    """forward_test_picks 表頭(比 `_header_state` **更嚴**):必須從 A 欄起完整等於 `_FT_HEADERS`
    (右邊自加欄可以);只有前段(窄表)也算 MISMATCH —— 不可重建歷史,⛔ 不替它補表頭。"""
    _state = _header_state(values, _FT_HEADERS)
    if _state == _HEADER_OK and list(values[0][:len(_FT_HEADERS)]) != _FT_HEADERS:
        return _HEADER_MISMATCH
    return _state


def _ft_worksheet():
    """**只開不建**:`forward_test_picks` worksheet(legacy active sheet)。⛔ 零寫入(B2)。

    ~~取得 (或建立) worksheet,並確保 header 列存在~~(Sheet Safety 批 B2,DEC-083,有意識的修改:
    修前讀取 / 對帳也走這裡 ⇒ 分頁不存在就建、表頭不符就覆寫 A1:F1 —— 對**不可重建的歷史**
    改表頭會讓既有每一列的欄意義錯位)。分頁不存在 → `SheetWorksheetMissingError`。
    """
    return _ws(worksheet_name=_FT_WORKSHEET_NAME)


def _ft_worksheet_for_write():
    """寫入用(只給 `append_forward_test_picks`,即使用者按 🧊 凍結的**明確寫入動作**):
      · 分頁不存在 → 建立 + 寫表頭;
      · 分頁在但整張表空白 → 寫表頭(沒有任何歷史可被影響);
      · 表頭不符(含只有前段)→ 在任何寫入之前 `SheetSchemaMismatchError`,⛔ 不重建表頭、⛔ 不 append。
    """
    try:
        ws = _ft_worksheet()
    except SheetWorksheetMissingError:
        print(f'[gsheet_portfolio] B2 凍結寫入建立分頁 worksheet={_FT_WORKSHEET_NAME}')
        ws = _open_spreadsheet(None).add_worksheet(title=_FT_WORKSHEET_NAME, rows=1000, cols=8)
        ws.append_row(_FT_HEADERS)
        return ws
    _state = _ft_header_state(ws.get_all_values())
    if _state == _HEADER_MISMATCH:
        raise SheetSchemaMismatchError(_FT_WORKSHEET_NAME, _FT_HEADERS, writing=True)
    if _state == _HEADER_EMPTY:
        ws.append_row(_FT_HEADERS)
    return ws


def append_forward_test_picks(rows: list[dict[str, Any]]) -> int:
    """把選股凍結列 append 到 forward_test_picks worksheet;回寫入列數。

    rows 每筆須含 _FT_HEADERS 各欄(由 L2 build_pick_snapshot_rows 產出)。空 → 0(不開 Sheet)。
    分頁 / 表頭規則見 `_ft_worksheet_for_write`(B2:表頭不符 → 拋錯、一列都不寫)。
    """
    if not rows:
        return 0
    ws = _ft_worksheet_for_write()
    ws.append_rows([[r.get(h, '') for h in _FT_HEADERS] for r in rows])
    return len(rows)


def read_forward_test_picks() -> tuple[str, list[dict[str, Any]]]:
    """讀回全部凍結紀錄 → `(讀取狀態, records)`。**零寫入**(B2:不建分頁、不重建表頭、不修)。

    狀態:`READ_OK`(含只有表頭 → [])/ `READ_EMPTY` / `READ_WORKSHEET_MISSING` /
    `READ_SCHEMA_MISMATCH` / `READ_NOT_CONFIGURED`(還沒選 Sheet 或還沒登入)/
    `error:<例外型別名>`(其他讀取失敗;⛔ 不交訊息)。狀態非 OK 時 records 一律 []。
    批 Z33（Z12-n2）:`stock_id`／`name` 保留 Sheet 原字串（`0050` 不可讀成 50,否則與本地
    '0050' 去重失效、對帳抓不到現價）;其餘欄轉換同 `get_all_records()` 預設。
    gspread `numericise_ignore` 只認 **1-based 欄序**（欄名不生效）⇒ 依實際表頭找欄位。
    """
    try:
        ws = _ft_worksheet()
        values = ws.get_all_values()
        _state = _ft_header_state(values)
        if _state == _HEADER_EMPTY:
            return READ_EMPTY, []
        if _state == _HEADER_MISMATCH:
            return READ_SCHEMA_MISMATCH, []
        header = list(values[0])
        return READ_OK, ws.get_all_records(numericise_ignore=[
            i + 1 for i, h in enumerate(header) if h in ('stock_id', 'name')])
    except SheetWorksheetMissingError:
        return READ_WORKSHEET_MISSING, []
    except (SheetNotConfiguredError, LoginRequiredError):
        return READ_NOT_CONFIGURED, []
    except Exception as _e:  # noqa: BLE001 — 交回狀態給 L3 揭露,不炸前進式驗證面板
        print(f'[gsheet] forward_test_picks 讀取失敗: {type(_e).__name__}')
        return f'{READ_ERROR_OTHER_PREFIX}{type(_e).__name__}', []


def load_forward_test_picks() -> list[dict[str, Any]]:
    """`read_forward_test_picks()` 的 list 相容包裝(既有 caller / 測試);非 OK 狀態記 log、回 []。

    worksheet 不存在 / 未設定 Sheet / 表頭不符 / 讀取失敗 → 回 [](不炸對帳面板;§1 由 caller 判空)。
    要分辨「為什麼是空的」請改用 `read_forward_test_picks()`(L3 `load_frozen_picks_df` 已改用)。
    """
    _status, _recs = read_forward_test_picks()
    if _status != READ_OK:
        print(f'[gsheet] forward_test_picks status={_status}')
    return _recs


def list_user_sheets(folder_id: str = '') -> list[dict]:
    """OAuth 模式列出使用者 Google Drive 內 Spreadsheets。

    Args:
        folder_id: 若提供，僅列出此資料夾內的 Sheets；留空則列全部。

    需要 OAuth scope `drive.metadata.readonly`（infra/oauth.py 已內建）。
    回傳 [{'id': ..., 'name': ...}, ...] 依名稱排序；非 OAuth 模式回空 list。

    v19.x：直接走 Drive v3 API（同 list_user_folders）加 `trashed=false` 過濾，
    取代原本 gspread `list_spreadsheet_files()`（會抓出已刪除 Sheets，造成
    UI 下拉出現殭屍項目）。
    """
    if not _has_oauth_tokens():
        # 未登入 OAuth → 無法列檔（SEC-3:網頁端只用本人 OAuth）
        return []
    client = _build_client()
    url = 'https://www.googleapis.com/drive/v3/files'
    q_parts = [
        'mimeType="application/vnd.google-apps.spreadsheet"',
        'trashed=false',
    ]
    if folder_id and folder_id.strip():
        q_parts.append(f'"{folder_id.strip()}" in parents')
    params = {
        'q': ' and '.join(q_parts),
        'pageSize': 1000,
        'supportsAllDrives': True,
        'includeItemsFromAllDrives': True,
        'fields': 'nextPageToken,files(id,name)',
    }
    files: list[dict] = []
    page_token: str | None = None
    try:
        while True:
            if page_token:
                params['pageToken'] = page_token
            resp = client.http_client.request('get', url, params=params)
            data = resp.json() if hasattr(resp, 'json') else resp
            for f in (data.get('files') or []):
                _id, _nm = f.get('id'), f.get('name')
                if _id and _nm:
                    files.append({'id': _id, 'name': _nm})
            page_token = data.get('nextPageToken')
            if not page_token:
                break
    except Exception as e:
        raise RuntimeError(f'列出 Drive Sheets 失敗：[{type(e).__name__}] {e}') from e
    files.sort(key=lambda x: x['name'].lower())
    return files


def list_user_folders() -> list[dict]:
    """OAuth 模式列出使用者 Google Drive 內所有資料夾（含共享）。

    透過 gspread client 的 http_client 直接打 Drive v3 API；
    需要 OAuth scope `drive.metadata.readonly`。
    回傳 [{'id': ..., 'name': ...}, ...] 依名稱排序；非 OAuth 模式回空 list。
    """
    if not _has_oauth_tokens():
        return []
    client = _build_client()
    url = 'https://www.googleapis.com/drive/v3/files'
    params = {
        'q': 'mimeType="application/vnd.google-apps.folder" and trashed=false',
        'pageSize': 1000,
        'supportsAllDrives': True,
        'includeItemsFromAllDrives': True,
        'fields': 'nextPageToken,files(id,name)',
    }
    folders: list[dict] = []
    page_token: str | None = None
    try:
        while True:
            if page_token:
                params['pageToken'] = page_token
            resp = client.http_client.request('get', url, params=params)
            data = resp.json()
            for f in (data.get('files') or []):
                _id, _nm = f.get('id'), f.get('name')
                if _id and _nm:
                    folders.append({'id': _id, 'name': _nm})
            page_token = data.get('nextPageToken')
            if not page_token:
                break
    except Exception as e:
        raise RuntimeError(f'列出 Drive 資料夾失敗：[{type(e).__name__}] {e}') from e
    folders.sort(key=lambda x: x['name'].lower())
    return folders


def _get_or_create_app_folder(folder_name: str) -> str:
    """回傳(或建立)名為 `folder_name` 的 app 專屬 Drive 資料夾 id。

    在 `drive.file` scope 下,Drive v3 `files.list` **只**會列出本 app 建立的檔案 /
    資料夾 —— 故先 SEARCH 同名資料夾:命中即 reuse(避免每次新建重複資料夾),
    未命中才 CREATE 一個。整個流程只需 `drive.file`,不需 `drive.metadata.readonly`。

    §1 fail-loud:任一 Drive API 呼叫失敗 → raise RuntimeError(不回假 id、不靜默)。
    """
    if not _has_oauth_tokens():
        raise RuntimeError('建立/查詢資料夾需先「🔐 用 Google 登入」')
    client = _build_client()
    url = 'https://www.googleapis.com/drive/v3/files'
    # q 字串內單引號需以 \' 轉義,避免注入 / 破壞查詢語法
    _escaped = folder_name.replace("'", "\\'")
    # ── SEARCH:同名 app-created 資料夾(mirror list_user_folders 的 params)──
    search_params = {
        'q': ("mimeType='application/vnd.google-apps.folder' and "
              f"name='{_escaped}' and trashed=false"),
        'pageSize': 10,
        'supportsAllDrives': True,
        'includeItemsFromAllDrives': True,
        'fields': 'files(id,name)',
    }
    try:
        resp = client.http_client.request('get', url, params=search_params)
        data = resp.json() if hasattr(resp, 'json') else resp
        for f in (data.get('files') or []):
            _fid = f.get('id')
            if _fid:
                return _fid            # ← reuse 既有資料夾
        # ── CREATE:未命中才建立 ──
        resp2 = client.http_client.request(
            'post', url,
            json={'name': folder_name,
                  'mimeType': 'application/vnd.google-apps.folder'},
            params={'fields': 'id', 'supportsAllDrives': True})
        data2 = resp2.json() if hasattr(resp2, 'json') else resp2
        new_id = (data2 or {}).get('id')
        if not new_id:
            raise RuntimeError('建立資料夾後未取得 id（Drive 回傳異常）')
        return new_id
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            f'資料夾建立/查詢失敗：[{type(e).__name__}] {e}') from e


def create_new_sheet(title: str = '台股 Dashboard - 投資組合', *,
                     folder_name: str | None = None) -> tuple[str, str]:
    """建立新 Google Sheet 並回傳 (sheet_id, sheet_url)。

    OAuth 模式下 `drive.file` scope 已允許 app 建立並擁有此檔，
    不需要 `drive.metadata.readonly` — 可避開「token 缺中繼權限」的卡關。

    folder_name
    -----------
    - None(預設)→ 行為與舊版 byte-for-byte 相同:Sheet 建於 Drive 根目錄
      (ETF caller 走此路,不受影響)。
    - 非空字串 → 建立後把 Sheet **搬入** 該名稱的 app 專屬資料夾
      (`_get_or_create_app_folder`),使個股 Sheet 與 ETF Sheet 在 Drive 物理分隔。
      §1 best-effort:搬移屬「錦上添花」,失敗**只記 log 不炸**,仍回傳已建立的
      (sheet_id, sheet_url) —— **Sheet 永不遺失 / 永不 orphan**。
    """
    if not _has_oauth_tokens():
        raise RuntimeError('建立新 Sheet 需先「🔐 用 Google 登入」')
    title = (title or '').strip() or '台股 Dashboard - 投資組合'
    client = _build_client()
    try:
        sh = client.create(title)
    except Exception as e:
        raise RuntimeError(f'建立 Sheet 失敗：[{type(e).__name__}] {e}') from e
    sheet_id = getattr(sh, 'id', '') or ''
    sheet_url = getattr(sh, 'url', '') or (
        f'https://docs.google.com/spreadsheets/d/{sheet_id}/edit' if sheet_id else '')
    if not sheet_id:
        raise RuntimeError('建立 Sheet 後未取得 ID（gspread 回傳異常）')

    # ── best-effort:放入專屬資料夾(失敗不影響已建立的 Sheet)──
    if isinstance(folder_name, str) and folder_name.strip():
        try:
            fid = _get_or_create_app_folder(folder_name)
            files_url = 'https://www.googleapis.com/drive/v3/files'
            # 先取現有 parents,搬移時一併 remove,避免雙 parent(dual-parented)
            resp = client.http_client.request(
                'get', f'{files_url}/{sheet_id}',
                params={'fields': 'parents', 'supportsAllDrives': True})
            gdata = resp.json() if hasattr(resp, 'json') else resp
            cur_parents = (gdata or {}).get('parents') or []
            update_params = {
                'addParents': fid,
                'fields': 'id,parents',
                'supportsAllDrives': True,
            }
            if cur_parents:
                update_params['removeParents'] = ','.join(cur_parents)
            client.http_client.request(
                'patch', f'{files_url}/{sheet_id}', params=update_params)
        except Exception as e:  # noqa: BLE001 — §1 disclosed best-effort log
            print(f'[create_new_sheet] 資料夾放置失敗，Sheet 仍建於根目錄：{e}')

    return sheet_id, sheet_url


def rename_sheet(new_title: str) -> bool:
    """重新命名目前作用中的 Sheet。需要編輯權限。"""
    new_title = (new_title or '').strip()
    if not new_title:
        raise ValueError('rename_sheet: 新名稱不可為空')
    sheet_id = _get_active_sheet_id()
    if not sheet_id:
        raise RuntimeError('rename_sheet: 尚未選定 Sheet ID')
    client = _build_client()
    try:
        sh = client.open_by_key(sheet_id)
        sh.update_title(new_title)
        return True
    except Exception as e:
        raise RuntimeError(f'重新命名失敗：[{type(e).__name__}] {e}') from e


def get_sheet_title(sheet_id: str = '') -> str:
    """取得指定 Sheet 的標題；sheet_id 為空時用目前作用中的。失敗回空字串。"""
    sheet_id = sheet_id or _get_active_sheet_id()
    if not sheet_id:
        return ''
    try:
        sh = _build_client().open_by_key(sheet_id)
        return getattr(sh, 'title', '') or ''
    except Exception:
        return ''


def read_sheet_title(sheet_id: str) -> tuple[str, str]:
    """指定 Sheet 的標題(👤 我的 P1)。**純讀,零寫入**;與 `get_sheet_title` 不同:**⛔ 不吞例外**(§1)。

    回 `(狀態, 標題)`:
      · `READ_OK` ＋ 標題(標題本身可以是空字串 —— 那是 Google 回的,照實);
      · `READ_ERROR_SHEET_NOT_FOUND`(404)/ `READ_ERROR_PERMISSION_DENIED`(403)＋ ''(**可進快取**:
        同一人、同一本,15 分鐘內不會自己變好;要立刻重試請用 `invalidate_my_read_cache`)。
    其他(未登入 `LoginRequiredError`、429、網路、不明)→ **原樣上拋**、⛔ 不進快取。
    sheet_id 消毒不過 / 空 → `SheetNotConfiguredError`(⛔ 不退回 session 綁定那本 —— 讀哪本由呼叫端說清楚)。
    快取同四支讀取:鍵含 (身分指紋, sheet_id, B5 失效世代);無身分不用快取(`_identity_scoped_read`)。
    ⚠️ `get_sheet_title`(失敗回空字串)本批**不動**(`tests/test_sec3_no_anonymous_sa.py` 釘住其既有行為)。
    """
    from shared.sheet_id import sanitize_sheet_id
    _sid = sanitize_sheet_id(sheet_id)
    if not _sid:
        raise SheetNotConfiguredError('read_sheet_title: 沒有可讀的 Sheet ID')
    _status, _title = _identity_scoped_read(_read_sheet_title_cached, _read_sheet_title_raw,
                                            sheet_id=_sid)
    return str(_status), str(_title or '')


@_cache_data(ttl=TTL_15MIN, show_spinner=False)
def _read_sheet_title_cached(identity: str, *, sheet_id: str,
                             read_gen: str = '') -> tuple[str, str]:
    # identity / read_gen 不加底線:底線參數不進 st.cache_data 快取鍵(B5 失效世代必須在鍵裡)
    return _run_as_identity(identity, _read_sheet_title_raw, sheet_id=sheet_id)


#: 標題讀取時「可以進快取」的失敗(同一人同一本短時間內不會自己變好)。其餘例外上拋、不快取。
_TITLE_CACHEABLE_ERRORS = frozenset({READ_ERROR_SHEET_NOT_FOUND, READ_ERROR_PERMISSION_DENIED})


def _read_sheet_title_raw(*, sheet_id: str) -> tuple[str, str]:
    try:
        sh = _build_client().open_by_key(sheet_id)
    except Exception as _e:  # noqa: BLE001 — 只把 403 / 404 轉成可快取的狀態,其餘原樣上拋(§1)
        _code = classify_read_error(_e)
        if _code in _TITLE_CACHEABLE_ERRORS:
            return _code, ''
        raise
    return READ_OK, str(getattr(sh, 'title', '') or '')


# ── AB-4r（D2.5 §5 序 5，2026-10-27）:指定分頁的原字串讀取(加法式,唯讀) ─────────────────
# 給 L1 `strategy_class_reader` 讀 `strategy_class` 分頁。表頭 / 內容判讀**不在這裡**(L0
# `shared/strategy_class_schema.parse_strategy_records`);本函式只負責「打開、讀原字串、零寫入」。
# ⚠️ 既有函式一個都沒改。⚠️ 已知限制(據實):全域 `clear_read_cache()` **沒有**列入本快取
# (改它＝改既有函式行為);本快取靠 B5 失效世代(`invalidate_my_read_cache` / `invalidate_sheet_read_cache`)
# 或 TTL_15MIN 失效。AB-4r 沒有寫入面,寫入後失效由 AB-4w 處理。
def read_worksheet_values(worksheet_name: str, *, sheet_id: str) -> list[list[Any]]:
    """指定 Sheet 的指定分頁 → `get_all_values()` 原字串(list of list)。**純讀,零寫入。**

    - sheet_id 必填、經 `sanitize_sheet_id`;消毒不過 / 空 → `SheetNotConfiguredError`
      (⛔ 不退回 session 綁定那本 —— 讀哪本由呼叫端說清楚,同 `read_sheet_title`)。
    - worksheet_name 非 str / 空白 → `ValueError`。
    - 分頁不存在 → `SheetWorksheetMissingError`(⛔ 不建;「不存在」狀態可進快取,不每輪 rerun 重打)。
    - 表頭**不**在這裡檢查(呼叫端依各自 schema 判);權限 / 網路 / 未登入例外原樣上拋(不進快取)。
    快取同四支讀取:鍵含 (身分指紋, sheet_id, worksheet_name, B5 失效世代);無身分不用快取。
    """
    from shared.sheet_id import sanitize_sheet_id
    _sid = sanitize_sheet_id(sheet_id)
    if not _sid:
        raise SheetNotConfiguredError('read_worksheet_values: 沒有可讀的 Sheet ID')
    if type(worksheet_name) is not str or not worksheet_name.strip():
        raise ValueError('read_worksheet_values: worksheet_name 必須是非空 str')
    _status, _values = _identity_scoped_read(_read_worksheet_values_cached, _read_worksheet_values_raw,
                                             worksheet_name=worksheet_name, sheet_id=_sid)
    if _status == READ_WORKSHEET_MISSING:
        raise SheetWorksheetMissingError(worksheet_name)
    return [list(_r) for _r in _values]


@_cache_data(ttl=TTL_15MIN, show_spinner=False)
def _read_worksheet_values_cached(identity: str, *, worksheet_name: str, sheet_id: str,
                                  read_gen: str = '') -> tuple[str, list]:
    # identity / read_gen 不加底線:底線參數不進 st.cache_data 快取鍵(B5 失效世代必須在鍵裡)
    return _run_as_identity(identity, _read_worksheet_values_raw,
                            worksheet_name=worksheet_name, sheet_id=sheet_id)


def _read_worksheet_values_raw(*, worksheet_name: str, sheet_id: str) -> tuple[str, list]:
    return _read_status(_worksheet_values, worksheet_name=worksheet_name, sheet_id=sheet_id)


def _worksheet_values(*, worksheet_name: str, sheet_id: str) -> list[list[Any]]:
    """只開不建(`_ws`)→ `get_all_values()`。⛔ 零寫入。"""
    return _ws(sheet_id=sheet_id, worksheet_name=worksheet_name).get_all_values()


def delete_portfolio(name: str, *, sheet_id: str | None = None) -> int:
    """刪除指定名稱的組合（所有持股列），回傳刪除的列數。

    sheet_id=None → legacy active sheet(ETF);非空 → 指定 sheet(個股組合)。
    分頁 / 表頭(B1):分頁不存在 → 回 0(⛔ 不為了刪除而建分頁);第一列欄名不符 →
    任何寫入之前 `SheetSchemaMismatchError`(第 1 欄不一定是 name ⇒ 不能據以刪列)。
    """
    name = (name or '').strip()
    if not name:
        return 0
    ws = _ws_for_write(sheet_id=sheet_id, create_if_missing=False)
    if ws is None:
        return 0
    existing = ws.get_all_values()
    _require_writable_header(existing, _HEADERS, _WORKSHEET_NAME)
    if len(existing) <= 1:
        return 0
    keep_rows = [r for r in existing[1:] if (r and r[0].strip() != name)]
    deleted = (len(existing) - 1) - len(keep_rows)
    if deleted == 0:
        return 0
    _write_whole_sheet(ws, existing, [_write_header(existing[0], _HEADERS)] + keep_rows)
    clear_read_cache()          # 刪除即清(§1)
    return deleted


def delete_stock_watchlist(name: str, *, sheet_id: str | None = None) -> int:
    """刪除指定名稱的**個股觀察清單**(所有代碼列),回傳刪除的列數。

    語意鏡像 delete_portfolio,但操作 `stock_watchlist` 分頁(純代碼、無價格)。
    補齊個股端原缺的刪除能力(ETF 早有 delete_portfolio,個股一直只能同名覆蓋)。
    sheet_id=None → legacy active sheet;非空 → 指定 sheet(個股組合分家用)。
    分頁 / 表頭(B1):同 `delete_portfolio`。
    """
    name = (name or '').strip()
    if not name:
        return 0
    ws = _ws_for_write(sheet_id=sheet_id, worksheet_name=_STOCK_WATCHLIST_WORKSHEET,
                       create_if_missing=False)
    if ws is None:
        return 0
    existing = ws.get_all_values()
    _require_writable_header(existing, _STOCK_WATCHLIST_HEADERS, _STOCK_WATCHLIST_WORKSHEET)
    if len(existing) <= 1:
        return 0
    keep_rows = [r for r in existing[1:] if (r and r[0].strip() != name)]
    deleted = (len(existing) - 1) - len(keep_rows)
    if deleted == 0:
        return 0
    _write_whole_sheet(ws, existing,
                       [_write_header(existing[0], _STOCK_WATCHLIST_HEADERS)] + keep_rows)
    clear_read_cache()          # 刪除即清(§1)
    return deleted
