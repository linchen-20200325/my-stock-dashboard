# -*- coding: utf-8 -*-
"""tests/test_b4a_data_coverage_honesty.py — 🔎 資料診斷「覆蓋率表」誠實性回歸(B4-a)。

═══ 這批測試在守什麼 ═══════════════════════════════════════════════
實機事故:籌碼表的先行指標三欄連續 9 個交易日數值完全不變(凍結),
🔎 資料診斷頁照樣顯示「🟢 3/3 完整 / 🟢 當日」。逐條根因 → 逐條回歸:

D-1  覆蓋率只判 `is not None`:三大法人全敗時 orchestrator 依契約回 `{}`(空 dict),
     被算成「有值」。
D-1b `detect_frozen_columns` 零 caller —— 唯一能抓到「值凍結」的偵測器沒被接上。
D-1c 抓取失敗時 tab_macro 靜默沿用上一輪 li_latest,且那份 df 無任何旗標。
D-2  新鮮度量的是抓取時間 `_loaded_at`(datetime.now()),不是資料日期。
D-3  籌碼面覆蓋率算 cl_data、新鮮度卻取自 li_latest;cl_data['inst_date'] 從未被讀。
D-4  個股讀 `t2_data['date']`、ETF 讀 top-level `nav_date` —— 兩個 key 都不存在。
D-5  抓取失敗(t2_data 帶 err)長得跟成功一樣。

⚠️ 全部寫成**行為斷言**(建 state → 呼叫 compute_tab_coverage → 驗回傳燈號),
   不做原始碼字面掃描 —— 字面守衛照抄實作,實作錯了它也跟著錯。
   唯二的非行為斷言是:
     (a) `_MACRO_KEY_CADENCE` 必須涵蓋 `MACRO_INFO_KEYS`(資料一致性,非字面);
     (b) render 出來的 caption 文字(**使用者實際看到的輸出**,非原始碼)。
"""
from __future__ import annotations

import datetime as dt
import sys
import types

import pandas as pd
import pytest


# ══════════════════════════════════════════════════════════════════
# streamlit stub(沿用 tests/test_data_coverage.py 的生命週期收斂模式)
# ══════════════════════════════════════════════════════════════════
_CAPTURED: dict[str, list] = {"caption": [], "markdown": []}


