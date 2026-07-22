#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai_qa_service.py — AI 分析師 panel + 問答服務(L3 Service)

三種能力(都讀真實資料、都由分析師討論):
  A) summarize_tab(tab_key, bundle=...)  — 每個 Tab 一鍵「AI 總結本頁」(輕量 lite)
  B) discuss_stock(stock_id)             — 個股一鍵多視角討論(多 agent full)
  C) run_agent(question, ...)            — 自由問答聊天(tool-calling)

核心原則(對齊 CLAUDE.md):
  §1 Fail Loud, Never Fake:資料先由工具/tab 提供真實數字 → 交 LLM 討論;**LLM 只討論不生成數字**;
     缺資料回結構化 error,不 fabricate。
  EX-AI-1(已退役但精神保留):AI 敘述帶 🧬 旗標(L5 渲染);權威數字由 tool/bundle 結果渲染,不從 AI 字串萃取。
  §8.2:本檔 L3 Service(允許 I/O),只 import 既有 public 函式(lazy),不 import streamlit。唯讀。

Stock adapter(v19.121 Phase 1,已對實際簽名校正,evidence: 驗證 agent + 冒煙測試):
  - import 路徑改 src.* 實際包;`calc_atr_stop` 在 src.compute.scoring(非 risk_control)。
  - market_state as_of 用 `timestamp`(無 locked_at)。
  - score 用實際 key(小寫 `vcp_atr_pass`;`fundamental` scoring 未輸出 → 不列,§0 不改既有函式)。
  - financial 無 `ROE(%)`/`as_of`:先用實際欄位 + as_of=period;ROE 需 TTM(§4.1 季vs年),留 Phase 1.5。

