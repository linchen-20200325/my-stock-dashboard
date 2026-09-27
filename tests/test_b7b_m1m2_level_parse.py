"""B7b：`update_macro_history.fetch_finmind_m1m2` 不得再把 CBC PXWeb 的月變動額（流量）
當成餘額（存量）寫進 `finmind_m1m2.parquet`。

合成回應（**無網路**）：真實 CBC 回應的欄位順序未能在本容器實測（cpx.cbc.gov.tw 被
egress 拒絕），故測的是**解析規則**：標籤優先、無標籤時以定義辨識且須唯一、否則 fail loud。
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

import scripts.update_macro_history as umh


def _periods(n, y=2005):
    out = []
    for i in range(n):
        yy, mm = y + i // 12, i % 12 + 1
        out.append(f"{yy}M{mm:02d}")
    return out


def _levels(n, base, g):
    return [round(base * (1 + g) ** i) for i in range(n)]


def _flows(lv):
    return ["-"] + [str(b - a) for a, b in zip(lv, lv[1:])]


N = 60
M1B = _levels(N, 1_000_000, 0.006)
M2 = _levels(N, 3_000_000, 0.004)


def _resp(cols, labels=None):
    rows = [[p] + [c[i] for c in cols] for i, p in enumerate(_periods(N))]
    body = {"meta": {"title": "x", "filename": "EF19M01.px"}, "data": {"dataSets": rows}}
    if labels is not None:
        body["data"]["structure"] = {"columns": labels}
    return body


def _flow_with_sign_change(lv):
    # 流量：刻意讓部分月份為負（真實 CBC 月變動額會變號）
    f = [str(b - a) for a, b in zip(lv, lv[1:])]
    f = [str(-int(x)) if i % 3 == 0 else x for i, x in enumerate(f)]
    return [f[0]] + f


class TestParseLevelColumn:
    def test_labels_pick_level_not_flow(self):
        body = _resp([_flow_with_sign_change(M1B), [str(v) for v in M1B]],
                     labels=["期間", "M1B 月變動額", "M1B 日平均餘額"])
        rows, desc = umh._parse_cbc_pxweb_level(body, "EF19M01")
        assert rows is not None and "餘額" in desc
        assert [float(r["value"]) for r in rows] == [float(v) for v in M1B]

    def test_labels_prefer_daily_average_when_two_levels(self):
        body = _resp([[str(v) for v in M1B], [str(v * 1.01) for v in M1B]],
                     labels=["期間", "M1B 月底餘額", "M1B 日平均餘額"])
        rows, desc = umh._parse_cbc_pxweb_level(body, "EF19M01")
        assert "日平均" in desc
        assert float(rows[0]["value"]) == pytest.approx(M1B[0] * 1.01)

    def test_no_labels_unique_definitional_candidate(self):
        body = _resp([_flow_with_sign_change(M1B), [str(v) for v in M1B]])
        rows, desc = umh._parse_cbc_pxweb_level(body, "EF19M01")
        assert rows is not None and "col=2" in desc

    def test_no_labels_flow_only_fails_loud(self):
        body = _resp([_flow_with_sign_change(M1B)])
        rows, desc = umh._parse_cbc_pxweb_level(body, "EF19M01")
        assert rows is None

    def test_no_labels_two_level_like_columns_does_not_guess(self):
        body = _resp([[str(v) for v in M1B], [str(v * 1.01) for v in M1B]])
        rows, desc = umh._parse_cbc_pxweb_level(body, "EF19M01")
        assert rows is None and "2" in desc

    def test_label_says_level_but_values_negative_rejected(self):
        body = _resp([_flow_with_sign_change(M1B)], labels=["期間", "M1B 餘額"])
        rows, _ = umh._parse_cbc_pxweb_level(body, "EF19M01")
        assert rows is None


class _R:
    status_code = 200

    def __init__(self, body):
        self._b = body
        self.text = str(body)[:50]

    def json(self):
        return self._b


def _patch_cbc(monkeypatch, ef19, ef21):
    import src.data.macro.tw_macro as tw
    import src.data.proxy.proxy_helper as ph
    monkeypatch.setattr(tw, "fetch_cbc_ms1_rows", lambda *a, **k: None)
    calls = []

    def _fu(url, params=None, **k):
        calls.append(params.get("FileName"))
        return _R({"EF19M01": ef19, "EF21M01": ef21}[params["FileName"]])
    monkeypatch.setattr(ph, "fetch_url", _fu)
    return calls


class TestFetchEndToEnd:
    def test_stores_levels_and_sane_gap(self, monkeypatch):
        _patch_cbc(monkeypatch,
                   _resp([_flow_with_sign_change(M1B), [str(v) for v in M1B]]),
                   _resp([_flow_with_sign_change(M2), [str(v) for v in M2]]))
        df = umh.fetch_finmind_m1m2(dt.date(2000, 1, 1), dt.date(2030, 1, 1), "")
        assert not df.empty
        assert (df["m1b"] > 0).all() and (df["m2"] > 0).all()
        g = df["m1b_m2_gap"].dropna()
        assert len(g) == N - 12
        # 0.6%/月 vs 0.4%/月 複利 → YoY 差約 2.5pp
        assert g.between(2.0, 3.0).all()
        assert "level" in df["source"].iloc[0]

    def test_flow_only_response_writes_nothing(self, monkeypatch):
        _patch_cbc(monkeypatch,
                   _resp([_flow_with_sign_change(M1B)]),
                   _resp([_flow_with_sign_change(M2)]))
        df = umh.fetch_finmind_m1m2(dt.date(2000, 1, 1), dt.date(2030, 1, 1), "")
        assert df.empty

    def test_ef15_not_requested(self, monkeypatch):
        calls = _patch_cbc(monkeypatch,
                           _resp([[str(v) for v in M1B]]),
                           _resp([[str(v) for v in M2]]))
        umh.fetch_finmind_m1m2(dt.date(2000, 1, 1), dt.date(2030, 1, 1), "")
        assert "EF15M01" not in calls


class TestSanityGate:
    def test_negative_level_fails(self):
        df = pd.DataFrame({"m1b": [-1.0, 2.0], "m2": [5.0, 6.0], "m1b_m2_gap": [None, 1.0]})
        assert umh._m1m2_level_sanity(df)[0] is False

    def test_nan_gap_first_year_ok(self):
        df = pd.DataFrame({"m1b": [1.0, 2.0], "m2": [5.0, 6.0], "m1b_m2_gap": [None, 1.0]})
        assert umh._m1m2_level_sanity(df)[0] is True

    def test_committed_file_is_flagged_corrupt(self):
        """現行 commit 的檔（流量）必須被守門判不合格 → 下一次 cron 會整段重建。"""
        from pathlib import Path
        p = Path(__file__).resolve().parent.parent / "data_cache" / "finmind_m1m2.parquet"
        if not p.exists():
            pytest.skip("無既有檔")
        df = pd.read_parquet(p)
        if (df["m1b"] > 0).all() and (df["m2"] >= df["m1b"]).all():
            pytest.skip("既有檔已重建為合格存量")
        assert umh._m1m2_level_sanity(df)[0] is False


class TestUpdateOneRebuild:
    def _setup(self, monkeypatch, tmp_path, fetch_result):
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        bad = pd.DataFrame({"date": [dt.date(2026, 5, 1), dt.date(2026, 6, 1)],
                            "m1b": [-5.0, 3.0], "m2": [4.0, -1.0],
                            "m1b_m2_gap": [900.0, -40.0]})
        bad.to_parquet(tmp_path / "finmind_m1m2.parquet", index=False)
        seen = {}

        def _fake(start, end, token):
            seen["start"] = start
            return fetch_result
        monkeypatch.setitem(umh.FETCHERS, "finmind_m1m2", (_fake, True))
        return seen

    def test_corrupt_existing_triggers_full_rebuild_and_replaces(self, monkeypatch, tmp_path):
        good = pd.DataFrame({"date": [dt.date(2025, 1, 1), dt.date(2026, 7, 1)],
                             "m1b": [100.0, 110.0], "m2": [300.0, 310.0],
                             "m1b_m2_gap": [None, 2.0]})
        seen = self._setup(monkeypatch, tmp_path, good)
        today = dt.date(2026, 9, 27)
        meta = umh.update_one("finmind_m1m2", today, False, 20, "tok")
        assert seen["start"] == today - dt.timedelta(days=20 * 365)  # 整段，非 last+1
        out = pd.read_parquet(tmp_path / "finmind_m1m2.parquet")
        assert (out["m1b"] > 0).all() and len(out) == 2  # 壞列不殘留
        assert meta["last_error"] is None

    def test_rebuild_failure_keeps_file_and_reports(self, monkeypatch, tmp_path):
        self._setup(monkeypatch, tmp_path, pd.DataFrame())
        meta = umh.update_one("finmind_m1m2", dt.date(2026, 9, 27), False, 20, "tok")
        assert "sanity" in meta["last_error"]
        assert meta["last_updated"] is None
        assert len(pd.read_parquet(tmp_path / "finmind_m1m2.parquet")) == 2


class TestFinalGate:
    def test_levels_parse_but_violate_m2_ge_m1b_rejected(self, monkeypatch):
        """兩表各自像存量、但合起來違反定義（M2 < M1B）→ 整表拒寫（最後一道守門）。"""
        small_m2 = _levels(N, 500_000, 0.004)
        _patch_cbc(monkeypatch,
                   _resp([[str(v) for v in M1B]]),
                   _resp([[str(v) for v in small_m2]]))
        df = umh.fetch_finmind_m1m2(dt.date(2000, 1, 1), dt.date(2030, 1, 1), "")
        assert df.empty


class TestSeriesNameOnLabels:
    """QA 2026-09-27：有標籤時，選中的餘額欄必須是目標序列（防 M1A 冒充 M1B）。"""

    def test_m1a_only_balance_column_rejected(self):
        body = _resp([_flow_with_sign_change(M1B), [str(v) for v in M1B]],
                     labels=["期間", "M1B 月變動額", "M1A 日平均餘額"])
        rows, desc = umh._parse_cbc_pxweb_level(body, "EF19M01", series="M1B")
        assert rows is None and "M1B" in desc

    def test_m1b_and_m1a_both_balance_picks_m1b(self):
        m1a = _levels(N, 800_000, 0.005)
        body = _resp([[str(v) for v in m1a], [str(v) for v in M1B]],
                     labels=["期間", "M1A 日平均餘額", "Ｍ１Ｂ 日平均餘額"])   # 全形也要認得
        rows, desc = umh._parse_cbc_pxweb_level(body, "EF19M01", series="M1B")
        assert rows is not None and "１Ｂ" in desc
        assert [float(r["value"]) for r in rows] == [float(v) for v in M1B]

    def test_m2_label_lowercase_ok(self):
        body = _resp([[str(v) for v in M2]], labels=["期間", "m2 餘額"])
        rows, _ = umh._parse_cbc_pxweb_level(body, "EF21M01", series="M2")
        assert rows is not None

    def test_end_to_end_m1a_table_writes_nothing(self, monkeypatch):
        m1a = _levels(N, 800_000, 0.005)
        _patch_cbc(monkeypatch,
                   _resp([[str(v) for v in m1a]], labels=["期間", "M1A 餘額"]),
                   _resp([[str(v) for v in M2]], labels=["期間", "M2 餘額"]))
        assert umh.fetch_finmind_m1m2(dt.date(2000, 1, 1), dt.date(2030, 1, 1), "").empty


def test_rebuild_fetch_raises_reports_known_bad(monkeypatch, tmp_path):
    monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
    pd.DataFrame({"date": [dt.date(2026, 5, 1)], "m1b": [-5.0], "m2": [4.0],
                  "m1b_m2_gap": [900.0]}).to_parquet(tmp_path / "finmind_m1m2.parquet", index=False)

    def _boom(start, end, token):
        raise TimeoutError("cbc")
    monkeypatch.setitem(umh.FETCHERS, "finmind_m1m2", (_boom, True))
    meta = umh.update_one("finmind_m1m2", dt.date(2026, 9, 27), False, 20, "tok")
    assert "TimeoutError" in meta["last_error"] and "sanity" in meta["last_error"]
    assert meta["row_count"] == 1 and meta["last_updated"] is None
