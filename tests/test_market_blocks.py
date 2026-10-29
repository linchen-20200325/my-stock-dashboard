"""tests/test_market_blocks.py — UI-M：`src/ui/views/_market_blocks.py` 的純函式與結構守衛。

守什麼（對應客戶 DEC-092 Q2／Q3 與 A 規格 §4.1／§7）：
  · 今日主要風險（hero）與圖 D 是**同一份** `MarketRisks`；只列非綠桶、依桶固定順序、最多 3 項、「另 N 項見圖 D」、
    同級並列寫「並列 N 項」、不做重要性排序；資料不足的桶不硬選最差；⛔ 不寫「無風險」。
  · 方向只轉述 L2 `LampDirection` 的原詞；無資料／計算失敗絕不畫成「持平」；不翻成「惡化」。
  · 圖 A／圖 B 的窗口與資料日由資料算出；均線是水平參考線（不自行算滾動）；圖 C 區塊內零數字。
  · 水位卡首屏無百分比；「查看依據」六欄一律填寫（沒有就寫 ⬜ 與原因）。
  · 結構：L5 不 import L1／ia_nav4；圖 A／圖 B 無 gate；圖 A 讀本地快取前必須先過「已載入」判斷。
"""
from __future__ import annotations

import ast
import pathlib
import re
from types import SimpleNamespace

import pandas as pd
import pytest

from shared.macro_buckets import BUCKET_ORDER
from src.compute.macro.lamp_direction import LampDirection
from src.ui.views import _market_blocks as B

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC = (_ROOT / "src" / "ui" / "views" / "_market_blocks.py").read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)


# ══════════════════════════════════════════════════════════════════
# 夾具：可控的 readout（五桶 summary 手工組）
# ══════════════════════════════════════════════════════════════════
def _detail(key, label, danger, value="1.0"):
    return {"key": key, "label": label, "value_str": value, "danger": danger, "note": ""}


def _bucket(level, *, main=None, details=None, label="某狀態", headline="某標題"):
    return {"level": level, "label": label, "headline": headline, "color": "#000", "emoji": "x",
            "details": details or [], "main_key": main}


def _readout(buckets, *, requested=True, error=""):
    return SimpleNamespace(requested=requested, error=error, summary=buckets, readiness={})


def _five(levels):
    """levels: {bucket: level}，每桶一盞主因燈（非綠時 main_key 指向它）；回 readout。"""
    _s = {}
    for _b in BUCKET_ORDER:
        _lv = levels.get(_b, "green")
        if _lv in ("yellow", "red"):
            _s[_b] = _bucket(_lv, main=f"{_b}_a", details=[_detail(f"{_b}_a", f"{_b}燈A", _lv, "9.9")])
        elif _lv == "green":
            _s[_b] = _bucket("green", details=[_detail(f"{_b}_a", f"{_b}燈A", "green")], headline="1 項指標全綠")
        else:
            _s[_b] = _bucket("gray", details=[_detail(f"{_b}_a", f"{_b}燈A", "gray")], headline="尚未載入")
    return _readout(_s)


def _dir(direction, delta=1.0):
    return LampDirection(direction=direction, delta=delta, unit="%", window_text="近 20 交易日",
                         as_of="2026-10-22", reason="")


def _all_up():
    return {f"{_b}_a": _dir("up") for _b in BUCKET_ORDER}


