"""批 Z63 — freshness F3：PMI 快取與新鮮度分離 ＋ PMI_Prev 改為帶日期的真正前一資料月（⛔ 不接線）。

客戶裁示（2026-10-14）：
- Q-z34 Q1=B：「PMI 連兩月低於 48」必須用兩個不同的資料月；上一個月取既有 PMI history 裡的
  「前一資料月官方值」，取不到 → 該紅線判「無法判定」；⛔ 不得用本月值、session_state、
  上次按按鈕的值頂替（門檻 48、上限 40% 不改）。
- Q-z38=A：月資料 freshness 依「資料月份＋正常發布週期」；cache 存活時間 ≠ 資料 freshness。

本檔守：
1. L0 `PreviousMonthOfPolicy` ＋ `assess_previous_month`：前一資料月**跟著當期走**，不獨立套月頻規則
   （回歸：今天 10/14、當期 9 月 FRESH、前月 8 月 → FRESH；獨立判會是 STALE）。
   `assess()` 遇到這種規則 → raise（⛔ 不默默套月頻規則）。
2. L1 `macro_cache_reader.load_tw_pmi_history`：原樣讀 `data_cache/tw_pmi.parquet`。
3. L2 `dated_inputs.extract_pmi_prev`：在歷史中取 anchor 的恰好前一個資料月（跨年、找不到、
   重複不一致、非有限值都判缺；⛔ 不取最後一列）。
4. 快取 ≠ 新鮮度：來源接受窗 90 天 ≥ 月頻新鮮窗最大天數（實算）；stale-cache 依資料月判定，
   不受 `cached_at` 影響。

⛔ 不連網（PMI 8 源以 monkeypatch 換成全敗的假來源）。
"""
from __future__ import annotations

import pathlib as _pl

# ══════════════════════════════════════════════════════════════════════════
# 0. 還原 pair（先於任何專案 import 定義 —— 舊批次測試檔會回頭 import 本表）
# ══════════════════════════════════════════════════════════════════════════
#: 本批對 `macro_cache_reader.py` 的改動（修後逐字, 修前逐字）。舊批次 Z40 的「還原體＝基底檔」
#: 守衛（`test_batch_z40.z40_revert_for`）串接本表，先換回 Z63 之前的寫法再套它自己的還原
#: （同 Z62 ↔ Z35／Z36 慣例）。`macro_core.py` 本批只加註解，無舊批次 sha 守衛，故不列。
_MCR_REL = "src/data/macro/macro_cache_reader.py"
Z63_REVERT_PAIRS: dict = {
    _MCR_REL: (
        ((
         '- `load_tw_pmi_history(cache_dir) -> DataFrame | None`:讀 tw_pmi.parquet 原樣回傳(批 Z63,\n'
         '  供 L2 `dated_inputs.extract_pmi_prev` 取「前一資料月官方值」;未接線)\n'
        ), ""),
        ((
         '#: 台灣 PMI 月資料歷史 parquet 檔名(cron `scripts/update_macro_history.py` 寫入,dgtw 6100)。\n'
         '#: 實測 schema(2026-10-14):`date`(object,值為 `datetime.date`,每月 1 日)/ `pmi`(float64)/\n'
         '#: `source`(str)/ `fetched_at`(str,ISO UTC);2012-07 ~ 2026-09 共 171 列、無重複月。\n'
         '#: ⚠️ `services/macro_v2_service._TW_PMI_PARQUET_NAME` 是同一個檔名的既有私有副本(批 Z63 不接線,未動)。\n'
         'TW_PMI_PARQUET_NAME = "tw_pmi.parquet"\n'
         '#: `load_tw_pmi_history` 要求的欄位(缺任一 → 回 None)。\n'
         'TW_PMI_REQUIRED_COLS: frozenset = frozenset({"date", "pmi"})\n'
         '\n'
         '\n'
         'def load_tw_pmi_history(\n'
         '    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,\n'
         ') -> Optional[pd.DataFrame]:\n'
         '    """讀 `tw_pmi.parquet` → **原樣** DataFrame(批 Z63,freshness F3;⛔ 未接線)。\n'
         '\n'
         '    用途:L2 `src/compute/macro/dated_inputs.extract_pmi_prev` 從這份歷史取「前一資料月官方值」\n'
         '    (客戶 2026-10-14 Q-z34 Q1=B)。**不新增網路來源**,只讀 cron 已寫好的本地檔。\n'
         '\n'
         '    - 不轉型、不排序、不去重、不補值 —— 日期解析、重複月判定都交給 L2(那裡寫得出原因)。\n'
         '    - 缺檔 / 壞檔 / 空檔 / 缺 `date`、`pmi` 欄 → 印一行 log 並回 None(§1 出聲不吞)。\n'
         '    - ⛔ 不判新鮮度:這份檔的新舊不代表前月值有效與否,有效性由 L0\n'
         '      `shared.freshness_policy.assess_previous_month` 跟著當期判。\n'
         '    """\n'
         '    path = cache_dir / TW_PMI_PARQUET_NAME\n'
         '    df = load_parquet_safe(path, set(TW_PMI_REQUIRED_COLS))\n'
         '    if df is None:\n'
         '        print(f"[macro_cache_reader/load_tw_pmi_history] {TW_PMI_PARQUET_NAME} 讀不到、為空"\n'
         '              f"或缺欄(需要 {sorted(TW_PMI_REQUIRED_COLS)})→ 回 None")\n'
         '    return df\n'
         '\n'
         '\n'
        ), ""),
    ),
}
_ROOT_Z63 = _pl.Path(__file__).resolve().parents[1]


