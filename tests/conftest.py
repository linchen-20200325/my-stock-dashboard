"""
共用測試夾具 (Fixtures)
提供 bull_df / bear_df / short_df / minimal_df 等標準 OHLCV DataFrame。

v18.359 併入 root conftest._isolate_module_caches:
原 root 的 conftest.py 持有 module-level cache 清空 autouse fixture
(tw_macro `_ttl_cache` + macro_core `_FRED_CACHE` / `_YF_CLOSE_CACHE`),
防測試污染。原 root conftest 的覆蓋範圍僅限 root test_*.py;Phase 2 F-1.3
將 root test_*.py 全搬入 tests/ 後,該 fixture 必須隨之併入本檔覆蓋。
"""
import sys
import os

# 確保專案根目錄在 Python 路徑中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd

# v18.361 F-6.5 R5:在 conftest load 時(test_data_coverage 之前)捕捉真實 streamlit,
#   存 backup。
# v19.107 生命週期重整(CI slow lane 全滅根因):
#   舊制靠「stub 掛 `_stub` 記號 + 每 test 前後還原」,但三代 stub 記號不一致
#   (`_stub` / `_is_test_stub` / 無記號),classroom 的 `_is_test_stub` 永不被還原
#   → collection 期模組級 stub 卡住整個 run phase → slow lane 24 個 AppTest
#   全 skip(守衛偵測到 stub)+ test_screener_candidates 硬炸
#   「'streamlit' is not a package」。CI run 對照:main 8b071cb 同紅,非 PR 引入。
#   新制:
#   ① stub 檔各自用 module-scoped autouse fixture 管生命週期(裝 stub → 測完
#      還原 pristine + reload 被綁模組),不再模組級永久替換;
#   ② conftest 只留 pytest_collection_finish **身分還原**(identity check,
#      不認記號)作為未來漏網 stub 的 backstop — collection 一結束全域必乾淨;
#   ③ tests/test_zz_streamlit_pollution_lock.py(字母序最後)鎖 run phase 尾端
#      streamlit 仍為真 package — 未來任何測試內 stub 沒收尾,CI 直接紅。
try:
    import streamlit as _STREAMLIT_PRISTINE  # noqa: F401
except Exception:
    _STREAMLIT_PRISTINE = None


def reload_prefixed_modules(prefixes: tuple[str, ...]) -> None:
    """就地 reload 指定前綴的已載入模組(rebind 它們的 module-level `st`)。

    importlib.reload 是 in-place 重執行 → 既有引用(package `_SUBMODULES`
    tuple、`from x import fn` 拿到的函式所屬 globals)全部看到新綁定,
    不會產生「兩份模組」。供 stub fixture 在裝 stub 後/還原後各呼叫一次。
    """
    import importlib
    for _name in sorted(k for k in list(sys.modules)
                        if any(k == p or k.startswith(p + ".") for p in prefixes)):
        _mod = sys.modules.get(_name)
        if _mod is None or not hasattr(_mod, "__spec__") or _mod.__spec__ is None:
            continue
        try:
            importlib.reload(_mod)
        except Exception:
            pass  # smoke-allow-pass — 個別模組 reload 失敗不炸整個 fixture


#: 掃描哪些前綴的模組會持有 module-level `st` / `_st`。
#: 三層都要:L0 config 的 secrets bootstrap、L1 fetcher 的 @st.cache_data、L5 UI。
_ST_HOLDER_PREFIXES: tuple[str, ...] = ("src", "shared", "infra")

#: 模組層綁定 streamlit 的常見變數名(本專案兩種寫法都有)。
_ST_ATTR_NAMES: tuple[str, ...] = ("st", "_st")