# ══════════════════════════════════════════════════════════════════
# 1. 風險項挑選
# ══════════════════════════════════════════════════════════════════
class TestRiskSelection:
    def test_cold_start_is_grey_not_loaded_and_has_no_rows(self):
        _r = B.build_market_risks(_readout({}, requested=False), _all_up())
        assert _r.cold and _r.rows == ()
        assert B.hero_risk_lines(_r) == [("grey", B.NOT_LOADED)]

    def test_only_non_green_in_fixed_bucket_order_max_three(self):
        _r = B.build_market_risks(_five({"long": "red", "mid": "green", "short": "yellow",
                                         "chips": "red", "news": "yellow"}), _all_up())
        _items, _more = B.hero_risk_items(_r)
        assert [_i.bucket for _i in _items] == ["long", "short", "chips"]      # 桶順序，⛔ 不排重要性
        assert _more == 1                                                      # news 在第 4 位
        _lines = B.hero_risk_lines(_r)
        assert any(t == "note" and x == "另 1 項見圖 D" for t, x in _lines)
        assert sum(1 for t, _ in _lines if t == "item") == 3

    def test_red_after_yellow_is_not_promoted(self):
        """不做重要性排序：黃桶排在前面就仍在前面，紅桶不會被拉到第一。"""
        _r = B.build_market_risks(_five({"long": "yellow", "mid": "red"}), _all_up())
        assert [_i.bucket for _i in B.hero_risk_items(_r)[0]] == ["long", "mid"]

    def test_green_bucket_not_in_hero_but_in_panel(self):
        _r = B.build_market_risks(_five({"long": "red"}), _all_up())
        assert [_i.bucket for _i in B.hero_risk_items(_r)[0]] == ["long"]
        _panel = B.risk_panel_rows(_r)
        assert len(_panel) == 5 and "全綠" in _panel[1][0]

    def test_insufficient_bucket_is_never_picked_even_if_main_key_present(self):
        """資料不足 ⇒ 顯示「⬜ 資料不足／無法判定」，⛔ 不硬選最差（即使上游誤帶了 main_key）。"""
        _ro = _five({"long": "gray", "mid": "yellow"})
        _ro.summary["long"]["main_key"] = "long_a"       # 對抗性：全灰桶卻帶 main_key
        _r = B.build_market_risks(_ro, _all_up())
        _long = _r.rows[0]
        assert _long.kind == B.KIND_INSUFFICIENT and _long.lamp_key is None and _long.lamp_label == ""
        assert [_i.bucket for _i in B.hero_risk_items(_r)[0]] == ["mid"]
        assert B.risk_panel_rows(_r)[0][1] == B.INSUFFICIENT_TEXT
        assert _r.n_insufficient == 1

    def test_all_insufficient_says_undetermined(self):
        _r = B.build_market_risks(_five({_b: "gray" for _b in BUCKET_ORDER}), _all_up())
        _txt = " ".join(x for _, x in B.hero_risk_lines(_r))
        assert B.UNDETERMINED in _txt

    def test_missing_bucket_in_summary_is_insufficient_not_green(self):
        _ro = _five({"long": "red"})
        del _ro.summary["news"]
        _r = B.build_market_risks(_ro, _all_up())
        assert _r.rows[-1].bucket == "news" and _r.rows[-1].kind == B.KIND_INSUFFICIENT

    @pytest.mark.parametrize("levels", (
        {}, {_b: "gray" for _b in BUCKET_ORDER}, {"long": "gray"}, {"long": "red"}))
    def test_never_writes_no_risk_phrases(self, levels):
        _r = B.build_market_risks(_five(levels), _all_up())
        for _t in (*(x for _, x in B.hero_risk_lines(_r)), *(c for _row in B.risk_panel_rows(_r) for c in _row)):
            for _bad in ("無風險", "沒有需要處理", "一切正常", "安全無虞"):
                assert _bad not in _t
        for _cold in (B.build_market_risks(_readout({}, requested=False), None),):
            assert "無風險" not in " ".join(x for _, x in B.hero_risk_lines(_cold))

    def test_all_green_is_not_claimed_as_safe(self):
        _r = B.build_market_risks(_five({}), _all_up())
        _txt = " ".join(x for _, x in B.hero_risk_lines(_r))
        assert "不代表安全" in _txt and "無風險" not in _txt

    def test_tied_lamps_are_disclosed_not_silently_picked(self):
        _ro = _five({"mid": "yellow"})
        _ro.summary["mid"]["details"] = [_detail("mid_a", "燈A", "yellow", "9.9"),
                                         _detail("mid_b", "燈B", "yellow", "8.8"),
                                         _detail("mid_c", "燈C", "green")]
        _r = B.build_market_risks(_ro, {**_all_up(), "mid_b": _dir("down")})
        _row = _r.rows[1]
        assert _row.tied_n == 2 and _row.tied_labels == ("燈A", "燈B") and _row.lamp_key == "mid_a"
        assert "同級並列 2 項" in B.risk_item_text(_row)
        assert "（同級並列 2 項）" in B.risk_panel_rows(_r)[1][0]
        assert "燈A、燈B" in B.basis_risks(_r).rule         # 依據裡列出全部並列燈

    def test_failed_summary_is_red_error_not_empty(self):
        _r = B.build_market_risks(_readout({}, error="RuntimeError('x')"), _all_up())
        assert _r.failed and not _r.cold
        assert B.hero_risk_lines(_r)[0][0] == "error"

    def test_unevaluated_count_comes_from_details(self):
        _r = B.build_market_risks(_five({"long": "red", "mid": "gray"}), _all_up())
        # 每桶 1 盞燈；long 紅(評估)、mid 灰(未評估)、其餘 3 桶綠(評估) ⇒ 評估 4 盞
        assert _r.n_lamps - _r.n_unevaluated == 4


