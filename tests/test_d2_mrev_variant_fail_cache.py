# -*- coding: utf-8 -*-
"""批 D2 — D2-f22 變形：單股月營收 FinMind **確定抓取失敗**、OpenAPI 正常 → 降級 1 列不入快取。

三個最容易出錯的輸入（§6）：
1. FinMind 確定失敗（`finmind_get` 回報 failed）＋ OpenAPI 正常 → 回降級 1 列（同修前），但不入 6 小時快取
2. FinMind 恢復、冷卻期滿 → 必須重抓、拿到 FinMind 的完整 19 個月
3. FinMind 只是回空（未回報失敗）→ 照舊快取（不猜；見 test_d3e 的 TestD2f22StillCached）
"""
from __future__ import annotations

import pytest

import src.data.stock.monthly_revenue_fetcher as MR
from shared.fail_cooldown import FAIL_COOLDOWN_SEC
from tests.test_d3e_mrev_fail_cache import (  # noqa: F401 — fixture 由 pytest 依名稱取用
    _assert_single_openapi_row, fc_clock, world,
)


@pytest.fixture()
def fm_down(world, monkeypatch):
    """替身 finmind_get：`state['down']` 時單股請求回空並回報確定失敗（D2-f24 的 failed 入口）。"""
    state = {"down": True}
    orig = world.finmind_get

    def _fg(dataset, data_id=None, failed=None, **kw):
        if data_id is not None and state["down"]:
            world._bump("fm_single")
            if failed is not None:
                failed.append(f"{dataset}: ConnectionError")
            import pandas as pd
            return pd.DataFrame()
        return orig(dataset, data_id=data_id, **kw)

    monkeypatch.setattr(MR, "finmind_get", _fg)
    return state


def test_degraded_row_not_cached_then_heals(world, fm_down, fc_clock):
    world.recover()                                   # OpenAPI 正常
    first = MR.fetch_monthly_revenue("2330")
    _assert_single_openapi_row(first, "2330")         # 回傳同修前（降級 1 列）
    n1 = dict(world.calls)
    fm_down["down"] = False
    world.fm_single = "ok"
    again = MR.fetch_monthly_revenue("2330")
    assert world.calls == n1, "冷卻期內不重打"
    _assert_single_openapi_row(again, "2330")
    fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
    healed = MR.fetch_monthly_revenue("2330")
    assert len(healed) == 19, "FinMind 恢復、冷卻期滿 → 降級結果不得被快取擋住"
    n2 = dict(world.calls)
    fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
    assert len(MR.fetch_monthly_revenue("2330")) == 19 and world.calls == n2, "成功照舊快取"


def test_finmind_failed_and_not_in_openapi_not_cached(world, fm_down, fc_clock):
    """FinMind 確定失敗、OpenAPI 正常但沒有這一檔 → 空表（同修前）不入快取。"""
    world.recover()
    first = MR.fetch_monthly_revenue("9999")
    assert first.empty
    fm_down["down"] = False
    world.fm_single = "ok"
    fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
    assert len(MR.fetch_monthly_revenue("9999")) == 19, "主源確定失敗的空表不得入快取"
