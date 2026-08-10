# -*- coding: utf-8 -*-
"""H1 ①：🏆 個股組合批次評分不得再捏造 regime。

修掉的原始碼（`src/ui/tabs/stock_grp_sections/section_batch_fetcher.py`）::

    _grp_regime = (st.session_state.get('macro_state', {}) or {}).get('regime') or 'neutral'
    sf = score_single_stock(df4, sid4, _n4_use, regime=_grp_regime)

`macro_state` 只有開過 🌍 總經頁才會被寫入。冷啟動直接點 🏆 個股組合時，那個
`or 'neutral'` 會讓**全批股票用「震盪」權重被評分**，畫面卻印出一組看起來完全正常
的分數與排名 —— 使用者無從得知這是在「總經沒有結論」的前提下算出來的。

本檔的測試分四層，**前三層都是行為斷言**（建構輸入 → 呼叫函式 → 驗結果）：

  A. `shared.scoring_regime_gate.resolve_scoring_regime` 的完整三態行為。
  B. **這件事為什麼要緊** —— 直接呼叫 `scoring_engine.stock_score`，證明
     bull/neutral/bear 權重會讓兩檔股票的**排名對調**（不是小數點後的差異），
     並釘住「WEIGHT_TABLES 沒有的 regime 會靜默拿到 neutral 權重」這個
     `.get(regime, WEIGHT_TABLES['neutral'])` 的既有行為 —— 那正是 gate 存在的理由。
  C. production wiring 的 **AST** 守衛（不掃字串、不看註解／docstring）：
     `score_single_stock(regime=...)` 的實參必須是 `_regime_dec.regime` 這種
     Attribute，且全檔不得再出現「以 'neutral' 當 or-fallback」或讀 `'macro_state'`。
  D. 使用者看得到的那句警示（`notice()`）必須講清楚四件事。

⚠️ 本檔 docstring 刻意寫滿 `or 'neutral'`、`macro_state` 等字面 —— 若哪天有人把 C
   退化成字串掃描，這些誘餌會讓它自我引爆。
"""
from __future__ import annotations

import ast
import math
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared.regime_arbiter import UNLOADED_VERDICT
from shared.scoring_regime_gate import (
    UNKNOWN_REGIME,
    ScoringRegimeDecision,
    resolve_scoring_regime,
    weight_table_regimes,
)
from src.compute.scoring.scoring_engine import stock_score
from src.config import WEIGHT_TABLES

_REPO = Path(__file__).resolve().parent.parent
_BATCH = _REPO / "src/ui/tabs/stock_grp_sections/section_batch_fetcher.py"


def _loaded(regime: str) -> dict:
    """一份「已評估」的 canonical 總經契約（欄位對齊 get_macro_state 的回傳）。"""
    return {
        "regime": regime, "light": "🟡", "source": "test",
        "trend_regime": None, "health": 55.0, "defense": False,
        "exposure_limit_pct": 60, "traffic_light": None, "is_loaded": True,
    }


