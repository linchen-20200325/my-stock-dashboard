"""src/services/app_ai_service.py — app.py 抽出的 L3 AI service。

內容分三塊(各自獨立,共通點是「原本住在 app.py(L6)的 AI 相關邏輯」):

1. `generate_ai_comment`  — Rule-based 個股文字建議(v18.398 P5-B3-β R7)
   純函式決策樹,**不打任何 API**。caller:tab_stock。
2. `gemini_call` + 金鑰池 — 真正的 Gemini HTTP 呼叫(F2,2026-08 自 app.py 下沉)
   caller:app.py / tab_macro / tab_stock / tab_stock_grp / section_news_ai。
3. `build_llm_context`     — 總經量化數據 → LLM prompt 文字(F2 自 app.py 下沉)

⚠️ **本檔 docstring 曾寫「純函式,無 I/O,無 Streamlit」——F2 起不再成立**,故改寫。
(舊敘述留著會變成 §8.2.A.0 規則 5 那種「文件說謊」;讀者依它判斷會判錯。)
現況:第 1 塊純函式;第 2/3 塊有 HTTP / `st.secrets` / `st.session_state` 讀取。

§8.2 layer 對齊:
- L3 Service。L3 **未**被 §8.2 五條硬規則禁止 import streamlit(規則只約束 L0/L1),
  本檔 streamlit 為條件 import,純 .py 環境退化為 no-op(同 EX-CACHE-1 寫法)。
- 與 `src/services/ai_fetcher.py::post_gemini` 的分工:
    ai_fetcher   = **單把 key** 的 HTTP transport(retry / model fallback / 429 退避)
    本檔 gemini_call = **多把 key 的金鑰池策略**(round-robin 起手 + 429/403 換 key)
  兩者行為**不等價**,F2 刻意**不**把 gemini_call 改寫成 post_gemini 的 wrapper:
  post_gemini 對非 gemini-3/preview 模型走 `v1` endpoint、且 model 間會 sleep,
  而 gemini_call 全走 `v1beta`、零 sleep。硬合併 = 動到全站 LLM 路徑的線上行為,
  超出 F2「純搬家」的範圍。要合併請另開提案並先量測。

§3.3 SSOT 對齊:`generate_ai_comment` 內 magic number(85/75/-5/-10/-20/25 等)為
決策樹閾值,單一 consumer,就近 inline 不違憲(類比 _SYSTEMIC_RISK_KEYWORDS pattern)。
"""
from __future__ import annotations

import os
import threading

import requests

# 條件 import streamlit:本檔只讀 `st.secrets`(金鑰池)與 `st.session_state`
# (build_llm_context),不做任何 UI 輸出。純 .py / CLI 環境退化為空 secrets、空 state。
try:
    import streamlit as st
except ImportError:
    class _NoOpST:  # noqa: D106
        secrets: dict = {}
        session_state: dict = {}
    st = _NoOpST()  # noqa

from src.config import TAIWAN_ADVISOR_PERSONA as _PERSONA


# ════════════════════════════════════════════════════════════════
# Gemini 金鑰池（做法 B：多帳號 key 自動換手，分散額度 / 速率限制）
# F2(2026-08)自 app.py:159-248 原封搬入 —— 邏輯一字未改,只換了住址。
# ════════════════════════════════════════════════════════════════
# 讀 GEMINI_API_KEY + GEMINI_API_KEY_2 .. _6（st.secrets 優先，os.environ fallback）。
# gemini_call 以 round-robin 起手 key（不同呼叫/不同 tab 從不同把 key 開始 → 分散負載），
# 任一把遇到 429（速率/額度滿）或 403（無效）時自動換下一把，全部用盡才報錯。
GEMINI_KEY_NAMES = ['GEMINI_API_KEY'] + [f'GEMINI_API_KEY_{_i}' for _i in range(2, 7)]
_gemini_rr = [0]  # round-robin 起手索引（每次呼叫遞增）
# v18.435 WONTFIX-翻案 Bug #3:多 Streamlit session 併發呼叫 gemini_call 時,
# _gemini_rr[0] 的讀+寫非 atomic(兩條指令),會讓 round-robin 跳號 →
# 同一把 hot key 連環打 → 提前 429。加 Lock 序列化 round-robin 增量。
_gemini_rr_lock = threading.Lock()


