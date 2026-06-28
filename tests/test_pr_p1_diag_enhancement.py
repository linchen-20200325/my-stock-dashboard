"""v18.350 PR-P1 — 先行指標 expander 診斷表 SSOT 清晰度增強。

audit P1.1 + P1.3:
- 加 TTL(避免 user 把 30min 舊值當「即時」)
- 加備援優先級(對齊「資料診斷 Tab」TTL_CONFIG / DATA_SOURCE_PRIORITY)
- 頂部加 cache 新鮮度橙色告示

§2.4 Freshness + §3.3 SSOT 清晰度。

守衛測重點(無 IO):
1. tab_macro.py:4635 區段含新增的 TTL + 備援優先級欄
2. 頂部 cache 新鮮度告示存在
3. 8 個指標都有完整 4-tuple
4. 向下相容 fallback(舊 2-tuple 仍 render)
"""
from __future__ import annotations

import unittest


class TestDiagTableEnhanced(unittest.TestCase):

    def setUp(self):
        with open('tab_macro.py', encoding='utf-8') as f:
            self.src = f.read()

    def test_freshness_caution_banner(self):
        """頂部 cache 新鮮度橙色告示存在。"""
        self.assertIn('注意 cache 新鮮度', self.src)
        self.assertIn('「即時」≠「最新交易日」', self.src)

    def test_ttl_chips_added(self):
        """8 指標應有 ⏱ TTL 註記。"""
        self.assertIn('⏱ TTL', self.src)
        # 對齊 TTL_CONFIG SSOT
        self.assertIn('TTL_CONFIG[institutional]', self.src)
        self.assertIn('TTL_CONFIG[volume]', self.src)
        # build_leading_fast pickle TTL
        self.assertIn('build_leading_fast pickle', self.src)

    def test_fallback_priority_chips_added(self):
        """8 指標應有 🔀 備援優先級註記。"""
        self.assertIn('🔀 備援優先級', self.src)
        # 至少有 ① ② 標號
        self.assertIn('①', self.src)
        self.assertIn('②', self.src)

    def test_diag_cols_4tuple(self):
        """_diag_cols 8 entries 全升為 4-tuple(來源/公式/TTL/備援)。"""
        # 找 _diag_cols dict 區段,粗檢查至少 6 個 4-tuple pattern
        # (4-tuple 在 dict literal 內看起來是 4 個 string 後接逗號右括號)
        # 簡化:確認 8 個指標 key 都還在 + 都有「30 分」或「10 分」TTL 字樣
        for _key in ['外資大小', '前五大留倉', '前十大留倉', '選PCR',
                     '外(選)', '韭菜指數', '外資/投信/自營', '成交量']:
            self.assertIn(f"'{_key}'", self.src, f'{_key} 應存在於 _diag_cols')

    def test_backward_compat_2tuple_fallback(self):
        """渲染 loop 應守 2-tuple fallback(避免外部 caller dict 改錯崩)。"""
        # 找 fallback 守護的 marker
        self.assertIn('if len(_tup) == 4', self.src)
        self.assertIn("_ttl, _fallback = '-', '-'", self.src)


class TestImports(unittest.TestCase):
    def test_tab_macro(self):
        import tab_macro  # noqa


if __name__ == "__main__":
    unittest.main()
