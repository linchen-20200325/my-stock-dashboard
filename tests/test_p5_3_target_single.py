"""tests/test_p5_3_target_single.py — Phase 5 PR3（🎯 標的頁第三區「單一股票」）守衛。

客戶 DEC-107／契約 §12.2（Q 無新增）：判型結果卡 → chip；單一股票先 ≤4 摘要卡＋主圖槽，再「▸ 完整分析」（預設收合、原樣）；
計數 chip「命中 N 項」「未通過／缺漏 M 項」**分開**；⛔ 合成單一結論／評分／HOLD；`UNKNOWN` 灰卡外露；冷啟動零取數。
線框 `docs/vnext/PHASE5_TARGET_PAGE_WIREFRAME_2026-10-31.md` §10 C2-5～C2-9／N1／N2／N3／N4。

寫法同 PR1／PR2：**契約檢查函式**（`_check_*`）＋**mutation 風格守衛**——把實作換成「錯的版本」，契約檢查必須轉紅。
所有字串期望值故意寫成**字面常數**（不引用 `B.*`），常數被改／刪就會紅。
"""
from __future__ import annotations

import re

import pytest

from src.ui.views import _target_blocks as B
from src.ui.views import page_find as F
from src.ui.views import page_inspect as I
from tests import uit_fakes as U
from tests.test_uit_target_page import _all_text, _click, _new

KIND_CHIP_STOCK = "🏢 個股 · 自動判型"
KIND_CHIP_STOCK_MANUAL = "🏢 個股 · 手動指定"
KIND_CHIP_ETF = "ETF · 自動判型"
DETAIL_LABEL = "▸ 判型明細"
FULL_LABEL = "▸ 完整分析（七區塊＋獲利能力診斷）"
CHART_LITERAL = "K 線新版尚未接上"
#: 完整分析內必須逐項存在（資訊只下沉不刪）。
FULL_SECTIONS = ("EPS／營收", "財報體檢（健康度）", "估值（357 存股估值）", "籌碼", "風險", "為什麼值得看",
                 "為什麼不能買／資料不足", "💰 獲利能力診斷")
#: 第三區外露層禁止出現的「合成結論」字樣（C2-6）。
SYNTH_WORDS = ("HOLD", "續抱", "買進", "賣出", "建議買", "綜合結論", "總評", "整體評分", "綜合評等", "綜合判斷")


# ── 元素樹小工具 ───────────────────────────────────────────────────
def _blocks(node, kind):
    for _c in getattr(node, "children", {}).values():
        if type(_c).__name__ == kind:
            yield _c
        if getattr(_c, "children", None):
            yield from _blocks(_c, kind)


def _leaves_outside_expanders(node):
    for _c in getattr(node, "children", {}).values():
        if type(_c).__name__ == "Expander":
            continue
        if getattr(_c, "children", None):
            yield from _leaves_outside_expanders(_c)
        else:
            yield _c


def _exposed(at) -> list[str]:
    _out = []
    for _c in _leaves_outside_expanders(at.main):
        if type(_c).__name__ in ("Caption", "Markdown", "Text", "Error", "Warning", "Info"):
            _v = getattr(_c, "value", None)
            if isinstance(_v, str):
                _out.append(_v)
    return _out


def _zone3_exposed(at) -> list[str]:
    """第三區標題之後、進階分析之前的外露文字（含 Markdown HTML）。"""
    _all = _exposed(at)
    _i = next((i for i, t in enumerate(_all) if "第三區｜單一股票" in t), None)
    assert _i is not None, "找不到第三區標題"
    return _all[_i:]


def _expanders(at, prefix):
    return [e for e in _blocks(at.main, "Expander") if str(e.label).startswith(prefix)]


def _inside_text(exp) -> str:
    _t = []
    for _kind in ("Caption", "Markdown", "Text"):
        _t.extend(c.value for c in _blocks(exp, _kind) if isinstance(getattr(c, "value", None), str))
    return "\n".join(_t)


def _chips_in(texts) -> list[str]:
    """外露層所有 chip span 的文字。"""
    _out = []
    for _t in texts:
        _out.extend(re.findall(r'<span class="cp-chip[^"]*" data-kind="[^"]*">(.*?)</span>', _t))
    return _out


