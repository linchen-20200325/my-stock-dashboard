"""src/services/macro_engine_inputs.py — 規則引擎輸入組裝＋規則引擎執行（L3 編排）。

批 Z64（freshness 第四批 F4，2026-10-14）。~~⛔ **本批不接線**：沒有任何呼叫端改用本檔；
`refresh_macro_now`、`macro_state.json`、任何頁面（含舊 UI `section_news_ai`）行為一律不變。~~
📌 **批 Z65（F5）更新 —— 有意識的更正，不是漏刪**：上句在 Z64 當天為真。Z65 起 L3
`src/services/risk_cap_apply.py` 呼叫本檔（`load_engine_inputs_from_session` → `run_rule_engine(...,
include_veto_flags=True)`），由新 UI「🚀 更新今日戰情」（`refresh_macro_now` 的 `STEP_RISK_CAP`）
寫 `macro_state.json`。舊 UI `section_news_ai` 仍不呼叫本檔、行為不變。

做什麼
──────
1. `build_engine_inputs(...)`（純函式）：L2 `src.compute.macro.dated_inputs` 抽出 9 項帶日期的
   引擎輸入 → 本檔做**型別檢查**（數值序列不收 bool）→ L0 `shared.freshness_policy` 評估新鮮度
   （PMI 前月用 `assess_previous_month`，**跟著當期走**）→ 組出：
   - `macro_numbers`：給**未修改**的 `calculate_system_state`；每一項一律取 `scoring_value`
     （非 FRESH ⇒ None ⇒ 走引擎既有「缺項不計分」路徑；客戶 2026-10-14 Q-z34 Q2=A）；
   - `red_lines`：每條硬紅線「能不能評估」（⛔ 門檻由引擎決定，這裡不重做判斷）；
   - `input_asof` / `not_evaluated` / `assessed`：可追溯資訊。
2. `load_engine_inputs_from_session(session, *, now)`：從 session 讀原始結構、讀 L1 PMI 歷史、
   取 L1 休市表 → 呼叫 1。⛔ 不寫 session、不寫檔。
3. `run_rule_engine(bundle)`：呼叫**未修改**的 `calculate_system_state(bundle.macro_numbers)`，
   回傳引擎原有鍵（一個都不覆寫）＋ `input_asof`／`not_evaluated`／`red_lines`（純資料、可 JSON 序列化）。

客戶規則（2026-10-14）
──────────────────────
- 搬遷既有風控，不重新設計：公式、門檻、權重全在 `calculate_system_state`，本檔一個都不碰。
- 缺資料不補 0、不用前值、不推定；無法計算 → 明確標「未取得／無法判定」，⛔ 不因此放寬風控。
- Q-z34 Q1=B：PMI 前月必須是真正的前一資料月（PMI 歷史 parquet），否則該紅線判「無法判定」。
- Q-z34 Q2=A：沿用「缺項不計分」；每條硬紅線缺必要輸入 → 各自標「無法判定」。
- Sahm：**沒有資料來源** ⇒ 永不觸發；`red_lines["sahm"]` 固定 `no_source` ——
  ⛔ 不得宣稱「該紅線已通過」。
- 外資期貨或 MA5 缺值 → 該紅線「無法判定」。
- Freshness（Q-z37／Q-z38）：規則 SSOT 是 `shared/freshness_policy.py`，本檔只讀。

與舊 UI 組裝（`src/ui/tabs/macro/section_news_ai.py`，原文未改）的**刻意差異**
────────────────────────────────────────────────────────────────────────
（完整新鮮資料、PMI 前月一致時，引擎原有鍵逐鍵逐值相同 —— tests/test_batch_z64.py golden 守住）
1. **PMI 前月**：舊 UI 用 session 的 `_s10_prev_pmi_value`（上次按按鈕時的當期值）；
   本檔用 PMI 歷史 parquet 的**真正前一資料月**（Q-z34 Q1=B）。兩者不同時，PMI 紅線結果可以不同。
2. **過期輸入不計分**：舊 UI 不看日期，過期值照樣計分；本檔非 FRESH 一律送 None。
3. **PCR／外資期貨逐欄往回找**最後一個有效值（舊 UI 只看最後一列），見 `dated_inputs` 檔頭。
4. **bool／字串判缺**：數值序列的值是 bool（Python 或 numpy）或字串 → MISSING
   （舊 UI 原值照送，引擎會把 True 當 1.0 計分）；`Index_Below_MA5` 只收 bool。
5. **TW_Export／US CPI／Fed** 等鍵**不傳**：引擎本來就不讀（`_ENGINE_NUMERIC_INPUTS` 以外）。
6. **`Sahm_Rule_Triggered` 送 None**（舊 UI 送 False）：引擎 `_b(None)` ⇒ False，行為相同；
   送 None 是為了不在資料上寫一個「已檢查、未觸發」的假 False。

休市表跨年（已查證，F7 範圍）
──────────────────────────────
L1 `fetch_twse_holiday_calendar(taipei_year=...)` 的 `taipei_year` **只是快取鍵**：官方端點
（`openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule`）沒有年份參數，回的是端點當下那一年的表，
`covered_years` 由表內實際列出的年份（通過錨點檢查者）決定。⇒ 用 `taipei_year=去年` 取不到去年的表
（只會以另一個快取鍵再抓一次同一份）。故本檔只取 `today.year`；1 月初評估去年 12 月的資料日時，
那幾天落在 `covered_years` 之外 ⇒ L0 依區間法判（上界 ≤ 上限仍 FRESH、下界 > 上限 STALE、其餘
UNDETERMINED）。⛔ 本批不新增端點。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from types import MappingProxyType
from typing import Any, Literal, Mapping

from shared.dated_value import AssessedValue, DatedValue, coerce_month_start, coerce_plain_date
from shared.freshness_policy import FreshnessStatus, assess, assess_previous_month
from shared.trading_days import CalendarSets
from src.compute.macro import dated_inputs as _di
from src.data.macro import macro_cache_reader as _mcr
from src.data.stock import twse_holiday_fetcher as _hf
from src.services.macro_state_locker import calculate_system_state
from src.services.trading_calendar_service import taipei_today

# ── 引擎輸入名（與 L2 抽取器同一份；一致性由 tests/test_batch_z64.py 守住）──
#: 本檔評估的 9 項引擎輸入（順序：session 8 項 → PMI 前月）。
ENGINE_INPUT_KEYS: tuple[str, ...] = _di.COVERED_ENGINE_INPUTS

#: 數值序列：值是 bool（Python 或 numpy）一律判 MISSING（QA 先前建議，批 Z64 落實）。
NUMERIC_SERIES: tuple[str, ...] = (
    _di.KEY_VIX, _di.KEY_PMI, _di.KEY_PMI_PREV, _di.KEY_M1B, _di.KEY_M2,
    _di.KEY_BIAS240, _di.KEY_PCR, _di.KEY_FUTURES,
)
#: bool 序列（只收 Python bool；numpy bool 先轉換）。
BOOL_SERIES: tuple[str, ...] = (_di.KEY_MA5,)

#: 薩姆規則引擎鍵：沒有資料來源，一律送 None（引擎 `_b(None)` ⇒ False）。⛔ 不送 True、不捏造。
KEY_SAHM = "Sahm_Rule_Triggered"

#: 硬紅線名稱。
RL_PMI = "pmi_contraction"
RL_FUTURES = "futures_ma5"
RL_SAHM = "sahm"

RedLineState = Literal["evaluable", "undetermined", "no_source"]

#: 紅線 → 必要輸入（門檻與觸發條件在 `calculate_system_state`，本檔只看「能不能評估」）。
RED_LINE_INPUTS: Mapping[str, tuple[str, ...]] = MappingProxyType({
    RL_PMI: (_di.KEY_PMI, _di.KEY_PMI_PREV),
    RL_FUTURES: (_di.KEY_FUTURES, _di.KEY_MA5),
    RL_SAHM: (),
})

#: Sahm 固定原因（客戶 2026-10-14 Q-z34：必須明說是現況，不得宣稱該紅線已通過）。
SAHM_NO_SOURCE_REASON = "目前無資料來源，未評估（不代表紅線已通過）"

#: 休市表沒給、也沒給錯誤訊息時的預設說明。
CALENDAR_NOT_PROVIDED = "休市表未提供（calendar=None）"

#: `run_rule_engine` 附加的鍵（⛔ 不得與引擎原有鍵重名）。
EXTRA_RESULT_KEYS: tuple[str, ...] = ("input_asof", "not_evaluated", "red_lines")

_STATUS_TEXT: Mapping[FreshnessStatus, str] = MappingProxyType({
    FreshnessStatus.FRESH: "可用",
    FreshnessStatus.STALE: "已過期",
    FreshnessStatus.MISSING: "未取得",
    FreshnessStatus.UNDETERMINED: "無法判定",
})


@dataclass(frozen=True)
class RedLineStatus:
    """一條硬紅線「能不能評估」。`evaluable` ≠「已通過」—— 觸發與否由引擎決定。"""

    status: RedLineState
    reason: str
    inputs: tuple[str, ...]

    def to_dict(self) -> dict:
        return {"status": self.status, "reason": self.reason, "inputs": list(self.inputs)}


@dataclass(frozen=True)
class EngineInputBundle:
    """規則引擎的一份完整輸入（含可追溯資訊）。"""

    macro_numbers: dict
    assessed: Mapping[str, AssessedValue]
    not_evaluated: tuple[str, ...]
    red_lines: Mapping[str, RedLineStatus]
    #: 每項輸入的資料日（'YYYY-MM-DD'）或資料月（'YYYY-MM'）；沒有日期 → None。
    input_asof: Mapping[str, str | None]
    today: date
    calendar_error: str | None = field(default=None)


# ══════════════════════════════════════════════════════════════════════
# 型別檢查（數值序列不收 bool）
# ══════════════════════════════════════════════════════════════════════


def _is_bool_like(v: Any) -> bool:
    """Python bool 或 numpy bool_。"""
    return isinstance(v, bool) or (type(v).__module__ == "numpy"
                                   and type(v).__name__ in ("bool", "bool_"))


def _bool_reason(key: str, v: Any) -> str:
    return f"{key} 的值是 bool（{v!r}），數值欄位型別錯誤，不計分"


def _as_map(d: Any) -> Mapping[str, Any]:
    return d if isinstance(d, Mapping) else {}


def _li_bool_cell(li: Any, col: str, as_of: date | None) -> Any:
    """先行指標表 `col` 欄：從「與抽取值同日的第一列」到最後一列，回傳第一個 bool 儲存格；沒有 → None。

    抽取器取的是由最後一列往回第一個有效值；那一列之後的列都被判無效而跳過。
    bool 儲存格若出現在這段（含被選中的那一列 —— `float(True)` 會被收成 1.0），代表最新讀數的型別壞了，
    ⛔ 不得往前拿舊值頂替，也不得把 True 當 1.0。抽取值沒有日期（已判缺）時不檢查。
    """
    if as_of is None or li is None or not hasattr(li, "columns") or col not in li.columns \
            or _di.LI_DATE_COL not in li.columns:
        return None
    dates = li[_di.LI_DATE_COL]
    cells = li[col]
    start = None
    for i in range(len(li)):
        if coerce_plain_date(dates.iloc[i]) == as_of:
            start = i
            break
    if start is None:
        return None
    for i in range(start, len(li)):
        if _is_bool_like(cells.iloc[i]):
            return cells.iloc[i]
    return None


def _pmi_hist_bool_cell(history: Any, target: date | None) -> Any:
    """PMI 歷史中 data_month == target 的列，若有 bool 值 → 回傳該值；否則 None。"""
    if target is None or history is None or not hasattr(history, "columns"):
        return None
    if _di.PMI_HIST_DATE_COL not in history.columns or _di.PMI_HIST_VALUE_COL not in history.columns:
        return None
    dates = history[_di.PMI_HIST_DATE_COL]
    vals = history[_di.PMI_HIST_VALUE_COL]
    for i in range(len(history)):
        if coerce_month_start(dates.iloc[i]) == target and _is_bool_like(vals.iloc[i]):
            return vals.iloc[i]
    return None


def _prev_month_start(m: date) -> date:
    """月初 → 前一個月月初（跨年：2026-01 → 2025-12）。"""
    return date(m.year - 1, 12, 1) if m.month == 1 else date(m.year, m.month - 1, 1)


def _as_missing(dv: DatedValue, reason: str) -> DatedValue:
    return DatedValue(None, dv.series_key, dv.source, as_of=dv.as_of, data_month=dv.data_month,
                      missing_reason=reason)


def _type_check(raw: dict[str, DatedValue], *, macro_info: Any, bias_info: Any,
                m1b_m2_info: Any, li_latest: Any, pmi_history: Any) -> dict[str, DatedValue]:
    """依序列做型別檢查（數值序列 bool → MISSING；MA5 numpy bool → Python bool）。"""
    out = dict(raw)
    mi = _as_map(macro_info)
    m1 = _as_map(m1b_m2_info)
    # 原始輸入端（抽取器會先把 bool 收斂成 None 或 1.0，故要看原值才寫得出真正原因）
    src_raw: dict[str, Any] = {
        _di.KEY_VIX: _as_map(mi.get("vix")).get("current"),
        _di.KEY_PMI: _as_map(mi.get("ism_pmi")).get("value"),
        _di.KEY_BIAS240: _as_map(bias_info).get("bias_240"),
    }
    for k, v in src_raw.items():
        if _is_bool_like(v):
            out[k] = _as_missing(out[k], _bool_reason(k, v))
    # M1B／M2：任一是 bool → 兩個一起判缺（沿用「不送單邊值」）
    _m1b_raw, _m2_raw = m1.get("m1b_yoy"), m1.get("m2_yoy")
    _bad = [(k, v) for k, v in ((_di.KEY_M1B, _m1b_raw), (_di.KEY_M2, _m2_raw)) if _is_bool_like(v)]
    if _bad:
        why = "；".join(_bool_reason(k, v) for k, v in _bad) + "（M1B／M2 兩者一併判缺，不送單邊值）"
        out[_di.KEY_M1B] = _as_missing(out[_di.KEY_M1B], why)
        out[_di.KEY_M2] = _as_missing(out[_di.KEY_M2], why)
    # 先行指標兩欄
    for k, col in ((_di.KEY_PCR, _di.LI_PCR_COL), (_di.KEY_FUTURES, _di.LI_FUTURES_COL)):
        cell = _li_bool_cell(li_latest, col, out[k].as_of)
        if cell is not None:
            out[k] = _as_missing(out[k], _bool_reason(k, cell) + f"（先行指標表「{col}」欄最新讀數）")
    # PMI 前月（parquet 歷史）
    prev = out[_di.KEY_PMI_PREV]
    _pmi_month = out[_di.KEY_PMI].data_month
    _target = _prev_month_start(_pmi_month) if _pmi_month is not None else None
    cell = _pmi_hist_bool_cell(pmi_history, _target)
    if cell is not None:
        out[_di.KEY_PMI_PREV] = _as_missing(prev, _bool_reason(_di.KEY_PMI_PREV, cell))
    # 抽取後的值（兜底：任何數值序列只要值是 bool —— 例如 numpy bool 通過了 finite 判定）
    for k in NUMERIC_SERIES:
        v = out[k].value
        if _is_bool_like(v):
            out[k] = _as_missing(out[k], _bool_reason(k, v))
    # MA5：只收 Python bool；numpy bool 轉換；其他型別判缺
    ma5 = out[_di.KEY_MA5]
    if ma5.value is not None and type(ma5.value) is not bool:
        if _is_bool_like(ma5.value):
            out[_di.KEY_MA5] = DatedValue(bool(ma5.value), ma5.series_key, ma5.source,
                                          as_of=ma5.as_of, data_month=ma5.data_month)
        else:
            out[_di.KEY_MA5] = _as_missing(
                ma5, f"{_di.KEY_MA5} 的值不是 bool（{ma5.value!r}），不計分")
    return out


# ══════════════════════════════════════════════════════════════════════
# 組裝
# ══════════════════════════════════════════════════════════════════════


def _asof_str(dv: DatedValue) -> str | None:
    if dv.as_of is not None:
        return dv.as_of.isoformat()
    if dv.data_month is not None:
        return dv.data_month.strftime("%Y-%m")
    return None


def _red_line(name: str, assessed: Mapping[str, AssessedValue]) -> RedLineStatus:
    inputs = RED_LINE_INPUTS[name]
    if name == RL_SAHM:
        return RedLineStatus("no_source", SAHM_NO_SOURCE_REASON, inputs)
    bad = [k for k in inputs
           if assessed[k].verdict.status != FreshnessStatus.FRESH or assessed[k].scoring_value is None]
    if not bad:
        return RedLineStatus("evaluable", "必要輸入皆可用（是否觸發由規則引擎判定）", inputs)
    parts = [f"{k}{_STATUS_TEXT[assessed[k].verdict.status]}（{assessed[k].verdict.reason}）"
             for k in bad]
    return RedLineStatus("undetermined", "無法判定：" + "；".join(parts), inputs)


def build_engine_inputs(*, macro_info: Any, bias_info: Any, m1b_m2_info: Any, li_latest: Any,
                        mkt_info: Any, pmi_history: Any, now: datetime,
                        calendar: CalendarSets | None,
                        calendar_error: str | None = None) -> EngineInputBundle:
    """session 原始結構 ＋ PMI 歷史 ＋ 休市表 → `EngineInputBundle`（純函式，不讀時鐘、不 I/O）。

    - `now` 必須是帶時區的 `datetime`；today 一律為 `now` 的**台北**日期。naive → `ValueError`。
    - `calendar` 為 None 時記錄 `calendar_error`（未給則用 `CALENDAR_NOT_PROVIDED`），台股日頻改走區間法。
    - `calendar` 不是 None 卻同時給 `calendar_error` → `ValueError`（狀態互相矛盾，不猜哪個對）。
    """
    if not isinstance(now, datetime):
        raise TypeError(f"now 必須是帶時區的 datetime：{now!r}")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now 必須是 timezone-aware datetime（naive 不猜時區）")
    today = taipei_today(now)
    if calendar is not None and not isinstance(calendar, CalendarSets):
        raise TypeError(f"calendar 必須是 CalendarSets 或 None：{type(calendar).__name__}")
    if calendar is not None and calendar_error is not None:
        raise ValueError(f"已提供休市表卻同時帶 calendar_error：{calendar_error!r}")
    if calendar is None and not calendar_error:
        calendar_error = CALENDAR_NOT_PROVIDED

    raw: dict[str, DatedValue] = {}
    raw.update(_di.extract_vix(macro_info))
    raw.update(_di.extract_bias240(bias_info))
    raw.update(_di.extract_leading(li_latest))
    raw.update(_di.extract_ma5(mkt_info))
    raw.update(_di.extract_monthly(macro_info, m1b_m2_info))
    raw.update(_di.extract_pmi_prev(pmi_history, raw[_di.KEY_PMI].data_month))
    if set(raw) != set(ENGINE_INPUT_KEYS):  # 抽取器漏項／多項 → 設定錯誤，不猜
        raise RuntimeError(f"抽取器輸出鍵與引擎輸入不符：{sorted(set(raw) ^ set(ENGINE_INPUT_KEYS))}")

    dvs = _type_check(raw, macro_info=macro_info, bias_info=bias_info, m1b_m2_info=m1b_m2_info,
                      li_latest=li_latest, pmi_history=pmi_history)

    assessed: dict[str, AssessedValue] = {}
    for k in ENGINE_INPUT_KEYS:
        if k == _di.KEY_PMI_PREV:
            continue
        assessed[k] = assess(dvs[k], today=today, calendar=calendar)
    assessed[_di.KEY_PMI_PREV] = assess_previous_month(dvs[_di.KEY_PMI_PREV],
                                                       anchor=assessed[_di.KEY_PMI])

    macro_numbers: dict[str, Any] = {k: assessed[k].scoring_value for k in ENGINE_INPUT_KEYS}
    macro_numbers[KEY_SAHM] = None

    not_evaluated = tuple(k for k in ENGINE_INPUT_KEYS
                          if assessed[k].verdict.status != FreshnessStatus.FRESH
                          or assessed[k].scoring_value is None)
    red_lines = {name: _red_line(name, assessed) for name in RED_LINE_INPUTS}
    input_asof = {k: _asof_str(assessed[k].dv) for k in ENGINE_INPUT_KEYS}

    return EngineInputBundle(
        macro_numbers=macro_numbers,
        assessed=MappingProxyType(dict(assessed)),
        not_evaluated=not_evaluated,
        red_lines=MappingProxyType(red_lines),
        input_asof=MappingProxyType(input_asof),
        today=today,
        calendar_error=calendar_error,
    )


# ══════════════════════════════════════════════════════════════════════
# L3 編排：session → bundle（⛔ 不寫 session、不寫檔）
# ══════════════════════════════════════════════════════════════════════


def _load_calendar(today: date) -> tuple[CalendarSets | None, str | None]:
    """與 `trading_calendar_service.get_today_trading_status` 同一種取法：
    L1 `fetch_twse_holiday_calendar(taipei_year=today.year)`，`HolidayCalendarUnavailable` → 記錄訊息。

    ⛔ 不另以 `taipei_year=去年` 再抓：端點無年份參數，只會回同一份表（見檔頭「休市表跨年」）。
    """
    try:
        cal = _hf.fetch_twse_holiday_calendar(taipei_year=today.year)
    except _hf.HolidayCalendarUnavailable as e:
        return None, f"休市表取不到：{e}"
    return cal.as_sets(), None


def load_engine_inputs_from_session(session: Any, *, now: datetime) -> EngineInputBundle:
    """從 session 讀 `macro_info`／`bias_info`／`m1b_m2_info`／`li_latest`／`mkt_info`，
    讀 L1 PMI 歷史、取 L1 休市表，交給 `build_engine_inputs`。唯讀。"""
    if not isinstance(now, datetime):
        raise TypeError(f"now 必須是帶時區的 datetime：{now!r}")
    today = taipei_today(now)  # naive → ValueError（與 build_engine_inputs 同一條）
    get = session.get
    pmi_history = _mcr.load_tw_pmi_history()
    calendar, calendar_error = _load_calendar(today)
    return build_engine_inputs(
        macro_info=get("macro_info"),
        bias_info=get("bias_info"),
        m1b_m2_info=get("m1b_m2_info"),
        li_latest=get("li_latest"),
        mkt_info=get("mkt_info"),
        pmi_history=pmi_history,
        now=now,
        calendar=calendar,
        calendar_error=calendar_error,
    )


# ══════════════════════════════════════════════════════════════════════
# 規則引擎執行
# ══════════════════════════════════════════════════════════════════════


def run_rule_engine(bundle: EngineInputBundle, *, include_veto_flags: bool = False) -> dict:
    """呼叫**未修改**的 `calculate_system_state`，回傳引擎原有鍵（一個都不覆寫）＋ 追溯資訊。

    附加鍵：`input_asof`（dict）、`not_evaluated`（list）、`red_lines`（{name: {status, reason, inputs}}）。
    引擎輸出若已含附加鍵名 → `RuntimeError`（⛔ 不覆寫）。

    `include_veto_flags`（批 Z65）：True → 轉給引擎同名參數，引擎輸出多帶 `veto_flags`（引擎自己的鍵，
    在三條紅線分支內設定；見 `calculate_system_state` docstring）。預設 False ⇒ 呼叫方式與 Z64 逐字相同。
    """
    if not isinstance(bundle, EngineInputBundle):
        raise TypeError(f"bundle 必須是 EngineInputBundle：{type(bundle).__name__}")
    if include_veto_flags:
        engine_result = calculate_system_state(dict(bundle.macro_numbers), include_veto_flags=True)
    else:
        engine_result = calculate_system_state(dict(bundle.macro_numbers))
    out = dict(engine_result)
    clash = [k for k in EXTRA_RESULT_KEYS if k in out]
    if clash:
        raise RuntimeError(f"引擎輸出已含附加鍵 {clash}，⛔ 不覆寫")
    out["input_asof"] = dict(bundle.input_asof)
    out["not_evaluated"] = list(bundle.not_evaluated)
    out["red_lines"] = {k: v.to_dict() for k, v in bundle.red_lines.items()}
    return out