可測性:`discuss/summarize_tab/discuss_stock/run_agent` 皆可注入 `gemini_http` 與 `tools` → golden test 離線可跑。
"""

import json
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from shared.staleness import stale_days_threshold  # 頻率感知過期門檻 SSOT(L0)

DEFAULT_MODEL = "gemini-2.5-flash"
_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_INSTRUCTION = (
    "你是「台股 dashboard」的 AI 問答助理。嚴格遵守:\n"
    "1. 只能依『工具回傳的結構化結果』回答;需要數字時一律呼叫工具,**嚴禁自行計算/推估/杜撰數字**。\n"
    "2. 工具回傳 ok=false 或缺資料時,如實說明『哪個來源、為什麼』,不編造(Fail Loud, Never Fake)。\n"
    "3. **開頭第一句必須先下一個明確的方向判斷**,用『偏強 / 中性偏多 / 中性 / 中性偏弱 / 偏弱』這類"
    "清楚的詞總評(讓使用者一眼看出好或不好),**禁止用分數或欄位數字開頭**;之後再 1-2 句講最關鍵"
    "的理由(哪邊強、哪邊弱)。你做的是研究面判讀,不是下單建議。\n"
    "4. 標註來源與時間;見 _stale_days 過期標記要提醒。你只做研究性說明,**不下單**。用繁體中文。"
)


# ============================================================================
# 結果型別
# ============================================================================
@dataclass
class QAResult:
    ok: bool = True
    text: str = ""
    error: Optional[str] = None
    model: str = DEFAULT_MODEL
    tool_calls: list = field(default_factory=list)   # [{"name","args","result"}]


@dataclass
class PanelResult:
    ok: bool = True
    text: str = ""                                   # 最終報告(敘述)
    per_analyst: list = field(default_factory=list)  # [{"role","text"}] = 分析師
    debate: dict = field(default_factory=dict)       # {"bull","bear","verdict"}  full 才有
    risk_review: dict = field(default_factory=dict)  # {"text","data_ok"}          full 才有
    data_bundle: dict = field(default_factory=dict)  # 權威數字(由 UI 渲染)
    model: str = DEFAULT_MODEL
    error: Optional[str] = None


# ============================================================================
# 【ADAPTER 區塊】← Stock 專屬:接既有 public 函式(v19.121 已對實際簽名校正)
# 每個工具回 {"ok":True,"data":{...},"provenance":{...}} 或 {"ok":False,"error":...};失敗 Fail Loud。
# ============================================================================
def _finmind_token() -> Optional[str]:
    return os.environ.get("FINMIND_TOKEN")


def _regime() -> str:
    """回英文 regime {bull,neutral,caution,bear} 供 WEIGHT_TABLES 切權重。

    v19.148 ① 接線:原直接回 load_macro_state 的中文 market_regime → WEIGHT_TABLES(英文 key)
    永遠 fallback neutral(regime 自適應權重從未生效的 bug)。改用 normalize_regime 轉英文。
    """
    try:
        from src.services.macro_state_locker import load_macro_state, normalize_regime
        return normalize_regime((load_macro_state() or {}).get("market_regime"))
    except Exception:
        return "neutral"


def _tool_get_market_state() -> dict:
    try:
        from src.services.macro_state_locker import load_macro_state
    except Exception as e:
        return {"ok": False, "error": f"import macro_state_locker 失敗:{e}"}
    st = load_macro_state()
    if not st:
        return {"ok": False, "error": "macro_state 尚未鎖定(macro_state.json 不存在或為空)"}
    keys = ("market_regime", "systemic_risk_level", "exposure_limit_pct", "Macro_Phase")
    return {"ok": True, "data": {k: st.get(k) for k in keys if k in st},
            "provenance": {"source": "macro_state.json (locked)", "as_of": st.get("timestamp")}}


def _tool_get_stock_score(stock_id: str) -> dict:
    try:
        from src.data.core import StockDataLoader
        from src.compute.scoring import score_single_stock
    except Exception as e:
        return {"ok": False, "error": f"import 失敗:{e}"}
    loader = StockDataLoader()
    df, err, name = loader.get_combined_data(stock_id, days=400)
    if err or df is None or len(df) == 0:
        return {"ok": False, "error": f"個股資料抓取失敗({stock_id}):{err or 'empty'}"}
    rev_df = None
    try:
        rev_df, _ = loader.get_monthly_revenue(stock_id)   # 選配:缺了評分仍可算(基本面因子內部自處理)
    except Exception:
        rev_df = None
    res = score_single_stock(df=df, stock_id=stock_id, stock_name=name, regime=_regime(),
                             revenue_df=rev_df)
    # 實際輸出 key(無 fundamental;vcp_atr_pass 為小寫,evidence: scoring_engine.py:436-452)
    keys = ("total", "grade", "trend", "momentum", "chip", "volume", "risk",
            "momentum_signal", "vcp_atr_pass", "vcp_atr_label", "squeeze_label")
    as_of = str(df["date"].iloc[-1]) if "date" in getattr(df, "columns", []) else None
    return {"ok": True,
            "data": {"stock_id": stock_id, "stock_name": name,
                     **{k: res.get(k) for k in keys if k in res}},
            "provenance": {"source": "FinMind/TWSE/Yahoo (T+1)", "as_of": as_of}}


def _calc_single_quarter_roe(net_inc_k, equity_k):
    """單季 ROE(%) = 單季稅後淨利 ÷ 股東權益 × 100(§4.1:單季 ≠ 年化,標籤須註明「單季」;
    兩者同為千元 → 約分後無量綱)。分母(股東權益)須為正的有限數,否則回 None
    (§1/§4.4:不 silent ÷0、不腦補;淨利可負 → 合法負 ROE = 虧損)。"""
    try:
        ni = float(net_inc_k)
        eq = float(equity_k)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(ni) and math.isfinite(eq)) or eq <= 0:
        return None
    return round(ni / eq * 100, 2)


def _tool_get_financial_health(stock_id: str) -> dict:
    try:
        from src.data.core import fetch_financial_statements
    except Exception as e:
        return {"ok": False, "error": f"import 失敗:{e}"}
    fd = fetch_financial_statements(stock_id, token=_finmind_token())
    if not isinstance(fd, dict) or fd.get("error"):
        return {"ok": False, "error": f"財報抓取失敗({stock_id}):{(fd or {}).get('error', 'unknown')}"}
    # 實際欄位(evidence: data_loader.py:2352-2403)。
    want = ("負債比率(%)", "毛利率(%)", "現金佔總資產(%)", "應收帳款天數", "EPS", "is_finance")
    _data = {"stock_id": stock_id, **{k: fd.get(k) for k in want if k in fd}}
    # v19.123 Phase 1.5:單季 ROE(誠實標籤;年化 TTM 需多季淨利來源,fetcher 只給單季,不硬湊 §1)
    _roe_q = _calc_single_quarter_roe(fd.get("稅後淨利(千)"), fd.get("股東權益(千)"))
    if _roe_q is not None:
        _data["ROE(單季%)"] = _roe_q
    return {"ok": True, "data": _data,
            # cadence="quarterly":季報 as_of=季末,~45d 後才公告 → 過期門檻走季頻(150d)非日頻(7d),
            # 否則當期最新一季會被誤標「已過期100+天」(SSOT: shared/staleness.stale_days_threshold)
            "provenance": {"source": "FinMind 季報 (季後~45d,公告日對齊)",
                           "as_of": fd.get("period"), "cadence": "quarterly"}}


def _tool_get_market_leading(days: int = 7) -> dict:
    try:
        from src.data.macro import build_leading_fast
    except Exception as e:
        return {"ok": False, "error": f"import 失敗:{e}"}
    df = build_leading_fast(days=int(days), token=_finmind_token())
    if df is None or len(df) == 0:
        return {"ok": False, "error": "先行指標抓取失敗(空表)"}
    last = df.iloc[-1].to_dict()
    # 只挑重點欄位(整列 dump 有 16+ 欄雜訊);PCR 實際欄名為「選PCR」(evidence: leading_indicators.py)
    want = ("日期", "外資", "投信", "自營", "選PCR", "韭菜指數", "融資餘額", "前十大留倉", "source")
    data = {str(k): _jsonable(last[k]) for k in want if k in last}
    if not data:
        data = {str(k): _jsonable(v) for k, v in last.items()}   # 欄名若變動 → 退回整列(fail-soft 不漏資料)
    return {"ok": True, "data": data,
            "provenance": {"source": "FinMind/TAIFEX (T+1)", "as_of": str(last.get("日期", ""))}}


def _tool_get_risk_plan(stock_id: str, capital_twd: float = 1_000_000) -> dict:
    try:
        from src.data.core import StockDataLoader
        from src.compute.scoring import calc_atr_stop          # ← 在 scoring,非 risk_control
        from src.compute.risk import RiskController
    except Exception as e:
        return {"ok": False, "error": f"import 失敗:{e}"}
    loader = StockDataLoader()
    df, err, name = loader.get_combined_data(stock_id, days=120)
    if err or df is None or len(df) == 0:
        return {"ok": False, "error": f"個股資料抓取失敗({stock_id}):{err or 'empty'}"}
    entry = float(df["close"].iloc[-1])
    stop = calc_atr_stop(df, entry_price=entry)
    alloc = RiskController(portfolio_value=float(capital_twd), regime=_regime()).position_size(price=entry)
    return {"ok": True,
            "data": {"stock_id": stock_id, "stock_name": name, "entry_price": entry,
                     "stop_loss": stop.get("stop_loss"), "atr": stop.get("atr"),
                     "stop_pct": stop.get("stop_pct"),
                     "position_lot": alloc.get("lots"), "allocated_twd": alloc.get("allocated")},
            "provenance": {"source": "計算自最新 close + ATR",
                           "as_of": str(df["date"].iloc[-1]) if "date" in df.columns else None}}


def _tool_get_etf_quality(etf_id: str) -> dict:
    # 包 L2 compute_etf_quality(自抓 L1:AUM/費用率/配息/beta),同 _tool_get_stock_score lazy-import 模式。
    # v19.129:讓 agent 能查/比較 ETF 品質(user 問「ETF 哪個好」時工具化,非 AI 腦補)。
    try:
        from src.compute.etf import compute_etf_quality, normalize_etf_ticker
    except Exception as e:
        return {"ok": False, "error": f"import 失敗:{e}"}
    ticker = normalize_etf_ticker(etf_id)
    if not ticker:
        return {"ok": False, "error": f"ETF 代碼無效:{etf_id!r}(需 4-6 位數字,如 0050 / 00878)"}
    q = compute_etf_quality(ticker)
    # Fail-Loud:抓取失敗 / 4 因子全缺 → compute_etf_quality 回 stars=None(§1 不假裝有分數)
    if not isinstance(q, dict) or q.get("stars") is None:
        return {"ok": False, "error": f"ETF 品質評分失敗({ticker}):{(q or {}).get('_err', 'unknown')}"}
    keys = ("stars", "score", "weakest", "coverage", "factors")
    return {"ok": True,
            "data": {"etf_id": ticker, **{k: q.get(k) for k in keys if k in q}},
            # 慢變基本面屬性,無單一 as_of(不套過期標記);coverage<1 表部分因子缺,AI 應提醒
            "provenance": {"source": "ETF 品質(AUM規模/費用率/配息穩定度/beta;yfinance+SITCA)", "as_of": None}}


REAL_TOOLS: dict = {
    "get_market_state": _tool_get_market_state,
    "get_stock_score": _tool_get_stock_score,
    "get_financial_health": _tool_get_financial_health,
    "get_market_leading": _tool_get_market_leading,
    "get_risk_plan": _tool_get_risk_plan,
    "get_etf_quality": _tool_get_etf_quality,
}

TOOLS_SCHEMA: list = [
    {"name": "get_market_state", "description": "目前總經/大盤狀態(多空 regime、建議曝險、景氣階段)。",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "get_stock_score", "description": "個股量化評分(總分/等級/各因子)。",
     "parameters": {"type": "object", "properties": {"stock_id": {"type": "string"}}, "required": ["stock_id"]}},
    {"name": "get_financial_health", "description": "個股財務體質(負債比/毛利率/現金佔比/EPS/單季ROE)。",
     "parameters": {"type": "object", "properties": {"stock_id": {"type": "string"}}, "required": ["stock_id"]}},
    {"name": "get_market_leading", "description": "大盤先行/籌碼(法人買賣超、PCR、韭菜指數)。",
     "parameters": {"type": "object", "properties": {"days": {"type": "integer"}}}},
    {"name": "get_risk_plan", "description": "依最新價與 ATR 給停損與倉位。",
     "parameters": {"type": "object", "properties": {"stock_id": {"type": "string"}, "capital_twd": {"type": "number"}},
                    "required": ["stock_id"]}},
    {"name": "get_etf_quality",
     "description": "ETF 品質評分(1-5星/綜合分數[0,1]/最弱因子/涵蓋率;因子=規模AUM、費用率、配息穩定度、beta)。"
                    "比較多檔 ETF 時每檔各呼叫一次。",
     "parameters": {"type": "object", "properties": {"etf_id": {"type": "string"}}, "required": ["etf_id"]}},
]


# ============================================================================
# 分析師 panel 設定(每視角一段 persona)
# ============================================================================
PANELS = {
    "general": [("重點", "你是資深分析師,負責抓出這頁資料的重點與明顯變化。"),
                ("風險", "你是風險分析師,負責指出這頁資料裡的風險與需注意之處。")],
    "stock": [("基本面", "你是基本面分析師,只看估值與獲利(EPS/毛利/負債)。"),
              ("技術籌碼", "你是技術與籌碼分析師,只看動能、法人買賣、融資。"),
              ("風險", "你是風險分析師,只看下檔風險、停損、曝險與資料品質。")],
    "macro": [("總經", "你是總經分析師,依 regime、曝險建議、法人與 PCR 判讀順逆風。")],
}
MODERATOR = ("主持人", "你是主持人,綜合各分析師觀點給平衡結論。")
DEBATE = {"bull": "你是多方研究員,基於下列分析師觀點提出買進理由,但不得杜撰數字。",
          "bear": "你是空方研究員,基於下列分析師觀點提出風險與賣出理由,但不得杜撰數字。",
          "judge": "你是裁判,綜合多空給出 buy/hold/avoid 與一句理由,不新增數字。"}
RISK_PERSONA = "你是風控,檢查資料完整度、曝險與結論一致性,保守為上,不新增數字。"
REPORT_PERSONA = "你是研究撰稿,把上述綜合成 4–6 句結論,標註資料時間,不新增數字。"

TAB_TOOLS = {
    "macro": [("get_market_state", {}), ("get_market_leading", {"days": 7})],
}
TAB_CONTEXT = {"macro": "macro"}


# ============================================================================
# 共用小工具
# ============================================================================
def _jsonable(v):
    try:
        json.dumps(v)
        return v
    except Exception:
        return str(v)


def _json_safe(obj):
    """遞迴把 numpy/pandas scalar、set、Timestamp 等非標準 JSON 型別轉成可序列化物件。
    工具結果 / bundle 送 Gemini(json.dumps)前**必過** —— 否則 numpy bool/int 會炸
    `TypeError: Object of type bool is not JSON serializable`(v19.124 修:個股問答整段死掉)。
    dict/list 遞迴;numpy scalar 走 `.item()` 轉 python 原生;其餘無法序列化者退成 str(不丟資料、不炸)。"""
    if obj is None or type(obj) in (bool, int, float, str):
        return obj
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v) for v in obj]
    _item = getattr(obj, "item", None)          # numpy/pandas scalar → python 原生
    if callable(_item):
        try:
            return _json_safe(_item())
        except Exception:
            pass
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)


def _parts(resp: dict) -> list:
    try:
        return resp["candidates"][0]["content"]["parts"] or []
    except Exception:
        return []


# ── 錯誤訊息金鑰洗白 + Gemini 錯誤友善化(v19.128 修 429 錯誤把 ?key=API_KEY 印到 UI)──
# requests 的 HTTPError str 含完整 URL(含 ?key=<GEMINI_KEY>);直接把 exception 塞進 UI 錯誤字串
# = 金鑰洩漏。任何要渲染給使用者的錯誤都必須先過 _scrub_secrets。
_SECRET_QS_RE = re.compile(r"\b(key|token|api[_-]?key|access[_-]?token)=[^&\s\"'<>]+", re.IGNORECASE)
_GOOGLE_KEY_RE = re.compile(r"AIza[0-9A-Za-z_\-]{10,}")


def _scrub_secrets(s) -> str:
    """移除錯誤訊息可能夾帶的金鑰:URL query 的 key=/token=/api_key= 值 + 裸露的 AIza… 金鑰。"""
    out = _SECRET_QS_RE.sub(lambda m: m.group(1) + "=***", str(s))
    return _GOOGLE_KEY_RE.sub("AIza***", out)


def _fmt_gemini_error(prefix: str, e) -> str:
    """統一 Gemini 呼叫錯誤:先洗白金鑰;429 額度上限給友善提示(而非丟原始 HTTPError)。"""
    msg = _scrub_secrets(f"{type(e).__name__}: {e}")
    if "429" in msg or "Too Many Requests" in msg or "RESOURCE_EXHAUSTED" in msg:
        return f"{prefix}:已達 Gemini 免費額度上限(429 Too Many Requests),請稍候約 30~60 秒再試。"
    return f"{prefix}:{msg}"


def _annotate_staleness(result: dict) -> dict:
    try:
        prov = result.get("provenance") or {}
        as_of = prov.get("as_of")
        if as_of:
            d = datetime.fromisoformat(str(as_of)[:10]).replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - d).days
            # 頻率感知門檻:季報 as_of=季末,季後~45d 才公告,不可用日頻 7d 誤標過期。
            # cadence 由各 tool 於 provenance 宣告(未宣告 → daily 最嚴)。SSOT: shared/staleness.py
            if age > stale_days_threshold(prov.get("cadence", "daily")):
                result["_stale_days"] = age
    except Exception:
        pass
    return result


def _run_tool(tools: dict, name: str, args: dict) -> dict:
    fn = tools.get(name)
    if fn is None:
        return {"ok": False, "error": f"未知工具:{name}"}
    try:
        out = fn(**args) if args else fn()
        result = _annotate_staleness(out if isinstance(out, dict) else {"ok": True, "data": out})
        return _json_safe(result)   # v19.124:送 Gemini(json.dumps)前確保可序列化(numpy bool/int 等)
    except Exception as e:                                   # Fail Loud
        return {"ok": False, "error": _scrub_secrets(f"{name} 失敗:{type(e).__name__}: {e}")}


def _make_default_http(api_key: str, model: str) -> Callable[[dict], dict]:
    """預設 Gemini REST(Stock L3 允許 I/O)。★Fund(L2 禁 requests):請改注入走 infra/llm 的 gemini_http。"""
    def _http(payload: dict) -> dict:
        import requests  # lazy
        r = requests.post(_GEMINI_URL.format(model=model), params={"key": api_key}, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()
    return _http


def _gemini_text(http: Callable[[dict], dict], system: str, user: str) -> str:
    resp = http({"system_instruction": {"parts": [{"text": system}]},
                 "contents": [{"role": "user", "parts": [{"text": user}]}]})
    return "".join(p.get("text", "") for p in _parts(resp) if isinstance(p, dict) and "text" in p).strip()


def _normalize_bundle(bundle: dict) -> dict:
    """接受工具結構(含 ok/data/provenance)或 tab 直接丟的 {名稱:資料},統一成結構化。"""
    out = {}
    for k, v in (bundle or {}).items():
        v = _json_safe(v)   # v19.124:tab 傳的 session_state 資料可能含 numpy/DataFrame → 先轉 JSON-safe
        if isinstance(v, dict) and ("ok" in v or "data" in v or "error" in v):
            out[k] = _annotate_staleness(v)
        else:
            out[k] = {"ok": v is not None,
                      "data": v if isinstance(v, dict) else {"值": v},
                      "provenance": {}}
    return out


def _bundle_brief(bundle: dict, cap: int = 700) -> str:
    lines = []
    for name, r in bundle.items():
        if r.get("ok"):
            prov = r.get("provenance", {})
            data = json.dumps(r.get("data", {}), ensure_ascii=False, default=str)[:cap]
            tag = f"　⚠️過期{r['_stale_days']}d" if r.get("_stale_days") else ""
            lines.append(f"[{name}] as_of={prov.get('as_of')} 來源={prov.get('source')}{tag}: {data}")
        else:
            lines.append(f"[{name}] 資料缺失: {r.get('error')}")
    return "\n".join(lines)


# ============================================================================
# A/B) 分析師 panel:discuss / summarize_tab / discuss_stock
# ============================================================================
def discuss(context: str, bundle: dict, question: Optional[str] = None, *, mode: str = "lite",
            api_key: Optional[str] = None, gemini_http: Optional[Callable[[dict], dict]] = None,
            model: str = DEFAULT_MODEL) -> PanelResult:
    """讓分析師 panel 討論『已備妥的真實資料(bundle)』。mode: lite(單次) / full(多 agent)。"""
    bundle = _normalize_bundle(bundle)
    if not any(r.get("ok") for r in bundle.values()):        # Fail Loud:無真實資料就不討論
        return PanelResult(ok=False, error="無可用資料,無法討論(見各項 error)", model=model, data_bundle=bundle)
    http = gemini_http or _make_default_http(api_key or "", model)
    brief = _bundle_brief(bundle)
    roles = PANELS.get(context, PANELS["general"])
    q = f"\n使用者問題:{question}" if question else ""

    if mode == "lite":
        role_list = "、".join(r[0] for r in roles)
        sys = (f"你要模擬一個分析師小組討論,角色:{role_list}。只依『下列工具資料(真實數字)』討論,"
               "**嚴禁自行計算或杜撰數字**;資料沒有的說『資料未涵蓋』。先每角色一句觀點,再給 3–5 句綜合結論。"
               "標註資料時間。用繁體中文。")
        try:
            text = _gemini_text(http, sys, f"工具資料:\n{brief}{q}")
        except Exception as e:
            return PanelResult(ok=False, error=_fmt_gemini_error("Gemini 失敗", e), model=model, data_bundle=bundle)
        return PanelResult(ok=True, text=text, model=model, data_bundle=bundle)

    # full:「(儀表板資料) → 3 分析師 → 多空辯論 → 風控 → 報告」,無 ingest 抓取
    def _call(system, user):
        return _gemini_text(http, system + " 用繁體中文。", user)
    views = []
    try:
        views = [{"role": role, "text": _call(persona + " 只依提供資料,不得杜撰數字。給你這一角色觀點(3–4 句)。",
                                              f"資料:\n{brief}{q}")} for role, persona in roles]
        vbrief = "\n".join(f"[{v['role']}] {v['text']}" for v in views)
        bull = _call(DEBATE["bull"], f"分析師觀點:\n{vbrief}\n資料:\n{brief}")
        bear = _call(DEBATE["bear"], f"分析師觀點:\n{vbrief}\n資料:\n{brief}")
        verdict = _call(DEBATE["judge"], f"多方:{bull}\n空方:{bear}")
        n_ok = sum(1 for r in bundle.values() if r.get("ok"))
        risk_text = _call(RISK_PERSONA, f"資料完整度:{n_ok}/{len(bundle)};辯論結論:{verdict}\n資料:\n{brief}")
        report = _call(REPORT_PERSONA, f"分析師:\n{vbrief}\n辯論:{verdict}\n風控:{risk_text}\n資料:\n{brief}{q}")
    except Exception as e:
        return PanelResult(ok=False, error=_fmt_gemini_error("Gemini 失敗", e), model=model,
                           data_bundle=bundle, per_analyst=views)
    return PanelResult(ok=True, text=report, per_analyst=views,
                       debate={"bull": bull, "bear": bear, "verdict": verdict},
                       risk_review={"text": risk_text, "data_ok": f"{n_ok}/{len(bundle)}"},
                       model=model, data_bundle=bundle)


def summarize_tab(tab_key: str, *, bundle: Optional[dict] = None, stock_id: Optional[str] = None,
                  context: str = "general", mode: str = "lite", api_key: Optional[str] = None,
                  gemini_http: Optional[Callable[[dict], dict]] = None, tools: Optional[dict] = None) -> PanelResult:
    """每個 Tab 的「AI 總結本頁」。優先用 tab 已載好的 bundle;否則用 TAB_TOOLS 抓;個股頁給 stock_id。"""
    if bundle is not None:
        return discuss(context, bundle, mode=mode, api_key=api_key, gemini_http=gemini_http)
    if stock_id:
        return discuss_stock(stock_id, api_key=api_key, gemini_http=gemini_http, tools=tools, mode="full")
    specs = TAB_TOOLS.get(tab_key)
    if not specs:
        return PanelResult(ok=False, error=f"tab『{tab_key}』未提供 bundle 也未定義 TAB_TOOLS")
    got = _fetch_bundle(specs, tools or REAL_TOOLS)
    return discuss(TAB_CONTEXT.get(tab_key, "general"), got, mode=mode, api_key=api_key, gemini_http=gemini_http)


def discuss_stock(stock_id: str, question: Optional[str] = None, *, mode: str = "full",
                  api_key: Optional[str] = None, gemini_http: Optional[Callable[[dict], dict]] = None,
                  tools: Optional[dict] = None, capital_twd: float = 1_000_000) -> PanelResult:
    """個股一鍵多視角討論。抓評分/財務/風險 → panel 討論(可帶 question)。"""
    specs = [("get_stock_score", {"stock_id": stock_id}),
             ("get_financial_health", {"stock_id": stock_id}),
             ("get_risk_plan", {"stock_id": stock_id, "capital_twd": capital_twd})]
    got = _fetch_bundle(specs, tools or REAL_TOOLS)
    return discuss("stock", got, question, mode=mode, api_key=api_key, gemini_http=gemini_http)


def _fetch_bundle(specs: list, tools: dict) -> dict:
    return {name: _run_tool(tools, name, args) for name, args in specs}


# ============================================================================
# C) 自由問答聊天(tool-calling 迴圈)
# ============================================================================
def _history_to_contents(history: Optional[list], max_turns: int = 8) -> list:
    out = []
    for m in (history or [])[-max_turns:]:
        role = "user" if m.get("role") == "user" else "model"
        if str(m.get("content", "")):
            out.append({"role": role, "parts": [{"text": str(m["content"])}]})
    return out


def run_agent(question: str, history: Optional[list] = None, *, api_key: Optional[str] = None,
              gemini_http: Optional[Callable[[dict], dict]] = None, tools: Optional[dict] = None,
              model: str = DEFAULT_MODEL, max_rounds: int = 4) -> QAResult:
    tools = tools if tools is not None else REAL_TOOLS
    http = gemini_http or _make_default_http(api_key or "", model)
    contents = _history_to_contents(history) + [{"role": "user", "parts": [{"text": question}]}]
    tool_calls: list = []
    for _ in range(max_rounds):
        try:
            resp = http({"system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
                         "contents": contents, "tools": [{"function_declarations": TOOLS_SCHEMA}]})
        except Exception as e:
            return QAResult(ok=False, error=_fmt_gemini_error("Gemini 呼叫失敗", e), model=model, tool_calls=tool_calls)
        parts = _parts(resp)
        fcalls = [p["functionCall"] for p in parts if isinstance(p, dict) and "functionCall" in p]
        if fcalls:
            contents.append({"role": "model", "parts": [{"functionCall": fc} for fc in fcalls]})
            rparts = []
            for fc in fcalls:
                name, args = fc.get("name", ""), (fc.get("args") or {})
                result = _run_tool(tools, name, args)
                tool_calls.append({"name": name, "args": args, "result": result})
                rparts.append({"functionResponse": {"name": name, "response": result}})
            contents.append({"role": "user", "parts": rparts})
            continue
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p).strip()
        return QAResult(ok=True, text=text, model=model, tool_calls=tool_calls)
    return QAResult(ok=True, text="(已達最大工具呼叫輪數;請看下方工具結果。)", model=model, tool_calls=tool_calls)


def make_llm_default_http(api_key, model=DEFAULT_MODEL):
    """對外:取得預設 Gemini http(Stock 用)。Fund 請改用 infra/llm。"""
    return _make_default_http(api_key, model)


# ============================================================================
# 內建 selftest(離線,免金鑰)
# ============================================================================
def _selftest() -> int:
    class _Http:
        def __init__(self, script): self.script, self.calls = list(script), 0
        def __call__(self, payload):
            self.calls += 1
            return self.script.pop(0) if self.script else {"candidates": [{"content": {"parts": [{"text": "…"}]}}]}
    txt = lambda t: {"candidates": [{"content": {"parts": [{"text": t}]}}]}
    fcall = lambda n, a: {"candidates": [{"content": {"parts": [{"functionCall": {"name": n, "args": a}}]}}]}
    tools = {"get_stock_score": lambda stock_id: {"ok": True, "data": {"total": 82, "grade": "A", "stock_id": stock_id},
                                                  "provenance": {"source": "FinMind", "as_of": "2026-07-11"}},
             "get_financial_health": lambda stock_id: {"ok": True, "data": {"毛利率(%)": 55},
                                                       "provenance": {"source": "FinMind"}},
             "get_risk_plan": lambda stock_id, capital_twd=1e6: {"ok": True, "data": {"stop_loss": 800},
                                                                 "provenance": {"source": "calc"}}}

    print("== selftest 1/6: 聊天 tool-calling + 數字只從工具 ==")
    g = _Http([fcall("get_stock_score", {"stock_id": "2330"}), txt("2330 評分 82。")])
    r = run_agent("2330 評分?", api_key="x", gemini_http=g, tools=tools)
    assert r.ok and r.tool_calls[0]["result"]["data"]["total"] == 82 and g.calls == 2
    print("  ok")

    print("== selftest 2/6: 聊天 Fail Loud ==")
    def boom(stock_id): raise RuntimeError("quota")
    r = run_agent("2330?", api_key="x", gemini_http=_Http([fcall("get_stock_score", {"stock_id": "2330"}), txt("")]),
                  tools={"get_stock_score": boom})
    assert r.tool_calls[0]["result"]["ok"] is False and "quota" in r.tool_calls[0]["result"]["error"]
    print("  ok")

    print("== selftest 3/6: panel lite(單次呼叫)==")
    bundle = {"評分": {"ok": True, "data": {"total": 82}, "provenance": {"source": "FinMind", "as_of": "2026-07-11"}}}
    g = _Http([txt("基本面:估值合理。風險:留意回檔。綜合:偏多但控管風險。")])
    p = discuss("stock", bundle, mode="lite", gemini_http=g)
    assert p.ok and p.text and g.calls == 1 and p.data_bundle["評分"]["data"]["total"] == 82
    print("  ok")

    print("== selftest 4/6: panel full(3 分析師→辯論→風控→報告)==")
    g = _Http([txt("基本面"), txt("技術籌碼"), txt("風險"), txt("多方"), txt("空方"),
               txt("hold"), txt("風控OK"), txt("最終報告")])
    p = discuss("stock", bundle, mode="full", gemini_http=g)
    assert p.ok and len(p.per_analyst) == 3 and g.calls == len(PANELS["stock"]) + 5
    assert p.debate.get("verdict") == "hold" and p.risk_review.get("text") == "風控OK" and p.text == "最終報告"
    print("  ok")

    print("== selftest 5/6: panel 無資料 → Fail Loud(不呼叫 LLM)==")
    g = _Http([txt("不該被呼叫")])
    p = discuss("stock", {"評分": {"ok": False, "error": "來源全敗"}}, mode="lite", gemini_http=g)
    assert p.ok is False and g.calls == 0
    print("  ok")

    print("== selftest 6/6: discuss_stock / summarize_tab 用注入工具 ==")
    g = _Http([txt("a"), txt("b"), txt("c"), txt("多"), txt("空"), txt("hold"), txt("風控"), txt("報告")])
    p = discuss_stock("2330", gemini_http=g, tools=tools, mode="full")
    assert p.ok and p.data_bundle["get_stock_score"]["data"]["total"] == 82 and p.text == "報告"
    g2 = _Http([txt("本頁總結")])
    p2 = summarize_tab("任意頁", bundle={"重點": {"ok": True, "data": {"x": 1}, "provenance": {}}}, gemini_http=g2)
    assert p2.ok and p2.text == "本頁總結"
    print("  ok")

    print("\nai_qa_service selftest 全部通過 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
