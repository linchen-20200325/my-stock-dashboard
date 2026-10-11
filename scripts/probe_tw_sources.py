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

執行模式(2026-10-11 起;probe workflow 只跑 `python scripts/probe_tw_sources.py` 不帶參數):
- 無參數(預設)→ 只跑 `probe_tpex_new_site()`:TPEx 新網站法人(insti/dailyTrade)/
  收盤(afterTrading/otc)+ TPEx 舊端點取證 + TPEx 市場彙總(推測路徑)+ TWSE T86/BFI82U
  欄位口徑 + FinMind 匿名交叉驗證;探針內直接驗算(買−賣==買賣超、合計關係、
  最低<=收盤<=最高…)並印成立比例。請求數上限 40、間隔 1.5s、timeout 25s。
- `--legacy` → 只跑舊版 PMI/出口 TARGETS + deep dumps + production smoke(原預設行為)。
- `--all` → 兩段都跑。
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


# ══════════════════════════════════════════════════════════════════════════
# 2026-10-11 TPEx 新網站法人/收盤 + TWSE T86/BFI82U 欄位探針（唯讀診斷，預設執行段）
# ──────────────────────────────────────────────────────────────────────────
# 客戶授權上櫃改接櫃買中心新網站 JSON,條件「先 Probe、驗證通過才切換」。沙箱
# egress 連不到 tpex/twse → 由本段在 GH Actions(美國 IP + PROXY_URL→NAS,與
# production 同視角)實打,並**在探針內直接驗算**(買-賣=買賣超、合計關係、
# 收盤落在高低區間…)。只印證據與比例,不下語意結論(語意判定由另組獨立審查)。
# 請求總數上限 _TW_MAX_REQ;每請求間隔 _TW_SLEEP_S 秒(v3 §02:不轟炸來源)。
# ══════════════════════════════════════════════════════════════════════════
import hashlib as _tw_hashlib
import json as _tw_json
import os as _tw_os
import time as _tw_time

_TW_TIMEOUT = 25
_TW_SLEEP_S = 1.5
_TW_MAX_REQ = 40
_TW_REQ_COUNT = 0
_TW_SAMPLE_CODES = ('6488', '5347', '8299')
_TW_SEEN: dict[str, str] = {}          # body sha1 → 首次出現的 label
_TW_SUMMARY: list[tuple[str, str]] = []  # (label, 結果一句話)

# 與 production 一致的 header(_get_tpex_day / fetch_tpex_close_day)
_TW_HDR_TPEX_INST_LEGACY = {'User-Agent': 'Mozilla/5.0', 'Accept': '*/*',
                            'Referer': 'https://www.tpex.org.tw/'}
_TW_HDR_TPEX_CLOSE_LEGACY = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json',
                             'Referer': 'https://www.tpex.org.tw/'}
# 新網站:沿用 fetch_url 預設 Chrome UA,只補 Referer + JSON Accept
_TW_HDR_TPEX_NEW = {'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'Referer': 'https://www.tpex.org.tw/'}
_TW_HDR_TWSE = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}


def _tw_secret_strings() -> list[str]:
    """收集不得出現在 log 的字串(proxy/NAS 連線資訊、金鑰)。"""
    from urllib.parse import urlsplit
    out: set[str] = set()
    for k in ('PROXY_URL', 'NAS_BASE_URL', 'NAS_RELAY_URL', 'NAS_API_KEY', 'FINMIND_TOKEN'):
        v = _tw_os.environ.get(k) or ''
        if len(v) >= 4:
            out.add(v)
            try:
                sp = urlsplit(v)
                for part in (sp.hostname, sp.username, sp.password, sp.netloc):
                    if part and len(part) >= 4:
                        out.add(part)
            except Exception:  # noqa: BLE001 — 非 URL 形式的 key 直接整串遮
                pass
    return sorted(out, key=len, reverse=True)


def _tw_redact(s: str) -> str:
    for sec in _tw_secret_strings():
        s = s.replace(sec, '***')
    return s


def _tw_prepared(url: str, params: dict | None) -> str:
    try:
        import requests
        return requests.Request('GET', url, params=params).prepare().url
    except Exception:  # noqa: BLE001
        return url


def _tw_final_url(r, requested: str) -> str:
    u = str(getattr(r, 'url', '') or '')
    if not u:
        return f'(r.url 空 — 可能為 Storm Shield 快取 mock;請求={requested})'
    nb = (_tw_os.environ.get('NAS_BASE_URL') or _tw_os.environ.get('NAS_RELAY_URL') or '').rstrip('/')
    if nb and u.startswith(nb):
        return f'[經 NAS 中繼 /proxy 代抓;中繼位址已遮] 目標={requested}'
    hist = getattr(r, 'history', None) or []
    chain = ' → '.join(f'{h.status_code}:{h.url}' for h in hist)
    return _tw_redact(u + (f'   (轉址鏈: {chain} → 最終)' if chain else '   (無轉址)'))


