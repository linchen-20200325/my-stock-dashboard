"""src/services/fundamental_screener_service.py — 全台股基本面初篩 L3 service。

Phase 2 選股網「全市場基本面漏斗」的編排層:
  L1 fundamentals_snapshot_loader(讀 parquet 快照)
    → L2 fundamental_prescreen(4 項全過初篩)
    → 本 service(快取 + 對外 API)
    → L5 選股網(用存活池取代舊「估值前50 pool」)

對外 API:
  - get_fundamental_prescreen(refresh=): (全市場 prescreen df, meta)
  - get_fundamental_survivors(refresh=): (四項全過子集 df, meta)
  - get_survivor_ids(refresh=): list[str] 存活股號

§8.2 L3 service:合法組合 L1 loader + L2 純函式(對齊 macro_fetch_orchestrator /
etf_sector_service pattern)。快取集中在此(TTL_1DAY,季度資料日級足夠);refresh 統一
清 L1 + 本層 cache,避免 UI 端各自 .clear() 越權。
"""
from __future__ import annotations

# §8.2.A EX-CACHE-1:條件 import streamlit,無真 UI 呼叫(僅 @st.cache_data)。
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

import pandas as pd

from shared.fundamental_prescreen_thresholds import SNAPSHOT_COVERAGE_WARN_RATIO
from shared.ttls import TTL_1DAY
from src.compute.screener.fundamental_prescreen import (
    run_fundamental_prescreen,
    survivors_only,
)
from src.data.stock.fundamentals_snapshot_loader import load_fundamentals_snapshot


def _clear(fn) -> None:
    """清 @st.cache_data 函式的 cache(no-op fallback 環境無 .clear → 安全略過)。"""
    clear = getattr(fn, "clear", None)
    if callable(clear):
        clear()


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def _prescreen_cached() -> tuple[pd.DataFrame, dict]:
    """讀快照 → 跑初篩 → (全市場 prescreen df, meta)。快取集中點。"""
    current, prev, meta = load_fundamentals_snapshot()
    return run_fundamental_prescreen(current, prev), meta


def get_fundamental_prescreen(*, refresh: bool = False) -> tuple[pd.DataFrame, dict]:
    """全市場基本面初篩結果(每檔一列含 4 項 pass 欄 + survivor)+ meta。

    refresh=True → 清 L1 快照 cache + 本層 cache 重算(選股網「重新整理」按鈕用)。
    """
    if refresh:
        _clear(load_fundamentals_snapshot)
        _clear(_prescreen_cached)
    return _prescreen_cached()


def get_fundamental_survivors(*, refresh: bool = False) -> tuple[pd.DataFrame, dict]:
    """四項全過的存活池子集(依 eps 由大到小)+ meta。"""
    df, meta = get_fundamental_prescreen(refresh=refresh)
    return survivors_only(df), meta


def get_survivor_ids(*, refresh: bool = False) -> list[str]:
    """存活股號 list[str](選股網入池用)。"""
    surv, _ = get_fundamental_survivors(refresh=refresh)
    if surv is None or surv.empty:
        return []
    return [str(s) for s in surv["stock_id"].tolist()]


def describe_snapshot_coverage(meta: dict) -> dict:
    """快照涵蓋率診斷(§5 可觀測性):latest.json 的 coverage → 人話 + 是否可能尚缺慢公布。

    Returns: {text, possibly_incomplete, total, prev_total}
      - possibly_incomplete: 本季 total < 去年同季 total × SNAPSHOT_COVERAGE_WARN_RATIO
      - coverage 未記錄(舊版快照)→ text 標「未記錄」、possibly_incomplete=False(不誤報)
    """
    _cov = (meta or {}).get("coverage") or {}
    _total = _cov.get("total")
    if not _total:
        return {"text": "涵蓋率未記錄（快照為舊版格式，下一趟補抓後即顯示）",
                "possibly_incomplete": False, "total": None, "prev_total": None}
    _q = f"民國{meta.get('roc_year')}Q{meta.get('season')}"
    _asof = str(meta.get("updated_at", ""))[:10]
    _sii, _otc, _prev = _cov.get("sii"), _cov.get("otc"), _cov.get("prev_total")
    _incomplete = bool(_prev and _total < _prev * SNAPSHOT_COVERAGE_WARN_RATIO)
    _parts = [f"{_q} 快照涵蓋 {_total:,} 檔"]
    if _sii is not None and _otc is not None:
        _parts.append(f"（上市 {_sii:,} + 上櫃 {_otc:,}）")
    if _asof:
        _parts.append(f"，抓取於 {_asof}")
    _text = "".join(_parts)
    if _incomplete:
        _text += (f"；⚠️ 較去年同季 {_prev:,} 檔偏低，可能尚有慢公布公司未納入，"
                  "每季第二趟 cron（截止+約5週）會自動補抓")
    else:
        _text += "；每季兩趟抓取（截止+1週 / +5週）確保慢公布公司納入"
    return {"text": _text, "possibly_incomplete": _incomplete,
            "total": _total, "prev_total": _prev}


def get_snapshot_coverage_note(*, refresh: bool = False) -> str:
    """給 RS / 缺貨掃描 caption 用的一行涵蓋率字串。快照缺 → 空字串(不炸掃描)。"""
    try:
        _, meta = get_fundamental_prescreen(refresh=refresh)
        return describe_snapshot_coverage(meta)["text"]
    except Exception as _e:  # noqa: BLE001 — 涵蓋率不可用不炸掃描
        print(f"[fund_screener_service] 涵蓋率不可用:{type(_e).__name__}: {_e}")
        return ""


def gate_pool_by_fundamentals(
    pool_df: pd.DataFrame,
    code_col: str = "代碼",
    *,
    refresh: bool = False,
) -> tuple[pd.DataFrame, dict]:
    """外部候選池(含 code_col 股號欄)∩ 基本面存活池 → (過濾後 pool, info)。

    選股網漏斗第一關:把 TWSE 估值池收斂到「四項全過」的基本面存活股。

    info: {'survivors': int|None, 'matched': int|None, 'note': str}
      - survivors: 存活池大小(None=快照不可用)
      - matched:   交集後檔數(None=未套用閘門)
      - note:      給 UI 顯示的警語(''=正常)

    §1 fail-loud + UI 韌性:快照缺 / 存活池空 / 無 code_col → **不阻擋**,回原 pool +
    警語(讓 caller 退回估值篩選,不炸整頁、不造假)。
    """
    try:
        ids = set(get_survivor_ids(refresh=refresh))
    except Exception as _e:  # noqa: BLE001 — UI 韌性:初篩不可用不炸選股網
        print(f"[fund_screener_service] 基本面初篩不可用:{type(_e).__name__}: {_e}")
        return pool_df, {"survivors": None, "matched": None,
                         "note": f"（⚠️ 基本面快照載入失敗：{_e}；暫以估值篩選）"}
    if not ids:
        return pool_df, {"survivors": 0, "matched": None,
                         "note": "（⚠️ 基本面存活池為空，暫以估值篩選）"}
    if code_col not in pool_df.columns:
        return pool_df, {"survivors": len(ids), "matched": None,
                         "note": "（⚠️ 候選池缺股號欄，暫以估值篩選）"}
    out = pool_df[pool_df[code_col].astype(str).str.strip().isin(ids)]
    return out, {"survivors": len(ids), "matched": len(out), "note": ""}
