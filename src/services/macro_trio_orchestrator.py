"""src/services/macro_trio_orchestrator.py — outer trio executor(P3-D12 v18.392 抽出)。

從 tab_macro inline 抽出(原 line 352-493,~142 LOC):
- 3 個薄殼 job: _job_m1b / _job_bias / _job_macro(各自委派 macro_snapshot 內 fetcher)
- 並發 trio ThreadPoolExecutor (max_workers=3)
- as_completed + 200s global timeout + cancel stuck futures
- shutdown(wait=False) — 不等 zombie thread
- 3 個 session_state writes(m1b_m2_info / bias_info / macro_info)守 truthy(§1 不蓋 stale)

§8.2 L3 service:純並發 orchestration + session writes。

ThreadPoolExecutor/as_completed/TimeoutError 由 caller 注入避循環(雖然都是
stdlib;此處為對齊 macro_fetch_orchestrator pattern,保 explicit DI 風格)。
"""
from __future__ import annotations

import datetime as _dt
import os

import streamlit as st


def run_macro_trio_and_persist(
    *,
    tw_raw: dict,
    fred_api_key: str = '',
    fm_token: str = '',
    global_timeout_s: int = 200,
    inner_pool_timeout_s: int = 70,
) -> None:
    """並發跑 m1b / bias / macro 3 job + 寫 session_state(§1 truthy guard)。

    參數:
        tw_raw: dict  ^TWII OHLCV 從 fetch_macro_bundle 取(closure dep:_job_bias 需要)
        fred_api_key: str  FRED_API_KEY(空字串 = 不嘗試 FRED 路徑)
        fm_token: str      FINMIND_TOKEN
        global_timeout_s: int  outer as_completed 全域 timeout(預設 200s)
        inner_pool_timeout_s: int  _job_macro 內部 6-fetcher pool timeout(預設 70s)

    寫入:
        st.session_state['m1b_m2_info']  if m1b 成功
        st.session_state['bias_info']    if bias 成功
        st.session_state['macro_info']   if macro 成功(含 6 sub-key + fetched_at)
    """
    from concurrent.futures import (
        ThreadPoolExecutor,
        TimeoutError as _ConcFutTimeout,
        as_completed,
    )

    # ── 3 個薄殼 job ─────────────────────────────────────────
    def _job_m1b():
        # 3-Tier fallback(CBC/FRED/IMF)— macro_snapshot.fetch_m1b_m2_block
        from src.data.macro.macro_snapshot import fetch_m1b_m2_block
        return fetch_m1b_m2_block(fred_api_key=fred_api_key)

    def _job_bias():
        # closure dep: tw_raw.get('台股加權指數')
        try:
            from src.data.macro.macro_snapshot import compute_twii_bias
            return compute_twii_bias(tw_raw.get('台股加權指數'))
        except Exception as _bias_e:
            print(f'[Bias] compute_twii_bias 失敗: {_bias_e}')
            return None

    def _job_macro():
        """6-fetcher 並行(VIX/CPI/PMI/NDC/Export/Fed)+ provenance 注入。"""
        from src.data.macro.macro_snapshot import (
            fetch_vix_block, fetch_cpi_block, fetch_fed_funds_block,
            fetch_tw_pmi_block, fetch_ndc_block, fetch_export_block,
        )
        _fetchers = {
            'vix':       fetch_vix_block,
            'cpi':       lambda: fetch_cpi_block(fred_api_key=fred_api_key),
            'pmi':       fetch_tw_pmi_block,
            'ndc':       fetch_ndc_block,
            'export':    lambda: fetch_export_block(
                             fred_api_key=fred_api_key, finmind_token=fm_token),
            'fed_funds': lambda: fetch_fed_funds_block(fred_api_key=fred_api_key),
        }
        _r: dict = {}
        _pool_mc = ThreadPoolExecutor(max_workers=6)
        try:
            _futs_mc = {_pool_mc.submit(fn): name
                        for name, fn in _fetchers.items()}
            try:
                for _fut_mc in as_completed(_futs_mc, timeout=inner_pool_timeout_s):
                    try:
                        _part = _fut_mc.result()
                        if _part:
                            _r.update(_part)
                    except Exception as _e:
                        print(f'[Macro] ❌ {_futs_mc.get(_fut_mc, "?")}: {_e}')
            except (TimeoutError, _ConcFutTimeout):
                _stuck = [_futs_mc[_f] for _f in _futs_mc if not _f.done()]
                for _f_pending in _futs_mc:
                    if not _f_pending.done():
                        _f_pending.cancel()
                print(f'[Macro] ⏰ as_completed {inner_pool_timeout_s}s timeout,'
                      f'未完成={_stuck},保留 keys={list(_r.keys())}')
        finally:
            _pool_mc.shutdown(wait=False)

        # Failsafe + provenance — 即使全失敗也回傳 partial 標記(不回 None)
        _r.setdefault('_loaded_at',
                      _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        if not any(k for k in _r if not k.startswith('_')):
            _r['_all_failed'] = True
        # v18.353 PR-Q3 S-PROV-1 phase 19:集中注入 fetched_at 到每個 sub-dict。
        try:
            _now_macro_prov = _dt.datetime.utcnow().isoformat() + 'Z'
            for _k_prov, _v_prov in _r.items():
                if _k_prov.startswith('_'):
                    continue
                if isinstance(_v_prov, dict):
                    _v_prov.setdefault('fetched_at', _now_macro_prov)
        except Exception as _e_prov:
            print(f'[Macro/prov] inject fetched_at fail: {_e_prov}')
        print(f'[Macro] 完成 keys={[k for k in _r.keys() if not k.startswith("_")]}')
        return _r

    # ── outer trio 並發 ────────────────────────────────────
    # v18.341 PR-L1:200s global timeout + partial preserve + shutdown(wait=False)
    # 解決 v10.61.0「總經抓資料中途停掉」(per-job timeout 設太緊 cutoff)。
    _exc2 = ThreadPoolExecutor(max_workers=3)
    _res_map = {'m1b': None, 'bias': None, 'macro': None}
    try:
        _futs2 = {
            _exc2.submit(_job_m1b):   'm1b',
            _exc2.submit(_job_bias):  'bias',
            _exc2.submit(_job_macro): 'macro',
        }
        try:
            for _fut2 in as_completed(_futs2, timeout=global_timeout_s):
                _name2 = _futs2.get(_fut2, '?')
                try:
                    _res_map[_name2] = _fut2.result()
                except Exception as _e2:
                    print(f'[並發] ❌ {_name2}: {type(_e2).__name__}: {_e2}')
        except (TimeoutError, _ConcFutTimeout):
            _stuck2 = [_futs2[_f] for _f in _futs2 if not _f.done()]
            for _f_pend in _futs2:
                if not _f_pend.done():
                    _f_pend.cancel()
            print(f'[並發] ⏰ outer trio {global_timeout_s}s timeout,未完成={_stuck2},'
                  f'保留 partial={[k for k, v in _res_map.items() if v]}')
    finally:
        _exc2.shutdown(wait=False)

    # ── session_state writes:truthy guard(partial 場景不蓋 stale) ──
    # § 1:某 job timeout → 既有 stale 不被 None 蓋,user 看到「上次成功的值」而非
    # 「資料消失」(誠實顯示)
    if _res_map['m1b']:
        st.session_state['m1b_m2_info'] = _res_map['m1b']
    if _res_map['bias']:
        st.session_state['bias_info'] = _res_map['bias']
    if _res_map['macro']:
        st.session_state['macro_info'] = _res_map['macro']
