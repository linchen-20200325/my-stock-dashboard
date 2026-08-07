# -*- coding: utf-8 -*-
"""shared/staleness.py — 資料時效 SSOT（L0 純函式，A~E backlog 批次2）。

第八份 review §3.1:時效驗證應發生在**資料回應層**(拿到資料當下),而非只在
cache 層或事後診斷燈號。核心 = 算「預期最新交易日」(扣週末 + 可選休市日),
與資料實際最新日期比對得 `staleness_days`,讓下游「即時多空判斷」強制過閘 ——
**過期資料可顯示,但必須標記,且不得餵給當下決策**(對應 STATE 記錄的 v18.442
ETF 假折溢價事故:過時 NAV 被硬戳今日 → 假 🔴 嚴禁追高)。

設計原則(§8.1 自評過度設計):
- **不硬編全年台股休市日曆**(維護負擔);只扣週末 + 呼叫端可選傳入 holidays set。
  真需要精確休市日(春節長假等)再由 caller 注入,本模組不預設。
- 純函式,無 I/O,無 streamlit 依賴 → 可單測、可被全層 import。
- 既有散落實作(app_stock_fetchers._expected_latest_trading_date)委派至此,消重複。
"""
from __future__ import annotations

import datetime as _dt
from typing import Optional


def expected_latest_trading_day(
    today: Optional[_dt.date] = None,
    holidays: Optional[set] = None,
) -> _dt.date:
    """預期最新交易日:自 today 起,往前退到最近一個非週末、非休市日。

    Parameters
    ----------
    today : date | None
        基準日;None → `date.today()`(呼叫端可注入以利測試/時區控制)。
    holidays : set[date] | None
        休市日集合(選填)。台股春節長假等由 caller 注入;None → 只扣週末。

    Returns
    -------
    date
        最近的預期交易日(weekday 0-4 且不在 holidays)。
    """
    d = today or _dt.date.today()
    _hol = holidays or set()
    # 上限 400 次防禦(holidays 若被誤傳整年會停;正常 1-4 次即命中)
    for _ in range(400):
        if d.weekday() < 5 and d not in _hol:
            return d
        d -= _dt.timedelta(days=1)
    return d


def staleness_days(
    data,
    *,
    date_col: str = "date",
    today: Optional[_dt.date] = None,
    holidays: Optional[set] = None,
) -> Optional[int]:
    """資料最新日期距「預期最新交易日」幾個日曆天。

    Parameters
    ----------
    data : pd.DataFrame | date | datetime | str | pd.Timestamp | None
        - DataFrame:取 `data[date_col]` 的 max 為最新日
        - date/datetime/str/Timestamp:直接視為最新日
    date_col : str
        DataFrame 的日期欄名(預設 "date")。
    today / holidays : 同 expected_latest_trading_day。

    Returns
    -------
    int | None
        `(預期最新交易日 - 資料最新日).days`;無法判定(空/缺欄/無法解析)回 None。
        正數 = 落後;0 = 當期;負數(資料比預期新,罕見)= 亦回實際差值。
    """
    latest = _extract_latest_date(data, date_col=date_col)
    if latest is None:
        return None
    exp = expected_latest_trading_day(today=today, holidays=holidays)
    return (exp - latest).days


def latest_date(
    data,
    *,
    date_col: str = "date",
) -> Optional[_dt.date]:
    """取資料的「最新資料日期(as-of)」;無法判定回 None。

    與 `staleness_days` 共用同一份萃取邏輯(`_extract_latest_date`),差別只在
    本函式回**日期本身**、前者回**落後天數**。UI 常常兩個都要(「🟡 落後3日
    (資料日 08/01)」),抽出來避免呼叫端各自再寫一份 pandas 日期解析而漂移。

    接受型別同 `staleness_days`:DataFrame / date / datetime / str / Timestamp。
    """
    return _extract_latest_date(data, date_col=date_col)


