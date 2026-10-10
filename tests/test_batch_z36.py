"""批 Z36 —— 客戶 2026-10-10 裁示 Q-z18＝A、Q-z19＝A、Q-z20＝A（基底 origin/main `0ef68f93`）。

- Q-z18（Z35-n1，L2 `market_strategy.market_regime`）：外資淨額整包未取得（缺 key／整包失敗，且
  `get_market_assessment` 既有 `fetch_market_data` 備援也沒拿到真值）⇒ 不再顯示「⏰ 外資數據待更新（收盤後15:30可用）」
  （程式從不檢查時間，原因是猜的），改同頁既有不帶原因的「外資買賣超 ⬜ 未取得」（批 Z35 已用）；0 分不變。
  備援成功取得真值 ⇒ 照舊使用（逐字同修前）。
- Q-z19（Z34-n1，L3 `macro_state_locker.get_macro_state`）：規則引擎 8 項數值輸入全缺時落檔的 fail-safe
  （「系統異常」＋`missing_inputs`，批 Z34 判斷式）在 strict 讀取下比照非 strict／檔不存在 ⇒ 未評估（不拋、不帶
  `file_error`）⇒「💼 我的持股」總經位階卡／建議水位卡走既有「未評估」灰態，⛔ 不出紅錯。
  AI 裁決失敗檔（`execute_and_lock` fail-safe，無 `missing_inputs`）、讀檔／JSON 失敗、程式例外 ⇒ 照舊紅錯。
- Q-z20（Z33-n3 一部分）：投信／自營商淨額「未觀測」（`InstNetDict.unobserved_net`）與真實 0 分離：
  BFI82U 解析器既有旗標 ＋ FinMind 補救本批補旗標（比照外資，⛔ 不改 fillna(0)）；消費點
  §三 籌碼卡（投信買超行＋柱狀圖）、§十一 AI prompt（投信／自營商行）、個股即時操作建議（trust_buy）
  未觀測 ⇒ 該處既有缺值路徑（＝ 同一份資料拿掉該 key 的輸出）；真實 0、正負值 ⇒ 逐字同修前。

golden：修前輸出於基底 `0ef68f93` 以本檔同一支 harness 實跑後寫死 sha256（⛔ 不由現行碼反推）。
突變：`Z36_REVERT_PAIRS` 為「修後逐字 → 修前逐字」（每組恰一處替換）；還原體逐字 ＝ 基底檔（sha256 自證），
      實跑重現修前行為 ⇒ 對應斷言轉紅。舊批次（Z33／Z34／Z35）的還原體串接本批 pair（同 Z33 串 Z34 慣例）。
"""
from __future__ import annotations

import functools
import hashlib
import importlib.util
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]

# ══════════════════════════════════════════════════════════════════════════
# 0. 還原 pair（先於任何 tests.* import 定義 —— 舊批次測試檔會回頭 import 本表，避免循環 import 半初始化）
# ══════════════════════════════════════════════════════════════════════════
_MS = 'src/services/market_strategy.py'
_MSL = 'src/services/macro_state_locker.py'
_ORCH = 'src/services/macro_fetch_orchestrator.py'
_CHIPS = 'src/ui/tabs/macro/section_chips.py'
_NEWS = 'src/ui/tabs/macro/section_news_ai.py'
_OP = 'src/ui/tabs/stock_sections/section_op_recommendation.py'
_DDF = 'src/data/daily/daily_data_fetchers.py'

