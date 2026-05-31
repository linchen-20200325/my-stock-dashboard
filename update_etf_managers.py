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

刻意維持「無 streamlit / 無 pandas」相依，只用 requests/urllib3 + proxy_helper，
在 Actions runner 上 `pip install requests urllib3` 即可跑（沙箱無網路抓不到屬正常）。
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

WATCHLIST_PATH = Path("etf_manager_watchlist.json")
MANAGERS_PATH = Path("etf_managers.json")
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
    import proxy_helper

    best = None
    for tmpl in PAGE_TEMPLATES:
        url = tmpl.format(etfid=etfid)
        try:
            r = proxy_helper.fetch_url(
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
                return parsed          # 名字+到職日齊全，最佳
            if best is None:
                best = parsed          # 名字有、到職日缺 → 暫存，續查其他頁
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

    db["managers"] = managers
    db["updated_at"] = datetime.now(timezone.utc).isoformat()
    MANAGERS_PATH.write_text(
        json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n📊 完成：成功 {ok_cnt} / 失敗 {fail_cnt} / 換手 {changed_cnt}，已寫 {MANAGERS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
