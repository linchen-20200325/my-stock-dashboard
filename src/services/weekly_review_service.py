"""src/services/weekly_review_service.py — 每週組合週報編排(L3 service)。

串「大盤定調(headless) + 逐檔體檢 + AI 建議」→ 一則 LINE 週報文字。給每週 cron
(`scripts/push_weekly_report.py`)呼叫。§8.2 L3:合法組合 L1 取價 + L3 sibling
(watchlist_health / ai_fetcher)+ L2 prompt。

為何大盤定調用「簡版 headless」而非 `get_macro_state`
------------------------------------------------
`macro_state.json`(完整 6 因子總經)**只由 Streamlit UI 產生、不進 git** → GitHub Actions
cron checkout 全新 repo 時**根本沒有這個檔**。故 cron 端改用**當週即時可算**的大盤定調
(加權指數 vs 年線 + 近月走勢),誠實、永遠可得。完整總經健康分入推播 = Phase 2(headless
刷新 macro_state)。

§1 Fail Loud / AI 是加值非主體:
- 大盤/逐檔取不到 → 誠實標「資料暫時無法取得」,不捏造。
- AI(post_gemini)失敗 / 無金鑰 → **仍送**上面的真實數據摘要(對齊每日推播:AI 缺席只送清單)。
"""
from __future__ import annotations

from src.data.etf import fetch_etf_price
from src.services.watchlist_health_service import (
    get_watchlist_health_rows,
    summarize_laggards,
)
from src.services.ai_fetcher import post_gemini
from src.compute.notify.weekly_review_prompt import (
    AI_JUDGMENT_MODELS,
    build_weekly_review_prompt,
)

#: 大盤定調用的年線窗(交易日)。與個股 config.ANNUAL_MA 同義(240),此處為 cron 端獨立輕量計算。
_ANNUAL_MA_DAYS = 240
_RECENT_WINDOW_DAYS = 20


def _macro_lite_lines() -> list[str]:
    """headless 大盤定調事實(加權指數 收盤 / 年線 站上或跌破 / 近20交易日%)。

    §1:取不到 → 回「資料暫時無法取得」,不捏造。cron 端不依賴 macro_state.json。
    """
    try:
        _df = fetch_etf_price("^TWII", period="2y")
        if _df is None or _df.empty or "Close" not in _df:
            return ["加權指數：資料暫時無法取得"]
        _close = _df["Close"].dropna()
        if _close.empty:
            return ["加權指數：資料暫時無法取得"]
        _last = float(_close.iloc[-1])
        _lines = [f"加權指數 收 {_last:,.0f}"]
        if len(_close) >= _ANNUAL_MA_DAYS:
            _ma = float(_close.tail(_ANNUAL_MA_DAYS).mean())
            _lines.append(f"年線({_ANNUAL_MA_DAYS}日均) {_ma:,.0f}｜"
                          + ("站上年線" if _last >= _ma else "跌破年線"))
        if len(_close) > _RECENT_WINDOW_DAYS:
            _chg = (_last / float(_close.iloc[-(_RECENT_WINDOW_DAYS + 1)]) - 1) * 100
            _lines.append(f"近{_RECENT_WINDOW_DAYS}交易日 {_chg:+.1f}%")
        return _lines
    except Exception as _e:                       # §1 loud log,不炸整份週報
        print(f"[weekly_review] macro-lite 失敗：{type(_e).__name__}: {_e}")
        return ["加權指數：資料暫時無法取得"]


def build_weekly_review(tickers, *, api_key=None, as_of: str = "") -> dict:
    """組本週週報資料 + AI 建議。api_key None/缺 → 不呼叫 AI(仍回真實數據)。"""
    _macro_lines = _macro_lite_lines()
    _rows = get_watchlist_health_rows(tickers)
    _prompt = build_weekly_review_prompt(_macro_lines, _rows, as_of=as_of)

    _ai_text = _ai_err = None
    if api_key:
        _txt, _info = post_gemini(api_key, _prompt, models=AI_JUDGMENT_MODELS)
        if _txt and not str(_txt).startswith("⚠️"):
            _ai_text = _txt
        else:
            _ai_err = _info
    return {
        "macro_lines": _macro_lines,
        "rows": _rows,
        "ai_text": _ai_text,
        "ai_err": _ai_err,
        "prompt": _prompt,
    }


def format_weekly_message(review, *, as_of: str = "") -> str:
    """把週報 dict 組成 LINE 文字。§1:AI 缺席仍送真實數據摘要(大盤 + 逐檔警示)。"""
    _rows = review.get("rows") or []
    _lag = summarize_laggards(_rows)
    _hdr = "📊 本週組合週報" + (f"（{as_of}）" if as_of else "")
    _out = [_hdr, ""]

    _out.append("〔大盤定調〕")
    _out += (review.get("macro_lines") or ["加權指數：資料暫時無法取得"])
    _out.append("")

    _out.append("〔逐檔體檢〕")
    if not _rows:
        _out.append("（清單無標的）")
    elif _lag:
        _out.append(f"⚠️ 亮警示 {len(_lag)}/{len(_rows)} 檔（建議檢視）：")
        for _r in _lag:
            _rel = _r.get("相對基準%")
            _rel_txt = f" 相對基準{_rel:+g}%" if _rel is not None else ""
            _out.append(f"　• {_r.get('代號')}｜{_r.get('燈號')}{_rel_txt}")
    else:
        _out.append(f"✅ {len(_rows)} 檔均無連續落後（體質正常者續抱觀察）")

    _ai = review.get("ai_text")
    if _ai:
        _out += ["", "──", str(_ai).strip()]
    else:
        _out += ["", "（AI 研判本次未產生，以上為真實數據摘要）"]
    _out += ["", "※ 非投資建議，買賣請自行決定。"]
    return "\n".join(_out)
