"""src/services/forward_test_service.py — 前進式驗證編排(L3 service).

凍結選股(抓進場價 → build rows → 存 Google Sheet)+ 讀回對帳資料。編排:
  L1 picker_fetcher(抓進場價) + L1 gsheet_portfolio(存/讀) + L2 forward_test(純函式)。

§8.2 L3:合法組合 L1 fetcher + L1 gsheet + L2 純函式(對齊 fundamental_screener_service /
etf_sector_service pattern)。UI(L6 app.py)只呼叫本層,不直呼 L1 gsheet/picker。
"""
from __future__ import annotations

import pandas as pd


def is_freeze_available() -> bool:
    """Google Sheet 是否已設定(可凍結存檔)。未設定 → UI 顯示提示、不給按。"""
    from src.data.portfolio.gsheet_portfolio import is_configured
    try:
        return bool(is_configured())
    except Exception as _e:  # noqa: BLE001 — 設定探測失敗當未設定
        print(f"[forward_test_service] is_configured 失敗: {type(_e).__name__}: {_e}")
        return False


def freeze_current_picks(codes, *, factors, cohort: str, names: dict | None = None) -> tuple[int, int]:
    """抓進場價 → 凍結本次選股存 Google Sheet。回 (存入檔數, 抓不到價而略過檔數)。

    Args:
        codes: 要凍結的股號(list[str];通常選股結果前 N 名)。
        factors: 當時勾選因子(記錄用,日後可分策略比較)。
        cohort: 批次標籤(通常凍結日 "YYYY-MM-DD")。
        names: {stock_id: 中文名}(選填,寫進 sheet 方便閱讀)。

    §1:抓不到進場價的檔**不凍結**(不存假價);gsheet 未設定 / 寫入失敗 → raise(UI 顯示)。
    """
    from src.compute.screener.forward_test import build_pick_snapshot_rows
    from src.data.portfolio.gsheet_portfolio import append_forward_test_picks
    from src.data.stock.picker_fetcher import fetch_stock_history_1y

    _codes = [str(c).strip() for c in (codes or []) if str(c).strip()]
    _entry: dict[str, float] = {}
    for _c in _codes:
        _df, _ = fetch_stock_history_1y(_c)
        if _df is not None and not _df.empty and "Close" in _df.columns:
            _entry[_c] = float(_df["Close"].iloc[-1])
    _rows = build_pick_snapshot_rows(
        _codes, _entry, factors=factors, cohort=cohort, names=names,
        frozen_at=pd.Timestamp.now(tz="Asia/Taipei").isoformat(),
    )
    _n = append_forward_test_picks(_rows)
    return _n, len(_codes) - _n


def load_frozen_picks_df() -> pd.DataFrame:
    """讀回全部凍結紀錄為 DataFrame(欄:cohort/stock_id/name/entry_price/factors/frozen_at)。

    gsheet 無資料 / 未設定 → 空 DataFrame(對帳面板判空,不炸)。
    """
    from src.data.portfolio.gsheet_portfolio import load_forward_test_picks

    _recs = load_forward_test_picks()
    if not _recs:
        return pd.DataFrame(columns=["cohort", "stock_id", "name", "entry_price", "factors", "frozen_at"])
    return pd.DataFrame(_recs)


def reconcile_all() -> tuple[pd.DataFrame, dict]:
    """讀凍結紀錄 + 抓現價 + 0050 基準 → 對帳。回 (per_cohort_df, overall)。

    §8.2 L3 編排:L1 gsheet 讀凍結 + L1 picker 抓現價/0050 + L2 reconcile/benchmark 純函式。
    無凍結紀錄 → 空 + note(對帳面板顯示「收集中」);抓不到某檔現價 → L2 自動剔除計數。
    """
    from src.compute.screener.forward_test import (
        benchmark_returns_from_close,
        reconcile_forward_test,
    )
    from src.data.stock.picker_fetcher import fetch_stock_history_1y
    from shared.forward_test_thresholds import FORWARD_TEST_BENCHMARK

    picks = load_frozen_picks_df()
    if picks.empty:
        return pd.DataFrame(), {"n_cohorts": 0, "n_picks_total": 0,
                                "note": "尚無凍結選股紀錄(先在上方按「🧊 凍結」)。"}

    # 各持股現價(每個不重複股號抓最後收盤)
    _codes = sorted({str(c).strip() for c in picks["stock_id"] if str(c).strip()})
    _cur: dict[str, float] = {}
    for _c in _codes:
        _df, _ = fetch_stock_history_1y(_c)
        if _df is not None and not _df.empty and "Close" in _df.columns:
            _cur[_c] = float(_df["Close"].iloc[-1])

    # 0050 基準:各 cohort(凍結日)當日 close → 現在的報酬
    _bench = {}
    _bdf, _ = fetch_stock_history_1y(FORWARD_TEST_BENCHMARK)
    if _bdf is not None and not _bdf.empty and "Close" in _bdf.columns:
        _bench = benchmark_returns_from_close(_bdf["Close"], list(picks["cohort"].unique()))

    return reconcile_forward_test(picks, _cur, benchmark_returns=_bench)
