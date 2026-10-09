"""批 Z19（客戶裁示：PMI = 50 統一語意為「中性（榮枯線）」）—— 三值守衛（基底 origin/main `d46d785b`）。

客戶裁示（總管轉述，逐字摘要）：PMI < 50＝收縮；PMI = 50＝中性／榮枯線；PMI > 50＝擴張；
風險燈在 =50 仍維持黃燈；曝險與長期 regime 的 =50 計分維持原裁示不變；
§九 ⑤ 因中性判定自然造成的綜合研判變化可接受，但不得另外修改評分邏輯；
不新增新的投資／持股指示。

本檔以 PMI 49.9／50／50.1 三值釘住：
- 五桶燈（`shared/macro_buckets` ism_pmi）：燈號不變（黃／黃／綠）＋ note／source 字句；
- §八 台灣 PMI 卡（`TW_PMI_CARD_BANDS` + `resolve_band`／`bands_caption`）：=50 為「🟡 中性（榮枯線）」；
  其他 band 表輸出逐字不變；
- §九 ①（`section_cross_ai`）：=50 走既有「景氣整理期 🟡」分支（desc 原句沿用，不另加字）；
- macro_state_locker 計分／長期 regime：三值輸出與基底逐字相同（未動）。
修前（基底）=50 在 §八 卡為「✅ 擴張」、§九 ① 為「景氣溫和擴張 🟢 …（擴張）…」→ 本檔在基底轉紅。
golden 為基底 `d46d785b` 實跑後寫死（⛔ 不由現行碼反推）。
"""
from __future__ import annotations

import re
import types
from pathlib import Path

import pytest

import shared.macro_buckets as mb
import src.services.allocation_service as AS
import src.ui.tabs.macro.section_cross_ai as CR
from shared import signal_thresholds as T
from src.ui.render.macro_ui_components import bands_caption, resolve_band
from tests.test_m2n2_no_zero_fill import _FakeST

_ROOT = Path(__file__).resolve().parent.parent
_PMI = next(s for s in mb.BUCKET_DANGER_SPECS if s.key == 'ism_pmi')


# ══════════════════════════════════════════════════════════════════════════
# 五桶燈（風險燈 =50 維持黃燈；字句改為「=50 中性（榮枯線）」）
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize('v, lamp', [(49.9, 'yellow'), (50.0, 'yellow'), (50.1, 'green')])
def test_bucket_lamp_unchanged(v, lamp):
    assert mb.classify_danger(v, _PMI) == lamp


def test_bucket_note_and_source():
    assert _PMI.note == '=50 中性（榮枯線） / <50 收縮 / ≤46 嚴重收縮'
    assert _PMI.source == '黃線 50／紅線 46：有既有常數背書（統一閾值表）'


# ══════════════════════════════════════════════════════════════════════════
# §八 台灣 PMI 卡
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize('v, band', [
    (49.9, ('yellow', '⚠️ 輕微收縮', '輕微收縮,留意內需與外銷動能')),
    (50.0, ('yellow', '🟡 中性（榮枯線）', '製造業好壞均衡')),
    (50.1, ('green', '✅ 擴張', '製造業擴張,內外需動能正向')),
])
def test_s8_pmi_card_band(v, band):
    assert resolve_band(v, T.TW_PMI_CARD_BANDS) == band


def test_s8_pmi_card_caption():
    assert bands_caption(T.TW_PMI_CARD_BANDS) == '✅>50｜🟡=50｜⚠️≥47｜🔴<47'


# 其他 band 表（無相鄰同 lo）：門檻帶說明與判定逐字同基底。
_OTHER_CAPTIONS = {
    'NDC_SIGNAL_BANDS': '🔴≥38｜🟡≥32｜🟢≥23｜🔵≥17｜🔵<17',
    'TW_EXPORT_YOY_BANDS': '✅≥0｜⚠️≥-5｜🔴<-5',
    'US_CORE_CPI_YOY_BANDS': '🔴≥3.5｜⚠️≥2.5｜✅<2.5',
    'FED_FUNDS_RATE_BANDS': '🔴≥5｜⚠️≥3｜✅<3',
}


@pytest.mark.parametrize('name', sorted(_OTHER_CAPTIONS))
def test_other_band_tables_unchanged(name):
    bands = getattr(T, name)
    assert bands_caption(bands) == _OTHER_CAPTIONS[name]
    for lo, ck, label, meaning in bands:          # 邊界值仍取該帶（≥ 語意）
        if lo != float('-inf'):
            assert resolve_band(lo, bands) == (ck, label, meaning)


# ══════════════════════════════════════════════════════════════════════════
# §九 ① 目前總經位階
# ══════════════════════════════════════════════════════════════════════════
_S9_RE = re.compile(r'① 目前總經位階</div><div[^>]*>([^<]*)</div><div[^>]*>([^<]*)</div>')


def _s9_cycle(pmi, exp, mp):
    info = {'ism_pmi': {'value': pmi}, 'vix': {'current': 18.0, 'ma20': 17.5}}
    if exp is not None:
        info['tw_export'] = {'yoy': exp}
    fake = _FakeST({'macro_info': info, 'm1b_m2_info': None, 'bias_info': None})
    mp.setattr(CR, 'st', fake)
    mp.setattr(AS, 'get_allocation', lambda *a, **k: types.SimpleNamespace(is_loaded=False))
    CR.render_section_cross_ai({}, {})
    m = _S9_RE.search('\n'.join(t for _k, t in fake.out))
    assert m, '§九 ① 卡未輸出'
    return m.groups()