# ══════════════════════════════════════════════════════════════
# A. gate 的三態行為
# ══════════════════════════════════════════════════════════════
class TestGateBehaviour:

    @pytest.mark.parametrize("regime", ["bull", "neutral", "bear"])
    def test_loaded_canonical_regime_is_usable(self, regime):
        dec = resolve_scoring_regime(_loaded(regime))
        assert dec.usable is True
        assert dec.regime == regime
        assert dec.reason == ""
        assert dec.notice() == "", "可評分時不該冒出任何警示句"

    def test_not_loaded_refuses(self):
        """冷啟動（沒開過總經頁）—— 本次要修的主線情境。"""
        dec = resolve_scoring_regime({"regime": "unknown", "is_loaded": False})
        assert dec.usable is False
        assert dec.regime is None, "拒絕評分時 regime 必須是 None，不得退回任何預設"
        assert "未評估" in dec.reason

    def test_unloaded_verdict_from_arbiter_is_refused(self):
        """直接餵 C1 仲裁點的 UNLOADED_VERDICT 欄位 —— 兩邊字面必須對得上。"""
        assert UNLOADED_VERDICT.regime == UNKNOWN_REGIME, (
            "regime_arbiter 的未評估字面若改了，本 gate 的比對就會失效")
        dec = resolve_scoring_regime({
            "regime": UNLOADED_VERDICT.regime, "is_loaded": False})
        assert dec.usable is False

    def test_loaded_but_regime_unknown_still_refuses(self):
        """`is_loaded=True` 但契約自己說 unknown —— 仍然拒絕（不吃 is_loaded 的表面）。"""
        dec = resolve_scoring_regime(_loaded(UNKNOWN_REGIME))
        assert dec.usable is False
        assert "unknown" in dec.reason

    def test_empty_regime_refuses(self):
        dec = resolve_scoring_regime(_loaded(""))
        assert dec.usable is False

    @pytest.mark.parametrize("bad", [None, "bull", 42, [], ("bull",)])
    def test_non_dict_refuses(self, bad):
        """取數失敗（例如 get_macro_regime 被改壞）→ 拒絕，不是猜一個。"""
        dec = resolve_scoring_regime(bad)
        assert dec.usable is False
        assert dec.regime is None

    @pytest.mark.parametrize("raw,want", [
        (" Bull ", "bull"), ("NEUTRAL", "neutral"), ("Bear", "bear"),
    ])
    def test_case_and_whitespace_normalised(self, raw, want):
        assert resolve_scoring_regime(_loaded(raw)).regime == want

    def test_caution_is_refused_not_silently_neutral(self):
        """`caution` 是 canonical regime 之一，但 WEIGHT_TABLES **沒有**這個 key。

        現況（量測日 2026-08-10）它打不到這裡（arbiter 只回 bull/neutral/bear/
        unknown、macro_state.json 只有 多頭/震盪/空頭/系統異常），所以這是**潛伏坑**
        不是活 bug。但一旦哪天有 producer 開始回 caution，`.get(regime, neutral)`
        會讓一個「轉守」的市場被**震盪權重**評分且毫無跡象 —— gate 必須擋下來。
        """
        assert "caution" not in WEIGHT_TABLES, (
            "WEIGHT_TABLES 多了 caution 這個 key —— 本測試的前提改變了，"
            "請重新確認 gate 是否還需要擋它")
        dec = resolve_scoring_regime(_loaded("caution"))
        assert dec.usable is False
        assert "caution" in dec.reason
        assert "WEIGHT_TABLES" in dec.reason

    def test_weight_table_regimes_matches_config(self):
        assert set(weight_table_regimes()) == set(WEIGHT_TABLES)

    def test_decision_is_frozen(self):
        dec = resolve_scoring_regime(_loaded("bull"))
        with pytest.raises(Exception):
            dec.regime = "bear"   # type: ignore[misc]

    def test_unusable_when_weight_tables_unreadable(self, monkeypatch):
        """讀不到權重表 → 拒絕評分（**不是**退回一組硬編碼 key 就放行）。"""
        import shared.scoring_regime_gate as _mod
        _calls = []

        def _fake_regimes():
            _calls.append(1)
            return ()

        monkeypatch.setattr(_mod, "weight_table_regimes", _fake_regimes)
        dec = _mod.resolve_scoring_regime(_loaded("bull"))
        assert _calls, "mock 沒有被呼叫到 —— 這條測試等於沒驗（E2 的失效 patch 教訓）"
        assert dec.usable is False
        assert "WEIGHT_TABLES" in dec.reason


# ══════════════════════════════════════════════════════════════
# B. 這件事為什麼要緊 —— 直接對真的評分函式做算術
# ══════════════════════════════════════════════════════════════
#: 動能／趨勢強、但風險與基本面差的「衝勁型」個股。
_MOMENTUM_STOCK = dict(trend=90.0, momentum=90.0, chip=50.0,
                       volume_score=50.0, risk_score=20.0, fundamental_score=20.0)
#: 趨勢弱、但風控與基本面紮實的「防禦型」個股。
_DEFENSIVE_STOCK = dict(trend=40.0, momentum=40.0, chip=50.0,
                        volume_score=50.0, risk_score=95.0, fundamental_score=95.0)


def _score(stock: dict, regime: str) -> float:
    return stock_score(
        stock["trend"], stock["momentum"], stock["chip"],
        stock["volume_score"], stock["risk_score"],
        stock["fundamental_score"], regime=regime)


