"""tests/test_p04_hold_view.py — 頁 4 守衛（IA v2「💼 我的持股」）。

⚠️ **2026-09-07 FE-15 更新**：戰情室 ①③④⑤ ＋ ⑥ 的核心／衛星 ＋ 葉2 的持股列預覽
**已接線**（新增 L3 `services/holdings_service.py`）。原本「這幾張卡恆為 unwired」
那幾條斷言**不是被放寬，是換成了新的事實**：接線的改成驗 live / empty / failed
三態（`TestTheWarroomIsWiredNow`），仍未接線的維持 unwired 但驗**新的**「去哪補」。
另補一整類 `TestHoldingsServiceIsReadOnly` —— 頁面那一類只證明「這一頁沒有寫入的路」，
**它呼叫的 L3 自己會不會寫不在射程內**，那個洞由新的一類補。

守的是 `src/ui/views/page_hold.py`。風格與粒度沿用
`tests/test_p03_inspect_view.py`：**一條測試對應一個具體的說謊方式**，
不是補覆蓋率。對應表：

  · `TestReadOnly`                ← **本頁獨有、也是最重要的一類。**
    前三頁碰的是公開市場資料；本頁的輸入是**使用者自己的 Google Sheets 帳本**。
    以 AST **白名單**釘住「這一頁可以呼叫哪幾支 L3」，再以**黑名單**釘住整個
    gsheet 寫入面一個都不准出現，並釘住「本層的資料結構裡沒有 sheet id」。
  · `TestThreeEmptiesNeverMix`    ← 「還沒綁」／「綁了但裡面是空的」／「上游掛了」
    三件事被畫成同一種。**空的組合不是故障** —— 一個剛註冊的使用者不該看到紅色。
  · `TestRequestedIsNotDerivedFromData` ← gate 從資料反推（頁 1 的恆真式事故）。
    做法與頁 2／3 相同：**白名單 AST 斷言**，不是一條越加越長的黑名單。
  · `TestNothingIsCalledBeforeYouAsk` ← 「沒按就不取數」只是 docstring 宣稱。
    把全部下游 L3 下毒（毒藥**不繼承 `Exception`**，本頁的 try/except 吞不掉），
    再跑一次每一支 loader —— 碰到就當場紅。**含本頁獨有的第二個 gate**：
    按了、但選了「只讀市場端」時，Google 那一支**一次都不准被碰到**。
  · `TestUnwiredStaysUnwired`     ← **剩下八張**未接線卡被「按一次就變好」、三要素
    留空、或共用同一句「去哪補」（那會讓「補哪一層才會好」這個資訊消失）。
    名單改成**從真正畫出來的卡裡挑 unwired**，不再手抄 —— 手抄的名單在
    「某張卡不小心變回 unwired」時不會有人發現。另加一條：**沒有任何一張卡
    可以再怪「缺 L3 holdings loader」**（那句話本批之後是假的）。
  · `TestTheWarroomIsWiredNow`    ← 接線之後才可能出現的說謊方式：
    「你沒有持股」／「還沒按」／「你選了不讀 Google」／「Google 掛了」被畫成同一種
    —— 對一個新使用者，「你沒有持股」是**每天都會看到**的正常狀態。
    含本批最重要的一條：**換入候選一定帶 `exclude=你已持有的代號`**，
    少了它畫面會叫你買你已經有的東西。
  · `TestTheDeepAnalysisIsWiredNow` ← **FE-19 新增。** ⑥ 的壓力測試 / VaR /
    配息現金流接線之後才可能出現的說謊方式：一格掛掉把另外兩格一起染紅、
    「近一年真的沒配息」與「算不出來」被畫成同一句、樣本三天的 VaR 被當成結果、
    Beta 是估的卻不說、**張→股的乘法跑到畫面層**（§4.1 漏乘 = 1000 倍低估）。
    以及本批最容易吞掉的但書：**配息現金流不含綜所稅**。
  · `TestPortfolioDeepServiceIsReadOnly` ← **FE-19 新增。** 那一支新 L3 自己的
    唯讀守衛：寫入面識別字為零、**連讀都不准碰 gsheet**（持股由呼叫端餵）、
    不自建快取、張→股的 1000 一律取 L0 SSOT 且**只准有一個乘法點**、
    配息一律 `marginal_rate=None`、三支入口對垃圾輸入都不 raise。
  · `TestHoldingsServiceIsReadOnly` ← 新增的那一支 L3 自己的唯讀守衛：
    寫入面識別字為零、只准碰 gsheet 讀取面的白名單、**每一次讀都顯式帶
    `sheet_id=`**（傳 `None` 會讓快取鍵恆為空 → 換 Sheet 後拿到上一本的資料）、
    投資組合那半 fail loud / 觀察清單那半不得靜默吞掉。
  · `TestScaleDisclosureComesFromL0` ← 線框 ② 的 degraded **不是寫死的**：
    它讀 L0 `station_specs` 的 `discriminative` 旗標，旗標翻面它就跟著翻面。
  · `TestFormStructure`           ← 線框 F11 ＋ 鐵律 2：本頁**沒有自己的 form**，
    直接用共用層 `_ui_kit.single_submit_form()`；全頁 0 顆裸 `st.button`。
  · `TestFormRunsBeforeItsConsumers` ← 表單在**葉2**、gate 被**葉1**消費。
    執行順序寫反 → 按了鈕、戰情室卻還是「尚未執行」，而且不會再自動 rerun。
  · `TestThreeColumnGrid`         ← 鐵律 1：⑥ 的六個區塊是 3 欄 × 2 排，不是六欄。
  · `TestNoHardcodedPositionPct`  ← 本頁最容易踩的那一條（整頁都在講持股比例）。
    **直接複用 repo 既有守門測試的 regex 與過濾器**，不另立第二把尺。
  · `test_page_mounts_clean`（slow）← 這一頁真的畫得出來，不是半截死頁。

⚠️ **這些是護欄，不是證明**（同 `tests/test_ui_state_model.py` /
`tests/test_p01_today_view.py` / `test_p02_find_view.py` / `test_p03_inspect_view.py`
的自陳）：釘住的是「已知的那幾種說謊方式不會再回來」，**不是**「這一頁不會再說謊」。
全綠不等於合規。特別是 `TestReadOnly`：它證明的是**本檔的靜態文字裡沒有寫入呼叫**，
**不是**「執行時絕不會寫到任何東西」—— 後者取決於它呼叫的那四支 L3 自己的行為，
那不在本測試的射程內（見 `TestReadOnly` 的 docstring）。
"""
from __future__ import annotations

import ast
import pathlib
import sys

import pytest

from shared.station_specs import KEY_STOCK_TREND, SPECS_BY_KEY
from shared.ui_state import (
    UI_DEGRADED,
    UI_EMPTY,
    UI_FAILED,
    UI_IDLE,
    UI_LIVE,
    UI_UNWIRED,
)
from src.ui.tabs.tab_today import Note
from src.ui.views import page_hold as P

_VIEW = pathlib.Path(P.__file__)


def _tree() -> ast.Module:
    return ast.parse(_VIEW.read_text(encoding="utf-8"))


def _src() -> str:
    return _VIEW.read_text(encoding="utf-8")


def _req(*, submitted: bool = True, mode: str = P.SCOPE_WITH_BINDING):
    return P.HoldRequest(submitted=submitted, mode=mode)


def _note_triple(note: Note | None) -> tuple[str, str, str]:
    assert note is not None, "非 live 的卡一定要有 Note（鐵律 4）"
    return (note.now, note.why, note.where)


def _binding(**kw) -> P.BindingReadout:
    kw.setdefault("requested", True)
    kw.setdefault("submitted", True)
    return P.BindingReadout(**kw)


# ── ⑥ 組合深度分析的假 readout（FE-19）───────────────────────────────
#: ⚠️ **用真的 dataclass，不用 `SimpleNamespace`**：卡片讀的是
#: `computed` / `partial` / `window_squeezed` / `has_payouts` 這些**衍生屬性**，
#: 手捏一個假物件會把「L3 契約改了、UI 沒跟上」這一整類 bug 測不出來。
def _stress_res(**kw):
    from src.services.portfolio_deep_service import StressResult

    kw.setdefault("computed", True)
    kw.setdefault("drop_pct", -20.0)
    kw.setdefault("loss_twd", -224000.0)
    kw.setdefault("loss_pct", 20.4)
    kw.setdefault("warn_pct", 20.0)
    kw.setdefault("total_value_twd", 1_100_000.0)
    kw.setdefault("valued_n", 2)
    kw.setdefault("held_n", 2)
    return StressResult(**kw)


def _var_res(**kw):
    from src.services.portfolio_deep_service import VarResult

    kw.setdefault("computed", True)
    kw.setdefault("hist_95_twd", 16817.0)
    kw.setdefault("hist_99_twd", 25000.0)
    kw.setdefault("param_95_twd", 16000.0)
    kw.setdefault("param_99_twd", 24000.0)
    kw.setdefault("monthly_99_twd", 95000.0)
    kw.setdefault("monthly_99_pct", 8.63)
    kw.setdefault("warn_pct", 10.0)
    kw.setdefault("total_value_twd", 1_100_000.0)
    kw.setdefault("n_common", 119)
    kw.setdefault("n_union", 120)
    kw.setdefault("first_day", "2025-01-02")
    kw.setdefault("last_day", "2025-06-17")
    kw.setdefault("valued_n", 2)
    kw.setdefault("held_n", 2)
    return VarResult(**kw)


def _cash_res(**kw):
    from src.services.portfolio_deep_service import DividendCashResult

    kw.setdefault("computed", True)
    kw.setdefault("gross_twd", 30000.0)
    kw.setdefault("nhi_twd", 0.0)
    kw.setdefault("net_after_nhi_twd", 30000.0)
    kw.setdefault("payouts_n", 8)
    kw.setdefault("tw_n", 2)
    kw.setdefault("lots_n", 2)
    kw.setdefault("held_n", 2)
    kw.setdefault("shares_total", 3000.0)
    return DividendCashResult(**kw)


def _deep(**kw) -> P.DeepReadout:
    """`requested=True` ＋ 戰情表有列的 ⑥ readout（預設三格都算得出來）。"""
    kw.setdefault("requested", True)
    kw.setdefault("submitted", True)
    kw.setdefault("bound", True)
    kw.setdefault("holdings_n", 2)
    kw.setdefault("has_station_rows", True)
    return P.DeepReadout(**kw)


def _live_deep() -> P.DeepReadout:
    return _deep(stress=_stress_res(), var=_var_res(), cash=_cash_res())


# ══════════════════════════════════════════════════════════════════
# 【1】唯讀 —— 本頁碰的是使用者資產，這一類排在最前面
# ══════════════════════════════════════════════════════════════════
#: 本頁**唯一**可以取用的下游符號。白名單，不是黑名單：
#: 任何沒被列在這裡的 `from src.services...import X` 就是紅燈，
#: 不必先想得到那個寫入函式叫什麼名字。
_ALLOWED_L3: frozenset[tuple[str, str]] = frozenset({
    # 持股清單（本批新增）—— 它自己也受 `TestHoldingsServiceIsReadOnly` 管。
    ("src.services.holdings_service", "get_holdings"),
    # 戰情表與它的純函式彙總（**全部唯讀**，逐支讀過 docstring）。
    ("src.services.dividend_station_service", "get_station_rows"),
    ("src.services.dividend_station_service", "build_station_digest"),
    ("src.services.dividend_station_service", "compute_portfolio_totals"),
    ("src.services.dividend_station_service", "get_switch_in_candidates"),
    ("src.services.dividend_station_service", "build_switch_advice"),
    ("src.services.dividend_station_service", "fetch_vix"),
    ("src.services.dividend_station_service", "get_station_macro"),
    # ⑥ 組合深度分析（FE-19 新增）—— 它自己也受
    # `TestPortfolioDeepServiceIsReadOnly` 管（同 `holdings_service` 的待遇）。
    ("src.services.portfolio_deep_service", "get_portfolio_stress"),
    ("src.services.portfolio_deep_service", "get_portfolio_var"),
    ("src.services.portfolio_deep_service", "get_dividend_cash_flow"),
    ("src.services.allocation_service", "get_allocation"),
    ("src.services.portfolio_binding_service", "get_binding_state"),
    ("src.services.portfolio_binding_service", "STATUS_BOUND"),
    ("src.services.portfolio_binding_service", "STATUS_UNBOUND"),
})

#: gsheet / 選股凍結 / 觀察清單的**寫入面**，以及會清掉別人快取的副作用函式。
#: 一個都不准以識別字的形式出現在本檔（呼叫、import、屬性取用都算）。
_WRITE_SURFACE: frozenset[str] = frozenset({
    "save_portfolio", "delete_portfolio",
    "save_stock_watchlist", "add_to_stock_watchlist", "delete_stock_watchlist",
    "create_new_sheet", "rename_sheet",
    "append_forward_test_picks", "add_picks_to_watchlist",
    "freeze_current_picks", "freeze_current_picks_local",
    "clear_read_cache",
    # allocation_service 的登記／重置面：會改到別的頁看到的持股結論。
    "register_cap", "clear_cap", "register_conflict", "reset_allocation_registry",
    "apply_vix_veto", "apply_ring_gate",
})


def _service_imports(tree: ast.Module) -> list[tuple[str, str, int]]:
    _out: list[tuple[str, str, int]] = []
    for _n in ast.walk(tree):
        if isinstance(_n, ast.ImportFrom) and (_n.module or "").startswith(
                ("src.services", "src.data", "src.compute", "app")):
            for _a in _n.names:
                _out.append((_n.module or "", _a.name, _n.lineno))
    return _out


def _identifiers(tree: ast.Module) -> set[str]:
    _out: set[str] = set()
    for _n in ast.walk(tree):
        if isinstance(_n, ast.Name):
            _out.add(_n.id)
        elif isinstance(_n, ast.Attribute):
            _out.add(_n.attr)
        elif isinstance(_n, ast.alias):
            _out.add((_n.asname or _n.name).split(".")[-1])
    return _out


