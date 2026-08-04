"""src/ui/pages/data_coverage.py — 前 N Tab 資料覆蓋率檢查表(v18.280)

學 Fund 端 ui/tab5_data_guard.py Section ⓪ 的「預設視角」:
user 關心的是「我的某個 Tab 有沒有資料」,而非只看「TWSE API 通不通」。

掛在 🔎 資料診斷 Tab **最上方**(Fund 架構:用戶視角優先,API 端點細節放後)。

純讀 session_state,無副作用(§8.2 L5 UI 規則,不寫入 session_state)。
對外 API:
- compute_tab_coverage() -> list[dict]  純函式,易測
- render_data_coverage() -> None         Streamlit 渲染
"""
from __future__ import annotations

import streamlit as st

# v18.349 — macro_info 核心指標 key 契約走 SSOT(L0)，與 tab_macro 寫入端共用，
# 杜絕 v18.282 那種 key 名各自寫死 → 漂移 → 覆蓋率永遠紅燈。
from shared.macro_buckets import MACRO_INFO_KEYS

# v19.170 P0-4:覆蓋率 ≠ 新鮮度。覆蓋率只問「有沒有值」,問不出「值是不是 9 天沒動
# 的死資料」(稽核實測:前五大留倉/前十大留倉/未平倉口數 7/21~7/31 完全不變,
# 覆蓋率表卻顯示 🟢 3/3 完整)。故本表加「新鮮度」欄,燈號規則走 L0 SSOT。
from shared.data_freshness import freshness_level
from shared.staleness import staleness_days

# 色票(對齊 shared/colors 但本檔不 import 避免循環,診斷頁用內聯 hex)
_C_GREEN = "#3fb950"
_C_YELLOW = "#d29922"
_C_RED = "#f85149"
_C_IDLE = "#666"

# ── 門檻常數(v19.170:原為散在 _coverage_emoji 內的 magic number)─────────
# 覆蓋率 ≥ 85% 才算綠燈:6 個總經指標容忍缺 1 個(5/6=0.83 會落黃燈,7/8=0.875 綠),
# 即「幾乎全到齊」才給綠;≥ 50% 為黃燈(過半有值,可用但殘缺);其餘紅燈。
_COVER_GREEN_RATIO = 0.85
_COVER_YELLOW_RATIO = 0.50
# 新鮮度門檻(日):≤1 日 = 當日(容忍收盤前的自然延遲);≤3 日 = 黃(含一個週末);
# 超過 3 日 = 紅(已跨過一個完整週末仍沒新資料 → 幾乎確定是管線壞了)。
_FRESH_WARN_DAYS = 1
_FRESH_BAD_DAYS = 3

# 新鮮度燈號 → 本表內聯色票(shared.colors 的 hex 與診斷頁色調不同,此處自帶對照)
_FRESH_COLOR = {"🟢": _C_GREEN, "🟡": _C_YELLOW, "🔴": _C_RED, "⬜": _C_IDLE}


def _freshness_of(data, *, date_col: str = "date") -> tuple[str, str]:
    """算單一資料源的 (新鮮度 emoji, label)。無法判定 → ('⬜','未知')。

    lag 天數委派 shared.staleness(日期維度 SSOT),燈號委派 shared.data_freshness,
    本檔只做串接,不自己算日期。
    """
    try:
        _lag = staleness_days(data, date_col=date_col)
    except Exception:  # noqa: BLE001 — 診斷頁不可因單一資料源解析失敗而整頁掛掉
        _lag = None
    return freshness_level(_lag, warn=_FRESH_WARN_DAYS, bad=_FRESH_BAD_DAYS)


def _li_frozen_info(df) -> tuple[bool, float | None]:
    """讀 li_latest 的欄位版 stale 旗標,回 (是否凍結, 凍結分鐘數|None)。

    v19.170:優先讀 `_is_stale` **欄**而非 `df.attrs` —— attrs 在 pandas 多數運算
    與 session_state 往返後會遺失,正是「9 天不變卻無警示」的直接原因
    (見 leading_indicators._mark_stale 註解)。attrs 僅作為向下相容的次選。
    """
    if df is None:
        return (False, None)
    _cols = getattr(df, "columns", None)
    _stale, _age = False, None
    if _cols is not None and "_is_stale" in _cols:
        try:
            _stale = bool(df["_is_stale"].any())
        except Exception:  # noqa: BLE001
            _stale = False
        if _stale and "_stale_age_min" in _cols:
            try:
                _v = df["_stale_age_min"].dropna()
                _age = float(_v.iloc[0]) if len(_v) else None
            except Exception:  # noqa: BLE001
                _age = None
    if not _stale:
        _attrs = getattr(df, "attrs", {}) or {}
        _stale = bool(_attrs.get("is_stale", False))
        if _stale:
            _age = _attrs.get("stale_age_min")
    return (_stale, _age)


