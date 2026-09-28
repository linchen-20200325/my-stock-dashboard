"""tests/test_dl_f1_s24_m2_missing.py — DL-f1-s24：§七 M1B／M2 缺值時不再捏 0（批 M2N）。

病史（本檔存在的理由）
────────────────────────────────────────────────────────────────
v1 `src/ui/tabs/macro/section_long.py::render_section_long` 的 §七「策略3 × 策略1 結論」卡
與同頁「M1B-M2 差距」KPI 卡，原用 `.get('m1b_yoy', 0)`／`.get('m2_yoy', 0)` 取年增率：

  (a) 代理源但缺數字 `{'source': 'TWII-proxy'}`
      → §七「M1B-M2=+0.00%（大盤動能代理估算） 接近0 → 資金動能趨緩，減碼等待訊號確認」
      → KPI「+0.00%（…）｜M1B:0.0%  M2:0.0%  🔴 資金撤離股市」＋ D2 代理警語；
  (b) 缺 m2 → 差額其實就是 M1B 年增率本身
      → §七「M1B-M2=+4.20% 正值 → 資金行情啟動，大膽做多！」、KPI「M2:0.0%  ✅ 資金流入股市」；
  (c) 值明確為 None → §七 `None - float` 拋 TypeError；`tab_macro.py` 直接呼叫、沒有 try。
  （另：NaN／±inf 一路算進分支，印成「+nan% 負值」「+inf% 正值 → 大膽做多！」。）

違反 CLAUDE.md §1（不得填 0、不得捏值）。production 目前走不到（唯一寫入者
`macro_trio_orchestrator` 的 4 條路徑都給 float）—— 本批屬防禦。

修法（⛔ 不改計分／門檻／燈號／顏色；屬修正錯誤，⛔ 不是版面異動）
────────────────────────────────────────────────────────────────
  · 判定用「有限數值」：缺鍵／None／NaN／±inf／非數值（含 bool）都算缺；
  · 任一缺 → §七 不列 M1B-M2 那條（純刪，與 `m1b_m2_info` 為空時同一個樣子）；
             KPI 走既有灰態「待取得」（副標沿用本卡既有「更新總經數據後自動計算」）；
             代理警語／代理註記只在有數字時出現；
  · 兩個都有值 → 同一組物件、同一段算式 → 輸出逐字不變。

本檔釘的東西
────────────────────────────────────────────────────────────────
  A. 修前真的會捏值／拋錯 —— 「修前」＝**還原體**：對現行原始碼套反向替換，把本批改動
     還原成 `.get(..., 0)`（`_revert_source`）。本實作組另做過一次性驗證（不在本檔重跑）：
     還原體的 `render_section_long` 與修前 commit b7456d1 的 AST 完全相同，且 496 組
     （測資 × 有無乖離）完整輸出與例外（型別＋訊息）逐字相同。
  B. 修後：缺值情境不捏、不拋；完整輸出 ＝「空」的完整輸出，唯一差別是 KPI 值「抓取中」→「待取得」。
  C. 非缺值：完整輸出與還原體逐字相同（代理 ×4 路徑／非代理 ×5 × 13 種 gap × 有無乖離），
     另有一組修前實跑擷取的關鍵字串 golden（防「兩邊一起錯」）。
  D. K1：本檔相對修前只多一個字面「待取得」，且它是 repo 既有的 kpi 灰態值（section_mid VIX 卡）；
     灰卡其餘參數與本卡既有「抓取中」灰卡逐一相同。
  E. 突變：每一個都讓 B（或 C 的 golden）轉紅。
  F. slow lane：真 Streamlit（AppTest）render。

⚠️ harness：`_FakeST` 直接換掉被測模組（本尊或突變體）的 module-level `st`，`finally` 還原；
   五桶 bar 換成 no-op；`_load_heavy=False` → 不觸網。本檔不吃日期、不寫檔。
"""
from __future__ import annotations

import ast
import decimal
import importlib.util
import json
import pathlib

import numpy as np
import pytest

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED
from shared.macro_provenance import (
    M1B_PROXY_SOURCE_LABEL,
    M1B_PROXY_SOURCE_LABEL_RAW,
    M1B_PROXY_VALUE_NOTE as NOTE,
)
from src.ui.render.ui_widgets import STRATEGY_TECHNICAL, kpi, strategy_conclusion

_REPO = pathlib.Path(__file__).resolve().parents[1]
_LONG_PATH = _REPO / "src/ui/tabs/macro/section_long.py"
_MID_PATH = _REPO / "src/ui/tabs/macro/section_mid.py"

