# -*- coding: utf-8 -*-
"""TW 資料源存活探針（v19.112 診斷工具,user 回報出口/PMI 無資料觸發）。

用途:從 GitHub Actions(美國 IP + PROXY_URL 走 NAS,與 Streamlit Cloud 同視角)
逐一 GET 出口 YoY 與台灣 PMI 兩鏈的候選端點,印出 HTTP 狀態 + 內容摘要,
產出「今天誰活誰死」的存活表 — 供換源提案用真實證據(§3.3 反捏造:
不驗證存活不接源;兩次 FinMind 假 dataset 事故的教訓)。

安全邊界:
- 只做 GET 讀取,不寫任何狀態、不 commit(§1)
- 絕不印 PROXY_URL / token 本身(fetch_url 內建 log 只印目標 URL 尾段)
- 走 production 同一條 `src.data.proxy.fetch_url`(NAS Squid → 直連降級),
  量到的就是正式環境會看到的
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# 同 update_macro_history.py / calibrate_health_weights.py 既有模式:
# 直跑時 sys.path[0]=scripts/,補 repo root 讓 src.* 可 import。
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# (標籤, URL, 內容關鍵字 — 有回應時檢查 body 是否含此字,證明不是空殼/攔截頁)
TARGETS: list[tuple[str, str, str]] = [
    # ── 台灣 PMI 鏈(現役 9 源中的關鍵 + 新候選) ──────────────
    ('PMI|CIER-EN 分類頁(新候選)',
     'https://www.cier.edu.tw/en/eco_cat/pmi-en/', 'PMI'),
    ('PMI|CIER-EN 2026-06 文章(新制式)',
     'https://www.cier.edu.tw/en/institution-en/31834/', 'PMI'),
    ('PMI|CIER 中文 2026-06 發布文',
     'https://www.cier.edu.tw/focus-ch/31810/', 'PMI'),
    ('PMI|CIER 舊 slug(預期 404,負對照)',
     'https://www.cier.edu.tw/en/eco/taiwan-manufacturing-pmi-june-2026/', 'PMI'),
    ('PMI|CIER 舊 news list cid21(現役第5源)',
     'https://www.cier.edu.tw/news/list?cid=21', 'PMI'),
    ('PMI|NDC index API(現役第3源)',
     'https://index.ndc.gov.tw/app/data/indicator/PMI', 'PMI'),
    ('PMI|data.gov.tw 6100 meta(現役第2源,cron 已證死)',
     'https://data.gov.tw/api/v2/rest/dataset/6100', 'result'),
    ('PMI|MacroMicro taiwan-pmi(現役第4源)',
     'https://www.macromicro.me/charts/22/taiwan-pmi', 'PMI'),
    ('PMI|Cnyes 新聞 API(現役第7源)',
     'https://news.cnyes.com/api/v3/news/category/headline?limit=30&q=%E5%8F%B0%E7%81%A3+PMI',
     'title'),
    # ── 出口 YoY 鏈(現役 6 tier 中的 TW 官方段 + 新候選) ─────
    ('EXP|stat.gov.tw 出口年增率頁(現役 Tier0)',
     'https://www.stat.gov.tw/Point.aspx?sid=t.8&n=3587&sms=11480', '出口'),
    ('EXP|MOF trade CSV 202606(現役 Tier2 式1)',
     'https://service.mof.gov.tw/public/Data/statistic/trade/excel/202606.csv', ''),
    ('EXP|data.gov.tw 6053 meta(現役 Tier3)',
     'https://data.gov.tw/api/v2/rest/dataset/6053', 'result'),
    ('EXP|DGBAS nstatdb 貿易表 qryout(新候選,同 CBC PXWeb 引擎)',
     'https://nstatdb.dgbas.gov.tw/dgbasall/webMain.aspx?sys=100&funid=qryout&funid2=A081201010&cycle=41&outkind=4&outmode=8&fldlst=11&codlst0=10&compmode=02.1',
     ''),
    ('EXP|MOF 統計資料庫 njswww 入口(新候選)',
     'https://web02.mof.gov.tw/njswww/WebMain.aspx?sys=100', ''),
    ('EXP|關港貿單一窗口 GA35(新候選)',
     'https://portal.sw.nat.gov.tw/APGA/GA35', '出口'),
]


def _snippet(body: str, keyword: str, width: int = 160) -> str:
    """取含關鍵字的鄰近片段(證明內容真實);無關鍵字取開頭。壓成單行。"""
    flat = re.sub(r'\s+', ' ', body)
    if keyword:
        idx = flat.find(keyword)
        if idx >= 0:
            return flat[max(0, idx - 40):idx + width - 40]
    return flat[:width]


# ── v19.114 深挖:錯誤碼面板實錘 stat.gov.tw:no-parse(連得上、解不動) ──
# 對指定頁抓「關鍵字前後文視窗」+ 當場試跑 production 正則 → 用真實內文
# 寫新解析器,不猜(§3.3)。每 pattern 印首個 match 的 groups。
_DEEP_DUMPS: list[tuple[str, str, list[str], list[tuple[str, str]]]] = [
    ('stat.gov.tw 出口年增率頁',
     'https://www.stat.gov.tw/Point.aspx?sid=t.8&n=3587&sms=11480',
     ['出口', '年增率', '出口年增率'],
     [('production 現行', r'(20\d{2})\s*年\s*(\d{1,2})\s*月[^。]{0,80}?'
                          r'出口[^。]{0,30}?年增率?[^\d\-]{0,15}(-?\d{1,3}\.\d)\s*%?'),
      ('寬鬆試探A(值優先)', r'年增率[^\d\-]{0,40}(-?\d{1,3}\.\d)'),
      ('寬鬆試探B(民國年月)', r'(1\d{2})年\s*(\d{1,2})月'),
      ('寬鬆試探C(西元年月)', r'(20\d{2})[年/\-\s]+(\d{1,2})[月]?')]),
    ('CIER-EN 2026-06 slug 頁',
     'https://www.cier.edu.tw/en/eco/taiwan-manufacturing-pmi-june-2026/',
     ['60.7', 'percentage', 'PMI was', 'fell'],
     [('production 現行', r'(?:Manufacturing\s+PMI|PMI)[^.]{0,80}?'
                          r'(?:at|registered|reached|of|stood\s+at|rose\s+to|fell\s+to|was)?'
                          r'[^\d]{0,15}(\d{2}\.\d)\s*(?:%|percent)?'),
      ('寬鬆試探(值域鎖)', r'(\d{2}\.\d)\s*(?:%|percent)')]),
]


def _dump_windows(flat: str, keyword: str, n: int = 4, width: int = 130) -> None:
    start = 0
    for i in range(n):
        idx = flat.find(keyword, start)
        if idx < 0:
            if i == 0:
                print(f'     (無「{keyword}」出現)')
            return
        print(f'     [{keyword}#{i + 1}] …{flat[max(0, idx - 50):idx + width - 50]}…')
        start = idx + len(keyword)


def _deep_dump(fetch_url) -> None:
    print('\n══ 深挖:內文視窗 + production 正則試跑 ══')
    for label, url, keywords, patterns in _DEEP_DUMPS:
        r = fetch_url(url, timeout=20, attempts=2)
        if r is None:
            print(f'❌ {label} | 無回應,無法深挖')
            continue
        try:
            r.encoding = r.encoding or 'utf-8'
            from bs4 import BeautifulSoup
            flat = re.sub(r'\s+', ' ',
                          BeautifulSoup(r.text, 'html.parser')
                          .get_text(' ', strip=True))
        except Exception as e:
            print(f'⚠️ {label} | 取文失敗 {type(e).__name__}: {e}')
            continue
        print(f'📄 {label} | HTTP {r.status_code} | 純文字 {len(flat)} chars')
        for kw in keywords:
            _dump_windows(flat, kw)
        for pname, pat in patterns:
            m = re.search(pat, flat)
            if m:
                print(f'   🎯 regex[{pname}] ✅ groups={m.groups()} '
                      f'| 前後文=…{flat[max(0, m.start() - 30):m.end() + 30]}…')
            else:
                print(f'   🎯 regex[{pname}] ❌ 不匹配')


def main() -> int:
    from src.data.proxy import fetch_url

    print(f'🔬 probe_tw_sources 起跑 — {len(TARGETS)} 端點,'
          f'走 production fetch_url(NAS→直連降級)\n')
    n_ok = 0
    for label, url, keyword in TARGETS:
        try:
            r = fetch_url(url, timeout=15, attempts=1)
        except Exception as e:  # fetch_url 理論上不拋,保險起見
            print(f'❌ {label} | EXC {type(e).__name__}: {e}')
            continue
        if r is None:
            print(f'❌ {label} | 無回應(NAS+直連皆敗)')
            continue
        try:
            r.encoding = r.encoding or 'utf-8'
            body = r.text or ''
        except Exception:
            body = ''
        has_kw = (keyword in body) if keyword else bool(body.strip())
        mark = '✅' if (r.status_code == 200 and has_kw) else '⚠️'
        if r.status_code == 200 and has_kw:
            n_ok += 1
        print(f'{mark} {label} | HTTP {r.status_code} | {len(body)} chars | '
              f'關鍵字「{keyword}」{"命中" if has_kw else "未命中"}')
        print(f'   ↳ {_snippet(body, keyword)}')
    print(f'\n📊 結果:{n_ok}/{len(TARGETS)} 端點回 200 且內容含關鍵字')
    _deep_dump(fetch_url)   # v19.114:內文視窗 + 正則試跑
    return 0  # 探針本身永遠 exit 0,存活判讀看逐行輸出


if __name__ == '__main__':
    raise SystemExit(main())