_S9_CASES = [
    # （PMI, 出口 YoY）→（標籤, 說明）
    (49.9, 3.0, ('景氣整理期 🟡', '台灣 PMI=49.9 × 台灣出口YoY=+3.0%— 方向待確認，保守持股')),
    (49.9, 6.0, ('景氣觸底回升 💎', '台灣 PMI=49.9（收縮但出口反彈）× 台灣出口YoY=+6.0%— 左側佈局黃金窗口')),
    (49.9, -1.0, ('景氣收縮期 📉', '台灣 PMI=49.9（收縮）× 台灣出口YoY=-1.0%— 多看少做，等待出口數據翻正')),
    (49.9, None, ('景氣趨緩（出口待確認）', '台灣 PMI=49.9 — 台灣出口數據載入中')),
    (50.0, 3.0, ('景氣整理期 🟡', '台灣 PMI=50.0 × 台灣出口YoY=+3.0%— 方向待確認，保守持股')),
    (50.0, 12.0, ('景氣整理期 🟡', '台灣 PMI=50.0 × 台灣出口YoY=+12.0%— 方向待確認，保守持股')),
    (50.0, 6.0, ('景氣整理期 🟡', '台灣 PMI=50.0 × 台灣出口YoY=+6.0%— 方向待確認，保守持股')),
    (50.0, -1.0, ('景氣整理期 🟡', '台灣 PMI=50.0 × 台灣出口YoY=-1.0%— 方向待確認，保守持股')),
    (50.0, None, ('景氣整理期（出口待確認）', '台灣 PMI=50.0 — 台灣出口數據載入中')),
    (50.1, 3.0, ('景氣溫和擴張 🟢', '台灣 PMI=50.1（擴張）× 台灣出口YoY=+3.0%— 穩步復甦，基本面有撐，持股安全')),
    (50.1, -1.0, ('景氣高峰震盪 ⚡', '台灣 PMI=50.1（微擴張）× 台灣出口YoY=-1.0%— 高位整理，需求疲軟，留意反轉訊號')),
    (50.1, None, ('景氣擴張（出口待確認）', '台灣 PMI=50.1 — 台灣出口數據載入中')),
]


@pytest.mark.parametrize('pmi, exp, want', _S9_CASES)
def test_s9_cycle_card(pmi, exp, want, monkeypatch):
    assert _s9_cycle(pmi, exp, monkeypatch) == want


def test_s9_neutral_adds_no_new_wording(monkeypatch):
    """=50 的 ① 說明只能是既有整理期句型（不得多出「中性」以外的新持股指示字）。"""
    _lbl, desc = _s9_cycle(50.0, 3.0, monkeypatch)
    _lbl2, desc2 = _s9_cycle(49.9, 3.0, monkeypatch)
    assert desc.replace('50.0', '49.9') == desc2


# ══════════════════════════════════════════════════════════════════════════
# AI 提示詞：PMI 判讀句
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize('rel, var', [('src/ui/tabs/macro/section_news_ai.py', '_pmi_mid'),
                                      ('src/ui/tabs/tab_stock.py', '_pmi_mid2')])
def test_prompt_pmi_wording(rel, var):
    """提示詞句型 `{v} 為榮枯線：>{v} 擴張、={v} 中性、<{v} 收縮`，v 由 ism_pmi 黃線（=50）插值。"""
    src = (_ROOT / rel).read_text(encoding='utf-8')
    v = '{' + var + '}'
    assert f'{v} 為榮枯線：>{v} 擴張、={v} 中性、<{v} 收縮' in src
    assert re.search(var + r''' = f'\{_bk_specs2?\["ism_pmi"\]\.yellow:g\}'$''', src, re.M)
    assert f'{mb.SPECS_BY_KEY["ism_pmi"].yellow:g}' == '50'
    assert '黃線即榮枯分界' not in src


# ══════════════════════════════════════════════════════════════════════════
# 計分不變：macro_state_locker／長期 regime（基底實跑 golden）
# ══════════════════════════════════════════════════════════════════════════
_LOCKER_BASE = {"VIX_Index": 18, "PMI_Prev_Month": 51, "M1B_YoY_pct": 5, "M2_YoY_pct": 4,
                "BIAS240_pct": 5, "PCR": 1.0, "Futures_Net_Short": -5000}
_LOCKER_GOLD = {
    49.9: {'market_regime': '震盪', 'systemic_risk_level': '警告', 'exposure_limit_pct': 60,
           'Macro_Phase': 'PMI收縮(49.9)'},
    50.0: {'market_regime': '震盪', 'systemic_risk_level': '警告', 'exposure_limit_pct': 60,
           'Macro_Phase': '環境正常'},
    50.1: {'market_regime': '震盪', 'systemic_risk_level': '警告', 'exposure_limit_pct': 60,
           'Macro_Phase': '環境正常'},
}
_LT_PMI_PTS = {49.9: (-1, 0.25), 50.0: (0, 0.45), 50.1: (0, 0.45)}


@pytest.mark.parametrize('v', [49.9, 50.0, 50.1])
def test_locker_scoring_unchanged(v):
    from src.services.macro_state_locker import calculate_system_state
    assert calculate_system_state(dict(_LOCKER_BASE, ISM_PMI_or_OECD_CLI=v)) == _LOCKER_GOLD[v]


@pytest.mark.parametrize('v', [49.9, 50.0, 50.1])
def test_long_term_regime_unchanged(v):
    from src.compute.macro.macro_helpers import classify_long_term_regime
    r = classify_long_term_regime(2.5, 4.0, 4.0, 25, v)
    pts, score = _LT_PMI_PTS[v]
    assert dict((n, p) for n, p, _w in r['components'])['台 PMI'] == pts
    assert r['score'] == pytest.approx(score)
    assert r['regime'] == '🔵 復甦期'
