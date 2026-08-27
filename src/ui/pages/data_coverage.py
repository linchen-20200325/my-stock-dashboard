"""src/ui/pages/data_coverage.py — 前 N Tab 資料「有值 / 新鮮」檢查表(v18.280)

學 Fund 端 ui/tab5_data_guard.py Section ⓪ 的「預設視角」:
user 關心的是「我的某個 Tab 有沒有資料」,而非只看「TWSE API 通不通」。

掛在 🔎 資料診斷 Tab **最上方**(Fund 架構:用戶視角優先,API 端點細節放後)。

純讀 session_state,無副作用(§8.2 L5 UI 規則,不寫入 session_state)。
對外 API:
- compute_tab_coverage() -> list[dict]  純函式,易測
- render_data_coverage() -> None         Streamlit 渲染

═══ B4-a(本輪):這頁本身在說謊,五條根因與修法 ═══════════════════════
稽核實測:先行指標「前五大留倉 / 前十大留倉 / 未平倉口數」連續 9 個交易日
數值完全不變,本表照樣顯示「🟢 3/3 完整 / 🟢 當日」。逐條:

D-1  覆蓋率只判 `is not None` → `inst` 全敗時 macro_fetch_orchestrator 依契約
     回 `{}`(空 dict,**不是** None),於是「抓取全失敗」被算成「有值」。
     修:改判 `_has_value`(空 dict / 空 list / 空 DataFrame / NaN / 只含 `_err`
     的 block 一律算沒值)。
D-1b `shared.data_freshness.detect_frozen_columns`(值凍結偵測)全 repo 零 caller。
     修:本檔接上 —— 籌碼面對 li_latest 的 7 個日頻欄跑一階差分,連續
     `FROZEN_STALE_PERIODS_LEADING`(L0 SSOT)期無變化即點名降級。
D-1c 既有 `_is_stale` 旗標路徑接不到:`_STALE_MAX_AGE_MIN=3 日`,超齡 pickle 直接
     回 None,旗標永遠不會被設;而 tab_macro 收到 None 時**靜默沿用上一輪的
     li_latest**(那份 df 身上沒有任何旗標)。修:tab_macro 改把「沿用上輪」寫成
     `li_retain_meta`,本檔讀它並降級(詳見該檔註解與報告)。
D-2  「🟢 當日」量的是 `macro_info['_loaded_at']` = **抓取時間**(datetime.now()),
     抓回一筆 60 天前的 CPI 也會顯示當日。修:改量每個指標 block 自己的
     `date`(as-of 資料日),並依該指標的發布頻率套 SSOT 門檻;`_loaded_at`
     降級為細項裡的「抓取時刻」文字,不再參與燈號。
D-3  籌碼面覆蓋率算 cl_data,新鮮度卻取自另一個物件 li_latest;而 cl_data 本身
     有真正的 as-of `cl_data['inst_date']` 從未被讀。修:三個子源各自取 as-of
     (inst_date / adl.date / li._date),取**最差**者當整列燈號。
D-4  個股讀 `t2_data['date']`(不存在,實際只有 `fetched_at` 與 `df`)、
     ETF 讀 `etf_single_data['nav_date']`(實際巢狀在 `premium` 內)→ 永遠 ⬜。
     修:key 接對;接對後若仍拿不到,顯示 ⬜ 但**分辨得出來**是哪一種 ——
     `未載入`(真的沒觸發)vs `無資料日期`(容器有值但找不到日期欄,附上找過
     哪些路徑,mis-wire 會直接顯示在畫面上而不是只躺在 log 裡)。
D-5  抓取失敗長得跟成功一樣:tab_stock 無條件寫 t2_data(含 `err`),失敗時
     dict 仍非空 → 🟢「已載入(28 欄)」。修:`err` 為真 → 🔴 並印出錯誤原文。

另:「完整」二字名不副實(該燈只代表「不是 None」)→ 全面改「有值」;
inline 門檻與色票改吃 SSOT(shared.staleness / shared.colors),詳見下方常數註解。
"""
from __future__ import annotations

import datetime as _dt

import streamlit as st

# 色票走 shared.colors SSOT(L0)。原本本檔內聯的 #3fb950/#d29922/#f85149/#6e7681
# 是 v19.68 前的 GitHub 舊色,全站早已改 Tailwind,只有這張表沒跟上 → 同一個
# 🟡 在診斷頁和其他頁是兩種黃。B4-a 一併收斂,不再留第二份色票。
from shared.colors import TRAFFIC_NEUTRAL as _C_IDLE, emoji_to_hex as _hex

# v18.349 — macro_info 核心指標 key 契約走 SSOT(L0)，與 tab_macro 寫入端共用，
# 杜絕 v18.282 那種 key 名各自寫死 → 漂移 → 覆蓋率永遠紅燈。
from shared.macro_buckets import (
    MACRO_INFO_KEYS, SPECS_BY_KEY,
    MISSING_NOT_LOADED, MISSING_NO_VALUE, MISSING_OUT_OF_RANGE,
    MISSING_NO_EXTRACTION,
)

# v19.170 P0-4:覆蓋率 ≠ 新鮮度。覆蓋率只問「有沒有值」,問不出「值是不是 9 天沒動
# 的死資料」。故本表分兩欄,燈號規則走 L0 SSOT。
from shared.data_freshness import (
    FROZEN_STALE_PERIODS_LEADING,
    LEADING_DATE_COL,
    downgrade_to_warn,
    freshness_level_for_cadence,
    leading_frozen_columns,
    monthly_freshness_level,
    worst_freshness,
)
from shared.staleness import STALE_DAYS_DAILY, latest_date, staleness_days

# ── 覆蓋率(有值率)門檻 ──────────────────────────────────────────────
# 覆蓋率 ≥ 85% 才算綠燈:8 個總經項容忍缺 1 個(7/8=0.875 綠,6/8=0.75 黃),
# ≥ 50% 為黃燈(過半有值,可用但殘缺);其餘紅燈。
_COVER_GREEN_RATIO = 0.85
_COVER_YELLOW_RATIO = 0.50