#: 修後逐字 → 修前逐字（每組恰好一處）。key ＝ repo 相對路徑（舊批次測試以檔案路徑查本表串接）。
Z36_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    _MS: (
        ("        # 批 Z36（Q-z18，客戶 2026-10-10 核准 A）：外資整包未取得（缺 key／整包失敗，且上方 `get_market_assessment`\n"
         "        #   的 `fetch_market_data` 備援也沒拿到真值）⇒ 程式從不檢查時間，「收盤後15:30」是猜的原因 ——\n"
         "        #   比照 Q-z16 改同一個不帶原因的既有缺值字（同頁 §三 籌碼卡 `_hye_ind`）；0 分不變、模型／權重／門檻不動。\n"
         "        signals.append('外資買賣超 ⬜ 未取得')\n",
         "        signals.append('⏰ 外資數據待更新（收盤後15:30可用）')\n"),
    ),
    _MSL: (
        ('    # 批 Z36（Q-z19，客戶 2026-10-10 核准 A）：規則引擎 8 項數值輸入**全缺**時落檔的 fail-safe（「系統異常」＋\n'
         '    #   `missing_inputs`，批 Z34；判斷式同 §十一 `section_news_ai`／`ai_qa_service`）是「缺資料、尚未形成有效評估」，\n'
         '    #   不是「讀壞了」⇒ strict 也比照非 strict／檔不存在走既有未評估路徑（不拋、不帶 `file_error`）。\n'
         '    #   AI 裁決失敗檔（`execute_and_lock` 寫的 fail-safe，無 `missing_inputs`）、讀檔／JSON 失敗、缺 `market_regime` 照舊。\n'
         '    _file_no_data = (_file.get("market_regime") == "系統異常" and bool(_file.get("missing_inputs")))\n',
         ''),
        ('    if (strict and not _is_loaded and os.path.exists(state_file_path) and not _file_expired\n'
         '            and not _file_no_data):\n',
         '    if strict and not _is_loaded and os.path.exists(state_file_path) and not _file_expired:\n'),
        ('            and not _file_expired and not _file_no_data):\n',
         '            and not _file_expired):\n'),
    ),
    _DDF: (
        ("    # 批 Z36（Q-z20，客戶 2026-10-10 核准 A）：自營商觀測判定只看「名稱含『自營』且不含『外資』」的國內自營列\n"
         "    #   （不依賴子列確切名稱；外資自營商列解析與否不影響本旗標，加總值照舊 ⛔ 不改）：任一列在但值不可解析\n"
         "    #   （'--'／空白／非數字）或沒有任何一列成功解析 ⇒ 自營商未觀測。真實 0（'0'／'-0'）仍為觀測值。\n"
         "    _dom_dealer_ok = _dom_dealer_bad = False\n",
         ''),
        ("            if _row and '自營' in str(_row[0]) and '外資' not in str(_row[0]):\n"
         "                _dom_dealer_bad = True\n",
         ''),
        ("        _is_dom_dealer = '自營' in _nm and '外資' not in _nm\n", ''),
        ('            _dom_dealer_bad = _dom_dealer_bad or _is_dom_dealer\n', ''),
        ('        _dom_dealer_ok = _dom_dealer_ok or _is_dom_dealer\n', ''),
        ("    _unobs = frozenset(_k for _k in _inst if _k not in _seen\n"
         "                       or (_k == '自營商' and (_dom_dealer_bad or not _dom_dealer_ok)))\n",
         '    _unobs = frozenset(_k for _k in _inst if _k not in _seen)\n'),
    ),
    _ORCH: (
        ("                    # 批 Z36（Q-z20，客戶 2026-10-10 核准 A）：投信／自營商比照外資記「未觀測」——\n"
         "                    #   列歸屬與下方迴圈同序（外資優先 → 投信 → 自營），buy／sell 不可解析即不是觀測值\n"
         "                    #   （⛔ 仍不改下兩行 fillna(0)；既有消費點照舊，只有讀旗標的消費點改走缺值路徑）。\n"
         "                    _fm_trust_rows = ~_fm_foreign_rows & _df_i['name'].astype(str).map(\n"
         "                        lambda _n: 'investment_trust' in _n.lower() or '投信' in _n)\n"
         "                    _fm_dealer_rows = ~_fm_foreign_rows & ~_fm_trust_rows & _df_i['name'].astype(str).map(\n"
         "                        lambda _n: 'dealer' in _n.lower() or '自營' in _n)\n",
         ''),
        ('                        _fm_trust_unobserved = bool((_fm_bad_rows & _fm_trust_rows).any())\n'
         '                        _fm_dealer_unobserved = bool((_fm_bad_rows & _fm_dealer_rows).any())\n',
         ''),
        ('                        _fm_trust_unobserved = bool(_fm_trust_rows.any())\n'
         '                        _fm_dealer_unobserved = bool(_fm_dealer_rows.any())\n',
         ''),
        ("                                              else ())\n"
         "                        # 批 Z36（Q-z20）：投信／自營商 buy／sell 缺值 ⇒ 淨額為 fillna(0) 推出的假值，同樣標未觀測\n"
         "                        + tuple(_k for _k, _u in (('投信', _fm_trust_unobserved),\n"
         "                                                  ('自營商', _fm_dealer_unobserved))\n"
         "                                if _u and _k in inst))\n",
         '                                              else ()))\n'),
    ),
    _CHIPS: (
        ("        # 批 Z36（Q-z20，客戶 2026-10-10 核准 A）：投信／自營商淨額未觀測 ⇒ 同缺該類既有路徑（不出「投信買超」行、\n"
         "        #   柱狀圖不畫該柱並列入下方「⬜ 未取得」）；觀測值（含真實 0）逐字不變。\n"
         "        _tn3 = inst[_tk3]['net'] if _tk3 and is_net_observed(inst, _tk3) else None\n",
         "        _tn3 = inst[_tk3]['net'] if _tk3 else None\n"),
        ("        _zn3 = (inst.get(_zk3) or {}).get('net') if _zk3 and is_net_observed(inst, _zk3) else None\n",
         "        _zn3 = (inst.get(_zk3) or {}).get('net') if _zk3 else None\n"),
    ),
    _NEWS: (
        ("                # 批 Z36（Q-z20，客戶 2026-10-10 核准 A）：投信／自營商淨額未觀測 ⇒ 同上既有「缺值整行不送」（不送「0 億」給 LLM）。\n"
         "                _tnet_v = (_inst_v.get(_tk_v, {}).get('net')\n"
         "                           if _tk_v and is_net_observed(_inst_v, _tk_v) else None)\n"
         "                _dnet_v = (_inst_v.get(_dk_v, {}).get('net')\n"
         "                           if _dk_v and is_net_observed(_inst_v, _dk_v) else None)\n",
         "                _tnet_v = _inst_v.get(_tk_v, {}).get('net') if _tk_v else None\n"
         "                _dnet_v = _inst_v.get(_dk_v, {}).get('net') if _dk_v else None\n"),
    ),
    _OP: (
        ("            # 批 Z36（Q-z20，客戶 2026-10-10 核准 A）：投信淨額未觀測 ⇒ 送 None，L3 既有 `or 0`（同缺 key）。\n"
         "            'trust_buy':   ((_inst_g.get(_tk_g, {}).get('net', 0)\n"
         "                             if is_net_observed(_inst_g, _tk_g) else None)\n"
         "                            if _tk_g else 0),\n",
         "            'trust_buy':   _inst_g.get(_tk_g, {}).get('net', 0) if _tk_g else 0,\n"),
    ),
}
#: 基底 `0ef68f93` 原始檔 sha256（`git show 0ef68f93:<檔> | sha256sum` 實算；寫死以免測試依賴 git）
Z36_BASE_SHA = {
    _MS: '7817fc2b79670835f1839c84d74b28773a78cd6121348755179308bcea61028a',
    _MSL: '10454ea88500a0ff8b8ac1b276374439e04d8c456afd2ba150f1d446ca1d19fe',
    _DDF: '77bc1a2640aeb75c3d30ad6447f79ce5d4f2dffdfbb25fca1de3af8df6b995b4',
    _ORCH: 'd02ce67a06348320d2e0288991f543e9445e6d852af111dc6131269544fb16f0',
    _CHIPS: '6d6f7576efbdd1d822653d358b51bb5a6fd517bbaf80db5e154c697b199280db',
    _NEWS: 'e87b40678538289cf8f7f7ee55b7fd06de9f2e2d93794f8e172fe2050dbb47e9',
    _OP: 'e2e0dd2651149c1b513dd5b5ed9747f6cb5b7a965d6586ef89acb4c9b74b8dd3',
}


def z36_pairs_for(file_path) -> tuple[tuple[str, str], ...]:
    """舊批次還原體串接用：給模組 `__file__`（或 repo 相對路徑），回本批該檔的 pair（無則空）。"""
    p = pathlib.Path(file_path)
    rel = (p.resolve().relative_to(_ROOT) if p.is_absolute() else p).as_posix()
    return Z36_REVERT_PAIRS.get(rel, ())


def z36_revert(rel: str, code: str) -> str:
    for new, old in Z36_REVERT_PAIRS[rel]:
        assert code.count(new) == 1, f'{rel} 替換點不唯一或已不存在：{new!r}'
        code = code.replace(new, old)
    return code


@functools.lru_cache(maxsize=None)
def z36_pre_module(rel: str):
    """現行檔只把本批改動換回基底 `0ef68f93` 寫法（獨立模組物件，不影響本尊）。"""
    path = _ROOT / rel
    name = '_z36_pre_' + rel.replace('/', '_').removesuffix('.py')
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    m.__file__ = str(path)
    sys.modules[name] = m          # dataclass 等需要以模組名回查
    exec(compile(z36_revert(rel, path.read_text(encoding='utf-8')), str(path), 'exec'), m.__dict__)
    return m


# ══════════════════════════════════════════════════════════════════════════
# 以下才 import 專案與舊批次測試（舊批次測試檔會回頭 import 上面的 pair）
# ══════════════════════════════════════════════════════════════════════════
import copy  # noqa: E402
import json  # noqa: E402
import pickle  # noqa: E402
import types  # noqa: E402

import pytest  # noqa: E402

import src.services.allocation_service as AL  # noqa: E402
import src.services.macro_state_locker as MSL  # noqa: E402
import src.services.market_assessment_apply as MAA  # noqa: E402
import src.services.market_strategy as MS  # noqa: E402
from shared.inst_net import InstNetDict, is_net_observed  # noqa: E402
from shared.ui_state import UI_EMPTY, UI_FAILED  # noqa: E402
from src.data.daily.daily_data_fetchers import _parse_bfi82u_rows  # noqa: E402
from src.ui.views import page_hold as PH  # noqa: E402
from tests import test_batch_z33_inst as Z33  # noqa: E402
from tests import test_batch_z35 as Z35  # noqa: E402
from tests import test_lamp_foreign_net_wiring as LAMP  # noqa: E402


