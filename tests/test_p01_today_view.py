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

import pathlib

import pytest

from shared.allocation_decision import REGIME_LABEL
from shared.macro_buckets import BUCKET_DANGER_SPECS, SPECS_BY_KEY
from shared.signal_thresholds import (
    KEY_ALERT_FED_FUNDS_MOVE_PCTPT as _KEY_ALERT_FED_FUNDS_MOVE_PCTPT,
)
from shared.signal_thresholds import (
    KEY_ALERT_VIX_DAY_SPIKE_PCT as _KEY_ALERT_VIX_DAY_SPIKE_PCT,
)
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

#: repo 根目錄（`tests/` 的上一層）。反向驗「文案點名 / 引述的東西還在不在」用。
_ROOT = pathlib.Path(__file__).resolve().parents[1]

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
        """渲染期若仍有東西炸，轉紅卡 ＋ `repr(e)`，**不留半截頁面**。

        ⚠️ **2026-09-07 FE-9：patch 的對象從 `P.render_card` 改成
        `K.render_card`** —— 這是**接縫搬家**，不是把守衛放寬。
        該邊界的本體已上移共用層 `_ui_kit.render_card_isolated()`
        （頁 1 與頁 2 原本各有一份逐行同構的 `_render_one()`），
        `page_today` 因此不再持有 `render_card` 這個名字。
        本條驗的東西**一個字都沒變**（炸了要轉紅卡、原始例外要看得見），
        只是注入點跟著實作移到它真正的所在地。
        """
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

        monkeypatch.setattr(K, "render_card", _boom)
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
# 【FIX-1】degraded 的位階卡：**有值的契約不得被說成「尚未評估」**
# ══════════════════════════════════════════════════════════════════
#: L3 `get_macro_state()` 走 `macro_state.json` 快照那一條分支的形狀。
#: （`macro_state_locker.get_macro_state` 實測：`_file_ok` ⇒ `_is_loaded=True`
#:  且 `source=SOURCE_FILE_RULE_ENGINE` ⇒ `discriminative=False` ⇒ degraded。
#:  也就是**這一態在 production 真的走得到**，不是為了測試捏出來的組合。）
DEGRADED_REGIME = {"regime": "bull", "light": "🟢", "traffic_light": "多頭",
                   "source": SOURCE_FILE_RULE_ENGINE, "is_loaded": True}


class TestDegradedRegimeIsNotCalledUnevaluated:
    """修前是 `if _regime_state == UI_LIVE: ... else: ...` ——
    **所有非 live（含 degraded）一起掉進 else**，於是對一個 `is_loaded=True`、
    有值的契約印出「市場位階：尚未評估」＋「四條來源本輪皆無值」。

    **那是假敘述**：degraded 的前提就是有值（L0 `shared/station_specs.py:139`
    「燈會亮、也有等級，只是門檻已失去判別力」／`:527`「有值、燈照亮，
    只是別照門檻讀」）。§1：錯誤的敘述比沒有敘述更危險。
    """

    def test_the_premise_of_this_test_still_holds(self):
        """前提自證：這份契約在 L0 判態下**真的**是 degraded。"""
        assert P.classify_macro_contract(DEGRADED_REGIME) == UI_DEGRADED

    def test_it_never_says_unevaluated(self):
        _n = _tiles(regime=DEGRADED_REGIME)["verdict.regime"].card.note
        _all = f"{_n.now}\n{_n.why}\n{_n.where}"
        assert "尚未評估" not in _all, "有值的契約不得被說成沒評估"
        assert "皆無值" not in _all, "degraded 的前提就是有值"

    def test_it_still_brings_out_the_level(self):
        """**位階是觀測不是判決 → 照印。** 留白會把本來看得到的資訊藏起來。"""
        _t = _tiles(regime=DEGRADED_REGIME)["verdict.regime"]
        _label = REGIME_LABEL["bull"]
        assert _t.signal_text == _label, "degraded 載的是 band 觀測 → 燈要照出"
        assert ("現值", _label) in _t.facts, (
            "非 live 不得帶 `value` ⇒ 現值改掛 facts，不是整個消失")

    def test_the_disclaimer_rides_on_the_state_channel(self):
        _t = _tiles(regime=DEGRADED_REGIME)["verdict.regime"]
        assert _t.card.state == UI_DEGRADED, "免責聲明＝狀態頻道那顆 chip"
        assert _t.card.value == "", "非 live 不得帶結論文字（`Card` 的鐵律）"
        assert ("生效分支", SOURCE_FILE_RULE_ENGINE) in _t.facts, (
            "「來自快照」要有證據可看，不能只是一句話")

    def test_the_wording_is_the_status_bar_ssot_not_a_second_copy(self):
        """文案**不得另寫一份** —— 對面對同一個狀態已經有推敲過的說法。"""
        from src.ui.tabs.tab_today import build_status_bar_card

        _mine = _tiles(regime=DEGRADED_REGIME)["verdict.regime"].card.note
        _ssot = build_status_bar_card(DEGRADED_REGIME).note
        assert (_mine.now, _mine.why, _mine.where) == (
            _ssot.now, _ssot.why, _ssot.where), "兩份文案漂開了＝兩種解釋"
        assert "快照" in _mine.now, "前提變了：對面的 degraded 文案被改過"

    def test_cold_start_still_says_unevaluated(self):
        """反向釘子：**真的**沒值那一態的文案沒有被這次改動弄丟。"""
        _t = _tiles(regime=COLD_REGIME)["verdict.regime"]
        assert "尚未評估" in _t.card.note.now
        assert "皆無值" in _t.card.note.why
        assert _t.signal_text == "", "灰態不給燈（未評估 ≠ 有位階）"

    def test_a_drifted_contract_neither_crashes_nor_invents_a_level(self):
        """契約漂移（degraded 卻沒帶 `regime`）→ 不炸，也不編一個位階出來。

        ⚠️ production 走不到（`macro_state_locker` 的 `_file_ok` 分支一律經
        `normalize_regime()`，實測 `None` / `''` / `'系統異常'` 全部落到
        `'neutral'`，**不會**回 `'unknown'`）—— 這條釘的是**漂移**那一天。
        """
        _t = _tiles(regime={"source": SOURCE_FILE_RULE_ENGINE,
                            "is_loaded": True})["verdict.regime"]
        assert _t.card.state == UI_DEGRADED
        assert _t.signal_text == REGIME_LABEL["unknown"], (
            "缺值時只准說「未評估」，不得挑一個位階填上去")

    def test_a_broken_contract_is_still_red(self):
        """`error` 在 `classify_ui_state` 排在 `discriminative` 前面 ——
        新增的 degraded 分支不得把紅態吃掉。"""
        _t = _tiles(regime=DEGRADED_REGIME,
                    regime_error='RuntimeError("boom")')["verdict.regime"]
        assert _t.card.state == UI_FAILED
        assert _t.signal_text == "", "紅態不給燈"


