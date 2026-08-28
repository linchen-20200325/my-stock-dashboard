"""
台股 AI 戰情室 v3.0 集中設定檔 (§11) — 優化版
整合分析建議：ATR停損、Sharpe動能、時間停損、滑價修正
"""

# ── 市場判斷閾值 ──────────────────────────────────────────────
MARKET_SCORE_BULL    = 3     # 總分 >= 3 判定為多頭
MARKET_SCORE_NEUTRAL = 2     # 總分 == 2 判定為中性

# ── 均線參數 ──────────────────────────────────────────────────
MA_SHORT  = 20
MA_MID    = 60
MA_LONG   = 120
MA_ANNUAL = 240   # 年線

# ── 風控參數（優化版）────────────────────────────────────────
MAX_POSITION_PER_STOCK  = 0.10   # 單股最大持倉比重 10%
MAX_PORTFOLIO_DRAWDOWN  = 0.15   # 最大回撤 15%，超過暫停交易
STOP_LOSS_PCT           = 0.08   # 固定停損 -8%（ATR模式下為備援）
TRAILING_STOP_PCT       = 0.07   # 移動停利回撤 7%
MIN_CASH_RATIO          = 0.10   # 現金部位下限 10%
MAX_POSITIONS           = 10     # 最大持股檔數

# ── ATR 動態停損參數（§優化1）────────────────────────────────
ATR_PERIOD     = 14      # ATR 計算週期（天）
ATR_MULTIPLIER = 1.5     # 停損距離 = Entry - (N × ATR14)，N=1.5~2.0

# ── 時間停損參數（§優化5：防止資金被套）────────────────────
TIME_STOP_DAYS      = 15    # 買進後超過 15 天
TIME_STOP_MIN_GAIN  = 0.02  # 若報酬未達 +2% → 強制換股

# ── 動態因子權重表（依市場狀態自動切換，6 因子 SSOT）──────
# 唯一權重來源；scoring_engine.stock_score 由此讀取。
# bull：趨勢/動能加重，進攻型；bear：風險/基本面加重，防禦型
WEIGHT_TABLES = {
    'bull': {
        'trend': 0.30, 'momentum': 0.25, 'chip': 0.20,
        'volume': 0.15, 'risk': 0.05, 'fundamental': 0.05,
    },
    'neutral': {
        'trend': 0.25, 'momentum': 0.20, 'chip': 0.20,
        'volume': 0.15, 'risk': 0.10, 'fundamental': 0.10,
    },
    'bear': {
        'trend': 0.15, 'momentum': 0.10, 'chip': 0.15,
        'volume': 0.15, 'risk': 0.25, 'fundamental': 0.20,
    },
}

# ── §4.2 權重和不變量（v19.105,import 時 fail loud）─────────────
# 三態 6 因子權重各自和必須 = 1.0；日後手調任一權重忘了配平,app 啟動即炸並指名
# 哪一態,而非讓 stock_score 加權總分悄悄整體縮放（§1 寧可炸掉,不可造假）。
import math as _math  # noqa: E402

for _wt_regime, _wt in WEIGHT_TABLES.items():
    if not _math.isclose(sum(_wt.values()), 1.0, abs_tol=1e-9):
        raise ValueError(
            f"WEIGHT_TABLES['{_wt_regime}'] 6 因子權重和 = {sum(_wt.values()):.4f} ≠ 1.0"
            "（§4.2 權重未歸一）— 請先配平再啟動"
        )
del _wt_regime, _wt

# ── 選股篩選條件 ──────────────────────────────────────────────
TOP_N_STOCKS    = 10
RSI_OVERBOUGHT  = 70
RSI_OVERSOLD    = 30
MIN_LIQUIDITY   = 500

# ── 市場曝險比例（依 market_regime）────────────────────────
EXPOSURE_BULL    = 0.80   # 多頭：80% 持股
EXPOSURE_NEUTRAL = 0.50   # 中性：50% 持股
EXPOSURE_BEAR    = 0.20   # 空頭：20% 持股

