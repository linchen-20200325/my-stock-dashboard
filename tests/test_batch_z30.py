"""批 Z30 —— 客戶 2026-10-09 核准（基底 origin/main `4591c5aa`，含批 Z29 #817）。

- Q-z8（L5 `section_warroom.py` 作戰室「外資方向」卡）：外資淨額真實觀測值**剛好 0**（含 -0.0／int 0／np 0）時，
  文字維持批 Z29「0億（持平）」，第 3 欄判定由 False（紅框 ⚠️）改 None（灰框 ⬜，無法判定）。
  **僅 = 0**；其餘正負值判定式 `(_wr_fnet or 0) > 0` 與門檻不變（含四捨五入後也印「0億」的 ±0.4、±1e-9）。
- Z29-n1（L1 `leading_indicators.render_leading_table`）：「成交量」欄由 L1 以 `f"{x:.1f}億"` **字串**寫入
  （缺值寫「-」），表格直接 `row.get("成交量")` 照印 ⇒ 非有限值（字串「inf億」「-inf億」「nan億」「nan」、
  float／np ±inf／NaN、Decimal 非有限）與 None／pd.NA 修前印「inf億」「nan」「None」「<NA>」⇒ 一律改走該欄
  既有缺值顯示「-」（同一個淡藍 span，與 L1 自己寫入的「-」逐字相同；該欄本無條件上色）。有限值輸出不變。
- Z29-n2（L5 `section_chips.py` §三 先行指標）：修前 `df_li_show` 所有非日期欄 `.ffill()` ⇒ 某日缺值被印成
  前一日的值（含末列「今日」），進階警示訊號 1～4、v5 卡、「最新一筆原始值」、CSV 都吃到冒充值 ⇒ 移除該填補。
  連帶：訊號 5 末列（今日）成交量取不到（NaN 或 L1 的「-」）時，修前（ffill 或 dropna）都拿前一天當今天
  ⇒ 整個訊號 5 不列（同批 Z29「⛔ 不得剔掉 inf 後拿前一天當今天」）；中間列缺值照舊剔除。
- Z30（續，總管裁定）：`read_v4_macro_veto()` 原另做 `.ffill().iloc[-1]` ⇒ 今日外資期貨缺、昨日 −40,000 時
  v4 引擎風險燈仍判「🔴 紅燈…外資期貨=-40,000口」、§八 跨區揭露框據以列出 ⇒ 改讀原始末列，缺值走引擎既有
  「⬜ 無法判定…外資期貨 未取得」與 §八 既有 caption（批 Z27 Q-z2 核准字句）；不新增字句、不改門檻與判定式。

golden：有限值／無缺值的修前輸出於基底 `4591c5aa` 以本檔同一支 harness 實跑後寫死 sha256（⛔ 不由現行碼反推）。
本檔所有斷言皆為實跑行為斷言，不讀原始碼字面。
"""
from __future__ import annotations

import base64
import functools
import hashlib
import importlib.util
import io
import math
import re
import types
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

import src.services.allocation_service as AS
import src.ui.tabs.macro.section_chips as SC
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED
from src.config.config import VETO_V4_ENGINE_NAME
from src.data.macro.leading_indicators import render_leading_table
from tests.test_batch_z29 import _GRAY, _ZEROS, _card, _joined, _val, _wr
from tests.test_m2n2_no_zero_fill import _FakeST

_INFNAN = re.compile(r'(?<![A-Za-z])(inf|nan|infinity)(?![A-Za-z])', re.I)


def _digest(out) -> str:
    return hashlib.sha256('\x1e'.join(f'{k}\x1f{t}' for k, t in out).encode('utf-8')).hexdigest()


