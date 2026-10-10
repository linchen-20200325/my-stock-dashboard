"""批 Z33 第 2、3 項 —— 外資淨額「未觀測」（`InstNetDict.unobserved_net`）不得在消費端被當成真值。

依據：客戶 2026-10-10〈資料品質、資料來源與公式正確性治理規則〉六（禁止假補值／缺資料直接填 0、
缺乏足夠資料仍輸出看似正常的投資結論）＋ 第八節（稽核發現的明確 bug 可自主最小修復）。
先例：批 Z16 C9-n6 (a) `section_warroom` 改讀 `shared/inst_net.is_net_observed` 走既有「未知」。

兩個上游產生「未觀測」的路徑（L1／L3，本批 ⛔ 不動）：
- F1：`daily_data_fetchers._parse_bfi82u_rows` 缺外資列或值為 '--' → 預填 0.0 並記入 `unobserved_net`；
- F2：`macro_fetch_orchestrator.fetch_macro_bundle` FinMind 補救在外資 buy 或 sell 為 NaN 時
  fillna(0) 推出淨額（＝−sell 或 +buy，可達 ±數百億）→ 同樣只標 `unobserved_net`。

本批修的 7 個消費點（一律「未觀測 → 改走該處既有的缺值路徑」，不新增任何字）：
  mid   §八 三環 E 外資徽章（既有「E 外資未知」）
  news  §十一 Gemini prompt「外資現貨買賣超」行（既有「缺值整行不送」）
  chips §三 籌碼卡外資判斷＋柱狀圖（既有「外資買賣超 ⬜ 未取得」「…缺「外資」欄位…」「⬜ 未取得：外資…」）
  long  §七「新台幣／外資視角」外資買賣超片段（既有缺 key 時省略該片段）
  edu   教學分頁 BFI82U 即時值條（既有缺 key 時不出即時值條）
  recon 對帳面板健康評分 v1/v2（既有 fnet=None → ⬜ both_missing）
  op    個股即時操作建議 → L3 `generate_ai_comment`（送 None，L3 既有 `or 0` 不出外資句）

本檔驗：
  A. 觀測值（0、+150、−201；皆由真的 BFI82U 解析器產生）＋ plain dict 舊路徑 → 完整輸出 sha256
     與修前（基底 a56ccf37，`_PRE_FIX_GOLDEN`）逐字相同 —— golden 由修前碼實跑擷取，⛔ 不由現行碼反推。
  B. 未觀測（F1 缺列／'--'、F2 buy 或 sell NaN 的 ±大額假淨額）→ 完整輸出 ＝「同一份資料拿掉外資 key」
     的完整輸出（＝ 既有缺值路徑，逐字）；並另驗關鍵字串（不出假數字、不出 E 綠徽章、prompt 無外資行）。
  C. 突變：每處拿掉 `is_net_observed` 判斷（＝ 修前碼，反向替換恰一次）→ B 轉紅。
  D. 缺 key 情境修前修後相同。
"""
from __future__ import annotations

import functools
import hashlib
import importlib.util
import types

import pandas as pd
import pytest

import src.services.allocation_service as AS
from shared.inst_net import InstNetDict
from src.data.daily.daily_data_fetchers import _parse_bfi82u_rows
from tests.test_m2n2_no_zero_fill import _FakeST, _Rerun

_FK = '外資及陸資'

# ══════════════════════════════════════════════════════════════════════════
# 資料：觀測值／F1／F2／缺 key
# ══════════════════════════════════════════════════════════════════════════
_FIELDS = ['單位名稱', '買進金額', '賣出金額', '買賣差額']
_OTHER_ROWS = [
    ['自營商(自行買賣)', '1', '1', '1,000,000,000'],
    ['自營商(避險)', '1', '1', '-550,000,000'],
    ['投信', '1', '1', '1,230,000,000'],
]
_FOREIGN_ROW = '外資及陸資(不含外資自營商)'


def _bfi(foreign_cell=None):
    """真的 BFI82U 解析器；`foreign_cell=None` ⇒ 回應裡沒有外資列（F1 缺列）。"""
    rows = list(_OTHER_ROWS)
    if foreign_cell is not None:
        rows.append([_FOREIGN_ROW, '1', '1', foreign_cell])
    return _parse_bfi82u_rows(_FIELDS, rows)