class TestReadOnly:
    """**本頁一律唯讀。不寫入、不刪除、不改動任何一列持股。**

    ⚠️ **這一類證明的是什麼、不證明什麼**（先講清楚，免得被當成全稱句用）：
    它證明**本檔的靜態文字裡沒有任何一條通往寫入面的路** —— 沒有 import、
    沒有識別字、沒有 L1。它**不能**證明「執行時絕不會寫到任何東西」，
    因為那取決於它呼叫的那四支 L3 自己的行為。
    那四支已逐一讀過 docstring（`get_binding_state` 自陳「純讀不寫」、
    `fetch_vix` / `get_station_macro` 自陳唯讀、`get_allocation` 自陳唯讀但會寫
    session 內的記憶化快取，本頁檔頭已揭露）—— **那是讀 docstring，不是本測試驗的。**
    """

    def test_only_whitelisted_l3_symbols_are_imported(self):
        _bad = [f"{_m}.{_n} @line {_l}"
                for _m, _n, _l in _service_imports(_tree())
                if (_m, _n) not in _ALLOWED_L3]
        assert not _bad, (
            "本頁 import 了白名單以外的下游符號：\n  " + "\n  ".join(_bad)
            + "\n（唯讀頁：新增任何一支都必須先確認它不寫使用者資產，"
              "並同步更新 `_ALLOWED_L3` 與檔頭的取數接線表）")

    def test_the_whitelist_is_not_empty_and_is_actually_used(self):
        """**反證**：白名單不是一張沒人比對的空表。"""
        _imports = {(m, n) for m, n, _ in _service_imports(_tree())}
        assert _imports, "本頁一支 L3 都沒有 import —— 白名單形同虛設"
        assert _imports <= _ALLOWED_L3
        assert len(_imports) >= 10, f"實際只 import 了 {sorted(_imports)}"
        assert ("src.services.holdings_service", "get_holdings") in _imports, (
            "持股清單沒有走 L3 —— 這一頁唯一合法的取得方式就是那一支")
        assert {("src.services.portfolio_deep_service", _n)
                for _n in ("get_portfolio_stress", "get_portfolio_var",
                           "get_dividend_cash_flow")} <= _imports, (
            "⑥ 的壓測 / VaR / 配息現金流沒有走 L3 —— "
            "它們的運算在 L2／L3，本頁不得跨層直呼，也不得自己乘 1000")

    def test_no_plain_module_import_can_slip_past_the_whitelist(self):
        """**白名單的漏洞**：`import src.services.x` 拿得到整個模組。

        `_service_imports()` 掃的是 `ast.ImportFrom`；一句 `import
        src.services.portfolio_deep_service` 是 `ast.Import`，**掃不到** ——
        接著 `mod.任何符號` 就完全繞過白名單（`from src.services import x`
        這一種倒是掃得到，它會以 `("src.services", "x")` 落在白名單外）。
        本條把 `ast.Import` 那條路也釘死。
        """
        _bad = [f"{_a.name} @line {_n.lineno}"
                for _n in ast.walk(_tree()) if isinstance(_n, ast.Import)
                for _a in _n.names
                if _a.name.split(".")[0] in ("src", "app", "scripts")]
        assert not _bad, (
            f"本頁用 `import <module>` 拉進了下游模組：{_bad} —— "
            "符號白名單掃不到它，一律改成 `from … import <符號>`")

    def test_no_write_surface_identifier_anywhere(self):
        _hit = sorted(_identifiers(_tree()) & _WRITE_SURFACE)
        assert not _hit, (
            f"本頁出現了寫入面的識別字 {_hit} —— 本頁對持股帳本一律唯讀")

    def test_no_l1_data_import_at_all(self):
        """L5 不得直呼 L1（`CLAUDE.md §8.2` 硬規則第 4 條）。

        對本頁還多一層意義：L1 `gsheet_portfolio` **就是**寫入面的所在地。
        """
        _bad = [f"{_m}.{_n} @line {_l}" for _m, _n, _l in _service_imports(_tree())
                if _m.startswith("src.data")]
        assert not _bad, f"本頁直接 import 了 L1：{_bad}"

    def test_no_import_from_app(self):
        _bad = [f"{_m} @line {_l}" for _m, _n, _l in _service_imports(_tree())
                if _m == "app" or _m.startswith("app.")]
        assert not _bad, f"跨層上行 import：{_bad}"

    def test_no_cross_module_private_symbol(self):
        """跨檔取用底線開頭的符號（`CLAUDE.md §8.2.A.2` V-PICKER-PRIV-1）。"""
        _bad = [f"{_m}.{_n} @line {_l}" for _m, _n, _l in _service_imports(_tree())
                if _n.startswith("_")]
        assert not _bad, f"跨層直取私有符號：{_bad}"

    def test_sheet_id_never_enters_this_layer(self):
        """**結構性**保證：本層的資料結構裡沒有 sheet id 這個欄位。

        L3 的 `BindingState` 有 `sheet_id`；把它帶進 UI 層，遲早有人「順手」
        印出來當除錯資訊。**結構上不讓它進來**，比寫一句「記得不要印」可靠。
        """
        assert "sheet_id" not in P.BindingReadout.__dataclass_fields__, (
            "`BindingReadout` 長出了 sheet_id 欄位 —— "
            "本頁只該回答「有沒有綁」這個布林")
        _fields = set(P.BindingReadout.__dataclass_fields__)
        assert {"logged_in", "sheet_bound"} <= _fields

    def test_the_binding_loader_does_not_read_the_sheet_id(self):
        """`load_binding()` 連讀都不讀 L3 的 `sheet_id` 屬性。"""
        import inspect

        _s = inspect.getsource(P.load_binding)
        assert "sheet_id" not in _s, (
            "`load_binding()` 碰了 sheet_id —— 讀了就有機會漏出去")

    def test_no_cache_decorator_and_no_inline_ttl(self):
        """L5 不得自建快取層（`CLAUDE.md §8.2.A.2` V-SMART-CACHE-1）。"""
        _bad = [f"@st.{_d.attr} @line {_d.lineno}"
                for _fn in ast.walk(_tree())
                if isinstance(_fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                for _d in _fn.decorator_list
                if isinstance(_d, ast.Attribute)
                and _d.attr in ("cache_data", "cache_resource")]
        _bad += [f"@st.{_c.func.attr} @line {_c.lineno}"
                 for _fn in ast.walk(_tree())
                 if isinstance(_fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                 for _c in _fn.decorator_list
                 if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Attribute)
                 and _c.func.attr in ("cache_data", "cache_resource")]
        assert not _bad, f"本頁自建了快取層：{_bad}"
        _ttl = [_k.lineno for _n in ast.walk(_tree())
                if isinstance(_n, ast.Call)
                for _k in _n.keywords if _k.arg == "ttl"]
        assert not _ttl, f"本頁出現 inline ttl=（第 {_ttl} 行）—— TTL 的 SSOT 在 L0"

    def test_no_io_library_is_touched(self):
        """零 `requests` / `yfinance` / FinMind / `read_csv` / SQL / parquet。"""
        _names = _identifiers(_tree())
        _banned = {"requests", "yfinance", "FinMind", "finmind",
                   "read_csv", "read_parquet", "to_parquet", "read_sql",
                   "execute", "connect"}
        assert not (_names & _banned), f"本頁碰了 I/O：{sorted(_names & _banned)}"


# ══════════════════════════════════════════════════════════════════
# 【2】三種「沒有」絕不可混（本頁的 §1 主戰場）
# ══════════════════════════════════════════════════════════════════
class TestThreeEmptiesNeverMix:
    """「還沒綁」／「綁了但裡面是空的」／「上游掛了」是**三件事**。

    ⛔ **空的組合不是故障。** 一個剛註冊、還沒填任何一列的使用者，
    看到的應該是「你的 Sheet 綁好了，只是還沒有內容」，**不是**一片紅色。
    把它畫成紅色 = v3 §02 前半句要杜絕的「假性錯誤滿版」，
    而且會讓**真的**壞掉那一次沒有人看得見。
    """

    def test_cold_start_is_idle_on_both_cards(self):
        _b = P.load_binding(P.HoldRequest(submitted=False))
        assert _b.requested is False and _b.submitted is False
        assert P.build_binding_card(_b)[0].state == UI_IDLE
        assert P.build_portfolio_count_card(_b)[0].state == UI_IDLE

    def test_unbound_is_grey_and_is_a_valid_answer(self):
        _b = _binding(sheet_bound=False, status="unbound")
        _card = P.build_binding_card(_b)[0]
        assert _card.state == UI_EMPTY, "「還沒綁」被畫成別的東西了"
        assert _card.state != UI_FAILED
        assert "有效的結果" in _card.note.why

    def test_bound_but_empty_is_grey_not_red(self):
        """**這一條就是「空的組合不是故障」。**"""
        _b = _binding(sheet_bound=True, status="bound_empty",
                      count_requested=True, portfolio_count=0)
        _bind_card = P.build_binding_card(_b)[0]
        _count_card = P.build_portfolio_count_card(_b)[0]
        assert _bind_card.state == UI_LIVE, "綁到了卻沒說綁到"
        assert _count_card.state == UI_EMPTY, (
            f"空組合被畫成 {_count_card.state} —— 空的組合不是故障")
        assert _count_card.state != UI_FAILED
        assert "有效的結果" in _count_card.note.why

    def test_bound_but_unreadable_is_the_red_one(self):
        """L3 為了不擋住全域狀態列把失敗降級成中性；本頁**還原成紅色**。"""
        _b = _binding(sheet_bound=True, status="bound", count_requested=True,
                      portfolio_count=None,
                      count_missing_reason="fetch_failed")
        _card = P.build_portfolio_count_card(_b)[0]
        assert _card.state == UI_FAILED, (
            "「綁了卻讀不到組合清單」是系統真出錯，必須是紅的")

    def test_zero_is_never_used_to_stand_in_for_unknown(self):
        """L3 契約：未知 → `None`，**不腦補 0**。本頁不得把它們畫成同一格。"""
        _zero = _binding(sheet_bound=True, status="bound_empty",
                         count_requested=True, portfolio_count=0)
        _unknown = _binding(sheet_bound=True, status="bound",
                            count_requested=True, portfolio_count=None,
                            count_missing_reason="fetch_failed")
        assert (P.build_portfolio_count_card(_zero)[0].state
                != P.build_portfolio_count_card(_unknown)[0].state)

    def test_upstream_exception_reds_both_cards(self):
        _b = _binding(error="RuntimeError('boom')")
        assert P.build_binding_card(_b)[0].state == UI_FAILED
        assert P.build_portfolio_count_card(_b)[0].state == UI_FAILED

    def test_an_exception_never_becomes_an_uncaught_valueerror(self):
        """**回歸守衛**：整支 L3 炸掉時，第二張卡的 gate 必須也算「問過了」。

        少了這條蘊含，第二張卡會拿到「`requested=False` 卻帶 `error`」——
        L0 當場 `ValueError`，一張該畫的紅卡變成**整頁未捕捉例外**。
        """
        _b = P.BindingReadout(requested=True, submitted=True,
                              error="RuntimeError('boom')")
        assert _b.count_requested is False and _b.count_gate is True
        assert P.build_portfolio_count_card(_b)[0].state == UI_FAILED

    def test_all_four_situations_are_pairwise_distinguishable_on_screen(self):
        """四種情境的**畫面文字**必須兩兩不同 —— 狀態相同也要講得出差別。

        ⚠️ 「還沒綁」與「這一輪沒去讀」在 L0 都是 `idle`；
        「還沒綁」與「綁了但空」在兩張卡上分屬不同格。
        狀態機分得開只是第一步，**使用者看到的那句話也要分得開**。
        """
        _cases = {
            "冷啟動": P.load_binding(P.HoldRequest(submitted=False)),
            "選了只讀市場端": P.load_binding(
                P.HoldRequest(submitted=True, mode=P.SCOPE_MARKET)),
            "讀了但沒綁": _binding(sheet_bound=False, status="unbound"),
            "綁了但空": _binding(sheet_bound=True, status="bound_empty",
                                 count_requested=True, portfolio_count=0),
        }
        _texts = {}
        for _name, _b in _cases.items():
            _bind = P.build_binding_card(_b)[0]
            _count = P.build_portfolio_count_card(_b)[0]
            _texts[_name] = (
                (_bind.note.now if _bind.note else _bind.value)
                + "||" + (_count.note.now if _count.note else _count.value))
        assert len(set(_texts.values())) == len(_cases), (
            f"有兩種情境畫出同一句話：{_texts}")

    def test_the_count_card_never_quotes_a_sentence_the_other_card_did_not_say(self):
        """冷啟動時第二張卡不得宣稱「上一張卡顯示你還沒有綁定」——

        冷啟動時上一張卡寫的是「尚未執行」，它**沒說過那句話**。
        `idle` 有三種來源（沒按／選了不讀／讀了但沒綁），文案一種都不可以共用。
        """
        _cold = P.load_binding(P.HoldRequest(submitted=False))
        _cold_bind = P.build_binding_card(_cold)[0]
        _cold_count = P.build_portfolio_count_card(_cold)[0]
        assert "還沒有綁定" not in _cold_count.note.why, (
            "冷啟動的第二張卡引用了上一張卡沒說過的話")
        assert _cold_count.note.now == _cold_bind.note.now == P.IDLE_NOW

        _unbound = _binding(sheet_bound=False, status="unbound")
        assert "還沒有綁定" in P.build_portfolio_count_card(_unbound)[0].note.why

    def test_choosing_market_only_is_not_an_error(self):
        """按了鈕但選「只讀市場端」→ `idle` ＋ 明講是你選的，**不是**紅、不是空。"""
        _b = P.load_binding(P.HoldRequest(submitted=True, mode=P.SCOPE_MARKET))
        _card = P.build_binding_card(_b)[0]
        assert _card.state == UI_IDLE
        assert P.binding_scope_idle(_b) is True
        assert "沒有發那一次網路呼叫" in _card.note.why

    def test_macro_not_evaluated_is_grey_and_never_substituted_with_neutral(self):
        """線框 ④：「總經本輪未評估，**依規則不以「中性」代替 —— 不猜多空**」。"""
        _m = P.MacroReadout(requested=True, loaded=False)
        _card = P.build_macro_stage_card(_m)[0]
        assert _card.state == UI_EMPTY and _card.state != UI_FAILED
        assert _card.value == "", "未評估卻給了結論文字"
        assert "不以「中性」代替" in _card.note.why

    def test_missing_vix_is_grey_not_red_and_is_never_zero(self):
        _card = P.build_vix_card(P.VixReadout(requested=True, vix=None))[0]
        assert _card.state == UI_EMPTY
        assert "0" not in _card.value
        assert "不拿舊值或 0 頂替" in _card.note.why

    def test_allocation_not_loaded_is_grey_not_a_made_up_range(self):
        _card = P.build_position_cap_card(
            P.AllocationReadout(requested=True, is_loaded=False))[0]
        assert _card.state == UI_EMPTY
        assert _card.value == ""


# ══════════════════════════════════════════════════════════════════
# 【3】`requested=` 不得從資料反推（白名單 AST，照頁 2／3 那套）
# ══════════════════════════════════════════════════════════════════
#: ⚠️ 這是**白名單**，不是黑名單：任何沒被宣告成 gate 的東西出現在那裡就是紅燈，
#: 不必先想得到它的名字（頁 1 的恆真式 `(alloc is not None)` 就是想不到的那種）。
_GATE_ATTRS: frozenset[str] = frozenset({
    "requested", "submitted", "count_requested", "count_gate",
    # 容器名（讀的是它們的欄位，不是它們本身）
    "req", "vix", "macro", "alloc", "binding", "disclosure", "self",
})

#: 明確的結果資料名 —— 一個都不准出現在 `requested=` 裡（黑名單，第二道）。
_PAYLOAD_TOKENS: frozenset[str] = frozenset({
    "loaded", "is_loaded", "sheet_bound", "portfolio_count", "has_rows",
    "hold_rows", "inspect_rows", "degraded", "range_text", "posture",
    "status", "logged_in", "rows", "has_value", "error", "value",
    "len", "empty", "any", "all",
})


def _leaf_names(node: ast.AST) -> set[str]:
    """運算式**實際讀出來的識別字**（容器名不算，讀的欄位才算）。"""
    _bases = {id(_n.value) for _n in ast.walk(node)
              if isinstance(_n, ast.Attribute)}
    _out: set[str] = set()
    for _n in ast.walk(node):
        if isinstance(_n, ast.Attribute):
            _out.add(_n.attr)
        elif isinstance(_n, ast.Name) and id(_n) not in _bases:
            _out.add(_n.id)
    return _out


def _classify_calls(tree: ast.Module):
    for _n in ast.walk(tree):
        if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
                and _n.func.id == "classify_ui_state"):
            yield _n