def gate_for_realtime(
    days: Optional[int],
    *,
    max_days: int = 1,
) -> tuple[bool, str]:
    """時效閘:回 (可否用於即時多空判斷, 使用者提示字串)。

    - days is None      → (False, 無法確認日期,暫不納入即時判斷)
    - days > max_days   → (False, N 交易日前資料,僅供歷史參考,未納入即時燈號)
    - 否則               → (True, "")

    §1 Fail-Loud:無法確認新鮮度時 fail-safe 排除(不假裝新鮮餵決策)。
    """
    if days is None:
        return False, "⚠️ 無法確認資料日期，暫不納入即時多空判斷。"
    if days > max_days:
        return False, (f"⚠️ 此數據為 {days} 天前的資料，僅供歷史參考，"
                       "未納入即時燈號。")
    return True, ""


def stale_tag(days: Optional[int], *, threshold: int = 40) -> str:
    """AI prompt 用的時效標籤:days > threshold → "[STALE:Nd] ",否則空字串。

    對齊 Fund 端既有「月度指標 >40 天注入 [STALE] 防 AI 當當期講」慣例,SSOT 化。
    """
    if days is not None and days > threshold:
        return f"[STALE:{days}d] "
    return ""


# ── 頻率感知「合理最舊」門檻(日曆天)──────────────────────────────────────
# 不同發布頻率的資料,其「自然發布延遲」差異極大;拿日頻標準套季頻會把「當期最新一筆」
# 誤標過期。門檻 = 該頻率下一筆資料「合理仍是最新」的最大 as_of 年齡,超過才算真過期。
STALE_DAYS_DAILY = 7          # 日頻(報價/三大法人/大盤 regime):扣週末+短假仍應 ≤7d
STALE_DAYS_MONTHLY = 45       # ⚠️ 僅適用「as_of = 資料月**月底**」的月頻序列。
                              #   推導:月底 as_of + 月後 ~10-13d 公布 + 一點緩衝 = ~45d。
                              #   ❌ **不得**用於 as_of 落在**月初**的序列(macro_info 的
                              #   PMI / CPI / 出口 / NDC / Fed 全部是月初)—— 那些指標
                              #   當期最新一筆的 as_of 年齡天生就是 63~89 天,套 45d
                              #   等於每天都亮假紅燈。月初 as_of 一律走本檔下方的
                              #   `monthly_periods_behind`(以「期」為單位,見 G2 區塊)。
                              #   G2 2026-08-08 起本常數在 production **無消費端**,
                              #   保留是為了讓「月底 as_of」型序列日後仍有 SSOT 可用。
STALE_DAYS_QUARTERLY = 150    # 季頻(台股季報):as_of=季末,季後~45d 才公告,下一季相隔~91d →
                              #   最新一季在下季公告前 as_of 年齡可達~136d;+FinMind 鏡像寬限~14d
                              #   = 91+45+14 = 150d。(例:力積電 Q1 as_of 3/31,7/15 為 106d < 150d
                              #   → 仍是最新一季,不該標過期;若 9 月還停在 Q1 → >150d 正確標過期)

_STALE_DAYS_BY_CADENCE = {
    "daily": STALE_DAYS_DAILY,
    "monthly": STALE_DAYS_MONTHLY,
    "quarterly": STALE_DAYS_QUARTERLY,
}


def stale_days_threshold(cadence: str = "daily") -> int:
    """依資料發布頻率回「合理最舊」門檻(日曆天)。

    未知 / 未指定 cadence → 退 daily(最嚴門檻;§1 Fail-Loud 寧可保守標過期也不放水)。
    """
    return _STALE_DAYS_BY_CADENCE.get(cadence, STALE_DAYS_DAILY)


