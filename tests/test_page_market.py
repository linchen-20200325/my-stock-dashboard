"""tests/test_page_market.py — 「📊 大盤」頁（`src/ui/views/page_market.py`）守衛。

客戶 2026-10-25 裁示（Q1=C／Q2-1／Q2-2／Q2-3／Q3=A／Q4=C）逐條釘住：
  · 結論句只用「；」並列、⛔ 但／因此／所以；缺值照實寫（L0 `shared/market_conclusion.py`）。
  · Risk Cap 卡位字樣逐字、⛔ 本頁不讀任何上限數字。
  · 趨勢兩卡只寫「尚未定義」、⛔ 燈色／多空字樣。
  · 卡①～③與「🚦 今天」頁是**同一段程式、同一組輸入**（不是第二份）。
  · 本頁⛔ 三欄摘要；導航登記一致；「🚦 今天」仍在。
"""
from __future__ import annotations

import ast
import pathlib
import textwrap
from types import SimpleNamespace

import pytest

from shared import ia_nav
from shared import market_conclusion as MC

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_PAGE = _ROOT / "src" / "ui" / "views" / "page_market.py"
_SRC = _PAGE.read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)


# ══════════════════════════════════════════════════════════════════
# 結論句（W2，純函式）
# ══════════════════════════════════════════════════════════════════
class TestConclusionSentence:
    _CASES = (
        (None, None),
        ("", "  "),
        ("多頭", "黃（2 桶黃　·　最差是「中期」　·　只根據 13／16 項有資料）"),
        ("尚未載入（未評估）", "讀取失敗（未評估）"),
    )

    @pytest.mark.parametrize("regime, danger", _CASES)
    def test_no_causal_or_contrast_connectors(self, regime, danger):
        _s = MC.build_market_conclusion(regime_text=regime, danger_text=danger)
        for _w in ("但", "因此", "所以", *MC.FORBIDDEN_CONNECTORS):
            assert _w not in _s, f"結論句出現禁用連接詞 {_w!r}：{_s}"

    @pytest.mark.parametrize("regime, danger", _CASES)
    def test_five_clauses_in_order_joined_only_by_semicolon(self, regime, danger):
        _s = MC.build_market_conclusion(regime_text=regime, danger_text=danger)
        assert _s.endswith("。")
        _parts = _s[:-1].split(MC.CLAUSE_SEP)
        assert [p.split("：", 1)[0] for p in _parts] == list(MC.CONCEPT_ORDER)

    def test_missing_is_written_explicitly_not_neutral(self):
        _s = MC.build_market_conclusion(regime_text=None, danger_text="")
        assert f"{MC.CONCEPT_REGIME}：{MC.MISSING_TEXT}" in _s
        assert f"{MC.CONCEPT_DANGER}：{MC.MISSING_TEXT}" in _s
        for _neutral in ("中性", "震盪", "正常", "綠"):
            assert _neutral not in _s

    def test_trend_and_risk_cap_clauses_are_fixed(self):
        _s = MC.build_market_conclusion(regime_text="多頭", danger_text="紅")
        assert f"{MC.CONCEPT_TW_TREND}：尚未定義" in _s
        assert f"{MC.CONCEPT_INTL_TREND}：尚未定義" in _s
        assert MC.RISK_CAP_PENDING_TEXT in _s

    def test_risk_cap_clause_is_exactly_the_customer_wording(self):
        """QA-A B1：子句逐字「風險上限：獨立顯示待 C2b＋RC-VISIBILITY Gate」，⛔ 不附任何指路／數字。"""
        assert MC.RISK_CAP_CLAUSE_TEXT == "獨立顯示待 C2b＋RC-VISIBILITY Gate"
        _s = MC.build_market_conclusion(regime_text="多頭", danger_text="紅")
        assert _s.endswith("；風險上限：獨立顯示待 C2b＋RC-VISIBILITY Gate。")
        assert "能不能出手" not in _s and "數字" not in _s

    @pytest.mark.parametrize("bad", ("多頭但轉弱", "黃，因此保守", "紅所以減碼", "a；b"))
    def test_forbidden_input_fails_loud(self, bad):
        with pytest.raises(ValueError):
            MC.build_market_conclusion(regime_text=bad, danger_text=None)

    def test_signature_does_not_accept_risk_cap_or_trend_values(self):
        import inspect
        _params = set(inspect.signature(MC.build_market_conclusion).parameters)
        assert _params == {"regime_text", "danger_text"}


