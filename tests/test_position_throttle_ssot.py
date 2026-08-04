"""tests/test_position_throttle_ssot.py — 持股% 單一引擎 SSOT 守衛(v19.168 IMPL-F)。

背景(對抗驗證 AI 指出的深層痛點):同一個問題「我該持股幾成?」原本有 3~4 套演算法、
給不同(甚至矛盾)的數字:
- 頁頂全域紅綠燈 bar / 今日作戰室 / 個股組合①卡 → regime 粗略 exposure_pct(80/50/20)
- 總經「建議持股油門」gauge → compute_position_throttle(health 細分區間)

IMPL-F 收斂:在 render_traffic_light_top(唯一同時握有 health + 有效 regime 之處)算一次
compute_position_throttle,存進 warroom_summary['throttle'],上述四處全讀同一份 → 一致。

本測試釘住:(1) warroom write 端算並存 throttle;(2) 四個顯示端都讀 warroom_summary.throttle;
(3) throttle dict 帶顯示端需要的 lo/hi/mid keys。純 source-scan + L0 純函式,無需 AppTest。
"""
from __future__ import annotations

from pathlib import Path

from shared.position_throttle import compute_position_throttle

_ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


# ── 寫入端:render_traffic_light_top 算 throttle 並存 warroom_summary ──────
def test_traffic_light_computes_and_stores_throttle():
    src = _read("src/ui/tabs/macro/section_traffic_light.py")
    assert "compute_position_throttle" in src
    assert "'throttle'" in src, "warroom_summary 未寫入 throttle SSOT"


# ── 讀取端:四個持股%顯示點都接 get_allocation() SSOT ─────────────────────
# v19.170:唯一取數入口的 import 原文。section_market_status 用
# `... import get_allocation as _get_alloc_ms`,故比對用 startswith 容許 as 別名。
_ALLOC_IMPORT = "from src.services.allocation_service import get_allocation"


def _imports_allocation_ssot(rel: str) -> bool:
    """該檔是否有一行**真正的** import 敘述接上 get_allocation。

    v19.170:刻意逐行 strip 後比對並跳過 `#` 註解行 —— 原斷言
    `"warroom_summary" in src and "throttle" in src` 是 false green,
    光靠一句「原本讀 warroom_summary['throttle']…」的註解就能矇混過關
    (section_market_status.py:72 正是如此)。
    """
    for _ln in _read(rel).splitlines():
        _s = _ln.strip()
        if _s.startswith("#"):
            continue
        if _s.startswith(_ALLOC_IMPORT):
            return True
    return False


def test_all_four_consumers_read_allocation_ssot():
    """四個持股%顯示點一律走 get_allocation(),不得自行再算或讀中繼 key。"""
    consumers = {
        "app.py": "頁頂/置底全域紅綠燈 bar",
        "src/ui/tabs/macro/section_traffic_light.py": "總經建議持股油門 gauge",
        "src/ui/tabs/macro/section_warroom.py": "今日作戰室",
        "src/ui/tabs/stock_grp_sections/section_market_status.py": "個股組合①卡",
    }
    for rel, label in consumers.items():
        assert _imports_allocation_ssot(rel), (
            f"{label}({rel})未接 get_allocation() SSOT → 持股%會再度不一致。"
            f"需有一行 `{_ALLOC_IMPORT}`(可 as 別名)")


# ── throttle dict 契約:顯示端用 lo_pct/hi_pct 區間 ───────────────────────
def test_throttle_dict_has_display_keys():
    thr = compute_position_throttle(62, regime="neutral")
    for k in ("lo_pct", "hi_pct", "mid_pct", "posture", "icon"):
        assert k in thr
    # 顯示端組 "lo–hi%" 字串,值須為 int-like 且 lo <= hi
    assert thr["lo_pct"] <= thr["hi_pct"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
