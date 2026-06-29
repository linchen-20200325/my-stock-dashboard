"""src/ui/tabs/macro/section_summary_bar.py — 📊 總經總結儀表板 + 五桶 bar(P3-D5 v18.390 抽出)。

原 tab_macro.py:299-341 inline。

closure params(explicit pass):
- 無(內部讀 st.session_state via load_section_inputs SSOT)

gate(L299 if _show_market_data):由 caller 包,不在函式內。

§8.2 L5 UI Tab,純 render,session_state 只讀不寫。
"""
from __future__ import annotations

import streamlit as st


def render_five_bucket_summary() -> None:
    """渲染頂部 📊 總經總結儀表板 + 五桶 bar(原 tab_macro line 299-341)。

    內部 catch + log,不向 caller 拋例外(對齊原 try/except 行為)。
    """
    try:
        # C1-A v18.287:走 section_inputs.load_section_inputs SSOT,
        # 後續 C1-B+ 其他 section 也接同個 helper,降低物理重排耦合。
        from src.compute.macro import compute_five_bucket_summary
        from src.services import load_section_inputs
        from src.ui.tabs.macro.helpers import render_five_bucket_bar
        _inp = load_section_inputs(st.session_state)
        _5b = compute_five_bucket_summary(
            macro_info=_inp.macro_info,
            mkt_info=_inp.mkt_info,
            warroom_summary=_inp.warroom_summary,
            m1b_m2_info=_inp.m1b_m2_info,
            bias_info=_inp.bias_info,
            cl_data=_inp.cl_data,
            li_latest=_inp.li_latest,
            jingqi_info=_inp.jingqi_info,
            news_items=_inp.news_items,
        )
        # v18.310:五桶 bar 升級為頂部「總結儀表板」(user 反饋「上方總結 bar 不夠顯眼」)
        st.markdown(
            '<div style="margin:6px 0 4px;padding:10px 16px;'
            'background:linear-gradient(90deg,#1f6feb22,#0d1117);'
            'border:1px solid #1f6feb55;border-radius:10px;">'
            '<span style="font-size:16px;font-weight:900;color:#58a6ff;">'
            '📊 總經總結儀表板</span>'
            '<span style="font-size:12px;color:#8b949e;margin-left:8px;">'
            '五時域一眼判讀：長期 ｜ 中期 ｜ 短線急殺 ｜ 籌碼 ｜ 新聞</span></div>',
            unsafe_allow_html=True)
        render_five_bucket_bar(_5b)
        # v18.310:下方各桶已加「桶群組 banner」分隔(取代純文字目錄),此處保留簡短導航
        # v18.317:🌍 全球風險桶(雷達);v18.321:🔮 拐點 + 💵 現金流向 加群組 banner
        st.caption(
            "📑 下方深度分析依桶順序排列,每桶有醒目分隔 banner:"
            "🔮 拐點 → 💵 現金流向 → 🌳 長期 → 📈 中期 → ⚡ 短線急殺 → "
            "🌍 全球風險 → 🧩 籌碼 → 🧠 AI 綜合決策"
        )
        st.divider()
    except Exception as _e_5b:
        print(f'[tab_macro/五桶] {type(_e_5b).__name__}: {_e_5b}')
