"""DL-f1-s1：線上 `tw_macro._try_cbc_ef15m01`（M1B／M2 三層備援 Tier 2）改用共用 EF15M01 解析器。

根因：舊版讀頂層 `DataSet`／`Structure`（舊格式），CBC 現行回應是 `{meta, data:{dataSets, structure}}`
⇒ 恆回 None，`fetch_cbc_m1b_m2()` 落到 Tier 3 `^TWII` 動能代理。探針 GitHub Actions run 36408641177
實測：代理回 m1b 3.65／m2 0.91／gap +2.74；央行 EF15M01 2026M07 官方年增率 7.34／7.42（gap −0.08）
—— 方向相反。

fixture：沿用 `tests/test_b7b_r1_ef15m01_level.py`（#732）的 `ef15_body()` —— meta／structure 全文與
2026M05～07 三列逐字轉錄自探針 log，其餘為自洽合成序列（說明見該檔檔頭）。
⚠️ 本檔只測規則；**沒有**在真實 CBC 回應上跑過（本容器連不到 CBC，egress 403）。

對帳窗口（致命範圍）：表內最新資料月 2026-07 → `ef15_fatal_from(2026-07-01)` = 2025-07-01，
即 2025-07～2026-07 內任一列對帳不符 → 拒用；更早的列不符只警示。

無網路：`tw_macro.fetch_url` 以 monkeypatch 回應；`_try_twii_proxy` 一律換樁（不打 Yahoo）。
"""
from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.update_macro_history as umh
from src.data.macro import cbc_ef15m01 as ef15
from src.data.macro import tw_macro
from tests.test_b7b_r1_ef15m01_level import (
    EF15_TABLE1,
    I_M1A,
    I_M1B,
    I_M2,
    _lv_col,
    _p,
    _row_of,
    _shift,
    _yy_col,
    ef15_body,
    ef15_body_from_levels,
    ef15_rows,
)

_REPO = Path(__file__).resolve().parent.parent

@pytest.fixture(autouse=True)
def _pin_today(monkeypatch):
    """D3（DL-f1-s13）起 `fetch_cbc_m1b_m2` 對官方值加資料月過期閘（落後 ≥ 1 期拒用）。
    本檔 fixture 最新月 2026M07 → 基準日釘在探針當天 2026-09-28（當期），不吃執行日。"""
    monkeypatch.setattr(tw_macro, "_today_tw", lambda: dt.date(2026, 9, 28))


#: 探針 run 36408641177 的 Tier 3 代理值（`fetch_cbc_m1b_m2()` 實測 tier_used=3 時的回傳）
_PROXY = (3.65, 0.91)


class _R:
    status_code = 200

    def __init__(self, body):
        self._b = body

    def json(self):
        if isinstance(self._b, Exception):
            raise self._b
        return self._b


def _patch(monkeypatch, body, *, proxy=_PROXY) -> list:
    """EF15M01 回 `body`（None = 無回應）；ms1.json 一律失敗；Tier 3 換成 `proxy` 樁。回請求紀錄。"""
    calls: list = []

    def _fake(url, headers=None, params=None, timeout=None, **kw):
        calls.append((url, dict(params or {}), timeout))
        if (params or {}).get("FileName") == "EF15M01":
            return None if body is None else _R(body)
        return None                                   # Tier 1 ms1.json：現況兩個網址都失效
    monkeypatch.setattr(tw_macro, "fetch_url", _fake)
    monkeypatch.setattr(tw_macro, "_try_twii_proxy", lambda: proxy)
    return calls


def _off(rows, per, idx=I_M2, by=0.02):
    """把某月某序列的官方年增率改掉 `by` pp（遠超捨入容差 ≈ 0.005pp）。"""
    r = _row_of(rows, per)
    r[_yy_col(idx)] = f"{float(r[_yy_col(idx)]) + by:.2f}"


