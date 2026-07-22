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


def _build_freeze_rows(codes, *, factors, cohort: str, names: dict | None = None) -> tuple[list[dict], int]:
    """抓進場價 → build pick-snapshot rows。回 (rows, 抓不到進場價而略過的檔數)。

    共用給 gsheet / 本地 parquet 兩種 sink（DRY，避免兩處各抓一次價 / 各自組 rows）。
    §1:抓不到進場價的檔 **不凍結**（build_pick_snapshot_rows 已濾，不存假價）。
    """
    from src.compute.screener.forward_test import build_pick_snapshot_rows
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
    return _rows, len(_codes) - len(_rows)


def freeze_current_picks(codes, *, factors, cohort: str, names: dict | None = None) -> tuple[int, int]:
    """抓進場價 → 凍結本次選股存 Google Sheet。回 (存入檔數, 抓不到價而略過檔數)。

    Args:
        codes: 要凍結的股號(list[str];通常選股結果前 N 名)。
        factors: 當時勾選因子(記錄用,日後可分策略比較)。
        cohort: 批次標籤(通常凍結日 "YYYY-MM-DD")。
        names: {stock_id: 中文名}(選填,寫進 sheet 方便閱讀)。

    §1:抓不到進場價的檔**不凍結**(不存假價);gsheet 未設定 / 寫入失敗 → raise(UI 顯示)。
    """
    from src.data.portfolio.gsheet_portfolio import append_forward_test_picks
    _rows, _miss = _build_freeze_rows(codes, factors=factors, cohort=cohort, names=names)
    _n = append_forward_test_picks(_rows)
    return _n, _miss


def freeze_current_picks_local(codes, *, factors, cohort: str, names: dict | None = None) -> tuple[int, int]:
    """同 freeze_current_picks，但存 **本地 git 追蹤 parquet**（cron headless 用，無需 OAuth）。

    回 (實際新增檔數, 抓不到進場價而略過檔數)。§5 冪等：同 (cohort, stock_id) 不重複新增。
    v19.147:讓每月 cron 自動凍結 + 手動凍結都落地 repo，解「0 樣本 + 只在私人 sheet」卡關。
    """
    from src.data.portfolio.forward_test_store import append_picks_local
    _rows, _miss = _build_freeze_rows(codes, factors=factors, cohort=cohort, names=names)
    _n = append_picks_local(_rows)
    return _n, _miss


_FROZEN_COLS = ["cohort", "stock_id", "name", "entry_price", "factors", "frozen_at"]


def load_frozen_picks_df() -> pd.DataFrame:
    """讀回全部凍結紀錄為 DataFrame（欄:cohort/stock_id/name/entry_price/factors/frozen_at）。

    v19.147:合併 **本地 git 追蹤 parquet（cron + 手動）∪ Google Sheet**，同 (cohort, stock_id)
    去重（本地在前 → keep='first' 保留本地）。兩邊皆空 / gsheet 未設定 → 空 DataFrame（對帳判空不炸）。
    """
    from src.data.portfolio.forward_test_store import load_picks_local

    _recs = list(load_picks_local())               # 本地(cron 自動 + 手動)優先
    try:
        from src.data.portfolio.gsheet_portfolio import load_forward_test_picks
        _recs += list(load_forward_test_picks() or [])
    except Exception as _e:  # noqa: BLE001 — gsheet 未設定 / 讀取失敗 → 只用本地,不炸
        print(f"[forward_test_service] gsheet 凍結讀取略過:{type(_e).__name__}: {_e}")

    if not _recs:
        return pd.DataFrame(columns=_FROZEN_COLS)
    _df = pd.DataFrame(_recs)
    if "cohort" not in _df.columns or "stock_id" not in _df.columns:
        return _df
    _df["cohort"] = _df["cohort"].astype(str)
    _df["stock_id"] = _df["stock_id"].astype(str).str.strip()
    return _df.drop_duplicates(subset=["cohort", "stock_id"], keep="first").reset_index(drop=True)


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
