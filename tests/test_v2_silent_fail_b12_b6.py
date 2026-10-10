"""B6 總括列：「標記矛盾」逐卡修上游 —— 失敗不得畫成「沒結果」。

客戶已裁示解法 (1)「逐卡修失敗源頭」；兩組判定「不得登記 #11」。本檔守本批修的三張卡：

  · `find.sector_flow`（`FLOW_EMPTY_NOW`「板塊資金快取尚未產生」）
      根因：L1 `read_sector_flow_cache()` 把「`bubble_latest.json` 存在但 JSON 壞／格式不符」
      與「檔案不存在」回成同一個 `ok=False`「尚未產生」→ L5 灰卡「這不是故障」。
      修法：L1 `read_sector_flow_cache(strict=)`、L3 `get_sector_flow_view(strict=)`（預設不變），
      L5 `load_sector_flow` 傳 `strict=True` → 壞檔拋出 → 既有紅態 `FLOW_FAILED_NOW`。
  · `hold.macro_stage`（`MACRO_EMPTY_NOW`「總經本輪未評估／這是一個有效的結果」）
  · `hold.position_cap`（`CAP_EMPTY_NOW`「總經未評估，本站不給建議水位」）
      根因：`macro_state.json` 存在但讀壞（`load_macro_state` 吞例外回 `_DEFAULT_STATE`）、
      或檔內是 `execute_and_lock` 失敗時寫下的 Fail-safe「系統異常」→ `get_macro_state`
      回 `is_loaded=False` → 兩張卡都畫成「未評估」。
      修法：L3 `get_macro_state(strict=)` / `get_macro_regime(strict=)` /
      `get_station_macro(strict=)` / `get_allocation(strict=)`（預設不變），
      L5 `load_macro` / `load_allocation` 傳 `strict=True` → 既有紅態
      `MACRO_FAILED_NOW` / `CAP_FAILED_NOW`。檔案**不存在**仍是未評估（灰）。

每卡：(a) 全失敗 → 紅；(b) 部分失敗；(c) 真的沒有 → 與修前 byte-identical；
(d) 既有呼叫端（不傳 strict）不變；(e) 突變：拿掉本批任一條 → (a) 必須失敗。
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types

import pytest

import src.data.sector_flow.reader as RD
import src.services.allocation_service as AL
import src.services.dividend_station_service as DS
import src.services.macro_state_locker as MSL
import src.services.sector_flow_service as SFS
from shared.ui_state import UI_DEGRADED, UI_EMPTY, UI_FAILED, UI_LIVE
from src.ui.views import page_find as PF
from src.ui.views import page_hold as PH

_SUBMITTED = PH.HoldRequest(submitted=True)


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    """把 `mod` 原始碼裡每一組 `old` **恰好一處**換成 `new`，載成獨立新模組。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_b12_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


# ══════════════════════════════════════════════════════════════════
# find.sector_flow
# ══════════════════════════════════════════════════════════════════
_GOOD_BUBBLE = {"sectors": [{"sector": "半導體", "quadrant": "漲潮", "x": 1.0, "y": 2.0}],
                "updated_at": "2026-09-26T09:00:00Z", "n_trading_days_used": 20}


@pytest.fixture
def flow_dir(tmp_path, monkeypatch):
    """把 reader 的三個路徑導到 tmp（真的 L1 讀檔，不是替身）。"""
    monkeypatch.setattr(RD, "BUBBLE_PATH", tmp_path / "bubble_latest.json")
    monkeypatch.setattr(RD, "META_PATH", tmp_path / "metadata.json")
    monkeypatch.setattr(RD, "TICKER_SECTOR_PATH", tmp_path / "ticker_sector.json")
    return tmp_path


def _flow_card(session=None, *, mod=PF):
    return mod.build_sector_flow_card(mod.load_sector_flow(session or {}, requested=True))[0]