def get_gemini_api_key() -> str:
    """GEMINI_API_KEY 單一取值口(st.secrets 優先,降級 os.environ)。

    F2:原 `app.py::api_key`(module-level 快照)。`tab_stock` 取它餵
    `analyze_financial_health(api_key, ...)`,原本靠 `from app import api_key`
    (L5→L6 上行 import)。改為函式後 caller 走 L3,且每次重讀(不再是 import 快照)。
    """
    try:
        _v = st.secrets.get('GEMINI_API_KEY', '')
    except Exception:  # noqa: BLE001 — 無 secrets.toml → 走 env(同 app._get_secret)
        _v = ''
    return _v or os.environ.get('GEMINI_API_KEY', '')


def gemini_keys() -> list:
    """收集所有可用 Gemini API key（去重保序）。st.secrets 優先，os.environ fallback。"""
    _keys = []
    for _n in GEMINI_KEY_NAMES:
        try:
            _v = st.secrets.get(_n, '') or os.environ.get(_n, '')
        except Exception:
            _v = os.environ.get(_n, '')
        _v = str(_v or '').strip()
        if _v and _v not in _keys:
            _keys.append(_v)
    _primary = get_gemini_api_key()
    if _primary and _primary not in _keys:
        _keys.append(_primary)
    return _keys


def gemini_call(prompt, max_tokens=2048):
    _keys = gemini_keys()
    if not _keys:
        return '⚠️ 請設定 GEMINI_API_KEY（可另加 GEMINI_API_KEY_2 ~ _6 分散額度）'
    # round-robin 起手：不同呼叫從不同把 key 開始，自然把負載分散到各帳號
    # v18.435 WONTFIX-翻案 Bug #3:Lock 序列化讀+寫,避免併發 session 跳號
    with _gemini_rr_lock:
        _start = _gemini_rr[0] % len(_keys)
        _gemini_rr[0] = (_gemini_rr[0] + 1) % 1_000_000
    _keys = _keys[_start:] + _keys[:_start]
    # 2026-03 有效模型：1.5系列全部退役，2.5為主力
    _models = ['gemini-2.5-flash-lite', 'gemini-2.5-flash',
               'gemini-2.0-flash', 'gemini-2.0-flash-lite']
    for _model in _models:
        # Gemini 2.5 預設開「思考模式」，思考 token 會跟輸出共用 maxOutputTokens 額度
        # → 常導致回覆只生成一半就被截斷。白話摘要不需深度推理，關閉思考（thinkingBudget=0）。
        _gen_cfg = {'temperature': 0.3, 'maxOutputTokens': max_tokens}
        if _model.startswith('gemini-2.5'):
            _gen_cfg['thinkingConfig'] = {'thinkingBudget': 0}
        for _ki, _key in enumerate(_keys):
            try:
                _r = requests.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/{_model}:generateContent',
                    # v19.170:憑證只走 header,不進 query string / URL(避免落入 access log)
                    headers=({'x-goog-api-key': _key} if _key else None),
                    json={'systemInstruction': {'parts': [{'text': _PERSONA}]},
                          'contents': [{'parts': [{'text': prompt}]}],
                          'generationConfig': _gen_cfg},
                    timeout=120
                )
                if _r.status_code == 200:
                    _d = _r.json()
                    _cands = _d.get('candidates', [])
                    if _cands:
                        _parts = _cands[0].get('content', {}).get('parts', [])
                        if _parts and _parts[0].get('text'):
                            return _parts[0]['text']
                    # safety 攔截：換 key 無助益 → 直接換下一個 model
                    if _cands and _cands[0].get('finishReason', '') == 'SAFETY':
                        break
                    continue  # 空回覆 → 試下一把 key
                elif _r.status_code == 400:
                    _err_msg = (_r.json() if _r.text else {}).get('error', {}).get('message', _r.text[:100])
                    print(f'[Gemini/{_model}] 400 Bad Request: {_err_msg}')
                    break  # 設定/prompt 問題，換 key 無用 → 換下一個 model
                elif _r.status_code == 403:
                    print(f'[Gemini/{_model}] 403 第 {_ki+1} 把 key 無效/無權限 → 換下一把')
                    continue  # 換 key
                elif _r.status_code == 404:
                    break  # 此 model 不存在 → 換下一個 model
                elif _r.status_code == 429:
                    print(f'[Gemini/{_model}] 429 第 {_ki+1} 把 key 額度/速率滿 → 換下一把')
                    continue  # 換 key（做法 B 核心：分散到別把帳號）
                else:
                    print(f'[Gemini/{_model}] HTTP {_r.status_code}: {_r.text[:200]}')
                    continue  # 換 key
            except Exception as _ge:
                print(f'[Gemini/{_model}] key#{_ki+1} {type(_ge).__name__}: {_ge}')
                continue  # 換 key
    return ('⚠️ AI 服務暫時無法使用（所有 key 與模型都試過了）—— '
            '請確認各把金鑰額度，或稍後再試')


