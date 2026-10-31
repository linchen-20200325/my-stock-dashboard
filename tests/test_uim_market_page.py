"""tests/test_uim_market_page.py — UI-M：📊 市場頁整頁（AppTest）＋與 UI-M 之前（d0482441）的保留區塊 parity。

守什麼：
  · 冷啟動：第一列全灰「⬜ 尚未載入，請按更新」、沒有任何紅字（未載入≠真出錯）。
  · 水位卡首屏無百分比；原有出手區間（含 risk_cap.v2）只在「🔍 查看依據」展開區內。
  · 圖 A／圖 B 預設直接畫（無 gate）；未載入時不讀快取、不畫（不顯示過期值）；灰（讀不到）與紅（真例外）分離；過期有警示。
  · hero「今日主要風險」與圖 D 同源（頁面層）；⚡ 區沒有來源時寫「⬜ 目前沒有可列的警示來源」。
  · parity：被保留的區塊（今日結論句、各展開區、所有未動的 helper）與 UI-M 之前逐字相同。
    「UI-M 之前」的原始碼由 `tests/test_uim_revert_chain.py::uim_revert_for` 還原（不依賴 git）。
"""
from __future__ import annotations

import ast
import pathlib
import re

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.services import market_twii_view_service as S
from src.ui.views import _market_blocks as B
from src.ui.views import page_today as P

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_REL = "src/ui/views/page_market.py"
_SCRIPT = "from src.ui.views.page_market import render_page_market\nrender_page_market()\n"

_IDX = pd.to_datetime(["2026-10-21", "2026-10-22", "2026-10-23"])
_LOADED = {
    "cl_data": {
        "tw": {"台股加權指數": pd.DataFrame({"close": [22000.0, 22100.0, 22200.0]}, index=_IDX)},
        "intl": {"道瓊工業 DJI": pd.DataFrame({"close": [40000.0, 40100.0, 39900.0]}, index=_IDX),
                 "10Y公債殖利率": pd.DataFrame({"close": [4.1, 4.2, 4.3]}, index=_IDX),
                 "美元指數 DXY": pd.DataFrame({"close": [99.0, 99.5, 100.0]}, index=_IDX)},
        "tech": {}, "inst": {"外資及陸資": {"net": -50.0}}, "margin": 3123.4, "adl": None},
    "macro_info": {"vix": {"current": 35.0, "date": "2026-10-22", "source": "yfinance:^VIX"},
                   "us10y": {"current": 4.8, "date": "2026-10-22"},
                   "ism_pmi": {"value": 44.0, "date": "2026-09-01"},
                   "us_core_cpi": {"yoy": 2.0, "date": "2026-09-01"}},
    "mkt_info": {"index_price": 22200.0, "index_as_of": "2026-10-23", "ma5": 22100.0, "ma60": 21500.0,
                 "ma120": 20500.0, "ma200": None, "ma200_status": "歷史不足"},
    "bias_info": {"bias_240": 5.5, "is_estimated": True, "data_days": 190},
}


def _run(tmp_path, session=None, script=_SCRIPT, name="_m.py") -> AppTest:
    _f = tmp_path / name
    _f.write_text(script, encoding="utf-8")
    _at = AppTest.from_file(str(_f), default_timeout=120)
    for _k, _v in (session or {}).items():
        _at.session_state[_k] = _v
    _at.run()
    return _at


_TEXT_KINDS = ("Markdown", "Caption", "Error", "Warning", "Success", "Info", "Text", "Code")
#: `st.line_chart` 在 AppTest 樹裡的元素型別名隨 Streamlit 版本不同（1.59：vega_lite_chart；舊版：arrow_*）⇒ 全收。
_CHART_TYPES = ("vega_lite_chart", "arrow_vega_lite_chart", "line_chart", "arrow_line_chart")


def _n_charts(at) -> int:
    return sum(len(at.get(_t)) for _t in _CHART_TYPES)


def _flat(block, in_exp=False):
    """AppTest 樹 → `(類別名, 值, 是否在 expander 內)`。"""
    for _ch in block.children.values():
        if hasattr(_ch, "children"):
            yield from _flat(_ch, in_exp or type(_ch).__name__ == "Expander")
        else:
            _name = type(_ch).__name__
            # 只讀文字類元素的 `.value`（widget 的 `.value` 會去查 session_state，無 key 時 KeyError）
            yield _name, (getattr(_ch, "value", None) if _name in _TEXT_KINDS else None), in_exp


