"""批 Z28 —— 客戶 2026-10-09 裁示 Q-z4～Q-z6（基底 origin/main `d88fe462`）。

客戶裁示原文（逐字）：「1. C8-n1 (b)：A　2. Z19-n8：A　3. Z6-n1：A　依既有有限自主巡航規則執行。C8-n1 (b) 僅使用
同頁既有「📌 外資期貨 未取得」，不得自行新增字句。Z19-n8 依既定原則，剛好等於門檻判較差側。Z6-n1 僅刪除未使用欄位及
因此失實的那一句，其餘文字與行為不動。」

- C8-n1 (b)（L5 `section_chips.py` §三 外資期貨快速結論卡）：外資大小欄有有限值、但末列非有限（None／NaN／±inf／
  pd.NA）時，修前印「外資期貨 nan口 → 外資期貨微空 nan口，水位正常」（None／pd.NA 則 TypeError）⇒ 改走同頁 v5 段
  既有字「📌 外資期貨 未取得」（逐字、灰色）；卡片其餘部分（「外資期貨留倉」）沿用同卡既有無資料分支。
- Z19-n8（L2 `V4StrategyEngine.check_macro_veto`）：外資期貨剛好 −20,000／−10,000 口歸較差側（`<` → `<=`）。
- Z6-n1（L3 `SectionInputs.futures_net` 刪除；`macro_refresh_service.UNTOUCHED_BLOCKS` 只刪一句）。

golden：修前輸出於基底 `d88fe462` 以本檔同一支 `_chips`／`_veto` 實跑後寫死（⛔ 不由現行碼反推）。

還原 helper（`pre_z28_v4_class` / `use_pre_z28_v4` / `_pre_chips_module`）：以原始碼**恰一次**字面替換建立「修前」
變體（不進 sys.modules、不碰本尊）；`TestRevertedCopyIsTheBase` 證明還原體重現基底 golden。既有測試
（test_batch_z20／z21／z22／z23）中剛好落在 −20,000 的 golden 改用 `use_pre_z28_v4` 保留原 digest。
"""
from __future__ import annotations

import dataclasses
import functools
import hashlib
import importlib.util
import math
import types

import numpy as np
import pandas as pd
import pytest

import src.compute.strategy.v4_strategy_engine as V4MOD
import src.services.allocation_service as AS
import src.services.macro_refresh_service as R
import src.ui.tabs.macro.section_chips as SC
from shared.colors import TRAFFIC_NEUTRAL
from src.compute.strategy import V4StrategyEngine
from src.services.section_inputs import SectionInputs, load_section_inputs
from src.ui.render.ui_widgets import STRATEGY_TECHNICAL, strategy_conclusion
from tests.test_m2n2_no_zero_fill import _FakeST


# ══════════════════════════════════════════════════════════════════════════
# 還原 helper（測試用）
# ══════════════════════════════════════════════════════════════════════════
def _variant_module(mod, pairs, tag):
    src = open(mod.__file__, encoding='utf-8').read()
    for old, new in pairs:
        assert src.count(old) == 1, f'替換點不唯一或已不存在：{old!r}'
        src = src.replace(old, new)
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(f'_z28_{tag}', loader=None))
    m.__file__ = mod.__file__
    exec(compile(src, mod.__file__, 'exec'), m.__dict__)
    return m


_PRE_V4_PAIRS = (
    ("                    and futures <= FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS)\n",
     "                    and futures < FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS)\n"),
    ("                       and futures <= FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS)\n",
     "                       and futures < FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS)\n"),
)

_PRE_CHIPS_PAIRS = (
    ("        _fut4_any = ('外資大小' in _li4.columns\n"
     "                     and any(_finite_yoy({'v': _v}, 'v') is not None for _v in _li4['外資大小']))\n"
     "        _fut4 = (_finite_yoy({'v': _li4.iloc[-1].get('外資大小')}, 'v') if _fut4_any else None)\n"
     "        _fut4 = float(_fut4) if _fut4 is not None else None\n"
     "        if _fut4 is None and _fut4_any:\n"
     "            _l4c = '📌 外資期貨 未取得'\n"
     "            _l4a = ''\n"
     "            _l4_ind = '外資期貨留倉'\n"
     "            _l4_color = TRAFFIC_NEUTRAL\n"
     "        elif _fut4 is not None:\n",
     "        _fut4 = (float(_li4.iloc[-1].get('外資大小', 0))\n"
     "                 if '外資大小' in _li4.columns\n"
     "                 and any(_finite_yoy({'v': _v}, 'v') is not None for _v in _li4['外資大小'])\n"
     "                 else None)\n"
     "        if _fut4 is not None:\n"),
    ("        st.markdown(strategy_conclusion(STRATEGY_TECHNICAL, _l4_ind, _l4c, _l4a, color=_l4_color),\n"
     "                    unsafe_allow_html=True)\n",
     "        st.markdown(strategy_conclusion(STRATEGY_TECHNICAL, _l4_ind, _l4c, _l4a), unsafe_allow_html=True)\n"),
)


