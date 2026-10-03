"""src/data/stock/monthly_revenue_fetcher.py — 月營收 L1 fetcher(v18.400 U1).

從 `src/ui/tabs/monthly_revenue_screener.py` 抽出 fetch 層(原 L1 邏輯誤放 L5),
配合 U1 修反向違憲(原 `src/compute/health/fin_trend_score.py:250` 反向 import L5;
v19.174 該檔已去識別化改名,原檔名帶人名縮寫)。

§8.2 layer:L1 Data — 月營收多源:FinMind 主 → TWSE/TPEx OpenAPI keyless fallback。
§8.2.A EX-CACHE-1 letter-compliant(try/except + `_NoOpST` fallback + secrets dict)。
§2.2 / S-PROV-1 phase 19 provenance(source + fetched_at)注入 DataFrame.attrs。

致命03 去 FinMind 單點(本次):FinMind 全敗(無 token/API 錯/回空)時,改抓
TWSE `t187ap05_L`(上市)+ TPEx `mopsfin_t187ap05_O`(上櫃)免 token OpenAPI 快照。
§4.1:OpenAPI 營收單位為**千元** → ×1000 對齊 FinMind 的**元**;民國年月 → 西元。
fallback 僅「最新月快照」(每股 1 列),非歷史序列 → 降級補位,非等價替代。

對外 API:
- `fetch_monthly_revenue(stock_id, months=18) -> pd.DataFrame`:單股 N 月營收
- `fetch_batch_monthly_revenue(months=18) -> pd.DataFrame`:全市場(不帶 data_id)
  兩者皆 FinMind 主 → OpenAPI fallback;私有實作 `_single_finmind` / `_batch_finmind`。
  D2-f5(2026-09-28):全市場那支「只快取成功」—— 快取在 `_fetch_batch_monthly_revenue_cached`,
  確定抓取失敗不入快取、外層以 `shared.fail_cooldown` 退避;公開名稱、簽名、回傳與 `.clear()` 不變
  (另掛 `.with_status` 給 L3 缺貨掃描判斷「這一份是不是確定失敗」)。單股那支 D2-f5 未動。
  批 D3e(2026-09-28):單股那支比照拆層(快取在 `_fetch_monthly_revenue_cached`,D2-f22);全市場那支
  「上市／上櫃一邊確定失敗、只拿到一半」也不入快取(D2-f23)、失敗冷卻改遞增(D2-f25);`_batch_finmind`
  的 schema 樣本改為真的只取首檔(D2-f21)。兩支的公開名稱、簽名、回傳與 `.clear()` 皆不變。
"""
from __future__ import annotations

import datetime as _dt
import os
import sys

import pandas as pd

try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa

from shared.ttls import TTL_1HOUR, TTL_6HOUR
from shared.fail_cooldown import (CachedFailure as _CachedFailure,  # D2-f5 2026-09-28
                                  FailCooldown as _FailCooldown, NO_HIT as _FC_NO_HIT)
import shared.fail_cooldown as _fc_mod  # D2-f29:快照時點與冷卻用同一個時鐘
from shared.roc_calendar import roc_to_gregorian_year  # B3 SSOT-H2:民國→西元
from src.data.core.finmind_client import finmind_get  # D5 step2 v18.437 SSOT client


def _get_token() -> str:
    """讀 FinMind token:FINMIND_TOKEN > FM_TOKEN > ''。"""
    return (os.environ.get("FINMIND_TOKEN", "") or
            os.environ.get("FM_TOKEN", ""))


def _single_finmind(stock_id: str, months: int = 18, *, failed: list | None = None) -> pd.DataFrame:
    """[私有] 單股近 N 月營收 FinMind 主源實作(TaiwanStockMonthRevenue)。

    公開入口 `fetch_monthly_revenue` 於此回空時改走 TWSE/TPEx OpenAPI keyless fallback
    (致命03 去 FinMind 單點)。

    Args:
        stock_id: 純台股代碼如 '2330'
        months: 回溯月數(預設 18 = 12 YoY 基期 + 6 分析窗口緩衝)

    Returns:
        DataFrame columns: date / revenue / revenue_year / revenue_month
        失敗回空 DataFrame

    failed(D2-f22 變形,批 D2;預設 None = 既有行為不變):轉給 `finmind_get`,確定抓取失敗時寫一筆說明。
    """
    _tok = _get_token()
    if not _tok:
        # D14c v19.75(review):原靜默回空 → 補 log(§5 可觀測性,診斷可分辨「無 token」vs「API 失敗」)
        print(f"[mrev-fetcher] {stock_id} 無 FinMind token(FINMIND_TOKEN/FM_TOKEN 皆空)→ 回空")
        return pd.DataFrame()
    _end = _dt.date.today()
    _start = (_end - _dt.timedelta(days=months * 31 + 31)).strftime("%Y-%m-%d")
    try:
        _df = finmind_get(
            "TaiwanStockMonthRevenue",
            data_id=stock_id,
            start_date=_start,
            token=_tok,
            timeout=20,
            failed=failed,
        )
        if _df.empty:
            return pd.DataFrame()
        if "revenue" not in _df.columns:
            return pd.DataFrame()
        if "date" not in _df.columns and "revenue_year" in _df.columns:
            _df["date"] = (
                _df["revenue_year"].astype(str) + "-" +
                _df["revenue_month"].astype(str).str.zfill(2) + "-01"
            )
        _df["date"] = pd.to_datetime(_df["date"], errors="coerce")
        # D13 v19.75:revenue 強制 float64 — FinMind JSON 整數營收會推成 int64,
        # 違反 MonthlyRevenueSchema float 契約 → blocking 模式整檔誤殺
        # (同 Fund repo v19.172 FRED 全整數 series 教訓;非數值 coerce 成 NaN 由下行 dropna 接手)
        _df["revenue"] = pd.to_numeric(_df["revenue"], errors="coerce").astype("float64")
        _df = _df.dropna(subset=["date", "revenue"]).sort_values("date").reset_index(drop=True)
        _result = _df[["date", "revenue", "revenue_year", "revenue_month"]] if all(
            c in _df.columns for c in ["revenue_year", "revenue_month"]
        ) else _df[["date", "revenue"]]
        # v18.356 PR-Q5b S-PROV-1 phase 19
        try:
            _result.attrs.setdefault('source', 'FinMind:TaiwanStockMonthRevenue:single')
            _result.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        # D13 v19.75(review,user 核准):log-mode → blocking。schema 違反 → 整檔
        # 棄用回空(§1 錯值比缺值危險),下游走既有「無資料」路徑 + 診斷 Tab 亮紅。
        try:
            from shared.schemas import validate_or_reject, MonthlyRevenueSchema
            _result = validate_or_reject(_result, MonthlyRevenueSchema,
                                         label=f'fetch_monthly_revenue:{stock_id}')
        except ImportError as _e_sch:
            print(f'[mrev-fetcher] schema 模組不可用,跳過驗證: {_e_sch}')
        return _result
    except Exception as _e:
        print(f"[mrev-fetcher] fetch {stock_id} 失敗: {type(_e).__name__}: {_e}")
        return pd.DataFrame()


