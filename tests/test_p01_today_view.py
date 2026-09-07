"""tests/test_p01_today_view.py — FE-4 修復組的**回歸釘子**（IA v2 第 1 頁 view）。

守的是 `src/ui/views/page_today.py` ＋ `src/ui/views/_ui_kit.py`，
而**每一條測試對應一個紅隊 / 稽核實測抓到的 bug**，不是憑空補的覆蓋率：

  · `TestTwoLightsFailIndependently`  ← 【1】§1 造假：regime 失敗連坐危險度，
    而且畫面上印出「16 盞燈…」這種**這一輪根本沒算過**的結論。
  · `TestRequestedIsAGateNotATautology` ← 【2】`requested=` 恆真式：
    `get_allocation()` 永不回 `None` ⇒ 卡①② 在真實 render path 上沒有 idle 態。
  · `TestSidecarCannotOverrideSSOT`    ← 【3】側車一筆就能把
    `wired=False` 的燈畫成「🟢 運作中」，而 L0 SSOT 一個字沒動。
  · `TestLiveCardKeepsItsNote`         ← 【6】`live` 態帶 `Note` 被靜默丟棄
    → 使用者看到一張標「正常」的**空白卡**。
  · `TestSignalChannelFailsAtBuildTime` ← 【7】渲染期才炸 ⇒ **半截死頁**。
  · `TestColdStartCoverage` / `TestDenominatorIsAlwaysSixteen`
    ← 分母與冷啟動的誠實呈現（未接線 / 已失準**不得**被藏出分母）。
  · `TestErrorSaysTheRightLayer`       ← 【8b】對使用者謊報出事的層。
  · `TestKeyBannerRedIsOnTheSignalChannel` ← 【8c】有紅的那天狀態 chip 仍是 🟢。
  · `TestUpstreamKeyListMatchesTheLoader`  ← 【8a】清單宣稱與實際不一致。

⚠️ **這些是護欄，不是證明**（同 `tests/test_ui_state_model.py` 的自陳）：
它們釘住的是「已知的那幾種說謊方式不會再回來」，
**不是**「這一頁不會再說謊」。全綠不等於合規。
"""
from __future__ import annotations

import pytest

from shared.macro_buckets import BUCKET_DANGER_SPECS, SPECS_BY_KEY
from shared.regime_arbiter import SOURCE_FILE_RULE_ENGINE, SOURCE_UNLOADED
from shared.ui_state import (
    UI_DEGRADED,
    UI_FAILED,
    UI_IDLE,
    UI_LIVE,
    UI_UNWIRED,
)
from src.ui.tabs.tab_today import Card, Note
from src.ui.views import _ui_kit as K
from src.ui.views import page_today as P

# ── 測試用的最小替身 ──────────────────────────────────────────────
#: L4 `macro_v2_cards.BAND_META` 的形狀（band → (中文, 色碼)）。
#: 這裡**不是**在複寫 SSOT：本檔只驗「呼叫端有沒有把它接上去」，
#: 字面正確與否由 L4 自己的測試守（`tests/test_macro_v2_tab.py`）。
BANDS = {"green": ("綠", "#0ca30c"), "yellow": ("黃", "#fab219"),
         "red": ("紅", "#d03b3b"), "gray": ("無資料", "#8a8e96")}

LIVE_REGIME = {"regime": "bull", "light": "🟢", "source": "warroom",
               "is_loaded": True}
COLD_REGIME = {"regime": "unknown", "light": "⬜", "source": SOURCE_UNLOADED,
               "is_loaded": False}


class _Alloc:
    """`AllocationDecision` 的最小替身。

    ⚠️ 關鍵：`services.allocation_service.get_allocation()` 的 return 只有
    `return _cached` / `return _decision` —— **它永不回 `None`**。
    未評估時它回的是一個 `is_loaded=False` 的**物件**，不是 `None`。
    修前的 `requested=(bool(alloc_error) or alloc is not None)` 就是死在這裡。
    """

    def __init__(self, *, is_loaded: bool) -> None:
        self.is_loaded = is_loaded
        self.range_text = "30-50%" if is_loaded else "--"
        self.posture = "中性偏多" if is_loaded else "未評估"
        self.drivers = ("總經健康分 62 → 姿態「中性偏多」",) if is_loaded else ()
        self.cap_text = ""
        self.conflicts = ()


