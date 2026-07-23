import streamlit as st
import datetime
import os
import re
import requests
import sys

# ── Streamlit Cloud 防護（PR #82/#86 升級版）────────────────
# tab_*.py 用 `from app import X`，Python 走 sys.modules['app'] 找模組。
# Cloud 上 sys.modules['__main__'] 是 Streamlit CLI binary 不是 script，
# 所以 PR #82 的 `setdefault('app', sys.modules[__name__])` 指錯模組。
# PR #86 用 ModuleType proxy + closure，但 closure 經 method.__globals__
# 解析 `_app_globals` 名稱對 Streamlit rerun 行為有依賴。
# 改為把 globals dict 塞 proxy.__dict__，每次都 refresh，徹底解耦。
import types as _types  # noqa: E402
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW

class _AppProxy(_types.ModuleType):
    """Proxy：`from app import X` → 從 proxy 自己 dict 拿 live globals。"""
    def __getattr__(self, name):
        g = self.__dict__.get('__app_globals__')
        if g is None:
            raise AttributeError(f"module 'app' proxy uninitialized; missing {name!r}")
        try:
            return g[name]
        except KeyError:
            raise AttributeError(
                f"module 'app' has no attribute {name!r} "
                f"(globals has {len(g)} keys)"
            ) from None

_existing = sys.modules.get('app')
if isinstance(_existing, _AppProxy):
    _existing.__dict__['__app_globals__'] = globals()
else:
    _proxy = _AppProxy('app')
    _proxy.__dict__['__app_globals__'] = globals()
    sys.modules['app'] = _proxy

# ── 台灣時間（UTC+8）─────────────────────────────────────
_TW_TZ = datetime.timezone(datetime.timedelta(hours=8))
def _tw_now(): return datetime.datetime.now(_TW_TZ)
def _tw_now_str(): return _tw_now().strftime('%Y-%m-%d %H:%M')

def _bps():
    try:
        import urllib3 as _ul3
        _ul3.disable_warnings(_ul3.exceptions.InsecureRequestWarning)
    except Exception:
        pass
    try:
        from src.data.stock import build_proxy_session as _b
        s = _b()
    except Exception:
        s = requests.Session()
    s.verify = False
    return s

print('[INFO] main.py v3.0 戰情室 載入完成')

# ── 新增模組（根據說明書 v1.0）──────────────────────────────
# ── v3.0 新增模組（§5-§11）──────────────────────────────────
from src.ui.etf import (  # noqa: E402
    render_etf_single, render_etf_portfolio,
    render_etf_ai,
    render_sector_heatmap,
)
from src.ui.pages import render_data_health_raw  # noqa: E402
from src.ui.pages import render_api_diagnostic  # noqa: E402
from src.ui.tabs import render_grape_ladder  # noqa: E402
from src.config import TAIWAN_ADVISOR_PERSONA as _PERSONA  # noqa: E402

def _get_secret(_key: str) -> str:
    """st.secrets 優先,降級 os.environ。

    st.secrets 在「無 secrets.toml」(本機 / CI fast lane)會 raise
    StreamlitSecretNotFoundError;在「streamlit 被 test stub 取代」時甚至缺
    `secrets` 屬性(AttributeError)。以 try/except 降級確保 app import 不炸
    (對齊 config.py EX-L0-1 + Fund data_registry 的 st.secrets guard)。
    """
    try:
        _v = st.secrets.get(_key, '')
    except Exception:
        _v = ''
    return _v or os.environ.get(_key, '')


api_key       = _get_secret('GEMINI_API_KEY')   # [Fixed] st.secrets 優先 + 缺失降級
FINMIND_TOKEN = _get_secret('FINMIND_TOKEN')    # [Fixed] st.secrets 優先 + 缺失降級

# [Fixed] 同步到 os.environ，讓子模組頂層讀取能拿到正確值
if FINMIND_TOKEN:
    os.environ['FINMIND_TOKEN'] = FINMIND_TOKEN
if api_key:
    os.environ['GEMINI_API_KEY'] = api_key

def _get_fm_token():
    """每次動態讀取最新 Token：st.secrets > os.environ"""
    _tok = (getattr(st, 'secrets', {}).get('FINMIND_TOKEN')
            or os.environ.get('FINMIND_TOKEN', ''))
    return _tok

st.set_page_config(page_title='台股AI戰情室 v3.0', layout='wide',
                   page_icon='📊', initial_sidebar_state='collapsed')

# ── OAuth callback：URL 帶 ?code= 時自動換 token（必須早於其他 query_params 操作）
# v18.400 D4:oauth_state 已從 src/ui/pages 歸位 src/data/portfolio
try:
    from src.data.portfolio.oauth_state import handle_oauth_callback as _oauth_cb
    _oauth_cb()
except Exception as _oauth_err:
    print(f'[oauth callback] {_oauth_err}')

# ── App 初始化閘門（每個 Session 僅執行一次，防重複迴圈）────────────
if '_app_boot_done' not in st.session_state:
    st.session_state['_app_boot_done'] = True
    # [Phase 3] 從 URL query_params 恢復關鍵狀態（手機斷線重連可保留設定）
    try:
        _qp = st.query_params
        if _qp.get('chips') == '1':
            st.session_state['chips_loaded'] = True
        _qp_sid = _qp.get('sid')
        if _qp_sid and isinstance(_qp_sid, str) and _qp_sid.isdigit():
            st.session_state['_qp_sid'] = _qp_sid  # 個股 Tab 啟動時讀取
    except Exception as _qpe:
        print(f'[query_params restore] {_qpe}')

# [Phase 3] 雙向同步：session_state → query_params（讓重連後 URL 仍帶狀態）
try:
    _qp_w = st.query_params
    if st.session_state.get('chips_loaded') and _qp_w.get('chips') != '1':
        _qp_w['chips'] = '1'
    elif not st.session_state.get('chips_loaded') and _qp_w.get('chips') == '1':
        del _qp_w['chips']
except Exception:
    pass

