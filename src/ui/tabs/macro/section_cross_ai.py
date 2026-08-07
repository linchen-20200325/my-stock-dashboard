"""src/ui/tabs/macro/section_cross_ai.py — Section 九 跨桶規則決策(B-S8-B 抽出;v19.168 去 AI 標籤)。

🧭 跨桶｜總經規則決策(離線可用,五維度卡:景氣位階 / 配置 / 貨幣 / 美股 / 結論)

⚠️ 本檔為**純 if/else 規則引擎(零 LLM / 免金鑰 / 離線可用)**,非 AI。v19.168 從「AI 綜合」
桶群移出、獨立為「🧭 規則決策」群,讓使用者知道這是最該信任的確定性決策而非黑箱。

closure params(explicit pass):
- tech_s: dict  美股 calc_stats 結果(SOX / NVDA / 大盤 TWII)
- tw_s:   dict  台股 calc_stats 結果(台股加權指數 fallback)

session_state 讀(0 寫):
- macro_info     §八 警示看板原始(_m8_vix/_m8_pmi/_m8_exp/_m8_cpi 來源)
- m1b_m2_info    M1B/M2 YoY + Gap
- bias_info      年線乖離(bias_240)

備註:v19.168 起 §九 emit 自己的 'rules' 桶群 banner;§十一(新聞 AI 裁決,真 Gemini)
改由 section_news_ai 自行 emit 'ai' 桶群 banner(不再共用 §九 的)。
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from src.ui.render.macro_ui_components import section_header


def render_section_cross_ai(tech_s: dict, tw_s: dict) -> None:
    """渲染§九 跨桶規則決策(離線可用,原 tab_macro line 2233-2452)。純規則引擎,非 AI。"""
    # v19.168 桶群組 banner:§九 從「AI 綜合」移出,獨立為「🧭 規則決策」群組。
    # 本 section 是純 if/else 規則引擎(零 LLM),離線可用、免金鑰;掛「AI」標籤會誤導
    # 使用者以為是黑箱,其實是最該信任的確定性決策。§十一 新聞 AI 裁決才 emit 'ai' banner。
    from shared.macro_buckets import bucket_group_banner_html as _bgb
    st.markdown(_bgb('rules', 0), unsafe_allow_html=True)
    st.markdown(section_header('九', '🧭 跨桶｜總經規則決策(離線可用,免 AI)', '🧭'), unsafe_allow_html=True)

    # ── 安全取數 ────────────────────────────────────────────────
    # v18.388:B-4 (1ee60c3) 把 _m8_* 隨 §八 section 抽至 section_mid local,§九 此處
    # 仍 reference → render 期 NameError。重抓 macro_info 以保持與 section_mid:58-64 同源。
    _macro_info_for_s9 = st.session_state.get('macro_info') or {}
    _m8_vix = _macro_info_for_s9.get('vix')
    _m8_pmi = _macro_info_for_s9.get('ism_pmi')
    _m8_exp = _macro_info_for_s9.get('tw_export')
    _m8_cpi = _macro_info_for_s9.get('us_core_cpi')
    # ── v19.183 D2 §1/§3.3:取數一律「缺 → None」,禁止捏造中性/安全預設值 ──────
    # 【修的是什麼】原碼一律寫成 `float(node.get('key', <預設>)) if node else None`。
    # `dict.get` 的預設值**只在 key 不存在時生效**,而這裡真正常見的失敗態是
    # **「node 在、值卻缺」** —— 例如 `macro_snapshot.fetch_us10y_block()` 全敗時
    # 就回 `{'us10y': {'_err': ..., 'current': None}}`,同款寫法在 vix/pmi/cpi 上
    # 只要上游哪天照辦就會中招。中招時的後果全是**假安全**:
    #   ・`current` 缺 → `_ai_vix = 0.0` → 下方 `_ai_vix < 20 and _cpi_ok`
    #     → 卡片印「🟢 美股平穩，降息預期支撐 / 無系統性風險」;
    #   ・`yoy` 缺   → `_ai_cpi = 0.0` → `_cpi_ok` 成立(通膨看起來完全沒問題);
    #   ・`value` 缺 → `_ai_pmi = 50` / `_ai_cli = 100` → 恰好是榮枯線,
    #     「景氣位階」直接拿一個憑空的分水嶺值去分類。
    # 這正是 section_mid v19.170 已修過的同一個坑(該檔註解寫得很清楚),
    # 但 §九 這份 copy 沒跟著修。此處統一收斂。
    def _num(node, key):
        """`node[key]` → float;node 非 dict / key 缺 / 值為 None 或 NaN → None。"""
        if not isinstance(node, dict):
            return None
        _v = node.get(key)
        if _v is None:
            return None
        try:
            _f = float(_v)
        except (TypeError, ValueError):
            return None
        return None if _f != _f else _f   # NaN guard

    _ai_vix  = _num(_m8_vix, 'current')
    _ai_vma  = _num(_m8_vix, 'ma20')
    _ai_is_cli = bool(_m8_pmi.get('is_oecd_cli', False)) if isinstance(_m8_pmi, dict) else False
    _ai_cli  = _num(_m8_pmi, 'value') if _ai_is_cli else None
    _ai_pmi  = _num(_m8_pmi, 'value') if not _ai_is_cli else None
    _ai_exp  = _num(_m8_exp, 'yoy')
    _ai_cpi  = _num(_m8_cpi, 'yoy')
    _ai_mi8  = st.session_state.get('m1b_m2_info') or {}
    _ai_m1b  = _num(_ai_mi8, 'm1b_yoy')
    _ai_m2   = _num(_ai_mi8, 'm2_yoy')
    _ai_gap  = round(_ai_m1b - _ai_m2, 2) if (_ai_m1b is not None and _ai_m2 is not None) else None
    # `st.session_state.get('bias_info', {})` 的預設同樣只在 key 不存在時生效 ——
    # key 在、值為 None 時原碼會 `None.get(...)` → AttributeError 炸掉整個 §九。
    # 改 `or {}` 同時涵蓋兩種缺法;乖離拿不到就是 None,不是 0%(0% 會被下方
    # 結論條列當成「乖離正常」而靜默略過,那是把未知當成已知)。
    _ai_bias = _num(st.session_state.get('bias_info') or {}, 'bias_240')
    _ai_sox  = _num(tech_s.get('費城半導體 SOX'), 'pct')
    _ai_nvda = _num(tech_s.get('輝達 NVDA'), 'pct')
    # 註:原本還有一個 `_ai_twii_pct`,全檔零 reference(死變數)→ v19.183 D2 移除。

    # ── ① 目前總經位階 ──────────────────────────────────────────
    _ai1_lbl, _ai1_clr, _ai1_desc, _ai1_cyc = (
        '資料載入中', '#484f58', '請先按上方「🚀 一鍵更新全部數據」', None)
    _cycle_ref = _ai_cli if _ai_cli is not None else (_ai_pmi if _ai_pmi is not None else None)
    _cycle_exp = (_cycle_ref >= 100.0) if (_ai_cli is not None) else (_cycle_ref >= 50.0 if _cycle_ref is not None else None)
    # ── v19.183 D2:`_cycle_exp is None`(PMI/CLI 都沒抓到)不得走「收縮」分支 ──────
    # 【原缺陷】舊條件寫 `elif not _cycle_exp and ...`。Python 的 `not None` 是 **True**,
    # 所以 PMI 與 CLI **雙雙抓不到**時,這兩條分支照樣成立,卡片印出
    # 「景氣觸底回升 💎（收縮但出口反彈）」/「景氣收縮期 📉（收縮）」——
    # 「收縮」這個斷言背後**一份景氣資料都沒有**(`_cli_str` 當下是空字串,
    # 連指標名都印不出來)。而且它會把 `_ai1_cyc='recovery'` 餵進下方 ⑤ 結論的
    # `_bull_score`,讓一個憑空的判斷再加一分(§1:寧可不講,不可腦補)。
    # 【修法】景氣位階四象限一律要求 `_cycle_exp is not None`;只有出口、沒有
    # PMI/CLI 時走新增的降級分支,誠實說「只有一半的資料」。
    if _ai_exp is not None and _cycle_exp is not None:
        _exp_str = f'台灣出口YoY={_ai_exp:+.1f}%'
        _cli_str = (f'OECD CLI={_ai_cli:.2f}' if _ai_cli is not None else
                    f'台灣 PMI={_ai_pmi:.1f}' if _ai_pmi is not None else '')
        if _cycle_exp and _ai_exp >= 10:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣擴張強勢期 📈', TRAFFIC_RED, 'bull'
            _ai1_desc = f'{_cli_str}（擴張）× {_exp_str}（強勁需求）— 主升段格局，基本面充分支撐'
        elif _cycle_exp and _ai_exp > 0:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣溫和擴張 🟢', TRAFFIC_GREEN, 'bull'
            _ai1_desc = f'{_cli_str}（擴張）× {_exp_str}— 穩步復甦，基本面有撐，持股安全'
        elif _cycle_exp and _ai_exp <= 0:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣高峰震盪 ⚡', TRAFFIC_YELLOW, 'peak'
            _ai1_desc = f'{_cli_str}（微擴張）× {_exp_str}— 高位整理，需求疲軟，留意反轉訊號'
        elif not _cycle_exp and _ai_exp >= 5:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣觸底回升 💎', '#58a6ff', 'recovery'
            _ai1_desc = f'{_cli_str}（收縮但出口反彈）× {_exp_str}— 左側佈局黃金窗口'
        elif not _cycle_exp and _ai_exp < 0:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣收縮期 📉', '#8b949e', 'bear'
            _ai1_desc = f'{_cli_str}（收縮）× {_exp_str}— 多看少做，等待出口數據翻正'
        else:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣整理期 🟡', TRAFFIC_YELLOW, 'neutral'
            _ai1_desc = f'{_cli_str} × {_exp_str}— 方向待確認，保守持股'
    elif _cycle_exp is not None:
        _cli_str = f'OECD CLI={_ai_cli:.2f}' if _ai_cli is not None else f'台灣 PMI={_ai_pmi:.1f}'
        _ai1_lbl = '景氣擴張（出口待確認）' if _cycle_exp else '景氣趨緩（出口待確認）'
        _ai1_clr = TRAFFIC_GREEN if _cycle_exp else TRAFFIC_YELLOW
        _ai1_cyc = 'bull' if _cycle_exp else 'neutral'
        _ai1_desc = f'{_cli_str} — 台灣出口數據載入中'
    elif _ai_exp is not None:
        # v19.183 D2 新增:只有出口、沒有 PMI/CLI。**不宣稱擴張或收縮**
        # （景氣位階的另一半根本沒到位），只把手上有的講清楚，並讓 `_ai1_cyc`
        # 維持 None → 不進下方 ⑤ 的多空計分（未知 ≠ 中性，也 ≠ 偏空）。
        _ai1_lbl, _ai1_clr = '景氣位階僅一半資料', TRAFFIC_YELLOW
        _ai1_desc = (f'台灣出口YoY={_ai_exp:+.1f}%（已取得）× '
                     '台灣 PMI／OECD CLI（未取得）— '
                     '缺景氣面另一半，本卡不判定擴張或收縮。')

    # v19.72 fail-loud（§1/§5）：其餘總經已載入（VIX/M1B/CPI 有值）卻算不出景氣位階 →
    # 代表「外銷訂單 + PMI/CLI」這兩個來源本次抓取失敗，而**非使用者尚未更新**。
    # 不再誤顯示「請點擊更新」（那會讓已更新的人找不到按鈕又困惑），改講實情。
    _macro_loaded = any(v is not None for v in (_ai_vix, _ai_m1b, _ai_cpi))
    # v19.183 D2 補 `_ai_exp is None`:新增的「僅一半資料」分支也讓 `_ai1_cyc`
    # 維持 None,若不加這個條件,下面這段會把它覆蓋成「兩個來源都失敗」——
    # 但出口明明拿到了,那句話就成了新的不實陳述(§1)。
    if _ai1_cyc is None and _macro_loaded and _ai_exp is None:
        _ai1_lbl, _ai1_clr = '景氣位階資料未就緒', TRAFFIC_YELLOW
        # v19.183 D2 正名:`macro_info['tw_export']` 是**財政部海關出口金額年增率**,
        # 不是經濟部外銷訂單(section_mid.py 已於 v19.85 正名,§九 這份 copy 漏改)。
        # 兩者是不同統計、不同發布單位、不同發布時點,寫錯 = 畫面宣稱 ≠ 實際來源。
        _ai1_desc = ('缺「台灣出口 YoY（財政部海關）＋ 台灣 PMI／OECD CLI」——'
                     '這兩個景氣來源本次抓取失敗'
                     '（多為 CIER／財政部第三方鏡像暫時不可用）；其餘總經已載入。'
                     '可於收盤後再按「🚀 一鍵更新全部數據」重試。')

    # ── ② 建議配置 ──────────────────────────────────────────────
    # v19.170 P0-1:原本這裡自行再判一次三環(_r1_ok/_r2_cnt/_r3_cnt),條件與 section_mid
    # 的三環還不一致,又各自輸出「持股0~20%」等字串 —— 正是稽核「6 套矛盾持股建議」之一。
    # 現改為直接顯示建議持股 SSOT 的結論(get_allocation),本卡不再自算任何持股%。
    from src.services.allocation_service import get_allocation
    _ai2_alloc = get_allocation()
    if not _ai2_alloc.is_loaded:
        # §1 Fail Loud:未評估就說未評估,不回填任何預設配置
        _ai2_lbl, _ai2_clr = '⬜ 總經未評估', '#8b949e'
        _ai2_desc = '請先按「🚀 一鍵更新全部數據」；資料未就緒前不提供持股建議。'
    else:
        _ai2_lbl = _ai2_alloc.headline()
        _ai2_hi = _ai2_alloc.final_hi
        # 顏色沿用既有色票,依最終持股上界分段(與油門/主結論卡同一個數,不再各判各的)
        if _ai2_hi <= 20:
            _ai2_clr = TRAFFIC_RED
        elif _ai2_hi <= 50:
            _ai2_clr = TRAFFIC_YELLOW
        elif _ai2_hi <= 80:
            _ai2_clr = TRAFFIC_GREEN
        else:
            _ai2_clr = '#f0e040'
        # desc = 最後一條推導(min(姿態, 天花板) 的算式) + 生效天花板
        _ai2_desc = (_ai2_alloc.drivers[-1] if _ai2_alloc.drivers else '')
        if _ai2_alloc.cap_text:
            _ai2_desc = f'{_ai2_desc}　{_ai2_alloc.cap_text}'

    # ── ③ 目前貨幣流向 ──────────────────────────────────────────
    _ai3_lbl, _ai3_clr, _ai3_desc = '待取得 M1B/M2', '#484f58', '央行貨幣數據載入中'
    if _ai_gap is not None:
        _gap_str = f'M1B={_ai_m1b:.1f}% M2={_ai_m2:.1f}% Gap={_ai_gap:+.2f}%'
        if _ai_gap >= 2.0:
            _ai3_lbl, _ai3_clr = '🔥 熱錢大量流入股市', TRAFFIC_RED
            _ai3_desc = f'{_gap_str} — 黃金交叉大幅擴散，投機資金湧入，活絡貨幣遠超廣義貨幣'
        elif _ai_gap >= 1.0:
            _ai3_lbl, _ai3_clr = '✅ 資金動能轉強', TRAFFIC_GREEN
            _ai3_desc = f'{_gap_str} — 活絡資金超越廣義貨幣，熱錢進場訊號確立，行情可期'
        elif _ai_gap >= 0:
            _ai3_lbl, _ai3_clr = '🟡 資金溫和偏多', TRAFFIC_YELLOW
            _ai3_desc = f'{_gap_str} — M1B微幅領先，資金偏多但動能尚未爆發，需等待 Gap≥1% 確認'
        elif _ai_gap > -1.0:
            _ai3_lbl, _ai3_clr = '⚠️ 資金略偏保守', TRAFFIC_YELLOW
            _ai3_desc = f'{_gap_str} — M2相對偏高，部分資金仍停留在定存，股市吸引力不足'
        else:
            _ai3_lbl, _ai3_clr = '📉 資金明顯外逃', '#8b949e'
            _ai3_desc = f'{_gap_str} — 死亡交叉，資金轉向固定收益，股市失血，謹慎操作'
    elif _ai_m1b is not None:
        _ai3_lbl, _ai3_clr = f'M1B={_ai_m1b:.1f}% M2待取得', '#484f58'
        _ai3_desc = 'M2 數據未就緒，暫無法判斷 Gap'

    # ── ④ 美股動態 ──────────────────────────────────────────────
    _ai4_lbl, _ai4_clr, _ai4_desc = '待取得', '#484f58', 'VIX / CPI 數據載入中'
    if _ai_vix is not None:
        _cpi_ok  = _ai_cpi is None or _ai_cpi < 3.0
        _cpi_wrm = _ai_cpi is not None and 3.0 <= _ai_cpi < 4.0
        _cpi_hot = _ai_cpi is not None and _ai_cpi >= 4.0
        _cpi_s   = f' CPI={_ai_cpi:.1f}%' if _ai_cpi is not None else ''
        # v19.183 D2:`if _ai_sox` 會把「真的 0.0%（平盤）」也當成沒資料而不顯示；
        # 改判 None（沒資料才不印）。同理 `_ai_vma`。
        _sox_s   = f' SOX={_ai_sox:+.1f}%' if _ai_sox is not None else ''
        _vma_s   = f' MA20={_ai_vma:.1f}' if _ai_vma is not None else ''
        # 半導體點火：沒抓到 SOX/NVDA 就是「無法確認點火」，不是「確認沒點火」，
        # 但兩者對本分支的效果相同（不升級成🚀）→ None 直接視為條件不成立即可，
        # 只需避免 `None >= 1.5` 拋 TypeError（v19.183 取數改回 None 後的必要收尾）。
        _sox_fire = (_ai_sox is not None and _ai_sox >= 1.5) or \
                    (_ai_nvda is not None and _ai_nvda >= 2.0)
        if _ai_vix < 20 and _cpi_ok and _sox_fire:
            _ai4_lbl, _ai4_clr = '🚀 美股強勢，科技領漲', TRAFFIC_RED
            _ai4_desc = f'VIX={_ai_vix:.1f}（恐慌低）{_sox_s}（半導體點火）{_cpi_s} — 台股跟漲機率高，可積極佈局科技'
        elif _ai_vix < 20 and _cpi_ok:
            _ai4_lbl, _ai4_clr = '🟢 美股平穩，降息預期支撐', TRAFFIC_GREEN
            _ai4_desc = f'VIX={_ai_vix:.1f}{_vma_s}（安全）{_cpi_s} — 無系統性風險，有利個股選股表現'
        elif _ai_vix < 20 and _cpi_wrm:
            _ai4_lbl, _ai4_clr = '🟡 美股震盪，通膨黏性制約', TRAFFIC_YELLOW
            _ai4_desc = f'VIX={_ai_vix:.1f}尚可但{_cpi_s}偏高 — Fed降息預期受壓，資金轉向謹慎，避免過度加槓桿'
        elif _ai_vix < 20 and _cpi_hot:
            _ai4_lbl, _ai4_clr = '⚠️ 美股承壓，Fed鷹派升溫', TRAFFIC_YELLOW
            _ai4_desc = f'VIX={_ai_vix:.1f}{_cpi_s}超標 — 高利率環境延續，外資提款風險升高，注意匯率走勢'
        elif _ai_vix < 30:
            _ai4_lbl, _ai4_clr = '🟡 美股波動加劇，謹慎操作', TRAFFIC_YELLOW
            _ai4_desc = f'VIX={_ai_vix:.1f}（警戒區間 20~30）{_vma_s} — 市場情緒不確定，控制倉位，勿追高'
        else:
            _ai4_lbl, _ai4_clr = '🔴 美股恐慌模式，流動性危機', TRAFFIC_RED
            _ai4_desc = f'VIX={_ai_vix:.1f}≥30 — 全球流動性急凍，強制防禦，任何技術面買訊均視為誘多'

    # ── ⑤ 結論 ──────────────────────────────────────────────────
    _ai5_pts = []
    if _ai1_cyc == 'bull':
        _ai5_pts.append('景氣擴張有基本面支撐')
    elif _ai1_cyc == 'recovery':
        _ai5_pts.append('景氣觸底，左側佈局機會')
    elif _ai1_cyc == 'peak':
        _ai5_pts.append('高位整理，防範反轉')
    elif _ai1_cyc == 'bear':
        _ai5_pts.append('景氣收縮，防禦優先')
    if _ai_gap is not None:
        if _ai_gap >= 1.0:
            _ai5_pts.append(f'M1B-M2 Gap=+{_ai_gap:.1f}% 資金動能正向共振')
        elif _ai_gap < 0:
            _ai5_pts.append('M1B-M2死亡交叉，貨幣資金外逃')
    if _ai_vix is not None:
        if _ai_vix < 15:
            _ai5_pts.append(f'VIX={_ai_vix:.1f} 極度平靜')
        elif _ai_vix < 20:
            _ai5_pts.append(f'VIX={_ai_vix:.1f} 安全窗口')
        elif _ai_vix >= 30:
            _ai5_pts.append(f'VIX={_ai_vix:.1f} 觸發危機，暫停攻擊')
    # v19.183 D2:`_ai_bias` 取數改為 None-able 後必須加守門（原本它被 `.get(...,0)`
    # 保證是 float，缺值時靜默當成「乖離 0%」而略過整段判讀）。
    if _ai_bias is not None:
        if _ai_bias >= 15:
            _ai5_pts.append(f'年線乖離+{_ai_bias:.1f}% 高估值需嚴設停損')
        elif _ai_bias <= -5:
            _ai5_pts.append(f'年線乖離{_ai_bias:.1f}% 超跌逢低佈局')
    if _ai_exp is not None:
        # v19.183 D2 正名:tw_export = 財政部海關出口年增率,非經濟部外銷訂單。
        if _ai_exp >= 10:
            _ai5_pts.append(f'台灣出口YoY={_ai_exp:+.1f}% 出口強勁')
        elif _ai_exp < -5:
            _ai5_pts.append(f'台灣出口YoY={_ai_exp:+.1f}% 出口衰退警訊')

    if _ai5_pts:
        _ai5_txt = '；'.join(_ai5_pts) + '。'
        _bull_score = (int(_ai1_cyc in ('bull', 'recovery')) +
                       int(_ai_gap is not None and _ai_gap >= 1.0) +
                       int(_ai_vix is not None and _ai_vix < 20) +
                       int(_ai_exp is not None and _ai_exp >= 0))
        _bear_score = (int(_ai1_cyc == 'bear') +
                       int(_ai_gap is not None and _ai_gap < 0) +
                       int(_ai_vix is not None and _ai_vix >= 30))
        if _bull_score >= 3 and _bear_score == 0:
            _ai5_clr, _ai5_icon = TRAFFIC_GREEN, '✅ 整體偏多，積極操作'
        elif _bear_score >= 2 or (_ai_vix is not None and _ai_vix >= 30):
            _ai5_clr, _ai5_icon = TRAFFIC_RED, '🚨 整體偏空，防禦為主'
        elif _bull_score >= 2:
            _ai5_clr, _ai5_icon = TRAFFIC_YELLOW, '🟡 溫和偏多，精選個股'
        else:
            _ai5_clr, _ai5_icon = '#8b949e', '⏸️ 中性觀望，等待訊號'
    else:
        _ai5_txt  = '請先按上方「🚀 一鍵更新全部數據」載入資料後自動生成結論。'
        _ai5_clr, _ai5_icon = '#484f58', '⏳ 等待資料'

    # ── 渲染五維度卡片 ────────────────────────────────────────────
    _aic1, _aic2, _aic3 = st.columns(3)
    def _ai_card(title, label, desc, color):
        return (f'<div style="background:#0d1117;border:1px solid {color}44;border-radius:8px;'
                f'padding:12px;min-height:110px;">'
                f'<div style="font-size:10px;color:#484f58;margin-bottom:4px;">{title}</div>'
                f'<div style="font-size:13px;font-weight:700;color:{color};line-height:1.3;">{label}</div>'
                f'<div style="font-size:11px;color:#8b949e;margin-top:6px;line-height:1.5;">{desc}</div>'
                f'</div>')
    with _aic1:
        st.markdown(_ai_card('① 目前總經位階', _ai1_lbl, _ai1_desc, _ai1_clr), unsafe_allow_html=True)
    with _aic2:
        st.markdown(_ai_card('② 建議配置', _ai2_lbl, _ai2_desc, _ai2_clr), unsafe_allow_html=True)
    with _aic3:
        st.markdown(_ai_card('③ 目前貨幣流向', _ai3_lbl, _ai3_desc, _ai3_clr), unsafe_allow_html=True)

    _aic4, _aic5 = st.columns(2)
    with _aic4:
        st.markdown(_ai_card('④ 美股動態', _ai4_lbl, _ai4_desc, _ai4_clr), unsafe_allow_html=True)
    with _aic5:
        st.markdown(
            f'<div style="background:#0d1117;border:2px solid {_ai5_clr};border-radius:8px;'
            f'padding:12px;min-height:110px;">'
            f'<div style="font-size:10px;color:#484f58;margin-bottom:4px;">⑤ 結論</div>'
            f'<div style="font-size:14px;font-weight:900;color:{_ai5_clr};">{_ai5_icon}</div>'
            f'<div style="font-size:12px;color:#c9d1d9;margin-top:6px;line-height:1.6;">{_ai5_txt}</div>'
            f'</div>', unsafe_allow_html=True)
