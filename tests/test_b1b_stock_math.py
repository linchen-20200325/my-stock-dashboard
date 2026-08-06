"""tests/test_b1b_stock_math.py — B1-b 個股頁兩個數學錯誤的守衛（v19.179）。

兩個缺陷、同一個根因家族：**畫面上的數字不是它宣稱的那個量**。

① v5 存股殖利率被除以股價兩次（§4.1 量綱陷阱）
   `calc_dividend_yield_357()` 契約寫 `avg_payout: 近三年平均配發率（0~1）`，
   函式內 `est_div = eps_ttm * avg_payout`、`est_yield = est_div / price * 100`。
   但唯一的 caller（`section_health_score.py`）傳的是 `avg_div2 / max(price2, 1)`
   ＝**殖利率**。展開後：

       est_yield = (eps × (avg_div / price)) / price × 100      ← price 出現兩次

   實機 2330 對帳（2026-08-06）：avg_div=13.70、price=2320
       誤傳 payout = 13.70 / 2320 = 0.0059
       est_div    ≈ EPS_ttm × 0.0059 ≈ 0.35 元
       est_yield  ≈ 0.015%  → 畫面顯示 **0.01%**  ✔ 與實機吻合
       真值        = 13.70 / 2320 × 100 = **0.59%**
   低估倍率 = price / eps_ttm ≈ 40×。而 0.01% 會落進「🔴 超貴（<3%）」——
   一個**由量綱錯誤生出來的看空結論**（§1 反捏造）。

   諷刺的是同一頁 B 區 357 的算法是對的（13.70÷7%/5%/3% = 195.7/274.0/456.7），
   所以是「同一頁兩套 357，一套壞的」。修法：v5 改收**年均現金股利（元）**，
   分級直接委派 `shared.thresholds.classify_stock_357_price`（B 區用的同一支），
   兩張卡從「代數上可能等價」升級成「由建構保證同一個答案」。

② 「盈虧比」恆等於 0.625，旁邊卻標「≥1.5 較理想」（§1 假目標）
   `tab_stock.py` 舊碼 `(_tp1_p - _cur_p) / max(_cur_p - _sl_p, 0.01)`，
   而 `_tp1_p = 現價×1.05`、`_sl_p = 現價×0.92` ⇒ 現價完全約掉
   ⇒ 結果 ≡ 5/8 = 0.625，**對任何股票、任何價格都一樣**。
   一個資訊量為 0 的數字，配一個數學上永遠達不到的門檻。
   同頁 `:809` 另有一個「實際盈虧比」用**紅K低點**當停損 → 同名不同義。
   修法：正名為「固定方案盈虧比」（並列 T1/T2，說明它是方案先天常數），
   另一個正名為「實際盈虧比（紅K低點停損）」；無紅K 錨點時顯示未評估，
   不再偷偷退回固定 -8% 停損卻仍自稱「實際」。

守衛設計（本 session 已被字串掃描守衛的假紅燈擋過四次）
==========================================================
- 原始碼層的檢查一律走 **AST**：
  * `#` 註解天生不在 AST 內 ⇒ 上面那些解釋「舊碼錯在哪」的中文註解
    （裡面照抄了 `≥1.5 較理想`、`avg_div2 / max(price2, 1)`）不會被自己誤殺。
  * docstring 以 `ast.get_docstring()` 逐節點顯式排除。
- 每個失敗訊息都印 `檔名:行號` + **該行原始碼原文**，紅燈可直接定位。
- 測試分三層：golden（實機數字逐格對帳）／property（固定格點窮舉，
  依本 repo 慣例不引 hypothesis）／單元＋契約守衛。
"""
from __future__ import annotations

