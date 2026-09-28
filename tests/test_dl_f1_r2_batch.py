"""批 R2：DL-f1-s9／s10／s11 —— M1B／M2 排程與 EF15M01 解析器的三個守衛缺口。

DL-f1-s9：`FETCHERS["finmind_m1m2"]` 原標 needs_token=True，但資料來自 CBC、不需要 FinMind token
（`fetch_finmind_m1m2` 自陳「token 參數忽略不用」）→ 沒有 token 的執行把本表白白跳過；
`main()` 缺 token 時印「FinMind 表全跳過（僅更新 TWII）」也不精確（tw_pmi 一直照跑）。
修正後：旗標改 False、`fetch_finmind_m1m2` 的 token 改為選填（`update_one` 對 False 以
`fn(start, end)` 呼叫）、缺 token 提示改由 `FETCHERS` 的旗標推導實際會跑／會跳過的表。

DL-f1-s10：`parse_cbc_ef15m01` 對帳時「t−12 餘額 ≤ 捨入半階 → 無法對帳」這條檢查沒有單獨測試
（B 組突變：改成只警示、或整段拿掉，EF15 相關測試全過）。這裡釘兩個方向：
致命範圍內 → 整表拒用；致命範圍之前 → 只警示、照樣產出。
⚠️ 「官方年增率設 "-"」設在 **t−12 那個月**（餘額改成 ≤ 半階的月份）：那個月自己也會與它的
t−12 對帳（自算 −100% vs 官方）→ 另一條「對帳不符」會蓋掉本檢查，突變時測試照樣過。
設在被檢查的月份本身則沒有用 —— 解析器在「無官方年增率」就先跳過，根本走不到本檢查。

DL-f1-s11：`cbc_norm_label` 的 `.upper()`（序列名大小寫容錯）沒有測試（B 組突變：拿掉全過）。

fixture：沿用 `tests/test_b7b_r1_ef15m01_level.py`（#732）的 `ef15_body()`／`ef15_rows()`／`patch_ef15()`
—— meta／structure 全文與 2026M05～07 三列逐字轉錄自探針 log，其餘為自洽合成序列（說明見該檔
檔頭）；載入方式同 `tests/test_dl_f1_s1_ef15m01_online_tier2.py`。
無網路：CBC 回應與 PMI 取數一律 monkeypatch；寫檔一律導到 `tmp_path`，不碰 repo 的 `data_cache/`。
"""
from __future__ import annotations

import datetime as dt
import inspect
import math
import re
import sys

import pandas as pd
import pytest

import scripts.update_macro_history as umh
from src.data.macro import cbc_ef15m01 as ef15
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
    ef15_rows,
    patch_ef15,
)


# ═════════════════════════════════════════════════════════════════════════════
# DL-f1-s9：finmind_m1m2 不需要 token
# ═════════════════════════════════════════════════════════════════════════════
def _run_main(monkeypatch, tmp_path, argv: list[str], *, token: str | None = None) -> list[str]:
    """跑 `main()`（`token` 為 None → 無 FINMIND_TOKEN；否則設成該值），回「抓取函式真的被呼叫」
    的表名（依呼叫順序）。

    `update_one` 用真的（token 閘門就在裡面）；每張表的抓取函式換成記名樁、**保留原本的
    needs_token 旗標**（樁回空表 → update_one 不寫檔）；PMI durable 步驟換樁（不打網路）。"""
    if token is None:
        monkeypatch.delenv("FINMIND_TOKEN", raising=False)
    else:
        monkeypatch.setenv("FINMIND_TOKEN", token)
    monkeypatch.setattr(sys, "argv", ["update_macro_history.py", *argv])
    monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(umh, "META_PATH", tmp_path / "metadata.json")
    called: list[str] = []
    for name, (_fn, needs_token) in list(umh.FETCHERS.items()):
        def _fake(start, end, token=None, _name=name):
            called.append(_name)
            return pd.DataFrame()
        monkeypatch.setitem(umh.FETCHERS, name, (_fake, needs_token))
    import src.data.macro.macro_core as mc
    monkeypatch.setattr(mc, "fetch_tw_pmi", lambda **k: {"value": None, "is_stale": False})

    def _no_save(*a, **k):
        raise AssertionError("PMI 未取得時不得寫 durable 快照")
    monkeypatch.setattr(mc, "_macro_durable_save", _no_save)
    assert umh.main() == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["metadata.json"]   # 樁回空表 → 不寫 parquet
    return called


def _notice_lists(out: str) -> tuple[list[str], list[str]]:
    """從 main() 的輸出取出缺 token 提示 → (跳過的表, 照常執行的表)。"""
    lines = [ln for ln in out.splitlines() if ln.startswith("⚠️ FINMIND_TOKEN 未設定")]
    assert len(lines) == 1, out                  # （逐表的「⏭ 跳過：FINMIND_TOKEN 未設定」不算）
    m = re.search(r"跳過需要 token 的表：(.*)；照常執行：(.*)$", lines[0])
    assert m, lines[0]

    def _names(s: str) -> list[str]:
        return [] if s == "（無）" else s.split(", ")
    return _names(m.group(1)), _names(m.group(2))