def _expanders(block, out=None):
    """label → 該 expander 子樹內所有 `(類別名, 值)`（含巢狀）。"""
    out = {} if out is None else out
    for _ch in block.children.values():
        if hasattr(_ch, "children"):
            if type(_ch).__name__ == "Expander":
                out.setdefault(_ch.label, []).extend((k, v) for k, v, _ in _flat(_ch))
            _expanders(_ch, out)
    return out


def _texts(at, *, outside_expanders: bool | None = None, kinds=("Markdown", "Caption", "Error", "Warning")):
    return [v for k, v, e in _flat(at.main) if k in kinds and isinstance(v, str)
            and (outside_expanders is None or e is (not outside_expanders))]


# ══════════════════════════════════════════════════════════════════
# 冷啟動
# ══════════════════════════════════════════════════════════════════
def test_cold_start_first_row_is_grey_and_nothing_is_red(tmp_path):
    _at = _run(tmp_path)
    assert not _at.exception, _at.exception
    assert not _at.error, [e.value for e in _at.error]       # 未載入 ≠ 真出錯：沒有任何紅字
    _top = _texts(_at, outside_expanders=True)
    assert "## 📊 市場" in _top
    assert B.PAGE_SUBTITLE in _top
    assert B.NOT_LOADED in _top                              # 今日主要風險：⬜ 尚未載入，請按更新
    assert "**⬜ 尚未核准／無法判定**" in _top                  # 水位卡永遠是 ⬜
    assert not any("無風險" in t for t in _texts(_at))
    assert not any("%" in t for t in _top if "style" not in t[:10] and not t.startswith("<"))   # 首屏（非 HTML 卡）無百分比


def test_cold_start_page_never_mentions_checkbox_or_engineering_words(tmp_path):
    """圖 A 去 gate 後，冷啟動畫面（含各「查看依據」內容）不得殘留「核取方塊／勾選」或工程符號。"""
    _at = _run(tmp_path)
    _all = "\n".join(_texts(_at))
    for _w in ("核取方塊", "勾選上方", "session mkt_info", "data_cache/", "allocation_service", "compute_five_bucket_summary"):
        assert _w not in _all, _w
    _chart_a_basis = next(v for v in _texts(_at, outside_expanders=False) if v.startswith("- **使用的資料**：本地加權指數歷史快取"))
    assert "指數線：⬜ 尚未載入，請按更新" in _chart_a_basis


@pytest.mark.parametrize("session", (None, _LOADED), ids=("cold", "hot"))
def test_danger_card_demotion_is_signposted_from_hero_and_chart_d(tmp_path, session):
    """客戶裁示 3A＋附加要求（DEC-105）：指標危險度降階後，首屏「今日主要風險」卡與圖 D 都要清楚指路；
    指路句含「指標危險度」，目標 expander 標題字面存在，且其第一張卡就是指標危險度。"""
    _at = _run(tmp_path, session)
    assert not _at.exception
    _top = _texts(_at, outside_expanders=True)
    assert _top.count(B.DANGER_POINTER) == 2                     # hero 風險卡一次＋圖 D 一次
    assert "指標危險度" in B.DANGER_POINTER and f"「{B.LAMP_DETAIL_EXPANDER_LABEL}」" in B.DANGER_POINTER
    _exps = _expanders(_at.main)
    assert B.LAMP_DETAIL_EXPANDER_LABEL in _exps                  # 指路目標存在（標題字面相同）
    _first = _exps[B.LAMP_DETAIL_EXPANDER_LABEL][0]
    assert _first[0] == "Markdown" and "指標危險度" in _first[1]   # 展開區最上方確實是指標危險度卡


def test_chart_a_grey_error_text_is_scrubbed(tmp_path, monkeypatch):
    _secret = "AIza" + "A" * 35
    monkeypatch.setattr(S, "get_twii_trend_view", lambda n: S.TwiiTrendView(ok=False, error=f"讀取失敗 key={_secret}"))
    _at = _run(tmp_path, _LOADED)
    assert not _at.exception
    assert _secret not in "\n".join(_texts(_at))


def test_cold_start_chart_d_is_not_loaded_and_no_unevaluated_count_claim_of_safety(tmp_path):
    _at = _run(tmp_path)
    _top = _texts(_at, outside_expanders=True)
    assert _top.count(B.NOT_LOADED) >= 2       # hero 風險 ＋ 圖 D（圖 B 也未載入）
    assert not any("未評估不等於安全" in t and "0 項" in t for t in _top)


