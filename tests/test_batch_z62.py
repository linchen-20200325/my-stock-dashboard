"""批 Z62 — freshness F2：輸入補上可追溯日期 ＋ L2 純抽取器（⛔ 仍不接線）。

客戶規則（2026-10-14，Q-z37=A）：每日型輸入必須保留並顯示實際資料日期；BIAS240、MA5 要補上
可追溯的資料日期；沒有日期的值不得頂替。

本檔守：
1. L1 `compute_twii_bias` 新增 `as_of`（取實際算乖離那份 Close 序列的最後日期；fallback 取 fallback frame）。
2. L3 `get_market_assessment` 新增 `index_as_of`（ISO 字串；既有鍵不變）；`< 5` 筆假值路徑走不到（不足 120 筆先回 None）。
   L1 `bias_info['as_of']` 同為 ISO 字串（總管裁定：新增日期鍵一律 'YYYY-MM-DD'，舊 UI 輸出逐字不變）。
3. L1 `HolidayCalendar.as_sets()` 與 L3 service 傳給 `classify_day` 的四個集合逐一相同。
4. L2 `src/compute/macro/dated_inputs.py` 抽取器：
   - **Golden**：完整新鮮資料下，值與舊 UI（`section_news_ai.py` 原文切片 exec）逐一相同；
   - **Delta**（刻意差異，非 bug）：最後一列 PCR 缺 → 新抽取器往回取前一列（值＋日期），舊 UI 判缺；
   - 日期：沒有日期一律判缺；結果與「今天」無關。
5. Z61 QA 遺留：`assess_daily` 的 max_lag 檢查、`classify_day` closed 與 trading 衝突時的優先序。

⛔ 不連網。
"""
from __future__ import annotations

import pathlib as _pl

# ══════════════════════════════════════════════════════════════════════════
# 還原 pair（先於任何專案 import 定義 —— 舊批次測試檔會回頭 import 本表）
# ══════════════════════════════════════════════════════════════════════════
#: 本批對 `market_strategy.py` 的改動（修後逐字, 修前逐字）。舊批次（Z35／Z36）的「還原體＝基底檔」
#: 守衛串接本表，先換回 Z62 之前的寫法再套它們自己的還原（同 Z33 串 Z34 慣例）。
_MS_REL = "src/services/market_strategy.py"
Z62_REVERT_PAIRS: dict = {
    _MS_REL: (
        ("from shared.macro_provenance import M1B_PROXY_VALUE_NOTE  # DL-f1-s23：代理註記（L0 SSOT，K1）\n"
         "from shared.dated_value import iso_date_or_none  # 批 Z62：index_as_of 收斂（L0）\n",
         "from shared.macro_provenance import M1B_PROXY_VALUE_NOTE  # DL-f1-s23：代理註記（L0 SSOT，K1）\n"),
        ("    result['index_below_ma5'] = current_price < ma5\n"
         "    # 批 Z62(freshness F2,schema-additive;既有鍵與值一律不變):\n"
         "    #   · `index_as_of`:df_index 最後一筆的日期,ISO 字串 'YYYY-MM-DD'(即上面 current_price／ma5\n"
         "    #     所屬的那一天)。index 無法解析 → None(下游判「無資料日期」,§1 不補今天)。\n"
         "    #     用字串不用 date 物件:舊 ETF AI prompt 會把 mkt_info 的 int／float 值逐一列出,字串不會被撿到。\n"
         "    #   ⚠️ 上面 `ma5` 在 `< 5` 筆時是 `current_price`(假值)—— 但本函式在不足 120 筆時已先回 None\n"
         "    #     (MA120 閘),production 走不到那條路徑(tests/test_batch_z62.py 守住),故不另設旗標;\n"
         "    #     新路徑 `dated_inputs.extract_ma5` 另要求 ma5／index_price 為有限數值。\n"
         "    result['index_as_of']     = iso_date_or_none(df_index.index[-1])\n",
         "    result['index_below_ma5'] = current_price < ma5\n"),
    ),
}
#: 本批在 `get_market_assessment` 回傳 dict 新增的鍵（schema-additive）。
Z62_NEW_MKT_KEYS: tuple = ("index_as_of",)
_ROOT_Z62 = _pl.Path(__file__).resolve().parents[1]


def z62_revert_for(file_path, code: str) -> str:
    """舊批次還原鏈串接用：給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批之前的寫法（無 pair 則原樣）。"""
    p = _pl.Path(file_path)
    rel = (p.resolve().relative_to(_ROOT_Z62) if p.is_absolute() else p).as_posix()
    for new, old in Z62_REVERT_PAIRS.get(rel, ()):
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    return code


def z62_strip_new_keys(x):
    """舊批次 golden（整份 mkt_info 的 sha256）比對用：拿掉本批新增的鍵，其餘原樣。非 dict 原樣回傳。"""
    if isinstance(x, dict) and any(k in x for k in Z62_NEW_MKT_KEYS):
        return {k: v for k, v in x.items() if k not in Z62_NEW_MKT_KEYS}
    return x


import ast
import itertools
import textwrap
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shared import freshness_policy as FP
from shared.dated_value import coerce_month_start, coerce_plain_date, finite_or_none
from shared.freshness_policy import FRESHNESS_POLICY, FreshnessStatus, assess, assess_daily
from shared.macro_provenance import m1b_m2_for_scoring
from shared.pcr_scale import normalize_pcr_to_ratio
from shared.trading_days import CLOSED, CalendarSets, classify_day
from src.compute.macro import dated_inputs as DI
from src.services.macro_state_locker import _ENGINE_NUMERIC_INPUTS, calculate_system_state, _is_finite_number

REPO = Path(__file__).resolve().parents[1]
UTC = timezone.utc


# ══════════════════════════════════════════════════════════════════════════
# 0. 舊 UI 組裝原文切片（`section_news_ai.py`，原文未改一字）
# ══════════════════════════════════════════════════════════════════════════
_OLD_REL = "src/ui/tabs/macro/section_news_ai.py"
_OLD_START = "_vix_d  = _macro_info.get('vix') or {}"
_OLD_END = "_system_state = calculate_system_state(_macro_numbers)"


def _slice(rel: str, start: str, end: str) -> str:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    b = [i for i, ln in enumerate(lines) if start in ln]
    e = [i for i, ln in enumerate(lines) if end in ln]
    assert len(b) == 1 and len(e) == 1, (rel, start, end, b, e)
    return textwrap.dedent("\n".join(lines[b[0]:e[0] + 1]))


_OLD_SRC = _slice(_OLD_REL, _OLD_START, _OLD_END)
_OLD_CODE = compile(_OLD_SRC, "<section_news_ai 組裝段>", "exec")


class _Sess:
    def __init__(self, d):
        self.session_state = d


def _old_numbers(macro_info, *, bias_info=None, li=None, mkt=None, m1b=None):
    """舊 UI 組裝段原文 exec → `_macro_numbers`（舊 UI 送給規則引擎的那一份）。"""
    from src.ui.tabs.macro.section_long import _finite_yoy
    from src.ui.tabs.macro.section_news_ai import _finite_or_none

    sess = {}
    if bias_info is not None:
        sess["bias_info"] = bias_info
    if li is not None:
        sess["li_latest"] = li
    if mkt is not None:
        sess["mkt_info"] = mkt
    if m1b is not None:
        sess["m1b_m2_info"] = m1b
    ns = {
        "_macro_info": macro_info, "st": _Sess(sess),
        "_normalize_pcr": normalize_pcr_to_ratio, "_finite_or_none": _finite_or_none,
        "_finite_yoy": _finite_yoy, "m1b_m2_for_scoring": m1b_m2_for_scoring,
        "calculate_system_state": calculate_system_state,
    }
    exec(_OLD_CODE, ns)
    return ns["_macro_numbers"]


