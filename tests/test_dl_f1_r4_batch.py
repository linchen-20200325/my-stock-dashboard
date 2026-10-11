"""批 R4：總經排程與季校準的資料層缺口（DL-f1-s34／s39／s40／s41／s42／s43）。

DL-f1-s40（中）：`update_macro_history.fetch_finmind_m1m2` 的 Tier 1 ms1.json 分支不驗單位量級；ms1 只要
回 ≥ 13 列就不再請求 EF15M01；`_m1m2_level_sanity` 沒有量級帶；ms1 欄名／形狀一變就回空表、不退到
EF15M01。修正後：寫出的列只來自 EF15M01（每次都請求）；ms1 只做形狀／量級檢查、結果只進 log（不同
來源／口徑的列不得疊進同一份 parquet —— 現行 parquet 全出自 EF15M01）；寫檔前守門多一條百萬元量級帶
（沿用 `MONEY_SUPPLY_LEVEL_SANITY_*_YI` 換算，不新增常數），同一條也是既有檔守門。
DL-f1-s43：`fetch_finmind_inst` 的 buy／sell 原本 `fillna(0)` 後相減 → 改為某日任一外資組成列缺值就整日
不產出（log 剔除日期數）、缺欄 raise；有值的日子以修正前算式當對照組，逐位相同。
DL-f1-s41：`parse_cbc_ef15m01` 範圍前對帳警示原本印 `infpp`、不分原因 → 依原因分類（比照 DL-f1-s19）；
只有容差類時整行與修正前逐字相同。
DL-f1-s39：`update_macro_history` 檔頭 docstring 四處照實更正（與程式碼互相對照）。
DL-f1-s42：缺 token 被跳過的表，metadata 的 row_count／last_updated 改描述現有 parquet；讀取端判定不變。
DL-f1-s34：`calibrate_macro_traffic.emit_thresholds_json` 寫檔保留未知鍵與既有註解；讀檔失敗不再靜默。

fixture：EF15M01 回應沿用 `tests/test_b7b_r1_ef15m01_level.py` 的 `ef15_body()`／`ef15_rows()`／
`patch_ef15()`（真實三列 ＋ 自洽合成序列，說明見該檔檔頭）；對帳 helper 沿用 `tests/test_dl_f1_r2_batch.py`。
ms1.json 形狀沿用既有測試（`年月`／`M1B`／`M2`）。
無網路：CBC／FinMind 回應一律 monkeypatch；寫檔一律導到 `tmp_path`，不碰 repo 的 `data_cache/` 與
根目錄 `macro_thresholds.json`（只讀、複製到 tmp）。
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

import scripts.update_macro_history as umh
from src.data.macro import cbc_ef15m01 as ef15
from tests.test_b7b_r1_ef15m01_level import (
    I_M1B,
    I_M2,
    _lv_col,
    ef15_body,
    ef15_rows,
    patch_ef15,
)
from tests.test_dl_f1_r2_batch import _off_by, _t12_at_or_below_half_step

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


def _gate(m1b, m2, gap):
    return umh._m1m2_level_sanity(pd.DataFrame({"m1b": m1b, "m2": m2, "m1b_m2_gap": gap}))


_OK_M1B = [30_000_000.0, 30_500_000.0]          # EF15M01 量級（百萬元），全在量級帶內
_OK_M2 = [70_000_000.0, 70_200_000.0]
_OK_GAP = [float("nan"), 1.0]


def _verdict(n_bad, n_rows=2, *, lv=0, order=0, gap=0, band=0) -> str:
    """`_m1m2_level_sanity` 拒寫訊息裡的四條計數（依序 ①②③④）。"""
    return (f"{n_bad}/{n_rows} 列不合格（餘額≤0:{lv}、m2<m1b:{order}、|gap|>30pp:{gap}、"
            f"百萬元量級帶外 [1e+06, 5e+08]:{band}）")


class TestS40EachGateConditionStillDiscriminates:
    """批 R4 獨立 QA（B1／N2）：新加的④（量級帶）不得遮住既有三條。每條各用一組「只違反它、其餘三條
    都通過」的帶內輸入單獨釘住 —— 刪掉哪一條，哪一條測試轉紅。
    ①（餘額 ≤ 0）目前被④完全涵蓋：帶下界 1e6 百萬元 > 0，任何 ≤ 0 的餘額必在帶外 ⇒ 找不到「只違反①」
    的輸入，刪掉①屬等價突變（量級帶常數未被調到 ≤ 0 之前）；①仍保留作定義層的防線。"""

    def test_baseline_passes_all_four(self):
        ok, msg = _gate(_OK_M1B, _OK_M2, _OK_GAP)
        assert ok is True, msg

    def test_only_m2_ge_m1b_violated(self):
        """②：M1B／M2 兩欄對調 —— 兩欄都在帶內、都 > 0、gap 正常，只有 m2 ≥ m1b 攔得住。"""
        ok, msg = _gate(_OK_M2, _OK_M1B, _OK_GAP)
        assert ok is False
        assert _verdict(2, order=2) in msg, msg

    @pytest.mark.parametrize("gap,ok", [(30.0, True), (-30.0, True), (30.5, False), (-30.5, False),
                                        (13976.0, False)],
                             ids=["正30邊界", "負30邊界", "正30.5", "負30.5", "流量量級"])
    def test_only_gap_bound_violated(self, gap, ok):
        """③：|gap| ≤ 30pp（恰 30 通過）—— 餘額在帶內、m2 ≥ m1b，只有 ③ 攔得住。"""
        got, msg = _gate(_OK_M1B, _OK_M2, [float("nan"), gap])
        assert got is ok, msg
        if not ok:
            assert _verdict(1, gap=1) in msg, msg

    def test_only_band_violated(self):
        """④：一列略低於帶下界（999,999 百萬元）—— > 0、m2 ≥ m1b、gap 正常，只有 ④ 攔得住。"""
        ok, msg = _gate([999_999.0, _OK_M1B[1]], _OK_M2, _OK_GAP)
        assert ok is False
        assert _verdict(1, band=1) in msg, msg

    def test_nonpositive_level_is_always_out_of_band_too(self):
        """①被④涵蓋的佐證：餘額 ≤ 0 的列，兩條同時計數（找不到只觸發①的輸入）。"""
        ok, msg = _gate([0.0, _OK_M1B[1]], _OK_M2, _OK_GAP)
        assert ok is False
        assert _verdict(1, lv=1, band=1) in msg, msg


# ═════════════════════════════════════════════════════════════════════════════
# DL-f1-s43：外資淨買賣超不以 0 代入缺值；缺欄 fail loud
# ═════════════════════════════════════════════════════════════════════════════
_INST_NAMES = ("Foreign_Investor", "Foreign_Dealer_Self", "Investment_Trust", "Dealer_self",
               "Dealer_Hedging", "total")                  # FinMind 實際 name 值（見 fetch_finmind_inst 註解）
_INST_DATES = ("2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25")
# 批 Z40（客戶 Q-z24＝A'）：列級 source 由 `...:Foreign` 改為 `...:Foreign_Investor`（＝ 列級口徑標記，
#   舊列仍是 `...:Foreign`，見 update_macro_history.fetch_finmind_inst docstring）。
_INST_SRC = "FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign_Investor"


def _raw_inst(seed: int = 20260928) -> pd.DataFrame:
    """FinMind TaiwanStockTotalInstitutionalInvestors 形狀（buy／sell 單位：元，量級 1e9～3e11）。"""
    import random
    rnd = random.Random(seed)
    rows = [{"buy": rnd.randrange(10**9, 3 * 10**11), "date": d, "name": n,
             "sell": rnd.randrange(10**9, 3 * 10**11)}
            for d in _INST_DATES for n in _INST_NAMES]
    return pd.DataFrame(rows)[["buy", "date", "name", "sell"]]


def _pre_s43_formula(raw: pd.DataFrame) -> pd.DataFrame:
    """修正前的算式（`fillna(0)` 在此只當對照組 —— 有值的日子，修正後必須與它逐位相同）。

    批 Z40（客戶 Q-z24＝A' 官方口徑）：篩列由 `str.contains("Foreign")`（Foreign_Investor ＋ Foreign_Dealer_Self）
    改為只取 `name == "Foreign_Investor"`（外資不含外資自營商）；對照組的 fillna(0)／相減／依日加總算式不變。"""
    fi = raw[raw["name"].astype(str) == "Foreign_Investor"].copy()
    fi["foreign_buy"] = (pd.to_numeric(fi.get("buy"), errors="coerce").fillna(0)
                         - pd.to_numeric(fi.get("sell"), errors="coerce").fillna(0)) / 1e8
    out = fi.groupby("date", as_index=False)["foreign_buy"].sum()
    out["date"] = pd.to_datetime(out["date"]).dt.date
    return out


def _run_inst(monkeypatch, raw: pd.DataFrame) -> pd.DataFrame:
    monkeypatch.setattr(umh, "_finmind_get", lambda *a, **k: raw.copy())
    return umh.fetch_finmind_inst(dt.date(2026, 9, 21), dt.date(2026, 9, 28), "tok")


def _assert_bitwise(got: pd.DataFrame, exp: pd.DataFrame) -> None:
    pd.testing.assert_frame_equal(got[["date", "foreign_buy"]].reset_index(drop=True),
                                  exp[["date", "foreign_buy"]].reset_index(drop=True), check_exact=True)
    assert (got["foreign_buy"].to_numpy().view("i8") == exp["foreign_buy"].to_numpy().view("i8")).all()


class TestS43ForeignNetNeverFabricated:
    def test_all_values_present_output_is_bitwise_unchanged(self, monkeypatch, capsys):
        raw = _raw_inst()
        got = _run_inst(monkeypatch, raw)
        _assert_bitwise(got, _pre_s43_formula(raw))
        assert list(got.columns) == ["date", "foreign_buy", "source", "fetched_at"]
        assert (got["source"] == _INST_SRC).all()
        assert "剔除" not in capsys.readouterr().out

    @pytest.mark.parametrize("col", ["buy", "sell"])
    # 批 Z40：外資組成列只剩 Foreign_Investor（Foreign_Dealer_Self 不再是外資組成列 ——
    #   其缺值不剔除該日，改由下方 test_missing_value_outside_foreign_rows_changes_nothing 參數化守）
    @pytest.mark.parametrize("name", ["Foreign_Investor"])
    @pytest.mark.parametrize("bad", [None, float("nan"), "--"], ids=["None", "NaN", "非數值"])
    def test_one_missing_component_drops_the_whole_day(self, monkeypatch, capsys, col, name, bad):
        clean = _raw_inst()
        raw = clean.astype({col: object})
        day = _INST_DATES[2]
        raw.loc[(raw["date"] == day) & (raw["name"] == name), col] = bad
        # 修正前：該日照樣產出一個數（缺的那格當 0 → 賣超缺值捏成大正數、買超缺值捏成大負數）
        pre = _pre_s43_formula(raw).set_index("date")["foreign_buy"]
        clean_val = _pre_s43_formula(clean).set_index("date")["foreign_buy"][dt.date(2026, 9, 23)]
        assert pre[dt.date(2026, 9, 23)] != clean_val
        assert bool(pre[dt.date(2026, 9, 23)] > clean_val) is (col == "sell")
        got = _run_inst(monkeypatch, raw)
        out = capsys.readouterr().out
        assert dt.date(2026, 9, 23) not in set(got["date"])                 # 整日不產出，不做部分加總
        exp = _pre_s43_formula(clean)
        _assert_bitwise(got, exp[exp["date"] != dt.date(2026, 9, 23)])   # 其餘日子逐位不變
        assert "剔除 1 個日期" in out and day in out and "1 列缺值" in out, out

    def test_counts_every_dropped_day(self, monkeypatch, capsys):
        # 批 Z40：原以 Foreign_Dealer_Self 缺值造 3 個剔除日（＋1 列 Foreign_Investor）＝「3 日／4 列」；
        #   外資自營商已不是外資組成列 ⇒ 改以 Foreign_Investor 缺值造 3 個剔除日（每日 1 列 ⇒「3 日／3 列」），
        #   另在第 3 日放一列 Foreign_Dealer_Self 缺值 ⇒ 該日**不得**被剔除。
        raw = _raw_inst().astype({"sell": object})
        for d in _INST_DATES[:2] + _INST_DATES[3:4]:
            raw.loc[(raw["date"] == d) & (raw["name"] == "Foreign_Investor"), "sell"] = None
        raw.loc[(raw["date"] == _INST_DATES[2]) & (raw["name"] == "Foreign_Dealer_Self"), "sell"] = None
        got = _run_inst(monkeypatch, raw)
        out = capsys.readouterr().out
        assert [str(d) for d in got["date"]] == [_INST_DATES[2], _INST_DATES[4]]
        assert "剔除 3 個日期" in out and "3 列缺值" in out, out

    def test_every_day_missing_gives_empty_frame(self, monkeypatch, capsys):
        raw = _raw_inst().astype({"buy": object})
        raw.loc[raw["name"] == "Foreign_Investor", "buy"] = None
        got = _run_inst(monkeypatch, raw)
        assert got.empty
        assert f"剔除 {len(_INST_DATES)} 個日期" in capsys.readouterr().out

    # 批 Z40：外資自營商（Foreign_Dealer_Self）不再是外資組成列 ⇒ 與投信／自營商同列此處
    @pytest.mark.parametrize("other", ["Investment_Trust", "Foreign_Dealer_Self", "Dealer_self", "Dealer_Hedging"])
    def test_missing_value_outside_foreign_rows_changes_nothing(self, monkeypatch, capsys, other):
        """只有外資的組成列算數：投信／自營商／外資自營商列缺值不影響外資淨額，該日照常產出。"""
        clean = _raw_inst()
        raw = clean.astype({"sell": object})
        raw.loc[(raw["date"] == _INST_DATES[1]) & (raw["name"] == other), "sell"] = None
        got = _run_inst(monkeypatch, raw)
        _assert_bitwise(got, _pre_s43_formula(clean))
        assert "剔除" not in capsys.readouterr().out

    def test_day_without_a_dealer_self_row_is_summed_as_before(self, monkeypatch):
        """某日根本沒有 Foreign_Dealer_Self 列 —— 不是缺值，照舊以有的列加總（與修正前逐位相同）。"""
        raw = _raw_inst()
        raw = raw[~((raw["date"] == _INST_DATES[1]) & (raw["name"] == "Foreign_Dealer_Self"))]
        got = _run_inst(monkeypatch, raw)
        assert len(got) == len(_INST_DATES)
        _assert_bitwise(got, _pre_s43_formula(raw))

    @pytest.mark.parametrize("drop", ["buy", "sell", "date"])
    def test_missing_column_raises_and_update_one_keeps_the_parquet(self, monkeypatch, tmp_path, drop):
        raw = _raw_inst().drop(columns=[drop])
        with pytest.raises(RuntimeError, match=rf"缺欄 \['{drop}'\]"):
            _run_inst(monkeypatch, raw)
        # 經 update_one：last_error 記下真正原因（不是「抓取結果為空」），既有 parquet 一個 byte 不動
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        pd.DataFrame({"date": [dt.date(2026, 9, 18)], "foreign_buy": [12.5], "source": [_INST_SRC],
                      "fetched_at": ["2026-09-18T12:00:00+00:00"]}).to_parquet(
            tmp_path / "finmind_inst.parquet", index=False)
        before = (tmp_path / "finmind_inst.parquet").read_bytes()
        meta = umh.update_one("finmind_inst", dt.date(2026, 9, 28), False, 20, "tok")
        assert meta["last_error"].startswith("RuntimeError: 缺欄"), meta
        assert (tmp_path / "finmind_inst.parquet").read_bytes() == before


# ═════════════════════════════════════════════════════════════════════════════
# DL-f1-s41：致命範圍之前對帳不符（只警示）那一行 —— 不再印 infpp、依原因分類
# ═════════════════════════════════════════════════════════════════════════════
_WHY_T12 = "t−12 餘額 ≤ 捨入半階,無法對帳"                # cbc_ef15m01 對帳段既有字樣，逐字
_WHY_TOL = "自算年增率 vs 表內官方年增率，超出捨入容差"      # DL-f1-s19 拒用句既有字樣，逐字
_TAG = "[cbc_ef15m01/EF15M01]"


def _warn_line(rows, fatal_from, capsys) -> str:
    capsys.readouterr()
    df, why = ef15.parse_cbc_ef15m01(ef15_body(rows), fatal_from)
    out = capsys.readouterr().out
    assert df is not None, why                                    # 範圍前不符只警示，照樣產出
    lines = [ln for ln in out.splitlines() if "之前對帳不符" in ln]
    assert len(lines) == 1, out
    assert "inf" not in lines[0].split(" first10=")[0], lines[0]  # 摘要段不得出現 inf
    assert "infpp" not in out
    return lines[0]


class TestS41PreFatalWarnLine:
    def test_only_t12_rows_name_the_cause_not_infpp(self, capsys):
        rows = ef15_rows()
        _t12_at_or_below_half_step(rows, "2025M01", I_M1B, "0")        # 致命範圍 ≥ 2025-02 之前
        line = _warn_line(rows, dt.date(2025, 2, 1), capsys)
        assert line.startswith(f"{_TAG} ⚠️ 致命範圍（≥ 2025-02）之前對帳不符 1 列（不影響寫入的資料，"
                               f"只警示、不拒用）：{_WHY_T12} first10=["), line
        assert "max|Δ|" not in line                                    # 沒有可算差值的列 → 不印 max|Δ|

    def test_only_tolerance_rows_line_is_unchanged(self, capsys):
        """只有容差類：與修正前逐字相同（`max|Δ|={max(第 5 格):.6f}pp first10=…`）。"""
        import ast
        rows = ef15_rows()
        _off_by(rows, "2025M01", I_M2)
        line = _warn_line(rows, dt.date(2025, 2, 1), capsys)
        first10 = ast.literal_eval(line.split(" first10=", 1)[1])
        mx = max(w[4] for w in first10)
        assert line == (f"{_TAG} ⚠️ 致命範圍（≥ 2025-02）之前對帳不符 1 列（不影響寫入的資料，"
                        f"只警示、不拒用）：max|Δ|={mx:.6f}pp first10={first10!r}"), line
        assert 0.015 < mx < 0.025

    def test_both_causes_listed_with_counts_and_max_over_tolerance_rows_only(self, capsys):
        rows = ef15_rows()
        _off_by(rows, "2025M06", I_M1B)                                   # |Δ| ≈ 0.02
        _off_by(rows, "2025M07", I_M2, by=0.05)                           # |Δ| ≈ 0.05（最大）
        _t12_at_or_below_half_step(rows, "2025M03", I_M2, "0")
        line = _warn_line(rows, dt.date(2026, 5, 1), capsys)              # 致命範圍 ≥ 2026-05 之前
        summary = line.split(" first10=")[0]
        assert summary.startswith(f"{_TAG} ⚠️ 致命範圍（≥ 2026-05）之前對帳不符 3 列（不影響寫入的資料，"
                                  f"只警示、不拒用）：{_WHY_TOL} 2 列（max|Δ|=0.0"), summary
        assert summary.endswith(f"pp）；{_WHY_T12} 1 列"), summary
        mx = float(summary.split("max|Δ|=")[1].split("pp")[0])
        assert 0.045 < mx < 0.055                                         # 只在容差類裡取，不是 inf

    def test_two_t12_rows_single_cause_no_count(self, capsys):
        rows = ef15_rows()
        _t12_at_or_below_half_step(rows, "2025M03", I_M1B, "0")
        _t12_at_or_below_half_step(rows, "2025M04", I_M2, "-3")
        line = _warn_line(rows, dt.date(2026, 5, 1), capsys)
        assert f"之前對帳不符 2 列（不影響寫入的資料，只警示、不拒用）：{_WHY_T12} first10=[" in line, line


# ═════════════════════════════════════════════════════════════════════════════
# DL-f1-s39：update_macro_history 檔頭 docstring 四處照實更正（與程式碼互相對照）
# ═════════════════════════════════════════════════════════════════════════════
class TestS39HeaderDocstringMatchesCode:
    @staticmethod
    def _line(prefix: str) -> str:
        """檔頭「data_cache/… ← …」那一列（含續行）。"""
        lines = umh.__doc__.splitlines()
        i = next(k for k, ln in enumerate(lines) if ln.startswith(prefix))
        out = [lines[i]]
        for ln in lines[i + 1:]:
            if not ln.startswith(" " * 20):
                break
            out.append(ln.strip())
        return "".join(out)

    def test_twii_is_the_yahoo_chart_api_not_yfinance(self):
        import inspect
        line = self._line("data_cache/twii_ohlcv.parquet")
        assert "query1.finance.yahoo.com/v8/finance/chart" in line and "yfinance via" not in line, line
        assert "query1.finance.yahoo.com/v8/finance/chart" in inspect.getsource(umh.fetch_twii_ohlcv)
        assert "import yfinance" not in inspect.getsource(umh)

    def test_inst_is_foreign_net_only(self):
        import inspect
        line = self._line("data_cache/finmind_inst.parquet")
        assert "外資淨買賣超" in line and "Foreign_Investor" in line and "Foreign_Dealer_Self" in line, line
        assert "三大法人總買賣超" not in umh.__doc__
        assert "外資淨買賣超" in umh.fetch_finmind_inst.__doc__
        assert "三大法人總買賣超" not in umh.fetch_finmind_inst.__doc__
        # 批 Z40（Q-z24＝A'）：篩列由 `str.contains("Foreign")` 改為只取 Foreign_Investor（L0 判定 SSOT）
        _src = inspect.getsource(umh.fetch_finmind_inst)
        assert 'map(is_finmind_foreign_investor)' in _src and 'str.contains("Foreign"' not in _src

    def test_finmind_tables_are_direct_not_proxy(self):
        import inspect
        doc = " ".join(umh.__doc__.split())
        assert "FinMind 兩張表（finmind_inst、finmind_margin）直連" in doc, doc
        src = inspect.getsource(umh._finmind_get)
        assert "requests.get(" in src and "fetch_url" not in src.split('"""')[-1]   # 函式本體直連

    def test_macro_last_good_is_listed(self):
        import inspect
        import os

        import src.data.macro.macro_core as mc
        line = self._line("data_cache/macro_last_good/tw_pmi.json")
        assert "durable" in line and "fetch_tw_pmi" in line and "_macro_durable_save" in line, line
        assert mc._MACRO_DURABLE_DIR == os.path.join("data_cache", "macro_last_good")
        assert '_macro_durable_save("tw_pmi"' in inspect.getsource(umh.main)

    def test_ms1_status_citation_points_to_a_record_that_exists(self):
        """批 R4 獨立 QA N1：檔頭原本引用「程式內註記『已不再可用，留邏輯防禦』」，那句註解已隨 DL-f1-s40
        移除 → 只剩檔頭自己引用自己。改引 `tw_macro.fetch_cbc_m1b_m2` docstring 的探針紀錄；被引用的
        事實必須真的在該處，檔頭若再引用「程式內註記」，引用的字句必須真的在程式本體裡。"""
        import inspect
        import re

        from src.data.macro import tw_macro
        doc = " ".join(umh.__doc__.split())
        body = inspect.getsource(umh).split('"""', 2)[2]          # 檔頭 docstring 之後的程式本體
        for quoted in re.findall(r"程式內註記「([^」]+)」", doc):
            assert quoted in body, f"檔頭引用的程式內註記「{quoted}」在程式本體裡找不到"
        tw_doc = " ".join(tw_macro.fetch_cbc_m1b_m2.__doc__.split())
        assert "`tw_macro.fetch_cbc_m1b_m2` docstring" in doc, doc
        for fact in ("run 36408641177", "`/public/data/ms1.json` 回 HTTP 404",
                     "`/tw/public/data/ms1.json` 有回應但未通過 `fetch_cbc_ms1_rows`"):
            assert fact in doc and fact in tw_doc, fact


