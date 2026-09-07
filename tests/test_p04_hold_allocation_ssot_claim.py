"""tests/test_p04_hold_allocation_ssot_claim.py — 頁 4 的「持股水位 SSOT」宣稱守衛。

⚠️ **這一檔守的不是頁 4 的 render 細節，而是一句印在使用者臉上的全稱句。**
故獨立成檔（不併進 `tests/test_p04_hold_view.py`）：它掃的是**全 repo 的不變量**
——「算整體資產持股水位的地方有幾處」——，頁 4 只是那個不變量的其中一個消費者。

修前的實測（2026-09-07）：`src/ui/views/page_hold.py` 的卡面 facts 列與
`AllocationReadout` docstring 都寫「**全站唯一**的建議持股 SSOT
（L3 `get_allocation()`）」。這句可實測為假 ——

  · `get_allocation()` **是**匯總者，但它只 `min()` 三條輸入：
    姿態油門（`compute_position_throttle`）／`macro_state` 的 `exposure_limit_pct`
    ／`_derive_intrinsic_caps()` 的 VIX＋三環天花板；
  · 全站另有**一條都沒進到那個 `min()`** 的獨立算法（本檔現場量測，見
    `_parallel_position_sites()`），其中一支**就在同一頁上** ——
    ④「姿態油門帶」走 `get_station_macro()` 的 `posture_range`，**未套任何 cap**。

`CLAUDE.md §-2` 規則 6：**沒查證的宣稱比沒有宣稱更危險。** 同一個檔案剛修掉三處
「全站唯一乘法點」的假宣稱，這是同型的第二個。本檔把兩個方向都釘住：

  1. **正向**（`TestNoScreenTextClaimsTheOnlyWay`）：只要全站不只一處在算持股水位，
     頁 4 的文案就**不准**出現非否定式的「全站唯一」。
  2. **反向**（`TestTheNamedUnmanagedSitesStillExist`）：文案點名的那幾支
     **現在真的還在**。哪天它們被收斂掉，這一類轉紅提醒改文案 ——
     **一份假的「未納管清單」跟一句假的「全站唯一」一樣糟**，兩者都是在
     使用者面前講一個沒查證的事實。
  3. **同頁自我矛盾**（`TestTheSamePageContradictionIsDisclosed`）：④ 那格必須
     自己標明「未套天花板」並指向 ⑤，否則使用者看到同一頁兩個持股區間、
     不知道口徑不同。

⚠️ **既有的 `tests/test_no_hardcoded_position_pct.py` 不足以當本檔的替代品**：
它只掃 `src/ui` + `src/compute` + `app.py`、只認**字面數字**，而且 `_KNOWN_DEBT`
已放行兩處。本檔要問的是「**有幾套算法**」，不是「**有沒有寫死數字**」——
一支完全不寫死數字、全部走常數的平行實作（`market_alert_banner` 正是如此）
在那把尺下是綠的，在這把尺下才會現形。

⚠️ **這是護欄，不是證明**：它釘住的是「已知的這一種說謊方式不會再回來」，
**不是**「頁 4 對持股水位的說明都是對的」。全綠不等於合規。
"""
from __future__ import annotations

import ast
import pathlib

from src.ui.views import page_hold as P

_VIEW = pathlib.Path(P.__file__)
_REPO = _VIEW.parents[3]

#: 掃 repo 時跳過的目錄。`tests` 也跳 —— 測試檔裡的假資料與斷言不是
#: production 的算法，混進來會讓計數失真（同 `test_p04_hold_view.py` 的作法）。
_SCAN_SKIP: frozenset[str] = frozenset({
    "__pycache__", ".git", "tests", "node_modules", ".venv", "venv", "build",
})

#: **會產出「整體資產該擺多少在股票上」這個答案**的可呼叫錨點。
#: 只認**呼叫**（`ast.Call`），不認 import／字串提及 —— 後者是 caller 或文件，
#: 把它們算進來就會犯 `CLAUDE.md §8.3` 點名的錯：把「一個 fetcher 很多 caller」
#: 誤判成「重複實作」。
_ANSWER_CALLS: frozenset[str] = frozenset({
    "compute_position_throttle",   # 姿態油門 → (lo_pct, hi_pct)
    "portfolio_exposure",          # regime → 80/50/20%
    "build_allocation_decision",   # 建議持股 SSOT 本體（仲裁者）
})

