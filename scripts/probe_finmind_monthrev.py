"""scripts/probe_finmind_monthrev.py — FinMind TaiwanStockMonthRevenue 欄位語意唯讀探針(DEC-152/153/154)。

目的:在『有合法 FINMIND_TOKEN 的 workflow_dispatch 環境』取少量真實樣本,**只輸出非敏感結構化證據**,
供客戶/總管判讀 `date` 與 `revenue_year`/`revenue_month` 的關係。

硬性邊界(違反任一條 = 停手):
  · 唯讀:不寫檔、不改 repo、不 commit、不推播、不呼叫任何 production writer。
  · 不輸出 token / Authorization header / 完整 request headers / 環境變數;所有輸出(含例外)經 `_redact`。
  · token 只走 Authorization: Bearer header,不進 URL/params、不進 log。
  · 無 token → 明確 exit 2 並印「NOT VERIFIED」,**不連網**、不虛構。
  · 本探針**不改** `BATCH_SOURCE_MONTH_KEY_VERIFIED` 或任何 repo 檔;只報告觀察到的關係,不下結論。
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date, timedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

DATASET = "TaiwanStockMonthRevenue"
DEFAULT_STOCK_IDS = "2330,2317,2454"
DEFAULT_MONTHS = 6
MAX_MONTHS = 12
MAX_STOCKS = 5
SHOW_REVENUE_ROWS = 3          # 每檔僅輸出前 N 列 revenue 數值
TIMEOUT_S = 20
_STOCK_ID_RE = re.compile(r"^[0-9A-Za-z]{1,8}$")
_BEARER_RE = re.compile(r"(?i)bearer\s+\S+")

NO_TOKEN_MSG = "NOT VERIFIED：無 FINMIND_TOKEN，未取樣"


def _secrets(env) -> list[str]:
    tok = (env.get("FINMIND_TOKEN") or "").strip()
    return [tok] if len(tok) >= 1 else []


def make_redactor(env):
    secs = sorted(_secrets(env), key=len, reverse=True)

    def _redact(s) -> str:
        s = str(s)
        for sec in secs:
            s = s.replace(sec, "***")
        return _BEARER_RE.sub("Bearer ***", s)

    return _redact


def parse_inputs(stock_ids_raw: str | None, months_raw: str | None) -> tuple[list[str], int, list[str]]:
    """驗證並截斷輸入:stock 數 ≤ MAX_STOCKS、代號僅英數 ≤8 碼、months ∈ [1, MAX_MONTHS]。回 (ids, months, notes)。"""
    notes: list[str] = []
    ids: list[str] = []
    for part in (stock_ids_raw or DEFAULT_STOCK_IDS).split(","):
        p = part.strip()
        if not p:
            continue
        if not _STOCK_ID_RE.match(p):
            notes.append("略過格式不合的代號(僅允許 1~8 碼英數)")
            continue
        if p not in ids:
            ids.append(p)
    if not ids:
        ids = DEFAULT_STOCK_IDS.split(",")
        notes.append("無有效代號,改用預設")
    if len(ids) > MAX_STOCKS:
        notes.append(f"代號數 {len(ids)} 超過上限,截斷為前 {MAX_STOCKS} 檔")
        ids = ids[:MAX_STOCKS]
    try:
        months = int(str(months_raw).strip()) if months_raw not in (None, "") else DEFAULT_MONTHS
    except ValueError:
        months = DEFAULT_MONTHS
        notes.append(f"months 非整數,改用預設 {DEFAULT_MONTHS}")
    if months < 1:
        months = 1
        notes.append("months < 1,調為 1")
    if months > MAX_MONTHS:
        notes.append(f"months 超過上限,截斷為 {MAX_MONTHS}")
        months = MAX_MONTHS
    return ids, months, notes


def _parse_date(s):
    try:
        y, m, d = str(s)[:10].split("-")
        return date(int(y), int(m), int(d))
    except Exception:  # noqa: BLE001 — 解析失敗以 None 表示,後續歸「其他/無法解析」
        return None


def _ym(row) -> tuple[int, int] | None:
    try:
        return int(row["revenue_year"]), int(row["revenue_month"])
    except (KeyError, TypeError, ValueError):
        return None


def _next_ym(y: int, m: int) -> tuple[int, int]:
    return (y + 1, 1) if m == 12 else (y, m + 1)


def analyze(rows: list[dict]) -> dict:
    """純函式:回傳結構化觀察(不下結論)。"""
    cols = sorted({k for r in rows for k in r.keys()})
    have_ym = bool(rows) and all(("revenue_year" in r and "revenue_month" in r) for r in rows)
    rel = {"同月(date年月=營收年月)": 0, "date=次月1日": 0, "其他": 0, "無法解析": 0}
    ym_list: list[tuple[int, int]] = []
    if have_ym:
        for r in rows:
            ym = _ym(r)
            d = _parse_date(r.get("date"))
            if ym is None or d is None:
                rel["無法解析"] += 1
                continue
            ym_list.append(ym)
            if (d.year, d.month) == ym:
                rel["同月(date年月=營收年月)"] += 1
            elif d.day == 1 and (d.year, d.month) == _next_ym(*ym):
                rel["date=次月1日"] += 1
            else:
                rel["其他"] += 1
    dups = sorted({ym for ym in ym_list if ym_list.count(ym) > 1})
    missing: list[tuple[int, int]] = []
    if ym_list:
        have = set(ym_list)
        cur, hi = min(ym_list), max(ym_list)
        while cur <= hi:
            if cur not in have:
                missing.append(cur)
            cur = _next_ym(*cur)
    dates = [_parse_date(r.get("date")) for r in rows]
    date_mono = all(a is not None and b is not None and a <= b for a, b in zip(dates, dates[1:]))
    ym_mono = all(a <= b for a, b in zip(ym_list, ym_list[1:]))
    return {"n": len(rows), "cols": cols, "have_ym": have_ym, "rel": rel, "dups": dups,
            "missing": missing, "date_mono": date_mono, "ym_mono": ym_mono}


def fetch_rows(stock_id: str, months: int, token: str, http_get, today: date | None = None) -> dict:
    """單檔取數。回 {http, api_status, msg, rows, error};token 只放 Authorization header。"""
    from src.config.config import FINMIND_API_URL
    t = today or date.today()
    start = (t - timedelta(days=31 * (months + 1))).isoformat()
    params = {"dataset": DATASET, "data_id": stock_id, "start_date": start}
    hdrs = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    out = {"http": None, "api_status": None, "msg": "", "rows": [], "error": None}
    try:
        r = http_get(FINMIND_API_URL, params=params, headers=hdrs, timeout=TIMEOUT_S)
        out["http"] = getattr(r, "status_code", None)
        body = r.json()
        out["api_status"] = body.get("status")
        out["msg"] = str(body.get("msg", ""))
        if out["api_status"] == 200 and out["http"] in (None, 200):
            data = body.get("data") or []
            out["rows"] = [x for x in data if isinstance(x, dict)]
    except Exception as e:  # noqa: BLE001 — 例外只回型別+(遮蔽後)訊息,由 caller 遮蔽輸出
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def run(env=None, http_get=None, out=print, today: date | None = None) -> int:
    env = os.environ if env is None else env
    redact = make_redactor(env)

    def emit(s: str = "") -> None:
        out(redact(s))

    token = (env.get("FINMIND_TOKEN") or "").strip()
    if not token:
        emit(NO_TOKEN_MSG)
        emit("本探針不改 verified 旗標(BATCH_SOURCE_MONTH_KEY_VERIFIED 維持原狀)")
        return 2
    if http_get is None:
        import requests
        http_get = requests.get

    ids, months, notes = parse_inputs(env.get("PROBE_STOCK_IDS"), env.get("PROBE_MONTHS"))
    emit(f"== FinMind {DATASET} 唯讀探針 ==  stocks={ids} months={months}")
    for n in notes:
        emit(f"[輸入調整] {n}")
    emit("本探針不改 verified 旗標(BATCH_SOURCE_MONTH_KEY_VERIFIED 維持原狀)")
    failed = 0
    for sid in ids:
        emit(f"--- {sid} ---")
        res = fetch_rows(sid, months, token, http_get, today)
        emit(f"HTTP={res['http']} api_status={res['api_status']} msg={res['msg']!r}")
        if res["error"]:
            emit(f"❌ 例外 {res['error']}")
            failed += 1
            continue
        if res["api_status"] != 200:
            emit("❌ API status != 200,無資料可分析")
            failed += 1
            continue
        a = analyze(res["rows"])
        emit(f"列數={a['n']} 欄位={a['cols']}")
        if not a["have_ym"]:
            emit("⚠️ 欄位缺失:revenue_year/revenue_month 非每列皆有 → 無法比對 date 與年月鍵")
        else:
            emit(f"date 與 (revenue_year,revenue_month) 關係統計: {a['rel']}")
        emit(f"重複(year,month)={a['dups']}  缺月(觀察區間內)={a['missing']}")
        emit(f"單調性: date 遞增={a['date_mono']}  (year,month) 遞增={a['ym_mono']}")
        for i, r in enumerate(res["rows"]):
            rev = r.get("revenue") if i < SHOW_REVENUE_ROWS else "(略)"
            emit(f"  date={r.get('date')} revenue_year={r.get('revenue_year')} "
                 f"revenue_month={r.get('revenue_month')} revenue={rev}")
    emit("== NOT VERIFIED 清單(本探針不下結論) ==")
    emit("1. 公告時點:FinMind 不提供逐列公告日,無法由此證實")
    emit("2. date 語意是否等於公布月:僅報告上列觀察到的關係,不下結論")
    emit("3. 是否 PIT(point-in-time):未驗證")
    emit("本探針不改 verified 旗標;BATCH_SOURCE_MONTH_KEY_VERIFIED 之翻轉須另經客戶 Decision Gate")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