def _tw_get(fetch_url, label: str, url: str, params: dict | None = None,
            headers: dict | None = None):
    """單一請求:印 URL/status/Content-Type/body 前 500 字;JSON 則 dump 結構。
    回 (json_obj 或 None, 是否與先前回應重複)。任何失敗都印原因並繼續,不拋。"""
    global _TW_REQ_COUNT
    if _TW_REQ_COUNT >= _TW_MAX_REQ:
        print(f'\n── [略] {label} — 已達請求上限 {_TW_MAX_REQ},不送出')
        _TW_SUMMARY.append((label, '未送出(達上限)'))
        return None, False
    if _TW_REQ_COUNT:
        _tw_time.sleep(_TW_SLEEP_S)
    _TW_REQ_COUNT += 1
    full = _tw_prepared(url, params)
    print(f'\n── [{_TW_REQ_COUNT:02d}] {label}')
    print(f'   請求 URL : {full}')
    try:
        r = fetch_url(url, headers=headers, params=params, timeout=_TW_TIMEOUT, attempts=1)
    except Exception as e:  # noqa: BLE001 — fetch_url 理論上不拋,保險
        print(f'   ❌ EXC {type(e).__name__}: {_tw_redact(str(e))}')
        _TW_SUMMARY.append((label, f'EXC {type(e).__name__}'))
        return None, False
    if r is None:
        print('   ❌ fetch_url 回 None(非 200,或 NAS→直連→中繼皆敗;'
              '實際 HTTP 狀態/錯誤見上方 [proxy]/[NAS中繼] log 行)')
        _TW_SUMMARY.append((label, 'None(非200/全敗,見 [proxy] log)'))
        return None, False
    status = getattr(r, 'status_code', '?')
    ctype = ''
    try:
        ctype = r.headers.get('Content-Type', '') if r.headers is not None else ''
    except Exception:  # noqa: BLE001
        pass
    raw = r.content or b''
    text = raw.decode('utf-8-sig', errors='replace')
    print(f'   最終 URL : {_tw_final_url(r, full)}')
    print(f'   HTTP {status} | Content-Type: {ctype or "(無)"} | {len(raw)} bytes')
    print(f'   body[:500]: {_tw_redact(text[:500]).replace(chr(10), "⏎").replace(chr(13), "")}')
    sha = _tw_hashlib.sha1(raw).hexdigest()[:12]
    dup_of = _TW_SEEN.get(sha)
    if dup_of is None:
        _TW_SEEN[sha] = label
    try:
        j = _tw_json.loads(text)
    except Exception as e:  # noqa: BLE001
        print(f'   ⚠️ 非 JSON({type(e).__name__}) — sha1={sha}')
        _TW_SUMMARY.append((label, f'HTTP {status} 非 JSON ({len(raw)}B)'))
        return None, dup_of is not None
    if dup_of is not None:
        print(f'   ♻️ body sha1={sha} 與「{dup_of}」完全相同 → 結構不重複 dump')
    else:
        print(f'   body sha1={sha}')
        _tw_dump_json(j)
    _TW_SUMMARY.append((label, f'HTTP {status} JSON {_tw_brief(j)}'
                        + (f' (=「{dup_of}」)' if dup_of else '')))
    return j, dup_of is not None


def _tw_tables(j) -> list[dict]:
    if not isinstance(j, dict):
        return []
    if isinstance(j.get('tables'), list):
        return [t for t in j['tables'] if isinstance(t, dict)]
    if 'fields' in j or 'data' in j:
        return [j]
    return []


def _tw_rows(t: dict) -> list:
    rows = t.get('data')
    if rows is None:
        rows = t.get('aaData')
    return rows if isinstance(rows, list) else []


def _tw_brief(j) -> str:
    if not isinstance(j, dict):
        return type(j).__name__
    ts = _tw_tables(j)
    parts = [f"stat={j.get('stat')!r}", f"date={j.get('date')!r}", f'tables={len(ts)}']
    if ts:
        parts.append('rows=' + '/'.join(str(len(_tw_rows(t))) for t in ts))
    if 'aaData' in j:
        parts.append(f"aaData={len(j.get('aaData') or [])}")
    return ' '.join(parts)


def _tw_dump_json(j) -> None:
    if not isinstance(j, dict):
        print(f'   JSON 頂層型別={type(j).__name__} len={len(j) if hasattr(j, "__len__") else "?"}')
        if isinstance(j, list):
            for x in j[:3]:
                print(f'     {x!r}'[:600])
        return
    print(f'   頂層 keys: {list(j.keys())}')
    for k, v in j.items():
        if k in ('tables', 'data', 'aaData', 'fields'):
            continue
        sv = repr(v)
        print(f'     .{k} = {sv[:400]}{"…" if len(sv) > 400 else ""}')
    if 'aaData' in j:
        aa = j.get('aaData') or []
        print(f'   aaData 列數={len(aa)}')
        for x in aa[:3]:
            print(f'     aaData列: {x!r}')
    ts = _tw_tables(j)
    print(f'   tables 數={len(ts)}' + ('(頂層即 table)' if ts and ts[0] is j else ''))
    for ti, t in enumerate(ts):
        fields = t.get('fields') or []
        rows = _tw_rows(t)
        print(f'   ┌ table[{ti}] title={t.get("title")!r} date={t.get("date")!r} '
              f'totalCount={t.get("totalCount")!r} data列數={len(rows)} fields長度={len(fields)}')
        for fi, fn in enumerate(fields):
            print(f'   │ field[{fi}] = {fn!r}')
        for x in rows[:3]:
            print(f'   │ data列: {x!r}')
        for k in t.keys():
            if k not in ('fields', 'data', 'aaData', 'title', 'date', 'totalCount'):
                sv = repr(t[k])
                print(f'   │ .{k} = {sv[:600]}{"…" if len(sv) > 600 else ""}')
        print('   └')