def _tiles(**kw):
    """`build_verdict_tiles` 的呼叫殼：把三張卡收成 `{key: Tile}`。"""
    _base = dict(alloc=_Alloc(is_loaded=False), alloc_error="",
                 danger=None, danger_error="", danger_requested=False,
                 regime=COLD_REGIME, regime_error="", band_zh_color=BANDS)
    _base.update(kw)
    return {_t.card.key: _t for _t in P.build_verdict_tiles(**_base)}


# ══════════════════════════════════════════════════════════════════
# 【1】兩顆燈各自失敗（§1：不得顯示一個沒發生過的計算的結論）
# ══════════════════════════════════════════════════════════════════
class TestTwoLightsFailIndependently:
    """紅隊實測：`_load_parallel` 開頭 `if regime is None: return None, ""`。

    危險度那一半（`build_rows`→`bucket_summary`→`overall_verdict`）
    **完全不依賴 regime**，卻被 regime 的失敗連坐；更糟的是畫面上講的理由
    指向 16 盞燈，而那 16 盞燈**這一輪根本沒被算過**。
    """

    def test_regime_failure_does_not_take_down_the_danger_card(self):
        _t = _tiles(alloc=None, alloc_error='RuntimeError("boom")',
                    danger=("red", "2 桶紅"), danger_requested=True,
                    regime=None, regime_error='RuntimeError("boom")')
        assert _t["verdict.danger"].card.state == UI_LIVE, (
            "位階掛掉不得連坐危險度 —— 危險度那一半完全不吃 regime")
        assert _t["verdict.danger"].card.value == "2 桶紅"
        assert _t["verdict.danger"].signal_text == "紅"

    def test_danger_failure_does_not_take_down_the_regime_card(self):
        """反方向同樣是說謊：位階明明 live，卻被畫成「尚未評估」。"""
        _t = _tiles(danger=None, danger_error="ImportError('tab_macro_v2')",
                    danger_requested=True, danger_source=P.SRC_DANGER,
                    regime=LIVE_REGIME, alloc=_Alloc(is_loaded=True))
        assert _t["verdict.regime"].card.state == UI_LIVE
        assert _t["verdict.regime"].card.value == "多頭"
        assert _t["verdict.danger"].card.state == UI_FAILED

    def test_a_computation_that_never_ran_is_never_quoted_as_a_reason(self):
        """**這一條是【1】的核心。**

        修前：regime 掛掉 → 卡② `state=idle`，理由卻寫
        「16 盞燈本輪一盞都沒有落在綠 / 黃 / 紅 —— 也就是沒有資料可彙總」。
        那 16 盞燈**這一輪沒有被算過**，那句話是憑空捏造的結論（§1）。
        """
        _t = _tiles(alloc=None, alloc_error='RuntimeError("boom")',
                    danger=None, danger_error="", danger_requested=False,
                    regime=None, regime_error='RuntimeError("boom")')
        _card = _t["verdict.danger"].card
        assert _card.state == UI_IDLE
        assert "一盞都沒有落在" not in _card.note.why, (
            "沒有算過 16 盞燈的那一輪，不得宣稱『16 盞燈都沒落在綠/黃/紅』")
        assert "連 16 盞燈都沒有算" in _card.note.why

    def test_the_all_grey_sentence_is_still_available_when_it_is_true(self):
        """真的算過、而且 16 盞全灰時，那句話仍然要出得來（不是把它刪掉了事）。"""
        _t = _tiles(danger=("gray", "尚未載入資料"), danger_requested=True)
        _card = _t["verdict.danger"].card
        assert _card.state != UI_LIVE
        assert "一盞都沒有落在" in _card.note.why

    def test_loader_no_longer_takes_regime_at_all(self):
        """`_load_danger()` 的簽名裡**不准**再出現 regime。"""
        import inspect

        assert "regime" not in inspect.signature(P._load_danger).parameters
        assert not hasattr(P, "_load_parallel"), (
            "`_load_parallel` 已被 `_load_danger` 取代；留著會有人再接回去")

    def test_loader_reports_the_five_bucket_failure_as_its_own_source(self):
        """五桶那一輪就炸了 → 錯誤與**出處**照實帶下去，不改寫成「沒資料」。"""
        _r = P.MacroReadout(requested=True, error="ImportError('macro_helpers')")
        _d, _err, _src = P._load_danger(_r)
        assert _d is None and _err == "ImportError('macro_helpers')"
        assert _src == P.SRC_FIVE_BUCKET


