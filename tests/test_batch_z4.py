"""批 Z4（2026-10-05）—— R9 釘子。

R9（L0）：NDC 景氣對策燈號 23 分「程式判黃、文件寫綠」（客戶 2026-10-02 定性為程式 bug）。
修法：`shared/macro_buckets.py::BUCKET_DANGER_SPECS['ndc_signal']` 的 `yellow_lo` 23.0 → 22.0。
要求：9～45 每個整數都與 `shared/signal_thresholds.NDC_SIGNAL_BANDS` 的色系一致
（≤16 紅／17～22 黃／23～31 綠／32～37 黃／≥38 紅）；門檻字出現「黃 ≤22」；只動數字、不改任何字。
本檔另逐一釘住受影響的消費端（v1 五桶 / v2 今天頁 / v2 總經頁 / 資料體檢頁門檻字 /
教學卡線位 / AI prompt 門檻句 / 超標幅度 / 長期桶主因選擇）。
"""
from __future__ import annotations

import math

import plotly.graph_objects as go
import pytest

from shared.macro_buckets import SPECS_BY_KEY, classify_danger, danger_exceedance
from shared.signal_thresholds import NDC_SIGNAL_BANDS

NDC = SPECS_BY_KEY["ndc_signal"]

# ══════════════════════════════════════════════════════════════════
# R9 —— NDC 低側黃線 23 → 22
# ══════════════════════════════════════════════════════════════════

#: NDC 官方分數帶的燈名 → 危險度三色。**以燈名對映、⛔ 不以列序對映**：
#: 表裡 17~22（黃藍燈）與 ≤16（藍燈）的色鍵同為 'blue'，只有燈名分得開。
_OFFICIAL_TO_DANGER = {
    "🔴 紅燈 過熱": "red",
    "🟡 黃紅燈 繁榮": "yellow",
    "🟢 綠燈 穩定": "green",
    "🔵 黃藍燈 趨緩": "yellow",
    "🔵 藍燈 衰退": "red",
}


def _official_level(score: int) -> str:
    """依 `NDC_SIGNAL_BANDS`（降冪 lo、首個 `score >= lo` 命中）推該分數的危險度色系。"""
    for _lo, _color, _label, _meaning in NDC_SIGNAL_BANDS:
        if score >= _lo:
            return _OFFICIAL_TO_DANGER[_label]
    raise AssertionError(f"NDC_SIGNAL_BANDS 沒有兜底項，{score} 落空")


class TestR9NdcBoundary:
    def test_official_band_table_covers_every_label(self):
        """對映表與官方表同一組燈名 —— 官方表改了燈名，本測試先紅（⛔ 靜默失效）。"""
        assert {_lbl for _lo, _c, _lbl, _m in NDC_SIGNAL_BANDS} == set(_OFFICIAL_TO_DANGER)

    @pytest.mark.parametrize("score", range(9, 46))
    def test_every_integer_score_matches_official_bands(self, score):
        assert classify_danger(score, NDC) == _official_level(score), score

    @pytest.mark.parametrize("score,expected", [
        (16, "red"), (17, "yellow"), (22, "yellow"), (23, "green"),
        (31, "green"), (32, "yellow"), (37, "yellow"), (38, "red"),
    ])
    def test_named_boundaries(self, score, expected):
        assert classify_danger(score, NDC) == expected
        assert classify_danger(float(score), NDC) == expected

    def test_only_the_number_changed(self):
        """只動 `yellow_lo`；其餘欄位與畫面上的字（note／source＝B5-2）一字未動。"""
        assert NDC.yellow_lo == 22.0
        assert (NDC.yellow, NDC.red, NDC.red_lo) == (32.0, 38.0, 16.0)
        assert (NDC.direction, NDC.unit, NDC.decimals, NDC.bucket) == ("band", "分", 0, "long")
        assert NDC.label == "NDC 景氣對策燈號"
        assert NDC.note == "9-16 藍衰退 / 23-31 綠穩定 / 38+ 紅過熱"
        assert NDC.source == "系統設計之警示線（NDC 燈號 9藍-45紅）"
        for seg in ("16", "17", "22", "23", "31", "32", "37", "38"):   # B5-2 ⛔ 不寫分段數字
            assert seg not in NDC.source

    def test_v2_threshold_text_says_yellow_le_22(self):
        """門檻字（v2 今天頁「門檻帶」/ v2 總經頁「門檻帶」同一支）出現「黃 ≤22」。"""
        from src.ui.render.macro_v2_cards import threshold_text
        txt = threshold_text(NDC)
        assert txt == "紅 ≤16 / 黃 ≤22　黃 ≥32 / 紅 ≥38"
        assert "黃 ≤22" in txt and "黃 ≤23" not in txt


