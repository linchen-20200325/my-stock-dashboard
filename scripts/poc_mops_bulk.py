"""POC(第 2 輪):鎖定 MOPS 資產負債表彙總 endpoint + 確認各報表確切欄位。

第 1 輪已確認(2026-07-04 GitHub Actions):
  - GitHub runner IP 不被 MOPS 擋(無 403)
  - 正確網域 = mopsov.twse.com.tw
  - 綜合損益表彙總 ajax_t163sb04(合併)/ sb05(個別)→ 全市場(上市~1011、上櫃~740)✅
第 2 輪目標:
  - 找出「資產負債表彙總」endpoint(第 1 輪 t163sb01 回錯誤頁)
  - 對每個回大表的 endpoint,檢查目標欄位關鍵字是否存在(確認欄位覆蓋)

只讀 MOPS 公開彙總報表、不寫檔、不動 production、無需 token。requests-only。
"""
from __future__ import annotations

import re
import sys
import time

import requests

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")

BASE = "https://mopsov.twse.com.tw/mops/web/"   # 第 1 輪確認可用網域

# 候選 endpoint:資產負債表家族(sb01/02/03)+ 已確認的損益表(sb04 對照組)+ 權益(sb06)
ENDPOINTS = [
    "ajax_t163sb01",   # 疑似 資產負債表(合併)
    "ajax_t163sb02",   # 疑似 資產負債表(個別)
    "ajax_t163sb03",   # 其他
    "ajax_t163sb04",   # 已確認 綜合損益表(合併)— 對照組
    "ajax_t163sb06",   # 疑似 權益變動表
]

# 目標欄位關鍵字(檢查每個報表回應內含哪些 → 確認能 cover 哪幾項基本面)
KEYWORDS = {
    # 資產負債表(負債比 #1 / 淨流動值 #8 需要)
    "資產總計": "BS", "負債總計": "BS", "流動資產": "BS", "流動負債": "BS",
    "權益總計": "BS", "應收": "BS-明細", "存貨": "BS-明細", "合約負債": "BS-明細",
    # 綜合損益表(三率 #2 / EPS-估值 #4 需要)
    "營業收入": "IS", "營業毛利": "IS", "營業利益": "IS",
    "本期淨利": "IS", "稅後淨利": "IS", "每股盈餘": "IS",
}

CASES = [("sii", "114", "04"), ("otc", "114", "04")]   # 上市/上櫃 2025 年報(已知有資料)

# 兩種 POST 參數版本(step=1 / step=2,以防資產負債表流程不同)
PARAM_VARIANTS = [
    {"step": "1", "firstin": "1"},
    {"step": "2", "firstin": "true", "keyword4": "", "code1": "", "checkbtn": "",
     "queryName": "co_id", "inpuType": "co_id", "TYPEK2": "", "co_id": ""},
]


def _form(typek, year, season, extra):
    base = {"encodeURIComponent": "1", "off": "1", "isnew": "false",
            "TYPEK": typek, "year": year, "season": season}
    base.update(extra)
    return base


def _kw_hits(text: str):
    return sorted({f"{k}[{tag}]" for k, tag in KEYWORDS.items() if k in text})


def _first_header_cells(text: str, limit=45):
    """粗抽表頭:取所有 <th> 內容(去標籤),前 limit 個。"""
    ths = re.findall(r"<th[^>]*>(.*?)</th>", text, flags=re.S | re.I)
    out = []
    for t in ths:
        t = re.sub(r"<[^>]+>", "", t)
        t = re.sub(r"\s+", "", t)
        if t and t not in out:
            out.append(t)
        if len(out) >= limit:
            break
    return out


def _try(ep, form):
    url = BASE + ep
    hdrs = {"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml",
            "Referer": BASE, "Origin": "https://mopsov.twse.com.tw"}
    try:
        t0 = time.monotonic()
        r = requests.post(url, data=form, headers=hdrs, timeout=40)
        el = time.monotonic() - t0
        text = r.text or ""
        trs = text.count("</tr>")
        codes = {c for c in re.findall(r"(?<!\d)(\d{4})(?!\d)", text)
                 if c[0] in "1234689"}
        return {"http": r.status_code, "trs": trs, "n_codes": len(codes),
                "kb": round(len(r.content) / 1024, 1), "sec": round(el, 1),
                "kw": _kw_hits(text), "headers": _first_header_cells(text)}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def main() -> int:
    print("MOPS POC 第 2 輪:鎖定資產負債表 endpoint + 欄位確認")
    print("=" * 72)
    found = {}
    for (typek, year, season) in CASES:
        print(f"\n########## 市場={typek} 民國{year} 第{season}季 ##########")
        for ep in ENDPOINTS:
            best = None
            for vi, extra in enumerate(PARAM_VARIANTS):
                res = _try(ep, _form(typek, year, season, extra))
                if "error" in res:
                    print(f"  {ep:16s} v{vi} ❌ {res['error']}")
                    continue
                is_big = res["trs"] >= 50 and res["n_codes"] >= 50
                print(f"  {ep:16s} v{vi} http={res['http']} trs={res['trs']} "
                      f"股號={res['n_codes']} {res['kb']}KB {res['sec']}s "
                      f"{'✅大表' if is_big else '—'}")
                if is_big:
                    print(f"        關鍵字: {res['kw']}")
                    print(f"        表頭前段: {res['headers'][:30]}")
                    if best is None:
                        best = res
                time.sleep(0.5)
            if best:
                found[f"{ep}/{typek}"] = best

    # ── VERDICT ──────────────────────────────────────────────────
    print("\n\n" + "#" * 72)
    print("# VERDICT — 把以下整段貼回給 Claude")
    print("#" * 72)
    bs_ep, is_ep = set(), set()
    for key, r in found.items():
        ep = key.split("/")[0]
        tags = {k.split("[")[1].rstrip("]") for k in r["kw"]}
        if "BS" in tags:
            bs_ep.add(ep)
        if "IS" in tags:
            is_ep.add(ep)
        print(f"# {key}: 股號={r['n_codes']} 列={r['trs']} 關鍵字={r['kw']}")
    print("#" + "-" * 70)
    print(f"# 資產負債表彙總 endpoint(含 資產/負債總計): {sorted(bs_ep) or '❌ 沒找到,需再試'}")
    print(f"# 綜合損益表彙總 endpoint(含 營收/毛利/EPS): {sorted(is_ep) or '❌'}")
    if bs_ep and is_ep:
        print("# → ✅ 兩表 endpoint 都定位,欄位覆蓋確認,可開始建 L1 fetcher")
    elif is_ep and not bs_ep:
        print("# → ⚠️ 損益表 OK,但資產負債表還沒中 → 我再換 endpoint 候選試一輪")
    print("#" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