@functools.lru_cache(maxsize=None)
def pre_z28_v4_class():
    """基底 d88fe462 的 V4StrategyEngine（外資期貨兩個判式還原為嚴格 `<`）。"""
    return _variant_module(V4MOD, _PRE_V4_PAIRS, 'v4').V4StrategyEngine


def use_pre_z28_v4(monkeypatch, mod=SC):
    """讓 §三（`mod`）的 v4 引擎風險燈改用修前引擎 —— 供既有 golden 剛好落在 −20,000／−10,000 的情境保留原 digest。"""
    monkeypatch.setattr(mod, 'V4StrategyEngine', pre_z28_v4_class())


_QZ7_NEW_SCOPE = '空單達 2 萬口 紅燈／達 1 萬口 黃燈'
_QZ7_OLD_SCOPE = '空單超過 2 萬口 紅燈／超過 1 萬口 黃燈'


def use_pre_qz7_scope(monkeypatch, mod=SC):
    """讓 §三（`mod`）v4 卡範圍說明恰一次還原為 Q-z7 修字前（「超過」）—— 供修字前寫死的 §三 golden 保留原 digest。"""
    note = mod.VETO_V4_ENGINE_SCOPE_NOTE
    assert note.count(_QZ7_NEW_SCOPE) == 1
    monkeypatch.setattr(mod, 'VETO_V4_ENGINE_SCOPE_NOTE', note.replace(_QZ7_NEW_SCOPE, _QZ7_OLD_SCOPE))


@functools.lru_cache(maxsize=None)
def _pre_chips_module():
    # 📌 批 Z30（Z29-n2，客戶 2026-10-09 核准，有意識的更正，⛔ 不是漏改）：本還原體定義為「基底 d88fe462」，
    #   故連同批 Z30 的各處（§三 ffill、訊號 5 末列缺值；批 Z30 續：`read_v4_macro_veto` 的 ffill）一併換回基底寫法
    #   （`Z30_CHIPS_REVERT_PAIRS`，同樣恰一次替換）。
    # 📌 批 Z31（Q-z10／Q-z11，客戶 2026-10-10 核准，有意識的更正，⛔ 不是漏改）：同理連同批 Z31 各處一併換回基底寫法
    #   （`Z31_CHIPS_REVERT_PAIRS`，同樣恰一次替換）。
    from tests.test_batch_z30 import Z30_CHIPS_REVERT_PAIRS
    from tests.test_batch_z31 import Z31_CHIPS_REVERT_PAIRS
    return _variant_module(SC, _PRE_CHIPS_PAIRS + Z30_CHIPS_REVERT_PAIRS + Z31_CHIPS_REVERT_PAIRS, 'chips')


def _digest(out) -> str:
    return hashlib.sha256('\x1e'.join(f'{k}\x1f{t}' for k, t in out).encode('utf-8')).hexdigest()


def _chips(li, mp, mod=SC):
    """實跑 §三（法人／融資空、VIX 15、先行指標 = li）；與 test_batch_z10 `_chips` 同一套設定，可指定模組。"""
    fake = _FakeST({"macro_info": {"vix": {"current": 15.0, "ma20": 15.0}}, "li_latest": li})
    mp.setattr(mod, "st", fake)
    mp.setattr(AS, "get_allocation", lambda *a, **k: types.SimpleNamespace(
        is_loaded=False, range_text="", capped=False, cap_text="", final_hi=None))
    mp.setattr(AS, "get_allocation_sleeves", lambda *a, **k: None)
    mod.render_section_chips({}, None, {})
    return list(fake.out)


def _li(fut, pcr=None, *, dtype=None):
    n = len(fut)
    d = {"日期": [f"2026-10-0{i + 1}" for i in range(n)], "外資大小": pd.Series(fut, dtype=dtype)}
    if pcr is not None:
        d["選PCR"] = pcr
    return pd.DataFrame(d)


_N, _I = math.nan, math.inf

# ══════════════════════════════════════════════════════════════════════════
# 1. C8-n1 (b)
# ══════════════════════════════════════════════════════════════════════════
#: 修後卡片：「外資期貨留倉」＝同卡既有無資料分支的指標字；「📌 外資期貨 未取得」＝同頁 v5 段既有字（逐字）；灰色。
_CARD_NEW = strategy_conclusion(STRATEGY_TECHNICAL, '外資期貨留倉', '📌 外資期貨 未取得', '', color=TRAFFIC_NEUTRAL)
#: C8-n1 (a) 既有分支（整欄無有限值），本批不動
_CARD_A = strategy_conclusion(STRATEGY_TECHNICAL, '外資期貨留倉', '先行指標欄位異常，請確認 FinMind Token', '')