# ══════════════════════════════════════════════════════════════════
# 水位卡：首屏無 %，原區間只在查看依據內
# ══════════════════════════════════════════════════════════════════
def test_water_card_hides_range_outside_basis_but_keeps_it_inside(tmp_path, monkeypatch):
    from tests.test_page_market import _SCENARIOS, _fake_alloc
    monkeypatch.setattr(P, "_load_allocation", lambda: (_fake_alloc(with_cap=True), ""))
    monkeypatch.setattr(P, "_load_regime", lambda: _SCENARIOS["live_with_cap"]["regime"])
    _at = _run(tmp_path, _LOADED)
    assert not _at.exception, _at.exception
    _all = [(k, v, e) for k, v, e in _flat(_at.main) if isinstance(v, str)]
    _outside = [v for k, v, e in _all if not e]
    _inside = [v for k, v, e in _all if e]
    assert not any("40%～60%" in v or "上限 37%" in v for v in _outside), "水位卡首屏不得出現出手區間／上限數字"
    assert any("40%～60%" in v for v in _inside), "原有出手區間（含 risk_cap.v2）應保留在查看依據內"
    assert any("風險上限：獨立顯示待 C2b＋RC-VISIBILITY Gate" == v for k, v, e in _all if k == "Caption" and not e)


# ══════════════════════════════════════════════════════════════════
# hero 與圖 D 同源（頁面層）
# ══════════════════════════════════════════════════════════════════
def test_hero_and_panel_share_one_build_market_risks_call(tmp_path, monkeypatch):
    _calls: list = []
    _real = B.build_market_risks
    monkeypatch.setattr(B, "build_market_risks", lambda *a, **k: (_calls.append(a), _real(*a, **k))[1])
    _at = _run(tmp_path, _LOADED)
    assert not _at.exception
    assert len(_calls) == 1, "hero 與圖 D 必須共用同一次 build_market_risks（單一來源）"


def test_loaded_hero_items_match_panel_rows(tmp_path):
    """📌 P4-1（客戶 DEC-117 Q6=A；有意識的修改，⛔ 不是降強度）：外露層改為縮短行「燈色＋桶名＋燈名＋方向」，
    整句版（①②③…｜方向：…）下沉到風險 tile 的「🔍 查看依據」。原斷言全部照守、改釘在新位置並加嚴：
    外露縮短行與摺疊整句**逐項一一對應**（同燈名、同方向），且兩者都與圖 D 同列逐字相同（同一份 `_risks`）。"""
    _at = _run(tmp_path, _LOADED)
    assert not _at.exception, _at.exception
    assert not _at.error
    _top = _texts(_at, outside_expanders=True)
    _items = [t for t in _top if t[:1] in "🟡🔴" and "：" in t and "　" in t]          # 外露縮短行
    _full = [t for t in _texts(_at, outside_expanders=False) if t[:1] in "①②③"]      # 摺疊內整句
    assert 1 <= len(_items) <= 3 and len(_full) == len(_items)
    _panel = next(t for t in _top if t.startswith("| 風險桶（每桶一項）"))
    # 📌 P4-2（線框 P-16；有意識的修改，⛔ 不是降強度）：圖 D 表格三欄→兩欄（桶／方向；「是否惡化」改 header 護欄 chip 寫一次）。
    _rows = {ln.strip("| ").split(" | ")[0]: ln.strip("| ").split(" | ")[1] for ln in _panel.splitlines()[2:]}
    for _it, _f in zip(_items, _full):
        _lamp = _it.split("：", 1)[1].split("　", 1)[0]
        _dir = _it.rsplit("　", 1)[1]
        assert _lamp in _panel, (_lamp, _panel)
        assert _lamp in _f and f"｜方向：{_dir}" in _f, (_it, _f)
        # QA-A MINOR 2：hero 每一項的「方向」文字必須與圖 D 對應列的方向欄逐字相同（同一份 `_risks`）
        assert any(_dir == v.strip() for v in _rows.values()), (_dir, _rows)
    assert any(t.startswith("**") and "項未評估**" in t for t in _top)        # 圖 D 頂端「N 項未評估」
    assert any("↗ 上升" in _it for _it in _items)                                  # 非全「無資料」，才有鑑別力
    assert not any("無風險" in t for t in _top)