def _new_values(macro_info, *, bias_info=None, li=None, mkt=None, m1b=None):
    out = {}
    out.update(DI.extract_vix(macro_info))
    out.update(DI.extract_bias240(bias_info))
    out.update(DI.extract_leading(li))
    out.update(DI.extract_ma5(mkt))
    out.update(DI.extract_monthly(macro_info, m1b))
    return out


def _eff(v):
    """規則引擎眼中的值（`calculate_system_state._f`）：有限 → float；其餘 → None。"""
    return float(v) if _is_finite_number(v) else None


def _assert_same_as_old(old: dict, new: dict, ctx) -> None:
    """Golden 判準：
    - 舊值有限 → 新值必須是**同一個值、同型別**（逐一相同）；
    - 舊值非有限（None／NaN／±inf）→ 新值為 None（引擎眼中同為缺；新抽取器直接回 None ＋ 原因）；
    - MA5：bool 逐一相同。
    """
    # 批 Z63：golden 只比 session 抽取的 8 項；`PMI_Prev_Month` 改取 PMI 歷史（舊 UI 取 session_state，
    #   依客戶 Q-z34 Q1=B 刻意不同），見 tests/test_batch_z63.py。
    for k in DI.SESSION_ENGINE_INPUTS:
        o, n = old[k], new[k].value
        if k == DI.KEY_MA5:
            assert n is not None and type(n) is bool and n == bool(o), (ctx, k, o, n)
            continue
        if _eff(o) is None:
            assert n is None, (ctx, k, o, n)
            assert new[k].missing_reason, (ctx, k, "缺值必須寫原因")
        else:
            assert n is not None and type(n) is type(o) and n == o, (ctx, k, o, n)


def _li(rows, dtype=None):
    return pd.DataFrame(rows, dtype=dtype)


TODAY = date(2026, 10, 14)
_VIX_FULL = {"current": 17.3, "date": "2026-10-13", "source": "yfinance:^VIX:3mo:1d"}
_PMI_FULL = {"value": 51.2, "date": "2026-09-01", "source": "CIER"}
_M1B_FULL = {"m1b_yoy": 3.2, "m2_yoy": 5.1, "data_month": "2026-08", "source": "CBC-tier1"}
_BIAS_FULL = {"bias_240": 12.3, "as_of": "2026-10-13", "data_days": 300, "is_estimated": False}
_MKT_FULL = {"index_below_ma5": True, "index_as_of": "2026-10-13",
             "ma5": 22000.0, "index_price": 21900.0}
_LI_FULL = [
    {"_date": "20261009", "選PCR": 101.5, "外資大小": -15000.0},
    {"_date": "20261013", "選PCR": 126.8, "外資大小": -21000.0},
]


def _full():
    return dict(macro_info={"vix": dict(_VIX_FULL), "ism_pmi": dict(_PMI_FULL)},
                bias_info=dict(_BIAS_FULL), li=_li(_LI_FULL), mkt=dict(_MKT_FULL),
                m1b=dict(_M1B_FULL))


# ══════════════════════════════════════════════════════════════════════════
# 1. Golden：完整新鮮資料下，與舊 UI 逐一相同
# ══════════════════════════════════════════════════════════════════════════
class TestGolden:
    def test_slice_shape(self):
        """切片確實是舊 UI 的組裝段（防錨點漂到別處）。"""
        for frag in ("'PCR':                 _pcr_ratio,", "_pcr_ratio, _pcr_scale_src = _normalize_pcr(_pcr_v)",
                     "if m1b_m2_for_scoring(_mi_d) is None:", "_below_ma5 = bool(_mkt_d.get('index_below_ma5', False))",
                     "_fut_net_v = _finite_or_none(_fut_net_v)"):
            assert frag in _OLD_SRC, frag

    def test_full_fresh_identical(self):
        kw = _full()
        old = _old_numbers(**kw)
        new = _new_values(**kw)
        _assert_same_as_old(old, new, "full")
        # 具體值（防兩邊一起壞）
        assert new["PCR"].value == pytest.approx(1.268) and new["PCR"].as_of == date(2026, 10, 13)
        assert new["Futures_Net_Short"].value == -21000.0
        assert new["VIX_Index"].as_of == date(2026, 10, 13)
        assert new["BIAS240_pct"].as_of == date(2026, 10, 13)
        assert new["Index_Below_MA5"].value is True and new["Index_Below_MA5"].as_of == date(2026, 10, 13)
        assert new["ISM_PMI_or_OECD_CLI"].data_month == date(2026, 9, 1)
        assert new["M1B_YoY_pct"].data_month == new["M2_YoY_pct"].data_month == date(2026, 8, 1)
        # 引擎輸出：把新值代回舊 dict，結果逐字相同
        sub = dict(old)
        sub.update({k: v.value for k, v in new.items()})
        assert calculate_system_state(sub) == calculate_system_state(old)

    @pytest.mark.parametrize("pcr_raw", [126.8, 1.268, "126.8", "1.268", 0, 0.0, -1.0, 600.0, 10.0, 10.5,
                                         500.0, float("nan"), float("inf"), "-", "", "nan", "None", None,
                                         "abc", np.float64(88.0)])
    def test_pcr_scales_single_row(self, pcr_raw):
        """單列（沒有前一列可退）：PCR 百分比／比值刻度、越界、NaN、inf、空字串族 —— 與舊 UI 相同。"""
        kw = _full()
        kw["li"] = _li([{"_date": "20261013", "選PCR": pcr_raw, "外資大小": -1.0}])
        _assert_same_as_old(_old_numbers(**kw), _new_values(**kw), pcr_raw)

    @pytest.mark.parametrize("fut_raw", [-21000.0, "-5000", 0, None, float("nan"), float("inf"),
                                         float("-inf"), "x", 10 ** 400, np.int64(-7)])
    def test_futures_single_row(self, fut_raw):
        kw = _full()
        kw["li"] = _li([{"_date": "20261013", "選PCR": 120.0, "外資大小": fut_raw}], dtype=object)
        _assert_same_as_old(_old_numbers(**kw), _new_values(**kw), fut_raw)

    @pytest.mark.parametrize("vix", [17.3, 0.0, float("nan"), float("inf"), None])
    @pytest.mark.parametrize("pmi", [51.2, float("nan"), float("-inf"), None])
    @pytest.mark.parametrize("bias", [12.3, -0.0, float("nan"), None])
    def test_vix_pmi_bias(self, vix, pmi, bias):
        kw = _full()
        kw["macro_info"]["vix"]["current"] = vix
        kw["macro_info"]["ism_pmi"]["value"] = pmi
        kw["bias_info"]["bias_240"] = bias
        _assert_same_as_old(_old_numbers(**kw), _new_values(**kw), (vix, pmi, bias))

    _M1B_VALS = (3.2, 0.0, -1.5, float("nan"), float("inf"), None, "<缺鍵>", True, "3.2")

    @pytest.mark.parametrize("m1b,m2", list(itertools.product(_M1B_VALS, _M1B_VALS)))
    @pytest.mark.parametrize("source", ["CBC-tier1", "TWII-proxy"])
    def test_m1b_m2_pairs_and_proxy(self, m1b, m2, source):
        """M1B／M2 成對缺值 ＋ 代理值不計分 —— 與舊 UI 相同。"""
        kw = _full()
        info = {"data_month": "2026-08", "source": source}
        if m1b != "<缺鍵>":
            info["m1b_yoy"] = m1b
        if m2 != "<缺鍵>":
            info["m2_yoy"] = m2
        kw["m1b"] = info
        _assert_same_as_old(_old_numbers(**kw), _new_values(**kw), (m1b, m2, source))

    def test_m1b_proxy_flag(self):
        kw = _full()
        kw["m1b"] = dict(_M1B_FULL, is_proxy=True)
        new = _new_values(**kw)
        _assert_same_as_old(_old_numbers(**kw), new, "is_proxy")
        assert new["M1B_YoY_pct"].value is None and "代理" in new["M1B_YoY_pct"].missing_reason

    @pytest.mark.parametrize("below", [True, False, np.bool_(True), np.bool_(False)])
    def test_ma5_values(self, below):
        kw = _full()
        kw["mkt"]["index_below_ma5"] = below
        _assert_same_as_old(_old_numbers(**kw), _new_values(**kw), below)

    def test_l0_finite_or_none_equals_l5_finite_yoy(self):
        """L0 `finite_or_none` ≡ L5 `_finite_yoy`（含回同一物件）。"""
        from src.ui.tabs.macro.section_long import _finite_yoy
        from src.ui.tabs.macro.section_news_ai import _finite_or_none

        vals = [None, True, False, 0, 1, -3, 3.2, -0.0, float("nan"), float("inf"), float("-inf"),
                10 ** 400, "3.2", "", "nan", np.float64(2.5), np.float64("nan"), np.int64(4),
                np.bool_(True), complex(1, 2), [], {}, object(), pd.NA, pd.NaT]
        for v in vals:
            a, b, c = finite_or_none(v), _finite_yoy({"v": v}, "v"), _finite_or_none(v)
            assert (a is b) and (a is c) or (a == b == c), (v, a, b, c)