# ══════════════════════════════════════════════════════════════════
# Risk Cap 卡位（Q2-2）與趨勢兩卡（Q3=A）
# ══════════════════════════════════════════════════════════════════
class TestRiskCapAndTrendCards:
    def test_risk_cap_text_is_exact(self):
        assert MC.CONCEPT_RISK_CAP == "風險上限"
        assert MC.RISK_CAP_PENDING_TEXT == "獨立顯示待 C2b＋RC-VISIBILITY Gate"

    def test_page_never_reads_risk_cap_values(self):
        """本頁 source 不得碰上限數字的任何欄位（卡①的顯示走 `page_today` 同一段程式，不在本檔）。"""
        for _tok in ("exposure_limit_pct", "cap_text", "risk_cap_face_text",
                     "risk_cap_detail_text", "risk_cap_disclosure", ".caps", "RISK_CAP_STATE_FILE"):
            assert _tok not in _SRC, f"page_market.py 出現 {_tok!r}"

    def _plain_card_calls(self):
        return [_n for _n in ast.walk(_TREE) if isinstance(_n, ast.Call)
                and getattr(_n.func, "id", "") == "_render_plain_card"]

    def test_plain_cards_only_take_constants(self):
        _calls = self._plain_card_calls()
        assert len(_calls) == 3, "趨勢兩卡＋風險上限卡位應各一次"
        for _c in _calls:
            assert all(isinstance(_a, ast.Name) for _a in _c.args), ast.unparse(_c)
            assert not _c.keywords
        _args = {tuple(_a.id for _a in _c.args) for _c in _calls}
        assert ("CONCEPT_RISK_CAP", "RISK_CAP_PENDING_TEXT") in _args
        assert ("CONCEPT_TW_TREND", "TREND_UNDEFINED_TEXT", "TREND_PENDING_WHY") in _args
        assert ("CONCEPT_INTL_TREND", "TREND_UNDEFINED_TEXT", "TREND_PENDING_WHY") in _args

    def test_trend_texts_have_no_direction_or_light_words(self):
        from src.ui.views import page_market as M
        assert M.TREND_UNDEFINED_TEXT == "尚未定義"
        for _txt in (M.TREND_UNDEFINED_TEXT, M.TREND_PENDING_WHY):
            for _w in ("多", "空", "燈", "綠", "黃", "紅", "偏", "漲", "跌"):
                assert _w not in _txt, f"趨勢卡字樣含 {_w!r}：{_txt}"


# ══════════════════════════════════════════════════════════════════
# 卡①～③：與「🚦 今天」同一段程式、同一組輸入
# ══════════════════════════════════════════════════════════════════
def _fake_alloc(*, with_cap: bool):
    from src.ui.views.risk_cap_gate import SYSTEM_RISK_CAP_NAME
    return SimpleNamespace(
        is_loaded=True, posture="持平", range_text="40%～60%", drivers=("健康分 55",),
        cap_text="🔒 上限 37%",
        caps=((SimpleNamespace(name=SYSTEM_RISK_CAP_NAME),) if with_cap else ()),
        risk_cap_disclosure=None, conflicts=())