import ast
import math
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from shared.signal_thresholds import (  # noqa: E402
    FIXED_PLAN_RR_T1,
    FIXED_PLAN_RR_T2,
    STOP_LOSS_DEFAULT_PCT,
    STOP_PROFIT_T1_PCT,
    STOP_PROFIT_T2_PCT,
)
from shared.thresholds import (  # noqa: E402
    YIELD_HIGH,
    YIELD_LOW,
    YIELD_MID,
    classify_stock_357_price,
)
from src.compute.strategy.v5_modules import (  # noqa: E402
    calc_dividend_yield_357,
    count_dividend_paying_years,
)

_TAB_STOCK = "src/ui/tabs/tab_stock.py"
_SECTION_HEALTH = "src/ui/tabs/stock_sections/section_health_score.py"

#: 實機 2330（2026-08-06 截圖）
_TSMC_PRICE = 2320.0
_TSMC_AVG_DIV = 13.70


# ══════════════════════════════════════════════════════════════
# 共用：AST 工具（註解自動排除；docstring 顯式排除）
# ══════════════════════════════════════════════════════════════

def _read(rel: str) -> tuple[str, ast.Module]:
    src = (REPO / rel).read_text(encoding="utf-8")
    return src, ast.parse(src, filename=rel)


def _at(src: str, rel: str, lineno: int) -> str:
    """`檔名:行號 | 該行原始碼原文` —— 失敗訊息用，讓紅燈可直接定位。"""
    lines = src.splitlines()
    raw = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else "<行號超出範圍>"
    return f"{rel}:{lineno} | {raw}"


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """所有 docstring 常數節點的 id()，供掃畫面字串時排除。"""
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


def _screen_strings(tree: ast.Module) -> list[tuple[str, int]]:
    """所有「會出現在畫面上」的字串常數（排除 docstring；含 f-string 片段）。"""
    skip = _docstring_nodes(tree)
    hits: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in skip):
            hits.append((node.value, getattr(node, "lineno", 0)))
    return hits


def _calls_to(tree: ast.Module, name: str) -> list[ast.Call]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if (isinstance(f, ast.Name) and f.id == name) or \
               (isinstance(f, ast.Attribute) and f.attr == name):
                out.append(node)
    return out


def _kpi_titles(tree: ast.Module) -> list[tuple[str, int]]:
    """`kpi(title, ...)` 第一個引數是字面字串時的卡片標題（f-string 標題跳過）。"""
    out: list[tuple[str, int]] = []
    for call in _calls_to(tree, "kpi"):
        if call.args and isinstance(call.args[0], ast.Constant) \
                and isinstance(call.args[0].value, str):
            out.append((call.args[0].value, call.lineno))
    return out


# ══════════════════════════════════════════════════════════════
# ① golden — 實機 2330 逐格對帳
# ══════════════════════════════════════════════════════════════

