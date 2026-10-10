"""批 Z34 —— 客戶 2026-10-10 裁示 Q-z12＝A、Q-z13＝A、Q-z14＝A（最小方案；基底 origin/main `76cac7cb`，含批 Z33 #820）。

- Q-z12（C9-n4，L5 `section_news_ai.py` §十一 卡）：找不到 `macro_state.json`（或讀不出來）時 `load_macro_state()`
  回 L3 `_DEFAULT_STATE`（`systemic_risk_level='危險'`、`timestamp=''`），卡片修前畫紅框「系統風險：危險」、同卡卻寫
  「裁決時間：尚未執行」⇒ 以同卡既有訊號「timestamp 為空」（＝「裁決時間：尚未執行」）判定 ⇒ 風險等級改「無法判定」、
  框色改同檔既有灰 `#8b949e`。⛔ `_DEFAULT_STATE` 本身與其他讀它的 fail-safe 消費點不動；有 timestamp 的檔（含
  `execute_and_lock` 失敗時寫下的 fail-safe「系統異常／危險」）逐字不變。
- Q-z13（Z3-n8＋C8-n8，L5 `section_mid.py` §八 火力分級卡）：第一環只因 VIX 或外資期貨未取得而沒過（沒有任何
  「已知且不利」條件）時，L3 `allocation_service._derive_intrinsic_caps` 實際**未套用**第一環天花板 ⇒ 卡片修前畫紅
  「🚫 禁止攻擊」＋操作指示＋腳註「（已納入本環天花板）」是不實的 ⇒ 改同 tab 既有「⬜ 無法判定」＋灰框，說明句沿用
  L3 既有句（逐字，由 L3 公開函式 `ring1_data_incomplete_note` 產生，`_derive_intrinsic_caps` 同用），該情境腳註
  刪去「（已納入本環天花板）」。⛔ 第一環門檻與判定式不動；有已知不利條件（L3 有套天花板）時卡片逐字不變。
- Q-z14（Z9-n2，L3 `macro_state_locker.calculate_system_state`）：8 項數值輸入全缺時修前落檔「震盪／警告／曝險上限
  60%」（60 為純基準分）⇒ 改回既有 fail-safe `_DEFAULT_STATE` 的「系統異常／危險／0」（＋`missing_inputs`）；
  `lock_system_state_only` 收到 fail-safe 時 `analysis_summary` 沿用 `_DEFAULT_STATE` 原句（與 `execute_and_lock`
  失敗時寫下的 fail-safe 同形）。下游 `get_macro_state` 既有規則把「系統異常」當未載入 ⇒ 不給曝險上限、ai_qa 回
  ok=False。⛔ 至少一項有效時模型、門檻、權重、輸出逐字不變。

golden：修前輸出於基底 `76cac7cb` 以本檔同一支 harness 實跑後寫死（⛔ 不由現行碼反推）。
"""
from __future__ import annotations

import hashlib
import json
import math
import types

import numpy as np
import pandas as pd
import pytest

import src.services.allocation_service as AS
import src.services.macro_state_locker as MSL
import src.ui.tabs.macro.section_chips as SC
import src.ui.tabs.macro.section_mid as MID
import src.ui.tabs.macro.section_news_ai as NEWS
import tests.test_batch_z7 as Z7
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from tests.test_m2n2_no_zero_fill import _FakeST, _Rerun

_GRAY = '#8b949e'


def _digest(out) -> str:
    return hashlib.sha256('\x1e'.join(f'{k}\x1f{t}' for k, t in out).encode('utf-8')).hexdigest()