# ══════════════════════════════════════════════════════════════════
# 【FIX-2】今日關鍵：degraded 下的「綠」在上游契約下不可達 —— 釘住那個前提
# ══════════════════════════════════════════════════════════════════
class TestDegradedGreenIsUnreachableUpstream:
    """degraded 下的綠只代表「**急變層** 0 紅 0 黃」，而門檻層
    （`threshold_scanned=False`）根本沒掃 —— 真的出得來就是一顆誤導性的
    all-clear。**查證結論：`collect_key_alerts` 的契約下走不到。**

    推導：degraded ⇒ `threshold_scanned=False` ⇒ `has_value=bool(items)`
    ⇒ items 非空；而 `collect_key_alerts` 只產 severity 0（紅）/ 1（黃）
    item，`n_red` / `n_yellow` 又是對 items 數出來的 ⇒ items 非空 ⇒ 至少一
    紅或一黃 ⇒ `_level` 不可能是 green。

    ⚠️ 所以本組釘的是**那個前提**，不是行為：哪天有人替
    `collect_key_alerts` 加一種「綠 / 提示」item，前提就破、綠燈就真的出得來
    —— 這裡會當場轉紅，逼下一個人回去改 `build_key_alert_tile`。
    """

    #: 急變層的兩個門檻**一律從 L0 SSOT 取**（`shared/signal_thresholds`）——
    #: 測試裡寫死一個「剛好超過」的數字，等於在測試檔裡複寫了一份門檻，
    #: 門檻一調整這裡就靜靜地不再觸發（§3.3 反捏造）。
    _VIX_HIT = [20.0, 20.0 * (1 + (_KEY_ALERT_VIX_DAY_SPIKE_PCT + 5) / 100)]
    _VIX_MISS = [20.0, 20.0 * (1 + (_KEY_ALERT_VIX_DAY_SPIKE_PCT - 5) / 100)]
    _FF_HIT = {"current": 5.0, "prev": 5.0 - (_KEY_ALERT_FED_FUNDS_MOVE_PCTPT + 0.05)}

    #: `(threshold_alerts, macro_info)`：兩層都涵蓋，含 None / 空 / 垃圾值。
    CASES = [
        (None, None),
        (None, {}),
        ([], {"vix": {"values": _VIX_HIT}}),                   # 急變層紅
        (None, {"fed_funds": _FF_HIT}),                        # 急變層黃
        (None, {"vix": {"values": _VIX_HIT}, "fed_funds": _FF_HIT}),
        (None, {"vix": {"values": _VIX_MISS}}),                # 沒踩到門檻
        (None, {"vix": {"values": ["bad", None]}}),            # 垃圾值
        ([{"level": "green", "label": "x", "value": 1}], None),
        ([{"level": "red", "label": "VIX", "value": 35, "unit": "",
           "message": "m"}], None),
        ([{"level": "yellow", "label": "CPI", "value": 3, "unit": "%",
           "message": "m"}], {"vix": {"values": _VIX_HIT}}),
    ]

    def _collect(self, ta, mi):
        from src.compute.macro.daily_key_alerts import collect_key_alerts

        return collect_key_alerts(ta, mi)

    def test_collect_key_alerts_only_ever_emits_red_or_yellow(self):
        for _ta, _mi in self.CASES:
            _r = self._collect(_ta, _mi)
            assert all(_i["severity"] in (0, 1) for _i in _r["items"]), _r
            assert _r["n_red"] + _r["n_yellow"] == len(_r["items"]), (
                f"items 非空卻數不出紅 / 黃 ⇒ degraded 會亮出綠燈：{_ta} / {_mi}")

    def test_no_real_contract_output_lights_a_green_chip_while_degraded(self):
        """走**真的** `collect_key_alerts` 輸出（不手捏 mapping）。"""
        _seen = 0
        for _ta, _mi in self.CASES:
            _t = P.build_key_alert_tile(
                self._collect(_ta, _mi), requested=True,
                threshold_scanned=bool(_ta), error="", band_zh_color=BANDS)
            if _t.card.state != UI_DEGRADED:
                continue
            _seen += 1
            assert _t.signal_text != BANDS["green"][0], (
                f"degraded 亮綠燈＝門檻層沒掃卻讀起來像 all-clear：{_ta} / {_mi}")
            assert _t.signal_text in (BANDS["red"][0], BANDS["yellow"][0])
        assert _seen, "一個 degraded 都沒走到 —— 這條測試沒有在測東西"


