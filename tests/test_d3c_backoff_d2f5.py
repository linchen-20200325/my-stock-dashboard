# -*- coding: utf-8 -*-
"""資料層修錯 D2-f5（2026-09-28，CLAUDE.md §1.A-3「只快取成功結果；失敗時退避，不連續轟炸來源」）。

三處的判定（動手前先以真的 `st.cache_data` 實地重現，見交付報告）：

  · **② L1 `monthly_revenue_fetcher.fetch_batch_monthly_revenue`**（`TTL_6HOUR`）——**有快取失敗，已修**。
    修前 TWSE/TPEx OpenAPI 備援**確定抓取失敗**（`fetch_url` 回 None／非 200、抓取或解 JSON 拋例外）
    時回的空表被快取 6 小時：來源恢復後同參數仍回空表、上游 0 次呼叫。現在快取層
    `_fetch_batch_monthly_revenue_cached` 在「結果為空 **且** OpenAPI 有一邊確定失敗」時拋私有
    `_BatchRevenueFetchFailed`（`st.cache_data` 不快取例外），外層接住、記 `FailCooldown`
    （`FAIL_COOLDOWN_SEC`，固定冷卻）：冷卻期內同一個 `months` 不重打、期滿重抓、成功即解除。
    **FinMind 那一段不計**：`finmind_client.finmind_get` 對非 200／逾時／連線錯誤一律回空表、不拋
    —— 這一層只看得到「空」，與真的沒資料分不出來，不猜（同 D2-f4 判準）。
  · **① L3 `shortage_screener_service._scan_cached`**（`TTL_1DAY`）——**有快取失敗，已修**。
    修前「兩個候選池來源都取不到」那一份結果被快取 1 天（就算 L1 已恢復）。現在**只有**全市場月營收
    是 L1 判定的確定抓取失敗時改拋私有 `_CandidatePoolFetchFailed`（不入快取），由 `run_shortage_scan`
    接住回逐字相同的 (rows, meta)；判定取自 L1 同一次呼叫（`fetch_batch_monthly_revenue.with_status`），
    沒有 `.with_status`（被換成純函式）一律當非失敗、照舊快取。本層**不另記退避**（同 D2-f1）：
    這條路唯一會打上游的是 L1 全市場月營收，它自己有冷卻；這條路也跑不到逐檔深掃。
  · **③ L1 `quarterly_financials_fetcher.fetch_quarterly_shortage_frame`**（`TTL_1DAY`）——**不改**。
    這一層看不到任何「確定失敗」訊號：它只透過 `finmind_get` 取數，而 `finmind_get` 對所有失敗都回空表、
    **從不拋例外**（`_finmind_rows_first` 的 `except` 在 production 路徑到不了）→ 回 `[]` 與「這檔真的
    沒有季報」分不出來 → 依判準照舊快取。本檔 `TestD2f5QuarterlyPremise` 把這個**前提**釘住：日後若
    `finmind_get` 改成會拋例外，前提測試轉紅，屆時再評估第 ③ 處。

「修前」的回傳一律用**獨立寫出的期望值**比對（不從被測檔推導），另以「修前模型」（把本次改動換回
origin/main `efca639` 原文的同一份模組）逐項對照。
不觸網：一律換掉 `finmind_get`／`proxy_helper.fetch_url`／存活池／逐檔季報與月營收／涵蓋率。
冷卻期用假時鐘：**只換 `shared.fail_cooldown` 的 `time`**（`st.cache_data` 的 TTL 不受影響，
故「把假時鐘推過冷卻期仍不重打」＝ 真的在快取裡，不是在退避裡）。
突變（`TestMutations`）：每一個突變體都讓本檔對應的共用檢查（`_check_*`）轉紅。

📌 批 D3e（2026-09-28）同步改（本檔其餘測試一字未動；各改動處皆標「D3e」）：上文「固定冷卻」自 D2-f25 起
改為遞增（起點 `FAIL_COOLDOWN_SEC`、上限 `TTL_1HOUR`）；「結果為空 **且** 有一邊確定失敗」自 D2-f23 起拿掉
「結果為空」（半邊表也不入快取）；單股 `fetch_monthly_revenue` 自 D2-f22 起也拆層。修前模型（`_prefix_mr`／
`_prefix_svc`）照舊是 `efca639` 原文 —— 因檔案結構改變而改用逐字常數重建。D3e 本身的測試在
`tests/test_d3e_mrev_fail_cache.py`。
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys
import threading
import time
import types

import pandas as pd
import pytest
import requests

import shared.fail_cooldown as FC
import src.data.core.finmind_client as FMC
import src.data.proxy.proxy_helper as PH
import src.data.stock.monthly_revenue_fetcher as MR
import src.data.stock.quarterly_financials_fetcher as QF
import src.services.fundamental_screener_service as FSS
import src.services.shortage_screener_service as SVC
from shared.fail_cooldown import FAIL_COOLDOWN_SEC
from shared.shortage_screen_thresholds import SHORTAGE_VERSION
from shared.ttls import TTL_1HOUR


def _load(src: str, name: str, file: str) -> types.ModuleType:
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = file
    sys.modules[name] = m
    try:
        exec(compile(src, file, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str], tag: str) -> types.ModuleType:
    """同 tests/test_d3b_backoff_d2f4_d2f7_d2f9.py：原始碼字面替換後另建一份模組（真模組不動）。

    `tag` 讓每個突變體有自己的模組名 —— `st.cache_data` 以「模組名＋函式名＋原始碼」當快取鍵。
    """
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    return _load(src, f"_mutant_d3c_{tag}_{mod.__name__.rsplit('.', 1)[-1]}", mod.__file__)


# ══════════════════════════════════════════════════════════════════
# 修前模型：把本次改動換回 origin/main（efca639）原文的同一份模組
# ══════════════════════════════════════════════════════════════════
#: efca639 `monthly_revenue_fetcher._batch_twse_openapi`（逐字）。
_PREFIX_TWSE_OPENAPI = '''def _batch_twse_openapi() -> pd.DataFrame:
    """keyless TWSE(上市)+ TPEx(上櫃)月營收快照 → 全市場 df(stock_id/date/revenue 元)。

    致命03 去 FinMind 單點:無 token,走 NAS proxy。單股/全市場 fallback 共用此入口。
    失敗回空 df(§1,上游 source_health 顯示 absent,不造假)。
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
                continue
            _parsed = _parse_twse_revenue_records(_r.json(), market=_mkt)
            print(f"[mrev-fetcher] TWSE fallback {_mkt}: {len(_parsed)} 檔月營收")
            _rows.extend(_parsed)
        except Exception as _e:
            print(f"[mrev-fetcher] TWSE fallback {_mkt} 失敗: {type(_e).__name__}: {_e}")
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


'''

#: efca639 `monthly_revenue_fetcher.fetch_batch_monthly_revenue`（逐字）。
_PREFIX_BATCH = '''@st.cache_data(ttl=TTL_6HOUR, show_spinner=False)
def fetch_batch_monthly_revenue(months: int = 18) -> pd.DataFrame:
    """全市場月營收。FinMind 主 → TWSE/TPEx OpenAPI keyless fallback(致命03 去單點)。

    Returns:
        DataFrame columns: stock_id / date / revenue(多股長表);全源無資料回空。
        fallback 僅提供最新月快照(每股 1 列),為 FinMind(帶 18 月歷史)全敗時降級補位。
    """
    _df = _batch_finmind(months)
    if _df is not None and not _df.empty:
        return _df
    print("[mrev-fetcher] batch FinMind 無資料/失敗 → TWSE+TPEx OpenAPI keyless fallback")
    return _batch_twse_openapi()
'''

#: efca639 `shortage_screener_service._scan_cached` ② 那一段（逐字）。
_PREFIX_SCAN_EXIT = '''    _batch = fetch_batch_monthly_revenue(months=18)
    if _batch is None or _batch.empty:
        return [], {
            "candidates": 0, "deep_scanned": 0, "scored": 0, "pool_source": "（無）",
            "note": ("⚠️ 兩個候選池來源都取不到：基本面快照為空（選股網初篩需先跑 cron 快照），"
                     "且全市場月營收批次不可用（此呼叫需 FinMind sponsor tier，你的方案不支援）。"),
            "source": "none", "fetched_at": _fetched_at, "version": SHORTAGE_VERSION}
'''

#: D3e（2026-09-28）：efca639 `monthly_revenue_fetcher.fetch_monthly_revenue`（逐字；D2-f22 起改名為快取層
#: `_fetch_monthly_revenue_cached`、外層另包冷卻 → 修前模型不能再從現行檔案切出來）。
_PREFIX_SINGLE = '''@st.cache_data(ttl=TTL_6HOUR, show_spinner=False)
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


