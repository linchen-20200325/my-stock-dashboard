"""v18.205 G2：Sidebar 全局資料健康總覽（鏡像 Fund 端 v19.63 F）。

把散落各 Tab 的資料新鮮度（個股 K線/籌碼/融資/財報六源 + 總經羅盤）聚合到
sidebar，讓 user 一眼看出哪些資料源已過期、該按強制刷新。

讀 st.session_state（sidebar 先於 tab render，故各 key 都可能未填 → 容錯）：
  - t2_data：個股 dict（fetched_at + df.attrs[*_src] + rev/qtr/qtr_extra.attrs）
  - _macro_compass_cache：總經羅盤（_ts 抓取時戳）

注意：t2_data['fetched_at'] 與 _macro_compass_cache['_ts'] 皆為 tz-naive
local datetime，age 用 naive now() 計算（混 tz-aware 會 TypeError）。
"""
from __future__ import annotations

import datetime as _dt

import streamlit as st
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW

# 各資料源「主源」值集合（命中即 🟢；missing→🔴；空/unknown→⬜；其餘→🟠 降級）
# 對齊 tab_stock.py L462-474（B1）+ E2 財報三段的 LABEL dict 慣例。
_SRC_PRIMARY = {
    "price_src": {"yahoo_adj"},
    "inst_src": {"finmind_sdk"},
    "margin_src": {"finmind_sdk"},
    "rev_src": {"finmind"},
    "qtr_src": {"finmind_rest"},
    "qtr_extra_src": {"finmind"},
}


def _src_emoji(src_key: str, val) -> str:
    """單一資料源 src 值 → traffic-light emoji。"""
    _v = str(val or "").strip()
    if not _v or _v == "unknown":
        return "⬜"
    if _v == "missing":
        return "🔴"
    if _v in _SRC_PRIMARY.get(src_key, set()):
        return "🟢"
    return "🟠"


def _fmt_age(delta_sec: float) -> str:
    """秒差 → 人話（Nm前 / Nh前）。"""
    _m = delta_sec / 60.0
    if _m < 60:
        return f"{int(_m)}分前"
    return f"{_m / 60:.1f}h前"


def _age_emoji_min(delta_sec: float) -> str:
    """抓取 age traffic-light：🟢<1h / 🟠<4h / 🔴≥4h（對齊 tab_stock 既有閾值）。"""
    _m = delta_sec / 60.0
    if _m < 60:
        return "🟢"
    if _m < 240:
        return "🟠"
    return "🔴"


def _collect_src_counts(t2d: dict) -> dict:
    """聚合個股六大資料源（price/inst/margin/rev/qtr/qtr_extra）紅綠燈統計。"""
    _counts = {"🟢": 0, "🟠": 0, "🔴": 0, "⬜": 0}
    _df = t2d.get("df")
    _df_attrs = (_df.attrs or {}) if (_df is not None and hasattr(_df, "attrs")) else {}
    for _k in ("price_src", "inst_src", "margin_src"):
        _counts[_src_emoji(_k, _df_attrs.get(_k))] += 1
    for _dkey, _skey in (("rev", "rev_src"), ("qtr", "qtr_src"),
                         ("qtr_extra", "qtr_extra_src")):
        _d = t2d.get(_dkey)
        if _d is None or (hasattr(_d, "empty") and _d.empty):
            _counts["🔴"] += 1
            continue
        _a = (_d.attrs or {}) if hasattr(_d, "attrs") else {}
        _counts[_src_emoji(_skey, _a.get(_skey))] += 1
    return _counts


def _kline_end_date(df) -> str:
    """從個股 df 取 K 線截止日（index 或 date 欄）。"""
    try:
        if df is None or (hasattr(df, "empty") and df.empty):
            return ""
        if hasattr(df, "index") and len(df.index):
            import pandas as _pd
            _d = _pd.to_datetime(df.index[-1])
            if _d is not None and not _pd.isna(_d):
                return _d.strftime("%Y-%m-%d")
        if "date" in getattr(df, "columns", []):
            import pandas as _pd
            return _pd.to_datetime(df["date"].iloc[-1]).strftime("%Y-%m-%d")
    except Exception:
        return ""
    return ""


