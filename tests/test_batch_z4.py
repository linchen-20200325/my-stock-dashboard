"""批 Z4（2026-10-05）—— R9 ＋ D4-n2 釘子。

R9（L0）：NDC 景氣對策燈號 23 分「程式判黃、文件寫綠」（客戶 2026-10-02 定性為程式 bug）。
修法：`shared/macro_buckets.py::BUCKET_DANGER_SPECS['ndc_signal']` 的 `yellow_lo` 23.0 → 22.0。
要求：9～45 每個整數都與 `shared/signal_thresholds.NDC_SIGNAL_BANDS` 的色系一致
（≤16 紅／17～22 黃／23～31 綠／32～37 黃／≥38 紅）；門檻字出現「黃 ≤22」；只動數字、不改任何字。
本檔另逐一釘住受影響的消費端（v1 五桶 / v2 今天頁 / v2 總經頁 / 資料體檢頁門檻字 /
教學卡線位 / AI prompt 門檻句 / 超標幅度 / 長期桶主因選擇）。

D4-n2（L0＋L5）：被擋的值**全部**是非有限值（NaN／±inf）＝ 📵 上游無值（客戶 10-02 裁「C1 選 A」），
三處（資料診斷頁／今天頁／總經 v2）共用 L0 `rejected_all_nonfinite`；見檔案下半部。
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

    def test_non_integer_follows_the_shared_le_rule(self):
        """批 Z4 追補【2】（QA：R9-c／R9-M05／R9-M17；重驗再補 R9-M18／M19／M20）：
        非整數沿用全燈共用的「≤ yellow_lo 才黃」。

        總管 2026-10-05 裁定：⛔ 不另立 NDC 專屬語意。
        ⚠️ 正式路徑的 NDC 分數一律是整數（`src/data/macro/macro_snapshot.fetch_ndc_block` 的來源
        全都轉 `int`，兩組 QA 皆查得）；本釘子**只鎖共用比較規則**，⛔ 不是官方分數帶語意
        （官方表 22.4 會落在「黃藍燈」）。⛔ 不釘畫面顯示（22.4 顯示「22分」卻亮綠屬既有類型的
        已知限制，總管另登記）。
        22.4 只殺得掉黃線外推 ≥ 0.4 的偏移（`<= yellow_lo+0.5`、`< yellow_lo+1`）；
        「緊鄰 22.0 的下一個浮點數 → 綠」才殺得掉 `<= yellow_lo+0.01`、`<= +0.3`、`< +0.4` 這類小偏移。
        """
        assert classify_danger(22.4, NDC) == "green"
        assert classify_danger(math.nextafter(22.0, math.inf), NDC) == "green"
        assert classify_danger(22.0, NDC) == "yellow"

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


# ══════════════════════════════════════════════════════════════════
# D4-n2 —— 被擋的值**全部**是非有限值 ⇒ 三處一致走既有的「上游無值」那一態
# ══════════════════════════════════════════════════════════════════
# 客戶 2026-10-02 審稿裁「C1 選 A」：被擋值全是 NaN／±inf ＝ 📵 上游無值（原本只套在資料診斷頁）。
#   · 資料診斷頁（`src/ui/pages/data_coverage.py`）：輸出**完全不變**（含「└」逐筆行）。
#   · 今天頁（`src/ui/views/page_today.py`）：紅燈「程式要修」→ 既有「無輸入」灰態＋`MISSING_NO_VALUE` 的既有說法。
#   · 總經 v2（`src/ui/tabs/tab_macro_v2.py`）：明細面板改用既有「上游來源這輪沒有回值」那句。
#   · 混合（有限越界＋非有限）／純有限越界 → 三處都維持原判定；L2 側車原因碼一個字不改。
#   · 三處共用 L0 `shared.macro_buckets.rejected_all_nonfinite`（下方 spy 測試釘「真的有用它」）。
import pandas as pd  # noqa: E402

from shared.macro_buckets import (  # noqa: E402
    MISSING_NO_VALUE,
    MISSING_OUT_OF_RANGE,
    rejected_all_nonfinite,
)
from shared.station_specs import MISS_CONTRACT_DRIFT, MISS_NO_INPUT, MISS_TEXT  # noqa: E402
from shared.ui_state import UI_FAILED, UI_MISSING_RETRYABLE  # noqa: E402

NAN, INF = float("nan"), float("inf")
_WHY_NONFINITE = "非有限值(NaN / ±inf)"          # L2 `_first_sane` 寫進側車的逐筆標註（既有字樣）
_V2_NO_VALUE_TXT = "上游來源這輪沒有回值 —— 到「🔎 資料診斷」看 API 根因。"
_V2_OOR_TXT = ("取到的值超出合理範圍,已被擋下 —— 通常是上游換了標的或報價慣例"
               "(如 DXY→UUP、殖利率×10)。**不猜換算**,故顯示無資料。")


def _rec(*vals, reason=MISSING_OUT_OF_RANGE, key="us10y"):
    """readiness 側車一筆（形狀同 L2 `macro_helpers._rec`）；`vals`＝被擋下的值，依序一源一筆。

    `wired` / `discriminative` 照 L2 的作法**抄自 spec**（批 Z4 追補：原本寫死 True，
    融資 `margin` 的側車就會跟 L0 對不上）。
    """
    _sp = SPECS_BY_KEY[key]
    return {
        "key": key, "label": _sp.label, "bucket": _sp.bucket, "wired": bool(_sp.wired),
        "discriminative": bool(_sp.discriminative), "state": "missing", "reason": reason, "value": None,
        "hit_source": None, "candidates": [f"源{i}" for i in range(len(vals))],
        "rejected": [(f"源{i}", v, _WHY_NONFINITE if not math.isfinite(v)
                      else f"out_of_range[{_sp.valid_min},{_sp.valid_max}]")
                     for i, v in enumerate(vals)],
    }


def _intl(**closes):
    return {"intl": {k: pd.DataFrame({"close": [v]}) for k, v in closes.items()}}


#: 真實 L2 路徑產生側車的情境（`compute_five_bucket_summary` 的關鍵字參數）。
#: 一律帶一個有值的 VIX，讓資料診斷頁那一列是「已載入」（macro_info 有實質 key）。
_VIX_OK = {"vix": {"current": 17.2}}
SCENARIOS = {
    "us10y_nan": dict(macro_info={**_VIX_OK, "us10y": {"current": NAN}}),
    "us10y_inf_both": dict(macro_info={**_VIX_OK, "us10y": {"current": INF}},
                           cl_data=_intl(**{"10Y公債殖利率": -INF})),
    "us10y_mixed": dict(macro_info={**_VIX_OK, "us10y": {"current": NAN}},
                        cl_data=_intl(**{"10Y公債殖利率": 46.3})),
    "us10y_finite": dict(macro_info=dict(_VIX_OK), cl_data=_intl(**{"10Y公債殖利率": 46.3})),
}
#: 情境 → 是否「被擋值全是非有限值」
NONFINITE_ONLY = {"us10y_nan": True, "us10y_inf_both": True,
                  "us10y_mixed": False, "us10y_finite": False}


def _readiness(**kw) -> dict:
    from src.compute.macro import compute_five_bucket_summary
    rd: dict = {}
    compute_five_bucket_summary(readiness_out=rd, **kw)
    return rd


class TestD4n2SharedPredicate:
    @pytest.mark.parametrize("vals", [(NAN,), (INF,), (-INF,), (NAN, INF, -INF), (INF, INF)])
    def test_true_when_every_rejected_value_is_nonfinite(self, vals):
        assert rejected_all_nonfinite(_rec(*vals)) is True

    @pytest.mark.parametrize("vals", [
        (NAN, 46.3), (46.3, INF), (-INF, 0.0, NAN),   # 混合：任一筆有限 ⇒ 仍是量綱訊號
        (46.3,), (-1e300,),                           # 純有限越界
        (),                                           # 沒有被擋的值（all([]) 恆真的陷阱）
    ])
    def test_false_otherwise(self, vals):
        assert rejected_all_nonfinite(_rec(*vals)) is False

    @pytest.mark.parametrize("reason", [MISSING_NO_VALUE, "not_loaded", "no_extraction", None, ""])
    def test_only_for_out_of_range(self, reason):
        assert rejected_all_nonfinite(_rec(NAN, reason=reason)) is False

    @pytest.mark.parametrize("rec", [None, {}, [], "out_of_range", {"reason": MISSING_OUT_OF_RANGE}])
    def test_not_a_record_or_no_rejected(self, rec):
        assert rejected_all_nonfinite(rec) is False

    def test_reads_the_value_column_not_the_label_or_note(self):
        """只看第 2 欄（值）—— 標註字串寫「非有限值」但值是有限的 ⇒ False。"""
        rec = {"reason": MISSING_OUT_OF_RANGE,
               "rejected": [("nan", 46.3, _WHY_NONFINITE), ("inf", 99.0, _WHY_NONFINITE)]}
        assert rejected_all_nonfinite(rec) is False

    def test_accepts_readonly_mapping(self):
        from types import MappingProxyType
        assert rejected_all_nonfinite(MappingProxyType(_rec(NAN))) is True

    @pytest.mark.parametrize("bad", ["-inf", "nan", "inf", "46.3"])
    def test_non_real_value_raises_type_error(self, bad):
        """批 Z4 追補【3】（QA D4-b）：rejected 的值是字串 → `math.isfinite` 拋 TypeError（現行行為）。

        釘的是「⛔ 先 `float()` 強轉」：強轉後 `'-inf'` 會被當成非有限值、整件事變成靜默轉灰。
        L2 契約下走不到（L2 寫入的一律是 Python float；產出端契約由本檔追補【5】的契約測試釘住）。
        """
        rec = {"reason": MISSING_OUT_OF_RANGE, "rejected": [("源0", bad, _WHY_NONFINITE)]}
        with pytest.raises(TypeError):
            rejected_all_nonfinite(rec)

    @pytest.mark.parametrize("name", sorted(SCENARIOS))
    def test_real_l2_sidecar(self, name):
        """真 L2 路徑：側車原因碼照舊 `out_of_range`（⛔ 不改 L2）；判斷結果與情境一致。"""
        rec = _readiness(**SCENARIOS[name])["us10y"]
        assert rec["reason"] == MISSING_OUT_OF_RANGE and rec["state"] == "missing"
        assert rejected_all_nonfinite(rec) is NONFINITE_ONLY[name]


# ── ① 資料診斷頁：輸出完全不變 ──────────────────────────────────────────
#: 修前（origin/main fd989ae）實跑的分組與「└」逐筆行（只取 us10y 那一段）。
_DC_BEFORE = {
    "us10y_nan": ("📵 上游無值", ["　└ us10y:FRED 美 10 年期殖利率 = nan 非有限值(NaN / ±inf)"]),
    "us10y_inf_both": ("📵 上游無值", [
        "　└ us10y:FRED 美 10 年期殖利率 = inf 非有限值(NaN / ±inf)",
        "　└ us10y:Yahoo 美債 10Y 殖利率（FRED 抓不到時的備援） = -inf 非有限值(NaN / ±inf)"]),
    "us10y_mixed": ("📐 量綱異常", [
        "　└ us10y:FRED 美 10 年期殖利率 = nan 非有限值(NaN / ±inf)",
        "　└ us10y:Yahoo 美債 10Y 殖利率（FRED 抓不到時的備援） = 46.3 out_of_range[0.0,20.0]"]),
    "us10y_finite": ("📐 量綱異常", [
        "　└ us10y:Yahoo 美債 10Y 殖利率（FRED 抓不到時的備援） = 46.3 out_of_range[0.0,20.0]"]),
}


def _coverage_detail(**kw) -> str:
    import datetime as _dt

    from src.ui.pages.data_coverage import compute_tab_coverage
    _state = {**{k: v for k, v in kw.items() if k != "macro_info"},
              "macro_info": {**kw.get("macro_info", {}), "_loaded_at": "2026-10-05T01:00"}}
    _rows = compute_tab_coverage(state=_state, today=_dt.date(2026, 10, 5))
    return [r for r in _rows if "總經" in r["tab"]][0]["detail"]


def _group_of(detail: str, key: str):
    """回 (key 所在分組的「圖示 名稱」, 緊接在該組標頭後、屬於 key 的「└」行)。"""
    segs = detail.split(" ｜ ")
    for i, s in enumerate(segs):
        if s[:1] in ("🔌", "📵", "📐", "🐛", "⬜") and "(" in s and ":" in s:
            members = s.split(":", 1)[1].split(" → ")[0].split("/")
            if key in members:
                tail = []
                for t in segs[i + 1:]:
                    if not t.startswith("　└"):
                        break
                    if t.startswith(f"　└ {key}:"):
                        tail.append(t)
                return s.split("(")[0], tail
    return None, []


class TestD4n2DataCoverageUnchanged:
    @pytest.mark.parametrize("name", sorted(_DC_BEFORE))
    def test_grouping_and_detail_lines_identical_to_before(self, name):
        assert _group_of(_coverage_detail(**SCENARIOS[name]), "us10y") == _DC_BEFORE[name]

    def test_two_keys_each_lines_under_its_own_group(self):
        """us10y（全非有限）在 📵、dxy（UUP 27）在 📐；各自的「└」排在自己那一組正下方。"""
        detail = _coverage_detail(macro_info={**_VIX_OK, "us10y": {"current": NAN}},
                                  cl_data=_intl(**{"美元指數 DXY": 27.0}))
        assert _group_of(detail, "us10y") == (
            "📵 上游無值", ["　└ us10y:FRED 美 10 年期殖利率 = nan 非有限值(NaN / ±inf)"])
        assert _group_of(detail, "dxy") == ("📐 量綱異常", [
            "　└ dxy:Yahoo 美元指數 → 美元指數期貨（ETF 備援尺度不同，一律擋下不用） = 27.0 "
            "out_of_range[70.0,130.0]"])


# ── ② 今天頁：全非有限 → 既有「無輸入」灰態；混合／有限越界 → 照舊紅 ──────────
def _today_tile(key, rec):
    from src.ui.render.macro_v2_cards import band_meta, threshold_text
    from src.ui.views import page_today as PT
    return PT.build_indicator_tile(key, rec, requested=True, error="",
                                   band_label=band_meta, thr_text=threshold_text)


class TestD4n2TodayPage:
    @pytest.mark.parametrize("key,vals", [
        ("us10y", (NAN,)), ("us10y", (INF, -INF)), ("vix", (NAN,)), ("m1b_m2_gap", (INF,)),
        ("dxy", (-INF,)), ("ndc_signal", (NAN,)),
    ])
    def test_nonfinite_only_is_gray_no_input(self, key, vals):
        from src.ui.views import page_today as PT
        t = _today_tile(key, _rec(*vals, key=key))
        assert t.card.state == UI_MISSING_RETRYABLE
        assert t.card.note.now == f"{SPECS_BY_KEY[key].label}　無數值"
        assert t.card.note.why == MISS_TEXT[MISS_NO_INPUT]        # MISSING_NO_VALUE 的既有說法
        assert t.card.note.where is PT.EXIT_RETRY_HERE
        assert t.signal_text == ""
        assert PT.v2_card_badge_n(t.card) == 7                    # ⚠︎ — 缺漏 · 可重跑
        assert PT.reason_is_unregistered(_rec(*vals, key=key)) is False

    def test_out_of_reach_light_keeps_its_exit(self):
        """`health`（本頁按鈕摸不到）：一樣轉灰，但出口照舊是「不在本頁射程內」。"""
        from src.ui.views import page_today as PT
        t = _today_tile("health", _rec(NAN, key="health"))
        assert t.card.state == UI_MISSING_RETRYABLE
        assert t.card.note.where is PT.EXIT_OUT_OF_REACH

    @pytest.mark.parametrize("vals", [(NAN, 46.3), (46.3,), (INF, 25.0, -INF)])
    def test_finite_or_mixed_stays_red(self, vals):
        from src.ui.views import page_today as PT
        t = _today_tile("us10y", _rec(*vals))
        assert t.card.state == UI_FAILED
        assert t.card.note.now == "10Y 公債殖利率　**這盞燈壞了，不是沒資料**"
        assert t.card.note.why == MISS_TEXT[MISS_CONTRACT_DRIFT]
        assert t.card.note.where is PT.EXIT_FIX_CODE
        assert PT.v2_card_badge_n(t.card) == 6                    # 🔴 取得失敗

    @pytest.mark.parametrize("name", sorted(SCENARIOS))
    def test_real_l2_path_and_coverage_counts(self, name):
        from src.ui.views import page_today as PT
        rd = _readiness(**SCENARIOS[name])
        tiles = PT.build_indicator_tiles(PT.MacroReadout(requested=True, readiness=rd))
        tile = [t for b in tiles.values() for t in b if t.card.key == "detail.us10y"][0]
        cov = PT.coverage(tiles)
        if NONFINITE_ONLY[name]:
            assert tile.card.state == UI_MISSING_RETRYABLE and cov.fault == 0
        else:
            assert tile.card.state == UI_FAILED and cov.fault == 1


# ── ③ 總經 v2：明細面板的說明句 ──────────────────────────────────────────
class TestD4n2MacroV2:
    @pytest.mark.parametrize("name", sorted(SCENARIOS))
    def test_detail_reason_text(self, name):
        from src.ui.tabs import tab_macro_v2 as TV
        # 批 Z4 追補【4】D-M28：另給一筆融資（discriminative=False ⇒ 「已失準」列）；
        #   只加在 cl_data 的 `margin` 格，⛔ 不影響 us10y 那一列的任何一源。
        _kw = {**SCENARIOS[name],
               "cl_data": {**SCENARIOS[name].get("cl_data", {}), "margin": 3000.0}}
        rows = {r.key: r for r in TV.build_rows(_readiness(**_kw))}
        row = rows["us10y"]
        assert (row.state, row.band, row.value) == ("missing", "gray", None)
        if NONFINITE_ONLY[name]:
            assert row.reason == MISSING_NO_VALUE
            assert TV._REASON_TXT[row.reason] == _V2_NO_VALUE_TXT
        else:
            assert row.reason == MISSING_OUT_OF_RANGE
            assert TV._REASON_TXT[row.reason] == _V2_OOR_TXT
        # 批 Z4 追補【4】D-M28（QA B 組）：運作中／已失準的列 `Row.reason` 一律 None（⛔ 不得補成 no_value）
        assert rows["vix"].state == "live" and rows["margin"].state == "degraded"
        _shown = [r for r in rows.values() if r.state in ("live", "degraded")]
        assert all(r.reason is None for r in _shown), [(r.key, r.reason) for r in _shown]

    def test_live_row_with_out_of_range_sidecar_pins_current_reason(self):
        """批 Z4 追補【4】D-M22（QA B 組）：側車「state=ok 有值」卻同時帶 out_of_range＋全非有限
        rejected（L2 契約下不會發生：命中時 `_rec(state="ok")` 不寫 reason）—— 釘住現行輸出：
        列照常判燈（live），`Row.reason` 照樣經 L0 共用判斷讀成 no_value（⛔ 不看列狀態）。"""
        from src.ui.tabs import tab_macro_v2 as TV
        rec = {**_ok_rec(SPECS_BY_KEY["vix"]), "value": 25.0, "reason": MISSING_OUT_OF_RANGE,
               "rejected": [("源0", NAN, _WHY_NONFINITE)]}
        row = {r.key: r for r in TV.build_rows({"vix": rec})}["vix"]
        assert (row.state, row.value, row.band) == ("live", 25.0, "yellow")
        assert row.reason == MISSING_NO_VALUE

    @pytest.mark.parametrize("nonfinite", [True, False])
    def test_render_detail_info_box(self, monkeypatch, nonfinite):
        """L4 明細面板實際印出的那一句（`st.info(…, icon="📭")`）。"""
        from unittest import mock

        from src.ui.render import macro_v2_cards as MV
        from src.ui.tabs import tab_macro_v2 as TV
        rd = _readiness(**SCENARIOS["us10y_nan" if nonfinite else "us10y_finite"])
        row = {r.key: r for r in TV.build_rows(rd)}["us10y"]
        fake = mock.MagicMock(name="st")
        monkeypatch.setattr(MV, "st", fake)
        MV.render_detail(row, SPECS_BY_KEY["us10y"], edu=None,
                         reason_text=TV._REASON_TXT.get(row.reason or "", ""))
        infos = [c.args[0] for c in fake.info.call_args_list if c.kwargs.get("icon") == "📭"]
        assert (_V2_NO_VALUE_TXT if nonfinite else _V2_OOR_TXT) in infos


# ── ④ 三處都真的走 L0 共用判斷（任一處自己判 ⇒ 紅燈）──────────────────────
def _dc_group(monkeypatch, verdict, scenario):
    """把資料診斷頁命名空間裡的共用判斷換成恆 `verdict`，回 us10y 被分到哪一組。"""
    from src.ui.pages import data_coverage as DC
    monkeypatch.setattr(DC, "rejected_all_nonfinite", lambda _r: verdict)
    return _group_of(_coverage_detail(**SCENARIOS[scenario]), "us10y")[0]


def _today_state(monkeypatch, verdict, vals):
    from src.ui.views import page_today as PT
    monkeypatch.setattr(PT, "rejected_all_nonfinite", lambda _r: verdict)
    t = _today_tile("us10y", _rec(*vals))
    return t.card.state, t.card.note.why, t.card.note.where is PT.EXIT_FIX_CODE


def _v2_reason(monkeypatch, verdict, vals):
    from src.ui.tabs import tab_macro_v2 as TV
    monkeypatch.setattr(TV, "rejected_all_nonfinite", lambda _r: verdict)
    return {r.key: r for r in TV.build_rows({"us10y": _rec(*vals)})}["us10y"].reason


class TestD4n2AllThreeUseTheSharedPredicate:
    """spy：把各頁命名空間裡的 `rejected_all_nonfinite` 換成恆真／恆假 → 結果必須跟著翻。

    任一處改回自己判（或漏接、只接一半）都會在這裡紅 —— 那正是「三處各寫一份」的病。
    """

    def test_data_coverage(self, monkeypatch):
        assert _dc_group(monkeypatch, True, "us10y_finite") == "📵 上游無值"
        assert _dc_group(monkeypatch, False, "us10y_nan") == "📐 量綱異常"

    def test_today_page_state_and_wording_both(self, monkeypatch):
        """判態（`indicator_state`）與說法／出口（`_miss_why`）兩處都得走同一支。"""
        assert _today_state(monkeypatch, True, (46.3,)) == (
            UI_MISSING_RETRYABLE, MISS_TEXT[MISS_NO_INPUT], False)
        assert _today_state(monkeypatch, False, (NAN,)) == (
            UI_FAILED, MISS_TEXT[MISS_CONTRACT_DRIFT], True)

    def test_macro_v2(self, monkeypatch):
        assert _v2_reason(monkeypatch, True, (46.3,)) == MISSING_NO_VALUE
        assert _v2_reason(monkeypatch, False, (NAN,)) == MISSING_OUT_OF_RANGE


# ══════════════════════════════════════════════════════════════════
# 批 Z4 追補（2026-10-05 QA 驗收 A 組 B1）【1】D4-n2 三頁 × 全燈參數化
# ══════════════════════════════════════════════════════════════════
# 修前的 D4-n2 釘子：總經 v2／資料診斷頁只測 us10y、今天頁只測 6 盞 ⇒ 下列突變 fast＋slow 全綠存活：
#   只對「有 valid 範圍」的燈套用（D4-f／D4-g）、只對 `discriminative=True` 套用（D4-m／D4-n）、
#   單一盞例外（D4-o：ism_pmi；D4-l：news_systemic）。
# 母集合＝`BUCKET_DANGER_SPECS`（16 盞）；兩種輸入：
#   (a) 真 L2 路徑注入：可注入的燈 × NaN／+inf／−inf（`compute_five_bucket_summary` 實跑）；
#   (b) 合成側車：全 16 盞（含 `news_systemic`），目標燈「被擋值全非有限」、其餘 15 盞照常有值。
# 斷言一律落在使用者看得到的輸出：
#   今天頁＝狀態／徽章 #7／「為什麼」句／去哪補短語／覆蓋率「故障 0」；
#   總經 v2＝`Row.reason` 與明細句；資料診斷頁＝📵 那一組＋該燈的「└」逐筆行（⛔ 不是 📐）。
from shared.macro_buckets import (  # noqa: E402
    BUCKET_DANGER_SPECS,
    CL_INTL_KEY_DXY,
    CL_INTL_KEY_US10Y,
)

#: (a) 真 L2 注入**排除**的燈與理由（明列，⛔ 不靜默略過）。
REAL_L2_EXCLUDED: dict[str, str] = {
    "news_systemic": ("值由 L2 自己數則數（`float(sum(...))`，恆為有限整數），上游沒有能塞進 "
                      "NaN／±inf 的欄位 ⇒ 真 L2 走不到「被擋值全非有限」；改由 (b) 合成側車涵蓋"),
}
#: 三頁**實際不消費**的燈與理由。現況 16 盞全 `wired=True` ⇒ 三頁都消費全部 16 盞，本表為空。
#: 日後若有燈改成 `wired=False`：三頁都先判「未接線」、⛔ 不讀缺值原因（L2 也不會寫 out_of_range）
#: ⇒ 必須登記在這裡並寫明理由（`TestD4n2ParamUniverse` 會逼你登記）。
PAGE_EXCLUDED: dict[str, str] = {}

ALL_KEYS = [s.key for s in BUCKET_DANGER_SPECS]
PAGE_KEYS = [k for k in ALL_KEYS if k not in PAGE_EXCLUDED]
REAL_L2_KEYS = [k for k in PAGE_KEYS if k not in REAL_L2_EXCLUDED]
NONFINITE = [NAN, INF, -INF]
_NF_IDS = ["nan", "+inf", "-inf"]
#: 總管指定的最小涵蓋：無 valid 範圍（vix／ndc_signal）、`discriminative=False`（margin）、ism_pmi。
MUST_COVER = {"vix", "ndc_signal", "margin", "ism_pmi"}


def _inject(key: str, x) -> dict:
    """把 `x` 塞進 `key` 那盞燈在真 L2（`compute_five_bucket_summary`）實際讀的那一格。"""
    def _df(col):
        return pd.DataFrame({col: [x]})
    return {
        "health": dict(warroom_summary={"health_score": x}),
        "ndc_signal": dict(macro_info={"ndc_signal": {"score": x}}),
        "m1b_m2_gap": dict(m1b_m2_info={"gap": x, "source": "CBC-tier1"}),
        "ism_pmi": dict(macro_info={"ism_pmi": {"value": x}}),
        "us_core_cpi": dict(macro_info={"us_core_cpi": {"yoy": x}}),
        "tw_export": dict(macro_info={"tw_export": {"yoy": x}}),
        "bias_240": dict(bias_info={"bias_240": x}),
        "us10y": dict(macro_info={"us10y": {"current": x}}),
        "dxy": dict(cl_data={"intl": {CL_INTL_KEY_DXY: _df("close")}}),
        "vix": dict(macro_info={"vix": {"current": x}}),
        "adl": dict(cl_data={"adl": _df("ad_ratio")}),
        "fut_net": dict(li_latest=_df("外資大小")),
        "margin": dict(cl_data={"margin": x}),
        "jingqi": dict(jingqi_info={"avg": x}),
        "foreign_net": dict(cl_data={"inst": {"外資及陸資": {"net": x}}}),
    }[key]


def _with_base_macro(kw: dict) -> dict:
    """資料診斷頁那一列要「已載入」：macro_info 至少要有一個實質 key（沒有就補一個有值的 VIX）。"""
    return kw if kw.get("macro_info") else {**kw, "macro_info": dict(_VIX_OK)}


def _ok_rec(spec) -> dict:
    """合成側車裡「照常有值」的一筆（值取 spec 自己的黃線 ⇒ ⛔ 不手抄門檻）。"""
    return {"key": spec.key, "label": spec.label, "bucket": spec.bucket,
            "wired": bool(spec.wired), "discriminative": bool(spec.discriminative),
            "state": "ok", "reason": None, "value": float(spec.yellow), "hit_source": "T",
            "candidates": ["T"], "rejected": []}


def _synthetic(target: str, x) -> dict:
    """全 16 盞的合成側車：`target` 被擋值全是非有限值 `x`，其餘 15 盞照常有值。"""
    rd = {s.key: _ok_rec(s) for s in BUCKET_DANGER_SPECS}
    rd[target] = _rec(x, key=target)
    return rd


def _today_tiles(rd: dict):
    from src.ui.render.macro_v2_cards import band_meta, threshold_text
    from src.ui.views import page_today as PT
    return PT.build_indicator_tiles(PT.MacroReadout(requested=True, readiness=rd),
                                    band_label=band_meta, thr_text=threshold_text)


def _assert_today_gray(tiles, key: str) -> None:
    """今天頁：目標燈＝既有「無輸入」灰態（#7）＋既有說法＋出口短語；覆蓋率沒有「故障」。"""
    from src.ui.views import page_today as PT
    tile = [t for b in tiles.values() for t in b if t.card.key == f"detail.{key}"][0]
    assert tile.card.state == UI_MISSING_RETRYABLE, (key, tile.card.state)
    assert PT.v2_card_badge_n(tile.card) == 7, key                      # ⚠︎ — 缺漏 · 可重跑
    _exit = "不在本頁射程內" if key in PT.OUT_OF_REACH_LIGHT_KEYS else "按上方 🚀 更新"
    assert PT.v2_level_line(tile)[1] == (
        ("現在", f"{SPECS_BY_KEY[key].label}　無數值"),
        ("為什麼", MISS_TEXT[MISS_NO_INPUT]),
        ("去哪補", _exit)), key
    cov = PT.coverage(tiles)
    assert cov.fault == 0 and "故障 0" in cov.text(), (key, cov.text())


