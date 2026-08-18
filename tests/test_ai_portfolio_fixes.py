"""AI 投資組合綜合判讀 稽核修正測試（2026-08）。

- B：共用 prompt 模板 PLAIN_RULES 含「禁止虛構數字/代號」硬規則。
- A：強弱排序段綜合評分取自 score_t3 真分,不再恆印「未評分」與第 1 節自打架。
（E-1 生成後立刻顯示 / E-2 快取 key 含全代號+資料版本 屬 Streamlit runtime 行為,
  由實機驗證;此處測純函式層可驗的 A/B。）
"""
from __future__ import annotations


def test_prompt_template_has_anti_fabrication_rule():
    """B：反捏造硬規則有進到最終 prompt（所有用此模板的 AI 摘要都受惠）。"""
    from src.services.ai_structured_summary import build_structured_summary_prompt
    _p = build_structured_summary_prompt('測試主題', [{'name': '章節', 'data': '數據'}])
    assert '虛構' in _p and '反捏造' in _p
    assert '沒有資料' in _p          # 「資料沒有就說沒有」的指示


def test_ranking_section_uses_real_total_from_score_t3(monkeypatch):
    """A：強弱排序段的「綜合評分」取自 score_t3 真分（82），不再恆印「未評分」。"""
    from src.services import allocation_service
    monkeypatch.setattr(allocation_service, 'get_macro_regime',
                        lambda: {'is_loaded': False, 'regime': 'unknown'})

    class _AllocStub:
        range_text = '--'
    monkeypatch.setattr(allocation_service, 'get_allocation', lambda: _AllocStub())

    from src.ui.tabs.stock_grp_sections.section_ai_portfolio import _build_portfolio_prompt

    _captured: dict = {}

    def _fake_build(*, subject_title, sections, news_text, overall_question):
        _captured['sections'] = sections
        return 'PROMPT'

    results_t3 = [{'stock_id': '2330', 'stock_name': '台積電', '_health': 90,
                   'RSI': '60', '趨勢': '多頭', 'VCP': '⚪', 'foreign_buy': 100}]
    score_t3 = [{'stock_id': '2330', 'total': 82, 'trend': 80, 'momentum': 70,
                 'chip': 60, 'volume': 50, 'risk': 40}]

    _build_portfolio_prompt(
        results_t3=results_t3, score_t3=score_t3, risk_alerts=[],
        fund_map={}, fh_cached={}, fetch_news_fn=lambda *a, **k: '',
        build_prompt_fn=_fake_build)

    _rank_sec = next(s for s in _captured['sections'] if '拖後腿' in s['name'])
    assert '綜合評分=82' in _rank_sec['data']     # 取到 score_t3 真分
    assert '未評分' not in _rank_sec['data']       # 不再自打架


def test_ranking_section_marks_unscored_honestly(monkeypatch):
    """A 反向：score_t3 真的沒這檔 → 誠實標「未評分」（§1 不編分）。"""
    from src.services import allocation_service
    monkeypatch.setattr(allocation_service, 'get_macro_regime',
                        lambda: {'is_loaded': False, 'regime': 'unknown'})

    class _AllocStub:
        range_text = '--'
    monkeypatch.setattr(allocation_service, 'get_allocation', lambda: _AllocStub())

    from src.ui.tabs.stock_grp_sections.section_ai_portfolio import _build_portfolio_prompt
    _captured: dict = {}

    def _fake_build(*, subject_title, sections, news_text, overall_question):
        _captured['sections'] = sections
        return 'PROMPT'

    results_t3 = [{'stock_id': '9999', 'stock_name': '無分股', '_health': 40,
                   'RSI': '-', '趨勢': '-', 'VCP': '⚪', 'foreign_buy': 0}]
    _build_portfolio_prompt(
        results_t3=results_t3, score_t3=[], risk_alerts=[],
        fund_map={}, fh_cached={}, fetch_news_fn=lambda *a, **k: '',
        build_prompt_fn=_fake_build)

    _rank_sec = next(s for s in _captured['sections'] if '拖後腿' in s['name'])
    assert '綜合評分=未評分' in _rank_sec['data']   # 無分誠實標,不捏造