def build_llm_context(macro_info: dict) -> str:
    """將 session_state 中的量化總經數據格式化為純文字供 LLM 使用。

    v19.87 A~E 批次2:月度指標(出口/PMI/CPI/NDC)距預期最新交易日超過該指標
    自身發布週期者,在該行前綴 `[STALE:Nd]`,防 AI 把過期資料當當期講
    (第八份 review §3.1;對齊 Fund 端既有慣例)。

    F2(2026-08)自 `app.py::_build_llm_context` 原封搬入(L3 職責住在 L6)。

    ⚠️ **本函式仍 0 production caller**(2026-08-07 G1 複驗)。真正在跑的兩處
    總經 prompt 是 `section_news_ai._ctx` 與 `tab_stock._macro_lines2`,兩者的
    內容都是本函式的**超集**(多了法人 / 融資 / PCR / ADL / 期貨 / 韭菜,且門檻
    走 v19.178 `danger_rule_text`)。G1 因此**不**把它們改成呼叫本函式(那會是
    往資訊量少的方向收斂),而是把本函式的時效標記能力抽成共用 SSOT
    (`ai_structured_summary.macro_stale_prefix`)接到那兩處去。
    本函式保留但改吃同一份 SSOT,不再是第二套門檻。是否刪除仍請 user 裁示。

    G1 修掉的兩個自身 bug(0 caller ⇒ 這段從未被實際執行過,錯了也沒人發現):
      1. **門檻 40 天對每個指標都錯**:這些 `date` 是資料歸屬月的月初,而
         月頻資料在被下一期取代前 as_of 年齡本來就會長到 62 天 + 發布延遲
         (美核心 CPI 可達 ~75 天)⇒ 原本 40 天會讓**當期**資料每天都被誤標
         過期。改走 `shared.staleness.monthly_stale_threshold(指標)`。
      2. **date 缺失時 `stale_tag(None)` 回空字串 = 默認新鮮**(§1 反例)。
         改為明確標 `[STALE:資料日期不明]`。
    另外補上 NDC 那行原本漏掉的資料月份(其餘三行本來就有)。
    """
    from src.services.ai_structured_summary import (
        macro_stale_legend as _legend,
        macro_stale_prefix as _prefix,
    )
    # I2(2026-08-10):BIAS240 的「這其實是 MA<N> 不是 MA240」估算標記。
    # 語法與上面 G1 的 `[STALE:Nd] ` 同一套(行首方括號 + 圖例),SSOT 在 L2
    # `src/compute/macro/macro_helpers.py`(L3 → L2 合法下行)。
    from src.compute.macro.macro_helpers import (
        bias_estimated_prompt_prefix as _est_prefix,
        macro_estimated_legend as _est_legend,
    )
    _vix = macro_info.get('vix') or {}
    _exp = macro_info.get('tw_export') or {}
    _pmi = macro_info.get('ism_pmi') or {}
    _cpi = macro_info.get('us_core_cpi') or {}
    _ndc = macro_info.get('ndc_signal') or {}
    _ss  = getattr(st, 'session_state', {}) or {}
    _mi  = _ss.get('m1b_m2_info') or {}
    _bi  = _ss.get('bias_info') or {}

    def _tag(_key: str, _d: dict) -> str:
        # 門檻依指標自身發布週期(L0 SSOT);date 缺失 → 標「資料日期不明」而非放行
        return _prefix(_key, (_d or {}).get('date'))

    _lines = []
    if _vix.get('current'):
        # VIX 是**日頻**,過期語意與月頻不同(不套月頻標記)
        _lines.append(f'• VIX 恐慌指數：{_vix["current"]} (MA20={_vix.get("ma20","N/A")})')
    if _exp.get('yoy') is not None:
        # v19.85 正名:tw_export = 海關出口年增率(非經濟部外銷訂單)
        _lines.append(f'• {_tag("tw_export", _exp)}台灣出口 YoY：'
                      f'{_exp["yoy"]:+.1f}%  ({_exp.get("date","") or "資料月份不明"})')
    if _pmi.get('value') is not None:
        _lines.append(f'• {_tag("ism_pmi", _pmi)}🇹🇼 台灣 PMI：{_pmi["value"]}  '
                      f'({_pmi.get("date","") or "資料月份不明"}，>50 擴張)')
    if _cpi.get('yoy') is not None:
        _lines.append(f'• {_tag("us_core_cpi", _cpi)}美國核心 CPI YoY：'
                      f'{_cpi["yoy"]:+.1f}%  ({_cpi.get("date","") or "資料月份不明"})')
    if _ndc.get('score') is not None:
        _lines.append(f'• {_tag("ndc_signal", _ndc)}NDC 景氣燈號分數：'
                      f'{_ndc["score"]:.0f}/45  ({_ndc.get("date","") or "資料月份不明"})')
    if _mi.get('m1b_yoy') is not None and _mi.get('m2_yoy') is not None:
        _gap = round(float(_mi['m1b_yoy']) - float(_mi['m2_yoy']), 2)
        _lines.append(f'• 台灣 M1B={_mi["m1b_yoy"]:.1f}%  M2={_mi["m2_yoy"]:.1f}%  Gap={_gap:+.2f}%')
    if _bi.get('bias_240') is not None:
        # I2:BIAS240 是**日頻**(不套月頻過期標記),但它有另一種「不是實測值」的
        # 失真 —— TWII 歷史不足 240 天時 `ma240` 其實是 MA<N>。只寫數字的話
        # LLM 會把它當實測年線寫進建議(§1)。行首標記 + 下方圖例補上這件事。
        _lines.append(f'• {_est_prefix(_bi)}台股大盤年線乖離率 BIAS240：'
                      f'{_bi["bias_240"]:+.1f}%')
    if not _lines:
        return '（量化數據載入中，請先按「🚀 一鍵更新全部數據」）'
    _out = '\n'.join(_lines)
    # 有任何一行被標過期 / 標估算 → 附對應圖例;不解釋 `[STALE:Nd]` / `[ESTIMATED:...]`
    # 等於沒標(LLM 不會自己懂)。兩種標記各自獨立判斷,沒命中的那種不加(免雜訊)。
    _lgs = [_lg for _lg in (_legend(_out), _est_legend(_out)) if _lg]
    return '{}\n\n{}'.format('\n'.join(_lgs), _out) if _lgs else _out