# ══════════════════════════════════════════════════════════════════
# 韭菜指數門檻 SSOT（v19.176 P0-D）
# ══════════════════════════════════════════════════════════════════
# ⚠️ §4.1 量綱陷阱 —— 本系統有**兩個都叫「韭菜指數」但單位完全不同**的東西，
#    兩者的門檻**絕對不可互換、不可統一成同一個數字**：
#
#  (A) 融資餘額 5Y 標準化指數  ── 值域 [0, 100]，中位 50
#      定義：((融資餘額 − μ_5Y) / σ_5Y + 2) / 4 × 100   （見 tab_edu.py:955-970）
#      校準：歷史頂峰對照表 2000/4=48、2007/10=42、2018/1=38、2021/11=45、
#            2024/7=35；底部 2009/3=8（tab_edu.py:974-986）
#      門檻：LEEK_HIGH_THRESHOLD / LEEK_LOW_THRESHOLD（見下）
#      ⚠️ 現況：**全 repo 無任何 code 產生此數列**（無融資 Z-score fetcher），
#         故這組門檻目前 0 consumer。保留為「教材/未來接線」用，
#         **禁止**拿去比對 (B) 的值 —— 那是拿 0~100 的指數去比 ±% 的比值。
#
#  (B) 小台法人空多比（線上畫面「韭菜指數」欄實際顯示的那個）── 值域約 [-100, +100]，中位 0
#      定義：(法人空方 MTX OI − 法人多方 MTX OI) / 小台全體 OI × 100
#            （leading_indicators.py:648-726；FinMind 備援版見同檔 :1533-1558）
#      正值 = 散戶被迫站多方（危險）；負值 = 散戶淨空（機會）
#      門檻：下方 LEEK_ALERT_* / LEEK_SCORE_* / LEEK_PIVOT_*
#
# 為什麼 (B) 有三組門檻而不統一：三個判定的**用途與敏感度本來就不同**
# （進階警示 = 只喊極端值；綜合評分 = 要能對中度傾斜給分；拐點偵測 = 抓轉折）。
# 統一數字 = 行為變更，須 user 另行核准。**分別命名**是為了讓「同數字不同義」
# 不會在未來被誰看到重複值就順手合併（§3.3）。
# ──────────────────────────────────────────────────────────────────

# (A) 融資餘額 5Y 標準化指數 [0,100] —— ⚠️ 目前 0 consumer，見上方說明
LEEK_HIGH_THRESHOLD  = 35.0   # 超過此值 = 散戶過熱，警戒（0~100 指數，非 ±%）
LEEK_LOW_THRESHOLD   = 10.0   # 低於此值 = 散戶淨空，潛在機會（0~100 指數，非 ±%）

# (B-1) 進階警示卡（section_chips「訊號 2：韭菜指數極端值」）
#       用途：只在**極端值**喊話，門檻最寬 → 誤報成本高（會跳紅色警示卡）
LEEK_ALERT_HIGH_PCT  = 30.0    # 法人空多比 > +30% → 🔴 散戶過度樂觀（頂部訊號）
LEEK_ALERT_LOW_PCT   = -30.0   # 法人空多比 < -30% → 🟢 軋空動能極強（機會）

# (B-2) 籌碼綜合判斷評分（section_chips 頁尾「🎯 籌碼綜合判斷」計分）
#       用途：與期貨/PCR/外選/前五大並列**加減 1 分**，需對中度傾斜就有反應
#       → 門檻最敏感。正負不對稱是刻意的：法人空多比長期分布偏正
#         （散戶結構性站多方），故看空側（-5）比看多側（+10）更早給分。
LEEK_SCORE_HIGH_PCT  = 10.0    # > +10% → -1 分（散戶過熱）
LEEK_SCORE_LOW_PCT   = -5.0    # < -5%  → +1 分（散戶悲觀）

# (B-3) 拐點偵測六大面向（section_state「面向 5：外資期貨 + 散戶比」）
#       用途：抓**轉折**，敏感度取中；且對稱（拐點不預設方向偏好）
LEEK_PIVOT_HIGH_PCT  = 20.0    # > +20% → 頂部拐點警示
LEEK_PIVOT_LOW_PCT   = -20.0   # < -20% → 底部拐點機會