def _tw_n(x):
    """數值化:去千分位/+號/HTML 標籤;空字串、--、---、X 等 → None。"""
    if x is None:
        return None
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = re.sub(r'<[^>]+>', '', str(x)).strip()
    s = s.replace(',', '').replace('+', '').replace('−', '-').replace(' ', '')
    if s in ('', '-', '--', '---', '----', 'X', 'x', 'N/A', 'NA'):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _tw_cell(row, i):
    return row[i] if isinstance(row, (list, tuple)) and i < len(row) else None


def _tw_ratio(rows, idxs, pred, label: str, show_fail: int = 3) -> None:
    """對所有 idxs 皆數值的列計算 pred 成立比例,印不成立樣本。"""
    n_valid = n_ok = n_nontriv = 0
    fails = []
    for row in rows:
        vals = [_tw_n(_tw_cell(row, i)) for i in idxs]
        if any(v is None for v in vals):
            continue
        n_valid += 1
        if all(v != 0 for v in vals[:-1]):
            n_nontriv += 1
        if pred(*vals):
            n_ok += 1
        elif len(fails) < show_fail:
            fails.append((_tw_cell(row, 0), [_tw_cell(row, i) for i in idxs]))
    pct = f'{n_ok / n_valid:.4%}' if n_valid else 'n/a'
    print(f'     {label}: 成立 {n_ok}/{n_valid} = {pct} (前項皆非零的列 {n_nontriv})')
    for code, vs in fails:
        print(f'        ✗ {code}: {vs}')


def _tw_eq(a, b, tol=0.5):
    return abs(a - b) < tol


def _tw_col_stats(fields, rows) -> int:
    ncols = max((len(r) for r in rows if isinstance(r, (list, tuple))), default=0)
    print(f'   [欄位統計] 列數={len(rows)} 最大欄數={ncols}')
    print('     idx | 欄名 | 空/非數值 | 正 | 負 | 零 | 加總 | 非數值樣本')
    for i in range(ncols):
        name = fields[i] if fields and i < len(fields) else f'col{i}'
        nn = pos = neg = zero = 0
        tot = 0.0
        samples: list = []
        for r in rows:
            v = _tw_n(_tw_cell(r, i))
            if v is None:
                nn += 1
                raw = _tw_cell(r, i)
                if len(samples) < 4 and raw not in samples:
                    samples.append(raw)
            elif v > 0:
                pos += 1; tot += v
            elif v < 0:
                neg += 1; tot += v
            else:
                zero += 1
        print(f'     {i:>3} | {name} | {nn} | {pos} | {neg} | {zero} | {tot:,.2f} | {samples!r}')
    return ncols


def _tw_net_classes(fields) -> dict:
    """依欄名把『買賣超/淨』欄歸類(順序重要:先判『不含』再判『外資自營商』)。"""
    cls: dict[str, int] = {}
    for i, fn in enumerate(fields or []):
        s = str(fn)
        if not ('買賣超' in s or '淨' in s or '差額' in s):
            continue
        if '三大法人' in s:
            key = 'total3'
        elif ('外資' in s or '外陸資' in s) and '不含' in s:
            key = 'f_excl'
        elif '外資自營商' in s:
            key = 'f_dealer'
        elif '外資' in s or '外陸資' in s:
            key = 'f_total'
        elif '投信' in s:
            key = 'trust'
        elif '自營' in s and '自行' in s:
            key = 'd_self'
        elif '自營' in s and '避險' in s:
            key = 'd_hedge'
        elif '自營' in s:
            key = 'd_total'
        else:
            key = f'other{i}'
        cls.setdefault(key, i)
    return cls


