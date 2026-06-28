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
import requests, datetime, os, sys as _sys_prov_nas
import urllib3


# v18.355 PR-Q5a — S-PROV-1 phase 19 helper
# 4 fetcher (_fetch_institutional / _fetch_margin_balance / _fetch_export_yoy /
# _fetch_business_indicator) 共用 stderr audit trail。NAS server module,
# 介面 0 改 caller(Streamlit Cloud → /api endpoint)。
def _prov_log(fn_name: str, source: str, result_summary: str):
    """§2.2 provenance — stderr 記 source/fetched_at。"""
    try:
        _now = datetime.datetime.utcnow().isoformat() + 'Z'
        print(f'[{fn_name}] source={source} fetched_at={_now} '
              f'result={result_summary}', file=_sys_prov_nas.stderr)
    except Exception:
        pass
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI(title="NAS 中繼站", version="1.0.0")

_API_KEY = os.environ.get("NAS_API_KEY", "")
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
        _r = requests.get(
            url,
            headers={**_HDR, 'Accept': '*/*'},
            timeout=20,
            verify=False,
            allow_redirects=True,
        )
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
