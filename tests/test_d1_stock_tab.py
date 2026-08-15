"""D1 v19.185 — 🔬 個股深度分析分頁全掃後的回歸測試。

為什麼是這些測試
================
個股頁是本輪唯一沒被專門稽核過的分頁。稽核抓到的缺陷全部落在同幾個形狀上：
**綠燈不代表算過 / 幽靈 key / 捏造預設值 / 畫面宣稱的門檻 ≠ 判定式 /
恆不命中的條件 / 量錯對象**。這些形狀有一個共同特徵 ——
**掃字串永遠抓不到**（實作跟畫面文案都「長得很正常」）。

所以本檔的原則是：

1. **能驗行為就驗行為。** 為此把 5 段原本內嵌在 render 裡的判定抽成純函式
   （`build_winning_conditions` / `kline_chip_verdict` / `evaluate_leading_gates`
   / `attach_chip_columns` / `vcp_bollinger_verdicts` / `_surge_pct`），
   測試直接餵輸入、驗輸出。
2. **非驗原始碼不可的（regime 接線需要 Streamlit runtime）用 AST**，
   排除 docstring / 註解，失敗訊息印出**該行原文**，並附「守衛自我驗證」
   （造一個假的違規檔，確認掃描器真的抓得到）——
   否則守衛壞掉時會靜靜地全綠。
3. **不照抄實作字面。** 字面比對只用在「舊的謊言不得復活」這種**負向**檢查
   （例如畫面不得再出現「需全部符合」而判定式其實是 4/5）。

對應修復（詳見各 section 檔內的 D1 v19.185 註解）：
  P0-1 5 處直讀 raw regime + 捏 'neutral' → `get_macro_regime()` 唯一仲裁點
  P0-2 勝利方程式「💎 非357昂貴區」讀幽靈 key `t2_data['val']` → 恆 ✅
  P0-3 勝利方程式「💰 融資安全」缺資料退 0 → 恆 ✅
  P0-4 v4 相對籌碼把「單日」外資廣播成整欄 → 5 日淨買 = 單日 × 5
  P0-5 v4 外本比分母缺股本時用假的 1,000,000 張
  P0-6 v5 財報領先 3 個輸入恆 None + 1 個幽靈 key → 死區（只可能回「一般水準」）
  P0-7 VCP 結論條印的是**布林**的結論（迴圈變數殘留）
  P0-8 K 線籌碼結論的 else 分支：外資 = 0 時說「月線下方」而其實站上月線
  P0-9 財報領先「✅ 龍多確認」判定式是 `>0`，副標卻寫「>股本50%/80%」
"""
from __future__ import annotations

import ast
import linecache
import re
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent


# ══════════════════════════════════════════════════════════════════════
# 共用 AST 工具
# ══════════════════════════════════════════════════════════════════════
def _tree(rel: str) -> ast.Module:
    _p = REPO / rel
    return ast.parse(_p.read_text(encoding="utf-8"), filename=str(_p))


def _line(rel: str, lineno: int) -> str:
    _p = str(REPO / rel)
    linecache.checkcache(_p)
    return linecache.getline(_p, lineno).strip()


def _docstring_ids(tree: ast.Module) -> set[int]:
    """module / class / def 的 docstring 節點 id（註解不進 AST，天然排除）。"""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                out.add(id(body[0].value))
    return out


def _render_strings(tree: ast.Module) -> list[tuple[int, str]]:
    """所有**可能被渲染**的字串常數（含 f-string 的字面片段），排除 docstring。"""
    _skip = _docstring_ids(tree)
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in _skip:
            out.append((node.lineno, node.value))
    return out


def _referenced_names(tree: ast.Module) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.alias):
            out.add(node.name.split(".")[-1])
            if node.asname:
                out.add(node.asname)
    return out


def _keywords_of_call(tree: ast.Module, func_name: str) -> set[str]:
    """找 `func_name(...)` 呼叫用到的關鍵字參數名（跨全檔聯集）。"""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == func_name:
            out.update(k.arg for k in node.keywords if k.arg)
    return out


