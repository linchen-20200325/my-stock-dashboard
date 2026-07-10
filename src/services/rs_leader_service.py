"""src/services/rs_leader_service.py — 抗跌 RS 選股 L3 編排（v19.70）。

需求:大盤下跌時（例如 2020 疫情崩盤），排出「仍贏過大盤」的相對強弱前 50。
Phase 1 = 即時模式（掃最近一段可調 lookback）；歷史視窗模式為 Phase 2（待接）。

資料流（§8.2 L3：合法組合 L1 fetcher + L2 純函式）：
  ① L1 get_survivor_ids（免費離線基本面存活池 ~324 檔，你的環境確定能跑）
  ② L1 fetch_yf_close('^TWII')（大盤基準）+ 逐檔 fetch_stock_history_1y（threaded）
  ③ L2 rank_rs_leaders（對齊日曆日 + σ標準化超額 + 排序取前 50）
  → rows + meta（含市場漲/跌情境；§5 診斷攤開資料不足檔數）

§1 fail-loud:存活池空 / 大盤抓不到 / 全資料不足 → 回空 + 精準 note，不炸、不造假。
§8.2.A EX-CACHE-1:條件 import streamlit，僅 @st.cache_data，無真 UI 呼叫。
"""
from __future__ import annotations

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

from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from shared.rs_screen_thresholds import (
    RS_DEFAULT_LOOKBACK,
    RS_LEADER_TOP_N,
    RS_LEADER_VERSION,
    RS_MAX_WORKERS,
    RS_SCAN_MAX,
)
from shared.ttls import TTL_1HOUR
from src.compute.screener.rs_leader_screener import (
    count_insufficient,
    market_interval_return,
    rank_rs_leaders,
    to_rows,
)
from src.data.macro import fetch_yf_close
from src.data.stock.picker_fetcher import fetch_stock_history_1y

_TWII_TICKER = "^TWII"


def _clear(fn) -> None:
    clear = getattr(fn, "clear", None)
    if callable(clear):
        clear()


def _survivor_pool(max_n: int) -> list[str]:
    """免費離線基本面存活池股號（選股網「四項全過」快照）。失敗回 []。"""
    try:
        from src.services.fundamental_screener_service import get_survivor_ids
        return [str(s) for s in get_survivor_ids()[:max_n]]
    except Exception as _e:  # noqa: BLE001 — 快照不可用不炸掃描
        print(f"[rs-svc] 基本面存活池不可用:{type(_e).__name__}: {_e}")
        return []


def _market_frame() -> pd.DataFrame:
    """大盤 ^TWII 收盤 Series → 單欄 close DataFrame（給 L2）。抓不到回空 df。"""
    s = fetch_yf_close(_TWII_TICKER, range_="2y")
    if s is None or len(s) == 0:
        return pd.DataFrame()
    return s.rename("close").to_frame()


def _fetch_one(sid: str) -> dict:
    """逐檔抓 1y K 線 → {stock_id, name, df}（df=None 代表抓不到，下游標資料不足）。"""
    try:
        df, _resolved = fetch_stock_history_1y(sid)
    except Exception as _e:  # noqa: BLE001 — 單檔失敗不拖垮整批
        print(f"[rs-svc] {sid} 抓價失敗:{type(_e).__name__}: {_e}")
        df = None
    return {"stock_id": str(sid), "name": "", "df": df}


def _fetch_pool_prices(ids: list[str]) -> list[dict]:
    """並行抓整個存活池的個股 K 線（fetch_stock_history_1y 無 st.cache、thread-safe）。"""
    out: list[dict] = []
    with ThreadPoolExecutor(max_workers=RS_MAX_WORKERS) as ex:
        _futs = {ex.submit(_fetch_one, sid): sid for sid in ids}
        for _f in as_completed(_futs):
            out.append(_f.result())
    return out


