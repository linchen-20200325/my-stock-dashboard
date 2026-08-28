# -*- coding: utf-8 -*-
"""tests/test_deprecation_honesty.py — 「註解說死了、程式還活著」的守衛(2026-08-27)。

═══ 為什麼需要這個守衛(不是儀式性測試)═════════════════════════════════
2026-08-27 盤點在本 repo 抓到兩處**方向相反於直覺**的陷阱:

  1. `src/services/market_strategy.py::market_score` 註解白紙黑字寫
     「舊版評分（**已棄用**，僅保留相容性）」—— 但 `get_market_assessment()`
     **每次都呼叫它**。照註解刪 → `{**old_result, **regime_result}` 合併少一半欄位
     → 大盤格局判定壞掉。
  2. `macro_helpers.detect_mk_golden_inflection` 標 `DEPRECATED，勿用於新程式碼`,
     而 `section_long_term.py` 還在 import 它。

兩者都不是「有沒有測到」的問題 —— 程式**跑得好好的**,壞的是**文件**。
下一個做垃圾清理的人(含未來的 AI)照著假註解動手,才會出事。
所以守的東西不是行為,而是「**標記與實際 caller 狀態不得矛盾**」。

⚠️ 反向陷阱也一併防:`ui_widgets.BREADTH_DEPRECATED_TITLES` 的**名字**含
`DEPRECATED`,本體卻是守衛測試的黑名單資料源 —— 本測試只讀**註解 / docstring 的
標記文字**,不看符號名,故不會誤傷它(見 `test_name_containing_deprecated_is_not_flagged`)。

═══ 判定方法(刻意只認「明確的引用」,不做名稱比對)══════════════════════
盤點組的掃描是「identifier 詞頻反查」,會把**同名參數**當成 caller
(實例:`shared/regime_arbiter.py` 有個參數就叫 `market_score`)。
本測試改認三種**不會誤判**的引用:
  (a) `from X import S` / `from X import S as Y`  — import 的意圖明確;
  (b) `obj.S` 屬性存取;
  (c) 定義檔**自己**檔內的 `Name` 使用(自我呼叫)。
其他檔案裡的**裸 `Name`**一律不算 —— 在別的檔案裡要用到 S 必須先 import,
而 import 已由 (a) 抓到;裸 Name 只會是區域變數 / 參數。
"""
from __future__ import annotations

import ast
import collections
import pathlib
import re

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_SCAN_DIRS = ("src", "shared", "scripts", "infra", "tools", "mcp_server")
#: 掃描排除:快取、虛擬環境殘骸、暫存工作區。
#: ⚠️ 2026-08-28:原本首項是 `"stock_etf_dashboard"`(獨立子 app)。該目錄已依 user
#: 裁示整個刪除,字串留著就會變成一個指向不存在目標的排除條件 —— 下一個讀這行的人
#: 會以為 repo 裡還有那個子 app。故一併移除。
#: 附帶事實(查證後才敢寫):這一項**在刪除前就已經是空轉的** —— `_SCAN_DIRS` 只走
#: src / shared / scripts / infra / tools / mcp_server,`stock_etf_dashboard/` 是
#: 頂層目錄、從來不在任一 scan 根底下,故該字串從加入起就沒有濾掉過任何一個檔案。
#: 移除它因此**不改變本測試掃描到的檔案集合**(掃描集合的變化全部來自目錄本身被刪)。
_SKIP_PARTS = ("__pycache__", ".git", "scratchpad", "wt-")

#: 「這東西已經廢棄」的**強標記**。刻意不收「舊版」「legacy」——
#: 本 repo 有大量「舊版寫錯,已修」的歷史說明句,收進來會全是雜訊。
_DEPRECATION_MARKER = re.compile(
    r"DEPRECATED|deprecated|已棄用|已廢棄|已退役|不再使用|勿用於新程式碼|不再被呼叫",
    re.IGNORECASE,
)