#: 同頁 KPI 卡在代理時的獨立警語（v19.183 D2 既有）—— 用它的具名開頭定位。
_PROXY_CAPTION_HEAD = "⚠️ 央行 M1B/M2 三層來源全部失敗"
#: 缺值灰卡（本批）與未載入灰卡（既有）的 kpi 參數：只差第二個（值）。
_PENDING_KPI = ("M1B-M2 差距", "待取得", "更新總經數據後自動計算", "#484f58", "#0d1117")
_FETCHING_KPI = ("M1B-M2 差距", "抓取中", "更新總經數據後自動計算", "#484f58", "#0d1117")


# ══════════════════════════════════════════════════════════════════════════
# 假的 streamlit（只記錄文字；未知 API 一律 no-op）
# ══════════════════════════════════════════════════════════════════════════
class _Any:
    """未實作的 st.* 回傳值：可呼叫 / 可 with / falsy；屬性轉回同一個記錄器。"""

    def __init__(self, st):
        self._st = st

    def __call__(self, *a, **k):
        return _Any(self._st)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(self._st, name)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __bool__(self):
        return False


class _FakeST:
    _TEXT = ("markdown", "caption", "info", "warning", "success", "error", "write")

    def __init__(self, session_state):
        self.session_state = dict(session_state)
        self.secrets: dict = {}
        self.out: list[tuple[str, str]] = []

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name in _FakeST._TEXT:
            def _rec(body="", *a, **k):
                self.out.append((name, str(body)))
                return _Any(self)
            return _rec
        return _Any(self)

    def columns(self, spec, *a, **k):
        return [_Any(self) for _ in range(spec if isinstance(spec, int) else len(spec))]


def _long_module():
    import src.ui.tabs.macro.section_long as M
    return M


def _render(mod, info, bias=None):
    """跑 `mod.render_section_long`（本尊或突變體）→ (記錄, 例外或 None)。"""
    ss = {"m1b_m2_info": info}
    if bias is not None:
        ss["bias_info"] = bias
    fake = _FakeST(ss)
    saved = (mod.st, mod.render_macro_bucket_summary_bar)
    mod.st, mod.render_macro_bucket_summary_bar = fake, (lambda *a, **k: None)
    try:
        mod.render_section_long(False, {}, {}, {}, {}, {}, {})
        exc = None
    except Exception as e:  # noqa: BLE001 —— 修前 (c) 就是要抓到這個
        exc = e
    finally:
        mod.st, mod.render_macro_bucket_summary_bar = saved
    return fake.out, exc


def _s7_m1b_cards(out) -> list[str]:
    return [t for _, t in out if "🎯 策略3" in t and "M1B-M2=" in t]


def _kpi_cards(out) -> list[str]:
    return [t for _, t in out if ">M1B-M2 差距</div>" in t]


# ══════════════════════════════════════════════════════════════════════════
# 還原體（修前）與突變體
# ══════════════════════════════════════════════════════════════════════════
def _apply(code: str, pairs) -> str:
    """每一組 `old` **恰好一處**換成 `new`。"""
    for old, new in pairs:
        assert code.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        code = code.replace(old, new)
    return code