def _h(x) -> str:
    return hashlib.sha256(repr(x).encode('utf-8')).hexdigest()


@pytest.mark.parametrize('rel', sorted(Z36_REVERT_PAIRS))
def test_reverted_source_equals_base_file(rel):
    """還原體原始碼逐字 ＝ 基底 `0ef68f93` 檔案 ⇒ 下方「修前」對照與突變斷言都是真修前碼。"""
    code = z36_revert(rel, (_ROOT / rel).read_text(encoding='utf-8'))
    assert hashlib.sha256(code.encode('utf-8')).hexdigest() == Z36_BASE_SHA[rel]


# ══════════════════════════════════════════════════════════════════════════
# 1. Q-z18：市場評估外資整包未取得 ⇒ 不帶原因的既有缺值字
# ══════════════════════════════════════════════════════════════════════════
_MISSING = '外資買賣超 ⬜ 未取得'          # 同頁 §三 籌碼卡既有字（section_chips `_hye_ind`，逐字）
_WAIT = '⏰ 外資數據待更新（收盤後15:30可用）'


def _ma(inst, mp, *, backup=None, ms=MS):
    """實跑 compute_and_apply_market_assessment（真 get_market_assessment）；備援 `fetch_market_data` 以 spy 擋網路。

    backup=None ⇒ 備援也失敗（`fetch_market_data` 既有失敗回傳）；backup=float（元）⇒ 備援取得真值。
    """
    calls = []

    def _spy():
        calls.append(1)
        if backup is None:
            return {'foreign_net': None, 'date': ''}
        return {'foreign_net': float(backup), 'date': '20261009'}
    ss: dict = {}
    mp.setattr(MAA, 'st', types.SimpleNamespace(session_state=ss))
    mp.setattr(ms, 'fetch_market_data', _spy)
    mp.setattr('src.services.get_market_assessment', ms.get_market_assessment)
    import pandas as pd
    MAA.compute_and_apply_market_assessment(inst=inst, tw_raw=Z35._tw_raw(), margin=2000.0,
                                            df_adl=pd.DataFrame({'ad_ratio': [60.0]}))
    return ss['mkt_info'], len(calls)


#: 整包未取得的兩種形狀（缺外資 key／整包 {}）
_WHOLE_MISSING = {
    'no_foreign_key': lambda: {'投信': {'net': 12.3}, '自營商': {'net': 4.5}},
    'empty_inst': lambda: {},
}
#: 修前（基底 `0ef68f93`）同一支 harness 實跑：mkt_info 的 sha256（⛔ 不由現行碼反推）
_QZ18_GOLDEN = {
    ('empty_inst', -3100000000.0): '7e6ce5838d8c6ccec886b80dcf6467c80d3ca1c6cd9b8088f344fb5eea1a3a9e',
    ('empty_inst', 0.0): '1631482e2071512c287b27e4a0d7d8f3df948a098ff4c471daf23a9984d4c254',
    ('empty_inst', None): 'b08486a11b4df84b6b0357b53f3273fa4e86eef38dc3d949d694a36b37a55e0d',
    ('no_foreign_key', 2500000000.0): '5ddfdf1bdee44693df60d8f32fc30b41db91369a8698602cc08e9d0b975ecef5',
    ('no_foreign_key', None): 'b08486a11b4df84b6b0357b53f3273fa4e86eef38dc3d949d694a36b37a55e0d',
}


class TestQz18:
    @pytest.mark.parametrize('name', sorted(_WHOLE_MISSING))
    def test_backup_also_failed_shows_existing_missing_text(self, name, monkeypatch):
        """備援也沒拿到 ⇒ 不帶原因的既有缺值字；不出「⏰」「15:30」；0 分；其餘逐字同修前（只換那一句）。"""
        r, n = _ma(_WHOLE_MISSING[name](), monkeypatch)
        assert n == 1                                   # 照舊打備援
        assert _MISSING in r['signals']
        txt = ' '.join(r['signals'])
        assert '⏰' not in txt and '15:30' not in txt and '待更新' not in txt
        assert r['foreign_net'] is None
        pre_like = dict(r, signals=[_WAIT if s == _MISSING else s for s in r['signals']])
        assert _h(pre_like) == _QZ18_GOLDEN[(name, None)]

    @pytest.mark.parametrize('key', [k for k in sorted(_QZ18_GOLDEN, key=repr) if k[1] is not None])
    def test_backup_success_uses_real_value_unchanged(self, key, monkeypatch):
        """備援成功取得真值（含真實 0）⇒ 照舊使用；mkt_info 逐字同修前 golden。"""
        name, backup = key
        r, n = _ma(_WHOLE_MISSING[name](), monkeypatch, backup=backup)
        assert n == 1 and _MISSING not in r['signals'] and _WAIT not in r['signals']
        assert _h(r) == _QZ18_GOLDEN[key]

    def test_score_unchanged_vs_real_zero(self):
        """L2 直呼：None 與真實 0 分數相同（0 分），文案分開（None ⇒ 缺值字；0 ⇒ 持平）。"""
        r_none = MS.market_regime(100, 90, 80, None)
        r_zero = MS.market_regime(100, 90, 80, 0)
        assert _MISSING in r_none['signals'] and not any('⏰' in s for s in r_none['signals'])
        assert any('相抵' in s for s in r_zero['signals'])
        assert r_none['score'] == r_zero['score']

    def test_string_is_the_existing_one(self):
        """沿用字串出處：同頁 §三 籌碼卡 `_hye_ind` 既有字（逐字）；批 Z35 未觀測分支同字。"""
        import src.ui.tabs.macro.section_chips as SC
        assert f"_hye_ind = '{_MISSING}'" in pathlib.Path(SC.__file__).read_text(encoding='utf-8')
        assert MS.market_regime(100, 90, 80, None, foreign_net_unobserved=True)['signals'].count(_MISSING) == 1

    @pytest.mark.parametrize('name', sorted(_WHOLE_MISSING))
    def test_mutant_reverted_shows_wait(self, name, monkeypatch):
        """突變：只還原本批 L2 那一句 ⇒ 又出「⏰ …15:30」（猜原因）⇒ 上方斷言轉紅；且等於修前 golden。"""
        r, _ = _ma(_WHOLE_MISSING[name](), monkeypatch, ms=z36_pre_module(_MS))
        assert _WAIT in r['signals'] and _MISSING not in r['signals']
        assert _h(r) == _QZ18_GOLDEN[(name, None)]


# ══════════════════════════════════════════════════════════════════════════
# 2. Q-z19：總經 8 項輸入全缺落檔 ⇒ 持股頁走既有「未評估」，⛔ 不出紅錯
# ══════════════════════════════════════════════════════════════════════════
_SUBMITTED = PH.HoldRequest(submitted=True)
_WR = {'health_score': 70.0, 'effective_regime': 'bull'}


def _write_all_missing(path: pathlib.Path, *, ai: bool = False, mod=MSL) -> dict:
    """走真的寫檔路徑落「8 項全缺」fail-safe：§十一 `lock_system_state_only`（ai=False）或
    `execute_and_lock` AI 成功（ai=True，AI 欄位照常寫入、regime 仍是「系統異常」＋`missing_inputs`）。"""
    locker = mod.MacroStateLocker(state_file_path=str(path))
    state = {**mod.calculate_system_state({}), 'm1b_m2_data_month': None}
    if ai:
        locker._llm = lambda prompt: json.dumps({'traffic_light': '⬜', 'analysis_summary': 'x'})
        assert locker.execute_and_lock(state, []) is True
    else:
        locker.lock_system_state_only(state)
    return json.loads(path.read_text(encoding='utf-8'))


