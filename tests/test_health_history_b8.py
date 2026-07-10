"""v19.77 — B8 健康度歷史快照(repo 快照 + cron)+ A-2 批次平行化 守衛測試。

user 2026-07-10 核准:B8 選「repo 快照 + cron」、A 類只做「批次抓取平行化」。

覆蓋:
- compute_health_row:公式重用(與 UI 同輸入形狀)/ 空 df fail-loud / 越界棄列
- merge_and_write:(date,sid) 冪等 / 升序 / §4.2 不變量
- load_watchlist:檔缺 / 空清單 / 正常(§1 不腦補持股)
- service load_health_history:tmp parquet 讀取 / 檔缺回 []
- merge_score_history:cron 底稿 + session 同日覆蓋 / keep 窗 / 壞日期略過
- script main() e2e:fake loader 全離線跑通 parquet + meta
- A-2 源碼守衛:Lock 串行已除 / sleep(0.2) 已除 / thread-local loader 存在
"""
from __future__ import annotations

import datetime as _dt
import json
import unittest

import pandas as pd


def _mk_price_df(n=300, base=100.0, last_date="2026-07-10"):
    """合成 get_combined_data 輸出形狀:OHLCV + date + MA 欄(升序日線)。"""
    end = _dt.date.fromisoformat(last_date)
    dates = pd.bdate_range(end=end, periods=n)
    close = pd.Series([base + i * 0.1 for i in range(n)], dtype="float64")
    df = pd.DataFrame({
        "date": dates,
        "open": close, "high": close * 1.01, "low": close * 0.99,
        "close": close, "volume": [1_000_000] * n,
    })
    for p in [5, 10, 20, 60, 100, 120, 240]:
        df[f"MA{p}"] = df["close"].rolling(p).mean()
    return df


class _FakeLoader:
    def __init__(self, df=None, err=None):
        self._df, self._err = df, err

    def get_combined_data(self, sid, days, use_adjusted=True):
        return self._df, self._err, f"假股{sid}"


class TestComputeHealthRow(unittest.TestCase):

    def test_normal_row_shape_and_pit_date(self):
        from scripts.update_health_history import compute_health_row
        row, err = compute_health_row("2330", _FakeLoader(_mk_price_df()))
        self.assertIsNone(err)
        self.assertEqual(row["sid"], "2330")
        self.assertEqual(row["date"], "2026-07-10", "PIT 鍵須為最後一根 K 的交易日")
        self.assertTrue(0 <= row["health"] <= 100)
        self.assertGreater(row["close"], 0)
        self.assertIn("source", row)       # §2.2 provenance
        self.assertIn("fetched_at", row)

    def test_empty_df_fails_loud(self):
        from scripts.update_health_history import compute_health_row
        row, err = compute_health_row("9999", _FakeLoader(None, err="雙源皆空"))
        self.assertIsNone(row)
        self.assertIn("雙源皆空", str(err))

    def test_uptrend_scores_above_downtrend(self):
        """行為煙霧:多頭排列分數應高於空頭(公式重用 sanity)。"""
        from scripts.update_health_history import compute_health_row
        up, _ = compute_health_row("U", _FakeLoader(_mk_price_df()))
        dn_df = _mk_price_df()
        dn_df["close"] = dn_df["close"].iloc[::-1].reset_index(drop=True)  # 反轉成下跌
        for p in [5, 10, 20, 60, 100, 120, 240]:
            dn_df[f"MA{p}"] = dn_df["close"].rolling(p).mean()
        dn, _ = compute_health_row("D", _FakeLoader(dn_df))
        self.assertGreater(up["health"], dn["health"])


class TestMergeAndWrite(unittest.TestCase):

    def _rows(self, date="2026-07-10", health=66.0):
        return [{"date": date, "sid": "2330", "health": health, "rsi": 55.0,
                 "close": 1000.0, "source": "t", "fetched_at": "x"}]

    def test_idempotent_same_key_overwrites(self):
        import tempfile
        from pathlib import Path

        from scripts.update_health_history import merge_and_write
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "h.parquet"
            n1 = merge_and_write(self._rows(health=60.0), parquet_path=p)
            n2 = merge_and_write(self._rows(health=70.0), parquet_path=p)  # 同 (date,sid) 重跑
            self.assertEqual((n1, n2), (1, 1), "冪等:同鍵重跑不得增列")
            df = pd.read_parquet(p)
            self.assertAlmostEqual(float(df["health"].iloc[0]), 70.0,
                                   msg="重跑應覆蓋為新值(keep=last)")

    def test_appends_new_dates_sorted(self):
        import tempfile
        from pathlib import Path

        from scripts.update_health_history import merge_and_write
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "h.parquet"
            merge_and_write(self._rows(date="2026-07-10"), parquet_path=p)
            merge_and_write(self._rows(date="2026-07-09"), parquet_path=p)  # 亂序補
            df = pd.read_parquet(p)
            self.assertEqual(len(df), 2)
            self.assertTrue(df["date"].is_monotonic_increasing, "§4.2 date 升序")

    def test_invariant_health_range_enforced(self):
        import tempfile
        from pathlib import Path

        from scripts.update_health_history import merge_and_write
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "h.parquet"
            with self.assertRaises(AssertionError):
                merge_and_write(self._rows(health=150.0), parquet_path=p)


