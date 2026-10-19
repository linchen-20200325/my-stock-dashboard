"""shared/oauth_session_policy.py — 重新整理後「靜默恢復 Google 登入」常數 SSOT（L0，vNext 1.0-B2）。

純常數模組，零依賴。使用端：
- L1 `src/data/portfolio/oauth_state.py`（設 / 讀網址記號、發靜默授權轉跳、處理 `?error=` 回呼）
- L1 `src/data/portfolio/gsheet_portfolio.py`（token 過期且無 refresh_token → 請重新整理）
- infra `infra/oauth.py`（authorize URL 的 `prompt=none`）

客戶硬性條件（DEC-062 Q2＝B，原文）：「不得保存 Google 密碼或 Google 憑證」
==========================================================================
所以**沒有任何 token 活得比 Streamlit session 久**：沒有 server 端 token 表、不寫 cookie /
localStorage、不用 `st.login`。重新整理 ＝ 新 session ＝ 沒有 token。恢復登入的做法是
**靜默重新授權**：登入成功後在網址掛一個**非憑證**的記號（`?gs=<MAC>`，見下）；重新整理時
（新 session、沒有 token）看到記號 → 標記本 session 已試過 → 發 nonce（state ＝ `nonce.sheet.記號`）→
瀏覽器端 script 先以 `history.replaceState` 拿掉 `gs`（同一筆歷史紀錄，不新增 → 按「上一頁」不會又轉一次）
→ 整個分頁轉去 Google 並帶 `prompt=none`（Google 不顯示任何畫面，已登入且授權過就直接帶 `code`
回原 redirect_uri；否則帶 `error=` 回來）→ 回呼走既有 SEC-2 nonce 驗證 → token 一樣只住在
`st.session_state`。
（📌 2026-10-19 更正：23596359 初版這裡寫的是「固定值 `?gs=1`、伺服器端先拿掉記號（一次性）」——
兩者都已在稽核修正輪改掉：固定值可偽造 → 改 MAC；伺服器端拿記號會多一筆帶記號的歷史紀錄 →
上一頁陷阱 → 改由 script replaceState。舊說法據實保留於此，⛔ 不是漏改。）

記號本身**不是**憑證：它只代表「上一次在這個網址、以**這個 Google 帳號 + 這本 Sheet** 登入成功過」。
1.0-B2 稽核修正（SA1）：記號值 ＝ HMAC-SHA256（金鑰＝OAuth client_secret，訊息＝網域字串＋sub＋Sheet ID）
的前 `OAUTH_SILENT_TAG_HEX_LEN` 個 hex。它跟著 `state` 繞 Google 一圈回來，回呼換到 token 後以
**新的** sub 與 state 帶回的 Sheet 重算比對 —— 對不上就**丟掉 token、不登入**。因此：
  · 攻擊者給的 `?gs=<亂數>&sheet=<他的 Sheet>` → 算不出合法 MAC（沒有 client_secret）→ 不登入、不綁；
  · 同一台電腦換了 Google 帳號 → sub 不同 → 不會靜默登入成另一個人（守住 v19.293 選帳號的本意）。
記號不含 sub / email 原文（單向 MAC），也不是任何 Google 憑證。
金鑰由 OAuth client_secret 加網域分隔字串（`OAUTH_SILENT_MAC_DOMAIN`）推出；**輪換 client_secret ⇒
所有舊記號一次失效**（使用者會看到一次「帳號或 Sheet 與上次不同」提示，按登入鈕即可）。
登入後換了 Sheet（側欄 / 📁 組合管理）→ `oauth_state.sync_silent_marker()` 以**本 session 自己的** sub
重算記號（只對「強驗登入」的 session 做；稽核修正第二輪 MUST-1）。
"""
from __future__ import annotations

#: 網址上的「可以試一次靜默恢復登入」記號參數名（非憑證；見檔頭）。
#: 理由：短、與既有 `?sheet=` / `?sid=` 不衝突（2026-10-18 全 repo grep `query_params` 實測只用到這兩個 + 舊 `chips`）。
OAUTH_SILENT_MARKER_PARAM: str = "gs"
#: ~~`OAUTH_SILENT_MARKER_VALUE = "1"`~~（23596359 初版：固定值，任何人都能偽造 → 稽核 SA1 SHOULD-1 改為 MAC；
#: 有意識的移除，⛔ 不是漏刪）。

#: 記號值（＝ MAC 截斷）的 hex 長度。128 bits：對「離線猜一個能過比對的值」綽綽有餘，網址也不會太長。
OAUTH_SILENT_TAG_HEX_LEN: int = 32
#: MAC 的網域分隔字串（domain separation）：同一把 client_secret 若日後拿去算別的 MAC，不會互相冒用。
OAUTH_SILENT_MAC_DOMAIN: str = "vn1-gs"

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
#: 需要使用者登入 / 互動 / 同意 / 選帳號。收到這幾個 → 顯示「請按側欄登入」的藍色提示（st.info）。
#: 其他代碼（例：`access_denied`）走通用訊息（見 `OAUTH_DISPLAYABLE_ERROR_CODES`）。
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

#: 畫面上**可以照實顯示**的 `?error=` 代碼（RFC 6749 §4.1.2.1 ＋ OpenID Connect Core §3.1.2.6 的標準代碼）。
#: 理由（稽核 SA1 NIT-1）：`error` 來自網址，攻擊者可以塞一個長得像代碼的句子（例：`visit-evil.com-to-fix`）
#: 讓它出現在本站畫面上。不在這張表裡 → 只顯示通用文字、⛔ 不顯示代碼。
OAUTH_DISPLAYABLE_ERROR_CODES: frozenset[str] = frozenset({
    # RFC 6749 §4.1.2.1
    "invalid_request", "unauthorized_client", "access_denied", "unsupported_response_type",
    "invalid_scope", "server_error", "temporarily_unavailable",
    # OpenID Connect Core §3.1.2.6
    "interaction_required", "login_required", "account_selection_required", "consent_required",
    "invalid_request_uri", "invalid_request_object", "request_not_supported",
    "request_uri_not_supported", "registration_not_supported",
})

#: session_state 旗標：本 session 的登入是因為「token 過期且無 refresh_token」才被清掉的。
#: 有它時，之後「沒有 token」的 `LoginRequiredError` 一律帶逾時訊息（而不是「請先登入」），
#: 頁面也據此畫灰色的「登入已逾時」卡（稽核 SA2 MUST-1）。下一次登入成功 / 登出時清掉。
OAUTH_LOGIN_EXPIRED_SESSION_KEY: str = "_oauth_login_expired"

#: token 過期且沒有 refresh_token（靜默恢復登入的常態，約 1 小時）時給使用者看的訊息。
#: 放 L0：L1 `gsheet_portfolio` 拋例外用、L5 `page_hold` 畫灰卡用 —— 同一句話只有一份。
OAUTH_LOGIN_EXPIRED_MSG: str = ("Google 登入已逾時，請重新整理頁面以自動恢復登入，"
                                "或按側欄「🔐 用 Google 登入」重新登入。")

#: session_state 旗標：本 session 的登入是**強驗通過**（consume ok）且掛過記號的那一種。
#: `sync_silent_marker()` 只對有這個旗標的 session 重算記號 —— 安全閥放行的登入、開關停用時的登入
#: 一律沒有它（稽核修正第二輪 MUST-1）。登出 / 重新登入時重設。
OAUTH_SILENT_ELIGIBLE_SESSION_KEY: str = "_oauth_silent_eligible"
