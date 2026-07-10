"""tests/test_news_scan_button.py — §十一 新聞獨立「掃描新聞」按鈕（v19.73）。

修使用者回報「新聞這邊沒有任何讀取按鈕」：原本新聞 RSS 只在按「🔒 執行 AI 裁決」時
順便抓（且需 Gemini 金鑰）。新增獨立「📰 掃描新聞」鈕：只抓 RSS、免金鑰、不跑 AI，
寫入與 AI 裁決同一 stash key（_macro_news_items）→ 上方「新聞整體狀態」燈號會更新。
"""
from __future__ import annotations

import ast
import pathlib

_F = pathlib.Path(__file__).resolve().parents[1] / "src/ui/tabs/macro/section_news_ai.py"


def test_module_compiles():
    ast.parse(_F.read_text(encoding="utf-8"))


def test_scan_news_button_present():
    src = _F.read_text(encoding="utf-8")
    assert "btn_scan_news" in src, "缺獨立掃新聞按鈕 key"
    assert "📰 掃描新聞" in src, "缺掃新聞按鈕文字"
    # 描述有標「掃新聞免金鑰、AI 才需金鑰」的區分
    assert "免金鑰" in src


def test_scan_handler_fetches_rss_without_gemini():
    src = _F.read_text(encoding="utf-8")
    idx = src.index("if _do_scan_news:")
    # 只取掃新聞 handler 本身（到下一個 AI 裁決 handler 為止）
    handler = src[idx: src.index("if _do_verdict:", idx)]
    # 抓 RSS + 寫入與 AI 裁決同一 stash key（燈號才會更新）
    assert "_fetch_macro_news" in handler
    assert "_macro_news_items" in handler
    # 不呼叫 AI（免金鑰）
    assert "gemini" not in handler.lower()


def test_ai_verdict_button_still_present():
    """不得誤刪既有 AI 裁決 / 清除報告鈕。"""
    src = _F.read_text(encoding="utf-8")
    assert "btn_run_verdict" in src and "🔒 執行 AI 裁決" in src
    assert "btn_clear_verdict" in src