# ══════════════════════════════════════════════════════════════════════════
# 2. Delta：刻意差異（新規則，不是 bug）
# ══════════════════════════════════════════════════════════════════════════
class TestDelta:
    def test_last_row_pcr_none_takes_previous_row(self):
        """⚠️ 刻意差異：最後一列 PCR 為 None、前一列有值 →
        新抽取器取**前一列的值與日期**；舊 UI 只看 iloc[-1] → 判缺。是否過期交給 freshness_policy。"""
        kw = _full()
        kw["li"] = _li([
            {"_date": "20261012", "選PCR": 120.0, "外資大小": -100.0},
            {"_date": "20261013", "選PCR": None, "外資大小": -200.0},
        ])
        old = _old_numbers(**kw)
        new = _new_values(**kw)
        assert old["PCR"] is None                                            # 舊：判缺
        assert new["PCR"].value == pytest.approx(1.2)                        # 新：前一列
        assert new["PCR"].as_of == date(2026, 10, 12)                        #     的日期
        # 兩欄各自獨立：外資期貨取它自己的最後一列
        assert new["Futures_Net_Short"].value == -200.0 == old["Futures_Net_Short"]
        assert new["Futures_Net_Short"].as_of == date(2026, 10, 13)

    def test_padded_weekday_rows_not_valid(self):
        """補出來、沒有資料的平日列（值 None／NaN／'-'）不算有效。"""
        li = _li([
            {"_date": "20261007", "選PCR": 99.0, "外資大小": -1.0},
            {"_date": "20261008", "選PCR": None, "外資大小": float("nan")},
            {"_date": "20261009", "選PCR": "-", "外資大小": None},
        ])
        out = DI.extract_leading(li)
        assert out["PCR"].as_of == date(2026, 10, 7) and out["PCR"].value == pytest.approx(0.99)
        assert out["Futures_Net_Short"].as_of == date(2026, 10, 7)

    def test_all_rows_invalid_is_missing(self):
        li = _li([{"_date": "20261009", "選PCR": None, "外資大小": None}])
        out = DI.extract_leading(li)
        assert out["PCR"].value is None and "沒有任何有效值" in out["PCR"].missing_reason
        assert out["Futures_Net_Short"].value is None

    def test_last_valid_pcr_out_of_scale_is_missing_not_skipped(self):
        """最後一個有限讀數刻度不明（例 0 或 >500）→ 判缺，⛔ 不再往前拿舊值頂替。"""
        li = _li([{"_date": "20261012", "選PCR": 120.0, "外資大小": 1.0},
                  {"_date": "20261013", "選PCR": 0.0, "外資大小": 1.0}])
        out = DI.extract_leading(li)
        assert out["PCR"].value is None and out["PCR"].as_of == date(2026, 10, 13)
        assert "刻度" in out["PCR"].missing_reason

    @pytest.mark.parametrize("patch,frag", [
        ({"ma5": float("nan")}, "MA5 不是有限數值"),       # 末 5 筆收盤含 NaN ⇒ ma5 為 NaN
        ({"ma5": None}, "MA5 不是有限數值"),
        ({"index_price": float("inf")}, "現價不是有限數值"),
        ({"index_below_ma5": 1}, "不是 bool"),
        ({"index_below_ma5": 0}, "不是 bool"),
    ])
    def test_ma5_stricter_than_old_ui(self, patch, frag):
        """⚠️ 刻意差異：ma5／index_price 非有限、index_below_ma5 不是 bool → 判缺；舊 UI 照送 `bool(...)`。"""
        mkt = dict(_MKT_FULL, **patch)
        assert type(_old_numbers({}, mkt=mkt)["Index_Below_MA5"]) is bool
        dv = DI.extract_ma5(mkt)["Index_Below_MA5"]
        assert dv.value is None and frag in dv.missing_reason


# ══════════════════════════════════════════════════════════════════════════
# 3. 日期
# ══════════════════════════════════════════════════════════════════════════
def _twii(n, end, *, freq="D", tz=None):
    idx = pd.date_range(end=end, periods=n, freq=freq, tz=tz)
    return pd.DataFrame({"Close": np.linspace(20000.0, 21000.0, n)}, index=idx)