#: 常數式的答案：直接用一個具名門檻當「建議持股降至 N%」。
#: 只認 **Load**（用它），不認 Store（L0 定義那一行是輸入，不是答案）。
_ANSWER_CONSTS: frozenset[str] = frozenset({
    "EXTREME_TARGET_POSITION_PCT", "LEAD_TARGET_POSITION_PCT",
})

#: 以 dict key 形式回傳的答案（v4 否決權的「強制持股水位上限」）。
_ANSWER_KEYS: frozenset[str] = frozenset({"max_position"})

#: `get_allocation()` 那道仲裁本身的三個檔 —— 它們**不是**平行答案，是 SSOT 鏈。
_ARBITRATION_CHAIN: frozenset[str] = frozenset({
    "shared/allocation_decision.py",     # L0 純函式：min() 在這裡
    "shared/position_throttle.py",       # L0 姿態油門引擎（仲裁的輸入之一）
    "src/services/allocation_service.py",  # L3 橋樑：get_allocation()
})

#: 「這句話在講持股水位」的關鍵字。命中才進入本守衛射程 —— 本頁另有
#: 「該檔唯一 ≠ 全站唯一」那組**乘法點**的宣稱（由 `test_p04_hold_view.py`
#: 的 `TestTheLotToShareClaimIsMeasurable` 管），不該被這條連坐。
_POSITION_TOPIC: tuple[str, ...] = (
    "持股水位", "建議持股", "持股 SSOT", "曝險", "姿態油門", "get_allocation")

#: 明示否認（「**不是**全站唯一」）是誠實揭露，不是假宣稱。
#: 比對前先把 markdown 粗體與引號洗掉，才不會因為排版寫法不同而漏認。
_DENIALS: tuple[str, ...] = (
    "不是全站唯一", "不等於全站唯一", "並非全站唯一", "≠全站唯一")


def _undecorate(text: str) -> str:
    """洗掉 markdown 粗體 / 引號 / 空白，讓否認式的比對不吃排版寫法。"""
    _out = text
    for _ch in ("*", "「", "」", "『", "』", "`", " ", "　", "\n"):
        _out = _out.replace(_ch, "")
    return _out


def _iter_production_py() -> list[pathlib.Path]:
    """全 repo 的 production `.py`（跳 `_SCAN_SKIP`）。"""
    return [_p for _p in sorted(_REPO.rglob("*.py"))
            if not any(_part in _SCAN_SKIP
                       for _part in _p.relative_to(_REPO).parts)]


def _position_sites() -> dict[str, list[str]]:
    """全站**實際**算出一個「整體資產持股水位」的地方 → `{相對路徑: [證據]}`。

    **現場量測，不抄名單**（`CLAUDE.md §8.2.A.0` 規則 2：抄一份窮舉名單，
    漏一筆清單自己就變成假話）。

    ⚠️ **掃不動就當場紅，不靜默跳過**（§1）：一個 parse 不了、卻提到錨點的檔案
    有可能就是一處沒被算到的平行實作 —— 漏算會讓本檔的計數變成一句安靜的假話，
    而下游那句「全站唯一」正是靠這個計數才被判為假的。
    """
    _out: dict[str, list[str]] = {}
    _unparsed: list[str] = []
    _anchors = _ANSWER_CALLS | _ANSWER_CONSTS | _ANSWER_KEYS
    for _p in _iter_production_py():
        _rel = _p.relative_to(_REPO).as_posix()
        try:
            _txt = _p.read_text(encoding="utf-8")
            _tree = ast.parse(_txt)
        except (SyntaxError, UnicodeDecodeError, OSError):
            try:
                _raw = _p.read_bytes().decode("utf-8", "replace")
            except OSError:
                _unparsed.append(_rel)
                continue
            if any(_a in _raw for _a in _anchors):
                _unparsed.append(_rel)
            continue
        _hits: list[str] = []
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.Call):
                _f = _n.func
                _nm = (_f.id if isinstance(_f, ast.Name)
                       else _f.attr if isinstance(_f, ast.Attribute) else None)
                if _nm in _ANSWER_CALLS:
                    _hits.append(f"call:{_nm}@{_n.lineno}")
            elif (isinstance(_n, ast.Name) and _n.id in _ANSWER_CONSTS
                    and isinstance(_n.ctx, ast.Load)):
                _hits.append(f"use:{_n.id}@{_n.lineno}")
            elif (isinstance(_n, ast.Constant) and isinstance(_n.value, str)
                    and _n.value in _ANSWER_KEYS):
                _hits.append(f"key:{_n.value}@{_n.lineno}")
        if _hits:
            _out[_rel] = sorted(set(_hits))
    if _unparsed:
        raise AssertionError(
            f"這些檔案 `ast.parse` 不動、卻提到持股水位的錨點：{_unparsed} —— "
            "本守衛的計數會因此漏算，而頁 4 的誠實揭露正是建立在這個計數上。"
            "請先讓它們能被解析，不要讓計數安靜地少一筆（§1 fail loud）")
    if not _out:
        raise AssertionError(
            "全 repo 掃不到任何一處在算持股水位 —— 這不可能，"
            f"是掃描器壞了（錨點：{sorted(_anchors)}）。"
            "**不准把它讀成『只剩一處，所以全站唯一是真的』**")
    return _out


