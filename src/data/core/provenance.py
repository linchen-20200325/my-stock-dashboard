"""src/data/core/provenance.py — §2.2 provenance audit trail SSOT(L1 shared)。

P2-1 v18.380 深層拔毒:統一原本 3 處同名 _prov_log(簽名不一)。

用於 scalar/dict/str return 的 fetcher;DataFrame return 應另用 df.attrs(schema-additive)。
"""
from __future__ import annotations

import sys
import datetime


def prov_log(fn_name: str, source: str, result_summary: str, ticker: str = '') -> None:
    """統一 provenance log。ticker 為選填(nas_server 等無 ticker 場景留空)。"""
    try:
        _now = datetime.datetime.utcnow().isoformat() + 'Z'
        if ticker:
            print(f'[{fn_name}] ticker={ticker} source={source} fetched_at={_now} '
                  f'result={result_summary}', file=sys.stderr)
        else:
            print(f'[{fn_name}] source={source} fetched_at={_now} '
                  f'result={result_summary}', file=sys.stderr)
    except Exception:
        pass
