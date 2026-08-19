"""L0 SSOT — 💰 存股戰情室門檻常數（以息養股 / 3-3-3 / 235 加碼）。

資料憲法 §3.3：所有判斷用到的數值一律從這裡引入,禁止 inline 腦補。
命名編碼單位（§4.1）：`_PCT` 百分比、`_Z` 布林標準差位階、`_WEEKS` 週數、`_YEARS` 年。
改門檻只改這一處。

⚠️ 這些門檻是「以息養股存股法」的參數,非本站發明；改動等於改策略,請審慎。
"""
from __future__ import annotations

# ── 235 加碼引擎：VIX 恐慌指數門檻（點數,非 %）──────────────────────────
VIX_LIGHT1: float = 20.0     # <20 巡航；20~25 燈一
VIX_LIGHT2: float = 25.0     # 25~30 燈二
VIX_LIGHT3: float = 30.0     # >=30 燈三

# ── 235：20 週布林通道標準差位階 z =（週收 − 20週均）/ 20週std ──────────
BOLL_PERIOD_WEEKS: int = 20
Z_LIGHT1: float = -1.0       # z < -1σ → 燈一
Z_LIGHT2: float = -2.0       # z < -2σ → 燈二
Z_LIGHT3: float = -3.0       # z < -3σ → 燈三
Z_TAKE_PROFIT_PARTIAL: float = 2.0   # z > +2σ 分批停利
Z_TAKE_PROFIT_FORCE: float = 3.0     # z > +3σ 強制停利

# ── 235：週線均線週期（週K）──────────────────────────────────────────
MA_MONTH_WEEKS: int = 4      # 4 週月線
MA_QUARTER_WEEKS: int = 13   # 13 週季線
MA_YEAR_WEEKS: int = 52      # 52 週年線

# ── 235：各燈動用「閒置加碼金」比例（%）──────────────────────────────
DEPLOY_LIGHT1_PCT: float = 20.0
DEPLOY_LIGHT2_PCT: float = 30.0
DEPLOY_LIGHT3_PCT: float = 50.0

# ── 235 燈號嚴重度排序（三取一取「最嚴重」那一盞）──────────────────────
# 數字越大越嚴重；停利獨立一軸（超漲）。
LIGHT_CRUISE = "cruise"      # ⚪ 巡航
LIGHT_1 = "light1"           # 🟢 小跌加碼
LIGHT_2 = "light2"           # 🟡 急跌加碼
LIGHT_3 = "light3"           # 🔴 崩盤加碼
LIGHT_TAKE_PROFIT = "take_profit"    # 💰 停利
_SEVERITY: dict[str, int] = {LIGHT_CRUISE: 0, LIGHT_1: 1, LIGHT_2: 2, LIGHT_3: 3}

LIGHT_META: dict[str, dict] = {
    LIGHT_CRUISE:      {"icon": "⚪", "label": "巡航（定期定額）", "deploy_pct": 0.0},
    LIGHT_1:           {"icon": "🟢", "label": "小跌加碼", "deploy_pct": DEPLOY_LIGHT1_PCT},
    LIGHT_2:           {"icon": "🟡", "label": "急跌加碼", "deploy_pct": DEPLOY_LIGHT2_PCT},
    LIGHT_3:           {"icon": "🔴", "label": "崩盤/深水加碼", "deploy_pct": DEPLOY_LIGHT3_PCT},
    LIGHT_TAKE_PROFIT: {"icon": "💰", "label": "停利警示", "deploy_pct": 0.0},
}

# ── 健檢門檻 ────────────────────────────────────────────────────────────
# D 折溢價：市價溢價 > 此 % → 高溢價不追高（🟡）
PREMIUM_ALERT_PCT: float = 1.5
# B 夏普：Sharpe < 此值 → 承擔風險無超額報酬（🔴）。ETF 也套用（user v19.166）。
SHARPE_NEG_THRESHOLD: float = 0.0

# ── 3-3-3 挑三原則 ──────────────────────────────────────────────────────
MIN_INCEPTION_YEARS: float = 3.0            # ① 成立 >= 3 年
MIN_ANN_RETURN_3Y_PCT: float = 7.0          # ② 3 年平均年化 >= 7%
MIN_CUM_RETURN_3Y_PCT: float = 21.0         # ②替代：3 年累積 >= 21%
PEER_TOP_FRACTION: float = 1.0 / 3.0        # ③ 同儕前 1/3（3M/6M/1Y 皆須）
PEER_WINDOWS_MONTHS: tuple[int, ...] = (3, 6, 12)   # 同儕比較的三個時間框
PEER_MIN_GROUP_SIZE: int = 3                # 同類 < 3 檔 → 同儕排名不可信

# ── 資料充足門檻（§1：不足就標「資料不足」不猜）──────────────────────
MIN_WEEKS_FOR_BOLL: int = BOLL_PERIOD_WEEKS         # < 20 週 → 無布林 z
MIN_WEEKS_FOR_YEAR_LINE: int = MA_YEAR_WEEKS        # < 52 週 → 無年線（燈三降級）

# ── 資產類型（個股 vs ETF；決定哪些健檢適用）────────────────────────────
KIND_STOCK = "stock"         # 個股：235/3-3-3 不適用,改走 財報體檢 + KD 判汰換
KIND_ETF = "etf"             # ETF：A/B/C/D + 235 + 3-3-3 全套（定期定額策略）

# ── 個股汰換（財報為主·KD為輔）：財報體檢 grade → 汰弱門檻 ──────────────────
# `financial_health_engine.no_ai_overall_verdict` 的 grade 分級為
# A+ / A / B / B+ / C / F（F=高危、C=明顯改善空間）。列於此的 grade 視為
# 「基本面汰弱」→ 建議換出（KD 只當進出場時機輔證,不獨立決定換股）。
STOCK_SWAP_GRADES: tuple[str, ...] = ("C", "F")


def classify_asset_kind(ticker: str) -> str:
    """依台股代號規則判 ETF vs 個股（純函式,**跟「在哪個清單」脫鉤**）。

    - `00` 開頭（0050 / 0056 / 00878 / 00980A / 00982T 等,可帶 A/T 後綴）→ ETF
    - 4 碼純數字（2330 / 6239 / 3006）→ 個股
    - 其餘（美股 BND / VOO 等非台股代號）→ 預設 ETF（本站非台股持有多為 ETF;
      折溢價/3-3-3 對美股 fetcher 會自然抓空標「—」,不誤傷）
    先去除 `.TW` / `.TWO` 後綴再判。
    §1:此為代號規則啟發式,非權威。個股被誤判成 ETF 的風險已由「4 碼→個股」優先攔下
    （避免對個股誤套折溢價/3-3-3）。
    """
    code = str(ticker or "").strip().upper()
    for _suf in (".TWO", ".TW"):
        if code.endswith(_suf):
            code = code[:-len(_suf)]
            break
    if code.startswith("00"):
        return KIND_ETF
    if len(code) == 4 and code.isdigit():
        return KIND_STOCK
    return KIND_ETF

# ── 80/20 核心/衛星分流 ────────────────────────────────────────────────
ASSET_CORE = "core"          # 核心（穩定配息,目標 80%）
ASSET_SATELLITE = "satellite"    # 衛星（成長/主題,目標 20%）
CORE_TARGET_PCT: float = 80.0
SATELLITE_TARGET_PCT: float = 20.0
# 衛星嚴格停利：獲利達此 % → 停利滾回核心
SATELLITE_TAKE_PROFIT_PCT: float = 15.0

# ── 浮點容差（§4.3）──────────────────────────────────────────────────
FLOAT_ABS_TOL: float = 1e-9