# ── 月頻總經指標:發布延遲 SSOT + 「as_of 還算當期」門檻(G1 2026-08-07)────────
#
# 【為什麼不能拿 STALE_DAYS_MONTHLY(45) 去量這些指標】
# 這幾個指標的 `date` 欄是**資料歸屬月的月初**,不是公布日
# (evidence: `macro_core.fetch_tw_pmi` 各源一律組 'YYYY-MM-01';
#  `macro_snapshot._parse_customs_export_csv` 回 'YYYY-MM';
#  FRED CPILFESL / FEDFUNDS 的 observation date 本來就是月初)。
# 於是同一筆「當期最新」資料,它的 as_of 年齡會從剛公布一路長到下一期公布前:
#
#     as_of(M 月資料)  = M/01
#     M   月資料公布   ≈ (M+1) 月底 + lag
#     M+1 月資料公布   ≈ (M+2) 月底 + lag      ← 到這一刻 M 月才被取代
#     ⇒ M 月資料「仍是最新」時,as_of 年齡最大 ≈ 62 天 + lag
#
# 2026-08-07 實算:美國核心 CPI 最新一筆是 6 月(as_of 2026-06-01,~7/15 公布,
# ~8/13 才被 7 月取代)⇒ as_of 年齡 67 天。用 40d(`build_llm_context` 原寫死值)
# 或 45d(STALE_DAYS_MONTHLY)去量,**一筆完全當期的 CPI 每天都會被標成過期**。
# 一個 100% 觸發的警告等於沒有警告 —— §1「不得把過期當當期」會被反向濫用成
# 「把當期當過期」,而 LLM 只會學會忽略這個標記。故門檻必須按**發布週期**推導。
#
# lag 值來源:CLAUDE.md §2.3「各來源發布延遲 + 修正風險」表(自月底起算的日曆天)。
#
# ⚠️ 名稱是歷史遺留(G1 建立時只服務 macro_info)。G2 起本表是**所有月頻序列**的
#    發布延遲登記處(含個股月營收 / M1B-M2),不限 macro。改名會動到既有 import,
#    ROI 低,故只在此說明。新增月頻資料源請在此登記一筆,否則走不到精確判定。
MACRO_PUBLICATION_LAG_DAYS: dict[str, int] = {
    "ism_pmi":     1,    # 台灣 PMI(CIER;session key 沿用 'ism_pmi'):月後第 1 營業日
    "tw_export":  10,    # 財政部 / 海關出口:月後 ~8-10 天(取上界)
    "us_core_cpi": 13,   # FRED CPILFESL:月後 ~13 天
    "fed_funds":   5,    # FRED FEDFUNDS:月後數日
    "ndc_signal": 27,    # 國發會景氣對策信號:月後 ~27 天
    # ── G2 2026-08-08 補登(健診儀表板的月頻列亦需精確判定)────────────
    "tw_monthly_revenue": 10,  # 個股月營收(FinMind/MOPS):月後 ~10 天(CLAUDE.md §2.3)
    "m1b_m2":              7,  # CBC M1B/M2:月後 ~5-7 天(取上界,CLAUDE.md §2.3)
}

#: as_of(月初)→ 下一期公布的最大跨度(31 天 × 2 個月)。
MONTHLY_SUPERSEDE_SPAN_DAYS = 62
#: 上游自己晚幾天發布的緩衝 —— 不為「來源遲到 3 天」亮假紅燈。
MONTHLY_PUBLICATION_MARGIN_DAYS = 7


def monthly_stale_threshold(indicator: str) -> int:
    """月頻總經指標的「as_of 還能算當期」最大日曆天數。

    threshold = 62(as_of 月初 → 下一期公布的跨度) + 該指標發布延遲 + 7 天緩衝。

    ⚠️ **這是 `monthly_periods_behind` 的保守日曆天投影,不是月頻的判準本體**
    (G2 2026-08-08)。62 取的是「連續兩個月最長跨度」(12/01→02/01 = 62 天),
    對短月組合(01/01→03/01 = 59 天)會鬆 3 天 —— 也就是存在一個窄窗口:
    資料**已經漏掉一整期**,天數卻還沒過門檻(見 `monthly_periods_behind`
    docstring 的實例)。方向上本函式只會**偏綠**,不會製造假紅。

    只在「呼叫端手上只有一個天數、拿不到 as_of 月份」時使用(現況:
    `ai_structured_summary.macro_stale_prefix` 的 prompt 標記路徑,
    它輸出的字面就是 `[STALE:Nd]` 天數)。**UI 燈號一律走
    `monthly_periods_behind` / `data_freshness.monthly_freshness_level`。**

    Parameters
    ----------
    indicator : str
        `macro_info` 的 key(`ism_pmi` / `tw_export` / `us_core_cpi` /
        `fed_funds` / `ndc_signal`)。

    Raises
    ------
    KeyError
        未登錄的指標。**刻意不給預設值**(§1 Fail Loud,對齊
        `ai_structured_summary.danger_rule_text` 的既有慣例):
        隨便回一個門檻 = 用錯誤的尺去量新指標,比沒有標記更危險。
        新增月頻指標請在 `MACRO_PUBLICATION_LAG_DAYS` 補一筆發布延遲。
    """
    _lag = MACRO_PUBLICATION_LAG_DAYS[indicator]
    return MONTHLY_SUPERSEDE_SPAN_DAYS + _lag + MONTHLY_PUBLICATION_MARGIN_DAYS


