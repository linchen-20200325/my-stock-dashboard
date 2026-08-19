"""tests/test_macro_traffic_light_none_inst.py — v19.175 P0 真回歸修。

production bug(user 實機 2/2 重現,線上站台 `?chips=1`):
    ⚠️「總經」分頁渲染異常,已隔離(其他分頁不受影響):
      TypeError: 'NoneType' object is not iterable

根因鏈(靜態追 + 症狀對帳雙向確認)
--------------------------------
1. `src/services/macro_fetch_orchestrator.py:238`
   `inst_res = _results.get('inst') or (None, None)` —— inst job 逾時(25s)或
   例外時 `_results['inst'] is None`,解包後 `inst = None`。
   接著的 FinMind rescue **只在拋例外時被 except 接住**;quota 用罄 /
   `status != 200` 這種「沒拋例外但也沒補到」的情況,`inst` 就一路維持 None。
2. `src/ui/tabs/tab_macro.py:355-358` 把它原樣寫進
   `st.session_state['cl_data'] = dict(..., inst=inst, ...)` → `cl_data['inst'] is None`。
3. `src/compute/macro/macro_helpers.py:calc_traffic_light`
   `_inst = _cd.get('inst', {})` —— dict.get 的預設值**只在 key 不存在時生效**,
   key 存在而值為 None 時回 None → 下一行
   `next((k for k in _inst if '外資' in k), None)` 對 None 做迭代 → TypeError。

⚠️ 同一個寫法在總經分頁**共 4 處**(只修 1 處 → 下一個 rerun 換下一處炸,
   使用者看到的錯誤訊息一模一樣,會誤以為「沒修好」):
   | # | 檔:行(修前) | tab_macro 呼叫順序 | 缺資料時的正確畫面 |
   |---|---|---|---|
   | 1 | `macro_helpers.py:calc_traffic_light` | L208 紅綠燈 | 信心<70 → 擋燈號並列缺項 |
   | 2 | `macro/section_warroom.py:53` | L263 今日作戰室 | 外資方向「未知」 |
   | 3 | `macro/section_mid.py:448` | L477 三環 E 條件 | 「E 外資未知」 |
   | 4 | `macro/section_news_ai.py:142` | L514 AI 量化脈絡 | 該行不列給 LLM |
   4 處已統一改吃 L2 SSOT `macro_helpers.coerce_inst_dict()`,並由本檔
   `TestNoBareInstGetDefault` 原始碼掃描守衛,防止未來新增消費點又寫回裸 `.get('inst', {})`。

為什麼會連帶「總經未評估」
------------------------
`calc_traffic_light` 是在
`section_traffic_light.render_traffic_light_top()` 的**最前段**被呼叫,而
`st.session_state['warroom_summary']`(全站建議持股 SSOT 的來源)是在它回傳
**之後**才寫入(`section_traffic_light.py:193`)。一炸就永遠寫不進去 →
`allocation_service.get_allocation()` 的 `is_loaded=False` →
置底常駐條 / 🎚️ 建議持股油門 / ETF 與個股組合的「📡 總經連動配置」
四處同時退化成「⬜ 總經未評估 / 建議持股 --」。
且 `cl_data` 一旦帶著 None 存進 session,**之後每一次 rerun 都會再炸一次**
(與 user「載入完成就崩、2/2 重現」的描述一致)。

修法(§1 Fail Loud,不是 `or []` 粉飾)
------------------------------------
- L3 `fetch_macro_bundle`(**真修上游**):回傳契約收斂 —— docstring 宣告
  `'inst': dict`,就不該吐 None。失敗時大聲 log 後統一回 `{}`。
- L2 `macro_helpers.coerce_inst_dict`(**消費端第二道防線**,舊 session 裡可能
  還躺著上一版寫入的 None):顯式判型;非 dict 一律視為「三大法人未載入」並寫
  stderr log。缺失**照樣被顯示** —— 它會讓 `_conf_sources` 的
  「外資買賣超 (三大法人)」判 False → conf 掉到 40% → `_render_traffic_light`
  在 conf<70 時直接擋掉燈號並逐項列出缺哪一份資料。差別只在不再炸掉整頁。
- L5 三個 section(warroom / mid / news_ai):同樣改吃 `coerce_inst_dict`,
  各自的「未知 / 不列出」降級路徑本來就存在,故**零畫面行為變更**,只是不再炸頁。
"""
from __future__ import annotations

