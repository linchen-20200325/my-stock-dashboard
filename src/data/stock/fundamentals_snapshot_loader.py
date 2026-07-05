"""src/data/stock/fundamentals_snapshot_loader.py — 全台股基本面季快照 loader(L1 Data)。

Phase 2 選股網:讀 GitHub Actions cron 產出的 MOPS 全市場季快照 parquet
(data_cache/fundamentals/{market}_{roc}Q{season}.parquet)+ latest.json 指標,
回「最新季 + 去年同季」兩張全市場合併 DataFrame,交 L2 fundamental_prescreen 初篩。

寫入端:scripts/update_fundamentals_snapshot.py(cron CLI)。本檔為對應**讀取端**。
路徑 SSOT:兩端都指 data_cache/fundamentals(本檔以 repo root 相對定位,免受 CWD 影響)。

§8.2:L1 Data。僅用 @st.cache_data(EX-CACHE-1,部署快取),無真 UI 呼叫。
§1 fail-loud:latest.json 不存在 / 最新季 parquet 全缺 → raise FileNotFoundError,
不回假資料。去年同季缺 → 回空 prev(YoY 由 L2 判 False,不猜)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

# §8.2.A EX-CACHE-1:條件 import streamlit,無真 UI 呼叫(僅 @st.cache_data)。
try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa

from shared.ttls import TTL_1DAY

# repo root = 本檔上溯 4 層(src/data/stock/xxx.py → repo/)。免受 CWD 影響。
_REPO_ROOT = Path(__file__).resolve().parents[3]
FUNDAMENTALS_CACHE_DIR = _REPO_ROOT / "data_cache" / "fundamentals"
_MARKETS = ("sii", "otc")


def _read_market_quarter(cache_dir: Path, roc_year: int, season: int) -> pd.DataFrame:
    """讀某季全市場(上市+上櫃 concat);兩市場都缺 → 空 DataFrame。"""
    frames: list[pd.DataFrame] = []
    for m in _MARKETS:
        path = cache_dir / f"{m}_{roc_year}Q{season}.parquet"
        if path.exists():
            frames.append(pd.read_parquet(path))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _load_impl(cache_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    meta_path = cache_dir / "latest.json"
    if not meta_path.exists():
        raise FileNotFoundError(
            f"[fundamentals_loader] 找不到 {meta_path};請先跑 Update Fundamentals workflow 產快照"
        )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    roc_year, season = int(meta["roc_year"]), int(meta["season"])

    current = _read_market_quarter(cache_dir, roc_year, season)
    if current.empty:
        raise FileNotFoundError(
            f"[fundamentals_loader] latest.json 指向 民國{roc_year}Q{season} 但 parquet 全缺"
        )

    prev_roc = meta.get("prev_roc_year")
    prev = (_read_market_quarter(cache_dir, int(prev_roc), season)
            if prev_roc is not None else pd.DataFrame())
    return current, prev, meta


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def load_fundamentals_snapshot() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """讀最新季 + 去年同季全市場基本面快照 → (current_df, prev_df, meta)。

    current_df: 最新季(latest.json)上市+上櫃合併,每檔一列。
    prev_df:    去年同季(prev_roc_year, 同 season);無則空 DataFrame。
    meta:       latest.json 內容(roc_year/season/prev_roc_year/updated_at)。

    §1 fail-loud:快照缺 → raise FileNotFoundError。快取 TTL_1DAY(季度資料,日級足夠)。
    """
    return _load_impl(FUNDAMENTALS_CACHE_DIR)