def render_sidebar_data_health(session_state) -> None:
    """v18.203 F2：渲染 sidebar 全局資料健康 panel（純顯示，零副作用）。"""
    _now = _dt.datetime.now()
    _lines: list = []
    _domain_emojis: list = []

    # ── 個股 t2_data ──
    _t2d = session_state.get("t2_data") or {}
    if isinstance(_t2d, dict) and _t2d.get("sid"):
        _sid = str(_t2d.get("sid", "?"))
        _nm = str(_t2d.get("name", "") or _sid)[:8]
        _fetched = _t2d.get("fetched_at")
        _age_txt = ""
        _emoji = "🟢"
        if _fetched is not None:
            try:
                _sec = (_now - _fetched.to_pydatetime()).total_seconds()
                _emoji = _age_emoji_min(_sec)
                _age_txt = f" · {_fmt_age(_sec)}"
            except Exception:
                _age_txt = ""
        _kend = _kline_end_date(_t2d.get("df"))
        _kend_txt = f" · K線 {_kend}" if _kend else ""
        _domain_emojis.append(_emoji)
        _lines.append(f"{_emoji} 個股 {_nm}{_age_txt}{_kend_txt}")
        # 六大資料源統計
        _c = _collect_src_counts(_t2d)
        _src_head = ("🔴" if _c["🔴"] else ("🟠" if _c["🟠"] else
                     ("🟢" if _c["🟢"] else "⬜")))
        _domain_emojis.append(_src_head)
        _lines.append(
            f"　└ 六源 🟢{_c['🟢']} 🟠{_c['🟠']} 🔴{_c['🔴']} ⬜{_c['⬜']}"
        )

    # ── 總經羅盤 _macro_compass_cache ──
    _mc = session_state.get("_macro_compass_cache") or {}
    if isinstance(_mc, dict) and _mc.get("data"):
        _ts = _mc.get("_ts")
        _emoji = "🟢"
        _age_txt = ""
        if _ts is not None:
            try:
                _sec = (_now - _ts).total_seconds()
                _emoji = _age_emoji_min(_sec)
                _age_txt = f" · {_fmt_age(_sec)}"
            except Exception:
                _age_txt = ""
        _domain_emojis.append(_emoji)
        _lines.append(f"{_emoji} 總經羅盤{_age_txt}")

    # ── headline + render ──
    st.markdown("##### 📊 全局資料健康")
    if not _lines:
        st.caption("⬜ 尚未載入；載入個股 / 總經後這裡顯示總覽")
        return
    _order = {"🔴": 3, "🟠": 2, "🟢": 1, "⬜": 0}
    _headline = max(_domain_emojis, key=lambda e: _order.get(e, 0)) if _domain_emojis else "⬜"
    _border = {"🔴": TRAFFIC_RED, "🟠": TRAFFIC_YELLOW, "🟢": TRAFFIC_GREEN, "⬜": "#444"}.get(_headline, "#444")
    _body = "<br/>".join(_lines)
    st.markdown(
        f"<div style='background:#0d1117;border-left:4px solid {_border};"
        f"border-radius:4px;padding:6px 10px;font-size:11px;color:#8b949e;"
        f"line-height:1.7'>{_body}</div>",
        unsafe_allow_html=True,
    )
    if _headline in ("🔴", "🟠"):
        st.caption("🟠 部分資料偏舊 / 走備援源，可按上方「🔄 強制刷新數據」重抓")
        _render_data_health_ai(_lines)


def _call_gemini_brief(prompt: str) -> str:
    """v18.205 G2：最小 Gemini 呼叫 helper（鏡像 ai_engine.py 多模型嘗試，max_tokens=500）。"""
    try:
        import os
        import requests as _rq
        _key = ""
        try:
            _key = st.secrets.get("GEMINI_API_KEY", "") or ""
        except Exception:
            pass
        if not _key:
            _key = os.environ.get("GEMINI_API_KEY", "")
        if not _key:
            return "⚠️ 未設定 GEMINI_API_KEY"
        _models = [
            "gemini-2.5-flash", "gemini-2.0-flash-exp",
            "gemini-1.5-flash-latest", "gemini-1.5-flash",
        ]
        for _m in _models:
            try:
                _r = _rq.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{_m}:generateContent",
                    params={"key": _key},
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"temperature": 0.3, "maxOutputTokens": 500}},
                    timeout=30,
                )
                if _r.status_code == 200:
                    return _r.json()["candidates"][0]["content"]["parts"][0]["text"]
                if _r.status_code == 404:
                    continue
            except Exception:
                continue
    except Exception as _e:
        return f"⚠️ AI 解讀失敗：{type(_e).__name__}"
    return "⚠️ AI 服務暫時不可用"


def _render_data_health_ai(lines: list) -> None:
    """v18.205 G2：資料異常 AI 解讀（按需觸發，控制 API 成本）。

    僅在 sidebar 資料健康偏舊（🔴/🟠）時提供按鈕；按下才呼叫 Gemini，
    結果存 session_state 避免重複呼叫。零自動 API 消耗。
    """
    _AI_KEY = "_data_health_ai_resp"
    if st.button("🤖 AI 解讀資料異常", key="btn_data_health_ai",
                 use_container_width=True,
                 help="按需呼叫 Gemini 解釋哪些資料偏舊 / 失敗 + 建議動作"
                      "（消耗 API 額度，點了才打）"):
        _ctx = "；".join(str(x) for x in (lines or []))
        _prompt = (
            "你是股票戰情室的資料健康助理。以下是面板各資料源的新鮮度狀態：\n"
            f"{_ctx}\n\n"
            "請用繁體中文、3-4 句白話，說明：(1) 哪些資料可能偏舊或抓取失敗；"
            "(2) 最可能原因（API 額度用盡 / 網路不通 / FinMind 上游延遲）；"
            "(3) 建議動作。直接講重點，不要客套或重複題目。"
        )
        with st.spinner("🤖 AI 解讀中…"):
            _resp = _call_gemini_brief(_prompt)
        st.session_state[_AI_KEY] = _resp
    _resp = st.session_state.get(_AI_KEY)
    if _resp:
        st.markdown(
            f"<div style='background:#161b22;border:1px solid #30363d;"
            f"border-radius:6px;padding:8px 10px;margin-top:4px;font-size:11px;"
            f"color:#c9d1d9;line-height:1.6'>🤖 {_resp}</div>",
            unsafe_allow_html=True,
        )