def _write_ai_failed(path: pathlib.Path) -> dict:
    """真正的 AI 裁決失敗：`execute_and_lock` 拋 ⇒ 寫 `_DEFAULT_STATE` fail-safe（無 `missing_inputs`）。"""
    locker = MSL.MacroStateLocker(state_file_path=str(path))

    def _boom(prompt):
        raise RuntimeError('LLM down')
    locker._llm = _boom
    assert locker.execute_and_lock(MSL.calculate_system_state({'VIX_Index': 18.0}), []) is False
    return json.loads(path.read_text(encoding='utf-8'))


@pytest.fixture
def hold_dir(tmp_path, monkeypatch):
    """CWD → tmp（`macro_state.json` 是相對路徑）；session 由各測試設定（預設無 warroom）。"""
    monkeypatch.chdir(tmp_path)
    ss: dict = {}
    monkeypatch.setattr(AL, 'st', types.SimpleNamespace(session_state=ss))
    return tmp_path, ss


def _cards(mod=PH):
    return (mod.build_macro_stage_card(mod.load_macro(_SUBMITTED))[0],
            mod.build_position_cap_card(mod.load_allocation(_SUBMITTED))[0])


def _with_msl(monkeypatch, msl_mod):
    """讓 L3 的 strict 讀取點改用指定的 `get_macro_state`（突變／修前用）。"""
    monkeypatch.setattr(MSL, 'get_macro_state', msl_mod.get_macro_state)


class TestQz19AllMissingIsNotEvaluated:
    @pytest.mark.parametrize('ai', [False, True], ids=['lock_only', 'ai_ok'])
    def test_no_warroom_cards_gray_same_as_no_file(self, hold_dir, ai):
        """(1) 全缺落檔、無 warroom ⇒ 兩張卡 = 檔不存在時的既有「未評估」（灰），⛔ 不出紅錯。"""
        d, _ = hold_dir
        st_file = _write_all_missing(d / 'macro_state.json', ai=ai)
        assert st_file['market_regime'] == '系統異常' and st_file['missing_inputs']
        got = _cards()
        assert got[0].state == UI_EMPTY and got[1].state == UI_EMPTY
        (d / 'macro_state.json').unlink()
        assert got == _cards()                             # 逐欄同「檔不存在」

    def test_warroom_ok_cap_same_as_no_file(self, hold_dir):
        """(1b) 全缺落檔、warroom 可用（總經頁顯示正常範圍）⇒ 建議水位卡 = 檔不存在時（不出紅錯、不帶 file_error）。"""
        d, ss = hold_dir
        ss['warroom_summary'] = dict(_WR)
        _write_all_missing(d / 'macro_state.json')
        got = _cards()
        assert UI_FAILED not in (got[0].state, got[1].state)
        assert 'file_error' not in MSL.get_macro_state(_WR, strict=True)
        (d / 'macro_state.json').unlink()
        AL._invalidate()
        assert got == _cards()

    def test_all_strict_readers_do_not_raise(self, hold_dir):
        """全部 strict 讀者（get_macro_state／get_macro_regime／get_station_macro／get_allocation）⇒ 未評估、不拋。"""
        d, _ = hold_dir
        _write_all_missing(d / 'macro_state.json')
        import src.services.dividend_station_service as DS
        assert MSL.get_macro_state({}, strict=True)['is_loaded'] is False
        assert AL.get_macro_regime(strict=True)['is_loaded'] is False
        assert DS.get_station_macro(strict=True)['loaded'] is False
        assert AL.get_allocation(strict=True).is_loaded is False
        # 非 strict 同結果（strict 現在與非 strict 一致）
        assert MSL.get_macro_state({}, strict=True) == MSL.get_macro_state({})


#: 修前（基底 `0ef68f93`）同一支 harness 實跑：(總經位階卡, 建議水位卡) repr 的 sha256（⛔ 不由現行碼反推）
_QZ19_GOLDEN = {
    'ai_failed_no_wr': '160968651ed50eff69484ec9eba2986b242ba389ba98c1c116bc7e824c76949d',
    'ai_failed_wr': '2aa6d2ef8667c6a8026fb6a3bd0f355d0844ee951b9d652fd1b0520aa5e86aaa',
    'bad_json_no_wr': '41f3788f15782196d4c628489ab33135f75f525eece045c7e1d41c4266b08204',
    'no_file_no_wr': '9069822bacab5327a8f6f119fdf851f179bbb49f928916cedc3a4884430e2ef9',
}


def _qz19_case(name, d, ss):
    if name.endswith('_wr') and not name.endswith('no_wr'):
        ss['warroom_summary'] = dict(_WR)
    if name.startswith('ai_failed'):
        _write_ai_failed(d / 'macro_state.json')
    elif name.startswith('bad_json'):
        (d / 'macro_state.json').write_text('{bad json', encoding='utf-8')


class TestQz19RealErrorsStayRed:
    @pytest.mark.parametrize('name', sorted(_QZ19_GOLDEN))
    def test_unchanged_vs_pre_fix_golden(self, hold_dir, name):
        """(2)(3) AI 裁決失敗檔／讀壞的檔／檔不存在 ⇒ 兩張卡逐字同修前 golden。"""
        d, ss = hold_dir
        _qz19_case(name, d, ss)
        assert _h(_cards()) == _QZ19_GOLDEN[name]

    def test_ai_failed_is_red(self, hold_dir):
        """(2) 真正 AI 裁決失敗（無 missing_inputs）⇒ 照舊紅錯（兩張卡；無 warroom）。"""
        d, _ = hold_dir
        f = _write_ai_failed(d / 'macro_state.json')
        assert f['market_regime'] == '系統異常' and 'missing_inputs' not in f
        m, c = _cards()
        assert m.state == UI_FAILED and c.state == UI_FAILED

    def test_ai_failed_with_warroom_cap_is_red(self, hold_dir):
        """(2) warroom 可用 ＋ AI 失敗檔 ⇒ 建議水位卡照舊紅（B6-r4 file_error）。"""
        d, ss = hold_dir
        ss['warroom_summary'] = dict(_WR)
        _write_ai_failed(d / 'macro_state.json')
        assert _cards()[1].state == UI_FAILED

    def test_program_exception_is_red(self, hold_dir, monkeypatch):
        """(3) 程式例外（L3 拋非預期例外）⇒ 照舊紅錯；與「全缺」不共用語意。"""
        d, _ = hold_dir
        _write_all_missing(d / 'macro_state.json')

        def _boom(*a, **k):
            raise ValueError('bug')
        monkeypatch.setattr(MSL, 'get_macro_state', _boom)
        m, c = _cards()
        assert m.state == UI_FAILED and c.state == UI_FAILED

    def test_semantics_not_shared(self, hold_dir):
        """全缺（灰）與 AI 失敗（紅）兩檔只差 `missing_inputs`；卡片語意不同。"""
        d, _ = hold_dir
        _write_all_missing(d / 'macro_state.json')
        gray = _cards()
        _write_ai_failed(d / 'macro_state.json')
        red = _cards()
        assert {gray[0].state, gray[1].state} == {UI_EMPTY}
        assert {red[0].state, red[1].state} == {UI_FAILED}