_A_NEUTRAL = '依個股技術面操作，保留備用現金　→ 實際持股見 🎚️ 建議持股油門'
#: 末列非有限、修前不拋的情境：(建構, 修前該卡逐字, 修前整段 §三 sha256〔基底 d88fe462 實跑〕)
_LAST_NONFINITE_BASE = {
    'last_nan': (lambda: _li([-16000.0, _N], [100.0, 110.0]),
                 strategy_conclusion(STRATEGY_TECHNICAL, '外資期貨 nan口 | PCR 110.0',
                                     '外資期貨微空 nan口，水位正常，依個股技術面操作', _A_NEUTRAL),
                 '01806854b9f7053085f6f99a3d0b05db5269ae7b371565e6d73ee39920fa7409'),
    'last_nan_nopcr': (lambda: _li([3000.0, _N]),
                       strategy_conclusion(STRATEGY_TECHNICAL, '外資期貨 nan口',
                                           '外資期貨微空 nan口，水位正常，依個股技術面操作', _A_NEUTRAL),
                       '755b27532847cb16fca5a184c60dd762d6a81612c1f3648c2ad502e089d702d3'),
    'last_inf': (lambda: _li([-16000.0, _I], [100.0, 110.0]),
                 strategy_conclusion(STRATEGY_TECHNICAL, '外資期貨 inf口 | PCR 110.0',
                                     '外資期貨多單 inf口，外資期貨翻多，燃料充足，積極作多',
                                     '順勢重壓強勢股　→ 實際持股見 🎚️ 建議持股油門'),
                 'f2741d88926418b2f7672e4733b1ac2d6aea4e2bd44d6bb4a21c36402dc7341a'),
    'last_ninf': (lambda: _li([5000.0, -_I], [100.0, 110.0]),
                  strategy_conclusion(STRATEGY_TECHNICAL, '外資期貨 -inf口 | PCR 110.0',
                                      '外資期貨空單 inf口 ≥ 30,000口，啟動強制防禦，等待空單回補',
                                      '啟動強制防禦，嚴禁追高攤平，保護本金　→ 實際持股見 🎚️ 建議持股油門'),
                  'b48b0779a97c2b7fc482053dd373da79c6128c0943b78c108b5e88f8bdb719fa'),
}
#: 末列 None／pd.NA：修前 `float()` 拋 TypeError（§三 之後整段不渲染），無 golden
_LAST_RAISED_BEFORE = {
    'last_none_obj': lambda: _li([-16000.0, None], [100.0, 110.0], dtype=object),
    'last_pdna_obj': lambda: _li([-16000.0, pd.NA], [100.0, 110.0], dtype=object),
    'last_f32_nan_obj': lambda: _li([-16000.0, np.float32(np.nan)], [100.0, 110.0], dtype=object),
}
_ALL_LAST_NONFINITE = {**{k: v[0] for k, v in _LAST_NONFINITE_BASE.items()}, **_LAST_RAISED_BEFORE}

#: 末列有限：修前整段 §三 sha256（基底 d88fe462 實跑；均不落在 −20,000／−10,000）
_FINITE_LAST_BASE = {
    'nan_then_m16000': (lambda: _li([_N, -16000.0], [100.0, 110.0]),
                        'c0d980e9e053c4e44bfa276eb59bf0db6a4477445d53e1490bc2a945bb68605e'),
    'm40000': (lambda: _li([-40000.0], [90.0]), '8b3174bd99a4407b5c1b8ddb524051db970790ccd2797f1471655e6fabfbeb95'),
    'p3000': (lambda: _li([1000.0, 3000.0], [100.0, 130.0]),
              'c83c814c50ebd60918c882514db719aa18e385a0f9f57170a97530758d285b80'),
    'm5000_nopcr': (lambda: _li([-5000.0]), '9ad96741c679801953264595d951bafb531db378c45213a5e0897d7a534de62a'),
}

_CONCL_BAD = ('nan口', 'inf口', '水位正常', '外資期貨翻多', '啟動強制防禦，等待空單回補', '空單累積中')


def _fut_cards(out):
    return [t for _k, t in out if '策略3' in t and '外資期貨' in t and ' → ' in t]


class TestC8n1bLastRowNonFinite:
    @pytest.mark.parametrize('case', sorted(_ALL_LAST_NONFINITE))
    def test_existing_unavailable_card(self, case, monkeypatch):
        out = _chips(_ALL_LAST_NONFINITE[case](), monkeypatch)
        texts = [t for _k, t in out]
        assert texts.count(_CARD_NEW) == 1, case
        assert _fut_cards(out) == [_CARD_NEW]
        for bad in _CONCL_BAD:
            assert bad not in _CARD_NEW
        assert 'PCR' not in _CARD_NEW
        assert TRAFFIC_NEUTRAL in _CARD_NEW
        # §三 之後照常渲染
        assert ('expander', '🔍 資料來源診斷（點此確認各欄數據正確性）') in out
        assert any('籌碼綜合判斷' in t for t in texts)

    @pytest.mark.parametrize('case', sorted(_LAST_NONFINITE_BASE))
    def test_only_the_card_changed_vs_base(self, case, monkeypatch):
        mk, old_card, base_d = _LAST_NONFINITE_BASE[case]
        # 📌 批 Z30（Z29-n2，客戶 2026-10-09 核准，有意識的更正，⛔ 不是漏改）：末列 NaN 不再被 ffill 成前一日 ⇒ 表格／v5 卡／v4 燈（批 Z30 續）／
        #   原始值／CSV 亦隨之改變（由 test_batch_z30 斷言）。本測試守的是「批 Z28 只改這張卡」⇒ 改用只把批 Z30 換回基底的
        #   還原體（`pre_z30_chips_module`，其餘批次改動保留）實跑，斷言強度不變。
        from tests.test_batch_z30 import pre_z30_chips_module
        _mod = pre_z30_chips_module()
        use_pre_qz7_scope(monkeypatch, _mod)   # golden 為 Q-z7 修字前實跑（見 use_pre_qz7_scope）
        out = _chips(mk(), monkeypatch, _mod)
        idx = [i for i, (_k, t) in enumerate(out) if t == _CARD_NEW]
        assert len(idx) == 1
        k = out[idx[0]][0]
        restored = out[:idx[0]] + [(k, old_card)] + out[idx[0] + 1:]
        assert _digest(restored) == base_d

    def test_phrase_is_the_same_page_existing_v5_phrase(self, monkeypatch):
        """「📌 外資期貨 未取得」是同頁 v5 段既有輸出（整欄缺值時即印），本批逐字沿用、未新增字。"""
        out = _chips(_li([None, None], [100.0, 110.0], dtype=object), monkeypatch)
        v5 = [t for _k, t in out if '💰 v5 動態配置' in t]
        assert len(v5) == 1 and '📌 外資期貨 未取得' in v5[0]