def _f2(net):
    """F2 形狀：FinMind 補救外資 buy 或 sell 為 NaN → fillna(0) 推出的淨額，只標 `unobserved_net`。
    （外資 buy NaN、sell 300 億 ⇒ −300；sell NaN、buy 500 億 ⇒ +500。）"""
    return InstNetDict({_FK: {'net': net}, '投信': {'net': 20.0}, '自營商': {'net': 10.0}},
                       unobserved_net=(_FK,))


#: 觀測值（含觀測到的 0）—— 修前修後逐字相同
OBSERVED = {
    'obs_zero': lambda: _bfi('0'),
    'obs_buy_150': lambda: _bfi('15,000,000,000'),
    'obs_sell_201': lambda: _bfi('-20,100,000,000'),
    'plain_dict_150': lambda: {_FK: {'net': 150.0}, '投信': {'net': 12.3}, '自營商': {'net': 4.5}},
    'other_row_unobserved': lambda: InstNetDict(
        {_FK: {'net': -201.0}, '投信': {'net': 0.0}, '自營商': {'net': 4.5}}, unobserved_net=('投信',)),
}
#: 未觀測 —— 走既有缺值路徑
UNOBSERVED = {
    'f1_missing_row': lambda: _bfi(None),
    'f1_dashdash': lambda: _bfi('--'),
    'f2_buy_nan_sell_300': lambda: _f2(-300.0),
    'f2_sell_nan_buy_500': lambda: _f2(500.0),
}
#: 缺 key（既有路徑，修前修後相同）
MISSING_KEY = {
    'no_foreign_key': lambda: {'投信': {'net': 12.3}, '自營商': {'net': 4.5}},
}


def _drop_foreign(inst):
    """同一份資料、拿掉外資 key（＝ 既有缺值路徑的輸入）。"""
    return {k: v for k, v in inst.items() if k != _FK}


def test_fixtures_have_the_documented_shape():
    for name, mk in UNOBSERVED.items():
        inst = mk()
        assert isinstance(inst, InstNetDict) and _FK in inst.unobserved_net, name
        assert _FK in inst, name
    assert UNOBSERVED['f1_missing_row']()[_FK]['net'] == 0.0      # L1 預填
    assert UNOBSERVED['f1_dashdash']()[_FK]['net'] == 0.0
    for name in ('obs_zero', 'obs_buy_150', 'obs_sell_201'):
        assert _FK not in OBSERVED[name]().unobserved_net, name
    assert [OBSERVED[n]()[_FK]['net'] for n in ('obs_zero', 'obs_buy_150', 'obs_sell_201')] == [0.0, 150.0, -201.0]


# ══════════════════════════════════════════════════════════════════════════
# 7 個消費點的 runner（全部離線；吃模組物件：本尊／修前還原體）
# ══════════════════════════════════════════════════════════════════════════
class _FigST(_FakeST):
    """另記 `st.plotly_chart` 的柱狀圖 x／y／text（§三 三大法人柱狀圖）。"""

    def plotly_chart(self, fig, *a, **k):
        try:
            d = fig.data[0]
            self.out.append(('plotly', repr((tuple(d.x), tuple(d.y), tuple(d.text)))))
        except Exception:  # noqa: BLE001 —— 非柱狀圖照記型別
            self.out.append(('plotly', type(fig).__name__))
        return None


def _mods():
    import src.ui.pages.reconcile_panel as RP
    import src.ui.tabs.macro.section_chips as SC
    import src.ui.tabs.macro.section_long as SL
    import src.ui.tabs.macro.section_mid as SM
    import src.ui.tabs.macro.section_news_ai as SN
    import src.ui.tabs.stock_sections.section_op_recommendation as OP
    import src.ui.tabs.tab_edu as TE
    return {'mid': SM, 'news': SN, 'chips': SC, 'long': SL, 'edu': TE, 'recon': RP, 'op': OP}


def _run_mid(mod, inst, mp):
    import src.ui.tabs.macro.section_chips as SC
    fake = _FakeST({'cl_data': {'inst': inst}})
    mp.setattr(mod, 'st', fake)
    mp.setattr(AS, 'apply_vix_veto', lambda *a, **k: None)
    mp.setattr(AS, 'apply_ring_gate', lambda *a, **k: None)
    mp.setattr(AS, 'register_conflict', lambda *a, **k: None)
    mp.setattr(AS, 'get_allocation', lambda *a, **k: types.SimpleNamespace(is_loaded=False, final_hi=None))
    mp.setattr(SC, 'read_v4_macro_veto', lambda *a, **k: None)
    mod.render_section_mid(False, {}, {}, {})
    return list(fake.out)


