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

# v18.182 ARCHIVED: 🧪 回測找參數 / v18.187 ARCHIVED: 📈 月營收進退 / v18.189 ARCHIVED: 📊 MJ 體檢變化
# 各暫封存模組保留磁碟，啟用方式見各 ARCHIVED 原始注解。
# v18.463: UI 重構 — 10 平鋪 Tab → 4 大群組 + Sub-tabs（sub-tab 變數名稱維持不變，測試仍通過）
tab_market, tab_stocks, tab_etf_main, tab_tools = st.tabs([
    '🌍 市場環境', '🔬 選股', '🏦 ETF', '🔧 工具箱',
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
    tab_stock, tab_stock_grp, tab_screener = st.tabs(['🔬 個股', '🏆 個股組合', '🔭 選股網'])

    with tab_stock:
        from src.ui.tabs import render_tab_stock
        _render_tab_isolated(render_tab_stock, '個股')

    with tab_stock_grp:
        from src.ui.tabs import render_stock_grp
        _render_tab_isolated(render_stock_grp, '個股組合')

    with tab_screener:
        # v18.463: 選股網 — AI 置頂卡（結果生成後自動填入）
        _screener_ai_md = next(
            (v for k, v in st.session_state.items() if '_ai_md_' in k and v),
            None,
        )
        with st.expander(
            '🤖 AI 選股建議' + (' ✅ 已生成，點此展開' if _screener_ai_md else ' — 完成下方篩選後結果顯示於此'),
            expanded=bool(_screener_ai_md),
        ):
            if _screener_ai_md:
                st.markdown(_screener_ai_md)
            else:
                st.info('完成下方篩選流程，點「🤖 生成 AI 三型建議報告」後，結果同步顯示此處。')
        # v19.65: 缺貨 / 供不應求選股（獨立 expander，collapsed，點按鈕才打 FinMind）
        # v19.66: 候選池改基本面存活池優先（相容免費 FinMind）+ AI 三型建議報告
        with st.expander('🔥 缺貨 / 供不應求選股（全市場掃描）', expanded=False):
            from src.ui.tabs.shortage_screener_ui import render_shortage_screener
            render_shortage_screener(gemini_fn=gemini_call)
        # v19.70: 抗跌 / 逆勢贏大盤選股（大盤下跌時仍贏過大盤的 RS 前 50，點按鈕才抓價）
        with st.expander('🛡️ 抗跌 / 逆勢贏大盤選股（RS 前 50）', expanded=False):
            from src.ui.tabs.rs_leader_ui import render_rs_leader_screener
            render_rs_leader_screener(gemini_fn=gemini_call)
        # v18.xxx: 選股 Pipeline（倒序）— 三階段 S1/S2 → 殖利率確認
        # 原始正序（殖利率篩選→三階段）已改為：先跑 S1/S2，通過後再顯示殖利率資訊
        from src.ui.tabs import render_tab_stock_picker
        from src.ui.tabs.tab_stock_picker import (
            PICKER_DEEP_SCAN_N, render_prescreen_panel,
        )
        from src.ui.tabs.yield_screener import fetch_twse_yield_pe, render_yield_confirm
        # v19.64：全台股基本面初篩「結果面板」——把 Phase 2 後端算出的四項全過存活池攤出來看
        render_prescreen_panel()
        # Phase 2 全台股基本面漏斗（L6→L3）：先用 MOPS 全市場季快照跑「四項全過」初篩
        #   ①負債比<50% ②三率三升 YoY ③淨流動值>0 ④EPS>0
        # → 交集 TWSE 估值池 → PE/殖利率確認 → 依估值便宜度取前 N 深跑三階段。
        # gate_pool_by_fundamentals 內含 fail-loud + UI 韌性（快照缺 → 退回估值篩選）。
        from src.services.fundamental_screener_service import gate_pool_by_fundamentals
        _fund_cnt = None
        _twse_scrn = fetch_twse_yield_pe()
        if not _twse_scrn.empty:
            _pool = _twse_scrn.copy()
            _pe_col = '本益比'    if '本益比'    in _pool.columns else None
            _yd_col = '殖利率(%)' if '殖利率(%)' in _pool.columns else None
            # ① 全台股基本面初篩：四項全過（與 TWSE 估值池取交集）
            _pool, _gate = gate_pool_by_fundamentals(_pool)
            _fund_cnt = _gate['matched']
            if _pe_col:
                # ② 估值 sanity：排除 PE ≤ 0（虧損）或 PE > 100（估值異常 / 價值陷阱）
                _pool = _pool[(_pool[_pe_col] > 0) & (_pool[_pe_col] < 100)]
            if _yd_col:
                # ③ 殖利率 sanity：排除 > 12%（配息恐削減 / 價值陷阱）；保留 ≥ 2%（配息股）
                _pool = _pool[(_pool[_yd_col] >= 2.0) & (_pool[_yd_col] <= 12.0)]
            _after = len(_pool)
            # 依「估值便宜度」（本益比由低到高）取前 N 深掃
            if _pe_col:
                _top_cands = _pool.nsmallest(PICKER_DEEP_SCAN_N, _pe_col).reset_index(drop=True)
            else:
                _top_cands = _pool.head(PICKER_DEEP_SCAN_N).reset_index(drop=True)
            _fund_seg = (f'基本面四項全過 {_gate["survivors"]} 檔 ∩ 估值池 → {_fund_cnt} 檔 → '
                         if _fund_cnt is not None else '')
            st.caption(
                f'📊 全台股基本面漏斗：{_fund_seg}PE/殖利率確認後 {_after} 檔'
                f'（排除虧損 / PE>100 / 殖利率<2% 或 >12%）→ 依估值便宜度取前 {PICKER_DEEP_SCAN_N} 檔'
                f'深跑三階段（殖利率移至最後確認）{_gate["note"]}'
            )
        else:
            _top_cands = None
        # Step 2: 三階段篩選 S1+S2（skip_s3=True 跳過 AI，通過清單存入 session_state）
        render_tab_stock_picker(
            gemini_fn=gemini_call, candidates=_top_cands,
            source_label='基本面優選' if _fund_cnt is not None else '估值優選',
            skip_s3=True,
        )
        # Step 3: 殖利率確認（S1/S2 通過標的）
        _s1s2_pass = st.session_state.get('picker_s1s2_qualified_tickers', [])
        render_yield_confirm(_s1s2_pass, _twse_scrn)

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
        from src.ui.pages import render_data_coverage, render_data_registry_panel, render_reconcile_panel
        render_data_coverage()
        st.markdown('---')
        render_data_registry_panel()
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

st.markdown('<div style="text-align:center;font-size:10px;color:#484f58;padding:8px 0;">⚠️ 台股AI戰情室 v3.0 · 僅供學術研究，非投資建議，盈虧自負</div>', unsafe_allow_html=True)