def _requested_offences(tree: ast.Module) -> list[str]:
    """本檔用的**單一**判定入口（測試與自證共用，不是兩把尺）。"""
    _bad: list[str] = []
    for _call in _classify_calls(tree):
        _kw = {_k.arg: _k.value for _k in _call.keywords if _k.arg}
        if "requested" not in _kw:
            _bad.append(f"line {_call.lineno}: 沒有傳 requested=")
            continue
        _req_expr = _kw["requested"]
        _names = _leaf_names(_req_expr)
        _illegal = {_x for _x in _names
                    if _x not in _GATE_ATTRS and not _x.endswith("requested")
                    and not _x.endswith("submitted") and _x != "bool"}
        if _illegal:
            _bad.append(f"line {_call.lineno}: requested= 讀了非 gate 的東西 "
                        f"{sorted(_illegal)}")
        _payload = _names & _PAYLOAD_TOKENS
        if _payload:
            _bad.append(f"line {_call.lineno}: requested= 含結果資料名 "
                        f"{sorted(_payload)}")
        if "has_value" in _kw and ast.dump(_req_expr) == ast.dump(_kw["has_value"]):
            _bad.append(f"line {_call.lineno}: requested= 與 has_value= 是同一個運算式")
        if "has_value" in _kw:
            _overlap = (_names & _leaf_names(_kw["has_value"])) - {"bool"}
            if _overlap:
                _bad.append(f"line {_call.lineno}: requested= 與 has_value= "
                            f"讀同一個欄位 {sorted(_overlap)}")
    return _bad


class TestRequestedIsNotDerivedFromData:
    """L0 的鐵律：**`idle` 只能由上游帶下來，禁止由 `if not data:` 推導。**"""

    def test_there_are_calls_to_guard(self):
        _calls = list(_classify_calls(_tree()))
        assert len(_calls) >= 6, (
            f"頁 4 至少有 6 個判態點（未接線共用 / 兩套刻度 / VIX / 總經位階 / "
            f"建議水位 / 綁定 / 組合本數），實際找到 {len(_calls)}")

    def test_every_call_passes_requested(self):
        for _call in _classify_calls(_tree()):
            assert any(_k.arg == "requested" for _k in _call.keywords), (
                f"{_VIEW.name}:{_call.lineno} 沒有傳 `requested=`")

    def test_no_call_derives_requested_from_result_data(self):
        _bad = _requested_offences(_tree())
        assert not _bad, (
            "`requested=` 從資料反推了（idle 只能由上游帶下來）：\n  "
            + "\n  ".join(_bad))

    def test_the_gate_key_is_written_by_the_shared_form_only(self):
        """gate 的 session key **本檔一次都不寫** —— 唯一寫入點在共用層。

        本頁把 `SS_APPLIED_HOLD` 當 `applied_key` 傳給
        `_ui_kit.single_submit_form()`，由它的 submit 分支寫。
        本檔若自己出現一行 `st.session_state[SS_APPLIED_HOLD] = …`，
        「有沒有人叫過」就不再是事實，而是可以被偽造的值。
        """
        _writes = [_n.lineno for _n in ast.walk(_tree())
                   if isinstance(_n, ast.Assign) and _n.targets
                   and isinstance(_n.targets[0], ast.Subscript)]
        assert not _writes, (
            f"本檔出現了 session 下標指派（第 {_writes} 行）—— "
            "gate 的唯一寫入點應該在 `_ui_kit.single_submit_form()`")
        import inspect

        _kit = inspect.getsource(
            sys.modules["src.ui.views._ui_kit"].single_submit_form)
        assert "st.session_state[applied_key]" in _kit
        assert "if _submitted:" in _kit, "共用層的寫入不再受 submit 保護了"

    def test_the_page_hands_the_gate_key_to_the_shared_form(self):
        _s = _src()
        assert "applied_key=SS_APPLIED_HOLD" in _s
        assert "widget_key=SS_SCOPE_WIDGET" in _s

    def test_reader_looks_at_key_existence_not_content(self):
        """`bool(rows)` 分不出「還沒按」與「按了但你沒有持股」→ 只准看 key 在不在。"""
        assert P.applied_hold_request({}).submitted is False
        assert P.applied_hold_request(
            {P.SS_APPLIED_HOLD: None}).submitted is True
        _r = P.applied_hold_request({P.SS_APPLIED_HOLD: {"mode": "  "}})
        assert _r.submitted is True and _r.mode == P.SCOPE_MARKET, (
            "形狀怪的已套用值應退回最保守的範圍，不猜使用者要連 Google")

    def test_the_second_gate_is_a_user_choice_not_a_data_property(self):
        assert P.HoldRequest(submitted=True,
                             mode=P.SCOPE_MARKET).wants_binding is False
        assert P.HoldRequest(submitted=True,
                             mode=P.SCOPE_WITH_BINDING).wants_binding is True
        assert P.HoldRequest(submitted=False,
                             mode=P.SCOPE_WITH_BINDING).wants_binding is False

    def test_a_result_with_data_but_no_gate_cannot_even_be_built(self):
        """**恆真式的直接反證**：這種卡在 L0 就**構造不出來**（§1 Fail Loud）。"""
        with pytest.raises(ValueError, match="requested=False"):
            P.build_vix_card(P.VixReadout(requested=False, vix=17.5))
        with pytest.raises(ValueError, match="requested=False"):
            P.build_macro_stage_card(P.MacroReadout(requested=False, loaded=True))

    def test_the_page_never_produces_that_contradiction_itself(self):
        """而本頁自己的 loader 走不到上面那個矛盾：沒按 → 什麼都不帶回來。"""
        _r = P.HoldRequest(submitted=False)
        assert P.load_vix(_r).vix is None
        assert P.load_macro(_r).loaded is False
        assert P.load_allocation(_r).is_loaded is False
        assert P.load_binding(_r).sheet_bound is False

    def test_the_always_on_disclosure_uses_a_literal_not_a_tautology(self):
        """② 的 `requested=` 必須是**字面 True**，不是任何運算式。

        字面常數是在**陳述**「這個揭露永遠開著」；
        `bool(rows)` 之類的則是在**假裝判斷** —— 那才是頁 1 的恆真式病。
        """
        _lits = [_c for _c in _classify_calls(_tree())
                 for _k in _c.keywords
                 if _k.arg == "requested" and isinstance(_k.value, ast.Constant)]
        assert len(_lits) == 1, (
            f"字面 `requested=` 應該只有 ② 那一處，實際 {len(_lits)} 處")
        assert _lits[0].keywords[0].value.value is True


# ══════════════════════════════════════════════════════════════════
# 【4】沒按之前一行 L3 都不呼叫（下毒實測，不是讀 docstring）
# ══════════════════════════════════════════════════════════════════
class _L3Touched(BaseException):
    """毒藥。**刻意不繼承 `Exception`** —— 本頁每一支 loader 都是

    `except Exception`，繼承 `Exception` 的話會被吞成一則錯誤字串，
    測試照樣綠、而 L3 其實已經被呼叫過了。不繼承才穿得出來。
    """


class _PoisonModule:
    """任何屬性取用都當場引爆的假模組。"""

    def __init__(self, name: str) -> None:
        self.__name__ = name

    def __getattr__(self, item: str):
        raise _L3Touched(f"{self.__name__}.{item} 在 requested=False 時被碰到了")


#: 頁 4 檔頭「取數接線表」列出的全部下游 L3 模組。
#: ⚠️ `holdings_service` 是 FE-15 新接線的那一支 —— **它一定要在這張表裡**，
#:    否則「沒按之前不碰你的 Google Sheet」這句話就沒有人在驗。
#: ⚠️ `portfolio_deep_service` 是 FE-19 新接線的那一支：它逐檔會打
#:    `fetch_etf_info` / `fetch_etf_price` / `fetch_etf_dividends`，
#:    **在按鈕之前跑一次就是白打幾十次網路** —— 同樣一定要在這張表裡。
_DOWNSTREAM = (
    "src.services.holdings_service",
    "src.services.dividend_station_service",
    "src.services.portfolio_deep_service",
    "src.services.allocation_service",
    "src.services.portfolio_binding_service",
)


@pytest.fixture()
def poisoned(monkeypatch):
    """把全部下游換成毒藥模組。碰到就 `_L3Touched`，穿過所有 try/except。"""
    for _m in _DOWNSTREAM:
        monkeypatch.setitem(sys.modules, _m, _PoisonModule(_m))
    return _DOWNSTREAM


class TestNothingIsCalledBeforeYouAsk:
    """檔頭宣稱「`requested=False` 時本檔一行 L3 都不呼叫」——

    在本條之前那是一句**沒有人驗過的自我宣稱**。idle 態的 Note 還把它
    寫給使用者看；宣稱與實作若不一致，那就是對使用者說謊（§1）。
    """

    def test_every_loader_touches_nothing_before_submit(self, poisoned):
        _r = P.HoldRequest(submitted=False)
        assert P.load_vix(_r).requested is False
        assert P.load_macro(_r).requested is False
        assert P.load_allocation(_r).requested is False
        assert P.load_binding(_r).requested is False
        _h = P.load_holdings(_r)
        assert _h.requested is False
        _st = P.load_station(_h)
        assert _st.requested is False
        assert P.load_switch(_st, P.load_macro(_r), _h).requested is False
        assert P.load_deep(_st).requested is False

    def test_market_only_scope_really_skips_google(self, poisoned):
        """**本頁獨有的第二個 gate**：選「只讀市場端」時 Google 那邊一次都不准被碰。

        ⚠️ 本批之後這個 gate 擋掉的**不只是綁定狀態，還有整份持股清單**（以及
        以它為輸入的戰情表與換股建議）—— 那才是真正會連到使用者資產的那幾支。
        VIX / 總經 / 建議水位這時**應該**被呼叫（毒藥會炸），所以本條不跑它們。
        """
        _r = P.HoldRequest(submitted=True, mode=P.SCOPE_MARKET)
        _b = P.load_binding(_r)
        assert _b.requested is False and _b.error == ""
        _h = P.load_holdings(_r)
        assert _h.requested is False and _h.error == "" and _h.holdings == ()
        _st = P.load_station(_h)
        assert _st.requested is False and _st.error == "" and _st.rows == ()
        _sw = P.load_switch(_st, P.MacroReadout(requested=False), _h)
        assert _sw.requested is False and _sw.error == ""
        _dp = P.load_deep(_st)
        assert _dp.requested is False and _dp.error == "" and _dp.stress is None

    def test_a_holdings_read_never_happens_for_an_empty_list(self, poisoned):
        """讀到空清單時**不再往下打第二次網路** —— 但 `requested` 仍然是 True。

        ⚠️ 這一條同時擋兩個方向的錯：
          · 對空清單還去跑一次逐檔抓取（白打一次網路）；
          · 把「清單是空的」當成 gate 寫回 `requested=False`（那就是從資料反推，
            使用者會看到「尚未執行」而其實已經執行過了）。
        """
        _h = P.HoldingsReadout(requested=True, submitted=True, bound=True)
        _st = P.load_station(_h)          # 毒藥全上，這一行不准碰任何 L3
        assert _st.requested is True and _st.rows == () and _st.error == ""
        _sw = P.load_switch(_st, P.MacroReadout(requested=True), _h)
        assert _sw.requested is True and _sw.error == ""
        _dp = P.load_deep(_st)          # 毒藥全上，⑥ 這一行也不准碰任何 L3
        assert _dp.requested is True and _dp.error == ""
        assert (_dp.stress, _dp.var, _dp.cash) == (None, None, None)
        assert _dp.has_station_rows is False

    def test_the_poison_really_would_have_fired(self, poisoned):
        """**反證**：同一組毒藥下，`requested=True` 一定炸。

        沒有這一條，上面幾條可能只是因為毒藥根本沒裝上去而綠。
        """
        _r = _req()
        with pytest.raises(_L3Touched):
            P.load_vix(_r)
        with pytest.raises(_L3Touched):
            P.load_macro(_r)
        with pytest.raises(_L3Touched):
            P.load_allocation(_r)
        with pytest.raises(_L3Touched):
            P.load_binding(_r)
        with pytest.raises(_L3Touched):
            P.load_holdings(_r)
        # 有持股 → 戰情表與換股建議都會往下打，毒藥同樣要炸。
        _h = P.HoldingsReadout(requested=True, submitted=True, bound=True,
                               holdings=({"ticker": "0056", "held": True},))
        with pytest.raises(_L3Touched):
            P.load_station(_h)
        _st = P.StationReadout(requested=True, submitted=True, bound=True,
                               holdings_n=1, rows=({"代號": "0056"},))
        with pytest.raises(_L3Touched):
            P.load_switch(_st, P.MacroReadout(requested=True), _h)
        with pytest.raises(_L3Touched):
            P.load_deep(_st)

    def test_the_disclosure_needs_no_l3_at_all(self, poisoned):
        """② 是 L0-only —— 毒藥全上，它照樣算得出來。"""
        _d = P.build_scale_disclosure()
        assert _d.error == "" and _d.has_rows

    def test_idle_note_promise_matches_the_code(self):
        """畫給使用者看的那句承諾，與上面實測到的行為必須是同一件事。"""
        assert "一次 L3 取數都不會發" in P.IDLE_WHY
        assert "沒有發那一次網路呼叫" in P.GOOGLE_NOT_ASKED_WHY
        assert "持股清單也在這一次呼叫裡" in P.GOOGLE_NOT_ASKED_WHY, (
            "這個選項現在擋掉的不只是綁定狀態 —— 文案沒講出來就是漏講")