class TestLoadWatchlist(unittest.TestCase):

    def test_missing_file_returns_empty(self):
        from pathlib import Path

        from scripts.update_health_history import load_watchlist
        self.assertEqual(load_watchlist(Path("/nonexistent/wl.json")), [])

    def test_valid_and_empty(self):
        import tempfile
        from pathlib import Path

        from scripts.update_health_history import load_watchlist
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "wl.json"
            p.write_text(json.dumps({"stocks": ["2330", " 2317 ", ""]}), encoding="utf-8")
            self.assertEqual(load_watchlist(p), ["2330", "2317"])
            p.write_text(json.dumps({"stocks": []}), encoding="utf-8")
            self.assertEqual(load_watchlist(p), [])

    def test_repo_default_watchlist_is_valid_json(self):
        """出廠 watchlist 檔須為合法 JSON 且 stocks 為 list(預設空=功能待命)。"""
        from src.services.health_history_service import HEALTH_WATCHLIST_JSON
        data = json.loads(HEALTH_WATCHLIST_JSON.read_text(encoding="utf-8"))
        self.assertIsInstance(data.get("stocks"), list)


class TestServiceLoadAndMerge(unittest.TestCase):

    def test_load_health_history_reads_and_filters(self):
        import tempfile
        from pathlib import Path

        import src.services.health_history_service as hhs
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "h.parquet"
            pd.DataFrame([
                {"date": "2026-07-08", "sid": "2330", "health": 60.0, "rsi": 50.0, "close": 990.0},
                {"date": "2026-07-09", "sid": "2330", "health": 70.0, "rsi": 55.0, "close": 995.0},
                {"date": "2026-07-09", "sid": "2317", "health": 40.0, "rsi": 45.0, "close": 100.0},
            ]).to_parquet(p, index=False)
            _orig = hhs.HEALTH_HISTORY_PARQUET
            try:
                hhs.HEALTH_HISTORY_PARQUET = p
                out = hhs.load_health_history("2330", days=14)
            finally:
                hhs.HEALTH_HISTORY_PARQUET = _orig
        self.assertEqual([r["date"] for r in out], ["2026-07-08", "2026-07-09"])
        self.assertAlmostEqual(out[-1]["health"], 70.0)

    def test_load_missing_file_returns_empty(self):
        from pathlib import Path

        import src.services.health_history_service as hhs
        _orig = hhs.HEALTH_HISTORY_PARQUET
        try:
            hhs.HEALTH_HISTORY_PARQUET = Path("/nonexistent/h.parquet")
            self.assertEqual(hhs.load_health_history("2330"), [])
        finally:
            hhs.HEALTH_HISTORY_PARQUET = _orig

    def test_merge_session_overrides_same_day(self):
        from src.services.health_history_service import merge_score_history
        persisted = [
            {"date": "2026-07-08", "health": 60.0, "rsi": 50.0, "close": 1.0},
            {"date": "2026-07-09", "health": 70.0, "rsi": 55.0, "close": 1.0},
        ]
        session = [{"date": "07/09", "health": 75, "rsi": 58, "total": 0}]  # 盤中即時
        out = merge_score_history(persisted, session, keep=7)
        self.assertEqual([r["date"] for r in out], ["07/08", "07/09"])
        self.assertEqual(out[-1]["health"], 75, "session 即時點應覆蓋同日 cron 快照")

    def test_merge_keep_window_and_bad_dates(self):
        from src.services.health_history_service import merge_score_history
        persisted = [{"date": f"2026-07-{d:02d}", "health": d, "rsi": 1, "close": 1.0}
                     for d in range(1, 11)] + [{"date": "bad", "health": 99}]
        out = merge_score_history(persisted, [], keep=7)
        self.assertEqual(len(out), 7, "只留尾端 keep 筆")
        self.assertEqual(out[-1]["date"], "07/10")
        self.assertTrue(all(r["health"] != 99 for r in out), "壞日期列須略過")