import pathlib
import re

import pytest

from src.compute.macro import calc_traffic_light, coerce_inst_dict

_ROOT = pathlib.Path(__file__).resolve().parents[1]


# 對應實機 `session_state['cl_data']` 的完整形狀(tab_macro.py:355-358)
def _prod_cl_data(inst_value):
    return {
        'intl': {}, 'tw': {}, 'tech': {},
        'inst': inst_value, 'inst_date': None,
        'margin': None, 'adl': None,
    }


_MKT = {'score': 3, 'regime': 'neutral', 'max_score': 4.0}
_JQ = {'avg': 60}

_FOREIGN_SOURCE_LABEL = '外資買賣超 (三大法人)'


class TestCalcTrafficLightNoneInst:
    """P0:`cl_data['inst'] is None` 不得炸頁,且缺失必須被看見。"""

    def test_none_inst_does_not_raise(self):
        """真回歸:修復前此呼叫拋 TypeError: 'NoneType' object is not iterable。"""
        tl = calc_traffic_light(_MKT, _JQ, _prod_cl_data(None), None)
        assert tl is not None
        assert isinstance(tl, dict)

    def test_none_inst_reports_missing_source(self):
        """§1:缺三大法人要被**列出來**,不可靜默當成「有資料且為 0」。

        P1 v19.470 斷言更正:本測試的 docstring 一直寫著「不可靜默當成有資料
        且為 0」,但原斷言卻是 `tl['fnet'] == 0` —— **與自己的意圖相反**。
        0 在下游 `market_regime` / `HEALTH_FNET_BONUS` 裡是一個合法的觀測值
        (買賣相抵),拿它當缺值標記正是本測試要防的事。三態化後改判 None。
        """
        tl = calc_traffic_light(_MKT, _JQ, _prod_cl_data(None), None)
        assert tl['fk'] is None
        assert _FOREIGN_SOURCE_LABEL in tl['missing_sources']
        assert tl['fnet'] is None, 'fnet 應為 None(沒拿到),不可退回 0(=持平)'

    def test_none_inst_confidence_below_gate(self):
        """conf 必須跌破 70 → handlers._render_traffic_light 會擋掉燈號並列缺項。

        5 個來源只剩 mkt_info / jingqi_info 兩個 → 2/5 = 40%。
        """
        tl = calc_traffic_light(_MKT, _JQ, _prod_cl_data(None), None)
        assert tl['conf'] == 40
        assert tl['conf'] < 70

    def test_none_inst_equals_empty_dict_inst(self):
        """None 與 {} 語意同為「沒拿到」→ 兩者輸出必須逐欄一致(無隱性差異)。"""
        tl_none = calc_traffic_light(_MKT, _JQ, _prod_cl_data(None), None)
        tl_empty = calc_traffic_light(_MKT, _JQ, _prod_cl_data({}), None)
        assert tl_none == tl_empty

    @pytest.mark.parametrize('bad', [[], ['外資'], '外資', 0, 3.14])
    def test_non_dict_inst_treated_as_missing(self, bad):
        """契約違約(list/str/數值)一律當未載入,不得炸頁也不得假裝有資料。

        注意 `['外資']` 這種 list 在舊寫法下**不會**炸(可迭代),反而會讓
        `_fk='外資'` 然後 `.get` 拋 AttributeError —— 一併收斂成「未載入」。
        """
        tl = calc_traffic_light(_MKT, _JQ, _prod_cl_data(bad), None)
        assert tl is not None
        assert tl['fk'] is None
        assert _FOREIGN_SOURCE_LABEL in tl['missing_sources']

    def test_valid_inst_behaviour_unchanged(self):
        """回歸護欄:正常 dict 的行為一字未改(外資 key 命中 + net 讀得到)。"""
        cl = _prod_cl_data({'外資及陸資': {'net': 123.4}, '投信': {'net': 5}})
        tl = calc_traffic_light(_MKT, _JQ, cl, None)
        assert tl['fk'] == '外資及陸資'
        assert tl['fnet'] == 123.4
        assert _FOREIGN_SOURCE_LABEL not in tl['missing_sources']

    def test_via_section_inputs_like_render_traffic_light_top(self):
        """端到端:照 `render_traffic_light_top()` 的取數路徑重跑一次。

        `load_section_inputs(state).cl_data or {}` 對 `{'inst': None}` **不會**
        觸發 `or {}`(dict 非空 → 為真),所以 None 會原封不動傳到 L2 —— 這正是
        線上炸點,必須由 L2 自己守住。
        """
        from src.services import load_section_inputs

        state = {
            'cl_data': _prod_cl_data(None),
            'cl_ts': '2026-08-05 14:30',
            'mkt_info': _MKT,
            'jingqi_info': _JQ,
        }
        inp = load_section_inputs(state)
        assert inp.cl_data['inst'] is None      # 前提成立才算真回歸
        tl = calc_traffic_light(
            inp.mkt_info or {}, inp.jingqi_info or {},
            inp.cl_data or {}, inp.li_latest,
        )
        assert tl is not None


