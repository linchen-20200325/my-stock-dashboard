"""tests/test_ui_state_model.py — L0 `shared/ui_state.py` 契約 + 第 4 類回歸守衛。

v3 憲法 §02「介面狀態嚴格分離」：
    「未點擊載入」以灰色說明提示，「系統真出錯」才標註紅色警示。

本檔守三件事：
  A. 七態的判定順序與顏色（`TestClassifyUiState`）
  B. **突變守衛**：拿掉 `requested`、或讓 `idle` 由 `if not data:` 推導 →
     必須轉紅（`TestMutationGuards` + `TestNoDerivedRequested`）
  C. 第 4 類五處的**文案回歸**：把錯誤指引放回去 → 必須轉紅
     （`TestClass4Regressions`）

⚠️ 為什麼 B 要有三條而不是一條：單靠「呼叫時漏傳 requested 會 TypeError」
擋不住「有人給它加個 `= False` 預設值」或「有人在呼叫端寫
`requested=bool(data)`」。三條各擋一種退化路徑，缺一條那條路就通了。
"""
from __future__ import annotations

import ast
import inspect
import io
import pathlib

import pytest

from shared.station_specs import (
    MISS_CONTRACT_DRIFT,
    MISS_FETCH_FAILED,
    MISS_NOT_ENOUGH,
    MISS_NO_INPUT,
)
from shared.ui_state import (
    FAILED_REASONS,
    UI_DEGRADED,
    UI_EMPTY,
    UI_FAILED,
    UI_IDLE,
    UI_LIVE,
    UI_LOADING,
    UI_STATE_META,
    UI_STATES,
    UI_UNWIRED,
    classify_ui_state,
    is_alarming,
    state_meta,
)

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _src(rel: str) -> str:
    return io.open(_REPO / rel, encoding="utf-8").read()


