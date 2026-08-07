"""驗證下游 `data` 分支實際收到什麼 —— 不看我們「以為送了什麼」,看它「真的有什麼」。

為什麼需要這支
──────────────
`export_stock_db.py` 每天把 `stock.db` force-push 到 `data` 分支,供下游專案
`2026_strategy_0719` 讀取。B3(v19.181)為融資混口徑加了 sanity gate:整份序列
若有任一列換算後超出 §3.2 合理區間 [500, 10000] 億,**整張 margin 表不外送**
(不是只丟壞列 —— 那會產生「看起來連續、實際上 60% 日期憑空消失」的序列,
下游算 YoY 卻不知道,那才是靜默造假)。

但「gate 有沒有真的生效」不能靠讀 code 確認,只能看下游那份 db 裡到底有沒有那張表。
本檔直接從 git 取出 `data` 分支的 stock.db 檢查,不需要 clone 或切分支。

用法
────
    python scripts/verify_data_branch.py            # 讀 origin/data
    python scripts/verify_data_branch.py --ref data # 讀本地 data 分支

先跑 `git fetch origin` 確保 origin/data 是最新的。
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
import tempfile

#: §3.2 融資餘額合理區間(億)。與 shared/margin_schema.py 同源語意 —— 這裡刻意
#: 不 import,因為本檔要驗的是「下游收到什麼」,不該與被驗對象共用實作。
MARGIN_SANITY_MIN_YI = 500.0
MARGIN_SANITY_MAX_YI = 10_000.0


def _fetch_db(ref: str) -> str:
    """從 git 取出該 ref 的 stock.db 到暫存檔,回傳路徑。"""
    _r = subprocess.run(['git', 'show', f'{ref}:stock.db'],
                        capture_output=True)
    if _r.returncode != 0:
        _err = _r.stderr.decode('utf-8', 'replace').strip()
        raise SystemExit(f'❌ 取不到 {ref}:stock.db — {_err}\n'
                         f'   先跑 `git fetch origin` 或確認分支名。')
    if not _r.stdout:
        raise SystemExit(f'❌ {ref}:stock.db 是空的')
    _p = os.path.join(tempfile.gettempdir(), 'verify_data_branch.db')
    with open(_p, 'wb') as _f:
        _f.write(_r.stdout)
    return _p


def main() -> int:
    _ap = argparse.ArgumentParser(description=__doc__)
    _ap.add_argument('--ref', default='origin/data', help='git ref(預設 origin/data)')
    _a = _ap.parse_args()

    _path = _fetch_db(_a.ref)
    _size_mb = os.path.getsize(_path) / 1e6
    print(f'📦 {_a.ref}:stock.db  ({_size_mb:.2f} MB)')

    _con = sqlite3.connect(_path)
    _tables = sorted(r[0] for r in _con.execute(
        'select name from sqlite_master where type = ?', ('table',)))
    print(f'\n📋 表({len(_tables)}):')
    for _t in _tables:
        _n = _con.execute(f'select count(*) from "{_t}"').fetchone()[0]
        print(f'   {_t:24s} {_n:>8,} 列')

    # ── source_health:下游用來判斷哪幾維要降級 ──────────────────────
    if 'source_health' in _tables:
        print('\n🩺 source_health:')
        _cols = [d[1] for d in _con.execute('pragma table_info(source_health)')]
        for _row in _con.execute('select * from source_health'):
            print('   ' + ' | '.join(f'{c}={v}' for c, v in zip(_cols, _row)))
    else:
        print('\n⚠️ 無 source_health 表 —— 下游無從得知哪幾維缺料')

    # ── margin:B3 gate 的驗收重點 ──────────────────────────────────
    print('\n💰 margin(B3 sanity gate 驗收):')
    if 'margin' not in _tables:
        print('   ✅ 表不存在 —— gate 生效,60% 混口徑的序列沒有外送下游。')
        print('      這是**預期且正確**的結果(§1 寧缺勿錯),直到 parquet 重抓完成。')
        return 0

    _mcols = [d[1] for d in _con.execute('pragma table_info(margin)')]
    print(f'   ⚠️ 表存在,欄位={_mcols}')
    _val_col = next((c for c in _mcols if 'balance' in c.lower()
                     or '餘額' in c or 'yi' in c.lower()), None)
    if _val_col is None:
        print('   ❓ 找不到數值欄,無法自動判定口徑 —— 請人工檢查')
        return 1

    _bad = _con.execute(
        f'select count(*) from margin where "{_val_col}" <= ? or "{_val_col}" >= ?',
        (MARGIN_SANITY_MIN_YI, MARGIN_SANITY_MAX_YI)).fetchone()[0]
    _tot = _con.execute('select count(*) from margin').fetchone()[0]
    _sample = _con.execute(
        f'select * from margin where "{_val_col}" <= ? or "{_val_col}" >= ? limit 5',
        (MARGIN_SANITY_MIN_YI, MARGIN_SANITY_MAX_YI)).fetchall()
    print(f'   超出 [{MARGIN_SANITY_MIN_YI:.0f}, {MARGIN_SANITY_MAX_YI:.0f}] 億：'
          f'{_bad:,}/{_tot:,} 列')
    if _bad:
        print(f'   🔴 **gate 沒生效** —— 下游正在收到混口徑的融資數字。')
        print(f'      樣本：{_sample}')
        print('      這比缺料嚴重:下游會拿它算 YoY / 過熱門檻而不知道 60% 是張數。')
        return 1
    print('   ✅ 全列通過 sanity —— 若這是重抓後的結果,代表資料已修復。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
