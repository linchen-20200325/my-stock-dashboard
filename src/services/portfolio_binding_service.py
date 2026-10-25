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
    #: 1.0-B2(只加不改):本 session 的 Google 登入因「token 過期且無 refresh_token」被清掉、之後還沒
    #: 重新登入。只在 `logged_in=False` 時可能為 True。頁面據此把「未登入」那張**灰**卡寫成
    #: 「登入已逾時，請重新整理」(⛔ 不是紅色錯誤,稽核 SA2 MUST-1)。既有 caller 不讀本欄,一字不變。
    login_expired: bool = False
    #: Sheet Safety 批 B1(只加不改,2026-10-25):讀組合清單那一步**為什麼**沒拿到本數。空字串 = 讀到了。
    #: · `worksheet_missing`:這本 Sheet 沒有 `portfolios` 分頁(讀取不再替你建)→ status=bound_empty、
    #:   `portfolio_count=None`(⛔ 不寫 0 —— 沒有分頁 ≠ 讀到 0 本);
    #: · 其他(L1 `classify_read_error` 代碼,例 `schema_mismatch` / `permission_denied` / `error:<型別>`)→
    #:   維持既有降級 status=bound + `portfolio_count=None`。既有 caller 不讀本欄,一字不變。
    sheet_issue: str = ""
    #: 👤 我的 P1(只加不改,DEC-083 Q6):`get_binding_state(ssot=True)` 時 = `get_active_sheet().state`
    #: (`ACTIVE_*` 之一);預設呼叫(舊狀態列等)恆為空字串、一字不變。
    active_state: str = ""


def is_login_required_error(exc: BaseException) -> bool:
    """`exc` 是不是 L1 的 `LoginRequiredError`(沒登入 / 登入已逾時)。

    給 L5 頁面用:L5 不得直接 import L1(§8.2),經本支判斷「這不是讀取失敗,是沒有登入」。
    L1 載不進來 → False(照舊當一般例外,由呼叫端畫紅 —— 那時確實是故障)。
    """
    try:
        from src.data.portfolio.gsheet_portfolio import LoginRequiredError   # L3→L1
    except Exception:  # noqa: BLE001
        return False
    return isinstance(exc, LoginRequiredError)


#: Sheet Safety 批 QA 回修(N-2):`sheet_read_issue()` 的「表頭不符」代碼(值同 L1 `READ_SCHEMA_MISMATCH`)。
SHEET_ISSUE_SCHEMA_MISMATCH = "schema_mismatch"


def sheet_read_issue(exc: BaseException) -> str:
    """讀取例外 → 分類代碼(L1 `classify_read_error`;例 `schema_mismatch` / `permission_denied`)。

    給 L5 頁面用(L5 不得直接 import L1,§8.2):拿來挑「怎麼辦」那一句 —— 表頭不符時叫人去改第一列,
    ⛔ 不叫人重新登入 / 查網路(那是錯的指引)。L1 載不進來 → `error:<型別>`。
    """
    try:
        from src.data.portfolio import gsheet_portfolio as _gsp   # L3→L1
    except Exception:  # noqa: BLE001
        return f"error:{type(exc).__name__}"
    return _classify_read_error(_gsp, exc)


def portfolio_worksheet_headers() -> tuple[str, ...]:
    """`portfolios` 分頁應有的第一列(L1 `_HEADERS`;給 L5「把第一列改成…」那一句用)。純讀常數。"""
    from src.data.portfolio import gsheet_portfolio as _gsp   # L3→L1
    return tuple(_gsp._HEADERS)


def _login_expired(_gsp) -> bool:
    try:
        return bool(_gsp.login_expired())
    except Exception:  # noqa: BLE001 — 讀不到旗標 ⇒ 退回一般「未登入」說法(仍是灰色有效態)
        return False


def _with_login_expired(state: BindingState, _gsp) -> BindingState:
    """未登入時補上 `login_expired`(1.0-B2);已登入 → 原樣回傳。⛔ 不改其他任何欄位。"""
    if state.logged_in or not _login_expired(_gsp):
        return state
    from dataclasses import replace
    return replace(state, login_expired=True)


