# Google 登入（OAuth）— SEC-2 防偽造量測與安全閥

> 本檔收 SEC-2（login CSRF）修法上線後的**量測方法與應變**，以及 1.0-B2「重新整理後靜默恢復登入」（見文末）。
> GCP OAuth Client 的建立步驟見 `infra/oauth.py` 檔頭。

## 機制（一句話）

登入鈕產生的 `state` nonce 存在 **server 端**（`src/data/portfolio/oauth_nonce_store.py`，
process 級、15 分鐘 TTL、上限 1 萬筆，常數見 `shared/oauth_csrf_policy.py`），
並綁定**發起登入的瀏覽器**（Streamlit 的 `_streamlit_xsrf` cookie 解遮罩後的 token 取 sha256）。
Google 轉跳回來時，只有「登記過、未過期、同一瀏覽器、第一次使用」才換 token。
⛔ 不存 Google 密碼、不存 token、不存 cookie 原文（DEC-062）。

## SEC-2 量測（看 Streamlit Cloud 的 app log）

驗證未通過時 log 只會有一行（⛔ 不含任何 nonce / cookie / token 值）：

```
[oauth_state] SEC-2 callback state 驗證未通過 reason=<代碼> enforce=<on|off>
```

另外，畫登入鈕時若讀不到 cookie（nonce 因此不登記），每個 session 記一次：

```
[oauth_state] SEC-2 login nonce 未登記 reason=no_cookie
```

| reason | 意思 | 正常會出現嗎 |
|---|---|---|
| `unknown` | 查無此 nonce：已用過（重新整理回呼網址）、被容量上限擠掉、**或回呼落到另一個 process**（多副本／重啟） | 偶發可以；**正常登入就一直出現** ⇒ 懷疑多副本或 process 重啟 |
| `expired` | 登入鈕最後一次畫出後超過 15 分鐘才回來。過期項即使已被別的 session 順手清掉，也留有墓碑（只存 nonce，上限 1 萬筆、滿了丟最舊）⇒ 仍回 `expired`，**不會**混進 `unknown` | 偶發（例：分頁閒置很久才按登入） |
| `mismatch` | 回呼的瀏覽器不是發起登入的那個（login CSRF 的樣子，或在 A 瀏覽器按、B 瀏覽器開回呼） | 不應常見 |
| `no_cookie` | 回呼請求讀不到 `_streamlit_xsrf` cookie | **正常登入就出現**（且畫登入鈕時也有上面那行 `login nonce 未登記`）⇒ 正式環境拿不到 cookie |

2026-10-18 本機實測（streamlit 1.59.2 starlette server，真 websocket 連線）：同一瀏覽器兩個
session（cookie 已被重新遮罩）綁定值相同、不同瀏覽器不同、沒 cookie 為 None。
⚠️ **未在 Streamlit Cloud 實測**（沙箱連不到）。
⚠️ 墓碑也在單一 process 記憶體內：process 重啟後，重啟前發出的 nonce 一律回 `unknown`。

## 安全閥（只給擁有者在正式環境登入壞掉時用）

若正式環境量到「正常登入就被拒」（`no_cookie` 或持續 `unknown`），在 Streamlit Cloud secrets 加：

```toml
oauth_csrf_enforce = false
```

效果：驗證失敗**仍放行登入**，但照記上面那行 log（`enforce=off`）；放行的登入**不會**自動回綁
state 帶回的 Sheet ID。預設（沒設）＝嚴格。⚠️ 關閉期間 login CSRF 防護失效，查明原因後應移除。

## 1.0-B2 重新整理後靜默恢復 Google 登入（DEC-062 Q2＝B）

客戶硬性條件（原文）：「不得保存 Google 密碼或 Google 憑證」。所以**沒有任何 token 活得比
Streamlit session 久**：沒有 server 端 token 表、不寫 cookie / localStorage、不用 `st.login`。
重新整理頁面 ＝ 新 session ＝ 沒有 token；恢復靠「**靜默重新授權**」。

### 怎麼運作

1. 你按「🔐 用 Google 登入」成功、且 SEC-2 驗證是**強驗通過**（consume ok）時，網址會多一個記號
   `?gs=1`（與 `?sheet=` 並列）。
2. 重新整理 → 新 session 沒有 token，但網址有 `gs=1` → app **先把記號拿掉**（一次性），照原本的方式
   發一個 15 分鐘的 nonce，把**整個分頁**轉去 Google，並帶 `prompt=none`（Google 不顯示任何畫面）。
   頁首會短暫出現灰字「正在恢復 Google 登入…」。
3. Google 判斷你仍登入、也授權過 → 直接帶 `code` 回原本的 redirect_uri → 走既有 SEC-2 驗證 →
   token 一樣只放在這個 session 的記憶體 → 記號重新掛上（下次重新整理仍可恢復）。
4. Google 做不到（要你選帳號、要同意、沒登入 Google…）→ 帶 `?error=` 回來 → 頁首灰色提示
   「未能自動恢復登入（Google 需要你再確認一次），請按側欄「🔐 用 Google 登入」。」。
   此時網址已經沒有記號 ⇒ **不會再轉、不會迴圈**（同一分頁最多轉一次）。