def _tw_analyze_insti(label: str, fields, rows) -> None:
    print(f'\n   ▶ 法人驗算〔{label}〕')
    if not rows:
        print('     (無資料列,跳過)')
        return
    fields = [str(f) for f in (fields or [])]
    ncols = _tw_col_stats(fields, rows)
    # ① 買進-賣出==買賣超 三欄一組
    print('   [三欄一組 買進−賣出==買賣超]')
    trips = []
    if fields:
        def _np(x: str) -> str:   # 去括號內文(如「(自行買賣)」「(不含外資自營商)」)再判買/賣
            return re.sub(r'[(（][^)）]*[)）]', '', x)
        for i in range(len(fields) - 2):
            a, b, c = _np(fields[i]), _np(fields[i + 1]), _np(fields[i + 2])
            if '買' in a and '賣' not in a and '賣' in b and '買' not in b \
                    and ('買賣超' in c or '淨' in c or '差額' in c):
                trips.append(i)
    if trips:
        for i in trips:
            _tw_ratio(rows, [i, i + 1, i + 2], lambda a, b, c: _tw_eq(a - b, c),
                      f'[{i},{i+1},{i+2}] {fields[i]} − {fields[i+1]} == {fields[i+2]}')
    else:
        print('     (欄名無法辨識三欄組 → 位置掃描:每個連續三欄,印成立比例≥50% 者)')
        for i in range(2, max(ncols - 2, 2)):
            ok = tot = 0
            for r in rows:
                v = [_tw_n(_tw_cell(r, k)) for k in (i, i + 1, i + 2)]
                if None in v:
                    continue
                tot += 1
                ok += _tw_eq(v[0] - v[1], v[2])
            if tot and ok / tot >= 0.5:
                print(f'     位置[{i},{i+1},{i+2}]: {ok}/{tot} = {ok/tot:.4%}')
    # ② 欄名推得的合計關係
    cls = _tw_net_classes(fields)
    print(f'   [淨額欄歸類(依欄名)] { {k: (v, fields[v]) for k, v in cls.items()} }')
    rel = [
        ('外資(不含外資自營商) + 外資自營商 == 外資合計', ['f_excl', 'f_dealer', 'f_total']),
        ('自營商(自行) + 自營商(避險) == 自營商合計', ['d_self', 'd_hedge', 'd_total']),
        ('三大法人 == 外資(不含) + 投信 + 自營商合計', ['f_excl', 'trust', 'd_total', 'total3']),
        ('三大法人 == 外資合計 + 投信 + 自營商合計', ['f_total', 'trust', 'd_total', 'total3']),
        ('三大法人 == 外資(不含) + 外資自營商 + 投信 + 自營商合計',
         ['f_excl', 'f_dealer', 'trust', 'd_total', 'total3']),
        ('三大法人 == 外資(不含) + 投信 + 自行 + 避險', ['f_excl', 'trust', 'd_self', 'd_hedge', 'total3']),
    ]
    for name, keys in rel:
        if all(k in cls for k in keys):
            idxs = [cls[k] for k in keys]
            _tw_ratio(rows, idxs, lambda *v: _tw_eq(sum(v[:-1]), v[-1]),
                      f'{name}  idx={idxs}')
        else:
            print(f'     {name}: 缺欄 {[k for k in keys if k not in cls]} → 無法驗')
    # ③ 名稱無關的暴力搜尋:淨額欄間 a+b==c、a+b+c==d(成立≥98% 且非平凡列≥20)
    net_idx = sorted(set(cls.values())) if cls else []
    if not net_idx:
        net_idx = [i for i in range(2, ncols)]  # 無欄名:全數值欄
    if len(net_idx) <= 12:
        from itertools import combinations
        print(f'   [暴力搜尋 加總關係(名稱無關)] 候選欄={net_idx}')
        cols = {i: [_tw_n(_tw_cell(r, i)) for r in rows] for i in net_idx}
        hits = []
        for k in (2, 3):
            for combo in combinations(net_idx, k):
                for tgt in net_idx:
                    if tgt in combo:
                        continue
                    ok = tot = nt = 0
                    for ri in range(len(rows)):
                        vs = [cols[c][ri] for c in combo]
                        t = cols[tgt][ri]
                        if t is None or None in vs:
                            continue
                        tot += 1
                        if all(v != 0 for v in vs):
                            nt += 1
                        ok += _tw_eq(sum(vs), t)
                    if tot and ok / tot >= 0.98 and nt >= 20:
                        hits.append((ok / tot, combo, tgt, ok, tot, nt))
        for ratio, combo, tgt, ok, tot, nt in sorted(hits, key=lambda h: -h[0])[:20]:
            nm = lambda i: fields[i] if fields and i < len(fields) else f'col{i}'
            print(f'     {" + ".join(f"[{c}]{nm(c)}" for c in combo)} == [{tgt}]{nm(tgt)}'
                  f' : {ok}/{tot}={ratio:.4%} 非平凡列={nt}')
        if not hits:
            print('     (無成立≥98% 且非平凡列≥20 的組合)')
    # ④ 樣本股完整列
    _tw_print_samples(fields, rows)


def _tw_print_samples(fields, rows) -> None:
    by = {str(_tw_cell(r, 0)).strip(): r for r in rows if isinstance(r, (list, tuple)) and r}
    for code in _TW_SAMPLE_CODES:
        r = by.get(code)
        if r is None:
            print(f'   [樣本 {code}] 不在本表')
            continue
        if fields:
            print(f'   [樣本 {code}] ' + ' | '.join(
                f'{fields[i] if i < len(fields) else f"col{i}"}={r[i]!r}' for i in range(len(r))))
        else:
            print(f'   [樣本 {code}] {r!r}')


