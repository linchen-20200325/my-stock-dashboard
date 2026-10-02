"""批 W1（客戶 2026-10-02「R7 審稿：18 句全採用，S1～S5 暫緩」）：16 盞總經燈「命中來源」白話句逐字釘。

R7-3 另依同日決策「取數順序字句：授權調序」把「大盤動能代理估算」（^TWII 動能代理）移到最後，
與 D3 #779 後 `fetch_m1b_m2_block` 的實際順序（CBC → FRED → IMF → ^TWII 代理）一致。
只換字串；取值 / 範圍守衛 / 燈號邏輯不變。
"""
from __future__ import annotations

import inspect

import pandas as pd
import pytest

from shared.signal_thresholds import HEALTH_WEIGHT_JQ, HEALTH_WEIGHT_SCORE
from src.compute.macro import macro_helpers as MH

# (燈號 key, R7 編號, 擬稿逐字) —— R7-8a / R7-8b 同句，故 us10y 出現兩次。
R7_LABELS = [
    ("ndc_signal", "R7-2", "國發會景氣對策信號，依序：FinMind（國發會官方鏡像）→ data.gov.tw 官方「景氣指標及燈號」→ StockFeel 股感 → MacroMicro 財經 M 平方"),
    ("m1b_m2_gap", "R7-3", "M1B 年增率減 M2 年增率，依序：央行公開 JSON → 央行 EF15M01 → FRED → IMF → 大盤動能代理估算"),
    ("ism_pmi", "R7-4", "台灣製造業 PMI（中華經濟研究院 CIER 等 8 源並行，依優先序取第一個有效值；全敗時沿用 90 天內舊值）"),
    ("us_core_cpi", "R7-5", "美國核心 CPI 年增率，依序：FRED 公開檔（無需 key）→ FRED API → BLS 備援"),
    ("tw_export", "R7-6", "財政部海關出口金額年增率，依序：中華民國統計資訊網 → FRED（OECD）→ 海關出口統計 → FRED → 財政部進出口統計"),
    ("bias_240", "R7-7", "計算值：加權指數（Yahoo）對年線的乖離；不足 240 天時改抓 2 年補，仍不足則標「（估算）」"),
    ("us10y", "R7-8a", "FRED 美 10 年期殖利率"),
    ("us10y", "R7-8b", "FRED 美 10 年期殖利率"),
    ("us10y", "R7-8c", "Yahoo 美債 10Y 殖利率（FRED 抓不到時的備援）"),
    ("dxy", "R7-9", "Yahoo 美元指數 → 美元指數期貨（ETF 備援尺度不同，一律擋下不用）"),
    ("vix", "R7-10", "Yahoo VIX 日線（主源，無備援）"),
    ("adl", "R7-11", "估算值：由加權指數（Yahoo）漲跌幅反推上漲家數，非真實統計"),
    ("fut_net", "R7-12", "FinMind 期貨法人資料：外資大台淨口 ＋ 小台淨口 × 0.25（大台當量口數；純 FinMind）"),
    ("margin", "R7-13", "全市場融資餘額（億元），依序：FinMind → 證交所 → HiStock → Goodinfo → Yahoo 股市 → 鉅亨網"),
    ("jingqi", "R7-14", "計算值：ADL 上漲佔比的 5 日平均（ADL 本身是大盤估算）；ADL 缺時改用近 5 日大盤上漲天數估算；舊總經分頁另可能以證交所即時單日上漲佔比頂替（非 5 日均）"),
    ("foreign_net", "R7-15", "外資及陸資現貨淨買賣（億元），依序：證交所三大法人表 → FinMind 三大法人合計"),
    ("news_systemic", "R7-16", "財經新聞 RSS（中央社財經、經濟日報、Google News 中英、Yahoo Finance、CNBC）取 5 則，標題＋摘要命中系統性風險關鍵字（戰爭／倒閉／崩盤等）的則數"),
]

OLD_LABELS = [
    "warroom_summary.health_score (calc_traffic_light)",
    "macro_info.ndc_signal.score (FinMind TaiwanBusinessIndicator)",
    "m1b_m2_info.gap (CBC ms1 → EF15M01 → ^TWII proxy → FRED → IMF)",
    "macro_info.ism_pmi.value (PMI_SOURCE_REGISTRY 多源賽跑)",
    "macro_info.us_core_cpi.yoy (FRED CPILFESL)",
    "macro_info.tw_export.yoy (MOF 進出口)",
    "bias_info.bias_240 (compute_twii_bias ← ^TWII)",
    "FRED:DGS10(macro_info)",
    "FRED:DGS10(macro_info.value)",
    "Yahoo:^TNX(cl_data.intl)",
    "Yahoo:DX-Y.NYB(cl_data.intl)",
    "macro_info.vix.current (Yahoo ^VIX → FRED VIXCLS)",
    "cl_data.adl[ad_ratio] (fetch_adl ← ^TWII 估算)",
    "li_latest[外資大小] (FinMind 期貨 + TAIFEX)",
    "cl_data.margin (TWSE → HiStock → Wearn)",
    "jingqi_info.avg (ad_ratio 5 日均)",
    "cl_data.inst[外資及陸資].net 億 (TWSE BFI82U → FinMind TotalInstitutional)",
    "_macro_news_items (RSS 系統性風險掃描)",
]


def _src() -> str:
    return inspect.getsource(MH.compute_five_bucket_summary)


def test_r7_count_is_18():
    assert len(R7_LABELS) + 1 == 18  # + R7-1（插值句，另測）


@pytest.mark.parametrize("key,rid,label", R7_LABELS, ids=[r[1] for r in R7_LABELS])
def test_r7_label_in_source(key, rid, label):
    assert f'"{label}"' in _src(), rid


def test_r7_1_health_weights_interpolated_not_hardcoded():
    src = _src()
    assert ('f"計算值：旌旗指數（上漲佔比 5 日均）{HEALTH_WEIGHT_JQ * 100:g}% ＋ '
            '大盤評分 {HEALTH_WEIGHT_SCORE * 100:g}%"') in src


@pytest.mark.parametrize("old", OLD_LABELS)
def test_old_labels_gone(old):
    assert old not in _src(), old


def _rd(**kw):
    rd: dict = {}
    MH.compute_five_bucket_summary(readiness_out=rd, **kw)
    return rd


def test_r7_1_rendered_hit():
    rd = _rd(warroom_summary={"health_score": 55.0})
    want = (f"計算值：旌旗指數（上漲佔比 5 日均）{HEALTH_WEIGHT_JQ * 100:g}% ＋ "
            f"大盤評分 {HEALTH_WEIGHT_SCORE * 100:g}%")
    assert rd["health"]["hit_source"] == want


def test_r7_3_runtime_hit_lists_twii_proxy_last():
    rd = _rd(m1b_m2_info={"m1b_yoy": 3.0, "m2_yoy": 1.0, "gap": 2.0, "source": "CBC-tier1"})
    hit = rd["m1b_m2_gap"]["hit_source"]
    assert hit == R7_LABELS[1][2]
    assert hit.endswith("→ 大盤動能代理估算")


def test_r7_8c_us10y_falls_back_to_yahoo_label():
    rd = _rd(cl_data={"intl": {"10Y公債殖利率": pd.DataFrame({"close": [4.2]})}})
    assert rd["us10y"]["hit_source"] == "Yahoo 美債 10Y 殖利率（FRED 抓不到時的備援）"
    assert rd["us10y"]["candidates"] == [
        "FRED 美 10 年期殖利率", "FRED 美 10 年期殖利率",
        "Yahoo 美債 10Y 殖利率（FRED 抓不到時的備援）"]
