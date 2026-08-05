"""DEPRECATED v19.174：本檔已改名為 fin_health_diff.py（去識別化）。保留轉發避免外部 import 斷裂。"""
from src.compute.health.fin_health_diff import *  # noqa: F401,F403
from src.compute.health.fin_health_diff import (  # noqa: F401
    _FH_MODULES,
    _score,
    _TOP_LEVEL_LIGHTS,
    _walk_statuses,
    diff_mj_health,
)
