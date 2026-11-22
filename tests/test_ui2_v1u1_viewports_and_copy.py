"""V1＋U1（總管核准）：三視窗量測（390×844／1280×900／1440×900）與 Real 橫幅／市場位階缺值旁註的守衛。

- V1：`measure_viewport.VIEWPORTS` 為 mobile／desktop／desktop1280 三個視窗（保留 1440）；桌機判定一律由「視窗寬」推導
  （`MOBILE_MAX_W`），不看視窗名稱，所以第三個視窗不會被誤當手機、也不會漏判。
- 證據守衛：docs/vnext 的四份量測 JSON（realfeed／batch3b × 預設／streamlit156）`meta.viewports`、每筆 `viewport_name`
  必須恰等於 `MV.VIEWPORTS`，且每個視窗都有場景數——證據在重產之前（`證據尚待重產`）預期為紅，**不 skip／不 xfail**。
- U1 的橫幅文案與位階缺值旁註守衛在 `test_ui2_p1_human_text.py`／`test_ui2_real_feed.py`；本檔另做「跨檔一致」的輕量鎖定。
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

from shared.ui2_contract import text as T
from src.services.ui2 import real_canonical as RC
from tests.ui2_viewport import measure_viewport as MV

ROOT = pathlib.Path(__file__).resolve().parents[1]
_EVIDENCE = [(d, n) for d in ("newui2_realfeed", "newui2_batch3b")
             for n in ("viewport_measurements.json", "viewport_measurements_streamlit156.json")]


def _load(d: str, n: str) -> dict:
    return json.loads((ROOT / "docs" / "vnext" / d / n).read_text(encoding="utf-8"))


# ── V1 ───────────────────────────────────────────────────────────────────
def test_viewports_are_exactly_the_three_approved_sizes_in_order():
    assert list(MV.VIEWPORTS) == ["mobile", "desktop", "desktop1280"]
    assert MV.VIEWPORTS == {"mobile": (390, 844), "desktop": (1440, 900), "desktop1280": (1280, 900)}


def test_third_viewport_is_judged_as_desktop_by_width_not_by_name():
    assert MV.VIEWPORTS["mobile"][0] <= MV.MOBILE_MAX_W
    for name in ("desktop", "desktop1280"):
        assert MV.VIEWPORTS[name][0] > MV.MOBILE_MAX_W, name


def test_no_name_based_desktop_branch_remains_in_the_measurement_scripts():
    """判定一律看寬度（`MOBILE_MAX_W`）；量測腳本不得再有 `vp_name == "desktop"`／`== 'desktop'` 這類以名稱判桌機的處所。"""
    for rel in ("tests/ui2_viewport/measure_viewport.py", "tests/ui2_viewport/degraded.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert not re.search(r"""vp_name\s*[!=]=\s*["']desktop["']""", src), rel
        assert not re.search(r"""for\s+vp\s+in\s+\(\s*["']mobile["']""", src), rel          # 不得再以寫死名稱元組迭代視窗


@pytest.mark.parametrize("vp_name", ["mobile", "desktop", "desktop1280"])
def test_want_shot_rules(vp_name):
    assert MV._want_shot("all", vp_name, "stale") is True
    assert MV._want_shot("none", vp_name, "loaded") is False
    assert MV._want_shot("core", vp_name, "loaded") is True                      # 兩個桌機視窗都留 cold／loaded
    assert MV._want_shot("core", vp_name, "stale") is (vp_name == "mobile")      # 桌機視窗其餘場景不截圖（控制檔案大小）


# ── 證據守衛（重產前預期紅；不 skip／不 xfail） ───────────────────────────
@pytest.mark.parametrize("d,n", _EVIDENCE)
def test_evidence_meta_viewports_equal_current_viewports(d, n):
    meta = _load(d, n)["meta"]
    assert set(meta["viewports"]) == set(MV.VIEWPORTS), "證據尚待重產"
    assert {k: tuple(v) for k, v in meta["viewports"].items()} == MV.VIEWPORTS, "證據尚待重產"


@pytest.mark.parametrize("d,n", _EVIDENCE)
def test_evidence_results_cover_every_viewport(d, n):
    results = _load(d, n)["results"]
    names = {r["viewport_name"] for r in results}
    assert names == set(MV.VIEWPORTS), "證據尚待重產"
    for vp in MV.VIEWPORTS:
        assert sum(1 for r in results if r["viewport_name"] == vp) > 0, (vp, "證據尚待重產")
    # 每個視窗的量測態數相同（同一組頁面×場景在每個視窗都量過；手機額外的長字串壓力態只在手機寬）
    per = {vp: sum(1 for r in results if r["viewport_name"] == vp and r.get("mode") != "stress") for vp in MV.VIEWPORTS}
    assert len(set(per.values())) == 1, (per, "證據尚待重產")


# ── U1 跨檔鎖定 ───────────────────────────────────────────────────────────
def test_u1_banner_and_regime_note_exact_strings():
    assert T.REAL_PREVIEW_BANNER_NOTE == "目前僅部分台股資料已接入；各項指標請以卡片顯示的資料日與狀態為準。"
    assert RC.REGIME_NO_DATA_NOTE == "尚無可用的市場位階資料，暫不顯示判讀。"
    assert "位階" not in T.REAL_PREVIEW_BANNER_NOTE
