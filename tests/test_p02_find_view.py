"""tests/test_p02_find_view.py — FE-9 的**第一支**頁 2 守衛（IA v2「🔍 找標的」）。

守的是 `src/ui/views/page_find.py`。**在本檔之前，頁 2 是零守衛的** ——
FE-8 自陳那是它最大的缺口：整頁的誠實性（三態不混、gate 不從資料反推、
未接線不靜默降級）**沒有任何一條被釘住**，全靠檔頭 docstring 的自我宣稱。

風格與粒度沿用 `tests/test_p01_today_view.py`：**一條測試對應一個具體的
說謊方式**，不是補覆蓋率。對應表：

  · `TestThreeEmptiesNeverMix`      ← 三態混用：「還沒選」／「選了 0 檔」／
    「上游掛了」被畫成同一種灰，使用者無從分辨自己該做什麼。
  · `TestRequestedIsNotDerivedFromData` ← gate 從資料反推（頁 1 的恆真式事故）。
    ⚠️ **本檔的檢查刻意設計成比 `tests/test_ui_state_model.py` 更強** ——
    那支只比對 `requested=` 與 `has_value=` 的 AST 是否**逐字相同**，
    而頁 1 的 `requested=(alloc is not None)` / `has_value=bool(alloc.is_loaded)`
    逐字不同、卻恆真，於是整個溜過去。做法見該類 docstring；
    `TestTheGuardIsActuallyStronger` 用合成程式碼**實跑證明**強在哪。
  · `TestNothingIsCalledBeforeYouAsk` ← 「沒按就不取數」只是 docstring 宣稱。
    本條把 L3 全部下毒（毒藥**不繼承 `Exception`**，本頁的 try/except 吞不掉），
    再跑一次 loader —— 碰到就當場紅。
  · `TestContractDriftIsNotZeroRows`  ← `rows is None`（回傳契約漂移）被寫成
    「0 檔」＝ 替上游宣稱一件它沒說的事（§1：錯誤的數字比沒有數字更危險）。
  · `TestUnwiredStaysUnwired`         ← 未接線的兩項被「按一次就變好」或
    三要素留空（鐵律 4）。
  · `TestCheckedFactorIsNeverSilentlyDropped` ← 勾了估值因子卻靜默不算
    ＝ §1 禁止的掩蓋問題（L3 的 note **不會**提到 pe 缺料，只能本頁自己講）。
  · `TestFormStructure`               ← 線框 F11：form 內放 `st.button`
    實跑即拋 `StreamlitAPIException`；一個 form 只准一顆 submit。
  · `test_page_mounts_clean`（slow）   ← 這一頁真的畫得出來，不是半截死頁。

⚠️ **這些是護欄，不是證明**（同 `tests/test_ui_state_model.py` 與
`tests/test_p01_today_view.py` 的自陳）：釘住的是「已知的那幾種說謊方式
不會再回來」，**不是**「這一頁不會再說謊」。全綠不等於合規。
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import sys

import pytest

from shared.station_specs import MISS_CONTRACT_DRIFT
from shared.ui_state import (
    UI_DEGRADED,
    UI_EMPTY,
    UI_FAILED,
    UI_IDLE,
    UI_LIVE,
    UI_UNWIRED,
)
from src.ui.tabs.tab_today import Note
from src.ui.views import page_find as P

_VIEW = pathlib.Path(P.__file__)


def _tree() -> ast.Module:
    return ast.parse(_VIEW.read_text(encoding="utf-8"))


#: 別名 —— 給類別內部用，避免與該類的區域變數 `_tree` 撞名。
_tree_of_view = _tree


class _Frame:
    """`len()` 讀得出來的最小 DataFrame 替身（本檔不需要 pandas）。"""

    def __init__(self, n: int) -> None:
        self._n = n

    def __len__(self) -> int:
        return self._n


def _screen(**kw):
    """`build_screen_result_card` 的呼叫殼 →（Card, facts dict）。"""
    _req = P.ScreenRequest(submitted=kw.pop("submitted", True),
                           factors=tuple(kw.pop("factors", ())),
                           top_n=kw.pop("top_n", P.DEFAULT_TOP_N))
    _res = P.ScreenResult(requested=_req.submitted, **kw)
    _card, _facts = P.build_screen_result_card(_res, _req)
    return _card, dict(_facts)


def _note_triple(note: Note | None) -> tuple[str, str, str]:
    assert note is not None, "非 live 態一定要有 Note（鐵律 4，`Card` 已擋）"
    return note.now, note.why, note.where


# ══════════════════════════════════════════════════════════════════
# 【1】三種「沒有結果」絕不可混
# ══════════════════════════════════════════════════════════════════
class TestThreeEmptiesNeverMix:
    """本頁的 §1 主戰場（檔頭「三種『沒有結果』絕不可混」那一段）。

    `idle` = 還沒有人叫過 ／ `empty` = 叫了、跑完了、真的 0 檔（**有效結果**）
    ／ `failed` = 上游掛了（唯一准用紅色的狀態）。
    三者若被畫成同一種灰，使用者無從知道自己該「按一下」「放寬條件」
    還是「回報維護者」—— 那三個動作完全不同。
    """

    def test_idle_is_idle(self):
        """冷啟動：**沒有人叫過**。不是 empty、更不是 failed。"""
        _card, _ = _screen(submitted=False)
        assert _card.state == UI_IDLE
        assert _card.value == "", "idle 不准帶結論文字（`Card` 已擋，這裡是語意確認）"

    def test_zero_rows_is_empty_and_says_so(self):
        """跑完了、0 檔 → `empty`，且 Note **明講這是一個有效的結果**。"""
        _card, _ = _screen(df=_Frame(0), rows=0, survivors_n=274)
        assert _card.state == UI_EMPTY
        _now, _why, _where = _note_triple(_card.note)
        assert "0 檔" in _now
        assert "有效的結果" in _why, (
            "0 檔沒有被說成『有效結果』→ 使用者會以為是故障或還沒跑")
        assert "還沒跑" in _why and "故障" in _why

    def test_upstream_failure_is_failed(self):
        """上游拋例外 → `failed`（紅），且**原始例外看得見**。"""
        _card, _ = _screen(error='RuntimeError("finmind quota")')
        assert _card.state == UI_FAILED
        assert "finmind quota" in _card.note.why, "原始例外必須看得見（§1）"

    def test_the_three_states_are_pairwise_distinct(self):
        """三態互斥：**同一組資料形狀**下，三個狀態兩兩不同。"""
        _states = [
            _screen(submitted=False)[0].state,
            _screen(df=_Frame(0), rows=0)[0].state,
            _screen(error='RuntimeError("boom")')[0].state,
        ]
        assert len(set(_states)) == 3, f"三態被畫成同一種：{_states}"
        assert _states == [UI_IDLE, UI_EMPTY, UI_FAILED]

    def test_the_three_wheres_point_at_three_different_actions(self):
        """三態的「去哪補」必須指向**三個不同的動作**，否則分態沒有意義。"""
        _idle = _note_triple(_screen(submitted=False)[0].note)[2]
        _empty = _note_triple(_screen(df=_Frame(0), rows=0)[0].note)[2]
        _failed = _note_triple(
            _screen(error='RuntimeError("boom")')[0].note)[2]
        assert len({_idle, _empty, _failed}) == 3
        assert P.ACTION_RUN_SCREEN_LABEL in _idle, "idle 要指路到那顆 submit"
        assert "放寬條件" in _empty, "empty 要給的是『改條件』，不是『再按一次』"

    def test_sector_flow_cache_not_ready_is_grey_not_red(self):
        """`ok=False` 是 reader 的 sentinel（快取還沒產生）——

        把它畫成紅色就是 v3 §02 前半句要杜絕的**假性錯誤**，
        而滿版假紅字會讓真正的錯誤沒人看得見（`CLAUDE.md §1.A` 第 4 點）。
        """
        _card, _ = P.build_sector_flow_card(
            P.SectorFlowReadout(requested=True, ok=False, reason="快照未產生"))
        assert _card.state == UI_EMPTY, "快取沒生出來不是故障"
        assert "不是故障" in _card.note.why

    def test_sector_flow_stale_is_degraded_not_live(self):
        """過期快照有值可讀，但**不是今天的** → `degraded`，不得畫成 live。"""
        _card, _ = P.build_sector_flow_card(P.SectorFlowReadout(
            requested=True, ok=True, stale=True,
            sectors=({"sector": "半導體", "quadrant": "漲潮"},)))
        assert _card.state == UI_DEGRADED
        assert _card.value == "", "非 live 不准帶結論文字"

    def test_sector_flow_idle_is_not_empty(self):
        _card, _ = P.build_sector_flow_card(
            P.SectorFlowReadout(requested=False))
        assert _card.state == UI_IDLE
        assert P.ACTION_LOAD_MAP_LABEL in _card.note.where


# ══════════════════════════════════════════════════════════════════
# 【2】`requested=` 是 gate 旗標，不是從資料反推
# ══════════════════════════════════════════════════════════════════
#: `requested=` 運算式裡**唯一允許被讀出來的欄位名**。
#: 白名單（不是黑名單）是本檔比 `test_ui_state_model` 強的第一個地方：
#: 黑名單只擋得住「想得到的那幾個名字」，白名單擋掉**所有沒被宣告成 gate 的東西**。
_GATE_ATTRS: frozenset[str] = frozenset({"requested", "submitted"})

#: 明確的結果資料名 —— 第二道網（與白名單獨立，兩道都要過）。
#: **由 dataclass 自己的欄位推出來**，不是手抄一份會漂移的清單。
_PAYLOAD_TOKENS: frozenset[str] = (
    frozenset(P.ScreenResult.__dataclass_fields__)
    | frozenset(P.SectorFlowReadout.__dataclass_fields__)
    | frozenset({"has_rows", "df", "rows", "result", "empty", "len",
                 "shape", "size", "values", "index", "any", "all"})
) - _GATE_ATTRS


def _leaf_names(node: ast.AST) -> set[str]:
    """運算式**實際讀出來的識別字**（容器名不算，讀的欄位才算）。

    - `result.requested` → `{"requested"}`（`result` 是容器，讀的是 `requested`）
    - `bool(flow.sectors)` → `{"bool", "sectors"}`
    - `not df.empty`      → `{"df", "empty"}`（`df` 是裸 Name，被當值用了）
    - `len(rows) > 0`     → `{"len", "rows"}`
    """
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
        _req = _kw["requested"]
        _names = _leaf_names(_req)
        # (a) 白名單：讀出來的欄位只准是 gate 欄位；容器名與布林轉換不算。
        _illegal = {_x for _x in _names
                    if _x not in _GATE_ATTRS and not _x.endswith("requested")
                    and not _x.endswith("submitted") and _x != "bool"}
        if _illegal:
            _bad.append(f"line {_call.lineno}: requested= 讀了非 gate 的東西 "
                        f"{sorted(_illegal)}")
        # (b) 黑名單：明確的結果資料名一個都不准出現。
        _payload = _names & _PAYLOAD_TOKENS
        if _payload:
            _bad.append(f"line {_call.lineno}: requested= 含結果資料名 "
                        f"{sorted(_payload)}")
        # (c) 舊護欄（`test_ui_state_model` 那條）也照跑一次：AST 不得相同。
        if "has_value" in _kw and ast.dump(_req) == ast.dump(_kw["has_value"]):
            _bad.append(f"line {_call.lineno}: requested= 與 has_value= "
                        "是同一個運算式")
        # (d) 讀出來的欄位不得與 has_value= 的欄位重疊
        #     （`requested=x.rows` / `has_value=bool(x.rows)` 這種）。
        if "has_value" in _kw:
            _overlap = (_names & _leaf_names(_kw["has_value"])) - {"bool"}
            if _overlap:
                _bad.append(f"line {_call.lineno}: requested= 與 has_value= "
                            f"讀同一個欄位 {sorted(_overlap)}")
    return _bad


class TestRequestedIsNotDerivedFromData:
    """L0 的鐵律：**`idle` 只能由上游帶下來，禁止由 `if not data:` 推導。**

    `tests/test_ui_state_model.py` 只做上面的 (c)（兩邊 AST 是否逐字相同），
    頁 1 的 `requested=(alloc is not None)` 配 `has_value=bool(alloc.is_loaded)`
    就是這樣溜過去的 —— 逐字不同、卻恆真。
    本檔改成 **(a) 白名單 ＋ (b) 黑名單 ＋ (c) 舊護欄 ＋ (d) 欄位不重疊** 四道，
    其中 (a) 才是真正的加強：`requested=` 只准讀被宣告為 gate 的欄位
    （`requested` / `submitted` / `*_requested` / `*_submitted`），
    **任何沒被宣告成 gate 的東西出現在那裡就是紅燈**，不必先想得到它的名字。
    """

    def test_there_are_calls_to_guard(self):
        _calls = list(_classify_calls(_tree()))
        assert len(_calls) >= 3, (
            f"頁 2 應有 3 個 gate（選股 / 熱力圖 / 泡泡圖），實際找到 {len(_calls)}")

    def test_every_call_passes_requested(self):
        for _call in _classify_calls(_tree()):
            assert any(_k.arg == "requested" for _k in _call.keywords), (
                f"{_VIEW.name}:{_call.lineno} 沒有傳 `requested=`")

    def test_no_call_derives_requested_from_result_data(self):
        _bad = _requested_offences(_tree())
        assert not _bad, (
            "`requested=` 從資料反推了（idle 只能由上游帶下來）：\n  "
            + "\n  ".join(_bad))

    def test_the_gate_keys_are_written_by_handlers_only(self):
        """gate 的兩個 session key **只有** submit / button handler 會寫。

        寫入點若多一個，「有沒有人叫過」就不再是事實，而是可以被別人偽造的值。
        """
        _tree_ = _tree()
        _writes: dict[str, list[str]] = {P.SS_APPLIED_SCREEN: [],
                                         P.SS_MAP_REQUESTED: []}
        for _fn in ast.walk(_tree_):
            if not isinstance(_fn, ast.FunctionDef):
                continue
            for _s in ast.walk(_fn):
                if not (isinstance(_s, ast.Assign) and _s.targets
                        and isinstance(_s.targets[0], ast.Subscript)):
                    continue
                _sub = _s.targets[0]
                if not (isinstance(_sub.slice, ast.Name)):
                    continue
                for _key, _const in ((P.SS_APPLIED_SCREEN, "SS_APPLIED_SCREEN"),
                                     (P.SS_MAP_REQUESTED, "SS_MAP_REQUESTED")):
                    if _sub.slice.id == _const:
                        _writes[_key].append(_fn.name)
        assert _writes[P.SS_APPLIED_SCREEN] == ["_render_screen_form"], (
            f"選股 gate 的寫入點變成 {_writes[P.SS_APPLIED_SCREEN]} —— "
            "它必須只有 submit handler 一處")
        assert _writes[P.SS_MAP_REQUESTED] == ["_render_map_leaf"], (
            f"地圖 gate 的寫入點變成 {_writes[P.SS_MAP_REQUESTED]}")

    def test_reader_looks_at_key_existence_not_content(self):
        """`bool(值)` 分不出「還沒選」與「選了但空」→ 只准看 key 在不在。"""
        assert P.applied_screen_request({}).submitted is False
        assert P.applied_screen_request(
            {P.SS_APPLIED_SCREEN: None}).submitted is True, (
            "key 在就是『送出過』—— 看內容會讓『選了但 0 個因子』退化成 idle")
        assert P.applied_screen_request(
            {P.SS_APPLIED_SCREEN: {"factors": [], "top_n": 20}}
        ).submitted is True

    def test_a_result_with_data_but_no_gate_cannot_even_be_built(self):
        """**恆真式的直接反證**，但真實情況比預期更嚴：這種卡**構造不出來**。

        紅隊本來想驗「有資料、沒人按過 → 仍是 idle」，實跑發現 L0
        `classify_ui_state` 在 `requested=False` 卻帶著本輪的值時**當場 raise**
        （§1 Fail Loud）—— 也就是「把資料的有無當成請求訊號」在本頁**不會
        安靜地畫出一張錯的卡，而是炸掉**。本條把那個事實釘住：
        它是比「畫成 idle」更強的保護，日後若有人把那道 raise 拿掉，本條轉紅。
        """
        _res = P.ScreenResult(requested=False, df=_Frame(50), rows=50,
                              survivors_n=274)
        with pytest.raises(ValueError, match="requested=False"):
            P.build_screen_result_card(_res, P.ScreenRequest(submitted=False))

    def test_the_page_never_produces_that_contradiction_itself(self):
        """而本頁自己的 loader 走不到上面那個矛盾：沒按 → 什麼都不帶回來。"""
        _res = P.load_screen_result(P.ScreenRequest(submitted=False))
        assert (_res.requested, _res.rows, _res.df) == (False, None, None)
        _card, _ = P.build_screen_result_card(
            _res, P.ScreenRequest(submitted=False))
        assert _card.state == UI_IDLE


class TestTheGuardIsActuallyStronger:
    """把「比 `test_ui_state_model` 更強」寫成**可執行的證明**，不是宣稱。

    做法：拿三段合成程式碼餵給兩邊的判定 ——
    舊護欄（AST 是否逐字相同）放行的，本檔的檢查必須攔下來。
    ⚠️ 誠實邊界：這證明的是「本檔的檢查嚴格覆蓋舊護欄的已知漏洞」，
    **不是**「本檔的檢查抓得到所有反推寫法」。它仍是護欄，不是證明。
    """

    #: 頁 1 真實發生過的恆真式（`get_allocation()` 永不回 None）。
    P01_TAUTOLOGY = ("classify_ui_state(requested=(alloc is not None), "
                     "has_value=bool(alloc.is_loaded))")
    #: 直接拿 DataFrame 反推。
    FROM_FRAME = ("classify_ui_state(requested=not result.df.empty, "
                  "has_value=bool(result.rows))")
    #: 語意等價、寫法不同（舊護欄 docstring 自陳抓不到的那一種）。
    LEN_VS_BOOL = ("classify_ui_state(requested=len(rows) > 0, "
                   "has_value=bool(rows))")
    #: 本頁真正在用的寫法（必須放行，否則這條檢查只是把所有東西都擋掉）。
    GOOD = ("classify_ui_state(requested=result.requested, "
            "error=result.error or None, has_value=result.has_rows)")

    @staticmethod
    def _old_guard_says_ok(src: str) -> bool:
        """`test_ui_state_model.TestNoDerivedRequested` 的判定，逐條照抄。"""
        for _call in _classify_calls(ast.parse(src)):
            _kw = {_k.arg: _k.value for _k in _call.keywords if _k.arg}
            if "requested" not in _kw or "has_value" not in _kw:
                continue
            if all(isinstance(_kw[_k], ast.Constant)
                   for _k in ("requested", "has_value")):
                continue
            if ast.dump(_kw["requested"]) == ast.dump(_kw["has_value"]):
                return False
        return True

    @pytest.mark.parametrize("name", ["P01_TAUTOLOGY", "FROM_FRAME",
                                      "LEN_VS_BOOL"])
    def test_old_guard_lets_them_through_but_this_one_does_not(self, name):
        _src = getattr(self, name)
        assert self._old_guard_says_ok(_src), (
            f"前提變了：{name} 現在連舊護欄都擋得住，本條要換一個樣本")
        assert _requested_offences(ast.parse(_src)), (
            f"{name} 溜過本檔的檢查 —— 那就沒有比舊護欄強")

    def test_the_shape_this_page_actually_uses_is_allowed(self):
        assert not _requested_offences(ast.parse(self.GOOD)), (
            "本頁真正在用的寫法被擋掉了 —— 檢查太嚴等於沒有檢查（會被關掉）")


# ══════════════════════════════════════════════════════════════════
# 【3】沒按之前，一行 L3 都不呼叫
# ══════════════════════════════════════════════════════════════════
class _L3Touched(BaseException):
    """毒藥。**刻意不繼承 `Exception`** —— 本頁每一支 loader 都是

    `except Exception`，繼承 `Exception` 的話會被吞成一則 aux 錯誤，
    測試照樣綠、而 L3 其實已經被呼叫過了。不繼承才穿得出來。
    """


class _PoisonModule:
    """任何屬性取用都當場引爆的假模組。"""

    def __init__(self, name: str) -> None:
        self.__name__ = name

    def __getattr__(self, item: str):
        raise _L3Touched(f"{self.__name__}.{item} 在 requested=False 時被碰到了")


#: 頁 2 檔頭「取數」表列出的全部下游（L3 六支 ＋ L4 繪圖 ＋ L5 純函式）。
#: ⚠️ 2026-09-07 FE-18 補上本批接線的 `valuation_service` —— **漏補的話它就
#: 沒有被下毒**，「沒按之前一行 L3 都不呼叫」對它形同虛設（測試照樣綠、
#: 而它其實已經被呼叫過了）。
_DOWNSTREAM = (
    "src.services.fundamental_screener_service",
    "src.services.valuation_service",
    "src.services.shortage_screener_service",
    "src.services.rs_leader_service",
    "src.services.allocation_service",
    "src.services.sector_flow_service",
    "src.ui.render.sector_flow_render",
    "src.ui.tabs.tab_stock_picker",
    # 2026-09-07 FE-32 接線的熱力圖兩支（L3 取數 ＋ L4 組圖）。
    # ⚠️ **漏補的話它們就沒有被下毒**，「沒按之前一行 L3 都不呼叫」對它們
    # 形同虛設 —— 測試照樣綠，而那一整批冷抓其實已經發出去了。
    "src.services.sector_heatmap_service",
    "src.ui.render.sector_heatmap_render",
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
    寫給使用者看（「在你送出之前，本頁一次 L3 取數都不會發」）；
    宣稱與實作若不一致，那就是對使用者說謊（§1）。
    """

    def test_screen_loader_touches_nothing(self, poisoned):
        _res = P.load_screen_result(P.ScreenRequest(submitted=False))
        assert _res.requested is False
        assert (_res.df, _res.rows, _res.survivors_n) == (None, None, None)
        assert (_res.pe_n, _res.name_n) == (None, None), (
            "沒叫過卻有估值檔數 —— 那一輪取數被提前發出去了")
        assert _res.aux_errors == (), "沒叫過就不該有任何週邊錯誤"

    def test_sector_flow_loader_touches_nothing(self, poisoned):
        _flow = P.load_sector_flow({}, requested=False)
        assert _flow.requested is False and _flow.sectors == ()

    def test_the_poison_really_would_have_fired(self, poisoned):
        """**反證**：同一組毒藥下，`requested=True` 一定炸。

        沒有這一條，上面兩條可能只是因為毒藥根本沒裝上去而綠。
        """
        with pytest.raises(_L3Touched):
            P.load_screen_result(P.ScreenRequest(submitted=True,
                                                 factors=("eps_high",)))
        with pytest.raises(_L3Touched):
            P.load_sector_flow({}, requested=True)

    def test_the_pe_loader_is_really_inside_the_poison(self, poisoned):
        """**針對性反證**（本批新增）：估值那一支真的在毒藥的射程內。

        上一條是整支 `load_screen_result()`，它可能在**碰到估值之前**就先被
        存活池那一支引爆而綠 —— 那樣的話「估值沒被提前呼叫」其實沒有被驗到。
        本條直接叫估值那一支，把射程釘死。
        """
        with pytest.raises(_L3Touched):
            P._load_pe_name_maps()

    def test_idle_note_promise_matches_the_code(self):
        """畫給使用者看的那句承諾，與上面實測到的行為必須是同一件事。"""
        assert "一次 L3 取數都不會發" in P.SCREEN_IDLE_WHY


