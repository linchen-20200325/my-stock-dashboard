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
# T1-a(2026-08)：空頭濾網的 regime 集合走既有 L0 SSOT，不另立常數（§3.3）。
# `regime_arbiter.py:66` 已把 THROTTLE_VETO_REGIMES 當成「caution 與 bear 同列否決」
# 的權威定義，本模組對齊同一份。
from shared.position_throttle import THROTTLE_VETO_REGIMES
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

    §1 B6-b(2026-08):**favorable_of == 0 的檔不放 key**。favorable_of 是「算得出來的
    因子數」,為 0 代表四個趨勢因子全 NaN(季數不足 / 營收·資產為 0 → 比率算不出),
    此時 favorable_count 必為 0 —— 那是「沒有證據」不是「四項全不佳」。原本一律放
    {sid: 0} 會讓 `_percentile_scores` 把它當**真實讀數**給最低百分位分,還算進
    SCREENER_MIN_FACTOR_COVERAGE_RATIO 涵蓋門檻的分子(= 一個捏造值幫它通過門檻)。
    """
    try:
        _df = get_cross_quarter_trends(refresh=refresh)
    except Exception as _e:  # noqa: BLE001 — 快照缺不炸選股
        print(f"[fund_screener_service] 跨季趨勢不可用:{type(_e).__name__}: {_e}")
        return {}
    if _df is None or _df.empty:
        return {}
    if "favorable_of" not in _df.columns:      # 舊 schema → 保守全收(不靜默丟資料)
        return {str(s): int(c) for s, c in zip(_df["stock_id"], _df["favorable_count"])}
    return {str(s): int(c)
            for s, c, n in zip(_df["stock_id"], _df["favorable_count"], _df["favorable_of"])
            if int(n) > 0}


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
    "缺貨動能（供不應求 4 訊號）": "shortage",
    # B6-b(2026-08)文案修:原「抗跌 RS 強（弱勢仍贏大盤）」承諾了判定式沒做的事 ——
    # 綜合評分走 `run_rs_leader_scan(beat_only=False)`(見 get_ranked_picks),排行含
    # 「落後大盤」分級(RS_RANKABLE_TIERS 含 TIER_LAG),故 RS 分只是**相對強弱百分位**,
    # 不保證該檔贏過大盤(大盤大漲時整池都可能沒贏)。label 改為描述實際判定式。
    "抗跌 RS（相對強弱 σ，越高越抗跌；不保證贏大盤）": "rs_leader",
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
    drop_unscored: bool = False,
) -> tuple[pd.DataFrame, str]:
    """從存活池，依【複選因子】的綜合評分排序 → 候選 DataFrame（含 '代碼' 欄）。

    factors ⊆ {'pe_low','eps_high','shortage','rs_leader','trend'}（籌碼技術×6 屬 ③ 深篩，不在此）。
    trend_map: {stock_id: favorable_count 0-4}（A-2 跨季轉強因子；缺料的股不在 map → 該因子不計入）。
    綜合分 = 該股**有資料的因子**百分位分（0-100）的平均（v19.90：缺料因子不計入、不記 0）。
    顯示欄：缺料因子該股為空白（None），不是 0，避免誤導。

    drop_unscored（B6-b 2026-08）：True → 綜合分為 None 的檔**不出現在結果**。
      預設 False 保留既有「排最後、綜合分空白」行為（直接呼叫本函式的既有 caller/測試）；
      `get_ranked_picks`（畫面 / 每月凍結 / MCP / 推播 同源入口）一律傳 True ——
      §1：沒算出綜合分的檔不該被當成「綜合評分排序」的入選結果拿去凍結進前進式驗證紀錄。

    Returns: (df[代碼/名稱/綜合分/各因子分], note)。
      - factors 空 → 空 + 「請至少勾一個因子」
      - 勾了缺貨/RS 但尚未掃描 → note 提示（該因子暫無資料、不計入，不擋其他因子）
      - 有因子只覆蓋部分存活池（如缺貨深掃上限 50 檔）→ note 揭露實際覆蓋分母（§5）
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

    # 綜合分 = 只平均「該股有資料的因子」；但需「勾選因子過半有資料」才進榜(涵蓋門檻),
    # 否則 None（排最後）—— 防「只有單一因子有資料、又剛好高分」的股(如只有 RS=100
    # 的上櫃股)以 100 衝頂(v19.90「只平均有資料因子」的反向副作用)。
    # SSOT: SCREENER_MIN_FACTOR_COVERAGE_RATIO(嚴格 >:3 勾需≥2、2 勾需2、1 勾需1)。
    # 分母用「全域實際有資料的勾選因子」_effective_n:某因子完全沒掃到(如缺貨未掃 →
    # 全空)時不算進門檻,否則「勾了但沒掃的因子」會把全榜清空(對齊既有『缺掃不擋』行為)。
    from shared.signal_thresholds import SCREENER_MIN_FACTOR_COVERAGE_RATIO
    _effective_n = sum(1 for _f in factors if _col_scores[_f])  # 至少 1 檔有值的勾選因子數
    _min_present = SCREENER_MIN_FACTOR_COVERAGE_RATIO * _effective_n
    _composite: dict[str, float | None] = {}
    _n_below_coverage = 0  # 有資料但不足過半 → 被涵蓋門檻擋下(可觀測性 §5)
    for i in ids:
        _present = [_col_scores[f][i] for f in factors if i in _col_scores[f]]
        if _present and len(_present) > _min_present:
            _composite[i] = round(sum(_present) / len(_present), 1)
        else:
            _composite[i] = None
            if _present:  # 「有部分資料但不足過半」才計入(全無資料本就 None,非新擋下)
                _n_below_coverage += 1
    ranked = sorted(ids, key=lambda i: (_composite[i] is None, -(_composite[i] or 0)))
    _n_unscored_dropped = 0
    if drop_unscored:
        _n_unscored_dropped = sum(1 for i in ranked if _composite[i] is None)
        ranked = [i for i in ranked if _composite[i] is not None]
    ranked = ranked[: int(top_n)]

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
        # v19.167 文案修:實際行為是「缺料因子不計分、不影響其他因子排序」(見上方
        # out[...] = get(c) 回 None 空白,非 0);且「開始選股」已自動掃描,無「下方掃描」區塊。
        note = (f"（{'、'.join(_missing)} 尚未掃描 → 該因子不計分、不影響其他因子排序;"
                "重按「🎯 開始選股」會自動掃描帶入。）")
    if _n_below_coverage:
        # 涵蓋門檻擋下數(§5 可觀測性):讓 user 知道有幾檔因「勾選因子涵蓋不足過半」被排最後。
        _pct = int(SCREENER_MIN_FACTOR_COVERAGE_RATIO * 100)
        _cov_txt = (f"（{_n_below_coverage} 檔因「勾選因子涵蓋未過半」未列入綜合排序;"
                    f"需 >{_pct}% 勾選因子有資料,避免單一因子高分股衝頂。）")
        note = f"{note} {_cov_txt}".strip() if note else _cov_txt

    # B6-b(§5 可觀測性):某因子「掃到了但只覆蓋部分存活池」時,原本完全無提示 ——
    # 例如缺貨深掃上限 50 檔(SHORTAGE_DEEP_SCAN_MAX)、存活池 324 檔,使用者以為整份
    # 榜是依缺貨排的,實際 85% 的股根本沒有缺貨分。把實際覆蓋分母攤開。
    # ⚠️ 用「覆蓋」而非「涵蓋」二字:「涵蓋」已被上面的門檻提示佔用,兩者語意不同
    #   （涵蓋門檻 = 個股層級被擋;覆蓋 = 因子層級的母體大小）。
    _cov_bits = [f"{_cfg[_f][2]} {len(_col_scores[_f])}/{len(ids)}"
                 for _f in factors
                 if _col_scores[_f] and len(_col_scores[_f]) < len(ids)]
    if _cov_bits:
        _bit_txt = ("（因子實際覆蓋:" + "、".join(_cov_bits)
                    + " —— 未覆蓋到的個股該因子不計分,不是 0 分。）")
        note = f"{note} {_bit_txt}".strip() if note else _bit_txt
    if _n_unscored_dropped:
        _drop_txt = (f"（{_n_unscored_dropped} 檔未取得綜合分（勾選因子資料不足）"
                     "→ 已排除於名單外,不列為入選。）")
        note = f"{note} {_drop_txt}".strip() if note else _drop_txt
    return out, note