def _h(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


# ══════════════════════════════════════════════════════════════════════════
# harness
# ══════════════════════════════════════════════════════════════════════════
_MISSING = object()   # 沒有 macro_state.json
_CORRUPT = object()   # 檔在但 JSON 壞掉


def _news(mp, tmp_path, state=_MISSING, *, alloc_loaded=False, mod=NEWS):
    """實跑 §十一（未按任何鈕）；cwd 切到 tmp（線上常態：沒有 macro_state.json）。回 fake.out。"""
    d = tmp_path / 'z34news'
    d.mkdir(exist_ok=True)
    f = d / 'macro_state.json'
    if f.exists():
        f.unlink()
    if state is _CORRUPT:
        f.write_text('{bad json', encoding='utf-8')
    elif isinstance(state, dict):
        f.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
    mp.chdir(d)
    fake = _FakeST({})
    mp.setattr(mod, 'st', fake)
    mp.setattr(mod, 'render_macro_bucket_summary_bar', lambda *a, **k: None)
    if alloc_loaded:
        alloc = types.SimpleNamespace(is_loaded=True, final_mid=40, range_text='30–50%')
        sleeves = {'貨幣/現金': 60}
    else:
        alloc, sleeves = types.SimpleNamespace(is_loaded=False), None
    mp.setattr(AS, 'get_allocation', lambda *a, **k: alloc)
    mp.setattr(AS, 'get_allocation_sleeves', lambda *a, **k: sleeves)
    mod.render_section_news_ai({}, 'unknown')
    return list(fake.out)


def _verdict_card(out) -> str:
    cards = [t for k, t in out if k == 'markdown' and '系統風險：' in t]
    assert len(cards) == 1
    return cards[0]


_NOLI = object()      # session 沒有 li_latest（外資期貨未取得）
_DROPVIX = Z7._DROP   # macro_info 沒有 vix 鍵


def _mid_ss(vix, fut):
    info = dict(Z7._MID_BASE)
    if vix is not _DROPVIX:
        info['vix'] = Z7._node(vix)
    ss = {'macro_info': info, 'bias_info': {'bias_240': 5.0}}
    if fut is not _NOLI:
        ss['li_latest'] = pd.DataFrame({'日期': ['2026-10-01'], '外資大小': [fut]})
    return ss


def _mid(mp, vix, fut, *, mod=MID):
    """實跑 §八（`_load_heavy=False`；§三 入口 stub 為 None、L3 登記類 stub）。回 fake.out。"""
    fake = Z7._FakeSTFig(_mid_ss(vix, fut))
    mp.setattr(mod, 'st', fake)
    mp.setattr(SC, 'read_v4_macro_veto', lambda *a, **k: None)
    mp.setattr(AS, 'apply_vix_veto', lambda *a, **k: None)
    mp.setattr(AS, 'apply_ring_gate', lambda *a, **k: None)
    mp.setattr(AS, 'register_conflict', lambda *a, **k: None)
    mp.setattr(AS, 'get_allocation', lambda *a, **k: types.SimpleNamespace(is_loaded=False, final_hi=None))
    mod.render_section_mid(False, {}, {}, {})
    return list(fake.out)


def _atk_card(out) -> str:
    cards = [t for k, t in out if k == 'markdown' and '第一環（解除保險）' in t]
    assert len(cards) == 1
    return cards[0]


def _l3_ring(mp, vix, fut):
    """L3 實算：同一份 session 下 `_derive_intrinsic_caps()` 是否套用「三環第一環」天花板＋其說明句。"""
    mp.setattr(AS, 'st', types.SimpleNamespace(session_state=_mid_ss(vix, fut)))
    caps, conf = AS._derive_intrinsic_caps()
    return any(c.name == '三環第一環' for c in caps), [c for c in conf if '三環第一環' in c]


_ENGINE_KEYS = MSL._ENGINE_NUMERIC_INPUTS


# ══════════════════════════════════════════════════════════════════════════
# 1. Q-z12：缺 macro_state.json ⇒ §十一 灰框「系統風險：無法判定」
# ══════════════════════════════════════════════════════════════════════════
_TS = '2026-10-10 09:00:00'
_STATES = {
    'safe': {'market_regime': '多頭', 'systemic_risk_level': '安全', 'exposure_limit_pct': 80,
             'Macro_Phase': '環境正常', 'timestamp': _TS},
    'warn': {'market_regime': '震盪', 'systemic_risk_level': '警告', 'exposure_limit_pct': 60,
             'Macro_Phase': 'x', 'timestamp': _TS},
    'danger': {'market_regime': '空頭', 'systemic_risk_level': '危險', 'exposure_limit_pct': 30,
               'Macro_Phase': 'x', 'timestamp': _TS},
    # execute_and_lock 失敗時寫下的既有 fail-safe（有 timestamp）—— ⛔ 不動
    'failsafe_ts': {**MSL._DEFAULT_STATE, 'timestamp': _TS},
}

#: 基底 `76cac7cb` 實跑（本檔 `_news` harness）整段 §十一 輸出 sha256；鍵＝(狀態, 建議持股是否已評估)。
_NEWS_BASE = {
    ('missing', False): '9a50e071086e640ebafe9be09eb1c92e3f2f5c2c73919df3c867d7c74c211fb7',
    ('missing', True): '054eb3b86e3d155514fdecceb0d7e73c60abab3b18e37ee3536637021050cc87',
    ('corrupt', False): '9a50e071086e640ebafe9be09eb1c92e3f2f5c2c73919df3c867d7c74c211fb7',
    ('corrupt', True): '054eb3b86e3d155514fdecceb0d7e73c60abab3b18e37ee3536637021050cc87',
    ('safe', False): 'd4f25b984c8cff5c7b0bce1c7a99562e5df5e136e6f913ffbcb233070b74c19b',
    ('safe', True): '646d475b598c35554c4b4ad7c627a306db69dfcaaff063397b74168b2e244370',
    ('warn', False): '86163ba741cabdb674e27467b0075dc037d870af0046a27d1c69f9c5db64f3d9',
    ('warn', True): '861df295e8a5eb38395f95df37d2b2a99d6a3640d046238ee5864039e1e36906',
    ('danger', False): 'ea2103a2f93325951a7edf3845a6b7049be8dd332e6433cf2a4c391f55c9aa64',
    ('danger', True): 'cbf6f2fd6626bcea05908eb5bf8136c50acfaf77b7ccd06501eaf23a9609e924',
    ('failsafe_ts', False): '14f7067a2ffa56aaa1ad2340ae7e7ab5cc2a6e74d4723918d1377ee0afefea87',
    ('failsafe_ts', True): '8688054c21d946f58719c0c200511160ae37e75d67d30bf6333787b855a9bc7f',
}
_NOFILE = {'missing': _MISSING, 'corrupt': _CORRUPT}


def _news_back_to_red(t: str) -> str:
    """把 §十一 卡的灰框／灰章／「無法判定」／灰色持股數字換回修前紅框／紅章／「危險」／紅數字（只動該卡）。"""
    R = TRAFFIC_RED
    return (t.replace(f'border:2px solid {_GRAY};border-radius:12px;padding:18px 20px;',
                      f'border:2px solid {R};border-radius:12px;padding:18px 20px;')
             .replace(f'background:{_GRAY}22;border:1px solid {_GRAY};', f'background:{R}22;border:1px solid {R};')
             .replace(f'font-weight:700;color:{_GRAY};">系統風險：無法判定</span>',
                      f'font-weight:700;color:{R};">系統風險：危險</span>')
             .replace(f'font-size:48px;font-weight:900;color:{_GRAY};', f'font-size:48px;font-weight:900;color:{R};'))


class TestQz12MissingStateFile:
    @pytest.mark.parametrize('loaded', [False, True], ids=['alloc-unloaded', 'alloc-loaded'])
    @pytest.mark.parametrize('nofile', sorted(_NOFILE))
    def test_gray_cannot_judge(self, nofile, loaded, monkeypatch, tmp_path):
        card = _verdict_card(_news(monkeypatch, tmp_path, _NOFILE[nofile], alloc_loaded=loaded))
        assert '系統風險：無法判定' in card and '危險' not in card
        assert TRAFFIC_RED not in card and TRAFFIC_YELLOW not in card and TRAFFIC_GREEN not in card
        assert f'border:2px solid {_GRAY};' in card
        assert '裁決時間：尚未執行' in card            # 其餘卡片文字照舊
        assert '>系統異常</span>' in card              # 市場體制原字照舊（本就灰）

    @pytest.mark.parametrize('loaded', [False, True], ids=['alloc-unloaded', 'alloc-loaded'])
    @pytest.mark.parametrize('nofile', sorted(_NOFILE))
    def test_only_risk_value_and_color_changed(self, nofile, loaded, monkeypatch, tmp_path):
        """修前（基底實跑）：同卡紅框「系統風險：危險」。把那幾處換回紅／危險後整段等於基底。"""
        out = _news(monkeypatch, tmp_path, _NOFILE[nofile], alloc_loaded=loaded)
        undone = [(k, _news_back_to_red(t)) if '系統風險：' in t else (k, t) for k, t in out]
        assert sum(a != b for a, b in zip(out, undone)) == 1
        assert _digest(undone) == _NEWS_BASE[(nofile, loaded)]
        assert _digest(out) != _NEWS_BASE[(nofile, loaded)]

    @pytest.mark.parametrize('loaded', [False, True], ids=['alloc-unloaded', 'alloc-loaded'])
    @pytest.mark.parametrize('state', sorted(_STATES))
    def test_existing_files_unchanged(self, state, loaded, monkeypatch, tmp_path):
        """有 timestamp 的檔（含既有 fail-safe「系統異常／危險」）整段與基底逐字相同。"""
        assert _digest(_news(monkeypatch, tmp_path, _STATES[state], alloc_loaded=loaded)) == \
            _NEWS_BASE[(state, loaded)]

    def test_default_state_untouched(self):
        """L3 `_DEFAULT_STATE`（其他 fail-safe 消費點讀它）一字不動。"""
        assert MSL._DEFAULT_STATE == {
            'market_regime': '系統異常', 'systemic_risk_level': '危險', 'exposure_limit_pct': 0,
            'Macro_Phase': '系統異常',
            'analysis_summary': '系統防護機制啟動：無法取得有效的總經與新聞數據，強制將風險部位降至零。請執行 AI 裁決後更新。',
            'timestamp': ''}


# ══════════════════════════════════════════════════════════════════════════
# 2. Q-z13：§八 第一環只因資料未取得而沒過 ⇒ 「⬜ 無法判定」＋L3 既有說明句、刪不實腳註
# ══════════════════════════════════════════════════════════════════════════
_FOOT = '（已納入本環天花板）'
_OLD_TXT = '第一環未通過（VIX過高 或 外資重兵空單）：大環境有鬼，任何技術面突破均為誘多，嚴格停損保留現金。'
_MISS_VIX = [pytest.param(_DROPVIX, id='vix-nokey'), pytest.param(None, id='vix-None'),
             pytest.param(math.nan, id='vix-nan'), pytest.param(math.inf, id='vix-pinf'),
             pytest.param(-math.inf, id='vix-ninf'), pytest.param(pd.NA, id='vix-pdNA')]
_MISS_FUT = [pytest.param(_NOLI, id='fut-noli'), pytest.param(None, id='fut-None'),
             pytest.param(math.nan, id='fut-nan'), pytest.param(math.inf, id='fut-pinf'),
             pytest.param(-math.inf, id='fut-ninf'), pytest.param(pd.NA, id='fut-pdNA')]

#: 基底 `76cac7cb` 實跑（本檔 `_mid` harness）整段 §八 輸出 sha256。
_MID_BASE = {
    # —— 修前誤畫「🚫 禁止攻擊」的情境（本批改）——
    'vixnokey': (_DROPVIX, 5000.0, '3af6b327eb493a98b84ef88e8948e33d0ee1b50aa43dbed5ba83fe02e408f79c'),
    'vixnone': (None, 5000.0, '3af6b327eb493a98b84ef88e8948e33d0ee1b50aa43dbed5ba83fe02e408f79c'),
    'vixnan': (math.nan, 5000.0, 'e8c309e197dcf35a9a11b35fdf5a26b93d3ea70eef02010d23c9f615c774b9b9'),
    'vixinf': (math.inf, 5000.0, 'e8c309e197dcf35a9a11b35fdf5a26b93d3ea70eef02010d23c9f615c774b9b9'),
    'vixninf': (-math.inf, 5000.0, 'e8c309e197dcf35a9a11b35fdf5a26b93d3ea70eef02010d23c9f615c774b9b9'),
    'vixna': (pd.NA, 5000.0, 'e8c309e197dcf35a9a11b35fdf5a26b93d3ea70eef02010d23c9f615c774b9b9'),
    'futnoli': (18.0, _NOLI, '2601c9816fbd3736278e323c48529ab2585eea88f5f45aa0480b5903d5d66f6a'),
    'futnone': (18.0, None, '2601c9816fbd3736278e323c48529ab2585eea88f5f45aa0480b5903d5d66f6a'),
    'futnan': (18.0, math.nan, '2601c9816fbd3736278e323c48529ab2585eea88f5f45aa0480b5903d5d66f6a'),
    'futinf': (18.0, math.inf, '2601c9816fbd3736278e323c48529ab2585eea88f5f45aa0480b5903d5d66f6a'),
    'futninf': (18.0, -math.inf, '2601c9816fbd3736278e323c48529ab2585eea88f5f45aa0480b5903d5d66f6a'),
    'futna': (18.0, pd.NA, '2601c9816fbd3736278e323c48529ab2585eea88f5f45aa0480b5903d5d66f6a'),
    'both': (_DROPVIX, _NOLI, '01048a111d6714539f562c877d50631981cfb139e6603c97c385118aac57ff3a'),
    'bothnan': (math.nan, math.nan, '6154973c5c6efd5c3b7e9b10873970fda01f8b641eb908c5e00cedf80309d3f0'),
}
#: 同上，資料齊全／有已知不利條件（L3 有套或確實通過）—— ⛔ 逐字不變。
_MID_KEEP = {
    'pass': (18.0, 5000.0, '7617e1a75c4018c5f80946c083098e77bda1055d0205568ebf7977a811f97880'),
    'vixfail': (25.0, 5000.0, 'ac7f5cf6297fdfc3937cbef7cca579010522c57e39c079405b584685052f70a1'),
    'futfail': (18.0, -20000.0, '18f9eaad8fb19ac4f33e4bb6eb9e445815746d6307763852c11744f64355d798'),
    'vixfail_futnone': (25.0, _NOLI, 'c18acd0a579ced58de996b625d013860595793c34482120a7888907787a7732f'),
    'vixnone_futfail': (_DROPVIX, -20000.0, '102d91bcf3ad89e9523a015c7a43d5224de8f395940a3077524f030137dba9f6'),
    'vixnan_futfail': (math.nan, -40000.0, 'aaad020fb7065ae7de041d4a8dcf8f61d1b63bfcdfd74efe33d7a779747258c8'),
    'edge_fut': (15.0, -15000.0, '830954beffb1494ca0dba9ca158b124cfa344fa112461696bde565530a846c57'),
    'edge_vix': (20.0, 5000.0, '2167706731995041ee98bfdca01168c8d295229c85ee751a2b7e3818f109b661'),
    'edge_pass': (19.9, -14999.0, 'e725dbe4c4a8b391947267068f86680835d6528d7cf118635bce3c7c4f17ceea'),
}


def _mid_back_to_red(t: str, note: str) -> str:
    R = TRAFFIC_RED
    return (t.replace(f'border:2px solid {_GRAY};border-radius:12px;padding:16px;',
                      f'border:2px solid {R};border-radius:12px;padding:16px;')
             .replace(f'font-weight:900;color:{_GRAY};">⬜ 無法判定</div>',
                      f'font-weight:900;color:{R};">🚫 禁止攻擊</div>')
             .replace(f'margin:4px 0;">{note}</div>', f'margin:4px 0;">{_OLD_TXT}</div>')
             .replace('🎚️ 建議持股油門</div></div>', f'🎚️ 建議持股油門{_FOOT}</div></div>'))


class TestQz13Ring1Undecided:
    @pytest.mark.parametrize('case', sorted(_MID_BASE))
    def test_card_cannot_judge(self, case, monkeypatch):
        vix, fut, _ = _MID_BASE[case]
        card = _atk_card(_mid(monkeypatch, vix, fut))
        assert '⬜ 無法判定' in card and f'border:2px solid {_GRAY};' in card
        assert '禁止攻擊' not in card and '🚫' not in card and _FOOT not in card
        # 不給任何操作指示（修前那句的停損／保留現金等）
        for w in ('停損', '保留現金', '誘多', '追擊', '佈局', '觀望', '建倉'):
            assert w not in card
        assert '三環第一環資料不全' in card and '未套用該天花板' in card

    @pytest.mark.parametrize('case', sorted(_MID_BASE))
    def test_only_card_changed(self, case, monkeypatch):
        """修前（基底實跑）：紅框「🚫 禁止攻擊」＋停損指示＋腳註。換回後整段等於基底（只差這張卡）。"""
        vix, fut, gold = _MID_BASE[case]
        out = _mid(monkeypatch, vix, fut)
        _, conf = _l3_ring(monkeypatch, vix, fut)
        assert len(conf) == 1
        undone = [(k, _mid_back_to_red(t, conf[0])) if '第一環（解除保險）' in t else (k, t) for k, t in out]
        assert sum(a != b for a, b in zip(out, undone)) == 1
        assert _digest(undone) == gold and _digest(out) != gold

    @pytest.mark.parametrize('case', sorted(_MID_KEEP))
    def test_valid_data_unchanged(self, case, monkeypatch):
        vix, fut, gold = _MID_KEEP[case]
        assert _digest(_mid(monkeypatch, vix, fut)) == gold

    @pytest.mark.parametrize('case', sorted(_MID_KEEP))
    def test_known_fail_keeps_footnote(self, case, monkeypatch):
        vix, fut, _ = _MID_KEEP[case]
        card = _atk_card(_mid(monkeypatch, vix, fut))
        capped, _ = _l3_ring(monkeypatch, vix, fut)
        assert '⬜ 無法判定' not in card and _FOOT in card
        assert ('🚫 禁止攻擊' in card) is capped

    def test_yesterday_value_today_missing(self, monkeypatch):
        """外資期貨昨日 −40,000、今日缺 ⇒ 不以昨日冒充（批 Z30）⇒ L3 未套 ⇒ 卡片無法判定、不出「禁止攻擊」。"""
        ss = _mid_ss(18.0, 0.0)
        ss['li_latest'] = pd.DataFrame({'日期': ['2026-09-30', '2026-10-01'], '外資大小': [-40000.0, math.nan]})
        fake = Z7._FakeSTFig(ss)
        monkeypatch.setattr(MID, 'st', fake)
        monkeypatch.setattr(SC, 'read_v4_macro_veto', lambda *a, **k: None)
        for n in ('apply_vix_veto', 'apply_ring_gate', 'register_conflict'):
            monkeypatch.setattr(AS, n, lambda *a, **k: None)
        monkeypatch.setattr(AS, 'get_allocation', lambda *a, **k: types.SimpleNamespace(is_loaded=False, final_hi=None))
        MID.render_section_mid(False, {}, {}, {})
        card = _atk_card(list(fake.out))
        monkeypatch.setattr(AS, 'st', types.SimpleNamespace(session_state=ss))
        caps, conf = AS._derive_intrinsic_caps()
        assert not any(c.name == '三環第一環' for c in caps)
        assert '⬜ 無法判定' in card and '禁止攻擊' not in card and _FOOT not in card
        assert [c for c in conf if '三環第一環' in c][0] in card

    @pytest.mark.parametrize('fut', _MISS_FUT + [pytest.param(5000.0, id='fut-ok'),
                                                 pytest.param(-20000.0, id='fut-fail'),
                                                 pytest.param(-15000.0, id='fut-edge')])
    @pytest.mark.parametrize('vix', _MISS_VIX + [pytest.param(18.0, id='vix-ok'),
                                                 pytest.param(25.0, id='vix-fail'),
                                                 pytest.param(20.0, id='vix-edge')])
    def test_ui_matches_l3(self, vix, fut, monkeypatch):
        """UI 與實際計算一致：L3 有套第一環天花板 ⇔ 卡片「🚫 禁止攻擊」＋腳註；
        L3 未套且第一環沒過 ⇔ 卡片「⬜ 無法判定」、無腳註、說明句＝L3 conflicts 那一句（逐字）。"""
        card = _atk_card(_mid(monkeypatch, vix, fut))
        capped, conf = _l3_ring(monkeypatch, vix, fut)
        assert ('🚫 禁止攻擊' in card) is capped
        assert (_FOOT in card) is (capped or '⬜ 無法判定' not in card)
        if '⬜ 無法判定' in card:
            assert not capped and len(conf) == 1 and conf[0] in card
        elif not capped:                         # 通過（資料齊全、條件都好）
            assert '禁止攻擊' not in card and not conf

    def test_note_is_l3_single_source(self, monkeypatch):
        """說明句由 L3 單一出處產生，與 `_derive_intrinsic_caps` 寫進 conflicts 的那句逐字相同（修前原句）。"""
        assert AS.ring1_data_incomplete_note(vix_known=True, fut_known=True) is None
        assert AS.ring1_data_incomplete_note(vix_known=False, fut_known=True) == \
            '⚠️ 三環第一環資料不全（VIX 未取得），未套用該天花板 — 數字可能偏樂觀'
        assert AS.ring1_data_incomplete_note(vix_known=True, fut_known=False) == \
            '⚠️ 三環第一環資料不全（外資期貨淨口 未取得），未套用該天花板 — 數字可能偏樂觀'
        assert AS.ring1_data_incomplete_note(vix_known=False, fut_known=False) == \
            '⚠️ 三環第一環資料不全（VIX、外資期貨淨口 未取得），未套用該天花板 — 數字可能偏樂觀'

    #: 基底 `76cac7cb` `_derive_intrinsic_caps()` 實跑（caps 的 (name, pct, reason)、conflicts）。
    _L3_BASE = {
        (None, 5000.0): ([], ['⚠️ 三環第一環資料不全（VIX 未取得），未套用該天花板 — 數字可能偏樂觀']),
        (18.0, None): ([], ['⚠️ 三環第一環資料不全（外資期貨淨口 未取得），未套用該天花板 — 數字可能偏樂觀']),
        (None, None): ([], ['⚠️ 三環第一環資料不全（VIX、外資期貨淨口 未取得），未套用該天花板 — 數字可能偏樂觀']),
        (25.0, None): ([('VIX 否決權', 30, 'VIX 25.0 進入 20–30 警戒帶，停止加槓桿'),
                        ('三環第一環', 20, 'VIX 25.0 ≥ 20')],
                       ['⚠️ 三環第一環資料不全（外資期貨淨口 未取得），未套用該天花板 — 數字可能偏樂觀']),
        (None, -20000.0): ([('三環第一環', 20, '外資期貨 -20,000 口 ≤ -15,000')],
                           ['⚠️ 三環第一環資料不全（VIX 未取得），未套用該天花板 — 數字可能偏樂觀']),
        (18.0, 5000.0): ([], []),
        (31.0, -15000.0): ([('VIX 否決權', 10, 'VIX 31.0 ≥ 30，系統性風險爆發，現金為王'),
                            ('三環第一環', 20, 'VIX 31.0 ≥ 20、外資期貨 -15,000 口 ≤ -15,000')], []),
    }

    @pytest.mark.parametrize('key', sorted(_L3_BASE, key=repr))
    def test_l3_output_unchanged(self, key, monkeypatch):
        vix, fut = key
        monkeypatch.setattr(AS, 'st', types.SimpleNamespace(session_state=_mid_ss(
            _DROPVIX if vix is None else vix, _NOLI if fut is None else fut)))
        caps, conf = AS._derive_intrinsic_caps()
        assert ([(c.name, c.pct, c.reason) for c in caps], conf) == self._L3_BASE[key]


# ══════════════════════════════════════════════════════════════════════════
# 3. Q-z14：8 項總經輸入全缺 ⇒ 既有 fail-safe「系統異常」，不給「震盪／曝險上限 60%」
# ══════════════════════════════════════════════════════════════════════════
_FAILSAFE = {'market_regime': '系統異常', 'systemic_risk_level': '危險', 'exposure_limit_pct': 0,
             'Macro_Phase': '系統異常', 'missing_inputs': list(_ENGINE_KEYS)}
_ALL_MISSING = {
    'empty': {},
    'none': {k: None for k in _ENGINE_KEYS},
    'nan': {k: math.nan for k in _ENGINE_KEYS},
    'pinf': {k: math.inf for k in _ENGINE_KEYS},
    'ninf': {k: -math.inf for k in _ENGINE_KEYS},
    'pdNA': {k: pd.NA for k in _ENGINE_KEYS},
    'npnan': {k: np.float64('nan') for k in _ENGINE_KEYS},
    'text': {k: 'abc' for k in _ENGINE_KEYS},
    'huge': {k: 10 ** 400 for k in _ENGINE_KEYS},
    'mixed_bools': {**{k: v for k, v in zip(_ENGINE_KEYS, (None, math.nan, math.inf, -math.inf, pd.NA,
                                                           'x', None, math.nan))},
                    'Index_Below_MA5': True, 'Sahm_Rule_Triggered': False},
}
_FULL = {'VIX_Index': 18.0, 'ISM_PMI_or_OECD_CLI': 51.0, 'PMI_Prev_Month': 50.5, 'M1B_YoY_pct': 4.0,
         'M2_YoY_pct': 5.0, 'BIAS240_pct': 8.0, 'PCR': 1.0, 'Futures_Net_Short': -5000.0,
         'Index_Below_MA5': False, 'Sahm_Rule_Triggered': False}
_M7 = ['ISM_PMI_or_OECD_CLI', 'PMI_Prev_Month', 'M1B_YoY_pct', 'M2_YoY_pct', 'BIAS240_pct', 'PCR',
       'Futures_Net_Short']
#: 基底 `76cac7cb` `calculate_system_state` 實跑（部分有效／全有效／薩姆已觸發）—— ⛔ 逐字不變。
_ENGINE_BASE = {
    'full': (_FULL, {'market_regime': '震盪', 'systemic_risk_level': '警告', 'exposure_limit_pct': 60,
                     'Macro_Phase': '資金緊縮'}),
    'vix_only': ({'VIX_Index': 15.0}, {'market_regime': '震盪', 'systemic_risk_level': '警告',
                                       'exposure_limit_pct': 60, 'Macro_Phase': '7 項未評估（缺資料不計分）',
                                       'missing_inputs': _M7}),
    'vix_only_rest_nan': ({**{k: math.nan for k in _ENGINE_KEYS}, 'VIX_Index': 15.0},
                          {'market_regime': '震盪', 'systemic_risk_level': '警告', 'exposure_limit_pct': 60,
                           'Macro_Phase': '7 項未評估（缺資料不計分）', 'missing_inputs': _M7}),
    'pcr_only': ({'PCR': 1.6}, {'market_regime': '震盪', 'systemic_risk_level': '警告', 'exposure_limit_pct': 50,
                                'Macro_Phase': '7 項未評估（缺資料不計分）',
                                'missing_inputs': ['VIX_Index', 'ISM_PMI_or_OECD_CLI', 'PMI_Prev_Month',
                                                   'M1B_YoY_pct', 'M2_YoY_pct', 'BIAS240_pct',
                                                   'Futures_Net_Short']}),
    'fut_only_veto': ({'Futures_Net_Short': -40000.0, 'Index_Below_MA5': True},
                      {'market_regime': '空頭', 'systemic_risk_level': '危險', 'exposure_limit_pct': 30,
                       'Macro_Phase': '🚨期貨淨空40000口+破MA5、7 項未評估（缺資料不計分）',
                       'missing_inputs': ['VIX_Index', 'ISM_PMI_or_OECD_CLI', 'PMI_Prev_Month', 'M1B_YoY_pct',
                                          'M2_YoY_pct', 'BIAS240_pct', 'PCR']}),
    'vix_high_only': ({'VIX_Index': 36.0}, {'market_regime': '空頭', 'systemic_risk_level': '危險',
                                            'exposure_limit_pct': 30,
                                            'Macro_Phase': 'VIX高波動(36.0)、7 項未評估（缺資料不計分）',
                                            'missing_inputs': _M7}),
    'bias_only': ({'BIAS240_pct': -12.0}, {'market_regime': '多頭', 'systemic_risk_level': '安全',
                                          'exposure_limit_pct': 70, 'Macro_Phase': '7 項未評估（缺資料不計分）',
                                          'missing_inputs': ['VIX_Index', 'ISM_PMI_or_OECD_CLI', 'PMI_Prev_Month',
                                                             'M1B_YoY_pct', 'M2_YoY_pct', 'PCR',
                                                             'Futures_Net_Short']}),
    'pmi_pair_veto': ({'ISM_PMI_or_OECD_CLI': 45.0, 'PMI_Prev_Month': 47.0},
                      {'market_regime': '震盪', 'systemic_risk_level': '警告', 'exposure_limit_pct': 40,
                       'Macro_Phase': '⚠️PMI連兩月收縮(47.0→45.0)、6 項未評估（缺資料不計分）',
                       'missing_inputs': ['VIX_Index', 'M1B_YoY_pct', 'M2_YoY_pct', 'BIAS240_pct', 'PCR',
                                          'Futures_Net_Short']}),
    'full_bear': ({**_FULL, 'VIX_Index': 36.0, 'ISM_PMI_or_OECD_CLI': 45.0, 'PMI_Prev_Month': 46.0,
                   'Futures_Net_Short': -40000.0, 'Index_Below_MA5': True},
                  {'market_regime': '空頭', 'systemic_risk_level': '危險', 'exposure_limit_pct': 10,
                   'Macro_Phase': '⚠️PMI連兩月收縮(46.0→45.0)、🚨期貨淨空40000口+破MA5、VIX高波動(36.0)、資金緊縮'}),
    # 薩姆 bool 已觸發＝有資料（屬「部分有效」），照舊走紅線
    'sahm_all_missing': ({'Sahm_Rule_Triggered': True},
                         {'market_regime': '空頭', 'systemic_risk_level': '危險', 'exposure_limit_pct': 20,
                          'Macro_Phase': '🚨薩姆規則觸發、8 項未評估（缺資料不計分）',
                          'missing_inputs': list(_ENGINE_KEYS)}),
}
#: 基底 `76cac7cb` 實跑：8 項全缺時落檔的結論（本批要消掉的）。
_ENGINE_ALL_MISSING_BASE = {'market_regime': '震盪', 'systemic_risk_level': '警告', 'exposure_limit_pct': 60,
                            'Macro_Phase': '8 項未評估（缺資料不計分）', 'missing_inputs': list(_ENGINE_KEYS)}


class TestQz14AllMissingFailSafe:
    @pytest.mark.parametrize('case', sorted(_ALL_MISSING))
    def test_all_missing_is_failsafe(self, case):
        got = MSL.calculate_system_state(_ALL_MISSING[case])
        assert got == _FAILSAFE and got != _ENGINE_ALL_MISSING_BASE
        assert '震盪' not in json.dumps(got, ensure_ascii=False) and got['exposure_limit_pct'] != 60
        for k in ('market_regime', 'systemic_risk_level', 'exposure_limit_pct', 'Macro_Phase'):
            assert got[k] == MSL._DEFAULT_STATE[k]          # 沿用既有 fail-safe，不新增數字

    @pytest.mark.parametrize('case', sorted(_ENGINE_BASE))
    def test_partial_and_full_unchanged(self, case):
        inp, gold = _ENGINE_BASE[case]
        assert MSL.calculate_system_state(inp) == gold

    def test_locked_file_matches_existing_failsafe(self, monkeypatch, tmp_path):
        """落檔形狀＝`execute_and_lock` 失敗時寫下的 fail-safe（`_DEFAULT_STATE`＋timestamp），多帶 missing_inputs／資料月。"""
        monkeypatch.setattr(MSL, '_now_str', lambda: _TS)
        p_new, p_ref = tmp_path / 'a.json', tmp_path / 'b.json'
        MSL.MacroStateLocker(state_file_path=str(p_new)).lock_system_state_only(
            {**MSL.calculate_system_state({}), 'm1b_m2_data_month': None})

        def _bad_llm(prompt):
            raise RuntimeError('x')
        MSL.MacroStateLocker(llm_client=_bad_llm, state_file_path=str(p_ref)).execute_and_lock({}, [])
        new = json.loads(p_new.read_text(encoding='utf-8'))
        ref = json.loads(p_ref.read_text(encoding='utf-8'))
        assert {k: v for k, v in new.items() if k not in ('missing_inputs', 'm1b_m2_data_month')} == ref
        assert new['missing_inputs'] == list(_ENGINE_KEYS) and new['m1b_m2_data_month'] is None
        assert '曝險上限' not in new['analysis_summary'] and '60' not in json.dumps(new)

    def test_locked_partial_summary_unchanged(self, monkeypatch, tmp_path):
        """基底實跑：部分有效時落檔摘要「曝險上限 60%（Python 規則引擎計算）」逐字不變。"""
        monkeypatch.setattr(MSL, '_now_str', lambda: _TS)
        p = tmp_path / 'c.json'
        MSL.MacroStateLocker(state_file_path=str(p)).lock_system_state_only(
            {**MSL.calculate_system_state({'VIX_Index': 15.0}), 'm1b_m2_data_month': None})
        assert json.loads(p.read_text(encoding='utf-8')) == {
            **_ENGINE_BASE['vix_only'][1], 'm1b_m2_data_month': None,
            'analysis_summary': '曝險上限 60%（Python 規則引擎計算）', 'timestamp': _TS}

    def _lock_all_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(MSL, '_now_str', lambda: _TS)
        d = tmp_path / 'lk'
        d.mkdir(exist_ok=True)
        MSL.MacroStateLocker(state_file_path=str(d / 'macro_state.json')).lock_system_state_only(
            {**MSL.calculate_system_state({}), 'm1b_m2_data_month': None})
        return d

    def test_downstream_treats_as_unloaded(self, monkeypatch, tmp_path):
        """下游 `get_macro_state` 既有規則：「系統異常」＝未載入 ⇒ 不給曝險上限（不是 60、也不是 0）。"""
        d = self._lock_all_missing(monkeypatch, tmp_path)
        now = pd.Timestamp('2026-10-10 10:00:00', tz='Asia/Taipei').to_pydatetime()
        ms = MSL.get_macro_state(None, state_file_path=str(d / 'macro_state.json'), now=now)
        assert ms['is_loaded'] is False and ms['exposure_limit_pct'] is None
        assert ms['regime'] == 'unknown' and ms['light'] == '⬜'
        # 修前基底落檔（震盪／60）⇒ 同一支讀取會當「已載入、曝險上限 60%」
        (d / 'base.json').write_text(json.dumps({**_ENGINE_ALL_MISSING_BASE, 'timestamp': _TS},
                                                ensure_ascii=False), encoding='utf-8')
        mb = MSL.get_macro_state(None, state_file_path=str(d / 'base.json'), now=now)
        assert mb['is_loaded'] is True and mb['exposure_limit_pct'] == 60

    def test_ai_qa_not_ok(self, monkeypatch, tmp_path):
        """ai_qa「目前總經狀態」同源：讀到 fail-safe 檔 ⇒ 走既有「總經尚未評估」ok=False（修前 ok=True＋60）。"""
        import src.services.ai_qa_service as QA
        d = self._lock_all_missing(monkeypatch, tmp_path)
        monkeypatch.chdir(d)
        monkeypatch.setattr(AS, 'st', types.SimpleNamespace(session_state={}))
        monkeypatch.setattr(MSL, 'macro_state_is_expired', lambda *a, **k: False)
        r = QA._tool_get_market_state()
        assert r['ok'] is False and '總經尚未評估' in r['error']

    @pytest.mark.parametrize('loaded', [False, True], ids=['alloc-unloaded', 'alloc-loaded'])
    def test_section11_card_all_missing_not_danger(self, loaded, monkeypatch, tmp_path):
        """總管複驗（Q-z12 × Q-z14）：§十一 讀到 8 項全缺落檔的 fail-safe ⇒ 不得畫「危險」紅框 ⇒ 同 Q-z12 灰框「無法判定」；
        其餘（市場體制「系統異常」、裁決時間）照舊 —— 換回紅／危險後＝基底「fail-safe 檔」實跑。"""
        d = self._lock_all_missing(monkeypatch, tmp_path)
        state = json.loads((d / 'macro_state.json').read_text(encoding='utf-8'))
        out = _news(monkeypatch, tmp_path, state, alloc_loaded=loaded)
        card = _verdict_card(out)
        assert '系統風險：無法判定' in card and '危險' not in card and TRAFFIC_RED not in card
        assert f'裁決時間：{_TS}' in card and '>系統異常</span>' in card
        undone = [(k, _news_back_to_red(t)) if '系統風險：' in t else (k, t) for k, t in out]
        assert _digest(undone) == _NEWS_BASE[('failsafe_ts', loaded)]

    @pytest.mark.parametrize('loaded', [False, True], ids=['alloc-unloaded', 'alloc-loaded'])
    def test_section11_ai_failure_file_unchanged(self, loaded, monkeypatch, tmp_path):
        """execute_and_lock（AI）失敗檔（無 missing_inputs）⇒ 照舊紅「危險」，與基底逐字相同。"""
        monkeypatch.setattr(MSL, '_now_str', lambda: _TS)
        p = tmp_path / 'ai_fail.json'

        def _bad_llm(prompt):
            raise RuntimeError('x')
        MSL.MacroStateLocker(llm_client=_bad_llm, state_file_path=str(p)).execute_and_lock({}, [])
        state = json.loads(p.read_text(encoding='utf-8'))
        assert 'missing_inputs' not in state
        out = _news(monkeypatch, tmp_path, state, alloc_loaded=loaded)
        assert _digest(out) == _NEWS_BASE[('failsafe_ts', loaded)]
        assert '系統風險：危險' in _verdict_card(out)

    @pytest.mark.parametrize('loaded', [False, True], ids=['alloc-unloaded', 'alloc-loaded'])
    @pytest.mark.parametrize('inp', [{'VIX_Index': 15.0}, {'VIX_Index': 36.0}, {'BIAS240_pct': -12.0},
                                     {'Sahm_Rule_Triggered': True}],
                             ids=['vix15', 'vix36', 'bias', 'sahm-all-missing'])
    def test_section11_partial_locked_file_unchanged(self, inp, loaded, monkeypatch, tmp_path):
        """部分有效（落檔帶 missing_inputs、但不是「系統異常」）⇒ 與修前碼逐字相同（還原體＝基底 sha，見 §4）。"""
        monkeypatch.setattr(MSL, '_now_str', lambda: _TS)
        p = tmp_path / 'partial.json'
        MSL.MacroStateLocker(state_file_path=str(p)).lock_system_state_only(
            {**MSL.calculate_system_state(inp), 'm1b_m2_data_month': None})
        state = json.loads(p.read_text(encoding='utf-8'))
        assert state['missing_inputs'] and state['market_regime'] != '系統異常'
        card = _verdict_card(_news(monkeypatch, tmp_path, state, alloc_loaded=loaded))
        assert f"系統風險：{state['systemic_risk_level']}</span>" in card and '無法判定' not in card
        assert _news(monkeypatch, tmp_path, state, alloc_loaded=loaded) == \
            _news(monkeypatch, tmp_path, state, alloc_loaded=loaded, mod=z34_pre_module('news'))

    def test_verdict_button_locks_failsafe(self, monkeypatch, tmp_path):
        """§十一「🔒 執行 AI 裁決」：session 8 項全缺 ⇒ 鎖定的是 fail-safe，不是「震盪／60」。"""
        import src.data.news as N
        import src.services.app_ai_service as A
        fake = _FakeST({}, clicked={'btn_run_verdict'})
        locked: list = []

        class _Locker:
            def lock_system_state_only(self, state):
                locked.append(state)

        monkeypatch.setattr(NEWS, 'st', fake)
        monkeypatch.setattr(NEWS, 'render_macro_bucket_summary_bar', lambda *a, **k: None)
        monkeypatch.setattr(NEWS, 'MacroStateLocker', _Locker)
        monkeypatch.setattr(A, 'gemini_call', lambda *a, **k: '（測試替身報告）')
        monkeypatch.setattr(N, 'fetch_macro_news', lambda *a, **k: [])
        with pytest.raises(_Rerun):
            NEWS.render_section_news_ai({}, 'unknown')
        assert len(locked) == 1
        assert {k: locked[0][k] for k in _FAILSAFE} == _FAILSAFE
        assert '震盪' not in json.dumps(locked[0], ensure_ascii=False)


# ══════════════════════════════════════════════════════════════════════════
# 4. 還原 pair（修後 → 修前，每組恰好一處；比照 Z30／Z31／Z33 慣例供其他測試檔「還原成修前原始碼」沿用）
# ══════════════════════════════════════════════════════════════════════════
_Z34_MID_BLOCK = (
    "            # 批 Z34（Z3-n8＋C8-n8，客戶 2026-10-10 Q-z13＝A）：第一環沒過、但沒有任何「已知且不利」的條件\n"
    "            #   （只因 VIX／外資期貨未取得）⇒ L3 `_derive_intrinsic_caps` 同一規則下**未套用**第一環天花板，\n"
    "            #   修前卻畫「🚫 禁止攻擊」＋操作指示＋腳註「已納入本環天花板」。改走同 tab 既有「⬜ 無法判定」＋同檔灰，\n"
    "            #   說明句沿用 L3 既有句（`ring1_data_incomplete_note`，逐字），不給操作指示；腳註刪「（已納入本環天花板）」。\n"
    "            #   判定只用上方既有 `_cA`／`_cB`（門檻一位未動）；有已知不利條件時（L3 有套天花板）走原分支、逐字不變。\n"
    "            _ring1_known_fail = ((_vix_now8 is not None and not _cA)\n"
    "                                 or (_fut8 is not None and not _cB))\n"
    "            _ring1_undecided = not _ring1_pass and not _ring1_known_fail\n"
    "            if _ring1_undecided:\n"
    "                _atk_color = '#8b949e'\n"
    "                _atk_grade = '⬜ 無法判定'\n"
    "                _atk_txt = ring1_data_incomplete_note(\n"
    "                    vix_known=_vix_now8 is not None, fut_known=_fut8 is not None)\n"
    "            elif not _ring1_pass:\n")
_Z34_NEWS_BLOCK = (
    "        # 批 Z34（C9-n4，客戶 2026-10-10 Q-z12＝A）：沒有可用的 macro_state.json（缺檔／讀不出來）時\n"
    "        #   `load_macro_state()` 回 L3 `_DEFAULT_STATE`（風險「危險」、timestamp 空）——那是「還沒裁決」，\n"
    "        #   不是偵測到危險。以同卡既有訊號「timestamp 為空」（＝下方「裁決時間：尚未執行」）判定 ⇒\n"
    "        #   風險等級改「無法判定」（下方對照表查無 ⇒ 同檔既有灰 #8b949e）。`_DEFAULT_STATE` 與其他消費點不動；\n"
    "        #   有 timestamp 的檔（含 execute_and_lock 失敗時寫下的 fail-safe）逐字不變。\n"
    "        #   另：規則引擎 8 項輸入全缺時落檔的 fail-safe（Q-z14；「系統異常」＋引擎的 `missing_inputs`）同屬「缺資料」，\n"
    "        #   同樣不得畫成「危險」。AI 失敗檔不帶 `missing_inputs`、部分有效檔不會是「系統異常」⇒ 皆不受影響。\n"
    "        if not _ms_ts or (_regime == '系統異常' and _ms.get('missing_inputs')):\n"
    "            _srl = '無法判定'\n")
_Z34_MSL_EARLY = (
    "    # 批 Z34（Z9-n2，客戶 2026-10-10 Q-z14＝A）：8 項數值輸入**全缺**時，下方計分只剩中性基準 60，\n"
    "    #   修前落檔「震盪／警告／曝險上限 60%」—— 沒有任何資料卻給出正常投資結論。改回既有 fail-safe\n"
    "    #   `_DEFAULT_STATE`（「系統異常」；`get_macro_state` 既有規則視同未載入、不給曝險上限），不新增任何數字。\n"
    "    #   薩姆規則 bool 已觸發屬「有資料」，照舊走下方紅線（not sahm 才短路）。至少一項有效 → 本段不進、輸出逐字不變。\n"
    "    if len(missing_inputs) == len(_ENGINE_NUMERIC_INPUTS) and not sahm:\n"
    "        return {\n"
    "            \"market_regime\": _DEFAULT_STATE[\"market_regime\"],\n"
    "            \"systemic_risk_level\": _DEFAULT_STATE[\"systemic_risk_level\"],\n"
    "            \"exposure_limit_pct\": _DEFAULT_STATE[\"exposure_limit_pct\"],\n"
    "            \"Macro_Phase\": _DEFAULT_STATE[\"Macro_Phase\"],\n"
    "            \"missing_inputs\": missing_inputs,\n"
    "        }\n"
    "\n")
_Z34_MSL_LOCK_OLD = (
    "            \"analysis_summary\": f\"曝險上限 {system_state.get('exposure_limit_pct', 0)}%（Python 規則引擎計算）\",\n")
_Z34_AS_NOTE_FN = (
    "\n\ndef ring1_data_incomplete_note(*, vix_known: bool, fut_known: bool) -> str | None:\n"
    "    \"\"\"三環第一環「資料不全、未套用天花板」說明句（本模組唯一出處）。\n"
    "\n"
    "    批 Z34（Z3-n8＋C8-n8，客戶 2026-10-10 Q-z13＝A）：原句寫在 `_derive_intrinsic_caps` 內；§八 火力分級卡\n"
    "    在「第一環只因資料未取得而沒過」時要沿用**同一句**（逐字），故原地抽出（字句、順序、標點一位未動），\n"
    "    兩處同呼本函式，不另抄一份字串。VIX 與外資期貨淨口皆已知 → None（不出句）。\n"
    "    \"\"\"\n"
    "    _unknown_bits: list[str] = []\n"
    "    if not vix_known:\n"
    "        _unknown_bits.append('VIX')\n"
    "    if not fut_known:\n"
    "        _unknown_bits.append('外資期貨淨口')\n"
    "    if not _unknown_bits:\n"
    "        return None\n"
    "    return (f'⚠️ 三環第一環資料不全（{\"、\".join(_unknown_bits)} 未取得），'\n"
    "            '未套用該天花板 — 數字可能偏樂觀')\n")

#: 修後 → 修前（每組恰好一處）。
Z34_REVERT_PAIRS = {
    'mid': (
        ("                apply_ring_gate, get_allocation, register_conflict,\n"
         "                ring1_data_incomplete_note,\n",
         "                apply_ring_gate, get_allocation, register_conflict,\n"),
        (_Z34_MID_BLOCK, "            if not _ring1_pass:\n"),
        ("                f'📌 本判定僅提供「火力分級」；實際持股請看 🎚️ 建議持股油門'\n"
         "                f'{\"\" if _ring1_undecided else \"（已納入本環天花板）\"}</div>'\n",
         "                f'📌 本判定僅提供「火力分級」；實際持股請看 🎚️ 建議持股油門（已納入本環天花板）</div>'\n"),
    ),
    'news': ((_Z34_NEWS_BLOCK, ''),),
    'msl': (
        (_Z34_MSL_EARLY, ''),
        ("        # 批 Z34（Q-z14）：收到 `calculate_system_state` 的 fail-safe（「系統異常」）時，摘要沿用 `_DEFAULT_STATE`\n"
         "        #   原句（與 execute_and_lock 失敗時寫下的 fail-safe 同形），不寫「曝險上限 0%（Python 規則引擎計算）」。\n"
         "        _failsafe = system_state.get(\"market_regime\") == _DEFAULT_STATE[\"market_regime\"]\n", ''),
        ("            \"analysis_summary\": (\n"
         "                _DEFAULT_STATE[\"analysis_summary\"] if _failsafe\n"
         "                else f\"曝險上限 {system_state.get('exposure_limit_pct', 0)}%（Python 規則引擎計算）\"),\n",
         _Z34_MSL_LOCK_OLD),
        ("      · 8 個**全缺**（且薩姆未觸發）→ 不計分，回既有 fail-safe `_DEFAULT_STATE` 的\n"
         "        regime／風險／曝險／Macro_Phase（「系統異常」）＋ `missing_inputs`（批 Z34，客戶 Q-z14）。\n", ''),
    ),
    'as': (
        ("    _fail_bits: list[str] = []\n"
         "\n"
         "    if _vix is not None and _vix >= 20:\n",
         "    _fail_bits: list[str] = []\n"
         "    _unknown_bits: list[str] = []\n"
         "\n"
         "    if _vix is None:\n"
         "        _unknown_bits.append('VIX')\n"
         "    elif _vix >= 20:\n"),
        ("    if _fut is not None and _fut <= _RING1_FUT_MIN_LOTS:\n",
         "    if _fut is None:\n"
         "        _unknown_bits.append('外資期貨淨口')\n"
         "    elif _fut <= _RING1_FUT_MIN_LOTS:\n"),
        ("    _note = ring1_data_incomplete_note(vix_known=_vix is not None, fut_known=_fut is not None)\n"
         "    if _note:\n"
         "        _conflicts.append(_note)\n",
         "    if _unknown_bits:\n"
         "        _conflicts.append(\n"
         "            f'⚠️ 三環第一環資料不全（{\"、\".join(_unknown_bits)} 未取得），'\n"
         "            '未套用該天花板 — 數字可能偏樂觀')\n"),
        (_Z34_AS_NOTE_FN, ''),
    ),
}
_Z34_FILES = {
    'mid': ('src/ui/tabs/macro/section_mid.py', MID),
    'news': ('src/ui/tabs/macro/section_news_ai.py', NEWS),
    'msl': ('src/services/macro_state_locker.py', MSL),
    'as': ('src/services/allocation_service.py', AS),
}
#: 基底 `76cac7cb` 原始檔 sha256（`git show 76cac7cb:<檔> | sha256sum` 實算；寫死以免測試依賴 git）。
_Z34_BASE_SHA = {
    'mid': '7a46045c5b02fec479ea52848285639cb091497eca3d74d504b0147c120e469a',
    'news': '3bccaf9ae90920e881e72bc95291af4f1bf066f746e481146958e6736f48d89c',
    'msl': '9ecd5dc55b76ce81daa3c7c4dcaf3f01a5f0cdcb024bddcd9c664a07d3874105',
    'as': 'b0890c5600fa6d00e190f977a14866c04d93b43009049ed6c8a534d23a0946c0',
}


def z34_revert(key: str, code: str) -> str:
    """把 Z34 的修改換回修前（每組恰好一處）。"""
    for old, new in Z34_REVERT_PAIRS[key]:
        assert code.count(old) == 1, f'{key} 替換點不唯一或已不存在：{old!r}'
        code = code.replace(old, new)
    return code


def _z34_source(key: str) -> str:
    import pathlib
    return (pathlib.Path(__file__).resolve().parents[1] / _Z34_FILES[key][0]).read_text(encoding='utf-8')


def _z34_load(key: str, code: str, tag: str):
    import importlib.util
    real = _Z34_FILES[key][1]
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(f'_z34_{key}_{tag}', loader=None))
    m.__file__ = real.__file__
    exec(compile(code, real.__file__, 'exec'), m.__dict__)
    return m