def _batch_finmind(months: int = 18) -> pd.DataFrame:
    """[私有] 全市場月營收 FinMind 主源實作(不帶 data_id,避開逐股迴圈)。

    公開入口 `fetch_batch_monthly_revenue` 於此回空時改走 TWSE/TPEx OpenAPI keyless
    fallback(致命03 去 FinMind 單點)。

    Args:
        months: 回溯月數(預設 18)

    Returns:
        DataFrame columns: stock_id / date / revenue(多股長表)
        失敗或無 token 回空 DataFrame
    """
    _tok = _get_token()
    if not _tok:
        # D14c v19.75(review):同單檔版,無 token 補 log 不再靜默
        print("[mrev-fetcher] batch 無 FinMind token(FINMIND_TOKEN/FM_TOKEN 皆空)→ 回空")
        return pd.DataFrame()
    _end = _dt.date.today()
    _start = (_end - _dt.timedelta(days=months * 31 + 31)).strftime("%Y-%m-%d")
    try:
        _df = finmind_get(
            "TaiwanStockMonthRevenue",
            start_date=_start,
            token=_tok,
            timeout=60,
        )
        if _df.empty:
            print("[mrev-fetcher] batch fetch 回空(status!=200 或無資料)")
            return pd.DataFrame()
        if "revenue" not in _df.columns or "stock_id" not in _df.columns:
            return pd.DataFrame()
        if "date" not in _df.columns and "revenue_year" in _df.columns:
            _df["date"] = (
                _df["revenue_year"].astype(str) + "-" +
                _df["revenue_month"].astype(str).str.zfill(2) + "-01"
            )
        _df["date"] = pd.to_datetime(_df["date"], errors="coerce")
        # D13 v19.75:同單檔版,revenue 強制 float64(schema float 契約;int64 會誤殺)
        _df["revenue"] = pd.to_numeric(_df["revenue"], errors="coerce").astype("float64")
        _df = _df.dropna(subset=["date", "revenue", "stock_id"])
        _result_b = _df[["stock_id", "date", "revenue"]].sort_values(
            ["stock_id", "date"]
        ).reset_index(drop=True)
        # v18.356 PR-Q5b S-PROV-1 phase 19
        try:
            _result_b.attrs.setdefault('source', 'FinMind:TaiwanStockMonthRevenue:batch(all-market)')
            _result_b.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        # D13 v19.75(review,user 核准):log-mode → blocking(batch 含 stock_id 多檔)。
        # 取首檔 36 列當代表驗(完整驗會誤判 date dup 跨股);樣本違反 = 系統性 shape
        # 問題 → 整批棄用回空(§1),下游走既有「無資料」路徑。
        # D2-f21(2026-09-28 批 D3e):修前實際取的是「排序後前 36 列」—— 每檔約 months+1 列,兩檔
        # 以上時樣本必然跨檔、date 不單調 → 樣本恆判違反 → 整批恆被丟棄(恆落到 OpenAPI 單月快照)。
        # 改為真的只取首檔(排序後第一個 stock_id)的前 36 列;schema 本身與「樣本違反 → 整批棄用」皆不變。
        try:
            from shared.schemas import validate_or_reject, MonthlyRevenueSchema
            _sample = _result_b.head(36)
            if not _sample.empty:   # D2-f21:只留首檔的列(已依 stock_id、date 排序 → 首檔在最前面)
                _sample = _sample[_sample["stock_id"] == _sample["stock_id"].iloc[0]]
            _sample_v = validate_or_reject(_sample, MonthlyRevenueSchema,
                                           label='fetch_batch_monthly_revenue:sample')
            if _sample_v.empty and not _result_b.empty:
                print('[mrev-fetcher] batch 樣本 schema 違反 → 整批棄用(§1 錯值比缺值危險)')
                return _result_b.iloc[0:0]
        except ImportError as _e_sch:
            print(f'[mrev-fetcher] schema 模組不可用,跳過驗證: {_e_sch}')
        return _result_b
    except Exception as _e:
        print(f"[mrev-fetcher] batch fetch 失敗: {type(_e).__name__}: {_e}")
        return pd.DataFrame()


