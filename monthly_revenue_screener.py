"""monthly_revenue_screener.py — 月營收進退篩選器

v18.180 新增功能：篩選台股近 3 個月月營收呈現「進步 / 退步」趨勢的標的。

判斷基準（YoY + MoM 雙條件）：
  • 強進步 = 近 3 月 YoY 全 ≥ +threshold% 且 末月 MoM ≥ 0
  • 進步   = 近 3 月 YoY 全 > 0% 且 末月 MoM ≥ 0
  • 強退步 = 近 3 月 YoY 全 ≤ -threshold% 且 末月 MoM ≤ 0
  • 退步   = 近 3 月 YoY 全 < 0% 且 末月 MoM ≤ 0
  • 中性   = 其餘情境
  • 資料不足 = 不足 15 個月歷史（含 12 個月 YoY 基期 + 3 個月當期）

資料源：
  ① FinMind TaiwanStockMonthRevenue（每月 10 日公告）
  ② TWSE OpenAPI BWIBBU_d（取股票名稱對照）

架構決策：
  • 純函式 + Streamlit UI 分離；fetch_* 走 @st.cache_data(ttl=21600) 6 小時快取
  • 鏡像 yield_screener.py 漏斗 UI pattern
  • 全市場掃描 = FinMind 不帶 data_id 一次抓全 → 本地分組計算（避開 1700 檔逐股 API 風暴）
"""
from __future__ import annotations

import os
from typing import Any

import pandas as pd
import streamlit as st

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

# 判斷模式 → 中文 label
TREND_LABELS = {
    "strong_up": "🚀 強進步",
    "up": "📈 進步",
    "strong_down": "🔻 強退步",
    "down": "📉 退步",
    "neutral": "➖ 中性",
    "insufficient": "⚪ 資料不足",
}


