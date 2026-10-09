"""批 Z27：客戶 2026-10-09 裁示 Q-z1＝A、Q-z2＝A 的核准字句落地（三項）。

1. Q-z1（Z9-n8／Z19-n1）`section_cross_ai` §九⑤：⑤ 的輸入（景氣 PMI／CLI、M1B-M2 Gap、VIX、年線乖離、出口）
   至少一項有值、卻全落中性帶而沒有條列時，不再誤印「⏳ 等待資料」，改「⏸️ 中性」＋「總經已載入；有資料，
   判定為一般水準。」。⑤ 的輸入全缺（含 Z7-n1：VIX 有值但無效、其餘全缺）維持原「⏳ 等待資料」與原句。
2. Q-z2(a)（Z19-n3）`data_registry.EDU_GUIDE[FRED_NAPM]`：「< 50 → 🔴 製造業萎縮」→ 🟡；
   「< 46 持續 3 月」→「≤ 46 持續 3 月」；新增「≤ 46 → 🔴 嚴重收縮」。數字仍走 `§§PMI_*§§` token。
3. Q-z2(b)（Z19-n6）`section_mid` §八：§三 v4 燈「⬜ 無法判定」（外資期貨未取得）時不出「兩套判定結論不一致」框，
   改出 caption；§三 🟢／🟡／🔴 已判定時原框逐字不變。

對拍方式：`_REVERT` 把本批改動**恰一次**還原成修前（`e333e5ff`）原始碼（另以 sha256 釘住還原結果＝修前檔案），
其餘情境本尊與修前逐字相同；另有修前實跑寫死的 sha256 golden。
"""
from __future__ import annotations

import hashlib
import itertools
import math

import pytest

import tests.test_batch_z7 as Z7
from shared.fred_series import FRED_NAPM
from tests.test_m2n2_no_zero_fill import _apply

_CROSS = Z7._CROSS
_MID = Z7._MID

#: 本批核准字句（客戶 2026-10-09；逐字）
_C5_NEUTRAL = Z7._card9_5("#8b949e", "⏸️ 中性", "總經已載入；有資料，判定為一般水準。")
_C5_WAIT = Z7._card9_5("#484f58", "⏳ 等待資料", "請先按上方「🚀 一鍵更新全部數據」載入資料後自動生成結論。")
_CAP_FUT = "（§三 籌碼的「v4 引擎風險燈」因外資期貨未取得而無法判定，本區與該燈暫時無法比對）"
_BOX = "兩套判定結論不一致"

#: 修後 → 修前（每組恰好一處）
_REVERT = {
    "cross": ((
        "    elif _macro_info_for_s9 and any(_v is not None for _v in (_cycle_ref, _ai_gap, _ai_vix, _ai_bias, _ai_exp)):\n"
        "        # 批 Z27（Z9-n8／Z19-n1，客戶 2026-10-09 Q-z1＝A 核准字句）：⑤ 自己的輸入（景氣 PMI／CLI、\n"
        "        #   M1B-M2 Gap、VIX、年線乖離、出口）至少一項有值、只是全落在中性帶而沒有條列 ⇒ 資料其實已載入，\n"
        "        #   不得再印「⏳ 等待資料」。判定只看上方已驗證過的值（無效 VIX／±inf 皆已是 None）⇒\n"
        "        #   Z7-n1「有值但無效、其餘全缺」仍走下方原句。顏色沿用同卡「⏸️ 中性觀望」的灰。\n"
        "        #   另要求總經主資料 `macro_info` 確實在 session 且非空（沿用 `macro_trio_orchestrator` 寫入端的\n"
        "        #   truthy 守門）：逾時只留下 bias／M1B 時，PMI／出口／VIX 其實沒有，不得說「總經已載入」。\n"
        "        _ai5_txt  = '總經已載入；有資料，判定為一般水準。'\n"
        "        _ai5_clr, _ai5_icon = '#8b949e', '⏸️ 中性'\n", ""),),
    "mid": ((
        "    if (_fund_evaluable and _v4_light is not None\n"
        "            and str(_v4_light.get('status', '')).startswith('⬜') and not _has_veto):\n"
        "        # 批 Z27（Z19-n6，客戶 2026-10-09 Q-z2＝A 核准字句）：§三 判「⬜ 無法判定」（VIX 有效、外資期貨未取得；\n"
        "        #   VIX 無效時入口回 None，走下方既有缺值句）—— 那盞燈沒有結論，不得當成「有風險訊號」去比對而印\n"
        "        #   「兩套判定結論不一致」框；改出與下方缺值句同款的 caption。🟢／🔴／🟡 等已判定狀態走原框，一字未動。\n"
        "        #   總管裁定最小改動：只替換「原本會出框」的情境（`not _has_veto`）；本區已觸發時原本就不出框，維持不出。\n"
        "        st.caption(\n"
        "            f'（§三 籌碼的「{VETO_V4_ENGINE_NAME}」因外資期貨未取得而無法判定，'\n"
        "            '本區與該燈暫時無法比對）')\n"
        "    elif _fund_evaluable and _v4_light is not None:\n",
        "    if _fund_evaluable and _v4_light is not None:\n"),),
}
#: 還原後原始碼的 sha256 ＝ 修前（`e333e5ff`）檔案
_PRE_SHA = {
    "cross": "4de75dbc8790be46178b0ab3e555a912cf1bf33a211ac68bb247d4f70c836e5f",
    "mid": "2fc67cb9bce46be9e19f3b6ec1274d6156302d91298fdf7350384b758e5161c1",
}
_SPECS = {"cross": _CROSS, "mid": _MID}