def get_binding_state(*, ssot: bool = False) -> BindingState:
    """讀目前投組 Sheet 綁定狀態,回三態。**純讀不寫**。

    ssot(👤 我的 P1,DEC-083 Q6/B4,只加不改):
      · False(預設)→ 既有行為**一字不變**(舊「🔗 我的組合」狀態列等仍讀 legacy 通道 ＋ secrets 預設)。
      · True(新版 UI)→ 「綁到哪本」改讀 `get_active_sheet()`:只有兩格綁定**同一本**(`ACTIVE_OK`)才算綁;
        組合 / 觀察清單指向不同本(`ACTIVE_DIVERGED`)、只有 secrets 部署預設(`ACTIVE_DEPLOY_DEFAULT_ONLY`)
        一律當**未綁**(⛔ 不偷選其中一本、⛔ 不把部署預設當成使用者的選擇)。`active_state` 帶出是哪一種。
        登入判定與 read_error 與預設呼叫**同一份**(`_read_login_and_sheet`,⛔ 不抄第二份)。

    未登入 / 未綁 → unbound(登入才是使用綁定的前提,故未登入一律 unbound,即使 ?sheet= 已還原)。
    已登入 + 已綁 → 讀 list_portfolios(active sheet,cached TTL_15MIN,SEC-1 起鍵含身分)判空/有;失敗回中性 bound。

    「沒有」與「讀失敗」分開記(`read_error`,批次 7):
      · token 不在 / Sheet 識別碼沒設 → unbound,`read_error=""`(**有效結果**)。
      · OAuth Client 沒設定(`is_oauth_configured()` 為 False)→ 同上,**算「還沒設定」不算失敗**:
        它是讀到了、答案是「沒有設定」;沒有設定就不可能有人在本 session 登入過
        (token 只由 `handle_oauth_callback` 寫入,它在沒設定時直接 return)。
      · 讀 token / 讀 Sheet 識別碼**拋例外**,或 `oauth_state` 模組載不進來(L1
        `_has_oauth_tokens()` 會把它吞成 False)→ status 照舊 unbound,`read_error` 帶例外 repr。
      · secrets 檔**格式錯誤**(TOML 解析失敗)或讀取例外 —— L1 `_get_active_sheet_id()` /
        `oauth_state._safe_secret()` 都會把它吞成「沒設定」→ 同上(L1 `_secrets_read_error()`
        以 Streamlit 的例外鏈分辨,不比對訊息;「沒有 secrets 檔」仍是有效結果)。
    """
    from src.data.portfolio import gsheet_portfolio as _gsp   # L3→L1(正常方向)

    _logged, _sid, _read_err = _read_login_and_sheet(_gsp)
    _active_state = ""
    if ssot:
        _sid, _active_state, _read_err = _ssot_sheet(_read_err)

    if not _logged or not _sid:
        return _with_login_expired(_with_active_state(BindingState(logged_in=_logged, sheet_id=_sid,
                            portfolio_count=None, status=STATUS_UNBOUND,
                            read_error=_read_err), _active_state), _gsp)

    # 已登入 + 已綁 → 看有沒有組合資料(區分 🟡 空 vs 🟢 有)。
    # ⚠️ 明確傳 sheet_id=_sid(而非預設 None)。SEC-1 起 L1 快取鍵＝(身分指紋, 實際 sheet_id),
    # None 也會先解析成 active sheet 再建鍵;但修 SEC-1 前鍵只有參數,傳 None 時鍵恆為空 →
    # 換 Sheet 後 15 分鐘內拿到**上一本的本數**(張冠李戴,§ P3a 稽核 #3)。顯式傳 _sid 讓讀哪一本
    # 由本檔說清楚,不依賴 L1 的解析細節。
    try:
        # B1:raise_if_missing=True ⇒「沒有 portfolios 分頁」不再被讀成「0 本」(也不再被讀取順手建出來)。
        _count = len(_gsp.list_portfolios(sheet_id=_sid, raise_if_missing=True))
    except Exception as _e:  # noqa: BLE001 — 讀組合清單失敗 → 中性「已綁定」,不炸狀態列、不腦補
        if is_login_required_error(_e):
            # 1.0-B2(稽核 SA2 MUST-1):這一次讀取期間登入被清掉了(token 過期且無 refresh_token,
            # L1 已清 session)→ **不是**讀取失敗,也⛔ 不得回舊的 logged_in=True(那會讓下游再打一次、
            # 拿到「請先登入」並畫成紅卡)。重讀一次登入狀態 → 照實回「未登入 / 未綁」。
            _logged, _sid, _read_err = _read_login_and_sheet(_gsp)
            if ssot:
                _sid, _active_state, _read_err = _ssot_sheet(_read_err)
            return _with_login_expired(_with_active_state(BindingState(
                logged_in=_logged, sheet_id=_sid, portfolio_count=None,
                status=STATUS_UNBOUND, read_error=_read_err), _active_state), _gsp)
        _issue = _classify_read_error(_gsp, _e)
        if _issue == getattr(_gsp, "READ_WORKSHEET_MISSING", None):
            # 綁定讀到了、那本 Sheet 也在,只是還沒有 `portfolios` 分頁 ＝「綁了但空」(灰,有效結果);
            # 本數**未知**(None),⛔ 不寫 0。
            return _with_active_state(BindingState(logged_in=_logged, sheet_id=_sid, portfolio_count=None,
                                status=STATUS_BOUND_EMPTY, sheet_issue=_issue), _active_state)
        return _with_active_state(BindingState(logged_in=_logged, sheet_id=_sid,
                            portfolio_count=None, status=STATUS_BOUND, sheet_issue=_issue), _active_state)
    if _count == 0:
        return _with_active_state(BindingState(logged_in=_logged, sheet_id=_sid,
                            portfolio_count=0, status=STATUS_BOUND_EMPTY), _active_state)
    return _with_active_state(BindingState(logged_in=_logged, sheet_id=_sid,
                        portfolio_count=_count, status=STATUS_BOUND), _active_state)