# ══════════════════════════════════════════════════════════════════════════════
# ① 資料抓取層
# ══════════════════════════════════════════════════════════════════════════════
def _get_token() -> str:
    return (os.environ.get("FINMIND_TOKEN", "") or
            os.environ.get("FM_TOKEN", ""))


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_monthly_revenue(stock_id: str, months: int = 18) -> pd.DataFrame:
    """抓單股近 N 月營收（FinMind TaiwanStockMonthRevenue）。

    Args:
        stock_id: 純台股代碼如 '2330'
        months: 回溯月數（預設 18 = 12 YoY 基期 + 6 分析窗口緩衝）

    Returns:
        DataFrame columns: date / revenue / revenue_year / revenue_month
        失敗回空 DataFrame
    """
    import datetime as _dt

    import requests as _rq

    _tok = _get_token()
    if not _tok:
        return pd.DataFrame()
    _end = _dt.date.today()
    _start = (_end - _dt.timedelta(days=months * 31 + 31)).strftime("%Y-%m-%d")
    try:
        _r = _rq.get(
            FINMIND_URL,
            params={
                "dataset": "TaiwanStockMonthRevenue",
                "data_id": stock_id,
                "start_date": _start,
                "token": _tok,
            },
            headers={"Authorization": f"Bearer {_tok}"},
            timeout=20,
        )
        _j = _r.json()
        if _j.get("status") != 200 or not _j.get("data"):
            return pd.DataFrame()
        _df = pd.DataFrame(_j["data"])
        if "revenue" not in _df.columns:
            return pd.DataFrame()
        if "date" not in _df.columns and "revenue_year" in _df.columns:
            _df["date"] = (
                _df["revenue_year"].astype(str) + "-" +
                _df["revenue_month"].astype(str).str.zfill(2) + "-01"
            )
        _df["date"] = pd.to_datetime(_df["date"], errors="coerce")
        _df = _df.dropna(subset=["date", "revenue"]).sort_values("date").reset_index(drop=True)
        return _df[["date", "revenue", "revenue_year", "revenue_month"]] if all(
            c in _df.columns for c in ["revenue_year", "revenue_month"]
        ) else _df[["date", "revenue"]]
    except Exception as _e:
        print(f"[mrev-screener] fetch {stock_id} 失敗: {type(_e).__name__}: {_e}")
        return pd.DataFrame()


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_batch_monthly_revenue(months: int = 18) -> pd.DataFrame:
    """一次抓全市場月營收（不帶 data_id，避開逐股迴圈）。

    Args:
        months: 回溯月數（預設 18）

    Returns:
        DataFrame columns: stock_id / date / revenue（多股長表）
        失敗或無 token 回空 DataFrame
    """
    import datetime as _dt

    import requests as _rq

    _tok = _get_token()
    if not _tok:
        return pd.DataFrame()
    _end = _dt.date.today()
    _start = (_end - _dt.timedelta(days=months * 31 + 31)).strftime("%Y-%m-%d")
    try:
        _r = _rq.get(
            FINMIND_URL,
            params={
                "dataset": "TaiwanStockMonthRevenue",
                "start_date": _start,
                "token": _tok,
            },
            headers={"Authorization": f"Bearer {_tok}"},
            timeout=60,
        )
        _j = _r.json()
        if _j.get("status") != 200 or not _j.get("data"):
            print(f"[mrev-screener] batch status={_j.get('status')} msg={_j.get('msg', '')}")
            return pd.DataFrame()
        _df = pd.DataFrame(_j["data"])
        if "revenue" not in _df.columns or "stock_id" not in _df.columns:
            return pd.DataFrame()
        if "date" not in _df.columns and "revenue_year" in _df.columns:
            _df["date"] = (
                _df["revenue_year"].astype(str) + "-" +
                _df["revenue_month"].astype(str).str.zfill(2) + "-01"
            )
        _df["date"] = pd.to_datetime(_df["date"], errors="coerce")
        _df = _df.dropna(subset=["date", "revenue", "stock_id"])
        return _df[["stock_id", "date", "revenue"]].sort_values(["stock_id", "date"]).reset_index(drop=True)
    except Exception as _e:
        print(f"[mrev-screener] batch fetch 失敗: {type(_e).__name__}: {_e}")
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# ② 趨勢計算層（純函式 — 不碰 streamlit / 網路）
# ══════════════════════════════════════════════════════════════════════════════
def compute_yoy_mom(df_stock: pd.DataFrame) -> dict[str, Any]:
    """對單股月營收序列計算近 3 月 YoY + 末月 MoM。

    Args:
        df_stock: DataFrame with [date, revenue]，按 date 升冪排序

    Returns:
        dict: {
          'last_date': pd.Timestamp | None,
          'last_revenue': float | None,
          'yoy_last3': list[float | None] — [M-2, M-1, M] 的 YoY%（缺基期為 None）,
          'mom_last': float | None — 末月 MoM%,
          'months_available': int,
        }
    """
    if df_stock is None or df_stock.empty or "revenue" not in df_stock.columns:
        return {"last_date": None, "last_revenue": None, "yoy_last3": [],
                "mom_last": None, "months_available": 0}
    _df = df_stock.copy()
    if "date" in _df.columns:
        _df = _df.sort_values("date").reset_index(drop=True)
    _rev = pd.to_numeric(_df["revenue"], errors="coerce").tolist()
    _dates = _df["date"].tolist() if "date" in _df.columns else [None] * len(_rev)
    _n = len(_rev)
    if _n == 0 or _rev[-1] is None:
        return {"last_date": None, "last_revenue": None, "yoy_last3": [],
                "mom_last": None, "months_available": 0}

    # YoY: 末 3 月相對 12 個月前
    _yoy_last3: list[float | None] = []
    for _off in (2, 1, 0):  # M-2, M-1, M（時序）
        _idx_curr = _n - 1 - _off
        _idx_base = _idx_curr - 12
        if _idx_curr < 0 or _idx_base < 0:
            _yoy_last3.append(None)
            continue
        _curr = _rev[_idx_curr]
        _base = _rev[_idx_base]
        if _curr is None or _base is None or _base == 0:
            _yoy_last3.append(None)
            continue
        _yoy_last3.append((_curr / _base - 1.0) * 100.0)

    # MoM: 末月 vs 上月
    _mom: float | None = None
    if _n >= 2 and _rev[-1] is not None and _rev[-2] is not None and _rev[-2] != 0:
        _mom = (_rev[-1] / _rev[-2] - 1.0) * 100.0

    return {
        "last_date": _dates[-1],
        "last_revenue": float(_rev[-1]) if _rev[-1] is not None else None,
        "yoy_last3": _yoy_last3,
        "mom_last": _mom,
        "months_available": _n,
    }