# ══════════════════════════════════════════════════════════════════════
# 月頻新鮮度的**判準本體**:落後幾個「發布期」(G2 2026-08-08)
# ══════════════════════════════════════════════════════════════════════
#
# 【為什麼不是「距今幾天」】
# 月頻資料以**月**為發布單位,as_of 又固定落在資料月月初(evidence 見上方 G1
# 區塊)。拿日曆天當判準,等於用一把刻度會漂的尺量一個離散的東西:
#
#   * 門檻設小(`STALE_DAYS_MONTHLY=45`)→ 當期最新一筆天天亮假紅
#     (G2 之前 `data_coverage` 的實況:🌍 總經列的新鮮度燈永遠 🔴);
#   * 門檻設大(62 + lag + margin)→ 短月組合會出現**假綠**窗口。
#     實例:今天 2026-03-10,台灣 PMI 最新一筆停在 2026-01-01。
#           2 月 PMI 早該在 3/01 + lag(1) + 緩衝(7) = 3/08 前公布,
#           它確實漏了整整一期;但 as_of 年齡只有 68 天 < 門檻 70 天
#           → 日曆天規則會說「還新鮮」。**這是掩蓋問題,§1 不可接受。**
#
# 故月頻的唯一判準是「**as_of 距預期最新資料月幾期**」:
#   資料月 M 的 as_of      = M/01
#   資料月 M 的應發布日     = (M+1)/01 + 發布延遲(lag) [+ 緩衝(margin)]
#   預期最新資料月(今天)   = 最大的 M 使得 應發布日 ≤ today
#   periods_behind         = 月序(預期最新資料月) − 月序(as_of)
#
# periods_behind ≤ 0 → 當期(甚至比預期還新);≥ 1 → 真的漏掉整期。
# 「緩衝」只推遲「開始期待下一期」的時點,不改變期數語意 ——
# 上游遲到 3 天不該亮紅,但遲到到下一期都出來了就必須亮紅。


def _month_index(d: _dt.date) -> int:
    """把日期壓成連續月序(y*12 + m-1),讓「差幾個月」變成單純減法。"""
    return d.year * 12 + (d.month - 1)


def _month_start(d: _dt.date) -> _dt.date:
    return _dt.date(d.year, d.month, 1)


