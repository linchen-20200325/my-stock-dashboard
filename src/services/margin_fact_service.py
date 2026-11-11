"""src/services/margin_fact_service.py — 大盤融資餘額「事實」的薄 L3 唯讀層（Issue #1140 §B）。

單一職責：把 L1 canonical `macro_cache_reader.load_v2_chart_series()['margin']` 的**最新一點＋`.attrs`** 判成
一個 frozen `MarginFact`（值、單位、資料日、新鮮度、狀態與原因碼）。**只回事實，不下判斷。**

為什麼存在：L5 不得 import L1（CLAUDE.md §8.2 硬規則 4）；`macro_v2_service.get_chart_series()` 回 dict／list、
不帶 attrs（⇒ 違反 §2.4「過期須帶 is_stale」）。本層包一層，**不新增** reader／公式／cache／fetcher／來源。
單位換算（元 → 億，÷`TWD_PER_YI`）已在 L1 完成，本層**不再換算、不 round**。

⛔ 本檔刻意**不做**（客戶授權範圍外；日後接線需另案）：
- 不接 UI／real_feed／VM（目前 0 production caller；範圍守衛見 tests/test_margin_fact_service.py。
  ⚠️ 下一步接線時，該守衛必須同步改寫為「只准指定 feed 引用」）；
- 不含任何門檻、紅黃綠燈、風險判斷、建議、判讀詞；不新增任何使用者可見文案（只回 reason 碼與數值）；
- 不快取（本機 parquet 讀取，毫秒級）⇒ 不存在「失敗被凍成 TTL 那麼久」（v3 §02 第 3 點 a）。

判定順序（先到先贏；reason → state 集中於 `_REASON_STATE` 單一 dict）：
  1 L1 呼叫丟例外                              → UNAVAILABLE `read_exception`
  2 結果非 dict／無 `margin`／序列空／尾端日期無法解析 → MISSING `source_absent_or_unreadable`
  2b 序列索引有重複日期                         → UNAVAILABLE `duplicate_date_index`
      （同一天多筆且值可能不同 ⇒ 「最新值」取決於列序，無法判定哪筆為真；fail closed。
      ⛔ 只偵測 `index.is_unique`，不 drop_duplicates、不自選一筆；修資料是上游／L1 的事）
  3 最新值非有限（±inf／非數值）                → MISSING     `value_not_finite`
      （NaN 在 L1 真實路徑已被 dropna：尾點 NaN 會讓序列尾日前移，表現為順位 5 `as_of_mismatch`；
      `value_not_finite` 對 NaN 只有 mock／直接注入序列時可達，對 ±inf 則真實路徑可達）
  4 `not margin_sanity_ok(v)`（500、10000 本身拒收）→ MISSING `unit_sanity_failed`
  5 attrs 有 as_of 且 ≠ 序列最後一點日期        → MISSING     `as_of_mismatch`
  6 最後一點日期 > 台北今日                     → MISSING     `future_as_of`（fail closed，不給值）
  7 attrs 缺／非布林 `is_stale`                 → STALE       `freshness_undetermined`
  8 `is_stale is True`                          → STALE       `stale`
  9 其餘                                        → OK

已知限制（L1 折疊，本層看不到）：缺檔／壞檔／缺欄／空檔／全 NaN 在 L1 都被折成「沒有 margin key」，
本層只能回 `source_absent_or_unreadable`，無法再細分。
`source` 為描述性常數，**不宣稱列級 provenance**（parquet 的 `source` 欄逐列旗標未被 L1 帶出）。
"""
from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from shared.margin_schema import margin_sanity_ok
from shared.signal_thresholds import MARGIN_BALANCE_SANITY_MAX_YI, MARGIN_BALANCE_SANITY_MIN_YI
from shared.ui2_contract.models import FieldState

