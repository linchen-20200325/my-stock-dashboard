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

# L0 → L0(`roc_calendar` 無任何 import,不會成環)。季頻 SSOT 對外回民國年,
# ±1911 這一步一律走既有 SSOT,不在本檔再寫一次 magic number(§3.3)。
from shared.roc_calendar import gregorian_to_roc_year as _greg_to_roc


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
STALE_DAYS_QUARTERLY = 150    # ⚠️ 僅適用「季後固定 ~45 天公告、且每季間隔相同」的假想季頻序列。
                              #   推導(v19.127 原文):91(一季)+45(公告延遲)+14(FinMind 鏡像寬限)=150。
                              #   ❌ **不得**用於**台股季報** —— 台股的公告截止日不是「季末 + 固定
                              #   延遲」,而是**四個固定日曆日**:Q1 5/15、Q2 8/14、Q3 11/14、
                              #   Q4(年報)次年 3/31。前三季確實是季末 +45 天,但 **Q3 之後要等
                              #   4.5 個月**才有下一份(年報)⇒ Q3 當期最新一筆的 as_of 年齡上限是
                              #   **196 天**(9/30 → 次年 4/14 含鏡像寬限),遠超 150
                              #   ⇒ 每年約 3/02–4/14 對一份完全當期的 Q3 財報亮假紅。
                              #   台股季報一律走本檔下方的 `quarterly_periods_behind` /
                              #   `quarterly_release_status`(以「期」為單位,見 G3 區塊)。
                              #   G3 2026-08-08 起本常數在 production **無消費端**,
                              #   保留是為了讓「等距季頻」型序列日後仍有 SSOT 可用。

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


