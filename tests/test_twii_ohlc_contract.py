"""tests/test_twii_ohlc_contract.py — Issue #1099 PR-1：TWII 日 K OHLC 唯讀、fail-closed 資料契約。

涵蓋三層：
- L0 `shared/twii_ohlc_contract.validate_ohlc_window`：正例＋每一個原因碼的負例（first violation wins）。
- L1 `macro_cache_reader.load_twii_ohlc`：tmp parquet（缺檔／缺欄／attrs／排除 volume／不去重不 dropna）。
- L3 `market_twii_view_service.get_twii_trend_view(..., with_ohlc=True)`：tmp parquet（20 根、5 根不足、
  違規 → ohlc_ok False 且 OHLC 空、收盤卡照常、例外 → failed）＋真 repo parquet 同源對帳＋G2F 白名單唯讀守衛。
"""
from __future__ import annotations

import ast
import json
import math
import pathlib
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from shared import twii_ohlc_contract as C
from src.data.macro import macro_cache_reader as R
from src.services import market_twii_view_service as S

REPO = pathlib.Path(__file__).resolve().parents[1]
TPE = timezone(timedelta(hours=8))


# ══════════════════════════════════════════════════════════════════════════
# L0 validator
# ══════════════════════════════════════════════════════════════════════════
def _bars(n=5, start=date(2026, 10, 1)):
    """n 根合法完整日 K（抓取於次日台北 01:00 ⇒ 完整）。"""
    ds, o, h, lo, c, fa = [], [], [], [], [], []
    for i in range(n):
        d = start + timedelta(days=i)
        ds.append(d.isoformat())
        o.append(100.0 + i)
        c.append(101.0 + i)
        h.append(102.0 + i)
        lo.append(99.0 + i)
        _nxt = d + timedelta(days=1)
        fa.append(datetime(_nxt.year, _nxt.month, _nxt.day, 1, 0, tzinfo=TPE).astimezone(timezone.utc).isoformat())
    return dict(dates=ds, opens=o, highs=h, lows=lo, closes=c, fetched_at=fa)


def _v(b, *, as_of="__last__", today=date(2026, 12, 31)):
    if as_of == "__last__":
        as_of = b["dates"][-1] if b["dates"] else None
    return C.validate_ohlc_window(b["dates"], b["opens"], b["highs"], b["lows"], b["closes"], b["fetched_at"],
                                  as_of=as_of, today=today)


def test_valid_window_ok():
    assert _v(_bars(20)) == (True, C.OHLC_OK, "")


def test_as_of_none_skips_as_of_check():
    assert _v(_bars(3), as_of=None)[0] is True


def test_doji_open_equals_close_is_valid():
    b = _bars(2)
    b["closes"][1] = b["opens"][1]
    assert _v(b)[0] is True


def test_empty():
    b = dict(dates=[], opens=[], highs=[], lows=[], closes=[], fetched_at=[])
    assert _v(b, as_of=None)[:2] == (False, C.EMPTY)


@pytest.mark.parametrize("key", ["opens", "highs", "lows", "closes", "fetched_at"])
def test_unequal_lengths(key):
    b = _bars(3)
    b[key] = b[key][:-1]
    assert _v(b)[:2] == (False, C.LENGTH_MISMATCH)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), None, "abc", True])
@pytest.mark.parametrize("key", ["opens", "highs", "lows", "closes"])
def test_not_finite(key, bad):
    b = _bars(3)
    b[key][1] = bad
    ok, code, detail = _v(b)
    assert (ok, code) == (False, C.NOT_FINITE) and b["dates"][1] in detail


@pytest.mark.parametrize("bad", [0.0, -1.0])
@pytest.mark.parametrize("key", ["opens", "highs", "lows", "closes"])
def test_non_positive(key, bad):
    b = _bars(3)
    b[key][2] = bad
    ok, code, detail = _v(b)
    assert (ok, code) == (False, C.NON_POSITIVE) and b["dates"][2] in detail