# ═════════════════════════════════════════════════════════════════════════════
class TestCurrentFormat:
    def test_returns_official_yoy_of_latest_month(self, monkeypatch, capsys):
        calls = _patch(monkeypatch, ef15_body())
        assert tw_macro._try_cbc_ef15m01() == (7.34, 7.42)
        # 取數照舊：同網址、同參數、同 timeout（只請求一次）
        assert calls == [(tw_macro.CBC_EF15M01_URL, {"FileName": "EF15M01"}, 15)]
        out = capsys.readouterr().out
        assert "[tw_macro/EF15M01] ✅ 2026-07 官方年增率 M1B=7.34% M2=7.42%" in out
        assert "致命範圍 ≥ 2025-07" in out                  # 對帳窗口 = 最新月往前 12 個月起

    def test_fetch_cbc_m1b_m2_uses_tier2_not_proxy(self, monkeypatch):
        _patch(monkeypatch, ef15_body())

        def _boom():
            raise AssertionError("Tier 2 可用時不得走到 Tier 3 ^TWII 代理")
        monkeypatch.setattr(tw_macro, "_try_twii_proxy", _boom)
        r = tw_macro.fetch_cbc_m1b_m2()
        assert r["tier_used"] == 2 and r["is_proxy_tier"] is False
        assert (r["m1b_yoy"], r["m2_yoy"], r["gap"]) == (7.34, 7.42, -0.08)
        assert r["source"] == "CBC:EF15M01:tier2" and r["error"] is None
        # 回傳 schema：修正前的鍵全在；D3（DL-f1-s13）加性多一個 `data_month`
        assert set(r) == {"m1b_yoy", "m2_yoy", "gap", "tier_used", "is_proxy_tier",
                          "error", "source", "fetched_at", "data_month"}
        assert r["data_month"] == "2026-07"

    def test_value_is_official_not_recomputed_from_levels(self, monkeypatch):
        """2025-07 餘額為 "-" → 2026-07 無 t−12 餘額、無從自算；官方年增率照樣是 7.34／7.42。
        （若實作偷換成「由餘額自算」，這裡拿不到值 —— 釘住「採官方年增率」。）"""
        rows = ef15_rows()
        _row_of(rows, "2025M07")[_lv_col(I_M2)] = "-"
        _patch(monkeypatch, ef15_body(rows))
        assert tw_macro._try_cbc_ef15m01() == (7.34, 7.42)