class TestC8n1bOtherPathsUnchanged:
    @pytest.mark.parametrize('case', sorted(_FINITE_LAST_BASE))
    def test_finite_last_digest_equals_base(self, case, monkeypatch):
        mk, want = _FINITE_LAST_BASE[case]
        if case == 'm5000_nopcr':
            # 📌 批 Z35（Q-z17，客戶 2026-10-10 核准 A，有意識的變更，⛔ 不是漏改）：本例「🎯 籌碼綜合判斷」只剩外資期貨
            #   1 項有效 ⇒ 結論改「⬜ 無法判定」（由 test_batch_z35 斷言）。本段 golden 為修前實跑 ⇒ 本例改用只把批 Z35
            #   換回的還原體實跑（同一套 `_chips` 設定），再照下方既有 `undo_qz11_card`，golden 不改。
            from tests.test_batch_z31 import pre_qz17_chips_module, undo_qz11_card
            _mod = pre_qz17_chips_module()
            use_pre_qz7_scope(monkeypatch, _mod)   # golden 為 Q-z7 修字前實跑
            assert _digest(undo_qz11_card(_chips(mk(), monkeypatch, _mod))) == want
            return
        use_pre_qz7_scope(monkeypatch)   # golden 為 Q-z7 修字前實跑
        # 📌 批 Z31（Q-z11，客戶 2026-10-10 核准，有意識的更正，⛔ 不是漏改）：「🎯 籌碼綜合判斷」卡缺項改列「📌 ○○ 未取得」、
        #   5 項全缺改「⬜ 無法判定」（由 test_batch_z31 斷言）。本段 golden 為修前實跑 ⇒ 以 `undo_qz11_card`（只把該卡換回修前，
        #   正確性由 test_batch_z31 以還原體實跑自證）後比對，golden 一字未改。
        from tests.test_batch_z31 import undo_qz11_card
        assert _digest(undo_qz11_card(_chips(mk(), monkeypatch))) == want

    @pytest.mark.parametrize('fut', [[None], [_N, _N], [_I, -_I]])
    def test_all_nonfinite_column_keeps_c8n1a_branch(self, fut, monkeypatch):
        out = _chips(_li(fut, [110.0] * len(fut), dtype=object), monkeypatch)
        assert _fut_cards(out) == [_CARD_A]


# ══════════════════════════════════════════════════════════════════════════
# 2. Z19-n8：v4 引擎外資期貨 −20,000／−10,000 等號判較差側
# ══════════════════════════════════════════════════════════════════════════
def _veto(vix, fut, cls=V4StrategyEngine):
    e = cls.__new__(cls)
    e.macro = {'vix': vix, 'foreign_futures': fut, 'pcr': None}
    return dict(e.check_macro_veto())


def _vd(r) -> str:
    return hashlib.sha256(repr(sorted(r.items())).encode()).hexdigest()


