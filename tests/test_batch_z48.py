"""批 Z48 —— 新 UI 持股頁 VaR 卡：歷史收盤價含 0／負值／NaN／±inf ⇒ **整張不計算**。

Bug（實測重現，修前）：`get_portfolio_var()` 拿含 0 的收盤價去 `pct_change()` → 隔天 +inf →
參數法印「95% 約 nan 元」，月度 99% 衝到 200%、卡片判「月度尾部偏高」（不實尾端警示）；
NaN 收盤價則被 `pct_change().dropna()` 靜靜吃掉那一天 → **剔除異常日後照樣給數字**；
負值收盤價照算出一個 4000% 的月度尾部。

客戶 2026-10-13 裁示（逐條）：
  ① 不得剔除異常日後繼續計算；② 整張 VaR 卡進入「無法計算」並標示資料異常原因；
  ③ 不得產生 nan／inf，也不得輸出尾端風險結論；④ 不得把異常值改成 0、前值或其他替代值。

修法：L2 `etf_calc.find_invalid_closes()`（只判不改）→ L3 `_daily_returns(invalid=)` 在**算報酬之前**
判收盤價 → `get_portfolio_var()` 任一檔有異常即回 `computed=False` ＋ `REASON_INVALID_CLOSE`
＋ `invalid_close=((代號, 第一個異常日), …)` → L5 `build_var_card()` 灰態 `VAR_INVALID_CLOSE_NOW`。

本檔驗：
  A. L2 判定：0／負值／NaN／±inf／非數值 → 異常；正常 → 無異常；不改輸入。
  B. L3：單檔各種異常、多檔中只一檔異常 → 整個不算、元金額全為 0、無 nan／inf。
  C. 迴歸：正常資料 → 與修前（還原體）逐欄相同，且與手算分位數一致。
  D. L5：灰態、原因列出代號與第一個異常日、卡面／HTML 無 nan／inf、無尾端結論。
  E. 突變（revert-pair）：拔掉偵測／拔掉整卡中止／拔掉 UI 分支 → 對應斷言轉紅。
"""
from __future__ import annotations

import dataclasses
import functools
import math
import pathlib
import sys
import types

import numpy as np
import pandas as pd
import pytest

import src.services.portfolio_deep_service as D
import src.ui.views.page_hold as PH
from src.compute.etf.etf_calc import find_invalid_closes
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_LIVE

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SVC = 'src/services/portfolio_deep_service.py'
_HOLD = 'src/ui/views/page_hold.py'

# ── revert pairs：(修後逐字, 修前逐字) —— 正式碼字面一改即找不到替換點而失敗 ──────────
#: ① L3 `_daily_returns` 的偵測段（拔掉 ＝ 修前直接 pct_change）。
Z48_DETECT_PAIR = (
    "        # 批 Z48：**算報酬之前**先判收盤價本身（0 → 隔天 +inf；NaN → 被下面的 dropna 吃掉那一天）。\n"
    "        _bad = find_invalid_closes(_df[\"Close\"])\n"
    "        # 批 Z48（QA r1）：L1 已用前值補掉的 Close NaN —— 值上看不出來，只能讀 L1 留下的旗標。\n"
    "        _ffilled = _ffilled_close_days(_df)\n"
    "        if _bad[\"n_invalid\"] or _ffilled:\n"
    "            _cands = [_d for _d in (_day_str(_bad[\"first_invalid\"]),\n"
    "                                    _ffilled[0] if _ffilled else \"\") if _d]\n"
    "            _first = min(_cands) if _cands else \"\"\n"
    "            print(f\"[portfolio_deep/var] {_tk} 歷史收盤價含 {_bad['n_invalid']} 筆 0／負值／無效值、\"\n"
    "                  f\"{len(_ffilled)} 筆上游以前值補過的空值\"\n"
    "                  f\"（第一筆 {_first or '日期不明'}）→ 不算報酬\")\n"
    "            invalid.append((_tk, _first))\n"
    "            continue\n",
    "",
)
#: ② L3 `get_portfolio_var` 的整卡中止（拔掉 ＝ 偵測到也只是那一檔掉出分布，其餘照算）。
Z48_ABORT_PAIR = (
    "    if _invalid:\n"
    "        # 批 Z48（客戶 2026-10-13 裁示）：**任一檔**收盤價有異常 → 整個 VaR 不算。\n"
    "        # ⛔ 不剔除異常日後照算、⛔ 不只剔那一檔、⛔ 不把異常值換成 0／前值。\n"
    "        # 排在 `not _rets` 之前：全員都異常時講的是「價格有異常」，不是「抓不到」。\n"
    "        return VarResult(reason=REASON_INVALID_CLOSE, invalid_close=tuple(_invalid),\n"
    "                         no_price=tuple(_missing), fetch_errors=tuple(_errors),\n"
    "                         excluded_tickers=tuple(sorted(_w)), **_base)\n",
    "",
)
#: ③ L5 `build_var_card` 的灰態分支（拔掉 ＝ 落回通用灰卡「這是一個有效的結果」）。
Z48_UI_PAIR = (
    "    elif _invalid:\n"
    "        # 批 Z48：灰「無法計算」。⛔ 不寫「這是一個有效的結果」（這是資料異常，不是有效結果），\n",
    "    elif False:\n"
    "        # 批 Z48：灰「無法計算」。⛔ 不寫「這是一個有效的結果」（這是資料異常，不是有效結果），\n",
)