# ══════════════════════════════════════════════════════════════════
# 【4】`rows is None`（契約漂移）不得被寫成「0 檔」
# ══════════════════════════════════════════════════════════════════
class TestContractDriftIsNotZeroRows:
    """`rows == 0` ＝ 跑完了、真的沒有符合的（有效結果，灰）；

    `rows is None` ＝ L3 回了一個**讀不出列數的東西**（既有實作恆回
    DataFrame，走到這裡代表回傳契約變了）→ 走 `MISS_CONTRACT_DRIFT` 升紅。
    兩者都畫成「0 檔」＝ **替上游宣稱一件它沒說的事**
    （§1：錯誤的數字比沒有數字更危險）。
    """

    def test_none_rows_escalates_to_failed(self):
        _card, _ = _screen(df=object(), rows=None, survivors_n=274)
        assert _card.state == UI_FAILED, (
            "契約漂移被當成 0 檔了 —— 那是替上游宣稱它沒說過的事")

    def test_none_rows_never_says_zero(self):
        _card, _ = _screen(df=object(), rows=None)
        _now, _why, _where = _note_triple(_card.note)
        assert "0 檔" not in _now and "0 檔" not in _why
        assert "讀不出" in _now
        assert "改程式" in _where, "契約漂移重跑不會好，指路句要講清楚"

    def test_zero_and_none_are_different_states(self):
        assert _screen(df=_Frame(0), rows=0)[0].state == UI_EMPTY
        assert _screen(df=object(), rows=None)[0].state == UI_FAILED

    def test_the_reason_constant_is_the_l0_one(self):
        """用的是 L0 的語彙，本檔**不自己判**「這算不算故障」。"""
        from shared.ui_state import FAILED_REASONS

        assert MISS_CONTRACT_DRIFT in FAILED_REASONS
        assert "MISS_CONTRACT_DRIFT" in _VIEW.read_text(encoding="utf-8")

    def test_an_upstream_exception_still_wins_over_drift(self):
        """有例外時走例外那一支（訊息更具體），不得被漂移分支蓋掉。"""
        _card, _ = _screen(rows=None, error='RuntimeError("boom")')
        assert _card.state == UI_FAILED
        assert "boom" in _card.note.why

    def test_survivors_unknown_is_a_dash_not_zero(self):
        """存活池取不到 → 顯示「—」。**不寫 0**（§1 不假報）。"""
        assert P._fmt_count(None) == "—"
        assert P._fmt_count(0) == "0"
        _card, _facts = _screen(df=_Frame(0), rows=0, survivors_n=None)
        assert "— 檔" in _facts["存活池"]