class TestBiasAsOf:
    def test_local_frame_date(self, monkeypatch):
        from src.data.macro import macro_snapshot as snap
        monkeypatch.setattr(snap, "fetch_twii_2y_for_ma240",
                            lambda: pytest.fail("≥240 天不應走 fallback"))
        out = snap.compute_twii_bias(_twii(300, "2026-03-20"))
        assert out["as_of"] == "2026-03-20" and type(out["as_of"]) is str

    def test_fallback_takes_fallback_frame_date(self, monkeypatch):
        """local 只有 90 天（末筆 2026-01-30）→ 走 2 年 fallback（末筆 2026-10-13）→ as_of 取 fallback。"""
        from src.data.macro import macro_snapshot as snap
        monkeypatch.setattr(snap, "fetch_twii_2y_for_ma240", lambda: _twii(500, "2026-10-13"))
        out = snap.compute_twii_bias(_twii(90, "2026-01-30"))
        assert out["data_days"] == 500
        assert out["as_of"] == "2026-10-13"

    def test_fallback_failed_uses_local_date(self, monkeypatch):
        from src.data.macro import macro_snapshot as snap
        monkeypatch.setattr(snap, "fetch_twii_2y_for_ma240", lambda: None)
        out = snap.compute_twii_bias(_twii(90, "2026-01-30"))
        assert out["is_estimated"] is True and out["as_of"] == "2026-01-30"

    def test_trailing_nan_close_dropped(self, monkeypatch):
        """as_of 是 dropna 後**實際用來算**的那份序列的末日（末筆 NaN 不算）。"""
        from src.data.macro import macro_snapshot as snap
        df = _twii(300, "2026-03-20")
        df.iloc[-1, 0] = np.nan
        out = snap.compute_twii_bias(df)
        assert out["as_of"] == "2026-03-19"

    def test_tz_aware_index_wall_date(self):
        from src.data.macro import macro_snapshot as snap
        out = snap.compute_twii_bias(_twii(300, "2026-03-20 00:00", tz="Asia/Taipei"))
        assert out["as_of"] == "2026-03-20"

    def test_unparseable_index_none(self):
        from src.data.macro import macro_snapshot as snap
        df = pd.DataFrame({"Close": np.linspace(1.0, 2.0, 300)})   # RangeIndex
        out = snap.compute_twii_bias(df)
        assert out is not None and out["as_of"] is None
        assert DI.extract_bias240(out)["BIAS240_pct"].value is None

    def test_existing_keys_unchanged(self):
        from src.data.macro import macro_snapshot as snap
        out = snap.compute_twii_bias(_twii(300, "2026-03-20"))
        assert set(out) == {"bias_20", "bias_60", "bias_240", "price", "ma20", "ma60", "ma120",
                            "ma240", "data_days", "is_estimated", "as_of"}