# ══════════════════════════════════════════════════════════════════
# 【5】仍然未接線的八張卡
# ══════════════════════════════════════════════════════════════════
#: ⚠️ **FE-15 從 17 張降到 8 張**（根因是 `src/services/` 沒有持股清單）；
#: **FE-19 再降到 5 張** —— ⑥ 的壓力測試 / VaR / 配息現金流補上了 L3
#: `portfolio_deep_service` 之後就活了。
#: 剩下這 5 張**卡在完全不同的地方**，各自的 `where` 不可共用：
#:   · `hold.deep.rebalance`  帳本沒有「目標比例」欄（**不是**缺 L3 wrapper）
#:   · `hold.deep.grape`      實作在 L5、widget key 寫死
#:   · `hold.ai_summary`      缺一顆要先出線框拍板的按鈕（資料已經有了）
#:   · `hold.setup.*`         **不是缺 L3，是缺授權**（本頁唯讀）
_UNWIRED_KEYS: frozenset[str] = frozenset({
    "hold.deep.rebalance", "hold.deep.grape",
    "hold.ai_summary", "hold.setup.pick_sheet", "hold.setup.watchlist",
})


def _all_unwired_builts(requested: bool):
    """**從真正畫出來的那幾批裡挑出未接線的**，不是另外手抄一份名單。

    手抄一份的話，某一張卡哪天不小心變回 unwired（或被接線卻忘了從名單移除）
    都不會有人發現 —— 那正是這一整類測試要防的事。
    """
    _station = P.StationReadout(requested=requested, submitted=requested)
    _built = (P.build_conclusion_cards(_station)
              + (P.build_lightwall_card(_station),
                 P.build_switch_card(P.SwitchReadout(requested=requested,
                                                     submitted=requested),
                                     _station),
                 P.build_allocation_split_card(_station),
                 P.build_take_profit_card(_station),
                 P.build_ai_summary_card(requested))
              + P.build_deep_cards(_station, P.load_deep(_station))
              + (P.build_holdings_preview_card(
                  P.HoldingsReadout(requested=requested, submitted=requested)),)
              + P.build_setup_unwired_cards(requested))
    return tuple(_b for _b in _built if _b[0].state == UI_UNWIRED)


class TestUnwiredStaysUnwired:
    """未接線 ≠ 查不到。**按幾次都一樣** —— 這正是它與 `empty` 必須分兩態的原因。"""

    def test_the_count_is_what_the_docstring_claims(self):
        _keys = {_c.key for _c, _f, _s in _all_unwired_builts(False)}
        assert _keys == _UNWIRED_KEYS, (
            f"未接線卡的名單與本測試的敘述不一致：\n"
            f"  多出來（該接線卻還是 unwired？）：{sorted(_keys - _UNWIRED_KEYS)}\n"
            f"  不見了（接線了？）：{sorted(_UNWIRED_KEYS - _keys)}\n"
            "接線或新增時，本名單與檔頭的「仍然沒有接上的項目」要一起改")

    def test_no_card_still_blames_the_missing_holdings_loader(self):
        """**本批最容易留下的假話**：`holdings_service` 已經補上了。

        任何一張卡若還寫「`src/services/` 沒有回傳持股清單的 L3」，
        就是叫下一個人去補一支已經在那裡的東西 —— 比不寫更糟（§-2）。
        """
        _bad = [_c.key for _c, _f, _s in _all_unwired_builts(False)
                if ("沒有任何一支" in _c.note.why
                    or "holdings loader" in _c.note.where
                    or "沒有 L3 介面" in _c.note.why)]
        assert not _bad, f"這幾張卡還在怪一個已經補好的東西：{_bad}"
        assert not hasattr(P, "HOLDINGS_WHY"), (
            "`HOLDINGS_WHY`（「沒有 L3 holdings loader」）還在 —— "
            "那句話本批之後是假的，常數留著遲早有人再用它")

    def test_no_card_still_blames_a_missing_l3_wrapper(self):
        """**FE-19 最容易留下的假話**：`portfolio_deep_service` 已經補上了。

        原本 ⑥ 的再平衡 / 壓力測試 / VaR 三張卡共用一句「L3 沒有 wrapper」。
        本批之後那句話**對三張都是假的**：壓測與 VaR 已接線，
        而再平衡缺的從來就不是 wrapper（是帳本沒有目標比例那一欄）。
        """
        _bad = [_c.key for _c, _f, _s in _all_unwired_builts(False)
                if ("L3 沒有 wrapper" in _c.note.why
                    or "還沒有 wrapper" in _c.note.why
                    or "連 L3 wrapper 都還沒有" in _c.note.why)]
        assert not _bad, f"這幾張卡還在怪一支已經補好的 L3 wrapper：{_bad}"
        assert not hasattr(P, "MISSING_L3_WRAPPER_WHY"), (
            "`MISSING_L3_WRAPPER_WHY`（「L3 沒有 wrapper」）還在 —— "
            "本批補上 `portfolio_deep_service` 之後那句話是假的，"
            "常數留著遲早有人再用它去叫下一個人補一支已經在那裡的東西")

    @pytest.mark.parametrize("requested", [False, True])
    def test_all_stay_unwired_whatever_you_press(self, requested):
        for _card, _facts, _signal in _all_unwired_builts(requested):
            assert _card.state == UI_UNWIRED, (
                f"{_card.key} 在 requested={requested} 時變成 {_card.state}")

    def test_each_has_all_three_elements(self):
        for _card, _facts, _signal in _all_unwired_builts(False):
            _now, _why, _where = _note_triple(_card.note)
            assert _now.strip() and _why.strip() and _where.strip(), _card.key

    def test_each_says_there_is_no_user_action(self):
        for _card, _facts, _signal in _all_unwired_builts(False):
            assert P.NO_EXIT_MARKER in _card.note.where, (
                f"{_card.key} 的「去哪補」給了一個使用者其實按不到的出口")

    def test_the_wheres_are_not_copy_pasted(self):
        """八張卡卡在**不同的層**，共用一句話會讓「補哪一層才會好」消失。

        ⚠️ 本批把門檻**收緊成「全部互異」**（原本是 17 張裡至少 14 種）——
        張數變少之後，「至少 N 種」會鬆到形同虛設。
        唯一的例外是 Sheet 選擇／觀察清單管理：它們是**同一個理由**
        （本頁不准寫），共用 `READONLY_WHERE` 是對的，故分開數。
        """
        _builts = _all_unwired_builts(False)
        _readonly = {"hold.setup.pick_sheet", "hold.setup.watchlist"}
        _wheres = [_c.note.where for _c, _f, _s in _builts
                   if _c.key not in _readonly]
        assert len(set(_wheres)) == len(_wheres), (
            f"未接線卡出現重複的「去哪補」：{len(_wheres)} 張只有 "
            f"{len(set(_wheres))} 種說法 —— 它們卡住的位置不同"
            "（缺 L3 wrapper／缺一個要先拍板的畫面元件／L5 widget key）")
        _ro_wheres = {_c.note.where for _c, _f, _s in _builts
                      if _c.key in _readonly}
        assert _ro_wheres == {P.READONLY_WHERE}, (
            "唯讀那兩張卡的「去哪補」不再是同一句 —— 它們是同一個理由，"
            "分頭寫只會漂移")

    def test_write_blocked_cards_do_not_blame_the_missing_l3(self):
        """Sheet 選擇／觀察清單管理**不是缺 L3，是缺授權** —— 不可寫成同一句。

        寫成「補一支 L3 就會有」是假的：就算補了，本頁也不會做那件事。
        """
        _by_key = {_c.key: _c for _c, _f, _s in P.build_setup_unwired_cards(False)}
        assert set(_by_key) == {"hold.setup.pick_sheet", "hold.setup.watchlist"}, (
            "葉2 的未接線卡名單變了 —— 持股列預覽本批已接線，"
            "它不該再回到這一批")
        for _k, _card in _by_key.items():
            _why = _card.note.why
            assert _why == P.READONLY_WHY, f"{_k} 的理由寫成了缺 L3"
            assert "寫入" in _why
            assert "L3" not in _why, f"{_k} 把「不准寫」講成了「缺 L3」"

    def test_the_rebalance_card_names_the_real_blocker(self):
        """⑥ 再平衡卡在**帳本沒有目標比例那一欄**，不是缺 L3、不是缺持股。

        講錯的話，下一個人會去補一支已經存在的 L3 wrapper（或一份已經存在的
        持股清單），而真正的缺口 —— 一個還沒拍板的「目標比例%」輸入元件 ——
        沒有人會去處理。
        """
        _station = P.StationReadout(requested=False)
        _by_key = {_c.key: (_c, dict(_f)) for _c, _f, _s in P.build_deep_cards(
            _station, P.load_deep(_station))}
        _card, _facts = _by_key["hold.deep.rebalance"]
        assert _card.state == UI_UNWIRED
        assert "目標" in _card.note.why, "沒有講出真正缺的東西（目標權重）"
        assert "不是 L3 wrapper" in _card.note.why, (
            "沒有明講「缺的不是 wrapper」—— 那正是上一版寫錯的地方")
        assert "0.0%" in _card.note.why, (
            "沒有解釋「拿現況當目標會恆等於 0.0%」—— "
            "少了這句，下一個人會覺得『那就拿現況當目標啊』")
        assert "CoreSatelliteManager" in _card.note.where, (
            "沒有擋掉「改用 portfolio_manager 頂替」那條路 —— "
            "它的核心比例是另一套，會讓同一頁出現兩個矛盾的核心比例")
        assert any("已接線" in _v for _v in _facts.values()), (
            "沒有把「持股清單與 L3 wrapper 都已經在了」講出來")

    def test_the_two_remaining_deep_cards_are_stuck_on_different_things(self):
        """再平衡與葡萄串**不是同一個原因** —— 共用一句話會讓資訊消失。"""
        _station = P.StationReadout(requested=False)
        _by_key = {_c.key: _c for _c, _f, _s in P.build_deep_cards(
            _station, P.load_deep(_station))}
        _reb, _grape = (_by_key["hold.deep.rebalance"],
                        _by_key["hold.deep.grape"])
        assert _reb.note.why != _grape.note.why
        assert _reb.note.where != _grape.note.where
        assert "widget" in _grape.note.why, "葡萄串卡的是 widget key，不是資料"

    def test_every_unwired_card_carries_facts(self):
        """未接線也要讓人看到「這一格本來會有什麼」，否則使用者不知道少看了什麼。"""
        for _card, _facts, _signal in _all_unwired_builts(False):
            assert _facts, f"{_card.key} 一列 facts 都沒有"

    def test_no_unwired_card_pretends_to_have_a_conclusion(self):
        for _card, _facts, _signal in _all_unwired_builts(False):
            assert _card.value == "" and _signal == "", _card.key

    def test_the_ai_button_is_deliberately_not_drawn(self):
        """線框 ⑦ 畫了一顆 `st.button`，本頁刻意沒畫 —— 那會是假出口。

        這一條同時保證：接線的人會先看到這段說明，而不是「順手」補一顆鈕。
        """
        _facts = dict(P.build_ai_summary_card(False)[1])
        assert any("假出口" in _v for _v in _facts.values()), (
            "⑦ 沒有說明為什麼線框那顆鈕不在畫面上")