class TestTsmcGolden:
    """截圖上的每個數字都要能被重現（或被證明是錯的）。"""

    def test_est_yield_is_059_not_001(self):
        """真值 13.70 / 2320 × 100 = 0.59%（舊碼畫面是 0.01%，40× 低估）。"""
        r = calc_dividend_yield_357(_TSMC_PRICE, avg_div_twd=_TSMC_AVG_DIV,
                                    div_years=5)
        assert r["est_yield"] == pytest.approx(0.59, abs=5e-3), (
            f"2330 存股殖利率應為 0.59%，實得 {r['est_yield']}%")
        # 舊 bug 的畫面值必須不可能再出現
        assert r["est_yield"] > 0.1, "0.01% 是量綱錯誤的指紋（除以股價兩次）"

    def test_357_targets_match_screenshot(self):
        """便宜 195.7 / 合理 274.0 / 昂貴 456.7 —— 與 B 區截圖一致。"""
        r = calc_dividend_yield_357(_TSMC_PRICE, avg_div_twd=_TSMC_AVG_DIV,
                                    div_years=5)
        assert r["p_cheap"] == pytest.approx(195.7, abs=0.05)
        assert r["p_fair"] == pytest.approx(274.0, abs=0.05)
        assert r["p_expensive"] == pytest.approx(456.7, abs=0.05)

    def test_verdict_is_overpriced(self):
        """2320 遠高於昂貴價 456.7 ⇒ 超貴。（舊碼碰巧也說超貴，但那是
        0.01% 撞出來的 —— 對的結論配錯的理由，換一檔就會翻車，見下面
        `TestV5AgreesWithSection357`。）"""
        r = calc_dividend_yield_357(_TSMC_PRICE, avg_div_twd=_TSMC_AVG_DIV,
                                    div_years=5)
        assert r["zone_code"] == "overpriced"
        assert "超貴" in r["signal"]

    def test_old_formula_reproduces_the_broken_screen_value(self):
        """根因對帳：把舊碼原樣重算一次，必須長出實機那個 0.01%。

        這是「這個 bug 就是它造成的」的證據，不是靠猜。
        EPS_ttm 取 2330 近四季量級 58 元（低估倍率 = price / eps_ttm，
        對這組數字約 40×，與稽核報告一致）。
        """
        eps_ttm = 58.0
        wrong_payout = _TSMC_AVG_DIV / _TSMC_PRICE      # caller 傳的其實是殖利率
        wrong = round(eps_ttm * wrong_payout / _TSMC_PRICE * 100, 2)
        assert wrong == pytest.approx(0.01, abs=1e-9), (
            f"舊式重算應得畫面上的 0.01%，實得 {wrong}%")

        right = calc_dividend_yield_357(
            _TSMC_PRICE, avg_div_twd=_TSMC_AVG_DIV, div_years=5)["est_yield"]
        assert right == pytest.approx(0.59, abs=5e-3)
        assert right / wrong > 30, (
            f"新舊值倍率 {right / wrong:.1f}×（≈ price/eps_ttm）—— "
            "倍率消失代表 bug 又被接回去了")


# ══════════════════════════════════════════════════════════════
# ② golden 一致性 — v5 卡 vs B 區 357 必須永遠同一個結論
# ══════════════════════════════════════════════════════════════

class TestV5AgreesWithSection357:
    """同一頁兩處 357 不得再打架（§2.1 SSOT）。"""

    #: 涵蓋四個 zone + 邊界（7%/5%/3% 正好命中）+ 高配發率（舊修法 (a) 的破口）
    CASES = [
        (100.0, 10.0),   # 10%  → cheap
        (100.0, 7.0),    # 7%   → cheap（邊界）
        (100.0, 6.0),    # 6%   → fair
        (100.0, 5.0),    # 5%   → fair（邊界）
        (100.0, 4.0),    # 4%   → dear
        (100.0, 3.0),    # 3%   → dear（邊界）
        (100.0, 1.0),    # 1%   → overpriced
        (2320.0, 13.7),  # 實機 2330
        (18.5, 1.55),    # 小型高息股
        (33.0, 5.5),     # 配發率 >100% 的情境（股利大於 TTM EPS 時仍須一致）
    ]

    @pytest.mark.parametrize("price,avg_div", CASES)
    def test_zone_code_identical(self, price, avg_div):
        v5 = calc_dividend_yield_357(price, avg_div_twd=avg_div, div_years=5)
        b_code, b_targets = classify_stock_357_price(price, avg_div)
        assert v5["zone_code"] == b_code, (
            f"v5 卡與 B 區 357 結論不一致：price={price} avg_div={avg_div} "
            f"v5={v5['zone_code']} vs B={b_code}")
        assert (v5["p_cheap"], v5["p_fair"], v5["p_expensive"]) == (
            b_targets["cheap"], b_targets["fair"], b_targets["dear"]), (
            "兩處的三檔目標價必須同源（都走 classify_stock_357_price）")

    @pytest.mark.parametrize("price,avg_div", CASES)
    def test_verdict_wording_matches_zone(self, price, avg_div):
        """UX 措辭必須跟著 zone code 走（便宜/合理/昂貴/超貴 不得錯位）。"""
        expected_kw = {
            "cheap": ("甜甜價", "高殖利率"),
            "fair": ("合理",),
            "dear": ("昂貴",),
            "overpriced": ("超貴",),
        }
        v5 = calc_dividend_yield_357(price, avg_div_twd=avg_div, div_years=5)
        kws = expected_kw[v5["zone_code"]]
        assert any(k in v5["signal"] for k in kws), (
            f"zone={v5['zone_code']} 但 signal='{v5['signal']}' 不含 {kws}")