def z63_revert_for(file_path, code: str) -> str:
    """舊批次還原鏈串接用：給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批之前的寫法（無 pair 則原樣）。"""
    p = _pl.Path(file_path)
    rel = (p.resolve().relative_to(_ROOT_Z63) if p.is_absolute() else p).as_posix()
    for new, old in Z63_REVERT_PAIRS.get(rel, ()):
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    return code


import inspect
import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shared import freshness_policy as FP
from shared.dated_value import AssessedValue, DatedValue, coerce_month_start, coerce_plain_date
from shared.freshness_policy import (
    FRESHNESS_POLICY,
    FreshnessStatus,
    FreshnessVerdict,
    MonthlyPolicy,
    PreviousMonthOfPolicy,
    assess,
    assess_monthly,
    assess_previous_month,
)
from shared.station_specs import INVALID_DATA_TEXT
from src.compute.macro import dated_inputs as DI
from src.data.macro import macro_cache_reader as MCR

REPO = Path(__file__).resolve().parents[1]
FRESH, STALE, MISSING, UNDET = (FreshnessStatus.FRESH, FreshnessStatus.STALE,
                                 FreshnessStatus.MISSING, FreshnessStatus.UNDETERMINED)
T = date(2026, 10, 14)
PMI = "ISM_PMI_or_OECD_CLI"
PREV = "PMI_Prev_Month"


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _anchor(month: str | None, value=51.2, today: date = T) -> AssessedValue:
    dm = _d(month) if month else None
    return assess(DatedValue(value, PMI, "CIER", data_month=dm), today=today, calendar=None)


def _prev(month: str | None, value=50.0) -> DatedValue:
    return DatedValue(value, PREV, "hist", data_month=_d(month) if month else None)


# ══════════════════════════════════════════════════════════════════════════
# 1. 規則表
# ══════════════════════════════════════════════════════════════════════════
class TestPolicy:
    def test_pmi_prev_uses_previous_month_policy(self):
        pol = FRESHNESS_POLICY[PREV]
        assert isinstance(pol, PreviousMonthOfPolicy)
        assert not isinstance(pol, MonthlyPolicy)
        assert pol.anchor_key == PMI

    def test_anchor_is_monthly_policy_in_table(self):
        for k, pol in FRESHNESS_POLICY.items():
            if isinstance(pol, PreviousMonthOfPolicy):
                assert pol.anchor_key in FRESHNESS_POLICY, k
                assert isinstance(FRESHNESS_POLICY[pol.anchor_key], MonthlyPolicy), k

    def test_policy_rejects_empty_anchor(self):
        with pytest.raises(ValueError):
            PreviousMonthOfPolicy(anchor_key="")

    def test_assess_refuses_previous_month_policy(self):
        """⛔ `assess()` 不得默默對前月套月頻規則。"""
        with pytest.raises(ValueError, match="assess_previous_month"):
            assess(_prev("2026-08-01"), today=T, calendar=None)

    def test_policy_keys_unchanged(self):
        from src.services.macro_state_locker import _ENGINE_NUMERIC_INPUTS
        assert set(FRESHNESS_POLICY) == set(_ENGINE_NUMERIC_INPUTS) | {"Index_Below_MA5"}