#: 資料來源說明（描述性；仿 `market_twii_view_service.TWII_SOURCE_TEXT`；⛔ 不宣稱列級 provenance）。
MARGIN_SOURCE_TEXT: str = "本地融資餘額歷史快取（FinMind 全市場融資金額，元換算為億元；每日更新）"

#: 單位字樣（L1 序列已是億元）。
MARGIN_UNIT: str = "億元"

# ── reason 碼（內部碼；ok 為 ""）─────────────────────────────────────────────
REASON_OK: str = ""
REASON_READ_EXCEPTION: str = "read_exception"
REASON_SOURCE_ABSENT: str = "source_absent_or_unreadable"
REASON_DUPLICATE_DATE_INDEX: str = "duplicate_date_index"
REASON_VALUE_NOT_FINITE: str = "value_not_finite"
REASON_UNIT_SANITY_FAILED: str = "unit_sanity_failed"
REASON_AS_OF_MISMATCH: str = "as_of_mismatch"
REASON_FUTURE_AS_OF: str = "future_as_of"
REASON_FRESHNESS_UNDETERMINED: str = "freshness_undetermined"
REASON_STALE: str = "stale"

#: reason → state 單一對照表（⛔ 不在他處另寫一份；測試窮舉每個 REASON_* 都在此）。
_REASON_STATE: dict[str, FieldState] = {
    REASON_OK: FieldState.OK,
    REASON_READ_EXCEPTION: FieldState.UNAVAILABLE,
    REASON_SOURCE_ABSENT: FieldState.MISSING,
    REASON_DUPLICATE_DATE_INDEX: FieldState.UNAVAILABLE,     # 資料本身自相矛盾（非「缺」），不給值
    REASON_VALUE_NOT_FINITE: FieldState.MISSING,
    REASON_UNIT_SANITY_FAILED: FieldState.MISSING,
    REASON_AS_OF_MISMATCH: FieldState.MISSING,
    REASON_FUTURE_AS_OF: FieldState.MISSING,
    REASON_FRESHNESS_UNDETERMINED: FieldState.STALE,
    REASON_STALE: FieldState.STALE,
}

#: 只有這兩個態可以帶值。
_VALUE_STATES = frozenset({FieldState.OK, FieldState.STALE})


@dataclass(frozen=True)
class MarginFact:
    """大盤融資餘額事實（唯讀）。

    Attributes:
        state: `FieldState`（OK／STALE 才有 `value_yi`；其餘一律 None）。
        reason: 內部原因碼（OK 為 ""）；⛔ 非使用者可見文案。
        value_yi: 最新一點融資餘額（億元；⛔ 不 round）；無值 → None。
        unit: 單位字樣。
        as_of: 該點資料日（ISO）；無值 → None。
        is_stale: L1 新鮮度（True／False）；None ＝ 沒判定出來（⛔ 不等於新鮮）。
        stale_reason: L1 過期原因（原樣轉述）；沒有 → ""。
        age_days: L1 距今天數；負值／缺 → None。
        upstream_state: L1 轉述的上游最近抓取三態（attrs 無則 ""）；與資料新鮮度各自獨立。
        source: 描述性來源常數（不宣稱列級 provenance）。
        sanity_interval_yi: 回顯 sanity 開區間 (MIN, MAX) 億（SSOT：`shared.signal_thresholds`）。
        detail: 診斷說明（僅 log／除錯；⛔ 不得直接顯示給使用者）。
    """

    state: FieldState
    reason: str = ""
    value_yi: float | None = None
    unit: str = MARGIN_UNIT
    as_of: str | None = None
    is_stale: bool | None = None
    stale_reason: str = ""
    age_days: int | None = None
    upstream_state: str = ""
    source: str = MARGIN_SOURCE_TEXT
    sanity_interval_yi: tuple[float, float] = (MARGIN_BALANCE_SANITY_MIN_YI, MARGIN_BALANCE_SANITY_MAX_YI)
    detail: str = ""

    def __post_init__(self) -> None:
        if self.state not in _VALUE_STATES and self.value_yi is not None:
            raise ValueError(f"MarginFact: state={self.state!r} 不得帶 value_yi（只有 OK／STALE 可帶值）")
        if self.state in _VALUE_STATES and self.value_yi is None:
            raise ValueError(f"MarginFact: state={self.state!r} 必須帶 value_yi")