# ══════════════════════════════════════════════════════════════════
# 【6】② 兩套刻度：degraded 由 L0 決定，不是寫死的
# ══════════════════════════════════════════════════════════════════
class TestScaleDisclosureComesFromL0:
    """線框 ②：「⚠️ 兩套刻度目前不一致 … 某一側的門檻來源已標
    `discriminative=False`」。

    ⚠️ 這張卡是本頁**唯一**會判 `degraded` 的地方，而且**不是硬湊的**：
    它直接讀 L0 `station_specs` 的旗標。旗標翻面，卡就跟著翻面。
    """

    def test_it_needs_no_gate_and_is_always_on(self):
        """線框原文：「揭露常駐，不隨載入狀態消失」。"""
        _card = P.build_scale_card(P.build_scale_disclosure())[0]
        assert _card.state != UI_IDLE

    def test_both_scales_are_listed_and_do_not_overlap_in_shape(self):
        _d = P.build_scale_disclosure()
        assert _d.hold_rows and _d.inspect_rows
        assert P.HOLD_SCALE_SHAPE != P.INSPECT_SCALE_SHAPE
        assert "分數" in P.INSPECT_SCALE_SHAPE
        assert "燈號" in P.HOLD_SCALE_SHAPE

    def test_the_degraded_flag_tracks_the_l0_spec(self):
        """repo 現況：財報趨勢標了 `discriminative=False` → 這張卡是 degraded。"""
        assert SPECS_BY_KEY[KEY_STOCK_TREND].discriminative is False, (
            "L0 的前提變了 —— 本測試的其餘斷言要跟著重新確認")
        _d = P.build_scale_disclosure()
        assert _d.degraded is True
        assert P.build_scale_card(_d)[0].state == UI_DEGRADED

    def test_it_goes_back_to_live_when_l0_says_so(self, monkeypatch):
        """**反證**：不是寫死的 degraded —— L0 說正常，它就變回 live。"""
        import dataclasses

        _patched = dict(SPECS_BY_KEY)
        for _k, _s in SPECS_BY_KEY.items():
            if not _s.discriminative:
                _patched[_k] = dataclasses.replace(_s, discriminative=True,
                                                   degraded_reason="")
        monkeypatch.setattr(P, "SPECS_BY_KEY", _patched)
        _d = P.build_scale_disclosure()
        assert _d.degraded is False
        _card = P.build_scale_card(_d)[0]
        assert _card.state == UI_LIVE and _card.value

    def test_the_l0_reason_is_passed_through_verbatim(self):
        """L0 寫的那段原因**原樣透傳**（§2.1：那是 L0 的話，本檔不改寫）。"""
        _d = P.build_scale_disclosure()
        _reasons = [_r for _l, _r in _d.degraded_notes]
        assert SPECS_BY_KEY[KEY_STOCK_TREND].degraded_reason in _reasons

    def test_no_threshold_number_is_written_in_this_page(self):
        """門檻文字一律來自 L0 的 `threshold_text`，本頁不自己描述門檻。"""
        _d = P.build_scale_disclosure()
        for _r in _d.hold_rows + _d.inspect_rows:
            if _r.threshold_text:
                assert _r.threshold_text == (
                    SPECS_BY_KEY[_r.key].threshold_text)

    def test_a_broken_spec_table_is_red_not_silently_empty(self, monkeypatch):
        def _boom(_keys):
            raise RuntimeError("spec table exploded")

        monkeypatch.setattr(P, "_scale_rows", _boom)
        _d = P.build_scale_disclosure()
        assert _d.error and not _d.has_rows
        _card = P.build_scale_card(_d)[0]
        assert _card.state == UI_FAILED
        assert "spec table exploded" in _card.note.why


# ══════════════════════════════════════════════════════════════════
# 【7】Form 結構（鐵律 2 ＋ 線框 F11）
# ══════════════════════════════════════════════════════════════════
def _attr_calls(nodes) -> list[ast.Call]:
    return [_c for _n in nodes for _c in ast.walk(_n)
            if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Attribute)]


class TestFormStructure:
    """本頁的表單輸入**剛好只有一組 radio**，所以直接用共用層 ——

    **能用共用層就不要多開一把尺**（頁 2／頁 3 各自就地實作，是因為它們需要
    `text_input` / `selectbox` / `checkbox`，共用層吃不下）。
    """

    def test_the_page_owns_no_local_form(self):
        _forms = [_c.lineno for _c in _attr_calls([_tree()])
                  if _c.func.attr == "form"]
        assert not _forms, (
            f"本頁自己開了 `st.form`（第 {_forms} 行）—— "
            "本頁應該直接用 `_ui_kit.single_submit_form()`，不寫第四份表單函式")

    def test_it_binds_the_shared_form(self):
        from src.ui.views import _ui_kit as K

        assert P.single_submit_form is K.single_submit_form

    def test_no_submit_button_is_written_here_either(self):
        _bad = [_c.lineno for _c in _attr_calls([_tree()])
                if _c.func.attr == "form_submit_button"]
        assert not _bad, f"submit 應由共用層產生，本頁不該有（第 {_bad} 行）"

    def test_the_page_has_no_stray_button(self):
        """本頁**刻意一顆 `st.button` 都沒有**（含線框 ⑦ 那顆 —— 見 ⑦ 的說明）。"""
        _bad = [f"st.{_c.func.attr} @line {_c.lineno}"
                for _c in _attr_calls([_tree()])
                if _c.func.attr in ("button", "download_button")]
        assert not _bad, f"本頁多了裸按鈕 {_bad} —— 請確認它的 gate 與位置"

    def test_widget_value_is_only_read_by_the_shared_form(self):
        """**鐵律 2 的本體**：下游只准讀已套用值，不准讀 widget 當下值。"""
        _offenders = []
        for _fn in ast.walk(_tree()):
            if not isinstance(_fn, ast.FunctionDef):
                continue
            if _fn.name == "_render_holdings_form":
                continue
            for _s in ast.walk(_fn):
                if isinstance(_s, ast.Name) and _s.id == "SS_SCOPE_WIDGET":
                    _offenders.append(f"{_fn.name}:{_s.lineno}")
        assert not _offenders, (
            f"widget 當下值被表單以外的地方讀了：{_offenders}")

    def test_both_scope_options_have_display_names(self):
        assert set(P.SCOPE_OPTIONS) == set(P.SCOPE_LABELS)
        assert P.SCOPE_OPTIONS[0] == P.SCOPE_MARKET, (
            "預設選項應是**不連 Google** 的那個（最小驚訝 ＋ 最少碰使用者資產）")


class TestFormRunsBeforeItsConsumers:
    """表單在**葉2**、gate 卻被**葉1**消費 —— 執行順序寫反就會「按了沒反應」。

    submit 觸發的那一次 rerun 裡，若葉1 先跑，它讀 session 時 gate 還沒被寫進去，
    戰情室會停在「尚未執行」，而且**不會再自動 rerun** 把它救回來。
    """

    def test_the_form_block_is_rendered_first(self):
        _fn = next(_n for _n in ast.walk(_tree())
                   if isinstance(_n, ast.FunctionDef)
                   and _n.name == "render_page_hold")
        _order: list[str] = []
        for _s in ast.walk(_fn):
            if isinstance(_s, ast.Call) and isinstance(_s.func, ast.Name):
                if _s.func.id in ("_render_setup_form_block",
                                  "_render_warroom_leaf",
                                  "_render_setup_result_block"):
                    _order.append((_s.lineno, _s.func.id))
        _names = [_n for _, _n in sorted(_order)]
        assert _names == ["_render_setup_form_block", "_render_warroom_leaf",
                          "_render_setup_result_block"], (
            f"渲染順序變成 {_names} —— 表單必須先跑，否則 gate 慢一個 rerun")

    def test_the_form_block_does_not_read_the_gate_itself(self):
        """表單那一段**不讀** gate（它只負責寫），避免自己讀到寫入前的舊值。"""
        import inspect

        _s = inspect.getsource(P._render_setup_form_block)
        assert "applied_hold_request" not in _s


# ══════════════════════════════════════════════════════════════════
# 【8】鐵律 1：3 欄上限
# ══════════════════════════════════════════════════════════════════
class TestThreeColumnGrid:

    def test_no_bare_columns_at_all(self):
        _bad = [_n.lineno for _n in ast.walk(_tree())
                if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
                and _n.func.attr == "columns"]
        assert not _bad, (
            f"本頁出現裸 `st.columns`（第 {_bad} 行）—— 一律走 `_ui_kit.grid()`")

    def test_the_six_deep_blocks_go_through_the_grid(self):
        """線框 ⑥ 是**並列**六個區塊 —— 3 欄 × 2 排，不是一排六欄。

        ⚠️ FE-15 接線了「核心／衛星」、FE-19 再接線壓測 / VaR / 配息現金流，
        `DEEP_SPECS` 因此只剩 2 張未接線卡；但**畫面上仍然是六格**
        （接線的那幾張留在原本的位置，不因為先做好就被搬到前面）。
        所以這裡數的是 `build_deep_cards()` 的產出，不是規格表。
        """
        assert len(P.DEEP_SPECS) == 2, "未接線的深度分析卡不是 2 張了"
        assert P.MAX_COLS == 3
        _station = P.StationReadout(requested=False)
        _built = P.build_deep_cards(_station, P.load_deep(_station))
        assert len(_built) == 6, "線框 ⑥ 是六格，接線與否都不改變格數"
        assert [_c.key for _c, _f, _s in _built] == [
            "hold.deep.rebalance", "hold.deep.core_satellite",
            "hold.deep.stress", "hold.deep.var",
            "hold.deep.dividend_cash", "hold.deep.grape"], (
            "⑥ 的順序不是線框那六項 —— 順序照線框，不照完成度")
        _rows = list(P.grid(_built, P.MAX_COLS))
        assert [len(_c) for _c, _cols in _rows] == [3, 3]

    def test_the_conclusion_row_is_three_cards(self):
        assert len(P.build_conclusion_cards(P.StationReadout(requested=False))) == 3


# ══════════════════════════════════════════════════════════════════
# 【9】不得寫死持股百分比（複用 repo 既有守門的 regex，不另立第二把尺）
# ══════════════════════════════════════════════════════════════════
class TestNoHardcodedPositionPct:
    """本頁整頁都在講持股比例，是全 repo 最容易長出硬編碼百分比的地方。

    ⚠️ 判定用的 regex 與過濾器**直接 import repo 既有的守門測試** ——
    自己抄一份會漂移，而漂移的那一份一定是比較鬆的那份。
    """

    def test_this_page_has_no_hardcoded_position_pct(self):
        from tests.test_no_hardcoded_position_pct import _scan

        _hits = _scan(_VIEW)
        assert not _hits, (
            "本頁寫死了持股百分比：\n" + "\n".join(_hits)
            + "\n持股百分比只能來自 `allocation_service.get_allocation()`")

    def test_the_targets_come_from_l0_not_from_literals(self):
        from shared.dividend_station_thresholds import (
            CORE_TARGET_PCT,
            SATELLITE_TAKE_PROFIT_PCT,
            SATELLITE_TARGET_PCT,
        )

        assert P.CORE_TARGET_PCT is CORE_TARGET_PCT
        assert P.SATELLITE_TARGET_PCT is SATELLITE_TARGET_PCT
        assert P.SATELLITE_TAKE_PROFIT_PCT is SATELLITE_TAKE_PROFIT_PCT

    def test_the_position_range_is_passed_through_from_l3(self):
        _card = P.build_position_cap_card(P.AllocationReadout(
            requested=True, is_loaded=True, range_text="30-50%",
            posture="中性偏多"))[0]
        assert _card.value == "30-50%", "本頁重排版了 SSOT 的區間字串"

    def test_the_vix_bands_come_from_l0(self):
        from shared.dividend_station_thresholds import (
            VIX_LIGHT1, VIX_LIGHT2, VIX_LIGHT3)

        _facts = dict(P.build_vix_card(P.VixReadout(requested=False))[1])
        _band = _facts["235 加碼燈的 VIX 門檻"]
        for _v in (VIX_LIGHT1, VIX_LIGHT2, VIX_LIGHT3):
            assert f"{_v:g}" in _band


# ══════════════════════════════════════════════════════════════════
# 【10】訊號頻道 / 渲染邊界
# ══════════════════════════════════════════════════════════════════
class TestSignalChannelAndRenderBoundary:

    def test_no_signal_text_carries_a_glyph(self):
        """鐵律 3：訊號頻道**只出中文標籤**（狀態的 🔴 與燈號的 🔴 是同一顆）。"""
        from src.ui.views._ui_kit import banned_signal_glyphs

        _live_station = P.StationReadout(
            requested=True, submitted=True, bound=True, holdings_n=2,
            rows=({"代號": "0056", "名稱": "高股息"}, {"代號": "2330", "名稱": "台積電"}),
            split={"core_pct": 70.0, "sat_pct": 30.0, "core_dev": -10.0,
                   "total_value": 123456.0, "partial": False,
                   "held_n": 2, "valued_n": 2},
            take_profit=({"代號": "2330", "損益%": 22.0},),
            totals={"pnl_twd": 12345.0, "pnl_pct": 8.1, "value_twd": 234567.0,
                    "held_n": 2, "valued_n": 2, "partial": False},
            add_n=1, cut_n=1, judged=9, total_lights=11, unjudged_rows=1,
            cruise_text="9/11 個依據可用")
        _builts = list(_all_unwired_builts(True)) + [
            P.build_scale_card(P.build_scale_disclosure()),
            *P.build_conclusion_cards(_live_station),
            P.build_lightwall_card(_live_station),
            P.build_allocation_split_card(_live_station),
            P.build_take_profit_card(_live_station),
            *P.build_deep_cards(_live_station, _live_deep()),
            P.build_switch_card(P.SwitchReadout(
                requested=True, submitted=True, stance="defensive",
                switch_out=({"代號": "2330", "建議動作": "汰弱"},),
                switch_in=({"代號": "0056", "名稱": "高股息"},),
                switch_in_src="watchlist", excluded_n=2), _live_station),
            P.build_holdings_preview_card(P.HoldingsReadout(
                requested=True, submitted=True, bound=True,
                holdings=({"ticker": "0056", "held": True, "lots": 3,
                           "avg_price": 35.0, "asset_kind": "etf"},))),
            P.build_vix_card(P.VixReadout(requested=True, vix=18.2)),
            P.build_macro_stage_card(P.MacroReadout(
                requested=True, loaded=True, regime="bull",
                posture_label="積極", defense=False)),
            P.build_position_cap_card(P.AllocationReadout(
                requested=True, is_loaded=True, range_text="30-50%",
                posture="中性偏多")),
            P.build_binding_card(_binding(sheet_bound=True, status="bound")),
        ]
        for _card, _facts, _signal in _builts:
            assert not banned_signal_glyphs(_signal), (
                f"{_card.key} 的 signal_text 帶了符號：{_signal!r}")

    def test_upstream_glyphs_are_scrubbed_before_reaching_the_channels(self):
        """L3 的 `posture_label` 形狀是 `f"{icon} {posture}"` —— icon 必須被洗掉。"""
        assert P._clean_signal("🟢 積極") == "積極"
        assert P._clean_signal("🔴 防禦") == "防禦"
        # ⚠️ 禁用字面集合是**共用層的 SSOT**（L0 狀態 glyph ∪ L0 燈號 emoji），
        #    本測試不自己加字面。`⚪` 不在那兩份 SSOT 裡，所以**刻意不會**被洗掉 ——
        #    要改的話應該改 SSOT，不是在這裡多列一個字元（那就是第二把尺）。
        from src.ui.views._ui_kit import banned_signal_glyphs
        assert not banned_signal_glyphs("⚪")

    def test_the_page_does_not_own_a_fourth_render_copy(self):
        from src.ui.views import _ui_kit as K

        assert not hasattr(P, "render_card"), (
            "`page_hold` 自己持有 render_card 了 —— "
            "渲染期轉紅卡的邏輯只准有一份")
        assert P.render_card_isolated is K.render_card_isolated

    def test_this_page_keeps_its_own_source_and_exit(self):
        import inspect

        _s = inspect.getsource(P._render_one)
        assert 'owner="views/page_hold"' in _s
        assert "SRC_RENDER" in _s and "NO_EXIT_MARKER" in _s

    def test_a_broken_card_becomes_a_red_card_not_half_a_page(self, monkeypatch):
        from src.ui.views import _ui_kit as K

        _md: list[str] = []
        _ns = type("NS", (), {})()
        _ns.markdown = lambda _s, **_k: _md.append(str(_s))
        _ns.caption = lambda _s, **_k: _md.append(str(_s))
        monkeypatch.setattr(K, "st", _ns)

        _calls = {"n": 0}
        _real = K.render_card

        def _boom(card, **kw):
            _calls["n"] += 1
            if _calls["n"] == 1:
                raise RuntimeError("render exploded")
            return _real(card, **kw)

        monkeypatch.setattr(K, "render_card", _boom)
        P._render_one(P.build_lightwall_card(P.StationReadout(requested=False)))
        _all = "\n".join(_md)
        assert "這一格畫不出來" in _all, "半截死頁：例外沒有被轉成看得見的紅卡"
        assert "render exploded" in _all, "原始例外必須看得見（§1）"

    def test_upstream_error_text_is_scrubbed_before_entering_a_note(self):
        """帶 `🔴` 的上游訊息不得把一張該畫的紅卡變成整頁未捕捉例外。"""
        _card = P.build_vix_card(P.VixReadout(
            requested=True, error="RuntimeError('FRED 連線失敗 🔴')"))[0]
        assert _card.state == UI_FAILED
        assert "🔴" not in _card.note.why


