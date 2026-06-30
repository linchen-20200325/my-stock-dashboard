"""src/services/macro_fetch_orchestrator.py — 7-job 並行 fetch orchestrator(P3-D4 v18.389 抽出)。

從 tab_macro.render_tab_macro 內 spinner-internal 區塊抽出(原 line 607-840)。

職責(L3 service):
- 並行 fetch 7 個資料源:intl/tw/tech/inst/margin/adl/li
- ThreadPoolExecutor with per-job timeout + global as_completed timeout
- shutdown(wait=False) + cancel_futures(避免 stuck thread 拖外層)
- FinMind inst rescue(API quota 用罄 / TWSE BFI82U 全敗時 fallback)
- importlib.reload(leading_indicators)(主執行緒一次性,worker thread 只 call build_leading_fast)

不負責(留 caller / tab_macro):
- st.spinner / st.empty UI 呈現
- st.session_state 寫入(cl_data / cl_ts / _last_inst / _last_margin / li_latest)
- ADL debug message UI 顯示(透過 bundle 回傳,caller 自行 set/pop)

§8.2 分層:L5 UI Tab → L3 Service(本檔)→ L1 Data(fetch_*)。
§1 Fail Loud:任何 fetcher 失敗收 None,FinMind rescue 失敗 print + 維持 None,不靜默吞。
"""
from __future__ import annotations

from src.config import FINMIND_API_URL  # Batch 10b v18.412 SSOT

import datetime as _dt
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed


