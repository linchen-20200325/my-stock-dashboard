"""src/ui/tabs/macro/handlers.py — tab_macro 4 個 inner def(F-7.1 B-1 抽出)。

無 closure 依賴(全部用 st.session_state + 顯式參數):
- _macro_session_reset:scoped session_state pop
- _on_refresh_click / _on_force_clear_click:streamlit button on_click handler
- _render_traffic_light(placeholder, tl, mkt_info):紅綠燈卡 placeholder 回填
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_RED, TRAFFIC_YELLOW


def _macro_session_reset():
    """pop 總經相關 session_state keys（scoped）。

    v18.329：**只清總經自己的 session_state**，不碰其他 tab 的 @st.cache_data
    快取。正常更新走此路徑＝吃既有 TTL 暖快取，秒級且不拖累個股 / ETF / 健診頁。
    """
    for _k in ('cl_data', 'cl_ts', 'mkt_info', 'jingqi_info', 'li_latest',
               'warroom_summary', '_last_inst', '_last_inst_date',
               '_last_margin', 'futures_net', 'adl_debug_msg'):
        st.session_state.pop(_k, None)
    st.session_state['_is_refreshing'] = True


def _on_refresh_click():
    """正常更新 on_click：只清總經 session_state，吃既有 @st.cache_data TTL 暖快取。

    v18.329：移除原本的全站 `st.cache_data.clear()`（會炸掉個股 / ETF / 健診的
    快取，導致每次更新總經後全站都要冷啟重抓 → 又慢又奇怪）。要零殘留改用下方
    『🆕 強制重抓』。對齊 Fund `clear_tab1_macro_caches` 的 scoped 行為。
    """
    _macro_session_reset()


def _on_force_clear_click():
    """強制重抓 on_click：全清 pkl + st.cache_data + proxy URL cache + 總經 session_state。"""
    try:
        from src.services import _pkl_clear_all
        _pkl_clear_all()
    except Exception as _e_clr:
        print(f'[Cache] pkl clear failed: {_e_clr}')
    try:
        st.cache_data.clear()
        print('[Cache] 🗑️ st.cache_data cleared (force)')
    except Exception as _e_sc:
        print(f'[Cache] st.cache_data clear failed: {_e_sc}')
    try:
        from src.data.proxy import proxy_helper as _ph_clr
        _ph_clr._URL_CACHE.clear()
        _ph_clr.reset_proxy_cache()
        print('[Cache] 🗑️ proxy URL cache + config cache cleared (force)')
    except Exception as _e_ph:
        print(f'[Cache] proxy clear failed: {_e_ph}')
    _macro_session_reset()
    print('[Cache] 🗑️ 強制重抓：全快取清除完成')


def _render_traffic_light(placeholder, tl, mkt_info=None):
    """將計算結果回填到 placeholder（或顯示等待狀態）。
    mkt_info: 選填，來自 market_regime() 的原始 dict，用以合併顯示市場評分與信號。
    以較保守信號為主（traffic light 已含 defense/health 降級邏輯）。

    信心門檻：conf < 70% 時不顯示燈號，改列出缺失資料避免誤導決策。
    """
    if tl is None:
        placeholder.info(
            '⏳ **系統正在深度解析大盤與籌碼數據，請稍候...**\n\n'
            '首次使用請點擊「🚀 一鍵更新全部數據」載入資料。',
            icon='📡'
        )
        return

    # ── 信心門檻 gating：conf<70% 直接擋燈號，逐項列出缺失資料 ──
    if tl.get('conf', 0) < 70:
        _missing = tl.get('missing_sources', []) or []
        _missing_lines = ''.join(
            f'<li style="margin:4px 0;color:{TRAFFIC_RED};">❌ {m}</li>' for m in _missing
        ) if _missing else '<li style="color:#8b949e;">（無法判斷）</li>'
        with placeholder.container():
            st.markdown(
                f'<div style="background:linear-gradient(135deg,#2a1d00,#1a1208);'
                f'border:2px solid {TRAFFIC_YELLOW};border-radius:14px;padding:18px 22px;margin-bottom:12px;">'
                f'<div style="font-size:22px;font-weight:900;color:{TRAFFIC_YELLOW};">⏸️ 資料不足，無法判斷市場狀態</div>'
                f'<div style="font-size:13px;color:#c9d1d9;margin-top:8px;">'
                f'目前數據信心 <b style="color:{TRAFFIC_RED};">{tl["conf"]}%</b>'
                f'（門檻 70%，避免新舊資料混雜誤導決策）</div>'
                f'<div style="font-size:12px;color:#8b949e;margin-top:10px;">缺少以下資料來源：</div>'
                f'<ul style="font-size:13px;margin:6px 0 0 4px;padding-left:20px;">{_missing_lines}</ul>'
                f'<div style="font-size:12px;color:#58a6ff;margin-top:12px;">'
                f'👉 請點上方「🚀 一鍵更新全部數據」載入完整資料後，燈號才會顯示。'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        return

    # ── P1 v19.470:`health` 三態後可能為 None(兩條腿都沒拿到)──────────────
    # 舊碼直接 `{tl["health"]:.0f}` 會 TypeError 炸掉整個總經分頁。
    # §1:算不出來就顯示「--」,**不可**印 0(0 分在這張卡的語意是「極度惡化」)。
    _h_raw  = tl.get('health')
    _h_text = f'{_h_raw:.0f}' if isinstance(_h_raw, (int, float)) else '--'

    # ── 整合 market_regime() 的輔助資訊 ──────────────────────
    _mi      = mkt_info or {}
    _mi_score  = _mi.get('score')
    _mi_mx     = _mi.get('max_score', 4)
    _mi_idx    = _mi.get('index_price', 0)
    # v19.170 P0-1:建議持股一律取自 SSOT(get_allocation),**不再**讀
    # market_strategy 的 `exposure_pct`(neutral→固定 50%)。本卡就印在
    # 🎚️ 建議持股油門正上方,兩者曾系統性打架(50% vs 30–50%)。
    # §1 Fail Loud:總經未評估時 range_text 自回 '--',不回填任何預設值。
    from src.services.allocation_service import get_allocation as _get_alloc_tl
    _mi_exp    = _get_alloc_tl().range_text
    _mi_sigs   = _mi.get('signals', [])
    _mi_upd    = st.session_state.get('cl_ts', '')

    _sigs_html = ''.join(
        f'<span style="background:#21262d;border-radius:5px;padding:2px 7px;'
        f'font-size:11px;color:#c9d1d9;margin-right:4px;">{s}</span>'
        for s in _mi_sigs
    )
    _meta_line = ''
    if _mi_score is not None:
        _meta_line = (
            f'<div style="display:flex;flex-wrap:wrap;gap:14px;margin-top:8px;">'
            f'<span style="font-size:12px;color:#8b949e;">評分 '
            f'<b style="color:{tl["color"]};">{_mi_score}/{_mi_mx}</b></span>'
            f'<span style="font-size:12px;color:#8b949e;">加權指數 '
            f'<b style="color:#e6edf3;">{_mi_idx:,.0f}</b></span>'
            f'<span style="font-size:12px;color:#8b949e;">建議持股 '
            f'<b style="color:{tl["color"]};">{_mi_exp}</b></span>'
            + (f'<span style="font-size:11px;color:#484f58;">更新 {_mi_upd}</span>'
               if _mi_upd else '')
            + '</div>'
        )

    with placeholder.container():
        # ── 合併看板主體 ────────────────────────────────────
        st.markdown(f'''<div style="background:linear-gradient(135deg,#0a1628,#0d1f3c);
border:3px solid {tl["color"]};border-radius:16px;padding:20px 24px;margin-bottom:12px;">
<div style="display:flex;align-items:flex-start;gap:16px;">
  <div style="font-size:56px;line-height:1;flex-shrink:0;">{tl["icon"]}</div>
  <div style="flex:1;min-width:0;">
<div style="font-size:24px;font-weight:900;color:{tl["color"]};">{tl["label"]}</div>
<div style="font-size:15px;color:#c9d1d9;margin-top:4px;">{tl["action"]}</div>
<div style="font-size:12px;color:#8b949e;margin-top:2px;">{tl["sub"]}</div>
{f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:8px;">{_sigs_html}</div>' if _sigs_html else ''}
{_meta_line}
  </div>
  <div style="text-align:right;flex-shrink:0;">
<div style="font-size:12px;color:#484f58;">綜合健康度</div>
<div style="font-size:36px;font-weight:900;color:{tl["color"]};">{_h_text}</div>
<div style="font-size:11px;color:#484f58;">/ 100分｜信心{tl["conf"]}%</div>
<div style="font-size:10px;color:#6e7681;margin-top:3px;max-width:170px;line-height:1.3;">📊 台股籌碼 / 技術面<br>（全球美股面看下方各桶）</div>
  </div>
</div></div>''', unsafe_allow_html=True)

        # v18.449:澄清本卡片與下方五桶儀表板的關係 —— 兩者本來就評估不同範疇/時間尺度,
        # 這裡是「短期戰術結論」(MA120 趨勢為主軸,判斷現在該不該積極進場),下方五桶是
        # 「多時域風險分層檢查」(任一項亮紅即整桶轉紅,寧可過度敏感也不放過警訊)。
        # 兩者不同步是正常現象,不是計算矛盾(user 曾誤以為「五桶全紅但這裡顯示多頭」是
        # bug,查證後屬設計上刻意分工,見 STATE.md v18.449)。
        st.caption(
            '💡 本結論為**短期戰術訊號**(大盤趨勢 + 籌碼,判斷現在該不該積極進場)；'
            '下方「五桶儀表板」是**多時域風險分層檢查**(任一項亮紅即整桶轉紅,較敏感)。'
            '兩者評估範疇不同,同時出現「這裡多頭、下方亮紅」並非矛盾。'
        )

        # ── 數據信心提示 ────────────────────────────────────
        # ⚠️ v19.177 P1-B:原本是 `if tl['conf'] < 80:` 只印一句籠統警告。
        # 兩個破口:
        #   ① 5 個來源缺 1 個時 conf 正好 = 80 ⇒ `80 < 80` 為 False
        #      ⇒ **畫面什麼都不顯示**。而上方 conf<70 的「列出缺項」分支也進不去
        #      (80 ≥ 70)⇒ 缺 1 項時使用者完全看不到自己少了哪份資料。
        #   ② 就算印了,也沒說「缺的是哪一項」。
        # 依 §1(降級必須顯式 + 帶旗標且可見):只要有任何一項缺失就逐項列出來。
        # conf<70 完全擋燈的邏輯維持在本函式上方不動(那是更嚴重的等級)。
        _missing_now = tl.get('missing_sources') or []
        if _missing_now:
            _msg = (f'⚠️ 數據信心 {tl["conf"]}%：缺少 {len(_missing_now)} 項資料來源 — '
                    + '、'.join(_missing_now) + '。')
            # 健康評分少了旌旗(廣度)那條腿時要特別講 —— 它佔權重 60%,
            # 缺了之後分數只由大盤評分推算,量級意義與平常不同(§1 不可靜默降級)。
            # P1 v19.470:原文寫死「未含旌旗指數」—— health_partial 現在也可能是
            # **大盤評分**那條腿缺席(v19.470 前它被 `get('score', 0)` 捏成 0 分,
            # 所以永遠不會「缺席」,只會靜默變成最強利空)。改為據實列出缺哪條腿。
            if tl.get('health_partial'):
                _legs = []
                if tl.get('jqavg') is None:
                    _legs.append('旌旗指數（廣度，權重 60%）')
                if tl.get('score') is None:
                    _legs.append('大盤趨勢評分（權重 40%）')
                _leg_txt = '、'.join(_legs) if _legs else '部分分項'
                _msg += (f'　🩺 **綜合健康度未含 {_leg_txt}**，本次僅由其餘分項'
                         '推算（權重已重新歸一化，非補中性值/非補 0），'
                         '請降低對該分數的信賴。')
            _msg += '　建議按「🚀 一鍵更新全部數據」後再操作。'
            st.warning(_msg)


