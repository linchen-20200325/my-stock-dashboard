"""src/data/sector_flow/reader.py — 板塊資金潮汐本地快取讀取(L1 Data).

讀 `data_cache/sector_flow/` 三檔(cron `scripts/update_sector_flow.py` 每交易日凍結):
  - bubble_latest.json  秒讀泡泡座標(**必要**;缺/壞 → ok=False sentinel)
  - metadata.json       更新時戳(判 staleness)
  - ticker_sector.json  {裸股號: 產業別}(持股→板塊對映;缺 → 空 dict,highlight 略過)

§8.2 L1:純檔案 I/O,無 streamlit、無業務邏輯、無跨層上行 import(對齊
`forward_test_store.py` / `macro_cache_reader.py`)。以 repo root 相對定位,免受 CWD 影響。

§1 Fail Loud, Never Fake:缺檔 / 壞檔 **不炸 UI**,回明確 sentinel(ok=False + reason 或
is_stale 旗標)讓 L5 顯示誠實訊息;**絕不**回傳 dummy 板塊或偽造更新時間。
§3.3:staleness 門檻走 L0 SSOT 常數 `SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS`,無 inline magic number。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from shared.sector_flow_thresholds import SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS

# repo root:reader.py 位於 src/data/sector_flow/ → parents[3] 為 repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CACHE_DIR = _REPO_ROOT / "data_cache" / "sector_flow"
BUBBLE_PATH = _CACHE_DIR / "bubble_latest.json"
META_PATH = _CACHE_DIR / "metadata.json"
TICKER_SECTOR_PATH = _CACHE_DIR / "ticker_sector.json"


def _load_json(path: Path):
    """讀 JSON;檔不存在回 None,壞檔當缺檔(log + None,不炸)。"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as _e:  # noqa: BLE001 — 壞檔不該炸 UI,降級當無資料
        print(f"[sector_flow_reader] 讀取失敗 {path.name}: {type(_e).__name__}: {_e}")
        return None


def _parse_iso_utc(s):
    """ISO 8601 字串 → aware UTC datetime;None / 無法解析 → None。"""
    if not s:
        return None
    try:
        _t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if _t.tzinfo is None:
        _t = _t.replace(tzinfo=timezone.utc)
    return _t.astimezone(timezone.utc)


def _compute_staleness(meta) -> tuple[bool, str | None, str | None]:
    """由 metadata.updated_at 判是否過期。回 (is_stale, reason, meta_updated_at_str)。

    §1:metadata 缺 / updated_at 無法解析 → 視為過期(不假設新鮮),reason 說明原因。
    """
    _upd = meta.get("updated_at") if isinstance(meta, dict) else None
    _dt = _parse_iso_utc(_upd)
    if _dt is None:
        return True, "metadata.json 缺失或 updated_at 無法解析", _upd
    _age_days = (datetime.now(timezone.utc) - _dt).total_seconds() / 86400.0
    if _age_days > SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS:
        return (True,
                f"上次更新距今 {_age_days:.1f} 日,超過 "
                f"{SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS} 日門檻",
                _upd)
    return False, None, _upd


def read_sector_flow_cache() -> dict:
    """讀三個本地快取檔 → 結構化 view dict。

    Returns
    -------
    成功:
        {
          'ok': True,
          'sectors': list[dict],        # bubble_latest.json 的 sectors(泡泡座標)
          'updated_at': str | None,     # bubble_latest.json 的更新時戳
          'window_size': int | None,
          'n_trading_days_used': int | None,
          'ticker_sector': dict,        # {裸股號: 產業別};缺檔 → {}
          'is_stale': bool,             # metadata.updated_at 距今 > 門檻
          'stale_reason': str | None,
          'meta_updated_at': str | None,
        }
    缺 bubble_latest.json / 壞檔 / schema 不符:
        {'ok': False, 'reason': str}
    """
    bubble = _load_json(BUBBLE_PATH)
    if not isinstance(bubble, dict) or not isinstance(bubble.get("sectors"), list):
        return {"ok": False,
                "reason": "板塊資金快取尚未產生(缺 bubble_latest.json 或格式不符)"}

    meta = _load_json(META_PATH)
    is_stale, stale_reason, meta_upd = _compute_staleness(meta)

    ts = _load_json(TICKER_SECTOR_PATH)
    ticker_sector = ts if isinstance(ts, dict) else {}
    # 容錯:若 cron 未來改成 {'map': {...}} 包裝,取內層;否則視為 flat {code: sector}。
    if isinstance(ticker_sector.get("map"), dict):
        ticker_sector = ticker_sector["map"]

    return {
        "ok": True,
        "sectors": bubble["sectors"],
        "updated_at": bubble.get("updated_at"),
        "window_size": bubble.get("window_size"),
        "n_trading_days_used": bubble.get("n_trading_days_used"),
        "ticker_sector": ticker_sector,
        "is_stale": is_stale,
        "stale_reason": stale_reason,
        "meta_updated_at": meta_upd,
    }