# ══════════════════════════════════════════════════════════════════════════
# 2. assess_previous_month 各分支
# ══════════════════════════════════════════════════════════════════════════
class TestAssessPreviousMonth:
    def test_normal_fresh(self):
        a = _anchor("2026-09-01")
        assert a.verdict.status == FRESH
        av = assess_previous_month(_prev("2026-08-01", 47.5), a)
        assert av.verdict.status == FRESH
        assert av.scoring_value == 47.5
        assert av.verdict.lag is None and av.verdict.overdue_days is None
        assert av.verdict.lag_unit == FP.LAG_UNIT_PERIOD
        assert av.verdict.evaluated_on == T
        assert "2026-08" in av.verdict.reason and "2026-09" in av.verdict.reason

    @pytest.mark.parametrize("anchor_month,anchor_status", [
        ("2026-07-01", STALE),     # 當期已落後 2 期
        ("2026-08-01", STALE),     # 當期已落後 1 期
        ("2026-10-01", UNDET),     # 當期資料月尚未結束（日期可疑）
    ])
    def test_anchor_not_fresh_gives_undetermined(self, anchor_month, anchor_status):
        a = _anchor(anchor_month)
        assert a.verdict.status == anchor_status
        prev_m = (_d(anchor_month).replace(day=1) - timedelta(days=1)).replace(day=1)
        av = assess_previous_month(DatedValue(50.0, PREV, "hist", data_month=prev_m), a)
        assert av.verdict.status == UNDET
        assert av.scoring_value is None
        assert "當期" in av.verdict.reason and "不可用" in av.verdict.reason

    def test_anchor_missing_gives_undetermined(self):
        a = assess(DatedValue(None, PMI, "CIER", missing_reason="台灣 PMI 無數值"),
                   today=T, calendar=None)
        assert a.verdict.status == MISSING
        av = assess_previous_month(_prev("2026-08-01"), a)
        assert av.verdict.status == UNDET and av.scoring_value is None

    def test_anchor_handbuilt_fresh_but_nan_gives_undetermined(self):
        """手工組出「FRESH 但值為 NaN」的當期 → 仍視為當期不可用。"""
        dv = DatedValue(float("nan"), PMI, "x", data_month=_d("2026-09-01"))
        a = AssessedValue(dv, FreshnessVerdict(FRESH, 0, FP.LAG_UNIT_PERIOD, 0, "hand", T))
        av = assess_previous_month(_prev("2026-08-01"), a)
        assert av.verdict.status == UNDET

    def test_prev_value_none_is_missing(self):
        dv = DatedValue(None, PREV, "hist", missing_reason="PMI 歷史中找不到前一資料月 2026-08")
        av = assess_previous_month(dv, _anchor("2026-09-01"))
        assert av.verdict.status == MISSING
        assert av.verdict.reason == "PMI 歷史中找不到前一資料月 2026-08"

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), "50.1"])
    def test_prev_value_non_finite_is_missing(self, bad):
        av = assess_previous_month(_prev("2026-08-01", bad), _anchor("2026-09-01"))
        assert av.verdict.status == MISSING
        assert av.verdict.reason == INVALID_DATA_TEXT.format(item=PREV)
        assert av.scoring_value is None

    def test_prev_without_data_month_is_missing(self):
        av = assess_previous_month(_prev(None, 50.0), _anchor("2026-09-01"))
        assert av.verdict.status == MISSING
        assert "無資料月份" in av.verdict.reason

    @pytest.mark.parametrize("prev_month", ["2026-09-01", "2026-07-01", "2026-10-01", "2025-08-01"])
    def test_prev_month_mismatch_is_missing(self, prev_month):
        """同月（拿本月值頂替）、隔兩月、較晚月、去年同月 → 一律「前一資料月不符」。"""
        av = assess_previous_month(_prev(prev_month), _anchor("2026-09-01"))
        assert av.verdict.status == MISSING
        assert "前一資料月不符" in av.verdict.reason
        assert av.scoring_value is None

    def test_cross_year(self):
        today = date(2026, 2, 14)
        a = _anchor("2026-01-01", today=today)
        assert a.verdict.status == FRESH
        ok = assess_previous_month(_prev("2025-12-01", 47.0), a)
        assert ok.verdict.status == FRESH and ok.scoring_value == 47.0
        assert ok.verdict.evaluated_on == today
        bad = assess_previous_month(_prev("2025-11-01", 47.0), a)
        assert bad.verdict.status == MISSING and "前一資料月不符" in bad.verdict.reason

    def test_order_anchor_checked_first(self):
        """當期不可用時，即使前月值也缺，結果仍是 UNDETERMINED（當期優先）。"""
        av = assess_previous_month(_prev(None, None), _anchor("2026-07-01"))
        assert av.verdict.status == UNDET

    def test_config_errors(self):
        a = _anchor("2026-09-01")
        with pytest.raises(ValueError):   # prev 用錯 key（不是 PreviousMonthOfPolicy）
            assess_previous_month(DatedValue(50.0, PMI, "x", data_month=_d("2026-08-01")), a)
        m1b = assess(DatedValue(3.0, "M1B_YoY_pct", "x", data_month=_d("2026-08-01")),
                     today=T, calendar=None)
        with pytest.raises(ValueError):   # anchor 不是 anchor_key 那一項
            assess_previous_month(_prev("2026-07-01"), m1b)
        with pytest.raises(ValueError):   # 月頻卻帶 as_of
            assess_previous_month(DatedValue(50.0, PREV, "x", as_of=_d("2026-08-31")), a)
        with pytest.raises(KeyError):
            assess_previous_month(DatedValue(50.0, "Nope", "x", data_month=_d("2026-08-01")), a)
        with pytest.raises(TypeError):
            assess_previous_month(_prev("2026-08-01"), a.dv)  # type: ignore[arg-type]