def modules_bound_to(module_obj, prefixes: tuple[str, ...] = _ST_HOLDER_PREFIXES) -> list[str]:
    """回傳所有 module-level `st` / `_st` **指向 module_obj** 的已載入模組名。

    用途:stub fixture 收尾時,找出「在 stub 視窗內首次 import、因而永久綁著
    死 stub」的模組。這是 `sys.modules['streamlit']` 那一層鎖**看不到**的維度
    —— 它只檢查 sys.modules 有沒有還原,不檢查各模組手上那份引用。
    """
    out = []
    for _name in sorted(k for k in list(sys.modules)
                        if any(k == p or k.startswith(p + ".") for p in prefixes)):
        _mod = sys.modules.get(_name)
        if _mod is None:
            continue
        for _attr in _ST_ATTR_NAMES:
            if getattr(_mod, _attr, None) is module_obj:
                out.append(_name)
                break
    return out


def rebind_modules_bound_to(module_obj,
                            prefixes: tuple[str, ...] = _ST_HOLDER_PREFIXES) -> list[str]:
    """把持有 module_obj 的模組 reload 掉,讓它們重新綁定目前的 streamlit。

    比 `reload_prefixed_modules(("src",))` 精準得多:只動真的被污染的那幾個,
    不是無差別 reload 五百個模組(後者慢,且大圖 reload 有自己的身分風險)。
    回傳實際被 reload 的模組名,方便 fixture 在除錯時印出來。
    """
    import importlib
    _hit = modules_bound_to(module_obj, prefixes)
    _done: list[str] = []
    for _name in _hit:
        _mod = sys.modules.get(_name)
        if _mod is None or getattr(_mod, "__spec__", None) is None:
            continue
        try:
            importlib.reload(_mod)
        except Exception as _e:  # noqa: BLE001 — 個別模組 reload 失敗不該炸整個 fixture
            # §3.3:不吞例外。這裡不 raise 是因為單一模組 reload 失敗
            # **不影響其他模組解毒**,但一定要留痕 —— 沉默失敗會讓
            # zz 第四層守衛紅燈時查不出是哪個模組沒回來。
            print(f"[rebind_modules_bound_to] reload {_name} 失敗,該模組仍持有舊 stub:{_e!r}")
            continue
        _done.append(_name)
    return _done


def restore_pristine_streamlit() -> bool:
    """把 sys.modules['streamlit'] 換回 conftest 載入時捕捉的真身(身分比對,
    不認任何 stub 記號)。回傳是否有做置換。"""
    cur = sys.modules.get("streamlit")
    if _STREAMLIT_PRISTINE is not None and cur is not _STREAMLIT_PRISTINE:
        sys.modules["streamlit"] = _STREAMLIT_PRISTINE
        return True
    return False


def pytest_collection_finish(session):  # noqa: ARG001
    """collection(=全部 test 模組 import)結束 → 全域 streamlit 必須是真身。

    backstop:未來若有測試檔又在模組層裝 stub 忘了收,run phase 一開始就被
    這裡矯正,而非讓字母序在後的整批測試陪葬(v19.74 CI run #422 病史)。
    """
    restore_pristine_streamlit()


def _clear_module_caches() -> None:
    """清空 tw_macro / macro_core 的 module-level in-process 快取。

    防禦式實作:模組未 import / 屬性不存在皆靜默跳過,不讓 fixture 自身炸測試。
    正式執行(Streamlit Cloud)每個 session 自然有 TTL 失效 + 跨 session 隔離,
    故此污染**僅存在於測試環境**(同一 pytest process 內跨測試殘留)。
    """
    try:
        from src.data.macro import tw_macro
        for _name in dir(tw_macro):
            _fn = getattr(tw_macro, _name, None)
            _clear = getattr(_fn, "cache_clear", None)
            if callable(_clear):
                _clear()
    except Exception:
        pass

    try:
        from src.data.macro import macro_core
        for _name in dir(macro_core):
            if _name.endswith("_CACHE"):
                _obj = getattr(macro_core, _name, None)
                if isinstance(_obj, dict):
                    _obj.clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _isolate_module_caches():
    """每個測試前後清空 module-level 快取,杜絕跨測試污染。

    v19.107:移除舊的每-test streamlit 還原 — 它與 module-scoped stub fixture
    衝突(function fixture 跑在 module fixture 之內,會把該模組自己的 stub
    中途拔掉)。streamlit 生命週期改由 stub 檔自身 fixture + collection_finish
    backstop + zz 鎖尾測試三層負責(見檔頭 v19.107 註)。
    """
    _clear_module_caches()
    yield
    _clear_module_caches()