def _parallel_position_sites() -> dict[str, list[str]]:
    """**沒有**經過 `get_allocation()` 那道 `min()` 的平行答案。"""
    return {_k: _v for _k, _v in _position_sites().items()
            if _k not in _ARBITRATION_CHAIN}


def _screen_strings() -> list[str]:
    """頁 4 的所有字串常數 ＋ docstring（＝會被讀到的文案的靜態上界）。"""
    _src = _VIEW.read_text(encoding="utf-8")
    return [_n.value for _n in ast.walk(ast.parse(_src))
            if isinstance(_n, ast.Constant) and isinstance(_n.value, str)]


def _uniqueness_claims(text: str) -> list[str]:
    """`text` 裡「宣稱某個持股水位算法是**全站**唯一」的片段。空 list = 沒有。

    逐一檢查每個「全站唯一」出現處的**上下文**（±80 字），而不是整段文字 ——
    整段判斷的話，同一個大 docstring 裡只要有一句誠實揭露，
    就會把同段其他的假宣稱一起放行。
    """
    _bad: list[str] = []
    _i = text.find("全站唯一")
    while _i >= 0:
        _around = text[max(0, _i - 80): _i + 80]
        _local = _undecorate(text[max(0, _i - 14): _i + 6])
        if (any(_k in _around for _k in _POSITION_TOPIC)
                and not any(_d in _local for _d in _DENIALS)):
            _bad.append(_around)
        _i = text.find("全站唯一", _i + 1)
    return _bad


def _read(rel: str) -> str:
    """讀一個 production 檔；讀不到就當場紅（§1，不 skip）。"""
    _p = _REPO / rel
    assert _p.is_file(), (
        f"`{rel}` 不在了 —— 頁 4 的卡面點名了它。"
        "檔案被搬走／改名時，那句揭露就變成假的未納管清單，**文案必須跟著改**")
    return _p.read_text(encoding="utf-8")


def _func(rel: str, name: str) -> ast.FunctionDef:
    """取某檔裡的某個函式節點；找不到當場紅。"""
    for _n in ast.walk(ast.parse(_read(rel))):
        if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and _n.name == name:
            return _n           # type: ignore[return-value]
    raise AssertionError(
        f"`{rel}` 裡找不到 `{name}()` —— 頁 4 的卡面點名了它。"
        "被改名／被收斂掉就要回頭改文案，不能放著讓使用者讀一句假的")


def _names_in(node: ast.AST) -> set[str]:
    """節點底下出現過的識別字（`Name` / `Attribute` / `import ... as`）。"""
    _out: set[str] = set()
    for _n in ast.walk(node):
        if isinstance(_n, ast.Name):
            _out.add(_n.id)
        elif isinstance(_n, ast.Attribute):
            _out.add(_n.attr)
        elif isinstance(_n, ast.alias):
            _out.add(_n.name.rsplit(".", 1)[-1])
    return _out


def _facts_text(built) -> str:
    """把一張卡的 facts 列攤成一段字（**看印出去的字**，不是只看原始碼）。"""
    return "　".join(f"{_k}　{_v}" for _k, _v in built[1])


def _live_macro() -> "P.MacroReadout":
    return P.MacroReadout(requested=True, loaded=True, regime="bull",
                          health=70.0, defense=False,
                          posture_label="積極", posture_range="70–90%")


def _live_alloc() -> "P.AllocationReadout":
    return P.AllocationReadout(requested=True, is_loaded=True,
                               range_text="30–50%", posture="中性",
                               cap_name="VIX 否決")


