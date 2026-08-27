"""src/ui/tabs/macro/section_chips.py — Section 3(§三)大戶籌碼全貌 v18.388(B-S8-A 抽出)。

🧩 籌碼｜🧮 大戶籌碼全貌：法人聰明錢 × 融資融券 × 先行指標

closure params(explicit pass,§-1 minimal):
- inst: dict  三大法人 net/buy/sell({外資/陸資, 投信, 自營商: {'net': ...}})
- margin: number | None  融資餘額(億元)
- cd: dict  _job_macro 回傳的合併結果(用來偵測「是否曾嘗試載入」)
"""
from __future__ import annotations

import streamlit as st

from shared.colors import (
    TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW,
)
# H1 §3.3：先行指標表「選PCR」欄的著色帶 + 平價點（百分比刻度 SSOT）。
# 原 caption 手抄「PCR<100偏空」，對不上它所標示的那張表（<80 紅 / >120 綠）。
from shared.pcr_scale import (
    PCR_PCT_COMPLACENCY_MAX,
    PCR_PCT_FEAR_MIN,
    PCR_PCT_PARITY,
)
from shared.signal_thresholds import (
    # F1 v19.184 §3.3：先行指標表 caption 的「外資空單>3萬 / 前五大>1萬」原為手抄。
    FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD,
    MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
    MARGIN_BALANCE_WARN_THRESHOLD_YI,
    MARKET_VOLUME_SHRINK_RATIO,
    MARKET_VOLUME_SURGE_RATIO,
    TOP5_LARGE_TRADER_NET_WARN_LOTS,
)
from src.compute.strategy import V4StrategyEngine
# v19.176 P0-D:韭菜門檻 + 兩個「否決」判定的正式名稱一律走 L0 SSOT(§3.3)
from src.config import (
    LEEK_ALERT_HIGH_PCT,
    LEEK_ALERT_LOW_PCT,
    LEEK_SCORE_HIGH_PCT,
    LEEK_SCORE_LOW_PCT,
    VETO_V4_ENGINE_NAME,
    VETO_V4_ENGINE_SCOPE_NOTE,
)
from src.data.macro import render_leading_table
from src.ui.render.macro_ui_components import section_header
# v19.174 去識別化：改用策略代號常數 + 新函式名 strategy_conclusion（原 teacher_conclusion）
from src.ui.render.ui_widgets import (
    STRATEGY_TECHNICAL,
    STRATEGY_VALUATION,
    strategy_conclusion,
)
from src.ui.tabs.tab_helpers import safe_get


# ══════════════════════════════════════════════════════════════════
# v4 引擎風險燈 — 全站唯一取數 + 判定入口（§2.1 SSOT，v19.176 P0-D）
# ══════════════════════════════════════════════════════════════════
def read_v4_macro_veto() -> dict | None:
    """讀 session 現況 → 回 `V4StrategyEngine.check_macro_veto()` 的判定結果。

    為什麼要抽成模組級函式
    ----------------------
    2026-08-05 實機同一次渲染，同一個名字「v4.0 總經否決權」在同一頁給出
    相反結論（§八 說「無觸發」、§三 說「🔴 紅燈 高風險」）。根因是 §八
    (`section_mid`) 那塊**根本不是 v4 引擎**，而是另一組 inline 規則，兩者
    只是撞名 —— 完整根因記在 `src/config/config.py` 的 `VETO_*` 常數上方。

    正名之後 §八 仍需要知道「籌碼側那盞燈現在是什麼顏色」才有辦法揭露分歧，
    於是把**取數 + 判定**收斂成這一個入口：兩個 section 保證吃同一份輸入，
    不會再各讀各的而長出第二種不一致。

    §1 Fail Loud：VIX 取不到一律回 `None`，**不得**回填 15。

    ⚠️ **2026-08-27（v19.186）狀態更新 —— 本段原文已過期，據實改寫**：
    這裡原本寫「`check_macro_veto()` 內部是 `float(self.macro.get('vix') or 15)`，
    傳 None 進去會被它悄悄換成 15」。**那句話現在不成立了** —— 引擎端的回填
    已經拔掉（`_macro_number()` 取不到一律回 `None`，判定端多出第四態
    「⬜ 無法判定」）。留著不改就會變成在說謊，下一個人會據以判斷。

    **短路照舊保留**，理由換成兩點：
      1. 這一層本來就要決定「VIX 沒有時這張卡印什麼」，短路讓那段文案
         （含「請先按 🚀 一鍵更新全部數據」這個**本頁專屬**的救法）留在 UI 層，
         引擎不必知道有這顆按鈕；
      2. 保持**行為零變更** —— 引擎端修的是「不要捏造數字」，不是「改判燈輸出」。
    ⚠️ 已知取捨（待議，不在本次範圍）：VIX 缺、但外資期貨已達 -20,000 口時，
    引擎其實給得出有根據的 🔴（判定是 OR），而這裡的短路會把它蓋成 ⬜。
    那是**改判燈輸出**，屬另案。

    Returns:
        dict: engine 原始回傳（status/level/color/max_position/msg）
              外加三個輸入 `_vix` / `_futures` / `_pcr`（供 UI 揭露依據）；
        None: VIX 未取得 → 無法判定。
    """
    _mi = st.session_state.get('macro_info') or {}
    _vix_node = _mi.get('vix')
    _vix_raw = _vix_node.get('current') if isinstance(_vix_node, dict) else None
    try:
        _vix = float(_vix_raw)
    except (TypeError, ValueError):
        return None
    if _vix != _vix:          # NaN → 視為未取得
        return None

    # 先行指標取「與畫面主表格同一份 ffill 後」的末筆：若 §三 吃 ffill 值、
    # §八 吃原始 NaN，兩邊輸入不同 → 又會生出一次「同名不同結論」。
    _fut = 0.0
    _pcr = 100.0
    _li = st.session_state.get('li_latest')
    if _li is not None and not getattr(_li, 'empty', True):
        try:
            _num_cols = [c for c in _li.columns if c != '日期']
            _row = _li[_num_cols].ffill().iloc[-1]
            _fut = float(_row.get('外資大小') or 0)
            _pcr = float(_row.get('選PCR') or 100)
        except Exception as _e_li:
            # §1：不靜默 —— 讀不到先行指標會讓這盞燈退化成「只看 VIX」。
            print(f'[section_chips/read_v4_macro_veto] 先行指標讀取失敗，'
                  f'外資期貨以 0 口計：{type(_e_li).__name__}: {_e_li}')

    _eng = V4StrategyEngine.__new__(V4StrategyEngine)
    _eng.macro = {'vix': _vix, 'foreign_futures': _fut, 'pcr': _pcr}
    _veto = dict(_eng.check_macro_veto())
    _veto['_vix'] = _vix
    _veto['_futures'] = _fut
    _veto['_pcr'] = _pcr
    return _veto