def _make_ohlcv(prices, atr_pct=0.01, volumes=None):
    """從收盤價列表建立最小 OHLCV DataFrame。
    high = close * (1 + atr_pct), low = close * (1 - atr_pct)
    """
    n = len(prices)
    return pd.DataFrame({
        "close":  [float(p) for p in prices],
        "open":   [float(p) for p in prices],
        "high":   [float(p) * (1 + atr_pct) for p in prices],
        "low":    [float(p) * (1 - atr_pct) for p in prices],
        "volume": volumes if volumes is not None else [1_000_000] * n,
    })


@pytest.fixture
def bull_df():
    """130 天穩定上漲序列（100→229）。所有 MA 趨勢條件均應成立。"""
    prices = [float(100 + i) for i in range(130)]
    return _make_ohlcv(prices, atr_pct=0.01)


@pytest.fixture
def bear_df():
    """130 天穩定下跌序列（229→100）。所有 MA 趨勢條件均不成立。"""
    prices = [float(229 - i) for i in range(130)]
    return _make_ohlcv(prices, atr_pct=0.01)


@pytest.fixture
def short_df():
    """59 天 DataFrame——不足以計算趨勢分數（需 >=60）。"""
    prices = [float(100 + i) for i in range(59)]
    return _make_ohlcv(prices)


@pytest.fixture
def minimal_df():
    """恰好 20 天 DataFrame——大多數評分函數的最小有效輸入。"""
    prices = [float(100 + i) for i in range(20)]
    return _make_ohlcv(prices)


@pytest.fixture
def synthetic_unwired_lamp():
    """把 `foreign_net` **在測試期間**合成為 `wired=False` 的燈，結束後原樣還原。

    為什麼需要（2026-09-27）：`foreign_net` 接線後，16 盞燈裡已**沒有**任何一盞
    `wired=False` —— 但「未接線」這一態的畫面 / 分母 / 側車防覆寫守衛仍是生產碼的
    契約（L0 日後可能再標一盞）。與其讓那些守衛變成空轉，改用合成 spec 驗。

    ⚠️ **原地**改 `shared.macro_buckets.SPECS_BY_KEY`（dict）與 `BUCKET_DANGER_SPECS`
    （list）—— 各模組 `from shared.macro_buckets import ...` 拿到的是同一個物件，
    所以一處改、處處生效；還原也是原地還原。回傳合成後的 spec。
    """
    import dataclasses
    from shared import macro_buckets as _mb
    _key = "foreign_net"
    _orig = _mb.SPECS_BY_KEY[_key]
    _idx = next(_i for _i, _s in enumerate(_mb.BUCKET_DANGER_SPECS) if _s.key == _key)
    _fake = dataclasses.replace(_orig, wired=False,
                                unwired_reason="（測試用合成未接線理由）")
    _mb.SPECS_BY_KEY[_key] = _fake
    _mb.BUCKET_DANGER_SPECS[_idx] = _fake
    try:
        yield _fake
    finally:
        _mb.SPECS_BY_KEY[_key] = _orig
        _mb.BUCKET_DANGER_SPECS[_idx] = _orig


@pytest.fixture
def stub_trading_day_status(monkeypatch):
    """批 Z59：「🚦 今天」狀態列「交易日」格**每一輪都讀** L3 → L1 證交所休市表（會對外連線）。

    整頁 render（含 AppTest）的測試用這個夾具把 L3 換成固定結果，fast lane ⛔ 不碰真實網路。
    ⚠️ **刻意不是 autouse**：全域 stub 會讓 `tests/test_d5_twse_holiday_calendar.py` 等直接測 L3／L1
    的測試失去施力點；需要的測試明文掛上（`@pytest.mark.usefixtures("stub_trading_day_status")`）。
    stub 打在 **L3**（`get_today_trading_status`），⛔ 不是頁面的 loader —— 頁面 loader 的
    late import 與例外處理照樣被走到。回傳那份固定結果（交易日，2026-09-04 週五）。
    """
    from datetime import date

    from src.services import trading_calendar_service as _tcs

    _fixed = _tcs.TradingDayStatus(today=date(2026, 9, 4), is_trading_day=True,
                                   next_trading_day=date(2026, 9, 7))
    monkeypatch.setattr(_tcs, "get_today_trading_status", lambda now=None: _fixed)
    return _fixed