# ══════════════════════════════════════════════════════════════════
# 【2】`requested=` 是 gate 旗標，不是恆真式
# ══════════════════════════════════════════════════════════════════
class TestRequestedIsAGateNotATautology:
    """`tests/test_ui_state_model.py` 的 AST 守衛抓不到這個 —— 它只比對

    `requested=` 與 `has_value=` 的運算式是否**逐字相同**，
    而 `alloc is not None` 與 `bool(alloc.is_loaded)` 逐字不同、卻恆真。
    **守衛綠燈不是合規證明**（該測試 docstring 自陳「是護欄不是證明」）。
    """

    def test_cold_start_gives_idle_not_empty_for_exposure(self):
        _t = _tiles(alloc=_Alloc(is_loaded=False), regime=COLD_REGIME)
        assert _t["verdict.exposure"].card.state == UI_IDLE, (
            "冷啟動＝『還沒有人叫』(idle)，不是『叫了沒回』(empty)")

    def test_cold_start_gives_idle_not_empty_for_danger(self):
        _t = _tiles(danger=None, danger_requested=False)
        assert _t["verdict.danger"].card.state == UI_IDLE

    def test_an_alloc_object_alone_does_not_make_it_requested(self):
        """**恆真式的直接反證**：物件在（永遠在），但沒有人叫過 → 仍是 idle。"""
        assert _Alloc(is_loaded=False) is not None      # 前提：它不是 None
        assert _tiles()["verdict.exposure"].card.state == UI_IDLE

    def test_once_the_contract_was_attempted_it_is_no_longer_idle(self):
        """上游真的算過（`source != unloaded`）→ 離開 idle。"""
        _snap = dict(COLD_REGIME, source=SOURCE_FILE_RULE_ENGINE, is_loaded=True)
        assert P.contract_attempted(_snap) is True
        assert P.contract_attempted(COLD_REGIME) is False
        assert P.contract_attempted(None, error='RuntimeError("x")') is True

    def test_gate_comes_from_the_contract_branch_marker(self):
        """gate 旗標讀的是上游自己標的 `source`，不是資料的有無。"""
        _t = _tiles(alloc=_Alloc(is_loaded=True),
                    regime=dict(LIVE_REGIME), danger=("green", "五桶全綠"),
                    danger_requested=True)
        assert _t["verdict.exposure"].card.state == UI_LIVE
        assert _t["verdict.exposure"].card.value == "30-50%"


# ══════════════════════════════════════════════════════════════════
# 【3】側車不得覆寫 L0 SSOT
# ══════════════════════════════════════════════════════════════════
class TestSidecarCannotOverrideSSOT:
    """紅隊只改側車一筆、L0 一個字沒動：

        rd["foreign_net"].update(wired=True, state="ok", value=100.0, reason=None)

    修前畫面變成「🟢 運作中 ｜ 綠 ｜ 100億」、coverage `4／16（未接線 0）`，
    而 `SPECS_BY_KEY["foreign_net"].wired` 仍然是 `False`。
    """

    def test_sidecar_cannot_turn_an_unwired_light_on(self):
        _spec = SPECS_BY_KEY["foreign_net"]
        assert _spec.wired is False, "前提變了：這條測試要換一盞未接線的燈"
        _rec = {"wired": True, "discriminative": True, "state": "ok",
                "value": 100.0, "reason": None}
        assert P.indicator_state(_rec, _spec, requested=True, error="") == UI_UNWIRED

    def test_sidecar_cannot_hide_a_degraded_threshold(self):
        _spec = SPECS_BY_KEY["margin"]
        assert _spec.discriminative is False, "前提變了：換一盞已失準的燈"
        _rec = {"wired": True, "discriminative": True, "state": "ok",
                "value": 3000.0, "reason": None}
        assert P.indicator_state(_rec, _spec, requested=True, error="") == UI_DEGRADED

    def test_the_attack_does_not_move_the_coverage_numbers(self):
        """整條路徑（tile → coverage）都不得被側車帶偏。"""
        _rd = {"foreign_net": {"wired": True, "discriminative": True,
                               "state": "ok", "value": 100.0, "reason": None}}
        _cov = P.coverage(P.build_indicator_tiles(
            P.MacroReadout(requested=True, readiness=_rd)))
        assert _cov.unwired == 1, "未接線不得被側車抹掉"
        assert _cov.live == 0, "一盞未接線的燈不得因為側車有值就變成『運作中』"

    def test_the_two_flags_are_read_from_the_spec_only(self):
        """突變守衛：把它們改回 `rec.get(...)` → 本條轉紅。"""
        import inspect

        _src = inspect.getsource(P.indicator_state)
        _body = _src.split('"""')[-1]
        assert "wired=bool(spec.wired)" in _body
        assert "discriminative=bool(spec.discriminative)" in _body
        assert 'rec.get("wired"' not in _body
        assert 'rec.get("discriminative"' not in _body


