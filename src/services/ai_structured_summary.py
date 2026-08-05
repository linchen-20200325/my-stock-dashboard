"""
ai_structured_summary.py — 共用「白話結構化 AI 摘要」元件

各 Tab 共用：吃該 Tab 已算好的『各章節資料』+『時事新聞』，產出一份
逐章節白話結論 + 時事連結 + 一句話總結 的 prompt，交給呼叫端的 gemini_fn。

設計原則
  - 強制白話：禁專業術語裸用；非用不可時必用括號附超白話解釋。
  - 逐章節：每節給 2~3 句「在看什麼、好還壞、要注意什麼」。
  - 時事：依提供新聞挑相關的講「發生什麼、是好消息還壞消息」；無則老實說沒抓到。
  - 純組字串，不抓資料、不呼叫 AI（由呼叫端傳入的 gemini_fn 執行），
    不被 fetch / calc 反向依賴。
"""
from shared.macro_buckets import SPECS_BY_KEY as _DANGER_SPECS
from src.config import MACRO_ALERT_RULES as _MACRO_ALERT_RULES


# ══════════════════════════════════════════════════════════════════════
# v19.178 AI-SSOT — 「餵給 LLM 的判讀門檻」文案產生器（§3.3 反捏造）
#
# 【修的是什麼】2026-08-06 稽核發現**兩處**組給 Gemini 的總經 context
# （`section_news_ai._ctx` 與 `tab_stock._macro_lines2`）都各自手寫了一套門檻，
# 而且**彼此不同、也都與畫面燈號用的 shared/macro_buckets SSOT 不同**：
#
#     指標      section_news_ai   tab_stock       SSOT(畫面燈號)
#     VIX       >28 / >35         >20 / >30       黃 22 / 紅 30
#     CPI       >3%               >3%             黃 3.5 / 紅 4.0
#     台灣 PMI  <48               <45             黃 50 / 紅 46
#     US10Y     —                 >4% / >5%       黃 4.5 / 紅 5.0
#     BIAS240   >15 / <-10        —               黃 10 / 紅 20
#     ADL       >70 / <30         —               黃 50 / 紅 35
#     外資期貨  <-35000           —               黃 -10000 / 紅 -20000
#
# 後果：系統畫面已亮 🔴、AI 卻依較寬的門檻說「還在安全區」；而且個股頁 AI 與
# 總經頁 AI 對同一個 VIX 值可能講出不同結論。使用者理所當然以為三者同源。
# 這是 §1「錯誤的數字比沒有數字更危險」的變形：**錯誤的門檻比沒有門檻更危險**。
#
# 【為何放這裡】本模組是「各 Tab 共用的 prompt 組裝元件」(L3)，是唯一同時被
# 總經 / 個股 / ETF / 選股各 prompt 建構點 import 的地方。放這裡才有一份真相；
# 放回 shared/macro_buckets(L0) 會讓純常數模組長出文案職責。
# ══════════════════════════════════════════════════════════════════════
def danger_rule_text(key: str) -> str:
    """由 `shared/macro_buckets` 的 DangerSpec 產生「畫面燈號門檻」判讀句。

    值 / 單位 / 小數位 / 方向全部取自 SSOT，**不在 prompt 內寫死任何數字**；
    改門檻只需改 SSOT 一處，所有 prompt 自動跟上。

    刻意寫明「與畫面燈號同一套門檻」，讓 LLM 的敘事與使用者看到的燈號對齊。
    未登錄的 key → KeyError（§1 Fail Loud，不靜默回空字串把門檻吞掉）。
    """
    _s = _DANGER_SPECS[key]
    _u, _d = _s.unit, _s.decimals
    if _s.direction == 'high_bad':
        _body = f'≥{_s.yellow:.{_d}f}{_u} 🟡 警戒、≥{_s.red:.{_d}f}{_u} 🔴 危險'
    elif _s.direction == 'low_bad':
        _body = f'≤{_s.yellow:.{_d}f}{_u} 🟡 警戒、≤{_s.red:.{_d}f}{_u} 🔴 危險'
    else:  # band — 高低兩側皆有危險帶
        _body = (f'≥{_s.yellow:.{_d}f}{_u} 或 ≤{_s.yellow_lo:.{_d}f}{_u} 🟡 警戒；'
                 f'≥{_s.red:.{_d}f}{_u} 或 ≤{_s.red_lo:.{_d}f}{_u} 🔴 危險')
    return f'畫面燈號同一套門檻：{_body}'


