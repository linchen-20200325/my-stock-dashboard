"""test_futures_oi_unit_label.py — 台指期外資留倉的單位正名（2026-08-27）。

`src/data/macro/leading_indicators.finmind_fut_oi` 的口徑是
**大台淨口 + 0.25 × 小台淨口**（`_MTX_TO_TX_FACTOR`），單位是 **TX 當量口**；
`scripts/export_stock_db.py` 檔頭卻標成裸「口」。量綱標錯 → 下游拿它去跟
任何「原始口數」相比或相除都會差到 4 倍（§4.1 量綱陷阱）。

⚠️ 本檔設計成「把單位 revert 成『口』就轉紅」。
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))
import export_stock_db as E  # noqa: E402,F401  （守衛檔的 import path 對齊其他 export 測試）

# ══════════════════════════════════════════════════════════════════════
# 問題 3：台指期外資留倉單位＝TX 當量口，不是「口」
# ══════════════════════════════════════════════════════════════════════
def test_futures_oi_unit_label_says_tx_equivalent():
    """匯出腳本的單位標註必須與上游實際口徑一致。

    上游 `finmind_fut_oi` = 大台淨口 + 0.25×小台淨口 → 單位是 **TX 當量口**。
    revert 成「單位 口」→ 本條轉紅。
    """
    src = (_ROOT / "scripts" / "export_stock_db.py").read_text(encoding="utf-8")
    head = src.split('"""')[1]        # module docstring
    fut_lines = [ln for ln in head.splitlines() if "futures_oi" in ln]
    assert fut_lines, "檔頭資料盤點應列出 futures_oi"
    blob = "\n".join(head.splitlines()[
        head.splitlines().index(fut_lines[0]):
        head.splitlines().index(fut_lines[0]) + 3])
    assert "當量" in blob, f"futures_oi 單位必須標 TX 當量口，實際：{blob!r}"
    assert "單位 口;" not in blob and "單位 口）" not in blob, \
        f"不得標成裸『口』：{blob!r}"


def test_futures_oi_unit_matches_upstream_factor():
    """單位敘述與上游換算因子同源：0.25 這個數字只准有一份 SSOT。"""
    from src.data.macro.leading_indicators import _MTX_TO_TX_FACTOR

    assert _MTX_TO_TX_FACTOR == 0.25
    src = (_ROOT / "scripts" / "export_stock_db.py").read_text(encoding="utf-8")
    assert "0.25" in src and "當量" in src, \
        "export 腳本須就地說明 TX 當量的組成（大台 + 0.25×小台），否則下游無從對齊量綱"
