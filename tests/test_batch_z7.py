"""批 Z7：§三／§八／§九 的「有效 VIX」＋外資期貨缺值（程式真相 origin/main `96779d4`）。

第八輪分類 A、B 兩組一致判可自主的四列（規格為總管轉述；交接本 HANDOFF `1aa4d44`）：

- Z3-n4（併 Z3-n11）§三 `section_chips.read_v4_macro_veto`：原只擋缺值／非數值／溢位／NaN／±inf，VIX ≤ 0、
  bool（含 numpy bool）、數字字串（含 bytes）、numpy 複數照樣判燈（實跑 VIX=-5＋外資 −40,000 口 → 🔴），
  §八 揭露框於是列出「看的是 VIX=-5.0」。改走 L0 `shared.vix_validity.vix_value_or_none`（與 §八 `_vcur8_v`
  同一套規則，A 段以輸入矩陣實跑 §八 對拍）→ 無效回 None ⇒ §三 卡走既有「⬜ 無法判定／VIX 未取得…」、
  §八 揭露框走既有缺值句。預期副作用（總管已知）：無效 VIX＋重空單時 §三 由 🔴 轉 ⬜（與缺 VIX 相同）。
- Z3-n1 §九 `section_cross_ai`：`_num` 不擋 ±inf、未接 OverflowError（VIX=10**400 整段拋例外），VIX ≤ 0／−inf／
  True 印「（安全）」「極度平靜」。改：VIX 走同一個 L0 判定、無效當缺值（④ 走既有「待取得」、⑤ 不列 VIX）；
  VIX「有值但無效」時 ④ 那句「VIX / CPI 數據載入中」整句純刪（比照批 Z3 V1-n5）；`_num` 補有限值檢查並接
  OverflowError（其餘欄位 ±inf／溢位 → 各自既有缺值路徑）。⛔ 美國核心 CPI 不套（④ 把 CPI 缺值當正常，
  另列 C8-n7）—— CPI 一切照舊，含 10**400 照舊拋 OverflowError。
- C7-n7 §八：VIX > 100（結論段「VIX 數值異常」的既有門檻，抽成本檔常數 `_VIX_ABNORMAL_ABOVE`）時，KPI 卡走既有
  「待取得」卡、基本面否決檢查走既有「VIX待取得，未納入任何判斷」；結論段原句不動。連帶變化（總管裁定接受）：
  其餘總經有值時既有揭露框改為出現（§三 照判 🔴；§三 該不該擋 > 100 屬客戶待答 Q-r8b），見 D 段末條。
- C7-n3 只做 (b)：`section_health_score` 的 `_v4_fut2` 預設 0.0 → None（畫面零變化：該頁不顯示 v4 總經燈）。
  (a)（§三 v5 卡「水位中性」）停手（⑤：卡上沒有任何既有字樣可說明「期貨缺值／未取得」；總管裁定停手、登記為
  卡住 ⑤），本檔只鎖現行輸出；(c) 依規格不碰。

golden：一律於基底 `96779d4` 實跑後寫死於本檔（⛔ 不讀 git、不由現行碼反推）。「修前副本」（現行檔反向替換本批
改動處；實作組已離線以 `96779d4` 原始檔對同一批輸入實跑、輸出逐字相同）只用於「與本批無關的形狀逐字不變」的
大範圍對拍 —— 「拔掉修復即轉紅」一律落在寫死的 golden 或實跑行為上，不靠副本、不靠原始碼字面。
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import math
import pathlib
import random
import re
import struct
import types
import warnings
from decimal import Decimal
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

from shared.vix_validity import vix_value_or_none
from tests.test_m2n2_no_zero_fill import _FakeST, _apply

_REPO = pathlib.Path(__file__).resolve().parents[1]
_HUGE = 10 ** 400
_COMPLEX_WARNING = getattr(np, "exceptions", np).ComplexWarning

_CHIPS = ("src/ui/tabs/macro/section_chips.py", "src.ui.tabs.macro.section_chips")
_MID = ("src/ui/tabs/macro/section_mid.py", "src.ui.tabs.macro.section_mid")
_CROSS = ("src/ui/tabs/macro/section_cross_ai.py", "src.ui.tabs.macro.section_cross_ai")
_HEALTH = ("src/ui/tabs/stock_sections/section_health_score.py",
           "src.ui.tabs.stock_sections.section_health_score")


def _real(spec):
    return importlib.import_module(spec[1])


def _source(spec) -> str:
    return (_REPO / spec[0]).read_text(encoding="utf-8")


def _variant(spec, code: str, tag: str):
    """把一份（改過的）原始碼載成獨立模組（不進 `sys.modules`，不碰本尊）。"""
    real = _real(spec)
    s = importlib.util.spec_from_loader(f"_z7_{tag}", loader=None)
    m = importlib.util.module_from_spec(s)
    m.__file__ = real.__file__
    exec(compile(code, real.__file__, "exec"), m.__dict__)
    return m


#: 修後 → 修前（反向替換，每組恰好一處；只換程式行）。僅供「無關形狀逐字不變」對拍用。
_REVERT = {
    "chips": (("    _vix = vix_value_or_none(_vix_raw)\n    if _vix is None:\n        return None\n",
               "    try:\n        _vix = float(_vix_raw)\n"
               "    except (TypeError, ValueError, OverflowError):\n        return None\n"
               "    if not __import__('math').isfinite(_vix):\n        return None\n"),),
    "cross": (("    _ai_vix  = vix_value_or_none(_m8_vix.get('current')) if isinstance(_m8_vix, dict) else None\n",
               "    _ai_vix  = _num_raw(_m8_vix, 'current')\n"),
              ("        try:\n            _f = _num_raw(node, key)\n        except OverflowError:\n"
               "            return None\n        return _f if (_f is None or math.isfinite(_f)) else None\n",
               "        return _num_raw(node, key)\n"),
              ("('' if _vix_bad9 else 'VIX / CPI 數據載入中')", "'VIX / CPI 數據載入中'")),
    "mid": (("    _vix_sane8 = (None if (_vcur8_v is not None and float(_vcur8_v) > _VIX_ABNORMAL_ABOVE)\n"
             "                  else _vcur8_v)\n",
             "    _vix_sane8 = _vcur8_v\n"),),
    "health": (("            _v4_fut2 = None\n", "            _v4_fut2 = 0.0\n"),),
}
_SPECS = {"chips": _CHIPS, "cross": _CROSS, "mid": _MID, "health": _HEALTH}


@pytest.fixture(scope="module")
def pre():
    """修前副本 {名: 模組}（見 `_REVERT`）。"""
    return {k: _variant(_SPECS[k], _apply(_source(_SPECS[k]), pairs), f"pre_{k}")
            for k, pairs in _REVERT.items()}


class _FakeSTFig(_FakeST):
    """多記一筆圖表標題（§八 VIX 走勢圖的燈義只出現在圖標題裡）。"""

    def plotly_chart(self, fig, *a, **k):
        self.out.append(("plotly_chart", str(fig.layout.title.text)))


class _FloatOnly:
    """有 `__float__`、沒有比較運算子的怪異物件：§八 在 `<= 0` 拋 TypeError —— 共用判定刻意照拋（同一套規則）。"""

    def __float__(self):
        return 18.0


# ══════════════════════════════════════════════════════════════════════════
# 共用 harness
# ══════════════════════════════════════════════════════════════════════════
_MID_BASE = {"ism_pmi": {"value": 52.0}, "us_core_cpi": {"yoy": 3.0},
             "tw_export": {"yoy": 5.0, "date": "2026-08"}, "ndc_signal": {"score": 27}}


def _node(v):
    """有走勢資料的 VIX 節點（有 dates 才走「畫圖」那枝，看得到圖標題的燈義）。"""
    return {"current": v, "dates": ["2026-09-30", "2026-10-01"], "values": [18.0, 18.0], "ma20": 17.5}


def _mid(vix_node, mp, *, mod=None, base=None, real_v4=False, fut=-40000.0):
    """實跑 §八（`_load_heavy=False`）。回 (輸出, apply_vix_veto 收到的參數)。

    real_v4=False：§三 入口 stub 為 None（只看 §八 自己）；True：用 §三 真函式，外資期貨＝fut。
    """
    import src.services.allocation_service as AS
    import src.ui.tabs.macro.section_chips as SC
    mod = mod or _real(_MID)
    info = dict(_MID_BASE if base is None else base)
    if vix_node is not _DROP:
        info["vix"] = vix_node
    ss = {"macro_info": info, "bias_info": {"bias_240": 5.0}}
    if real_v4:
        ss["li_latest"] = pd.DataFrame({"日期": ["2026-10-01"], "外資大小": [fut]})
    fake = _FakeSTFig(ss)
    calls: list = []
    mp.setattr(mod, "st", fake)
    if real_v4:
        assert (SC.read_v4_macro_veto.__module__, SC.read_v4_macro_veto.__qualname__) == (
            "src.ui.tabs.macro.section_chips", "read_v4_macro_veto")
        mp.setattr(SC, "st", fake)
    else:
        mp.setattr(SC, "read_v4_macro_veto", lambda *a, **k: None)
    mp.setattr(AS, "apply_vix_veto", lambda *a, **k: calls.append(a))
    mp.setattr(AS, "apply_ring_gate", lambda *a, **k: None)
    mp.setattr(AS, "register_conflict", lambda *a, **k: None)
    mp.setattr(AS, "get_allocation", lambda *a, **k: types.SimpleNamespace(is_loaded=False, final_hi=None))
    mod.render_section_mid(False, {}, {}, {})
    return list(fake.out), calls


_DROP = object()   # 「macro_info 沒有 vix 鍵」


def _li(fut=-40000.0, pcr=110.0):
    return pd.DataFrame({"日期": ["2026-10-01"], "外資大小": [fut], "選PCR": [pcr]})


def _chips(vix_node, mp, *, mod=None, li=None, sleeves=None):
    """實跑 §三（法人／融資空、先行指標一列）。回 (輸出, read_v4_macro_veto() 的結果)。"""
    import src.services.allocation_service as AS
    mod = mod or _real(_CHIPS)
    fake = _FakeST({"macro_info": {"vix": vix_node}, "li_latest": _li() if li is None else li})
    mp.setattr(mod, "st", fake)
    mp.setattr(AS, "get_allocation", lambda *a, **k: types.SimpleNamespace(
        is_loaded=False, range_text="", capped=False, cap_text="", final_hi=None))
    mp.setattr(AS, "get_allocation_sleeves", lambda *a, **k: sleeves)
    mod.render_section_chips({}, None, {})
    return list(fake.out), mod.read_v4_macro_veto()


_S9_FULL = {"ism_pmi": {"value": 52.0}, "us_core_cpi": {"yoy": 2.5}, "tw_export": {"yoy": 5.0}}


def _s9(vix_node, mp, *, mod=None, base=None, m1b=None, bias=None, tech=None):
    """實跑 §九。回輸出（vix_node 為 `_DROP` 時 macro_info 不放 vix 鍵）。"""
    import src.services.allocation_service as AS
    mod = mod or _real(_CROSS)
    info = dict(_S9_FULL if base is None else base)
    if vix_node is not _DROP:
        info["vix"] = vix_node
    fake = _FakeST({"macro_info": info, "m1b_m2_info": m1b, "bias_info": bias})
    mp.setattr(mod, "st", fake)
    mp.setattr(AS, "get_allocation", lambda *a, **k: types.SimpleNamespace(is_loaded=False))
    mod.render_section_cross_ai(tech or {}, {})
    return list(fake.out)


# ── §九 卡片：凍結 `_ai_card` 與 ⑤ 結論卡的 HTML 樣板（`96779d4` 原樣） ─────────────────────────
def _card9(title, color, label, desc):
    return (f'<div style="background:#0d1117;border:1px solid {color}44;border-radius:8px;'
            f'padding:12px;min-height:110px;">'
            f'<div style="font-size:10px;color:#484f58;margin-bottom:4px;">{title}</div>'
            f'<div style="font-size:13px;font-weight:700;color:{color};line-height:1.3;">{label}</div>'
            f'<div style="font-size:11px;color:#8b949e;margin-top:6px;line-height:1.5;">{desc}</div>'
            f'</div>')


def _card9_5(color, icon, txt):
    return (f'<div style="background:#0d1117;border:2px solid {color};border-radius:8px;'
            f'padding:12px;min-height:110px;">'
            f'<div style="font-size:10px;color:#484f58;margin-bottom:4px;">⑤ 結論</div>'
            f'<div style="font-size:14px;font-weight:900;color:{color};">{icon}</div>'
            f'<div style="font-size:12px;color:#c9d1d9;margin-top:6px;line-height:1.6;">{txt}</div>'
            f'</div>')


def _md(out):
    return [t for k, t in out if k == "markdown"]


# ══════════════════════════════════════════════════════════════════════════
# A. 共用判定 `vix_value_or_none` ＝ §八 `_vcur8_v` 的判定（實跑 §八 對拍）
# ══════════════════════════════════════════════════════════════════════════
_MATRIX = [pytest.param(v, id=i) for v, i in (
    (None, "None"),
    # 非有限／溢位
    (math.nan, "nan"), (math.inf, "+inf"), (-math.inf, "-inf"), (np.float64("nan"), "np.nan"),
    (np.float64("-inf"), "np.-inf"), (_HUGE, "10**400"), (-_HUGE, "-10**400"),
    (np.longdouble("1e400"), "longdouble-1e400"), (Decimal("NaN"), "Decimal-NaN"),
    (Decimal("sNaN"), "Decimal-sNaN"), (Decimal("Infinity"), "Decimal-inf"),
    # ≤ 0
    (0, "0"), (0.0, "0.0"), (-0.0, "-0.0"), (-5, "-5"), (-5.0, "-5.0"), (-1e-9, "-1e-9"), (-5e-324, "-5e-324"),
    (np.float64(-3.0), "np.float64(-3)"), (np.int64(-3), "np.int64(-3)"), (np.int64(0), "np.int64(0)"),
    (np.float32(-5), "np.float32(-5)"), (Decimal("-5"), "Decimal(-5)"), (Decimal("0"), "Decimal(0)"),
    (Decimal("-0"), "Decimal(-0)"), (Fraction(-5, 1), "Fraction(-5)"), (Fraction(0), "Fraction(0)"),
    (np.array(-3.0), "0d-array(-3)"),
    # bool
    (True, "True"), (False, "False"), (np.True_, "np.True_"), (np.False_, "np.False_"),
    # 複數
    (complex(18, 0), "complex(18)"), (np.complex128(18), "np.complex128(18)"),
    (np.complex64(25), "np.complex64(25)"), (np.complex128(-5), "np.complex128(-5)"),
    (np.complex128(18 + 5j), "np.complex128(18+5j)"),
    # 字串／bytes／容器
    ("18.5", "'18.5'"), ("30", "'30'"), (" 18 ", "' 18 '"), ("-5", "'-5'"), ("", "''"), ("N/A", "'N/A'"),
    ("nan", "'nan'"), ("inf", "'inf'"), (np.str_("18.5"), "np.str_('18.5')"), (b"18.5", "b'18.5'"),
    (bytearray(b"18"), "bytearray"), ([18], "[18]"), ({}, "{}"), ((18,), "(18,)"),
    (pd.NA, "pd.NA"), (pd.NaT, "pd.NaT"),
    # 極小正數（有效）
    (5e-324, "5e-324"), (2.2250738585072014e-308, "min-normal"), (1e-300, "1e-300"), (1e-9, "1e-9"),
    # 正常值與門檻邊界（有效；> 100 由 §八 結論段另判「數值異常」）
    (18, "18"), (18.0, "18.0"), (12.5, "12.5"), (20, "20"), (22, "22"), (25, "25"), (30, "30"),
    (35.5, "35.5"), (99.9, "99.9"), (100, "100"), (100.0, "100.0"), (100.0001, "100.0001"), (150, "150"),
    (150.0, "150.0"), (1e300, "1e300"), (1.7976931348623157e308, "max-float"),
    # numpy／Decimal／Fraction 有效值
    (np.float64(18.0), "np.float64(18)"), (np.float32(18.5), "np.float32(18.5)"),
    (np.int64(18), "np.int64(18)"), (np.float16(18), "np.float16(18)"), (np.longdouble(18), "longdouble(18)"),
    (Decimal("18.5"), "Decimal(18.5)"), (Decimal("150"), "Decimal(150)"), (Fraction(37, 2), "Fraction(37/2)"),
    (np.array(18.0), "0d-array(18)"),
    # Z3-n9（已登記、第八輪分歧未判）：0 維布林陣列 §八 現況放行（當 1.0）—— 共用判定照樣放行
    (np.array(True), "0d-array(True)"),
)]


def _verdict_mid(v, mp):
    """實跑 §八，讀出它對這個 VIX 的判定（只看行為：apply_vix_veto 的參數／結論段的「數值異常」）。"""
    with warnings.catch_warnings():
        warnings.simplefilter("error", _COMPLEX_WARNING)       # 不得靠 math.isfinite 丟虛部過關
        out, calls = _mid({"current": v}, mp)
    errs = [t for k, t in out if k == "error" and t.startswith("❌ VIX 數值異常（")]
    if errs:
        assert calls == [] and len(errs) == 1, (calls, errs)
        return "abnormal", re.match(r"❌ VIX 數值異常（(.*?)）", errs[0]).group(1)
    assert len(calls) == 1, calls
    x = calls[0][0]
    return ("invalid",) if x is None else ("valid", float(x).hex())


def _verdict_shared(v):
    with warnings.catch_warnings():
        warnings.simplefilter("error", _COMPLEX_WARNING)
        s = vix_value_or_none(v)
    if s is None:
        return ("invalid",)
    assert type(s) is float
    return ("abnormal", f"{s:.0f}") if s > 100 else ("valid", s.hex())


class TestSharedEqualsSection8:
    @pytest.mark.parametrize("v", _MATRIX)
    def test_same_verdict_as_section8(self, v, monkeypatch):
        assert _verdict_shared(v) == _verdict_mid(v, monkeypatch)

    def test_random_doubles_same_verdict(self, monkeypatch):
        rng = random.Random(20261005)
        vals = [struct.unpack("<d", rng.getrandbits(64).to_bytes(8, "little"))[0] for _ in range(40)]
        vals += [rng.uniform(-50, 150) for _ in range(40)]
        for v in vals:
            assert _verdict_shared(v) == _verdict_mid(v, monkeypatch), v
            monkeypatch.undo()

    def test_weird_object_raises_in_both(self, monkeypatch):
        # 有 __float__、沒有比較 → §八 在 `<= 0` 拋 TypeError；共用判定照拋（⛔ 不另吞成 None）
        with pytest.raises(TypeError):
            _mid({"current": _FloatOnly()}, monkeypatch)
        with pytest.raises(TypeError):
            vix_value_or_none(_FloatOnly())

    @pytest.mark.parametrize("v", [5e-324, 1e-300, 18.0, 150.0, 1.7976931348623157e308])
    def test_valid_returns_same_float_bits(self, v):
        assert vix_value_or_none(v).hex() == float(v).hex()


# ══════════════════════════════════════════════════════════════════════════
# B. Z3-n4（併 Z3-n11）：§三 `read_v4_macro_veto` 收下無效 VIX
# ══════════════════════════════════════════════════════════════════════════
#: §三「🏛️ v4 引擎風險燈」卡：`96779d4` 實跑 HTML 凍結為樣板
_V4_CARD = ('<div style="border-left:5px solid {c};background:#0d1117;padding:9px 14px;'
            'border-radius:0 8px 8px 0;margin:6px 0;"><span style="font-size:11px;color:#888888;">'
            '🏛️ v4 引擎風險燈</span><br><span style="font-size:14px;font-weight:900;color:{c};">'
            '{status} — ⬜ 總經未評估</span><br><span style="font-size:12px;color:#c9d1d9;">{msg}</span><br>'
            '<span style="font-size:11px;color:#888888;">📌 本燈只看【VIX（超過 25 紅燈／超過 20 黃燈）× '
            '外資期貨淨口數（空單超過 2 萬口 紅燈／超過 1 萬口 黃燈）】—— 不含 PMI／CPI／出口／NDC。'
            '景氣與通膨面請見 §八 總經拼圖的「總經基本面否決檢查」。</span></div>')
_UNKNOWN_CARD = _V4_CARD.format(
    c="#888888", status="⬜ 無法判定",
    msg="VIX 未取得，v4 引擎風險燈無法判定 — 請先按「🚀 一鍵更新全部數據」補齊 VIX 後再看本卡。")


def _light_card(light, vt, ft):
    c, status, msg = {
        "R": ("#da3633", "🔴 紅燈", f"🚨 總經環境高風險！VIX={vt} / 外資期貨={ft} — （實際持股見 🎚️ 建議持股油門），嚴禁追高攤平"),
        "Y": ("#eab308", "🟡 黃燈", f"⚠️ 大盤震盪中，VIX={vt} / 外資期貨={ft} — 縮小部位，跌破防守線務必嚴格執行"),
        "G": ("#2ea043", "🟢 綠燈", f"✅ 總經環境安全，VIX={vt} / 外資期貨={ft} — 可依策略佈局"),
    }[light]
    return _V4_CARD.format(c=c, status=status, msg=msg)


_FUTS = ((-40000.0, "-40,000口"), (0.0, "0口"))


def _v4_card(out):
    cards = [t for t in _md(out) if "🏛️ " in t]
    assert len(cards) == 1, cards
    return cards[0]


#: 修前（`96779d4` 實跑）照樣判燈、批 Z7 起判無效：(值, 修前卡上的 VIX 字樣, 外資 0 口時修前的燈)
#: （外資 −40,000 口時修前一律 🔴）
_NEWLY_INVALID = [pytest.param(v, vt, l0, id=i) for v, vt, l0, i in (
    (-5, "-5.0", "G", "-5"), (0, "0.0", "G", "0"), (-0.0, "-0.0", "G", "-0.0"), (-1e-9, "-0.0", "G", "-1e-9"),
    (np.float64(-3.0), "-3.0", "G", "np.float64(-3)"), (np.int64(-3), "-3.0", "G", "np.int64(-3)"),
    (np.int64(0), "0.0", "G", "np.int64(0)"), (np.float32(-5), "-5.0", "G", "np.float32(-5)"),
    (Decimal("-5"), "-5.0", "G", "Decimal(-5)"), (Decimal("0"), "0.0", "G", "Decimal(0)"),
    (Fraction(-5, 1), "-5.0", "G", "Fraction(-5)"),
    (True, "1.0", "G", "True"), (False, "0.0", "G", "False"), (np.True_, "1.0", "G", "np.True_"),
    (np.False_, "0.0", "G", "np.False_"),
    ("18.5", "18.5", "G", "'18.5'"), ("30", "30.0", "R", "'30'"), (" 18 ", "18.0", "G", "' 18 '"),
    ("-5", "-5.0", "G", "'-5'"), (np.str_("18.5"), "18.5", "G", "np.str_"), (b"18.5", "18.5", "G", "bytes"),
    (bytearray(b"18"), "18.0", "G", "bytearray"),
    (np.complex128(18), "18.0", "G", "np.complex128(18)"), (np.complex64(25), "25.0", "Y", "np.complex64(25)"),
    (np.complex128(-5), "-5.0", "G", "np.complex128(-5)"),
)]
#: 修前修後都判不出（`96779d4` 實跑即 ⬜）
_ALREADY_NONE = [pytest.param(v, id=i) for v, i in (
    (None, "None"), (math.nan, "nan"), (math.inf, "+inf"), (-math.inf, "-inf"), ("x", "'x'"), ("", "''"),
    ("N/A", "'N/A'"), ("nan", "'nan'"), ("inf", "'inf'"), ("1e400", "'1e400'"), ([1], "[1]"), ({}, "{}"),
    (pd.NA, "pd.NA"), (pd.NaT, "pd.NaT"), (_HUGE, "10**400"), (-_HUGE, "-10**400"),
    (complex(18, 0), "complex(18)"), (Decimal("NaN"), "Decimal-NaN"), (Decimal("sNaN"), "Decimal-sNaN"),
)]
#: 有效值：(值, 卡上的 VIX 字樣, 外資 0 口時的燈) —— `96779d4` 實跑寫死，修後必須逐字相同
_VALID = [pytest.param(v, vt, l0, id=i) for v, vt, l0, i in (
    (18.0, "18.0", "G", "18.0"), (18, "18.0", "G", "18"), (12.5, "12.5", "G", "12.5"), (20, "20.0", "G", "20"),
    (20.0001, "20.0", "Y", "20.0001"), (22, "22.0", "Y", "22"), (25, "25.0", "Y", "25"),
    (25.0001, "25.0", "R", "25.0001"), (26, "26.0", "R", "26"), (30, "30.0", "R", "30"),
    (99.9, "99.9", "R", "99.9"), (100, "100.0", "R", "100"), (100.0, "100.0", "R", "100.0"),
    (100.0001, "100.0", "R", "100.0001"), (150.0, "150.0", "R", "150.0"),
    (1e300, format(1e300, ".1f"), "R", "1e300"),
    (1.7976931348623157e308, format(1.7976931348623157e308, ".1f"), "R", "max-float"),
    (5e-324, "0.0", "G", "5e-324"), (1e-300, "0.0", "G", "1e-300"),
    (np.float64(18.0), "18.0", "G", "np.float64"), (np.float32(18.5), "18.5", "G", "np.float32"),
    (np.int64(18), "18.0", "G", "np.int64"), (np.float16(18), "18.0", "G", "np.float16"),
    (Decimal("18.5"), "18.5", "G", "Decimal"), (Fraction(37, 2), "18.5", "G", "Fraction"),
    (np.longdouble(18), "18.0", "G", "longdouble"), (np.array(18.0), "18.0", "G", "0d-array"),
    (np.array(True), "1.0", "G", "0d-array(True)"),   # Z3-n9：與 §八 一致（放行），本批不改
)]


class TestZ3n4Section3:
    @pytest.mark.parametrize("fut,ft", _FUTS)
    @pytest.mark.parametrize("v,vt,l0", _NEWLY_INVALID)
    def test_newly_invalid_takes_existing_unknown_card(self, v, vt, l0, fut, ft, monkeypatch):
        with warnings.catch_warnings():
            warnings.simplefilter("error", _COMPLEX_WARNING)
            out, light = _chips({"current": v}, monkeypatch, li=_li(fut))
        assert light is None
        assert _v4_card(out) == _UNKNOWN_CARD
        # 修前（寫死）：照樣判燈並印出無效值 —— 拔掉修復即轉紅
        assert _v4_card(out) != _light_card("R" if fut else l0, vt, ft)

    @pytest.mark.parametrize("fut,ft", _FUTS)
    @pytest.mark.parametrize("v,vt,l0", _NEWLY_INVALID)
    def test_whole_section_equals_missing_vix(self, v, vt, l0, fut, ft, monkeypatch):
        # 無效 VIX ＝ 缺 VIX：整個 §三 輸出逐字相同（v4 卡以外本來就與 VIX 無關）
        with warnings.catch_warnings():
            warnings.simplefilter("error", _COMPLEX_WARNING)
            out, _ = _chips({"current": v}, monkeypatch, li=_li(fut))
        base, _ = _chips({"current": None}, monkeypatch, li=_li(fut))
        assert out == base

    @pytest.mark.parametrize("fut,ft", _FUTS)
    @pytest.mark.parametrize("v", _ALREADY_NONE)
    def test_already_missing_unchanged(self, v, fut, ft, monkeypatch):
        out, light = _chips({"current": v}, monkeypatch, li=_li(fut))
        assert light is None and _v4_card(out) == _UNKNOWN_CARD

    @pytest.mark.parametrize("fut,ft", _FUTS)
    @pytest.mark.parametrize("v,vt,l0", _VALID)
    def test_valid_vix_card_golden(self, v, vt, l0, fut, ft, monkeypatch):
        out, light = _chips({"current": v}, monkeypatch, li=_li(fut))
        assert _v4_card(out) == _light_card("R" if fut else l0, vt, ft)
        assert type(light["_vix"]) is float and light["_vix"].hex() == float(v).hex()
        assert light["_futures"] == fut and light["_pcr"] == 110.0

    @pytest.mark.parametrize("node", [None, "x", 18.5, {}], ids=["node-None", "node-str", "node-float", "node-empty"])
    def test_non_dict_or_keyless_node(self, node, monkeypatch):
        out, light = _chips(node, monkeypatch)
        assert light is None and _v4_card(out) == _UNKNOWN_CARD

    @pytest.mark.parametrize("li", [
        pytest.param(_li(math.nan), id="fut-nan"), pytest.param(_li(-15000.0), id="fut--15000"),
        pytest.param(_li(5000.0), id="fut-5000"), pytest.param(_li(-0.0), id="fut--0.0"),
        pytest.param(pd.DataFrame({"日期": ["d"], "選PCR": [90.0]}), id="fut-col-missing"),
        pytest.param(pd.DataFrame({"日期": ["a", "b"], "外資大小": [-40000.0, math.nan], "選PCR": [1.0, 2.0]}),
                     id="ffill-last-nan"),
    ])
    @pytest.mark.parametrize("v", [18.0, 26.0, 150.0, 5e-324, Decimal("18.5"), None, math.nan, "x"], ids=repr)
    def test_unrelated_shapes_identical_to_pre_fix(self, v, li, pre, monkeypatch):
        now = _chips({"current": v}, monkeypatch, li=li)
        old = _chips({"current": v}, monkeypatch, li=li, mod=pre["chips"])
        assert now[0] == old[0] and repr(now[1]) == repr(old[1])

    @pytest.mark.parametrize("v,vt,l0", _NEWLY_INVALID)
    def test_section8_disclosure_takes_missing_sentence(self, v, vt, l0, monkeypatch):
        # §八 揭露框（真 §三 入口）：修前列出「看的是 VIX=<無效值>」／或不出；批 Z7 起走既有缺值句（此時屬實）
        for fut in (-40000.0, 0.0):
            with warnings.catch_warnings():
                warnings.simplefilter("error", _COMPLEX_WARNING)
                out, _ = _mid({"current": v}, monkeypatch, real_v4=True, fut=fut)
            disc = [(k, t) for k, t in out if (k == "warning" and "兩套判定結論不一致" in t)
                    or (k == "caption" and t.startswith("（§三 籌碼的「"))]
            assert disc == [("caption", _V4_UNAVAILABLE)], disc
            assert not any(f"看的是 VIX={vt}" in t for _k, t in out)
            monkeypatch.undo()


_V4_UNAVAILABLE = ("（§三 籌碼的「v4 引擎風險燈」因 VIX 未取得而無法判定，本區與該燈暫時無法比對 —— "
                   "兩區都缺 VIX 時請先按「🚀 一鍵更新全部數據」）")


# ── C7-n3 (a)：⑤ 停手 —— v5 卡「水位中性」本批未改，只鎖現行輸出（`96779d4` 實跑寫死）──────────────────
#   📌 批 Z10（客戶 2026-10-09 Q-r10a「缺值不得視為 0」）：期貨缺值時 v5 卡改走同頁 v4 卡既有字「外資期貨 未取得」，
#   本條改鎖新輸出（`_V5_MISSING_NO_SLEEVES`）；修前字面保留於下（`_V5_NEUTRAL_NO_SLEEVES`，供對照）。
_V5_NEUTRAL_NO_SLEEVES = (
    '<div style="border-left:5px solid #888888;background:#0d1117;padding:9px 14px;border-radius:0 8px 8px 0;'
    'margin:6px 0;"><span style="font-size:11px;color:#888888;">💰 v5 動態配置（數字來源：🎚️ 建議持股油門）</span>'
    '<br><span style="font-size:14px;font-weight:900;color:#888888;">⬜ 總經未評估 — 請先按「🚀 一鍵更新全部數據」'
    '</span><br><span style="font-size:12px;color:#c9d1d9;">📌 水位中性，依個股技術面操作，保留現金彈藥</span></div>')
_V5_MISSING_NO_SLEEVES = _V5_NEUTRAL_NO_SLEEVES.replace('📌 水位中性，依個股技術面操作，保留現金彈藥', '📌 外資期貨 未取得')


class TestC7n3aNotDone:
    @pytest.mark.parametrize("li", [pytest.param(_li(math.nan), id="fut-all-nan"),
                                    pytest.param(pd.DataFrame({"日期": ["d"], "選PCR": [90.0]}), id="fut-col-missing")])
    def test_v5_card_unchanged_pending_client(self, li, monkeypatch):
        # (a) 未做（⑤ 停手：刪掉「水位中性…」後卡上沒有任何既有字樣可說明期貨缺值，只剩顏色；總管裁定停手、
        #   登記為卡住 ⑤，2026-10-05）—— 輸出與 96779d4 逐字相同；(a) 日後有答案時依答案更新本條
        # 批 Z10 更新（客戶 2026-10-09 Q-r10a）：改走同頁 v4 卡既有字「外資期貨 未取得」，其餘逐字同 96779d4
        out, _ = _chips({"current": 18.0}, monkeypatch, li=li)
        assert [t for t in _md(out) if "💰 v5" in t] == [_V5_MISSING_NO_SLEEVES]


# ══════════════════════════════════════════════════════════════════════════
# C. Z3-n1：§九 `section_cross_ai`
# ══════════════════════════════════════════════════════════════════════════
_C4_MISSING = _card9("④ 美股動態", "#484f58", "待取得", "VIX / CPI 數據載入中")   # 既有（真的沒值）
_C4_BAD = _card9("④ 美股動態", "#484f58", "待取得", "")                          # 有值但無效：整句純刪
_C5_NO_VIX = _card9_5("#eab308", "🟡 溫和偏多，精選個股", "景氣擴張有基本面支撐。")


def _g4_green(vt, extra=" CPI=2.5%"):
    return _card9("④ 美股動態", "#22c55e", "🟢 美股平穩，降息預期支撐",
                  f"VIX={vt} MA20=17.5（安全）{extra} — 無系統性風險，有利個股選股表現")


def _g5_green(vt, word):
    return _card9_5("#22c55e", "✅ 整體偏多，積極操作", f"景氣擴張有基本面支撐；VIX={vt} {word}。")


#: 修前（`96779d4` 實跑寫死）收下、批 Z7 起判無效：(值, 修前 ④ 卡, 修前 ⑤ 卡)
_S9_NEWLY_INVALID = [pytest.param(v, c4, c5, id=i) for v, c4, c5, i in (
    (-5, _g4_green("-5.0"), _g5_green("-5.0", "極度平靜"), "-5"),
    (0, _g4_green("0.0"), _g5_green("0.0", "極度平靜"), "0"),
    (-0.0, _g4_green("-0.0"), _g5_green("-0.0", "極度平靜"), "-0.0"),
    (True, _g4_green("1.0"), _g5_green("1.0", "極度平靜"), "True"),
    (False, _g4_green("0.0"), _g5_green("0.0", "極度平靜"), "False"),
    (np.True_, _g4_green("1.0"), _g5_green("1.0", "極度平靜"), "np.True_"),
    (np.False_, _g4_green("0.0"), _g5_green("0.0", "極度平靜"), "np.False_"),
    ("18.5", _g4_green("18.5"), _g5_green("18.5", "安全窗口"), "'18.5'"),
    (np.complex128(18), _g4_green("18.0"), _g5_green("18.0", "安全窗口"), "np.complex128(18)"),
    (-math.inf, _g4_green("-inf"), _g5_green("-inf", "極度平靜"), "-inf"),
    (math.inf, _card9("④ 美股動態", "#ef4444", "🔴 美股恐慌模式，流動性危機",
                      "VIX=inf≥30 — 全球流動性急凍，強制防禦，任何技術面買訊均視為誘多"),
     _card9_5("#ef4444", "🚨 整體偏空，防禦為主", "景氣擴張有基本面支撐；VIX=inf 觸發危機，暫停攻擊。"), "+inf"),
    (_HUGE, None, None, "10**400"),          # 修前整段拋 OverflowError
    (-_HUGE, None, None, "-10**400"),
    (np.int64(-3), _g4_green("-3.0"), _g5_green("-3.0", "極度平靜"), "np.int64(-3)"),
    (Decimal("-5"), _g4_green("-5.0"), _g5_green("-5.0", "極度平靜"), "Decimal(-5)"),
    (b"18.5", _g4_green("18.5"), _g5_green("18.5", "安全窗口"), "bytes"),
)]
#: 修前就判缺（④「VIX / CPI 數據載入中」）、但 VIX「有值」：批 Z7 起比照 V1-n5 刪句
_S9_HAS_VALUE_WAS_MISSING = [pytest.param(v, id=i) for v, i in (
    (math.nan, "nan"), ("x", "'x'"), ("", "''"), ([1], "[1]"), ({}, "{}"), (complex(18, 0), "complex(18)"),
    (pd.NA, "pd.NA"), ("N/A", "'N/A'"),
)]
#: 真的沒值：④ 原句一字不變
_S9_TRUE_MISSING = [pytest.param(n, id=i) for n, i in (
    ({"current": None, "ma20": 17.5}, "current-None"), ({"ma20": 17.5}, "current-missing"),
    (_DROP, "vix-key-missing"), (None, "node-None"), ("x", "node-str"), (18.5, "node-float"),
)]
#: 有效 VIX：`96779d4` 實跑寫死的 ④／⑤（修後逐字相同）
_S9_VALID = [pytest.param(v, c4, c5, id=i) for v, c4, c5, i in (
    (18.0, _g4_green("18.0"), _g5_green("18.0", "安全窗口"), "18.0"),
    (12.0, _g4_green("12.0"), _g5_green("12.0", "極度平靜"), "12.0"),
    (25.0, _card9("④ 美股動態", "#eab308", "🟡 美股波動加劇，謹慎操作",
                  "VIX=25.0（警戒區間 20~30） MA20=17.5 — 市場情緒不確定，控制倉位，勿追高"), _C5_NO_VIX, "25.0"),
    (35.0, _card9("④ 美股動態", "#ef4444", "🔴 美股恐慌模式，流動性危機",
                  "VIX=35.0≥30 — 全球流動性急凍，強制防禦，任何技術面買訊均視為誘多"),
     _card9_5("#ef4444", "🚨 整體偏空，防禦為主", "景氣擴張有基本面支撐；VIX=35.0 觸發危機，暫停攻擊。"), "35.0"),
    (150.0, _card9("④ 美股動態", "#ef4444", "🔴 美股恐慌模式，流動性危機",
                   "VIX=150.0≥30 — 全球流動性急凍，強制防禦，任何技術面買訊均視為誘多"),
     _card9_5("#ef4444", "🚨 整體偏空，防禦為主", "景氣擴張有基本面支撐；VIX=150.0 觸發危機，暫停攻擊。"), "150.0"),
    (100.0001, _card9("④ 美股動態", "#ef4444", "🔴 美股恐慌模式，流動性危機",
                      "VIX=100.0≥30 — 全球流動性急凍，強制防禦，任何技術面買訊均視為誘多"),
     _card9_5("#ef4444", "🚨 整體偏空，防禦為主", "景氣擴張有基本面支撐；VIX=100.0 觸發危機，暫停攻擊。"), "100.0001"),
    (5e-324, _g4_green("0.0"), _g5_green("0.0", "極度平靜"), "5e-324"),
    (1e-300, _g4_green("0.0"), _g5_green("0.0", "極度平靜"), "1e-300"),
    (Decimal("18.5"), _g4_green("18.5"), _g5_green("18.5", "安全窗口"), "Decimal(18.5)"),
    (Fraction(37, 2), _g4_green("18.5"), _g5_green("18.5", "安全窗口"), "Fraction(37/2)"),
    (np.int64(18), _g4_green("18.0"), _g5_green("18.0", "安全窗口"), "np.int64(18)"),
    (np.float64(18.0), _g4_green("18.0"), _g5_green("18.0", "安全窗口"), "np.float64(18)"),
)]


def _vnode(v):
    return {"current": v, "ma20": 17.5}


class TestZ3n1Section9:
    @pytest.mark.parametrize("v,c4_pre,c5_pre", _S9_NEWLY_INVALID)
    def test_invalid_vix_takes_missing_path(self, v, c4_pre, c5_pre, monkeypatch):
        with warnings.catch_warnings():
            warnings.simplefilter("error", _COMPLEX_WARNING)
            out = _s9(_vnode(v), monkeypatch)                    # 不得拋（修前 10**400 拋 OverflowError）
        md = _md(out)
        assert _C4_BAD in md and _C5_NO_VIX in md, md[-2:]
        if c4_pre is not None:                                    # 修前（寫死）的假「安全／極度平靜」不再出現
            assert c4_pre not in md and c5_pre not in md
        joined = "\n".join(md)
        assert "（安全）" not in joined and "極度平靜" not in joined and "VIX=" not in joined

    @pytest.mark.parametrize("v,c4_pre,c5_pre", _S9_NEWLY_INVALID)
    def test_invalid_equals_missing_except_deleted_clause(self, v, c4_pre, c5_pre, monkeypatch):
        out = _s9(_vnode(v), monkeypatch)
        base = _s9(_vnode(None), monkeypatch)
        assert sum(t == _C4_MISSING for _k, t in base) == 1
        assert out == [(k, _C4_BAD if t == _C4_MISSING else t) for k, t in base]

    @pytest.mark.parametrize("v", _S9_HAS_VALUE_WAS_MISSING)
    def test_has_value_already_missing_drops_clause(self, v, monkeypatch):
        out = _s9(_vnode(v), monkeypatch)
        assert _C4_BAD in _md(out) and _C4_MISSING not in _md(out)

    @pytest.mark.parametrize("node", _S9_TRUE_MISSING)
    def test_true_missing_keeps_original_sentence(self, node, pre, monkeypatch):
        out = _s9(node, monkeypatch)
        assert _C4_MISSING in _md(out) and _C4_BAD not in _md(out)
        assert out == _s9(node, monkeypatch, mod=pre["cross"])

    @pytest.mark.parametrize("v,c4,c5", _S9_VALID)
    def test_valid_vix_golden(self, v, c4, c5, monkeypatch):
        md = _md(_s9(_vnode(v), monkeypatch))
        assert c4 in md and c5 in md, md[-2:]

    def test_k1_pure_deletion(self):
        # K1：新輸出只比既有句少字（整句只有一個子句 → 整句刪），不新增任何字
        assert _C4_BAD == _C4_MISSING.replace("VIX / CPI 數據載入中", "")
        assert _source(_CROSS).count("'VIX / CPI 數據載入中'") == 1


#: 其餘 `_num` 欄位：±inf／溢位 → 該欄位的既有缺值路徑（＝給 None 的輸出）。
#: (名稱, 給壞值的 kwargs, 給 None 的 kwargs, 修前（寫死）才有的字樣；修前拋例外時為 None)
_S9_FIELDS = [pytest.param(bad, none, pre_txt, id=i) for i, bad, none, pre_txt in (
    ("exp+inf", dict(base={**_S9_FULL, "tw_export": {"yoy": math.inf}}),
     dict(base={**_S9_FULL, "tw_export": {"yoy": None}}), "台灣出口YoY=+inf%"),
    ("exp-10**400", dict(base={**_S9_FULL, "tw_export": {"yoy": _HUGE}}),
     dict(base={**_S9_FULL, "tw_export": {"yoy": None}}), None),
    ("pmi+inf", dict(base={**_S9_FULL, "ism_pmi": {"value": math.inf}}),
     dict(base={**_S9_FULL, "ism_pmi": {"value": None}}), "台灣 PMI=inf"),
    ("cli-inf", dict(base={**_S9_FULL, "ism_pmi": {"value": -math.inf, "is_oecd_cli": True}}),
     dict(base={**_S9_FULL, "ism_pmi": {"value": None, "is_oecd_cli": True}}), "OECD CLI=-inf"),
    ("m1b+inf", dict(m1b={"m1b_yoy": math.inf, "m2_yoy": 5.0}), dict(m1b={"m1b_yoy": None, "m2_yoy": 5.0}),
     "M1B=inf%"),
    ("m2-inf", dict(m1b={"m1b_yoy": 5.0, "m2_yoy": -math.inf}), dict(m1b={"m1b_yoy": 5.0, "m2_yoy": None}),
     "M2=-inf%"),
    ("bias+inf", dict(bias={"bias_240": math.inf}), dict(bias={"bias_240": None}), "年線乖離+inf%"),
    ("sox+inf", dict(tech={"費城半導體 SOX": {"pct": math.inf}}), dict(tech={"費城半導體 SOX": {"pct": None}}),
     "SOX=+inf%"),
    ("nvda+inf", dict(tech={"輝達 NVDA": {"pct": math.inf}}), dict(tech={"輝達 NVDA": {"pct": None}}),
     "（半導體點火）"),
)]


class TestZ3n1NumOtherFields:
    @pytest.mark.parametrize("bad,none,pre_txt", _S9_FIELDS)
    def test_non_finite_equals_missing(self, bad, none, pre_txt, monkeypatch):
        out = _s9(_vnode(18.0), monkeypatch, **bad)               # 不得拋（修前 10**400 拋 OverflowError）
        assert out == _s9(_vnode(18.0), monkeypatch, **none)
        if pre_txt is not None:                                    # 修前（寫死）才有的字樣不再出現
            assert pre_txt not in "\n".join(_md(out))

    @pytest.mark.parametrize("bad,none,pre_txt", _S9_FIELDS)
    def test_premise_pre_fix_copy_used_the_value(self, bad, none, pre_txt, pre, monkeypatch):
        # 前提：修前副本在同一輸入印出寫死的字樣／整段拋例外（＝本列 bug）
        if pre_txt is None:
            with pytest.raises(OverflowError):
                _s9(_vnode(18.0), monkeypatch, mod=pre["cross"], **bad)
        else:
            assert pre_txt in "\n".join(_md(_s9(_vnode(18.0), monkeypatch, mod=pre["cross"], **bad)))

    @pytest.mark.parametrize("vma", [math.inf, -math.inf, _HUGE], ids=["+inf", "-inf", "10**400"])
    def test_vix_ma20_non_finite_drops_ma20_text(self, vma, monkeypatch):
        out = _s9({"current": 18.0, "ma20": vma}, monkeypatch)
        assert out == _s9({"current": 18.0}, monkeypatch)
        assert _g4_green("18.0").replace(" MA20=17.5", "") in _md(out)

    def test_finite_fields_identical_to_pre_fix(self, pre, monkeypatch):
        for kw in (dict(), dict(m1b={"m1b_yoy": 5.0, "m2_yoy": 3.0}), dict(bias={"bias_240": 20.0}),
                   dict(bias={"bias_240": -7.0}), dict(tech={"費城半導體 SOX": {"pct": 2.0}}),
                   dict(base={**_S9_FULL, "ism_pmi": {"value": 99.0, "is_oecd_cli": True}}),
                   dict(base={**_S9_FULL, "tw_export": {"yoy": -12.0}}), dict(base={})):
            for v in (18.0, 25.0, 35.0, None):
                assert _s9(_vnode(v), monkeypatch, **kw) == _s9(_vnode(v), monkeypatch, mod=pre["cross"], **kw)
                monkeypatch.undo()


#: ⛔ CPI 不套（C8-n7）：`96779d4` 實跑寫死，修後逐字相同（含 10**400 照舊拋）
#: 📌 批 Z9 第 2 組（C8-n7，客戶 2026-10-08 核字）起：VIX<20 且 CPI 非有限 ⇒ ④ 改印「CPI待取得」；
#:    修前（`96779d4`）這兩例印「⚠️ 美股承壓…CPI=inf%超標」／「🟢 美股平穩…CPI=-inf%」—— 原字面值保留於下方
#:    `_PRE_*` 並斷言不再出現。取數本身仍未改走 `_num`（10**400 照舊拋），故本類其餘斷言不變。
_C4_CPI_PENDING_18 = _card9("④ 美股動態", "#484f58", "VIX=18.0 CPI待取得", "CPI 數據未就緒，暫無法判斷降息預期")


class TestZ3n1CpiCarvedOut:
    _PRE_PLUS_INF = _card9("④ 美股動態", "#eab308", "⚠️ 美股承壓，Fed鷹派升溫",
                           "VIX=18.0 CPI=inf%超標 — 高利率環境延續，外資提款風險升高，注意匯率走勢")
    _PRE_MINUS_INF = _g4_green("18.0", " CPI=-inf%")

    def test_cpi_plus_inf_now_pending(self, monkeypatch):
        md = _md(_s9(_vnode(18.0), monkeypatch, base={**_S9_FULL, "us_core_cpi": {"yoy": math.inf}}))
        assert _C4_CPI_PENDING_18 in md and self._PRE_PLUS_INF not in md

    def test_cpi_minus_inf_now_pending(self, monkeypatch):
        md = _md(_s9(_vnode(18.0), monkeypatch, base={**_S9_FULL, "us_core_cpi": {"yoy": -math.inf}}))
        assert _C4_CPI_PENDING_18 in md and self._PRE_MINUS_INF not in md

    def test_cpi_huge_int_still_raises(self, monkeypatch):
        with pytest.raises(OverflowError):
            _s9(_vnode(18.0), monkeypatch, base={**_S9_FULL, "us_core_cpi": {"yoy": _HUGE}})


#: 只有 VIX 一項（其餘全缺）且無效：① 也走既有缺值卡（＝VIX 缺值時的輸出；`96779d4` 實跑寫死修前值）
class TestZ3n1OnlyVix:
    _C1_LOADING = _card9("① 目前總經位階", "#484f58", "資料載入中", "請先按上方「🚀 一鍵更新全部數據」")
    _C1_PRE = _card9("① 目前總經位階", "#eab308", "景氣位階資料未就緒",
                     "缺「台灣出口 YoY（財政部海關）＋ 台灣 PMI／OECD CLI」——這兩個景氣來源本次抓取失敗"
                     "（多為 CIER／財政部第三方鏡像暫時不可用）；其餘總經已載入。可於收盤後再按「🚀 一鍵更新全部數據」重試。")
    _C5_WAIT = _card9_5("#484f58", "⏳ 等待資料", "請先按上方「🚀 一鍵更新全部數據」載入資料後自動生成結論。")

    @pytest.mark.parametrize("v", [-5, True, "18.5", np.complex128(18)], ids=repr)
    def test_only_invalid_vix(self, v, monkeypatch):
        out = _s9({"current": v}, monkeypatch, base={})
        md = _md(out)
        assert self._C1_LOADING in md and self._C1_PRE not in md
        assert _C4_BAD in md and self._C5_WAIT in md
        base = _s9({"current": None}, monkeypatch, base={})
        assert out == [(k, _C4_BAD if t == _C4_MISSING else t) for k, t in base]

    def test_only_valid_vix_unchanged(self, monkeypatch):
        md = _md(_s9({"current": 18.0}, monkeypatch, base={}))
        assert self._C1_PRE in md
        assert _card9_5("#8b949e", "⏸️ 中性觀望，等待訊號", "VIX=18.0 安全窗口。") in md


# ══════════════════════════════════════════════════════════════════════════
# D. C7-n7：§八 VIX > 100 時 KPI 卡／否決清單不再自相矛盾
# ══════════════════════════════════════════════════════════════════════════
#: `96779d4` 實跑寫死
_KPI_PENDING = ('<div style="background:#161b22;border:1px solid #0d1117;border-radius:8px;padding:12px 14px;'
                'text-align:center;"><div style="font-size:10px;color:#484f58;margin-bottom:3px;">VIX 恐慌指數</div>'
                '<div style="font-size:20px;font-weight:900;color:#484f58;">待取得</div>'
                '<div style="font-size:10px;color:#8b949e;margin-top:3px;">≥22警戒 / ≥30危機→強制空手</div></div>')
_VETO_FIRED = "🚨 總經基本面否決檢查已觸發（展開看詳情）"
_OK_VIX_MISSING = "✅ 總經基本面否決檢查：無觸發（⚠️ VIX待取得，未納入任何判斷）"


def _veto_vix_line(txt):
    return ('<div style="border-left:3px solid #ef4444;padding:6px 12px;margin:4px 0;color:#ef4444;'
            f'font-size:13px;">🚨 VIX={txt} ≥ 30：全球流動性危機，無視所有技術面買訊，強制空手！</div>')


def _abnormal(txt):
    return f"❌ VIX 數值異常（{txt}），疑似 API 變數映射錯誤，結論暫不顯示。請重新整理。"


#: (值, 修前圖標題與否決清單裡的 VIX 字樣, 結論段 .0f 字樣)
_ABOVE_100 = [pytest.param(v, t, e, id=i) for v, t, e, i in (
    (100.0001, "100.0001", "100", "100.0001"), (150, "150", "150", "150"), (150.0, "150.0", "150", "150.0"),
    (1e300, "1e+300", format(1e300, ".0f"), "1e300"), (Decimal("150"), "150", "150", "Decimal(150)"),
    (np.float64(150.0), "150.0", "150", "np.float64(150)"),
)]


class TestC7n7Section8:
    @pytest.mark.parametrize("v,t,e", _ABOVE_100)
    def test_kpi_and_veto_list_take_missing_path(self, v, t, e, monkeypatch):
        out, calls = _mid(_node(v), monkeypatch)
        assert ("markdown", _KPI_PENDING) in out
        assert not any(k == "plotly_chart" for k, _t in out)
        assert ("success", _OK_VIX_MISSING) in out
        assert ("expander", _VETO_FIRED) not in out
        assert ("error", _abnormal(e)) in out and calls == []          # 結論段原句不動
        # 修前（寫死）：圖標題「🚨 恐慌衝頂，強制空手」＋否決清單「VIX=… ≥ 30…強制空手！」
        assert ("plotly_chart", f"VIX 恐慌指數 {t}（MA20=17.5）— 🚨 恐慌衝頂，強制空手") not in out
        assert ("markdown", _veto_vix_line(t)) not in out

    @pytest.mark.parametrize("v,t,e", _ABOVE_100)
    def test_upper_part_equals_missing_vix(self, v, t, e, monkeypatch):
        # 結論段之前（KPI、否決檢查、揭露框）＝ VIX 缺值時的輸出
        out, _ = _mid(_node(v), monkeypatch)
        base, _ = _mid({"current": None, "dates": ["2026-09-30", "2026-10-01"], "values": [18.0, 18.0]},
                       monkeypatch)
        i = out.index(("error", _abnormal(e)))
        j = base.index(("info", "VIX 數據載入中，VIX 否決權暫無法判斷"))
        assert out[:i] == base[:j]

    @pytest.mark.parametrize("v,t,e", _ABOVE_100)
    def test_only_vix_above_100_not_evaluable(self, v, t, e, monkeypatch):
        # 只有 VIX 一項且 > 100、其餘四項皆缺：基本面檢查不可評估（不印 ✅ 行、不印範圍註腳）＝ VIX 缺值時
        out, _ = _mid(_node(v), monkeypatch, base={})
        base, _ = _mid({"current": None, "dates": ["2026-09-30", "2026-10-01"], "values": [18.0, 18.0]},
                       monkeypatch, base={})
        assert not any(k == "success" and t2.startswith("✅ 總經基本面否決檢查") for k, t2 in out)
        assert not any(k == "caption" and t2.startswith("📌 本檢查只看【") for k, t2 in out)
        i = out.index(("error", _abnormal(e)))
        j = base.index(("info", "VIX 數據載入中，VIX 否決權暫無法判斷"))
        assert out[:i] == base[:j]

    @pytest.mark.parametrize("v,t", [(100, "100"), (100.0, "100.0"), (99.9, "99.9"), (30.0, "30.0")], ids=repr)
    def test_at_or_below_threshold_golden(self, v, t, monkeypatch):
        out, calls = _mid(_node(v), monkeypatch)
        assert ("plotly_chart", f"VIX 恐慌指數 {t}（MA20=17.5）— 🚨 恐慌衝頂，強制空手") in out
        assert ("expander", _VETO_FIRED) in out and ("markdown", _veto_vix_line(t)) in out
        assert calls == [(float(v),)] and not any(k == "error" for k, _t in out)

    def test_decimal_just_above_100_consistent_with_conclusion(self, monkeypatch):
        # 比較取 float(…)：結論段 float 後不超過門檻 → KPI／清單也照常（兩處不分歧）
        v = Decimal("100.0000000000000000001")
        out, calls = _mid(_node(v), monkeypatch)
        assert ("plotly_chart", f"VIX 恐慌指數 {v}（MA20=17.5）— 🚨 恐慌衝頂，強制空手") in out
        assert calls == [(100.0,)] and not any(k == "error" for k, _t in out)

    @pytest.mark.parametrize("thr,v,abnormal", [(50, 60.0, True), (50, 50.0, False), (40, 45.0, True)])
    def test_threshold_constant_drives_both_sites(self, thr, v, abnormal, monkeypatch):
        mod = _real(_MID)
        monkeypatch.setattr(mod, "_VIX_ABNORMAL_ABOVE", thr)
        out, calls = _mid(_node(v), monkeypatch)
        assert (("markdown", _KPI_PENDING) in out) is abnormal
        assert (("error", _abnormal(f"{v:.0f}")) in out) is abnormal
        assert (("success", _OK_VIX_MISSING) in out) is abnormal

    def test_constant_value(self):
        assert _real(_MID)._VIX_ABNORMAL_ABOVE == 100

    @pytest.mark.parametrize("v", [18.0, 25.0, 35.0, 99.9, 100, 5e-324, -5, math.nan, None, "18.5", True], ids=repr)
    def test_at_or_below_identical_to_pre_fix(self, v, pre, monkeypatch):
        for node in (_node(v), {"current": v}):
            assert _mid(node, monkeypatch) == _mid(node, monkeypatch, mod=pre["mid"])
            monkeypatch.undo()

    def test_disclosure_side_effect_pinned(self, monkeypatch):
        # 連帶變化（規格未明列；實作組回報後總管裁定「接受」，2026-10-05）：VIX > 100 且 §八 其餘總經有值時，
        #   §八 基本面檢查不再把 VIX 算成觸發，而 §三 的共用有效性規則不擋 > 100、照判 🔴 ⇒ 既有揭露框改為出現
        #   （修前：兩邊都「觸發」→ 不出）。接受理由同批 Z3 改判：揭露框如實寫出 §三 實際看的值（真實優先於
        #   表面一致，§1）。§三 是否也該擋 > 100 屬客戶待答的 Q-r8b（承接 C8-n3「VIX > 100 時各區不一致」），
        #   本批不動；Q-r8b 有答案後，本條依答案更新。
        out, _ = _mid(_node(150.0), monkeypatch, real_v4=True, fut=-40000.0)
        warns = [t for k, t in out if k == "warning" and "兩套判定結論不一致" in t]
        assert len(warns) == 1
        assert "（§三 籌碼）：🔴 紅燈　看的是 VIX=150.0、外資期貨=-40,000 口" in warns[0]
        assert "（本區）：✅ 無觸發" in warns[0]


# ══════════════════════════════════════════════════════════════════════════
# E. C7-n3 (b)：section_health_score `_v4_fut2` 預設 0.0 → None（畫面零變化）
# ══════════════════════════════════════════════════════════════════════════
def _df2():
    n = 80
    close = [100.0 + 0.3 * i + (2.0 if i % 7 == 0 else -1.0) for i in range(n)]
    return pd.DataFrame({"date": pd.date_range("2026-01-01", periods=n), "close": close,
                         "open": [c - 0.5 for c in close], "low": [c - 1.5 for c in close],
                         "high": [c + 1.5 for c in close], "volume": [3000.0 + 10 * i for i in range(n)],
                         "外資": [float((i * 37) % 200 - 100) for i in range(n)],
                         "投信": [float((i * 13) % 20 - 10) for i in range(n)]})


def _health(li, mp, *, mod=None, force_fut=_DROP):
    """實跑個股健康度頁。回 (輸出, 交給 V4 引擎的 macro dict)；force_fut 可強制改寫引擎收到的期貨值。"""
    from src.compute.strategy.v4_strategy_engine import V4StrategyEngine as _engine_cls
    mod = mod or _real(_HEALTH)
    seen: list = []
    # ⛔ 不取 `mod.V4StrategyEngine`：同一支測試連呼叫多次時那是上一次的 _Spy（未 undo）→ 包成鏈，
    #   上一層的 force_fut 會蓋掉這一層的值。一律直接繼承 L2 本尊。
    assert mod.V4StrategyEngine is _engine_cls or issubclass(mod.V4StrategyEngine, _engine_cls)

    class _Spy(_engine_cls):
        def __init__(self, df, macro, shares):
            if force_fut is not _DROP:
                macro = {**macro, "foreign_futures": force_fut}
            seen.append(dict(macro))
            super().__init__(df, macro, shares)

    fake = _FakeST({"macro_info": {"vix": {"current": 18.0}}, "li_latest": li})
    mp.setattr(mod, "st", fake)
    mp.setattr(mod, "V4StrategyEngine", _Spy)
    mod.render_health_score_section("2330", 70.0, {}, _df2(), 100.0, None, None, None,
                                    55.0, 1.2, 0.5, 60.0, 55.0, None, None, None)
    assert len(seen) == 1
    return list(fake.out), seen[0]


_LI_DEFAULT = [pytest.param(None, id="li-None"), pytest.param(pd.DataFrame(), id="li-empty"),
               pytest.param(pd.DataFrame({"外資大小": pd.array([pd.NA], dtype="Float64")}), id="li-read-fails")]


class TestC7n3bHealthScore:
    @pytest.mark.parametrize("li", _LI_DEFAULT)
    def test_default_futures_is_none(self, li, monkeypatch):
        _out, macro = _health(li, monkeypatch)
        assert macro["foreign_futures"] is None                       # 修前（寫死）：0.0
        assert macro["vix"] == 18.0 and macro["pcr"] == 100.0

    @pytest.mark.parametrize("li", _LI_DEFAULT)
    def test_screen_does_not_depend_on_it(self, li, monkeypatch):
        # 畫面零變化：引擎收到 0.0 或 None，整頁輸出逐字相同（本頁不顯示引擎的總經燈）
        a, ma = _health(li, monkeypatch, force_fut=0.0)
        b, mb = _health(li, monkeypatch, force_fut=None)
        c, mc = _health(li, monkeypatch)
        assert ma["foreign_futures"] == 0.0 and mb["foreign_futures"] is None and mc["foreign_futures"] is None
        assert a == b == c

    @pytest.mark.parametrize("li", [*_LI_DEFAULT,
                                    pytest.param(pd.DataFrame({"外資大小": [-40000.0], "選PCR": [90.0]}), id="fut"),
                                    pytest.param(pd.DataFrame({"選PCR": [90.0]}), id="fut-col-missing"),
                                    pytest.param(pd.DataFrame({"外資大小": [math.nan]}), id="fut-nan")])
    def test_screen_identical_to_pre_fix(self, li, pre, monkeypatch):
        now, m_now = _health(li, monkeypatch)
        old, m_old = _health(li, monkeypatch, mod=pre["health"])
        assert now == old
        if li is not None and not li.empty and "外資大小" in li.columns and not li["外資大小"].isna().all():
            assert m_now == m_old                                      # 有值時引擎輸入不變

    def test_value_present_passes_through(self, monkeypatch):
        _out, macro = _health(pd.DataFrame({"外資大小": [-40000.0], "選PCR": [90.0]}), monkeypatch)
        assert macro == {"vix": 18.0, "foreign_futures": -40000.0, "pcr": 90.0}


# ══════════════════════════════════════════════════════════════════════════
# F. K1：本批不新增任何使用者看得到的字句（只比對本批改動處；docstring 除外）
# ══════════════════════════════════════════════════════════════════════════
def _str_consts(code: str) -> set[str]:
    tree = ast.parse(code)
    docs = {id(n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)}
    return {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs}


@pytest.mark.parametrize("name", list(_REVERT))
def test_k1_no_new_string_literals(name):
    now = _source(_SPECS[name])
    old = _apply(now, _REVERT[name])
    assert _str_consts(now) - _str_consts(old) == set()
