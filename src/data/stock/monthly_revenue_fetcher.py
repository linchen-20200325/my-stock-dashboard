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
  (另掛 `.with_status` 給 L3 缺貨掃描判斷「這一份是不是確定失敗」)。單股那支本次未動。
"""
from __future__ import annotations

import datetime as _dt
import os

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

from shared.ttls import TTL_6HOUR
from shared.fail_cooldown import (CachedFailure as _CachedFailure,  # D2-f5 2026-09-28
                                  FailCooldown as _FailCooldown, NO_HIT as _FC_NO_HIT)
from shared.roc_calendar import roc_to_gregorian_year  # B3 SSOT-H2:民國→西元
from src.data.core.finmind_client import finmind_get  # D5 step2 v18.437 SSOT client


def _get_token() -> str:
    """讀 FinMind token:FINMIND_TOKEN > FM_TOKEN > ''。"""
    return (os.environ.get("FINMIND_TOKEN", "") or
            os.environ.get("FM_TOKEN", ""))


def _single_finmind(stock_id: str, months: int = 18) -> pd.DataFrame:
    """[私有] 單股近 N 月營收 FinMind 主源實作(TaiwanStockMonthRevenue)。

    公開入口 `fetch_monthly_revenue` 於此回空時改走 TWSE/TPEx OpenAPI keyless fallback
    (致命03 去 FinMind 單點)。

    Args:
        stock_id: 純台股代碼如 '2330'
        months: 回溯月數(預設 18 = 12 YoY 基期 + 6 分析窗口緩衝)

    Returns:
        DataFrame columns: date / revenue / revenue_year / revenue_month
        失敗回空 DataFrame
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
        try:
            from shared.schemas import validate_or_reject, MonthlyRevenueSchema
            _sample_v = validate_or_reject(_result_b.head(36), MonthlyRevenueSchema,
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

    failed(D2-f5 2026-09-28;預設 None = 既有行為一字不變,單股 fallback 不傳):傳一個 list
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


@st.cache_data(ttl=TTL_6HOUR, show_spinner=False)
def fetch_monthly_revenue(stock_id: str, months: int = 18) -> pd.DataFrame:
    """單股近 N 月營收。FinMind 主 → TWSE/TPEx OpenAPI keyless fallback(致命03 去單點)。

    Returns:
        DataFrame columns: date / revenue / revenue_year / revenue_month;失敗回空。
        fallback 僅提供最新月(OpenAPI 快照特性),歷史序列仍以 FinMind 為主。
    """
    _df = _single_finmind(stock_id, months)
    if _df is not None and not _df.empty:
        return _df
    print(f"[mrev-fetcher] {stock_id} FinMind 無資料 → TWSE/TPEx OpenAPI fallback(單股篩)")
    _batch = _batch_twse_openapi()
    if _batch.empty:
        return pd.DataFrame()
    _one = _batch[_batch["stock_id"] == str(stock_id)].copy()
    if _one.empty:
        return pd.DataFrame()
    _one["revenue_year"] = _one["date"].dt.year
    _one["revenue_month"] = _one["date"].dt.month
    _one = _one[["date", "revenue", "revenue_year", "revenue_month"]].reset_index(drop=True)
    try:
        _one.attrs["source"] = "TWSE-OpenAPI:t187ap05_L(keyless fallback,單股)"
        _one.attrs["fetched_at"] = pd.Timestamp.now("UTC").isoformat()
    except Exception:
        pass
    return _one


class _BatchRevenueFetchFailed(_CachedFailure):
    """`_fetch_batch_monthly_revenue_cached` 的「確定抓取失敗」出口專用(D2-f5 2026-09-28,§1.A-3(a))。

    `st.cache_data` 不快取例外 → 失敗的空表不會被凍成 6 小時;外層
    `_fetch_batch_monthly_revenue_with_status` 只接住本類別,取 `.payload`(＝修前會回傳的
    同一份空表)。刻意用私有子類別、不直接接 `CachedFailure`(同 rs_leader_service D2-f1 的
    理由):別處的 `CachedFailure` 若從下層漏出來,不會在這裡被誤當成 DataFrame 回傳。
    """


@st.cache_data(ttl=TTL_6HOUR, show_spinner=False)
def _fetch_batch_monthly_revenue_cached(months: int = 18) -> pd.DataFrame:
    """`fetch_batch_monthly_revenue()` 的快取層(原函式本體;TTL、參數、回傳同修前)。

    D2-f5(2026-09-28,§1.A-3(a)「只快取成功結果」):結果為空**且** OpenAPI 備援有市場
    **確定抓取失敗**(判準見 `_batch_twse_openapi` 的 `failed`)→ **拋** `_BatchRevenueFetchFailed`
    (不入快取),`.payload` 即修前會回傳的那一份空表。其餘結果(成功;以及沒有確定失敗的
    空表)照舊回傳、照舊快取。
    """
    _df = _batch_finmind(months)
    if _df is not None and not _df.empty:
        return _df
    print("[mrev-fetcher] batch FinMind 無資料/失敗 → TWSE+TPEx OpenAPI keyless fallback")
    _failed: list[str] = []
    _out = _batch_twse_openapi(failed=_failed)
    if _out.empty and _failed:
        raise _BatchRevenueFetchFailed(_out, "；".join(_failed))
    return _out


#: D2-f5(2026-09-28,§1.A-3(b)):全市場月營收的失敗退避。鍵 ＝ `months`(與快取層的快取鍵同義)。
#: 單鍵取數 → 固定冷卻 `FAIL_COOLDOWN_SEC`(不開遞增;遞增只給「一次重抓就要打數百次上游」的
#: 掃描層,這裡一次重抓 ＝ FinMind 1 次 ＋ OpenAPI 上市／上櫃各 1 次)。
_batch_fail_cooldown = _FailCooldown()


def _fetch_batch_monthly_revenue_with_status(months: int = 18) -> tuple[pd.DataFrame, bool]:
    """(全市場月營收, 這一份是不是**確定抓取失敗**)。**本函式不快取**;快取在 `_fetch_batch_monthly_revenue_cached`。

    第 1 項與 `fetch_batch_monthly_revenue(months)` 回的逐字相同。第 2 項為 True ＝ 本次(或冷卻期內
    記下的那次)是快取層判定的確定失敗 —— 給 L3 `shortage_screener_service` 判斷「兩個候選池來源都
    取不到」那一份能不能入它自己的快取(同一次呼叫取得,不必事後查退避表,沒有競態)。
    失敗後 `FAIL_COOLDOWN_SEC` 秒內同一個 `months` 不重打上游,回同一份空表;成功(含沒有確定
    失敗的空表)一次即解除;並行時期間有人成功過,較晚到的失敗不記(`FailCooldown` 世代)。
    """
    _hit, _gen = _batch_fail_cooldown.begin(months)
    if _hit is not _FC_NO_HIT:
        return _hit, True
    try:
        _df = _fetch_batch_monthly_revenue_cached(months)
    except _BatchRevenueFetchFailed as _bf:
        print(f"[mrev-fetcher] batch 全源無資料且 OpenAPI 確定抓取失敗({_bf})→ 不入快取,"
              f"{_batch_fail_cooldown.seconds:.0f}s 內不重打上游")
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
    「全市場月營收動能候選池」吃這一支)。現在那一種**不入快取**;失敗後
    `shared.fail_cooldown.FAIL_COOLDOWN_SEC` 秒內同一個 `months` 不重打上游,回同一份空表;
    成功一次即解除。**失敗 vs 真的沒資料的判準**(只認這一層看得到的訊號,拿不準一律照舊快取):
      · **確定失敗** ＝ 結果為空,且 OpenAPI 上市／上櫃至少一邊「`fetch_url` 回 None／非 200、
        或抓取／解 JSON 拋例外」(`_batch_twse_openapi` 的 `failed`)。TWSE/TPEx keyless 快照
        是整個上市／上櫃市場的最新月營收,打得到就不會是空的,所以「空＋有一邊確定打不到」
        歸因在抓取失敗。
      · FinMind 那一段**不計**:`finmind_client.finmind_get` 對非 200(含額度用罄／方案不支援)、
        逾時、連線錯誤一律回空表、**不拋例外** —— 這一層看到的只有「空」,與真的沒資料分不出來,
        不猜(§1);`_batch_finmind` 自己的 `except` 只接得到「已收到並解開的 JSON 在整理時出錯」
        這種確定性錯誤(同一份回應重抓也一樣),不是暫時性抓取失敗。無 token 也不計(設定,不是上游)。
      · 有資料的結果(即使某一邊市場失敗、只拿到一半)照舊快取 —— 本項只處理「失敗的空表」。
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