def render_section_chips(inst: dict, margin, cd: dict) -> None:
    """渲染§三 籌碼桶(原 tab_macro line 2229-2788)。"""
    import os
    import pandas as pd

    # ════════════════════════════════════════════════════════════════════
    # 三、大戶籌碼全貌：法人聰明錢 × 融資融券 × 先行指標
    # ════════════════════════════════════════════════════════════════════
    from shared.macro_buckets import bucket_group_banner_html as _bgb  # v18.310 桶群組 banner
    st.markdown(_bgb('chips', 4), unsafe_allow_html=True)
    st.markdown(section_header('三','🧩 籌碼｜🧮 大戶籌碼全貌：法人聰明錢 × 融資融券 × 先行指標','🧮'),unsafe_allow_html=True)

    # ── v18.336 §1 Fail Loud：三源(法人/融資/先行指標)全空時明確診斷,不靜默空白 ──
    # user 2026-06-28「§三 籌碼 資料不見了」：三源在缺 FINMIND_TOKEN / 來源無回應時全敗,
    # 原本 `if inst:` / `if margin:` 靜默跳過 → 整區空白。改為:全空時印診斷卡指出原因 + 救法。
    _li_probe3 = st.session_state.get('li_latest')
    _chips_all_empty3 = (not inst) and (not margin) and (
        _li_probe3 is None or getattr(_li_probe3, 'empty', True))
    if _chips_all_empty3:
        from shared.macro_buckets import chips_empty_state_html as _ces3
        _attempted3 = bool(st.session_state.get('cl_ts')) or bool(
            st.session_state.get('chips_loaded'))
        try:
            _fm_present3 = bool((getattr(st, 'secrets', {}) or {}).get('FINMIND_TOKEN')
                                or os.environ.get('FINMIND_TOKEN', ''))
        except Exception:
            _fm_present3 = bool(os.environ.get('FINMIND_TOKEN', ''))
        st.markdown(_ces3(attempted=_attempted3, token_present=_fm_present3),
                    unsafe_allow_html=True)

    if inst:
        _fk3 = next((k for k in inst if '外資' in k and '陸資' in k), None) or next((k for k in inst if '外資' in k), None)
        _tk3 = next((k for k in inst if '投信' in k), None)
        # ── v19.183 D2 §1:找不到「外資」欄位時不得回填 0（原 `if _fk3 else 0`）──
        # `inst` 有值但沒有外資 key（TWSE BFI82U 欄名變動 / FinMind rescue 只補到
        # 投信自營）時，舊碼把 `_fn3` 設 0，落進下方 `else` 分支印出
        # 「外資 +0.0億（觀望區間）→ 資金觀望，區間操作」——
        # 一個**沒有任何外資資料**的日子，被寫成「外資今天不買不賣」這個明確結論。
        # 改為 None，並在敘事上與「真的接近 0」分開（後者仍走觀望區間）。
        _fn3 = inst[_fk3]['net'] if _fk3 else None
        _tn3 = inst[_tk3]['net'] if _tk3 else None
        if _fn3 is None:
            _hye_c = TRAFFIC_NEUTRAL
            _hye_ind = '外資買賣超 ⬜ 未取得'
            _hye_concl = '三大法人資料缺「外資」欄位，本卡不下籌碼結論'
            _hye_act = ('先按「🚀 一鍵更新全部數據」；仍缺請看下方'
                        '「🔍 資料來源診斷」確認 TWSE BFI82U / FinMind 狀態')
        elif _fn3 >= 100:
            _hye_c = TRAFFIC_GREEN
            _hye_ind = f'外資大買超 {_fn3:.1f}億'
            _hye_concl = '大戶點火，跟著大戶走 → 積極加碼'
            _hye_act = '趁拉回布局，優先強勢主流股　→ 實際持股見 🎚️ 建議持股油門'
        elif _fn3 <= -100:
            _hye_c = TRAFFIC_RED
            _hye_ind = f'外資大賣超 {abs(_fn3):.1f}億'
            _hye_concl = '大戶倒貨，嚴格減碼 → 離場為上'
            _hye_act = '停損優先，嚴禁攤平　→ 實際持股見 🎚️ 建議持股油門'
        else:
            _hye_c = '#8b949e'
            _hye_ind = f'外資 {_fn3:+.1f}億（觀望區間）'
            _hye_concl = '資金觀望，區間操作'
            _hye_act = '高出低進，等方向表態　→ 實際持股見 🎚️ 建議持股油門'
        st.markdown(strategy_conclusion(STRATEGY_TECHNICAL, _hye_ind, _hye_concl, color=_hye_c), unsafe_allow_html=True)
        st.markdown(f'<div style="color:#8b949e;font-size:11px;padding:1px 8px 6px 8px;">→ 建議行動：{_hye_act}</div>', unsafe_allow_html=True)
        if _tn3 is not None and _tn3 > 5:
            st.markdown(f'<div style="color:#58a6ff;font-size:12px;padding:2px 6px;">• 投信買超 {_tn3:.1f}億 → 連續買超是加碼訊號</div>', unsafe_allow_html=True)
        # 三大法人買賣超柱狀圖（直接用 plotly，繞過 st.bar_chart→altair 相容性問題）
        # ── v19.183 D2 §1：缺哪一類就**不畫那根柱子**（原碼 `float(x or 0)`）──────
        # 舊碼把「沒抓到」畫成一根高度 0 的柱子並標「+0.0億」——
        # 讀者無從分辨「今天真的買賣超 0 億」與「今天這一類根本沒資料」。
        # 順帶清掉 `_bc_colors` 被連續賦值三次（前兩次是死碼，v19.183 移除）。
        _zk3 = next((k for k in inst if '自營' in k), None)
        _zn3 = (inst.get(_zk3) or {}).get('net') if _zk3 else None
        _bc_spec = [('外資', _fn3, '#58a6ff'),
                    ('投信', _tn3, TRAFFIC_GREEN),
                    ('自營商', _zn3, '#ffd700')]
        _bc_known = [(_nm, float(_v), _pos_c) for _nm, _v, _pos_c in _bc_spec
                     if _v is not None]
        _bc_missing = [_nm for _nm, _v, _ in _bc_spec if _v is None]
        if _bc_known:
            _bc_x = [_nm for _nm, _, _ in _bc_known]
            _bc_vals = [_v for _, _v, _ in _bc_known]
            _bc_colors = [(_pos_c if _v >= 0 else TRAFFIC_RED)
                          for _, _v, _pos_c in _bc_known]
            try:
                import plotly.graph_objects as _go_bc
                _fig_bc = _go_bc.Figure(_go_bc.Bar(
                    x=_bc_x, y=_bc_vals,
                    marker_color=_bc_colors, text=[f'{v:+.1f}億' for v in _bc_vals],
                    textposition='outside'))
                _fig_bc.update_layout(
                    height=200, margin=dict(t=30, b=10, l=10, r=10),
                    paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
                    font=dict(color='#e6edf3', size=12),
                    yaxis=dict(showgrid=False, zeroline=True,
                               zerolinecolor='#484f58', showticklabels=False))
                st.plotly_chart(_fig_bc, use_container_width=True,
                                config={'displayModeBar': False})
            except Exception as _bc_err:
                print(f'[section_chips/三大法人柱狀圖] '
                      f'{type(_bc_err).__name__}: {_bc_err}')
                st.caption('　｜　'.join(f'{_nm} {_v:+.1f}億'
                                        for _nm, _v, _ in _bc_known))
        if _bc_missing:
            st.caption(f'⬜ 未取得：{"、".join(_bc_missing)}（該類今日無資料，'
                       f'非買賣超 0 億）')
    # v19.170 P0-1 順手修 bug:原 `if margin:` 會把 margin == 0(真的收到 0 億)當成沒資料
    # 整段靜默跳過 → 改 `is not None`,0 也照常判讀(§1:有資料就要顯示)。
    if margin is not None:
        if margin >= MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:
            _sql_mc = TRAFFIC_RED
            _sql_mind = f'融資餘額 {margin:.0f}億'
            _sql_mconcl = '極度危險，嚴防多殺多 → 行情尾端'
            _sql_mact = '全面減碼、去槓桿，勿追高'
        elif margin >= MARGIN_BALANCE_WARN_THRESHOLD_YI:
            _sql_mc = TRAFFIC_YELLOW
            _sql_mind = f'融資餘額 {margin:.0f}億'
            _sql_mconcl = '水位偏高，籌碼凌亂 → 警戒操作'
            _sql_mact = '降低槓桿部位，避免重倉單一標的'
        else:
            _sql_mc = TRAFFIC_GREEN
            _sql_mind = f'融資餘額 {margin:.0f}億'
            _sql_mconcl = '籌碼乾淨，安全水位 → 可積極布局'
            _sql_mact = '籌碼面無壓，可維持既定姿態'
        st.markdown(strategy_conclusion(STRATEGY_VALUATION, _sql_mind, _sql_mconcl, color=_sql_mc), unsafe_allow_html=True)
        # v19.170 P0-1:本段只講「籌碼面該怎麼做」,持股百分比一律交給建議持股 SSOT,
        # 不再自行喊任何持股百分比,以免與 🎚️ 建議持股油門 打架。
        st.markdown(
            f'<div style="color:#8b949e;font-size:11px;padding:1px 8px 6px 8px;">'
            f'→ 建議行動：{_sql_mact}　→ 實際持股見 🎚️ 建議持股油門</div>',
            unsafe_allow_html=True)
    st.markdown('<hr style="border-color:#21262d;margin:10px 0;">', unsafe_allow_html=True)

    # ── 外資期貨（先行指標快速結論）─────────────────────────────────
    _li4 = st.session_state.get('li_latest')
    if _li4 is not None and not _li4.empty:
        _fut4 = (float(_li4.iloc[-1].get('外資大小', 0)) if '外資大小' in _li4.columns else None)
        _pcr4 = (float(_li4.iloc[-1].get('選PCR', 0)) if '選PCR' in _li4.columns else None)
        if _fut4 is not None:
            _pcr_txt = f' | PCR {_pcr4:.1f}' if _pcr4 else ''
            _l4_ind = f'外資期貨 {_fut4:,.0f}口{_pcr_txt}'
            # 絕對口數門檻（容錯率最高）
            # F1 v19.184 §3.3：`-30000` 改吃 `FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD`
            #   （同值 30000，零行為變更），結論文字裡的「3萬口」同步插值。
            # ⚠️ 下一階 `-15000` 目前**沒有**對應 SSOT 常數（B 類待抽）——
            #   它不出現在任何說明文字裡，故本批只留記錄不動它；
            #   要抽需另立具名常數（如 `FOREIGN_FUTURES_ACCUM_WATCH_LOT_THRESHOLD`）。
            if _fut4 <= -FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD:
                _l4c = (f'外資期貨空單 {abs(_fut4):,.0f}口 > '
                        f'{FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD:,}口，'
                        f'啟動強制防禦，等待空單回補')
                _l4a = '啟動強制防禦，嚴禁追高攤平，保護本金　→ 實際持股見 🎚️ 建議持股油門'
            elif _fut4 <= -15000:
                _l4c = f'外資期貨空單 {abs(_fut4):,.0f}口，空單累積中，大戶動向保守，逢高調節'
                _l4a = '收回資金，逢高調節，等待明確表態　→ 實際持股見 🎚️ 建議持股油門'
            elif _fut4 > 0:
                _l4c = f'外資期貨多單 {_fut4:,.0f}口，外資期貨翻多，燃料充足，積極作多'
                _l4a = '順勢重壓強勢股　→ 實際持股見 🎚️ 建議持股油門'
            else:
                _l4c = f'外資期貨微空 {abs(_fut4):,.0f}口，水位正常，依個股技術面操作'
                _l4a = '依個股技術面操作，保留備用現金　→ 實際持股見 🎚️ 建議持股油門'
        else:
            _l4c = '先行指標欄位異常，請確認 FinMind Token'
            _l4a = ''
            _l4_ind = '外資期貨留倉'
    else:
        _l4c = '先行指標尚未載入，請點擊「🚀 一鍵更新全部數據」'
        _l4a = ''
        _l4_ind = '外資期貨留倉'
    # v18.336：三源全空時上方已有 fail-loud 診斷卡,此處不重複「尚未載入」(避免點過更新仍喊更新)
    if not _chips_all_empty3:
        st.markdown(strategy_conclusion(STRATEGY_TECHNICAL, _l4_ind, _l4c, _l4a), unsafe_allow_html=True)

    # ── 副標籤：欄位確認列（v12 風格）─────────────────────────────────
    st.markdown("""<div style="font-size:11px;color:#484f58;margin:-6px 0 10px 0;">
✅ 外資期貨留倉口數 &nbsp;｜&nbsp; ✅ 前五大/前十大交易人 &nbsp;｜&nbsp; ✅ 外資選擇權金額 &nbsp;｜&nbsp; ✅ 韭菜指數 &nbsp;｜&nbsp; ✅ PCR
</div>""", unsafe_allow_html=True)

    # 先行指標隨更新大盤自動載入（執行緒快取版，build_leading_fast）
    df_li_show = st.session_state.get('li_latest')

    if df_li_show is not None and not df_li_show.empty:
        # v18.342 PR-L2:預存 is_stale 旗標(copy 前讀,copy 後 attrs 可能丟失)
        _is_stale_li = bool(getattr(df_li_show, 'attrs', {}).get('is_stale', False))
        _stale_age_li = getattr(df_li_show, 'attrs', {}).get('stale_age_min')
        # 向前填補 NaN（各欄位用最後一次有效數值補齊，避免 API 部分失敗造成空格）
        _li_num_cols = [c for c in df_li_show.columns if c != '日期']
        df_li_show = df_li_show.copy()
        df_li_show[_li_num_cols] = df_li_show[_li_num_cols].ffill()

        # ── ① 資料期間 caption ─────────────────────────────────────────
        _li_dates = df_li_show['日期'].tolist() if '日期' in df_li_show.columns else []
        if _li_dates:
            _d0 = _li_dates[0]
            _d1 = _li_dates[-1]
            # F1 v19.184 §3.3：前兩條門檻插 SSOT（原手抄「3萬」「1萬」）。
            # H1：第三條原為手抄的「PCR<100偏空」，本版改寫。查證結果與 F1 當時
            # 的註記**不同**，記在這裡免得又被改回去：
            #   (a) 「100」並非憑空 —— 本頁最底下的「🎯 籌碼綜合判斷」計分器確實
            #       用 >130 / >100 / ≤100 三段（見本檔下方 `_score` 那段）。
            #   (b) 但這行 caption 是**它正下方那張表**的圖例，而那張表
            #       （`render_leading_table`）的著色判定式是 <80 紅 / >120 綠。
            #       圖例標的線 ≠ 表格用的線 → 讀數 90 的那天，caption 說「偏空」、
            #       表格塗中性色。
            #   (c) 本區顯示的 PCR 是**百分比刻度**（126.8 這種數字），不是比值。
            #       `li_latest['選PCR']` 由 `leading_indicators` 寫入時已 ×100，
            #       B2-b 的 `normalize_pcr_to_ratio()` 只在取值端換算給規則引擎/
            #       LLM 用，**沒有回寫** li_latest。所以這行不可改寫成比值刻度，
            #       否則會出現「caption 說 0.8、表格印 126.8」的新矛盾。
            # → 改為指向表格真正會亮燈的兩條帶（SSOT: shared/pcr_scale），
            #   並另起一行把刻度與「1.0 平價點是常識、不是本系統門檻」講明。
            st.caption(
                f'📅 資料期間：{_d0} ~ {_d1}  共 {len(df_li_show)} 筆  '
                f'｜外資空單>{FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD:,}口⚠️  '
                f'前五大>{abs(TOP5_LARGE_TRADER_NET_WARN_LOTS):,}口⚠️  '
                f'選PCR<{PCR_PCT_COMPLACENCY_MAX:.0f}🔴過樂觀／'
                f'>{PCR_PCT_FEAR_MIN:.0f}🟢恐慌區'
            )
            st.caption(
                f'ℹ️ 本表「選PCR」為**百分比刻度**（＝標準 Put/Call 比值×100，'
                f'例：{PCR_PCT_FEAR_MIN:.0f} ＝ 比值 {PCR_PCT_FEAR_MIN / 100:.1f}）。'
                f'比值 1.0（本表 {PCR_PCT_PARITY:.0f}）是選擇權 put/call 的**平價點**，'
                f'屬市場常識，**不是本系統的判定線**；'
                f'本表著色帶為 <{PCR_PCT_COMPLACENCY_MAX:.0f} 紅（保護不足）／'
                f'>{PCR_PCT_FEAR_MIN:.0f} 綠（避險濃厚）。'
                f'下方「⚡ 進階警示」與「🎯 籌碼綜合判斷」另有各自的敏感度，'
                f'三者用途不同、刻意不合併。'
            )
            # v18.342 PR-L2:stale fallback 顯示「📦 上次有效資料」chip(§2.4)
            if _is_stale_li:
                _age_txt = f'{_stale_age_li:.0f} 分鐘前' if isinstance(
                    _stale_age_li, (int, float)) else '較早'
                st.markdown(
                    f'<div style="display:inline-block;font-size:11px;color:#f0883e;'
                    f'background:#0d1117;border:1px solid #f0883e;border-radius:4px;'
                    f'padding:3px 9px;margin:2px 0 8px 0;">'
                    f'📦 顯示上次有效資料({_age_txt}抓的)— 當次 FinMind 無新資料'
                    f'(週末/假日/API 額度) → 數值非今日最新</div>',
                    unsafe_allow_html=True)

        # S-PROV-1 UI chip v18.265 — provenance(source + fetched_at,從 df 末筆讀)
        try:
            _li_prov_src = None
            _li_prov_at = None
            if "source" in df_li_show.columns and not df_li_show.empty:
                _li_prov_src = str(df_li_show["source"].iloc[-1])
            if "fetched_at" in df_li_show.columns and not df_li_show.empty:
                _li_prov_at = str(df_li_show["fetched_at"].iloc[-1])[:19]
            if _li_prov_src or _li_prov_at:
                st.markdown(
                    f"<div style='font-size:10px;color:#888;padding:3px 8px;"
                    f"background:#0d1117;border-radius:4px;margin:2px 0 6px 0'>"
                    f"📍 來源:{_li_prov_src or '—'}　🕐 抓取:{_li_prov_at or '—'} UTC"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        except Exception:
            pass

        # ── ② 主表格（render_leading_table，已內含深色主題CSS）──────────
        st.markdown(render_leading_table(df_li_show), unsafe_allow_html=True)

        # 欄位說明 → 已移至 Tab 5 策略手冊



        # ── ③ 進階警示訊號（依建議加入5個條件）──────────────────────────
        _last_row = df_li_show.iloc[-1] if not df_li_show.empty else {}
        _fut_net  = _last_row.get('外資大小')
        _pcr      = _last_row.get('選PCR')
        _opt_net  = _last_row.get('外(選)')
        _leek     = _last_row.get('韭菜指數')
        _foreign  = _last_row.get('外資')  # 現貨外資買賣
        _trust    = _last_row.get('投信')  # 投信買賣
        _warnings = []

        # 訊號 1：期權同向崩盤訊號（最強烈）
        # 期貨大空 + 選擇權外資淨空 → 不惜成本避險
        try:
            if _fut_net is not None and float(_fut_net) < -20000:
                if _opt_net is not None and float(_opt_net) < 0:
                    # v19.171:移除硬編碼「建議降倉至30%以下」—— 實機驗收抓到它與
                    # 同畫面「最終建議持股 20%」(建議持股 SSOT)當場矛盾。
                    # 警示卡只負責敘事(發生什麼事、為何危險),持股水位一律指回
                    # get_allocation();守門測試 v19.171 已補動詞型「降倉」樣式。
                    _warnings.append(('🔴', '期權同向崩盤警戒',
                        f'期貨空{abs(float(_fut_net)):,.0f}口 + 選擇權外資淨空{float(_opt_net):,.0f}千元',
                        '外資「不惜成本」雙向避險，高機率隨即殺盤，務必嚴控風險　'
                        '→ 實際持股見 🎚️ 建議持股油門'))
                elif _fut_net is not None and float(_fut_net) < -30000:
                    _warnings.append(('🟡', '期貨大空警戒',
                        f'外資期貨空單 {abs(float(_fut_net)):,.0f} 口（>3萬口門檻）',
                        '注意流向：若每日持續增加空單才是真訊號；若空單縮減則危機解除'))
        except Exception:
            pass

        # 訊號 2：韭菜指數極端值
        # v19.176 P0-D §3.3：門檻 ±30 原為 inline magic number，抽至 L0 SSOT
        # `config.LEEK_ALERT_*`。**刻意不與** section_chips 綜合評分（±10/-5）、
        # section_state 拐點（±20）合併 —— 三者用途/敏感度不同，合併=行為變更。
        # ⚠️ 本欄位是「小台法人空多比 ±%」，與 config.LEEK_HIGH_THRESHOLD(35)
        # 那組「融資餘額 0~100 指數」**不同量綱**，不可互換（§4.1）。
        try:
            if _leek is not None:
                _leek_f = float(_leek)
                if _leek_f > LEEK_ALERT_HIGH_PCT:
                    _warnings.append(('🔴', '散戶過度樂觀（韭菜極端多）',
                        f'法人空多比 {_leek_f:+.1f}%'
                        f'（超過 {LEEK_ALERT_HIGH_PCT:+.0f}% 警戒線）',
                        '散戶一面倒看多，短線見頂訊號，主力容易在此出貨'))
                elif _leek_f < LEEK_ALERT_LOW_PCT:
                    _warnings.append(('🟢', '軋空動能極強（韭菜極端空）',
                        f'法人空多比 {_leek_f:+.1f}%'
                        f'（超過 {LEEK_ALERT_LOW_PCT:+.0f}% 機會線）',
                        '散戶爭相放空，軋空動能強，千萬不要在此放空，逆勢做多機會'))
        except Exception:
            pass

        # 訊號 3：外資投信同買（最強籌碼訊號）
        try:
            if _foreign is not None and _trust is not None:
                _f2 = float(_foreign)
                _t2 = float(_trust)
                if _f2 > 50 and _t2 > 5:
                    _warnings.append(('🟢', '外資投信同買（籌碼共鳴）',
                        f'外資+{_f2:.0f}億 + 投信+{_t2:.1f}億 同步買超',
                        '外投同買的股票漲幅連續性最強，現貨籌碼最乾淨'))
                elif _f2 < -100 and _t2 < -5:
                    _warnings.append(('🔴', '外資投信同賣（籌碼潰散）',
                        f'外資{_f2:.0f}億 + 投信{_t2:.1f}億 同步賣超',
                        '雙主力同步出場，下跌壓力沉重'))
        except Exception:
            pass

        # 訊號 4：PCR 極端值判斷
        try:
            if _pcr is not None:
                _pcr_f = float(_pcr)
                if _pcr_f < 80:
                    _warnings.append(('🔴', '選擇權Put/Call偏低（市場過樂觀）',
                        f'PCR={_pcr_f:.1f}（<80偏危險，市場保護不足）',
                        '選擇權市場無人買保護，通常出現在短線頂部'))
                elif _pcr_f > 150:
                    _warnings.append(('🟢', '選擇權Put/Call偏高（恐慌區）',
                        f'PCR={_pcr_f:.1f}（>150偏多，市場過度悲觀）',
                        '大量買保護代表市場恐慌，通常是逆向布局訊號'))
        except Exception:
            pass

        # 訊號 5：成交量萎縮（市場觀望）
        try:
            # P4: vectorized str → numeric，避免逐列 Python 呼叫
            _vols = (pd.to_numeric(
                df_li_show['成交量'].tail(5).astype(str).str.replace('億','', regex=False),
                errors='coerce').dropna().tolist()
                if '成交量' in df_li_show.columns else [])
            if len(_vols) >= 3:
                _avg_vol = sum(_vols[:-1]) / len(_vols[:-1])
                _last_vol = _vols[-1]
                # F1 v19.184 §3.3 + §4.1：比值 0.7/1.5 抽 SSOT，
                # 文案的「30%」「50%」由同一個比值**現算**（原本是人腦換算後手寫）。
                if _last_vol < _avg_vol * MARKET_VOLUME_SHRINK_RATIO:
                    _warnings.append(('🟡', '成交量急萎縮（市場觀望）',
                        f'今日成交量{_last_vol:.0f}億（前{len(_vols)-1}日均量{_avg_vol:.0f}億的{_last_vol/_avg_vol*100:.0f}%）',
                        f'量縮超過{(1 - MARKET_VOLUME_SHRINK_RATIO) * 100:.0f}%'
                        f'代表市場觀望，方向選擇前勿輕易追高'))
                elif _last_vol > _avg_vol * MARKET_VOLUME_SURGE_RATIO:
                    _warnings.append(('🔵', '成交量急放（趨勢加速）',
                        f'今日成交量{_last_vol:.0f}億（前均量{_avg_vol:.0f}億的{_last_vol/_avg_vol*100:.0f}%）',
                        f'成交量暴增{(MARKET_VOLUME_SURGE_RATIO - 1) * 100:.0f}%以上，'
                        f'趨勢加速，注意是否配合方向'))
        except Exception:
            pass

        if _warnings:
            for _wc, _wt, _wd, _wa in _warnings:
                _wcolor = ('#2ea043' if _wc == '🟢' else
                           '#da3633' if _wc == '🔴' else
                           TRAFFIC_YELLOW if _wc == '🟡' else '#388bfd')
                st.markdown(
                    f'<div style="border-left:5px solid {_wcolor};background:#0d1117;'
                    f'padding:9px 14px;border-radius:0 8px 8px 0;margin:4px 0;">'
                    f'<span style="font-size:11px;color:{TRAFFIC_NEUTRAL};">⚡ 進階警示</span><br>'
                    f'<span style="font-size:14px;font-weight:900;color:{_wcolor};">{_wc} {_wt}</span><br>'
                    f'<span style="font-size:12px;color:#c9d1d9;">{_wd}</span><br>'
                    f'<span style="font-size:11px;color:#8b949e;">→ {_wa}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )


        # ── ⑤ v4 引擎風險燈（V4StrategyEngine Task 2）─────────────────
        # v19.170 P0-1:本卡原本直接印 V4StrategyEngine 的 `max_position`
        # (L2 上游自算的 20/50/100),與 🎚️ 建議持股油門 完全脫鉤 → 同一畫面
        # 兩個持股數字打架。改為:**v4 的否決狀態/理由(敘事)保留**,
        # 持股數字一律取自建議持股 SSOT(get_allocation)。
        #
        # v19.176 P0-D 正名:本卡原標題「🏛️ v4.0 總經否決權」與 §八 總經拼圖
        # 裡另一組**完全不同**的判定同名,同一頁給出相反結論(實機 2026-08-05)。
        # 兩者不合併(輸入集/用途不同,合併=行為變更),改為正名 + 各自標明
        # 「看了什麼、沒看什麼」。名稱與範圍說明走 L0 SSOT(config.VETO_*),
        # 取數+判定走同檔 `read_v4_macro_veto()`(§八 揭露分歧時吃同一份輸入)。
        try:
            import re as _re_v4

            from src.services.allocation_service import (
                get_allocation as _get_alloc_veto,
            )
            # v19.170 P0-2 的「常數偽裝成資料」修正(原硬編碼 vix=15,讓
            # VIX>25 紅燈 / VIX>20 黃燈 兩條規則永久失效)已下沉至
            # `read_v4_macro_veto()`,含 §1「VIX 取不到不得回填 15」的短路。
            _v4_veto = read_v4_macro_veto()
            if _v4_veto is None:
                _v4_veto = {
                    'status': '⬜ 無法判定',
                    'color':  TRAFFIC_NEUTRAL,
                    'msg':    f'VIX 未取得，{VETO_V4_ENGINE_NAME}無法判定 — '
                              '請先按「🚀 一鍵更新全部數據」補齊 VIX 後再看本卡。',
                }
            _v4_c = _v4_veto['color']
            _alloc_veto = _get_alloc_veto()
            _v4_pos = (f'建議持股 {_alloc_veto.range_text}' if _alloc_veto.is_loaded
                       else '⬜ 總經未評估')
            _v4_cap_html = (
                f'<span style="font-size:11px;color:{TRAFFIC_YELLOW};">'
                f'{_alloc_veto.cap_text}</span><br>'
                if _alloc_veto.capped and _alloc_veto.cap_text else '')
            # L2 的 msg 字串內嵌硬編碼百分比(v4_strategy_engine:93 的紅燈文案)。
            # L2 屬白名單不改,改在 UI 邊界剝除數字、只留敘事 → 畫面零競爭數字。
            _v4_msg = _re_v4.sub(
                r'建議持股\s*[≤≥<>~\-–—]*\s*\d+\s*[%％]',
                '（實際持股見 🎚️ 建議持股油門）',
                str(_v4_veto.get('msg', '')))
            st.markdown(
                f'<div style="border-left:5px solid {_v4_c};background:#0d1117;'
                f'padding:9px 14px;border-radius:0 8px 8px 0;margin:6px 0;">'
                f'<span style="font-size:11px;color:{TRAFFIC_NEUTRAL};">'
                f'🏛️ {VETO_V4_ENGINE_NAME}</span><br>'
                f'<span style="font-size:14px;font-weight:900;color:{_v4_c};">'
                f'{_v4_veto["status"]} — {_v4_pos}</span><br>'
                f'{_v4_cap_html}'
                f'<span style="font-size:12px;color:#c9d1d9;">{_v4_msg}</span><br>'
                # v19.176 P0-D §1:標明本燈的判定範圍。使用者看到「🔴 高風險」
                # 而 §八 說「無觸發」時,必須看得出那是**兩個不同判定**,
                # 而不是系統自打嘴巴。
                f'<span style="font-size:11px;color:{TRAFFIC_NEUTRAL};">'
                f'📌 {VETO_V4_ENGINE_SCOPE_NOTE}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
        except Exception as _v4e:
            # v19.170 §1 Fail Loud:原本 `pass` → 整張卡無聲消失、零 log,
            # 使用者只看到畫面少一塊,無從分辨是「沒觸發」還是「算爆了」。
            print(f'[section_chips/v4] {type(_v4e).__name__}: {_v4e}')
            st.warning(f'⚠️ {VETO_V4_ENGINE_NAME}卡計算失敗，請看 log')


        # ── v5.0 動態資產配置建議 ─────────────────────────────────────
        # v19.170 P0-1:原本依外資期貨口數自算 20/80、50/50、90/10、70/30,
        # 與 🎚️ 建議持股油門 完全脫鉤。改為:**期貨敘事(該怎麼操作)保留**,
        # 配置數字一律取自 get_allocation_sleeves()(由 SSOT 最終持股中值推導)。
        try:
            from src.services.allocation_service import get_allocation_sleeves
            _v5_fut = float(_last_row.get('外資大小') or 0)
            if _v5_fut <= -30000:
                _v5_strategy = '嚴禁追高攤平，保護本金優先；可留意低基期高殖利率個股'
                _v5_color = TRAFFIC_RED
            elif _v5_fut <= -15000:
                _v5_strategy = '收回資金，逢高減碼漲多個股，等待期空回補訊號'
                _v5_color = TRAFFIC_YELLOW
            elif _v5_fut > 0:
                _v5_strategy = '期貨翻多，順勢重壓強勢股，外投同買個股優先布局'
                _v5_color = TRAFFIC_GREEN
            else:
                _v5_strategy = '水位中性，依個股技術面操作，保留現金彈藥'
                _v5_color = '#58a6ff'
            _v5_slv = get_allocation_sleeves()
            if _v5_slv is None:
                # §1 Fail Loud:總經未評估 → 誠實顯示,不回填任何預設配置
                _v5_head = '⬜ 總經未評估 — 請先按「🚀 一鍵更新全部數據」'
                _v5_color = TRAFFIC_NEUTRAL
            else:
                _v5_head = (f'股票 {_v5_slv["股票型ETF"]}%'
                            f' ／債券 {_v5_slv["債券型ETF"]}%'
                            f' ／現金 {_v5_slv["貨幣/現金"]}%')
            st.markdown(
                f'<div style="border-left:5px solid {_v5_color};background:#0d1117;'
                f'padding:9px 14px;border-radius:0 8px 8px 0;margin:6px 0;">'
                f'<span style="font-size:11px;color:{TRAFFIC_NEUTRAL};">'
                f'💰 v5 動態配置（數字來源：🎚️ 建議持股油門）</span><br>'
                f'<span style="font-size:14px;font-weight:900;color:{_v5_color};">'
                f'{_v5_head}</span><br>'
                f'<span style="font-size:12px;color:#c9d1d9;">📌 {_v5_strategy}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
        except Exception as _v5e:
            # v19.170 §1 Fail Loud:同 v4 —— 不再靜默吞掉配置卡的例外。
            print(f'[section_chips/v5] {type(_v5e).__name__}: {_v5e}')
            st.warning('⚠️ v5.0 動態配置卡計算失敗，請看 log')

# ── ④ 資料來源診斷（收合，供進階使用者確認）─────────────────────
        with st.expander('🔍 資料來源診斷（點此確認各欄數據正確性）', expanded=False):
            # v18.350 PR-P1:加 TTL + 備援優先級兩欄,SSOT 對齊「資料診斷 Tab」(app.py:1649
            # tab_diag),避免 user 誤把 30min 快取舊值當「即時」。dict 升級為 4-tuple:
            # (來源主鏈, 公式, TTL, 備援優先級或 single-source 標註)。
            _diag_cols = {
                '外資大小':       ('FinMind TX+MTX 期貨留倉',
                                   '外資大台淨口 + 外資小台淨口×0.25',
                                   '30 分(build_leading_fast pickle)',
                                   '① FinMind TX → ② FinMind MTX → ③ TAIFEX futContractsDate 備援'),
                '前五大留倉':     ('TAIFEX largeTraderFutQry POST',
                                   '前五大買方所有契約 − 賣方所有契約',
                                   '30 分(同上)',
                                   '單一源(免費 FinMind 無此資料)'),
                '前十大留倉':     ('TAIFEX largeTraderFutQry POST',
                                   '前十大買方所有契約 − 賣方所有契約',
                                   '30 分(同上)',
                                   '單一源'),
                '選PCR':          ('TAIFEX pcRatio POST',
                                   'Put未平倉量 / Call未平倉量 × 100',
                                   '30 分(同上)',
                                   '① TAIFEX → ② FinMind TXO 法人估算(備援)'),
                '外(選)':         ('TAIFEX callsAndPutsDate POST',
                                   'BC金額 − SC金額 − BP金額 + SP金額',
                                   '30 分(同上)',
                                   '單一源'),
                '韭菜指數':       ('TAIFEX futContractsDate+futDailyMarketReport',
                                   '(法人空方MTX OI − 法人多方MTX OI) / 全體MTX OI × 100',
                                   '30 分(同上)',
                                   '① TAIFEX → ② FinMind 法人空多比估算(備援)'),
                '外資/投信/自營': ('TWSE BFI82U(via Squid Proxy)',
                                   '三大法人現貨買賣差額(億元)',
                                   '10 分(TTL_CONFIG[institutional])',
                                   '① TWSE → ② FinMind → ③ pkl Cache(過期)'),
                '成交量':         ('TWSE FMTQIK 月報',
                                   '每日全市場成交金額(億元)',
                                   '10 分(TTL_CONFIG[volume])',
                                   '① TWSE OpenAPI → ② YFinance → ③ Cache'),
            }
            # 頂部全域註腳:cache 新鮮度告示
            st.markdown(
                '<div style="font-size:11px;color:#f0883e;background:#0d1117;'
                'padding:6px 10px;border-left:3px solid #f0883e;margin:4px 0 10px;">'
                '💡 <b>注意 cache 新鮮度</b>:本表所列指標多走 30 分鐘 pickle 快取 + '
                'st.cache_data。週末/假日 4 個 FinMind API 全空時 leading_fast 會 fallback '
                '到過期 pickle(已標 📦 stale chip)。「即時」≠「最新交易日」,以畫面上方'
                '「資料期間」caption 為準。</div>',
                unsafe_allow_html=True)
            for _col, _tup in _diag_cols.items():
                # 向下相容:舊 2-tuple 仍 fallback(避免外部 caller 改 dict 時崩)
                if len(_tup) == 4:
                    _src, _formula, _ttl, _fallback = _tup
                else:
                    _src, _formula = _tup[0], _tup[1]
                    _ttl, _fallback = '-', '-'
                st.markdown(
                    f'<div style="font-size:12px;color:#8b949e;padding:3px 0;">'
                    f'<b style="color:#c9d1d9;">{_col}</b> → 主來源:{_src}<br>'
                    f'&nbsp;&nbsp;&nbsp;公式:{_formula}<br>'
                    f'&nbsp;&nbsp;&nbsp;⏱ TTL:{_ttl}<br>'
                    f'&nbsp;&nbsp;&nbsp;🔀 備援優先級:{_fallback}</div>',
                    unsafe_allow_html=True
                )
            # [BUG FIX] 最新一筆原始值 - 用 pd.isna 確保 NaN 不造成 format error
            if len(df_li_show) > 0:
                _raw = df_li_show.iloc[-1]
                st.markdown('<br><b style="color:#c9d1d9;font-size:12px;">最新一筆原始值：</b>', unsafe_allow_html=True)
                _raw_items = []
                for _c in ['外資大小','前五大留倉','前十大留倉','選PCR','外(選)','韭菜指數','外資','投信','自營']:
                    _v = _raw.get(_c)
                    if _v is not None:
                        try:
                            import pandas as _pd_raw
                            if not _pd_raw.isna(_v):  # [BUG FIX] 過濾 NaN 避免 format 崩潰
                                _raw_items.append(f'{_c}={float(_v):+,.0f}')
                        except Exception:
                            _raw_items.append(f'{_c}={_v}')
                st.code(' | '.join(_raw_items), language=None)

        # ── ⑤ 下載按鈕（Base64 data URL，不依賴 WebSocket）──────
        try:
            import base64 as _b64_li
            # ── v19.173:匯出欄位白名單(原本 to_csv 直接倒全欄 → schema 靜默變寬)──
            # df_li_show 帶著一批**內部 marker 欄**,是給下游程式判旗標用的,不是
            # 給人看的資料:`_date`(YYYYMMDD 排序鍵)、`_oi_src`(契約別)、
            # `_oi_inconsistent`(資料源打架)、`_is_stale` / `_stale_age_min`
            # (v19.170 過期快取旗標)。v19.172 一口氣新增 3 欄後,它們就跟著跑進
            # 使用者下載的「先行指標.csv」,畫面上卻完全看不到 → 規則:
            #   ① 底線開頭 = 內部 marker → 一律排除。
            #   ② `OI_TX當量` **保留**:它不以底線開頭,也不是 marker,而是唯一
            #      與「外資大小」同當量(TX)的分母(TX + 0.25×MTX,§4.1 量綱)。
            #      分析價值高於欄名沿用歷史包袱、契約別會跳動的「未平倉口數」,
            #      拿掉反而讓 CSV 使用者算不出正確的比值。
            #   ③ `_date` 例外處理 —— **改名保留而非丟棄**:畫面「日期」欄是
            #      「8月4日」(無年份),跨年下載會無法判讀;正名為 `日期YYYYMMDD`
            #      後它就是使用者可讀欄位,不算 marker 外洩,且零資訊損失。
            #   ④ `source` / `fetched_at` 保留(§2.2 血緣:CSV 落地後仍可追來源)。
            _drop_li = [c for c in df_li_show.columns
                        if str(c).startswith('_') and c != '_date']
            _csv_df_li = df_li_show.drop(columns=_drop_li, errors='ignore')
            if '_date' in _csv_df_li.columns:
                _csv_df_li = _csv_df_li.rename(columns={'_date': '日期YYYYMMDD'})
                _csv_df_li = _csv_df_li[
                    ['日期YYYYMMDD']
                    + [c for c in _csv_df_li.columns if c != '日期YYYYMMDD']]
            _csv_li = _csv_df_li.to_csv(index=False, encoding='utf-8-sig')
            _b64_li_data = _b64_li.b64encode(_csv_li.encode('utf-8-sig')).decode()
            st.markdown(
                f'<a href="data:text/csv;charset=utf-8-sig;base64,{_b64_li_data}" '
                f'download="先行指標.csv" '
                f'style="display:inline-block;padding:5px 14px;background:#21262d;'
                f'color:#e6edf3;border:1px solid #30363d;border-radius:6px;'
                f'font-size:13px;text-decoration:none;">⬇️ 下載先行指標 CSV</a>',
                unsafe_allow_html=True
            )
            # v19.173:欄位範圍公告 —— 排除 marker 後欄數會變少,不講清楚使用者
            # 會以為「資料變少了」。同時點名多出來的 OI_TX當量 是什麼。
            st.caption(
                'CSV 欄位＝畫面表格全欄 ＋ `日期YYYYMMDD`（完整日期）'
                ' ＋ `OI_TX當量`（TX 當量分母＝OI_TX＋0.25×OI_MTX，唯一可與「外資大小」相除）'
                ' ＋ `source` / `fetched_at`（來源與抓取時間）；'
                '已排除底線開頭的內部旗標欄（契約別、資料源打架、過期快取標記）。'
            )
        except Exception as _e_csv_li:
            # §1:匯出失敗會讓下載按鈕整個消失,靜默 pass 使用者只會以為功能壞了
            print(f'[section_chips] 先行指標 CSV 匯出失敗: '
                  f'{type(_e_csv_li).__name__}: {_e_csv_li}')

    else:
        # v18.340 §1 Fail Loud：對齊 PR #362 chips_empty_state 三狀態分流(table 專屬 helper)。
        # user 2026-06-28「原來的 table 呢?」(對比 6/14 截圖)→ 真正根因常是 FINMIND_TOKEN
        # 缺失/失效,舊文案沒明指,user 找不到救法。新 helper 明確分流:
        #   未載入(灰) / 已試+無token(橙明指 FINMIND_TOKEN) / 已試+有token(橙歸因額度/週末)。
        from shared.macro_buckets import leading_table_empty_state_html as _li_es
        _attempted_li = bool(cd) or bool(st.session_state.get('cl_ts')) or bool(
            st.session_state.get('chips_loaded'))
        try:
            _fm_present_li = bool((getattr(st, 'secrets', {}) or {}).get('FINMIND_TOKEN')
                                  or os.environ.get('FINMIND_TOKEN', ''))
        except Exception:
            _fm_present_li = bool(os.environ.get('FINMIND_TOKEN', ''))
        st.markdown(_li_es(attempted=_attempted_li, token_present=_fm_present_li),
                    unsafe_allow_html=True)

    # 判斷方式 → 已移至 Tab 5 策略手冊

    # ── 智能綜合結論 ─────────────────────────────────────────────────────
    _df_li_c = st.session_state.get('li_latest')
    if _df_li_c is not None and not _df_li_c.empty:
        _last_li = _df_li_c.iloc[-1]
        _fnet = safe_get(_last_li.get('外資大小'))
        _pcr  = safe_get(_last_li.get('選PCR'))
        _leek = safe_get(_last_li.get('韭菜指數'))
        _top5 = safe_get(_last_li.get('前五大留倉'))
        _opt  = safe_get(_last_li.get('外(選)'))
        _date = _last_li.get('日期','最新')

        _score = 0
        _sigs = []
        if _fnet is not None:
            if   _fnet < -30000:
                _score -= 2
                _sigs.append(f'🔴 期貨空單 {_fnet:,.0f}口（超越3萬危險線）')
            elif _fnet <      0:
                _score -= 1
                _sigs.append(f'⚠️ 期貨淨空 {_fnet:,.0f}口')
            else:
                _score += 1
                _sigs.append(f'✅ 期貨淨多 {_fnet:+,.0f}口')
        if _pcr is not None:
            if   _pcr > 130:
                _score += 1
                _sigs.append(f'🟢 PCR={_pcr:.0f}（>130強支撐）')
            elif _pcr > 100:
                _sigs.append(f'🔵 PCR={_pcr:.0f}（偏多）')
            else:
                _score -= 1
                _sigs.append(f'🔴 PCR={_pcr:.0f}（<100偏空）')
        if _opt is not None:
            if   _opt >  10000:
                _score += 1
                _sigs.append(f'🟢 外選 +{_opt:,.0f}千元（多方佈局）')
            elif _opt < -10000:
                _score -= 1
                _sigs.append(f'🔴 外選 {_opt:,.0f}千元（空方佈局）')
            else:
                _sigs.append(f'⚪ 外選 {_opt:+,.0f}千元（中性）')
        if _top5 is not None:
            if   _top5 < -10000:
                _score -= 1
                _sigs.append(f'🔴 前五大淨空 {_top5:,.0f}口（警戒）')
            elif _top5 >       0:
                _score += 1
                _sigs.append(f'✅ 前五大淨多 {_top5:+,.0f}口')
        if _leek is not None:
            # v19.176 P0-D §3.3：門檻 +10 / -5 原為 inline magic number，抽至 L0
            # SSOT `config.LEEK_SCORE_*`。**刻意與上方進階警示（±30）分名** ——
            # 這裡是「加減 1 分」的計分器，要對中度傾斜就有反應，故門檻最敏感；
            # 正負不對稱（+10 vs -5）也是刻意的，理由記在 config 該常數註解。
            # 敏感度差異的實務後果：leek=15 時本行亮 🔴，而進階警示（>30）與
            # 拐點（>20）都不會吭聲 —— 那是**設計如此**，不是 bug。
            if   _leek > LEEK_SCORE_HIGH_PCT:
                _score -= 1
                _sigs.append(f'🔴 韭菜指數{_leek:.1f}%（散戶過熱）')
            elif _leek < LEEK_SCORE_LOW_PCT:
                _score += 1
                _sigs.append(f'✅ 韭菜指數{_leek:.1f}%（散戶悲觀）')
            else:
                _sigs.append(f'⚪ 韭菜指數{_leek:.1f}%（中性）')

        if   _score <= -3:
            _vd='🚨 強烈偏空'
            _vc=TRAFFIC_RED
            _va='建議大幅降倉，等待空單回補訊號'
        elif _score <= -1:
            _vd='🔴 偏空'
            _vc='#da6d3e'
            _va='籌碼不穩，建議觀望為主'
        elif _score ==  0:
            _vd='⚪ 多空分歧'
            _vc=TRAFFIC_YELLOW
            _va='訊號分歧，小倉觀察，詳見策略手冊'
        elif _score <=  2:
            _vd='🟢 偏多'
            _vc=TRAFFIC_GREEN
            _va='籌碼偏健康，可正常持倉'
        else:
            _vd='💚 強烈偏多'
            _vc='#2ea043'
            _va='聰明錢明顯佈多，積極持倉'

        st.markdown(
            f'<div style="background:#0d1117;border:2px solid {_vc}44;border-radius:10px;padding:14px 18px;margin:8px 0;">'
            f'<div style="font-size:11px;color:#8b949e;margin-bottom:4px;">🎯 {_date} 籌碼綜合判斷</div>'
            f'<div style="font-size:24px;font-weight:900;color:{_vc};">{_vd}</div>'
            f'<div style="font-size:13px;color:#c9d1d9;margin:6px 0 10px 0;">{_va}</div>'
            f'<div style="font-size:12px;color:#484f58;">{" ； ".join(_sigs)}</div>'
            f'</div>',
            unsafe_allow_html=True
        )


    st.markdown('<hr style="border-color:#21262d;margin:14px 0;">',unsafe_allow_html=True)
