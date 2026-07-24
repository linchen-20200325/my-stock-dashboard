"""tests/test_mj_health_diff_mounted.py — v19.164 守衛:MJ「體質差→變好」轉機能力
已**合併**進「🏆 個股組合」的「📊 MJ 趨勢 × 轉機」區塊,並未消失。

歷程:
- v18.463 10→4 群組時被漏掛 → v19.159 判死刪除。
- v19.160 user 要求復活(找體質差→變好)→ 掛回 🔬 選股群組。
- v19.163 併進 🏆 個股組合(獨立 expander,自帶批次輸入)。
- v19.164 **去重合一**:轉機判定改由 `compute_one_stock_trend` 用同一份季快照附帶算出
  (`diff_verdict` / `turn_icon`),渲染進「MJ 趨勢 × 轉機」表(轉機欄 + 🌟/⚠️ 摘要 +
  逐檔變好/變差明細)。獨立 `tab_mj_health_diff.py`(自帶第二輸入框 + 重複第二張表)已退役真刪。

本測試釘住「能力還在、且吃單一來源」,避免下一輪稽核把合併後的它誤判為孤兒/遺失。
"""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def test_turnaround_merged_into_stock_grp():
    """『找體質差→變好』轉機能力併進 個股組合 的 MJ 趨勢×轉機表(轉機欄 + 🌟 摘要)。"""
    grp = (_REPO / "src/ui/tabs/tab_stock_grp.py").read_text(encoding="utf-8")
    assert "turn_icon" in grp, "MJ 轉機標記(turn_icon)未渲染進組合(能力遺失風險)"
    assert "'轉機'" in grp or '"轉機"' in grp, "MJ 趨勢表未加『轉機』欄"
    assert "本業虧轉盈" in grp, "缺『本業虧轉盈』轉機摘要(user 要的找體質差→變好)"


def test_trend_score_computes_diff_verdict():
    """合併點:compute_one_stock_trend 用已載入的近 2 季快照附帶算 diff_mj_health(零額外抓取)。"""
    src = (_REPO / "src/compute/health/mj_trend_score.py").read_text(encoding="utf-8")
    assert "diff_verdict" in src, "trend 未回傳 diff_verdict(轉機合併點缺失)"
    assert "diff_mj_health" in src, "trend 未呼叫 diff_mj_health 引擎"


def test_standalone_mj_diff_tab_retired():
    """獨立 tab_mj_health_diff.py(自帶第二輸入框 + 重複第二張表)已退役真刪。"""
    assert not (_REPO / "src/ui/tabs/tab_mj_health_diff.py").exists(), \
        "退役的獨立 MJ 體檢轉機檔案應已刪除(能力已合併進趨勢區塊)"
    app = (_REPO / "app.py").read_text(encoding="utf-8")
    assert "with tab_mj:" not in app, "app.py 殘留獨立 MJ 體檢轉機分頁"


def test_stock_grp_single_ticker_source():
    """v19.164 單一來源:組合不再有蔡森 selectbox / MJ 第二批次輸入,改帶入持股填唯一輸入。"""
    grp = (_REPO / "src/ui/tabs/tab_stock_grp.py").read_text(encoding="utf-8")
    assert "_csgrp_pick" not in grp, "蔡森仍有獨立『選擇標的』selectbox(第二來源未清)"
    assert "_mj_batch_input" not in grp, "MJ 仍有獨立批次輸入框(第三來源未清)"
    assert "_grp_load_holdings_callback" in grp, "帶入持股改填唯一輸入的 callback 缺失"
