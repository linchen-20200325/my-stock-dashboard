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
            st.success('🟢 已登入')
            if st.button('🚪 登出', key='btn_oauth_logout_sb',
                          use_container_width=True):
                st.session_state.pop('gsheet_tokens', None)
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
            _sb_url = _sb_buildurl(_sb_cfg['client_id'], _sb_cfg['redirect_uri'])
            st.link_button('🔐 用 Google 登入', _sb_url, use_container_width=True)
            st.caption('登入後 ETF 組合 Tab 可雲端存取')
    elif _sb_gsa and _sb_sid:
        st.caption('ℹ️ 使用 Service Account（舊版部署）')
    else:
        st.caption('⚙️ OAuth 尚未設定 — 至「ETF 組合」Tab 展開「💾 雲端儲存」設定')

    st.markdown('---')
    st.markdown('### 🔌 連線狀態')
    # [Fixed] 與 line 73-74 對齊：st.secrets 優先，os.environ fallback
    _fm_tok  = str(st.secrets.get('FINMIND_TOKEN',  os.environ.get('FINMIND_TOKEN',  '')))
    # Gemini 改看整池 key（GEMINI_API_KEY + _2~_6），任一把有設就算通
    _gm_keys  = _gemini_keys()
    _gm_slots = [_n for _n in _GEMINI_KEY_NAMES
                 if str(st.secrets.get(_n, '') or os.environ.get(_n, '') or '').strip()]
    _px_host = str(st.secrets.get('PROXY_HOST',     os.environ.get('PROXY_HOST',     '')))
    # PROXY_URL 與 PROXY_HOST 二擇一即可亮 ✅
    if not _px_host:
        _px_host = str(st.secrets.get('PROXY_URL', os.environ.get('PROXY_URL', '')))
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
        _px_port = str(st.secrets.get('PROXY_PORT', os.environ.get('PROXY_PORT', '')))
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
    '<div style="display:flex;align-items:center;gap:10px;padding:4px 0 8px;">'    '<span style="font-size:22px;font-weight:900;color:#e6edf3;">&#128202; 台股 AI 戰情室</span>'    '<span style="font-size:10px;color:#484f58;background:#161b22;border-radius:10px;padding:2px 8px;">v4.0 Pro</span>'    '</div>',
    unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# 🧭 總經指南針 — render_macro_compass 已抽至 src/ui/render/app_render.py
# (v18.404 U5 B3-γ);_render_compass_card 同步搬走(internal helper)
# ══════════════════════════════════════════════════════
from src.ui.render.app_render import render_macro_compass  # noqa: E402
render_macro_compass()

# v18.182 ARCHIVED: 🧪 回測找參數 Tab 暫封存
# 未來啟用：(1) tuple 加回 tab_backtest 在 tab_etf_margin 之後 tab_diag 之前
# (2) labels 加回 '🧪 回測找參數' 對應位置 (3) 取消下方 with tab_backtest 區塊註解
# v18.187 ARCHIVED: 📈 月營收進退 Tab 暫封存（FinMind batch endpoint 已不支援免費 tier）
# 未來啟用：(1) tuple 加回 tab_rev_screener 在 tab_screener 之後 tab_mj_diff 之前
# (2) labels 加回 '📈 月營收進退' 對應位置 (3) 取消下方 with tab_rev_screener 區塊註解
# v18.189 ARCHIVED: 📊 MJ 體檢變化 Tab 暫封存（功能改整合至「🏆 個股組合」批次體檢區塊下方）
# 未來啟用：(1) tuple 加回 tab_mj_diff 在 tab_screener 之後 tab_etf 之前
# (2) labels 加回 '📊 MJ 體檢變化' 對應位置 (3) 取消下方 with tab_mj_diff 區塊註解
tab_macro, tab_heatmap, tab_stock, tab_stock_grp, tab_screener, tab_etf, tab_etf_grp, tab_etf_margin, tab_diag, tab_edu = st.tabs([
    '🌍 總經', '🗺️ 產業熱力圖', '🔬 個股', '🏆 個股組合',
    '💎 高息網', '🏦 ETF', '⚖️ ETF組合', '💰 ETF質借模擬', '🔎 資料診斷', '📚 教學',
])

