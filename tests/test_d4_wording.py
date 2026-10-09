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
    # 批 Z18 追加（客戶 2026-10-09 裁示「採最簡版說明」）：health／tw_export／fut_net 三句括號內字改最簡版。
    "health": "紅線 35：有既有常數背書（防禦門檻預設值，手訂未校準）；黃線 50：系統設計之警示線（≤50 轉弱警示）",
    "ndc_signal": "系統設計之警示線（NDC 燈號 9藍-45紅）",
    # 批 Z18（客戶 2026-10-09 Q-r15a 裁示「1：A」）：符號依實際判燈邊界修正（≥1→>1、<0→≤0）。
    "m1b_m2_gap": "系統設計之警示線（資金動能交叉慣例）：>1 黃金交叉／≤0 死亡交叉",
    "ism_pmi": "黃線 50／紅線 46：有既有常數背書（統一閾值表；<50 收縮／<46 嚴重收縮）",
    "us_core_cpi": "黃線 3.5%／紅線 4%：有既有常數背書（統一閾值表）",
    # R1：黃線 0% 改標系統設計
    "tw_export": "紅線 -5%：沿用總經基本面否決檢查的出口門檻（台灣出口 YoY -5%）；黃線 0%：系統設計之警示線（衰退邊界）",
    # R2：紅線 +20% 改標系統設計
    "bias_240": "紅線 +20%：系統設計之警示線（正乖離過熱；負乖離為超賣機會，非危險）；黃線 10%：系統設計之警示線（無單一官方源）",
    "vix": "黃線 22／紅線 30：有既有常數背書（統一閾值表）",
    "us10y": "黃線 4.5%／紅線 5.0%：有既有常數背書（統一閾值表）",
    "dxy": "黃線 105／紅線 110：有既有常數背書（統一閾值表）",
    "adl": "黃線 50%：有既有常數背書（市場廣度中性分界）；紅線 35%：系統設計之警示線（無單一官方源）",
    "fut_net": "黃線 -10,000 口／紅線 -20,000 口：沿用 v4 引擎風險燈的外資期貨門檻（空單 1 萬口 黃燈／2 萬口 紅燈）",
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
    # 📌 批 Z4（2026-10-05）：R9 已修（yellow_lo 23→22，見 tests/test_batch_z4.py）；
    #    「B5-2 不寫分段數字」照舊有效（客戶 10-02 裁示），本守衛一字不改。
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
    # 批 W1（客戶 2026-10-02）：R7-3 取代本句，且「^TWII 動能代理」移到最後（逐字釘於 test_w1_r7_hit_source.py）。
    assert "M1B 年增率減 M2 年增率，依序：央行公開 JSON → 央行 EF15M01 → FRED → IMF → 大盤動能代理估算" in src
    assert "m1b_m2_info.gap (CBC ms1 → EF15M01 → ^TWII proxy → FRED → IMF)" not in src
    assert "CBC ms1 → FRED → IMF → ^TWII proxy" not in src


