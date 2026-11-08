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
例外與 canonical 契約違反一律在讀取期接住 → 該事實只記錯誤代碼（例外型別名，僅存 snapshot 內部欄位；訊息全文只 print 進 log；P1 QA 起畫面一律不放型別名）→
由 `real_canonical` 映射成紅色 Unavailable；兩個事實互相隔離（一個壞不拖垮另一個）。
"""
from __future__ import annotations

from src.services.ui2.real_canonical import (
    ERROR_CODE_RE, RealFeedSnapshot, RegimeFact, TwiiFact, exception_code, validate_regime_fact,
    validate_twii_fact,
)

#: 卡片只顯示最新一筆收盤（取尾端 1 個交易日；「畫幾天」屬呈現決策，卡片＝1）。
TWII_CARD_DAYS = 1


def _code(e: BaseException) -> str:
    """snapshot 只留例外型別名（內部代碼）；契約違反＝固定代碼。訊息全文只進 log（⛔ token／路徑上畫面）。畫面**不放**型別名（`real_canonical._error_text` 一律固定人話句）。"""
    return exception_code(e)


def _type_of_service_error(text: str) -> str:
    """service 的 `error`（`"{型別}: {訊息}"`）→ 只取型別名（正規式＋長度上限）；不符 → `ServiceError`。"""
    head = (text or "").split(":", 1)[0].strip()
    return head if ERROR_CODE_RE.match(head) else "ServiceError"


def _read_twii() -> tuple[TwiiFact | None, str]:
    try:
        from src.services.market_twii_view_service import get_twii_trend_view
        v = get_twii_trend_view(TWII_CARD_DAYS)
        if v.upstream_error:
            print(f"[ui2.real_feed] 台股快取上游最近一次錯誤（只進 log）：{v.upstream_error}")
        if v.error:
            print(f"[ui2.real_feed] 台股讀取說明（只進 log）：{v.error}")
        # B2(DEC-148):三態由 L3 service(TwiiTrendView,經 L0 `shared.upstream_state` 統一判定)給出;feed 只拷貝。
        fact = TwiiFact(
            ok=bool(v.ok), close=tuple(v.close), as_of=v.as_of, is_stale=v.is_stale,
            stale_reason=str(v.stale_reason or ""), age_days=v.age_days,
            has_upstream_error=(v.upstream_state == "FETCH_FAILED"),
            error_type=_type_of_service_error(v.error) if v.failed else "",
            failed=bool(v.failed), source=str(v.source), upstream_state=v.upstream_state)
        validate_twii_fact(fact)                # 讀取期驗契約：違反 → 本事實 Unavailable，另一事實照常
        return fact, ""
    except Exception as e:  # noqa: BLE001 — 讀不到就講出來（§1）：log 全文、snapshot 只留型別名代碼、畫面只放固定句
        print(f"[ui2.real_feed] 台股加權指數讀取失敗：{exception_code(e)}: {e}")
        return None, _code(e)


def _read_regime() -> tuple[RegimeFact | None, str]:
    try:
        from src.services.allocation_service import get_macro_regime
        d = get_macro_regime(strict=True, require_valid_risk_cap=True)
        if d.get("file_error"):
            print(f"[ui2.real_feed] 位階契約帶 file_error（不呈現、不影響位階；只進 log）：{d.get('file_error')}")
        fact = RegimeFact(regime=str(d["regime"]), light=str(d["light"]), source=str(d["source"]),
                          is_loaded=bool(d["is_loaded"]), has_file_error=bool(d.get("file_error")))
        validate_regime_fact(fact)              # 讀取期驗契約
        return fact, ""
    except Exception as e:  # noqa: BLE001 — strict：讀壞了 ≠ 未評估；log 全文、snapshot 只留型別名代碼、畫面只放固定句
        print(f"[ui2.real_feed] 市場位階讀取失敗：{exception_code(e)}: {e}")
        return None, _code(e)


def read_real_snapshot() -> RealFeedSnapshot:
    """一次 rerun 的真資料快照（唯讀；兩個事實各自隔離）。"""
    twii, twii_err = _read_twii()
    regime, regime_err = _read_regime()
    return RealFeedSnapshot.of(twii, twii_err, regime, regime_err)
