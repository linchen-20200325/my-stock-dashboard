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


# ════════════════════════════════════════════════════════════════
# 選股網「從優選池挑候選」— 依排序角度排出候選清單（v19.74 重設計）
# ════════════════════════════════════════════════════════════════
# UI 下拉 SSOT：label → angle key（與 build_candidate_frame 對應，禁止 UI 端寫死 key）。
SCREEN_ANGLE_LABELS: dict[str, str] = {
    "估值便宜（本益比低）": "pe_low",
    "高 EPS（獲利高）": "eps_high",
    "缺貨動能（需先於下方掃描）": "shortage",
    "抗跌 RS 強（需先於下方掃描）": "rs_leader",
}


def build_candidate_frame(
    survivors_df: pd.DataFrame,
    *,
    angle: str,
    top_n: int = 300,
    pe_map: dict | None = None,
    name_map: dict | None = None,
    shortage_rows: list[dict] | None = None,
    rs_rows: list[dict] | None = None,
) -> tuple[pd.DataFrame, str]:
    """從基本面存活池，依「排序角度」排出候選 DataFrame（含 '代碼' 欄，供 picker 勾選）。

    純函式（所有資料由 caller 傳入，無 I/O / session_state）：
      - pe_low   : 依 pe_map 本益比由低到高（無 PE 排最後）
      - eps_high : 依存活池 eps 由高到低
      - shortage : 依 shortage_rows 缺貨分數（存活池 ∩ 掃描結果）；無掃描結果 → 空 + note
      - rs_leader: 依 rs_rows RS(σ)（存活池 ∩ 掃描結果）；無掃描結果 → 空 + note

    Returns: (df, note)。df 欄：代碼 / 名稱 / <角度指標>。df 空時 note 說明原因（§1/§5）。
    """
    pe_map = pe_map or {}
    name_map = name_map or {}
    if survivors_df is None or survivors_df.empty or "stock_id" not in survivors_df.columns:
        return pd.DataFrame(columns=["代碼", "名稱"]), "基本面存活池為空（季快照未就緒，請先跑 Update Fundamentals）。"

    ids = [str(s) for s in survivors_df["stock_id"].tolist()]
    _id_set = set(ids)
    eps_map = (dict(zip(ids, survivors_df["eps"].tolist()))
               if "eps" in survivors_df.columns else {})

    def _as_num(v, default: float) -> float:
        """None / NaN / 非數字 → default（避免 sorted 比較 None 崩潰；缺值排最後）。"""
        try:
            f = float(v)
        except (TypeError, ValueError):
            return default
        return default if f != f else f  # NaN

    metric_label = ""
    note = ""
    if angle == "pe_low":
        metric_label = "本益比"
        # 本益比由低到高；無 PE（OTC 常見，不在 TWSE 估值表）→ +inf 排最後
        ranked = sorted(ids, key=lambda c: _as_num(pe_map.get(c), float("inf")))
        metric = {c: pe_map.get(c) for c in ranked}
    elif angle == "eps_high":
        metric_label = "EPS"
        # EPS 由高到低；無 EPS → -inf → 排最後
        ranked = sorted(ids, key=lambda c: -_as_num(eps_map.get(c), float("-inf")))
        metric = {c: eps_map.get(c) for c in ranked}
    elif angle == "shortage":
        metric_label = "缺貨分數"
        if not shortage_rows:
            return (pd.DataFrame(columns=["代碼", "名稱"]),
                    "『缺貨動能』排序需先在下方「🔎 進階主題選股」掃描缺貨股，掃完會自動帶上來。")
        ranked = [str(r.get("代碼", "")) for r in shortage_rows
                  if str(r.get("代碼", "")) in _id_set]
        metric = {str(r.get("代碼", "")): r.get("缺貨分數") for r in shortage_rows}
    elif angle == "rs_leader":
        metric_label = "RS(σ)"
        if not rs_rows:
            return (pd.DataFrame(columns=["代碼", "名稱"]),
                    "『抗跌 RS』排序需先在下方「🔎 進階主題選股」掃描抗跌股，掃完會自動帶上來。")
        ranked = [str(r.get("代碼", "")) for r in rs_rows
                  if str(r.get("代碼", "")) in _id_set]
        metric = {str(r.get("代碼", "")): r.get("RS(σ)") for r in rs_rows}
    else:
        ranked, metric = ids, {}

    ranked = ranked[: int(top_n)]
    if not ranked:
        return (pd.DataFrame(columns=["代碼", "名稱"]),
                "此角度在存活池內無可排序標的（掃描結果與存活池無交集）。")
    out = pd.DataFrame({
        "代碼": ranked,
        "名稱": [str(name_map.get(c, "")) for c in ranked],
    })
    if metric_label:
        out[metric_label] = [metric.get(c) for c in ranked]
    return out, note