# ══════════════════════════════════════════════════════════════════
# A. 七態
# ══════════════════════════════════════════════════════════════════
class TestClassifyUiState:
    def test_not_requested_is_idle(self):
        assert classify_ui_state(requested=False) == UI_IDLE

    def test_unwired_beats_everything(self):
        """未接線排第 1：叫不叫、有沒有值都不改變它。"""
        assert classify_ui_state(requested=False, wired=False) == UI_UNWIRED
        assert classify_ui_state(requested=True, wired=False,
                                 has_value=True) == UI_UNWIRED
        assert classify_ui_state(requested=True, wired=False,
                                 error="boom") == UI_UNWIRED

    def test_idle_beats_error(self):
        """**本檔最重要的一條**：`idle` 排在 `error` 前面。

        Streamlit 每次 rerun 都重跑整頁，session 裡常躺著上一輪的錯誤字串。
        若先判 error，一個「已重置、還沒重新載入」的區塊會亮紅燈 ——
        那就是 v3 §02 前半句要杜絕的假性錯誤。

        ⚠️ 這裡用 `wired=False` 之外的路徑驗證順序：`requested=False` 且
        帶 error 會被矛盾守衛擋掉（那是另一條測試），故改用「本輪沒請求、
        上一輪的錯誤已被呼叫端依約清成 None」這個合法組合，
        並另以原始碼順序斷言把「idle 在 error 之前」釘死。
        """
        assert classify_ui_state(requested=False, error=None) == UI_IDLE
        _lines = [ln.strip() for ln in
                  inspect.getsource(classify_ui_state).splitlines()]
        _i_idle = next(i for i, ln in enumerate(_lines)
                       if ln.startswith("if not requested:"))
        _i_err = next(i for i, ln in enumerate(_lines)
                      if ln.startswith("if error:"))
        assert _i_idle < _i_err, "判定順序漂移：idle 必須排在 error 之前"

    def test_in_flight_is_loading(self):
        assert classify_ui_state(requested=True, in_flight=True) == UI_LOADING

    def test_error_is_failed(self):
        assert classify_ui_state(requested=True, error="HTTPError: 429") == UI_FAILED

    def test_no_value_is_empty_not_failed(self):
        """請求過、沒錯、沒值 → `empty`（灰），**不是紅色**。"""
        assert classify_ui_state(requested=True, has_value=False) == UI_EMPTY

    @pytest.mark.parametrize("reason", sorted(FAILED_REASONS))
    def test_failed_reasons_escalate(self, reason):
        assert classify_ui_state(requested=True, has_value=False,
                                 reason=reason) == UI_FAILED

    @pytest.mark.parametrize("reason", [MISS_NO_INPUT, MISS_NOT_ENOUGH, "n/a"])
    def test_non_failed_reasons_stay_grey(self, reason):
        """「等一等就好」類的缺值原因**不得**標紅（否則就是假性錯誤）。"""
        assert classify_ui_state(requested=True, has_value=False,
                                 reason=reason) == UI_EMPTY

    def test_failed_reasons_membership(self):
        assert FAILED_REASONS == {MISS_FETCH_FAILED, MISS_CONTRACT_DRIFT}

    def test_degraded_and_live(self):
        assert classify_ui_state(requested=True, has_value=True,
                                 discriminative=False) == UI_DEGRADED
        assert classify_ui_state(requested=True, has_value=True) == UI_LIVE

    def test_only_failed_is_red(self):
        """v3 §02：紅色**只**留給「系統真出錯」。"""
        for _s in UI_STATES:
            assert is_alarming(_s) is (_s == UI_FAILED)
        _reds = [s for s, (_, _, hex_) in UI_STATE_META.items()
                 if hex_.lower() == "#ef4444"]
        assert _reds == [UI_FAILED], f"紅色只准給 failed，實際：{_reds}"

    def test_grey_states_share_one_hex_and_differ_by_glyph(self):
        _grey = [s for s in (UI_IDLE, UI_LOADING, UI_EMPTY, UI_UNWIRED)]
        _hexes = {UI_STATE_META[s][2] for s in _grey}
        assert len(_hexes) == 1, "灰色不得裂成多個色票"
        _glyphs = [UI_STATE_META[s][1] for s in _grey]
        assert len(set(_glyphs)) == len(_glyphs), "灰色四態必須靠 glyph 分辨"

    def test_state_meta_fails_loud_on_unknown(self):
        with pytest.raises(ValueError):
            state_meta("nope")
        for _s in UI_STATES:
            assert len(state_meta(_s)) == 3


# ══════════════════════════════════════════════════════════════════
# B. 突變守衛
# ══════════════════════════════════════════════════════════════════
class TestMutationGuards:
    def test_requested_is_required_keyword_only(self):
        """突變 (a)：把 `requested` 拿掉、或給它一個預設值 → 本條轉紅。"""
        from shared.ui_state import _signature_has_required_requested
        assert _signature_has_required_requested(), (
            "`requested` 必須是必填的 keyword-only 參數（無預設值）——"
            "一旦有預設值，呼叫端就可以不回答『有沒有被叫過』，"
            "這個模型當天就退化回 `if not data:`"
        )
        with pytest.raises(TypeError):
            classify_ui_state()          # type: ignore[call-arg]
        with pytest.raises(TypeError):
            classify_ui_state(True)      # type: ignore[misc]

    def test_idle_and_failed_are_distinguishable_from_identical_data(self):
        """突變 (b)：把 `idle` 改成由 `if not data:` 推導 → 本條轉紅。

        兩次呼叫的**資料完全相同**（都沒有值），只有 `requested` 不同。
        任何從資料本身推導 idle 的實作，都不可能讓這兩者分開。
        """
        _idle = classify_ui_state(requested=False, has_value=False)
        _failed = classify_ui_state(requested=True, has_value=False,
                                    reason=MISS_FETCH_FAILED)
        assert _idle == UI_IDLE
        assert _failed == UI_FAILED
        assert _idle != _failed, (
            "同一份『沒有資料』必須能分出『還沒叫』與『叫了但失敗』——"
            "分不出來就是第 5 類（資訊沒傳到 UI）原地復活"
        )

    def test_contradiction_fails_loud(self):
        """`requested=False` 卻帶著本輪的值 / 錯誤 / in_flight → raise（§1）。"""
        for _kw in ({"has_value": True}, {"error": "boom"}, {"in_flight": True}):
            with pytest.raises(ValueError, match="requested=False"):
                classify_ui_state(requested=False, **_kw)  # type: ignore[arg-type]

    def test_l0_purity(self):
        """L0 不得碰 streamlit / I/O（§8.2 硬規則）。"""
        _s = _src("shared/ui_state.py")
        _tree = ast.parse(_s)
        _mods = set()
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.Import):
                _mods.update(a.name.split(".")[0] for a in _n.names)
            elif isinstance(_n, ast.ImportFrom) and _n.module:
                _mods.add(_n.module.split(".")[0])
        _banned = {"streamlit", "requests", "httpx", "yfinance", "pandas"}
        assert not (_mods & _banned), f"L0 不得 import {_mods & _banned}"


