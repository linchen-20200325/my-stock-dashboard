"""src/ui/render/app_render.py — L4 app 級渲染元件(v18.404 U5 B3-γ).

從 app.py:679-1007 抽出 3 個 render 函式,對齊 APP_PY_AUDIT.md B3-γ phase。

§8.2 layer:L4 Render — Streamlit container-aware UI 元件,純展示無業務邏輯
(I/O 透過 caller 預傳資料或 lazy import L1 fetcher,latter 為 EX-PASSTHRU-1 範疇)。

對外 API:
- `render_health_score(score, details, sid, fund_scores, tech_alerts) -> str`:
  個股健診 v2 HTML(SVG 量表 + 四維 + 警示 + 條形圖)
- `render_macro_compass() -> None`:頂部三卡(VIX × 10Y × S&P 500 vs 60MA)
  含「📡 抓取最新」按鈕觸發 src.data.macro.fetch_macro_compass(lazy)
"""
from __future__ import annotations

import math
import datetime
from typing import Any

import pandas as pd
import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from src.compute.scoring.scoring_helpers import health_grade


def render_health_score(score, details, sid: str = '', fund_scores=None,
                        tech_alerts=None) -> str:
    """個股健診 v2:SVG量表 + 四維評分 + 技術警示 + 因子條形圖。

    回傳 HTML 字串(caller 用 `st.markdown(..., unsafe_allow_html=True)`)。
    """
    grade, color, css_class, emoji = health_grade(score)

    # ① SVG 半圓量表
    angle = (-180 + score * 1.8) * math.pi / 180
    cx, cy, r = 100, 90, 70
    nx = cx + r * math.cos(angle)
    ny = cy + r * math.sin(angle)
    gauge = (
        '<div style="text-align:center;padding:4px 0;">'
        '<svg viewBox="0 0 200 110" style="width:175px;height:92px;">'
        '<path d="M20,90 A80,80 0 0,1 60,22" stroke="#4c1d95" stroke-width="14" fill="none" stroke-linecap="round"/>'
        '<path d="M60,22 A80,80 0 0,1 100,10" stroke="#1e3a5f" stroke-width="14" fill="none" stroke-linecap="round"/>'
        '<path d="M100,10 A80,80 0 0,1 140,22" stroke="#1a4a1a" stroke-width="14" fill="none" stroke-linecap="round"/>'
        '<path d="M140,22 A80,80 0 0,1 180,90" stroke="#3d2000" stroke-width="14" fill="none" stroke-linecap="round"/>'
        f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/>'
        f'<circle cx="{cx}" cy="{cy}" r="5" fill="{color}"/>'
        '<text x="14" y="103" fill="#8b949e" font-size="8">注意</text>'
        '<text x="48" y="18" fill="#8b949e" font-size="8">較差</text>'
        '<text x="88" y="8" fill="#8b949e" font-size="8">普通</text>'
        '<text x="127" y="18" fill="#8b949e" font-size="8">良好</text>'
        f'<text x="100" y="82" text-anchor="middle" fill="{color}" font-size="26" font-weight="900">{score}</text>'
        f'<text x="100" y="97" text-anchor="middle" fill="{color}" font-size="10">{grade}</text>'
        '</svg></div>'
    )

    # ② 四維評分
    fund_html = ''
    if fund_scores:
        _cat_ic = {'profit': '💰', 'growth': '📈', 'dividend': '🎁', 'valuation': '⚖️'}
        _sc_cl = {0: '#8b949e', 1: TRAFFIC_YELLOW, 2: TRAFFIC_GREEN, 3: '#2ea043'}
        fund_html = '<div style="display:flex;gap:4px;margin:10px 0;">'
        for cat in ['profit', 'growth', 'dividend', 'valuation']:
            fs = fund_scores.get(cat, {})
            sc = fs.get('score', 0)
            lb = fs.get('label', cat)
            ic = _cat_ic.get(cat, '')
            cl = _sc_cl.get(min(sc, 3), '#8b949e')
            chk = ''
            for cn, cv, cp in fs.get('checks', [])[:3]:
                cc = TRAFFIC_GREEN if cp else TRAFFIC_RED
                chk += f'<div style="font-size:9px;color:{cc};margin-top:1px;">{"✓" if cp else "✗"} {cn}</div>'
            fund_html += (
                f'<div style="flex:1;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:7px 4px;text-align:center;">'
                f'<div style="font-size:20px;font-weight:900;color:{cl};">{sc}</div>'
                f'<div style="font-size:9px;color:#8b949e;">{ic} {lb}</div>'
                f'{chk}</div>'
            )
        fund_html += '</div>'

    # ③ 技術警示
    tech_html = ''
    if tech_alerts:
        _pc = {'🔴': TRAFFIC_RED, '🟡': TRAFFIC_YELLOW, '🟢': TRAFFIC_GREEN}
        tech_html = '<div style="margin:8px 0;"><div style="font-size:11px;color:#8b949e;margin-bottom:4px;">⚡ 技術警示</div>'
        for pri, name, sig, desc in tech_alerts[:5]:
            bc = _pc.get(pri, '#484f58')
            sc2 = TRAFFIC_RED if any(k in sig for k in ['看跌', '空頭', '超賣']) else (
                TRAFFIC_GREEN if any(k in sig for k in ['看漲', '多頭']) else TRAFFIC_YELLOW
            )
            tech_html += (
                f'<div style="display:flex;align-items:center;gap:6px;margin:3px 0;background:#0d1117;border-left:3px solid {bc};padding:4px 8px;border-radius:0 4px 4px 0;">'
                f'<span style="font-size:10px;">{pri}</span>'
                f'<div style="flex:1;">'
                f'<span style="font-size:11px;font-weight:700;color:#c9d1d9;">{name}</span>'
                f'<span style="font-size:9px;background:{sc2}33;color:{sc2};padding:1px 4px;border-radius:3px;margin-left:5px;">{sig}</span>'
                f'<div style="font-size:9px;color:#8b949e;">{desc}</div>'
                f'</div></div>'
            )
        tech_html += '</div>'

    # ④ 因子條形圖
    breakdown = '<div style="margin-top:8px;">'
    for factor, (desc, got, total) in details.items():
        pct = got / total * 100
        bc = TRAFFIC_GREEN if pct >= 70 else (TRAFFIC_YELLOW if pct >= 40 else TRAFFIC_RED)
        breakdown += (
            f'<div style="display:flex;align-items:center;gap:6px;margin:2px 0;">'
            f'<div style="width:45px;font-size:10px;color:#8b949e;text-align:right;">{factor}</div>'
            f'<div style="flex:1;background:#21262d;border-radius:4px;height:7px;">'
            f'<div style="width:{pct:.0f}%;background:{bc};border-radius:4px;height:7px;"></div></div>'
            f'<div style="width:85px;font-size:9px;color:{bc};">{got}/{total} {desc[:8]}</div>'
            f'</div>'
        )
    breakdown += '</div>'
    return gauge + fund_html + tech_html + breakdown


