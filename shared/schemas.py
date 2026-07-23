"""shared/schemas.py — Pandera 資料 schema SSOT(L0)。

CLAUDE.md §3.1 — DataFrame 邊界契約集中宣告,**全專案唯一 schema 家**。

歷史
----
- v18.306 Phase A pilot:MacroFredSchema(macro_core.fetch_fred 出口)。
- v19.159(團隊交叉稽核 架構師-Med)併入原 `src/compute/risk/schemas.py`(v18.397 POC):
  OHLCV / MonthlyRevenue / MacroDF / PMI / ForeignFlow schema + try_validate /
  validate_in_log_mode / validate_or_reject。原檔位於 L2(compute)卻被 8 處 L1
  fetcher 上行 import(違反 §8.2 L1 不得 import L2)+ 與本 L0 檔分裂成兩個 schema 家
  (違反本檔自稱 SSOT)。**併回 L0 一次解掉「SSOT 分裂 + L1→L2 上行」兩型違憲。**

設計
----
- L0 / 純契約,零 I/O(pandera 為唯一重依賴,已 pin 於 requirements.txt)。
- 各 fetcher 出口呼叫 `validate_*(df)` 強制或 log 契約。
- schema 改動 = 本檔唯一 commit point;**禁止** caller 端重新宣告。
- pandera 不在環境時(極簡測試環境)→ graceful degrade:PANDERA_AVAILABLE=False、
  schema instance = None、validate_* 直接放行回原 df(§1:schema 模組本身不可用
  視為環境問題,不阻斷業務流程;契約違反才 raise / reject)。

對外 API
========
- Schema instances(pandera 缺時為 None):
  MacroFredSchema / OHLCVSchema / MonthlyRevenueSchema / MacroDFSchema /
  PMISchema / ForeignFlowSchema
- validate_fred(df) -> df:MacroFredSchema 專用 raise wrapper
- try_validate(df, schema, *, lazy) -> (df, errors):非-raise(audit mode)
- validate_in_log_mode(df, schema, label, *, normalize_case) -> df:log-only 非阻斷
- validate_or_reject(df, schema, label, *, normalize_case) -> df:違反則整檔棄用回空殼
- PANDERA_AVAILABLE:bool
"""
from __future__ import annotations

from typing import Any

try:
    import pandera.pandas as pa  # pandera >=0.20 lazy path
    PANDERA_AVAILABLE = True
except ImportError:  # pragma: no cover
    try:
        import pandera as pa
        PANDERA_AVAILABLE = True
    except ImportError:
        pa = None
        PANDERA_AVAILABLE = False

import pandas as pd