class TestWhyItMatters:

    @pytest.mark.parametrize("stock,regime,expected", [
        (_MOMENTUM_STOCK,  "bull",    69.0),
        (_MOMENTUM_STOCK,  "neutral", 62.0),
        (_MOMENTUM_STOCK,  "bear",    46.5),
        (_DEFENSIVE_STOCK, "bull",    49.0),
        (_DEFENSIVE_STOCK, "neutral", 54.5),
        (_DEFENSIVE_STOCK, "bear",    67.75),
    ])
    def test_weights_change_the_number_a_lot(self, stock, regime, expected):
        """手算對帳（§4.3 重算對帳）：權重表逐項相乘的結果。

        例（衝勁型 × bear）：
            90×0.15 + 90×0.10 + 50×0.15 + 50×0.15 + 20×0.25 + 20×0.20 = 46.5
        """
        got = _score(stock, regime)
        assert math.isclose(got, expected, abs_tol=0.06), (
            f"{regime} 權重下的總分應為 {expected}，實得 {got}")

    def test_ranking_flips_between_bull_and_bear(self):
        """**排名會對調** —— 這不是化妝品等級的差異。

        捏造 neutral 的實質後果就是：使用者拿到的「最強檔」可能根本不是
        當前市場狀態下該排第一的那一檔。
        """
        a_bull, b_bull = _score(_MOMENTUM_STOCK, "bull"), _score(_DEFENSIVE_STOCK, "bull")
        a_bear, b_bear = _score(_MOMENTUM_STOCK, "bear"), _score(_DEFENSIVE_STOCK, "bear")
        assert a_bull > b_bull, "多頭權重下衝勁型應勝出"
        assert b_bear > a_bear, "空頭權重下防禦型應勝出"

    def test_unknown_regime_silently_falls_back_to_neutral(self):
        """釘住 `stock_score` 既有的靜默 fallback —— gate 存在的直接理由。

        `stock_score` 內是 `WEIGHT_TABLES.get(regime, WEIGHT_TABLES['neutral'])`，
        所以光是「把 'unknown' 傳下去」**完全不夠**：它會被悄悄換成震盪權重，
        而回傳 dict 裡的 `regime` 欄位還會誠實寫著 'unknown' —— 一個看起來有標示、
        實際上已經造假的組合。必須在 caller 端擋住。
        """
        assert UNKNOWN_REGIME not in WEIGHT_TABLES
        assert math.isclose(_score(_MOMENTUM_STOCK, UNKNOWN_REGIME),
                            _score(_MOMENTUM_STOCK, "neutral"), abs_tol=1e-9)

    def test_caution_regime_silently_falls_back_to_neutral(self):
        """同上，但對象是**合法的** canonical regime `caution`（潛伏坑）。"""
        assert math.isclose(_score(_DEFENSIVE_STOCK, "caution"),
                            _score(_DEFENSIVE_STOCK, "neutral"), abs_tol=1e-9)

    def test_weight_rows_sum_to_one(self):
        """§4.2 不變量：三態權重各自和 = 1（config.py import 期也有守衛，這裡再釘一次）。"""
        for _r, _w in WEIGHT_TABLES.items():
            assert math.isclose(sum(_w.values()), 1.0, abs_tol=1e-9), _r


# ══════════════════════════════════════════════════════════════
# C. production wiring 的 AST 守衛
# ══════════════════════════════════════════════════════════════
def _tree():
    src = _BATCH.read_text(encoding="utf-8")
    return ast.parse(src), src


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """所有 docstring 的 Constant 節點 id（模組／類別／函式的第一個 Expr）。"""
    out: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None) or []
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            out.add(id(body[0].value))
    return out


def _score_calls(tree: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "score_single_stock"]