def get_ranked_picks(
    factors: list[str],
    *,
    top_n: int = 300,
    survivors_df: pd.DataFrame | None = None,
    pe_map: dict | None = None,
    name_map: dict | None = None,
    shortage_rows: list[dict] | None = None,
    rs_rows: list[dict] | None = None,
    trend_map: dict | None = None,
    auto_fetch: bool = True,
    refresh: bool = False,
    regime: str | None = None,
) -> tuple[pd.DataFrame, str]:
    """選股網「一鍵選股」同源編排：存活池 +（缺貨/RS/跨季）+ PE → 綜合排名。

    v19.147：把原本散在 app.py 選股網（app.py:664-681）的組裝抽成單一函式，讓
    **畫面**（app.py）與 **cron**（scripts/update_forward_test_freeze.py 前進式驗證自動凍結）
    共用同一支 → 保證「自動凍結的清單 = 使用者畫面看到的清單」（§8 SSOT，防兩處組裝漂移）。

    分層（§8.2 L3）:
      - survivors / shortage / rs / trend 全走 L3 service（get_fundamental_survivors /
        run_shortage_scan / run_rs_leader_scan / build_trend_map）——合法。
      - `pe_map` / `name_map` 由 **orchestrator（app / cron / MCP）抓後傳入**：四個入口
        共用同一支 `fetch_pe_name_maps`（E2 2026-08 起在 L1
        `src/data/stock/yield_pe_fetcher.py`；此前住在 L5 `src/ui/tabs/yield_screener.py`，
        「L3 不反向 import」才是當時改由 caller 注入的理由）。現在 L3 直呼 L1 已無分層
        障礙，但**維持注入**：畫面端本來就要拿 name_map 顯示，注入可避免重抓 + 讓
        「畫面 / 推播 / 凍結 / MCP」四處明確共用同一份 map（§2.1 SSOT）。

    參數:
      - survivors_df: 已備存活池則傳入（app 端已抓，避免重抓；不傳則本層自抓，cron 用）。
      - auto_fetch: True（cron）→ 缺的 shortage/rs/trend 自動掃；False（app）→ 只用傳入的
        session 快取值，不重掃（保留畫面既有「按鈕觸發掃描 + session 快取」行為）。
      - regime: canonical 總經五態（`allocation_service.get_macro_regime()`）。
        `bear` / `caution` → 套用**空頭濾網**（見下）。None / 其他值 → 不套用。

    ── T1-a(2026-08)空頭濾網 ──────────────────────────────────
    §8「總經影響全系統風控」的接線點：空頭中弱勢股的下檔風險顯著高於強勢股，
    故 `regime ∈ {bear, caution}` 時剔除「區間報酬未贏過大盤」的候選。

    ⚠️ **刻意不改 `beat_only`**（原規劃曾如此提案，實作時查證後推翻）：
      `:487` 的 `run_rs_leader_scan(beat_only=False)` 決定的是**百分位的分母**，
      不是濾網開關。改成 True 會讓落後股從 `rs_map` 消失 → 對它們而言 RS 因子
      變成「缺料」→ 依 `:319` 的規則**不計入**平均 → 若 RS 本來在拖累它們，
      綜合分反而**上升**。那是「幫落後股加分」，與空頭濾網的意圖完全相反。
      故改為在**排名結果**上做顯式後濾，百分位計算完全不動。

    §1：RS 資料不存在（未勾選 rs_leader 因子 / 掃描失敗）時**無法**套用濾網。
      此時 note 明確寫出「未套用」，**不可**靜默跳過 —— 否則使用者會以為
      空頭防禦已經生效。

    §1：任一掃描失敗 → 該因子缺料（composite 自動不計入、不記 0），不炸整體。
    Returns: (cands_df[代碼/名稱/綜合分/各因子分], note)。
    """
    _factors = list(factors or [])
    if survivors_df is None:
        try:
            survivors_df, _ = get_fundamental_survivors(refresh=refresh)
        except Exception as _e:  # noqa: BLE001 — 快照缺不炸選股
            print(f"[fund_screener_service] get_ranked_picks 存活池不可用：{type(_e).__name__}: {_e}")
            survivors_df = None

    if auto_fetch:
        if "shortage" in _factors and shortage_rows is None:
            try:
                from src.services.shortage_screener_service import run_shortage_scan
                shortage_rows = run_shortage_scan()[0]
            except Exception as _es:  # noqa: BLE001 — 掃描失敗 → 該因子缺料，不炸
                print(f"[fund_screener_service] get_ranked_picks 缺貨掃描失敗：{type(_es).__name__}: {_es}")
        if "rs_leader" in _factors and rs_rows is None:
            try:
                # v19.90:綜合分需【全存活池】RS 分位 → beat_only=False + top_n 給大值（同 app.py:645）。
                from shared.rs_screen_thresholds import RS_SCAN_MAX
                from src.services.rs_leader_service import run_rs_leader_scan
                rs_rows = run_rs_leader_scan(beat_only=False, top_n=RS_SCAN_MAX)[0]
            except Exception as _er:  # noqa: BLE001
                print(f"[fund_screener_service] get_ranked_picks RS 掃描失敗：{type(_er).__name__}: {_er}")
        if "trend" in _factors and trend_map is None:
            trend_map = build_trend_map(refresh=refresh)

    # drop_unscored=True(B6-b 2026-08):本函式是「畫面 / 每月凍結 / MCP / 推播」四處
    # 同源入口,回傳值會被 `.head(N)` 當「綜合評分排序前 N 名」直接凍結進 forward-test
    # 紀錄。綜合分 None = 該檔**從未被評分**(勾選因子資料不足),把它排在後面仍可能因
    # 「有分的檔不足 N 個」被 head(N) 撈進凍結名單 → 污染畫面與凍結紀錄(§1 綠燈假象)。
    _df, _note = composite_rank_candidates(
        survivors_df, factors=_factors, top_n=top_n,
        pe_map=pe_map, name_map=name_map,
        shortage_rows=shortage_rows, rs_rows=rs_rows, trend_map=trend_map,
        drop_unscored=True,
    )
    return _apply_bear_market_filter(_df, _note, regime=regime, rs_rows=rs_rows)


