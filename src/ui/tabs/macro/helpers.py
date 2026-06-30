"""src/ui/tabs/macro/helpers.py — tab_macro 頂部 helper(F-7.1a 抽出)。

8 個函式:
- _radar_threshold_lines / _make_radar_sparkline / _render_macro_indicator_card
  — 通用總經指標卡(SPEC threshold 線 + mini sparkline)
- _render_global_risk_bucket / _render_china_drag_panel
  — 風險桶 / 中國拖累面板
- render_five_bucket_bar / render_macro_bucket_summary_bar
  — 五桶 bar / 桶摘要(public,test_render_smoke 走 lazy __getattr__ 從 src.ui.tabs)
- add_danger_hlines — 危險區水平線繪製
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_NEUTRAL



# ════════════════════════════════════════════════════════════════
# v18.317 — 總經指標 sparkline 小卡（鏡像 fund tab1_macro v19.187）
# 短線雷達 / 全球風險桶共用：燈號 + 值 + 白話 + mini sparkline + SPEC 線。
# SPEC 線 cut-off import 自 risk_radar SSOT 常數 → 卡片燈色與 SPEC 線同源
# （§3.3 反捏造：禁止 inline magic；threshold 與 _signal_* 判讀同一組常數）。
# ════════════════════════════════════════════════════════════════
def _radar_threshold_lines(key: str) -> list:
    """回傳該 radar 信號 sparkline 的 SPEC threshold 線 [(y, dash, color, txt), ...]。

    僅「trend 所繪量 == 判讀量」的 4 燈有 natural level 線（VIX 級距 / VIX 期限 /
    MOVE / Put-Call）；其餘 delta/結構型燈（10Y/SOX/sector/SPX/亞夜/HY-delta）
    trend 與判讀非同量，回 [] 不畫線（避免誤導）。cut-off 全 import 自 risk_radar SSOT。
    """
    try:
        from src.compute.risk import (
            VIX_WARN_LEVEL, VIX_PANIC_LEVEL,
            VIX_TERM_WARN, VIX_TERM_PANIC,
            MOVE_WARN_LEVEL, MOVE_PANIC_LEVEL,
        )
    except Exception:
        return []
    if key == 'vix_level':
        return [(VIX_WARN_LEVEL, 'dot', '#d29922', f'警戒 {VIX_WARN_LEVEL:.0f}'),
                (VIX_PANIC_LEVEL, 'dash', '#f85149', f'恐慌 {VIX_PANIC_LEVEL:.0f}')]
    if key == 'vix_term_struct':
        return [(VIX_TERM_WARN, 'dot', '#d29922', f'倒掛 {VIX_TERM_WARN:.2f}'),
                (VIX_TERM_PANIC, 'dash', '#f85149', f'極端 {VIX_TERM_PANIC:.2f}')]
    if key == 'move_level':
        return [(MOVE_WARN_LEVEL, 'dot', '#d29922', f'警戒 {MOVE_WARN_LEVEL:.0f}'),
                (MOVE_PANIC_LEVEL, 'dash', '#f85149', f'恐慌 {MOVE_PANIC_LEVEL:.0f}')]
    # v18.320 put_call_ratio 燈下線（四源全死），其 SPEC 線一併移除
    return []


def _make_radar_sparkline(trend: list, key: str, color: str):
    """產生 radar 卡用的迷你 sparkline + SPEC threshold 線。trend < 2 筆 → None。"""
    if not trend or len(trend) < 2:
        return None
    try:
        import plotly.graph_objects as _go_r
        _fig = _go_r.Figure()
        _fig.add_trace(_go_r.Scatter(
            y=trend, mode='lines+markers',
            line=dict(color=color, width=2),
            marker=dict(size=4, color=color),
            showlegend=False,
            hovertemplate='%{y:.2f}<extra></extra>',
        ))
        for _y, _dash, _lcolor, _txt in _radar_threshold_lines(key):
            _fig.add_hline(
                y=_y, line_dash=_dash, line_color=_lcolor, line_width=1.2,
                opacity=0.65, annotation_text=_txt,
                annotation_position='top right',
                annotation_font=dict(size=8, color=_lcolor),
            )
        _fig.update_layout(
            height=70, margin=dict(l=2, r=2, t=2, b=2),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(visible=False, fixedrange=True),
            yaxis=dict(visible=False, fixedrange=True),
            showlegend=False,
        )
        return _fig
    except Exception:
        return None


def _render_macro_indicator_card(title: str, signal: str, color: str,
                                 value_str: str, note: str, label: str,
                                 trend, spark_key: str) -> None:
    """通用總經指標卡（燈號 + 值 + 白話 + mini sparkline + SPEC 線）。
    **須在 `with st.columns(...)[i]:` 容器內呼叫**。spark_key 決定 SPEC 線（無則純線）。
    """
    st.markdown(
        f"<div style='background:#0d1117;border:2px solid {color};"
        f"border-radius:10px;padding:10px 12px 6px;margin:4px 0;min-height:150px;"
        f"display:flex;flex-direction:column;justify-content:space-between'>"
        f"<div>"
        f"<div style='color:#888;font-size:10px;letter-spacing:1px'>{title}</div>"
        f"<div style='color:{color};font-size:15px;font-weight:800;margin:4px 0 6px'>{signal}</div>"
        f"<div style='color:#fff;font-weight:700;font-size:14px'>值 {value_str}</div>"
        f"</div>"
        f"<div style='color:#aaa;font-size:9px;border-top:1px solid #30363d;"
        f"padding-top:4px;margin-top:4px;line-height:1.3'>{note}"
        f"<br/><span style='color:#555'>{label}</span></div>"
        f"</div>", unsafe_allow_html=True)
    _sp = _make_radar_sparkline(trend, spark_key, color)
    if _sp is not None:
        st.plotly_chart(_sp, use_container_width=True,
                        key=f"mcard_sp_{spark_key}",
                        config={"displayModeBar": False})


# ════════════════════════════════════════════════════════════════
# v18.172 全球風險雷達（10 燈短線急殺訊號）— 鏡像 fund v19.20
# v18.317：原頂部「10 燈格子」改為比照基金的 🌍 全球風險「桶」(群組 banner +
# 整體狀態 bar + sparkline 小卡 + Raw 細節收合 + 雙速合議)，並從總覽頂部下移
# 至「短線急殺」桶之後(全球視角接續本土短線)。資料源仍為 risk_radar。
# AppTest 保護門：fred_api_key < 30 字元 → 完全跳過（避開 4×~15s 序列 HTTP）
# ════════════════════════════════════════════════════════════════
def _render_global_risk_bucket(fred_api_key: str = "",
                               slow_verdict: dict | None = None) -> None:
    """渲染 🌍 全球風險桶：10 燈短線雷達（VIX / VIX/3M / HY OAS / 10Y / MOVE /
    SPX DMA / SOX / Sector / P/C / Asia 夜盤）改桶卡片樣式。

    v18.173：若 slow_verdict 提供（dict with level/score/color/icon/action），
    於卡片之下渲染「🤝 雙速合議」banner — 慢總經 verdict × 短線雷達 level
    → 單一行動建議（adopt_slow / downgrade_1 / downgrade_2 / override_defense）。"""
    # AppTest 保護門：測試環境 key 通常 <30 字元 → 直接跳過避開 HTTP 撞 timeout
    if not fred_api_key or len(str(fred_api_key).strip()) < 30:
        return
    try:
        from src.compute.risk import detect_risk_radar, summarize_radar
    except Exception as _e_imp:
        st.warning(f'⚠️ 風險雷達模組載入失敗：{_e_imp}')
        return
    try:
        _radar = detect_risk_radar(fred_api_key)
        _rs = summarize_radar(_radar)
    except Exception as _e_rd:
        st.warning(f'⚠️ 風險雷達抓取失敗：{type(_e_rd).__name__}: {_e_rd}')
        return

    # ── 🌍 全球風險桶群組 banner（與其他桶一致的分隔條）──
    from shared.macro_buckets import bucket_group_banner_html as _bgb_g
    st.markdown(_bgb_g('global', 0), unsafe_allow_html=True)

    # ── 整體狀態 bar（沿用 summarize_radar 的 10 燈計數）──
    _banner_txt = (
        f'🔴 {_rs["red"]}　🟡 {_rs["yellow"]}　🟢 {_rs["green"]}　⬜ {_rs["gray"]}'
    )
    st.markdown(
        f'<div style="background:#0d1117;border:2px solid {_rs["color"]};'
        f'border-radius:8px;padding:10px 14px;margin:4px 0 10px 0;">'
        f'<div style="color:#8b949e;font-size:12px;margin-bottom:4px;">'
        f'⚡ 短線雷達整體狀態（10 燈）｜1～5 日動量/情緒/位階，與本土短線急殺互補</div>'
        f'<div style="color:{_rs["color"]};font-size:20px;font-weight:700;">'
        f'{_rs["level"]}</div>'
        f'<div style="color:#c9d1d9;font-size:13px;margin-top:6px;">{_banner_txt}'
        f'　<span style="color:#8b949e;">紅 ≥4 極端警報 / ≥2 警報 / 紅+黃 ≥4 警戒</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── sparkline 小卡（10 燈，3/row）──
    _light_labels = {
        'vix_level':       'VIX 級距',
        'vix_term_struct': 'VIX/3M',
        'hy_oas_delta':    'HY OAS Δ',
        'yield_10y_shock': '10Y 衝擊',
        'move_level':      'MOVE 級距',
        'spx_trend_break': 'SPX 均線',
        'sox_drop':        'SOX 日跌',
        'sector_rotation': '防禦/攻擊',
        'asia_overnight':  '亞洲夜盤',
    }
    _keys = list(_light_labels.keys())
    for _row_start in range(0, len(_keys), 3):
        _cols = st.columns(3)
        for _i, _k in enumerate(_keys[_row_start:_row_start + 3]):
            _lt = _radar.get(_k) or {}
            _sig = _lt.get('signal', '⬜ 無資料')
            _color = _lt.get('color', '#888')
            _val = _lt.get('value')
            _val_txt = f'{_val}' if _val is not None else '—'
            _note = _lt.get('note', '—')
            _src = _lt.get('label', '—')
            _trend = _lt.get('trend') or []
            with _cols[_i]:
                _render_macro_indicator_card(
                    title=_light_labels[_k], signal=_sig, color=_color,
                    value_str=_val_txt, note=_note, label=_src,
                    trend=_trend, spark_key=_k)

    with st.expander('🌍 10 燈細節 — 每燈觸發解釋 + 資料源', expanded=False):
        for _k, _label in _light_labels.items():
            _lt = _radar.get(_k) or {}
            _src = _lt.get('label', '—')
            _note = _lt.get('note', '—')
            _sig = _lt.get('signal', '⬜')
            # S-RECON-1 phase 2 v18.255 — 殖利率燈附「FRED vs Yahoo」對帳 chip
            _rec_chip = ''
            _rec = _lt.get('reconcile') if isinstance(_lt, dict) else None
            if isinstance(_rec, dict) and _rec.get('status') in ('agree', 'disagree', 'a_missing', 'b_missing'):
                _rec_status = _rec.get('status', '')
                _rec_emoji = {'agree': '✅', 'disagree': '⚠️',
                              'a_missing': '⬜', 'b_missing': '⬜'}.get(_rec_status, '⬜')
                _rec_color = {'agree': '#22c55e', 'disagree': '#ef4444'}.get(_rec_status, '#888888')
                _va, _vb = _rec.get('value_a'), _rec.get('value_b')
                _va_t = f'{_va:.3f}' if isinstance(_va, (int, float)) else '—'
                _vb_t = f'{_vb:.3f}' if isinstance(_vb, (int, float)) else '—'
                _rec_chip = (
                    f'  \n<span style="color:{_rec_color};font-size:11px;">'
                    f'{_rec_emoji} 對帳：{_rec.get("source_a","")}={_va_t} '
                    f'vs {_rec.get("source_b","")}={_vb_t}（{_rec_status}）</span>'
                )
            st.markdown(
                f'**{_label}**：{_sig}  \n'
                f'<span style="color:#8b949e;font-size:12px;">{_note}</span>  \n'
                f'<span style="color:{TRAFFIC_NEUTRAL};font-size:11px;">資料源：{_src}</span>'
                f'{_rec_chip}',
                unsafe_allow_html=True,
            )
        st.caption('💡 雷達為「短線急殺領先指標」（1～5 日視角），與上方長/短期總經（季級）互補。'
                   '4+ 紅燈 = 急殺進行中；2 紅燈 = 警報需降槓桿；紅+黃 ≥4 = 警戒觀察。')

    # ── v18.173 🤝 雙速合議（慢總經 × 短線雷達 → 單一行動建議）──────────
    if slow_verdict and isinstance(slow_verdict, dict):
        try:
            from src.compute.risk import synthesize_dual_verdict
            _syn = synthesize_dual_verdict(
                slow_level=str(slow_verdict.get('level') or '中性'),
                slow_score=float(slow_verdict.get('score') or 0.0),
                slow_color=str(slow_verdict.get('color') or '#888'),
                slow_icon=str(slow_verdict.get('icon') or '⚪'),
                slow_action=str(slow_verdict.get('action') or '—'),
                radar_level=_rs.get('level'),
            )
            st.markdown(
                f'<div style="background:#0d1117;border:2px solid {_syn["color"]};'
                f'border-radius:8px;padding:12px 14px;margin:10px 0 4px 0;">'
                f'<div style="color:#8b949e;font-size:12px;margin-bottom:4px;">'
                f'🤝 雙速合議（長期總經 × 短線雷達）｜模式 {_syn["mode"]}</div>'
                f'<div style="color:{_syn["color"]};font-size:20px;font-weight:700;">'
                f'{_syn["icon"]} {_syn["level"]}</div>'
                f'<div style="color:#c9d1d9;font-size:13px;margin-top:8px;line-height:1.6;">'
                f'{_syn["action"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.caption('💡 規則：雷達極端警報 → 強制減倉（覆蓋慢總經）；雷達警報 + 慢樂觀 → 降槓桿（分歧）；'
                       '雷達警戒 → 維持持倉但暫緩加碼；雷達平靜 → 採用慢總經結論。')
        except Exception as _e_syn:
            print(f'[risk_radar/dual_verdict] {type(_e_syn).__name__}: {_e_syn}')


def _render_china_drag_panel(fred_api_key: str = "",
                             main_health: float | None = None) -> None:
    """v18.276 中國拖累唯讀面板 — 4 個數字 + regime + USDCNY FX 警示。

    顯示 China 副盤對主分的乘法 modifier 結果,但**不改變**任何既有 UI 數字:
    panel 只 READ main_health(tl['health'] from calc_traffic_light, 0-100 scale),
    COMPUTE multiplier + composite,RENDER NEW markdown。
    既有的 traffic-light 主分卡(tab_macro.py:299)+ 今日市場總覽 4 KPI 完全不動。

    顯示(對稱 Fund v19.118,Stock 主分原生 0-100 無需 scale):
      - 主分(綜合健康度): main_health / 100
      - 中國副盤:         china_subscore / 100(0=最差,100=最好)
      - 乘子:             multiplier ∈ [0.7, 1.0]
      - 折扣後:           main × multiplier / 100
      - 4 級 regime + USDCNY > 7.4 fx_alert(若有)

    §1 fail loud:
      - fred_api_key 缺/AppTest → caption '⬜ 未設,跳過'(無 HTTP 撞 timeout)
      - main_health 缺(健康燈未算)→ caption '⬜ 等待主分'
      - 5 條 FRED series 全敗 → caption '⬜ 中國資料不足'
      - 任何例外 → caption error,caller try/except 包覆,不擋整個 tab

    §8.2 分層:lazy import L2 macro_helpers.get_china_snapshot(本檔 v18.276 加),
              無 L1 直呼,無需擴充 EX-PASSTHRU-1 例外清單。
    """
    # AppTest / 缺 key 守衛(對齊 _render_global_risk_radar L51)
    if not fred_api_key or len(str(fred_api_key).strip()) < 30:
        st.caption("🇨🇳 中國拖累 China Drag:⬜ 未設 FRED key,跳過")
        return
    if main_health is None:
        st.caption("🇨🇳 中國拖累 China Drag:⬜ 等待主分(健康燈未算)")
        return

    try:
        from src.compute.macro import (  # noqa: PLC0415
            apply_china_modifier,
            classify_china_regime,
            compute_china_subscore,
            get_china_snapshot,
        )
        _snap = get_china_snapshot(fred_api_key)
        if not _snap:
            st.caption("🇨🇳 中國拖累 China Drag:⬜ 中國資料不足(5 條 series 全敗)")
            return

        _china_sub = compute_china_subscore(_snap)
        _china_score = _china_sub.get("score") if _china_sub else None
        _regime = classify_china_regime(_china_sub) if _china_sub else None
        _regime_label = _regime.get("regime") if _regime else "—"
        _regime_color = _regime.get("color") if _regime else "#888"
        _fx_alert = _regime.get("fx_alert") if _regime else None

        _mod = apply_china_modifier(main_health, _china_score)
        if _mod is None:
            st.caption("🇨🇳 中國拖累 China Drag:⬜ 計算失敗")
            return
        _multiplier = _mod["multiplier"]
        _composite = _mod["composite"]
    except Exception as _e:  # noqa: BLE001
        st.caption(f"🇨🇳 中國拖累 China Drag:⚠️ 取數失敗 {type(_e).__name__}: {_e}")
        return

    # ── 渲染:標題列 + 4-column 唯讀卡 ─────────────────────────────
    st.markdown(
        f'<div style="border-left:4px solid {_regime_color};padding:8px 12px;'
        f'background:#0d1117;margin:8px 0;border-radius:4px;">'
        f'<b style="color:#e6edf3;">🇨🇳 中國拖累 China Drag</b>  '
        f'<span style="color:{_regime_color};font-weight:bold;">{_regime_label}</span>'
        f'{("  ⚠️ " + _fx_alert) if _fx_alert else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )
    _c1, _c2, _c3, _c4 = st.columns(4)
    with _c1:
        st.metric("主分(綜合健康度)", f"{main_health:.1f} / 100")
    with _c2:
        if _china_score is None:
            st.metric("中國副盤", "—")
        else:
            st.metric("中國副盤", f"{_china_score:.1f} / 100")
    with _c3:
        st.metric("乘子", f"{_multiplier:.3f}",
                  help="0.7~1.0,中國越差扣得越多,只懲罰不加成")
    with _c4:
        st.metric("折扣後主分", f"{_composite:.1f} / 100",
                  delta=f"{_composite - main_health:+.1f}",
                  delta_color="inverse")
    st.caption(
        "ℹ️ 唯讀展示:本面板**不改變**上方主分卡與今日市場總覽,僅示意「若 China 副盤納入主分」的折扣強度。"
        "資料源:5 條 FRED OECD MEI(CLI/PMI/CPI/M2/USDCNY)。"
    )


def render_five_bucket_bar(summary: dict) -> None:
    """v18.284 — 頂部總經五桶總結 bar（5 columns × emoji+燈號+1句）+ 可展開指標明細。

    順序鎖定：🌳長期 → 📈中期 → ⚡短線急殺 → 🧩籌碼 → 📰新聞。
    桶燈號 / headline 由 macro_helpers.compute_five_bucket_summary 算好；本函式只渲染。
    明細區讓 user 一眼看出「哪個指標逼近危險線」（值 + 燈號對照 SPEC §11）。
    """
    from shared.macro_buckets import BUCKET_ORDER, BUCKET_META, LEVEL_EMOJI

    _cols = st.columns(len(BUCKET_ORDER))
    for _col, _key in zip(_cols, BUCKET_ORDER):
        _meta = BUCKET_META[_key]
        _d = summary.get(_key) or {}
        _color = _d.get('color', '#6e7681')
        _emoji = _d.get('emoji', '⬜')
        _label = _d.get('label', '—')
        _headline = _d.get('headline', '')
        with _col:
            st.markdown(
                f'''<div style="border-left:4px solid {_color};padding:8px 12px;
background:rgba(255,255,255,0.03);border-radius:6px;margin-bottom:4px;min-height:104px;">
<div style="font-size:0.72em;color:#888;letter-spacing:0.5px;">{_meta['sub']}</div>
<div style="font-size:1.0em;font-weight:700;margin-top:2px;">{_meta['emoji']} {_meta['title']}: <span style="color:{_color};">{_emoji} {_label}</span></div>
<div style="font-size:0.8em;color:#bbb;margin-top:4px;line-height:1.35;">{_headline}</div>
</div>''',
                unsafe_allow_html=True,
            )

    with st.expander('🔍 五桶指標明細（值 vs 危險線 — 對照 SPEC §11）', expanded=False):
        _dcols = st.columns(len(BUCKET_ORDER))
        for _dcol, _key in zip(_dcols, BUCKET_ORDER):
            _meta = BUCKET_META[_key]
            _d = summary.get(_key) or {}
            with _dcol:
                st.markdown(f"**{_meta['emoji']} {_meta['title']}**")
                for _it in _d.get('details', []):
                    _ic = LEVEL_EMOJI.get(_it['danger'], '⬜')
                    st.markdown(
                        f"<div style='font-size:0.78em;line-height:1.5;'>{_ic} {_it['label']}："
                        f"<b>{_it['value_str']}</b></div>",
                        unsafe_allow_html=True,
                    )


def render_macro_bucket_summary_bar(bucket_key: str, with_cards: bool = False) -> None:
    """v18.314 — 桶輕量總結 bar：整體燈號 + 各指標 chip + SPEC §11 參考。

    user 反饋:每桶(除 §三 籌碼保留原樣)頂部加「整體狀態」簡圖,raw data 收下方。
    復用 compute_five_bucket_summary 該桶 summary(color/emoji/label/details),
    **不新增資料線**。各桶獨立呼叫(自足,不建跨 section 變數依賴 → 利於未來重排)。
    失敗 stderr log 不阻斷主流程(§1:空資料 → bar 顯示「未載入」,不偽造數字)。

    with_cards (v18.338)：True 時於 bar 下方加 Fund 式指標卡片網格(小圖 + 值 +
    燈號 + SPEC)。user 2026-06-28「總經像基金那樣分組 + 小圖 + SPEC」，先套 🌳 長期桶
    當模板；同一次 compute 共用，不重複算。
    """
    try:
        from src.compute.macro import compute_five_bucket_summary
        from src.services import load_section_inputs
        from shared.macro_buckets import (
            bucket_indicator_cards_html, bucket_summary_bar_html,
        )
        _inp = load_section_inputs(st.session_state)
        _5b = compute_five_bucket_summary(
            macro_info=_inp.macro_info, mkt_info=_inp.mkt_info,
            warroom_summary=_inp.warroom_summary, m1b_m2_info=_inp.m1b_m2_info,
            bias_info=_inp.bias_info, cl_data=_inp.cl_data,
            li_latest=_inp.li_latest, jingqi_info=_inp.jingqi_info,
            news_items=_inp.news_items,
        )
        _bsum = _5b.get(bucket_key, {})
        st.markdown(bucket_summary_bar_html(bucket_key, _bsum),
                    unsafe_allow_html=True)
        if with_cards:
            st.markdown(bucket_indicator_cards_html(_bsum), unsafe_allow_html=True)
    except Exception as _e_bsb:
        print(f'[tab_macro/{bucket_key}總結bar] {type(_e_bsb).__name__}: {_e_bsb}')


def add_danger_hlines(fig, key: str, yref=None) -> None:
    """v18.284 — 在 plotly 圖加該指標的黃/紅危險標準線（讀 shared.macro_buckets SSOT）。

    一看就知道現值超過哪條線 = 違規。門檻同頂部五桶 bar、SPEC §11，同源不漂移。
    high_bad/low_bad 各 2 線；band 4 線。yref：多軸圖指定 'y2' 等（預設主軸）。
    """
    from shared.macro_buckets import SPECS_BY_KEY, LEVEL_COLOR
    _spec = SPECS_BY_KEY.get(key)
    if _spec is None:
        return
    _pairs = [(_spec.yellow, LEVEL_COLOR['yellow'], '🟡 黃線'),
              (_spec.red, LEVEL_COLOR['red'], '🔴 紅線')]
    if _spec.direction == 'band':
        _pairs += [(_spec.yellow_lo, LEVEL_COLOR['yellow'], '🟡 黃線'),
                   (_spec.red_lo, LEVEL_COLOR['red'], '🔴 紅線')]
    for _y, _c, _lbl in _pairs:
        if _y is None:
            continue
        _kw = dict(y=_y, line_dash='dash', line_color=_c, opacity=0.6,
                   annotation_text=f'{_lbl} {_y:g}{_spec.unit}',
                   annotation_position='top left',
                   annotation_font=dict(size=9, color=_c))
        if yref:
            _kw['yref'] = yref
        fig.add_hline(**_kw)

