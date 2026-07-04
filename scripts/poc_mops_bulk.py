"""POC(第 3 輪):鎖定 MOPS 資產負債表彙總 endpoint。

已確認(GitHub Actions 實測):
  - 網域 mopsov.twse.com.tw、GitHub IP 不被擋
  - 綜合損益表彙總 ajax_t163sb04 → 全市場(上市1011/上櫃740),欄位含
    營業收入/營業成本/營業毛利/營業利益/本期淨利/基本每股盈餘 → 三率(#2)+EPS(#4) ✅
  - sb01/sb02/sb03 空或連線被拒 → 非資產負債表
第 3 輪目標:掃更廣的 t163sbXX code,找出含「資產總計/負債總計/流動資產/權益總計」
的資產負債表彙總 endpoint(供 負債比 #1 / 淨流動值 #8)。放慢請求避免 MOPS 拒連。

只讀 MOPS 公開彙總報表、不寫檔、不動 production、無需 token。requests-only。
"""
from __future__ import annotations

import re
import sys
import time

import requests

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
BASE = "https://mopsov.twse.com.tw/mops/web/"

# 掃描候選(跳過已知損益表 sb04/sb06):找資產負債表
SWEEP = [f"ajax_t163sb{n:02d}" for n in
         (1, 2, 3, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18)]

# 資產負債表關鍵字(找到含這些 = 命中)
BS_KW = ["資產總計", "負債總計", "資產總額", "負債總額", "流動資產",
         "流動負債", "權益總計", "權益總額", "非流動資產"]

TYPEK, YEAR, SEASON = "sii", "114", "04"   # 上市 2025 年報(已知有資料)


def _post(ep):
    url = BASE + ep
    form = {"encodeURIComponent": "1", "step": "1", "firstin": "1", "off": "1",
            "isnew": "false", "TYPEK": TYPEK, "year": YEAR, "season": SEASON}
    hdrs = {"User-Agent": _UA, "Accept": "text/html",
            "Referer": BASE, "Origin": "https://mopsov.twse.com.tw"}
    try:
        t0 = time.monotonic()
        r = requests.post(url, data=form, headers=hdrs, timeout=40)
        el = time.monotonic() - t0
        text = r.text or ""
        trs = text.count("</tr>")
        codes = {c for c in re.findall(r"(?<!\d)(\d{4})(?!\d)", text) if c[0] in "1234689"}
        bs_hits = [k for k in BS_KW if k in text]
        return {"http": r.status_code, "trs": trs, "n_codes": len(codes),
                "kb": round(len(r.content) / 1024, 1), "sec": round(el, 1),
                "bs_hits": bs_hits}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:60]}"}


def main() -> int:
    print(f"MOPS POC 第 3 輪:掃資產負債表 endpoint（{TYPEK} 民國{YEAR} 第{SEASON}季）")
    print("=" * 72)
    found = []
    for ep in SWEEP:
        res = _post(ep)
        if "error" in res:
            print(f"  {ep:16s} ❌ {res['error']}")
        else:
            big = res["trs"] >= 50 and res["n_codes"] >= 50
            hit = "🎯 資產負債表!" if res["bs_hits"] else ("✅大表(非BS)" if big else "—")
            print(f"  {ep:16s} http={res['http']} trs={res['trs']} 股號={res['n_codes']} "
                  f"{res['kb']}KB {res['sec']}s  {hit}")
            if res["bs_hits"]:
                print(f"        命中欄位: {res['bs_hits']}")
                found.append((ep, res))
        time.sleep(1.5)   # 放慢避免 MOPS 拒連

    print("\n" + "#" * 72)
    print("# VERDICT — 貼回給 Claude")
    print("#" * 72)
    if found:
        for ep, r in found:
            print(f"# 🎯 資產負債表彙總 = {ep} (股號={r['n_codes']} 列={r['trs']} "
                  f"命中={r['bs_hits']})")
        print("# → ✅ 資產負債表 endpoint 定位!搭配已確認的 sb04(損益表),")
        print("#   4 項基本面(負債比/三率/淨值/估值)資料源全部到齊,可開始建 L1 fetcher")
    else:
        print("# ❌ 本輪 sweep 仍未找到含資產/負債總計的 endpoint")
        print("# → 可能資產負債表在別的報表家族(t164/t051)或需不同流程,我再換一批候選")
    print("#" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