def _run_news(mod, inst, mp):
    import src.data.news as N
    import src.services.app_ai_service as A
    fake = _FakeST({'cl_data': {'inst': inst}}, clicked={'btn_run_verdict'})
    prompts: list[str] = []

    class _Locker:
        def lock_system_state_only(self, state):
            pass

    def _gemini(prompt, max_tokens=2048):
        prompts.append(prompt)
        return '（測試替身報告）'

    mp.setattr(mod, 'st', fake)
    mp.setattr(mod, 'render_macro_bucket_summary_bar', lambda *a, **k: None)
    mp.setattr(mod, 'MacroStateLocker', _Locker)
    mp.setattr(A, 'gemini_call', _gemini)
    mp.setattr(N, 'fetch_macro_news', lambda *a, **k: [])
    try:
        mod.render_section_news_ai({}, 'unknown')
    except _Rerun:
        pass
    assert len(prompts) == 1
    return [('prompt', prompts[0])] + list(fake.out)


def _run_chips(mod, inst, mp):
    fake = _FigST({'macro_info': {'vix': {'current': 15.0, 'ma20': 15.0}}, 'li_latest': None})
    mp.setattr(mod, 'st', fake)
    mp.setattr(AS, 'get_allocation', lambda *a, **k: types.SimpleNamespace(
        is_loaded=False, range_text='', capped=False, cap_text='', final_hi=None))
    mp.setattr(AS, 'get_allocation_sleeves', lambda *a, **k: None)
    mod.render_section_chips(inst, None, {})
    return list(fake.out)


def _flow_snapshot():
    from shared.etf_universe import REGIONAL_ETFS
    out = {}
    for i, n in enumerate(REGIONAL_ETFS):
        out[n] = pd.DataFrame({'close': [100.0 + i + 0.5 * j * (1 + i % 3) for j in range(60)]})
    return out


def _run_long(mod, inst, mp):
    fake = _FakeST({'cl_data': {'inst': inst}})
    mp.setattr(mod, 'st', fake)
    mp.setattr(mod, 'render_macro_bucket_summary_bar', lambda *a, **k: None)
    mp.setattr(mod, 'fetch_flow_snapshot', _flow_snapshot)
    mp.setattr(mod, 'multi_chart', lambda *a, **k: None)
    mp.setattr(mod, '_fetch_otc_via_finmind', lambda *a, **k: None)   # 不觸網
    tw_s = {'新台幣匯率': {'pct': -0.3}}
    mod.render_section_long(True, {}, {}, {}, {}, {}, tw_s)
    return list(fake.out)


def _run_edu(mod, inst, mp):
    fake = _FakeST({'cl_data': {'inst': inst}})
    mp.setattr(mod, 'st', fake)
    mp.setattr(mod, '_fetch_fred_series_edu', lambda *a, **k: None)
    mod.render_tab_edu()
    return list(fake.out)


def _run_recon(mod, inst, mp):
    fake = _FakeST({'warroom_summary': {'jingqi_avg': 62.0},
                    'mkt_info': {'score': 3, 'max_score': 4},
                    'cl_data': {'inst': inst}})
    mp.setattr(mod, 'st', fake)
    rows = mod.compute_reconcile_rows()
    return [('row', repr(sorted(r.items()))) for r in rows] + [('caption', mod.reconcile_caption(rows))]


def _run_op(mod, inst, mp):
    fake = _FakeST({'cl_data': {'inst': inst}})
    seen: list = []
    from src.services.app_ai_service import generate_ai_comment as _real_gac

    def _spy(data):
        seen.append(data.get('foreign_buy', '<absent>'))
        return _real_gac(data)

    mp.setattr(mod, 'st', fake)
    mp.setattr(mod, 'generate_ai_comment', _spy)
    mp.setattr(AS, 'get_macro_regime', lambda *a, **k: {'is_loaded': False})
    mod.render_op_recommendation_section('2330', 82.0, {'contracting': True}, 5.0, 100.0, 55.0, 0, 0)
    assert len(seen) == 1
    return {'foreign_buy': seen[0], 'out': list(fake.out)}


_RUN = {'mid': _run_mid, 'news': _run_news, 'chips': _run_chips, 'long': _run_long,
        'edu': _run_edu, 'recon': _run_recon, 'op': _run_op}
_EXITS = sorted(_RUN)


def _screen(ek, r):
    """畫面（＋ prompt／對帳列）；op 的 `foreign_buy` 另驗。"""
    return r['out'] if ek == 'op' else r


