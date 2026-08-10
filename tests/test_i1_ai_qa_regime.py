# -*- coding: utf-8 -*-
"""I1 ①：AI 問答的個股評分不得再用捏造的 regime。

修掉的原始碼（`src/services/ai_qa_service.py`）::

    def _regime() -> str:
        try:
            from src.services.macro_state_locker import load_macro_state, normalize_regime
            return normalize_regime((load_macro_state() or {}).get("market_regime"))
        except Exception:
            return "neutral"
    ...
    res = score_single_stock(df=df, ..., regime=_regime(), revenue_df=rev_df)

`macro_state.json` 不存在時 `normalize_regime(None)` 回 ``"neutral"``、`except` 也回
``"neutral"`` ⇒ **兩條路都把「不知道」講成「判斷為震盪」**，然後直接餵給
`score_single_stock` 決定 `WEIGHT_TABLES` —— 使用者在對話裡拿到一個看起來完全正常的
分數與等級。H1 已在 🏆 個股組合修掉同型的最後一處，這裡是**另一個消費端**。

本檔的測試分五層，**除了 E 之外全是行為斷言**（建構輸入 → 呼叫函式 → 驗結果）：

  A. `_macro_state()` 的來源優先序與失敗降級（不猜 regime）。
  B. `get_stock_score`：未評估 → 整份拒絕、**且在 fetch 之前就 return**、
     **不夾帶任何子分數**；可評估 → 把仲裁出來的真 regime 傳下去並回戳記。
  C. `get_market_state`：與評分吃**同一份**契約（同一段對話不得出現兩個 regime）。
  D. `get_risk_plan`：**不**因總經未評估而拒絕 —— 附一條對 `RiskController` 的
     行為斷言證明 `position_size()` 真的不吃 regime（哪天它開始吃，這條會紅）。
  E. 錯誤訊息本身：與 H1 的表格版共用 `reason`（SSOT），但措辭必須是對話版。

⚠️ 本檔 docstring 刻意保留 `return "neutral"` 等字面 —— 若有人把上面的行為斷言
   退化成字串掃描，這些誘餌會讓它自我引爆。
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.services.ai_qa_service as QA  # noqa: E402
from shared.scoring_regime_gate import resolve_scoring_regime  # noqa: E402


# ══════════════════════════════════════════════════════════════
# 測資 / 假物
# ══════════════════════════════════════════════════════════════
def _loaded(regime: str = "bull") -> dict:
    """一份「已評估」的 canonical 總經契約（欄位對齊 `get_macro_state()` 回傳）。"""
    return {"regime": regime, "light": "🟢", "source": "test-arbiter",
            "trend_regime": "bull", "health": 62.0, "defense": False,
            "exposure_limit_pct": 70, "traffic_light": "🟢 進攻", "is_loaded": True}


def _unloaded() -> dict:
    """冷啟動：紅綠燈沒算、macro_state.json 也沒有 —— 本次要修的主線情境。"""
    return {"regime": "unknown", "light": "⬜", "source": "unloaded",
            "trend_regime": None, "health": None, "defense": False,
            "exposure_limit_pct": None, "traffic_light": None, "is_loaded": False}


class _MacroSpy:
    """可控的 `_macro_state`；同時記錄呼叫次數（E2 教訓：patch 失效也要看得出來）。"""

    def __init__(self, state: dict):
        self.state = state
        self.calls = 0

    def __call__(self) -> dict:
        self.calls += 1
        return self.state


@pytest.fixture
def macro(monkeypatch):
    spy = _MacroSpy(_unloaded())
    monkeypatch.setattr(QA, "_macro_state", spy)
    return spy


def _stub_module(monkeypatch, name: str, **attrs) -> types.ModuleType:
    """把 `sys.modules[name]` 換成假模組（monkeypatch 會自動還原）。

    用途：production 的 `from src.data.core import StockDataLoader` 是**函式內**
    lazy import，換掉 sys.modules 就能在「完全不 import 真 L1」的前提下觀察它有沒有
    被呼叫 —— 也順便保證這個測試檔絕不會打到網路。
    """
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, name, mod)
    return mod


def _explode_data_layer(monkeypatch) -> dict:
    """L1/L2 一被碰就炸 —— 用來證明「拒絕評分時根本沒去抓資料」。"""
    hit = {"n": 0}

    def _loader(*_a, **_k):
        hit["n"] += 1
        raise AssertionError(
            "regime 不可用時仍建立了 StockDataLoader —— 應在 fetch 之前就 return")

    def _score(*_a, **_k):
        hit["n"] += 1
        raise AssertionError("regime 不可用時仍呼叫了 score_single_stock")

    _stub_module(monkeypatch, "src.data.core", StockDataLoader=_loader)
    _stub_module(monkeypatch, "src.compute.scoring", score_single_stock=_score)
    return hit


def _fake_price_df():
    import pandas as pd
    return pd.DataFrame({
        "date": pd.date_range("2026-01-02", periods=6, freq="D"),
        "close": [10.0, 10.5, 11.0, 10.8, 11.4, 11.9],
    })


def _capture_scoring(monkeypatch) -> dict:
    """可用 regime 時的假 L1/L2：記下 `score_single_stock` 收到的 kwargs。"""
    cap: dict = {"kwargs": None}
    _df = _fake_price_df()

    class _Loader:
        def get_combined_data(self, _sid, days=400):
            return _df, None, "假名"

        def get_monthly_revenue(self, _sid):
            return None, None

    def _score(**kw):
        cap["kwargs"] = kw
        return {"stock_id": kw.get("stock_id"), "stock_name": kw.get("stock_name"),
                "trend": 80, "momentum": 70, "chip": 60, "volume": 55, "risk": 50,
                "total": 71.2, "grade": "B", "regime": kw.get("regime")}

    _stub_module(monkeypatch, "src.data.core", StockDataLoader=_Loader)
    _stub_module(monkeypatch, "src.compute.scoring", score_single_stock=_score)
    return cap


def _capture_risk(monkeypatch) -> dict:
    """假 L1/L2：記下 `RiskController(...)` 收到的 kwargs。"""
    cap: dict = {"kwargs": None}
    _df = _fake_price_df()

    class _Loader:
        def get_combined_data(self, _sid, days=120):
            return _df, None, "假名"

    class _RC:
        def __init__(self, **kw):
            cap["kwargs"] = kw

        def position_size(self, price):
            return {"lots": 10, "allocated": 100_000.0, "shares": 10_000,
                    "actual_cost": 10_000 * price}

    _stub_module(monkeypatch, "src.data.core", StockDataLoader=_Loader)
    _stub_module(monkeypatch, "src.compute.scoring",
                 calc_atr_stop=lambda _df_, entry_price: {
                     "stop_loss": entry_price * 0.92, "atr": 0.8, "stop_pct": -8.0})
    _stub_module(monkeypatch, "src.compute.risk", RiskController=_RC)
    return cap


# ══════════════════════════════════════════════════════════════
# A. `_macro_state()` —— 來源優先序 + 失敗降級
# ══════════════════════════════════════════════════════════════
class TestMacroStateSource:

    def test_prefers_the_c1_arbitration_point(self, monkeypatch):
        """有 Streamlit session 時走 C1 唯一仲裁點（會併入本次 session 的紅綠燈）。"""
        calls = {"alloc": 0, "locker": 0}

        def _alloc_fn():
            calls["alloc"] += 1
            return _loaded("bear")

        def _locker_fn():
            calls["locker"] += 1
            return _loaded("bull")     # 故意不同：拿到這個就代表優先序錯了

        _stub_module(monkeypatch, "src.services.allocation_service",
                     get_macro_regime=_alloc_fn)
        _stub_module(monkeypatch, "src.services.macro_state_locker",
                     get_macro_state=_locker_fn)
        out = QA._macro_state()
        assert calls == {"alloc": 1, "locker": 0}, calls
        assert out["regime"] == "bear"

    def test_falls_back_to_pure_locker_without_streamlit_runtime(self, monkeypatch):
        """無 session context（離線 CLI / 測試）→ 退回**同一支**仲裁函式，只少了 warroom。"""
        calls = {"alloc": 0, "locker": 0}

        def _alloc_fn():
            calls["alloc"] += 1
            raise RuntimeError("missing ScriptRunContext")

        def _locker_fn():
            calls["locker"] += 1
            return _loaded("neutral")

        _stub_module(monkeypatch, "src.services.allocation_service",
                     get_macro_regime=_alloc_fn)
        _stub_module(monkeypatch, "src.services.macro_state_locker",
                     get_macro_state=_locker_fn)
        out = QA._macro_state()
        assert calls == {"alloc": 1, "locker": 1}, calls
        assert out["regime"] == "neutral"

    def test_both_sources_dead_returns_empty_and_gate_refuses(self, monkeypatch):
        """兩條都失敗 → `{}`，**不猜一個 regime**；gate 據此拒絕評分（§1）。"""
        def _boom(*_a, **_k):
            raise RuntimeError("boom")

        _stub_module(monkeypatch, "src.services.allocation_service",
                     get_macro_regime=_boom)
        _stub_module(monkeypatch, "src.services.macro_state_locker",
                     get_macro_state=_boom)
        assert QA._macro_state() == {}
        assert QA._scoring_regime().usable is False
        assert QA._scoring_regime().regime is None


# ══════════════════════════════════════════════════════════════
# B. get_stock_score
# ══════════════════════════════════════════════════════════════
class TestStockScoreTool:

    def test_refuses_when_macro_unevaluated(self, macro, monkeypatch):
        hit = _explode_data_layer(monkeypatch)
        out = QA._tool_get_stock_score("2330")
        assert macro.calls >= 1, "mock 沒被呼叫到 —— 這條測試等於沒驗"
        assert out["ok"] is False
        assert "未評估" in out["error"], out["error"]
        assert hit["n"] == 0, "拒絕評分卻仍去打了資料源"

    def test_refusal_carries_no_numbers_at_all(self, macro, monkeypatch):
        """**設計決定的核心斷言**：拒絕時不得夾帶 data。

        `trend/momentum/chip/volume/risk` 不吃 regime，技術上可以「回子分數、不回總分」
        —— 表格情境這樣做是對的（空白格就是空白格）。但這裡下游是 LLM：六因子加權表
        就是「把這些子分數合成一個數字」的規則，而 `SYSTEM_INSTRUCTION` 第 3 條又要求
        模型開頭先下方向判斷 ⇒ 給它子分數等於邀請它自己平均，那是**悄悄選了等權重**，
        且包在散文裡使用者無從稽核。故整份拒絕。
        """
        _explode_data_layer(monkeypatch)
        out = QA._tool_get_stock_score("2330")
        assert macro.calls >= 1
        assert "data" not in out, f"拒絕時仍夾帶資料：{out.get('data')!r}"
        # 精確釘死回傳形狀：只有 ok/error 兩個 key，沒有任何可被 LLM 加總的數字。
        # （刻意不做「'risk' 不在字串裡」這種掃描 —— error 文案本來就提到
        #   `get_risk_plan`，那種寫法會變成照抄實作字面的假守衛。）
        assert set(out) == {"ok", "error"}, out

    @pytest.mark.parametrize("regime", ["bull", "neutral", "bear"])
    def test_passes_the_arbitrated_regime_through(self, macro, monkeypatch, regime):
        macro.state = _loaded(regime)
        cap = _capture_scoring(monkeypatch)
        out = QA._tool_get_stock_score("2330")
        assert macro.calls >= 1, "mock 沒被呼叫到"
        assert cap["kwargs"] is not None, "score_single_stock 沒被呼叫 —— 斷言等於沒驗"
        assert cap["kwargs"]["regime"] == regime
        assert out["ok"] is True
        assert out["data"]["regime"] == regime, "總分是 regime 的函數，回傳必須帶戳記（§2.2）"
        assert out["data"]["total"] == 71.2

    def test_caution_regime_is_refused_not_silently_neutral(self, macro, monkeypatch):
        """`caution` 是 canonical regime，但 `WEIGHT_TABLES` 沒這個 key（H1 的潛伏坑）。"""
        macro.state = _loaded("caution")
        hit = _explode_data_layer(monkeypatch)
        out = QA._tool_get_stock_score("2330")
        assert out["ok"] is False
        assert "caution" in out["error"] and "WEIGHT_TABLES" in out["error"]
        assert hit["n"] == 0


# ══════════════════════════════════════════════════════════════
# C. get_market_state —— 一段對話只能有一個 regime
# ══════════════════════════════════════════════════════════════
class TestMarketStateTool:

    def test_shares_one_regime_with_scoring(self, macro, monkeypatch):
        """報告 regime 的工具與消費 regime 的工具必須同源。

        修前：`get_market_state` 讀 `macro_state.json`、評分讀另一條路 —— 快照過期或
        「只有 warroom 有結論」時，模型會在同一段對話裡同時拿到兩個多空結論。
        """
        macro.state = _loaded("bear")
        _stub_module(monkeypatch, "src.services.macro_state_locker",
                     load_macro_state=lambda *_a, **_k: {})
        ms = QA._tool_get_market_state()
        assert macro.calls >= 1, "mock 沒被呼叫到"
        assert ms["ok"] is True
        assert ms["data"]["regime"] == "bear"
        assert QA._scoring_regime().regime == "bear"

    def test_unevaluated_is_fail_loud(self, macro, monkeypatch):
        _stub_module(monkeypatch, "src.services.macro_state_locker",
                     load_macro_state=lambda *_a, **_k: {})
        out = QA._tool_get_market_state()
        assert macro.calls >= 1
        assert out["ok"] is False
        assert "未評估" in out["error"]
        assert "data" not in out

    def test_trend_regime_is_labelled_as_input_not_conclusion(self, macro, monkeypatch):
        """`trend_regime` 是趨勢面**輸入**；欄名必須讓模型不可能把它當第二個 regime。"""
        macro.state = _loaded("neutral")
        _stub_module(monkeypatch, "src.services.macro_state_locker",
                     load_macro_state=lambda *_a, **_k: {})
        _data = QA._tool_get_market_state()["data"]
        _trend_keys = [k for k in _data if "trend_regime" in k]
        assert _trend_keys, _data
        assert all(k != "trend_regime" for k in _trend_keys), (
            f"欄名太素，模型會把它當結論：{_trend_keys}")


# ══════════════════════════════════════════════════════════════
# D. get_risk_plan —— 不過度拒絕，但也不捏造
# ══════════════════════════════════════════════════════════════
class TestRiskPlanTool:

    def test_position_size_is_regime_independent(self):
        """`RiskController.position_size()` 不吃 regime —— 這是 D 組不拒絕的前提。

        `position_size` 只用 `self.max_single_weight`（= `MAX_POSITION_PER_STOCK`）；
        regime 只影響 `target_exposure` / `max_stock_budget`，而 `get_risk_plan`
        沒有呼叫那兩個。**哪天 `position_size` 開始吃 regime，這條就會紅**，
        屆時 `_tool_get_risk_plan` 必須改成「未評估 → 不輸出倉位」。
        """
        from src.compute.risk import RiskController
        from src.compute.risk.risk_control import portfolio_exposure

        _kw = dict(portfolio_value=1_000_000)
        _bull = RiskController(regime="bull", **_kw).position_size(price=100.0)
        _bear = RiskController(regime="bear", **_kw).position_size(price=100.0)
        _none = RiskController(**_kw).position_size(price=100.0)
        _junk = RiskController(regime="unknown", **_kw).position_size(price=100.0)
        assert _bull == _bear == _none == _junk, (
            f"position_size 已經開始吃 regime 了：bull={_bull} / bear={_bear}")
        # 非空自證：regime 在這個 class 的**別處**確實有作用，測試不是恆真。
        assert portfolio_exposure("bull") != portfolio_exposure("bear")

    def test_passes_real_regime_when_known(self, macro, monkeypatch):
        macro.state = _loaded("bull")
        cap = _capture_risk(monkeypatch)
        out = QA._tool_get_risk_plan("2330")
        assert macro.calls >= 1, "mock 沒被呼叫到"
        assert cap["kwargs"] is not None, "RiskController 沒被建立 —— 斷言等於沒驗"
        assert cap["kwargs"].get("regime") == "bull"
        assert out["ok"] is True and out["data"]["position_lot"] == 10

    def test_omits_regime_when_unknown_but_still_answers(self, macro, monkeypatch):
        """未評估：不傳捏造的 regime，但**照樣**回停損/ATR/倉位（它們不是 regime 的函數）。"""
        cap = _capture_risk(monkeypatch)
        out = QA._tool_get_risk_plan("2330")
        assert macro.calls >= 1
        assert cap["kwargs"] is not None
        assert "regime" not in cap["kwargs"], (
            f"未評估卻仍傳了 regime={cap['kwargs'].get('regime')!r}")
        assert out["ok"] is True, "停損/ATR 不吃 regime，不該被總經未評估連坐"
        assert out["data"]["stop_loss"] is not None


# ══════════════════════════════════════════════════════════════
# E. 使用者（與模型）實際讀到的那段話
# ══════════════════════════════════════════════════════════════
class TestBlockedMessage:

    @pytest.mark.parametrize("state", [
        None, {}, "bull", {"is_loaded": False},
        {"is_loaded": True, "regime": "unknown"},
        {"is_loaded": True, "regime": ""},
        {"is_loaded": True, "regime": "caution"},
    ])
    def test_message_carries_the_gate_reason(self, state):
        """判定理由是 SSOT（`ScoringRegimeDecision.reason`），對話版只換包裝不換內容。"""
        dec = resolve_scoring_regime(state)
        assert dec.usable is False
        msg = QA._regime_blocked_error(dec)
        assert dec.reason and dec.reason in msg, (dec.reason, msg)

    def test_message_forbids_the_model_from_synthesising_a_score(self):
        msg = QA._regime_blocked_error(resolve_scoring_regime({"is_loaded": False}))
        assert "不得" in msg and "推估" in msg, msg
        assert "不是個股資料抓取失敗" in msg
        assert "一鍵更新全部數據" in msg
        assert "get_financial_health" in msg, "沒講什麼還能用，模型會宣告整體失敗"

    def test_chat_wording_differs_from_the_table_wording(self):
        """與 H1 表格版共用判定、**不共用措辭** —— 對話裡叫使用者去看一張表是錯的指引。"""
        dec = resolve_scoring_regime({"is_loaded": False})
        chat, table = QA._regime_blocked_error(dec), dec.notice()
        assert dec.reason in chat and dec.reason in table
        assert chat != table
        assert "多因子評分排行" not in chat, chat

    def test_blocked_reason_actually_reaches_the_llm_prompt(self):
        """整段串起來：拒絕理由必須進 Gemini payload，且其他真實資料照常討論。"""
        seen: dict = {}

        def _http(payload):
            seen["payload"] = payload
            return {"candidates": [{"content": {"parts": [{"text": "已如實說明"}]}}]}

        dec = resolve_scoring_regime({"is_loaded": False})
        bundle = {
            "get_stock_score": {"ok": False, "error": QA._regime_blocked_error(dec)},
            "get_financial_health": {"ok": True, "data": {"毛利率(%)": 55},
                                     "provenance": {"source": "FinMind 季報"}},
        }
        p = QA.discuss("stock", bundle, mode="lite", gemini_http=_http)
        assert "payload" in seen, "LLM 沒被呼叫 —— 還有真實資料時不該整段放棄"
        assert p.ok is True
        _txt = str(seen["payload"])
        assert dec.reason in _txt
        assert "不得" in _txt


if __name__ == "__main__":   # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