def _load_variant(rel: str, pairs, name: str) -> types.ModuleType:
    """現行原始碼只套 `pairs`（修後 → 修前），載成獨立模組物件（不影響本尊）。"""
    path = _ROOT / rel
    code = path.read_text(encoding='utf-8')
    for new, old in pairs:
        assert code.count(new) == 1, f'替換點不唯一或已不存在：{new[:60]!r}'
        code = code.replace(new, old)
    m = types.ModuleType(name)
    m.__file__ = str(path)
    sys.modules[name] = m          # dataclass 解析註解需要模組已註冊
    exec(compile(code, str(path), 'exec'), m.__dict__)
    return m


@functools.lru_cache(maxsize=None)
def z48_pre_svc():
    """L3 修前（偵測 ＋ 中止兩段都拔掉）。"""
    return _load_variant(_SVC, (Z48_DETECT_PAIR, Z48_ABORT_PAIR), '_z48_pre_svc')


@functools.lru_cache(maxsize=None)
def z48_no_abort_svc():
    """L3 只拔掉整卡中止（偵測保留）。"""
    return _load_variant(_SVC, (Z48_ABORT_PAIR,), '_z48_no_abort_svc')


@functools.lru_cache(maxsize=None)
def z48_pre_ui():
    return _load_variant(_HOLD, (Z48_UI_PAIR,), '_z48_pre_ui')


# ── 合成資料 ─────────────────────────────────────────────────────────────
_N = 60
_IDX = pd.bdate_range("2025-01-02", periods=_N)
_BAD_AT = 30
_BAD_DAY = _IDX[_BAD_AT].strftime("%Y-%m-%d")          # 2025-02-13


def _prices(bad=None, at: int = _BAD_AT, offset: float = 0.0) -> pd.DataFrame:
    """確定性收盤價（不用亂數）；`bad` 不為 None 時把第 `at` 筆換成它。"""
    v = [100.0 + offset + (i % 5) for i in range(_N)]
    if bad is not None:
        v[at] = bad
    return pd.DataFrame({"Close": v}, index=_IDX)


def _stub(available: dict):
    """假的 L1 `fetch_etf_price`（收 `failed=`，strict 會帶）：只有 `available` 裡的代號有資料。"""
    def _fake(ticker, period="1y", failed=None):
        _df = available.get(ticker)
        return pd.DataFrame() if _df is None else _df.copy()
    return _fake


def _row(code: str, lots: float, price: float) -> dict:
    return {"代號": code, "held": True, "張數": lots,
            "均價": price / 2.0, "現價": price, "_detail": {}}


_ROWS_ONE = [_row("2330", 1.0, 1000.0)]
_ROWS_TWO = [_row("2330", 1.0, 1000.0), _row("0056", 2.0, 50.0)]

_BAD = {"zero": 0.0, "nan": float("nan"), "inf": float("inf"),
        "neg_inf": float("-inf"), "negative": -5.0}

_MONEY = ("hist_95_twd", "hist_99_twd", "param_95_twd", "param_99_twd",
          "monthly_99_twd", "monthly_99_pct", "covered_value_twd", "coverage_pct")


def _var(mod, monkeypatch, available, rows, strict=True):
    monkeypatch.setattr("src.data.etf.etf_fetch.fetch_etf_price", _stub(available))
    return mod.get_portfolio_var(rows, strict=strict)


def _card(mod_ui, res, **kw):
    deep = mod_ui.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=len(_ROWS_TWO),
                              has_station_rows=True, var=res, **kw)
    return mod_ui.build_var_card(deep)


def _blob(mod_ui, built) -> str:
    card, facts, sig = built
    return (repr(card) + repr(tuple(facts)) + sig
            + mod_ui.v2_card_html(card, facts, sig))


def _all_finite(res) -> bool:
    return all(math.isfinite(float(getattr(res, _f))) for _f in _MONEY)


# ── A：L2 判定 ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("bad", list(_BAD.values()) + ["abc", None], ids=repr)
def test_l2_flags_invalid_close_and_first_day(bad):
    s = pd.Series([10.0, 11.0, bad, 12.0, bad], index=_IDX[:5], dtype=object
                  if isinstance(bad, str) or bad is None else "float64")
    before = s.copy()
    got = find_invalid_closes(s)
    assert got["n_invalid"] == 2
    assert got["first_invalid"] == _IDX[2]
    pd.testing.assert_series_equal(s, before)            # 只判不改（不 fillna／replace）


def test_l2_valid_and_empty_have_no_invalid():
    assert find_invalid_closes(_prices()["Close"]) == {"n_invalid": 0, "first_invalid": None}
    assert find_invalid_closes(pd.Series(dtype="float64")) == {"n_invalid": 0, "first_invalid": None}
    assert find_invalid_closes(None) == {"n_invalid": 0, "first_invalid": None}


