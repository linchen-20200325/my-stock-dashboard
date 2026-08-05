"""DEPRECATED v19.174：本檔已改名為 fin_trend_score.py（去識別化）。保留轉發避免外部 import 斷裂。"""
from src.compute.health.fin_trend_score import *  # noqa: F401,F403
from src.compute.health.fin_trend_score import (  # noqa: F401
    _LABEL_THRESHOLDS,
    _label_from_score,
    _LOW_LABEL,
    _safe_num,
    _squash,
    _yoy_step_score,
    compute_mj_trend_subscore,
)
