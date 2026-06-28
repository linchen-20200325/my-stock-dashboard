"""v18.207 I5：個股 ↔ 組合/ETF 投組持倉聯動 banner（鏡像 Fund v19.65 I2）。

研究單一個股時讀 session_state（其他 Tab 已寫入），顯示：
  - 已在 ETF 投組：顯示張數 / 權重 / 角色（核心/衛星）
  - 已在組合比較：顯示健康度評級
  - 兩者皆未出現：靜默（不打擾只用單檔的 user）

讀取 key：
  - `etf_portfolio_rows`（list）：{ticker, lots, shares, current_value, actual_pct, role}
  - `t3_data['results']`（list）：{stock_id, 代碼, 名稱, 健康度, 評級}
"""
from __future__ import annotations

import streamlit as st


def _norm(s) -> str:
    return str(s or "").strip().upper()


def _find_in_etf_pf(sid: str, pf_rows) -> dict | None:
    if not pf_rows or not isinstance(pf_rows, list):
        return None
    _sid = _norm(sid)
    for r in pf_rows:
        if isinstance(r, dict) and _norm(r.get("ticker")) == _sid:
            return r
    return None


def _find_in_t3(sid: str, t3) -> dict | None:
    if not isinstance(t3, dict):
        return None
    _results = t3.get("results")
    if not _results or not isinstance(_results, list):
        return None
    _sid = _norm(sid)
    for r in _results:
        if not isinstance(r, dict):
            continue
        if _norm(r.get("stock_id")) == _sid or _norm(r.get("代碼")) == _sid:
            return r
    return None


def render_stock_portfolio_membership(session_state, sid: str, name: str = "") -> None:
    """渲染個股的「跨 Tab 持倉聯動」banner（純讀，零副作用）。

    讀 ETF 投組與組合比較的 session_state，命中時顯示綠框（持倉資訊），
    未命中時顯示淺色提示「尚未加入任何 Tab 分析範圍」；若兩個 Tab 都沒載入則靜默。
    """
    if not sid:
        return
    _etf_rows = session_state.get("etf_portfolio_rows")
    _t3 = session_state.get("t3_data")
    if not _etf_rows and not _t3:
        return  # 兩 Tab 都未載入 → 靜默
    _hit_etf = _find_in_etf_pf(sid, _etf_rows)
    _hit_t3 = _find_in_t3(sid, _t3)

    _parts: list = []
    if _hit_etf:
        _lots = float(_hit_etf.get("lots") or 0)
        _pct = float(_hit_etf.get("actual_pct") or 0)
        _role = str(_hit_etf.get("role") or "—")
        _pnl = float(_hit_etf.get("capital_gain_pct") or 0)
        _role_zh = "🎯 核心" if _role == "core" else ("🛰️ 衛星" if _role == "satellite" else _role)
        _parts.append(
            f"✅ <b>已在 ETF 投組</b> · {_lots:.1f} 張 · 權重 {_pct:.1f}% · "
            f"{_role_zh} · 損益 {_pnl:+.1f}%"
        )
    if _hit_t3:
        _health = _hit_t3.get("健康度")
        _grade = str(_hit_t3.get("評級") or "—")
        _health_txt = f"{float(_health):.0f}" if _health is not None else "—"
        _parts.append(f"📊 <b>已分析於組合比較</b> · 健康度 {_health_txt} · 評級 {_grade}")

    if not _parts:
        _nm = str(name or sid)[:10]
        _scope = []
        if _etf_rows:
            _scope.append("ETF 投組")
        if _t3:
            _scope.append("組合比較")
        _scope_s = " / ".join(_scope) or "其他 Tab"
        st.markdown(
            f"<div style='background:#0d1117;border-left:4px solid #6e7681;"
            f"border-radius:4px;padding:6px 12px;margin:6px 0;font-size:11px;"
            f"color:#8b949e;line-height:1.7'>"
            f"🔗 <b>{_nm}</b> ➕ 尚未出現在你的 {_scope_s}"
            f"</div>",
            unsafe_allow_html=True,
        )
        return

    # v18.210 K4：走 shared/colors SSOT
    from shared.colors import TRAFFIC_GREEN
    _body = "<br/>".join(_parts)
    st.markdown(
        f"<div style='background:#0d1117;border-left:4px solid {TRAFFIC_GREEN};"
        f"border-radius:4px;padding:6px 12px;margin:6px 0;font-size:11px;"
        f"color:#c9d1d9;line-height:1.7'>"
        f"🔗 <b>{str(name or sid)[:14]}</b> 跨 Tab 持倉聯動<br/>{_body}"
        f"</div>",
        unsafe_allow_html=True,
    )
