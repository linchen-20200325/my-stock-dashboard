"""shared/schemas.py Phase A pilot — unit tests(v18.306 S-PANDERA-1)。

對應 Fund v19.155 test pattern。守 MacroFredSchema + validate_fred 契約。
"""
from __future__ import annotations

import pandas as pd
import pytest

# pandera 不在時整批 skip(本 test 專測 schema 邊界)
pytest.importorskip("pandera")

from shared.schemas import MacroFredSchema, validate_fred  # noqa: E402


# ════════════════════════════════════════════════════════════════
# Happy path
# ════════════════════════════════════════════════════════════════
def _make_good_df():
    return pd.DataFrame({
        "date": pd.to_datetime(["2025-01-01", "2025-02-01", "2025-03-01"]),
        "value": [1.5, 2.5, 3.5],
        "source": ["FRED:DGS10"] * 3,
        "fetched_at": ["2026-06-26T00:00:00+00:00"] * 3,
    })


def test_validate_fred_happy_path():
    df = _make_good_df()
    out = validate_fred(df)
    # pandera 0.20+ 可能回 new view 或同 obj;只要驗證內容等值即可
    pd.testing.assert_frame_equal(out, df)


def test_validate_fred_empty_passes():
    """fetch_fred 失敗時回空 DataFrame,schema 不擋。"""
    empty = pd.DataFrame()
    out = validate_fred(empty)
    assert out is empty


def test_validate_fred_none_passes():
    assert validate_fred(None) is None


# ════════════════════════════════════════════════════════════════
# 整數序列(PAYEMS / HSN1F 等)— Fund v19.172 同類 regression
# ════════════════════════════════════════════════════════════════
def test_validate_fred_rejects_int64_value():
    """value 必須 float64;int64(PAYEMS 全整數)不通過。

    對應 macro_core.fetch_fred:317 `.astype("float64")` 強制轉型的測試。
    """
    df = _make_good_df()
    df["value"] = pd.Series([1, 2, 3], dtype="int64")
    import pandera.errors
    with pytest.raises(pandera.errors.SchemaError):
        MacroFredSchema.validate(df, lazy=False)


# ════════════════════════════════════════════════════════════════
# 契約違反
# ════════════════════════════════════════════════════════════════
def test_validate_fred_rejects_unsorted_date():
    df = _make_good_df()
    df["date"] = pd.to_datetime(["2025-03-01", "2025-01-01", "2025-02-01"])
    import pandera.errors
    with pytest.raises(pandera.errors.SchemaError):
        MacroFredSchema.validate(df, lazy=False)


def test_validate_fred_rejects_duplicate_date():
    df = _make_good_df()
    df["date"] = pd.to_datetime(["2025-01-01", "2025-01-01", "2025-02-01"])
    import pandera.errors
    with pytest.raises(pandera.errors.SchemaError):
        MacroFredSchema.validate(df, lazy=False)


def test_validate_fred_rejects_nan_value():
    df = _make_good_df()
    df["value"] = [1.5, float("nan"), 3.5]
    import pandera.errors
    with pytest.raises(pandera.errors.SchemaError):
        MacroFredSchema.validate(df, lazy=False)


def test_validate_fred_rejects_source_without_fred_prefix():
    df = _make_good_df()
    df["source"] = ["Yahoo:VIX"] * 3
    import pandera.errors
    with pytest.raises(pandera.errors.SchemaError):
        MacroFredSchema.validate(df, lazy=False)


def test_validate_fred_rejects_fetched_at_without_T():
    df = _make_good_df()
    df["fetched_at"] = ["2026-06-26 00:00:00"] * 3  # no 'T'
    import pandera.errors
    with pytest.raises(pandera.errors.SchemaError):
        MacroFredSchema.validate(df, lazy=False)


# ════════════════════════════════════════════════════════════════
# fetch_fred 串接(import-time best-effort)— 確保 wiring 不破生產線
# ════════════════════════════════════════════════════════════════
def test_macro_core_fetch_fred_wired_to_validate():
    """macro_core.fetch_fred 末尾的 try/except + validate_fred wiring 不該
    影響空 api_key 早返情境(回空 DataFrame),也不該影響無 obs 早返。"""
    from macro_core import fetch_fred
    # empty api_key → early return empty DataFrame, schema not invoked
    out = fetch_fred("DGS10", api_key="")
    assert isinstance(out, pd.DataFrame)
    assert out.empty
