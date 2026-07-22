"""src/data/portfolio/forward_test_store.py — 前進式驗證凍結紀錄「本地落地」(L1 Data)。

v19.147:forward-test 凍結紀錄原本只存使用者私人 Google Sheet（需 OAuth、無法 headless、
repo 端不可稽核 → 卡在 0 樣本）。本檔加一份 **git 追蹤的本地 parquet**，讓：
  - GitHub Actions cron（headless、無 OAuth）也能自動凍結、每月累積 cohort；
  - 凍結紀錄進 repo → 可稽核、跨 App 重啟持久（不再只活在私人 sheet）。

路徑 SSOT：data_cache/forward_test/picks.parquet（子目錄 → 躲過 .gitignore 的
`data_cache/*.parquet` 頂層規則，同 data_cache/fundamentals/ 手法，git 可追蹤）。
以 repo root 相對定位，免受 CWD 影響。

Schema 對齊 L2 forward_test.PICK_SNAPSHOT_HEADERS（cohort/stock_id/name/entry_price/factors/frozen_at）。
§5 冪等：同 (cohort, stock_id) 重跑不新增、不覆蓋（保留最早那筆進場價 = 真進場價）。
§8.2 L1：純檔案 I/O，無 streamlit、無業務邏輯。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.compute.screener.forward_test import PICK_SNAPSHOT_HEADERS

_REPO_ROOT = Path(__file__).resolve().parents[3]
FORWARD_TEST_STORE_PATH = _REPO_ROOT / "data_cache" / "forward_test" / "picks.parquet"

_KEY_COLS = ["cohort", "stock_id"]   # 一列 = 一個 (批次, 個股) 凍結


def load_picks_local() -> list[dict]:
    """讀本地凍結紀錄 → list[dict]（欄 = PICK_SNAPSHOT_HEADERS）。檔不存在 / 壞 → []。"""
    if not FORWARD_TEST_STORE_PATH.exists():
        return []
    try:
        df = pd.read_parquet(FORWARD_TEST_STORE_PATH)
    except Exception as _e:  # noqa: BLE001 — 壞檔不炸 UI，當無資料處理
        print(f"[forward_test_store] 讀取失敗 {FORWARD_TEST_STORE_PATH}: {type(_e).__name__}: {_e}")
        return []
    if df is None or df.empty:
        return []
    return df.to_dict("records")


def append_picks_local(rows: list[dict]) -> int:
    """把凍結列 append 進本地 parquet，回「實際新增筆數」。

    §5 冪等：同 (cohort, stock_id) 已存在 → 不新增、不覆蓋（保留最早進場價）。
    rows 空 → 回 0（不建檔）。目錄不存在自動建。
    """
    _rows = [r for r in (rows or []) if r]
    if not _rows:
        return 0
    _new = pd.DataFrame(_rows)
    for _c in _KEY_COLS:
        if _c not in _new.columns:
            raise ValueError(f"forward_test_store append 缺 key 欄：{_c}")
    _new["cohort"] = _new["cohort"].astype(str)
    _new["stock_id"] = _new["stock_id"].astype(str).str.strip()

    _existing = pd.DataFrame(load_picks_local())
    if _existing.empty:
        _added = int(len(_new.drop_duplicates(subset=_KEY_COLS)))
        _merged = _new
    else:
        _existing["cohort"] = _existing["cohort"].astype(str)
        _existing["stock_id"] = _existing["stock_id"].astype(str).str.strip()
        _seen = set(zip(_existing["cohort"], _existing["stock_id"]))
        _fresh_mask = ~_new.apply(lambda r: (r["cohort"], r["stock_id"]) in _seen, axis=1)
        _added = int(len(_new[_fresh_mask].drop_duplicates(subset=_KEY_COLS)))
        _merged = pd.concat([_existing, _new], ignore_index=True)

    # 既有在前 → 同鍵 keep='first' 保留最早進場價；欄序對齊 SSOT。
    _merged = _merged.drop_duplicates(subset=_KEY_COLS, keep="first").reset_index(drop=True)
    _ordered = [c for c in PICK_SNAPSHOT_HEADERS if c in _merged.columns]
    _merged = _merged[_ordered + [c for c in _merged.columns if c not in _ordered]]

    FORWARD_TEST_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _merged.to_parquet(FORWARD_TEST_STORE_PATH, index=False)
    return _added