# ══════════════════════════════════════════════════════════════════
# 圖 A：gate、灰紅分離、過期
# ══════════════════════════════════════════════════════════════════
def _view(**kw):
    _base = dict(ok=True, xs=("2026-10-21", "2026-10-22", "2026-10-23"), close=(22000.0, 22100.0, 22200.0),
                 n_available=3, as_of="2026-10-23", is_stale=False)
    _base.update(kw)
    return S.TwiiTrendView(**_base)


#: 📌 P4-2（客戶 DEC-117 Q4=P-B；有意識的修改，⛔ 不是降強度）：圖 B 由「每系列一張原生折線圖」改為 small multiples 一組
#:（行內 svg，不是原生圖元素 ⇒ `_n_charts` 不再計入）。原生折線圖只剩 Primary（圖 A）**一張**。
_PRIMARY_CHARTS = 1


def test_chart_a_draws_by_default_when_loaded_and_never_reads_when_not_loaded(tmp_path, monkeypatch):
    """無 gate：已載入 → 預設就讀本地快取並畫；未載入（冷啟動）→ 不讀、不畫（⇒ 不顯示過期值），灰字。"""
    _calls: list[int] = []

    def _fake(n):
        _calls.append(n)
        return _view(is_stale=True, stale_reason="落後 4 個交易日")
    monkeypatch.setattr(S, "get_twii_trend_view", _fake)
    _cold = _run(tmp_path, name="_cold.py")
    assert _calls == [] and _n_charts(_cold) == 0 and not _cold.warning and not _cold.error
    assert not _cold.checkbox or all(c.key not in ("p00m_gate_chart_a", "p00m_gate_chart_b") for c in _cold.checkbox)
    _at = _run(tmp_path, _LOADED)
    assert not _at.exception, _at.exception
    assert _calls == [B.TWII_CHART_TRADING_DAYS]
    assert _n_charts(_at) == _PRIMARY_CHARTS
    # 來源 caption 與趨勢結論句下沉到圖 A 摺疊（只下沉，逐字）；兩條護欄各自獨立成 header chip（外露，D10(a)）
    _inner = _expanders(_at.main)[B.FOLD_LABEL]
    assert any(k == "Caption" and v == "近 3 日，資料至 2026-10-23　·　" + S.TWII_SOURCE_TEXT for k, v in _inner)
    assert any(k == "Markdown" and "台股趨勢結論：⬜ 尚未定義" in v for k, v in _inner)
    _head = next(t for t in _texts(_at, outside_expanders=True) if t.startswith('<div class="cp-chart-header"><div class="cp-ch-title">圖A'))
    assert f'data-kind="guard_text">{B.CHART_A_MA_DISCLAIMER}</span>' in _head
    assert 'data-kind="not_defined">⬜ 尚未定義</span>' in _head
    assert B.CHART_A_SAY in _head


@pytest.mark.parametrize("view, red, grey_prefix", (
    (S.TwiiTrendView(ok=False, error="加權指數歷史快取讀不到"), False, "⬜ 台股指數歷史暫時讀不到"),
    (S.TwiiTrendView(ok=False, failed=True, error="OSError: disk"), True, None),
))
def test_chart_a_grey_for_unreadable_red_for_exception(tmp_path, monkeypatch, view, red, grey_prefix):
    monkeypatch.setattr(S, "get_twii_trend_view", lambda n: view)
    _at = _run(tmp_path, _LOADED)
    assert not _at.exception
    assert bool(_at.error) is red
    if grey_prefix:
        assert any(t.startswith(grey_prefix) for t in _texts(_at, kinds=("Caption",)))
    assert _n_charts(_at) == 0            # 圖 A 沒畫（圖 B 本來就不是原生圖元素）


def test_chart_a_stale_cache_is_flagged(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "get_twii_trend_view", lambda n: _view(is_stale=True, stale_reason="落後 4 個交易日"))
    _at = _run(tmp_path, _LOADED)
    assert any("已過期" in w.value and "落後 4 個交易日" in w.value for w in _at.warning)
    assert _n_charts(_at) == _PRIMARY_CHARTS                               # 照畫（不擋資料），但有旗標
    # 過期旗標除了摺疊「限制」內的原句，header 還有琥珀 chip（不塗紅；紅只給 failed）
    assert any('data-kind="stale"' in t and "cp-t-amber" in t for t in _texts(_at, outside_expanders=True))
    assert not _at.error


