"""批 R4：總經排程與季校準的資料層缺口（DL-f1-s34／s39／s40／s41／s42／s43）。

DL-f1-s40（中）：`update_macro_history.fetch_finmind_m1m2` 的 Tier 1 ms1.json 分支不驗單位量級；ms1 只要
回 ≥ 13 列就不再請求 EF15M01；`_m1m2_level_sanity` 沒有量級帶；ms1 欄名／形狀一變就回空表、不退到
EF15M01。修正後：寫出的列只來自 EF15M01（每次都請求）；ms1 只做形狀／量級檢查、結果只進 log（不同
來源／口徑的列不得疊進同一份 parquet —— 現行 parquet 全出自 EF15M01）；寫檔前守門多一條百萬元量級帶
（沿用 `MONEY_SUPPLY_LEVEL_SANITY_*_YI` 換算，不新增常數），同一條也是既有檔守門。

fixture：EF15M01 回應沿用 `tests/test_b7b_r1_ef15m01_level.py` 的 `ef15_body()`／`ef15_rows()`／
`patch_ef15()`（真實三列 ＋ 自洽合成序列，說明見該檔檔頭）。ms1.json 形狀沿用既有測試（`年月`／`M1B`／`M2`）。
無網路：CBC／FinMind 回應一律 monkeypatch；寫檔一律導到 `tmp_path`，不碰 repo 的 `data_cache/`。
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

import scripts.update_macro_history as umh
from tests.test_b7b_r1_ef15m01_level import (
    I_M1B,
    I_M2,
    _lv_col,
    ef15_body,
    ef15_rows,
    patch_ef15,
)

_TODAY = dt.date(2026, 9, 28)
_ALL = (dt.date(1980, 1, 1), dt.date(2030, 1, 1))
_EF15_SRC_PREFIX = "CBC:PXWeb:EF15M01:daily_avg_level["


# ═════════════════════════════════════════════════════════════════════════════
# DL-f1-s40：M1B／M2 寫出的列只來自 EF15M01；任何來源都過百萬元量級帶
# ═════════════════════════════════════════════════════════════════════════════
def _patch_cbc(monkeypatch, *, ms1_rows=None, ef15_ok: bool = True) -> list:
    """ms1（Tier 1）回 `ms1_rows`（None = 兩個網址都失敗）；EF15M01：`ef15_ok` → fixture 表，否則無回應。
    回 PXWeb 的請求紀錄（FileName 清單）。"""
    if ef15_ok:
        return patch_ef15(monkeypatch, ef15_body(), ms1_rows=ms1_rows)
    import src.data.macro.tw_macro as tw
    import src.data.proxy.proxy_helper as ph
    monkeypatch.setattr(tw, "fetch_cbc_ms1_rows", lambda *a, **k: ms1_rows)
    calls: list = []

    def _fu(url, params=None, **k):
        calls.append((params or {}).get("FileName"))
        return None
    monkeypatch.setattr(ph, "fetch_url", _fu)
    return calls


def _ms1_like(scale: float = 1.0, *, keys=("年月", "M1B", "M2")) -> list[dict]:
    """由 EF15M01 fixture 的 M1B／M2 餘額組 ms1.json 形狀的列（2024-01～2026-07，31 列；1987 兩列略過 ——
    ms1 的日期規則只認 20xx）。scale：1.0 = 同單位同口徑（逐月與 EF15M01 相同）；1.03 = 同單位、
    口徑差約 3%（月底 vs 日平均的量級）；0.01 = 億元（百萬元 ÷ 100）。"""
    k_date, k1, k2 = keys
    return [{k_date: f"{r[0][:4]}-{r[0][5:]}",
             k1: round(int(r[_lv_col(I_M1B)]) * scale, 2),
             k2: round(int(r[_lv_col(I_M2)]) * scale, 2)}
            for r in ef15_rows() if r[0].startswith("20")]


def _bad_month_ms1() -> list[dict]:
    """同單位同口徑，但有一列的年月是 2026-13 → 日期正規化時 `datetime.date` 拋 ValueError。"""
    rows = _ms1_like(1.0)
    rows[-1] = dict(rows[-1], 年月="2026-13")
    return rows


def _fetch(monkeypatch, capsys, **kw):
    calls = _patch_cbc(monkeypatch, **kw)
    capsys.readouterr()
    df = umh.fetch_finmind_m1m2(*_ALL, "")
    return calls, df, capsys.readouterr().out


def _ms1_verdicts(out: str) -> list[str]:
    """`fetch_finmind_m1m2` 對 ms1 回應的判定行（「不採用」或「通過但仍不寫出」）。"""
    return [ln for ln in out.splitlines()
            if ln.startswith("[finmind_m1m2/ms1] ") and ("不採用" in ln or "仍不寫出" in ln)]


@pytest.fixture
def ef15_only(monkeypatch, capsys) -> pd.DataFrame:
    """基準：ms1 兩個網址都失敗時的輸出（= 只有 EF15M01）。"""
    calls, df, _out = _fetch(monkeypatch, capsys, ms1_rows=None)
    assert calls == ["EF15M01"] and not df.empty
    assert df["source"].str.startswith(_EF15_SRC_PREFIX).all()
    return df


class TestS40Ms1IsNeverWritten:
    @pytest.mark.parametrize("ms1_rows,verdict", [
        pytest.param(None, None, id="ms1失敗"),
        pytest.param(_ms1_like(1.0), "形狀與百萬元量級皆通過", id="同單位同口徑"),
        pytest.param(_ms1_like(1.03), "形狀與百萬元量級皆通過", id="同單位不同口徑約3pct"),
        pytest.param(_ms1_like(0.01), "量級不符", id="億元"),
        pytest.param(_ms1_like(1.0, keys=("期間", "貨幣總計數M1B", "貨幣總計數M2")), "形狀不符",
                     id="欄名形狀改變"),
        pytest.param(_ms1_like(1.0)[:5], "不是 ≥ 13 列", id="不足13列"),
        pytest.param(_bad_month_ms1(), "解析例外 ValueError", id="解析例外"),
    ])
    def test_every_ms1_outcome_falls_through_to_ef15(self, monkeypatch, capsys, ef15_only,
                                                     ms1_rows, verdict):
        """(b)(c)：ms1 不論失敗、形狀不符、量級不符、解析出例外、或全部檢查都通過 —— 都接著請求 EF15M01
        （不回空表），寫出的列全出自 EF15M01，且與 ms1 失敗時逐欄相同（fetched_at 為抓取時戳，除外）。"""
        calls, df, out = _fetch(monkeypatch, capsys, ms1_rows=ms1_rows)
        assert calls == ["EF15M01"], out
        assert df["source"].str.startswith(_EF15_SRC_PREFIX).all()
        pd.testing.assert_frame_equal(df.drop(columns="fetched_at"),
                                      ef15_only.drop(columns="fetched_at"))
        lines = _ms1_verdicts(out)
        if verdict is None:
            assert lines == [], out
            return
        assert len(lines) == 1 and verdict in lines[0], out
        assert lines[0].endswith("→ 改取 EF15M01"), lines[0]
        if verdict.startswith("形狀與"):                   # 通過檢查者：log 講清楚為何仍不寫出
            assert "仍不寫出" in lines[0] and "口徑無從驗證" in lines[0], lines[0]

    @pytest.mark.parametrize("scale", [1.0, 1.03], ids=["同單位同口徑", "同單位不同口徑約3pct"])
    def test_ef15_failure_is_not_replaced_by_ms1(self, monkeypatch, capsys, scale):
        """(c)：EF15M01 失敗時，ms1 就算通過形狀與量級檢查也不拿來替代 → 本輪不寫出（空表）。"""
        calls, df, out = _fetch(monkeypatch, capsys, ms1_rows=_ms1_like(scale), ef15_ok=False)
        assert calls == ["EF15M01"]
        assert df.empty, df.head()
        assert "無可用資料 → 本輪不寫出" in out and "ms1 不作替代來源" in out, out

    @pytest.mark.parametrize("scale", [1.0, 1.03, 0.01], ids=["同單位同口徑", "同單位不同口徑約3pct", "億元"])
    def test_update_one_never_stacks_ms1_rows_onto_the_ef15_parquet(self, monkeypatch, tmp_path,
                                                                   ef15_only, scale):
        """(c) 端到端：既有 parquet（EF15M01，到 2026-06）＋ ms1 有回應 → 增量只疊上 EF15M01 的 2026-07。"""
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        existing = ef15_only[ef15_only["date"] < dt.date(2026, 7, 1)].reset_index(drop=True)
        existing.to_parquet(tmp_path / "finmind_m1m2.parquet", compression="snappy", index=False)
        _patch_cbc(monkeypatch, ms1_rows=_ms1_like(scale))
        meta = umh.update_one("finmind_m1m2", _TODAY, False, 20, "")
        assert meta["last_error"] is None and meta["last_updated"] == "2026-07-01", meta
        after = pd.read_parquet(tmp_path / "finmind_m1m2.parquet")
        assert len(after) == len(existing) + 1 == meta["row_count"]
        assert after["source"].str.startswith(_EF15_SRC_PREFIX).all()
        assert str(after["m1b"].dtype) == str(after["m2"].dtype) == "int64"
        last = after.iloc[-1]
        assert last["date"] == dt.date(2026, 7, 1)
        assert (last["m1b"], last["m2"]) == (30530948, 70224762)      # EF15M01 2026-07 原值（非 ms1 的值）


class TestS40LevelBand:
    def test_band_is_the_export_yi_band_converted_to_million_twd(self):
        from shared.margin_schema import TWD_PER_YI
        from shared.signal_thresholds import (
            MONEY_SUPPLY_LEVEL_SANITY_MAX_YI,
            MONEY_SUPPLY_LEVEL_SANITY_MIN_YI,
            MONEY_SUPPLY_TWD_PER_CACHE_UNIT,
        )
        lo, hi = umh._m1m2_level_band()
        assert (lo, hi) == (1e6, 5e8)
        assert (lo, hi) == (MONEY_SUPPLY_LEVEL_SANITY_MIN_YI * TWD_PER_YI / MONEY_SUPPLY_TWD_PER_CACHE_UNIT,
                            MONEY_SUPPLY_LEVEL_SANITY_MAX_YI * TWD_PER_YI / MONEY_SUPPLY_TWD_PER_CACHE_UNIT)

    def test_band_follows_the_constants_not_a_copy(self, monkeypatch):
        """沿用既有常數（SSOT）：常數一改，帶子跟著改 —— 不是把 1e6／5e8 另抄一份。"""
        import shared.signal_thresholds as st
        monkeypatch.setattr(st, "MONEY_SUPPLY_LEVEL_SANITY_MIN_YI", 2e4)
        monkeypatch.setattr(st, "MONEY_SUPPLY_LEVEL_SANITY_MAX_YI", 3e6)
        assert umh._m1m2_level_band() == (2e6, 3e8)

    @pytest.mark.parametrize("scale,ok", [(1.0, True), (0.01, False), (1000.0, False), (1e-6, False)],
                             ids=["百萬元", "億元", "千元", "兆元"])
    def test_sanity_rejects_every_unit_off_by_100x_or_more(self, ef15_only, scale, ok):
        df = ef15_only[["date", "m1b", "m2", "m1b_m2_gap"]].copy()
        df["m1b"] = df["m1b"] * scale
        df["m2"] = df["m2"] * scale                      # gap 是比值 → 換單位不變，只剩量級帶攔得住
        got, msg = umh._m1m2_level_sanity(df)
        assert got is ok, msg
        if not ok:
            assert f"百萬元量級帶外 [1e+06, 5e+08]:{len(df)}" in msg, msg

    def test_band_is_closed_and_checks_both_columns(self):
        lo, hi = umh._m1m2_level_band()

        def _ok(m1b, m2):
            return umh._m1m2_level_sanity(pd.DataFrame(
                {"m1b": [m1b], "m2": [m2], "m1b_m2_gap": [float("nan")]}))[0]
        assert _ok(lo, hi) is True                          # 閉區間：恰在邊界 → 通過
        assert _ok(lo - 1, hi) is False                     # m1b 低於下界（m2 ≥ m1b 仍成立）
        assert _ok(lo, hi + 1) is False                     # m2 高於上界
        assert _ok(hi + 1, hi + 2) is False                 # m1b 高於上界
        assert _ok(lo - 2, lo - 1) is False                 # m2 低於下界

    def test_nan_level_is_rejected(self):
        """原本三條對 NaN 餘額都判通過；量級帶把它判帶外。"""
        df = pd.DataFrame({"m1b": [30_000_000.0, float("nan")], "m2": [70_000_000.0, 70_100_000.0],
                           "m1b_m2_gap": [float("nan"), float("nan")]})
        assert umh._m1m2_level_sanity(df)[0] is False

    def test_prewrite_gate_does_not_trust_the_parser(self, monkeypatch, capsys):
        """(a)：寫檔前守門不假設資料來自哪一支 —— 就算解析端交出億元的表（例：單位檢查被繞過），也不寫出。"""
        good, desc = umh._parse_cbc_ef15m01_levels(ef15_body())
        yi = good.copy()
        yi["m1b"] = yi["m1b"] / 100
        yi["m2"] = yi["m2"] / 100
        monkeypatch.setattr(umh, "_parse_cbc_ef15m01_levels", lambda sdmx, fatal_from=None: (yi, desc))
        calls, df, out = _fetch(monkeypatch, capsys, ms1_rows=None)
        assert calls == ["EF15M01"]
        assert df.empty
        assert "sanity 不過,拒寫" in out and "百萬元量級帶外" in out, out

    def test_existing_parquet_with_yi_rows_is_rebuilt(self, monkeypatch, tmp_path, capsys):
        """既有檔守門同一條量級帶：parquet 混進億元列（前三條定義檢查照樣通過）→ 下一次排程整段重建。"""
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        _patch_cbc(monkeypatch, ms1_rows=None)
        good = umh.fetch_finmind_m1m2(_TODAY - dt.timedelta(days=20 * 365), _TODAY, "")
        bad = good.astype({"m1b": "float64", "m2": "float64"})
        tail = bad.index[-3:]
        bad.loc[tail, ["m1b", "m2"]] = bad.loc[tail, ["m1b", "m2"]] / 100      # 最新 3 個月混成億元
        assert (bad["m1b"] > 0).all() and (bad["m2"] >= bad["m1b"]).all()       # ① ② 照樣通過
        bad.to_parquet(tmp_path / "finmind_m1m2.parquet", compression="snappy", index=False)
        capsys.readouterr()
        meta = umh.update_one("finmind_m1m2", _TODAY, False, 20, "")
        out = capsys.readouterr().out
        assert "既有檔 sanity 不過" in out and "改整段重建" in out, out
        after = pd.read_parquet(tmp_path / "finmind_m1m2.parquet")
        lo, hi = umh._m1m2_level_band()
        assert after["m1b"].between(lo, hi).all() and after["m2"].between(lo, hi).all()
        assert after["source"].str.startswith(_EF15_SRC_PREFIX).all()
        assert meta["last_error"] is None and len(after) == meta["row_count"] == len(good)