def _load(code: str, tag: str):
    """把一份 section_long 原始碼載成獨立模組（不進 `sys.modules`，不碰本尊）。"""
    M = _long_module()
    spec = importlib.util.spec_from_loader(f"_dl_f1_s24_{tag}", loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = M.__file__
    exec(compile(code, M.__file__, "exec"), m.__dict__)
    return m


#: 反向替換：把本批改動還原成 `.get(..., 0)`（＝修前 b7456d1 的 render_section_long）。
_REVERT_PAIRS = (
    ("    _m1b_v = _finite_yoy(_m1b_info, 'm1b_yoy')\n"
     "    _m2_v = _finite_yoy(_m1b_info, 'm2_yoy')\n"
     "    _m1b_ok = _m1b_v is not None and _m2_v is not None\n", ""),
    ("    if _m1b_ok:\n        _diff2 = _m1b_v - _m2_v\n",
     "    if _m1b_info:\n        _diff2 = _m1b_info.get('m1b_yoy', 0) - _m1b_info.get('m2_yoy', 0)\n"),
    ("        if _m1b_ok:\n            _diff   = round(_m1b_v - _m2_v, 2)\n",
     "        if _m1b_info:\n"
     "            _m1b_v  = _m1b_info.get('m1b_yoy', 0)\n"
     "            _m2_v   = _m1b_info.get('m2_yoy', 0)\n"
     "            _diff   = round(_m1b_v - _m2_v, 2)\n"),
    ("f'M1B:{_m1b_v:.1f}%  M2:{_m2_v:.1f}%  {_ml}'",
     "f'M1B:{_m1b_info.get(\"m1b_yoy\",0):.1f}%  M2:{_m1b_info.get(\"m2_yoy\",0):.1f}%  {_ml}'"),
)
#: 本批新增的缺值灰態那一枝：從 `elif _m1b_info:` 到「待取得」那張 kpi 為止（中間註解不計）。
_PENDING_BRANCH = ("        elif _m1b_info:\n",
                   "'待取得', '更新總經數據後自動計算', '#484f58', '#0d1117'), unsafe_allow_html=True)\n")


def _revert_source() -> str:
    code = _apply(_LONG_PATH.read_text(encoding="utf-8"), _REVERT_PAIRS)
    start, end = _PENDING_BRANCH
    assert code.count(start) == 1 and code.count(end) == 1, "缺值灰態那一枝定位失準"
    i = code.index(start)
    return code[:i] + code[code.index(end, i) + len(end):]


@pytest.fixture(scope="module")
def pre_fix():
    return _load(_revert_source(), "pre_fix")


# ══════════════════════════════════════════════════════════════════════════
# 測資
# ══════════════════════════════════════════════════════════════════════════
#: 非缺值的來源形狀：非代理 ×5、代理 ×4（L0 `is_m1b_m2_proxy` 的兩個 label ＋ 兩個布林旗標）
_SOURCES = {
    "CBC-tier1": {"source": "CBC-tier1"},
    "CBC-tier2": {"source": "CBC-tier2"},
    "FRED": {"source": "FRED"},
    "IMF": {"source": "IMF(2025)"},
    "no_source": {},
    "proxy_label": {"source": M1B_PROXY_SOURCE_LABEL},
    "proxy_label_raw": {"source": M1B_PROXY_SOURCE_LABEL_RAW},
    "proxy_flag_is_proxy_tier": {"source": "CBC-tier1", "is_proxy_tier": True},
    "proxy_flag_is_proxy": {"source": "CBC-tier1", "is_proxy": True},
}
#: (m1b_yoy, m2_yoy)
_GAPS = {
    "strong": (5.1, 2.0),              # +3.10 → 正值
    "mild": (3.0, 2.5),                # +0.50 → 正值
    "tiny_pos": (2.001, 2.0),          # 顯示 +0.00 但 >0 → §七 正值／KPI 撤離（既有行為，照舊）
    "zero": (2.0, 2.0),                # 0.00 → 接近0
    "near_zero": (1.0, 2.0),           # -1.00 → 接近0
    "minus2": (1.0, 3.0),              # -2.00 邊界 → 負值
    "negative": (1.2, 5.0),            # -3.80 → 負值
    "both_negative": (-1.5, -3.0),     # 兩者皆負、差額 +1.50
    "m2_is_zero": (1.5, 0.0),          # 真的 0.0% 不是缺值
    "m1b_is_zero": (0.0, 0.8),         # 真的 0.0% 不是缺值
    "ints": (5, 2),                    # int 型別
    "np_float64": (np.float64(4.25), np.float64(1.5)),
    "large": (123.456, -78.9),
}
_BIAS = {"no_bias": None, "with_bias": {"bias_240": 5.0, "bias_20": 2.0}}

#: 缺值情境（修後一律：§七 無 M1B 那條、KPI「待取得」、無代理註記／警語、不拋）
_MISSING = {
    # (a) 代理源、缺數字
    "a_proxy_no_number_keys": {"source": M1B_PROXY_SOURCE_LABEL},
    "a_proxy_raw_both_none": {"m1b_yoy": None, "m2_yoy": None, "source": M1B_PROXY_SOURCE_LABEL_RAW},
    "a_proxy_flag_m1b_nan": {"m1b_yoy": float("nan"), "m2_yoy": 2.0, "source": "CBC-tier1",
                             "is_proxy_tier": True},
    # (b) 缺一邊的鍵
    "b_m2_key_absent": {"m1b_yoy": 4.2, "source": "CBC-tier1"},
    "b_m1b_key_absent": {"m2_yoy": 2.0, "source": "FRED"},
    "b_m2_key_absent_proxy": {"m1b_yoy": 4.2, "source": M1B_PROXY_SOURCE_LABEL},
    "b_gap_only": {"gap": 1.5, "source": "CBC-tier1"},
    # (c) 明確為 None
    "c_m1b_none": {"m1b_yoy": None, "m2_yoy": 2.0, "source": "CBC-tier1"},
    "c_m2_none": {"m1b_yoy": 4.2, "m2_yoy": None, "source": "CBC-tier1"},
    # NaN／±inf
    "nan_m2": {"m1b_yoy": 4.2, "m2_yoy": float("nan"), "source": "CBC-tier1"},
    "np_nan_m1b": {"m1b_yoy": np.nan, "m2_yoy": 2.0, "source": "FRED"},
    "np_float64_nan_m2": {"m1b_yoy": 4.2, "m2_yoy": np.float64("nan")},
    "inf_m1b": {"m1b_yoy": float("inf"), "m2_yoy": 2.0, "source": "CBC-tier1"},
    "neg_inf_m2_proxy": {"m1b_yoy": 4.2, "m2_yoy": float("-inf"), "source": M1B_PROXY_SOURCE_LABEL},
    # 非數值
    "str_m2": {"m1b_yoy": 4.2, "m2_yoy": "n/a", "source": "CBC-tier1"},
    "bool_m2": {"m1b_yoy": 4.2, "m2_yoy": True, "source": "CBC-tier1"},
}
_PROXY_MISSING = {k for k, v in _MISSING.items()
                  if v.get("source") in (M1B_PROXY_SOURCE_LABEL, M1B_PROXY_SOURCE_LABEL_RAW)
                  or v.get("is_proxy_tier")}


# ══════════════════════════════════════════════════════════════════════════
# B 的契約（本尊跑＝測試；突變體跑＝證明測試抓得到）
# ══════════════════════════════════════════════════════════════════════════
def _check_missing(mod, info, bias=None) -> None:
    out, exc = _render(mod, info, bias)
    assert exc is None, f"缺值不得拋錯：{exc!r}"
    assert _s7_m1b_cards(out) == [], "§七 不得列 M1B-M2 那條（缺值不得算差額）"
    assert NOTE not in "\n".join(t for _, t in out), "沒有數字就不得出現代理註記"
    assert not any(t.startswith(_PROXY_CAPTION_HEAD) for _, t in out), "沒有數字就不得出現代理警語"
    assert _kpi_cards(out) == [kpi(*_PENDING_KPI)], "KPI 應走灰態「待取得」"
    empty, e_empty = _render(mod, None, bias)
    assert e_empty is None
    fetching, pending = kpi(*_FETCHING_KPI), kpi(*_PENDING_KPI)
    assert sum(1 for _, t in empty if t == fetching) == 1, "「空」的樣子應恰有一張「抓取中」灰卡"
    want = [(k, pending if t == fetching else t) for k, t in empty]
    assert out == want, "完整輸出應＝「空」的完整輸出，唯一差別是 KPI 值 抓取中 → 待取得"


# ══════════════════════════════════════════════════════════════════════════
# A＋B：三種情形，修前 vs 修後
# ══════════════════════════════════════════════════════════════════════════
class TestThreeCasesBeforeAndAfter:

    def test_a_proxy_without_numbers(self, pre_fix):
        info = {"source": M1B_PROXY_SOURCE_LABEL}
        out, exc = _render(pre_fix, info)
        assert exc is None
        # 修前：捏 0 ＋ 代理註記 ＋ D2 警語（修前 b7456d1 實跑擷取）
        assert _s7_m1b_cards(out) == [strategy_conclusion(
            STRATEGY_TECHNICAL, f"M1B-M2=+0.00%{NOTE} 接近0", "資金動能趨緩，減碼等待訊號確認",
            color=TRAFFIC_RED)]
        assert _kpi_cards(out) == [kpi("M1B-M2 差距", f"+0.00%{NOTE}",
                                       "M1B:0.0%  M2:0.0%  🔴 資金撤離股市", "#2ea043", "#0d1117")]
        assert any(t.startswith(_PROXY_CAPTION_HEAD) for _, t in out)
        _check_missing(_long_module(), info)

    def test_b_m2_missing(self, pre_fix):
        info = {"m1b_yoy": 4.2, "source": "CBC-tier1"}
        out, exc = _render(pre_fix, info)
        assert exc is None
        # 修前：差額＝M1B 年增率本身 →「正值 → 大膽做多！」
        assert _s7_m1b_cards(out) == [strategy_conclusion(
            STRATEGY_TECHNICAL, "M1B-M2=+4.20% 正值", "資金行情啟動，大膽做多！（領先大盤3~6月）",
            color=TRAFFIC_GREEN)]
        assert _kpi_cards(out) == [kpi("M1B-M2 差距", "+4.20%",
                                       "M1B:4.2%  M2:0.0%  ✅ 資金流入股市", "#da3633", "#0d1117")]
        _check_missing(_long_module(), info)

    @pytest.mark.parametrize("info", [
        {"m1b_yoy": None, "m2_yoy": 2.0, "source": "CBC-tier1"},
        {"m1b_yoy": 4.2, "m2_yoy": None, "source": "CBC-tier1"},
        {"m1b_yoy": None, "m2_yoy": None, "source": M1B_PROXY_SOURCE_LABEL},
    ], ids=["m1b_none", "m2_none", "both_none_proxy"])
    def test_c_explicit_none(self, pre_fix, info):
        _out, exc = _render(pre_fix, info)
        assert isinstance(exc, TypeError), f"修前應在 §七 拋 TypeError，實得 {exc!r}"
        _check_missing(_long_module(), info)

    @pytest.mark.parametrize("info", [
        {"m1b_yoy": 4.2, "m2_yoy": float("nan"), "source": "CBC-tier1"},
        {"m1b_yoy": float("inf"), "m2_yoy": 2.0, "source": "CBC-tier1"},
    ], ids=["nan", "inf"])
    def test_nan_inf_were_printed_as_numbers_before(self, pre_fix, info):
        out, exc = _render(pre_fix, info)
        assert exc is None
        joined = "\n".join(t for _, t in out)
        assert "+nan%" in joined or "+inf%" in joined, "修前應把 NaN／inf 印成數字"
        _check_missing(_long_module(), info)


class TestMissingMatrix:

    @pytest.mark.parametrize("bias", sorted(_BIAS))
    @pytest.mark.parametrize("name", sorted(_MISSING))
    def test_no_fabrication_and_looks_like_empty(self, name, bias):
        _check_missing(_long_module(), _MISSING[name], _BIAS[bias])

    @pytest.mark.parametrize("bias", sorted(_BIAS))
    @pytest.mark.parametrize("name", sorted(_MISSING))
    def test_s7_block_identical_to_empty(self, name, bias):
        """§七 那一區（標題到 KPI 卡之前）與 `m1b_m2_info` 為空時逐字相同 —— 純刪，不留替代句。"""
        M = _long_module()
        out, _ = _render(M, _MISSING[name], _BIAS[bias])
        empty, _ = _render(M, None, _BIAS[bias])

        def _s7(recs):
            i = next(n for n, (_, t) in enumerate(recs) if ">M1B-M2 差距</div>" in t)
            return recs[:i]
        assert _s7(out) == _s7(empty)

    @pytest.mark.parametrize("name", sorted(_MISSING))
    def test_pre_fix_fabricated_or_raised(self, pre_fix, name):
        """反向對照：每一個缺值情境在修前都真的出事（否則上面的測試不證明什麼）。"""
        out, exc = _render(pre_fix, _MISSING[name])
        assert exc is not None or _s7_m1b_cards(out), f"{name}：修前既沒拋錯也沒捏值？"


class TestEmptyStateUnchanged:

    @pytest.mark.parametrize("bias", sorted(_BIAS))
    @pytest.mark.parametrize("info", [None, {}], ids=["none", "empty_dict"])
    def test_identical_to_pre_fix(self, pre_fix, info, bias):
        now, e1 = _render(_long_module(), info, _BIAS[bias])
        pre, e2 = _render(pre_fix, info, _BIAS[bias])
        assert e1 is None and e2 is None
        assert now == pre
        assert _kpi_cards(now) == [kpi(*_FETCHING_KPI)] and _s7_m1b_cards(now) == []


# ══════════════════════════════════════════════════════════════════════════
# C：非缺值 —— 完整輸出與修前逐字相同
# ══════════════════════════════════════════════════════════════════════════
#: 修前（b7456d1）以同一個 harness 實跑擷取（非代理）：(差額字串, §七 分支, §七 結論, KPI 副標, KPI 色)。
#: 代理時：§七 指標段與 KPI 值在差額字串後多一串 NOTE，其餘逐字相同。
_GOLDEN = {
    "strong": ("+3.10%", "正值", "資金行情啟動，大膽做多！（領先大盤3~6月）",
               "M1B:5.1%  M2:2.0%  ✅ 資金流入股市", "#da3633"),
    "mild": ("+0.50%", "正值", "資金行情啟動，大膽做多！（領先大盤3~6月）",
             "M1B:3.0%  M2:2.5%  ✅ 資金流入股市", "#da3633"),
    "tiny_pos": ("+0.00%", "正值", "資金行情啟動，大膽做多！（領先大盤3~6月）",
                 "M1B:2.0%  M2:2.0%  🔴 資金撤離股市", "#2ea043"),
    "zero": ("+0.00%", "接近0", "資金動能趨緩，減碼等待訊號確認",
             "M1B:2.0%  M2:2.0%  🔴 資金撤離股市", "#2ea043"),
    "near_zero": ("-1.00%", "接近0", "資金動能趨緩，減碼等待訊號確認",
                  "M1B:1.0%  M2:2.0%  🔴 資金撤離股市", "#2ea043"),
    "minus2": ("-2.00%", "負值", "資金撤離，空手觀望！",
               "M1B:1.0%  M2:3.0%  🔴 資金撤離股市", "#2ea043"),
    "negative": ("-3.80%", "負值", "資金撤離，空手觀望！",
                 "M1B:1.2%  M2:5.0%  🔴 資金撤離股市", "#2ea043"),
    "both_negative": ("+1.50%", "正值", "資金行情啟動，大膽做多！（領先大盤3~6月）",
                      "M1B:-1.5%  M2:-3.0%  ✅ 資金流入股市", "#da3633"),
    "m2_is_zero": ("+1.50%", "正值", "資金行情啟動，大膽做多！（領先大盤3~6月）",
                   "M1B:1.5%  M2:0.0%  ✅ 資金流入股市", "#da3633"),
    "m1b_is_zero": ("-0.80%", "接近0", "資金動能趨緩，減碼等待訊號確認",
                    "M1B:0.0%  M2:0.8%  🔴 資金撤離股市", "#2ea043"),
}


def _check_golden(mod, gap: str, source: str) -> None:
    diff, branch, result, sub, color = _GOLDEN[gap]
    m1b, m2 = _GAPS[gap]
    out, exc = _render(mod, {"m1b_yoy": m1b, "m2_yoy": m2, **_SOURCES[source]})
    assert exc is None
    note = NOTE if source.startswith("proxy") else ""
    assert _s7_m1b_cards(out) == [strategy_conclusion(
        STRATEGY_TECHNICAL, f"M1B-M2={diff}{note} {branch}", result,
        color=TRAFFIC_GREEN if branch == "正值" else TRAFFIC_RED)]
    assert _kpi_cards(out) == [kpi("M1B-M2 差距", f"{diff}{note}", sub, color, "#0d1117")]
    assert sum(t.startswith(_PROXY_CAPTION_HEAD) for _, t in out) == (1 if note else 0)


class TestNonMissingUnchanged:

    @pytest.mark.parametrize("gap", sorted(_GAPS))
    @pytest.mark.parametrize("source", sorted(_SOURCES))
    def test_full_output_identical_to_pre_fix(self, pre_fix, source, gap):
        m1b, m2 = _GAPS[gap]
        for bias in _BIAS.values():
            info = {"m1b_yoy": m1b, "m2_yoy": m2, **_SOURCES[source]}
            now, e_now = _render(_long_module(), info, bias)
            pre, e_pre = _render(pre_fix, info, bias)
            assert e_now is None and e_pre is None
            assert now == pre, f"{source}/{gap}/bias={bias}：完整輸出與修前不同"

    @pytest.mark.parametrize("gap", sorted(_GOLDEN))
    @pytest.mark.parametrize("source", ["CBC-tier1", "no_source", "proxy_label", "proxy_flag_is_proxy_tier"])
    def test_key_strings_match_pre_fix_golden(self, source, gap):
        _check_golden(_long_module(), gap, source)


class TestFiniteYoy:

    @pytest.mark.parametrize("v", [
        None, float("nan"), np.nan, np.float64("nan"), float("inf"), float("-inf"), np.inf,
        True, False, "4.2", "n/a", 1 + 2j, decimal.Decimal("NaN"), decimal.Decimal("sNaN"),
        decimal.Decimal("Infinity"), 10 ** 400, [1.0], {},
    ])
    def test_not_a_finite_number_is_missing(self, v):
        assert _long_module()._finite_yoy({"k": v}, "k") is None

    @pytest.mark.parametrize("info", [None, {}, [1.0], "x", {"other": 1.0}])
    def test_absent_key_or_non_dict_is_missing(self, info):
        assert _long_module()._finite_yoy(info, "k") is None

    @pytest.mark.parametrize("v", [4.2, -3.0, 0.0, -0.0, 5, 0, np.float64(1.5), np.float32(2.5), np.int64(3)])
    def test_finite_number_is_returned_as_the_same_object(self, v):
        """回原物件、不轉型 —— 非缺值路徑的算術與格式化與修前同一個物件（真 0 不是缺）。"""
        assert _long_module()._finite_yoy({"k": v}, "k") is v


# ══════════════════════════════════════════════════════════════════════════
# D：K1 —— 不自擬文案
# ══════════════════════════════════════════════════════════════════════════
def _str_literals(code: str) -> set[str]:
    """原始碼中所有字串常數（排除 docstring；註解天然不在 AST）。f-string 以字面片段計。"""
    tree = ast.parse(code)
    doc: set[int] = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body:
            b0 = n.body[0]
            if isinstance(b0, ast.Expr) and isinstance(b0.value, ast.Constant) \
                    and isinstance(b0.value.value, str):
                doc.add(id(b0.value))
    return {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc}


def _kpi_calls(code: str) -> list[tuple]:
    """所有「參數全為字串常數」的 `kpi(...)` 呼叫 → 參數 tuple。"""
    out = []
    for n in ast.walk(ast.parse(code)):
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "kpi" \
                and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in n.args):
            out.append(tuple(a.value for a in n.args))
    return out