# ══════════════════════════════════════════════════════════════════
# 【11】本批接線的那幾張卡：四態不得混（FE-15）
# ══════════════════════════════════════════════════════════════════
def _holdings(**kw) -> P.HoldingsReadout:
    kw.setdefault("requested", True)
    kw.setdefault("submitted", True)
    return P.HoldingsReadout(**kw)


def _station(**kw) -> P.StationReadout:
    kw.setdefault("requested", True)
    kw.setdefault("submitted", True)
    return P.StationReadout(**kw)


#: 本批接線的卡 → 建構它的那一支（給「四態逐一走過」用）。
def _wired_builts(station: P.StationReadout, *, switch=None, holdings=None):
    _sw = switch if switch is not None else P.SwitchReadout(
        requested=station.requested, submitted=station.submitted,
        error=station.error)
    _h = holdings if holdings is not None else P.HoldingsReadout(
        requested=station.requested, submitted=station.submitted,
        bound=station.bound, error=station.error)
    return (P.build_conclusion_cards(station)
            + (P.build_lightwall_card(station),
               P.build_switch_card(_sw, station),
               P.build_allocation_split_card(station),
               P.build_take_profit_card(station),
               P.build_core_satellite_card(station),
               P.build_holdings_preview_card(_h)))


class TestTheWarroomIsWiredNow:
    """FE-15：戰情室 ①③④⑤ ＋ ⑥ 核心衛星 ＋ 葉2 預覽**已接線**。

    ⚠️ 這一類守的是**接線之後才可能出現的說謊方式**：
    「你沒有持股」與「還沒按」與「Google 掛了」被畫成同一種
    —— 而前者對一個新使用者是**每天都會看到**的正常狀態。
    """

    def test_cold_start_every_wired_card_is_idle_not_empty(self):
        """冷啟動：**還沒有人叫過** → 全部灰的 idle，一張都不准是 empty。"""
        for _card, _f, _s in _wired_builts(_station(requested=False,
                                                    submitted=False)):
            assert _card.state == UI_IDLE, f"{_card.key} 冷啟動就是 {_card.state}"
            assert _card.note.now == P.IDLE_NOW, _card.key

    def test_market_only_says_you_chose_not_to_read_google(self):
        """按了、但選「只讀市場端」→ 仍是 idle，**但指路句完全不同**。

        對這種人說「請按下那顆鈕」，他會按了又按 —— 他已經按過了。
        """
        for _card, _f, _s in _wired_builts(_station(requested=False,
                                                    submitted=True)):
            assert _card.state == UI_IDLE, _card.key
            assert _card.note.now == P.GOOGLE_NOT_ASKED_NOW, _card.key
            assert _card.note.now != P.IDLE_NOW
            assert "改成" in _card.note.where, (
                f"{_card.key} 叫使用者去按一顆他已經按過的鈕")

    def test_not_bound_and_empty_sheet_are_two_different_sentences(self):
        """「還沒綁」要你去**綁**、「綁了但空」要你去**填** —— 一句都不可共用。"""
        _unbound = _wired_builts(_station(bound=False))
        _empty = _wired_builts(_station(bound=True))
        for (_c1, _, _), (_c2, _, _) in zip(_unbound, _empty):
            assert _c1.state == _c2.state == UI_EMPTY, _c1.key
            assert _c1.note.now != _c2.note.now, (
                f"{_c1.key}：還沒綁與綁了但空講了同一句話")
            assert _c1.note.where != _c2.note.where, _c1.key
        assert P.NOT_BOUND_NOW in {_c.note.now for _c, _, _ in _unbound}
        assert P.EMPTY_SHEET_NOW in {_c.note.now for _c, _, _ in _empty}

    def test_an_empty_portfolio_is_never_red(self):
        """**一個剛註冊、還沒填任何一列的使用者不該看到紅色。**"""
        for _card, _f, _s in _wired_builts(_station(bound=True)):
            assert _card.state != UI_FAILED, f"{_card.key} 把「空的」畫成了故障"
            assert _card.value == "", f"{_card.key} 沒有值卻給了結論文字"

    def test_an_upstream_failure_is_the_only_red(self):
        """L3 拋例外 → 紅，而且**原始例外看得見**（§1）。"""
        _err = "RuntimeError('Google 502')"
        for _card, _f, _s in _wired_builts(_station(bound=True, error=_err)):
            assert _card.state == UI_FAILED, f"{_card.key} 吞掉了上游的例外"
            assert "Google 502" in _card.note.why, _card.key

    def test_a_holdings_failure_never_shows_half_a_portfolio(self):
        """讀失敗時**整份都不給** —— 半份算出來的比例看起來完全正常。"""
        _h = _holdings(error="RuntimeError('boom')")
        _st = P.load_station(_h)
        assert _st.error and _st.rows == ()
        assert P.build_allocation_split_card(_st)[0].state == UI_FAILED
        assert "半份清單" in P.build_holdings_preview_card(_h)[0].note.where

    def test_take_profit_none_is_grey_and_says_it_is_a_result(self):
        """沒有一檔達停利門檻是**好消息**，不是故障、也不是「還沒算」。"""
        _card = P.build_take_profit_card(_station(
            bound=True, holdings_n=1, rows=({"代號": "2330"},)))[0]
        assert _card.state == UI_EMPTY
        assert "有效的結果" in _card.note.why
        assert "判不了" in _card.note.why, "沒把「沒達標」與「判不了」分開講"

    def test_split_partial_is_disclosed_not_swallowed(self):
        """部分持股缺金額 → **必須把「N 檔裡只算了 M 檔」講出來**。"""
        _facts = dict(P.build_allocation_split_card(_station(
            bound=True, holdings_n=3,
            rows=({"代號": "0056"},),
            split={"core_pct": 60.0, "sat_pct": 40.0, "core_dev": -20.0,
                   "total_value": 1000.0, "partial": True,
                   "held_n": 3, "valued_n": 1}))[1])
        assert any("只算了" in _v for _v in _facts.values()), (
            "部分持股缺金額卻沒有揭露 —— 使用者會把一檔的比例當成整個組合的")

    def test_core_satellite_reuses_the_same_numbers_as_block_five(self):
        """⑥ 的核心／衛星與 ⑤ **同一支 L3、同一份數字**，不得各算一次。"""
        _st = _station(bound=True, holdings_n=2, rows=({"代號": "0056"},),
                       split={"core_pct": 70.0, "sat_pct": 30.0,
                              "core_dev": -10.0, "total_value": 100.0,
                              "partial": False, "held_n": 2, "valued_n": 2})
        _five = P.build_allocation_split_card(_st)[0]
        _six = P.build_core_satellite_card(_st)[0]
        assert _five.state == _six.state == UI_LIVE
        assert "70.0" in _five.value and "70.0" in _six.value
        # 非 live 時兩張卡連文案都必須一致（同一份輸入不得給兩種說法）。
        _empty_five = P.build_allocation_split_card(_station(bound=True))[0]
        _empty_six = P.build_core_satellite_card(_station(bound=True))[0]
        assert _note_triple(_empty_five.note) == _note_triple(_empty_six.note)

    def test_switch_in_candidates_always_exclude_what_you_hold(self, monkeypatch):
        """**本批最重要的一條**：少了 `exclude`，畫面會叫你買你已經有的東西。"""
        import src.services.dividend_station_service as DSS

        _seen: dict = {}

        def _fake_candidates(*, regime=None, exclude=None, top_n=5):
            _seen["regime"] = regime
            _seen["exclude"] = list(exclude or [])
            return [{"代碼": "2412", "名稱": "中華電", "綜合分": 80}]

        monkeypatch.setattr(DSS, "get_switch_in_candidates", _fake_candidates)
        monkeypatch.setattr(DSS, "build_switch_advice",
                            lambda rows, macro, cands: {
                                "switch_out": [], "switch_in": list(cands or []),
                                "switch_in_src": "screener", "stance": "neutral"})
        _h = _holdings(bound=True, holdings=(
            {"ticker": "0056", "held": True, "lots": 1, "avg_price": 30.0},
            {"ticker": "2330.TW", "held": True, "lots": 1, "avg_price": 900.0},
            {"ticker": "2412", "held": False, "lots": None, "avg_price": None}))
        _st = _station(bound=True, holdings_n=3, rows=({"代號": "0056"},))
        _sw = P.load_switch(_st, P.MacroReadout(requested=True, loaded=True,
                                                regime="bull"), _h)
        assert _seen["exclude"] == ["0056", "2330.TW"], (
            "傳給選股池的 exclude 不是「你已持有的代號」 —— "
            f"實際傳了 {_seen.get('exclude')}")
        assert "2412" not in _seen["exclude"], (
            "觀察清單（未持有）被當成已持有排除掉了 —— 那正好把候選也弄丟")
        assert _seen["regime"] == "bull"
        assert _sw.excluded_n == 2
        _facts = dict(P.build_switch_card(_sw, _st)[1])
        assert any("2 檔" in _v for _v in _facts.values()), (
            "卡面沒有把「排除了幾檔」講出來 —— 那就只剩一句沒人能驗證的宣稱")

    def test_switch_does_not_invent_a_stance_when_macro_is_unknown(self):
        """總經未評估 → `stance=unknown`，**不以「中性」代替**（不猜多空）。"""
        _payload = P._macro_payload(P.MacroReadout(requested=True, loaded=False))
        assert _payload["loaded"] is False
        assert _payload["defense"] is None
        _facts = dict(P.build_switch_card(P.SwitchReadout(
            requested=True, submitted=True, stance="unknown",
            switch_out=({"代號": "2330", "建議動作": "汰弱"},)),
            _station(bound=True, holdings_n=1, rows=({"代號": "2330"},)))[1])
        assert any("不猜多空" in _v for _v in _facts.values())

    def test_preview_shows_a_dash_not_zero_for_watchlist_rows(self):
        """觀察清單那些列**沒有**張數／均價 —— 顯示「—」，**不是 0**（§1）。"""
        assert P._fmt_lots(None) == "—"
        assert P._fmt_lots(0) == "0", "真的填 0 時不該被改寫成「—」"
        assert P._fmt_num(None, digits=2) == "—"
        _facts = dict(P.build_holdings_preview_card(_holdings(
            bound=True, holdings=({"ticker": "2412", "held": False,
                                   "lots": None, "avg_price": None},)))[1])
        assert any("本來就沒有" in _v for _v in _facts.values()), (
            "沒有說明觀察清單為什麼沒有張數／均價 —— "
            "使用者會以為是資料掉了")

    def test_the_preview_never_shows_a_sheet_id(self):
        """葉2 的預覽卡與綁定卡同一條線：**一個字元的識別碼都不印。**"""
        _h = _holdings(bound=True, portfolio_name="主組合",
                       holdings=({"ticker": "0056", "held": True,
                                  "lots": 1, "avg_price": 30.0},))
        _card, _facts, _sig = P.build_holdings_preview_card(_h)
        _all = _card.value + " ".join(f"{_k}{_v}" for _k, _v in _facts)
        assert "sheet_id" not in _all.lower()
        assert "sheet_id" not in P.HoldingsReadout.__dataclass_fields__

    def test_a_partial_read_of_the_watchlist_is_never_silent(self):
        """觀察清單那半失敗 → **要講出來**（它會改變換入建議的來源）。"""
        _facts = dict(P.build_holdings_preview_card(_holdings(
            bound=True, watchlist_error="RuntimeError('watchlist gone')",
            holdings=({"ticker": "0056", "held": True, "lots": 1,
                       "avg_price": 30.0},)))[1])
        _txt = " ".join(_facts.values())
        assert "watchlist gone" in _txt and "換入" in _txt

    def test_rows_without_lights_never_claim_the_table_came_back_empty(self):
        """**實跑抓到的假話**：有 3 列回來，畫面卻說「一列都沒有回來」。

        「戰情表沒回來」與「回來了但沒有逐盞燈資料」是兩件事 ——
        後者是舊版結果／上游換形狀，前者才是真的空。
        講錯的那一句**使用者當場就能否證**（他看得到燈牆上有幾列）。
        """
        _st = _station(bound=True, holdings_n=3,
                       rows=({"代號": "0056"}, {"代號": "2330"}),
                       judged=0, total_lights=0)
        _card = P.build_confidence_card(_st)[0]
        assert _card.state == UI_EMPTY
        assert "一列都沒有回來" not in _card.note.now
        assert "重跑" in _card.note.where
        # 燈牆同一輪也不准印一個沒有意義的 0/0。
        assert "0/0" not in P.build_lightwall_card(_st)[0].value

    def test_more_portfolios_are_disclosed(self):
        """只讀第一本 → **必須講**，否則使用者以為畫面上就是他的全部部位。"""
        _facts = dict(P.build_holdings_preview_card(_holdings(
            bound=True, more_portfolios=True, portfolio_name="主組合",
            holdings=({"ticker": "0056", "held": True, "lots": 1,
                       "avg_price": 30.0},)))[1])
        assert any("不是你的全部" in _v for _v in _facts.values())


