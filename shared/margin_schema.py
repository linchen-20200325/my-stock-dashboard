"""shared/margin_schema.py — 大盤融資餘額 FinMind 口徑判定 SSOT(L0)。

CLAUDE.md §2.1 SSOT / §4.1 量綱 / §1 Fail-Loud。

為什麼要有這一檔(B3 事故根因)
================================
FinMind `TaiwanStockTotalMarginPurchaseShortSale` 是**彙總版長格式**:
同一天回**多列**,靠 `name` 欄分口徑 —

    date         name                    TodayBalance      YesBalance
    2026-08-04   MarginPurchaseMoney     619,648,244,000   ...   ← 金額,單位「元」
    2026-08-04   MarginPurchaseVolume    9,614,955         ...   ← 張數,**不是金額**
    2026-08-04   ShortSale...            ...                     ← 融券,不是融資

`src/data/daily/daily_data_fetchers.py`(即時 6 路 fallback)v19.79 起已用
「name 過濾 Money 列 + 排除 Yes* 欄」的正確解法,並由
`tests/test_review_fixes_v19_74.py` 釘死;但 `scripts/update_macro_history.py`
(cron,寫 `data_cache/finmind_margin.parquet`)是照**個股版寬格式**寫的欄位偵測,
`raw[["date", bal_col]]` 把所有 name 列一起拿,再被 `_merge_dedupe` 的
`drop_duplicates(keep="last")` 壓成一列 → 留哪一列由 FinMind 回傳順序決定
→ 序列變成「張 / 元」雙峰混口徑(2006-07-17~2026-08-04 共 4,929 列,
約 40% 元、36% 張、25% 不明)。

**同一條規則寫在兩個地方 = 遲早分岔**(§2.1)。本檔把「哪一列 / 哪一欄 / 什麼單位」
的判定抽成 L0 純函式,L1 fetcher 與 cron script 共吃同一份;
`tests/test_b3_margin_schema.py` 以 AST 釘住兩邊確實引用本檔。

為什麼放 L0 `shared/` 而不是 L2 `compute/`
==========================================
consumer 之一是 L1(`daily_data_fetchers`),L1 不得 import L2(§8.2 跨層上行)。
L0 是唯一兩邊都能合法 import 的層。先例:`shared/schemas.py`(pandera DataFrame
契約)同樣是「帶 pandas 的 L0 契約模組」。本檔零 I/O、零 streamlit、純函式。

單位鐵則(§4.1)
===============
- `MarginPurchaseMoney` 的 TodayBalance 單位 = **元**(TWD),÷1e8 = 億。
  考證:2026-08 線上真值 619,648,244,000 元 = 6,196 億 ∈ sanity[500,10000]億。
- `MarginPurchaseVolume` 單位 = **張**,量級 ~1e7 — **永遠不可**當金額換算。
- `data_cache/finmind_margin.parquet` 的 `margin_balance` 欄契約 = **元**
  (原下游 `macro_signal_lookback_tw.py` 以 /1e8 轉億,該檔已於 v19.181 detox 移除)。
"""
from __future__ import annotations

import pandas as pd

from shared.signal_thresholds import (  # §3.2 融資餘額合理區間 SSOT(v19.74)
    MARGIN_BALANCE_SANITY_MAX_YI,
    MARGIN_BALANCE_SANITY_MIN_YI,
)

# ════════════════════════════════════════════════════════════════
# 口徑常數(SSOT)
# ════════════════════════════════════════════════════════════════
MARGIN_DATASET = "TaiwanStockTotalMarginPurchaseShortSale"
"""FinMind 彙總版融資融券 dataset 名(全市場,非個股)。"""

MARGIN_MONEY_ROW_NAME = "MarginPurchaseMoney"
"""唯一可採信的「金額」列 name(單位:元)。"""

MARGIN_VOLUME_ROW_NAME = "MarginPurchaseVolume"
"""同組的「張數」列 name(單位:張)—— **明確拒收**,只列在此供測試/log 對照。"""