def _tiles(texts) -> list[str]:
    return [t for t in texts if 'class="cp-tile"' in t]


def _go(monkeypatch, ticker="2330", *, screen=True, kind=None, after_install=None, **kw):
    at, calls = _new(monkeypatch, **kw)
    if after_install:
        after_install()          # 假 loader 裝好之後才換（`U.install` 會覆蓋先前的 monkeypatch）
    at.run()
    if screen:
        _click(at, F.ACTION_RUN_SCREEN_LABEL)
    at.text_input(key=I.SS_TICKER_WIDGET).set_value(ticker)
    if kind:
        at.selectbox(key=I.SS_KIND_WIDGET).set_value(kind)
    _click(at, I.ACTION_LOAD_INSPECT_LABEL)
    assert not at.exception, at.exception
    return at, calls


# ══════════════════════════════════════════════════════════════════
# 契約檢查
# ══════════════════════════════════════════════════════════════════
def _check_stock(at, *, hits: int = 2, misses: int = 1, chip_text: str = KIND_CHIP_STOCK) -> None:
    """已選一檔個股（預設假資料：分數 82/A、負債比未通過；已跑選股）的第三區契約。"""
    _z = _zone3_exposed(at)
    _joined = "\n".join(_z)
    # C2-5：判型 chip 外露；原卡下沉到『▸ 判型明細』（L3、預設收合）
    assert chip_text in _chips_in(_z), ("判型 chip 缺", _chips_in(_z))
    for _s in ("判型結果", "判型來源", "系統判型", "這一輪採用"):
        assert _s not in _joined, f"判型明細字樣不得外露：{_s}"
    _det = _expanders(at, DETAIL_LABEL)
    assert len(_det) == 1 and not _det[0].proto.expanded, "『▸ 判型明細』必須恰一個且預設收合"
    assert "判型結果" in _inside_text(_det[0]) or "判型來源" in _inside_text(_det[0]) or any(
        "判型結果" in getattr(c, "value", "") for c in _blocks(_det[0], "Markdown")), "判型明細內必須有原卡"
    # C2-6／C2-7：≤4 摘要卡，標題齊全（357 必帶）
    _t = _tiles(_z)
    assert 1 <= len(_t) <= 4, len(_t)
    _labels = [re.search(r'cp-tile-label">(.*?)</div>', x).group(1) for x in _t]
    assert _labels == ["財報體檢", "357 估值", "近 20 日籌碼"], _labels
    assert any("82 / 100" in x for x in _t) and any("A 級" in x for x in _t), "財報體檢摘要值取自 builder 欄位"
    assert any("殖利率 5.50%" in x for x in _t) and any("集中度 6.30%" in x for x in _t)
    # 計數 chip 分開兩顆
    _chips = _chips_in(_z)
    _hit = [c for c in _chips if c.startswith("✅ 命中 ")]
    _miss = [c for c in _chips if c.startswith("⬜ 未通過／缺漏 ")]
    assert _hit == [f"✅ 命中 {hits} 項"], _hit
    assert _miss == [f"⬜ 未通過／缺漏 {misses} 項"], _miss
    assert not [c for c in _chips if "命中" in c and "缺漏" in c], "命中與缺漏不得合併成同一顆 chip"
    # ⛔ 合成單一結論／評分
    for _w in SYNTH_WORDS:
        assert _w not in _joined, f"第三區外露層出現合成結論字樣：{_w}"
    # 主圖槽：誠實 placeholder
    assert CHART_LITERAL in _joined
    # 完整分析：預設收合、原樣（八項逐一）；且這些區塊標題不得在外露層
    _full = _expanders(at, "▸ 完整分析")
    assert len(_full) == 1 and str(_full[0].label) == FULL_LABEL and not _full[0].proto.expanded
    _in = _inside_text(_full[0])
    for _s in FULL_SECTIONS:
        assert _s in _in, f"完整分析缺：{_s}"
        assert _s not in _joined or _s in ("籌碼", "風險"), f"完整分析區塊不得外露：{_s}"   # 籌碼/風險是摘要卡/其他字的子字串
    for _s in ("**為什麼值得看**", "**為什麼不能買／資料不足**", "**EPS／營收**"):
        assert _s not in _joined
    # 估值摘要卡標題帶 357（口徑與候選表不同）
    assert "357 估值" in _joined
    # 🔍 查看依據保留
    assert _expanders(at, "🔍 查看依據"), "查看依據入口缺"