# ══════════════════════════════════════════════════════════════════
# 【FIX-3】判準要寫在 kit 的 docstring 裡（兩頁分歧的根因就是它沒寫）
# ══════════════════════════════════════════════════════════════════
class TestSignalChannelDocumentsTheDegradedRule:
    """`_ui_kit.render_card` 的 `signal_text` 修前只寫「空字串 = 沒有燈號
    頻道」，**對 degraded 一個字都沒有** —— 於是頁1 照出、頁4 留白，
    兩頁對同一個狀態做出相反處理。這條防它日後被刪掉又分歧。
    """

    def test_the_criterion_is_written_down(self):
        _doc = K.render_card.__doc__ or ""
        assert "degraded" in _doc, "判準不見了"
        for _k in ("觀測", "判決", "留白"):
            assert _k in _doc, f"判準少了「{_k}」那一半"

    def test_it_points_back_at_the_l0_evidence(self):
        """依據要指得回去 —— 不然下一個人只會看到一個沒有出處的規定。"""
        _doc = K.render_card.__doc__ or ""
        assert "station_specs.py:139" in _doc
        assert ":527" in _doc

    def test_the_l0_sentences_it_quotes_are_really_there(self):
        """**行號會過期**（`CLAUDE.md §8.2.A.0` 規則 1）—— 所以連 docstring
        **引述的那兩句 L0 原文**一起驗：句子還在就找得回去，行號漂掉也不會
        變成一個指不到東西的假出處。
        """
        _t = (_ROOT / "shared/station_specs.py").read_text(encoding="utf-8")
        for _q in ("燈會亮、也有等級，只是門檻已失去判別力", "有值、燈照亮"):
            assert _q in _t, (
                f"`station_specs.py` 已經沒有 {_q!r} —— "
                "`render_card` docstring 引的出處過期了，回來改它")

    def test_grey_and_red_are_still_documented_as_blank(self):
        """**未評估 ≠ 綠**：灰態 / 紅態留白那一半不得被這次補寫沖掉。"""
        _doc = K.render_card.__doc__ or ""
        assert "未評估 ≠ 綠" in _doc


# ══════════════════════════════════════════════════════════════════
# 【FIX-4】位階卡不得宣稱自己是全站唯一出處（實測為假）
# ══════════════════════════════════════════════════════════════════
#: 揭露裡點名的**平行判讀**：`(相對路徑, 這一支的識別特徵…)`。
#: ⚠️ 依 `CLAUDE.md §8.2.A.0` 規則 1，**一律不寫行號**（行號保證會過期），
#: 改以「檔案 + 符號 / 字串」定位。
_PARALLEL_REGIME_CALLS = (
    ("src/ui/tabs/macro/section_cross_ai.py",
     ("① 目前總經位階", "_bull_score", "_bear_score")),
    ("src/compute/macro/macro_helpers.py",
     ("def classify_long_term_regime",)),
    ("src/ui/tabs/macro/section_news_ai.py",
     ("market_regime", "市場體制")),
)