#: 基底 d88fe462 實跑 `check_macro_veto` 的 sha256（repr(sorted(items))）；本批預期不變的組合
_V4_BASE = {
    (None, None): '598acdbb961b41f1ba4d83f58977569a64ef9822058fffecd49f3572fe76413b',
    (None, -40000.0): '9c83c3d27ae7f221abf0cda473674954d09a2257366f4282b88af7ea5726c327',
    (None, -30000): '7db6327d86b8a5543d4fc90bf5c0a73d0b86e5fb37cb4803918fc0665f24f04b',
    (None, -20001): '41ba78462aa6a0b1dc0e130fa18b8cf4d8abbb56e69d67f585537dc3a1db669b',
    (None, -19999): 'e9655358d008dd8c32bbd89cb7bc02d45a8bc88240a25c74d38682f874dd2e2a',
    (None, -10001): '609b384b0860a0c0ea9d79d8a387efa23d3b4c2dd62d455541e36a85b30a82a3',
    (None, -9999): '86eb20fb73e1fecd8b57d9b4cca347cd6b077452cce2e1911de0337dbaaebe12',
    (None, 0): '27402b79970ec1ee3e8886e39f5db43c4124664bfa6a917aed45a01c966bac4b',
    (None, -20000.5): 'a852afbbc98a0c3ff256e59c7c391188e0e290fd3c4e28e7fab9d954347d2c0a',
    (None, -19999.5): '4088aef020892883c24a6623fc47677d656875261ba76b9e3f6f8af65395cfed',
    (None, -10000.5): '4287ad661d10bf2d80506ffa683984b507207c466dbf3512e9d6a6aa0ec58be7',
    (None, -9999.5): '342cc164681adfe3da51ddf268b8e5593ea5f7623dcaf168fc270390a97f26d9',
    (15.0, None): '9b6cf227e4c26e64ccd4730200cfc0b2dd82f1fe50f61930ecdbc56c74407b45',
    (15.0, -35000): '2e6ab4e1c31976b582ce3f8aca353df9ab52b3e1614e17e021e0afbb2e67f646',
    (15.0, -29999): '451f81c603ee2a1c6daf7032abf3bee889e3b48c0c5c64c45270d33829f28f3e',
    (15.0, -20001): '12d65e356198a3bfb300ef106a0a9ae14ee4d0f0dce1bded9c6276f422bea463',
    (15.0, -19999): '001140e0741c16b15630d15df5ca9dcb0f1ae28f032f684822de7b92496fc290',
    (15.0, -15000): '3a9e0ab0d6e3edf0e5c643a256e432d8491c20805def700a7b1c5f49dd7c2779',
    (15.0, -10001): 'cf7a2148c8667632ec7badca02cd3dc2d8a80447973dda8c3a0119249d48f1c8',
    (15.0, -9999): 'fc64271db8848ef9ad604476ea0aa42595ca2cd5823fc16331cc2bfac5e6ccde',
    (15.0, -1): 'dee80b191ddb3cb57f7f4c10d4bc8e5d812490354dc1981c570f6e1c5288ce35',
    (15.0, 5000): '42b9f782b85843527eb9ea7e05c68f80f680c8a89debafcf57ad06f42c74fd1d',
    (15.0, -20000.5): '567ab8036cc25e1a41607074431c33a17b3f0de00c3c4289a5eca5747f1423e2',
    (15.0, -19999.5): 'cc04f234a6f3922344338c37592136b00aeadfcef453fb1fa6a4648dc024e5b2',
    (15.0, -10000.5): 'ddc3c72cedfb200b195e79950e7329b54f723c9733634247ba71d587462b8c17',
    (15.0, -9999.5): '84a36ba4b1d8a8524a4404b3f5fe6a19a5ceae7679b6851aae0d11675ff2323c',
    (22.0, None): '2882a9bbea6a44c2ca07ee3cee4eb50b22c8370fe384d29f329cc15317177e22',
    (22.0, -20001): '379e645c4fa6c1b2488dc7efad4ccf1d4c23148605c85440863d0e5f23331ce4',
    (22.0, -19999): '59249daeb34d5a09b95e5e3d6dd3cf9bd58f8e28faf1504c12f5d321809c388e',
    (22.0, -10000): 'f7dde759963471ae4f7b90456604d23347fff26fb073e4dd91d12ae47369da58',   # 黃→黃，不變
    (22.0, 0): '7ffb73d84de54510ed40ad1b072061bfad64009e76a106338947a693f5a2d9f9',
    (30.0, -20000): '71144612d15a09a0f21060adef6c12ff101bf8d3c1287631ff4e5fecec425540',   # 紅→紅，不變
    (30.0, -10000): 'ff1365dd9b0e7675584c9c06b924b1609c9bf1e972576896d5773fa787a7945a',   # 紅→紅，不變
    (30.0, 5000): '45624b8640372bd2807903d5bced1b2e6443336580f644a0bb9bb10e2bd96ccf',
}

#: 基底 d88fe462 實跑：剛好等於門檻、本批預期改變的組合（修前 digest，供還原體自證）
_V4_BASE_EDGE = {
    (None, -20000): '603b02ad6cedac79cc207c76ab2cb70f4ed10e274dd09aa264d033c7421380be',   # 修前 🟡
    (None, -10000): 'b0d4c4806a9131b57c75383dc04627062d33bb0f6b7e90b72408e92aeeea0706',   # 修前 ⬜
    (15.0, -20000): 'ef37f082eebacd8e974654e444bd8f314cdc31d3fde6a20a1e8a840a38090345',   # 修前 🟡
    (15.0, -10000): '15027df696c62355222e4be45e20376930eb64ec2ad87e0ef80bac4883f07b75',   # 修前 🟢
    (22.0, -20000): '5150caccd09634815793afd965101ab470c388665edc915dca29c1a3c2696a0a',   # 修前 🟡
}