# ══════════════════════════════════════════════════════════════════
# 【12】新增的那一支 L3 也要唯讀（FE-15）
# ══════════════════════════════════════════════════════════════════
class TestHoldingsServiceIsReadOnly:
    """`src/services/holdings_service.py` —— 它才是真正碰到使用者帳本的那一層。

    ⚠️ 頁面那一類（`TestReadOnly`）證明的是**這一頁沒有寫入的路**；
    但頁面呼叫的 L3 自己會不會寫，**不在它的射程內**。這一類補那個洞。
    ⚠️ 它同樣只證明「靜態文字裡沒有寫入呼叫」，不證明執行時絕不寫 ——
    後者取決於 L1 `gsheet_portfolio` 讀取面的行為（那幾支自陳唯讀 + 讀取快取）。
    """

    def _tree(self):
        import src.services.holdings_service as H

        return ast.parse(pathlib.Path(H.__file__).read_text(encoding="utf-8"))

    def test_no_write_surface_identifier_anywhere(self):
        _hit = sorted(_identifiers(self._tree()) & _WRITE_SURFACE)
        assert not _hit, f"L3 持股 loader 出現了寫入面的識別字 {_hit}"

    def test_only_reader_functions_of_the_gsheet_layer_are_called(self):
        """**白名單**：它只准碰 gsheet 的這幾支讀取函式。"""
        _allowed = {"list_portfolios", "load_portfolio",
                    "list_stock_watchlists", "load_stock_watchlist",
                    "_get_active_stock_sheet_id"}
        _called = {_n.func.attr for _n in ast.walk(self._tree())
                   if isinstance(_n, ast.Call)
                   and isinstance(_n.func, ast.Attribute)
                   and isinstance(_n.func.value, ast.Name)
                   and _n.func.value.id == "_gsp"}
        assert _called <= _allowed, (
            f"L3 持股 loader 碰了讀取面以外的 gsheet 函式：{sorted(_called - _allowed)}")
        assert _called, "一支 gsheet 函式都沒呼叫 —— 白名單形同虛設"

    def test_every_gsheet_read_passes_an_explicit_sheet_id(self):
        """**踩過的坑**：`sheet_id=None` 會讓 `@st.cache_data` 的鍵恆為空 ——

        換一本 Sheet 之後 15 分鐘內會拿到**上一本**的資料（張冠李戴）。
        `portfolio_binding_service` 的註解已經把這個坑寫明白，本檔照辦。
        """
        _need = {"list_portfolios", "load_portfolio",
                 "list_stock_watchlists", "load_stock_watchlist"}
        _bad = [f"{_n.func.attr} @line {_n.lineno}"
                for _n in ast.walk(self._tree())
                if isinstance(_n, ast.Call)
                and isinstance(_n.func, ast.Attribute)
                and _n.func.attr in _need
                and not any(_k.arg == "sheet_id" for _k in _n.keywords)]
        assert not _bad, f"這幾支讀取沒有顯式帶 sheet_id=：{_bad}"

    def test_the_portfolio_half_fails_loud(self):
        """投資組合讀失敗 → **往上拋**，不 best-effort 回半份。

        半份清單算出來的 80/20 與損益看起來完全正常、實際是錯的（§1）。
        """
        import inspect

        import src.services.holdings_service as H

        _src = inspect.getsource(H.get_holdings)
        _head, _sep, _tail = _src.partition("# ── 觀察清單")
        assert _sep, "get_holdings 的兩半結構變了 —— 本條的定位假設要重寫"
        assert "try:" not in _head.split("_state = get_binding_state()")[-1], (
            "投資組合那半被包進 try/except 了 —— 它必須 fail loud")
        assert "except Exception" in _tail, (
            "觀察清單那半不再 best-effort 了 —— 它失敗不該擋住整個戰情室")

    def test_the_watchlist_half_is_never_silently_swallowed(self):
        """觀察清單失敗要**回報**（它會改變換入建議的來源），不是只印 log。"""
        import src.services.holdings_service as H

        assert "watchlist_error" in H.HoldingsResult.__dataclass_fields__

    def test_the_contract_matches_what_the_consumers_expect(self):
        """回傳欄位必須與既有消費端（`dividend_station_service`）同構。"""
        import src.services.holdings_service as H

        _row = H._row("0056", held=True, lots=3, avg_price=35.0)
        assert set(_row) == {"ticker", "name", "held", "asset_kind",
                             "asset_class", "lots", "avg_price"}
        _watch = H._row("2412", held=False)
        assert _watch["lots"] is None and _watch["avg_price"] is None, (
            "觀察清單列被填了 0 —— 那份分頁根本沒有張數與均價（§1 不猜）")


# ══════════════════════════════════════════════════════════════════
# 【13】⑥ 組合深度分析接線之後才可能出現的說謊方式（FE-19）
# ══════════════════════════════════════════════════════════════════
class TestTheDeepAnalysisIsWiredNow:
    """⑥ 的壓力測試 / VaR / 配息現金流**已接線**（L3 `portfolio_deep_service`）。

    ⚠️ 這一類守的是**接線之後**才可能出現的錯：
      · 「還沒按」／「你沒有持股」／「算不出來」／「上游掛了」被畫成同一種；
      · 一格掛掉把另外兩格一起染紅（線框 ⑥：區塊並列 · 逐格獨立判態）；
      · 「不含綜所稅」被吞掉（那會讓「配息」兩個字變成一個假的可支配金額）；
      · **張 → 股 的乘法跑到畫面層**（§4.1 漏乘 = 1000 倍低估）。
    """

    _BUILDERS = ("build_stress_card", "build_var_card",
                 "build_dividend_cash_card")

    @pytest.mark.parametrize("builder", _BUILDERS)
    def test_cold_start_is_idle(self, builder):
        _card = getattr(P, builder)(P.DeepReadout(requested=False))[0]
        assert _card.state == UI_IDLE
        assert _card.note.now == P.IDLE_NOW

    @pytest.mark.parametrize("builder", _BUILDERS)
    def test_market_only_scope_says_it_was_your_choice(self, builder):
        _card = getattr(P, builder)(
            P.DeepReadout(requested=False, submitted=True))[0]
        assert _card.state == UI_IDLE
        assert "沒有發那一次網路呼叫" in _card.note.why

    @pytest.mark.parametrize("builder", _BUILDERS)
    def test_no_holdings_is_grey_not_red(self, builder):
        """新使用者**每天都會看到**這個狀態 —— 它不是故障。"""
        _card = getattr(P, builder)(
            _deep(has_station_rows=False, bound=False, holdings_n=0))[0]
        assert _card.state == UI_EMPTY and _card.state != UI_FAILED
        assert _card.note.now == P.NOT_BOUND_NOW

    @pytest.mark.parametrize("builder", _BUILDERS)
    def test_bound_but_empty_is_a_different_sentence_from_unbound(self, builder):
        _unbound = getattr(P, builder)(
            _deep(has_station_rows=False, bound=False, holdings_n=0))[0]
        _empty = getattr(P, builder)(
            _deep(has_station_rows=False, bound=True, holdings_n=0))[0]
        assert _unbound.state == _empty.state == UI_EMPTY
        assert _unbound.note.now != _empty.note.now, (
            "「還沒綁」與「綁了但空」畫成同一句 —— 指路句完全不同")

    @pytest.mark.parametrize("builder,err_field", list(zip(
        _BUILDERS, ("stress_error", "var_error", "cash_error"))))
    def test_its_own_error_reds_only_itself(self, builder, err_field):
        """**一格掛掉不准染色鄰格。** 三條上游是分開的，狀態也必須分開。"""
        _readout = _live_deep()
        _broken = P.DeepReadout(**{**_readout.__dict__,
                                   err_field: "RuntimeError('boom')"})
        _states = {_b: getattr(P, _b)(_broken)[0].state for _b in self._BUILDERS}
        assert _states[builder] == UI_FAILED
        assert [_s for _b, _s in _states.items() if _b != builder] \
            == [UI_LIVE, UI_LIVE], (
            f"{builder} 掛掉把另外兩格一起染紅了：{_states}")

    @pytest.mark.parametrize("builder", _BUILDERS)
    def test_an_upstream_error_reds_all_three(self, builder):
        """上游（持股／戰情表）掛掉是**另一回事** —— 三格的輸入都沒有了。"""
        _card = getattr(P, builder)(
            P.DeepReadout(requested=True, submitted=True,
                          error="RuntimeError('boom')"))[0]
        assert _card.state == UI_FAILED

    def test_a_computed_zero_is_not_the_same_as_cannot_compute(self):
        """§1：「近一年真的沒配息」與「算不出來」**不是同一件事**。"""
        from src.services.portfolio_deep_service import REASON_NO_LOTS_ROWS

        _no_payout = P.build_dividend_cash_card(
            _deep(cash=_cash_res(gross_twd=0.0, net_after_nhi_twd=0.0,
                                 payouts_n=0)))[0]
        _cannot = P.build_dividend_cash_card(
            _deep(cash=_cash_res(computed=False, gross_twd=0.0, payouts_n=0,
                                 lots_n=0, reason=REASON_NO_LOTS_ROWS)))[0]
        assert REASON_NO_LOTS_ROWS in _cannot.note.why, (
            "算不出來卻沒有把 L3 給的原因印出來 —— 使用者不知道要補什麼")
        assert _no_payout.state == _cannot.state == UI_EMPTY
        assert _no_payout.note.now != _cannot.note.now, (
            "「查過了、真的沒有」與「算不出來」被畫成同一句")
        assert "已經逐檔查過" in _no_payout.note.why
        assert "殖利率回推" in _no_payout.note.why, (
            "沒有講「不用殖利率回推一個數字頂替」—— 那正是這一格最容易造假的地方")

    def test_the_dividend_card_always_says_it_excludes_income_tax(self):
        """**不講就是說謊。** 綜所稅沒算，卻讓人以為那是可支配的錢。"""
        for _readout in (_live_deep(), _deep(cash=_cash_res(payouts_n=0))):
            _card, _facts, _signal = P.build_dividend_cash_card(_readout)
            _text = " ".join(_v for _k, _v in _facts) + " " + " ".join(
                _k for _k, _v in _facts)
            assert "不含綜所稅" in _text, "卡面沒有講「不含綜所稅」"
        assert "不含綜所稅" in P.build_dividend_cash_card(_live_deep())[2], (
            "訊號頻道沒有帶「不含綜所稅」—— 那是這張卡最重要的但書")
        assert "不含綜所稅" in P.WIRING_DISCLOSURE, (
            "常駐的接線揭露也要講 —— 使用者不一定會展開那張卡")

    def test_the_var_card_never_pretends_a_short_sample_is_a_result(self):
        """樣本不足一個月 → 灰的「算不出來」，**不是**一個看起來很小的 VaR。"""
        from src.services.portfolio_deep_service import REASON_SHORT_SAMPLE

        _card = P.build_var_card(_deep(var=_var_res(
            computed=False, reason=REASON_SHORT_SAMPLE, n_common=4,
            hist_95_twd=0.0, hist_99_twd=0.0, monthly_99_twd=0.0,
            monthly_99_pct=0.0)))[0]
        assert _card.state == UI_EMPTY and _card.state != UI_FAILED
        assert _card.value == "", "算不出來卻給了結論文字"
        assert REASON_SHORT_SAMPLE in _card.note.why
        assert "0" not in _card.value

    def test_a_dead_price_source_is_red_but_a_missing_history_is_grey(self):
        """v3 §02：**「還沒有資料」是灰，「上游掛了」是紅** —— 不可混成一種。

        混了的話，Yahoo 掛掉的那一天使用者會以為「我的股票太新」，
        而**真的**壞掉那一次沒有人看得見（假性錯誤的反面：假性正常）。
        """
        from src.services.portfolio_deep_service import REASON_NO_RETURNS

        _grey = P.build_var_card(_deep(var=_var_res(
            computed=False, reason=REASON_NO_RETURNS, hist_95_twd=0.0,
            hist_99_twd=0.0, monthly_99_twd=0.0, monthly_99_pct=0.0,
            no_price=("0056.TW",))))[0]
        assert _grey.state == UI_EMPTY, "「這一檔沒有那段歷史」被畫成紅色了"

        _dead = _var_res(computed=False, reason=REASON_NO_RETURNS,
                         hist_95_twd=0.0, hist_99_twd=0.0, monthly_99_twd=0.0,
                         monthly_99_pct=0.0,
                         fetch_errors=("0056.TW：RuntimeError: yahoo 掛了",))
        assert _dead.upstream_down is True
        assert P.build_var_card(_deep(var=_dead))[0].state == UI_FAILED, (
            "取價那一層整個掛掉卻畫成灰的 —— 真的壞掉那一次就沒有人看得見")

    def test_a_partial_fetch_failure_is_not_called_a_dead_source(self):
        """有一部分抓成功 → **不算掛掉**，只是部分缺料（由 facts 揭露）。"""
        _partial = _var_res(fetch_errors=("2330.TW：RuntimeError: boom",),
                            tickers_used=("0056.TW",))
        assert _partial.upstream_down is False
        assert P.build_var_card(_deep(var=_partial))[0].state == UI_LIVE

    def test_imputed_beta_is_disclosed(self):
        """§1：Beta 是估的就要說 —— 不說的話那個虧損看起來是實測值。"""
        _facts = dict(P.build_stress_card(
            _deep(stress=_stress_res(beta_imputed=("2330.TW",))))[1])
        assert any("2330.TW" in _v and "估" in _v for _v in _facts.values()), (
            "查無 Beta 以 1.0 估算的那幾檔沒有揭示出來")

    def test_partial_coverage_is_disclosed(self):
        """三檔裡只算了一檔的風險數字，不能講得像整個組合的風險。"""
        _facts = dict(P.build_var_card(
            _deep(var=_var_res(valued_n=1, held_n=3)))[1])
        assert any("3 檔持有列裡納入了 1 檔" in _v for _v in _facts.values())

    def test_the_reconciliation_failure_is_surfaced(self):
        """§4.3 對帳：兩套算法對不起來時**畫面要講**，不得靜默採信一邊。"""
        _facts = dict(P.build_stress_card(
            _deep(stress=_stress_res(reconciled=False,
                                     reference_value_twd=999.0)))[1])
        assert any("對不起來" in _k or "對不起來" in _v
                   for _k, _v in _facts.items()), (
            "總市值與 ① 那張卡對不上卻沒有講出來")

    def test_the_page_does_no_lot_to_share_arithmetic_itself(self):
        """**§4.1 的主戰場**：張 → 股的乘法一律住 L3，本頁一個都不准有。

        漏乘 = 1000 倍低估；散在畫面層的乘法遲早會有一處漏掉。
        """
        _lits = [_n.lineno for _n in ast.walk(_tree())
                 if isinstance(_n, ast.Constant)
                 and isinstance(_n.value, (int, float))
                 and not isinstance(_n.value, bool)
                 and float(_n.value) == 1000.0]
        assert not _lits, (
            f"本頁出現了字面 1000（第 {_lits} 行）—— 張→股的換算必須住 L3 "
            "`portfolio_deep_service`（那裡取 L0 `SHARES_PER_LOT`）")
        # 常數名出現在**說明文字**裡是好事（讀者要知道它住哪）；
        # 出現在**程式碼**裡才是問題 —— 引進來就會有人在這裡乘一次。
        assert "SHARES_PER_LOT" not in _identifiers(_tree()), (
            "本頁把張→股的常數當識別字用了 —— 那個乘法只准在 L3 發生")

    def test_an_idle_card_never_claims_a_zero_percent_scenario(self):
        """沒有結果時**不准**印「假設大盤下跌 0 個百分點」——

        那是一個假的情境設定（`getattr(None, 'drop_pct', 0.0)` 的典型後果），
        而且它看起來完全像一個真的設定值。本頁不持有這個門檻，
        它只能由 L0 經 L3 帶下來；帶不下來就不印。
        """
        for _readout in (P.DeepReadout(requested=False),
                         _deep(has_station_rows=False)):
            _facts = dict(P.build_stress_card(_readout)[1])
            assert not any("下跌 0" in _v for _v in _facts.values()), _facts
        _live = dict(P.build_stress_card(_deep(stress=_stress_res()))[1])
        assert any("下跌 20" in _v for _v in _live.values()), (
            "有結果時反而不印情境了 —— 那個跌幅是讀懂這個數字的必要條件")

    def test_a_missing_reason_is_said_out_loud_not_left_blank(self):
        """L3 沒給原因時**要講「上游沒有給訊息」**，不是留一個空句。"""
        _card = P.build_var_card(_deep(var=_var_res(
            computed=False, reason="", hist_95_twd=0.0, hist_99_twd=0.0,
            monthly_99_twd=0.0, monthly_99_pct=0.0)))[0]
        assert _card.state == UI_EMPTY
        assert P.UNKNOWN_ERROR_TEXT in _card.note.why
        assert "—— 。" not in _card.note.why, "留了一個空句"

    def test_the_deep_readout_carries_no_sheet_id(self):
        """同 `BindingReadout`：**結構上**不讓憑證進到這一層。"""
        assert "sheet_id" not in P.DeepReadout.__dataclass_fields__