_SCENARIOS = {
    "cold": dict(alloc=(None, ""), regime=(None, "")),
    "alloc_error": dict(alloc=(None, "RuntimeError('boom')"), regime=(None, "RuntimeError('x')")),
    "live_with_cap": dict(
        alloc=(_fake_alloc(with_cap=True), ""),
        regime=({"regime": "bull", "light": "🟢", "source": "warroom", "health": 60,
                 "is_loaded": True, "trend_regime": None, "defense": False,
                 "exposure_limit_pct": 37.0, "traffic_light": None}, "")),
    "live_no_cap": dict(
        alloc=(_fake_alloc(with_cap=False), ""),
        regime=({"regime": "bull", "light": "🟢", "source": "warroom", "health": 60,
                 "is_loaded": True, "trend_regime": None, "defense": False,
                 "exposure_limit_pct": None, "traffic_light": None}, "")),
}


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_verdict_cards_identical_to_today(name, monkeypatch):
    """兩頁各跑一次：`build_verdict_tiles` 收到的引數相同、畫出來的卡①②③逐欄相同。"""
    from src.ui.views import page_market as M
    from src.ui.views import page_today as P

    _sc = _SCENARIOS[name]
    monkeypatch.setattr(P, "_load_allocation", lambda: _sc["alloc"])
    monkeypatch.setattr(P, "_load_regime", lambda: _sc["regime"])
    monkeypatch.setattr(P, "_load_breadth_proxy", lambda: None)

    _calls: list[dict] = []
    _real = P.build_verdict_tiles

    def _rec(**kw):
        _calls.append(kw)
        return _real(**kw)

    monkeypatch.setattr(P, "build_verdict_tiles", _rec)
    _drawn: list = []
    monkeypatch.setattr(P, "_render_one", lambda t: _drawn.append(t))
    monkeypatch.setattr(P, "_render_tiles", lambda ts, cols=3: _drawn.extend(ts))
    # 兩頁共用的互動元件與 v2 樣式在這裡不是受測對象 —— 換成 no-op（bare mode 下 form 也不會送出）。
    monkeypatch.setattr(P, "_render_update_form", lambda s: None)
    monkeypatch.setattr(P, "_inject_v2_css", lambda: None)
    monkeypatch.setattr(P, "load_sheet_binding", lambda: (None, "stub"))
    monkeypatch.setattr(P, "load_trading_day_status", lambda: (None, "stub"))

    P.render_page_today()
    _today_kw = _calls[-1]
    _today_tiles = {t.card.key: t for t in _drawn if t.card.key.startswith("verdict.")}
    _drawn.clear()
    M.render_page_market()
    _market_kw = _calls[-1]
    _market_tiles = {t.card.key: t for t in _drawn if t.card.key.startswith("verdict.")}

    assert _today_kw == _market_kw
    assert set(_today_tiles) == {"verdict.exposure", "verdict.danger", "verdict.regime"}
    assert _today_tiles == _market_tiles