# ══════════════════════════════════════════════════════════════════════
# 1. SOP 進場檢核：「近 N 交易日漲幅」只能有一個基期
#    （原本檢核②用 iloc[-6]、禁止清單用 iloc[-5]，同一頁兩個數字）
# ══════════════════════════════════════════════════════════════════════
class TestSurgePct:
    @staticmethod
    def _df(vals):
        return pd.DataFrame({"close": [float(v) for v in vals]})

    def test_base_is_n_bars_back(self):
        from src.ui.tabs.stock_sections.section_psy_checklist import _surge_pct
        # 6 根 K，基期 = 第 1 根(100)，現價 110 → +10.0%
        assert _surge_pct(self._df([100, 101, 102, 103, 104, 110])) == pytest.approx(10.0)

    def test_lookback_is_configurable_and_consistent(self):
        from shared.signal_thresholds import SOP_SURGE_LOOKBACK_DAYS
        from src.ui.tabs.stock_sections.section_psy_checklist import _surge_pct
        _n = SOP_SURGE_LOOKBACK_DAYS
        # 建 N+1 根：只有第一根與最後一根不同 → 漲幅完全由基期決定
        _vals = [100.0] + [999.0] * (_n - 1) + [150.0]
        assert _surge_pct(self._df(_vals)) == pytest.approx(50.0)

    def test_insufficient_bars_returns_none_not_zero(self):
        """§1：算不出來要回 None，不可回 0（0% 會被讀成「沒有追高」）。"""
        from shared.signal_thresholds import SOP_SURGE_LOOKBACK_DAYS
        from src.ui.tabs.stock_sections.section_psy_checklist import _surge_pct
        _short = self._df([100.0] * SOP_SURGE_LOOKBACK_DAYS)   # 只有 N 根，差一根
        assert _surge_pct(_short) is None

    def test_zero_base_returns_none(self):
        from src.ui.tabs.stock_sections.section_psy_checklist import _surge_pct
        assert _surge_pct(self._df([0, 1, 2, 3, 4, 5])) is None

    def test_no_column_returns_none(self):
        from src.ui.tabs.stock_sections.section_psy_checklist import _surge_pct
        assert _surge_pct(pd.DataFrame({"open": [1.0] * 10})) is None
        assert _surge_pct(None) is None

    def test_no_leftover_off_by_one_index(self):
        """兩個舊基期（`iloc[-5]` / `iloc[-6]`）都不得再出現在本檔。

        它們是「同一個量、兩份實作」的痕跡；現在只有 `_surge_pct` 一處算。
        """
        _rel = "src/ui/tabs/stock_sections/section_psy_checklist.py"
        _bad = []
        # 掃 Subscript(value=Attribute(attr='iloc'), slice=UnaryOp(-, Constant))
        for node in ast.walk(_tree(_rel)):
            if not (isinstance(node, ast.Subscript)
                    and isinstance(node.value, ast.Attribute)
                    and node.value.attr == "iloc"):
                continue
            _s = node.slice
            if (isinstance(_s, ast.UnaryOp) and isinstance(_s.op, ast.USub)
                    and isinstance(_s.operand, ast.Constant)
                    and _s.operand.value in (5, 6)):
                _bad.append(f"line {node.lineno}: {_line(_rel, node.lineno)!r}")
        assert not _bad, (
            "同一頁又出現寫死的 iloc[-5] / iloc[-6]（近5日漲幅的兩個基期）：\n  "
            + "\n  ".join(_bad))


# ══════════════════════════════════════════════════════════════════════
# 2. 勝利方程式 5 條件：三態 + 幽靈 key / 捏造預設值回歸
# ══════════════════════════════════════════════════════════════════════
def _conds(**over):
    from src.ui.tabs.stock_sections.section_psy_checklist import build_winning_conditions
    _base = dict(regime="bull", macro_loaded=True, margin_yi=1000.0,
                 health=90.0, price=10.0, avg_div=1.0, stop_set=True)
    _base.update(over)
    return build_winning_conditions(**_base)


def _state(conds, keyword):
    _hit = [c for c in conds if keyword in c[0]]
    assert len(_hit) == 1, f"找不到（或找到多個）條件：{keyword} → {[c[0] for c in conds]}"
    return _hit[0][1]