def test_l2_tiny_positive_is_valid():
    assert find_invalid_closes(pd.Series([1e-9, 0.01, 5.0]))["n_invalid"] == 0


# ── B：L3 ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("strict", [True, False], ids=["strict", "default"])
@pytest.mark.parametrize("kind", list(_BAD), ids=list(_BAD))
def test_l3_single_holding_invalid_close_is_not_computed(kind, strict, monkeypatch):
    res = _var(D, monkeypatch, {"2330.TW": _prices(_BAD[kind])}, _ROWS_ONE, strict)
    assert res.computed is False
    assert res.reason == D.REASON_INVALID_CLOSE
    assert res.invalid_close == (("2330.TW", _BAD_DAY),)
    assert res.tickers_used == () and res.warn is False
    assert all(getattr(res, _f) == 0.0 for _f in _MONEY), "異常時不得帶任何元金額"
    assert _all_finite(res)
    assert res.no_price == () and res.fetch_errors == ()


@pytest.mark.parametrize("at", [0, _N - 1], ids=["first_row", "last_row"])
def test_l3_invalid_at_edges_reports_that_day(at, monkeypatch):
    res = _var(D, monkeypatch, {"2330.TW": _prices(0.0, at=at)}, _ROWS_ONE)
    assert res.computed is False and res.reason == D.REASON_INVALID_CLOSE
    assert res.invalid_close == (("2330.TW", _IDX[at].strftime("%Y-%m-%d")),)


@pytest.mark.parametrize("kind", list(_BAD), ids=list(_BAD))
def test_l3_one_bad_holding_among_many_stops_the_whole_var(kind, monkeypatch):
    res = _var(D, monkeypatch, {"2330.TW": _prices(),
                                "0056.TW": _prices(_BAD[kind], offset=3.0)}, _ROWS_TWO)
    assert res.computed is False and res.reason == D.REASON_INVALID_CLOSE
    assert res.invalid_close == (("0056.TW", _BAD_DAY),), "只列異常的那一檔"
    assert res.tickers_used == (), "不得只剔那一檔、其餘照算"
    assert set(res.excluded_tickers) == {"2330.TW", "0056.TW"}
    assert all(getattr(res, _f) == 0.0 for _f in _MONEY)


def test_l3_every_bad_holding_is_listed(monkeypatch):
    res = _var(D, monkeypatch, {"2330.TW": _prices(float("nan")),
                                "0056.TW": _prices(0.0, at=5, offset=3.0)}, _ROWS_TWO)
    assert res.reason == D.REASON_INVALID_CLOSE
    assert dict(res.invalid_close) == {"2330.TW": _BAD_DAY,
                                       "0056.TW": _IDX[5].strftime("%Y-%m-%d")}


def test_l3_invalid_wins_over_no_price(monkeypatch):
    """一檔異常、一檔抓不到 → 仍是「價格有異常」（不是「抓不到」），抓不到那一檔照樣揭露。"""
    res = _var(D, monkeypatch, {"2330.TW": _prices(0.0)}, _ROWS_TWO)
    assert res.reason == D.REASON_INVALID_CLOSE
    assert res.no_price == ("0056.TW",)


# ── C：迴歸 ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("strict", [True, False], ids=["strict", "default"])
@pytest.mark.parametrize("rows,avail", [
    (_ROWS_ONE, {"2330.TW": _prices()}),
    (_ROWS_TWO, {"2330.TW": _prices(), "0056.TW": _prices(offset=3.0)}),
    (_ROWS_TWO, {"2330.TW": _prices()}),                    # 部分覆蓋（既有行為）
], ids=["one", "two", "partial"])
def test_normal_data_identical_to_pre_batch(rows, avail, strict, monkeypatch):
    now = dataclasses.asdict(_var(D, monkeypatch, avail, rows, strict))
    pre = dataclasses.asdict(_var(z48_pre_svc(), monkeypatch, avail, rows, strict))
    assert now == pre
    assert now["computed"] is True and now["invalid_close"] == ()


def test_normal_data_matches_hand_quantile(monkeypatch):
    res = _var(D, monkeypatch, {"2330.TW": _prices()}, _ROWS_ONE)
    _ret = _prices()["Close"].pct_change().dropna()
    assert res.hist_95_twd == pytest.approx(abs(float(_ret.quantile(0.05))) * 1_000_000.0)
    assert _all_finite(res)


def test_normal_card_identical_to_pre_batch(monkeypatch):
    avail = {"2330.TW": _prices(), "0056.TW": _prices(offset=3.0)}
    now = _card(PH, _var(D, monkeypatch, avail, _ROWS_TWO))
    pre = _card(z48_pre_ui(), _var(z48_pre_svc(), monkeypatch, avail, _ROWS_TWO))
    assert now[0].state == UI_LIVE
    assert repr(now) == repr(pre)