def _digest(ek, r) -> str:
    out = _screen(ek, r)
    payload = '\x1e'.join(f'{k}\x1f{t}' for k, t in out)
    if ek == 'op':
        payload += f'\x1dforeign_buy={r["foreign_buy"]!r}'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _text(ek, r) -> str:
    return '\n'.join(t for _k, t in _screen(ek, r))


# ══════════════════════════════════════════════════════════════════════════
# 修前還原體（反向替換恰一次）＝ 每處拿掉 `is_net_observed` 判斷的突變體
# ══════════════════════════════════════════════════════════════════════════
_IMPORT = 'from shared.inst_net import is_net_observed  # 批 Z33：外資淨額未觀測（L1 預填／L3 補零推出）不當真值\n'
_M = '批 Z33（第 2／3 項，修正錯誤）'
#: 修後 → 修前（每組恰好一處；含本批加的說明註解行）。供其他測試檔的「還原成修前原始碼」沿用（同 Z30／Z31 慣例）。
Z33_INST_REVERT_PAIRS = {
    'mid': (
        (_IMPORT, ''),
        (f"            # {_M}：外資淨額未觀測（L1 缺列預填 0／L3 補零推出的假淨額）⇒ 走既有「E 外資未知」。\n"
         "            _fnet8    = (_inst8.get(_fk8, {}).get('net', None)\n"
         "                         if _fk8 and is_net_observed(_inst8, _fk8) else None)\n",
         "            _fnet8    = _inst8.get(_fk8, {}).get('net', None) if _fk8 else None\n"),
    ),
    'news': (
        (_IMPORT, ''),
        (f"                # {_M}：外資淨額未觀測 ⇒ 走上面既有「缺值整行不送」（不把假 0／假淨額送給 LLM）。\n"
         "                _fnet_v = (_inst_v.get(_fk_v, {}).get('net')\n"
         "                           if _fk_v and is_net_observed(_inst_v, _fk_v) else None)\n",
         "                _fnet_v = _inst_v.get(_fk_v, {}).get('net') if _fk_v else None\n"),
    ),
    'chips': (
        (_IMPORT, ''),
        (f"        # {_M}：外資淨額未觀測（L1 缺列預填 0／L3 補零推出）⇒ 同缺「外資」既有路徑（含下方柱狀圖「⬜ 未取得」）。\n"
         "        _fn3 = inst[_fk3]['net'] if _fk3 and is_net_observed(inst, _fk3) else None\n",
         "        _fn3 = inst[_fk3]['net'] if _fk3 else None\n"),
    ),
    'long': (
        (_IMPORT, ''),
        (f"        # {_M}：外資淨額未觀測 ⇒ 同缺 key 既有路徑（省略外資買賣超片段）；挑鍵沿用上一行 `or` 的同一順序。\n"
         "        _frn_k = '外資及陸資' if _inst_f.get('外資及陸資') else '外資'\n"
         "        _frn_net = (_frn.get('net')\n"
         "                    if isinstance(_frn, dict) and is_net_observed(_inst_f, _frn_k) else None)\n",
         "        _frn_net = _frn.get('net') if isinstance(_frn, dict) else None\n"),
    ),
    'edu': (
        (_IMPORT, ''),
        (f"                    # {_M}：外資淨額未觀測 ⇒ 同缺 key 既有路徑（不出即時值條）。\n"
         "                    if _foreign_key and is_net_observed(_inst, _foreign_key):\n",
         "                    if _foreign_key:\n"),
    ),
    'recon': (
        (_IMPORT, ''),
        (f"    # {_M}：L1 缺外資列預填的 0.0／L3 補零推出的假淨額同屬「沒載入」⇒ 同上走 None（⬜ both_missing）。\n"
         "    _fnet_raw = (_inst.get(_fk, {}).get('net')\n"
         "                 if _fk and is_net_observed(_inst, _fk) else None)\n",
         "    _fnet_raw = _inst.get(_fk, {}).get('net') if _fk else None\n"),
    ),
    'op': (
        (_IMPORT, ''),
        (f"            # {_M}：外資淨額未觀測 ⇒ 送 None，L3 既有 `or 0` 不出外資句（缺 key 仍照舊送 0）。\n"
         "            'foreign_buy': ((_inst_g.get(_fk_g, {}).get('net', 0)\n"
         "                             if is_net_observed(_inst_g, _fk_g) else None)\n"
         "                            if _fk_g else 0),\n",
         "            'foreign_buy': _inst_g.get(_fk_g, {}).get('net', 0) if _fk_g else 0,\n"),
    ),
}
_REVERT = Z33_INST_REVERT_PAIRS