class TestQz19Mutation:
    def test_pre_fix_all_missing_was_red(self, hold_dir, monkeypatch):
        """還原體（修前）：全缺落檔在 strict 下拋 ⇒ 兩張卡紅 ⇒ 上方 TestQz19AllMissingIsNotEvaluated 轉紅。"""
        d, _ = hold_dir
        _write_all_missing(d / 'macro_state.json')
        _with_msl(monkeypatch, z36_pre_module(_MSL))
        m, c = _cards()
        assert m.state == UI_FAILED and c.state == UI_FAILED

    def test_pre_fix_warroom_cap_was_red(self, hold_dir, monkeypatch):
        d, ss = hold_dir
        ss['warroom_summary'] = dict(_WR)
        _write_all_missing(d / 'macro_state.json')
        _with_msl(monkeypatch, z36_pre_module(_MSL))
        assert _cards()[1].state == UI_FAILED

    @pytest.mark.parametrize('name', sorted(_QZ19_GOLDEN))
    def test_pre_fix_module_reproduces_golden(self, hold_dir, monkeypatch, name):
        d, ss = hold_dir
        _qz19_case(name, d, ss)
        _with_msl(monkeypatch, z36_pre_module(_MSL))
        assert _h(_cards()) == _QZ19_GOLDEN[name]


# ══════════════════════════════════════════════════════════════════════════
# 3. Q-z20：投信／自營商「未觀測」與真實 0 分離
# ══════════════════════════════════════════════════════════════════════════
_FK, _TK, _DK = '外資及陸資', '投信', '自營商'
_FIELDS = ['單位名稱', '買進金額', '賣出金額', '買賣差額']


def _bfi(foreign='15,000,000,000', trust='1,230,000,000', dealer=('1,000,000,000', '-550,000,000'),
         foreign_dealer=None):
    """真的 BFI82U 解析器；某欄給 None ⇒ 回應裡沒有那一列（未觀測）。dealer 子列給 None ⇒ 該子列不存在。
    foreign_dealer：另加「外資自營商」列（值字串）；⚠️ 子列名取自 fixture（沙箱連不到 TWSE）。"""
    rows = []
    if dealer is not None:
        rows += [[n, '1', '1', v] for n, v in zip(('自營商(自行買賣)', '自營商(避險)'), dealer) if v is not None]
    if foreign_dealer is not None:
        rows.append(['外資自營商', '1', '1', foreign_dealer])
    if trust is not None:
        rows.append(['投信', '1', '1', trust])
    if foreign is not None:
        rows.append(['外資及陸資(不含外資自營商)', '1', '1', foreign])
    return _parse_bfi82u_rows(_FIELDS, rows)


#: BFI82U：未觀測（L1 既有旗標）
BFI_UNOBSERVED = {
    'trust_missing': (lambda: _bfi(trust=None), {_TK}),
    'trust_dashdash': (lambda: _bfi(trust='--'), {_TK}),
    'dealer_missing': (lambda: _bfi(dealer=None), {_DK}),
    'both_missing': (lambda: _bfi(trust=None, dealer=None), {_TK, _DK}),
    # 自營：一列 '--'／空白（存在但不可解析）⇒ 未觀測（另一列照常加總，值不改）
    'dealer_one_dashdash': (lambda: _bfi(dealer=('1,000,000,000', '--')), {_DK}),
    'dealer_one_blank': (lambda: _bfi(dealer=('', '-550,000,000')), {_DK}),
    # 只有外資自營商列被解析、沒有任何國內自營列 ⇒ 自營商未觀測（外資自營商不算自營商的觀測）
    'only_foreign_dealer': (lambda: _bfi(dealer=None, foreign_dealer='200,000,000'), {_DK}),
}
#: 觀測值（含真實 0、正負值）—— 修前修後逐字相同
OBSERVED = {
    'real_zero': lambda: _bfi(trust='0', dealer=('0', '0')),
    'normal_pos': lambda: _bfi(),
    'normal_neg': lambda: _bfi(foreign='-20,100,000,000', trust='-800,000,000',
                               dealer=('-100,000,000', '-200,000,000')),
    'plain_dict': lambda: {_FK: {'net': 150.0}, _TK: {'net': 12.3}, _DK: {'net': 4.5}},
    'minus_zero': lambda: _bfi(trust='-0', dealer=('-0', '0')),
    # 外資自營商列解析與否不影響自營商旗標（加總值照舊：解析到的外資自營商值仍併入自營商 —— 既有歸類，登記不改）
    'foreign_dealer_dashdash': lambda: _bfi(foreign_dealer='--'),
    'foreign_dealer_parsed': lambda: _bfi(foreign_dealer='200,000,000'),
}


def _fm(name, buy, sell):
    return LAMP._fm_row(name, buy, sell)


_FM_FOREIGN = _fm('Foreign_Investor', 30_000_000_000, 55_000_000_000)
_FM_TRUST = _fm('Investment_Trust', 5_000_000_000, 3_000_000_000)
_FM_DSELF = _fm('Dealer_self', 1_000_000_000, 2_000_000_000)
_FM_DHEDGE = _fm('Dealer_Hedging', 4_000_000_000, 1_000_000_000)
#: FinMind 補救：(rows, 預期 unobserved_net)
FM_CASES = {
    'fm_good': ([_FM_FOREIGN, _FM_TRUST, _FM_DSELF, _FM_DHEDGE], frozenset()),
    'fm_real_zero': ([_FM_FOREIGN, _fm('Investment_Trust', 3_000_000_000, 3_000_000_000),
                      _fm('Dealer_self', 0, 0), _fm('Dealer_Hedging', 2_000_000_000, 2_000_000_000)],
                     frozenset()),
    'fm_trust_buy_nan': ([_FM_FOREIGN, _fm('Investment_Trust', None, 3_000_000_000), _FM_DSELF, _FM_DHEDGE],
                         frozenset({_TK})),
    'fm_dealer_sell_bad': ([_FM_FOREIGN, _FM_TRUST, _FM_DSELF, _fm('Dealer_Hedging', 4_000_000_000, 'n/a')],
                           frozenset({_DK})),
    'fm_trust_dealer_nan': ([_FM_FOREIGN, _fm('Investment_Trust', 5_000_000_000, None),
                             _fm('Dealer_self', None, None), _FM_DHEDGE], frozenset({_TK, _DK})),
    # 限制（不猜測）：自營只有一列存在、另一列不存在 ⇒ 維持既有（觀測）
    'fm_only_dealer_self': ([_FM_FOREIGN, _FM_TRUST, _FM_DSELF], frozenset()),
    # 外資自營商（Foreign_Dealer_Self）依既有迴圈歸外資（N2 既有限制）⇒ 不得誤標自營商
    'fm_foreign_dealer_bad': ([_FM_FOREIGN, _fm('Foreign_Dealer_Self', None, 1), _FM_TRUST, _FM_DSELF],
                              frozenset({_FK})),
}


