"""src/services/core_summary_service.py — 核心總表接線層(L3 Service,E1 v19.185)。

職責一句話
----------
把 8 個 KPI 的 **既有 SSOT producer** 接到一起,產出唯一一份 `CoreSummary`;
判定與格式化全在 L0 `shared/core_summary.py`,本層只做「取數 + 降級」。

資料流(依賴方向由高到低,無上行)::

    app.py (L6)
      └─ compute_tab_coverage()  (L5, 由 L6 注入 → 見下方「KPI 5/6 為何用注入」)
      └─ get_core_summary()      (L3, 本檔)
            ├─ allocation_service.get_macro_regime() / get_allocation()  (L3)
            ├─ daily_key_alerts.collect_key_alerts()                     (L2)
            ├─ scorability.summarize_candidates()                        (L2)
            └─ shared.core_summary.assemble_core_summary()               (L0)
      └─ render_core_summary()   (L4, 純渲染)

四條硬約束
----------
1. **不觸發任何 fetch。** 本層只讀 `session_state` 與 `macro_state.json`,
   一行 HTTP 都不打。總表的語意是「顯示已經算過的東西」;沒算過就顯示
   ⬜ 未評估 + 引導。否則原本 button-gated 的抓取路徑會變成無條件執行
   (app.py 的 5 個 `st.button` gate + tab_macro 的一鍵更新)。
2. **不 `from app import`。**(F2 2026-08 更新:原文寫「全專案已有 5 處 L5→L6
   late import」—— 那 5 處已全數收斂,production code 現為 **0 處**,見
   CLAUDE.md V-UP-APP-1 結案說明。)本檔一開始就沒沾,維持 0
   (需要 AI 走 `src/services/app_ai_service`;此處根本不需要 AI)。
3. **不 import `src.ui.*`。** L3 不得 import L5(§8.2)。KPI 5/6 因此走注入 —— 見下。
4. **不重算任何已有 producer 的數字。** 每個 KPI 只搬既有 SSOT 的輸出。

時序:為什麼 caller 必須在所有 tab render **之後**才呼叫
--------------------------------------------------------
`app.py:484-502` 記錄過同款事故(v19.171 🔴-1):頁首的 module-level 區塊執行順序
**早於** `with tab_x:`,而它要讀的 `warroom_summary` / `mkt_info` 是 tab render 時
才寫進 session_state 的 → 置底紅綠燈實機上**永遠**停在「⬜ 未評估」。
核心總表放頁首會 100% 複製這個 bug,所以:

- 版面位置:`st.empty()` 佔位在**最頂端**(使用者看到的位置);
- 執行時機:內容在**所有 tab render 完**之後才填(本函式此時才被呼叫)。

另外本層**刻意不撿 tab 的殘留衍生值**:regime / 持股 % 一律向 canonical 的
`allocation_service` 取(它內部每次由來源重算,不依賴任何會被整包覆寫的中繼 key),
而不是讀 `warroom_summary['throttle']` 那種曾被 `section_state` 抹掉的欄位。
只有「原始輸入」才從 session 讀(`macro_alerts` / `macro_info` / `li_latest` /
`t3_data`)—— 它們是產生端寫入的原始資料,不是別人算過的結論。

KPI 5(覆蓋率)/ 6(新鮮度)為何用「由 L6 注入」而不是自己算
---------------------------------------------------------
兩者的唯一 producer 是 `src/ui/pages/data_coverage.compute_tab_coverage()`,
它在 **L5**。L3 不得 import L5(§8.2 硬規則),而在本層「照抄一份覆蓋率算法」
正是本次要消滅的缺陷(同一個量兩個實作 → 兩個答案)。
故採 **caller 注入**:L6 `app.py` 同時看得到 L5 與 L3(合法),由它把
`compute_tab_coverage()` 的結果傳進來。依賴方向 L6→L5、L6→L3,零上行。
未注入時兩格誠實顯示 ⬜ 未評估(不猜、不留白)。

長期正解是把 `compute_tab_coverage` 的純計算部分下沉 L2,由 L5 與 L3 共用;
該檔不在本次可改範圍,故先以注入解,不製造第二份實作。
"""
from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from shared.core_summary import CoreSummary, CoreSummaryInputs, assemble_core_summary


def _resolve_session(session: Optional[Mapping]) -> Mapping:
    """`session=None` → `st.session_state`;否則用注入的 mapping(測試/其他 caller)。

    streamlit 為**函式內 import**:L3 允許 import streamlit(§8.2),此處延後只是
    為了讓「已注入 session」的呼叫路徑完全不碰 streamlit(單測不必架 stub)。
    這不是在躲分層規則(L3→streamlit 本來就合法),與 `V-L0-NAME-1` 那種
    「late import 藏違憲」性質不同。
    """
    if session is not None:
        return session
    import streamlit as st
    return st.session_state