class TestNoDerivedRequested:
    """突變 (b) 的第二道：掃全 repo 的呼叫點，禁止用資料反推 `requested`。

    鐵律：**`idle` 只能由上游帶下來，禁止由 `if not data:` 推導。**
    這條測試把它編碼成可執行檢查 —— 若 `requested=` 綁的運算式與
    `has_value=` 綁的**是同一個**，那就是拿資料的有無當請求訊號。

    ⚠️ 誠實揭露本檢查的**極限**：它比對的是 AST 結構是否相同，
    抓得到 `requested=bool(x), has_value=bool(x)` 這種直接同源，
    **抓不到**語意等價但寫法不同的（例如 `requested=len(x)>0` 配
    `has_value=bool(x)`）。它是護欄不是證明。
    """

    def _calls(self):
        for _p in sorted(_REPO.rglob("*.py")):
            if any(_x in _p.parts for x_ in [()] for _x in
                   (".git", "__pycache__", ".ruff_cache", "data_cache")):
                continue
            try:
                _tree = ast.parse(io.open(_p, encoding="utf-8").read())
            except (SyntaxError, UnicodeDecodeError):
                continue
            for _n in ast.walk(_tree):
                if (isinstance(_n, ast.Call)
                        and isinstance(_n.func, ast.Name)
                        and _n.func.id == "classify_ui_state"):
                    yield _p.relative_to(_REPO), _n

    def test_every_call_passes_requested(self):
        _found = 0
        for _rel, _call in self._calls():
            _kw = {k.arg for k in _call.keywords if k.arg}
            if _rel.as_posix().startswith("tests/"):
                continue
            _found += 1
            assert "requested" in _kw, (
                f"{_rel}:{_call.lineno} 呼叫 classify_ui_state 沒有傳 "
                "`requested=` —— 鐵律：idle 只能由上游帶下來"
            )
        assert _found >= 5, (
            f"production 呼叫點只找到 {_found} 個，"
            "第 4 類五處應該都已接上 L0 模型"
        )

    def test_requested_is_not_the_same_expression_as_has_value(self):
        for _rel, _call in self._calls():
            if _rel.as_posix().startswith("tests/"):
                continue
            _kw = {k.arg: k.value for k in _call.keywords if k.arg}
            if "requested" not in _kw or "has_value" not in _kw:
                continue
            # 兩邊都是字面常數 → 不是「從資料推回來」,放行
            # (例如 `requested=False, has_value=False` 這種顯式列舉)。
            if all(isinstance(_kw[_k], ast.Constant) for _k in
                   ("requested", "has_value")):
                continue
            _r = ast.dump(_kw["requested"])
            _h = ast.dump(_kw["has_value"])
            assert _r != _h, (
                f"{_rel}:{_call.lineno} `requested=` 與 `has_value=` 綁了"
                "**同一個運算式** —— 那就是用資料的有無反推有沒有被叫過，"
                "正是 S-4.6 / Fund F-4.3 兩個 repo 各自長出同一個 bug 的成因"
            )


