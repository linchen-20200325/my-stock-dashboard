"""src/ui/pages/api_diagnostic.py — API Key & 連線根因診斷面板

掛在 tab_diag 第一格，用來釐清「Key 已設但全站抓不到資料」的常見根因：
1. st.secrets 是否能 parse（TOML 格式錯會整段 fallback 到空）
2. 每把 Key 的狀態（已設定／未設定／解析失敗）與來源（st.secrets / os.environ / none）
3. PROXY 是否已設定（最常見兇手：把所有外連導去打不通的 NAS）
4. 各 API endpoint「走 proxy vs 直連」雙跑比對

D6 資安（Issue #1113，客戶 D6 授權的最小修補）：本頁**只顯示狀態，不顯示任何值**。
- 只列固定的核准 Key 名稱 + 狀態 + 來源；⛔ 不顯示金鑰前後碼、長度、完整 proxy URL、
  secrets 全部 key 名稱或數量。
- 每個探測的畫面結果只有：成功／失敗、整數 HTTP 狀態碼、固定列舉的錯誤類別
  （逾時／連線失敗／代理錯誤／認證失敗(401/403)／伺服器錯誤(5xx)／其他）。
  ⛔ 不顯示例外原文、回應本文、URL、標頭、query string。
- 請求本身（端點、參數、標頭、timeout、verify）一字未動；只改「怎麼把結果上畫面」。

純 Streamlit 顯示，不寫入 session_state 以外的副作用。
"""
from __future__ import annotations

from src.config import FINMIND_API_URL  # Batch 10b v18.412 SSOT

import contextlib
import io
import os
import time
import streamlit as st

#: 固定核准顯示的 Key 名稱（D6）。⚠️ 只有名稱與狀態可上畫面。
APPROVED_KEY_NAMES: tuple[str, ...] = (
    'GEMINI_API_KEY', 'FINMIND_TOKEN', 'FRED_API_KEY',
    'PROXY_URL', 'PROXY_HOST', 'PROXY_PORT',
)

STATE_SET = '已設定'
STATE_UNSET = '未設定'
STATE_PARSE_FAIL = '解析失敗'

SRC_SECRETS = 'st.secrets'
SRC_ENV = 'os.environ'
SRC_NONE = 'none'

#: 錯誤類別固定列舉（D6）：畫面上只能出現這些字，不得夾帶例外原文。
ERR_TIMEOUT = '逾時'
ERR_CONNECTION = '連線失敗'
ERR_PROXY = '代理錯誤'
ERR_AUTH = '認證失敗(401/403)'
ERR_SERVER = '伺服器錯誤(5xx)'
ERR_OTHER = '其他'
ERROR_CATEGORIES: tuple[str, ...] = (
    ERR_TIMEOUT, ERR_CONNECTION, ERR_PROXY, ERR_AUTH, ERR_SERVER, ERR_OTHER,
)


def _safe_secret(key: str):
    """安全讀 st.secrets[key]。回傳 (value, failed)。

    D6：failed 只是布林——⛔ 不回傳也不保留例外原文（可能帶檔案路徑／秘密片段）。
    """
    try:
        sec = getattr(st, 'secrets', None)
        if sec is None:
            return None, True
        if key in sec:
            return sec[key], False
        return None, False
    except Exception:
        return None, True


def _resolve_key(key: str) -> dict:
    """回傳一把 key 的解析結果：名稱、來源、狀態、值（僅供探測用，⛔ 不上畫面）。"""
    sec_val, sec_failed = _safe_secret(key)
    env_val = os.environ.get(key, '')
    if sec_val:
        return {'name': key, 'source': SRC_SECRETS, 'val': sec_val, 'state': STATE_SET}
    if env_val:
        return {'name': key, 'source': SRC_ENV, 'val': env_val, 'state': STATE_SET}
    return {'name': key, 'source': SRC_NONE, 'val': '',
            'state': STATE_PARSE_FAIL if sec_failed else STATE_UNSET}


def _classify_exception(e: BaseException) -> str:
    """例外 → 固定錯誤類別。只看型別，⛔ 不讀例外訊息。"""
    import requests
    ex = requests.exceptions
    if isinstance(e, ex.ProxyError):       # ProxyError 是 ConnectionError 子類，要先判
        return ERR_PROXY
    if isinstance(e, ex.Timeout):          # ConnectTimeout 同時是 ConnectionError 子類，要先判
        return ERR_TIMEOUT
    if isinstance(e, ex.ConnectionError):  # 含 SSLError
        return ERR_CONNECTION
    return ERR_OTHER


