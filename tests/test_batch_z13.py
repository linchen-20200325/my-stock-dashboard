"""批 Z13：VIX ≤ 0／> 100 在取數層當抓取失敗（Z3-n6、C7-n6、C8-n3）。

客戶 2026-10-06 裁示 Q-r8b ②「VIX ≤0／>100 取數層當抓取失敗，改一處修四處」（總管轉述）。

修法（L1 取數層，兩個 VIX 取數點；判定重用 L0 `shared.vix_validity.vix_value_or_none`，加 `upper=`）：
- `macro_snapshot.fetch_vix_block`（`macro_info['vix']` 的唯一來源）：末筆 ≤ 0／> 100 → 走既有失敗出口
  `{'_err_vix': 'not enough data'}`（同「末筆非有限」）；中段同樣剔除（同中段非有限）。
- `macro_alert._yf_latest`（頂部警示看板在 `macro_info` 沒有 VIX 時的補抓點）：^VIX ≤ 0／> 100 → 當抓不到
  （None）→ 走既有「含抓不到的檔 → 不入快取」出口。

下游 §三／§八／§九／五桶／警示看板／L3 配置一律只讀上面兩處 → 看到的是「VIX 抓取失敗」，與既有失敗逐字相同。
C7-n6（L3 `_read_vix` 無下限）、C8-n3（VIX > 100 各區不一致）由 L1 收斂，L3／L5 一行未改（本檔 C 段以實跑證明）。

「修前」一律指基底 origin/main `1354d9ac`：本檔 A／B／C 段在基底實跑皆轉紅（實作組實測）。
"""
from __future__ import annotations

import math
import types

import pandas as pd
import pytest

from src.data.macro import macro_alert, macro_snapshot
from tests.test_batch_z7 import _DROP, _MID_BASE, _S9_FULL, _chips, _mid, _s9

_ERR = {'_err_vix': 'not enough data'}


def _vix_df(closes):
    idx = pd.date_range('2026-09-01', periods=len(closes), freq='D')
    return pd.DataFrame({'Close': closes}, index=idx)


@pytest.fixture
def clear_vix():
    macro_snapshot.fetch_vix_block.clear()
    macro_alert._yf_latest.clear()
    yield
    macro_snapshot.fetch_vix_block.clear()
    macro_alert._yf_latest.clear()


def _l1(closes, mp):
    """以假 yfinance 實跑 L1 `fetch_vix_block`。"""
    import yfinance
    mp.setattr(yfinance, 'download', lambda *a, **k: _vix_df(list(closes)))
    macro_snapshot.fetch_vix_block.clear()
    return macro_snapshot.fetch_vix_block()


_OK = [18.0] * 25
_BAD_LAST = [pytest.param(v, id=i) for v, i in (
    (-5.0, '-5'), (0.0, '0'), (-0.0, '-0.0'), (-1e-9, '-1e-9'), (-1.7e308, '-1.7e308'),
    (150.0, '150'), (100.0001, '100.0001'), (100.1, '100.1'), (1e300, '1e300'), (1.7e308, '1.7e308'),
)]