class TestWinningFormula:
    def test_happy_path_all_true(self):
        _c = _conds()
        assert [s for _, s, _n in _c] == [True, True, True, True, True]

    def test_357_expensive_must_be_false(self):
        """💎「非357昂貴區」原本讀 `t2_data['val']`（**全站無寫入點**），
        `'昂貴' not in ''` 恆 True ⇒ 每一檔、任何價位都是 ✅。

        avg_div=1 → 便宜價 14.3 / 合理價 20 / 昂貴價 33.3。
        price=25 落在「昂貴區」→ 這一條必須是 False。
        """
        assert _state(_conds(price=25.0, avg_div=1.0), "357") is False

    def test_357_cheap_is_true(self):
        assert _state(_conds(price=10.0, avg_div=1.0), "357") is True

    def test_357_without_dividend_is_unknown(self):
        """無配息（成長股）→ 357 不適用 ⇒ **未評估**，不是「非昂貴」。"""
        assert _state(_conds(avg_div=0.0), "357") is None
        assert _state(_conds(avg_div=None), "357") is None
        assert _state(_conds(price=0.0), "357") is None

    def test_margin_missing_is_unknown_not_pass(self):
        """💰「融資安全」原本 `cl_data.get('margin', 0)`，
        總經沒載入時 `0 < 2500億` ⇒ 恆 ✅。現在必須是 ⬜。"""
        assert _state(_conds(margin_yi=None), "融資安全") is None

    def test_margin_thresholds_match_ssot(self):
        from shared.signal_thresholds import MARGIN_BALANCE_WARN_THRESHOLD_YI as W
        assert _state(_conds(margin_yi=W - 1), "融資安全") is True
        assert _state(_conds(margin_yi=W), "融資安全") is False       # 邊界不算安全
        assert _state(_conds(margin_yi=W + 1), "融資安全") is False
        # 畫面標籤上的數字必須就是 SSOT 那個數字（不是另外手打一個）
        _label = [c[0] for c in _conds() if "融資安全" in c[0]][0]
        assert f"{W:.0f}" in _label

    def test_macro_unloaded_is_unknown_not_false(self):
        """總經未評估 ≠ 判定為非多頭。"""
        assert _state(_conds(macro_loaded=False), "大盤") is None
        assert _state(_conds(macro_loaded=False, regime="bull"), "大盤") is None

    def test_macro_regime_mapping(self):
        assert _state(_conds(regime="bull"), "大盤") is True
        for _r in ("neutral", "caution", "bear", "unknown"):
            assert _state(_conds(regime=_r), "大盤") is False, _r

    def test_health_boundary_matches_label(self):
        from shared.signal_thresholds import WINNING_FORMULA_HEALTH_MIN as H
        assert _state(_conds(health=H), "健康度") is True        # ≥ 是含等於
        assert _state(_conds(health=H - 0.1), "健康度") is False
        assert _state(_conds(health=None), "健康度") is None
        _label = [c[0] for c in _conds() if "健康度" in c[0]][0]
        assert f"{H:.0f}" in _label, f"標籤沒印 SSOT 門檻：{_label}"

    def test_unknown_never_counted_as_pass(self):
        """三態的重點：未評估既不加分也不當否定。"""
        _c = _conds(macro_loaded=False, margin_yi=None)
        _passed = sum(1 for _, s, _n in _c if s is True)
        _unknown = sum(1 for _, s, _n in _c if s is None)
        assert (_passed, _unknown) == (3, 2)

    def test_gate_and_title_agree(self):
        """卡片標題不得再宣稱「需全部符合」而判定式其實是 4/5。"""
        from shared.signal_thresholds import WINNING_FORMULA_MIN_PASS
        assert 1 <= WINNING_FORMULA_MIN_PASS <= 5
        _rel = "src/ui/tabs/stock_sections/section_psy_checklist.py"
        _t = _tree(_rel)
        _lies = [f"line {ln}: {_line(_rel, ln)!r}"
                 for ln, s in _render_strings(_t) if "需全部符合" in s]
        assert not _lies, (
            f"門檻是 {WINNING_FORMULA_MIN_PASS}/5，畫面卻寫「需全部符合」：\n  "
            + "\n  ".join(_lies))
        assert "WINNING_FORMULA_MIN_PASS" in _referenced_names(_t), (
            "放行門檻沒有引用 SSOT 常數 → 標題與判定式又會各寫一份")


# ══════════════════════════════════════════════════════════════════════
# 3. K 線籌碼結論：外資 = 0 / 未取得 時不得說出與月線位置相反的話
# ══════════════════════════════════════════════════════════════════════
class TestKlineChipVerdict:
    @staticmethod
    def _v(above, net):
        from src.ui.tabs.stock_sections.section_kline_chart import kline_chip_verdict
        return kline_chip_verdict(above, net)

    def test_above_ma20_with_zero_net_does_not_say_below(self):
        """原始 bug：`else` 分支寫死「月線下方且外資賣超」，而 net==0 會落進來。"""
        _label, _verdict, _next = self._v(True, 0)
        assert _label == "中性"
        assert "站上月線" in _verdict
        assert "月線下方" not in _verdict
        assert "賣超" not in _verdict

    def test_above_ma20_with_unknown_net(self):
        _label, _verdict, _next = self._v(True, None)
        assert _label == "未取得"
        assert "站上月線" in _verdict
        assert "未取得" in _verdict
        # 「外資買賣超未取得」本身含「買賣超」三字，先剔掉再驗沒有方向性宣稱
        _stripped = _verdict.replace("買賣超", "")
        assert "賣超" not in _stripped and "買超" not in _stripped

    def test_ma_position_always_matches_text(self):
        """不變量：文字裡的月線位置必須等於輸入的月線位置（8 種組合全覆蓋）。"""
        for _above in (True, False):
            for _net in (None, -100.0, 0, 100.0):
                _, _verdict, _ = self._v(_above, _net)
                assert ("站上月線" in _verdict) is _above, (_above, _net, _verdict)
                assert ("月線下方" in _verdict) is (not _above), (_above, _net, _verdict)

    def test_direction_labels(self):
        assert self._v(True, 100.0)[0] == "買超"
        assert self._v(False, -100.0)[0] == "賣超"
        assert "築底" in self._v(False, 100.0)[1]
        assert "迴避" in self._v(False, -100.0)[1]


