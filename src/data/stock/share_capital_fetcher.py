"""src/data/stock/share_capital_fetcher.py — 個股股本 L1 fetcher(v18.412 R-FETCH-1).

從 src/ui/tabs/tab_stock.py:71 搬出(原 `_fetch_share_capital`),修正 §8.2 違憲:
原為 UI 層(L5)藏 L1 fetcher,完整 FinMind REST API 呼叫 + cache 邏輯。

職責:抓 FinMind TaiwanStockBalanceSheet 最新一季的「股本」(普通股股本)。
供龍頭預警區(stock_sections.section_dragon_alert)計算「合約負債 / 資本支出 對股本
比」真實比例 — 取代舊版 >0 假判斷。

§8.2 layer:L1 Data(EX-CACHE-1 letter-compliant try/import streamlit fallback)。
S-PROV-1 phase 19:success-path provenance log 保留(stderr)。
"""
from __future__ import annotations

# EX-CACHE-1 letter-compliant: 純 py 環境(無 Streamlit lifecycle)時 fallback no-op
try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa

from shared.ttls import TTL_1DAY
from src.config import FINMIND_API_URL  # Batch 10b v18.412 SSOT


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def fetch_share_capital(sid: str) -> float:
    """FinMind 抓最新一季股本(普通股股本),回傳原始元值;失敗回 0。

    供龍頭預警區(section_dragon_alert)計算「合約負債/資本支出 對 股本比」真實比例
    (取代舊版 >0 假判斷)。Cache TTL 1 日(股本變動極低頻)。

    Args:
        sid: 股票代碼(如 "2330")

    Returns:
        float 股本值(元;0.0 代表抓取失敗或無資料)
    """
    import os as _os_sc
    import datetime as _dt_sc
    import requests as _rq_sc
    try:
        _tok = _os_sc.environ.get('FINMIND_TOKEN', '')
        _start = (_dt_sc.date.today() - _dt_sc.timedelta(days=540)).strftime('%Y-%m-%d')
        _p = {'dataset': 'TaiwanStockBalanceSheet', 'data_id': sid, 'start_date': _start}
        if _tok:
            _p['token'] = _tok
        _r = _rq_sc.get(FINMIND_API_URL,
                        params=_p, timeout=15)
        _data = _r.json().get('data', []) if _r.status_code == 200 else []
        if not _data:
            return 0.0
        _dates = sorted({_row.get('date', '') for _row in _data}, reverse=True)
        _latest = _dates[0] if _dates else ''
        for _row in _data:
            if _row.get('date') != _latest:
                continue
            _t = str(_row.get('type', ''))
            _nm = str(_row.get('origin_name', ''))
            if (_t in ('CommonStock', 'OrdinaryShare', 'ShareCapital')
                    or '股本' in _t or '普通股股本' in _nm or '股本' in _nm):
                try:
                    _v = float(str(_row.get('value', 0) or 0).replace(',', ''))
                    if _v > 0:
                        # v18.356 PR-Q5b S-PROV-1 phase 19:success-path provenance
                        try:
                            import sys as _sys_sc
                            print(f'[fetch_share_capital] sid={sid} '
                                  f'source=FinMind:TaiwanStockBalanceSheet '
                                  f'fetched_at={_dt_sc.datetime.utcnow().isoformat()}Z '
                                  f'result=float:{_v}', file=_sys_sc.stderr)
                        except Exception:
                            pass
                        return _v
                except (TypeError, ValueError):
                    continue
        return 0.0
    except Exception as _e:
        import sys as _sys
        print(f'[fetch_share_capital] swallow: {type(_e).__name__}: {_e}', file=_sys.stderr)
        return 0.0