def _h(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def _strip(s: str) -> str:
    return re.sub(r'<[^>]+>', '', s)


# ══════════════════════════════════════════════════════════════════════════
# 1. Q-z8：外資淨額剛好 0 ⇒ 第 3 欄 None（灰框 ⬜）
# ══════════════════════════════════════════════════════════════════════════
#: 基底 `4591c5aa`（批 Z29 後）實跑：外資淨額剛好 0（印「0億（持平）」、判定 False ⇒ 紅 ⚠️）的整段 sha256。
_Z29_ZERO_GOLD = 'e3954f3a44573d5a569ce5611b4950a611031d7614f52745d7876c9588e5d118'


def _back_to_red(t: str) -> str:
    """把「外資方向」卡的灰框／灰字／⬜ 換回修前的紅框／紅字／⚠️（只動該卡三處）。"""
    return (t.replace(f'border-top:3px solid {_GRAY};', f'border-top:3px solid {TRAFFIC_RED};')
             .replace(f'font-weight:800;color:{_GRAY};', f'font-weight:800;color:{TRAFFIC_RED};')
             .replace('⬜ 外資方向</div>', '⚠️ 外資方向</div>'))


class TestQz8ZeroGray:
    @pytest.mark.parametrize('net', _ZEROS)
    def test_gray_cannot_judge(self, net, monkeypatch):
        card = _card(_wr(monkeypatch, net=net), '外資方向')
        assert _val('0億（持平）') in card
        assert f'border-top:3px solid {_GRAY};' in card and '⬜ 外資方向</div>' in card
        assert TRAFFIC_RED not in card and TRAFFIC_GREEN not in card
        assert '⚠️' not in card and '✅' not in card

    @pytest.mark.parametrize('net', _ZEROS)
    def test_only_judgement_changed(self, net, monkeypatch):
        """修前（基底實跑）：同字「0億（持平）」、判定 False ⇒ 紅 ⚠️。把該卡灰框／⬜ 換回紅框／⚠️ 後整段等於基底。"""
        out = _wr(monkeypatch, net=net)
        undone = [(k, _back_to_red(t)) if '外資方向</div>' in t else (k, t) for k, t in out]
        assert sum(a != b for a, b in zip(out, undone)) == 1
        assert _digest(undone) == _Z29_ZERO_GOLD
        assert _digest(out) != _Z29_ZERO_GOLD

    @pytest.mark.parametrize('net', _ZEROS)
    def test_no_foreign_warning(self, net, monkeypatch):
        assert '外資賣超' not in _joined(_wr(monkeypatch, net=net))


#: 基底 `4591c5aa` 實跑（非 0：極小正負、四捨五入也印「0億」的 ±0.4、一般買賣超、達警示、np）。
_NONZERO_BASE = {
    'tiny_pos': (1e-9, 'c48c74b9149a6a4fc9c6149240ca6c6955dc89cfe11883d6cb211ea0f149457e'),
    'one': (1.0, 'afca099b3e0789d9460a0c5c2c23cd84a8605258fc8974424bfb89333203e217'),
    'neg_one': (-1.0, 'd5432b8eae967210f4104181f28460010d8249db3c0b463ad435a3d9f1a01b63'),
    'neg20_edge': (-20.0, '52c336ba5e27de100221ef40608a9888d077f18116cdef41441e4ae9ee990682'),
    'tiny_neg': (-1e-9, '3b2f35af1f43bc2a52f3d4ec96f11a218643941f6cd6ac6993768a107d8e3b0e'),
    'r0_pos': (0.4, 'c48c74b9149a6a4fc9c6149240ca6c6955dc89cfe11883d6cb211ea0f149457e'),
    'r0_neg': (-0.4, '3b2f35af1f43bc2a52f3d4ec96f11a218643941f6cd6ac6993768a107d8e3b0e'),
    'buy': (25.4, '5683abec9fc6c88f5337c1781c6137dd0cfd8e8eff68bb7c80856e6a161e174a'),
    'sell_warn': (-30.0, '66599b147157f1ad70b16b4206bc22c36f1ef7c3c735e0a2ffd31a5ebaa503b2'),
    'np_neg': (np.float64(-7.6), '9a13345ca27efc44b80529804b8ba9c365e59fe7a34cbc7b251415fbb54c964b'),
}


class TestQz8NonZeroUnchanged:
    @pytest.mark.parametrize('case', sorted(_NONZERO_BASE))
    def test_golden(self, case, monkeypatch):
        net, gold = _NONZERO_BASE[case]
        assert _digest(_wr(monkeypatch, net=net)) == gold

    @pytest.mark.parametrize('net, text, color', [
        (1e-9, '買超 0億', TRAFFIC_GREEN), (0.4, '買超 0億', TRAFFIC_GREEN), (1.0, '買超 1億', TRAFFIC_GREEN),
        (25.4, '買超 25億', TRAFFIC_GREEN),
        (-1e-9, '賣超 0億', TRAFFIC_RED), (-0.4, '賣超 0億', TRAFFIC_RED), (-1.0, '賣超 1億', TRAFFIC_RED),
        (-20.0, '賣超 20億', TRAFFIC_RED), (-30.0, '賣超 30億', TRAFFIC_RED)])
    def test_nonzero_text_and_judgement(self, net, text, color, monkeypatch):
        """只有剛好 0 改灰；非 0（含 ±0.4、±1e-9 這種也印「0億」的）文字與判定照舊（正 ⇒ 綠 ✅、負 ⇒ 紅 ⚠️）。"""
        card = _card(_wr(monkeypatch, net=net), '外資方向')
        assert _val(text) in card and _val('0億（持平）') not in card
        assert f'border-top:3px solid {color};' in card
        assert ('✅ 外資方向</div>' if color == TRAFFIC_GREEN else '⚠️ 外資方向</div>') in card
        assert f'border-top:3px solid {_GRAY};' not in card

    @pytest.mark.parametrize('net, warned', [(-20.0, False), (-20.5, True), (-30.0, True), (0.0, False)])
    def test_sell_warning_threshold_unchanged(self, net, warned, monkeypatch):
        """風險警示句門檻（< -20）不變；0 不出警示。"""
        assert ('外資賣超' in _joined(_wr(monkeypatch, net=net))) is warned


# ══════════════════════════════════════════════════════════════════════════
# 2. Z29-n1：先行指標表「成交量」欄非有限 ⇒ 「-」
# ══════════════════════════════════════════════════════════════════════════
_VOL_DASH = '<td><span style="color:#9CDCFE;">-</span></td>'


def _vol_df(*vols) -> pd.DataFrame:
    n = len(vols)
    return pd.DataFrame({
        '日期': [f'10月{i + 1}日' for i in range(n)],
        '成交量': pd.Series(list(vols), dtype=object),
        '外資': [12.3] * n, '投信': [-4.5] * n, '自營': [0.0] * n,
        '外資大小': [-12000.0] * n, '融資餘額': [2900.0] * n, '融券餘額': [50.0] * n,
        '前五大留倉': [-3000.0] * n, '前十大留倉': [-5000.0] * n, '選PCR': [110.0] * n,
        '外(選)': [-200.0] * n, '未平倉口數': [-30000.0] * n, '韭菜指數': [12.5] * n,
    })


_NF_VOL = [
    pytest.param('inf億', id='str-inf'),
    pytest.param('-inf億', id='str-ninf'),
    pytest.param('nan億', id='str-nan'),
    pytest.param('nan', id='str-nan-bare'),
    pytest.param('Infinity', id='str-Infinity'),
    pytest.param(' inf億 ', id='str-inf-spaced'),
    pytest.param('1e400億', id='str-overflow'),
    pytest.param(math.inf, id='float-pinf'),
    pytest.param(-math.inf, id='float-ninf'),
    pytest.param(math.nan, id='float-nan'),
    pytest.param(np.float64(np.inf), id='np-pinf'),
    pytest.param(np.float64(np.nan), id='np-nan'),
    pytest.param(np.float32(-np.inf), id='f32-ninf'),
    pytest.param(Decimal('NaN'), id='dec-nan'),
    pytest.param(None, id='None'),
    pytest.param(pd.NA, id='pd-NA'),
]


class TestVolumeNonFinite:
    @pytest.mark.parametrize('vol', _NF_VOL)
    def test_dash(self, vol):
        html = render_leading_table(_vol_df('3000.0億', vol))
        last = html.split('<tr>')[-1]
        assert _VOL_DASH in last
        assert not _INFNAN.search(_strip(html)), _strip(html)
        assert 'None' not in html and '<NA>' not in html

    @pytest.mark.parametrize('vol', _NF_VOL)
    def test_same_as_l1_missing(self, vol):
        """與 L1 自己寫入的缺值「-」逐字相同（同欄既有缺值顯示）。"""
        assert render_leading_table(_vol_df('3000.0億', vol)) == render_leading_table(_vol_df('3000.0億', '-'))

    def test_column_missing(self):
        """整欄缺（df 無「成交量」欄）⇒ 照舊走 `row.get` 預設「-」，不崩、不填 0。"""
        html = render_leading_table(_vol_df('3000.0億', '2000.0億').drop(columns=['成交量']))
        assert html.count(_VOL_DASH) == 2 and '>0<' not in html

    def test_other_rows_untouched(self):
        html = render_leading_table(_vol_df('3000.0億', 'inf億', '2500.5億'))
        assert '<td><span style="color:#9CDCFE;">3000.0億</span></td>' in html
        assert '<td><span style="color:#9CDCFE;">2500.5億</span></td>' in html
        assert html.count(_VOL_DASH) == 1

    #: 修前基底 `4591c5aa` 實跑：該格照印原值（「inf億」「nan」「None」「<NA>」）的整張表 sha256。
    _PRE = {
        'inf億': ('inf億', 'ea9aa39c05eccec0ce7d0448edaeec9ee9da2f1e2957297a0d0dfef947f3f82f'),
        'nan億': ('nan億', '158320e1809b14c1efaad5d6d66386fcd9d3dfeebeae97e1fb7712fe13e2a845'),
        'float-inf': (math.inf, '039e9fea45249d9fca9d0e605e760541585765a47d3030fb8a39b0712d0534f2'),
        'None': (None, '9c8731757ed115f21de1da9d169790e2192a9a505983107b1e9a90cd8d2a8ebb'),
        'pd-NA': (pd.NA, '0404f1f60a91fed570a5d8c1533851d002d084c551416abf1e2e092b58fb513a'),
    }

    @pytest.mark.parametrize('case', sorted(_PRE))
    def test_only_that_cell_changed(self, case):
        """把「-」換回該值的原樣字串後，整張表等於修前基底實跑（只差這一格）。"""
        vol, gold = self._PRE[case]
        html = render_leading_table(_vol_df('3000.0億', vol))
        head, sep, tail = html.rpartition(_VOL_DASH)
        assert sep
        undone = head + f'<td><span style="color:#9CDCFE;">{vol}</span></td>' + tail
        assert _h(undone) == gold
        assert _h(html) != gold


#: 修前基底 `4591c5aa` 實跑：有限值（L1 字串、「-」、0、float／np、科學記號字串）整張表 sha256。
_VOL_FINITE_BASE = {
    'strs': (('3000.0億', '1234.5億', '-', '0.0億'), '3ca8364ade566bb681566982914d45793374e291ab42cfc1a8645792aec3652b'),
    'floats': ((3000.0, np.float64(2999.9), 0.0, -1.5), 'bcdf6b4cb0246a722d39a1966ce0386cbf2847cfe26cb84a3441128f3c8d183d'),
    'sci': (('1e3億', '3,000.0億'), 'd250739f4ba45bc5ee2ecf68d1d357f859e680a547ab3017faba26df248f26a8'),
}


class TestVolumeFiniteUnchanged:
    @pytest.mark.parametrize('case', sorted(_VOL_FINITE_BASE))
    def test_golden(self, case):
        vols, gold = _VOL_FINITE_BASE[case]
        assert _h(render_leading_table(_vol_df(*vols))) == gold

    def test_text(self):
        html = render_leading_table(_vol_df('3000.0億', 3000.0))
        assert '<td><span style="color:#9CDCFE;">3000.0億</span></td>' in html
        assert '<td><span style="color:#9CDCFE;">3000.0</span></td>' in html


# ══════════════════════════════════════════════════════════════════════════
# 3. Z29-n2：§三 先行指標不再以前日值冒充當日
# ══════════════════════════════════════════════════════════════════════════
class _FakeSTCode(_FakeST):
    """同 `_FakeST`，另記錄 `st.code`（「最新一筆原始值」）。"""

    def code(self, body='', *a, **k):
        self.out.append(('code', str(body)))


def _chips(li, mp):
    """實跑 §三（法人／融資空、VIX 15、先行指標 = li）。回 [(種類, 文字)]；拋例外照拋。"""
    fake = _FakeSTCode({'macro_info': {'vix': {'current': 15.0, 'ma20': 15.0}}, 'li_latest': li})
    mp.setattr(SC, 'st', fake)
    mp.setattr(AS, 'get_allocation', lambda *a, **k: types.SimpleNamespace(
        is_loaded=False, range_text='', capped=False, cap_text='', final_hi=None))
    mp.setattr(AS, 'get_allocation_sleeves', lambda *a, **k: None)
    SC.render_section_chips({}, None, {})
    return list(fake.out)


#: 一個「昨天」會觸發訊號 1～4、v5 卡紅色防禦的交易日（全部有限值）。
_DAY = {'成交量': '3000.0億', '外資': 80.0, '投信': 10.0, '自營': -3.0, '外資大小': -40000.0,
        '融資餘額': 2900.0, '融券餘額': 50.0, '前五大留倉': -12000.0, '前十大留倉': -15000.0,
        '選PCR': 70.0, '外(選)': -5000.0, '未平倉口數': -30000.0, '韭菜指數': 40.0}
_NUM = [c for c in _DAY if c != '成交量']


def _li(*rows) -> pd.DataFrame:
    recs = []
    for i, r in enumerate(rows):
        d = {'日期': f'10月{i + 1}日', **r, '_date': f'202610{i + 1:02d}',
             'source': 'TEST:leading', 'fetched_at': '2026-10-09T00:00:00+00:00'}
        recs.append(d)
    df = pd.DataFrame(recs)
    df['成交量'] = df['成交量'].astype(object)
    return df


def _nan_row(cols=None, vol=math.nan):
    r = dict(_DAY)
    for c in (cols or _NUM):
        r[c] = math.nan
    r['成交量'] = vol
    return r


def _tbody_row(out, date: str) -> str:
    tbl = [t for _k, t in out if 'li-tbl' in t]
    assert len(tbl) == 1
    rows = [r for r in tbl[0].split('<tr>') if f'>{date}</td>' in r]
    assert len(rows) == 1
    return rows[0]


def _warn_txt(out) -> str:
    return _strip('\x1e'.join(t for _k, t in out if '⚡ 進階警示' in t))


def _v5_card(out) -> str:
    cards = [t for _k, t in out if '💰 v5 動態配置' in t]
    assert len(cards) == 1
    return cards[0]


def _csv(out) -> pd.DataFrame:
    links = [t for _k, t in out if 'download="先行指標.csv"' in t]
    assert len(links) == 1
    b64 = re.search(r'base64,([^"]+)"', links[0]).group(1)
    return pd.read_csv(io.StringIO(base64.b64decode(b64).decode('utf-8-sig')))


def _raw_line(out) -> str:
    codes = [t for k, t in out if k == 'code']
    assert len(codes) == 1
    return codes[0]


_TODAY_NAN = lambda: _li(_DAY, _DAY, _DAY, _nan_row())  # noqa: E731


# ── 還原體：本批 section_chips 兩處改動逐字換回基底 `4591c5aa` 寫法（供本檔「修前」自證與既有 golden 測試沿用）──
#: (修後逐字, 修前逐字)。⚠️ 正式碼字面一改，這裡會因找不到替換點而失敗 —— 那是字面錨點。
Z30_CHIPS_REVERT_PAIRS = (
    ("        # 批 Z30（Z29-n2，客戶原則「今天缺值不得以昨天冒充」）：原對全部非日期欄 `.ffill()`，缺值被印成前一日的值\n"
     "        #   （含末列「今日」）並據以下結論 ⇒ 移除；缺值走各消費點既有路徑（表格「-」、警示不列、v5「未取得」、CSV 照實）。\n",
     "        # 向前填補 NaN（各欄位用最後一次有效數值補齊，避免 API 部分失敗造成空格）\n"
     "        _li_num_cols = [c for c in df_li_show.columns if c != '日期']\n"
     "        df_li_show = df_li_show.copy()\n"
     "        df_li_show[_li_num_cols] = df_li_show[_li_num_cols].ffill()\n"),
    ("                errors='coerce')\n"
     "                if '成交量' in df_li_show.columns else pd.Series(dtype=float))\n"
     "            # 批 Z30（Z29-n2）：末列（今日）取不到 ⇒ 整個訊號 5 不列，⛔ 不得 dropna 後拿前一天當今天；中間列缺值照舊剔除。\n"
     "            _vols = _vols.dropna().tolist() if len(_vols) and pd.notna(_vols.iloc[-1]) else []\n",
     "                errors='coerce').dropna().tolist()\n"
     "                if '成交量' in df_li_show.columns else [])\n"),
    # 批 Z30（續，總管裁定）：`read_v4_macro_veto` 的 ffill（v4 引擎風險燈與 §八 跨區揭露的輸入）
    ("    # 先行指標取「與畫面主表格同一份」的末筆：批 Z30（Z29-n2）起兩邊皆為原始值、不再 ffill\n"
     "    #   （末日缺值不得以前日冒充）⇒ 缺值走引擎既有「⬜ 無法判定…外資期貨 未取得」，§三／§八 仍同一份輸入。\n",
     "    # 先行指標取「與畫面主表格同一份 ffill 後」的末筆：若 §三 吃 ffill 值、\n"
     "    # §八 吃原始 NaN，兩邊輸入不同 → 又會生出一次「同名不同結論」。\n"),
    ("            _row = _li.iloc[-1]\n",
     "            _num_cols = [c for c in _li.columns if c != '日期']\n"
     "            _row = _li[_num_cols].ffill().iloc[-1]\n"),
)


@functools.lru_cache(maxsize=None)
def _variant_with(pairs):
    """現行 section_chips 只把 `pairs`（修後, 修前）各恰一次換回基底寫法（其餘批次改動保留）。"""
    src = open(SC.__file__, encoding='utf-8').read()
    for new, old in pairs:
        assert src.count(new) == 1, f'替換點不唯一或已不存在：{new!r}'
        src = src.replace(new, old)
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader('_z30_pre_chips', loader=None))
    m.__file__ = SC.__file__
    exec(compile(src, SC.__file__, 'exec'), m.__dict__)
    return m


