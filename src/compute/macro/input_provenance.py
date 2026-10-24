"""src/compute/macro/input_provenance.py — 引擎輸入「資料身分 × 新鮮度」shadow 分類（L2 純函式，零 I/O）。

C2a-1（契約層，2026-10-24；客戶裁示 DEC-080）。⛔ **本批不接線**：沒有任何產品程式呼叫本檔；
Risk Cap 計分、門檻、權重、Required Core、寫檔、UI 一律不變。本檔只把**已經存在**的資訊
（session 原始結構＋L3 `build_engine_inputs` 的新鮮度評估）翻譯成 L0
`shared.input_provenance_policy` 的兩軸契約，供日後 shadow 記錄使用。

逐項紀錄（可 JSON 化，`json.dumps(allow_nan=False)` 可過）
──────────────────────────────────────────────────────────
`{provenance, provenance_detail, provenance_basis, freshness, as_of, source_id,
  exists, fresh, displayable, scoring_eligible, riskcap_eligible, actual_scored}`
- `provenance`／`freshness`：L0 enum 的字串值或 None（判不出來；原因寫在 `provenance_basis`）。
- `as_of`：日頻 'YYYY-MM-DD'、月頻 'YYYY-MM'（取自新鮮度評估用的同一個 `DatedValue`）；無 → None。
- `source_id`：上游原始來源字樣（PMI／PCR／VIX／M1B 的來源標籤）；上游沒有時用抽取器的來源說明；無 → None。
- `exists`～`riskcap_eligible`：L0 `classify_eligibility` 的五欄（⛔ 不壓成單一 boolean）。
- `actual_scored`：該鍵是否在呼叫端給的 `scored_keys` 內（本輪引擎實際計分的鍵）；`scored_keys`
  不是字串集合 → None。呼叫端應傳 `macro_numbers` 中值不是 None、**且不在 `bundle.disabled_inputs`**
  的鍵 —— 停用的 M1B／M2 引擎雖收到值但不計分，⛔ 不得記成已計分。⚠️ 與 `scoring_eligible` 是兩回事：C2a 不改計分，故兩者可以不一致 —— 那正是
  shadow 要觀察的差異。

規則（C2a-1 規格）
──────────────────
- 值不存在（抽取器判缺；含「無資料日期」）→ unavailable。⚠️ 例外：M1B／M2 為 ^TWII 動能代理時，
  抽取器會把值丟掉（只顯示不計分），本檔仍記 **proxy**、exists 依原始年增率是否為有限數值（原始值也不是有限數值 → unavailable）。
- BIAS240：`is_estimated` 是 Python `True` → estimated；Python `False` → secondary；
  缺或型別不符（含 numpy bool、0／1）→ None ＋ basis。
- M1B／M2：^TWII 動能代理 → proxy（`shared.macro_provenance` 判定，照舊）；非代理時只有央行來源標籤
  （L0 `M1B_CBC_SOURCE_LABELS` 精確比對，或 `M1B_CBC_SOURCE_PREFIX` 前綴）記 official；FRED／IMF 等
  其他來源 → None ＋ basis（IMF 為 USD 計價，§4.1）。
- PCR：以新鮮度評估用的 as_of，在先行指標表找**恰好一列**有效「選PCR」（解析規則與 L2 `dated_inputs`
  同一支函式），讀該列的逐日來源欄（欄名取自 L0 `PCR_SOURCE_COLUMN`）查表；0 列／多列／缺欄／未知標籤
  → None ＋ basis。該列 `_is_stale` 為 True → carried_forward。
- 外資期貨：secondary；定位方式同 PCR，該列 `_is_stale` 為 True → carried_forward。
- PMI 當期：`macro_info['ism_pmi']['source']` 精確查表；`stale-cache(X)` 剝一層取 X、
  freshness＝carried_forward；`is_stale` 為 True 也記 carried_forward。⛔ 不讀 PMI 的代理旗標
  （該旗標語意倒置且無讀者，修正屬另案資料語意變更）。
- PMI 前月：在 PMI 歷史裡取目標資料月（當期資料月的前一月）所有列的來源；不一致或缺 → None。
  當期為 carried_forward 時，前月 basis 另註「前月有效性依附當期」（前月自身 freshness 判定不變）。
- VIX、MA5：secondary（L0 `INPUT_POLICY` 總管判定）。
- freshness 軸：既有 status STALE → stale；FRESH 且上游舊快照標記 → carried_forward；FRESH → fresh；
  MISSING／UNDETERMINED → None。⚠️ STALE **優先**：舊快照標記不得把已過期的值翻成「沿用」
  （DEC-080「超過允許期間」→ provenance 保留、freshness＝stale、不可用，見 L0 檔頭）。
- 每項獨立 `try/except Exception`：任何一項分類失敗只影響該項，記全 None ＋
  `provenance_basis="classification_failed:<例外型別名>"`（⛔ 不含例外訊息，避免把上游內容寫進紀錄）。
- 不改任何輸入、不讀時鐘、不 I/O。

分層（CLAUDE.md §8.2）：L2 —— 只 import L0（`shared.*`）與同層 L2（`dated_inputs` 的解析函式，
共用以確保「同一列」的判定與抽取器逐字相同）。⛔ 不 import L1、不 import L3。
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from shared.dated_value import coerce_month_start, coerce_plain_date, finite_or_none
from shared.freshness_policy import FreshnessStatus
from shared.input_provenance_policy import (
    DETAIL_BIAS_SHORT_WINDOW,
    DETAIL_M1B_TWII_PROXY,
    DETAIL_PMI_STALE_CACHE,
    INPUT_POLICY,
    M1B_CBC_SOURCE_LABELS,
    M1B_CBC_SOURCE_PREFIX,
    PCR_LABEL_PROVENANCE,
    PCR_SOURCE_COLUMN,
    PMI_LABEL_PROVENANCE,
    PMI_STALE_CACHE_PREFIX,
    PMI_STALE_CACHE_SUFFIX,
    FreshnessAxis,
    Provenance,
    classify_eligibility,
    is_strict_true,  # 「上游舊快照標記」：Python／numpy True 才算（寧可多判沿用，不可假新鮮）
)
from shared.macro_provenance import is_m1b_m2_proxy
from src.compute.macro import dated_inputs as _di

#: 逐項紀錄的欄位（順序即報告順序）。
RECORD_FIELDS: tuple[str, ...] = (
    "provenance", "provenance_detail", "provenance_basis", "freshness", "as_of", "source_id",
    "exists", "fresh", "displayable", "scoring_eligible", "riskcap_eligible", "actual_scored",
)

#: 先行指標表「上游沿用舊快照」的欄位（L1 `_mark_stale` 寫入，整表同值）。
LI_STALE_COL = "_is_stale"

#: 分類失敗時 basis 的前綴（後接例外型別名，不含訊息）。
CLASSIFICATION_FAILED_PREFIX = "classification_failed:"


# ══════════════════════════════════════════════════════════════════════
# 小工具
# ══════════════════════════════════════════════════════════════════════


def _as_map(d: Any) -> Mapping[str, Any]:
    return d if isinstance(d, Mapping) else {}


def _assessed_parts(assessed: Any, key: str) -> tuple[Any, Any]:
    """`assessed[key]` → `(DatedValue, FreshnessStatus)`；拿不到 → `(None, None)`（duck typing，不猜）。"""
    av = assessed.get(key) if isinstance(assessed, Mapping) else None
    dv = getattr(av, "dv", None)
    verdict = getattr(av, "verdict", None)
    status = getattr(verdict, "status", None)
    return dv, (status if isinstance(status, FreshnessStatus) else None)


def _asof_str(dv: Any) -> str | None:
    """與 L3 `macro_engine_inputs._asof_str` 同一種寫法（日頻 ISO 日、月頻 'YYYY-MM'）。"""
    as_of = getattr(dv, "as_of", None)
    if as_of is not None and hasattr(as_of, "isoformat"):
        return as_of.isoformat()
    dm = getattr(dv, "data_month", None)
    if dm is not None and hasattr(dm, "strftime"):
        return dm.strftime("%Y-%m")
    return None


def _value_exists(dv: Any) -> bool:
    """抽取器給的值是否為可用觀測值（有限實數或 Python bool）。"""
    v = getattr(dv, "value", None)
    if isinstance(v, bool):
        return True
    return finite_or_none(v) is not None


def _freshness_axis(status: Any, carried: bool | None) -> FreshnessAxis | None:
    """既有 status ＋ 上游舊快照標記 → 新軸。`carried` 為 None ＝ 標記判不出來（FRESH 時亦回 None）。"""
    if status == FreshnessStatus.STALE:
        return FreshnessAxis.STALE
    if status == FreshnessStatus.FRESH:
        if carried is None:
            return None
        return FreshnessAxis.CARRIED_FORWARD if carried else FreshnessAxis.FRESH
    return None  # MISSING／UNDETERMINED／判不出來


def _str_or_none(v: Any) -> str | None:
    return v if isinstance(v, str) and v else None


# ══════════════════════════════════════════════════════════════════════
# 先行指標表：以 as_of 定位「恰好一列」有效值
# ══════════════════════════════════════════════════════════════════════


def _li_unique_row(li: Any, col: str, as_of: Any, parse: Callable[[Any], Any]) -> tuple[int | None, str]:
    """先行指標表中 `_date`＝as_of 且 `col` 經 `parse` 有效的列；恰好一列 → (位置, '')，否則 (None, 原因)。"""
    if as_of is None:
        return None, "新鮮度評估沒有資料日，無法定位先行指標表的列"
    cols = getattr(li, "columns", None)
    if li is None or cols is None or not hasattr(li, "iloc"):
        return None, "先行指標表（li_latest）未載入或型別不明"
    if col not in cols or _di.LI_DATE_COL not in cols:
        return None, f"先行指標表缺「{col}」或「{_di.LI_DATE_COL}」欄"
    dates = li[_di.LI_DATE_COL]
    cells = li[col]
    hits = [i for i in range(len(li))
            if coerce_plain_date(dates.iloc[i]) == as_of and parse(cells.iloc[i]) is not None]
    if len(hits) == 1:
        return hits[0], ""
    if not hits:
        return None, f"先行指標表找不到 {as_of} 的有效「{col}」列"
    return None, f"先行指標表 {as_of} 有 {len(hits)} 列有效「{col}」，不猜哪一列"


def _li_row_carried(li: Any, pos: int | None) -> bool | None:
    """該列是否帶「上游沿用舊快照」標記。沒有該欄 → False；定位不到列（且有該欄）→ None。"""
    cols = getattr(li, "columns", None)
    if cols is None or LI_STALE_COL not in cols:
        return False
    if pos is None:
        return None
    return is_strict_true(li[LI_STALE_COL].iloc[pos])


# ══════════════════════════════════════════════════════════════════════
# 逐項分類（各回 (provenance, detail, basis, carried, source_id)；carried＝上游舊快照標記）
# ══════════════════════════════════════════════════════════════════════

_Cls = tuple[Any, Any, str, Any, Any]


def _cls_vix(dv: Any, *, macro_info: Any, **_: Any) -> _Cls:
    pol = INPUT_POLICY[_di.KEY_VIX]
    src = _str_or_none(_as_map(_as_map(macro_info).get("vix")).get("source"))
    return pol.normal_provenance, None, pol.provenance_basis, False, src


def _cls_ma5(dv: Any, **_: Any) -> _Cls:
    pol = INPUT_POLICY[_di.KEY_MA5]
    return pol.normal_provenance, None, pol.provenance_basis, False, None


def _cls_bias(dv: Any, *, bias_info: Any, **_: Any) -> _Cls:
    bi = _as_map(bias_info)
    flag = bi.get("is_estimated")
    if flag is True:
        return (Provenance.ESTIMATED, DETAIL_BIAS_SHORT_WINDOW,
                f"bias_info 標 is_estimated=True（可得 {bi.get('data_days')!r} 日 < 240），"
                "以短窗均線頂替 MA240（DEC-080：不參與 Risk Cap）", False, None)
    # ⚠️ 只收 Python bool：production（`macro_snapshot.compute_twii_bias` 的 `_n < 240`，`_n` 為 int）
    #   一律產生 Python bool；numpy bool 代表上游型別變了，保守拒收（記 None＋basis，不猜成估算或非估算）。
    if flag is False:
        return (INPUT_POLICY[_di.KEY_BIAS240].normal_provenance, None,
                INPUT_POLICY[_di.KEY_BIAS240].provenance_basis, False, None)
    why = ("bias_info 無 is_estimated 欄" if "is_estimated" not in bi
           else f"bias_info 的 is_estimated 不是 Python bool（{type(flag).__name__}），不猜")
    return None, None, why + "，無法判定是否為估算", False, None


def _cls_pcr(dv: Any, *, li_latest: Any, **_: Any) -> _Cls:
    pos, why = _li_unique_row(li_latest, _di.LI_PCR_COL, getattr(dv, "as_of", None),
                              _di._parse_pcr_cell)
    carried = _li_row_carried(li_latest, pos)
    if pos is None:
        return None, None, why + "，無法讀逐日來源", carried, None
    cols = getattr(li_latest, "columns", ())
    if PCR_SOURCE_COLUMN not in cols:
        return None, None, "先行指標表無逐日 PCR 來源欄（舊快取未回填），無法判定來源", carried, None
    label = li_latest[PCR_SOURCE_COLUMN].iloc[pos]
    if not isinstance(label, str) or label not in PCR_LABEL_PROVENANCE:
        return (None, None, f"逐日 PCR 來源標籤未登錄（{label!r}），不猜", carried,
                label if isinstance(label, str) and label else None)
    prov, detail = PCR_LABEL_PROVENANCE[label]
    return prov, detail, f"逐日 PCR 來源標籤「{label}」查表", carried, label


def _cls_futures(dv: Any, *, li_latest: Any, **_: Any) -> _Cls:
    pol = INPUT_POLICY[_di.KEY_FUTURES]
    pos, why = _li_unique_row(li_latest, _di.LI_FUTURES_COL, getattr(dv, "as_of", None),
                              _di._parse_futures_cell)
    carried = _li_row_carried(li_latest, pos)
    basis = pol.provenance_basis + ("" if pos is not None or carried is False
                                    else f"（{why}，上游舊快照標記判不出來）")
    return pol.normal_provenance, None, basis, carried, _str_or_none(getattr(dv, "source", None))


def _pmi_label_lookup(label: Any) -> tuple[Any, bool, str]:
    """PMI 來源標籤 → (provenance 或 None, 是否 stale-cache, 說明)。只剝一層 stale-cache(X)。"""
    if not isinstance(label, str) or not label:
        return None, False, f"PMI 來源標籤缺或型別不符（{label!r}）"
    stale = False
    inner = label
    if (label.startswith(PMI_STALE_CACHE_PREFIX) and label.endswith(PMI_STALE_CACHE_SUFFIX)
            and len(label) >= len(PMI_STALE_CACHE_PREFIX) + len(PMI_STALE_CACHE_SUFFIX)):
        stale = True
        inner = label[len(PMI_STALE_CACHE_PREFIX):len(label) - len(PMI_STALE_CACHE_SUFFIX)]
    prov = PMI_LABEL_PROVENANCE.get(inner)
    if prov is None:
        return None, stale, f"PMI 來源標籤「{inner}」未登錄，不猜"
    return prov, stale, (f"PMI 來源標籤「{label}」剝一層 stale-cache 取「{inner}」查表" if stale
                         else f"PMI 來源標籤「{label}」查表")


def _cls_pmi(dv: Any, *, macro_info: Any, **_: Any) -> _Cls:
    pmi_d = _as_map(_as_map(macro_info).get("ism_pmi"))
    label = pmi_d.get("source")
    prov, stale_cache, basis = _pmi_label_lookup(label)
    carried = stale_cache or is_strict_true(pmi_d.get("is_stale"))
    detail = DETAIL_PMI_STALE_CACHE if carried else None
    return prov, detail, basis, carried, _str_or_none(label)


def _cls_pmi_prev(dv: Any, *, macro_info: Any, pmi_history: Any, **_: Any) -> _Cls:
    anchor = coerce_month_start(_as_map(_as_map(macro_info).get("ism_pmi")).get("date"))
    if anchor is None:
        return None, None, "當期台灣 PMI 無資料月份，無法定位前一資料月的來源", False, None
    target = _di._prev_month_start(anchor)
    target_s = target.strftime("%Y-%m")
    cols = getattr(pmi_history, "columns", None)
    if pmi_history is None or cols is None or not hasattr(pmi_history, "iloc"):
        return None, None, "PMI 歷史未提供或型別不明", False, None
    if _di.PMI_HIST_DATE_COL not in cols or _di.PMI_HIST_SOURCE_COL not in cols:
        return None, None, f"PMI 歷史缺「{_di.PMI_HIST_DATE_COL}」或「{_di.PMI_HIST_SOURCE_COL}」欄", False, None
    dates = pmi_history[_di.PMI_HIST_DATE_COL]
    srcs = pmi_history[_di.PMI_HIST_SOURCE_COL]
    raw = [srcs.iloc[i] for i in range(len(pmi_history)) if coerce_month_start(dates.iloc[i]) == target]
    if not raw:
        return None, None, f"PMI 歷史中找不到前一資料月 {target_s}", False, None
    labels = {r for r in raw if isinstance(r, str) and r}
    if len(labels) != 1 or any(not (isinstance(r, str) and r) for r in raw):
        return (None, None, f"前一資料月 {target_s} 在 PMI 歷史有 {len(raw)} 列，"
                "來源標籤不一致或有缺，不猜", False, None)
    (label,) = labels
    prov, stale_cache, basis = _pmi_label_lookup(label)
    return (prov, DETAIL_PMI_STALE_CACHE if stale_cache else None, basis, stale_cache, label)


def _cls_m1b_m2(key: str) -> Callable[..., _Cls]:
    def _cls(dv: Any, *, m1b_m2_info: Any, **_: Any) -> _Cls:
        pol = INPUT_POLICY[key]
        info = m1b_m2_info if isinstance(m1b_m2_info, dict) else None
        src = _str_or_none(_as_map(info).get("source"))
        if info is not None and is_m1b_m2_proxy(info):
            return (Provenance.PROXY, DETAIL_M1B_TWII_PROXY,
                    "M1B／M2 為 ^TWII 動能代理（shared.macro_provenance 判定）；" + pol.provenance_basis,
                    False, src)
        if src is not None and (src in M1B_CBC_SOURCE_LABELS or src.startswith(M1B_CBC_SOURCE_PREFIX)):
            return (Provenance.OFFICIAL, None, f"M1B／M2 來源標籤「{src}」為央行（CBC）；" + pol.provenance_basis,
                    False, src)
        return (None, None, f"M1B／M2 來源標籤（{src!r}）不是央行來源（FRED／IMF 等；IMF 為 USD 計價，"
                "§4.1 禁止跨幣別混用），不猜身分", False, src)
    return _cls


_CLASSIFIERS: Mapping[str, Callable[..., _Cls]] = {
    _di.KEY_VIX: _cls_vix,
    _di.KEY_PMI: _cls_pmi,
    _di.KEY_PMI_PREV: _cls_pmi_prev,
    _di.KEY_FUTURES: _cls_futures,
    _di.KEY_MA5: _cls_ma5,
    _di.KEY_BIAS240: _cls_bias,
    _di.KEY_PCR: _cls_pcr,
    _di.KEY_M1B: _cls_m1b_m2(_di.KEY_M1B),
    _di.KEY_M2: _cls_m1b_m2(_di.KEY_M2),
}

#: M1B／M2 代理時，抽取器已丟掉值；exists 改看原始年增率欄位。
_M1B_RAW_FIELD: Mapping[str, str] = {_di.KEY_M1B: "m1b_yoy", _di.KEY_M2: "m2_yoy"}


def _failed_record(exc: BaseException) -> dict[str, Any]:
    rec = {f: None for f in RECORD_FIELDS}
    rec["provenance_basis"] = CLASSIFICATION_FAILED_PREFIX + type(exc).__name__
    return rec


def _scored_set(scored_keys: Any) -> frozenset | None:
    if isinstance(scored_keys, (str, bytes)) or scored_keys is None:
        return None
    if isinstance(scored_keys, Mapping):
        scored_keys = scored_keys.keys()
    try:
        items = list(scored_keys)
    except TypeError:
        return None
    if not all(isinstance(k, str) for k in items):
        return None
    return frozenset(items)


def _classify_one(key: str, *, macro_info: Any, bias_info: Any, li_latest: Any, mkt_info: Any,
                  m1b_m2_info: Any, pmi_history: Any, assessed: Any,
                  scored: frozenset | None) -> dict[str, Any]:
    dv, status = _assessed_parts(assessed, key)
    prov, detail, basis, carried, source_id = _CLASSIFIERS[key](
        dv, macro_info=macro_info, bias_info=bias_info, li_latest=li_latest, mkt_info=mkt_info,
        m1b_m2_info=m1b_m2_info, pmi_history=pmi_history)

    exists = _value_exists(dv)
    if prov == Provenance.PROXY and key in _M1B_RAW_FIELD:
        exists = finite_or_none(_as_map(m1b_m2_info).get(_M1B_RAW_FIELD[key])) is not None
    if exists and prov == Provenance.UNAVAILABLE:
        # 例：PMI 來源標籤是「全敗」字樣卻帶值 —— 標籤與值互相矛盾，不猜哪個對
        prov, detail = None, None
        basis = f"來源標籤表示無值，但有值，互相矛盾，不猜（{basis}）"
    if not exists:
        why = getattr(dv, "missing_reason", "") if dv is not None else "新鮮度評估未提供"
        prov, detail = Provenance.UNAVAILABLE, None
        basis = f"值不存在（{why or '無值'}）" + (f"；來源判定：{basis}" if basis else "")

    if source_id is None:
        source_id = _str_or_none(getattr(dv, "source", None))
    fresh_axis = _freshness_axis(status, carried)
    elig = classify_eligibility(input_key=key, provenance=prov, freshness=fresh_axis, exists=exists)
    return {
        "provenance": prov.value if isinstance(prov, Provenance) else None,
        "provenance_detail": detail if isinstance(detail, str) else None,
        "provenance_basis": basis,
        "freshness": fresh_axis.value if fresh_axis is not None else None,
        "as_of": _asof_str(dv),
        "source_id": source_id,
        **elig,
        "actual_scored": (key in scored) if scored is not None else None,
    }


def infer_input_provenance(*, macro_info: Any, bias_info: Any, li_latest: Any, mkt_info: Any,
                           m1b_m2_info: Any, pmi_history: Any, assessed: Any,
                           scored_keys: Any) -> dict[str, dict[str, Any]]:
    """引擎輸入逐項 → 兩軸 provenance／freshness ＋ 五欄資格（純函式；⛔ 不 raise、不改輸入）。

    Args:
        macro_info／bias_info／li_latest／mkt_info／m1b_m2_info: session 原始結構（與
            L3 `build_engine_inputs` 收的同一份）。
        pmi_history: L1 `load_tw_pmi_history()` 原樣回傳的 PMI 歷史表。
        assessed: `EngineInputBundle.assessed`（引擎輸入名 → `AssessedValue`）。
        scored_keys: 本輪引擎實際計分的鍵，例：
            `{k for k, v in bundle.macro_numbers.items() if v is not None} - set(bundle.disabled_inputs)`
            （⛔ 停用的 M1B／M2 不得記已計分）。

    Returns:
        `{引擎輸入名: 紀錄}`，鍵集合與順序＝L0 `INPUT_POLICY`；紀錄欄位見 `RECORD_FIELDS`。
    """
    scored = _scored_set(scored_keys)
    out: dict[str, dict[str, Any]] = {}
    for key in INPUT_POLICY:
        try:
            out[key] = _classify_one(
                key, macro_info=macro_info, bias_info=bias_info, li_latest=li_latest,
                mkt_info=mkt_info, m1b_m2_info=m1b_m2_info, pmi_history=pmi_history,
                assessed=assessed, scored=scored)
        except Exception as exc:  # 每項獨立：一項壞不拖垮其他項；只記型別名（§1：失敗留痕、不吞）
            out[key] = _failed_record(exc)
    # PMI 前月的有效性依附當期（L0 `assess_previous_month`）：當期是沿用舊快照時，前月紀錄要看得出來。
    # ⛔ 只補 basis，不改前月自身的 freshness／資格判定。
    try:
        cur, prev = out[_di.KEY_PMI], out[_di.KEY_PMI_PREV]
        if (cur.get("freshness") == FreshnessAxis.CARRIED_FORWARD.value
                and isinstance(prev.get("provenance_basis"), str)
                and not prev["provenance_basis"].startswith(CLASSIFICATION_FAILED_PREFIX)):
            prev["provenance_basis"] += ("；前月有效性依附當期（assess_previous_month），"
                                         "當期為 carried_forward")
    except Exception as exc:
        out[_di.KEY_PMI_PREV] = _failed_record(exc)
    return out