def _revert(ek: str, code: str, pairs=None) -> str:
    for old, new in (pairs if pairs is not None else _REVERT[ek]):
        assert code.count(old) == 1, f'{ek} 替換點不唯一或已不存在：{old!r}'
        code = code.replace(old, new)
    return code


@functools.lru_cache(maxsize=None)
def _pre_fix(ek: str):
    real = _mods()[ek]
    code = _revert(ek, open(real.__file__, encoding='utf-8').read())
    assert 'is_net_observed' not in code and 'Z33' not in code, ek
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(f'_z33i_{ek}_pre', loader=None))
    m.__file__ = real.__file__
    exec(compile(code, real.__file__, 'exec'), m.__dict__)
    return m


#: 基底 a56ccf37 原始檔的 sha256（`git show a56ccf37:<檔>` 實算；寫死以免測試依賴外部 git）
_BASE_SHA = {
    'chips': '3aa598834619adeb1edf4b11d76cf3248a729fea968e1ee685e895ccfc449a3d',
    'edu': 'ed6cd7a9144bdf75e9c2d730c4df23de4dcec73d4720de5bd229a1b8cb874ce0',
    'long': 'ab864b4f7a11132d3c2281e7dbc5aaff5610100ac830a5bcba5fa37fe7639cd1',
    'mid': 'e1b9aa6da1b34a49de60e6cab2c56880b800f212f88ed8edd0c1dde9d3a99d58',
    'news': 'e89c96792fd44ab45df919cad3270a7107fd22fc76a60bd5c4030b979314dfc2',
    'op': 'f134989b5ec0bbab8666ffac07fccf07e539d8761f5b1aeb98b4008c2e50275b',
    'recon': '773ed539c378e420811fe8fbe66a5db4ca34f112a2bb6ad2a649a781c02e9fa2',
}


@pytest.mark.parametrize('ek', sorted(_BASE_SHA))
def test_pre_fix_body_equals_base_source(ek):
    """還原體（反向替換恰一次）與基底 a56ccf37 原始檔逐字相同（sha256）。"""
    code = _revert(ek, open(_mods()[ek].__file__, encoding='utf-8').read())
    assert hashlib.sha256(code.encode('utf-8')).hexdigest() == _BASE_SHA[ek]


