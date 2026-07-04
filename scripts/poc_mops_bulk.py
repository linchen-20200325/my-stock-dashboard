"""POC:驗證 MOPS(公開資訊觀測站)「整季、全公司彙總報表」能否一次抓全市場財報。

用途(全台股基本面選股網 — MOPS 路線前置驗證):
  MOPS 彙總報表(綜合損益表 / 資產負債表)理論上一次回全市場多公司(摘要欄位)。
  但確切 endpoint id、POST 參數、HTML 格式、以及「GitHub runner IP 會不會被 geo-block(403)」
  audit 只能推測,必須實測。此腳本試打多個候選 endpoint,報告每個回應的結構訊號
  (是否 HTML 大表 / 幾列 / 是否含大量股號 / 是否被擋),跑完把 VERDICT 貼回給我。

只讀公開財報彙總、不寫任何檔、不動 production、無需 token。
requests-only(不依賴 pandas/lxml),用原始 HTML 訊號判斷即可。

執行:GitHub Actions workflow_dispatch(見 .github/workflows/poc_mops_bulk.yml),
或本地 `python scripts/poc_mops_bulk.py`。
"""
from __future__ import annotations

import re
import sys
import time

import requests

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# 候選 endpoint(MOPS 彙總報表「財務報表>彙總報表」家族;確切 id 需實測)
#   t163sb01 = 資產負債表彙總、t163sb04/sb05 = 綜合損益表彙總(合併/個別)
BASES = [
    "https://mops.twse.com.tw/mops/web/",
    "https://mopsov.twse.com.tw/mops/web/",   # 2023 改版後可能的新網域
]
ENDPOINTS = [
    "ajax_t163sb01",   # 資產負債表 彙總
    "ajax_t163sb04",   # 綜合損益表 彙總(合併)
    "ajax_t163sb05",   # 綜合損益表 彙總(個別)
    "t163sb01",        # 無 ajax_ 前綴變體
    "t163sb04",
]
# (市場, 民國年, 季)——挑已公布完成的期別
CASES = [
    ("sii", "114", "04"),   # 上市 2025 年報(民國114 Q4,~2026/3 公布)
    ("sii", "115", "01"),   # 上市 2026 Q1(~2026/5 公布)
    ("otc", "114", "04"),   # 上櫃 2025 年報
]


def _form(typek: str, year: str, season: str) -> dict:
    return {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "isnew": "false",
        "TYPEK": typek,
        "year": year,
        "season": season,
    }


def _signals(text: str) -> dict:
    """從原始 HTML 抽結構訊號:表格列數、股號數量、是否像多公司大表。"""
    tr = text.count("</tr>")
    tables = text.count("<table")
    # 台股 4 碼股號(粗略:出現在 >NNNN< 或 值欄)
    codes = set(re.findall(r"(?<!\d)(\d{4})(?!\d)", text))
    plausible_codes = {c for c in codes if c[0] in "1234689" and 1000 <= int(c) <= 9999}
    err = None
    for kw in ("查詢無資料", "沒有符合", "請重新查詢", "資料處理中", "Error", "error",
               "很抱歉", "無法", "重新登入", "驗證碼", "captcha"):
        if kw in text:
            err = kw
            break
    return {"trs": tr, "tables": tables, "n_codes": len(plausible_codes), "err_kw": err}


def _try(base: str, ep: str, form: dict):
    url = base + ep
    hdrs = {"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml",
            "Referer": base, "Origin": base.rstrip("/web/").rstrip("/")}
    # 先試 POST(MOPS 彙總報表慣例),失敗再試 GET
    for method in ("POST", "GET"):
        try:
            t0 = time.monotonic()
            if method == "POST":
                r = requests.post(url, data=form, headers=hdrs, timeout=30)
            else:
                r = requests.get(url, params=form, headers=hdrs, timeout=30)
            el = time.monotonic() - t0
            text = r.text or ""
            sig = _signals(text)
            return {
                "method": method, "http": r.status_code,
                "final_url": r.url if r.url != url else "(no-redirect)",
                "ctype": r.headers.get("Content-Type", "")[:40],
                "kb": round(len(r.content) / 1024, 1), "sec": round(el, 1),
                **sig, "head": re.sub(r"\s+", " ", text[:160]),
            }
        except Exception as e:
            last = {"method": method, "error": f"{type(e).__name__}: {e}"}
    return last


