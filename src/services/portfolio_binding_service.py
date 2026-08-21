"""L3 Service — 投組 Sheet 綁定狀態(供全域「🔗 我的組合」狀態列讀取)。

P3a(v19.207 順暢化):把「有沒有登入 / 綁到哪本 Sheet / 有沒有組合資料」的判定集中成一個
L3 read service,讓全域狀態列(L5)不必自己散打 L1、也把三態(未綁 / 綁了但空 / 已綁 N 本)
的判斷收在一處(多讀 + 後處理 = 真 L3 編排,非 pure pass-through)。

§8.2:L3 → L1 gsheet_portfolio(正常 service→data 方向)。§1:任何一步讀取失敗都 graceful
degrade,**不炸**(狀態列是全域 chrome,不可因附帶讀取失敗擋住整個 app);但降級是「誠實少顯示」
而非「假裝有資料」——讀不到組合數就回 None,不腦補 0/假數。
"""
from __future__ import annotations

from dataclasses import dataclass

# 綁定狀態三態(§1 不混:綁定 ≠ 有資料)
STATUS_UNBOUND = "unbound"          # 未登入 or 未選 Sheet → 要先登入 + 挑 Sheet
STATUS_BOUND_EMPTY = "bound_empty"  # 綁了 Sheet 但沒有任何組合資料
STATUS_BOUND = "bound"              # 綁了 Sheet 且有 N 本組合


@dataclass(frozen=True)
class BindingState:
    logged_in: bool
    sheet_id: str
    portfolio_count: "int | None"   # None = 未知(未綁 or 讀取失敗);不腦補 0
    status: str                     # STATUS_* 之一


def get_binding_state() -> BindingState:
    """讀目前投組 Sheet 綁定狀態,回三態。**純讀不寫**。

    未登入 / 未綁 → unbound(登入才是使用綁定的前提,故未登入一律 unbound,即使 ?sheet= 已還原)。
    已登入 + 已綁 → 讀 list_portfolios(active sheet,cached TTL_15MIN)判空/有;失敗回中性 bound。
    """
    from src.data.portfolio import gsheet_portfolio as _gsp   # L3→L1(正常方向)

    try:
        _logged = bool(_gsp._has_oauth_tokens())
    except Exception:  # noqa: BLE001 — 讀 token 失敗視為未登入(§1 不假裝已登入)
        _logged = False
    try:
        _sid = _gsp._get_active_sheet_id() or ""
    except Exception:  # noqa: BLE001
        _sid = ""

    if not _logged or not _sid:
        return BindingState(logged_in=_logged, sheet_id=_sid,
                            portfolio_count=None, status=STATUS_UNBOUND)

    # 已登入 + 已綁 → 看有沒有組合資料(區分 🟡 空 vs 🟢 有)。
    # ⚠️ 明確傳 sheet_id=_sid(而非預設 None):list_portfolios 以參數為 @st.cache_data 快取鍵,
    # 傳 None 時鍵恆為空、內部才靠 session 解析 active sheet → 換 Sheet 後 15 分鐘內會拿到
    # **上一本的本數**(張冠李戴)。傳 _sid 讓快取鍵隨 Sheet 變動,一併正確定位(§ P3a 稽核 #3)。
    try:
        _count = len(_gsp.list_portfolios(sheet_id=_sid))
    except Exception:  # noqa: BLE001 — 讀組合清單失敗 → 中性「已綁定」,不炸狀態列、不腦補
        return BindingState(logged_in=_logged, sheet_id=_sid,
                            portfolio_count=None, status=STATUS_BOUND)
    if _count == 0:
        return BindingState(logged_in=_logged, sheet_id=_sid,
                            portfolio_count=0, status=STATUS_BOUND_EMPTY)
    return BindingState(logged_in=_logged, sheet_id=_sid,
                        portfolio_count=_count, status=STATUS_BOUND)