class TestSingleSourceHeroAndPanel:
    def test_hero_items_are_the_same_objects_as_panel_rows(self):
        """hero 與圖 D 同源：hero 的項目就是 `risks.rows` 裡的同一批物件（不是另算一份）。"""
        _r = B.build_market_risks(_five({"long": "red", "short": "yellow", "chips": "yellow"}), _all_up())
        _items, _ = B.hero_risk_items(_r)
        _risk_rows = [_row for _row in _r.rows if _row.kind == B.KIND_RISK]
        assert all(_a is _b for _a, _b in zip(_items, _risk_rows))
        _panel = B.risk_panel_rows(_r)
        for _it in _items:
            _idx = BUCKET_ORDER.index(_it.bucket)
            assert _it.lamp_label in _panel[_idx][0]
            assert _it.direction_word == _panel[_idx][1]

    def test_both_blocks_share_one_basis_object_shape(self):
        _r = B.build_market_risks(_five({"long": "red"}), _all_up())
        assert B.basis_risks(_r) == B.basis_risks(_r)


# ══════════════════════════════════════════════════════════════════
# 2. 方向原詞
# ══════════════════════════════════════════════════════════════════
class TestDirectionWords:
    @pytest.mark.parametrize("d, word", (("up", "↗ 上升"), ("flat", "→ 持平"), ("down", "↘ 下降")))
    def test_original_words(self, d, word):
        assert B.lamp_direction_texts({"k": _dir(d)}, "k")[0] == word

    def test_nodata_and_error_are_never_flat(self):
        _nd = LampDirection(direction="nodata", delta=None, unit="", window_text="", as_of=None, reason="x")
        _er = LampDirection(direction="error", delta=None, unit="", window_text="", as_of=None, reason="RuntimeError")
        _w1, _ = B.lamp_direction_texts({"a": _nd}, "a")
        _w2, _ = B.lamp_direction_texts({"a": _er}, "a")
        assert _w1 == "無資料" and _w2 == "計算失敗（RuntimeError）"
        for _w in (_w1, _w2):
            assert "持平" not in _w and "→" not in _w

    def test_missing_key_is_failure_not_flat_and_none_means_not_provided(self):
        _w, _ = B.lamp_direction_texts({}, "k")
        assert _w == "計算失敗（未回傳）" and "持平" not in _w
        assert B.lamp_direction_texts(None, "k")[0] == "⬜ 方向未提供"

    @pytest.mark.parametrize("d", ("up", "flat", "down"))
    def test_never_translated_to_worsening_words(self, d):
        for _t in B.lamp_direction_texts({"k": _dir(d)}, "k"):
            for _w in ("惡化", "改善", "好轉", "轉弱", "轉強"):
                assert _w not in _t
        assert "惡化" in B.CHART_D_WORSENING and "尚未定義" in B.CHART_D_WORSENING   # 欄位固定 ⬜ 尚未定義

    def test_risk_row_carries_direction_of_main_lamp_only(self):
        _r = B.build_market_risks(_five({"long": "red"}), {**_all_up(), "long_a": _dir("down")})
        assert _r.rows[0].direction_word == "↘ 下降"