def classify_trend(stats: dict[str, Any], yoy_threshold: float = 15.0) -> str:
    """根據 YoY + MoM 雙條件分類趨勢。

    Args:
        stats: compute_yoy_mom() 回傳 dict
        yoy_threshold: 強進步/強退步門檻 %，預設 15.0

    Returns:
        'strong_up' / 'up' / 'strong_down' / 'down' / 'neutral' / 'insufficient'
    """
    _yoy3 = stats.get("yoy_last3") or []
    _mom = stats.get("mom_last")

    # 資料完整性檢查：需要 3 個 YoY + 1 個 MoM 全部非 None
    if len(_yoy3) < 3 or any(y is None for y in _yoy3) or _mom is None:
        return "insufficient"

    _all_strong_up = all(y >= yoy_threshold for y in _yoy3)
    _all_up = all(y > 0 for y in _yoy3)
    _all_strong_down = all(y <= -yoy_threshold for y in _yoy3)
    _all_down = all(y < 0 for y in _yoy3)

    if _all_strong_up and _mom >= 0:
        return "strong_up"
    if _all_strong_down and _mom <= 0:
        return "strong_down"
    if _all_up and _mom >= 0:
        return "up"
    if _all_down and _mom <= 0:
        return "down"
    return "neutral"


# ══════════════════════════════════════════════════════════════════════════════
# ③ 批次篩選層
# ══════════════════════════════════════════════════════════════════════════════
def screen_from_batch(
    df_batch: pd.DataFrame,
    yoy_threshold: float = 15.0,
    name_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """從 batch fetch 結果分組計算每股趨勢。

    Args:
        df_batch: fetch_batch_monthly_revenue() 結果（含 stock_id / date / revenue）
        yoy_threshold: 強進步/強退步門檻 %
        name_map: 可選 {sid: name} 對照（來自 TWSE BWIBBU_d）

    Returns:
        DataFrame: 代碼 / 名稱 / 末月日期 / 末月營收(億) / YoY-2 / YoY-1 / YoY / MoM / 趨勢
    """
    if df_batch is None or df_batch.empty:
        return pd.DataFrame()
    _rows = []
    _name_map = name_map or {}
    for _sid, _grp in df_batch.groupby("stock_id"):
        _stats = compute_yoy_mom(_grp)
        _trend = classify_trend(_stats, yoy_threshold=yoy_threshold)
        _rows.append({
            "代碼": _sid,
            "名稱": _name_map.get(str(_sid), ""),
            "末月日期": _stats["last_date"].strftime("%Y-%m") if _stats["last_date"] is not None else "",
            "末月營收(億)": (round(_stats["last_revenue"] / 1e8, 2)
                          if _stats["last_revenue"] is not None else None),
            "YoY-2(%)": _yoy_round(_stats["yoy_last3"], 0),
            "YoY-1(%)": _yoy_round(_stats["yoy_last3"], 1),
            "YoY(%)":   _yoy_round(_stats["yoy_last3"], 2),
            "MoM(%)":   round(_stats["mom_last"], 2) if _stats["mom_last"] is not None else None,
            "趨勢":     TREND_LABELS.get(_trend, _trend),
            "_trend_key": _trend,
        })
    return pd.DataFrame(_rows)


def _yoy_round(yoy_list: list[float | None], idx: int) -> float | None:
    if len(yoy_list) <= idx:
        return None
    _v = yoy_list[idx]
    return round(_v, 2) if _v is not None else None


def filter_by_mode(df_result: pd.DataFrame, mode: str) -> pd.DataFrame:
    """依模式過濾 screen_from_batch 結果。

    Args:
        df_result: screen_from_batch 輸出（含 _trend_key 欄）
        mode: 'all' / 'up' / 'strong_up' / 'down' / 'strong_down' / 'any_up' / 'any_down'

    Returns:
        過濾後 DataFrame（保留 _trend_key 供下游用）
    """
    if df_result is None or df_result.empty or mode == "all":
        return df_result
    if "_trend_key" not in df_result.columns:
        return df_result
    if mode == "any_up":
        return df_result[df_result["_trend_key"].isin(["up", "strong_up"])].reset_index(drop=True)
    if mode == "any_down":
        return df_result[df_result["_trend_key"].isin(["down", "strong_down"])].reset_index(drop=True)
    return df_result[df_result["_trend_key"] == mode].reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# ④ Streamlit UI
# ══════════════════════════════════════════════════════════════════════════════
def render_monthly_revenue_screener():
    """月營收進退篩選器主畫面。"""
    st.markdown("### 📈 月營收進退篩選")
    st.caption(
        "🎯 **判斷基準（YoY + MoM 雙條件）**：近 3 月年增率全正且末月月增率 ≥ 0 → 進步；"
        "全負且末月月增率 ≤ 0 → 退步。資料源：FinMind `TaiwanStockMonthRevenue`（每月 10 日公告）"
    )

    if not _get_token():
        st.error(
            "🔴 **未偵測到 FINMIND_TOKEN 環境變數**\n\n"
            "本功能需 FinMind sponsor tier 抓月營收歷史。請至「🔎 資料診斷」Tab 檢查 API 金鑰狀態。"
        )
        return

    with st.expander("💡 判斷規則細節（強進步 / 進步 / 退步 / 強退步）", expanded=False):
        st.markdown(
            "- **🚀 強進步** = 近 3 月 YoY 全 ≥ 門檻（預設 +15%）且末月 MoM ≥ 0\n"
            "- **📈 進步**   = 近 3 月 YoY 全 > 0% 且末月 MoM ≥ 0\n"
            "- **🔻 強退步** = 近 3 月 YoY 全 ≤ -門檻（預設 -15%）且末月 MoM ≤ 0\n"
            "- **📉 退步**   = 近 3 月 YoY 全 < 0% 且末月 MoM ≤ 0\n"
            "- **➖ 中性**   = 其餘情境（震盪/拐點未確認/混合方向）\n"
            "- **⚪ 資料不足** = 不足 15 個月歷史（含 12 個月 YoY 基期 + 3 個月當期）；上市未滿 1.5 年常見\n\n"
            "**為什麼要 YoY + MoM 雙條件？** YoY 排除季節性偏差（如 1 月電子業淡季），MoM 補捉「近期動量」防止靠基期低估的假進步。"
        )

    # ── 篩選條件 ──────────────────────────────────────────
    _c1, _c2, _c3 = st.columns([1, 1, 1])
    with _c1:
        _yoy_thr = st.slider(
            "強進步 / 強退步 YoY 門檻 (%)", 5.0, 50.0, 15.0, 1.0,
            help="近 3 月 YoY 全部超過此門檻 → 強進步；全部低於 -此門檻 → 強退步",
            key="mrev_yoy_threshold",
        )
    with _c2:
        _mode_label = st.radio(
            "篩選模式",
            ["🚀 強進步", "📈 進步（含強進步）", "📉 退步（含強退步）",
             "🔻 強退步", "全部"],
            index=1,
            key="mrev_mode",
            horizontal=False,
        )
        _mode_key = {
            "🚀 強進步": "strong_up",
            "📈 進步（含強進步）": "any_up",
            "📉 退步（含強退步）": "any_down",
            "🔻 強退步": "strong_down",
            "全部": "all",
        }[_mode_label]
    with _c3:
        _topn = st.number_input(
            "顯示上限筆數", min_value=10, max_value=500, value=100, step=10,
            help="排序後取前 N 筆（依末月 YoY 絕對值排序）",
            key="mrev_topn",
        )

    if st.button("📡 抓取全市場月營收 + 計算", key="mrev_fetch_btn", type="primary"):
        with st.spinner("正在抓全市場月營收（FinMind batch，約 15-60 秒）…"):
            _df_batch = fetch_batch_monthly_revenue(months=18)
        if _df_batch.empty:
            st.error(
                "🔴 **全市場月營收抓取失敗**\n\n"
                "可能原因：① FinMind tier 不支援 batch（無 data_id） ② token 過期 ③ 網路逾時\n\n"
                "👉 請至「🔎 資料診斷」Tab 檢查 API 狀態"
            )
            return
        st.success(f"✅ 抓到 **{_df_batch['stock_id'].nunique()}** 檔股票 × **{_df_batch['date'].nunique()}** 個月資料")
        st.session_state["_mrev_batch"] = _df_batch

        # 同步抓 TWSE 名稱對照
        try:
            from yield_screener import fetch_twse_yield_pe
            _df_names = fetch_twse_yield_pe()
            if not _df_names.empty and "代碼" in _df_names.columns:
                st.session_state["_mrev_namemap"] = dict(zip(
                    _df_names["代碼"].astype(str),
                    _df_names.get("名稱", pd.Series([""] * len(_df_names))).astype(str),
                ))
        except Exception as _en:
            print(f"[mrev-screener] 名稱對照載入失敗: {_en}")
            st.session_state["_mrev_namemap"] = {}

    _df_batch = st.session_state.get("_mrev_batch")
    if _df_batch is None or _df_batch.empty:
        st.info("👆 請點擊「📡 抓取全市場月營收」開始")
        return

    # ── 計算 + 篩選 ─────────────────────────────────────────
    _namemap = st.session_state.get("_mrev_namemap", {})
    _df_screen = screen_from_batch(_df_batch, yoy_threshold=_yoy_thr, name_map=_namemap)
    _df_filtered = filter_by_mode(_df_screen, _mode_key)

    if _df_filtered.empty:
        st.warning(f"🟡 在「{_mode_label}」模式 + YoY 門檻 {_yoy_thr}% 下無符合標的，請放寬條件")
        return

    # 排序：依末月 YoY 絕對值降冪（強進步/退步浮上來）
    _df_filtered = _df_filtered.copy()
    _df_filtered["_abs_yoy"] = _df_filtered["YoY(%)"].abs()
    _df_filtered = _df_filtered.sort_values("_abs_yoy", ascending=False).head(int(_topn))
    _df_show = _df_filtered.drop(columns=["_abs_yoy", "_trend_key"])

    # ── Summary 卡 ─────────────────────────────────────────
    _summary_cols = st.columns(5)
    for _i, (_k, _label) in enumerate([
        ("strong_up", "🚀 強進步"),
        ("up", "📈 進步"),
        ("neutral", "➖ 中性"),
        ("down", "📉 退步"),
        ("strong_down", "🔻 強退步"),
    ]):
        _cnt = int((_df_screen["_trend_key"] == _k).sum())
        with _summary_cols[_i]:
            st.metric(_label, f"{_cnt} 檔")

    st.markdown(f"#### 📋 結果（共 {len(_df_show)} 檔 · 依 YoY 絕對值排序）")
    st.dataframe(_df_show, use_container_width=True, hide_index=True)

    # ── CSV 下載 ────────────────────────────────────────────
    _csv = _df_show.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "💾 下載結果 CSV",
        data=_csv,
        file_name=f"monthly_revenue_screen_{_mode_key}_yoy{int(_yoy_thr)}.csv",
        mime="text/csv",
        key="mrev_csv_dl",
    )