# ═════════════════════════════════════════════════════════════════════════════
# DL-f1-s42：因缺 token 被跳過的表，metadata 的 row_count／last_updated 描述現有 parquet
# ═════════════════════════════════════════════════════════════════════════════
def _inst_parquet(path, dates) -> None:
    pd.DataFrame({"date": [dt.date.fromisoformat(d) for d in dates],
                  "foreign_buy": [1.5 * (k + 1) for k in range(len(dates))],
                  "source": [_INST_SRC] * len(dates),
                  "fetched_at": ["2026-09-26T09:00:00+00:00"] * len(dates)}).to_parquet(path, index=False)


class TestS42SkippedTableMetadata:
    def test_docstring_no_longer_claims_only_run_tables_are_written(self):
        doc = " ".join(umh.__doc__.split())
        assert "只寫本次有跑的表" not in doc
        assert "因缺 FINMIND_TOKEN 被跳過的表**也會寫進去**" in doc, doc
        assert "row_count／last_updated 描述磁碟上現有的 parquet" in doc, doc

    def test_skip_describes_the_existing_parquet(self, monkeypatch, tmp_path):
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        _inst_parquet(tmp_path / "finmind_inst.parquet", _INST_DATES[:3])

        def _must_not_fetch(*a, **k):
            raise AssertionError("缺 token 時不得呼叫抓取函式")
        monkeypatch.setitem(umh.FETCHERS, "finmind_inst", (_must_not_fetch, True))
        meta = umh.update_one("finmind_inst", _TODAY, False, 20, "")
        assert meta == {"name": "finmind_inst", "last_updated": "2026-09-23", "row_count": 3,
                        "last_error": "FINMIND_TOKEN 未設定"}

    def test_skip_without_parquet_stays_zero_and_null(self, monkeypatch, tmp_path):
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        meta = umh.update_one("finmind_inst", _TODAY, False, 20, "")
        assert meta == {"name": "finmind_inst", "last_updated": None, "row_count": 0,
                        "last_error": "FINMIND_TOKEN 未設定"}

    def test_skip_with_unreadable_parquet_stays_zero_and_null(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        (tmp_path / "finmind_inst.parquet").write_bytes(b"not a parquet")
        meta = umh.update_one("finmind_inst", _TODAY, False, 20, "")
        assert (meta["row_count"], meta["last_updated"]) == (0, None)
        assert "讀現有 Parquet 失敗" in capsys.readouterr().out            # 讀不到照舊 log，不假裝有資料

    def test_skip_does_not_vouch_for_a_known_bad_file(self, monkeypatch, tmp_path):
        """需要 token、又有既有檔守門的表（目前沒有 —— 以測試用表模擬）：守門不過 → 不背書 last_updated。"""
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        _inst_parquet(tmp_path / "zz_probe.parquet", _INST_DATES[:2])
        monkeypatch.setitem(umh.FETCHERS, "zz_probe", (lambda *a, **k: pd.DataFrame(), True))
        monkeypatch.setitem(umh._EXISTING_SANITY_GATES, "zz_probe", lambda df: (False, "壞"))
        meta = umh.update_one("zz_probe", _TODAY, False, 20, "")
        assert meta == {"name": "zz_probe", "last_updated": None, "row_count": 2,
                        "last_error": "FINMIND_TOKEN 未設定；既有檔 sanity 不過,待重建"}
        monkeypatch.setitem(umh._EXISTING_SANITY_GATES, "zz_probe", lambda df: (True, "ok"))
        assert umh.update_one("zz_probe", _TODAY, False, 20, "")["last_updated"] == "2026-09-22"

    def test_main_only_run_and_readers_see_the_same_verdict(self, monkeypatch, tmp_path):
        """`--only` 無 token 端到端：metadata 的跳過表有真實 row_count／last_updated；讀取端的判定不變
        （last_error 仍是「FINMIND_TOKEN 未設定」→ 校準閘門照樣擋下）。"""
        import json

        import scripts.calibrate_health_weights as chw
        import src.data.macro.macro_core as mc
        from src.data.macro.macro_cache_reader import compute_cache_staleness
        monkeypatch.delenv("FINMIND_TOKEN", raising=False)
        monkeypatch.setattr("sys.argv", ["update_macro_history.py", "--only", "finmind_inst,finmind_margin"])
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        monkeypatch.setattr(umh, "META_PATH", tmp_path / "metadata.json")
        monkeypatch.setattr(mc, "fetch_tw_pmi", lambda **k: {"value": None, "is_stale": False})
        _inst_parquet(tmp_path / "finmind_inst.parquet", _INST_DATES)
        assert umh.main() == 0
        ds = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))["datasets"]
        assert ds == {
            "finmind_inst": {"name": "finmind_inst", "last_updated": "2026-09-25",
                             "row_count": len(_INST_DATES), "last_error": "FINMIND_TOKEN 未設定"},
            "finmind_margin": {"name": "finmind_margin", "last_updated": None, "row_count": 0,
                               "last_error": "FINMIND_TOKEN 未設定"},
        }
        st = compute_cache_staleness("finmind_inst", cache_dir=tmp_path, today=dt.date(2026, 9, 26))
        assert st["upstream_error"] == "FINMIND_TOKEN 未設定" and st["meta_last_updated"] == "2026-09-25"
        bad = {s["dataset"]: s for s in chw.check_inputs_fresh(tmp_path, today=dt.date(2026, 9, 26))}
        assert "finmind_inst" in bad                                 # 跳過的表照樣擋下（因 last_error）
        assert bad["finmind_inst"]["is_stale"] is False
        # 對照組：把 metadata 換回修正前的寫法（row_count 0、last_updated null），判定逐欄相同
        # （只有顯示用的 meta_last_updated 不同）
        ds["finmind_inst"].update(row_count=0, last_updated=None)
        (tmp_path / "metadata.json").write_text(json.dumps({"datasets": ds}), encoding="utf-8")
        st0 = compute_cache_staleness("finmind_inst", cache_dir=tmp_path, today=dt.date(2026, 9, 26))
        assert {**st, "meta_last_updated": None} == st0
        bad0 = {s["dataset"] for s in chw.check_inputs_fresh(tmp_path, today=dt.date(2026, 9, 26))}
        assert bad0 == set(bad)


