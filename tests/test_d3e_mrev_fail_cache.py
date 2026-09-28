# -*- coding: utf-8 -*-
"""批 D3e（2026-09-28）：月營收抓取鏈的失敗快取（CLAUDE.md §1.A-3「只快取成功結果；失敗時退避，不連續轟炸來源」）。

五列（第四輪分類 A／B 兩組皆判「可自主」；照 #744〔D2-f5〕與 #741〔`max_seconds` 遞增退避〕同一手法）：

  · **D2-f22（主情形）** L1 單股 `monthly_revenue_fetcher.fetch_monthly_revenue`（`TTL_6HOUR`）——
    FinMind 無資料後改走 TWSE／TPEx OpenAPI，修前呼叫時不傳 `failed`：OpenAPI 確定抓取失敗（或該股所在的
    那一邊失敗）時回的空表照樣被快取 6 小時。現在比照 D2-f5 拆層：快取層 `_fetch_monthly_revenue_cached`
    在「這一檔沒拿到 **且** OpenAPI 有市場確定失敗」時拋私有 `_SingleRevenueFetchFailed`（不入快取），外層
    `fetch_monthly_revenue` 接住、記 `FailCooldown`（鍵 (stock_id, months)；遞增、上限 `TTL_1HOUR`）。
    **變形不在本批**（FinMind 掛掉、OpenAPI 正常 → 降級 1 列照舊快取；等 D2-f24 的 FinMind 狀態入口），
    本檔把它釘成「照舊」。
  · **D2-f23** 半邊失敗：上市／上櫃一邊確定失敗、另一邊有資料時，修前 L1 `fetch_batch_monthly_revenue`
    （6 小時）與 L3 `shortage_screener_service._scan_cached`（1 天）都照舊快取。現在 L1 快取層只要有市場
    確定失敗就拋（不論空不空），L3 ② 拿到 L1 判定失敗的半邊表也改拋 `_CandidatePoolFetchFailed`；
    對呼叫端的回傳逐字同修前。
  · **D2-f21** L1 `_batch_finmind` 的 schema 樣本：修前取「排序後前 36 列」，兩檔以上時樣本跨檔、date 不單調
    → 整批恆被丟棄。改為只取首檔的前 36 列（schema 本身不動）。依交接本 D2-f21 列的總管實查，production
    目前在方案層就被 FinMind 拒絕（HTTP 400「Your level is register」→ batch 回空），只能用合成資料測。
  · **D2-f25** L1 `_batch_fail_cooldown` 固定 180 秒 → 遞增（起點 `FAIL_COOLDOWN_SEC`、上限 `TTL_1HOUR`；
    比照 RS 掃描層與 #744 測試已建模的遞增對照；不新增常數）。單股新加的冷卻用同一組設定。
  · **D2-f26**（只補測試）`run_shortage_scan` 只接 `_CandidatePoolFetchFailed`、不接 `CachedFailure` ——
    突變「放寬成接 `CachedFailure`」必須轉紅。L1 兩處同型的 `except` 一併守住。

「修前」＝ origin/main `b2dafba`：把本次改動的區段換回 b2dafba 原文（逐字常數）的同一份模組（修前模型，
`_prefix_mr`／`_prefix_svc`；去掉 docstring 後與 b2dafba 的 AST 逐節點相同，唯多一個沒用到的 `TTL_1HOUR` import）。
D2-f21／f22／f23／f25 都先以修前模型跑同一個共用檢查、證明修前會錯（`TestPrefixReproducesBug`），再以現行跑同一個
檢查、證明修後正確；D2-f26 只補測試，以突變（`TestMutations.test_m14_*`）證明新測試抓得到。
不觸網：一律換掉 `finmind_get`／`proxy_helper.fetch_url`／存活池／逐檔季報／涵蓋率。
冷卻期用假時鐘：**只換 `shared.fail_cooldown` 的 `time`**（`st.cache_data` 的 TTL 不受影響，故「把假時鐘
推過冷卻期仍不重打」＝ 真的在快取裡，不是在退避裡）。
突變（`TestMutations`）：逐一拿掉每一處修正，對應的共用檢查（`_check_*`）必須轉紅。
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import pathlib
import sqlite3
import sys
import threading
import time
import types

import pandas as pd
import pytest

import shared.fail_cooldown as FC
import src.data.proxy.proxy_helper as PH
import src.data.stock.monthly_revenue_fetcher as MR
import src.services.fundamental_screener_service as FSS
import src.services.shortage_screener_service as SVC
from shared.fail_cooldown import FAIL_COOLDOWN_SEC
from shared.schemas import PANDERA_AVAILABLE
from shared.ttls import TTL_1HOUR, TTL_6HOUR

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_NEEDS_PANDERA = pytest.mark.skipif(not PANDERA_AVAILABLE,
                                    reason="D2-f21 的「修前整批被丟棄」要 pandera 才會發生（CI 有裝）")


# ══════════════════════════════════════════════════════════════════
# 模組重建：修前模型 ／ 突變體（真模組不動）
# ══════════════════════════════════════════════════════════════════
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


def _replace_once(src: str, old: str, new: str) -> str:
    assert src.count(old) == 1, f"替換點不唯一或已不存在：{old!r}"
    return src.replace(old, new)


def _replace_region(src: str, start: str, end: str, new: str) -> str:
    """把 `start`（含）到 `end`（含）之間換成 `new`；兩個錨點都必須唯一。"""
    assert src.count(start) == 1, f"錨點不唯一或已不存在：{start!r}"
    a = src.index(start)
    b = src.index(end, a)
    assert src.count(end, a) >= 1
    return src[:a] + new + src[b + len(end):]


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str], tag: str) -> types.ModuleType:
    """原始碼字面替換後另建一份模組（同 #741／#744）。`tag` 讓每個突變體有自己的模組名 ——
    `st.cache_data` 以「模組名＋函式名＋原始碼」當快取鍵。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        src = _replace_once(src, old, new)
    return _load(src, f"_mutant_d3e_{tag}_{mod.__name__.rsplit('.', 1)[-1]}", mod.__file__)


#: b2dafba `monthly_revenue_fetcher.fetch_monthly_revenue`（逐字；直接掛 st.cache_data、OpenAPI 備援不傳 failed）。
_B2_SINGLE = '''@st.cache_data(ttl=TTL_6HOUR, show_spinner=False)
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

#: b2dafba `_batch_finmind` 的 schema 樣本那一句（逐字）。
_B2_SAMPLE = ("            _sample_v = validate_or_reject(_result_b.head(36), MonthlyRevenueSchema,\n"
              "                                           label='fetch_batch_monthly_revenue:sample')\n")
#: b2dafba 全市場快取層的判準（逐字）。
_B2_BATCH_COND = "    if _out.empty and _failed:\n"
#: b2dafba 全市場冷卻表（逐字；固定冷卻）。
_B2_BATCH_COOLDOWN = "_batch_fail_cooldown = _FailCooldown()\n"
#: b2dafba 全市場失敗 log（逐字）。
_B2_BATCH_LOG = ('        print(f"[mrev-fetcher] batch 全源無資料且 OpenAPI 確定抓取失敗({_bf})→ 不入快取,"\n'
                 '              f"{_batch_fail_cooldown.seconds:.0f}s 內不重打上游")\n')
#: b2dafba `shortage_screener_service._scan_cached` ② 的尾段（逐字）。
_B2_SCAN_TAIL = '''    return _rows, {
        "candidates": len(_pool), "deep_scanned": len(_pairs), "scored": len(_rows),
        "pool_source": "全市場月營收動能候選池（sponsor tier）",
        "note": _note,
        "source": "FinMind:MonthRevenue(batch)+FS+BS",
        "fetched_at": _fetched_at, "version": SHORTAGE_VERSION}