# ══════════════════════════════════════════════════════════════════
# 3. 圖 A／圖 B／圖 C
# ══════════════════════════════════════════════════════════════════
class TestChartData:
    @pytest.mark.parametrize("val, ok", ((22000.0, True), (None, False), (float("nan"), False),
                                         (float("inf"), False), (0, False), (-5, False), ("x", False),
                                         (True, False)))
    def test_ma_reference_values(self, val, ok):
        _good, _bad = B.ma_reference_values({"ma5": val, "ma60": 1.0, "ma120": 2.0, "ma200": 3.0})
        assert any(n == "MA5" for n, _ in _good) is ok
        assert any(n == "MA5" for n, _ in _bad) is (not ok)

    def test_ma200_missing_carries_the_status_reason(self):
        _, _bad = B.ma_reference_values({"ma5": 1.0, "ma60": 1.0, "ma120": 1.0, "ma200": None,
                                         "ma200_status": "歷史不足"})
        assert _bad == [("MA200", "無資料（歷史不足）")]

    def test_ma_reference_without_mkt_info_is_all_missing(self):
        _good, _bad = B.ma_reference_values(None)
        assert _good == [] and [n for n, _ in _bad] == ["MA5", "MA60", "MA120", "MA200"]

    def test_chart_frame_ma_columns_are_horizontal_not_rolling(self):
        from src.services.market_twii_view_service import TwiiTrendView
        _view = TwiiTrendView(ok=True, xs=("2026-10-20", "2026-10-21", "2026-10-22"),
                              close=(100.0, 110.0, 105.0), n_available=3, as_of="2026-10-22")
        _df = B.twii_chart_frame(_view, [("MA5", 104.0), ("MA60", 99.0)])
        assert list(_df.columns) == [B.TWII_COLUMN, "MA5（最新值，參考）", "MA60（最新值，參考）"]
        assert _df["MA5（最新值，參考）"].nunique() == 1 and _df["MA60（最新值，參考）"].iloc[0] == 99.0
        assert list(_df[B.TWII_COLUMN]) == [100.0, 110.0, 105.0] and len(_df) == 3

    def test_window_constant_is_the_ssot_year(self):
        from shared.signal_thresholds import TRADING_DAYS_PER_YEAR
        assert B.TWII_CHART_TRADING_DAYS == TRADING_DAYS_PER_YEAR

    def _intl(self, **frames):
        return {"cl_data": {"intl": frames}}

    def test_intl_window_and_date_come_from_the_data(self):
        _idx = pd.date_range("2026-10-15", periods=6, freq="D")
        _df = pd.DataFrame({"close": [1.0, 2.0, None, 4.0, 5.0, 6.0]}, index=_idx)
        _s = B.intl_series(self._intl(**{"道瓊工業 DJI": _df}))
        _dj = next(x for x in _s if x.name == "道瓊工業 DJI")
        assert _dj.status == "ok" and _dj.n == 5 and _dj.last_date == "2026-10-20"
        assert _dj.window_text == "近 5 日，資料至 2026-10-20"

    def test_intl_missing_series_are_explicit(self):
        _s = B.intl_series(self._intl(**{"道瓊工業 DJI": pd.DataFrame({"close": []})}))
        _by = {x.name: x for x in _s}
        assert _by["道瓊工業 DJI"].status == "empty" and _by["道瓊工業 DJI"].window_text == "⬜ 無資料"
        assert _by["費城半導體 SOX"].status == "absent"

    def test_intl_not_loaded_is_none(self):
        assert B.intl_series({}) is None and B.intl_series({"cl_data": {}}) is None
        assert B.intl_series({"cl_data": {"intl": None}}) is None

    def test_intl_groups_cover_every_known_series_exactly_once(self):
        """漂移守衛：L3 `daily_checklist.INTL_MAP` 多一個系列，圖 B 分組就要回來補。"""
        from src.services.daily_checklist import INTL_MAP
        _names = [n for _, ns in B.INTL_GROUPS for n in ns]
        assert sorted(_names) == sorted(INTL_MAP) and len(_names) == len(set(_names))
        assert [g for g, _ in B.INTL_GROUPS] == ["海外市場", "利率", "美元"]

    def test_unknown_extra_series_is_shown_not_dropped(self):
        _idx = pd.date_range("2026-10-15", periods=2, freq="D")
        _s = B.intl_series(self._intl(**{"新系列": pd.DataFrame({"close": [1.0, 2.0]}, index=_idx)}))
        assert any(x.group == B.INTL_OTHER_GROUP and x.name == "新系列" for x in _s)

    def test_chart_c_has_no_digit_percent_or_region_labels(self):
        """圖 C 區塊內零數值（含示意值）、零「現在指數位置」、不畫便宜／合理／偏貴區域標籤。"""
        _all = "".join(B.chart_c_texts())
        assert re.search(r"[0-9０-９%％]", _all) is None, _all
        assert "現在指數位置" not in _all
        # 標題（「大盤合理區間」）與客戶白話說明句本來就含「合理／便宜／偏貴」；其餘文字不得再出現區域標籤。
        _without_say = _all.replace(B.CHART_C_SAY, "").replace(B.CHART_C_TITLE, "")
        for _w in ("便宜", "合理", "偏貴", "▲"):
            assert _w not in _without_say, _w
        assert "研究框架，未啟用" in _all and "EPS" in _all