def _sha(x) -> str:
    return hashlib.sha256(repr(x).encode("utf-8")).hexdigest()


def _pre_code(k):
    return _apply(Z7._source(_SPECS[k]), _REVERT[k])


class _LazyPre(dict):
    """修前副本，用到才建（突變驗證時本尊斷言先跑、不被還原失敗遮蔽）。"""

    def __missing__(self, k):
        self[k] = Z7._variant(_SPECS[k], _pre_code(k), f"z27_pre_{k}")
        return self[k]


@pytest.fixture(scope="module")
def pre():
    return _LazyPre()


def pre_mid():
    """給既有測試用：恰一次還原本批 §八 改動的修前副本。"""
    return Z7._variant(_MID, _pre_code("mid"), "z27_pre_mid_ext")


@pytest.mark.parametrize("k", sorted(_REVERT))
def test_revert_is_exact_pre_source(k):
    assert hashlib.sha256(_pre_code(k).encode("utf-8")).hexdigest() == _PRE_SHA[k]


# ══════════════════════════════════════════════════════════════════════════
# 1. Q-z1：§九⑤
# ══════════════════════════════════════════════════════════════════════════
def _s9(mp, *, pmi=None, cli=None, exp=None, vix=None, cpi=None, gap=None, bias=None, mod=None):
    info = {}
    if pmi is not None:
        info["ism_pmi"] = {"value": pmi}
    if cli is not None:
        info["ism_pmi"] = {"value": cli, "is_oecd_cli": True}
    if exp is not None:
        info["tw_export"] = {"yoy": exp}
    if cpi is not None:
        info["us_core_cpi"] = {"yoy": cpi}
    m1b = None if gap is None else {"m1b_yoy": 4.0 + gap, "m2_yoy": 4.0}
    b = None if bias is None else {"bias_240": bias}
    return Z7._s9(Z7._DROP if vix is None else {"current": vix}, mp, mod=mod, base=info, m1b=m1b, bias=b)


def _c5(out):
    c = [t for t in Z7._md(out) if "⑤ 結論" in t]
    assert len(c) == 1
    return c[0]


