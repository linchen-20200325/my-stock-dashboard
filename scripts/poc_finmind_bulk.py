"""POC:驗證 FinMind 免費/付費 tier 能否「只給 date、不給 data_id」一次回全市場財報。

用途(全市場基本面選股網 前置可行性驗證,v18.466 audit 唯一未確認項):
  基本面 9 項只吃 3 個 FinMind 財報表。若這 3 表支援 date-bulk(不帶 data_id → 回全市場
  逐股),每天只要 ~3-5 次 API 就能覆蓋 ~2000 檔;否則需 per-stock ≈ 上萬次(爆額度)。
  此腳本用「你的 token」實測,確認 (a) 回不回全市場多股、(b) payload 會不會被擋、
  (c) quota 反應。跑完把最底下的 VERDICT 區塊貼回給我即可。

執行(本地,需你的 FINMIND_TOKEN):
  # 方式一:環境變數
  export FINMIND_TOKEN='你的token'
  python scripts/poc_finmind_bulk.py
  # 方式二:讀 .streamlit/secrets.toml 內的 FINMIND_TOKEN(自動 fallback)
  python scripts/poc_finmind_bulk.py

只讀取公開財報、不寫入任何檔案、不動 production。
"""
from __future__ import annotations

import os
import sys
import time

import requests

FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko)")

# 基本面 9 項去重後只吃這 3 個財報表(見 v18.466 audit B 段)
DATASETS = [
    "TaiwanStockFinancialStatements",   # 損益表(三率三升 / EPS / PE)
    "TaiwanStockBalanceSheet",          # 資產負債表(負債比 / 應收 / 存貨 / 淨值 / 合約負債)
    "TaiwanStockCashFlowsStatement",    # 現金流量表(資本支出)
]

# 依序嘗試的「單季窗口」(start, end)——挑已公布完成的季,避免抓到還沒公布的空窗
QUARTER_WINDOWS = [
    ("2025-06-01", "2025-08-31"),   # 2025 Q2(截 2025-06-30)
    ("2025-03-01", "2025-05-31"),   # 2025 Q1
    ("2024-12-01", "2025-02-28"),   # 2024 Q4
]


def _load_token() -> str:
    tok = os.environ.get("FINMIND_TOKEN", "").strip()
    if tok:
        print("[token] 來源:環境變數 FINMIND_TOKEN")
        return tok
    # fallback:讀 .streamlit/secrets.toml
    for path in (".streamlit/secrets.toml", os.path.expanduser("~/.streamlit/secrets.toml")):
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("FINMIND_TOKEN"):
                            v = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if v:
                                print(f"[token] 來源:{path}")
                                return v
            except Exception as e:
                print(f"[token] 讀 {path} 失敗:{e}")
    return ""