# ══════════════════════════════════════════════════════════════════════
# 4. 財報領先：「龍多確認」必須真的比對佔股本比，不是「有值就綠」
# ══════════════════════════════════════════════════════════════════════
class TestLeadingGates:
    @staticmethod
    def _g(cl, cx, cap):
        from src.ui.tabs.stock_sections.section_financial_leading import (
            evaluate_leading_gates)
        return evaluate_leading_gates(cl, cx, cap)

    def test_positive_but_below_threshold_is_not_lead(self):
        """原始 bug：判定式只有 `cl>0 and cx>0` ⇒ 幾乎每檔製造業都「✅ 龍多確認」。"""
        _cap = 100e8
        _g = self._g(10e8, 20e8, _cap)      # 10% / 20%
        assert _g["cl_pct"] == pytest.approx(10.0)
        assert _g["cx_pct"] == pytest.approx(20.0)
        assert _g["cl_lead"] is False and _g["cx_lead"] is False
        assert _g["ratio_known"] is True     # 「算過但不達標」≠「沒算」

    def test_threshold_boundaries_match_ssot(self):
        from shared.signal_thresholds import (
            CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT as CX,
            CONTRACT_LIABILITY_TO_EQUITY_RATIO_THRESHOLD_PCT as CL,
        )
        _cap = 100e8
        assert self._g(_cap * CL / 100, None, _cap)["cl_lead"] is True    # 恰達標
        assert self._g(_cap * (CL - 1) / 100, None, _cap)["cl_lead"] is False
        assert self._g(None, _cap * CX / 100, _cap)["cx_lead"] is True
        assert self._g(None, _cap * (CX - 1) / 100, _cap)["cx_lead"] is False

    def test_capital_unknown_is_unevaluated_not_fail(self):
        for _cap in (None, 0, 0.0, "x"):
            _g = self._g(60e8, 90e8, _cap)
            assert _g["cl_pct"] is None and _g["cx_pct"] is None, _cap
            assert _g["cl_lead"] is False and _g["cx_lead"] is False, _cap
            assert _g["ratio_known"] is False, _cap   # ← 用來區分「未評估」與「未達標」

    def test_missing_item_is_unevaluated(self):
        _g = self._g(None, 90e8, 100e8)
        assert _g["cl_pct"] is None and _g["cl_lead"] is False
        assert _g["cx_lead"] is True
        assert _g["ratio_known"] is True

    def test_tab_stock_passes_capital(self):
        """接線：不傳股本的話，上面那條門檻永遠是「未評估」。"""
        _kw = _keywords_of_call(_tree("src/ui/tabs/tab_stock.py"),
                                "render_financial_leading_section")
        assert "capital" in _kw, f"tab_stock 沒把股本傳給財報領先 section（實傳 {_kw}）"


# ══════════════════════════════════════════════════════════════════════
# 5. v4 相對籌碼：逐日序列，不是單日廣播
# ══════════════════════════════════════════════════════════════════════
class TestChipColumns:
    @staticmethod
    def _df(foreign, trust=None):
        return pd.DataFrame({
            "close": [100.0] * len(foreign),
            "外資": foreign,
            "投信": trust if trust is not None else [0] * len(foreign),
        })

    def test_maps_daily_series_not_scalar(self):
        from src.ui.tabs.stock_sections.section_health_score import attach_chip_columns
        _out = attach_chip_columns(self._df([1, 2, 3, 4, 5]))
        assert _out["foreign_net"].tolist() == [1, 2, 3, 4, 5]

    def test_five_day_sum_is_real_sum(self):
        """原始 bug：整欄被塞成最後一日的值 ⇒ `tail(5).sum()` = 單日 × 5。

        這裡直接把「正確」與「舊錯法」都算一次，釘住兩者不同。
        """
        from src.ui.tabs.stock_sections.section_health_score import attach_chip_columns
        _src = self._df([1, 2, 3, 4, 5])
        _good = attach_chip_columns(_src)["foreign_net"].tail(5).sum()
        _old_broadcast = pd.Series([5] * 5).sum()     # 舊寫法的等效結果
        assert _good == 15
        assert _old_broadcast == 25
        assert _good != _old_broadcast

    def test_nan_becomes_zero_but_column_still_daily(self):
        from src.ui.tabs.stock_sections.section_health_score import attach_chip_columns
        _out = attach_chip_columns(self._df([1, None, 3, 4, 5]))
        assert _out["foreign_net"].tolist() == [1, 0, 3, 4, 5]

    def test_missing_columns_leaves_engine_without_chips(self):
        """§1：沒有籌碼欄就不建欄，讓引擎誠實回「無籌碼資料」。"""
        from src.ui.tabs.stock_sections.section_health_score import attach_chip_columns
        _out = attach_chip_columns(pd.DataFrame({"close": [1.0, 2.0]}))
        assert "foreign_net" not in _out.columns
        assert "trust_net" not in _out.columns

    def test_does_not_mutate_input(self):
        from src.ui.tabs.stock_sections.section_health_score import attach_chip_columns
        _src = self._df([1, 2, 3])
        attach_chip_columns(_src)
        assert "foreign_net" not in _src.columns

    def test_engine_ratio_uses_five_day_sum(self):
        """接到 L2 引擎：外本比 = 近5日淨買 ÷ 發行張數 × 100。"""
        from src.compute.strategy.v4_strategy_engine import V4StrategyEngine
        from src.ui.tabs.stock_sections.section_health_score import attach_chip_columns
        _n = 30
        _df = pd.DataFrame({
            "close": [100.0] * _n, "open": [99.0] * _n,
            "high": [101.0] * _n, "low": [98.0] * _n,
            "volume": [1000.0] * _n,
            "外資": [0] * (_n - 5) + [10, 20, 30, 40, 50],
            "投信": [0] * _n,
        })
        _eng = V4StrategyEngine(attach_chip_columns(_df), {"vix": None}, 100_000)
        _chip = _eng.calc_relative_chips(days=5)
        # (10+20+30+40+50) / 100000 * 100 = 0.15
        assert _chip["foreign_ratio"] == pytest.approx(0.15, abs=1e-6)


