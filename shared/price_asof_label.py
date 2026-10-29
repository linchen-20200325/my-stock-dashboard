"""shared/price_asof_label.py — 價格「資料時間＋來源」小字（XV-ASOF，L0 純函式，零 I/O）。

規格：`docs/vnext/NEWUI_D25_XVIEW_ASOF_WIREFRAME_2026-10-28.md`（客戶 2026-10-28 確認
Q1＝A、Q2＝A、Q3＝A，DEC-102）。§2 狀態字樣表是本檔所有字樣的出處。

本檔做三件事，**都不改任何數字**（市值／損益%／357／健康度照舊）：
1. `assess_price_freshness()` —— L3 用：最後一根 K 的日期是否「非最新」。
   ⛔ 不自創天數：預期最新交易日走 `shared.staleness.expected_latest_trading_day()`，
   容忍值走 freshness SSOT `shared.freshness_policy.DAILY_MAX_LAG_TRADING_DAYS`
   （DEC-029，日頻落後超過 3 個交易日＝過期）；計數走同檔 `assess_daily(calendar_kind="weekday")`
   ——只扣週末、不扣國定假日（偏嚴：長假後可能多標 ⚠，不會假新鮮）。
2. `price_asof_label()` —— 一個價格的一行小字（§2）。
3. `group_price_asof()` —— 多列共用一行時的「多數＋例外」分組（§3.3、§4 方案 A）。

⛔ **盤中／收盤**：沙箱無法驗 yfinance 盤中行為與部署時區（線框 §1.3、XV-X8），
本檔**沒有任何路徑會寫「收盤」或「盤中」** —— 一律寫 `UNCONFIRMED_CLOSE`
（客戶 Q2＝A：「寧可明說不確定」）。
⛔ 拿不到時間時寫 `資料時間：⬜ 未提供`，**不用今天代替**。
⛔ 狀態不只靠顏色：⚠ 與文字標籤一律在字串裡。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Hashable, Mapping, Sequence

from shared.dated_value import coerce_plain_date
from shared.freshness_policy import (
    DAILY_MAX_LAG_TRADING_DAYS,
    FreshnessStatus,
    assess_daily,
)
from shared.staleness import expected_latest_trading_day
from shared.ttls import TTL_1HOUR

# ── L3 非顯示鍵（加性；`fetch_metrics()` 回傳 dict 與戰情表列共用同一組名字）────────
KEY_PRICE_AS_OF = "price_as_of"          # date | None：最後一根 K 的日期
KEY_PRICE_SRC = "price_src"              # str | None：實際成功的那一腿（見 SRC_*）
KEY_IS_STALE = "is_stale"                # bool | None：None ＝ 判不出來
KEY_IS_FALLBACK = "is_fallback"          # bool | None：None ＝ 來源不明
KEY_FFILLED_LAST = "ffilled_last"        # bool：最後一根是補值（只有 ETF 路徑給得出）
KEY_FFILLED_FROM = "ffilled_from"        # date | None：補值沿用的那一天
KEY_PRICE_EXPECTED_DAY = "price_expected_day"   # date | None：預期最新交易日
KEY_PRICE_LAG_DAYS = "price_lag_weekdays"       # int | None：落後幾個平日

#: 全部非顯示鍵（測試與「拿不到」時的預設值用）。
PRICE_ASOF_KEYS: tuple[str, ...] = (
    KEY_PRICE_AS_OF, KEY_PRICE_SRC, KEY_IS_STALE, KEY_IS_FALLBACK,
    KEY_FFILLED_LAST, KEY_FFILLED_FROM, KEY_PRICE_EXPECTED_DAY, KEY_PRICE_LAG_DAYS)

# ── 來源腿（值沿用 L1 `data_loader._get_combined_data_body` 寫進 `attrs["price_src"]` 的字面）──
SRC_YAHOO_ADJ = "yahoo_adj"              # 主源：Yahoo auto_adjust（還原）；ETF 路徑亦是這一腿
SRC_FINMIND_SDK = "finmind_sdk"
SRC_FINMIND_RAW = "finmind_raw"
SRC_YAHOO_FALLBACK = "yahoo_fallback"    # Yahoo 預設參數（備援）

#: 主源（非這些即備援）。線框 §7：「由 price_src 推得（非 yahoo_adj 即備援）」。
PRIMARY_SOURCES: frozenset[str] = frozenset({SRC_YAHOO_ADJ})

#: 顯示名稱。FinMind 類一律「FinMind」（任務規格）。
SOURCE_DISPLAY: Mapping[str, str] = {
    SRC_YAHOO_ADJ: "Yahoo",
    SRC_FINMIND_SDK: "FinMind",
    SRC_FINMIND_RAW: "FinMind",
    SRC_YAHOO_FALLBACK: "Yahoo（預設參數）",
}

#: 還原口徑（只上「查看依據」，線框 §5）。
SOURCE_BASIS: Mapping[str, str] = {
    SRC_YAHOO_ADJ: "還原",
    SRC_FINMIND_SDK: "原始價，試還原",
    SRC_FINMIND_RAW: "原始價，試還原",
    SRC_YAHOO_FALLBACK: "預設參數",
}

# ── 字樣（線框 §2；⛔ 不得只靠顏色）──────────────────────────────────────────
UNCONFIRMED_CLOSE = "盤中或收盤未確認"
NOT_PROVIDED = "⬜ 未提供"
TIME_NOT_PROVIDED = f"資料時間：{NOT_PROVIDED}"          # 🔬 各處
HOLD_LABEL = "價格資料時間"                               # 💼 ① E17 位置的標籤
HOLD_NOT_PROVIDED = NOT_PROVIDED                          # 💼：「價格資料時間：⬜ 未提供」
SRC_NOT_PROVIDED = f"來源：{NOT_PROVIDED}"
FALLBACK_PREFIX = "備援來源："
STALE_MARK = "⚠ 非最新"
FFILL_MARK = "⚠ 含補值日"

#: 查看依據（線框 §5）：來源鏈全文。
SOURCE_CHAIN_TEXT = ("個股＝Yahoo（還原）→ FinMind（原始價，試還原）→ Yahoo（預設參數）；"
                     "ETF＝Yahoo（還原）")


def assess_price_freshness(as_of: Any, *, today: date
                           ) -> tuple[bool | None, date | None, int | None]:
    """最後一根 K 的日期 → `(is_stale, 預期最新交易日, 落後平日數)`。

    `today`：台北當日（呼叫端傳入；⛔ 本檔不讀系統時鐘）。
    `as_of` 解析不了 → `(None, 預期日, None)`（判不出來，⛔ 不當成最新）。
    `as_of` 晚於預期日（日期可疑）→ `(None, …)`。
    """
    _exp = expected_latest_trading_day(today=today)
    _d = coerce_plain_date(as_of)
    if _d is None:
        return None, _exp, None
    _v = assess_daily(_d, today=_exp, calendar=None,
                      max_lag=DAILY_MAX_LAG_TRADING_DAYS, calendar_kind="weekday")
    if _v.status == FreshnessStatus.STALE:
        return True, _exp, _v.lag
    if _v.status == FreshnessStatus.FRESH:
        return False, _exp, _v.lag
    return None, _exp, _v.lag


def is_fallback_source(src: Any) -> bool | None:
    """`price_src` → 是否備援。來源不明（None／空／'unknown'／未登錄字面）→ None。"""
    _s = str(src or "").strip()
    if not _s or _s not in SOURCE_DISPLAY:
        return None
    return _s not in PRIMARY_SOURCES


@dataclass(frozen=True)
class PriceAsOf:
    """一個價格的時間與來源（L3 非顯示鍵的唯讀視圖）。"""

    as_of: date | None = None
    src: str | None = None
    is_stale: bool | None = None
    is_fallback: bool | None = None
    ffilled_last: bool = False
    ffilled_from: date | None = None
    expected_day: date | None = None
    lag_weekdays: int | None = None

    @classmethod
    def from_mapping(cls, m: Mapping[str, Any] | None) -> "PriceAsOf":
        """從 `fetch_metrics()` 的 dict 或戰情表列讀出；缺鍵 ＝ 拿不到（⛔ 不猜）。"""
        m = m if isinstance(m, Mapping) else {}
        _src = m.get(KEY_PRICE_SRC)
        _lag = m.get(KEY_PRICE_LAG_DAYS)
        _stale = m.get(KEY_IS_STALE)
        _fb = m.get(KEY_IS_FALLBACK)
        return cls(
            as_of=coerce_plain_date(m.get(KEY_PRICE_AS_OF)),
            src=(str(_src) if _src else None),
            is_stale=(_stale if isinstance(_stale, bool) else None),
            is_fallback=(_fb if isinstance(_fb, bool) else None),
            ffilled_last=(m.get(KEY_FFILLED_LAST) is True),
            ffilled_from=coerce_plain_date(m.get(KEY_FFILLED_FROM)),
            expected_day=coerce_plain_date(m.get(KEY_PRICE_EXPECTED_DAY)),
            lag_weekdays=(_lag if isinstance(_lag, int) and not isinstance(_lag, bool) else None),
        )

    @property
    def is_normal(self) -> bool:
        """有日期、主源、非最新為否、非補值 —— 「沒有例外」的那一種。"""
        return (self.as_of is not None and self.is_stale is False
                and self.is_fallback is False and not self.ffilled_last)


def _source_text(p: PriceAsOf) -> str:
    _name = SOURCE_DISPLAY.get(p.src or "")
    if not _name:
        return SRC_NOT_PROVIDED
    return f"{FALLBACK_PREFIX}{_name}" if p.is_fallback else _name


def price_asof_label(p: PriceAsOf | None) -> str:
    """一個價格 → 一行小字（線框 §2；拿掉顏色後意思不變）。

    - 拿不到日期                → `資料時間：⬜ 未提供`
    - 正常                      → `2026-10-28｜Yahoo（盤中或收盤未確認）`
    - 備援                      → `2026-10-27｜備援來源：FinMind（盤中或收盤未確認）`
    - 非最新                    → `⚠ 非最新（上次成功 2026-10-27；盤中或收盤未確認）｜Yahoo`
    - 最後一根是補值            → `⚠ 含補值日（2026-10-28 沿用 2026-10-27；盤中或收盤未確認）｜Yahoo`
    """
    if p is None or p.as_of is None:
        return TIME_NOT_PROVIDED
    _d = p.as_of.isoformat()
    _warn: list[str] = []
    if p.is_stale is True:
        _warn.append(f"{STALE_MARK}（上次成功 {_d}；{UNCONFIRMED_CLOSE}）")
    if p.ffilled_last:
        _from = (f"{_d} 沿用 {p.ffilled_from.isoformat()}" if p.ffilled_from
                 else f"{_d} 為補值")
        _warn.append(f"{FFILL_MARK}（{_from}；{UNCONFIRMED_CLOSE}）")
    if _warn:
        return "；".join(_warn) + f"｜{_source_text(p)}"
    return f"{_d}｜{_source_text(p)}（{UNCONFIRMED_CLOSE}）"


@dataclass(frozen=True)
class AsOfGrouping:
    """多列共用一行時的分組結果。

    - `majority_label`：嚴格過半（> 一半）那一組的字樣；沒有 → None（退回逐列寫法）。
    - `groups`：全部分組 `(字樣, 鍵 tuple)`，依第一次出現的順序。
    """

    majority_label: str | None
    groups: tuple[tuple[str, tuple[Hashable, ...]], ...]

    @property
    def total(self) -> int:
        return sum(len(_k) for _, _k in self.groups)

    @property
    def exceptions(self) -> tuple[tuple[str, tuple[Hashable, ...]], ...]:
        """不屬於多數組的那幾組（沒有多數時 ＝ 全部）。"""
        return tuple(_g for _g in self.groups if _g[0] != self.majority_label)

    def label_of(self, key: Hashable) -> str | None:
        for _lbl, _keys in self.groups:
            if key in _keys:
                return _lbl
        return None


def group_price_asof(items: Sequence[tuple[Hashable, PriceAsOf | None]]) -> AsOfGrouping:
    """`(鍵, PriceAsOf)` 序列 → 依字樣分組；嚴格過半那一組為「多數」。

    ⚠️ 「多數」必須是**真的過半**（線框 §4 風險欄：「共同那一行必須是多數列的真值」）；
    平手或全部各不相同 → `majority_label=None`，呼叫端逐列寫。
    """
    _order: list[str] = []
    _by: dict[str, list[Hashable]] = {}
    for _k, _p in items:
        _lbl = price_asof_label(_p)
        if _lbl not in _by:
            _by[_lbl] = []
            _order.append(_lbl)
        _by[_lbl].append(_k)
    _groups = tuple((_l, tuple(_by[_l])) for _l in _order)
    _n = sum(len(_v) for _v in _by.values())
    _major = next((_l for _l in _order if len(_by[_l]) * 2 > _n), None)
    return AsOfGrouping(majority_label=_major, groups=_groups)


def price_basis_facts(p: PriceAsOf | None) -> tuple[tuple[str, str], ...]:
    """「🔍 查看依據」兩格（線框 §5：使用的資料／資料日期）—— 只補價格說明。"""
    p = p or PriceAsOf()
    _src = p.src or ""
    if _src in SOURCE_DISPLAY:
        _used = f"{SOURCE_DISPLAY[_src]}（{SOURCE_BASIS.get(_src, '—')}）"
        if p.is_fallback:
            _used = f"{FALLBACK_PREFIX}{_used}"
    else:
        _used = SRC_NOT_PROVIDED
    _uses = f"價格來源鏈：{SOURCE_CHAIN_TEXT}。本次實際：{_used}"
    _ttl_min = TTL_1HOUR // 60
    _parts = [
        f"最後一根 K：{p.as_of.isoformat() if p.as_of else NOT_PROVIDED}",
        f"預期最新交易日：{p.expected_day.isoformat() if p.expected_day else NOT_PROVIDED}"
        "（只扣週末，未扣國定假日）",
        (f"相差 {p.lag_weekdays} 個平日" if p.lag_weekdays is not None else "相差：無法判定")
        + f"（超過 {DAILY_MAX_LAG_TRADING_DAYS} 個平日標 {STALE_MARK}；"
        "日頻上限為交易日，此處以平日計、偏嚴）",
        (f"補值日：{p.as_of.isoformat()}" + (f" 沿用 {p.ffilled_from.isoformat()}"
                                            if p.ffilled_from else "")
         if p.ffilled_last and p.as_of else "補值日：最後一根不是補值（或此來源不提供）"),
        f"快取：這份價格最多可能是約 {_ttl_min} 分鐘前抓的",
        f"盤中／收盤：{UNCONFIRMED_CLOSE}（目前技術上無法可靠判定）",
    ]
    return (("使用的資料（價格）", _uses), ("資料日期（價格）", "；".join(_parts)))