class TestRegression1014:
    """「10/14 例子」：當期 9 月 FRESH、前月 8 月 —— 獨立判會 STALE（F1 的設計錯誤），新規則判 FRESH。"""

    def test_independent_monthly_rule_would_be_stale(self):
        # 釘住 F1 問題的成因：前月獨立套月頻規則，在完全正常的 10/14 也是 STALE
        v = assess_monthly(_d("2026-08-01"), today=T, lag_key="ism_pmi")
        assert v.status == STALE and v.lag == 1

    def test_prev_follows_anchor_fresh(self):
        a = _anchor("2026-09-01", 47.0)
        assert a.verdict.status == FRESH
        av = assess_previous_month(_prev("2026-08-01", 47.5), a)
        assert av.verdict.status == FRESH
        # 紅線「連兩月低於 48」兩個輸入都可計分（兩個不同的資料月）
        assert a.scoring_value == 47.0 and av.scoring_value == 47.5
        assert a.dv.data_month != av.dv.data_month


# ══════════════════════════════════════════════════════════════════════════
# 3. L2 extract_pmi_prev
# ══════════════════════════════════════════════════════════════════════════
def _hist(rows) -> pd.DataFrame:
    """仿實際 parquet：date 為 object 欄（`datetime.date`）、pmi float64、source／fetched_at 字串。"""
    df = pd.DataFrame(rows, columns=["date", "pmi", "source", "fetched_at"])
    df["date"] = df["date"].astype(object)
    return df


_SRC = "data.gov.tw:dataset:6100"
_FA = "2026-09-24T13:25:17.353825+00:00"
_HIST_ROWS = [
    (date(2025, 12, 1), 50.1, _SRC, _FA),
    (date(2026, 1, 1), 51.2, _SRC, _FA),
    (date(2026, 6, 1), 60.7, _SRC, _FA),
    (date(2026, 7, 1), 61.5, _SRC, _FA),
    (date(2026, 8, 1), 62.5, _SRC, _FA),
    (date(2026, 9, 1), 63.4, _SRC, "2026-10-01T16:13:27.915204+00:00"),
]