class TestK1NoNewCopy:

    def test_only_new_literal_is_daiqude(self):
        """本檔相對修前（還原體）新增的字串常數只有「待取得」，也沒有刪掉任何既有字面。"""
        now = _str_literals(_LONG_PATH.read_text(encoding="utf-8"))
        pre = _str_literals(_revert_source())
        assert now - pre == {"待取得"}, f"新增了本檔原本沒有的字面：{sorted(now - pre)}"
        assert pre - now == set(), f"刪掉了既有字面：{sorted(pre - now)}"

    def test_daiqude_is_an_existing_gray_kpi_value_in_repo(self):
        """「待取得」不是新句：section_mid 的 VIX 卡本來就用同一個 kpi 灰態（值＋灰字色）。"""
        mid = [c for c in ast.walk(ast.parse(_MID_PATH.read_text(encoding="utf-8")))
               if isinstance(c, ast.Call) and getattr(c.func, "id", None) == "kpi"
               and len(c.args) >= 4
               and isinstance(c.args[1], ast.Constant) and c.args[1].value == "待取得"
               and isinstance(c.args[3], ast.Constant) and c.args[3].value == "#484f58"]
        assert mid, "section_mid 找不到「待取得」灰態 kpi —— K1 出處失效，請重新確認"

    def test_pending_card_is_the_existing_gray_card_with_only_the_value_swapped(self):
        gray = [c for c in _kpi_calls(_LONG_PATH.read_text(encoding="utf-8")) if c[0] == "M1B-M2 差距"]
        assert sorted(gray) == sorted([_FETCHING_KPI, _PENDING_KPI]), gray
        assert _FETCHING_KPI[:1] + _FETCHING_KPI[2:] == _PENDING_KPI[:1] + _PENDING_KPI[2:]