# ══════════════════════════════════════════════════════════════════════
# 6. VCP / 布林結論：標籤與內容不得錯配
# ══════════════════════════════════════════════════════════════════════
class TestVcpBollingerVerdicts:
    _BB = {"bw": 9.0, "bw_mean": 10.0, "near_upper": False}

    def test_two_verdicts_are_distinct(self):
        """原始 bug：`for _msg in [...]` 的迴圈變數殘留 ⇒ VCP 的結論條印出布林的話。"""
        from src.ui.tabs.stock_sections.section_vcp_bollinger import vcp_bollinger_verdicts
        _v, _b = vcp_bollinger_verdicts({"contracting": True, "swings": [3, 2, 1]}, self._BB)
        assert "VCP" in _v
        assert "布林" in _b
        assert _v != _b

    def test_vcp_only(self):
        from src.ui.tabs.stock_sections.section_vcp_bollinger import vcp_bollinger_verdicts
        _v, _b = vcp_bollinger_verdicts({"contracting": False, "swings": []}, None)
        assert _b == ""
        assert _v and "布林" not in _v

    def test_bollinger_only(self):
        from src.ui.tabs.stock_sections.section_vcp_bollinger import vcp_bollinger_verdicts
        _v, _b = vcp_bollinger_verdicts(None, self._BB)
        assert _v == ""
        assert "布林" in _b

    def test_both_missing(self):
        from src.ui.tabs.stock_sections.section_vcp_bollinger import vcp_bollinger_verdicts
        assert vcp_bollinger_verdicts(None, None) == ("", "")

    def test_no_dir_lookup_antipattern(self):
        """`'x' in dir()` 是這個 bug 的根因寫法（把迴圈變數殘留當成「有沒有算過」）。"""
        _bad = []
        for _rel in ("src/ui/tabs/stock_sections/section_vcp_bollinger.py",
                     "src/ui/tabs/stock_sections/section_kline_chart.py"):
            for node in ast.walk(_tree(_rel)):
                if not isinstance(node, ast.Compare):
                    continue
                if not any(isinstance(o, ast.In) for o in node.ops):
                    continue
                for _cmp in node.comparators:
                    if (isinstance(_cmp, ast.Call) and isinstance(_cmp.func, ast.Name)
                            and _cmp.func.id == "dir" and not _cmp.args):
                        _bad.append(f"{_rel}:{node.lineno}: {_line(_rel, node.lineno)!r}")
        assert not _bad, (
            "`'x' in dir()` 反模式復活（它會把上一個迴圈殘留的值當成有效結論）：\n  "
            + "\n  ".join(_bad))