# ══════════════════════════════════════════════════════════════════
# 子句取自卡面（regime_clause / danger_clause）
# ══════════════════════════════════════════════════════════════════
class TestClausesComeFromTheCards:
    def _tiles(self, **kw):
        from src.ui.views import page_today as P
        _base = dict(alloc=None, alloc_error="", danger=None, danger_error="",
                     danger_requested=False, regime=None, regime_error="")
        _base.update(kw)
        return P.build_verdict_tiles(**_base)

    def test_cold_session_says_not_loaded(self):
        from src.ui.views import page_market as M
        _e, _d, _r = self._tiles()
        assert M.regime_clause(_r) == "尚未評估（尚未載入）"
        assert M.danger_clause(_d) == "尚未載入"

    def test_breadth_unevaluated_regime_says_why(self):
        from shared import regime_arbiter as RA
        from src.ui.views import page_market as M
        _reg = {"source": RA.SOURCE_UNEVALUATED_BREADTH, "is_loaded": False, "regime": "unknown",
                "light": "⬜", "health": None, "exposure_limit_pct": None}
        _e, _d, _r = self._tiles(regime=_reg)
        _c = M.regime_clause(_r, _reg)
        assert _c == "尚未評估（缺真實市場廣度，代理估算值不計分）"
        assert "可重跑" not in _c   # 卡上 #7 徽章與原因句矛盾，⛔ 不帶進結論句

    def test_gray_danger_uses_card_badge(self):
        from src.ui.views import page_market as M
        _e, _d, _r = self._tiles(danger=("gray", "尚未載入資料", (0, 16)), danger_requested=True)
        assert M.danger_clause(_d) == f"尚未載入（{M.card_badge_text(_d)}）"
        assert M.card_badge_text(_d) in M.danger_clause(_d)

    def test_live_danger_uses_card_words(self):
        from src.ui.views import page_market as M
        _bz = {"yellow": ("黃", "#fab219")}
        _e, _d, _r = self._tiles(danger=("yellow", "1 桶黃　·　最差是「中期」", (16, 16)),
                                 danger_requested=True, band_zh_color=_bz)
        assert M.danger_clause(_d) == "黃（1 桶黃　·　最差是「中期」）"

    def test_partial_danger_keeps_coverage_text(self):
        from src.ui.views import page_market as M
        _bz = {"yellow": ("黃", "#fab219")}
        _det = "1 桶黃　·　最差是「中期」　·　只根據 13／16 項有資料"
        _e, _d, _r = self._tiles(danger=("yellow", _det, (13, 16)),
                                 danger_requested=True, band_zh_color=_bz)
        assert M.danger_clause(_d) == f"黃（{_det}）"

    def test_failed_states_say_failed(self):
        from src.ui.views import page_market as M
        _e, _d, _r = self._tiles(danger_error="RuntimeError('x')", regime_error="RuntimeError('y')")
        assert M.danger_clause(_d) == "尚未載入（取得失敗）"
        assert M.regime_clause(_r) == "尚未評估（取得失敗）"


def _all_states():
    from shared import ui_state as U
    return [U.UI_IDLE, U.UI_LOADING, U.UI_FAILED, U.UI_EMPTY, U.UI_MISSING_RETRYABLE,
            U.UI_NOT_APPLICABLE, U.UI_PARTIAL, U.UI_DEGRADED, U.UI_UNWIRED, U.UI_LIVE]


def test_state_enumeration_is_complete():
    """列舉表涵蓋 L0 全部卡態 —— L0 多一態，本檔就要回來補。"""
    from shared import ui_state as U
    assert set(_all_states()) == set(U.UI_STATE_META)


@pytest.mark.parametrize("state", _all_states())
@pytest.mark.parametrize("which", ("regime", "danger"))
def test_every_card_state_maps_to_card_wording(state, which):
    """QA-B #1：每一種卡態都對到卡上看得到的字（徽章字／卡面那句），⛔ 沒有一態掉成「無資料」或中性字。"""
    from shared import ui_state as U
    from src.ui.tabs.tab_today import Card, Note
    from src.ui.views import page_market as M
    from src.ui.views.page_today import Tile
    _prefix = "市場位階：" if which == "regime" else "指標危險度："
    _cov = (13, 16) if state == U.UI_PARTIAL else None
    if state == U.UI_LIVE:
        _card = Card(key=f"verdict.{which}", label="x", state=state, value="多頭" if which == "regime" else "1 桶黃")
    else:
        _card = Card(key=f"verdict.{which}", label="x", state=state,
                     note=Note(now=f"**{_prefix}尚未評估**", why="測試用原因", where="測試用出口"))
    _tile = Tile(_card, signal_text=("黃" if state in (U.UI_DEGRADED, U.UI_LIVE, U.UI_PARTIAL) else ""),
                 badge_coverage=_cov,
                 facts=((M.today.DANGER_DETAIL_FACT_KEY, "1 桶黃"),) if state == U.UI_PARTIAL else ())
    _c = M.regime_clause(_tile, None) if which == "regime" else M.danger_clause(_tile)
    assert _c and _c.strip()
    assert _c != MC.MISSING_TEXT
    for _w in ("中性", "正常", "震盪"):
        assert _w not in _c
    if state != U.UI_LIVE and not (which == "danger" and state == U.UI_PARTIAL):
        assert M.card_badge_text(_tile) in _c, f"{state}: {_c}"
    # 放進結論句也組得起來（不含禁用連接詞）
    MC.build_market_conclusion(regime_text=_c, danger_text=_c)