class TestQz1Section9:
    @pytest.mark.parametrize("kw", [
        # Z9-n8 實跑情境：PMI 缺、其餘有值且皆落中性帶
        dict(vix=25.0, cpi=2.8, exp=3.0, gap=0.5, bias=5.0),
        # Z19-n1：① neutral（PMI=50）且 VIX 20–30、Gap 0–1、乖離 −5~15、出口 −5~10
        dict(pmi=50.0, vix=25.0, gap=0.5, bias=5.0, exp=3.0),
        dict(pmi=50.0),                     # 只有 PMI=50
        dict(pmi=48.0),                     # ① 「景氣趨緩（出口待確認）」＝ neutral
        dict(cli=99.0),                     # CLI 收縮、出口缺
        dict(vix=25.0), dict(gap=0.5, cpi=2.5), dict(bias=5.0, cpi=2.5), dict(exp=-3.0),
        # macro_info 在（只有 ⑤ 不讀的 CPI）＋ bias／Gap 中性值
        dict(gap=0.5, bias=5.0, cpi=2.5),
    ], ids=["Z9-n8", "Z19-n1", "pmi50", "pmi48", "cli99", "vix25", "gap+cpi", "bias+cpi", "exp",
            "gap+bias+cpi"])
    def test_loaded_neutral_shows_approved_wording(self, kw, monkeypatch, pre):
        out = _s9(monkeypatch, **kw)
        assert _c5(out) == _C5_NEUTRAL
        assert "⏳ 等待資料" not in "".join(t for _k, t in out)
        # 修前：同一情境誤印「⏳ 等待資料」，其餘輸出逐字相同
        base = _s9(monkeypatch, mod=pre["cross"], **kw)
        assert _c5(base) == _C5_WAIT
        assert out == [(k, _C5_NEUTRAL if t == _C5_WAIT else t) for k, t in base]

    @pytest.mark.parametrize("kw", [
        dict(),                                        # 全缺
        dict(vix=-5), dict(vix=True), dict(vix="18.5"), dict(vix=math.inf),   # Z7-n1：VIX 有值但無效、其餘全缺
        dict(exp=math.inf), dict(bias=math.nan),        # 其他欄位非有限
        dict(cpi=2.5),                                 # 只有 CPI（⑤ 不讀 CPI）
        # QA：trio 逾時只留 bias／M1B、macro_info 從未寫入（空）⇒ 不得說「總經已載入」
        dict(bias=5.0), dict(gap=0.5), dict(bias=5.0, gap=0.5),
    ], ids=["all-missing", "vix-5", "vixTrue", "vix-str", "vix+inf", "exp+inf", "bias-nan", "cpi-only",
            "bias-only", "gap-only", "bias+gap"])
    def test_not_loaded_keeps_wait(self, kw, monkeypatch, pre):
        out = _s9(monkeypatch, **kw)
        assert _c5(out) == _C5_WAIT and _C5_NEUTRAL not in "".join(t for _k, t in out)
        assert out == _s9(monkeypatch, mod=pre["cross"], **kw)

    @pytest.mark.parametrize("macro_info", ["absent", None, {}], ids=["key-absent", "None", "empty"])
    def test_macro_info_missing_keeps_wait(self, macro_info, monkeypatch, pre):
        """QA：session 只有 bias_info／m1b_m2_info（`macro_info` 缺鍵／None／空）⇒ 「⏳」，與修前逐字相同。"""
        import src.services.allocation_service as AS
        import types

        def run(mod):
            ss = {"bias_info": {"bias_240": 5.0}, "m1b_m2_info": {"m1b_yoy": 4.5, "m2_yoy": 4.0}}
            if macro_info != "absent":
                ss["macro_info"] = macro_info
            fake = Z7._FakeST(ss)
            monkeypatch.setattr(mod, "st", fake)
            monkeypatch.setattr(AS, "get_allocation", lambda *a, **k: types.SimpleNamespace(is_loaded=False))
            mod.render_section_cross_ai({}, {})
            return list(fake.out)

        out = run(Z7._real(_CROSS))
        assert _c5(out) == _C5_WAIT and _C5_NEUTRAL not in "".join(t for _k, t in out)
        assert out == run(pre["cross"])

    def test_grid_only_neutral_case_changes(self, monkeypatch, pre):
        """全格點：本尊與修前只在「⑤ 輸入有值但無條列」那格不同，且只差 ⑤ 卡。"""
        n_changed = n_same = 0
        for pmi, exp, vix, gap, bias in itertools.product(
                (None, 45.0, 50.0, 52.0), (None, -10.0, 3.0, 12.0), (None, 12.0, 18.0, 25.0, 35.0),
                (None, -1.0, 0.5, 2.0), (None, -10.0, 5.0, 20.0)):
            kw = dict(pmi=pmi, exp=exp, vix=vix, gap=gap, bias=bias, cpi=2.5)
            out, base = _s9(monkeypatch, **kw), _s9(monkeypatch, mod=pre["cross"], **kw)
            has_input = any(v is not None for v in (pmi, exp, vix, gap, bias))
            if out == base:
                n_same += 1
                assert _c5(out) != _C5_NEUTRAL
                if _c5(out) == _C5_WAIT:
                    assert not has_input
            else:
                n_changed += 1
                assert has_input and _c5(base) == _C5_WAIT and _c5(out) == _C5_NEUTRAL
                assert out == [(k, _C5_NEUTRAL if t == _C5_WAIT else t) for k, t in base]
        assert n_changed > 0 and n_same > 0

    #: 修前（`e333e5ff`）實跑寫死：未改到的情境整段輸出 sha256
    _GOLD = {
        "all-missing": (dict(), "a5c4ba23768340423dafeeff58dd9574354bbea6e54ad1514813f90aaff544e6"),
        "bull": (dict(pmi=52.0, exp=12.0, vix=12.0, gap=2.0, bias=5.0, cpi=2.5), "b6a89afed81efdc0f2f548202b370009ee835ef7a9e18aa69813743859a7f7ff"),
        "bear": (dict(pmi=45.0, exp=-10.0, vix=35.0, gap=-1.0, bias=20.0, cpi=2.5), "39bac04eecc1a5b76ae6f30cd771f9e2bf30e421b01340f10ff6670443fa4673"),
        "mixed": (dict(pmi=50.0, exp=3.0, vix=18.0, gap=0.5, bias=5.0, cpi=2.5), "0d267e10a7af3c1ac0744840d1162a2b4cb5b8a0a0e7692ed4297e32def6fd2a"),
        "z7n1": (dict(vix=-5), "81401d2ffcaf54fc54c5de2bdd42bb74e90e749b17e0b3e5c6f45a1167d83493"),
    }

    @pytest.mark.parametrize("case", sorted(_GOLD))
    def test_unchanged_golden(self, case, monkeypatch):
        kw, sha = self._GOLD[case]
        assert _sha(_s9(monkeypatch, **kw)) == sha