def _apply_bear_market_filter(
    df: pd.DataFrame,
    note: str,
    *,
    regime: str | None,
    rs_rows: list[dict] | None,
) -> tuple[pd.DataFrame, str]:
    """T1-a：`regime ∈ {bear, caution}` → 剔除「未贏過大盤」的候選。

    這是「總經 → 全系統風控」在**選股引擎**上的接線點。此前
    `fundamental_screener_service` 全檔零 `regime` 引用 —— 總經說空頭防禦時，
    選股網照樣用同一組門檻選出同一批股票。

    防禦性 regime 集合走 L0 SSOT `shared.position_throttle.THROTTLE_VETO_REGIMES`
    （`regime_arbiter.py:66` 已把它當成 caution/bear 同列否決的權威定義），
    **不另立常數**（§3.3）。

    §1 三種情形都必須在 note 講清楚，不可靜默：
      1. 未套用（regime 非防禦態 / 未評估）→ 不加註（避免每次都刷一行雜訊）
      2. 想套用但**沒有 RS 資料** → 明寫「無法套用」+ 原因
      3. 套用了 → 明寫剔除幾檔
    """
    if regime not in THROTTLE_VETO_REGIMES:
        return df, note

    # 情形 2：RS 資料缺席 → 濾網無法生效。§1 必須說，否則使用者會誤以為
    # 「總經空頭 → 系統已經幫我濾掉弱勢股」，而實際上什麼都沒發生。
    if not rs_rows:
        return df, (
            f"{note}\n\n⚠️ 總經為「{regime}」但**未套用空頭濾網** —— "
            "本次沒有相對強弱（RS）資料，無法判斷哪些檔贏過大盤。"
            "勾選「抗跌 RS」因子後重跑即可啟用。"
        )

    if df is None or df.empty or "代碼" not in df.columns:
        return df, note

    _beat = {str(r.get("代碼", "")).strip() for r in rs_rows if r.get("贏過大盤")}
    _before = len(df)
    _filtered = df[df["代碼"].astype(str).str.strip().isin(_beat)]
    _dropped = _before - len(_filtered)

    # 情形 3：套用了就講清楚剔除了什麼、依據什麼。
    _msg = (
        f"{note}\n\n🛡️ 總經為「{regime}」→ 已套用**空頭濾網**："
        f"剔除 {_dropped} 檔區間報酬未贏過大盤者，剩 {len(_filtered)} 檔。"
        "（空頭中弱勢股的下檔風險顯著高於強勢股；"
        "此濾網只在總經為 bear / caution 時啟用。）"
    )
    if _filtered.empty:
        # §1：空表要說明「為什麼是空的」，不可讓使用者以為系統壞了。
        # 空頭中沒有任何存活池成員贏過大盤，是**有意義的訊號**，不是故障。
        _msg += "\n\n本次**沒有任何一檔**贏過大盤 —— 這本身就是空頭訊號，不是系統故障。"
    return _filtered, _msg


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