# ══════════════════════════════════════════════════════════════════
# 原始資料（R12 白名單）
# ══════════════════════════════════════════════════════════════════
class TestRawData:
    def test_fmt_value(self):
        from src.ui.views import page_market as M
        assert M.fmt_value(None) == "無資料"
        assert M.fmt_value("") == "無資料"
        assert M.fmt_value(float("nan")).startswith("無資料")
        assert M.fmt_value(True) == "是"
        assert M.fmt_value(1234.5, "%") == "1,234.50%"
        assert M.fmt_value(0.0) == "0.00"   # 真的 0 照印，⛔ 不當缺值

    def test_whitelist_has_no_conclusion_fields(self):
        from src.ui.views import page_market as M
        _bad = {"regime", "label", "action", "score", "market_score", "exposure",
                "exposure_pct", "signal_text", "status", "confidence", "color"}
        # 國發會景氣對策信號的「分數」是官方發布的原始值（不是本站的評分），明文豁免這一條路徑。
        _official = {("ndc_signal", "score")}
        for _spec in (*M.X5_FIELDS, *M.X6_FIELDS, *M.X7_FIELDS):
            if _spec[2] in _official:
                assert "官方原始值" in _spec[4]
                continue
            assert not (set(_spec[2]) & _bad), _spec

    def test_bias240_estimated_is_marked(self):
        from src.ui.views import page_market as M
        _s = {"bias_info": {"bias_240": 3.2, "is_estimated": True, "data_days": 180}}
        _row = next(r for r in M.raw_rows(_s, M.X5_FIELDS) if "BIAS240" in r[0])
        assert _row[1] == "3.20%" and _row[2] == "估算・180 天資料"

    @pytest.mark.parametrize("days, want", ((0, "估算・天數不明"), (None, "估算・天數不明"),
                                            ("x", "估算・天數不明"), (90, "估算・90 天資料")))
    def test_bias240_estimated_days_via_l2_helper(self, days, want):
        from src.ui.views import page_market as M
        _bi = {"bias_240": 1.0, "ma240": 20000.0, "is_estimated": True}
        if days is not None:
            _bi["data_days"] = days
        _rows = {r[0]: r for r in M.raw_rows({"bias_info": _bi}, M.X5_FIELDS)}
        assert _rows["年線乖離（BIAS240）"][2] == want
        assert _rows["MA240"][2] == want      # MA240 本身也是估算均線，一併標
        assert "無資料 天" not in "".join(r[2] for r in _rows.values())

    def test_bias_not_estimated_has_no_mark(self):
        from src.ui.views import page_market as M
        _rows = {r[0]: r for r in M.raw_rows({"bias_info": {"bias_240": 1.0, "ma240": 1.0,
                                                            "is_estimated": False}}, M.X5_FIELDS)}
        assert _rows["MA240"][2] == "" and _rows["年線乖離（BIAS240）"][2] == ""

    def test_proxy_breadth_is_marked(self):
        from src.ui.views import page_market as M
        _s = {"jingqi_info": {"avg": 55.0, "is_proxy": True, "label": "🟢 多頭積極"}}
        _rows = M.raw_rows(_s, M.X5_FIELDS)
        assert any("代理" in r[2] for r in _rows)
        assert not any("多頭" in r[1] for r in _rows)

    def test_missing_session_is_explicit(self):
        from src.ui.views import page_market as M
        assert all(r[1] == "無資料" for r in M.raw_rows({}, M.X7_FIELDS))

    def test_unobserved_inst_is_not_zero(self):
        from shared.inst_net import InstNetDict
        from src.ui.views import page_market as M
        _inst = InstNetDict({"外資及陸資": {"net": 0.0}, "投信": {"net": 12.5}},
                            unobserved_net={"外資及陸資"})
        _rows = dict((r[0], r[1]) for r in M.inst_rows({"cl_data": {"inst": _inst}}))
        assert _rows["外資及陸資"] == "無資料（未觀測）"
        assert _rows["投信"] == "12.50 億"

    def test_inst_rows_show_data_date_including_fallback(self):
        from src.ui.views import page_market as M
        _now = M.inst_rows({"cl_data": {"inst": {"投信": {"net": 1.0}}, "inst_date": "20261024"}})
        assert "資料日 20261024" in _now[0][2] and _now[0][2].startswith("本輪")
        _fb = M.inst_rows({"cl_data": {"inst": {}}, "_last_inst": {"投信": {"net": 2.0}},
                           "_last_inst_date": "20261023"})
        assert "上一次有效值" in _fb[0][2] and "資料日 20261023" in _fb[0][2]

    def test_frame_last_close(self):
        import pandas as pd
        from src.ui.views import page_market as M
        _df = pd.DataFrame({"close": [1.0, 2.0, None]},
                           index=pd.to_datetime(["2026-10-20", "2026-10-21", "2026-10-22"]))
        assert M.frame_last_close(_df) == ("2.00", "2026-10-21", "3")
        assert M.frame_last_close(None) == ("無資料", "無資料", "無資料")

    def test_leading_table_excludes_short_selling(self):
        from src.ui.views import page_market as M
        assert "融券餘額" not in {c for c, _ in M.LEADING_COLUMNS}
        assert dict(M.LEADING_COLUMNS)["選PCR"] == "法人估算"