class TestS9M1m2NeedsNoToken:
    def test_m1m2_registered_as_not_needing_token(self):
        fn, needs_token = umh.FETCHERS["finmind_m1m2"]
        assert fn is umh.fetch_finmind_m1m2
        assert needs_token is False, "CBC 不需要 FinMind token；標 True 會讓無 token 的執行白白跳過"

    @pytest.mark.parametrize("name", sorted(umh.FETCHERS))
    def test_every_fetcher_binds_the_call_form_update_one_uses(self, name):
        """update_one：needs_token → fn(start, end, token)；否則 fn(start, end)。綁不上 = 執行時 TypeError。"""
        fn, needs_token = umh.FETCHERS[name]
        args = (dt.date(2026, 1, 1), dt.date(2026, 9, 28)) + (("tok",) if needs_token else ())
        inspect.signature(fn).bind(*args)

    def test_update_one_without_token_still_updates_m1m2(self, monkeypatch, tmp_path):
        """端到端（真的 update_one ＋ 真的 fetch_finmind_m1m2，只有 CBC 回應是假的）：沒有 token
        也照常抓、照常寫 —— 不被 token 閘門跳過，也不因少傳一個參數而 TypeError。"""
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        calls = patch_ef15(monkeypatch, ef15_body())
        meta = umh.update_one("finmind_m1m2", dt.date(2026, 9, 28), True, 20, "")
        assert calls == ["EF15M01"], "應真的去抓 CBC，而不是被 token 閘門跳過"
        assert meta["last_error"] is None, meta
        assert meta["last_updated"] == "2026-07-01"
        out = pd.read_parquet(tmp_path / "finmind_m1m2.parquet")
        assert len(out) == meta["row_count"] == 28 + 3
        assert umh._m1m2_level_sanity(out)[0]

    def test_main_no_token_notice_lists_what_actually_runs(self, monkeypatch, tmp_path, capsys):
        called = _run_main(monkeypatch, tmp_path, [])
        skip, run = _notice_lists(capsys.readouterr().out)
        assert "finmind_m1m2" in run and "finmind_m1m2" not in skip
        assert "tw_pmi" in run and "twii_ohlcv" in run            # 原句「僅更新 TWII」漏了 tw_pmi
        assert {"finmind_inst", "finmind_margin"} <= set(skip)
        assert sorted(skip + run) == sorted(umh.DATASETS)        # 每張表恰列一次、不多不少
        # 提示與實際行為一致（真的 update_one 閘門）：列為「照常執行」的表恰好就是真的被抓的表
        assert called == run

    def test_main_notice_is_derived_from_registry_and_only(self, monkeypatch, tmp_path, capsys):
        """不寫死表名：提示跟著 `FETCHERS` 的旗標與 `--only` 走；未註冊的表名不列（主迴圈另印）。"""
        def _placeholder(*a, **k):
            raise AssertionError("應已被 _run_main 換成記名樁")
        monkeypatch.setitem(umh.FETCHERS, "zz_probe_free", (_placeholder, False))
        monkeypatch.setitem(umh.FETCHERS, "zz_probe_token", (_placeholder, True))
        called = _run_main(monkeypatch, tmp_path,
                           ["--only", "zz_probe_token,finmind_inst,zz_probe_free,no_such_table"])
        out = capsys.readouterr().out
        assert _notice_lists(out) == (["zz_probe_token", "finmind_inst"], ["zz_probe_free"])
        assert called == ["zz_probe_free"]
        assert "[main] 未知 dataset: no_such_table" in out

    def test_main_with_token_prints_no_missing_token_notice(self, monkeypatch, tmp_path, capsys):
        """（批 R2 QA）有 token 時不得印缺 token 提示，也沒有任何表因 token 被跳過 —— 全部照常執行。"""
        called = _run_main(monkeypatch, tmp_path, [], token="tok-for-test")
        out = capsys.readouterr().out
        assert "FINMIND_TOKEN 未設定" not in out, out
        assert called == list(umh.DATASETS)


# ═════════════════════════════════════════════════════════════════════════════
# DL-f1-s10：致命範圍內「t−12 餘額 ≤ 捨入半階 → 無法對帳」
# ═════════════════════════════════════════════════════════════════════════════
_START = dt.date(2026, 2, 1)                  # 寫入窗口起點 → 第一個寫入月 2026-02
_FATAL = ef15.ef15_fatal_from(_START)        # 致命範圍 ≥ 2025-02（寫入窗口往前 12 個月）


def _t12_at_or_below_half_step(rows, per: str, idx: int, level: str) -> None:
    """把 `per` 的 t−12 月、序列 `idx` 的餘額改成 `level`（≤ 捨入半階），並把 **t−12 那個月** 該序列
    的官方年增率設成 "-"（它自己的對帳才不會另外判不符 → 只剩本檢查觸發）。"""
    y, m = int(per[:4]), int(per[5:])
    r12 = _row_of(rows, _p(*_shift(y, m, -12)))
    r12[_lv_col(idx)] = level
    r12[_yy_col(idx)] = "-"
    assert _row_of(rows, per)[_yy_col(idx)] != "-"     # 被檢查的月份要有官方年增率，才走得到本檢查


