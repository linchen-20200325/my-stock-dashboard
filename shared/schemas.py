"""shared/schemas.py — Pandera 資料 schema SSOT(v18.306 Phase A pilot)

CLAUDE.md §3.1 — DataFrame 邊界契約集中宣告。對齊 Fund v19.155 pattern。

設計
----
- L0 / 純常數,零 I/O
- 各 fetcher 出口呼叫 `validate_*(df)` 強制契約
- schema 改動 = 本檔唯一 commit point;**禁止** caller 端重新宣告
- pandera 不在環境時(極罕見:requirements.txt 已 pin >=0.20),caller 應降級
  為 best-effort try/except,不阻斷流程(§1 Fail Loud 對齊:契約違反 raise,
  但 schema 模組本身不可用視為環境問題)

對外 API
========
- `MacroFredSchema`:macro_core.fetch_fred 出口 schema
- `validate_fred(df) -> df`:wrapper(避免每個 caller import pandera 細節)

Phase 規劃(對齊 Fund SPEC §18.3 採用節奏):
- ✅ Phase A v18.306 — pilot:macro_core.fetch_fred 1 個 fetcher
- 未來 Phase B+ — 視需求擴展(fetch_yf_close attrs / OHLCV 等),不機械式推展
"""
from __future__ import annotations

from typing import Any

import pandera.pandas as pa


# ════════════════════════════════════════════════════════════════
# MacroFredSchema — fetch_fred 出口契約
# ════════════════════════════════════════════════════════════════
# 依據(CLAUDE.md §3.1 + macro_core.py:258-324 實際輸出):
#   date          datetime64[ns]  ascending 排序,unique;to_datetime 強制
#   value         float64         dropna 後保證無 NaN;> 0 不強制(macro 可負,e.g. yield spread)
#   source        str             v18.246 S-PROV-1 起必含,格式 "FRED:<series_id>"
#   fetched_at    str             ISO 8601 UTC 字串(含 'T' 分隔符)
#
# 容差:
# - strict=False — 允許 unknown 額外欄位(若未來補 realtime_start 等不檢)
# - coerce=False — 不強制型別轉換(fetch_fred 內部已 pd.to_datetime / to_numeric+astype,
#                   此處 schema 只做 final assert,違反 = 上游 bug)

MacroFredSchema = pa.DataFrameSchema(
    {
        "date": pa.Column(
            "datetime64[ns]",
            nullable=False,
            checks=[
                pa.Check(
                    lambda s: s.is_monotonic_increasing,
                    error="date 必須單調遞增(asc)",
                ),
                pa.Check(
                    lambda s: s.is_unique,
                    error="date 不可重複",
                ),
            ],
        ),
        "value": pa.Column(
            "float64",
            nullable=False,
            checks=[
                pa.Check(lambda s: s.notna().all(), error="value 不可有 NaN(fetch_fred 已 dropna)"),
            ],
        ),
        "source": pa.Column(
            str,
            nullable=False,
            checks=[
                pa.Check(
                    lambda s: s.str.startswith("FRED:").all(),
                    error="source 必須以 'FRED:' 開頭(SSOT provenance 慣例 v18.246)",
                ),
            ],
        ),
        "fetched_at": pa.Column(
            str,
            nullable=False,
            checks=[
                pa.Check(
                    lambda s: s.str.contains("T", regex=False).all(),
                    error="fetched_at 必須是 ISO 8601 字串(含 'T' 分隔符)",
                ),
            ],
        ),
    },
    strict=False,
    coerce=False,
)


def validate_fred(df: Any) -> Any:
    """fetch_fred 出口 schema validation wrapper。

    對空 DataFrame(fetch 失敗時)直接 pass — §1 Fail Loud:caller 已知是
    fail token,schema 不重複擋。

    Returns
    -------
    驗證通過的 DataFrame(本檔 strict=False,不 augment 額外欄位)。

    Raises
    ------
    pandera.errors.SchemaError:契約違反(date 重複 / value NaN / source 缺前綴等)。
    """
    if df is None or len(df) == 0:
        return df
    return MacroFredSchema.validate(df, lazy=False)
