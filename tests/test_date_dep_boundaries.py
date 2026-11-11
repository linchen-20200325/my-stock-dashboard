# -*- coding: utf-8 -*-
"""TEST-DATE-DEP-1（Issue #1130 裁示 4）—— 月營收『公告時點』邊界測試：全部以**注入的 as_of／today** 計算，不依賴真實時鐘。

守什麼：
  · `shared.staleness.monthly_publication_due` / `expected_latest_data_month`（發布延遲 SSOT
    `MACRO_PUBLICATION_LAG_DAYS['tw_monthly_revenue']`）；
  · `monthly_revenue_month_contract.compute_month_contract` 的『目標月』（`yoy_target_months`）與公告時點資格
    （`target_date_eligible` / `excluded_not_yet_due_months`）。

判準（以實際程式為準，逐字實測，**不是**「月底後第 10 天」）：
  資料月 M 的最晚應發布日 due(M) = (M+1)/01 + 10 天 ＝ **次月 11 日**（＝月底後第 11 天）。
  ⇒ as_of ＝ 次月 11 日（公告日當日）→ M 已入目標月；as_of ＝ 次月 10 日（前一日）→ M 尚未入。
  （CLAUDE.md §2.3「月後 ~10 天」＝ lag 常數 10；due 另加 `(M+1)/01` 一天的起算，是現行 SSOT 的既有語意。）

⛔ 本檔的字面值（10／11 日、各目標月）是**規格釘**：發布延遲或 PIT 規則若有意更動，須連同本檔一併走 PIT 決策；
   不得為了讓本檔轉綠而改字面值（突變驗證：把延遲改成 0／11，本檔必轉紅）。
⛔ 不依賴真實時鐘：`no_real_clock` 讓被測模組的 `date.today()` 一旦被呼叫就 raise。
"""
from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pandas as pd
import pytest

import shared.staleness as ST
import src.compute.health.monthly_revenue_month_contract as MC

D = dt.date
_IND = "tw_monthly_revenue"


class _NoTodayMeta(type):
    def __instancecheck__(cls, x):
        return isinstance(x, dt.date)

    def __subclasscheck__(cls, c):
        return issubclass(c, dt.date)


class _NoTodayDate(dt.date, metaclass=_NoTodayMeta):
    """`date` 的替身：建構／算術照舊（回傳真 date），但 `today()` 一被讀就炸 —— 證明被測碼沒偷讀真實時鐘。"""

    def __new__(cls, *a, **k):
        return dt.date(*a, **k)

    @classmethod
    def today(cls):  # pragma: no cover - 被呼叫即失敗
        raise AssertionError("被測碼讀了真實時鐘 date.today()；as_of／today 必須由呼叫端注入")


@pytest.fixture(autouse=True)
def no_real_clock(monkeypatch):
    """只在被測的兩個模組內把 `_dt.date.today` 封死（窄範圍，非全域時間凍結）。"""
    fake_dt = SimpleNamespace(**{k: getattr(dt, k) for k in dir(dt) if not k.startswith("__")})
    fake_dt.date = _NoTodayDate
    monkeypatch.setattr(ST, "_dt", fake_dt)
    monkeypatch.setattr(MC, "_dt", fake_dt)


def _end(asof: dt.date) -> str:
    """as_of 當天的『最後一個目標月』（YYYY-MM）。"""
    return MC._target_labels(asof)[-1]


# ── 1. SSOT 規格釘 ───────────────────────────────────────────────────
def test_lag_ssot_pinned():
    """CLAUDE.md §2.3：個股月營收發布延遲 ＝ 月後 ~10 天；緩衝 grace 預設不影響月營收契約（契約用 grace=0）。"""
    assert ST.MACRO_PUBLICATION_LAG_DAYS[_IND] == 10
    assert MC.REVENUE_INDICATOR == _IND


# ── 2. monthly_publication_due：公告日 ───────────────────────────────
@pytest.mark.parametrize("data_month,due", [
    ("2026-10", D(2026, 11, 11)),
    ("2026-11", D(2026, 12, 11)),
    ("2026-12", D(2027, 1, 11)),      # 跨年
    ("2027-01", D(2027, 2, 11)),
    ("2027-02", D(2027, 3, 11)),      # 平年二月
    ("2028-02", D(2028, 3, 11)),      # 閏年二月（2028-02-29 存在）
    ("2028-01", D(2028, 2, 11)),
])
def test_publication_due_is_next_month_11th(data_month, due):
    assert ST.monthly_publication_due(data_month + "-01", indicator=_IND) == due


