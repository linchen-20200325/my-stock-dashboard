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
    _data = j.get('data') if isinstance(j.get('data'), dict) else {}
    print(f'   ↳ top-level keys = {list(j)[:12]}')
    print(f'   ↳ result keys    = {list(_result)[:20]}')
    shapes = {
        'result.resources    [兩邊都有]': _result.get('resources'),
        'resources           [兩邊都有]': j.get('resources'),
        'result.distribution [只有探針有]': _result.get('distribution'),
        'data.resources      [只有 production 有]': _data.get('resources'),
    }
    for _k, _v in shapes.items():
        print(f'   ↳ {_k} → {("list × " + str(len(_v))) if isinstance(_v, list) else type(_v).__name__}')
    _hit = [k for k, v in shapes.items() if isinstance(v, list) and v]
    print(f'   🎯 實際命中的 shape = {_hit or "全部皆空"}')

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

    # ③ 模擬修好後的撈法（**只在探針裡模擬,production 未改**）
    print('\n   —— ③ 模擬修法:候選 list 加回 distribution,再交 production 的真 parser ——')
    _res = (_result.get('resources') or j.get('resources')
            or _result.get('distribution') or _data.get('resources') or [])
    if not _res:
        print('   ❌ 四種 shape 全空 → 假設被否證,不是 shape 問題,另尋根因')
        return
    print(f'   ↳ 撈到 resource × {len(_res)};第一筆 keys = '
          f'{list(_res[0])[:14] if isinstance(_res[0], dict) else type(_res[0]).__name__}')
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
        print(f'🎯 fetch_tw_pmi() → value={_r.get("value")} date={_r.get("date")} '
              f'source={_r.get("source")} is_stale={_r.get("is_stale")} '
              f'_err_pmi={_r.get("_err_pmi")}')
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