def _safe(label: str, fn: Callable[[], Any]) -> Any:
    """取數失敗 → 回**原始例外物件**(不是 None)。

    為什麼不回 None:None 會讓下游把「炸了」顯示成「未評估」—— 那是 §1 明令
    禁止的靜默降級。回例外物件後,`shared.core_summary` 的 builder 會原樣
    re-raise,組裝層再轉成 `failed` cell 並印出**原始 exception type**。
    """
    try:
        return fn()
    except Exception as _e:  # noqa: BLE001 — 單一 KPI 取數失敗不得拖垮整張表
        print(f'[core_summary] 取「{label}」失敗：{type(_e).__name__}: {_e}')
        return _e


def get_core_summary(
    *,
    session: Optional[Mapping] = None,
    coverage_rows: Any = None,
    macro_state: Any = None,
    allocation: Any = None,
) -> CoreSummary:
    """組裝核心總表(唯讀,零 fetch)。

    Args:
        session: session_state 的替身(測試 / 其他 caller 注入)。None → 真的
            `st.session_state`。
        coverage_rows: `compute_tab_coverage()` 的輸出。**必須由 L6 注入**
            (L3 不得 import L5);未給 → KPI「資料覆蓋率」「資料新鮮度」誠實顯示
            ⬜ 未評估。
        macro_state / allocation: 覆寫用(預設向 `allocation_service` 取)。
            production 一律走預設路徑 —— 覆寫參數只給測試做依賴注入,
            **不構成第二個 producer**。

    Returns:
        `CoreSummary`;任一 KPI 取數失敗只影響那一格。

    Note:
        §1:本函式不會為了「讓畫面好看」而填任何預設值。未載入 = ⬜ 未評估,
        取數失敗 = ❌ + exception type,兩者在畫面上分得出來。
    """
    _ss = _resolve_session(session)

    def _get(key: str, default: Any = None) -> Any:
        try:
            return _ss.get(key, default)
        except Exception as _e:  # noqa: BLE001 — session 型別異常不得炸總表
            print(f'[core_summary] 讀 session["{key}"] 失敗：'
                  f'{type(_e).__name__}: {_e}')
            return default

    # ── KPI 1/2/3：總經燈號 / 建議持股 / 硬否決天花板 ──────────────────────
    # 一律向 canonical 的 allocation_service 取（它每次由來源重算），
    # **不**讀 warroom_summary['throttle'] 之類會被整包覆寫的中繼 key。
    if macro_state is None:
        macro_state = _safe('總經燈號', _lazy_macro_regime)
    if allocation is None:
        allocation = _safe('建議持股', _lazy_allocation)

    # ── KPI 4：今日關鍵警示 ───────────────────────────────────────────────
    # `threshold_scanned` 契約逐字對齊 `macro_ui_components.key_alerts_banner`：
    # None（section_mid 這輪沒跑）與 []（跑了但一個指標都沒取到）都 falsy，
    # 兩者都是「未評估」，**不得**顯示成「無異常」。
    _raw_alerts = _get('macro_alerts')
    _alerts = _safe('今日關鍵警示',
                    lambda: _collect_alerts(_raw_alerts, _get('macro_info')))

    # ── KPI 7：值凍結告警（先行指標）──────────────────────────────────────
    _leading = _get('li_latest')

    # ── KPI 8：個股組合候選統計 ───────────────────────────────────────────
    _stats = _safe('個股組合候選', lambda: _candidate_stats(_get('t3_data')))

    return assemble_core_summary(CoreSummaryInputs(
        macro_state=macro_state,
        allocation=allocation,
        coverage_rows=coverage_rows,
        leading_df=_leading,
        alerts=_alerts,
        alerts_threshold_scanned=bool(_raw_alerts),
        candidate_stats=_stats,
    ))


# ── 內部：延後 import 的 producer 取數(避免 module import 時拉整條依賴鏈)──────
def _lazy_macro_regime() -> dict:
    from src.services.allocation_service import get_macro_regime
    return get_macro_regime()


def _lazy_allocation():
    from src.services.allocation_service import get_allocation
    return get_allocation()


def _collect_alerts(raw_alerts: Any, macro_info: Any) -> dict:
    """L2 純函式,零 I/O。與 `tab_macro` 用的是**同一支**,給定同輸入必同輸出。"""
    from src.compute.macro.daily_key_alerts import collect_key_alerts
    return collect_key_alerts(raw_alerts, macro_info)


def _candidate_stats(t3_data: Any):
    """`session_state['t3_data']` → `CandidateStats`;沒跑過批次分析 → None。

    分子/分母都由 `summarize_candidates` 這一支決定(B5-b 的教訓:分子取自
    `score_t3`、分母取自 `results_t3` 兩個不等長 list → 同頁兩個母體)。
    """
    if not isinstance(t3_data, dict):
        return None
    _results = t3_data.get('results')
    if not _results:
        return None
    from src.compute.screener.scorability import summarize_candidates
    return summarize_candidates(_results, t3_data.get('score_t3') or [])
