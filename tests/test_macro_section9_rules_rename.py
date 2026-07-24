"""tests/test_macro_section9_rules_rename.py — §九 去 AI 標籤正名守衛(v19.168)。

背景:§九 section_cross_ai 是**純 if/else 規則引擎(零 LLM、免金鑰、離線可用)**,卻長期
掛「總經 AI 投資決策」標題 + 被歸進「AI 綜合」桶群,是全 App 最誤導的標籤(使用者以為
它是黑箱 AI,其實是最該信任的確定性決策)。v19.168 正名:
- §九 標題去「AI」、改「規則決策(離線可用)」,並 emit 自己的 'rules' 桶群 banner。
- §十一(新聞 AI 總裁決,真 Gemini)改自行 emit 'ai' 桶群 banner(原由 §九 共用 emit)。

本測試釘住正名不得回退,且 banner 歸屬正確。純 source-scan + L0 純函式,無需 AppTest。
"""
from __future__ import annotations

from pathlib import Path

from shared.macro_buckets import BUCKET_GROUP_COLOR, bucket_group_banner_html

_ROOT = Path(__file__).resolve().parents[1]
_CROSS_AI = (_ROOT / "src/ui/tabs/macro/section_cross_ai.py").read_text(encoding="utf-8")
_NEWS_AI = (_ROOT / "src/ui/tabs/macro/section_news_ai.py").read_text(encoding="utf-8")


# ── L0:新「規則決策」桶群 banner ────────────────────────────────
def test_rules_group_banner_renders():
    h = bucket_group_banner_html("rules", 0)
    assert "linear-gradient" in h
    assert BUCKET_GROUP_COLOR["rules"] in h
    assert "🧭" in h
    assert "規則決策" in h
    assert "規則" in h            # badge 用「規則」非「桶 N/5」
    assert "桶 0/5" not in h


def test_ai_group_still_intact():
    """'ai' 桶群 banner 契約不變(title/badge)——§十一 仍用它。"""
    h = bucket_group_banner_html("ai", 6)
    assert "AI 綜合決策" in h and "綜合" in h


# ── §九:標題去 AI、改規則決策、emit 'rules' banner ───────────────
def test_section9_title_dropped_ai_label():
    """§九 標題不得再出現「AI 投資決策」(誤導字串),須改「規則決策」。"""
    assert "AI 投資決策" not in _CROSS_AI, "§九 仍殘留誤導的『AI 投資決策』標題"
    assert "規則決策" in _CROSS_AI


def test_section9_emits_rules_banner_not_ai():
    """§九 emit 自己的 'rules' 桶群 banner,不再 emit 'ai'。"""
    assert "_bgb('rules'" in _CROSS_AI, "§九 未 emit 'rules' 桶群 banner"
    assert "_bgb('ai'" not in _CROSS_AI, "§九 不應再 emit 'ai' banner(已移出 AI 桶)"


# ── §十一:接手 emit 'ai' banner ─────────────────────────────────
def test_section11_now_emits_ai_banner():
    """§九 移出後,§十一(真 Gemini)須自行 emit 'ai' 桶群 banner。"""
    assert "_bgb('ai'" in _NEWS_AI, "§十一 未接手 emit 'ai' banner(桶群會消失)"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