# ══════════════════════════════════════════════════════════════════
# 1｜先量測，再談宣稱
# ══════════════════════════════════════════════════════════════════
class TestTheRepoReallyHasMoreThanOneWay:
    """**先量測，再談宣稱。** 把「全站不只一套持股水位算法」釘成可執行的事實。"""

    def test_the_arbitration_chain_is_still_where_we_say_it_is(self):
        """卡面說仲裁住在 `get_allocation()` —— 先證明那條鏈還在。"""
        _src = _read("src/services/allocation_service.py")
        assert "def get_allocation(" in _src, (
            "`allocation_service.get_allocation()` 不見了 —— "
            "頁 4 的「來源」列指的就是它，函式沒了那一列就是假的")
        # 仲裁鏈裡**會呼叫**答案錨點的兩支：一定要被掃到，否則錨點過期了。
        _callers = {"shared/allocation_decision.py",
                    "src/services/allocation_service.py"}
        _missing = sorted(_callers - set(_position_sites()))
        assert not _missing, (
            f"仲裁鏈這幾個檔沒有出現在量測結果裡：{_missing} —— "
            "要嘛被搬走了，要嘛掃描器的錨點過期了。兩種都會讓下面那條"
            "「平行實作有幾處」的計數失真")
        # 姿態油門引擎**只定義、不呼叫**（它是仲裁的輸入，不是另一個答案）——
        # 這也是它被排除在計數外的理由，寫成斷言免得下一個人以為是漏掉。
        assert "def compute_position_throttle(" in _read(
            "shared/position_throttle.py"), (
            "`shared/position_throttle.py` 不再定義 `compute_position_throttle()`"
            " —— 仲裁的三條輸入之一不見了，`get_allocation()` 那句「仲裁三條輸入」"
            "要跟著改")

    def test_more_than_one_place_computes_a_portfolio_position_level(self):
        """**這一條是整個檔的地基**：不只一處 → 「全站唯一」就是假的。"""
        _parallel = _parallel_position_sites()
        _flat = sorted(_parallel)
        assert len(_flat) > 1, (
            f"沒經過 `get_allocation()` 仲裁的持股水位算法只剩 {_flat} —— "
            "**這不是壞事**，但頁 4 的誠實揭露（「這不是全站唯一」＋點名那幾支）"
            "是建立在「不只一處」這個量測值上的。前提變了，文案要跟著重寫")

    def test_the_declared_ban_in_the_ssot_layer_still_stands(self):
        """L3 檔頭明文禁止呼叫端自己算 —— 那條禁令正是「平行實作＝違規」的依據。

        禁令若被刪掉，「未納管」這個說法的立足點就換了，文案要重寫。
        """
        _src = _read("src/services/allocation_service.py")
        assert "compute_position_throttle" in _src and "portfolio_exposure" in _src, (
            "`allocation_service` 檔頭那條「不得再自行 `compute_position_throttle` / "
            "`portfolio_exposure`」的禁令不見了 —— 頁 4 的揭露是靠它才說得出"
            "「這些是**未經**仲裁的平行答案」")


# ══════════════════════════════════════════════════════════════════
# 2｜正向：畫面不准再宣稱「全站唯一」
# ══════════════════════════════════════════════════════════════════
class TestNoScreenTextClaimsTheOnlyWay:
    """全站不只一套算法時，頁 4 的文案不准把 `get_allocation()` 講成全站唯一。"""

    def test_no_page_text_claims_the_repo_wide_uniqueness(self):
        """**靜態**：掃本頁全部字串常數 ＋ docstring。

        `不是全站唯一` 這種**明示否認**是誠實揭露，不在射程內。
        """
        if len(_parallel_position_sites()) <= 1:
            raise AssertionError(
                "平行實作只剩一處 —— 由 "
                "`test_more_than_one_place_computes_a_portfolio_position_level` "
                "負責提醒改文案；本條不該在這個前提下被略過")
        _bad = [_frag for _s in _screen_strings() for _frag in _uniqueness_claims(_s)]
        assert not _bad, (
            f"頁 4 文案仍宣稱持股水位算法「全站唯一」：{_bad} —— "
            f"實測另有 {sorted(_parallel_position_sites())} 沒進到那道仲裁。"
            "把「全站」兩個字刪掉還不夠，讀者仍會以為全站只有這一處，"
            "要**明說另外還有哪些**")

    def test_the_rendered_position_cap_card_says_the_measurable_thing(self):
        """**動態**：真的建出 ⑤ 那張卡，看**印出去的字**。"""
        _text = _facts_text(P.build_position_cap_card(_live_alloc()))
        assert not _uniqueness_claims(_text), (
            f"⑤ 的卡面 facts 列仍在宣稱全站唯一：{_text}")
        assert "get_allocation" in _text, (
            "卡面沒有指出水位**具體由哪一支算出來** —— "
            "只寫「SSOT」的話，讀者無從自己驗證")
        assert any("不是" in _k and "全站唯一" in _k for _k, _ in
                   P.build_position_cap_card(_live_alloc())[1]), (
            "卡面沒有把「這不是全站唯一」講成一列 —— "
            "§1：讀者會把一個只涵蓋一條仲裁鏈的保證讀成全站保證")


