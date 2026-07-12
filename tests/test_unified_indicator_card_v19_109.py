# -*- coding: utf-8 -*-
"""v19.109 — 統一指標卡試點(第 5 步,總經拼圖模組八 5 卡)回歸鎖。

核心不變量:band 表 = 判定邏輯 = 燈義文字 = 門檻帶說明的**同一來源**,
任何一邊改動測試即紅(§3.3 反漂移)。

三個最容易出錯的輸入(§6):
1. band 邊界值(恰等於 lo)→ 取該帶(≥ 語意,v19.109 已記錄邊界語意變更)
2. 值非數('N/A')→ gray 資料異常,不炸不腦補方向
3. band 表無 -inf 兜底 → resolver 回 gray(防未來新表漏兜底)
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _src(rel: str) -> str:
    return (REPO / rel).read_text(encoding='utf-8')


# ═════════════════════════════════════════════════════════════════
# band 表 SSOT:鎖定與 legacy inline 完全同值(零行為位移)
# ═════════════════════════════════════════════════════════════════
def test_band_tables_lock_legacy_thresholds():
    from shared.signal_thresholds import (
        FED_FUNDS_RATE_BANDS, NDC_SIGNAL_BANDS, TW_EXPORT_YOY_BANDS,
        TW_PMI_CARD_BANDS, US_CORE_CPI_YOY_BANDS,
    )
    assert [b[0] for b in NDC_SIGNAL_BANDS][:4] == [38.0, 32.0, 23.0, 17.0]
    assert [b[0] for b in TW_EXPORT_YOY_BANDS][:2] == [0.0, -5.0]
    assert [b[0] for b in TW_PMI_CARD_BANDS][:2] == [50.0, 47.0]
    assert [b[0] for b in US_CORE_CPI_YOY_BANDS][:2] == [3.5, 2.5]
    assert [b[0] for b in FED_FUNDS_RATE_BANDS][:2] == [5.0, 3.0]
    for _tbl in (NDC_SIGNAL_BANDS, TW_EXPORT_YOY_BANDS, TW_PMI_CARD_BANDS,
                 US_CORE_CPI_YOY_BANDS, FED_FUNDS_RATE_BANDS):
        assert _tbl[-1][0] == float('-inf'), '每表末項必須 -inf 兜底'
        assert all(len(b) == 4 for b in _tbl), '(lo, 色鍵, 燈標籤, 燈義) 四元組'


# ═════════════════════════════════════════════════════════════════
# resolve_band
# ═════════════════════════════════════════════════════════════════
class TestResolveBand:
    def test_ndc_five_levels(self):
        from shared.signal_thresholds import NDC_SIGNAL_BANDS
        from src.ui.render.macro_ui_components import resolve_band
        assert resolve_band(40, NDC_SIGNAL_BANDS)[0] == 'red'
        assert resolve_band(38, NDC_SIGNAL_BANDS)[0] == 'red'      # 邊界含
        assert resolve_band(33, NDC_SIGNAL_BANDS)[0] == 'yellow'
        assert resolve_band(25, NDC_SIGNAL_BANDS)[0] == 'green'
        assert resolve_band(18, NDC_SIGNAL_BANDS)[1] == '🔵 黃藍燈 趨緩'
        assert resolve_band(10, NDC_SIGNAL_BANDS)[1] == '🔵 藍燈 衰退'

    def test_pmi_and_meaning_from_same_table(self):
        from shared.signal_thresholds import TW_PMI_CARD_BANDS
        from src.ui.render.macro_ui_components import resolve_band
        _ck, _label, _meaning = resolve_band(44.0, TW_PMI_CARD_BANDS)
        assert _ck == 'red' and '嚴重收縮' in _label
        assert _meaning == TW_PMI_CARD_BANDS[-1][3], '燈義必須出自同一 band 表'

    def test_garbage_value_gray_not_crash(self):
        from shared.signal_thresholds import NDC_SIGNAL_BANDS
        from src.ui.render.macro_ui_components import resolve_band
        assert resolve_band('N/A', NDC_SIGNAL_BANDS)[0] == 'gray'
        assert resolve_band(None, NDC_SIGNAL_BANDS)[0] == 'gray'

    def test_table_without_catchall_returns_gray(self):
        from src.ui.render.macro_ui_components import resolve_band
        _no_catchall = [(50.0, 'green', '✅', 'x')]
        assert resolve_band(10.0, _no_catchall)[0] == 'gray'


# ═════════════════════════════════════════════════════════════════
# bands_caption + 卡片 HTML
# ═════════════════════════════════════════════════════════════════
class TestCardRender:
    def test_caption_mirrors_thresholds(self):
        from shared.signal_thresholds import NDC_SIGNAL_BANDS
        from src.ui.render.macro_ui_components import bands_caption
        cap = bands_caption(NDC_SIGNAL_BANDS, '分')
        assert '≥38分' in cap and '≥17分' in cap and '<17分' in cap, (
            '門檻帶說明必須逐項反映 band 表(同源防漂移)')

    def test_unified_card_four_elements(self):
        from shared.signal_thresholds import TW_PMI_CARD_BANDS
        from src.ui.render.macro_ui_components import (
            resolve_band, unified_indicator_card,
        )
        html = unified_indicator_card(
            title='🇹🇼 台灣 PMI', nickname='製造業景氣問卷',
            value_str='48.2',
            band=resolve_band(48.2, TW_PMI_CARD_BANDS), bands=TW_PMI_CARD_BANDS,
            principle='CIER 調查,50 榮枯線', date='2026-06',
        )
        assert '製造業景氣問卷' in html          # 俗名
        assert '燈義：' in html and '輕微收縮' in html   # 燈義(來自 band 表)
        assert '原理：' in html and '50 榮枯線' in html  # 原理
        assert '門檻帶：' in html and '≥50' in html      # 門檻帶(同源)
        assert '(2026-06)' in html

    def test_pending_card_honest(self):
        from src.ui.render.macro_ui_components import (
            unified_indicator_card_pending,
        )
        html = unified_indicator_card_pending(
            title='NDC 景氣燈號', nickname='台灣景氣紅綠燈',
            principle='國發會 9 項指標合成', source_note='來源備註')
        assert '待取得' in html and '台灣景氣紅綠燈' in html
        assert '原理：' in html and '來源備註' in html


# ═════════════════════════════════════════════════════════════════
# section_mid 接線:magic number 收斂 + 5 卡全走統一卡
# ═════════════════════════════════════════════════════════════════
def test_section_mid_rewired_no_inline_thresholds():
    text = _src('src/ui/tabs/macro/section_mid.py')
    assert text.count('unified_indicator_card(') == 5, '5 張資料卡全走統一卡'
    assert text.count('unified_indicator_card_pending(') == 5, '5 張待取得態同構'
    for _legacy in ('_sc8 >= 38', "_ey8 > 0 else TRAFFIC_RED", '_pmi_榮枯',
                    '_cy8 > 3.5', '_fc >= 5.0'):
        assert _legacy not in text, (
            f'legacy inline 門檻「{_legacy}」不得殘留(已收 band SSOT,§3.3)')
