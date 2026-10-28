"""XV-V1（客戶 2026-10-28 裁示）：`etf_fetch.py` 後綴正規化改為大小寫不敏感。

原寫法（字串取代 `.tw`→`.TW`）對小寫 `.two` 產生 `00679b.TWo`（後綴未正規化）。
修後 `.two`→`.TWO`、`.tw`→`.TW`；代碼本體不動（不改大小寫、不補前導零、不加減後綴）。
"""
from __future__ import annotations

import pathlib
import re

import pytest

from src.data.etf.etf_fetch import _norm_tw_suffix


@pytest.mark.parametrize("raw, want", [
    ("00679b.two", "00679b.TWO"),
    ("00679B.TWO", "00679B.TWO"),
    ("5314.Two", "5314.TWO"),
    ("0050.tw", "0050.TW"),
    ("0050.Tw ", "0050.TW"),
    ("  0050.TW", "0050.TW"),
    ("0050", "0050"),
    ("00631l", "00631l"),       # 本體大小寫不動
    ("VOO", "VOO"),
    ("", ""),
    (None, ""),
])
def test_norm_tw_suffix(raw, want):
    assert _norm_tw_suffix(raw) == want


def test_no_partial_two_suffix():
    """回歸：舊寫法的 `.TWo` 形狀不得再出現。"""
    assert not _norm_tw_suffix("00679b.two").endswith(".TWo")


def test_no_case_sensitive_tw_replace_left_in_file():
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "src/data/etf/etf_fetch.py").read_text(encoding="utf-8")
    assert not re.search(r"""\.replace\(\s*['"]\.tw['"]\s*,\s*['"]\.TW['"]\s*\)""", src)