def _classify_status(code: int) -> str | None:
    """HTTP 狀態碼 → 固定錯誤類別；< 400 回 None（成功）。"""
    if code < 400:
        return None
    if code in (401, 403):
        return ERR_AUTH
    if 500 <= code <= 599:
        return ERR_SERVER
    return ERR_OTHER


def _probe(label: str, url: str, params: dict | None = None,
           proxies: dict | None = None, timeout: int = 8,
           headers: dict | None = None) -> tuple[bool, str]:
    """輕量探測，回傳 (ok, msg)。不丟例外。

    v19.170:新增 headers 參數——診斷需要真的打 API，但憑證只走 header，
    不進 query string(避免落入 proxy / access log)。

    D6：msg 只由「整數 HTTP 狀態碼 + 固定錯誤類別」組成——
    ⛔ 不含回應本文、例外原文、URL、標頭。請求語意（含 verify=False）一字未動。
    """
    import requests
    _hdr = {'User-Agent': 'Mozilla/5.0'}
    if headers:
        _hdr.update(headers)
    try:
        r = requests.get(url, params=params, proxies=proxies,
                         timeout=timeout, verify=False,
                         headers=_hdr)
        code = r.status_code
        if isinstance(code, bool) or not isinstance(code, int):
            return False, ERR_OTHER
        cat = _classify_status(code)
        if cat is None:
            return True, f'HTTP {code}'
        return False, f'HTTP {code}（{cat}）'
    except Exception as e:
        return False, _classify_exception(e)


def _get_proxy_config_quiet():
    """取 proxy 設定；⛔ 吞掉 `get_proxy_config` 內部可能印到 stderr 的例外原文。

    `proxy_helper.get_proxy_config` 在 st.secrets 讀取失敗時會把例外原文印到 stderr
    （不在本頁修補範圍）；本頁呼叫它時把 stderr 暫時導向丟棄，避免診斷頁觸發該輸出。
    回傳值與呼叫語意不變。
    """
    from src.data.proxy import get_proxy_config
    with contextlib.redirect_stderr(io.StringIO()):
        return get_proxy_config()


