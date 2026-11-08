"""tests/test_d3_fetch_outcome.py — D3（DEC-148）空抓取三態：NO_NEW_DATA／FETCH_FAILED／UNDETERMINED。

B1 範圍 ＝ producer（`scripts/update_macro_history.py` 的 fetcher 與 `update_one`）＋ PR 文案
（`scripts/publish_data_pr.py` 的 `assess_state`）。consumer／UI 留 B2，本檔不測。

三個最容易出錯的輸入（§6）：
1. 週末（或任何日期）的空回應、無正面證據 → 必須 UNDETERMINED，⛔ 不得因 weekday 推論成功；
2. 缺 attrs 的 fetcher（舊碼／新 fetcher 忘記標）→ UNDETERMINED（保守預設），不是 NO_NEW_DATA；
3. 空抓取不得動 Last Good：既有 parquet 位元組不變、last_updated／row_count 不變、不寫 0。

無網路：HTTP 一律 monkeypatch；寫檔導到 `tmp_path`。
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json

import pandas as pd
import pytest

import scripts.publish_data_pr as pdp
import scripts.update_macro_history as umh
from shared.fetch_outcome import (
    EVIDENCE_MAX_LEN,
    EVIDENCE_NOT_PROVIDED,
    FetchOutcome,
    parse_outcome,
    read_outcome,
    sanitize_evidence,
    tag_outcome,
)
from shared.staleness import EMPTY_FETCH_MARKER
from tests.test_b7b_r1_ef15m01_level import ef15_body, patch_ef15
from tests.test_dl_f1_r4_batch import _INST_DATES, _TODAY, _inst_parquet

NO_NEW, FAILED, UNDET = FetchOutcome.NO_NEW_DATA, FetchOutcome.FETCH_FAILED, FetchOutcome.UNDETERMINED


def _oc(df):
    return read_outcome(df)[0]


# ═════════════════════════════════════════════════════════════════════════════
# 1. shared/fetch_outcome.py 本體
# ═════════════════════════════════════════════════════════════════════════════
class TestSharedModule:
    def test_three_states_are_strings(self):
        assert {m.value for m in FetchOutcome} == {"NO_NEW_DATA", "FETCH_FAILED", "UNDETERMINED"}
        assert json.dumps({"k": FetchOutcome.NO_NEW_DATA}) == '{"k": "NO_NEW_DATA"}'

    def test_missing_attrs_is_undetermined_never_no_new_data(self):
        oc, ev = read_outcome(pd.DataFrame())
        assert oc is UNDET and ev == EVIDENCE_NOT_PROVIDED

    def test_roundtrip(self):
        df = tag_outcome(pd.DataFrame(), NO_NEW, "x")
        assert read_outcome(df) == (NO_NEW, "x")

    def test_failed_requires_evidence(self):
        with pytest.raises(ValueError):
            tag_outcome(pd.DataFrame(), FAILED, "")

    def test_failed_without_evidence_in_attrs_is_downgraded_not_trusted(self):
        df = pd.DataFrame()
        df.attrs.update(fetch_outcome="FETCH_FAILED", fetch_evidence="")
        assert _oc(df) is UNDET

    def test_garbage_value_is_undetermined(self):
        df = pd.DataFrame()
        df.attrs.update(fetch_outcome="OK", fetch_evidence="x")
        assert _oc(df) is UNDET
        assert parse_outcome("OK") is None and parse_outcome(None) is None

    def test_evidence_has_no_timestamps_and_is_bounded(self):
        s = sanitize_evidence("失敗 2026-11-08T09:30:12.123456+00:00 再 2026-11-08 09:30:12Z 結束")
        assert "2026-11-08T" not in s and "09:30" not in s and s.count("<ts>") == 2
        assert len(sanitize_evidence("x" * 1000)) <= EVIDENCE_MAX_LEN
        assert "\n" not in sanitize_evidence("a\nb")

    def test_not_mixed_with_freshness_status(self):
        """與 freshness 分離：本模組不 import freshness_policy／staleness，枚舉也不重疊。"""
        import shared.fetch_outcome as fo
        from shared.freshness_policy import FreshnessStatus
        import ast
        tree = ast.parse(open(fo.__file__, encoding="utf-8").read())
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        mods |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any("freshness" in (m or "") or "staleness" in (m or "") or m == "pandas" for m in mods), mods
        assert {m.value for m in FetchOutcome}.isdisjoint({m.value for m in FreshnessStatus})
        assert not isinstance(NO_NEW, FreshnessStatus)


# ═════════════════════════════════════════════════════════════════════════════
# 2. FinMind 抓取器（_finmind_get）
# ═════════════════════════════════════════════════════════════════════════════
class _Resp:
    def __init__(self, status=200, body=None, text="", json_exc=None, content=b""):
        self.status_code, self._body, self.text, self._exc, self.content = status, body, text, json_exc, content

    def json(self):
        if self._exc:
            raise self._exc
        return self._body


def _finmind(monkeypatch, resp=None, exc=None):
    def _get(*a, **k):
        if exc:
            raise exc
        return resp
    monkeypatch.setattr(umh.requests, "get", _get)
    return umh._finmind_get("TaiwanStockX", "", "2026-11-01", "2026-11-08", "tok")


class TestFinmindGet:
    def test_http200_status200_empty_list_is_no_new_data(self, monkeypatch):
        df = _finmind(monkeypatch, _Resp(200, {"status": 200, "data": []}))
        assert df.empty and _oc(df) is NO_NEW
        assert "data=[]" in read_outcome(df)[1]

    def test_http_error_is_fetch_failed(self, monkeypatch):
        df = _finmind(monkeypatch, _Resp(503, {}, text="down"))
        assert df.empty and _oc(df) is FAILED and "503" in read_outcome(df)[1]

    def test_api_status_not_200_is_fetch_failed(self, monkeypatch):
        df = _finmind(monkeypatch, _Resp(200, {"status": 402, "msg": "quota"}))
        assert _oc(df) is FAILED and "402" in read_outcome(df)[1]

    def test_network_exception_is_fetch_failed(self, monkeypatch):
        df = _finmind(monkeypatch, exc=ConnectionError("boom"))
        assert _oc(df) is FAILED and "ConnectionError" in read_outcome(df)[1]

    def test_unparseable_json_is_fetch_failed(self, monkeypatch):
        df = _finmind(monkeypatch, _Resp(200, json_exc=ValueError("bad json")))
        assert _oc(df) is FAILED

    def test_200_but_no_data_key_is_only_undetermined(self, monkeypatch):
        """成功回應但證據不足（沒有 data 清單）→ UNDETERMINED，不可當「無新資料」。"""
        df = _finmind(monkeypatch, _Resp(200, {"status": 200}))
        assert df.empty and _oc(df) is UNDET

    def test_non_empty_result_is_not_tagged(self, monkeypatch):
        df = _finmind(monkeypatch, _Resp(200, {"status": 200, "data": [{"date": "2026-11-06", "v": 1}]}))
        assert len(df) == 1 and "fetch_outcome" not in df.attrs


class TestFinmindWrappers:
    def test_inst_empty_passes_through_no_new_data(self, monkeypatch):
        monkeypatch.setattr(umh, "_finmind_get", lambda *a, **k: tag_outcome(pd.DataFrame(), NO_NEW, "e"))
        df = umh.fetch_finmind_inst(dt.date(2026, 11, 7), dt.date(2026, 11, 8), "tok")
        assert df.empty and _oc(df) is NO_NEW

    def test_inst_failure_passes_through_with_evidence(self, monkeypatch):
        monkeypatch.setattr(umh, "_finmind_get", lambda *a, **k: tag_outcome(pd.DataFrame(), FAILED, "HTTP 500"))
        df = umh.fetch_finmind_inst(dt.date(2026, 11, 7), dt.date(2026, 11, 8), "tok")
        assert (_oc(df), read_outcome(df)[1]) == (FAILED, "HTTP 500")

    def test_inst_rows_but_no_foreign_rows_is_undetermined(self, monkeypatch):
        raw = pd.DataFrame({"date": ["2026-11-06"], "name": ["Dealer_self"], "buy": [1], "sell": [1]})
        monkeypatch.setattr(umh, "_finmind_get", lambda *a, **k: raw)
        df = umh.fetch_finmind_inst(dt.date(2026, 11, 6), dt.date(2026, 11, 8), "tok")
        assert df.empty and _oc(df) is UNDET

    def test_inst_schema_drift_still_raises_not_swallowed(self, monkeypatch):
        raw = pd.DataFrame({"date": ["2026-11-06"], "buy": [1], "sell": [1]})   # 缺 name 欄
        monkeypatch.setattr(umh, "_finmind_get", lambda *a, **k: raw)
        with pytest.raises(RuntimeError):
            umh.fetch_finmind_inst(dt.date(2026, 11, 6), dt.date(2026, 11, 8), "tok")

    def test_margin_empty_passes_through(self, monkeypatch):
        monkeypatch.setattr(umh, "_finmind_get", lambda *a, **k: tag_outcome(pd.DataFrame(), NO_NEW, "e"))
        df = umh.fetch_finmind_margin(dt.date(2026, 11, 7), dt.date(2026, 11, 8), "tok")
        assert df.empty and _oc(df) is NO_NEW

    def test_margin_unusable_schema_is_fetch_failed(self, monkeypatch):
        raw = pd.DataFrame({"date": ["2026-11-06"], "weird": [1]})
        monkeypatch.setattr(umh, "_finmind_get", lambda *a, **k: raw)
        df = umh.fetch_finmind_margin(dt.date(2026, 11, 6), dt.date(2026, 11, 8), "tok")
        assert df.empty and _oc(df) is FAILED and "融資" in read_outcome(df)[1]


# ═════════════════════════════════════════════════════════════════════════════
# 3. twii_ohlcv（Yahoo chart）
# ═════════════════════════════════════════════════════════════════════════════
def _twii(monkeypatch, resp, start=dt.date(2026, 11, 7), end=dt.date(2026, 11, 8)):
    monkeypatch.setattr(umh, "_fetch_url_via_proxy", lambda *a, **k: resp)
    return umh.fetch_twii_ohlcv(start, end)


class TestTwii:
    def test_no_response_and_http_error_are_failed(self, monkeypatch):
        assert _oc(_twii(monkeypatch, None)) is FAILED
        df = _twii(monkeypatch, _Resp(500))
        assert _oc(df) is FAILED and "500" in read_outcome(df)[1]

    def test_non_json_is_failed(self, monkeypatch):
        assert _oc(_twii(monkeypatch, _Resp(200, json_exc=ValueError("x")))) is FAILED

    def test_chart_error_is_failed(self, monkeypatch):
        body = {"chart": {"result": None, "error": {"code": "Not Found", "description": "x"}}}
        df = _twii(monkeypatch, _Resp(200, body))
        assert _oc(df) is FAILED and "Not Found" in read_outcome(df)[1]

    @pytest.mark.parametrize("start", [dt.date(2026, 11, 7), dt.date(2026, 11, 9)])   # 週六／週一
    def test_empty_window_without_timestamp_is_undetermined_regardless_of_weekday(self, monkeypatch, start):
        """區間無交易日時 Yahoo 的合法形狀（result 內沒有 timestamp）與 schema 漂移不可分 → UNDETERMINED；
        ⛔ 不得因為 start 是週末就推論成功。"""
        body = {"chart": {"result": [{"meta": {}, "indicators": {"quote": [{}]}}], "error": None}}
        df = _twii(monkeypatch, _Resp(200, body), start=start, end=start)
        assert df.empty and _oc(df) is UNDET

    def test_all_nan_close_is_undetermined(self, monkeypatch):
        body = {"chart": {"result": [{"timestamp": [1762560000],
                                      "indicators": {"quote": [{"open": [None], "high": [None], "low": [None],
                                                                "close": [None], "volume": [None]}]}}]}}
        df = _twii(monkeypatch, _Resp(200, body))
        assert df.empty and _oc(df) is UNDET

    def test_rows_returned_untagged(self, monkeypatch):
        body = {"chart": {"result": [{"timestamp": [1762560000],
                                      "indicators": {"quote": [{"open": [1.0], "high": [2.0], "low": [0.5],
                                                                "close": [1.5], "volume": [10]}]}}]}}
        df = _twii(monkeypatch, _Resp(200, body))
        assert len(df) == 1 and "fetch_outcome" not in df.attrs


# ═════════════════════════════════════════════════════════════════════════════
# 4. finmind_m1m2（CBC EF15M01）
# ═════════════════════════════════════════════════════════════════════════════
class TestM1M2:
    def test_parsed_ok_but_zero_rows_in_window_is_no_new_data(self, monkeypatch):
        patch_ef15(monkeypatch, ef15_body())
        df = umh.fetch_finmind_m1m2(dt.date(2026, 8, 1), dt.date(2026, 11, 8), "")
        assert df.empty and _oc(df) is NO_NEW

    def test_rows_in_window_untagged(self, monkeypatch):
        patch_ef15(monkeypatch, ef15_body())
        df = umh.fetch_finmind_m1m2(dt.date(1980, 1, 1), dt.date(2030, 1, 1), "")
        assert not df.empty and "fetch_outcome" not in df.attrs

    def test_window_empty_but_full_table_sanity_fails_is_not_no_new_data(self, monkeypatch):
        patch_ef15(monkeypatch, ef15_body())
        monkeypatch.setattr(umh, "_m1m2_level_sanity", lambda df: (False, "壞"))
        df = umh.fetch_finmind_m1m2(dt.date(2026, 8, 1), dt.date(2026, 11, 8), "")
        assert df.empty and _oc(df) is UNDET

    def test_http_error_is_failed(self, monkeypatch):
        import src.data.macro.tw_macro as tw
        import src.data.proxy.proxy_helper as ph
        monkeypatch.setattr(tw, "fetch_cbc_ms1_rows", lambda *a, **k: None)
        monkeypatch.setattr(ph, "fetch_url", lambda *a, **k: _Resp(503))
        df = umh.fetch_finmind_m1m2(dt.date(2026, 8, 1), dt.date(2026, 11, 8), "")
        assert df.empty and _oc(df) is FAILED and "503" in read_outcome(df)[1]

    def test_no_response_is_failed(self, monkeypatch):
        import src.data.macro.tw_macro as tw
        import src.data.proxy.proxy_helper as ph
        monkeypatch.setattr(tw, "fetch_cbc_ms1_rows", lambda *a, **k: None)
        monkeypatch.setattr(ph, "fetch_url", lambda *a, **k: None)
        df = umh.fetch_finmind_m1m2(dt.date(2026, 8, 1), dt.date(2026, 11, 8), "")
        assert _oc(df) is FAILED

    def test_bad_json_is_failed(self, monkeypatch):
        import src.data.macro.tw_macro as tw
        import src.data.proxy.proxy_helper as ph
        monkeypatch.setattr(tw, "fetch_cbc_ms1_rows", lambda *a, **k: None)
        monkeypatch.setattr(ph, "fetch_url", lambda *a, **k: _Resp(200, json_exc=ValueError("x"), text="<html>"))
        assert _oc(umh.fetch_finmind_m1m2(dt.date(2026, 8, 1), dt.date(2026, 11, 8), "")) is FAILED

    def test_parse_rejected_is_failed_with_reason(self, monkeypatch):
        """形狀不符（舊格式頂層 DataSet）→ 解析被拒 ＝ 解析／欄位驗證失敗 ⇒ FETCH_FAILED。"""
        patch_ef15(monkeypatch, {"DataSet": [], "Structure": {}})
        df = umh.fetch_finmind_m1m2(dt.date(2026, 8, 1), dt.date(2026, 11, 8), "")
        assert df.empty and _oc(df) is FAILED and "EF15M01" in read_outcome(df)[1]


# ═════════════════════════════════════════════════════════════════════════════
# 5. tw_pmi（data.gov.tw 6100）
# ═════════════════════════════════════════════════════════════════════════════
_PMI_META = {"result": {"resources": [{"url": "https://x/Download.ashx?u=1", "format": "CSV"}]}}
_PMI_CSV = "Date,PMI,NMI\n202604,50.1,-\n202605,51.2,-\n202606,60.7,-\n".encode()


def _pmi(monkeypatch, handler, start=dt.date(2026, 7, 1), end=dt.date(2026, 11, 8)):
    monkeypatch.setattr(umh, "_fetch_url_via_proxy", handler)
    return umh.fetch_tw_pmi_history(start, end)


def _pmi_ok(url, **k):
    if "Download" in url:
        return _Resp(200, content=_PMI_CSV)
    return _Resp(200, _PMI_META)


class TestTwPmi:
    def test_csv_parsed_but_no_month_in_window_is_no_new_data(self, monkeypatch):
        df = _pmi(monkeypatch, _pmi_ok)
        assert df.empty and _oc(df) is NO_NEW

    def test_rows_in_window_untagged(self, monkeypatch):
        df = _pmi(monkeypatch, _pmi_ok, start=dt.date(2026, 6, 1))
        assert len(df) == 1 and "fetch_outcome" not in df.attrs

    def test_all_http_errors_is_failed(self, monkeypatch):
        df = _pmi(monkeypatch, lambda url, **k: _Resp(500))
        assert df.empty and _oc(df) is FAILED and "500" in read_outcome(df)[1]

    def test_no_response_is_failed(self, monkeypatch):
        assert _oc(_pmi(monkeypatch, lambda url, **k: None)) is FAILED

    def test_csv_unparseable_is_failed(self, monkeypatch):
        def h(url, **k):
            return _Resp(200, content=b"junk,here\n1,2\n") if "Download" in url else _Resp(200, _PMI_META)
        df = _pmi(monkeypatch, h)
        assert _oc(df) is FAILED and "無有效列" in read_outcome(df)[1]

    def test_200_with_no_resources_is_only_undetermined(self, monkeypatch):
        df = _pmi(monkeypatch, lambda url, **k: _Resp(200, {"result": {}}))
        assert df.empty and _oc(df) is UNDET


# ═════════════════════════════════════════════════════════════════════════════
# 6. update_one：metadata（additive 欄、Last Good、恢復、向後相容）
# ═════════════════════════════════════════════════════════════════════════════
def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _fetcher_returning(df):
    return lambda start, end, token=None: df


@pytest.fixture
def inst_env(monkeypatch, tmp_path):
    monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
    _inst_parquet(tmp_path / "finmind_inst.parquet", _INST_DATES)
    return tmp_path


def _run_inst(monkeypatch, df):
    monkeypatch.setitem(umh.FETCHERS, "finmind_inst", (lambda s, e, t: df, True))
    return umh.update_one("finmind_inst", _TODAY, False, 20, "tok")


class TestUpdateOne:
    @pytest.mark.parametrize("outcome,ev", [(NO_NEW, "ok-evidence"), (FAILED, "http 500"), (UNDET, "unsure")])
    def test_each_state_is_written_additively_and_legacy_fields_unchanged(self, monkeypatch, inst_env, outcome, ev):
        before = _sha(inst_env / "finmind_inst.parquet")
        meta = _run_inst(monkeypatch, tag_outcome(pd.DataFrame(), outcome, ev))
        # 舊欄位逐一照舊
        assert meta["name"] == "finmind_inst" and meta["last_error"] == EMPTY_FETCH_MARKER
        assert meta["last_updated"] == "2026-09-25" and meta["row_count"] == len(_INST_DATES)
        # 新欄 additive
        assert meta["fetch_outcome"] == outcome.value and meta["fetch_evidence"] == ev
        assert set(meta) == {"name", "last_updated", "row_count", "last_error", "fetch_outcome", "fetch_evidence"}
        # Last Good：parquet 位元組不變、沒有被寫入 0
        assert _sha(inst_env / "finmind_inst.parquet") == before
        assert (pd.read_parquet(inst_env / "finmind_inst.parquet")["foreign_buy"] != 0).all()

    def test_untagged_empty_frame_is_undetermined(self, monkeypatch, inst_env):
        meta = _run_inst(monkeypatch, pd.DataFrame())
        assert meta["fetch_outcome"] == "UNDETERMINED" and meta["fetch_evidence"] == EVIDENCE_NOT_PROVIDED
        assert meta["last_error"] == EMPTY_FETCH_MARKER

    def test_weekend_style_empty_without_evidence_is_never_inferred_as_success(self, monkeypatch, inst_env):
        """今天是週六、fetcher 回沒有任何標記的空表 → UNDETERMINED（不由 weekday 推論 NO_NEW_DATA）。"""
        sat = dt.date(2026, 11, 7)
        assert sat.weekday() == 5
        monkeypatch.setitem(umh.FETCHERS, "finmind_inst", (lambda s, e, t: pd.DataFrame(), True))
        meta = umh.update_one("finmind_inst", sat, False, 20, "tok")
        assert meta["fetch_outcome"] == "UNDETERMINED"

    def test_no_existing_file_keeps_zero_and_null_but_labels(self, monkeypatch, tmp_path):
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        meta = _run_inst(monkeypatch, tag_outcome(pd.DataFrame(), NO_NEW, "e"))
        assert (meta["row_count"], meta["last_updated"]) == (0, None)
        assert not (tmp_path / "finmind_inst.parquet").exists()      # 空抓取不建檔、不寫 0 列

    def test_marker_with_failed_always_carries_evidence(self, monkeypatch, inst_env):
        """不變式：標記 EMPTY_FETCH_MARKER ⇒ 若 outcome 是 FETCH_FAILED，必有錯誤證據（缺證據的 FAILED 會被降級）。"""
        bad = pd.DataFrame()
        bad.attrs.update(fetch_outcome="FETCH_FAILED", fetch_evidence="")
        meta = _run_inst(monkeypatch, bad)
        assert meta["last_error"] == EMPTY_FETCH_MARKER
        assert meta["fetch_outcome"] != "FETCH_FAILED" or meta["fetch_evidence"]
        assert meta["fetch_outcome"] == "UNDETERMINED"

    def test_recovery_clears_outcome_and_last_error(self, monkeypatch, inst_env):
        m1 = _run_inst(monkeypatch, tag_outcome(pd.DataFrame(), NO_NEW, "e"))
        assert m1["fetch_outcome"] == "NO_NEW_DATA"
        new = pd.DataFrame({"date": [dt.date(2026, 9, 28)], "foreign_buy": [1.5],
                            "source": ["s"], "fetched_at": ["t"]})
        m2 = _run_inst(monkeypatch, new)
        assert m2["last_error"] is None and "fetch_outcome" not in m2 and "fetch_evidence" not in m2
        assert m2["row_count"] == len(_INST_DATES) + 1 and m2["last_updated"] == "2026-09-28"

    def test_already_latest_skip_writes_no_outcome(self, monkeypatch, inst_env):
        called = []
        monkeypatch.setitem(umh.FETCHERS, "finmind_inst", (lambda s, e, t: called.append(1), True))
        meta = umh.update_one("finmind_inst", dt.date(2026, 9, 25), False, 20, "tok")   # last >= today → 不發請求
        assert called == [] and "fetch_outcome" not in meta and meta["last_error"] is None

    def test_exception_path_unchanged_shape_and_still_an_error(self, monkeypatch, inst_env):
        """例外路徑的 metadata 形狀被舊測試釘死（整本 dict 相等）→ 不加新欄；仍是『有 last_error 且非空抓取標記』。"""
        def boom(*a, **k):
            raise RuntimeError("upstream down")
        monkeypatch.setitem(umh.FETCHERS, "finmind_inst", (boom, True))
        meta = umh.update_one("finmind_inst", _TODAY, False, 20, "tok")
        assert meta["last_error"] == "RuntimeError: upstream down" and "fetch_outcome" not in meta

    def test_corrupt_existing_rebuild_failure_keeps_composite_last_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        _inst_parquet(tmp_path / "zz_probe.parquet", _INST_DATES[:2])
        monkeypatch.setitem(umh.FETCHERS, "zz_probe", (lambda s, e, t: tag_outcome(pd.DataFrame(), NO_NEW, "e"), True))
        monkeypatch.setitem(umh._EXISTING_SANITY_GATES, "zz_probe", lambda df: (False, "壞"))
        meta = umh.update_one("zz_probe", _TODAY, False, 20, "tok")
        assert meta["last_error"] == "抓取結果為空；既有檔 sanity 不過,待重建" and meta["last_updated"] is None


# ═════════════════════════════════════════════════════════════════════════════
# 7. publish_data_pr：PR 文案分流
# ═════════════════════════════════════════════════════════════════════════════
def _meta_bytes(datasets):
    return json.dumps({"updated_at": "x", "datasets": datasets}).encode()


def _ds(last_error=EMPTY_FETCH_MARKER, outcome=None, evidence="e"):
    d = {"name": "n", "last_updated": "2026-09-25", "row_count": 5, "last_error": last_error}
    if outcome is not None:
        d["fetch_outcome"], d["fetch_evidence"] = outcome, evidence
    return d


def _state(datasets, today="2026-11-09", new_rows=None):
    return pdp.assess_state({pdp.MACRO_META: _meta_bytes(datasets)}, new_rows or {}, today)


class TestPrWording:
    def test_only_fetch_failed_goes_to_failure_line(self):
        st = _state({"a": _ds(outcome="FETCH_FAILED", evidence="HTTP 500"),
                     "b": _ds(outcome="NO_NEW_DATA"), "c": _ds(outcome="UNDETERMINED")})
        assert "a:" in st["failure"] and "HTTP 500" in st["failure"]
        assert "b:" not in st["failure"] and "c:" not in st["failure"]

    def test_no_new_data_goes_to_line2_without_claiming_fresh(self):
        st = _state({"b": _ds(outcome="NO_NEW_DATA")})
        assert st["failure"].startswith("無（") and "FETCH_FAILED" in st["failure"]
        assert "無新資料（來源讀取成功" in st["holiday"] and "['b']" in st["holiday"]
        assert "不代表資料為最新" in st["holiday"]
        assert "最新鮮" not in st["holiday"] and "fresh" not in st["holiday"].lower()

    def test_undetermined_says_cannot_determine(self):
        st = _state({"c": _ds(outcome="UNDETERMINED")})
        assert st["failure"].startswith("無（")
        assert "無法判定" in st["holiday"] and "['c']" in st["holiday"] and "來源讀取成功" not in st["holiday"]

    def test_weekend_today_does_not_turn_undetermined_into_holiday_or_success(self):
        st = _state({"c": _ds(outcome="UNDETERMINED")}, today="2026-11-07")     # 週六
        assert "休市" not in st["holiday"] and "無法判定" in st["holiday"]

    def test_legacy_metadata_without_outcome_is_unchanged(self):
        st = _state({"a": _ds(outcome=None)})
        assert "a: 抓取結果為空" in st["failure"] and "（FETCH_FAILED" not in st["failure"]
        assert st["holiday"].startswith("有更新失敗")

    def test_non_marker_error_is_never_softened_even_if_outcome_says_no_new_data(self):
        st = _state({"a": _ds(last_error="抓取結果為空；既有檔 sanity 不過,待重建", outcome="NO_NEW_DATA"),
                     "b": _ds(last_error="RuntimeError: x", outcome="UNDETERMINED")})
        assert "a:" in st["failure"] and "b:" in st["failure"]

    def test_unknown_outcome_value_falls_back_to_failure(self):
        st = _state({"a": _ds(outcome="MAYBE")})
        assert "a:" in st["failure"]

    def test_mixed_failure_and_no_new_data_both_visible(self):
        st = _state({"a": _ds(outcome="FETCH_FAILED"), "b": _ds(outcome="NO_NEW_DATA")})
        assert "a:" in st["failure"] and "['b']" in st["holiday"] and "有更新失敗" in st["holiday"]

    @pytest.mark.parametrize("outcome,failure_has,holiday_has", [
        ("FETCH_FAILED", "n: 抓取結果為空", "有更新失敗"),
        ("NO_NEW_DATA", "無（", "無新資料（來源讀取成功"),
        ("UNDETERMINED", "無（", "無法判定（空抓取"),
    ])
    def test_rendered_pr_body_matches_actual_state(self, outcome, failure_has, holiday_has):
        d = _ds(outcome=outcome)
        d["name"] = "n"
        st = _state({"n": d})
        body = pdp.build_pr_body("macro-history", [pdp.MACRO_META], None, "t", st, "sha")
        l1 = [ln for ln in body.splitlines() if ln.startswith("- ① 更新失敗：")][0]
        l2 = [ln for ln in body.splitlines() if ln.startswith("- ② 休市／無新資料：")][0]
        assert failure_has in l1 and holiday_has in l2
        if outcome != "FETCH_FAILED":
            assert "n: 抓取結果為空" not in l1


class TestPublishMetadataHandling:
    def _meta(self, **over):
        return json.dumps({"updated_at": "A", "datasets": {"x": _ds(outcome="NO_NEW_DATA", **over)}}).encode()

    def test_outcome_change_is_substantive(self):
        old = self._meta()
        new = json.dumps({"updated_at": "B", "datasets": {"x": _ds(outcome="UNDETERMINED")}}).encode()
        assert pdp.json_substantive_change(pdp.MACRO_META, old, new) is True

    def test_same_outcome_same_evidence_only_updated_at_is_not_substantive(self):
        old = self._meta()
        new = json.dumps({"updated_at": "B", "datasets": {"x": _ds(outcome="NO_NEW_DATA")}}).encode()
        assert pdp.json_substantive_change(pdp.MACRO_META, old, new) is False

    def test_evidence_change_is_substantive_so_it_must_be_stable(self):
        old = self._meta()
        new = json.dumps({"updated_at": "A", "datasets": {"x": _ds(outcome="NO_NEW_DATA", evidence="other")}}).encode()
        assert pdp.json_substantive_change(pdp.MACRO_META, old, new) is True

    def test_producer_evidence_is_stable_across_runs(self, monkeypatch, tmp_path):
        """同一個失敗連兩輪（不同 fetched 時間）→ evidence 位元組相同（否則每天都會開出實質變更的 PR）。"""
        import time
        monkeypatch.setattr(umh.requests, "get", lambda *a, **k: _Resp(503, {}, text="down"))
        a = read_outcome(umh._finmind_get("D", "", "2026-11-01", "2026-11-08", "t"))
        time.sleep(0.01)
        b = read_outcome(umh._finmind_get("D", "", "2026-11-01", "2026-11-08", "t"))
        assert a == b

    def test_consistency_flags_invalid_outcome_and_failed_without_evidence(self):
        probs = pdp._consistency_problems(pdp.MACRO_META, {"datasets": {
            "a": {"last_error": "x", "row_count": 1, "fetch_outcome": "OOPS"},
            "b": {"last_error": "x", "row_count": 1, "fetch_outcome": "FETCH_FAILED"},
            "c": {"last_error": "x", "row_count": 1, "fetch_outcome": "FETCH_FAILED", "fetch_evidence": "e"},
            "d": {"last_error": "x", "row_count": 1, "fetch_outcome": "NO_NEW_DATA"}}})
        assert any("a:" in p and "三態" in p for p in probs)
        assert any("b:" in p and "fetch_evidence" in p for p in probs)
        assert not any(p.startswith("datasets.c") or p.startswith("datasets.d") for p in probs)