# ══════════════════════════════════════════════════════════════════
# 【5】未接線的兩項恆為未接線
# ══════════════════════════════════════════════════════════════════
class TestHeatmapIsWiredAndTellsTheTruth:
    """產業熱力圖 —— **2026-09-07 FE-32 接線後改寫**（原 `TestUnwiredStaysUnwired`）。

    ⚠️ **這不是放寬斷言。** 原本這裡釘的是「熱力圖恆為 `UI_UNWIRED`、
    `_why` 必須含 `DuplicateWidgetID`」。那兩條在接線之前**是對的**：
    當時本頁真的畫不出熱力圖，而畫不出來的原因真的是那五個寫死的 widget key。

    **接上之後照原樣留著它們，反而會變成本頁最大的謊**：卡片對使用者說
    「這裡沒有出口、按了也不會變」，而其實上面那顆「🗺️ 載入板塊地圖」按下去
    就會出圖。那正是 `CLAUDE.md §1.A` 第 4 點要防的方向——把**有**的東西
    講成**沒有**，跟把沒有的講成有一樣是造假。
    （同一個處置在 FE-18 對「估值（本益比）」已經走過一次。）

    改成**正向守衛**：釘住四態各自正確、且**沒有一態是靠猜的**。
    另外兩條「接線前的保護」各有替身，不是被刪掉：
      · 「不得跨檔直取 L4 私有符號 / 不得自己抄一份類股表」
        → `tests/test_sector_heatmap_universe_single_source.py`
      · 「不得與舊分頁撞 widget key」
        → 下方 `TestHeatmapKeysNeverCollideWithTheOldTab`（**新的、更硬**：
          原本只是卡片文字裡的一句宣稱，現在是 AST 實測）。
    """

    def _hm(self, **kw):
        return P.HeatmapReadout(**kw)

    def test_not_pressed_is_idle_not_empty_and_not_red(self):
        """沒按 → 灰的 idle。**不是紅**（線框葉2 grey 原文）。"""
        _card, _facts = P.build_heatmap_card(self._hm(requested=False))
        assert _card.state == UI_IDLE
        assert _card.value == "", "idle 不准帶結論文字"
        _now, _why, _where = _note_triple(_card.note)
        assert all((_now.strip(), _why.strip(), _where.strip())), "鐵律 4"
        assert P.ACTION_LOAD_MAP_LABEL in _where, "灰態要指去那顆按鈕"
        assert _facts_nonempty(_facts)

    def test_pressed_and_nothing_came_back_is_red_not_grey(self):
        """按了、**一檔都沒抓到** → 🔴（線框葉2 `err` 原文）。

        ⚠️ 這一條是本類最重要的一條，而且**規劃組原本提的是灰態**。
        灰（`UI_EMPTY`）的語意是「還沒有人叫過 / 東西還沒生出來」——
        使用者已經按下去、上游一檔都沒回來，那是**真故障**。
        畫成灰的話，真正的斷線會被讀成「我還沒按」，於是沒有人去看網路／proxy。
        對照泡泡圖那半：它的 `ok=False` 是「盤後任務還沒產生快取」，**那才是灰的**。
        **兩者長得像、語意相反，這一條就是釘住它們不准合流。**
        """
        _card, _ = P.build_heatmap_card(
            self._hm(requested=True, any_data=False, sectors_n=10, sub_total_n=32))
        assert _card.state == UI_FAILED, (
            "「按了但一檔都沒抓到」被畫成了灰態 —— 那會讓真正的斷線沒人看見")
        assert _card.state != UI_EMPTY
        _now, _why, _where = _note_triple(_card.note)
        assert "0" not in _now, "紅態的標題不該出現 0，避免讀成「0% 持平」"
        assert "填 0" in _why or "冒充" in _why, "要講明沒有拿 0 把格子填滿"

    def test_partial_coverage_is_degraded_and_says_blanks_are_blank(self):
        """只抓到一部分 → 橘。缺格**留白**，不是 0%。"""
        _card, _facts = P.build_heatmap_card(self._hm(
            requested=True, any_data=True, complete=False,
            fetched_n=8, sectors_n=10, sub_fetched_n=20, sub_total_n=32))
        assert _card.state == UI_DEGRADED
        _now, _why, _where = _note_triple(_card.note)
        assert "8/10" in _why and "20/32" in _why, "覆蓋率要講出實際數字"
        assert "留白" in _why, "缺格是留白，不是 0"
        assert dict(_facts)["資料覆蓋率"].strip()

    def test_full_coverage_is_live_with_a_real_number(self):
        _card, _facts = P.build_heatmap_card(self._hm(
            requested=True, any_data=True, complete=True,
            fetched_n=10, sectors_n=10, sub_fetched_n=32, sub_total_n=32))
        assert _card.state == UI_LIVE
        assert _card.value == "10 個類股"
        assert _card.note is None, "live 不需要空狀態三要素"

    def test_the_idle_market_label_matches_l3(self):
        """本頁「還沒載入」時顯示的市場名，必須與 L3 之後真的回的那個一致。

        本頁刻意不 module-level import L3（見該常數的註解），代價是同一個
        字串有兩份。**兩份就會漂移**，除非有人在比 —— 這一條就是那個人。
        """
        from src.services import sector_heatmap_service as S

        _expect = (S.MARKET_LABEL_US if P.HEATMAP_IS_US else S.MARKET_LABEL_TW)
        assert P.HEATMAP_MARKET_LABEL_IDLE == _expect, (
            f"本頁 idle 顯示 {P.HEATMAP_MARKET_LABEL_IDLE!r}，"
            f"但 L3 之後會回 {_expect!r} —— 使用者按下去會看到市場名突然變了")
        _card, _facts = P.build_heatmap_card(P.HeatmapReadout(requested=False))
        assert _expect in dict(_facts)["市場 / 區間"]

    def test_an_exception_is_red_and_carries_the_message(self):
        _card, _ = P.build_heatmap_card(self._hm(
            requested=True, error="RuntimeError('yfinance 掛了')"))
        assert _card.state == UI_FAILED
        _now, _why, _where = _note_triple(_card.note)
        assert "yfinance 掛了" in _why, "§1：原始例外訊息必須看得見"
        assert "sector_heatmap_service" in _why, "出處要講對是哪一層"

    def test_the_state_is_never_decided_by_the_page_itself(self):
        """四態一律走 L0 `classify_ui_state`，本頁不得自己寫 `state=UI_FAILED`。

        自己寫一套 = 第二把尺；L0 那道「`requested=False` 卻帶著值就 raise」
        的保護會被繞過去。
        """
        _src = inspect.getsource(P.build_heatmap_card)
        assert "classify_ui_state(" in _src
        for _bad in ("state=UI_FAILED", "state=UI_DEGRADED", "state=UI_EMPTY"):
            assert _bad not in _src, f"本頁自己決定了 {_bad} —— 那是第二把尺"

    def test_the_loader_calls_nothing_before_you_press(self, poisoned):
        """沒按 → **整批冷抓不會發**（毒藥穿得過所有 try/except）。"""
        _hm = P.load_heatmap(requested=False)
        assert (_hm.requested, _hm.figure, _hm.any_data) == (False, None, False)

    def test_the_poison_really_would_have_fired_on_the_heatmap(self, poisoned):
        """反證：同一組毒藥下 `requested=True` 一定炸 —— 證明它真的在射程內。"""
        with pytest.raises(_L3Touched):
            P.load_heatmap(requested=True)

    def test_the_default_factor_is_still_the_cheap_one(self):
        """預設因子仍不是 PE —— **理由換了，結論沒換**（有意識的保留）。

        舊理由：PE 未接線，拿它當預設等於讓每個人都拿到少算一個因子的名單。
        **那個理由已經不成立**（接上了），但預設值不改，新理由是成本：
        `eps_high` 走存活池自己的 `eps` 欄、**零額外取數**，
        而 `pe_low` 每一次都要打 TWSE ＋ TPEX 兩支 OpenAPI。

        ⚠️ 本條原本掛在 `TestUnwiredStaysUnwired` 底下，與未接線無關，
        隨該類改寫一起搬過來，**內容一字未改**。
        """
        assert P.DEFAULT_FACTOR_KEY != P.PE_FACTOR_KEY
        assert P.DEFAULT_FACTOR_KEY == "eps_high"