st.markdown(f"""<style>
.main{{background:#0e1117;}}
[data-testid="stSidebar"]{{background:#161b22;}}
.stTabs [data-baseweb="tab-list"]{{gap:2px;}}
.stTabs [data-baseweb="tab"]{{background:#161b22;color:#8b949e;border-radius:6px 6px 0 0;padding:8px 16px;font-size:13px;}}
.stTabs [aria-selected="true"]{{background:linear-gradient(135deg,#1f6feb,#0d4faa);color:#fff;font-weight:700;}}
.teacher-card{{background:#0d1117;border-left:3px solid #ffd700;border-radius:0 8px 8px 0;padding:10px 14px;margin:6px 0;}}
.health-A{{background:linear-gradient(90deg,#0d2818,#0d1117);border:2px solid {TRAFFIC_GREEN};border-radius:12px;padding:16px;text-align:center;}}
.health-B{{background:linear-gradient(90deg,#2a1f00,#0d1117);border:2px solid {TRAFFIC_YELLOW};border-radius:12px;padding:16px;text-align:center;}}
.health-C{{background:linear-gradient(90deg,#2a0d0d,#0d1117);border:2px solid {TRAFFIC_RED};border-radius:12px;padding:16px;text-align:center;}}
</style>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════
# v18.302 §8.3 app.py 拆檔:parse_stocks 已提至 shared/parse_helpers.py(L0)。
# 此處保 re-export 維持向後相容(tab_stock_grp.py:52 等 caller 0 改)。
from shared.parse_helpers import parse_stocks  # noqa: F401

# ── Gemini 金鑰池（做法 B：多帳號 key 自動換手，分散額度 / 速率限制）──────
# 讀 GEMINI_API_KEY + GEMINI_API_KEY_2 .. _6（st.secrets 優先，os.environ fallback）。
# gemini_call 以 round-robin 起手 key（不同呼叫/不同 tab 從不同把 key 開始 → 分散負載），
# 任一把遇到 429（速率/額度滿）或 403（無效）時自動換下一把，全部用盡才報錯。
_GEMINI_KEY_NAMES = ['GEMINI_API_KEY'] + [f'GEMINI_API_KEY_{_i}' for _i in range(2, 7)]
_gemini_rr = [0]  # round-robin 起手索引（每次呼叫遞增）
# v18.435 WONTFIX-翻案 Bug #3:多 Streamlit session 併發呼叫 gemini_call 時,
# _gemini_rr[0] 的讀+寫非 atomic(兩條指令),會讓 round-robin 跳號 →
# 同一把 hot key 連環打 → 提前 429。加 Lock 序列化 round-robin 增量。
import threading as _threading_rr
_gemini_rr_lock = _threading_rr.Lock()


def _gemini_keys() -> list:
    """收集所有可用 Gemini API key（去重保序）。st.secrets 優先，os.environ fallback。"""
    _keys = []
    for _n in _GEMINI_KEY_NAMES:
        try:
            _v = st.secrets.get(_n, '') or os.environ.get(_n, '')
        except Exception:
            _v = os.environ.get(_n, '')
        _v = str(_v or '').strip()
        if _v and _v not in _keys:
            _keys.append(_v)
    if api_key and api_key not in _keys:
        _keys.append(api_key)
    return _keys


def gemini_call(prompt, max_tokens=2048):
    _keys = _gemini_keys()
    if not _keys:
        return '⚠️ 請設定 GEMINI_API_KEY（可另加 GEMINI_API_KEY_2 ~ _6 分散額度）'
    # round-robin 起手：不同呼叫從不同把 key 開始，自然把負載分散到各帳號
    # v18.435 WONTFIX-翻案 Bug #3:Lock 序列化讀+寫,避免併發 session 跳號
    with _gemini_rr_lock:
        _start = _gemini_rr[0] % len(_keys)
        _gemini_rr[0] = (_gemini_rr[0] + 1) % 1_000_000
    _keys = _keys[_start:] + _keys[:_start]
    # 2026-03 有效模型：1.5系列全部退役，2.5為主力
    _models = ['gemini-2.5-flash-lite', 'gemini-2.5-flash',
               'gemini-2.0-flash', 'gemini-2.0-flash-lite']
    for _model in _models:
        # Gemini 2.5 預設開「思考模式」，思考 token 會跟輸出共用 maxOutputTokens 額度
        # → 常導致回覆只生成一半就被截斷。白話摘要不需深度推理，關閉思考（thinkingBudget=0）。
        _gen_cfg = {'temperature': 0.3, 'maxOutputTokens': max_tokens}
        if _model.startswith('gemini-2.5'):
            _gen_cfg['thinkingConfig'] = {'thinkingBudget': 0}
        for _ki, _key in enumerate(_keys):
            try:
                _r = requests.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/{_model}:generateContent',
                    params={'key': _key},
                    json={'systemInstruction': {'parts': [{'text': _PERSONA}]},
                          'contents': [{'parts': [{'text': prompt}]}],
                          'generationConfig': _gen_cfg},
                    timeout=120
                )
                if _r.status_code == 200:
                    _d = _r.json()
                    _cands = _d.get('candidates', [])
                    if _cands:
                        _parts = _cands[0].get('content', {}).get('parts', [])
                        if _parts and _parts[0].get('text'):
                            return _parts[0]['text']
                    # safety 攔截：換 key 無助益 → 直接換下一個 model
                    if _cands and _cands[0].get('finishReason', '') == 'SAFETY':
                        break
                    continue  # 空回覆 → 試下一把 key
                elif _r.status_code == 400:
                    _err_msg = (_r.json() if _r.text else {}).get('error', {}).get('message', _r.text[:100])
                    print(f'[Gemini/{_model}] 400 Bad Request: {_err_msg}')
                    break  # 設定/prompt 問題，換 key 無用 → 換下一個 model
                elif _r.status_code == 403:
                    print(f'[Gemini/{_model}] 403 第 {_ki+1} 把 key 無效/無權限 → 換下一把')
                    continue  # 換 key
                elif _r.status_code == 404:
                    break  # 此 model 不存在 → 換下一個 model
                elif _r.status_code == 429:
                    print(f'[Gemini/{_model}] 429 第 {_ki+1} 把 key 額度/速率滿 → 換下一把')
                    continue  # 換 key（做法 B 核心：分散到別把帳號）
                else:
                    print(f'[Gemini/{_model}] HTTP {_r.status_code}: {_r.text[:200]}')
                    continue  # 換 key
            except Exception as _ge:
                print(f'[Gemini/{_model}] key#{_ki+1} {type(_ge).__name__}: {_ge}')
                continue  # 換 key
    return ('⚠️ AI 服務暫時無法使用（所有 key 與模型都試過了）—— '
            '請確認各把金鑰額度，或稍後再試')

# ── 本地快取（SQLite + Pickle 雙軌）───────────────────────
# v18.404 B3-α:cache helper 50 LOC 抽至 shared/app_cache.py(thin shim 保 caller API)。
from shared.app_cache import _cache_key, _load_cache, _save_cache, _CACHE_DIR  # noqa: F401

# 6 fetchers + _get_loader + _expected_latest_trading_date 已抽至
# src/data/stock/app_stock_fetchers.py(v18.405 U5 B3-δ)
from src.data.stock.app_stock_fetchers import (  # noqa: E402,F401
    _expected_latest_trading_date,
    _get_loader,
    fetch_dividend_data,
    fetch_financials,
    fetch_price_data,
    fetch_quarterly,
    fetch_quarterly_extra,
    fetch_revenue,
)



# ════════════════════════════════════════════════════════════════
# 技術指標計算 — 已抽出至 tech_indicators.py（PR P2-B Phase 1）
# ════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════
# 健康度評分（0~100）— 已抽出至 scoring_helpers.py（PR P2-B Phase 3）
# ════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════
# 初學者友善說明系統 — 已抽出至 ui_widgets.py（PR P2-B Phase 2）
# ════════════════════════════════════════════════════════════════
from src.ui.render import (  # noqa: E402
    traffic_light, show_term_help,
)
# P2-B Phase 5 A/B/C/D: 4 個 TAB 全部已抽到獨立模組（app.py 9208→1394 行，−85%）

# 在先行指標 section 使用
_TERM_HELP_LI = show_term_help('PCR') + show_term_help('ADL') + show_term_help('M1B-M2')

# generate_ai_comment 已抽至 src/services/app_ai_service.py(v18.398 P5-B3-β R7)
# caller 改走 `from src.services.app_ai_service import generate_ai_comment`

# ── kpi / teacher_conclusion / signal_box 已抽至 ui_widgets.py ──

# render_health_score 已抽至 src/ui/render/app_render.py(v18.404 U5 B3-γ)
# caller 改走 `from src.ui.render.app_render import render_health_score`


primary_stock = '2330'

# ── Sidebar: 整合 AI 分析 ───────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="text-align:center;padding:8px 0;font-size:15px;font-weight:900;color:#e6edf3;">&#128202; 台股AI戰情室 v3.0</div>', unsafe_allow_html=True)
    st.markdown('---')
    # v18.461 FIX: 使用台灣時區（UTC+8），避免 Streamlit Cloud UTC 服務器在 00:00~08:00 TW 顯示昨天日期
    _TW_TZ_SB = datetime.timezone(datetime.timedelta(hours=8))
    _today_sb = datetime.datetime.now(_TW_TZ_SB).date()
    _wd_sb = {0:'一',1:'二',2:'三',3:'四',4:'五',5:'六',6:'日'}[_today_sb.weekday()]
    _trade_sb = '✅ 交易日' if _today_sb.weekday() < 5 else '❌ 非交易日'
    st.caption(f'{_today_sb.strftime("%Y/%m/%d")} 週{_wd_sb}  {_trade_sb}')
    st.markdown('---')
    st.markdown('### 🤖 AI 分析')
    st.caption('頁面底部有 AI 整合報告面板')
    ai_run = False  # AI button moved to bottom panel
    st.markdown('---')
    st.success('🟢 系統正常運作中')

    # ── Google 帳號（OAuth）— ETF 組合雲端存取用 ─────────────────
    st.markdown('---')
    st.markdown('### 🔐 Google 帳號')
    try:
        from src.data.portfolio.oauth_state import (
            get_oauth_cfg as _sb_get_cfg,
            get_login_state as _sb_login_state,
            _gsa_secret as _sb_gsa,
            _sheet_id_secret as _sb_sid,
        )
        from infra.oauth import build_authorize_url as _sb_buildurl
        # 每次 rerun 動態解析，避免 module-level cache 過期
        _sb_cfg = _sb_get_cfg()
        _sb_oc = _sb_cfg is not None
    except Exception:
        _sb_oc, _sb_cfg, _sb_gsa, _sb_sid, _sb_buildurl = False, None, None, '', None
    _sb_logged = bool(st.session_state.get('gsheet_tokens'))
    if _sb_oc:
        if _sb_logged:
            _sb_email = st.session_state.get('gsheet_email', '')
            st.success(f'🟢 已登入{("：" + _sb_email) if _sb_email else ""}')
            if st.button('🚪 登出', key='btn_oauth_logout_sb',
                          use_container_width=True):
                for _k in ('gsheet_tokens', 'gsheet_email', '_oauth_state'):
                    st.session_state.pop(_k, None)
                st.rerun()
            # ── Google Sheet ID（集中於帳號區；ETF 組合面板可從 Drive 挑選/新建）──
            _sb_sid_cur = str(st.session_state.get('portfolio_sheet_id', '') or '').strip()
            _sb_sid_raw = st.text_input(
                'Google Sheet ID 或完整 URL（系統會自動解析 ID）',
                value=_sb_sid_cur, key='sb_portfolio_sheet_id_input',
                placeholder='貼上 https://docs.google.com/spreadsheets/d/...',
                help='貼 URL/ID 設定投組資料庫；或到「ETF 組合」Tab 從 Drive 挑選 / 一鍵新建')
            _sb_m = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', _sb_sid_raw)
            _sb_sid_new = _sb_m.group(1) if _sb_m else _sb_sid_raw.strip()
            if _sb_sid_new and _sb_sid_new != _sb_sid_cur:
                st.session_state['portfolio_sheet_id'] = _sb_sid_new
            if _sb_sid_new:
                st.caption(f'✅ Sheet ID：`{_sb_sid_new}`')
            else:
                st.caption('💡 未設定 — 貼上 URL/ID 或到「ETF 組合」Tab 挑選')
        elif _sb_buildurl and _sb_cfg:
            _sb_url = _sb_buildurl(_sb_cfg['client_id'], _sb_cfg['redirect_uri'],
                                   state=_sb_login_state())
            st.link_button('🔐 用 Google 登入', _sb_url, use_container_width=True)
            st.caption('登入後 ETF 組合 Tab 可雲端存取')
    elif _sb_gsa and _sb_sid:
        st.caption('ℹ️ 使用 Service Account（舊版部署）')
    else:
        st.caption('⚙️ OAuth 尚未設定 — 至「ETF 組合」Tab 展開「💾 雲端儲存」設定')

    st.markdown('---')
    st.markdown('### 🔌 連線狀態')
    # v19.81:原裸呼 st.secrets.get ×5 — 無 secrets.toml 環境(CI slow lane /
    # 本機裸跑)直接 StreamlitSecretNotFoundError 炸 module import(slow lane
    # test_app_reexport 抓到,main 上已紅)。收斂走既有 SSOT helper _get_secret
    # (st.secrets 優先 → env 降級 → raise 降級),語意同 line 88-89。
    _fm_tok  = str(_get_secret('FINMIND_TOKEN'))
    # Gemini 改看整池 key（GEMINI_API_KEY + _2~_6），任一把有設就算通
    _gm_keys  = _gemini_keys()
    _gm_slots = [_n for _n in _GEMINI_KEY_NAMES
                 if str(_get_secret(_n) or '').strip()]
    _px_host = str(_get_secret('PROXY_HOST'))
    # PROXY_URL 與 PROXY_HOST 二擇一即可亮 ✅
    if not _px_host:
        _px_host = str(_get_secret('PROXY_URL'))
    _sb_c1, _sb_c2, _sb_c3 = st.columns(3)
    with _sb_c1:
        if _fm_tok:
            st.success('FinMind ✅')
        else:
            st.error('FinMind ❌')
    with _sb_c2:
        if _gm_keys:
            st.success(f'Gemini ✅ ×{len(_gm_keys)}')
        else:
            st.error('Gemini ❌')
    with _sb_c3:
        if _px_host:
            st.success('Proxy ✅')
        else:
            st.warning('Proxy —')
    # Gemini 金鑰池偵測明細（協助確認多帳號 key 有沒有被讀到）
    if _gm_slots:
        st.caption('🔑 偵測到 Gemini 金鑰：' + '、'.join(_gm_slots))
    else:
        st.caption('🔑 未偵測到任何 Gemini 金鑰（請確認 Secrets 內 '
                   'GEMINI_API_KEY 或 GEMINI_API_KEY_2~_6 的名稱與值）')
    if _px_host:
        _px_port = str(_get_secret('PROXY_PORT'))  # v19.81:同上,收斂 _get_secret
        st.caption(f'🔒 {_px_host}:{_px_port}' if _px_port else '🔒 PROXY_URL 已設定')
        st.caption('💡 詳細診斷請看「🔎 資料診斷」Tab 的 API Key 診斷面板')
    if st.button('🔍 測試連線', key='sb_conn_test', use_container_width=True):
        import requests as _rq_sb
        import urllib3 as _ul3
        _ul3.disable_warnings(_ul3.exceptions.InsecureRequestWarning)
        _test_targets = [
            ('FinMind', 'https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo&stock_id=2330&date=2024-01-01', False),
            ('TWSE',    'https://openapi.twse.com.tw/v1/opendata/t187ap03_L', True),
            ('Yahoo',   'https://query1.finance.yahoo.com/v8/finance/chart/2330.TW?range=1d&interval=1d', False),
        ]
        _conn_res = []
        for _tn, _tu, _skip_ssl in _test_targets:
            try:
                _tr = _rq_sb.get(_tu, timeout=6, verify=not _skip_ssl,
                                  headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
                _conn_res.append((_tn, _tr.status_code, _tr.status_code < 400))
            except Exception as _te:
                _conn_res.append((_tn, type(_te).__name__, False))
        st.session_state['_sb_conn_results'] = _conn_res
    for _rn, _rc, _rok in st.session_state.get('_sb_conn_results', []):
        if _rok:
            st.success(f'✅ {_rn} 可達！HTTP {_rc}')
        else:
            st.error(f'❌ {_rn} 失敗：{_rc}')

    st.markdown('---')
    st.caption('⚠️ 僅供學術研究，非投資建議，盈虧自負')

# v3.0 RENDER FUNCTIONS (§9.3)
# ════════════════════════════════════════════════════════════════

# ── 旌旗指數計算（站上 MA20/MA60/MA120/MA240 的家數比例）──────
# ════════════════════════════════════════════════════════════════
# TABS: 3 主頁籤
# ════════════════════════════════════════════════════════════════
# ── Sidebar ────────────────────
with st.sidebar:
    if st.button('🔄 強制刷新數據', key='_sb_force_refresh', use_container_width=True,
                 help='清除所有快取並重新抓取最新資料'):
        st.cache_data.clear()
        st.rerun()
    st.markdown('---')

    # ── v18.203 F2：全局資料健康總覽（聚合個股六源 + 總經羅盤 → 一眼看哪舊）──
    try:
        from src.ui.pages import render_sidebar_data_health
        render_sidebar_data_health(st.session_state)
    except Exception as _e_sbh:
        print(f'[sidebar_health] {type(_e_sbh).__name__}: {_e_sbh}')
    st.markdown('---')

# 主標題
st.markdown(
    # v19.82(第五份 review):badge 原掛「4.0 Pro」,與 page_title/側欄/頁尾 v3.0
    # 同畫面矛盾 — 統一 v3.0(多數決;若要全面升版請 user 點名再一次換齊)
    '<div style="display:flex;align-items:center;gap:10px;padding:4px 0 8px;">'    '<span style="font-size:22px;font-weight:900;color:#e6edf3;">&#128202; 台股 AI 戰情室</span>'    '<span style="font-size:10px;color:#484f58;background:#161b22;border-radius:10px;padding:2px 8px;">v3.0</span>'    '</div>',
    unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# 🧭 總經指南針 — render_macro_compass 已抽至 src/ui/render/app_render.py
# (v18.404 U5 B3-γ);_render_compass_card 同步搬走(internal helper)
# ══════════════════════════════════════════════════════
from src.ui.render.app_render import render_macro_compass  # noqa: E402
render_macro_compass()

# v18.182 ARCHIVED: 🧪 回測找參數 / v18.187 ARCHIVED: 📈 月營收進退 / v18.189 ARCHIVED: 📊 MJ 體檢變化
# 各暫封存模組保留磁碟，啟用方式見各 ARCHIVED 原始注解。
# v18.463: UI 重構 — 10 平鋪 Tab → 4 大群組 + Sub-tabs（sub-tab 變數名稱維持不變，測試仍通過）
tab_market, tab_stocks, tab_etf_main, tab_tools, tab_ai = st.tabs([
    '🌍 市場環境', '🔬 選股', '🏦 ETF', '🔧 工具箱', '🧬 AI 問答',
])

# ══════════════════════════════════════════════════════════════
# 全域多空紅綠燈（Tab 外，永遠可見）
# ══════════════════════════════════════════════════════════════

# ── 全域多空紅綠燈（頁面最頂端）─────────────────────────────
_mkt_top  = st.session_state.get('mkt_info', {})
_jq_top   = st.session_state.get('jingqi_info', {})
_ts_top   = st.session_state.get('cl_ts', '')
if (_mkt_top or _jq_top) and not st.session_state.get('_is_refreshing', False):
    _reg   = _mkt_top.get('regime', 'neutral')
    _jqpct = _jq_top.get('avg', 50) if _jq_top else None
    # 綜合信號
    _gl_color, _gl_label = traffic_light(
        None,
        _reg == 'bull' and (_jqpct is None or _jqpct >= 40),
        _reg == 'bear' or (_jqpct is not None and _jqpct < 20),
        '多頭市場（可積極操作）', '空頭市場（先觀望保守）', '🟡 震盪整理（謹慎操作）'
    )
    _gl_pos = _mkt_top.get('exposure_pct', '80%' if _reg=='bull' else ('20%' if _reg=='bear' else '50%'))

    # v19.88 A~E 批次2 收尾:時效閘 — 紅綠燈基於過期資料時,保留燈色(資料可顯示)但
    # 撤下「建議持股 X%」actionable 建議 + 旌旗均值,改明確過期警示。§1/第八份 §3.1:
    # 過期資料可顯示但須標記,且不得以「可積極操作」語氣餵當下決策(cl_ts = 上次一鍵更新)。
    from shared.staleness import gate_for_realtime, staleness_days
    _rt_ok, _rt_msg = gate_for_realtime(
        staleness_days(_ts_top) if _ts_top else None, max_days=1)
    if _rt_ok:
        _mid_html = (
            f'<span style="font-size:12px;color:#c9d1d9;">建議持股 <b>{_gl_pos}</b></span>'
            + (f'<span style="font-size:12px;color:#8b949e;">旌旗均值 {_jqpct:.0f}%</span>'
               if _jqpct is not None else ''))
    else:
        _mid_html = ('<span style="font-size:12px;font-weight:700;color:#d29922;">'
                     '⚠️ 資料已過期，燈號僅供參考 — 請先按「🚀 一鍵更新全部數據」再操作</span>')

    st.markdown(
        f'<div style="background:#0d1117;border:1px solid {_gl_color};border-radius:8px;'
        f'padding:8px 14px;margin-bottom:8px;display:flex;align-items:center;gap:16px;">'
        f'<span style="font-size:16px;font-weight:900;color:{_gl_color};">{_gl_label}</span>'
        f'{_mid_html}'
        f'<span style="font-size:11px;color:#484f58;margin-left:auto;">更新：{_ts_top}</span>'
        f'</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# AI 總經戰情 — 新聞抓取已抽至 src/data/news/(v18.398 P5-B3-β R8)
# caller 改走 `from src.data.news import fetch_macro_news, fetch_stock_news`
# ══════════════════════════════════════════════════════════════


def _build_llm_context(macro_info: dict) -> str:
    """將 session_state 中的量化總經數據格式化為純文字供 LLM 使用。

    v19.87 A~E 批次2:月度指標(出口/PMI/CPI/NDC)距預期最新交易日 >40 天者,
    在該行前綴 `[STALE:Nd]`(shared/staleness.stale_tag SSOT),防 AI 把過期資料
    當當期講(第八份 review §3.1;對齊 Fund 端既有慣例)。
    """
    from shared.staleness import stale_tag, staleness_days
    _vix = macro_info.get('vix') or {}
    _exp = macro_info.get('tw_export') or {}
    _pmi = macro_info.get('ism_pmi') or {}
    _cpi = macro_info.get('us_core_cpi') or {}
    _ndc = macro_info.get('ndc_signal') or {}
    _mi  = st.session_state.get('m1b_m2_info') or {}
    _bi  = st.session_state.get('bias_info') or {}

    def _tag(_d: dict) -> str:
        # 月度指標 stale 閾值 40 天;date 缺失 → staleness_days 回 None → 無標籤
        return stale_tag(staleness_days(_d.get('date')), threshold=40)

    _lines = []
    if _vix.get('current'):
        _lines.append(f'• VIX 恐慌指數：{_vix["current"]} (MA20={_vix.get("ma20","N/A")})')
    if _exp.get('yoy') is not None:
        # v19.85 正名:tw_export = 海關出口年增率(非經濟部外銷訂單)
        _lines.append(f'• {_tag(_exp)}台灣出口 YoY：{_exp["yoy"]:+.1f}%  ({_exp.get("date","")})')
    if _pmi.get('value') is not None:
        _lines.append(f'• {_tag(_pmi)}🇹🇼 台灣 PMI：{_pmi["value"]}  ({_pmi.get("date","")}，>50 擴張)')
    if _cpi.get('yoy') is not None:
        _lines.append(f'• {_tag(_cpi)}美國核心 CPI YoY：{_cpi["yoy"]:+.1f}%  ({_cpi.get("date","")})')
    if _ndc.get('score') is not None:
        _lines.append(f'• {_tag(_ndc)}NDC 景氣燈號分數：{_ndc["score"]:.0f}/45')
    if _mi.get('m1b_yoy') is not None and _mi.get('m2_yoy') is not None:
        _gap = round(float(_mi['m1b_yoy']) - float(_mi['m2_yoy']), 2)
        _lines.append(f'• 台灣 M1B={_mi["m1b_yoy"]:.1f}%  M2={_mi["m2_yoy"]:.1f}%  Gap={_gap:+.2f}%')
    if _bi.get('bias_240') is not None:
        _lines.append(f'• 台股大盤年線乖離率 BIAS240：{_bi["bias_240"]:+.1f}%')
    return '\n'.join(_lines) if _lines else '（量化數據載入中，請先按「🚀 一鍵更新全部數據」）'


# ══════════════════════════════════════════════════════════════
# render 隔離器 — v18.439/v18.440 修復：單 tab 出錯不拖垮全頁
# ══════════════════════════════════════════════════════════════
def _render_tab_isolated(_render, _label):
    """單一 tab render 隔離:例外不拖垮全頁,改在該 tab st.error + stderr full traceback。"""
    try:
        _render()
    except Exception as _e_tab:
        import sys as _sys_t, traceback as _tb_t
        st.error(f'⚠️ 「{_label}」分頁渲染異常,已隔離(其他分頁不受影響):'
                 f'{type(_e_tab).__name__}: {str(_e_tab)[:300]}')
        print(f'[tab:{_label}] render error:\n{_tb_t.format_exc()}', file=_sys_t.stderr)


# ══════════════════════════════════════════════════════════════
# GROUP 1: 市場環境（總經 + 產業熱力圖）
# ══════════════════════════════════════════════════════════════
with tab_market:
    tab_macro, tab_heatmap = st.tabs(['🌍 總經', '🗺️ 產業熱力圖'])

    with tab_macro:
        from src.ui.tabs import render_tab_macro
        _render_tab_isolated(render_tab_macro, '總經')

    with tab_heatmap:
        render_sector_heatmap(gemini_fn=gemini_call)

# ══════════════════════════════════════════════════════════════
# GROUP 2: 選股（個股 + 個股組合 + 選股網）
# ══════════════════════════════════════════════════════════════
with tab_stocks:
    tab_stock, tab_stock_grp, tab_screener, tab_mj = st.tabs(['🔬 個股', '🏆 個股組合', '🔭 選股網', '🩺 體檢轉機'])

    with tab_stock:
        from src.ui.tabs import render_tab_stock
        _render_tab_isolated(render_tab_stock, '個股')

    with tab_stock_grp:
        from src.ui.tabs import render_stock_grp
        _render_tab_isolated(render_stock_grp, '個股組合')

    with tab_screener:
        # v19.111 選股網極簡版：① 基本面優選（自動）→ ② 勾條件（4 因子可複選）→ ③ 一鍵出名單。
        # 只留最上方「開始選股」一顆按鈕；移除下方進階掃描 expander + 籌碼×6 picker（user 要求極簡）。
        st.markdown('### 🔭 選股網 — 勾條件 → 一鍵選股')
        from src.ui.tabs.tab_stock_picker import render_prescreen_panel
        from src.ui.tabs.yield_screener import fetch_twse_yield_pe
        from src.services.fundamental_screener_service import (
            SCREEN_ANGLE_LABELS, get_fundamental_survivors, get_ranked_picks,
        )

        # ── ① 基本面優選（四項全過，自動）────────────────────────
        st.markdown('#### ① 基本面優選（四項全過，自動）')
        render_prescreen_panel()

        # ── ② 勾選條件（可複選）────────────────────────────────
        st.markdown('#### ② 勾選條件（可複選）')
        _factor_labels = st.multiselect(
            '要用哪些條件？（估值/EPS 立即算；缺貨動能 / 抗跌RS 按「開始選股」時**自動掃描**，不用另外去按）',
            list(SCREEN_ANGLE_LABELS), default=[list(SCREEN_ANGLE_LABELS)[0]],
            key='screener_factors')
        _factors = [SCREEN_ANGLE_LABELS[_l] for _l in _factor_labels]

        # ── ③ 一鍵開始選股（缺貨/RS 自動掃 → 綜合評分）─────────────
        if st.button('🎯 開始選股', key='screener_go', type='primary', use_container_width=True):
            with st.spinner('選股中：需要時自動掃缺貨/抗跌RS + 綜合評分…（首次較久）'):
                if 'shortage' in _factors and not st.session_state.get('_shortage_rows'):
                    try:
                        from src.services.shortage_screener_service import run_shortage_scan
                        _sr, _sm = run_shortage_scan()
                        st.session_state['_shortage_rows'] = _sr
                        st.session_state['_shortage_meta'] = _sm
                    except Exception as _es:  # noqa: BLE001 — 掃描失敗不炸選股
                        print(f'[screener] 缺貨自動掃失敗: {type(_es).__name__}: {_es}')
                if 'rs_leader' in _factors and not st.session_state.get('_rs_rows_all'):
                    try:
                        # v19.90:綜合評分需【全存活池】RS 分位 → beat_only=False + top_n 給大值
                        # (不是只回 top-50 贏大盤股,否則 274 檔 RS 無資料 → 綜合分失真)。
                        from shared.rs_screen_thresholds import RS_SCAN_MAX
                        from src.services.rs_leader_service import run_rs_leader_scan
                        _rr, _rm = run_rs_leader_scan(beat_only=False, top_n=RS_SCAN_MAX)
                        st.session_state['_rs_rows_all'] = _rr
                        st.session_state['_rs_meta_all'] = _rm
                    except Exception as _er:  # noqa: BLE001
                        print(f'[screener] 抗跌RS自動掃失敗: {type(_er).__name__}: {_er}')
                if 'trend' in _factors and not st.session_state.get('_trend_map'):
                    try:
                        # A-2 v19.140:跨季轉強因子 = 全市場基本面趨勢(從快照算,非掃描,秒級)。
                        from src.services.fundamental_screener_service import build_trend_map
                        st.session_state['_trend_map'] = build_trend_map()
                    except Exception as _et:  # noqa: BLE001
                        print(f'[screener] 跨季趨勢計算失敗: {type(_et).__name__}: {_et}')
            st.session_state['_screener_ran'] = True

        # ── 結果（點過「開始選股」才顯示）──────────────────────────
        if not st.session_state.get('_screener_ran'):
            st.info('👆 勾好條件後，點「🎯 開始選股」。缺貨/抗跌RS 會自動幫你掃，不用另外操作。')
        else:
            try:
                _surv_df, _ = get_fundamental_survivors()
            except Exception as _e_surv:  # noqa: BLE001 — 快照缺不炸選股網
                _surv_df = None
                print(f'[screener] 存活池不可用: {type(_e_surv).__name__}: {_e_surv}')
            _twse_scrn = fetch_twse_yield_pe()
            _pe_map, _name_map = {}, {}
            if _twse_scrn is not None and not _twse_scrn.empty and '代碼' in _twse_scrn.columns:
                _codes_s = _twse_scrn['代碼'].astype(str)
                if '本益比' in _twse_scrn.columns:
                    _pe_map = dict(zip(_codes_s, _twse_scrn['本益比']))
                if '名稱' in _twse_scrn.columns:
                    _name_map = dict(zip(_codes_s, _twse_scrn['名稱'].astype(str)))
            # v19.147:改走 L3 get_ranked_picks（畫面/cron 同源，保證自動凍結清單=畫面清單）。
            # auto_fetch=False = 只用 session 已快取的掃描結果（掃描仍由上方「開始選股」按鈕觸發），行為不變。
            _cands, _cnote = get_ranked_picks(
                _factors, top_n=300, survivors_df=_surv_df,
                pe_map=_pe_map, name_map=_name_map,
                shortage_rows=st.session_state.get('_shortage_rows'),
                rs_rows=st.session_state.get('_rs_rows_all'),  # v19.90 全存活池 RS（非 top-50）
                trend_map=st.session_state.get('_trend_map'),  # A-2 v19.140 跨季轉強
                auto_fetch=False)
            if _cnote:
                st.info(_cnote)
            st.markdown('#### ③ 選股結果（綜合評分排序）')
            _surv_n = len(_surv_df) if _surv_df is not None else 0
            if _cands.empty:
                st.info('目前沒有符合的標的（請至少勾一個條件；缺貨/抗跌RS 需能連上資料源）。')
            else:
                st.caption(f'從基本面優選 {_surv_n} 檔 → 綜合評分取前 {min(len(_cands), 50)} 名。')
                st.dataframe(_cands.head(50), hide_index=True, use_container_width=True)
                _csv = _cands.head(50).to_csv(index=False).encode('utf-8-sig')
                st.download_button('💾 下載選股結果 CSV', data=_csv,
                                   file_name='screener_result.csv', mime='text/csv',
                                   key='screener_csv')
                # ── 🧊 前進式驗證：凍結本次選股（FT-2 v19.142）→ 存 Google Sheet，日後對帳 vs 0050 ──
                st.markdown('##### 🧊 前進式驗證：凍結本次選股')
                st.caption('把前 20 名凍結存進你的 Google Sheet（含當下進場價 + 勾選因子），'
                           '日後對帳看這套選股實際贏不贏 0050 —— 零 lookahead、零存活者偏誤。')
                from src.services.forward_test_service import (
                    freeze_current_picks, is_freeze_available)
                if not is_freeze_available():
                    st.info('⚪ 需先在「⚖️ ETF 組合 → 💾 雲端儲存」設定 Google Sheet，才能凍結存檔。')
                elif st.button('🧊 凍結前 20 名（存 Google Sheet）', key='ft_freeze_go'):
                    _ft_top = _cands.head(20)
                    _ft_codes = [str(c) for c in _ft_top['代碼'].tolist()]
                    if '名稱' in _ft_top.columns:
                        _ft_names = dict(zip(_ft_codes, _ft_top['名稱'].astype(str)))
                    else:
                        _ft_names = {}
                    _ft_cohort = _tw_now().strftime('%Y-%m-%d')
                    try:
                        with st.spinner(f'抓進場價 + 存檔 {len(_ft_codes)} 檔…'):
                            _ft_n, _ft_miss = freeze_current_picks(
                                _ft_codes, factors=_factor_labels,
                                cohort=_ft_cohort, names=_ft_names)
                        _ft_msg = f'✅ 已凍結 {_ft_n} 檔（cohort {_ft_cohort}）到 Google Sheet「forward_test_picks」。'
                        if _ft_miss:
                            _ft_msg += f'（{_ft_miss} 檔抓不到進場價已略過）'
                        st.success(_ft_msg)
                    except Exception as _e_fz:  # noqa: BLE001 — 存檔失敗顯示不炸頁
                        st.error(f'❌ 凍結失敗：{type(_e_fz).__name__}: {_e_fz}')
                # ── 📊 前進式驗證對帳（FT-3 v19.143）：讀凍結 + 現價 → vs 0050 ──
                with st.expander('📊 前進式驗證對帳：這套選股實際贏 0050 嗎？', expanded=False):
                    st.caption('讀你 Google Sheet 的凍結紀錄、抓現價算「各期報酬 vs 0050」。'
                               '前進式驗證要時間累積 —— 剛開始樣本少、數字僅供參考。')
                    if st.button('📊 對帳（讀凍結 + 抓現價）', key='ft_reconcile_go'):
                        from src.services.forward_test_service import reconcile_all
                        with st.spinner('讀凍結紀錄 + 抓現價對帳…'):
                            st.session_state['_ft_recon'] = reconcile_all()
                    _ft_r = st.session_state.get('_ft_recon')
                    if _ft_r is None:
                        st.info('👆 點「📊 對帳」讀取凍結紀錄並計算績效。')
                    elif _ft_r[0] is None or _ft_r[0].empty:
                        st.info(f'⚪ {_ft_r[1].get("note", "尚無資料")}')
                    else:
                        _ft_df, _ft_ov = _ft_r
                        _ae = _ft_ov.get('avg_excess_pct')
                        _hr = _ft_ov.get('overall_hit_rate_pct')
                        _ae_s = '—' if _ae != _ae else f'{_ae:+.1f}%'
                        _hr_s = '—' if _hr != _hr else f'{_hr:.0f}%'
                        st.markdown(
                            f"**累積 {_ft_ov.get('n_cohorts', 0)} 批 / "
                            f"{_ft_ov.get('n_valid_total', 0)} 檔**"
                            f"｜平均超額 vs 0050：{_ae_s}｜整體勝率：{_hr_s}")
                        if _ft_ov.get('note'):
                            st.caption(f'ℹ️ {_ft_ov["note"]}')
                        _ft_disp = _ft_df.rename(columns={
                            'cohort': '凍結批次', 'n_valid': '檔數', 'avg_return_pct': '平均報酬%',
                            'benchmark_return_pct': '0050報酬%', 'excess_pct': '超額%',
                            'hit_rate_pct': '勝率%', 'beat_bench_rate_pct': '贏0050率%'})
                        _ft_cols = ['凍結批次', '檔數', '平均報酬%', '0050報酬%',
                                    '超額%', '勝率%', '贏0050率%']
                        st.dataframe(_ft_disp[_ft_cols], hide_index=True, use_container_width=True)
                # ── 🧬 AI 總結本頁（v19.122 Phase 2，用選股已載結果組 bundle，不重抓；fail-soft）──
                try:
                    from src.ui.tabs.tab_ai_chat import render_tab_summary
                    render_tab_summary('選股網', {
                        '選股結果': _cands.head(15).to_dict('records'),
                        '缺貨掃描': st.session_state.get('_shortage_rows'),
                        '抗跌RS': st.session_state.get('_rs_rows_all'),
                    }, context='general')
                except Exception as _ai_sum_e:
                    st.caption(f'🧬 AI 總結暫不可用：{type(_ai_sum_e).__name__}')

        # ── 🌍 全台股跨季趨勢排行（A-2 v19.140：全市場 ~2000 檔，非只存活池；button-gated）──
        with st.expander('🌍 全台股跨季趨勢排行（全市場，不限存活池）', expanded=False):
            st.caption('用近 5 季基本面算「毛利率/營益率是否逐季升、負債比是否逐季降、營收年增」，'
                       '列出全市場改善最明顯的股票。⚠️ 僅 5 季資料 → 用比率趨勢斜率（非「連續成長季數」）。')
            if st.button('🌍 掃全台股跨季趨勢', key='trend_rank_go'):
                try:
                    from src.services.fundamental_screener_service import get_cross_quarter_trends
                    _tr = get_cross_quarter_trends()
                    st.session_state['_trend_rank'] = _tr
                except Exception as _e_tr:  # noqa: BLE001 — 快照缺不炸
                    st.session_state['_trend_rank'] = None
                    print(f'[screener] 跨季趨勢排行失敗: {type(_e_tr).__name__}: {_e_tr}')
            _tr = st.session_state.get('_trend_rank')
            if _tr is None:
                st.info('👆 點「🌍 掃全台股跨季趨勢」列出全市場改善最明顯的股票（首次約數秒）。')
            elif _tr.empty:
                st.info('目前無跨季趨勢資料（季快照未就緒）。')
            else:
                _disp = _tr.rename(columns={
                    'stock_id': '代碼', 'gross_margin_slope': '毛利率趨勢',
                    'op_margin_slope': '營益率趨勢', 'debt_ratio_slope': '負債比趨勢',
                    'revenue_yoy': '營收YoY', 'favorable_count': '佳項數',
                    'favorable_of': '有資料項', 'n_quarters': '季數',
                }).round({'毛利率趨勢': 4, '營益率趨勢': 4, '負債比趨勢': 4, '營收YoY': 4})
                _cols = ['代碼', '佳項數', '有資料項', '毛利率趨勢', '營益率趨勢',
                         '負債比趨勢', '營收YoY', '季數']
                st.caption(f'全市場 {len(_tr):,} 檔 → 依「佳項數」由高到低取前 100。'
                           f'（🔺 毛利/營益率趨勢>0、🔻 負債比趨勢<0、營收YoY>0 為佳）')
                st.dataframe(_disp[_cols].head(100), hide_index=True, use_container_width=True)
                _csv_tr = _disp[_cols].to_csv(index=False).encode('utf-8-sig')
                st.download_button('💾 下載全台股跨季趨勢 CSV', data=_csv_tr,
                                   file_name='cross_quarter_trend_rank.csv',
                                   mime='text/csv', key='trend_rank_csv')

    with tab_mj:
        # v19.160 user 要求復活:MJ 體檢轉機掃描(找體質差→變好的公司)。
        # 修當初 v18.463「10 Tab→4 群組」改版漏掛的根因;守衛測試釘住掛載避免再變孤兒。
        from src.ui.tabs import render_mj_health_diff_tab
        _render_tab_isolated(render_mj_health_diff_tab, '體檢轉機')

# ══════════════════════════════════════════════════════════════
# GROUP 3: ETF（單檔診斷 + 多檔比較 + ETF 組合）
# v18.464: 移除質借模擬 Tab；新增標準差買賣帶 + 分散度分析到單檔 & 組合
# v18.465: 新增 MK 3-3-3 原則評估（成立>3年 / 3年年化>7% / 同儕前1/3）
# ══════════════════════════════════════════════════════════════
with tab_etf_main:
    tab_etf, tab_etf_compare, tab_etf_grp = st.tabs([
        '🔍 單檔診斷', '📊 多檔比較', '⚖️ ETF 組合',
    ])

    with tab_etf:
        from src.ui.etf.etf_tab_smart import (
            render_std_band_section, render_correlation_finder, render_333_section,
        )
        # 三個 smart 區塊統一吃「開始診斷」代號,且插在 AI 白話總結之前(hook)→ AI 置底
        def _etf_single_smart():
            _tk = st.session_state.get('etf_s_active')
            render_333_section(_tk, key_suffix='_single')
            render_std_band_section(_tk, key_suffix='_single')
            render_correlation_finder(_tk, key_suffix='_single')
        render_etf_single(gemini_fn=gemini_call, before_ai_hook=_etf_single_smart)

    with tab_etf_compare:
        from src.ui.etf import render_etf_grp_compare
        render_etf_grp_compare()

    with tab_etf_grp:
        render_etf_portfolio(gemini_fn=gemini_call)
        st.markdown('<hr style="margin:32px 0;border-color:#30363d;">', unsafe_allow_html=True)
        render_grape_ladder(gemini_fn=gemini_call)
        st.markdown('<hr style="margin:32px 0;border-color:#30363d;">', unsafe_allow_html=True)
        from src.ui.etf.etf_tab_smart import (
            render_std_band_section, render_correlation_finder, render_333_section,
            render_smart_ticker_input,
        )
        # 組合頁無單一主代號 → 用一個共用輸入框驅動下方三項分析（取代原本各自 3 個輸入框）
        _etf_grp_tk = render_smart_ticker_input(key_suffix='_grp')
        render_333_section(_etf_grp_tk, key_suffix='_grp')
        render_std_band_section(_etf_grp_tk, key_suffix='_grp')
        render_correlation_finder(_etf_grp_tk, key_suffix='_grp')
        # AI 置底（移到 smart 區塊之後）
        st.markdown('<hr style="margin:24px 0;border-color:#30363d;">', unsafe_allow_html=True)
        render_etf_ai(gemini_fn=gemini_call)

# ══════════════════════════════════════════════════════════════
# GROUP 4: 工具箱（資料診斷 + 教學）
# ══════════════════════════════════════════════════════════════
with tab_tools:
    tab_diag, tab_edu = st.tabs(['🔎 資料診斷', '📚 教學'])

    with tab_diag:
        from src.ui.pages import (
            render_data_coverage,
            render_data_registry_panel,
            render_fetch_monitor_panel,  # v19.96 批次4 Item1+2
            render_reconcile_panel,
        )
        render_data_coverage()
        st.markdown('---')
        render_data_registry_panel()
        render_fetch_monitor_panel()   # v19.96:@monitored 監控 + 孤兒 set-diff
        st.markdown('---')
        render_reconcile_panel()
        st.markdown('---')
        render_api_diagnostic()
        st.markdown('---')
        render_data_health_raw()
        st.markdown('---')
        from src.ui.pages import render_calibration_panel
        render_calibration_panel()

    with tab_edu:
        from src.ui.tabs import render_tab_edu
        _render_tab_isolated(render_tab_edu, '教學')

# ── 🧬 AI 問答（v19.121 Phase 1，L5→L3 ai_qa_service）──────────────
with tab_ai:
    from src.ui.tabs import tab_ai_chat
    _render_tab_isolated(tab_ai_chat.render, 'AI 問答')

st.markdown('<div style="text-align:center;font-size:10px;color:#484f58;padding:8px 0;">⚠️ 台股AI戰情室 v3.0 · 僅供學術研究，非投資建議，盈虧自負</div>', unsafe_allow_html=True)