# ══════════════════════════════════════════════════════════════════
# 兩個「總經否決」判定的正式名稱 SSOT（v19.176 P0-D）
# ══════════════════════════════════════════════════════════════════
# 【修的是什麼】2026-08-05 實機同一次渲染，同一個名字「v4.0 總經否決權」
#   在同一頁給出相反結論：
#     §八 總經拼圖（section_mid）→ ✅ 無觸發
#     §三 籌碼    （section_chips）→ 🔴 紅燈「總經環境高風險」
#
# 【根因】兩者**根本不是同一個判定**，只是共用了同一個名字（命名衝突）：
#   - section_mid  的是 inline 規則集，看 VIX / 台灣 PMI / 美國核心 CPI /
#     台灣出口 YoY / NDC 燈號 —— **完全不看外資期貨**，也從未呼叫 v4 引擎。
#   - section_chips 的才是真正的 `V4StrategyEngine.check_macro_veto()`（L2 Task 2），
#     只看 VIX + 外資期貨口數。
#   當日 VIX < 30（基本面側不觸發）但外資期貨空單 < -20,000 口（v4 側紅燈），
#   兩邊各自都「算對了」，錯的是它們頂著同一個名字。
#
# 【處置】不合併判定（兩者輸入集不同、用途不同，合併=行為變更），
#   改為：① 正名，讓使用者看得出是兩件事；② 各自標明「看了什麼／沒看什麼」；
#   ③ 兩者結論不一致時**主動揭露**（§1：不一致本身必須可見，不可挑一個顯示）。
#
# ⚠️ 文案撰寫限制：SCOPE_NOTE 兩條字串會被塞進 `st.markdown(..., unsafe_allow_html=True)`
#   的 HTML span 裡，因此**不得**使用 `**粗體**`（HTML 區塊內的 markdown 不會被解析，
#   會原樣印出星號）與 `<` / `>`（瀏覽器可能誤判為標籤起始）。門檻一律用中文敘述。
VETO_FUNDAMENTAL_NAME = '總經基本面否決檢查'
VETO_FUNDAMENTAL_INPUTS = (
    'VIX 達 30／台灣 PMI 低於 48／美國核心 CPI 超過 4%／'
    '台灣出口 YoY 低於 -5%／NDC 燈號 16 分以下'
)
VETO_FUNDAMENTAL_SCOPE_NOTE = (
    f'本檢查只看【{VETO_FUNDAMENTAL_INPUTS}】—— 不含籌碼面（外資期貨、PCR）。'
    '籌碼面風險燈請見 §三 籌碼的「v4 引擎風險燈」。'
)

VETO_V4_ENGINE_NAME = 'v4 引擎風險燈'
VETO_V4_ENGINE_INPUTS = (
    'VIX（超過 25 紅燈／超過 20 黃燈）× '
    '外資期貨淨口數（空單超過 2 萬口 紅燈／超過 1 萬口 黃燈）'
)
VETO_V4_ENGINE_SCOPE_NOTE = (
    f'本燈只看【{VETO_V4_ENGINE_INPUTS}】—— 不含 PMI／CPI／出口／NDC。'
    '景氣與通膨面請見 §八 總經拼圖的「總經基本面否決檢查」。'
)

# ── 瘋牛濾網（量能過濾韭菜指數）────────────────────────────
BULLRUN_VOL_THRESHOLD = 1.3   # 大盤成交量 > 月均量 x 1.3 = 資金派對模式

# 20 日均量至少要有幾個「物理上可能」的觀測才算數（§1 缺值不得偽裝成 0）。
# 為什麼需要這條:`volume == 0` 在日 K 上**不是**一個有效觀測 —— 一整個市場
# 不可能在有價格波動的交易日成交 0 張。若把那些 0 當樣本餵進 rolling(20).mean(),
# 均量會被稀釋成接近「真值 / 有效筆數」,量比因此暴衝。
# 實測(2026-08-27,`data_cache/twii_ohlcv.parquet`):近 20 日有 19 筆假 0 +
# 1 筆真量 4,026,600 → 均量算成 201,330、量比 20.0x > 1.3 → 畫面送出
# 「💹 瘋牛模式：成交量 20.0x 均量」這個**假多頭訊號**,取代了原本誠實的
# 「⬜ 成交量資料缺失（瘋牛濾網未評估）」。門檻設 15/20(75%)是為了讓
# 「零星一兩天缺值」仍能照算,而「整段缺值」直接誠實回報未評估。
BULLRUN_VOL_MIN_VALID_DAYS = 15

# ── 總經警示規則（macro_alert.py 使用）──────────────────────
# 欄位說明：
#   red_above    → 值 > 此門檻觸發 🔴
#   yellow_above → 值 > 此門檻觸發 🟡（優先級低於 red_above）
#   red_below    → 值 < 此門檻觸發 🔴（雙向指標適用）
#   yellow_below → 值 < 此門檻觸發 🟡（雙向指標適用）
MACRO_ALERT_RULES: list = [
    {
        'key':          'vix',
        'label':        'VIX 恐慌指數',
        'unit':         '',
        'red_above':    30.0,   # > 30 市場恐慌
        'yellow_above': 20.0,   # 20–30 警戒
    },
    {
        'key':          'cpi',
        'label':        'CPI YoY（美）',
        'unit':         '%',
        'red_above':    3.5,    # > 3.5% 通膨加速，Fed 升息壓力
        'yellow_above': 2.5,    # 2.5–3.5% 溫和通膨
    },
    {
        'key':          'us10y',
        'label':        '美債 10Y 殖利率',
        'unit':         '%',
        'red_above':    4.8,    # > 4.8% 融資成本壓力，股市估值承壓
        'yellow_above': 4.2,    # 4.2–4.8% 觀察區
    },
    {
        'key':          'dxy',
        'label':        'DXY 美元指數',
        'unit':         '',
        'red_above':    107.0,  # > 107 強美元，外資撤離新興市場壓力
        'yellow_above': 103.0,  # 103–107 中性偏強
    },
    {
        'key':          'pcr',
        'label':        'PCR 選擇權比值',
        'unit':         '',
        'red_above':    1.5,    # > 1.5 市場極度恐慌
        'yellow_above': 1.2,    # 1.2–1.5 偏空情緒
        'red_below':    0.5,    # < 0.5 過度樂觀（頂部訊號）
        'yellow_below': 0.7,    # 0.5–0.7 樂觀偏高，注意反轉
    },
]


