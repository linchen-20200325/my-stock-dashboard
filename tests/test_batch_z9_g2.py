"""批 Z9 第 2 組（2026-10-08 客戶核字）—— C8-n7 ＋ Z6-n7 釘子（基底 origin/main `fa4ad8a`）。

客戶裁示（總管轉述，逐字）：「C8-n7：採 A，字句照 HANDOFF 主案，不改字。Z6-n7：採 A，字句照 HANDOFF 主案，不改字。」

- C8-n7（L5 `src/ui/tabs/macro/section_cross_ai.py` ④ 美股動態）：`_cpi_ok = _ai_cpi is None or …` 把 CPI 缺值
  當正常 ⇒ VIX<20、CPI 缺時印「🟢 美股平穩，降息預期支撐…無系統性風險，有利個股選股表現」，SOX／NVDA 點火時印
  「🚀 美股強勢，科技領漲…可積極佈局科技」。改：VIX<20 且 CPI 缺（None／缺鍵／非有限）⇒
  標籤「VIX={VIX:.1f} CPI待取得」（灰 #484f58）／說明「CPI 數據未就緒，暫無法判斷降息預期」
  （比照同函式 ③ 卡缺 M2：「M1B=…% M2待取得」／「M2 數據未就緒，暫無法判斷 Gap」）。
  VIX≥20 各枝、CPI 有限值時：整段 §九 輸出逐字不變。
- Z6-n7（L5 `src/ui/tabs/macro/section_warroom.py` 作戰室 📐 行）：價（或年線）缺 ⇒ 三個位階片段不列，
  外資期貨 < −30,000 時現印「📐 年線位階參考：外資期貨避險」（標題與內容不符）→ 改印
  「📐 年線位階參考：未知｜外資期貨避險」。其餘情況整段作戰室輸出逐字不變。

golden：修前輸出於基底 `fa4ad8a` 以本檔同一支 `_s9`／`_wr`（`_FakeST`）實跑後寫死（⛔ 不讀 git、不由現行碼反推）：
- `_D_*`：整段輸出（每個 st.* 文字呼叫的種類＋內容）的 sha256；
- 修後與修前的差異以「還原替換」表達（把修後**唯一**預期改變的字串換回修前寫法後，sha256 必須等於修前
  golden）—— 等於斷言「除了這一處，整段輸出逐字與基底相同」。
- 本檔所有斷言皆為實跑行為斷言，不讀原始碼字面（無字面錨點）。
"""
from __future__ import annotations

import hashlib
import math
import random
import re
import types

import numpy as np
import pytest

import src.services.allocation_service as AS
import src.ui.tabs.macro.section_cross_ai as CR
import src.ui.tabs.macro.section_warroom as W
from shared.allocation_decision import build_allocation_decision
from tests.test_m2n2_no_zero_fill import _FakeST
from tests.test_batch_z25 import undo_z25_gray_card  # 批 Z25:外資方向未取得改灰,本檔沿用修前 golden
from tests.test_batch_z26 import undo_z26_gray_card  # 批 Z26:融資餘額／年線位置缺值改灰,本檔沿用修前 golden


def _digest(out) -> str:
    return hashlib.sha256('\x1e'.join(f'{k}\x1f{t}' for k, t in out).encode('utf-8')).hexdigest()


def _undo(out, new, old):
    """把輸出中唯一預期改變的字串（恰好出現一次）換回修前寫法。"""
    joined = '\x1e'.join(t for _k, t in out)
    assert joined.count(new) == 1, (new, joined.count(new))
    return [(k, t.replace(new, old)) for k, t in out]


# ══════════════════════════════════════════════════════════════════════════
# C8-n7：§九 ④ 美股動態
# ══════════════════════════════════════════════════════════════════════════
_BASE9 = {"ism_pmi": {"value": 52.0}, "tw_export": {"yoy": 5.0}}
_SOX = {"費城半導體 SOX": {"pct": 2.0}}
_NVDA = {"輝達 NVDA": {"pct": 3.0}}
_DROP = object()