# ══════════════════════════════════════════════════════════════════
# 【6】live 態的 Note 不得被靜默丟棄
# ══════════════════════════════════════════════════════════════════
class _FakeST:
    """`_ui_kit` 用得到的那幾支 `st.*` 的錄音替身。"""

    def __init__(self) -> None:
        self.markdown: list[str] = []
        self.caption: list[str] = []

    def __call__(self, *_a, **_k):  # pragma: no cover - 不會被呼叫
        raise AssertionError("測試替身被當成函式呼叫了")


def _record(fake: _FakeST):
    fake_ns = type("NS", (), {})()
    fake_ns.markdown = lambda _s, **_k: fake.markdown.append(str(_s))
    fake_ns.caption = lambda _s, **_k: fake.caption.append(str(_s))
    return fake_ns


class TestLiveCardKeepsItsNote:
    """`Card.__post_init__` 擋「非 live 沒 Note」與「非 live 帶 value」，

    **沒有**擋「live 帶 Note」；而修前 `render_card` 是
    `if card.state != UI_LIVE and card.note is not None` ——
    於是 `state=live` / `value=''` / 帶 Note 的卡被畫成標「🟢 運作中」的
    **空白框**，那段 Note 被靜默丟棄。靜默丟棄＝§1 禁止的「掩蓋問題」。
    """

    def test_card_type_still_allows_the_dangerous_combination(self):
        """前提：型別那一側沒有擋（本批不得改 `tab_today.py`）。"""
        _c = Card(key="k", label="l", state=UI_LIVE, value="",
                  note=Note(now="a", why="b", where="c"))
        assert _c.state == UI_LIVE and _c.note is not None

    def test_a_live_card_with_a_note_still_prints_it(self, monkeypatch):
        _fake = _FakeST()
        monkeypatch.setattr(K, "st", _record(_fake))
        K.render_card(Card(key="k", label="市場位階", state=UI_LIVE, value="",
                           note=Note(now="現況一句話", why="為什麼沒有",
                                     where="去哪補")))
        _all = "\n".join(_fake.markdown)
        for _piece in ("現況一句話", "為什麼沒有", "去哪補"):
            assert _piece in _all, f"live 態的 Note 被丟棄了：{_piece!r} 不在畫面上"

    def test_a_non_live_card_still_prints_its_note(self, monkeypatch):
        """回歸：原本就會畫的那一半不准壞掉。"""
        _fake = _FakeST()
        monkeypatch.setattr(K, "st", _record(_fake))
        K.render_card(Card(key="k", label="l", state=UI_UNWIRED,
                           note=Note(now="尚未接線", why="分批落地",
                                     where="沒有出口")))
        assert "尚未接線" in "\n".join(_fake.markdown)