def _check_unknown(at) -> None:
    _z = "\n".join(_zone3_exposed(at))
    assert "判不出型別 —— 已停在這裡" in _z or "無法判定這是個股還是 ETF" in _z, "UNKNOWN 灰卡必須外露"
    assert "這個代碼系統無法判定是個股或 ETF" in _z, "指路句必須外露"
    assert not _tiles(_zone3_exposed(at)) and not _expanders(at, "▸ 完整分析")


# ══════════════════════════════════════════════════════════════════
# A. 正向
# ══════════════════════════════════════════════════════════════════
class TestStockZone:
    def test_contract_holds(self, monkeypatch):
        at, calls = _go(monkeypatch)
        _check_stock(at)
        assert calls["stock"] == 1 and calls["valuation"] == 1 and calls["chips"] == 1 and calls["profit"] == 1

    def test_manual_kind_chip_says_manual(self, monkeypatch):
        at, _ = _go(monkeypatch, "AAPL", kind=I.KIND_CHOICE_STOCK, screen=False)
        assert KIND_CHIP_STOCK_MANUAL in _chips_in(_zone3_exposed(at))

    def test_no_screen_means_zero_hits_but_misses_still_counted(self, monkeypatch):
        at, _ = _go(monkeypatch, screen=False)
        _c = _chips_in(_zone3_exposed(at))
        assert "✅ 命中 1 項" in _c or "✅ 命中 0 項" in _c    # 無選股列：只剩體檢達標那項
        assert [c for c in _c if c.startswith("⬜ 未通過／缺漏 ")]

    def test_missing_health_is_blank_tile_not_zero(self, monkeypatch):
        at, _ = _go(monkeypatch, stock_score=None)
        _t = _tiles(_zone3_exposed(at))
        _h = [x for x in _t if "財報體檢" in x][0]
        assert "cp-blank" in _h and "/ 100" not in _h and "無資料" in _h, "缺值必須是留白＋原因 chip，不補 0"

    def test_chips_gap_is_grey_blank_tile(self, monkeypatch):
        at, _ = _go(monkeypatch, chips_ok=False)
        _c = [x for x in _tiles(_zone3_exposed(at)) if "近 20 日籌碼" in x][0]
        assert "cp-blank" in _c and "集中度" not in _c and "cp-t-red" not in _c

    def test_failed_leg_tile_is_not_zero_and_error_line_still_exposed(self, monkeypatch):
        at, _ = _go(monkeypatch, chips_error="RuntimeError('日線抓不到')")
        _c = [x for x in _tiles(_zone3_exposed(at)) if "近 20 日籌碼" in x][0]
        assert "cp-blank" in _c and "取得失敗" in _c


class TestOtherKinds:
    def test_etf_chip_three_cards_no_stock_blocks(self, monkeypatch):
        at, calls = _go(monkeypatch, "00878", screen=False)
        _z = _zone3_exposed(at)
        assert KIND_CHIP_ETF in _chips_in(_z)
        assert not _tiles(_z) and not _expanders(at, "▸ 完整分析")
        _t = _all_text(at)
        assert "折溢價" in _t and "配息" in _t and "同儕" in _t and calls["etf"] == 1 and calls["stock"] == 0
        assert len(_expanders(at, DETAIL_LABEL)) == 1

    def test_unknown_grey_card_stays_exposed(self, monkeypatch):
        at, calls = _go(monkeypatch, "AAPL", screen=False)
        assert calls["stock"] == calls["etf"] == 0
        _check_unknown(at)
        assert not at.error
        assert not _expanders(at, DETAIL_LABEL), "UNKNOWN 是真狀態，不得被收進判型明細"

    def test_blank_ticker_card_stays_exposed(self, monkeypatch):
        at, calls = _go(monkeypatch, "  ", screen=False)
        assert "代碼欄是空的" in "\n".join(_zone3_exposed(at)) and sum(calls.values()) == 0