# ═════════════════════════════════════════════════════════════════════════════
class TestStepBack:
    @pytest.mark.parametrize("col,idx", [("yoy", I_M2), ("yoy", I_M1B),
                                         ("level", I_M1B), ("level", I_M2)])
    def test_latest_month_dash_steps_back_one_month(self, monkeypatch, col, idx):
        rows = ef15_rows()
        r = _row_of(rows, "2026M07")
        r[_yy_col(idx) if col == "yoy" else _lv_col(idx)] = "-"
        _patch(monkeypatch, ef15_body(rows))
        # 2026M06 真實列：M1B 9.40、M2 8.13（逐字轉錄自探針 log）
        assert tw_macro._try_cbc_ef15m01() == (9.40, 8.13)

    def test_no_month_with_both_yoy_returns_none(self, monkeypatch):
        rows = ef15_rows()
        for r in rows:
            if r[0] >= "2025M01":
                r[_yy_col(I_M1B) if int(r[0][5:]) % 2 else _yy_col(I_M2)] = "-"
        for r in rows:
            if r[0] < "2025M01":
                r[_yy_col(I_M1B)] = "-"
        _patch(monkeypatch, ef15_body(rows))
        assert tw_macro._try_cbc_ef15m01() is None

    def test_available_month_older_than_window_rejected(self, monkeypatch, capsys):
        """窗口（≥ 2025-07）內每個月都只缺一個序列的官方年增率（M1B、M2 輪流缺）→ 兩序列在窗口內
        都各有可對帳列（解析器放行），但沒有任何一個月兩者都有值 → 能用的最新月是 2025-06，
        落在對帳窗口之外 → 拒用（不拿窗口外、未以致命規則對帳的月份頂替）。"""
        rows = ef15_rows()
        for r in rows:
            if r[0] >= "2025M07":
                r[_yy_col(I_M1B) if int(r[0][5:]) % 2 else _yy_col(I_M2)] = "-"
        _patch(monkeypatch, ef15_body(rows))
        assert tw_macro._try_cbc_ef15m01() is None
        out = capsys.readouterr().out
        assert "2025-06" in out and "早於對帳窗口" in out

    def test_available_month_equal_to_window_start_is_accepted(self, monkeypatch):
        """（批 M QA QM5）可用的最新月份**恰好等於**窗口起點 2025-07 → 它本身在致命範圍內
        （已以致命規則對帳）→ 採用；判定是「早於」窗口才拒用，等於不算早於。
        窗口內 2025-08～2026-07 每月只缺一個序列的官方年增率（輪流缺），2025-07 兩者都有。"""
        rows = ef15_rows()
        for r in rows:
            if r[0] > "2025M07":
                r[_yy_col(I_M1B) if int(r[0][5:]) % 2 else _yy_col(I_M2)] = "-"
        r07 = _row_of(rows, "2025M07")
        _patch(monkeypatch, ef15_body(rows))
        assert ef15.ef15_fatal_from(dt.date(2026, 7, 1)) == dt.date(2025, 7, 1)   # 前提：窗口起點
        assert tw_macro._try_cbc_ef15m01() == (float(r07[_yy_col(I_M1B)]),
                                               float(r07[_yy_col(I_M2)]))

    def test_official_yoy_exactly_zero_is_a_value_not_missing(self, monkeypatch):
        """（批 M QA QM13）官方年增率剛好 "0.00"（與同月去年同額，持平）是有效觀測，
        **不是缺值** —— 不得被當成 "-" 而往前退一個月。"""
        n = 30
        periods = [_p(*_shift(2024, 2, k)) for k in range(n)]             # 2024-02 … 2026-07
        m1b = [round(20_000_000 * 1.006 ** k) for k in range(n)]
        m1b[-1] = m1b[-13]                                                 # 最新月 = 同月去年
        m2 = [round(60_000_000 * 1.005 ** k) for k in range(n)]
        body = ef15_body_from_levels(periods, m1b, m2)
        last = body["data"]["dataSets"][-1]
        assert last[0] == "2026M07" and last[_yy_col(I_M1B)] == "0.00"   # 前提
        _patch(monkeypatch, body)
        assert tw_macro._try_cbc_ef15m01() == (0.0, float(last[_yy_col(I_M2)]))


# ═════════════════════════════════════════════════════════════════════════════
class TestLabels:
    def test_m1a_values_never_returned_as_m1b(self, monkeypatch):
        body = ef15_body()
        _patch(monkeypatch, body)
        m1a_2026_07 = float(_row_of(body["data"]["dataSets"], "2026M07")[_yy_col(I_M1A)])
        assert m1a_2026_07 == 8.28                     # 前提：M1A 與 M1B 的官方年增率不同
        got = tw_macro._try_cbc_ef15m01()
        assert got == (7.34, 7.42) and got[0] != m1a_2026_07

    @pytest.mark.parametrize("variant", ["貨幣總計數 -Ｍ１Ｃ",              # M1B 標籤不見 → 0 命中
                                         "貨幣總計數 -Ｍ１Ｂ（含外幣）"])  # 部分同名不算命中
    def test_missing_m1b_label_falls_to_tier3_never_m1a(self, monkeypatch, variant):
        t1 = list(EF15_TABLE1)
        t1[I_M1B] = variant
        _patch(monkeypatch, ef15_body(table1=t1))
        assert tw_macro._try_cbc_ef15m01() is None
        r = tw_macro.fetch_cbc_m1b_m2()
        assert r["tier_used"] == 3 and r["is_proxy_tier"] is True
        assert (r["m1b_yoy"], r["m2_yoy"]) == _PROXY

    def test_m1a_relabelled_as_m1b_is_ambiguous_and_rejected(self, monkeypatch):
        t1 = list(EF15_TABLE1)
        t1[I_M1A] = "貨幣總計數-M1B"                   # NFKC 後與 M1B 同名 → 2 個命中
        _patch(monkeypatch, ef15_body(table1=t1))
        assert tw_macro._try_cbc_ef15m01() is None


