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

> 📌 2026-10-19 稽核修正輪（兩組獨立稽核 PASS-WITH-FIXES 後）：記號改為**綁帳號＋Sheet 的 MAC**、
> 修掉「上一頁走不出去」、`?error=` 不再一律燒 nonce、只顯示標準錯誤代碼、登入逾時改為灰卡。
> 下文已是修正後的行為。

### 怎麼運作

1. 你按「🔐 用 Google 登入」成功、且 SEC-2 驗證是**強驗通過**（consume ok）時，網址會多一個記號
   `?gs=<32 個 hex>`（與 `?sheet=` 並列）。記號 ＝ HMAC-SHA256（金鑰＝OAuth client_secret，
   內容＝網域分隔字串 `vn1-gs`＋你的 Google 帳號 ID（sub）＋網址上這本 Sheet 的 ID）的前 32 個 hex。
   - 金鑰直接取自 OAuth client_secret、靠網域分隔字串與其他用途區隔 ⇒ **輪換 client_secret 會讓所有舊記號
     一次失效**（每位使用者下一次重新整理會看到一次「帳號或 Sheet 與上次不同」，按登入鈕即可）。
   - 登入後才綁 / 換 Sheet（側欄、📁 組合管理、💼 頁的就地綁定）→ app 會以**這個 session 自己的** Google
     帳號 ID 重算記號（只對強驗登入的 session；安全閥放行的登入不會）。側欄是寫完就地重算；📁 組合管理與
     就地綁定寫完都會重跑一輪，在那一輪重算 ⇒ 換完馬上重新整理也對得上。
     ~~（重算時 Sheet 取網址上的 `?sheet=`）~~ 📌 2026-10-19 第三輪（客戶核准，有意識的修改）：重算時的 Sheet
     **只信這個 session 裡使用者自己設定的那本**（側欄 / 組合管理 / 就地綁定 / 強驗登入回綁時寫入）；網址上的
     `?sheet=` 若被外部改成別本、與 session 不同 → **不重算**（log `resync_skip reason=url_sheet_not_session_sheet`）。
     修前這裡會替你自己的帳號算出「綁那本外來 Sheet」的記號，下次重新整理就自動綁上它。
2. 重新整理 → 新 session 沒有 token，但網址有記號 → app 照原本的方式發一個 15 分鐘的 nonce，
   `state` 帶著 `nonce.Sheet.記號`；頁首短暫出現**灰字**（`st.caption`）「正在恢復 Google 登入…」；
   瀏覽器端的 script 先在**要導的那個視窗**上 `history.replaceState` 把網址裡的 `gs` 拿掉（同一筆
   歷史紀錄，不新增），成功後才把**整個分頁**導去 Google，帶 `prompt=none`（Google 不顯示任何畫面）。
3. Google 判斷你仍登入、也授權過 → 帶 `code` 回原本的 redirect_uri → 走既有 SEC-2 驗證 →
   換到 token 後，用**這次的** Google 帳號 ID 與 state 帶回的 Sheet **重算記號**比對：
   - 對得上 → 登入（token 一樣只放在這個 session 的記憶體）→ 記號重新掛上。
   - 對不上（換了 Google 帳號、網址上的 Sheet 被換掉、記號被竄改或偽造）→ **丟掉 token、不登入、
     不把 Sheet 綁進這個 session**，顯示**藍色提示**（`st.info`）「自動恢復登入的帳號或 Sheet 與上次不同，
     請按「🔐 用 Google 登入」手動登入。」但 state 帶回的 Sheet 會**寫回網址的 `?sheet=`**
     （只在 SEC-2 強驗通過時；⛔ 不寫 `gs`）⇒ 你手動登入時照常回綁那一本，不會弄丟。
4. Google 做不到（要你選帳號、要同意、沒登入 Google…）→ 帶 `?error=` 回來 → **藍色提示**（`st.info`）
   「未能自動恢復登入（Google 需要你再確認一次），請按側欄「🔐 用 Google 登入」。」
   落地網址沒有記號 ⇒ **不會再轉、不會迴圈**。靜默恢復的回呼不論 Google 回哪一種錯誤
   （含 `server_error` / `temporarily_unavailable`），或被 SEC-2 拒絕（例：process 重啟）、或換 token 失敗，
   state 帶回的 Sheet 都會寫回網址的 `?sheet=` —— 網址原本有 `?sheet=` 就保留原本的。