def _tw_find_idx(fields, *keys, exclude=()):
    for i, f in enumerate(fields or []):
        s = str(f)
        if all(k in s for k in keys) and not any(e in s for e in exclude):
            return i
    return None


def _tw_analyze_close(label: str, fields, rows, positional: bool = False) -> None:
    print(f'\n   ▶ 收盤驗算〔{label}〕')
    if not rows:
        print('     (無資料列,跳過)')
        return
    fields = [str(f) for f in (fields or [])]
    _tw_col_stats(fields, rows)
    if positional or not fields:
        # production docstring:[代號, 名稱, 收盤, 漲跌, 開盤, 最高, 最低, 成交股數, 成交金額, ...]
        ix = {'close': 2, 'open': 4, 'high': 5, 'low': 6, 'vol': 7, 'amt': 8}
        print(f'     (無欄名 → 依 production docstring 位置假設) {ix}')
    else:
        ix = {'close': _tw_find_idx(fields, '收盤'), 'open': _tw_find_idx(fields, '開盤'),
              'high': _tw_find_idx(fields, '最高'), 'low': _tw_find_idx(fields, '最低'),
              'vol': _tw_find_idx(fields, '成交股數') if _tw_find_idx(fields, '成交股數') is not None
              else _tw_find_idx(fields, '成交量'),
              'amt': _tw_find_idx(fields, '成交金額')}
        print(f'     欄名定位: { {k: (v, fields[v] if v is not None else None) for k, v in ix.items()} }')
        print(f'     單位線索(含 股/金額/元/仟/張 的欄名): '
              f'{[f for f in fields if any(u in f for u in ("股", "金額", "元", "仟", "張"))]}')
    c, h, lo, vol, amt = ix['close'], ix['high'], ix['low'], ix['vol'], ix['amt']
    if None in (c, h, lo):
        print('     缺 收盤/最高/最低 欄 → 跳過區間驗算')
    else:
        _tw_ratio(rows, [lo, c, h], lambda a, b, d: a - 1e-9 <= b <= d + 1e-9, '最低 <= 收盤 <= 最高')
        _tw_ratio(rows, [lo, h], lambda a, d: a <= d + 1e-9, '最低 <= 最高')
        if vol is not None and amt is not None:
            for tag, mul in (('金額/股數', 1.0), ('金額×1000/股數', 1000.0), ('金額/(股數×1000)', 0.001)):
                _tw_ratio(rows, [vol, amt, lo, h],
                          lambda v, a, l, hh, m=mul: v > 0 and (l * 0.999 - 1e-9) <= a * m / v <= (hh * 1.001 + 1e-9),
                          f'{tag} ∈ [最低,最高](±0.1%)')
    if c is not None:
        nonnum = [r[c] for r in rows if _tw_n(_tw_cell(r, c)) is None]
        print(f'     非數值收盤: {len(nonnum)} 列,distinct 樣本={sorted(set(map(str, nonnum)))[:8]}')
    _tw_print_samples(fields, rows)


def _tw_cross_cols(label: str, fa, rows_a, fb, rows_b) -> None:
    """名稱無關:A 每個數值欄找 B 中相等比例最高的欄(共同代號上)。"""
    print(f'\n   ▶ 跨端點欄位對映〔{label}〕')
    ma = {str(_tw_cell(r, 0)).strip(): r for r in rows_a if isinstance(r, (list, tuple)) and r}
    mb = {str(_tw_cell(r, 0)).strip(): r for r in rows_b if isinstance(r, (list, tuple)) and r}
    common = sorted(set(ma) & set(mb))
    print(f'     A 代號數={len(ma)} B 代號數={len(mb)} 共同={len(common)} '
          f'只在A={len(set(ma) - set(mb))} 只在B={len(set(mb) - set(ma))}')
    if not common:
        return
    na = max(len(ma[k]) for k in common)
    nb = max(len(mb[k]) for k in common)
    fa = [str(x) for x in (fa or [])]
    fb = [str(x) for x in (fb or [])]
    for i in range(1, na):
        best = (0.0, None, 0)
        ratios: dict[int, float] = {}
        for j in range(1, nb):
            ok = tot = 0
            for k in common:
                a, b = _tw_cell(ma[k], i), _tw_cell(mb[k], j)
                va, vb = _tw_n(a), _tw_n(b)
                if va is None and vb is None:
                    if i == 1 and j == 1:
                        tot += 1; ok += (str(a).strip() == str(b).strip())
                    continue
                if va is None or vb is None:
                    tot += 1
                    continue
                tot += 1
                ok += abs(va - vb) < 1e-6
            if tot:
                ratios[j] = ok / tot
            if tot and ok / tot > best[0]:
                best = (ok / tot, j, tot)
        na_ = fa[i] if i < len(fa) else f'col{i}'
        ties = [j for j, v in ratios.items() if best[1] is not None and v >= best[0] - 1e-12]
        nb_ = ' / '.join(f'B[{j}] {fb[j] if j < len(fb) else f"col{j}"}' for j in ties) or 'B[None]'
        print(f'     A[{i}] {na_}  →  {nb_} : 相等 {best[0]:.4%} (n={best[2]})')