def _default_cache_dir() -> Path:
    """repo root 的 data_cache 絕對路徑（避免 CWD 相對路徑陷阱）。"""
    return Path(__file__).resolve().parents[2] / "data_cache"


def _taipei_today() -> _dt.date:
    """台北今日（顯式傳給 L1；L1 預設的 `date.today()` 是主機日期）。"""
    from shared.macro_compute import tw_now
    return tw_now().date()


def _parse_today(v) -> _dt.date:
    """呼叫端注入的 today → date。只收 date／datetime（含 Timestamp）／ISO 日期字串；
    其餘（含 int、無法解析的字串）→ `ValueError`（⛔ 不讓 pd.Timestamp(5) 之類被當成 1970 年）。"""
    if isinstance(v, _dt.datetime):
        return v.date()
    if isinstance(v, _dt.date):
        return v
    if isinstance(v, str):
        try:
            return _dt.date.fromisoformat(v.strip()[:10])
        except ValueError:
            pass
    raise ValueError(f"today 無法解析為日期（只收 date／datetime／ISO 字串）：{v!r}")


def _to_date(v) -> _dt.date | None:
    """date／datetime／Timestamp／ISO 字串 → date；解析不出 → None（⛔ 不用今天代替）。"""
    if v is None:
        return None
    try:
        import pandas as pd
        if v is pd.NaT:                 # NaT 是 datetime 子類，必須先擋（否則 .date() 回 NaT）
            return None
        if isinstance(v, _dt.datetime):
            return v.date()
        if isinstance(v, _dt.date):
            return v
        _ts = pd.Timestamp(v)
        return None if pd.isna(_ts) else _ts.date()
    except Exception:  # noqa: BLE001 — 解析不出就當不可用，由呼叫端 fail closed
        return None


def _no_value(reason: str, detail: str, **kw) -> MarginFact:
    """無值的 fact（state 由 `_REASON_STATE` 查）。"""
    print(f"[margin_fact_service] {reason}：{detail}")
    return MarginFact(state=_REASON_STATE[reason], reason=reason, detail=detail, **kw)


