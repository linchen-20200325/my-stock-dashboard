"""找標的／查一檔四處小修（E3-r2、E3-r3、SA-r2、SA-r5②）—— 只刪不加（K1）。

① E3-r2 `page_find._load_shortage` / `_load_rs` 失敗訊息：`repr(e)` → `_safe_msg(e) or UNKNOWN_ERROR_TEXT`
   （同 #711 跨季轉強列）—— 同一張卡的三列用同一種樣式，不再出現「RuntimeError(…)」程式字樣。
② E3-r3 三支 loader 的 log 行不再呼叫 `__repr__`（它自己拋錯會把整頁炸掉）。
③ SA-r2 `VALUATION_WHERE` / `CHIPS_WHERE` 刪句尾「…到資料體檢看…備援鏈是否可用」——
   配息與法人（T86）兩條鏈都沒掛 `@monitored`，資料體檢那面牆上看不到它們。
④ SA-r5② `VALUATION_NO_SOURCE_WHY` 與 v2 短句刪「這一輪」（比照 B9 ⑦ #705）。
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys
import types

import pytest

import src.services.fundamental_screener_service as S
from shared.ui_state import UI_EMPTY
from src.ui.views import page_find as PF
from src.ui.views import page_inspect as P

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    """把 `mod` 原始碼裡每一組 `old` **恰好一處**換成 `new`，載成獨立的新模組。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_p23_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


def _raises(exc):
    def _f(*_a, **_k):
        raise exc
    return _f


def _patch_scans(monkeypatch, exc):
    import src.services.rs_leader_service as RS
    import src.services.shortage_screener_service as SH
    monkeypatch.setattr(SH, "run_shortage_scan", _raises(exc))
    monkeypatch.setattr(RS, "run_rs_leader_scan", _raises(exc))
    monkeypatch.setattr(S, "build_trend_map", _raises(exc))


def _loaders(mod):
    return ((mod._load_shortage, ("shortage",)), (mod._load_rs, ("rs_leader",)),
            (mod._load_trend, ("trend",)))


class _BadStr(RuntimeError):
    def __str__(self):
        raise ValueError("__str__ 自己壞了")


class _BadRepr(RuntimeError):
    def __repr__(self):
        raise ValueError("__repr__ 自己壞了")


# ══════════════════════════════════════════════════════════════════
# ① E3-r2
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("exc, want", [
    (RuntimeError(), PF.UNKNOWN_ERROR_TEXT),
    (RuntimeError("   "), PF.UNKNOWN_ERROR_TEXT),
    (_BadStr(), PF.UNKNOWN_ERROR_TEXT),
    (ValueError("候選池取不到"), "候選池取不到"),
])
def test_shortage_rs_trend_failure_message_is_text_not_repr(monkeypatch, exc, want):
    _patch_scans(monkeypatch, exc)
    for fn, factors in _loaders(PF):
        got, err = fn(factors)
        assert got is None, fn.__name__
        assert err == want and err, (fn.__name__, err)
        assert "Error(" not in err, (fn.__name__, err)


def test_e3r2_mutation_restoring_repr_is_caught(monkeypatch):
    _old = '''        print(f"[views/page_find] 缺貨掃描失敗：{type(_e).__name__}: {_safe_msg(_e)}")
        return None, (_safe_msg(_e) or UNKNOWN_ERROR_TEXT)'''
    m = _mutant(PF, (_old, '''        print(f"[views/page_find] 缺貨掃描失敗：{type(_e).__name__}: {_safe_msg(_e)}")
        return None, repr(_e)'''))
    _patch_scans(monkeypatch, ValueError("候選池取不到"))
    assert m._load_shortage(("shortage",))[1] == "ValueError('候選池取不到')", "突變版應回 repr"
    assert PF._load_shortage(("shortage",))[1] == "候選池取不到"