# ── D：L5 卡片 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("kind", list(_BAD), ids=list(_BAD))
@pytest.mark.parametrize("rows,avail", [
    (_ROWS_ONE, lambda b: {"2330.TW": _prices(b)}),
    (_ROWS_TWO, lambda b: {"2330.TW": _prices(b), "0056.TW": _prices(offset=3.0)}),
], ids=["one", "two_one_bad"])
def test_card_is_grey_cannot_compute_without_nan_or_tail_verdict(kind, rows, avail, monkeypatch):
    built = _card(PH, _var(D, monkeypatch, avail(_BAD[kind]), rows))
    card, facts, sig = built
    assert card.state == UI_EMPTY, "資料異常是灰的「無法計算」，不是綠／橘"
    assert card.note.now == PH.VAR_INVALID_CLOSE_NOW
    assert card.value == "" and sig == ""
    _item = f"2330.TW（第一個異常日 {_BAD_DAY}）"
    assert card.note.why == (f"{PH.VAR_INVALID_CLOSE_WHY_HEAD}：{_item}。"
                             f"{PH.VAR_INVALID_CLOSE_WHY_TAIL}")
    assert card.note.where == PH.VAR_INVALID_CLOSE_WHERE
    assert dict(facts)[PH.VAR_INVALID_CLOSE_FACT] == _item
    blob = _blob(PH, built)
    assert "nan" not in blob.lower() and "inf" not in blob.lower()
    for _w in ("尾部", "門檻內", "超過門檻"):
        assert _w not in blob, f"無法計算的卡出現了尾端／門檻結論字樣：{_w}"
    assert "元" not in "".join(_v for _, _v in facts), "不得出現任何金額"
    short, _full = PH.v2_short_rows(card)              # 卡面短句是原文摘錄（對不上會 KeyError）
    assert dict(short)[PH.V2_NOW_FACT_KEY] == "歷史收盤價有異常值，VaR 無法計算"


def test_card_with_fetch_error_and_invalid_stays_red_and_names_the_bad_one(monkeypatch):
    """有取價例外 → 既有紅卡不變；異常那一檔照樣列出，仍無 nan／inf。"""
    def _fake(ticker, period="1y", failed=None):
        if ticker.startswith("0056"):
            raise ConnectionError("yahoo 429")
        return _prices(0.0)
    monkeypatch.setattr("src.data.etf.etf_fetch.fetch_etf_price", _fake)
    res = D.get_portfolio_var(_ROWS_TWO, strict=True)
    assert res.reason == D.REASON_INVALID_CLOSE and res.fetch_errors
    built = _card(PH, res)
    assert built[0].state == UI_FAILED
    assert dict(built[1])[PH.VAR_INVALID_CLOSE_FACT] == f"2330.TW（第一個異常日 {_BAD_DAY}）"
    blob = _blob(PH, built).lower()
    assert "nan" not in blob and "inf" not in blob


def test_card_without_date_lists_ticker_only():
    res = D.VarResult(reason=D.REASON_INVALID_CLOSE, invalid_close=(("2330.TW", ""),))
    card, facts, _ = _card(PH, res)
    assert dict(facts)[PH.VAR_INVALID_CLOSE_FACT] == "2330.TW"
    assert "第一個異常日" not in card.note.why


def test_no_substitution_calls_in_the_new_code():
    """④ 不得替換：本批新增的 L2／L3 段落沒有 fillna／ffill／bfill／replace。"""
    import inspect
    src = inspect.getsource(find_invalid_closes) + Z48_DETECT_PAIR[0] + Z48_ABORT_PAIR[0]
    code = "\n".join(_l.split("#", 1)[0] for _l in src.splitlines()
                     if not _l.strip().startswith(("#", "⛔", "`")))
    for _bad in (".fillna(", ".ffill(", ".bfill(", ".replace(", ".interpolate("):
        assert _bad not in code


# ── E：突變（revert pair）───────────────────────────────────────────────
def test_mutation_detect_removed_turns_red(monkeypatch):
    pre = z48_pre_svc()
    # Close=0：還原體照算 → 參數法 nan、卡片綠燈並給尾端結論（修前症狀）
    res = _var(pre, monkeypatch, {"2330.TW": _prices(0.0)}, _ROWS_ONE)
    assert res.computed is True and not _all_finite(res)
    built = _card(PH, res)
    assert built[0].state == UI_LIVE and "nan" in _blob(PH, built).lower()
    assert built[2] in ("月度尾部偏高", "月度尾部可控")
    # NaN：還原體把那一天剔掉後照算（客戶裁示 ① 禁止）
    res = _var(pre, monkeypatch, {"2330.TW": _prices(float("nan"))}, _ROWS_ONE)
    assert res.computed is True and res.n_common < _N - 1
    # 負值：還原體照算出一個數字
    res = _var(pre, monkeypatch, {"2330.TW": _prices(-5.0)}, _ROWS_ONE)
    assert res.computed is True
    # 本尊對同樣輸入一律不算 → B／D 在還原體上必紅
    for _b in (0.0, float("nan"), -5.0):
        assert _var(D, monkeypatch, {"2330.TW": _prices(_b)}, _ROWS_ONE).computed is False