# ══════════════════════════════════════════════════════════════
# TAB 1: 總體經濟
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

    st.markdown(
        f'<div style="background:#0d1117;border:1px solid {_gl_color};border-radius:8px;'
        f'padding:8px 14px;margin-bottom:8px;display:flex;align-items:center;gap:16px;">'
        f'<span style="font-size:16px;font-weight:900;color:{_gl_color};">{_gl_label}</span>'
        f'<span style="font-size:12px;color:#c9d1d9;">建議持股 <b>{_gl_pos}</b></span>'
        + (f'<span style="font-size:12px;color:#8b949e;">旌旗均值 {_jqpct:.0f}%</span>'
           if _jqpct is not None else '') +
        f'<span style="font-size:11px;color:#484f58;margin-left:auto;">更新：{_ts_top}</span>'
        f'</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# AI 總經戰情 — 新聞抓取已抽至 src/data/news/(v18.398 P5-B3-β R8)
# caller 改走 `from src.data.news import fetch_macro_news, fetch_stock_news`
# ══════════════════════════════════════════════════════════════


def _build_llm_context(macro_info: dict) -> str:
    """將 session_state 中的量化總經數據格式化為純文字供 LLM 使用"""
    _vix = macro_info.get('vix') or {}
    _exp = macro_info.get('tw_export') or {}
    _pmi = macro_info.get('ism_pmi') or {}
    _cpi = macro_info.get('us_core_cpi') or {}
    _ndc = macro_info.get('ndc_signal') or {}
    _mi  = st.session_state.get('m1b_m2_info') or {}
    _bi  = st.session_state.get('bias_info') or {}
    _lines = []
    if _vix.get('current'):
        _lines.append(f'• VIX 恐慌指數：{_vix["current"]} (MA20={_vix.get("ma20","N/A")})')
    if _exp.get('yoy') is not None:
        _lines.append(f'• 台灣外銷訂單 YoY：{_exp["yoy"]:+.1f}%  ({_exp.get("date","")})')
    if _pmi.get('value') is not None:
        _lines.append(f'• 🇹🇼 台灣 PMI：{_pmi["value"]}  ({_pmi.get("date","")}，>50 擴張)')
    if _cpi.get('yoy') is not None:
        _lines.append(f'• 美國核心 CPI YoY：{_cpi["yoy"]:+.1f}%  ({_cpi.get("date","")})')
    if _ndc.get('score') is not None:
        _lines.append(f'• NDC 景氣燈號分數：{_ndc["score"]:.0f}/45')
    if _mi.get('m1b_yoy') is not None and _mi.get('m2_yoy') is not None:
        _gap = round(float(_mi['m1b_yoy']) - float(_mi['m2_yoy']), 2)
        _lines.append(f'• 台灣 M1B={_mi["m1b_yoy"]:.1f}%  M2={_mi["m2_yoy"]:.1f}%  Gap={_gap:+.2f}%')
    if _bi.get('bias_240') is not None:
        _lines.append(f'• 台股大盤年線乖離率 BIAS240：{_bi["bias_240"]:+.1f}%')
    return '\n'.join(_lines) if _lines else '（量化數據載入中，請先點擊更新總經拼圖）'


# ══════════════════════════════════════════════════════════════
# TAB 1/3/4/10 render 綁定 — v18.439 修復 + v18.440 per-tab 隔離
# 94a257d「chore(dead): 刪 4 個 0-caller dead fn」誤把這 4 個
# `with tab_X: render_tab_X()` 渲染綁定當死碼刪掉,導致
# 總經 / 個股 / 個股組合 / 教學 四個分頁全空白(0 內容)。
# render_* 採「tab 內 lazy import」:① 避免 app ↔ tab 循環 import
# ② 杜絕 module-level import 被 ruff F401 當未用再刪的回歸。
# v18.440:這 4 分頁久未綁定渲染 → code 與 helper 簽章已漂移(如 tab_edu
# 呼叫 make_sparkline 傳了已移除的 high_is_bad/lookback → TypeError 拖垮全頁)。
# 改各自 try/except 隔離:單一分頁出錯只在該 tab st.error(§1 fail-loud 可見),
# 不再拖垮其他分頁 / 全頁。
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


with tab_macro:
    from src.ui.tabs import render_tab_macro
    _render_tab_isolated(render_tab_macro, '總經')
with tab_stock:
    from src.ui.tabs import render_tab_stock
    _render_tab_isolated(render_tab_stock, '個股')
with tab_stock_grp:
    from src.ui.tabs import render_stock_grp
    _render_tab_isolated(render_stock_grp, '個股組合')
with tab_edu:
    from src.ui.tabs import render_tab_edu
    _render_tab_isolated(render_tab_edu, '教學')


# ══════════════════════════════════════════════════════════════
# TAB: ETF 單一深度診斷 + 多檔批次評分（v18.223 子分頁）
# ══════════════════════════════════════════════════════════════
with tab_etf:
    _etf_sub_tabs = st.tabs(['🔍 單檔深度診斷', '📊 多檔評分比較'])
    with _etf_sub_tabs[0]:
        render_etf_single(gemini_fn=gemini_call)
    with _etf_sub_tabs[1]:
        from src.ui.etf import render_etf_grp_compare
        render_etf_grp_compare()

# ══════════════════════════════════════════════════════════════
# TAB: ETF 組合戰情室（4 區段整合：組合配置 + 歷史回測 + AI + 葡萄串）
# ══════════════════════════════════════════════════════════════
with tab_etf_grp:
    # ── ① 組合配置與再平衡（唯一輸入來源，下游模組共享 etf_portfolio_rows）──
    render_etf_portfolio(gemini_fn=gemini_call)
    st.markdown('<hr style="margin:32px 0;border-color:#30363d;">', unsafe_allow_html=True)

    # ── ② 葡萄串領息法（自動讀取持股做月配息評估）──
    render_grape_ladder(gemini_fn=gemini_call)
    st.markdown('<hr style="margin:32px 0;border-color:#30363d;">', unsafe_allow_html=True)

    # ── ③ AI 綜合評斷 + 自由提問（壓軸區，整合所有上方分析）──
    render_etf_ai(gemini_fn=gemini_call)

# ══════════════════════════════════════════════════════════════
# TAB: ETF 質借倒金字塔加碼模擬器 (v18.162)
# ══════════════════════════════════════════════════════════════
with tab_etf_margin:
    from src.ui.tabs import render_etf_margin_simulator
    render_etf_margin_simulator()

# ══════════════════════════════════════════════════════════════
# TAB: 7% 高殖利率防禦網（Screener Mode）
# ══════════════════════════════════════════════════════════════
with tab_screener:
    from src.ui.tabs import render_yield_screener
    _picker_candidates = render_yield_screener()

    # ── 🎯 智慧選股（三階段濾網 + AI 三型建議）— 接續高息網候選清單 ──
    st.markdown('---')
    from src.ui.tabs import render_tab_stock_picker
    render_tab_stock_picker(gemini_fn=gemini_call, candidates=_picker_candidates)

# ══════════════════════════════════════════════════════════════
# TAB: 月營收進退篩選（v18.180） — v18.187 ARCHIVED
# FinMind TaiwanStockMonthRevenue batch endpoint (無 data_id) 已不支援免費/sponsor tier
# 模組 monthly_revenue_screener.py 保留磁碟，未來啟用：取消下方註解即可
# ══════════════════════════════════════════════════════════════
# with tab_rev_screener:
#     from monthly_revenue_screener import render_monthly_revenue_screener
#     render_monthly_revenue_screener()

# ══════════════════════════════════════════════════════════════
# TAB: MJ 體檢變化（v18.186 / v18.188 batch 版） — v18.189 ARCHIVED
# 功能改整合至「🏆 個股組合」批次體檢區塊下方「📊 MJ 趨勢分數」新區塊
# 模組 tab_mj_health_diff.py 與 mj_trend_score.py 保留磁碟，未來啟用：取消下方註解
# ══════════════════════════════════════════════════════════════
# with tab_mj_diff:
#     from tab_mj_health_diff import render_mj_health_diff_tab
#     render_mj_health_diff_tab()

# ══════════════════════════════════════════════════════════════
# TAB: 資料診斷（Raw Data only）
# ══════════════════════════════════════════════════════════════
with tab_diag:
    # v18.280 — 學 Fund 架構 + 預設視角:覆蓋率表(用戶視角)放最上方,
    # API Key / Proxy 雙跑(developer 視角)放後。對齊 Fund tab5 Section ⓪。
    from src.ui.pages import render_data_coverage, render_data_registry_panel, render_reconcile_panel
    render_data_coverage()
    st.markdown('---')
    # v18.394 Path C:資料源完整清單(50+ entries by SSOT 11 emoji category)。
    # coverage tab 4-row 是 Tab 級總覽;此 panel 是資料源級細項。語意分清楚不重複。
    render_data_registry_panel()
    st.markdown('---')
    # v18.403 #8+#12:§4.3 雙演算法對帳 panel(US10Y / 月營收 / 健康評分)。
    render_reconcile_panel()
    st.markdown('---')
    render_api_diagnostic()
    st.markdown('---')
    render_data_health_raw()
    st.markdown('---')
    from src.ui.pages import render_calibration_panel
    render_calibration_panel()

# ══════════════════════════════════════════════════════════════
# TAB: 產業熱力圖
# ══════════════════════════════════════════════════════════════
with tab_heatmap:
    render_sector_heatmap(gemini_fn=gemini_call)

st.markdown('<div style="text-align:center;font-size:10px;color:#484f58;padding:8px 0;">⚠️ 台股AI戰情室 v3.0 · 僅供學術研究，非投資建議，盈虧自負</div>', unsafe_allow_html=True)