# ════════════════════════════════════════════════════════════════
# MacroFredSchema — fetch_fred 出口契約(v18.306 Phase A)
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
def _make_macro_fred_schema():
    if not PANDERA_AVAILABLE:
        return None
    return pa.DataFrameSchema(
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


MacroFredSchema = _make_macro_fred_schema()


def validate_fred(df: Any) -> Any:
    """fetch_fred 出口 schema validation wrapper。

    對空 DataFrame(fetch 失敗時)或 pandera 不可用時直接 pass — §1 Fail Loud:
    caller 已知是 fail token / 環境問題,schema 不重複擋。

    Returns
    -------
    驗證通過的 DataFrame(本檔 strict=False,不 augment 額外欄位)。

    Raises
    ------
    pandera.errors.SchemaError:契約違反(date 重複 / value NaN / source 缺前綴等)。
    """
    if df is None or len(df) == 0:
        return df
    if not PANDERA_AVAILABLE or MacroFredSchema is None:
        return df
    return MacroFredSchema.validate(df, lazy=False)


# ════════════════════════════════════════════════════════════════
# 以下併自 src/compute/risk/schemas.py(v18.397 POC → v19.159 遷入 L0)
# §3.1 邊界契約落地 — 從 dict / assert 散落驗證轉為 pandera DataFrameSchema。
# schema validation 是 opt-in:fetcher 在出口主動呼叫 validate_in_log_mode /
# validate_or_reject;違反 → 依函式語意 stderr log 或整檔棄用(§1 fail loud)。
# ════════════════════════════════════════════════════════════════
def _make_ohlcv_schema():
    """OHLCV 股價 DataFrame 共通 schema。

    覆蓋:
    - OHLC 4 欄 non-null + >= 0
    - volume non-null + >= 0
    - 不變量:low ≤ min(open, close), high ≥ max(open, close), low ≤ high
    """
    if not PANDERA_AVAILABLE:
        return None

    def _ohlc_invariants(df):
        # low ≤ open / close ≤ high;low ≤ high;volume ≥ 0
        ok_low_open = (df['low'] <= df['open']).all()
        ok_low_close = (df['low'] <= df['close']).all()
        ok_high_open = (df['high'] >= df['open']).all()
        ok_high_close = (df['high'] >= df['close']).all()
        ok_low_high = (df['low'] <= df['high']).all()
        return ok_low_open and ok_low_close and ok_high_open and ok_high_close and ok_low_high

    return pa.DataFrameSchema(
        columns={
            'open':   pa.Column(float, checks=pa.Check.ge(0), nullable=False),
            'high':   pa.Column(float, checks=pa.Check.ge(0), nullable=False),
            'low':    pa.Column(float, checks=pa.Check.ge(0), nullable=False),
            'close':  pa.Column(float, checks=pa.Check.ge(0), nullable=False),
            'volume': pa.Column('int64', checks=pa.Check.ge(0), nullable=False),
        },
        checks=[
            pa.Check(_ohlc_invariants, error='OHLC invariants violated'),
        ],
        strict=False,  # 允許 extra columns(provenance 欄位等)
    )


def _make_monthly_revenue_schema():
    """月營收 DataFrame schema(§3.1 範例)。

    覆蓋:
    - `date` datetime / **單股升序 unique**(全市場 batch 因多 stock_id 同月份 → 不檢 unique)
    - `revenue` > 0(月營收為正,§4.6「停業時應為 NaN 而非 0」;單位 TWD,FinMind native column)

    v18.433 對齊現實:原 `revenue_twd` 命名 + `date.is_unique` 屬未來 SSOT 設計,
    但 production fetcher(monthly_revenue_fetcher.py)實際輸出 `revenue` 欄 +
    batch fetcher 有多 stock_id 同月份重複日期 → schema 鬆綁兩處,避免 false-positive
    schema_drift log。Strict 設計仍可在新 fetcher 採用。
    """
    if not PANDERA_AVAILABLE:
        return None
    return pa.DataFrameSchema(
        columns={
            'date': pa.Column(
                'datetime64[ns]',
                checks=[
                    pa.Check(lambda s: s.is_monotonic_increasing,
                             error='date 必須升序排列'),
                    # 注意:不檢 is_unique(batch fetcher 多 stock_id 共用月份)
                ],
                nullable=False,
            ),
            # revenue 為正,允許 NaN(停業 / 等公布狀態);FinMind native column 'revenue'
            'revenue': pa.Column(
                float,
                checks=pa.Check(
                    lambda s: ((s > 0) | s.isna()).all(),
                    error='revenue 必須為正或 NaN(§4.6 月營收三態)',
                ),
                nullable=True,
            ),
        },
        strict=False,
    )


def _make_macro_df_schema():
    """macro 通用 DataFrame schema(date + value + source + as_of)。

    對齊 §3.1 範例:
    - `date` datetime / ascending
    - `value` float
    - `source` str(§2.2 provenance)
    - `as_of` date(§2.3 PIT)
    """
    if not PANDERA_AVAILABLE:
        return None
    return pa.DataFrameSchema(
        columns={
            'date':   pa.Column('datetime64[ns]', nullable=False),
            'value':  pa.Column(float, nullable=True),
            'source': pa.Column(str, nullable=True, required=False),
            'as_of':  pa.Column(nullable=True, required=False),  # 任意 date 型
        },
        strict=False,
    )


def _make_pmi_schema():
    """PMI(採購經理指數)DataFrame schema(P2 v18.434)。

    對齊 §3.2 範圍表 + §4.2 不變量:
    - `date` datetime / ascending(月度,normalized 月底)
    - `value` float in [30, 70](PMI 合理範圍,shared/signal_thresholds.PMI_VALID_MIN/MAX)
    - `source` str(§2.2 provenance)

    當期 TW PMI 由 `macro_core.fetch_tw_pmi`(8 源賽跑,v19.113)供應;PMISchema 保留供
    未來 PMI 歷史序列驗證用(原唯一 caller fetch_pmi_history 為死碼,v19.86 已刪)。
    """
    if not PANDERA_AVAILABLE:
        return None
    from shared.signal_thresholds import PMI_VALID_MIN, PMI_VALID_MAX
    return pa.DataFrameSchema(
        columns={
            'date':   pa.Column(
                'datetime64[ns]',
                checks=pa.Check(lambda s: s.is_monotonic_increasing,
                                error='PMI date 必須升序'),
                nullable=False,
            ),
            'value':  pa.Column(
                float,
                checks=pa.Check.in_range(PMI_VALID_MIN, PMI_VALID_MAX,
                                          include_min=True, include_max=True,
                                          error=f'PMI value 須 ∈ [{PMI_VALID_MIN}, {PMI_VALID_MAX}](§3.2)'),
                nullable=False,
            ),
            'source': pa.Column(str, nullable=True, required=False),
        },
        strict=False,
    )


def _make_foreign_flow_schema():
    """外資資金流量 DataFrame schema(P2 v18.434)。

    對齊 §3.1 範例:
    - `date` datetime / ascending(交易日)
    - `foreign_net_yi` float(億 TWD,可正可負;§4.6 三大法人單日買賣超合理性)
      範圍寬鬆 [-9999, 9999] 億 — 防 unit confusion(若爆界很可能單位寫錯)

    fetcher:foreign_flow_fetcher.fetch_foreign_flow_series
    """
    if not PANDERA_AVAILABLE:
        return None
    return pa.DataFrameSchema(
        columns={
            'date':   pa.Column(
                'datetime64[ns]',
                checks=pa.Check(lambda s: s.is_monotonic_increasing,
                                error='foreign flow date 須升序'),
                nullable=False,
            ),
            # 億 TWD,sanity check 防單位混淆(元 vs 億 = 1e8 倍誤差)
            'foreign_net_yi': pa.Column(
                float,
                checks=pa.Check.in_range(-9999, 9999,
                                          include_min=True, include_max=True,
                                          error='foreign_net_yi 須在 ±9999 億內(§4.1 單位)'),
                nullable=True,
            ),
        },
        strict=False,
    )


# 模組 level instances(pandera 缺時為 None)
OHLCVSchema = _make_ohlcv_schema()
MonthlyRevenueSchema = _make_monthly_revenue_schema()
MacroDFSchema = _make_macro_df_schema()
PMISchema = _make_pmi_schema()
ForeignFlowSchema = _make_foreign_flow_schema()


def try_validate(df: pd.DataFrame, schema, *, lazy: bool = True) -> tuple:
    """非-raise 的 validation wrapper(audit mode)。

    Args:
        df: 待驗 DataFrame
        schema: pandera DataFrameSchema instance(本檔 schema 之一)
        lazy: True → pandera lazy=True(收集所有 error 後 raise);False → 遇第一個 raise

    Returns:
        (validated_df, errors):
        - schema 通過 → (df, [])
        - schema 失敗 → (df 原樣, error message list)
        - pandera 不可用 → (df, ['pandera not installed'])
    """
    if not PANDERA_AVAILABLE or schema is None:
        return df, ['pandera not installed or schema unavailable']
    try:
        validated = schema.validate(df, lazy=lazy)
        return validated, []
    except Exception as e:  # pandera.errors.SchemaError or SchemaErrors
        return df, [str(e)]


def validate_in_log_mode(df: pd.DataFrame, schema, label: str = '',
                          *, normalize_case: bool = False) -> pd.DataFrame:
    """log-only validation(POC rollout 模式,v18.404 #3 + v18.406 R9 case-handling)。

    對齊 user 未完成項目 #3:讓 production fetcher 開始累積 schema 漂移信號,
    但**不擋 caller**(回傳原 df,只 stderr 出錯)。

    v18.406 R9 enhancement:`normalize_case=True` 時把 column name 小寫化後再驗
    (yfinance 用 Open/High/Low/Close/Volume 大寫,vs OHLCVSchema 小寫)。
    原 df 不變(只 build copy 驗證)。

    用法(在 production fetcher 結尾):
        # yfinance OHLCV(大寫 column)→ normalize_case=True
        return validate_in_log_mode(df, OHLCVSchema,
                                     label='fetch_etf_price', normalize_case=True)
        # 自己 SSOT shape(小寫)→ normalize_case=False(預設)
        return validate_in_log_mode(df, MonthlyRevenueSchema, label='fetch_revenue')

    Args:
        df: 待驗 DataFrame
        schema: pandera schema(可為 None,代表 pandera 不可用)
        label: log 識別,通常 fetcher fn name + key params
        normalize_case: True → 驗證前 columns.str.lower()(不動原 df)

    Returns:
        df 原樣(不修改,絕不 raise)
    """
    import sys
    if df is None or (hasattr(df, 'empty') and df.empty):
        return df
    _df_to_validate = df
    if normalize_case and hasattr(df, 'columns'):
        # build a copy with lowered column names(不改原 df)
        _df_to_validate = df.rename(columns={c: str(c).lower() for c in df.columns})
    validated, errors = try_validate(_df_to_validate, schema)
    if errors and 'pandera not installed' not in errors[0]:
        msg = f'[pandera-schema/{label}] WARN: {errors[0][:200]}'
        print(msg, file=sys.stderr)
    return df  # 絕對回原 df,non-blocking


def validate_or_reject(df: pd.DataFrame, schema, label: str = '',
                       *, normalize_case: bool = False) -> pd.DataFrame:
    """blocking validation(D13 v19.75,user 核准 review D 類):
    schema 違反 → **整檔棄用回空 DataFrame** + stderr log。

    與 validate_in_log_mode 的分工:
    - log-mode:POC 累積漂移信號,不擋 caller(壞 shape 仍流入計算)
    - 本函式:給「錯值比缺值危險」的資料流(§1 Fail Loud)— 驗證失敗回空殼,
      下游走既有「無資料」路徑(診斷 Tab 亮紅可見),絕不讓壞 shape 靜默進計算。
      刻意**整檔棄用**而非丟壞列:部分刪列會讓資料「看似完整」= §1 掩蓋問題。

    pandera 未安裝 → 視同 log-mode 放行(部署環境 requirements 已 pin,
    僅極簡測試環境會走到;放行 + 不 log 對齊 try_validate 既有語意)。
    絕不 raise。
    """
    import sys
    if df is None or (hasattr(df, 'empty') and df.empty):
        return df
    _df_to_validate = df
    if normalize_case and hasattr(df, 'columns'):
        _df_to_validate = df.rename(columns={c: str(c).lower() for c in df.columns})
    validated, errors = try_validate(_df_to_validate, schema)
    if errors and 'pandera not installed' not in errors[0]:
        print(f'[pandera-schema/{label}] REJECT(整檔棄用,§1 錯值比缺值危險): '
              f'{errors[0][:200]}', file=sys.stderr)
        return df.iloc[0:0]  # 同欄位空殼,caller 的 df.empty 防線直接接手
    return df