def _call(token: str, dataset: str, *, start_date=None, end_date=None, data_id=None):
    """回傳 (elapsed_s, http_status, json_status, msg, data_list, payload_kb)。"""
    params: dict = {"dataset": dataset}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if data_id:
        params["data_id"] = data_id
    if token:
        params["token"] = token
    hdrs = {"User-Agent": _UA, "Accept": "application/json"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    t0 = time.monotonic()
    r = requests.get(FINMIND_API_URL, params=params, headers=hdrs, timeout=60)
    elapsed = time.monotonic() - t0
    payload_kb = len(r.content) / 1024
    try:
        j = r.json()
    except Exception:
        return elapsed, r.status_code, None, f"non-JSON body: {r.text[:120]}", [], payload_kb
    return elapsed, r.status_code, j.get("status"), j.get("msg", ""), j.get("data", []) or [], payload_kb


def main() -> int:
    token = _load_token()
    if not token:
        print("\n❌ 找不到 FINMIND_TOKEN。請先 `export FINMIND_TOKEN='你的token'` 再跑。")
        print("   (沒有 token 也可跑,但免費匿名額度極低、測不準,不建議)")
    else:
        print(f"[token] 長度 {len(token)}(不顯示內容)\n")

    results = {}

    # ── 控制組:per-stock 呼叫確認 token 本身可用 ──────────────────
    print("=" * 70)
    print("【控制組】per-stock 呼叫(data_id=2330,確認 token / 網路正常)")
    print("=" * 70)
    try:
        el, http, js, msg, data, kb = _call(
            token, "TaiwanStockFinancialStatements",
            start_date="2025-06-01", end_date="2025-08-31", data_id="2330")
        uniq = len({row.get("stock_id") for row in data})
        print(f"  http={http} json_status={js} rows={len(data)} 不同股數={uniq} "
              f"payload={kb:.0f}KB {el:.1f}s msg={msg!r}")
        results["control"] = {"http": http, "json_status": js, "rows": len(data), "uniq": uniq, "msg": msg}
    except Exception as e:
        print(f"  ❌ 控制組例外:{type(e).__name__}: {e}")
        results["control"] = {"error": f"{type(e).__name__}: {e}"}

    # ── 主測:date-bulk(不給 data_id)是否回全市場 ────────────────
    for ds in DATASETS:
        print("\n" + "=" * 70)
        print(f"【date-bulk 主測】{ds}(只給 date,不給 data_id)")
        print("=" * 70)
        hit = None
        for (sd, ed) in QUARTER_WINDOWS:
            try:
                el, http, js, msg, data, kb = _call(token, ds, start_date=sd, end_date=ed)
            except Exception as e:
                print(f"  窗口 {sd}~{ed}:❌ 例外 {type(e).__name__}: {e}")
                results[ds] = {"error": f"{type(e).__name__}: {e}"}
                hit = "error"
                break
            uniq = len({row.get("stock_id") for row in data})
            cols = list(data[0].keys()) if data else []
            print(f"  窗口 {sd}~{ed}:http={http} json_status={js} rows={len(data)} "
                  f"不同股數={uniq} payload={kb:.0f}KB {el:.1f}s")
            if msg:
                print(f"     msg={msg!r}")
            if data:
                print(f"     欄位={cols[:12]}{'...' if len(cols) > 12 else ''}")
                print(f"     stock_id 樣本={sorted({row.get('stock_id') for row in data})[:12]}")
                results[ds] = {"http": http, "json_status": js, "rows": len(data),
                               "uniq": uniq, "payload_kb": round(kb), "window": f"{sd}~{ed}",
                               "cols_has_stock_id": "stock_id" in cols}
                hit = "data"
                break
            # 空窗 → 試下一個更舊的季
        if hit is None:
            print("  ⚠️ 三個窗口都空(可能資料未公布或被擋)")
            results[ds] = {"empty": True}
        time.sleep(1)  # 溫和一點,避免瞬間打太快觸發限流

    # ── VERDICT(把這一段貼回給我)──────────────────────────────
    print("\n\n" + "#" * 70)
    print("# VERDICT — 把以下整段貼回給 Claude")
    print("#" * 70)
    ctrl = results.get("control", {})
    print(f"# 控制組(per-stock): {ctrl}")
    bulk_ok = []
    for ds in DATASETS:
        r = results.get(ds, {})
        verdict = "?"
        if r.get("uniq", 0) >= 50 and r.get("cols_has_stock_id"):
            verdict = "✅ date-bulk 回全市場"
            bulk_ok.append(ds)
        elif r.get("uniq", 1) == 1:
            verdict = "⚠️ 只回單股(date-bulk 不成立 → 需 per-stock)"
        elif r.get("empty"):
            verdict = "⚠️ 全空(資料未公布或被擋)"
        elif r.get("error"):
            verdict = f"❌ 例外 {r.get('error')}"
        elif r.get("json_status") not in (200, None):
            verdict = f"❌ json_status={r.get('json_status')} msg 見上(可能額度/權限)"
        print(f"# {ds}: {verdict}  -> {r}")
    print("#" + "-" * 68)
    if len(bulk_ok) == 3:
        print("# 總結:✅✅✅ 三表都能 date-bulk → 全市場批次快取方案成立,可動工")
    elif bulk_ok:
        print(f"# 總結:部分成立({len(bulk_ok)}/3 可 bulk)→ 需討論卡住的表怎麼辦")
    else:
        print("# 總結:❌ date-bulk 不成立 → 免費 tier 可能不放行,需換方案(付費/分天/減項)")
    print("#" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