# ── 3. expected_latest_data_month：公告日當日／前一日／跨月／跨年／閏年 ──
# (today, 預期『最新已到公告時點的資料月』月初)；grace=0（與月營收契約相同）
_EXPECTED = [
    # 公告日當日（次月 11）→ 已含；前一日（次月 10）→ 尚未含
    (D(2026, 11, 11), D(2026, 10, 1)),
    (D(2026, 11, 10), D(2026, 9, 1)),
    (D(2026, 12, 11), D(2026, 11, 1)),
    (D(2026, 12, 10), D(2026, 10, 1)),
    # 跨年 12→1
    (D(2027, 1, 10), D(2026, 11, 1)),
    (D(2027, 1, 11), D(2026, 12, 1)),
    (D(2027, 1, 15), D(2026, 12, 1)),
    (D(2026, 12, 31), D(2026, 11, 1)),
    (D(2027, 1, 1), D(2026, 11, 1)),
    # 跨月 1/31→2/1、2/28→3/1（平年）
    (D(2027, 1, 31), D(2026, 12, 1)),
    (D(2027, 2, 1), D(2026, 12, 1)),
    (D(2027, 2, 10), D(2026, 12, 1)),
    (D(2027, 2, 11), D(2027, 1, 1)),
    (D(2027, 2, 28), D(2027, 1, 1)),
    (D(2027, 3, 1), D(2027, 1, 1)),
    (D(2027, 3, 10), D(2027, 1, 1)),
    (D(2027, 3, 11), D(2027, 2, 1)),
    # 閏年 2028：2/29 存在；3/1 在閏日之後一天
    (D(2028, 2, 10), D(2027, 12, 1)),
    (D(2028, 2, 11), D(2028, 1, 1)),
    (D(2028, 2, 28), D(2028, 1, 1)),
    (D(2028, 2, 29), D(2028, 1, 1)),
    (D(2028, 3, 1), D(2028, 1, 1)),
    (D(2028, 3, 10), D(2028, 1, 1)),
    (D(2028, 3, 11), D(2028, 2, 1)),   # 閏年二月資料在 3/11 公告
]


@pytest.mark.parametrize("today,expected", _EXPECTED, ids=[t.isoformat() for t, _ in _EXPECTED])
def test_expected_latest_data_month_boundaries(today, expected):
    assert ST.expected_latest_data_month(lag_days=10, today=today, grace_days=0) == expected
    # 與月營收契約實際使用的路徑（SSOT 常數）一致
    got = ST.expected_latest_data_month(lag_days=ST.MACRO_PUBLICATION_LAG_DAYS[_IND], today=today, grace_days=0)
    assert got == expected


# ── 4. 月營收契約：as_of 注入 → 目標月 / 公告時點資格 ─────────────────
def _frame(through_ym: tuple[int, int], n: int = 28) -> pd.DataFrame:
    """連續 n 個月、含 revenue_year/revenue_month（date 與之同月 ⇒ 已驗證）；末月 ＝ through_ym。"""
    y, m = through_ym
    end = y * 12 + (m - 1)
    rows = []
    for k in range(end - n + 1, end + 1):
        yy, mm = k // 12, k % 12 + 1
        rows.append({"date": f"{yy:04d}-{mm:02d}-01", "revenue_year": yy, "revenue_month": mm,
                     "revenue": 1000.0 + (k % 7)})
    return pd.DataFrame(rows)


