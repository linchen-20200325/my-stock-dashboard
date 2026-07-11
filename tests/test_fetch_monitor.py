# -*- coding: utf-8 -*-
"""v19.96 — 批次4 Item1+2:shared/fetch_monitor @monitored 裝飾器 + 孤兒 set-diff。

§8.1 設計 user 核准（最小版:decorator + registry + accessor + 裝 5 個高風險 fetcher
+ 診斷頁顯示;Item2 孤兒 set-diff 順做）。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from shared.fetch_monitor import (
    _MONITOR_REGISTRY,
    find_orphans,
    get_monitor_registry,
    monitored,
)

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _snapshot_registry():
    """每測前後還原 registry,防測試間互染（§3.3 測試隔離）。"""
    before = {k: dict(v) for k, v in _MONITOR_REGISTRY.items()}
    yield
    _MONITOR_REGISTRY.clear()
    _MONITOR_REGISTRY.update(before)


class TestDecorator:
    def test_registers_at_import_time_never_called(self):
        @monitored('t_never', category='X', frequency='daily', registry_key='K')
        def f():
            return 1
        ent = get_monitor_registry()['t_never']
        assert ent['last_status'] == '未執行'          # 沒呼叫也在(不隱形)
        assert ent['category'] == 'X' and ent['registry_key'] == 'K'
        assert ent['last_called_at'] is None

    def test_success_records_ok_rows_ms(self):
        @monitored('t_ok')
        def f():
            return pd.DataFrame({'a': [1, 2, 3]})
        f()
        ent = get_monitor_registry()['t_ok']
        assert ent['last_status'] == 'ok'
        assert ent['last_rows'] == 3
        assert ent['last_ms'] is not None and ent['last_ms'] >= 0
        assert ent['last_called_at'] is not None
        assert ent['last_error'] is None

    def test_failure_records_failed_and_reraises(self):
        @monitored('t_fail')
        def f():
            raise ValueError('boom')
        with pytest.raises(ValueError, match='boom'):   # §1 不吞,原樣上拋
            f()
        ent = get_monitor_registry()['t_fail']
        assert ent['last_status'] == 'failed'
        assert 'ValueError: boom' in ent['last_error']

    def test_none_result_rows_zero_scalar_rows_none(self):
        @monitored('t_none')
        def f_none():
            return None

        @monitored('t_scalar')
        def f_scalar():
            return 42.0
        f_none()
        f_scalar()
        reg = get_monitor_registry()
        assert reg['t_none']['last_rows'] == 0          # None → 0
        assert reg['t_scalar']['last_rows'] is None     # scalar → 未知不偽造

    def test_wraps_preserves_metadata_and_passthrough(self):
        @monitored('t_meta')
        def my_fetcher(x, *, y=2):
            """docstring."""
            return x + y
        assert my_fetcher.__name__ == 'my_fetcher'
        assert my_fetcher(1, y=4) == 5                  # 參數/回傳原樣穿透

    def test_accessor_returns_copy(self):
        @monitored('t_copy')
        def f():
            return []
        snap = get_monitor_registry()
        snap['t_copy']['last_status'] = 'HACK'
        assert _MONITOR_REGISTRY['t_copy']['last_status'] == '未執行'  # 原本不受污染


class TestFindOrphans:
    def test_orphan_detected_when_key_absent(self):
        @monitored('t_orphan', registry_key='某指標')
        def f():
            return 1
        assert 't_orphan' in find_orphans(['別的指標'])

    def test_not_orphan_when_key_present(self):
        @monitored('t_present', registry_key='某指標')
        def f():
            return 1
        assert 't_present' not in find_orphans(['某指標', '別的'])

    def test_none_registry_key_skipped(self):
        @monitored('t_nokey')     # 不宣告落點 → 誠實跳過不猜
        def f():
            return 1
        assert 't_nokey' not in find_orphans([])

    def test_empty_present_keys_safe(self):
        assert isinstance(find_orphans(None), list)


class TestProductionWiring:
    """5 個高風險 fetcher 已掛 @monitored + 診斷頁已接線(source-scan)。"""

    def test_five_fetchers_decorated(self):
        pairs = [
            ("src/data/macro/macro_core.py", "@monitored('fetch_tw_pmi'"),
            ("src/data/macro/tw_macro.py", "@monitored('fetch_business_indicator_series'"),
            ("src/data/macro/tw_macro.py", "@monitored('fetch_ndc_signal_history'"),
            ("src/data/macro/tw_macro.py", "@monitored('fetch_ndc_leading_index'"),
            ("src/data/daily/daily_data_fetchers.py", "@monitored('fetch_margin_balance'"),
        ]
        for path, needle in pairs:
            src = (REPO / path).read_text(encoding="utf-8")
            assert needle in src, f"{path} 缺 {needle}"

    def test_monitored_sits_inside_cache_decorators(self):
        # @monitored 必須在 cache 之「內」(緊貼 def) → 只記真實外抓
        tw = (REPO / "src/data/macro/tw_macro.py").read_text(encoding="utf-8")
        assert "@_ttl_cache(ttl_sec=TTL_15MIN, maxsize=4)\n@monitored('fetch_business_indicator_series'" in tw
        dd = (REPO / "src/data/daily/daily_data_fetchers.py").read_text(encoding="utf-8")
        assert "show_spinner=False)\n@monitored('fetch_margin_balance'" in dd

    def test_diag_page_wired(self):
        app = (REPO / "app.py").read_text(encoding="utf-8")
        assert "render_fetch_monitor_panel()" in app
        panel = (REPO / "src/ui/pages/data_registry_panel.py").read_text(encoding="utf-8")
        assert "def render_fetch_monitor_panel" in panel
        assert "find_orphans" in panel

    def test_import_side_effect_registers_production_fetchers(self):
        # import 這兩個 L1 模組後,監控清單應含 5 個 production fetcher
        import src.data.daily.daily_data_fetchers  # noqa: F401
        import src.data.macro.macro_core  # noqa: F401
        import src.data.macro.tw_macro  # noqa: F401
        reg = get_monitor_registry()
        for name in ('fetch_tw_pmi', 'fetch_business_indicator_series',
                     'fetch_ndc_signal_history', 'fetch_ndc_leading_index',
                     'fetch_margin_balance'):
            assert name in reg, f"{name} 未登錄"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