# ── 新鮮度門檻 ─────────────────────────────────────────────────────
# 【日頻紅燈】走 SSOT `shared.staleness.stale_days_threshold('daily')`=7,
#   本檔**不自己寫天數**。
# 【月頻】G2 2026-08-08 **改為以「發布期數」判定**,不再用日曆天門檻:
#   B4-a 當初套 `stale_days_threshold('monthly')`=45,但 macro_info 月頻指標的
#   `date` 是**資料月月初**(PMI/CPI/出口/NDC/Fed 全部),當期最新一筆的 as_of
#   年齡天生就是 63~89 天 ⇒ 這一列的新鮮度燈**在健康狀態下也永遠 🔴**。
#   一個 100% 觸發的警告等於沒有警告。改走
#   `shared.data_freshness.monthly_freshness_level(as_of, indicator=key)`,
#   規則本體在 `shared.staleness.monthly_release_status`,全站月頻同一份。
# 【黃燈】診斷頁刻意比一般頁嚴格,保留一個具名的日頻黃燈起點:
_DIAG_DAILY_WARN_DAYS = 3
# 為什麼是 3 而不是沿用 SSOT 的 7:
#   (a) 這頁的用途就是「今天能不能信這些數字」,日頻資料落後 4~7 天雖然還沒到
#       SSOT 判定的「過期」,但已經跨過一個完整週末仍無新資料,值得先亮黃。
#   (b) 為什麼不是更嚴的 1(舊值):`staleness_days` 量的是**日曆天**,而
#       `expected_latest_trading_day` 只回最近的非週末日 —— 於是「週五資料在
#       週一被讀到」是完全正常的狀態,lag 卻等於 3。舊門檻 warn=1/bad=3 會讓
#       每個週一早上整頁亮黃、週二早上亮紅,全是假警報。3 = 一個週末的自然差值
#       上限,低於此不報警。
# 【季頻】不設黃燈帶(warn=bad):季報要嘛是當期最新一筆,要嘛就是逾期。
# 【月頻】黃燈有明確語意(不是「有點舊」):下一期的**原定發布日已過**、但還在
#   `MONTHLY_PUBLICATION_MARGIN_DAYS` 緩衝內 → 🟡「待公布」;
#   緩衝過完仍沒有新的一期 → 🔴「落後N期」。

# macro_info 各 key 的發布頻率 → 決定走哪一條規則(§2.3 發布延遲表)。
# ⚠️ 新增 MACRO_INFO_KEYS 時必須同步在此登記;
#   tests/test_b4a_data_coverage_honesty.py 有漂移守衛會擋。
# ⚠️ 標 "monthly" 的 key **必須**同時登錄在
#   `shared.staleness.MACRO_PUBLICATION_LAG_DAYS`(否則該格顯示 ⬜「門檻未登錄」);
#   tests/test_g2_monthly_freshness.py 有守衛會擋。
_MACRO_KEY_CADENCE: dict[str, str] = {
    "vix":         "daily",     # yfinance ^VIX,日線
    "ism_pmi":     "monthly",   # 台灣 PMI(CIER),月後第 1 營業日
    "us_core_cpi": "monthly",   # FRED CPILFESL,月後 ~13 天
    "fed_funds":   "monthly",   # FRED FEDFUNDS,月頻
    "ndc_signal":  "monthly",   # 國發會景氣燈號,月頻
    "tw_export":   "monthly",   # MOF 進出口,月後 ~8-10 天
    "us10y":       "daily",     # FRED DGS10,日頻(非核心 6 key,列此備用)
}
_MACRO_CADENCE_FALLBACK = "daily"   # 未登記 → 最嚴(同 stale_days_threshold 預設)

# macro_info 每個 block 內屬於 provenance / 座標軸的欄位,不算「實質數值」。
# 用途:一個 block 若把這些扣掉之後剩下的值全是 None,代表 fetcher 其實失敗了
# (如 fetch_us10y_block 全敗會回 {'_err':..., 'current': None}),不得算有值。
_MACRO_BLOCK_META_KEYS = frozenset({
    "source", "fetched_at", "series_id", "date", "dates", "values", "cadence",
})

# ── 先行指標凍結偵測(D-1b)────────────────────────────────────────────
# 2026-08-27:本檔原有三個私有副本 `_LI_FROZEN_WATCH_COLS` /
# `_LI_FROZEN_STALE_PERIODS` / `_LI_DATE_COL`(與 L0 逐字相同,靠
# `tests/test_data_coverage.py` 的 AST drift 守衛釘住)。**副本已刪,改直接
# 用 L0 SSOT** —— 主畫面(L2 判燈)也要問同一個問題「哪幾欄凍結」,再留一份
# 副本就會有第三份答案。監看欄與期數的**選法理由**(為什麼只挑日頻淨額 /
# 未平倉類、為什麼刻意排除成交量與融資餘額)寫在 L0 常數的 docstring,
# 不在這裡重述 —— 理由重述兩份,漂移的就是理由。

# 各 Tab 取 as-of 日期時「找過哪些路徑」——接錯 key 時要能在畫面上看見找過什麼,
# 而不是只留下一個永遠不會變色的 ⬜(D-4 的根因就是沒人發現 key 接錯)。
_ASOF_PATHS_ETF: tuple = (("premium", "nav_date"), ("premium", "data_date"),
                          ("premium", "price_date"))