def _market_context(df_market: pd.DataFrame, lookback: int) -> dict:
    """此期間大盤漲/跌情境（決定「抗跌」語意是否成立）。"""
    ret = market_interval_return(df_market, lookback)
    if ret is None:
        return {"market_ret_pct": None, "is_down": None,
                "banner": "⚠️ 大盤 ^TWII 區間報酬無法計算（歷史不足）"}
    ret = float(ret)                 # numpy → python，避免下游 is True/is False 比較踩雷
    _down = bool(ret < 0)
    if _down:
        banner = (f"📉 此期間大盤（^TWII）約 {ret:+.1f}% — 屬下跌情境；"
                  f"以下為「跌勢中仍相對抗跌 / 逆勢贏過大盤」的個股。")
    else:
        banner = (f"📈 此期間大盤（^TWII）約 {ret:+.1f}% — 大盤其實在漲，"
                  f"「抗跌」語意此時不成立；以下 RS 僅代表相對強弱（誰漲更多）。")
    return {"market_ret_pct": ret, "is_down": _down, "banner": banner}


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def _scan_cached(lookback: int, max_scan: int, beat_only: bool) -> tuple[list[dict], dict]:
    """存活池 → 抓價 → L2 排名 → (前 N rows, meta)。快取集中點（無名稱）。"""
    _fetched_at = pd.Timestamp.now("UTC").isoformat()
    _base_meta = {"lookback": lookback, "top_n": RS_LEADER_TOP_N,
                  "source": "FundamentalsSnapshot(survivors)+yfinance:1y+Yahoo:^TWII",
                  "fetched_at": _fetched_at, "version": RS_LEADER_VERSION}

    # ── ① 大盤基準（先抓；抓不到直接 fail-loud，沒有大盤就無從比較）──
    dfm = _market_frame()
    if dfm.empty:
        return [], {**_base_meta, "candidates": 0, "scanned": 0, "scored": 0,
                    "pool_source": "（無）", "market": {"banner": ""},
                    "note": "⚠️ 大盤 ^TWII 抓取失敗（Yahoo 暫時不可用），無基準可比較 RS，稍後再試。"}

    # ── ② 存活池 ──────────────────────────────────────────────
    survivors = _survivor_pool(max_scan)
    if not survivors:
        return [], {**_base_meta, "candidates": 0, "scanned": 0, "scored": 0,
                    "pool_source": "（無）", "market": _market_context(dfm, lookback),
                    "note": ("⚠️ 基本面存活池為空（選股網初篩需先由 GitHub Actions cron 產出季快照）。"
                             "快照就緒後即可掃描。")}

    # ── ③ 逐檔抓價 + L2 排名 ──────────────────────────────────
    stocks = _fetch_pool_prices(survivors)
    ranked = rank_rs_leaders(stocks, dfm, lookback=lookback,
                             top_n=RS_LEADER_TOP_N, beat_only=beat_only)
    rows = to_rows(ranked)
    market = _market_context(dfm, lookback)

    note = ""
    if not rows:
        _insuff = count_insufficient(stocks, dfm, lookback=lookback)
        note = (f"⚠️ 掃描 {len(stocks)} 檔後無可排名標的：其中資料不足 {_insuff} 檔"
                f"（歷史 < lookback 或 yfinance 抓不到價）"
                + ("；且已勾選『只留贏過大盤』，此期間存活池全數未贏過大盤。" if beat_only else "。"))

    return rows, {**_base_meta, "candidates": len(survivors), "scanned": len(stocks),
                  "scored": len(rows), "pool_source": "基本面存活池（免費離線快照）",
                  "market": market, "note": note}


def run_rs_leader_scan(
    *,
    lookback: int = RS_DEFAULT_LOOKBACK,
    beat_only: bool = False,
    refresh: bool = False,
    max_scan: int = RS_SCAN_MAX,
    name_map: dict[str, str] | None = None,
) -> tuple[list[dict], dict]:
    """抗跌 RS 掃描 → (排行 rows, meta)。

    Args:
        lookback: 區間交易日數（20/60/120）。
        beat_only: True → 只留「贏過大盤」的（excess>0）。
        refresh: True → 清 L1 大盤/個股 cache + 本層 cache 重掃。
        max_scan: 深掃存活池上限（預設 RS_SCAN_MAX）。
        name_map: {代碼: 名稱}（於快取外套用，避免大 dict 進 cache key）。
    """
    if refresh:
        _clear(fetch_yf_close)
        _clear(fetch_stock_history_1y)
        _clear(_scan_cached)

    rows, meta = _scan_cached(int(lookback), int(max_scan), bool(beat_only))
    # 存活池涵蓋率診斷（§5，快取外注入以反映最新快照；淺拷貝避免污染 cache 內 dict）
    try:
        from src.services.fundamental_screener_service import get_snapshot_coverage_note
        meta = {**meta, "coverage_note": get_snapshot_coverage_note()}
    except Exception as _e:  # noqa: BLE001 — 涵蓋率不可用不炸掃描
        print(f"[rs-svc] 涵蓋率注入失敗:{type(_e).__name__}: {_e}")
    if name_map:
        rows = [dict(r) for r in rows]  # 淺拷貝避免污染 cache 內物件
        for r in rows:
            _nm = name_map.get(str(r.get("代碼", "")))
            if _nm:
                r["名稱"] = _nm
    return rows, meta