# ── 致命03 去 FinMind 單點:TWSE(上市)+ TPEx(上櫃)OpenAPI keyless fallback ─────
# OpenAPI 免 token、走 NAS proxy(TW IP);t187ap05_L / mopsfin_t187ap05_O 僅回「最新
# 一個月」快照(每股 1 列)非歷史序列,故為 FinMind(帶 18 月歷史)全敗時的降級補位。
# §4.1 單位陷阱:「營業收入-當月營收」單位為 **千元** → ×1000 轉「元」對齊 FinMind。
# §2.1 來源:上市 TWSE OpenAPI / 上櫃 TPEx OpenAPI(同 MOPS 欄名);已於本 repo
# stock_names_fetcher.py 消費同族 t187ap03_L,沿用 fetch_url + 容錯欄名 pattern。
_TWSE_REVENUE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"       # 上市
_TPEX_REVENUE_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"    # 上櫃
_REV_CODE_KEYS = ("公司代號", "Code")       # 個股代號
_REV_YM_KEYS = ("資料年月",)                # 民國年月 e.g. '11505' = 民國115年05月
_REV_AMT_KEYS = ("營業收入-當月營收",)       # 當月營收(單位:千元,§4.1)


def _roc_ym_to_date(ym: str) -> str | None:
    """民國年月字串 → '西元-MM-01'(西元 = 民國 + 1911)。壞值回 None(§1 不臆造)。

    例:'11505' → '2026-05-01'(民國115年5月);'10001' → '2011-01-01'。
    """
    s = str(ym).strip()
    if len(s) < 4 or not s.isdigit():
        return None
    roc_year, month = int(s[:-2]), int(s[-2:])
    if roc_year < 1 or not (1 <= month <= 12):
        return None
    return f"{roc_to_gregorian_year(roc_year):04d}-{month:02d}-01"