# ═════════════════════════════════════════════════════════════════════════════
class TestFormatMismatch:
    @staticmethod
    def _old_top_level_body() -> dict:
        """舊版 `_try_cbc_ef15m01` 認得的頂層 `DataSet`／`Structure` 形狀（修正前唯一會放行的格式）。"""
        rows = [{"TIME": f"{2025 + k // 12}M{k % 12 + 1:02d}",
                 "M1B": str(28_000_000 + 100_000 * k), "M2": str(65_000_000 + 150_000 * k)}
                for k in range(19)]
        return {"DataSet": rows,
                "Structure": {"Dimensions": [{"id": "M1B", "name": "M1B"},
                                             {"id": "M2", "name": "M2"}]}}

    @pytest.mark.parametrize("body", [
        pytest.param("old", id="old-top-level-DataSet"),
        pytest.param({"meta": {}, "data": {}}, id="empty-data"),
        pytest.param([["2026M07", "1"]], id="list-not-object"),
        pytest.param("not json", id="json-string"),
    ])
    def test_format_mismatch_returns_none_and_falls_to_tier3(self, monkeypatch, body):
        body = self._old_top_level_body() if body == "old" else body
        _patch(monkeypatch, body)
        assert tw_macro._try_cbc_ef15m01() is None
        r = tw_macro.fetch_cbc_m1b_m2()
        assert r["tier_used"] == 3 and r["is_proxy_tier"] is True
        assert r["source"] == "Yahoo:^TWII:proxy_tier3"

    def test_title_or_units_mismatch_returns_none(self, monkeypatch):
        body = ef15_body()
        body["meta"]["units"] = "新台幣千元,%"
        _patch(monkeypatch, body)
        assert tw_macro._try_cbc_ef15m01() is None

    def test_no_response_or_non_json_returns_none(self, monkeypatch, capsys):
        _patch(monkeypatch, None)
        assert tw_macro._try_cbc_ef15m01() is None
        _patch(monkeypatch, ValueError("Expecting value: line 1 column 1"))
        assert tw_macro._try_cbc_ef15m01() is None
        assert "JSON 解析失敗" in capsys.readouterr().out

    def test_parser_exception_is_contained_and_falls_to_tier3(self, monkeypatch, capsys):
        """期間年份 0000 → `datetime.date` 拋 ValueError（解析器照舊拋，排程路徑行為不變）；
        線上路徑須攔下、印出、回 None → Tier 3，不讓例外打斷三層備援。"""
        rows = ef15_rows()
        rows[0][0] = "0000M05"
        _patch(monkeypatch, ef15_body(rows))
        assert tw_macro._try_cbc_ef15m01() is None
        assert "解析例外 ValueError" in capsys.readouterr().out
        assert tw_macro.fetch_cbc_m1b_m2()["tier_used"] == 3

    @pytest.mark.parametrize("periods", [["0001M05"], ["0000M12", "0001M01"]])
    def test_latest_period_year_0001_does_not_leak_exception(self, monkeypatch, capsys, periods):
        """（批 M QA 實測重現）表內最新期間是 0001 年 → 推對帳窗口時 `ef15_fatal_from` 要回
        0000 年 → `datetime.date` 拋 ValueError。它發生在「推窗口」這一步（解析之前），
        須與其他解析失敗一樣攔下、印出、回 None → Tier 3，**不得冒出 `fetch_cbc_m1b_m2`**。"""
        rows = [[p] + ["-"] * 30 for p in periods]
        _patch(monkeypatch, ef15_body(rows))
        assert tw_macro._try_cbc_ef15m01() is None
        assert "解析例外 ValueError" in capsys.readouterr().out
        r = tw_macro.fetch_cbc_m1b_m2()
        assert r["tier_used"] == 3 and r["is_proxy_tier"] is True

    def test_parser_overflow_is_contained(self, monkeypatch, capsys):
        """（批 M QA QM7）餘額極大（> int64 上限 9.22e18）但彼此自洽 → 對帳放行，建 int64 欄時
        解析器拋 OverflowError；線上路徑須攔下、回 None → Tier 3。"""
        n = 30
        periods = [_p(*_shift(2024, 2, k)) for k in range(n)]
        body = ef15_body_from_levels(periods, [10 ** 19] * n, [3 * 10 ** 19] * n)
        with pytest.raises(OverflowError):          # 前提：解析器本身確實拋 OverflowError
            ef15.parse_cbc_ef15m01(body)
        _patch(monkeypatch, body)
        assert tw_macro._try_cbc_ef15m01() is None
        assert "解析例外 OverflowError" in capsys.readouterr().out
        r = tw_macro.fetch_cbc_m1b_m2()
        assert r["tier_used"] == 3 and r["is_proxy_tier"] is True