# ══════════════════════════════════════════════════════════════════════════
# E：突變 —— 每一個都要讓新測試轉紅
# ══════════════════════════════════════════════════════════════════════════
_PENDING_LINE = "'待取得', '更新總經數據後自動計算', '#484f58', '#0d1117'), unsafe_allow_html=True)\n"
_NUMERIC = {k for k in _MISSING if k.startswith(("nan", "np_", "inf", "neg_inf"))} | {"a_proxy_flag_m1b_nan"}
_ABSENT_KEY = {"a_proxy_no_number_keys", "b_m2_key_absent", "b_m1b_key_absent",
               "b_m2_key_absent_proxy", "b_gap_only"}
_EXPLICIT_NONE = {"a_proxy_raw_both_none", "c_m1b_none", "c_m2_none"}

#: 名稱 → (替換組, 至少要轉紅的缺值情境)
_MUTANTS = {
    # 恢復 `.get(key, 0)`：缺鍵 → 0 → 有限 → 捏值
    "helper_get_default_zero": ((("    _v = info.get(key)\n", "    _v = info.get(key, 0)\n"),),
                                _ABSENT_KEY),
    # 只判 None、不判 NaN／inf
    "helper_none_only_no_finite_check": ((("        return _v if math.isfinite(_v) else None\n",
                                           "        return _v\n"),), _NUMERIC),
    # bool 當數字
    "helper_bool_counts_as_number": ((("    if _v is None or isinstance(_v, bool):\n",
                                       "    if _v is None:\n"),), {"bool_m2"}),
    # 缺值時仍顯示代理警語（灰卡下面照樣貼 D2 那行）
    "proxy_caption_without_number": (((_PENDING_LINE, _PENDING_LINE
                                       + "            if is_m1b_m2_proxy(_m1b_info):\n"
                                       + "                st.caption('⚠️ 央行 M1B/M2 三層來源全部失敗，上方兩個數字是以 '\n"
                                       + "                           '**^TWII 20/60 日動量反推的代理估算**，'\n"
                                       + "                           '不是真實貨幣供給年增率 —— 請勿據此判斷資金行情。')\n"),),
                                     _PROXY_MISSING),
    # 缺值時灰卡的值後面仍貼代理註記
    "proxy_note_on_pending_value": ((("kpi('M1B-M2 差距', '待取得', ",
                                      "kpi('M1B-M2 差距', '待取得' + m1b_m2_proxy_badge(_m1b_info), "),),
                                    _PROXY_MISSING),
    # KPI 走錯灰態：缺值掉進「抓取中」（未載入）那一枝
    "kpi_falls_into_fetching_state": ((("        elif _m1b_info:\n", "        elif False:\n"),),
                                      set(_MISSING)),
    # §七 閘門退回 `if _m1b_info:`（缺值照樣算差額）
    "s7_gate_back_to_truthiness": ((("    if _m1b_ok:\n        _diff2", "    if _m1b_info:\n        _diff2"),),
                                   set(_MISSING)),
    # KPI 閘門退回 `if _m1b_info:`
    "kpi_gate_back_to_truthiness": ((("        if _m1b_ok:\n            _diff   =",
                                      "        if _m1b_info:\n            _diff   ="),), set(_MISSING)),
}