def _clean_revenue_amount(raw) -> float | None:
    """月營收字串(可能帶千分位逗號)→ float 千元值。空/'-'/非數 → None(§1 顯式剔除)。"""
    if raw is None:
        return None
    s = str(raw).replace(",", "").strip()
    if s in ("", "-", "N/A", "None", "nan"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _first_field(rec: dict, keys: tuple) -> str | None:
    """取 rec 中第一個非空欄位(容錯中英欄名,同 stock_names_fetcher pattern)。"""
    for k in keys:
        if k in rec:
            v = str(rec[k]).strip()
            if v:
                return v
    return None


def _parse_twse_revenue_records(records, *, market: str = "") -> list[dict]:
    """TWSE/TPEx OpenAPI 月營收 raw JSON list → [{stock_id, date, revenue(元)}]。

    純轉換(無 I/O,offline 可單測)。§4.1 千元 → 元(×1000);民國年月 → 西元。
    §1 Fail-Loud:代號非數字 / 年月壞 / 營收缺或 ≤0 → 略過該筆(不造假、不填 0)。
    """
    out: list[dict] = []
    if not isinstance(records, list):
        return out
    for rec in records:
        if not isinstance(rec, dict):
            continue
        code = _first_field(rec, _REV_CODE_KEYS)
        if not code or not code.isdigit():          # 僅收個股數字代號(排除權證/債等)
            continue
        d = _roc_ym_to_date(_first_field(rec, _REV_YM_KEYS) or "")
        amt_k = _clean_revenue_amount(_first_field(rec, _REV_AMT_KEYS))
        if d is None or amt_k is None or amt_k <= 0:  # 缺/壞/非正 → 略過(§1)
            continue
        out.append({"stock_id": code, "date": d, "revenue": amt_k * 1000.0})  # 千元→元
    return out


def _batch_twse_openapi(*, failed: list | None = None) -> pd.DataFrame:
    """keyless TWSE(上市)+ TPEx(上櫃)月營收快照 → 全市場 df(stock_id/date/revenue 元)。

    致命03 去 FinMind 單點:無 token,走 NAS proxy。單股/全市場 fallback 共用此入口。
    失敗回空 df(§1,上游 source_health 顯示 absent,不造假)。

    failed(D2-f5 2026-09-28;預設 None = 既有行為一字不變;單股 fallback 自 D2-f22〔批 D3e〕起也傳):傳一個 list
    進來 → **確定是抓取失敗**的市場各寫一筆說明(「上市: …」/「上櫃: …」)。「確定」的定義
    (拿不準的一律不寫,不猜 §1):
      · `fetch_url` 回 None(代理/直連/NAS 中繼全敗;它對非 200 也回 None)或回非 200 ⇒ 寫;
      · 抓取或解 JSON **拋例外**(回應不是 JSON:維護頁、被截斷…)⇒ 寫;
      · 有回 200、JSON 也解得出來,只是解析後 0 筆 ⇒ **不寫** —— 那與「這一期真的沒有」
        在這一層分不出來;
      · `fetch_url` import 不到 ⇒ 不寫(環境問題,不是上游失敗;重打也不會變)。
    """
    try:
        from src.data.proxy import fetch_url as _furl
    except ImportError:
        print("[mrev-fetcher] proxy fetch_url 不可用 → TWSE fallback 略過")
        return pd.DataFrame()
    _rows: list[dict] = []
    for _url, _mkt in ((_TWSE_REVENUE_URL, "上市"), (_TPEX_REVENUE_URL, "上櫃")):
        try:
            _r = _furl(_url, headers={"Accept": "application/json"}, timeout=25, attempts=2)
            if _r is None or _r.status_code != 200:
                print(f"[mrev-fetcher] TWSE fallback {_mkt} 非200: "
                      f"status={getattr(_r, 'status_code', None)}")
                if failed is not None:   # D2-f5:確定抓取失敗
                    failed.append(f"{_mkt}: status={getattr(_r, 'status_code', None)}")
                continue
            _parsed = _parse_twse_revenue_records(_r.json(), market=_mkt)
            print(f"[mrev-fetcher] TWSE fallback {_mkt}: {len(_parsed)} 檔月營收")
            _rows.extend(_parsed)
        except Exception as _e:
            print(f"[mrev-fetcher] TWSE fallback {_mkt} 失敗: {type(_e).__name__}: {_e}")
            if failed is not None:       # D2-f5:確定抓取失敗(抓取/解碼拋例外)
                failed.append(f"{_mkt}: {type(_e).__name__}: {_e}")
    if not _rows:
        print("[mrev-fetcher] TWSE/TPEx OpenAPI fallback 全空 → 回空(§1 不造假)")
        return pd.DataFrame()
    _df = pd.DataFrame(_rows)
    _df["date"] = pd.to_datetime(_df["date"], errors="coerce")
    _df["revenue"] = pd.to_numeric(_df["revenue"], errors="coerce").astype("float64")
    _df = _df.dropna(subset=["stock_id", "date", "revenue"])
    _df = _df.sort_values(["stock_id", "date"]).reset_index(drop=True)
    try:
        _df.attrs["source"] = ("TWSE-OpenAPI:t187ap05_L+TPEx:mopsfin_t187ap05_O"
                               "(keyless fallback,單月快照)")
        _df.attrs["fetched_at"] = pd.Timestamp.now("UTC").isoformat()
    except Exception:
        pass
    return _df


def _cooldown_note(cd: _FailCooldown) -> str:
    """log 用(批 D3e):一個 `FailCooldown` 的冷卻設定白話(固定 or 遞增),不會因設定不同而拋錯。"""
    if cd.max_seconds is None:
        return f"{cd.seconds:.0f}s 內不重打上游"
    return (f"冷卻期內不重打上游(冷卻由 {cd.seconds:.0f}s 起、連續失敗加倍、"
            f"上限 {cd.max_seconds:.0f}s)")


class _SingleRevenueFetchFailed(_CachedFailure):
    """`_fetch_monthly_revenue_cached` 的「確定抓取失敗」出口專用(D2-f22 2026-09-28 批 D3e,§1.A-3(a))。

    同下方 `_BatchRevenueFetchFailed`:`st.cache_data` 不快取例外 → 失敗的空表不會被凍成 6 小時;
    外層 `fetch_monthly_revenue` 只接住本類別,取 `.payload`(＝修前會回傳的同一份空表)。刻意用私有
    子類別、不直接接 `CachedFailure`:別處的 `CachedFailure` 若從下層漏出來,不會在這裡被誤當成
    DataFrame 回傳。
    """


@st.cache_data(ttl=TTL_6HOUR, show_spinner=False)
def _fetch_monthly_revenue_cached(stock_id: str, months: int = 18) -> pd.DataFrame:
    """`fetch_monthly_revenue()` 的快取層(原函式本體;TTL、參數、回傳同修前)。

    D2-f22(2026-09-28 批 D3e,§1.A-3(a)「只快取成功結果」):FinMind 無資料後改走 OpenAPI 時傳
    `failed`;**這一檔沒拿到資料**且 OpenAPI 有市場**確定抓取失敗**(判準見 `_batch_twse_openapi`)
    → **拋** `_SingleRevenueFetchFailed`(不入快取),`.payload` 即修前會回傳的那一份空表。
    這一層不知道該股在上市還是上櫃 —— 有一邊確定失敗、這檔又沒拿到,它就可能正在失敗的那一邊,
    不猜(§1),一律不入快取。其餘結果照舊回傳、照舊快取:FinMind 有資料;OpenAPI 拿到這一檔(即使
    另一邊失敗 —— 一檔只在其中一個市場);沒有確定失敗的空表(與真的沒資料分不出來)。
    D2-f22 變形(批 D2,經 D2-f24 的 `finmind_get(failed=…)`):FinMind **確定抓取失敗**、改走 OpenAPI
    拿到的降級 1 列 → 同樣拋 `_SingleRevenueFetchFailed`(不入快取),`.payload` 即那一份降級結果
    (回傳不變);FinMind 恢復後冷卻期滿即重抓。FinMind 只是回空(非確定失敗)→ 照舊快取。
    """
    _fm_failed: list[str] = []
    _df = _single_finmind(stock_id, months, failed=_fm_failed)
    if _df is not None and not _df.empty:
        return _df
    print(f"[mrev-fetcher] {stock_id} FinMind 無資料 → TWSE/TPEx OpenAPI fallback(單股篩)")
    _failed: list[str] = []                           # D2-f22:確定抓取失敗的市場(判準同全市場那支)
    _batch = _single_openapi_snapshot(_failed)        # D2-f29:檔與檔共用失敗冷卻
    _one = (_batch[_batch["stock_id"] == str(stock_id)].copy() if not _batch.empty
            else pd.DataFrame())
    if _one.empty:
        if _failed:   # D2-f22:這一檔沒拿到,且有市場確定抓取失敗 → 不入快取
            raise _SingleRevenueFetchFailed(pd.DataFrame(), "；".join(_failed))
        if _fm_failed:   # D2-f22 變形:主源確定失敗、備援也沒有這一檔 → 不入快取
            raise _SingleRevenueFetchFailed(pd.DataFrame(), "FinMind " + "；".join(_fm_failed))
        return pd.DataFrame()
    _one["revenue_year"] = _one["date"].dt.year
    _one["revenue_month"] = _one["date"].dt.month
    _one = _one[["date", "revenue", "revenue_year", "revenue_month"]].reset_index(drop=True)
    try:
        _one.attrs["source"] = "TWSE-OpenAPI:t187ap05_L(keyless fallback,單股)"
        _one.attrs["fetched_at"] = pd.Timestamp.now("UTC").isoformat()
    except Exception:
        pass
    if _fm_failed:   # D2-f22 變形:FinMind 確定抓取失敗 → 降級結果不入快取
        raise _SingleRevenueFetchFailed(_one, "FinMind " + "；".join(_fm_failed))
    return _one


#: D2-f22(2026-09-28 批 D3e,§1.A-3(b)):單股月營收的失敗退避。鍵 ＝ (stock_id, months)(與快取層的
#: 快取鍵同義)。冷卻設定同全市場那支(`_batch_fail_cooldown`,見其註解):起點 `FAIL_COOLDOWN_SEC`、
#: 連續失敗加倍、上限 `TTL_1HOUR` —— 這裡重打一次 ＝ FinMind 1 次 ＋ OpenAPI 上市／上櫃各 1 次全市場快照,
#: 與全市場那支是同一組上游、同一組逾時(上游只收連線、不回應時一輪可卡數分鐘,D2-f25)。
#: ⚠️ 本表只擋「同一檔」重打;檔與檔之間的 OpenAPI 失敗冷卻見 `_openapi_snapshot_fail_cooldown`(D2-f29)。
#:
#: 筆數上限(批 D3e QA 必修,2026-09-29):**對齊成功快取 `_fetch_monthly_revenue_cached` 的容量** —— 那一層的
#: `st.cache_data` 沒設 `max_entries`(不限筆數、只靠 TTL 過期),修前失敗的空表也存在那裡 6 小時、不限筆數。
#: 所以本表同樣不限筆數,只靠冷卻期滿清掉(`FailCooldown` 每次存取都先清過期紀錄)⇒ 冷卻期內的失敗紀錄不會被
#: 逐出、不會因為「同時失敗的鍵太多」而每輪重打(§1.A-3(b))。若沿用預設 `FAIL_COOLDOWN_MAX_ENTRIES`(64):
#: 冷卻期內失敗的不同鍵超過 64 時會逐出最舊紀錄,被逐出的鍵下一次呼叫就重打上游。
#: 為何不取「單一使用者動作最多會產生的鍵數」(本組 grep 所見,⚠️ 未經第二組驗證):缺貨掃描 ① 存活池一次最多
#: `SHORTAGE_DEEP_SCAN_MAX`(50)鍵、v1 組合頁最多 10 鍵(`parse_stocks(...)[:10]`)、個股頁 1 鍵,同一次 rerun
#: 合計也不到 64 —— 會超過的是**跨 session 的累積**:本表整個行程共用、紀錄最長留 `TTL_1HOUR`,冷卻期內不同
#: 使用者查的不同股票一路累積,沒有哪個單一動作的數字框得住。記憶體:本表每筆 payload 恆為空表(實測約 1 KB/筆),
#: 只留到冷卻期滿(最長 `TTL_1HOUR`);修前同一批失敗則是存在不限筆數的 `st.cache_data` 裡留 6 小時。
#: `sys.maxsize` 在這裡的意思就是「不設筆數上限」(`FailCooldown` 的 `max_entries` 只收整數)。
_SINGLE_FAIL_COOLDOWN_MAX_ENTRIES: int = sys.maxsize
_single_fail_cooldown = _FailCooldown(max_seconds=TTL_1HOUR, max_entries=_SINGLE_FAIL_COOLDOWN_MAX_ENTRIES)

#: D2-f29(2026-10-03,§1.A-3(b)「失敗要退避、不轟炸來源」):單股 fallback 的 OpenAPI 全市場快照**檔與檔共用**
#: 的失敗冷卻。修前只有「同一檔」的 `_single_fail_cooldown`(D2-f22):FinMind 掛掉、OpenAPI 又確定抓取失敗時,
#: 缺貨掃描 ① 一輪最多 `SHORTAGE_DEEP_SCAN_MAX`(50)檔、每一檔各打一次上市＋上櫃全市場快照(每次
#: `timeout=25, attempts=2`)。現在單一鍵 `_OPENAPI_SNAPSHOT_KEY`:有市場確定抓取失敗(判準同 `_batch_twse_openapi`
#: 的 `failed`)→ 記下那一份 (快照, 失敗說明);冷卻期內其他檔直接沿用,不重打上游 —— 回的就是那次抓到的同一份
#: 快照(另一邊有資料的照樣篩得到)與同一組失敗說明,所以每一檔的結果、要不要入快取,都與「冷卻期內重打、
#: 上游仍同樣失敗」時相同。兩邊都沒有確定失敗 → 解除冷卻(成功的快照由 `fetch_url` 的 URL 快取在檔與檔之間共用,
#: 同修前)。冷卻設定同 `_single_fail_cooldown`(起點 `FAIL_COOLDOWN_SEC`、連續失敗加倍、上限 `TTL_1HOUR`)。
#: 只用在單股 fallback;全市場那支(`fetch_batch_monthly_revenue`)有自己的冷卻,未改。
_OPENAPI_SNAPSHOT_KEY = "openapi_snapshot"
_openapi_snapshot_fail_cooldown = _FailCooldown(max_seconds=TTL_1HOUR)


def _single_openapi_snapshot(failed: list) -> pd.DataFrame:
    """單股 fallback 用的 OpenAPI 全市場快照(D2-f29):`_batch_twse_openapi(failed=…)`,外加檔與檔共用的失敗冷卻。

    回傳與 `failed` 的寫入同 `_batch_twse_openapi(failed=failed)`;冷卻期內回上次確定失敗那一份的複本、
    `failed` 寫入同一組說明,不打上游。

    沿用的快照若含另一邊(正常市場)的資料,最多只沿用 `proxy_helper._URL_CACHE_TTL` 秒(＝修前重打時
    `fetch_url` 的 URL 快取能給的最舊資料);超過就照常重抓一次(並以新快照重記冷卻)—— 不會把比修前更舊的
    資料當成新抓的(單股結果會以抓取當下的 `fetched_at` 入 6 小時快取)。兩邊都失敗(快照為空)時沒有舊資料
    可言,整段冷卻期都沿用。"""
    from src.data.proxy import proxy_helper as _ph   # late import:同 `_batch_twse_openapi`
    _hit, _gen = _openapi_snapshot_fail_cooldown.begin(_OPENAPI_SNAPSHOT_KEY)
    if _hit is not _FC_NO_HIT:
        _snap, _notes, _at = _hit
        if _snap.empty or _fc_mod.time.monotonic() - _at <= _ph._URL_CACHE_TTL:
            failed.extend(_notes)
            print(f"[mrev-fetcher] TWSE/TPEx OpenAPI fallback 退避中(他檔剛確定抓取失敗:{'；'.join(_notes)})"
                  f"→ 不重打上游,{_cooldown_note(_openapi_snapshot_fail_cooldown)}")
            return _snap
        print("[mrev-fetcher] TWSE/TPEx OpenAPI fallback 退避中,但沿用的快照已超過 URL 快取期限 → 重抓一次")
    _failed: list[str] = []
    _at = _fc_mod.time.monotonic()
    _batch = _batch_twse_openapi(failed=_failed)
    failed.extend(_failed)
    if _failed:
        _openapi_snapshot_fail_cooldown.fail(_OPENAPI_SNAPSHOT_KEY, _gen, (_batch, list(_failed), _at))
    else:
        _openapi_snapshot_fail_cooldown.success(_OPENAPI_SNAPSHOT_KEY)
    return _batch


def fetch_monthly_revenue(stock_id: str, months: int = 18) -> pd.DataFrame:
    """單股近 N 月營收。FinMind 主 → TWSE/TPEx OpenAPI keyless fallback(致命03 去單點)。

    Returns:
        DataFrame columns: date / revenue / revenue_year / revenue_month;失敗回空。
        fallback 僅提供最新月(OpenAPI 快照特性),歷史序列仍以 FinMind 為主。
        回傳內容同修前(失敗也是無旗標的空表)。

    D2-f22(2026-09-28 批 D3e,§1.A-3「只快取成功結果;失敗時退避」):修前 FinMind 無資料、OpenAPI
    備援又**確定抓取失敗**(或該股所在的那一邊失敗)時回的空表被快取 6 小時 —— 來源恢復後同參數仍回
    空表。現在那一種**不入快取**(判準見 `_fetch_monthly_revenue_cached`);失敗後同一個
    (stock_id, months) 在冷卻期內不重打上游、回同一份空表 —— 冷卻由 `FAIL_COOLDOWN_SEC` 起、連續
    失敗加倍、上限 `TTL_1HOUR`;成功一次即歸零;連續失敗次數另隨時間衰減(D2-f38,#768):距上一次失敗已達「上一次的冷卻秒數 ＋ `TTL_1HOUR`」才又失敗 → 視為新的一串,冷卻回到 `FAIL_COOLDOWN_SEC`(見 `shared.fail_cooldown.FailCooldown`)。**本函式不快取**;`.clear()` 同清快取層與退避紀錄。
    已知代價(與 D2-f5／#741 的 D2-f8、D2-f11 同型):全站 `st.cache_data.clear()`(例:v1 側欄「強制刷新
    數據」、個股頁「強制重抓」)清不掉這張退避表 —— 失敗後的冷卻期內按它不會重抓這一檔(修前按它會);
    `fetch_monthly_revenue.clear()` 則會。
    """
    return _fetch_monthly_revenue_with_status(stock_id, months)[0]


def _fetch_monthly_revenue_with_status(stock_id: str, months: int = 18) -> tuple[pd.DataFrame, bool]:
    """(單股月營收, 這一份是不是確定抓取失敗)。**本函式不快取**(D2-f30,批 D2:給 L3 缺貨掃描判斷
    自己的結果能不能入快取)。第 1 項與 `fetch_monthly_revenue` 回的相同;冷卻期內回 (同一份, True)。"""
    _key = (stock_id, months)
    _hit, _gen = _single_fail_cooldown.begin(_key)
    if _hit is not _FC_NO_HIT:
        return _hit, True
    try:
        _df = _fetch_monthly_revenue_cached(stock_id, months)
    except _SingleRevenueFetchFailed as _sf:
        print(f"[mrev-fetcher] {stock_id} "
              f"{'無資料且 OpenAPI' if _sf.payload.empty else '降級結果、FinMind'} 確定抓取失敗({_sf})→ 不入快取,"
              f"{_cooldown_note(_single_fail_cooldown)}")
        return _single_fail_cooldown.fail(_key, _gen, _sf.payload), True
    _single_fail_cooldown.success(_key)
    return _df, False


fetch_monthly_revenue.with_status = _fetch_monthly_revenue_with_status


def _clear_fetch_monthly_revenue() -> None:
    """`fetch_monthly_revenue.clear()`:同清快取層與退避紀錄(D2-f22)。"""
    getattr(_fetch_monthly_revenue_cached, "clear", lambda: None)()
    _single_fail_cooldown.clear()
    _openapi_snapshot_fail_cooldown.clear()   # D2-f29


fetch_monthly_revenue.clear = _clear_fetch_monthly_revenue


class _BatchRevenueFetchFailed(_CachedFailure):
    """`_fetch_batch_monthly_revenue_cached` 的「確定抓取失敗」出口專用(D2-f5 2026-09-28,§1.A-3(a))。

    `st.cache_data` 不快取例外 → 失敗的結果不會被凍成 6 小時;外層
    `_fetch_batch_monthly_revenue_with_status` 只接住本類別,取 `.payload`(＝修前會回傳的
    同一份表:全空,或 D2-f23 起的半邊表)。刻意用私有子類別、不直接接 `CachedFailure`(同 rs_leader_service D2-f1 的
    理由):別處的 `CachedFailure` 若從下層漏出來,不會在這裡被誤當成 DataFrame 回傳。
    """


@st.cache_data(ttl=TTL_6HOUR, show_spinner=False)
def _fetch_batch_monthly_revenue_cached(months: int = 18) -> pd.DataFrame:
    """`fetch_batch_monthly_revenue()` 的快取層(原函式本體;TTL、參數、回傳同修前)。

    §1.A-3(a)「只快取成功結果」:OpenAPI 備援有市場**確定抓取失敗**(判準見 `_batch_twse_openapi`
    的 `failed`)→ **拋** `_BatchRevenueFetchFailed`(不入快取),`.payload` 即修前會回傳的那一份表
    (全空,或只拿到另一邊的半邊表)。其餘結果(成功;沒有確定失敗的空表)照舊回傳、照舊快取。
    沿革:D2-f5(2026-09-28)只處理「結果為空**且**有市場確定失敗」;D2-f23(2026-09-28 批 D3e)拿掉
    「結果為空」這個前提 —— 一邊確定失敗、另一邊有資料(修前照舊快取 6 小時)也不入快取。
    """
    _df = _batch_finmind(months)
    if _df is not None and not _df.empty:
        return _df
    print("[mrev-fetcher] batch FinMind 無資料/失敗 → TWSE+TPEx OpenAPI keyless fallback")
    _failed: list[str] = []
    _out = _batch_twse_openapi(failed=_failed)
    if _failed:   # D2-f23:有市場確定抓取失敗就不入快取,不論空不空(修前 D2-f5:只有「空＋失敗」)
        raise _BatchRevenueFetchFailed(_out, "；".join(_failed))
    return _out


#: D2-f5(2026-09-28,§1.A-3(b)):全市場月營收的失敗退避。鍵 ＝ `months`(與快取層的快取鍵同義)。
#: D2-f25(2026-09-28 批 D3e):冷卻由固定 `FAIL_COOLDOWN_SEC` 改**遞增** —— 同一個 `months` 連續失敗時
#: 由 `FAIL_COOLDOWN_SEC` 起、每次加倍,上限 `TTL_1HOUR`(比照 RS 掃描層 `_scan_fail_cooldown`;刻意短於
#: 本函式成功快取的 `TTL_6HOUR`:長時間中斷恢復後最慢 1 小時就重抓 —— D2-f5 以前失敗是凍 6 小時);
#: 一次成功即歸零;連續失敗次數另隨時間衰減(D2-f38,#768):距上一次失敗已達「上一次的冷卻秒數 ＋ `TTL_1HOUR`」才又失敗 → 視為新的一串,冷卻回到 `FAIL_COOLDOWN_SEC`(見 `shared.fail_cooldown.FailCooldown`)。原因(D2-f25 登記):上游只收連線、不回應時一輪重抓可卡數分鐘(批 D3c QA 在無代理
#: 環境量到約 264 秒),冷卻又從該輪結束才起算 → 固定 180 秒時,走缺貨掃描後備 ② 的頁面約每 7.4 分鐘
#: (264 ＋ 180 秒)再被卡一次。
_batch_fail_cooldown = _FailCooldown(max_seconds=TTL_1HOUR)


def _fetch_batch_monthly_revenue_with_status(months: int = 18) -> tuple[pd.DataFrame, bool]:
    """(全市場月營收, 這一份是不是**確定抓取失敗**)。**本函式不快取**;快取在 `_fetch_batch_monthly_revenue_cached`。

    第 1 項與 `fetch_batch_monthly_revenue(months)` 回的逐字相同。第 2 項為 True ＝ 本次(或冷卻期內
    記下的那次)是快取層判定的確定失敗 —— 給 L3 `shortage_screener_service` 判斷它自己的結果(「兩個
    候選池來源都取不到」,或 D2-f23 起的半邊表候選池)能不能入它自己的快取(同一次呼叫取得,不必事後查
    退避表,沒有競態)。失敗後冷卻期內同一個 `months` 不重打上游,回同一份表(冷卻由 `FAIL_COOLDOWN_SEC`
    起、連續失敗加倍、上限 `TTL_1HOUR`,D2-f25);成功(含沒有確定失敗的空表)一次即解除並歸零;
    連續失敗次數另隨時間衰減(D2-f38,#768):距上一次失敗已達「上一次的冷卻秒數 ＋ `TTL_1HOUR`」才又失敗 → 視為新的一串,冷卻回到 `FAIL_COOLDOWN_SEC`(見 `shared.fail_cooldown.FailCooldown`);
    並行時期間有人成功過,較晚到的失敗不記(`FailCooldown` 世代)。
    """
    _hit, _gen = _batch_fail_cooldown.begin(months)
    if _hit is not _FC_NO_HIT:
        return _hit, True
    try:
        _df = _fetch_batch_monthly_revenue_cached(months)
    except _BatchRevenueFetchFailed as _bf:
        print(f"[mrev-fetcher] batch {'全源無資料且 ' if _bf.payload.empty else '只拿到一半、'}"
              f"OpenAPI 確定抓取失敗({_bf})→ 不入快取,{_cooldown_note(_batch_fail_cooldown)}")
        return _batch_fail_cooldown.fail(months, _gen, _bf.payload), True
    _batch_fail_cooldown.success(months)
    return _df, False


def fetch_batch_monthly_revenue(months: int = 18) -> pd.DataFrame:
    """全市場月營收。FinMind 主 → TWSE/TPEx OpenAPI keyless fallback(致命03 去單點)。

    Returns:
        DataFrame columns: stock_id / date / revenue(多股長表);全源無資料回空。
        fallback 僅提供最新月快照(每股 1 列),為 FinMind(帶 18 月歷史)全敗時降級補位。
        回傳內容同修前(失敗也是無旗標的空表)。

    D2-f5(2026-09-28,§1.A-3「只快取成功結果;失敗時退避」):修前 OpenAPI 備援**確定抓取失敗**
    時回的空表被快取 6 小時 —— 來源恢復後同參數仍回空表、上游 0 次呼叫(L3 缺貨掃描的
    「全市場月營收動能候選池」吃這一支)。現在那一種**不入快取**;失敗後冷卻期內同一個 `months`
    不重打上游,回同一份表;成功一次即解除。冷卻由 `shared.fail_cooldown.FAIL_COOLDOWN_SEC` 起、
    連續失敗加倍、上限 `TTL_1HOUR`(D2-f25,2026-09-28 批 D3e;修前固定 `FAIL_COOLDOWN_SEC`)。
    **失敗 vs 真的沒資料的判準**(只認這一層看得到的訊號,拿不準一律照舊快取):
      · **確定失敗** ＝ OpenAPI 上市／上櫃至少一邊「`fetch_url` 回 None／非 200、或抓取／解 JSON
        拋例外」(`_batch_twse_openapi` 的 `failed`),**不論結果空不空**:
        - 結果為空(D2-f5):TWSE/TPEx keyless 快照是整個上市／上櫃市場的最新月營收,打得到就不會
          是空的,所以「空＋有一邊確定打不到」歸因在抓取失敗;
        - 結果不空、只拿到另一邊(D2-f23,批 D3e):確定少了一整個市場 —— 修前這種半邊表照舊快取
          6 小時,現在同樣不入快取;回傳的仍是那一份半邊表(對呼叫端的回傳不變)。
      · FinMind 那一段**不計**:`finmind_client.finmind_get` 對非 200(含額度用罄／方案不支援)、
        逾時、連線錯誤一律回空表、**不拋例外** —— 這一層看到的只有「空」,與真的沒資料分不出來,
        不猜(§1);`_batch_finmind` 自己的 `except` 只接得到「已收到並解開的 JSON 在整理時出錯」
        這種確定性錯誤(同一份回應重抓也一樣),不是暫時性抓取失敗。無 token 也不計(設定,不是上游)。
      · 兩邊都有回 200、只是其中一邊(或兩邊)解析後 0 筆 ⇒ 不是確定失敗,照舊快取。
    `.clear()` 同清快取層與退避紀錄。`.with_status(months)` 給 L3 用(見
    `_fetch_batch_monthly_revenue_with_status`)。
    """
    return _fetch_batch_monthly_revenue_with_status(months)[0]


def _clear_fetch_batch_monthly_revenue() -> None:
    """`fetch_batch_monthly_revenue.clear()`:同清快取層與退避紀錄(D2-f5)。"""
    getattr(_fetch_batch_monthly_revenue_cached, "clear", lambda: None)()
    _batch_fail_cooldown.clear()


fetch_batch_monthly_revenue.clear = _clear_fetch_batch_monthly_revenue
fetch_batch_monthly_revenue.with_status = _fetch_batch_monthly_revenue_with_status