def _ext(df, anchor) -> DatedValue:
    out = DI.extract_pmi_prev(df, anchor)
    assert set(out) == {PREV}
    return out[PREV]


class TestExtractPmiPrev:
    def test_fixture_matches_real_schema(self):
        df = _hist(_HIST_ROWS)
        assert df["date"].dtype == object and isinstance(df["date"].iloc[0], date)
        assert df["pmi"].dtype == np.float64

    def test_normal(self):
        dv = _ext(_hist(_HIST_ROWS), _d("2026-09-01"))
        assert dv.value == 62.5 and type(dv.value) is float
        assert dv.data_month == _d("2026-08-01")
        assert dv.series_key == PREV
        assert DI.SRC_PMI_PREV in dv.source and _SRC in dv.source
        assert not dv.missing_reason

    def test_takes_anchor_previous_not_last_row(self):
        """⛔ 不取最後一列：anchor 8 月 → 取 7 月（即使 9 月在表內、且是最後一列）。"""
        dv = _ext(_hist(_HIST_ROWS), _d("2026-08-01"))
        assert dv.value == 61.5 and dv.data_month == _d("2026-07-01")

    def test_unsorted_history(self):
        dv = _ext(_hist(list(reversed(_HIST_ROWS))), _d("2026-09-01"))
        assert dv.value == 62.5

    def test_cross_year(self):
        dv = _ext(_hist(_HIST_ROWS), _d("2026-01-01"))
        assert dv.value == 50.1 and dv.data_month == _d("2025-12-01")

    def test_not_found(self):
        dv = _ext(_hist(_HIST_ROWS), _d("2026-06-01"))   # 5 月不在表內
        assert dv.value is None and dv.data_month is None
        assert "找不到前一資料月 2026-05" in dv.missing_reason

    def test_anchor_none(self):
        dv = _ext(_hist(_HIST_ROWS), None)
        assert dv.value is None and "無法定位前一資料月" in dv.missing_reason

    @pytest.mark.parametrize("bad", [date(2026, 9, 15), datetime(2026, 9, 1), "2026-09-01",
                                     pd.Timestamp("2026-09-01")])
    def test_anchor_must_be_month_start_date(self, bad):
        with pytest.raises(ValueError):
            DI.extract_pmi_prev(_hist(_HIST_ROWS), bad)

    def test_duplicate_inconsistent_is_missing(self):
        rows = _HIST_ROWS + [(date(2026, 8, 1), 62.0, "other", _FA)]
        dv = _ext(_hist(rows), _d("2026-09-01"))
        assert dv.value is None
        assert "值不一致" in dv.missing_reason and "2026-08" in dv.missing_reason

    def test_duplicate_consistent_takes_value(self):
        rows = _HIST_ROWS + [(date(2026, 8, 1), 62.5, "other-src", _FA)]
        dv = _ext(_hist(rows), _d("2026-09-01"))
        assert dv.value == 62.5 and dv.data_month == _d("2026-08-01")
        assert _SRC in dv.source and "other-src" in dv.source

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), None])
    def test_non_finite_is_missing(self, bad):
        rows = [r if r[0] != date(2026, 8, 1) else (r[0], bad, r[2], r[3]) for r in _HIST_ROWS]
        dv = _ext(_hist(rows), _d("2026-09-01"))
        assert dv.value is None and "非有限值" in dv.missing_reason

    def test_string_value_is_missing(self):
        df = _hist(_HIST_ROWS)
        df["pmi"] = df["pmi"].astype(object)
        df.loc[df["date"] == date(2026, 8, 1), "pmi"] = "62.5"
        dv = _ext(df, _d("2026-09-01"))
        assert dv.value is None and "非有限值" in dv.missing_reason

    def test_duplicate_one_nan_is_missing(self):
        """重複月其中一列 NaN → 判缺（⛔ 不挑有值的那列）。"""
        rows = _HIST_ROWS + [(date(2026, 8, 1), float("nan"), _SRC, _FA)]
        dv = _ext(_hist(rows), _d("2026-09-01"))
        assert dv.value is None

    def test_other_date_formats(self):
        """ISO 字串、Timestamp 的日期欄也能比對（與 `extract_monthly` 同一個 `coerce_month_start`）。"""
        df = _hist(_HIST_ROWS)
        df["date"] = [d.isoformat() for d in df["date"]]
        assert _ext(df, _d("2026-09-01")).value == 62.5
        df["date"] = pd.to_datetime(df["date"])
        assert _ext(df, _d("2026-09-01")).value == 62.5

    def test_unparsable_date_rows_ignored(self):
        rows = [(r[0] if r[0] != date(2026, 8, 1) else "2026-8", *r[1:]) for r in _HIST_ROWS]
        dv = _ext(_hist(rows), _d("2026-09-01"))
        assert dv.value is None and "找不到前一資料月 2026-08" in dv.missing_reason

    def test_no_source_column(self):
        df = _hist(_HIST_ROWS).drop(columns=["source"])
        dv = _ext(df, _d("2026-09-01"))
        assert dv.value == 62.5 and dv.source == DI.SRC_PMI_PREV

    @pytest.mark.parametrize("df,why", [
        (None, "讀不到"),
        (pd.DataFrame(columns=["date", "pmi"]), "為空"),
        (pd.DataFrame({"date": [date(2026, 8, 1)]}), "無「pmi」欄"),
        (pd.DataFrame({"pmi": [62.5]}), "無「date」欄"),
        ({"date": [date(2026, 8, 1)], "pmi": [62.5]}, "型別不明"),
    ])
    def test_bad_history(self, df, why):
        dv = _ext(df, _d("2026-09-01"))
        assert dv.value is None and why in dv.missing_reason and "2026-08" in dv.missing_reason

    def test_end_to_end_with_live_anchor(self):
        """當期（live）＋前月（parquet 歷史）→ 兩者都 FRESH；來源分別記錄。"""
        live = {"ism_pmi": {"value": 47.0, "date": "2026-09-01", "source": "data.gov.tw"}}
        cur = DI.extract_monthly(live, None)[PMI]
        a = assess(cur, today=T, calendar=None)
        prev = DI.extract_pmi_prev(_hist(_HIST_ROWS), cur.data_month)[PREV]
        av = assess_previous_month(prev, a)
        assert a.verdict.status == FRESH and av.verdict.status == FRESH
        assert a.dv.source == "data.gov.tw" and "tw_pmi.parquet" in av.dv.source
        # 當期過期 → 前月連帶無法判定（紅線無法評估），⛔ 不拿前月自己的日期另判
        live_old = {"ism_pmi": {"value": 47.0, "date": "2026-07-01"}}
        cur2 = DI.extract_monthly(live_old, None)[PMI]
        a2 = assess(cur2, today=T, calendar=None)
        av2 = assess_previous_month(DI.extract_pmi_prev(_hist(_HIST_ROWS), cur2.data_month)[PREV], a2)
        assert a2.verdict.status == STALE and av2.verdict.status == UNDET

    def test_covered_keys(self):
        assert DI.KEY_PMI_PREV == PREV
        assert PREV in DI.COVERED_ENGINE_INPUTS and PREV not in DI.SESSION_ENGINE_INPUTS
        assert DI.COVERED_ENGINE_INPUTS == DI.SESSION_ENGINE_INPUTS + DI.HISTORY_ENGINE_INPUTS
        assert set(DI.COVERED_ENGINE_INPUTS) == set(FRESHNESS_POLICY)