class TestHeatmapKeysNeverCollideWithTheOldTab:
    """本頁**一個舊 widget key 都不准重用** —— 重用會**弄壞既有分頁**。

    這不是潔癖，是兩個實際會發生的故障（~~Streamlit 每次 app run 會跑
    **全部** tab body，而本頁的渲染順序在 🌍 市場環境的熱力圖**之前**~~）：

      1. **共用 `heatmap_loaded`（session 旗標）** → 使用者在舊分頁按過載入之後，
         本頁會在**從未被造訪的情況下**發出整批冷抓；反過來，本頁按了載入
         會讓舊分頁的 opt-in 效能保證當場失效
         （`tests/test_etf_render_heatmap_gate.py` 守的就是那件事）。
      2. ~~**共用 `heatmap_market` / `heatmap_period` / `heatmap_refresh` /
         `heatmap_load`（widget key）** → 先執行的那一邊佔住 ID，
         **另一邊拋 `DuplicateWidgetID`**。先執行的是本頁 → 壞的是舊分頁。~~

    ⚠️ **2026-09-08 FE-36 事實更正 —— 結論與斷言一字未改，理由變了。**
    `b5bdb36` 把五頁改成**側欄 radio ＋ `st.stop()`**：新頁與舊 7 個頁籤
    **不再進到同一個 script run** ⇒ 上面第 2 點那個「同輪撞 ID」的機制
    **對舊分頁已不成立**（畫掉的兩處就是這個原因，不是原文寫錯）。
    **第 1 點完全沒有失效，而且現在是這條紀律的承重理由**：`heatmap_loaded`
    是普通的 `st.session_state` 旗標，**跨 rerun、跨頁存活**，切一下側欄 radio
    就是同 session 的一次 rerun。另外 `st.stop()` 之前跑完的**整個側欄**
    widget 與本頁**同輪** —— 撞 ID 這件事沒消失，只是對手換人。
    掛載形態本身由 `tests/test_p0x_view_mount_claims.py` 釘住。

    ⚠️ **用 AST 不用字串搜尋**：本頁檔頭的病史說明**必須**寫出那五個 key 才
    講得清楚「為什麼不能共用」，字串搜尋會把**誠實的揭露**判成違規
    （同 `TestValuationGoesThroughL3::test_no_l1_import_and_no_reexport_detour`
    的理由）。
    """

    #: 本頁「真的會進 Streamlit 命名空間」的字串只有兩種來源：
    #:   (a) `st.<widget>(..., key=...)` 的 key；
    #:   (b) `session_state` / 本頁傳進來的 session mapping 的下標。
    #: ⚠️ **刻意不收 `Card(key=...)`**：那是卡片自己的識別碼（`find.heatmap`
    #: 這種），不會進 Streamlit 的 widget 命名空間，收進來只會製造假紅燈。
    def _keys_actually_used(self) -> set[str]:
        _used: set[str] = set()

        def _add(_node) -> None:
            if isinstance(_node, ast.Constant) and isinstance(_node.value, str):
                _used.add(_node.value)
            elif isinstance(_node, ast.Name):
                _v = getattr(P, _node.id, None)
                if isinstance(_v, str):
                    _used.add(_v)

        for _n in ast.walk(_tree_of_view()):
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
                # `st.button(...)` / `st.download_button(...)` / `col.selectbox(...)`
                for _kw in _n.keywords:
                    if _kw.arg == "key":
                        _add(_kw.value)
            elif isinstance(_n, ast.Subscript):
                _tgt = _n.value
                _is_session = (
                    (isinstance(_tgt, ast.Attribute)
                     and _tgt.attr == "session_state")
                    or (isinstance(_tgt, ast.Name)
                        and "session" in _tgt.id.lower()))
                if _is_session:
                    _add(_n.slice)
        return _used

    def test_the_five_legacy_keys_are_a_real_list_not_a_guess(self):
        """名單本身要對得上舊分頁 —— 名單抄錯的話下面兩條就是空轉。"""
        import src.ui.render.etf_render as R

        _src = inspect.getsource(R.render_sector_heatmap)
        for _k in P.LEGACY_HEATMAP_KEYS:
            assert f"'{_k}'" in _src or f'"{_k}"' in _src, (
                f"{_k!r} 已經不在 `render_sector_heatmap()` 裡了 —— "
                "請更新 `LEGACY_HEATMAP_KEYS`，別讓這張名單變成過期的擺設")

    def test_the_collector_actually_finds_this_pages_keys(self):
        """**反證**：沒有這一條，上面兩條可能只是因為收集器什麼都沒收到而綠。"""
        _used = self._keys_actually_used()
        for _k in (P.SS_MAP_BUTTON, P.SS_MAP_REQUESTED, P.SS_APPLIED_SCREEN,
                   P.SS_FACTORS_WIDGET, P.SS_TOPN_WIDGET):
            assert _k in _used, (
                f"收集器沒有看到本頁自己的 {_k!r} —— "
                "它壞了，下面兩條的綠燈不算數")

    def test_this_page_uses_none_of_them(self):
        _used = self._keys_actually_used()
        _clash = sorted(_used & set(P.LEGACY_HEATMAP_KEYS))
        assert not _clash, (
            f"本頁用了舊分頁的 key {_clash} —— "
            "session 旗標共用會讓另一邊在沒被造訪時發出整批冷抓；"
            "widget key 共用會讓先執行者佔住 ID、另一邊拋 DuplicateWidgetID。"
            "本頁的 key 一律用 `p02v_` / `_p02_` 前綴")

    def test_every_key_this_page_uses_carries_the_page_prefix(self):
        """不是只避開那五個，而是**全部**都要帶前綴。

        只避開已知的五個，等於等下一個同名衝突自己撞上來；
        帶前綴則讓衝突在結構上不可能發生。
        ⚠️ 兩個上游 session key（ETF 組合持股 / 個股 sheet_id）是**讀別人寫的**，
        不是本頁自有的 widget，故排除。
        """
        _upstream = {P.SS_ETF_PORTFOLIO_ROWS, P.SS_STOCK_SHEET_ID, P.FORM_KEY}
        _bad = sorted(_k for _k in self._keys_actually_used() - _upstream
                      if not _k.startswith(("p02v_", "_p02_")))
        assert not _bad, f"這些 key 沒有本頁前綴：{_bad}"


