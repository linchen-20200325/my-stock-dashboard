"""xview V6：去後綴順序 —— 先 `.TWO` 再 `.TW`（反序時 `5314.TWO` → `5314O`）。

只修 🔍 找標的（新 UI `page_find`）會用到的 `sector_heatmap_render.build_sector_treemap`
子項顯示名。`etf_smart_analysis.check_333_criteria` 的同型 2 處只有舊 UI
（`src/ui/etf/etf_tab_smart.py`）呼叫 → DEC-019 舊 UI 凍結，未修（登記）。
"""
from __future__ import annotations

import pathlib
import re

import pytest

from src.ui.render.sector_heatmap_render import build_sector_treemap


@pytest.mark.parametrize("raw, want", [
    ("00679B.TWO", "00679B"),
    ("5314.TWO", "5314"),
    ("2330.TW", "2330"),
    ("2330", "2330"),
])
def test_sub_label_strips_suffix(raw, want):
    fig = build_sector_treemap({"SEC.TW": {"name": "測試", "sub": [raw]}},
                               {raw: 1.0}, "台股")
    labels = list(fig.data[0].labels)
    assert labels[-1].split("<br>")[0] == want
    # text 欄仍保留原代號（不改其他行為）
    assert list(fig.data[0].text)[-1] == raw


def test_lowercase_behavior_unchanged():
    """不改大小寫行為：小寫後綴照舊不去除（與修前一致）。"""
    fig = build_sector_treemap({"S": {"name": "n", "sub": ["5314.two"]}}, {}, "m")
    assert list(fig.data[0].labels)[-1].split("<br>")[0] == "5314.two"


def test_no_reversed_strip_in_fixed_file():
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "src/ui/render/sector_heatmap_render.py").read_text(encoding="utf-8")
    assert not re.search(r"""replace\(\s*['"]\.TW['"]\s*,\s*['"]['"]\s*\)\s*\.replace\(\s*['"]\.TWO['"]""", src)
