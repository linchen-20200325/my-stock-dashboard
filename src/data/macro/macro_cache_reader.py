"""src/data/macro/macro_cache_reader.py — Parquet 本地快取讀取 L1(C4 v18.402).

從 L2 modules 抽出的 Parquet 檔案 I/O,落實 §8.2「L2 純函式無 I/O」契約:
- 原 `src/compute/macro/macro_signal_lookback_tw.py:109 _load_parquet_safe`
- 原 `src/compute/macro/macro_validation_tw.py:40 load_twii_close_from_parquet`

§8.2 layer:L1 Data — 本地 cache 反序列化(filesystem read,非網路 I/O)。
無 Streamlit 依賴(L2 caller 為純函式契約,L1 helper 也保持無 streamlit)。

對外 API:
- `DEFAULT_PARQUET_CACHE_DIR`:預設 cache 目錄(Path("data_cache"))
- `load_parquet_safe(path, required_cols) -> DataFrame | None`:通用 safe loader
- `load_twii_close(cache_dir) -> Series`:讀 twii_ohlcv.parquet → close series
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

DEFAULT_PARQUET_CACHE_DIR = Path("data_cache")


def load_parquet_safe(path: Path, required_cols: set) -> Optional[pd.DataFrame]:
    """安全讀 Parquet — 缺檔 / 壞檔 / 缺欄 → 回 None。

    Args:
        path: parquet 檔絕對 / 相對路徑
        required_cols: 必須存在的欄位 set;任一缺失即視為損壞,回 None

    Returns:
        DataFrame(命中)或 None(任一失敗條件)
    """
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        if df.empty or not required_cols.issubset(df.columns):
            return None
        return df
    except Exception as e:  # noqa: BLE001
        print(f"[macro_cache_reader/load_parquet_safe] {path.name} 讀檔失敗:{e}")
        return None


def load_twii_close(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> pd.Series:
    """讀 twii_ohlcv.parquet → close pd.Series indexed by date(Timestamp)。

    Args:
        cache_dir: parquet cache 目錄(預設 data_cache/)

    Returns:
        close pd.Series(name='twii_close',date 升序,NaN dropped);
        若檔不存在 / 壞 / 缺欄,回空 Series(name 保留)
    """
    path = cache_dir / "twii_ohlcv.parquet"
    df = load_parquet_safe(path, {"date", "close"})
    if df is None:
        return pd.Series(dtype=float, name="twii_close")
    try:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        s = (df.set_index("date")["close"]
               .astype(float)
               .sort_index())
        s.name = "twii_close"
        return s.dropna()
    except Exception as e:  # noqa: BLE001
        print(f"[macro_cache_reader/load_twii_close] 處理失敗:{e}")
        return pd.Series(dtype=float, name="twii_close")