MARGIN_MONEY_NAME_ZH = "融資金額"
"""中文欄名變體(FinMind 曾出現中文 name;保留相容)。"""

MARGIN_BALANCE_COL_TOKENS = ("alance", "餘額", "amount", "Amount")
"""「餘額欄」token(大小寫敏感;'alance' 同時涵蓋 Balance / balance)。"""

MARGIN_YESTERDAY_COL_PREFIX = "yes"
# v19.181:長格式的裸欄名是 `YesterdayBalance`(prefix 命中),但寬格式是
# `MarginPurchaseYesterdayBalance`(prefix 不命中)。多一條 substring 判定,
# 讓 `is_today_balance_col` 的契約對兩種格式都成立(§2.3 PIT,詳見該函式 docstring)。
MARGIN_YESTERDAY_COL_TOKEN = "yesterday"
"""昨日餘額欄前綴(小寫比對)—— 涵蓋 `YesBalance` / `YesterdayBalance`。
採用昨日欄會讓整條序列**日期錯位一天**(§2.3 PIT lookahead 反向違規),必須排除。"""

MARGIN_WIDE_TODAY_BALANCE_COLS = (
    "TotalMarginPurchaseTodayBalance",
    "MarginPurchaseTodayBalance",
)
"""寬格式(個股版 / 舊彙總版)的當日餘額欄,**依偏好順序**。
不提供「任何含 Balance 的欄」這種寬鬆 fallback —— 那正是 B3 事故的原始寫法。"""

TWD_PER_YI = 1e8
"""元 → 億 換算常數(§4.1;1 億 = 1e8 元)。"""

MARGIN_SOURCE_PREFIX = f"FinMind:{MARGIN_DATASET}"
"""provenance 前綴;完整字串再串 `:<name 列>:<欄名>` 到**列級**(§2.2)。
事故根因之二:原本 source 只記到 dataset 就停,事後分辨不出 Money vs Volume。"""


# ════════════════════════════════════════════════════════════════
# 純判定函式(L1 fetcher 與 cron script 共用)
# ════════════════════════════════════════════════════════════════
def is_margin_money_row(name) -> bool:
    """這一列的 `name` 是不是「融資**金額**」?(唯一可採信的口徑)

    規則(與 `daily_data_fetchers.fetch_margin_balance` v19.79 逐字一致):
    正規化去底線後同時含 'marginpurchase' + 'money',或中文 '融資金額'。
    → `MarginPurchaseVolume`(缺 money)、`ShortSaleMoney`(缺 marginpurchase)皆不匹配。
    """
    n = str(name)
    nl = n.lower()
    return (
        ("marginpurchase" in nl.replace("_", "") and "money" in nl)
        or MARGIN_MONEY_NAME_ZH in n
    )


def is_balance_col(col) -> bool:
    """欄名看起來是不是「餘額」欄(不分今昨)。"""
    c = str(col)
    return any(tok in c for tok in MARGIN_BALANCE_COL_TOKENS)


def is_today_balance_col(col) -> bool:
    """是不是「**當日**餘額」欄 —— 餘額欄且不是昨日餘額。

    ⚠️ v19.181:原本只檢查 `startswith('yes')`,對長格式的裸欄名 `YesterdayBalance`
    有效,但對**寬格式**(個股版)的 `MarginPurchaseYesterdayBalance` 會誤判成當日欄
    (它以 `marginpurchase` 開頭)。目前不會出事 —— 寬格式走
    `MARGIN_WIDE_TODAY_BALANCE_COLS` 白名單(`_extract_wide` 只認明列欄名),
    本函式只用在長格式。但**函式名承諾的是「當日餘額欄」,契約大於現有 caller**:
    哪天有人拿它去掃寬格式欄位,抓到昨日餘額 = 整條序列日期錯位一天(§2.3 PIT),
    而那種錯不會炸、只會靜默偏移。故補強成「開頭是 Yes* **或**任何位置含
    yesterday」一律排除。長格式行為不變(`TodayBalance` 仍 True)。
    """
    c = str(col)
    if not is_balance_col(c):
        return False
    c_l = c.lower()
    return not (c_l.startswith(MARGIN_YESTERDAY_COL_PREFIX)
                or MARGIN_YESTERDAY_COL_TOKEN in c_l)