# ══════════════════════════════════════════════════════════════════════════
# A. 觀測值：與修前實跑 golden 逐字相同
# ══════════════════════════════════════════════════════════════════════════
#: 修前碼（基底 a56ccf37）以本檔同一套 runner／資料實跑的完整輸出 sha256。⛔ 不由現行碼反推。
_PRE_FIX_GOLDEN: dict = {
    'chips': {
        'obs_zero': 'a578efde5eb29a3a8ff16ec75c289b16555c87fbe10e72ed2682662e8f147e66',
        'obs_buy_150': '36f1a8fd02f0e05866a817fb5093f5ac42342ddfe72672b32996fbb51a11fe7d',
        'obs_sell_201': 'ed839b12863136bd2310713d26122656c96010a354a530395e0d306b636a308a',
        'plain_dict_150': '36f1a8fd02f0e05866a817fb5093f5ac42342ddfe72672b32996fbb51a11fe7d',
        'other_row_unobserved': '5b6c18ebc59a77c1291dcc6206561a7feb934a9e33c951e446069a66dd95aee5',
        'no_foreign_key': 'b1cb6c1a52e984c3c3eb43d05caed3f52e876c888f2d72f512bf1f942ff3f52f',
    },
    'edu': {
        'obs_zero': '6615e09b117890768da7a9532b7295cae3a9093fd1623f4b6c5ba3b7a8aaabcc',
        'obs_buy_150': '56bdeb17524c199747a42c8fa6d4403f5648546236fbed91144e7dc803906920',
        'obs_sell_201': 'b6ffa52bf9281c7dad1c23daae3bd052a1df227337f0a02a4058f152316fd268',
        'plain_dict_150': '56bdeb17524c199747a42c8fa6d4403f5648546236fbed91144e7dc803906920',
        'other_row_unobserved': 'b6ffa52bf9281c7dad1c23daae3bd052a1df227337f0a02a4058f152316fd268',
        'no_foreign_key': '4727e9c0a53b37e048e2bb2f48633c21cc1ef96dcfd121454d7196fec978f881',
    },
    'long': {
        'obs_zero': 'e8e83ce4227ce8f18365a0f5861dc396f2eeb9a6f8835919470427397cf88c07',
        'obs_buy_150': '9cda3ec0d61ce97d49807a0cd59272842a7c14f67178e03ba206669b0dd86d70',
        'obs_sell_201': '71d2105515374c0a871386c92432a5bb8e242fdbef0afa898913e75a85ae106b',
        'plain_dict_150': '9cda3ec0d61ce97d49807a0cd59272842a7c14f67178e03ba206669b0dd86d70',
        'other_row_unobserved': '71d2105515374c0a871386c92432a5bb8e242fdbef0afa898913e75a85ae106b',
        'no_foreign_key': '58631bb31fe91ea02bf99fac039508b2b135638e3dc4d5bcdd3e3058f7f48f3f',
    },
    'mid': {
        'obs_zero': 'aa034dd6353ad21ee5cff6e2155a058bc4cb1dc46347cd019b5815ba5532d6c7',
        'obs_buy_150': 'c3de3edf689c8b2c71574fe568deccde1df4e2e0ffe3e9f2e0859aaa486d815a',
        'obs_sell_201': 'cfb7847b654b4aa98e2ba9528034d9555b632b08b491d0cd9ea2b4c4825461ae',
        'plain_dict_150': 'c3de3edf689c8b2c71574fe568deccde1df4e2e0ffe3e9f2e0859aaa486d815a',
        'other_row_unobserved': 'cfb7847b654b4aa98e2ba9528034d9555b632b08b491d0cd9ea2b4c4825461ae',
        'no_foreign_key': '7d37c96375a011d240af199f3e79026811d088d015fa17ecbaa4c2dd51eb7227',
    },
    'news': {
        'obs_zero': '9710122bf963b634e0abf5459a19b4602c65c510c7b56b78ed92b80f20b9741d',
        'obs_buy_150': '1efb4d79bed25fa965ac10306a145f9882d628b5b655fb67c63f7abb938c6eb3',
        'obs_sell_201': 'f60b5b96356840a427899d018bdd53f053806a3cde9f7d463e8ca16bc30dcf39',
        'plain_dict_150': '1efb4d79bed25fa965ac10306a145f9882d628b5b655fb67c63f7abb938c6eb3',
        'other_row_unobserved': '573e66c75e2879f1e4db7f93452798bedffbd285b5ed59e118b4eb2b3f864656',
        'no_foreign_key': '1d5e815b650b20a5410bfe4738d0125086f140eaa827678367bac51c56860a94',
    },
    'op': {
        'obs_zero': 'fd9efe0d8aa8c0f266e88a3c4b269d545886f76fef7e5689e5e248f60ea34c61',
        'obs_buy_150': 'a91c3b4931adbda4ba2f47381da44c2b48d6110ff73d8351a3bcf4dfb404f72f',
        'obs_sell_201': '2bd1df2b3f3ab637b79608878ebf2e676945064d318a9aef33a14fa950d4fc0b',
        'plain_dict_150': 'a91c3b4931adbda4ba2f47381da44c2b48d6110ff73d8351a3bcf4dfb404f72f',
        'other_row_unobserved': '2bd1df2b3f3ab637b79608878ebf2e676945064d318a9aef33a14fa950d4fc0b',
        'no_foreign_key': '66a13e22280d4afcbb776df664c6dd5b9c60a4294ab19c29bcd5c5a5336fd740',
    },
    'recon': {
        'obs_zero': 'a54bae64de73b804d134dce9f45c0ad110a01c6d4b0d2f3812f66c10bad4cdca',
        'obs_buy_150': '037d872e5480febe039ab9c0cfb1a1e01b0b606bbe853ad4aeb519346aeb7eda',
        'obs_sell_201': 'a54bae64de73b804d134dce9f45c0ad110a01c6d4b0d2f3812f66c10bad4cdca',
        'plain_dict_150': '037d872e5480febe039ab9c0cfb1a1e01b0b606bbe853ad4aeb519346aeb7eda',
        'other_row_unobserved': 'a54bae64de73b804d134dce9f45c0ad110a01c6d4b0d2f3812f66c10bad4cdca',
        'no_foreign_key': '6a06d6fcf074312f01c0e5419f1b0862012e6c3438a3c31e4f6223f2bca6d819',
    },
}


@pytest.mark.parametrize('ek', _EXITS)
@pytest.mark.parametrize('case', sorted(OBSERVED) + sorted(MISSING_KEY))
def test_observed_and_missing_key_identical_to_pre_fix_golden(ek, case, monkeypatch):
    mk = {**OBSERVED, **MISSING_KEY}[case]
    r = _RUN[ek](_mods()[ek], mk(), monkeypatch)
    assert _digest(ek, r) == _PRE_FIX_GOLDEN[ek][case]