def _fm_inst(mp, name, *, orch=None):
    if orch is not None:
        mp.setattr('src.services.macro_fetch_orchestrator.fetch_macro_bundle', orch.fetch_macro_bundle)
    return LAMP._finmind_bundle(mp, FM_CASES[name][0])['inst']


def _drop(inst, keys):
    """同一份資料、拿掉那幾個 key（＝ 既有缺值路徑的輸入；保留其餘 key 的旗標）。"""
    return InstNetDict({k: v for k, v in inst.items() if k not in keys},
                       unobserved_net=getattr(inst, 'unobserved_net', frozenset()) - set(keys))


def _run_op(mod, inst, mp):
    """個股即時操作建議：記下送進 L3 的 trust_buy／foreign_buy ＋ 畫面。"""
    fake = Z33._FakeST({'cl_data': {'inst': inst}})
    seen: list = []
    from src.services.app_ai_service import generate_ai_comment as _real_gac

    def _spy(data):
        seen.append((data.get('foreign_buy', '<absent>'), data.get('trust_buy', '<absent>')))
        return _real_gac(data)
    mp.setattr(mod, 'st', fake)
    mp.setattr(mod, 'generate_ai_comment', _spy)
    mp.setattr(Z33.AS, 'get_macro_regime', lambda *a, **k: {'is_loaded': False})
    mod.render_op_recommendation_section('2330', 82.0, {'contracting': True}, 5.0, 100.0, 55.0, 0, 0)
    assert len(seen) == 1
    return {'buys': seen[0], 'out': list(fake.out)}


_RUN = {'chips': Z33._run_chips, 'news': Z33._run_news, 'op': _run_op}
_REL = {'chips': _CHIPS, 'news': _NEWS, 'op': _OP}
_EXITS = sorted(_RUN)


def _mod(ek):
    return Z33._mods()[ek]


def _digest(ek, r) -> str:
    return _h(r)


#: 修前（基底 `0ef68f93`）同一支 harness 實跑：消費點完整輸出 sha256（⛔ 不由現行碼反推）
_QZ20_GOLDEN: dict = {
    ('chips', 'foreign_dealer_dashdash'): '1e1b51070c3720489be4a5dcf697db12cc92397cb363c39b48b5b3f1d610f697',
    ('chips', 'foreign_dealer_parsed'): 'eb1564fee86240aa4c0984b645189b53ec75ca3f59350237b9cca3ae62222cc0',
    ('chips', 'minus_zero'): '775fdb4c62ef83f04dbcbc9c268b531bc0b9acc0d98d1312c6e3b7c9460b7ac2',
    ('chips', 'normal_neg'): '658765f304ef52b396c05a6aefed5021bc2e9e4d06ddaaf3ad531ac47d3a8245',
    ('chips', 'normal_pos'): '1e1b51070c3720489be4a5dcf697db12cc92397cb363c39b48b5b3f1d610f697',
    ('chips', 'plain_dict'): '1e1b51070c3720489be4a5dcf697db12cc92397cb363c39b48b5b3f1d610f697',
    ('chips', 'real_zero'): '775fdb4c62ef83f04dbcbc9c268b531bc0b9acc0d98d1312c6e3b7c9460b7ac2',
    ('news', 'foreign_dealer_dashdash'): 'acc07faec62abfbd4c31410a3f748a3cb40832d0a4732ed02f5d046215afae9b',
    ('news', 'foreign_dealer_parsed'): '257b3837464adc0c162898eba18aeee08fce4ec1262cd084e6be31c66273ab3e',
    ('news', 'minus_zero'): '7d1f21b005df043e0cf6cc13d3fbfd90e66437a7a80bea169c1dae342c3edf94',
    ('news', 'normal_neg'): 'ead5de0836ed3004bb757b8d4f8f58725e638b86fb145fdaec1fed46bb33f94b',
    ('news', 'normal_pos'): 'acc07faec62abfbd4c31410a3f748a3cb40832d0a4732ed02f5d046215afae9b',
    ('news', 'plain_dict'): 'acc07faec62abfbd4c31410a3f748a3cb40832d0a4732ed02f5d046215afae9b',
    ('news', 'real_zero'): '7d1f21b005df043e0cf6cc13d3fbfd90e66437a7a80bea169c1dae342c3edf94',
    ('op', 'foreign_dealer_dashdash'): '90fe31e3758a4eaf1355608acbfd315501a16e35dc2f03f3ebc01516dffca91b',
    ('op', 'foreign_dealer_parsed'): '90fe31e3758a4eaf1355608acbfd315501a16e35dc2f03f3ebc01516dffca91b',
    ('op', 'minus_zero'): 'a61a7f9682cf87c3f19d74003c187550292375d7869f5096c1d0143b0f1826a7',
    ('op', 'normal_neg'): '1fe32870db2bdabc0d4136dd3799176b1f9fe0acd8469de6f170d039af67d891',
    ('op', 'normal_pos'): '90fe31e3758a4eaf1355608acbfd315501a16e35dc2f03f3ebc01516dffca91b',
    ('op', 'plain_dict'): '90fe31e3758a4eaf1355608acbfd315501a16e35dc2f03f3ebc01516dffca91b',
    ('op', 'real_zero'): 'a61a7f9682cf87c3f19d74003c187550292375d7869f5096c1d0143b0f1826a7',
}
#: 修前 FinMind 補救 (repr(inst), sorted(unobserved_net))（⛔ 不由現行碼反推）
_QZ20_FM_GOLDEN: dict = {
    'fm_dealer_sell_bad': ('c5dfcbf3133bbf88be2ba6ebee5e5c0060d1c580454643658e34ec88a24dce7f', []),
    'fm_foreign_dealer_bad': ('aa2f899ce2bb7c36239348d572fe2f869e96a02b9533228891588a12f6c94ef8', ['外資及陸資']),
    'fm_good': ('56550c57691a288ac47f886c890e7f2c0bcbda2fa6e82f8e825b652400681f59', []),
    'fm_only_dealer_self': ('aa2f899ce2bb7c36239348d572fe2f869e96a02b9533228891588a12f6c94ef8', []),
    'fm_real_zero': ('b22246bca693f7f7287e12eb0d945ad797a7fed96123c3f5f6b1a531359dbbbf', []),
    'fm_trust_buy_nan': ('b793e1f0c2a3ddee9569cea92dae963be1eb72b21684a78f73a4cacf870fa5cd', []),
    'fm_trust_dealer_nan': ('df25a0194a646cd1d6a4a1156579ab310667c5da82e658ac1893639b0b78a101', []),
}