def test_mutation_abort_removed_turns_red(monkeypatch):
    """只拔整卡中止：異常那一檔悄悄掉出分布，其餘照算（客戶裁示：不得只剔該檔）。"""
    m = z48_no_abort_svc()
    avail = {"2330.TW": _prices(), "0056.TW": _prices(0.0, offset=3.0)}
    res = _var(m, monkeypatch, avail, _ROWS_TWO)
    assert res.computed is True and res.tickers_used == ("2330.TW",)
    assert _var(D, monkeypatch, avail, _ROWS_TWO).computed is False


def test_mutation_ui_branch_removed_turns_red(monkeypatch):
    res = _var(D, monkeypatch, {"2330.TW": _prices(0.0)}, _ROWS_ONE)
    pre_card = _card(z48_pre_ui(), res)[0]
    assert pre_card.note.now == PH.VAR_EMPTY_NOW
    assert "這是一個有效的結果" in pre_card.note.why     # 還原體：把資料異常講成有效結果
    assert _card(PH, res)[0].note.now == PH.VAR_INVALID_CLOSE_NOW


# ══════════════════════════════════════════════════════════════════════════
# 批 Z48 第 2 項：新 UI 個股頁籌碼卡「單日爆量檢查」—— 倍數非有限值改用客戶核准文案
# ══════════════════════════════════════════════════════════════════════════
# L2 回 `ok`／`outlier`、倍數卻是 NaN／±inf → L3 `_outlier_fields` 判 `OUTLIER_UNKNOWN`（原因仍是
# `ok`／`outlier`）。修前畫面落到 `CHIPS_OUTLIER_UNKNOWN_OTHER`「上游的回傳字彙可能改了」（與實因不符），
# 且 HEAD 印出「（上游原因：`ok`）」與「沒有異常」字樣。修後整列只出客戶核准的那一句。
import src.data.stock.app_stock_fetchers as F_STK  # noqa: E402
import src.services.stock_chips_service as CHIPS  # noqa: E402
import src.ui.views.page_inspect as PI  # noqa: E402
from src.compute.risk import inst_sanity as INST  # noqa: E402

_INSPECT = 'src/ui/views/page_inspect.py'
#: 客戶 2026-10-13 核准逐字文案（⛔ 一字不改）—— 測試這一邊**手抄**，不讀實作常數。
_APPROVED = "主力買賣超倍數資料異常，無法判定是否達到異常門檻。"

#: ④ L5 `_outlier_fact` 的新分支（拔掉 ＝ 落回 HEAD ＋ OTHER）。
Z48_CHIPS_PAIR = (
    '    if _v == OUTLIER_UNKNOWN and chips.outlier_reason in ("ok", "outlier"):\n'
    "        # 批 Z48 第 2 項：L2 判得出來的兩個原因卻落到判不出來 ⇒ 只可能是倍數非有限（L3 `_outlier_fields`）。\n"
    "        return (CHIPS_OUTLIER_LABEL, CHIPS_OUTLIER_UNKNOWN_NONFINITE)\n"
    "\n",
    "",
)


@functools.lru_cache(maxsize=None)
def z48_pre_inspect():
    return _load_variant(_INSPECT, (Z48_CHIPS_PAIR,), '_z48_pre_inspect')


class _ChipsVerdict:
    requested = True
    is_stock = True
    code = '2330'


class _ChipsReq:
    period_days = 120


def _chips_df(inst_last=100.0, vol_last=None):
    n = 40
    d = pd.DataFrame({'外資': [50.0] * n, '投信': [10.0] * n,
                      '主力合計': [60.0] * n, 'volume': [1000.0] * n},
                     index=pd.date_range('2026-01-01', periods=n))
    d.iloc[-1, d.columns.get_loc('主力合計')] = inst_last
    if vol_last is not None:
        d.iloc[-1, d.columns.get_loc('volume')] = vol_last
    return d


def _chips_built(ui_mod, monkeypatch, df=None, l2=None):
    """L1（合成 df）→ L3 → `load_chips` → `build_chips_card`。`l2` 給了就換掉 L2 的判定結果。"""
    monkeypatch.setattr(F_STK, 'fetch_price_data',
                        lambda sid, days: (_chips_df() if df is None else df, 'X', ''))
    if l2 is not None:
        monkeypatch.setattr(INST, 'flag_latest_inst_outlier_from_df', lambda _df, **_k: l2)
    return ui_mod.build_chips_card(ui_mod.load_chips(_ChipsVerdict(), _ChipsReq()))


def _row_of(built, ui_mod=PI):
    return dict(built[1]).get(ui_mod.CHIPS_OUTLIER_LABEL)


#: 三個指定情境（ok＋NaN／outlier＋inf／outlier＋-inf）走 L2 替身；另兩例走真 L2（合成 df）。
_NONFINITE_L2 = {
    'ok_nan': INST.InstNetSanityResult(is_outlier=False, ratio=float('nan'), reason='ok'),
    'outlier_inf': INST.InstNetSanityResult(is_outlier=True, ratio=float('inf'), reason='outlier'),
    'outlier_neg_inf': INST.InstNetSanityResult(is_outlier=True, ratio=float('-inf'),
                                                reason='outlier'),
}
_NONFINITE_DF = {
    'real_l2_ok_nan': dict(inst_last=np.inf, vol_last=np.inf),      # inf / inf = NaN、reason='ok'
    'real_l2_outlier_inf': dict(inst_last=np.inf),                   # inf / 1000 = inf、reason='outlier'
}
_FORBIDDEN_IN_ROW = ("nan", "inf", "有異常", "沒有異常", "上游的回傳字彙", "上游原因", "`ok`", "`outlier`")