5. 按「🚪 登出」會一併拿掉記號 ⇒ 重新整理不會又登回去。

### 存了什麼（全部不是憑證）

| 東西 | 放哪 | 多久 |
|---|---|---|
| `gs=1` 記號 | 網址 | 直到登出 / 一次靜默恢復用掉 |
| OAuth nonce（`state`） | server process 記憶體（綁瀏覽器 cookie 雜湊） | 15 分鐘、一次性 |
| access token / id_token | **只**在本 session 的 `st.session_state` | session 結束即消失 |

記號只代表「這個網址上次登入成功過，可以試一次」。別人拿到你的網址，在他自己的瀏覽器打開，
只會用**他自己的** Google 登入狀態去問 Google，拿不到你的帳號；回呼仍要過 SEC-2「同一瀏覽器」檢查。

### 開關（停用）

```toml
oauth_silent_reauth = false
```

只有 `false` / `"false"` / `"0"` / `0` / `"no"` / `"off"` 會停用；沒設或其他值 ＝ 啟用。
停用後不掛記號、不轉跳 ⇒ 退回「重新整理後要再按一次登入」。
另外：安全閥 `oauth_csrf_enforce = false` 放行的登入（驗證沒過但被放行）**不會**掛記號。

### log（只有代碼，⛔ 不含 nonce / token / email / URL / Sheet ID）

```
[oauth_state] 1.0-B2 silent_reauth=redirect                      # 發出了靜默轉跳
[oauth_state] 1.0-B2 silent_reauth=skip reason=no_cookie         # 網址有記號，但讀不到瀏覽器 cookie（每 session 一次）
[oauth_state] 1.0-B2 silent_reauth=skip reason=disabled          # 網址有記號，但開關已關
[oauth_state] 1.0-B2 silent_reauth=skip reason=not_configured    # 網址有記號，但 OAuth Client 沒設定
[oauth_state] 1.0-B2 callback error=<Google 代碼> state=<ok|unknown|expired|mismatch|no_cookie|absent>
[gsheet_portfolio] 1.0-B2 login_expired reason=no_refresh_token  # 靜默恢復的登入用滿約 1 小時
```

`callback error=` 的 `state=` 是燒掉 nonce 時的 SEC-2 reason（意思見上方 SEC-2 表；`absent` ＝ 沒帶 state）。

### 已知限制（據實標明）

- **約 1 小時後要重新整理**：`prompt=none` 時 Google 通常**不發 refresh_token**（只有第一次同意 /
  `prompt=consent` 才發）。access token 過期後，讀寫 Sheet 會顯示「Google 登入已逾時，請重新整理頁面
  以自動恢復登入，或按側欄「🔐 用 Google 登入」重新登入。」並清掉本 session 的 token；
  **session 進行中途不會自動轉跳**，重新整理即可再靜默恢復一次。
  手動按鈕登入（`prompt=select_account consent`）仍會拿到 refresh_token，那一段 session 照舊自動續期。
- **瀏覽器同時登入多個 Google 帳號**：Google 可能回 `account_selection_required` / `interaction_required`
  → 灰色提示，按一次登入鈕選帳號即可（不會迴圈）。
- **Streamlit Cloud 的 iframe**：app 若被包在 iframe 裡，script 只會在「最上層頁面與 app **同源**」時
  導最上層頁面；跨來源時什麼都不做（不會把 iframe 自己導去 Google → 白畫面），畫面上的灰字就是出口。
  ⚠️ **未在 Streamlit Cloud 實測**（沙箱連不到）—— 請依下方清單驗收。
- **process 重啟 / 多副本**：nonce 在單一 process 記憶體內。轉跳出去後 process 換了 → 回呼查無 nonce →
  顯示 SEC-2 的「Google 登入驗證未通過…」紅字（log `reason=unknown`），按一次登入鈕即可；網址記號已拿掉，不會迴圈。

### 客戶驗收清單（Streamlit Cloud）

1. 開 app → 側欄「🔐 用 Google 登入」→ 登入成功。看網址：應該有 `gs=1`（有綁 Sheet 的話還有 `sheet=`）。
2. **按瀏覽器重新整理**。預期：頁面閃一下（或短暫看到灰字「正在恢復 Google 登入…」）→ 側欄回到
   「🟢 已登入：<你的信箱>」，持股照常讀得到，**沒有**跳出 Google 選帳號畫面。
3. 若第 2 步停在灰字「正在恢復 Google 登入…」超過幾秒沒反應 → 代表 iframe 擋住了最上層轉跳。
4. 若第 2 步出現灰色「未能自動恢復登入…」→ 按一次登入鈕可登入；回報當時瀏覽器是否登入多個 Google 帳號。
5. 按「🚪 登出」→ 再重新整理 → 預期**維持登出**（不會自己登回去）。
6. 登入後放著超過 1 小時再操作持股 → 預期看到「Google 登入已逾時，請重新整理頁面…」→ 重新整理 → 恢復登入。

回報時請附：第幾步、看到的字（截圖）、網址上有沒有 `gs=1`，以及 Streamlit Cloud log 裡以
`[oauth_state] 1.0-B2` / `[gsheet_portfolio] 1.0-B2` 開頭的那幾行。
