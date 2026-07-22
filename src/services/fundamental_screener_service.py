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
from src.compute.screener.cross_quarter_trends import compute_cross_quarter_trends
from src.compute.screener.fundamental_prescreen import (
    run_fundamental_prescreen,
    survivors_only,
)
from src.data.stock.fundamentals_snapshot_loader import (
    load_all_fundamentals_quarters,
    load_fundamentals_snapshot,
)


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


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def _cross_quarter_trends_cached() -> pd.DataFrame:
    """讀全季快照 → 跑跨季趨勢(全市場,每檔一列)。快取集中點(A-2 v19.140)。"""
    return compute_cross_quarter_trends(load_all_fundamentals_quarters())


def get_cross_quarter_trends(*, refresh: bool = False) -> pd.DataFrame:
    """全台股跨季趨勢 DataFrame(每檔一列;欄見 cross_quarter_trends._OUT_COLS)。

    §8.2 L3:合法組合 L1 load_all_fundamentals_quarters + L2 compute_cross_quarter_trends。
    refresh=True → 清 L1 全季 cache + 本層 cache。快照缺 → raise(caller 自行 fail-soft)。
    """
    if refresh:
        _clear(load_all_fundamentals_quarters)
        _clear(_cross_quarter_trends_cached)
    return _cross_quarter_trends_cached()


def build_trend_map(*, refresh: bool = False) -> dict[str, int]:
    """{stock_id: favorable_count} 供選股網 composite「跨季轉強」因子用。

    favorable_count ∈ [0,4] = 毛利/營益率升·負債降·營收增 中「方向為佳」的個數。
    快照缺 / 計算失敗 → 回空 dict(不炸選股;§1 缺料下游不計入該因子)。
    """
    try:
        _df = get_cross_quarter_trends(refresh=refresh)
    except Exception as _e:  # noqa: BLE001 — 快照缺不炸選股
        print(f"[fund_screener_service] 跨季趨勢不可用:{type(_e).__name__}: {_e}")
        return {}
    if _df is None or _df.empty:
        return {}
    return {str(s): int(c) for s, c in zip(_df["stock_id"], _df["favorable_count"])}


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
    "跨季轉強（毛利/營益率升·負債降·營收增）": "trend",
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


# ── 綜合評分（多因子複選；v19.88 / v19.90 修 0-fill 失真）────────────
# 每個勾選因子給 0-100 分位分數（在【有該因子資料的股票】之間排百分位）。
# ⚠️ v19.90:綜合分 = 該股「**有資料的因子**」的平均（NOT 全因子平均）。原本對「缺資料因子」
# 記 0 分再除以全因子數 → 缺貨/RS 只覆蓋 ~50 檔(掃描上限)時,274 檔被灌 0 → 綜合分嚴重失真
# (user 實測:RS 分全 0、排序與 RS 排行對不上)。改「只平均有資料的因子」+ 缺料顯示空白(非 0)。
# 籌碼技術×6 因需逐檔深抓,屬 ③ 深篩關(不入綜合分)。
def _percentile_scores(ids: list[str], value_map: dict, *, higher_better: bool) -> dict:
    """{id: 0-100 百分位分}——**只回有值的股票**（缺值/NaN/非數字 → 不放 key，代表「無此因子資料」）。

    v19.90:不再對缺值填 0（那會在綜合分被當「最差」拉低，且與「真的很差=低分」混淆）。
    """
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
        return {}
    if len(valid) == 1:
        return {i: 100.0 for i in valid}
    _s = pd.Series(valid)
    # higher_better=True → 值越大分越高（ascending=True 使最大值 pct=1.0）；
    # pe_low（higher_better=False）→ 值越小分越高。
    _pct = _s.rank(pct=True, ascending=higher_better)
    return {i: float(v) for i, v in (_pct * 100).round(1).to_dict().items()}


def composite_rank_candidates(
    survivors_df: pd.DataFrame,
    *,
    factors: list[str],
    top_n: int = 300,
    pe_map: dict | None = None,
    name_map: dict | None = None,
    shortage_rows: list[dict] | None = None,
    rs_rows: list[dict] | None = None,
    trend_map: dict | None = None,
) -> tuple[pd.DataFrame, str]:
    """從存活池，依【複選因子】的綜合評分排序 → 候選 DataFrame（含 '代碼' 欄）。

    factors ⊆ {'pe_low','eps_high','shortage','rs_leader','trend'}（籌碼技術×6 屬 ③ 深篩，不在此）。
    trend_map: {stock_id: favorable_count 0-4}（A-2 跨季轉強因子；缺料的股不在 map → 該因子不計入）。
    綜合分 = 該股**有資料的因子**百分位分（0-100）的平均（v19.90：缺料因子不計入、不記 0）。
    顯示欄：缺料因子該股為空白（None），不是 0，避免誤導。

    Returns: (df[代碼/名稱/綜合分/各因子分], note)。
      - factors 空 → 空 + 「請至少勾一個因子」
      - 勾了缺貨/RS 但尚未掃描 → note 提示（該因子暫無資料、不計入，不擋其他因子）
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
    trend_map = {str(k): v for k, v in (trend_map or {}).items()}

    # (value_map, higher_better, 顯示欄名)
    _cfg = {
        "pe_low":    (pe_map,       False, "估值分"),
        "eps_high":  (eps_map,      True,  "EPS分"),
        "shortage":  (shortage_map, True,  "缺貨分"),
        "rs_leader": (rs_map,       True,  "RS分"),
        "trend":     (trend_map,    True,  "跨季分"),
    }
    _missing = []
    if "shortage" in factors and not shortage_rows:
        _missing.append("缺貨動能")
    if "rs_leader" in factors and not rs_rows:
        _missing.append("抗跌 RS")
    # trend 由快照計算(非掃描),缺料時 _percentile_scores 自然不計入,不走「尚未掃描」提示。

    _col_scores: dict[str, dict] = {}
    for _f in factors:
        _vmap, _hb, _col = _cfg.get(_f, ({}, True, _f))
        _col_scores[_f] = _percentile_scores(ids, _vmap, higher_better=_hb)

    # 綜合分 = 只平均「該股有資料的因子」；全無資料 → None（排最後）
    _composite: dict[str, float | None] = {}
    for i in ids:
        _present = [_col_scores[f][i] for f in factors if i in _col_scores[f]]
        _composite[i] = round(sum(_present) / len(_present), 1) if _present else None
    ranked = sorted(ids, key=lambda i: (_composite[i] is None, -(_composite[i] or 0)))[: int(top_n)]

    out = pd.DataFrame({
        "代碼": ranked,
        "名稱": [str(name_map.get(c, "")) for c in ranked],
        "綜合分": [_composite[c] for c in ranked],
    })
    for _f in factors:
        # 缺料 → None（畫面顯示空白，非 0）
        out[_cfg[_f][2]] = [_col_scores[_f].get(c) for c in ranked]

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
