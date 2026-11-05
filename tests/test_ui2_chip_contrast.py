"""New UI2 chip 文字色對比守衛（Visual Fidelity Gate V8 / Exec Spec §1）。

純 CSS 解析：從 `src/ui2/shell/css.py::CSS` 取出 `.ui2-chip--positive/--warning/--danger` 的文字色與 tint，
依 WCAG 2.x 相對亮度公式算對比；文字色須對深色底（`.streamlit/config.toml` backgroundColor）與
「疊 tint 後的底色」皆 ≥ 4.5:1（chip 字級 .78rem＝小字）。底色從 config.toml 讀，不寫死。
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from src.ui2.shell.css import CSS

ROOT = Path(__file__).resolve().parents[1]
MIN_RATIO = 4.5
TONES = ("positive", "warning", "danger")


def _bg() -> tuple[int, int, int]:
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    return _hex(cfg["theme"]["backgroundColor"])


def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    assert len(h) == 6, h
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _lum(rgb) -> float:
    def lin(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(a, b) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _over(rgb, alpha: float, bg):
    return tuple(a * alpha + b * (1 - alpha) for a, b in zip(rgb, bg))


def _parse(css: str) -> dict[str, tuple[tuple[int, int, int], tuple[int, int, int], float]]:
    out = {}
    for tone in TONES:
        m = re.search(r"\.ui2-chip--%s\{([^}]*)\}" % tone, css)
        assert m, f".ui2-chip--{tone} 規則不存在"
        body = m.group(1)
        col = re.search(r"(?<![-\w])color:(#[0-9a-fA-F]{6})", body)
        tint = re.search(r"background:rgba\((\d+),(\d+),(\d+),([0-9.]+)\)", body)
        assert col and tint, f".ui2-chip--{tone} 缺 color 或 rgba tint：{body}"
        out[tone] = (_hex(col.group(1)), tuple(int(tint.group(i)) for i in (1, 2, 3)), float(tint.group(4)))
    return out


@pytest.mark.parametrize("tone", TONES)
def test_chip_text_contrast_on_bg_and_on_tint(tone):
    fg, tint_rgb, alpha = _parse(CSS)[tone]
    bg = _bg()
    assert _ratio(fg, bg) >= MIN_RATIO, f"{tone} 對底 {_ratio(fg, bg):.2f} < {MIN_RATIO}"
    on_tint = _over(tint_rgb, alpha, bg)
    assert _ratio(fg, on_tint) >= MIN_RATIO, f"{tone} 對疊 tint 底 {_ratio(fg, on_tint):.2f} < {MIN_RATIO}"


def test_wcag_formula_sanity():
    assert abs(_ratio((255, 255, 255), (0, 0, 0)) - 21.0) < 1e-9
    assert abs(_ratio((119, 119, 119), (255, 255, 255)) - 4.48) < 0.01


def test_tint_and_size_not_changed():
    """本批只換文字色：tint rgba 與 chip 尺寸維持原值。"""
    p = _parse(CSS)
    assert p["positive"][1:] == ((26, 127, 55), 0.12)
    assert p["warning"][1:] == ((183, 121, 31), 0.14)
    assert p["danger"][1:] == ((198, 40, 40), 0.12)
    assert "font-size:.78rem;line-height:1.5" in CSS and "padding:1px 8px" in CSS


@pytest.mark.parametrize("tone,old", [("positive", "#1a7f37"), ("warning", "#b7791f"), ("danger", "#c62828")])
def test_negative_mutation_old_colours_fail(tone, old):
    """負向突變：換回舊色（對深色底不足）必須轉紅——證明守衛有牙。"""
    mutated = re.sub(r"(\.ui2-chip--%s\{color:)#[0-9a-fA-F]{6}" % tone, r"\g<1>" + old, CSS, count=1)
    assert mutated != CSS
    fg, tint_rgb, alpha = _parse(mutated)[tone]
    bg = _bg()
    assert (_ratio(fg, bg) < MIN_RATIO) or (_ratio(fg, _over(tint_rgb, alpha, bg)) < MIN_RATIO)
