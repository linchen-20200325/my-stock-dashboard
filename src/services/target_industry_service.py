"""src/services/target_industry_service.py — 🎯 標的頁候選表「產業」欄要的 ticker→產業對映（L3 Service，薄）。

單一職責一句話：**把既有的 `ticker_sector.json`（板塊資金快取附帶的官方產業分類對映）以 L3 介面交給 L5 UI。**

═══ 為什麼存在 ══════════════════════════════════════════════════════
UI-T（2026-10-29，客戶線框 S8）：候選標的表要有「產業」欄，且「用既有 ticker→產業對映、不新增來源」。
對映住在 L1 `src.data.sector_flow.reader`（本地快取，非網路取數）；`CLAUDE.md §8.2` 硬規則第 4 條
禁止 L5 直呼 L1，故補這一支薄 L3（比照 `sector_flow_service` 的 late import L1 reader 作法）。

═══ 這個檔**不是**什麼 ═══════════════════════════════════════════════
- ❌ 不新增資料來源、不改產業分類、不做任何聚合或排名；回傳值就是 L1 reader 給的 `ticker_sector` 原樣。
- ❌ 不把「對不到」補成任何預設板塊：對不到的代碼**不放 key**（呼叫端顯示 ⬜）。
- ❌ 不建快取（reader 是讀本地小檔；失敗不入任何快取）。

§1：reader 回 `ok=False`（快取尚未產生）→ 本函式回空 dict **並**帶 `available=False`，
呼叫端據此顯示「⬜ 產業對映尚未產生」，與「這一檔查無產業」是兩件事。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TickerSectorMap:
    """`ticker_sector.json` 的唯讀視圖。

    Attributes:
        available: 對映檔讀得到（reader `ok=True`）。False ＝ 板塊資金快取尚未產生（**不是**「每一檔都沒有產業」）。
        mapping: `{裸股號: 產業別}`。對不到的代碼不放 key（⛔ 不補預設值）。
        reason: `available=False` 時 reader 給的原因原文（空字串＝沒有問題）。
    """

    available: bool
    mapping: dict = field(default_factory=dict)
    reason: str = ""


def get_ticker_sector_map() -> TickerSectorMap:
    """讀產業對映。reader 拋例外 → 原樣往上拋（§1，由 L5 loader 轉成可見的紅態，不吞）。"""
    from src.data.sector_flow.reader import read_sector_flow_cache

    _view = read_sector_flow_cache()
    if not isinstance(_view, dict) or not _view.get("ok"):
        _reason = str((_view or {}).get("reason") or "") if isinstance(_view, dict) else ""
        return TickerSectorMap(available=False, mapping={}, reason=_reason)
    _m = _view.get("ticker_sector")
    return TickerSectorMap(available=True, mapping=dict(_m) if isinstance(_m, dict) else {})