# ══════════════════════════════════════════════════════════════════════
# 7. v5 財報領先：死區必須解除
# ══════════════════════════════════════════════════════════════════════
class TestFundamentalLeadingWiring:
    def test_old_call_shape_can_only_return_generic(self):
        """釘住「舊寫法是死區」這個事實：3 個判定輸入全 None ⇒ 只可能回一般水準。

        （這條不是要求實作維持舊行為，而是證明舊行為確實是死區 ——
        下一條才是真正的修復驗證。）
        """
        from src.compute.strategy.v5_modules import analyze_fundamental_leading
        for _cl in (1e8, 500e8, 5000e8):
            _r = analyze_fundamental_leading(_cl, None, None, None, None)
            assert "一般水準" in _r["signal"], (_cl, _r["signal"])

    def test_capex_branch_is_reachable_with_real_inputs(self):
        from shared.signal_thresholds import CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT as CX
        from src.compute.strategy.v5_modules import analyze_fundamental_leading
        _equity = 100e8
        _capex = _equity * (CX + 10) / 100          # 90% > 80% 門檻
        _r = analyze_fundamental_leading(10e8, None, _capex, None, _equity)
        assert "積極擴張" in _r["signal"], _r
        assert _r["capex_ratio"] == pytest.approx(CX + 10)

    def test_below_threshold_still_generic(self):
        from shared.signal_thresholds import CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT as CX
        from src.compute.strategy.v5_modules import analyze_fundamental_leading
        _equity = 100e8
        _r = analyze_fundamental_leading(10e8, None, _equity * (CX - 10) / 100,
                                         None, _equity)
        assert "一般水準" in _r["signal"], _r

    def test_tab_stock_passes_capex_and_capital(self):
        _kw = _keywords_of_call(_tree("src/ui/tabs/tab_stock.py"),
                                "render_health_score_section")
        _missing = {"capex2", "capital2"} - _kw
        assert not _missing, (
            f"v5 財報領先卡缺少輸入 {sorted(_missing)} → 會退回死區（實傳 {sorted(_kw)}）")

    def test_no_phantom_equity_session_key(self):
        """`t2_equity_{sid}` 全站無寫入點，不得再被讀。"""
        _rel = "src/ui/tabs/stock_sections/section_health_score.py"
        _bad = [f"line {ln}: {_line(_rel, ln)!r}"
                for ln, s in _render_strings(_tree(_rel)) if "t2_equity_" in s]
        assert not _bad, "又在讀從未被寫入的 session key `t2_equity_`：\n  " + "\n  ".join(_bad)


# ══════════════════════════════════════════════════════════════════════
# 8. regime 接線：不得直讀 raw regime，也不得捏 'neutral'
# ══════════════════════════════════════════════════════════════════════
_REGIME_CONSUMERS = (
    "src/ui/tabs/tab_stock.py",
    "src/ui/tabs/macro_stock_link.py",
    "src/ui/tabs/stock_sections/section_op_recommendation.py",
    "src/ui/tabs/stock_sections/section_psy_checklist.py",
    "src/ui/tabs/stock_grp_sections/section_ai_portfolio.py",
)


def _fabricated_regime_defaults(tree: ast.Module) -> list[ast.Call]:
    """找 `<x>.get('regime', <字串>)` —— 未評估時被偽裝成一個具體多空判斷。"""
    out: list[ast.Call] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get" and len(node.args) == 2):
            continue
        _k, _d = node.args
        if (isinstance(_k, ast.Constant) and _k.value == "regime"
                and isinstance(_d, ast.Constant) and isinstance(_d.value, str)):
            out.append(node)
    return out


class TestRegimeWiring:
    @pytest.mark.parametrize("rel", _REGIME_CONSUMERS)
    def test_no_fabricated_regime_default(self, rel):
        _hits = _fabricated_regime_defaults(_tree(rel))
        _msg = [f"{rel}:{n.lineno}: {_line(rel, n.lineno)!r}" for n in _hits]
        assert not _hits, (
            "§1：`.get('regime', '<預設>')` 把「總經未評估」偽裝成一個具體多空判斷。\n"
            "  請改吃 allocation_service.get_macro_regime()（C1 唯一仲裁點）：\n  "
            + "\n  ".join(_msg))

    @pytest.mark.parametrize("rel", _REGIME_CONSUMERS)
    def test_uses_single_arbiter(self, rel):
        assert "get_macro_regime" in _referenced_names(_tree(rel)), (
            f"{rel} 沒有接上 C1 唯一仲裁點 get_macro_regime()")

    def test_detector_catches_a_synthetic_offender(self, tmp_path):
        """守衛自我驗證：造一個真的違規檔，掃描器必須抓到。"""
        _f = tmp_path / "offender.py"
        _f.write_text(
            "import streamlit as st\n"
            "x = st.session_state.get('mkt_info', {}).get('regime', 'neutral')\n",
            encoding="utf-8")
        _t = ast.parse(_f.read_text(encoding="utf-8"))
        assert len(_fabricated_regime_defaults(_t)) == 1

    def test_detector_ignores_the_fixed_shape(self, tmp_path):
        """守衛自我驗證②：修好之後的寫法不得被誤判（避免假紅燈）。"""
        _f = tmp_path / "fixed.py"
        _f.write_text(
            "from src.services.allocation_service import get_macro_regime\n"
            "r = get_macro_regime()\n"
            "x = r.get('regime') or 'unknown'\n",
            encoding="utf-8")
        _t = ast.parse(_f.read_text(encoding="utf-8"))
        assert _fabricated_regime_defaults(_t) == []
        assert "get_macro_regime" in _referenced_names(_t)

    def test_unknown_regime_has_prompt_wording(self):
        """未評估要送進 LLM 的是「未評估 + 禁止推估」，不是「震盪整理」。"""
        for _rel in ("src/ui/tabs/tab_stock.py",
                     "src/ui/tabs/stock_grp_sections/section_ai_portfolio.py"):
            _texts = [s for _, s in _render_strings(_tree(_rel))]
            assert any("未評估" in s and "禁止" in s for s in _texts), (
                f"{_rel} 的 regime → 中文對照表沒有處理 'unknown'，"
                "LLM 會收到英文碼或被當成震盪")