class TestColdStart:
    def test_cold_zero_fetch_and_zone3_idle_only(self, monkeypatch):
        at, calls = _new(monkeypatch)
        at.run()
        assert sum(v for k, v in calls.items() if k in ("stock", "valuation", "chips", "profit", "etf")) == 0
        _z = _zone3_exposed(at)
        assert any("還沒選標的" in t for t in _z)
        assert not _tiles(_z) and not _chips_in(_z) and not _expanders(at, "▸ 完整分析")


# ══════════════════════════════════════════════════════════════════
# B. mutation 風格守衛（拔掉實作，契約檢查必須轉紅）
# ══════════════════════════════════════════════════════════════════
class TestMutationGuards:
    def test_synthetic_conclusion_turns_red(self, monkeypatch):
        _orig = B.render_summary_tiles

        def _bad(single):
            _orig(single)
            B.st.markdown("**綜合結論：HOLD**")
        monkeypatch.setattr(B, "render_summary_tiles", _bad)
        at, _ = _go(monkeypatch)
        with pytest.raises(AssertionError):
            _check_stock(at)

    def test_full_analysis_deleted_turns_red(self, monkeypatch):
        monkeypatch.setattr(B, "render_stock_blocks", lambda single, sb: None)
        at, _ = _go(monkeypatch)
        with pytest.raises(AssertionError):
            _check_stock(at)

    def test_full_analysis_default_expanded_turns_red(self, monkeypatch):
        _orig = B.st.expander

        def _exp(label, *a, **kw):
            if str(label).startswith("▸ 完整分析"):
                kw["expanded"] = True
            return _orig(label, *a, **kw)
        monkeypatch.setattr(B.st, "expander", _exp)
        at, _ = _go(monkeypatch)
        with pytest.raises(AssertionError):
            _check_stock(at)

    def test_full_analysis_exposed_instead_of_folded_turns_red(self, monkeypatch):
        import contextlib
        monkeypatch.setattr(B.st, "expander", lambda label, *a, **kw: contextlib.nullcontext()
                            if str(label).startswith("▸ 完整分析") else _REAL_EXPANDER(label, *a, **kw))
        at, _ = _go(monkeypatch)
        with pytest.raises(AssertionError):
            _check_stock(at)

    def test_unknown_grey_card_removed_turns_red(self, monkeypatch):
        _orig = B._render_built

        def _skip(built):
            if built[0].key in ("inspect.unknown", "inspect.kind"):
                return
            _orig(built)
        monkeypatch.setattr(B, "_render_built", _skip)
        at, _ = _go(monkeypatch, "AAPL", screen=False)
        with pytest.raises(AssertionError):
            _check_unknown(at)

    def test_357_title_missing_turns_red(self, monkeypatch):
        monkeypatch.setattr(B, "SUMMARY_VALUATION_LABEL", "估值")
        at, _ = _go(monkeypatch)
        with pytest.raises(AssertionError):
            _check_stock(at)

    def test_missing_filled_with_zero_turns_red(self, monkeypatch):
        _orig = B._summary_tile

        def _zero(label, value, **kw):
            return _orig(label, "0" if value is None else value, **{k: v for k, v in kw.items() if k == "say"})
        monkeypatch.setattr(B, "_summary_tile", _zero)
        at, _ = _go(monkeypatch, stock_score=None)
        _h = [x for x in _tiles(_zone3_exposed(at)) if "財報體檢" in x][0]
        assert "cp-blank" not in _h, "（mutation 已生效）"
        with pytest.raises(AssertionError):
            assert "cp-blank" in _h and "/ 100" not in _h, "缺值必須是留白"

    def test_cold_fetch_turns_red(self, monkeypatch):
        _orig = B.render_zone_single

        def _bad(session, sb):
            I.load_stock_readout(I.KindVerdict(requested=True, code="2330", is_stock=True))
            return _orig(session, sb)
        monkeypatch.setattr(B, "render_zone_single", _bad)
        at, calls = _new(monkeypatch)
        at.run()
        with pytest.raises(AssertionError):
            assert calls["stock"] == 0, "冷啟動不得取數"

    def test_count_chips_merged_turns_red(self, monkeypatch):
        from src.ui_v2 import compact as cp
        monkeypatch.setattr(B, "count_chips", lambda single, pick: [cp.guard_chip("✅ 命中 2 項／⬜ 未通過／缺漏 1 項")])
        at, _ = _go(monkeypatch)
        with pytest.raises(AssertionError):
            _check_stock(at)

    def test_kind_card_left_exposed_turns_red(self, monkeypatch):
        """判型卡沒 chip 化（整卡外露）→ 紅。"""
        _orig = B.render_chip_row

        def _drop_kind(chips):
            return _orig([c for c in chips if "判型" not in c.text])
        monkeypatch.setattr(B, "render_chip_row", _drop_kind)
        at, _ = _go(monkeypatch)
        with pytest.raises(AssertionError):
            _check_stock(at)


