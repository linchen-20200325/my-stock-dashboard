"""tests/test_margin_fact_service.py — 融資事實 L3 唯讀層（Issue #1140 §B）。

零網路；today 與 cache_dir 一律注入。覆蓋：判定順序 1~9、reason→state 單一對照、sanity 開區間邊界、
未來日、as_of 對帳、stale 邊界、attrs 缺 is_stale、無值態 value 必為 None、禁字／import／網路／範圍守衛、
真實 data_cache 一次。
"""
from __future__ import annotations

import ast
import dataclasses
import datetime as dt
import math
import pathlib
import re

import numpy as np
import pandas as pd
import pytest

# 先完成 barrel／L1 import（macro barrel 會 eager 載入 streamlit——已知事實），之後才 patch 網路。
import src.data.macro.macro_cache_reader as R
from shared.margin_schema import margin_sanity_ok
from shared.signal_thresholds import MARGIN_BALANCE_SANITY_MAX_YI, MARGIN_BALANCE_SANITY_MIN_YI
from shared.staleness import STALE_DAYS_DAILY
from shared.ui2_contract.models import FieldState
from src.services import margin_fact_service as S

_REPO = pathlib.Path(__file__).resolve().parents[1]
_SVC_PATH = pathlib.Path(S.__file__)
_SRC = _SVC_PATH.read_text(encoding="utf-8")
_TODAY = dt.date(2026, 11, 11)
_YI = 1e8     # 元 → 億（與 shared.margin_schema.TWD_PER_YI 同值；測試自帶以便抓換算常數被改）


def _write(tmp_path, rows, *, name="finmind_margin.parquet"):
    """rows: [(date_str, margin_balance_元)]；NaN 允許。"""
    pd.DataFrame({
        "date": [r[0] for r in rows],
        "margin_balance": [r[1] for r in rows],
        "source": "FinMind:test",
        "fetched_at": "2026-11-10T00:00:00+00:00",
    }).to_parquet(tmp_path / name)


def _rows_ending(last: dt.date, last_yi: float = 5399.15741, n: int = 5):
    days = [last - dt.timedelta(days=n - 1 - i) for i in range(n)]
    return [(d.isoformat(), (5000.0 + i) * _YI) for i, d in enumerate(days[:-1])] + [(last.isoformat(), last_yi * _YI)]


def _fact(tmp_path, rows, today=_TODAY):
    _write(tmp_path, rows)
    return S.get_margin_fact(today=today, cache_dir=tmp_path)


def _patch_series(monkeypatch, s):
    monkeypatch.setattr(R, "load_v2_chart_series",
                        lambda *a, **k: ({} if s is None else {"margin": s}))


def _series(values, last="2026-11-09", attrs=None):
    idx = pd.date_range(end=pd.Timestamp(last), periods=len(values), freq="D")
    s = pd.Series(values, index=idx, name="margin", dtype=float)
    s.attrs.update(attrs if attrs is not None else {
        "is_stale": False, "stale_reason": None, "as_of": idx[-1].date(), "age_days": 2, "upstream_error": None})
    return s


# ═════════════ 正常 ═════════════
def test_ok_value_not_rounded(tmp_path):
    f = _fact(tmp_path, _rows_ending(dt.date(2026, 11, 9)))
    assert f.state is FieldState.OK and f.reason == ""
    assert f.value_yi == 5399.15741          # 不 round
    assert f.unit == "億元" and f.as_of == "2026-11-09"
    assert f.is_stale is False and f.age_days == 2 and f.stale_reason == ""
    assert f.upstream_state == "" and f.source == S.MARGIN_SOURCE_TEXT
    assert f.sanity_interval_yi == (MARGIN_BALANCE_SANITY_MIN_YI, MARGIN_BALANCE_SANITY_MAX_YI)


def test_today_none_uses_taipei_today_and_passes_it_to_l1(tmp_path, monkeypatch):
    seen = {}

    def _spy(cache_dir, *, today=None):
        seen["today"], seen["dir"] = today, cache_dir
        return {"margin": _series([5000.0, 5399.15741], last="2026-11-09")}
    monkeypatch.setattr(R, "load_v2_chart_series", _spy)
    import shared.macro_compute as MC
    monkeypatch.setattr(MC, "tw_now", lambda: dt.datetime(2026, 11, 11, 23, 30, tzinfo=dt.timezone(dt.timedelta(hours=8))))
    f = S.get_margin_fact(cache_dir=tmp_path)
    assert seen["today"] == dt.date(2026, 11, 11) and seen["dir"] == tmp_path
    assert f.state is FieldState.OK