class TestScriptMainE2E(unittest.TestCase):

    def test_main_offline_end_to_end(self):
        """--stocks 指定 + fake loader → parquet + meta 全離線落地。"""
        import tempfile
        from pathlib import Path

        import scripts.update_health_history as upd
        import src.data.core.data_loader as dl_mod

        with tempfile.TemporaryDirectory() as td:
            _p = Path(td) / "h.parquet"
            _m = Path(td) / "meta.json"
            _orig = (upd.HEALTH_HISTORY_PARQUET, upd.HEALTH_HISTORY_META_JSON,
                     dl_mod.StockDataLoader)
            try:
                upd.HEALTH_HISTORY_PARQUET = _p
                upd.HEALTH_HISTORY_META_JSON = _m
                dl_mod.StockDataLoader = lambda: _FakeLoader(_mk_price_df())
                rc = upd.main(["--stocks", "2330,2317"])
            finally:
                (upd.HEALTH_HISTORY_PARQUET, upd.HEALTH_HISTORY_META_JSON,
                 dl_mod.StockDataLoader) = _orig
            self.assertEqual(rc, 0)
            df = pd.read_parquet(_p)
            self.assertEqual(len(df), 2)
            self.assertSetEqual(set(df["sid"]), {"2330", "2317"})
            meta = json.loads(_m.read_text(encoding="utf-8"))
            self.assertEqual((meta["n_ok"], meta["n_fail"]), (2, 0))

    def test_main_per_stock_isolation(self):
        """一檔炸不連坐:另一檔照常入庫,meta.fails 記錄(§5)。"""
        import tempfile
        from pathlib import Path

        import scripts.update_health_history as upd
        import src.data.core.data_loader as dl_mod

        class _Half:
            def get_combined_data(self, sid, days, use_adjusted=True):
                if sid == "9999":
                    raise RuntimeError("boom")
                return _mk_price_df(), None, "ok"

        with tempfile.TemporaryDirectory() as td:
            _p = Path(td) / "h.parquet"
            _m = Path(td) / "meta.json"
            _orig = (upd.HEALTH_HISTORY_PARQUET, upd.HEALTH_HISTORY_META_JSON,
                     dl_mod.StockDataLoader)
            try:
                upd.HEALTH_HISTORY_PARQUET = _p
                upd.HEALTH_HISTORY_META_JSON = _m
                dl_mod.StockDataLoader = lambda: _Half()
                rc = upd.main(["--stocks", "2330,9999"])
            finally:
                (upd.HEALTH_HISTORY_PARQUET, upd.HEALTH_HISTORY_META_JSON,
                 dl_mod.StockDataLoader) = _orig
            self.assertEqual(rc, 0)
            self.assertEqual(len(pd.read_parquet(_p)), 1)
            meta = json.loads(_m.read_text(encoding="utf-8"))
            self.assertEqual(meta["n_fail"], 1)
            self.assertIn("boom", json.dumps(meta["fails"]))


class TestBatchFetcherParallelA2(unittest.TestCase):

    def test_lock_serialization_removed(self):
        with open("src/ui/tabs/stock_grp_sections/section_batch_fetcher.py",
                  encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("_t3_loader_lock", src, "全域 Lock 串行應已移除")
        self.assertNotIn("time.sleep(0.2)", src, "計算迴圈尾 sleep 應已移除")
        self.assertNotIn("import time", src)
        self.assertIn("_get_worker_loader", src, "應改 thread-local loader")
        self.assertIn("threading.local()", src)
        self.assertIn("max_workers=3", src, "FinMind 禮貌上限須維持")

    def test_module_importable_and_worker_loader_isolated(self):
        import threading

        import src.ui.tabs.stock_grp_sections.section_batch_fetcher as bf
        self.assertTrue(callable(bf.run_batch_fetch))
        # thread-local 隔離:兩執行緒各得不同實例(免鎖的前提)
        import src.data.core.data_loader as dl_mod
        _orig = dl_mod.StockDataLoader
        _made = []

        class _Marker:
            def __init__(self):
                _made.append(id(self))
        try:
            dl_mod.StockDataLoader = _Marker
            if hasattr(bf._tls_batch, 'loader'):
                del bf._tls_batch.loader
            got = []

            def _grab():
                got.append(id(bf._get_worker_loader()))
            t1 = threading.Thread(target=_grab)
            t2 = threading.Thread(target=_grab)
            t1.start(); t2.start(); t1.join(); t2.join()
            self.assertEqual(len(set(got)), 2, "各執行緒應持有各自 loader 實例")
        finally:
            dl_mod.StockDataLoader = _orig
            if hasattr(bf._tls_batch, 'loader'):
                del bf._tls_batch.loader


if __name__ == "__main__":
    unittest.main()