def pre_z30_chips_module():
    """現行 section_chips 只把本批各處（含續）換回基底 `4591c5aa` 寫法。

    📌 批 Z31（Q-z10／Q-z11，客戶 2026-10-10 核准，有意識的更正，⛔ 不是漏改）：基底 `4591c5aa` 尚無批 Z31 ⇒
    連同批 Z31 各處（`Z31_CHIPS_REVERT_PAIRS`，同樣恰一次替換）一併換回，本還原體仍等於該基底（比照批 Z30 對 z28 的作法）。
    """
    from tests.test_batch_z31 import Z31_CHIPS_REVERT_PAIRS
    return _variant_with(Z30_CHIPS_REVERT_PAIRS + Z31_CHIPS_REVERT_PAIRS)


def _chips_mod(li, mp, mod):
    fake = _FakeSTCode({'macro_info': {'vix': {'current': 15.0, 'ma20': 15.0}}, 'li_latest': li})
    mp.setattr(mod, 'st', fake)
    mp.setattr(AS, 'get_allocation', lambda *a, **k: types.SimpleNamespace(
        is_loaded=False, range_text='', capped=False, cap_text='', final_hi=None))
    mp.setattr(AS, 'get_allocation_sleeves', lambda *a, **k: None)
    mod.render_section_chips({}, None, {})
    return list(fake.out)