class TestFetchMacroBundleInstContract:
    """L3 契約:`fetch_macro_bundle` 宣告 `'inst': dict`,就不得吐 None。"""

    @staticmethod
    def _run_bundle(monkeypatch, *, inst_fn):
        """以 stub 注入跑真正的 fetch_macro_bundle(不碰網路)。

        `importlib.reload` 被換成 no-op,否則 reload 會把下面對
        `build_leading_fast` 的 monkeypatch 洗掉 → 真的去打 TAIFEX。
        """
        import importlib

        from src.data.macro import leading_indicators as _li_mod
        from src.services import macro_fetch_orchestrator as _orch

        monkeypatch.setattr(importlib, 'reload', lambda m: m)
        monkeypatch.setattr(_li_mod, 'build_leading_fast',
                            lambda **kw: None, raising=False)

        class _DeadSession:
            def get(self, *a, **kw):
                raise RuntimeError('FinMind rescue 不可用(模擬 quota/網路失效)')

        return _orch.fetch_macro_bundle(
            load_heavy=True,
            prev_cl_data={},
            fm_token='',
            li_token='',
            bps_session=_DeadSession(),
            intl_map={'x': 'X'}, tw_map={'台股加權指數': '^TWII'}, tech_map={'y': 'Y'},
            fetch_single=lambda *a, **kw: None,
            fetch_institutional=inst_fn,
            fetch_margin_balance=lambda *a, **kw: None,
            fetch_adl=lambda *a, **kw: None,
        )

    def test_inst_job_exception_yields_dict_not_none(self, monkeypatch):
        """inst job 炸 + rescue 也失敗 → bundle['inst'] 必須是 dict(修前為 None)。"""
        def _boom():
            raise RuntimeError('TWSE BFI82U 逾時')

        bundle = self._run_bundle(monkeypatch, inst_fn=_boom)
        assert isinstance(bundle['inst'], dict)
        assert bundle['inst'] == {}

    def test_inst_job_returns_empty_tuple_unchanged(self, monkeypatch):
        """既有行為護欄:fetch_institutional 回 ({}, date) 時仍是 {},不被改壞。"""
        bundle = self._run_bundle(monkeypatch, inst_fn=lambda: ({}, '20260804'))
        assert bundle['inst'] == {}

    def test_orchestrator_keeps_dict_contract_clamp(self):
        """守衛:L3 出口的型別鉗制不得被日後重構刪掉(刪了就退回 None 外洩)。"""
        _src = (_ROOT / 'src' / 'services' / 'macro_fetch_orchestrator.py').read_text(
            encoding='utf-8')
        assert 'isinstance(inst, dict)' in _src, (
            'macro_fetch_orchestrator 缺少 `inst` 的 dict 契約鉗制 —— '
            "移除它會讓 None 再次外洩到 session_state['cl_data']['inst']。"
        )


