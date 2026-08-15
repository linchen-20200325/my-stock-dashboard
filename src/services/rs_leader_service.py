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
    RS_MIN_ALIGNED_ROWS,
    RS_SCAN_MAX,
)
from shared.signal_thresholds import (  # v19.178:AI prompt 引 RS σ 分級 SSOT
    RS_MARKET_SIGMA_MIN_PCT,           # I1:空排行歸因要講出 σ 門檻,不寫死數字(§3.3)
    RS_SIGMA_LAG_MAX,
    RS_SIGMA_LEAD_MIN,
    RS_SIGMA_MILD_MIN,
)
from shared.ttls import TTL_1HOUR
from src.compute.screener.rs_leader_screener import (
    count_insufficient,
    market_interval_return,
    rank_rs_leaders,
    score_rs_leader,
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
    # FIX(§1 / 顯示一致性): 原為二分法 `_down = bool(ret < 0)`，無中性帶，且
    #   上游 market_interval_return 已 round(...,2)、此處顯示又用 {:+.1f} ——
    #   三者相乘造成兩個實際發生的畫面矛盾：
    #     (a) ret=-0.04 印「📉 約 -0.0% — 屬下跌情境」、ret=+0.04 印「📈 約 +0.0% — 大盤其實在漲」
    #         → 畫面數字一模一樣、結論相反。
    #     (b) 真值落在 (-0.005, 0) 時 round 產生 -0.0，而 `-0.0 < 0` 為 False
    #         → 印出「📈 此期間大盤約 **-0.0%** — 大盤其實在漲」的自相矛盾句。
    #   且此 banner 會被 build_rs_ai_prompt 原文餵給 LLM。
    #   修法：補「持平」第三態 + 顯示精度改 {:+.2f} 與上游 round(2) 對齊。
    #   門檻 0.5% 為顯示用中性帶，不參與任何排序或評分（is_down 僅供文案分支）。
    _FLAT_BAND_PCT = 0.5
    if abs(ret) < _FLAT_BAND_PCT:
        _down = None                 # 三態：None = 持平，不宣稱漲也不宣稱跌
        banner = (f"⚖️ 此期間大盤（^TWII）約 {ret:+.2f}% — 大致持平；"
                  f"「抗跌」與「領漲」語意此時都不成立，以下 RS 僅代表相對強弱。")
    elif ret < 0:
        _down = True
        banner = (f"📉 此期間大盤（^TWII）約 {ret:+.2f}% — 屬下跌情境；"
                  f"以下為「跌勢中仍相對抗跌 / 逆勢贏過大盤」的個股。")
    else:
        _down = False
        banner = (f"📈 此期間大盤（^TWII）約 {ret:+.2f}% — 大盤其實在漲，"
                  f"「抗跌」語意此時不成立；以下 RS 僅代表相對強弱（誰漲更多）。")
    return {"market_ret_pct": ret, "is_down": _down, "banner": banner}


def _has_price(stock: dict) -> bool:
    """這一檔到底有沒有拿到任何 K 線 —— 把「抓不到價」與「有價但排不進」分開。"""
    _df = (stock or {}).get("df")
    try:
        return _df is not None and len(_df) > 0
    except TypeError:                     # 非序列型別(理論上不該發生)→ 視為沒有價
        return False


def _market_baseline_unusable(df_market: pd.DataFrame, lookback: int) -> bool:
    """大盤基準自己能不能產出 σ 標準化讀數。True ＝ 不能(問題在**大盤側**)。

    §2.1 SSOT:這裡**不自己算一次 σ** —— 直接用 L2 的 `score_rs_leader` 把大盤當成
    一檔股票丟進去(個股序列＝大盤序列 ⇒ 超額恆 0),那麼唯一還會讓 `avg_rs` 變成
    `None` 的只剩兩件事:對齊後共同交易日不足、或分母 σ ≤ `RS_MARKET_SIGMA_MIN_PCT`
    /NaN。兩者都在大盤側。重寫一份 σ 判準就是第二套演算法,兩邊一漂又是一個假歸因。
    """
    return score_rs_leader(
        {"stock_id": _TWII_TICKER, "name": "", "df": df_market},
        df_market, lookback=int(lookback),
    ).avg_rs is None


def _empty_scan_note(stocks: list[dict], df_market: pd.DataFrame, *,
                     lookback: int, beat_only: bool) -> str:
    """排行為空時的**歸因**(§5 可觀測性;§1 不把單一猜測寫成原因)。

    I1 2026-08-10 修掉的原文::

        note = (f"⚠️ 掃描 {len(stocks)} 檔後無可排名標的：其中資料不足 {_insuff} 檔"
                f"（歷史 < lookback 或 yfinance 抓不到價）"
                + ("；且已勾選『只留贏過大盤』，此期間存活池全數未贏過大盤。" if beat_only else "。"))

    兩句都可能是假的:

      (a) H2(2026-08)之後,`calc_relative_strength` 在「大盤日報酬 σ ≤
          `RS_MARKET_SIGMA_MIN_PCT` 或 NaN」時回 `avg_rs=None` → `TIER_INSUFFICIENT`。
          那是**大盤側**的分母問題,個股資料再完整也排不進去;而畫面卻叫使用者去查
          個股歷史長度與 yfinance —— 查一整天也查不到東西。
      (b) 一檔都沒被成功量測時,「此期間存活池全數未贏過大盤」是憑空生出來的**市場
          結論**:沒有人被量過,就不知道有沒有人贏。這比 (a) 更嚴重 —— (a) 只是指錯
          方向,(b) 是無中生有一個投資判斷。
    """
    _n = len(stocks)
    _insuff = count_insufficient(stocks, df_market, lookback=int(lookback))
    # RS_RANKABLE_TIERS 涵蓋「資料不足」以外的全部分級 ⇒ 量測成功數 = 總數 − 資料不足數。
    _measured = _n - _insuff
    _need = max(int(lookback), RS_MIN_ALIGNED_ROWS)

    if _measured > 0:
        if beat_only:
            return (f"⚠️ 掃描 {_n} 檔:成功量測 {_measured} 檔,但其中 **0 檔**在此期間"
                    f"贏過大盤(已勾選「只留贏過大盤」)。取消勾選即可看到完整相對強弱"
                    f"排序(含落後大盤的檔);另有 {_insuff} 檔資料不足,未列入量測。")
        # beat_only=False 且有量測成功卻排不出列 → 只可能是排序/取數環節壞了。
        # 不編一個像樣的理由蓋過去(§1),直接講「這不該發生」。
        return (f"⚠️ 內部不一致:成功量測 {_measured} 檔,卻排不出任何一列"
                f"(未勾選「只留贏過大盤」,理論上不該發生)。另有 {_insuff} 檔資料不足。"
                f"請回報這段訊息。")

    # ── 以下:一檔都沒有被成功量測(_measured == 0,即全部判「資料不足」)──────
    _no_price = sum(1 for s in stocks if not _has_price(s))
    _with_price = _insuff - _no_price
    if _market_baseline_unusable(df_market, lookback):
        _note = (f"⚠️ 掃描 {_n} 檔後無可排名標的,{_n} 檔全部判「資料不足」。"
                 f"**問題指向大盤側**:基準 ^TWII 自己也產不出 σ 標準化讀數"
                 f"(大盤日報酬標準差 ≤ {RS_MARKET_SIGMA_MIN_PCT:g}%,"
                 f"或對齊後交易日 < {_need} 日)—— RS 的分母來自大盤,"
                 f"分母不成立時每一檔都會踩到同一個問題。"
                 f"請先確認 ^TWII 序列是否停更/凍結,**再考慮重抓個股**。")
    else:
        _note = (f"⚠️ 掃描 {_n} 檔後無可排名標的,{_n} 檔全部判「資料不足」:"
                 f"其中 {_no_price} 檔完全抓不到 K 線(yfinance 回空)、"
                 f"{_with_price} 檔有 K 線但與大盤對齊後的共同交易日 < {_need} 日"
                 f"(歷史太短 / 欄位不符 / 日期對不上)。"
                 f"大盤基準 ^TWII 本身正常(σ 可用),因此這是個股側的資料問題。")
    if beat_only:
        _note += ("(已勾選「只留贏過大盤」,但本次沒有任何一檔被成功量測,"
                  "因此**無法**判斷有沒有人贏過大盤 —— 這不等於「全數落後」。)")
    return _note


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def _scan_cached(lookback: int, max_scan: int, beat_only: bool,
                 top_n: int = RS_LEADER_TOP_N) -> tuple[list[dict], dict]:
    """存活池 → 抓價 → L2 排名 → (前 N rows, meta)。快取集中點（無名稱）。

    top_n：排行取幾檔。選股網綜合評分需**全存活池** RS 分位（top_n 給大值 + beat_only=False），
    避免只回 top-50 → 綜合分那邊 274 檔 RS 記 0 的失真。
    """
    _fetched_at = pd.Timestamp.now("UTC").isoformat()
    _base_meta = {"lookback": lookback, "top_n": top_n,
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
                             top_n=top_n, beat_only=beat_only)
    rows = to_rows(ranked)
    market = _market_context(dfm, lookback)

    note = ""
    if not rows:
        note = _empty_scan_note(stocks, dfm, lookback=lookback, beat_only=beat_only)

    return rows, {**_base_meta, "candidates": len(survivors), "scanned": len(stocks),
                  "scored": len(rows), "pool_source": "基本面存活池（免費離線快照）",
                  "market": market, "note": note}


def run_rs_leader_scan(
    *,
    lookback: int = RS_DEFAULT_LOOKBACK,
    beat_only: bool = False,
    refresh: bool = False,
    max_scan: int = RS_SCAN_MAX,
    top_n: int = RS_LEADER_TOP_N,
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

    rows, meta = _scan_cached(int(lookback), int(max_scan), bool(beat_only), int(top_n))
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
        # v19.178 §3.3:原寫死「+1σ 以上 / 0 附近 / 負值」，與實際分級 SSOT
        # (shared/signal_thresholds RS_SIGMA_*) 的三段門檻不同 —— 表格裡的「訊號」欄
        # 用 1.0 / 0.3 / -0.3 分級，餵給 AI 的說明卻把 0.3 / -0.3 壓縮成「0 附近」，
        # LLM 讀不出 🟡 偏強與 ⚪ 同步的界線。改為插值 SSOT。
        (f"- RS 為「σ 標準化超額報酬」（單位＝大盤日報酬標準差的倍數）："
         f"≥{RS_SIGMA_LEAD_MIN:+.1f}σ＝🔴 顯著逆勢強、"
         f"≥{RS_SIGMA_MILD_MIN:+.1f}σ＝🟡 偏強、"
         f"<{RS_SIGMA_LAG_MAX:+.1f}σ＝🟢 弱於大盤，其間＝⚪ 與大盤同步。"),
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