def _add_months(d: _dt.date, n: int) -> _dt.date:
    """月初 + n 個月(回月初)。不用 dateutil,避免為了三行加一個相依。"""
    _t = _month_index(d) + n
    return _dt.date(_t // 12, _t % 12 + 1, 1)


def _resolve_monthly_lag(
    indicator: Optional[str],
    lag_days: Optional[int],
) -> Optional[int]:
    """取某月頻序列的發布延遲(日曆天);判不出來回 None。

    - `lag_days` 明給 → 用它(供未登錄但呼叫端確知延遲的序列,如探測型列)。
    - `indicator` 已登錄 → 查 `MACRO_PUBLICATION_LAG_DAYS`。
    - 兩者都給 → `ValueError`(語意衝突,不猜)。
    - 都沒有 / 未登錄 → **回 None** + loud log。

    §1 為什麼這裡回 None 而不是像 `monthly_stale_threshold` 那樣 raise:
    兩者的下游代價不同。`monthly_stale_threshold` 服務 **LLM prompt**,
    一個錯的過期標記會被 AI 當事實寫進建議 → 必須當場炸。本函式服務
    **診斷頁燈號**,炸掉會讓整張「用來找問題的表」變成 traceback;
    回 None 讓上層顯示 ⬜「門檻未登錄」——**既不假裝新鮮也不假裝過期**,
    而且未登錄這件事本身會直接顯示在畫面上(比躲在 log 裡更容易被修)。
    """
    if lag_days is not None and indicator is not None:
        raise ValueError(
            "monthly lag 同時給了 indicator 與 lag_days,語意衝突;請只給一個")
    if lag_days is not None:
        _v = int(lag_days)
        if _v < 0:
            raise ValueError(f"發布延遲不得為負:lag_days={lag_days!r}")
        return _v
    if indicator is None:
        print("[staleness] ⚠️ 月頻新鮮度缺 indicator/lag_days → 無法判定(回 None)")
        return None
    _lag = MACRO_PUBLICATION_LAG_DAYS.get(indicator)
    if _lag is None:
        print(f"[staleness] ⚠️ 月頻指標未登錄發布延遲,無法判定新鮮度: {indicator!r}"
              f"(請在 MACRO_PUBLICATION_LAG_DAYS 補一筆)")
    return _lag


def expected_latest_data_month(
    *,
    lag_days: int,
    today: Optional[_dt.date] = None,
    grace_days: Optional[int] = None,
) -> _dt.date:
    """今天「應該已經拿得到」的最新資料月,以該月**月初**表示(= as_of 語意)。

    Parameters
    ----------
    lag_days : int
        該序列自資料月月底起算的發布延遲(日曆天)。
    today : date | None
        基準日;None → `date.today()`(測試/時區控制請注入)。
    grace_days : int | None
        上游遲到緩衝;None → `MONTHLY_PUBLICATION_MARGIN_DAYS`。
    """
    _d = today or _dt.date.today()
    _grace = (MONTHLY_PUBLICATION_MARGIN_DAYS if grace_days is None
              else int(grace_days))
    _cand = _add_months(_month_start(_d), -1)
    # 迴圈上限 24:lag+grace 現況 < 40 天,正常 1~2 次命中;上限純屬防禦
    # (若有人登錄了荒謬的 lag,寧可回一個很舊的月份也不要無窮迴圈)。
    for _ in range(24):
        if _add_months(_cand, 1) + _dt.timedelta(days=int(lag_days) + _grace) <= _d:
            return _cand
        _cand = _add_months(_cand, -1)
    return _cand


def monthly_publication_due(
    data_month,
    *,
    indicator: Optional[str] = None,
    lag_days: Optional[int] = None,
    grace_days: int = 0,
) -> Optional[_dt.date]:
    """某資料月的「最晚應發布日」= 次月 1 日 + 發布延遲 (+ 緩衝)。

    `data_month` 接受任何 `staleness_days` 支援的型別(取其所屬月份)。
    判不出月份 / 判不出延遲 → None。
    """
    _d = _extract_latest_date(data_month, date_col="date")
    if _d is None:
        return None
    _lag = _resolve_monthly_lag(indicator, lag_days)
    if _lag is None:
        return None
    return _add_months(_month_start(_d), 1) + _dt.timedelta(
        days=int(_lag) + int(grace_days))


def monthly_periods_behind(
    as_of,
    *,
    indicator: Optional[str] = None,
    lag_days: Optional[int] = None,
    today: Optional[_dt.date] = None,
    grace_days: Optional[int] = None,
) -> Optional[int]:
    """月頻資料落後「預期最新資料月」幾個發布期。

    Parameters
    ----------
    as_of :
        資料歸屬日期(月初);型別同 `staleness_days`
        (DataFrame / date / datetime / 'YYYY-MM' / 'YYYY-MM-DD' / Timestamp)。
    indicator / lag_days :
        擇一給。`indicator` 查 `MACRO_PUBLICATION_LAG_DAYS`;`lag_days` 直接給值。
    today : date | None
        基準日(測試必須注入,否則測試會吃執行當天日期)。
    grace_days : int | None
        上游遲到緩衝;None → `MONTHLY_PUBLICATION_MARGIN_DAYS`。
        傳 0 = 嚴格版(「原定發布日已過但還在緩衝內」也算落後),
        供上層區分「🟡 上游遲到」與「🔴 真的漏了一期」。

    Returns
    -------
    int | None
        `≤ 0` → 當期(0 = 正好是預期那一期;負數 = 比預期還新,罕見但合法);
        `≥ 1` → 漏掉 N 個發布期;
        `None` → as_of 無法解析,或該序列未登錄發布延遲(§1:不確定 ≠ 新鮮)。
    """
    _asof = _extract_latest_date(as_of, date_col="date")
    if _asof is None:
        return None
    _lag = _resolve_monthly_lag(indicator, lag_days)
    if _lag is None:
        return None
    _exp = expected_latest_data_month(
        lag_days=_lag, today=today, grace_days=grace_days)
    return _month_index(_exp) - _month_index(_month_start(_asof))


def monthly_release_status(
    as_of,
    *,
    indicator: Optional[str] = None,
    lag_days: Optional[int] = None,
    today: Optional[_dt.date] = None,
) -> tuple[Optional[int], Optional[int]]:
    """月頻新鮮度的**單一 producer**:回 `(periods_behind, overdue_days)`。

    - `periods_behind`:含緩衝的落後期數(≥1 = 真的漏了整期)。
    - `overdue_days`:預期的下一期已超過**原定發布日**幾天(0 = 未逾期)。
      只在 `periods_behind ≤ 0` 時有意義,供上層畫「🟡 上游遲到中」。
    - 任一判不出來 → `(None, None)`。

    UI 端請一律呼叫 `data_freshness.monthly_freshness_level`(它包裝本函式
    並負責翻成 emoji/label),不要各自再組一次燈號規則。
    """
    _behind = monthly_periods_behind(
        as_of, indicator=indicator, lag_days=lag_days, today=today)
    if _behind is None:
        return (None, None)
    if _behind >= 1:
        return (_behind, 0)
    # 當期:再用「零緩衝」量一次 —— 若嚴格版已落後,代表下一期原定發布日過了
    # 但還沒到,且仍在緩衝內 → 回逾期天數讓 UI 畫黃燈。
    _strict = monthly_periods_behind(
        as_of, indicator=indicator, lag_days=lag_days, today=today, grace_days=0)
    if _strict is None or _strict <= 0:
        return (_behind, 0)
    _due = monthly_publication_due(
        _add_months(_month_start(_extract_latest_date(as_of, date_col="date")),
                    _strict),
        indicator=indicator, lag_days=lag_days)
    if _due is None:
        return (_behind, 0)
    _od = ((today or _dt.date.today()) - _due).days
    return (_behind, max(0, _od))


# ── 內部:多型別日期萃取 ────────────────────────────────────────────────
def _extract_latest_date(data, *, date_col: str) -> Optional[_dt.date]:
    if data is None:
        return None
    # DataFrame(或有 columns 屬性者)
    _cols = getattr(data, "columns", None)
    if _cols is not None:
        try:
            if getattr(data, "empty", False) or date_col not in _cols:
                return None
            import pandas as _pd
            _s = _pd.to_datetime(data[date_col], errors="coerce").dropna()
            if _s.empty:
                return None
            return _s.max().date()
        except Exception:
            return None
    # date / datetime
    if isinstance(data, _dt.datetime):
        return data.date()
    if isinstance(data, _dt.date):
        return data
    # str / Timestamp 等 → 交給 pandas 寬鬆解析
    try:
        import pandas as _pd
        _ts = _pd.to_datetime(data, errors="coerce")
        if _ts is None or _pd.isna(_ts):
            return None
        return _ts.date()
    except Exception:
        return None