# ══════════════════════════════════════════════════════════════
# ③ property — 固定格點窮舉（本 repo 慣例：不引 hypothesis）
# ══════════════════════════════════════════════════════════════

class TestYieldProperties:

    PRICES = [5.0, 18.5, 33.0, 100.0, 250.75, 1000.0, 2320.0, 4800.0]
    DIVS = [0.25, 1.0, 1.55, 3.3, 5.5, 13.7, 40.0]

    def test_yield_definition_holds_everywhere(self):
        """不變量：est_yield ≡ round(avg_div / price × 100, 2)。

        這條就是「不准除以股價兩次」的形式化 —— 舊碼在這裡會差
        `price / eps_ttm` 倍（2330 ≈ 40×）。用等式而非容差比較，
        因為 est_yield 有 2 位小數的 round，反推回元會被放大 price/20000。
        """
        for p in self.PRICES:
            for d in self.DIVS:
                r = calc_dividend_yield_357(p, avg_div_twd=d, div_years=5)
                assert r["est_yield"] == pytest.approx(round(d / p * 100, 2),
                                                       abs=1e-9), (
                    f"price={p} avg_div={d}: est_yield={r['est_yield']}% "
                    f"≠ {round(d / p * 100, 2)}%（量綱走鐘）")

    @staticmethod
    def _near_boundary(y: float) -> bool:
        """殖利率落在 7%/5%/3% 邊界上（浮點縮放後可能左右翻面，不納入比較）。"""
        return any(abs(y - b) < 1e-6 for b in (YIELD_HIGH, YIELD_MID, YIELD_LOW))

    def test_scale_invariance(self):
        """殖利率是比值：price 與 avg_div 同倍放大，結論不變（§4.1）。"""
        for k in (2.0, 10.0, 137.5):
            for p in self.PRICES:
                for d in self.DIVS:
                    if self._near_boundary(d / p * 100):
                        continue  # 邊界格點另由 test_boundaries_* 精確驗證
                    a = calc_dividend_yield_357(p, avg_div_twd=d, div_years=5)
                    b = calc_dividend_yield_357(p * k, avg_div_twd=d * k,
                                                div_years=5)
                    assert a["zone_code"] == b["zone_code"], (
                        f"同倍縮放後結論改變：({p},{d}) → ({p * k},{d * k})")
                    assert math.isclose(a["est_yield"], b["est_yield"],
                                        rel_tol=1e-6, abs_tol=0.011)

    def test_monotonic_in_price(self):
        """股價越高 → 殖利率越低 → 位階不會往「便宜」跑（單調性）。"""
        order = {"cheap": 3, "fair": 2, "dear": 1, "overpriced": 0}
        for d in self.DIVS:
            prev = None
            for p in sorted(self.PRICES):
                r = calc_dividend_yield_357(p, avg_div_twd=d, div_years=5)
                cur = order[r["zone_code"]]
                if prev is not None:
                    assert cur <= prev, (
                        f"avg_div={d}: 股價漲到 {p} 反而變便宜（{r['zone_code']}）")
                prev = cur

    def test_boundaries_land_on_the_generous_side(self):
        """7%/5%/3% 正好命中時，落在較樂觀的那一格（與 B 區同一套邊界）。"""
        for pct, expect in ((YIELD_HIGH, "cheap"), (YIELD_MID, "fair"),
                            (YIELD_LOW, "dear")):
            r = calc_dividend_yield_357(100.0, avg_div_twd=pct, div_years=5)
            assert r["zone_code"] == expect, (
                f"殖利率正好 {pct}% 時應為 {expect}，實得 {r['zone_code']}")