class TestQz20Fixtures:
    def test_bfi_flags(self):
        for name, (mk, flags) in BFI_UNOBSERVED.items():
            inst = mk()
            assert inst.unobserved_net == frozenset(flags), name
            if name in ('trust_missing', 'trust_dashdash', 'dealer_missing', 'both_missing'):
                for k in flags:
                    assert inst[k]['net'] == 0.0, name      # L1 預填 0.0（既有）
        for name in ('real_zero', 'normal_pos', 'normal_neg'):
            assert OBSERVED[name]().unobserved_net == frozenset(), name
        assert [OBSERVED['real_zero']()[k]['net'] for k in (_TK, _DK)] == [0.0, 0.0]
        assert [OBSERVED['normal_neg']()[k]['net'] for k in (_FK, _TK, _DK)] == [-201.0, -8.0, -3.0]
        for name in ('minus_zero', 'foreign_dealer_dashdash', 'foreign_dealer_parsed'):
            assert OBSERVED[name]().unobserved_net == frozenset(), name
        assert OBSERVED['foreign_dealer_parsed']()[_DK]['net'] == 6.5    # 4.5 ＋ 外資自營商 2.0（既有歸類，未改）
        assert BFI_UNOBSERVED['dealer_one_dashdash'][0]()[_DK]['net'] == 10.0   # 值照舊加總

    def test_dealer_subrow_absent_is_known_limit(self):
        """限制（不猜測）：子列整列不存在（只有自行買賣、沒有避險）無法在不知真實子列名下可靠判斷 ⇒ 維持觀測。"""
        inst = _bfi(dealer=('1,000,000,000', None))
        assert _DK not in inst.unobserved_net and inst[_DK]['net'] == 10.0


class TestQz20Observed:
    @pytest.mark.parametrize('ek', _EXITS)
    @pytest.mark.parametrize('case', sorted(OBSERVED))
    def test_identical_to_pre_fix_golden(self, ek, case, monkeypatch):
        """(4)(5)(9) 真實 0／正負值／plain dict ⇒ 完整輸出逐字同修前 golden。"""
        r = _RUN[ek](_mod(ek), OBSERVED[case](), monkeypatch)
        assert _digest(ek, r) == _QZ20_GOLDEN[(ek, case)]

    def test_real_zero_kept_as_zero(self, monkeypatch):
        """(4) 真實 0 保留 0：柱狀圖畫 0 柱、prompt 照送「+0.0億」、op 送 0.0。"""
        inst = OBSERVED['real_zero']()
        chips = Z33._text('chips', Z33._run_chips(_mod('chips'), inst, monkeypatch))
        assert "'投信', '自營商'" in chips and '⬜ 未取得' not in chips
        prompt = Z33._run_news(_mod('news'), inst, monkeypatch)[0][1]
        assert '• 投信買賣超：+0.0億' in prompt and '• 自營商買賣超：+0.0億' in prompt
        assert _run_op(_mod('op'), inst, monkeypatch)['buys'][1] == 0.0


class TestQz20Unobserved:
    @pytest.mark.parametrize('ek', _EXITS)
    @pytest.mark.parametrize('case', sorted(BFI_UNOBSERVED))
    def test_takes_existing_missing_path(self, ek, case, monkeypatch):
        """(1)(2)(3) 未觀測 ⇒ 完整輸出 ＝ 同一份資料拿掉該 key（＝ 既有缺值路徑，逐字）。"""
        mk, flags = BFI_UNOBSERVED[case]
        got = _RUN[ek](_mod(ek), mk(), monkeypatch)
        ref = _RUN[ek](_mod(ek), _drop(mk(), flags), monkeypatch)
        if ek == 'op':
            # 缺 key 既有送 0、未觀測送 None —— L3 兩者走同一條 `or 0`；畫面逐字相同
            assert got['buys'][1] == (None if _TK in flags else ref['buys'][1])
            assert got['out'] == ref['out']
        else:
            assert got == ref

    @pytest.mark.parametrize('case', sorted(BFI_UNOBSERVED))
    def test_prompt_has_no_fake_zero(self, case, monkeypatch):
        """(8) AI prompt 不再把未觀測輸出成「0 億」：該行整行不送；觀測到的另一類照送。"""
        mk, flags = BFI_UNOBSERVED[case]
        prompt = Z33._run_news(_mod('news'), mk(), monkeypatch)[0][1]
        for k, line in ((_TK, '• 投信買賣超：'), (_DK, '• 自營商買賣超：')):
            assert (line in prompt) is (k not in flags), (case, k)
        assert '+0.0億（系統未對此項設危險門檻）' not in prompt

    @pytest.mark.parametrize('case', sorted(BFI_UNOBSERVED))
    def test_chips_lists_missing_not_zero_bar(self, case, monkeypatch):
        mk, flags = BFI_UNOBSERVED[case]
        txt = Z33._text('chips', Z33._run_chips(_mod('chips'), mk(), monkeypatch))
        names = [n for k, n in ((_TK, '投信'), (_DK, '自營商')) if k in flags]
        assert f'⬜ 未取得：{"、".join(names)}' in txt
        assert '投信買超 0.0億' not in txt


class TestQz20FinMind:
    @pytest.mark.parametrize('name', sorted(FM_CASES))
    def test_flags(self, name, monkeypatch):
        """(6)(7) FinMind 補救：buy／sell 不可解析 ⇒ 該類標未觀測；真實 0（buy＝sell）與正常值 ⇒ 不標。"""
        inst = _fm_inst(monkeypatch, name)
        assert inst.unobserved_net == FM_CASES[name][1]

    @pytest.mark.parametrize('name', sorted(FM_CASES))
    def test_values_identical_to_pre_fix(self, name, monkeypatch):
        """fillna(0) 未動：inst 內容（repr）逐字同修前 golden；旗標只在投信／自營未觀測時多出。"""
        inst = _fm_inst(monkeypatch, name)
        g_repr, g_flags = _QZ20_FM_GOLDEN[name]
        assert _h(repr(inst)) == g_repr
        assert sorted(inst.unobserved_net - {_TK, _DK}) == g_flags

    def test_real_zero_values(self, monkeypatch):
        inst = _fm_inst(monkeypatch, 'fm_real_zero')
        assert inst[_TK]['net'] == 0.0 and inst[_DK]['net'] == 0.0
        assert is_net_observed(inst, _TK) and is_net_observed(inst, _DK)

    @pytest.mark.parametrize('name', ['fm_trust_buy_nan', 'fm_dealer_sell_bad', 'fm_trust_dealer_nan'])
    def test_fallback_unobserved_consumers_take_missing_path(self, name, monkeypatch):
        """(6) FinMind 未取得（buy／sell 缺）⇒ 三個消費點 ＝ 拿掉該 key 的既有缺值路徑。"""
        inst = _fm_inst(monkeypatch, name)
        flags = FM_CASES[name][1]
        for ek in _EXITS:
            got = _RUN[ek](_mod(ek), inst, monkeypatch)
            ref = _RUN[ek](_mod(ek), _drop(inst, flags), monkeypatch)
            if ek == 'op':
                assert got['out'] == ref['out']
            else:
                assert got == ref, ek

    @pytest.mark.parametrize('name', ['fm_trust_buy_nan', 'fm_dealer_sell_bad', 'fm_trust_dealer_nan'])
    def test_mutant_orchestrator_drops_flag(self, name, monkeypatch):
        """突變：還原本批 L3 旗標 ⇒ 投信／自營不標（＝修前）⇒ 上方 test_flags 轉紅。"""
        inst = _fm_inst(monkeypatch, name, orch=z36_pre_module(_ORCH))
        assert not (inst.unobserved_net & {_TK, _DK})