class TestIndexAsOf:
    def _df(self, end):
        idx = pd.date_range(end=end, periods=130, freq="B")
        close = np.linspace(20000.0, 21000.0, 130)
        return pd.DataFrame({"Close": close, "Volume": np.full(130, 1000.0)}, index=idx)

    def test_index_as_of_is_last_row_not_today(self):
        """`index_as_of` = df 最後一筆的日期（刻意設成 3 天前，證明不是今天）。"""
        from src.services.market_strategy import get_market_assessment
        end = pd.Timestamp.now().normalize() - pd.Timedelta(days=3)
        df = self._df(end)
        r = get_market_assessment(df_index=df, foreign_net=1.0)
        assert r is not None
        assert r["index_as_of"] == df.index[-1].date().isoformat() and type(r["index_as_of"]) is str
        assert r["index_as_of"] != date.today().isoformat()
        assert "ma5_insufficient" not in r
        # 既有鍵不變
        assert r["ma5"] == round(float(df["Close"].tail(5).mean()), 2)
        assert r["index_below_ma5"] == (float(df["Close"].iloc[-1]) < float(df["Close"].tail(5).mean()))

    def test_revert_pairs_restore_base_file(self):
        """還原 pair 換回後 ＝ 基底 `5524320a` 的 market_strategy.py（證明本批對該檔只有這兩處改動）。"""
        import hashlib
        code = z62_revert_for(_MS_REL, (REPO / _MS_REL).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == \
            "3fb731a5f5f982524801e39fbc7542753bfb8a697f950446b9acf562fcfa1807"

    @pytest.mark.parametrize("n", [1, 4, 5, 60, 119])
    def test_under_120_rows_returns_none(self, n):
        """守衛（總管裁定）：df 不足 120 筆 → 回 None（MA120 閘）。
        ⇒ `< 5` 筆時 `ma5=current_price` 的假值路徑在 production 到不了，不需要旗標。"""
        from src.services.market_strategy import get_market_assessment
        end = pd.Timestamp.now().normalize() - pd.Timedelta(days=1)
        idx = pd.date_range(end=end, periods=n, freq="B")
        df = pd.DataFrame({"Close": np.linspace(20000.0, 21000.0, n), "Volume": np.full(n, 1000.0)},
                          index=idx)
        assert get_market_assessment(df_index=df, foreign_net=1.0) is None

    def test_ma5_fake_value_kept_in_source(self):
        """舊的 `<5` 筆 ma5=current_price 假值保持原樣（走不到，見上一條）；不再新增 ma5_insufficient。"""
        src = (REPO / "src/services/market_strategy.py").read_text(encoding="utf-8")
        assert "ma5   = float(_close.rolling(5).mean().iloc[-1]) if len(df_index) >= 5 else current_price" in src
        assert "result['ma5_insufficient']" not in src

class TestExtractorDates:
    def test_li_date_parse(self):
        li = _li([{"_date": "20261013", "選PCR": 120.0, "外資大小": 1.0}])
        assert DI.extract_leading(li)["PCR"].as_of == date(2026, 10, 13)

    def test_li_bad_date_missing(self):
        li = _li([{"_date": "2026-13-45", "選PCR": 120.0, "外資大小": 1.0}])
        out = DI.extract_leading(li)
        for k in ("PCR", "Futures_Net_Short"):
            assert out[k].value is None and out[k].missing_reason.startswith("無資料日期")

    def test_li_no_date_column(self):
        li = _li([{"選PCR": 120.0, "外資大小": 1.0}])
        out = DI.extract_leading(li)
        assert out["PCR"].value is None and "無資料日期" in out["PCR"].missing_reason

    @pytest.mark.parametrize("li", [None, pd.DataFrame(), "壞掉"])
    def test_li_not_loaded(self, li):
        out = DI.extract_leading(li)
        assert out["PCR"].value is None and out["Futures_Net_Short"].value is None
        assert out["PCR"].missing_reason

    @pytest.mark.parametrize("bad", [None, "", "13/10/2026", "not a date", 20261013])
    def test_vix_no_date(self, bad):
        dv = DI.extract_vix({"vix": {"current": 17.3, "date": bad}})["VIX_Index"]
        assert dv.value is None and dv.missing_reason == "無資料日期" and dv.as_of is None

    def test_vix_not_loaded(self):
        dv = DI.extract_vix({})["VIX_Index"]
        assert dv.value is None and dv.missing_reason

    def test_bias_no_as_of(self):
        dv = DI.extract_bias240({"bias_240": 12.3})["BIAS240_pct"]
        assert dv.value is None and dv.missing_reason == "無資料日期"

    @pytest.mark.parametrize("mkt", [
        dict(_MKT_FULL, index_as_of=None),
        dict(_MKT_FULL, index_as_of="2026/13/45"),
        {k: v for k, v in _MKT_FULL.items() if k != "index_as_of"},
        {k: v for k, v in _MKT_FULL.items() if k != "index_below_ma5"},
        {k: v for k, v in _MKT_FULL.items() if k != "ma5"},
        {k: v for k, v in _MKT_FULL.items() if k != "index_price"},
        dict(_MKT_FULL, index_below_ma5=None),
        dict(_MKT_FULL, ma5=float("-inf")),
        None, {},
    ])
    def test_ma5_missing(self, mkt):
        dv = DI.extract_ma5(mkt)["Index_Below_MA5"]
        assert dv.value is None and dv.missing_reason

    def test_pmi_no_date(self):
        out = DI.extract_monthly({"ism_pmi": {"value": 51.2}}, dict(_M1B_FULL))
        assert out["ISM_PMI_or_OECD_CLI"].value is None
        assert out["ISM_PMI_or_OECD_CLI"].missing_reason == "無資料月份"

    def test_m1b_data_month_none_is_missing(self):
        out = DI.extract_monthly({}, dict(_M1B_FULL, data_month=None))
        assert out["M1B_YoY_pct"].value is None and out["M2_YoY_pct"].value is None
        assert "無資料月份" in out["M1B_YoY_pct"].missing_reason

    def test_coerce_helpers(self):
        assert coerce_plain_date(pd.Timestamp("2026-10-13 23:59", tz="UTC")) == date(2026, 10, 13)
        assert coerce_plain_date(pd.NaT) is None and coerce_plain_date(np.datetime64("NaT")) is None
        assert coerce_plain_date(np.datetime64("2026-10-13")) == date(2026, 10, 13)
        assert coerce_plain_date(datetime(2026, 10, 13, 5)) == date(2026, 10, 13)
        assert coerce_plain_date(True) is None and coerce_plain_date(0) is None
        assert coerce_month_start("2026-09") == date(2026, 9, 1)
        assert coerce_month_start("2026-09-15") == date(2026, 9, 1)
        assert coerce_month_start("2026/9") is None
        from shared.dated_value import iso_date_or_none
        assert iso_date_or_none(pd.Timestamp("2026-10-13")) == "2026-10-13"
        assert iso_date_or_none("20261013") == "2026-10-13" and iso_date_or_none("x") is None

    def test_results_independent_of_today(self, monkeypatch):
        """抽取器結果與今天無關：把 `time.time` 與 `pandas.Timestamp.now／today` 換成
        遠在 2031 年的「現在」，輸出逐一相同（無 freezegun；`date.today()` 為 C 實作無法換，
        改由下一條 AST 測試保證程式碼裡根本沒有 now()／today()）。"""
        import time as _time

        def _run():
            kw = _full()
            return {k: (v.value, v.as_of, v.data_month, v.missing_reason)
                    for k, v in _new_values(**kw).items()}

        base = _run()
        _fake = pd.Timestamp("2031-01-01 12:00")
        monkeypatch.setattr(_time, "time", lambda: _fake.timestamp())
        monkeypatch.setattr(pd.Timestamp, "now", classmethod(lambda cls, tz=None: _fake))
        monkeypatch.setattr(pd.Timestamp, "today", classmethod(lambda cls, tz=None: _fake))
        assert _run() == base

    def test_no_now_today_fetched_at_in_code(self):
        """AST：抽取器與 L0 helper 的**程式碼**（不含 docstring）沒有呼叫 now()／today()／utcnow()，
        也沒有讀 `fetched_at`。L1／L3 新增的那幾行同樣不用。"""
        for rel in ("src/compute/macro/dated_inputs.py", "shared/dated_value.py"):
            tree = ast.parse((REPO / rel).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    assert node.attr not in ("now", "today", "utcnow"), (rel, node.attr)
                if isinstance(node, ast.Constant) and node.value == "fetched_at":
                    pytest.fail(f"{rel} 讀取 fetched_at")
        for rel, anchor in (("src/data/macro/macro_snapshot.py", "'as_of': iso_date_or_none("),
                            ("src/services/market_strategy.py", "result['index_as_of']")):
            line = next(ln for ln in (REPO / rel).read_text(encoding="utf-8").splitlines() if anchor in ln)
            assert "now" not in line and "today" not in line and "fetched_at" not in line, line
        snap_src = (REPO / "src/data/macro/macro_snapshot.py").read_text(encoding="utf-8")
        assert "'as_of': iso_date_or_none(_cs.index[-1])," in snap_src

    def test_end_to_end_assess(self):
        """抽出的值可直接交給 L0 `assess` 判新鮮度（本批不接線，只確認型別契約對得上）。"""
        cal = CalendarSets(closed=frozenset(), trading=frozenset(), unclassified=frozenset(),
                           covered_years=frozenset({2026}))
        vals = _new_values(**_full())
        got = {k: assess(v, today=TODAY, calendar=cal) for k, v in vals.items()}
        for k, av in got.items():
            assert av.verdict.status == FreshnessStatus.FRESH, (k, av.verdict)
            assert av.scoring_value is not None
        stale = _full()
        stale["li"] = _li([{"_date": "20261001", "選PCR": 120.0, "外資大小": 1.0}])
        av = assess(DI.extract_leading(stale["li"])["PCR"], today=TODAY, calendar=cal)
        assert av.verdict.status == FreshnessStatus.STALE and av.scoring_value is None


# ══════════════════════════════════════════════════════════════════════════
# 4. 鍵一致性 ＋ 分層
# ══════════════════════════════════════════════════════════════════════════
class TestKeysAndLayering:
    def test_covered_keys(self):
        # 批 Z63：`PMI_Prev_Month` 納入 COVERED（由 `extract_pmi_prev` 自 PMI 歷史抽取）；
        #   session 抽取器涵蓋的範圍改名為 SESSION_ENGINE_INPUTS（仍是原本 8 項）。
        assert set(DI.SESSION_ENGINE_INPUTS) == (set(_ENGINE_NUMERIC_INPUTS) | {"Index_Below_MA5"}) - {"PMI_Prev_Month"}
        assert set(DI.COVERED_ENGINE_INPUTS) == set(_ENGINE_NUMERIC_INPUTS) | {"Index_Below_MA5"}
        assert set(DI.COVERED_ENGINE_INPUTS) <= set(FRESHNESS_POLICY)
        assert set(_new_values(**_full())) == set(DI.SESSION_ENGINE_INPUTS)

    def test_l2_imports_only_l0_stdlib_pandas(self):
        tree = ast.parse((REPO / "src/compute/macro/dated_inputs.py").read_text(encoding="utf-8"))
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                mods.add((node.module or "").split(".")[0])
        assert mods <= {"__future__", "datetime", "typing", "math", "pandas", "shared"}, mods


# ══════════════════════════════════════════════════════════════════════════
# 5. HolidayCalendar.as_sets ↔ L3 service 傳給 classify_day 的參數
# ══════════════════════════════════════════════════════════════════════════
class TestAsSets:
    def _cal(self):
        import json
        from src.data.stock import twse_holiday_fetcher as hf
        payload = json.loads((REPO / "tests/fixtures/twse_holiday_schedule_115_synthetic.json")
                             .read_text(encoding="utf-8"))
        # 加一列衝突（同日一列放假、一列開始交易）→ 只歸 unclassified
        payload.append({"Name": "中秋節後開始交易日", "Date": "1150925", "Weekday": "五",
                        "Description": "開始交易。"})
        return hf.parse_holiday_schedule(payload, fetched_at=datetime(2026, 10, 2, tzinfo=UTC))

    def test_same_as_service_kwargs(self, monkeypatch):
        from src.services import trading_calendar_service as svc
        cal = self._cal()
        monkeypatch.setattr(svc._hf, "fetch_twse_holiday_calendar", lambda *, taipei_year: cal)
        seen = []
        real = svc._tc.classify_day

        def spy(day, **kw):
            seen.append(kw)
            return real(day, **kw)

        monkeypatch.setattr(svc._tc, "classify_day", spy)
        svc.get_today_trading_status(datetime(2026, 10, 2, 3, tzinfo=UTC))
        assert seen, "service 沒有呼叫 classify_day"
        s = cal.as_sets()
        assert isinstance(s, CalendarSets)
        kw = seen[0]
        assert set(kw) == {"closed", "trading", "unclassified", "covered_years"}
        assert s.closed == kw["closed"] and s.trading == kw["trading"]
        assert s.unclassified == kw["unclassified"]
        assert s.covered_years == frozenset(kw["covered_years"])
        assert date(2026, 9, 25) in s.unclassified and date(2026, 9, 25) not in s.closed


# ══════════════════════════════════════════════════════════════════════════
# 5b. assess()：值不是有限數值 → MISSING（自檢 A 組；日期判斷之前）
# ══════════════════════════════════════════════════════════════════════════
_CAL26 = CalendarSets(closed=frozenset(), trading=frozenset(), unclassified=frozenset(),
                      covered_years=frozenset({2026}))


class TestAssessNonFinite:
    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), np.float64("nan"),
                                     "1.2", np.bool_(True)])
    @pytest.mark.parametrize("key,dated", [
        ("VIX_Index", {"as_of": date(2026, 10, 13)}),
        ("PCR", {"as_of": date(2026, 10, 13)}),
        ("PCR", {"as_of": date(2026, 9, 1)}),          # 日期本來會判 STALE
        ("PCR", {"as_of": date(2026, 10, 20)}),        # 日期本來會判 UNDETERMINED
        ("PCR", {}),                                   # 沒有日期 —— 仍以「資料異常」為準（在日期判斷之前）
        ("M1B_YoY_pct", {"data_month": date(2026, 8, 1)}),
    ])
    def test_non_finite_is_missing(self, bad, key, dated):
        from shared.dated_value import DatedValue
        av = assess(DatedValue(bad, key, "test", **dated), today=TODAY, calendar=_CAL26)
        assert av.verdict.status == FreshnessStatus.MISSING
        assert "資料異常" in av.verdict.reason
        assert av.verdict.reason == f"{key}資料異常，無法計算，不下結論。"
        assert av.scoring_value is None

    def test_reason_text_is_the_approved_ssot(self):
        from shared.station_specs import INVALID_DATA_TEXT
        assert FP.NON_FINITE_REASON_FMT is INVALID_DATA_TEXT

    @pytest.mark.parametrize("key,val,dated,expect", [
        ("VIX_Index", 17.3, {"as_of": date(2026, 10, 13)}, FreshnessStatus.FRESH),
        ("PCR", 1.2, {"as_of": date(2026, 9, 1)}, FreshnessStatus.STALE),
        ("PCR", 0.0, {"as_of": date(2026, 10, 13)}, FreshnessStatus.FRESH),
        ("PCR", 1.2, {"as_of": date(2026, 10, 20)}, FreshnessStatus.UNDETERMINED),
        ("PCR", 1.2, {}, FreshnessStatus.MISSING),
        ("Index_Below_MA5", True, {"as_of": date(2026, 10, 13)}, FreshnessStatus.FRESH),
        ("Index_Below_MA5", False, {"as_of": date(2026, 10, 13)}, FreshnessStatus.FRESH),
        ("M1B_YoY_pct", 3.2, {"data_month": date(2026, 8, 1)}, FreshnessStatus.FRESH),
    ])
    def test_finite_values_follow_original_flow(self, key, val, dated, expect):
        from shared.dated_value import DatedValue
        av = assess(DatedValue(val, key, "test", **dated), today=TODAY, calendar=_CAL26)
        assert av.verdict.status == expect, av.verdict
        assert "資料異常" not in av.verdict.reason


