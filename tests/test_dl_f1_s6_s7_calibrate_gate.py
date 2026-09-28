# -*- coding: utf-8 -*-
"""tests/test_dl_f1_s6_s7_calibrate_gate.py — 季校準輸入閘門的兩個誤擋(DL-f1-s6／DL-f1-s7,2026-09-28)。

═══ 在防什麼 ═══════════════════════════════════════════════════════════
`scripts/calibrate_health_weights.py::check_inputs_fresh` 是季排程
(`.github/workflows/calibrate_health_weights.yml`,cron `0 10 1 1,4,7,10 *`)的輸入閘門。
兩個誤判讓它在**輸入正常**時也擋下:

  s6 ─ cron `scripts/update_macro_history.py::update_one` 在 fetcher 回空表時寫
       `last_error`＝「抓取結果為空」—— 週末、休市、月頻表兩次發布之間天天如此
       (2026-09-28 讀 origin/main 上 `data_cache/metadata.json` 近 10 版〔09-20～09-27〕:
        tw_pmi 9 版、m1m2 8 版、finmind_inst 4 版〔其中 3 版在週末〕是它)。
       舊閘門把它當上游錯誤一律擋。
  s7 ─ `shared.staleness.MACRO_PUBLICATION_LAG_DAYS["m1b_m2"]` 原為 7。批 R(#732)起 m1m2
       取 CBC EF15M01;探針 run 36419092722(2026-09-28 20:00 台北)讀到 EF15M01
       `meta.last_updated`＝2026-08-27、末列期間 2026M07 ⇒ 7 月資料最晚 08-27 上架。
       舊值 7 從 08-15 起就把 6 月判「落後 1 期」—— 比實測上架日早了 12 天。

現行規則(本檔逐條守):
  1. `last_error` **完全等於** `shared.staleness.EMPTY_FETCH_MARKER`、且新鮮度判定**不過期** → 可用;
  2. 同一標記但**過期** → 擋(擋它的是新鮮度判定,不是標記);
  3. 其他任何非空 `last_error`(含「抓取結果為空；既有檔 sanity 不過,待重建」這種複合字串、
     前後多一個空白)→ 照舊擋;
  4. 寫入端(`update_one`)與讀取端(`check_inputs_fresh`)共用同一個常數 —— 改一邊另一邊跟著變;
  5. m1b_m2 的應發布日涵蓋 EF15M01 實測上架日;08-27 前後都不誤判落後,但真的漏期仍會判過期。

⚠️ 門檻一律從 `shared/staleness.py` 取;本檔寫死的只有「2026-08-27 上架」這個**觀測事實**與情境日期。
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import pathlib
import sys

import pandas as pd
import pytest

import shared.staleness as S
from shared.staleness import (
    EMPTY_FETCH_MARKER,
    MONTHLY_PUBLICATION_MARGIN_DAYS,
    monthly_periods_behind,
    monthly_publication_due,
)
from src.data.macro.macro_cache_reader import compute_cache_staleness

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_REQUIRED = ("twii_ohlcv", "finmind_inst", "finmind_m1m2")

#: 探針 run 36419092722 讀到的 EF15M01:`meta.last_updated`＝2026-08-27、末列期間 2026M07。
#: ⇒ 2026-07 這一期最晚在這一天上架(觀測事實,不是門檻)。
_JULY_2026_RELEASED = dt.date(2026, 8, 27)

_JUNE, _JULY = dt.date(2026, 6, 1), dt.date(2026, 7, 1)


def _gate():
    """以檔案路徑載入校準 script(它不是套件模組;載法同 test_cache_staleness_honesty)。"""
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    spec = importlib.util.spec_from_file_location(
        "_calib_gate_dl_f1_s6_s7", _ROOT / "scripts" / "calibrate_health_weights.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_daily(tmp_path, name: str, last_day: dt.date, n: int = 30):
    idx = pd.bdate_range(end=pd.Timestamp(last_day), periods=n)
    pd.DataFrame({"date": idx, "close": range(n), "foreign_buy": range(n)}).to_parquet(
        tmp_path / f"{name}.parquet")


def _write_m1m2(tmp_path, last_month: dt.date, n: int = 24):
    """月頻存量表(百萬元量級、m2 > m1b、gap 小)—— 過得了 `update_one` 的既有檔 sanity 守門。"""
    months = pd.date_range(end=pd.Timestamp(last_month), periods=n, freq="MS")
    pd.DataFrame({
        "date": [m.date() for m in months],
        "m1b": [30_000_000 + 10_000 * i for i in range(n)],
        "m2": [70_000_000 + 20_000 * i for i in range(n)],
        "m1b_m2_gap": [0.1] * n,
    }).to_parquet(tmp_path / "finmind_m1m2.parquet", index=False)


def _write_meta(tmp_path, datasets: dict):
    """照 `update_macro_history.main()` 的 payload 形狀寫 metadata.json。"""
    (tmp_path / "metadata.json").write_text(json.dumps(
        {"updated_at": "2026-09-27T14:38:22+00:00", "datasets": datasets},
        ensure_ascii=False), encoding="utf-8")


def _meta(error_by_name: dict) -> dict:
    return {n: {"name": n, "last_updated": None, "row_count": 1,
                "last_error": error_by_name.get(n)} for n in _REQUIRED}


def _meta_all(error) -> dict:
    return _meta({n: error for n in _REQUIRED})


def _blocked(tmp_path, today) -> list:
    return [b["dataset"] for b in _gate().check_inputs_fresh(tmp_path, today=today)]


def _empty_fetcher(needs_token: bool):
    if needs_token:
        return lambda start, end, token: pd.DataFrame()
    return lambda start, end: pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════
# s6. 「抓取結果為空」:不過期才放行;過期與其他錯誤照擋
# ══════════════════════════════════════════════════════════════════════
class TestEmptyFetchMarker:
    #: 2026-09-27 是週日(真實 metadata 當天 finmind_inst 即為「抓取結果為空」)。
    #: m1m2 用 2026-08 —— 無論 lag 取多少都是當期,讓本組只測 s6、不受 s7 牽動。
    _TODAY = dt.date(2026, 9, 27)

    def _fresh_inputs(self, tmp_path):
        _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 9, 25))
        _write_daily(tmp_path, "finmind_inst", dt.date(2026, 9, 25))
        _write_m1m2(tmp_path, dt.date(2026, 8, 1))

    def test_marker_on_fresh_inputs_passes(self, tmp_path):
        """三個輸入都新鮮、metadata 全是「抓取結果為空」→ 放行(舊碼三個全擋)。"""
        self._fresh_inputs(tmp_path)
        _write_meta(tmp_path, _meta_all(EMPTY_FETCH_MARKER))
        assert _blocked(tmp_path, self._TODAY) == []

    def test_marker_on_stale_daily_input_is_blocked(self, tmp_path):
        """標記不是免死金牌:日頻表 26 天沒新列 → 由新鮮度判定擋下。"""
        self._fresh_inputs(tmp_path)
        _write_daily(tmp_path, "finmind_inst", dt.date(2026, 9, 1))
        _write_meta(tmp_path, _meta_all(EMPTY_FETCH_MARKER))
        bad = _gate().check_inputs_fresh(tmp_path, today=self._TODAY)
        assert [b["dataset"] for b in bad] == ["finmind_inst"]
        assert bad[0]["is_stale"] is True, "擋它的必須是新鮮度判定"
        assert bad[0]["upstream_error"] == EMPTY_FETCH_MARKER

    def test_marker_on_stale_monthly_input_is_blocked(self, tmp_path):
        """月頻表漏掉整期(停在 2026-05)+ 標記 → 擋,且理由講得出「落後」。"""
        self._fresh_inputs(tmp_path)
        _write_m1m2(tmp_path, dt.date(2026, 5, 1))
        _write_meta(tmp_path, _meta_all(EMPTY_FETCH_MARKER))
        bad = _gate().check_inputs_fresh(tmp_path, today=self._TODAY)
        assert [b["dataset"] for b in bad] == ["finmind_m1m2"]
        assert bad[0]["is_stale"] is True and "落後" in (bad[0]["reason"] or "")

    @pytest.mark.parametrize("err", [
        # `update_one` 自己寫的複合字串:既有檔已知不合格、重建又沒抓到 —— 絕不可放行
        "抓取結果為空；既有檔 sanity 不過,待重建",
        "TimeoutError: cbc；既有檔 sanity 不過,待重建",
        "FINMIND_TOKEN 未設定",
        "HTTPError: 503 Server Error",
        # 只認「完全相等」:不去空白、不比前綴、不比包含
        "抓取結果為空 ",
        " 抓取結果為空",
        "抓取結果為空\n",
        "抓取結果為空。",
    ])
    def test_any_other_error_on_fresh_input_is_blocked(self, tmp_path, err):
        self._fresh_inputs(tmp_path)
        _write_meta(tmp_path, _meta({"finmind_inst": err}))
        bad = _gate().check_inputs_fresh(tmp_path, today=self._TODAY)
        assert [b["dataset"] for b in bad] == ["finmind_inst"], err
        assert bad[0]["is_stale"] is False, "資料本身新鮮 —— 擋它的必須是錯誤字串"

    @pytest.mark.parametrize("err", [
        {"msg": "抓取結果為空"}, ["抓取結果為空"], 1,
    ])
    def test_non_string_error_is_blocked(self, tmp_path, err):
        """metadata 被手改成非字串 → 不等於標記 → 擋(不做型別寬鬆轉換)。"""
        self._fresh_inputs(tmp_path)
        _write_meta(tmp_path, _meta({"finmind_inst": err}))
        assert _blocked(tmp_path, self._TODAY) == ["finmind_inst"]

    @pytest.mark.parametrize("state", ["missing", "empty_frame"])
    def test_marker_without_usable_parquet_is_blocked(self, tmp_path, state):
        """歷史上真的出現過的形狀:`{last_updated: null, row_count: 0, last_error: 抓取結果為空}`
        (tw_pmi 曾長期如此)。檔案缺 / 空表 → 判不出年齡 → 視為過期 → 標記救不了它。"""
        self._fresh_inputs(tmp_path)
        _p = tmp_path / "finmind_inst.parquet"
        _p.unlink()
        if state == "empty_frame":
            pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]")}).to_parquet(_p)
        _write_meta(tmp_path, {**_meta_all(None), "finmind_inst": {
            "name": "finmind_inst", "last_updated": None, "row_count": 0,
            "last_error": EMPTY_FETCH_MARKER}})
        bad = _gate().check_inputs_fresh(tmp_path, today=self._TODAY)
        assert [b["dataset"] for b in bad] == ["finmind_inst"]
        assert bad[0]["is_stale"] is True and bad[0]["as_of"] is None

    def test_no_error_on_fresh_input_still_passes(self, tmp_path):
        """基準:`last_error` 為 null → 照舊放行(本次修改不得動到這一格)。"""
        self._fresh_inputs(tmp_path)
        _write_meta(tmp_path, _meta_all(None))
        assert _blocked(tmp_path, self._TODAY) == []


# ══════════════════════════════════════════════════════════════════════
# s6. 寫入端與讀取端共用同一個常數(SSOT)
# ══════════════════════════════════════════════════════════════════════
class TestMarkerSharedByWriterAndReader:
    _SENTINEL = "⟪DL-f1-s6 哨兵⟫"
    _TODAY = dt.date(2026, 9, 27)

    def _fresh_inputs(self, tmp_path):
        _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 9, 25))
        _write_daily(tmp_path, "finmind_inst", dt.date(2026, 9, 25))
        _write_m1m2(tmp_path, dt.date(2026, 8, 1))

    def test_writer_writes_the_shared_constant(self, monkeypatch, tmp_path):
        """改常數 → `update_one` 寫出來的字跟著變(寫入端若另抄一份字面值,這條會紅)。"""
        import scripts.update_macro_history as umh

        monkeypatch.setattr(S, "EMPTY_FETCH_MARKER", self._SENTINEL)
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 9, 25))
        monkeypatch.setitem(umh.FETCHERS, "twii_ohlcv", (_empty_fetcher(False), False))
        meta = umh.update_one("twii_ohlcv", self._TODAY, False, 1, "")
        assert meta["last_error"] == self._SENTINEL
        assert meta["last_updated"] == "2026-09-25", "既有資料原封不動、last_updated 照實回報"

    def test_reader_compares_against_the_shared_constant(self, monkeypatch, tmp_path):
        """改常數 → 閘門認的字跟著變;舊字面值此時就只是「一個錯誤字串」→ 擋。"""
        monkeypatch.setattr(S, "EMPTY_FETCH_MARKER", self._SENTINEL)
        self._fresh_inputs(tmp_path)
        _write_meta(tmp_path, _meta_all(self._SENTINEL))
        assert _blocked(tmp_path, self._TODAY) == []
        _write_meta(tmp_path, _meta_all("抓取結果為空"))
        assert _blocked(tmp_path, self._TODAY) == list(_REQUIRED)

    def test_round_trip_cron_output_is_accepted_by_gate(self, monkeypatch, tmp_path):
        """整合:cron 真的寫出來的 metadata → 閘門真的放行(兩端任一端改回字面值都會紅)。"""
        import scripts.update_macro_history as umh

        self._fresh_inputs(tmp_path)
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        for name in _REQUIRED:
            _needs_token = umh.FETCHERS[name][1]
            monkeypatch.setitem(umh.FETCHERS, name,
                                (_empty_fetcher(_needs_token), _needs_token))
        metadata = {n: umh.update_one(n, self._TODAY, False, 1, "tok") for n in _REQUIRED}
        assert {m["last_error"] for m in metadata.values()} == {EMPTY_FETCH_MARKER}, metadata
        _write_meta(tmp_path, metadata)
        assert _blocked(tmp_path, self._TODAY) == []

    def test_marker_matches_what_is_already_persisted(self):
        """main 上既有的 metadata.json 全由舊碼以這個字面值寫入 —— 常數若改字,
        已落地的標記在下一次 cron 重寫前會全部變成「上游錯誤」而被擋。要改字請連同遷移一起想。"""
        assert EMPTY_FETCH_MARKER == "抓取結果為空"


# ══════════════════════════════════════════════════════════════════════
# s6. 不變量:fetcher 拋例外 → ⛔ 不得寫成 EMPTY_FETCH_MARKER
# ══════════════════════════════════════════════════════════════════════
class TestFetcherExceptionIsNeverTheMarker:
    """閘門在「不過期」時放行 `EMPTY_FETCH_MARKER`。例外一旦被寫成標記,真的上游錯誤
    就會被當成「這一輪沒有新列」放過 —— 資料還沒過期的那段期間完全看不見。

    (批 C QA 2026-09-28:這條不變量原本只被 tests/test_b3_margin_schema.py 偶然抓到 ——
     那條斷言的是例外訊息裡恰好有 "sanity" 字樣,換一個例外訊息就抓不到。)
    """
    _TODAY = dt.date(2026, 9, 27)

    @pytest.mark.parametrize("exc", [
        ConnectionError("CBC 逾時"),
        ValueError(""),                   # 空訊息:型別名仍須留下
        RuntimeError("抓取結果為空"),      # 訊息恰好等於標記文字:仍不得變成標記
    ])
    def test_exception_is_recorded_as_itself_and_gate_blocks(self, monkeypatch, tmp_path, exc):
        import scripts.update_macro_history as umh

        _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 9, 25))
        _write_daily(tmp_path, "finmind_inst", dt.date(2026, 9, 25))
        _write_m1m2(tmp_path, dt.date(2026, 8, 1))
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)

        def _boom(start, end, token):
            raise exc
        monkeypatch.setitem(umh.FETCHERS, "finmind_inst", (_boom, True))
        meta = umh.update_one("finmind_inst", self._TODAY, False, 1, "tok")
        assert meta["last_error"] != EMPTY_FETCH_MARKER, "例外被寫成了「抓取結果為空」"
        assert type(exc).__name__ in (meta["last_error"] or ""), meta["last_error"]
        # 端到端:資料本身新鮮(09-25),仍必須被閘門擋下,而且擋它的是錯誤字串
        _write_meta(tmp_path, {**_meta_all(None), "finmind_inst": meta})
        bad = _gate().check_inputs_fresh(tmp_path, today=self._TODAY)
        assert [b["dataset"] for b in bad] == ["finmind_inst"]
        assert bad[0]["is_stale"] is False


# ══════════════════════════════════════════════════════════════════════
# s7. m1b_m2 發布延遲:涵蓋 EF15M01 實測上架日,且真漏期仍會被抓到
# ══════════════════════════════════════════════════════════════════════
class TestM1bM2PublicationLag:
    def test_due_date_covers_the_observed_release(self):
        """7 月資料的應發布日不得早於實測上架日(早於 = 資料還沒出就開始算逾期)。"""
        assert monthly_publication_due(_JULY, indicator="m1b_m2") >= _JULY_2026_RELEASED

    def test_june_is_never_behind_before_july_is_released(self):
        """7 月資料最晚 08-27 上架 → 到那天為止(含當天),停在 6 月都不得判落後
        (就算 7 月其實更早上架,到 08-27 也仍在緩衝內)。

        舊值 7:應發布日 08-08、緩衝到 08-15 ⇒ 08-15～08-27 每天把 6 月判「落後 1 期」。
        """
        bad, d = [], dt.date(2026, 7, 1)
        while d <= _JULY_2026_RELEASED:
            _b = monthly_periods_behind(_JUNE, indicator="m1b_m2", today=d)
            if _b is None or _b >= 1:
                bad.append((d.isoformat(), _b))
            d += dt.timedelta(days=1)
        assert not bad, f"7 月資料最晚 {_JULY_2026_RELEASED} 上架,6 月卻被判落後:{bad[:5]}…"

    def test_july_is_current_after_its_release(self):
        """7 月上架後(含季排程當天 10-01:EF15M01 09-28 20:00 仍停在 2026M07)→ 7 月是當期。"""
        for d in (_JULY_2026_RELEASED, dt.date(2026, 9, 28), dt.date(2026, 10, 1)):
            _b = monthly_periods_behind(_JULY, indicator="m1b_m2", today=d)
            assert _b is not None and _b <= 0, (d, _b)

    def test_genuinely_missed_month_is_still_caught(self):
        """放寬 lag 不得變成永遠不過期:6 月卡住、7 月早已上架 → 緩衝用完那天起落後 1 期。

        邊界兩側都測(只測「很久以後會紅」抓不到 off-by-one)。
        上限原本在這裡(「發現時點不晚於上架後 31 天」,等於容許 lag 到 50),
        批 C QA(2026-09-28)突變 lag=45 存活 → 收緊並移到下一條
        `test_lag_slack_over_observation_does_not_exceed_the_grace`。
        """
        _first_red = monthly_publication_due(
            _JULY, indicator="m1b_m2", grace_days=MONTHLY_PUBLICATION_MARGIN_DAYS)
        assert monthly_periods_behind(
            _JUNE, indicator="m1b_m2", today=_first_red - dt.timedelta(days=1)) == 0
        assert monthly_periods_behind(_JUNE, indicator="m1b_m2", today=_first_red) == 1

    def test_lag_slack_over_observation_does_not_exceed_the_grace(self):
        """lag 的上限:應發布日比實測上架日多出來的天數,不得超過緩衝本身。

        分工:lag 描述「正常上架日」;上游遲到的容忍由 `MONTHLY_PUBLICATION_MARGIN_DAYS`
        負責。lag 若再多留超過緩衝的餘裕 = 把緩衝重複算一次 —— 真的漏期要多拖一整個緩衝才被發現。
        ⇒ 0 ≤ 應發布日 − 實測上架日 ≤ 緩衝。現值 27 → 多 1 天;容許的 lag = 26～33:
        容得下「8 月 ≥ 月底後 28 天」這個設限觀測帶來的不確定,但擋得住 45 這種明顯過寬的值
        (批 C QA 2026-09-28:原上限容許到 50,突變 lag=45 存活)。
        """
        _slack = (monthly_publication_due(_JULY, indicator="m1b_m2")
                  - _JULY_2026_RELEASED).days
        assert 0 <= _slack <= MONTHLY_PUBLICATION_MARGIN_DAYS, (
            f"應發布日比實測上架日晚 {_slack} 天,超過緩衝 {MONTHLY_PUBLICATION_MARGIN_DAYS} 天"
            " —— lag 放太寬")

    def test_cache_reader_follows_the_same_rule(self, tmp_path):
        """`compute_cache_staleness`(閘門實際呼叫的那一層)對同一組日期給同一個答案。"""
        pd.DataFrame({"date": [_JUNE]}).to_parquet(tmp_path / "finmind_m1m2.parquet")
        for d in (dt.date(2026, 8, 15), dt.date(2026, 8, 26), _JULY_2026_RELEASED):
            _r = compute_cache_staleness("finmind_m1m2", cache_dir=tmp_path, today=d)
            assert _r["is_stale"] is False, (d, _r["reason"])


# ══════════════════════════════════════════════════════════════════════
# s6 + s7. 閘門端到端:舊碼在這兩個真實情境都會誤擋
# ══════════════════════════════════════════════════════════════════════
class TestGateScenarios:
    def test_2026_08_26_june_with_marker_passes(self, tmp_path):
        """實測上架日(08-27)前一天:m1m2 停在 6 月、metadata「抓取結果為空」。
        舊碼擋兩次 —— 6 月被判落後(s7)、標記被當上游錯誤(s6)。"""
        today = dt.date(2026, 8, 26)
        _write_daily(tmp_path, "twii_ohlcv", today)
        _write_daily(tmp_path, "finmind_inst", today)
        _write_m1m2(tmp_path, _JUNE)
        _write_meta(tmp_path, _meta({"finmind_m1m2": EMPTY_FETCH_MARKER}))
        assert _blocked(tmp_path, today) == []

    def test_2026_10_01_quarterly_run_with_july_passes(self, tmp_path):
        """季排程當天的一種可能樣子(EF15M01 09-28 20:00 仍停在 2026M07,8 月何時上架未知):
        m1m2 最新 7 月、三個輸入的 metadata 都是「抓取結果為空」→ 必須放行。
        舊值 7 會把 7 月判落後 1 期(應發布日 09-08、緩衝到 09-15)。"""
        today = dt.date(2026, 10, 1)
        _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 9, 30))
        _write_daily(tmp_path, "finmind_inst", dt.date(2026, 9, 30))
        _write_m1m2(tmp_path, _JULY)
        _write_meta(tmp_path, _meta_all(EMPTY_FETCH_MARKER))
        assert _blocked(tmp_path, today) == []

    def test_sanity_rebuild_marker_still_blocks_even_when_dates_look_current(self, tmp_path):
        """真實 metadata(origin/main 2026-09-27 版)的 m1m2:日期看似當期,但既有檔已知不合格
        →「抓取結果為空；既有檔 sanity 不過,待重建」必須擋(它不是「沒有新資料」)。"""
        today = dt.date(2026, 9, 28)
        _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 9, 24))
        _write_daily(tmp_path, "finmind_inst", dt.date(2026, 9, 24))
        _write_m1m2(tmp_path, _JULY)
        _write_meta(tmp_path, _meta({
            "twii_ohlcv": None,
            "finmind_inst": EMPTY_FETCH_MARKER,
            "finmind_m1m2": "抓取結果為空；既有檔 sanity 不過,待重建"}))
        bad = _gate().check_inputs_fresh(tmp_path, today=today)
        assert [b["dataset"] for b in bad] == ["finmind_m1m2"]
        assert bad[0]["is_stale"] is False, "日期是當期 —— 擋它的必須是複合錯誤字串"


# ══════════════════════════════════════════════════════════════════════
# s6. `main()` 被擋時的操作訊息(排程 log／開發者訊息,不是畫面文案)
# ══════════════════════════════════════════════════════════════════════
class TestMainBlockedMessage:
    """s6 之後,被擋訊息要講對兩件事(批 C QA 2026-09-28):
      ① 資料沒過期、純因錯誤字串被擋 → 不得寫「判為過期」;過期的照樣講出舊到哪;
      ② 修法不得再要求 last_error「一定是 null」—— 標記＋不過期現在是可接受的。"""

    def test_blocked_message_is_accurate(self, monkeypatch, tmp_path):
        mod = _gate()
        today = dt.date(2026, 9, 27)
        _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 9, 25))
        _write_daily(tmp_path, "finmind_inst", dt.date(2026, 9, 25))
        _write_m1m2(tmp_path, dt.date(2026, 5, 1))                     # 真的落後
        _write_meta(tmp_path, _meta({"finmind_inst": "HTTPError: 503 Server Error",
                                      "finmind_m1m2": EMPTY_FETCH_MARKER}))
        states = mod.check_inputs_fresh(tmp_path, today=today)
        assert [s["dataset"] for s in states] == ["finmind_inst", "finmind_m1m2"]
        assert [s["is_stale"] for s in states] == [False, True]

        # main() 讀的是模組層 `_CACHE`(真實 data_cache),改指 tmp;閘門結果用上面算好的。
        monkeypatch.setattr(mod, "_CACHE", tmp_path)
        monkeypatch.setattr(mod, "check_inputs_fresh", lambda *a, **k: states)
        with pytest.raises(SystemExit) as ei:
            mod.main()
        lines = str(ei.value).splitlines()
        _inst = next(ln for ln in lines if "finmind_inst" in ln)
        _m1m2 = next(ln for ln in lines if "finmind_m1m2" in ln)
        _fix = next(ln for ln in lines if "修法" in ln)
        assert "判為過期" not in _inst and "未過期" in _inst, _inst       # ①
        assert "HTTPError" in _inst, _inst
        assert "落後" in _m1m2, _m1m2
        assert EMPTY_FETCH_MARKER in _fix, _fix                           # ②
