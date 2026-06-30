"""shared/cache_layer.py — pickle 跨 session 快取 (L0 IO helper)。

v18.344 PR-N1 從 daily_checklist.py L33-73 抽出。原模組 4.5 起的 SSOT cache 邏輯,
本身與 daily_checklist 業務無關(只是 pickle wrapper),改 shared 後其他 L1 fetcher
亦可共用,避免重複實作。

依賴:
- data_config.PKL_DIR(預設 'cache/')— 透過參數或 import 取得

接口:
- _CACHE_SENTINEL: 區別「快取未命中」與「合法 None 值」的哨兵物件
- _pkl_get(key, ttl): 讀;未命中/過期返回 _CACHE_SENTINEL
- _pkl_put(key, value): 寫;return value(便於 fluent chain)
- _pkl_clear_all(): 強制刷新(全清);供「強制更新」按鈕用

§1 Fail Loud:讀失敗 stderr log(壞檔/版本不容)+ fallback 重抓。
"""
from __future__ import annotations

import os
import sys

# A2 v18.383:改 env 注入(STK_PKL_DIR),解原 `from src.config import PKL_DIR` L0↔L0 反向 import 設計味道。
# src/config/data_config.py 同步用 env(預設 '/tmp/stock_cache'),caller 介面不變。
_PKL_DIR = os.environ.get('STK_PKL_DIR', '/tmp/stock_cache')

_CACHE_SENTINEL = object()


def _pkl_get(key: str, ttl: int):
    """讀取 pickle 快取;未命中或過期返回 _CACHE_SENTINEL。

    v18.435 WONTFIX-翻案 Bug #1:原 `if _v_ is not None: return _v_` 違反 docstring
    宣告的 sentinel pattern — 把合法 cache 到的 None 當 miss 處理,觸發無謂重抓。
    pickle 載入成功即視為命中,不論 value 真假;sentinel 才是 miss 唯一信號。
    """
    import pickle as _pk_, time as _tm_
    _path = f'{_PKL_DIR}/{key}.pkl'
    try:
        if os.path.exists(_path) and _tm_.time() - os.path.getmtime(_path) < ttl:
            with open(_path, 'rb') as _f_:
                _v_ = _pk_.load(_f_)
            print(f'[Cache] ✅ {key} 命中（ttl={ttl}s）')
            return _v_
    except Exception as _e:
        # §1:壞 pickle / OSError 記錄但 fallback 重抓(_CACHE_SENTINEL 觸發呼叫端重新 fetch)
        print(f'[Cache] {key} pkl 載入失敗,重抓: {type(_e).__name__}: {_e}',
              file=sys.stderr)
    return _CACHE_SENTINEL


def _pkl_put(key: str, value):
    """寫入 pickle 快取(本次執行成功的資料)後 return value。"""
    import pickle as _pk_
    try:
        os.makedirs(_PKL_DIR, exist_ok=True)
        with open(f'{_PKL_DIR}/{key}.pkl', 'wb') as _f_:
            _pk_.dump(value, _f_)
    except Exception as _e:
        # 寫失敗不影響業務(只是下次冷啟動會重抓),log 以便 admin 追磁碟/權限
        print(f'[Cache] {key} pkl 寫入失敗: {type(_e).__name__}: {_e}',
              file=sys.stderr)
    return value


def _pkl_clear_all():
    """強制刷新:清除所有 pickle 快取檔案(供前端「強制更新」按鈕使用)。"""
    import glob as _glob_
    _removed = 0
    for _f_ in _glob_.glob(f'{_PKL_DIR}/*.pkl'):
        try:
            os.remove(_f_)
            _removed += 1
        except OSError as _e:
            print(f'[Cache] 移除 {_f_} 失敗: {_e}', file=sys.stderr)
    print(f'[Cache] 🗑️ 已清除 {_removed} 個快取檔案')