# ══════════════════════════════════════════════════════════════════
# 3｜反向：文案點名的那幾支現在真的還在
# ══════════════════════════════════════════════════════════════════
class TestTheNamedUnmanagedSitesStillExist:
    """**假的「未納管清單」跟假的「全站唯一」一樣糟。**

    卡面點名了四支「沒進到 `get_allocation()` 仲裁」的算法。哪天它們被收斂掉，
    這一類會轉紅 —— 那時要改的是文案，不是測試。
    """

    def test_market_alert_banner_still_sets_its_own_target_pct(self):
        """每日推播自己講「建議持股降至 N%」，完全不經過仲裁。"""
        _rel = "src/compute/notify/market_alert_banner.py"
        _used = _names_in(ast.parse(_read(_rel)))
        assert _ANSWER_CONSTS <= _used, (
            f"`{_rel}` 不再使用 {sorted(_ANSWER_CONSTS - _used)} —— "
            "頁 4 卡面點名了它，收斂掉就要改文案")
        assert "get_allocation" not in _used, (
            f"`{_rel}` 現在會走 `get_allocation()` 了 —— **這是好事**，"
            "但它已不再是「未納管」，卡面那句要改")

    def test_v4_engine_still_returns_its_own_max_position(self):
        """v4 否決權的 `max_position`（docstring 自稱「強制持股水位上限」）。"""
        _rel = "src/compute/strategy/v4_strategy_engine.py"
        _fn = _func(_rel, "check_macro_veto")
        _keys = {_n.value for _n in ast.walk(_fn)
                 if isinstance(_n, ast.Constant) and isinstance(_n.value, str)}
        assert "max_position" in _keys, (
            f"`{_rel}::check_macro_veto()` 不再回 `max_position` —— "
            "頁 4 卡面點名了它，收斂掉就要改文案")
        assert "get_allocation" not in _names_in(_fn), (
            f"`{_rel}::check_macro_veto()` 現在會走 `get_allocation()` 了 —— "
            "它已不再是「未納管」，卡面那句要改")

    def test_market_strategy_still_derives_exposure_pct_on_its_own(self):
        """`market_strategy` 的 `exposure_pct` ← `portfolio_exposure(regime)`。"""
        _rel = "src/services/market_strategy.py"
        _tree = ast.parse(_read(_rel))
        _calls = [_n for _n in ast.walk(_tree)
                  if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
                  and _n.func.id == "portfolio_exposure"]
        assert _calls, (
            f"`{_rel}` 不再呼叫 `portfolio_exposure()` —— "
            "頁 4 卡面點名了它，收斂掉就要改文案")
        assert "exposure_pct" in _read(_rel), (
            f"`{_rel}` 不再產出 `exposure_pct` —— 卡面那句要改")

    def test_the_posture_band_source_is_still_uncapped(self):
        """**最重要的一條**：④ 那格的來源 `get_station_macro()` 仍未套任何 cap。

        它就是「同一頁的自我矛盾」那一項的事實基礎。哪天它改成走
        `get_allocation()`，同頁矛盾就消失了 —— 那時 ④ 的「未套天花板」
        說明要拿掉，否則變成另一句假話。
        """
        _rel = "src/services/dividend_station_service.py"
        _fn = _func(_rel, "get_station_macro")
        _used = _names_in(_fn)
        assert "compute_position_throttle" in _used, (
            f"`{_rel}::get_station_macro()` 不再自行呼叫 "
            "`compute_position_throttle()` —— 頁 4 ④ 的「未套天花板」說明要跟著改")
        _caps = {"get_allocation", "build_allocation_decision",
                 "vix_veto_cap", "ring_gate_cap", "exposure_limit_pct"}
        _now_capped = sorted(_caps & _used)
        assert not _now_capped, (
            f"`{_rel}::get_station_macro()` 現在會套天花板了（{_now_capped}）"
            " —— **這是好事**，但 ④ 那格「未套任何天花板」的說明就變成假的，"
            "文案要跟著改")
        assert "posture_range" in _read(_rel), (
            f"`{_rel}` 不再產出 `posture_range` —— 頁 4 ④ 印的就是它")


