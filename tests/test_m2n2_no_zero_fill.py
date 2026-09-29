"""tests/test_m2n2_no_zero_fill.py — 批 M2N-2：M1B／M2 年增率缺值時不再捏 0（DL-f1-s16＋s44）。

病史（本檔存在的理由）
────────────────────────────────────────────────────────────────
#746（DL-f1-s24，`b2dafba`）只修了 v1 `section_long.py` 的 §七。同型的「缺值捏 0」
（`.get('m1b_yoy', 0)`／`.get('m2_yoy', 0)`／`float(m2 or 0)`）還有 4 個出口：

  ① src/ui/tabs/macro/section_news_ai.py::render_section_news_ai（§十一 AI 裁決）
     · prompt：缺 M2 鍵 →「M2=0.0%」、差額以 0 代 M2；M2 為 None → `:.1f` 拋 TypeError；
     · 規則引擎 `_macro_numbers`：原樣轉送 → 只缺一邊時 spread 變成單邊值
       （缺 M2 ⇒ +M1B ⇒ 升成「多頭」；缺 M1B ⇒ −M2 ⇒ 扣分並貼「資金緊縮」）；±inf 直接算分。
  ② src/ui/tabs/stock_sections/section_op_recommendation.py（個股即時操作建議）
     · `m1b_diff` 兩鍵各 `.get(...,0)` 相減 → 缺一邊時 L3 印「M1B-M2為正且強勁／為負」；
       值為 None → TypeError 被吞成「AI 分析暫時無法使用」。
  ③ src/ui/tabs/macro/section_state.py（§二 拐點 M1B-M2 黃金／死亡交叉）
     · 同上 2 處；值為 None 時 `None - x` 直接炸掉 §二（無 try）；NaN／缺數字仍把
       資金群登記為可評估 ⇒ 畫面印「資金：中性」並算進分母。
  ④ src/ui/tabs/macro/section_mid.py（§八 策略3 卡＋⚔️ 三環 D 徽章）
     · 外層已判 `is not None`，但 NaN／±inf 照樣進三段分支（nan ⇒「死亡交叉」）。

修法（L5 only；⛔ L3 零行）
────────────────────────────────────────────────────────────────
  · 「可用」一律用 #746 的 `section_long._finite_yoy`（同一個函式，不另寫一份）；
  · M1B 或 M2 任一不可用 → 兩個都當缺：§十一 規則引擎兩個都收 None、prompt 不送那一行
    （同一行在 M1B 缺時本來就不送）；個股建議 `m1b_diff` 送 None；§二 不出交叉訊號、
    資金群不因 M1B/M2 登記；§八 走既有「載入後自動顯示」與「D M1B-M2未知」；
  · 兩個都有值 → 同一組物件、同一段算式 → 輸出與修前相同（唯一例外見 D-2）。

本檔釘的東西
────────────────────────────────────────────────────────────────
  A. L3 實跑：兩個 None 走既有缺值路徑（不加不扣、不貼「資金緊縮」、個股不出 M1B-M2 句）；
     只清一個值會被看見（突變 G 的前提守衛）。
  B. 修後缺值契約：每個出口 × 每種缺值 → 不拋、完整輸出 ＝ `m1b_m2_info` 為空時的完整輸出；
     §十一 另驗 prompt 無「M2=0.0%」、規則引擎收到兩個 None。
  C. 修前確實出事：還原體（反向替換回修前碼）在每個出口的「出事集合」與修前實跑相符。
  D. 非缺值：完整輸出與還原體逐字相同（19 種數值 × 非代理／代理共 7 種來源形狀）＋修前實跑 golden
     （還原體由現行檔反向替換產生，看不到寫進原始檔本身的非缺值改動 —— 那部分只靠 golden，
     含驗收組非阻擋 1 補的小數第 2 位差額與零差額）；
     D-2：唯一差異（M1B、M2 皆為負零時 §十一 差額的零號）照實釘住。
  E. 不複製判斷邏輯：4 檔都從 section_long 取 `_finite_yoy`，檔內無自寫的有限值判斷。
  F. K1：4 檔字串常數集合與修前完全相同（不新增、不改寫任何字）。
  G. 突變：拿掉守衛／只清一個值／只驗一邊／登記移回閘門外 … 每個都讓 B 轉紅；
     非缺值路徑的突變讓 D 轉紅；寫進原始檔本身的非缺值突變（驗收組點名的 §八 `_gap8` 少一位、
     §二 `> 0` 改 `>= 0`）讓 golden 轉紅。
  H. slow lane：真 Streamlit（AppTest）render 4 個出口（§十一 真按「執行 AI 裁決」）。

⚠️ harness：`_FakeST` 以 monkeypatch 換掉**被測模組**（本尊或還原體／突變體）的 module-level
   `st`；Gemini、新聞 RSS、狀態鎖寫檔、配置 SSOT 一律換成離線替身。還原體／突變體以
   `exec` 載成獨立模組（不進 `sys.modules`，不碰本尊）。本檔不吃日期、不觸網、不寫檔。
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import json
import pathlib
import re
import types

import numpy as np
import pytest

from shared.macro_provenance import (
    M1B_PROXY_SOURCE_LABEL,
    M1B_PROXY_SOURCE_LABEL_RAW,
    M1B_PROXY_VALUE_NOTE as NOTE,
)

_REPO = pathlib.Path(__file__).resolve().parents[1]

#: 出口代號 → (檔案, 模組名)
_FILES = {
    "news": ("src/ui/tabs/macro/section_news_ai.py", "src.ui.tabs.macro.section_news_ai"),
    "op": ("src/ui/tabs/stock_sections/section_op_recommendation.py",
           "src.ui.tabs.stock_sections.section_op_recommendation"),
    "state": ("src/ui/tabs/macro/section_state.py", "src.ui.tabs.macro.section_state"),
    "mid": ("src/ui/tabs/macro/section_mid.py", "src.ui.tabs.macro.section_mid"),
}
_EXITS = sorted(_FILES)
_LONG_MOD = "src.ui.tabs.macro.section_long"

#: §八 既有灰態字樣（本批沿用，不是新字）
_MID_PENDING = "M1B/M2 數據載入後自動顯示資金動能判斷"
_MID_D_UNKNOWN = "D M1B-M2未知"


# ══════════════════════════════════════════════════════════════════════════
# 假的 streamlit（只記錄文字；未知 API 一律 no-op）
# ══════════════════════════════════════════════════════════════════════════
class _Rerun(Exception):
    """`st.rerun()` 的替身：讓 §十一 裁決流程在 Gemini 回來後乾淨地停下。"""


class _Any:
    """未實作的 st.* 回傳值：可呼叫 / 可 with / falsy（未知 widget = 沒被按）。"""

    def __init__(self, st):
        self._st = st

    def __call__(self, *a, **k):
        return _Any(self._st)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(self._st, name)      # column.markdown(...) → 同一個記錄器

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __bool__(self):
        return False


class _FakeST:
    _TEXT = ("markdown", "caption", "info", "warning", "success", "error", "write")

    def __init__(self, session_state=None, clicked=()):
        self.session_state = dict(session_state or {})
        self.secrets: dict = {}
        self.out: list[tuple[str, str]] = []
        self._clicked = set(clicked)

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

    def tabs(self, labels, *a, **k):
        return [_Any(self) for _ in labels]

    def expander(self, label="", *a, **k):
        self.out.append(("expander", str(label)))
        return _Any(self)

    def button(self, label="", key=None, *a, **k):
        return key in self._clicked

    def checkbox(self, *a, **k):
        return False

    toggle = checkbox

    def rerun(self, *a, **k):
        raise _Rerun()


# ══════════════════════════════════════════════════════════════════════════
# 還原體（修前）與突變體
# ══════════════════════════════════════════════════════════════════════════
def _mod(ek: str):
    return importlib.import_module(_FILES[ek][1])


def _source(ek: str) -> str:
    return (_REPO / _FILES[ek][0]).read_text(encoding="utf-8")


def _apply(code: str, pairs) -> str:
    """每一組 `old` **恰好一處**換成 `new`。"""
    for old, new in pairs:
        assert code.count(old) == 1, f"替換點不唯一或已不存在：{old!r}"
        code = code.replace(old, new)
    return code


def _load(ek: str, code: str, tag: str):
    """把一份（改過的）原始碼載成獨立模組（不進 `sys.modules`，不碰本尊）。"""
    real = _mod(ek)
    spec = importlib.util.spec_from_loader(f"_m2n2_{ek}_{tag}", loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = real.__file__
    exec(compile(code, real.__file__, "exec"), m.__dict__)
    return m


_IMPORT_LINE = "from src.ui.tabs.macro.section_long import _finite_yoy\n"

#: 反向替換：把本批改動還原成修前碼（＝da4eb94）。
#: 本實作組另做過一次性驗證（不在本檔重跑）：4 個還原體與 da4eb94 的 AST 完全相同；
#: 並以同一個 harness 在修前工作樹實跑擷取 696 組輸出（4 出口 ×〔17 種數值 × 9 種來源形狀
#: ＋ 19 種缺值 ＋ 2 種空值〕），修後逐一比對 —— 612 組正常／代理只有 D-2 那 9 組
#:（同一格 × 9 種來源形狀）不同；84 組缺值／空值修後每組都＝空值輸出；空值兩組的畫面／prompt
#: 修前修後相同（唯一不同是個股建議送 L3 的 `m1b_diff` 由 0 改為 None，見 D 的空值那條）。
_REVERT = {
    "news": (
        (_IMPORT_LINE, ""),
        ("                _m1b_ai = _finite_yoy(_mi_d, 'm1b_yoy')\n"
         "                _m2_ai  = _finite_yoy(_mi_d, 'm2_yoy')\n"
         "                if _m1b_ai is None or _m2_ai is None:\n"
         "                    _m1b_ai = _m2_ai = None\n", ""),
        ("                    'M1B_YoY_pct':         _m1b_ai,\n"
         "                    'M2_YoY_pct':          _m2_ai,\n",
         "                    'M1B_YoY_pct':         _mi_d.get('m1b_yoy'),\n"
         "                    'M2_YoY_pct':          _mi_d.get('m2_yoy'),\n"),
        ("                if _m1b_ai is not None and _m2_ai is not None:\n"
         "                    _gap_v = round(float(_m1b_ai) - float(_m2_ai), 2)\n",
         "                if _mi_d.get('m1b_yoy') is not None:\n"
         "                    _gap_v = round(float(_mi_d['m1b_yoy']) - float(_mi_d.get('m2_yoy') or 0), 2)\n"),
        ("f'• M1B={_m1b_ai:.1f}%  M2={_m2_ai:.1f}%  '",
         "f'• M1B={_mi_d[\"m1b_yoy\"]:.1f}%  M2={_mi_d.get(\"m2_yoy\",0):.1f}%  '"),
    ),
    "op": (
        (_IMPORT_LINE, ""),
        ("        _m1b_g = _finite_yoy(_m1b_top_g, 'm1b_yoy')\n"
         "        _m2_g = _finite_yoy(_m1b_top_g, 'm2_yoy')\n"
         "        _m1b_diff_g = (_m1b_g - _m2_g\n"
         "                       if _m1b_g is not None and _m2_g is not None else None)\n",
         "        _m1b_diff_g = (_m1b_top_g.get('m1b_yoy', 0) - _m1b_top_g.get('m2_yoy', 0)\n"
         "                       if _m1b_top_g else 0)\n"),
    ),
    "state": (
        (_IMPORT_LINE, ""),
        ("        _m1b_y = _finite_yoy(_m1b2, 'm1b_yoy')\n"
         "        _m2_y  = _finite_yoy(_m1b2, 'm2_yoy')\n"
         "        if (_m1b2 and not is_m1b_m2_proxy(_m1b2)\n"
         "                and _m1b_y is not None and _m2_y is not None):\n"
         "            _fam_ok.add('liquidity')   # v19.173：M1B/M2 到位 → 資金群可評估\n",
         "        if _m1b2 and not is_m1b_m2_proxy(_m1b2):\n"
         "            _fam_ok.add('liquidity')   # v19.173：M1B/M2 到位 → 資金群可評估\n"
         "            _m1b_y = _m1b2.get('m1b_yoy', 0)\n"
         "            _m2_y  = _m1b2.get('m2_yoy', 0)\n"),
    ),
    "mid": (
        (_IMPORT_LINE, ""),
        ("        _m1b8_v = _finite_yoy(_m1b8_info, 'm1b_yoy')\n"
         "        _m2b8_v = _finite_yoy(_m1b8_info, 'm2_yoy')\n"
         "        if _m1b8_v is not None and _m2b8_v is not None:\n"
         "            _m1b8 = float(_m1b8_v)\n"
         "            _m2b8 = float(_m2b8_v)\n",
         "        if _m1b8_info and _m1b8_info.get('m1b_yoy') is not None"
         " and _m1b8_info.get('m2_yoy') is not None:\n"
         "            _m1b8 = float(_m1b8_info.get('m1b_yoy', 0))\n"
         "            _m2b8 = float(_m1b8_info.get('m2_yoy', 0))\n"),
        ("            if _m1b8_v is not None and _m2b8_v is not None:\n"
         "                try:\n"
         "                    _gap8c = round(float(_m1b8_v) - float(_m2b8_v), 2)\n",
         "            if (_m1b8_info and _m1b8_info.get('m1b_yoy') is not None and\n"
         "                    _m1b8_info.get('m2_yoy') is not None):\n"
         "                try:\n"
         "                    _gap8c = round(float(_m1b8_info['m1b_yoy']) -\n"
         "                                   float(_m1b8_info['m2_yoy']), 2)\n"),
    ),
}


def _revert_source(ek: str) -> str:
    return _apply(_source(ek), _REVERT[ek])


@pytest.fixture(scope="module")
def pre_fix():
    return {ek: _load(ek, _revert_source(ek), "pre_fix") for ek in _EXITS}


# ══════════════════════════════════════════════════════════════════════════
# 4 個出口的 runner（吃模組物件：本尊／還原體／突變體；全部離線）
# ══════════════════════════════════════════════════════════════════════════
def _run_news(mod, info, mp) -> dict:
    """§十一：按下「🔒 執行 AI 裁決」→ 攔下送 Gemini 的 prompt、引擎輸入、鎖定的狀態。"""
    import src.data.news as N
    import src.services.app_ai_service as A
    from src.services.macro_state_locker import calculate_system_state as _real_calc
    fake = _FakeST({"m1b_m2_info": info}, clicked={"btn_run_verdict"})
    prompts: list[str] = []
    locked: list[dict] = []
    numbers: list[dict] = []

    class _Locker:                       # 不寫 macro_state.json
        def lock_system_state_only(self, state):
            locked.append(state)

    def _spy_calc(nums):                 # 只記錄、原樣交給 L3 本尊
        numbers.append(dict(nums))
        return _real_calc(nums)

    def _gemini(prompt, max_tokens=2048):
        prompts.append(prompt)
        return "（測試替身報告）"

    mp.setattr(mod, "st", fake)
    mp.setattr(mod, "render_macro_bucket_summary_bar", lambda *a, **k: None)
    mp.setattr(mod, "MacroStateLocker", _Locker)
    mp.setattr(mod, "calculate_system_state", _spy_calc)
    mp.setattr(A, "gemini_call", _gemini)
    mp.setattr(N, "fetch_macro_news", lambda *a, **k: [])
    exc = None
    try:
        mod.render_section_news_ai({}, "unknown")
    except _Rerun:
        pass
    except Exception as e:  # noqa: BLE001 —— 修前 None 值就是要抓到這個
        exc = e
    return {"exc": exc, "prompt": prompts[0] if prompts else None,
            "n_prompts": len(prompts), "numbers": numbers, "locked": locked, "out": fake.out}


def _run_op(mod, info, mp) -> dict:
    """個股「即時操作建議」：攔下送 L3 `generate_ai_comment` 的 `m1b_diff`。"""
    import src.services.allocation_service as AS
    from src.services.app_ai_service import generate_ai_comment as _real_gac
    fake = _FakeST({"m1b_m2_info": info, "cl_data": {"inst": {}}})
    seen: list = []

    def _spy_gac(data):
        seen.append(data.get("m1b_diff", "<absent>"))
        return _real_gac(data)

    mp.setattr(mod, "st", fake)
    mp.setattr(mod, "generate_ai_comment", _spy_gac)
    mp.setattr(AS, "get_macro_regime", lambda *a, **k: {"is_loaded": False})
    exc = None
    try:
        mod.render_op_recommendation_section("2330", 82.0, {"contracting": True},
                                             5.0, 100.0, 55.0, 0, 0)
    except Exception as e:  # noqa: BLE001
        exc = e
    return {"exc": exc, "m1b_diff": seen, "out": fake.out}


def _run_state(mod, info, mp) -> dict:
    """§二 拐點面板：六大面向其餘來源全空（NDC／外資連續以空快取擋住，不觸網）。"""
    fake = _FakeST({"m1b_m2_info": info, "_ndc_hist_cache": {}, "_ndc_li_cache": {},
                    "_fi_streak_cache": {}})
    mp.setattr(mod, "st", fake)
    exc = None
    try:
        mod.render_section_state({"signals": []}, None, None, {},
                                 show_market_data=False, requested=True)
    except Exception as e:  # noqa: BLE001 —— 修前 None 值 `None - x` 就是要抓到這個
        exc = e
    return {"exc": exc, "pivots": fake.session_state.get("_pivot_signals"), "out": fake.out}


def _run_mid(mod, info, mp) -> dict:
    """§八 總經拼圖：策略3 M1B-M2 卡 ＋ ⚔️ 三環 D 徽章。"""
    import src.services.allocation_service as AS
    import src.ui.tabs.macro.section_chips as SC
    fake = _FakeST({"m1b_m2_info": info})
    mp.setattr(mod, "st", fake)
    mp.setattr(AS, "apply_vix_veto", lambda *a, **k: None)
    mp.setattr(AS, "apply_ring_gate", lambda *a, **k: None)
    mp.setattr(AS, "register_conflict", lambda *a, **k: None)
    mp.setattr(AS, "get_allocation", lambda *a, **k: types.SimpleNamespace(
        is_loaded=False, final_hi=None))
    mp.setattr(SC, "read_v4_macro_veto", lambda *a, **k: None)
    exc = None
    try:
        mod.render_section_mid(False, {}, {}, {})
    except Exception as e:  # noqa: BLE001 —— 修前 "n/a" 就是要抓到這個
        exc = e
    return {"exc": exc, "out": fake.out}


_RUN = {"news": _run_news, "op": _run_op, "state": _run_state, "mid": _run_mid}


def _exc(r):
    e = r["exc"]
    return None if e is None else (type(e).__name__, str(e))


def _view(ek: str, r: dict):
    """「完整輸出」：畫面記錄 ＋ 該出口送進 L3／Gemini 的東西（比對用）。"""
    if ek == "news":
        return (_exc(r), r["n_prompts"], r["prompt"], r["numbers"], r["locked"], r["out"])
    if ek == "op":
        return (_exc(r), r["m1b_diff"], r["out"])
    if ek == "state":
        return (_exc(r), r["pivots"], r["out"])
    return (_exc(r), r["out"])


def _text(r: dict) -> str:
    return "\n".join([t for _, t in r["out"]] + [r.get("prompt") or ""])


def _m1b_lines(prompt: str) -> list[str]:
    return [ln for ln in (prompt or "").splitlines() if ln.startswith("• M1B=")]


# ══════════════════════════════════════════════════════════════════════════
# 測資
# ══════════════════════════════════════════════════════════════════════════
_NAN, _INF = float("nan"), float("inf")

#: 缺值情境（修後一律：不拋、完整輸出 ＝ 空的完整輸出）
_MISSING = {
    # M2 缺
    "m2_key_absent": {"m1b_yoy": 4.2, "source": "CBC-tier1"},
    "m2_none": {"m1b_yoy": 4.2, "m2_yoy": None, "source": "CBC-tier1"},
    # M1B 缺（另一個 5.0 → 只拿掉 M1B 時 spread＝−5 會被扣分並貼「資金緊縮」）
    "m1b_key_absent": {"m2_yoy": 5.0, "source": "FRED"},
    "m1b_none": {"m1b_yoy": None, "m2_yoy": 5.0, "source": "CBC-tier1"},
    "both_none": {"m1b_yoy": None, "m2_yoy": None, "source": "CBC-tier1"},
    "gap_only": {"gap": 1.5, "source": "CBC-tier1"},
    # NaN
    "both_nan": {"m1b_yoy": _NAN, "m2_yoy": _NAN, "source": "CBC-tier1"},
    "m1b_nan": {"m1b_yoy": np.nan, "m2_yoy": 2.0, "source": "CBC-tier1"},
    "m2_nan": {"m1b_yoy": 4.2, "m2_yoy": np.float64("nan"), "source": "FRED"},
    # ±inf
    "m1b_pos_inf": {"m1b_yoy": _INF, "m2_yoy": 2.0, "source": "CBC-tier1"},
    "m2_pos_inf": {"m1b_yoy": 4.2, "m2_yoy": _INF, "source": "CBC-tier1"},
    "m1b_neg_inf": {"m1b_yoy": -_INF, "m2_yoy": 2.0, "source": "CBC-tier1"},
    "m2_neg_inf": {"m1b_yoy": 4.2, "m2_yoy": -_INF, "source": "CBC-tier1"},
    # 代理源（Tier 3）但缺數字
    "proxy_m2_absent": {"m1b_yoy": 4.2, "source": M1B_PROXY_SOURCE_LABEL},
    "proxy_both_none": {"m1b_yoy": None, "m2_yoy": None, "source": M1B_PROXY_SOURCE_LABEL_RAW},
    "proxy_flag_m1b_nan": {"m1b_yoy": _NAN, "m2_yoy": 2.0, "source": "CBC-tier1",
                           "is_proxy_tier": True},
    # 非數值（沿用 `_finite_yoy` 既有語意：一律算缺）
    "str_m2": {"m1b_yoy": 4.2, "m2_yoy": "n/a", "source": "CBC-tier1"},
    "numstr_m2": {"m1b_yoy": 4.2, "m2_yoy": "2.0", "source": "CBC-tier1"},
    "bool_m2": {"m1b_yoy": 4.2, "m2_yoy": True, "source": "CBC-tier1"},
}
_M2_SIDE = {"m2_key_absent", "m2_none", "m2_nan", "m2_pos_inf", "m2_neg_inf",
            "proxy_m2_absent", "str_m2", "numstr_m2", "bool_m2"}
_M1B_SIDE = {"m1b_key_absent", "m1b_none", "m1b_nan", "m1b_pos_inf", "m1b_neg_inf",
             "proxy_flag_m1b_nan"}
_NON_FINITE = {"both_nan", "m1b_nan", "m2_nan", "m1b_pos_inf", "m2_pos_inf",
               "m1b_neg_inf", "m2_neg_inf", "proxy_flag_m1b_nan"}
_NON_NUMERIC = {"str_m2", "numstr_m2", "bool_m2"}
_PROXY_MISSING = {"proxy_m2_absent", "proxy_both_none", "proxy_flag_m1b_nan"}

#: 非缺值的來源形狀：非代理 ×3、代理 ×4（L0 `is_m1b_m2_proxy` 的兩個 label ＋ 兩個布林旗標）
_SOURCES = {
    "CBC-tier1": {"source": "CBC-tier1"},
    "FRED": {"source": "FRED"},
    "no_source": {},
    "proxy_label": {"source": M1B_PROXY_SOURCE_LABEL},
    "proxy_label_raw": {"source": M1B_PROXY_SOURCE_LABEL_RAW},
    "proxy_flag_is_proxy_tier": {"source": "CBC-tier1", "is_proxy_tier": True},
    "proxy_flag_is_proxy": {"source": "CBC-tier1", "is_proxy": True},
}
#: (m1b_yoy, m2_yoy) —— 涵蓋 §八 三段（≥1／≥0／<0）、§二 兩段（>0／<−1）、L3 門檻兩側
_GAPS = {
    "strong": (5.1, 2.0),              # +3.10
    "gap_one": (3.0, 2.0),             # +1.00（§八 ≥1.0 邊界）
    "mild": (3.0, 2.5),                # +0.50
    "tiny_pos": (2.001, 2.0),          # 顯示 +0.00 但 >0
    "zero": (2.0, 2.0),                # 0.00
    "near_zero": (1.0, 2.0),           # −1.00（§二 `< -1` 邊界：不成立）
    "minus2": (1.0, 3.0),              # −2.00
    "negative": (1.2, 5.0),            # −3.80
    "both_negative": (-1.5, -3.0),     # 兩者皆負、差額 +1.50
    "m2_is_zero": (1.5, 0.0),          # 真的 0.0% 不是缺值
    "m1b_is_zero": (0.0, 0.8),         # 真的 0.0% 不是缺值
    "ints": (5, 2),                    # int 型別
    "np_float64": (np.float64(4.25), np.float64(1.5)),
    "large": (123.456, -78.9),
    "neg_zero_m2": (1.5, -0.0),        # 負零只在一邊 → 逐字相同
    "neg_zero_m1b": (-0.0, 0.8),
    # 以下 3 組為驗收組非阻擋 1 補的 golden 輸入：差額要到小數第 2 位才看得出差別，
    # 「差額四捨五入少一位」這類改動才會露出來（golden 值見下方 `_GOLDEN_*` 的補充段）。
    "gap_2dp_713": (9.33, 2.2),        # +7.13（§八 ≥1 那段）
    "gap_2dp_pos004": (2.04, 2.0),     # +0.04（§八 0~1 那段、§二 黃金交叉）
    "gap_2dp_neg104": (1.0, 2.04),     # −1.04（§二 `< -1` 剛成立 → 死亡交叉）
}


def _info(gap: str, source: str) -> dict:
    m1b, m2 = _GAPS[gap]
    return {"m1b_yoy": m1b, "m2_yoy": m2, **_SOURCES[source]}


# ══════════════════════════════════════════════════════════════════════════
# B 的契約（本尊跑＝測試；還原體／突變體跑＝證明測試抓得到）
# ══════════════════════════════════════════════════════════════════════════
def _check_missing(ek: str, mod, info, mp) -> None:
    got = _RUN[ek](mod, info, mp)
    assert got["exc"] is None, f"缺值不得拋錯：{got['exc']!r}"
    empty = _RUN[ek](mod, {}, mp)
    assert empty["exc"] is None, f"空值基準本身就拋錯：{empty['exc']!r}"
    text = _text(got)
    assert NOTE not in text, "沒有數字就不得出現代理註記"
    if ek == "news":
        assert got["n_prompts"] == 1, "Gemini 替身沒被呼叫到 —— 裁決流程沒跑完"
        assert _m1b_lines(got["prompt"]) == [], "缺值不得送 M1B 那一行"
        assert "M2=0.0%" not in got["prompt"], "缺 M2 不得以 0.0% 送進 prompt"
        assert len(got["numbers"]) == 1, "規則引擎替身應恰被呼叫一次"
        nums = got["numbers"][0]
        assert nums["M1B_YoY_pct"] is None and nums["M2_YoY_pct"] is None, (
            f"規則引擎必須收到兩個 None，實得 M1B={nums['M1B_YoY_pct']!r} "
            f"M2={nums['M2_YoY_pct']!r}")
        assert "資金緊縮" not in str(got["locked"])
    elif ek == "op":
        assert got["m1b_diff"] == [None], f"個股建議的 m1b_diff 必須是 None，實得 {got['m1b_diff']!r}"
        assert "【景氣環境】" not in text
    elif ek == "state":
        assert not [p for p in got["pivots"] if str(p[0]).startswith("M1B")], "不得出 M1B 交叉訊號"
    else:
        assert _MID_PENDING in text and _MID_D_UNKNOWN in text
    assert _view(ek, got) == _view(ek, empty), "完整輸出應＝ m1b_m2_info 為空時的完整輸出"


def _red_cases(ek: str, mod, mp, cases=None) -> set[str]:
    red = set()
    for name in (cases or _MISSING):
        try:
            _check_missing(ek, mod, _MISSING[name], mp)
        except AssertionError:
            red.add(name)
    return red


# ══════════════════════════════════════════════════════════════════════════
# A：L3 實跑 —— 兩個 None 走既有缺值路徑（本批 L3 零行，這裡只釘它的行為）
# ══════════════════════════════════════════════════════════════════════════
_L3_BASE = {"VIX_Index": 17.0, "ISM_PMI_or_OECD_CLI": 51.0, "PMI_Prev_Month": 50.5,
            "BIAS240_pct": 5.0, "PCR": 1.0}


class TestL3MissingPath:

    @pytest.mark.parametrize("base", [{}, _L3_BASE], ids=["empty_base", "scenario_base"])
    def test_both_none_is_neutral_no_add_no_deduct(self, base):
        from src.services.macro_state_locker import calculate_system_state as css
        both_none = css({**base, "M1B_YoY_pct": None, "M2_YoY_pct": None})
        assert both_none == css(dict(base)), "兩個 None 應＝兩個鍵都不在"
        # spread = 0 的真值 → 資金項不加不扣：兩個 None 的結果必須與它相同
        assert both_none == css({**base, "M1B_YoY_pct": 2.0, "M2_YoY_pct": 2.0})
        assert "資金緊縮" not in both_none["Macro_Phase"]

    @pytest.mark.parametrize("base", [{}, _L3_BASE], ids=["empty_base", "scenario_base"])
    def test_clearing_only_one_side_is_visible(self, base):
        """前提守衛：本檔的測資若「只清一個值」，引擎結果必然不同 —— 否則突變 G 抓不到。"""
        from src.services.macro_state_locker import calculate_system_state as css
        both_none = css({**base, "M1B_YoY_pct": None, "M2_YoY_pct": None})
        only_m2_cleared = css({**base, "M1B_YoY_pct": 4.2, "M2_YoY_pct": None})
        only_m1b_cleared = css({**base, "M1B_YoY_pct": None, "M2_YoY_pct": 5.0})
        assert only_m2_cleared["exposure_limit_pct"] > both_none["exposure_limit_pct"]
        assert "資金緊縮" in only_m1b_cleared["Macro_Phase"]
        assert only_m1b_cleared["exposure_limit_pct"] < both_none["exposure_limit_pct"]

    @pytest.mark.parametrize("info", [None, {}, {"m1b_yoy": 4.2, "source": M1B_PROXY_SOURCE_LABEL}],
                             ids=["no_info", "empty_info", "proxy_info"])
    def test_generate_ai_comment_none_diff_has_no_m1b_sentence(self, info):
        from src.services.app_ai_service import generate_ai_comment as gac
        out = gac({"m1b_diff": None, "m1b_m2_info": info})
        assert "【景氣環境】" not in out and NOTE not in out
        assert out == gac({"m1b_diff": 0}), "None 與 0 應走 L3 同一條路徑"


# ══════════════════════════════════════════════════════════════════════════
# B：修後缺值契約
# ══════════════════════════════════════════════════════════════════════════
class TestMissingContract:

    @pytest.mark.parametrize("name", sorted(_MISSING))
    @pytest.mark.parametrize("ek", _EXITS)
    def test_no_fabrication_and_looks_like_empty(self, ek, name, monkeypatch):
        _check_missing(ek, _mod(ek), _MISSING[name], monkeypatch)

    @pytest.mark.parametrize("ek", _EXITS)
    def test_empty_dict_and_none_look_the_same(self, ek, monkeypatch):
        a = _RUN[ek](_mod(ek), {}, monkeypatch)
        b = _RUN[ek](_mod(ek), None, monkeypatch)
        assert a["exc"] is None and b["exc"] is None
        assert _view(ek, a) == _view(ek, b)

    @pytest.mark.parametrize("name", ["m2_key_absent", "m2_none", "proxy_m2_absent"])
    def test_news_prompt_no_zero_m2_and_no_typeerror(self, name, monkeypatch):
        """§十一 點名的兩個病：缺 M2 鍵送「M2=0.0%」、M2 為 None 拋 TypeError。"""
        got = _run_news(_mod("news"), _MISSING[name], monkeypatch)
        assert got["exc"] is None
        assert "M2=0.0%" not in got["prompt"] and _m1b_lines(got["prompt"]) == []
        assert got["numbers"][0]["M1B_YoY_pct"] is None
        assert got["numbers"][0]["M2_YoY_pct"] is None

    def test_state_liquidity_family_is_unevaluated_not_neutral(self, monkeypatch):
        """§二：沒有數字＝「未評估」（排除於分母外），不是「中性」。"""
        from src.compute.macro.macro_helpers import PIVOT_FAMILIES
        name = dict(PIVOT_FAMILIES)["liquidity"]
        text = _text(_run_state(_mod("state"), _MISSING["m2_nan"], monkeypatch))
        assert f"{name}：未評估" in text and f"{name}：中性" not in text

    def test_state_none_value_no_longer_crashes(self, monkeypatch):
        assert _run_state(_mod("state"), _MISSING["m1b_none"], monkeypatch)["exc"] is None


# ══════════════════════════════════════════════════════════════════════════
# C：修前確實出事（反向對照；否則 B 不證明什麼）
# ══════════════════════════════════════════════════════════════════════════
#: 修前（da4eb94）以同一個 harness 實跑擷取的「出事集合」（拋錯，或完整輸出≠空的樣子）。
#: 另各出口「本來就沒事」的缺值情境，修後照樣沒事（B 已涵蓋）。
_PRE_FIX_BROKEN = {
    # 兩個都缺時修前恰好沒事（兩個都送 None）；其餘都出事
    "news": set(_MISSING) - {"both_none", "gap_only", "proxy_both_none"},
    # 修前「沒有數字也送 0」本身就違反契約（m1b_diff 必須是 None）→ 全部
    "op": set(_MISSING),
    # 代理源整段被跳過 → 修前沒事；其餘（含 gap_only：登記成「中性」）都出事
    "state": set(_MISSING) - _PROXY_MISSING,
    # 外層已判 `is not None` → 只有 NaN／±inf／非數值出事
    "mid": _NON_FINITE | _NON_NUMERIC,
}


class TestPreFixWasBroken:

    @pytest.mark.parametrize("ek", _EXITS)
    def test_pre_fix_broken_set(self, ek, pre_fix, monkeypatch):
        assert _red_cases(ek, pre_fix[ek], monkeypatch) == _PRE_FIX_BROKEN[ek]

    @pytest.mark.parametrize("ek", _EXITS)
    def test_real_module_is_green(self, ek, monkeypatch):
        assert _red_cases(ek, _mod(ek), monkeypatch) == set()

    def test_pre_fix_news_fabricated_m2_zero_and_bull(self, pre_fix, monkeypatch):
        """修前實況（da4eb94 實跑擷取）：缺 M2 → 「M2=0.0%」且引擎升成多頭。"""
        got = _run_news(pre_fix["news"], _MISSING["m2_key_absent"], monkeypatch)
        assert _m1b_lines(got["prompt"])[0].startswith("• M1B=4.2%  M2=0.0%  差額=+4.20%")
        assert got["locked"][0]["market_regime"] == "多頭"
        none = _run_news(pre_fix["news"], _MISSING["m2_none"], monkeypatch)
        assert isinstance(none["exc"], TypeError)

    def test_pre_fix_news_m1b_missing_tags_funding_squeeze(self, pre_fix, monkeypatch):
        got = _run_news(pre_fix["news"], _MISSING["m1b_key_absent"], monkeypatch)
        assert "資金緊縮" in got["locked"][0]["Macro_Phase"]


# ══════════════════════════════════════════════════════════════════════════
# D：非缺值 —— 完整輸出與還原體逐字相同（正常 × 代理）
# ══════════════════════════════════════════════════════════════════════════
class TestNonMissingUnchanged:

    @pytest.mark.parametrize("gap", sorted(_GAPS))
    @pytest.mark.parametrize("ek", _EXITS)
    def test_full_output_identical_to_pre_fix(self, ek, gap, pre_fix, monkeypatch):
        for source in _SOURCES:
            info = _info(gap, source)
            now = _RUN[ek](_mod(ek), info, monkeypatch)
            pre = _RUN[ek](pre_fix[ek], info, monkeypatch)
            assert now["exc"] is None and pre["exc"] is None
            assert _view(ek, now) == _view(ek, pre), f"{ek}/{gap}/{source}：完整輸出與修前不同"

    @pytest.mark.parametrize("ek", _EXITS)
    def test_empty_state_identical_to_pre_fix(self, ek, pre_fix, monkeypatch):
        """沒有 m1b_m2_info：畫面／prompt 與修前相同（個股建議 `m1b_diff` 由 0 改送 None，
        L3 對兩者走同一條路徑 —— 文案逐字相同，由 `out` 比對證明）。"""
        now = _RUN[ek](_mod(ek), {}, monkeypatch)
        pre = _RUN[ek](pre_fix[ek], {}, monkeypatch)
        if ek == "op":
            assert pre["m1b_diff"] == [0] and now["m1b_diff"] == [None]
            assert now["out"] == pre["out"]
        else:
            assert _view(ek, now) == _view(ek, pre)


#: 修前（da4eb94）實跑擷取的關鍵字串（防「兩邊一起錯」）。
#: ⚠️ 為什麼 D 類之外還要 golden：D 類的還原體是由「現行檔」反向替換 `_REVERT` 那幾段產生，
#:    替換片段以外的改動（例：§八 `_gap8` 四捨五入改一位、§二 `> 0` 改 `>= 0`）會同時出現在
#:    本尊與還原體 → D 類看不到。golden 取自修前實跑、與現行檔無關，才抓得到（見 G 類
#:    `test_source_level_mutant_is_caught_by_golden`）。
#: 取得方式：
#:  · 每個 dict 的前段（strong／negative／near_zero／m2_is_zero／both_negative）：本批實作期
#:    在尚未改動的 da4eb94 工作樹上，以同構 harness（本檔 `_run_*` 的前身，只在批次暫存區、
#:    未入庫）實跑擷取。
#:  · 標「驗收組非阻擋 1 補」的後段：2026-09-29 在本 worktree `git checkout --detach da4eb94`
#:   （修前樹，本檔尚不存在）後，匯入本檔 4043cb7 版的副本、呼叫其 `_run_mid`／`_run_state`／
#:    `_run_news`／`_run_op` 實跑擷取；同一組輸入切回 4043cb7 重跑，32 組輸出逐字相同。
_GOLDEN_NEWS = {
    ("strong", "CBC-tier1"): "• M1B=5.1%  M2=2.0%  差額=+3.10%（正=資金行情啟動；",
    ("strong", "proxy_label"): f"• M1B=5.1%  M2=2.0%  差額=+3.10%{NOTE}（正=資金行情啟動；",
    ("negative", "CBC-tier1"): "• M1B=1.2%  M2=5.0%  差額=-3.80%（正=資金行情啟動；",
    ("m2_is_zero", "CBC-tier1"): "• M1B=1.5%  M2=0.0%  差額=+1.50%（正=資金行情啟動；",
    ("both_negative", "proxy_label"): f"• M1B=-1.5%  M2=-3.0%  差額=+1.50%{NOTE}（正=資金行情啟動；",
    # ── 驗收組非阻擋 1 補（da4eb94 樹實跑）──
    ("gap_2dp_713", "CBC-tier1"): "• M1B=9.3%  M2=2.2%  差額=+7.13%（正=資金行情啟動；",
    ("gap_2dp_neg104", "proxy_label"): f"• M1B=1.0%  M2=2.0%  差額=-1.04%{NOTE}（正=資金行情啟動；",
    ("zero", "CBC-tier1"): "• M1B=2.0%  M2=2.0%  差額=+0.00%（正=資金行情啟動；",
}
_GOLDEN_OP = {
    ("strong", "CBC-tier1"): "• 🌐 【景氣環境】M1B-M2為正且強勁，資金行情啟動中，可積極持股。",
    ("strong", "proxy_label"): f"• 🌐 【景氣環境】M1B-M2{NOTE}為正且強勁，資金行情啟動中，可積極持股。",
    ("negative", "CBC-tier1"): "• 🌐 【景氣環境】M1B-M2為負，目前處於資金縮減期。",
    # ── 驗收組非阻擋 1 補（da4eb94 樹實跑）──
    ("gap_2dp_713", "CBC-tier1"): "• 🌐 【景氣環境】M1B-M2為正且強勁，資金行情啟動中，可積極持股。",
    ("gap_2dp_neg104", "CBC-tier1"): "• 🌐 【景氣環境】M1B-M2為負，目前處於資金縮減期。",
}
_GOLDEN_STATE = {
    ("strong", "CBC-tier1"): [("M1B>M2 黃金交叉", "✅", "#22c55e",
                               "M1B(5.1%) > M2(2.0%) → 資金由定存轉入股市，長線起漲徵兆")],
    ("negative", "CBC-tier1"): [("M1B<M2 死亡交叉", "❌", "#ef4444",
                                 "M1B(1.2%) < M2(5.0%) → 資金撤離股市，長線起跌警示")],
    ("near_zero", "CBC-tier1"): [],
    ("strong", "proxy_label"): [],      # 代理值不產生交叉訊號（v19.183 D2，照舊）
    # ── 驗收組非阻擋 1 補（da4eb94 樹實跑）──
    # 零差額：`_diff > 0` 是嚴格大於 → M1B＝M2 不出任何交叉（改成 `>= 0` 會多出黃金交叉）
    ("zero", "CBC-tier1"): [],
    # 2 位小數差額：+0.04 剛好 > 0、−1.04 剛好 < −1（差額若被四捨五入到 1 位，兩條都會消失）
    ("gap_2dp_pos004", "CBC-tier1"): [("M1B>M2 黃金交叉", "✅", "#22c55e",
                                       "M1B(2.0%) > M2(2.0%) → 資金由定存轉入股市，長線起漲徵兆")],
    ("gap_2dp_neg104", "CBC-tier1"): [("M1B<M2 死亡交叉", "❌", "#ef4444",
                                       "M1B(1.0%) < M2(2.0%) → 資金撤離股市，長線起跌警示")],
    ("gap_2dp_713", "CBC-tier1"): [("M1B>M2 黃金交叉", "✅", "#22c55e",
                                    "M1B(9.3%) > M2(2.2%) → 資金由定存轉入股市，長線起漲徵兆")],
}
_GOLDEN_MID = {
    ("strong", "CBC-tier1"): ("M1B-M2 Gap = +3.10%（黃金交叉·熱錢狂潮）",
                              "🔥 資金動能強勁（M1B=5.1% > M2=2.0%），熱錢湧入股市，積極作多強勢股。",
                              "D M1B-M2=+3.10%"),
    ("strong", "proxy_label"): (f"M1B-M2 Gap = +3.10%{NOTE}（黃金交叉·熱錢狂潮）",
                                "🔥 資金動能強勁（M1B=5.1% > M2=2.0%），熱錢湧入股市，積極作多強勢股。",
                                f"D M1B-M2=+3.10%{NOTE}"),
    ("negative", "CBC-tier1"): ("M1B-M2 Gap = -3.80%（死亡交叉·資金退潮）",
                                "📉 資金動能趨緩（M1B=1.2% < M2=5.0%），資金轉向定存或匯出，減碼等待訊號確認。",
                                "D M1B-M2=-3.80%"),
    # ── 驗收組非阻擋 1 補（da4eb94 樹實跑）：差額到小數第 2 位（策略3 卡與三環 D 徽章各一個數字）──
    ("gap_2dp_713", "CBC-tier1"): ("M1B-M2 Gap = +7.13%（黃金交叉·熱錢狂潮）",
                                   "🔥 資金動能強勁（M1B=9.3% > M2=2.2%），熱錢湧入股市，積極作多強勢股。",
                                   "D M1B-M2=+7.13%"),
    ("gap_2dp_713", "proxy_label"): (f"M1B-M2 Gap = +7.13%{NOTE}（黃金交叉·熱錢狂潮）",
                                     "🔥 資金動能強勁（M1B=9.3% > M2=2.2%），熱錢湧入股市，積極作多強勢股。",
                                     f"D M1B-M2=+7.13%{NOTE}"),
    ("gap_2dp_pos004", "CBC-tier1"): ("M1B-M2 Gap = +0.04%（資金溫和·中性擴張）",
                                      "💧 資金動能溫和（M1B=2.0% ≥ M2=2.0%），無失血風險，回歸個股基本面與籌碼面操作。",
                                      "D M1B-M2=+0.04%"),
    ("gap_2dp_neg104", "CBC-tier1"): ("M1B-M2 Gap = -1.04%（死亡交叉·資金退潮）",
                                      "📉 資金動能趨緩（M1B=1.0% < M2=2.0%），資金轉向定存或匯出，減碼等待訊號確認。",
                                      "D M1B-M2=-1.04%"),
    ("zero", "CBC-tier1"): ("M1B-M2 Gap = +0.00%（資金溫和·中性擴張）",
                            "💧 資金動能溫和（M1B=2.0% ≥ M2=2.0%），無失血風險，回歸個股基本面與籌碼面操作。",
                            "D M1B-M2=+0.00%"),
}
_D_SPAN = re.compile(r'<span style="[^"]*">(D M1B-M2[^<]*)</span>')


def _golden_news(mod, mp) -> list:
    bad = []
    for (gap, source), want in _GOLDEN_NEWS.items():
        got = _run_news(mod, _info(gap, source), mp)
        lines = _m1b_lines(got["prompt"])
        m1b, m2 = _GAPS[gap]
        if not (len(lines) == 1 and lines[0].startswith(want)
                and got["numbers"][0]["M1B_YoY_pct"] == m1b
                and got["numbers"][0]["M2_YoY_pct"] == m2):
            bad.append((gap, source))
    return bad


def _golden_op(mod, mp) -> list:
    bad = []
    for (gap, source), want in _GOLDEN_OP.items():
        got = _run_op(mod, _info(gap, source), mp)
        m1b, m2 = _GAPS[gap]
        if not (got["m1b_diff"] == [m1b - m2] and want in _text(got)):
            bad.append((gap, source))
    return bad


def _golden_state(mod, mp) -> list:
    return [(gap, source) for (gap, source), want in _GOLDEN_STATE.items()
            if _run_state(mod, _info(gap, source), mp)["pivots"] != want]


def _golden_mid(mod, mp) -> list:
    bad = []
    for (gap, source), (indicator, conclusion, d_text) in _GOLDEN_MID.items():
        got = _run_mid(mod, _info(gap, source), mp)
        text = _text(got)
        d = [m.group(1) for m in _D_SPAN.finditer(text)]
        if not (indicator in text and conclusion in text and d == [d_text]):
            bad.append((gap, source))
    return bad


_GOLDEN = {"news": _golden_news, "op": _golden_op, "state": _golden_state, "mid": _golden_mid}


class TestNonMissingGolden:

    @pytest.mark.parametrize("ek", _EXITS)
    def test_key_strings_match_pre_fix_capture(self, ek, monkeypatch):
        assert _GOLDEN[ek](_mod(ek), monkeypatch) == []


class TestNegativeZeroCorner:
    """D-2：唯一的非缺值差異 —— §十一 prompt 在 M1B、M2 **皆為負零**時的差額零號。

    修前差額是 `float(m1b) - float(m2 or 0)`：`or 0` 把 −0.0 換成 +0 → `-0.0 - 0.0 = -0.0`
    →「差額=-0.00%」。修後兩個已驗證值直接相減 `-0.0 - (-0.0) = +0.0` →「差額=+0.00%」
    （與 §七 `_m1b_v - _m2_v`、§八 `float(m1b) - float(m2)` 同一個結果）。
    只差這一個字元；規則引擎輸入、鎖定狀態、畫面其餘部分逐字相同。
    """

    @pytest.mark.parametrize("source", sorted(_SOURCES))
    def test_only_the_sign_of_zero_differs(self, source, pre_fix, monkeypatch):
        info = {"m1b_yoy": -0.0, "m2_yoy": -0.0, **_SOURCES[source]}
        now = _run_news(_mod("news"), info, monkeypatch)
        pre = _run_news(pre_fix["news"], info, monkeypatch)
        assert now["exc"] is None and pre["exc"] is None
        assert (now["numbers"], now["locked"], now["out"]) == (pre["numbers"], pre["locked"], pre["out"])
        (ln_now,), (ln_pre,) = _m1b_lines(now["prompt"]), _m1b_lines(pre["prompt"])
        assert "差額=-0.00%" in ln_pre and "差額=+0.00%" in ln_now
        assert ln_now.replace("差額=+0.00%", "差額=-0.00%") == ln_pre
        assert now["prompt"].replace(ln_now, ln_pre) == pre["prompt"]

    @pytest.mark.parametrize("ek", ["op", "state", "mid"])
    def test_other_exits_identical(self, ek, pre_fix, monkeypatch):
        for source in _SOURCES:
            info = {"m1b_yoy": -0.0, "m2_yoy": -0.0, **_SOURCES[source]}
            assert _view(ek, _RUN[ek](_mod(ek), info, monkeypatch)) == \
                _view(ek, _RUN[ek](pre_fix[ek], info, monkeypatch))


# ══════════════════════════════════════════════════════════════════════════
# E：不複製判斷邏輯 —— 4 檔都從 section_long 取 `_finite_yoy`
# ══════════════════════════════════════════════════════════════════════════
class TestSharedFiniteYoy:
    """`_finite_yoy` 的位置（section_long）目前被兩處綁住 —— 日後若要搬到共用模組，兩處要一起改：

    1. 本類：import 來源與 `__module__` 都指定 section_long。
    2. #746 的 tests/test_dl_f1_s24_m2_missing.py：`_REVERT_PAIRS` 定位的是 `render_section_long`
       裡的**呼叫點**（搬移不受影響）；但 `_MUTANTS` 的 3 個 helper 突變與
       `test_non_missing_mutant_breaks_golden` 的 zero_as_missing，定位字串是 `_finite_yoy`
       **函式本體**的行、比對對象是 section_long.py 原文（搬走即「突變點不唯一或已不存在」）。
    """

    @pytest.mark.parametrize("ek", _EXITS)
    def test_imported_from_section_long_not_redefined(self, ek):
        tree = ast.parse(_source(ek))
        imports = [n for n in ast.walk(tree)
                   if isinstance(n, ast.ImportFrom) and n.module == _LONG_MOD
                   and any(a.name == "_finite_yoy" and a.asname is None for a in n.names)]
        assert len(imports) == 1, "應恰有一行 `from src.ui.tabs.macro.section_long import _finite_yoy`"
        defs = [n.name for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and n.name == "_finite_yoy"]
        assert defs == [], "不得在本檔另寫一份 `_finite_yoy`"
        names = {getattr(n, "attr", None) or getattr(n, "id", None) for n in ast.walk(tree)
                 if isinstance(n, (ast.Attribute, ast.Name))}
        assert not names & {"isfinite", "isnan", "isinf"}, "不得另寫有限值判斷（一律走 _finite_yoy）"

    @pytest.mark.parametrize("ek", _EXITS)
    def test_runtime_object_is_the_section_long_function(self, ek):
        f = _mod(ek)._finite_yoy
        assert (f.__module__, f.__qualname__) == (_LONG_MOD, "_finite_yoy")


# ══════════════════════════════════════════════════════════════════════════
# F：K1 —— 不新增、不改寫任何字
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


class TestK1NoNewCopy:

    @pytest.mark.parametrize("ek", _EXITS)
    def test_string_literals_identical_to_pre_fix(self, ek):
        now = _str_literals(_source(ek))
        pre = _str_literals(_revert_source(ek))
        assert now - pre == set(), f"新增了本檔原本沒有的字面：{sorted(now - pre)}"
        assert pre - now == set(), f"刪掉了既有字面：{sorted(pre - now)}"


# ══════════════════════════════════════════════════════════════════════════
# G：突變 —— 每一個都要讓新測試轉紅
# ══════════════════════════════════════════════════════════════════════════
#: 名稱 → (出口, 替換組, 至少要轉紅的缺值情境)
_MUTANTS = {
    # ── §十一 ────────────────────────────────────────────────
    # 把守衛拿掉：改回原始 `.get`（兩個一起清的那段還在）→ NaN／±inf／非數值照樣送
    "news_guard_removed": ("news", (
        ("_m1b_ai = _finite_yoy(_mi_d, 'm1b_yoy')", "_m1b_ai = _mi_d.get('m1b_yoy')"),
        ("_m2_ai  = _finite_yoy(_mi_d, 'm2_yoy')", "_m2_ai  = _mi_d.get('m2_yoy')"),
    ), _NON_FINITE | _NON_NUMERIC),
    # 改成只清一個值（缺哪個清哪個）：拿掉「兩個一起當缺」
    "news_only_clear_the_missing_one": ("news", (
        ("                if _m1b_ai is None or _m2_ai is None:\n"
         "                    _m1b_ai = _m2_ai = None\n", ""),
    ), _M2_SIDE | _M1B_SIDE),
    # 只清 M1B（M2 照送）→ 缺 M1B 時 spread＝−M2（test_strong_scenario_is_sensitive_to_m1b_only_removal 那一型）
    "news_clear_only_m1b": ("news", (
        ("                    _m1b_ai = _m2_ai = None\n", "                    _m1b_ai = None\n"),
    ), _M1B_SIDE),
    # prompt 那一行退回讀原始 dict（`or 0`）；引擎輸入仍是修後
    "news_prompt_reverted": ("news", _REVERT["news"][3:5],
                             {"m2_key_absent", "m2_none", "proxy_m2_absent"}),
    # 引擎輸入退回原始 dict；prompt 仍是修後
    "news_numbers_reverted": ("news", _REVERT["news"][2:3], _M2_SIDE | _M1B_SIDE),
    # ── 個股建議 ─────────────────────────────────────────────
    # 把守衛拿掉：整段退回 `.get(..., 0)` 相減
    "op_guard_removed": ("op", _REVERT["op"][1:2], set(_MISSING)),
    # 只驗 M1B，M2 缺就當 0
    "op_only_m1b_checked": ("op", (
        ("        _m1b_diff_g = (_m1b_g - _m2_g\n"
         "                       if _m1b_g is not None and _m2_g is not None else None)\n",
         "        _m1b_diff_g = (_m1b_g - (_m2_g or 0)\n"
         "                       if _m1b_g is not None else None)\n"),
    ), _M2_SIDE),
    # 有限值判斷拿掉（改回原始 `.get`）
    "op_finite_dropped": ("op", (
        ("_m1b_g = _finite_yoy(_m1b_top_g, 'm1b_yoy')", "_m1b_g = (_m1b_top_g or {}).get('m1b_yoy')"),
        ("_m2_g = _finite_yoy(_m1b_top_g, 'm2_yoy')", "_m2_g = (_m1b_top_g or {}).get('m2_yoy')"),
    ), _NON_FINITE | _NON_NUMERIC),
    # ── §二 ──────────────────────────────────────────────────
    "state_guard_removed": ("state", _REVERT["state"][1:2], set(_MISSING) - _PROXY_MISSING),
    # 只驗 M1B → 缺 M2 時 `x - None` 炸掉 §二
    "state_only_m1b_checked": ("state", (
        ("                and _m1b_y is not None and _m2_y is not None):\n",
         "                and _m1b_y is not None):\n"),
    ), _M2_SIDE - _PROXY_MISSING),
    # 資金群登記移回有限值閘門外（沒有數字也登記 →「資金：中性」）
    "state_registration_outside_gate": ("state", (
        ("        if (_m1b2 and not is_m1b_m2_proxy(_m1b2)\n",
         "        if _m1b2 and not is_m1b_m2_proxy(_m1b2):\n"
         "            _fam_ok.add('liquidity')\n"
         "        if (_m1b2 and not is_m1b_m2_proxy(_m1b2)\n"),
    ), set(_MISSING) - _PROXY_MISSING),
    "state_finite_dropped": ("state", (
        ("_m1b_y = _finite_yoy(_m1b2, 'm1b_yoy')", "_m1b_y = (_m1b2 or {}).get('m1b_yoy')"),
        ("_m2_y  = _finite_yoy(_m1b2, 'm2_yoy')", "_m2_y  = (_m1b2 or {}).get('m2_yoy')"),
    ), (_NON_FINITE | _NON_NUMERIC) - _PROXY_MISSING),
    # ── §八 ──────────────────────────────────────────────────
    # 把守衛拿掉：退回只判 `is not None`（策略3 與 D 徽章共用的那組值）
    "mid_guard_back_to_is_not_none": ("mid", (
        ("_m1b8_v = _finite_yoy(_m1b8_info, 'm1b_yoy')", "_m1b8_v = (_m1b8_info or {}).get('m1b_yoy')"),
        ("_m2b8_v = _finite_yoy(_m1b8_info, 'm2_yoy')", "_m2b8_v = (_m1b8_info or {}).get('m2_yoy')"),
    ), _NON_FINITE | _NON_NUMERIC),
    # 策略3 只驗 M1B → 缺 M2 時 `float(None)` 炸掉 §八
    "mid_only_m1b_checked": ("mid", (
        ("        if _m1b8_v is not None and _m2b8_v is not None:\n"
         "            _m1b8 = float(_m1b8_v)\n",
         "        if _m1b8_v is not None:\n"
         "            _m1b8 = float(_m1b8_v)\n"),
    ), _M2_SIDE),
    # 三環 D 徽章退回讀原始 dict（策略3 仍是修後）
    "mid_ring_d_reverted": ("mid", _REVERT["mid"][2:3], _NON_FINITE),
}


#: 驗收組（非阻擋 1）實測在原始檔上做、當時新測試全綠的兩個突變 → 名稱 → (出口, 替換組, 必須轉紅的 golden 鍵)
_SOURCE_LEVEL_MUTANTS = {
    # §八 策略3 卡的差額四捨五入少一位：+7.13 → +7.10、+0.04 → +0.00、−1.04 → −1.00
    "mid_gap8_round_1dp": ("mid", (("            _gap8 = round(_m1b8 - _m2b8, 2)\n",
                                    "            _gap8 = round(_m1b8 - _m2b8, 1)\n"),),
                           {("gap_2dp_713", "CBC-tier1"), ("gap_2dp_713", "proxy_label"),
                            ("gap_2dp_pos004", "CBC-tier1"), ("gap_2dp_neg104", "CBC-tier1")}),
    # §二 黃金交叉由嚴格大於改成大於等於：M1B＝M2 會多出一條黃金交叉
    "state_golden_cross_ge0": ("state", (("            if _diff > 0:\n",
                                          "            if _diff >= 0:\n"),),
                               {("zero", "CBC-tier1")}),
}


class TestMutantsAreCaught:

    @pytest.mark.parametrize("name", sorted(_MUTANTS))
    def test_mutant_turns_missing_contract_red(self, name, monkeypatch):
        ek, pairs, must_be_red = _MUTANTS[name]
        m = _load(ek, _apply(_source(ek), pairs), name)
        red = _red_cases(ek, m, monkeypatch)
        assert red, f"突變「{name}」沒讓任何缺值情境轉紅 —— 新測試抓不到它"
        assert must_be_red <= red, f"突變「{name}」應讓 {sorted(must_be_red - red)} 轉紅"

    @pytest.mark.parametrize("ek, pairs", [
        # 非缺值路徑：§十一 M2 顯示改兩位小數
        ("news", (("M2={_m2_ai:.1f}%", "M2={_m2_ai:.2f}%"),)),
        # 非缺值路徑：個股建議差額方向反了
        ("op", (("_m1b_diff_g = (_m1b_g - _m2_g\n", "_m1b_diff_g = (_m2_g - _m1b_g\n"),)),
        # 非缺值路徑：§二 把真 0 當缺（`if not _v`）—— 用 `and _m2_y` 的真值判斷
        ("state", (("and _m1b_y is not None and _m2_y is not None):",
                    "and _m1b_y is not None and _m2_y):"),)),
        # 非缺值路徑：§八 D 徽章改用四捨五入到一位
        ("mid", (("_gap8c = round(float(_m1b8_v) - float(_m2b8_v), 2)",
                  "_gap8c = round(float(_m1b8_v) - float(_m2b8_v), 1)"),)),
    ], ids=["news_m2_format", "op_diff_sign", "state_zero_as_missing", "mid_d_rounding"])
    def test_non_missing_mutant_breaks_identity_or_golden(self, ek, pairs, pre_fix, monkeypatch):
        # 突變體只在記憶體裡、比對基準是「未突變現行檔」的還原體 → D 類抓得到。
        # 突變若直接寫進原始檔，基準會一起被帶歪 —— 那種情形見下一條（靠 golden）。
        m = _load(ek, _apply(_source(ek), pairs), "non_missing")
        broken = [(g, s) for g in _GAPS for s in ("CBC-tier1", "proxy_label")
                  if _view(ek, _RUN[ek](m, _info(g, s), monkeypatch))
                  != _view(ek, _RUN[ek](pre_fix[ek], _info(g, s), monkeypatch))]
        assert broken, "非缺值路徑的突變沒被 D 抓到"

    @pytest.mark.parametrize("name", sorted(_SOURCE_LEVEL_MUTANTS))
    def test_source_level_mutant_is_caught_by_golden(self, name, monkeypatch):
        """驗收組非阻擋 1：突變**寫進原始檔本身**時，D 類看不到，golden（修前實跑）抓得到。"""
        ek, pairs, must_break = _SOURCE_LEVEL_MUTANTS[name]
        mutated = _apply(_source(ek), pairs)
        m = _load(ek, mutated, name)
        own_pre = _load(ek, _apply(mutated, _REVERT[ek]), f"{name}_pre")
        # 前提照實釘住：以「突變後的檔」反向替換出的還原體同樣帶著突變 → D 類比不出差別
        for gap, source in sorted(must_break):
            info = _info(gap, source)
            assert _view(ek, _RUN[ek](m, info, monkeypatch)) == \
                _view(ek, _RUN[ek](own_pre, info, monkeypatch))
        broken = set(_GOLDEN[ek](m, monkeypatch))
        assert must_break <= broken, f"golden 應讓 {sorted(must_break - broken)} 轉紅"


# ══════════════════════════════════════════════════════════════════════════
# H：slow lane —— 真 Streamlit（AppTest）render
# ══════════════════════════════════════════════════════════════════════════
_APP_CALLS = {
    "op": ("from src.ui.tabs.stock_sections.section_op_recommendation import "
           "render_op_recommendation_section\n"
           "render_op_recommendation_section('2330', 82.0, {'contracting': True}, "
           "5.0, 100.0, 55.0, 0, 0)\n"),
    "state": ("st.session_state['_ndc_hist_cache'] = {}\n"
              "st.session_state['_ndc_li_cache'] = {}\n"
              "st.session_state['_fi_streak_cache'] = {}\n"
              "from src.ui.tabs.macro.section_state import render_section_state\n"
              "render_section_state({'signals': []}, st.empty(), st.empty(), {}, "
              "show_market_data=False, requested=True)\n"),
    "mid": ("from src.ui.tabs.macro.section_mid import render_section_mid\n"
            "render_section_mid(False, {}, {}, {})\n"),
    "news": ("from src.ui.tabs.macro.section_news_ai import render_section_news_ai\n"
             "render_section_news_ai({}, 'unknown')\n"),
}


def _app(ek: str, info):
    """真 AppTest（`m1b_m2_info` 以 JSON 傳入，NaN／±inf 亦可）→ 已 run 的 AppTest。"""
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest
    body = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(_REPO)!r})\n"
        "import streamlit as st\n"
        f"st.session_state['m1b_m2_info'] = json.loads({json.dumps(info)!r})\n"
        "st.session_state.setdefault('cl_data', {'inst': {}})\n"
        f"{_APP_CALLS[ek]}"
    )
    at = AppTest.from_string(body, default_timeout=90)
    at.run()
    return at


def _app_fail_on_exception(at) -> None:
    if at.exception:
        pytest.fail("render 有 uncaught exception:\n" + "\n".join(
            f"{e.type}: {str(e.value)[:300]}" for e in at.exception))


def _app_texts(at) -> list[str]:
    return [str(x.value) for x in (*at.markdown, *at.caption, *at.info, *at.warning, *at.error)]


_APP_MISSING = ["m2_none", "m1b_key_absent", "both_nan", "m2_pos_inf", "proxy_m2_absent"]


@pytest.mark.slow
class TestRealStreamlitRender:

    @pytest.mark.parametrize("name", _APP_MISSING)
    @pytest.mark.parametrize("ek", ["op", "state", "mid"])
    def test_missing_renders_like_empty(self, ek, name):
        at = _app(ek, _MISSING[name])
        _app_fail_on_exception(at)
        empty = _app(ek, {})
        _app_fail_on_exception(empty)
        texts = _app_texts(at)
        assert texts == _app_texts(empty), f"{ek}/{name}：真 render 與空值不同"
        assert not any(NOTE in t or "nan%" in t or "inf%" in t for t in texts)

    @pytest.mark.parametrize("ek", ["op", "state", "mid"])
    def test_numbers_still_render(self, ek):
        at = _app(ek, {"m1b_yoy": 5.1, "m2_yoy": 2.0, "source": M1B_PROXY_SOURCE_LABEL})
        _app_fail_on_exception(at)
        texts = "\n".join(_app_texts(at))
        want = {"op": f"【景氣環境】M1B-M2{NOTE}為正且強勁",
                "state": "",                         # 代理值不產生交叉訊號（照舊）
                "mid": f"M1B-M2 Gap = +3.10%{NOTE}（黃金交叉·熱錢狂潮）"}[ek]
        assert want in texts
        if ek == "state":
            assert "M1B>M2 黃金交叉" not in texts

    @pytest.mark.parametrize("name", ["m2_key_absent", "m2_none", "both_nan", "m1b_key_absent"])
    def test_news_verdict_button_real_click(self, name, monkeypatch):
        """真按「🔒 執行 AI 裁決」：Gemini／新聞／狀態鎖在同一個 process 內換成替身。"""
        import src.data.news as N
        import src.services.app_ai_service as A
        import src.ui.tabs.macro.section_news_ai as M
        from src.services.macro_state_locker import calculate_system_state as real_calc
        seen: dict = {"prompts": [], "numbers": [], "locked": []}

        class _Locker:
            def lock_system_state_only(self, state):
                seen["locked"].append(state)

        def _spy(nums):
            seen["numbers"].append(dict(nums))
            return real_calc(nums)

        monkeypatch.setattr(A, "gemini_call",
                            lambda p, max_tokens=2048: seen["prompts"].append(p) or "（替身）")
        monkeypatch.setattr(N, "fetch_macro_news", lambda *a, **k: [])
        monkeypatch.setattr(M, "MacroStateLocker", _Locker)
        monkeypatch.setattr(M, "calculate_system_state", _spy)
        at = _app("news", _MISSING[name])
        _app_fail_on_exception(at)
        at.button(key="btn_run_verdict").click().run()
        _app_fail_on_exception(at)
        assert len(seen["prompts"]) == 1, "真按鈕沒有走到 Gemini 替身"
        assert _m1b_lines(seen["prompts"][0]) == [] and "M2=0.0%" not in seen["prompts"][0]
        assert seen["numbers"][0]["M1B_YoY_pct"] is None
        assert seen["numbers"][0]["M2_YoY_pct"] is None
        assert "資金緊縮" not in str(seen["locked"])