def _assert_v2_no_value(rows, key: str) -> None:
    """總經 v2：目標列 `Row.reason`＝no_value，明細句＝既有「上游來源這輪沒有回值」那句。"""
    from src.ui.tabs import tab_macro_v2 as TV
    row = {r.key: r for r in rows}[key]
    assert (row.state, row.band, row.value) == ("missing", "gray", None), key
    assert row.reason == MISSING_NO_VALUE, (key, row.reason)
    assert TV._REASON_TXT.get(row.reason or "", "") == _V2_NO_VALUE_TXT, key


def _assert_dc_no_value(detail: str, key: str, rejected) -> None:
    """資料診斷頁：目標燈在「📵 上游無值」組，其下緊接它自己的「└」逐筆行（字樣同修前）。"""
    expect = [f"　└ {key}:{_lbl} = {_v} {_why}" for _lbl, _v, _why in rejected]
    assert expect, key
    assert _group_of(detail, key) == ("📵 上游無值", expect), (key, detail)


class TestD4n2ParamUniverse:
    def test_param_universe(self):
        """母集合＝16 盞；排除一律明列＋理由；總管指定的四盞都在兩種輸入的參數裡。"""
        assert len(ALL_KEYS) == len(set(ALL_KEYS)) == len(BUCKET_DANGER_SPECS)
        assert set(PAGE_KEYS) | set(PAGE_EXCLUDED) == set(ALL_KEYS)
        assert all(PAGE_EXCLUDED.values()) and all(REAL_L2_EXCLUDED.values())
        assert set(REAL_L2_EXCLUDED) <= set(PAGE_KEYS)
        # 未接線的燈三頁都不讀缺值原因 ⇒ 不可能在母集合裡而不登記（見 PAGE_EXCLUDED 註解）
        assert all(SPECS_BY_KEY[k].wired for k in PAGE_KEYS)
        assert MUST_COVER <= set(REAL_L2_KEYS) and MUST_COVER <= set(PAGE_KEYS)
        assert "news_systemic" in PAGE_KEYS            # 真 L2 走不到 ⇒ 靠 (b) 合成側車
        assert SPECS_BY_KEY["vix"].valid_min is None and SPECS_BY_KEY["ndc_signal"].valid_min is None
        assert SPECS_BY_KEY["margin"].discriminative is False

    @pytest.mark.parametrize("x", NONFINITE, ids=_NF_IDS)
    @pytest.mark.parametrize("key", REAL_L2_KEYS)
    def test_real_l2_really_writes_nonfinite_only(self, key, x):
        """(a) 的前提：真 L2 對這盞燈確實寫出「out_of_range＋被擋值全非有限」（⛔ 不改 L2 原因碼）。"""
        rec = _readiness(**_inject(key, x))[key]
        assert rec["state"] == "missing" and rec["reason"] == MISSING_OUT_OF_RANGE, (key, rec)
        assert rec["rejected"] and rejected_all_nonfinite(rec), (key, rec["rejected"])