# ══════════════════════════════════════════════════════════════════
# 小工具
# ══════════════════════════════════════════════════════════════════
def _has_value(v) -> bool:
    """「這個欄位真的有值嗎」——D-1 的核心判定,取代原本的 `is not None`。

    False 的情形:None / NaN / 空 DataFrame / 空 dict / 空 list / 空字串。
    True  的情形:其餘(含數值 0 —— 0 是一個真實的觀測值,不當缺值處理;
    「不可能為 0」的業務判斷屬各 fetcher 的職責,不在這張表上腦補)。
    """
    if v is None:
        return False
    _empty = getattr(v, "empty", None)      # DataFrame / Series
    if _empty is not None:
        try:
            return not bool(_empty)
        except Exception:                    # noqa: BLE001 — 診斷頁不因單源解析失敗掛掉
            return True
    if isinstance(v, float):
        return v == v                        # NaN != NaN
    if isinstance(v, (str, bytes, list, tuple, set, dict)):
        return len(v) > 0
    return True


def _macro_block_has_value(v) -> bool:
    """macro_info 單一指標 block 是否真的有數值(而非「失敗但回了個 dict」)。

    fetcher 失敗時常見兩種形狀,兩種都必須算沒值(§1 不得被覆蓋率洗成綠燈):
      1. `{'_err': '...'}`                    → 有 `_err`
      2. `{'_err': '...', 'current': None}`   → 扣掉 meta 後全是 None
    """
    if not _has_value(v):
        return False
    if isinstance(v, dict):
        if v.get("_err"):
            return False
        _payload = {k: x for k, x in v.items()
                    if not str(k).startswith("_") and k not in _MACRO_BLOCK_META_KEYS}
        if _payload and all(x is None for x in _payload.values()):
            return False
    return True


def _dig(obj, path):
    """依 path 取巢狀值。path 可為 str 或 (str, str, ...);任一層缺 → None。"""
    _keys = (path,) if isinstance(path, str) else tuple(path)
    _cur = obj
    for _k in _keys:
        if not isinstance(_cur, dict):
            return None
        _cur = _cur.get(_k)
        if _cur is None:
            return None
    return _cur


def _fmt_date(d) -> str:
    try:
        return d.strftime("%m/%d")
    except Exception:                        # noqa: BLE001
        return str(d)[:10]


def _asof_of_mapping(obj, paths, *, tab: str, today: _dt.date | None = None):
    """從 dict 依序找第一個可解析的 as-of 日期。

    回 `(as_of_date|None, lag_days|None, reason)`;
    reason ∈ {'ok', 'not_loaded', 'no_date_key', 'unparsable'}。

    `today` 供測試注入(不注入 → `date.today()`;測試若吃執行當天日期,
    斷言會在某些日子隨機轉紅)。

    §1:找不到就誠實回 None + reason,**不**退回抓取時間頂替(D-2 就是這樣爛掉的)。
    """
    if not _has_value(obj) or not isinstance(obj, dict):
        return (None, None, "not_loaded")
    _raw = None
    for _p in paths:
        _v = _dig(obj, _p)
        if _v is not None:
            _raw = _v
            break
    if _raw is None:
        print(f"[coverage] ⚠️ {tab}:找不到資料日期,已找過 "
              f"{['.'.join((p,)) if isinstance(p, str) else '.'.join(p) for p in paths]};"
              f" 實際 top-level keys={sorted(str(k) for k in obj)[:12]}")
        return (None, None, "no_date_key")
    _d = latest_date(_raw)
    if _d is None:
        print(f"[coverage] ⚠️ {tab}:資料日期無法解析 raw={_raw!r}")
        return (None, None, "unparsable")
    return (_d, staleness_days(_raw, today=today), "ok")


def _asof_of_df(df, *, date_col: str, tab: str, today: _dt.date | None = None):
    """從 DataFrame 取 as-of。無 columns / 無該欄 → 'no_date_key'(含 loud log)。"""
    if not _has_value(df):
        return (None, None, "not_loaded")
    _cols = getattr(df, "columns", None)
    if _cols is None:
        print(f"[coverage] ⚠️ {tab}:期望 DataFrame(含 '{date_col}' 欄)"
              f"但拿到 {type(df).__name__} → 無法取資料日期")
        return (None, None, "no_date_key")
    if date_col not in list(_cols):
        print(f"[coverage] ⚠️ {tab}:DataFrame 缺 '{date_col}' 欄,"
              f"實際欄={list(_cols)[:12]}")
        return (None, None, "no_date_key")
    _d = latest_date(df, date_col=date_col)
    if _d is None:
        return (None, None, "unparsable")
    return (_d, staleness_days(df, date_col=date_col, today=today), "ok")


def _asof_of_df_index(df, *, tab: str, today: _dt.date | None = None):
    """從 DataFrame 的 DatetimeIndex 取 as-of(yfinance 價量表沒有 date 欄)。

    ⚠️ 只接受**日期型 index**。預設的 RangeIndex 取 max 會拿到 0/1/2…,
    `pd.to_datetime(4)` 會安靜地解成 1970-01-01 → 假紅燈。§1:寧可回「不可知」。
    """
    if not _has_value(df):
        return (None, None, "not_loaded")
    _idx = getattr(df, "index", None)
    if _idx is None or len(_idx) == 0:
        return (None, None, "no_date_key")
    try:
        _mx = _idx.max() if hasattr(_idx, "max") else max(_idx)
    except Exception as _e:                  # noqa: BLE001
        print(f"[coverage] ⚠️ {tab}:index 無法取 max: {type(_e).__name__}: {_e}")
        return (None, None, "unparsable")
    if not isinstance(_mx, (_dt.date, _dt.datetime)):
        print(f"[coverage] ⚠️ {tab}:index 不是日期型（max={_mx!r} "
              f"型別={type(_mx).__name__}）→ 不猜,回「無資料日期」")
        return (None, None, "no_date_key")
    _d = latest_date(_mx)
    if _d is None:
        return (None, None, "unparsable")
    return (_d, staleness_days(_mx, today=today), "ok")


_REASON_LABEL = {
    "not_loaded":  "未載入",
    "no_date_key": "無資料日期",     # 容器有值但找不到日期欄 → 多半是 key 接錯
    "unparsable":  "日期無法解析",
}