def _s9(vix, cpi, tech=None, mp=None, ma20=17.5):
    """實跑 §九。`cpi` 為 `_DROP` 時 macro_info 不放 us_core_cpi 鍵。回 [(種類, 文字)]。"""
    info = dict(_BASE9)
    info['vix'] = {'current': vix, 'ma20': ma20}
    if cpi is not _DROP:
        info['us_core_cpi'] = {'yoy': cpi}
    fake = _FakeST({'macro_info': info, 'm1b_m2_info': None, 'bias_info': None})
    mp.setattr(CR, 'st', fake)
    mp.setattr(AS, 'get_allocation', lambda *a, **k: types.SimpleNamespace(is_loaded=False))
    CR.render_section_cross_ai(tech or {}, {})
    return list(fake.out)


def _card9(title, color, label, desc):
    """`_ai_card` 的 HTML 樣板（`fa4ad8a` 原樣）。"""
    return (f'<div style="background:#0d1117;border:1px solid {color}44;border-radius:8px;'
            f'padding:12px;min-height:110px;">'
            f'<div style="font-size:10px;color:#484f58;margin-bottom:4px;">{title}</div>'
            f'<div style="font-size:13px;font-weight:700;color:{color};line-height:1.3;">{label}</div>'
            f'<div style="font-size:11px;color:#8b949e;margin-top:6px;line-height:1.5;">{desc}</div>'
            f'</div>')


def _new4(vt):
    """修後：VIX<20、CPI 缺。"""
    return _card9('④ 美股動態', '#484f58', f'VIX={vt} CPI待取得', 'CPI 數據未就緒，暫無法判斷降息預期')


def _green4(vt, cpi_s=''):
    return _card9('④ 美股動態', '#22c55e', '🟢 美股平穩，降息預期支撐',
                  f'VIX={vt} MA20=17.5（安全）{cpi_s} — 無系統性風險，有利個股選股表現')


def _rocket4(vt, mid):
    return _card9('④ 美股動態', '#ef4444', '🚀 美股強勢，科技領漲',
                  f'VIX={vt}（恐慌低）{mid} — 台股跟漲機率高，可積極佈局科技')


#: (id, vix, cpi, tech, 修後 ④ 卡 VIX 字樣, 修前 ④ 卡（fa4ad8a 實跑寫死）, 修前整段 digest)
_C8_MISSING = [pytest.param(v, c, t, vt, pre4, d, id=i) for i, v, c, t, vt, pre4, d in (
    ('cpi-key-missing', 18.0, _DROP, None, '18.0', _green4('18.0'),
     '885d73d7421995253360d98b417ebf1d017a0b00c3c6a8ab1135635ffd35d07b'),
    ('cpi-None', 18.0, None, None, '18.0', _green4('18.0'),
     '885d73d7421995253360d98b417ebf1d017a0b00c3c6a8ab1135635ffd35d07b'),
    ('cpi-nan', 18.0, math.nan, None, '18.0', _green4('18.0'),
     '885d73d7421995253360d98b417ebf1d017a0b00c3c6a8ab1135635ffd35d07b'),
    ('cpi-+inf', 18.0, math.inf, None, '18.0',
     _card9('④ 美股動態', '#eab308', '⚠️ 美股承壓，Fed鷹派升溫',
            'VIX=18.0 CPI=inf%超標 — 高利率環境延續，外資提款風險升高，注意匯率走勢'),
     'fb46fdb49a31f6dafdabd1f496f1c3e392b54213ecee716a56020541f85528e1'),
    ('cpi--inf', 18.0, -math.inf, None, '18.0', _green4('18.0', ' CPI=-inf%'),
     'bbfb6c51abace043bbe2625897b16b7ba048274067c65fe57059ee0731bbed2b'),
    ('sox-fire-cpi-None', 12.0, None, _SOX, '12.0', _rocket4('12.0', ' SOX=+2.0%（半導體點火）'),
     'f8229d7fcd75b6f0b8409cb92eea11ab1c4e26f96670a0285ed57ac10a832ee5'),
    ('nvda-fire-cpi-nan', 18.0, math.nan, _NVDA, '18.0', _rocket4('18.0', '（半導體點火）'),
     '8dd5d7e3e7f5db43f6503855ad3d6e79eadc58ee09759f4d23383ea79e5cc31b'),
    ('vix-19.99-cpi-None', 19.99, None, None, '20.0', _green4('20.0'),
     '908e6be12f720ac6a431d7b994af32884923d185164199666e5dd2cbf305f818'),
)]