# ══════════════════════════════════════════════════════════════════════════
# 6. Z61 QA 遺留
# ══════════════════════════════════════════════════════════════════════════
class TestZ61Leftovers:
    @pytest.mark.parametrize("bad", [-1, 3.5, True, False, "3", None])
    def test_assess_daily_max_lag_validated(self, bad):
        with pytest.raises(ValueError):
            assess_daily(date(2026, 10, 13), today=TODAY, calendar=None, max_lag=bad)

    def test_assess_daily_max_lag_zero_ok(self):
        v = assess_daily(TODAY, today=TODAY, calendar=None, max_lag=0)
        assert v.status == FreshnessStatus.FRESH

    def test_classify_day_closed_beats_trading(self):
        """釘住現行優先序：同一天同時在 closed 與 trading → closed 勝（只加測試，不改行為）。"""
        d = date(2026, 10, 13)
        v = classify_day(d, closed={d}, trading={d}, unclassified=set(), covered_years={2026})
        assert v.status == CLOSED
        sat = date(2026, 10, 17)
        assert classify_day(sat, closed={sat}, trading={sat}, unclassified=set(),
                            covered_years={2026}).status == CLOSED

    def test_policy_header_lists_new_pending_items(self):
        """檔頭待接線表：日頻曆日規則逐條登記（自檢 B 組盤點），且明寫計分以 FRESHNESS_POLICY 為準。"""
        doc = FP.__doc__ or ""
        for name in ("STALE_DAYS_DAILY", "MACRO_VERDICT_MAX_AGE_DAYS", "_days_old > 7",
                     "_STALE_MAX_AGE_MIN", "EXTREME_STALE_MAX_CALENDAR_DAYS", "LEAD_QUOTE_MAX_AGE_DAYS",
                     "SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS", "FROZEN_STALE_PERIODS_LEADING"):
            assert name in doc, name
        assert "計分輸入的 freshness 一律以本檔 `FRESHNESS_POLICY` 為準" in doc
        assert "快取 pickle 的存活上限" in doc and "凍結值判定" in doc
        # 【中】更正：MACRO_VERDICT_MAX_AGE_DAYS 是裁決有效期（決策閘、已核准），接線時保留
        assert "裁決有效期（決策閘，客戶已核准）" in doc and "接線時保留" in doc
        assert "它們是**診斷頁的曆日尺**" not in doc

    def test_page_today_comment_points_to_l0(self):
        src = (REPO / "src/ui/views/page_today.py").read_text(encoding="utf-8")
        assert "L0 `shared/trading_days.py` 檔頭" in src
        assert "L2 `compute/trading_calendar.py` 檔頭" not in src


# ══════════════════════════════════════════════════════════════════════════
# 7. 補件（總管裁定）：舊 UI 輸出逐字不變 ＋ 實際產出路徑的日期格式
# ══════════════════════════════════════════════════════════════════════════
_ETF_REL = "src/ui/etf/etf_tab_ai.py"
_ETF_SRC = _slice(_ETF_REL, "for _k, _v in mkt_info.items():", "_macro_str = '\\n'.join(_macro_lines)")
_ETF_CODE = compile(_ETF_SRC, "<etf_tab_ai mkt_info 逐值掃描段>", "exec")


def _z62_pre_market_strategy():
    """現行 market_strategy 只把本批改動換回 Z62 之前（獨立模組物件，不影響本尊）。"""
    import importlib.util
    import sys
    path = REPO / _MS_REL
    name = "_z62_pre_market_strategy"
    if name in sys.modules:
        return sys.modules[name]
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    m.__file__ = str(path)
    sys.modules[name] = m
    exec(compile(z62_revert_for(_MS_REL, path.read_text(encoding="utf-8")), str(path), "exec"), m.__dict__)
    return m


