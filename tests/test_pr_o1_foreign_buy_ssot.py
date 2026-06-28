"""v18.349 PR-O1 — 個股組合 foreign_buy 真 bug 修 + 單位 SSOT 對齊。

audit 發現:
- tab_stock_grp.py:1202/1240 讀 _rp.get('foreign_buy', 0) 但 results_t3 從未寫此欄
  → AI prompt 永遠顯示「外資 0.0 億」誤導 user
- 同處 /1e8「億」是錯誤假設值在「元」,實際 df['外資'] 單位 = 張(L286 /1000)
- data_loader.py:709 fill_cols 未明示單位

§3.3 反捏造 + §4.1 量綱:單位編碼必要,不可預設假設。

守衛測重點(無 IO,純檔案 + AST 檢驗):
1. tab_stock_grp.py results_t3.append 區段含 foreign_buy 欄(防 regression)
2. tab_stock_grp.py 兩處 AI prompt 顯示用「張」非「億」
3. data_loader.py L709 fill_cols 鄰近含「單位 = 張」註解
"""
from __future__ import annotations

import unittest


class TestForeignBuyPopulated(unittest.TestCase):

    def test_results_t3_writes_foreign_buy(self):
        """results_t3.append 應包含 foreign_buy 欄(原 bug:從未寫入)。"""
        with open('tab_stock_grp.py', encoding='utf-8') as f:
            src = f.read()
        # 防 regression:確認 PR-O1 加的 foreign_buy 寫入點還在
        self.assertIn("'foreign_buy': _fb4", src,
                      'foreign_buy 欄位需被寫入 results_t3(PR-O1 修)')

    def test_fb_computed_from_df_foreign_col(self):
        """_fb4 應從 df['外資'] 計算(SSOT 對齊 data_loader L286 張單位)。"""
        with open('tab_stock_grp.py', encoding='utf-8') as f:
            src = f.read()
        self.assertIn("df4['外資'].tail(20)", src,
                      '_fb4 計算應讀近 20 日 df[外資] 累計')


class TestDisplayUnitsCorrect(unittest.TestCase):
    """顯示單位「張」非「億」(原 bug:/1e8 假設「元」是錯的)。"""

    def test_port_lines_display_uses_lots(self):
        """L1217-area 主 AI prompt 應用「張」單位。"""
        with open('tab_stock_grp.py', encoding='utf-8') as f:
            src = f.read()
        # 新顯示串
        self.assertIn("外資近20日", src, 'AI prompt 應有「外資近20日」字樣')
        # 不應再有 /1e8 後直接接「億」(舊 bug pattern)
        # 注意:其他欄位(合約負債 /1e8 億)是正確的,只擋 foreign_buy 的舊 pattern
        self.assertNotIn("abs(_fb_p)/1e8", src,
                         '舊 bug pattern abs(_fb_p)/1e8 應已清除')
        self.assertNotIn("abs(_fb_r)/1e8", src,
                         '舊 bug pattern abs(_fb_r)/1e8 應已清除')


class TestUnitAnnotationAdded(unittest.TestCase):
    """data_loader.py L709 fill_cols 鄰近含單位註解(SSOT 文檔化)。"""

    def test_data_loader_has_unit_annotation(self):
        with open('src/data/core/data_loader.py', encoding='utf-8') as f:
            src = f.read()
        # 新增的 SSOT 對齊註記
        self.assertIn('PR-O1 SSOT 對齊註記', src)
        # 明示「張」單位
        self.assertIn('單位 = **張**', src,
                      'fill_cols 鄰近應有「單位 = 張」明文註解')
        # 提及 _normalize_inst_pivot L286 SSOT 源
        self.assertIn('_normalize_inst_pivot L286', src,
                      '應指回 SSOT 來源 _normalize_inst_pivot 的 /1000 轉換')


class TestImports(unittest.TestCase):

    def test_tab_stock_grp(self):
        import tab_stock_grp  # noqa

    def test_data_loader(self):
        from src.data.core import data_loader  # noqa


if __name__ == "__main__":
    unittest.main()