5. 按「🚪 登出」會拿掉**這個分頁**網址上的記號 ⇒ 重新整理不會又登回去（限制見下）。
6. 同一個 session 最多轉一次（session 旗標）。script 沒成功時分兩種，結果不同：
   - **還沒動到網址就停了**（app 在跨來源 iframe 裡、或 `replaceState` 本身失敗）→ 網址**仍帶記號**，
     下一次你按重新整理會再試一次 —— 仍是「每一次使用者動作最多一次」。
   - **網址已拿掉記號、但導去 Google 被瀏覽器擋下**（`location.replace` 失敗）→ 網址**已經沒有記號**，
     頁首停在灰字「正在恢復 Google 登入…」，重新整理也不會再試，請手動按登入鈕。

### 存了什麼（全部不是 Google 憑證）

| 東西 | 放哪 | 多久 | 是什麼 |
|---|---|---|---|
| `gs=<MAC>` 記號 | 網址 | 直到登出 / 被 script 拿掉 / 換掉 | 單向 MAC，綁帳號＋Sheet；不含帳號 / email 原文，沒有 client_secret 算不出來 |
| OAuth nonce（`state`） | server process 記憶體（綁瀏覽器 cookie 雜湊） | 15 分鐘、一次性 | 防 login CSRF |
| access token / id_token | **只**在本 session 的 `st.session_state` | session 結束即消失 | Google 憑證（不落地） |
| Sheet 讀取快取（`st.cache_data`） | server process 記憶體 | 15 分鐘（`TTL_15MIN`） | **Sheet 內容**（持股列 / 組合名），快取鍵含身分指紋（refresh_token 或 sub 的 sha256，**不是**憑證本身）；SEC-1 每人一格 |

別人拿到你的網址，在他自己的瀏覽器打開，只會用**他自己的** Google 帳號去問 Google；回呼重算記號時
帳號 ID 對不上 → 不登入。攻擊者寄 `?gs=<亂數>&sheet=<他的 Sheet>` 也一樣（他算不出合法記號）。

### 開關（停用）

```toml
oauth_silent_reauth = false
```

只有 `false` / `"false"` / `"0"` / `0` / `"no"` / `"off"` 會停用；沒設或其他值 ＝ 啟用。
停用後不掛記號、不轉跳 ⇒ 退回「重新整理後要再按一次登入」。
另外：安全閥 `oauth_csrf_enforce = false` 放行的登入（驗證沒過但被放行）**不會**掛記號；
OAuth Client 沒有 client_secret 時（算不出記號）靜默恢復整個停用。

### log（只有代碼，⛔ 不含 nonce / token / email / URL / Sheet ID / 記號值）

```
[oauth_state] 1.0-B2 silent_reauth=redirect                        # 發出了靜默轉跳
[oauth_state] 1.0-B2 silent_reauth=skip reason=no_cookie           # 網址有記號，但讀不到瀏覽器 cookie（每 session 一次）
[oauth_state] 1.0-B2 silent_reauth=skip reason=disabled            # 網址有記號，但開關已關
[oauth_state] 1.0-B2 silent_reauth=skip reason=not_configured      # 網址有記號，但 OAuth Client 沒設定
[oauth_state] 1.0-B2 silent_reauth=skip reason=no_client_secret    # 網址有記號，但沒有 client_secret（算不出記號）
[oauth_state] 1.0-B2 silent_reauth=skip reason=bad_url             # 防禦：組出來的轉跳目標不是 Google（不應發生）
[oauth_state] 1.0-B2 silent_reauth=reject reason=tag_mismatch      # 回呼重算記號對不上（換帳號 / 換 Sheet / 竄改）→ 不登入
[oauth_state] 1.0-B2 silent_reauth=reject reason=no_sub            # 回呼的 id_token 沒有帳號 ID → 無從比對 → 不登入
[oauth_state] 1.0-B2 silent_reauth=marker_not_set_no_sub           # 登入成功但 id_token 沒有帳號 ID → 不掛記號
[oauth_state] 1.0-B2 silent_reauth=marker_set_failed (<例外型別>)   # 掛記號失敗（登入不受影響）
[oauth_state] 1.0-B2 silent_reauth=marker_remove_failed (<例外型別>) # 登出時拿不掉記號
[oauth_state] 1.0-B2 silent_reauth=marker_resynced                 # 登入後換了 Sheet → 記號已依新 Sheet 重算
[oauth_state] 1.0-B2 silent_reauth=resync_skip reason=url_sheet_not_session_sheet  # 網址 Sheet ≠ session 設定的 Sheet → 不重算（每 session 一次）
[oauth_state] 1.0-B2 callback error=<標準代碼|other> state=<ok|unknown|expired|mismatch|no_cookie|kept|absent>
[gsheet_portfolio] 1.0-B2 login_expired reason=no_refresh_token    # 靜默恢復的登入用滿約 1 小時
```