def _render_compass_card(col, info: dict | None, title: str, ticker: str,
                         fmt: str = '{:.2f}', unit: str = '',
                         show_ma: bool = False) -> None:
    """單張指標卡:值 + Phase 1 訊號燈 + 60D sparkline。info=None 顯示降級訊息。"""
    if info is None:
        col.markdown(
            f'<div style="background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:10px;height:84px;">'
            f'<div style="font-size:11px;color:#8b949e;">{title}（{ticker}）</div>'
            f'<div style="font-size:13px;color:#8b949e;margin-top:6px;">🔴 未取得（yfinance 暫時失敗）</div>'
            f'</div>', unsafe_allow_html=True)
        return
    val = info.get('value')
    sig = info.get('signal') or ('⚪', '無訊號', '#8b949e')
    light, label, color = sig[0], sig[1], sig[2]
    val_str = fmt.format(val) + unit if val is not None else 'N/A'
    extra = ''
    if show_ma and info.get('ma60') is not None:
        extra = f' <span style="font-size:10px;color:#8b949e;font-weight:400;">/ 60MA {fmt.format(info["ma60"])}</span>'
    col.markdown(
        f'<div style="background:#0d1117;border:1px solid {color};border-radius:8px;padding:10px;">'
        f'<div style="font-size:11px;color:#8b949e;">{title}（{ticker}）</div>'
        f'<div style="font-size:22px;font-weight:900;color:#e6edf3;margin:2px 0;">{val_str}{extra}</div>'
        f'<div style="font-size:11px;font-weight:700;color:{color};">{light} {label}</div>'
        f'</div>', unsafe_allow_html=True)
    ser = info.get('series') or []
    if ser:
        try:
            col.line_chart(pd.Series(ser, name=title), height=80, use_container_width=True)
        except Exception:
            pass


def render_macro_compass() -> None:
    """頂部三卡:VIX 恐慌指數 × 美 10Y 殖利率 × S&P 500 vs 60MA。

    預設不抓資料(避免顯示過時值誤判),按「📡 抓取最新」按鈕才打 yfinance。
    """
    def _do_fetch():
        try:
            from src.data.macro import fetch_macro_compass as _fmc
            _data = _fmc()
        except Exception as e:
            print(f'[render_macro_compass] fetch failed: {e}')
            _data = {}
        st.session_state['_macro_compass_cache'] = {
            '_ts': datetime.datetime.now(), 'data': _data,
        }

    _cache = st.session_state.get('_macro_compass_cache')
    _has_data = bool(_cache and _cache.get('data'))
    _ts_str = (_cache.get('_ts').strftime('%H:%M:%S')
               if _has_data and _cache.get('_ts') else '尚未抓取')

    _header = st.columns([6, 1])
    _header[0].markdown(
        '<div style="font-size:14px;font-weight:900;color:#e6edf3;margin:4px 0 4px;">'
        '🧭 總經指南針 (Top-Down Macro)'
        '<span style="font-size:10px;color:#8b949e;font-weight:400;margin-left:8px;">'
        f'VIX × 10Y × S&amp;P 500 — {"即將抓取（無快取）" if not _has_data else f"更新於 {_ts_str}"}'
        '</span></div>',
        unsafe_allow_html=True)
    _header[1].button('📡 抓取最新' if not _has_data else '🔄 重抓',
                      key='_compass_fetch_btn', on_click=_do_fetch,
                      use_container_width=True)

    if not _has_data:
        st.info('💡 點擊右上「📡 抓取最新」按鈕載入即時 VIX / 10Y / S&P 500')
        return

    data = _cache.get('data') or {}
    c1, c2, c3 = st.columns(3)
    _render_compass_card(c1, data.get('vix'),  'VIX 恐慌指數',     '^VIX',  fmt='{:.2f}')
    _render_compass_card(c2, data.get('tnx'),  '美 10Y 殖利率',    '^TNX',  fmt='{:.2f}', unit='%')
    _render_compass_card(c3, data.get('gspc'), 'S&P 500 vs 60MA',  '^GSPC', fmt='{:,.2f}', show_ma=True)
