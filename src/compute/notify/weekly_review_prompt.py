"""src/compute/notify/weekly_review_prompt.py — 每週組合週報 AI prompt 組字(L2 純函式)。

把「大盤定調事實 + 逐檔體檢事實(vs 基準是否落後)」包成 <Macro>/<Holdings>,請 Gemini
照「先總經定調 → 再逐檔建議」給白話週報。對齊 ai_judgment.py 的絕對約束樣板。

§2.1 Tier-5「synthesis only」/ §1:prompt 硬性要求「只依提供資料、絕對禁止腦補任何數字/
價位/新聞、不喊買賣、附非投資建議聲明」。事實一律由 caller 傳入已算好的字串(§3.3 不另算)。

§8.2 L2:純組字串,無 I/O、無 streamlit、不呼叫 AI(post_gemini 由 orchestrator 執行)。
"""
from __future__ import annotations

# Gemini model fallback(對齊 ai_judgment.AI_JUDGMENT_MODELS SSOT)。
from src.compute.notify.ai_judgment import AI_JUDGMENT_MODELS  # noqa: F401  re-export 供 orchestrator


def build_holding_fact_lines(rows) -> list[str]:
    """逐檔一行客觀事實(來自 get_watchlist_health_rows;缺料的欄略過不腦補)。"""
    out: list[str] = []
    for _r in rows or []:
        _code = str(_r.get("代號", "") or "").strip()
        _kind = str(_r.get("類型", "") or "").strip()
        _light = str(_r.get("燈號", "") or "").strip()
        _bits = [f"{_code} {_kind}".strip()]
        if _light:
            _bits.append(_light)
        _rel = _r.get("相對基準%")
        if _rel is not None:
            _bits.append(f"相對基準{_rel:+g}%")
        _streak = _r.get("連敗季數")
        if _streak:
            _bits.append(f"連敗{_streak}季")
        out.append("｜".join(_b for _b in _bits if _b))
    return out


def build_weekly_review_prompt(macro_lines, holding_rows, *, as_of: str) -> str:
    """組出「先總經定調 → 再逐檔建議」的 AI prompt(只研判餵進去的客觀事實)。

    Args:
        macro_lines:  大盤定調的已算好事實字串 list(如「加權指數 收 X｜年線 Y｜站上年線」)。
        holding_rows: get_watchlist_health_rows 的逐檔 rows。
        as_of:        資料時間標記。
    """
    _macro_block = "\n".join(str(_l) for _l in (macro_lines or []) if str(_l).strip()) \
        or "（大盤資料暫時無法取得）"
    _fact_lines = build_holding_fact_lines(holding_rows)
    _data_block = "\n".join(_fact_lines) if _fact_lines else "（清單無標的或皆無資料）"
    return f"""你是台股資料整理助手。下面 <Macro> 是本週大盤定調、<Holdings> 是使用者持股\
逐檔「vs 基準是否落後」的**已算好客觀事實**(個股比大盤加權指數、ETF 比 0050)。\
請照「先總經定調 → 再逐檔」給白話週報。

## 絕對約束(違反視同錯誤)
1. 只能根據 <Macro>/<Holdings> 內的內容。【絕對禁止】腦補或使用你預訓練知識中的任何數字、價位、新聞。
2. 【絕對禁止】喊「一定買 / 保證賺 / 必漲 / 快進場」,也不給任何具體買賣點或目標價。
3. 全程繁體中文,白話簡短;逐檔理由**一句話**,務必引用資料事實,不要自己編數字。

## 資料時間:{as_of}
<Macro>
{_macro_block}
</Macro>
<Holdings>
{_data_block}
</Holdings>

## 輸出格式(Markdown,不要多餘前言)
📊 **本週組合週報**（僅整理客觀資料,非投資建議）

**大盤定調**：一段白話（依 <Macro> 事實說明整體偏多/偏空/保守,例如站上或跌破年線、近月走勢）。

**逐檔建議**（依 <Holdings> 逐檔一句話：連續落後/雙向弱勢 → 建議檢視是否保留；體質正常 → 續抱觀察；資料不足 → 留意即可）
- 代號:一句話

最後另起一行小字:「以上只是把你的組合資料分類整理,不是投資建議,買賣請自己決定。」"""