def _level_from_asof(asof, lag, reason, *, cadence: str,
                     indicator: str | None = None,
                     today: _dt.date | None = None):
    """把 `(as_of, lag, reason)` 翻成 `(emoji, label, asof_txt)`。

    reason != 'ok' 一律 ⬜,但 label 分得出「真的沒觸發」vs「接錯/解析不了」——
    後者是**程式 bug 的徵狀**,不該跟前者長一樣(D-4 的教訓)。

    cadence == 'monthly' 走**期數**規則(需 `indicator`),其餘走日曆天門檻。
    兩條路的規則本體都在 L0,本檔只負責挑路。
    """
    if reason != "ok":
        return ("⬜", _REASON_LABEL.get(reason, "未知"), "")
    _at = _fmt_date(asof) if asof is not None else ""
    if cadence == "monthly":
        # 未登錄發布延遲 → monthly_freshness_level 自己會回 ⬜「門檻未登錄」+ log,
        # **不**退回日曆天門檻頂替(退回去就等於把 G2 修掉的假紅燈再放回來)。
        _e, _l = monthly_freshness_level(asof, indicator=indicator, today=today)
        return (_e, _l, _at)
    _warn = _DIAG_DAILY_WARN_DAYS if cadence == "daily" else None
    _e, _l = freshness_level_for_cadence(lag, cadence, warn_days=_warn)
    return (_e, _l, _at)


def _ss(key: str):
    """安全讀 session_state(測試環境 st 可能 stub)。"""
    try:
        return st.session_state.get(key)
    except Exception:                        # noqa: BLE001
        return None


def _coverage_emoji(have: int, total: int) -> str:
    """依「有值率」回 emoji。total=0 → 未觸發。"""
    if total == 0:
        return "⬜"
    r = have / total
    if r >= _COVER_GREEN_RATIO:
        return "🟢"
    if r >= _COVER_YELLOW_RATIO:
        return "🟡"
    return "🔴"


def _li_frozen_info(df) -> tuple[bool, float | None]:
    """讀 li_latest 的欄位版 stale 旗標,回 (是否凍結, 凍結分鐘數|None)。

    v19.170:優先讀 `_is_stale` **欄**而非 `df.attrs` —— attrs 在 pandas 多數運算
    與 session_state 往返後會遺失(見 leading_indicators._mark_stale 註解)。
    attrs 僅作為向下相容的次選。
    """
    if df is None:
        return (False, None)
    _cols = getattr(df, "columns", None)
    _stale, _age = False, None
    if _cols is not None and "_is_stale" in _cols:
        try:
            _stale = bool(df["_is_stale"].any())
        except Exception:                    # noqa: BLE001
            _stale = False
        if _stale and "_stale_age_min" in _cols:
            try:
                _v = df["_stale_age_min"].dropna()
                _age = float(_v.iloc[0]) if len(_v) else None
            except Exception:                # noqa: BLE001
                _age = None
    if not _stale:
        _attrs = getattr(df, "attrs", {}) or {}
        _stale = bool(_attrs.get("is_stale", False))
        if _stale:
            _age = _attrs.get("stale_age_min")
    return (_stale, _age)