def _coverage_macro_detail(us10y_close, us10y_macro=None):
    import streamlit as st

    from src.ui.pages.data_coverage import compute_tab_coverage
    _mi = {"vix": {"current": 17.2}, "_loaded_at": "2026-08-20T01:00"}
    if us10y_macro is not None:
        _mi["us10y"] = {"current": us10y_macro}
    _ss = {"macro_info": _mi,
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


def test_dl_f1_s14_edu_source_table_and_m1b_card():
    """DL-f1-s14 ①～⑦：說明書資料源表 M1B／中國拖累兩列＋M1B 說明卡「資料源」行。"""
    import inspect as _inspect

    from shared import fred_series as F
    from src.ui.tabs import tab_edu as E
    src = _inspect.getsource(E)
    for want in ("'CBC ms1.json → EF15M01（央行）'",
                 "'月後 ~27 天,1hr cache'",
                 "'CBC ms1.json → EF15M01 → FRED → IMF（USD,僅 fallback,禁跨幣別平均） → ^TWII 動能代理'",
                 "'月頻,30min cache'",
                 "'全敗 → ⬜ 中國資料不足'",
                 "**資料源**:央行 CBC ms1.json → EF15M01 月公布（月後 ~27 天）,備援 FRED → IMF → ^TWII 動能代理。"):
        assert want in src, want
    china = (f"FRED（{F.FRED_USDCNY} / {F.FRED_CHN_OECD_CLI} / {F.FRED_CHN_CPI} / "
             f"{F.FRED_CHN_M2} / {F.FRED_CHN_PMI}）")
    assert f"'{china}'" in src
    for gone in ("CNCPIALLMINMEI", "90 天 cache", "modifier = 1.0 中性", "月後 ~5-7 天",
                 "EF15M01 → ^TWII 動能代理 → FRED", "備援 ^TWII 動能代理 → FRED"):  # 批 W1 調序
        assert gone not in src, gone


def test_dl_f1_s14_health_inspector_m1b_source_and_endpoint():
    """DL-f1-s14 ⑧⑨：健診 M1B 列「來源」×3、「端點」×2 對齊 5 段取數鏈（M1B 路徑沒有 FinMind）。"""
    import inspect as _inspect

    from src.ui.pages import health_inspector as H
    src = _inspect.getsource(H)
    # 批 W1（客戶 2026-10-02）：只把「^TWII 動能代理」移到最後。
    assert src.count("'CBC ms1.json+EF15M01+FRED+IMF+^TWII 動能代理 5段'") == 3
    assert "EF15M01+^TWII 動能代理+FRED" not in src
    # 客戶 2026-10-03：端點字串只把「Yahoo」移到最後（只調詞序，不加新字）。
    assert src.count("'cbc.gov.tw / cpx.cbc.gov.tw / FRED / IMF DataMapper / Yahoo'") == 2
    assert "cpx.cbc.gov.tw / Yahoo / FRED" not in src
    assert "CBC + FinMind 雙源" not in src and "TaiwanStockMonetaryAggregates" not in src


def test_dl_f1_s66_system_cap_basis_wording():
    """DL-f1-s66：持股頁「推導依據」的系統風險上限說明列出分數因子與三大硬否決紅線。"""
    from shared.allocation_decision import build_allocation_decision
    import inspect as _inspect
    src = _inspect.getsource(build_allocation_decision)
    assert ("'macro_state 規則引擎（分數計算：VIX／PMI／M1B-M2／BIAS240／PCR；"
            "三大硬否決紅線：薩姆／PMI／外資期貨）'") in src
    assert "外資期貨硬否決）" not in src


def test_w2_f1_etf_force_refresh_help():
    """W2-f1：按鈕只清全站快取再重跑，⛔ 不保證抓到最新 ⇒ 說明不再寫「重新抓取最新現價與配息」。"""
    import inspect as _inspect

    from src.ui.etf import etf_tab_portfolio as T
    src = _inspect.getsource(T)
    assert "help='清快取（不需重填表格），會一併清掉其他頁快取'" in src
    assert "重新抓取最新現價與配息" not in src


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_c1_mixed_non_finite_and_finite_out_of_range_stays_dimension_anomaly(bad):
    """C1 只在「被擋的值**全是**非有限值」時改組；混有一筆有限值超範圍 ⇒ 仍是量綱問題。"""
    from src.compute.macro.macro_helpers import compute_five_bucket_summary
    rd: dict = {}
    compute_five_bucket_summary(
        macro_info={"us10y": {"current": bad}},
        cl_data={"intl": {"10Y公債殖利率": pd.DataFrame({"close": [46.3]})}},
        readiness_out=rd)
    _whys = [x[2] for x in rd["us10y"]["rejected"]]
    assert "非有限值(NaN / ±inf)" in _whys and any(w.startswith("out_of_range") for w in _whys), _whys
    detail = _coverage_macro_detail(46.3, us10y_macro=bad)
    assert "📐 量綱異常(1):us10y" in detail, detail
    assert "📵 上游無值" not in detail or "us10y" not in detail.split("📵 上游無值")[1].split("→")[0], detail
