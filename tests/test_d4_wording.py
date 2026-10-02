"""批 D4（客戶 2026-10-02 審核字句擬稿 `wording_draft_d4_final.md`）—— 逐字守衛。

客戶裁示：39 列字句「採用」（照擬稿欄原文）；B5-13 用前半短版；R1／R2 改標「系統設計」
（沿用既有句型「系統設計之警示線（…）」，⛔ 不造新字）；R9 未修 ⇒ B5-2 ⛔ 不寫分段數字。
本檔只釘「畫面上要顯示的字」，邏輯另有各自的測試。
"""
from __future__ import annotations

import pandas as pd
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


def _m1b_readiness(gap):
    from src.compute.macro.macro_helpers import compute_five_bucket_summary
    rd: dict = {}
    compute_five_bucket_summary(
        m1b_m2_info={"m1b_yoy": 3.0, "m2_yoy": 1.0, "gap": gap, "source": "CBC-tier1"},
        readiness_out=rd)
    return rd["m1b_m2_gap"]


@pytest.mark.parametrize("gap", [float("inf"), float("-inf"), float("nan")])
def test_nf_f2_non_finite_rejection_says_non_finite(gap, capsys):
    """NF-f2 ①②：非有限值被擋時，標註與 log 說「非有限值(NaN / ±inf)」，⛔ 不再說超出範圍。"""
    r = _m1b_readiness(gap)
    assert r["rejected"][0][2] == "非有限值(NaN / ±inf)"
    out = capsys.readouterr().out
    assert "非有限值(NaN / ±inf) → 跳過此源(§3.2)。" in out
    assert "超出合理範圍" not in out


def test_dl_f1_s67_m1b_hit_source_chain_order():
    from src.compute.macro import macro_helpers as MH
    import inspect as _inspect
    src = _inspect.getsource(MH.compute_five_bucket_summary)
    assert "m1b_m2_info.gap (CBC ms1 → EF15M01 → ^TWII proxy → FRED → IMF)" in src
    assert "CBC ms1 → FRED → IMF → ^TWII proxy" not in src


def _coverage_macro_detail(us10y_close):
    import streamlit as st

    from src.ui.pages.data_coverage import compute_tab_coverage
    _ss = {"macro_info": {"vix": {"current": 17.2}, "_loaded_at": "2026-08-20T01:00"},
           "cl_data": {"intl": {"10Y公債殖利率": pd.DataFrame({"close": [us10y_close]})}}}
    for k, v in _ss.items():
        st.session_state[k] = v
    try:
        return [r for r in compute_tab_coverage() if "總經" in r["tab"]][0]["detail"]
    finally:
        for k in _ss:
            st.session_state.pop(k, None)


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
def test_c1_non_finite_grouped_as_upstream_no_value(bad):
    """C1 = A：資料診斷頁裡，被擋的值全是非有限值 ⇒ 歸「📵 上游無值」，⛔ 不再進「📐 量綱異常」。"""
    detail = _coverage_macro_detail(bad)
    import re as _re
    no_val = _re.search(r"📵 上游無值\(\d+\):([^ ]+)", detail)
    assert no_val and "us10y" in no_val.group(1).split("/"), detail
    assert "📐 量綱異常" not in detail, detail
    assert "非有限值(NaN / ±inf)" in detail  # NF-f2 ②：逐筆標註仍在


def test_c1_finite_out_of_range_still_dimension_anomaly():
    detail = _coverage_macro_detail(46.3)
    assert "📐 量綱異常(1):us10y" in detail, detail
    assert "46.3" in detail
