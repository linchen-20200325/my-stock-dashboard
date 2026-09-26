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
    #: 「登入 token / Sheet 識別碼」這兩次讀取**拋了例外**(或 OAuth 模組載不進來)時的 repr;
    #: 空字串 = 兩次讀取都正常完成(含「真的沒有」)。**只加不改**(2026-09-26 批次 7):
    #: 有值時 status 仍照舊降成 unbound(全域狀態列等既有 caller 一字不變,它們不讀本欄);
    #: 💼 我的持股頁讀本欄,把「讀失敗」還原成紅卡,而不是「你還沒有綁定」的灰卡。
    #: ⚠️ 組合清單(list_portfolios)讀取失敗**不**記在這裡 —— 那一種既有契約是
    #: status=bound + portfolio_count=None(綁定本身是讀到的),頁面另有處理。
    read_error: str = ""


def get_binding_state() -> BindingState:
    """讀目前投組 Sheet 綁定狀態,回三態。**純讀不寫**。

    未登入 / 未綁 → unbound(登入才是使用綁定的前提,故未登入一律 unbound,即使 ?sheet= 已還原)。
    已登入 + 已綁 → 讀 list_portfolios(active sheet,cached TTL_15MIN)判空/有;失敗回中性 bound。

    「沒有」與「讀失敗」分開記(`read_error`,批次 7):
      · token 不在 / Sheet 識別碼沒設 → unbound,`read_error=""`(**有效結果**)。
      · OAuth Client 沒設定(`is_oauth_configured()` 為 False)→ 同上,**算「還沒設定」不算失敗**:
        它是讀到了、答案是「沒有設定」;沒有設定就不可能有人在本 session 登入過
        (token 只由 `handle_oauth_callback` 寫入,它在沒設定時直接 return)。
      · 讀 token / 讀 Sheet 識別碼**拋例外**,或 `oauth_state` 模組載不進來(L1
        `_has_oauth_tokens()` 會把它吞成 False)→ status 照舊 unbound,`read_error` 帶例外 repr。
    """
    from src.data.portfolio import gsheet_portfolio as _gsp   # L3→L1(正常方向)

    _errs: list[str] = []
    try:
        _logged = bool(_gsp._has_oauth_tokens())
    except Exception as _e:  # noqa: BLE001 — 讀 token 失敗視為未登入(§1 不假裝已登入)
        _logged = False
        _errs.append(repr(_e))   # 仍視為未登入,但**記下來**:這不是「沒登入」,是讀不到
    else:
        if not _logged:
            # L1 在 oauth_state import 失敗時也回 False(既有行為不動)—— 分出那一種。
            _imp = _gsp._oauth_import_error()
            if _imp:
                _errs.append(_imp)
    try:
        _sid = _gsp._get_active_sheet_id() or ""
    except Exception as _e:  # noqa: BLE001
        _sid = ""
        _errs.append(repr(_e))
    _read_err = "; ".join(_errs)

    if not _logged or not _sid:
        return BindingState(logged_in=_logged, sheet_id=_sid,
                            portfolio_count=None, status=STATUS_UNBOUND,
                            read_error=_read_err)

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