def test_default_cache_dir_is_absolute_repo_root():
    d = S._default_cache_dir()
    assert d.is_absolute() and d == _REPO / "data_cache"


# ═════════════ 缺檔／壞檔／缺欄／空檔 ═════════════
def test_missing_file(tmp_path):
    f = S.get_margin_fact(today=_TODAY, cache_dir=tmp_path)
    assert (f.state, f.reason, f.value_yi) == (FieldState.MISSING, "source_absent_or_unreadable", None)


def test_empty_file(tmp_path):
    pd.DataFrame({"date": [], "margin_balance": []}).to_parquet(tmp_path / "finmind_margin.parquet")
    f = S.get_margin_fact(today=_TODAY, cache_dir=tmp_path)
    assert f.reason == "source_absent_or_unreadable" and f.value_yi is None


def test_missing_column(tmp_path):
    pd.DataFrame({"date": ["2026-11-09"], "other": [1.0]}).to_parquet(tmp_path / "finmind_margin.parquet")
    f = S.get_margin_fact(today=_TODAY, cache_dir=tmp_path)
    assert f.reason == "source_absent_or_unreadable" and f.state is FieldState.MISSING


def test_corrupt_file(tmp_path):
    (tmp_path / "finmind_margin.parquet").write_bytes(b"not a parquet file")
    f = S.get_margin_fact(today=_TODAY, cache_dir=tmp_path)
    assert f.reason == "source_absent_or_unreadable" and f.value_yi is None


def test_all_nan_collapsed_by_l1(tmp_path):
    f = _fact(tmp_path, [("2026-11-06", np.nan), ("2026-11-09", np.nan)])
    assert f.reason == "source_absent_or_unreadable" and f.value_yi is None


# ═════════════ 例外 ═════════════
def test_l1_exception_is_unavailable(monkeypatch, tmp_path):
    def _boom(*a, **k):
        raise RuntimeError("disk gone")
    monkeypatch.setattr(R, "load_v2_chart_series", _boom)
    f = S.get_margin_fact(today=_TODAY, cache_dir=tmp_path)
    assert (f.state, f.reason, f.value_yi) == (FieldState.UNAVAILABLE, "read_exception", None)
    assert "RuntimeError" in f.detail and "disk gone" in f.detail


def test_empty_series_or_none(monkeypatch, tmp_path):
    for bad in (None, pd.Series(dtype=float)):
        _patch_series(monkeypatch, bad)
        f = S.get_margin_fact(today=_TODAY, cache_dir=tmp_path)
        assert f.reason == "source_absent_or_unreadable"


# ═════════════ 非有限 ═════════════
@pytest.mark.parametrize("bad", (np.nan, np.inf, -np.inf))
def test_non_finite_latest(monkeypatch, tmp_path, bad):
    _patch_series(monkeypatch, _series([5000.0, bad]))
    f = S.get_margin_fact(today=_TODAY, cache_dir=tmp_path)
    assert (f.state, f.reason, f.value_yi) == (FieldState.MISSING, "value_not_finite", None)


def test_non_finite_not_masked_by_earlier_good_value(monkeypatch, tmp_path):
    # 最新值壞，即使前一點是好的，也不得退回前一點（不補值）
    _patch_series(monkeypatch, _series([5399.0, np.nan]))
    assert S.get_margin_fact(today=_TODAY, cache_dir=tmp_path).value_yi is None


# ═════════════ sanity 邊界（開區間）═════════════
@pytest.mark.parametrize("v", (500.0, 10000.0, 0.0, -1.0, -5000.0, 499.99, 10000.01))
def test_sanity_reject(monkeypatch, tmp_path, v):
    _patch_series(monkeypatch, _series([5000.0, v]))
    f = S.get_margin_fact(today=_TODAY, cache_dir=tmp_path)
    assert (f.state, f.reason, f.value_yi) == (FieldState.MISSING, "unit_sanity_failed", None)