# ══════════════════════════════════════════════════════════════════
# C. 靜態：不新增資料源／公式／門檻
# ══════════════════════════════════════════════════════════════════
class TestStatic:
    def test_no_new_data_or_service_imports(self):
        from pathlib import Path
        _src = (Path(B.__file__)).read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+src\.data", _src, re.M)
        assert not re.search(r"^\s*import requests|^\s*@st\.cache_", _src, re.M)

    def test_summary_tile_values_come_from_builder_fields_only(self):
        """摘要卡主值只能是 builder 的 Card.value／readout 的 score_pct／grade：以假 readout 逐一驗證。"""
        _single = B.SingleBundle(req=None, verdict=I.KindVerdict(requested=True, code="2330", is_stock=True),
                                 stock=U.make_stock(score=61.4, grade="B"), valuation=U.make_valuation(),
                                 chips=U.make_chips())
        _t = B.summary_tiles(_single)
        assert "61 / 100" in _t[0] and "B 級" in _t[0]
        assert "殖利率 5.50%" in _t[1] and "合理" in _t[1]
        assert "集中度 6.30%" in _t[2] and "大戶吸籌" in _t[2]


# ══════════════════════════════════════════════════════════════════
# D. A8：freshness 整句→chip（外露）＋整句逐字下沉（資訊守恆；`TestFreshness` 的字面斷言照舊通過、未放寬）
# ══════════════════════════════════════════════════════════════════
def _check_freshness(at, *, aged: bool) -> None:
    """選股區與單檔區：外露只有 `抓取 10:05`（過 TTL 另有 `⚠ 可能已過期`）；整句在各自『🔍 查看依據』內。"""
    _exp = _exposed(at)
    assert not [t for t in _exp if "此結果載入於" in t], "freshness 整句不得外露"
    _chips = _chips_in(_exp)
    assert _chips.count("抓取 10:05") == 2 + 1, _chips        # 選股＋單檔＋第一區 Primary header
    _stale = [c for c in _chips if c == "⚠ 可能已過期"]
    assert (len(_stale) >= 1) if aged else not _stale, _chips
    _bases = [_inside_text(e) for e in _expanders(at, "🔍 查看依據")]
    for _lab in ("🎯 開始選股", "🔍 載入完整分析"):
        _hit = [t for t in _bases if f"再按「{_lab}」重新載入" in t]
        assert len(_hit) == 1, (_lab, "整句必須恰在一個『查看依據』內")
        assert "本次工作階段內不會自動更新" in _hit[0] and "載入於 10:05" in _hit[0]
        assert ("可能已過期" in _hit[0]) == aged


def _loaded_clock(monkeypatch):
    from tests.test_uit_target_page_qa import _Clock
    at, _ = _new(monkeypatch)
    clock = _Clock()
    monkeypatch.setattr(B, "now_taipei", clock)
    at.run()
    _click(at, F.ACTION_RUN_SCREEN_LABEL)
    _click(at, F.ACTION_LOAD_MAP_LABEL)
    at.text_input(key=I.SS_TICKER_WIDGET).set_value("2330")
    _click(at, I.ACTION_LOAD_INSPECT_LABEL)
    return at, clock