#: CPI 有限值，或 VIX≥20：修後整段 §九 輸出＝修前（fa4ad8a 實跑寫死的 digest）
_C8_SAME = [pytest.param(v, c, t, d, id=i) for i, v, c, t, d in (
    ('vix20-cpi-None', 20.0, None, None, 'cdba4ea68a262dd87d1668c05be8e401d40357c9754c73597855416264ac04d5'),
    ('vix25-cpi-None', 25.0, None, None, '90ab8f62d7f6ed7569371949028c023f72efa7def5eadce391a5818c8b89be08'),
    ('vix35-cpi-+inf', 35.0, math.inf, None, 'ba291808ac834825aebd5528eefdac02f035e03bc3ecf271273ed55fa64feda9'),
    ('vix18-cpi2.5', 18.0, 2.5, None, 'e9a850280e1eee010f8ec5ca6f7615a267d56a7fd5e02f9db0880ed306cb793e'),
    ('vix18-cpi3.5', 18.0, 3.5, None, '8ded75b6b885ee4e701500ac7738dffc7109cc3475a7a7b0eeb863b7492502b8'),
    ('vix18-cpi4.5', 18.0, 4.5, None, 'fa8b23121564c389dadd42d70e9f0edd855befe0a294732af9da86b3acf5aebf'),
    ('vix18-cpi2.5-sox', 18.0, 2.5, _SOX, 'ac0d11cd9188b498c9613080996bff0f25adcc5d7a5291aff6baff9360b3db09'),
    ('vix18-cpi0.0', 18.0, 0.0, None, '36fe65d64f841d2e59498832a4e2ae95152a770b611610134b093e53fb7cf10b'),
    ('vix25-cpi2.5', 25.0, 2.5, None, '90ab8f62d7f6ed7569371949028c023f72efa7def5eadce391a5818c8b89be08'),
    ('vix35-cpi4.5-sox', 35.0, 4.5, _SOX, 'ba291808ac834825aebd5528eefdac02f035e03bc3ecf271273ed55fa64feda9'),
)]


class TestC8n7CpiMissing:
    @pytest.mark.parametrize('vix,cpi,tech,vt,pre4,pre_d', _C8_MISSING)
    def test_new_card_literal(self, vix, cpi, tech, vt, pre4, pre_d, monkeypatch):
        md = [t for k, t in _s9(vix, cpi, tech, monkeypatch) if k == 'markdown']
        assert _new4(vt) in md
        joined = '\n'.join(md)
        assert 'CPI待取得' in joined and 'CPI 數據未就緒，暫無法判斷降息預期' in joined
        # 舊的假結論一個字都不能留
        for bad in ('降息預期支撐', '積極佈局', '無系統性風險', '美股平穩', '美股強勢', '鷹派'):
            assert bad not in joined, bad

    @pytest.mark.parametrize('vix,cpi,tech,vt,pre4,pre_d', _C8_MISSING)
    def test_only_card4_differs_from_base(self, vix, cpi, tech, vt, pre4, pre_d, monkeypatch):
        out = _s9(vix, cpi, tech, monkeypatch)
        assert _digest(out) != pre_d                               # 真的有改
        assert _digest(_undo(out, _new4(vt), pre4)) == pre_d       # 除了 ④ 卡，整段逐字＝基底

    def test_label_text_carries_the_meaning_not_only_color(self, monkeypatch):
        """顏色不是唯一資訊載體：標籤字句本身就寫「待取得」，說明句寫「未就緒」。"""
        md = '\n'.join(t for k, t in _s9(18.0, None, None, monkeypatch) if k == 'markdown')
        lbl = re.search(r'④ 美股動態</div><div[^>]*>([^<]*)</div><div[^>]*>([^<]*)</div>', md)
        assert lbl.groups() == ('VIX=18.0 CPI待取得', 'CPI 數據未就緒，暫無法判斷降息預期')

    def test_ma20_missing_same_new_card(self, monkeypatch):
        md = [t for k, t in _s9(15.0, None, None, monkeypatch, ma20=None) if k == 'markdown']
        assert _new4('15.0') in md

    def test_random_vix_below_20_cpi_missing(self, monkeypatch):
        rng = random.Random(20261008)
        for _ in range(60):
            v = rng.uniform(0.01, 19.94)
            cpi = rng.choice((None, math.nan, math.inf, -math.inf, _DROP, np.float64('nan')))
            tech = rng.choice((None, _SOX, _NVDA))
            md = '\n'.join(t for k, t in _s9(v, cpi, tech, monkeypatch) if k == 'markdown')
            assert _new4(f'{v:.1f}') in md, (v, cpi)
            assert '降息預期支撐' not in md and '積極佈局' not in md, (v, cpi)