def _with_active_state(state: BindingState, active_state: str) -> BindingState:
    """ssot 呼叫時補上 `active_state`;預設呼叫(空字串)→ 原物件照回(既有 caller 一字不變)。"""
    if not active_state:
        return state
    from dataclasses import replace
    return replace(state, active_state=active_state)


def _ssot_sheet(read_err: str) -> "tuple[str, str, str]":
    """ssot 用:`(active sheet_id 或 "", active_state, read_error)`。

    只有 `ACTIVE_OK` 才回 sheet_id;快照讀不出來 → 併入 read_error(⛔ 不吞成「沒綁」,同 `read_error` 既有語意)。
    """
    _a = get_active_sheet()
    # 同一個讀取例外（例:session 本身讀不出來)兩邊都會記到 ⇒ 去重,⛔ 不重複列同一句。
    _err = "; ".join(dict.fromkeys(_x for _x in (read_err, _a.read_error) if _x))
    return (_a.sheet_id if _a.state == ACTIVE_OK else ""), _a.state, _err


def _classify_read_error(_gsp, exc: BaseException) -> str:
    """L1 `classify_read_error`(B1);L1 版本太舊 / 分類本身出錯 → `error:<型別>`(⛔ 不吞成空字串)。"""
    try:
        return str(_gsp.classify_read_error(exc))
    except Exception:  # noqa: BLE001
        return f"error:{type(exc).__name__}"


def _read_login_and_sheet(_gsp) -> "tuple[bool, str, str]":
    """「登入 token / Sheet 識別碼」那兩次讀取(**不連 Google、不讀組合清單**)。

    回 `(logged_in, sheet_id, read_error)`。批 Z54 自 `get_binding_state()` 原樣抽出(一行未改,
    該函式行為不變),讓 `get_binding_presence()` 共用同一份判定 —— ⛔ 不抄第二份。
    """
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
    if not _logged or not _sid:
        # secrets 檔格式錯誤時,L1 兩處(Sheet 識別碼 / OAuth Client 設定)都把它吞成「沒設定」
        # (既有行為不動)—— 只在要回 unbound 時分出那一種。L1 只交型別名;上面讀 Sheet 識別碼
        # 已經以同一型別記過(repr 以型別名開頭)就不重複記。
        _sec = _gsp._secrets_read_error()
        if _sec and not any(_x.startswith(_sec + "(") for _x in _errs):
            _errs.append(_sec)
    _read_err = "; ".join(_errs)
    return _logged, _sid, _read_err