# ══════════════════════════════════════════════════════════════════
# ② E3-r3
# ══════════════════════════════════════════════════════════════════
def test_exception_whose_repr_raises_does_not_blow_up_the_loaders(monkeypatch, capsys):
    _patch_scans(monkeypatch, _BadRepr("上游掛了"))
    for fn, factors in _loaders(PF):
        assert fn(factors) == (None, "上游掛了"), fn.__name__     # ⛔ 不得拋
    out = capsys.readouterr().out
    assert out.count("_BadRepr: 上游掛了") == 3, out


def test_whole_screen_survives_an_exception_whose_repr_raises(monkeypatch):
    _patch_scans(monkeypatch, _BadRepr("上游掛了"))
    req = PF.ScreenRequest(submitted=True, factors=("shortage", "rs_leader", "trend"))
    try:
        res = PF.load_screen_result(req)
    except ValueError as e:                                     # pragma: no cover
        pytest.fail(f"__repr__ 拋錯把整頁炸掉了：{e}")
    for f in ("shortage", "rs_leader", "trend"):
        assert f in res.factor_input_failed, f


@pytest.mark.parametrize("lbl, fn_name, factors", [
    ("缺貨掃描失敗", "_load_shortage", ("shortage",)),
    ("抗跌 RS 掃描失敗", "_load_rs", ("rs_leader",)),
    ("跨季趨勢計算失敗", "_load_trend", ("trend",)),
])
def test_e3r3_mutation_restoring_repr_in_log_is_caught(monkeypatch, lbl, fn_name, factors):
    _old = f'print(f"[views/page_find] {lbl}：{{type(_e).__name__}}: {{_safe_msg(_e)}}")'
    m = _mutant(PF, (_old, f'print(f"[views/page_find] {lbl}：{{_e!r}}")'))
    _patch_scans(monkeypatch, _BadRepr("上游掛了"))
    with pytest.raises(ValueError, match="__repr__"):
        getattr(m, fn_name)(factors)
    assert getattr(PF, fn_name)(factors) == (None, "上游掛了")


# ══════════════════════════════════════════════════════════════════
# ③ SA-r2
# ══════════════════════════════════════════════════════════════════
#: 修前（baseline `1894b50`）字面（渲染後），逐字抄 —— ⛔ 不由現行常數組出來。
_OLD_VAL_WHERE = (
    "若這一檔近 5 年真的沒有配息，357 這套殖利率法則**本來就不適用它**，重按幾次都一樣 —— "
    "那不是故障，改看健康度與獲利能力那幾格。"
    "配息資料持續抓不到時，到「📖 憑什麼 › 資料體檢」看 FinMind／yfinance／TWSE 三段備援鏈是否可用")
_OLD_CHIPS_WHERE = (
    "按「🔍 載入完整分析」重跑一次；三大法人那一腿常態性地比日線晚到（TWSE 盤後 ~14:30、"
    "完整要等 17:00 後），新上市或長期停牌的標的也可能整段沒有法人資料。"
    "持續如此請到「📖 憑什麼 › 資料體檢」看 TWSE／TPEX／FinMind 的法人備援鏈是否可用")
_VAL_TAIL = "配息資料持續抓不到時，到「📖 憑什麼 › 資料體檢」看 FinMind／yfinance／TWSE 三段備援鏈是否可用"
_CHIPS_TAIL = "持續如此請到「📖 憑什麼 › 資料體檢」看 TWSE／TPEX／FinMind 的法人備援鏈是否可用"


def _monitored_fetchers() -> set[str]:
    """`src/` 底下**真的**掛了 `@monitored` 的函式名（AST，不數字樣）。"""
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


def test_premise_dividend_and_institutional_chains_are_not_on_the_data_health_wall():
    """前提：刪句的理由是「那兩條鏈不在資料體檢牆上」；有人掛上 `@monitored` 時這條會紅。"""
    mon = _monitored_fetchers()
    assert mon, "AST 一支都沒掃到 → 掃描本身壞了"
    for fn in ("fetch_dividend_data", "fetch_price_data", "_get_t86_day", "_get_tpex_day",
               "_fetch_twse_inst_fallback", "_fetch_tpex_inst_fallback"):
        assert fn not in mon, f"{fn} 已掛 @monitored → SA-r2 的刪句前提不再成立，請重評"
    assert not any("dividend" in n or "inst" in n or "t86" in n.lower() for n in mon), mon


