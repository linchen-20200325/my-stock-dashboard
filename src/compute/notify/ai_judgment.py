"""src/compute/notify/ai_judgment.py — 選股清單「AI 研判」prompt 組字(L2 純函式)。

把當日入選股**已算好的客觀事實**(綜合分 / 均線排列 / RSI / KD / 財報趨勢 / 缺貨 / 籌碼)
包成 <Data> 區塊,請 Gemini 分成 **偏多 / 偏空 / 需觀察** 三類,各附一句白話理由。

§2.1 Tier-5「synthesis only」:prompt 內硬性要求「**只依 Data、絕對禁止腦補任何數字/價位/
新聞、不建議買賣、附非投資建議聲明**」,對齊 `macro_state_locker` 的絕對約束樣板。事實一律
複用推播訊息同源的 L2 formatter(§3.3 不另立第二套演算法)。

§8.2 L2:純組字串,無 I/O、無 streamlit、**不呼叫 AI**(真正的 post_gemini 由 orchestrator
`scripts/push_daily_signals.py` 執行;缺 key / AI 失敗 → orchestrator 略過本段只送清單)。
"""
from __future__ import annotations

from src.compute.notify.signal_message import (
    _num,
    _trend_emoji,
    format_chip_line,
    format_fundamental_trend,
    format_shortage_badge,
    format_technical_line,
)

# Gemini model fallback 清單(對齊 macro_state_locker._default_gemini_call SSOT;
# 2026-03 起 gemini-1.5 全退役,2.5 為主力)。
AI_JUDGMENT_MODELS = [
    "gemini-2.5-flash-lite", "gemini-2.5-flash",
    "gemini-2.0-flash", "gemini-2.0-flash-lite",
]

# 趨勢燈 → 白話(給 AI 判讀用,非顯示)
_TREND_TEXT = {"🟢": "均線多頭排列", "🟡": "未站上均線", "⚪": "均線資料不足"}


def build_fact_lines(picks: list[dict], tech_by_code: dict,
                     trend_by_code: dict | None = None,
                     shortage_by_code: dict | None = None,
                     chip_by_code: dict | None = None) -> list[str]:
    """每檔一行客觀事實字串(與推播訊息**同源**,不另算;缺料的欄自動略過不腦補)。"""
    trend_by_code = trend_by_code or {}
    shortage_by_code = shortage_by_code or {}
    chip_by_code = chip_by_code or {}
    out: list[str] = []
    for _p in picks:
        code = str(_p.get("代碼", "") or "").strip()
        name = str(_p.get("名稱", "") or "").strip()
        snap = tech_by_code.get(code) or {}
        comp = _num(_p.get("綜合分"))
        _bits: list[str] = [f"{code} {name}".strip()]
        _bits.append(f"綜合分{comp:g}" if comp is not None else "綜合分—")
        _bits.append(_TREND_TEXT.get(_trend_emoji(snap), ""))
        _tech = format_technical_line(snap)
        if _tech and _tech != "技術資料不足":
            _bits.append(_tech)
        _fund = format_fundamental_trend(trend_by_code.get(code))
        if _fund:
            _bits.append(_fund)
        _short = format_shortage_badge(shortage_by_code.get(code))
        if _short:
            _bits.append(_short)
        _chip = format_chip_line(chip_by_code.get(code))
        if _chip:
            _bits.append(_chip)
        out.append("｜".join(b for b in _bits if b))
    return out


def build_ai_judgment_prompt(picks: list[dict], tech_by_code: dict, *,
                             as_of: str,
                             trend_by_code: dict | None = None,
                             shortage_by_code: dict | None = None,
                             chip_by_code: dict | None = None,
                             regime: str | None = None) -> str:
    """組出「分 偏多 / 偏空 / 需觀察」的 AI prompt(只研判餵進去的客觀事實)。"""
    fact_lines = build_fact_lines(picks, tech_by_code, trend_by_code,
                                  shortage_by_code, chip_by_code)
    data_block = "\n".join(fact_lines) if fact_lines else "（今日無入選股）"
    _regime = f"\n目前總經 regime:{regime}" if regime else ""
    return f"""你是台股資料整理助手。下面 <Data> 是今天「選股網」綜合分入選股的\
**已算好客觀事實**(綜合分、均線排列、RSI、KD、財報趨勢、缺貨、籌碼),請幫使用者快速分類。

## 絕對約束(違反視同錯誤)
1. 只能根據 <Data> 內的內容判讀。【絕對禁止】腦補或使用你預訓練知識中的任何數字、價位、新聞。
2. 【絕對禁止】喊「一定買 / 保證賺 / 必漲 / 快進場」,也不給任何具體買賣點或目標價。
3. 全程繁體中文;每檔理由**一句話**、白話、簡短,務必引用 Data 內的事實,不要自己編數字。

## 資料時間:{as_of}{_regime}
<Data>
{data_block}
</Data>

## 輸出格式(Markdown,只輸出這三類 + 結尾聲明,不要多餘前言)
🤖 **AI 研判**（僅整理上面客觀資料,非投資建議）

**偏多**（均線多頭排列 / KD偏多 / 財報變好 / 籌碼吸籌 之類偏正向的）
- 代碼 名稱:一句話理由
（若無符合的就寫「今日無明顯偏多」）

**偏空**（未站上均線 / KD偏空 / 財報轉弱 / 籌碼倒貨 之類偏負向的）
- 代碼 名稱:一句話理由
（若無就寫「今日無明顯偏空」）

**需觀察**（訊號互相矛盾 / 資料不足 / 中性的）
- 代碼 名稱:一句話理由
（若無就寫「今日無」）

最後另起一行小字:「以上只是把選股資料分類整理,不是投資建議,買賣請自己決定。」"""