#: canonical 那一側（揭露句自己也點名了它們，同樣要能被驗）。
_CANONICAL_REGIME = (
    ("shared/regime_arbiter.py", ("def arbitrate_regime",)),
    ("src/services/macro_state_locker.py", ("def get_macro_state",)),
)


class TestNoGlobalUniquenessClaim:
    """2026-09-07 獨立稽核：本卡標題原本宣稱自己是本站位階的**唯一**出處，
    **實測為假** —— 舊版「🌍 市場環境」分頁至少有三處未經 L0
    `arbitrate_regime()` 仲裁的平行判讀，新聞頁還直讀 `macro_state.json`
    快照。那幾支住在客戶明令不得修改的舊版 Tab ⇒ **能改的只有本頁的宣稱**。

    ⚠️ 本組同時釘**兩個方向**，缺一不可：
      · 正向：本頁不准再出現那句全稱宣稱（label 改回去 → 轉紅）。
      · 反向：揭露裡點名的那幾支現在**真的還在**。一份過期的「未納管清單」
        跟一句假的唯一性宣稱一樣糟 —— 收斂掉了就該回來改文案，
        而不是留一段沒人再驗的話。
    """

    def _text(self, rel: str) -> str:
        _p = _ROOT / rel
        assert _p.exists(), f"{rel} 不見了 —— 揭露文案點名的檔案已不存在"
        return _p.read_text(encoding="utf-8")

    def test_the_page_makes_no_repo_wide_uniqueness_claim(self):
        """**突變守衛**：label 改回「全站唯一…」那句 → 本條當場轉紅。

        （若日後真的需要寫一句**明示否認**式的句子，請照
        `tests/test_p04_hold_view.py` 的 `_UNIQUENESS_DENIALS` 先例改成
        上下文判斷 —— **不要**直接放寬成不檢查。）
        """
        _src = self._text("src/ui/views/page_today.py")
        assert "全站唯一" not in _src, (
            "本頁不得出現需要窮舉全 repo 才成立的唯一性全稱句 —— "
            "2026-09-07 實測那句是假的")

    def test_the_label_is_the_single_constant_used_by_every_branch(self):
        """標題只准定義一次：改了一處、另外兩處還在說舊話是最常見的漏改。"""
        assert P.REGIME_CARD_LABEL == "市場位階（總經契約）"
        for _kw in ({"regime": dict(LIVE_REGIME)},
                    {"regime": DEGRADED_REGIME},
                    {"regime": COLD_REGIME}):
            assert _tiles(**_kw)["verdict.regime"].card.label == (
                P.REGIME_CARD_LABEL)

    def test_every_state_carries_the_disclosure(self):
        """揭露掛 `facts` ⇒ **每一態都出**（`render_card` 任何狀態都畫 facts）。"""
        for _kw in ({"regime": dict(LIVE_REGIME)},
                    {"regime": DEGRADED_REGIME},
                    {"regime": COLD_REGIME},
                    {"regime": None, "regime_error": 'RuntimeError("x")'}):
            _f = dict(_tiles(**_kw)["verdict.regime"].facts)
            assert _f.get("位階的出處") == P.REGIME_SCOPE_NOTE, _kw

    def test_the_disclosure_says_what_it_takes_and_what_it_does_not_cover(self):
        _n = P.REGIME_SCOPE_NOTE
        assert "get_macro_state" in _n and "arbitrate_regime" in _n
        assert "本頁" in _n, "要寫成單點可驗的「本頁取自 X」，不是「全站只有 X」"
        assert "以這張卡為準" in _n, "不一致時該看哪一邊，要講清楚"

    def test_the_parallel_readings_it_names_still_exist(self):
        """反向釘子：點名的四處**現在真的還在**（收斂掉了 → 轉紅改文案）。"""
        for _rel, _marks in _PARALLEL_REGIME_CALLS:
            _t = self._text(_rel)
            for _m in _marks:
                assert _m in _t, (
                    f"{_rel} 已經沒有 {_m!r} —— 揭露文案過期了，回來改它")

    def test_the_canonical_side_is_also_real(self):
        for _rel, _marks in _CANONICAL_REGIME:
            _t = self._text(_rel)
            for _m in _marks:
                assert _m in _t, f"{_rel} 找不到 {_m!r} —— canonical 側變了"

    def test_the_old_tab_the_disclosure_names_is_still_mounted(self):
        """揭露句寫「舊版『🌍 市場環境』分頁」—— 那個分頁名要真的還掛著。"""
        assert "🌍 市場環境" in self._text("app.py")


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