# ── Secrets / API Tokens ─────────────────────────────────────
# FINMIND_TOKEN：優先讀 Streamlit secrets，否則 fallback 到環境變數。
# 由 tab_stock.py / tab_stock_grp.py 等模組統一從這裡 import，
# 避免各檔重複貼 secrets+env 的 fallback 樣板。
#
# v18.241 A1：CLAUDE.md §8.2 例外 — L0 條件 import streamlit 限於 secrets bootstrap
# 理由：
#   1. try/except ImportError 已護 streamlit 缺席（純 .py 環境仍可運行）
#   2. 用途僅限讀 st.secrets，無 UI lifecycle 依賴（不用 cache_data / session_state）
#   3. 替代方案（移到 L3 + FINMIND_TOKEN 改函式）會打破所有 caller 介面，ROI 低
# 將此模式列為 CLAUDE.md §8.2 已知例外（見「8.2 已知例外清單」）。
import os as _os  # noqa: E402
try:
    import streamlit as _st  # noqa: E402  -- 例外:見上方 v18.241 A1 註解
    try:
        _t = (getattr(_st, 'secrets', None) or {}).get('FINMIND_TOKEN', '')
    except Exception:
        _t = ''
    FINMIND_TOKEN = _t or _os.environ.get('FINMIND_TOKEN', '')
except ImportError:
    FINMIND_TOKEN = _os.environ.get('FINMIND_TOKEN', '')


def get_finmind_token() -> str:
    """**每次呼叫即時**讀最新 FinMind Token:st.secrets > os.environ。

    與上方 module-level `FINMIND_TOKEN` 的差別:那是 **import 當下的快照**,
    Streamlit Cloud 改 Secrets 後要重啟才生效;本函式每次重讀,適合 UI 端
    「Token 狀態提示」與抓取前取值。

    F2(2026-08):原 `app.py::_get_fm_token`。搬來 L0 是為了拆掉
    `tab_macro`(L5)→ `app`(L6) 的上行 import(CLAUDE.md V-UP-APP-1)。
    conditional import streamlit 沿用同檔既有的 EX-L0-1 例外(僅讀 st.secrets,
    無 UI lifecycle 依賴)。

    ⚠️ **與 app.py 版的一處行為差異(刻意)**:原版寫
    `getattr(st, 'secrets', {}).get('FINMIND_TOKEN') or os.environ.get(...)`,
    **沒有** try/except —— 在無 `secrets.toml` 的環境(本機裸跑 / CI)
    `st.secrets.get()` 會 raise `StreamlitSecretNotFoundError`,而唯一 caller
    `tab_macro` 是裸呼叫 → 整頁炸。這裡補上 try/except 降級到 os.environ,
    與同檔 module-level `FINMIND_TOKEN` 及 `app.py::_get_secret` 的既有寫法一致。
    不是「掩蓋問題」:缺 secrets.toml 本來就該走 env fallback,而 token 真的缺時
    回空字串,caller(tab_macro)已有明確的 `🔑 FINMIND_TOKEN 未設定` 錯誤提示。
    """
    try:
        import streamlit as _st_t  # noqa: PLC0415 -- EX-L0-1,見上方 v18.241 A1 註解
        _tok = (getattr(_st_t, 'secrets', None) or {}).get('FINMIND_TOKEN', '')
    except Exception:  # noqa: BLE001 — 無 streamlit / 無 secrets.toml → 走 env
        _tok = ''
    return _tok or _os.environ.get('FINMIND_TOKEN', '')


# Batch 10 v18.412 R-FETCH「附帶」:FinMind API endpoint SSOT
# 原 22 檔散落 hardcoded URL(37 occurrences),改 import 收 SSOT
FINMIND_API_URL = 'https://api.finmindtrade.com/api/v4/data'

# Batch 8.1 v18.420:TWSE 三大法人 BFI82U endpoint SSOT
# Batch 8 re-audit:三大法人 4 路中 FinMind(Path 1/3/4)已全 SSOT,僅剩這 1 個
# TWSE 直連 URL 待集中(dispatcher 統一仍 WONTFIX,因 endpoint 真不同)
TWSE_BFI82U_URL = 'https://www.twse.com.tw/fund/BFI82U'