# ══════════════════════════════════════════════════════════════
# ④ §1 Fail Loud — 缺資料一律「未評估」，不得回 0
# ══════════════════════════════════════════════════════════════

class TestMissingDataIsUnevaluated:
    """0% 會被判「超貴」＝ 拿缺資料當看空結論，這是舊碼最惡質的地方
    （caller 在 avg_div2 為 0 時直接傳 0 進去）。"""

    @pytest.mark.parametrize("price,avg_div", [
        (2320.0, 0.0),      # 成長股不配息
        (2320.0, None),     # 抓取失敗
        (2320.0, -1.0),     # 髒資料
        (0.0, 13.7),        # 無股價
        (None, 13.7),       # 無股價（None）
        (-5.0, 13.7),       # 髒股價
    ])
    def test_returns_none_not_zero(self, price, avg_div):
        r = calc_dividend_yield_357(price or 0, avg_div_twd=avg_div,
                                    div_years=None)
        assert r["est_yield"] is None, "缺資料必須回 None（未評估），不可回 0"
        assert r["zone_code"] == "na"
        assert "未評估" in r["signal"]
        for bad in ("超貴", "昂貴", "甜甜價", "合理"):
            assert bad not in r["signal"], (
                f"缺資料卻給出估值結論『{bad}』（§1 反捏造）：{r['signal']}")

    def test_old_positional_call_fails_loud(self):
        """舊簽章 `(price, eps_ttm, avg_payout, div_years)` 的殘留呼叫必須
        當場 TypeError，而不是靜默算出錯 40 倍的數字（keyword-only 防呆）。"""
        with pytest.raises(TypeError):
            calc_dividend_yield_357(100, 8, 0.75, 7)  # type: ignore[misc]

    def test_avg_div_is_required(self):
        with pytest.raises(TypeError):
            calc_dividend_yield_357(100)  # type: ignore[call-arg]


# ══════════════════════════════════════════════════════════════
# ⑤ 配息年數 — 「沒查到」不等於「查到 0 年」
# ══════════════════════════════════════════════════════════════

class TestCountDividendPayingYears:

    def test_counts_paying_years(self):
        yearly = [{"year": 2021, "cash": 2.5}, {"year": 2022, "cash": 11.0},
                  {"year": 2023, "cash": 11.0}, {"year": 2024, "cash": 13.5},
                  {"year": 2025, "cash": 16.0}]
        assert count_dividend_paying_years(yearly) == 5

    def test_skips_zero_years(self):
        yearly = [{"year": 2023, "cash": 0.0}, {"year": 2024, "cash": 3.0}]
        assert count_dividend_paying_years(yearly) == 1

    @pytest.mark.parametrize("bad", [None, [], [1, 2, 3], [{"year": 2024}]])
    def test_unknown_returns_none_not_zero(self, bad):
        """形狀不符 / 沒資料 → None（未知），不可猜 0（那會宣稱「連續配息 0 年」）。"""
        assert count_dividend_paying_years(bad) is None

    def test_unknown_years_do_not_claim_instability(self):
        r = calc_dividend_yield_357(100.0, avg_div_twd=10.0, div_years=None)
        assert r["zone_code"] == "cheap"
        assert "未知" in r["msg"], f"配息年數未知時不得宣稱穩定或不穩定：{r['msg']}"

    def test_five_paying_years_unlocks_sweet_price(self):
        r = calc_dividend_yield_357(100.0, avg_div_twd=10.0, div_years=5)
        assert "甜甜價" in r["signal"]


# ══════════════════════════════════════════════════════════════
# ⑥ Bug 2 數學 — 固定方案盈虧比是常數；實際盈虧比不是
# ══════════════════════════════════════════════════════════════

def _old_rr_from_prices(price: float) -> float:
    """舊碼 tab_stock.py:640 的算式（原樣重現，用來證明它是常數）。"""
    tp1 = round(price * (1 + STOP_PROFIT_T1_PCT / 100), 2)
    sl = round(price * (1 - STOP_LOSS_DEFAULT_PCT / 100), 2)
    return round((tp1 - price) / max(price - sl, 0.01), 2)