class TestC8n7Unchanged:
    @pytest.mark.parametrize('vix,cpi,tech,pre_d', _C8_SAME)
    def test_golden(self, vix, cpi, tech, pre_d, monkeypatch):
        out = _s9(vix, cpi, tech, monkeypatch)
        assert _digest(out) == pre_d
        assert 'CPI待取得' not in '\n'.join(t for _k, t in out)

    def test_finite_cpi_card_literals(self, monkeypatch):
        md = [t for k, t in _s9(18.0, 2.5, None, monkeypatch) if k == 'markdown']
        assert _green4('18.0', ' CPI=2.5%') in md
        md = [t for k, t in _s9(18.0, 2.5, _SOX, monkeypatch) if k == 'markdown']
        assert _rocket4('18.0', ' SOX=+2.0%（半導體點火） CPI=2.5%') in md

    def test_vix_missing_card_unchanged(self, monkeypatch):
        """VIX 沒值（CPI 也沒值）：既有「待取得／VIX / CPI 數據載入中」一字不變。"""
        md = [t for k, t in _s9(None, None, None, monkeypatch) if k == 'markdown']
        assert _card9('④ 美股動態', '#484f58', '待取得', 'VIX / CPI 數據載入中') in md


# ══════════════════════════════════════════════════════════════════════════
# Z6-n7：作戰室 📐 年線位階參考
# ══════════════════════════════════════════════════════════════════════════
_UNLOADED = build_allocation_decision(None)
_HINT_DIV = '<div style="font-size:11px;color:#8b949e;margin-top:4px;">📐 年線位階參考：{}</div>'
_CARD = ('<div style="background:#0a2818;border-left:5px solid #22c55e;border-radius:0 10px 10px 0;'
         'padding:14px 18px;margin:8px 0;"><div style="font-size:11px;color:#484f58;margin-bottom:4px;">'
         '📌 今日唯一行動建議</div><div style="font-size:17px;font-weight:900;color:#22c55e;">'
         '🟢 趨勢偏多 — 可逢回布局核心部位</div>{}</div>')
_NEW_HINT = '未知｜外資期貨避險'
_PRE_HINT = '外資期貨避險'


def _wr(bias, fut, mp):
    mp.setattr(AS, 'get_allocation', lambda *a, **k: _UNLOADED)
    state = {'bias_info': bias, 'cl_data': {'margin': 2000.0}, 'warroom_summary': {'futures_net': fut}}
    fake = _FakeST(state)
    mp.setattr(W, 'st', fake)
    W.render_section_warroom('bull', True, False)
    # 批 Z25（Z16-n1）：「外資方向」未取得那格修後改灰框 ⬜ ⇒ 換回修前紅框再比修前 golden（該格由 test_batch_z25 守）。
    # 批 Z26（Z25-(d)）：「融資餘額」「年線位置」缺值那兩格修後改灰框 ⬜ ⇒ 同樣換回修前綠框（該兩格由 test_batch_z26 守）。
    return undo_z26_gray_card(undo_z25_gray_card(list(fake.out)))


def _hint(out) -> list:
    return re.findall(r'📐 年線位階參考：([^<]*)', '\n'.join(t for _k, t in out))


_D_PXMISS_HEDGE = '1439a4c7e1acb148e2721b7dd25a28c45735a684f819a98d061d92108bfb5311'   # 修前：只剩避險
_D_NO_HINT = 'dff46aeb62fd42156c4f40181be5c8fecc15a2a1603dc9ee9e4a060e81dd8430'        # 整行「📐」不出