class TestRevertedCopyIsTheBase:
    def test_today_nan(self, monkeypatch):
        """還原體重現基底 `4591c5aa` 實跑：今日全缺（含成交量）被 ffill 成昨天 —— 表格今日列印昨天的值、
        進階警示四則、v5 紅色防禦、原始值 9 項全是昨天的。"""
        out = _chips_mod(_TODAY_NAN(), monkeypatch, pre_z30_chips_module())
        assert _digest(out) == TestTodayMissingNotImpersonated._PRE_GOLD
        assert '▼ (40,000)' in _tbody_row(out, '10月4日')
        w = _warn_txt(out)
        for t in ('期權同向崩盤警戒', '散戶過度樂觀', '外資投信同買', '選擇權Put/Call偏低'):
            assert t in w
        assert '嚴禁追高' in _v5_card(out) and '外資大小=-40,000' in _raw_line(out)

    @pytest.mark.parametrize('today', [math.nan, '-'])
    def test_signal5_pre_used_yesterday(self, today, monkeypatch):
        li = _li(*[dict(_DAY, 成交量=v) for v in ('3000.0億', '3000.0億', '3000.0億', '1000.0億', today)])
        w = _warn_txt(_chips_mod(li, monkeypatch, pre_z30_chips_module()))
        assert '今日成交量1000億' in w      # 修前：昨天的 1000 億被當成今日