def _assert_approved_only(built):
    row = _row_of(built)
    assert row == _APPROVED, f"整列應只呈現客戶核准那一句：{row!r}"
    for _w in _FORBIDDEN_IN_ROW:
        assert _w not in row.lower() if _w in ("nan", "inf") else _w not in row
    _all = repr(built).lower()
    assert "nan" not in _all and "inf" not in _all


@pytest.mark.parametrize("case", sorted(_NONFINITE_L2), ids=str)
def test_chips_nonfinite_ratio_shows_approved_sentence(case, monkeypatch):
    built = _chips_built(PI, monkeypatch, l2=_NONFINITE_L2[case])
    assert CHIPS.OUTLIER_UNKNOWN == "unknown"
    _assert_approved_only(built)


@pytest.mark.parametrize("case", sorted(_NONFINITE_DF), ids=str)
def test_chips_nonfinite_ratio_from_real_l2(case, monkeypatch):
    r = INST.flag_latest_inst_outlier_from_df(_chips_df(**_NONFINITE_DF[case]))
    assert r.reason in ("ok", "outlier") and not math.isfinite(r.ratio)   # 前提成立
    _assert_approved_only(_chips_built(PI, monkeypatch, df=_chips_df(**_NONFINITE_DF[case])))


def test_chips_constant_is_the_approved_text_verbatim():
    assert PI.CHIPS_OUTLIER_UNKNOWN_NONFINITE == _APPROVED


def test_chips_truly_unknown_vocab_still_goes_other():
    v = PI.ChipsView(requested=True, outlier_verdict="unknown", outlier_reason="brand_new_token")
    row = PI._outlier_fact(v)[1]
    assert PI.CHIPS_OUTLIER_UNKNOWN_OTHER in row and _APPROVED not in row
    assert row == z48_pre_inspect()._outlier_fact(v)[1]           # 與修前逐字相同


@pytest.mark.parametrize("reason", ["vol_unavailable", "inst_net_zero", "", "brand_new_token"])
def test_chips_other_unknown_reasons_unchanged(reason):
    v = PI.ChipsView(requested=True, outlier_verdict="unknown", outlier_reason=reason)
    assert PI._outlier_fact(v) == z48_pre_inspect()._outlier_fact(v)
    assert _APPROVED not in PI._outlier_fact(v)[1]


@pytest.mark.parametrize("kw", [dict(inst_last=100.0), dict(inst_last=100000.0), dict(inst_last=0.0)],
                         ids=["normal", "anomaly", "zero"])
def test_chips_finite_paths_identical_to_pre(kw, monkeypatch):
    now = _chips_built(PI, monkeypatch, df=_chips_df(**kw))
    pre = _chips_built(z48_pre_inspect(), monkeypatch, df=_chips_df(**kw))
    assert repr(now) == repr(pre)
    assert _APPROVED not in repr(now)


def test_chips_mutation_branch_removed_turns_red(monkeypatch):
    pre = z48_pre_inspect()
    for _l2 in _NONFINITE_L2.values():
        row = _row_of(_chips_built(pre, monkeypatch, l2=_l2), pre)
        assert row != _APPROVED                                    # 還原體：不是核准文案
        assert "上游的回傳字彙" in row and "沒有異常" in row      # 還原體：OTHER ＋ HEAD
        assert _row_of(_chips_built(PI, monkeypatch, l2=_l2)) == _APPROVED


# ══════════════════════════════════════════════════════════════════════════
# 批 Z48 第 3 項（獨立 QA r1 FAIL）：L1 `_fetch_etf_price_max_cached` 的 `df.ffill()`
# ══════════════════════════════════════════════════════════════════════════
# 中段／最後一筆的 Close NaN 先被 L1 用前值補掉 → L3 的 `find_invalid_closes` 看不到 → VaR 照算
# （＝客戶禁止的「把異常值改成前值」）。上面的測試替換的是 `fetch_etf_price`，整段跳過了 L1。
# 修法：L1 在 ffill **之前**記下 Close 被補的日子放進 `attrs[PRICE_CLOSE_FFILLED_ATTR]`（只附加），
# L3 讀到（且落在 1y 切片內）→ 列入 invalid → 既有整卡中止路徑。
# 本段**只替換 yfinance 底層**（`_history_or_raise` ＋ `yf.Ticker`），L1 的 ffill／快取／切片全走真的。
import pickle  # noqa: E402

import src.data.etf.etf_fetch as EF  # noqa: E402