# ══════════════════════════════════════════════════════════════════════════
# A. L1 fetch_vix_block
# ══════════════════════════════════════════════════════════════════════════
class TestFetchVixBlock:
    @pytest.mark.parametrize('bad', _BAD_LAST)
    def test_last_out_of_range_is_fetch_failure(self, bad, monkeypatch, clear_vix, capsys):
        assert _l1(_OK + [bad], monkeypatch) == _ERR
        assert '[Macro/VIX] ❌' in capsys.readouterr().out   # 出聲（§1），不靜默

    @pytest.mark.parametrize('ok,cur', [(100.0, 100.0), (99.95, 100.0), (0.1, 0.1), (18.37, 18.4)])
    def test_boundary_still_valid(self, ok, cur, monkeypatch, clear_vix):
        out = _l1(_OK + [ok], monkeypatch)
        assert out['vix']['current'] == cur
        assert out['vix']['values'][-1] == cur

    def test_normal_series_unchanged(self, monkeypatch, clear_vix):
        out = _l1([15.0, 16.0, 17.0, 18.24], monkeypatch)['vix']
        assert (out['current'], out['ma20'], out['values']) == (18.2, 16.6, [15.0, 16.0, 17.0, 18.2])
        assert out['dates'] == ['2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04']

    @pytest.mark.parametrize('bad', [-5.0, 0.0, 150.0, 1.7e308])
    def test_mid_series_dropped_like_non_finite(self, bad, monkeypatch, clear_vix, capsys):
        out = _l1([10.0, bad, 20.0, 30.0], monkeypatch)['vix']
        assert out['values'] == [10.0, 20.0, 30.0]
        assert out['dates'] == ['2026-09-01', '2026-09-03', '2026-09-04']
        assert out['ma20'] == 20.0
        assert '剔除中段' in capsys.readouterr().out

    def test_failure_not_cached_success_cached(self, monkeypatch, clear_vix):
        """§1.A-3(a)：失敗不入快取（上游恢復後下一次就重抓）；成功照舊入快取（證明快取真的在作用）。"""
        import yfinance
        feed = [_OK + [-5.0], _OK + [150.0], _OK + [19.0], _OK + [21.0]]
        calls = []

        def _dl(*a, **k):
            calls.append(1)
            return _vix_df(feed[len(calls) - 1])

        monkeypatch.setattr(yfinance, 'download', _dl)
        assert macro_snapshot.fetch_vix_block() == _ERR
        assert macro_snapshot.fetch_vix_block() == _ERR
        assert macro_snapshot.fetch_vix_block()['vix']['current'] == 19.0
        assert macro_snapshot.fetch_vix_block()['vix']['current'] == 19.0
        assert len(calls) == 3


# ══════════════════════════════════════════════════════════════════════════
# B. L1 警示看板補抓點 macro_alert._yf_latest
# ══════════════════════════════════════════════════════════════════════════
def _yf(mp, seq):
    calls = []

    def _fake(tickers):
        calls.append(tickers)
        v = seq[min(len(calls), len(seq)) - 1]
        return {t: (v if t == '^VIX' else {'^TNX': 4.2, 'DX-Y.NYB': 100.0}[t]) for t in tickers}

    mp.setattr(macro_alert, '_macro_core_yf_latest', _fake)
    return calls


def _vix_alerts(snap):
    return [a for a in macro_alert.check_macro_alerts(snap) if a['key'] == 'vix']


class TestAlertBoardFallback:
    @pytest.mark.parametrize('bad', [-5.0, 0.0, 150.0, 100.0001])
    def test_bad_vix_dropped_and_not_cached(self, bad, monkeypatch, clear_vix):
        calls = _yf(monkeypatch, [bad, 25.0])
        snap = macro_alert.fetch_macro_snapshot(session_macro={**_ERR})
        assert 'vix' not in snap
        assert _vix_alerts(snap) == []
        assert (snap['us10y'], snap['dxy']) == (4.2, 100.0)       # 同批其他檔不受影響
        snap2 = macro_alert.fetch_macro_snapshot(session_macro={**_ERR})
        assert snap2['vix'] == 25.0 and len(calls) == 2           # 沒被快取 → 上游恢復即重抓

    @pytest.mark.parametrize('ok', [100.0, 25.0, 0.5])
    def test_valid_vix_unchanged_and_cached(self, ok, monkeypatch, clear_vix):
        calls = _yf(monkeypatch, [ok])
        assert macro_alert.fetch_macro_snapshot(session_macro={})['vix'] == ok
        assert macro_alert.fetch_macro_snapshot(session_macro={})['vix'] == ok
        assert len(calls) == 1

    def test_session_vix_path_unchanged(self, monkeypatch, clear_vix):
        calls = _yf(monkeypatch, [99.0])
        snap = macro_alert.fetch_macro_snapshot(session_macro={'vix': {'current': 31.2}})
        assert snap['vix'] == 31.2 and calls == [('^TNX', 'DX-Y.NYB')]
        assert [a['emoji'] for a in _vix_alerts(snap)] == ['🔴']