@pytest.mark.parametrize('ek', _EXITS)
@pytest.mark.parametrize('case', sorted(OBSERVED) + sorted(MISSING_KEY))
def test_observed_and_missing_key_identical_to_pre_fix_body(ek, case, monkeypatch):
    mk = {**OBSERVED, **MISSING_KEY}[case]
    now = _RUN[ek](_mods()[ek], mk(), monkeypatch)
    pre = _RUN[ek](_pre_fix(ek), mk(), monkeypatch)
    assert _digest(ek, now) == _digest(ek, pre)


# ══════════════════════════════════════════════════════════════════════════
# B. 未觀測 → 既有缺值路徑（＝ 拿掉外資 key 的輸出，逐字）
# ══════════════════════════════════════════════════════════════════════════
def _unobserved_takes_missing_path(ek, mod, inst, mp):
    got = _RUN[ek](mod, inst, mp)
    ref = _RUN[ek](mod, _drop_foreign(inst), mp)
    if ek == 'op':
        # 缺 key 既有送 0、未觀測送 None —— L3 兩者走同一條 `or 0`；畫面逐字相同
        assert got['foreign_buy'] is None
        assert got['out'] == ref['out']
    else:
        assert got == ref
    return got


@pytest.mark.parametrize('ek', _EXITS)
@pytest.mark.parametrize('case', sorted(UNOBSERVED))
def test_unobserved_takes_existing_missing_path(ek, case, monkeypatch):
    _unobserved_takes_missing_path(ek, _mods()[ek], UNOBSERVED[case](), monkeypatch)


@pytest.mark.parametrize('ek', _EXITS)
@pytest.mark.parametrize('case', sorted(UNOBSERVED))
def test_mutant_without_flag_check_turns_red(ek, case, monkeypatch):
    """C. 突變：拿掉 `is_net_observed`（＝ 修前碼）→ B 必須轉紅。"""
    with pytest.raises(AssertionError):
        _unobserved_takes_missing_path(ek, _pre_fix(ek), UNOBSERVED[case](), monkeypatch)


# ── 關鍵字串（人讀得懂的那一層；上面已驗逐字等於缺值路徑）────────────────────
_FAKE_NUMS = {'f1_missing_row': 0.0, 'f1_dashdash': 0.0,
              'f2_buy_nan_sell_300': -300.0, 'f2_sell_nan_buy_500': 500.0}