# ══════════════════════════════════════════════════════════════════
# 【7】訊號頻道在**建構期**就驗（不留到渲染期 → 不會半截死頁）
# ══════════════════════════════════════════════════════════════════
class TestSignalChannelFailsAtBuildTime:

    @pytest.mark.parametrize("bad", ["🔴 紅", "⬜ 無資料", "🟢", "⛔ 未接線"])
    def test_tile_rejects_a_glyph_before_anything_is_drawn(self, bad):
        with pytest.raises(ValueError, match="signal_text"):
            P.Tile(Card(key="k", label="l", state=UI_LIVE, value="v"),
                   signal_text=bad)

    def test_render_card_keeps_the_same_check_as_the_last_line(self):
        """建構期那道**不是**用來取代渲染期那道（兩邊同一支函式）。"""
        with pytest.raises(ValueError, match="signal_text"):
            K.render_card(Card(key="k", label="l", state=UI_LIVE, value="v"),
                          signal_text="🔴 紅")

    def test_clean_chinese_labels_pass(self):
        assert K.banned_signal_glyphs("紅") == []
        assert K.banned_signal_glyphs("循環惡化") == []
        _t = P.Tile(Card(key="k", label="l", state=UI_LIVE, value="v"),
                    signal_text="紅")
        assert _t.signal_text == "紅"

    def test_render_boundary_turns_a_broken_tile_into_a_red_card(
            self, monkeypatch):
        """渲染期若仍有東西炸，轉紅卡 ＋ `repr(e)`，**不留半截頁面**。"""
        _fake = _FakeST()
        monkeypatch.setattr(K, "st", _record(_fake))
        monkeypatch.setattr(P, "st", _record(_FakeST()))

        _calls = {"n": 0}
        _real = K.render_card

        def _boom(card, **kw):
            _calls["n"] += 1
            if _calls["n"] == 1:
                raise RuntimeError("render exploded")
            return _real(card, **kw)

        monkeypatch.setattr(P, "render_card", _boom)
        P._render_one(P.Tile(Card(key="k", label="測試卡", state=UI_LIVE,
                                  value="v")))
        _all = "\n".join(_fake.markdown)
        assert "這一格畫不出來" in _all
        assert "render exploded" in _all, "原始例外必須看得見（§1）"


# ══════════════════════════════════════════════════════════════════
# 分母與冷啟動
# ══════════════════════════════════════════════════════════════════
class TestColdStartCoverage:

    def test_cold_start_is_zero_of_sixteen(self):
        _cov = P.coverage(P.build_indicator_tiles(
            P.MacroReadout(requested=False)))
        assert (_cov.live, _cov.total) == (0, 16)
        assert _cov.unwired == 1, "未接線在冷啟動就該看得見（線框灰態原文）"
        assert _cov.fault == 0, "冷啟動不是故障 —— 假紅字會蓋掉真的錯誤"
        assert _cov.stale == 0 and _cov.gray == 15

    def test_cold_start_text_matches_the_wireframe_shape(self):
        _txt = P.coverage(P.build_indicator_tiles(
            P.MacroReadout(requested=False))).text()
        assert "0／16" in _txt and "未接線 1" in _txt and "故障 0" in _txt

    def test_cold_start_lights_are_idle_not_empty(self):
        _t = P.build_indicator_tiles(P.MacroReadout(requested=False))
        _states = {_x.card.state for _b in _t.values() for _x in _b}
        assert _states == {UI_IDLE, UI_UNWIRED}, (
            f"冷啟動只該有 idle ＋ unwired，實際 {sorted(_states)}")


class TestDenominatorIsAlwaysSixteen:

    @pytest.mark.parametrize("readout", [
        P.MacroReadout(requested=False),
        P.MacroReadout(requested=True),
        P.MacroReadout(requested=True, error="ImportError('x')"),
        P.MacroReadout(requested=True, readiness={
            "vix": {"wired": True, "discriminative": True, "state": "ok",
                    "value": 18.0, "reason": None}}),
    ])
    def test_total_is_the_ssot_length(self, readout):
        assert P.coverage(P.build_indicator_tiles(readout)).total == \
            len(BUCKET_DANGER_SPECS) == 16

    def test_unwired_and_degraded_are_not_excluded_from_the_denominator(self):
        """把未接線 / 已失準藏起來 ＝ 製造一個永遠 100% 的假可信度。"""
        _keys = {_k for _b in P.build_indicator_tiles(
            P.MacroReadout(requested=True)).values() for _k in
            (_t.card.key for _t in _b)}
        assert "detail.foreign_net" in _keys, "wired=False 的燈不得被排除"
        assert "detail.margin" in _keys, "discriminative=False 的燈不得被排除"


