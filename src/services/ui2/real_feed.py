"""Real-data Preview 的 feed：**New UI2 唯一做 I/O 的檔**（NUI2-REAL-FEED A2；G2F 守衛）。

    Existing Canonical Services → **本檔（UI2 Feed Adapter）** → `real_canonical`（純函式）→ 既有 VM builder → UI2

只呼叫兩個既有 L3 canonical service（**唯讀、無 session 寫入、無網路**；實查見
`docs/vnext/NEWUI2_REAL_FEED_MAPPING_2026-11-03.md` §2）：
1. `market_twii_view_service.get_twii_trend_view(1)`：讀 git 追蹤的 `data_cache/twii_ohlcv.parquet`（不快取、不碰 session）。
2. `allocation_service.get_macro_regime(strict=True, require_valid_risk_cap=True)`：全站唯一的位階橋樑
   （只 `session_state.get('warroom_summary')` ＋ 讀本地 `macro_state.json`／`risk_cap_state.json`）；
   **strict**：讀壞了 ≠ 未評估（非 strict 會把例外吞成未評估）。`require_valid_risk_cap=True` 與 Legacy New UI
   市場頁同一呼叫；回傳的 Risk Cap 欄位**不收**（UI2 Risk Cap 恆 `⬜ 無法判定`）。

本檔**不**：轉語意（交給 `real_canonical`）、快取、寫 session／檔案、連網、呼叫任何 producer／寫入函式
（`refresh_macro_now`、`get_allocation`〔寫 `_alloc_*` session〕、`register_*`、`apply_*`、
`compute_and_lock_risk_cap`、`risk_cap_history_*`、`get_account`、`build_login_url`〔寫 `_oauth_state`＋nonce〕、
`get_holdings`、任何 save／write／delete／bind）。⛔ import streamlit、`src.data`、`src.compute`（G2F 鎖定）。

每次 rerun 由殼呼叫**一次** `read_real_snapshot()`，四頁共用同一份（位階三處同一次呼叫結果）。
例外一律接住 → 該事實記錯誤字串（只截長度）→ 由 `real_canonical` 映射成 Unavailable；兩個事實互相隔離。
"""
from __future__ import annotations

from src.services.ui2.real_canonical import RealFeedSnapshot, RegimeFact, TwiiFact

#: 卡片只顯示最新一筆收盤（取尾端 1 個交易日；「畫幾天」屬呈現決策，卡片＝1）。
TWII_CARD_DAYS = 1
#: 錯誤字串上畫面的長度上限（呈現保護；全文另 print 進 log）。
_ERR_MAX = 300


def _clip(text: object) -> str:
    """錯誤字串原樣（上畫面前只截長度）。⚠️ 未經金鑰遮蔽：UI2 守衛禁止識別字含 secrets（Batch 3
    `check_no_oauth_or_sheet`），本批不放寬該守衛；兩個讀取皆為本地檔、不涉憑證（BACKLOG `NUI2-REALFEED-ERROR-SCRUB`）。"""
    s = "" if text is None else str(text)
    return s if len(s) <= _ERR_MAX else s[:_ERR_MAX] + "…"


def _err(e: BaseException) -> str:
    return _clip(f"{type(e).__name__}: {e}") or type(e).__name__


def _read_twii() -> tuple[TwiiFact | None, str]:
    try:
        from src.services.market_twii_view_service import get_twii_trend_view
        v = get_twii_trend_view(TWII_CARD_DAYS)
        return TwiiFact(
            ok=bool(v.ok), close=tuple(v.close), as_of=v.as_of, is_stale=v.is_stale,
            stale_reason=_clip(v.stale_reason), age_days=v.age_days,
            upstream_error=_clip(v.upstream_error), error=_clip(v.error),
            failed=bool(v.failed), source=str(v.source)), ""
    except Exception as e:  # noqa: BLE001 — 讀不到就講出來（§1）；由 real_canonical 映射 Unavailable
        print(f"[ui2.real_feed] 台股加權指數讀取失敗：{type(e).__name__}: {e}")
        return None, _err(e)


def _read_regime() -> tuple[RegimeFact | None, str]:
    try:
        from src.services.allocation_service import get_macro_regime
        d = get_macro_regime(strict=True, require_valid_risk_cap=True)
        return RegimeFact(regime=str(d["regime"]), light=str(d["light"]), source=str(d["source"]),
                          is_loaded=bool(d["is_loaded"]),
                          file_error=_clip(d.get("file_error") or "")), ""
    except Exception as e:  # noqa: BLE001 — strict：讀壞了 ≠ 未評估；由 real_canonical 映射 Unavailable
        print(f"[ui2.real_feed] 市場位階讀取失敗：{type(e).__name__}: {e}")
        return None, _err(e)


def read_real_snapshot() -> RealFeedSnapshot:
    """一次 rerun 的真資料快照（唯讀；兩個事實各自隔離）。"""
    twii, twii_err = _read_twii()
    regime, regime_err = _read_regime()
    return RealFeedSnapshot(twii=twii, twii_error=twii_err, regime=regime, regime_error=regime_err)