# （批 R2 QA）兩個序列都測：「t−12 檢查只對其中一個序列生效」這種突變也要轉紅
_SERIES = [pytest.param(I_M1B, "m1b", "M1B", id="M1B"),
           pytest.param(I_M2, "m2", "M2", id="M2")]


class TestS10T12AtOrBelowHalfStep:
    def test_fatal_from_is_write_window_minus_12_months(self):
        assert _FATAL == dt.date(2025, 2, 1)

    @pytest.mark.parametrize("idx,key,short", _SERIES)
    @pytest.mark.parametrize("level", ["0", "-3"])
    def test_inside_fatal_range_rejects_whole_table(self, level, idx, key, short, capsys):
        # 2026-02 = 第一個寫入月（致命範圍內）；它的 t−12 = 2025-02（= 致命範圍起點）
        rows = ef15_rows()
        _t12_at_or_below_half_step(rows, "2026M02", idx, level)
        capsys.readouterr()
        df, why = ef15.parse_cbc_ef15m01(ef15_body(rows), _FATAL)
        out = capsys.readouterr().out
        assert df is None
        assert why.startswith("對帳不符 1 列") and "致命範圍 ≥ 2025-02" in why, why
        assert "捨入半階" in out and "無法對帳" in out and f"'2026-02', '{short}'" in out, out
        # 對照組：同一份表只把 t−12 餘額還原（官方年增率仍是 "-"）→ 放行 —— 擋下它的是那筆餘額
        rows_ok = ef15_rows()
        _row_of(rows_ok, "2025M02")[_yy_col(idx)] = "-"
        assert ef15.parse_cbc_ef15m01(ef15_body(rows_ok), _FATAL)[0] is not None

    @pytest.mark.parametrize("idx,key,short", _SERIES)
    @pytest.mark.parametrize("level", ["0", "-3"])
    def test_before_fatal_range_only_warns_and_still_outputs(self, level, idx, key, short, capsys):
        # 2025-01 = 致命範圍（≥ 2025-02）之前的最後一個月；它的 t−12 = 2024-01
        base, _ = ef15.parse_cbc_ef15m01(ef15_body(), _FATAL)
        rows = ef15_rows()
        _t12_at_or_below_half_step(rows, "2025M01", idx, level)
        capsys.readouterr()
        df, why = ef15.parse_cbc_ef15m01(ef15_body(rows), _FATAL)
        out = capsys.readouterr().out
        assert df is not None, why
        assert "之前對帳不符 1 列" in out and "只警示" in out, out
        assert "無法對帳" in out and f"'2025-01', '{short}'" in out, out
        assert "範圍前不符（只警示）1 列" in out
        # 照樣產出：只有被改的兩格（2024-01 該序列的餘額與官方年增率）不同，其餘一格不變
        exp = base.copy()
        i = exp.index[exp["date"] == dt.date(2024, 1, 1)][0]
        exp.loc[i, key] = int(level)
        exp.loc[i, f"{key}_yoy"] = math.nan
        pd.testing.assert_frame_equal(df, exp)


# ═════════════════════════════════════════════════════════════════════════════
# DL-f1-s11：序列名比對不分大小寫（`cbc_norm_label` 的 `.upper()`）
# ═════════════════════════════════════════════════════════════════════════════
class TestS11SeriesLabelCase:
    @pytest.mark.parametrize("m1a,m1b,m2", [
        ("貨幣總計數-m1a", "貨幣總計數-m1b", "貨幣總計數-m2"),            # 半形全小寫
        ("貨幣總計數 -Ｍ１Ａ", "貨幣總計數-M1b", "貨幣總計數 -Ｍ２"),      # 大小寫混寫（只改 M1B）
        ("貨幣總計數 -ｍ１ａ", "貨幣總計數 -ｍ１Ｂ", "貨幣總計數 -ｍ２"),   # 全形小寫／混寫（CBC 標籤是全形字）
    ])
    def test_lower_or_mixed_case_label_still_unique_hit(self, m1a, m1b, m2):
        base, base_desc = ef15.parse_cbc_ef15m01(ef15_body())
        t1 = list(EF15_TABLE1)
        t1[I_M1A], t1[I_M1B], t1[I_M2] = m1a, m1b, m2
        df, desc = ef15.parse_cbc_ef15m01(ef15_body(table1=t1))
        assert df is not None, desc
        pd.testing.assert_frame_equal(df, base)          # 餘額（與官方年增率）一格不變
        assert desc == base_desc == "M1B label=貨幣總計數-M1B; M2 label=貨幣總計數-M2"

    def test_case_variants_of_one_name_are_the_same_series(self):
        """大小寫不同仍是同一個序列名 → 兩個標籤同時出現 = 2 個命中 → 拒用（唯一命中是在正規化後判定）。"""
        t1 = list(EF15_TABLE1)
        t1[I_M1A] = "貨幣總計數-m1b"
        df, why = ef15.parse_cbc_ef15m01(ef15_body(table1=t1))
        assert df is None and "M1B" in why and "2 個" in why, why