def _stub_st():
    _existing = sys.modules.get("streamlit")
    if _existing is not None and getattr(_existing, "_b4a_stub", False):
        return
    m = types.ModuleType("streamlit")
    m._stub = True
    m._is_test_stub = True
    m._b4a_stub = True

    class _SS(dict):
        def get(self, k, d=None):
            return super().get(k, d)
    m.session_state = _SS()

    def _noop(*a, **k):
        return None

    def _rec(name):
        def _f(*a, **k):
            if a:
                _CAPTURED.setdefault(name, []).append(str(a[0]))
            return None
        return _f

    for n in ("divider", "expander", "error", "plotly_chart", "warning", "info",
              "title", "header", "subheader", "write", "code", "metric",
              "dataframe", "table", "button", "text_input", "selectbox",
              "multiselect", "slider", "checkbox", "radio", "columns",
              "container", "spinner", "progress", "tabs", "sidebar", "image",
              "json", "altair_chart", "bar_chart", "line_chart", "area_chart",
              "pyplot", "graphviz_chart", "form", "form_submit_button", "empty",
              "rerun", "experimental_rerun"):
        setattr(m, n, _noop)
    m.caption = _rec("caption")
    m.markdown = _rec("markdown")

    def _cache_data(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f
    m.cache_data = _cache_data
    m.cache_resource = _cache_data
    m.secrets = {}

    sys.modules["streamlit"] = m


def _reload_pages_modules() -> None:
    import importlib
    for _name in sorted(k for k in list(sys.modules)
                        if k == "src.ui.pages" or k.startswith("src.ui.pages.")):
        _mod = sys.modules.get(_name)
        if _mod is None:
            continue
        try:
            importlib.reload(_mod)
        except Exception:
            pass  # smoke-allow-pass — 個別 reload 失敗不炸 fixture


@pytest.fixture(autouse=True, scope="module")
def _scoped_streamlit_stub():
    from tests.conftest import rebind_modules_bound_to

    # ① 裝 stub **之前**先在真 streamlit 下 import 目標。`src/ui/pages/__init__.py`
    #    是 eager barrel,一次拉進全部 7 個子模組及其相依;若那發生在 stub 視窗內,
    #    那批模組的 module-level `st` 會**永久**綁在待丟棄的 stub 上(實測 8 個)。
    #    先行 import 讓視窗內不再有任何「首次 import」。
    import src.ui.pages  # noqa: F401 — 只為觸發 import,不取用符號

    _saved = sys.modules.get("streamlit")
    _stub_st()
    _stub = sys.modules["streamlit"]
    _reload_pages_modules()
    yield
    if _saved is not None:
        sys.modules["streamlit"] = _saved
    else:
        sys.modules.pop("streamlit", None)
    _reload_pages_modules()
    # ② 補漏:`_reload_pages_modules` 只掃 src.ui.pages.*,視窗內被連帶
    #    首次 import 的其他模組(src.data.* 等)它看不到。這行針對性補齊。
    rebind_modules_bound_to(_stub)


# ══════════════════════════════════════════════════════════════════
# 共用 fixture / helper
# ══════════════════════════════════════════════════════════════════
def _cover(state):
    from src.ui.pages import compute_tab_coverage
    return compute_tab_coverage(state=state)


def _row(rows, needle):
    return next(r for r in rows if needle in r["tab"])


def _exp_day() -> dt.date:
    """預期最新交易日 —— 測試日期全部相對它推,避免週末/假日造成不穩定。"""
    from shared.staleness import expected_latest_trading_day
    return expected_latest_trading_day()


def _behind(days: int) -> dt.date:
    return _exp_day() - dt.timedelta(days=days)


def _li_frame(*, frozen_cols=(), n=8, frozen_tail=None) -> pd.DataFrame:
    """造一份 li_latest 形狀的 DataFrame(列序:由舊到新,同 production)。

    frozen_cols 內的欄位灌常數 → 一階差分恆 0 = 凍結;其餘監看欄每列都不同。
    frozen_tail 給值時,只有**最後 N 列**(最新的 N 天)是常數,更早的仍在動 ——
    用來驗證「尾端 N 期」是依日期而非依物理列序判定的。
    `_date` 為 YYYYMMDD 字串,同 production 的 build_leading_fast。
    """
    from src.ui.pages.data_coverage import _LI_FROZEN_WATCH_COLS
    _dates = [_behind(n - 1 - i) for i in range(n)]
    _df = pd.DataFrame({"_date": [d.strftime("%Y%m%d") for d in _dates]})
    for _i, _c in enumerate(_LI_FROZEN_WATCH_COLS):
        if _c not in frozen_cols:
            _df[_c] = [100 + _i * 7 + _j * 13 for _j in range(n)]
        elif frozen_tail:
            _df[_c] = ([200 + _j * 11 for _j in range(n - frozen_tail)]
                       + [12345] * frozen_tail)
        else:
            _df[_c] = [12345] * n
    return _df


def _adl_frame(lag_days: int = 0, n: int = 5) -> pd.DataFrame:
    _dates = [_behind(lag_days + n - 1 - i) for i in range(n)]
    return pd.DataFrame({"date": pd.to_datetime(_dates),
                         "up": range(n), "down": range(n)})


def _price_frame(lag_days: int = 0, n: int = 5) -> pd.DataFrame:
    _dates = [_behind(lag_days + n - 1 - i) for i in range(n)]
    return pd.DataFrame({"date": pd.to_datetime(_dates),
                         "close": [10.0 + i for i in range(n)]})


def _full_chip_state(**over):
    """一份「三源俱全 + 資料日皆為當期」的籌碼 state,測試各自覆寫。"""
    _s = {
        "cl_data": {
            "inst": {"外資及陸資": {"net": 1.0}, "投信": {"net": 2.0}},
            "inst_date": _exp_day().strftime("%Y%m%d"),
            "margin": 3400.0,
            "adl": _adl_frame(0),
        },
        "li_latest": _li_frame(),
    }
    _s.update(over)
    return _s


# ══════════════════════════════════════════════════════════════════
# D-1 —— 「有值」不等於 `is not None`
# ══════════════════════════════════════════════════════════════════
class TestD1EmptyContainerIsNotAValue:
    def test_inst_empty_dict_is_not_counted(self):
        """實機根因:三大法人全敗時 orchestrator 回 `{}`(非 None)。

        舊碼 `_cl.get('inst') is not None` → True → 3/3 🟢「完整」。
        修正後空 dict 必須算沒值 → 2/3 🟡。
        """
        rows = _cover(_full_chip_state(cl_data={
            "inst": {},                       # ← 抓取全失敗的真實形狀
            "inst_date": _exp_day().strftime("%Y%m%d"),
            "margin": 3400.0,
            "adl": _adl_frame(0),
        }))
        chip = _row(rows, "籌碼")
        assert chip["ratio_txt"] == "2/3", f"空 dict 被當成有值:{chip['ratio_txt']}"
        assert chip["emoji"] != "🟢", "三大法人整組沒抓到,不得亮綠燈"

    def test_all_empty_containers_go_red(self):
        rows = _cover({"cl_data": {"inst": {}, "margin": None,
                                   "adl": pd.DataFrame()}})
        chip = _row(rows, "籌碼")
        assert chip["ratio_txt"] == "0/3"
        assert chip["emoji"] == "🔴"

    def test_macro_block_with_only_err_is_not_a_value(self):
        """fetcher 失敗常回 `{'_err':..., 'current': None}` —— 非空 dict 但沒數值。"""
        from shared.macro_buckets import MACRO_INFO_KEYS
        _mi = {k: {"_err": "5 源全失敗", "current": None} for k in MACRO_INFO_KEYS}
        _mi["_loaded_at"] = "2026-08-06 10:00:00"
        macro = _row(_cover({"macro_info": _mi}), "總經")
        assert macro["emoji"] == "🔴", "全部 fetcher 失敗卻不是紅燈"
        assert macro["ratio_txt"].startswith("0/")

    def test_zero_is_still_a_value(self):
        """0 是真實觀測值,不得被當成缺值(否則會把真實的 0 洗成『沒抓到』)。"""
        from src.ui.pages.data_coverage import _has_value
        assert _has_value(0) is True
        assert _has_value(0.0) is True
        assert _has_value(float("nan")) is False
        assert _has_value({}) is False
        assert _has_value([]) is False
        assert _has_value(pd.DataFrame()) is False
        assert _has_value(None) is False


# ══════════════════════════════════════════════════════════════════
# D-1b —— 值凍結必須被偵測(接上零 caller 的 detect_frozen_columns)
# ══════════════════════════════════════════════════════════════════
class TestD1bFrozenDetection:
    _AUDIT_COLS = ("前五大留倉", "前十大留倉", "未平倉口數")

    def test_frozen_series_is_detected_and_downgrades(self):
        """事故現場重演:三欄連續不變,但覆蓋率 3/3、資料日期全新。

        → 覆蓋率燈與新鮮度燈都必須從 🟢 降到 🟡,細項要點名是哪幾欄。
        """
        rows = _cover(_full_chip_state(
            li_latest=_li_frame(frozen_cols=self._AUDIT_COLS)))
        chip = _row(rows, "籌碼")
        assert chip["ratio_txt"] == "3/3", "前提:覆蓋率本來就是滿的"
        assert chip["emoji"] == "🟡", f"凍結卻沒降級:{chip['emoji']}"
        assert chip["fresh_emoji"] == "🟡", "新鮮度燈也必須降級"
        assert "🧊" in chip["detail"], "細項沒有凍結標記"
        for _c in self._AUDIT_COLS:
            assert _c in chip["detail"], f"凍結欄位 {_c} 沒被點名"

    def test_healthy_series_stays_green(self):
        """反向:值天天在動 + 資料日當期 → 不得亮黃燈(否則就是假警報)。"""
        chip = _row(_cover(_full_chip_state()), "籌碼")
        assert chip["emoji"] == "🟢", f"健康資料被誤降級:{chip['detail']}"
        assert "🧊" not in chip["detail"]

    def test_all_nan_column_is_missing_not_frozen(self):
        """全 NaN(FinMind 免費版無此資料)= 缺失,**不是**凍結。

        §1:不確定 ≠ 凍結。缺失由覆蓋率負責,不得被包裝成「穩定」也不得誤報凍結。
        """
        _li = _li_frame()
        for _c in self._AUDIT_COLS:
            _li[_c] = None
        chip = _row(_cover(_full_chip_state(li_latest=_li)), "籌碼")
        assert "🧊" not in chip["detail"], "全 NaN 被誤判成凍結"

    def test_frozen_detection_sorts_by_date_first(self):
        """尾端 N 期必須依 `_date` 判定,不是依物理列序。

        造一份「最新 4 天才凍結、更早在動」的資料,再把列序反轉(新→舊)。
        - 直接餵給偵測器(不排序)→ 物理尾端是最舊的 3 列,它們還在動 → 抓不到;
        - 走 compute_tab_coverage(內部先依 `_date` 排序)→ 必須抓到。
        兩段一起斷言,證明「有排序」這件事是必要的而非碰巧通過。
        """
        from shared.data_freshness import detect_frozen_columns, frozen_summary
        from src.ui.pages.data_coverage import (
            _LI_FROZEN_STALE_PERIODS, _LI_FROZEN_WATCH_COLS,
        )
        _asc = _li_frame(frozen_cols=self._AUDIT_COLS, n=8, frozen_tail=4)
        _desc = _asc.iloc[::-1].reset_index(drop=True)     # 新 → 舊

        _n_unsorted, _ = frozen_summary(detect_frozen_columns(
            _desc, _LI_FROZEN_WATCH_COLS,
            stale_periods=_LI_FROZEN_STALE_PERIODS))
        assert _n_unsorted == 0, "前提不成立:未排序時本來就該抓不到"

        chip = _row(_cover(_full_chip_state(li_latest=_desc)), "籌碼")
        assert "🧊" in chip["detail"], "亂序輸入下凍結偵測失效(內部沒依 _date 排序)"
        for _c in self._AUDIT_COLS:
            assert _c in chip["detail"]

    def test_non_dataframe_li_does_not_raise(self):
        """li_latest 型別不符時只能靜靜跳過,不得炸掉整個診斷頁。"""
        for _bad in ({"v": 1}, [1, 2, 3], "oops", None):
            rows = _cover(_full_chip_state(li_latest=_bad))
            assert len(rows) == 4


# ══════════════════════════════════════════════════════════════════
# D-1c —— 「本輪沒抓到,沿用上輪」必須看得見
# ══════════════════════════════════════════════════════════════════
class TestD1cRetainedStaleData:
    def test_retain_meta_downgrades_chip_row(self):
        rows = _cover(_full_chip_state(
            li_retain_meta={"rounds": 3, "since": "2026-08-01 09:00:00"}))
        chip = _row(rows, "籌碼")
        assert chip["emoji"] == "🟡", "連續 3 輪抓取失敗卻仍亮綠燈"
        assert "♻️" in chip["detail"]
        assert "3" in chip["detail"]

    def test_stale_pickle_flag_column_downgrades(self):
        """走 stale pickle fallback(欄位版旗標)也必須降級。"""
        _li = _li_frame()
        _li["_is_stale"] = True
        _li["_stale_age_min"] = 4000.0
        chip = _row(_cover(_full_chip_state(li_latest=_li)), "籌碼")
        assert chip["emoji"] == "🟡"
        assert "📦" in chip["detail"]

    def test_no_retain_meta_no_downgrade(self):
        chip = _row(_cover(_full_chip_state(li_retain_meta={})), "籌碼")
        assert chip["emoji"] == "🟢"
        assert "♻️" not in chip["detail"]


# ══════════════════════════════════════════════════════════════════
# D-2 —— 新鮮度量「資料日期」,不是「抓取時間」
# ══════════════════════════════════════════════════════════════════
class TestD2FreshnessUsesAsOfNotFetchTime:
    @staticmethod
    def _macro_state(*, block_date, loaded_at, key="vix"):
        return {"macro_info": {
            key: {"current": 18.2, "date": block_date.strftime("%Y-%m-%d")},
            "_loaded_at": loaded_at,
        }}

    def test_old_data_fetched_now_is_not_fresh(self):
        """剛剛抓回來的一筆 60 天前資料 —— 舊碼顯示「🟢 當日」。"""
        _now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        macro = _row(_cover(self._macro_state(
            block_date=_behind(60), loaded_at=_now)), "總經")
        assert macro["fresh_emoji"] == "🔴", (
            f"60 天前的日頻資料被判成 {macro['fresh_emoji']} {macro['fresh_label']}")
        assert "60" in macro["fresh_label"]

    def test_fetch_time_does_not_change_the_light(self):
        """property:同一份資料日期,`_loaded_at` 怎麼變燈號都不能變。"""
        _d = _behind(60)
        _lights = {
            _row(_cover(self._macro_state(block_date=_d, loaded_at=_lt)),
                 "總經")["fresh_emoji"]
            for _lt in ("2020-01-01 00:00:00",
                        dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "")
        }
        assert len(_lights) == 1, f"抓取時間影響了新鮮度燈號:{_lights}"

    def test_current_data_is_green(self):
        macro = _row(_cover(self._macro_state(
            block_date=_exp_day(), loaded_at="2026-08-06 10:00:00")), "總經")
        assert macro["fresh_emoji"] == "🟢"

    def test_monthly_indicator_is_not_judged_by_daily_threshold(self):
        """月頻(CPI)as_of 天生就是上個月 —— 用日頻 7 日門檻量它會永遠紅燈。"""
        _30d = {"macro_info": {
            "us_core_cpi": {"yoy": 3.1, "date": _behind(30).strftime("%Y-%m-%d")},
            "_loaded_at": "2026-08-06 10:00:00"}}
        assert _row(_cover(_30d), "總經")["fresh_emoji"] == "🟢"
        _90d = {"macro_info": {
            "us_core_cpi": {"yoy": 3.1, "date": _behind(90).strftime("%Y-%m-%d")},
            "_loaded_at": "2026-08-06 10:00:00"}}
        assert _row(_cover(_90d), "總經")["fresh_emoji"] == "🔴"

    def test_worst_source_drives_the_light(self):
        """多指標時取最差者,不得被其他新鮮的指標平均掉(§1)。"""
        _s = {"macro_info": {
            "vix": {"current": 18.0, "date": _exp_day().strftime("%Y-%m-%d")},
            "us_core_cpi": {"yoy": 3.1, "date": _behind(400).strftime("%Y-%m-%d")},
            "_loaded_at": "2026-08-06 10:00:00"}}
        macro = _row(_cover(_s), "總經")
        assert macro["fresh_emoji"] == "🔴"
        assert "us_core_cpi" in macro["fresh_label"]

    def test_loaded_at_shown_but_labelled_as_fetch_time(self):
        """`_loaded_at` 仍可顯示,但必須標明是抓取時刻而非資料日期。"""
        macro = _row(_cover(self._macro_state(
            block_date=_exp_day(), loaded_at="2026-08-06 10:11:12")), "總經")
        assert "抓取" in macro["detail"]
        assert "≠ 資料日期" in macro["detail"]


# ══════════════════════════════════════════════════════════════════
# D-3 —— 籌碼面新鮮度量的是 cl_data 自己的 as-of
# ══════════════════════════════════════════════════════════════════
class TestD3ChipFreshnessUsesInstDate:
    def test_inst_date_is_actually_read(self):
        """`cl_data['inst_date']` 早就存在,舊碼從未讀過它。

        法人資料 9 天沒更新、其餘全新 → 整列新鮮度必須被拉紅。
        """
        rows = _cover(_full_chip_state(cl_data={
            "inst": {"外資及陸資": {"net": 1.0}},
            "inst_date": _behind(9).strftime("%Y%m%d"),
            "margin": 3400.0,
            "adl": _adl_frame(0),
        }))
        chip = _row(rows, "籌碼")
        assert chip["fresh_emoji"] == "🔴", (
            f"inst_date 落後 9 日卻是 {chip['fresh_emoji']}")
        assert "法人" in chip["fresh_label"]

    def test_adl_date_also_participates(self):
        rows = _cover(_full_chip_state(cl_data={
            "inst": {"外資及陸資": {"net": 1.0}},
            "inst_date": _exp_day().strftime("%Y%m%d"),
            "margin": 3400.0,
            "adl": _adl_frame(30),
        }))
        chip = _row(rows, "籌碼")
        assert chip["fresh_emoji"] == "🔴"
        assert "廣度" in chip["fresh_label"]

    def test_coverage_and_freshness_are_independent_axes(self):
        """覆蓋率滿分 + 新鮮度過期 —— 兩欄必須分別呈現,不得互相蓋掉。"""
        chip = _row(_cover(_full_chip_state(cl_data={
            "inst": {"外資及陸資": {"net": 1.0}},
            "inst_date": _behind(20).strftime("%Y%m%d"),
            "margin": 3400.0,
            "adl": _adl_frame(0),
        })), "籌碼")
        assert chip["ratio_txt"] == "3/3"      # 有值率仍是滿的
        assert chip["fresh_emoji"] == "🔴"      # 但值是舊的


# ══════════════════════════════════════════════════════════════════
# D-4 —— 接錯 key 的迴歸(個股 / ETF)
# ══════════════════════════════════════════════════════════════════
class TestD4WiredKeys:
    def test_stock_asof_comes_from_price_df(self):
        """舊碼讀 `t2_data['date']`(不存在)→ 永遠 ⬜。真正的 as-of 在 df.date。"""
        stock = _row(_cover({"t2_data": {
            "sid": "2330", "df": _price_frame(0), "err": None}}), "個股")
        assert stock["fresh_emoji"] == "🟢", (
            f"接對 key 後仍是 {stock['fresh_emoji']} {stock['fresh_label']}")
        assert stock["fresh_asof"], "應顯示資料日"

    def test_stock_stale_price_series_turns_red(self):
        stock = _row(_cover({"t2_data": {
            "sid": "2330", "df": _price_frame(30), "err": None}}), "個股")
        assert stock["fresh_emoji"] == "🔴"

    def test_etf_nav_date_is_nested_under_premium(self):
        """舊碼讀 top-level `nav_date`,實際巢狀在 `premium` 內 → 永遠 ⬜。"""
        etf = _row(_cover({"etf_single_data": {
            "ticker": "0050.TW",
            "premium": {"nav": 104.0, "price": 104.1,
                        "nav_date": _exp_day()},
        }}), "ETF")
        assert etf["fresh_emoji"] == "🟢", (
            f"nested nav_date 沒被讀到:{etf['fresh_emoji']} {etf['fresh_label']}")

    def test_etf_stale_nav_turns_red(self):
        etf = _row(_cover({"etf_single_data": {
            "ticker": "0050.TW",
            "premium": {"nav": 104.0, "nav_date": _behind(20)},
        }}), "ETF")
        assert etf["fresh_emoji"] == "🔴"

    def test_etf_falls_back_to_price_index(self):
        """premium 三個日期都沒有時退用價格序列 index,不該直接放棄。"""
        _pdf = _price_frame(0).set_index("date")
        etf = _row(_cover({"etf_single_data": {
            "ticker": "0050.TW", "price_df": _pdf}}), "ETF")
        assert etf["fresh_emoji"] == "🟢"

    def test_unknown_is_distinguishable_from_not_loaded(self):
        """關鍵:接對 key 之後若仍拿不到日期,⬜ 是正確的 ——

        但必須分得出「真的沒觸發」和「容器有值卻取不到 as-of(多半是 key 接錯)」,
        否則下一次 mis-wire 又會被誤讀成「使用者還沒查」。
        """
        _not_loaded = _row(_cover({}), "個股")
        assert _not_loaded["fresh_emoji"] == "⬜"
        assert _not_loaded["fresh_label"] == "未載入"

        _no_date = _row(_cover({"t2_data": {
            "sid": "2330", "df": pd.DataFrame({"close": [1.0, 2.0]})}}), "個股")
        assert _no_date["fresh_emoji"] == "⬜"
        assert _no_date["fresh_label"] == "無資料日期"
        assert _no_date["fresh_label"] != _not_loaded["fresh_label"], (
            "『沒觸發』與『取不到日期』顯示成同一種 ⬜ —— 接錯 key 會再次隱形")


# ══════════════════════════════════════════════════════════════════
# D-5 —— 抓取失敗不得顯示綠燈
# ══════════════════════════════════════════════════════════════════
class TestD5FetchFailureIsVisible:
    def test_error_token_forces_red(self):
        """tab_stock 無條件寫 t2_data(含 err);舊碼 dict 非空 → 🟢「已載入」。"""
        stock = _row(_cover({"t2_data": {
            "sid": "2330", "name": "台積電", "df": None,
            "err": "FinMind 429 Too Many Requests",
            "rsi": None, "health": None,
        }}), "個股")
        assert stock["emoji"] == "🔴", f"抓取失敗卻顯示 {stock['emoji']}"
        assert stock["emoji"] != "🟢"
        assert "429" in stock["detail"], "錯誤原文沒被顯示出來"
        assert "已載入" not in stock["detail"]

    def test_empty_price_frame_is_not_green(self):
        """沒有 err 但價格序列是空的 —— 技術指標全算不出來,一樣不是綠燈。"""
        stock = _row(_cover({"t2_data": {
            "sid": "2330", "df": pd.DataFrame(), "err": None}}), "個股")
        assert stock["emoji"] == "🔴"

    def test_successful_fetch_still_green(self):
        stock = _row(_cover({"t2_data": {
            "sid": "2330", "df": _price_frame(0), "err": None}}), "個股")
        assert stock["emoji"] == "🟢"
        assert stock["ratio_txt"] == "已查"

    def test_etf_nav_failure_downgrades(self):
        """NAV 全源失敗 = 折溢價整段不可信(v18.442 假折溢價事故入口)。"""
        etf = _row(_cover({"etf_single_data": {
            "ticker": "0050.TW", "price_df": _price_frame(0).set_index("date"),
            "_err_nav": "FinMind + goodinfo + TWSE + MoneyDJ + yfinance 5 源全失敗",
        }}), "ETF")
        assert etf["emoji"] == "🟡", f"NAV 全敗卻是 {etf['emoji']}"
        assert "NAV" in etf["detail"]


# ══════════════════════════════════════════════════════════════════
# 門檻收斂 —— 燈號規則走 SSOT,不再 inline
# ══════════════════════════════════════════════════════════════════
class TestThresholdSSOT:
    def test_daily_red_threshold_tracks_ssot(self):
        """紅燈起點必須跟著 `shared.staleness.STALE_DAYS_DAILY` 走(不寫死 7)。

        ⚠️ 預設 `warn_days=None` 是**刻意的兩態**（見 `freshness_level_for_cadence`
        docstring：「與紅燈同門檻，等於沒有黃燈帶」）—— 門檻當日仍是 🟢「在窗內」，
        隔一天才 🔴「已逾窗」。黃燈帶是**診斷頁自己傳 `warn_days` 才有的**，
        不是函式預設（本 class 的 `test_weekend_lag_is_not_a_false_alarm` 測那條路徑）。
        本測試只釘「紅燈起點 = SSOT + 1」，不對中間色過度指定 ——
        原本此處斷言 🟡 與下方月頻那條（同預設、斷言 🟢）自相矛盾。
        """
        from shared.data_freshness import freshness_level_for_cadence
        from shared.staleness import STALE_DAYS_DAILY
        assert freshness_level_for_cadence(STALE_DAYS_DAILY, "daily")[0] != "🔴"
        assert freshness_level_for_cadence(STALE_DAYS_DAILY + 1, "daily")[0] == "🔴"

    def test_daily_yellow_band_is_opt_in_via_warn_days(self):
        """診斷頁的三態（🟢≤3 / 🟡4~7 / 🔴≥8）必須靠顯式 `warn_days` 取得。"""
        from shared.data_freshness import freshness_level_for_cadence
        from shared.staleness import STALE_DAYS_DAILY
        from src.ui.pages.data_coverage import _DIAG_DAILY_WARN_DAYS
        _f = lambda d: freshness_level_for_cadence(  # noqa: E731
            d, "daily", warn_days=_DIAG_DAILY_WARN_DAYS)[0]
        assert _f(_DIAG_DAILY_WARN_DAYS) == "🟢"
        assert _f(_DIAG_DAILY_WARN_DAYS + 1) == "🟡"
        assert _f(STALE_DAYS_DAILY) == "🟡"
        assert _f(STALE_DAYS_DAILY + 1) == "🔴"

    def test_monthly_and_quarterly_track_ssot(self):
        from shared.data_freshness import freshness_level_for_cadence
        from shared.staleness import STALE_DAYS_MONTHLY, STALE_DAYS_QUARTERLY
        assert freshness_level_for_cadence(STALE_DAYS_MONTHLY, "monthly")[0] == "🟢"
        assert freshness_level_for_cadence(STALE_DAYS_MONTHLY + 1, "monthly")[0] == "🔴"
        assert freshness_level_for_cadence(STALE_DAYS_QUARTERLY, "quarterly")[0] == "🟢"

    def test_unknown_cadence_falls_back_to_strictest(self):
        from shared.data_freshness import freshness_level_for_cadence
        from shared.staleness import STALE_DAYS_DAILY
        assert (freshness_level_for_cadence(STALE_DAYS_DAILY + 1, "made-up")[0]
                == "🔴")

    def test_weekend_lag_is_not_a_false_alarm(self):
        """週五資料在週一被讀到 = lag 3 日曆天,屬正常 → 不得亮黃燈。

        舊門檻 warn=1 會讓每個週一早上整頁假黃燈、週二假紅燈。
        """
        from src.ui.pages.data_coverage import _DIAG_DAILY_WARN_DAYS
        from shared.data_freshness import freshness_level_for_cadence
        assert _DIAG_DAILY_WARN_DAYS >= 3, "黃燈起點必須容得下一個完整週末"
        assert freshness_level_for_cadence(
            3, "daily", warn_days=_DIAG_DAILY_WARN_DAYS)[0] == "🟢"

    def test_green_label_never_claims_zero_lag(self):
        """燈號寬容是設計選擇;把「落後 3 日」寫成「當日」是說謊(§1)。"""
        from shared.data_freshness import freshness_level
        _e0, _l0 = freshness_level(0, warn=3, bad=7)
        assert (_e0, _l0) == ("🟢", "最新")
        _e3, _l3 = freshness_level(3, warn=3, bad=7)
        assert _e3 == "🟢"
        assert "3" in _l3 and "當日" not in _l3 and "最新" not in _l3

    def test_warn_cannot_exceed_bad(self):
        """呼叫端設出「黃燈比紅燈寬」的矛盾組合時要被夾住,不得產生怪燈號。"""
        from shared.data_freshness import freshness_level_for_cadence
        from shared.staleness import STALE_DAYS_DAILY
        assert freshness_level_for_cadence(
            STALE_DAYS_DAILY + 5, "daily", warn_days=999)[0] == "🔴"

    def test_none_lag_is_unknown_not_fresh(self):
        from shared.data_freshness import freshness_level_for_cadence
        assert freshness_level_for_cadence(None, "daily") == ("⬜", "未知")

    def test_every_macro_key_has_a_declared_cadence(self):
        """漂移守衛:新增 MACRO_INFO_KEYS 卻忘了登記頻率 → 會被套最嚴的日頻門檻,
        月頻指標就會永遠紅燈。這裡直接擋下。"""
        from shared.macro_buckets import MACRO_INFO_KEYS
        from src.ui.pages.data_coverage import _MACRO_KEY_CADENCE
        _missing = [k for k in MACRO_INFO_KEYS if k not in _MACRO_KEY_CADENCE]
        assert not _missing, f"這些 macro key 未登記發布頻率:{_missing}"

    def test_colors_come_from_shared_ssot(self):
        """色票走 shared.colors,不得再有第二份 hex 複本。"""
        from shared.colors import emoji_to_hex
        for r in _cover(_full_chip_state()):
            assert r["color"] == emoji_to_hex(r["emoji"])
            assert r["fresh_color"] == emoji_to_hex(r["fresh_emoji"])


# ══════════════════════════════════════════════════════════════════
# 使用者實際看到的文字(輸出斷言,非原始碼掃描)
# ══════════════════════════════════════════════════════════════════
class TestRenderedWording:
    def test_summary_says_has_value_not_complete(self):
        """「完整」名不副實 —— 那個燈從頭到尾只檢查了「欄位不是空的」。"""
        from src.ui.pages import render_data_coverage
        _CAPTURED["caption"].clear()
        render_data_coverage()
        _txt = "\n".join(_CAPTURED["caption"])
        assert _txt, "render 沒有輸出任何 caption"
        assert "完整" not in _txt, f"摘要仍自稱『完整』:{_txt}"
        assert "有值" in _txt

    def test_render_does_not_raise_on_empty_state(self):
        from src.ui.pages import render_data_coverage
        render_data_coverage()


# ══════════════════════════════════════════════════════════════════
# 邊界(§6 自審清單:空集 / 單筆 / 全空值)
# ══════════════════════════════════════════════════════════════════
class TestEdgeCases:
    def test_empty_state_is_all_idle(self):
        rows = _cover({})
        assert len(rows) == 4
        assert all(r["emoji"] == "⬜" for r in rows)
        assert all(r["fresh_emoji"] == "⬜" for r in rows)

    def test_single_row_li_does_not_claim_frozen(self):
        """單筆:有效 diff 數不足 → 不下凍結結論(樣本不足 ≠ 凍結)。"""
        chip = _row(_cover(_full_chip_state(li_latest=_li_frame(n=1))), "籌碼")
        assert "🧊" not in chip["detail"]

    def test_every_row_has_the_full_contract(self):
        for r in _cover(_full_chip_state()):
            for f in ("tab", "emoji", "color", "ratio_txt", "detail", "action",
                      "fresh_emoji", "fresh_label", "fresh_color", "fresh_asof"):
                assert f in r, f"缺欄位 {f}"

    def test_garbage_types_do_not_raise(self):
        """所有 session key 給錯型別 —— 診斷頁不得整頁掛掉。"""
        rows = _cover({
            "macro_info": "not-a-dict",
            "m1b_m2_info": 42,
            "li_latest": "oops",
            "t2_data": ["a"],
            "cl_data": 3.14,
            "etf_single_data": None,
            "li_retain_meta": "x",
        })
        assert len(rows) == 4