`callback error=` 的 `state=`：靜默恢復（三段 state）的任何錯誤都會燒掉那個一次性 nonce，記的是 SEC-2 reason
（意思見上方 SEC-2 表）；一般登入（兩段 state）的錯誤（例：在新分頁按了取消）**不燒** nonce → `kept`
（原分頁那顆登入鈕再按一次仍能登入）；`absent` ＝ 沒帶 state。不在標準錯誤代碼表裡的代碼記成 `other`，
畫面上也只寫「Google 登入未完成。」不顯示代碼（避免網址上的字被搬上畫面）。

### 已知限制（據實標明）

- **約 1 小時後要重新整理**：`prompt=none` 時 Google 通常**不發 refresh_token**（只有第一次同意 /
  `prompt=consent` 才發）。access token 過期後，「💼 我的持股」的綁定 / 持股卡會顯示**灰色**
  「Google 登入已逾時」卡（指路：「Google 登入已逾時，請重新整理頁面以自動恢復登入，或按側欄
  「🔐 用 Google 登入」重新登入。」），本 session 的 token 會被清掉；**session 進行中途不會自動轉跳**。
  手動按鈕登入（`prompt=select_account consent`）仍會拿到 refresh_token，那一段 session 照舊自動續期。
  - ⚠️ 重新整理會**丟掉畫面上還沒存的編輯**（例：組合管理的表格編輯器）。
  - ⚠️ 側欄「🔐 用 Google 登入」按鈕會**開新分頁**（`st.link_button` 的行為）。
  - ⚠️ 舊版頁籤（凍結、本批不改）：📁 組合管理會把逾時顯示成**紅色** `st.error`、股利站顯示成**黃色**
    警告 —— 文字是同一句逾時訊息，只有顏色與新版頁面不同。
- ~~**換了 Sheet 之後第一次重新整理**：……按一次登入鈕即可（之後記號會綁新的那本）。~~
  （📌 2026-10-19 稽核第二輪更正：那句在 1d169927 不成立 —— 記號對不上時 Sheet 會被一起清掉、而且每次
  重新整理都一樣。現行行為見「怎麼運作」第 1、3 點：換 Sheet 會重算記號；萬一仍對不上，Sheet 留在網址，
  手動登入即回綁。舊句保留，⛔ 不是漏刪。）
- **記號仍可能對不上的情況**：日後若新增一個「寫 `?sheet=` 但寫完不重跑、也沒呼叫 `sync_silent_marker()`」
  的入口，換完 Sheet 立刻重新整理就會對不上一次（藍色提示、Sheet 留在網址、按一次登入即可）。
  目前已知的三個入口（側欄、📁 組合管理、💼 頁就地綁定）都有涵蓋（2026-10-19 全 repo 搜尋 `query_params['sheet']`
  只有側欄與 `portfolio_binder.apply_active_sheet` 兩處寫入，後者的呼叫點寫完都 `st.rerun()`；
  ⚠️ 單組搜尋結果，未經第二組驗證）。
- **`?sheet=` 的網址信任模型是既有的**（app.py v19.204：開新 session 時把網址上的 `?sheet=` 還原成「目前選的
  Sheet」，未登入也會；登入時跟著 state 回綁）。任何人都能寄一個帶 `?sheet=<某本>` 的連結 —— 那一本仍要你自己的
  Google 帳號有權限才讀得到。本批靜默恢復沒成功時「把 state 帶回的 Sheet 寫回網址」與它**同一個信任等級**，
  沒有放大；網址還原本身沒消毒等問題已另案追蹤（不在本批範圍）。
  📌 2026-10-19 第三輪（客戶核准）補限定：上句只對**未登入**的落地頁成立。**已登入**的分頁收到 `?error=…`
  時**不**寫 state 帶回的 Sheet（網址原有的照留），重算記號也只信 session 的 Sheet（見「怎麼運作」第 1 點）——
  ~~登入中的分頁也與 v19.204 同一個信任等級~~（修前 `?error=` 分支在已登入分頁也會寫，再被重算記號信任，
  等於放大了；有意識的更正）。