'''


def _prefix_mr(tag: str) -> types.ModuleType:
    """修前模型：b2dafba 的 `monthly_revenue_fetcher`（本次改動的區段換回原文逐字常數；其餘沿用現行檔）。"""
    src = pathlib.Path(MR.__file__).read_text(encoding="utf-8")
    src = _replace_region(src, "            _sample = _result_b.head(36)\n",
                          "label='fetch_batch_monthly_revenue:sample')\n", _B2_SAMPLE)          # D2-f21
    src = _replace_region(src, "def _cooldown_note(", "fetch_monthly_revenue.clear = _clear_fetch_monthly_revenue\n",
                          _B2_SINGLE.rstrip("\n") + "\n")                                     # D2-f22
    src = _replace_region(src, "    if _failed:   # D2-f23", "\n", _B2_BATCH_COND)             # D2-f23（L1）
    src = _replace_region(src, "_batch_fail_cooldown = _FailCooldown(max_seconds=TTL_1HOUR)", "\n",
                          _B2_BATCH_COOLDOWN)                                                  # D2-f25
    src = _replace_region(src, '        print(f"[mrev-fetcher] batch {',
                          '{_cooldown_note(_batch_fail_cooldown)}")\n', _B2_BATCH_LOG)       # log
    return _load(src, f"_prefix_d3e_{tag}_monthly_revenue_fetcher", MR.__file__)


def _prefix_svc(tag: str) -> types.ModuleType:
    """修前模型：b2dafba 的 `shortage_screener_service`（② 尾段換回原文）。"""
    src = pathlib.Path(SVC.__file__).read_text(encoding="utf-8")
    src = _replace_region(src, "    _result = (_rows, {\n", "    return _result\n", _B2_SCAN_TAIL)  # D2-f23（L3）
    return _load(src, f"_prefix_d3e_{tag}_shortage_screener_service", SVC.__file__)


# ══════════════════════════════════════════════════════════════════
# 上游替身、假時鐘、期望值
# ══════════════════════════════════════════════════════════════════
_COVERAGE = "（涵蓋率替身）"
#: OpenAPI 快照（民國 115 年 8 月 ＝ 2026-08-01）：上市 2317、2330；上櫃 6488。
_TWSE_ROWS = [{"公司代號": "2330", "公司名稱": "台積電", "資料年月": "11508", "營業收入-當月營收": "263,714,000"},
              {"公司代號": "2317", "公司名稱": "鴻海", "資料年月": "11508", "營業收入-當月營收": "500,000"}]
_TPEX_ROWS = [{"公司代號": "6488", "公司名稱": "環球晶", "資料年月": "11508", "營業收入-當月營收": "1,000"}]
#: 獨立寫出的「千元 × 1000 ＝ 元」期望值。
_OPENAPI_YUAN = {"2330": 263_714_000.0 * 1000, "2317": 500_000.0 * 1000, "6488": 1_000.0 * 1000}


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


def _fm_single_frame(sid: str, n: int = 19) -> pd.DataFrame:
    """FinMind 單股月營收成功回應（n 個月、逐月成長 → 算得出年增率）。"""
    dates = pd.date_range("2025-02-01", periods=n, freq="MS")
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "stock_id": [sid] * n,
                         "revenue": [float(1000 + i * 80) for i in range(n)],
                         "revenue_month": list(dates.month), "revenue_year": list(dates.year)})


def _fm_batch_frame(sids: list[str], n: int = 19, *, bad: tuple[str, int] | None = None) -> pd.DataFrame:
    """FinMind 全市場月營收成功回應（多檔長表、每檔 n 個月、逐月成長）；`bad=(股號, 第幾列)` 把該列營收改成負數。"""
    dates = pd.date_range("2025-02-01", periods=n, freq="MS")
    frames = []
    for k, sid in enumerate(sids):
        rev = [float(1000 + k + i * 80) for i in range(n)]
        if bad is not None and bad[0] == sid:
            rev[bad[1]] = -5.0
        frames.append(pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "stock_id": [sid] * n, "revenue": rev,
                                    "revenue_month": list(dates.month), "revenue_year": list(dates.year)}))
    return pd.concat(frames, ignore_index=True)


class _World:
    """上游替身：FinMind（`finmind_get`：帶 data_id ＝ 單股、不帶 ＝ 全市場）＋ OpenAPI（`proxy_helper.fetch_url`）。

    `fm_single`：empty（回空表 —— 失敗或真的沒有，這一層分不出來）／ok。
    `fm_batch`：empty／ok（1 檔 1001）／("multi", n)／一張 DataFrame（原樣回傳）。
    `twse`／`tpex`：ok／none（`fetch_url` 回 None）／non200／json_err（回應不是 JSON）／raise（抓取拋例外）／
    empty200（200 但 0 筆）。`delay`：每打一次 OpenAPI 就把假時鐘往前推幾秒（D2-f25：上游只收連線、不回應）。
    """

    def __init__(self, clock: dict):
        self.clock = clock
        self.fm_single, self.fm_batch = "empty", "empty"
        self.twse, self.tpex = "none", "none"
        self.delay = 0.0
        self.calls = {"fm_single": 0, "fm_batch": 0, "twse": 0, "tpex": 0}
        self._lock = threading.Lock()

    def _bump(self, k):
        with self._lock:
            self.calls[k] += 1

    def recover(self):
        self.twse = self.tpex = "ok"

    def finmind_get(self, dataset, data_id=None, **_kw):
        assert dataset == "TaiwanStockMonthRevenue"
        if data_id is not None:
            self._bump("fm_single")
            return _fm_single_frame(str(data_id)) if self.fm_single == "ok" else pd.DataFrame()
        self._bump("fm_batch")
        spec = self.fm_batch
        if isinstance(spec, pd.DataFrame):
            return spec.copy()
        if spec == "ok":
            return _fm_batch_frame(["1001"])
        if isinstance(spec, tuple) and spec[0] == "multi":
            return _fm_batch_frame([str(1001 + i) for i in range(spec[1])])
        return pd.DataFrame()

    def fetch_url(self, url, headers=None, params=None, timeout=20, attempts=3):
        side = "twse" if "openapi.twse.com.tw" in url else "tpex"
        self._bump(side)
        if self.delay:
            self.clock["now"] += self.delay
        mode = getattr(self, side)
        if mode == "ok":
            return _Resp([dict(r) for r in (_TWSE_ROWS if side == "twse" else _TPEX_ROWS)])
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
        raise AssertionError(mode)

    def upstream(self) -> int:
        return sum(self.calls.values())


@pytest.fixture
def fc_clock(monkeypatch):
    """可手動推進的假 monotonic 時鐘 —— **只**換 `shared.fail_cooldown` 模組裡的 `time`（同 #741／#744）。"""
    t = {"now": float(int(time.monotonic()))}
    monkeypatch.setattr(FC, "time", types.SimpleNamespace(monotonic=lambda: t["now"]))
    return t


@pytest.fixture
def frozen_now(monkeypatch):
    """`fetched_at` 取 `pd.Timestamp.now("UTC")` —— 凍結後才能與修前模型逐字比。"""
    fixed = pd.Timestamp("2026-09-28T01:02:03.456789", tz="UTC")
    monkeypatch.setattr(pd.Timestamp, "now", classmethod(lambda cls, tz=None: fixed))
    return fixed


def _install_mr(mod, monkeypatch, w: _World) -> None:
    monkeypatch.setattr(mod, "finmind_get", w.finmind_get)
    mod.fetch_monthly_revenue.clear()
    mod.fetch_batch_monthly_revenue.clear()


@pytest.fixture
def world(monkeypatch, fc_clock):
    """換掉 L1 月營收的上游；預設 FinMind 單股／全市場都回空、OpenAPI 兩邊 `fetch_url` 回 None。"""
    w = _World(fc_clock)
    monkeypatch.setenv("FINMIND_TOKEN", "dummy-token")
    monkeypatch.delenv("FM_TOKEN", raising=False)
    # 同 tests/test_monthly_revenue_twse_fallback.py：patch 真正持有者 proxy_helper，不 patch package。
    monkeypatch.setattr(PH, "fetch_url", w.fetch_url)
    _install_mr(MR, monkeypatch, w)
    yield w
    MR.fetch_monthly_revenue.clear()
    MR.fetch_batch_monthly_revenue.clear()


def _with_prefix_mr(tag, monkeypatch, w):
    pre = _prefix_mr(tag)
    _install_mr(pre, monkeypatch, w)
    return pre


def _assert_empty_frame(df) -> None:
    """修前失敗時回的是 `return pd.DataFrame()` —— 逐字比（無欄、無 attrs）。"""
    ref = pd.DataFrame()
    assert isinstance(df, pd.DataFrame)
    assert repr(df) == repr(ref) and df.attrs == {}
    pd.testing.assert_frame_equal(df, ref)


def _assert_single_openapi_row(df, sid: str) -> None:
    """OpenAPI 單股備援的 1 列（獨立寫出：2026-08、千元 ×1000 ＝ 元）。"""
    assert isinstance(df, pd.DataFrame) and not df.empty, "應拿到上游恢復後的新值，卻是空表"
    assert list(df.columns) == ["date", "revenue", "revenue_year", "revenue_month"]
    assert len(df) == 1 and df["revenue"].iloc[0] == _OPENAPI_YUAN[sid]
    assert df["date"].iloc[0] == pd.Timestamp("2026-08-01")
    assert (int(df["revenue_year"].iloc[0]), int(df["revenue_month"].iloc[0])) == (2026, 8)
    assert df.attrs["source"] == "TWSE-OpenAPI:t187ap05_L(keyless fallback,單股)"


def _sans_time(res: tuple) -> tuple:
    """(rows, meta) 去掉 `fetched_at`：L3 不快取的那一份每次重算，`fetched_at` 是當次時點（同 #744）。"""
    rows, meta = res
    return rows, {k: v for k, v in meta.items() if k != "fetched_at"}


# ══════════════════════════════════════════════════════════════════
# L3 替身（同 #744）
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
    """換掉 L3 的存活池／逐檔季報／涵蓋率；`plan["real_mrev"]` 為真時逐檔月營收走**真的 L1 單股**。"""
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
    if not plan.get("real_mrev"):
        monkeypatch.setattr(mod, "fetch_monthly_revenue", _mrev)
    monkeypatch.setattr(FSS, "get_snapshot_coverage_note", lambda: _COVERAGE)
    mod._scan_cached.clear()


@pytest.fixture
def sv(monkeypatch, world):
    """L3：存活池預設為空 → 走 ② 全市場批次（真的 L1，上游由 `world` 換掉）。"""
    plan = {"pool": [], "qtr": "strong"}
    side = {"pool": 0, "qtr": 0, "mrev": 0}
    _install_svc(SVC, monkeypatch, plan, side)
    yield plan, side
    SVC._scan_cached.clear()


# ══════════════════════════════════════════════════════════════════
# 共用檢查（主測試、修前重現、突變測試共用：修前模型與突變體必須讓它們轉紅）
# ══════════════════════════════════════════════════════════════════
# ── D2-f22 單股 ─────────────────────────────────────────────────
def _check_single_failure_backs_off_then_recovers(mod, w: _World, clock: dict, *, sid: str = "2330",
                                                   twse: str = "none", tpex: str = "none") -> None:
    """FinMind 無資料 ＋ OpenAPI 確定失敗（或該股那一邊失敗）→ 回修前同一份空表 → 冷卻期內 0 次上游 →
    期滿的下一次即拿到新值 → 成功照舊快取。"""
    w.twse, w.tpex = twse, tpex
    _assert_empty_frame(mod.fetch_monthly_revenue(sid))
    n1 = dict(w.calls)
    assert n1["twse"] == 1 and n1["tpex"] == 1, "前提：OpenAPI 兩邊都打過"
    w.recover()                                             # 上游恢復，但仍在冷卻期內
    clock["now"] += FAIL_COOLDOWN_SEC - 1
    within = [mod.fetch_monthly_revenue(sid) for _ in range(3)]
    assert w.calls == n1, "冷卻期內 0 次上游呼叫"
    for df in within:
        _assert_empty_frame(df)                             # 冷卻期內回的是同一份失敗空表
    clock["now"] += 1                                       # 剛好滿冷卻期（`<` 比較：滿即過期）
    df = mod.fetch_monthly_revenue(sid)
    assert not df.empty, "冷卻期過的下一次即拿到新值（修前：失敗的空表凍 6 小時）"
    _assert_single_openapi_row(df, sid)
    n2 = dict(w.calls)
    clock["now"] += 100 * FAIL_COOLDOWN_SEC
    pd.testing.assert_frame_equal(mod.fetch_monthly_revenue(sid), df)
    assert w.calls == n2, "成功照舊快取"


def _check_single_still_cached(mod, w: _World, clock: dict, *, sid: str, twse: str, tpex: str,
                               fm_single: str = "empty") -> pd.DataFrame:
    """沒有「確定失敗」的單股結果（成功、或分不出失敗與真的沒資料的空表）→ 照舊快取 6 小時。"""
    w.fm_single, w.twse, w.tpex = fm_single, twse, tpex
    first = mod.fetch_monthly_revenue(sid)
    n1 = dict(w.calls)
    w.fm_single = "ok"
    w.recover()                                             # 就算上游此刻全變了……
    clock["now"] += 100 * FAIL_COOLDOWN_SEC                 # ……且遠超過冷卻期
    again = mod.fetch_monthly_revenue(sid)
    assert w.calls == n1, "照舊入 6 小時快取（不是退避）：上游呼叫數不變"
    assert repr(again) == repr(first) and again.attrs == first.attrs
    return first


def _check_single_cooldown_is_per_stock_and_months(mod, w: _World, clock: dict) -> None:
    w.twse, w.tpex = "none", "ok"                            # 上市失敗、上櫃正常
    _assert_empty_frame(mod.fetch_monthly_revenue("2330"))   # 2330（上市）→ 確定失敗、冷卻
    _assert_single_openapi_row(mod.fetch_monthly_revenue("6488"), "6488")   # 別檔不被連坐
    n1 = dict(w.calls)
    w.recover()
    _assert_empty_frame(mod.fetch_monthly_revenue("2330"))   # 原鍵仍在冷卻（0 次上游）
    assert w.calls == n1, "原鍵 (2330, 18) 仍在冷卻"
    df12 = mod.fetch_monthly_revenue("2330", months=12)      # 別的 months 照常抓
    _assert_single_openapi_row(df12, "2330")
    assert w.calls["twse"] == n1["twse"] + 1, "退避鍵＝(stock_id, months)（與快取鍵同義）"


def _check_single_clear_resets_both(mod, w: _World, clock: dict) -> None:
    mod.fetch_monthly_revenue("2330")                        # 失敗 → 退避中
    w.recover()
    mod.fetch_monthly_revenue.clear()
    df = mod.fetch_monthly_revenue("2330")
    assert w.calls["twse"] == 2, ".clear() 清掉退避紀錄 → 立刻重打"
    _assert_single_openapi_row(df, "2330")
    mod.fetch_monthly_revenue.clear()
    mod.fetch_monthly_revenue("2330")
    assert w.calls["twse"] == 3, ".clear() 清掉成功快取 → 重打"


def _check_single_success_bumps_generation(mod, w: _World, clock: dict) -> None:
    """別的 session 已開抓（記下世代）→ 本次成功 → 那次較晚寫入的失敗不得進退避表。"""
    _, g = mod._single_fail_cooldown.begin(("2330", 18))
    w.recover()
    _assert_single_openapi_row(mod.fetch_monthly_revenue("2330"), "2330")
    mod._single_fail_cooldown.fail(("2330", 18), g, pd.DataFrame())   # 同儕晚到的失敗
    assert ("2330", 18) not in mod._single_fail_cooldown
    _assert_single_openapi_row(mod.fetch_monthly_revenue("2330"), "2330")


# ── D2-f23 半邊失敗（L1）────────────────────────────────────────
def _check_batch_partial_not_cached_then_recovers(mod, w: _World, clock: dict, *, twse: str = "none",
                                                  tpex: str = "ok") -> None:
    """一邊確定失敗、另一邊有資料 → 回修前同一份半邊表 → 冷卻期內 0 次上游、回同一份 → 期滿的下一次
    拿到兩邊 → 成功照舊快取。"""
    w.twse, w.tpex = twse, tpex
    first = mod.fetch_batch_monthly_revenue()
    want = sorted(({"ok": ["2317", "2330"]}.get(twse, [])) + ({"ok": ["6488"]}.get(tpex, [])))
    assert list(first["stock_id"]) == want and want and len(want) < 3, "前提：只拿到一半"
    n1 = dict(w.calls)
    w.recover()
    clock["now"] += FAIL_COOLDOWN_SEC - 1
    within = [mod.fetch_batch_monthly_revenue() for _ in range(3)]
    assert w.calls == n1, "冷卻期內 0 次上游呼叫"
    for again in within:
        assert repr(again) == repr(first) and again.attrs == first.attrs, "冷卻期內回同一份半邊表"
    clock["now"] += 1
    full = mod.fetch_batch_monthly_revenue()
    assert list(full["stock_id"]) == ["2317", "2330", "6488"], \
        "冷卻期過的下一次即拿到兩邊（修前：半邊表凍 6 小時）"
    assert list(full["revenue"]) == [_OPENAPI_YUAN[s] for s in ("2317", "2330", "6488")]
    n2 = dict(w.calls)
    clock["now"] += 100 * FAIL_COOLDOWN_SEC
    pd.testing.assert_frame_equal(mod.fetch_batch_monthly_revenue(), full)
    assert w.calls == n2, "成功照舊快取"


# ── D2-f23 半邊失敗（L3）────────────────────────────────────────
def _check_l3_partial_not_cached_then_recovers(svc_mod, w: _World, side: dict, clock: dict) -> None:
    """② 全市場月營收是 L1 判定失敗的半邊表 → L3 不入快取 → L1 冷卻期內重算但 0 次上游 → 期滿即拿到新排行
    → 成功照舊快取。"""
    w.twse, w.tpex = "none", "ok"                            # 上市確定失敗、上櫃有資料
    first = svc_mod.run_shortage_scan()
    rows, meta = first
    assert rows == [] and meta["candidates"] == 0, "半邊表是 OpenAPI 單月快照 → 候選池 0 檔"
    assert meta["pool_source"] == "全市場月營收動能候選池（sponsor tier）"
    n1 = dict(w.calls)
    assert n1["twse"] == 1 and n1["tpex"] == 1 and side["pool"] == 1
    w.fm_batch = "ok"                                        # FinMind 全市場與 OpenAPI 都恢復，但仍在 L1 冷卻期內
    w.recover()
    clock["now"] += FAIL_COOLDOWN_SEC - 1
    within = [svc_mod.run_shortage_scan() for _ in range(3)]
    assert w.calls == n1, "L1 冷卻期內 0 次上游呼叫"
    assert side["pool"] == 4, "L3 沒有快取這一份（每次都重算；修前：凍 1 天）"
    assert side["qtr"] == 0, "半邊表 → 候選池 0 檔 → 逐檔深掃 0 次"
    assert all(_sans_time(r) == _sans_time(first) for r in within), "冷卻期內回同一份結果"
    clock["now"] += 1
    rows2, meta2 = svc_mod.run_shortage_scan()
    assert len(rows2) == 1 and rows2[0]["代碼"] == "1001" and meta2["note"] == "", \
        "L1 冷卻期過的下一次即拿到新排行（修前：半邊表那一份凍 1 天）"
    n2, s2 = dict(w.calls), dict(side)
    clock["now"] += 100 * FAIL_COOLDOWN_SEC
    assert svc_mod.run_shortage_scan() == (rows2, meta2)
    assert w.calls == n2 and side == s2, "恢復後的成功照舊入快取"


# ── D2-f21 FinMind 全市場批次的 schema 樣本 ──────────────────────
def _check_finmind_multi_stock_batch_kept(mod, w: _World, n_stocks: int) -> None:
    w.fm_batch = ("multi", n_stocks)
    w.recover()
    df = mod.fetch_batch_monthly_revenue()
    assert (df.attrs.get("source") == "FinMind:TaiwanStockMonthRevenue:batch(all-market)"
            and df["stock_id"].nunique() == n_stocks and len(df) == n_stocks * 19), \
        "FinMind 多檔全市場批次不再被整批丟棄（修前：兩檔以上恆落到 OpenAPI 單月快照）"
    assert w.calls["twse"] == 0 and w.calls["tpex"] == 0, "FinMind 有資料 → 不走 OpenAPI"
    assert list(df.columns) == ["stock_id", "date", "revenue"]
    assert df.equals(df.sort_values(["stock_id", "date"]).reset_index(drop=True))


def _check_all_rows_dropped_keeps_columns(mod, w: _World) -> None:
    """邊界：整理後 0 列（營收全缺）→ 回同欄位的空表（修前行為），不因取首檔而拋錯變成無欄空表。"""
    frame = _fm_batch_frame(["1001", "1002"])
    frame["revenue"] = float("nan")
    w.fm_batch = frame
    out = mod._batch_finmind(18)
    assert out.empty and list(out.columns) == ["stock_id", "date", "revenue"], \
        "樣本取首檔前要先擋空表（否則 .iloc[0] 拋錯 → 回無欄空表）"
    assert out.attrs["source"] == "FinMind:TaiwanStockMonthRevenue:batch(all-market)"


# ── D2-f25 遞增退避 ─────────────────────────────────────────────
def _expected_hits(base: float, cap: float, *, horizon: int, step: int = 60, round_s: float = 0) -> list[float]:
    """獨立參考模型：持續失敗、每 `step` 秒 rerun 一次；一輪重打要花 `round_s` 秒（期間不會 rerun），冷卻從
    該輪結束起算、每次失敗加倍到 `cap`（`base == cap` 即固定冷卻）。回傳真的打到上游那幾輪的開始時點。"""
    times, t, next_ok, w = [], 0.0, 0.0, base
    while t <= horizon:
        if t >= next_ok:
            times.append(t)
            t += round_s
            next_ok, w = t + w, min(w * 2, cap)
        t += step
    return times


def _drive(fn, w: _World, clock: dict, *, horizon: int, step: int = 60) -> list[float]:
    """每 `step` 秒呼叫一次 `fn()`（上游慢時，呼叫本身會把假時鐘往前推）；回傳真的打到 OpenAPI 的那幾次的開始時點。"""
    hits, t0 = [], clock["now"]
    while clock["now"] - t0 <= horizon:
        start = clock["now"]
        before = w.calls["twse"] + w.calls["tpex"]
        fn()
        if w.calls["twse"] + w.calls["tpex"] > before:
            hits.append(start - t0)
        clock["now"] += step
    return hits


_LONG = 4 * TTL_1HOUR       # 4 小時：看得到封頂（連續失敗約 1.5 小時起每段都是 TTL_1HOUR）
_ESC_4H = [0, 180, 540, 1260, 2700, 5580, 9180, 12780]       # 起點 180、逐次加倍、封頂 3600


def _check_batch_escalating_schedule(mod, w: _World, clock: dict) -> None:
    hits = _drive(mod.fetch_batch_monthly_revenue, w, clock, horizon=_LONG)
    assert hits == _expected_hits(FAIL_COOLDOWN_SEC, TTL_1HOUR, horizon=_LONG) == _ESC_4H, \
        "D2-f25：全市場冷卻遞增（起點 FAIL_COOLDOWN_SEC、每次加倍、上限 TTL_1HOUR）"


def _check_single_escalating_schedule(mod, w: _World, clock: dict) -> None:
    hits = _drive(lambda: mod.fetch_monthly_revenue("2330"), w, clock, horizon=_LONG)
    assert hits == _ESC_4H, "單股冷卻與全市場同設定（遞增、上限 TTL_1HOUR）"


# ── D2-f26／L1 兩處 except 的範圍 ────────────────────────────────
def _leaked(payload):
    return FC.CachedFailure(payload, "別處漏出來的 CachedFailure")


def _check_run_scan_catches_only_own_subclass(svc_mod, monkeypatch) -> None:
    """`run_shortage_scan` 只接 `_CandidatePoolFetchFailed`：別處的 `CachedFailure`（即使 payload 剛好拆得成
    (rows, meta)）必須原樣往上拋，不得被當成 (rows, meta) 回傳。"""
    for exc in (_leaked(([{"代碼": "9999"}], {"note": "不該被當成結果"})),
                MR._BatchRevenueFetchFailed(pd.DataFrame({"a": [1], "b": [2]}), "L1 漏出來"),
                MR._SingleRevenueFetchFailed(pd.DataFrame(), "L1 單股漏出來")):
        def _boom(max_scan, _e=exc):
            raise _e
        monkeypatch.setattr(svc_mod, "_scan_cached", _boom)
        with pytest.raises(FC.CachedFailure) as ei:
            svc_mod.run_shortage_scan()
        assert ei.value is exc, "D2-f26：別處的 CachedFailure 原樣往上拋"


def _check_single_catches_only_own_subclass(mod, monkeypatch) -> None:
    for exc in (_leaked(pd.DataFrame({"x": [1]})), mod._BatchRevenueFetchFailed(pd.DataFrame(), "batch")):
        def _boom(stock_id, months=18, _e=exc):
            raise _e
        monkeypatch.setattr(mod, "_fetch_monthly_revenue_cached", _boom)
        with pytest.raises(FC.CachedFailure) as ei:
            mod.fetch_monthly_revenue("2330")
        assert ei.value is exc
        assert ("2330", 18) not in mod._single_fail_cooldown, "別處的失敗不得記進單股退避表"


def _check_batch_catches_only_own_subclass(mod, monkeypatch) -> None:
    for exc in (_leaked(pd.DataFrame({"x": [1]})), mod._SingleRevenueFetchFailed(pd.DataFrame(), "single")):
        def _boom(months=18, _e=exc):
            raise _e
        monkeypatch.setattr(mod, "_fetch_batch_monthly_revenue_cached", _boom)
        with pytest.raises(FC.CachedFailure) as ei:
            mod.fetch_batch_monthly_revenue()
        assert ei.value is exc
        assert 18 not in mod._batch_fail_cooldown, "別處的失敗不得記進全市場退避表"


# ══════════════════════════════════════════════════════════════════
# D2-f22 單股：確定失敗不入快取、冷卻期內不重打、期滿重打拿到新值
# ══════════════════════════════════════════════════════════════════
#: 單股「確定抓取失敗」的樣態：值 ＝ (股號, 上市, 上櫃, 有無 token)。
_SINGLE_FAILURES = {
    "both_fetch_none": ("2330", "none", "none", True),
    "both_non200": ("2330", "non200", "non200", True),
    "both_json_decode": ("2330", "json_err", "json_err", True),
    "both_fetch_raise": ("2330", "raise", "raise", True),
    "own_market_twse_failed": ("2330", "none", "ok", True),        # 該股（上市）所在的那一邊失敗
    "own_market_tpex_failed": ("6488", "ok", "raise", True),       # 該股（上櫃）所在的那一邊失敗
    "one_failed_other_empty200": ("2330", "non200", "empty200", True),
    "no_token": ("2330", "none", "none", False),
}


class TestD2f22SingleFailureNotCached:
    @pytest.mark.parametrize("case", sorted(_SINGLE_FAILURES))
    def test_failure_backs_off_then_recovers(self, world, fc_clock, monkeypatch, case):
        sid, twse, tpex, token = _SINGLE_FAILURES[case]
        if not token:
            monkeypatch.delenv("FINMIND_TOKEN", raising=False)
        _check_single_failure_backs_off_then_recovers(MR, world, fc_clock, sid=sid, twse=twse, tpex=tpex)
        assert (sid, 18) not in MR._single_fail_cooldown, "成功即解除退避"

    def test_not_listed_with_one_side_failed_not_cached(self, world, fc_clock):
        """這一層不知道該股在哪一邊：一邊確定失敗、這檔又沒拿到 → 不入快取（不猜它在健康的那一邊）。
        恢復後若仍查無此檔（兩邊都 200）→ 那才是「沒有確定失敗的空表」，照舊快取。"""
        world.twse, world.tpex = "ok", "none"
        _assert_empty_frame(MR.fetch_monthly_revenue("9999"))
        assert ("9999", 18) in MR._single_fail_cooldown
        world.recover()
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        _assert_empty_frame(MR.fetch_monthly_revenue("9999"))
        assert world.calls["twse"] == 2, "冷卻期過重打一次"
        assert ("9999", 18) not in MR._single_fail_cooldown
        n = dict(world.calls)
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
        _assert_empty_frame(MR.fetch_monthly_revenue("9999"))
        assert world.calls == n, "兩邊都 200 仍查無此檔 → 照舊快取"

    def test_finmind_recovery_is_retried_after_cooldown(self, world, fc_clock):
        """修前：失敗凍 6 小時，連 FinMind 都不再問；現在冷卻期過就重問 FinMind，恢復即拿到完整歷史。"""
        _assert_empty_frame(MR.fetch_monthly_revenue("2330"))
        world.fm_single = "ok"
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        df = MR.fetch_monthly_revenue("2330")
        assert len(df) == 19 and df.attrs["source"] == "FinMind:TaiwanStockMonthRevenue:single"
        assert world.calls["fm_single"] == 2 and world.calls["twse"] == 1, "FinMind 有資料 → 不再走 OpenAPI"

    def test_cooldown_is_per_stock_and_months(self, world, fc_clock):
        _check_single_cooldown_is_per_stock_and_months(MR, world, fc_clock)

    def test_clear_resets_cache_and_backoff(self, world, fc_clock):
        _check_single_clear_resets_both(MR, world, fc_clock)

    def test_success_bumps_generation(self, world, fc_clock):
        _check_single_success_bumps_generation(MR, world, fc_clock)

    def test_late_failure_does_not_override_peer_success(self, world, monkeypatch):
        """競態：本次抓取期間另一個 session 已成功 → 本次較晚的失敗不得寫進退避表。"""
        def _fail_after_peer_success(stock_id, months=18):
            MR._single_fail_cooldown.success((stock_id, months))
            raise MR._SingleRevenueFetchFailed(pd.DataFrame(), "late failure")
        monkeypatch.setattr(MR, "_fetch_monthly_revenue_cached", _fail_after_peer_success)
        _assert_empty_frame(MR.fetch_monthly_revenue("2330"))
        assert ("2330", 18) not in MR._single_fail_cooldown

    def test_backoff_returns_a_copy(self, world):
        df = MR.fetch_monthly_revenue("2330")
        df["污染"] = []
        df.attrs["污染"] = True
        _assert_empty_frame(MR.fetch_monthly_revenue("2330"))

    def test_parallel_calls_during_failure(self, world):
        n_threads = 8
        barrier = threading.Barrier(n_threads)
        results, errors = [], []

        def _worker():
            try:
                barrier.wait(timeout=5)
                results.append(MR.fetch_monthly_revenue("2330"))
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
            _assert_empty_frame(df)
        assert 1 <= world.calls["twse"] <= n_threads
        n = dict(world.calls)
        MR.fetch_monthly_revenue("2330")
        assert world.calls == n, "並行失敗之後：冷卻期內不再重打"

    def test_failure_log_then_silent_in_cooldown(self, world, capsys):
        MR.fetch_monthly_revenue("2330")
        out = capsys.readouterr().out
        assert "[mrev-fetcher] 2330 FinMind 無資料 → TWSE/TPEx OpenAPI fallback(單股篩)" in out, "修前的 log 照印"
        assert ("[mrev-fetcher] 2330 無資料且 OpenAPI 確定抓取失敗(上市: status=None；上櫃: status=None)→ 不入快取,"
                f"冷卻期內不重打上游(冷卻由 {FAIL_COOLDOWN_SEC:.0f}s 起、連續失敗加倍、上限 {TTL_1HOUR:.0f}s)") in out
        MR.fetch_monthly_revenue("2330")
        assert capsys.readouterr().out == "", "冷卻期內不重打，也就不再印失敗 log"

    def test_known_cost_global_cache_clear_keeps_cooldown(self, world, fc_clock):
        """已知代價（據實釘住，同 #744 的全市場那支）：全站 `st.cache_data.clear()`（側欄「強制刷新數據」、個股頁
        「強制重抓」）清不掉單股退避表 —— 冷卻期內仍回失敗、不重抓；期滿即恢復。這裡只清這一支的
        `st.cache_data`（＝全站 clear 對它的效果），不在測試行程裡真的清全站快取。"""
        MR.fetch_monthly_revenue("2330")
        world.recover()
        MR._fetch_monthly_revenue_cached.clear()
        assert ("2330", 18) in MR._single_fail_cooldown, "退避表是一般 Python 物件，st.cache_data 的 clear 碰不到"
        _assert_empty_frame(MR.fetch_monthly_revenue("2330"))
        assert world.calls["twse"] == 1
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        _assert_single_openapi_row(MR.fetch_monthly_revenue("2330"), "2330")

    def test_escalating_cooldown(self, world, fc_clock):
        assert MR._single_fail_cooldown.seconds == FAIL_COOLDOWN_SEC
        assert MR._single_fail_cooldown.max_seconds == TTL_1HOUR
        _check_single_escalating_schedule(MR, world, fc_clock)

    def test_success_resets_escalation(self, world, fc_clock):
        for window in (FAIL_COOLDOWN_SEC, 2 * FAIL_COOLDOWN_SEC):   # 連續失敗兩段：180 → 360
            MR.fetch_monthly_revenue("2330")
            fc_clock["now"] += window
        world.recover()
        _assert_single_openapi_row(MR.fetch_monthly_revenue("2330"), "2330")   # 第 3 次：成功 → 歸零
        MR._fetch_monthly_revenue_cached.clear()                   # 只清成功快取（退避表不動，驗「成功即歸零」）
        world.twse = world.tpex = "none"
        MR.fetch_monthly_revenue("2330")                           # 再失敗：冷卻回到起點 180（沒歸零會是 720）
        world.recover()
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        _assert_single_openapi_row(MR.fetch_monthly_revenue("2330"), "2330")


class TestD2f22StillCached:
    #: 沒有「確定失敗」的單股結果：值 ＝ (股號, 上市, 上櫃, FinMind 單股)。
    _CASES = {
        "found_other_market_failed": ("6488", "none", "ok", "empty"),     # 一檔只在一個市場：拿到了就是完整的
        "found_other_market_raise": ("2330", "ok", "raise", "empty"),
        "not_listed_both_200": ("9999", "ok", "ok", "empty"),              # 分不出失敗與真的沒有 → 照舊
        "not_listed_one_empty200": ("9999", "ok", "empty200", "empty"),
        "both_empty200": ("2330", "empty200", "empty200", "empty"),
        "finmind_ok": ("2330", "none", "none", "ok"),
        # D2-f22 的「變形」（本批不處理，等 D2-f24）：FinMind 掛掉（這一層只看得到空）、OpenAPI 正常 → 降級 1 列照舊快取
        "variant_finmind_down_openapi_ok": ("2330", "ok", "ok", "empty"),
    }

    @pytest.mark.parametrize("case", sorted(_CASES))
    def test_still_cached(self, world, fc_clock, case):
        sid, twse, tpex, fm = self._CASES[case]
        first = _check_single_still_cached(MR, world, fc_clock, sid=sid, twse=twse, tpex=tpex, fm_single=fm)
        assert len(MR._single_fail_cooldown) == 0, "不是確定失敗，不記退避"
        if case.startswith(("found_", "variant_")):
            _assert_single_openapi_row(first, sid)
        elif case == "finmind_ok":
            assert len(first) == 19
        else:
            _assert_empty_frame(first)


class TestD2f22IdenticalToPrefix:
    """修前模型（b2dafba 原文）與現行在同一個世界、第一次呼叫的回傳逐項相同（含 attrs）。"""

    @pytest.mark.parametrize("case", sorted(_SINGLE_FAILURES) + sorted(TestD2f22StillCached._CASES))
    def test_first_call_identical(self, world, monkeypatch, frozen_now, case):
        if case in _SINGLE_FAILURES:
            sid, twse, tpex, token = _SINGLE_FAILURES[case]
            fm = "empty"
        else:
            (sid, twse, tpex, fm), token = TestD2f22StillCached._CASES[case], True
        if not token:
            monkeypatch.delenv("FINMIND_TOKEN", raising=False)
        pre = _with_prefix_mr(f"single_first_{case}", monkeypatch, world)
        world.fm_single, world.twse, world.tpex = fm, twse, tpex
        try:
            got, want = MR.fetch_monthly_revenue(sid), pre.fetch_monthly_revenue(sid)
            assert repr(got) == repr(want) and got.attrs == want.attrs
            pd.testing.assert_frame_equal(got, want)
            assert list(got.dtypes) == list(want.dtypes)
        finally:
            pre.fetch_monthly_revenue.clear()


# ══════════════════════════════════════════════════════════════════
# D2-f23 半邊失敗：L1 不入快取
# ══════════════════════════════════════════════════════════════════
_PARTIAL = {"twse_none_tpex_ok": ("none", "ok"), "twse_non200_tpex_ok": ("non200", "ok"),
            "twse_ok_tpex_raise": ("ok", "raise"), "twse_ok_tpex_json_err": ("ok", "json_err")}


class TestD2f23BatchPartialNotCached:
    @pytest.mark.parametrize("case", sorted(_PARTIAL))
    def test_partial_backs_off_then_recovers(self, world, fc_clock, case):
        twse, tpex = _PARTIAL[case]
        _check_batch_partial_not_cached_then_recovers(MR, world, fc_clock, twse=twse, tpex=tpex)
        assert 18 not in MR._batch_fail_cooldown, "成功即解除退避"

    def test_with_status_flags_partial_as_failed(self, world, fc_clock):
        world.twse, world.tpex = "none", "ok"
        df, failed = MR.fetch_batch_monthly_revenue.with_status(18)
        assert failed is True and list(df["stock_id"]) == ["6488"]
        df2, failed2 = MR.fetch_batch_monthly_revenue.with_status(18)          # 冷卻期內：同一份、同旗標
        assert failed2 is True and repr(df2) == repr(df)
        world.recover()
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        df3, failed3 = MR.fetch_batch_monthly_revenue.with_status(18)
        assert failed3 is False and len(df3) == 3

    def test_partial_with_ambiguous_other_side_still_cached(self, world, fc_clock):
        """另一邊是 200 但 0 筆（分不出失敗與真的沒有）→ 不是確定失敗 → 照舊快取（本批不改）。"""
        world.twse, world.tpex = "ok", "empty200"
        first = MR.fetch_batch_monthly_revenue()
        assert list(first["stock_id"]) == ["2317", "2330"]
        n = dict(world.calls)
        world.recover()
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
        pd.testing.assert_frame_equal(MR.fetch_batch_monthly_revenue(), first)
        assert world.calls == n and len(MR._batch_fail_cooldown) == 0

    def test_partial_log(self, world, capsys):
        world.twse, world.tpex = "ok", "raise"
        MR.fetch_batch_monthly_revenue()
        out = capsys.readouterr().out
        assert ("[mrev-fetcher] batch 只拿到一半、OpenAPI 確定抓取失敗(上櫃: ConnectionError: proxy down)→ 不入快取,"
                f"冷卻期內不重打上游(冷卻由 {FAIL_COOLDOWN_SEC:.0f}s 起、連續失敗加倍、上限 {TTL_1HOUR:.0f}s)") in out

    @pytest.mark.parametrize("case", sorted(_PARTIAL))
    def test_first_call_identical_to_prefix(self, world, monkeypatch, frozen_now, case):
        pre = _with_prefix_mr(f"partial_first_{case}", monkeypatch, world)
        world.twse, world.tpex = _PARTIAL[case]
        try:
            got, want = MR.fetch_batch_monthly_revenue(), pre.fetch_batch_monthly_revenue()
            assert repr(got) == repr(want) and got.attrs == want.attrs
            pd.testing.assert_frame_equal(got, want)
            within = MR.fetch_batch_monthly_revenue()                            # 冷卻期內的那一份也逐字相同
            assert repr(within) == repr(want) and within.attrs == want.attrs
        finally:
            pre.fetch_batch_monthly_revenue.clear()


class TestBatchIdenticalToPrefix:
    """全市場那支其餘樣態（成功／全失敗／分不出的空表）第一次呼叫與修前模型（b2dafba）逐字相同。
    刻意不含 FinMind 多檔（D2-f21 的預期改變，見 `TestD2f21FinmindBatchSample`）。"""

    _CASES = {"finmind_ok_one_stock": ("ok", "ok", "ok"), "openapi_both_ok": ("empty", "ok", "ok"),
              "openapi_both_failed": ("empty", "none", "none"), "one_failed_other_empty200": ("empty", "raise", "empty200"),
              "ambiguous_both_empty200": ("empty", "empty200", "empty200")}

    @pytest.mark.parametrize("case", sorted(_CASES))
    def test_first_call_identical(self, world, monkeypatch, frozen_now, case):
        pre = _with_prefix_mr(f"batch_first_{case}", monkeypatch, world)
        world.fm_batch, world.twse, world.tpex = self._CASES[case]
        try:
            got, want = MR.fetch_batch_monthly_revenue(), pre.fetch_batch_monthly_revenue()
            assert repr(got) == repr(want) and got.attrs == want.attrs
            pd.testing.assert_frame_equal(got, want)
        finally:
            pre.fetch_batch_monthly_revenue.clear()


# ══════════════════════════════════════════════════════════════════
# D2-f23 半邊失敗：L3 缺貨掃描不入快取
# ══════════════════════════════════════════════════════════════════
class TestD2f23ScanPartialNotCached:
    def test_not_cached_then_recovers_after_l1_cooldown(self, sv, world, fc_clock):
        _plan, side = sv
        _check_l3_partial_not_cached_then_recovers(SVC, world, side, fc_clock)

    def test_output_identical_to_prefix(self, sv, world, monkeypatch, frozen_now):
        """現行（第一次＋冷卻期內兩次）與修前模型（b2dafba 的 L3 ＋ L1）的第一次逐字相同（含鍵的順序）。"""
        world.twse, world.tpex = "none", "ok"
        now = [SVC.run_shortage_scan() for _ in range(3)]
        pre_mr, pre_svc = _prefix_mr("scan_partial"), _prefix_svc("scan_partial")
        world2 = _World(world.clock)
        world2.twse, world2.tpex = "none", "ok"
        monkeypatch.setattr(PH, "fetch_url", world2.fetch_url)
        _install_mr(pre_mr, monkeypatch, world2)
        _install_svc(pre_svc, monkeypatch, {"pool": [], "qtr": "strong"}, {"pool": 0, "qtr": 0, "mrev": 0})
        monkeypatch.setattr(pre_svc, "fetch_batch_monthly_revenue", pre_mr.fetch_batch_monthly_revenue)
        try:
            want = pre_svc.run_shortage_scan()
            for got in now:
                assert repr(got) == repr(want)
                assert list(got[1]) == list(want[1]), "meta 鍵的順序也同修前"
            assert want[1]["note"] == "⚠️ 深掃 0 檔後無可評分：資料不足 0 檔"
        finally:
            pre_svc._scan_cached.clear()
            pre_mr.fetch_batch_monthly_revenue.clear()

    def test_ui_text_same_as_prefix(self, sv, world, monkeypatch):
        """K1：v2 找標的「缺貨動能」列 —— 半邊失敗時修前顯示什麼，修後（冷卻期內每一次）顯示同一句。"""
        from src.ui.views import page_find as PF
        world.twse, world.tpex = "none", "ok"
        now = [PF._load_shortage(("shortage",)) for _ in range(3)]
        pre_mr, pre_svc = _with_prefix_mr("ui_partial_mr", monkeypatch, world), _prefix_svc("ui_partial")
        _install_svc(pre_svc, monkeypatch, {"pool": [], "qtr": "strong"}, {"pool": 0, "qtr": 0, "mrev": 0})
        monkeypatch.setattr(pre_svc, "fetch_batch_monthly_revenue", pre_mr.fetch_batch_monthly_revenue)
        monkeypatch.setattr(SVC, "run_shortage_scan", pre_svc.run_shortage_scan)
        try:
            want = PF._load_shortage(("shortage",))
        finally:
            pre_svc._scan_cached.clear()
            pre_mr.fetch_batch_monthly_revenue.clear()
        assert now == [want] * 3 and want[0] is None and want[1]

    def test_ambiguous_partial_still_cached(self, sv, world, fc_clock):
        """L1 沒有確定失敗（另一邊 200 但 0 筆）→ L3 照舊快取（本批不改）。"""
        _plan, side = sv
        world.twse, world.tpex = "ok", "empty200"
        first = SVC.run_shortage_scan()
        n1, s1 = dict(world.calls), dict(side)
        world.fm_batch = "ok"
        world.recover()
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
        assert SVC.run_shortage_scan() == first
        assert world.calls == n1 and side == s1

    def test_batch_success_still_cached(self, sv, world, fc_clock):
        _plan, side = sv
        world.fm_batch = "ok"
        first = SVC.run_shortage_scan()
        assert len(first[0]) == 1
        n1, s1 = dict(world.calls), dict(side)
        world.fm_batch = "empty"
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
        assert SVC.run_shortage_scan() == first
        assert world.calls == n1 and side == s1

    def test_refresh_during_partial_backoff_refetches(self, sv, world):
        world.twse, world.tpex = "none", "ok"
        SVC.run_shortage_scan()
        world.fm_batch = "ok"
        rows, meta = SVC.run_shortage_scan(refresh=True)
        assert len(rows) == 1 and meta["note"] == ""
        assert world.calls["fm_batch"] == 2


# ══════════════════════════════════════════════════════════════════
# D2-f21 FinMind 全市場批次：schema 樣本只取首檔
# ══════════════════════════════════════════════════════════════════
@_NEEDS_PANDERA
class TestD2f21FinmindBatchSample:
    @pytest.mark.parametrize("n", [1, 2, 3, 50, 1800])
    def test_multi_stock_batch_kept(self, world, n):
        _check_finmind_multi_stock_batch_kept(MR, world, n)

    def test_batch_finmind_direct_output(self, world, frozen_now):
        world.fm_batch = ("multi", 3)
        df = MR._batch_finmind(18)
        assert list(df["stock_id"].unique()) == ["1001", "1002", "1003"] and len(df) == 57
        assert str(df["revenue"].dtype) == "float64" and pd.api.types.is_datetime64_any_dtype(df["date"])
        assert df.attrs == {"source": "FinMind:TaiwanStockMonthRevenue:batch(all-market)",
                            "fetched_at": frozen_now.isoformat()}

    def test_single_stock_output_identical_to_prefix(self, world, monkeypatch, frozen_now):
        """一檔時修前本來就過（樣本不跨檔）→ 逐字相同。"""
        pre = _with_prefix_mr("f21_one", monkeypatch, world)
        world.fm_batch = "ok"
        got, want = MR._batch_finmind(18), pre._batch_finmind(18)
        assert repr(got) == repr(want) and got.attrs == want.attrs

    def test_bad_first_stock_still_rejects_whole_batch(self, world, capsys):
        """「樣本違反 → 整批棄用」照舊（§1）：首檔有負營收 → 整批回空、改走 OpenAPI。"""
        world.fm_batch = _fm_batch_frame(["1001", "1002"], bad=("1001", 5))
        out = MR._batch_finmind(18)
        assert out.empty and list(out.columns) == ["stock_id", "date", "revenue"]
        assert "batch 樣本 schema 違反 → 整批棄用" in capsys.readouterr().out
        world.recover()
        df = MR.fetch_batch_monthly_revenue()
        assert list(df["stock_id"]) == ["2317", "2330", "6488"], "整批棄用 → 走 OpenAPI 備援"

    def test_sample_is_first_stock_only(self, world):
        """取樣範圍照註解本意＝首檔：第二檔以後的異常不在樣本內（抽樣檢查的既有取捨，本批不改）。"""
        world.fm_batch = _fm_batch_frame(["1001", "1002"], bad=("1002", 5))
        assert len(MR._batch_finmind(18)) == 38

    def test_sample_is_first_36_rows_of_first_stock(self, world):
        """首檔超過 36 列時只驗前 36 列（「首檔 36 列」）；前 36 列內有異常 → 整批棄用。"""
        world.fm_batch = _fm_batch_frame(["1001", "1002"], n=40, bad=("1001", 38))
        assert len(MR._batch_finmind(18)) == 80
        world.fm_batch = _fm_batch_frame(["1001", "1002"], n=40, bad=("1001", 35))
        assert MR._batch_finmind(18).empty

    def test_all_rows_dropped_returns_same_empty_frame_as_prefix(self, world, monkeypatch, frozen_now):
        """邊界：全部列都被 dropna 掉（整理後 0 列）→ 回的空表與修前逐字相同（樣本取首檔前先擋空表）。"""
        _check_all_rows_dropped_keeps_columns(MR, world)
        got = MR._batch_finmind(18)
        pre = _with_prefix_mr("f21_allnan", monkeypatch, world)
        want = pre._batch_finmind(18)
        assert got.empty and repr(got) == repr(want) and got.attrs == want.attrs

    def test_l3_batch_path_gets_candidates(self, sv, world):
        """② 全市場批次：FinMind 多檔 → 候選池有料（修前：整批被丟、候選池 0 檔）。"""
        _plan, side = sv
        world.fm_batch = ("multi", 3)
        rows, meta = SVC.run_shortage_scan()
        assert meta["candidates"] == 3 and meta["deep_scanned"] == 3 and side["qtr"] == 3
        assert sorted(r["代碼"] for r in rows) == ["1001", "1002", "1003"]


# ══════════════════════════════════════════════════════════════════
# D2-f25 遞增退避
# ══════════════════════════════════════════════════════════════════
class TestD2f25BatchEscalatingCooldown:
    def test_config_reuses_existing_constants(self):
        assert MR._batch_fail_cooldown.seconds == FAIL_COOLDOWN_SEC
        assert MR._batch_fail_cooldown.max_seconds == TTL_1HOUR
        tree = ast.parse(pathlib.Path(MR.__file__).read_text(encoding="utf-8"))
        calls = {t.id: ast.unparse(n.value) for n in tree.body if isinstance(n, ast.Assign)
                 for t in n.targets if isinstance(t, ast.Name) and t.id.endswith("_fail_cooldown")}
        assert calls == {"_single_fail_cooldown": "_FailCooldown(max_seconds=TTL_1HOUR)",
                         "_batch_fail_cooldown": "_FailCooldown(max_seconds=TTL_1HOUR)"}, \
            "沿用既有常數（FAIL_COOLDOWN_SEC 為預設起點、TTL_1HOUR 為上限），不新增數字"

    def test_escalating_schedule_4h(self, world, fc_clock):
        _check_batch_escalating_schedule(MR, world, fc_clock)

    def test_partial_failure_escalates_too(self, world, fc_clock):
        world.twse, world.tpex = "none", "ok"
        hits = _drive(MR.fetch_batch_monthly_revenue, world, fc_clock, horizon=_LONG)
        assert hits == _ESC_4H

    def test_success_resets_escalation(self, world, fc_clock):
        for window in (FAIL_COOLDOWN_SEC, 2 * FAIL_COOLDOWN_SEC, 4 * FAIL_COOLDOWN_SEC):
            MR.fetch_batch_monthly_revenue()
            fc_clock["now"] += window
        world.recover()
        assert len(MR.fetch_batch_monthly_revenue()) == 3          # 成功 → 歸零
        MR._fetch_batch_monthly_revenue_cached.clear()             # 只清成功快取（退避表不動，驗「成功即歸零」）
        world.twse = world.tpex = "none"
        MR.fetch_batch_monthly_revenue()                            # 再失敗：冷卻回到起點 180（沒歸零會是 1440）
        world.recover()
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        assert len(MR.fetch_batch_monthly_revenue()) == 3

    def test_slow_upstream_stalls_fixed_vs_escalating(self, world, fc_clock, monkeypatch):
        """D2-f25 情境：上游只收連線、不回應 —— 一輪重打卡 264 秒（D2-f25 登記的 QA 量測值，本檔照用、未實測），
        冷卻從該輪結束起算；頁面每 60 秒 rerun。固定 180 秒（修前）＝ 每 444 秒（約 7.4 分鐘）再卡一次，
        3 小時卡 25 次；遞增後 3 小時卡 7 次（封頂後每 3600＋264 秒一次）。兩者都與獨立參考模型逐點相同。"""
        horizon, round_s = 3 * TTL_1HOUR, 264
        world.delay = round_s / 2                                   # 上市、上櫃各卡一半
        now = _drive(MR.fetch_batch_monthly_revenue, world, fc_clock, horizon=horizon)
        assert now == _expected_hits(FAIL_COOLDOWN_SEC, TTL_1HOUR, horizon=horizon, round_s=round_s)
        assert now == [0, 444, 1068, 2052, 3756, 6900, 10764]

        pre = _with_prefix_mr("slow", monkeypatch, world)
        fc_clock["now"] += 10 * horizon
        try:
            fixed = _drive(pre.fetch_batch_monthly_revenue, world, fc_clock, horizon=horizon)
        finally:
            pre.fetch_batch_monthly_revenue.clear()
        assert fixed == _expected_hits(FAIL_COOLDOWN_SEC, FAIL_COOLDOWN_SEC, horizon=horizon, round_s=round_s)
        assert {b - a for a, b in zip(fixed, fixed[1:])} == {444}, "修前：每 264＋180＝444 秒（約 7.4 分鐘）卡一次"
        assert len(fixed) == 25 and len(now) == 7


# ══════════════════════════════════════════════════════════════════
# D2-f26：except 的範圍（只補測試；L1 兩處同型一併守住）
# ══════════════════════════════════════════════════════════════════
class TestD2f26ExceptScope:
    # 注意：這兩條不用 `sv`（它的 teardown 會呼叫 `SVC._scan_cached.clear()`，而這裡的 `_scan_cached` 已被換成
    # 會拋錯的替身）；只需要換掉涵蓋率注入。
    def test_run_shortage_scan_catches_only_own_subclass(self, monkeypatch):
        monkeypatch.setattr(FSS, "get_snapshot_coverage_note", lambda: _COVERAGE)
        _check_run_scan_catches_only_own_subclass(SVC, monkeypatch)

    def test_run_shortage_scan_still_catches_own_subclass(self, monkeypatch):
        """正向對照：自己的 `_CandidatePoolFetchFailed` 照舊被接住、拆成 (rows, meta)、套用快取外注入。"""
        monkeypatch.setattr(FSS, "get_snapshot_coverage_note", lambda: _COVERAGE)
        payload = ([{"代碼": "1001"}], {"note": "失敗那一份"})
        monkeypatch.setattr(SVC, "_scan_cached", lambda max_scan: (_ for _ in ()).throw(
            SVC._CandidatePoolFetchFailed(payload)))
        rows, meta = SVC.run_shortage_scan(name_map={"1001": "甲"})
        assert rows == [{"代碼": "1001", "名稱": "甲"}] and meta == {"note": "失敗那一份", "coverage_note": _COVERAGE}

    def test_single_fetch_catches_only_own_subclass(self, world, monkeypatch):
        _check_single_catches_only_own_subclass(MR, monkeypatch)

    def test_batch_fetch_catches_only_own_subclass(self, world, monkeypatch):
        _check_batch_catches_only_own_subclass(MR, monkeypatch)

    def test_exception_classes_are_disjoint_private_subclasses(self):
        classes = (MR._SingleRevenueFetchFailed, MR._BatchRevenueFetchFailed, SVC._CandidatePoolFetchFailed)
        for c in classes:
            assert issubclass(c, FC.CachedFailure) and c is not FC.CachedFailure
        for a in classes:
            for b in classes:
                assert a is b or not issubclass(a, b), f"{a.__name__} 不得是 {b.__name__} 的子類別"


# ══════════════════════════════════════════════════════════════════
# 公開介面與呼叫端契約
# ══════════════════════════════════════════════════════════════════
def _load_script(rel: str, name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPublicContract:
    def test_signatures_and_clear_unchanged(self):
        sig = inspect.signature(MR.fetch_monthly_revenue)
        assert [(p.name, p.kind, p.default) for p in sig.parameters.values()] == [
            ("stock_id", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
            ("months", inspect.Parameter.POSITIONAL_OR_KEYWORD, 18)], "單股公開簽名同修前"
        (name, p), = inspect.signature(MR.fetch_batch_monthly_revenue).parameters.items()
        assert (name, p.kind, p.default) == ("months", p.POSITIONAL_OR_KEYWORD, 18), "全市場公開簽名同修前"
        assert callable(MR.fetch_monthly_revenue.clear) and callable(MR.fetch_batch_monthly_revenue.clear)
        assert MR.fetch_batch_monthly_revenue.with_status is MR._fetch_batch_monthly_revenue_with_status
        assert SVC.fetch_monthly_revenue is MR.fetch_monthly_revenue, "L3 import 到的是外層（有冷卻的那一支）"
        assert SVC.fetch_batch_monthly_revenue is MR.fetch_batch_monthly_revenue

    def test_cache_layers_keep_prefix_decorators(self):
        tree = ast.parse(pathlib.Path(MR.__file__).read_text(encoding="utf-8"))
        fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        for cached in ("_fetch_monthly_revenue_cached", "_fetch_batch_monthly_revenue_cached"):
            assert [ast.unparse(d) for d in fns[cached].decorator_list] == \
                ["st.cache_data(ttl=TTL_6HOUR, show_spinner=False)"], "快取層 TTL／參數同修前"
        for outer in ("fetch_monthly_revenue", "fetch_batch_monthly_revenue"):
            assert fns[outer].decorator_list == [], "外層不快取 —— 失敗才不會被凍住"
        stree = ast.parse(pathlib.Path(SVC.__file__).read_text(encoding="utf-8"))
        fn = next(n for n in stree.body if isinstance(n, ast.FunctionDef) and n.name == "_scan_cached")
        assert [ast.unparse(d) for d in fn.decorator_list] == ["st.cache_data(ttl=TTL_1DAY, show_spinner=False)"]
        assert TTL_6HOUR == 21600


class TestCallers:
    """呼叫端逐一核對（`fetch_monthly_revenue`：L3 `_score_and_diagnose`、L2 `fin_trend_score.compute_one_stock_trend`、
    `scripts/shortage_cli.build_stock_input`；`fetch_batch_monthly_revenue`：L3 `_batch_revenue_with_status`、
    `scripts/export_stock_db.write_monthly_revenue`；`run_shortage_scan`：v2 `page_find._load_shortage` 等）：
    第一次呼叫的回傳與修前逐字相同；差別只在「失敗那一份會不會被凍住」。"""

    def test_l3_survivor_path_caller(self, world, monkeypatch, fc_clock, frozen_now):
        """L3 ①（逐檔呼叫單股月營收）：第一次與修前逐字相同。L3 自己仍把 ① 的結果快取 1 天（D2-f30，本批不處理）；
        `refresh=True`（它不清單股快取）後，修前那一檔的失敗仍凍在 L1 6 小時，現在冷卻期過即重問、拿到新值。"""
        plan, side = {"pool": ["2330"], "qtr": "strong", "real_mrev": True}, {"pool": 0, "qtr": 0, "mrev": 0}
        _install_svc(SVC, monkeypatch, plan, side)
        first = SVC.run_shortage_scan()
        pre_mr, pre_svc = _with_prefix_mr("caller_l3", monkeypatch, world), _prefix_svc("caller_l3")
        _install_svc(pre_svc, monkeypatch, plan, {"pool": 0, "qtr": 0, "mrev": 0})
        monkeypatch.setattr(pre_svc, "fetch_monthly_revenue", pre_mr.fetch_monthly_revenue)
        try:
            assert repr(pre_svc.run_shortage_scan()) == repr(first), "第一次：與修前逐字相同"
            world.fm_single = "ok"                                           # FinMind 恢復
            fc_clock["now"] += FAIL_COOLDOWN_SEC
            now_rows, _ = SVC.run_shortage_scan(refresh=True)
            pre_rows, _ = pre_svc.run_shortage_scan(refresh=True)
            assert now_rows[0]["理由"] != first[0][0]["理由"], "現在：重問到 FinMind，月營收年增率進得來"
            assert pre_rows[0]["理由"] == first[0][0]["理由"], "修前：單股失敗凍在 L1，refresh 也拿不到"
        finally:
            SVC._scan_cached.clear()
            pre_svc._scan_cached.clear()
            pre_mr.fetch_monthly_revenue.clear()

    def test_fin_trend_score_caller(self, world, monkeypatch, fc_clock):
        """L2 `compute_one_stock_trend`（個股 Tab／組合 Tab）：第一次與修前相同、沒有新例外外漏；FinMind 恢復後
        修前要等 6 小時，現在冷卻期過即拿到月營收。"""
        from src.compute.health.fin_trend_score import compute_one_stock_trend

        def _row():
            return compute_one_stock_trend(
                "2330", "202608", "tok", 0.65,
                fetch_financial_statements=lambda *a: pytest.fail("不該補抓財報"),
                analyze_financial_health=lambda *a, **k: pytest.fail("不該分析"),
                list_snapshots=lambda sid: ["202608"], load_snapshot=lambda sid, ym: None,
                save_snapshot=lambda *a: pytest.fail("不該存檔"))
        first = _row()
        assert "月營收抓取失敗" not in first["note"], "失敗走正常回傳（空表），不是例外"
        pre = _with_prefix_mr("caller_trend", monkeypatch, world)
        try:
            with monkeypatch.context() as mp:
                mp.setattr(MR, "fetch_monthly_revenue", pre.fetch_monthly_revenue)
                assert _row() == first, "第一次：與修前相同"
                world.fm_single = "ok"                                     # FinMind 恢復
                fc_clock["now"] += FAIL_COOLDOWN_SEC
                assert _row() == first, "修前：失敗凍 6 小時"
            after = _row()                                                 # 現行：冷卻期已過 → 重問 FinMind
        finally:
            pre.fetch_monthly_revenue.clear()
        assert after != first and after["mon_sub"] != first["mon_sub"], "現在：冷卻期過即重問 FinMind，月營收進得來"

    def test_shortage_cli_caller(self, world, monkeypatch):
        cli = _load_script("scripts/shortage_cli.py", "_d3e_shortage_cli")
        monkeypatch.setattr(cli, "fetch_quarterly_shortage_frame", lambda sid, quarters=12: _strong_frame())
        assert cli.fetch_monthly_revenue is MR.fetch_monthly_revenue
        got = cli.build_stock_input("2330")
        pre = _with_prefix_mr("caller_cli", monkeypatch, world)
        monkeypatch.setattr(cli, "fetch_monthly_revenue", pre.fetch_monthly_revenue)
        want = cli.build_stock_input("2330")
        assert got == want and got["revenue_yoy_last3"] == []

    @pytest.mark.parametrize("case", ["partial", "openapi_ok", "failed"])
    def test_export_stock_db_caller(self, world, monkeypatch, case):
        """匯出端拿到的表與修前逐字相同（半邊表照寫、沒有旗標 —— D2-f28，本批不處理）。"""
        E = _load_script("scripts/export_stock_db.py", "_d3e_export_stock_db")
        world.twse, world.tpex = {"partial": ("none", "ok"), "openapi_ok": ("ok", "ok"),
                                  "failed": ("none", "none")}[case]

        def _export():
            conn = sqlite3.connect(":memory:")
            n = E.write_monthly_revenue(conn, token="tok")
            rows = (pd.read_sql("select * from monthly_revenue", conn) if n >= 0 else None)
            conn.close()
            return n, rows
        got_n, got = _export()
        pre = _with_prefix_mr(f"caller_export_{case}", monkeypatch, world)
        monkeypatch.setattr(MR, "fetch_batch_monthly_revenue", pre.fetch_batch_monthly_revenue)
        want_n, want = _export()
        assert got_n == want_n and (got is None) == (want is None)
        if got is not None:
            pd.testing.assert_frame_equal(got, want)
        assert got_n == {"partial": 1, "openapi_ok": 3, "failed": -1}[case]

    @_NEEDS_PANDERA
    def test_export_stock_db_gets_finmind_history_d2f21(self, world):
        """D2-f21 的預期效果（方案層放行時才會發生）：匯出端拿到 FinMind 多檔歷史，不再只有 OpenAPI 單月快照。"""
        E = _load_script("scripts/export_stock_db.py", "_d3e_export_stock_db_f21")
        world.fm_batch = ("multi", 3)
        world.recover()
        conn = sqlite3.connect(":memory:")
        assert E.write_monthly_revenue(conn, token="tok") == 57
        conn.close()


# ══════════════════════════════════════════════════════════════════
# 修前 bug 重現：修前模型跑同一組共用檢查 → 轉紅
# ══════════════════════════════════════════════════════════════════
class TestPrefixReproducesBug:
    def test_d2f22_prefix_caches_single_failure(self, world, fc_clock, monkeypatch):
        pre = _with_prefix_mr("bug_f22", monkeypatch, world)
        try:
            with pytest.raises(AssertionError, match="冷卻期過的下一次即拿到新值"):
                _check_single_failure_backs_off_then_recovers(pre, world, fc_clock)
            assert world.calls["twse"] == 1, "修前：恢復＋過冷卻期仍 0 次上游（空表凍 6 小時）"
        finally:
            pre.fetch_monthly_revenue.clear()

    def test_d2f22_prefix_caches_own_market_failure(self, world, fc_clock, monkeypatch):
        pre = _with_prefix_mr("bug_f22_own", monkeypatch, world)
        try:
            with pytest.raises(AssertionError, match="冷卻期過的下一次即拿到新值"):
                _check_single_failure_backs_off_then_recovers(pre, world, fc_clock, sid="2330",
                                                              twse="none", tpex="ok")
        finally:
            pre.fetch_monthly_revenue.clear()

    def test_d2f23_prefix_caches_partial_l1(self, world, fc_clock, monkeypatch):
        pre = _with_prefix_mr("bug_f23", monkeypatch, world)
        try:
            with pytest.raises(AssertionError, match="冷卻期過的下一次即拿到兩邊"):
                _check_batch_partial_not_cached_then_recovers(pre, world, fc_clock)
        finally:
            pre.fetch_batch_monthly_revenue.clear()

    def test_d2f23_prefix_caches_partial_l3(self, sv, world, fc_clock, monkeypatch):
        """修前 L3（即使 L1 已修、已回報「確定失敗」）仍把半邊表的結果凍 1 天。"""
        pre_svc = _prefix_svc("bug_f23_l3")
        side2 = {"pool": 0, "qtr": 0, "mrev": 0}
        _install_svc(pre_svc, monkeypatch, {"pool": [], "qtr": "strong"}, side2)
        try:
            with pytest.raises(AssertionError, match="L3 沒有快取這一份"):
                _check_l3_partial_not_cached_then_recovers(pre_svc, world, side2, fc_clock)
            assert side2["pool"] == 1, "修前：後續呼叫連存活池都不再問（整份凍 1 天）"
        finally:
            pre_svc._scan_cached.clear()

    @_NEEDS_PANDERA
    @pytest.mark.parametrize("n", [2, 3, 50, 1800])
    def test_d2f21_prefix_discards_multi_stock_batch(self, world, monkeypatch, n):
        pre = _with_prefix_mr(f"bug_f21_{n}", monkeypatch, world)
        try:
            with pytest.raises(AssertionError, match="不再被整批丟棄"):
                _check_finmind_multi_stock_batch_kept(pre, world, n)
            assert world.calls["twse"] == 1, "修前：整批被丟 → 落到 OpenAPI 單月快照"
        finally:
            pre.fetch_batch_monthly_revenue.clear()

    def test_d2f25_prefix_fixed_cooldown(self, world, fc_clock, monkeypatch):
        pre = _with_prefix_mr("bug_f25", monkeypatch, world)
        try:
            with pytest.raises(AssertionError, match="D2-f25"):
                _check_batch_escalating_schedule(pre, world, fc_clock)
            assert world.calls["twse"] == len(_expected_hits(FAIL_COOLDOWN_SEC, FAIL_COOLDOWN_SEC, horizon=_LONG))
        finally:
            pre.fetch_batch_monthly_revenue.clear()


# ══════════════════════════════════════════════════════════════════
# 突變：逐一拿掉每一處修正 → 對應的共用檢查轉紅
# ══════════════════════════════════════════════════════════════════
def _mr_mutant(tag, monkeypatch, w, *pairs):
    m = _mutant(MR, *pairs, tag=tag)
    _install_mr(m, monkeypatch, w)
    return m


class TestMutations:
    # ── D2-f22 ──
    def test_m1_single_failure_cached_again(self, world, fc_clock, monkeypatch):
        m = _mr_mutant("m1", monkeypatch, world, (
            '            raise _SingleRevenueFetchFailed(pd.DataFrame(), "；".join(_failed))',
            "            return pd.DataFrame()"))
        try:
            with pytest.raises(AssertionError, match="冷卻期過的下一次即拿到新值"):
                _check_single_failure_backs_off_then_recovers(m, world, fc_clock)
        finally:
            m.fetch_monthly_revenue.clear()

    def test_m2_single_does_not_pass_failed(self, world, fc_clock, monkeypatch):
        m = _mr_mutant("m2", monkeypatch, world, ("    _batch = _batch_twse_openapi(failed=_failed)\n",
                                                  "    _batch = _batch_twse_openapi()\n"))
        try:
            with pytest.raises(AssertionError, match="冷卻期過的下一次即拿到新值"):
                _check_single_failure_backs_off_then_recovers(m, world, fc_clock, twse="none", tpex="ok")
        finally:
            m.fetch_monthly_revenue.clear()

    def test_m3_single_no_backoff(self, world, fc_clock, monkeypatch):
        m = _mr_mutant("m3", monkeypatch, world, ("        return _single_fail_cooldown.fail(_key, _gen, _sf.payload)",
                                                  "        return _sf.payload"))
        try:
            with pytest.raises(AssertionError, match="冷卻期內 0 次上游呼叫"):
                _check_single_failure_backs_off_then_recovers(m, world, fc_clock)
        finally:
            m.fetch_monthly_revenue.clear()

    def test_m4_single_success_does_not_bump_generation(self, world, fc_clock, monkeypatch):
        m = _mr_mutant("m4", monkeypatch, world, ("    _single_fail_cooldown.success(_key)\n", ""))
        try:
            with pytest.raises(AssertionError):
                _check_single_success_bumps_generation(m, world, fc_clock)
        finally:
            m.fetch_monthly_revenue.clear()

    def test_m5_single_clear_keeps_backoff(self, world, fc_clock, monkeypatch):
        m = _mr_mutant("m5", monkeypatch, world, ("    _single_fail_cooldown.clear()\n", "    pass\n"))
        try:
            with pytest.raises(AssertionError, match="清掉退避紀錄"):
                _check_single_clear_resets_both(m, world, fc_clock)
        finally:
            m._single_fail_cooldown.clear()
            m.fetch_monthly_revenue.clear()

    def test_m6_single_cooldown_key_ignores_months(self, world, fc_clock, monkeypatch):
        m = _mr_mutant("m6", monkeypatch, world, ("    _key = (stock_id, months)\n", "    _key = stock_id\n"))
        try:
            with pytest.raises(AssertionError):
                _check_single_cooldown_is_per_stock_and_months(m, world, fc_clock)
        finally:
            m.fetch_monthly_revenue.clear()

    def test_m7_single_classification_too_broad(self, world, fc_clock, monkeypatch):
        m = _mr_mutant("m7", monkeypatch, world, ("        if _failed:   # D2-f22", "        if True:   # D2-f22"))
        try:
            with pytest.raises(AssertionError, match="照舊入 6 小時快取"):
                _check_single_still_cached(m, world, fc_clock, sid="9999", twse="ok", tpex="ok")
        finally:
            m.fetch_monthly_revenue.clear()

    def test_m8_single_fixed_cooldown(self, world, fc_clock, monkeypatch):
        m = _mr_mutant("m8", monkeypatch, world, ("_single_fail_cooldown = _FailCooldown(max_seconds=TTL_1HOUR)",
                                                  "_single_fail_cooldown = _FailCooldown()"))
        try:
            with pytest.raises(AssertionError, match="單股冷卻與全市場同設定"):
                _check_single_escalating_schedule(m, world, fc_clock)
        finally:
            m.fetch_monthly_revenue.clear()

    # ── D2-f23 ──
    def test_m9_batch_partial_cached_again(self, world, fc_clock, monkeypatch):
        m = _mr_mutant("m9", monkeypatch, world, ("    if _failed:   # D2-f23", "    if _out.empty and _failed:   # D2-f23"))
        try:
            with pytest.raises(AssertionError, match="冷卻期過的下一次即拿到兩邊"):
                _check_batch_partial_not_cached_then_recovers(m, world, fc_clock)
        finally:
            m.fetch_batch_monthly_revenue.clear()

    def test_m10_scan_partial_cached_again(self, world, fc_clock, monkeypatch):
        m = _mutant(SVC, ("    if _batch_failed:   # D2-f23", "    if False:   # D2-f23"), tag="m10")
        side = {"pool": 0, "qtr": 0, "mrev": 0}
        _install_svc(m, monkeypatch, {"pool": [], "qtr": "strong"}, side)
        try:
            with pytest.raises(AssertionError, match="L3 沒有快取這一份"):
                _check_l3_partial_not_cached_then_recovers(m, world, side, fc_clock)
        finally:
            m._scan_cached.clear()

    # ── D2-f21 ──
    @_NEEDS_PANDERA
    def test_m11_sample_crosses_stocks_again(self, world, monkeypatch):
        m = _mr_mutant("m11", monkeypatch, world, ("            _sample_v = validate_or_reject(_sample, MonthlyRevenueSchema,",
                                                   "            _sample_v = validate_or_reject(_result_b.head(36), MonthlyRevenueSchema,"))
        try:
            with pytest.raises(AssertionError, match="不再被整批丟棄"):
                _check_finmind_multi_stock_batch_kept(m, world, 2)
        finally:
            m.fetch_batch_monthly_revenue.clear()

    def test_m17_sample_guard_removed(self, world, monkeypatch):
        m = _mr_mutant("m17", monkeypatch, world, ("            if not _sample.empty:   # D2-f21",
                                                   "            if True:   # D2-f21"))
        with pytest.raises(AssertionError, match="樣本取首檔前要先擋空表"):
            _check_all_rows_dropped_keeps_columns(m, world)

    # ── D2-f25 ──
    def test_m12_batch_fixed_cooldown(self, world, fc_clock, monkeypatch):
        m = _mr_mutant("m12", monkeypatch, world, ("_batch_fail_cooldown = _FailCooldown(max_seconds=TTL_1HOUR)",
                                                   "_batch_fail_cooldown = _FailCooldown()"))
        try:
            with pytest.raises(AssertionError, match="D2-f25"):
                _check_batch_escalating_schedule(m, world, fc_clock)
        finally:
            m.fetch_batch_monthly_revenue.clear()

    def test_m13_batch_cap_too_long(self, world, fc_clock, monkeypatch):
        m = _mr_mutant("m13", monkeypatch, world, ("_batch_fail_cooldown = _FailCooldown(max_seconds=TTL_1HOUR)",
                                                   "_batch_fail_cooldown = _FailCooldown(max_seconds=TTL_6HOUR)"))
        try:
            with pytest.raises(AssertionError, match="D2-f25"):
                _check_batch_escalating_schedule(m, world, fc_clock)
        finally:
            m.fetch_batch_monthly_revenue.clear()

    # ── D2-f26 與 L1 同型的 except ──
    def test_m14_run_scan_catches_any_cached_failure(self, world, monkeypatch):
        m = _mutant(SVC, ("    except _CandidatePoolFetchFailed as _cf:", "    except _CachedFailure as _cf:"), tag="m14")
        monkeypatch.setattr(FSS, "get_snapshot_coverage_note", lambda: _COVERAGE)
        with pytest.raises(pytest.fail.Exception, match="DID NOT RAISE"):
            _check_run_scan_catches_only_own_subclass(m, monkeypatch)

    def test_m15_single_catches_any_cached_failure(self, world, monkeypatch):
        m = _mr_mutant("m15", monkeypatch, world, ("    except _SingleRevenueFetchFailed as _sf:",
                                                   "    except _CachedFailure as _sf:"))
        with pytest.raises(pytest.fail.Exception, match="DID NOT RAISE"):
            _check_single_catches_only_own_subclass(m, monkeypatch)

    def test_m16_batch_catches_any_cached_failure(self, world, monkeypatch):
        m = _mr_mutant("m16", monkeypatch, world, ("    except _BatchRevenueFetchFailed as _bf:",
                                                   "    except _CachedFailure as _bf:"))
        with pytest.raises(pytest.fail.Exception, match="DID NOT RAISE"):
            _check_batch_catches_only_own_subclass(m, monkeypatch)