def test_chart_a_unknown_freshness_is_grey_not_assumed_fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "get_twii_trend_view", lambda n: _view(is_stale=None))
    _at = _run(tmp_path, _LOADED)
    assert "⬜ 台股指數歷史快取的新鮮度未判定" in _texts(_at, kinds=("Caption",))


def test_chart_a_missing_ma_is_listed_not_drawn_as_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "get_twii_trend_view", lambda n: _view())
    _at = _run(tmp_path, _LOADED)
    _caps = _texts(_at, kinds=("Caption",))
    assert "⬜ 缺少的均線：MA200：無資料（歷史不足）" in _caps


# ══════════════════════════════════════════════════════════════════
# 圖 B
# ══════════════════════════════════════════════════════════════════
def test_chart_b_is_one_small_multiples_group_with_five_cells(tmp_path, monkeypatch):
    """📌 P4-2（有意識的修改，⛔ 不是降強度）：原「每系列一張原生圖＋分組小標＋名稱·近 N 日」→ small multiples 一組 5 格；
    分組小標、每系列「名稱　·　近 N 日，資料至…」、趨勢結論句下沉到摺疊「來源」（逐字）。"""
    monkeypatch.setattr(S, "get_twii_trend_view", lambda n: S.TwiiTrendView(ok=False, error="x"))   # 圖 A 不畫，單獨看圖 B
    _at = _run(tmp_path, _LOADED)
    assert not _at.exception, _at.exception
    assert _n_charts(_at) == 0                                   # 不再有原生圖；5 格是行內 svg
    _grid = next(t for t in _texts(_at, outside_expanders=True) if t.startswith('<div class="cp-sm '))
    assert _grid.count('class="cp-sm-cell"') == 5               # DJI／IXIC／SOX／10Y／DXY（固定順序）
    assert _grid.count("<svg") == 3                              # 本輪有資料的 DJI／10Y／DXY；IXIC／SOX 本輪沒有
    assert _grid.count("⬜ 本輪沒有這個系列") == 2
    _inner = _expanders(_at.main)[B.FOLD_LABEL]
    _md = [v for k, v in _inner if k == "Markdown"]
    for _g in ("**海外市場**", "**利率**", "**美元**"):
        assert _g in _md
    assert "道瓊工業 DJI　·　近 3 日，資料至 2026-10-23" in _md
    assert any("國際趨勢結論：⬜ 尚未定義" in v for v in _md)


def test_chart_b_not_loaded_is_grey(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "get_twii_trend_view", lambda n: S.TwiiTrendView(ok=False, error="x"))   # 圖 A 不畫，單獨看圖 B
    _at = _run(tmp_path, {k: v for k, v in _LOADED.items() if k != "cl_data"})
    assert not _at.error and _n_charts(_at) == 0
    assert B.NOT_LOADED in _texts(_at, kinds=("Caption",))


# ══════════════════════════════════════════════════════════════════
# ⚡ 需要處理
# ══════════════════════════════════════════════════════════════════
def test_alerts_block_without_sources_says_so_and_never_claims_all_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "_load_allocation", lambda: (None, ""))
    _at = _run(tmp_path)
    _top = _texts(_at, outside_expanders=True)
    # 📌 P4-1（客戶 DEC-117 Q8c；有意識的修改，⛔ 不是降強度）：⚡ 改一行 bar ⇒ 標題與「沒有來源」寫在**同一行**外露
    #   （原斷言：兩者各自一個外露元素）。改為：恰一個外露元素同時以「**⚡ 需要處理**」開頭並含 `ALERTS_NO_SOURCE`。
    _bar = [t for t in _top if t.startswith("**⚡ 需要處理**")]
    assert len(_bar) == 1 and B.ALERTS_NO_SOURCE in _bar[0]
    assert not any("沒有需要處理的事" in t for t in _texts(_at))


