"""src/data/core/ — 核心資料 fetcher。"""
from .data_loader import *  # noqa: F401,F403
from .data_registry import *  # noqa: F401,F403
# 顯式 re-export _ private 名
from .data_loader import _LOADER_VERSION  # noqa: F401
