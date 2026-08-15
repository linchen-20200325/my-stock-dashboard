"""src/ui/tabs/stock_sections/section_psy_checklist.py — 心理檢查 + 勝利方程式 + 禁止操作 3 section(v18.406 U4 Phase 2-Psy).

從 tab_stock.py:826-909 抽出。原 3 個相連 section 共享 _q3 / _wr_margin2 / _wr_reg2 state,
合併為一個 render 函式維持原邏輯。

§8.2 layer:L5 UI Tab section helper。

D1 v19.185 稽核修正（§1 Fail Loud, Never Fake / §3.3 反捏造）
--------------------------------------------------------------
本檔原本是「綠燈不代表算過」的重災區,4 項一次收斂:

1. **幽靈 key**:「💎 非357昂貴區」讀 `t2_data['val']` —— 該 key **全站沒有任何
   寫入點**（`tab_stock.py` 寫的是 sid/name/df/price/avg_div/… 共 28 個 key,
   沒有 `val`）。於是 `'昂貴' not in ''` 恆為 True ⇒ **這一項對每一檔股票、
   任何價位都是 ✅**。現改用 `classify_stock_357_price(price, avg_div)` SSOT
   由 `t2_data` 真有的 price/avg_div 現算。
2. **捏造預設值**:「💰 融資安全」讀 `cl_data.margin` 缺席時退 `0`,
   `0 < 2500億` ⇒ 總經沒載入時這一項也是 ✅。現改三態,未取得顯示 ⬜。
3. **未載入被偽裝成震盪**:兩處 `mkt_info.get('regime','neutral')` 直讀趨勢面
   **輸入** + 捏 `'neutral'`。現改吃 C1 唯一仲裁點 `get_macro_regime()`。
4. **畫面宣稱門檻 ≠ 判定式**:標題寫「需全部符合」、判定式是 `>= 4`(5 項中 4 項);
   同一頁「近5日漲幅」用了 `iloc[-6]` 與 `iloc[-5]` 兩個基期算出兩個數字。
   兩者皆收斂到 `shared/signal_thresholds` 常數 + 單一算式。

對外 API:
- render_psy_checklist_section(sid2, df2, health2, _atr2_val) -> None
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED
from shared.signal_thresholds import (
    MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
    MARGIN_BALANCE_WARN_THRESHOLD_YI,
    SOP_BAN_MONTHLY_LOSS_PCT,
    SOP_BAN_SURGE_PCT,
    SOP_SURGE_HARD_PCT,
    SOP_SURGE_LOOKBACK_DAYS,
    SOP_SURGE_WARN_PCT,
    WINNING_FORMULA_HEALTH_MIN,
    WINNING_FORMULA_MIN_PASS,
)
from shared.thresholds import classify_stock_357_price
from src.ui.render.tab_sections import border_left_banner, box_wrapper_open

#: 三態旗標 → (emoji, 顏色)。None = 未評估,**不得**當成 False 渲染（§1）。
_TRISTATE_ICON = {True: '✅', False: '❌', None: '⬜'}
_TRISTATE_COLOR = {True: TRAFFIC_GREEN, False: TRAFFIC_RED, None: TRAFFIC_NEUTRAL}


def _surge_pct(df2, lookback_days: int = SOP_SURGE_LOOKBACK_DAYS):
    """近 N 個**交易日**漲幅 %(§4.1:交易日 ≠ 日曆日)。

    基期 = `close.iloc[-(N+1)]`（N 根 K 棒之前的收盤）。資料不足 → None(不猜)。

    D1 v19.185:原本同一頁有兩份實作 —— 檢核 ② 用 `iloc[-6]`、禁止清單用
    `iloc[-5]`,兩者都標「近5日漲幅」卻差一根 K 棒,畫面上會出現兩個不同數字。
    """
    if df2 is None or 'close' not in getattr(df2, 'columns', []):
        return None
    if len(df2) < lookback_days + 1:
        return None
    try:
        _now = float(df2['close'].iloc[-1])
        _base = float(df2['close'].iloc[-(lookback_days + 1)])
    except (ValueError, TypeError, IndexError):
        return None
    if not _base or _base <= 0 or _now != _now or _base != _base:  # 0 / NaN guard
        return None
    return round((_now - _base) / _base * 100, 1)


def _read_margin_yi():
    """總經一鍵更新寫入的融資餘額(億)。**未取得回 None**,不回 0。

    §1:`0 億融資` 與「沒抓到融資」是兩件事,前者會讓「融資安全」條件變成
    永遠成立的假綠燈。
    """
    _cd = st.session_state.get('cl_data')
    if not isinstance(_cd, dict):
        return None
    _m = _cd.get('margin')
    try:
        _f = float(_m)
    except (TypeError, ValueError):
        return None
    return None if _f != _f else _f  # NaN → None


def build_winning_conditions(*, regime, macro_loaded: bool, margin_yi,
                             health, price, avg_div, stop_set: bool):
    """「🏆 勝利方程式」5 條件 → `[(label, state, unknown_note), ...]`（純函式）。

    `state` 是**三態**：True 成立 / False 不成立 / **None 未評估**。
    §1：把 None 壓成 False 或 True 都是造假 —— 前者說「查過，不符合」、
    後者說「查過，符合」，而事實是「沒查」。

    抽成純函式的理由（D1 v19.185）：這 5 條的判定原本內嵌在 render 裡，
    只能靠掃字串驗，而字串守衛照抄實作字面 ⇒ 永遠驗不出實作本身錯了
    （例如「💎 非357昂貴區」讀一個不存在的 key 卻恆綠，掃字串完全看不出來）。
    現在測試可以直接餵輸入、驗輸出。

    Args:
        regime: canonical regime（`get_macro_regime()['regime']`）。
        macro_loaded: 總經是否已評估。False → 大盤那條為 None。
        margin_yi: 市場融資餘額（億）。None = 未取得（**不是** 0）。
        health: 個股健康分 0-100。None = 未算。
        price / avg_div: 現價 / 5 年均股利 → 357 分級（None/0 → 未評估）。
        stop_set: 使用者是否已勾「已設停損點」。

    Returns:
        list[tuple[str, bool|None, str]]
    """
    _code357, _ = classify_stock_357_price(price, avg_div)
    return [
        ('🌍 大盤多頭燈號',
         (str(regime) == 'bull') if macro_loaded else None,
         '總經未評估'),
        (f'💰 融資安全(<{MARGIN_BALANCE_WARN_THRESHOLD_YI:.0f}億)',
         None if margin_yi is None else (float(margin_yi) < MARGIN_BALANCE_WARN_THRESHOLD_YI),
         '融資餘額未取得'),
        (f'🏥 個股健康度≥{WINNING_FORMULA_HEALTH_MIN:.0f}',
         None if health is None else (float(health) >= WINNING_FORMULA_HEALTH_MIN),
         '健康度未算'),
        ('💎 非357昂貴區',
         None if _code357 == 'na' else (_code357 in ('cheap', 'fair')),
         '無配息資料,357 不適用'),
        ('✋ 已設停損點', bool(stop_set), ''),
    ]


def render_psy_checklist_section(sid2: str, df2, health2,
                                   _atr2_val=None) -> None:
    """心理檢查 + 勝利方程式 + 禁止操作 3 連 section(SOP 進場檢核 +
    5 條件勝利方程式 + 4 條禁止操作清單)。

    Args:
        sid2: 股票代碼
        df2: 股價 DataFrame
        health2: 個股健康分(0-100)
        _atr2_val: ATR 值(None → 用 price × 7% 估算停損)
    """
    # ── C1 唯一仲裁點：本 section 全部 regime 判斷共用這一次結果 ──────────
    from src.services.allocation_service import get_macro_regime
    _macro_reg = get_macro_regime()
    _macro_loaded = bool(_macro_reg.get('is_loaded'))
    _regime = str(_macro_reg.get('regime') or 'unknown') if _macro_loaded else 'unknown'
    _is_bear = _macro_loaded and _regime in ('bear', 'caution')
    _regime_txt = (_macro_reg.get('traffic_light')
                   or {'bull': '多頭', 'neutral': '震盪', 'caution': '轉守',
                       'bear': '空頭'}.get(_regime, _regime)) if _macro_loaded else '未評估'

    # ══ 操作前心理檢查 + 勝利方程式 ═══════════════════════
    st.markdown('---')
    st.markdown('#### 🧠 操作前必做：心理檢查 + 勝利方程式')

    _mc_cols = st.columns([3, 2])

    _surge_chk = _surge_pct(df2)

    with _mc_cols[0]:
        st.markdown(box_wrapper_open('primary', padding=12), unsafe_allow_html=True)
        st.markdown('**📋 SOP 進場強制檢核表（3 關卡全通過才顯示建議）**')
        _price_chk = float(df2['close'].iloc[-1]) if df2 is not None and not df2.empty else 0
        # _atr2_val 來自 caller;若 None 則用價格 × 7% 估算停損距離
        _atr_eff = _atr2_val if _atr2_val is not None else _price_chk * 0.07
        _stop_chk = round(_price_chk - 1.5 * _atr_eff, 2)
        _q1 = st.checkbox(
            f'① 確認非空頭格局（目前：{_regime_txt}）',
            value=not _is_bear, key=f't2_q1_{sid2}',
            disabled=_is_bear,
        )
        # §1:漲幅算不出來時,checkbox 不預先勾（不是「確認未追高」，是「無法確認」）
        _surge_txt = (f'{_surge_chk:+.1f}%' if _surge_chk is not None
                      else f'資料不足（需 {SOP_SURGE_LOOKBACK_DAYS + 1} 根 K 線）')
        # FIX(職責分離，非放寬安全閘): 原本 value / disabled 都用 abs()，**大漲與大跌一視同仁** ——
        #   一檔近 5 交易日跌 12% 的股票會被鎖住第②關，而使用者看到的理由是「追高」，
        #   完全對不上（跌 12% 的定義上不可能是追高）。這是 category error，不是保守。
        #
        #   改為**單邊判定**：第②關只管它名字所說的那件事 ——「未追高」。
        #   ⚠️ 這**不會**讓急跌失去攔截，因為急跌已經在另一處被攔且理由正確：
        #      同檔 `_ban_items` 的「今日禁止操作」條款（Batch A 已修）會印
        #      「📉 個股近 N 交易日跌幅 X% 超過 4%（急跌，先確認有無基本面利空再進場）」，
        #      走的是更嚴的 SOP_BAN_SURGE_PCT=4.0，比本關的 WARN=5% / HARD=10% 都早觸發。
        #   ⇒ 淨效果是「同一件事只在一個地方講，且講對理由」，不是少講一件事。
        #
        #   §1 三態保留：`_surge_chk is None`（K 線不足）時 value 仍為 False ——
        #   那是「無法確認」，不是「確認未追高」，不可預先勾選。
        _q2 = st.checkbox(
            f'② 確認近{SOP_SURGE_LOOKBACK_DAYS}交易日漲幅未超過 {SOP_SURGE_WARN_PCT:g}%'
            f'（目前：{_surge_txt}）',
            value=(_surge_chk is not None and _surge_chk <= SOP_SURGE_WARN_PCT),
            key=f't2_q2_{sid2}',
            help=f'本關只管追高：漲超過 {SOP_SURGE_WARN_PCT:g}% 不自動勾選，'
                 f'超過 {SOP_SURGE_HARD_PCT:g}% 直接鎖住。\n\n'
                 f'急跌不在本關處理 —— 近{SOP_SURGE_LOOKBACK_DAYS}交易日跌幅超過 '
                 f'{SOP_BAN_SURGE_PCT:g}% 會列入上方「今日禁止操作」，'
                 '並提醒先確認有無基本面利空。',
            disabled=(_surge_chk is not None and _surge_chk > SOP_SURGE_HARD_PCT),
        )
        _q3 = st.checkbox(
            f'③ 確認停損價（跌破 {_stop_chk} 元無條件出場）',
            key=f't2_q3_{sid2}'
        )
        _all_checked = _q1 and _q2 and _q3
        if _all_checked:
            st.success('✅ 心理狀態良好，可以繼續評估操作')
        else:
            st.warning('⚠️ 尚有項目未確認，建議先暫停，避免情緒化操作')
        if not _macro_loaded:
            st.caption('⬜ 第 ① 關的大盤格局尚未評估（先開一次「🌡️ 總經」分頁按更新）'
                       '—— 目前不擋你勾選，但這不等於已確認非空頭。')
        st.markdown('</div>', unsafe_allow_html=True)

    with _mc_cols[1]:
        st.markdown(
            f'<div style="background:#0a1628;border:1px solid {TRAFFIC_GREEN};'
            f'border-radius:10px;padding:12px;">', unsafe_allow_html=True)
        st.markdown(f'**🏆 勝利方程式（5 項至少 {WINNING_FORMULA_MIN_PASS} 項符合）**')
        _wr_margin2 = _read_margin_yi()
        # 💎 357 估值：改由 t2_data 真有的 price / avg_div 現算（原讀不存在的 'val'）
        _t2d_psy = st.session_state.get('t2_data') or {}
        _win_conds = build_winning_conditions(
            regime=_regime, macro_loaded=_macro_loaded,
            margin_yi=_wr_margin2, health=health2,
            price=_t2d_psy.get('price'), avg_div=_t2d_psy.get('avg_div'),
            stop_set=bool(_q3),
        )
        _win_count = sum(1 for _, v, _n in _win_conds if v is True)
        _win_unknown = sum(1 for _, v, _n in _win_conds if v is None)
        for _wn, _wv, _wnote in _win_conds:
            _wc = _TRISTATE_COLOR[_wv]
            _wi = _TRISTATE_ICON[_wv]
            _suffix = (f'<span style="color:{TRAFFIC_NEUTRAL};font-size:11px;">'
                       f'（{_wnote}）</span>' if _wv is None and _wnote else '')
            st.markdown(f'<div style="font-size:12px;color:{_wc};padding:2px 0;">'
                        f'{_wi} {_wn}{_suffix}</div>',
                        unsafe_allow_html=True)
        _pass = _win_count >= WINNING_FORMULA_MIN_PASS
        _unknown_txt = (f'　⬜{_win_unknown} 項未評估' if _win_unknown else '')
        st.markdown(
            f'<div style="margin-top:8px;font-size:13px;font-weight:700;'
            f'color:{TRAFFIC_GREEN if _pass else TRAFFIC_RED};">'
            f'{"🚀 符合 " if _pass else "⛔ 僅符合 "}{_win_count}/5，'
            f'{"可以考慮操作" if _pass else "建議等待"}{_unknown_txt}'
            f'</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 今日禁止操作清單
    st.markdown('#### 🚫 今日禁止操作情況（有任何一項→今天暫停）')
    _ban_items = []
    _unevaluated = []
    # §1:同一個「近 N 交易日漲幅」只算一次(上方 _surge_chk),不再另起第二個基期。
    # FIX(方向性 bug): 原為 `abs(_surge_chk) > SOP_BAN_SURGE_PCT` —— 用絕對值判斷
    #   「追高風險」，等於把**大跌**也算成追高。SOP_BAN_SURGE_PCT = 4.0，所以一檔
    #   近 5 交易日跌 18% 的股票會印出：
    #       「📈 個股近5交易日漲幅 -18.0% 超過4%（追高風險）」
    #   —— 數字是負的、emoji 是上漲箭頭、理由是追高，三者互相矛盾。
    #   修法：正向才算追高；負向另立分支，講「急跌」而不是「追高」。
    #   ⚠️ 門檻值一律不動（改門檻屬行為變更）；負向沿用同一個 SOP_BAN_SURGE_PCT，
    #      只是把單邊判定拆成兩邊，讓文案與方向一致。
    if _surge_chk is None:
        _unevaluated.append(f'近{SOP_SURGE_LOOKBACK_DAYS}交易日漲幅（K 線資料不足）')
    elif _surge_chk > SOP_BAN_SURGE_PCT:
        _ban_items.append(f'📈 個股近{SOP_SURGE_LOOKBACK_DAYS}交易日漲幅 {_surge_chk:+.1f}% '
                          f'超過{SOP_BAN_SURGE_PCT:g}%（追高風險）')
    elif _surge_chk < -SOP_BAN_SURGE_PCT:
        _ban_items.append(f'📉 個股近{SOP_SURGE_LOOKBACK_DAYS}交易日跌幅 {_surge_chk:+.1f}% '
                          f'超過{SOP_BAN_SURGE_PCT:g}%（急跌，先確認有無基本面利空再進場）')
    # `monthly_loss_pct` 全站無寫入點(D1 v19.185 複驗) → 恆為未追蹤。
    # §1:不可因為「沒有虧損紀錄」就宣告「本月沒虧」,列入未評估項誠實揭露。
    _ml = st.session_state.get('monthly_loss_pct')
    if _ml is None:
        _unevaluated.append('本月累計損益（系統未追蹤實際交易績效）')
    elif float(_ml) < SOP_BAN_MONTHLY_LOSS_PCT:
        _ban_items.append(f'📉 本月已虧損 {abs(float(_ml)):.1f}%（情緒操作風險上升）')
    if _wr_margin2 is None:
        _unevaluated.append('市場融資餘額（總經未載入）')
    elif _wr_margin2 > MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:
        _ban_items.append(f'💸 融資 {_wr_margin2:.0f}億 極度過熱（散戶追高期，等待）')
    if not _macro_loaded:
        _unevaluated.append('大盤格局（總經未評估）')
    elif _is_bear:
        _ban_items.append('🔴 大盤空頭格局（禁止做多）')

    if _ban_items:
        for _bi in _ban_items:
            st.markdown(
                border_left_banner(TRAFFIC_RED, f'⛔ {_bi}',
                                   padding_y=7, margin_y=3, bg='#2a0d0d'),
                unsafe_allow_html=True,
            )
    elif _unevaluated:
        # §1:4 條裡有幾條根本沒資料可判時,不能印「無禁止操作情況」——
        # 那會被讀成「4 條都查過且都安全」。
        st.info('✅ 已可判定的條款均未觸發，但下列條款**無資料可判**：'
                + '、'.join(_unevaluated))
    else:
        st.success('✅ 今日無禁止操作情況，可以正常評估')
    if _ban_items and _unevaluated:
        st.caption('⬜ 另有下列條款無資料可判：' + '、'.join(_unevaluated))