def _real_rr(price: float, stop: float) -> float:
    """新的「實際盈虧比」：停利用 T1，停損用真實錨點（紅K低點）。"""
    tp1 = round(price * (1 + STOP_PROFIT_T1_PCT / 100), 2)
    return round((tp1 - price) / (price - stop), 2)


class TestRiskRewardIsNoLongerAConstantPretendingToBeAScore:

    PRICES = [12.35, 33.0, 100.0, 250.75, 1000.0, 2320.0, 4800.0]

    def test_fixed_plan_rr_derives_from_ssot(self):
        """§3.3：0.625 不得 inline，必須由 SSOT 百分比推導。"""
        assert math.isclose(FIXED_PLAN_RR_T1,
                            STOP_PROFIT_T1_PCT / STOP_LOSS_DEFAULT_PCT,
                            rel_tol=1e-12, abs_tol=1e-12)
        assert math.isclose(FIXED_PLAN_RR_T2,
                            STOP_PROFIT_T2_PCT / STOP_LOSS_DEFAULT_PCT,
                            rel_tol=1e-12, abs_tol=1e-12)
        assert math.isclose(FIXED_PLAN_RR_T1, 0.625, rel_tol=1e-12)
        assert math.isclose(FIXED_PLAN_RR_T2, 1.25, rel_tol=1e-12)

    def test_old_formula_is_constant_across_every_price(self):
        """舊「盈虧比」對任何股票都一樣 ⇒ 資訊量 0，所以它被正名為
        『固定方案盈虧比』而不是留著假裝是個股評分。"""
        vals = [_old_rr_from_prices(p) for p in self.PRICES]
        for p, v in zip(self.PRICES, vals):
            assert v == pytest.approx(FIXED_PLAN_RR_T1, abs=0.011), (
                f"price={p} 的舊式盈虧比 {v} 偏離常數 {FIXED_PLAN_RR_T1}")

    def test_old_formula_jitters_only_from_rounding(self):
        """舊式從 `round(價位, 2)` 反推 ⇒ 會冒出 0.62 / 0.63 兩個值，
        看起來像「因股而異」，其實只是四捨五入雜訊 ——
        這正是新碼改用 SSOT 推導常數、不從價位反推的理由。"""
        vals = {_old_rr_from_prices(p) for p in self.PRICES}
        assert len(vals) > 1, (
            f"預期看到四捨五入造成的假抖動，實得單一值 {vals}")
        assert max(vals) - min(vals) <= 0.011, (
            f"抖動幅度應在一個 round 單位內，實得 {sorted(vals)}")

    def test_old_target_of_1_5_was_mathematically_unreachable(self):
        """舊碼標『≥1.5 較理想』—— 這個方案連 T2 都只有 1.25，永遠達不到。"""
        assert max(FIXED_PLAN_RR_T1, FIXED_PLAN_RR_T2) < 1.5

    def test_real_rr_actually_varies(self):
        """實際盈虧比錨在紅K低點 ⇒ 隨個股波動而變，不是常數。"""
        price = 2320.0
        vals = {_real_rr(price, stop)
                for stop in (2280.0, 2200.0, 2134.4, 2050.0, 1900.0)}
        assert len(vals) > 1, f"實際盈虧比不應是單一值：{vals}"
        # 停損越近 → 盈虧比越高（單調性）
        assert _real_rr(price, 2280.0) > _real_rr(price, 1900.0)

    def test_real_rr_can_reach_the_stated_target(self):
        """『≥1.5 可操作』這個門檻在實際盈虧比上是**可達的**（停損夠近時），
        所以留在那張卡上是誠實的。"""
        price = 2320.0
        tight_stop = price * (1 - STOP_PROFIT_T1_PCT / 100 / 1.6)
        assert _real_rr(price, tight_stop) >= 1.5