def z34_pre_module(key: str):
    """現行檔拿掉本批修改後的模組（＝基底 `76cac7cb` 該檔）。'news' 另把 `calculate_system_state` 換成修前 L3 的同名函式
    （§十一 送引擎的是 L3 本尊，本批 Q-z14 的行為在 L3）。供其他測試檔比對「本批以外的行為逐字不變」用。"""
    m = _z34_load(key, z34_revert(key, _z34_source(key)), 'pre')
    if key == 'news':
        m.calculate_system_state = z34_pre_module('msl').calculate_system_state
    return m


@pytest.mark.parametrize('key', sorted(Z34_REVERT_PAIRS))
def test_revert_is_exact_base_source(key):
    assert hashlib.sha256(z34_revert(key, _z34_source(key)).encode('utf-8')).hexdigest() == _Z34_BASE_SHA[key]


def test_pre_module_reproduces_base_behaviour(monkeypatch, tmp_path):
    """還原體實跑＝基底寫死 golden（拔掉修復即轉回修前輸出）。"""
    assert _digest(_news(monkeypatch, tmp_path, _MISSING, mod=z34_pre_module('news'))) == _NEWS_BASE[('missing', False)]
    vix, fut, gold = _MID_BASE['futnoli']
    assert _digest(_mid(monkeypatch, vix, fut, mod=z34_pre_module('mid'))) == gold
    assert z34_pre_module('msl').calculate_system_state({}) == _ENGINE_ALL_MISSING_BASE