def pick_today_balance_cols(cols) -> list[str]:
    """從欄位清單挑出所有「當日餘額」欄,保留原順序。"""
    return [str(c) for c in cols if is_today_balance_col(c)]


def margin_sanity_ok(v_yi: float) -> bool:
    """融資餘額合理區間檢查(單位:億,§3.2)。

    超出 (MARGIN_BALANCE_SANITY_MIN_YI, MARGIN_BALANCE_SANITY_MAX_YI) 開區間 →
    疑似單位/欄位誤判,呼叫端應棄用(§1 寧缺勿錯)。NaN → False。
    """
    return MARGIN_BALANCE_SANITY_MIN_YI < v_yi < MARGIN_BALANCE_SANITY_MAX_YI


def margin_money_to_yi(raw_twd) -> float | None:
    """`MarginPurchaseMoney` 原始值(元) → 億;不過 sanity 回 None(§1 不猜、不補)。"""
    try:
        v = float(raw_twd)
    except (TypeError, ValueError):
        return None
    if pd.isna(v) or v <= 0:
        return None
    yi = v / TWD_PER_YI
    return round(yi, 1) if margin_sanity_ok(yi) else None


def margin_row_source(row_name: str, col_name: str) -> str:
    """列級 provenance 字串(§2.2)。

    e.g. `FinMind:TaiwanStockTotalMarginPurchaseShortSale:MarginPurchaseMoney:TodayBalance`
    """
    return f"{MARGIN_SOURCE_PREFIX}:{row_name}:{col_name}"


def margin_twd_sanity_mask(values_twd) -> pd.Series:
    """逐列 sanity(輸入單位:元)→ bool Series(True=合理)。NaN / 非數值 → False。"""
    yi = pd.to_numeric(pd.Series(values_twd), errors="coerce") / TWD_PER_YI
    return yi.gt(MARGIN_BALANCE_SANITY_MIN_YI) & yi.lt(MARGIN_BALANCE_SANITY_MAX_YI)


def _to_numeric_twd(s: pd.Series) -> pd.Series:
    """字串千分位容錯 → float(元)。"""
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )


