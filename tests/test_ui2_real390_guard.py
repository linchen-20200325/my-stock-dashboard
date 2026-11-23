"""R1 WIP：Real 390 📊 市場導覽餘裕 ≥109px 守衛（`p2_real_nav_margin_109`）＋ Real meta note 逐字。

純 Python（不啟動瀏覽器、不 import streamlit／src.services）；判定器單元測試，風格與 test_ui2_p2_primary_slot 的
`_p2_eval`／`_good` 一致（那份檔因頂層 import src.services 在無 streamlit 環境無法收集，故新測試獨立成檔）。
"""
from __future__ import annotations

import inspect

import pytest

from tests.ui2_viewport import measure_viewport as MV

K109 = "p2_real_nav_margin_109"
K160 = "p2_nav_margin_160"
REAL_NOTE_EXPECTED = ("Real-data Preview（唯讀）：目前僅部分台股資料已接入；其餘資料依各卡片狀態顯示。"
                      "本報告記錄量測當下的資料及畫面狀態，不代表即時或正式生產環境。")


def _p2_eval(m: dict) -> dict[str, list[str]]:
    out = {t["id"]: [] for t in MV.THRESHOLDS}
    MV._evaluate_p2(m, out)
    return out


def _m(margin, *, w=390, scenario="real", feed="real", page="p4_market") -> dict:
    mobile = w <= 768
    return {"page": page, "scenario": scenario, "feed": feed,
            "viewport": {"w": w, "h": 844 if mobile else 900},
            "nav": {"top": 791.0}, "first_block_after_l1_top": (791.0 - margin) if margin is not None else None,
            "risk": {"top": 500.0, "bottom": 560.0},
            "elements": [{"q": "q2", "bottom": 300.0}, {"q": "q3", "bottom": 340.0}],
            "p2": {"onebrain": {"top": 910.0, "bottom": 960.0}, "slot": {"top": 570.0, "bottom": 660.0},
                   "grid": {"top": 670.0, "bottom": 900.0}, "slot_graphics": 0, "slot_danger": 0,
                   "slot_text": "🇹🇼 台股趨勢 ⬜ 尚未提供 SPEC｜最新收盤參考｜X｜資料日 2026-11-02｜缺值不補",
                   "spec_text": "SPEC｜最新收盤參考｜X｜資料日 2026-11-02｜缺值不補"}}


def test_real_390_margin_109_boundaries():
    assert _p2_eval(_m(108.9))[K109] != []
    assert _p2_eval(_m(109.0))[K109] == []
    assert _p2_eval(_m(109.8))[K109] == []
    assert _p2_eval(_m(108.96))[K109] == []          # 與既有 160 守衛同一 ±0.05 容差
    assert _p2_eval(_m(108.9))[K160] == []           # 160 規則不套用 Real（既有行為不變）


@pytest.mark.parametrize("w", [320, 360])
def test_not_applied_to_320_and_360(w):
    assert _p2_eval(_m(50.0, w=w))[K109] == []


@pytest.mark.parametrize("sc", ["cold", "loaded", "missing", "stale", "unavailable"])
def test_not_applied_to_fake_390_and_160_rule_unchanged(sc):
    r = _p2_eval(_m(50.0, scenario=sc, feed="fake"))
    assert r[K109] == []
    assert (r[K160] != []) == (sc in ("stale", "unavailable"))


def test_not_applied_to_other_pages_desktop_or_missing_margin():
    assert _p2_eval(_m(50.0, page="p4_data"))[K109] == []
    assert _p2_eval(_m(50.0, w=1440))[K109] == []
    assert _p2_eval(_m(None))[K109] == []


def test_registered_and_wired_in_evaluate():
    assert MV.P2_REAL_NAV_MARGIN_MIN_PX == 109.0
    assert K109 in {t["id"] for t in MV.THRESHOLDS}
    # evaluate 需完整瀏覽器量測 dict（hscroll／elements 全欄位），單元層以原始碼確認掛載 _evaluate_p2（k3 key 由 THRESHOLDS 初始化）
    assert "_evaluate_p2(m, out)" in inspect.getsource(MV.evaluate)


def test_real_meta_note_verbatim_and_used_by_run_real():
    assert MV.REAL_META_NOTE == REAL_NOTE_EXPECTED
    assert '"note": REAL_META_NOTE' in inspect.getsource(MV._run_real)
    assert "兩項" not in MV.REAL_META_NOTE and "三項" not in MV.REAL_META_NOTE