# ══════════════════════════════════════════════════════════════════════════
# 4. L1 load_tw_pmi_history ＋ repo 實檔 schema
# ══════════════════════════════════════════════════════════════════════════
class TestL1Loader:
    def test_missing_file_returns_none(self, tmp_path):
        assert MCR.load_tw_pmi_history(tmp_path) is None

    def test_reads_raw(self, tmp_path):
        df = _hist(_HIST_ROWS)
        df.to_parquet(tmp_path / MCR.TW_PMI_PARQUET_NAME)
        got = MCR.load_tw_pmi_history(tmp_path)
        assert got is not None and list(got.columns) == list(df.columns) and len(got) == len(df)
        assert _ext(got, _d("2026-09-01")).value == 62.5

    def test_missing_column_returns_none(self, tmp_path):
        _hist(_HIST_ROWS).drop(columns=["pmi"]).to_parquet(tmp_path / MCR.TW_PMI_PARQUET_NAME)
        assert MCR.load_tw_pmi_history(tmp_path) is None

    def test_same_file_as_v2_service(self):
        from src.services import macro_v2_service as V2
        assert MCR.TW_PMI_PARQUET_NAME == V2._TW_PMI_PARQUET_NAME


_REAL = REPO / "data_cache" / MCR.TW_PMI_PARQUET_NAME