@pytest.mark.parametrize("v", (500.0000001, 9999.9999999, 5399.15741))
def test_sanity_accept(monkeypatch, tmp_path, v):
    _patch_series(monkeypatch, _series([5000.0, v]))
    f = S.get_margin_fact(today=_TODAY, cache_dir=tmp_path)
    assert f.state is FieldState.OK and f.value_yi == v


def test_sanity_agrees_with_ssot_function():
    for v in (500.0, 10000.0, 500.0000001, 9999.9999999):
        assert margin_sanity_ok(v) == (500.0 < v < 10000.0)
    assert (MARGIN_BALANCE_SANITY_MIN_YI, MARGIN_BALANCE_SANITY_MAX_YI) == (500.0, 10000.0)


# ═════════════ 單位 ═════════════
def test_unit_yuan_fed_converts_into_range(tmp_path):
    f = _fact(tmp_path, _rows_ending(dt.date(2026, 11, 9), last_yi=6196.48244))   # 619,648,244,000 元
    assert f.state is FieldState.OK and math.isclose(f.value_yi, 6196.48244, rel_tol=1e-12)


@pytest.mark.parametrize("scale", (1e3, 1e-3))
def test_unit_off_by_1e3_rejected(tmp_path, scale):
    f = _fact(tmp_path, _rows_ending(dt.date(2026, 11, 9), last_yi=5399.15741 * scale))
    assert f.reason == "unit_sanity_failed" and f.value_yi is None


def test_unit_volume_scale_rejected(tmp_path):
    # 「張」量級（~1e7）被誤當金額：除 1e8 後遠低於 500 億
    f = _fact(tmp_path, [("2026-11-06", 9_614_955), ("2026-11-09", 9_614_955)])
    assert f.reason == "unit_sanity_failed"


# ═════════════ 未來日／as_of ═════════════
def test_asof_equals_today_ok(tmp_path):
    f = _fact(tmp_path, _rows_ending(_TODAY))
    assert f.state is FieldState.OK and f.as_of == _TODAY.isoformat() and f.age_days == 0


def test_future_asof_plus_one_rejected(tmp_path):
    f = _fact(tmp_path, _rows_ending(_TODAY + dt.timedelta(days=1)))
    assert (f.state, f.reason, f.value_yi, f.as_of) == (FieldState.MISSING, "future_as_of", None, None)


def test_future_asof_does_not_fall_back_to_earlier_point(tmp_path):
    f = _fact(tmp_path, _rows_ending(_TODAY + dt.timedelta(days=3), n=5))
    assert f.value_yi is None


def test_asof_mismatch_real_path_last_row_nan(tmp_path):
    # 最後一列融資為 NaN：L1 dropna 後序列尾端 = 11-06，但 attrs.as_of（df 的 date 最大值）= 11-09
    rows = _rows_ending(dt.date(2026, 11, 6), n=4) + [("2026-11-09", np.nan)]
    f = _fact(tmp_path, rows)
    assert (f.state, f.reason, f.value_yi) == (FieldState.MISSING, "as_of_mismatch", None)
    assert "2026-11-09" in f.detail and "2026-11-06" in f.detail


def test_asof_mismatch_unparseable_attr_fails_closed(monkeypatch, tmp_path):
    s = _series([5000.0, 5399.0], attrs={"is_stale": False, "as_of": "not-a-date", "age_days": 1})
    _patch_series(monkeypatch, s)
    assert S.get_margin_fact(today=_TODAY, cache_dir=tmp_path).reason == "as_of_mismatch"


def test_asof_attr_absent_is_not_mismatch(monkeypatch, tmp_path):
    s = _series([5000.0, 5399.0], attrs={"is_stale": False, "age_days": 2})
    _patch_series(monkeypatch, s)
    assert S.get_margin_fact(today=_TODAY, cache_dir=tmp_path).state is FieldState.OK


def test_asof_attr_as_string_or_timestamp_matches(monkeypatch, tmp_path):
    for a in ("2026-11-09", pd.Timestamp("2026-11-09")):
        _patch_series(monkeypatch, _series([5000.0, 5399.0], attrs={"is_stale": False, "as_of": a, "age_days": 2}))
        assert S.get_margin_fact(today=_TODAY, cache_dir=tmp_path).state is FieldState.OK


