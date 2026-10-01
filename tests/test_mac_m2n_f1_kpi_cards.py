"""批 MAC · M2N-f1（KPI 卡部分）：§八 總經拼圖 KPI 卡缺值不再捏 0／50。

修前：dict 在、值缺時 `.get('score',0)`／`.get('yoy',0)`／`.get('value',50)`／
`.get('current',0)`／`.get('prev',0)`／VIX `.get('current',0)`、`.get('ma20',0)`
→ 印「0 分」「+0.0%」「50.0」「0.00%」「上月 0.00%」「MA20=0」並給燈色。
修後：缺鍵／None／NaN／±inf／非數值（同 `_finite_yoy`）一律走各卡**既有**「待取得」灰卡；
上月值／MA20 缺 → 只刪該段（不加字）。⛔ 範圍外：策略1 矩陣、三環、否決檢查（另案 ⑤）。

harness 沿用 `tests/test_m2n2_no_zero_fill.py` 的 `_FakeST`（全部離線）。
"""
from __future__ import annotations

import pytest

from tests.test_m2n2_no_zero_fill import _FakeST, _mod

_NAN, _INF = float("nan"), float("inf")
_PENDING = ">待取得<"


class _CapST(_FakeST):
    """另記 plotly 圖（VIX 卡的標題在圖上）。"""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.figs: list = []

    def plotly_chart(self, fig, *a, **k):
        self.figs.append(fig)


def _render(macro_info: dict, monkeypatch) -> _CapST:
    import src.services.allocation_service as AS
    import src.ui.tabs.macro.section_chips as SC
    mod = _mod("mid")
    fake = _CapST({"macro_info": macro_info})
    monkeypatch.setattr(mod, "st", fake)
    monkeypatch.setattr(AS, "apply_vix_veto", lambda *a, **k: None)
    monkeypatch.setattr(AS, "apply_ring_gate", lambda *a, **k: None)
    monkeypatch.setattr(AS, "register_conflict", lambda *a, **k: None)
    monkeypatch.setattr(AS, "get_allocation", lambda *a, **k: type("A", (), {
        "is_loaded": False, "final_hi": None})())
    monkeypatch.setattr(SC, "read_v4_macro_veto", lambda *a, **k: None)
    try:
        mod.render_section_mid(False, {}, {}, {})
    except TypeError as e:
        # ⚠️ 範圍外的既有問題（非 KPI 卡）：下游「總經基本面否決檢查」以
        # `.get(key, 預設) <比較>` 判定，值為 None／字串時拋 TypeError。KPI 卡在它之前
        # 已渲染完畢，本檔只驗 KPI 卡；該處另案（M2N-f1 的非 KPI 部分）。
        fake.exc = e
    return fake


def _card(fake: _CapST, title: str) -> str:
    hits = [t for k, t in fake.out if k == "markdown" and f'color:#c9d1d9;">{title}<' in t]
    assert len(hits) == 1, (title, len(hits))
    return hits[0]


#: (macro_info key, 值的 key, 卡標題, 有值時的值 → 期望出現的字串)
_CARDS = [
    ("ndc_signal", "score", "NDC 景氣燈號", 30, "30 分"),
    ("tw_export", "yoy", "台灣出口 YoY", 3.2, "+3.2%"),
    ("ism_pmi", "value", "🇹🇼 台灣 PMI", 51.3, "51.3"),
    ("us_core_cpi", "yoy", "美國核心CPI YoY", 2.81, "+2.81%"),
    ("fed_funds", "current", "美國 Fed Funds Rate", 4.33, "4.33%"),
]
_MISSING = {"absent": None, "none": "NONE", "nan": _NAN, "+inf": _INF, "-inf": -_INF,
            "str": "-"}


def _info_for(key, vkey, v):
    d = {"date": "2026-08"}
    if v is not None:
        d[vkey] = None if v == "NONE" else v
    return {key: d}