def test_alerts_block_relays_allocation_conflicts_verbatim(tmp_path, monkeypatch):
    from tests.test_page_market import _SCENARIOS, _fake_alloc
    _a = _fake_alloc(with_cap=False)
    _a.conflicts = ("某個與結論相反的既有提示",)
    monkeypatch.setattr(P, "_load_allocation", lambda: (_a, ""))
    monkeypatch.setattr(P, "_load_regime", lambda: _SCENARIOS["live_no_cap"]["regime"])
    _at = _run(tmp_path, _LOADED)
    _top = _texts(_at, outside_expanders=True)
    # 📌 P4-1（客戶 DEC-117 Q8c「資訊只能下沉，不得刪除」；有意識的修改，⛔ 不是降強度）：衝突提示原文由外露改到 ⚡ 的
    #   「🔍 查看依據」內（逐字），外露 bar 帶計數；「有來源 ⇒ 不出現『沒有來源』」照守（外露、摺疊都不得出現）。
    assert "- 某個與結論相反的既有提示" in _texts(_at, outside_expanders=False)
    assert any(t.startswith("**⚡ 需要處理**") and B.ALERTS_CONFLICTS_COUNT_FMT.format(n=1) in t for t in _top)
    assert not any(B.ALERTS_NO_SOURCE in t for t in _texts(_at))


# ══════════════════════════════════════════════════════════════════
# 圖 C
# ══════════════════════════════════════════════════════════════════
def test_chart_c_block_is_text_only_no_numbers_no_charts(tmp_path):
    """📌 P4-2（客戶 DEC-117 Q8a／D6=B；有意識的修改，⛔ 不是降強度）：圖 C 外露＝header（標題＋「研究框架，未啟用」chip）＋
    `CHART_C_EMPTY` 一行；`CHART_C_SAY`／`CHART_C_BASIS` 下沉摺疊。整塊（含摺疊）仍零數字、零圖形、零按鈕。"""
    _at = _run(tmp_path, _LOADED)
    _flat_all = list(_flat(_at.main))
    _i = next(i for i, (k, v, e) in enumerate(_flat_all) if isinstance(v, str) and v.startswith(
        '<div class="cp-chart-header"><div class="cp-ch-title">圖C'))
    _j = next(i for i, (k, v, e) in enumerate(_flat_all) if isinstance(v, str) and v == "以下為可展開區塊（預設收合）。")
    _block = [(k, v, e) for k, v, e in _flat_all[_i:_j] if isinstance(v, str)]
    _outside = [v for k, v, e in _block if not e]
    assert len(_outside) == 2 and _outside[1] == B.CHART_C_EMPTY                  # header ＋ 一行
    assert B.CHART_C_SAY not in _outside and B.CHART_C_BASIS not in _outside
    _inside = [v for k, v, e in _block if e]
    assert B.CHART_C_SAY in _inside and B.CHART_C_BASIS in _inside
    _visible = "".join(re.sub(r"<[^>]+>", "", v) for _, v, _ in _block)           # 去標籤（class 名無數字，保險）
    assert not any(c.isdigit() or "%" in c for c in _visible)
    assert not [k for k, v, e in _flat_all[_i:_j] if k in ("Dataframe", "Table", "UnknownElement", "Button", "Checkbox")]


# ══════════════════════════════════════════════════════════════════
# 保留不動：parity
# ══════════════════════════════════════════════════════════════════
def _base_source() -> str:
    from tests.test_uim_revert_chain import uim_revert_for
    return uim_revert_for(_REL, (_ROOT / _REL).read_text(encoding="utf-8"))


def _defs(src: str) -> dict[str, str]:
    _out = {}
    for _n in ast.parse(src).body:
        if isinstance(_n, ast.FunctionDef):
            _out[f"def {_n.name}"] = ast.dump(_n)
        elif isinstance(_n, ast.Assign):
            for _t in _n.targets:
                if isinstance(_t, ast.Name):
                    _out[f"var {_t.id}"] = ast.dump(_n)
        elif isinstance(_n, ast.AnnAssign) and isinstance(_n.target, ast.Name):
            _out[f"var {_n.target.id}"] = ast.dump(_n)
    return _out


#: UI-M 有意識改動／移出的頂層定義（其餘一律必須與 UI-M 之前逐字相同 —— 能力保留）。
_INTENTIONALLY_CHANGED = {
    "def render_page_market",        # 編排重排（本批本意）
    "def _render_plain_card",       # 被 Hero／圖 A／圖 B 取代後無 caller，已刪
    "var TREND_PENDING_WHY",        # 移入 `_market_blocks`，page_market re-export
    "var PAGE_QUESTION",            # 值未改，只加註（AST 不含註解；保險起見列入）
}