# ═════════════════════════════════════════════════════════════════════════════
class TestReconcileWindow:
    @pytest.mark.parametrize("per", ["2026M07", "2025M07"])   # 最新月、窗口起點（邊界）
    def test_mismatch_inside_window_returns_none(self, monkeypatch, capsys, per):
        rows = ef15_rows()
        _off(rows, per)
        _patch(monkeypatch, ef15_body(rows))
        assert tw_macro._try_cbc_ef15m01() is None
        out = capsys.readouterr().out
        assert "對帳不符" in out and "致命範圍 ≥ 2025-07" in out
        r = tw_macro.fetch_cbc_m1b_m2()
        assert r["tier_used"] == 3 and r["is_proxy_tier"] is True

    def test_real_row_mismatch_7_44_vs_7_42_returns_none(self, monkeypatch):
        rows = ef15_rows()
        _row_of(rows, "2026M07")[_yy_col(I_M2)] = "7.44"           # 真值 7.42
        _patch(monkeypatch, ef15_body(rows))
        assert tw_macro._try_cbc_ef15m01() is None

    def test_mismatch_before_window_only_warns(self, monkeypatch, capsys):
        rows = ef15_rows()
        _off(rows, "2025M06")                          # 窗口起點前一個月
        _patch(monkeypatch, ef15_body(rows))
        assert tw_macro._try_cbc_ef15m01() == (7.34, 7.42)
        out = capsys.readouterr().out
        assert "只警示" in out and "2025-06" in out
        # 同一份表若全表都算致命範圍 → 拒用：證明放行靠的是窗口，不是容差變寬
        assert ef15.parse_cbc_ef15m01(ef15_body(rows))[0] is None

    def test_window_follows_latest_month(self, monkeypatch):
        """窗口錨在「表內最新資料月」：拿掉 2026-05～07 三列後最新月變 2026-04 → 窗口 ≥ 2025-04，
        原本在窗口外的 2025-06 不符改為致命。"""
        rows = [r for r in ef15_rows() if r[0] < "2026M05"]
        _off(rows, "2025M06")
        _patch(monkeypatch, ef15_body(rows))
        assert ef15.ef15_latest_month(ef15_body(rows)) == dt.date(2026, 4, 1)
        assert tw_macro._try_cbc_ef15m01() is None


