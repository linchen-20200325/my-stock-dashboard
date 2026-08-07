"""mcp_server/server.py — 台股資料 MCP Server(無頭第二前端,v20 首波)。

把已過憲法把關的 L3 service 包成 MCP 工具,讓 Claude Desktop / Cursor 等 MCP client
用對話查台股。本檔為 **orchestrator**(同 app.py L6 / scripts cron)——允許**往下**跨層
import L3 service + L1 fetcher(§8.2 orchestrator 慣例:app.py / update_forward_test_freeze.py
皆如此);本檔只做「組裝 + 序列化」,不寫任何業務邏輯 / 門檻 / 公式(那些留在 L2/L3)。
⚠️ orchestrator 身分不涵蓋「去 L5 UI 取數」(方向錯,非例外)——E2 2026-08 已把 PE /
名稱 fetcher 從 `src.ui.tabs.yield_screener` 下沉到 L1 `src.data.stock.yield_pe_fetcher`。

架構定位(§8.2):
    Streamlit 網頁 (app.py, L6) ─┐
                                 ├─→ L3 Service ─→ L1 Data(多源 fallback + provenance)
    本 MCP Server (sibling)    ─┘
  現有 L1/L2/L3/UI 全部不碰,純新增 adapter → 零回歸風險。

首波工具(唯讀):
  - screen_stocks:全台股基本面選股綜合排名(= 選股網「開始選股」/ cron 凍結 **同源**
    get_ranked_picks;§8 SSOT 保證三處組裝不漂移)。

§1 fail-loud:選股缺料(季快照未就緒 / 存活池空 / 上游全敗)→ 回 ok=False + 具體 reason,
**不編造清單、不填 0**。工具例外一律轉結構化錯誤回傳(帶 source),不讓 server 崩、也不吞掉。

啟動:python -m mcp_server.server   (stdio 模式,供 Claude Desktop 掛載)
"""
from __future__ import annotations

import datetime as _dt
import math
import sys
from pathlib import Path

# orchestrator:確保可從專案根 import src.*（同 scripts/update_forward_test_freeze.py:27）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastmcp import FastMCP  # noqa: E402 — 須在 sys.path 注入後

_UTC = _dt.timezone.utc

mcp = FastMCP("台股資料台(my-stock-dashboard)")


def _now_utc_iso() -> str:
    """抓取當下 UTC ISO 字串(provenance:回傳資料的 fetched_at)。"""
    return _dt.datetime.now(_UTC).isoformat(timespec="seconds")


def _build_pe_name_maps() -> tuple[dict, dict]:
    """全市場(上市 TWSE + 上櫃 TPEX)本益比 / 名稱 → (pe_map, name_map)。抓不到 → 兩個空 dict。

    走 SSOT `fetch_pe_name_maps`(**L1** `src/data/stock/yield_pe_fetcher.py`;畫面 / 推播 /
    凍結 / MCP 四 orchestrator 同源),確保「MCP 選股 = 畫面 / cron 選股」且上櫃股同樣有
    估值 + 名稱(§8 SSOT)。pe_low 因子缺 pe_map 時 composite 自動不計入、不記 0(§1),不炸整體。

    E2(2026-08)修:原 import `src.ui.tabs.yield_screener`(L5,無條件 import streamlit)
    —— 本 server 是 headless stdio 進程,不該把 streamlit UI 鏈拉進來。
    """
    try:
        from src.data.stock.yield_pe_fetcher import fetch_pe_name_maps
        return fetch_pe_name_maps()
    except Exception as _e:  # noqa: BLE001 — PE 抓不到 → pe_low 缺料,不炸
        print(f"[mcp_server] 本益比抓取失敗:{type(_e).__name__}: {_e}", file=sys.stderr)
        return {}, {}


