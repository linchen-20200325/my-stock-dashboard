import streamlit as st
import os
import re

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW

# ── F2(2026-08)：`_AppProxy` / `sys.modules['app']` 劫持已移除 ──────────
# 原註解（保留供追溯）：「tab_*.py 用 `from app import X`，Python 走
# sys.modules['app'] 找模組。Cloud 上 sys.modules['__main__'] 是 Streamlit CLI
# binary 不是 script…」——那整套 ModuleType proxy 的**唯一**存在理由，就是讓
# 5 處 L5→L6 的 `from app import gemini_call / api_key / parse_stocks / _bps /
# _get_fm_token / _tw_now_str`（CLAUDE.md V-UP-APP-1）在 Streamlit Cloud 上不炸。
#
# 那 5 處已於 F2 全數改走 L3/L0：
#   gemini_call / get_gemini_api_key → src/services/app_ai_service.py  (L3)
#   parse_stocks                     → shared/parse_helpers.py          (L0)
#   _tw_now_str                      → shared/macro_compute.py          (L0)
#   _get_fm_token                    → src/config/config.py             (L0)
#   _bps                             → src/data/proxy/proxy_helper.py   (L1)
# → production code 已 0 處 `from app import`（由 tests/test_f2_app_decomposition.py
#   與 tests/test_c3_layering_guard.py 規則 5 共同釘住），proxy 沒有消費者了。
#
# ⚠️ 仍在用 `from app import` 的只剩 tests/test_parse_helpers.py::test_app_reexport，
#    它跑在 **subprocess** 裡且是 `import app`（不是 __main__）→ Python 自己就會把
#    真模組註冊進 sys.modules['app']，本來就不需要這個 proxy。

# ── 台灣時間（UTC+8）─────────────────────────────────────
# F2:原本這裡自建第 N 份 `timezone(timedelta(hours=8))`(§4.5 全站已有多份複本)。
# 改吃 L0 SSOT;`_tw_now` 供下方前進式驗證 cohort 用,`_tw_now_str` 保留別名
# 是因為 tab_macro 過去靠 `from app import _tw_now_str`(現已直接吃 L0)。
from shared.macro_compute import tw_now as _tw_now, tw_now_str as _tw_now_str  # noqa: F401

print('[INFO] main.py v3.0 戰情室 載入完成')

# ── 新增模組（根據說明書 v1.0）──────────────────────────────
# ── v3.0 新增模組（§5-§11）──────────────────────────────────
from src.ui.etf import (  # noqa: E402
    render_etf_single,
    render_sector_heatmap,
)
# P3 v19.202:render_etf_portfolio / render_etf_ai / render_grape_ladder 的呼叫已搬進
# 💼 我的持股戰情室(組合深度分析 + 葡萄串),app.py 不再直接呼叫 → 移除頂層 import。
from src.ui.pages import render_data_health_raw  # noqa: E402
from src.ui.pages import render_api_diagnostic  # noqa: E402
# F2:`TAIWAN_ADVISOR_PERSONA` 的唯一用途是 gemini_call 的 systemInstruction,
# 隨 gemini_call 一起搬到 src/services/app_ai_service.py,app.py 不再需要。

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
# F2 註:`api_key` 這個 module-level 名字**仍有用**,不是殘骸 ——
#   (1) 下面這行把它同步進 os.environ,`macro_state_locker._default_gemini_call`
#       等純 .py 路徑靠 os.environ 取金鑰;
#   (2) 但它**不再**被 gemini_call 消費(金鑰池已下沉 L3,自行讀 st.secrets/env),
#       也不再被 tab_stock 以 `from app import api_key` 取用
#       (改走 L3 `app_ai_service.get_gemini_api_key()`)。
if FINMIND_TOKEN:
    os.environ['FINMIND_TOKEN'] = FINMIND_TOKEN
if api_key:
    os.environ['GEMINI_API_KEY'] = api_key

# F2:`_get_fm_token()` 已下沉 L0 → `src.config.get_finmind_token()`(app.py 內
# 本來就沒有 caller,唯一消費者是 tab_macro,原本靠 `from app import _get_fm_token`)。

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
    # [Phase 3] 從 URL query_params 恢復關鍵狀態（手機斷線重連可保留「設定」）
    #
    # FIX(S1 §1 Fail Loud｜殭屍已載入態): 原本這裡還有一段
    #     if _qp.get('chips') == '1':
    #         st.session_state['chips_loaded'] = True
    #   它把「已載入」**旗標**從 URL 還原，但**資料**（cl_data / cl_ts / mkt_info /
    #   macro_info / warroom_summary）全都住在 session_state，一個也救不回來。
    #   而 chips_loaded 一個人就同時滿足 tab_macro.py:146-150 的 `_macro_loaded`
    #   與 tab_macro.py:372 的 `_load_heavy` ⇒ **空 session 被渲染成「已載入」**：
    #     · 跳過 tab_macro.py:200-208 誠實的「👉 點擊上方按鈕載入總經資料」
    #     · 燈號卡印「⏳ 燈號等待中（尚無資料）」(section_traffic_light.py:185-191)
    #     · warroom_summary 不存在 → get_macro_state() 回 regime='unknown'
    #       (macro_state_locker.py:365-367) → 個股 / 個股組合 / 選股網 / ETF /
    #       工具箱 五頁同時顯示「⬜ 總經未評估」
    #     · 今日關鍵從 2 項掉成 1 項 —— CPI 只讀 session_state['macro_info']
    #       (macro_alert.py:276-282，零 fallback) 故死；美債 10Y 走
    #       @st.cache_data(TTL_30MIN)(macro_alert.py:204-205) 是 **server 級、
    #       跨 session 存活** 故活。這個不對稱正是「session 沒了、cache 還在」
    #       的指紋，也是本 bug 唯一能從畫面反推根因的線索。
    #
    #   ⚠️ 本修法**不阻止 session 被重建** —— 那是 Cloud 容器回收 / websocket
    #   斷線 / 記憶體壓力，非 code 可控。它做的是讓重建後**誠實承認沒資料**：
    #   使用者看到空狀態 → 按一次按鈕 → 快取還熱 → 數秒回來，
    #   而不是對著一整頁空值以為系統壞掉。§1「寧可炸掉，不可造假」。
    #
    #   ⚠️ chips_loaded 本身**不是**壞設計，切勿一併拔除：
    #     · tab_macro.py:185 由「使用者真的按下按鈕」寫入 —— 語意是「本 session
    #       嘗試過載入」。抓取失敗時它仍須為 True，畫面才能顯示失敗診斷，
    #       而不是退回「還沒載入」假裝什麼都沒發生。
    #     · section_chips.py:136-137 / :752 用它算 `_attempted`，區分
    #       「按過但三源全空（→ 印 FINMIND_TOKEN 診斷卡）」vs「根本還沒按」。
    #   壞掉的只有「跨 session 還原」這一件事，故只拔還原、不動語意。
    #
    #   sid 保留還原：那是「使用者選了哪支股票」＝設定，不是抓回來的資料，
    #   跨 session 還原它不會製造任何假的已載入狀態。
    try:
        _qp = st.query_params
        _qp_sid = _qp.get('sid')
        if _qp_sid and isinstance(_qp_sid, str) and _qp_sid.isdigit():
            st.session_state['_qp_sid'] = _qp_sid  # 個股 Tab 啟動時讀取
        # A+C(v19.204 順暢化):還原上次選定的投組 Sheet ID(?sheet=)→ ETF+個股兩通道。
        # 解「必須先繞 📁 組合管理選 Sheet 才能去戰情室/選股分析」的順序痛點:選過一次後,
        # 重整/斷線重連/直接開任一頁都自動有源(戰情室/選股的既有 auto-load + 15min 快取即生效)。
        # 安全:Sheet ID 非憑證(存取仍需 OAuth + Sheet ACL),且屬「設定」非抓回來的資料 →
        # 跨 session 還原不會製造假「已載入」態(同上方 sid 的理由;§1)。setdefault:本 session
        # 已手動選過則不覆寫(當次選擇優先)。
        _qp_sheet = _qp.get('sheet')
        if _qp_sheet and isinstance(_qp_sheet, str) and _qp_sheet.strip():
            # §8.2 R4:app.py(L6)不得 import L1 gsheet_portfolio 取常數 → 用其 session key
            # 字面值(與本檔側欄既有 'portfolio_sheet_id' / 'stock_portfolio_sheet_id' 一致;
            # gsheet_portfolio 的 PORTFOLIO_SHEET_KEY/STOCK_PORTFOLIO_SHEET_KEY 即這兩個值)。
            st.session_state.setdefault('portfolio_sheet_id', _qp_sheet.strip())
            st.session_state.setdefault('stock_portfolio_sheet_id', _qp_sheet.strip())
    except Exception as _qpe:
        print(f'[query_params restore] {_qpe}')