#: 批 Z59 QA：證交所休市表端點的辨識字樣（今天頁狀態列「交易日」格每一輪都讀它）。
_LIVE_HOLIDAY_HOST = "openapi.twse.com.tw"
_LIVE_HOLIDAY_PATH = "holidaySchedule"


@pytest.fixture(autouse=True)
def _forbid_live_holiday_schedule():
    """守衛：任何測試**真的**去打證交所休市表（`openapi.twse.com.tw/v1/holidaySchedule/…`）⇒ 該測試失敗。

    ⚠️ 攔在 `requests.Session.request`：L1 `twse_holiday_fetcher._fetch_json` → `proxy_helper.fetch_url`
    的 proxy／降級直連兩段走 thread-local `Session.get`，NAS 中繼走 `requests.get`（內部也是
    `Session.request`，目標 URL 放在 `params={'url': …}`）—— 三段都經過這一層，故連 `params` 一起比。
    ⚠️ **只 raise 不夠**：`fetch_url` 與 `nas_relay_fetch` 會 `except Exception` 吞掉並回 None，
    頁面照樣畫出紅卡、測試照樣綠 ⇒ 另外記下來，在 teardown 用 `pytest.fail` 讓測試本身轉紅。
    ⚠️ 不影響：已用 `stub_trading_day_status`（stub 在 L3，根本不會走到 L1）、直接 patch
    `fetch_url`／`fetch_twse_holiday_calendar` 的測試、以及 127.0.0.1 黑洞測試（host 不符）。
    刻意不分 fast／slow lane：slow lane 同樣 ⛔ 不得依賴外網。
    ⚠️ **刻意不用 `monkeypatch` 夾具**：autouse 夾具若先要了 `monkeypatch`，那個（與測試共用的）
    實例會比測試模組自己的 autouse 夾具**更晚**拆除 ⇒ 模組夾具 teardown 時還看得到測試的 patch
    （實測 `test_d5_twse_holiday_calendar.py::_clear` 因此 AttributeError）。改成手動裝／還原。
    """
    import requests

    # ⚠️ L1 失敗後有 180 秒冷卻（冷卻期內不打上游、直接再拋）⇒ 同一個 pytest 行程裡只有**第一支**
    #    連網的測試會走到 requests 層被抓到，其餘的被冷卻遮住、照樣綠。每支測試開始前清掉
    #    L1 的快取與冷卻（只在模組已載入時；不為此 import 任何東西）。
    _hf = sys.modules.get("src.data.stock.twse_holiday_fetcher")
    _clear = getattr(getattr(_hf, "fetch_twse_holiday_calendar", None), "clear", None)
    if callable(_clear):
        _clear()

    _hits: list[str] = []
    _orig = requests.Session.request

    def _guarded(self, method, url, *args, **kwargs):
        _params = kwargs.get("params", args[0] if args else None)
        _blob = f"{url} {_params!r}"
        if _LIVE_HOLIDAY_HOST in _blob and _LIVE_HOLIDAY_PATH in _blob:
            _hits.append(f"{method} {url} params={_params!r}")
            raise RuntimeError(
                "測試不得連真實的證交所休市表 —— 請掛 `stub_trading_day_status` 夾具"
                "（tests/conftest.py）或 patch L1／L3")
        return _orig(self, method, url, *args, **kwargs)

    requests.Session.request = _guarded
    try:
        yield
    finally:
        requests.Session.request = _orig
    if _hits:
        pytest.fail("本測試對外連了證交所休市表（fast／slow lane 皆不得依賴外網）：\n  "
                    + "\n  ".join(_hits), pytrace=False)
