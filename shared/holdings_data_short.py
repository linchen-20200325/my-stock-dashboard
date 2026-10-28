"""shared/holdings_data_short.py — 「組合層資料不足」的**單一**判定（L0 純函式）。

XV-H1-EXT（客戶 2026-10-28 裁示 A：missing ≠ HOLD；unavailable ≠ safe）＋獨立複驗組 C MAJOR-1/2：
原本 ① 該做什麼 gate、③「未判 N」、⑦ prompt 續抱句、LINE 正文續抱／無需動作句**各自實作**
「資料不足」判定，彼此漏不同的洞。本檔收斂成一份，四處一律呼叫這裡。

一列**持有**列（`held` 為真、非整批抓取失敗）只要符合任一條，就讓整個組合「資料不足」：
- `KEY_INSUFFICIENT`：建議動作已被換成「⬜ 資料不足／無法判定」；
- `KEY_INVALID_INPUTS`／`KEY_INVALID_LIGHTS`：張數／均價／現價或燈號資料異常（批 Z49～Z52）；
- `KEY_PRICE_MISSING_KEPT`：缺現價、但結論可證明（結論保留，可是停利等判不了）；
- `KEY_FX_UNCONFIRMED`：外幣／幣別未確認（不進總額、損益% 判不了）；
- 個股汰換燈 ⚪ 且原因是契約漂移（`MISS_CONTRACT_DRIFT`；診斷句保留、不換 ⬜，但同樣判不出）。
組合層另加：沒有任何一檔完成評估（total 非有限或 < 1）、或有整批抓取失敗（`errors`）。

L3 `build_station_digest` 以 `row_data_short` 算出 `digest["data_short"]`（代號清單），
⑦／LINE 以 `digest_data_short(digest)` 判；① 逐列以 `row_data_short` 判。本檔零 I/O、零 `src.*`。
"""
from __future__ import annotations

import math
import numbers

from shared import asset_currency_gate as FXG
from shared import station_specs as SS


def row_data_short(row) -> bool:
    """這一列（持有、非整批抓取失敗）是否讓組合層「資料不足」。觀察清單列一律 False。"""
    if not isinstance(row, dict) or not row.get("held"):
        return False
    if (row.get("_detail") or {}).get("error"):
        return False            # 整批抓取失敗另由 `errors` 管（組合層照樣算資料不足）
    return bool(
        row.get(SS.KEY_INSUFFICIENT) or row.get(SS.KEY_INVALID_INPUTS)
        or row.get(SS.KEY_INVALID_LIGHTS) or row.get(SS.KEY_PRICE_MISSING_KEPT)
        or row.get(FXG.KEY_FX_UNCONFIRMED)
        or (row.get("種類") == "個股" and row.get("健檢") == "⚪"
            and row.get("_miss_reason") == SS.MISS_CONTRACT_DRIFT))


def total_judged(total) -> bool:
    """有效判斷檔數是有限值且 ≥ 1（bool、NaN、inf、0.5 → False）。"""
    return (isinstance(total, numbers.Real) and not isinstance(total, bool)
            and math.isfinite(total) and total >= 1)


def digest_data_short(digest) -> bool:
    """組合層資料不足 → ⑦／LINE ⛔ 不給「續抱」「今日無需動作」類 blanket 結論。"""
    digest = digest or {}
    return (not total_judged(digest.get("total")) or bool(digest.get("errors"))
            or bool(digest.get("data_short")))
