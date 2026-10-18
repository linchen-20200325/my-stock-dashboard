# Google 登入（OAuth）— SEC-2 防偽造量測與安全閥

> 本檔目前只收 SEC-2（login CSRF）修法上線後的**量測方法與應變**。
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

| reason | 意思 | 正常會出現嗎 |
|---|---|---|
| `unknown` | 查無此 nonce：已用過（重新整理回呼網址）、被擠掉、**或回呼落到另一個 process**（多副本／重啟） | 偶發可以；**正常登入就一直出現** ⇒ 懷疑多副本或 process 重啟 |
| `expired` | 按登入後超過 15 分鐘才回來 | 偶發 |
| `mismatch` | 回呼的瀏覽器不是發起登入的那個（login CSRF 的樣子，或在 A 瀏覽器按、B 瀏覽器開回呼） | 不應常見 |
| `no_cookie` | 回呼請求讀不到 `_streamlit_xsrf` cookie | **正常登入就出現** ⇒ 正式環境拿不到 cookie |

2026-10-18 本機實測（streamlit 1.59.2 starlette server，真 websocket 連線）：同一瀏覽器兩個
session（cookie 已被重新遮罩）綁定值相同、不同瀏覽器不同、沒 cookie 為 None。
⚠️ **未在 Streamlit Cloud 實測**（沙箱連不到）。

## 安全閥（只給擁有者在正式環境登入壞掉時用）

若正式環境量到「正常登入就被拒」（`no_cookie` 或持續 `unknown`），在 Streamlit Cloud secrets 加：

```toml
oauth_csrf_enforce = false
```

效果：驗證失敗**仍放行登入**，但照記上面那行 log（`enforce=off`）；放行的登入**不會**自動回綁
state 帶回的 Sheet ID。預設（沒設）＝嚴格。⚠️ 關閉期間 login CSRF 防護失效，查明原因後應移除。