@dataclass(frozen=True)
class BindingPresence:
    """「有沒有綁」—— 只回答這一件事,**不含組合本數**(批 Z54)。

    Attributes:
        logged_in: Google 有沒有登入。
        sheet_bound: ~~已登入 **且** 已設 Sheet 識別碼(同 `get_binding_state()` 的非 unbound 判定)。~~
            (👤 我的 P1,DEC-083,有意識的修改,⛔ 不是漏刪:唯一 consumer「🚦 今天」是新版 UI,改讀新版 SSOT。)
            現行:已登入 **且** active Sheet 成立(`ACTIVE_OK`;同 `get_binding_state(ssot=True)` 的非 unbound 判定)。
            只有 secrets 部署預設 / 組合與觀察清單指向不同本 ⇒ False。
        read_error: 同 `BindingState.read_error`(讀 token / Sheet 識別碼拋例外時的 repr)。
        active_state: `get_active_sheet().state`(👤 我的 P1,只加不改)。
    """

    logged_in: bool
    sheet_bound: bool
    read_error: str = ""
    active_state: str = ""


def get_binding_presence() -> BindingPresence:
    """只讀「有沒有綁」,**⛔ 不呼叫 `list_portfolios`(不連 Google)**。純讀不寫。

    給「🚦 今天」頂部狀態列「Sheet 綁定」那一格用:那一格只回答有沒有綁,
    不需要組合本數;改走 `get_binding_state()` 的話,已登入＋已設 Sheet 時每一輪都會
    讀組合清單,而讀失敗(L3 吞成中性 bound、⛔ 不入快取)會讓**每一次 rerun 都重打 Google**。
    判定與 `get_binding_state()` 共用 `_read_login_and_sheet()`(同一份,⛔ 不抄第二份)。
    """
    from src.data.portfolio import gsheet_portfolio as _gsp   # L3→L1(正常方向)

    _logged, _sid, _read_err = _read_login_and_sheet(_gsp)
    # 👤 我的 P1(DEC-083):~~`sheet_bound=bool(_logged and _sid)`(legacy 通道 ＋ secrets 預設)~~ → 新版 SSOT。
    _sid, _active_state, _read_err = _ssot_sheet(_read_err)
    return BindingPresence(logged_in=_logged, sheet_bound=bool(_logged and _sid),
                           read_error=_read_err, active_state=_active_state)


def reload_my_sheet_reads(*sheet_ids: str) -> int:
    """「重新讀取」(Sheet Safety 批 B5,DEC-083):只失效**目前這位使用者 × 這幾本 Sheet** 的讀取快取。

    沒給 sheet_ids → 目前綁定的那本(ETF / 個股兩通道)。別的使用者、本人的其他 Sheet 一律不動;
    ⛔ 不呼叫任何全域 `.clear()`。未登入 → 0(那時讀取本來就不經快取)。回失效的 (身分, Sheet) 筆數。
    **純快取操作,不連 Google、不寫 Sheet。**
    """
    from src.data.portfolio import gsheet_portfolio as _gsp   # L3→L1(正常方向)

    return int(_gsp.invalidate_my_read_cache(*sheet_ids))


# ══ 👤 我的 P1(DEC-083 Q6/Q7/B4):新版 UI 的 Sheet SSOT ═════════════════════════════════════
# 客戶原文 Q6:「組合與觀察清單使用同一本 active Sheet。若 legacy 狀態兩者不一致:顯示白話警示、不偷偷選 ETF 通道、
# 不偷偷選個股通道、不自動覆寫其中一個、讓使用者在 👤 我的明確重新選定。」
# AI 總管裁示:secrets 部署預設在新版 UI **不當 active**(要使用者明確按「使用這本」)。
# 值的 SSOT 在 L0 `shared/sheet_id.py`(PR #927 QA-2:「🚦 今天」也要分辨;本檔同名 re-export,值一字未改)。
from shared.sheet_id import (  # noqa: E402
    ACTIVE_DEPLOY_DEFAULT_ONLY,   # 兩格都沒綁,只有 secrets 部署預設 ⇒ ⛔ 不當 active
    ACTIVE_DIVERGED,              # 兩格不同(含其中一格是空的)⇒ ⛔ 不偷選
    ACTIVE_NONE,                  # 兩格都沒綁、也沒有部署預設
    ACTIVE_OK,                    # 兩格綁定同一本 ⇒ 這本就是 active Sheet
)