- **觀察清單那一半**：讀觀察清單的瞬間剛好逾時，會記成「觀察清單讀不到」（持股本身不受影響），
  與其他讀取失敗同一個說法 —— 機率極低（要剛好落在兩次讀取之間），本批不另外處理。
- **瀏覽器同時登入多個 Google 帳號**：Google 可能回 `account_selection_required` / `interaction_required`
  → 藍色提示，按一次登入鈕選帳號即可（不會迴圈）。
- **Streamlit Cloud 的 iframe**：app 若被包在 iframe 裡，script 只會在「最上層頁面與 app **同源**」時
  動最上層頁面；跨來源時什麼都不做（不會把 iframe 自己導去 Google → 白畫面），網址原封不動，
  畫面上的灰字就是出口（下一次重新整理會再試一次）。⚠️ **未在 Streamlit Cloud 實測**（沙箱連不到）。
- **登出只管得到這個分頁現在的網址**：登出拿掉記號在前端是新增一筆歷史紀錄。其他還開著的分頁、或按
  「上一頁」回到帶記號的舊網址，在你的 Google 仍登入時會**再靜默登入一次** —— 但只會登回**同一個帳號、
  同一本 Sheet**（記號綁定）。要徹底登出請一併登出 Google 或關掉那些分頁。
- **連線中斷太久後自動重連**：websocket 斷線超過 Streamlit 的 session 保留時間（disconnectedSessionTTL）
  後重連 ＝ 新 session → 網址若還帶記號，會在**你沒按任何東西**的情況下靜默轉跳一次。
- **process 重啟 / 多副本**：nonce 在單一 process 記憶體內。轉跳出去後 process 換了 → 回呼查無 nonce →
  顯示 SEC-2 的「Google 登入驗證未通過…」紅字（log `reason=unknown`），按一次登入鈕即可；不會迴圈。

### 客戶驗收清單（Streamlit Cloud）

1. 開 app → 側欄「🔐 用 Google 登入」→ 登入成功。看網址：應該有 `gs=` 後面一串 32 個英數字
   （有綁 Sheet 的話還有 `sheet=`）。
2. **按瀏覽器重新整理**。預期：頁面閃一下（或短暫看到灰字「正在恢復 Google 登入…」）→ 側欄回到
   「🟢 已登入：<你的信箱>」，持股照常讀得到，**沒有**跳出 Google 選帳號畫面。
3. 接著按瀏覽器「**上一頁**」。預期：**不會**又自動轉一次 Google、也不會卡在 app 出不去。
4. 若第 2 步停在灰字「正在恢復 Google 登入…」超過幾秒沒反應 → 代表 iframe 擋住了最上層轉跳（請回報）。
5. 若第 2 步出現藍色「未能自動恢復登入…」→ 按一次登入鈕可登入；回報當時瀏覽器是否登入多個 Google 帳號。
6. 按「🚪 登出」→ 再重新整理 → 預期**維持登出**（不會自己登回去）。
6b. （第一次使用的情境）登入時還沒綁 Sheet → 登入後在側欄貼上 Sheet → **馬上**重新整理 → 預期仍自動恢復登入，
   且持股讀的是剛綁的那一本（網址的 `gs=` 那串在綁 Sheet 後會變）。
7. 登入後放著超過 1 小時，再到「💼 我的持股」按一次執行 → 預期綁定 / 持股卡是**灰色**「Google 登入已逾時」
   （**不是紅色**錯誤）→ 按重新整理 → 恢復登入（若有沒存的編輯會不見）。

回報時請附：第幾步、看到的字（截圖）、網址上有沒有 `gs=`，以及 Streamlit Cloud log 裡以
`[oauth_state] 1.0-B2` / `[gsheet_portfolio] 1.0-B2` 開頭的那幾行。