# ═════════════════════════════════════════════════════════════════════════════
# DL-f1-s34：季校準寫 macro_thresholds.json 時保留未知鍵與既有註解；讀檔失敗不靜默
# ═════════════════════════════════════════════════════════════════════════════
_OLD_DEFAULT_COMMENT = "By recalibrate_macro Actions workflow. PR-reviewed before applied."
_FROZEN_NOW = "2026-10-01 00:00:05"


def _old_writer_text(h: int, s: int, method: str) -> str:
    """修正前 `emit_thresholds_json` 寫出的全文（固定 5 鍵；時戳為凍結值）—— 新建檔時須逐字相同。"""
    import json
    return json.dumps({"HEALTH_DEFENSE_THRESHOLD": h, "BULL_MIN_SCORE": s,
                       "last_calibrated": _FROZEN_NOW, "method": method,
                       "_comment": _OLD_DEFAULT_COMMENT}, indent=2, ensure_ascii=False) + "\n"


@pytest.fixture
def cmt(monkeypatch):
    """`scripts.calibrate_macro_traffic`，`_dt.datetime.now()` 凍結在 2026-10-01 00:00:05。"""
    import types

    import scripts.calibrate_macro_traffic as mod

    class _Frozen:
        @staticmethod
        def now():
            return dt.datetime(2026, 10, 1, 0, 0, 5)
    monkeypatch.setattr(mod, "_dt", types.SimpleNamespace(datetime=_Frozen))
    return mod