def render_api_diagnostic():
    """主入口：顯示完整 API 診斷面板（D6：只顯示狀態，不顯示任何值）。"""
    st.markdown('### 🔑 API Key 與連線根因診斷')
    st.caption('排查「Key 都設了但全站抓不到資料」的標準工具：解析來源 → 設定狀態 → 走 proxy 與直連雙跑。')

    # ── §1 環境基本資訊 ─────────────────────────────────────
    try:
        import streamlit as _st_v
        st_ver = getattr(_st_v, '__version__', 'unknown')
    except Exception:
        st_ver = 'unknown'

    sec_obj = getattr(st, 'secrets', None)
    sec_parse_failed = False
    try:
        if sec_obj is not None:
            list(sec_obj.keys())  # 只為測「能不能解析」；⛔ 結果（key 名稱／數量）不上畫面
    except Exception:
        sec_parse_failed = True   # ⛔ 不保留例外原文

    c1, c2 = st.columns(2)
    c1.metric('Streamlit 版本', st_ver)
    c2.metric('st.secrets 可讀', '❌' if sec_parse_failed else '✅')

    if sec_parse_failed:
        st.error('⚠️ st.secrets 解析失敗（或無 secrets 檔）\n\n'
                 '→ 通常是 TOML 格式錯（缺引號／用了 export／特殊字元未跳脫）。\n'
                 '→ Streamlit Cloud 後台 App settings → Secrets 重貼一次，記得每個值都加雙引號。')

    st.markdown('---')

    # ── §2 逐把 Key 解析 ───────────────────────────────────
    st.markdown('#### 📋 各 API Key 載入狀態')
    rows = [_resolve_key(k) for k in APPROVED_KEY_NAMES]
    st.table([
        {'Key': r['name'], '狀態': r['state'], '使用來源': r['source']}
        for r in rows
    ])
    st.caption('「使用來源」= 程式實際取用的位置。如果是 `none` 表示 st.secrets 與 os.environ 都沒有，'
               'fallback 會拿到空字串，下游 API 必然 401/403/missing token。'
               '本頁只顯示狀態，不顯示任何金鑰內容。')

    # ── §3 PROXY 配置診斷（最容易害死全站的兇手）─────────
    st.markdown('---')
    st.markdown('#### 🚧 Proxy 配置診斷（最常見的「全部抓不到」根因）')
    proxy_cfg = _get_proxy_config_quiet()
    if proxy_cfg:
        st.warning(
            '⚠️ Proxy 已設定\n\n'
            '**警告**：Streamlit Cloud（美/歐機房）走家用 NAS proxy 經常不通——\n'
            '- 你家寬頻沒 port forward / IP 變動 / NAS 防火牆封鎖外部連入\n'
            '- `proxy_helper.fetch_url()` 只有在 `ProxyError` 或連續 403×2 才降級直連，'
            '**Timeout 不會降級**，外連就全 timeout 卡死。\n\n'
            '→ **快速驗證**：暫時到 Streamlit Cloud Secrets 把 `PROXY_URL` 整行刪掉重啟，'
            '若所有 Key 立刻活過來，就是 proxy 兇手。')
    else:
        st.success('✅ Proxy 未設定，所有外連走直連（這是 Streamlit Cloud 推薦設定）')

    # ── §4 連線雙跑實測 ─────────────────────────────────────
    st.markdown('---')
    st.markdown('#### 🔬 端對端連線實測（走 proxy vs 直連 雙跑）')

    if st.button('🚀 開始診斷外連狀態', key='api_diag_run', use_container_width=True, type='primary'):
        keys = {r['name']: r['val'] for r in rows}
        # v19.170:憑證只走 header,不進 query string(避免落入 proxy / access log)
        # tests 改為 4-tuple (label, url, params, headers);FinMind token 由
        # Authorization: Bearer 帶,query string 不再出現 token。
        _fm_tok = keys.get('FINMIND_TOKEN', '')
        _gm_key = keys.get('GEMINI_API_KEY', '')
        tests = [
            ('FinMind (需 token)',
             FINMIND_API_URL,
             {'dataset': 'TaiwanStockInfo', 'stock_id': '2330'},
             {'Authorization': f'Bearer {_fm_tok}'} if _fm_tok else None),
            # v19.170:憑證只走 header,不進 query string —— Gemini 官方支援
            # `x-goog-api-key` header,改走 header 後 URL 不再帶 key。
            ('Gemini API (需 key)',
             'https://generativelanguage.googleapis.com/v1beta/models',
             None,
             {'x-goog-api-key': _gm_key} if _gm_key else None),
            # ⚠️ FRED 例外(刻意不改):St. Louis Fed 的 FRED API **只接受**
            # `api_key` query 參數,沒有任何 header 認證方式(官方文件與實測皆然),
            # 改 header 會直接 400。這是 API 端的限制,非本專案疏漏。
            ('FRED API (需 key)',
             'https://api.stlouisfed.org/fred/series',
             {'series_id': 'GDP', 'api_key': keys.get('FRED_API_KEY', ''),
              'file_type': 'json'}, None),
            ('Yahoo Finance (免 key)',
             'https://query1.finance.yahoo.com/v8/finance/chart/2330.TW',
             {'range': '1d', 'interval': '1d'}, None),
            ('TWSE OpenAPI (免 key)',
             'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL',
             None, None),
        ]
        for label, url, params, hdrs in tests:
            with st.spinner(f'測試 {label}…'):
                t0 = time.time()
                ok_p, msg_p = (False, '(skip)')  # 固定字面，非外部輸入
                if proxy_cfg:
                    ok_p, msg_p = _probe(label, url, params,
                                         proxies=proxy_cfg, headers=hdrs)
                t_p = time.time() - t0

                t0 = time.time()
                ok_d, msg_d = _probe(label, url, params, proxies=None, headers=hdrs)
                t_d = time.time() - t0

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f'**{label} — 走 Proxy** ({t_p:.1f}s)')
                if not proxy_cfg:
                    st.info('未設定 proxy，略過')
                elif ok_p:
                    st.success(msg_p)
                else:
                    st.error(msg_p)
            with col2:
                st.markdown(f'**{label} — 直連** ({t_d:.1f}s)')
                if ok_d:
                    st.success(msg_d)
                else:
                    st.error(msg_d)

        st.markdown('---')
        st.markdown('#### 📌 結果判讀指南')
        st.markdown(
            '- **直連全綠 + 走 proxy 全紅** → 100% 是 proxy 兇手，到 Secrets 刪掉 `PROXY_URL` 即可\n'
            '- **直連也紅，但回應有 401/403** → Key 真的無效或過期，重新申請\n'
            '- **直連也紅，回應是 Timeout/ConnectionError** → Streamlit Cloud 對該域名被封 / DNS 問題\n'
            '- **Yahoo / TWSE 直連紅** → Streamlit Cloud 機房 IP 被該服務封鎖（常見），考慮改用其他資料源\n'
        )