# ═════════════════════════════════════════════════════════════════════════════
class TestSharedParserSSOT:
    """同一份 EF15M01 回應全站只有一處解析實作（§2.1）：腳本舊名全部轉到共用模組。"""

    @pytest.mark.parametrize("old,new", [
        ("_ef15_yoy_tolerance_pp", "ef15_yoy_tolerance_pp"),
        ("_ef15_fatal_from", "ef15_fatal_from"),
        ("_ef15_labels", "ef15_labels"),
        ("_cbc_norm_label", "cbc_norm_label"),
        ("_EF15_FILE", "EF15_FILE"),
        ("_EF15_SERIES", "EF15_SERIES"),
        ("_EF15_PERIOD_RE", "EF15_PERIOD_RE"),
    ])
    def test_script_old_names_are_the_shared_objects(self, old, new):
        assert getattr(umh, old) is getattr(ef15, new)

    def test_script_getattr_unknown_name_raises_attribute_error(self):
        """（批 M QA QM19）腳本的 PEP 562 `__getattr__` 只轉發登記過的舊名；
        未知名稱照常拋 AttributeError（不得回 None 之類的預設值，否則拼錯字會靜默變成 None）。"""
        with pytest.raises(AttributeError, match="_no_such_ef15_name"):
            getattr(umh, "_no_such_ef15_name")
        assert not hasattr(umh, "_EF15_NOT_A_REAL_NAME")
        with pytest.raises(ImportError):
            exec("from scripts.update_macro_history import _no_such_ef15_name", {})

    def test_script_parser_delegates_and_keeps_its_contract(self, capsys):
        body = ef15_body()
        df, desc = umh._parse_cbc_ef15m01_levels(body)
        out = capsys.readouterr().out
        assert list(df.columns) == ["date", "m1b", "m2"]              # parquet 契約：三欄
        assert out.startswith("[finmind_m1m2/EF15M01] ✅")             # 排程 log 前綴不變
        full, desc2 = ef15.parse_cbc_ef15m01(body)
        assert desc == desc2
        assert list(full.columns) == ["date", "m1b", "m2", "m1b_yoy", "m2_yoy"]
        assert df.equals(full[["date", "m1b", "m2"]])

    def test_official_yoy_columns_keep_dash_as_nan(self):
        full, _ = ef15.parse_cbc_ef15m01(ef15_body())
        first = full.iloc[0]                                          # 1987-05：官方年增率 "-"
        assert first["date"] == dt.date(1987, 5, 1)
        assert first[["m1b_yoy", "m2_yoy"]].isna().all()
        last = full.iloc[-1]
        assert (last["m1b_yoy"], last["m2_yoy"]) == (7.34, 7.42)
        assert str(full["m1b_yoy"].dtype) == str(full["m2_yoy"].dtype) == "float64"

    def test_latest_month_scan_ignores_bad_rows(self):
        assert ef15.ef15_latest_month(None) is None
        assert ef15.ef15_latest_month({"data": {"dataSets": "x"}}) is None
        body = ef15_body()
        rows = body["data"]["dataSets"]
        rows += [["2026M13"] + ["-"] * 30, ["0000M01"] + ["-"] * 30, [], "junk"]
        assert ef15.ef15_latest_month(body) == dt.date(2026, 7, 1)

    def test_importing_script_does_not_import_src_data_macro(self):
        """腳本對 `src.*` 一律延遲 import（單一 dataset 的 import 失敗不拖垮整支腳本）；
        re-export 走 PEP 562，import 腳本本身不得連帶載入 `src.data.macro` 套件。"""
        code = ("import sys; import scripts.update_macro_history as m; "
                "print('src.data.macro' in sys.modules)")
        r = subprocess.run([sys.executable, "-c", code], cwd=_REPO, capture_output=True,
                           text=True, timeout=120)
        assert r.returncode == 0, r.stderr[-2000:]
        assert r.stdout.strip().splitlines()[-1] == "False"