class TestTodayMissingNotImpersonated:
    """末列（今日）全部數值欄缺 ⇒ 修前 ffill 印昨天的值並據以下結論；修後走各消費點既有缺值路徑。"""

    def test_table_today_row_dashes(self, monkeypatch):
        row = _tbody_row(_chips(_TODAY_NAN(), monkeypatch), '10月4日')
        assert row.count('<td>-</td>') == 12            # 修前：▼ 40,000／70.0／▲ 40.0%… 全是昨天的值
        assert _VOL_DASH in row
        assert '40,000' not in row and '70.0' not in row and '2,900' not in row

    def test_missing_not_zero(self, monkeypatch):
        """Missing 不填 0：今日列除日期外不出現任何數字（不是 0、也不是昨天的值）。"""
        row = _tbody_row(_chips(_TODAY_NAN(), monkeypatch), '10月4日')
        assert re.search(r'\d', _strip(row.split('</td>', 1)[1])) is None, row

    def test_previous_rows_untouched(self, monkeypatch):
        row = _tbody_row(_chips(_TODAY_NAN(), monkeypatch), '10月3日')
        assert '▼ (40,000)' in row and '70.0' in row and '2,900億' in row

    def test_no_signals_from_yesterday(self, monkeypatch):
        w = _warn_txt(_chips(_TODAY_NAN(), monkeypatch))
        # 修前（基底實跑）：以下四則全部以昨天的值列出。
        for t in ('期權同向崩盤警戒', '散戶過度樂觀', '外資投信同買', '選擇權Put/Call偏低', '成交量急'):
            assert t not in w, w
        assert not _INFNAN.search(w)

    def test_v5_card_unavailable(self, monkeypatch):
        card = _v5_card(_chips(_TODAY_NAN(), monkeypatch))
        assert '📌 外資期貨 未取得' in card            # 同卡既有缺值字（批 Z10）
        assert '嚴禁追高' not in card                  # 修前：昨天 -40000 ⇒ 紅色防禦句

    def test_raw_line_shows_no_yesterday(self, monkeypatch):
        """「最新一筆原始值」：缺值欄走既有「不列」（修前列出昨天的 外資大小=-40,000 等 9 項）。"""
        assert _raw_line(_chips(_TODAY_NAN(), monkeypatch)) == ''

    def test_csv_exports_raw(self, monkeypatch):
        """CSV 照實匯出原始值（v19.171 起的既有設計）：今日缺值為空格，不再是昨天的值。"""
        df = _csv(_chips(_TODAY_NAN(), monkeypatch))
        assert len(df) == 4
        assert df[_NUM].iloc[-1].isna().all()
        assert df['外資大小'].iloc[-2] == -40000.0

    def test_no_crash_no_leak_with_none_and_pdna(self, monkeypatch):
        for bad in (None, pd.NA):
            r = _nan_row()
            for c in _NUM:
                r[c] = bad
            r['成交量'] = bad
            li = _li(_DAY, _DAY, _DAY, r).astype({c: object for c in _NUM})
            out = _chips(li, monkeypatch)
            html = '\x1e'.join(t for _k, t in out)
            assert 'None' not in html and '<NA>' not in html and '&lt;NA' not in html
            assert not _INFNAN.search(_warn_txt(out))
            assert _tbody_row(out, '10月4日').count('<td>-</td>') == 12
            monkeypatch.undo()

    #: 修前基底 `4591c5aa` 實跑（今日全缺，被 ffill 成昨天）的整段 sha256 —— 本批後必不同。
    _PRE_GOLD = '4f8999225729192b91238a81399514b39197f8d834576d722d01d0f0fa7cbd1d'

    def test_differs_from_base(self, monkeypatch):
        assert _digest(_chips(_TODAY_NAN(), monkeypatch)) != self._PRE_GOLD