class TestValuationGoesThroughL3:
    """估值接線**只准走 L3** —— 這是 `test_pe_map_is_never_wired_by_accident`

    的等效替身（2026-09-07 FE-18）。

    ⚠️ **舊那條不是被放寬，是被取代。** 它釘的是「`pe_map=` 恆為 `None`」，
    而它真正要防的**不是**「接上」這件事本身 —— 它的訊息原文寫得很清楚：
    「哪天有人把它接上，本條轉紅，提醒他**同時**要把卡上那句『本頁未接線』
    拿掉，否則畫面會開始說謊」。也就是說它防的是**接上卻沒改文案**。
    那個提醒已經照做了，於是這一組接手，改釘兩件**接上之後**才有意義的事：

      1. `pe_map=` / `name_map=` **仍然顯式傳**（預設值會無聲改變行為），
         而且**不再是常數 `None`** —— 傳回常數就是偷偷退回未接線；
      2. 接線走的是**新的 L3**，不是 `src.data.*` 直呼、也不是
         `src.ui.tabs.yield_screener` 的 re-export 繞道
         （**那條繞道只是騙過 AST、不改變性質** —— 前一組明文拒絕過，
         這條禁令**沒有**因為接線而放寬）。
    """

    def test_the_two_kwargs_are_still_explicit_and_no_longer_none(self):
        _calls = [_n for _n in ast.walk(_tree())
                  if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
                  and _n.func.id == "get_ranked_picks"]
        assert _calls, "找不到 `get_ranked_picks(...)` 呼叫 —— 這條測試的前提壞了"
        for _c in _calls:
            _kw = {_k.arg: _k.value for _k in _c.keywords if _k.arg}
            for _name in ("pe_map", "name_map"):
                assert _name in _kw, f"{_name}= 沒有顯式傳 —— 預設值會無聲改變行為"
                _v = _kw[_name]
                assert not (isinstance(_v, ast.Constant) and _v.value is None), (
                    f"{_name}= 又被寫死成 None（line {_c.lineno}）—— "
                    "那是偷偷退回未接線，而畫面上的揭露已經說它接上了")

    def test_no_l1_import_and_no_reexport_detour(self):
        """AST：零 `src.data.*`、零 `src.ui.tabs.yield_screener`。

        ⚠️ 用 AST 而不是字串搜尋 —— 檔頭的「為什麼不走那條路」本來就必須
        寫出那兩個模組名才說得清楚，字串搜尋會把**誠實的揭露**判成違規。
        """
        _mods: set[str] = set()
        for _n in ast.walk(_tree()):
            if isinstance(_n, ast.ImportFrom) and _n.module:
                _mods.add(_n.module)
            elif isinstance(_n, ast.Import):
                _mods |= {_a.name for _a in _n.names}
        _bad = {_m for _m in _mods
                if _m.startswith("src.data")
                or _m.startswith("src.ui.tabs.yield_screener")}
        assert not _bad, (
            f"本頁直接 import 了 {sorted(_bad)} —— L5→L1 是分層違憲；"
            "經其他 L5 檔 re-export 繞道只是騙過靜態檢查、不改變性質")
        assert "src.services.valuation_service" in _mods, (
            "估值輸入沒有走本批新增的 L3")

    def test_the_l3_is_a_pass_through_of_the_l1_ssot(self, monkeypatch):
        """L3 真的轉發 L1 的 SSOT `fetch_pe_name_maps`，沒有自己合併一份。

        自己拆開兩支 fetcher 再合併 = 複製 L1 的合併規則（上市先填、
        代碼空間互斥、不平均）＝ 第二個 SSOT（§2.1）。
        """
        from src.data.stock import yield_pe_fetcher as Y
        from src.services import valuation_service as V

        monkeypatch.setattr(Y, "fetch_pe_name_maps",
                            lambda: ({"2330": 21.5}, {"2330": "台積電"}),
                            raising=True)
        assert V.get_pe_name_maps() == ({"2330": 21.5}, {"2330": "台積電"})

    def test_the_l3_does_not_swallow_failures(self, monkeypatch):
        """§1：L1 炸了就往上拋，**不回一份看起來很合理的空 map**。"""
        from src.data.stock import yield_pe_fetcher as Y
        from src.services import valuation_service as V

        def _boom():
            raise RuntimeError("twse down")

        monkeypatch.setattr(Y, "fetch_pe_name_maps", _boom, raising=True)
        with pytest.raises(RuntimeError, match="twse down"):
            V.get_pe_name_maps()


