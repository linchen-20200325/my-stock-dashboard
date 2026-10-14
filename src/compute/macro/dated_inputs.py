"""src/compute/macro/dated_inputs.py — 規則引擎輸入的「帶日期」抽取器（L2 純函式，零 I/O）。

批 Z62（freshness SSOT 第二批 F2，2026-10-14）。⛔ **本批不接線**：沒有任何呼叫端改用本檔，
引擎呼叫點（L5 `section_news_ai`）與新頁行為一律不變。

做什麼
──────
把 session 的原始結構（`macro_info`／`bias_info`／`li_latest`／`mkt_info`／`m1b_m2_info`）
轉成 `dict[引擎輸入名, shared.dated_value.DatedValue]`，交給 L0 `shared.freshness_policy.assess`
判新鮮度。key 對齊 `src/services/macro_state_locker._ENGINE_NUMERIC_INPUTS` ＋ `Index_Below_MA5`。

客戶規則（2026-10-14，Q-z37=A）：每日型輸入必須保留**實際資料日期**；沒有日期的值不得頂替
⇒ 本檔任何一個值拿不到可追溯的日期，一律回 `value=None` ＋ `missing_reason`（繁中）。
⛔ 不補值、不用 now()／today()、不用 `fetched_at` 當資料日期。

數值正規化與舊 UI 逐一相同
──────────────────────────
舊 UI 組裝在 `src/ui/tabs/macro/section_news_ai.py`（§十一「執行 AI 裁決」，`_macro_numbers`）。
本檔對每一個值走**同一條**正規化：
- PCR：`str(...)` 擋 `''／'-'／'nan'／'None'` → `float()` → L0 `shared.pcr_scale.normalize_pcr_to_ratio`。
- 外資期貨：`float()`（ValueError／TypeError／OverflowError → 缺）→ 有限值判定。
- 有限值判定：L0 `shared.dated_value.finite_or_none`（＝ L5 `_finite_yoy`／`_finite_or_none` 的 L0 等價實作；
  L2 不得 import L5）。
- M1B／M2：任一缺 → 兩個一起缺（不送單邊值）；`shared.macro_provenance.m1b_m2_for_scoring`
  拒絕（^TWII 動能代理）→ 兩個一起缺。
- MA5：`bool(mkt_info['index_below_ma5'])`。
等價性由 tests/test_batch_z62.py 以「切出舊檔原文 exec」的 golden 逐一比對守住。

與舊 UI **刻意不同**的地方（新規則，不是 bug）
──────────────────────────────────────────────
1. **先行指標逐欄往回找**：舊 UI 只看 `li_latest.iloc[-1]`，最後一列該欄沒值就判缺；
   本檔對 `選PCR`、`外資大小` **各自獨立**往回找最後一個有效（有限）值，日期取**該列**的 `_date`。
   補出來、沒有資料的平日列（值為 None／NaN）不算有效。是否過期交給 `freshness_policy` 判。
2. **VIX／PMI／BIAS240 不是「有限實數」的值**：
   - NaN／±inf：舊 UI 原值照送（引擎 `_is_finite_number` 會當缺）；本檔直接回 None ＋ 原因 ——
     引擎端效果相同，但缺值原因寫得出來。
   - ⚠️ **數字字串（如 '20.5'）或 bool**：舊 UI 原值照送，引擎 `_is_finite_number` 先 `float()`
     ⇒ 當成 20.5／1.0 **計分**；本檔回 None（判缺）。這是**真的行為差異**（批 Z62 QA L1 據實補記；
     原句「引擎端效果相同」只對 NaN／inf 成立）。依 §1 Fail Loud 維持判缺 —— 數值欄出現字串／bool
     代表上游型別壞了，不應猜成數字。**目前所有 producer 都只輸出 float**（`fetch_vix_block`
     `round(float(v), 1)`、`compute_twii_bias` `calc_bias_pct`、PMI 各源 `float`），故**沒有實際影響**；
     tests/test_batch_z62.py 釘住此差異。
3. **MA5 判缺更嚴**：`ma5`、`index_price` 任一不是有限數值（例：末 5 筆收盤含 NaN ⇒ ma5 為 NaN）、
   `index_below_ma5` 不是 bool、`index_as_of` 缺或無法解析 → 一律判缺。
   舊 UI 在這些情形會送 `bool(...)`（缺鍵時為 `False`＝「指數在 MA5 之上」）。
4. 所有輸入**沒有日期就判缺**（舊 UI 不看日期）。

未涵蓋：`PMI_Prev_Month`（留給 F3）。
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from shared.dated_value import (
    DatedValue,
    coerce_month_start,
    coerce_plain_date,
    finite_or_none,
)
from shared.macro_provenance import m1b_m2_for_scoring
from shared.pcr_scale import normalize_pcr_to_ratio

# ── 引擎輸入名（與 `macro_state_locker._ENGINE_NUMERIC_INPUTS` 同字串；一致性由測試守住）──
KEY_VIX = "VIX_Index"
KEY_BIAS240 = "BIAS240_pct"
KEY_PCR = "PCR"
KEY_FUTURES = "Futures_Net_Short"
KEY_MA5 = "Index_Below_MA5"
KEY_PMI = "ISM_PMI_or_OECD_CLI"
KEY_M1B = "M1B_YoY_pct"
KEY_M2 = "M2_YoY_pct"

#: 本批抽取器涵蓋的引擎輸入（`PMI_Prev_Month` 留給 F3）。
COVERED_ENGINE_INPUTS: tuple[str, ...] = (
    KEY_VIX, KEY_BIAS240, KEY_PCR, KEY_FUTURES, KEY_MA5, KEY_PMI, KEY_M1B, KEY_M2,
)

# ── 來源標籤（provenance；上游 dict 自帶 `source` 字串時優先用它）──
SRC_VIX = "macro_info['vix']（yfinance ^VIX 日線）"
SRC_BIAS240 = "bias_info（^TWII 收盤對 MA240 乖離，macro_snapshot.compute_twii_bias）"
SRC_PCR = "li_latest['選PCR']（先行指標表，百分比刻度 → 比值刻度）"
SRC_FUTURES = "li_latest['外資大小']（先行指標表，外資期貨淨口數，TX 當量）"
SRC_MA5 = "mkt_info（market_strategy.get_market_assessment，^TWII 收盤 vs MA5）"
SRC_PMI = "macro_info['ism_pmi']（台灣 PMI，CIER）"
SRC_M1B_M2 = "m1b_m2_info（M1B／M2 年增率）"

#: 舊 UI 判定 PCR 儲存格「沒有值」的字串（`section_news_ai` 原文同一組）。
_PCR_EMPTY_STRS: frozenset[str] = frozenset({"", "-", "nan", "None"})

#: 先行指標表的日期欄（'YYYYMMDD'）。
LI_DATE_COL = "_date"
LI_PCR_COL = "選PCR"
LI_FUTURES_COL = "外資大小"

NO_DATE = "無資料日期"


def _src(d: Mapping[str, Any] | None, default: str) -> str:
    s = d.get("source") if isinstance(d, Mapping) else None
    return s if isinstance(s, str) and s else default


def _as_mapping(d: Any) -> Mapping[str, Any]:
    """舊 UI 寫法 `x or {}`：None／空 → {}；非 Mapping 也當 {}（⛔ 不猜裡面是什麼）。"""
    return d if isinstance(d, Mapping) else {}


def _daily_numeric(key: str, raw: Any, as_of_raw: Any, *, source: str,
                   what: str) -> DatedValue:
    """日頻數值的共用收斂：值缺 → 值非有限 → 日期缺，依序判。"""
    as_of = coerce_plain_date(as_of_raw)
    if raw is None:
        return DatedValue(None, key, source, as_of=as_of, missing_reason=f"{what}無數值")
    val = finite_or_none(raw)
    if val is None:
        return DatedValue(None, key, source, as_of=as_of,
                          missing_reason=f"{what}數值非有限值（{raw!r}），不計分")
    if as_of is None:
        return DatedValue(None, key, source, missing_reason=NO_DATE)
    return DatedValue(val, key, source, as_of=as_of)


# ══════════════════════════════════════════════════════════════════════
# 日頻
# ══════════════════════════════════════════════════════════════════════


def extract_vix(macro_info: Any) -> dict[str, DatedValue]:
    """`macro_info['vix']` → `{"VIX_Index": DatedValue}`。

    值：`macro_info['vix']['current']`（舊 UI 同一個值）；as_of：`macro_info['vix']['date']`。
    日期解析失敗 → `value=None`、`missing_reason="無資料日期"`。
    """
    vix_d = _as_mapping(_as_mapping(macro_info).get("vix"))
    return {KEY_VIX: _daily_numeric(KEY_VIX, vix_d.get("current"), vix_d.get("date"),
                                    source=_src(vix_d, SRC_VIX), what="VIX ")}


def extract_bias240(bias_info: Any) -> dict[str, DatedValue]:
    """`bias_info` → `{"BIAS240_pct": DatedValue}`；as_of 取 `bias_info['as_of']`（批 Z62 L1 新增）。

    ⚠️ `bias_info` 若是批 Z62 之前產生的（沒有 `as_of`）→ 判缺「無資料日期」。
    """
    bi = _as_mapping(bias_info)
    return {KEY_BIAS240: _daily_numeric(KEY_BIAS240, bi.get("bias_240"), bi.get("as_of"),
                                        source=SRC_BIAS240, what="年線乖離（BIAS240）")}


def _parse_pcr_cell(raw: Any) -> float | None:
    """舊 UI 的 PCR 儲存格解析（`str` 擋空字串族 → `float`），再加「有限值」才算有效。"""
    s = str(raw)
    if s in _PCR_EMPTY_STRS:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return finite_or_none(v)


def _parse_futures_cell(raw: Any) -> float | None:
    """舊 UI 的外資期貨儲存格解析（`float()`；ValueError／TypeError／OverflowError → 缺）＋有限值。"""
    try:
        v = float(raw)
    except (ValueError, TypeError, OverflowError):
        return None
    return finite_or_none(v)


def _li_frame_problem(li: Any, col: str) -> str:
    """先行指標表無法逐列找值的原因；可以找 → ''。"""
    if li is None:
        return "先行指標表（li_latest）未載入"
    cols = getattr(li, "columns", None)
    if cols is None or not hasattr(li, "iloc"):
        return f"先行指標表（li_latest）型別不明：{type(li).__name__}"
    if getattr(li, "empty", True):
        return "先行指標表（li_latest）為空"
    if col not in cols:
        return f"先行指標表無「{col}」欄"
    if LI_DATE_COL not in cols:
        return f"{NO_DATE}（先行指標表無 {LI_DATE_COL} 欄）"
    return ""


def _last_valid_row(li: Any, col: str, parse) -> tuple[Any, Any] | None:
    """由最後一列往回找 `col` 第一個 `parse(...)` 非 None 的列 → `(parsed, 該列 _date 原值)`。"""
    ser = li[col]
    dates = li[LI_DATE_COL]
    for i in range(len(ser) - 1, -1, -1):
        v = parse(ser.iloc[i])
        if v is not None:
            return v, dates.iloc[i]
    return None


def _extract_li_column(li: Any, key: str, col: str, parse, *, source: str,
                       finish=None) -> DatedValue:
    problem = _li_frame_problem(li, col)
    if problem:
        return DatedValue(None, key, source, missing_reason=problem)
    hit = _last_valid_row(li, col, parse)
    if hit is None:
        return DatedValue(None, key, source,
                          missing_reason=f"先行指標表「{col}」欄沒有任何有效值")
    raw_v, raw_date = hit
    as_of = coerce_plain_date(raw_date)
    if as_of is None:
        return DatedValue(None, key, source,
                          missing_reason=f"{NO_DATE}（「{col}」最後有效值那一列的 "
                                         f"{LI_DATE_COL}＝{raw_date!r} 無法解析）")
    if finish is not None:
        val, why = finish(raw_v)
        if val is None:
            return DatedValue(None, key, source, as_of=as_of, missing_reason=why)
        return DatedValue(val, key, source, as_of=as_of)
    return DatedValue(raw_v, key, source, as_of=as_of)


def _finish_pcr(v: float) -> tuple[float | None, str]:
    ratio, scale_src = normalize_pcr_to_ratio(v)
    if ratio is None:
        return None, f"PCR 刻度無法判定（{scale_src}），不猜換算"
    return ratio, ""


def extract_leading(li_latest: Any) -> dict[str, DatedValue]:
    """`li_latest`（先行指標 DataFrame）→ `{"PCR": …, "Futures_Net_Short": …}`。

    兩欄**各自獨立**由最後一列往回找最後一個有效（有限數值）的值，as_of 取該列 `_date`
    （'YYYYMMDD'）。PCR 再經 `normalize_pcr_to_ratio` 收成比值刻度；刻度不明 → 判缺
    （⛔ 不再往前找 —— 那一列確實有讀數，只是讀不懂，往前找等於拿舊值頂替）。
    """
    return {
        KEY_PCR: _extract_li_column(li_latest, KEY_PCR, LI_PCR_COL, _parse_pcr_cell,
                                    source=SRC_PCR, finish=_finish_pcr),
        KEY_FUTURES: _extract_li_column(li_latest, KEY_FUTURES, LI_FUTURES_COL,
                                        _parse_futures_cell, source=SRC_FUTURES),
    }


def _is_bool(v: Any) -> bool:
    """Python bool 或 numpy bool_（`current_price < ma5` 兩邊若是 numpy 純量會得到後者）。"""
    return isinstance(v, bool) or (type(v).__module__ == "numpy"
                                   and type(v).__name__ in ("bool", "bool_"))


def extract_ma5(mkt_info: Any) -> dict[str, DatedValue]:
    """`mkt_info` → `{"Index_Below_MA5": DatedValue(bool)}`；as_of 取 `index_as_of`（批 Z62 L3 新增，ISO 字串）。

    判缺（一律 `value=None`，原因寫明）：
    - `mkt_info` 不是 dict 或為空（未載入）；
    - `ma5` 不是有限數值（缺、None、NaN／±inf —— 末 5 筆收盤含 NaN 時即為 NaN）；
    - `index_price` 不是有限數值；
    - `index_below_ma5` 不是 bool（缺鍵、None、0／1 之類的數字一律不收）；
    - `index_as_of` 缺或無法解析。
    ⚠️ `get_market_assessment` 在 `< 5` 筆時的 `ma5=current_price` 假值路徑：該函式不足 120 筆
    已先回 None，production 走不到（tests/test_batch_z62.py 守住），故不另設旗標。
    值一律轉成 Python `bool`（`AssessedValue.scoring_value` 不收 numpy `bool_`）。
    """
    if not isinstance(mkt_info, Mapping) or not mkt_info:
        return {KEY_MA5: DatedValue(None, KEY_MA5, SRC_MA5,
                                    missing_reason="大盤評估（mkt_info）未載入")}
    as_of = coerce_plain_date(mkt_info.get("index_as_of"))
    raw = mkt_info.get("index_below_ma5")
    ma5 = mkt_info.get("ma5")
    px = mkt_info.get("index_price")
    if finite_or_none(ma5) is None:
        why = f"MA5 不是有限數值（{ma5!r}），無法判斷指數是否跌破 MA5"
    elif finite_or_none(px) is None:
        why = f"加權指數現價不是有限數值（{px!r}），無法判斷指數是否跌破 MA5"
    elif not _is_bool(raw):
        why = f"大盤評估的「指數是否跌破 MA5」（index_below_ma5）不是 bool（{raw!r}）"
    elif as_of is None:
        why = NO_DATE
    else:
        return {KEY_MA5: DatedValue(bool(raw), KEY_MA5, SRC_MA5, as_of=as_of)}
    return {KEY_MA5: DatedValue(None, KEY_MA5, SRC_MA5, as_of=as_of, missing_reason=why)}


# ══════════════════════════════════════════════════════════════════════
# 月頻
# ══════════════════════════════════════════════════════════════════════


def _monthly(key: str, val: Any, data_month: date | None, *, source: str,
             why_if_missing: str) -> DatedValue:
    if val is None:
        return DatedValue(None, key, source, data_month=data_month,
                          missing_reason=why_if_missing)
    if data_month is None:
        return DatedValue(None, key, source, missing_reason="無資料月份")
    return DatedValue(val, key, source, data_month=data_month)


def extract_monthly(macro_info: Any, m1b_m2_info: Any) -> dict[str, DatedValue]:
    """→ `{"ISM_PMI_or_OECD_CLI", "M1B_YoY_pct", "M2_YoY_pct"}`。

    - PMI：值 `macro_info['ism_pmi']['value']`；data_month 取 `ism_pmi['date']` 的月初
      （該欄一律是資料歸屬月月初，見 `ai_structured_summary.macro_stale_prefix`）。
    - M1B／M2：沿用舊 UI 兩道閘 —— 任一非有限 → 兩個一起缺；`m1b_m2_for_scoring` 拒絕
      （^TWII 動能代理）→ 兩個一起缺。data_month 取 `m1b_m2_info['data_month']`（'YYYY-MM'），
      為 None（代理值或來源未提供）→ 判缺。
    """
    pmi_d = _as_mapping(_as_mapping(macro_info).get("ism_pmi"))
    pmi_raw = pmi_d.get("value")
    pmi_val = finite_or_none(pmi_raw)
    pmi_why = ("台灣 PMI 無數值" if pmi_raw is None
               else f"台灣 PMI 數值非有限值（{pmi_raw!r}），不計分")
    out = {KEY_PMI: _monthly(KEY_PMI, pmi_val, coerce_month_start(pmi_d.get("date")),
                             source=_src(pmi_d, SRC_PMI), why_if_missing=pmi_why)}

    # 舊 UI：`_mi_d = st.session_state.get('m1b_m2_info') or {}`
    mi = m1b_m2_info if m1b_m2_info else {}
    if not isinstance(mi, dict):
        why = f"M1B／M2 資料型別不明（{type(mi).__name__}）"
        out[KEY_M1B] = DatedValue(None, KEY_M1B, SRC_M1B_M2, missing_reason=why)
        out[KEY_M2] = DatedValue(None, KEY_M2, SRC_M1B_M2, missing_reason=why)
        return out
    src = _src(mi, SRC_M1B_M2)
    m1b = finite_or_none(mi.get("m1b_yoy"))
    m2 = finite_or_none(mi.get("m2_yoy"))
    if m1b_m2_for_scoring(mi) is None:
        why = "M1B／M2 為 ^TWII 動能代理值，只顯示不計分"
        m1b = m2 = None
    elif m1b is None or m2 is None:
        why = "M1B／M2 年增率任一缺值，兩者一併判缺（不送單邊值）"
        m1b = m2 = None
    else:
        why = ""
    dm_raw = mi.get("data_month")
    dm = coerce_month_start(dm_raw)
    if m1b is not None and dm is None:
        why = ("無資料月份（m1b_m2_info['data_month'] 為 None：代理值或來源未提供）"
               if dm_raw is None else f"無資料月份（data_month＝{dm_raw!r} 無法解析）")
        m1b = m2 = None
    out[KEY_M1B] = _monthly(KEY_M1B, m1b, dm, source=src, why_if_missing=why)
    out[KEY_M2] = _monthly(KEY_M2, m2, dm, source=src, why_if_missing=why)
    return out