@dataclass(frozen=True)
class ActiveSheet:
    """新版 UI 的 active Sheet 判定。⚠️ 只有 `state == ACTIVE_OK` 時 `sheet_id` 非空。

    `portfolio_channel` / `stock_channel` / `deploy_default`:原始值(消毒後),給「👤 我的」畫警示與按鈕用 ——
    ⚠️ 畫面只准顯示它們的末 6 碼(L0 `sheet_id_tail`,Q4)。
    `read_error`:快照本身讀不出來(或 secrets 檔格式錯誤)的說明;非空時 state 為 `ACTIVE_NONE`。
    """

    state: str
    sheet_id: str = ""
    portfolio_channel: str = ""
    stock_channel: str = ""
    deploy_default: str = ""
    read_error: str = ""


def get_active_sheet() -> ActiveSheet:
    """新版 UI 的 active Sheet(純讀,不連 Google、不寫任何東西)。判定順序固定,⛔ 不猜:

    1. 兩格(組合 / 觀察清單)都綁同一本 → `ACTIVE_OK`;
    2. 兩格不同(含其中一格空)→ `ACTIVE_DIVERGED`(⛔ 不偷選、⛔ 不覆寫,由使用者在「👤 我的」重選);
    3. 兩格都空、有 secrets 部署預設 → `ACTIVE_DEPLOY_DEFAULT_ONLY`(⛔ 不當 active);
    4. 都沒有 → `ACTIVE_NONE`。
    """
    from src.data.portfolio import gsheet_portfolio as _gsp   # L3→L1(正常方向)

    try:
        _snap = _gsp.session_binding_snapshot()
    except Exception as _e:  # noqa: BLE001 — 讀不出來 ≠ 沒綁:帶 read_error 交給呼叫端畫紅(§1)
        return ActiveSheet(state=ACTIVE_NONE, read_error=repr(_e))
    _pf, _stk, _dflt = _snap.portfolio_channel, _snap.stock_channel, _snap.deploy_default
    _common = {"portfolio_channel": _pf, "stock_channel": _stk, "deploy_default": _dflt}
    if _pf and _pf == _stk:
        return ActiveSheet(state=ACTIVE_OK, sheet_id=_pf, **_common)
    if _pf or _stk:
        return ActiveSheet(state=ACTIVE_DIVERGED, **_common)
    if _dflt:
        return ActiveSheet(state=ACTIVE_DEPLOY_DEFAULT_ONLY, **_common)
    try:
        _sec = str(_gsp._secrets_read_error() or "")
    except Exception as _e:  # noqa: BLE001
        _sec = repr(_e)
    return ActiveSheet(state=ACTIVE_NONE, read_error=_sec, **_common)


@dataclass(frozen=True)
class ActiveSelection:
    """active Sheet 裡使用者選定分析的那一本組合 / 那一份觀察清單(Q7)。只活在 session。

    `portfolio` / `watchlist`:名稱;空字串 = 還沒選(⛔ 不代表「選了第一本」)。
    `watchlist_skip`:使用者明確選了「不使用觀察清單」。
    ⚠️ 名稱存不存在於那本 Sheet 這裡**不查**(不連 Google);由讀取端(`holdings_service`)對清單核對。
    """

    sheet_id: str = ""
    portfolio: str = ""
    watchlist: str = ""
    watchlist_skip: bool = False


def get_active_selection(sheet_id: "str | None" = None) -> ActiveSelection:
    """`sheet_id` 那本(沒給 → `get_active_sheet()`,只有 `ACTIVE_OK` 才有)的選定。純讀。

    選定綁著選的時候那本 Sheet(L1 `oauth_state.get_active_selection`)⇒ 換了 Sheet 就讀不到舊名字。
    """
    from shared.sheet_id import SELECTION_KIND_PORTFOLIO, SELECTION_KIND_WATCHLIST
    from src.data.portfolio import oauth_state as _ost   # L3→L1(正常方向)

    if sheet_id is None:
        _a = get_active_sheet()
        sheet_id = _a.sheet_id if _a.state == ACTIVE_OK else ""
    if not sheet_id:
        return ActiveSelection()
    _pf = _ost.get_active_selection(SELECTION_KIND_PORTFOLIO, sheet_id) or {}
    _wl = _ost.get_active_selection(SELECTION_KIND_WATCHLIST, sheet_id) or {}
    return ActiveSelection(sheet_id=sheet_id, portfolio=str(_pf.get("name") or ""),
                           watchlist=str(_wl.get("name") or ""),
                           watchlist_skip=bool(_wl.get("skip")))