# ── 綜合評分（多因子複選；v19.88）────────────────────────────────
# 每個勾選因子給 0-100 分位分數（各因子在存活池內排百分位），取平均為綜合分，降冪排序。
# 缺料的因子該股記 0 分（不造假、不猜）。籌碼技術×6 因需逐檔深抓，屬 ③ 深篩關（不入綜合分）。
def _percentile_scores(ids: list[str], value_map: dict, *, higher_better: bool) -> dict:
    """{id: 0-100 百分位分}。有值者排百分位（最佳=100），缺值/NaN/非數字 → 0。"""
    valid: dict[str, float] = {}
    for _i in ids:
        _v = value_map.get(_i)
        try:
            _f = float(_v)
        except (TypeError, ValueError):
            continue
        if _f == _f:  # 非 NaN
            valid[_i] = _f
    if not valid:
        return {i: 0.0 for i in ids}
    if len(valid) == 1:
        return {i: (100.0 if i in valid else 0.0) for i in ids}
    _s = pd.Series(valid)
    # higher_better=True → 值越大分越高（ascending=True 使最大值 pct=1.0）；
    # pe_low（higher_better=False）→ 值越小分越高。
    _pct = _s.rank(pct=True, ascending=higher_better)
    _sc = (_pct * 100).round(1).to_dict()
    return {i: float(_sc.get(i, 0.0)) for i in ids}


def composite_rank_candidates(
    survivors_df: pd.DataFrame,
    *,
    factors: list[str],
    top_n: int = 300,
    pe_map: dict | None = None,
    name_map: dict | None = None,
    shortage_rows: list[dict] | None = None,
    rs_rows: list[dict] | None = None,
) -> tuple[pd.DataFrame, str]:
    """從存活池，依【複選因子】的綜合評分排序 → 候選 DataFrame（含 '代碼' 欄）。

    factors ⊆ {'pe_low','eps_high','shortage','rs_leader'}（籌碼技術×6 屬 ③ 深篩，不在此）。
    綜合分 = 各勾選因子百分位分（0-100）的平均。缺料因子該股記 0（§1 不造假）。

    Returns: (df[代碼/名稱/綜合分/各因子分], note)。
      - factors 空 → 空 + 「請至少勾一個因子」
      - 勾了缺貨/RS 但尚未掃描 → note 提示（該因子暫全記 0，不擋其他因子）
    """
    pe_map = pe_map or {}
    name_map = name_map or {}
    if survivors_df is None or survivors_df.empty or "stock_id" not in survivors_df.columns:
        return pd.DataFrame(columns=["代碼", "名稱"]), "基本面存活池為空（季快照未就緒）。"
    if not factors:
        return pd.DataFrame(columns=["代碼", "名稱"]), "請至少勾選一個選股因子。"

    ids = [str(s) for s in survivors_df["stock_id"].tolist()]
    eps_map = (dict(zip(ids, survivors_df["eps"].tolist()))
               if "eps" in survivors_df.columns else {})
    shortage_map = {str(r.get("代碼", "")): r.get("缺貨分數") for r in (shortage_rows or [])}
    rs_map = {str(r.get("代碼", "")): r.get("RS(σ)") for r in (rs_rows or [])}

    # (value_map, higher_better, 顯示欄名)
    _cfg = {
        "pe_low":    (pe_map,       False, "估值分"),
        "eps_high":  (eps_map,      True,  "EPS分"),
        "shortage":  (shortage_map, True,  "缺貨分"),
        "rs_leader": (rs_map,       True,  "RS分"),
    }
    _missing = []
    if "shortage" in factors and not shortage_rows:
        _missing.append("缺貨動能")
    if "rs_leader" in factors and not rs_rows:
        _missing.append("抗跌 RS")

    _col_scores: dict[str, dict] = {}
    for _f in factors:
        _vmap, _hb, _col = _cfg.get(_f, ({}, True, _f))
        _col_scores[_f] = _percentile_scores(ids, _vmap, higher_better=_hb)

    _composite = {
        i: round(sum(_col_scores[f].get(i, 0.0) for f in factors) / len(factors), 1)
        for i in ids
    }
    ranked = sorted(ids, key=lambda i: -_composite[i])[: int(top_n)]

    out = pd.DataFrame({
        "代碼": ranked,
        "名稱": [str(name_map.get(c, "")) for c in ranked],
        "綜合分": [_composite[c] for c in ranked],
    })
    for _f in factors:
        out[_cfg[_f][2]] = [_col_scores[_f].get(c, 0.0) for c in ranked]

    note = ""
    if _missing:
        note = (f"（{'、'.join(_missing)} 尚未掃描 → 該因子暫記 0 分；"
                "請先在下方「🔎 進階主題選股」掃描，回來重按即帶入。）")
    return out, note


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