# ══════════════════════════════════════════════════════════════
# ⑦ AST 契約守衛 — tab_stock.py（註解/docstring 已排除）
# ══════════════════════════════════════════════════════════════

class TestTabStockRiskRewardWiring:

    def test_no_ambiguous_bare_risk_reward_card(self):
        """同頁兩張『盈虧比』卡必須各自具名，不得再有一張叫『盈虧比』。"""
        src, tree = _read(_TAB_STOCK)
        offenders = [(t, ln) for t, ln in _kpi_titles(tree) if t.strip() == "盈虧比"]
        assert not offenders, "\n".join(
            f"kpi 標題仍是無限定的『盈虧比』（同頁另有不同義的一個）：\n  "
            + _at(src, _TAB_STOCK, ln) for _, ln in offenders)

    def test_both_risk_reward_cards_are_named(self):
        src, tree = _read(_TAB_STOCK)  # noqa: F841 — src 供失敗訊息備用
        titles = [t for t, _ in _kpi_titles(tree)]
        rr_titles = {t for t in titles if "盈虧比" in t}
        assert "固定方案盈虧比" in rr_titles, (
            f"找不到『固定方案盈虧比』卡；現有盈虧比類標題：{sorted(rr_titles)}")
        assert any("實際盈虧比" in t and "紅K低點" in t for t in rr_titles), (
            f"『實際盈虧比』未標明停損錨點是紅K低點；現有：{sorted(rr_titles)}")
        # 兩個不同義的量 → 恰好兩個不同名稱（同名不同義即為 regression）
        assert len(rr_titles) == 2, (
            f"預期恰有 2 個具名的盈虧比卡，實得 {sorted(rr_titles)}")

    def test_misleading_target_text_is_gone(self):
        """『≥1.5 較理想』掛在一個恆為 0.63 的常數上＝永不達標的假目標。

        只掃 AST 字串常數：本檔頂端 docstring 與 tab_stock.py 的 `#` 註解
        都照抄了這串（用來解釋舊碼錯在哪），它們**不該**被判違規。
        """
        src, tree = _read(_TAB_STOCK)
        offenders = [(s, ln) for s, ln in _screen_strings(tree)
                     if "≥1.5 較理想" in s]
        assert not offenders, "\n".join(
            f"畫面字串仍有『≥1.5 較理想』：\n  " + _at(src, _TAB_STOCK, ln)
            for _, ln in offenders)

    def test_old_constant_formula_is_gone(self):
        """舊算式（由 round 後價位反推）不得殘留 —— 它會產生 ±0.01 的
        四捨五入雜訊，看起來像『因股而異』，其實是常數。"""
        src, tree = _read(_TAB_STOCK)
        bad_shapes = ("_cur_p - _sl_p", "_abs_sl or _sl_p")
        offenders = []
        for node in ast.walk(tree):
            # BoolOp 才抓得到 `_abs_sl or _sl_p`（它不是 BinOp）
            if isinstance(node, (ast.BinOp, ast.BoolOp)):
                try:
                    text = ast.unparse(node)
                except Exception:  # pragma: no cover - 舊版 Python 保險
                    continue
                if any(b in text for b in bad_shapes):
                    offenders.append((text, node.lineno))
        assert not offenders, "\n".join(
            f"舊盈虧比算式殘留（{text}）：\n  " + _at(src, _TAB_STOCK, ln)
            for text, ln in offenders)

    def test_rr_constants_come_from_ssot(self):
        """§3.3：不得 inline 0.625，必須 import FIXED_PLAN_RR_*。"""
        src, tree = _read(_TAB_STOCK)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and \
                    "signal_thresholds" in node.module:
                imported |= {a.name for a in node.names}
        assert {"FIXED_PLAN_RR_T1", "FIXED_PLAN_RR_T2"} <= imported, (
            f"tab_stock.py 未從 shared.signal_thresholds 引入 FIXED_PLAN_RR_*；"
            f"實得 {sorted(imported)}")
        inline = [n.lineno for n in ast.walk(tree)
                  if isinstance(n, ast.Constant)
                  and isinstance(n.value, (int, float))
                  and not isinstance(n.value, bool)
                  and math.isclose(float(n.value), 0.625, abs_tol=1e-12)]
        assert not inline, "\n".join(
            "inline 0.625（應改用 FIXED_PLAN_RR_T1）：\n  " + _at(src, _TAB_STOCK, ln)
            for ln in inline)