class TestZ19n8EqualsThresholdWorseSide:
    @pytest.mark.parametrize('fut', [-20000, -20000.0, np.float64(-20000)])
    @pytest.mark.parametrize('vix', [None, 15.0, 22.0])
    def test_minus_20000_is_red(self, vix, fut):
        r = _veto(vix, fut)
        _vix_txt = '未取得' if vix is None else f'{vix:.1f}'
        assert r['status'] == '🔴 紅燈' and r['max_position'] == 20
        assert r['msg'] == f'🚨 總經環境高風險！VIX={_vix_txt} / 外資期貨=-20,000口 — 建議持股 ≤20%，嚴禁追高攤平'
        assert r['futures'] == -20000.0 and r['vix'] == vix
        assert r['unknown'] == (('vix',) if vix is None else ())

    @pytest.mark.parametrize('fut', [-10000, -10000.0, np.float64(-10000)])
    @pytest.mark.parametrize('vix', [None, 15.0])
    def test_minus_10000_is_yellow(self, vix, fut):
        r = _veto(vix, fut)
        _vix_txt = '未取得' if vix is None else f'{vix:.1f}'
        assert r['status'] == '🟡 黃燈' and r['max_position'] == 50
        assert r['msg'] == f'⚠️ 大盤震盪中，VIX={_vix_txt} / 外資期貨=-10,000口 — 縮小部位，跌破防守線務必嚴格執行'
        assert r['futures'] == -10000.0

    @pytest.mark.parametrize('key', sorted(_V4_BASE, key=repr), ids=repr)
    def test_other_values_unchanged(self, key):
        assert _vd(_veto(*key)) == _V4_BASE[key]

    def test_neighbours_keep_their_side(self):
        assert _veto(15.0, -20001)['status'] == '🔴 紅燈' and _veto(15.0, -19999)['status'] == '🟡 黃燈'
        assert _veto(15.0, -10001)['status'] == '🟡 黃燈' and _veto(15.0, -9999)['status'] == '🟢 綠燈'

    def test_other_thresholds_untouched(self):
        """−29,999／−30,000 等與 v4 門檻無關的值、VIX 判式皆不變（VIX 剛好 25／20 仍是嚴格 `>`）。"""
        assert _veto(25.0, 0)['status'] == '🟡 黃燈' and _veto(20.0, 0)['status'] == '🟢 綠燈'
        assert _veto(15.0, -29999)['status'] == _veto(15.0, -30000)['status'] == '🔴 紅燈'


# ══════════════════════════════════════════════════════════════════════════
# 3. Z6-n1：刪除 SectionInputs.futures_net ＋ UNTOUCHED_BLOCKS 只刪一句
# ══════════════════════════════════════════════════════════════════════════
_FIELDS_BASE = ['macro_info', 'mkt_info', 'warroom_summary', 'm1b_m2_info', 'bias_info', 'cl_data', 'li_latest',
                'jingqi_info', 'news_items', 'last_inst', 'cl_ts', 'futures_net', 'last_inst_date', 'last_margin']
_OLD_WHY = ("**全 repo 沒有任何一處寫這個 key**（實測 0 個寫入點）——"
            "五桶取數對它一律吃 `state.get('futures_net', 0)` 的預設值。"
            "⚠️ 這不是本路徑的缺口，是全站的：舊分頁按一百次也一樣。"
            "（判燈實際用的是 `li_latest['外資大小']`，那一項本路徑有更新）")
_DELETED = "五桶取數對它一律吃 `state.get('futures_net', 0)` 的預設值。"
#: 基底 d88fe462 實跑：UNTOUCHED_BLOCKS 各列 `astuple` repr 的 sha256（futures_net 列為修前 why）
_BLOCKS_BASE = {
    'macro_alerts': 'a997f2827b19caccc6ee932f3cf67688c4aa9cc994f6d1d64ff15d7963969eb2',
    'warroom_summary / macro_state.json': '26b1b8bb86ff50b03e7b36f219d98516ff1624c498f6caa841badd8d8f217c2c',
    '_macro_news_items': '249781fbff2415cacd279dc98286e368bfb529b19379aa80786fa6c677672f56',
    'futures_net': 'd80873b360af55ef48602d1afb55771f519dd3492ae6b8cb40baf60b246b823e',
    'chips_loaded': 'a61bf752f623390386f2adf7315dc0b88e7d9e164532943f2ce3a43bc3bac271',
    'intl_snap / ma_snap': 'a93bedea4589dcbae033eb233743fa02673734d7a822fc9860f6a37cfd272b9d',
}
_STATE = {'macro_info': {'a': 1}, 'warroom_summary': {'jingqi_avg': 52.0, 'futures_net': -3},
          'cl_ts': '2026-10-09 10:00', 'futures_net': -5, '_last_inst': {'x': 1}, '_last_inst_date': 'd',
          '_last_margin': 2000.0, 'li_latest': 'L', '_macro_news_items': [1], 'bias_info': {'b': 1},
          'cl_data': {'c': 1}, 'm1b_m2_info': {'m': 1}, 'mkt_info': {'k': 1}}
