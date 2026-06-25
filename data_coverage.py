"""data_coverage.py — 前 N Tab 資料覆蓋率檢查表(v18.280)

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

# 色票(對齊 shared/colors 但本檔不 import 避免循環,診斷頁用內聯 hex)
_C_GREEN = "#3fb950"
_C_YELLOW = "#d29922"
_C_RED = "#f85149"
_C_IDLE = "#666"


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
    if r >= 0.85:
        return ("🟢", _C_GREEN)
    if r >= 0.5:
        return ("🟡", _C_YELLOW)
    return ("🔴", _C_RED)


def compute_tab_coverage(state: dict | None = None) -> list[dict]:
    """計算各資料 Tab 覆蓋率。

    state: 測試可注入 dict;None → 讀 st.session_state。
    回傳 list[dict],每筆:
      {tab, emoji, color, ratio_txt, detail, action}
    """
    def _get(key: str):
        if state is not None:
            return state.get(key)
        return _ss(key)

    rows = []

    # ── 🌐 總經:macro_info 6 指標 + M1B-M2 + 領先指標 ──
    # v18.282 修正:用真實 session_state key(原 v18.280 key 名全錯導致永遠紅燈)
    # 實際 macro_info 寫於 tab_macro.py:1862 _job_macro,key 為:
    #   vix / ism_pmi / us_core_cpi / fed_funds / ndc_signal / tw_export
    _ma = _get("macro_info") or {}
    _mi = _get("m1b_m2_info") or {}
    _li = _get("li_latest")
    _macro_keys = ["vix", "ism_pmi", "us_core_cpi", "fed_funds",
                   "ndc_signal", "tw_export"]
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
    rows.append({
        "tab": "🌐 總經",
        "emoji": _e1, "color": _c1,
        "ratio_txt": f"{_macro_have_all}/{_macro_total_all}" if _ma_loaded else "未載入",
        "detail": (f"VIX/ISM/CPI/Fed/NDC/出口 {_macro_have}/{_macro_total} ｜ "
                   f"M1B-M2 {'✓' if _mi else '✗'} ｜ 領先 {'✓' if _li is not None else '✗'}")
                  if _ma_loaded else "在 🌐 總經 Tab 按更新觸發",
        "action": "缺值 → 看下方 API Key / Proxy 診斷",
    })

    # ── 📈 個股:t2_data 為單一個股 metrics dict(present = 已查)──
    _t2 = _get("t2_data") or {}
    _t2_loaded = isinstance(_t2, dict) and bool(_t2)
    _e2, _c2 = _coverage_emoji(1, 1) if _t2_loaded else ("⬜", _C_IDLE)
    rows.append({
        "tab": "📈 個股",
        "emoji": _e2, "color": _c2,
        "ratio_txt": "已查" if _t2_loaded else "未查",
        "detail": (f"個股資料已載入（{len(_t2)} 欄）" if _t2_loaded
                   else "在 📈 個股 Tab 查股票代號觸發"),
        "action": "缺資料 → TWSE / FinMind / Yahoo fallback chain",
    })

    # ── 💰 籌碼:cl_data(法人 inst / 融資 margin / 廣度 adl)──
    # 實際 cl_data 寫於 tab_macro.py:1046,key 為:
    #   intl / tw / tech / inst（三大法人）/ margin（融資）/ adl（騰落）
    _cl = _get("cl_data") or {}
    _cl_keys = [("inst", "法人"), ("margin", "融資"), ("adl", "廣度")]
    _cl_have = sum(1 for k, _ in _cl_keys
                   if isinstance(_cl, dict) and _cl.get(k) is not None)
    _e3, _c3 = _coverage_emoji(_cl_have, len(_cl_keys)) if _cl else ("⬜", _C_IDLE)
    rows.append({
        "tab": "💰 籌碼面",
        "emoji": _e3, "color": _c3,
        "ratio_txt": f"{_cl_have}/{len(_cl_keys)}" if _cl else "未載入",
        "detail": (" ｜ ".join(
            f"{_lbl} {'✓' if (_cl or {}).get(_k) is not None else '✗'}"
            for _k, _lbl in _cl_keys)
            if _cl else "在 🌐 總經 Tab 載入籌碼觸發"),
        "action": "缺資料 → TWSE 三大法人 / 融資餘額 API",
    })

    # ── 🏦 ETF:etf_single_data 為單一 ETF dict(present = 已查)──
    _e1d = _get("etf_single_data") or {}
    _etf_loaded = isinstance(_e1d, dict) and bool(_e1d)
    _e4, _c4 = _coverage_emoji(1, 1) if _etf_loaded else ("⬜", _C_IDLE)
    rows.append({
        "tab": "🏦 ETF",
        "emoji": _e4, "color": _c4,
        "ratio_txt": "已查" if _etf_loaded else "未查",
        "detail": ("ETF 資料已載入" if _etf_loaded
                   else "在 🏦 ETF Tab 查 ETF 代號觸發"),
        "action": "缺資料 → etf_fetch fallback chain",
    })

    return rows


def render_data_coverage() -> None:
    """渲染前 N Tab 資料覆蓋率表(Fund 風格 Section ⓪)。"""
    st.markdown("### ⓪ 📊 各 Tab 資料覆蓋率檢查表")
    st.caption("快速確認各資料 Tab 的關鍵資料是否都已抓到 — 紅燈 = 缺資料,該 Tab 可能渲染不完整。"
               "對照 CLAUDE.md §2.1 SSOT 來源分級。")

    rows = compute_tab_coverage()

    _th = ("font-size:10px;color:#888;font-weight:700;padding:8px 10px;"
           "border-bottom:1px solid #30363d")
    _td = "font-size:11px;padding:8px 10px;line-height:1.4"
    _html = (
        f"<div style='display:grid;grid-template-columns:1.1fr 0.5fr 0.9fr 2.6fr 2fr;"
        f"background:#0d1117;border-radius:6px 6px 0 0'>"
        f"<span style='{_th}'>Tab</span>"
        f"<span style='{_th};text-align:center'>狀態</span>"
        f"<span style='{_th}'>覆蓋</span>"
        f"<span style='{_th}'>細項</span>"
        f"<span style='{_th}'>缺資料時排查</span>"
        f"</div>"
    )
    for r in rows:
        _bg = ("#0a1a0a" if r["emoji"] == "🟢" else
               ("#1a1200" if r["emoji"] == "🟡" else
                ("#1a0606" if r["emoji"] == "🔴" else "#0d1117")))
        _html += (
            f"<div style='display:grid;grid-template-columns:1.1fr 0.5fr 0.9fr 2.6fr 2fr;"
            f"background:{_bg};border-bottom:1px solid #21262d'>"
            f"<span style='{_td};color:#e6edf3;font-weight:600'>{r['tab']}</span>"
            f"<span style='{_td};text-align:center;color:{r['color']};font-size:14px'>{r['emoji']}</span>"
            f"<span style='{_td};color:{r['color']};font-weight:600'>{r['ratio_txt']}</span>"
            f"<span style='{_td};color:#bbb'>{r['detail']}</span>"
            f"<span style='{_td};color:#888;font-size:10px'>{r['action']}</span>"
            f"</div>"
        )
    st.markdown(
        f"<div style='border:1px solid #30363d;border-radius:6px;overflow:hidden'>"
        f"{_html}</div>", unsafe_allow_html=True,
    )

    _emojis = [r["emoji"] for r in rows]
    st.caption(
        f"全 {len(rows)} 個資料 Tab｜🟢 完整 {_emojis.count('🟢')}　"
        f"🟡 部分 {_emojis.count('🟡')}　🔴 缺失 {_emojis.count('🔴')}　"
        f"⬜ 未觸發 {_emojis.count('⬜')}　"
        "｜下方 API Key + Proxy 雙跑診斷可定位根因"
    )
