"""💰 存股戰情室 L3：build_station_rows 組表（依賴注入,離線）。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from shared import dividend_station_thresholds as T
from shared import station_specs as SS
from src.compute.etf import dividend_station as ds
from src.services import dividend_station_service as svc


def _wk(n=60, lo=80, hi=120):
    idx = pd.date_range("2022-01-07", periods=n, freq="W-FRI")
    return pd.Series(np.linspace(lo, hi, n), index=idx)


def _good_metrics(ticker, asset_kind='etf'):
    return {"weekly_close": _wk(), "premium_pct": 0.3, "sharpe": 1.1,
            "total_return_1y_pct": 15, "annual_yield_pct": 6, "inception_years": 8,
            "ann_return_3y_pct": 10, "cum_return_3y_pct": None,
            "peer_ranks": {m: 0.2 for m in T.PEER_WINDOWS_MONTHS}}


def test_build_rows_shape_and_pass():
    holdings = [{"ticker": "0056", "name": "高股息", "asset_class": T.ASSET_CORE}]
    rows = svc.build_station_rows(holdings, vix=18, metrics_fn=_good_metrics)
    assert len(rows) == 1
    r = rows[0]
    assert r["代號"] == "0056" and "核心" in r["類別"]
    for col in ("健檢", "235 燈號", "3-3-3", "建議動作", "_detail"):
        assert col in r
    assert r["3-3-3"].startswith("✅")


def test_build_rows_per_ticker_failure_is_isolated():
    def _bad(ticker, asset_kind='etf'):
        raise RuntimeError("no data")
    holdings = [{"ticker": "9999", "name": "壞檔", "asset_class": T.ASSET_SATELLITE}]
    rows = svc.build_station_rows(holdings, vix=None, metrics_fn=_bad)
    assert len(rows) == 1
    assert "資料不足/抓取失敗" in rows[0]["建議動作"]      # §1 誠實標記,不炸整表


def test_build_rows_mixed_good_and_bad():
    calls = {"n": 0}
    def _mixed(ticker, asset_kind='etf'):
        calls["n"] += 1
        if ticker == "BAD":
            raise ValueError("x")
        return _good_metrics(ticker)
    holdings = [{"ticker": "0056", "name": "A", "asset_class": T.ASSET_CORE},
                {"ticker": "BAD", "name": "B", "asset_class": T.ASSET_CORE}]
    rows = svc.build_station_rows(holdings, vix=18, metrics_fn=_mixed)
    assert len(rows) == 2
    assert rows[0]["3-3-3"].startswith("✅")
    assert "抓取失敗" in rows[1]["建議動作"]


def test_build_rows_stock_kind_mj_kd():
    """個股列改走 財報體檢 + KD（§ user 2026-08：不套 235/3-3-3）。

    財報 F + KD 死亡交叉 → 建議換出 🔴。個股 row 不含 235/3-3-3 欄,改含 財報體檢/KD。
    """
    def _stock_metrics(ticker, asset_kind="stock"):
        return {"mj_grade": "F", "mj_score_pct": 20, "mj_headline": "🔴 高危企業",
                "mj_fail_items": ["負債比率", "流動比率"],
                "kd_state": {"k": 82.0, "d": 88.0, "label": "死亡交叉", "cross": "death",
                             "high_passivation": False, "bearish_divergence": False,
                             "bullish_divergence": False, "low_passivation": False},
                "current_price": 30.0}
    holdings = [{"ticker": "2330", "name": "台積電", "asset_class": T.ASSET_SATELLITE,
                 "asset_kind": T.KIND_STOCK}]
    r = svc.build_station_rows(holdings, vix=18, metrics_fn=_stock_metrics)[0]
    assert r["種類"] == "個股"
    assert "3-3-3" not in r and "235 燈號" not in r       # 個股不套 ETF 規則
    assert "財報體檢" in r and "KD" in r
    assert r["健檢"] == "🔴"                              # F + KD 轉弱 → 汰弱換出
    assert "換出" in r["建議動作"]
    assert r["_detail"]["KD交叉"] == "死亡交叉"


def test_build_rows_passes_asset_kind_to_metrics_fn():
    seen = {}
    def _cap(ticker, asset_kind):
        seen[ticker] = asset_kind
        return _good_metrics(ticker)
    holdings = [{"ticker": "0056", "asset_kind": T.KIND_ETF},
                {"ticker": "2330", "asset_kind": T.KIND_STOCK}]
    svc.build_station_rows(holdings, vix=18, metrics_fn=_cap)
    assert seen == {"0056": T.KIND_ETF, "2330": T.KIND_STOCK}


def test_build_rows_skips_blank_ticker():
    rows = svc.build_station_rows([{"ticker": "  ", "name": ""}], vix=18, metrics_fn=_good_metrics)
    assert rows == []


def test_fetch_metrics_wires_real_sources(monkeypatch):
    """稽核 H1/M3 回歸：fetch_metrics 走 fetch_etf_price（非已刪函式）並算出
    週K/報酬/夏普/配息/折溢價,不再每檔都變 error 列。用假 L1 模組注入。"""
    import sys
    import types

    idx = pd.bdate_range("2020-01-02", periods=900)     # ~3.5 年
    close = pd.Series(np.linspace(50, 100, len(idx)), index=idx)
    px = pd.DataFrame({"Close": close})
    divs = pd.Series([1.0, 1.2],
                     index=pd.to_datetime(["2024-07-01", "2025-01-02"]))

    seen = {}
    fake = types.ModuleType("src.data.etf.etf_fetch")
    def _cap_price(t, period="5y"):
        seen["price"] = t
        return px
    fake.fetch_etf_price = _cap_price
    fake.fetch_etf_dividends = lambda t: divs
    fake.fetch_etf_info = lambda t, *a, **k: {}
    monkeypatch.setitem(sys.modules, "src.data.etf.etf_fetch", fake)

    # A2:折溢價改走 calc_premium_discount SSOT;B4:品質 display;B2:rf 注入 —— 皆 patch 隔離網路
    monkeypatch.setattr("src.compute.etf.etf_calc.calc_premium_discount",
                        lambda info, df, tk='': {"premium_pct": 0.5}, raising=False)
    monkeypatch.setattr("src.compute.etf.etf_quality.compute_etf_quality",
                        lambda t: {"stars": None}, raising=False)
    monkeypatch.setattr("src.services.etf_scoring_service.ensure_etf_rf_injected",
                        lambda: None, raising=False)
    # 3-3-3③ 同儕排名已接(#37):隔離掉真同儕抓取,只驗 fetch_metrics 有把它接進 m。
    monkeypatch.setattr(svc, "_fetch_peer_ranks", lambda t: {3: 0.1, 6: 0.2, 12: 0.3})
    m = svc.fetch_metrics("0056")
    assert seen["price"] == "0056.TW", "台股裸碼須正規化補 .TW 再抓,否則 yfinance 抓空整排 error"
    assert "weekly_close" in m and len(m["weekly_close"]) > 20
    assert m["total_return_1y_pct"] is not None
    assert m["ann_return_3y_pct"] is not None
    assert m["sharpe"] is not None
    assert m["annual_yield_pct"] is not None
    assert m["premium_pct"] == 0.5
    assert m["inception_years"] is not None and m["inception_years"] >= 3
    assert m["peer_ranks"] == {3: 0.1, 6: 0.2, 12: 0.3}   # 3-3-3③ 已接(不再 Phase 2 None)


def test_fetch_metrics_stock_kd_via_get_combined_data(monkeypatch):
    """B1(v19.198):個股 KD 改走 StockDataLoader.get_combined_data(4 源鏈,含 .TWO 內部
    fallback,回小寫 OHLC)。回現價 + KD 狀態(非 weekly_close)。財報隔離 → mj_grade None。"""
    idx = pd.bdate_range("2020-01-02", periods=300)
    _base = np.linspace(20, 40, len(idx))
    _df = pd.DataFrame({"close": _base, "high": _base + 0.5, "low": _base - 0.5}, index=idx)
    seen = []
    def _gcd(self, stock_id, days, use_adjusted=True):
        seen.append((stock_id, days, use_adjusted))
        return _df, None, "測試股"
    monkeypatch.setattr("src.data.core.data_loader.StockDataLoader.get_combined_data",
                        _gcd, raising=False)
    # 隔離財報 + 名稱網路（本測聚焦 KD 計算走新來源）
    monkeypatch.setattr(
        "src.data.core.financial_statements_fetcher.fetch_financial_statements",
        lambda *a, **k: {"error": "test-skip"}, raising=False)
    monkeypatch.setattr("src.config.stock_names.get_stock_name",
                        lambda code: code, raising=False)
    m = svc.fetch_metrics("5314", asset_kind=T.KIND_STOCK)
    assert seen and seen[0][0] == "5314"                     # 走 get_combined_data(裸碼,非 .TW)
    assert m["current_price"] == pytest.approx(40.0, abs=1.0)
    assert m["kd_state"] is not None and m["kd_state"].get("k") is not None
    assert m["mj_grade"] is None                             # 財報隔離 → 標資料不足


def test_fetch_metrics_no_daily_raises(monkeypatch):
    """日線抓不到 → raise（該列標抓取失敗,§1 不假裝成功；不再被當資料不足吞掉）。"""
    import sys
    import types
    fake = types.ModuleType("src.data.etf.etf_fetch")
    fake.fetch_etf_price = lambda t, period="5y": pd.DataFrame()
    monkeypatch.setitem(sys.modules, "src.data.etf.etf_fetch", fake)
    with pytest.raises(ValueError):
        svc.fetch_metrics("9999")


def test_row_detail_has_health_and_235():
    holdings = [{"ticker": "0056", "name": "高股息", "asset_class": T.ASSET_CORE}]
    r = svc.build_station_rows(holdings, vix=18, metrics_fn=_good_metrics)[0]
    d = r["_detail"]
    for k in ("健檢A", "健檢B", "健檢C", "健檢D", "235觸發", "3-3-3明細"):
        assert k in d


# ── AI 戰情總結（digest 純函式 + AI 潤稿注入）──────────────────────────────
def _rows_fixture():
    """涵蓋：紅燈汰弱 / 235 加碼 / 抓取失敗 / 正常 四種列。"""
    return [
        {"代號": "2412", "健檢": "🔴", "加碼金": "", "235 燈號": "⚪ 巡航",
         "建議動作": "汰弱：賺息賠本", "_detail": {}},
        {"代號": "0056", "健檢": "🟡", "加碼金": "20%", "235 燈號": "🟢 小跌加碼",
         "建議動作": "小跌加碼", "_detail": {}},
        {"代號": "9999", "健檢": "⚪", "加碼金": "", "235 燈號": "—",
         "建議動作": "⚠️ 資料不足/抓取失敗：無日線", "_detail": {"error": "無日線"}},
        {"代號": "00878", "健檢": "🟢", "加碼金": "", "235 燈號": "⚪ 巡航",
         "建議動作": "續抱", "_detail": {}},
    ]


def test_digest_classifies_reds_adds_errors():
    d = svc.build_station_digest(_rows_fixture(), vix=22.5)
    assert [r["代號"] for r in d["reds"]] == ["2412"]        # 只有 🔴 進汰弱
    assert [a["代號"] for a in d["adds"]] == ["0056"]        # 加碼金非空 = 235 觸發
    assert d["errors"] == ["9999"]                           # error 列誠實排除
    assert d["total"] == 3                                   # 有效 = 4 - 1 抓取失敗
    assert d["vix"] == 22.5


def test_digest_no_fake_config_key():
    """§1：戰情室無部位金額 → digest 不得捏造核心/衛星配置偏離。"""
    d = svc.build_station_digest(_rows_fixture())
    assert not any("配置" in k or "core" in k.lower() for k in d.keys())


def test_digest_empty_rows():
    d = svc.build_station_digest([], vix=None)
    assert d == {"total": 0, "vix": None, "reds": [], "adds": [], "errors": [],
                 "allocation": None, "take_profit": []}


def test_summary_prompt_contains_facts_and_hold_instruction():
    d = svc.build_station_digest(_rows_fixture(), vix=22.5)
    p = svc.build_summary_prompt(d)
    assert "2412" in p and "0056" in p          # 汰弱 + 加碼代號都入 prompt
    assert "22.5" in p                          # VIX 帶入
    assert "續抱" in p                          # 無事時要 AI 明講續抱
    assert "杜撰" in p                          # §1：禁 AI 生數字的指示


def test_build_ai_summary_injects_prompt_and_returns_text():
    seen = {}
    def _fake_gemini(prompt, max_tokens=2048):
        seen["prompt"] = prompt
        seen["max_tokens"] = max_tokens
        return "今日 2412 亮紅燈建議汰弱,0056 小跌可加碼 20%。"
    d = svc.build_station_digest(_rows_fixture(), vix=22.5)
    out = svc.build_ai_summary(d, _fake_gemini)
    assert "2412" in seen["prompt"]             # digest 事實有進 prompt
    assert out.startswith("今日")               # 回傳 AI 文字原樣
    assert seen["max_tokens"] == 700            # 推播摘要(含換股建議)短輸出


def test_build_ai_summary_propagates_failure():
    """§1：AI 失敗往上拋,不吞成假摘要。"""
    def _boom(prompt, max_tokens=2048):
        raise RuntimeError("gemini down")
    d = svc.build_station_digest(_rows_fixture())
    with pytest.raises(RuntimeError):
        svc.build_ai_summary(d, _boom)


# ── 代號規則判 ETF/個股（L0,跟清單脫鉤）────────────────────────────────────
def test_classify_asset_kind_by_code():
    assert T.classify_asset_kind("0050.TW") == T.KIND_ETF        # 00 開頭 ETF
    assert T.classify_asset_kind("00980A.TW") == T.KIND_ETF      # 帶字母後綴仍 ETF（00 先攔）
    assert T.classify_asset_kind("00878") == T.KIND_ETF
    assert T.classify_asset_kind("2330") == T.KIND_STOCK         # 4 碼個股
    assert T.classify_asset_kind("6239.TWO") == T.KIND_STOCK     # 上櫃 4 碼個股
    assert T.classify_asset_kind("2881A") == T.KIND_STOCK        # 特別股 → 個股（稽核2a）
    assert T.classify_asset_kind("2882A.TW") == T.KIND_STOCK     # 特別股帶後綴 → 個股
    assert T.classify_asset_kind("BND") == T.KIND_ETF            # 非台股 → 預設 ETF
    assert T.classify_asset_kind("") == T.KIND_ETF               # 空 → 預設,不炸


def test_normalize_ticker():
    """後綴 SSOT:去 .TW/.TWO + 大寫;空/None 不炸。"""
    assert T.normalize_ticker("2330.TW") == "2330"
    assert T.normalize_ticker("6239.two") == "6239"
    assert T.normalize_ticker(" 0050 ") == "0050"
    assert T.normalize_ticker("2330") == "2330"
    assert T.normalize_ticker(None) == ""


def test_get_switch_in_candidates_excludes_held_suffix_aware(monkeypatch):
    """稽核1b+6a:已持有 2330.TW 必須擋掉 bare 2330 候選（exclude 走 normalize_ticker）。"""
    import src.services.fundamental_screener_service as FS
    _df = pd.DataFrame([{"代碼": "2330", "名稱": "台積電", "綜合分": 90},
                        {"代碼": "2317", "名稱": "鴻海", "綜合分": 80}])
    monkeypatch.setattr(FS, "get_ranked_picks", lambda *a, **k: (_df, ""))
    out = svc.get_switch_in_candidates(exclude=["2330.TW"], top_n=5)
    _codes = [c["代碼"] for c in out]
    assert "2330" not in _codes, "已持有(2330.TW)卻把 bare 2330 當換入候選"
    assert "2317" in _codes


def test_get_switch_in_candidates_empty_on_screener_fail(monkeypatch):
    """§1:選股網不可用 → 回 []（不捏造標的）。"""
    import src.services.fundamental_screener_service as FS
    def _boom(*a, **k):
        raise RuntimeError("screener down")
    monkeypatch.setattr(FS, "get_ranked_picks", _boom)
    assert svc.get_switch_in_candidates(exclude=[]) == []


# ── held 旗標傳遞（換股建議依賴）─────────────────────────────────────────
def test_build_rows_propagates_held_flag():
    holdings = [{"ticker": "0056", "asset_class": T.ASSET_CORE, "held": True},
                {"ticker": "2330", "asset_kind": T.KIND_STOCK,
                 "asset_class": T.ASSET_SATELLITE, "held": False}]
    rows = svc.build_station_rows(holdings, vix=18, metrics_fn=_good_metrics)
    assert rows[0]["held"] is True and rows[1]["held"] is False


def test_build_rows_held_defaults_true_and_on_error():
    def _bad(t, ak='etf'):
        raise RuntimeError("x")
    rows = svc.build_station_rows([{"ticker": "9999", "held": False}],
                                  vix=None, metrics_fn=_bad)
    assert rows[0]["held"] is False and "抓取失敗" in rows[0]["建議動作"]  # error 列也帶 held


# ── 換股建議純函式 ───────────────────────────────────────────────────────
def _switch_rows():
    return [
        {"代號": "00980D", "健檢": "🔴", "建議動作": "汰弱:賺息賠本", "held": True, "_detail": {}},
        {"代號": "2412", "健檢": "🔴", "建議動作": "紅燈", "held": False, "_detail": {}},  # 觀察紅燈≠換出
        {"代號": "0056", "健檢": "🟢", "建議動作": "續抱", "held": True, "_detail": {}},
    ]


def test_switch_out_only_held_reds():
    """換出只含**持有**的紅燈;觀察清單的紅燈(未持有)不算換出。"""
    adv = svc.build_switch_advice(_switch_rows(),
                                  {"loaded": True, "defense": False, "regime": "neutral"},
                                  candidates=[])
    assert [d["代號"] for d in adv["switch_out"]] == ["00980D"]     # 2412 是觀察紅燈,排除
    assert adv["stance"] == "neutral"


def test_switch_in_from_candidates_and_defense_trims():
    cands = [{"代碼": f"C{i}", "名稱": f"n{i}", "綜合分": 90 - i} for i in range(6)]
    # 正常(非防禦)→ 給 5 檔
    adv_n = svc.build_switch_advice(_switch_rows(), {"loaded": True, "defense": False,
                                                     "regime": "neutral"}, cands)
    assert len(adv_n["switch_in"]) == 5
    # 轉守 → 換入從嚴,只給 3 檔 + stance defensive
    adv_d = svc.build_switch_advice(_switch_rows(), {"loaded": True, "defense": True,
                                                     "regime": "bear"}, cands)
    assert len(adv_d["switch_in"]) == 3 and adv_d["stance"] == "defensive"


def test_switch_unknown_regime_no_posture_guess():
    """§1：位階未評估 → stance=unknown,不套攻守方向。"""
    adv = svc.build_switch_advice(_switch_rows(), {"loaded": False}, candidates=[])
    assert adv["stance"] == "unknown" and adv["loaded"] is False
    assert adv["defense"] is None            # 未評估不回填 False/True


def test_summary_prompt_has_switch_but_never_regime():
    d = svc.build_station_digest(_switch_rows())
    adv = svc.build_switch_advice(_switch_rows(),
                                  {"loaded": True, "defense": True, "regime": "bear",
                                   "posture_label": "🔴 防禦"},
                                  [{"代碼": "2412", "名稱": "中華電", "綜合分": 88}])
    p = svc.build_summary_prompt(d, switch=adv)
    assert "換股建議" in p
    assert "00980D" in p and "2412" in p          # 換出/換入都入 prompt
    # 2026-08-24 user 指定移除總經位階。LINE 本文那行刪了,AI prompt 這邊若留著,
    # 總結段落還是會講位階 —— 使用者看到訊息沒有的數字,無從對照來源。
    # 反向守衛:regime 值(bear)、姿態、攻守指引都不得再進 prompt。
    assert "bear" not in p, "總經位階值仍進了 AI prompt"
    assert "換入從嚴" not in p, "攻守指引仍進了 AI prompt"
    # 註:禁止指示本身刻意不寫「建議持股」四個字(改寫成「持股成數」),
    # 這條守衛才不會被自己的禁止句觸發 —— 守衛要能分辨「講了」與「叫 AI 別講」。
    assert "建議持股" not in p, "建議持股比例仍進了 AI prompt"
    assert "不要" in p and "總經位階" in p, "缺少『禁止 AI 自行補位階』的指示"


# ── 3-3-3③ 同儕排名 adapter（#37：接 compute_etf_peer_ranking）──────────────
def test_fetch_peer_ranks_converts_percentile_and_days(monkeypatch):
    """percentile(越高越強)→分位(0=最強) = (100-p)/100;交易日 63/126/252→月 3/6/12。"""
    from src.compute.etf import etf_calc
    monkeypatch.setattr(etf_calc, "compute_etf_peer_ranking",
                        lambda t, periods=(63, 126, 252): {
                            63: {"percentile": 90.0}, 126: {"percentile": 50.0},
                            252: {"percentile": 70.0}, "category": "高股息", "peers": ["a", "b", "c"]})
    out = svc._fetch_peer_ranks("0056.TW")
    assert set(out.keys()) == {3, 6, 12}
    assert out[3] == pytest.approx(0.1)      # 贏 90% → 分位 0.1(前段)
    assert out[6] == pytest.approx(0.5)
    assert out[12] == pytest.approx(0.3)


def test_fetch_peer_ranks_err_returns_none(monkeypatch):
    """§1：同儕不足/抓取失敗(_err) → None（→ kernel peer_ok 維持「待資料」不硬判）。"""
    from src.compute.etf import etf_calc
    monkeypatch.setattr(etf_calc, "compute_etf_peer_ranking",
                        lambda t, periods=(63, 126, 252): {"_err": "同儕資料不足", "category": ""})
    assert svc._fetch_peer_ranks("0056.TW") is None


def test_fetch_peer_ranks_partial_window_omitted(monkeypatch):
    """某視窗資料不足 → 該月不填(partial) → kernel 因不齊而不判定(§1)。"""
    from src.compute.etf import etf_calc
    monkeypatch.setattr(etf_calc, "compute_etf_peer_ranking",
                        lambda t, periods=(63, 126, 252): {
                            63: {"percentile": 80.0}, 126: {"_err": "資料不足 126 日"},
                            252: {"percentile": 60.0}})
    out = svc._fetch_peer_ranks("0056.TW")
    assert set(out.keys()) == {3, 12}        # 6M 缺 → 不填


def test_fetch_peer_ranks_swallows_exception(monkeypatch):
    """compute 拋例外 → None，不擋整檔健檢。"""
    from src.compute.etf import etf_calc
    def _boom(t, periods=(63, 126, 252)):
        raise RuntimeError("net down")
    monkeypatch.setattr(etf_calc, "compute_etf_peer_ranking", _boom)
    assert svc._fetch_peer_ranks("0056.TW") is None


# ── #38：80/20 配置偏離 + 衛星停利（有張數/均價才算）────────────────────────
def _alloc_rows():
    return [
        {"代號": "0056", "種類": "ETF", "held": True, "市值": 800000.0, "損益%": 5.0,
         "健檢": "🟢", "_detail": {}},
        {"代號": "2330", "種類": "個股", "held": True, "市值": 300000.0, "損益%": 18.0,
         "健檢": "🟢", "_detail": {}},
        {"代號": "6239", "種類": "個股", "held": True, "市值": None, "損益%": None,
         "健檢": "🟢", "_detail": {}},                         # 缺金額
        {"代號": "1101", "種類": "個股", "held": False, "市值": 999.0, "損益%": 50.0,
         "健檢": "🟢", "_detail": {}},                         # 觀察(未持有)不算
    ]


def test_allocation_split_core_satellite_and_partial():
    a = svc.compute_allocation_split(_alloc_rows())
    # 核心(ETF 0056)80萬 / 衛星(個股 2330)30萬 → 核心 72.7%
    assert a["core_pct"] == pytest.approx(72.7, abs=0.1)
    assert a["sat_pct"] == pytest.approx(27.3, abs=0.1)
    assert a["core_dev"] == pytest.approx(-7.3, abs=0.1)      # 目標 80 → 偏離 -7.3
    assert a["partial"] is True and a["held_n"] == 3 and a["valued_n"] == 2  # 6239 缺,觀察排除


def test_allocation_split_none_when_no_market_value():
    rows = [{"代號": "0056", "種類": "ETF", "held": True, "市值": None, "_detail": {}}]
    assert svc.compute_allocation_split(rows) is None      # §1 無市值不捏造


def test_take_profit_satellite_over_threshold_only():
    tp = svc.flag_take_profit(_alloc_rows())
    assert [d["代號"] for d in tp] == ["2330"]             # 個股 +18%≥15;ETF/觀察/無成本都不列


def test_take_profit_skips_no_cost_and_etf():
    rows = [
        {"代號": "00878", "種類": "ETF", "held": True, "損益%": 30.0, "_detail": {}},   # ETF 不算衛星停利
        {"代號": "3006", "種類": "個股", "held": True, "損益%": None, "_detail": {}},   # 無成本 → 不判
        {"代號": "6770", "種類": "個股", "held": False, "損益%": 40.0, "_detail": {}},  # 觀察不算
    ]
    assert svc.flag_take_profit(rows) == []


def test_build_rows_computes_market_value_and_pnl():
    """build_station_rows 由 holding lots/avg + metrics current_price 算市值/損益%。"""
    def _m(t, ak="etf"):
        return {"weekly_close": _wk(), "sharpe": 1.0, "current_price": 60.0,
                "inception_years": 8, "ann_return_3y_pct": 10, "total_return_1y_pct": 15,
                "annual_yield_pct": 6, "peer_ranks": None}
    holdings = [{"ticker": "2330", "asset_kind": T.KIND_STOCK,
                 "asset_class": T.ASSET_SATELLITE, "held": True,
                 "lots": 2.0, "avg_price": 50.0}]
    r = svc.build_station_rows(holdings, vix=18, metrics_fn=_m)[0]
    assert r["市值"] == pytest.approx(120.0)                # 2 張 × 60
    assert r["損益%"] == pytest.approx(20.0)                # (60/50-1)*100


def test_build_rows_market_value_none_without_lots():
    """§1：無張數/均價 → 市值/損益% = None(不捏 0)。"""
    def _m(t, ak="etf"):
        return {"weekly_close": _wk(), "sharpe": 1.0, "current_price": 60.0,
                "inception_years": 8, "peer_ranks": None}
    holdings = [{"ticker": "0056", "held": True}]           # 無 lots/avg
    r = svc.build_station_rows(holdings, vix=18, metrics_fn=_m)[0]
    assert r["市值"] is None and r["損益%"] is None


def test_summary_prompt_includes_allocation_and_take_profit():
    d = svc.build_station_digest(_alloc_rows(), vix=18)
    p = svc.build_summary_prompt(d)
    assert "實際配置" in p and "核心 73%" in p and "偏離 -7%" in p
    assert "衛星達停利" in p and "2330(+18%)" in p
    assert f"≥{T.SATELLITE_TAKE_PROFIT_PCT:.0f}%" in p   # §3.3 門檻走 SSOT(改門檻不漂移)


# ── #34：換股建議換入優先用觀察清單綠燈（空才 fallback 選股池）─────────────
def test_switch_in_prefers_watchlist_greens():
    rows = [{"代號": "00980D", "健檢": "🔴", "held": True, "建議動作": "汰弱", "_detail": {}},
            {"代號": "2412", "名稱": "中華電", "健檢": "🟢", "held": False, "_detail": {}},  # 觀察綠燈
            {"代號": "2330", "健檢": "🟢", "held": True, "_detail": {}}]                    # 持有綠燈≠換入
    cands = [{"代碼": "9999", "名稱": "選股池股", "綜合分": 88}]
    a = svc.build_switch_advice(rows, {"loaded": False}, cands)
    assert a["switch_in_src"] == "watchlist"
    assert [d["代號"] for d in a["switch_in"]] == ["2412"]     # 觀察綠燈,非持有綠燈/非選股池


def test_switch_in_fallback_to_screener_when_no_watchlist_greens():
    rows = [{"代號": "00980D", "健檢": "🔴", "held": True, "建議動作": "汰弱", "_detail": {}}]
    cands = [{"代碼": "9999", "名稱": "選股池股", "綜合分": 88}]
    b = svc.build_switch_advice(rows, {"loaded": False}, cands)
    assert b["switch_in_src"] == "screener"
    assert [d["代號"] for d in b["switch_in"]] == ["9999"]


# ── 名稱解析 + 個股組表（v19.x 名稱抓進 + 個股 財報體檢/KD 分區）─────────────
def test_resolve_holding_names_stock_etf_and_fallback(monkeypatch):
    """ETF→fetch_etf_zh_name、個股→get_stock_name;查無留空、已有不覆蓋（§1 不捏造）。"""
    import sys
    import types
    monkeypatch.setattr("src.config.stock_names.get_stock_name",
                        lambda code: {"2330": "台積電"}.get(code, code), raising=False)
    fake = types.ModuleType("src.data.etf.etf_fetch")
    fake.fetch_etf_zh_name = lambda t: {"0056": "元大高股息"}.get(t)
    monkeypatch.setitem(sys.modules, "src.data.etf.etf_fetch", fake)

    holdings = [
        {"ticker": "2330", "name": "", "asset_kind": T.KIND_STOCK},
        {"ticker": "0056", "name": "", "asset_kind": T.KIND_ETF},
        {"ticker": "9999", "name": "", "asset_kind": T.KIND_STOCK},   # 查無→回代號→留空
        {"ticker": "0050", "name": "既有", "asset_kind": T.KIND_ETF},  # 已有→不覆蓋
    ]
    out = svc.resolve_holding_names(holdings)
    assert out is holdings                                    # 就地更新回同一 list
    assert holdings[0]["name"] == "台積電"
    assert holdings[1]["name"] == "元大高股息"
    assert holdings[2]["name"] == ""                          # §1 查無留空
    assert holdings[3]["name"] == "既有"


def test_stock_row_from_assessment_shape():
    sa = ds.assess_stock(ticker="2330", name="台積電", asset_class=T.ASSET_SATELLITE,
                         mj_grade="A", mj_score_pct=85, mj_headline="🟢 優質",
                         mj_fail_items=[],
                         kd={"k": 70.0, "d": 65.0, "label": "黃金交叉", "cross": "golden",
                             "high_passivation": False, "low_passivation": False,
                             "bearish_divergence": False, "bullish_divergence": False})
    row = svc.stock_row_from_assessment(sa)
    assert row["種類"] == "個股" and row["名稱"] == "台積電"
    assert row["財報體檢"] == "A（85）"
    assert row["KD"].startswith("K70") and "黃金交叉" in row["KD"]
    assert row["健檢"] == sa.swap_level                       # 復用鍵給下游/高亮
    assert row["_detail"]["KD交叉"] == "黃金交叉"
    assert "3-3-3" not in row and "235 燈號" not in row       # 個股不含 ETF 欄


def test_stock_row_data_insufficient_labels():
    sa = ds.assess_stock(ticker="9999", name="", asset_class=T.ASSET_SATELLITE,
                         mj_grade=None, mj_score_pct=None, mj_headline="",
                         mj_fail_items=None, kd=None)
    row = svc.stock_row_from_assessment(sa)
    assert row["財報體檢"] == "資料不足" and row["KD"] == "資料不足"


def test_fetch_vix_via_fetch_yf_close(monkeypatch):
    """D1(v19.198):VIX 改走 macro_core.fetch_yf_close(全站 SSOT 抓取點,NAS proxy+cache),
    取序列末值,不再直呼 yfinance。"""
    monkeypatch.setattr("src.data.macro.macro_core.fetch_yf_close",
                        lambda t, range_="6mo": pd.Series([15.0, 16.5, 17.2]), raising=False)
    assert svc.fetch_vix() == pytest.approx(17.2)


def test_build_rows_etf_quality_expense_pct():
    """B4/M1:ETF 品質 display —— 費用率為比例(0.0036),顯示須 ×100 = 0.36%(非 0.00%,§4.1)。"""
    def _m(ticker, asset_kind='etf'):
        d = _good_metrics(ticker)
        d["etf_quality"] = {"stars": 4, "factors": {
            "aum": {"val": 5e10, "score": 1.0},
            "expense": {"val": 0.0036, "score": 0.9}}}
        return d
    r = svc.build_station_rows([{"ticker": "0056", "asset_class": T.ASSET_CORE}],
                               vix=18, metrics_fn=_m)[0]
    _q = r["_detail"]["ETF品質"]
    assert "費用率 0.36%" in _q          # 比例 0.0036 ×100 = 0.36%,非壓成 0.00%
    assert "AUM 500億" in _q


def test_build_rows_etf_quality_liquidation_risk():
    """B4:AUM 因子 score≤0(=AUM≤10億)→ 顯示清算風險徽章(不另立門檻,§3.3)。"""
    def _m(ticker, asset_kind='etf'):
        d = _good_metrics(ticker)
        d["etf_quality"] = {"stars": 2, "factors": {
            "aum": {"val": 5e8, "score": 0.0},      # 5億 → score 0 → 清算風險
            "expense": {"val": 0.005, "score": 0.5}}}
        return d
    r = svc.build_station_rows([{"ticker": "00xxx", "asset_class": T.ASSET_CORE}],
                               vix=18, metrics_fn=_m)[0]
    assert "清算風險" in r["_detail"]["ETF品質"]


# ── 週線走勢圖原料 `_weekly_series`（L3 把序列帶出來,#階段D 第二塊）────────
class TestWeeklySeriesPayload:
    """`build_station_rows` 每一列都要帶走勢圖原料;缺的要說得出為什麼（§1）。

    這一組守的是三件事:
      1. 圖上的線與 235 燈**同一把尺**（序列末值 == L2 純量版,用容差不用 `==`,§4.3）;
      2. 畫不出來的線各自帶原因,而且**原因不能給錯的指引**（個股 ≠ 抓取失敗）;
      3. 鍵**永遠在**，消費端不必靠「鍵在不在」去猜（§1 不留靜默）。
    """

    _KEY = svc.KEY_WEEKLY_SERIES

    def _etf_metrics(self, n):
        def _m(ticker, asset_kind="etf"):
            d = _good_metrics(ticker)
            d["weekly_close"] = _wk(n)
            return d
        return _m

    def _stock_metrics(self, ticker, asset_kind="stock"):
        return {"mj_grade": "B", "mj_score_pct": 70, "mj_headline": "ok",
                "mj_fail_items": [],
                "kd_state": {"k": 50.0, "d": 50.0, "label": "—", "cross": "none",
                             "high_passivation": False, "bearish_divergence": False,
                             "bullish_divergence": False, "low_passivation": False},
                "current_price": 30.0}

    def _etf_row(self, n=60):
        return svc.build_station_rows(
            [{"ticker": "0056", "name": "高股息", "asset_class": T.ASSET_CORE}],
            vix=18, metrics_fn=self._etf_metrics(n))[0]

    def test_key_is_non_display_and_always_present(self):
        """三種列型（ETF / 個股 / 抓取失敗）都要有鍵,且是底線開頭的非顯示欄。"""
        def _boom(ticker, asset_kind="etf"):
            raise RuntimeError("x")
        _etf = self._etf_row()
        _stk = svc.build_station_rows(
            [{"ticker": "2330", "asset_class": T.ASSET_SATELLITE,
              "asset_kind": T.KIND_STOCK}], vix=18, metrics_fn=self._stock_metrics)[0]
        _err = svc.build_station_rows(
            [{"ticker": "9999", "asset_class": T.ASSET_CORE}],
            vix=None, metrics_fn=_boom)[0]
        assert self._KEY.startswith("_")          # 非顯示欄（不進 _ETF_COLS / _STOCK_COLS）
        for _r in (_etf, _stk, _err):
            assert self._KEY in _r

    def test_series_tail_matches_scalar_kernel(self):
        """序列末值 ≡ L2 純量版（§4.3 對帳,math.isclose 不用 ==）。"""
        import math
        _p = self._etf_row(60)[self._KEY]
        _w = _wk(60)
        for _win in (T.MA_MONTH_WEEKS, T.MA_QUARTER_WEEKS, T.MA_YEAR_WEEKS):
            _scalar = ds.week_ma(_w, _win)
            _tail = float(_p["ma"][_win].iloc[-1])
            if _scalar is None:
                assert math.isnan(_tail)
            else:
                assert math.isclose(_scalar, _tail, rel_tol=1e-12)
        _z = ds.bollinger_z(_w)
        assert math.isclose(_z, float(_p["boll_z"].iloc[-1]), rel_tol=1e-12)

    def test_enough_weeks_no_miss(self):
        _p = self._etf_row(260)[self._KEY]
        assert _p["miss_reason"] == "" and _p["ma_miss"] == {} and _p["boll_z_miss"] == ""
        assert _p["n_weeks"] == 260 and len(_p["close"]) == 260
        assert _p["boll_period_weeks"] == T.BOLL_PERIOD_WEEKS

    def test_short_history_marks_not_enough_per_line(self):
        """30 週:年線畫不出（NOT_ENOUGH）,月線/季線/布林照畫 —— 逐條,不是整組砍掉。"""
        _p = self._etf_row(30)[self._KEY]
        assert _p["miss_reason"] == ""                    # 週收本身畫得出來
        assert _p["ma_miss"] == {T.MA_YEAR_WEEKS: SS.MISS_NOT_ENOUGH}
        assert _p["boll_z_miss"] == ""

    def test_very_short_history_marks_boll_not_enough(self):
        _p = self._etf_row(10)[self._KEY]
        assert _p["boll_z_miss"] == SS.MISS_NOT_ENOUGH
        assert _p["ma_miss"] == {T.MA_QUARTER_WEEKS: SS.MISS_NOT_ENOUGH,
                                 T.MA_YEAR_WEEKS: SS.MISS_NOT_ENOUGH}

    def _flat_row(self, n: int = 60, value: float = 50.0):
        def _m(ticker, asset_kind="etf"):
            d = _good_metrics(ticker)
            _idx = pd.date_range("2022-01-07", periods=n, freq="W-FRI")
            d["weekly_close"] = pd.Series([value] * n, index=_idx)
            return d
        return svc.build_station_rows([{"ticker": "0056", "asset_class": T.ASSET_CORE}],
                                      vix=18, metrics_fn=_m)[0][self._KEY]

    def test_flat_price_boll_is_no_variation(self):
        """週數夠但整段零波動（std≈0）→ 布林 z 無有限值 → `MISS_NO_VARIATION`。

        ⚠️ **本條原本斷言的是 `MISS_NO_INPUT`,那個行為是錯的**（2026-08-27 改）。
        舊 docstring 的理由是「沿用 `light_235` 對布林軸算不出來的既有標法」——
        但 `MISS_NO_INPUT` 的**使用者文案**是「上游這輪失敗,**可以重跑一次**」,
        而零波動重跑一百次 std 還是 0。**是這條測試把錯的指引釘成了規格,
        不是有人為了讓測試過而改測試。**

        `MISS_NOT_ENOUGH` 同樣不對（筆數是夠的,「等時間累積」也不是該做的事）——
        這一點舊 docstring 講對了,故保留在測試名字裡的對照斷言。
        """
        _p = self._flat_row()
        assert _p["boll_z_miss"] == SS.MISS_NO_VARIATION
        assert _p["boll_z_miss"] not in (SS.MISS_NO_INPUT, SS.MISS_NOT_ENOUGH)
        assert _p["ma_miss"] == {}                        # 均線照畫得出來（平盤也是線）

    def test_no_variation_text_never_tells_the_user_to_rerun(self):
        """**語意鎖**:使用者看到的是文案不是常數名 —— 文案不得叫人重跑。

        只鎖常數不鎖文案的話,有人把文案改回「可以重跑一次」照樣全綠。
        """
        _txt = SS.MISS_TEXT[SS.MISS_NO_VARIATION]
        assert "重跑不會改變" in _txt
        assert "可以重跑" not in _txt
        assert "等時間累積" not in _txt, "那是 MISS_NOT_ENOUGH 的指引,不適用零波動"

    def test_all_nan_weekly_close_is_still_no_input(self):
        """週收本身全 NaN（不是零波動）→ 仍是 `MISS_NO_INPUT`,新常數不得吃掉它。

        這一條分辨的是「有數字但不動」與「根本沒有數字」—— 兩者該做的事不同。
        """
        def _m(ticker, asset_kind="etf"):
            d = _good_metrics(ticker)
            _idx = pd.date_range("2022-01-07", periods=60, freq="W-FRI")
            d["weekly_close"] = pd.Series([float("nan")] * 60, index=_idx)
            return d
        _p = svc.build_station_rows([{"ticker": "0056", "asset_class": T.ASSET_CORE}],
                                    vix=18, metrics_fn=_m)[0][self._KEY]
        assert _p["boll_z_miss"] == SS.MISS_NO_INPUT
        # 均線同樣算不出來,且原因一致（都是「沒有輸入」,不是「沒在動」）
        assert set(_p["ma_miss"].values()) == {SS.MISS_NO_INPUT}

    def test_short_flat_history_is_still_not_enough(self):
        """10 週且平盤 → 先卡「筆數不夠」,不被新常數吃掉（長度問題優先）。"""
        _p = self._flat_row(10)
        assert _p["boll_z_miss"] == SS.MISS_NOT_ENOUGH

    @pytest.mark.parametrize("value", [0.0, 50.0, 1e6])
    def test_any_constant_series_is_no_variation(self, value):
        """property 版:任何常數序列（含 0）都該是零波動,與那個常數是多少無關。"""
        assert self._flat_row(60, value)["boll_z_miss"] == SS.MISS_NO_VARIATION

    def test_one_different_week_is_enough_to_not_be_flat(self):
        """反向:只要有一週不同 → 布林 z 算得出來,不得標成零波動。"""
        def _m(ticker, asset_kind="etf"):
            d = _good_metrics(ticker)
            _idx = pd.date_range("2022-01-07", periods=60, freq="W-FRI")
            _vals = [50.0] * 60
            _vals[30] = 51.0
            d["weekly_close"] = pd.Series(_vals, index=_idx)
            return d
        _p = svc.build_station_rows([{"ticker": "0056", "asset_class": T.ASSET_CORE}],
                                    vix=18, metrics_fn=_m)[0][self._KEY]
        assert _p["boll_z_miss"] == ""

    def test_stock_row_is_not_applicable(self):
        """個股列**結構上沒有**這張圖 → NOT_APPLICABLE,不是「資料不足 / 重跑就好」。"""
        _p = svc.build_station_rows(
            [{"ticker": "2330", "asset_class": T.ASSET_SATELLITE,
              "asset_kind": T.KIND_STOCK}], vix=18,
            metrics_fn=self._stock_metrics)[0][self._KEY]
        assert _p["miss_reason"] == SS.MISS_NOT_APPLICABLE
        assert _p["n_weeks"] == 0 and len(_p["close"]) == 0
        # 給錯指引的那三個都不可以出現
        assert _p["miss_reason"] not in (SS.MISS_NOT_ENOUGH, SS.MISS_NO_INPUT,
                                         SS.MISS_FETCH_FAILED)

    def test_error_row_reason_depends_on_kind(self):
        """抓取失敗列:ETF → FETCH_FAILED;**個股 → 仍是 NOT_APPLICABLE**。

        個股那張圖抓得成不成功都不存在,標 FETCH_FAILED 等於叫人去修一個修好也
        不會出圖的東西（§1 錯的指引比沒有指引更危險）。
        """
        def _boom(ticker, asset_kind="etf"):
            raise RuntimeError("boom")
        _etf = svc.build_station_rows([{"ticker": "0050", "asset_class": T.ASSET_CORE}],
                                      vix=None, metrics_fn=_boom)[0]
        _stk = svc.build_station_rows(
            [{"ticker": "2317", "asset_class": T.ASSET_SATELLITE,
              "asset_kind": T.KIND_STOCK}], vix=None, metrics_fn=_boom)[0]
        assert _etf[self._KEY]["miss_reason"] == SS.MISS_FETCH_FAILED
        assert _stk[self._KEY]["miss_reason"] == SS.MISS_NOT_APPLICABLE
        assert _etf["_miss_reason"] == SS.MISS_FETCH_FAILED   # 整列原因照舊,未被連動

    def test_no_extra_fetch(self):
        """零新增外部抓取:序列本來就在 metrics 裡,metrics_fn 仍只被呼叫一次/檔。"""
        _calls = {"n": 0}
        _inner = self._etf_metrics(60)
        def _count(ticker, asset_kind="etf"):
            _calls["n"] += 1
            return _inner(ticker, asset_kind)
        svc.build_station_rows([{"ticker": "0056", "asset_class": T.ASSET_CORE},
                                {"ticker": "0050", "asset_class": T.ASSET_CORE}],
                               vix=18, metrics_fn=_count)
        assert _calls["n"] == 2

    def test_lights_and_verdicts_unchanged(self):
        """判燈欄位不因為多帶序列而改變（本塊只搬運,不動判定）。"""
        _r = self._etf_row(60)
        assert _r["健檢"] in ("🔴", "🟡", "🟢", "⚪")
        _r2 = svc.build_station_rows(
            [{"ticker": "0056", "name": "高股息", "asset_class": T.ASSET_CORE}],
            vix=18, metrics_fn=self._etf_metrics(60))[0]
        for _k in ("健檢", "235 燈號", "加碼金", "3-3-3", "建議動作"):
            assert _r[_k] == _r2[_k]