_L1 = 'src/data/etf/etf_fetch.py'
_L1N = 300
_L1_IDX = pd.bdate_range(end="2026-09-30", periods=_L1N)
_L1_CUTOFF = _L1_IDX[-1] - pd.Timedelta(days=365)          # `fetch_etf_price(period='1y')` 的切點
_MID, _TAIL, _OLD = _L1N - 50, _L1N - 1, 5
assert _L1_IDX[_MID] >= _L1_CUTOFF and _L1_IDX[_OLD] < _L1_CUTOFF   # 前提：一個在窗內、一個在窗外

#: ⑤ L1：補值前的記錄（拔掉 ＝ 不留旗標，ffill 照舊）。
Z48_L1_RECORD_PAIR = (
    "    _ffilled = _close_ffilled_days(df)      # 批 Z48：補值**之前**記下 Close 被補的那幾天\n",
    "    _ffilled = ()\n",
)
#: ⑥ L3：讀 L1 旗標（拔掉 ＝ 只看值，被補過的那天看不到）。
Z48_L3_READ_PAIR = (
    "        _ffilled = _ffilled_close_days(_df)\n",
    "        _ffilled = ()\n",
)


@functools.lru_cache(maxsize=None)
def z48_l1_no_record():
    return _load_variant(_L1, (Z48_L1_RECORD_PAIR,), '_z48_l1_no_record')


@functools.lru_cache(maxsize=None)
def z48_l3_no_read():
    return _load_variant(_SVC, (Z48_L3_READ_PAIR,), '_z48_l3_no_read')


def _yahoo_df(bad_at=None, bad=float("nan")):
    """yfinance `history()` 會回的形狀（大寫 OHLCV、tz-aware index）。只有 Close 那一格放異常值。"""
    v = [100.0 + (i % 7) * 0.8 for i in range(_L1N)]
    close = list(v)
    if bad_at is not None:
        close[bad_at] = bad
    return pd.DataFrame({"Open": v, "High": v, "Low": v, "Close": close,
                         "Volume": [1000] * _L1N},
                        index=_L1_IDX.tz_localize("Asia/Taipei"))


class _FakeTicker:
    def __init__(self, ticker):
        self.ticker = ticker


@pytest.fixture
def yahoo(monkeypatch):
    """只換 yfinance 底層。回傳 `(set_df, calls)`：`set_df(df, mod=EF)` 指定這一輪 Yahoo 回什麼。"""
    calls: list = []

    def set_df(df, mod=EF):
        def _hist(tk, ticker, period, **_k):
            calls.append(ticker)
            return None if df is None else df.copy()
        monkeypatch.setattr(mod, "_history_or_raise", _hist)
        monkeypatch.setattr(mod.yf, "Ticker", _FakeTicker)
        mod._fetch_etf_price_max.clear()

    yield set_df, calls
    EF._fetch_etf_price_max.clear()
    for _m in (z48_l1_no_record(),):
        _m._fetch_etf_price_max.clear()


def _l1_var(mod_l3=D, l1=EF, monkeypatch=None):
    if l1 is not EF:
        monkeypatch.setattr("src.data.etf.etf_fetch.fetch_etf_price", l1.fetch_etf_price)
    return mod_l3.get_portfolio_var(_ROWS_ONE, strict=True)


@pytest.mark.parametrize("at", [_MID, _TAIL], ids=["mid_nan", "last_nan"])
def test_l1_records_ffilled_close_days(at, yahoo):
    set_df, _ = yahoo
    set_df(_yahoo_df(at))
    out = EF.fetch_etf_price("2330.TW", period="max")
    assert out.attrs[EF.PRICE_CLOSE_FFILLED_ATTR] == (_L1_IDX[at].strftime("%Y-%m-%d"),)
    assert not out["Close"].isna().any(), "前提：L1 的 ffill 照舊（值上已看不出那一天）"


def test_l1_values_identical_to_pre_batch(yahoo):
    """其他 caller 看到的 df：值與修前逐值相同；attrs 只多一個鍵。"""
    set_df, _ = yahoo
    for period in ("1y", "5y", "max"):
        set_df(_yahoo_df(_MID))
        now = EF.fetch_etf_price("2330.TW", period=period)
        pre_mod = z48_l1_no_record()
        set_df(_yahoo_df(_MID), mod=pre_mod)
        pre = pre_mod.fetch_etf_price("2330.TW", period=period)
        pd.testing.assert_frame_equal(now, pre)
        _a = {k: v for k, v in now.attrs.items() if k not in ("fetched_at", EF.PRICE_CLOSE_FFILLED_ATTR)}
        _b = {k: v for k, v in pre.attrs.items() if k != "fetched_at"}
        assert _a == _b and EF.PRICE_CLOSE_FFILLED_ATTR not in pre.attrs


def test_l1_normal_data_has_no_flag(yahoo):
    set_df, _ = yahoo
    set_df(_yahoo_df())
    out = EF.fetch_etf_price("2330.TW", period="1y")
    assert EF.PRICE_CLOSE_FFILLED_ATTR not in out.attrs
    assert set(out.attrs) == {"source", "fetched_at", "price_basis"}