def _red_cases(mod) -> set[str]:
    red = set()
    for k, info in _MISSING.items():
        try:
            _check_missing(mod, info)
        except AssertionError:
            red.add(k)
    return red


class TestMutantsAreCaught:

    def test_real_module_is_green(self):
        assert _red_cases(_long_module()) == set()

    @pytest.mark.parametrize("name", sorted(_MUTANTS))
    def test_mutant_turns_missing_contract_red(self, name):
        pairs, must_be_red = _MUTANTS[name]
        m = _load(_apply(_LONG_PATH.read_text(encoding="utf-8"), pairs), name)
        red = _red_cases(m)
        assert red, f"突變「{name}」沒讓任何缺值情境轉紅 —— 新測試抓不到它"
        assert must_be_red <= red, f"突變「{name}」應讓 {sorted(must_be_red - red)} 轉紅"

    def test_full_revert_to_pre_fix_turns_every_missing_case_red(self, pre_fix):
        assert _red_cases(pre_fix) == set(_MISSING)

    @pytest.mark.parametrize("pairs", [
        # 非缺值路徑：§七 改用四捨五入後的差額（tiny_pos 的分支會變）
        (("        _diff2 = _m1b_v - _m2_v\n", "        _diff2 = round(_m1b_v - _m2_v, 2)\n"),),
        # 非缺值路徑：KPI 副標格式變了
        (("f'M1B:{_m1b_v:.1f}%  M2:{_m2_v:.1f}%  {_ml}'", "f'M1B:{_m1b_v:.2f}%  M2:{_m2_v:.2f}%  {_ml}'"),),
        # 非缺值路徑：把真 0 當缺（`if not _v`）
        (("    if _v is None or isinstance(_v, bool):\n", "    if not _v or isinstance(_v, bool):\n"),),
    ], ids=["s7_rounded_diff", "kpi_sub_format", "zero_as_missing"])
    def test_non_missing_mutant_breaks_golden(self, pairs):
        m = _load(_apply(_LONG_PATH.read_text(encoding="utf-8"), pairs), "golden")
        broken = []
        for gap in _GOLDEN:
            for source in ("CBC-tier1", "proxy_label"):
                try:
                    _check_golden(m, gap, source)
                except AssertionError:
                    broken.append((gap, source))
        assert broken, "非缺值路徑的突變沒被 golden 抓到"