class TestCrossReferences:
    def test_report_pointer_follows_state(self):
        from src.ui.views import page_market as M
        assert "還沒按過更新" in M.report_pointer(None)
        assert "上一次更新的結果" in M.report_pointer(SimpleNamespace(started_at="10/25 09:00"))
        assert "上方" not in M.report_pointer(None)

    def test_x3_points_at_the_real_place(self):
        from src.ui.views import page_market as M
        assert "下方「資料來源與完整度」" not in M.X3_TEXT
        assert "更新鈕下方" in M.X3_TEXT

    def test_old_ui_pointer_strings_exist_in_app(self):
        from src.ui.views import page_market as M
        _app = (_ROOT / "app.py").read_text(encoding="utf-8")
        for _s in (M.OLD_UI_NAV_RADIO, M.OLD_UI_NAV_OFF, M.OLD_UI_MARKET_TAB):
            assert _s in _app, _s
        # NAV-1 回修（QA MAJOR-1）：三處引用改經 `_old_ui_pointer()`（legacy／無旗標 ⇒ 仍回 `OLD_UI_POINTER` 原句，
        # 預設模式 ⇒ 誠實句）。引用次數門檻不變（≥3），另釘 legacy 路徑確實回原句。
        assert _SRC.count("{_old_ui_pointer()}") >= 3
        assert M._old_ui_pointer() == M.OLD_UI_POINTER   # 無旗標（單元測試）＝legacy 原句
        assert "見「🌍 市場環境」舊分頁" not in _SRC

    def test_x1_source_is_human_wording(self):
        from shared import regime_arbiter as RA
        from src.ui.views import page_market as M
        for _code in (RA.SOURCE_UNLOADED, RA.SOURCE_UNEVALUATED_BREADTH, RA.SOURCE_BULL_SCORE,
                      RA.SOURCE_DEFENSE_HEALTH, RA.SOURCE_DEFENSE_FUTURES, RA.SOURCE_BEAR_TREND,
                      RA.SOURCE_NEUTRAL_FALLTHROUGH, RA.SOURCE_FILE_RULE_ENGINE):
            _t = M.regime_source_text(_code)
            assert _code not in _t and _t.strip()
        assert M.regime_source_text(None) == "無資料"
        assert "zzz" in M.regime_source_text("zzz")   # 未登錄 ⇒ 照實講代碼，⛔ 不猜