# ══════════════════════════════════════════════════════════════════
# 4｜同一頁的自我矛盾必須被講出來
# ══════════════════════════════════════════════════════════════════
class TestTheSamePageContradictionIsDisclosed:
    """④ 與 ⑤ 同時印兩個持股區間、口徑不同 —— 使用者不會自己知道。

    這是本輪最該讓使用者看到的一件事：宣稱「唯一」的那一頁，
    同一頁就印了一個不經同一仲裁的持股區間。
    """

    def test_the_posture_band_row_admits_it_is_uncapped(self):
        """④ 的「姿態油門帶」那一列要自己講「未套天花板」。"""
        _built = P.build_macro_stage_card(_live_macro())
        _rows = [(_k, _v) for _k, _v in _built[1] if "姿態油門帶" in _k]
        assert _rows, "④ 不再印「姿態油門帶」了 —— 那 ⑤ 卡面點名它的那句要改"
        _text = _undecorate("　".join(f"{_k}{_v}" for _k, _v in _rows))
        assert "天花板" in _text, (
            f"④ 的姿態油門帶沒講它未套天花板：{_rows} —— "
            "使用者會把它和 ⑤ 的水位讀成同一個口徑")
        assert "get_station_macro" in _text, (
            "④ 沒指出這條帶子**具體從哪一支來** —— 讀者無從自己驗證口徑不同")

    def test_the_posture_band_row_points_at_the_final_number(self):
        """光說「不同」不夠，要告訴使用者**該看哪一個**。"""
        _built = P.build_macro_stage_card(_live_macro())
        _text = _undecorate(_facts_text(_built))
        assert "建議持股水位" in _text, (
            "④ 沒有把使用者導到 ⑤「建議持股水位（市場端）」那一格 —— "
            "同頁兩個區間卻不說哪個是最終值，等於留給使用者自己猜")
        assert P.build_position_cap_card(_live_alloc())[0].label in \
            _undecorate("".join(_facts_text(_built))), (
            "④ 指過去的名字和 ⑤ 那張卡的實際 label 對不起來 —— "
            "使用者照著找會找不到")

    def test_the_posture_band_value_is_still_shown(self):
        """⚠️ **只加說明，不准把數字拿掉**（拿掉是功能變更，A-8 要先送草稿）。"""
        _built = P.build_macro_stage_card(_live_macro())
        assert "70–90%" in _facts_text(_built), (
            "④ 的姿態油門帶數字不見了 —— 本輪只准加說明文字，"
            "拿掉一格是版面／功能變更，依 `CLAUDE.md §-1.5` A-8 要先出線框草稿")

    def test_no_uncapped_warning_when_there_is_no_band_to_warn_about(self):
        """**邊界**：`posture_range` 為空（總經未評估）→ 那一列整列不印。

        只印「未套天花板的原始帶」卻沒有數字，等於憑空生出一個不存在的觀測
        （§1：畫出來就是造假）。空字串／未評估兩種都測。
        """
        for _m in (P.MacroReadout(requested=True, loaded=True, health=70.0,
                                  posture_range=""),
                   P.MacroReadout(requested=True, loaded=False)):
            _rows = [_k for _k, _ in P.build_macro_stage_card(_m)[1]
                     if "姿態油門帶" in _k or "天花板" in _k]
            assert not _rows, (
                f"沒有姿態帶可印，卻仍印了 {_rows}（輸入：{_m}）—— "
                "一句沒有數字的「未套天花板」是憑空生出的觀測")

    def test_the_position_cap_card_names_the_same_page_contradiction(self):
        """⑤ 的揭露列要把「本頁 ④ 也是一個未納管的答案」講出來。

        點名別人家的三支很容易，講自己這一頁最難 —— 而那正是使用者唯一
        會同時看到的兩個數字。
        """
        _text = _undecorate(_facts_text(P.build_position_cap_card(_live_alloc())))
        assert "姿態油門帶" in _text, (
            "⑤ 的揭露沒有點名**同一頁**的姿態油門帶 —— "
            "只講別的模組，等於讓使用者以為這一頁內部是一致的")
        for _nm in ("market_alert_banner", "max_position", "exposure_pct"):
            assert _nm in _text, (
                f"⑤ 的揭露沒點名 `{_nm}` —— 「另有未納管的算法」若不指名道姓，"
                "讀者無法自己 grep 驗證，那句揭露就退回成另一句要人相信的話")
