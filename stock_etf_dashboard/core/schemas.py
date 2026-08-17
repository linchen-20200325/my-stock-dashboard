"""L0 Infra — Pandera 出口驗證 (資料憲法 §3.1).

原則：資料「流出」抓取層前先過 schema。壞形狀 → §1 Fail Loud：
- `validate_or_reject`：阻斷式,違規回「同 schema 的空殼」讓下游走紅字缺料路徑,
  絕不把壞值放行（錯值比缺值更危險）。
- `validate_in_log_mode`：只記 log 不阻斷,給漸進導入用。

pandera 缺席時 graceful degrade（不阻斷、原樣回傳）。
"""
from __future__ import annotations

import sys

import pandas as pd

try:
    import pandera.pandas as pa
    from pandera.pandas import Check, Column, DataFrameSchema
    from pandera.errors import SchemaError, SchemaErrors
    PANDERA_AVAILABLE = True
except Exception:  # pragma: no cover - 純環境降級
    PANDERA_AVAILABLE = False
    pa = None
    SchemaError = SchemaErrors = Exception

    def _noop_schema(*_a, **_k):
        return None

    DataFrameSchema = Column = Check = _noop_schema  # type: ignore


# ── Schemas ─────────────────────────────────────────────────────────────
if PANDERA_AVAILABLE:
    _nonneg = Check.ge(0)

    OHLCVSchema = DataFrameSchema(
        {
            "date": Column("datetime64[ns]", nullable=False, coerce=True),
            "open": Column(float, _nonneg, nullable=False, coerce=True),
            "high": Column(float, _nonneg, nullable=False, coerce=True),
            "low": Column(float, _nonneg, nullable=False, coerce=True),
            "close": Column(float, _nonneg, nullable=False, coerce=True),
            "volume": Column(float, _nonneg, nullable=False, coerce=True),
        },
        checks=[
            # §4.2 OHLC 鐵則（element-wise：回傳 bool Series）
            Check(lambda df: df["low"] <= df["high"], error="low<=high"),
            Check(lambda df: df["low"] <= df["open"], error="low<=open"),
            Check(lambda df: df["low"] <= df["close"], error="low<=close"),
            Check(lambda df: df["high"] >= df["open"], error="high>=open"),
            Check(lambda df: df["high"] >= df["close"], error="high>=close"),
        ],
        strict=False,
        name="OHLCV",
    )

    ValuationSchema = DataFrameSchema(
        {
            "date": Column("datetime64[ns]", nullable=False, coerce=True),
            # PE/PB 可為 NaN（EPS<=0 或無資料時,§1 不捏造）；有值須 > 0
            "pe": Column(float, Check.gt(0), nullable=True, coerce=True),
            "pb": Column(float, Check.gt(0), nullable=True, coerce=True),
        },
        strict=False,
        name="Valuation",
    )

    ChipSchema = DataFrameSchema(
        {
            "date": Column("datetime64[ns]", nullable=False, coerce=True),
            # 單位：張（可正可負）；缺日以 NaN,不 fillna(0)
            "foreign_net": Column(float, nullable=True, coerce=True),
            "trust_net": Column(float, nullable=True, coerce=True),
            "dealer_net": Column(float, nullable=True, coerce=True),
        },
        strict=False,
        name="Chip",
    )
else:  # pragma: no cover
    OHLCVSchema = ValuationSchema = ChipSchema = None


# ── 驗證入口 ────────────────────────────────────────────────────────────
def _empty_like(df: pd.DataFrame) -> pd.DataFrame:
    """回傳保留欄位與 attrs 的 0 列空殼。"""
    shell = df.iloc[0:0].copy()
    shell.attrs = dict(df.attrs)
    shell.attrs["rejected"] = True
    return shell


def validate_in_log_mode(df: pd.DataFrame, schema, *, name: str = "") -> pd.DataFrame:
    """只記 log,不阻斷。原樣回傳。"""
    if not PANDERA_AVAILABLE or schema is None or df is None or df.empty:
        return df
    try:
        schema.validate(df, lazy=True)
    except (SchemaError, SchemaErrors) as e:  # pragma: no cover - 診斷用
        print(f"[schema:log] {name or getattr(schema, 'name', '?')} 違規: {e}",
              file=sys.stderr)
    return df


def validate_or_reject(df: pd.DataFrame, schema, *, name: str = "") -> pd.DataFrame:
    """阻斷式。違規 → 回同 schema 空殼（§1：壞值不放行）。"""
    if not PANDERA_AVAILABLE or schema is None or df is None or df.empty:
        return df
    try:
        return schema.validate(df, lazy=True)
    except (SchemaError, SchemaErrors) as e:
        print(f"[schema:reject] {name or getattr(schema, 'name', '?')} "
              f"違規,回空殼: {e}", file=sys.stderr)
        return _empty_like(df)