class TestSectorFlow:
    def test_a_corrupt_json_is_red(self, flow_dir):
        (flow_dir / "bubble_latest.json").write_text("{not json", encoding="utf-8")
        _c = _flow_card()
        assert _c.state == UI_FAILED and _c.note.now == PF.FLOW_FAILED_NOW

    def test_a_schema_mismatch_is_red(self, flow_dir):
        (flow_dir / "bubble_latest.json").write_text(json.dumps({"sectors": "x"}),
                                                     encoding="utf-8")
        _c = _flow_card()
        assert _c.state == UI_FAILED and _c.note.now == PF.FLOW_FAILED_NOW

    def test_b_partial_metadata_broken_still_degraded(self, flow_dir):
        """部分失敗：泡泡檔好、metadata 壞 → 既有 degraded（有圖、標過期），不變紅。"""
        (flow_dir / "bubble_latest.json").write_text(json.dumps(_GOOD_BUBBLE), encoding="utf-8")
        (flow_dir / "metadata.json").write_text("{bad", encoding="utf-8")
        _c = _flow_card()
        assert _c.state == UI_DEGRADED

    def test_c_missing_file_is_byte_identical_gray(self, flow_dir):
        _c = _flow_card()
        _base = PF.build_sector_flow_card(PF.SectorFlowReadout(
            requested=True, ok=False, reason=RD.read_sector_flow_cache()["reason"]))[0]
        assert _c == _base
        _pre = _mutant(PF, ("            strict=True,\n", ""))
        assert repr(_c) == repr(_flow_card(mod=_pre))
        assert _c.state == UI_EMPTY and _c.note.now == PF.FLOW_EMPTY_NOW

    def test_c_valid_file_unchanged_between_strict_and_default(self, flow_dir):
        (flow_dir / "bubble_latest.json").write_text(json.dumps(_GOOD_BUBBLE), encoding="utf-8")
        _a = RD.read_sector_flow_cache()
        _b = RD.read_sector_flow_cache(strict=True)
        assert _a == _b and _a["ok"]
        assert _flow_card().state in (UI_LIVE, UI_DEGRADED)

    def test_d_default_callers_unchanged(self, flow_dir):
        (flow_dir / "bubble_latest.json").write_text("{not json", encoding="utf-8")
        assert RD.read_sector_flow_cache()["ok"] is False
        _v = SFS.get_sector_flow_view(include_stock_watchlists=False)
        assert _v["ok"] is False and "尚未產生" in _v["reason"]
        with pytest.raises(Exception):
            SFS.get_sector_flow_view(include_stock_watchlists=False, strict=True)

    def test_e_mutant_l5_without_strict_goes_gray(self, flow_dir):
        (flow_dir / "bubble_latest.json").write_text("{not json", encoding="utf-8")
        _m = _mutant(PF, ("            strict=True,\n", ""))
        assert _flow_card(mod=_m).state == UI_EMPTY

    def test_e_mutant_reader_without_strict_branch(self, flow_dir, monkeypatch):
        (flow_dir / "bubble_latest.json").write_text("{not json", encoding="utf-8")
        _m = _mutant(RD, ("    if strict and BUBBLE_PATH.exists():",
                          "    if False:"))
        _m.BUBBLE_PATH = RD.BUBBLE_PATH
        assert _m.read_sector_flow_cache(strict=True)["ok"] is False


# ══════════════════════════════════════════════════════════════════
# hold.macro_stage ／ hold.position_cap
# ══════════════════════════════════════════════════════════════════
_FAILSAFE = {"market_regime": "系統異常", "exposure_limit_pct": 0}
# D3（DL-f1-s65）：裁決有有效期限 → 測資帶當下 timestamp（模組載入時取，測試期間遠小於期限）
_GOOD_STATE = {"market_regime": "多頭", "exposure_limit_pct": 80,
               "timestamp": MSL._now_str()}


@pytest.fixture
def macro_dir(tmp_path, monkeypatch):
    """CWD 導到 tmp（`macro_state.json` 是相對路徑）；session 換成空 dict（無 warroom）。"""
    monkeypatch.chdir(tmp_path)
    _ss: dict = {}
    monkeypatch.setattr(AL, "st", types.SimpleNamespace(session_state=_ss))
    return tmp_path


def _write(path: pathlib.Path, obj) -> None:
    path.write_text(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False),
                    encoding="utf-8")


def _macro_card(mod=PH):
    return mod.build_macro_stage_card(mod.load_macro(_SUBMITTED))[0]


def _cap_card(mod=PH):
    return mod.build_position_cap_card(mod.load_allocation(_SUBMITTED))[0]