def _etf_macro_str(mkt_info) -> str:
    ns = {"mkt_info": mkt_info, "_macro_lines": ["• 大盤狀態：多頭"]}
    exec(_ETF_CODE, ns)
    return ns["_macro_str"]


class TestOldUiUnchanged:
    def _df(self, n=130, end_days_ago=2):
        end = pd.Timestamp.now().normalize() - pd.Timedelta(days=end_days_ago)
        idx = pd.date_range(end=end, periods=n, freq="B")
        close = np.linspace(20000.0, 21000.0, n)
        close[-1] = close[-2] - 50.0          # 讓 index_below_ma5 為 True（真 bool 值會被逐值列出）
        return pd.DataFrame({"Close": close, "Volume": np.full(n, 1000.0)}, index=idx)

    def test_slice_is_the_enumeration_loop(self):
        assert "isinstance(_v, (int, float))" in _ETF_SRC and "_macro_lines.append(f'• {_k}: {_v}')" in _ETF_SRC

    @pytest.mark.parametrize("foreign_net", [1.5e9, -2.0e9])
    def test_etf_ai_prompt_identical_before_after_z62(self, foreign_net):
        """舊 ETF AI prompt 的 mkt_info 逐值段：Z62 前（還原體）後（現行）逐字相同。"""
        from src.services import market_strategy as MS
        df = self._df()
        new = MS.get_market_assessment(df_index=df.copy(), foreign_net=foreign_net)
        old = _z62_pre_market_strategy().get_market_assessment(df_index=df.copy(), foreign_net=foreign_net)
        assert new is not None and old is not None
        assert "index_as_of" in new and "index_as_of" not in old
        assert {k: v for k, v in new.items() if k != "index_as_of"} == old
        assert _etf_macro_str(new) == _etf_macro_str(old)
        assert "index_as_of" not in _etf_macro_str(new)
        assert "index_below_ma5: True" in _etf_macro_str(new)    # 證明掃描段真的有在列 bool

    def test_new_keys_are_str_not_date(self):
        """新增日期鍵一律 ISO 字串（不是 date 物件）—— 可序列化，也不會被 int／float 掃描撿到。"""
        import json
        from src.data.macro import macro_snapshot as snap
        from src.services import market_strategy as MS
        r = MS.get_market_assessment(df_index=self._df(), foreign_net=1.0)
        bi = snap.compute_twii_bias(_twii(300, "2026-03-20"))
        for v in (r["index_as_of"], bi["as_of"]):
            assert type(v) is str and len(v) == 10 and v[4] == "-" and v[7] == "-"
            assert not isinstance(v, (int, float))
        json.dumps({"index_as_of": r["index_as_of"], "as_of": bi["as_of"]})


# ── 實際產出路徑的日期格式（不是手造字串）──────────────────────────────────
class TestRealProducerFormats:
    def test_li_latest_date_from_build_leading_fast(self, monkeypatch, tmp_path):
        """`build_leading_fast` 真實路徑（FinMind 回應以 z25 同款合成框餵入、其餘來源離線）→
        `_date` 實際為 str 'YYYYMMDD'；`extract_leading` 讀得出日期（不會永遠判缺）。"""
        from shared import cache_layer as CL
        from src.data.macro import leading_indicators as LI
        from tests.test_batch_z25 import _D, _DK, _MTX, _TX, _frame, _patch

        _patch(monkeypatch, _frame(_TX), _frame(_MTX))
        monkeypatch.setattr(CL, "_PKL_DIR", str(tmp_path))
        df = LI.build_leading_fast(days=7, token="z62-real-path")
        assert df is not None and not df.empty
        kinds = {type(v) for v in df["_date"]}
        assert kinds == {str}, kinds
        assert all(len(v) == 8 and v.isdigit() for v in df["_date"])
        assert set(df["_date"]) >= set(_DK)
        out = DI.extract_leading(df)
        fut = out["Futures_Net_Short"]
        assert fut.value is not None and fut.as_of == max(_D)
        # 經 pickle 快取讀回（第二次呼叫走新鮮快取）：型別不變
        df2 = LI.build_leading_fast(days=7, token="z62-real-path")
        assert {type(v) for v in df2["_date"]} == {str}
        assert DI.extract_leading(df2)["Futures_Net_Short"].as_of == max(_D)

    def test_vix_date_from_fetch_vix_block(self, monkeypatch):
        """`fetch_vix_block` 真實路徑（yfinance.download 以合成日線替換）→ `date` 為 str 'YYYY-MM-DD'。"""
        import yfinance
        from src.data.macro import macro_snapshot as snap
        idx = pd.date_range("2026-07-01", periods=40, freq="B")
        monkeypatch.setattr(yfinance, "download",
                            lambda *a, **k: pd.DataFrame({"Close": np.linspace(15.0, 18.0, 40)}, index=idx))
        if hasattr(snap.fetch_vix_block, "clear"):
            snap.fetch_vix_block.clear()
        try:
            blk = snap.fetch_vix_block()
        finally:
            if hasattr(snap.fetch_vix_block, "clear"):
                snap.fetch_vix_block.clear()
        d = blk["vix"]["date"]
        assert type(d) is str and d == idx[-1].strftime("%Y-%m-%d")
        dv = DI.extract_vix(blk)["VIX_Index"]
        assert dv.value == blk["vix"]["current"] and dv.as_of == idx[-1].date()

    def test_pmi_date_from_real_parser(self):
        """台灣 PMI 各源一律組成 'YYYY-MM-01' 字串；以 data.gov.tw 真實解析器（`_parse_dgtw_pmi_csv`）驗。"""
        from src.data.macro import macro_core
        got = macro_core._parse_dgtw_pmi_csv("Date,PMI,NMI\n202607,55.0,-\n202608,56.2,-\n",
                                              today=date(2026, 10, 14), max_age_days=120)
        assert got == {"value": 56.2, "date": "2026-08-01"}
        dv = DI.extract_monthly({"ism_pmi": got}, {})["ISM_PMI_or_OECD_CLI"]
        assert dv.value == 56.2 and dv.data_month == date(2026, 8, 1)

    def test_m1b_data_month_from_cbc_tier(self, monkeypatch):
        """`fetch_cbc_m1b_m2` 真實路徑（Tier 1 解析以合成結果替換）→ `data_month` 為 str 'YYYY-MM'。"""
        from src.data.macro import tw_macro as TM
        monkeypatch.setattr(TM, "_try_cbc_ms1_dated", lambda url: (3.2, 5.1, date(2026, 8, 1)))
        monkeypatch.setattr(TM, "_today_tw", lambda: date(2026, 10, 14))
        res = TM.fetch_cbc_m1b_m2(include_proxy=False)
        assert res["data_month"] == "2026-08" and type(res["data_month"]) is str
        info = {"m1b_yoy": res["m1b_yoy"], "m2_yoy": res["m2_yoy"], "data_month": res["data_month"],
                "source": "CBC-tier1"}
        out = DI.extract_monthly({}, info)
        assert out["M1B_YoY_pct"].data_month == date(2026, 8, 1) and out["M1B_YoY_pct"].value == 3.2

    def test_bias_as_of_from_trio_path(self, monkeypatch):
        """L3 `macro_trio_orchestrator` 呼叫的就是 `compute_twii_bias(tw_raw['台股加權指數'])` → as_of 為 ISO 字串。"""
        from src.data.macro import macro_snapshot as snap
        monkeypatch.setattr(snap, "fetch_twii_2y_for_ma240", lambda: None)
        bi = snap.compute_twii_bias(_twii(260, "2026-10-13"))
        assert bi["as_of"] == "2026-10-13"
        assert DI.extract_bias240(bi)["BIAS240_pct"].as_of == date(2026, 10, 13)


