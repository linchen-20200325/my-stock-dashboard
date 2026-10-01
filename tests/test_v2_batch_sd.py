"""批 SD（2026-10-01）：畫面字樣的純刪（K1：只刪不改，剩下的句子原文一字未動）。

- W-f5（純刪部分）：估值灰卡 why 尾句「（`CLAUDE.md §1`）」—— 內部文件出處不上畫面。
- W2-f1（3 處純刪）：「按強制重抓／刷新就會重抓」「確保零殘留」這類在冷卻期內不成立的說法。

畫面字串寫在 Streamlit 呼叫裡、無法單獨 import 的那幾處，以原始碼字面斷言（同 repo 既有作法）。
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ── W-f5 ──────────────────────────────────────────────────────────
def test_wf5_valuation_why_tail_has_no_internal_doc_ref():
    from src.ui.views import page_inspect as P
    assert "CLAUDE.md" not in P.VALUATION_WHY_TAIL
    assert P.VALUATION_WHY_TAIL == (
        "　本站**不以 0% 殖利率頂替** —— 0% 會被同一套門檻判成「超貴」，"
        "那是拿缺資料當看空結論"), "只刪尾句括號，其餘一字未動"