@pytest.mark.skipif(not _REAL.exists(), reason="repo 內無 data_cache/tw_pmi.parquet")
class TestRealParquet:
    def test_schema_and_months(self):
        df = MCR.load_tw_pmi_history(REPO / "data_cache")
        assert df is not None
        assert {"date", "pmi", "source", "fetched_at"} <= set(df.columns)
        months = [coerce_month_start(v) for v in df["date"]]
        assert all(m is not None for m in months)
        # 每列都是月初（資料月），且無重複月
        assert all(coerce_plain_date(v) == m for v, m in zip(df["date"], months))
        assert len(set(months)) == len(months)
        assert all(math.isfinite(float(v)) for v in df["pmi"])

    def test_extract_from_latest_month(self):
        df = MCR.load_tw_pmi_history(REPO / "data_cache")
        latest = max(coerce_month_start(v) for v in df["date"])
        dv = _ext(df, latest)
        assert dv.value is not None, dv.missing_reason
        assert FP.is_previous_data_month(latest, dv.data_month)


# ══════════════════════════════════════════════════════════════════════════
# 5. 快取 ≠ 新鮮度
# ══════════════════════════════════════════════════════════════════════════
def _max_fresh_window_days(lag_key: str = "ism_pmi") -> tuple[int, date, date]:
    """實算：資料月 M 月初到「STALE 起點前一天」（最後一個 FRESH 日）的最大天數。"""
    best = (-1, None, None)
    for y in range(2020, 2036):
        for mth in range(1, 13):
            m = date(y, mth, 1)
            last = None
            for k in range(0, 160):
                t = m + timedelta(days=k)
                if assess_monthly(m, today=t, lag_key=lag_key).status == FRESH:
                    last = t
            assert last is not None, m
            # 最後一個 FRESH 日的隔天必須是 STALE（中間沒有其他狀態），窗口才有意義
            assert assess_monthly(m, today=last + timedelta(days=1), lag_key=lag_key).status == STALE
            if (last - m).days > best[0]:
                best = ((last - m).days, m, last)
    return best