class TestKeyStrings:

    @pytest.mark.parametrize('case', sorted(UNOBSERVED))
    def test_mid_badge_unknown_and_ce_not_true(self, case, monkeypatch):
        from src.ui.render.ui_widgets import cond_badge
        txt = _text('mid', _run_mid(_mods()['mid'], UNOBSERVED[case](), monkeypatch))
        assert cond_badge(False, 'E 外資未知') in txt
        assert 'E 外資=' not in txt
        assert cond_badge(True, 'E 外資未知') not in txt          # `_cE` 不為 True

    def test_mid_f2_big_fake_was_green_before(self, monkeypatch):
        """修前：F2 +500 億假淨額 ⇒ `_cE` True（綠徽章「E 外資=+500億」）。"""
        from src.ui.render.ui_widgets import cond_badge
        txt = _text('mid', _run_mid(_pre_fix('mid'), UNOBSERVED['f2_sell_nan_buy_500'](), monkeypatch))
        assert cond_badge(True, 'E 外資=+500億') in txt

    @pytest.mark.parametrize('v,label', [(150.0, 'E 外資=+150億'), (-201.0, 'E 外資=-201億'), (0.0, 'E 外資=+0億')])
    def test_mid_observed_badge(self, v, label, monkeypatch):
        from src.ui.render.ui_widgets import cond_badge
        txt = _text('mid', _run_mid(_mods()['mid'], _bfi(f'{int(v * 1e8):,}'), monkeypatch))
        assert cond_badge(v >= 100, label) in txt

    @pytest.mark.parametrize('case', sorted(UNOBSERVED))
    def test_news_prompt_has_no_foreign_line(self, case, monkeypatch):
        prompt = _run_news(_mods()['news'], UNOBSERVED[case](), monkeypatch)[0][1]
        assert '外資現貨買賣超' not in prompt
        assert '• 投信買賣超：' in prompt                           # 其他行照送

    def test_news_prompt_observed_line(self, monkeypatch):
        prompt = _run_news(_mods()['news'], OBSERVED['obs_sell_201'](), monkeypatch)[0][1]
        assert '• 外資現貨買賣超：-201.0億' in prompt

    @pytest.mark.parametrize('case', sorted(UNOBSERVED))
    def test_chips_uses_existing_missing_strings(self, case, monkeypatch):
        out = _run_chips(_mods()['chips'], UNOBSERVED[case](), monkeypatch)
        txt = _text('chips', out)
        assert '外資買賣超 ⬜ 未取得' in txt
        assert '三大法人資料缺「外資」欄位，本卡不下籌碼結論' in txt
        assert '⬜ 未取得：外資（該類今日無資料，非買賣超 0 億）' in txt
        bars = [t for k, t in out if k == 'plotly']
        assert bars and all("'外資'" not in b for b in bars)
        n = _FAKE_NUMS[case]
        assert f'{n:+.1f}億' not in txt and f'外資 {n:+.1f}億' not in txt

    @pytest.mark.parametrize('case', sorted(UNOBSERVED))
    def test_long_omits_foreign_piece(self, case, monkeypatch):
        txt = _text('long', _run_long(_mods()['long'], UNOBSERVED[case](), monkeypatch))
        assert '**🇹🇼 新台幣／外資視角**' in txt                    # 其餘片段照出
        assert '外資買賣超 **' not in txt

    def test_long_observed_piece(self, monkeypatch):
        txt = _text('long', _run_long(_mods()['long'], OBSERVED['obs_buy_150'](), monkeypatch))
        assert '外資買賣超 **+150 億**' in txt

    @pytest.mark.parametrize('case', sorted(UNOBSERVED))
    def test_recon_health_row_both_missing_not_red(self, case, monkeypatch):
        rows = _run_recon(_mods()['recon'], UNOBSERVED[case](), monkeypatch)
        health = rows[2][1]
        assert "('status', 'both_missing')" in health and "('emoji', '⬜')" in health

    def test_recon_pre_fix_f1_was_false_red(self, monkeypatch):
        """修前：F1 預填 0.0 ⇒ v2 壓制項把它當「外資淨賣」⇒ 健康列假紅。"""
        rows = _run_recon(_pre_fix('recon'), UNOBSERVED['f1_missing_row'](), monkeypatch)
        assert "('status', 'disagree')" in rows[2][1]

    @pytest.mark.parametrize('case', sorted(UNOBSERVED))
    def test_op_sends_none_and_no_foreign_sentence(self, case, monkeypatch):
        r = _run_op(_mods()['op'], UNOBSERVED[case](), monkeypatch)
        assert r['foreign_buy'] is None
        txt = _text('op', r)
        assert '【外資買進】' not in txt and '【外資賣超】' not in txt and '【籌碼共振】' not in txt

    def test_op_observed_sentence(self, monkeypatch):
        r = _run_op(_mods()['op'], OBSERVED['obs_sell_201'](), monkeypatch)
        assert r['foreign_buy'] == -201.0
        assert '⚠️ 【外資賣超】外資-201.0億' in _text('op', r)


def test_edu_bfi82u_live_bar_only_when_observed(monkeypatch):
    """教學卡：觀測值 → 有 BFI82U 即時值條；未觀測 → 與缺 key 相同（整段輸出逐字）。"""
    obs = _run_edu(_mods()['edu'], OBSERVED['obs_sell_201'](), monkeypatch)
    miss = _run_edu(_mods()['edu'], MISSING_KEY['no_foreign_key'](), monkeypatch)
    extra = [x for x in obs if x not in miss]
    assert not [x for x in miss if x not in obs]
    # 即時值條 ＝ 一段「📈 即時值與趨勢 -201.00」＋ 既有「僅有單一最新值」說明 —— 缺 key／未觀測時兩段都不出
    assert len(extra) == 2 and len(obs) == len(miss) + 2
    assert '📈 即時值與趨勢' in extra[0][1] and '-201.00' in extra[0][1]
    assert extra[1] == ('caption', '⚠️ 此指標目前僅有單一最新值，趨勢圖待後續 PR 補齊（需擴充 macro fetcher）')


# ══════════════════════════════════════════════════════════════════════════
# 白名單守衛：本批新讀旗標的檔案已登記
# ══════════════════════════════════════════════════════════════════════════
def test_flag_readers_registered_in_lamp_guard():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parent / 'test_lamp_foreign_net_wiring.py').read_text(encoding='utf-8')
    for mod in _mods().values():
        rel = str(pathlib.Path(mod.__file__).resolve().relative_to(pathlib.Path(__file__).resolve().parents[1]))
        assert f'"{rel}"' in src, rel