#: 已知且**有意識保留**的矛盾。每一筆都必須寫清楚:誰該修、為什麼本輪沒修。
#: ⚠️ 這張表是「暫緩」不是「豁免」—— 新增一筆等於欠一筆技術債,不是取得許可。
_ACCEPTED: dict[tuple[str, str], str] = {
    ("src/ui/render/etf_render.py", "MACRO_ALLOC"): (
        "2026-08-27 資料工程組查得:本項註解自稱『保留給尚未遷移的 caller "
        "(etf_tab_ai._generate_report 的 prompt 文案) 作 fallback』,但該 caller 已在"
        "**同一個版本 v19.170** 被移除(etf_tab_ai.py:10/24/170 三處註解自陳不再引用)。"
        "→ 這是與 market_score 相反方向的謊:註解**留住**了一個其實可以刪的東西。"
        "現存唯一引用是 etf_dashboard.py 的 `# noqa: F401` re-export shim。"
        "本輪未修:etf_render.py / etf_dashboard.py 不在本次派工的檔案邊界內。"
    ),
    ("src/ui/render/etf_render.py", "MACRO_DESC"): (
        "同 MACRO_ALLOC。註解另寫『唯一剩下的引用是 etf_dashboard.py:40』—— "
        "實際行號已漂移(現為 etf_dashboard.py 的 re-export 區塊),屬行號腐爛。"
        "本輪未修:不在檔案邊界內。"
    ),
    ("src/ui/render/etf_render.py", "_PERIOD_MAP"): (
        "同上。註解指的 shim 行號同樣已漂移;且此名的**語意已變**"
        "(從『計算區間』變成『下載窗』),留著本身就是誤導源。本輪未修:不在檔案邊界內。"
    ),
    ("src/compute/etf/portfolio_coherence.py", "classify_core_satellite"): (
        "docstring 寫『ETF 投組頁不再使用本函式』—— 這句對**投組頁**成立(已改用 "
        "portfolio_gates.classify_portfolio_role),但同檔的 `assess_core_satellite` "
        "仍呼叫它。兩者在 production 都是 0 caller(僅測試),故標記沒有說謊、"
        "只是沒把同檔 caller 講出來。屬『可能死』,刪除需另派獨立複驗。"
        "本輪未修:不在檔案邊界內,且 §-1 無 bug 觸發不主動動工。"
    ),
}


def _py_files():
    for d in _SCAN_DIRS:
        base = _REPO / d
        if not base.exists():
            continue
        for f in base.rglob("*.py"):
            if any(s in str(f) for s in _SKIP_PARTS):
                continue
            yield f
    app = _REPO / "app.py"
    if app.exists():
        yield app


def _rel(p: pathlib.Path) -> str:
    return p.relative_to(_REPO).as_posix()


def _preceding_comment_block(lines, start_idx: int) -> str:
    """往上收「緊貼定義」的連續註解區塊(允許中間有空行,但空行後不再往上跨)。"""
    out, i = [], start_idx - 1
    while i >= 0:
        stripped = lines[i].lstrip()
        if stripped.startswith("#"):
            out.append(lines[i])
        elif not stripped:
            if out:
                break
        else:
            break
        i -= 1
    return "\n".join(out)


def _collect_marked_symbols():
    """→ [(rel_path, symbol, lineno, marker)]:帶棄用標記的 top-level 符號。"""
    found = []
    for f in _py_files():
        try:
            txt = f.read_text(encoding="utf-8")
        except OSError:                                    # pragma: no cover
            continue
        try:
            tree = ast.parse(txt)
        except SyntaxError:                                # pragma: no cover
            continue
        lines = txt.splitlines()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names = [node.name]
                doc = ast.get_docstring(node) or ""
            elif isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                doc = ""
            else:
                continue
            if not names:
                continue
            start = node.lineno - 1
            if getattr(node, "decorator_list", None):
                start = min(d.lineno for d in node.decorator_list) - 1
            blob = _preceding_comment_block(lines, start) + "\n" + doc
            m = _DEPRECATION_MARKER.search(blob)
            if m:
                for n in names:
                    found.append((_rel(f), n, node.lineno, m.group(0)))
    return found