# ══════════════════════════════════════════════════════════════════════
# 9. 殘留人名 + 說明文字與判定式一致
# ══════════════════════════════════════════════════════════════════════
class TestRenderTextHonesty:
    def test_no_person_name_left_in_when_buy_sell(self):
        _rel = "src/ui/tabs/stock_sections/section_when_buy_sell.py"
        _bad = [f"line {ln}: {_line(_rel, ln)!r}"
                for ln, s in _render_strings(_tree(_rel)) if "林穎" in s]
        assert not _bad, "可渲染字串仍含人名：\n  " + "\n  ".join(_bad)

    def test_banned_list_covers_it(self):
        """名單型守衛的補洞：這個名字必須進得了全 repo 掃描的 SSOT 名單。"""
        from tests.test_b2a_breach_and_naming import _BANNED_PERSON_TOKENS
        assert "林穎" in _BANNED_PERSON_TOKENS

    def test_revenue_help_text_matches_rule(self):
        """月營收說明原寫「連續3個月YoY>15%」，判定式其實是「近3月平均>15% 且皆為正」。"""
        _rel = "src/ui/tabs/stock_sections/section_revenue.py"
        _texts = [s for _, s in _render_strings(_tree(_rel))]
        _lies = [s for s in _texts if "連續3個月YoY" in s]
        assert not _lies, f"說明文字仍宣稱一個沒在跑的規則：{_lies}"
        assert any("平均" in s and "15" in s for s in _texts), \
            "說明文字沒有講出實際在跑的『近3月平均』規則"

    def test_chart_percent_labels_are_interpolated(self):
        """K 線關鍵價位圖例的 % 原本寫死，門檻一改就會指錯位置。"""
        _rel = "src/ui/tabs/stock_sections/section_when_buy_sell.py"
        _t = _tree(_rel)
        _names = _referenced_names(_t)
        for _c in ("STOP_PROFIT_T1_PCT", "STOP_PROFIT_T2_PCT",
                   "STOP_LOSS_DEFAULT_PCT", "HARD_STOP_LOSS_PCT"):
            assert _c in _names, f"{_rel} 未引用 {_c}（圖例 % 又會與實際價位脫鉤）"
        # 負向檢查：可渲染字串裡不得再出現「停利/停損 + 寫死數字」的組合
        # （插值寫法的字面片段是 `停利1 +` / `% ` —— 數字在 f-string 佔位符裡，掃不到）
        # ⚠️ 必須要求「正負號 + 數字 + %」三者齊備。原式 `[+-]?\d` 沒有要求符號與 %，
        # 於是 f-string 常數片段 `'停利2 +'` 裡的 **2（序號「停利2」）** 被當成百分比，
        # 讓正確的插值寫法自己觸發守衛 —— 守衛分不出「停利2」與「停利 +5%」。
        _hard = re.compile(r"(停利|停損)[^0-9\n]{0,4}[+-]\s*\d+(?:\.\d+)?\s*%")
        _lies = [f"line {ln}: {s!r}" for ln, s in _render_strings(_t) if _hard.search(s)]
        assert not _lies, "圖例／文案又出現寫死的停利停損百分比：\n  " + "\n  ".join(_lies)

    def test_dragon_alert_uses_ssot_thresholds(self):
        """龍頭預警的 50% / 80% 曾有三份複本（此處 inline、AI prompt、財報卡副標）。

        Batch A(2026-08) 更新 —— 守衛強度只增不減：

        原本斷言「本檔必須直接引用兩個門檻常數」。但本檔已改為委派
        `section_financial_leading.evaluate_leading_gates()`（同層 L5 純函式），
        由**那一支**引用 SSOT 常數並負責比例計算 —— 這比各自引用常數再各寫一次
        `value / capital * 100 >= 門檻` 更強：連「判定式」本身都只剩一份。
        直接沿用舊斷言會逼著本檔為了過測試而 import 兩個用不到的常數。

        改為「二擇一 + 負向檢查」：
          (1) 直接引用兩個常數，**或** 委派 `evaluate_leading_gates`；
          (2) **新增**：檔內不得出現這兩個門檻的數值複本 —— 這才是 docstring 裡
              「三份複本」真正要防的事，舊版反而沒有檢查。
        """
        from shared.signal_thresholds import (
            CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT as _CX_TH,
            CONTRACT_LIABILITY_TO_EQUITY_RATIO_THRESHOLD_PCT as _CL_TH,
        )
        _rel = "src/ui/tabs/stock_sections/section_dragon_alert.py"
        _t = _tree(_rel)
        _names = _referenced_names(_t)

        _direct = ("CONTRACT_LIABILITY_TO_EQUITY_RATIO_THRESHOLD_PCT" in _names
                   and "CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT" in _names)
        _delegated = "evaluate_leading_gates" in _names
        assert _direct or _delegated, (
            f"{_rel} 既未引用兩個 SSOT 門檻常數，也未委派 evaluate_leading_gates "
            "→ 門檻判定很可能又自己寫了一份")

        # 負向檢查：門檻「數值」不得以字面量形式出現在本檔（SSOT 一改就漂移）。
        # 只掃數值 Constant —— docstring 裡的「≥ 50%」是字串，不算複本。
        _dupes = [
            f"line {_n.lineno}: {_n.value!r}"
            for _n in ast.walk(_t)
            if isinstance(_n, ast.Constant)
            and isinstance(_n.value, (int, float))
            and not isinstance(_n.value, bool)
            and float(_n.value) in (float(_CL_TH), float(_CX_TH))
        ]
        assert not _dupes, (
            f"{_rel} 出現門檻數值複本（SSOT 一改就會漂移）：\n  " + "\n  ".join(_dupes))


