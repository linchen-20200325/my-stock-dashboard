"""DEPRECATED v19.174：本檔已改名為 fin_snapshot_io.py（去識別化）。保留轉發避免外部 import 斷裂。"""
from src.compute.health.fin_snapshot_io import *  # noqa: F401,F403
from src.compute.health.fin_snapshot_io import (  # noqa: F401
    _ensure_dir,
    _FILE_RE,
    _read_dirs,
    _sanitize_sid,
    _sanitize_yyyymm,
)
