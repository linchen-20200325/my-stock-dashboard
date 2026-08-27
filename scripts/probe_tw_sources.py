# -*- coding: utf-8 -*-
"""TW 資料源存活探針（v19.112 診斷工具,user 回報出口/PMI 無資料觸發）。

（v19.116 re-run:驗 25s timeout 是否讓 dgtw 慢站在雲端+NAS 成功。）

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
    # ── v19.115 option②:美元計價出口序列探勘(對帳財政部頭條 +40.3% USD) ──
    # 海關 6053 為新臺幣千元 → TWD YoY 與美元頭條有匯率落差。探是否有乾淨
    # machine-readable 美元出口 dataset;無則誠實回報 TWD 為自動化卡片正解。
    ('EXP-USD|CKAN 搜「進出口 美元」',
     'https://data.gov.tw/api/3/action/package_search?q=%E9%80%B2%E5%87%BA%E5%8F%A3%20%E7%BE%8E%E5%85%83&rows=8',
     'result'),
    ('EXP-USD|CKAN 搜「出口 美元 統計」',
     'https://data.gov.tw/api/3/action/package_search?q=%E5%87%BA%E5%8F%A3%20%E7%BE%8E%E5%85%83&rows=8',
     'result'),
    ('EXP-USD|關務署 opendata 站台首頁(找美元變體 dataset)',
     'https://opendata.customs.gov.tw/', '美元'),
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


def _deep_dump_v2(fetch_url) -> None:
    """v19.114 第三輪:資料端點探勘。

    第二輪實錘:stat.gov.tw get_text 只剩 2177 字導覽殼(數值 JS 動態載入)、
    CIER-EN 同 URL 時而 94KB 全頁時而 1.5K 殼(回應不穩)。本輪:
    A. nstatdb qryout 47KB 是殼還是真資料表
    B. stat.gov.tw RAW HTML 掃 AJAX/JSON 資料端點
    C. dgtw 6100/6053 metadata resources 枚舉 + 首資源下載試讀
    D. CIER-EN 同 URL 兩連抓驗不穩定性
    """
    from bs4 import BeautifulSoup
    print('\n══ 深挖v2:資料端點探勘 ══')

    # A. nstatdb qryout
    _nstat = ('https://nstatdb.dgbas.gov.tw/dgbasall/webMain.aspx?sys=100'
              '&funid=qryout&funid2=A081201010&cycle=41&outkind=4&outmode=8'
              '&fldlst=11&codlst0=10&compmode=02.1')
    r = fetch_url(_nstat, timeout=20, attempts=2)
    if r is not None:
        r.encoding = r.encoding or 'utf-8'
        flat = re.sub(r'\s+', ' ',
                      BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True))
        print(f'📄 A.nstatdb qryout | HTTP {r.status_code} | raw {len(r.text)} '
              f'| text {len(flat)}')
        for kw in ('出口', '年增率', '115年', '114年'):
            _dump_windows(flat, kw, n=3)
        for pn, pat in (('民國年月', r'(1\d{2})年\s*(\d{1,2})月'),
                        ('小數值樣本', r'-?\d{1,3}\.\d')):
            ms = re.findall(pat, flat)[:8]
            print(f'   🎯 {pn}: {ms if ms else "無"}')
    else:
        print('❌ A.nstatdb 無回應')

    # B. stat.gov.tw RAW HTML 端點掃描
    _stat = 'https://www.stat.gov.tw/Point.aspx?sid=t.8&n=3587&sms=11480'
    r = fetch_url(_stat, timeout=20, attempts=2)
    if r is not None:
        r.encoding = 'utf-8'
        raw = r.text
        print(f'📄 B.stat.gov.tw RAW | {len(raw)} chars | API/JSON 端點候選:')
        hits = re.findall(
            r'["\']([^"\']{4,120}?(?:api|json|ashx|handler|GetData|Chart)'
            r'[^"\']{0,80})["\']', raw, re.IGNORECASE)
        seen: list[str] = []
        for h in hits:
            if h not in seen:
                seen.append(h)
        for h in seen[:15]:
            print(f'   ↳ {h}')
        if not seen:
            print('   (無命中)')
    else:
        print('❌ B.stat.gov.tw 無回應')

    # C. dgtw metadata resources + 首資源試讀
    for _ds in ('6100', '6053'):
        r = fetch_url(f'https://data.gov.tw/api/v2/rest/dataset/{_ds}',
                      timeout=15, attempts=2,
                      headers={'Accept': 'application/json'})
        if r is None:
            print(f'❌ C.dgtw {_ds} metadata 無回應')
            continue
        try:
            j = r.json()
        except Exception as e:
            print(f'⚠️ C.dgtw {_ds} 非 JSON:{type(e).__name__} '
                  f'| head={r.text[:120]!r}')
            continue
        res = (j.get('result', {}).get('resources') or j.get('resources')
               or j.get('result', {}).get('distribution') or [])
        print(f'📄 C.dgtw {_ds} resources × {len(res)}')
        first_url = None
        for it in res[:6]:
            fmt = str(it.get('format', '?'))
            u = (it.get('url') or it.get('resourceDownloadUrl')
                 or it.get('downloadUrl') or '')
            print(f'   ↳ [{fmt}] {u[:110]}')
            if first_url is None and u:
                first_url = u
        if not res:
            print(f'   (metadata keys={list(j.get("result", j))[:12]})')
        if first_url:
            rc = fetch_url(first_url, timeout=20, attempts=2)
            if rc is None:
                print('   ⬇️ 首資源下載:無回應')
            else:
                head = re.sub(r'\s+', ' ', rc.content[:400].decode(
                    'utf-8-sig', errors='ignore'))[:220]
                print(f'   ⬇️ 首資源 HTTP {rc.status_code} '
                      f'| {len(rc.content)} bytes | head={head!r}')

    # D. CIER-EN 不穩定性
    _cier = 'https://www.cier.edu.tw/en/eco/taiwan-manufacturing-pmi-june-2026/'
    for i in (1, 2):
        r = fetch_url(_cier, timeout=20, attempts=1)
        if r is None:
            print(f'📄 D.CIER-EN 第{i}抓:無回應')
        else:
            flat = re.sub(r'\s+', ' ',
                          BeautifulSoup(r.text, 'html.parser')
                          .get_text(' ', strip=True))
            print(f'📄 D.CIER-EN 第{i}抓 | HTTP {r.status_code} '
                  f'| raw {len(r.text)} | text {len(flat)} | head={flat[:90]!r}')


# ── 2026-08-27 第四輪:CIER-EN「那個數字到底在不在原始 HTML 裡」 ──────
# 前三輪只量到「raw 94218 bytes → html.parser get_text 只剩 1561 chars」,
# 而且在**取出來的文字**裡找不到 60.7 —— 但**從來沒有人去原始 HTML 裡找過那個數字**。
# production(`macro_core._pmi_src_cier_en_monthly`)因此每月回 `no-parse/過時`。
#
# 這一題決定修法,兩條路差很多,不能猜(§3.3):
#   ① 數字**在** raw 裡 → 是 html.parser 把內容吃掉了(requirements 已 pin
#      lxml>=5.3.0)→ 換 parser 或直接對 raw 跑正則,一行的事。
#   ② 數字**不在** raw 裡 → JS 動態載入,正則怎麼改都沒用 → 要換源
#      (ISM World 月報 PDF),那是新增 PDF 解析相依 = 範圍擴大,須先送客戶。
#
# 本段唯讀,只印判讀所需的最小資訊;**不印整頁 HTML**(94KB 進 log 沒有意義)。
_MONTH_NAMES = ['january', 'february', 'march', 'april', 'may', 'june',
                'july', 'august', 'september', 'october', 'november', 'december']

#: 逐字複製自 `macro_core._pmi_src_cier_en_monthly`(該處為 inline,無常數可 import)。
#: 若 production 那條正則變了,這裡要跟著改 —— 本段的意義就是「拿 production 的東西去試跑」。
_PROD_CIER_EN_PAT = (r'(?:Manufacturing\s+PMI|PMI)[^.]{0,80}?'
                     r'(?:at|registered|reached|of|stood\s+at|rose\s+to|fell\s+to|was)?'
                     r'[^\d]{0,15}(\d{2}\.\d)\s*(?:%|percent)?')


def _cier_en_slugs(n_back: int = 3) -> list[str]:
    """與 production 同一套 slug 推算（當月 / -1 / -2），避免探針打到跟線上不同的頁。"""
    import datetime as _dt
    today = _dt.date.today()
    out = []
    for _m_back in range(n_back):
        _y, _m = today.year, today.month - _m_back
        while _m <= 0:
            _m += 12
            _y -= 1
        out.append(f'taiwan-manufacturing-pmi-{_MONTH_NAMES[_m - 1]}-{_y}')
    return out


def _deep_dump_v4_cier_raw(fetch_url) -> None:
    from bs4 import BeautifulSoup
    print('\n══ 深挖v4:CIER-EN 原始 HTML vs 取文後 —— 數字在不在 raw 裡? ══')
    for _slug in _cier_en_slugs():
        url = f'https://www.cier.edu.tw/en/eco/{_slug}/'
        r = fetch_url(url, timeout=20, attempts=2)
        if r is None:
            print(f'❌ {_slug} | 無回應(NAS+直連皆敗)')
            continue
        if r.status_code != 200:
            print(f'⚠️ {_slug} | HTTP {r.status_code}(production 在此就 continue)')
            continue
        r.encoding = 'utf-8'
        raw = r.text or ''
        # 三種表示法：raw / html.parser(production 現用) / lxml(requirements 已 pin)
        reps: list[tuple[str, str]] = [('raw HTML', raw)]
        for _parser in ('html.parser', 'lxml'):
            try:
                reps.append((f'get_text[{_parser}]',
                             re.sub(r'\s+', ' ',
                                    BeautifulSoup(raw, _parser).get_text(' ', strip=True))))
            except Exception as e:
                print(f'   ⚠️ {_parser} 取文失敗 {type(e).__name__}: {e}')
        print(f'📄 {_slug} | HTTP 200 | ' +
              ' | '.join(f'{_n} {len(_t)} chars' for _n, _t in reps))
        for _name, _text in reps:
            # 值域鎖 [30, 70]（同 production 的 sanity 範圍）——避免把年份 / 版號當 PMI
            cands = [c for c in dict.fromkeys(re.findall(r'\d{2}\.\d', _text))
                     if 30.0 <= float(c) <= 70.0]
            m = re.search(_PROD_CIER_EN_PAT, _text, re.IGNORECASE)
            print(f'   ↳ [{_name}] 值域內 xx.x 候選={cands[:12] or "無"} '
                  f'| production 正則 {"✅ " + str(m.groups()) if m else "❌ 不匹配"}')
        # raw 裡 PMI 附近的窗（證明內容真的在，不是我們正則寫壞）
        _flat_raw = re.sub(r'\s+', ' ', raw)
        for _kw in ('Manufacturing PMI', 'PMI'):
            _i = _flat_raw.find(_kw)
            if _i >= 0:
                print(f'   ↳ raw「{_kw}」窗 …{_flat_raw[max(0, _i - 60):_i + 200]}…')
                break


# ── 2026-08-27 第五輪:補 v4 的洞 ——「不在 raw 裡」這個結論當時其實不成立 ────
# v4 印候選時寫的是 `cands[:12]`,**只印前 12 個**。而 july-2026 與 june-2026
# 兩頁印出來的 12 個完全相同(['60.5','31.3','57.3',...]) —— 兩個不同月份的
# 報導不可能有一模一樣的內文數字,那 12 個是**版型 boilerplate**(來自 CSS/
# srcset/?ver= 之類的屬性值);真正的 PMI 值若存在,只會排在第 13 個之後,
# **正好被截掉**。拿一份被截斷的清單去斷言「數字不在裡面」= 用沒查證的東西
# 當事實(§3.3 / §-2 規則 6),故本段補洞後才准下結論。
#
# 本段唯讀,只回答一件事:**指定的那個數字,字面上在不在 raw HTML 裡?**
#   - 不截斷:印候選**總數**與**全部**去重候選;
#   - 直接對 raw 做 substring membership(不經 parser、不經正則),最不容易騙人;
#   - 命中就印它在 raw 裡的上下文窗 → 分辨是內文還是版型雜訊;
#   - 印 raw 裡 'PMI' 的出現次數與前幾個窗 → 判斷內文究竟有沒有被送過來。

#: 要在 raw 裡找的目標值。61.5 = user 指定的 2026-07 值;60.7 = 現行 stale-cache
#: 裡的 2026-06 值(cached_at=2026-07-01,見 v19.116 smoke 輸出)。兩個都找,
#: 因為「新月份的頁面上通常同時出現本月值與上月值」,任一命中都證明內文有送。
_CIER_TARGETS = ('61.5', '60.7')


def _windows(text: str, needle: str, limit: int = 3, half: int = 110) -> list[str]:
    """回傳 needle 在 text 中前 limit 次出現的上下文窗(已壓成單行)。"""
    out, start = [], 0
    while len(out) < limit:
        i = text.find(needle, start)
        if i < 0:
            break
        out.append(text[max(0, i - half):i + half])
        start = i + 1
    return out


def _deep_dump_v5_cier_where(fetch_url) -> None:
    print('\n══ 深挖v5:CIER-EN raw HTML —— 不截斷地找那個數字 ══')
    for _slug in _cier_en_slugs():
        url = f'https://www.cier.edu.tw/en/eco/{_slug}/'
        r = fetch_url(url, timeout=20, attempts=2)
        if r is None:
            print(f'❌ {_slug} | 無回應(NAS+直連皆敗)')
            continue
        if r.status_code != 200:
            print(f'⚠️ {_slug} | HTTP {r.status_code}(production 在此就 continue)')
            continue
        r.encoding = 'utf-8'
        raw = r.text or ''
        flat = re.sub(r'\s+', ' ', raw)

        all_hits = re.findall(r'\d{2}\.\d', raw)
        uniq = list(dict.fromkeys(all_hits))
        in_band = [c for c in uniq if 30.0 <= float(c) <= 70.0]
        print(f'📄 {_slug} | HTTP 200 | raw {len(raw)} chars '
              f'| xx.x 總命中 {len(all_hits)} 次 / 去重 {len(uniq)} 個 '
              f'/ 值域[30,70] 內 {len(in_band)} 個')
        # ⚠️ 不加 [:N] —— v4 就是栽在這裡
        print(f'   ↳ 值域內全部候選(未截斷)={in_band or "無"}')

        # 最直接的證據:字面 substring,不經 parser 也不經正則
        for _t in _CIER_TARGETS:
            if _t in raw:
                print(f'   ✅ 目標「{_t}」**字面出現在 raw HTML 裡**,共 {raw.count(_t)} 次')
                for _w in _windows(flat, _t):
                    print(f'      窗 …{_w}…')
            else:
                print(f'   ❌ 目標「{_t}」字面**不在** raw HTML 裡(raw.count=0)')

        n_pmi = flat.count('PMI')
        print(f'   ↳ raw 裡 "PMI" 出現 {n_pmi} 次;前 3 窗:')
        for _w in _windows(flat, 'PMI', limit=3):
            print(f'      …{_w}…')


# ── 2026-08-27 第六輪:dgtw 6100 —— 探針拿得到、production 拿不到,差在哪 ──────
# 同一次 run(33100973836)內:
#   探針 section C  → `📄 C.dgtw 6100 resources × 1` + CSV 下載 HTTP 200 / 2899 bytes
#   production 端到端 → `dgtw./rest/dataset/6100:無回應`、`dgtw.aset/6100/resource:無回應`
# 兩邊打的**第一個 URL 完全相同**(都是 `/api/v2/rest/dataset/6100`,同樣帶
# `Accept: application/json`,production 的 timeout 還更寬:25s/2 vs 探針 15s/2)
# → **不是**「打錯 endpoint」,也**不是** timeout。
#
# 讀 code 後的待驗假設(本段就是要證實/否證它):
#   兩邊從 metadata JSON 撈 resource 清單的 **shape 候選list 不一樣** —
#     探針:      result.resources → resources → **result.distribution**
#     production:result.resources → resources → **data.resources**
#   若 v2 API 實際回的是 DCAT 風格的 `result.distribution[]`,則探針撈得到、
#   production 撈到空 list → 走 `if not _res: continue`,而那條 continue
#   **不寫 errs** → 整段靜默跳過。
#
# 這個假設能同時解釋 log 裡三件本來對不起來的事:
#   (a) 3 個 meta URL 卻只有 2 筆 dgtw errs(v2 靜默跳過,v1 與第三個各 404→無回應);
#   (b) production 區段完全沒有 `Download.ashx` 的 proxy 成功行(CSV 根本沒被下載);
#   (c) 探針同時間同一個 URL 卻拿得到 resources。
#
# 本段唯讀,且**不修改 production** —— 只做三件事:
#   ① 印 metadata JSON 的實際 shape(top-level keys / result keys / 四種候選各自長度);
#   ② 原封呼叫 production 的 `_pmi_src_dgtw`,印它的回傳與它寫進 errs 的內容;
#   ③ 在探針端**模擬**修好後的撈法(加回 distribution),下載 CSV 後交
#      **production 的真 `_parse_dgtw_pmi_csv`** 解析,印出實際數值與日期。
#   ③ 若印得出值 → 修法確定可行,且那個值就是修好後 production 會拿到的值。
#
# ── 2026-08-27 後續:假設**已被證實**,修法已進 production(v19.120 / 23ff938) ──
# 實測 shape 就是 `result.distribution`;candidate 清單已在 macro_core 補上,
# 那條靜默的 `continue` 也改成會寫 errs。**本段因此改變用途,不再是一次性診斷**:
#   舊:證明假設(一次性)          新:**常設 shape drift 偵測**(每次跑都在看)
# 為什麼值得常設 —— 這次事故的形狀是「**來源換了 shape,而我們的候選清單沒跟上,
# 且不會報錯**」。那種漂移沒有任何徵兆:HTTP 200、JSON 合法、程式不拋例外,
# 只有數字悄悄不再更新。本段現在做三件以前沒做的事:
#   (a) **指名** production 的 `or` 鏈會停在哪一個 shape(不再只印「哪些非空」);
#   (b) **反向掃描**整份 JSON 找出所有 resource 清單,凡是 production 候選鏈裡
#       沒有的路徑就喊 SHAPE DRIFT —— 下次同類問題**第一輪探針就會指出來**,
#       不必再像這次燒掉三輪才定位;
#   (c) 印 resource item 的**完整 keys**,並明講 format / URL 是**哪一個欄名**真的有值
#       (v19.120 的第二半 bug 就是 `format` → `resourceFormat` 欄名漂移)。


#: production `_pmi_src_dgtw` 的 resource shape 候選鏈,**順序與 macro_core 那條 `or` 鏈一致**。
#: 該處為 inline 運算式、無常數可 import → 這裡是**複本**;production 那條鏈改了,這裡要跟著改。
#: (同 `_PROD_CIER_EN_PAT` 的既有做法:探針的價值來自「拿 production 的東西去試跑」。)
_PROD_SHAPE_CHAIN: list[tuple[str, tuple[str, ...]]] = [
    ('result.resources', ('result', 'resources')),
    ('resources', ('resources',)),
    ('result.distribution', ('result', 'distribution')),   # v19.120 補上的那一個
    ('data.resources', ('data', 'resources')),
]

#: resource item 用來擺下載連結的欄名(production 同樣依序 or 下去)。
_RES_URL_KEYS = ('url', 'resourceDownloadUrl', 'downloadUrl')


def _dig(obj, path: tuple[str, ...]):
    """依 dotted path 取值;中途不是 dict 就回 None(不拋)。"""
    for _k in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(_k)
    return obj


def _find_resource_lists(node, path: str = '', out=None, depth: int = 0):
    """遞迴找出 JSON 裡**所有**長得像 resource 清單的節點(list[dict] 且含 URL 欄)。

    這是 shape drift 偵測的核心:不去猜來源「應該」把清單放在哪,而是把它**實際**
    放的所有位置攤出來,再跟 `_PROD_SHAPE_CHAIN` 對比。少一個路徑就是一次靜默失效。
    """
    if out is None:
        out = []
    if depth > 4:            # 防禦性:metadata 再深就不是 resource 清單了
        return out
    if isinstance(node, list):
        if node and all(isinstance(_i, dict) for _i in node) and any(
                _k in _i for _i in node for _k in _RES_URL_KEYS):
            out.append((path or '<root>', len(node)))
        return out
    if isinstance(node, dict):
        for _k, _v in node.items():
            _find_resource_lists(_v, f'{path}.{_k}' if path else _k, out, depth + 1)
    return out


def _deep_dump_v6_dgtw_shape(fetch_url) -> None:
    import datetime as _dt6
    print('\n══ 深挖v6:dgtw 6100 metadata shape —— 探針 vs production 差在哪 ══')
    meta_url = 'https://data.gov.tw/api/v2/rest/dataset/6100'
    r = fetch_url(meta_url, timeout=25, attempts=2,
                  headers={'Accept': 'application/json'})
    if r is None:
        print(f'❌ metadata 無回應:{meta_url}')
        return
    print(f'📄 metadata HTTP {r.status_code} | {len(r.text)} chars')
    if r.status_code != 200:
        return
    try:
        j = r.json()
    except Exception as e:
        print(f'❌ 非 JSON {type(e).__name__} | head={r.text[:160]!r}')
        return

    _result = j.get('result') if isinstance(j.get('result'), dict) else {}
    print(f'   ↳ top-level keys = {list(j)[:12]}')
    print(f'   ↳ result keys    = {list(_result)[:20]}')
    # ① production 候選鏈逐項量測 + **指名**它的 `or` 會停在哪一個
    #    (原本只印「哪些非空」,讀者還要自己心算 or 的短路順序 —— 這次就是這樣讀漏的)
    _winner = None
    for _name, _shape_path in _PROD_SHAPE_CHAIN:
        _v = _dig(j, _shape_path)
        _desc = f'list × {len(_v)}' if isinstance(_v, list) else type(_v).__name__
        if _winner is None and isinstance(_v, list) and _v:
            _winner = _name
            _desc += '   ← production 的 or 鏈會停在這裡'
        print(f'   ↳ {_name:<19} → {_desc}')
    print(f'   🎯 命中 shape = {_winner or "全部皆空(production 會撈到空 list → 走 200但無 resource)"}')

    # ①-b shape drift:live 回應裡有 resource 清單、但 production 候選鏈沒涵蓋的路徑。
    #     這一行就是為了讓「下次同類問題不必再燒三輪探針」。
    _live_lists = _find_resource_lists(j)
    _known_paths = {_n for _n, _ in _PROD_SHAPE_CHAIN}
    _drift = [(_p, _n) for _p, _n in _live_lists if _p not in _known_paths]
    if _drift:
        print(f'   ⚠️ SHAPE DRIFT:live 有 resource 清單,但 production 候選鏈**沒有**這些路徑 → {_drift}')
        print('      → 照 v19.120 的前例,這會讓 production 撈到空 list 而**不報錯**;'
              '請把路徑補進 macro_core 的 or 鏈與本檔 _PROD_SHAPE_CHAIN(兩邊都要)。')
    elif not _live_lists:
        print('   ⚠️ SHAPE DRIFT:整份 JSON 裡找不到任何 resource 清單 → 是來源本身變了,不是 shape 對不上。')
    else:
        print(f'   ✅ 無 shape drift:live 的 resource 清單 {[_p for _p, _ in _live_lists]} 全在 production 候選鏈內')

    # ② production 現況:原封呼叫,看它到底回什麼、寫了什麼 errs
    print('\n   —— ② production `_pmi_src_dgtw` 原封呼叫（現況）——')
    try:
        from src.data.macro.macro_core import _pmi_src_dgtw
        _errs6: list = []
        _out = _pmi_src_dgtw(_dt6.date.today(), 90, _errs6)
        print(f'   🎯 _pmi_src_dgtw() → {_out!r}')
        print(f'   🎯 它寫進 errs 的內容 = {_errs6}')
    except Exception as _e:
        import traceback
        print(f'   ❌ EXC {type(_e).__name__}: {_e}')
        traceback.print_exc()

    # ③ resource item 的**真實欄位形狀** + CSV 原始內容佐證。
    #    v19.120 前這裡是「模擬修法」;修法已進 production(23ff938),故改為佐證用 ——
    #    印出 CSV 實際末行,讓 ② 拿到的值可以跟原始資料**逐字對照**,而不是只信一個回傳值。
    print('\n   —— ③ resource 欄位形狀 + CSV 原始內容佐證 ——')
    _res = _dig(j, dict(_PROD_SHAPE_CHAIN)[_winner]) if _winner else []
    if not _res:
        print('   ❌ production 候選鏈全空 → 這一輪 dgtw 這條路必然拿不到值(見上方 drift 判讀)')
        return
    _first = _res[0] if isinstance(_res[0], dict) else {}
    print(f'   ↳ shape={_winner} | resource × {len(_res)} | 第一筆完整 keys = {list(_first)}')
    # v19.120 的**第二半** bug:format 欄名也漂移了(`format` → `resourceFormat`),
    # 舊碼只看 `format` → 恆為空 → CSV 永遠排不到前面。明講哪個欄名真的有值,免得下次再猜。
    print(f'   ↳ format 類欄位有值的是 '
          f'{[_k for _k in ("format", "resourceFormat") if _first.get(_k)] or "都沒有值"} '
          f'(format={_first.get("format")!r} / resourceFormat={_first.get("resourceFormat")!r})')
    print(f'   ↳ URL 類欄位有值的是 '
          f'{[_k for _k in _RES_URL_KEYS if _first.get(_k)] or "都沒有值"}')
    for _it in _res[:4]:
        if not isinstance(_it, dict):
            continue
        _u = (_it.get('url') or _it.get('resourceDownloadUrl')
              or _it.get('downloadUrl') or '')
        print(f'   ↳ [format={_it.get("format", "?")!r}] {_u[:100]}')
        if not _u:
            continue
        _rc = fetch_url(_u, timeout=25, attempts=2)
        if _rc is None or _rc.status_code != 200:
            print(f'      ⬇️ 下載失敗:{"無回應" if _rc is None else _rc.status_code}')
            continue
        _txt = _rc.content.decode('utf-8-sig', errors='ignore')
        _lines = [ln for ln in _txt.splitlines() if ln.strip()]
        print(f'      ⬇️ HTTP 200 | {len(_rc.content)} bytes | {len(_lines)} 行')
        # ⚠️ 這幾行直接回答總管的 Q3:這條路拿得到的**最新月份到哪**
        print(f'      ↳ 首行={_lines[0]!r} | 末3行={_lines[-3:]!r}')
        try:
            from src.data.macro.macro_core import _parse_dgtw_pmi_csv
            for _age in (90, 3650):
                _p = _parse_dgtw_pmi_csv(_txt, today=_dt6.date.today(),
                                         max_age_days=_age)
                print(f'      🎯 _parse_dgtw_pmi_csv(max_age_days={_age}) → {_p!r}')
        except Exception as _e:
            print(f'      ❌ parser EXC {type(_e).__name__}: {_e}')


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
    _deep_dump(fetch_url)      # v19.114:內文視窗 + 正則試跑
    _deep_dump_v2(fetch_url)   # v19.114:資料端點探勘
    _deep_dump_v4_cier_raw(fetch_url)  # 2026-08-27:數字在不在 raw HTML 裡
    _deep_dump_v5_cier_where(fetch_url)   # 2026-08-27:補 v4 的截斷洞
    _deep_dump_v6_dgtw_shape(fetch_url)   # 2026-08-27:dgtw shape 差異
    _prod_smoke()             # v19.116:production fetcher 端到端(驗 v19.114/115)
    return 0  # 探針本身永遠 exit 0,存活判讀看逐行輸出


def _prod_smoke() -> None:
    """v19.116 診斷:直接跑合併後的 production fetcher,雲端+NAS 端到端驗證。

    user 部署後回報出口/PMI 仍待取得 → 三種可能:①app 跑舊 code ②新 parser
    有 bug ③dgtw 源間歇性又死。本段在 GH Actions(與 Streamlit Cloud 同視角)
    跑真 `fetch_tw_pmi()` / `fetch_export_block()`,印實際回傳 → 分辨是哪種。
    """
    print('\n══ v19.116 production fetcher 端到端 smoke（雲端+NAS）══')
    try:
        from src.data.macro.macro_core import fetch_tw_pmi
        _r = fetch_tw_pmi()
        # 2026-08-27:`is_stale` **只有走 stale fallback 那條路徑才會被寫**;命中 live 時
        # 這個 key 根本不存在 → 原本直接印 `_r.get("is_stale")` 會印出 `None`,而 `None`
        # 讀起來像「不知道」,無法回答驗收要問的那一句「這次到底走 live 還是快照」。
        # 故改為在此判定並印**明確二值 + 一行結論**(§1:不確定就講清楚,不要讓人猜)。
        _stale_flag = bool(_r.get('is_stale'))
        _verdict = ('🟡 STALE — 8 段全失敗,回的是 90 天內的舊快照' if _stale_flag
                    else ('🟢 LIVE — 本次命中即時來源,非快照' if _r.get('value') is not None
                          else '🔴 無值 — 既沒命中 live,也沒有可用快照'))
        print(f'🎯 fetch_tw_pmi() → value={_r.get("value")} date={_r.get("date")} '
              f'source={_r.get("source")} is_stale={_stale_flag} '
              f'_err_pmi={_r.get("_err_pmi")}')
        print(f'   ↳ 判定：{_verdict}'
              f'｜cached_at={_r.get("cached_at")}｜fetched_at={_r.get("fetched_at")}')
    except Exception as _e:
        import traceback
        print(f'❌ fetch_tw_pmi EXC {type(_e).__name__}: {_e}')
        traceback.print_exc()
    try:
        from src.data.macro.macro_snapshot import fetch_export_block
        _r = fetch_export_block(fred_api_key='', finmind_token='')
        print(f'🎯 fetch_export_block() → tw_export={_r.get("tw_export")} '
              f'_err_export={_r.get("_err_export")}')
    except Exception as _e:
        import traceback
        print(f'❌ fetch_export_block EXC {type(_e).__name__}: {_e}')
        traceback.print_exc()


if __name__ == '__main__':
    raise SystemExit(main())