def _month_from_index(i: int) -> _dt.date:
    """月序 → 該月月初日期(`_month_index` 的反函式)。"""
    return _dt.date(i // 12, i % 12 + 1, 1)


def _month_start(d: _dt.date) -> _dt.date:
    return _dt.date(d.year, d.month, 1)


def _add_months(d: _dt.date, n: int) -> _dt.date:
    """月初 + n 個月(回月初)。不用 dateutil,避免為了三行加一個相依。"""
    return _month_from_index(_month_index(d) + n)


# ══════════════════════════════════════════════════════════════════════
# 「以發布期為單位」的共用核心(G3 2026-08-08 自月頻抽出,月頻/季頻共用)
# ══════════════════════════════════════════════════════════════════════
#
# 月頻(G2)與季頻(G3)共用的是**判準骨架**,不是門檻:
#     ① 期別 → 連續序號(讓「差幾期」變成減法);
#     ② 期別序號 → 該期的「應發布日」;
#     ③ 今天應該拿得到的最新期 = 最大的 i 使得 due(i) + grace ≤ today;
#     ④ 三態:落後 ≥1 期 → 紅;否則看下一期是否已過**原定**發布日 → 黃;否則綠。
# ③④ 兩步是所有 off-by-one 與 grace 語意錯誤的溫床,故抽成共用函式,
# 讓月頻與季頻**不可能**在這兩步上漂移。
#
# ⚠️ **② 不能共用**,這是月頻與季頻唯一的實質差異:
#     月頻 due(M)   = (M+1)/01 + 該序列的發布延遲(lag)   ← 每期同一個 lag
#     季頻 due(Q)   = 台股**法定公告截止日**(固定日曆日)  ← 每季不同,且 Q4 差很多
#                     Q1 5/15 / Q2 8/14 / Q3 11/14 / Q4(年報)次年 3/31
# 若硬把季頻寫成「季末 + lag」,Q1~Q3 的 lag 是 45 天、Q4 是 90 天 —— 不是同一個數,
# 套任何單一 lag 都會錯一整季(這正是 `STALE_DAYS_QUARTERLY=150` 的病根)。
# 故 due 由各頻率各自提供一個小函式注入,其餘全部共用。


def _expected_latest_period_index(
    *,
    due_of_index,
    today: _dt.date,
    grace_days: int,
    start_index: int,
    max_lookback: int,
) -> int:
    """今天「應該已經拿得到」的最新期別序號 = 最大的 i 使 `due(i) + grace ≤ today`。

    `start_index` 應取一個**必定還沒到期**的期別(當期或前一期),函式由此往回退。
    `max_lookback` 純屬防禦:若有人注入了荒謬的 due 函式,寧可回一個很舊的期別
    也不要無窮迴圈(§1:回舊 = 偏向「標過期」= 保守,不會把過期講成新鮮)。
    """
    _cand = int(start_index)
    for _ in range(int(max_lookback)):
        if due_of_index(_cand) + _dt.timedelta(days=int(grace_days)) <= today:
            return _cand
        _cand -= 1
    return _cand


def _release_status_from_parts(
    *,
    behind_graced: Optional[int],
    behind_strict: Optional[int],
    asof_index: int,
    due_of_index,
    today: _dt.date,
) -> tuple[Optional[int], Optional[int]]:
    """三態語意的共用核心:回 `(periods_behind, overdue_days)`。

    - `behind_graced ≥ 1` → 真的漏了整期,`overdue_days` 一律 0
      (已經紅了就不再談「逾期幾天」,避免 UI 同時畫兩種字);
    - 否則若**零緩衝**版已落後 → 下一期原定發布日已過但仍在緩衝內,
      回該期的逾期天數供上層畫 🟡;
    - 否則 → 當期,`(behind, 0)`。
    """
    if behind_graced is None:
        return (None, None)
    if behind_graced >= 1:
        return (behind_graced, 0)
    if behind_strict is None or behind_strict <= 0:
        return (behind_graced, 0)
    _due = due_of_index(int(asof_index) + int(behind_strict))
    return (behind_graced, max(0, (today - _due).days))


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
    # 迴圈上限 24:lag+grace 現況 < 40 天,正常 1~2 次命中;上限純屬防禦。
    return _month_from_index(_expected_latest_period_index(
        due_of_index=_monthly_due_of_index(int(lag_days)),
        today=_d, grace_days=_grace,
        start_index=_month_index(_d) - 1, max_lookback=24))


def _monthly_due_of_index(lag_days: int):
    """月頻的「期別序號 → 應發布日」:due(M) = (M+1)/01 + 發布延遲。"""
    def _due(i: int) -> _dt.date:
        return _month_from_index(i + 1) + _dt.timedelta(days=int(lag_days))
    return _due


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
    # 當期:再用「零緩衝」量一次 —— 若嚴格版已落後,代表下一期原定發布日過了
    # 但還沒到,且仍在緩衝內 → 回逾期天數讓 UI 畫黃燈。
    # (三態組裝走 `_release_status_from_parts`,與季頻共用同一份語意。)
    _strict = monthly_periods_behind(
        as_of, indicator=indicator, lag_days=lag_days, today=today, grace_days=0)
    _lag = _resolve_monthly_lag(indicator, lag_days)
    return _release_status_from_parts(
        behind_graced=_behind,
        behind_strict=_strict,
        asof_index=_month_index(
            _month_start(_extract_latest_date(as_of, date_col="date"))),
        due_of_index=_monthly_due_of_index(int(_lag)),
        today=today or _dt.date.today(),
    )


# ══════════════════════════════════════════════════════════════════════
# 季頻(台股季報)新鮮度的**判準本體**:落後幾個「發布期」(G3 2026-08-08)
# ══════════════════════════════════════════════════════════════════════
#
# 【為什麼 `STALE_DAYS_QUARTERLY = 150` 對 Q3 每年假紅】
# 台股季報的 as_of 是**季末日**(evidence:`data_loader.get_quarterly_data` 與
# `get_quarterly_bs_cf` 都補 `date` = 季末 03-31/06-30/09-30/12-31;
# `financial_statements_fetcher` 的 `period` 直接沿用 FinMind 財報 date,同為季末)。
# 而「下一份財報什麼時候出現」由**法定公告截止日**決定,它不是「季末 + 固定延遲」:
#
#     季別   as_of    法定公告截止      距下一份多久        當期最大 as_of 年齡
#     Q1     3/31     5/15   (+45d)    → Q2 8/14           136d   ✅ < 150
#     Q2     6/30     8/14   (+45d)    → Q3 11/14          137d   ✅ < 150
#     Q3     9/30     11/14  (+45d)    → **年報 次年 3/31** 182d   🔴 > 150
#     Q4     12/31    次年 3/31 (+90d) → Q1 5/15           135d   ✅ < 150
#
# Q3 公布後要等 **4.5 個月**才有下一份(年報公告期限是季末 +90 天,不是 +45)。
# 於是每年約 3/02 起,一份**完全當期**的 Q3 財報 as_of 年齡就會超過 150 天,
# 一路假紅到年報真的該出來為止 —— 每年約 30~44 天。G2 對月頻的診斷在這裡完全成立:
# **拿日曆天去量一個以「期」為發布單位的東西**,門檻設多少都會錯。
#
# 影響面比月頻嚴重:除了 `health_inspector` 的季頻列,
# `ai_qa_service._annotate_staleness` 會把它注進**送給 Gemini 的 tool result**
# ⇒ 每年 3 月,AI 會對一份當期財報說「已過期」,再據此寫進投資建議。
#
# 【判準】與月頻同一套骨架(見上方 `_expected_latest_period_index`):
#     季別 Q 的 as_of      = 該季季末
#     季別 Q 的應發布日     = 法定公告截止日 [+ 鏡像緩衝]
#     預期最新季別(今天)   = 最大的 Q 使得 應發布日 ≤ today
#     periods_behind       = 季序(預期最新季) − 季序(as_of)

#: 台股財報法定公告截止日 SSOT:`{season: (年份位移, 月, 日)}`。
#: 年份位移 = 相對於**該季所屬的西元年**;Q4 為年報,截止日落在次年 → 位移 1。
#: 來源:證交所/櫃買中心財報公告期限(Q1/Q2/Q3 季末 +45 天;Q4 年報季末 +90 天)。
#: ⚠️ 這是**台股專用**日曆。若日後接入非台股季頻序列,請另立一份 due 表,
#: **不要**把新市場的截止日塞進本 dict(§2.1 衝突裁決:不同市場不共用權威)。
TW_QUARTER_STATUTORY_DUE: dict[int, tuple[int, int, int]] = {
    1: (0, 5, 15),
    2: (0, 8, 14),
    3: (0, 11, 14),
    4: (1, 3, 31),      # 年報:次年 3/31
}

#: 各季季末的「日」(月份 = season × 3)。
_QUARTER_END_DAY: dict[int, int] = {1: 31, 2: 30, 3: 30, 4: 31}

#: 上游(FinMind 鏡像 / MOPS 同步)自己晚幾天才有資料的緩衝。
#: 14 天沿用 `STALE_DAYS_QUARTERLY` 原推導裡就已編列的「FinMind 鏡像寬限 ~14d」,
#: 不另外發明新數字;語意同月頻的 `MONTHLY_PUBLICATION_MARGIN_DAYS`
#: —— 只推遲「開始期待下一期」的時點,不改變期數語意。
QUARTERLY_PUBLICATION_MARGIN_DAYS = 14


def _quarter_index(d: _dt.date) -> int:
    """把日期壓成連續季序(y*4 + (m-1)//3),讓「差幾季」變成單純減法。

    接受該季內**任一天**(不必剛好是季末),故 as_of 若因來源差異落在
    9/30 以外的 Q3 日期也會判進同一季。
    """
    return d.year * 4 + (d.month - 1) // 3


def _quarter_year_season(i: int) -> tuple[int, int]:
    """季序 → (西元年, season 1-4)。"""
    return (i // 4, i % 4 + 1)


def _quarter_end_from_index(i: int) -> _dt.date:
    """季序 → 該季**季末日**(= 季頻 as_of 的語意,`_quarter_index` 的反函式)。"""
    _y, _s = _quarter_year_season(i)
    return _dt.date(_y, _s * 3, _QUARTER_END_DAY[_s])


def _quarter_due_of_index(i: int) -> _dt.date:
    """季序 → 該季財報的**法定公告截止日**(季頻版的 due,對應月頻的季末+lag)。"""
    _y, _s = _quarter_year_season(i)
    _off, _m, _dd = TW_QUARTER_STATUTORY_DUE[_s]
    return _dt.date(_y + _off, _m, _dd)


def expected_latest_data_quarter(
    *,
    today: Optional[_dt.date] = None,
    grace_days: Optional[int] = None,
) -> _dt.date:
    """今天「應該已經拿得到」的最新季別,以該季**季末日**表示(= as_of 語意)。

    Parameters
    ----------
    today : date | None
        基準日;None → `date.today()`(測試/時區控制請注入)。
    grace_days : int | None
        上游遲到緩衝;None → `QUARTERLY_PUBLICATION_MARGIN_DAYS`。
        傳 0 = 嚴格版(只看法定截止日),供上層區分 🟡 待公布 與 🔴 落後。
    """
    _d = today or _dt.date.today()
    _grace = (QUARTERLY_PUBLICATION_MARGIN_DAYS if grace_days is None
              else int(grace_days))
    # start 取「今天所在的季」—— 它的截止日必定還在未來(最快也是季末 +45 天),
    # 故迴圈一定從未到期處起算。上限 12(= 3 年)純屬防禦。
    return _quarter_end_from_index(_expected_latest_period_index(
        due_of_index=_quarter_due_of_index,
        today=_d, grace_days=_grace,
        start_index=_quarter_index(_d), max_lookback=12))


def latest_published_quarter(
    today: Optional[_dt.date] = None,
) -> tuple[int, int]:
    """依台股法定公告截止日,回今天「應已公布」的最新季 → **(民國年, season)**。

    Q1(3/31)~5/15、Q2(6/30)~8/14、Q3(9/30)~11/14、Q4 年報(12/31)~次年 3/31。

    **本函式是季別推導的 SSOT。** `scripts/update_fundamentals_snapshot.py`
    另有一份逐字等價的私有實作(同名函式),應改為 import 本函式 —— 兩份會漂,
    而漂掉的後果是「補抓哪一季」與「這一季新不新鮮」給出互相矛盾的答案。
    (該檔不在 G3 可改範圍,已於報告點名,待 user 裁示後收斂。)

    ⚠️ 這裡**不加**鏡像緩衝(grace=0):它回答的是法律問題(「該公布了嗎」),
    不是資料管線問題(「抓到了嗎」)。要後者請用
    `expected_latest_data_quarter()` / `quarterly_release_status()`。
    """
    _d = today or _dt.date.today()      # 只取一次,避免跨午夜時兩次取值不一致
    _y, _s = _quarter_year_season(_expected_latest_period_index(
        due_of_index=_quarter_due_of_index,
        today=_d, grace_days=0,
        start_index=_quarter_index(_d), max_lookback=12))
    return (_greg_to_roc(_y), _s)


def quarterly_publication_due(
    as_of,
    *,
    grace_days: int = 0,
) -> Optional[_dt.date]:
    """某季財報的「最晚應發布日」= 該季法定公告截止日 (+ 緩衝)。

    `as_of` 接受任何 `staleness_days` 支援的型別(取其所屬季別);
    判不出季別 → None。
    """
    _d = _extract_latest_date(as_of, date_col="date")
    if _d is None:
        return None
    return _quarter_due_of_index(_quarter_index(_d)) + _dt.timedelta(
        days=int(grace_days))


def quarterly_periods_behind(
    as_of,
    *,
    today: Optional[_dt.date] = None,
    grace_days: Optional[int] = None,
) -> Optional[int]:
    """季頻資料落後「預期最新季別」幾個發布期。

    Parameters
    ----------
    as_of :
        資料歸屬日期(季頻一律是季末日);型別同 `staleness_days`。
    today : date | None
        基準日(測試必須注入,否則測試會吃執行當天日期)。
    grace_days : int | None
        上游遲到緩衝;None → `QUARTERLY_PUBLICATION_MARGIN_DAYS`。

    Returns
    -------
    int | None
        `≤ 0` → 當期(0 = 正好是預期那一季;負數 = 比預期還新,合法);
        `≥ 1` → 漏掉 N 個發布期;
        `None` → as_of 無法解析(§1:不確定 ≠ 新鮮)。

    Notes
    -----
    與月頻不同,季頻**不需要 `indicator`** —— 台股季報的公告截止日是全市場
    一致的法定日曆,不逐序列不同。故也沒有「門檻未登錄」這個狀態。
    """
    _d = _extract_latest_date(as_of, date_col="date")
    if _d is None:
        return None
    _exp = expected_latest_data_quarter(today=today, grace_days=grace_days)
    return _quarter_index(_exp) - _quarter_index(_d)


def quarterly_release_status(
    as_of,
    *,
    today: Optional[_dt.date] = None,
) -> tuple[Optional[int], Optional[int]]:
    """季頻新鮮度的**單一 producer**:回 `(periods_behind, overdue_days)`。

    語意與 `monthly_release_status` 逐字相同(共用 `_release_status_from_parts`):
    - `periods_behind`:含緩衝的落後期數(≥1 = 真的漏了整季)。
    - `overdue_days`:預期的下一季已超過**法定公告截止日**幾天(0 = 未逾期)。
    - 任一判不出來 → `(None, None)`。

    UI 端請一律呼叫 `data_freshness.quarterly_freshness_level`(它包裝本函式
    並負責翻成 emoji/label),不要各自再組一次燈號規則。
    """
    _d = _extract_latest_date(as_of, date_col="date")
    if _d is None:
        return (None, None)
    _t = today or _dt.date.today()
    return _release_status_from_parts(
        behind_graced=quarterly_periods_behind(as_of, today=_t),
        behind_strict=quarterly_periods_behind(as_of, today=_t, grace_days=0),
        asof_index=_quarter_index(_d),
        due_of_index=_quarter_due_of_index,
        today=_t,
    )


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