class TestCacheVsFreshness:
    def test_source_window_covers_fresh_window(self):
        from src.data.macro import macro_core as MC
        days, m, last = _max_fresh_window_days()
        assert days == 69, (days, m, last)   # 31＋31＋7：資料月 M 與 M+1 都是大月 + 緩衝 7 天
        src_window = inspect.signature(MC.fetch_tw_pmi).parameters["max_age_days"].default
        assert src_window == 90
        assert days <= src_window
        # 快取保留期也不得短於新鮮窗（否則快取會比規則先丟掉仍新鮮的資料）
        assert days <= MC._MACRO_CACHE_TTL_DAYS
        # 檔頭寫的「69 天」必須等於實算值（數字改了文件要跟著改）
        assert f"實算為 {days} 天" in (FP.__doc__ or "")
        assert f"實算 {days} 天" in (MC.fetch_tw_pmi.__doc__ or "")

    def test_source_filter_accepts_last_fresh_day(self):
        """以純函式 `_parse_dgtw_pmi_csv` 實測：在最壞情況的最後一個 FRESH 日，來源篩選仍收這一列。"""
        from src.data.macro import macro_core as MC
        days, m, last = _max_fresh_window_days()
        csv = f"Date,PMI,NMI\n{m.year}{m.month:02d},50.5,-\n"
        got = MC._parse_dgtw_pmi_csv(csv, today=last, max_age_days=90)
        assert got == {"value": 50.5, "date": m.isoformat()}
        assert assess_monthly(m, today=last, lag_key="ism_pmi").status == FRESH

    @pytest.fixture
    def stale_cache_env(self, tmp_path, monkeypatch):
        """8 源全敗（不連網）＋ 快取目錄換成 tmp；回傳「寫快取」函式。"""
        from shared import fetch_monitor
        from src.data.macro import macro_core as MC

        eph, dur = tmp_path / "cache", tmp_path / "durable"
        eph.mkdir()
        dur.mkdir()
        monkeypatch.setattr(MC, "_MACRO_CACHE_DIR", str(eph))
        monkeypatch.setattr(MC, "_MACRO_DURABLE_DIR", str(dur))
        monkeypatch.setattr(MC, "PMI_SOURCE_REGISTRY",
                            [("FAKE-A", lambda today, mad, errs: None),
                             ("FAKE-B", lambda today, mad, errs: None)])
        _saved = dict(fetch_monitor._MONITOR_REGISTRY.get("fetch_tw_pmi", {}))

        def write(data_month: str, cached_at: datetime):
            payload = {"value": 47.2, "date": data_month, "label": "x",
                       "source": "data.gov.tw", "is_proxy": False, "series_id": "s",
                       "cached_at": cached_at.isoformat()}
            (eph / "tw_pmi.json").write_text(json.dumps(payload), encoding="utf-8")

        yield MC, write
        fetch_monitor._MONITOR_REGISTRY["fetch_tw_pmi"] = _saved

    def test_stale_cache_judged_by_data_month_not_cached_at(self, stale_cache_env):
        """快取昨天才寫入，但資料月已落後 2 期 → 必須 STALE（不受 cached_at 影響）。"""
        MC, write = stale_cache_env
        write("2026-07-01", datetime.now() - timedelta(days=1))
        res = MC.fetch_tw_pmi()
        assert res["is_stale"] is True and res["value"] == 47.2
        assert res["date"] == "2026-07-01"          # stale-cache 保留原始資料月
        assert res["source"].startswith("stale-cache(")
        dv = DI.extract_monthly({"ism_pmi": res}, None)[PMI]
        assert dv.data_month == _d("2026-07-01")
        av = assess(dv, today=T, calendar=None)
        assert av.verdict.status == STALE and av.verdict.lag == 2
        assert av.scoring_value is None

    def test_verdict_independent_of_cached_at(self, stale_cache_env):
        """同一個資料月，cached_at 是昨天或 85 天前 → 判定逐字相同。"""
        MC, write = stale_cache_env
        verdicts = []
        for age in (1, 85):
            write("2026-09-01", datetime.now() - timedelta(days=age))
            res = MC.fetch_tw_pmi()
            assert res["date"] == "2026-09-01"
            verdicts.append(assess(DI.extract_monthly({"ism_pmi": res}, None)[PMI],
                                   today=T, calendar=None).verdict)
        assert verdicts[0] == verdicts[1] and verdicts[0].status == FRESH

    def test_cache_retention_is_separate(self, stale_cache_env):
        """快取超過保留期（90 天）→ 不回快取 → 當期判缺；這是「快取還在不在」，不是新鮮度。"""
        MC, write = stale_cache_env
        write("2026-09-01", datetime.now() - timedelta(days=MC._MACRO_CACHE_TTL_DAYS))
        res = MC.fetch_tw_pmi()
        assert res["value"] is None
        av = assess(DI.extract_monthly({"ism_pmi": res}, None)[PMI], today=T, calendar=None)
        assert av.verdict.status == MISSING


# ══════════════════════════════════════════════════════════════════════════
# 6. 還原 pair 自證
# ══════════════════════════════════════════════════════════════════════════
def test_revert_pairs_reproduce_pre_z63_cache_reader():
    """還原 pair 套上後，`macro_cache_reader.py` 不再含本批新增的 public 名稱（Z40 sha 守衛靠它串接）。"""
    code = z63_revert_for(_MCR_REL, (REPO / _MCR_REL).read_text(encoding="utf-8"))
    assert "load_tw_pmi_history" not in code and "TW_PMI_PARQUET_NAME" not in code
    from tests.test_batch_z40 import Z40_BASE_SHA, z40_revert_for
    import hashlib
    assert hashlib.sha256(z40_revert_for(_MCR_REL, (REPO / _MCR_REL).read_text(encoding="utf-8"))
                          .encode("utf-8")).hexdigest() == Z40_BASE_SHA[_MCR_REL]
