"""
NAS 中繼站 FastAPI Server v1.0
在台灣家用 NAS (Synology/QNAP) 上執行，代 Streamlit Cloud 抓取受地區限制的台股資料。

【安裝相依套件】
  pip install fastapi uvicorn requests pandas

【設定 API Key（必填）】
  export NAS_API_KEY="your_strong_secret_key_2026"

【啟動】
  uvicorn nas_server:app --host 0.0.0.0 --port 8765

【Streamlit Cloud Secrets 設定】
  NAS_BASE_URL = "http://chen10021.synology.me:8765"
  NAS_API_KEY  = "your_strong_secret_key_2026"

【支援 action】
  institutional       — 三大法人買賣超（億元）
  margin_balance      — 大盤融資餘額（億元）
  export_yoy          — 台灣出口年增率（%）
  business_indicator  — 景氣燈號
"""
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import Response as _RawResponse
from pydantic import BaseModel
from typing import Optional
import ipaddress
import socket
import requests, datetime, os
import urllib3
from urllib.parse import urlparse


# v18.355 PR-Q5a — S-PROV-1 phase 19 helper
# 4 fetcher (_fetch_institutional / _fetch_margin_balance / _fetch_export_yoy /
# _fetch_business_indicator) 共用 stderr audit trail。NAS server module,
# 介面 0 改 caller(Streamlit Cloud → /api endpoint)。
# P2-1 v18.380:_prov_log 統一至 src/data/core/provenance.py
from src.data.core.provenance import prov_log as _prov_log_unified


def _prov_log(fn_name: str, source: str, result_summary: str):
    """§2.2 provenance — backward-compat shim(無 ticker 場景)。"""
    try:
        _prov_log_unified(fn_name, source, result_summary)
    except Exception:
        pass
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI(title="NAS 中繼站", version="1.0.0")

_API_KEY = os.environ.get("NAS_API_KEY", "")
# v19.86 安全（第八份 review D）:未設 NAS_API_KEY = `/proxy` `/api/fetch` 無認證
# 開放,任何人可把本機當跳板(SSRF)。此處大聲警告;硬性「未設 key 拒絕啟動」屬
# 部署行為變更,列 user 決定(見 PR 描述)。無論有無 key,下方 _assert_public_url
# 都會封鎖內網/metadata 目標,先堵住 SSRF 最危險面。
if not _API_KEY:
    print("=" * 72, flush=True)
    print("⚠️  [NAS 安全警告] NAS_API_KEY 未設定 — /proxy 與 /api/fetch 目前"
          "「無認證開放」!", flush=True)
    print("    任何知道本站網址者都可驅動本機發出 HTTP 請求。強烈建議:", flush=True)
    print('    export NAS_API_KEY="<高強度隨機字串>" 後重啟。', flush=True)
    print("    (SSRF 內網存取已由 _assert_public_url 封鎖,但認證仍應設定)", flush=True)
    print("=" * 72, flush=True)

_HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.twse.com.tw/",
    "X-Requested-With": "XMLHttpRequest",
}


# ── 認證 ──────────────────────────────────────────────────────────────────
def _auth(x_api_key: str = Header(None)):
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")