def _facts_nonempty(facts) -> bool:
    return bool(facts) and all(str(_k).strip() and str(_v).strip()
                               for _k, _v in facts)


# ══════════════════════════════════════════════════════════════════
# 【6】勾了估值因子 → 一定要看得見「少算了一個你勾的因子」
# ══════════════════════════════════════════════════════════════════
class TestCheckedFactorIsNeverSilentlyDropped:
    """L3 `composite_rank_candidates` 的 note **看不見**「估值整個因子全空」

    這一種（`_missing` 只收缺貨 / RS，而「因子實際覆蓋」那句有
    `if _col_scores[_f]` 的前提，全空時不印）—— 所以這句話只能本頁自己講。
    講不出來 = 使用者拿到一份「悄悄少算一個因子」的名單卻看到綠燈卡片，
    那正是 §1 禁止的掩蓋問題。

    ⚠️ **2026-09-07 FE-18：接線後這一類的射程從「一種」變成「三種」。**
    接線前 `pe_map` 恆為 `None`，所以「勾了就一定要講」是無條件的；
    接線後**多了兩種必須分開的情形**，而且其中一種是**不准講**：
      · 取數失敗 → 要講（有出口：重按）
      · 拿到空 map → 要講（沒有出口可按，但要說清楚是上游沒給）
      · 拿到 N 檔 → **不准講** ←← 這一條是新的，也是最容易寫錯的：
        照抄接線前那句無條件的 Note，畫面就會對一份**明明算了估值**的名單
        說「這份名單少算了一個你勾的因子」= 假警告（`CLAUDE.md §1.A` 第 4 點）。
    """

    def test_live_card_carries_the_note_when_the_fetch_failed(self):
        """勾了、而且取數失敗 → 一定要看得見。"""
        _card, _facts = _screen(
            df=_Frame(12), rows=12, survivors_n=274, pe_n=None, name_n=None,
            factors=("eps_high", P.PE_FACTOR_KEY),
            aux_errors=(("估值（本益比）", "取不到：RuntimeError('boom')"),))
        assert _card.state == UI_LIVE
        assert _card.note is not None, (
            "live 卡沒有帶 Note —— 「少算了一個你勾的因子」被靜默丟棄了")
        assert "少算了一個你勾的因子" in _card.note.now
        assert _facts["估值（本益比）"].startswith("取不到")

    def test_the_pe_note_still_has_all_three_elements(self):
        """鐵律 4 的**等效替身**：原 `test_pe_factor_note_has_all_three_elements`

        驗的是「未接線的那則 PE Note 三要素齊備」。接線後那則 Note 換成了
        **兩種缺料版本**，射程不能跟著消失 —— 這裡對兩種各驗一次。
        （`Note.__post_init__` 本來就會擋空欄位，但那是結構保證；
        寫出來是為了讓「PE 這則 Note 有沒有被驗過」在檔案裡看得見。）
        """
        for _pe_n, _tag in ((0, "空 map"), (None, "取不到")):
            _card, _ = _screen(df=_Frame(3), rows=3, pe_n=_pe_n, name_n=_pe_n,
                               factors=(P.PE_FACTOR_KEY,))
            _now, _why, _where = _note_triple(_card.note)
            assert _now.strip() and _why.strip() and _where.strip(), _tag
            assert P.NO_EXIT_MARKER not in _where, (
                f"{_tag}：接線後仍宣稱沒有出口 —— 重按其實有機會好")

    def test_live_card_carries_the_note_when_the_map_is_empty(self):
        """勾了、拿到了、但**是空的** → 同樣要看得見，而且要說是上游沒給。"""
        _card, _ = _screen(df=_Frame(12), rows=12, survivors_n=274,
                           pe_n=0, name_n=0,
                           factors=("eps_high", P.PE_FACTOR_KEY))
        assert _card.state == UI_LIVE and _card.note is not None
        assert "少算了一個你勾的因子" in _card.note.now
        assert "都沒有給資料" in _card.note.why, _card.note.why

    def test_a_successful_fetch_produces_no_false_alarm(self):
        """⭐ **接上之後最容易寫錯的一條**：算到了就**不准**再喊少算。

        照抄接線前那句無條件的 Note = 對一份明明算了估值的名單說謊；
        假警報與假數字是同一種說謊（滿版假警告會讓真的警告沒人看）。
        """
        _card, _facts = _screen(df=_Frame(12), rows=12, survivors_n=274,
                                pe_n=931, name_n=1042,
                                factors=("eps_high", P.PE_FACTOR_KEY))
        assert _card.state == UI_LIVE
        assert _card.note is None, (
            "估值明明算出來了，卡上還在說「這份名單少算了一個你勾的因子」")
        assert "931" in _facts["估值（本益比）"], _facts["估值（本益比）"]

    def test_the_name_column_tells_the_truth_four_ways(self):
        """名稱欄跟勾不勾估值無關 → **永遠講一次**，而且四種情形四句話。

        ⚠️ 第四種（**冷啟動**）最容易被漏掉：那時 `name_n` 也是 `None`，
        但那是因為**這一輪根本沒有發過取數**。對它說「這一輪取不到」＝
        替一輪沒發生的取數宣稱它的結果（`CLAUDE.md §1.A` 第 4 點）。
        """
        _, _f_ok = _screen(df=_Frame(3), rows=3, pe_n=931, name_n=1042)
        _, _f_empty = _screen(df=_Frame(3), rows=3, pe_n=0, name_n=0)
        _, _f_fail = _screen(df=_Frame(3), rows=3, pe_n=None, name_n=None)
        _, _f_idle = _screen(submitted=False)
        assert "1042" in _f_ok["名稱欄"]
        assert "空的" in _f_empty["名稱欄"] and "不是本頁沒接" in _f_empty["名稱欄"]
        assert "取不到" in _f_fail["名稱欄"]
        assert "送出後才會取" in _f_idle["名稱欄"], (
            f"冷啟動被說成取不到：{_f_idle['名稱欄']}")
        assert "取不到" not in _f_idle["名稱欄"]
        assert len({_f_ok["名稱欄"], _f_empty["名稱欄"], _f_fail["名稱欄"],
                    _f_idle["名稱欄"]}) == 4, "四種情形被講成同一句話"

    def test_not_checking_it_produces_no_such_note(self):
        """沒勾就不要嚇人 —— 假警報一樣是說謊（`CLAUDE.md §1.A` 第 4 點）。"""
        _card, _facts = _screen(df=_Frame(12), rows=12, pe_n=931, name_n=1042,
                                factors=("eps_high",))
        assert _card.state == UI_LIVE and _card.note is None
        assert "估值（本益比）" not in _facts

    def test_the_disclosure_is_also_permanent_under_the_form(self):
        """常駐揭露（不隨狀態消失）：勾之前就該看得到，且**內容要是真的**。"""
        assert "已全部接線" in P.WIRING_DISCLOSURE
        assert "未接線" not in P.WIRING_DISCLOSURE, (
            "估值已經接上了，常駐揭露還說它沒接 —— 那是說謊")
        assert "st.caption(WIRING_DISCLOSURE)" in \
            _VIEW.read_text(encoding="utf-8")

    def test_l3_note_is_passed_through_verbatim(self):
        """L3 自己的 note **原樣透傳**，本檔不改寫、不摘要（§2.1 那是 L3 的話）。"""
        _msg = "缺貨動能未掃描，該因子不計入；空頭濾網未套用"
        _card, _facts = _screen(df=_Frame(3), rows=3, note=_msg)
        assert _facts["L3 說明"] == _msg

    def test_aux_errors_are_visible_without_turning_the_card_red(self):
        """一個因子掛掉 ≠ 選股掛掉；但**必須看得見**。"""
        _card, _facts = _screen(df=_Frame(3), rows=3, survivors_n=100,
                                aux_errors=(("缺貨掃描", "失敗，該因子不計入"),))
        assert _card.state == UI_LIVE, "週邊失敗不得讓整張卡轉紅"
        assert _facts["缺貨掃描"] == "失敗，該因子不計入"