class TestMidRowMissing:
    """中間某日缺值：表格該格「-」（修前印前一日的值）；今日有值 ⇒ 訊號／v5 卡與「該日補任意值」相同。"""

    def _mid(self, fill=None):
        r = _nan_row(cols=['外資大小', '選PCR'], vol='3000.0億')
        if fill is not None:
            r['外資大小'], r['選PCR'] = fill
        return _li(_DAY, r, _DAY, _DAY)

    def test_mid_cells_dash(self, monkeypatch):
        row = _tbody_row(_chips(self._mid(), monkeypatch), '10月2日')
        assert row.count('<td>-</td>') == 2 and '40,000' not in row and '70.0' not in row

    def test_today_conclusions_unchanged(self, monkeypatch):
        a = _chips(self._mid(), monkeypatch)
        monkeypatch.undo()
        b = _chips(self._mid(fill=(-1.0, 999.0)), monkeypatch)
        assert _warn_txt(a) == _warn_txt(b) and '期權同向崩盤警戒' in _warn_txt(a)
        assert _v5_card(a) == _v5_card(b)
        assert _raw_line(a) == _raw_line(b)


class TestSignal5TodayVolume:
    def _vols(self, *vols):
        return _li(*[dict(_DAY, 成交量=v) for v in vols])

    @pytest.mark.parametrize('today', [math.nan, '-', None, pd.NA, 'abc'])
    def test_today_missing_not_listed(self, today, monkeypatch):
        """前 4 日 3000／3000／3000／1000 本會判「急萎縮」——⛔ 今日取不到時不得拿前一天當今天。
        修前：NaN（ffill）、「-」／None／pd.NA／非數字（dropna）皆印「今日成交量1000億…」。"""
        w = _warn_txt(_chips(self._vols('3000.0億', '3000.0億', '3000.0億', '1000.0億', today), monkeypatch))
        assert '成交量急' not in w and '今日成交量' not in w, w

    def test_mid_missing_still_dropped(self, monkeypatch):
        """中間列缺值照舊剔除（不改既有平均作法），今日有值 ⇒ 照常列出。"""
        w = _warn_txt(_chips(self._vols('3000.0億', math.nan, '3000.0億', '3000.0億', '1000.0億'), monkeypatch))
        assert '今日成交量1000億（前3日均量3000億的33%）' in w

    def test_finite_still_alerts(self, monkeypatch):
        w = _warn_txt(_chips(self._vols('3000.0億', '3000.0億', '3000.0億', '9000.0億'), monkeypatch))
        assert '今日成交量9000億（前均量3000億的300%）' in w


#: 修前基底 `4591c5aa` 同一支 `_chips` 實跑：**沒有可被 ffill 的缺值**時整段 §三 sha256（ffill 為恆等 ⇒ 必須逐字不變）。
_NO_FILL_BASE = {
    'all_finite': (lambda: _li(_DAY, _DAY, dict(_DAY, 外資大小=-5000.0, 選PCR=130.0, 韭菜指數=-3.0),
                               dict(_DAY, 成交量='1000.0億')), '93f01ef06015ad9d51c8dd0b6478943d47a141fb54d72b1c5f1efa42529d528a'),
    'leading_nan': (lambda: _li(_nan_row(vol='3000.0億'), _DAY, _DAY, _DAY), '2d72492b030bd273f63223b59ef2237e4c0f5dfb4305901cf41e76ca67fb185b'),
    'margin_all_nan': (lambda: _li(*[_nan_row(cols=['融資餘額', '融券餘額'], vol='3000.0億')] * 4), 'd4fcf6a4bcb16b9550979a9330bc47866a0b3bdb605aa2115366215531672d41'),
    'single_row': (lambda: _li(_DAY), 'a0cf30d62ff31524457e3d1532ef1f31777f52b05e742983c0877c690acf15b1'),
}


class TestNoFillUnchanged:
    @pytest.mark.parametrize('case', sorted(_NO_FILL_BASE))
    def test_golden(self, case, monkeypatch):
        mk, gold = _NO_FILL_BASE[case]
        assert _digest(_chips(mk(), monkeypatch)) == gold