# ══════════════════════════════════════════════════════════════════════════
# F：slow lane —— 真 Streamlit（AppTest）render
# ══════════════════════════════════════════════════════════════════════════
def _app(info):
    """真 AppTest render（`m1b_m2_info` 以 JSON 傳入，NaN 亦可）→ 已 run 的 AppTest。"""
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest
    body = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(_REPO)!r})\n"
        "import streamlit as st\n"
        f"st.session_state['m1b_m2_info'] = json.loads({json.dumps(info)!r})\n"
        "from src.ui.tabs.macro.section_long import render_section_long\n"
        "render_section_long(False, {}, {}, {}, {}, {}, {})\n"
    )
    at = AppTest.from_string(body, default_timeout=90)
    at.run()
    if at.exception:
        pytest.fail("render 有 uncaught exception:\n" + "\n".join(
            f"{e.type}: {str(e.value)[:300]}" for e in at.exception))
    return at


def _texts(at) -> list[str]:
    return [str(m.value) for m in at.markdown] + [str(c.value) for c in at.caption]


@pytest.mark.slow
class TestRealStreamlitRender:

    @pytest.mark.parametrize("info", [
        {"source": M1B_PROXY_SOURCE_LABEL},
        {"m1b_yoy": 4.2, "source": "CBC-tier1"},
        {"m1b_yoy": None, "m2_yoy": 2.0, "source": "CBC-tier1"},
        {"m1b_yoy": 4.2, "m2_yoy": float("nan"), "source": M1B_PROXY_SOURCE_LABEL},
    ], ids=["a_proxy_no_number", "b_m2_missing", "c_m1b_none", "nan_m2_proxy"])
    def test_missing_renders_pending_without_fabrication(self, info):
        texts = _texts(_app(info))
        assert any(">M1B-M2 差距</div>" in t and ">待取得</div>" in t for t in texts), "KPI 應為「待取得」"
        assert not any("M1B-M2=" in t for t in texts), "§七 不得列 M1B-M2 那條"
        assert not any(NOTE in t for t in texts), "沒有數字不得出現代理註記"
        assert not any(t.startswith(_PROXY_CAPTION_HEAD) for t in texts), "沒有數字不得出現代理警語"

    def test_empty_state_still_fetching(self):
        texts = _texts(_app(None))
        assert any(">M1B-M2 差距</div>" in t and ">抓取中</div>" in t for t in texts)

    def test_numbers_still_render_with_proxy_disclosure(self):
        texts = _texts(_app({"m1b_yoy": 5.1, "m2_yoy": 2.0, "source": M1B_PROXY_SOURCE_LABEL}))
        assert any(f"M1B-M2=+3.10%{NOTE} 正值 → " in t for t in texts)
        assert any(f">+3.10%{NOTE}</div>" in t for t in texts)
        assert any(t.startswith(_PROXY_CAPTION_HEAD) for t in texts)