# ══════════════════════════════════════════════════════════════════
# 4. 水位卡首屏、查看依據
# ══════════════════════════════════════════════════════════════════
class TestWaterAndBasis:
    def test_water_card_first_screen_texts_have_no_percent(self):
        from shared.market_conclusion import CONCEPT_RISK_CAP, RISK_CAP_PENDING_TEXT
        for _t in (B.WATER_TITLE, B.WATER_VALUE, B.WATER_WHY, f"{CONCEPT_RISK_CAP}：{RISK_CAP_PENDING_TEXT}"):
            assert "%" not in _t and "％" not in _t, _t
        assert B.WATER_VALUE == "⬜ 尚未核准／無法判定"

    def test_water_basis_names_risk_cap_v2_and_not_approved(self):
        assert "risk_cap.v2" in B.WATER_BASIS_NOTE and "未經 C2b 核准" in B.WATER_BASIS_NOTE

    def test_all_six_fields_filled_in_every_state(self):
        _states = (
            B.build_market_risks(_readout({}, requested=False), None),
            B.build_market_risks(_readout({}, error="boom"), None),
            B.build_market_risks(_five({"long": "red", "mid": "gray"}), _all_up()),
        )
        _bases = [B.basis_risks(_r) for _r in _states]
        _bases += [B.basis_water(None, ""), B.basis_water(None, "boom"), B.basis_water(object(), ""),
                   B.basis_alerts(None, False, "", None), B.basis_alerts({"items": [{"text": "x"}]}, True, "", None),
                   B.basis_chart_a(None, None), B.basis_chart_b(None, "src"), B.basis_chart_b([], "src")]
        for _b in _bases:
            _rows = B.basis_rows(_b)
            assert [k for k, _ in _rows] == ["使用的資料", "資料日期", "規則／計算結果", "missing",
                                             "confidence／availability", "AI 是否參與"]
            assert all(v.strip() for _, v in _rows)

    def test_empty_field_fails_loud(self):
        with pytest.raises(ValueError):
            B.basis_rows(B.Basis("a", "b", "c", "", "e", "f"))

    def test_no_as_of_contract_is_written_not_replaced_by_refresh_time(self):
        assert B.basis_water(None, "").as_of == "⬜ 此判斷的資料日：契約未提供"
        assert B.basis_risks(B.build_market_risks(_five({}), _all_up())).as_of.startswith("⬜ 此判斷的資料日：契約未提供")

    def test_price_asof_label_helper_is_not_used(self):
        """`shared/price_asof_label` 是個股價用的，⛔ 不得套到市場頁。"""
        assert "price_asof_label" not in _SRC

    def test_chart_d_note_is_the_wireframe_sentence_and_ai_placeholder_has_no_engineering_tone(self):
        assert B.CHART_D_NOTE == "只顯示最需要注意的 3–5 項、方向、是否惡化。"
        assert B.HERO_AI_PLACEHOLDER == "🤖 AI 投資總結：⬜ 尚未提供"

    def test_ai_field_claims_only_what_is_true(self):
        assert B.AI_NOT_INVOLVED.startswith("不參與")
        for _n in ("gemini", "post_gemini", "ai_engine", "app_ai_service", "ai_fetcher"):
            assert _n not in _SRC, _n

    def test_data_date_text_uses_index_as_of_or_says_missing(self):
        assert B.data_date_text({"index_as_of": "2026-10-23"}).startswith("資料日：2026-10-23")
        assert B.data_date_text({}) == B.DATA_DATE_NOT_PROVIDED
        assert B.data_date_text(None) == B.DATA_DATE_NOT_PROVIDED

    def test_alerts_without_any_listable_source_say_so(self):
        assert B.alerts_has_listable_source(None, None) is False
        assert B.alerts_has_listable_source({"items": []}, SimpleNamespace(conflicts=())) is False
        assert B.alerts_has_listable_source({"items": [{"text": "x"}]}, None) is True
        assert B.alerts_has_listable_source(None, SimpleNamespace(conflicts=("c",))) is True
        assert B.ALERTS_NO_SOURCE == "⬜ 目前沒有可列的警示來源"
        for _t in B.STATIC_TEXTS:
            assert "沒有需要處理的事" not in _t