class TestR9Consumers:
    """逐一釘住讀 `yellow_lo` 的消費端（數字全由 SSOT 推，本檔不手抄門檻）。"""

    def test_why_page_threshold_text(self):
        from src.ui.views import page_why as PW
        assert PW._macro_threshold_text(NDC) == "黃線 32分 · 紅線 38分 · 低側黃線 22分 · 低側紅線 16分"

    def test_edu_card_lower_line_is_22(self):
        """教學卡 sparkline 的兩條線＝綠燈區間上下緣（高側黃線, 低側黃線）。"""
        from src.ui.tabs.tab_edu import edu_threshold_lines
        assert edu_threshold_lines("NDC_signal") == (32.0, 22.0, None)

    def test_ai_prompt_rule_text(self):
        from src.services.ai_structured_summary import danger_rule_text
        assert danger_rule_text("ndc_signal") == (
            "畫面燈號同一套門檻：≥32分 或 ≤22分 🟡 警戒；≥38分 或 ≤16分 🔴 危險")

    def test_v1_danger_hlines(self):
        from src.ui.tabs.macro.helpers import add_danger_hlines
        fig = go.Figure()
        add_danger_hlines(fig, "ndc_signal")
        got = sorted((_s.y0, _a.text) for _s, _a in zip(fig.layout.shapes, fig.layout.annotations))
        assert got == [(16.0, "🔴 紅線 16分"), (22.0, "🟡 黃線 22分"),
                       (32.0, "🟡 黃線 32分"), (38.0, "🔴 紅線 38分")]

    def test_v2_chart_threshold_lines(self):
        from src.ui.render import macro_v2_cards as MV
        f1 = go.Figure()
        MV._threshold_lines(f1, NDC)
        f2 = go.Figure()
        MV._threshold_lines_ssot(f2, NDC, yref="y", side=MV._THR_SIDE_LEFT)
        for fig in (f1, f2):
            assert "黃線(下) 22" in {_a.text for _a in fig.layout.annotations}

    @pytest.mark.parametrize("score,level,expected", [
        (22, "yellow", 0.0),            # 恰在黃線上
        (20, "yellow", 2 / 6),          # (22-20)/6
        (17, "yellow", 5 / 6),
        (16, "red", 0.0),
        (9, "red", 7 / 6),              # (16-9)/6
        (44, "red", 1.0),               # 高側不受影響：(44-38)/6
    ])
    def test_low_side_exceedance_uses_band_width_6(self, score, level, expected):
        """低側黃→紅帶寬 7（23−16）→ 6（22−16），有意識的變更。"""
        assert classify_danger(score, NDC) == level
        assert math.isclose(danger_exceedance(score, NDC, level), expected, abs_tol=1e-12)

    @pytest.mark.parametrize("score,level,label", [
        (16, "red", "結構防禦"), (17, "yellow", "結構轉折"), (22, "yellow", "結構轉折"),
        (23, "green", "結構健康"), (31, "green", "結構健康"), (32, "yellow", "結構轉折"),
        (38, "red", "結構過熱"),
    ])
    def test_five_bucket_long_bucket(self, score, level, label):
        """v1 五桶 bar / v2 今天頁五桶摘要共用的 L2 長期桶：NDC 23 不再亮黃。"""
        from src.compute.macro import compute_five_bucket_summary
        out = compute_five_bucket_summary(macro_info={"ndc_signal": {"score": score}})["long"]
        assert out["level"] == level and out["label"] == label
        assert [d["danger"] for d in out["details"] if d["key"] == "ndc_signal"] == [level]

    @pytest.mark.parametrize("kw,headline_prefix", [
        # 黃燈同色：健康 45（(50-45)/15＝1/3）vs NDC 20（修前 3/7、修後 2/6＝1/3）→ 平手退回註冊順序
        (dict(warroom_summary={"health_score": 45}, macro_info={"ndc_signal": {"score": 20}}),
         "總經健康評分 45"),
        # 黃燈同色：M1B-M2 0.6%（(1-0.6)/1＝0.4）vs NDC 20（修後 1/3）→ M1B 為主因
        (dict(m1b_m2_info={"gap": 0.6, "source": "CBC-tier1"}, macro_info={"ndc_signal": {"score": 20}}),
         "M1B-M2 資金動能 0.60%"),
        # 紅燈同色：M1B-M2 −0.6%（0.6）vs NDC 12（修前 4/7≈0.571、修後 4/6≈0.667）→ NDC 為主因
        (dict(m1b_m2_info={"gap": -0.6, "source": "CBC-tier1"}, macro_info={"ndc_signal": {"score": 12}}),
         "NDC 景氣對策燈號 12分"),
    ])
    def test_long_bucket_headline_picks_largest_exceedance(self, kw, headline_prefix):
        """長期桶多盞同色燈 → 主因（headline）取超標幅度最大者；帶寬 7→6 會換主因。"""
        from src.compute.macro import compute_five_bucket_summary
        out = compute_five_bucket_summary(**kw)["long"]
        assert out["headline"].startswith(headline_prefix), out["headline"]

    @pytest.mark.parametrize("score,zh", [(16, "紅"), (22, "黃"), (23, "綠"), (31, "綠")])
    def test_v2_today_tile(self, score, zh):
        from src.ui.render.macro_v2_cards import band_meta, threshold_text
        from src.ui.views import page_today as PT
        rec = {"key": "ndc_signal", "wired": True, "discriminative": True, "state": "ok",
               "reason": None, "value": float(score), "hit_source": "FinMind",
               "candidates": [], "rejected": []}
        tile = PT.build_indicator_tile("ndc_signal", rec, requested=True, error="",
                                       band_label=band_meta, thr_text=threshold_text)
        assert tile.signal_text == zh
        assert dict(tile.facts)["門檻帶"] == "紅 ≤16 / 黃 ≤22　黃 ≥32 / 紅 ≥38"

    @pytest.mark.parametrize("score,band,verdict", [
        (22, "yellow", ("yellow", "1 桶黃　·　最差是「長期」")),
        (23, "green", ("green", "五桶全綠　·　最差是「長期」")),
    ])
    def test_v2_macro_page_rows_and_danger(self, score, band, verdict):
        """v2 總經頁（與 v2 今天頁「指標危險度」卡同一條 build_rows→bucket_summary→overall_verdict）。"""
        from src.compute.macro import compute_five_bucket_summary
        from src.ui.tabs import tab_macro_v2 as TV
        rd: dict = {}
        compute_five_bucket_summary(macro_info={"ndc_signal": {"score": score}}, readiness_out=rd)
        rows = TV.build_rows(rd)
        ndc_row = [r for r in rows if r.key == "ndc_signal"][0]
        assert ndc_row.band == band
        assert ndc_row.thr_text == "紅 ≤16 / 黃 ≤22　黃 ≥32 / 紅 ≥38"
        assert TV.overall_verdict(TV.bucket_summary(rows)) == verdict