# ── SSRF 防護（第八份 review D，v19.86）────────────────────────────────────
# `/proxy?url=` 原本對任意 url 直接 requests.get → 可被用來打內網主機、雲端
# metadata endpoint(169.254.169.254)、localhost 服務等(SSRF)。此 guard 先解析
# 目標主機的 IP,凡落在私有/loopback/link-local/保留範圍一律拒絕。
#
# 涵蓋範圍:公開站(TWSE/FinMind/FRED/Yahoo 等)解析為公網 IP → 放行,零誤傷;
# 內網 IP / metadata / localhost → 擋。
# 已知限制:不防 DNS rebinding(解析時公網、requests 抓取時翻內網)—屬進階攻擊,
# 需 pin 已解析 IP,列後續強化(本 guard 已堵住直接以內網 URL 打進來的主要面)。
def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400,
                            detail=f"僅允許 http/https,拒絕 scheme={parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise HTTPException(status_code=400, detail="URL 缺 host")
    try:
        # 取得該主機所有解析結果(IPv4+IPv6),任一內網即拒
        infos = socket.getaddrinfo(host, parsed.port or None,
                                   proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        # 解析不了 → 讓 requests.get 自然失敗(不誤判為攻擊),但也抓不到內網
        return
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise HTTPException(
                status_code=403,
                detail=f"拒絕存取內網/保留位址 {ip_str}（SSRF 防護）")


class FetchReq(BaseModel):
    action: str
    date: Optional[str] = None
    token: Optional[str] = None


# ── 工具函數 ──────────────────────────────────────────────────────────────
def _num(s):
    try:
        return float(str(s).replace(",", "").replace(" ", "").replace("+", ""))
    except Exception:
        return None


def _tw_today():
    tz = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.now(tz).date()


def _recent_date():
    d = _tw_today()
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d.strftime("%Y%m%d")


# ── 三大法人 ──────────────────────────────────────────────────────────────
def _fetch_institutional(date_str: Optional[str] = None):
    if date_str is None:
        date_str = _recent_date()
    base = datetime.datetime.strptime(date_str, "%Y%m%d").date()

    for delta in range(5):
        d = base - datetime.timedelta(days=delta)
        if d.weekday() >= 5:
            continue
        ds = d.strftime("%Y%m%d")
        for url in [
            "https://www.twse.com.tw/rwd/zh/fund/BFI82U",
            "https://www.twse.com.tw/fund/BFI82U",
        ]:
            try:
                r = requests.get(
                    url,
                    params={"response": "json", "dayDate": ds},
                    headers=_HDR, timeout=10, verify=False)
                j = r.json()
                if j.get("stat") != "OK" or not j.get("data"):
                    continue
                fields = [str(f) for f in j.get("fields", [])]
                diff_idx = next(
                    (i for i, f in enumerate(fields) if "差額" in f and "張" not in f), 3)
                raw = {}
                for row in j["data"]:
                    name = str(row[0]).strip()
                    if "合計" in name:
                        continue
                    if len(row) > diff_idx:
                        v = _num(row[diff_idx])
                        if v is not None:
                            raw[name] = round(v / 1e8, 2)
                if not raw:
                    continue
                dealer = sum(v for k, v in raw.items() if "自營商" in k)
                foreign = next((v for k, v in raw.items() if "外資" in k and "陸資" in k), None)
                if foreign is None:
                    foreign = next((v for k, v in raw.items() if "外資" in k), 0)
                trust = next((v for k, v in raw.items() if "投信" in k), 0)
                print(f"[NAS/institutional] ✅ {ds}: 外資={foreign:.1f} 投信={trust:.1f} 自營={dealer:.1f}億")
                _prov_log('_fetch_institutional', f'TWSE:BFI82U(NAS direct):date={ds}',
                          f'dict:3-investors')
                return {
                    "外資及陸資": {"net": round(foreign, 2)},
                    "投信":       {"net": round(trust, 2)},
                    "自營商":     {"net": round(dealer, 2)},
                }
            except Exception as e:
                print(f"[NAS/institutional/{ds}] {url.split('/')[-1]}: {e}")
    print("[NAS/institutional] ❌ 所有日期/來源失敗")
    _prov_log('_fetch_institutional', 'TWSE:BFI82U(NAS direct):all-dates-fail',
              'None:5-days-all-fail')
    return None


# ── 融資餘額 ──────────────────────────────────────────────────────────────
def _fetch_margin_balance(date_str: Optional[str] = None):
    today = _tw_today()
    candidates = []
    d = today
    for _ in range(8):
        if d.weekday() < 5:
            candidates.append(d)
        d -= datetime.timedelta(days=1)
        if len(candidates) >= 4:
            break

    for _d in candidates:
        ds = _d.strftime("%Y%m%d")
        try:
            r = requests.get(
                "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN",
                params={"date": ds, "selectType": "ALL", "response": "json"},
                headers={**_HDR, "Referer": "https://www.twse.com.tw/zh/trading/margin/mi-margn.html"},
                timeout=10, verify=False)
            j = r.json()
            if j.get("stat") != "OK":
                continue
            data = j.get("data", [])
            if not data:
                continue
            fields = [str(f) for f in j.get("fields", [])]
            margin_col = next(
                (i for i, f in enumerate(fields) if "融資" in f and "餘額" in f and "限" not in f), 6)
            for row in reversed(data):
                if len(row) <= margin_col:
                    continue
                raw = str(row[margin_col]).replace(",", "").replace(" ", "")
                try:
                    v = float(raw)
                except Exception:
                    continue
                if v > 10_000_000:
                    result = round(v / 100_000, 1)
                    if 500 < result < 10000:
                        print(f"[NAS/margin_balance] ✅ {ds}: {result}億")
                        _prov_log('_fetch_margin_balance',
                                  f'TWSE:MI_MARGN(NAS direct):date={ds}:仟元÷100000',
                                  f'float:{result}億')
                        return result
                elif v > 1_000_000:
                    result = round(v / 10_000, 1)
                    if 500 < result < 10000:
                        print(f"[NAS/margin_balance] ✅ {ds}: {result}億(萬元)")
                        _prov_log('_fetch_margin_balance',
                                  f'TWSE:MI_MARGN(NAS direct):date={ds}:萬元÷10000',
                                  f'float:{result}億')
                        return result
        except Exception as e:
            print(f"[NAS/margin_balance/{ds}] {e}")

    print("[NAS/margin_balance] ❌ 所有日期失敗")
    _prov_log('_fetch_margin_balance', 'TWSE:MI_MARGN(NAS direct):all-dates-fail',
              'None:4-days-all-fail')
    return None


# ── 台灣出口年增率 ────────────────────────────────────────────────────────
def _fetch_export_yoy():
    # 財政部統計資料
    urls = [
        "https://service.mof.gov.tw/public/Data/statistic/trade/efile/totalEstat-en.csv",
        "https://www.mof.gov.tw/API/statistics/trade/total",
    ]
    for url in urls:
        try:
            r = requests.get(
                url, headers={"User-Agent": _HDR["User-Agent"]},
                timeout=15, verify=False)
            if r.status_code == 200 and r.text.strip():
                lines = r.text.strip().split("\n")
                for line in reversed(lines[1:]):
                    parts = [p.strip().strip('"') for p in line.split(",")]
                    if len(parts) >= 3:
                        try:
                            yoy = float(str(parts[2]).replace("%", ""))
                            date_str = parts[0]
                            print(f"[NAS/export_yoy] ✅ {date_str}: {yoy}%")
                            _prov_log('_fetch_export_yoy',
                                      f'MOF:trade(NAS direct):{url[-40:]}',
                                      f'dict:value={yoy}%:date={date_str}')
                            return {"value": yoy, "date": date_str}
                        except Exception:
                            continue
        except Exception as e:
            print(f"[NAS/export_yoy] {url}: {e}")
    print("[NAS/export_yoy] ❌ 所有來源失敗")
    _prov_log('_fetch_export_yoy', 'MOF:trade(NAS direct):all-urls-fail',
              'None:2-urls-all-fail')
    return None


# ── 景氣燈號 ──────────────────────────────────────────────────────────────
def _fetch_business_indicator():
    urls = [
        "https://index.ndc.gov.tw/app/data/indicator/composite",
        "https://index.ndc.gov.tw/app/data/indicator/latest",
    ]
    for url in urls:
        try:
            r = requests.get(
                url,
                headers={"User-Agent": _HDR["User-Agent"], "Accept": "application/json"},
                timeout=15, verify=False)
            if r.status_code == 200:
                j = r.json()
                items = j if isinstance(j, list) else j.get("data", [])
                if items:
                    latest = items[-1] if isinstance(items, list) else items
                    result = {
                        "signal": str(latest.get("lightColor") or latest.get("signal") or ""),
                        "score":  int(latest.get("score") or latest.get("composite") or 0),
                        "date":   str(latest.get("date") or latest.get("yearMonth") or ""),
                    }
                    print(f"[NAS/business_indicator] ✅ {result}")
                    _prov_log('_fetch_business_indicator',
                              f'NDC:{url[-30:]}(NAS direct)',
                              f'dict:signal={result["signal"]}:score={result["score"]}')
                    return result
        except Exception as e:
            print(f"[NAS/business_indicator] {url}: {e}")
    print("[NAS/business_indicator] ❌ 所有來源失敗")
    _prov_log('_fetch_business_indicator', 'NDC(NAS direct):all-urls-fail',
              'None:2-urls-all-fail')
    return None


# ── API Endpoints ─────────────────────────────────────────────────────────

@app.get("/proxy")
@app.post("/proxy")
def proxy_relay(url: str, _=Depends(_auth)):
    """
    通用 URL 透明中繼端點 v1.0
    以台灣 IP 代為抓取任意 URL，原封不動轉發 HTTP Status + Content-Type + Body。
    用法：GET {NAS_BASE_URL}/proxy?url=https://www.twse.com.tw/...
    """
    try:
        # v19.86 SSRF 防護:每一跳(初始 + 每次轉址)都先過 _assert_public_url
        # 再抓,防「公開 URL 302 → 內網」繞過。手動有界迴圈保留多層轉址支援。
        _cur = url
        _r = None
        for _hop in range(6):  # 上限 6 跳,足夠合法 http→https→final;逾則截斷
            _assert_public_url(_cur)
            _r = requests.get(
                _cur,
                headers={**_HDR, 'Accept': '*/*'},
                timeout=20,
                verify=False,
                allow_redirects=False,
            )
            if _r.is_redirect and _r.headers.get('Location'):
                _cur = requests.compat.urljoin(_cur, _r.headers['Location'])
                continue
            break
        print(f'[NAS/proxy] ✅ {url[:80]} HTTP {_r.status_code}')
        return _RawResponse(
            content=_r.content,
            status_code=_r.status_code,
            media_type=_r.headers.get('Content-Type', 'application/octet-stream'),
        )
    except Exception as _e_px:
        print(f'[NAS/proxy] ❌ {url[:80]} {type(_e_px).__name__}: {_e_px}')
        raise HTTPException(status_code=502, detail=f'中繼失敗: {_e_px}')


@app.get("/")
def health():
    return {
        "status": "ok",
        "service": "NAS 中繼站 v1.0",
        "time": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        "actions": ["institutional", "margin_balance",
                    "export_yoy", "business_indicator"],
    }


@app.post("/api/fetch")
def fetch(req: FetchReq, _=Depends(_auth)):
    _dispatch = {
        "institutional":      lambda: _fetch_institutional(req.date),
        "margin_balance":     lambda: _fetch_margin_balance(req.date),
        "export_yoy":         lambda: _fetch_export_yoy(),
        "business_indicator": lambda: _fetch_business_indicator(),
    }
    handler = _dispatch.get(req.action)
    if handler is None:
        raise HTTPException(status_code=400, detail=f"未知 action: {req.action}")

    data = handler()
    return {
        "status": "ok" if data is not None else "failed",
        "data":   data,
        "action": req.action,
    }
