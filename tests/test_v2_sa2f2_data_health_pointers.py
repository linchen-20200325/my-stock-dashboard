"""SA-r2-f2（2026-09-27）：v2 頁的「去哪補」⛔ 不得指向資料體檢看**不到**的鏈。

資料體檢那面牆只列掛了 `@monitored` 的 fetcher（L0 `shared/fetch_monitor.get_monitor_registry()`）。
下列卡片的取數鏈（個股報價 `StockDataLoader`／財報／配息／T86 法人／ETF `etf_fetch`／
Google Sheet／VIX `fetch_yf_close`／熱力圖 `_fetch_sector_returns`）一支都沒掛 ⇒
「細節在資料體檢」是指向不存在的地方，已在子句界刪掉（只刪不改；同 SA-r2 #718／SA-r2-f1 #723）。
仍保留的指路（「🚦 今天」總經燈、「📖 憑什麼」頁自身）其鏈含 `@monitored` fetcher，不在本檔範圍。
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from shared.ui_state import UI_EMPTY, UI_FAILED
from src.ui.views import page_find as PF
from src.ui.views import page_hold as PH
from src.ui.views import page_inspect as P

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_DH = "資料體檢"

# ── ① 常數：刪後的逐字值（舊值＝新值＋被刪的那一段）─────────────────────────
_CONSTS = {
    "page_hold.STATION_ERROR_WHERE": (
        PH.STATION_ERROR_WHERE,
        "先確認網路與 Google 授權是否仍有效；持續失敗請把上面那行訊息回報給維護者"),
    "page_hold.VIX_RETRY_WHERE": (PH.VIX_RETRY_WHERE, None),
    "page_find.HEATMAP_FAILED_WHERE": (PF.HEATMAP_FAILED_WHERE, None),
    "page_inspect._V2_CHECK_NET": (P._V2_CHECK_NET, "先確認代碼與網路／proxy"),
}


@pytest.mark.parametrize("name", sorted(_CONSTS))
def test_constant_no_longer_points_to_data_health(name):
    val, exact = _CONSTS[name]
    assert _DH not in val and "來源狀態" not in val, f"{name} 仍指向資料體檢：{val!r}"
    if exact is not None:
        assert val == exact
    assert not val.endswith(("；", "，", "到", "在")), f"{name} 截斷處不在子句界：{val!r}"


# ── ② 函式體：這些 builder 不得再引用資料體檢的 ia_nav 目標 ─────────────────
_FUNCS = [
    (P, "build_health_card"), (P, "build_valuation_card"), (P, "build_chips_card"),
    (P, "build_profit_cards"), (P, "_etf_card"), (P, "build_dividend_card"),
    (P, "build_peer_card"), (PH, "build_binding_card"), (PH, "build_portfolio_count_card"),
    (PH, "build_vix_card"), (PF, "build_heatmap_card"),
]


@pytest.mark.parametrize("mod,fn", _FUNCS, ids=[f"{m.__name__.rsplit('.', 1)[1]}.{f}" for m, f in _FUNCS])
def test_builder_body_has_no_data_health_pointer(mod, fn):
    src = inspect.getsource(getattr(mod, fn))
    assert "SECTION_WHY_DATA_HEALTH" not in src and "_V2_DATA_HEALTH" not in src, f"{fn} 仍指向資料體檢"


# ── ③ 實際畫出來的卡（紅／灰態）＋ 卡面短句 ────────────────────────────────
def _inspect_cards():
    err = "boom"
    yield "health.failed", P.build_health_card(P.StockReadout(requested=True, error=err))
    _raised = "RuntimeError('boom')"
    yield "valuation.failed", P.build_valuation_card(
        P.ValuationReadout(requested=True, error=P._error_why(P.SRC_DIVIDENDS, _raised)))
    yield "chips.failed", P.build_chips_card(
        P.ChipsView(requested=True, error=P._error_why(P.SRC_CHIPS, _raised)))
    for i, b in enumerate(P.build_profit_cards(P.ProfitabilityReadout(
            requested=True, error=P._error_why(P.SRC_STATEMENTS, _raised)))):
        yield f"profit.failed.{i}", b
    _etf_err = P.EtfReadout(requested=True, error=err)
    _etf_empty = P.EtfReadout(requested=True)
    for f in (P.build_premium_card, P.build_dividend_card, P.build_peer_card):
        yield f"{f.__name__}.failed", f(_etf_err)
    yield "dividend.empty", P.build_dividend_card(_etf_empty)
    yield "peer.empty", P.build_peer_card(_etf_empty)


_CARDS = dict(_inspect_cards())


@pytest.mark.parametrize("name", sorted(_CARDS))
def test_inspect_cards_where_and_face_do_not_point_to_data_health(name):
    built = _CARDS[name]
    card = built[0]
    assert card.state in (UI_FAILED, UI_EMPTY), (name, card.state)
    assert _DH not in card.note.where, f"{name} 去哪補仍指向資料體檢：{card.note.where!r}"
    html = P.v2_card_html(*built)                # 短句摘錄仍對得上（對不上會 KeyError）
    assert _DH not in html, f"{name} 卡面仍出現資料體檢"


def test_inspect_v2_short_rows_have_no_data_health():
    bad = [k for k, v in P.V2_SHORT_ROWS.items() if _DH in repr(v)]
    assert not bad, bad


def test_hold_binding_failed_where():
    card = PH.build_binding_card(PH.BindingReadout(requested=True, error="boom"))[0]
    assert card.state == UI_FAILED and card.note.where == "先確認網路與 Google 授權是否仍有效"


# ── ④ 前提守衛：這些鏈哪天掛上 `@monitored`，刪句的理由就不成立 → 紅燈，請重評 ─────
def _monitored_fetchers() -> set[str]:
    names: set[str] = set()
    for f in (_ROOT / "src").rglob("*.py"):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:                                     # pragma: no cover
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for d in node.decorator_list:
                    _t = d.func if isinstance(d, ast.Call) else d
                    if getattr(_t, "id", None) == "monitored" or getattr(_t, "attr", None) == "monitored":
                        names.add(node.name)
    return names


_UNMONITORED_CHAINS = (
    # 個股報價／財報／配息／T86
    "get_combined_data", "fetch_financial_statements", "fetch_dividend_data", "fetch_price_data",
    "_get_t86_day", "_get_tpex_day",
    # ETF
    "fetch_etf_price", "fetch_etf_dividends", "fetch_etf_info", "_fetch_sector_returns",
    # VIX／熱力圖／Google Sheet
    "fetch_yf_close", "fetch_vix",
)


@pytest.mark.parametrize("fn", _UNMONITORED_CHAINS)
def test_premise_chain_is_not_on_the_data_health_wall(fn):
    mon = _monitored_fetchers()
    assert mon, "AST 一支都沒掃到 → 掃描本身壞了"
    assert fn not in mon, f"{fn} 已掛 @monitored → SA-r2-f2 的刪句前提不再成立，請重評是否補回指路"


def test_premise_no_gsheet_fetcher_is_monitored():
    assert not any("sheet" in n.lower() or "portfolio" in n.lower() for n in _monitored_fetchers())