'''

#: D3e：efca639 `_batch_finmind` 的 schema 樣本那一句（逐字；D2-f21 起改為只取首檔）。
_PREFIX_SAMPLE = ("            _sample_v = validate_or_reject(_result_b.head(36), MonthlyRevenueSchema,\n"
                  "                                           label='fetch_batch_monthly_revenue:sample')\n")

#: D3e：efca639 `_scan_cached` ② 的尾段（逐字；D2-f23 起在這裡多了「半邊表不入快取」）。
_PREFIX_SCAN_TAIL = '''
    _pool = _candidate_pool(_batch, max_n=max_scan)
    _pairs = [(c["stock_id"], c["revenue_yoy_last3"]) for c in _pool]
    _rows, _note = _score_and_diagnose(_pairs)
    return _rows, {
        "candidates": len(_pool), "deep_scanned": len(_pairs), "scored": len(_rows),
        "pool_source": "全市場月營收動能候選池（sponsor tier）",
        "note": _note,
        "source": "FinMind:MonthRevenue(batch)+FS+BS",
        "fetched_at": _fetched_at, "version": SHORTAGE_VERSION}
'''


def _prefix_mr(tag: str) -> types.ModuleType:
    src = pathlib.Path(MR.__file__).read_text(encoding="utf-8")
    # D3e：`_batch_finmind` 的樣本換回 efca639 原文；`_batch_twse_openapi` 之後整段以逐字常數重建
    # （efca639 在那之後只有：`_batch_twse_openapi` → 單股 → 全市場，兩支都直接掛 `st.cache_data`）。
    s0 = src.index("            _sample = _result_b.head(36)\n")
    s1 = src.index("label='fetch_batch_monthly_revenue:sample')\n", s0) + \
        len("label='fetch_batch_monthly_revenue:sample')\n")
    src = src[:s0] + _PREFIX_SAMPLE + src[s1:]
    a = src.index("def _batch_twse_openapi(")
    src = src[:a] + _PREFIX_TWSE_OPENAPI + _PREFIX_SINGLE + _PREFIX_BATCH
    return _load(src, f"_prefix_d3c_{tag}_monthly_revenue_fetcher", MR.__file__)


def _prefix_svc(tag: str) -> types.ModuleType:
    src = pathlib.Path(SVC.__file__).read_text(encoding="utf-8")
    a = src.index("    _batch, _batch_failed = _batch_revenue_with_status(months=18)")
    b = src.index("\n\ndef run_shortage_scan(")         # D3e：② 的尾段也換回 efca639 原文
    src = src[:a] + _PREFIX_SCAN_EXIT + _PREFIX_SCAN_TAIL + src[b:]
    c = src.index("    try:\n        rows, meta = _scan_cached(max_scan)\n")
    d = src.index("\n", src.index("rows, meta = _cf.payload")) + 1
    src = src[:c] + "    rows, meta = _scan_cached(max_scan)\n" + src[d:]
    return _load(src, f"_prefix_d3c_{tag}_shortage_screener_service", SVC.__file__)


# ══════════════════════════════════════════════════════════════════
# 共用：假時鐘、L1 上游替身、期望值
# ══════════════════════════════════════════════════════════════════
_COVERAGE = "（涵蓋率替身）"
#: 修前 `_scan_cached` ②「兩個候選池來源都取不到」寫的字（逐字抄寫）。
_FAIL_NOTE = ("⚠️ 兩個候選池來源都取不到：基本面快照為空（選股網初篩需先跑 cron 快照），"
              "且全市場月營收批次不可用（此呼叫需 FinMind sponsor tier，你的方案不支援）。")
_TWSE_OK = [{"公司代號": "2330", "公司名稱": "台積電", "資料年月": "11505",
             "營業收入-當月營收": "263,714,000"}]
_TPEX_OK = [{"公司代號": "6488", "公司名稱": "環球晶", "資料年月": "11505",
             "營業收入-當月營收": "1,000"}]


@pytest.fixture
def fc_clock(monkeypatch):
    """可手動推進的假 monotonic 時鐘 —— **只**換 `shared.fail_cooldown` 模組裡的 `time`（同 #741）。"""
    t = {"now": float(int(time.monotonic()))}
    monkeypatch.setattr(FC, "time", types.SimpleNamespace(monotonic=lambda: t["now"]))
    return t


@pytest.fixture
def frozen_now(monkeypatch):
    """`fetched_at` 取 `pd.Timestamp.now("UTC")` —— 凍結後才能與修前的期望值逐字比。"""
    fixed = pd.Timestamp("2026-09-28T01:02:03.456789", tz="UTC")
    monkeypatch.setattr(pd.Timestamp, "now", classmethod(lambda cls, tz=None: fixed))
    return fixed


class _Resp:
    """`fetch_url` 回應替身（status_code ＋ json；`exc` 不為 None 時 json() 拋出）。"""

    def __init__(self, payload=None, *, status: int = 200, exc: Exception | None = None):
        self.status_code = status
        self._payload = payload
        self._exc = exc

    def json(self):
        if self._exc is not None:
            raise self._exc
        return self._payload


def _fm_one_stock(sid: str = "1001", n: int = 19) -> pd.DataFrame:
    """FinMind 全市場月營收的成功回應（單一檔、n 個月、逐月成長）。

    刻意只放一檔：`_batch_finmind` 以前 36 列當 schema 樣本，兩檔以上會跨檔（日期不單調）→
    整批棄用（既有行為，非本次範圍）。
    （D3e：該既有問題即 D2-f21，批 D3e 已改為只取首檔；本檔照舊用一檔即可，多檔見
    `tests/test_d3e_mrev_fail_cache.py`。）"""
    dates = pd.date_range("2025-01-01", periods=n, freq="MS").strftime("%Y-%m-%d")
    return pd.DataFrame({"stock_id": [sid] * n, "date": list(dates),
                         "revenue": [float(100 + i * 8) for i in range(n)]})


class _MrWorld:
    """L1 全市場月營收的上游替身：FinMind（`finmind_get`）＋ OpenAPI（`proxy_helper.fetch_url`）。

    `fm`：empty（回空表 —— 失敗或真的沒有，這一層分不出來）／bad_schema（回應在整理時拋 KeyError）／ok。
    `twse`／`tpex`：ok／none（`fetch_url` 回 None）／non200／json_err（回應不是 JSON）／raise（抓取拋例外）／
    empty200（200 但 0 筆）／dict200（200 但 JSON 不是 list）。
    """

    def __init__(self):
        self.fm, self.twse, self.tpex = "empty", "none", "none"
        self.calls = {"fm": 0, "twse": 0, "tpex": 0}
        self._lock = threading.Lock()

    def _bump(self, k):
        with self._lock:
            self.calls[k] += 1

    def recover(self):
        self.twse = self.tpex = "ok"

    def finmind_get(self, dataset, **_kw):
        self._bump("fm")
        if self.fm == "ok":
            return _fm_one_stock()
        if self.fm == "bad_schema":      # 有 revenue／stock_id／revenue_year、缺 date 與 revenue_month
            return pd.DataFrame({"stock_id": ["1101"], "revenue": [1.0], "revenue_year": [2026]})
        return pd.DataFrame()

    def fetch_url(self, url, headers=None, params=None, timeout=20, attempts=3):
        side = "twse" if "openapi.twse.com.tw" in url else "tpex"
        self._bump(side)
        mode = getattr(self, side)
        if mode == "ok":
            return _Resp(list(_TWSE_OK if side == "twse" else _TPEX_OK))
        if mode == "none":
            return None
        if mode == "non200":
            return _Resp(None, status=503)
        if mode == "json_err":
            return _Resp(None, exc=ValueError("Expecting value: line 1 column 1 (char 0)"))
        if mode == "raise":
            raise ConnectionError("proxy down")
        if mode == "empty200":
            return _Resp([])
        if mode == "dict200":
            return _Resp({"error": "maintenance"})
        raise AssertionError(mode)


def _install_mr(mod, monkeypatch, w: _MrWorld) -> None:
    monkeypatch.setattr(mod, "finmind_get", w.finmind_get)
    mod.fetch_batch_monthly_revenue.clear()


@pytest.fixture
def mr(monkeypatch, fc_clock):
    """換掉 L1 全市場月營收的上游（FinMind ＋ OpenAPI）；預設 FinMind 回空、OpenAPI 兩邊 `fetch_url` 回 None。"""
    w = _MrWorld()
    monkeypatch.setenv("FINMIND_TOKEN", "dummy-token")
    monkeypatch.delenv("FM_TOKEN", raising=False)
    # 同 tests/test_monthly_revenue_twse_fallback.py：patch 真正持有者 proxy_helper，不 patch package。
    monkeypatch.setattr(PH, "fetch_url", w.fetch_url)
    _install_mr(MR, monkeypatch, w)
    yield w
    MR.fetch_batch_monthly_revenue.clear()


def _assert_prefix_failure_frame(df) -> None:
    """修前 OpenAPI 全失敗時 `_batch_twse_openapi` 回的是 `return pd.DataFrame()` —— 逐字比（無旗標、無 attrs）。"""
    ref = pd.DataFrame()
    assert isinstance(df, pd.DataFrame)
    assert repr(df) == repr(ref)
    pd.testing.assert_frame_equal(df, ref)
    assert type(df.index) is type(ref.index) and df.attrs == {}


def _assert_openapi_frame(df) -> None:
    """上游恢復後的 OpenAPI 快照（獨立寫出：上市 2330、上櫃 6488；千元 ×1000 ＝ 元）。"""
    assert isinstance(df, pd.DataFrame) and not df.empty, "應拿到上游恢復後的新值，卻是空表"
    assert list(df["stock_id"]) == ["2330", "6488"]
    assert list(df["revenue"]) == [263_714_000.0 * 1000, 1_000.0 * 1000]
    assert list(df["date"].dt.strftime("%Y-%m-%d")) == ["2026-05-01", "2026-05-01"]
    assert "TWSE-OpenAPI:t187ap05_L" in df.attrs["source"]


# ══════════════════════════════════════════════════════════════════
# 共用檢查（主測試與突變測試共用：突變體必須讓它們轉紅）
# ══════════════════════════════════════════════════════════════════
def _check_l1_failure_backs_off_then_recovers(mod, w: _MrWorld, clock: dict, *, months: int = 18) -> None:
    """② 確定失敗：回修前同一份空表 → 冷卻期內 0 次上游 → 期滿重打拿到新值 → 成功照舊快取。"""
    _assert_prefix_failure_frame(mod.fetch_batch_monthly_revenue(months))
    n1 = dict(w.calls)
    assert n1["twse"] >= 1 and n1["tpex"] >= 1, "前提：OpenAPI 兩邊都打過"
    w.recover()                                           # 上游恢復，但仍在冷卻期內
    clock["now"] += FAIL_COOLDOWN_SEC - 1
    within = [mod.fetch_batch_monthly_revenue(months) for _ in range(3)]
    assert w.calls == n1, "冷卻期內 0 次上游呼叫"
    for df in within:
        _assert_prefix_failure_frame(df)                  # 冷卻期內回的是同一份失敗空表
    clock["now"] += 1                                     # 剛好滿冷卻期（`<` 比較：滿即過期）
    df = mod.fetch_batch_monthly_revenue(months)
    assert not df.empty, "冷卻期過 → 重打並拿到新值（修前：空表凍 6 小時）"
    _assert_openapi_frame(df)
    assert w.calls["twse"] == n1["twse"] + 1 and w.calls["tpex"] == n1["tpex"] + 1
    n2 = dict(w.calls)
    clock["now"] += 100 * FAIL_COOLDOWN_SEC               # 退避時鐘怎麼走都碰不到成功快取
    pd.testing.assert_frame_equal(mod.fetch_batch_monthly_revenue(months), df)
    assert w.calls == n2, "成功照舊快取"


def _check_l1_ambiguous_still_cached(mod, w: _MrWorld, clock: dict) -> None:
    """② 沒有確定失敗的空表（這一層分不出失敗與真的沒資料）→ 照舊快取，不記退避。"""
    first = mod.fetch_batch_monthly_revenue()
    assert first.empty
    n1 = dict(w.calls)
    w.fm, w.twse, w.tpex = "ok", "ok", "ok"               # 就算上游此刻變了……
    clock["now"] += 100 * FAIL_COOLDOWN_SEC               # ……且遠超過冷卻期
    again = mod.fetch_batch_monthly_revenue()
    assert w.calls == n1, "照舊入 6 小時快取（不是退避）：上游呼叫數不變"
    assert again.empty and repr(again) == repr(first)


def _check_l1_persistent_failure_once_per_cooldown(mod, w: _MrWorld, clock: dict) -> None:
    # D3e（D2-f25）：冷卻由固定改遞增 —— 第 i 段冷卻 ＝ FAIL_COOLDOWN_SEC × 2^(i−1)（這 3 段都未達上限
    # TTL_1HOUR）；每一段照舊只打 1 次，且該段最後一秒仍不重打。
    for i in range(1, 4):
        window = FAIL_COOLDOWN_SEC * 2 ** (i - 1)
        for _ in range(4):
            _assert_prefix_failure_frame(mod.fetch_batch_monthly_revenue())
        clock["now"] += window - 1
        _assert_prefix_failure_frame(mod.fetch_batch_monthly_revenue())
        assert w.calls["twse"] == i and w.calls["tpex"] == i, \
            "持續失敗：每一段冷卻只打 1 次（不入快取、也不轟炸）"
        clock["now"] += 1


def _check_l1_cooldown_is_per_months(mod, w: _MrWorld, clock: dict) -> None:
    _assert_prefix_failure_frame(mod.fetch_batch_monthly_revenue(18))
    w.recover()
    _assert_openapi_frame(mod.fetch_batch_monthly_revenue(12))
    _assert_prefix_failure_frame(mod.fetch_batch_monthly_revenue(18))
    assert w.calls["twse"] == 2, "退避鍵＝months（與快取鍵同義）：別的 months 照常抓、原鍵仍在冷卻"


def _check_l1_clear_resets_both(mod, w: _MrWorld, clock: dict) -> None:
    mod.fetch_batch_monthly_revenue()                     # 失敗 → 退避中
    w.recover()
    mod.fetch_batch_monthly_revenue.clear()
    df = mod.fetch_batch_monthly_revenue()
    assert w.calls["twse"] == 2, ".clear() 清掉退避紀錄 → 立刻重打"
    _assert_openapi_frame(df)
    mod.fetch_batch_monthly_revenue.clear()
    mod.fetch_batch_monthly_revenue()
    assert w.calls["twse"] == 3, ".clear() 清掉成功快取 → 重打"


def _check_l1_success_bumps_generation(mod, w: _MrWorld, clock: dict) -> None:
    """別的 session 已開抓（記下世代）→ 本次成功 → 那次較晚寫入的失敗不得進退避表。"""
    _, g = mod._batch_fail_cooldown.begin(18)
    w.recover()
    _assert_openapi_frame(mod.fetch_batch_monthly_revenue(18))
    mod._batch_fail_cooldown.fail(18, g, pd.DataFrame())  # 同儕晚到的失敗
    assert 18 not in mod._batch_fail_cooldown
    _assert_openapi_frame(mod.fetch_batch_monthly_revenue(18))


def _sans_time(res: tuple) -> tuple:
    """(rows, meta) 去掉 `fetched_at`：L3 不快取的那一份每次重算，`fetched_at` 是當次算出的時點
    （同 D2-f1 大盤失敗那條；逐字比對見凍結時鐘的 `test_output_identical_to_prefix`）。"""
    rows, meta = res
    return rows, {k: v for k, v in meta.items() if k != "fetched_at"}


def _check_l3_failure_not_cached_then_recovers(mod, w: _MrWorld, side: dict, clock: dict) -> None:
    """① 候選池兩來源都取不到（L1 確定失敗）：L3 不入快取 → L1 冷卻期內重算但 0 次上游 →
    期滿即拿到新排行 → 成功照舊快取。"""
    rows, meta = mod.run_shortage_scan()
    assert rows == [] and meta["note"] == _FAIL_NOTE
    n1 = dict(w.calls)
    assert n1 == {"fm": 1, "twse": 1, "tpex": 1} and side["pool"] == 1
    w.fm = "ok"                                           # FinMind 全市場恢復，但仍在 L1 冷卻期內
    clock["now"] += FAIL_COOLDOWN_SEC - 1
    within = [mod.run_shortage_scan() for _ in range(3)]
    assert w.calls == n1, "L1 冷卻期內 0 次上游呼叫"
    assert side["pool"] == 4, "L3 沒有快取這一份（每次都重算，修前：凍 1 天）"
    assert side["qtr"] == 0, "失敗那條路跑不到逐檔深掃"
    assert all(_sans_time(r) == _sans_time((rows, meta)) for r in within), "冷卻期內回同一份失敗結果"
    clock["now"] += 1
    rows2, meta2 = mod.run_shortage_scan()
    assert len(rows2) == 1 and rows2[0]["代碼"] == "1001" and meta2["note"] == "", \
        "L1 冷卻期過的下一次即拿到新排行（修前：失敗結果凍 1 天）"
    assert meta2["pool_source"] == "全市場月營收動能候選池（sponsor tier）"
    assert w.calls["fm"] == 2 and side["qtr"] == 1
    n2, s2 = dict(w.calls), dict(side)
    clock["now"] += 100 * FAIL_COOLDOWN_SEC
    assert mod.run_shortage_scan() == (rows2, meta2)
    assert w.calls == n2 and side == s2, "恢復後的成功照舊入快取"


def _check_l3_ambiguous_still_cached(mod, w: _MrWorld, side: dict, clock: dict) -> None:
    """① L1 沒有確定失敗的空表（兩邊都有回 200、只是 0 筆）→ L3 照舊快取。"""
    w.twse = w.tpex = "empty200"
    first = mod.run_shortage_scan()
    assert first[0] == [] and first[1]["note"] == _FAIL_NOTE
    n1, s1 = dict(w.calls), dict(side)
    w.fm, w.twse, w.tpex = "ok", "ok", "ok"
    clock["now"] += 100 * FAIL_COOLDOWN_SEC
    again = mod.run_shortage_scan()
    assert w.calls == n1 and side == s1, "照舊入 1 天快取：第二次連存活池都不再問"
    assert again == first


# ══════════════════════════════════════════════════════════════════
# ② L1 全市場月營收：確定失敗不入快取、冷卻期內不重打、期滿重打拿到新值
# ══════════════════════════════════════════════════════════════════
#: 「確定抓取失敗」的各種樣態（結果為空 ＋ OpenAPI 至少一邊確定打不到）。值：(fm, twse, tpex, 有無 token)。
_FAILURES = {
    "both_fetch_none": ("empty", "none", "none", True),
    "both_non200": ("empty", "non200", "non200", True),
    "both_json_decode": ("empty", "json_err", "json_err", True),
    "both_fetch_raise": ("empty", "raise", "raise", True),
    "twse_none_tpex_empty200": ("empty", "none", "empty200", True),
    "twse_empty200_tpex_raise": ("empty", "empty200", "raise", True),
    "no_token": ("empty", "none", "none", False),
    "finmind_bad_schema": ("bad_schema", "none", "none", True),
}


def _set_world(w: _MrWorld, monkeypatch, spec) -> None:
    w.fm, w.twse, w.tpex, token = spec
    if not token:
        monkeypatch.delenv("FINMIND_TOKEN", raising=False)


class TestD2f5BatchFailureNotCached:
    @pytest.mark.parametrize("case", sorted(_FAILURES))
    def test_failure_backs_off_then_recovers(self, mr, fc_clock, monkeypatch, case):
        _set_world(mr, monkeypatch, _FAILURES[case])
        _check_l1_failure_backs_off_then_recovers(MR, mr, fc_clock)
        assert 18 not in MR._batch_fail_cooldown, "成功即解除退避"

    def test_failure_recorded_not_cached(self, mr):
        _assert_prefix_failure_frame(MR.fetch_batch_monthly_revenue())
        assert 18 in MR._batch_fail_cooldown, "失敗記進退避表（鍵＝months）"
        assert MR._batch_fail_cooldown.seconds == FAIL_COOLDOWN_SEC
        # D3e（D2-f25）：原斷言「max_seconds is None（固定冷卻，不開遞增）」→ 改為遞增、上限 TTL_1HOUR。
        assert MR._batch_fail_cooldown.max_seconds == TTL_1HOUR, "D2-f25：遞增退避，上限 TTL_1HOUR"

    def test_persistent_failure_hits_upstream_once_per_cooldown(self, mr, fc_clock):
        _check_l1_persistent_failure_once_per_cooldown(MR, mr, fc_clock)

    def test_cooldown_is_per_months(self, mr, fc_clock):
        _check_l1_cooldown_is_per_months(MR, mr, fc_clock)

    def test_late_failure_does_not_override_peer_success(self, mr, monkeypatch):
        """競態：本次抓取期間另一個 session 已成功 → 本次較晚的失敗不得寫進退避表。"""
        def _fail_after_peer_success(months=18):
            MR._batch_fail_cooldown.success(months)
            raise MR._BatchRevenueFetchFailed(pd.DataFrame(), "late failure")
        monkeypatch.setattr(MR, "_fetch_batch_monthly_revenue_cached", _fail_after_peer_success)
        _assert_prefix_failure_frame(MR.fetch_batch_monthly_revenue())
        assert 18 not in MR._batch_fail_cooldown

    def test_success_bumps_generation(self, mr, fc_clock):
        _check_l1_success_bumps_generation(MR, mr, fc_clock)

    def test_backoff_returns_a_copy(self, mr):
        df = MR.fetch_batch_monthly_revenue()
        df["污染"] = []
        df.attrs["污染"] = True
        _assert_prefix_failure_frame(MR.fetch_batch_monthly_revenue())

    def test_parallel_calls_during_failure(self, mr):
        n_threads = 8
        barrier = threading.Barrier(n_threads)
        results, errors = [], []

        def _worker():
            try:
                barrier.wait(timeout=5)
                results.append(MR.fetch_batch_monthly_revenue())
            except Exception as e:  # noqa: BLE001 — 收集起來讓斷言報出來
                errors.append(e)

        threads = [threading.Thread(target=_worker, daemon=True) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        assert not any(t.is_alive() for t in threads), "不得死鎖"
        assert errors == [] and len(results) == n_threads
        for df in results:
            _assert_prefix_failure_frame(df)
        assert 1 <= mr.calls["twse"] <= n_threads
        n = dict(mr.calls)
        MR.fetch_batch_monthly_revenue()
        assert mr.calls == n, "並行失敗之後：冷卻期內不再重打"

    def test_failure_log_then_silent_in_cooldown(self, mr, capsys):
        MR.fetch_batch_monthly_revenue()
        out = capsys.readouterr().out
        assert "[mrev-fetcher] TWSE fallback 上市 非200: status=None" in out, "修前的失敗 log 照印"
        # D3e（D2-f25）：冷卻改遞增，log 尾巴由「{秒}s 內不重打上游」改成寫出起點與上限（固定秒數已不成立）。
        assert ("[mrev-fetcher] batch 全源無資料且 OpenAPI 確定抓取失敗(上市: status=None；上櫃: status=None)"
                f"→ 不入快取,冷卻期內不重打上游(冷卻由 {FAIL_COOLDOWN_SEC:.0f}s 起、連續失敗加倍、"
                f"上限 {TTL_1HOUR:.0f}s)") in out
        MR.fetch_batch_monthly_revenue()
        assert capsys.readouterr().out == "", "冷卻期內不重打，也就不再印失敗 log"


# ══════════════════════════════════════════════════════════════════
# ② 成功與「分不出失敗與真的沒資料」照舊快取；公開介面不變
# ══════════════════════════════════════════════════════════════════
#: 沒有確定失敗的空表：值同 `_FAILURES`。
_AMBIGUOUS = {
    "both_200_but_zero_rows": ("empty", "empty200", "empty200", True),
    "json_not_a_list": ("empty", "dict200", "dict200", True),
    "finmind_bad_schema_and_openapi_empty": ("bad_schema", "empty200", "empty200", True),
}


class TestD2f5BatchStillCached:
    @pytest.mark.parametrize("case", sorted(_AMBIGUOUS))
    def test_ambiguous_empty_still_cached(self, mr, fc_clock, monkeypatch, case):
        _set_world(mr, monkeypatch, _AMBIGUOUS[case])
        _check_l1_ambiguous_still_cached(MR, mr, fc_clock)
        assert len(MR._batch_fail_cooldown) == 0, "不是確定失敗，不記退避"

    @pytest.mark.parametrize("fm", ["ok", "empty"], ids=["finmind_ok", "openapi_ok"])
    def test_success_cached_and_layout_unchanged(self, mr, fc_clock, fm):
        mr.fm, mr.twse, mr.tpex = fm, "ok", "ok"
        first = MR.fetch_batch_monthly_revenue()
        assert not first.empty
        n1 = dict(mr.calls)
        mr.fm, mr.twse, mr.tpex = "empty", "none", "none"      # 之後上游壞了也不影響 TTL 內的成功
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
        pd.testing.assert_frame_equal(MR.fetch_batch_monthly_revenue(), first)
        assert mr.calls == n1 and len(MR._batch_fail_cooldown) == 0
        tree = ast.parse(pathlib.Path(MR.__file__).read_text(encoding="utf-8"))
        fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        assert [ast.unparse(d) for d in fns["_fetch_batch_monthly_revenue_cached"].decorator_list] == \
            ["st.cache_data(ttl=TTL_6HOUR, show_spinner=False)"], "快取層參數同修前（原本掛在公開函式上那一行）"
        assert fns["fetch_batch_monthly_revenue"].decorator_list == [], "外層不快取 —— 失敗才不會被凍住"

    def test_partial_market_failure_with_data_not_cached_d3e(self, mr, fc_clock):
        """D3e（D2-f23）：原本這條是「範圍外（照舊）：一邊市場失敗、另一邊有資料 ⇒ 不是『失敗的空表』，照舊
        快取」（原名 `test_partial_market_failure_with_data_still_cached`）。批 D3e 起改為**不入快取**：回傳同一份
        半邊表並記退避，冷卻期過後重抓拿到兩邊。完整檢查見 `tests/test_d3e_mrev_fail_cache.py`。"""
        mr.twse, mr.tpex = "none", "ok"
        first = MR.fetch_batch_monthly_revenue()
        assert list(first["stock_id"]) == ["6488"]
        assert 18 in MR._batch_fail_cooldown, "半邊失敗記進退避表（鍵＝months）"
        n1 = dict(mr.calls)
        mr.recover()
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        _assert_openapi_frame(MR.fetch_batch_monthly_revenue())
        assert mr.calls["twse"] == n1["twse"] + 1 and len(MR._batch_fail_cooldown) == 0

    def test_clear_resets_cache_and_backoff(self, mr, fc_clock):
        _check_l1_clear_resets_both(MR, mr, fc_clock)

    def test_public_signature_unchanged(self):
        import inspect
        (name, p), = inspect.signature(MR.fetch_batch_monthly_revenue).parameters.items()
        assert (name, p.kind, p.default) == ("months", p.POSITIONAL_OR_KEYWORD, 18), "公開簽名同修前"
        assert callable(MR.fetch_batch_monthly_revenue.clear)
        assert MR.fetch_batch_monthly_revenue.with_status is MR._fetch_batch_monthly_revenue_with_status
        (name, p), = inspect.signature(MR._batch_twse_openapi).parameters.items()
        assert (name, p.kind, p.default) == ("failed", p.KEYWORD_ONLY, None), \
            "私有函式只多一個選用關鍵字參數（預設不傳＝修前；D3e 起單股 fallback 也傳）"

    def test_single_stock_first_call_same_as_prefix_d3e(self, mr, fc_clock):
        """D3e（D2-f22）：原本這條是「範圍外（照舊，未改）：單股 `fetch_monthly_revenue` 的 OpenAPI 備援仍是修前
        行為（不傳 `failed`）」（原名 `test_single_stock_fetcher_untouched`）。批 D3e 起單股也拆層、傳 `failed`
        （完整檢查見 `tests/test_d3e_mrev_fail_cache.py`）；這裡只留：第一次呼叫的回傳仍與修前模型逐字相同。"""
        pre = _prefix_mr("single")
        pre.finmind_get = mr.finmind_get
        try:
            pre.fetch_monthly_revenue.clear()
            MR.fetch_monthly_revenue.clear()
            a = MR.fetch_monthly_revenue("2330")
            b = pre.fetch_monthly_revenue("2330")
            assert repr(a) == repr(b) and a.attrs == b.attrs
            src = pathlib.Path(MR.__file__).read_text(encoding="utf-8")
            body = src[src.index("def _fetch_monthly_revenue_cached("):src.index("class _BatchRevenueFetchFailed(")]
            assert "_batch_twse_openapi(failed=_failed)" in body
        finally:
            MR.fetch_monthly_revenue.clear()
            pre.fetch_monthly_revenue.clear()


class TestD2f5BatchIdenticalToPrefix:
    """修前模型（efca639 原文）與現行在同一個世界、第一次呼叫的回傳逐項相同；`_batch_twse_openapi()`
    （不傳 `failed`）連 log 都逐字相同。"""

    @pytest.mark.parametrize("case", sorted(_FAILURES) + sorted(_AMBIGUOUS) + ["finmind_ok", "openapi_ok",
                                                                                   "partial"])
    def test_first_call_identical(self, mr, monkeypatch, frozen_now, case):
        spec = {**_FAILURES, **_AMBIGUOUS,
                "finmind_ok": ("ok", "ok", "ok", True), "openapi_ok": ("empty", "ok", "ok", True),
                "partial": ("empty", "none", "ok", True)}[case]
        pre = _prefix_mr(f"first_{case}")
        pre.finmind_get = mr.finmind_get
        _set_world(mr, monkeypatch, spec)
        try:
            pre.fetch_batch_monthly_revenue.clear()
            got, want = MR.fetch_batch_monthly_revenue(), pre.fetch_batch_monthly_revenue()
            assert repr(got) == repr(want)
            pd.testing.assert_frame_equal(got, want)
            assert got.attrs == want.attrs and list(got.dtypes) == list(want.dtypes)
        finally:
            pre.fetch_batch_monthly_revenue.clear()

    @pytest.mark.parametrize("modes", [("none", "none"), ("json_err", "raise"), ("ok", "ok"),
                                       ("empty200", "dict200"), ("non200", "ok")])
    def test_twse_openapi_default_identical_incl_log(self, mr, frozen_now, capsys, modes):
        mr.twse, mr.tpex = modes
        pre = _prefix_mr(f"openapi_{'_'.join(modes)}")
        got = MR._batch_twse_openapi()
        log_now = capsys.readouterr().out
        want = pre._batch_twse_openapi()
        log_pre = capsys.readouterr().out
        assert repr(got) == repr(want) and got.attrs == want.attrs
        assert log_now == log_pre, "預設不傳 failed：log 一字不差"


# ══════════════════════════════════════════════════════════════════
# ① L3 缺貨掃描：候選池兩來源都取不到（L1 確定失敗）不入快取
# ══════════════════════════════════════════════════════════════════
def _strong_frame() -> list[dict]:
    def _q(rev, gp, cogs, cl, inv):
        return {"label": "Q", "date": "2025-01-01", "revenue": rev,
                "gross_profit": gp, "cogs": cogs, "contract_liab": cl, "inventory": inv}
    return [
        _q(1000, 600, 400, 200, 300), _q(1000, 550, 400, 160, 350),
        _q(1000, 540, 400, 150, 360), _q(1000, 530, 400, 150, 380),
        _q(1000, 500, 400, 150, 400), _q(1000, 500, 400, 140, 400),
        _q(1000, 500, 400, 140, 400), _q(1000, 500, 400, 140, 400),
    ]


def _install_svc(mod, monkeypatch, plan: dict, side: dict) -> None:
    lock = threading.Lock()

    def _bump(k):
        with lock:
            side[k] += 1

    def _pool(max_n):
        _bump("pool")
        return list(plan["pool"])[:max_n]

    def _qtr(sid, quarters=12):
        _bump("qtr")
        return _strong_frame() if plan["qtr"] == "strong" else []

    def _mrev(sid, months=18):
        _bump("mrev")
        dates = pd.date_range("2024-01-01", periods=18, freq="MS")
        return pd.DataFrame({"date": dates, "revenue": [float(100 + i * 8) for i in range(18)]})

    monkeypatch.setattr(mod, "_survivor_pool", _pool)
    monkeypatch.setattr(mod, "fetch_quarterly_shortage_frame", _qtr)
    monkeypatch.setattr(mod, "fetch_monthly_revenue", _mrev)
    monkeypatch.setattr(FSS, "get_snapshot_coverage_note", lambda: _COVERAGE)
    mod._scan_cached.clear()


@pytest.fixture
def sv(monkeypatch, mr):
    """換掉 L3 的存活池／逐檔季報／逐檔月營收／涵蓋率；全市場月營收走**真的 L1**（上游由 `mr` 換掉）。
    預設：存活池為空、季報強缺貨 → 走 ② 全市場批次，且 L1 確定失敗。"""
    plan = {"pool": [], "qtr": "strong"}
    side = {"pool": 0, "qtr": 0, "mrev": 0}
    _install_svc(SVC, monkeypatch, plan, side)
    yield plan, side
    SVC._scan_cached.clear()


def _fail_meta(fetched_at: str) -> dict:
    """修前 `_scan_cached` ② 回傳的 meta（逐字抄寫）＋ 快取外注入的涵蓋率。"""
    return {"candidates": 0, "deep_scanned": 0, "scored": 0, "pool_source": "（無）",
            "note": _FAIL_NOTE, "source": "none", "fetched_at": fetched_at,
            "version": SHORTAGE_VERSION, "coverage_note": _COVERAGE}


class TestD2f5ScanFailureNotCached:
    def test_not_cached_then_recovers_after_l1_cooldown(self, sv, mr, fc_clock):
        _plan, side = sv
        _check_l3_failure_not_cached_then_recovers(SVC, mr, side, fc_clock)

    def test_persistent_failure_upstream_once_per_l1_cooldown(self, sv, mr, fc_clock):
        _plan, side = sv
        for i in range(1, 4):
            window = FAIL_COOLDOWN_SEC * 2 ** (i - 1)        # D3e（D2-f25）：L1 冷卻遞增（原為固定 FAIL_COOLDOWN_SEC）
            for _ in range(4):
                rows, meta = SVC.run_shortage_scan()
                assert rows == [] and meta["note"] == _FAIL_NOTE
            fc_clock["now"] += window - 1
            rows, meta = SVC.run_shortage_scan()
            assert rows == [] and meta["note"] == _FAIL_NOTE
            assert mr.calls == {"fm": i, "twse": i, "tpex": i}, "每一段 L1 冷卻只打上游 1 次"
            fc_clock["now"] += 1
        assert side["qtr"] == 0 and side["mrev"] == 0, "失敗那條路 0 次逐檔深掃"

    @pytest.mark.parametrize("kwargs", [{}, {"name_map": {"1001": "甲"}}, {"max_scan": 10},
                                        {"refresh": True}], ids=["default", "name_map", "max_scan", "refresh"])
    def test_output_identical_to_prefix(self, sv, frozen_now, kwargs):
        want = _fail_meta(frozen_now.isoformat())
        for _ in range(2):                                   # 第一次與冷卻期內（refresh 則每次都重打）
            rows, meta = SVC.run_shortage_scan(**kwargs)
            assert rows == [] and meta == want
            assert list(meta) == list(want), "鍵的順序也同修前"
            assert repr((rows, meta)) == repr(([], want))

    def test_matches_prefix_model_first_call(self, sv, mr, monkeypatch, frozen_now):
        got = SVC.run_shortage_scan()
        pre_mr, pre_svc = _prefix_mr("scan_first"), _prefix_svc("scan_first")
        pre_mr.finmind_get = mr.finmind_get
        plan2, side2 = {"pool": [], "qtr": "strong"}, {"pool": 0, "qtr": 0, "mrev": 0}
        _install_svc(pre_svc, monkeypatch, plan2, side2)
        monkeypatch.setattr(pre_svc, "fetch_batch_monthly_revenue", pre_mr.fetch_batch_monthly_revenue)
        try:
            assert repr(pre_svc.run_shortage_scan()) == repr(got)
        finally:
            pre_svc._scan_cached.clear()
            pre_mr.fetch_batch_monthly_revenue.clear()

    def test_ui_text_same_as_prefix_within_cooldown(self, sv, mr, monkeypatch):
        """K1：v2 找標的「缺貨動能」列 —— 修前失敗時顯示什麼，修後在冷卻期內顯示同一句。"""
        from src.ui.views import page_find as PF
        now = [PF._load_shortage(("shortage",)) for _ in range(3)]
        assert now == [(None, _FAIL_NOTE)] * 3
        assert mr.calls == {"fm": 1, "twse": 1, "tpex": 1}
        pre_mr, pre_svc = _prefix_mr("ui"), _prefix_svc("ui")
        pre_mr.finmind_get = mr.finmind_get
        _install_svc(pre_svc, monkeypatch, {"pool": [], "qtr": "strong"}, {"pool": 0, "qtr": 0, "mrev": 0})
        monkeypatch.setattr(pre_svc, "fetch_batch_monthly_revenue", pre_mr.fetch_batch_monthly_revenue)
        monkeypatch.setattr(SVC, "run_shortage_scan", pre_svc.run_shortage_scan)
        try:
            assert PF._load_shortage(("shortage",)) == (None, _FAIL_NOTE)
        finally:
            pre_svc._scan_cached.clear()
            pre_mr.fetch_batch_monthly_revenue.clear()

    def test_known_cost_global_cache_clear_keeps_l1_cooldown(self, sv, mr, fc_clock):
        """已知代價（據實釘住，與 #741 列的 D2-f8／D2-f11 同型）：全站 `st.cache_data.clear()`（v1 側欄
        「強制刷新」）清不掉 L1 冷卻 —— 冷卻期內仍回失敗、不重抓；期滿即恢復。`refresh=True` 會清（見下一條）。
        這裡只清這兩支的 `st.cache_data`（＝全站 clear 對它們的效果），不在測試行程裡真的清全站快取。"""
        SVC.run_shortage_scan()
        mr.fm = "ok"
        SVC._scan_cached.clear()
        MR._fetch_batch_monthly_revenue_cached.clear()
        assert 18 in MR._batch_fail_cooldown, "冷卻是一般 Python 物件，任何 st.cache_data 的 clear 都碰不到"
        rows, meta = SVC.run_shortage_scan()
        assert rows == [] and meta["note"] == _FAIL_NOTE and mr.calls["fm"] == 1
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        assert len(SVC.run_shortage_scan()[0]) == 1 and mr.calls["fm"] == 2

    def test_refresh_during_l1_backoff_refetches(self, sv, mr):
        """修前：refresh 清掉被快取的失敗並重抓；現在失敗在 L1 退避裡 —— refresh（`.clear()` 兩層）同樣立刻重抓。"""
        SVC.run_shortage_scan()
        mr.fm = "ok"
        rows, meta = SVC.run_shortage_scan(refresh=True)
        assert len(rows) == 1 and meta["note"] == ""
        assert mr.calls["fm"] == 2

    def test_parallel_calls_during_failure(self, sv, mr):
        n_threads = 6
        barrier = threading.Barrier(n_threads)
        results, errors = [], []

        def _worker():
            try:
                barrier.wait(timeout=5)
                results.append(SVC.run_shortage_scan())
            except Exception as e:  # noqa: BLE001 — 收集起來讓斷言報出來
                errors.append(e)

        threads = [threading.Thread(target=_worker, daemon=True) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        assert not any(t.is_alive() for t in threads), "不得死鎖"
        assert errors == [] and len(results) == n_threads
        assert all(r == [] and m["note"] == _FAIL_NOTE for r, m in results)
        assert 1 <= mr.calls["twse"] <= n_threads
        n = dict(mr.calls)
        SVC.run_shortage_scan()
        assert mr.calls == n, "並行失敗之後：L1 冷卻期內不再重打"

    def test_exception_class_is_private_subclass(self):
        assert issubclass(SVC._CandidatePoolFetchFailed, FC.CachedFailure)
        assert SVC._CandidatePoolFetchFailed is not FC.CachedFailure
        assert issubclass(MR._BatchRevenueFetchFailed, FC.CachedFailure)
        assert not issubclass(MR._BatchRevenueFetchFailed, SVC._CandidatePoolFetchFailed), \
            "L1 的失敗例外萬一漏出來，L3 不會把它當成 (rows, meta) 拆開"


# ══════════════════════════════════════════════════════════════════
# ① 其餘結果照舊快取（L1 沒有確定失敗的空表／存活池路徑／成功）
# ══════════════════════════════════════════════════════════════════
class TestD2f5ScanStillCached:
    def test_l1_ambiguous_empty_still_cached(self, sv, mr, fc_clock):
        _plan, side = sv
        _check_l3_ambiguous_still_cached(SVC, mr, side, fc_clock)

    def test_plain_batch_function_without_status_treated_as_not_failed(self, sv, monkeypatch, fc_clock):
        """相容：`fetch_batch_monthly_revenue` 被換成純函式（沒有 `.with_status`）→ 照修前呼叫、照舊快取。"""
        _plan, side = sv
        n = {"batch": 0}

        def _plain(months=18):
            n["batch"] += 1
            return pd.DataFrame()
        monkeypatch.setattr(SVC, "fetch_batch_monthly_revenue", _plain)
        first = SVC.run_shortage_scan()
        assert first[1]["note"] == _FAIL_NOTE
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
        assert SVC.run_shortage_scan() == first
        assert n["batch"] == 1 and side["pool"] == 1

    @pytest.mark.parametrize("pool,qtr,note_has", [
        (["1234", "5678"], "empty", "資料不足 2 檔"),       # 存活池路徑：季報全 0 季（L1 回 []，分不出失敗）
        (["1001"], "strong", None),                          # 存活池路徑：成功
    ], ids=["survivor_all_insufficient", "survivor_success"])
    def test_survivor_path_still_cached(self, sv, fc_clock, pool, qtr, note_has):
        plan, side = sv
        plan["pool"], plan["qtr"] = pool, qtr
        first = SVC.run_shortage_scan()
        if note_has is None:
            assert first[0] and first[1]["note"] == ""
        else:
            assert first[0] == [] and note_has in first[1]["note"]
        s1 = dict(side)
        plan["qtr"] = "strong"
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
        assert SVC.run_shortage_scan() == first
        assert side == s1, "照舊入 1 天快取（第 ① 條路本次未動）"

    def test_batch_success_still_cached(self, sv, mr, fc_clock):
        _plan, side = sv
        mr.fm = "ok"
        first = SVC.run_shortage_scan()
        assert len(first[0]) == 1
        n1, s1 = dict(mr.calls), dict(side)
        mr.fm = "empty"
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
        assert SVC.run_shortage_scan() == first
        assert mr.calls == n1 and side == s1

    def test_scan_cache_decorator_unchanged(self):
        tree = ast.parse(pathlib.Path(SVC.__file__).read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_scan_cached")
        assert [ast.unparse(d) for d in fn.decorator_list] == ["st.cache_data(ttl=TTL_1DAY, show_spinner=False)"]


# ══════════════════════════════════════════════════════════════════
# ③ L1 季報（不改）：前提守衛 —— 這一層看不到「確定失敗」
# ══════════════════════════════════════════════════════════════════
def _fake_requests_get(kind: str):
    def _get(*_a, **_k):
        if kind == "conn":
            raise requests.exceptions.ConnectionError("boom")
        if kind == "timeout":
            raise requests.exceptions.Timeout("slow")
        if kind == "quota_402":
            return _Resp({"status": 402, "msg": "Requests reach the upper limit."}, status=402)
        if kind == "html_500":
            return _Resp(None, status=500, exc=ValueError("Expecting value"))
        if kind == "json_list":
            return _Resp([1, 2, 3])
        raise AssertionError(kind)
    return _get


_FM_FAILURE_KINDS = ["conn", "timeout", "quota_402", "html_500", "json_list"]


def _check_finmind_get_never_raises(mod, kind: str, monkeypatch) -> None:
    monkeypatch.setattr(requests, "get", _fake_requests_get(kind))
    try:
        out = mod.finmind_get("TaiwanStockBalanceSheet", data_id="2330", start_date="2023-01-01",
                              token="t", timeout=1)
    except Exception as e:  # noqa: BLE001 — 轉成斷言失敗（前提被推翻）
        raise AssertionError(f"前提被推翻：finmind_get 對「{kind}」拋了 {type(e).__name__}") from e
    assert isinstance(out, pd.DataFrame) and out.empty, "前提：失敗一律回空表（與真的沒資料同形）"


class TestD2f5QuarterlyPremise:
    """第 ③ 處不改的依據（前提守衛）：`finmind_get` 從不拋例外 ⇒ `fetch_quarterly_shortage_frame` 只看得到
    空表 ⇒ 依判準（沒拋、只回空 ＝ 分不出失敗與真的沒資料）照舊快取。前提一旦被推翻，本類別轉紅。"""

    @pytest.mark.parametrize("kind", _FM_FAILURE_KINDS)
    def test_premise_finmind_get_never_raises(self, monkeypatch, kind):
        _check_finmind_get_never_raises(FMC, kind, monkeypatch)

    def test_quarterly_frame_sees_only_empty_and_caches_it(self, monkeypatch, fc_clock):
        monkeypatch.setenv("FINMIND_TOKEN", "dummy-token")
        n = {"get": 0}

        def _down(*_a, **_k):
            n["get"] += 1
            raise requests.exceptions.ConnectionError("FinMind down")
        monkeypatch.setattr(requests, "get", _down)
        QF.fetch_quarterly_shortage_frame.clear()
        try:
            assert QF.fetch_quarterly_shortage_frame("2330") == [], "不拋、回 [] —— 與「這檔沒有季報」同形"
            assert n["get"] == 3, "損益表兩種 dataset 名 ＋ 資產負債表，各打 1 次"

            def _up(*_a, **_k):
                n["get"] += 1
                return _Resp({"status": 200, "data": [
                    {"date": "2025-03-31", "type": "Revenue", "origin_name": "營業收入合計", "value": 1000}]})
            monkeypatch.setattr(requests, "get", _up)
            fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
            assert QF.fetch_quarterly_shortage_frame("2330") == [] and n["get"] == 3, \
                "照舊快取（本層分不出失敗；本次不改）"
        finally:
            QF.fetch_quarterly_shortage_frame.clear()
        tree = ast.parse(pathlib.Path(QF.__file__).read_text(encoding="utf-8"))
        fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "fetch_quarterly_shortage_frame")
        assert [ast.unparse(d) for d in fn.decorator_list] == ["st.cache_data(ttl=TTL_1DAY, show_spinner=False)"]


# ══════════════════════════════════════════════════════════════════
# 遞增退避評估：全失敗 1 小時、每 60 秒 rerun —— 固定冷卻 vs 遞增 vs 修前
# ══════════════════════════════════════════════════════════════════
_STEP = 60
_HORIZON = TTL_1HOUR


def _drive_hour(svc_mod, w: _MrWorld, side: dict, clock: dict) -> dict:
    """照 #741 QA N1 情境呼叫 `run_shortage_scan`；回傳真的打到 L1 上游的時點與各項呼叫數。"""
    hits, t0 = [], clock["now"]
    for t in range(0, _HORIZON + 1, _STEP):
        clock["now"] = t0 + t
        before = sum(w.calls.values())
        rows, meta = svc_mod.run_shortage_scan()
        assert rows == [] and meta["note"] == _FAIL_NOTE
        if sum(w.calls.values()) > before:
            hits.append(t)
    return {"hits": hits, "finmind": w.calls["fm"], "fetch_url": w.calls["twse"] + w.calls["tpex"],
            "deep_scan": side["qtr"] + side["mrev"], "survivor_pool": side["pool"]}


def _expected_hits(base: float, cap: float) -> list[int]:
    """獨立參考模型：每次重打都失敗 → 下次最早 t＋w，w 每次加倍到 cap（base＝cap 即固定冷卻）。"""
    times, next_at, w = [], 0, base
    for t in range(0, _HORIZON + 1, _STEP):
        if t >= next_at:
            times.append(t)
            next_at, w = t + w, min(w * 2, cap)
    return times


class TestD2f5LoadFixedVsEscalating:
    """D3e（D2-f25）：原類別名 `TestD2f5LoadNoEscalation` —— 當時現行是固定冷卻、遞增只是對照組。批 D3e 起現行
    改為遞增（正是本測試原本的「對照一」設定），故兩組對調：現行 ＝ 遞增；固定冷卻改由突變體（換回 D2-f5 的
    `_FailCooldown()`）重現。三組期望值一字未改。"""

    def test_hour_of_reruns_fixed_vs_escalating_vs_prefix(self, sv, mr, fc_clock, monkeypatch):
        plan, side = sv
        out = {"escalating": _drive_hour(SVC, mr, side, fc_clock)}

        # 對照一：D2-f5 時的固定冷卻（D3e 前的現行設定）
        fixed = _mutant(MR, ("_batch_fail_cooldown = _FailCooldown(max_seconds=TTL_1HOUR)",
                             "_batch_fail_cooldown = _FailCooldown()"), tag="fixed")
        w2, side2 = _MrWorld(), {"pool": 0, "qtr": 0, "mrev": 0}
        monkeypatch.setattr(PH, "fetch_url", w2.fetch_url)
        _install_mr(fixed, monkeypatch, w2)
        _install_svc(SVC, monkeypatch, plan, side2)
        monkeypatch.setattr(SVC, "fetch_batch_monthly_revenue", fixed.fetch_batch_monthly_revenue)
        fc_clock["now"] += 10 * _HORIZON
        try:
            out["fixed"] = _drive_hour(SVC, w2, side2, fc_clock)
        finally:
            SVC._scan_cached.clear()
            fixed.fetch_batch_monthly_revenue.clear()

        # 對照二：修前（L1 凍 6 小時、L3 凍 1 天）
        pre_mr, pre_svc = _prefix_mr("load"), _prefix_svc("load")
        w3, side3 = _MrWorld(), {"pool": 0, "qtr": 0, "mrev": 0}
        monkeypatch.setattr(PH, "fetch_url", w3.fetch_url)
        pre_mr.finmind_get = w3.finmind_get
        pre_mr.fetch_batch_monthly_revenue.clear()
        _install_svc(pre_svc, monkeypatch, plan, side3)
        monkeypatch.setattr(pre_svc, "fetch_batch_monthly_revenue", pre_mr.fetch_batch_monthly_revenue)
        fc_clock["now"] += 10 * _HORIZON
        try:
            out["prefix"] = _drive_hour(pre_svc, w3, side3, fc_clock)
        finally:
            pre_svc._scan_cached.clear()
            pre_mr.fetch_batch_monthly_revenue.clear()

        assert out["fixed"] == {"hits": _expected_hits(FAIL_COOLDOWN_SEC, FAIL_COOLDOWN_SEC),
                                "finmind": 21, "fetch_url": 42, "deep_scan": 0, "survivor_pool": 61}
        assert len(out["fixed"]["hits"]) == 21
        assert out["escalating"] == {"hits": _expected_hits(FAIL_COOLDOWN_SEC, TTL_1HOUR),
                                     "finmind": 5, "fetch_url": 10, "deep_scan": 0, "survivor_pool": 61}
        assert out["escalating"]["hits"] == [0, 180, 540, 1260, 2700]
        assert out["prefix"] == {"hits": [0], "finmind": 1, "fetch_url": 2, "deep_scan": 0, "survivor_pool": 1}


# ══════════════════════════════════════════════════════════════════
# 修前 bug 重現：修前模型跑同一組檢查 → 轉紅（快取了失敗）
# ══════════════════════════════════════════════════════════════════
class TestPrefixReproducesBug:
    def test_l1_prefix_caches_failure(self, mr, fc_clock):
        pre = _prefix_mr("bug_l1")
        pre.finmind_get = mr.finmind_get
        try:
            with pytest.raises(AssertionError, match="冷卻期過"):
                _check_l1_failure_backs_off_then_recovers(pre, mr, fc_clock)
            assert mr.calls == {"fm": 1, "twse": 1, "tpex": 1}, "修前：恢復＋過冷卻期仍 0 次上游（空表凍 6 小時）"
        finally:
            pre.fetch_batch_monthly_revenue.clear()

    def test_l3_prefix_caches_failure_even_after_l1_recovers(self, sv, mr, fc_clock, monkeypatch):
        pre_svc = _prefix_svc("bug_l3")
        plan2, side2 = {"pool": [], "qtr": "strong"}, {"pool": 0, "qtr": 0, "mrev": 0}
        _install_svc(pre_svc, monkeypatch, plan2, side2)
        try:
            with pytest.raises(AssertionError, match="L3 沒有快取這一份"):
                _check_l3_failure_not_cached_then_recovers(pre_svc, mr, side2, fc_clock)
            assert side2["pool"] == 1, "修前：L3 把「兩個候選池來源都取不到」凍 1 天，後續呼叫連存活池都不再問"
        finally:
            pre_svc._scan_cached.clear()


# ══════════════════════════════════════════════════════════════════
# 突變：每一個突變體都讓本檔對應的共用檢查轉紅
# ══════════════════════════════════════════════════════════════════
_L1_NONE_APPEND = ("                if failed is not None:   # D2-f5:確定抓取失敗\n"
                   "                    failed.append(f\"{_mkt}: status={getattr(_r, 'status_code', None)}\")\n")


def _l1_mutant_world(tag, monkeypatch, *pairs):
    m = _mutant(MR, *pairs, tag=tag)
    w = _MrWorld()
    monkeypatch.setattr(PH, "fetch_url", w.fetch_url)
    _install_mr(m, monkeypatch, w)
    return m, w


class TestMutations:
    # ── 第 ② 處（L1 全市場月營收）──
    def test_m1_l1_failure_cached_again(self, monkeypatch, fc_clock, mr):
        """M1：快取層不拋、照舊回空表（修前結構）→ 失敗被凍 6 小時。"""
        m, w = _l1_mutant_world("m1", monkeypatch, ('        raise _BatchRevenueFetchFailed(_out, "；".join(_failed))',
                                                    "        return _out"))
        try:
            with pytest.raises(AssertionError, match="冷卻期過"):
                _check_l1_failure_backs_off_then_recovers(m, w, fc_clock)
        finally:
            m.fetch_batch_monthly_revenue.clear()

    def test_m2_l1_no_backoff(self, monkeypatch, fc_clock, mr):
        """M2：不入快取但不記退避 → 冷卻期內每呼叫一次就重打一次（轟炸）。"""
        m, w = _l1_mutant_world("m2", monkeypatch, ("        return _batch_fail_cooldown.fail(months, _gen, _bf.payload), True",
                                                    "        return _bf.payload, True"))
        try:
            with pytest.raises(AssertionError, match="冷卻期內 0 次上游呼叫"):
                _check_l1_failure_backs_off_then_recovers(m, w, fc_clock)
        finally:
            m.fetch_batch_monthly_revenue.clear()

    def test_m3_l1_wrong_cooldown_key(self, monkeypatch, fc_clock, mr):
        """M3：冷卻鍵錯（所有 months 共用一格）→ 別的 months 被連坐。"""
        m, w = _l1_mutant_world("m3", monkeypatch,
                                ("_hit, _gen = _batch_fail_cooldown.begin(months)", '_hit, _gen = _batch_fail_cooldown.begin("batch")'),
                                ("_batch_fail_cooldown.fail(months, _gen,", '_batch_fail_cooldown.fail("batch", _gen,'),
                                ("    _batch_fail_cooldown.success(months)\n", '    _batch_fail_cooldown.success("batch")\n'))
        try:
            with pytest.raises(AssertionError):
                _check_l1_cooldown_is_per_months(m, w, fc_clock)
        finally:
            m.fetch_batch_monthly_revenue.clear()

    def test_m4_l1_classification_too_broad(self, monkeypatch, fc_clock, mr):
        """M4：判準放寬成「空就算失敗」→ 分不出失敗的空表也不快取、每個冷卻期被重打。
        （D3e：D2-f23 起判準本體改為 `if _failed:`，突變點隨之改為在其上加「或空」。）"""
        m, w = _l1_mutant_world("m4", monkeypatch, ("    if _failed:   # D2-f23", "    if _failed or _out.empty:   # D2-f23"))
        w.twse = w.tpex = "empty200"
        try:
            with pytest.raises(AssertionError, match="照舊入 6 小時快取"):
                _check_l1_ambiguous_still_cached(m, w, fc_clock)
        finally:
            m.fetch_batch_monthly_revenue.clear()

    def test_m5_l1_clear_keeps_backoff(self, monkeypatch, fc_clock, mr):
        """M5：`.clear()` 沒清退避 → refresh 在冷卻期內不重打（refresh 行為被改變）。"""
        m, w = _l1_mutant_world("m5", monkeypatch, ("    _batch_fail_cooldown.clear()\n", "    pass\n"))
        try:
            with pytest.raises(AssertionError, match="清掉退避紀錄"):
                _check_l1_clear_resets_both(m, w, fc_clock)
        finally:
            m._batch_fail_cooldown.clear()
            m.fetch_batch_monthly_revenue.clear()

    def test_m6_l1_openapi_none_not_recorded(self, monkeypatch, fc_clock, mr):
        """M6：OpenAPI「fetch_url 回 None」那一邊不記成確定失敗 → 這種失敗又被快取。"""
        m, w = _l1_mutant_world("m6", monkeypatch, (_L1_NONE_APPEND, ""))
        try:
            with pytest.raises(AssertionError, match="冷卻期過"):
                _check_l1_failure_backs_off_then_recovers(m, w, fc_clock)
        finally:
            m.fetch_batch_monthly_revenue.clear()

    def test_m7_l1_success_does_not_bump_generation(self, monkeypatch, fc_clock, mr):
        """M7：成功不推進世代 → 並行時同儕晚到的失敗蓋掉剛發生的成功。"""
        m, w = _l1_mutant_world("m7", monkeypatch, ("    _batch_fail_cooldown.success(months)\n", ""))
        try:
            with pytest.raises(AssertionError):
                _check_l1_success_bumps_generation(m, w, fc_clock)
        finally:
            m.fetch_batch_monthly_revenue.clear()

    # ── 第 ① 處（L3 缺貨掃描）──
    def _l3_mutant(self, tag, monkeypatch, *pairs):
        m = _mutant(SVC, *pairs, tag=tag)
        plan, side = {"pool": [], "qtr": "strong"}, {"pool": 0, "qtr": 0, "mrev": 0}
        _install_svc(m, monkeypatch, plan, side)
        return m, side

    def test_m8_l3_failure_cached_again(self, monkeypatch, fc_clock, mr):
        """M8：② 改回 return（修前）→ 「兩個候選池來源都取不到」凍 1 天，L1 恢復也看不到。"""
        m, side = self._l3_mutant("m8", monkeypatch, ("            raise _CandidatePoolFetchFailed(_empty)",
                                                      "            return _empty"))
        try:
            with pytest.raises(AssertionError, match="L3 沒有快取這一份"):
                _check_l3_failure_not_cached_then_recovers(m, mr, side, fc_clock)
        finally:
            m._scan_cached.clear()

    def test_m9_l3_ignores_l1_status(self, monkeypatch, fc_clock, mr):
        """M9：L3 不取 L1 的失敗判定（一律當非失敗）→ 同 M8 的失效。"""
        m, side = self._l3_mutant("m9", monkeypatch, ('    _with_status = getattr(fetch_batch_monthly_revenue, "with_status", None)',
                                                      "    _with_status = None"))
        try:
            with pytest.raises(AssertionError, match="L3 沒有快取這一份"):
                _check_l3_failure_not_cached_then_recovers(m, mr, side, fc_clock)
        finally:
            m._scan_cached.clear()

    def test_m10_l3_classification_too_broad(self, monkeypatch, fc_clock, mr):
        """M10：② 不看 L1 判定、一律不入快取 → 分不出失敗的空表每次都重算（違反「不猜、照舊快取」）。"""
        m, side = self._l3_mutant("m10", monkeypatch, ("        if _batch_failed:\n", "        if True:\n"))
        try:
            with pytest.raises(AssertionError, match="照舊入 1 天快取"):
                _check_l3_ambiguous_still_cached(m, mr, side, fc_clock)
        finally:
            m._scan_cached.clear()

    # ── 第 ③ 處（不改；突變的是它依據的前提 `finmind_get`）──
    def test_m11_premise_finmind_get_reraises(self, monkeypatch):
        """M11：`finmind_get` 最後一次嘗試改成往上拋 → 前提守衛轉紅（屆時第 ③ 處要重新評估）。"""
        m = _mutant(FMC, ("            if _i == _attempts - 1:\n                return pd.DataFrame()\n",
                          "            if _i == _attempts - 1:\n                raise\n"), tag="m11")
        with pytest.raises(AssertionError, match="前提被推翻"):
            _check_finmind_get_never_raises(m, "conn", monkeypatch)

    def test_m12_premise_finmind_get_except_narrowed(self, monkeypatch):
        """M12：`finmind_get` 的 except 收窄（不接連線／逾時錯誤）→ 前提守衛轉紅。"""
        m = _mutant(FMC, ("        except Exception as _e:\n            print(f\"[FinMind] {dataset} attempt",
                          "        except KeyError as _e:\n            print(f\"[FinMind] {dataset} attempt"), tag="m12")
        with pytest.raises(AssertionError, match="前提被推翻"):
            _check_finmind_get_never_raises(m, "timeout", monkeypatch)