def _ss(key: str):
    """安全讀 session_state(測試環境 st 可能 stub)。"""
    try:
        return st.session_state.get(key)
    except Exception:  # noqa: BLE001
        return None


def _coverage_emoji(have: int, total: int) -> tuple[str, str]:
    """依完整率回 (emoji, color)。total=0 → 未觸發。"""
    if total == 0:
        return ("⬜", _C_IDLE)
    r = have / total
    # v19.170:門檻改引模組頂端常數(原為就地 magic number 0.85 / 0.5)
    if r >= _COVER_GREEN_RATIO:
        return ("🟢", _C_GREEN)
    if r >= _COVER_YELLOW_RATIO:
        return ("🟡", _C_YELLOW)
    return ("🔴", _C_RED)


def compute_tab_coverage(state: dict | None = None) -> list[dict]:
    """計算各資料 Tab 覆蓋率。

    state: 測試可注入 dict;None → 讀 st.session_state。
    回傳 list[dict],每筆:
      {tab, emoji, color, ratio_txt, detail, action,
       fresh_emoji, fresh_label, fresh_color}   # v19.170 新增新鮮度三欄
    """
    def _get(key: str):
        if state is not None:
            return state.get(key)
        return _ss(key)

    rows = []

    # ── 🌐 總經:macro_info 6 指標 + M1B-M2 + 領先指標 ──
    # v18.282 修正:用真實 session_state key(原 v18.280 key 名全錯導致永遠紅燈)
    # 實際 macro_info 寫於 tab_macro.py _job_macro,key 為:
    #   vix / ism_pmi / us_core_cpi / fed_funds / ndc_signal / tw_export
    # v18.349:此清單下沉 shared.macro_buckets.MACRO_INFO_KEYS(SSOT)，與
    #   tab_macro 寫入端 has-data 判定共用,杜絕 v18.282 類 key 漂移再現。
    _ma = _get("macro_info") or {}
    _mi = _get("m1b_m2_info") or {}
    _li = _get("li_latest")
    _macro_keys = list(MACRO_INFO_KEYS)
    _macro_have = sum(1 for k in _macro_keys
                      if isinstance(_ma, dict) and _ma.get(k) is not None)
    _macro_total = len(_macro_keys)
    _macro_extra = int(bool(_mi)) + int(_li is not None)
    _macro_have_all = _macro_have + _macro_extra
    _macro_total_all = _macro_total + 2
    # 判 macro_info「有實質資料」:排除純 _ 開頭 meta key(_loaded_at / _all_failed)
    _ma_loaded = isinstance(_ma, dict) and any(
        not str(k).startswith("_") for k in _ma)
    _e1, _c1 = _coverage_emoji(_macro_have_all, _macro_total_all) if _ma_loaded else ("⬜", _C_IDLE)
    # v19.170:總經以 macro_info['_loaded_at'](本輪抓取時間)判新鮮度;未載入 → 未知
    _f1e, _f1l = (_freshness_of(_ma.get("_loaded_at") if isinstance(_ma, dict) else None)
                  if _ma_loaded else ("⬜", "未知"))
    rows.append({
        "tab": "🌐 總經",
        "emoji": _e1, "color": _c1,
        "ratio_txt": f"{_macro_have_all}/{_macro_total_all}" if _ma_loaded else "未載入",
        "detail": (f"VIX/ISM/CPI/Fed/NDC/出口 {_macro_have}/{_macro_total} ｜ "
                   f"M1B-M2 {'✓' if _mi else '✗'} ｜ 領先 {'✓' if _li is not None else '✗'}")
                  if _ma_loaded else "在 🌐 總經 Tab 按更新觸發",
        "action": "缺值 → 看下方 API Key / Proxy 診斷",
        "fresh_emoji": _f1e, "fresh_label": _f1l,
        "fresh_color": _FRESH_COLOR.get(_f1e, _C_IDLE),
    })

    # ── 📈 個股:t2_data 為單一個股 metrics dict(present = 已查)──
    _t2 = _get("t2_data") or {}
    _t2_loaded = isinstance(_t2, dict) and bool(_t2)
    _e2, _c2 = _coverage_emoji(1, 1) if _t2_loaded else ("⬜", _C_IDLE)
    # v19.170:t2_data 為 metrics dict,無統一日期欄 → 誠實回「未知」而非假設當日
    _f2e, _f2l = _freshness_of(_t2.get("date") if isinstance(_t2, dict) else None)
    rows.append({
        "tab": "📈 個股",
        "emoji": _e2, "color": _c2,
        "ratio_txt": "已查" if _t2_loaded else "未查",
        "detail": (f"個股資料已載入（{len(_t2)} 欄）" if _t2_loaded
                   else "在 📈 個股 Tab 查股票代號觸發"),
        "action": "缺資料 → TWSE / FinMind / Yahoo fallback chain",
        "fresh_emoji": _f2e, "fresh_label": _f2l,
        "fresh_color": _FRESH_COLOR.get(_f2e, _C_IDLE),
    })

    # ── 💰 籌碼:cl_data(法人 inst / 融資 margin / 廣度 adl)──
    # 實際 cl_data 寫於 tab_macro.py:1046,key 為:
    #   intl / tw / tech / inst（三大法人）/ margin（融資）/ adl（騰落）
    _cl = _get("cl_data") or {}
    _cl_keys = [("inst", "法人"), ("margin", "融資"), ("adl", "廣度")]
    _cl_have = sum(1 for k, _ in _cl_keys
                   if isinstance(_cl, dict) and _cl.get(k) is not None)
    _e3, _c3 = _coverage_emoji(_cl_have, len(_cl_keys)) if _cl else ("⬜", _C_IDLE)
    # v19.170:籌碼面新鮮度以 li_latest 的 _date 欄(先行指標實際資料日)判定
    _f3e, _f3l = _freshness_of(_li, date_col="_date") if _li is not None else ("⬜", "未知")
    _detail3 = (" ｜ ".join(
        f"{_lbl} {'✓' if (_cl or {}).get(_k) is not None else '✗'}"
        for _k, _lbl in _cl_keys)
        if _cl else "在 🌐 總經 Tab 載入籌碼觸發")
    # ── v19.170 P0-4 強制降級:先行指標走了 stale pickle fallback ────────
    # 這一列是本次稽核事故現場 —— 有值(覆蓋率 3/3 🟢)但值是 9 天前凍結的。
    # 只要 li_latest 帶 `_is_stale` 旗標,不論覆蓋率多完整,一律降到 🟡 並在細項
    # 明講凍結多久(§1 Fail Loud:壞掉要說出來,不能用綠燈蓋過去)。
    _li_stale, _li_age = _li_frozen_info(_li)
    if _li_stale:
        if _e3 == "🟢":
            _e3, _c3 = "🟡", _C_YELLOW
        _age_txt = f"{_li_age:.0f} 分鐘" if isinstance(_li_age, (int, float)) else "未知時長"
        _detail3 += f" ｜ ⚠️ 先行指標資料凍結 {_age_txt} 未更新（沿用舊快取）"
        # 凍結時新鮮度燈號至少黃燈(即使 _date 看起來是近日)
        if _f3e == "🟢":
            _f3e, _f3l = "🟡", "凍結"
    rows.append({
        "tab": "💰 籌碼面",
        "emoji": _e3, "color": _c3,
        "ratio_txt": f"{_cl_have}/{len(_cl_keys)}" if _cl else "未載入",
        "detail": _detail3,
        "action": "缺資料 → TWSE 三大法人 / 融資餘額 API",
        "fresh_emoji": _f3e, "fresh_label": _f3l,
        "fresh_color": _FRESH_COLOR.get(_f3e, _C_IDLE),
    })

    # ── 🏦 ETF:etf_single_data 為單一 ETF dict(present = 已查)──
    _e1d = _get("etf_single_data") or {}
    _etf_loaded = isinstance(_e1d, dict) and bool(_e1d)
    _e4, _c4 = _coverage_emoji(1, 1) if _etf_loaded else ("⬜", _C_IDLE)
    # v19.170:ETF 以 nav_date(有則用)判新鮮度 — v18.442 假折溢價事故即為過時 NAV
    _f4e, _f4l = _freshness_of(
        (_e1d.get("nav_date") or _e1d.get("date")) if isinstance(_e1d, dict) else None)
    rows.append({
        "tab": "🏦 ETF",
        "emoji": _e4, "color": _c4,
        "ratio_txt": "已查" if _etf_loaded else "未查",
        "detail": ("ETF 資料已載入" if _etf_loaded
                   else "在 🏦 ETF Tab 查 ETF 代號觸發"),
        "action": "缺資料 → etf_fetch fallback chain",
        "fresh_emoji": _f4e, "fresh_label": _f4l,
        "fresh_color": _FRESH_COLOR.get(_f4e, _C_IDLE),
    })

    return rows