# ══════════════════════════════════════════════════════════════════
# C. 第 4 類回歸守衛（把錯誤指引放回去 → 轉紅）
# ══════════════════════════════════════════════════════════════════
class TestClass4Regressions:
    def test_s41_blocked_branch_has_no_idle_cta(self):
        """S-4.1：擋燈分支不得再出現「請點上方…載入完整資料後，燈號才會顯示」。

        走到擋燈分支的前提是 `tl is not None` = 燈號已經算過一輪 =
        使用者按過了。此時叫他「再點一次」是**錯誤指引**（點一百次也一樣）。
        """
        _s = _src("src/ui/tabs/macro/handlers.py")
        assert "請點上方「🚀 一鍵更新全部數據」載入完整資料後，燈號才會顯示" not in _s, (
            "S-4.1 的錯誤指引被放回去了：擋燈分支是**真故障**，不是閒置態"
        )
        assert "重按「🚀 一鍵更新全部數據」對這個原因無效" in _s, (
            "S-4.1 的反轉指引不見了 —— 這句是本項修復的核心"
        )

    def test_s41_uses_upstream_requested_not_data(self):
        _s = _src("src/ui/tabs/macro/handlers.py")
        assert "requested=None" in _s or "requested=None)" in _s
        assert "st.session_state.get('chips_loaded')" in _s, (
            "requested 必須讀按鈕 handler 寫下的 gate 旗標"
        )

    def test_s42_failure_branch_is_not_st_info(self):
        """S-4.2：全球資金流向真失敗那一支不得再用 `st.info`（藍/灰）。"""
        _s = _src("src/ui/tabs/macro/section_long.py")
        assert "st.info('ℹ️ 全球資金流向資料暫時無法取得" not in _s
        assert "🟠 全球資金流向暫時取不到" in _s

    def test_s43_failure_branch_says_failed_not_click(self):
        """S-4.3：已載入過卻沒有 cl_data → 必須說失敗，不得說「請點擊載入」。"""
        _s = _src("src/ui/tabs/macro/section_state.py")
        assert "st.info('📡 請點擊「🚀 一鍵更新全部數據」載入大盤數據')" not in _s
        assert "🔴 大盤資料取得失敗" in _s
        assert "MISS_FETCH_FAILED" in _s

    def test_s44_no_caller_should_have_guess(self):
        """S-4.4：不得再用「caller **應該**已抓」這種自白式猜測當文案。"""
        _s = _src("src/ui/tabs/hot_money.py")
        assert "caller 應已抓 TWD=X）；無法計算熱錢訊號" not in _s
        assert "requested: bool = True" in _s, "requested 必須由 caller 帶下來"

    def test_s44_caller_actually_passes_requested(self):
        _s = _src("src/ui/tabs/macro/section_state.py")
        assert "render_hot_money_section(" in _s
        _i = _s.index("render_hot_money_section(\n")
        assert "requested=_requested" in _s[_i:_i + 400], (
            "section_state 呼叫 hot_money 時必須把 gate 旗標傳下去"
        )

    def test_s46_empty_lines_no_longer_asserts_not_loaded(self):
        """S-4.6：`_lines` 為空時不得再無條件斷言「尚未載入」。

        這是兩個 repo 各自獨立長出的**模式**：蒐集成 list、
        再用 list 空不空當狀態 —— 天生分不出「沒去蒐集」與「一無所獲」。
        """
        _s = _src("src/ui/pages/sidebar_health.py")
        assert 'st.caption("⬜ 尚未載入；載入個股 / 總經後這裡顯示總覽")' not in _s
        assert "_stock_requested" in _s and "_mc_requested" in _s
        assert "**不是還沒載入**" in _s

    def test_s46_requested_comes_from_key_presence_not_lines(self):
        """`requested` 必須來自 session key 的存在，不得來自 `_lines`。"""
        _s = _src("src/ui/pages/sidebar_health.py")
        assert '_stock_requested = "t2_data" in session_state' in _s
        assert '_mc_requested = "_macro_compass_cache" in session_state' in _s
        assert "requested=_lines" not in _s and "requested=bool(_lines)" not in _s
