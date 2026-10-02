"""批 D4（客戶 2026-10-02 審核字句擬稿 `wording_draft_d4_final.md`）—— 逐字守衛。

客戶裁示：39 列字句「採用」（照擬稿欄原文）；B5-13 用前半短版；R1／R2 改標「系統設計」
（沿用既有句型「系統設計之警示線（…）」，⛔ 不造新字）；R9 未修 ⇒ B5-2 ⛔ 不寫分段數字。
本檔只釘「畫面上要顯示的字」，邏輯另有各自的測試。
"""
from __future__ import annotations

import pytest

import shared.macro_buckets as mb

#: B5：16 盞總經燈「門檻出處」（`DangerSpec.source`）。
B5_SOURCES = {
    "health": "紅線 35：有既有常數背書（防禦門檻預設值，手訂未校準）；黃線 50：系統設計之警示線（低於半分轉弱警示）",
    "ndc_signal": "系統設計之警示線（NDC 燈號 9藍-45紅）",
    "m1b_m2_gap": "系統設計之警示線（資金動能交叉慣例）：≥1 黃金交叉／<0 死亡交叉",
    "ism_pmi": "黃線 50／紅線 46：有既有常數背書（統一閾值表；<50 收縮／<46 嚴重收縮）",
    "us_core_cpi": "黃線 3.5%／紅線 4%：有既有常數背書（統一閾值表）",
    # R1：黃線 0% 改標系統設計
    "tw_export": "紅線 -5%：沿用總經基本面否決檢查的出口門檻（台灣出口 YoY 低於 -5%）；黃線 0%：系統設計之警示線（衰退邊界）",
    # R2：紅線 +20% 改標系統設計
    "bias_240": "紅線 +20%：系統設計之警示線（正乖離過熱；負乖離為超賣機會，非危險）；黃線 10%：系統設計之警示線（無單一官方源）",
    "vix": "黃線 22／紅線 30：有既有常數背書（統一閾值表）",
    "us10y": "黃線 4.5%／紅線 5.0%：有既有常數背書（統一閾值表）",
    "dxy": "黃線 105／紅線 110：有既有常數背書（統一閾值表）",
    "adl": "黃線 50%：有既有常數背書（市場廣度中性分界）；紅線 35%：系統設計之警示線（無單一官方源）",
    "fut_net": "黃線 -10,000 口／紅線 -20,000 口：沿用 v4 引擎風險燈的外資期貨門檻（空單超過 1 萬口 黃燈／超過 2 萬口 紅燈）",
    "margin": "紅線 3,400 億（歷史 P95 經驗值）／黃線 2,500 億：有既有常數背書",
    "jingqi": "黃線 60%／紅線 40%：系統設計之警示線（廣度佔比經驗切點，與均線無關）",
    "foreign_net": "黃線 0／紅線 -200 億：系統設計之警示線（外資現貨流向；-200 為軟線）",
    "news_systemic": "≥1 則黃線／≥2 則紅線：系統設計之命中則數規則（判讀規則，非金融閾值）",
}


def test_b5_covers_every_lamp():
    assert set(B5_SOURCES) == {s.key for s in mb.BUCKET_DANGER_SPECS}


@pytest.mark.parametrize("key", sorted(B5_SOURCES))
def test_b5_threshold_source_wording(key):
    assert mb.SPECS_BY_KEY[key].source == B5_SOURCES[key]


@pytest.mark.parametrize("key", sorted(B5_SOURCES))
def test_b5_no_internal_codes_on_screen(key):
    src = mb.SPECS_BY_KEY[key].source
    for code in ("SSOT:", "DESIGN:", "DESIGN(", "MACRO_THRESHOLDS", "_LOTS", "HEALTH_DEFENSE"):
        assert code not in src, (key, src)


def test_b5_2_ndc_writes_no_segment_numbers():
    """R9（NDC 23 分邊界）未修 ⇒ B5-2 ⛔ 不寫分段數字（只留既有的「9藍-45紅」）。"""
    src = mb.SPECS_BY_KEY["ndc_signal"].source
    for seg in ("16", "17", "22", "23", "31", "32", "37", "38"):
        assert seg not in src, src


def test_b5_numbers_follow_the_constants():
    """數字是插值，不是手抄：與 spec 自己的 yellow／red 一致。"""
    for key in ("ism_pmi", "us_core_cpi", "vix", "dxy", "margin", "fut_net"):
        s = mb.SPECS_BY_KEY[key]
        for v in (s.yellow, s.red):
            assert (f"{v:g}" in s.source or f"{v:,.0f}" in s.source
                    or f"{v:.1f}" in s.source), (key, v, s.source)


def test_w_f5_valuation_card_label_is_upstream_note():
    """W-f5：估值卡那一列標籤由「L2 說明」改「上游說明」（同籌碼卡既有字樣），內容原樣。"""
    import inspect as _inspect

    from src.ui.views import page_inspect as PI
    src = _inspect.getsource(PI.build_valuation_card)
    assert '("上游說明", scrub_secrets(val.msg))' in src
    assert "L2 說明" not in src


def test_sa2_f11_scales_card_why_and_summary():
    """SA2-f11：why 原句與摘要列第三段同步改；摘要列每段仍是原句的連續片段。"""
    import inspect as _inspect

    from src.ui.views import page_why as PW
    src = _inspect.getsource(PW.build_scale_card)
    assert "其中一側的門檻已失準" in src
    assert "逐盞原因見「⚠️ 已失準」與這張卡下面的對照表" in src
    assert "discriminative=False`" not in src and "上方的 facts" not in src
    assert "上方的 facts" not in _inspect.getsource(PW)
    assert len("逐盞原因見「⚠️ 已失準」與這張卡下面的對照表") <= 46