def pcr_rule_text() -> str:
    """由 `src/config.MACRO_ALERT_RULES['pcr']` 產生 PCR 判讀句。

    PCR 不在五桶 DangerSpec 內（它是雙向指標），其 SSOT 是總經警示規則表。
    ⚠️ 這裡的門檻是**標準 PCR 比值刻度**（0.5~2.0）；若 caller 手上的值來自
    `li_latest['選PCR']`（已 ×100 的百分比刻度），**必須先換算**再配上本判讀句，
    否則就是 100× 量綱錯（§4.1）—— 見 `shared.signal_thresholds.PCR_PERCENT_SCALE_MIN`。
    """
    _r = next(_x for _x in _MACRO_ALERT_RULES if _x.get('key') == 'pcr')
    return (f"高於 {_r['yellow_above']:.1f} 🟡 偏空情緒、高於 {_r['red_above']:.1f} 🔴 極度恐慌；"
            f"低於 {_r['yellow_below']:.1f} 🟡 樂觀偏高、低於 {_r['red_below']:.1f} 🔴 過度樂觀(頂部訊號)")


# ── 白話硬規格（所有 Tab 共用，確保口吻一致）──────────────────
PLAIN_RULES = """【講話規則 — 一定要遵守】
1. 用「跟完全不懂股票的長輩或朋友聊天解釋」的白話口吻，能講人話就不要拽詞。
2. 嚴禁專業術語裸用。若非用不可（如 殖利率、乖離、KD、折溢價、Sharpe），
   務必馬上用括號附超白話解釋，例：「殖利率（你買進後一年大概能領回幾 % 現金）」。
3. 重點不是堆數字，而是「這代表好還是壞、該開心還是擔心、要注意什麼」。
4. 不要喊「一定要買 / 保證賺 / 必漲 / 快進場」這種話。
5. 全程繁體中文，語氣親切、簡短，不要落落長。"""


def build_structured_summary_prompt(subject_title: str,
                                    sections: list,
                                    news_text: str = None,
                                    overall_question: str = None) -> str:
    """組出「白話 + 逐章節結論 + 時事」的 AI prompt。

    Parameters
    ----------
    subject_title : str
        這份摘要的主題（如 '2330 台積電'、'我的 ETF 組合'、'台股大盤'）。
    sections : list[dict]
        每個元素 {'name': 章節白話名稱, 'data': 已算好的原始數據字串}。
        data 可為空，元件會自動標「這節沒有資料」。
    news_text : str | None
        已抓好的相關新聞（每則一行）；None / 空字串 → 標示沒抓到。
    overall_question : str | None
        「一句話總結」要回答的問題；None 時用通用問法。
    """
    _blocks = []
    _section_names: list[str] = []
    for _i, _s in enumerate(sections, 1):
        _name = (_s.get('name') or f'第{_i}節').strip()
        _data = (str(_s.get('data') or '')).strip() or '（這節目前沒有資料）'
        _blocks.append(f'【第{_i}節：{_name}】\n{_data}')
        _section_names.append(f'第{_i}節：{_name}')
    _data_all = '\n\n'.join(_blocks) if _blocks else '（沒有提供任何章節資料）'
    _n_sections = len(sections)
    _section_list_str = '\n'.join(f'  {i+1}. {n}' for i, n in enumerate(_section_names))

    _news = (news_text or '').strip() or '（目前沒有抓到相關的即時新聞）'
    _overall = (overall_question or
                '這個標的現在整體看起來如何、適合什麼樣的人留意、最該小心什麼。')

    return f"""你是一個很會「把複雜的投資資訊翻成人話」的朋友，正在幫一個\
完全不懂股票的人看懂下面這份「{subject_title}」的資料。

{PLAIN_RULES}

下面是各章節的原始數據（都幫你算好了），請逐節用白話解讀：

{_data_all}

【最近相關新聞 / 時事】
{_news}

【輸出格式 — 用 Markdown，務必逐節對應】
## 🧾 {subject_title}｜白話總整理

⚠️ **硬規定（缺一不可）**：以下 {_n_sections} 個章節**全部都要輸出**，順序與名稱完全照下方清單，
缺資料的章節也必須保留標題，並用一句話說明「為什麼缺資料 / 看不出來」，不准跳過、不准合併：

{_section_list_str}

每節都用這個格式輸出（節名沿用上面的章節名稱）：
### 第N節：<章節名稱>
- 用 2~3 句白話講：這節在看什麼、現在狀況是好是壞、要開心還是擔心、要注意什麼。

全部 {_n_sections} 節講完後，再加兩段：
### 📰 最近發生了什麼事（時事）
- 從上面新聞挑「跟這個標的真的有關」的 1~3 件，白話講「發生什麼、對它是好消息還壞消息」。
  若沒抓到新聞，就老實說「最近沒抓到相關新聞」，不要硬掰。
### ✅ 一句話總結
- 用一句最白話的話總結：{_overall}
- 最後另起一行附小字：「以上只是把資料翻成白話幫你理解，不是投資建議，買賣請自己決定。」"""