class TestD4n2AllLampsRealL2:
    """(a) 真 L2 路徑注入：可注入的 15 盞 × NaN／+inf／−inf。"""

    @pytest.mark.parametrize("x", NONFINITE, ids=_NF_IDS)
    @pytest.mark.parametrize("key", REAL_L2_KEYS)
    def test_today_page(self, key, x):
        _assert_today_gray(_today_tiles(_readiness(**_inject(key, x))), key)

    @pytest.mark.parametrize("x", NONFINITE, ids=_NF_IDS)
    @pytest.mark.parametrize("key", REAL_L2_KEYS)
    def test_macro_v2(self, key, x):
        from src.ui.tabs import tab_macro_v2 as TV
        _assert_v2_no_value(TV.build_rows(_readiness(**_inject(key, x))), key)

    @pytest.mark.parametrize("x", NONFINITE, ids=_NF_IDS)
    @pytest.mark.parametrize("key", REAL_L2_KEYS)
    def test_data_coverage(self, key, x):
        kw = _with_base_macro(_inject(key, x))
        _assert_dc_no_value(_coverage_detail(**kw), key, _readiness(**kw)[key]["rejected"])


class TestD4n2AllLampsSyntheticSidecar:
    """(b) 合成側車：全 16 盞（含真 L2 走不到的 `news_systemic`）。"""

    @pytest.mark.parametrize("x", NONFINITE, ids=_NF_IDS)
    @pytest.mark.parametrize("key", PAGE_KEYS)
    def test_today_page(self, key, x):
        _assert_today_gray(_today_tiles(_synthetic(key, x)), key)

    @pytest.mark.parametrize("x", NONFINITE, ids=_NF_IDS)
    @pytest.mark.parametrize("key", PAGE_KEYS)
    def test_macro_v2(self, key, x):
        from src.ui.tabs import tab_macro_v2 as TV
        rows = TV.build_rows(_synthetic(key, x))
        _assert_v2_no_value(rows, key)
        # 批 Z4 追補 D-M28（QA B 組）：其餘 15 盞（運作中／已失準）的 `Row.reason` 一律 None
        others = [r for r in rows if r.key != key]
        assert {r.state for r in others} == ({"live", "degraded"} if key != "margin" else {"live"})
        assert all(r.reason is None for r in others), [(r.key, r.reason) for r in others]

    @pytest.mark.parametrize("x", NONFINITE, ids=_NF_IDS)
    @pytest.mark.parametrize("key", PAGE_KEYS)
    def test_data_coverage(self, monkeypatch, key, x):
        """資料診斷頁自己會呼叫 L2 —— 這裡把 L2 換成「回填合成側車」，其餘照真路徑跑。"""
        import src.compute.macro as CM
        rd_syn = _synthetic(key, x)

        def _fake_summary(**kw):
            kw["readiness_out"].update(rd_syn)
            return {}

        monkeypatch.setattr(CM, "compute_five_bucket_summary", _fake_summary)
        _assert_dc_no_value(_coverage_detail(macro_info=dict(_VIX_OK)), key, rd_syn[key]["rejected"])