def render_data_coverage() -> None:
    """渲染前 N Tab 資料覆蓋率表(Fund 風格 Section ⓪)。"""
    st.markdown("### ⓪ 📊 各 Tab 資料覆蓋率檢查表")
    st.caption("快速確認各資料 Tab 的關鍵資料是否都已抓到 — 紅燈 = 缺資料,該 Tab 可能渲染不完整。"
               "對照 CLAUDE.md §2.1 SSOT 來源分級。"
               "v19.170:新增「新鮮度」欄 —— **覆蓋率 ≠ 新鮮度**,有值不代表值是活的。")

    rows = compute_tab_coverage()

    # v19.170:多一欄「新鮮度」,總寬不變(細項/排查各讓出一點)
    _grid = "grid-template-columns:1.0fr 0.5fr 0.8fr 0.9fr 2.4fr 1.8fr"
    _th = ("font-size:10px;color:#888;font-weight:700;padding:8px 10px;"
           "border-bottom:1px solid #30363d")
    _td = "font-size:11px;padding:8px 10px;line-height:1.4"
    _html = (
        f"<div style='display:grid;{_grid};"
        f"background:#0d1117;border-radius:6px 6px 0 0'>"
        f"<span style='{_th}'>Tab</span>"
        f"<span style='{_th};text-align:center'>狀態</span>"
        f"<span style='{_th}'>覆蓋</span>"
        f"<span style='{_th}'>新鮮度</span>"
        f"<span style='{_th}'>細項</span>"
        f"<span style='{_th}'>缺資料時排查</span>"
        f"</div>"
    )
    for r in rows:
        _bg = ("#0a1a0a" if r["emoji"] == "🟢" else
               ("#1a1200" if r["emoji"] == "🟡" else
                ("#1a0606" if r["emoji"] == "🔴" else "#0d1117")))
        _fe = r.get("fresh_emoji", "⬜")
        _fl = r.get("fresh_label", "未知")
        _fc = r.get("fresh_color", _C_IDLE)
        _html += (
            f"<div style='display:grid;{_grid};"
            f"background:{_bg};border-bottom:1px solid #21262d'>"
            f"<span style='{_td};color:#e6edf3;font-weight:600'>{r['tab']}</span>"
            f"<span style='{_td};text-align:center;color:{r['color']};font-size:14px'>{r['emoji']}</span>"
            f"<span style='{_td};color:{r['color']};font-weight:600'>{r['ratio_txt']}</span>"
            f"<span style='{_td};color:{_fc};font-weight:600'>{_fe} {_fl}</span>"
            f"<span style='{_td};color:#bbb'>{r['detail']}</span>"
            f"<span style='{_td};color:#888;font-size:10px'>{r['action']}</span>"
            f"</div>"
        )
    st.markdown(
        f"<div style='border:1px solid #30363d;border-radius:6px;overflow:hidden'>"
        f"{_html}</div>", unsafe_allow_html=True,
    )

    _emojis = [r["emoji"] for r in rows]
    _fresh = [r.get("fresh_emoji", "⬜") for r in rows]
    st.caption(
        f"全 {len(rows)} 個資料 Tab｜🟢 完整 {_emojis.count('🟢')}　"
        f"🟡 部分 {_emojis.count('🟡')}　🔴 缺失 {_emojis.count('🔴')}　"
        f"⬜ 未觸發 {_emojis.count('⬜')}　"
        "｜下方 API Key + Proxy 雙跑診斷可定位根因"
    )
    # v19.170:新鮮度單獨一行摘要 — 覆蓋率全綠但新鮮度有黃/紅時,這行是唯一的提醒
    st.caption(
        f"新鮮度｜🟢 當日 {_fresh.count('🟢')}　🟡 落後/凍結 {_fresh.count('🟡')}　"
        f"🔴 過期 {_fresh.count('🔴')}　⬜ 未知 {_fresh.count('⬜')}　"
        "｜🟡/🔴 = 有值但可能是舊資料,別拿來當今日決策依據"
    )