# ══════════════════════════════════════════════════════════════════
# 主計算
# ══════════════════════════════════════════════════════════════════
def compute_tab_coverage(state: dict | None = None,
                         today: _dt.date | None = None) -> list[dict]:
    """計算各資料 Tab 的「有值率」與「新鮮度」。

    state: 測試可注入 dict;None → 讀 st.session_state。
    today: 測試可注入基準日;None → `date.today()`。
           (不可省 —— 新鮮度斷言若吃執行當天日期,會在某些日子隨機轉色。)
    回傳 list[dict],每筆:
      {tab, emoji, color, ratio_txt, detail, action,
       fresh_emoji, fresh_label, fresh_color, fresh_asof}
    """
    def _get(key: str):
        if state is not None:
            return state.get(key)
        return _ss(key)

    rows = []

    # ══ 🌍 總經:macro_info 6 指標 + M1B-M2 + 領先指標 ══════════════
    _ma = _get("macro_info") or {}
    _mi = _get("m1b_m2_info") or {}
    _li = _get("li_latest")
    _macro_keys = list(MACRO_INFO_KEYS)
    _ma_is_dict = isinstance(_ma, dict)
    # D-1:改判「有實質值」。空 dict / 只有 _err / 值全 None 都不算有值。
    _macro_have = sum(1 for k in _macro_keys
                      if _ma_is_dict and _macro_block_has_value(_ma.get(k)))
    _macro_total = len(_macro_keys)
    _macro_extra = int(_has_value(_mi)) + int(_has_value(_li))

    # ── 決策燈 readiness(2026-08-20)────────────────────────────────────
    # 舊分母是 `MACRO_INFO_KEYS` 這 6 個 macro_info 容器,但**真正驅動五桶決策的
    # 是 `BUCKET_DANGER_SPECS` 的 16 盞燈** —— 差集 11 個從來不在覆蓋率檢查裡。
    #
    # 改為直接問決策函式自己:16 盞燈有幾盞拿到值、沒拿到的**為什麼**。
    # readiness 是 `compute_five_bucket_summary` 的副產物(從餵給 classify_danger
    # 的同一個 values dict 生出來),所以「新增一盞燈」與「新增一筆 readiness」
    # 是同一個動作 —— 不是偵測漂移,是沒有第二份東西可以漂移。
    #
    # L5 → L2 下行 import,既有先例(`macro/helpers.py`、`section_summary_bar.py`)。
    _readiness: dict = {}
    try:
        from src.compute.macro import compute_five_bucket_summary  # noqa: PLC0415
        compute_five_bucket_summary(
            macro_info=_ma if _ma_is_dict else None,
            mkt_info=_get("mkt_info"), warroom_summary=_get("warroom_summary"),
            m1b_m2_info=_mi, bias_info=_get("bias_info"),
            cl_data=_get("cl_data"), li_latest=_li,
            jingqi_info=_get("jingqi_info"), news_items=_get("_macro_news_items"),
            readiness_out=_readiness,
        )
    except Exception as _e_rd:
        # §1:算不出來就說,不要靜默退回舊分母後假裝一切正常。
        print(f"[data_coverage] ⚠️ readiness 取得失敗,總經列退回舊口徑:"
              f"{type(_e_rd).__name__}: {_e_rd}")

    # 分母**不含刻意未接線者** —— 一個 100% 恆亮的警告等於沒有警告(同 G2 教訓)。
    _rd_wired = [r for r in _readiness.values() if r.get("wired")]
    _rd_ok = [r for r in _rd_wired if r.get("state") == "ok"]
    _rd_unwired = [r for r in _readiness.values() if not r.get("wired")]

    if _rd_wired:
        # 主計數 = 決策燈;`fed_funds` 等「在 macro_info 但不是五桶燈」的容器
        # 走第二個子計數(user 2026-08-20 裁示:不把不同語意的東西加在一起)。
        _macro_have_all = len(_rd_ok)
        _macro_total_all = len(_rd_wired)
    else:
        _macro_have_all = _macro_have + _macro_extra
        _macro_total_all = _macro_total + 2
    # 判 macro_info「有被跑過」:排除純 _ 開頭 meta key(_loaded_at / _all_failed)
    _ma_loaded = _ma_is_dict and any(not str(k).startswith("_") for k in _ma)
    _e1 = _coverage_emoji(_macro_have_all, _macro_total_all) if _ma_loaded else "⬜"

    # D-2:新鮮度量**每個指標自己的資料日期**,依該指標的發布頻率套 SSOT 門檻。
    #      `_loaded_at`(抓取時刻)降級為細項文字,完全不參與燈號。
    _macro_entries: list[tuple[str, str, str]] = []   # (emoji, label, as_of_txt)
    _macro_no_date = []
    if _ma_loaded:
        for _k in _macro_keys:
            _blk = _ma.get(_k) if _ma_is_dict else None
            if not _macro_block_has_value(_blk):
                continue                     # 沒值的由覆蓋率那欄負責,不重複扣新鮮度
            _cad = _MACRO_KEY_CADENCE.get(_k, _MACRO_CADENCE_FALLBACK)
            _a, _lag, _rsn = _asof_of_mapping(_blk, ("date",), tab=f"總經:{_k}",
                                              today=today)
            if _rsn != "ok":
                _macro_no_date.append(_k)
                continue
            # 月頻走期數規則 → indicator 就是 macro_info 的 key(與
            # MACRO_PUBLICATION_LAG_DAYS 同名);日頻用不到 indicator。
            _e, _l, _at = _level_from_asof(_a, _lag, _rsn, cadence=_cad,
                                           indicator=_k, today=today)
            _macro_entries.append((_e, f"{_k} {_l}", _at))
    _macro_asof = ""
    if _macro_entries:
        # 燈號取最差者(worst_freshness 是唯一的排序 SSOT,本檔不自己寫 rank 表)
        _f1e, _f1l = worst_freshness([(e, l) for e, l, _ in _macro_entries])
        _macro_asof = next((at for e, l, at in _macro_entries
                            if e == _f1e and l == _f1l), "")
    elif _ma_loaded and _macro_no_date:
        _f1e, _f1l = "⬜", "無資料日期"
    else:
        _f1e, _f1l = "⬜", "未載入"

    _loaded_at_txt = str(_ma.get("_loaded_at") or "") if _ma_is_dict else ""
    if _rd_wired:
        # 主計數 = 決策燈;缺席者**依原因分組**列出 —— 五種灰燈長得一樣但處置完全不同,
        # 混在一起講「缺 N 項」等於要使用者自己猜該做什麼(user 原話:避免誤判)。
        _by_reason: dict = {}
        for _r in _rd_wired:
            if _r.get("state") != "ok":
                _by_reason.setdefault(_r.get("reason") or "?", []).append(_r["key"])
        _REASON_TXT = {
            MISSING_NOT_LOADED:    ("🔌", "未載入", "在 🌍 總經 按更新"),
            MISSING_NO_VALUE:      ("📵", "上游無值", "看下方 API 根因診斷"),
            MISSING_OUT_OF_RANGE:  ("📐", "量綱異常", "上游換標的/報價慣例改變"),
            MISSING_NO_EXTRACTION: ("🐛", "spec 無取值", "程式 bug,非資料問題"),
        }
        _detail1_parts = [f"決策燈 {len(_rd_ok)}/{len(_rd_wired)} 有值"]
        for _rs, _keys in _by_reason.items():
            _ic, _nm, _act = _REASON_TXT.get(_rs, ("⬜", str(_rs), ""))
            _detail1_parts.append(f"{_ic} {_nm}({len(_keys)}):{'/'.join(_keys)} → {_act}")
        # 量綱異常最毒(有值、數字看起來正常、但尺度錯) → 把實際被擋的值講出來
        for _r in _rd_wired:
            if _r.get("reason") == MISSING_OUT_OF_RANGE:
                for _lbl, _v, _why in (_r.get("rejected") or []):
                    _detail1_parts.append(f"　└ {_r['key']}:{_lbl} = {_v} {_why}")
        # 刻意未接線者:不計入分母,但要具名說明,否則使用者會以為它壞了
        for _r in _rd_unwired:
            _sp_u = SPECS_BY_KEY.get(_r["key"])
            _detail1_parts.append(
                f"⛔ 未接線:{_r['key']} — {getattr(_sp_u, 'unwired_reason', '')[:40]}"
                f"（不計入分母，此燈永遠不會亮）")
        # 2026-08-25:鑑別力已失效者 —— 與「未接線」是**不同的病**。
        # 這盞燈會亮、也計入分母(它真的有值),但門檻本身已失去判別力,
        # 於是它跟一盞真正的紅燈長得一模一樣。不標出來,使用者無從分辨。
        for _r in _readiness.values():
            if _r.get("discriminative", True):
                continue
            _sp_d = SPECS_BY_KEY.get(_r["key"])
            _detail1_parts.append(
                f"🔒 門檻已失效:{_r['key']} — "
                f"{getattr(_sp_d, 'degraded_reason', '').splitlines()[0][:40]}"
                f"（燈會亮但別照門檻讀，看相對變化）")
        # user 2026-08-20 裁示:fed_funds 這類「在 macro_info 但不是五桶決策燈」的
        # 容器保留為**第二個子計數**,不與決策燈加總(語意不同的東西不該相加)。
        _detail1_parts.append(f"另 macro 容器 {_macro_have}/{_macro_total} 有值")
    else:
        _detail1_parts = [
            f"核心指標 {_macro_have}/{_macro_total} 有值",
            f"M1B-M2 {'✓' if _has_value(_mi) else '✗'}",
            f"領先 {'✓' if _has_value(_li) else '✗'}",
        ]
    # 大盤評分本輪少了哪幾條腿 —— `market_regime` 2026-08-19 起就在算 `missing_factors`,
    # 但診斷頁從來沒有人讀它。這是一行的事。
    _mkt_missing = (_get("mkt_info") or {}).get("missing_factors") or []
    if _mkt_missing:
        _detail1_parts.append(f"⚠️ 大盤評分本輪少了:{'、'.join(_mkt_missing)}")
    if _macro_no_date:
        _detail1_parts.append(f"⚠️ {len(_macro_no_date)} 項無資料日期:"
                              f"{'/'.join(_macro_no_date)}")
    if _loaded_at_txt:
        # 明講這是抓取時刻,不是資料日期 —— D-2 的整個病灶就是把這兩件事混為一談
        _detail1_parts.append(f"本輪抓取於 {_loaded_at_txt[5:16]}（≠ 資料日期）")
    rows.append({
        "tab": "🌍 總經",
        "emoji": _e1, "color": _hex(_e1),
        "ratio_txt": f"{_macro_have_all}/{_macro_total_all}" if _ma_loaded else "未載入",
        "detail": " ｜ ".join(_detail1_parts) if _ma_loaded else "在 🌍 總經 Tab 按更新觸發",
        "action": "缺值 → 看下方 API Key / Proxy 診斷",
        "fresh_emoji": _f1e, "fresh_label": _f1l, "fresh_color": _hex(_f1e),
        "fresh_asof": _macro_asof,
    })

    # ══ 📈 個股:t2_data(單一個股 metrics dict)═════════════════════
    _t2 = _get("t2_data") or {}
    _t2_is_dict = isinstance(_t2, dict)
    _t2_loaded = _t2_is_dict and bool(_t2)
    _t2_err = _t2.get("err") if _t2_is_dict else None
    _t2_df = _t2.get("df") if _t2_is_dict else None
    if not _t2_loaded:
        _e2, _ratio2 = "⬜", "未查"
        # B6-a v19.181:Tab 名對齊 app.py:584（真名 🔬 個股，非 📈 個股）
        _detail2 = "在 🔬 個股 Tab 查股票代號觸發"
    elif _t2_err:
        # D-5:tab_stock 無條件寫 t2_data(含 err),失敗時 dict 仍非空 →
        #      原本照樣 🟢「已載入(28 欄)」。抓取失敗必須看起來就是失敗。
        _e2, _ratio2 = "🔴", "抓取失敗"
        _detail2 = f"❌ {_t2.get('sid', '?')} 價格抓取失敗：{str(_t2_err)[:70]}"
    elif not _has_value(_t2_df):
        _e2, _ratio2 = "🔴", "無 K 線"
        _detail2 = ("個股 dict 已寫入但價格序列為空 —— 技術指標 / 健康評分全部"
                    "算不出來,畫面上的數字不可信")
    else:
        _e2, _ratio2 = "🟢", "已查"
        _n_bars = len(_t2_df) if hasattr(_t2_df, "__len__") else "?"
        _detail2 = (f"{_t2.get('sid', '')} 已載入（{len(_t2)} 欄，"
                    f"K 線 {_n_bars} 筆）").strip()
    # D-4:原本讀 `t2_data['date']`(根本不存在)→ 永遠 ⬜。真正的 as-of 在 df.date。
    _a2, _lag2, _rsn2 = _asof_of_df(_t2_df, date_col="date", tab="個股 t2_data['df']",
                                    today=today)
    _f2e, _f2l, _f2a = _level_from_asof(_a2, _lag2, _rsn2, cadence="daily",
                                        today=today)
    rows.append({
        "tab": "📈 個股",
        "emoji": _e2, "color": _hex(_e2),
        "ratio_txt": _ratio2,
        "detail": _detail2,
        "action": "缺資料 → TWSE / FinMind / Yahoo fallback chain",
        "fresh_emoji": _f2e, "fresh_label": _f2l, "fresh_color": _hex(_f2e),
        "fresh_asof": _f2a,
    })

    # ══ 💰 籌碼:cl_data(法人 inst / 融資 margin / 廣度 adl)+ 先行指標 ══
    _cl = _get("cl_data") or {}
    _cl_is_dict = isinstance(_cl, dict)
    _cl_keys = [("inst", "法人"), ("margin", "融資"), ("adl", "廣度")]
    # D-1:`inst` 全敗時 orchestrator 回 `{}`(非 None)—— 舊的 `is not None`
    #      會把「三大法人整組沒抓到」算成有值,這是本次假綠燈的直接來源。
    _cl_have = sum(1 for k, _ in _cl_keys
                   if _cl_is_dict and _has_value(_cl.get(k)))
    _e3 = _coverage_emoji(_cl_have, len(_cl_keys)) if _has_value(_cl) else "⬜"

    # D-3:新鮮度改量 cl_data 自己的 as-of。三個子源各自算,取最差。
    _chip_levels, _chip_asof = [], ""
    if _has_value(_cl):
        # ① 三大法人:cl_data['inst_date'](既有但從未被讀)
        if _cl_is_dict and _has_value(_cl.get("inst")):
            _a, _lg, _rs = _asof_of_mapping(_cl, ("inst_date",), tab="籌碼 cl_data",
                                            today=today)
            _e, _l, _at = _level_from_asof(_a, _lg, _rs, cadence="daily", today=today)
            _chip_levels.append((_e, f"法人 {_l}"))
            _chip_asof = _at or _chip_asof
        # ② 廣度 ADL:df 內建 date 欄
        if _cl_is_dict and _has_value(_cl.get("adl")):
            _a, _lg, _rs = _asof_of_df(_cl.get("adl"), date_col="date",
                                       tab="籌碼 cl_data['adl']", today=today)
            _e, _l, _at = _level_from_asof(_a, _lg, _rs, cadence="daily", today=today)
            _chip_levels.append((_e, f"廣度 {_l}"))
            _chip_asof = _chip_asof or _at
    # ③ 先行指標:li_latest 的 _date(舊版把它當成整列的唯一新鮮度來源 = D-3)
    if _has_value(_li):
        _a, _lg, _rs = _asof_of_df(_li, date_col=LEADING_DATE_COL, tab="籌碼 li_latest",
                                   today=today)
        _e, _l, _at = _level_from_asof(_a, _lg, _rs, cadence="daily", today=today)
        _chip_levels.append((_e, f"先行 {_l}"))
        _chip_asof = _chip_asof or _at
    _f3e, _f3l = worst_freshness(_chip_levels) if _chip_levels else ("⬜", "未載入")

    _detail3 = (" ｜ ".join(
        f"{_lbl} {'✓' if (_cl_is_dict and _has_value(_cl.get(_k))) else '✗'}"
        for _k, _lbl in _cl_keys)
        if _has_value(_cl) else "在 🌍 總經 Tab 載入籌碼觸發")

    # ── 三條強制降級(§1 Fail Loud:壞掉要說出來,不能用綠燈蓋過去)──────
    # 覆蓋率再滿,只要值本身可疑,整列一律降到 🟡 並在細項講清楚是哪一種可疑。
    _warns = []
    # (a) D-1b 值凍結 —— 本輪事故的主偵測器
    # 排序 + 偵測 + 摘要全在 L0 `leading_frozen_columns` 裡(它自己排序,
    # 消掉「每個 caller 都要記得先排序」這個必然會漏的步驟)。
    _n_frozen, _frozen_cols = leading_frozen_columns(_li)
    if _n_frozen:
        _warns.append(f"🧊 {_n_frozen} 欄數值凍結（連續 {FROZEN_STALE_PERIODS_LEADING} "
                      f"期一階差分為 0）：{'/'.join(str(c) for c in _frozen_cols)}")
    # (b) 走了 stale pickle fallback(旗標版;只在 pickle 未超齡時才會出現)
    _li_stale, _li_age = _li_frozen_info(_li)
    if _li_stale:
        _age_txt = (f"{_li_age:.0f} 分鐘" if isinstance(_li_age, (int, float))
                    else "未知時長")
        _warns.append(f"📦 先行指標沿用過期快取（{_age_txt} 未更新）")
    # (c) D-1c 本輪抓取失敗但畫面沿用上一輪 li_latest(tab_macro 寫的降級標記)
    _retain = _get("li_retain_meta") or {}
    if _has_value(_li) and isinstance(_retain, dict) and _retain.get("rounds"):
        _warns.append(f"♻️ 先行指標最近 {_retain.get('rounds')} 輪抓取都失敗，"
                      f"畫面沿用 {str(_retain.get('since', ''))[:16]} 那份舊資料")
    if _warns:
        _e3 = downgrade_to_warn(_e3)
        # 新鮮度燈:原本是綠燈或「不可知」→ 改標「值可疑」(日期看起來很新,但值是死的,
        # 正是本次事故的形狀);原本已是黃/紅 → 保留它自己的落後天數,不覆寫成更模糊的字。
        if _f3e in ("🟢", "⬜"):
            _f3e, _f3l = "🟡", "值可疑"
        _detail3 += " ｜ " + " ｜ ".join(_warns)

    rows.append({
        "tab": "💰 籌碼面",
        "emoji": _e3, "color": _hex(_e3),
        "ratio_txt": f"{_cl_have}/{len(_cl_keys)}" if _has_value(_cl) else "未載入",
        "detail": _detail3,
        "action": "缺資料 → TWSE 三大法人 / 融資餘額 API",
        "fresh_emoji": _f3e, "fresh_label": _f3l, "fresh_color": _hex(_f3e),
        "fresh_asof": _chip_asof,
    })

    # ══ 🏦 ETF:etf_single_data(單一 ETF dict)═══════════════════════
    _e1d = _get("etf_single_data") or {}
    _etf_is_dict = isinstance(_e1d, dict)
    _etf_loaded = _etf_is_dict and bool(_e1d)
    _e4 = "🟢" if _etf_loaded else "⬜"
    _detail4 = ("ETF 資料已載入" if _etf_loaded else "在 🏦 ETF Tab 查 ETF 代號觸發")
    _err_nav = _e1d.get("_err_nav") if _etf_is_dict else None
    if _etf_loaded and _err_nav:
        # NAV 抓不到 = 折溢價整段不可信(v18.442 假折溢價事故的入口),不得純綠燈
        _e4 = downgrade_to_warn(_e4)
        _detail4 += f" ｜ ⚠️ NAV 缺:{str(_err_nav)[:50]}"
    # D-4:nav_date **巢狀在 premium 內**,原本讀 top-level `nav_date` → 永遠 ⬜。
    _a4, _lag4, _rsn4 = _asof_of_mapping(_e1d, _ASOF_PATHS_ETF,
                                         tab="ETF etf_single_data", today=today)
    if _rsn4 != "ok":
        # premium 三個日期都沒有時,退用價格序列的最後一根 K(誠實標示這是價格日)
        _a4, _lag4, _rsn4 = _asof_of_df_index(
            _e1d.get("price_df") if _etf_is_dict else None, tab="ETF price_df",
            today=today)
    _f4e, _f4l, _f4a = _level_from_asof(_a4, _lag4, _rsn4, cadence="daily", today=today)
    rows.append({
        "tab": "🏦 ETF",
        "emoji": _e4, "color": _hex(_e4),
        "ratio_txt": "已查" if _etf_loaded else "未查",
        "detail": _detail4,
        "action": "缺資料 → etf_fetch fallback chain",
        "fresh_emoji": _f4e, "fresh_label": _f4l, "fresh_color": _hex(_f4e),
        "fresh_asof": _f4a,
    })

    return rows