# ══════════════════════════════════════════════════════════════
# ⑧ AST 契約守衛 — section_health_score.py 的 caller 接線
# ══════════════════════════════════════════════════════════════

class TestHealthScoreCallerWiring:

    def _the_call(self) -> tuple[str, ast.Call]:
        src, tree = _read(_SECTION_HEALTH)
        calls = _calls_to(tree, "calc_dividend_yield_357")
        assert len(calls) == 1, f"預期 1 個呼叫點，實得 {len(calls)}"
        return src, calls[0]

    def test_passes_amount_not_a_ratio(self):
        """核心回歸守衛：第 2 個參數必須是**股利金額**變數本身，
        不得是 `avg_div2 / price2` 這種已經除過股價的比值。"""
        src, call = self._the_call()
        kw = {k.arg: k.value for k in call.keywords if k.arg}
        assert "avg_div_twd" in kw, (
            "必須以 keyword `avg_div_twd=` 傳入（keyword-only 契約）：\n  "
            + _at(src, _SECTION_HEALTH, call.lineno))
        expr = ast.unparse(kw["avg_div_twd"])
        assert expr == "avg_div2", (
            f"avg_div_twd 應直接傳金額 `avg_div2`，實得 `{expr}`\n"
            f"（含除法＝又把殖利率當配發率傳，就是本 bug 的原形）\n  "
            + _at(src, _SECTION_HEALTH, call.lineno))
        assert not any(isinstance(n, ast.Div)
                       for n in ast.walk(kw["avg_div_twd"])), (
            "avg_div_twd 的運算式含除法：\n  "
            + _at(src, _SECTION_HEALTH, call.lineno))

    def test_only_price_is_positional(self):
        """其餘參數一律 keyword —— 位置呼叫是這個 bug 得以潛伏的溫床。"""
        src, call = self._the_call()
        assert len(call.args) == 1, (
            f"只有 price 可以是位置參數，實得 {len(call.args)} 個：\n  "
            + _at(src, _SECTION_HEALTH, call.lineno))

    def test_div_years_comes_from_real_data(self):
        """配息年數要從真實 yearly 資料數，不得再讀那個從沒被寫過的
        session key `t2_div_hist`。"""
        src, call = self._the_call()
        kw = {k.arg: k.value for k in call.keywords if k.arg}
        assert "div_years" in kw
        expr = ast.unparse(kw["div_years"])
        assert "count_dividend_paying_years" in expr, (
            f"div_years 應由 count_dividend_paying_years(yearly2) 得出，實得 `{expr}`")

    def test_dead_session_key_is_gone(self):
        src, tree = _read(_SECTION_HEALTH)
        offenders = [(s, ln) for s, ln in _screen_strings(tree)
                     if "t2_div_hist" in s]
        assert not offenders, "\n".join(
            "仍在讀從未被寫入的 session key `t2_div_hist`：\n  "
            + _at(src, _SECTION_HEALTH, ln) for _, ln in offenders)

    def test_unevaluated_is_rendered_as_text_not_zero(self):
        """est_yield 為 None 時畫面要出現「未評估」（不是 0% / N/A%）。"""
        src, tree = _read(_SECTION_HEALTH)
        strings = [s for s, _ in _screen_strings(tree)]
        assert any("未評估" in s for s in strings), (
            "section_health_score 未提供『未評估』文案，缺資料會退回數字")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([os.path.abspath(__file__), "-v"]))