# ══════════════════════════════════════════════════════════════════
# 版面：⛔ 三欄摘要、⛔ 舊 UI 結論、重區塊有 gate
# ══════════════════════════════════════════════════════════════════
class TestLayoutRules:
    def test_no_three_column_summary(self):
        for _tok in ("build_summary_tiles", "today.summary", "build_today_blocks", "LEAF1_SUMMARY_NOTE"):
            assert _tok not in _SRC

    def test_no_old_ui_conclusion_sources(self):
        for _tok in ("strategy_conclusion", "parallel_verdict", "'action'", "\"action\"",
                     "get('label')", "['label']", "\"label\"", "market_score", "exposure_pct"):
            assert _tok not in _SRC, _tok

    def test_heavy_blocks_are_checkbox_gated(self):
        _gates = [_n for _n in ast.walk(_TREE) if isinstance(_n, ast.Call)
                  and getattr(_n.func, "attr", "") == "checkbox"]
        assert len(_gates) >= 3
        for _n in ast.walk(_TREE):
            if isinstance(_n, ast.Call) and getattr(_n.func, "attr", "") in ("line_chart", "dataframe"):
                # 每一次畫圖／畫逐日表都必須在某個 `if st.checkbox(...)` 底下
                assert self._under_checkbox(_n), ast.unparse(_n)

    def _under_checkbox(self, target) -> bool:
        for _if in ast.walk(_TREE):
            if isinstance(_if, ast.If) and "checkbox" in ast.unparse(_if.test):
                if any(_c is target for _c in ast.walk(_if)):
                    return True
        return False

    def test_no_data_layer_import(self):
        for _n in ast.walk(_TREE):
            if isinstance(_n, ast.ImportFrom):
                assert not (_n.module or "").startswith("src.data"), ast.unparse(_n)
            if isinstance(_n, ast.Import):
                assert not any(_a.name.startswith("src.data") for _a in _n.names)


# ══════════════════════════════════════════════════════════════════
# 導航（Q1=C：大盤排第一、「🚦 今天」照留）
# ══════════════════════════════════════════════════════════════════
class TestNavigation:
    def test_market_is_first_and_today_stays(self):
        _ids = list(ia_nav.PAGE_LABELS)
        assert _ids[0] == ia_nav.PAGE_MARKET
        assert ia_nav.PAGE_LABELS[ia_nav.PAGE_MARKET] == "📊 大盤"
        assert ia_nav.PAGE_LABELS[ia_nav.PAGE_TODAY] == "🚦 今天"
        # 📌 👤 我的 P1（2026-10-25 DEC-083 Q1=A，有意識的修改，⛔ 不是漏改）：
        #   ~~{"market", "today", "find", "inspect", "hold", "why"}~~ → 多第 7 頁「me」（排最後；大盤仍是第一頁）。
        assert set(_ids) == {"market", "today", "find", "inspect", "hold", "why", "me"}
        assert _ids[-1] == ia_nav.PAGE_ME

    def test_app_routes_market(self):
        _app = (_ROOT / "app.py").read_text(encoding="utf-8")
        assert "_IA_MARKET: _ia_view_market" in _app
        assert "from src.ui.views.page_market import render_page_market" in _app
        assert "_IA_TODAY: _ia_view_today" in _app

    def test_qa_section_label_matches_page_why(self):
        from src.ui.views import page_why
        assert ia_nav.SECTION_LABELS[ia_nav.SECTION_WHY_QA] == page_why.LEAF_QA_TITLE
        assert ia_nav.where_to_find(ia_nav.SECTION_WHY_QA) == "「🩺 資料中心 › 📖 憑什麼 › AI 問答」"   # D2（DEC-090 ⑦）：指路句多帶方向名

    def test_data_center_pointer_uses_ssot(self):
        assert "ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)" in _SRC