def _json_safe(obj):
    """遞迴轉 JSON-safe:dict/list 遞迴、NaN→None(§1 缺料留空**不填 0**)、numpy 純量→py 原生。"""
    if isinstance(obj, dict):
        return {_k: _json_safe(_v) for _k, _v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(_v) for _v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if hasattr(obj, "item"):        # numpy int/float/bool 純量 → py 原生
        return obj.item()
    return obj


def _df_to_records(df) -> list[dict]:
    """DataFrame → JSON-safe list[dict](NaN→None、numpy→py;走 _json_safe)。"""
    return [_json_safe(_r) for _r in df.to_dict(orient="records")]


def _screen_stocks_impl(factors, top_n: int) -> dict:
    """screen_stocks 的實作本體(與 MCP 註冊分離 → 可獨立單元測試,不受 decorator 包裝影響)。"""
    from src.services.fundamental_screener_service import (
        SCREEN_ANGLE_LABELS,
        get_ranked_picks,
    )
    _all = list(SCREEN_ANGLE_LABELS.values())   # ['pe_low','eps_high','shortage','rs_leader','trend']
    # 過濾非法 factor;全空 → 用全 5 因子(同畫面 / cron 預設)
    _factors = [f for f in (factors or _all) if f in _all] or _all
    _as_of = _now_utc_iso()
    try:
        _pe, _nm = _build_pe_name_maps()
        # top_n 給大值(≥300)讓 composite 排名穩定,再於下方 head(top_n);同 cron:83-86
        _cands, _note = get_ranked_picks(
            _factors, top_n=max(int(top_n), 300),
            pe_map=_pe, name_map=_nm, auto_fetch=True,
        )
    except Exception as _e:  # noqa: BLE001 — fail-loud:轉結構化錯誤,不崩 server、不吞
        return {
            "ok": False, "as_of": _as_of, "factors": _factors,
            "error": f"{type(_e).__name__}: {_e}",
            "source": "fundamental_screener_service.get_ranked_picks",
        }
    if _cands is None or _cands.empty or "代碼" not in _cands.columns:
        return {
            "ok": False, "as_of": _as_of, "factors": _factors, "count": 0,
            "note": _note or "綜合排名為空(季快照未就緒 / 存活池空)。", "picks": [],
        }
    _picks = _df_to_records(_cands.head(int(top_n)))
    return {
        "ok": True, "as_of": _as_of, "factors": _factors,
        "count": len(_picks), "note": _note, "picks": _picks,
    }


@mcp.tool
def screen_stocks(factors: list[str] | None = None, top_n: int = 30) -> dict:
    """全台股基本面選股綜合排名(= 選股網「🎯 開始選股」同源)。

    先過「基本面四項全過」存活池,再依所選【因子】的百分位綜合分排序,回綜合分前 N 名。
    這與網頁選股網、每月自動凍結(前進式驗證)走的是**同一支** get_ranked_picks(數字一致)。

    Args:
        factors: 選股因子子集,任選:
                 'pe_low'(低估值/本益比)、'eps_high'(高 EPS)、'shortage'(缺貨動能)、
                 'rs_leader'(抗跌 RS 相對強度)、'trend'(跨季轉強)。
                 留空 = 全 5 因子(同畫面預設)。
        top_n:   回傳綜合分前 N 名(預設 30)。

    Returns:
        {ok, as_of(UTC 抓取時間), factors, count, note, picks:[{代碼,名稱,綜合分,各因子分}]}。
        缺料因子在 picks 內為 null(非 0)。季快照未就緒 / 存活池空 → ok=False + reason,
        **不編造清單**(§1 fail-loud)。
    """
    return _screen_stocks_impl(factors, top_n)


# ════════════════════════════════════════════════════════════════════
# 第二波工具(v20-MCP W2):前進式驗證對帳 + 個股體質(免 AI)
# ════════════════════════════════════════════════════════════════════

def _forward_test_reconcile_impl() -> dict:
    """forward_test_reconcile 實作本體(與 MCP 註冊分離,便於單元測試)。"""
    from src.services.forward_test_service import reconcile_all
    _as_of = _now_utc_iso()
    try:
        _per_cohort, _overall = reconcile_all()
    except Exception as _e:  # noqa: BLE001 — fail-loud:轉結構化錯誤,不崩 server
        return {"ok": False, "as_of": _as_of,
                "error": f"{type(_e).__name__}: {_e}",
                "source": "forward_test_service.reconcile_all"}
    _cohorts = (_df_to_records(_per_cohort)
                if _per_cohort is not None and not _per_cohort.empty else [])
    return {"ok": True, "as_of": _as_of,
            "overall": _json_safe(dict(_overall or {})), "cohorts": _cohorts}


@mcp.tool
def forward_test_reconcile() -> dict:
    """前進式驗證對帳:凍結過的選股清單,事後用真實現價對帳 vs 0050(零 lookahead)。

    讀「本地 git 追蹤 parquet ∪ Google Sheet」的歷史凍結選股 → 抓現價 + 0050 基準 →
    逐 cohort(凍結批次)計算實際報酬 vs 0050。這是「這套選股實際贏不贏大盤」的誠實計分。

    Returns:
        {ok, as_of, overall(整體統計/含 note), cohorts:[每個凍結批次的對帳列]}。
        尚無凍結紀錄 → ok=True、cohorts 空、overall.note 說明「收集中」(§1 不偽造績效)。
    """
    return _forward_test_reconcile_impl()


def _stock_health_impl(stock_id) -> dict:
    """stock_health 實作本體(與 MCP 註冊分離,便於單元測試)。"""
    from src.data.core.financial_statements_fetcher import fetch_financial_statements
    from src.services.financial_health_engine import (
        analyze_financial_health,
        no_ai_overall_verdict,
    )
    _sid = str(stock_id or "").strip()
    _as_of = _now_utc_iso()
    if not _sid:
        return {"ok": False, "as_of": _as_of, "error": "stock_id 為空"}
    try:
        _fin = fetch_financial_statements(_sid)
    except Exception as _e:  # noqa: BLE001 — fail-loud
        return {"ok": False, "as_of": _as_of, "stock_id": _sid,
                "error": f"{type(_e).__name__}: {_e}",
                "source": "fetch_financial_statements"}
    # §1 關鍵:財報缺料 → **不呼叫引擎、不編造評級**(否則缺料被當 N/A 會誤產高分,
    # 見 headless smoke:error fin_data 竟回 B+)。直接回 fail-loud 說明。
    if not _fin or _fin.get("error"):
        return {"ok": False, "as_of": _as_of, "stock_id": _sid,
                "error": (_fin or {}).get("error", "財報資料為空"),
                "source": "fetch_financial_statements"}
    # 空 api_key → analyze_financial_health 純規則計算,不呼叫 Gemini(免金鑰)
    _fh = analyze_financial_health("", _sid, _fin)
    _v = no_ai_overall_verdict(_fin, _fh)
    return {
        "ok": True, "as_of": _as_of, "stock_id": _sid,
        "grade": _v.get("grade"),
        "score_pct": _v.get("score_pct"),
        "headline": _v.get("headline"),
        "comment": _v.get("comment"),
        "pass_items": _v.get("pass_items"),
        "fail_items": _v.get("fail_items"),
        "business_model_dna": _fh.get("business_model_dna"),
    }


@mcp.tool
def stock_health(stock_id: str) -> dict:
    """個股「財報體檢」總評(純規則、免 AI 金鑰)。

    v19.174 去識別化:原標題帶稱謂,改為純功能描述(MCP tool docstring 會被下游 LLM 讀到)。

    抓最新一季財報 → 6 大模組(存活/營運/獲利/財務結構/償債/進階診斷)純數學計算 →
    綜合評級 A+/A/B+/C/F + 生死指標通過/警示清單。與網頁「個股 → 財報體檢」同一引擎。

    Args:
        stock_id: 台股代碼(如 "2330")。

    Returns:
        {ok, as_of, stock_id, grade, score_pct, headline, comment, pass_items,
         fail_items, business_model_dna}。
        財報抓不到 / 為空 → ok=False + error,**不編造體質評級**(§1 fail-loud)。
    """
    return _stock_health_impl(stock_id)


if __name__ == "__main__":
    mcp.run()   # 預設 stdio transport,供 Claude Desktop / Cursor 掛載