@pytest.mark.parametrize("mut", [
    ("lows", 100.5),     # low > open (open=100)
    ("lows", 103.0),     # low > high
    ("highs", 100.5),    # high < close (close=101)
    ("highs", 99.5),     # high < open
])
def test_ohlc_relation(mut):
    b = _bars(3)
    key, val = mut
    b[key][0] = val
    ok, code, detail = _v(b)
    assert (ok, code) == (False, C.OHLC_RELATION) and b["dates"][0] in detail


def test_duplicate_date():
    b = _bars(3)
    b["dates"][2] = b["dates"][1]
    ok, code, detail = _v(b, as_of=None)
    assert (ok, code) == (False, C.DUPLICATE_DATE) and b["dates"][1] in detail


def test_not_ascending():
    b = _bars(3)
    for k in b:                          # 整列對調（各欄一致）⇒ 只剩順序錯
        b[k][1], b[k][2] = b[k][2], b[k][1]
    ok, code, detail = _v(b, as_of=None)
    assert (ok, code) == (False, C.NOT_ASCENDING) and b["dates"][2] in detail


def test_bad_date():
    b = _bars(3)
    b["dates"][0] = "2026/10/01"
    assert _v(b, as_of=None)[:2] == (False, C.BAD_DATE)


def test_future_date():
    b = _bars(3)
    ok, code, detail = _v(b, today=date.fromisoformat(b["dates"][1]))
    assert (ok, code) == (False, C.FUTURE_DATE) and b["dates"][2] in detail


def _fetch_at(b, i, local: datetime):
    b["fetched_at"][i] = local.astimezone(timezone.utc).isoformat()


def test_incomplete_bar_fetched_same_day_1659_taipei():
    b = _bars(3)
    d = date.fromisoformat(b["dates"][2])
    _fetch_at(b, 2, datetime(d.year, d.month, d.day, 16, 59, 59, tzinfo=TPE))
    ok, code, detail = _v(b)
    assert (ok, code) == (False, C.INCOMPLETE_BAR) and b["dates"][2] in detail


def test_complete_bar_fetched_same_day_1700_taipei():
    b = _bars(3)
    d = date.fromisoformat(b["dates"][2])
    _fetch_at(b, 2, datetime(d.year, d.month, d.day, C.TWII_BAR_TRUSTED_AFTER_TAIPEI_HOUR, 0, tzinfo=TPE))
    assert _v(b)[0] is True


def test_complete_bar_fetched_next_day_early_morning():
    b = _bars(3)
    d = date.fromisoformat(b["dates"][2]) + timedelta(days=1)
    _fetch_at(b, 2, datetime(d.year, d.month, d.day, 0, 5, tzinfo=TPE))
    assert _v(b)[0] is True


def test_fetched_before_bar_date_is_incomplete():
    b = _bars(3)
    d = date.fromisoformat(b["dates"][2]) - timedelta(days=1)
    _fetch_at(b, 2, datetime(d.year, d.month, d.day, 20, 0, tzinfo=TPE))
    assert _v(b)[:2] == (False, C.INCOMPLETE_BAR)


def test_utc_1659_vs_taipei_conversion():
    """UTC 08:59 ＝ 台北 16:59（未完成）；UTC 09:00 ＝ 台北 17:00（完整，與 cron 0 9 * * * 對齊）。"""
    b = _bars(1)
    d = date.fromisoformat(b["dates"][0])
    b["fetched_at"][0] = f"{d.isoformat()}T08:59:00+00:00"
    assert _v(b)[:2] == (False, C.INCOMPLETE_BAR)
    b["fetched_at"][0] = f"{d.isoformat()}T09:00:00+00:00"
    assert _v(b)[0] is True


@pytest.mark.parametrize("bad", [None, "", "not-a-time", "2026-10-02T03:00:00", float("nan"), 123])
def test_fetched_at_missing_naive_or_unparseable(bad):
    b = _bars(3)
    b["fetched_at"][1] = bad
    ok, code, detail = _v(b)
    assert (ok, code) == (False, C.FETCHED_AT_MISSING) and b["dates"][1] in detail