# ══════════════════════════════════════════════════════════════════════════
# 8. 獨立 QA 回饋（B1 阻擋 ＋ L1／L2 低嚴重度）
# ══════════════════════════════════════════════════════════════════════════
class TestQaB1StrictDateStrings:
    @pytest.mark.parametrize("bad", ["2026101", "2026111", "202612", "2026-1-5", "2026-10-1",
                                     "2026/1/05", "2026-1-05", "2026/10/1", "202610131",
                                     "２０２６１０１３", "2026-10-13T00:00", "2026-13-01", "20261301"])
    def test_truncated_or_malformed_day_strings_are_none(self, bad):
        """B1：strptime 的 %m／%d 收一位數 ⇒ 殘缺字串會被捏成日期。先 fullmatch 位數，不合格一律 None（§1）。"""
        assert coerce_plain_date(bad) is None

    @pytest.mark.parametrize("bad", ["2026-8", "2026-1", "202608", "2026/08", "2026-13", "2026-8-01"])
    def test_truncated_month_strings_are_none(self, bad):
        assert coerce_month_start(bad) is None

    @pytest.mark.parametrize("good,expect", [("2026-10-13", date(2026, 10, 13)), ("20261013", date(2026, 10, 13)),
                                             ("2026/10/13", date(2026, 10, 13)), (" 2026-10-13 ", date(2026, 10, 13))])
    def test_full_formats_still_parse(self, good, expect):
        assert coerce_plain_date(good) == expect

    def test_extract_vix_truncated_date_is_missing(self):
        dv = DI.extract_vix({"vix": {"current": 17.3, "date": "2026101"}})["VIX_Index"]
        assert dv.value is None and dv.as_of is None and dv.missing_reason == "無資料日期"

    def test_extract_leading_truncated_date_is_missing(self):
        out = DI.extract_leading(_li([{"_date": "2026101", "選PCR": 120.0, "外資大小": 1.0}]))
        assert out["PCR"].value is None and out["PCR"].missing_reason.startswith("無資料日期")


class TestQaL1StringOrBoolIsMissing:
    @pytest.mark.parametrize("raw", ["20.5", True, False, "0"])
    def test_vix_pmi_bias_string_or_bool_delta(self, raw):
        """⚠️ 刻意差異（docstring「刻意差異 2」）：數字字串／bool —— 舊 UI 原值照送、引擎當成數字計分；
        新抽取器判缺（§1：數值欄出現字串／bool 代表上游型別壞了，不猜）。目前 producer 只出 float，無實際影響。"""
        kw = _full()
        kw["macro_info"]["vix"]["current"] = raw
        kw["macro_info"]["ism_pmi"]["value"] = raw
        kw["bias_info"]["bias_240"] = raw
        old = _old_numbers(**kw)
        new = _new_values(**kw)
        for k in ("VIX_Index", "ISM_PMI_or_OECD_CLI", "BIAS240_pct"):
            assert old[k] is raw and _eff(old[k]) is not None, k        # 舊：引擎會計分
            assert new[k].value is None and "非有限值" in new[k].missing_reason, k   # 新：判缺

    def test_docstring_states_the_delta(self):
        doc = DI.__doc__ or ""
        assert "數字字串（如 '20.5'）或 bool" in doc and "目前所有 producer 都只輸出 float" in doc


class TestQaL2Gaps:
    @pytest.mark.parametrize("last", [float("inf"), float("-inf"), "NaN", "inf", float("nan")])
    def test_m2_non_finite_last_pcr_steps_back(self, last):
        """M2：現行規則 —— 非有限值（inf／'NaN'／'inf'）一律視為無效、繼續往回找；
        「刻度不明」只限**有限**值（≤0 或 >500，見 test_last_valid_pcr_out_of_scale_is_missing_not_skipped）。"""
        li = _li([{"_date": "20261012", "選PCR": 120.0, "外資大小": 1.0},
                  {"_date": "20261013", "選PCR": last, "外資大小": 1.0}], dtype=object)
        dv = DI.extract_leading(li)["PCR"]
        assert dv.value == pytest.approx(1.2) and dv.as_of == date(2026, 10, 12)

    @pytest.mark.parametrize("out_of_scale", [0.0, -3.0, 600.0])
    def test_m2_finite_out_of_scale_does_not_step_back(self, out_of_scale):
        li = _li([{"_date": "20261012", "選PCR": 120.0, "外資大小": 1.0},
                  {"_date": "20261013", "選PCR": out_of_scale, "外資大小": 1.0}])
        dv = DI.extract_leading(li)["PCR"]
        assert dv.value is None and dv.as_of == date(2026, 10, 13) and "刻度" in dv.missing_reason

    def test_m11_numpy_float64_types_match_old_path(self):
        """M11：np.float64 輸入 —— 輸出型別與舊路徑逐一相同（golden 為準：舊路徑原物件照送 ⇒ np.float64）。"""
        kw = _full()
        kw["macro_info"]["vix"]["current"] = np.float64(17.3)
        kw["macro_info"]["ism_pmi"]["value"] = np.float64(51.2)
        kw["bias_info"]["bias_240"] = np.float64(12.3)
        kw["m1b"] = dict(_M1B_FULL, m1b_yoy=np.float64(3.2), m2_yoy=np.float64(5.1))
        old = _old_numbers(**kw)
        new = _new_values(**kw)
        for k in ("VIX_Index", "ISM_PMI_or_OECD_CLI", "BIAS240_pct", "M1B_YoY_pct", "M2_YoY_pct"):
            assert type(old[k]) is np.float64, k
            assert type(new[k].value) is np.float64 and new[k].value == old[k], k
        # PCR／外資期貨：舊路徑經 float()（PCR 再 ÷100）⇒ Python float；新路徑相同
        for k in ("PCR", "Futures_Net_Short"):
            assert type(old[k]) is float and type(new[k].value) is float, k

    @pytest.mark.parametrize("raw,expect", [
        ("2026-09", date(2026, 9, 1)),        # 'YYYY-MM' ⇒ 取月初
        ("2026-09-15", date(2026, 9, 1)),     # 非月初日期 ⇒ 取月初（現行規則）
        ("2026-09-01", date(2026, 9, 1)),
        ("2026-9", None),                     # 殘缺 ⇒ 判缺（B1）
        ("2026-09-1", None),
    ])
    def test_m17_pmi_date_shapes(self, raw, expect):
        """M17：PMI date 的形狀 —— 現行規則：'YYYY-MM' 與非月初日期一律取月初；殘缺字串判缺。"""
        dv = DI.extract_monthly({"ism_pmi": {"value": 51.2, "date": raw}}, {})["ISM_PMI_or_OECD_CLI"]
        if expect is None:
            assert dv.value is None and dv.missing_reason == "無資料月份"
        else:
            assert dv.value == 51.2 and dv.data_month == expect