# ══════════════════════════════════════════════════════════════════════════
# C. 下游：L1 收斂後各區＝「VIX 抓取失敗」（C7-n6、C8-n3 不另改 L3／L5）
# ══════════════════════════════════════════════════════════════════════════
#: 對照組：既有失敗（Close 全 NaN → 既有出口 'not enough data'）。
_REF_CLOSES = [math.nan] * 5


def _split(part, base):
    """仿 orchestrator `_r.update(part)`：回 (vix 節點或 _DROP, 其餘併入 base)。"""
    node = part.get('vix', _DROP)
    return node, {**base, **{k: v for k, v in part.items() if k != 'vix'}}


_SCEN = [pytest.param(-5.0, id='VIX=-5'), pytest.param(150.0, id='VIX=150')]


class TestDownstreamEqualsFetchFailure:
    @pytest.mark.parametrize('bad', _SCEN)
    def test_section8(self, bad, monkeypatch, clear_vix):
        n_ref, b_ref = _split(_l1(_REF_CLOSES, monkeypatch), _MID_BASE)
        n_got, b_got = _split(_l1(_OK + [bad], monkeypatch), _MID_BASE)
        ref = _mid(n_ref, monkeypatch, base=b_ref)
        assert _mid(n_got, monkeypatch, base=b_got) == ref
        assert ref[1] == [(None,)]                       # VIX 否決權收到「未知」

    @pytest.mark.parametrize('bad', _SCEN)
    def test_section9(self, bad, monkeypatch, clear_vix):
        n_ref, b_ref = _split(_l1(_REF_CLOSES, monkeypatch), _S9_FULL)
        n_got, b_got = _split(_l1(_OK + [bad], monkeypatch), _S9_FULL)
        got = _s9(n_got, monkeypatch, base=b_got)
        assert got == _s9(n_ref, monkeypatch, base=b_ref)
        txt = '\n'.join(t for _k, t in got)
        assert '急凍' not in txt and '極度平靜' not in txt

    @pytest.mark.parametrize('bad', _SCEN)
    def test_section3(self, bad, monkeypatch, clear_vix):
        n_got, _ = _split(_l1(_OK + [bad], monkeypatch), {})
        n_ref, _ = _split(_l1(_REF_CLOSES, monkeypatch), {})
        got = _chips(None if n_got is _DROP else n_got, monkeypatch)
        assert got == _chips(None if n_ref is _DROP else n_ref, monkeypatch)
        assert got[1] is None

    @pytest.mark.parametrize('bad', _SCEN)
    def test_five_buckets_short(self, bad, monkeypatch, clear_vix):
        from src.compute.macro.macro_helpers import compute_five_bucket_summary
        ref = compute_five_bucket_summary(macro_info=_l1(_REF_CLOSES, monkeypatch))
        got = compute_five_bucket_summary(macro_info=_l1(_OK + [bad], monkeypatch))
        assert got['short'] == ref['short']
        assert got['short']['label'] != '急殺風險'

    @pytest.mark.parametrize('bad', _SCEN)
    def test_alert_board(self, bad, monkeypatch, clear_vix):
        _yf(monkeypatch, [bad])                         # 同源補抓也拿到同一個壞值
        snap = macro_alert.fetch_macro_snapshot(session_macro=_l1(_OK + [bad], monkeypatch))
        assert 'vix' not in snap and _vix_alerts(snap) == []

    @pytest.mark.parametrize('bad', _SCEN)
    def test_allocation_caps(self, bad, monkeypatch, clear_vix):
        import src.services.allocation_service as AS
        li = pd.DataFrame({'日期': ['2026-10-01'], '外資大小': [5000.0]})

        def _caps(mi):
            monkeypatch.setattr(AS, 'st', types.SimpleNamespace(
                session_state={'macro_info': mi, 'li_latest': li}))
            return AS._read_vix(), AS._derive_intrinsic_caps()

        got = _caps(_l1(_OK + [bad], monkeypatch))
        ref = _caps(_l1(_REF_CLOSES, monkeypatch))
        assert got == ref
        assert got[0] is None and got[1][0] == []        # 不掛 VIX 否決、不扣三環
        assert any('VIX' in c and '未取得' in c for c in got[1][1])
