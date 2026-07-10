"""shared/app_cache.py — app.py pickle 快取 helper(v18.404 B3-α 從 app.py 抽出)。

§-1 對齊 user 未完成項目 #2 — B3-α 第 1 phase(LOW risk,~50 LOC)。

從 app.py L247-273 抽出 3 個 helper:
- `_cache_key(prefix, sid, extra='')`:組 cache file path(MD5 hash + 當日 date)
- `_load_cache(prefix, sid, extra='', ttl_hours=6)`:讀 pickle(過 TTL 視為 stale)
- `_save_cache(prefix, sid, data, extra='')`:寫 pickle(silent fail OK,cache 失敗不該炸 caller)

設計考量:
- L0 工具層,無 Streamlit 依賴
- CACHE_DIR 統一用 `_CACHE_DIR` 常數(同 app.py 原 inline)
- silent except 屬 cache pattern 合理(§-1 例外:讀寫快取失敗 ≠ 業務邏輯失敗)
- 對應 app.py 既有 thin shim 維持原 caller API

對齊 shared/cache_layer.py(daily_checklist 用)pattern,但本檔是 app.py 自有
pickle cache,key 含「當日 date」自然 TTL,與 cache_layer 平行(不共用)。
"""
from __future__ import annotations

import datetime
import hashlib
import os
import pickle
import time

# 對齊 app.py L247 原值;D14b v19.75(review):與 cache_layer._PKL_DIR 同語意
# (env STK_PKL_DIR 優先 + tempfile 可攜預設;Linux 結果不變 = /tmp/stock_cache)
import tempfile as _tf_ac
_CACHE_DIR = os.environ.get('STK_PKL_DIR') or os.path.join(_tf_ac.gettempdir(), 'stock_cache')
os.makedirs(_CACHE_DIR, exist_ok=True)


def _cache_key(prefix: str, sid: str, extra: str = '') -> str:
    """組 pickle cache file path:MD5 hash on `prefix_sid_extra_YYYY-MM-DD`。

    當日 date 含於 key → 跨日自動失效(無需 TTL)。
    """
    raw = f'{prefix}_{sid}_{extra}_{datetime.date.today()}'
    return os.path.join(_CACHE_DIR, hashlib.md5(raw.encode()).hexdigest() + '.pkl')


def _load_cache(prefix: str, sid: str, extra: str = '', ttl_hours: int = 6):
    """讀 pickle cache;超 TTL hours → 視為過期回 None。

    silent fail 是 cache pattern 合理選擇 — 載入失敗 caller 自然走重抓 path。
    """
    path = _cache_key(prefix, sid, extra)
    if os.path.exists(path):
        age = (time.time() - os.path.getmtime(path)) / 3600
        if age < ttl_hours:
            try:
                with open(path, 'rb') as f:
                    return pickle.load(f)
            except Exception:  # noqa: BLE001 — cache fail-safe
                pass
    return None


def _save_cache(prefix: str, sid: str, data, extra: str = '') -> None:
    """寫 pickle cache;silent fail(寫失敗不該炸 caller)。"""
    path = _cache_key(prefix, sid, extra)
    try:
        with open(path, 'wb') as f:
            pickle.dump(data, f)
    except Exception:  # noqa: BLE001 — cache fail-safe
        pass