def render_data_coverage() -> None:
    """渲染前 N Tab「有值 / 新鮮度」表(Fund 風格 Section ⓪)。"""
    st.markdown("### ⓪ 📊 各 Tab 資料檢查表（有值 × 新鮮度）")
    st.caption(
        "**「有值」欄只回答『這個欄位不是空的』,不回答『值是不是活的』** —— "
        "後者看右邊「新鮮度」欄(量的是**資料日期 as-of**,不是抓取時間),"
        "以及細項裡的 🧊 凍結 / 📦 過期快取 / ♻️ 沿用上輪 三種降級標記。"
        f"日頻紅燈門檻走 SSOT `STALE_DAYS_DAILY={STALE_DAYS_DAILY}` 日,"
        f"黃燈起點本頁刻意較嚴({_DIAG_DAILY_WARN_DAYS} 日)。"
        "**月頻(PMI / CPI / 出口 / NDC / Fed)不用天數判定** —— 它們的資料日是"
        "「資料月月初」,當期最新一筆天生就是 60~90 天前;改判"
        "「距預期最新資料月**落後幾期**」:當期 🟢 ／ 下期已逾原定發布日但仍在"
        "緩衝內 🟡 ／ 真的漏掉整期 🔴。"
    )

    rows = compute_tab_coverage()

    _grid = "grid-template-columns:1.0fr 0.5fr 0.7fr 1.0fr 2.6fr 1.5fr"
    _th = ("font-size:10px;color:#888;font-weight:700;padding:8px 10px;"
           "border-bottom:1px solid #30363d")
    _td = "font-size:11px;padding:8px 10px;line-height:1.4"
    _html = (
        f"<div style='display:grid;{_grid};"
        f"background:#0d1117;border-radius:6px 6px 0 0'>"
        f"<span style='{_th}'>Tab</span>"
        f"<span style='{_th};text-align:center'>狀態</span>"
        f"<span style='{_th}'>有值</span>"
        f"<span style='{_th}'>新鮮度（資料日）</span>"
        f"<span style='{_th}'>細項</span>"
        f"<span style='{_th}'>缺資料時排查</span>"
        f"</div>"
    )
    for r in rows:
        _bg = ("#0a1a0a" if r["emoji"] == "🟢" else
               ("#1a1200" if r["emoji"] == "🟡" else
                ("#1a0606" if r["emoji"] == "🔴" else "#0d1117")))
        _fe = r.get("fresh_emoji", "⬜")
        _fl = r.get("fresh_label", "未知")
        _fc = r.get("fresh_color", _C_IDLE)
        _fa = r.get("fresh_asof", "")
        _fa_html = (f"<br><span style='color:#777;font-size:10px'>資料日 {_fa}</span>"
                    if _fa else "")
        _html += (
            f"<div style='display:grid;{_grid};"
            f"background:{_bg};border-bottom:1px solid #21262d'>"
            f"<span style='{_td};color:#e6edf3;font-weight:600'>{r['tab']}</span>"
            f"<span style='{_td};text-align:center;color:{r['color']};font-size:14px'>{r['emoji']}</span>"
            f"<span style='{_td};color:{r['color']};font-weight:600'>{r['ratio_txt']}</span>"
            f"<span style='{_td};color:{_fc};font-weight:600'>{_fe} {_fl}{_fa_html}</span>"
            f"<span style='{_td};color:#bbb'>{r['detail']}</span>"
            f"<span style='{_td};color:#888;font-size:10px'>{r['action']}</span>"
            f"</div>"
        )
    st.markdown(
        f"<div style='border:1px solid #30363d;border-radius:6px;overflow:hidden'>"
        f"{_html}</div>", unsafe_allow_html=True,
    )

    _emojis = [r["emoji"] for r in rows]
    _fresh = [r.get("fresh_emoji", "⬜") for r in rows]
    # 「完整」→「有值」:這個燈從頭到尾就只檢查了「欄位不是空的」,
    # 用「完整」二字會跟同一段 caption 的「覆蓋率 ≠ 新鮮度」直接互抵。
    st.caption(
        f"全 {len(rows)} 個資料 Tab｜🟢 幾乎全有值 {_emojis.count('🟢')}　"
        f"🟡 部分有值/有疑慮 {_emojis.count('🟡')}　🔴 多數缺值 {_emojis.count('🔴')}　"
        f"⬜ 未觸發 {_emojis.count('⬜')}　"
        "｜下方 API Key + Proxy 雙跑診斷可定位根因"
    )
    st.caption(
        f"新鮮度（依資料日期）｜🟢 在合理發布窗內 {_fresh.count('🟢')}　"
        f"🟡 落後/可疑 {_fresh.count('🟡')}　🔴 已逾期 {_fresh.count('🔴')}　"
        f"⬜ 不可知 {_fresh.count('⬜')}　"
        "｜⬜「無資料日期」代表容器有值但取不到 as-of（多半是欄位契約變了），"
        "與「未載入」不同,兩者都不可當成「資料是新的」"
    )