def _collect_references():
    """→ {symbol: [(rel_path, lineno, kind)]}:只收 import / attribute / 同檔 Name。"""
    refs = collections.defaultdict(list)
    for f in _py_files():
        rel = _rel(f)
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):                     # pragma: no cover
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for a in node.names:
                    refs[a.name].append((rel, node.lineno, "import"))
            elif isinstance(node, ast.Attribute):
                refs[node.attr].append((rel, node.lineno, "attribute"))
            elif isinstance(node, ast.Name):
                refs[node.id].append((rel, node.lineno, "name"))
    return refs


def _production_callers(symbol: str, def_file: str, def_line: int, refs) -> list:
    out = []
    for rel, lineno, kind in refs.get(symbol, []):
        if kind == "name" and rel != def_file:
            continue                      # 別檔的裸 Name:必為區域變數/參數,不算引用
        if rel == def_file and abs(lineno - def_line) <= 3:
            continue                      # 定義自身
        out.append((rel, lineno, kind))
    return sorted(set(out))


# ══════════════════════════════════════════════════════════════════════
# 主守衛
# ══════════════════════════════════════════════════════════════════════
def test_no_deprecated_marker_on_symbol_that_still_has_callers():
    """標了「已棄用 / DEPRECATED」的符號,不得還有 production caller。

    紅燈的兩種正解(**不是**把符號加進 `_ACCEPTED` 了事):
      - 標記說錯了 → 改註解,寫出它現在的真實角色與退役條件(market_score 走這條);
      - 標記說對了、只是沒遷完 → 把 caller 遷到新 API(section_long_term 走這條)。
    """
    refs = _collect_references()
    violations = []
    for rel, sym, line, marker in _collect_marked_symbols():
        if (rel, sym) in _ACCEPTED:
            continue
        callers = _production_callers(sym, rel, line, refs)
        if callers:
            violations.append((rel, sym, line, marker, callers))

    assert not violations, "\n".join(
        [
            "以下符號帶棄用標記,但仍有 production caller —— 註解與程式狀態矛盾:",
            *[
                f"  {r}:{ln}  {s}  (標記 {mk!r})\n"
                + "\n".join(f"      caller: {c[0]}:{c[1]} [{c[2]}]" for c in cs)
                for r, s, ln, mk, cs in violations
            ],
        ]
    )


def test_accepted_table_has_no_stale_entries():
    """`_ACCEPTED` 只准放**真的還在矛盾**的項目。

    修好之後忘了把白名單那筆拿掉,白名單本身就會變成下一個說謊的文件 ——
    這正是本測試要防的病。
    """
    refs = _collect_references()
    marked = {(r, s): (ln, mk) for r, s, ln, mk in _collect_marked_symbols()}
    stale = []
    for key in _ACCEPTED:
        rel, sym = key
        if key not in marked:
            stale.append(f"  {rel}::{sym} —— 已經不帶棄用標記了,請把這筆從 _ACCEPTED 移除")
            continue
        line, _ = marked[key]
        if not _production_callers(sym, rel, line, refs):
            stale.append(f"  {rel}::{sym} —— 已經沒有 caller 了(矛盾解除),請移除這筆")
    assert not stale, "_ACCEPTED 有過期項目:\n" + "\n".join(stale)


def test_name_containing_deprecated_is_not_flagged():
    """反向陷阱:符號**名字**含 DEPRECATED ≠ 該符號已廢棄。

    `ui_widgets.BREADTH_DEPRECATED_TITLES` 是守衛測試的黑名單資料源,
    活得好好的。本測試釘住「只看標記文字、不看符號名」這個判定方式 ——
    若日後有人把判定改成比對符號名,這條會轉紅。
    """
    marked = {(r, s) for r, s, _, _ in _collect_marked_symbols()}
    assert ("src/ui/render/ui_widgets.py", "BREADTH_DEPRECATED_TITLES") not in marked


