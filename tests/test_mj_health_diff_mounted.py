"""tests/test_mj_health_diff_mounted.py — v19.160 守衛:MJ 體檢轉機 Tab 確實掛載於 app.py。

根因回顧:此功能 v18.463「10 Tab → 4 群組」改版時被**漏掛**(render fn 全域 0 caller),
淪為孤兒 → v19.159 團隊稽核判死並刪除。user v19.160 要求復活(找體質差→變好的公司)
並掛回 🔬 選股群組。本測試釘住「app.py 有掛載 + UI 可 import + 帶入持股 callback 在」,
避免它再次靜默變孤兒被下一輪稽核誤刪。
"""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def test_render_mj_health_diff_importable_via_package():
    """UI 經 src.ui.tabs 套件 PEP 562 轉發可取用。"""
    from src.ui.tabs import render_mj_health_diff_tab
    assert callable(render_mj_health_diff_tab)


def test_stock_grp_mounts_mj_health_diff_tab():
    """v19.163:MJ 體檢轉機併進 🏆 個股組合 Tab(批次),不再獨立分頁(孤兒回歸防線)。"""
    grp = (_REPO / "src/ui/tabs/tab_stock_grp.py").read_text(encoding="utf-8")
    assert "render_mj_health_diff_tab" in grp, "個股組合 Tab 未掛載 MJ 體檢轉機(孤兒回歸風險)"
    app = (_REPO / "app.py").read_text(encoding="utf-8")
    assert "with tab_mj:" not in app, "app.py 殘留獨立 MJ 體檢轉機分頁"


def test_load_holdings_callback_exists():
    """v19.160『帶入我的持股』callback 存在(貼清單 + 帶入持股 兩入口)。"""
    import src.ui.tabs.tab_mj_health_diff as m
    assert hasattr(m, "_mj_load_holdings_callback"), "帶入持股 callback 缺失"


def test_result_table_shows_stock_name():
    """v19.161:結果表代碼旁顯示中文名(走 get_stock_name L0 SSOT,不腦補)。"""
    src = (_REPO / "src/ui/tabs/tab_mj_health_diff.py").read_text(encoding="utf-8")
    assert "from src.config.stock_names import get_stock_name" in src, "未用股票名 SSOT"
    assert '"名稱"' in src, "結果表未加『名稱』欄"