class TestTodayInfAndColumnMissing:
    """今日 ±inf（ffill 本不填 inf，修前即「-」／不列；本批後同樣）與整欄缺：不顯示 inf、不崩、不下結論。"""

    @pytest.mark.parametrize('bad', [math.inf, -math.inf])
    def test_today_inf(self, bad, monkeypatch):
        r = dict(_DAY, **{c: bad for c in _NUM})
        r['成交量'] = f'{bad}億'
        out = _chips(_li(_DAY, _DAY, _DAY, r), monkeypatch)
        row = _tbody_row(out, '10月4日')
        assert row.count('<td>-</td>') == 12 and _VOL_DASH in row
        assert not _INFNAN.search(_strip('\x1e'.join(t for _k, t in out if 'li-tbl' in t)))
        w = _warn_txt(out)
        assert not _INFNAN.search(w)
        for t in ('期權同向崩盤警戒', '散戶過度', '軋空', '外資投信同', '選擇權Put/Call', '成交量急'):
            assert t not in w, w
        assert '📌 外資期貨 未取得' in _v5_card(out)

    def test_columns_missing(self, monkeypatch):
        """先行指標欄整欄缺（無 成交量／選PCR／外資大小）：不崩、表格該欄缺即不顯示、無假結論。"""
        li = _li(_DAY, _DAY, _DAY, _DAY).drop(columns=['成交量', '選PCR', '外資大小'])
        out = _chips(li, monkeypatch)
        row = _tbody_row(out, '10月4日')
        assert _VOL_DASH in row
        w = _warn_txt(out)
        assert '成交量急' not in w and '選擇權Put/Call' not in w and '期權同向崩盤' not in w
        assert '📌 外資期貨 未取得' in _v5_card(out)


# ══════════════════════════════════════════════════════════════════════════
# 4. 批 Z30（續，總管裁定）：v4 引擎風險燈與 §八 跨區揭露不再以前日值冒充當日
#    `read_v4_macro_veto()` 原另做 `.ffill().iloc[-1]` ⇒ 今日外資期貨缺、昨日 −40,000 時 v4 燈仍判
#    「🔴 紅燈…外資期貨=-40,000口」，§八 揭露框亦據以列出 —— 與表格／v5 卡的缺值自相矛盾。
#    修後缺值走引擎既有「⬜ 無法判定…外資期貨 未取得」與 §八 既有 caption（批 Z27 Q-z2 核准字句）。
# ══════════════════════════════════════════════════════════════════════════

_V4_UNKNOWN_HEAD = '⬜ 無法判定'
_V4_UNKNOWN_MSG = '⬜ 總經環境無法判定：外資期貨 未取得（VIX=15.0 / 外資期貨=未取得）'


def _v4_card(out) -> str:
    cards = [t for _k, t in out if f'🏛️ {VETO_V4_ENGINE_NAME}' in t]
    assert len(cards) == 1
    return _strip(cards[0])


def _read_v4(li, mp, mod=SC, vix=15.0):
    mp.setattr(mod, 'st', _FakeSTCode({'macro_info': {'vix': {'current': vix}}, 'li_latest': li}))
    return mod.read_v4_macro_veto()


#: 末列外資期貨缺、前一日有值（含原 z10／z28 記錄 ffill 後燈號的情境）
_LAST_MISSING = {
    'today_all_nan(-40000)': _TODAY_NAN,
    'z28_b_last_nan(-20000)': lambda: pd.DataFrame({'日期': ['a', 'b'], '外資大小': [-20000.0, math.nan],
                                                     '選PCR': [100.0, 110.0]}),
    'z28_last_nan(-16000)': lambda: pd.DataFrame({'日期': ['a', 'b'], '外資大小': [-16000.0, math.nan],
                                                   '選PCR': [100.0, 110.0]}),
    'z28_last_nan_nopcr(+3000)': lambda: pd.DataFrame({'日期': ['a', 'b'], '外資大小': [3000.0, math.nan]}),
    'today_None(-40000)': lambda: pd.DataFrame({'日期': ['a', 'b'], '外資大小': pd.Series([-40000.0, None], dtype=object)}),
    'today_pdNA(-40000)': lambda: pd.DataFrame({'日期': ['a', 'b'], '外資大小': pd.Series([-40000.0, pd.NA], dtype=object)}),
}


class TestV4LightTodayMissing:
    @pytest.mark.parametrize('case', sorted(_LAST_MISSING))
    def test_inputs_are_raw_last_row(self, case, monkeypatch):
        v = _read_v4(_LAST_MISSING[case](), monkeypatch)
        assert v['_futures'] is None and v['status'].startswith(_V4_UNKNOWN_HEAD)

    @pytest.mark.parametrize('case', sorted(_LAST_MISSING))
    def test_pre_used_previous_day(self, case, monkeypatch):
        """還原體（ffill 加回）：同一份資料，引擎吃到的是前一日的值 —— 本批修掉的正是這個。"""
        v = _read_v4(_LAST_MISSING[case](), monkeypatch, mod=pre_z30_chips_module())
        assert v['_futures'] is not None and not v['status'].startswith(_V4_UNKNOWN_HEAD)

    def test_card_today_all_nan(self, monkeypatch):
        card = _v4_card(_chips(_TODAY_NAN(), monkeypatch))
        assert _V4_UNKNOWN_HEAD in card and _V4_UNKNOWN_MSG in card
        assert '-40,000' not in card and '🔴 紅燈' not in card and not _INFNAN.search(card)

    def test_card_pre_was_red_from_yesterday(self, monkeypatch):
        card = _v4_card(_chips_mod(_TODAY_NAN(), monkeypatch, pre_z30_chips_module()))
        assert '🔴 紅燈' in card and '外資期貨=-40,000口' in card       # 修前：昨日 −40,000 冒充今日

    def test_only_v4_card_differs_from_partial_revert(self, monkeypatch):
        """只把 read_v4 的 ffill 加回（其餘本批改動保留）⇒ 整段只差 v4 卡一段。"""
        only_v4 = _variant_with(Z30_CHIPS_REVERT_PAIRS[2:])
        a = _chips(_TODAY_NAN(), monkeypatch)
        monkeypatch.undo()
        b = _chips_mod(_TODAY_NAN(), monkeypatch, only_v4)
        diff = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        assert len(a) == len(b) and len(diff) == 1 and f'🏛️ {VETO_V4_ENGINE_NAME}' in a[diff[0]][1]

    @pytest.mark.parametrize('fut, head', [(-40000.0, '🔴 紅燈'), (-15000.0, '🟡'), (5000.0, '🟢')])
    def test_today_finite_unchanged(self, fut, head, monkeypatch):
        li = _li(_DAY, dict(_DAY, 外資大小=fut))
        now = _v4_card(_chips(li, monkeypatch))
        monkeypatch.undo()
        assert now == _v4_card(_chips_mod(li, monkeypatch, pre_z30_chips_module())) and head in now


