"""💰 存股戰情室 L3：build_station_rows 組表（依賴注入,離線）。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from shared import dividend_station_thresholds as T
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


def test_build_rows_stock_kind_not_applicable():
    """個股列：種類=個股、3-3-3=—、D 標個股不適用（不硬套 ETF 規則,§1）。"""
    def _stock_metrics(ticker, asset_kind="stock"):
        return {"weekly_close": _wk(), "sharpe": 1.0, "total_return_1y_pct": 20,
                "annual_yield_pct": 2, "inception_years": 10, "premium_pct": 1.9,
                "ann_return_3y_pct": 15, "cum_return_3y_pct": None,
                "peer_ranks": {m: 0.1 for m in T.PEER_WINDOWS_MONTHS}}
    holdings = [{"ticker": "2330", "name": "台積電", "asset_class": T.ASSET_SATELLITE,
                 "asset_kind": T.KIND_STOCK}]
    r = svc.build_station_rows(holdings, vix=18, metrics_fn=_stock_metrics)[0]
    assert r["種類"] == "個股"
    assert r["3-3-3"] == "—"                       # 個股不適用,非 ✅/❌/❔
    assert "個股不適用" in r["_detail"]["健檢D"]   # 即使 premium=1.9 也不判 🟡


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
    nav = pd.DataFrame({"折溢價率(%)": [0.3, 0.5]})

    seen = {}
    fake = types.ModuleType("src.data.etf.etf_fetch")
    def _cap_price(t, period="5y"):
        seen["price"] = t
        return px
    fake.fetch_etf_price = _cap_price
    fake.fetch_etf_dividends = lambda t: divs
    fake.fetch_etf_nav_history = lambda t, *a, **k: nav
    monkeypatch.setitem(sys.modules, "src.data.etf.etf_fetch", fake)

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


def test_fetch_metrics_otc_twoo_fallback(monkeypatch):
    """稽核 MED：上櫃股 .TW 抓空 → 自動試 .TWO（否則 OTC 存股整檔 error）。"""
    import sys
    import types
    idx = pd.bdate_range("2020-01-02", periods=900)
    px = pd.DataFrame({"Close": pd.Series(np.linspace(20, 40, len(idx)), index=idx)})
    seen = []
    def _price(t, period="5y"):
        seen.append(t)
        return px if t.endswith(".TWO") else pd.DataFrame()   # .TW 空, .TWO 有
    fake = types.ModuleType("src.data.etf.etf_fetch")
    fake.fetch_etf_price = _price
    fake.fetch_etf_dividends = lambda t: pd.Series(dtype=float)
    monkeypatch.setitem(sys.modules, "src.data.etf.etf_fetch", fake)
    m = svc.fetch_metrics("5314", asset_kind=T.KIND_STOCK)
    assert "5314.TW" in seen and "5314.TWO" in seen          # 先 .TW 再 .TWO
    assert len(m["weekly_close"]) > 20


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
    assert T.classify_asset_kind("00980A.TW") == T.KIND_ETF      # 帶字母後綴仍 ETF
    assert T.classify_asset_kind("00878") == T.KIND_ETF
    assert T.classify_asset_kind("2330") == T.KIND_STOCK         # 4 碼個股
    assert T.classify_asset_kind("6239.TWO") == T.KIND_STOCK     # 上櫃 4 碼個股
    assert T.classify_asset_kind("BND") == T.KIND_ETF            # 非台股 → 預設 ETF
    assert T.classify_asset_kind("") == T.KIND_ETF               # 空 → 預設,不炸


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


def test_summary_prompt_includes_switch_and_regime():
    d = svc.build_station_digest(_switch_rows())
    adv = svc.build_switch_advice(_switch_rows(),
                                  {"loaded": True, "defense": True, "regime": "bear",
                                   "posture_label": "🔴 防禦"},
                                  [{"代碼": "2412", "名稱": "中華電", "綜合分": 88}])
    p = svc.build_summary_prompt(d, switch=adv)
    assert "換股建議" in p and "bear" in p
    assert "00980D" in p and "2412" in p          # 換出/換入都入 prompt
    assert "換入從嚴" in p                          # 轉守攻守指引


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