# ════════════════════════════════════════════════════════════════
# 序列抽取(長 / 寬格式共用入口)
# ════════════════════════════════════════════════════════════════
def extract_margin_money_series(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """FinMind 原始回應 → `[date, margin_balance(元), source]` 一日一列。

    支援兩種 shape:
    - **長格式**(有 `name` 欄,彙總版):只取 `is_margin_money_row` 的列 +
      `pick_today_balance_cols` 的欄。張數列 / 融券列 / 昨日欄一律不取。
    - **寬格式**(個股版 / 舊彙總版,無 `name` 欄):依
      `MARGIN_WIDE_TODAY_BALANCE_COLS` 偏好順序取欄。

    **不做** sanity 過濾 —— 政策留給呼叫端(cron raise / export 略過整表);
    本函式只負責「選對列與欄」。找不到 → 回空 DataFrame(§1 不猜、不亂挑欄)。

    Returns
    -------
    (df, meta)
        df   : columns=['date','margin_balance','source'];margin_balance 單位 = **元**
        meta : 診斷用 dict(§5 可觀測性),欄位見 `_meta_skeleton`
    """
    meta = _meta_skeleton()
    if raw is None or not isinstance(raw, pd.DataFrame) or raw.empty:
        meta["reason"] = "raw 為空"
        return _empty_out(), meta
    meta["n_raw"] = len(raw)
    meta["columns"] = [str(c) for c in raw.columns]
    if "date" not in raw.columns:
        meta["reason"] = f"缺 date 欄;欄位={meta['columns']}"
        return _empty_out(), meta

    if "name" in raw.columns:
        return _extract_long(raw, meta)
    return _extract_wide(raw, meta)


def _meta_skeleton() -> dict:
    return {
        "format": None,          # 'long' / 'wide' / None
        "n_raw": 0,              # 原始列數
        "columns": [],
        "n_money_rows": 0,       # name 過濾後列數(long)
        "balance_col": None,     # 實際採用的欄
        "name_values": [],       # 出現過的 name(long;供 log 佐證)
        "n_dropped_nonpositive": 0,   # 顯式剔除的 NaN / <=0 列數(§3.3 必 log)
        "n_dup_dates": 0,        # 同日重複列數(過濾後理應 0)
        "reason": None,          # 回空時的原因
    }


def _empty_out() -> pd.DataFrame:
    return pd.DataFrame(columns=["date", "margin_balance", "source"])


def _finalize(df: pd.DataFrame, meta: dict) -> tuple[pd.DataFrame, dict]:
    """共用收尾:剔除非正值(顯式 + 計數)、同日去重、依日期排序。"""
    n_before = len(df)
    df = df[df["margin_balance"].notna() & (df["margin_balance"] > 0)].copy()
    meta["n_dropped_nonpositive"] = n_before - len(df)
    if df.empty:
        meta["reason"] = meta["reason"] or "餘額欄無有效正值"
        return _empty_out(), meta
    dup = int(df["date"].duplicated().sum())
    meta["n_dup_dates"] = dup
    if dup:
        # 過濾後仍同日多列 = 上游 shape 又變了;保留第一列(API 順序)並讓 caller 看得到。
        df = df[~df["date"].duplicated()].copy()
    df = df.sort_values("date").reset_index(drop=True)
    return df[["date", "margin_balance", "source"]], meta


def _extract_long(raw: pd.DataFrame, meta: dict) -> tuple[pd.DataFrame, dict]:
    meta["format"] = "long"
    names = raw["name"].astype(str)
    meta["name_values"] = sorted(set(names.tolist()))[:12]
    mask = names.map(is_margin_money_row).astype(bool)   # 避免 object dtype 布林索引
    money = raw[mask]
    meta["n_money_rows"] = len(money)
    if money.empty:
        meta["reason"] = (
            f"name 欄無「融資金額」列(只認 {MARGIN_MONEY_ROW_NAME});"
            f"unique name={meta['name_values']}"
        )
        return _empty_out(), meta

    today_cols = pick_today_balance_cols(raw.columns)
    if not today_cols:
        meta["reason"] = (
            f"無「當日餘額」欄(已排除 {MARGIN_YESTERDAY_COL_PREFIX}*);"
            f"欄位={meta['columns']}"
        )
        return _empty_out(), meta

    for col in today_cols:
        vals = _to_numeric_twd(money[col])
        if vals.notna().any() and (vals > 0).any():
            meta["balance_col"] = col
            out = pd.DataFrame({
                "date": money["date"].values,
                "margin_balance": vals.values,
                "source": [margin_row_source(n, col) for n in money["name"].astype(str)],
            })
            return _finalize(out, meta)

    meta["reason"] = f"當日餘額欄 {today_cols} 全無有效正值"
    return _empty_out(), meta


def _extract_wide(raw: pd.DataFrame, meta: dict) -> tuple[pd.DataFrame, dict]:
    meta["format"] = "wide"
    col = next((c for c in MARGIN_WIDE_TODAY_BALANCE_COLS if c in raw.columns), None)
    if col is None:
        meta["reason"] = (
            f"寬格式找不到當日餘額欄(只認 {list(MARGIN_WIDE_TODAY_BALANCE_COLS)},"
            f"**不**接受任意含 Balance 的欄);欄位={meta['columns']}"
        )
        return _empty_out(), meta
    meta["balance_col"] = col
    vals = _to_numeric_twd(raw[col])
    out = pd.DataFrame({
        "date": raw["date"].values,
        "margin_balance": vals.values,
        "source": margin_row_source("wide", col),
    })
    return _finalize(out, meta)