# ══════════════════════════════════════════════════════════════════
# 【7】Form 結構（線框 F11：form 內放 button 實跑即拋）
# ══════════════════════════════════════════════════════════════════
def _form_withs(tree: ast.Module) -> list[ast.With]:
    """本檔所有 `with st.form(...)` 的 With 節點。"""
    _out = []
    for _n in ast.walk(tree):
        if not isinstance(_n, ast.With):
            continue
        for _item in _n.items:
            _c = _item.context_expr
            if (isinstance(_c, ast.Call) and isinstance(_c.func, ast.Attribute)
                    and _c.func.attr == "form"):
                _out.append(_n)
    return _out


def _attr_calls(nodes) -> list[ast.Call]:
    return [_c for _n in nodes for _c in ast.walk(_n)
            if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Attribute)]


class TestFormStructure:
    """鐵律 2 的**結構**面。`_ui_kit.single_submit_form()` 只吃一組 radio，

    本頁需要 multiselect ＋ selectbox，故就地實作 —— 那就必須有一支守衛
    盯著它沒有偏離同一套契約（FE-8 自陳的交接事項之一）。
    """

    def test_there_is_exactly_one_form(self):
        assert len(_form_withs(_tree())) == 1, (
            "頁 2 應該只有一個 form（條件表單）")

    def test_the_form_has_exactly_one_submit_button(self):
        _calls = _attr_calls(_form_withs(_tree()))
        _submits = [_c for _c in _calls
                    if _c.func.attr == "form_submit_button"]
        assert len(_submits) == 1, (
            f"form 內應恰有 1 顆 submit，實際 {len(_submits)} 顆")

    def test_no_button_of_any_kind_inside_the_form(self):
        """線框 F11：form 內的 `st.button` / `st.download_button` 實跑即拋。"""
        _calls = _attr_calls(_form_withs(_tree()))
        _bad = [f"st.{_c.func.attr} @line {_c.lineno}" for _c in _calls
                if _c.func.attr in ("button", "download_button")]
        assert not _bad, (
            f"form 內出現按鈕 {_bad} —— 線框 F11：實跑即拋 "
            "StreamlitAPIException")

    def test_the_two_real_buttons_live_outside_every_form(self):
        """反面：那兩顆鈕**確實存在**，而且都在 form 外（不是被刪掉才綠的）。"""
        _tree_ = _tree()
        _inside = {id(_c) for _c in _attr_calls(_form_withs(_tree_))}
        _outside = [_c.func.attr for _c in _attr_calls([_tree_])
                    if _c.func.attr in ("button", "download_button")
                    and id(_c) not in _inside]
        assert sorted(_outside) == ["button", "download_button"], (
            f"預期 form 外恰有 1 顆 st.button ＋ 1 顆 st.download_button，"
            f"實際 {sorted(_outside)}")

    def test_widget_values_are_only_read_inside_the_form_handler(self):
        """**鐵律 2 的本體**：下游只准讀已套用值，不准讀 widget 當下值。"""
        _offenders = []
        for _fn in ast.walk(_tree()):
            if not isinstance(_fn, ast.FunctionDef) \
                    or _fn.name == "_render_screen_form":
                continue
            for _s in ast.walk(_fn):
                if isinstance(_s, ast.Name) and _s.id in (
                        "SS_FACTORS_WIDGET", "SS_TOPN_WIDGET"):
                    _offenders.append(f"{_fn.name}:{_s.lineno}")
        assert not _offenders, (
            f"widget 當下值被 form handler 以外的地方讀了：{_offenders}")

    def test_no_bare_columns_above_three(self):
        """鐵律 1：格子多於 3 個要換行，不是加欄（本頁一律走 `grid()`）。"""
        for _n in ast.walk(_tree()):
            if (isinstance(_n, ast.Call)
                    and isinstance(_n.func, ast.Attribute)
                    and _n.func.attr == "columns" and _n.args
                    and isinstance(_n.args[0], ast.Constant)):
                assert _n.args[0].value <= P.MAX_COLS, (
                    f"{_VIEW.name}:{_n.lineno} 用了 {_n.args[0].value} 欄")