class TestS34EmitThresholdsJson:
    def test_new_file_is_byte_identical_to_pre_fix(self, cmt, tmp_path, capsys):
        p = tmp_path / "macro_thresholds.json"
        assert cmt.emit_thresholds_json(37, 4, method="m", path=str(p)) is True
        assert p.read_text(encoding="utf-8") == _old_writer_text(37, 4, "m")
        assert "不存在" in capsys.readouterr().out                        # 缺檔：照舊以預設值比較，但要出聲

    def test_rewriting_a_pre_fix_file_is_byte_identical(self, cmt, tmp_path):
        p = tmp_path / "macro_thresholds.json"
        p.write_text(_old_writer_text(37, 4, "m1"), encoding="utf-8")
        assert cmt.emit_thresholds_json(38, 5, method="m2", path=str(p)) is True
        assert p.read_text(encoding="utf-8") == _old_writer_text(38, 5, "m2")

    def test_unknown_keys_and_comment_text_are_kept_in_place(self, cmt, tmp_path):
        import json
        orig = {"HEALTH_DEFENSE_THRESHOLD": 35, "BULL_MIN_SCORE": 4, "last_calibrated": None,
                "method": "default (uncalibrated)",
                "_comment": "By recalibrate_macro Actions workflow. Override calc_traffic_light "
                            "thresholds. PR-reviewed before applied.",
                "_comment_v19_173": "校準狀態誠實化（只是說明，未動任何數值）：…待辦：以同一份樣本跑 ROC。"}
        p = tmp_path / "macro_thresholds.json"
        p.write_text(json.dumps(orig, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        assert cmt.emit_thresholds_json(36, 5, method="walk-forward 4 folds (x)", path=str(p)) is True
        exp = dict(orig, HEALTH_DEFENSE_THRESHOLD=36, BULL_MIN_SCORE=5, last_calibrated=_FROZEN_NOW,
                   method="walk-forward 4 folds (x)")
        text = p.read_text(encoding="utf-8")
        assert text == json.dumps(exp, indent=2, ensure_ascii=False) + "\n"   # 鍵、順序、註解原文都在
        assert list(json.loads(text)) == list(orig)

    def test_live_repo_file_keeps_every_key(self, cmt, tmp_path):
        """現行 repo 的 macro_thresholds.json（只讀、複製到 tmp）：寫回後每個既有鍵都在、順序不變，
        本函式不負責的鍵一字不動。"""
        import json
        from pathlib import Path
        live = Path(__file__).resolve().parent.parent / "macro_thresholds.json"
        if not live.exists():
            pytest.skip("repo 無 macro_thresholds.json")
        orig = json.loads(live.read_text(encoding="utf-8"))
        p = tmp_path / "macro_thresholds.json"
        p.write_text(live.read_text(encoding="utf-8"), encoding="utf-8")
        h = int(orig.get("HEALTH_DEFENSE_THRESHOLD", 35)) + 1
        assert cmt.emit_thresholds_json(h, 4, method="t", path=str(p)) is True
        new = json.loads(p.read_text(encoding="utf-8"))
        owned = {"HEALTH_DEFENSE_THRESHOLD", "BULL_MIN_SCORE", "last_calibrated", "method"}
        assert list(new)[:len(orig)] == list(orig)
        assert {k: v for k, v in new.items() if k not in owned} == \
               {k: v for k, v in orig.items() if k not in owned} | {"_comment": orig.get("_comment", _OLD_DEFAULT_COMMENT)}

    def test_no_change_returns_false_and_leaves_the_bytes(self, cmt, tmp_path):
        p = tmp_path / "macro_thresholds.json"
        p.write_text(_old_writer_text(35, 4, "old").replace(_FROZEN_NOW, "2025-01-01 00:00:00"),
                     encoding="utf-8")
        before = p.read_bytes()
        assert cmt.emit_thresholds_json(35, 4, method="new", path=str(p)) is False
        assert p.read_bytes() == before

    def test_missing_file_with_default_values_creates_nothing(self, cmt, tmp_path, capsys):
        p = tmp_path / "macro_thresholds.json"
        assert cmt.emit_thresholds_json(35, 4, method="m", path=str(p)) is False
        assert not p.exists()
        assert "不存在" in capsys.readouterr().out

    def test_defaults_come_from_the_ssot(self, cmt, tmp_path, monkeypatch):
        import shared.macro_calibration as mcal
        monkeypatch.setattr(mcal, "HEALTH_DEFENSE_THRESHOLD_DEFAULT", 40)
        monkeypatch.setattr(mcal, "BULL_MIN_SCORE_DEFAULT", 3)
        p = tmp_path / "macro_thresholds.json"
        assert cmt.emit_thresholds_json(40, 3, method="m", path=str(p)) is False   # 缺檔 → 與預設值比較
        assert cmt.emit_thresholds_json(35, 4, method="m", path=str(p)) is True

    @pytest.mark.parametrize("content,why", [
        (b"{not json", "讀不了現行門檻檔"),
        (b"", "讀不了現行門檻檔"),
        (b"\xff\xfe\x00\x01", "讀不了現行門檻檔"),                 # 非 UTF-8
        (b"[35, 4]", "頂層不是 JSON 物件"),
        (b'"35"', "頂層不是 JSON 物件"),
    ], ids=["壞JSON", "空檔", "非UTF8", "頂層是陣列", "頂層是字串"])
    def test_unreadable_file_raises_and_is_not_overwritten(self, cmt, tmp_path, content, why):
        p = tmp_path / "macro_thresholds.json"
        p.write_bytes(content)
        with pytest.raises(RuntimeError, match=why):
            cmt.emit_thresholds_json(37, 4, method="m", path=str(p))
        assert p.read_bytes() == content

    def test_path_is_a_directory_raises(self, cmt, tmp_path):
        d = tmp_path / "macro_thresholds.json"
        d.mkdir()
        with pytest.raises(RuntimeError, match="讀不了現行門檻檔"):
            cmt.emit_thresholds_json(37, 4, method="m", path=str(d))

    def test_missing_keys_compare_against_defaults_and_keep_the_rest(self, cmt, tmp_path):
        import json
        p = tmp_path / "macro_thresholds.json"
        p.write_text(json.dumps({"_comment": "手寫說明", "foo": 1}, ensure_ascii=False), encoding="utf-8")
        assert cmt.emit_thresholds_json(35, 4, method="m", path=str(p)) is False   # 缺鍵 = 預設值 35／4
        assert cmt.emit_thresholds_json(36, 4, method="m", path=str(p)) is True
        assert json.loads(p.read_text(encoding="utf-8")) == {
            "_comment": "手寫說明", "foo": 1, "HEALTH_DEFENSE_THRESHOLD": 36, "BULL_MIN_SCORE": 4,
            "last_calibrated": _FROZEN_NOW, "method": "m"}