#: 基底 d88fe462 實跑 `load_section_inputs(_STATE)` 除 futures_net 外各欄
_STATE_BASE = {'macro_info': {'a': 1}, 'mkt_info': {'k': 1}, 'warroom_summary': {'jingqi_avg': 52.0, 'futures_net': -3},
               'm1b_m2_info': {'m': 1}, 'bias_info': {'b': 1}, 'cl_data': {'c': 1}, 'li_latest': 'L',
               'jingqi_info': {'avg': 52.0}, 'news_items': [1], 'last_inst': {'x': 1}, 'cl_ts': '2026-10-09 10:00',
               'last_inst_date': 'd', 'last_margin': 2000.0}


def _block(key):
    (b,) = [b for b in R.UNTOUCHED_BLOCKS if b.session_key == key]
    return b


class TestZ6n1FieldRemoved:
    def test_field_gone_others_in_order(self):
        assert [f.name for f in dataclasses.fields(SectionInputs)] == [f for f in _FIELDS_BASE if f != 'futures_net']

    def test_other_fields_values_unchanged(self):
        o = load_section_inputs(_STATE)
        assert {f.name: getattr(o, f.name) for f in dataclasses.fields(o)} == _STATE_BASE
        assert not hasattr(o, 'futures_net')

    def test_session_key_no_longer_read(self):
        """欄位刪除的直接結果：session `futures_net`（全 repo 0 寫入點）怎麼放都不再被讀、也不再因 int() 拋例外。"""
        for v in (-5, 'abc', math.nan, math.inf, [1]):
            assert load_section_inputs({'futures_net': v}) == load_section_inputs({})


class TestZ6n1WhySentence:
    def test_only_that_sentence_removed(self):
        assert _OLD_WHY.count(_DELETED) == 1
        assert _block('futures_net').why == _OLD_WHY.replace(_DELETED, '')

    def test_rest_of_block_and_other_blocks_unchanged(self):
        assert [b.session_key for b in R.UNTOUCHED_BLOCKS] == list(_BLOCKS_BASE)
        for b in R.UNTOUCHED_BLOCKS:
            if b.session_key == 'futures_net':
                b = dataclasses.replace(b, why=_OLD_WHY)
            assert hashlib.sha256(repr(dataclasses.astuple(b)).encode()).hexdigest() == _BLOCKS_BASE[b.session_key]


# ══════════════════════════════════════════════════════════════════════════
# 還原體自證 ＋ 原 test_batch_z10 `b_last_nan`（兩項改動同時命中）
# ══════════════════════════════════════════════════════════════════════════
#: 原 test_batch_z10 `_UNCHANGED['b_last_nan']`（_li([-20000.0, NaN], [100.0, 110.0])）的修前 digest
_B_LAST_NAN_BASE = '42bcb378d663bd051421ba5ea2a4d8fa52692509353672be4282930cd19b83ff'


class TestRevertedCopyIsTheBase:
    """還原體（恰一次字面替換）重現基底 golden。⚠️ 正式碼字面一改，這裡會因找不到替換點而失敗 —— 那是字面錨點。"""

    @pytest.mark.parametrize('key', sorted(_V4_BASE_EDGE, key=repr), ids=repr)
    def test_pre_v4_edge(self, key):
        assert _vd(_veto(*key, cls=pre_z28_v4_class())) == _V4_BASE_EDGE[key]
        assert _vd(_veto(*key)) != _V4_BASE_EDGE[key]

    @pytest.mark.parametrize('key', sorted(_V4_BASE, key=repr), ids=repr)
    def test_pre_v4_others(self, key):
        assert _vd(_veto(*key, cls=pre_z28_v4_class())) == _V4_BASE[key]

    @pytest.mark.parametrize('case', sorted(_LAST_NONFINITE_BASE))
    def test_pre_chips(self, case, monkeypatch):
        mk, _old, base_d = _LAST_NONFINITE_BASE[case]
        use_pre_qz7_scope(monkeypatch, _pre_chips_module())
        assert _digest(_chips(mk(), monkeypatch, _pre_chips_module())) == base_d

    def test_b_last_nan(self, monkeypatch):
        """原 z10 `b_last_nan`：末列 NaN（卡片改「📌 外資期貨 未取得」）＋ ffill 後 −20,000（v4 燈 🟡→🔴）。"""
        pre = _pre_chips_module()
        monkeypatch.setattr(pre, 'V4StrategyEngine', pre_z28_v4_class())
        use_pre_qz7_scope(monkeypatch, pre)
        old = _chips(_li([-20000.0, _N], [100.0, 110.0]), monkeypatch, pre)
        assert _digest(old) == _B_LAST_NAN_BASE
        monkeypatch.undo()
        # 📌 批 Z30（Z29-n2，有意識的更正）：末列 NaN 不再 ffill ⇒ 現行碼另有表格／v5／原始值／CSV 差異（test_batch_z30 斷言）；
        #   本測試守「批 Z28 兩項改動恰改兩段」⇒ `new` 改用只把批 Z30 換回基底的還原體實跑。
        # 📌 批 Z30（續，總管裁定，有意識的更正，⛔ 不是漏改）：`read_v4_macro_veto` 亦不再 ffill ⇒ 現行碼此例 v4 燈
        #   不再是「ffill 後 −20,000 ⇒ 🔴」，改走引擎既有「⬜ 無法判定…外資期貨 未取得」（見本測試末段斷言）；
        #   上方 `old`＝還原體（ffill 加回）仍逐字等於舊 golden，下方 `new`（只換回批 Z30）仍證明批 Z28 恰改兩段。
        from tests.test_batch_z30 import pre_z30_chips_module
        _mod = pre_z30_chips_module()
        use_pre_qz7_scope(monkeypatch, _mod)
        new = _chips(_li([-20000.0, _N], [100.0, 110.0]), monkeypatch, _mod)
        assert len(new) == len(old)
        diff = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
        assert len(diff) == 2
        assert new[diff[0]][1] == _CARD_NEW
        assert '🔴 紅燈' in new[diff[1]][1] and '外資期貨=-20,000口' in new[diff[1]][1]
        assert '🟡 黃燈' in old[diff[1]][1]
        # 現行碼（批 Z30 續）：末日外資期貨缺 ⇒ v4 燈 ⬜ 無法判定、不再以前一日 −20,000 判 🔴；其餘段與 `new` 的差異由 test_batch_z30 守。
        monkeypatch.undo()
        cur = _chips(_li([-20000.0, _N], [100.0, 110.0]), monkeypatch)
        (v4,) = [t for _k, t in cur if '🏛️' in t and '引擎風險燈' in t]
        assert '⬜ 無法判定' in v4 and '外資期貨=未取得' in v4 and '-20,000' not in v4