# ══════════════════════════════════════════════════════════════════
# 【FE-9】渲染期轉紅卡：兩頁走**同一支**共用實作（搬家後的釘子）
# ══════════════════════════════════════════════════════════════════
class _FakeST:
    """`_ui_kit` 用得到的那幾支 `st.*` 的錄音替身（形狀沿用頁 1 的測試）。"""

    def __init__(self) -> None:
        self.markdown: list[str] = []
        self.caption: list[str] = []


def _record(fake: _FakeST):
    _ns = type("NS", (), {})()
    _ns.markdown = lambda _s, **_k: fake.markdown.append(str(_s))
    _ns.caption = lambda _s, **_k: fake.caption.append(str(_s))
    return _ns


class TestRenderBoundaryIsShared:
    """頁 1 與頁 2 原本**各有一份逐行同構的 `_render_one()`** ——

    兩把尺遲早漂移（一邊修了「`except ... as _e` 的 `_e` 會被 `del`」那個坑、
    另一邊沒修，就是最典型的漂移）。2026-09-07 FE-9 把本體上移
    `_ui_kit.render_card_isolated()`，兩頁各留一層綁定 shim。
    本類釘住：**(a) 邊界還在**、**(b) 兩頁真的走同一支**。
    """

    def test_a_broken_card_becomes_a_red_card_not_half_a_page(self, monkeypatch):
        from src.ui.views import _ui_kit as K

        _fake = _FakeST()
        monkeypatch.setattr(K, "st", _record(_fake))

        _calls = {"n": 0}
        _real = K.render_card

        def _boom(card, **kw):
            _calls["n"] += 1
            if _calls["n"] == 1:
                raise RuntimeError("render exploded")
            return _real(card, **kw)

        monkeypatch.setattr(K, "render_card", _boom)
        P._render_one(P.build_heatmap_card(
            P.HeatmapReadout(requested=False))[0])
        _all = "\n".join(_fake.markdown)
        assert "這一格畫不出來" in _all, "半截死頁：例外沒有被轉成看得見的紅卡"
        assert "render exploded" in _all, "原始例外必須看得見（§1）"

    def test_the_page_no_longer_owns_a_second_copy(self):
        """本頁不得再自己 import `render_card` —— 那就是第二把尺長回來了。"""
        assert not hasattr(P, "render_card"), (
            "`page_find` 又自己持有 render_card 了 —— "
            "渲染期轉紅卡的邏輯只准有一份（`_ui_kit.render_card_isolated`）")
        assert hasattr(P, "render_card_isolated")

    def test_both_pages_bind_the_same_shared_function(self):
        from src.ui.views import _ui_kit as K
        from src.ui.views import page_today as T

        assert P.render_card_isolated is K.render_card_isolated
        assert T.render_card_isolated is K.render_card_isolated, (
            "兩頁綁到了不同的東西 —— 共用層形同虛設")

    def test_each_page_keeps_its_own_source_and_exit(self):
        """搬家保留了**該保留的差異**：出處與「去哪補」仍是各頁自己的。

        （頁 1 的【8b】就是拿共用文案去包別的層，對使用者謊報出事的層。）
        """
        import inspect

        _src = inspect.getsource(P._render_one)
        assert 'owner="views/page_find"' in _src
        assert "SRC_RENDER" in _src and "NO_EXIT_MARKER" in _src


# ══════════════════════════════════════════════════════════════════
# 冒煙（slow lane）：這一頁真的畫得出來
# ══════════════════════════════════════════════════════════════════
@pytest.mark.slow
def test_page_mounts_clean(tmp_path):
    """冷啟動整頁 mount：**沒有 uncaught exception、不是半截頁面**。

    ⚠️ 這一條看得到的只有「畫得出來」；它**看不到**畫出來的東西是不是真的
    （狀態對不對、有沒有靜默降級）—— 那些由上面的單元測試守。
    """
    import textwrap

    from streamlit.testing.v1 import AppTest

    _script = tmp_path / "_p02_view.py"
    _script.write_text(textwrap.dedent("""
        from src.ui.views.page_find import render_page_find
        render_page_find()
    """), encoding="utf-8")

    _at = AppTest.from_file(str(_script), default_timeout=90)
    _at.run()
    assert not _at.exception, f"page_find mount 有 uncaught exception: {_at.exception}"

    _md = "\n".join(_m.value for _m in _at.markdown)
    _cap = "\n".join(_c.value for _c in _at.caption)
    _all = _md + "\n" + _cap

    # 表單那顆 submit（form 外的那顆載入鈕不會出現在 `_at.button` 裡以外的地方）。
    assert P.ACTION_RUN_SCREEN_LABEL in [
        _b.label for _b in _at.button], "選股 submit 沒畫出來"
    assert P.ACTION_LOAD_MAP_LABEL in [
        _b.label for _b in _at.button], "載入板塊地圖鈕沒畫出來"

    # 冷啟動 = idle，**不是** empty、**不是**紅。
    assert P.SCREEN_IDLE_NOW.strip("*") in _all, "冷啟動不是 idle 態"
    assert P.SCREEN_EMPTY_NOW.strip("*") not in _all, (
        "冷啟動被畫成「0 檔」—— 還沒選 ≠ 選了 0 檔")

    # 常駐揭露（不隨狀態消失）—— 尾端這兩句畫不出來就是半截死頁。
    # ⚠️ 2026-09-07 FE-18：原本 grep 的是「估值（本益比）在本頁未接線」，
    # 接線後那句話已改寫。**改成直接比對常數本身**，這比原本的字串片段
    # **更嚴** —— 以後改文案不必再改測試，揭露被整段刪掉時一樣會紅。
    assert P.WIRING_DISCLOSURE in _all, "接線揭露沒畫出來"
    assert "面積不等於權重" in _all, (
        "葉2 尾端的口徑揭露沒畫出來（可能是半截頁面）")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