# ══════════════════════════════════════════════════════════════════════
# 10. 外本比分母：不得有捏造的預設張數
# ══════════════════════════════════════════════════════════════════════
class TestShareDenominator:
    _REL = "src/ui/tabs/stock_sections/section_health_score.py"

    def test_no_positive_default_for_shares(self):
        _bad = []
        for node in ast.walk(_tree(self._REL)):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get" and len(node.args) == 2):
                continue
            _k, _d = node.args
            _is_key = (isinstance(_k, ast.JoinedStr)
                       and any(isinstance(v, ast.Constant) and "t2_shares_" in str(v.value)
                               for v in _k.values))
            if _is_key and isinstance(_d, ast.Constant) \
                    and isinstance(_d.value, (int, float)) and _d.value > 0:
                _bad.append(f"line {node.lineno}: {_line(self._REL, node.lineno)!r}")
        assert not _bad, (
            "外本比分母又出現捏造的預設張數（§1）：\n  " + "\n  ".join(_bad))

    def test_render_gates_on_known_shares(self):
        assert "_shares_known" in _referenced_names(_tree(self._REL)), \
            "缺少『發行張數是否已知』的三態旗標 → 股本抓不到時仍會印出百分比"

    def test_vpoc_card_is_tristate(self):
        """VPOC 算不出來（<60 日 / 計算失敗）時不得顯示綠色的「✅ 壓力有限」。

        引擎在這兩種情況都回 `vpoc_price=None, has_pressure=False`，
        舊碼只看 `has_pressure` ⇒ 新股一律綠燈。
        """
        from src.compute.strategy.v4_strategy_engine import V4StrategyEngine
        _n = 30   # < 60 → 引擎明確回「資料不足」
        _df = pd.DataFrame({
            "close": [100.0] * _n, "open": [99.0] * _n,
            "high": [101.0] * _n, "low": [98.0] * _n, "volume": [1000.0] * _n,
        })
        _rs = V4StrategyEngine(_df, {"vix": None}, 100_000).find_overhead_resistance()
        assert _rs["vpoc_price"] is None and _rs["has_pressure"] is False, _rs
        # UI 端必須改看 vpoc_price 才能區分「沒壓力」與「沒算出來」
        assert "_rs_known" in _referenced_names(_tree(self._REL)), (
            "上方賣壓卡沒有『VPOC 是否算得出來』的旗標 → 新股又會顯示綠色的「壓力有限」")

    def test_vix_not_hardcoded_in_ui(self):
        """v4 總經輸入的 VIX 原本在 UI 層寫死 15（引擎的 fallback 值被當成已知值）。"""
        _bad = []
        for node in ast.walk(_tree(self._REL)):
            if not isinstance(node, ast.Dict):
                continue
            for _k, _v in zip(node.keys, node.values):
                if (isinstance(_k, ast.Constant) and _k.value == "vix"
                        and isinstance(_v, ast.Constant)
                        and isinstance(_v.value, (int, float))):
                    _bad.append(f"line {node.lineno}: {_line(self._REL, node.lineno)!r}")
        assert not _bad, "UI 層又把 VIX 寫成固定數字：\n  " + "\n  ".join(_bad)