# ════════════════════════════════════════════════════════════════
# AI 三型建議報告 — prompt 組裝（純函式；AI 呼叫由 L5 傳入 gemini_fn 執行）
# ════════════════════════════════════════════════════════════════
def build_rs_ai_prompt(
    rows: list[dict],
    meta: dict | None = None,
    *,
    top_n: int = 10,
    news_text: str | None = None,
) -> str:
    """把抗跌 RS 排行組成「白話三型建議」AI prompt（積極 / 穩健 / 保守）。

    §8.2 L3:純組字串，不抓資料、不呼叫 AI（gemini_fn 由 L5 傳入執行）。可用合成 rows 單測。
    """
    from src.services.ai_structured_summary import build_structured_summary_prompt

    _rows = rows or []
    _top = _rows[:top_n]
    _meta = meta or {}
    _mkt = _meta.get("market") or {}
    _lookback = _meta.get("lookback", "?")

    # ── 第 1 節：抗跌 RS 排行 ──────────────────────────────
    _pick_lines = []
    for r in _top:
        _code = str(r.get("代碼", "")).strip()
        _name = str(r.get("名稱", "")).strip()
        _title = f"{_code} {_name}".strip()
        _pick_lines.append(
            f"- {_title}：RS {r.get('RS(σ)', '?')}σ（{r.get('訊號', '?')}）；"
            f"個股 {r.get('個股報酬%', '?')}% vs 大盤 {r.get('大盤報酬%', '?')}%"
            f"（超額 {r.get('超額%', '?')}%）")
    _pick_data = "\n".join(_pick_lines) if _pick_lines else "（本次掃描沒有掃出可排名的抗跌標的）"

    # ── 第 2 節：市場情境 + 分布 ───────────────────────────
    def _cnt_beat():
        return sum(1 for r in _rows if r.get("贏過大盤"))
    _stat_data = "\n".join([
        f"- 觀察區間：近 {_lookback} 個交易日。",
        f"- {_mkt.get('banner', '（市場情境未知）')}",
        f"- 這次掃出共 {len(_rows)} 檔進榜，其中 {_cnt_beat()} 檔區間報酬贏過大盤。",
        "- RS 為「σ 標準化超額報酬」：+1σ 以上＝顯著逆勢強、0 附近＝與大盤連動、負值＝弱於大盤。",
    ])

    # ── 第 3 節：模型限制與正確用法（誠實揭露）──────────────
    _caveat_data = "\n".join([
        "- 這是「相對強弱」不是「基本面買點」：抗跌只代表跌得比大盤少 / 逆勢強，不等於便宜或該追。",
        "- 只掃了免費基本面存活池（約 300 多檔體質過關股），非全上市；很強但體質未過篩的個股可能沒進榜。",
        "- 用的是已收盤日線；當日盤中不完整，隔日資料才齊。",
        "- 大盤在漲時「抗跌」語意不成立，此時 RS 只代表誰漲更多。",
    ])

    _sections = [
        {"name": "這次掃出哪些抗跌 / 逆勢贏過大盤的股票", "data": _pick_data},
        {"name": "這段期間的市場情境與強弱分布", "data": _stat_data},
        {"name": "這個 RS 抗跌模型的限制與正確用法", "data": _caveat_data},
    ]

    return build_structured_summary_prompt(
        subject_title="抗跌 / 逆勢贏過大盤（RS）選股候選清單",
        sections=_sections,
        news_text=news_text,
        overall_question=(
            "針對三種人分別給白話建議："
            "①積極型（願意在跌勢中布局強勢股）②穩健型（想等大盤止跌或技術面確認再進）"
            "③保守型（先觀望），這批抗跌股各自現在該怎麼看、進場前最該小心什麼。"
        ),
    )