def test_as_of_mismatch():
    b = _bars(3)
    ok, code, detail = _v(b, as_of=b["dates"][1])
    assert (ok, code) == (False, C.AS_OF_MISMATCH) and b["dates"][2] in detail


def test_first_violation_wins_by_row_order():
    b = _bars(4)
    b["highs"][1] = 50.0                 # row 2: relation
    b["closes"][3] = float("nan")        # row 4: not finite
    assert _v(b)[1] == C.OHLC_RELATION


def test_trusted_hour_constant_is_17():
    assert C.TWII_BAR_TRUSTED_AFTER_TAIPEI_HOUR == 17


def test_l0_is_pure_stdlib():
    """L0：不 import pandas／streamlit／src.*（CLAUDE.md §8.2 L0↛L1+）。"""
    tree = ast.parse((REPO / "shared/twii_ohlc_contract.py").read_text(encoding="utf-8"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add((n.module or "").split(".")[0])
    assert mods <= {"__future__", "math", "datetime", "typing", "zoneinfo"}, mods


# ══════════════════════════════════════════════════════════════════════════
# L1 load_twii_ohlc（tmp parquet）
# ══════════════════════════════════════════════════════════════════════════
def _frame(n=20, start=date(2026, 10, 1)):
    b = _bars(n, start)
    return pd.DataFrame({
        "date": [date.fromisoformat(d) for d in b["dates"]],
        "open": b["opens"], "high": b["highs"], "low": b["lows"], "close": b["closes"],
        "volume": [float("nan")] * n, "source": ["Yahoo:^TWII:chart"] * n, "fetched_at": b["fetched_at"],
    })


def _write(tmp_path, df, *, last_error=None):
    df.to_parquet(tmp_path / "twii_ohlcv.parquet")
    (tmp_path / "metadata.json").write_text(json.dumps({"datasets": {"twii_ohlcv": {
        "last_updated": "2026-10-21T09:00:00+00:00", "row_count": len(df), "last_error": last_error}}}),
        encoding="utf-8")


def test_l1_missing_file_returns_empty_with_columns(tmp_path):
    out = R.load_twii_ohlc(tmp_path)
    assert out.empty and list(out.columns) == list(R.TWII_OHLC_COLUMNS)


def test_l1_missing_column_returns_empty(tmp_path):
    _write(tmp_path, _frame(5).drop(columns=["fetched_at"]))
    out = R.load_twii_ohlc(tmp_path)
    assert out.empty and list(out.columns) == list(R.TWII_OHLC_COLUMNS)


def test_l1_reads_ohlc_excludes_volume_and_attaches_staleness(tmp_path):
    _write(tmp_path, _frame(20))
    out = R.load_twii_ohlc(tmp_path, today=date(2026, 10, 21))
    assert list(out.columns) == ["open", "high", "low", "close", "fetched_at"]
    assert "volume" not in out.columns and "source" not in out.columns
    assert isinstance(out.index, pd.DatetimeIndex) and out.index.is_monotonic_increasing and len(out) == 20
    for k in ("cache_dataset", "is_stale", "stale_reason", "as_of", "age_days", "upstream_error"):
        assert k in out.attrs, k
    assert out.attrs["cache_dataset"] == "twii_ohlcv"
    assert out.attrs["as_of"] == date(2026, 10, 20) and out.attrs["is_stale"] is False


def test_l1_does_not_dedupe_or_dropna_and_sorts(tmp_path):
    df = _frame(5)
    df.loc[2, "close"] = float("nan")
    df = pd.concat([df, df.iloc[[1]]]).iloc[::-1].reset_index(drop=True)   # 重複一列＋倒序
    _write(tmp_path, df)
    out = R.load_twii_ohlc(tmp_path, today=date(2026, 10, 21))
    assert len(out) == 6 and out.index.is_monotonic_increasing      # ⛔ 不去重
    assert out["close"].isna().sum() == 1                            # ⛔ 不 dropna


def test_l1_load_twii_close_unchanged_alongside(tmp_path):
    _write(tmp_path, _frame(5))
    s = R.load_twii_close(tmp_path, today=date(2026, 10, 21))
    assert s.name == "twii_close" and len(s) == 5


# ══════════════════════════════════════════════════════════════════════════
# L3 with_ohlc（tmp parquet，經 monkeypatch 把 L1 cache_dir 指到 tmp）
# ══════════════════════════════════════════════════════════════════════════
@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "DEFAULT_PARQUET_CACHE_DIR", tmp_path)
    _orig_ohlc, _orig_close = R.load_twii_ohlc, R.load_twii_close
    monkeypatch.setattr(R, "load_twii_ohlc", lambda *a, **k: _orig_ohlc(tmp_path, **k))
    monkeypatch.setattr(R, "load_twii_close", lambda *a, **k: _orig_close(tmp_path, **k))
    return tmp_path


T_AFTER = date(2026, 11, 9)


def test_l3_with_ohlc_ok_20_bars(tmp_cache):
    _write(tmp_cache, _frame(30))
    v = S.get_twii_trend_view(20, with_ohlc=True, today=T_AFTER)
    assert v.ok and v.ohlc_requested and v.ohlc_ok is True and v.ohlc_error == "" and v.ohlc_detail == ""
    assert v.n_ohlc == 20 and len(v.xs) == len(v.close) == len(v.open) == len(v.high) == len(v.low) == 20
    assert v.as_of == v.xs[-1] == "2026-10-30"
    assert all(lo <= min(o, c) <= max(o, c) <= h for o, h, lo, c in zip(v.open, v.high, v.low, v.close))
    base = S.get_twii_trend_view(20, today=T_AFTER)
    assert (base.xs, base.close, base.as_of, base.is_stale) == (v.xs, v.close, v.as_of, v.is_stale)
    assert base.ohlc_requested is False and base.ohlc_ok is None and base.open == ()


def test_l3_partial_5_bars_not_padded(tmp_cache):
    _write(tmp_cache, _frame(5))
    v = S.get_twii_trend_view(20, with_ohlc=True, today=T_AFTER)
    assert v.ok and v.ohlc_ok is True and v.n_ohlc == 5 and len(v.open) == len(v.xs) == 5


def test_l3_violation_empties_ohlc_but_close_card_works(tmp_cache):
    df = _frame(20)
    df.loc[19, "high"] = 1.0              # 最後一根 high < close
    _write(tmp_cache, df)
    v = S.get_twii_trend_view(20, with_ohlc=True, today=T_AFTER)
    assert v.ok is True and len(v.close) == 20 and v.as_of == "2026-10-20"      # 收盤卡照常
    assert v.ohlc_requested and v.ohlc_ok is False and v.ohlc_error == C.OHLC_RELATION
    assert "2026-10-20" in v.ohlc_detail
    assert v.open == v.high == v.low == () and v.n_ohlc == 0                     # ⛔ 不部分填


def test_l3_nan_close_in_window_fails_closed(tmp_cache):
    df = _frame(20)
    df.loc[19, "close"] = float("nan")
    _write(tmp_cache, df)
    v = S.get_twii_trend_view(5, with_ohlc=True, today=T_AFTER)
    assert v.ok is True and v.ohlc_ok is False and v.ohlc_error == C.NOT_FINITE and v.open == ()


def test_l3_incomplete_last_bar_fails_closed(tmp_cache):
    df = _frame(20)
    df.loc[19, "fetched_at"] = "2026-10-20T08:30:00+00:00"   # 台北 16:30 當日
    _write(tmp_cache, df)
    v = S.get_twii_trend_view(20, with_ohlc=True, today=T_AFTER)
    assert v.ohlc_ok is False and v.ohlc_error == C.INCOMPLETE_BAR and v.open == ()


def test_l3_future_bar_fails_closed(tmp_cache):
    _write(tmp_cache, _frame(20))
    v = S.get_twii_trend_view(20, with_ohlc=True, today=date(2026, 10, 15))
    assert v.ohlc_ok is False and v.ohlc_error == C.FUTURE_DATE


def test_l3_missing_file_is_gray_not_red(tmp_cache):
    v = S.get_twii_trend_view(20, with_ohlc=True, today=T_AFTER)
    assert v.ok is False and v.failed is False and v.ohlc_ok is False and v.ohlc_error == C.EMPTY
    assert v.open == () and v.xs == ()


def test_l3_exception_path_is_failed(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("disk gone")
    monkeypatch.setattr(R, "load_twii_ohlc", _boom)
    v = S.get_twii_trend_view(20, with_ohlc=True, today=T_AFTER)
    assert v.ok is False and v.failed is True and "disk gone" in v.error
    assert v.ohlc_requested and v.ohlc_ok is False and v.ohlc_error == C.READ_FAILED and v.open == ()


def test_l3_with_ohlc_false_does_not_touch_ohlc_loader(monkeypatch):
    """with_ohlc=False ＝ 原路徑：只讀 load_twii_close（⛔ 不讀 OHLC）。"""
    def _boom(*a, **k):
        raise AssertionError("with_ohlc=False 不得讀 load_twii_ohlc")
    monkeypatch.setattr(R, "load_twii_ohlc", _boom)
    _idx = pd.date_range("2026-10-20", periods=3, freq="D")
    s = pd.Series([1.0, 2.0, 3.0], index=_idx, name="twii_close")
    s.attrs.update({"is_stale": False, "as_of": _idx[-1].date(), "age_days": 1})
    monkeypatch.setattr(R, "load_twii_close", lambda *a, **k: s)
    v = S.get_twii_trend_view(3)
    assert v.ok and v.ohlc_requested is False and v.ohlc_ok is None and v.n_ohlc == 0


def test_l3_positional_construction_still_valid():
    v = S.TwiiTrendView(True, ("2026-10-01",), (1.0,))
    assert v.ohlc_ok is None and v.open == () and v.source == S.TWII_SOURCE_TEXT


# ══════════════════════════════════════════════════════════════════════════
# 真 repo parquet 對帳（同源：with_ohlc False vs True）
# ══════════════════════════════════════════════════════════════════════════
def test_real_parquet_parity_and_ohlc_ok():
    p = REPO / "data_cache" / "twii_ohlcv.parquet"
    if not p.exists():
        pytest.skip("沙箱沒有 data_cache/twii_ohlcv.parquet")
    # 基準日固定在「最後一根之後一天」⇒ 不受日後 cron 新增列影響（DEC-156 驗收例：2026-11-09）。
    last = max(pd.to_datetime(pd.read_parquet(p, columns=["date"])["date"]).dt.date)
    today = max(date(2026, 11, 9), last + timedelta(days=1))
    a = S.get_twii_trend_view(20, today=today)
    b = S.get_twii_trend_view(20, with_ohlc=True, today=today)
    assert a.ok and b.ok
    assert (a.xs, a.close, a.as_of, a.is_stale, a.age_days, a.n_available) == \
           (b.xs, b.close, b.as_of, b.is_stale, b.age_days, b.n_available)
    assert b.ohlc_ok is True, (b.ohlc_error, b.ohlc_detail)
    assert b.n_ohlc == 20 and len(b.open) == 20 and all(math.isfinite(x) for x in b.open + b.high + b.low)


# ══════════════════════════════════════════════════════════════════════════
# G2F 白名單唯讀守衛（本 PR 不得擴 real_feed 的 import 面）
# ══════════════════════════════════════════════════════════════════════════
def test_g2f_allowlist_for_twii_service_unchanged():
    from tests.test_ui2_guards import G2F_IMPORT_ALLOWLIST
    assert G2F_IMPORT_ALLOWLIST["src.services.market_twii_view_service"] == frozenset({"get_twii_trend_view"})
