"""update_etf_managers.py — GitHub Actions 爬蟲：抓 ETF 經理人並維護換手歷史。

資料流（與新聞 etf_profile_fetcher.py 同套路）：
  etf_manager_watchlist.json（追蹤清單）
        │  經 PROXY_URL 代理 → 抓 MoneyDJ 經理人頁 → 解析現任經理人 + 到職日
        ▼
  etf_managers.json：每檔 {name, since, tenure_days, last_seen, history[]}
        └─ 名字與上次不同 → 寫一筆 history（from→to + detected_at）

為何要這支：app 端的換手偵測原本只寫 /tmp，Streamlit Cloud 容器重啟即清空，
紅色「經理人異動」框幾乎不會跳。改由 Actions 定期抓 → commit 此 JSON →
app 讀檔當持久基準，換手紀錄就能跨重啟存活。

相依現況（2026-08-25 更正 —— 原文宣稱「無 pandas 相依」已不成立）:
  本腳本自己只用 requests / urllib3,不碰 streamlit、不碰 pandas、不碰 DataFrame。
  **但** 它要的 `fetch_url` 住在 `src/data/proxy/proxy_helper.py`,而 Python 取用
  子模組前必先執行 package 的 `__init__.py`,那裡有一行
  `from . import proxy_helper, yf_proxy` —— sibling `yf_proxy` 需要 pandas。
  於是 runner 上會炸 `ModuleNotFoundError: No module named 'pandas'`。

  為什麼不改 barrel 改成 lazy import:試過,會同時打斷兩個由實際事故長出來的守衛
  ——`tests/test_c3_layering_guard.py` 的 `_barrel_exports()` 用 AST 認那一行的固定
  寫法(改掉它就靜默失效、判不出 risk_radar 的分層違憲),以及
  `tests/test_zz_proxy_pollution_lock.py`(v19.74 / v19.113 兩次 order-dependent
  事故的鎖,只允許三個實體屬性)。為了在一支週更 workflow 上省十幾秒安裝時間,
  去動兩個事故催生的守衛,不划算(CLAUDE.md §8.1 step 6)。故改為誠實安裝 pandas。

連線統一走 proxy_helper（讀 env 的 PROXY_URL）。
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

# `python scripts/update_etf_managers.py` 直跑時 sys.path[0]=scripts/,不含 repo root
# → 下方 `src.*` import 必 ImportError。同 update_macro_history.py v19.101 既有模式。
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# 與 reader(src/data/etf/etf_fetch.py)同目錄 —— reader 以 __file__ 相對路徑讀取,
# 故持久檔須與其 co-locate(F-6.2 src/ 搬移曾把 etf_fetch.py 移入 src/data/etf/ 卻
# 遺留 JSON 在 root,導致 reader 讀不到 → 換手紅框跨重啟失效;B2 v19.152 歸位修復)。
_ETF_DATA_DIR = Path(__file__).resolve().parents[1] / "src" / "data" / "etf"
WATCHLIST_PATH = _ETF_DATA_DIR / "etf_manager_watchlist.json"
MANAGERS_PATH = _ETF_DATA_DIR / "etf_managers.json"
REQUEST_GAP_SEC = 0.6

# MoneyDJ 經理人相關頁（簡介頁 Basic0004 通常就有「經理人」欄，擺第一）
PAGE_TEMPLATES = [
    "https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid={etfid}",
    "https://www.moneydj.com/ETF/X/Basic/Basic0001.xdjhtm?etfid={etfid}",
    "https://www.moneydj.com/ETF/X/Basic/Basic0006.xdjhtm?etfid={etfid}",
    "https://www.moneydj.com/ETF/X/Basic/Basic0011.xdjhtm?etfid={etfid}",
]


def _html_kv_pairs(html_text: str) -> dict:
    """把 HTML 表格 td/th 相鄰儲存格配成 {欄位名: 值}（與 etf_fetch._html_kv_pairs 同法）。"""
    class _Cells(HTMLParser):
        def __init__(self):
            super().__init__()
            self.cells, self._buf = [], None

        def handle_starttag(self, tag, attrs):
            if tag in ("td", "th"):
                self._buf = []

        def handle_data(self, data):
            if self._buf is not None:
                self._buf.append(data)

        def handle_endtag(self, tag):
            if tag in ("td", "th") and self._buf is not None:
                self.cells.append(re.sub(r"\s+", " ", "".join(self._buf)).strip())
                self._buf = None

    p = _Cells()
    try:
        p.feed(html_text or "")
    except Exception:
        return {}
    cells = [c for c in p.cells if c]
    kv: dict = {}
    for i in range(len(cells) - 1):
        key = cells[i].rstrip(":： ").strip()
        val = cells[i + 1].strip()
        if val and key and key not in kv and len(key) <= 12 and re.search(r"[一-鿿]", key):
            kv[key] = val
    return kv


def _parse_manager(html_text: str) -> dict | None:
    """從一頁 HTML 解析現任經理人 + 到職日。回 {name, since, tenure_days} 或 None。"""
    kv = _html_kv_pairs(html_text)
    name_raw = ""
    for k in ("基金經理人", "現任經理人", "經理人"):
        if k in kv:
            name_raw = kv[k]
            break
    if not name_raw:
        for k, v in kv.items():
            if "經理" in k:
                name_raw = v
                break
    m = re.search(r"[一-鿿]{2,8}", name_raw)  # 取首段中文，避開「、」多人共管
    if not m:
        return None
    name = m.group(0)

    since, tenure_days = None, None
    dt_raw = ""
    for k in ("到職日", "上任日", "派任日", "起聘日", "管理基金日", "任期"):
        if k in kv:
            dt_raw = kv[k]
            break
    dm = re.search(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", dt_raw)
    if dm:
        try:
            d = date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
            since = d.strftime("%Y-%m-%d")
            tenure_days = (date.today() - d).days
        except ValueError:
            pass
    return {"name": name, "since": since, "tenure_days": tenure_days}


def fetch_manager(etfid: str) -> dict | None:
    """逐頁抓 MoneyDJ 經理人；名字有、到職日缺時續查其他頁（與 app 端同策略）。"""
    # v18.359 檔案搬家後根目錄 shim 已刪,舊的 `import proxy_helper` 恆 ImportError
    # → 本 workflow 自 2026-06-29 起連續 9 次 red。改正式路徑(同 v19.101 對
    # update_macro_history.py 的修法)。
    # 這裡刻意**不**做「直連 fallback」:MoneyDJ 擋海外 IP,GitHub runner 直連必敗,
    # 補 fallback 只會把 ImportError(程式 bug)偽裝成「查無經理人」(§1 Fail Loud)。
    from src.data.proxy.proxy_helper import fetch_url

    best = None
    for tmpl in PAGE_TEMPLATES:
        url = tmpl.format(etfid=etfid)
        try:
            r = fetch_url(
                url, headers={"Referer": "https://www.moneydj.com/"},
                timeout=15, attempts=2)
        except Exception as e:
            print(f"  [{etfid}] {url[-28:]}: {type(e).__name__}: {e}")
            continue
        if r is None or r.status_code != 200 or len(r.text or "") < 500:
            code = r.status_code if r is not None else "None"
            print(f"  [{etfid}] {url[-28:]}: HTTP {code}")
            time.sleep(REQUEST_GAP_SEC)
            continue
        try:
            r.encoding = "utf-8"
        except Exception:
            pass
        parsed = _parse_manager(r.text)
        time.sleep(REQUEST_GAP_SEC)
        if parsed:
            if parsed.get("since"):
                # v18.357 PR-Q5c S-PROV-1 phase 19
                try:
                    import sys as _sys_em, datetime as _dt_em
                    print(f'[fetch_manager] etfid={etfid} '
                          f'source=MoneyDJ:Basic(multi-page) '
                          f'fetched_at={_dt_em.datetime.utcnow().isoformat()}Z '
                          f'result=dict:name={parsed.get("name","?")}:since={parsed.get("since")}',
                          file=_sys_em.stderr)
                except Exception:
                    pass
                return parsed          # 名字+到職日齊全，最佳
            if best is None:
                best = parsed          # 名字有、到職日缺 → 暫存，續查其他頁
    # v18.357 PR-Q5c:暫存最佳 or None
    try:
        import sys as _sys_em2, datetime as _dt_em2
        print(f'[fetch_manager] etfid={etfid} '
              f'source=MoneyDJ:Basic(multi-page:fallback) '
              f'fetched_at={_dt_em2.datetime.utcnow().isoformat()}Z '
              f'result={"dict:name="+best.get("name","?") if best else "None"}',
              file=_sys_em2.stderr)
    except Exception:
        pass
    return best


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠️ 讀 {path} 失敗（{e}），用預設值")
    return default


def main() -> int:
    wl = load_json(WATCHLIST_PATH, {})
    tickers = wl.get("tickers") or []
    if not tickers:
        print("❌ etf_manager_watchlist.json 無 tickers，結束")
        return 1

    db = load_json(MANAGERS_PATH, {"managers": {}})
    managers: dict = db.get("managers") or {}
    today = date.today().isoformat()

    changed_cnt, ok_cnt, fail_cnt = 0, 0, 0
    for ticker in tickers:
        etfid = ticker.strip().upper()
        if "." not in etfid:
            etfid = f"{etfid}.TW"
        res = fetch_manager(etfid)
        if not res or not res.get("name"):
            fail_cnt += 1
            print(f"✗ {etfid}: 查無經理人")
            continue
        ok_cnt += 1
        name = res["name"]
        rec = managers.get(etfid) or {}
        prev = rec.get("name")
        if prev and prev != name:                       # 偵測到換手
            changed_cnt += 1
            hist = rec.get("history") or []
            hist.append({"from": prev, "to": name, "detected_at": today,
                         "since": res.get("since")})
            rec["history"] = hist[-20:]
            # 經理人換新 → first_seen 重設為今天（新任期起點）
            rec["first_seen"] = today
            print(f"🔁 {etfid}: 經理人異動 {prev} → {name}")
        else:
            rec.setdefault("history", rec.get("history", []))
            # 首次紀錄此經理人時設 first_seen（後續不動，當 MoneyDJ 未揭露到職日的備援）
            rec.setdefault("first_seen", today)
            print(f"✓ {etfid}: {name}"
                  + (f"（到職 {res['since']}）" if res.get("since") else "（到職日未揭露）"))
        rec.update({"name": name, "since": res.get("since"),
                    "tenure_days": res.get("tenure_days"), "last_seen": today})
        managers[etfid] = rec

    # §1 Fail Loud:清單非空卻一檔都沒抓到 = 上游全敗,不可寫檔又回 0 裝成功
    # (那會讓「MoneyDJ 全面擋掉」看起來跟「本週經理人都沒換」一模一樣)。
    if ok_cnt == 0:
        print(f"\n❌ {len(tickers)} 檔全數抓取失敗,不覆寫 {MANAGERS_PATH.name}")
        return 1

    db["managers"] = managers
    db["updated_at"] = datetime.now(timezone.utc).isoformat()
    MANAGERS_PATH.write_text(
        json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n📊 完成：成功 {ok_cnt} / 失敗 {fail_cnt} / 換手 {changed_cnt}，已寫 {MANAGERS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