class TestCoerceInstDict:
    """L2 SSOT `coerce_inst_dict` —— 4 個消費點共用的型別收斂閘。"""

    def test_valid_dict_passes_through_identically(self):
        """正常 dict:原物件回傳(不複製、不改寫),既有行為零變更。"""
        _inst = {'外資及陸資': {'net': 1.0}}
        assert coerce_inst_dict({'inst': _inst}, where='t') is _inst

    def test_none_value_becomes_empty_dict(self):
        """key 在、值為 None(上游全敗)→ {} 且可安全迭代。"""
        _out = coerce_inst_dict({'inst': None}, where='t')
        assert _out == {}
        assert list(_out) == []          # 真正的回歸點:能被 for 迭代

    def test_missing_key_becomes_empty_dict(self):
        """key 不存在(冷啟動尚未抓)→ {},且**不**應被視為契約違約。"""
        assert coerce_inst_dict({}, where='t') == {}

    def test_none_cl_data_becomes_empty_dict(self):
        """整包 cl_data 為 None(session 尚未寫入)→ {},不得炸。"""
        assert coerce_inst_dict(None, where='t') == {}

    @pytest.mark.parametrize('bad', [[], ['外資'], '外資', 0, 3.14, ()])
    def test_non_dict_becomes_empty_dict(self, bad):
        """契約違約(list/str/數值/tuple)一律收成 {} —— 含**可迭代但無 .get** 的
        `['外資']`(舊寫法下不炸 TypeError,而是後一行 `.get` 拋 AttributeError)。"""
        assert coerce_inst_dict({'inst': bad}, where='t') == {}

    def test_contract_violation_is_logged_not_silent(self, capsys):
        """§1:降級必須留跡 —— None 與型別違約都要寫 stderr,不得靜默。"""
        coerce_inst_dict({'inst': None}, where='unit_none')
        coerce_inst_dict({'inst': ['外資']}, where='unit_list')
        _err = capsys.readouterr().err
        assert 'unit_none' in _err and 'unit_list' in _err

    def test_missing_key_is_not_logged(self, capsys):
        """冷啟動(key 不存在)是正常狀態,不該洗版 stderr。"""
        coerce_inst_dict({}, where='unit_missing')
        assert 'unit_missing' not in capsys.readouterr().err


class TestNoBareInstGetDefault:
    """原始碼守衛:總經路徑不得再出現 `.get('inst', <default>)` 這種假安全寫法。

    為什麼用原始碼掃描而非行為測試:這 3 個消費點都在 L5 Streamlit section 內,
    行為測試需要完整 st context;而「寫法本身」就是 bug 來源(預設值只在 key 不存在
    時生效),字串守衛能在**新增消費點**時立刻變紅 —— 這正是本次事故的形狀
    (前一輪只修了 4 個之中的 1 個)。同類守衛前例:`test_macro_section_render_wiring.py`。
    """

    #  `.get('inst',` / `.get("inst",` —— 有逗號 = 帶預設值 = 假安全
    _BARE = re.compile(r"""\.get\(\s*(['"])inst\1\s*,""")
    _SCAN_DIRS = (
        _ROOT / 'src' / 'ui' / 'tabs' / 'macro',
        _ROOT / 'src' / 'compute' / 'macro',
    )

    def test_no_bare_get_inst_with_default_in_macro_path(self):
        # 註解會**刻意**複述這個壞寫法(修正說明要講清楚錯在哪),故先砍掉 `#` 之後
        # 的內容再比對。`#` 出現在字串字面值中只會造成漏判、不會造成誤判,對守衛
        # 而言是安全方向(寧可漏抓也不要製造假紅)。
        _hits = []
        for _d in self._SCAN_DIRS:
            for _p in sorted(_d.rglob('*.py')):
                for _i, _line in enumerate(
                        _p.read_text(encoding='utf-8').splitlines(), start=1):
                    if self._BARE.search(_line.split('#', 1)[0]):
                        _hits.append(f'{_p.relative_to(_ROOT)}:{_i}: {_line.strip()}')
        assert not _hits, (
            "偵測到 `.get('inst', <default>)` —— dict.get 的預設值**只在 key 不存在時**"
            '生效,上游失敗寫入 None 時會原樣回 None,下一個 `for k in inst` 立刻拋 '
            "TypeError: 'NoneType' object is not iterable 並炸掉整個總經分頁。\n"
            '請改用 `from src.compute.macro import coerce_inst_dict`。\n違規:\n'
            + '\n'.join(_hits)
        )

    @pytest.mark.parametrize('rel', [
        'src/compute/macro/macro_helpers.py',
        'src/ui/tabs/macro/section_warroom.py',
        'src/ui/tabs/macro/section_mid.py',
        'src/ui/tabs/macro/section_news_ai.py',
    ])
    def test_all_four_consumers_go_through_ssot(self, rel):
        """4 個消費點都必須實際呼叫 SSOT(防「只 import 沒用到」的假修)。"""
        _src = (_ROOT / rel).read_text(encoding='utf-8')
        assert 'coerce_inst_dict(' in _src, f'{rel} 未走 coerce_inst_dict SSOT'