class TestQz20ParserMutation:
    _DEALER_CASES = ('dealer_one_dashdash', 'dealer_one_blank', 'only_foreign_dealer')

    @pytest.mark.parametrize('case', _DEALER_CASES)
    def test_pre_fix_parser_did_not_flag_dealer(self, case, monkeypatch):
        """突變：還原本批 L1 解析器 ⇒ 自營商不標（修前：任一含「自營」列解析到即算觀測）⇒ test_bfi_flags 轉紅。"""
        pre = z36_pre_module(_DDF)
        monkeypatch.setattr(sys.modules[__name__], '_parse_bfi82u_rows', pre._parse_bfi82u_rows)
        assert _DK not in BFI_UNOBSERVED[case][0]().unobserved_net

    @pytest.mark.parametrize('case', sorted(OBSERVED))
    def test_parser_values_and_flags_same_as_pre_fix_for_observed(self, case, monkeypatch):
        """觀測值情境：解析器輸出（值＋旗標）與修前逐字相同。"""
        if case == 'plain_dict':
            pytest.skip('非解析器產生')
        now = OBSERVED[case]()
        monkeypatch.setattr(sys.modules[__name__], '_parse_bfi82u_rows',
                            z36_pre_module(_DDF)._parse_bfi82u_rows)
        pre = OBSERVED[case]()
        assert repr(now) == repr(pre) and now.unobserved_net == pre.unobserved_net

    @pytest.mark.parametrize('case', sorted(BFI_UNOBSERVED))
    def test_parser_values_unchanged_for_unobserved(self, case, monkeypatch):
        """未觀測情境：只多旗標，淨額值（含加總）逐字同修前（⛔ 不改加總值）。"""
        now = BFI_UNOBSERVED[case][0]()
        monkeypatch.setattr(sys.modules[__name__], '_parse_bfi82u_rows',
                            z36_pre_module(_DDF)._parse_bfi82u_rows)
        assert repr(now) == repr(BFI_UNOBSERVED[case][0]())


class TestQz20Mutation:
    @pytest.mark.parametrize('ek', _EXITS)
    @pytest.mark.parametrize('case', sorted(BFI_UNOBSERVED))
    def test_pre_fix_consumer_turns_red(self, ek, case, monkeypatch):
        """還原體（修前）：未觀測照讀預填 0 ⇒ ≠ 既有缺值路徑 ⇒ TestQz20Unobserved 轉紅（op：trust_buy 送 0.0）。"""
        mk, flags = BFI_UNOBSERVED[case]
        pre = z36_pre_module(_REL[ek])
        got = _RUN[ek](pre, mk(), monkeypatch)
        ref = _RUN[ek](pre, _drop(mk(), flags), monkeypatch)
        if ek == 'op':
            if _TK in flags:
                assert got['buys'][1] == 0.0
            else:
                pytest.skip('op 只讀投信（自營商不進個股操作建議）')
        else:
            assert got != ref

    @pytest.mark.parametrize('ek', _EXITS)
    @pytest.mark.parametrize('case', sorted(OBSERVED))
    def test_pre_fix_module_reproduces_golden(self, ek, case, monkeypatch):
        r = _RUN[ek](z36_pre_module(_REL[ek]), OBSERVED[case](), monkeypatch)
        assert _digest(ek, r) == _QZ20_GOLDEN[(ek, case)]


class TestQz20FlagSurvival:
    """旗標存活：pickle 往返（`_pkl_put`／st.cache_data 皆 pickle）、coerce、session 沿用、deepcopy；dict() 會掉（既有限制）。"""

    @staticmethod
    def _inst():
        return BFI_UNOBSERVED['both_missing'][0]()

    def test_pickle_roundtrip(self):
        back = pickle.loads(pickle.dumps((self._inst(), '20261009')))[0]
        assert isinstance(back, InstNetDict) and back.unobserved_net == frozenset({_TK, _DK})

    def test_pkl_put_get_roundtrip(self, tmp_path, monkeypatch):
        import shared.cache_layer as CL
        monkeypatch.setattr(CL, '_PKL_DIR', str(tmp_path))
        CL._pkl_put('institutional', (self._inst(), '20261009'))
        back = CL._pkl_get('institutional', 600)[0]
        assert back.unobserved_net == frozenset({_TK, _DK})

    def test_deepcopy(self):
        assert copy.deepcopy(self._inst()).unobserved_net == frozenset({_TK, _DK})

    def test_coerce_returns_same_object(self):
        from src.compute.macro.macro_helpers import coerce_inst_dict
        inst = self._inst()
        assert coerce_inst_dict({'inst': inst}, where='t') is inst

    def test_session_patch_keeps_object(self):
        """`macro_session_patch` 寫 cl_data／_last_inst：外層 dict() 複製，inst 本身同一物件。"""
        from src.compute.macro import macro_session_patch as P
        import inspect
        inst = self._inst()
        bundle = {'intl_raw': {}, 'tw_raw': {}, 'tech_raw': {}, 'inst': inst, 'inst_date': '20261009',
                  'margin': None, 'df_adl_raw': None, 'df_li_a': None, 'adl_debug_msg': None,
                  'elapsed_s': 0.0}
        fn = next(getattr(P, n) for n in dir(P)
                  if callable(getattr(P, n)) and 'bundle' in inspect.signature(getattr(P, n)).parameters
                  and not n.startswith('_'))
        params = inspect.signature(fn).parameters
        kw = {k: v.default for k, v in params.items() if v.default is not inspect.Parameter.empty}
        args = {'bundle': bundle}
        for k, p in params.items():
            if k not in kw and k != 'bundle':
                args[k] = {} if 'prev' in k else (True if 'heavy' in k else '2026-10-10 15:00')
        out = fn(**args)
        patch = out[0] if isinstance(out, tuple) else out
        assert patch['cl_data']['inst'] is inst and patch['_last_inst'] is inst

    def test_cold_start_prev_cl_data_keeps_object(self, monkeypatch):
        """冷啟動（load_heavy=False）沿用 prev_cl_data['inst']：同一物件、旗標在。"""
        import importlib

        from src.data.macro import leading_indicators as _li_mod
        from src.services import macro_fetch_orchestrator as _orch
        monkeypatch.setattr(importlib, 'reload', lambda m: m)
        monkeypatch.setattr(_li_mod, 'build_leading_fast', lambda **kw: None, raising=False)
        inst = self._inst()
        b = _orch.fetch_macro_bundle(
            load_heavy=False, prev_cl_data={'inst': inst, 'inst_date': '20261009'}, fm_token='',
            li_token='', bps_session=None, intl_map={'x': 'X'}, tw_map={'台股加權指數': '^TWII'},
            tech_map={'y': 'Y'}, fetch_single=lambda *a, **kw: None,
            fetch_institutional=lambda *a, **kw: ({}, '20261009'),
            fetch_margin_balance=lambda *a, **kw: None, fetch_adl=lambda *a, **kw: None)
        assert b['inst'] is inst and not is_net_observed(b['inst'], _TK)

    def test_dict_copy_drops_flag_known_limit(self):
        """既有限制（未改）：`dict(inst)` 複製會掉旗標 ⇒ 退回讀 net 原值。現行 repo 消費鏈無此複製（見本批報告）。"""
        assert not hasattr(dict(self._inst()), 'unobserved_net')
        assert is_net_observed(dict(self._inst()), _TK)