_CONTRACT_CASES = [
    # (as_of, 目標月 [舊→新])
    (D(2026, 11, 11), ["2026-08", "2026-09", "2026-10"]),     # 公告日當日 → 含 10 月
    (D(2026, 11, 10), ["2026-07", "2026-08", "2026-09"]),     # 前一日 → 不含 10 月
    (D(2026, 12, 15), ["2026-09", "2026-10", "2026-11"]),
    (D(2027, 1, 10), ["2026-09", "2026-10", "2026-11"]),      # 跨年：前一日
    (D(2027, 1, 11), ["2026-10", "2026-11", "2026-12"]),      # 跨年：當日
    (D(2027, 1, 15), ["2026-10", "2026-11", "2026-12"]),
    (D(2027, 1, 31), ["2026-10", "2026-11", "2026-12"]),
    (D(2027, 2, 1), ["2026-10", "2026-11", "2026-12"]),
    (D(2027, 2, 11), ["2026-11", "2026-12", "2027-01"]),
    (D(2027, 2, 28), ["2026-11", "2026-12", "2027-01"]),
    (D(2027, 3, 1), ["2026-11", "2026-12", "2027-01"]),
    (D(2028, 2, 29), ["2027-11", "2027-12", "2028-01"]),      # 閏日當天
    (D(2028, 3, 1), ["2027-11", "2027-12", "2028-01"]),
    (D(2028, 3, 10), ["2027-11", "2027-12", "2028-01"]),
    (D(2028, 3, 11), ["2027-12", "2028-01", "2028-02"]),      # 閏年二月資料公告日
]


@pytest.mark.parametrize("asof,targets", _CONTRACT_CASES, ids=[a.isoformat() for a, _ in _CONTRACT_CASES])
def test_contract_target_months_follow_injected_asof(asof, targets):
    # 表內多放兩個『尚未到公告時點』的月 → 必須被排除而非入目標
    df = _frame((int(targets[-1][:4]), int(targets[-1][5:])), n=26)
    ext = []
    y, m = int(targets[-1][:4]), int(targets[-1][5:])
    for _ in range(2):
        m += 1
        if m == 13:
            y, m = y + 1, 1
        ext.append({"date": f"{y:04d}-{m:02d}-01", "revenue_year": y, "revenue_month": m, "revenue": 5000.0})
    df = pd.concat([df, pd.DataFrame(ext)], ignore_index=True)

    c = MC.compute_month_contract(df, as_of=asof)
    assert c["contract_status"] == MC.STATUS_OK
    assert c["yoy_target_months"] == targets
    assert c["target_date_eligible"] == [True, True, True]               # 三個目標月皆已過公告時點、月份鍵已驗證
    assert c["excluded_not_yet_due_months"] == [MC._label(MC._month_idx(y, m) - 1), MC._label(MC._month_idx(y, m))]
    assert c["as_of"] == asof.isoformat()


def test_contract_eligibility_flips_exactly_on_announcement_day():
    """同一份資料：10 月營收在 11/10 尚未到公告時點（被排除）、11/11 起才入目標月且 eligible。"""
    df = _frame((2026, 10))
    before = MC.compute_month_contract(df, as_of=D(2026, 11, 10))
    on_day = MC.compute_month_contract(df, as_of=D(2026, 11, 11))
    assert "2026-10" in before["excluded_not_yet_due_months"] and "2026-10" not in before["yoy_target_months"]
    assert on_day["excluded_not_yet_due_months"] == [] and on_day["yoy_target_months"][-1] == "2026-10"
    assert on_day["target_date_eligible"] == [True, True, True]


def test_contract_asof_accepts_date_datetime_str_equally():
    df = _frame((2026, 10))
    ref = MC.compute_month_contract(df, as_of=D(2026, 11, 11))["yoy_target_months"]
    assert MC.compute_month_contract(df, as_of=dt.datetime(2026, 11, 11, 23, 59))["yoy_target_months"] == ref
    assert MC.compute_month_contract(df, as_of="2026-11-11")["yoy_target_months"] == ref


def test_contract_without_asof_does_not_fall_back_to_today():
    """沒給 as_of ⇒ 目標月未定（NOT VERIFIED），**不得**退回今天（`no_real_clock` 讀到 today() 會直接炸）。"""
    c = MC.compute_month_contract(_frame((2026, 10)), as_of=None)
    assert c["yoy_target_months"] == [None, None, None]
    assert c["date_eligibility"] == MC.ELIG_NOT_VERIFIED
    assert c["target_date_eligible"] == [None, None, None]


def test_real_clock_unreachable_sentinel():
    """守衛自身有效：封死的 today() 真的會炸（防 fixture 失效而靜默放行）。"""
    with pytest.raises(AssertionError):
        ST._dt.date.today()
    with pytest.raises(AssertionError):
        MC._dt.date.today()
