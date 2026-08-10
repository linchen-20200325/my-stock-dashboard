"""src/ui/tabs/stock_sections/section_op_recommendation.py — 即時操作建議規則引擎 section(v18.406 U4 Phase 2-OpRec).

從 tab_stock.py:1698-1753 抽出。
對齊 docs/TAB_STOCK_AUDIT.md Phase 2 低風險 section batch。

§8.2 layer:L5 UI Tab section helper。

對外 API:
- render_op_recommendation_section(sid2, health2, vcp2, avg_div2, price2, rsi2, cl2, cx2) -> None
"""
from __future__ import annotations

import streamlit as st

from shared.health_thresholds import HEALTH_GRADE_A_MIN
from shared.thresholds import YIELD_MID_DEC
# I2(2026-08-10):大盤 `bias_240` 估算揭露文案 SSOT(L5 → L2,合法下行依賴)。
from src.compute.macro import bias_estimated_note as _bias_est_note
from src.services.app_ai_service import generate_ai_comment
from src.ui.render import STRATEGY_TECHNICAL, strategy_conclusion  # v19.174 去識別化


def render_op_recommendation_section(sid2: str, health2,
                                       vcp2, avg_div2, price2, rsi2,
                                       cl2, cx2) -> None:
    """即時操作建議(規則引擎):4 訊號共振判定 + AI 文案。

    Args:
        sid2: 股票代碼
        health2: 個股健康分(0-100)
        vcp2: VCP dict(`contracting`)
        avg_div2: 5 年平均配息
        price2: 當前股價
        rsi2: RSI 值
        cl2: 合約負債(元)
        cx2: 資本支出(元)
    """
    st.markdown('#### 💡 即時操作建議（規則引擎）')
    # D1 v19.185（C1 接線 · §1 Fail Loud）：原碼 `mkt_info.get('regime','neutral')`
    # 直讀趨勢面**輸入**並在未評估時捏 'neutral'。後果：健康分跌破防禦門檻那天，
    # 總經頁印 🔴 而這張卡照 raw regime 給 4 訊號中的「大盤」一分；總經根本沒開過
    # 的冷啟動則被講成「震盪」。改吃全站唯一仲裁點。
    from src.services.allocation_service import get_macro_regime
    _macro_reg = get_macro_regime()
    _macro_loaded = bool(_macro_reg.get('is_loaded'))
    _reg_op = str(_macro_reg.get('regime') or 'unknown') if _macro_loaded else 'unknown'
    _sig_count = sum([
        1 if health2 >= HEALTH_GRADE_A_MIN else 0,
        1 if _reg_op == 'bull' else 0,
        1 if (vcp2 and vcp2.get('contracting')) else 0,
        1 if (avg_div2 > 0 and price2 > 0
              and price2 <= round(avg_div2 / YIELD_MID_DEC, 1)) else 0,
    ])
    if _reg_op in ('bear', 'caution'):
        # v19.171:移除硬編碼「先降倉至20%以下」—— 個股卡片沒有資格宣告全站持股
        # 水位(那是 get_allocation() 的職責),否則同畫面會出現第二個競爭數字。
        # 這裡只保留「方向性判斷」,實際百分比指回建議持股 SSOT。
        _op_a = (f'大盤空頭格局，{sid2} 無論評分多高，先控制風險、不重壓　'
                 '→ 實際持股見 🎚️ 建議持股油門')
        _op_b = '市場趨勢優先，個股強不等於能賺錢'
    elif _sig_count >= 3:
        _op_a = f'{_sig_count}個訊號共振（健康度+大盤+VCP+估值），可積極進場'
        _op_b = '分批建倉，停損設健康度跌破60'
    elif _sig_count >= 2:
        _op_a = f'{_sig_count}個訊號共振，中性偏多，可小倉試水溫'
        _op_b = '輕倉試探，等待更多確認訊號'
    else:
        _op_a = f'只有{_sig_count}個訊號，條件不足，今日不操作 {sid2}'
        _op_b = '耐心等待，寧可錯過勿強求'
    st.markdown(strategy_conclusion(STRATEGY_TECHNICAL, f'{sid2} 共振訊號 {_sig_count}/4', _op_a, _op_b),
                unsafe_allow_html=True)
    # §1：「大盤」這一分是 4 個訊號之一。未評估時它必然拿不到分 —— 必須說清楚
    # 那是「還沒判斷」而不是「判斷為非多頭」，否則 user 會以為大盤已被評為不利。
    if not _macro_loaded:
        st.caption('⬜ 大盤格局尚未評估（先開一次「🌡️ 總經」分頁按更新）→ 上面 4 個共振訊號中的'
                   '「大盤」這一項**未計分**，不代表大盤不利。')
    # I2:取值**提到 try 之外**（取法一字未改，仍是 `.get('bias_info', {})`，
    # 故 None 值時下方仍會照舊拋 AttributeError → 走原本的降級警語，行為不變）。
    # 這樣做的理由：估算揭露不該被「AI 文案那段出錯」一起吞掉（§1 降級要看得見）。
    _bias_g = st.session_state.get('bias_info', {})
    try:
        _mkt_top_g = st.session_state.get('mkt_info', {})
        _m1b_top_g = st.session_state.get('m1b_m2_info', {})
        _m1b_diff_g = (_m1b_top_g.get('m1b_yoy', 0) - _m1b_top_g.get('m2_yoy', 0)
                       if _m1b_top_g else 0)
        # 取 Tab3 最近分析的外資資料
        _cd_g = st.session_state.get('cl_data', {})
        _inst_g = _cd_g.get('inst', {})
        _fk_g = next((k for k in _inst_g if '外資' in k), None)
        _tk_g = next((k for k in _inst_g if '投信' in k), None)
        _comment_data = {
            'health':      health2,
            'score':       0,  # Tab3 多因子評分(此處無法取得,用0)
            'rsi':         rsi2,
            'vcp_ok':      bool(vcp2 and isinstance(vcp2, dict) and vcp2.get('contracting')),
            'bias_240':    _bias_g.get('bias_240', 0),
            'bias_20':     _bias_g.get('bias_20', 0),
            # I2:整包帶進去只為了讓 generate_ai_comment 能在年線乖離那兩句
            # 加「（估算）」徽章。**不影響任何判定分支**(該函式的 b240 門檻未動);
            # 缺這個 key 時徽章為空字串,輸出與 I2 前逐字元相同。
            'bias_info':   _bias_g,
            # val_label / trend 在原 tab_stock 內走 `if 'xx' in dir()`,但 _357_label2 /
            # _trend_text2 從未在 render_tab_stock 內被定義,故 dir() 永遠 False,實質 ''
            'val_label':   '',
            'trend':       '',
            'cl':          cl2 / 1e8 if cl2 and cl2 > 0 else 0,
            'cx':          cx2 / 1e8 if cx2 and cx2 > 0 else 0,
            'foreign_buy': _inst_g.get(_fk_g, {}).get('net', 0) if _fk_g else 0,
            'trust_buy':   _inst_g.get(_tk_g, {}).get('net', 0) if _tk_g else 0,
            'm1b_diff':    _m1b_diff_g,
        }
        _comment_txt = generate_ai_comment(_comment_data)
        if _comment_txt:
            st.markdown(
                '<div style="background:#0d1117;border:1px solid #30363d;'
                'border-radius:10px;padding:14px;margin-bottom:10px;'
                'font-size:13px;color:#c9d1d9;line-height:1.7;">'
                + _comment_txt.replace(chr(10), '<br>') +
                '</div>', unsafe_allow_html=True)
    except Exception as _ai_err:
        st.warning(f'⚠️ AI 分析暫時無法使用（{type(_ai_err).__name__}），以上為規則引擎建議。')
    # I2:上面那段文案裡的「年線正/負乖離」是**大盤** TWII 的乖離,
    # 而它在 TWII 歷史不足 240 天時是估算值。徽章只有三個字,補一句完整說明。
    # 放在 try/except 之外 —— 揭露不該因為 AI 文案那段失敗就一起消失。
    _op_bias_note = _bias_est_note(_bias_g)
    if _op_bias_note:
        st.caption(_op_bias_note)