# ═════════════ stale ═════════════
def test_stale_boundary_7_days_not_stale_8_days_stale(tmp_path):
    assert STALE_DAYS_DAILY == 7
    last = dt.date(2026, 11, 9)
    f7 = _fact(tmp_path, _rows_ending(last), today=last + dt.timedelta(days=7))
    assert f7.state is FieldState.OK and f7.is_stale is False and f7.age_days == 7
    f8 = S.get_margin_fact(today=last + dt.timedelta(days=8), cache_dir=tmp_path)
    assert (f8.state, f8.reason, f8.is_stale) == (FieldState.STALE, "stale", True)
    assert f8.value_yi == 5399.15741 and f8.age_days == 8 and f8.stale_reason    # STALE 仍帶值與原因


def test_attrs_missing_is_stale_is_freshness_undetermined(monkeypatch, tmp_path):
    _write(tmp_path, _rows_ending(dt.date(2026, 11, 9)))

    monkeypatch.setattr(R, "_attach_staleness", lambda series, *a, **k: series)   # 等價於 L1 吞例外回「無 attrs」
    f = S.get_margin_fact(today=_TODAY, cache_dir=tmp_path)
    assert (f.state, f.reason, f.is_stale) == (FieldState.STALE, "freshness_undetermined", None)
    assert f.value_yi == 5399.15741 and f.age_days is None


def test_l1_swallowed_staleness_exception_real_path(monkeypatch, tmp_path):
    _write(tmp_path, _rows_ending(dt.date(2026, 11, 9)))

    def _boom(*a, **k):
        raise RuntimeError("compute broke")
    monkeypatch.setattr(R, "compute_cache_staleness", _boom)       # _attach_staleness 吞例外 → 無 attrs
    f = S.get_margin_fact(today=_TODAY, cache_dir=tmp_path)
    assert f.reason == "freshness_undetermined" and f.state is FieldState.STALE and f.is_stale is None


@pytest.mark.parametrize("raw", ("False", 0, 1, None))
def test_non_bool_is_stale_is_undetermined(monkeypatch, tmp_path, raw):
    _patch_series(monkeypatch, _series([5000.0, 5399.0], attrs={"is_stale": raw, "as_of": dt.date(2026, 11, 9)}))
    f = S.get_margin_fact(today=_TODAY, cache_dir=tmp_path)
    assert f.reason == "freshness_undetermined" and f.is_stale is None


def test_numpy_bool_is_stale_respected(monkeypatch, tmp_path):
    _patch_series(monkeypatch, _series([5000.0, 5399.0], attrs={"is_stale": np.bool_(True), "as_of": dt.date(2026, 11, 9)}))
    assert S.get_margin_fact(today=_TODAY, cache_dir=tmp_path).reason == "stale"


@pytest.mark.parametrize("age", (-3, -1, float("nan"), True, "2", None))
def test_age_days_negative_or_bad_is_none(monkeypatch, tmp_path, age):
    _patch_series(monkeypatch, _series([5000.0, 5399.0], attrs={"is_stale": False, "as_of": dt.date(2026, 11, 9), "age_days": age}))
    assert S.get_margin_fact(today=_TODAY, cache_dir=tmp_path).age_days is None


def test_upstream_state_is_relayed_and_independent(monkeypatch, tmp_path):
    _patch_series(monkeypatch, _series([5000.0, 5399.0], attrs={
        "is_stale": False, "as_of": dt.date(2026, 11, 9), "age_days": 2, "upstream_state": "FETCH_FAILED"}))
    f = S.get_margin_fact(today=_TODAY, cache_dir=tmp_path)
    assert f.upstream_state == "FETCH_FAILED" and f.state is FieldState.OK     # 不蘊含資料不新鮮


# ═════════════ 資料型別不變量 ═════════════
def test_value_only_in_ok_or_stale():
    for st in FieldState:
        if st in (FieldState.OK, FieldState.STALE):
            continue
        with pytest.raises(ValueError):
            S.MarginFact(state=st, value_yi=5000.0)
        assert S.MarginFact(state=st).value_yi is None
    with pytest.raises(ValueError):
        S.MarginFact(state=FieldState.OK)            # 有值態必須有值（不允許空殼 OK）


