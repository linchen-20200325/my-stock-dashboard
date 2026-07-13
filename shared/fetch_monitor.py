"""shared/fetch_monitor.py — @monitored fetcher 自我登錄 + 真實抓取狀態記錄 (v19.96 批次4 Item1).

孤兒 bug 根因（§8.1 設計 user 核准）:診斷頁靠 3 份**手寫**清單（DATA_REGISTRY /
data_registry_scanner / health_inspector _g_add）,新 fetcher 漏登即隱形——B5 v19.75
（籌碼集中度等 3 項未登錄,抓壞診斷不亮紅）+ S13 v19.78（patch 誤刪 B5 補登項）兩次實案。

本模組（最小版）:
- `@monitored(name, ...)`:**import 時**自我登錄 metadata（從未被呼叫也顯示「未執行」,
  不再隱形）;每次**真實**呼叫記錄 status / rows / 耗時。放置順序:@st.cache_data /
  @_ttl_cache 之「內」（最貼函式）→ cache hit 不觸發,last_* 一律代表最後一次真實外抓。
- `get_monitor_registry()`:診斷頁 accessor（pass-through 讀,EX-PASSTHRU-1 精神）。
- `find_orphans(present_keys)`:Item2 孤兒 set-diff——已監控且宣告 registry_key,
  但該 key 不在 session_state['data_registry'] 的 fetcher（= 有在抓但診斷清單沒它的列）。

§1 Fail Loud:fetcher raise → 記 failed 後**原樣 re-raise**（不吞）;registry 寫入
失敗絕不影響 fetch 主流程（fetch 永遠優先,只 stderr log）。

分層:純 Python（functools / datetime / time）,零 streamlit / 零 I/O — 置 shared/
（同 cache_layer.py / app_cache.py 慣例）,被 L1 fetcher import,無迴圈依賴。
（§8.1 原設計寫 src/data/core/;因該包 __init__ 急載重量級 data_loader,
 依 shared/cache_layer 先例改置此,依賴方向更乾淨——placement refinement 已於
 STATE.md v19.96 註記。）
"""
from __future__ import annotations

import functools
import sys
import time as _time
from datetime import datetime, timedelta, timezone

_TW_TZ = timezone(timedelta(hours=8))   # §4.5 repo 慣例（app.py:47）

# name → {category, frequency, registry_key,
#          last_status('未執行'|'ok'|'failed'), last_error, last_rows, last_ms,
#          last_called_at('YYYY-MM-DD HH:MM:SS' TW)}
_MONITOR_REGISTRY: dict[str, dict] = {}


def _infer_rows(result):
    """盡力推 rows:有 len 的（DataFrame/list/dict/str…）→ len;None → 0;
    其他（scalar 等）→ None（未知,不偽造）。"""
    if result is None:
        return 0
    try:
        return int(len(result))
    except TypeError:
        return None


def _record(name: str, status: str, *, rows=None, error=None, ms=None) -> None:
    """寫回 registry;任何失敗只 stderr log 不拋（fetch 主流程優先）。"""
    try:
        ent = _MONITOR_REGISTRY.setdefault(name, {})
        ent.update(last_status=status, last_rows=rows, last_error=error,
                   last_ms=round(ms, 1) if ms is not None else None,
                   last_called_at=datetime.now(_TW_TZ).strftime('%Y-%m-%d %H:%M:%S'))
    except Exception as e:
        print(f'[fetch_monitor] record {name} fail: {type(e).__name__}: {e}',
              file=sys.stderr)


def monitored(name: str, *, category: str = '', frequency: str = 'daily',
              registry_key: str | None = None, success_check=None):
    """裝飾 L1 fetcher:import 時登 metadata,真實呼叫時記錄狀態。

    Args:
        name: 監控顯示名（建議 = 函式名,好 grep）。
        category / frequency: 診斷分組顯示用。
        registry_key: 此 fetcher 資料最終落在 session_state['data_registry'] 的
            key（供 find_orphans set-diff）;不確定就留 None（誠實跳過,不猜）。
        success_check: v19.118 選填 callable(result) -> bool。**預設 None = 舊行為**
            （不拋例外即記 'ok'）。給了就用它判定成敗——治「fetcher 不拋例外、但回
            `value=None` 診斷 dict」的**假綠燈**（如 `fetch_tw_pmi` 8 源全敗仍回 dict
            → 舊版恆綠，誤導 user 以為有值）。回 False → 記 'failed'（診斷亮 🔴）。
            check 本身拋例外 → 保守記 'ok'（不因判定器壞掉誤殺）。
    """
    def deco(fn):
        try:
            _MONITOR_REGISTRY[name] = {
                'category': category, 'frequency': frequency,
                'registry_key': registry_key,
                'last_status': '未執行', 'last_error': None,
                'last_rows': None, 'last_ms': None, 'last_called_at': None,
            }
        except Exception as e:   # 登錄失敗不阻擋模組 import
            print(f'[fetch_monitor] register {name} fail: {type(e).__name__}: {e}',
                  file=sys.stderr)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = _time.perf_counter()
            try:
                result = fn(*args, **kwargs)
            except Exception as e:
                _record(name, 'failed', error=f'{type(e).__name__}: {e}',
                        ms=(_time.perf_counter() - t0) * 1000)
                raise                                   # §1 不吞,原樣上拋
            # v19.118:success_check 治假綠燈——回 dict 不拋例外 ≠ 真的有值
            _ok = True
            _err = None
            if success_check is not None:
                try:
                    _ok = bool(success_check(result))
                except Exception:
                    _ok = True   # 判定器自身壞掉不誤殺成 failed（保守）
                if not _ok:
                    _err = 'success_check=False（回應無有效值）'
            _record(name, 'ok' if _ok else 'failed', rows=_infer_rows(result),
                    error=_err, ms=(_time.perf_counter() - t0) * 1000)
            return result
        return wrapper
    return deco


def get_monitor_registry() -> dict[str, dict]:
    """診斷頁 accessor（回 shallow copy,防 UI 端誤改內部狀態）。"""
    return {k: dict(v) for k, v in _MONITOR_REGISTRY.items()}


def find_orphans(present_keys) -> list[str]:
    """Item2 孤兒 set-diff。

    Args:
        present_keys: session_state['data_registry'] 的 keys（任何 iterable / None）。

    Returns:
        孤兒 fetcher 名單 — 已監控且宣告 registry_key,但 key 不在 present_keys
        （registry_key=None 者跳過:不知道落點就不猜,§1）。
    """
    present = set(present_keys or [])
    return [n for n, ent in _MONITOR_REGISTRY.items()
            if ent.get('registry_key') and ent['registry_key'] not in present]