# ══════════════════════════════════════════════════════════════════
# 【8a】【8b】【8c】誠實性小修
# ══════════════════════════════════════════════════════════════════
class TestUpstreamKeyListMatchesTheLoader:

    def test_every_key_the_loader_reads_is_on_the_gate_list(self):
        """清單的 docstring 宣稱「＝ loader 讀的那幾個 key」—— 讓它逐字為真。"""
        import ast
        import inspect

        from src.services import section_inputs as SI

        _tree = ast.parse(inspect.getsource(SI.load_section_inputs))
        _read = {
            _n.args[0].value
            for _n in ast.walk(_tree)
            if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
                and _n.func.attr == "get" and isinstance(_n.func.value, ast.Name)
                and _n.func.value.id == "state" and _n.args
                and isinstance(_n.args[0], ast.Constant)
                and isinstance(_n.args[0].value, str))
        }
        assert _read, "抓不到任何 state.get(...)，這條測試的前提壞了"
        assert _read <= set(P.UPSTREAM_SESSION_KEYS), (
            f"gate 清單少列了 {sorted(_read - set(P.UPSTREAM_SESSION_KEYS))}")

    def test_upstream_requested_only_looks_at_existence(self):
        assert P.upstream_requested({}) is False
        assert P.upstream_requested({"macro_info": None}) is True, (
            "看的是 key 的存在性，不是內容（`bool(data)` 分不出還沒叫 vs 叫了沒回）")


class TestErrorSaysTheRightLayer:
    """修前一律套 `tab_today.upstream_error_why()`，文案寫死

    「讀 **L3 canonical 契約**時拋出例外」—— 而 `page_today` 拿它去包 **L2**
    （`macro_helpers` / `daily_key_alerts`）的例外，**對使用者謊報出事的層**。
    """

    def test_five_bucket_failure_does_not_blame_the_l3_contract(self):
        _t = P.build_indicator_tile(
            "vix", {}, requested=True, error="ImportError('macro_helpers')")
        _why = _t.card.note.why
        assert "canonical 契約" not in _why
        assert "macro_helpers" in _why and "L2" in _why

    def test_key_alert_failure_points_at_l2(self):
        _t = P.build_key_alert_tile(None, requested=True,
                                    threshold_scanned=False,
                                    error="KeyError('vix')")
        assert "daily_key_alerts" in _t.card.note.why
        assert "canonical 契約" not in _t.card.note.why

    def test_the_regime_card_still_uses_the_shared_wording(self):
        """位階那一張**真的**是 L3 canonical 契約 → 續用對面的 SSOT 文案。"""
        _t = _tiles(regime=None, regime_error='RuntimeError("boom")')
        assert "L3 canonical 契約" in _t["verdict.regime"].card.note.why

    def test_glyphs_in_upstream_messages_are_still_scrubbed(self):
        """洗 glyph 仍走 `scrub_state_glyphs()` SSOT —— 不洗會炸 `Note`。"""
        _why = P._error_why(P.SRC_FIVE_BUCKET, "RuntimeError('FRED 掛了 🔴')")
        assert "🔴" not in _why and "已移除" in _why
        Note(now="a", why=_why, where="c")   # 不得炸


