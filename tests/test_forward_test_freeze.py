"""tests/test_forward_test_freeze.py — 前進式驗證每月自動凍結（v19.147）。

覆蓋斷鏈③接線的三塊純邏輯（皆離線可測，不碰網路 / 不寫 repo 真檔）：
  1. L1 forward_test_store：本地 parquet append/load 往返 + §5 冪等 + 邊界。
  2. L3 get_ranked_picks：畫面/cron 同源排名的直通（delegates composite_rank_candidates）。
  3. L3 load_frozen_picks_df：本地 ∪ gsheet union 去重（本地優先）。

⚠️ store 測試以 monkeypatch 把 FORWARD_TEST_STORE_PATH 指到 tmp_path，
   絕不寫進 repo 的 data_cache/forward_test/picks.parquet（git 追蹤，測試不可污染）。
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.data.portfolio import forward_test_store as store


@pytest.fixture()
def tmp_store(tmp_path, monkeypatch):
    p = tmp_path / "forward_test" / "picks.parquet"
    monkeypatch.setattr(store, "FORWARD_TEST_STORE_PATH", p)
    return p


def _row(cohort, sid, price, name="", factors="pe_low",
         frozen="2026-07-02T14:00:00+08:00"):
    return {"cohort": cohort, "stock_id": sid, "name": name,
            "entry_price": price, "factors": factors, "frozen_at": frozen}


# ── 1. L1 store ──────────────────────────────────────────────
def test_append_and_load_roundtrip(tmp_store):
    n = store.append_picks_local([_row("2026-07-02", "2330", 100.0),
                                  _row("2026-07-02", "2317", 50.0)])
    assert n == 2
    recs = store.load_picks_local()
    assert {r["stock_id"] for r in recs} == {"2330", "2317"}


def test_idempotent_same_cohort_stock(tmp_store):
    store.append_picks_local([_row("2026-07-02", "2330", 100.0)])
    n2 = store.append_picks_local([_row("2026-07-02", "2330", 999.0)])  # 同鍵
    assert n2 == 0                                   # 不新增
    recs = store.load_picks_local()
    assert len(recs) == 1
    assert float(recs[0]["entry_price"]) == 100.0    # 保留最早進場價，不被覆蓋


def test_different_cohort_adds(tmp_store):
    store.append_picks_local([_row("2026-07-02", "2330", 100.0)])
    n = store.append_picks_local([_row("2026-08-02", "2330", 110.0)])  # 不同批次
    assert n == 1
    assert len(store.load_picks_local()) == 2


def test_empty_rows_no_file(tmp_store):
    assert store.append_picks_local([]) == 0
    assert not tmp_store.exists()                    # 空 → 不建檔
    assert store.load_picks_local() == []


def test_missing_file_returns_empty(tmp_store):
    assert store.load_picks_local() == []


def test_missing_key_col_raises(tmp_store):
    with pytest.raises(ValueError):
        store.append_picks_local([{"stock_id": "2330", "entry_price": 100.0}])  # 缺 cohort


# ── 2. get_ranked_picks 同源直通 ─────────────────────────────
def test_get_ranked_picks_eps_passthrough():
    from src.services.fundamental_screener_service import get_ranked_picks
    surv = pd.DataFrame({"stock_id": ["2330", "2317", "1101"], "eps": [30.0, 5.0, 2.0]})
    cands, _ = get_ranked_picks(["eps_high"], survivors_df=surv, auto_fetch=False, top_n=10)
    assert "代碼" in cands.columns
    assert list(cands["代碼"]) == ["2330", "2317", "1101"]   # EPS 高→低（同 composite）


def test_get_ranked_picks_empty_survivors():
    from src.services.fundamental_screener_service import get_ranked_picks
    cands, _ = get_ranked_picks(["eps_high"], survivors_df=pd.DataFrame(), auto_fetch=False)
    assert cands.empty


# ── 3. load_frozen_picks_df 本地 ∪ gsheet 去重 ───────────────
def test_load_frozen_union_dedupe(monkeypatch):
    from src.services import forward_test_service as svc
    _local = [_row("2026-07-02", "2330", 100.0)]
    _gs = [_row("2026-07-02", "2330", 999.0),   # 與本地同鍵 → 去重，保留本地
           _row("2026-07-02", "2317", 50.0)]    # 只在 gsheet → 併入
    monkeypatch.setattr("src.data.portfolio.forward_test_store.load_picks_local",
                        lambda: list(_local))
    monkeypatch.setattr("src.data.portfolio.gsheet_portfolio.load_forward_test_picks",
                        lambda: list(_gs))
    df = svc.load_frozen_picks_df()
    assert len(df) == 2                                        # 2330 去重 + 2317
    _r2330 = df[df["stock_id"] == "2330"].iloc[0]
    assert float(_r2330["entry_price"]) == 100.0              # 本地優先（keep='first'）


def test_load_frozen_empty_both(monkeypatch):
    from src.services import forward_test_service as svc
    monkeypatch.setattr("src.data.portfolio.forward_test_store.load_picks_local", lambda: [])
    monkeypatch.setattr("src.data.portfolio.gsheet_portfolio.load_forward_test_picks", lambda: [])
    df = svc.load_frozen_picks_df()
    assert df.empty
    assert list(df.columns) == ["cohort", "stock_id", "name", "entry_price", "factors", "frozen_at"]
