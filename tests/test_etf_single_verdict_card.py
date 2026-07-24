"""tests/test_etf_single_verdict_card.py — v19.166 守衛:ETF 單檔 🚦 綜合研判卡。

單檔頁原本 verdict 散在多張老師卡、無單一「留/觀察/換」結論。此卡置頂,沿用「單檔/多檔
共用 row SSOT」build_etf_score_row + recommend_etf_action(與多檔同引擎),§8.1 餵 render
已抓的 df/divs/info 不重抓。本測試釘住「有掛 + 走共用 SSOT + 缺料不腦補」。
"""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def test_single_tab_mounts_verdict_card():
    src = (_REPO / "src/ui/etf/etf_tab_single.py").read_text(encoding="utf-8")
    assert "recommend_etf_action" in src, "單檔頁未接留/觀察/換研判"
    assert "build_etf_score_row" in src, "研判卡未用共用 row SSOT(疑似重算/重抓)"
    assert "綜合研判" in src, "研判卡標題缺失"


def test_recommend_etf_action_single_usable_and_honest():
    """recommend_etf_action 單檔可用;缺 composite / error → 不腦補(觀察 / 資料不足)。"""
    from src.compute.etf import recommend_etf_action
    r_missing = recommend_etf_action({'composite': None})
    assert '觀察' in r_missing['verdict'] and r_missing['reasons']
    r_err = recommend_etf_action({'error': '抓取失敗'})
    assert r_err['reasons'] and 'icon' in r_err