# [Phase 3] 單向清理（原為雙向同步）：舊版會把 chips_loaded 寫回 URL 成 ?chips=1，
# 專供上方那段已移除的還原邏輯使用。還原端沒了，這個參數就**零 reader**，
# 留著只會讓使用者的書籤 / 分享連結帶著一個看似有意義、實則無效的狀態。
# 這裡順手清掉殘留值（含使用者從舊版複製的舊網址）。
try:
    _qp_w = st.query_params
    if _qp_w.get('chips') is not None:
        del _qp_w['chips']
except Exception:
    pass

st.markdown(f"""<style>
.main{{background:#0e1117;}}
[data-testid="stSidebar"]{{background:#161b22;}}
.stTabs [data-baseweb="tab-list"]{{gap:2px;}}
.stTabs [data-baseweb="tab"]{{background:#161b22;color:#8b949e;border-radius:6px 6px 0 0;padding:8px 16px;font-size:13px;}}
.stTabs [aria-selected="true"]{{background:linear-gradient(135deg,#1f6feb,#0d4faa);color:#fff;font-weight:700;}}
/* v19.174 去識別化：新名 .strategy-card；.teacher-card 為過渡期舊名(ui_widgets.strategy_box
   目前仍輸出舊 class,待該檔 caller 收乾淨後可刪。兩者樣式必須一致,否則畫面會漏樣式) */
.strategy-card,.teacher-card{{background:#0d1117;border-left:3px solid #ffd700;border-radius:0 8px 8px 0;padding:10px 14px;margin:6px 0;}}
.health-A{{background:linear-gradient(90deg,#0d2818,#0d1117);border:2px solid {TRAFFIC_GREEN};border-radius:12px;padding:16px;text-align:center;}}
.health-B{{background:linear-gradient(90deg,#2a1f00,#0d1117);border:2px solid {TRAFFIC_YELLOW};border-radius:12px;padding:16px;text-align:center;}}
.health-C{{background:linear-gradient(90deg,#2a0d0d,#0d1117);border:2px solid {TRAFFIC_RED};border-radius:12px;padding:16px;text-align:center;}}
</style>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════
# v18.302 §8.3 app.py 拆檔:parse_stocks 已提至 shared/parse_helpers.py(L0)。
# F2:最後一個靠 `from app import parse_stocks` 的 caller(tab_stock_grp)已改直吃 L0,
# 這行現在只服務 tests/test_parse_helpers.py::test_app_reexport 的身分驗證。
from shared.parse_helpers import parse_stocks  # noqa: F401

# ── Gemini 金鑰池 + gemini_call ── F2(2026-08)已下沉 L3 ────────────────
# 原本整段(金鑰池常數 / round-robin Lock / _gemini_keys / gemini_call ~90 LOC)
# 住在 app.py = L6 直接打 Gemini HTTP(CLAUDE.md V-APP-1)。現在住
# src/services/app_ai_service.py(L3),邏輯一字未改。
# app.py 保留 import 是因為它**確實是 orchestrator 職責**:把 gemini_fn 注入
# 各 render(render_sector_heatmap / render_etf_single / render_grape_ladder /
# render_etf_portfolio / render_etf_ai),以及側欄「連線狀態」顯示金鑰池偵測結果。
from src.services.app_ai_service import (  # noqa: E402
    GEMINI_KEY_NAMES as _GEMINI_KEY_NAMES,
    gemini_call,
    gemini_keys as _gemini_keys,
)

# ── 本地快取 / 個股 fetcher ────────────────────────────────
# FIX(A-2 死碼清理): 這裡原有兩組 `# noqa: F401` 的 re-export shim ——
#   (1) `from shared.app_cache import _cache_key, _load_cache, _save_cache, _CACHE_DIR`
#       (v18.404 B3-α 抽出時留的 thin shim)
#   (2) `from src.data.stock.app_stock_fetchers import` 6 個 fetcher + `_get_loader`
#       + `_expected_latest_trading_date`(v18.405 U5 B3-δ 抽出時留的)
#   兩組都是「為了讓舊 caller `from app import xxx` 不用改」而留的轉發層。
#   但 F2(2026-08)收掉 5 處 L5→L6 上行 import 後，**production 已零 `from app import`**
#   (`test_c3_layering_guard.py` 規則 5 的 `_KNOWN_VIOLATIONS` 4 條已移除、反向守衛生效)；
#   app.py 自己也完全不用這些符號(`noqa: F401` 就是 flake8 早就在講的話)。
#   ⇒ 轉發層的兩端都沒人了，屬純歷史殘骸。真 caller 一律直接吃 L0 `shared.app_cache`
#     與 L1 `src.data.stock.app_stock_fetchers`。
#   連帶同步移除 `test_c3_layering_guard.py` 的 EX-PASSTHRU-1 白名單條目
#   `("R4", "app.py", "src.data.stock.app_stock_fetchers")` —— 該檔 `test_rule4_whitelist_not_stale`
#   是**反向守衛**：留著已不違憲的條目會直接紅燈（設計上刻意如此，防清單越長越假）。
#   ⚠️ 唯一保留的 re-export 是上方的 `parse_stocks`(shared/parse_helpers)：
#     `tests/test_parse_helpers.py` 仍以 subprocess 走 `from app import parse_stocks`。



# ════════════════════════════════════════════════════════════════
# 技術指標計算 — 已抽出至 tech_indicators.py（PR P2-B Phase 1）
# ════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════
# 健康度評分（0~100）— 已抽出至 scoring_helpers.py（PR P2-B Phase 3）
# ════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════
# 初學者友善說明系統 — 已抽出至 ui_widgets.py（PR P2-B Phase 2）
# ════════════════════════════════════════════════════════════════
from src.ui.render import traffic_light  # noqa: E402
# P2-B Phase 5 A/B/C/D: 4 個 TAB 全部已抽到獨立模組（app.py 9208→1394 行，−85%）

# FIX(A-2 死碼清理): 原有 `_TERM_HELP_LI = show_term_help('PCR') + ... ('ADL') + ... ('M1B-M2')`，
#   註解寫「在先行指標 section 使用」—— 但全檔零讀取點（先行指標區早已搬到
#   `src/ui/tabs/macro/section_chips.py`，自己呼叫 show_term_help）。
#   它是 **module level** 賦值 ⇒ 每一次 rerun 都白呼叫 3 次組出一段沒人看的 HTML。
#   連帶 `show_term_help` 在 app.py 失去唯一 caller，故從 import 一併移除
#   （`traffic_light` 仍在 :958 使用，保留）。

# generate_ai_comment 已抽至 src/services/app_ai_service.py(v18.398 P5-B3-β R7)
# caller 改走 `from src.services.app_ai_service import generate_ai_comment`

# ── kpi / strategy_conclusion / signal_box 已抽至 ui_widgets.py ──
#    (v19.174 去識別化：strategy_conclusion 舊名 teacher_conclusion)

# render_health_score 已抽至 src/ui/render/app_render.py(v18.404 U5 B3-γ)
# caller 改走 `from src.ui.render.app_render import render_health_score`


# FIX(A-2 死碼清理): 原有 `primary_stock = '2330'` —— 全 repo 零讀取點
#   （只有本行賦值）。個股預設代號真正的來源是 `?sid=` query param 還原
#   （見上方開機閘門的 `_qp_sid`）與各 Tab 自己的 `st.text_input` 預設值。

# ── Sidebar: 整合 AI 分析 ───────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="text-align:center;padding:8px 0;font-size:15px;font-weight:900;color:#e6edf3;">&#128202; 台股AI戰情室 v3.0</div>', unsafe_allow_html=True)
    st.markdown('---')
    # v18.461 FIX: 使用台灣時區（UTC+8），避免 Streamlit Cloud UTC 服務器在 00:00~08:00 TW 顯示昨天日期
    # FIX(§3.3 SSOT): 原自建 `_TW_TZ_SB = timezone(timedelta(hours=8))`,而本檔 L32 已
    #   `from shared.macro_compute import tw_now as _tw_now`(同一個 UTC+8 定義)。
    #   原註解自陳「§4.5 全站已有多份複本」,結果同一檔又生一份 —— 改吃 L0 SSOT。
    _today_sb = _tw_now().date()
    _wd_sb = {0:'一',1:'二',2:'三',3:'四',4:'五',5:'六',6:'日'}[_today_sb.weekday()]
    _trade_sb = '✅ 交易日' if _today_sb.weekday() < 5 else '❌ 非交易日'
    st.caption(f'{_today_sb.strftime("%Y/%m/%d")} 週{_wd_sb}  {_trade_sb}')
    # FIX(誠實性): 移除兩段與實際狀態無關的側欄顯示 ——
    #   (1)「### 🤖 AI 分析 / 頁面底部有 AI 整合報告面板」:該面板已不存在。
    #       AI 現在住在「🧬 AI 問答」主頁籤,原指路會把使用者送到頁尾免責聲明。
    #   (2) `st.success('🟢 系統正常運作中')`:硬編碼常數,不讀任何狀態,且印在下方
    #       「🔌 連線狀態」三顆真燈**上方** —— FinMind/Gemini/Proxy 全紅時第一眼仍是綠。
    #       真實狀態由下方 `_fm_tok / _gm_keys / _px_host` 三顆燈負責,不需要這句。
    #   附帶移除 `ai_run = False`(全 repo 僅此 1 處、零 consumer,含 tests)。

    # ── Google 帳號（OAuth）— ETF 組合雲端存取用 ─────────────────
    st.markdown('---')
    st.markdown('### 🔐 Google 帳號')
    try:
        from src.data.portfolio.oauth_state import (
            get_oauth_cfg as _sb_get_cfg,
            login_state_with_sheet as _sb_login_state_with_sheet,
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
            # ── Google Sheet ID（集中於帳號區；亦可於「📁 組合管理」頁設定）──
            _sb_sid_cur = str(st.session_state.get('portfolio_sheet_id', '') or '').strip()
            _sb_sid_raw = st.text_input(
                'Google Sheet ID 或完整 URL（系統會自動解析 ID）',
                value=_sb_sid_cur, key='sb_portfolio_sheet_id_input',
                placeholder='貼上 https://docs.google.com/spreadsheets/d/...',
                help='貼 URL/ID 設定投組資料庫（或在「📁 組合管理」頁設定）')
            _sb_m = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', _sb_sid_raw)
            _sb_sid_new = _sb_m.group(1) if _sb_m else _sb_sid_raw.strip()
            if _sb_sid_new and _sb_sid_new != _sb_sid_cur:
                # A(v19.204 順暢化):側欄設 Sheet 也走「ETF+個股兩通道 + ?sheet= 持久化」,
                # 與 📁 組合管理 的 _apply_active_sheet 一致 —— 否則從側欄設的 Sheet 不持久
                # (重整就沒了)、也漏設個股通道(個股組合讀不到)。稽核抓到的不對稱,補齊。
                st.session_state['portfolio_sheet_id'] = _sb_sid_new
                st.session_state['stock_portfolio_sheet_id'] = _sb_sid_new
                try:
                    st.query_params['sheet'] = _sb_sid_new
                except Exception:  # noqa: BLE001 — query param 寫入失敗不擋設定
                    pass
            if _sb_sid_new:
                st.caption(f'✅ Sheet ID：`{_sb_sid_new}`')
            else:
                st.caption('💡 未設定 — 貼上 URL/ID（或在「📁 組合管理」頁設定）')
        elif _sb_buildurl and _sb_cfg:
            # P2(v19.206):把目前(若曾綁過 / 由書籤 ?sheet= 還原的)Sheet ID 夾帶進登入 state
            # → Google 轉跳回來自動回綁,不必再繞 📁 組合管理。Sheet ID 非憑證(§ P2 安全前提)。
            _sb_cur_sid = str(st.session_state.get('portfolio_sheet_id', '') or '')
            _sb_url = _sb_buildurl(_sb_cfg['client_id'], _sb_cfg['redirect_uri'],
                                   state=_sb_login_state_with_sheet(_sb_cur_sid))
            st.link_button('🔐 用 Google 登入', _sb_url, use_container_width=True)
            st.caption('登入後可在「📁 組合管理」頁雲端存取')
    elif _sb_gsa and _sb_sid:
        st.caption('ℹ️ 使用 Service Account（舊版部署）')
    else:
        st.caption('⚙️ OAuth 尚未設定 — 需於部署端 secrets.toml 設定 [google_oauth]（或改用 Service Account）')

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

# ── 旌旗指數 = 上漲佔比(ad_ratio) 的 5 日移動平均（src/services/jingqi_calc.py）──
#    FIX(§3.3 反捏造): 原註解寫「站上 MA20/MA60/MA120/MA240 的家數比例」——
#    全站沒有任何一行 code 在算站上均線家數比。同一個錯誤定義已在
#    shared/macro_buckets.py(v19.177 P1-B) 與 section_overview.py 正名退役,此處為漏網。
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

# ══════════════════════════════════════════════════════════════
# 🧭 核心總表（E1 v19.185）— 此處只「佔位」，內容延後到所有 tab render 完才填
# ══════════════════════════════════════════════════════════════
# 【版面】使用者要求「頂層放核心總表提供最高階整體概況與 KPI，下方才是依業務邏輯
#   分類的詳細數據」→ 佔位建立在標題正下方、總經指南針與 tabs **之上**。
# 【時序】內容**不能**在這裡算。本段是 module level，執行順序早於 `with tab_x:`，
#   而總表要用的 `warroom_summary` / `macro_alerts` / `li_latest` / `t3_data`
#   全是 tab render 期間才寫入 session_state 的；加上「🚀 一鍵更新全部數據」的
#   on_click callback 會先 pop 掉 `warroom_summary`，在這裡算必然全部讀到空值 →
#   總表會 100% 複製 v19.171 🔴-1 那個「置底紅綠燈永遠停在 ⬜ 未評估」的實機事故
#   （見下方 `_gl_slot` 的完整病史）。
#   故沿用同一套 placeholder 模式：`st.empty()` 現在佔住版面位置，
#   實際內容由檔案最後的填充區塊寫入（那時 tab 都 render 完了）。
_core_summary_slot = st.empty()

# ══════════════════════════════════════════════════════
# 🔗 我的組合 — 全域綁定狀態列(P3a v19.207 順暢化):把「選 Sheet」從必經分頁
# (📁 組合管理)提升為標題下常駐的全域狀態,點開就地綁定,去「先繞組合管理」心智模型。
# 分頁結構不動。L6 掛 L5 render(向下,合規)。
# ══════════════════════════════════════════════════════
from src.ui.tabs.portfolio_status_bar import render_portfolio_status_bar  # noqa: E402
render_portfolio_status_bar()

# ══════════════════════════════════════════════════════
# 🧭 總經指南針 — render_macro_compass 已抽至 src/ui/render/app_render.py
# (v18.404 U5 B3-γ);_render_compass_card 同步搬走(internal helper)
# ══════════════════════════════════════════════════════
from src.ui.render.app_render import render_macro_compass  # noqa: E402
render_macro_compass()

# v18.182 ARCHIVED: 🧪 回測找參數 / v18.187 ARCHIVED: 📈 月營收進退 / v18.189 ARCHIVED: 📊 財報體檢變化
# 各暫封存模組保留磁碟，啟用方式見各 ARCHIVED 原始注解。
# v18.463: UI 重構 — 10 平鋪 Tab → 4 大群組 + Sub-tabs（sub-tab 變數名稱維持不變，測試仍通過）
tab_market, tab_stocks, tab_etf_main, tab_tools, tab_warroom, tab_mgmt, tab_ai = st.tabs([
    '🌍 市場環境', '🔬 選股', '🏦 ETF', '🔧 工具箱', '💼 我的持股戰情室', '📁 組合管理', '🧬 AI 問答',
])

# ══════════════════════════════════════════════════════════════
# 全域多空紅綠燈（Tab 外，永遠可見）
# ══════════════════════════════════════════════════════════════

# ── 全域置底常駐條：此處只「佔位」，內容延後到所有 tab render 完才填 ──────
# v19.171 🔴-1（線上實機驗收 2026-08-05 抓到，非偶發）：
#   本段原本在此就把整條 bar 算完並印出，但它是 **module level**，執行順序早於
#   `with tab_market:` 內的 `render_traffic_light_top()` —— 而 `warroom_summary`
#   （`get_allocation()` 取 health / regime 的來源）正是在那裡才寫入。
#   再加上「🚀 一鍵更新全部數據」的 on_click callback
#   (`src/ui/tabs/macro/handlers.py::_macro_session_reset`) 會 **pop 掉**
#   `warroom_summary`，於是更新後的那一次 rerun，這裡必然讀到空 →
#   `get_macro_state` 的 `_wr_ok=False` → `is_loaded=False` → 顯示
#   「⬜ 總經未評估 / 建議持股 --」，而同一畫面下方的 tab 內容卻已是
#   「最終建議持股 20%」。使用者不再操作就沒有下一次 rerun →
#   **置底條實質永遠停在「未評估」**（市場環境頁與 ETF 頁同時複現）。
#
# 修法（Streamlit placeholder 模式）：
#   `st.empty()` 在**建立當下**就佔住版面位置（仍在 tabs 區塊之後、頁尾免責聲明
#   之前），實際內容改由檔案最後的填充區塊寫入 —— 此時所有 tab 都已 render 完，
#   `warroom_summary` 已是本輪最新值。計算邏輯（get_allocation / 時效閘 /
#   traffic_light / 旌旗均值）一字未改，**只是執行時機延後**，視覺位置不變。
_gl_slot = st.empty()

# ══════════════════════════════════════════════════════════════
# AI 總經戰情 — 新聞抓取已抽至 src/data/news/(v18.398 P5-B3-β R8)
# caller 改走 `from src.data.news import fetch_macro_news, fetch_stock_news`
# ══════════════════════════════════════════════════════════════


# F2(2026-08):`_build_llm_context` 已下沉 L3
# → `src/services/app_ai_service.py::build_llm_context`(邏輯一字未改)。
# 它組 LLM prompt 上下文 = L3 職責,住在 L6 是 CLAUDE.md V-APP-1 點名的違憲之一。
# ⚠️ 順帶查證結果:它**0 個 production caller**(AST 全 repo 掃描)。F2 只搬家不刪,
#    是否刪除留給 user 裁示(§-1)。


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
    tab_macro, tab_heatmap, tab_sector_flow = st.tabs(
        ['🌍 總經', '🗺️ 產業熱力圖', '🌊 板塊資金潮汐'])

    with tab_macro:
        from src.ui.tabs import render_tab_macro
        _render_tab_isolated(render_tab_macro, '總經')

    with tab_heatmap:
        # B4-b H-9:本 tab 原為全 app 唯一未包隔離器者,任何例外(例:色階
        # max() 空序列 ValueError)會白掉整頁。對齊鄰居「總經」寫法。
        _render_tab_isolated(
            lambda: render_sector_heatmap(gemini_fn=gemini_call), '產業熱力圖')

    with tab_sector_flow:
        # 板塊資金泡泡圖 Stage 2:讀 L3 sector_flow_service(L1 本地快取 + L2 持股對映)
        # → L4 泡泡圖。與「產業熱力圖」同屬市場/板塊視角,故並列於市場環境群組。
        from src.ui.tabs.tab_sector_flow import render_tab_sector_flow
        _render_tab_isolated(render_tab_sector_flow, '板塊資金潮汐')

# ══════════════════════════════════════════════════════════════
# GROUP 2: 選股（個股 + 個股組合 + 選股網）
# ══════════════════════════════════════════════════════════════
with tab_stocks:
    tab_stock, tab_stock_grp, tab_screener = st.tabs(['🔬 個股', '📊 多檔個股比較', '🔭 選股網'])

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
        from src.ui.tabs.tab_stock_picker import (
            render_prescreen_panel, summarize_factor_hits,
        )
        from src.ui.tabs.yield_screener import fetch_pe_name_maps
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
            # 上市(TWSE BWIBBU) + 上櫃(TPEX peratio) 合併 → 上櫃股也有估值分 + 名稱
            # (原僅 TWSE:上櫃股 pe_low None、名稱空白)。SSOT 見 fetch_pe_name_maps。
            _pe_map, _name_map = fetch_pe_name_maps()
            # v19.147:改走 L3 get_ranked_picks（畫面/cron 同源，保證自動凍結清單=畫面清單）。
            # auto_fetch=False = 只用 session 已快取的掃描結果（掃描仍由上方「開始選股」按鈕觸發），行為不變。
            # T1-a(2026-08)「總經 → 全系統風控」接線：把 canonical regime 傳進選股引擎。
            #   此前 fundamental_screener_service 全檔零 regime 引用 —— 總經顯示「空頭防禦」
            #   時，選股網照樣用同一組門檻選出同一批股票（流程圖層次 1 那支箭頭在此是斷的）。
            #   regime ∈ {bear, caution} → 剔除區間報酬未贏過大盤的候選；其餘不變。
            #   取不到就傳 None（= 不套用），並由 service 端在 note 明講「未套用」（§1）。
            #   ⚠️ 只有**畫面**傳 regime；凍結 cron / MCP / 推播三處維持 None ——
            #     前進式驗證要的是「當下真實決定」的跨期可比性，濾網改變凍結內容會破壞它。
            try:
                from src.services.allocation_service import get_macro_regime as _gmr
                # ⚠️ get_macro_regime() 回的是 dict 契約(regime/light/is_loaded…),
                # 不是字串。選股濾網只吃「regime 字串」,且僅在總經**已評估**時套用
                # (§1:未評估→None,不套用、不捏造多空)。此前誤把整個 dict 當 regime 傳,
                # 到 `_apply_bear_market_filter` 的 `regime not in frozenset` → TypeError
                # (dict unhashable),選股網一按就炸。
                _reg_state = _gmr()
                _screen_regime = (_reg_state.get('regime')
                                  if isinstance(_reg_state, dict)
                                  and _reg_state.get('is_loaded') else None)
            except Exception as _e_reg:  # noqa: BLE001 — 總經取不到不該炸掉選股
                _screen_regime = None
                print(f'[screener] regime 取得失敗，不套用空頭濾網: '
                      f'{type(_e_reg).__name__}: {_e_reg}')
            _cands, _cnote = get_ranked_picks(
                _factors, top_n=300, survivors_df=_surv_df,
                pe_map=_pe_map, name_map=_name_map,
                shortage_rows=st.session_state.get('_shortage_rows'),
                rs_rows=st.session_state.get('_rs_rows_all'),  # v19.90 全存活池 RS（非 top-50）
                trend_map=st.session_state.get('_trend_map'),  # A-2 v19.140 跨季轉強
                auto_fetch=False,
                regime=_screen_regime)
            if _cnote:
                st.info(_cnote)
            st.markdown('#### ③ 選股結果（綜合評分排序）')
            _surv_n = len(_surv_df) if _surv_df is not None else 0
            if _cands.empty:
                st.info('目前沒有符合的標的（請至少勾一個條件；缺貨/抗跌RS 需能連上資料源）。')
            else:
                # 🔭 選股結果總覽卡(v19.167:一眼看命中,對稱個股 🧭 / ETF 🚦 頁頂卡)。
                # 命中數只在該因子有掃到結果(session 值存在)時顯示,§1 掃失敗不假報 0。
                #
                # ── H2 2026-08:三個裸 len() 冠「命中」全部名不副實,改吃 SSOT tier ──
                # 舊碼:`缺貨命中 {len(_shortage_rows)}` / `抗跌RS {len(_rs_rows_all)}` /
                #      `跨季轉強 {len(_trend_map)}`。三個分母全被當成分子印出去:
                #   - _shortage_rows 含 TIER_WEAK「⬜ 不明顯」→ 是被評分數不是命中數
                #   - _rs_rows_all 走 beat_only=False → 含「同步大盤 / 落後大盤」,不是抗跌數
                #   - _trend_map 含 favorable_count==0 的檔 → 是「可算檔數」≈ 全市場 ~2000
                # 計數邏輯抽 `tab_stock_picker.summarize_factor_hits`(純函式,可單測);
                # 分子一律用既有 tier SSOT 邊界,不新增門檻;分子/分母同時顯示。
                _hit_bits = summarize_factor_hits(
                    _factors,
                    shortage_rows=st.session_state.get('_shortage_rows'),
                    rs_rows=st.session_state.get('_rs_rows_all'),
                    trend_map=st.session_state.get('_trend_map'),
                )
                _hit_txt = ' · '.join(_hit_bits) if _hit_bits else '僅基本面四項全過'
                st.markdown(
                    f'<div style="background:#0d1117;border:2px solid #3fb950;border-radius:10px;'
                    f'padding:12px 16px;margin:4px 0 10px;">'
                    f'<span style="font-size:18px;font-weight:900;color:#3fb950;">'
                    f'🔭 存活池 {_surv_n} 檔 → 綜合入選前 {min(len(_cands), 50)} 名</span>'
                    f'<span style="font-size:12px;color:#8b949e;margin-left:10px;">'
                    f'本次因子:{_hit_txt}</span></div>', unsafe_allow_html=True)
                st.dataframe(_cands.head(50), hide_index=True, use_container_width=True)
                _csv = _cands.head(50).to_csv(index=False).encode('utf-8-sig')
                st.download_button('💾 下載選股結果 CSV', data=_csv,
                                   file_name='screener_result.csv', mime='text/csv',
                                   key='screener_csv')
                # ── ☑️ 加入觀察清單（選股池閉環 #33）：勾選 → 併入你的觀察清單 ──
                st.markdown('##### ☑️ 加入觀察清單（選進你的池子 → 💼 戰情室追蹤 + 換股建議換入）')
                _add_opts = [f"{r['代碼']} {r.get('名稱', '')}".strip()
                             for _, r in _cands.head(50).iterrows()]
                _add_pick = st.multiselect('勾選要加入的標的（可多選）', _add_opts,
                                           key='screener_add_watch_pick')
                from src.services.watchlist_service import (
                    add_picks_to_watchlist, get_watchlist_add_context)
                _stk_sid_add, _wl_names = get_watchlist_add_context()
                if not _stk_sid_add:
                    # 2026-08 UX 修:原本這裡只印說明、把「加入」按鈕整個藏掉 → user 看到
                    # 有勾選框卻沒有按鈕,以為「少了加入選股池的按鈕」。改成按鈕照樣顯示
                    # (disabled 灰態 + tooltip),明講要先在 組合管理 選個股清單 Sheet。
                    st.button('➕ 加入觀察清單', key='screener_add_watch_go_disabled',
                              type='primary', disabled=True,
                              help='需先在 📁 組合管理 選定「個股清單 Sheet」才能加入 —— '
                                   '設定後這顆按鈕就會啟用。')
                    st.caption('（需先在 📁 組合管理 選定個股清單 Sheet,才能加入觀察清單。）')
                else:
                    _NEW_WL = '＋ 新建清單'
                    _wl_sel = st.selectbox('加到哪份觀察清單', _wl_names + [_NEW_WL],
                                           key='screener_add_watch_name')
                    _wl_final = (st.text_input('新清單名稱', key='screener_add_watch_new',
                                               placeholder='例：選股池')
                                 if _wl_sel == _NEW_WL else _wl_sel)
                    if st.button('➕ 加入觀察清單', key='screener_add_watch_go', type='primary'):
                        _codes_add = [p.split()[0] for p in _add_pick]
                        if not _codes_add:
                            st.warning('請先勾選標的。')
                        elif not (_wl_final or '').strip():
                            st.warning('請選或填觀察清單名稱。')
                        else:
                            try:
                                _n_wl = add_picks_to_watchlist(_wl_final.strip(), _codes_add)
                                st.success(f'✅ 已把 {len(_codes_add)} 檔加入「{_wl_final.strip()}」'
                                           f'（現共 {_n_wl} 檔）。到 💼 戰情室按 🔄 重新載入即生效。')
                            except Exception as _e_add:  # noqa: BLE001 — §1 失敗誠實報
                                st.error(f'加入失敗：{type(_e_add).__name__}: {_e_add}')
                # ── 🧊 前進式驗證：凍結本次選股（FT-2 v19.142）→ 存 Google Sheet，日後對帳 vs 0050 ──
                st.markdown('##### 🧊 前進式驗證：凍結本次選股')
                st.caption('把前 20 名凍結存進你的 Google Sheet（含當下進場價 + 勾選因子），'
                           '日後對帳看這套選股實際贏不贏 0050 —— 零 lookahead、零存活者偏誤。')
                from src.services.forward_test_service import (
                    freeze_current_picks, is_freeze_available)
                if not is_freeze_available():
                    st.info('⚪ 需先在側欄「🔐 Google 帳號」貼上 Google Sheet ID（或在「📁 組合管理」頁設定），才能凍結存檔。')
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

# v19.163 財報體檢轉機併進 🏆 個股組合 Tab(批次)、目標價區間內嵌 🔬 個股 + 🏆 組合;
# 皆不設獨立分頁(user 要求「都合併在個股與組合中,不需要開立新的 tab」)。
# ══════════════════════════════════════════════════════════════
# GROUP 3: ETF（單檔診斷 + 多檔比較 + ETF 組合）
# v18.464: 移除質借模擬 Tab；新增標準差買賣帶 + 分散度分析到單檔 & 組合
# v18.465: 新增 3-3-3 原則評估（成立>3年 / 3年年化>7% / 同儕前1/3）
# ══════════════════════════════════════════════════════════════
with tab_etf_main:
    tab_etf, tab_etf_compare = st.tabs([
        '🔍 單檔診斷', '📊 多檔比較',
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
        # FIX(隔離器): ETF 三頁原為裸呼叫,是全站唯一沒有隔離保護的一組。
        _render_tab_isolated(
            lambda: render_etf_single(gemini_fn=gemini_call, before_ai_hook=_etf_single_smart),
            'ETF 單檔診斷')

    with tab_etf_compare:
        from src.ui.etf import render_etf_grp_compare
        _render_tab_isolated(render_etf_grp_compare, 'ETF 多檔比較')

    # 🔬 ETF 深度工具已於 P3 v19.202 搬入 💼 我的持股戰情室(user 指派「輸入持股組合分析全移到戰情室」):
    #   • 組合(再平衡/核衛80-20/壓測/VaR/效率前緣/配息現金流/稅後)+ 葡萄串領息
    #       → 戰情室「5️⃣ 📊 組合深度分析」(輸入改吃 📁 組合管理持股,見 portfolio_analysis_bridge);
    #   • 3-3-3 / 標準差帶 / 分散度 → 與 🔍 單檔診斷(上方 _etf_single_smart)逐字重複,不再於多檔比較重出;
    #   • ETF AI 研判 → 戰情室已有「6️⃣ 🤖 AI 戰情總結」等價功能。
    # 多檔比較僅保留 render_etf_grp_compare(7 維評分表)本體,回歸乾淨。

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
        # v19.168 IMPL-E:使用者版 —— 資料覆蓋率/新鮮度總覽常駐(一般使用者只需看這張燈號表)。
        # FIX(隔離器): 原為裸呼叫,本頁任一例外會炸掉整個 app。補上與其他 tab 一致的隔離。
        _render_tab_isolated(render_data_coverage, '資料診斷')
        # v19.168 IMPL-E:工程師版 —— 資料源清單 / Fetcher 監控 / §4.3 雙演算法對帳 / API 根因 /
        # 原始資料表 / 門檻校準,全對照 CLAUDE.md §編號、談 SSOT/proxy/@monitored,一般使用者用不到,
        # 收進折疊、預設隱藏(不刪 —— 診斷仍在,只是不干擾主畫面)。
        with st.expander(
                '🔧 進階診斷（工程師用；一般使用者不需要打開）',
                expanded=False):
            # FIX(效能): st.expander(expanded=False) 只收合**視覺**,body 每次 rerun 仍會完整執行。
            #   原本 6 個 panel 無條件跑:render_data_registry_panel 每次組 50+ 筆 HTML、
            #   render_data_health_raw 內另有未受 button 保護的 per-ETF 外抓(MoneyDJ/SITCA)。
            #   改為 checkbox gate —— 預設不執行,要看才載入。診斷內容一項未刪。
            if st.checkbox(
                    '載入進階診斷（較耗時，部分項目會實際打外部 API）',
                    key='_diag_adv_on',
                    help='資料源清單 · Fetcher 監控 · §4.3 對帳 · API 根因 · 原始表 · 門檻校準'):
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

# ── 💼 我的持股戰情室（v19.x 提升為頂層分頁,原為 ETF 子分頁;user 2026-08）──────
#   標的唯一來源 = 📁 組合管理(自動載入、唯讀),個股+ETF 統一健檢/235/3-3-3
#   + 🔄 換股建議(搭配總經位階) + 🤖 AI 戰情總結(可推播)。
with tab_warroom:
    from src.ui.etf.etf_tab_dividend_station import render_dividend_station
    _render_tab_isolated(lambda: render_dividend_station(gemini_fn=gemini_call),
                         '我的持股戰情室')

# ── 📁 組合管理（統一頁:ETF 組合 + 個股清單,存 Google Sheet）──────────
with tab_mgmt:
    from src.ui.tabs.portfolio_manager import render_portfolio_manager
    _render_tab_isolated(render_portfolio_manager, '組合管理')

# ── 🧬 AI 問答（v19.121 Phase 1，L5→L3 ai_qa_service）──────────────
with tab_ai:
    from src.ui.tabs import tab_ai_chat
    _render_tab_isolated(tab_ai_chat.render, 'AI 問答')

# ══════════════════════════════════════════════════════════════
# 🧭 核心總表 — 延後填充（E1 v19.185）
# ══════════════════════════════════════════════════════════════
# 執行時機：所有 `with tab_*:` 都已 render 完 → `warroom_summary` / `macro_alerts`
#   / `li_latest` / `t3_data` 都是本輪最新值。渲染位置：上方 `_core_summary_slot`
#   （頁面最頂端），使用者看到的是「總表在最上面、詳細數據在下面」。
#
# `compute_tab_coverage()` 在**這裡**呼叫而不是在 L3 service 內：
#   它住在 `src/ui/pages/data_coverage.py`（L5），而 §8.2 硬規則禁止 L3 import L5。
#   若讓 L3 自己再寫一份覆蓋率算法，就會出現「同一個量兩個實作、兩個答案」——
#   正是核心總表要消滅的缺陷。改由 L6（同時合法看得見 L5 與 L3）注入，
#   依賴方向 L6→L5、L6→L3，零上行 import。長期正解是把該函式的純計算部分
#   下沉 L2 由兩者共用（該檔不在 E1 可改範圍）。
#
# ⚠️ 本段**不得**觸發任何 fetch：`compute_tab_coverage()` 純讀 session_state，
#   `get_core_summary()` 只讀 session_state + macro_state.json。沒算過的 KPI
#   一律顯示「⬜ 未評估 + 怎麼補」，絕不順手幫使用者抓資料（那會把原本
#   button-gated 的抓取路徑變成無條件執行）。
try:
    from src.services.core_summary_service import get_core_summary
    from src.ui.pages.data_coverage import compute_tab_coverage
    from src.ui.render.core_summary_render import render_core_summary

    try:
        _cs_rows = compute_tab_coverage()
    except Exception as _cs_cov_err:  # noqa: BLE001 — 覆蓋率壞掉只讓那兩格 ⬜
        print('[app/核心總表] compute_tab_coverage() 失敗，'
              f'覆蓋率/新鮮度兩格降為未評估：{type(_cs_cov_err).__name__}: {_cs_cov_err}')
        _cs_rows = None

    with _core_summary_slot.container():
        render_core_summary(get_core_summary(coverage_rows=_cs_rows))
except Exception as _cs_err:  # noqa: BLE001 — module level，不得讓它炸掉全站
    import traceback as _tb_cs
    print(f'[app/核心總表] 組裝失敗：{type(_cs_err).__name__}: {_cs_err}')
    _tb_cs.print_exc()
    # §1 Fail Loud：失敗要看得見，且說得出是哪一種例外 —— 不留白、不假裝正常。
    _core_summary_slot.error(
        f'❌ 核心總表組裝失敗（{type(_cs_err).__name__}）：'
        f'{str(_cs_err)[:200]} —— 其餘分頁不受影響。')

# ══════════════════════════════════════════════════════════════
# 全域置底常駐條 — 延後填充（v19.171 🔴-1）
# ══════════════════════════════════════════════════════════════
# 執行時機：所有 `with tab_*:` 都已 render 完 → `warroom_summary` /
#   `mkt_info` / `jingqi_info` / `cl_ts` 都是**本輪最新值**，不再是被
#   `_macro_session_reset()` on_click callback pop 掉的空值。
# 渲染位置：填進上方的 `_gl_slot`（建立於 tabs 區塊之後、頁尾之前）→
#   使用者看到的位置與 v19.170 完全相同（tab 內容下方、免責聲明上方）。
# ⚠️ gate 用的 `_mkt_top` / `_jq_top` / `_ts_top` 必須**在這裡重新讀**：
#   module-level 讀到的是 tab render 之前的舊值（refresh 那一輪甚至是空 dict），
#   沿用舊值就等於沒修。
_mkt_top  = st.session_state.get('mkt_info', {})
_jq_top   = st.session_state.get('jingqi_info', {})
_ts_top   = st.session_state.get('cl_ts', '')
if (_mkt_top or _jq_top) and not st.session_state.get('_is_refreshing', False):
    # FIX(§1 反捏造): 原為 `_jq_top.get('avg', 50)` —— jingqi_info 存在但缺 'avg' 鍵時
    #   會憑空印出「旌旗均值 50%」,而 50 正好是最不容易被察覺的中性值。
    #   下方 L937 已有 `if _jqpct is not None` 守衛,拿掉 default 即自動改為「不顯示」。
    #   同型問題 section_overview.py 已於稍早修正(改 .get('avg', None) 並註明是 §1 違憲),
    #   本處是當時的漏網第二處。
    _jqpct = _jq_top.get('avg') if _jq_top else None
    # v19.170 P0-1:燈號 label 與持股% 全部改讀建議持股 SSOT(get_allocation)——
    # 原本 label 自行看 mkt_info.regime + jingqi_info.avg;持股% 則是
    # warroom_summary['throttle'](v19.168 SSOT,會被 section_state 整包覆寫抹掉)
    # → mkt_info['exposure_pct'] → 硬編碼 80/50/20 三層 fallback,與 🎚️ 建議持股油門 /
    # 三環 / VIX 否決權 打架(稽核 P0-1 六套結論之一)。現在全站只剩 get_allocation()
    # 一個出處,且已內含「姿態 vs 硬否決取較低」規則。
    # v19.170 🟡-1 防白屏:本段仍是 module level(v19.171 只是移到 tab 之後),
    # **不受 _render_tab_isolated 保護** —— get_allocation() 任何 raise
    # (macro_state.json 壞、session 型別異常、下游 import 失敗…)都會直接白屏全站。
    # 改為 try/except 兜住並降級為「⬜ 總經未評估」;錯誤原文 + traceback 一律
    # print 出來(§1:要留跡,不吞掉錯誤訊息)。
    try:
        from src.services.allocation_service import get_allocation
        _alloc = get_allocation()
    except Exception as _alloc_err:  # noqa: BLE001 — module level,不得讓它炸掉全站
        import traceback as _tb_alloc
        print('[app/置底紅綠燈] get_allocation() 失敗，降級為「總經未評估」：'
              f'{type(_alloc_err).__name__}: {_alloc_err}')
        _tb_alloc.print_exc()
        _alloc = None

    _gl_pos = _alloc.range_text if _alloc is not None else '--'
    if _alloc is None or not _alloc.is_loaded:
        # §1 Fail Loud:總經未評估(或取數失敗)→ 誠實顯示未評估,
        # 不回填任何多空結論或預設持股%
        _gl_color, _gl_label = '#8b949e', '⬜ 總經未評估'
    else:
        # 綜合信號(多空判斷與持股% 同源,不再各算各的)
        _gl_color, _gl_label = traffic_light(
            None,
            _alloc.regime == 'bull',
            _alloc.regime == 'bear',
            f'多頭市場（{_alloc.posture}）', f'空頭市場（{_alloc.posture}）',
            f'🟡 {_alloc.regime_text}（{_alloc.posture}）',
        )
        # 被硬否決壓低時,label 後面直接掛上生效的天花板,避免「多頭」與低持股% 看似矛盾
        if _alloc.capped:
            _gl_label = f'{_gl_label}&nbsp;<span style="font-size:12px;">{_alloc.cap_text}</span>'

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

    # v19.171:唯一差異 —— 由 `st.markdown(...)` 改為 `_gl_slot.markdown(...)`,
    # 內容寫回上方預留的位置(視覺位置不變)。
    _gl_slot.markdown(
        f'<div style="background:#0d1117;border:1px solid {_gl_color};border-radius:8px;'
        f'padding:8px 14px;margin-bottom:8px;display:flex;align-items:center;gap:16px;">'
        f'<span style="font-size:16px;font-weight:900;color:{_gl_color};">{_gl_label}</span>'
        f'{_mid_html}'
        f'<span style="font-size:11px;color:#484f58;margin-left:auto;">更新：{_ts_top}</span>'
        f'</div>', unsafe_allow_html=True)

st.markdown('<div style="text-align:center;font-size:10px;color:#484f58;padding:8px 0;">⚠️ 台股AI戰情室 v3.0 · 僅供學術研究，非投資建議，盈虧自負</div>', unsafe_allow_html=True)
