"""scripts/update_sector_flow.py — 板塊資金泡泡圖每日資料管線(L1 cron entrypoint)。

資料流(entrypoint 編排 L1 fetch → L2 pure → parquet;類比 update_macro_history.py)
==================================================================================
  _get_t86_day / _get_tpex_day (L1, 三大法人淨買超【張】) ┐
  fetch_twse_close_day / fetch_tpex_close_day (L1, 收盤【元】)├─→ sector_flow.compute_* (L2, 純)
  fetch_industry_map_bulk (L1, 產業別)                    ┘         ↓
                                          data_cache/sector_flow/daily_net.parquet(SSOT 日頻長表)
                                          data_cache/sector_flow/bubble_latest.json(秒讀泡泡座標)
                                          data_cache/sector_flow/metadata.json

每晚 TW 17:30(收盤後)跑:
- incremental:讀既有 parquet last_date → 只補 (last+1 .. today) 的交易日(通常 1 日)
- --bootstrap:回抓近 `--days` 日曆日(預設 30 ≈ 20 交易日,湊滿 WINDOW_SIZE)
- 走與畫面同源的 L1 fetcher(T86 selectType=ALL / TPEX 3itrade / MI_INDEX / TPEX 收盤)
- 直連即可(fetch_url 內 PROXY_URL 未設自動降級直連,官方 endpoint 全球可達)

§1 Fail Loud, Never Fake
------------------------
- 某交易日**三大法人全空**(假日/來源全敗)→ 該日整日跳過,不寫假(§4.6 自然排除)。
- 某日有法人淨額但**收盤全缺** → L2 inner-join 會剔除該日全部股 + coverage 計數;
  metadata 記 `days_missing_price` 供排查(不補價、不 ffill,§4.6 停牌不可 ffill)。
- **全部交易日皆無有效資料** → 不覆寫既有 parquet + 非零 exit(§1 寧缺勿錯)。
- 冪等(§5):同交易日重跑覆蓋同 (date,sector) 列(dedupe keep='last'),不產重複。

批 Z39(客戶 Q-z26=A / Q-z28=A):逐日分市場判定(上市 TWSE / 上櫃 TPEx 各自成敗)
------------------------------------------------------------------------------
- TWSE ok ＝ T86 非空 且 MI_INDEX 收盤非空 且 兩者代號交集 > 0。
- TPEx ok ＝ 3itrade 非空 且 `get_tpex_day_status(ds) == "ok"` 且 TPEx 收盤非空 且 交集 > 0。
- **invariant**:當日 TWSE/TPEx 任一有法人資料(交易日)而 TPEx 回空 / 非 JSON / 欄位驗證失敗 /
  收盤空 / 交集 0 → TPEx **失敗**(不是假日),不得標 TPEx success;該日 TPEx 法人列**不納入**
  彙總(讓該日一致只含上市),`source` 只列實際成功的市場。
- TWSE 失敗(僅 TPEx 成功或兩邊都失敗)的交易日 → **不寫入**,記入 metadata `unresolved_days`。
- 兩邊法人都空 → 假日/休市(跳過)。
- 法人分項缺鍵 → NaN(不是 0);bubble_latest.json 的 NaN 一律寫成 `null`(不寫非標準 NaN token)。

CLI
===
    python scripts/update_sector_flow.py                 # 每晚增量(補最新交易日)
    python scripts/update_sector_flow.py --bootstrap     # 回抓近 30 日曆日
    python scripts/update_sector_flow.py --days 45       # 自訂 bootstrap 回溯日曆天
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# repo root 上 sys.path(同 update_macro_history / update_fundamentals_snapshot 慣例)
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.sector_flow_thresholds import WINDOW_SIZE  # noqa: E402
from src.compute.sector_flow import (  # noqa: E402
    compute_bubble,
    compute_sector_daily_net,
)
from src.data.core.data_loader_inst_fetchers import (  # noqa: E402
    TPEX_DAY_STATUS_OK,
    _get_t86_day,
    _get_tpex_day,
    get_tpex_day_status,
)
from src.data.stock.market_close_fetcher import (  # noqa: E402
    fetch_industry_map_bulk,
    fetch_tpex_close_day,
    fetch_twse_close_day,
    get_tpex_close_status,
)

CACHE_DIR = Path("data_cache/sector_flow")
PARQUET_PATH = CACHE_DIR / "daily_net.parquet"
BUBBLE_PATH = CACHE_DIR / "bubble_latest.json"
META_PATH = CACHE_DIR / "metadata.json"
#: Stage 2 UI 秒讀:{裸股號: 產業別},供把使用者持股對映板塊(highlight)。
TICKER_SECTOR_PATH = CACHE_DIR / "ticker_sector.json"

#: bootstrap 預設回溯日曆天(≈ 20 交易日 + 週末/短假緩衝,湊滿 WINDOW_SIZE)。
_DEFAULT_BOOTSTRAP_DAYS = 30
#: 交易日軸鍵。
_DEDUPE_KEYS = ["date", "sector"]
#: 批 Z39:`source` 欄依日只列實際成功使用的市場。
_SOURCE_TWSE = "TWSE:T86+MI_INDEX"
_SOURCE_TPEX = "TPEX:3itrade+otc_quotes"


# ── I/O helpers(照 update_macro_history 範式)────────────────────────────
def _load_existing() -> pd.DataFrame | None:
    if not PARQUET_PATH.exists():
        return None
    try:
        return pd.read_parquet(PARQUET_PATH)
    except Exception as e:
        print(f"[sector_flow] 讀既有 parquet 失敗:{type(e).__name__}: {e}")
        return None


def _last_date(df: pd.DataFrame | None) -> _dt.date | None:
    if df is None or df.empty or "date" not in df.columns:
        return None
    try:
        return pd.to_datetime(df["date"]).max().date()
    except Exception:
        return None


def _merge_dedupe(old: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """合併 old + new,按 (date,sector) 去重保留最新,排序。"""
    if old is None or old.empty:
        out = new
    else:
        out = pd.concat([old, new], ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    out = (out.drop_duplicates(subset=_DEDUPE_KEYS, keep="last")
              .sort_values(_DEDUPE_KEYS).reset_index(drop=True))
    return out


def _candidate_trading_days(today: _dt.date, existing: pd.DataFrame | None,
                            bootstrap: bool, days: int) -> list[_dt.date]:
    """要抓的候選日曆日(已濾週末)。假日由 fetcher 回空自然排除(§4.5 自證法)。"""
    if bootstrap or existing is None or existing.empty:
        start = today - _dt.timedelta(days=max(1, days))
    else:
        last = _last_date(existing)
        start = (last + _dt.timedelta(days=1)) if last else (
            today - _dt.timedelta(days=_DEFAULT_BOOTSTRAP_DAYS))
    out: list[_dt.date] = []
    d = start
    while d <= today:
        if d.weekday() < 5:            # 只保留平日(週末 TWSE/TPEX 必無資料)
            out.append(d)
        d += _dt.timedelta(days=1)
    return out


# ── 抓取:逐交易日組 inst(張)+ price(元)長表 ────────────────────────────
def _collect_days(days: list[_dt.date]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """對每候選日抓 T86+TPEX 法人 + TWSE+TPEX 收盤 → 兩個長表 + 診斷 meta。

    批 Z39:逐日分市場判定成敗(規則見檔頭);只把**成功市場**的法人列與收盤放進長表。
    diag 追加 `per_day[ds]`(各源筆數 / TPEx 狀態 / twse_ok / tpex_ok / written)與
    `unresolved_days`(TWSE 失敗、未寫入的交易日)。回傳仍為 3-tuple。
    """
    inst_rows: list[dict] = []
    price_rows: list[dict] = []
    diag = {"days_fetched": 0, "days_holiday_or_empty": 0, "days_missing_price": 0,
            "per_day": {}, "unresolved_days": []}
    _nan = float("nan")
    for d in days:
        ds = d.strftime("%Y%m%d")
        t86 = _get_t86_day(ds) or {}
        tpex = _get_tpex_day(ds) or {}
        _day = {"twse_inst": len(t86), "twse_close": 0, "tpex_inst": len(tpex),
                "tpex_close": 0, "tpex_inst_status": get_tpex_day_status(ds),
                "tpex_close_status": None, "twse_ok": False, "tpex_ok": False,
                "holiday": False, "written": False}
        diag["per_day"][ds] = _day
        if not t86 and not tpex:
            diag["days_holiday_or_empty"] += 1
            _day["holiday"] = True
            continue   # §1/§4.6:兩邊都空 = 假日/休市 → 整日跳過,不寫假
        diag["days_fetched"] += 1
        twse_close = fetch_twse_close_day(ds) or {}
        tpex_close = fetch_tpex_close_day(ds) or {}
        _day["twse_close"] = len(twse_close)
        _day["tpex_close"] = len(tpex_close)
        _day["tpex_close_status"] = get_tpex_close_status(ds)
        if not twse_close and not tpex_close:
            # 有法人淨額但當日收盤全缺 → 該日金額無法換算(§1 不補價)
            diag["days_missing_price"] += 1
            print(f"[sector_flow] ⚠️ {ds} 有法人淨額但收盤全缺 → 該日金額不計")
        twse_ok = bool(t86) and bool(twse_close) and bool(set(t86) & set(twse_close))
        # invariant:TPEx 0 筆 / parser failure / 欄位未驗證 / 收盤空 / 交集 0 → 不得標成功
        tpex_ok = (bool(tpex) and _day["tpex_inst_status"] == TPEX_DAY_STATUS_OK
                   and bool(tpex_close) and bool(set(tpex) & set(tpex_close)))
        _day["twse_ok"], _day["tpex_ok"] = bool(twse_ok), bool(tpex_ok)
        if not twse_ok:
            # TWSE 失敗(含只有 TPEx 成功)→ 不寫入,交 metadata 列 unresolved(不寫半套日)
            diag["unresolved_days"].append(ds)
            print(f"[sector_flow] ⚠️ {ds} 上市(TWSE)未成功(法人 {len(t86)} / 收盤 "
                  f"{len(twse_close)})→ 該日不寫入,列 unresolved_days")
            continue
        if not tpex_ok:
            print(f"[sector_flow] ⚠️ {ds} 上櫃(TPEx)未成功(法人 {len(tpex)} 狀態 "
                  f"{_day['tpex_inst_status']} / 收盤 {len(tpex_close)} 狀態 "
                  f"{_day['tpex_close_status']})→ 該日只含上市")
        _day["written"] = True
        _inst = {**tpex, **t86} if tpex_ok else dict(t86)
        for code, v in _inst.items():
            v = v if isinstance(v, dict) else {}
            inst_rows.append({
                "date": d, "stock_id": str(code).strip(),
                # 批 Z39:缺鍵 = 未取得(NaN),不是 0(Q-z26=A)
                "foreign_lots": v.get("外資", _nan),
                "trust_lots": v.get("投信", _nan),
                "dealer_lots": v.get("自營商", _nan),
            })
        close_map: dict = {}
        if tpex_ok:
            close_map.update(tpex_close)
        close_map.update(twse_close)   # 上市覆蓋上櫃(代號不重疊)
        for code, close in close_map.items():
            price_rows.append({"date": d, "stock_id": str(code).strip(),
                               "close": close})
    inst_df = pd.DataFrame(inst_rows) if inst_rows else pd.DataFrame(
        columns=["date", "stock_id", "foreign_lots", "trust_lots", "dealer_lots"])
    price_df = pd.DataFrame(price_rows) if price_rows else pd.DataFrame(
        columns=["date", "stock_id", "close"])
    return inst_df, price_df, diag


def _json_safe(o):
    """批 Z39:NaN / ±inf → None(JSON null);numpy 純量 → Python 原生;遞迴 dict / list。"""
    if isinstance(o, dict):
        return {str(k): _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    if hasattr(o, "item") and not isinstance(o, (str, bytes)):
        try:
            o = o.item()
        except (ValueError, TypeError):
            pass
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


def _day_flags_frame(diag: dict) -> pd.DataFrame:
    """per_day → DataFrame[date, twse_ok, tpex_ok, source](只含已寫入日)。"""
    rows = []
    for ds, v in (diag.get("per_day") or {}).items():
        if not v.get("written"):
            continue
        rows.append({
            "date": pd.Timestamp(_dt.datetime.strptime(ds, "%Y%m%d")).normalize(),
            "twse_ok": bool(v.get("twse_ok")), "tpex_ok": bool(v.get("tpex_ok")),
            "source": _SOURCE_TWSE + (f" / {_SOURCE_TPEX}" if v.get("tpex_ok") else ""),
        })
    out = pd.DataFrame(rows, columns=["date", "twse_ok", "tpex_ok", "source"])
    out["date"] = pd.to_datetime(out["date"]).astype("datetime64[ns]")
    return out


def _norm_flag_cols(df: pd.DataFrame) -> pd.DataFrame:
    """twse_ok / tpex_ok → nullable boolean;舊列(無旗標 → NaN/None)為 <NA>(未知 ≠ True)。"""
    for c in ("twse_ok", "tpex_ok"):
        if c in df.columns:
            df[c] = pd.array([True if (v is True or v is np.True_) else
                              (False if (v is False or v is np.False_) else pd.NA)
                              for v in df[c]], dtype="boolean")
    return df


def _markets_summary(diag: dict) -> dict:
    """本次抓取的分市場成敗(假日不計)。"""
    out = {}
    for mkt, key in (("TWSE", "twse_ok"), ("TPEx", "tpex_ok")):
        ok = sorted(ds for ds, v in (diag.get("per_day") or {}).items()
                    if not v.get("holiday") and v.get(key))
        fail = sorted(ds for ds, v in (diag.get("per_day") or {}).items()
                      if not v.get("holiday") and not v.get(key))
        out[mkt] = {"ok_days": len(ok), "fail_days": len(fail),
                    "ok_dates": ok, "fail_dates": fail}
    return out


def _write_bubble_json(full: pd.DataFrame) -> dict:
    """由完整長表算最新泡泡座標,落 bubble_latest.json(Stage 2 秒讀)。

    批 Z39:NaN → `null`(`allow_nan=False` 守門,不寫非標準 NaN token);
    `tpex_complete` ＝ 窗口內每個交易日 TPEx 皆成功(舊列無旗標 → 非 True → False);
    回傳 meta 追加 `tpex_complete`。
    """
    bubble, meta = compute_bubble(full)
    _n_used = meta.get("n_trading_days_used") or 0
    _n_tp = meta.get("n_days_tpex_ok")
    meta["tpex_complete"] = bool(_n_tp is not None and _n_used > 0 and _n_tp == _n_used)
    payload = _json_safe({
        "updated_at": pd.Timestamp.now("UTC").isoformat(),
        "window_size": WINDOW_SIZE,
        "n_trading_days_used": meta.get("n_trading_days_used"),
        "n_days_tpex_ok": _n_tp,
        "tpex_complete": meta["tpex_complete"],
        "n_absent_cells": meta.get("n_absent_cells"),
        "sectors": bubble.to_dict(orient="records"),
    })
    BUBBLE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                                      allow_nan=False) + "\n",
                           encoding="utf-8")
    print(f"[sector_flow] ✅ bubble_latest.json:{len(bubble)} 板塊 "
          f"({meta.get('n_trading_days_used')} 交易日)")
    return meta


def _write_ticker_sector_json(industry_map: dict) -> None:
    """多存一份 {裸股號: 產業別} 供 Stage 2 UI 把持股對映板塊(highlight)。

    §1 Fail Loud, Never Fake:industry_map 空(FinMind + openapi 皆敗)→ **不寫**,
    不留一份空表冒充成功;既有(上次成功那份)保留不動。只清洗掉 code/sector 任一為空
    的髒列(不臆造產業別)。
    """
    if not industry_map:
        print("[sector_flow] ⚠️ industry_map 空 → 不寫 ticker_sector.json(§1 不造假,保留既有)")
        return
    clean = {str(k).strip(): str(v).strip()
             for k, v in industry_map.items()
             if str(k).strip() and str(v).strip()}
    if not clean:
        print("[sector_flow] ⚠️ industry_map 清洗後為空 → 不寫 ticker_sector.json")
        return
    TICKER_SECTOR_PATH.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[sector_flow] ✅ ticker_sector.json:{len(clean)} 檔 → {TICKER_SECTOR_PATH}")


def _write_metadata(full: pd.DataFrame, diag: dict, cov: dict,
                    last_error: str | None, bubble_meta: dict | None = None) -> None:
    """批 Z39:追加 per_day / markets_summary / unresolved_days / warnings。

    `warnings` 在「本次有 TPEx 失敗日」「窗口內有交易日未含 TPEx」「有 unresolved 日」時
    非空 —— 不得 last_error=null 又看起來全成功。
    """
    diag = diag or {}
    _summary = _markets_summary(diag)
    _warn: list[str] = []
    if _summary["TPEx"]["fail_days"]:
        _warn.append("本次抓取上櫃(TPEx)未成功日:"
                     + ",".join(_summary["TPEx"]["fail_dates"]) + "(該日只含上市)")
    if diag.get("unresolved_days"):
        _warn.append("上市(TWSE)未成功、未寫入日:" + ",".join(diag["unresolved_days"]))
    if bubble_meta:
        _n_used = bubble_meta.get("n_trading_days_used") or 0
        _n_tp = bubble_meta.get("n_days_tpex_ok")
        if _n_used and not bubble_meta.get("tpex_complete"):
            _warn.append(f"泡泡圖窗口 {_n_used} 交易日中 TPEx 成功納入 "
                         f"{_n_tp if _n_tp is not None else '未知'} 日 → 目前僅含上市資料")
    payload = {
        "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "last_updated": (_last_date(full).isoformat()
                         if _last_date(full) else None),
        "row_count": int(len(full)) if full is not None else 0,
        "n_days": int(pd.to_datetime(full["date"]).dt.normalize().nunique())
                  if full is not None and not full.empty else 0,
        "fetch_diag": {k: v for k, v in diag.items()
                       if k not in ("per_day", "unresolved_days")},
        "coverage": cov,
        "last_error": last_error,
        "warnings": _warn,
        "per_day": diag.get("per_day") or {},
        "markets_summary": _summary,
        "unresolved_days": list(diag.get("unresolved_days") or []),
        "bubble_window": ({k: bubble_meta.get(k) for k in
                           ("n_trading_days_used", "n_days_tpex_ok", "tpex_complete",
                            "n_absent_cells", "n_missing_value_cells")}
                          if bubble_meta else None),
    }
    META_PATH.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2,
                                    allow_nan=False) + "\n",
                         encoding="utf-8")
    print(f"[sector_flow] ✅ metadata.json → {META_PATH}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", action="store_true",
                    help="回抓近 --days 日曆日(初次部署 / 補洞用)")
    ap.add_argument("--days", type=int, default=_DEFAULT_BOOTSTRAP_DAYS,
                    help=f"bootstrap 回溯日曆天(預設 {_DEFAULT_BOOTSTRAP_DAYS})")
    args = ap.parse_args(argv)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    today = _dt.date.today()
    existing = None if args.bootstrap else _load_existing()

    cand = _candidate_trading_days(today, existing, args.bootstrap, args.days)
    if not cand:
        print("[sector_flow] 已是最新,無新交易日待抓")
        # 仍重算 bubble(交易日軸可能因日期前進而右移),但不改長表
        if existing is not None and not existing.empty:
            _write_bubble_json(existing)
        return 0

    print(f"[sector_flow] 抓 {cand[0]} ~ {cand[-1]}(共 {len(cand)} 候選日,"
          f"bootstrap={args.bootstrap})")

    # 產業別整表(一次抓,全日共用)
    industry_map = fetch_industry_map_bulk()
    if not industry_map:
        # §1:無產業別 → L2 會全歸「未分類」;仍可算「全市場」但失去板塊維度 → loud
        print("[sector_flow] ⚠️ 產業別整表為空,全部將歸『未分類』桶")

    # 持股→板塊對映(Stage 2 UI highlight)**只依賴 industry_map**,與「當日三大法人是否
    # 已公布」完全無關 → 抓到 map 就立刻落地。若擺在後段 happy-path,盤前手動跑(inst 未出)
    # 會走下面 `inst_df.empty` 早退 → ticker_sector.json 永遠不生成(highlight 失效)。
    # 空 map 由 `_write_ticker_sector_json` 內 §1 守衛不寫、保留既有。
    _write_ticker_sector_json(industry_map)

    inst_df, price_df, diag = _collect_days(cand)
    print(f"[sector_flow] fetch 診斷:{diag}")

    if inst_df.empty:
        msg = "所有候選交易日皆無三大法人資料(假日/來源全敗)"
        if diag.get("unresolved_days"):
            msg += f";上市(TWSE)未成功日 {','.join(diag['unresolved_days'])} 未寫入"
        print(f"[sector_flow] ❌ {msg} → 不覆寫既有 parquet")
        # 既有存在才重算 bubble;完全無資料 → 非零 exit
        if existing is not None and not existing.empty:
            _bm = _write_bubble_json(existing)
            _write_metadata(existing, diag, {}, last_error=msg, bubble_meta=_bm)
            return 0
        _write_metadata(pd.DataFrame(), diag, {}, last_error=msg)
        return 1

    sector_daily, cov = compute_sector_daily_net(inst_df, price_df, industry_map)
    print(f"[sector_flow] L2 coverage:{cov}")

    if sector_daily.empty:
        msg = ("有三大法人資料但換算後 0 板塊列"
               f"(缺價剔除 {cov.get('n_dropped_missing_price')})")
        print(f"[sector_flow] ❌ {msg} → 不覆寫既有 parquet")
        if existing is not None and not existing.empty:
            _bm = _write_bubble_json(existing)
            _write_metadata(existing, diag, cov, last_error=msg, bubble_meta=_bm)
            return 0
        _write_metadata(pd.DataFrame(), diag, cov, last_error=msg)
        return 1

    # provenance(§2.2 schema-additive)。批 Z39:source 依日只列實際成功的市場;
    # 加 twse_ok / tpex_ok(同日相同)兩欄供 bubble 算 tpex_complete(L2 7 欄不變)。
    sector_daily = sector_daily.copy()
    sector_daily["date"] = (pd.to_datetime(sector_daily["date"]).dt.normalize()
                            .astype("datetime64[ns]"))
    sector_daily = sector_daily.merge(_day_flags_frame(diag), on="date", how="left")
    sector_daily = _norm_flag_cols(sector_daily)
    sector_daily["fetched_at"] = pd.Timestamp.now("UTC").isoformat()

    full = _norm_flag_cols(_merge_dedupe(existing, sector_daily))
    full.to_parquet(PARQUET_PATH, compression="snappy", index=False)
    print(f"[sector_flow] ✅ 寫入 {len(full)} 列 → {PARQUET_PATH}")

    # ticker_sector.json 已於前段 industry_map 抓取後就落地(與 inst 資料解耦),此處不再重寫。
    _bm = _write_bubble_json(full)
    _write_metadata(full, diag, cov, last_error=None, bubble_meta=_bm)
    if diag.get("unresolved_days") or not _bm.get("tpex_complete"):
        print(f"[sector_flow] ⚠️ unresolved_days={diag.get('unresolved_days')} "
              f"tpex_complete={_bm.get('tpex_complete')}(見 metadata warnings)")

    if diag.get("days_missing_price"):
        print(f"[sector_flow] ⚠️ {diag['days_missing_price']} 個交易日收盤全缺"
              f"(該日金額未計,見 metadata)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
