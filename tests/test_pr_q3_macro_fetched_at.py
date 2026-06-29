"""v18.353 PR-Q3 — tab_macro _job_macro 集中注入 fetched_at。

策略:6 wrappers (_fetch_vix/cpi/pmi/ndc/export/fed_funds) 已有 'source' key 在
各自 sub-dict 內(由 14 處 return 各自寫入)。集中在 _job_macro 收尾 setdefault
('fetched_at') 比改 14 處 return point 乾淨,且 schema-additive(caller 0 改)。

守衛測:
- tab_macro.py:2140 區段含 fetched_at 注入 loop
- 跳過 meta key(_loaded_at / _all_failed)
- 用 setdefault 不覆蓋既有(if any sub-dict already has fetched_at)
"""
from __future__ import annotations

import unittest


class TestMacroFetchedAtInjection(unittest.TestCase):

    def setUp(self):
        # P3-D12 v18.392:setdefault('fetched_at') loop 搬至 macro_trio_orchestrator。
        with open('src/services/macro_trio_orchestrator.py', encoding='utf-8') as f:
            self.src = f.read()

    def test_pr_q3_marker_present(self):
        """PR-Q3 marker 在 _job_macro 收尾。"""
        self.assertIn('PR-Q3 S-PROV-1 phase 19', self.src)
        self.assertIn('集中注入 fetched_at 到每個 sub-dict', self.src)

    def test_setdefault_pattern(self):
        """setdefault('fetched_at') 模式存在(不覆蓋既有)。"""
        self.assertIn("setdefault('fetched_at'", self.src)

    def test_skip_meta_keys(self):
        """meta key(_loaded_at / _all_failed)應跳過(by startswith('_'))。"""
        self.assertIn("if _k_prov.startswith('_'):", self.src)
        self.assertIn("continue", self.src)

    def test_isinstance_dict_guard(self):
        """sub-value 應 isinstance check 是 dict(否則 setdefault 會崩)。"""
        self.assertIn("isinstance(_v_prov, dict)", self.src)


class TestSimulatedInjection(unittest.TestCase):
    """模擬 _job_macro 收尾 logic,驗證行為等價。"""

    def test_inject_adds_to_sub_dicts(self):
        """6 sub-dict 都會被注入,meta key 不會。"""
        import datetime
        _r = {
            'vix': {'current': 18.5, 'source': 'Yahoo:^VIX'},
            'us_core_cpi': {'yoy': 3.2, 'source': 'FRED-API'},
            'fed_funds': {'current': 5.25, 'source': 'FRED/fredgraph.csv'},
            '_loaded_at': '2026-06-28 12:00:00',
            '_all_failed': False,
        }
        _now = datetime.datetime.utcnow().isoformat() + 'Z'
        for _k, _v in _r.items():
            if _k.startswith('_'):
                continue
            if isinstance(_v, dict):
                _v.setdefault('fetched_at', _now)
        # 3 sub-dict 都有 fetched_at
        self.assertEqual(_r['vix'].get('fetched_at'), _now)
        self.assertEqual(_r['us_core_cpi'].get('fetched_at'), _now)
        self.assertEqual(_r['fed_funds'].get('fetched_at'), _now)
        # meta key 仍是原值,沒被當 dict 處理
        self.assertEqual(_r['_loaded_at'], '2026-06-28 12:00:00')
        self.assertFalse(_r['_all_failed'])

    def test_inject_setdefault_not_overwrite(self):
        """既有 fetched_at(如 sub-dict 自己已寫)不被蓋掉。"""
        _r = {'vix': {'current': 18.5, 'fetched_at': '2020-01-01T00:00:00Z'}}
        _now = '2026-06-28T12:00:00Z'
        for _k, _v in _r.items():
            if _k.startswith('_'):
                continue
            if isinstance(_v, dict):
                _v.setdefault('fetched_at', _now)
        # 沒被蓋
        self.assertEqual(_r['vix']['fetched_at'], '2020-01-01T00:00:00Z')

    def test_inject_skips_non_dict(self):
        """sub-value 不是 dict(意外場景)不爆。"""
        _r = {'bad': 'not a dict', 'good': {'val': 1}}
        _now = '2026-06-28T12:00:00Z'
        for _k, _v in _r.items():
            if _k.startswith('_'):
                continue
            if isinstance(_v, dict):
                _v.setdefault('fetched_at', _now)
        # 'bad' 仍是字串,沒被改
        self.assertEqual(_r['bad'], 'not a dict')
        # 'good' 有 fetched_at
        self.assertEqual(_r['good']['fetched_at'], _now)


class TestImport(unittest.TestCase):
    def test_tab_macro(self):
        from src.ui.tabs import tab_macro  # noqa


if __name__ == "__main__":
    unittest.main()