# ══════════════════════════════════════════════════════════════════
# 批 Z4 追補【5】L2 產出端契約＋形狀不合法時 fail loud
# ══════════════════════════════════════════════════════════════════
# `rejected_all_nonfinite` 遇到形狀不合法的 rejected 會拋（值非實數 → TypeError；tuple 不足 2 欄 →
# IndexError）。資料診斷頁修前就是如此；今天頁與總經 v2 則是**新增的例外路徑**（兩頁修前不讀
# rejected）。總管 2026-10-05 裁定：維持 fail-loud、⛔ 不吞 —— 但「L2 契約下走不到」要由測試保證：
#   · `TestL2RejectedContract`：真 L2 產生器 × 各種型別 → 每筆 rejected 都是 ≥2 欄 tuple、第 2 欄是 Python float；
#   · `TestMalformedRejectedFailsLoud`：形狀不合法時三處都照樣拋（⛔ 不得被改成靜默吞掉）。
from decimal import Decimal  # noqa: E402

import numpy as np  # noqa: E402


def _deep_merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = _deep_merge(out[k], v) if isinstance(out.get(k), dict) and isinstance(v, dict) else v
    return out


def _inject_all(x) -> dict:
    """把 `x` 同時塞進 15 盞可注入燈的**每一個**取值格（us10y 三個源全塞）＋新聞清單。"""
    kw: dict = {}
    for _k in REAL_L2_KEYS:
        kw = _deep_merge(kw, _inject(_k, x))
    kw = _deep_merge(kw, {"macro_info": {"us10y": {"value": x}},
                          "cl_data": {"intl": {CL_INTL_KEY_US10Y: pd.DataFrame({"close": [x]})}}})
    kw["news_items"] = [{"is_systemic": x}]
    return kw