class TestKeyBannerRedIsOnTheSignalChannel:
    """線框原文 `🔴 今日關鍵：3 紅 1 黃`，修前狀態 chip 恆為 🟢。

    ⚠️ **不得**改成 `state=failed` 去拿那顆紅：狀態頻道的 🔴 在 L0
    `UI_STATE_META` 是**故障**，而「今天 3 個指標踩線」是**訊號紅**。
    """

    def test_three_reds_light_the_signal_channel(self):
        _al = {"items": [{"text": "VIX 破 30", "severity": 0}],
               "n_red": 3, "n_yellow": 1}
        _t = P.build_key_alert_tile(_al, requested=True, threshold_scanned=True,
                                    error="", band_zh_color=BANDS)
        assert _t.card.state == UI_LIVE, "訊號紅不是故障 —— 狀態頻道維持運作中"
        assert (_t.signal_text, _t.signal_color) == BANDS["red"]
        assert "3 紅" in _t.card.value

    def test_a_quiet_day_is_green_on_the_signal_channel(self):
        _t = P.build_key_alert_tile({"items": [], "n_red": 0, "n_yellow": 0},
                                    requested=True, threshold_scanned=True,
                                    error="", band_zh_color=BANDS)
        assert (_t.signal_text, _t.signal_color) == BANDS["green"]

    def test_an_unevaluated_day_gets_no_light_at_all(self):
        """**未評估 ≠ 綠。** 灰態一律不給燈。"""
        for _kw in ({"requested": False, "threshold_scanned": False},
                    {"requested": True, "threshold_scanned": False}):
            _t = P.build_key_alert_tile(None, error="", band_zh_color=BANDS,
                                        **_kw)
            assert _t.signal_text == "", f"{_kw} 不該有燈號"

    def test_the_signal_text_never_carries_an_emoji(self):
        """訊號頻道只出中文標籤（`Tile.__post_init__` 已擋，這裡是語意確認）。"""
        _al = {"items": [{"text": "x", "severity": 0}], "n_red": 1, "n_yellow": 0}
        _t = P.build_key_alert_tile(_al, requested=True, threshold_scanned=True,
                                    error="", band_zh_color=BANDS)
        assert K.banned_signal_glyphs(_t.signal_text) == []


# ══════════════════════════════════════════════════════════════════
# 【5】葉1 ③ 回到線框的三欄摘要
# ══════════════════════════════════════════════════════════════════
class TestLeaf1ThirdBlockIsTheWireframeSummary:

    def test_the_summary_block_exists_and_has_three_columns(self):
        from src.ui.tabs.tab_today import build_today_blocks

        _blk = {_b.key: _b for _b in build_today_blocks()}["today.summary"]
        assert [_c.label for _c in _blk.cards] == ["位階", "動能", "風險"]

    def test_the_page_renders_that_block_not_the_bucket_summary(self):
        import inspect

        _src = inspect.getsource(P.render_page_today)
        _leaf1 = _src.split("with _leaf2:")[0]
        assert '_blocks["today.summary"]' in _leaf1
        assert "build_bucket_tiles" not in _leaf1, (
            "五桶摘要已移到葉2 頁首；葉1 ③ 是線框的三欄摘要")
        assert "build_bucket_tiles" in _src.split("with _leaf2:")[1]

    def test_the_move_is_disclosed_on_screen(self):
        """稽核抓到的是「換掉了、而且一個字都沒揭露」。"""
        assert "葉1 ③" in P.BUCKET_SUMMARY_MOVED_NOTE
        assert "三欄摘要" in P.BUCKET_SUMMARY_MOVED_NOTE
        assert "沒有刪" in P.BUCKET_SUMMARY_MOVED_NOTE


# ══════════════════════════════════════════════════════════════════
# 冒煙（slow lane）：這一頁真的畫得出來
# ══════════════════════════════════════════════════════════════════
@pytest.mark.slow
def test_page_mounts_clean(tmp_path):
    """冷啟動 session 整頁 mount：**沒有 uncaught exception、不是半截頁面**。"""
    import textwrap

    from shared import ia_nav
    from streamlit.testing.v1 import AppTest

    _script = tmp_path / "_p01_view.py"
    _script.write_text(textwrap.dedent("""
        from src.ui.views.page_today import render_page_today
        render_page_today()
    """), encoding="utf-8")

    _at = AppTest.from_file(str(_script), default_timeout=90)
    _at.run()
    assert not _at.exception, f"page_today mount 有 uncaught exception: {_at.exception}"

    _md = "\n".join(_m.value for _m in _at.markdown)
    _cap = "\n".join(_c.value for _c in _at.caption)
    assert ia_nav.action_label(ia_nav.ACTION_UPDATE_TODAY) in [
        _b.label for _b in _at.button], "submit 沒畫出來"
    # 葉1 ③ 是線框的三欄摘要（動能 / 風險兩格誠實標未接線）。
    for _label in ("位階", "動能", "風險"):
        assert _label in _md, f"葉1 ③ 的「{_label}」欄沒有畫出來"
    # 尾端的葉2 也要畫到（半截死頁會在這裡斷掉）。
    assert "0／16" in (_md + _cap), "coverage 那一行沒畫出來（可能是半截頁面）"