# ══════════════════════════════════════════════════════════════════
# 5. 字樣與對帳
# ══════════════════════════════════════════════════════════════════
class TestWording:
    def test_title_matches_nav4_label_without_importing_it(self):
        from shared import ia_nav4
        assert B.PAGE_TITLE == ia_nav4.PAGE4_LABELS[ia_nav4.P4_MARKET] == "📊 市場"
        for _n in ast.walk(_TREE):
            if isinstance(_n, ast.ImportFrom):
                assert "ia_nav4" not in (_n.module or "") and all("ia_nav4" not in a.name for a in _n.names)

    def test_subtitle_and_say_lines_are_verbatim_from_spec(self):
        _spec = (_ROOT / "docs" / "vnext" / "NEWUI_D25_A_FOUR_PAGE_SPEC_2026-10-27.md").read_text(encoding="utf-8")
        assert "現在適不適合投資？未來風險正在增加還是下降？" == B.PAGE_SUBTITLE
        for _s in (B.PAGE_SUBTITLE, B.CHART_A_SAY, B.CHART_B_SAY, B.CHART_C_SAY):
            assert _s in _spec, _s

    def test_conclusion_texts_are_not_defined_and_have_no_direction_words(self):
        assert B.CHART_A_CONCLUSION == "台股趨勢結論：⬜ 尚未定義"
        assert B.CHART_B_CONCLUSION == "國際趨勢結論：⬜ 尚未定義"
        for _t in (B.CHART_A_CONCLUSION, B.CHART_B_CONCLUSION, B.TREND_DEFINITION_NOTE, B.TREND_PENDING_WHY):
            for _w in ("偏多", "偏空", "多頭", "空頭", "看多", "看空", "上升趨勢", "下降趨勢"):
                assert _w not in _t

    def test_ma_disclaimer_is_verbatim(self):
        assert B.CHART_A_MA_DISCLAIMER == "均線為參考，不等於正式台股趨勢判斷。"

    def test_regime_scope_caption(self):
        assert B.REGIME_SCOPE_CAPTION == "市場位階，不是台股趨勢"

    def test_no_forbidden_old_ui_words(self):
        for _t in B.STATIC_TEXTS:
            for _w in ("舊版", "不使用", "切回", "legacy"):
                assert _w not in _t


