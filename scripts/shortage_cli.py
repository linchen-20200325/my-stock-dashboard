#!/usr/bin/env python3
"""scripts/shortage_cli.py — 缺貨 / 供不應求選股 單機 CLI（v19.67）。

跟網頁「選股網 → 🔥 缺貨選股」用【完全相同】的 L1 抓取器 + L2 計分函式，
不重寫任何公式 / 門檻（SSOT）→ 單機與網頁算出的分數保證一致。

差異只在「介面」：這支吃命令列的股號、印純文字報告；網頁吃基本面存活池、畫表格。

用法（需先設 FinMind token；且在 repo 根目錄執行才 import 得到 src.*）：
    export FINMIND_TOKEN=你的token
    python scripts/shortage_cli.py 2330 2317 1590
    python scripts/shortage_cli.py --file watchlist.txt      # 檔案每行一個股號
    python scripts/shortage_cli.py 2330 --json               # 機器可讀 JSON

計分（與 dashboard 同一套，滿分 100）：
  ① 合約負債 35  ② 毛利率 25  ③ 存貨天數(近4季年化) 20  ④ 月營收 YoY 20
  → 🟥 強缺貨(≥65) / 🟧 中度(40–64) / ⬜ 不明顯(<40)；金融股(28/58) 排除。

§8.2：本檔屬 scripts/ 維運 CLI，只做 I/O + 呼叫既有 L1/L2，無自有計算邏輯。
§1：抓不到 → 顯式標「資料不足 / 無科目」，不補 0 造假。
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import sys

# repo 根目錄上 path（讓 `python scripts/shortage_cli.py` 從任何地方都 import 得到 src.*）
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# 靜音 streamlit「No runtime found」cache 警告（CLI 無 streamlit runtime，屬正常）
logging.getLogger("streamlit").setLevel(logging.ERROR)

from src.compute.health.monthly_revenue_calc import compute_yoy_mom  # noqa: E402
from src.compute.screener.shortage_screener import (  # noqa: E402
    ShortageScore,
    rank_shortage,
)
from src.data.stock.monthly_revenue_fetcher import fetch_monthly_revenue  # noqa: E402
from src.data.stock.quarterly_financials_fetcher import (  # noqa: E402
    fetch_quarterly_shortage_frame,
)


def _is_finance(stock_id: str) -> bool:
    """台股金融族群代碼前綴（28/58）→ 缺貨模型不適用。與 L3 service 同規則。"""
    return str(stock_id).startswith(("28", "58"))


def build_stock_input(stock_id: str) -> dict:
    """抓齊單股資料 → 組 L2 `score_shortage` 輸入 dict（與 L3 `_score_pairs` 同流程）。

    合約負債/毛利/存貨 ← fetch_quarterly_shortage_frame（單股）；
    月營收 YoY ← fetch_monthly_revenue（單股）→ compute_yoy_mom（自算，不信任 FinMind %）。
    """
    sid = str(stock_id).strip()
    # 金融股(28/58)不適用本模型 → 不浪費 FinMind 額度抓（score_shortage 會先判 is_finance）
    if _is_finance(sid):
        return {"stock_id": sid, "name": "", "is_finance": True,
                "quarters": [], "revenue_yoy_last3": []}
    _frame = fetch_quarterly_shortage_frame(sid)
    _mrev = fetch_monthly_revenue(sid, months=18)
    _yoy3 = (compute_yoy_mom(_mrev).get("yoy_last3", [])
             if _mrev is not None and not _mrev.empty else [])
    return {
        "stock_id": sid,
        "name": "",
        "is_finance": False,
        "quarters": _frame,
        "revenue_yoy_last3": _yoy3,
    }


# ── 報告格式化（純函式，可測）─────────────────────────────────
def _fmt_pct(v) -> str:
    return f"{v:+.1f}%" if isinstance(v, (int, float)) else "—"


def _fmt_days(v) -> str:
    return f"{v:.0f}天" if isinstance(v, (int, float)) else "—"


def _fmt_gm(v) -> str:
    return f"{v:.1f}%" if isinstance(v, (int, float)) else "—"


def format_score_report(s: ShortageScore) -> str:
    """單股 ShortageScore → 純文字報告。"""
    _head = f"{s.tier_icon} {s.stock_id} {s.name}".strip()
    if not s.c1_contract_liab and not s.c2_gross_margin and \
            not s.c3_inventory_days and not s.c4_revenue_yoy and s.total == 0.0 \
            and s.tier in ("不適用", "資料不足"):
        return f"{_head}\n  {s.tier}：{s.reason_text}"

    m = s.metrics or {}
    lines = [
        f"{_head}",
        f"  綜合總分：{s.total:.0f} / 100   訊號評級：{s.tier_icon} {s.tier}"
        + ("   ⚠️降級(無合約負債科目)" if s.cl_na else ""),
        f"  ① 合約負債 {s.c1_contract_liab:>4.0f}/35   "
        f"YoY {_fmt_pct(m.get('cl_yoy'))} / QoQ {_fmt_pct(m.get('cl_qoq'))}",
        f"  ② 毛利率   {s.c2_gross_margin:>4.0f}/25   "
        f"最新 {_fmt_gm(m.get('gm_t'))}（上季 {_fmt_gm(m.get('gm_t1'))} / 去年同季 {_fmt_gm(m.get('gm_t4'))}）",
        f"  ③ 存貨天數 {s.c3_inventory_days:>4.0f}/20   "
        f"最新 {_fmt_days(m.get('dio_t'))}（上季 {_fmt_days(m.get('dio_t1'))} / 去年同季 {_fmt_days(m.get('dio_t4'))}）",
        f"  ④ 月營收   {s.c4_revenue_yoy:>4.0f}/20   "
        f"近3月YoY {[round(x, 1) if isinstance(x, (int, float)) else None for x in (m.get('rev_yoy_last3') or [])]}",
        f"  理由：{s.reason_text}",
    ]
    return "\n".join(lines)


def format_report(scores: list[ShortageScore], as_json: bool = False) -> str:
    if as_json:
        return json.dumps([dataclasses.asdict(s) for s in scores],
                          ensure_ascii=False, indent=2)
    if not scores:
        return "（無結果）"
    _blocks = [format_score_report(s) for s in scores]
    return ("\n" + "─" * 60 + "\n").join(_blocks)


# ── 進入點 ────────────────────────────────────────────────────
def _load_ids(args) -> list[str]:
    ids = list(args.stock_ids)
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            ids += [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    # 去重保序
    seen, out = set(), []
    for x in ids:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="缺貨 / 供不應求選股 CLI（與 dashboard 同一套計分）")
    p.add_argument("stock_ids", nargs="*", help="台股代號，如 2330 2317")
    p.add_argument("--file", help="股號清單檔（每行一個，# 開頭略過）")
    p.add_argument("--json", action="store_true", help="輸出 JSON")
    args = p.parse_args(argv)

    ids = _load_ids(args)
    if not ids:
        p.print_help()
        return 2
    if not (os.environ.get("FINMIND_TOKEN") or os.environ.get("FM_TOKEN")):
        print("🔴 未偵測到 FINMIND_TOKEN 環境變數。請先：export FINMIND_TOKEN=你的token",
              file=sys.stderr)
        return 2

    if not args.json:
        print(f"🔍 分析 {len(ids)} 檔（每檔抓 FinMind 季報+月營收，請稍候）…\n", file=sys.stderr)
    stocks = [build_stock_input(sid) for sid in ids]
    scores = rank_shortage(stocks, include_na=True)   # CLI 保留資料不足/金融股（顯示原因）
    print(format_report(scores, as_json=args.json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