# ══════════════════════════════════════════════════════════════════════════
# 2. Q-z2(a)：PMI 教學表
# ══════════════════════════════════════════════════════════════════════════
class TestQz2aEduPmi:
    _ROWS = [
        ("> 50", "🟢 製造業擴張"),
        ("= 50", "🟡 中性線（榮枯分水嶺）"),
        ("< 50", "🟡 製造業萎縮（通常伴隨股市修正）"),
        ("≤ 46", "🔴 嚴重收縮"),
        ("≤ 46 持續 3 月", "🚨 衰退強烈訊號（五桶「中期」紅線）"),
    ]

    def test_resolved_rows_exact(self):
        from shared.edu_tokens import edu_tokens, resolve_edu_rules
        from src.data.core.data_registry import EDU_GUIDE
        assert list(resolve_edu_rules(EDU_GUIDE[FRED_NAPM]["how_to_read"], edu_tokens())) == self._ROWS

    def test_numbers_come_from_tokens(self):
        from src.data.core.data_registry import EDU_GUIDE
        raw = EDU_GUIDE[FRED_NAPM]["how_to_read"]
        assert [c for c, _ in raw] == ["> §§PMI_YELLOW§§", "= §§PMI_YELLOW§§", "< §§PMI_YELLOW§§",
                                       "≤ §§PMI_RED§§", "≤ §§PMI_RED§§ 持續 3 月"]

    def test_red_label_is_existing_band_label(self):
        from shared.signal_thresholds import TW_PMI_CARD_BANDS
        assert TW_PMI_CARD_BANDS[-1][2] == "🔴 嚴重收縮"

    def test_old_rows_gone(self):
        from src.data.core.data_registry import EDU_GUIDE
        raw = EDU_GUIDE[FRED_NAPM]["how_to_read"]
        assert ("< §§PMI_YELLOW§§", "🔴 製造業萎縮（通常伴隨股市修正）") not in raw
        assert not any(c == "< §§PMI_RED§§ 持續 3 月" for c, _ in raw)

    #: 修前（`e333e5ff`）實跑寫死：PMI 以外整份 EDU_GUIDE（含 token 代入後）sha256
    _OTHERS_SHA = "9b0e473495ba5884a14417aef78ae31223161d562f601705fc1968bb912ffaea"

    def test_other_cards_unchanged(self):
        from shared.edu_tokens import edu_tokens, resolve_edu_rules, resolve_edu_tokens
        from src.data.core.data_registry import EDU_GUIDE
        tk = edu_tokens()
        rest = []
        for key in sorted(EDU_GUIDE, key=str):
            card = EDU_GUIDE[key]
            if key == FRED_NAPM:
                card = {k: v for k, v in card.items() if k != "how_to_read"}
            rest.append((key, repr(card)))
            if key != FRED_NAPM and card.get("how_to_read"):
                rest.append((key, list(resolve_edu_rules(card["how_to_read"], tk))))
            rest.append((key, resolve_edu_tokens(card.get("meaning", ""))))
        assert _sha(rest) == self._OTHERS_SHA


# ══════════════════════════════════════════════════════════════════════════
# 3. Q-z2(b)：§八 兩套判定框
# ══════════════════════════════════════════════════════════════════════════
def _mid(mp, *, fut, vix=18.0, veto=False, mod=None):
    base = dict(Z7._MID_BASE)
    if veto:
        base["ism_pmi"] = {"value": 45.0}
    return Z7._mid(Z7._node(vix), mp, mod=mod, real_v4=True, fut=fut, base=base)[0]