class TestFreshnessChips:
    def test_fresh_then_aged(self, monkeypatch):
        at, clock = _loaded_clock(monkeypatch)
        _check_freshness(at, aged=False)
        clock.advance(seconds=B.FRESH_TTL_SEC["single"] + 60)      # 單檔過 TTL（選股 1 天未到）
        at.run()
        _chips = _chips_in(_exposed(at))
        assert _chips.count("⚠ 可能已過期") >= 1
        _bases = [_inside_text(e) for e in _expanders(at, "🔍 查看依據")]
        assert any("可能已過期" in t and "再按「🔍 載入完整分析」" in t for t in _bases)
        assert not any("可能已過期" in t and "再按「🎯 開始選股」" in t for t in _bases), "選股 TTL 為 1 天，尚未過期"

    def test_pick_note_short_exposed_full_text_in_notes_fold(self, monkeypatch):
        at, _ = _loaded_clock(monkeypatch)
        assert "按「🔍 查看此檔」才取該檔資料。" in _exposed(at)
        _full = "選一檔後按「🔍 查看此檔」才會取這一檔的資料；候選表本身不會自動逐檔取數。"
        assert _full not in _exposed(at)
        assert any(_full in _inside_text(e) for e in _expanders(at, "▸ 說明（"))

    def test_no_exposed_long_sentence_in_zone2_and_zone3(self, monkeypatch):
        at, _ = _loaded_clock(monkeypatch)
        _ok_prefix = ("<", "**", "本次因子", "4 項基本面全過")      # HTML 卡／chip、標題、PR2 條件摘要（既有，量測另列）
        _long = [t for t in _exposed(at) if len(re.sub(r"\s", "", t)) > 32 and not t.startswith(_ok_prefix)
                 and t not in (B.ZONE1_SAY, B.ZONE2_SAY, B.ZONE1_SORT_NOTE)]
        assert not _long, _long

    def test_mutations_turn_red(self, monkeypatch):
        # 1) freshness 整句被丟（不下沉）→ 紅
        monkeypatch.setattr(B, "freshness_text", lambda session, slot: None)
        at, _ = _loaded_clock(monkeypatch)
        with pytest.raises(AssertionError):
            _check_freshness(at, aged=False)

    def test_mutation_sentence_exposed_turns_red(self, monkeypatch):
        _orig = B.render_chip_row

        def _bad(chips):
            B.st.caption("此結果載入於 10:05（本次工作階段內不會自動更新）")
            return _orig(chips)
        monkeypatch.setattr(B, "render_chip_row", _bad)
        at, _ = _loaded_clock(monkeypatch)
        with pytest.raises(AssertionError):
            _check_freshness(at, aged=False)

    def test_mutation_stale_chip_dropped_turns_red(self, monkeypatch):
        monkeypatch.setattr(B, "is_aged", lambda *a, **k: False)
        at, clock = _loaded_clock(monkeypatch)
        clock.advance(seconds=B.FRESH_TTL_SEC["single"] + 60)
        at.run()
        with pytest.raises(AssertionError):
            assert _chips_in(_exposed(at)).count("⚠ 可能已過期") >= 1