# ══════════════════════════════════════════════════════════════════
# 【14】⑥ 那一支新 L3 也要唯讀（FE-19，比照 `TestHoldingsServiceIsReadOnly`）
# ══════════════════════════════════════════════════════════════════
class TestPortfolioDeepServiceIsReadOnly:
    """`src/services/portfolio_deep_service.py` —— 頁面那一類管不到它。

    ⚠️ 同 `TestHoldingsServiceIsReadOnly` 的自陳：這只證明「**靜態文字裡沒有
    寫入呼叫**」，不證明執行時絕不寫 —— 後者取決於它呼叫的 L1／L2／L3 的行為。
    """

    def _mod(self):
        import src.services.portfolio_deep_service as D

        return D

    def _tree(self):
        return ast.parse(
            pathlib.Path(self._mod().__file__).read_text(encoding="utf-8"))

    def test_no_write_surface_identifier_anywhere(self):
        _hit = sorted(_identifiers(self._tree()) & _WRITE_SURFACE)
        assert not _hit, f"⑥ 的 L3 出現了寫入面的識別字 {_hit}"

    def test_it_never_touches_the_users_google_sheet_at_all(self):
        """它連**讀**都不該碰 gsheet —— 持股是呼叫端餵進來的。

        碰了就代表同一份持股被讀了兩次（兩次之間可能不一致），
        而且會多打一次 Google（§2.4 快取集中在 L1 的理由）。
        """
        _mods = {(_n.module or "") for _n in ast.walk(self._tree())
                 if isinstance(_n, ast.ImportFrom)}
        _bad = sorted(_m for _m in _mods
                      if "gsheet" in _m or "portfolio_binding" in _m
                      or "oauth" in _m)
        assert not _bad, f"⑥ 的 L3 碰了使用者帳本／授權那一層：{_bad}"

    def test_it_has_no_cache_layer_of_its_own(self):
        """快取集中在 L1（`CLAUDE.md §8.2.A.2` V-SMART-CACHE-1 的同一條理由）。

        ⚠️ 比對的是 **AST**，不是字串：檔頭寫「`@st.cache_data` 集中在 L1」
        是**應該**寫的說明，用字串比對會把說明本身罰掉。
        """
        _decor = [f"line {_d.lineno}"
                  for _fn in ast.walk(self._tree())
                  if isinstance(_fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                  for _d in _fn.decorator_list
                  for _a in ([_d.func] if isinstance(_d, ast.Call) else [_d])
                  if isinstance(_a, ast.Attribute)
                  and _a.attr in ("cache_data", "cache_resource")]
        assert not _decor, f"⑥ 的 L3 自建了快取層：{_decor}"
        _st_imports = [_n.lineno for _n in ast.walk(self._tree())
                       if (isinstance(_n, ast.Import)
                           and any(_a.name.split(".")[0] == "streamlit"
                                   for _a in _n.names))
                       or (isinstance(_n, ast.ImportFrom)
                           and (_n.module or "").split(".")[0] == "streamlit")]
        assert not _st_imports, (
            f"⑥ 的 L3 import 了 streamlit（第 {_st_imports} 行）—— L3 不需要它")

    def test_the_lot_to_share_constant_comes_from_l0(self):
        """§3.3：張→股的 1000 **不得寫死**，一律取自 L0 SSOT。"""
        _src_txt = pathlib.Path(
            self._mod().__file__).read_text(encoding="utf-8")
        assert "SHARES_PER_LOT" in _src_txt
        _lits = [_n.lineno for _n in ast.walk(self._tree())
                 if isinstance(_n, ast.Constant)
                 and isinstance(_n.value, (int, float))
                 and not isinstance(_n.value, bool)
                 and float(_n.value) == 1000.0]
        assert not _lits, (
            f"⑥ 的 L3 出現了字面 1000（第 {_lits} 行）—— 取 L0 `SHARES_PER_LOT`")

    def test_there_is_exactly_one_multiplication_site(self):
        """**單一乘法點**：`SHARES_PER_LOT` 只准出現在 `_lot_to_shares()` 裡。

        散成兩處之後，日後只改一處就是 1000 倍的沉默錯誤。
        """
        _uses = [_n.lineno for _n in ast.walk(self._tree())
                 if isinstance(_n, ast.Name) and _n.id == "SHARES_PER_LOT"]
        assert len(_uses) == 1, (
            f"`SHARES_PER_LOT` 被用在 {len(_uses)} 處（第 {_uses} 行）—— "
            "張→股 只准有一個乘法點")
        import inspect

        _fn = inspect.getsource(self._mod()._lot_to_shares)
        assert "SHARES_PER_LOT" in _fn, "那一處不在 `_lot_to_shares()` 裡"

    def test_the_lot_to_share_math_is_actually_right(self):
        """**數值反證**：2 張 × 50 元 = 100,000 元，不是 100 元。"""
        D = self._mod()
        _rows = [{"代號": "0056", "held": True, "張數": 2.0,
                  "均價": 30.0, "現價": 50.0, "_detail": {}}]
        _priced = D.priced_rows(_rows)
        assert len(_priced) == 1
        assert D._total_value_twd(_priced) == 100_000.0, (
            "漏乘了每張股數 —— 這就是 §4.1 的 1000 倍低估")
        assert D._shares_of(_rows) == [{"ticker": "0056.TW", "shares": 2000.0}]

    def test_it_reconciles_against_the_existing_l3_total(self):
        """§4.3：本檔的總市值與 `compute_portfolio_totals()` 必須對得起來。"""
        D = self._mod()
        _rows = [{"代號": "0056", "held": True, "張數": 2.0,
                  "均價": 30.0, "現價": 50.0, "_detail": {}},
                 {"代號": "2330", "held": True, "張數": 1.0,
                  "均價": 500.0, "現價": 1000.0, "_detail": {}}]
        _ok, _ref = D._reconcile(_rows, D._total_value_twd(D.priced_rows(_rows)))
        assert _ok is True and _ref == 1_100_000.0

    def test_watchlist_rows_are_never_counted_as_zero_lots(self):
        """§1：觀察清單那些列沒有張數 —— **不是持有 0 張、成本 0 元**。"""
        D = self._mod()
        _rows = [{"代號": "2412", "held": False, "張數": None,
                  "均價": None, "現價": None, "_detail": {}},
                 {"代號": "9999", "held": True, "張數": None,
                  "均價": None, "現價": None, "_detail": {}}]
        assert D.priced_rows(_rows) == []
        assert D._shares_of(_rows) == []
        assert D.get_portfolio_stress(_rows).computed is False
        assert D.get_dividend_cash_flow(_rows).computed is False
        assert D.get_portfolio_stress(_rows).loss_twd == 0.0
        assert D.get_portfolio_stress(_rows).reason, "算不出來卻沒有給原因"

    def test_a_failed_row_is_never_valued(self):
        """逐檔抓取失敗的那一列（`_detail.error`）不得進分子也不得進分母。"""
        D = self._mod()
        _rows = [{"代號": "0056", "held": True, "張數": 2.0, "均價": 30.0,
                  "現價": 50.0, "_detail": {"error": "boom"}}]
        assert D.priced_rows(_rows) == [] and D._shares_of(_rows) == []

    def test_the_dividend_call_always_passes_marginal_rate_none(self):
        """**綜所稅刻意不算** —— 傳一個猜的稅率就是替使用者編一筆稅。"""
        _calls = [_n for _n in ast.walk(self._tree())
                  if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
                  and _n.func.id == "get_dividend_tax_view"]
        assert len(_calls) == 1, "配息稅後試算被呼叫了 0 次或多次"
        _kw = {_k.arg: _k.value for _k in _calls[0].keywords if _k.arg}
        assert "marginal_rate" in _kw, "沒有顯式傳 marginal_rate="
        assert isinstance(_kw["marginal_rate"], ast.Constant)
        assert _kw["marginal_rate"].value is None, (
            "傳了一個稅率 —— 那是使用者輸入，本批沒有那個元件（A-8）")
        assert self._mod().DividendCashResult().income_tax_included is False

    def test_none_of_the_three_entry_points_raises_on_junk(self):
        """三支都**不 raise** —— ⑥ 是六個並列格，一格算不出來不該炸整頁。"""
        D = self._mod()
        for _bad in ([], None, [{}], [{"代號": None, "held": True}]):
            assert D.get_portfolio_stress(_bad).computed is False
            assert D.get_portfolio_var(_bad).computed is False
            assert D.get_dividend_cash_flow(_bad).computed is False


# ══════════════════════════════════════════════════════════════════
# 冒煙（slow lane）：這一頁真的畫得出來
# ══════════════════════════════════════════════════════════════════
@pytest.mark.slow
def test_page_mounts_clean(tmp_path):
    """冷啟動整頁 mount：**沒有 uncaught exception、不是半截頁面**。

    ⚠️ 這一條看得到的只有「畫得出來」；它**看不到**畫出來的東西是不是真的 ——
    那些由上面的單元測試守。冷啟動不會發任何 L3 取數（gate 未開），
    所以本條不需要網路。
    """
    import textwrap

    from streamlit.testing.v1 import AppTest

    _script = tmp_path / "_p04_view.py"
    _script.write_text(textwrap.dedent("""
        from src.ui.views.page_hold import render_page_hold
        render_page_hold()
    """), encoding="utf-8")

    _at = AppTest.from_file(str(_script), default_timeout=120)
    _at.run()
    assert not _at.exception, (
        f"page_hold mount 有 uncaught exception: {_at.exception}")

    _all = ("\n".join(_m.value for _m in _at.markdown)
            + "\n" + "\n".join(_c.value for _c in _at.caption))

    # 一顆 submit，而且是唯一一顆按鈕（form 外沒有任何裸按鈕）。
    _labels = [_b.label for _b in _at.button]
    assert _labels == [P.ACTION_RUN_WARROOM_LABEL], f"按鈕變成 {_labels}"

    # 兩套刻度的逐盞對照表真的畫出來了（線框 ②：「就地列出兩者的定義與門檻」）。
    assert len(_at.dataframe) == 2, (
        f"兩套刻度應各有一張對照表，實際 {len(_at.dataframe)} 張")

    # 冷啟動 = idle，**不是** empty、**不是**紅。
    assert P.IDLE_NOW.strip("*") in _all, "冷啟動不是 idle 態"
    assert "你還沒有綁定持股 Sheet" not in _all, (
        "冷啟動就宣稱「你還沒綁」了 —— 那要讀過才知道")
    assert "綁好了，但裡面還沒有任何一本組合" not in _all

    # 常駐揭露（不隨狀態消失）—— 這兩句畫不出來就是半截死頁。
    assert "唯讀宣告" in _all, "唯讀宣告沒畫出來"
    assert "取數接線揭露" in _all, "接線揭露沒畫出來"
    # ② 是常駐的，冷啟動就該看得到它的結論（本 repo 現況為已失準）。
    assert "兩套刻度" in _all


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