# ══════════════════════════════════════════════════════════════════════
# market_score 專屬:防「連函式帶呼叫一起清掉」
# ══════════════════════════════════════════════════════════════════════
#
# 上面的通用守衛擋不住這一種:GC 的人把假註解**和**函式**和**呼叫行一起刪乾淨,
# 標記消失 → 通用守衛無話可說,但 `status` / `confidence` 兩個 key 已經靜默不見。
# 故另立契約測試,釘住「這兩個 key 必須來自 market_score」。
def _synthetic_index_df():
    import numpy as np
    import pandas as pd

    n = 300
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    return pd.DataFrame(
        {"close": np.linspace(15000.0, 18000.0, n), "volume": np.full(n, 1e9)},
        index=idx,
    )


def test_market_score_is_reached_by_get_market_assessment(monkeypatch):
    """`get_market_assessment` 必須真的呼叫 `market_score`,且其輸出必須進到結果裡。

    做法:把 `market_score` 換成回傳哨兵值的假函式 —— 哨兵沒出現在結果 dict,
    代表呼叫鏈被剪斷了(不管是刪了呼叫、還是換掉合併方式)。
    """
    from src.services import market_strategy as MS

    called = {}

    def _fake(index_price, ma200, foreign_buy, volume, avg_volume=1000):
        called["hit"] = True
        return {"status": "__SENTINEL__", "confidence": -12345,
                "score": 0, "max_score": 0, "signals": []}

    monkeypatch.setattr(MS, "market_score", _fake)
    res = MS.get_market_assessment(df_index=_synthetic_index_df(), foreign_net=1e9)

    assert called.get("hit"), "get_market_assessment 沒有呼叫 market_score —— 呼叫鏈被剪斷"
    assert res is not None
    assert res.get("status") == "__SENTINEL__", (
        "market_score 的 `status` 沒進到結果 —— 合併被改掉或欄位被蓋掉")
    assert res.get("confidence") == -12345, (
        "market_score 的 `confidence` 沒進到結果")


def test_market_assessment_still_exposes_status_and_confidence():
    """真實路徑下 `status` / `confidence` 必須存在(它們是 market_score 的獨佔輸出)。"""
    from src.services.market_strategy import get_market_assessment

    res = get_market_assessment(df_index=_synthetic_index_df(), foreign_net=1e9)
    assert res is not None, "合成資料應算得出評估結果"
    for k in ("status", "confidence"):
        assert k in res, (
            f"`{k}` 從 get_market_assessment 的結果消失 —— "
            f"若這是有意識的退役,請同步更新 market_score 定義處的退役條件註解")
    assert isinstance(res["status"], str) and res["status"]
    assert isinstance(res["confidence"], (int, float))


# ══════════════════════════════════════════════════════════════════════
# detect_mk_golden_inflection 專屬:alias 必須維持「真的沒人用」
# ══════════════════════════════════════════════════════════════════════
def test_deprecated_alias_has_no_production_caller():
    """`detect_mk_golden_inflection` 是 DEPRECATED alias —— production 端不得再 import。

    2026-08-27 把最後一個 caller(`section_long_term.py`)遷到正名後的
    `detect_cpi_fed_double_top`。測試檔仍可用舊名(`test_macro_helpers.py`
    刻意兼測 alias 未斷),那是**測試**不是 production。
    """
    refs = _collect_references()
    callers = _production_callers(
        "detect_mk_golden_inflection",
        "src/compute/macro/macro_helpers.py",
        _alias_lineno(),
        refs,
    )
    assert not callers, (
        "DEPRECATED alias 又出現 production caller:\n"
        + "\n".join(f"  {c[0]}:{c[1]} [{c[2]}]" for c in callers)
        + "\n請改用 `detect_cpi_fed_double_top`。"
    )


def _alias_lineno() -> int:
    p = _REPO / "src/compute/macro/macro_helpers.py"
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("detect_mk_golden_inflection ="):
            return i
    pytest.fail("找不到 detect_mk_golden_inflection alias 定義行")
    return -1                                              # pragma: no cover