#: 總管指定的輸入型別：None、字串、Decimal、numpy 型別、±inf、NaN、bool（另加一般有限值作對照）。
_CONTRACT_VALUES = [
    None,
    "abc", "", "nan", "-inf", "inf", "46.3",
    Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), Decimal("46.3"),
    np.float64("nan"), np.float32("inf"), np.float64("-inf"), np.int64(5), np.int32(-7), np.bool_(True),
    NAN, INF, -INF,
    True, False,
    46.3, -1e300, 1e300,
]


class TestL2RejectedContract:
    @pytest.mark.parametrize("x", _CONTRACT_VALUES, ids=repr)
    def test_every_rejected_entry_is_a_tuple_with_a_python_float(self, x):
        rd = _readiness(**_inject_all(x))
        assert set(rd) == set(ALL_KEYS)
        for _key, _rec_l2 in rd.items():
            for _e in _rec_l2.get("rejected") or []:
                assert isinstance(_e, tuple) and len(_e) >= 2, (_key, _e)
                assert type(_e[1]) is float, (_key, _e, type(_e[1]))

    @pytest.mark.parametrize("x", [NAN, INF, -INF, "nan", "-inf", Decimal("NaN"), np.float64("inf")],
                             ids=repr)
    def test_contract_is_not_vacuous(self, x):
        """上一條不是因為 rejected 全空才綠：非有限輸入下，15 盞可注入燈每盞都至少擋下一筆。"""
        rd = _readiness(**_inject_all(x))
        assert [k for k in REAL_L2_KEYS if not rd[k]["rejected"]] == []
        assert all(rejected_all_nonfinite(rd[k]) for k in REAL_L2_KEYS)


