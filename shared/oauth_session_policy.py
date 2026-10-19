"""shared/oauth_session_policy.py — 重新整理後「靜默恢復 Google 登入」常數 SSOT（L0，vNext 1.0-B2）。

純常數模組，零依賴。使用端：
- L1 `src/data/portfolio/oauth_state.py`（設 / 讀網址記號、發靜默授權轉跳、處理 `?error=` 回呼）
- L1 `src/data/portfolio/gsheet_portfolio.py`（token 過期且無 refresh_token → 請重新整理）
- infra `infra/oauth.py`（authorize URL 的 `prompt=none`）

客戶硬性條件（DEC-062 Q2＝B，原文）：「不得保存 Google 密碼或 Google 憑證」
==========================================================================
所以**沒有任何 token 活得比 Streamlit session 久**：沒有 server 端 token 表、不寫 cookie /
localStorage、不用 `st.login`。重新整理 ＝ 新 session ＝ 沒有 token。恢復登入的做法是
**靜默重新授權**：登入成功後在網址掛一個**非憑證**的一次性記號（`?gs=1`）；重新整理時看到
記號 → 先把記號拿掉（一次性）→ 整個分頁轉去 Google 並帶 `prompt=none`（Google 不顯示任何畫面，
已登入且授權過就直接帶 `code` 回原 redirect_uri；否則帶 `error=` 回來）→ 回呼走既有 SEC-2
nonce 驗證 → token 一樣只住在 `st.session_state`。

記號本身**不是**憑證：它只代表「上一次在這個網址登入成功過，可以試一次靜默恢復」。
任何人複製這個網址，在**自己的**瀏覽器打開只會用**自己的** Google 登入狀態去問 Google
（拿不到別人的帳號）；而回呼仍要過 SEC-2「同一瀏覽器發起」的 nonce 檢查。
"""
from __future__ import annotations

#: 網址上的「可以試一次靜默恢復登入」記號參數名與值（非憑證；見檔頭）。
#: 理由：短、與既有 `?sheet=` / `?sid=` 不衝突（2026-10-18 全 repo grep `query_params` 實測只用到這兩個 + 舊 `chips`）。
OAUTH_SILENT_MARKER_PARAM: str = "gs"
OAUTH_SILENT_MARKER_VALUE: str = "1"

#: Google authorize 端點的 `prompt` 值：不顯示任何畫面，做不到就以 `error=` 回來。
#: ⚠️ OpenID Connect 規定 `none` 必須**單獨**出現，不得與 `consent` / `select_account` 併用。
OAUTH_PROMPT_NONE: str = "none"

#: secrets 開關鍵名：`oauth_silent_reauth = false` → 完全停用靜默恢復（不設記號、不轉跳），
#: 退回「重新整理後要再按一次登入鈕」。預設（沒設）＝ 啟用。
OAUTH_SILENT_REAUTH_SECRET_KEY: str = "oauth_silent_reauth"

#: secrets 布林開關「明確關閉」的字串值（小寫比較）。`oauth_csrf_enforce` 與
#: `oauth_silent_reauth` 共用同一套解析：只有 False / 這些字串（含整數 0 → "0"）才關，其他一律開。
SECRET_FLAG_OFF_STRINGS: frozenset[str] = frozenset({"false", "0", "no", "off"})

#: 回呼網址上「這是一次 OAuth 回呼」的參數；任一個在場時**不得**發起靜默轉跳
#: （避免回呼尚未處理完又轉一次 → 迴圈）。
OAUTH_CALLBACK_QUERY_KEYS: tuple[str, ...] = ("code", "error", "state")

#: `prompt=none` 做不到時 Google 回的 `error` 代碼（OpenID Connect Core §3.1.2.6）：
#: 需要使用者登入 / 互動 / 同意 / 選帳號。收到這幾個 → 顯示「請按側欄登入」的灰色提示。
#: 其他代碼（例：`access_denied`）走通用訊息（只顯示白名單字元的代碼本身）。
OAUTH_SILENT_FAILURE_ERROR_CODES: frozenset[str] = frozenset({
    "login_required",
    "interaction_required",
    "consent_required",
    "account_selection_required",
})

#: session_state 旗標：本 session 已經「用掉」靜默恢復的機會（已轉跳過 / 已記過略過原因 /
#: 登入在 session 中途逾時 / 使用者登出）。有它就**不再**轉跳 —— 每個 session 最多一次，
#: 且 session 進行中途絕不自動轉跳（v19.63 迴圈教訓）。
OAUTH_SILENT_ATTEMPTED_SESSION_KEY: str = "_oauth_silent_reauth_attempted"