class TestMacroStageAndCap:
    @pytest.mark.parametrize("content", ["{bad json", _FAILSAFE, {"foo": 1}])
    def test_a_unusable_file_is_red(self, macro_dir, content):
        _write(macro_dir / "macro_state.json", content)
        _m = _macro_card()
        assert _m.state == UI_FAILED and _m.note.now == PH.MACRO_FAILED_NOW
        _c = _cap_card()
        assert _c.state == UI_FAILED and _c.note.now == PH.CAP_FAILED_NOW

    def test_b_partial_warroom_ok_file_broken_not_raised(self, macro_dir):
        """部分失敗：warroom 可用 → 位階仍評估得出（檔壞只少 exposure 那半），不拋。

        B6-r4 起 strict 多帶一個 `file_error` 鍵（其餘欄位與預設逐一相同；見 test_v2_hold_p1c）。
        """
        _write(macro_dir / "macro_state.json", "{bad json")
        _wr = {"health_score": 70.0, "effective_regime": "bull"}
        _s = MSL.get_macro_state(_wr, strict=True)
        assert _s.pop("file_error")
        assert _s == MSL.get_macro_state(_wr)

    def test_c_missing_file_is_byte_identical_gray(self, macro_dir):
        assert (MSL.get_macro_state({}, strict=True) == MSL.get_macro_state({}))
        assert DS.get_station_macro(strict=True) == DS.get_station_macro()
        _m = _macro_card()
        assert _m.state == UI_EMPTY and _m.note.now == PH.MACRO_EMPTY_NOW
        _c = _cap_card()
        assert _c.state == UI_EMPTY and _c.note.now == PH.CAP_EMPTY_NOW
        # 與「修前的 L5」（拿掉 strict=True 的突變體）逐欄相同
        _pre = _mutant(PH, ("_m = get_station_macro(strict=True)", "_m = get_station_macro()"),
                       ("_a = get_allocation(strict=True)", "_a = get_allocation()"))
        assert repr(_m) == repr(_macro_card(_pre))
        assert repr(_c) == repr(_cap_card(_pre))

    def test_c_valid_file_same_between_strict_and_default(self, macro_dir):
        _write(macro_dir / "macro_state.json", _GOOD_STATE)
        assert MSL.get_macro_state({}, strict=True) == MSL.get_macro_state({})
        assert DS.get_station_macro(strict=True) == DS.get_station_macro()
        assert _macro_card().state == UI_LIVE

    def test_d_default_callers_unchanged(self, macro_dir):
        _write(macro_dir / "macro_state.json", _FAILSAFE)
        assert MSL.get_macro_state({})["is_loaded"] is False
        assert AL.get_macro_regime()["is_loaded"] is False
        assert DS.get_station_macro()["loaded"] is False
        assert AL.get_allocation().is_loaded is False
        for _f in (lambda: MSL.get_macro_state({}, strict=True),
                   lambda: AL.get_macro_regime(strict=True),
                   lambda: DS.get_station_macro(strict=True),
                   lambda: AL.get_allocation(strict=True)):
            with pytest.raises(RuntimeError):
                _f()

    def test_e_mutant_locker_without_raise(self, macro_dir, monkeypatch):
        _write(macro_dir / "macro_state.json", _FAILSAFE)
        # D3（DL-f1-s65）起該行多一個「過期裁決不算讀壞」子句，錨點同步（突變語意不變）。
        # 批 Z36（Q-z19）起再多一個「8 項全缺落檔不算讀壞」子句（換行續寫），錨點同步（突變語意不變）。
        _m = _mutant(MSL, ("    if (strict and not _is_loaded and os.path.exists(state_file_path)"
                           " and not _file_expired\n            and not _file_no_data):",
                           "    if False:"))
        monkeypatch.setattr(MSL, "get_macro_state", _m.get_macro_state)
        assert _macro_card().state == UI_EMPTY
        assert _cap_card().state == UI_EMPTY

    def test_e_mutant_l5_without_strict(self, macro_dir):
        _write(macro_dir / "macro_state.json", _FAILSAFE)
        _m = _mutant(PH, ("_m = get_station_macro(strict=True)", "_m = get_station_macro()"),
                     ("_a = get_allocation(strict=True)", "_a = get_allocation()"))
        assert _macro_card(_m).state == UI_EMPTY
        assert _cap_card(_m).state == UI_EMPTY

    def test_e_mutant_station_fallback_swallows(self, macro_dir, monkeypatch):
        """退化路徑（無 session）：拿掉 `if strict: raise` → 又被吞成未評估。"""
        _write(macro_dir / "macro_state.json", _FAILSAFE)
        monkeypatch.setattr(AL, "st", types.SimpleNamespace())   # get_macro_regime 會炸
        assert _macro_card().state == UI_FAILED
        _m = _mutant(DS, ("""            if strict:
                raise
            print(f"[dividend_station] 位階讀取失敗""",
                          """            print(f"[dividend_station] 位階讀取失敗"""))
        monkeypatch.setattr(DS, "get_station_macro", _m.get_station_macro)
        assert _macro_card().state == UI_EMPTY

    def test_e_mutant_allocation_swallows(self, macro_dir, monkeypatch):
        _write(macro_dir / "macro_state.json", _FAILSAFE)
        _m = _mutant(AL, ("""        if strict:
            raise
        print(f'[allocation] get_macro_state failed""",
                          """        print(f'[allocation] get_macro_state failed"""))
        _m.st = AL.st
        monkeypatch.setattr(AL, "get_allocation", _m.get_allocation)
        assert _cap_card().state == UI_EMPTY