#: 形狀不合法的 rejected → 預期例外（現行行為；⛔ 不吞）。
_MALFORMED = [
    pytest.param([("源0", "-inf", _WHY_NONFINITE)], TypeError, id="value-is-str"),
    pytest.param([("源0",)], IndexError, id="tuple-shorter-than-2"),
]


def _malformed_rec(rejected) -> dict:
    return {**_rec(key="us10y"), "rejected": list(rejected)}


class TestMalformedRejectedFailsLoud:
    @pytest.mark.parametrize("rejected,exc", _MALFORMED)
    def test_l0(self, rejected, exc):
        with pytest.raises(exc):
            rejected_all_nonfinite(_malformed_rec(rejected))

    @pytest.mark.parametrize("rejected,exc", _MALFORMED)
    def test_today_page_new_exception_path(self, rejected, exc):
        with pytest.raises(exc):
            _today_tile("us10y", _malformed_rec(rejected))

    @pytest.mark.parametrize("rejected,exc", _MALFORMED)
    def test_macro_v2_new_exception_path(self, rejected, exc):
        from src.ui.tabs import tab_macro_v2 as TV
        with pytest.raises(exc):
            TV.build_rows({"us10y": _malformed_rec(rejected)})

    @pytest.mark.parametrize("rejected,exc", _MALFORMED)
    def test_data_coverage_same_as_before(self, monkeypatch, rejected, exc):
        import src.compute.macro as CM
        rd_bad = {"us10y": {**_malformed_rec(rejected)}}

        def _fake_summary(**kw):
            kw["readiness_out"].update(rd_bad)
            return {}

        monkeypatch.setattr(CM, "compute_five_bucket_summary", _fake_summary)
        with pytest.raises(exc):
            _coverage_detail(macro_info=dict(_VIX_OK))