def fetch_macro_bundle(
    *,
    load_heavy: bool,
    prev_cl_data: dict,
    fm_token: str,
    li_token: str,
    bps_session,
    intl_map: dict,
    tw_map: dict,
    tech_map: dict,
    fetch_single,
    fetch_institutional,
    fetch_margin_balance,
    fetch_adl,
) -> dict:
    """並行 fetch 7 個資料源 + FinMind inst rescue,回傳 unified bundle(無 session_state 副作用)。

    參數:
        load_heavy: bool       是否抓重資料(inst/margin/adl/li);冷啟動 False → 沿用 prev_cl_data
        prev_cl_data: dict     上一輪 cl_data(冷啟動用)
        fm_token: str          FinMind token(inst rescue 用)
        li_token: str          先行指標用 token
        bps_session: Session   app._bps() 回傳的 requests session(FinMind inst rescue 用)
        intl_map/tw_map/tech_map: dict  各市場 ticker 對照(name → symbol)
        fetch_single/...:      L1 fetcher callables(由 caller 注入,避 L3→L1 import 循環)

    回傳:
        {
            'intl_raw': dict, 'tw_raw': dict, 'tech_raw': dict,
            'inst': dict, 'inst_date': str | None, 'margin': float | None,
            'df_adl_raw': DataFrame | None, 'df_li_a': DataFrame | None,
            'adl_debug_msg': str | None,  # 失敗時 caller setdefault 到 session_state
            'elapsed_s': float,
        }
    """
    _t_start = _time.time()

    # ── 並發任務定義 ────────────────────────────────────
    # v18.193 perf:3 個 job 內部從 ticker 序列改為內層 ThreadPoolExecutor 並行
    # (原 N×fetch_single 序列 → max(t);fetch_single /tmp pickle 30 分鐘 cache 不變、
    # DX-Y.NYB→DX=F→UUP 備援邏輯不變)
    def _parallel_fetch(_mp, **_kw):
        _max_w = max(1, len(_mp))
        with ThreadPoolExecutor(max_workers=_max_w) as _e_in:
            _f_in = {_e_in.submit(fetch_single, _s, **_kw): _n for _n, _s in _mp.items()}
            return {_f_in[_ft]: _ft.result() for _ft in _f_in}

    def _job_intl():
        return _parallel_fetch(intl_map)

    def _job_tw():
        # 9mo ≈ 195 交易日,確保 ^TWII 有足夠 bars 計算 MA120(需 120 筆)
        return _parallel_fetch(tw_map, period='9mo')

    def _job_tech():
        return _parallel_fetch(tech_map)

    def _job_inst():
        return fetch_institutional()

    def _job_margin():
        try:
            return fetch_margin_balance()
        except Exception as _em:
            print(f'[融資] ❌ {_em}')
            return None

    def _job_adl():
        return fetch_adl(days=60, token=fm_token)

    # v18.331 (2-C):先行指標併入平行池。原 v8 因 Colab worker thread 中 requests
    # 受阻而移出池、改主流程序列呼叫(拖慢 ~15-55s);現平台為 Streamlit Cloud,
    # 池內 inst/margin/adl 等 requests job 運作正常,該平台限制已不適用。
    # import + reload 留在主執行緒(importlib.reload 非 thread-safe),worker thread
    # 內只呼叫純抓取 build_leading_fast(不碰 UI)。失敗時下游既有 fallback(保留舊
    # li_latest)兜底,最壞只是先行指標顯示舊資料,不致崩潰。
    _li_build_fn = None
    try:
        import importlib as _il_li
        from src.data.macro import leading_indicators as _li_mod
        _il_li.reload(_li_mod)
        _li_build_fn = _li_mod.build_leading_fast
        print(f'[先行指標] v={getattr(_li_mod, "LI_VERSION", "?")} token={bool(li_token)}(併池)')
    except Exception as _e_li_imp:
        print(f'[先行指標] ❌ import 失敗 {type(_e_li_imp).__name__}: {_e_li_imp}')

    def _job_li():
        if _li_build_fn is None:
            return None
        return _li_build_fn(days=14, token=li_token)

    # ── 並發執行(yfinance 最慢,先丟進去)─────────────
    # [Phase 2] 輕量任務(永遠跑,~30s 內完成)
    _jobs = {
        'intl': _job_intl,
        'tw': _job_tw,
        'tech': _job_tech,
    }
    _job_timeouts = {
        'intl': 30, 'tw': 30, 'tech': 30,
    }
    # [Phase 2] 重量任務(按鈕觸發或手動 refresh 才跑)
    if load_heavy:
        _jobs.update({
            'inst': _job_inst,
            'margin': _job_margin,
            'adl': _job_adl,
            'li': _job_li,
        })
        _job_timeouts.update({
            'inst': 25,
            'margin': 25,
            'adl': 55,
            'li': 80,
        })
    _results = {}
    # [BUG FIX] as_completed global timeout = max(per-job) + 20s 餘裕
    # li job 內部 thread join(timeout=80),global timeout < 80 會 TimeoutError 崩潰
    # try/except 包住迴圈,確保其他 job 結果不因 li 超時而丟失
    # shutdown(wait=False) — 消除 `with TPE` 阻塞 7-20 分鐘的問題
    _AS_COMPLETED_TIMEOUT = max(_job_timeouts.values()) + 20
    _exc = ThreadPoolExecutor(max_workers=len(_jobs))
    _futs = {_exc.submit(fn): name for name, fn in _jobs.items()}
    try:
        try:
            for _fut in as_completed(_futs, timeout=_AS_COMPLETED_TIMEOUT):
                name = _futs[_fut]
                _t_limit = _job_timeouts.get(name, 20)
                try:
                    _results[name] = _fut.result(timeout=_t_limit)
                    print(f'[並發] ✅ {name} ({_time.time()-_t_start:.1f}s)')
                except Exception as _fe:
                    _results[name] = None
                    print(f'[並發] ❌ {name}: {type(_fe).__name__}: {_fe}')
        except TimeoutError:
            print(f'[並發] ⚠️ as_completed {_AS_COMPLETED_TIMEOUT}s 超時,補救已完成結果')
            for _fut, _name in _futs.items():
                if _name not in _results:
                    if _fut.done():
                        try:
                            _results[_name] = _fut.result(timeout=1)
                            print(f'[並發] ✅ {_name} 補救成功')
                        except Exception:
                            _results[_name] = None
                    else:
                        _results[_name] = None
                        print(f'[並發] ⏰ {_name} 確認超時')
    finally:
        # 立即取消未開始任務,不等執行中的 thread(避免 with-block wait=True 卡 240s)
        try:
            _exc.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            _exc.shutdown(wait=False)  # Python < 3.9
    # 補齊所有未收到結果的 job
    for _name in _jobs:
        if _name not in _results:
            _results[_name] = None
            print(f'[並發] ⏰ {_name} 超時')

    # ── 解包結果 ────────────────────────────────────────
    intl_raw = _results.get('intl') or {}
    tw_raw = _results.get('tw') or {}
    tech_raw = _results.get('tech') or {}

    _adl_debug_msg = None
    if load_heavy:
        inst_res = _results.get('inst') or (None, None)
        inst, inst_date = (inst_res if isinstance(inst_res, tuple) else (inst_res, None))
        # 如果 inst 是空的,用 FinMind TaiwanStockTotalInstitutionalInvestors 補救
        if not inst:
            print('[並發] inst 為空,用 FinMind 補救...')
            try:
                import pandas as _pd
                _start_i = (_dt.date.today() - _dt.timedelta(days=5)).strftime('%Y-%m-%d')
                _ri = bps_session.get(
                    FINMIND_API_URL,
                    params={'dataset': 'TaiwanStockTotalInstitutionalInvestors',
                            'start_date': _start_i, 'token': fm_token},
                    headers={'Authorization': f'Bearer {fm_token}'},
                    timeout=15)
                _ji = _ri.json()
                print(f'[FinMind-Inst] status={_ji.get("status")} rows={len(_ji.get("data",[]))}')
                if _ji.get('status') == 200 and _ji.get('data'):
                    _df_i = _pd.DataFrame(_ji['data'])
                    _ld_i = _df_i['date'].max()
                    _df_i = _df_i[_df_i['date'] == _ld_i]
                    _df_i['buy'] = _pd.to_numeric(_df_i.get('buy', 0), errors='coerce').fillna(0)
                    _df_i['sell'] = _pd.to_numeric(_df_i.get('sell', 0), errors='coerce').fillna(0)
                    _df_i['_net'] = ((_df_i['buy'] - _df_i['sell']) / 1e8).round(2)
                    # FinMind name 欄為英文 key(Foreign_Investor / Investment_Trust / Dealer_*)
                    # 與 tw_macro.py:151 / hot_money.py:157 一致採英文匹配,中文為向下相容
                    inst = {}
                    for _nm, _net in zip(_df_i['name'].astype(str), _df_i['_net']):
                        _nl = _nm.lower()
                        if 'foreign' in _nl or '外資' in _nm:
                            inst.setdefault('_f', 0)
                            inst['_f'] = round(inst['_f'] + _net, 2)
                        elif 'investment_trust' in _nl or '投信' in _nm:
                            inst['投信'] = {'net': _net}
                        elif 'dealer' in _nl or '自營' in _nm:
                            inst.setdefault('_d', 0)
                            inst['_d'] = round(inst['_d'] + _net, 2)
                    if '_f' in inst:
                        inst['外資及陸資'] = {'net': inst.pop('_f')}
                    if '_d' in inst:
                        inst['自營商'] = {'net': inst.pop('_d')}
                    inst_date = _ld_i
                    print(f'[FinMind-Inst] ✅ {inst}')
            except Exception as _ei:
                print(f'[FinMind-Inst] ❌ {_ei}')
        margin = _results.get('margin')
        df_adl_raw = _results.get('adl')
        if df_adl_raw is None:
            _adl_debug_msg = ('來源均無回應(yfinance + TWSE MI_INDEX),'
                              '詳見 Colab [ADL] 輸出')
        df_li_a = _results.get('li')
        if df_li_a is not None and not (hasattr(df_li_a, 'empty') and df_li_a.empty):
            print(f'[先行指標] ✅ 併池成功 {len(df_li_a)} 筆')
        else:
            print('[先行指標] ⚠️ 併池回空/None — 下游保留舊快取')
    else:
        # 冷啟動跳過重資料:沿用 prev_cl_data 或 None
        inst = prev_cl_data.get('inst') or {}
        inst_date = prev_cl_data.get('inst_date')
        margin = prev_cl_data.get('margin')
        df_adl_raw = prev_cl_data.get('adl')
        df_li_a = None  # caller 自行從 session_state.get('li_latest') 取
        print('[Phase 2] 冷啟動跳過 inst/margin/adl/li(按鈕載入)')

    _elapsed_s = _time.time() - _t_start
    print(f'[並發] 🎉 全部完成 共 {_elapsed_s:.1f}s')

    return {
        'intl_raw': intl_raw,
        'tw_raw': tw_raw,
        'tech_raw': tech_raw,
        'inst': inst,
        'inst_date': inst_date,
        'margin': margin,
        'df_adl_raw': df_adl_raw,
        'df_li_a': df_li_a,
        'adl_debug_msg': _adl_debug_msg,
        'elapsed_s': _elapsed_s,
    }
