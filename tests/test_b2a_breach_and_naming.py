"""tests/test_b2a_breach_and_naming.py — v19.180 B2-a 守衛。

本檔釘兩件事，都是**實機**（2330，現價 2320）抓到的：

A. v4 防守價已跌破卻顯示「風險 −1.1%」（CLAUDE.md §1 級別）
--------------------------------------------------------
`V4StrategyEngine.calculate_stop_loss()` 的防守價 = `min(MA20, 近10日爆量紅K低點)`，
**兩個候選都可能在現價之上**（股價跌破月線 + 跌破前次帶量紅K低點）。此時
`risk_pct = (price − stop) / price × 100` 會是負數，而 UI 原本無條件印
「風險 {risk_pct}%」＋沿用一般配色 ⇒ 使用者讀成「風險很小」，實際語意卻是
**「依系統自己的規則你已經該無條件停損了」**。

修法：引擎回傳新增 `is_breached` 旗標（語意定義只放 L2 一處，§2.1 SSOT），
UI 依旗標分三態（N/A / 🚨 已跌破 + 紅底 / 正常）渲染，**不讓每個 UI 各自比大小**。

B. v19.174 去識別化的三處漏網
---------------------------
`section_strategy_conclusion.py:89`「🎓 陳重銘 · 毛利率」、
`section_vcp_bollinger.py:54`「VCP [Mark Minervini]」、
`shared/stock_buckets.py:217`「展開下方體檢表後評定 MJ 等級」。

⚠️ **為什麼既有守衛沒抓到**（本檔存在的真正理由）
------------------------------------------------
既有三個人名守衛**全部是「檔案級」的**，加起來只涵蓋 3 個檔：

  1. `tests/test_ui_widgets.py::TestNoPersonNameInSource` → 只掃 `ui_widgets.py`
  2. `tests/test_pattern_targets_ui_mounted.py::test_no_person_name_in_renamed_modules`
     → 只掃 `pattern_targets.py` + `pattern_targets_ui.py`
  3. `tests/test_financial_health_ssot.py` 的人名檢查 → 只掃
     `shared/financial_health_thresholds.py`

而 `tests/test_strategy_code_wiring.py` **根本沒有人名黑名單** —— 它管的是
「`策略N（範疇）`括號一致」「`strategy_conclusion()` 第 1 引數是登記代號」
「三個代號都有 caller」。那三處漏網都是**手打的 banner 字串**（不是
`strategy_conclusion()` 呼叫、也沒有全形括號），三條規則一條都踩不到。

第二層原因：那三個黑名單**內容也不全**（都沒有「陳重銘」「Minervini」「MJ」）。

⇒ 本檔補的是**全 repo 掃描**（`src/**` + `shared/**` + `app.py`），並反向
釘住「舊守衛的黑名單必須是本檔 SSOT 的子集」，避免以後又出現「加在 A 檔忘了加 B 檔」。

⚠️ 掃描方式（本 session 已被字串掃描守衛的假紅燈擋過四次，見 STATE.md）：
  - 一律走 **AST**，只看「會被渲染的字串常數」
  - **排除 docstring**（module / class / def 的第一個字串），`#` 註解天然不進 AST
  - 失敗訊息印出 `檔:行` **與該行原文**，讓人一眼看出是真的還是誤判
  - 附**自我驗證誘餌測試**：掃描器抓不到誘餌 = 掃描器自己壞了
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pandas as pd
import pytest

from src.compute.strategy.v4_strategy_engine import V4StrategyEngine

_REPO = Path(__file__).resolve().parents[1]


# ══════════════════════════════════════════════════════════════════════
# A. v4 防守價：已跌破必須有旗標，不可只給一個負數（§1）
# ══════════════════════════════════════════════════════════════════════
def _flat_df(n: int = 30, close: float = 50.0, low: float = 48.0,
             volume: int = 1000) -> pd.DataFrame:
    """全平盤 K 線：無爆量紅K → 走 `近10日低點×0.98` 備援分支。"""
    return pd.DataFrame(
        {
            "close":  [close] * n,
            "open":   [close] * n,
            "low":    [low] * n,
            "volume": [volume] * n,
        },
        index=pd.date_range("2023-01-01", periods=n),
    )


def _breached_df() -> pd.DataFrame:
    """造出「防守價 > 現價」的真實情境（實機 2330 的結構）。

    30 根 K，收盤 100 → 71 逐日下跌：
      - MA20（近 20 根均值 = 80.5）> 現價 71
      - index 20 是一根**爆量紅K**（open 79 / close 80 / low 79，量 ×100），
        其低點 79 也 > 現價 71
    ⇒ `min(80.5, 79) = 79 > 71` ⇒ 已跌破，`risk_pct` 為負。
    """
    n = 30
    close = [100.0 - i for i in range(n)]          # 100 … 71
    open_ = [c + 0.5 for c in close]               # 收黑（close < open）
    low = [c - 1.0 for c in close]
    volume = [1000] * n
    # index 20：爆量紅K（close > open），低點 79 高於最終現價 71
    open_[20] = 79.0
    close[20] = 80.0
    low[20] = 79.0
    volume[20] = 100_000
    return pd.DataFrame(
        {"close": close, "open": open_, "low": low, "volume": volume},
        index=pd.date_range("2023-01-01", periods=n),
    )


def _at_stop_df() -> pd.DataFrame:
    """造出「防守價 == 現價」的邊界：MA20 恰等於現價，且爆量紅K低點更高。

    近 20 根收盤 = 15 根 50 + 一根 60 + 一根 40 + 3 根 50 ⇒ 均值剛好 50，
    最後一根收盤也是 50；index 25 那根爆量紅K（open 55 / close 60 / low 55）
    低點 55 > 50 ⇒ `min(50, 55) = 50` == 現價。
    """
    n = 30
    close = [50.0] * n
    open_ = [50.0] * n
    low = [49.0] * n
    volume = [1000] * n
    close[25], open_[25], low[25], volume[25] = 60.0, 55.0, 55.0, 100_000  # 爆量紅K
    close[26], open_[26], low[26] = 40.0, 45.0, 40.0                       # 對沖回均值
    return pd.DataFrame(
        {"close": close, "open": open_, "low": low, "volume": volume},
        index=pd.date_range("2023-01-01", periods=n),
    )


class TestStopLossBreachFlag:
    def test_breached_sets_flag_and_negative_risk(self):
        """核心回歸：防守價高於現價 ⇒ `is_breached=True` + 訊息明說已跌破。"""
        r = V4StrategyEngine(_breached_df(), {}, 100_000).calculate_stop_loss()
        assert r["stop_loss"] > r["current_price"], "測試資料沒造出跌破情境"
        assert r["is_breached"] is True
        assert r["risk_pct"] < 0, "已跌破時 risk_pct 應為負（帶號，不可被偷偷取絕對值）"
        assert "已跌破" in r["msg"] and "🚨" in r["msg"], r["msg"]
        # 舊訊息把負數包裝成「距現價 -11.3%」，讀起來像「還有距離」
        assert "距現價" not in r["msg"], "已跌破仍用『距現價』措辭 = 誤導"

    def test_normal_case_is_not_breached(self):
        r = V4StrategyEngine(_flat_df(), {}, 100_000).calculate_stop_loss()
        assert r["is_breached"] is False
        assert r["risk_pct"] > 0
        assert "🛡️" in r["msg"]

    def test_price_exactly_at_stop_is_not_breached_but_warns(self):
        """邊界：現價 == 防守價 ⇒ 尚未跌破（risk 0%），但要明說『正好觸及』。"""
        r = V4StrategyEngine(_at_stop_df(), {}, 100_000).calculate_stop_loss()
        assert r["stop_loss"] == pytest.approx(r["current_price"])
        assert r["is_breached"] is False, "『正好觸及』不是『已跌破』（跌破 = 嚴格低於）"
        assert r["risk_pct"] == pytest.approx(0.0, abs=0.05)
        assert "正好觸及" in r["msg"], r["msg"]

    def test_insufficient_data_returns_none_not_false(self):
        """§1：資料不足 ⇒ `is_breached=None`（不知道），**不是** False（沒跌破）。"""
        r = V4StrategyEngine(_flat_df(4), {}, 100_000).calculate_stop_loss()
        assert r["stop_loss"] is None
        assert r["is_breached"] is None
        assert r["risk_pct"] is None, "算不出來卻回 0 = 造假（原碼就是這樣寫的）"

    @pytest.mark.parametrize("bad_close", [0.0, -3.0, float("nan")])
    def test_invalid_price_fails_loud_instead_of_zero(self, bad_close):
        """§1：現價 0 / 負 / NaN ⇒ 全部回 None + 明說無效，不填 0 假裝正常。

        NaN 這條特別重要：`__init__` 的 `fillna(0)` 會把全空的 close 補成 0，
        舊碼 `sl_pct = ... if current_price > 0 else 0` 剛好把它變成「風險 0%」。
        """
        df = _flat_df()
        df["close"] = bad_close
        df["low"] = bad_close
        r = V4StrategyEngine(df, {}, 100_000).calculate_stop_loss()
        assert r["is_breached"] is None
        assert r["risk_pct"] is None
        assert r["stop_loss"] is None
        assert "無效" in r["msg"], r["msg"]

    def test_generate_report_carries_the_flag(self):
        """下游只拿得到 report ⇒ 旗標必須跟著整合輸出走。"""
        rep = V4StrategyEngine(_breached_df(), {"vix": 15}, 100_000).generate_report()
        assert rep["stop_loss"]["is_breached"] is True


# ══════════════════════════════════════════════════════════════════════
# AST 掃描工具（本檔自足，不 import 其他測試模組以免耦合）
# ══════════════════════════════════════════════════════════════════════
_SCAN_ROOTS = (_REPO / "src", _REPO / "shared")
_SCAN_EXTRA = (_REPO / "app.py",)


def _iter_scanned_files() -> list[Path]:
    out: list[Path] = []
    for root in _SCAN_ROOTS:
        out.extend(sorted(root.rglob("*.py")))
    out.extend(p for p in _SCAN_EXTRA if p.exists())
    return out


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - 不該發生
        return None


def _docstring_node_ids(tree: ast.Module) -> set[int]:
    """module / class / def 的 docstring 常數節點 id。

    docstring 是寫給開發者看的（例如「原名 `render_caisen_for_ticker`」這種
    遷移紀錄），**不會出現在畫面上**；掃進去只會製造假紅燈。
    `#` 註解不進 AST，天然被排除。
    """
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


def _render_strings(path: Path) -> list[tuple[int, str]]:
    """回 `[(lineno, 字串值)]` —— 所有「可能被渲染」的字串常數（排除 docstring）。

    f-string 會被拆成 `JoinedStr` 的字面片段，這正是要的：
    `f'🎓 {STRATEGY_VALUATION} · 毛利率'` 只留下不含人名的片段，
    而 `'🎓 陳重銘 · 毛利率'` 這種**手打**的才會整段留下來。
    """
    tree = _parse(path)
    if tree is None:
        return []
    skip = _docstring_node_ids(tree)
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in skip]


def _source_line(path: Path, lineno: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):  # pragma: no cover
        return "<讀檔失敗>"
    return lines[lineno - 1].strip() if 0 < lineno <= len(lines) else "<行號越界>"


def _referenced_names(path: Path) -> set[str]:
    """真的被當識別字用的名稱（AST `Name`）—— docstring / 註解提到不算。"""
    tree = _parse(path)
    if tree is None:
        return set()
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


# ══════════════════════════════════════════════════════════════════════
# B. 去識別化：全 repo 掃描（SSOT 黑名單）
# ══════════════════════════════════════════════════════════════════════
# ⚠️ 這是**守衛黑名單**，刻意保留的檢查清單，不是去識別化殘留 ——
#    全 repo 掃人名時請跳過本區塊（同 test_ui_widgets / test_pattern_targets_ui_mounted 慣例）。
#
# 來源：既有三個檔案級守衛的黑名單聯集 ＋ v19.180 B2-a 實機補抓的三個
#      （「陳重銘」「Minervini」「MJ」——前兩者是人名，MJ 是人名縮寫識別碼）。
_BANNED_PERSON_TOKENS: tuple[str, ...] = (
    # 中文人名 / 稱謂
    "陳重銘", "林明樟", "明樟", "孫慶龍", "郭俊宏", "蔡森", "春哥",
    "弘爺", "宏爺", "妮可", "朱家泓",
    "老師", "大師", "師父",
    # 課程 / 品牌（等同人名指涉）
    "超級數字力",
    # 英文人名
    "Minervini",
    # 羅馬拼音識別碼（舊檔名 caisen_*）
    "caisen",
)

# 「MJ」單獨用 regex（英數詞界），避免誤傷 `MJPEG` 這類字串。
#
# ⚠️ **刻意大小寫敏感、刻意只抓大寫 `MJ`**（避免第 5 次假紅燈）：
# 小寫 `mj_*` 目前還有一批**刻意保留**的過渡期 alias / 相容路徑，它們
# **不會出現在畫面上**，把它們掃紅只會逼人為了消紅燈刪掉相容層：
#   - `src/compute/health/fin_trend_score.py` 的 `"mj_subscore"` / `"mj_detail"`
#     / `"mj_sub"` dict key（與新 key 同值並存，v19.174 註明為過渡期）
#   - `src/compute/health/fin_snapshot_io.py:31` `Path("data_cache/mj_snapshots")`
#     （讀舊快照目錄的相容路徑）
#   - `src/ui/tabs/chip_radar.py` 的區域變數 `_mj`（「大戶」縮寫，與人名無關）
# 待 caller 全面改吃新 key、舊快照目錄清空後，再收斂這些殘留。
_MJ_RE = re.compile(r"(?<![0-9A-Za-z])MJ(?![0-9A-Za-z])")


def _scan_banned(path: Path) -> list[str]:
    """回本檔的違規清單（每筆含 `檔:行` + 該行原文 + 命中字樣）。"""
    rel = path.relative_to(_REPO).as_posix()
    hits: list[str] = []
    for lineno, text in _render_strings(path):
        found = [tok for tok in _BANNED_PERSON_TOKENS if tok.lower() in text.lower()]
        if _MJ_RE.search(text):
            found.append("MJ")
        if found:
            hits.append(f"{rel}:{lineno} 命中 {found} → {_source_line(path, lineno)!r}")
    return hits


class TestNoPersonNameRepoWide:
    """全 repo 可渲染字串不得出現人名／人名縮寫識別碼。"""

    @pytest.fixture(scope="class")
    def violations(self) -> list[str]:
        out: list[str] = []
        for py in _iter_scanned_files():
            out.extend(_scan_banned(py))
        return out

    def test_scan_actually_covers_the_repo(self):
        """掃不到檔案 = 掃描器壞了，後面的斷言會假性通過。"""
        files = _iter_scanned_files()
        assert len(files) >= 100, f"只掃到 {len(files)} 個 .py，掃描範圍可能失效"

    def test_scan_covers_the_three_previously_missed_files(self):
        """釘住「範圍」這個真因：三處漏網所在的檔必須在掃描清單內。

        既有守衛全是檔案級（只掃 3 個檔），這三個檔一個都沒被涵蓋 ——
        這條測試就是那件事的直接反面。
        """
        scanned = {p.relative_to(_REPO).as_posix() for p in _iter_scanned_files()}
        for rel in ("src/ui/tabs/stock_sections/section_strategy_conclusion.py",
                    "src/ui/tabs/stock_sections/section_vcp_bollinger.py",
                    "shared/stock_buckets.py"):
            assert rel in scanned, f"{rel} 不在掃描範圍（就是它讓 v19.174 漏網）"

    def test_no_banned_token_in_any_render_string(self, violations):
        assert not violations, (
            "以下**可渲染字串**仍含人名／人名縮寫（docstring、# 註解已排除）：\n"
            + "\n".join(violations))

    def test_scan_would_catch_a_handwritten_name(self, tmp_path):
        """自我驗證①：手打人名要抓得到。"""
        fake = tmp_path / "fake_ui.py"
        fake.write_text("X = '🎓 陳重銘 · 毛利率'\n", encoding="utf-8")
        hits = [t for _, t in _render_strings(fake)
                if any(b in t for b in _BANNED_PERSON_TOKENS)]
        assert hits == ["🎓 陳重銘 · 毛利率"]

    def test_scan_ignores_docstring_and_comment(self, tmp_path):
        """自我驗證②：docstring／註解提到人名**不算**違規（否則遷移紀錄全紅）。"""
        fake = tmp_path / "fake_doc.py"
        fake.write_text(
            '"""說明：原名 Mark Minervini 的 VCP，v19.174 已改名。"""\n'
            "# 陳重銘 · 毛利率（歷史註記）\n"
            "X = 1\n",
            encoding="utf-8")
        assert not [t for _, t in _render_strings(fake)
                    if any(b in t for b in _BANNED_PERSON_TOKENS)]

    def test_scan_ignores_fstring_with_constant(self, tmp_path):
        """自我驗證③：改用常數後的寫法不得被誤判（f-string 只留無害片段）。"""
        fake = tmp_path / "fake_fixed.py"
        fake.write_text(
            "STRATEGY_VALUATION = '策略1'\n"
            "X = f'🎓 {STRATEGY_VALUATION} · 毛利率'\n",
            encoding="utf-8")
        assert not [t for _, t in _render_strings(fake)
                    if any(b in t for b in _BANNED_PERSON_TOKENS)]

    def test_mj_regex_boundaries(self):
        """`MJ` 用英數詞界，抓得到舊識別碼、抓不到 `MJPEG` 這類無關字。"""
        assert _MJ_RE.search("展開下方體檢表後評定 MJ 等級"), "抓不到原始 bug 字樣"
        assert _MJ_RE.search("MJ_CASH_RATIO_SAFE_PCT"), "舊常數名出現在渲染字串也該抓"
        assert _MJ_RE.search("MJPEG 影像") is None
        assert _MJ_RE.search("EMJI") is None
        assert _MJ_RE.search("財報體檢等級") is None


class TestOldGuardBlacklistsAreSubsets:
    """守衛的守衛：既有檔案級黑名單必須是本檔 SSOT 的子集。

    第二層真因是「黑名單各寫各的」—— 三個守衛各有一份 `_BANNED`，
    誰都沒有「陳重銘 / Minervini / MJ」。這條讓「只加在其中一份」當場紅。
    """

    _OLD_GUARDS = (
        "tests/test_ui_widgets.py",
        "tests/test_pattern_targets_ui_mounted.py",
    )

    @staticmethod
    def _banned_tuples(path: Path) -> list[list[str]]:
        tree = _parse(path)
        assert tree is not None, f"{path} 解析失敗"
        out: list[list[str]] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name) and t.id == "_BANNED"
                       for t in node.targets):
                continue
            if isinstance(node.value, (ast.Tuple, ast.List)):
                out.append([e.value for e in node.value.elts
                            if isinstance(e, ast.Constant)
                            and isinstance(e.value, str)])
        return out

    @pytest.mark.parametrize("rel", _OLD_GUARDS)
    def test_old_blacklist_is_covered(self, rel):
        path = _REPO / rel
        tuples = self._banned_tuples(path)
        assert tuples, f"{rel} 找不到 `_BANNED` 清單（守衛被移除或改名？）"
        ssot = {t.lower() for t in _BANNED_PERSON_TOKENS}
        for names in tuples:
            missing = [n for n in names if n.lower() not in ssot]
            assert not missing, (
                f"{rel} 的 _BANNED 有本檔 SSOT 沒收錄的名字 {missing} —— "
                f"請補進 test_b2a_breach_and_naming._BANNED_PERSON_TOKENS，"
                f"否則全 repo 掃描永遠掃不到它")


class TestThreeLeftoversFixed:
    """三處漏網的逐點回歸（直接釘住畫面文字與接線方式）。"""

    def test_gross_margin_banner_uses_strategy_constant(self):
        from src.ui.render.ui_widgets import STRATEGY_VALUATION
        path = _REPO / "src/ui/tabs/stock_sections/section_strategy_conclusion.py"
        assert "STRATEGY_VALUATION" in _referenced_names(path), (
            "毛利率／月營收 banner 未真的引用 STRATEGY_VALUATION（只在註解提到不算）")
        texts = [t for _, t in _render_strings(path)]
        assert any("· 毛利率" in t for t in texts), "毛利率 banner 不見了？"
        assert STRATEGY_VALUATION == "策略1"  # 對帳 SSOT 值，避免代號被偷改

    def test_vcp_card_title_uses_strategy_constant(self):
        from src.ui.render.ui_widgets import STRATEGY_TECHNICAL
        path = _REPO / "src/ui/tabs/stock_sections/section_vcp_bollinger.py"
        assert "STRATEGY_TECHNICAL" in _referenced_names(path)
        texts = [t for _, t in _render_strings(path)]
        # 改成 f-string 後，字面片段只剩 `**VCP [` / `]**`
        assert any(t.startswith("**VCP [") for t in texts), "VCP 卡標題不見了？"
        assert not any("Minervini" in t for t in texts)
        assert STRATEGY_TECHNICAL == "策略3"

    def test_financials_bucket_headline_renamed(self):
        from shared.stock_buckets import compute_stock_section_levels
        out = compute_stock_section_levels()
        head = out["financials"]["headline"]
        assert "財報體檢等級" in head, head
        assert _MJ_RE.search(head) is None, f"仍殘留 MJ：{head!r}"
        # 語彙必須與 shared/financial_health_thresholds.py（FH = Financial Health）一致
        import shared.financial_health_thresholds as _fh
        assert "財報體檢" in (_fh.__doc__ or ""), "門檻模組用語與桶結論用語不一致"
        # on-demand 桶仍必須是 gray（§1 不偽造未展開的東西）
        assert out["financials"]["level"] == "gray"


# ══════════════════════════════════════════════════════════════════════
# C. UI 接線：防守價卡必須讀旗標，而不是自己印負數
# ══════════════════════════════════════════════════════════════════════
class TestStopLossCardWiring:
    _CARD = _REPO / "src/ui/tabs/stock_sections/section_health_score.py"

    def test_card_reads_is_breached_flag(self):
        texts = [t for _, t in _render_strings(self._CARD)]
        assert "is_breached" in texts, (
            "防守價卡沒有讀 `is_breached` —— 又會退回『風險 -1.1%』的寫法")

    def test_card_has_breach_wording(self):
        texts = [t for _, t in _render_strings(self._CARD)]
        assert any("已跌破" in t for t in texts), "跌破時沒有明確的『已跌破』字樣"
        assert any("依規則無條件停損" in t for t in texts)

    def test_card_no_longer_labels_negative_number_as_risk(self):
        """舊寫法 `f'... 風險 {_sl["risk_pct"]}%'` 的字面片段是 `'風險 '`。"""
        texts = [t for _, t in _render_strings(self._CARD)]
        assert not any(t.strip() == "風險" or t.endswith("風險 ") for t in texts), (
            "仍有『風險 ' + 數字』的無條件渲染 —— 負值會被讀成『風險很小』")


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