# ══════════════════════════════════════════════════════════════════
# 6. 結構守衛
# ══════════════════════════════════════════════════════════════════
class TestStructure:
    def test_no_data_layer_import(self):
        for _n in ast.walk(_TREE):
            if isinstance(_n, ast.ImportFrom):
                assert not (_n.module or "").startswith("src.data"), ast.unparse(_n)
            if isinstance(_n, ast.Import):
                assert not any(_a.name.startswith("src.data") for _a in _n.names)

    def test_chart_a_cache_read_is_behind_the_loaded_check_not_a_checkbox(self):
        """📌 UI-M 修正（總管 QA-B）：圖 A／圖 B 去掉 checkbox gate。等義的新守衛 ——
        `get_twii_trend_view` 只能出現在 `if not today.upstream_requested(...) … else:` 的 else 分支（未載入不讀、不畫過期值）；
        `_market_blocks` 內不再有任何 checkbox。"""
        assert "checkbox" not in _SRC
        _fn = next(n for n in _TREE.body if isinstance(n, ast.FunctionDef) and n.name == "render_chart_a")
        _reads = [c for c in ast.walk(_fn) if isinstance(c, ast.Call)
                  and getattr(c.func, "attr", "") == "get_twii_trend_view"]
        assert len(_reads) == 1
        _ifs = [i for i in ast.walk(_fn) if isinstance(i, ast.If) and "upstream_requested" in ast.unparse(i.test)]
        assert len(_ifs) == 1
        assert any(c is _reads[0] for st_ in _ifs[0].orelse for c in ast.walk(st_))
        assert not any(c is _reads[0] for st_ in _ifs[0].body for c in ast.walk(st_))

    def test_no_gate_keys_left(self):
        assert not hasattr(B, "SS_GATE_CHART_A") and not hasattr(B, "SS_GATE_CHART_B")

    def test_risk_cap_numbers_are_never_read(self):
        for _tok in ("exposure_limit_pct", "cap_text", "risk_cap_face_text",
                     "risk_cap_detail_text", "risk_cap_disclosure", ".caps", "RISK_CAP_STATE_FILE",
                     "final_lo", "final_hi", "range_text"):
            assert _tok not in _SRC, _tok

    def test_hero_has_four_cards_and_expanders_are_not_nested_in_expanders(self):
        _fn = next(n for n in _TREE.body if isinstance(n, ast.FunctionDef) and n.name == "render_hero")
        assert "st.columns(4)" in ast.unparse(_fn)
        # 水位卡的「原有出手區間」只放在 `render_basis(..., extra=_original_range)` 的 callback 裡：
        # 畫 `exposure_tile` 的呼叫必須只出現在內層函式 `_original_range`（⇒ 只在「🔍 查看依據」展開區內）。
        _calls = [c for c in ast.walk(_fn) if isinstance(c, ast.Call) and any(
            isinstance(a, ast.Name) and a.id == "exposure_tile" for a in c.args)]
        assert len(_calls) == 1
        _inner = next(n for n in ast.walk(_fn) if isinstance(n, ast.FunctionDef) and n.name == "_original_range")
        assert any(c is _calls[0] for c in ast.walk(_inner))

    def test_blocks_do_not_recompute_lamp_rules(self):
        for _tok in ("classify_danger", "aggregate_level", "danger_exceedance", "BUCKET_LEVEL_LABEL"):
            assert _tok not in _SRC, _tok