def test_where_constants_are_the_old_ones_with_the_tail_deleted():
    assert P.VALUATION_WHERE == _OLD_VAL_WHERE.removesuffix(_VAL_TAIL) != _OLD_VAL_WHERE
    assert P.CHIPS_WHERE == _OLD_CHIPS_WHERE.removesuffix(_CHIPS_TAIL) != _OLD_CHIPS_WHERE
    for w in (P.VALUATION_WHERE, P.CHIPS_WHERE):
        assert "資料體檢" not in w and "備援鏈是否可用" not in w
        assert w.endswith("。"), "在句界截斷，句子要完整"


def test_built_cards_carry_the_trimmed_where():
    val = P.build_valuation_card(P.ValuationReadout(requested=True, price=600.0))
    assert val[0].state == UI_EMPTY and val[0].note.where == P.VALUATION_WHERE
    chips = P.build_chips_card(P.ChipsView(requested=True, signal="⚫ 資料不足",
                                           miss_reason="df法人欄全為0", rows=250, days_loaded=250))
    assert chips[0].state == UI_EMPTY and chips[0].note.where == P.CHIPS_WHERE
    for b in (val, chips):
        P.v2_card_html(*b)                      # 短句摘錄仍對得上（對不上會 KeyError）


def test_sa_r2_mutation_restoring_the_tail_is_caught():
    _old = '    "重按幾次都一樣 —— 那不是故障，改看健康度與獲利能力那幾格。")\n'
    m = _mutant(P, (_old, '    "重按幾次都一樣 —— 那不是故障，改看健康度與獲利能力那幾格。"\n'
                          '    "配息資料持續抓不到時，到"\n'
                          '    f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}"\n'
                          '    "看 FinMind／yfinance／TWSE 三段備援鏈是否可用")\n'))
    assert m.VALUATION_WHERE == _OLD_VAL_WHERE
    assert m.VALUATION_WHERE != P.VALUATION_WHERE


# ══════════════════════════════════════════════════════════════════
# ④ SA-r5②
# ══════════════════════════════════════════════════════════════════
_OLD_NO_SOURCE_WHY = (
    "配息備援鏈（FinMind → yfinance → TWSE）跑完了，**沒有一段給出紀錄**。"
    "那可能是這一檔近 5 年真的沒有配息，也可能是三段這一輪都沒拿到 —— "
    "**上游的回傳值分不出這兩者，本站也不猜**")
_OLD_SHORT = "配息備援鏈…沒有一段給出紀錄…可能是這一檔近 5 年真的沒有配息，也可能是三段這一輪都沒拿到"


def test_no_source_why_and_short_row_drop_this_round():
    assert P.VALUATION_NO_SOURCE_WHY == _OLD_NO_SOURCE_WHY.replace("這一輪", "", 1)
    short = P.V2_SHORT_ROWS[("inspect.stock.valuation", P.VALUATION_EMPTY_NOW)][1][0]
    assert short == _OLD_SHORT.replace("這一輪", "", 1)
    assert "這一輪" not in P.VALUATION_NO_SOURCE_WHY and "這一輪" not in short


def test_no_source_grey_card_face_has_no_this_round():
    b = P.build_valuation_card(P.ValuationReadout(requested=True, price=600.0))
    assert b[0].note.why.startswith(P.VALUATION_NO_SOURCE_WHY.split("**", 1)[0])
    face = P.v2_short_rows(b[0])[0][1][1]
    assert "也可能是三段都沒拿到" in face and "這一輪" not in face
    P.v2_card_html(*b)


def test_sa_r5_mutation_restoring_this_round_is_caught():
    _old = '"那可能是這一檔近 5 年真的沒有配息，也可能是三段都沒拿到 —— "'
    m = _mutant(P, (_old, _old.replace("三段都", "三段這一輪都")))
    assert m.VALUATION_NO_SOURCE_WHY == _OLD_NO_SOURCE_WHY
    assert "這一輪" in m.VALUATION_NO_SOURCE_WHY