@pytest.mark.parametrize("key,vkey,title,good,shown", _CARDS, ids=[c[0] for c in _CARDS])
@pytest.mark.parametrize("miss", sorted(_MISSING))
def test_kpi_card_missing_value_is_pending_card(key, vkey, title, good, shown, miss, monkeypatch):
    card = _card(_render(_info_for(key, vkey, _MISSING[miss]), monkeypatch), title)
    absent = _card(_render({}, monkeypatch), title)      # 整包沒來 → 既有待取得卡
    assert card == absent and _PENDING in card            # 與既有灰卡逐字相同，不新增字
    for bad in ("0 分", "+0.0%", "50.0", "0.00%", "nan", "inf"):
        assert bad not in card, bad


@pytest.mark.parametrize("key,vkey,title,good,shown", _CARDS, ids=[c[0] for c in _CARDS])
def test_kpi_card_with_value_unchanged(key, vkey, title, good, shown, monkeypatch):
    card = _card(_render(_info_for(key, vkey, good), monkeypatch), title)
    assert _PENDING not in card and shown in card


def test_kpi_card_real_zero_is_a_value(monkeypatch):
    """真的 0.0% 不是缺值（不得被當成缺）。"""
    card = _card(_render(_info_for("tw_export", "yoy", 0.0), monkeypatch), "台灣出口 YoY")
    assert _PENDING not in card and "+0.0%" in card


@pytest.mark.parametrize("prev", [None, _NAN, _INF], ids=["absent", "nan", "inf"])
def test_fed_prev_missing_drops_trend_not_fabricated(prev, monkeypatch):
    d = {"current": 4.33, "date": "2026-08"}
    if prev is not None:
        d["prev"] = prev
    card = _card(_render({"fed_funds": d}, monkeypatch), "美國 Fed Funds Rate")
    assert "4.33%" in card and "上月" not in card


def test_fed_prev_present_keeps_trend(monkeypatch):
    card = _card(_render({"fed_funds": {"current": 4.33, "prev": 4.58}}, monkeypatch),
                 "美國 Fed Funds Rate")
    assert "上月 4.58% (↓0.25)" in card


@pytest.mark.parametrize("prev", [_NAN, _INF])
def test_cpi_prev_non_finite_drops_trend(prev, monkeypatch):
    card = _card(_render({"us_core_cpi": {"yoy": 2.81, "prev_yoy": prev}}, monkeypatch),
                 "美國核心CPI YoY")
    assert "+2.81%" in card and "上月" not in card


def _vix_texts(fake):
    return [t for k, t in fake.out if k == "markdown" and "VIX 恐慌指數" in t]


@pytest.mark.parametrize("cur", [None, _NAN, _INF, "-"], ids=["absent", "nan", "inf", "str"])
def test_vix_tile_current_missing_is_pending(cur, monkeypatch):
    d = {"dates": ["2026-08-01", "2026-08-02"], "values": [15.0, 16.0], "ma20": 15.5}
    if cur is not None:
        d["current"] = cur
    fake = _render({"vix": d}, monkeypatch)
    assert fake.figs == []                                   # 不畫「VIX=0 ✅ 市場平靜」
    absent = _vix_texts(_render({}, monkeypatch))
    assert _vix_texts(fake) == absent and any("待取得" in t for t in absent)


@pytest.mark.parametrize("ma20,frag", [(15.5, "VIX 恐慌指數 16.0（MA20=15.5）— "),
                                       (None, "VIX 恐慌指數 16.0— "),
                                       (_NAN, "VIX 恐慌指數 16.0— ")],
                         ids=["has-ma20", "absent", "nan"])
def test_vix_title_ma20(ma20, frag, monkeypatch):
    d = {"dates": ["2026-08-01", "2026-08-02"], "values": [15.0, 16.0], "current": 16.0}
    if ma20 is not None:
        d["ma20"] = ma20
    fake = _render({"vix": d}, monkeypatch)
    title = fake.figs[0].layout.title.text
    assert title.startswith(frag) and "MA20=0" not in title and "nan" not in title
