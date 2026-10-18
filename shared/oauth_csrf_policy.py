"""shared/oauth_csrf_policy.py — OAuth `state`（login CSRF 防護）常數 SSOT（L0，SEC-2）。

純常數模組，只依賴 L0 `shared.ttls`。使用端：
- L1 `src/data/portfolio/oauth_nonce_store.py`（server 端一次性 nonce 表）
- L1 `src/data/portfolio/oauth_state.py`（發 nonce / 驗 callback）

為什麼要 server 端 nonce ＋ 綁瀏覽器（SEC-2 根因，寫下來防重犯）
--------------------------------------------------------------------
Google 轉跳回來是一次**整頁載入** ⇒ Streamlit 開的是**新 session**，`session_state` 裡的
「期望 state」幾乎一定不在 —— 舊版因此把「沒有期望值」一律放行（v19.63 修迴圈），
等於 state 檢查形同虛設：攻擊者把**他自己的** `?code=` 塞給受害者，受害者就登入攻擊者帳號。
只把 nonce 存到 server 也不夠：攻擊者在**他自己的瀏覽器**打開本站就能領到一個合法 nonce。
所以 nonce 必須綁定「發起登入的那個瀏覽器」—— 本 repo 用 Streamlit 自己發的
`_streamlit_xsrf` cookie（同一瀏覽器跨整頁載入不變；攻擊者讀不到也寫不進受害者的 cookie）。
"""
from __future__ import annotations

from shared.ttls import TTL_15MIN

#: 一個 OAuth nonce 從最後一次發出（每次 rerun 畫登入鈕都會延長）起算的有效秒數。
#: 理由：使用者按「🔐 用 Google 登入」後要在 Google 選帳號、按同意 —— 實務上數十秒，
#: 15 分鐘留足餘裕（含 2FA）；再長只是讓一個外洩的 authorize URL 活更久。沿用 TTL SSOT。
OAUTH_STATE_TTL_SEC: int = TTL_15MIN

#: server 端 nonce 表的上限筆數（滿了先丟最久沒被延長的那筆）。
#: 理由：每個開著登入鈕的瀏覽器 session 佔 1 筆（約 200 bytes）⇒ 1 萬筆 ≈ 2 MB，
#: 遠高於本 app 同時在線人數，又能擋「狂開新 session 灌爆記憶體」。被擠掉的人
#: 只會在 callback 看到「連結過期」並重按一次登入（fail closed，不會放行）。
OAUTH_STATE_MAX_ENTRIES: int = 10_000

#: 「已過期而被清掉」的 nonce 墓碑上限筆數(只存 nonce 字串,約 32 bytes/筆 ⇒ 1 萬筆 ≈ 0.5 MB)。
#: 理由(SEC-2 審計 SA1-S1):過期項通常在**別的 session** 的 `issue()` 被順手清掉,沒有墓碑時
#: callback 只會看到 `unknown`,而 docs 把「持續 unknown」解讀成多副本／重啟 —— 誤導診斷。
#: 墓碑讓「閒置超過 TTL 才回來」照實回報 `expired`;與 nonce 表同量級即可(滿了丟最舊,FIFO)。
OAUTH_STATE_EXPIRED_TOMBSTONE_MAX: int = OAUTH_STATE_MAX_ENTRIES

#: Streamlit 發給瀏覽器的 XSRF cookie 名稱（streamlit 1.59 `XSRF_COOKIE_NAME`；本 repo
#: **不 import streamlit 內部模組**，故在此具名）。格式 v2：`2|<mask hex>|<masked token hex>|<ts>`，
#: mask 每個回應都會換，**真正不變的是解遮罩後的 token bytes**（見 oauth_state._decode_xsrf_token）。
STREAMLIT_XSRF_COOKIE_NAME: str = "_streamlit_xsrf"

#: secrets 開關鍵名：`oauth_csrf_enforce = false` → 驗證失敗**仍放行**登入、但照記 reason code。
#: 預設（沒設）＝ True ＝ 嚴格。只給「正式環境量測到 cookie 讀不到 / 多副本 nonce 表不共用」
#: 時讓擁有者能立刻恢復登入用；量測方法見 docs/OAUTH_SETUP.md「SEC-2 量測」。
OAUTH_CSRF_ENFORCE_SECRET_KEY: str = "oauth_csrf_enforce"