def test_all_retained_toplevel_definitions_are_byte_identical_to_pre_uim():
    _old, _new = _defs(_base_source()), _defs((_ROOT / _REL).read_text(encoding="utf-8"))
    _same = {k for k in _old if k not in _INTENTIONALLY_CHANGED}
    assert _same, "沒有可比對的保留定義？"
    _diff = sorted(k for k in _same if _new.get(k) != _old[k])
    assert not _diff, f"以下保留定義與 UI-M 之前不同（能力保留被破壞）：{_diff}"
    # 本批只允許「移除」與「新增 re-export」，不允許默默多出別的頂層定義
    _added = sorted(set(_new) - set(_old))
    assert not _added, _added
    # 保留區塊的幾個關鍵 helper 明確在列（防止比對集合被意外掏空）
    for _k in ("def regime_clause", "def danger_clause", "def status_line", "def report_pointer",
               "def _render_report_guarded", "def _render_x1", "def _render_x5", "def _render_x6",
               "def _render_x8", "def raw_rows", "def inst_rows", "var X3_TEXT", "var X9_TEXT",
               "var X5_FIELDS", "var X6_FIELDS", "var X7_FIELDS", "var CONCLUSION_HEADING"):
        assert _k in _same


def test_conclusion_sentence_and_expanders_are_identical_to_pre_uim(tmp_path):
    _new = _run(tmp_path, _LOADED, name="_new.py")
    _old = _run(tmp_path, _LOADED, script=_base_source() + "\nrender_page_market()\n", name="_old.py")
    assert not _new.exception and not _old.exception, (_new.exception, _old.exception)

    def _conclusion(at):
        return [v for k, v, _ in _flat(at.main) if k == "Markdown" and v.startswith("市場位階：")]
    assert _conclusion(_new) == _conclusion(_old) and len(_conclusion(_new)) == 1

    _en, _eo = _expanders(_new.main), _expanders(_old.main)
    _lamp = "指標明細（16 項）"
    # 📌 P4-1（線框 P-03「只下沉」；有意識的修改，⛔ 不是降強度）：原首屏的「逐項資料日：尚未提供…」整句（含資料健康指路）
    #   移到「資料來源與完整度」展開區最上方。該展開區＝〔那一句（必須與 UI-M 之前首屏的那一個元素逐字相同）〕＋原內容逐項相同。
    _src_label = "資料來源與完整度"
    _old_top_caps = [v for k, v, e in _flat(_old.main) if k == "Caption" and not e]
    assert _en[_src_label][0][0] == "Caption" and _en[_src_label][0][1] in _old_top_caps
    assert _en[_src_label][0][1].startswith("逐項資料日：尚未提供")
    assert _en[_src_label][1:] == _eo[_src_label]
    assert _en[_src_label][0][1] not in [v for k, v, e in _flat(_new.main) if not e]     # 不再外露（只下沉，不重複）
    for _label, _items in _eo.items():
        assert _label in _en, f"保留的展開區不見了：{_label}"
        if _label in (_lamp, _src_label):
            continue
        assert _en[_label] == _items, f"展開區內容與 UI-M 之前不同：{_label}"
    # 指標明細：最上面多一張「指標危險度」卡（原首屏卡②，同一張卡），其餘逐項相同
    assert _en[_lamp][1:] == _eo[_lamp]
    _old_top = {v for k, v, e in _flat(_old.main) if k == "Markdown" and not e}
    assert _en[_lamp][0][0] == "Markdown" and _en[_lamp][0][1] in _old_top
    # 新增的展開區只有各區塊的「🔍 查看依據」、P4-1 的「更新選項」與 P4-2 的圖表摺疊（以及原本就有的那些）
    assert set(_en) - set(_eo) == {B.BASIS_EXPANDER_LABEL, B.UPDATE_OPTIONS_LABEL, B.FOLD_LABEL}


def test_verdict_cards_are_all_still_drawn(tmp_path, monkeypatch):
    """卡①②③ 一張都沒少：市場位階在 hero、出手區間在水位卡的查看依據、指標危險度在指標明細。"""
    _drawn: list[str] = []
    _real = P._render_one
    monkeypatch.setattr(P, "_render_one", lambda t: (_drawn.append(t.card.key), _real(t))[1])
    _at = _run(tmp_path, _LOADED)
    assert not _at.exception
    assert [k for k in _drawn if k.startswith("verdict.")] == ["verdict.regime", "verdict.exposure", "verdict.danger"]