def main() -> int:
    print("MOPS 彙總報表 date-bulk 可行性 POC(全市場整季財報)")
    print("=" * 72)
    results = []
    for (typek, year, season) in CASES:
        form = _form(typek, year, season)
        print(f"\n########## 市場={typek} 民國{year} 第{season}季 ##########")
        for base in BASES:
            for ep in ENDPOINTS:
                res = _try(base, ep, form)
                tag = f"{base.split('//')[1].split('.')[0]}/{ep}"
                if "error" in res:
                    print(f"  {tag:32s} {res['method']} ❌ {res['error']}")
                    continue
                verdict = "?"
                if res["http"] == 200 and res["n_codes"] >= 50 and res["trs"] >= 50:
                    verdict = "✅ 疑似全市場大表"
                elif res["http"] == 403:
                    verdict = "🚫 403(可能 geo-block)"
                elif res["http"] == 404:
                    verdict = "404 endpoint 不存在"
                elif res["err_kw"]:
                    verdict = f"⚠️ 頁面訊息:{res['err_kw']}"
                elif res["http"] == 200:
                    verdict = "200 但非大表(列/股號少)"
                print(f"  {tag:32s} {res['method']} http={res['http']} "
                      f"trs={res['trs']} 股號={res['n_codes']} tables={res['tables']} "
                      f"{res['kb']}KB {res['sec']}s  {verdict}")
                if verdict.startswith("✅") or (res["http"] == 200 and res["n_codes"] >= 10):
                    print(f"        head: {res['head']}")
                res["_tag"] = tag
                res["_case"] = f"{typek}/{year}/{season}"
                res["_verdict"] = verdict
                results.append(res)
                time.sleep(0.6)

    # ── VERDICT(貼回給我)────────────────────────────────────────
    print("\n\n" + "#" * 72)
    print("# VERDICT — 把以下整段貼回給 Claude")
    print("#" * 72)
    hits = [r for r in results if r.get("_verdict", "").startswith("✅")]
    blocked = [r for r in results if r.get("http") == 403]
    if hits:
        print(f"# ✅ 找到 {len(hits)} 個疑似全市場彙總表 endpoint:")
        seen = set()
        for r in hits:
            key = r["_tag"]
            if key in seen:
                continue
            seen.add(key)
            print(f"#   {r['_tag']} ({r['method']}) case={r['_case']} "
                  f"股號={r['n_codes']} 列={r['trs']} {r['kb']}KB")
        print("# → MOPS 全市場 bulk 成立,可據此建 MOPS 路線")
    elif blocked:
        print(f"# 🚫 {len(blocked)} 個請求被 403 擋(GitHub runner IP 可能被 MOPS geo-block)")
        print("# → 需改走 proxy_helper.nas_relay_fetch(台灣住宅 IP 中繼)再測")
    else:
        print("# ❌ 沒有任何 endpoint 回全市場大表(endpoint id 可能不對 / 改版 / 需多步 token)")
        print("# → 我看 head 訊息調整 endpoint 或 POST 參數再測一輪")
    print("#" + "-" * 70)
    print("# 各請求摘要(http/股號數/verdict):")
    for r in results:
        if "error" in r:
            print(f"#   {r.get('_tag','?')} {r['method']} ERR {r['error']}")
        else:
            print(f"#   {r['_tag']} {r['method']} {r['_case']} http={r['http']} "
                  f"股號={r['n_codes']} trs={r['trs']} → {r['_verdict']}")
    print("#" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