def test_fact_is_frozen():
    f = S.MarginFact(state=FieldState.OK, value_yi=5000.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.value_yi = 1.0   # type: ignore[misc]


def test_every_non_value_scenario_has_none_value(monkeypatch, tmp_path):
    outs = []
    outs.append(S.get_margin_fact(today=_TODAY, cache_dir=tmp_path))                              # 缺檔
    for v in (np.nan, np.inf, 499.0, 10000.0):
        _patch_series(monkeypatch, _series([5000.0, v]))
        outs.append(S.get_margin_fact(today=_TODAY, cache_dir=tmp_path))
    for f in outs:
        assert f.state not in (FieldState.OK, FieldState.STALE) and f.value_yi is None and f.as_of is None


def test_reason_state_mapping_exhaustive():
    reasons = {v for k, v in vars(S).items() if k.startswith("REASON_") and isinstance(v, str)}
    assert reasons == set(S._REASON_STATE), "每個 REASON_* 都必須在 _REASON_STATE 有對照，反之亦然"
    assert len(reasons) == 9
    assert S._REASON_STATE[S.REASON_READ_EXCEPTION] is FieldState.UNAVAILABLE
    assert S._REASON_STATE[S.REASON_OK] is FieldState.OK
    for r in (S.REASON_FRESHNESS_UNDETERMINED, S.REASON_STALE):
        assert S._REASON_STATE[r] is FieldState.STALE
    for r in (S.REASON_SOURCE_ABSENT, S.REASON_VALUE_NOT_FINITE, S.REASON_UNIT_SANITY_FAILED,
              S.REASON_AS_OF_MISMATCH, S.REASON_FUTURE_AS_OF):
        assert S._REASON_STATE[r] is FieldState.MISSING
    # state 賦值只經由對照表：原始碼不得出現「直接寫 FieldState.XXX 當 state= 引數」
    assert not re.search(r"state=FieldState\.", _SRC)


# ═════════════ 禁字／import／網路／範圍守衛 ═════════════
def _docstring_nodes(tree):
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            b = n.body
            if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant) \
                    and isinstance(b[0].value.value, str):
                out.add(id(b[0].value))
    return out


_JUDGEMENT_WORDS = ("過熱", "偏高", "偏低", "警示", "警戒", "風險", "建議", "看多", "看空", "樂觀", "悲觀",
                    "危險", "安全", "健康", "異常", "資料疑義", "紅燈", "黃燈", "綠燈")


def test_no_threshold_or_judgement_in_source():
    for needle in ("3400", "2500", "OVERHEAT", "overheat", "THRESHOLD"):
        assert needle not in _SRC, f"新檔不得出現 {needle}"
    tree = ast.parse(_SRC)
    skip = _docstring_nodes(tree)
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip:
            for w in _JUDGEMENT_WORDS:
                assert w not in n.value, f"非 docstring 字串含判讀詞 {w!r}：{n.value!r}"
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            assert n.value not in (3400, 2500, 3400.0, 2500.0)
    # 數值常數只准 sanity 以外的 0/1/2 這類結構性數字；不得內嵌 500／10000（必走 SSOT）
    nums = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)}
    assert not ({500, 500.0, 10000, 10000.0} & nums)


def test_source_has_only_fixed_user_visible_strings():
    # 非 docstring 的中文字串只准：來源描述常數、單位字樣；其餘（detail 診斷）不得是名詞片語的使用者文案——
    # 以「模組層級常數字串」白名單核對。
    assert S.MARGIN_UNIT == "億元"
    tree = ast.parse(_SRC)
    module_str_consts = {t.id: n.value.value for n in tree.body if isinstance(n, ast.Assign)
                         for t in n.targets if isinstance(t, ast.Name)
                         and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)}
    cn = {k for k, v in module_str_consts.items() if re.search(r"[一-鿿]", v)}
    assert cn <= {"MARGIN_SOURCE_TEXT", "MARGIN_UNIT"}, cn


_BANNED_IMPORT_PREFIXES = ("streamlit", "src.ui", "src.ui2", "src.ui_v2", "src.services.ui2", "app", "app_ui2",
                           "requests", "urllib", "socket", "http")