# ══════════════════════════════════════════════════════════════════════════
# 4. Q-z7（客戶 2026-10-09 核准，原文：「照擬句修改，與 Z28 一起合併。目的僅為讓使用者可見說明與已核准的門檻
#    等號歸屬一致，不再延伸修改其他門檻、判定邏輯或字句。」）—— v4 外資期貨門檻說明字與 `<=` 一致
# ══════════════════════════════════════════════════════════════════════════
#: 基底 d88fe462（與本批修字前 4774e293 同）實跑 `render_tab_edu()` 整段輸出 sha256（72 段）
_EDU_BASE = 'e8f2b7635fb9740cea4cbf00e7103e5b74b88a545549f863788ab9a153fb2ae2'
#: (修後逐字, 修前逐字) —— 只有外資期貨 v4 門檻的比較符號 `<` → `≤`；VIX 的 `>` 不動
_EDU_PAIRS = (
    ('🟡 期貨淨部位 ≤ -10,000 口 ／ 🔴 ≤ -20,000 口；', '🟡 期貨淨部位 < -10,000 口 ／ 🔴 < -20,000 口；'),
    ('🔴 VIX > 25    或  期貨淨部位 ≤ -20,000 口', '🔴 VIX > 25    或  期貨淨部位 < -20,000 口'),
    ('🟡 VIX > 20 或  期貨淨部位 ≤ -10,000 口', '🟡 VIX > 20 或  期貨淨部位 < -10,000 口'),
)


def _edu_out(mp):
    import src.ui.tabs.tab_edu as M
    fake = _FakeST({})
    mp.setattr(M, 'st', fake)
    mp.setattr(M, '_fetch_fred_series_edu', lambda *a, **k: None)
    M.render_tab_edu()
    return list(fake.out)


class TestQz7Wording:
    def test_v4_engine_inputs_exact(self):
        from src.config import VETO_V4_ENGINE_INPUTS, VETO_V4_ENGINE_SCOPE_NOTE
        assert VETO_V4_ENGINE_INPUTS == ('VIX（超過 25 紅燈／超過 20 黃燈）× '
                                         '外資期貨淨口數（空單達 2 萬口 紅燈／達 1 萬口 黃燈）')
        assert '超過 2 萬口' not in VETO_V4_ENGINE_SCOPE_NOTE and '超過 1 萬口' not in VETO_V4_ENGINE_SCOPE_NOTE
        assert '空單達 2 萬口 紅燈／達 1 萬口 黃燈' in VETO_V4_ENGINE_SCOPE_NOTE

    def test_section3_v4_card_shows_new_scope(self, monkeypatch):
        out = _chips(_li([-16000.0], [110.0]), monkeypatch)
        cards = [t for _k, t in out if '🏛️ v4 引擎風險燈' in t]
        assert len(cards) == 1
        assert '空單達 2 萬口 紅燈／達 1 萬口 黃燈' in cards[0] and '超過 2 萬口' not in cards[0]
        assert 'VIX（超過 25 紅燈／超過 20 黃燈）' in cards[0]

    def test_edu_new_phrases_present_old_gone(self, monkeypatch):
        txt = '\x1e'.join(t for _k, t in _edu_out(monkeypatch))
        for new, old in _EDU_PAIRS:
            assert txt.count(new) == 1, new
            assert old not in txt, old

    def test_edu_only_these_three_changed_vs_base(self, monkeypatch):
        out = _edu_out(monkeypatch)
        joined = '\x1e'.join(f'{k}\x1f{t}' for k, t in out)
        for new, old in _EDU_PAIRS:
            assert joined.count(new) == 1
            joined = joined.replace(new, old)
        assert hashlib.sha256(joined.encode('utf-8')).hexdigest() == _EDU_BASE