def generate_ai_comment(data: dict) -> str:
    """決策樹文字建議產生器(Rule-based,無 AI API)。

    Args:
        data: 含以下 key 的 dict:
            health, rsi, vcp_ok, bias_240, bias_20
            val_label (357評價), trend, cl (合約負債億), cx (資本支出億)
            foreign_buy, trust_buy (三大法人, 億), score (多因子總分)
            m1b_diff (M1B-M2 差距%)
            bias_info (**選填**, I2):整包 `session_state['bias_info']`。
                只用來判斷 `bias_240` 是否為「資料不足 240 天」的估算值,
                並在文案裡加「（估算）」徽章。**不影響任何判定分支**
                （下方 `b240 > 25` / `< -20` 一行未動）;缺這個 key 時
                徽章為空字串,輸出與 I2 前逐字元相同。

    Returns:
        多行建議文字(每行前綴 '• ')
    """
    # I2:估算徽章。純顯示 —— 不參與任何 if 判斷(§-1 本批不改判定)。
    from src.compute.macro.macro_helpers import bias_estimated_badge as _bias_badge_fn
    b240_badge = _bias_badge_fn(data.get('bias_info'))
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
        # v19.170 P0-1:移除硬編碼持股%(原「30%以下」)。本函式產出的文字會餵給
        # AI prompt 與個股卡片,與 🎚️ 建議持股油門(建議持股 SSOT)打架。
        # 敘事保留(資金縮減期該偏保守),數字一律交給 SSOT。
        lines.append('🌐 【景氣環境】M1B-M2為負，目前處於資金縮減期。'
                     '建議偏保守、降低持股比重，優先選擇低位階、高股利標的'
                     '（實際持股水位見 🎚️ 建議持股油門）。')
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
        # v19.174 去識別化：原括號內為人名稱謂，改為方法論描述
        lines.append(f'💰 【外資買進】外資+{fb:.1f}億，跟著大戶走（籌碼面策略）。')
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
        lines.append(f'🔴 【過熱警告】年線正乖離{b240:.0f}%{b240_badge}（>25%），策略1：開始分批減碼。'
                     '建議回收本金，剩餘部位守10週線（≈50MA）。')
    elif b240 < -20:
        lines.append(f'✅ 【低估機會】年線負乖離{abs(b240):.0f}%{b240_badge}（<-20%），'
                     '策略1：左側布局最佳時機，分批進場（2008/2020模式）。')

    if b240 > 25 and b20 > 10:
        lines.append(f'🟠 【分批減碼】年線乖離>25%{b240_badge} + 月線乖離>10%雙重過熱，'
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