def _imports(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                yield a.name
        elif isinstance(n, ast.ImportFrom) and n.module:
            yield n.module


def test_no_streamlit_or_ui_or_network_imports_ast():
    mods = set(_imports(ast.parse(_SRC)))
    for m in mods:
        for p in _BANNED_IMPORT_PREFIXES:
            assert not (m == p or m.startswith(p + ".")), f"禁止 import {m}"
    # L3 只准 shared／L1 canonical reader／標準庫
    assert "src.data.macro.macro_cache_reader" in mods
    assert not any(m.startswith("src.data") and m != "src.data.macro.macro_cache_reader" for m in mods)


def test_no_new_reader_cache_or_fetcher_artifacts():
    assert "st.cache" not in _SRC and "lru_cache" not in _SRC and "read_parquet" not in _SRC
    assert "requests" not in _SRC and "fetch_" not in _SRC.replace("fetched_at", "")


def test_no_network_during_call(tmp_path, monkeypatch):
    import socket
    import urllib.request

    import requests

    def _deny(*a, **k):
        raise AssertionError("網路呼叫被禁止")
    monkeypatch.setattr(socket.socket, "connect", _deny)
    monkeypatch.setattr(requests.Session, "request", _deny)
    monkeypatch.setattr(urllib.request, "urlopen", _deny)
    f = _fact(tmp_path, _rows_ending(dt.date(2026, 11, 9)))
    assert f.state is FieldState.OK
    assert S.get_margin_fact(today=_TODAY, cache_dir=tmp_path / "nope").reason == "source_absent_or_unreadable"


def _referrers() -> list[str]:
    needle = "margin_fact_service"
    paths = []
    for pat in ("src/ui/**/*.py", "src/ui2/**/*.py", "src/ui_v2/**/*.py", "src/services/ui2/**/*.py", "app*.py"):
        paths.extend(_REPO.glob(pat))
    return sorted(str(p.relative_to(_REPO)) for p in set(paths)
                  if p.is_file() and needle in p.read_text(encoding="utf-8", errors="ignore"))


def test_scope_guard_not_wired_to_ui_or_real_feed():
    """範圍守衛：本批只交 L3 事實層，**不接** UI／real_feed／VM。
    ⚠️ 下一步（客戶授權接線）時，本守衛必須同步改寫為「只准指定 feed 引用」，不是直接刪除。"""
    assert _referrers() == []
    assert (_REPO / "src/services/ui2/real_feed.py").is_file()
    feed = (_REPO / "src/services/ui2/real_feed.py").read_text(encoding="utf-8")
    assert "margin_fact_service" not in feed
    guards = (_REPO / "tests/test_ui2_guards.py").read_text(encoding="utf-8")
    assert "margin_fact_service" not in guards          # 未偷偷放進 G2F 白名單


def test_scope_guard_has_teeth(tmp_path):
    # 守衛本身要抓得到：對同一個掃描邏輯餵含引用的檔，必須命中
    p = tmp_path / "x.py"
    p.write_text("from src.services.margin_fact_service import get_margin_fact\n", encoding="utf-8")
    assert "margin_fact_service" in p.read_text(encoding="utf-8")


# ═════════════ 真實 data_cache（一次）═════════════
_REAL = _REPO / "data_cache" / "finmind_margin.parquet"


@pytest.mark.skipif(not _REAL.exists(), reason="data_cache/finmind_margin.parquet 不存在（未 checkout 快取）")
def test_real_cache_pinned_snapshot():
    df = pd.read_parquet(_REAL)
    last = pd.to_datetime(df["date"]).max().date()
    if last != dt.date(2026, 11, 9):
        pytest.skip(f"快取已更新到 {last}（釘住快照為 2026-11-09 / 5399.157 億）；改由下一個 cross-check 覆蓋")
    f = S.get_margin_fact(today=dt.date(2026, 11, 11))      # 預設 cache_dir = repo root 絕對路徑
    assert f.state is FieldState.OK and f.as_of == "2026-11-09"
    assert math.isclose(f.value_yi, 5399.15741, rel_tol=1e-9) and f.is_stale is False


@pytest.mark.skipif(not _REAL.exists(), reason="data_cache/finmind_margin.parquet 不存在（未 checkout 快取）")
def test_real_cache_crosscheck_with_independent_computation():
    df = pd.read_parquet(_REAL).dropna(subset=["margin_balance"])
    df["date"] = pd.to_datetime(df["date"])
    row = df.sort_values("date").iloc[-1]
    f = S.get_margin_fact(today=row["date"].date())
    assert f.state is FieldState.OK, (f.reason, f.detail)
    assert f.as_of == row["date"].date().isoformat()
    assert math.isclose(f.value_yi, float(row["margin_balance"]) / 1e8, rel_tol=1e-12)