# ══════════════════════════════════════════════════════════════════
# E. QA P2：計數 chip 的 M 必須是真項數；三塊全未評估 ⇒ `⬜ 尚未評估`（missing≠0）
# ══════════════════════════════════════════════════════════════════
def _all_none(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("上游炸了")
    monkeypatch.setattr(I, "load_stock_readout", _boom)
    monkeypatch.setattr(I, "load_chips", _boom)
    monkeypatch.setattr(I, "load_profitability", _boom)


def _miss_chip(at):
    return [c for c in _chips_in(_zone3_exposed(at)) if c.startswith("⬜ 未通過／缺漏 ")]


class TestCountChipsHonest:
    def test_m_is_real_item_count_not_fact_rows(self, monkeypatch):
        # 3 項體檢未通過＋籌碼判不出來（1 項缺漏）＝4；`why_not_facts` 只有 2 列
        monkeypatch.setattr(U, "make_stock", lambda **kw: I.StockReadout(
            requested=True, score_pct=40.0, grade="C", fail_items=("負債比", "流動比", "毛利率"), name="台積電",
            price=900.0, price_asof=I.PAL.PriceAsOf(as_of=__import__("datetime").date(2026, 10, 28), src="yfinance")))
        at, _ = _go(monkeypatch, chips_ok=False)
        assert _miss_chip(at) == ["⬜ 未通過／缺漏 4 項"], _miss_chip(at)

    def test_why_not_count_unit(self):
        _s = I.StockReadout(requested=True, score_pct=40.0, fail_items=("a", "b", "c"), price=1.0)
        _b = B.SingleBundle(req=None, verdict=I.KindVerdict(requested=True, code="2330", is_stock=True), stock=_s)
        assert len(B.why_not_facts(_b)) == 1 and B.why_not_count(_b) == 3

    def test_all_unevaluated_shows_not_evaluated_not_zero(self, monkeypatch):
        at, _ = _go(monkeypatch, after_install=lambda: _all_none(monkeypatch))
        _c = _chips_in(_zone3_exposed(at))
        assert "⬜ 尚未評估" in _c, _c
        assert not [x for x in _c if x.startswith("✅ 命中") or x.startswith("⬜ 未通過／缺漏")], _c

    def test_mutation_row_count_instead_of_item_count_turns_red(self, monkeypatch):
        monkeypatch.setattr(B, "why_not_count", lambda single: len(B.why_not_facts(single)))
        monkeypatch.setattr(U, "make_stock", lambda **kw: I.StockReadout(
            requested=True, score_pct=40.0, grade="C", fail_items=("負債比", "流動比", "毛利率"), name="台積電", price=900.0))
        at, _ = _go(monkeypatch, chips_ok=False)
        with pytest.raises(AssertionError):
            assert _miss_chip(at) == ["⬜ 未通過／缺漏 4 項"]

    def test_mutation_zero_shown_when_unevaluated_turns_red(self, monkeypatch):
        from src.ui_v2 import compact as cp
        monkeypatch.setattr(B, "count_chips", lambda single, pick: [cp.guard_chip("✅ 命中 0 項"),
                                                                    cp.guard_chip("⬜ 未通過／缺漏 0 項")])
        at, _ = _go(monkeypatch, after_install=lambda: _all_none(monkeypatch))
        with pytest.raises(AssertionError):
            assert "⬜ 尚未評估" in _chips_in(_zone3_exposed(at))


class TestPartialUnevaluated:
    @staticmethod
    def _partial(monkeypatch):
        def _boom(*a, **k):
            raise RuntimeError("上游炸了")
        monkeypatch.setattr(I, "load_chips", _boom)
        monkeypatch.setattr(I, "load_valuation", _boom)

    def test_partial_none_adds_explicit_not_evaluated_chip(self, monkeypatch):
        at, _ = _go(monkeypatch, after_install=lambda: self._partial(monkeypatch))
        _c = _chips_in(_zone3_exposed(at))
        assert "⬜ 2 塊尚未評估" in _c, _c
        assert [x for x in _c if x.startswith("✅ 命中")] and [x for x in _c if x.startswith("⬜ 未通過／缺漏")]
        assert "⬜ 尚未評估" not in _c

    def test_all_present_has_no_not_evaluated_chip(self, monkeypatch):
        at, _ = _go(monkeypatch)
        assert not [x for x in _chips_in(_zone3_exposed(at)) if "尚未評估" in x]

    def test_mutation_partial_chip_dropped_turns_red(self, monkeypatch):
        _orig = B.count_chips
        monkeypatch.setattr(B, "count_chips", lambda single, pick: [c for c in _orig(single, pick) if "尚未評估" not in c.text])
        at, _ = _go(monkeypatch, after_install=lambda: self._partial(monkeypatch))
        with pytest.raises(AssertionError):
            assert "⬜ 2 塊尚未評估" in _chips_in(_zone3_exposed(at))


_REAL_EXPANDER = B.st.expander
