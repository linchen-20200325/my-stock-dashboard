"""mcp_server/server.py — 台股資料 MCP Server(無頭第二前端,v20 首波)。

把已過憲法把關的 L3 service 包成 MCP 工具,讓 Claude Desktop / Cursor 等 MCP client
用對話查台股。本檔為 **orchestrator**(同 app.py L6 / scripts cron)——允許跨層 import
L3 service + L5 fetcher(§8.2 orchestrator 慣例:app.py / update_forward_test_freeze.py
皆如此);本檔只做「組裝 + 序列化」,不寫任何業務邏輯 / 門檻 / 公式(那些留在 L2/L3)。

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
    """自 TWSE BWIBBU 抓全市場本益比 / 名稱 → (pe_map, name_map)。抓不到 → 兩個空 dict。

    **鏡像** scripts/update_forward_test_freeze.py:_build_pe_name_maps —— 兩者皆
    orchestrator、走同一支 L5 `fetch_twse_yield_pe`,確保「MCP 選股 = 畫面 / cron 選股」
    (§8 SSOT)。pe_low 因子缺 pe_map 時 composite 自動不計入、不記 0(§1),不炸整體。
    """
    try:
        from src.ui.tabs.yield_screener import fetch_twse_yield_pe
        _df = fetch_twse_yield_pe()
    except Exception as _e:  # noqa: BLE001 — PE 抓不到 → pe_low 缺料,不炸
        print(f"[mcp_server] TWSE 本益比抓取失敗:{type(_e).__name__}: {_e}", file=sys.stderr)
        return {}, {}
    if _df is None or _df.empty or "代碼" not in _df.columns:
        return {}, {}
    _codes = _df["代碼"].astype(str)
    _pe = dict(zip(_codes, _df["本益比"])) if "本益比" in _df.columns else {}
    _nm = dict(zip(_codes, _df["名稱"].astype(str))) if "名稱" in _df.columns else {}
    return _pe, _nm


def _df_to_records(df) -> list[dict]:
    """DataFrame → JSON-safe list[dict]:NaN→None(§1 缺料留空不填 0)、numpy 純量→py 原生。"""
    _out: list[dict] = []
    for _r in df.to_dict(orient="records"):
        _clean: dict = {}
        for _k, _v in _r.items():
            if _v is None:
                _clean[_k] = None
            elif isinstance(_v, float) and math.isnan(_v):
                _clean[_k] = None          # 缺料因子顯示 null,非 0(避免誤導)
            elif hasattr(_v, "item"):       # numpy int/float/bool 純量
                _clean[_k] = _v.item()
            else:
                _clean[_k] = _v
        _out.append(_clean)
    return _out


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


if __name__ == "__main__":
    mcp.run()   # 預設 stdio transport,供 Claude Desktop / Cursor 掛載