#: 價（或年線）缺＋外資期貨 < −30,000（修前 fa4ad8a 皆為 `_D_PXMISS_HEDGE`）
_Z6_CHANGED = [pytest.param(b, f, id=i) for i, b, f in (
    ('price-missing', {'ma240': 16000.0}, -40000.0),
    ('price-None', {'price': None, 'ma240': 16000.0}, -40000.0),
    ('price-nan', {'price': math.nan, 'ma240': 16000.0}, -40000.0),
    ('price-zero', {'price': 0.0, 'ma240': 16000.0}, -40000.0),
    ('ma-missing', {'price': 16000.0}, -40000.0),
    ('both-missing', {}, -40000.0),
    ('bias_info-None', None, -40000.0),
    ('price-missing-just-below', {'ma240': 16000.0}, math.nextafter(-30000.0, -math.inf)),
    # 批 Z10 續作（Q-r10b，客戶 2026-10-09「等於門檻歸防禦」）：剛好 −30000 改歸避險 ⇒ 自 _Z6_SAME 移入本表
    ('price-missing-m30000', {'ma240': 16000.0}, -30000.0),
)]

#: 修後整段作戰室輸出＝修前（fa4ad8a 實跑寫死）
_Z6_SAME = [pytest.param(b, f, d, h, id=i) for i, b, f, d, h in (
    # 批 Z10 續作（Q-r10b）：'pxmiss-m30000'（−30000）已移 _Z6_CHANGED；−29999 仍不避險、整行不出
    ('pxmiss-m29999', {'ma240': 16000.0}, -29999.0, _D_NO_HINT, []),
    ('pxmiss-nofut', {'ma240': 16000.0}, None, _D_NO_HINT, []),
    ('bull-hedge', {'price': 20000.0, 'ma240': 19000.0}, -40000.0,
     '419b4c56151b6dda6fce1a1066b97c99268e0a038bf32756596600b04f71b124', ['年線乖離 +5.3%｜外資期貨避險']),
    ('bull-nofut', {'price': 20000.0, 'ma240': 19000.0}, None,
     '353d20727c06e794815cf60e3fd0fdcbd9ef26690b62cb99c01a5cdcb4539367', ['年線乖離 +5.3%']),
    ('below-hedge', {'price': 15000.0, 'ma240': 16000.0}, -40000.0,
     '40620544079de1adce162b9244d5db39aa81d433c4e739b2c5cd731d2ac28b68', ['年線乖離 -6.2%｜股價在年線下｜外資期貨避險']),
)]


class TestZ6n7PriceMissingHedging:
    @pytest.mark.parametrize('bias,fut', _Z6_CHANGED)
    def test_hint_line(self, bias, fut, monkeypatch):
        out = _wr(bias, fut, monkeypatch)
        assert _hint(out) == [_NEW_HINT]
        assert out[1] == ('markdown', _CARD.format(_HINT_DIV.format(_NEW_HINT)))

    @pytest.mark.parametrize('bias,fut', _Z6_CHANGED)
    def test_only_hint_differs_from_base(self, bias, fut, monkeypatch):
        out = _wr(bias, fut, monkeypatch)
        assert _digest(out) != _D_PXMISS_HEDGE
        assert _digest(_undo(out, _HINT_DIV.format(_NEW_HINT), _HINT_DIV.format(_PRE_HINT))) == _D_PXMISS_HEDGE


class TestZ6n7Unchanged:
    @pytest.mark.parametrize('bias,fut,pre_d,hint', _Z6_SAME)
    def test_golden(self, bias, fut, pre_d, hint, monkeypatch):
        out = _wr(bias, fut, monkeypatch)
        assert _digest(out) == pre_d and _hint(out) == hint
        assert '未知｜' not in '\n'.join(t for _k, t in out)

    def test_random_priced_never_says_unknown(self, monkeypatch):
        """價、年線皆為有限正數：不論期貨值，📐 行不出現「未知」。"""
        rng = random.Random(10008)
        for _ in range(60):
            ma = rng.uniform(1000.0, 30000.0)
            px = ma * (1 + rng.uniform(-0.3, 0.3))
            fut = rng.choice((None, rng.uniform(-60000, 60000), -40000.0))
            h = _hint(_wr({'price': px, 'ma240': ma}, fut, monkeypatch))
            assert len(h) == 1 and not h[0].startswith('未知'), (px, ma, fut, h)