# ── §八 跨區揭露（真 §三 入口 `read_v4_macro_veto`）──────────────────────────
_CAP_FUT8 = (f'（§三 籌碼的「{VETO_V4_ENGINE_NAME}」因外資期貨未取得而無法判定，'
             '本區與該燈暫時無法比對）')
_BOX8 = '兩套判定結論不一致'


def _mid8(li, mp, chips_mod=None, mid_mod=None):
    import tests.test_batch_z7 as Z7
    mod = mid_mod or Z7._real(Z7._MID)
    info = dict(Z7._MID_BASE)
    info['vix'] = Z7._node(18.0)
    fake = Z7._FakeSTFig({'macro_info': info, 'bias_info': {'bias_240': 5.0}, 'li_latest': li})
    mp.setattr(mod, 'st', fake)
    mp.setattr(SC, 'st', fake)
    if chips_mod is not None:
        mp.setattr(chips_mod, 'st', fake)
        mp.setattr(SC, 'read_v4_macro_veto', chips_mod.read_v4_macro_veto)
    mp.setattr(AS, 'apply_vix_veto', lambda *a, **k: None)
    mp.setattr(AS, 'apply_ring_gate', lambda *a, **k: None)
    mp.setattr(AS, 'register_conflict', lambda *a, **k: None)
    mp.setattr(AS, 'get_allocation', lambda *a, **k: types.SimpleNamespace(is_loaded=False, final_hi=None))
    mod.render_section_mid(False, {}, {}, {})
    return list(fake.out)


def _disc8(out):
    return [(k, t) for k, t in out if (k == 'warning' and _BOX8 in t)
            or (k == 'caption' and t.startswith('（§三 籌碼的「'))]


#: 基底 `4591c5aa` 實跑：今日全缺＋昨日 −40,000 的整段 §八 sha256（揭露框列出「🔴 紅燈…外資期貨=-40,000 口」）。
_PRE_MID8_GOLD = 'c31d07772909fb61921bfefe11cf7cfb82dc2dd2e880829dbb029616ba2a70b7'


class TestSection8Disclosure:
    @pytest.mark.parametrize('case', sorted(_LAST_MISSING))
    def test_today_missing_caption(self, case, monkeypatch):
        out = _mid8(_LAST_MISSING[case](), monkeypatch)
        assert _disc8(out) == [('caption', _CAP_FUT8)], _disc8(out)
        j = '\x1e'.join(t for _k, t in out)
        assert '外資期貨=-' not in j and '外資期貨=3,000' not in j
        assert not _INFNAN.search(_strip(j))

    def test_pre_disclosed_yesterday_and_equals_base(self, monkeypatch):
        # 📌 批 Z34（Q-z13，客戶 2026-10-10 核准，有意識的變更）：今日外資期貨缺 ⇒ 本批起火力分級卡改「⬜ 無法判定」；
        #   本測試比的是基底 `4591c5aa` 整段 golden，故 §八 取拿掉 Z34 修改的還原體（golden 不改）。
        from tests.test_batch_z34 import z34_pre_module
        out = _mid8(_TODAY_NAN(), monkeypatch, chips_mod=pre_z30_chips_module(), mid_mod=z34_pre_module('mid'))
        d = _disc8(out)
        assert len(d) == 1 and d[0][0] == 'warning' and '外資期貨=-40,000 口' in d[0][1]
        assert hashlib.sha256(repr(out).encode('utf-8')).hexdigest() == _PRE_MID8_GOLD

    def test_only_disclosure_changed(self, monkeypatch):
        new = _mid8(_TODAY_NAN(), monkeypatch)
        monkeypatch.undo()
        old = _mid8(_TODAY_NAN(), monkeypatch, chips_mod=pre_z30_chips_module())
        diff = [i for i, (a, b) in enumerate(zip(new, old)) if a != b]
        assert len(new) == len(old) and len(diff) == 1
        assert new[diff[0]] == ('caption', _CAP_FUT8) and _BOX8 in old[diff[0]][1]

    def test_today_finite_unchanged(self, monkeypatch):
        li = _li(_DAY, _DAY)
        new = _mid8(li, monkeypatch)
        monkeypatch.undo()
        old = _mid8(li, monkeypatch, chips_mod=pre_z30_chips_module())
        assert new == old and '外資期貨=-40,000 口' in _disc8(new)[0][1]