# ══════════════════════════════════════════════════════════════════
# 冒煙（slow lane）：整頁畫得出來
# ══════════════════════════════════════════════════════════════════
@pytest.mark.slow
def test_page_mounts_clean(tmp_path):
    from streamlit.testing.v1 import AppTest

    _script = tmp_path / "_market_view.py"
    _script.write_text(textwrap.dedent("""
        from src.ui.views.page_market import render_page_market
        render_page_market()
    """), encoding="utf-8")
    _at = AppTest.from_file(str(_script), default_timeout=120)
    _at.run()
    assert not _at.exception, f"page_market mount 有 uncaught exception: {_at.exception}"
    _md = [_m.value for _m in _at.markdown]
    _joined = "\n".join(_md)
    assert ia_nav.action_label(ia_nav.ACTION_UPDATE_TODAY) in [_b.label for _b in _at.button]
    # Risk Cap 卡位：標題後緊接著逐字狀態字樣
    _i = _md.index("**風險上限**")
    assert _md[_i + 1] == "獨立顯示待 C2b＋RC-VISIBILITY Gate"
    for _t in ("**台股趨勢**", "**國際趨勢**"):
        assert _md[_md.index(_t) + 1] == "尚未定義"
    # 結論句
    assert any(_m.startswith("市場位階：") and "；台股趨勢：尚未定義；" in _m for _m in _md)
    # ⛔ 三欄摘要（今天頁的「位階／動能／風險」那一段）
    assert "三欄摘要" not in _joined
    assert "位階 / 動能 / 風險" not in _joined
    # 原始資料區標題
    _exp = [_e.label for _e in _at.expander]
    assert any("原始資料，不構成趨勢判斷" in _l and "台股" in _l for _l in _exp)
    assert any("原始資料，不構成趨勢判斷" in _l and "國際" in _l for _l in _exp)


@pytest.mark.slow
def test_page_renders_with_populated_session(tmp_path):
    """塞一份有值的 session：原始資料區畫得出來、Risk Cap 卡位仍不出現數字。"""
    from streamlit.testing.v1 import AppTest

    _script = tmp_path / "_market_view_full.py"
    _script.write_text(textwrap.dedent("""
        import pandas as pd
        import streamlit as st
        from src.ui.views.page_market import render_page_market
        _idx = pd.to_datetime(["2026-10-21", "2026-10-22"])
        st.session_state.setdefault("cl_data", {
            "tw": {"台股加權指數": pd.DataFrame({"close": [22000.0, 22100.0]}, index=_idx)},
            "intl": {"10Y公債殖利率": pd.DataFrame({"close": [4.1, 4.2]}, index=_idx)},
            "tech": {}, "inst": {"投信": {"net": 3.0}}, "margin": 3123.4, "adl": None,
        })
        st.session_state.setdefault("macro_info", {"vix": {"current": 17.3, "date": "2026-10-22",
                                                     "source": "yfinance:^VIX"}})
        st.session_state.setdefault("bias_info", {"bias_240": 5.5, "is_estimated": True,
                                                    "data_days": 190})
        st.session_state.setdefault("li_latest", pd.DataFrame(
            {"日期": ["10/22"], "外資": [1.0], "選PCR": [0.9], "融券餘額": [123.0]}))
        st.session_state.setdefault("li_retain_meta", {"rounds": 2, "since": "2026-10-24 09:00:00"})
        render_page_market()
    """), encoding="utf-8")
    _at = AppTest.from_file(str(_script), default_timeout=120)
    _at.run()
    assert not _at.exception, f"{_at.exception}"
    _md = [_m.value for _m in _at.markdown]
    _joined = "\n".join(_md)
    assert "22,100.00" in _joined and "17.30" in _joined and "估算・190 天資料" in _joined
    _i = _md.index("**風險上限**")
    assert _md[_i + 1] == "獨立顯示待 C2b＋RC-VISIBILITY Gate"
    assert "還沒按過更新" in _joined                 # X10 指路照實（沒有報告）
    assert "unloaded" not in _joined                  # X1 不出機器碼
    from src.ui.views.page_market import SS_GATE_LEADING
    _at.checkbox(key=SS_GATE_LEADING).check().run()
    assert not _at.exception
    _warn = "\n".join(_w.value for _w in _at.warning)
    assert "最近 2 輪抓取都失敗" in _warn and "2026-10-24 09:00" in _warn
    assert all("融券餘額" not in list(_d.value.columns) for _d in _at.dataframe)