def _tw_first_table(j):
    """回 (fields, rows):新網站 tables[0] / TWSE 頂層 / 舊 TPEx aaData。"""
    if not isinstance(j, dict):
        return [], []
    ts = _tw_tables(j)
    if ts:
        return ts[0].get('fields') or [], _tw_rows(ts[0])
    if isinstance(j.get('aaData'), list):
        return [], j['aaData']
    return [], []


def _tw_finmind(fetch_url, tpex_inst: tuple, tpex_close: tuple) -> None:
    print('\n══ ④ FinMind 匿名交叉驗證(probe workflow 無 FINMIND_TOKEN → 匿名呼叫) ══')
    fi_fields, fi_rows = tpex_inst
    fc_fields, fc_rows = tpex_close
    by_i = {str(_tw_cell(r, 0)).strip(): r for r in fi_rows if isinstance(r, (list, tuple)) and r}
    by_c = {str(_tw_cell(r, 0)).strip(): r for r in fc_rows if isinstance(r, (list, tuple)) and r}
    for code in _TW_SAMPLE_CODES:
        for ds in ('TaiwanStockInstitutionalInvestorsBuySell', 'TaiwanStockPrice'):
            j, _ = _tw_get(fetch_url, f'FinMind {ds} {code} 2026-10-08',
                           'https://api.finmindtrade.com/api/v4/data',
                           params={'dataset': ds, 'data_id': code,
                                   'start_date': '2026-10-08', 'end_date': '2026-10-08'})
            if not isinstance(j, dict):
                print('     (FinMind 失敗,跳過比對)')
                continue
            data = j.get('data') or []
            if not data:
                print(f'     FinMind 無資料 msg={j.get("msg")!r} status={j.get("status")!r}')
                continue
            if ds.startswith('TaiwanStockInst'):
                row = by_i.get(code)
                fl = [str(f) for f in (fi_fields or [])]
                for d in data:
                    nm = d.get('name')
                    buy, sell = _tw_n(d.get('buy')), _tw_n(d.get('sell'))
                    net = None if buy is None or sell is None else buy - sell
                    hit = []
                    if row is not None:
                        for tag, val in (('buy', buy), ('sell', sell), ('net', net)):
                            if val is None:
                                continue
                            idx = [i for i in range(len(row)) if i >= 2 and _tw_n(row[i]) is not None
                                   and abs(_tw_n(row[i]) - val) < 0.5]
                            hit.append(f'{tag}={val:,.0f}→TPEx新欄{[(i, fl[i] if i < len(fl) else None) for i in idx]}')
                    print(f'     FinMind {code} {nm}: buy={buy} sell={sell} net={net} | '
                          + ('; '.join(hit) if row is not None else 'TPEx 新網站 10/08 無此代號列'))
            else:
                row = by_c.get(code)
                fl = [str(f) for f in (fc_fields or [])]
                for d in data:
                    print(f'     FinMind {code} price row: {d}')
                    if row is None:
                        print('       TPEx 新網站收盤 10/08 無此代號列')
                        continue
                    for key in ('open', 'max', 'min', 'close', 'Trading_Volume', 'Trading_money', 'spread'):
                        val = _tw_n(d.get(key))
                        if val is None:
                            continue
                        idx = [i for i in range(len(row)) if i >= 2 and _tw_n(row[i]) is not None
                               and abs(_tw_n(row[i]) - val) < 1e-6]
                        print(f'       {key}={val} → TPEx新欄 {[(i, fl[i] if i < len(fl) else None) for i in idx]}')


