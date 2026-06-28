"""src/data/daily/ — 日間快照 fetcher。"""
from .daily_data_fetchers import *  # noqa: F401,F403
# 顯式 re-export _ private 名
from .daily_data_fetchers import (  # noqa: F401
    _fetch_otc_via_finmind,
    _adl_selftest,
    _get_finmind_token,
    _prov_log,
)
