"""src/services/app_ai_service.py — Rule-based 個股文字建議(v18.398 P5-B3-β R7).

對齊 docs/APP_PY_AUDIT.md B3-β 拆檔藍圖:app.py:677-772 `generate_ai_comment`
~96 LOC 純函式決策樹,單一 caller(tab_stock.py:1725)→ 抽至 L3 service。

§8.2 layer 對齊:
- 純函式,無 I/O,無 Streamlit
- 屬 L3 service(決策編排:依數據 dict 產出文案)
- caller 改走 `from src.services.app_ai_service import generate_ai_comment`

§3.3 SSOT 對齊:函式內 magic number(85/75/-5/-10/-20/25 等)為決策樹閾值,
單一 consumer,就近 inline 不違憲(類比 _SYSTEMIC_RISK_KEYWORDS pattern)。
"""
from __future__ import annotations


def generate_ai_comment(data: dict) -> str:
    """決策樹文字建議產生器(Rule-based,無 AI API)。

    Args:
        data: 含以下 key 的 dict:
            health, rsi, vcp_ok, bias_240, bias_20
            val_label (357評價), trend, cl (合約負債億), cx (資本支出億)
            foreign_buy, trust_buy (三大法人, 億), score (多因子總分)
            m1b_diff (M1B-M2 差距%)

    Returns:
        多行建議文字(每行前綴 '• ')
    """
    lines = []
    score  = data.get('score', 0)
    rsi    = data.get('rsi') or 50
    val    = str(data.get('val_label', ''))
    trend  = str(data.get('trend', ''))
    cl     = data.get('cl') or 0
    cx     = data.get('cx') or 0
    fb     = data.get('foreign_buy') or 0
    tb     = data.get('trust_buy') or 0
    vcp_ok = data.get('vcp_ok', False)
    b240   = data.get('bias_240') or 0
    b20    = data.get('bias_20') or 0
    m1b    = data.get('m1b_diff') or 0

    if m1b < 0:
        lines.append('🌐 【景氣環境】M1B-M2為負，目前處於資金縮減期。'
                     '建議維持低持股（30%以下），優先選擇低位階、高股利標的。')
    elif m1b > 2:
        lines.append('🌐 【景氣環境】M1B-M2為正且強勁，資金行情啟動中，可積極持股。')

    fin_msg = []
    if cl > 0:
        fin_msg.append(f'合約負債{cl:.1f}億（流動+非流動合計；含預收款項）')
    if cx > 0:
        fin_msg.append(f'資本支出{cx:.1f}億（大規模擴廠，2-3年後營收爆發可期）')
    if fin_msg:
        lines.append('📊 【財報訊號】' + '；'.join(fin_msg) + '。')

    if score >= 85 and '便宜' in val and '多頭' in trend:
        lines.append('🚀 【強烈買入】評分≥85 + 357便宜價 + 多頭排列。'
                     '建議突破60日箱頂時分批進場，回測紅K低點不破可加碼。')
    elif score >= 75 and '便宜' in val:
        lines.append('✅ 【積極買入】評分≥75且位於357便宜區，可分批布局。')
    elif score >= 75:
        lines.append('✅ 【評分優良】多因子評分≥75，技術面健康，可考慮建立底倉。')

    if fb > 5 and tb > 0:
        lines.append(f'💰 【籌碼共振】外資+{fb:.1f}億 & 投信+{tb:.1f}億，主力共同買進，訊號強烈。')
    elif fb > 5:
        lines.append(f'💰 【外資買進】外資+{fb:.1f}億，跟著大戶走（宏爺策略）。')
    elif fb < -10:
        lines.append(f'⚠️ 【外資賣超】外資-{abs(fb):.1f}億，籌碼面轉弱，建議等待。')

    if vcp_ok:
        lines.append('🎯 【VCP籌碼安定】波幅持續收縮，籌碼集中於強手。'
                     '建議帶量突破高點時以30~50%建立底倉（策略3）。')

    if rsi < 30:
        lines.append(f'📉 RSI={rsi:.0f}（超賣區），短線反彈機率高，可小量試單。')
    elif rsi > 75:
        lines.append(f'📈 RSI={rsi:.0f}（超買區），注意短線回調風險，不宜追高。')

    if b240 > 25:
        lines.append(f'🔴 【過熱警告】年線正乖離{b240:.0f}%（>25%），策略1：開始分批減碼。'
                     '建議回收本金，剩餘部位守10週線（≈50MA）。')
    elif b240 < -20:
        lines.append(f'✅ 【低估機會】年線負乖離{abs(b240):.0f}%（<-20%），'
                     '策略1：左側布局最佳時機，分批進場（2008/2020模式）。')

    if b240 > 25 and b20 > 10:
        lines.append('🟠 【分批減碼】年線乖離>25% + 月線乖離>10%雙重過熱，'
                     '建議先減50%部位，剩餘守5MA停利。')

    if score < 60 and '空頭' in trend:
        lines.append('🛑 【絕對停損警示】多因子評分<60 + 空頭排列，理由消失即出場。'
                     '出清後觀望，等待評分重返60以上再考慮回補。')

    if '便宜' in val:
        lines.append('💎 【357估值】位於7%殖利率線以下（便宜區），策略1認定的必買送分題。')
    elif '昂貴' in val or '超貴' in val:
        lines.append('⚠️ 【357估值】位於3%殖利率線以上（昂貴區），不宜追高，等待回調。')

    if not lines:
        lines.append('⚪ 目前無明顯買賣訊號，建議繼續觀察。')

    return '\n'.join(f'• {_ln}' for _ln in lines)