def _boxes(out):
    return [t for k, t in out if k == "warning" and _BOX in t]


class TestQz2bSection8:
    def test_caption_constant_matches_engine_name(self):
        from src.config.config import VETO_V4_ENGINE_NAME
        assert _CAP_FUT == f"（§三 籌碼的「{VETO_V4_ENGINE_NAME}」因外資期貨未取得而無法判定，本區與該燈暫時無法比對）"

    @pytest.mark.parametrize("fut", [None, float("nan")], ids=["none", "nan"])
    def test_unknown_light_caption_instead_of_box(self, fut, monkeypatch, pre):
        out = _mid(monkeypatch, fut=fut)
        assert _boxes(out) == [] and out.count(("caption", _CAP_FUT)) == 1
        base = _mid(monkeypatch, fut=fut, mod=pre["mid"])
        bx = _boxes(base)
        assert len(bx) == 1 and "⬜ 無法判定" in bx[0]           # 修前：誤出比對框
        assert out == [("caption", _CAP_FUT) if (k == "warning" and t == bx[0]) else (k, t) for k, t in base]

    #: 修前（`e333e5ff`）實跑寫死：§三 ⬜＋本區已觸發的整段 §八 sha256
    _GOLD_UNKNOWN_VETO = "cb59d1e4bc91fee2e66b0db8d91dbbe0b5ee065a0ec07aa6855ba60982e6892a"

    def test_unknown_light_with_veto_unchanged(self, monkeypatch, pre):
        # 總管裁定（最小改動）：§三 ⬜ 且本區已觸發 ⇒ 修前本就不出框，維持「不出框、也不出 caption」，整段與基底逐字相同
        out = _mid(monkeypatch, fut=None, veto=True)
        assert _boxes(out) == [] and ("caption", _CAP_FUT) not in out
        assert _sha(out) == self._GOLD_UNKNOWN_VETO
        assert out == _mid(monkeypatch, fut=None, veto=True, mod=pre["mid"])

    @pytest.mark.parametrize("fut,vix,veto", [
        (-40000.0, 18.0, False),      # 🔴 vs 無觸發 → 原框
        (-30000.0, 18.0, False),
        (5000.0, 18.0, True),         # 🟢 vs 已觸發 → 原框
        (5000.0, 18.0, False),        # 🟢 一致 → 無框
        (None, 26.0, False),          # VIX 26 → 🟡（已判定）→ 原框
        (-40000.0, 26.0, True),
    ])
    def test_judged_light_unchanged(self, fut, vix, veto, monkeypatch, pre):
        out = _mid(monkeypatch, fut=fut, vix=vix, veto=veto)
        assert ("caption", _CAP_FUT) not in out
        assert out == _mid(monkeypatch, fut=fut, vix=vix, veto=veto, mod=pre["mid"])

    def test_red_box_golden(self, monkeypatch):
        bx = _boxes(_mid(monkeypatch, fut=-40000.0))
        assert len(bx) == 1 and _sha(bx[0]) == "81fe46e5f8f665e813b1f76b9cb3769eba3cb53b8eabfc509536a72f4cae2d09"

    #: 修前（`e333e5ff`）實跑寫死：已判定情境整段 §八 sha256
    _GOLD = {
        (-40000.0, 18.0, False): "b5ab4d5f950b532524a9b868f5bc0e9cae33972b8fb2b4be63f1725d6a3fd06b",
        (5000.0, 18.0, True): "49135bcf7dc449e9323829cd776f389f71ff725e33c1c520d878173cbc38e9d5",
        (None, 26.0, False): "39da532279641d94f393d2dee14bbd8fd80c02a05f98971584c8554a053ff470",
    }

    @pytest.mark.parametrize("key", sorted(_GOLD, key=repr))
    def test_unchanged_golden(self, key, monkeypatch):
        fut, vix, veto = key
        assert _sha(_mid(monkeypatch, fut=fut, vix=vix, veto=veto)) == self._GOLD[key]

    def test_vix_missing_sentence_untouched(self, monkeypatch, pre):
        out = Z7._mid({"current": None}, monkeypatch, real_v4=True, fut=None)[0]
        assert ("caption", _CAP_FUT) not in out
        assert out == Z7._mid({"current": None}, monkeypatch, mod=pre["mid"], real_v4=True, fut=None)[0]