def _evaluate(today: _dt.date, cache_dir: Path) -> MarginFact:
    from src.data.macro.macro_cache_reader import load_v2_chart_series

    _res = load_v2_chart_series(cache_dir, today=today)

    # 2 ── 缺 key／空序列／尾端日期無法解析（L1 把缺檔／壞檔／缺欄／空檔／全 NaN 折成「沒有 margin key」）
    _s = _res.get("margin") if isinstance(_res, dict) else None
    if _s is None or len(_s) == 0:
        return _no_value(REASON_SOURCE_ABSENT, "L1 未回 margin 序列（缺檔／壞檔／缺欄／空檔／全 NaN 無法細分）")
    _last_date = _to_date(_s.index[-1])
    if _last_date is None:
        return _no_value(REASON_SOURCE_ABSENT, f"margin 序列尾端索引無法解析為日期：{_s.index[-1]!r}")

    # 2b ── 重複日期：尾日若有多筆，「最新值」取決於列序 ⇒ fail closed（不 drop_duplicates、不自選）
    if not _s.index.is_unique:
        _dups = sorted({str(_i)[:10] for _i in _s.index[_s.index.duplicated(keep=False)]})
        return _no_value(REASON_DUPLICATE_DATE_INDEX, f"margin 序列索引有重複日期：{_dups[:5]}")

    # 3 ── 非有限
    try:
        _v = float(_s.iloc[-1])
    except (TypeError, ValueError):
        return _no_value(REASON_VALUE_NOT_FINITE, f"最新值無法轉為數值：{_s.iloc[-1]!r}")
    if not math.isfinite(_v):
        return _no_value(REASON_VALUE_NOT_FINITE, f"最新值非有限：{_v!r}")

    # 4 ── 單位 sanity（開區間；邊界本身拒收）
    if not margin_sanity_ok(_v):
        return _no_value(
            REASON_UNIT_SANITY_FAILED,
            f"最新值 {_v!r} 億 不在 ({MARGIN_BALANCE_SANITY_MIN_YI}, {MARGIN_BALANCE_SANITY_MAX_YI}) 開區間（疑似單位／欄位誤判）")

    # 5 ── attrs.as_of 與序列尾端對帳
    _attrs = dict(getattr(_s, "attrs", {}) or {})
    _attr_as_of_raw = _attrs.get("as_of")
    if _attr_as_of_raw is not None:
        _attr_as_of = _to_date(_attr_as_of_raw)
        if _attr_as_of is None or _attr_as_of != _last_date:
            return _no_value(
                REASON_AS_OF_MISMATCH,
                f"attrs.as_of={_attr_as_of.isoformat() if _attr_as_of else repr(_attr_as_of_raw)}"
                f" ≠ 序列最後一點日期 {_last_date.isoformat()}")

    # 6 ── 未來日（fail closed）
    if _last_date > today:
        return _no_value(REASON_FUTURE_AS_OF, f"最後一點日期 {_last_date.isoformat()} 晚於台北今日 {today.isoformat()}")

    # 7/8/9 ── 新鮮度
    _is_stale_raw = _attrs.get("is_stale")
    _is_stale: bool | None = bool(_is_stale_raw) if isinstance(_is_stale_raw, (bool, np.bool_)) else None
    _age_raw = _attrs.get("age_days")
    _age: int | None = None
    if isinstance(_age_raw, (int, float, np.integer, np.floating)) and not isinstance(_age_raw, (bool, np.bool_)):
        if math.isfinite(float(_age_raw)) and _age_raw >= 0:      # 負天數（未來日）一律 None（沿用 #1140 C2）
            _age = int(_age_raw)
    if _is_stale is None:
        _reason = REASON_FRESHNESS_UNDETERMINED
    elif _is_stale:
        _reason = REASON_STALE
    else:
        _reason = REASON_OK
    return MarginFact(
        state=_REASON_STATE[_reason],
        reason=_reason,
        value_yi=_v,
        as_of=_last_date.isoformat(),
        is_stale=_is_stale,
        stale_reason=str(_attrs.get("stale_reason") or ""),
        age_days=_age,
        upstream_state=str(_attrs.get("upstream_state") or ""),
    )


def get_margin_fact(*, today=None, cache_dir=None) -> MarginFact:
    """讀大盤融資餘額最新一點事實（唯讀；不快取、不連網）。

    Args:
        today: 基準日（測試注入）；None → 台北今日。**顯式傳給 L1**（L1 預設為主機 `date.today()`）。
            無法解析（非 date／datetime／ISO 字串）→ **raise `ValueError`**（呼叫端程式錯誤，不是資料問題；
            ⛔ 不 fail closed 成 MarginFact，避免把呼叫端 bug 偽裝成「資料缺」）。
        cache_dir: data_cache 目錄（測試注入 tmp_path）；None → repo root 絕對路徑。
    """
    _today = _parse_today(today) if today is not None else _taipei_today()
    _dir = Path(cache_dir) if cache_dir is not None else _default_cache_dir()
    try:
        return _evaluate(_today, _dir)
    except Exception as _e:  # noqa: BLE001 — 讀不到就講出來（§1），state=UNAVAILABLE（系統真出錯）
        return _no_value(REASON_READ_EXCEPTION, f"{type(_e).__name__}: {_e}")