def test_l1_leading_nan_is_not_called_ffilled(yahoo):
    """開頭沒有前值可補 → 仍是 NaN（不記成被補）；L3 由值本身看得到。"""
    set_df, _ = yahoo
    set_df(_yahoo_df(0))
    out = EF.fetch_etf_price("2330.TW", period="max")
    assert EF.PRICE_CLOSE_FFILLED_ATTR not in out.attrs and math.isnan(out["Close"].iloc[0])


def test_l1_flag_survives_cache_hit_and_pickle(yahoo):
    """attrs 穿過 `@st.cache_data`（命中時回的是反序列化的複本）與 `fetch_etf_price` 的切片包裝。"""
    set_df, calls = yahoo
    set_df(_yahoo_df(_MID))
    first = EF._fetch_etf_price_max_cached("2330.TW")
    second = EF._fetch_etf_price_max_cached("2330.TW")
    assert calls == ["2330.TW"], f"第二次應命中快取：{calls}"
    assert second is not first, "前提：命中時是另一個物件（經序列化）"
    _want = (_L1_IDX[_MID].strftime("%Y-%m-%d"),)
    assert second.attrs[EF.PRICE_CLOSE_FFILLED_ATTR] == _want
    assert pickle.loads(pickle.dumps(first)).attrs[EF.PRICE_CLOSE_FFILLED_ATTR] == _want
    assert EF.fetch_etf_price("2330.TW", period="1y").attrs[EF.PRICE_CLOSE_FFILLED_ATTR] == _want
    assert calls == ["2330.TW"]


@pytest.mark.parametrize("at", [_MID, _TAIL], ids=["mid_nan", "last_nan"])
def test_var_through_real_l1_ffilled_nan_stops_the_card(at, yahoo):
    set_df, _ = yahoo
    set_df(_yahoo_df(at))
    res = _l1_var()
    assert res.computed is False and res.reason == D.REASON_INVALID_CLOSE
    assert res.invalid_close == (("2330.TW", _L1_IDX[at].strftime("%Y-%m-%d")),)
    assert all(getattr(res, _f) == 0.0 for _f in _MONEY)
    built = _card(PH, res)
    assert built[0].state == UI_EMPTY and built[0].note.now == PH.VAR_INVALID_CLOSE_NOW
    _blob_l = _blob(PH, built).lower()
    assert "nan" not in _blob_l and "inf" not in _blob_l


@pytest.mark.parametrize("bad", [0.0, -5.0, float("inf")], ids=["zero", "negative", "inf"])
def test_var_through_real_l1_other_bad_values(bad, yahoo):
    set_df, _ = yahoo
    set_df(_yahoo_df(_MID, bad))
    res = _l1_var()
    assert res.computed is False and res.invalid_close == (("2330.TW", _L1_IDX[_MID].strftime("%Y-%m-%d")),)


def test_var_through_real_l1_normal_unchanged(yahoo, monkeypatch):
    set_df, _ = yahoo
    set_df(_yahoo_df())
    now = dataclasses.asdict(_l1_var())
    pre = dataclasses.asdict(_l1_var(mod_l3=z48_pre_svc()))
    assert now == pre and now["computed"] is True


def test_var_ignores_ffill_outside_the_1y_window(yahoo):
    """L1 旗標記的是 max 整段；落在 1y 切片外的補值與本次 VaR 無關 → 照算（且與修前相同）。"""
    set_df, _ = yahoo
    set_df(_yahoo_df(_OLD))
    res = _l1_var()
    assert EF._fetch_etf_price_max("2330.TW").attrs[EF.PRICE_CLOSE_FFILLED_ATTR]   # 前提：L1 有記
    assert res.computed is True and res.invalid_close == ()
    assert dataclasses.asdict(res) == dataclasses.asdict(_l1_var(mod_l3=z48_pre_svc()))


def test_l3_ffilled_days_without_date_range_keeps_all():
    df = pd.DataFrame({"Close": [1.0, 2.0]}, index=[0, 1])
    df.attrs[EF.PRICE_CLOSE_FFILLED_ATTR] = ("2026-01-05",)
    assert D._ffilled_close_days(df) == ("2026-01-05",)
    assert D._ffilled_close_days(pd.DataFrame({"Close": [1.0]})) == ()


# ── 突變：拔掉 L1 記錄／拔掉 L3 讀取 → 中段 NaN 又照算 ──────────────────────
def test_mutation_l1_record_removed_turns_red(yahoo, monkeypatch):
    set_df, _ = yahoo
    _orig = EF.fetch_etf_price
    m = z48_l1_no_record()
    set_df(_yahoo_df(_MID), mod=m)
    res = _l1_var(l1=m, monkeypatch=monkeypatch)
    assert res.computed is True and res.invalid_close == ()     # 還原體：前值補過的那天照算
    set_df(_yahoo_df(_MID))
    monkeypatch.setattr("src.data.etf.etf_fetch.fetch_etf_price", _orig)
    assert _l1_var().computed is False


def test_mutation_l3_read_removed_turns_red(yahoo):
    set_df, _ = yahoo
    set_df(_yahoo_df(_MID))
    res = _l1_var(mod_l3=z48_l3_no_read())
    assert res.computed is True and res.invalid_close == ()     # 還原體：看不到 L1 的旗標
    assert _l1_var().computed is False