class TestProductionWiring:

    def test_regime_argument_is_not_a_literal(self):
        """`regime=` 的實參不得是字面常數，也不得是 `x or '...'` 這種 fallback。"""
        tree, src = _tree()
        calls = _score_calls(tree)
        assert calls, f"{_BATCH} 找不到 score_single_stock 呼叫 —— 守衛失去對象"
        for call in calls:
            kw = {k.arg: k.value for k in call.keywords}
            assert "regime" in kw, (
                f"沒有傳 regime → 走 score_single_stock 的 default 'neutral'：\n"
                f"{ast.get_source_segment(src, call)}")
            node = kw["regime"]
            assert not isinstance(node, ast.Constant), (
                f"regime 被寫死成字面常數：\n{ast.get_source_segment(src, call)}")
            assert not isinstance(node, ast.BoolOp), (
                f"regime 又出現 `... or '預設'` 形式的捏造：\n"
                f"{ast.get_source_segment(src, call)}")
            assert isinstance(node, ast.Attribute) and node.attr == "regime", (
                f"regime 應取自 gate 的判定結果（`<decision>.regime`），實得：\n"
                f"{ast.get_source_segment(src, node)}")

    def test_no_or_neutral_fallback_anywhere(self):
        """全檔不得有任何 `... or 'neutral'`（含其他 regime 字面）。"""
        tree, src = _tree()
        _bad = {"neutral", "bull", "bear", "caution"}
        for node in ast.walk(tree):
            if not isinstance(node, ast.BoolOp) or not isinstance(node.op, ast.Or):
                continue
            for value in node.values:
                if isinstance(value, ast.Constant) and value.value in _bad:
                    pytest.fail(
                        "偵測到用 regime 字面當 or-fallback（＝捏造市場判斷）：\n"
                        f"{ast.get_source_segment(src, node)}")

    def test_no_macro_state_session_read(self):
        """不得再直讀 `st.session_state['macro_state']`（C1：一律走唯一仲裁點）。

        docstring 內的字面會被排除；註解本來就不進 AST，所以本檔／原始碼的說明文字
        提到 macro_state 都不會誤觸發。
        """
        tree, src = _tree()
        _docs = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and node.value == "macro_state"
                    and id(node) not in _docs):
                pytest.fail(
                    "仍有 'macro_state' 字面（應改吃 allocation_service."
                    "get_macro_regime()）：\n"
                    + str(ast.get_source_segment(src, node)))

    def test_imports_the_gate(self):
        tree, _src = _tree()
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert "shared.scoring_regime_gate" in mods, (
            "section_batch_fetcher 未引用 L0 gate —— regime 判定可能又被寫回 inline")
        assert "src.services.allocation_service" in mods, (
            "未走 C1 唯一仲裁點 get_macro_regime()")

    def test_score_append_is_guarded_by_usable(self):
        """`score_t3.append(...)` 必須落在某個 `.usable` 條件之下。

        這條防的是「gate 引進來了但沒接上」：只要 append 不在 usable 的守衛範圍內，
        未評估時仍會產出分數。
        """
        tree, src = _tree()
        _guarded = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            _uses_usable = any(
                isinstance(sub, ast.Attribute) and sub.attr == "usable"
                for sub in ast.walk(node.test))
            if not _uses_usable:
                continue
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == "append"
                        and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == "score_t3"):
                    _guarded = True
        assert _guarded, (
            "找不到「被 .usable 守著的 score_t3.append」—— "
            "gate 可能只是被 import 進來，實際沒擋住任何東西。\n"
            f"檔案：{_BATCH}")

    def test_score_failure_is_not_silently_swallowed(self):
        """評分例外不得再是 `except Exception: pass`（§1：降級不靜默）。"""
        tree, src = _tree()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                pytest.fail(
                    "仍有 `except ...: pass`（吞掉例外＝畫面與「總經未評估」無法分辨）：\n"
                    + str(ast.get_source_segment(src, node)))


# ══════════════════════════════════════════════════════════════
# D. 使用者實際會讀到的那句話
# ══════════════════════════════════════════════════════════════
class TestUserFacingNotice:

    def test_notice_covers_the_four_things(self):
        notice = resolve_scoring_regime({"is_loaded": False}).notice()
        assert notice
        # 1) 被擋掉的是什麼
        assert "多因子總分" in notice
        # 2) 為什麼
        assert "WEIGHT_TABLES" in notice
        # 3) 不是 K 線抓取失敗（畫面上「⚪ 無法評分」同時服務兩種原因）
        assert "K 線" in notice
        # 4) 救法
        assert "一鍵更新全部數據" in notice

    def test_notice_says_what_still_works(self):
        """不能讓使用者誤以為整個批次分析都廢了 —— 不吃 regime 的那些照常。"""
        notice = resolve_scoring_regime({"is_loaded": False}).notice()
        for kept in ("健康度", "型態"):
            assert kept in notice

    def test_notice_is_empty_when_usable(self):
        assert ScoringRegimeDecision("bull").notice() == ""
