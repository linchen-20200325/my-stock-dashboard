"""資料層修錯（2026-09-27，CLAUDE.md §1.A-3「只快取成功、失敗退避」）三條：

  · **Q2-r2** `macro_core._fetch_yf_close_base`：Yahoo 回 200 但收盤全 null（dropna 後空）
    修前被放進 1hr 成功快取 → 現不入快取、記退避（`FAIL_COOLDOWN_SEC` 內不重打）、之後重抓；
    成功路徑不變。
  · **DL-f4** `StockDataLoader._get_combined_data_cached`：整體失敗 `_CombinedDataError`
    修前每次 rerun 都重打 → 現記入既有 `_combined_inst_fail_cooldown`，冷卻期內再拋同一則錯誤；
    仍不入快取。
  · **B6-r5** `get_macro_state(strict=True)`：檔存在但讀檔／JSON 失敗時，錯誤修前寫
    `market_regime='系統異常'`（降級後的預設值）→ 現帶檔名＋原始例外 repr。strict=False 不變。
每條含突變測試：拿掉修復 → 對應斷言轉紅。
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types

import pytest

import src.data.core.data_loader as DL
import src.data.macro.macro_core as MC
import src.services.macro_state_locker as MSL


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_d2_{mod.__name__.rsplit('.', 1)[-1]}"
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
# Q2-r2
# ══════════════════════════════════════════════════════════════════
class _Resp:
    def __init__(self, close):
        self._close = close

    def json(self):
        return {"chart": {"result": [{"timestamp": [1700000000 + 86400 * i
                                                    for i in range(len(self._close))],
                                      "indicators": {"quote": [{"close": self._close}]}}]}}


@pytest.fixture
def yf_plan(monkeypatch):
    plan = {"close": [None, None, None]}
    calls = {"n": 0}

    def _fetch(*_a, **_k):
        calls["n"] += 1
        return _Resp(plan["close"])
    return plan, calls, _fetch


def _use(mod, monkeypatch, fetch):
    monkeypatch.setattr(mod, "fetch_url", fetch)
    monkeypatch.setattr(mod, "_YF_CLOSE_CACHE", {})
    if hasattr(mod, "_YF_CLOSE_EMPTY_FAIL_CACHE"):
        monkeypatch.setattr(mod, "_YF_CLOSE_EMPTY_FAIL_CACHE", {})


class TestQ2r2YfAllNull:
    def test_all_null_not_cached_backs_off_then_recovers(self, yf_plan, monkeypatch):
        plan, calls, fetch = yf_plan
        _use(MC, monkeypatch, fetch)
        s = MC.fetch_yf_close("^VIX")
        assert s.empty and s.name == "^VIX", "回傳形狀同修前（空、帶名）"
        assert ("^VIX", "1d") not in MC._YF_CLOSE_CACHE, "全 null 不得進 1hr 成功快取"
        MC.fetch_yf_close("^VIX")
        assert calls["n"] == 1, "冷卻期內不重打上游"
        monkeypatch.setattr(MC, "_FAIL_COOLDOWN_SEC", 0)
        plan["close"] = [10.0, 11.0, 12.5]
        s2 = MC.fetch_yf_close("^VIX")
        assert calls["n"] == 2 and list(s2) == [10.0, 11.0, 12.5], "冷卻期過 → 重抓並拿到成功"
        assert ("^VIX", "1d") not in MC._YF_CLOSE_EMPTY_FAIL_CACHE, "成功即解除退避"

    def test_success_path_unchanged(self, yf_plan, monkeypatch):
        plan, calls, fetch = yf_plan
        plan["close"] = [1.0, None, 3.0]
        _use(MC, monkeypatch, fetch)
        s = MC.fetch_yf_close("^GSPC")
        assert list(s) == [1.0, 3.0] and s.attrs["source"] == "Yahoo:^GSPC"
        MC.fetch_yf_close("^GSPC")
        assert calls["n"] == 1, "成功照舊快取"

    def test_mutation_revert_caches_empty(self, yf_plan, monkeypatch):
        """突變：拿掉 `if s.empty:` 守衛（＝修前）→ 空序列進成功快取、恢復後仍空。"""
        plan, calls, fetch = yf_plan
        m = _mutant(MC, ("        if s.empty:\n            # Q2-r2", "        if False:\n            # Q2-r2"))
        _use(m, monkeypatch, fetch)
        m.fetch_yf_close("^VIX")
        plan["close"] = [10.0]
        monkeypatch.setattr(m, "_FAIL_COOLDOWN_SEC", 0)
        assert m.fetch_yf_close("^VIX").empty and calls["n"] == 1, "修前：失敗被凍成 1hr 空答案"


# ══════════════════════════════════════════════════════════════════
# DL-f4
# ══════════════════════════════════════════════════════════════════
@pytest.fixture
def loader(monkeypatch):
    monkeypatch.setattr(DL.StockDataLoader, "__init__", lambda self, *a, **k: None)
    DL._combined_inst_fail_cooldown.clear()
    yield DL.StockDataLoader()
    DL._combined_inst_fail_cooldown.clear()


class TestDLf4CombinedErrorBackoff:
    def _boom(self, monkeypatch, cls, calls, mode):
        def _body(_self, sid, days, use_adjusted=True):
            calls["n"] += 1
            if mode["ok"]:
                return "DF", None, "名"
            raise DL._CombinedDataError("系統錯誤: ReadTimeout")
        monkeypatch.setattr(cls, "_get_combined_data_body", _body)

    def test_error_backs_off_reraises_same_then_recovers(self, loader, monkeypatch):
        calls, mode = {"n": 0}, {"ok": False}
        self._boom(monkeypatch, DL.StockDataLoader, calls, mode)
        assert loader.get_combined_data("2330", 60) == (None, "系統錯誤: ReadTimeout", None)
        with pytest.raises(DL._CombinedDataError, match="ReadTimeout"):
            loader.get_combined_data("2330", 60, strict=True)
        assert calls["n"] == 1, "冷卻期內不重打、仍拋同型別同訊息"
        mode["ok"] = True
        monkeypatch.setattr(DL._combined_inst_fail_cooldown, "seconds", 0)
        assert loader.get_combined_data("2330", 60) == ("DF", None, "名")
        assert calls["n"] == 2 and ("2330", 60, True) not in DL._combined_inst_fail_cooldown

    def test_first_call_strict_raises_then_cooldown_reraises(self, loader, monkeypatch):
        """首次 strict 呼叫必須拋（不得在快取入口被吞成 tuple），冷卻期內再拋同一則。"""
        DL._combined_inst_fail_cooldown.clear()
        calls, mode = {"n": 0}, {"ok": False}
        self._boom(monkeypatch, DL.StockDataLoader, calls, mode)
        with pytest.raises(DL._CombinedDataError, match="ReadTimeout"):
            loader.get_combined_data("2330", 60, strict=True)
        with pytest.raises(DL._CombinedDataError, match="ReadTimeout"):
            loader.get_combined_data("2330", 60, strict=True)
        assert calls["n"] == 1

    def test_mutation_swallow_to_tuple(self, loader, monkeypatch):
        """突變：入口把錯誤吞成 (None, err, None) → 上一個測試必紅（首次 strict 不拋）。"""
        m = _mutant(DL, ("            _combined_inst_fail_cooldown.fail(_key, _gen, _cde)\n            raise\n",
                         "            return None, str(_cde), None\n"))
        m._combined_inst_fail_cooldown.clear()
        monkeypatch.setattr(m.StockDataLoader, "__init__", lambda self, *a, **k: None)

        def _body(_self, sid, days, use_adjusted=True):
            raise m._CombinedDataError("系統錯誤: ReadTimeout")
        monkeypatch.setattr(m.StockDataLoader, "_get_combined_data_body", _body)
        assert m.StockDataLoader().get_combined_data("2330", 60, strict=True) == \
            (None, "系統錯誤: ReadTimeout", None), "突變體：strict 首次呼叫不拋（＝被守衛抓到的失效）"

    def test_other_key_not_blocked(self, loader, monkeypatch):
        calls, mode = {"n": 0}, {"ok": False}
        self._boom(monkeypatch, DL.StockDataLoader, calls, mode)
        loader.get_combined_data("2330", 60)
        loader.get_combined_data("2317", 60)
        assert calls["n"] == 2

    def test_mutation_no_backoff(self, loader, monkeypatch):
        m = _mutant(DL, ("            _combined_inst_fail_cooldown.fail(_key, _gen, _cde)\n",
                         "            pass\n"))
        m._combined_inst_fail_cooldown.clear()
        monkeypatch.setattr(m.StockDataLoader, "__init__", lambda self, *a, **k: None)
        calls = {"n": 0}

        def _body(_self, sid, days, use_adjusted=True):
            calls["n"] += 1
            raise m._CombinedDataError("系統錯誤: x")
        monkeypatch.setattr(m.StockDataLoader, "_get_combined_data_body", _body)
        ld = m.StockDataLoader()
        ld.get_combined_data("2330", 60)
        ld.get_combined_data("2330", 60)
        assert calls["n"] == 2, "修前：每次 rerun 都重打（轟炸）"


# ══════════════════════════════════════════════════════════════════
# B6-r5
# ══════════════════════════════════════════════════════════════════
_WR = {"health_score": 70.0, "effective_regime": "bull"}


@pytest.fixture
def msdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestB6r5StrictOriginalException:
    def test_bad_json_raise_carries_exception_repr(self, msdir):
        (msdir / "macro_state.json").write_text("{bad json", encoding="utf-8")
        with pytest.raises(RuntimeError) as ei:
            MSL.get_macro_state(None, strict=True)
        msg = str(ei.value)
        assert msg.startswith("macro_state.json: JSONDecodeError(")
        assert "系統異常" not in msg

    def test_bad_json_file_error_carries_exception_repr(self, msdir):
        (msdir / "macro_state.json").write_text("{bad json", encoding="utf-8")
        s = MSL.get_macro_state(_WR, strict=True)
        assert s["file_error"].startswith("macro_state.json: JSONDecodeError(")

    def test_bad_int_exposure_repr(self, msdir):
        (msdir / "macro_state.json").write_text(
            json.dumps({"market_regime": "多頭", "exposure_limit_pct": "N/A"}), encoding="utf-8")
        with pytest.raises(RuntimeError, match=r"^macro_state\.json: ValueError\("):
            MSL.get_macro_state(None, strict=True)

    def test_readable_failsafe_unchanged(self, msdir):
        (msdir / "macro_state.json").write_text(
            json.dumps({"market_regime": "系統異常", "exposure_limit_pct": 0},
                       ensure_ascii=False), encoding="utf-8")
        with pytest.raises(RuntimeError, match=r"^macro_state\.json: market_regime='系統異常'$"):
            MSL.get_macro_state(None, strict=True)

    def test_non_strict_unchanged(self, msdir):
        (msdir / "macro_state.json").write_text("{bad json", encoding="utf-8")
        assert MSL.load_macro_state("macro_state.json") == MSL._DEFAULT_STATE
        s = MSL.get_macro_state(None)
        assert "file_error" not in s and s["is_loaded"] is False

    def test_mutation_revert(self, msdir):
        (msdir / "macro_state.json").write_text("{bad json", encoding="utf-8")
        m = _mutant(MSL, ("        + (repr(_read_exc) if _read_exc is not None\n",
                          "        + (repr(_read_exc) if False\n"))
        with pytest.raises(RuntimeError, match="系統異常"):
            m.get_macro_state(None, strict=True)