def probe_tpex_new_site() -> int:
    """預設執行段:TPEx 新/舊端點 + TWSE T86/BFI82U + FinMind 匿名交叉驗證。"""
    from src.data.proxy import fetch_url
    print('🔬 probe_tw_sources(預設段:TPEx 新網站法人/收盤 + TWSE T86/BFI82U 欄位探針)')
    print(f'   走 production fetch_url(NAS→直連→中繼降級) timeout={_TW_TIMEOUT}s attempts=1 '
          f'請求間隔 {_TW_SLEEP_S}s 上限 {_TW_MAX_REQ} 請求')
    print(f'   PROXY_URL 設定={"是" if _tw_os.environ.get("PROXY_URL") else "否"} '
          f'NAS_BASE_URL 設定={"是" if _tw_os.environ.get("NAS_BASE_URL") else "否"} '
          f'FINMIND_TOKEN 設定={"是" if _tw_os.environ.get("FINMIND_TOKEN") else "否"}(值一律不印)')

    # ── A. TPEx 舊端點(取證) ─────────────────────────────────────────
    print('\n══ A. TPEx 舊端點(production 現行參數) ══')
    old = {}
    for key, url, params, hdr in (
        ('hedge', 'https://www.tpex.org.tw/web/stock/3insti/daily_report/3itrade_hedge_result.php',
         {'l': 'zh-tw', 'se': 'EW', 't': 'D', 'd': '115/10/08', 'o': 'json'}, _TW_HDR_TPEX_INST_LEGACY),
        ('trade', 'https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php',
         {'l': 'zh-tw', 'se': 'EW', 't': 'D', 'd': '115/10/08', 'o': 'json'}, _TW_HDR_TPEX_INST_LEGACY),
        ('close', 'https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php',
         {'l': 'zh-tw', 'd': '115/10/08', 'o': 'json'}, _TW_HDR_TPEX_CLOSE_LEGACY),
    ):
        j, dup = _tw_get(fetch_url, f'A 舊端點 {key} 115/10/08', url, params, hdr)
        old[key] = _tw_first_table(j)
        if j is not None and not dup:
            f, rows = old[key]
            if key == 'close':
                _tw_analyze_close(f'A 舊 close', f, rows, positional=not f)
            else:
                _tw_analyze_insti(f'A 舊 {key}', f, rows)

    trading = ('2026-10-08', '2026-10-01', '2026-09-18')
    nontrading = ('2026-10-09', '2026-10-10')

    def _fmt(d: str, kind: str) -> str:
        y, m, dd = d.split('-')
        return f'{int(y) - 1911}/{m}/{dd}' if kind == 'roc' else f'{y}/{m}/{dd}'

    # ── B. 新網站法人 ───────────────────────────────────────────────
    print('\n══ B. TPEx 新網站法人 insti/dailyTrade ══')
    newi: dict = {}
    for d in trading + nontrading:
        for kind in ('roc', 'greg'):
            lab = f'B 新法人 sect=EW date={_fmt(d, kind)}({kind}) {"交易日" if d in trading else "非交易日"}'
            j, dup = _tw_get(fetch_url, lab, 'https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade',
                             {'type': 'Daily', 'sect': 'EW', 'date': _fmt(d, kind), 'id': '',
                              'response': 'json'}, _TW_HDR_TPEX_NEW)
            newi[(d, kind)] = _tw_first_table(j)
            if isinstance(j, dict):
                print(f'   ↳ 請求日 {d} vs 回傳 date={j.get("date")!r} '
                      f'tables[0].date={(_tw_tables(j)[0].get("date") if _tw_tables(j) else None)!r} '
                      f'列數={len(newi[(d, kind)][1])}')
            if j is not None and not dup and d in trading and newi[(d, kind)][1]:
                _tw_analyze_insti(lab, *newi[(d, kind)])
    fmt_ok = 'greg' if newi.get(('2026-10-08', 'greg'), ([], []))[1] else (
        'roc' if newi.get(('2026-10-08', 'roc'), ([], []))[1] else 'greg')
    lab = f'B 新法人 sect=AL date={_fmt("2026-10-08", fmt_ok)}'
    j, dup = _tw_get(fetch_url, lab, 'https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade',
                     {'type': 'Daily', 'sect': 'AL', 'date': _fmt('2026-10-08', fmt_ok), 'id': '',
                      'response': 'json'}, _TW_HDR_TPEX_NEW)
    if isinstance(j, dict):
        f_al, r_al = _tw_first_table(j)
        f_ew, r_ew = newi.get(('2026-10-08', fmt_ok), ([], []))
        print(f'   ↳ AL 列數={len(r_al)} vs EW 列數={len(r_ew)};AL 獨有代號樣本='
              f'{sorted({str(r[0]) for r in r_al if r} - {str(r[0]) for r in r_ew if r})[:15]}')

    # ── C. 新網站收盤 ───────────────────────────────────────────────
    print('\n══ C. TPEx 新網站收盤 afterTrading/otc ══')
    newc: dict = {}
    for d in trading + nontrading:
        for kind in ('roc', 'greg'):
            lab = f'C 新收盤 type=EW date={_fmt(d, kind)}({kind}) {"交易日" if d in trading else "非交易日"}'
            j, dup = _tw_get(fetch_url, lab, 'https://www.tpex.org.tw/www/zh-tw/afterTrading/otc',
                             {'date': _fmt(d, kind), 'type': 'EW', 'id': '', 'response': 'json'},
                             _TW_HDR_TPEX_NEW)
            newc[(d, kind)] = _tw_first_table(j)
            if isinstance(j, dict):
                print(f'   ↳ 請求日 {d} vs 回傳 date={j.get("date")!r} '
                      f'tables[0].date={(_tw_tables(j)[0].get("date") if _tw_tables(j) else None)!r} '
                      f'列數={len(newc[(d, kind)][1])}')
            if j is not None and not dup and d in trading and newc[(d, kind)][1]:
                _tw_analyze_close(lab, *newc[(d, kind)])

    # 跨端點(舊 vs 新,10/08)
    ni = newi.get(('2026-10-08', 'greg'), ([], [])) if newi.get(('2026-10-08', 'greg'), ([], []))[1] \
        else newi.get(('2026-10-08', 'roc'), ([], []))
    nc = newc.get(('2026-10-08', 'greg'), ([], [])) if newc.get(('2026-10-08', 'greg'), ([], []))[1] \
        else newc.get(('2026-10-08', 'roc'), ([], []))
    for key in ('hedge', 'trade'):
        if old.get(key, ([], []))[1] and ni[1]:
            _tw_cross_cols(f'舊 {key} (A) → 新 dailyTrade (B) 10/08', old[key][0], old[key][1], ni[0], ni[1])
    if old.get('close', ([], []))[1] and nc[1]:
        _tw_cross_cols('舊 close (A) → 新 otc (B) 10/08', old['close'][0], old['close'][1], nc[0], nc[1])
    if ni[1]:
        # 全市場加總(股數)
        cls = _tw_net_classes([str(f) for f in ni[0]])
        print('\n   ▶ 全市場加總(新 dailyTrade 10/08,各淨額欄股數加總)')
        for k, i in cls.items():
            s = sum(v for v in (_tw_n(_tw_cell(r, i)) for r in ni[1]) if v is not None)
            print(f'     {k} [{i}] {ni[0][i]}: {s:,.0f}')

    # ── D. 市場合計(推測路徑) ─────────────────────────────────────────
    print('\n══ D. TPEx 三大法人市場彙總(路徑為推測,失敗即記錄) ══')
    for lab, params in (
        ('D insti/summary greg', {'type': 'Daily', 'date': '2026/10/08', 'response': 'json'}),
        ('D insti/summary roc', {'type': 'Daily', 'date': '115/10/08', 'response': 'json'}),
        ('D insti/summary greg+sect=EW', {'type': 'Daily', 'sect': 'EW', 'date': '2026/10/08',
                                          'response': 'json'}),
    ):
        _tw_get(fetch_url, lab, 'https://www.tpex.org.tw/www/zh-tw/insti/summary', params, _TW_HDR_TPEX_NEW)

    # ── E. TWSE T86 / BFI82U ──────────────────────────────────────
    print('\n══ E. TWSE T86 / BFI82U(Q-z24/Q-z25 口徑查證) ══')
    t86_done = False
    for lab, url, params in (
        ('E T86 rwd(任務指定)', 'https://www.twse.com.tw/rwd/zh/fund/T86',
         {'date': '20261008', 'selectType': 'ALL', 'response': 'json'}),
        ('E T86 /fund/T86(repo _get_t86_day 現行)', 'https://www.twse.com.tw/fund/T86',
         {'response': 'json', 'date': '20261008', 'selectType': 'ALL'}),
    ):
        j, dup = _tw_get(fetch_url, lab, url, params, _TW_HDR_TWSE)
        f, rows = _tw_first_table(j)
        if rows and not t86_done:
            t86_done = True
            fl = [str(x) for x in f]
            print('   [T86 指定欄位索引]')
            for want in ('外陸資買賣超股數(不含外資自營商)', '外資自營商買賣超股數', '投信買賣超股數',
                         '自營商買賣超股數', '自營商買賣超股數(自行買賣)', '自營商買賣超股數(避險)',
                         '三大法人買賣超股數'):
                print(f'     「{want}」 → idx={fl.index(want) if want in fl else "（無完全相符欄名）"}')
            _tw_analyze_insti(lab, f, rows)
        elif rows and t86_done:
            print('   (已於前一個 T86 請求完整驗算;此處只比對 fields 是否相同)')

    for lab, url, params in (
        ('E BFI82U rwd type=day&dayDate(任務指定)', 'https://www.twse.com.tw/rwd/zh/fund/BFI82U',
         {'type': 'day', 'dayDate': '20261008', 'response': 'json'}),
        ('E BFI82U rwd response&date(repo daily_data_fetchers 現行)',
         'https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json&date=20261008', None),
    ):
        j, dup = _tw_get(fetch_url, lab, url, params, _TW_HDR_TWSE)
        if isinstance(j, dict):
            f, rows = _tw_first_table(j)
            print(f'   [BFI82U 全部列] fields={f!r}')
            for r in rows:
                print(f'     {r!r}')
            print(f'   [BFI82U notes 原文] {j.get("notes")!r}')
            ts = _tw_tables(j)
            if ts and ts[0] is not j:
                print(f'   [BFI82U tables[0].notes] {ts[0].get("notes")!r}')

    # ── 4. FinMind 匿名 ───────────────────────────────────────────────
    _tw_finmind(fetch_url, ni, nc)

    print(f'\n══ 請求總結(共送出 {_TW_REQ_COUNT} 個 probe 請求,不含 fetch_url 內部降級重試) ══')
    for lab, res in _TW_SUMMARY:
        print(f'   • {lab} → {res}')
    return 0


def _legacy_main() -> int:
    """舊版預設段(v19.112~2026-08-27 PMI/出口探針);現需 `--legacy` 才執行。"""
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


def main(argv: list[str] | None = None) -> int:
    """CLI:無參數 → 只跑 TPEx/TWSE 欄位探針(probe workflow 不帶參數,即此段);
    `--legacy` → 只跑舊 PMI/出口探針;`--all` → 兩段都跑。"""
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--legacy' in argv:
        return _legacy_main()
    rc = probe_tpex_new_site()
    if '--all' in argv:
        rc = _legacy_main() or rc
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
