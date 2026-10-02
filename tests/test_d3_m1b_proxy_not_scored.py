"""批 D3（DL-f1-s17 等）：M1B 代理值只顯示不計分 —— 守衛。"""
from __future__ import annotations

from shared.macro_provenance import m1b_m2_for_scoring

_PROXY = {'m1b_yoy': 3.65, 'm2_yoy': 0.91, 'gap': 2.74, 'source': 'TWII-proxy'}
_REAL = {'m1b_yoy': 7.34, 'm2_yoy': 7.42, 'gap': -0.08, 'source': 'CBC-tier2'}


class TestL0ScoringGate:
    def test_proxy_source_is_dropped(self):
        assert m1b_m2_for_scoring(_PROXY) is None

    def test_proxy_flag_is_dropped(self):
        assert m1b_m2_for_scoring({**_REAL, 'is_proxy': True}) is None
        assert m1b_m2_for_scoring({**_REAL, 'is_proxy_tier': True}) is None

    def test_real_returns_same_object(self):
        assert m1b_m2_for_scoring(_REAL) is _REAL

    def test_none_and_empty_passthrough(self):
        assert m1b_m2_for_scoring(None) is None
        _e = {}
        assert m1b_m2_for_scoring(_e) is _e