class TestTrafficLightCardRendersAfterWarroomWrite:
    """v19.175 順手收掉的**潛在**順序缺陷:`render_traffic_light_top` 先讀後寫。

    `handlers._render_traffic_light` 內部呼叫 `allocation_service.get_allocation()`,
    而它唯一的來源 `st.session_state['warroom_summary']` 原本是在同一個函式**更下面**
    才寫入 → 卡片讀到的是上一輪的 warroom;而「🚀 一鍵更新全部數據」的 on_click
    (`handlers._macro_session_reset`)剛好會 pop 掉它 → `get_macro_state({})` →
    `health is None` → `build_allocation_decision` 回 `is_loaded=False` →
    卡片印「建議持股 --」。

    ⚠️ 誠實範圍界定:user 實機看到的那次 `--`,**主因是本檔上半部那個 TypeError**
    (warroom 根本沒寫成);而且正常路徑下這張卡稍後會被 `section_state.py:479`
    用同一個 placeholder 重畫,所以本缺陷平時不可見。修它是為了讓函式自身的
    「先寫後讀」不變量成立(section_state 沒跑到 / 提早炸時就會露出來)。

    修法:卡片回填移到 warroom_summary / macro_state 寫入之後(placeholder 已在
    頁頂佔位,版面順序不受影響)。本測試用原始碼順序釘住,防止日後又被搬回去。
    """

    _PATH = _ROOT / 'src' / 'ui' / 'tabs' / 'macro' / 'section_traffic_light.py'

    def _src(self) -> str:
        return self._PATH.read_text(encoding='utf-8')

    def test_render_called_exactly_once(self):
        """只能有一個回填點 —— 兩個會讓卡片畫兩次(舊值先蓋、新值後蓋,閃爍)。"""
        assert self._src().count('_render_traffic_light(') == 1

    def test_render_happens_after_warroom_write(self):
        _s = self._src()
        _i_write = _s.index("st.session_state['warroom_summary'] =")
        _i_render = _s.index('_render_traffic_light(')
        assert _i_write < _i_render, (
            '燈號卡在 warroom_summary 寫入**之前**回填 —— get_allocation() 會讀到'
            "上一輪(或被 on_click pop 掉)的 warroom,卡片固定印「建議持股 --」。"
        )

    def test_macro_state_write_also_precedes_render(self):
        """canonical macro_state 同樣要先寫(get_allocation 也吃它的 exposure 上限)。"""
        _s = self._src()
        assert (_s.index("st.session_state['macro_state'] =")
                < _s.index('_render_traffic_light('))

    def test_none_traffic_light_still_renders_waiting_card(self):
        """回歸護欄:`calc_traffic_light` 回 None 時 `_render_traffic_light(.., None)`
        有自己的「⏳ 系統正在深度解析」畫面,不可因為改用 `if _tl_init is not None`
        當旗標而被整個跳過(那會變成一片空白)。"""
        _s = self._src()
        assert '_tl_computed' in _s, '缺少 _tl_computed 旗標 → None 分支畫面會消失'
        assert 'if _tl_computed:' in _s
