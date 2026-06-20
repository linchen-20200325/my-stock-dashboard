from data_config import CACHE_TTL
"""monthly_revenue_screener.py ?????園脤蝭拚??

v18.180 ?啣??嚗祟?詨?∟? 3 ?????嗅??整脫郊 / ?甇乓隅?Ｙ?璅???

?斗?箸?嚗oY + MoM ??隞塚?嚗?
  ??撘琿脫郊 = 餈?3 ??YoY ????+threshold% 銝??急? MoM ??0
  ???脫郊   = 餈?3 ??YoY ??> 0% 銝??急? MoM ??0
  ??撘琿甇?= 餈?3 ??YoY ????-threshold% 銝??急? MoM ??0
  ???甇?  = 餈?3 ??YoY ??< 0% 銝??急? MoM ??0
  ??銝剜?  = ?園???
  ??鞈?銝雲 = 銝雲 15 ??甇瑕嚗 12 ?? YoY ?箸? + 3 ???嗆?嚗?

鞈?皞?
  ??FinMind TaiwanStockMonthRevenue嚗???10 ?亙??
  ??TWSE OpenAPI BWIBBU_d嚗??∠巨?迂撠嚗?

?嗆?瘙箇?嚗?
  ??蝝撘?+ Streamlit UI ?嚗etch_* 韏?@st.cache_data(ttl=CACHE_TTL["daily_snapshot"]) 6 撠?敹怠?
  ???∪? yield_screener.py 瞍? UI pattern
  ???典??湔???= FinMind 銝葆 data_id 銝甈⊥??????砍??閮?嚗??1700 瑼 API 憸冽嚗?
"""
from __future__ import annotations

import os
from typing import Any

import pandas as pd
import streamlit as st

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

# ?斗璅∪? ??銝剜? label
TREND_LABELS = {
    "strong_up": "?? 撘琿脫郊",
    "up": "?? ?脫郊",
    "strong_down": "? 撘琿甇?,
    "down": "?? ?甇?,
    "neutral": "??銝剜?,
    "insufficient": "??鞈?銝雲",
}


# ??????????????????????????????????????????????????????????????????????????????
# ??鞈???撅?
# ??????????????????????????????????????????????????????????????????????????????
def _get_token() -> str:
    return (os.environ.get("FINMIND_TOKEN", "") or
            os.environ.get("FM_TOKEN", ""))


@st.cache_data(ttl=CACHE_TTL["daily_snapshot"], show_spinner=False)
def fetch_monthly_revenue(stock_id: str, months: int = 18) -> pd.DataFrame:
    """??∟? N ???塚?FinMind TaiwanStockMonthRevenue嚗?

    Args:
        stock_id: 蝝?∩誨蝣澆? '2330'
        months: ?滲?嚗?閮?18 = 12 YoY ?箸? + 6 ??蝒蝺抵?嚗?

    Returns:
        DataFrame columns: date / revenue / revenue_year / revenue_month
        憭望??征 DataFrame
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
        print(f"[mrev-screener] fetch {stock_id} 憭望?: {type(_e).__name__}: {_e}")
        return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL["daily_snapshot"], show_spinner=False)
def fetch_batch_monthly_revenue(months: int = 18) -> pd.DataFrame:
    """銝甈⊥??典??湔??嚗?撣?data_id嚗?餈游?嚗?

    Args:
        months: ?滲?嚗?閮?18嚗?

    Returns:
        DataFrame columns: stock_id / date / revenue嚗??⊿銵剁?
        憭望?? token ?征 DataFrame
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
        print(f"[mrev-screener] batch fetch 憭望?: {type(_e).__name__}: {_e}")
        return pd.DataFrame()


# ??????????????????????????????????????????????????????????????????????????????
# ??頞典閮?撅歹?蝝撘???銝１ streamlit / 蝬脰楝嚗?
# ??????????????????????????????????????????????????????????????????????????????
def compute_yoy_mom(df_stock: pd.DataFrame) -> dict[str, Any]:
    """撠?⊥??摨?閮?餈?3 ??YoY + ?急? MoM??

    Args:
        df_stock: DataFrame with [date, revenue]嚗? date ???

    Returns:
        dict: {
          'last_date': pd.Timestamp | None,
          'last_revenue': float | None,
          'yoy_last3': list[float | None] ??[M-2, M-1, M] ??YoY%嚗撩?箸???None嚗?
          'mom_last': float | None ???急? MoM%,
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

    # YoY: ??3 ?撠?12 ????
    _yoy_last3: list[float | None] = []
    for _off in (2, 1, 0):  # M-2, M-1, M嚗?摨?
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

    # MoM: ?急? vs 銝?
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
    """?寞? YoY + MoM ??隞嗅?憿隅?Ｕ?

    Args:
        stats: compute_yoy_mom() ? dict
        yoy_threshold: 撘琿脫郊/撘琿甇仿?瑼?%嚗?閮?15.0

    Returns:
        'strong_up' / 'up' / 'strong_down' / 'down' / 'neutral' / 'insufficient'
    """
    _yoy3 = stats.get("yoy_last3") or []
    _mom = stats.get("mom_last")

    # 鞈?摰?扳炎?伐??閬?3 ??YoY + 1 ??MoM ?券??None
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


# ??????????????????????????????????????????????????????????????????????????????
# ???寞活蝭拚撅?
# ??????????????????????????????????????????????????????????????????????????????
def screen_from_batch(
    df_batch: pd.DataFrame,
    yoy_threshold: float = 15.0,
    name_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """敺?batch fetch 蝯???閮?瘥頞典??

    Args:
        df_batch: fetch_batch_monthly_revenue() 蝯?嚗 stock_id / date / revenue嚗?
        yoy_threshold: 撘琿脫郊/撘琿甇仿?瑼?%
        name_map: ?舫 {sid: name} 撠嚗???TWSE BWIBBU_d嚗?

    Returns:
        DataFrame: 隞?Ⅳ / ?迂 / ?急??交? / ?急??(?? / YoY-2 / YoY-1 / YoY / MoM / 頞典
    """
    if df_batch is None or df_batch.empty:
        return pd.DataFrame()
    _rows = []
    _name_map = name_map or {}
    for _sid, _grp in df_batch.groupby("stock_id"):
        _stats = compute_yoy_mom(_grp)
        _trend = classify_trend(_stats, yoy_threshold=yoy_threshold)
        _rows.append({
            "隞?Ⅳ": _sid,
            "?迂": _name_map.get(str(_sid), ""),
            "?急??交?": _stats["last_date"].strftime("%Y-%m") if _stats["last_date"] is not None else "",
            "?急??(??": (round(_stats["last_revenue"] / 1e8, 2)
                          if _stats["last_revenue"] is not None else None),
            "YoY-2(%)": _yoy_round(_stats["yoy_last3"], 0),
            "YoY-1(%)": _yoy_round(_stats["yoy_last3"], 1),
            "YoY(%)":   _yoy_round(_stats["yoy_last3"], 2),
            "MoM(%)":   round(_stats["mom_last"], 2) if _stats["mom_last"] is not None else None,
            "頞典":     TREND_LABELS.get(_trend, _trend),
            "_trend_key": _trend,
        })
    return pd.DataFrame(_rows)


def _yoy_round(yoy_list: list[float | None], idx: int) -> float | None:
    if len(yoy_list) <= idx:
        return None
    _v = yoy_list[idx]
    return round(_v, 2) if _v is not None else None


def filter_by_mode(df_result: pd.DataFrame, mode: str) -> pd.DataFrame:
    """靘芋撘?瞈?screen_from_batch 蝯???

    Args:
        df_result: screen_from_batch 頛詨嚗 _trend_key 甈?
        mode: 'all' / 'up' / 'strong_up' / 'down' / 'strong_down' / 'any_up' / 'any_down'

    Returns:
        ?蕪敺?DataFrame嚗???_trend_key 靘?皜貊嚗?
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


# ??????????????????????????????????????????????????????????????????????????????
# ??Streamlit UI
# ??????????????????????????????????????????????????????????????????????????????
def render_monthly_revenue_screener():
    """???園脤蝭拚?其蜓?恍??""
    st.markdown("### ?? ???園脤蝭拚")
    st.caption(
        "? **?斗?箸?嚗oY + MoM ??隞塚?**嚗? 3 ?僑憓??冽迤銝??憓? ??0 ???脫郊嚗?
        "?刻?銝??憓? ??0 ???甇乓???嚗inMind `TaiwanStockMonthRevenue`嚗???10 ?亙??"
    )

    if not _get_token():
        st.error(
            "? **?芸皜砍 FINMIND_TOKEN ?啣?霈**\n\n"
            "?砍??賡? FinMind sponsor tier ???甇瑕???喋??鞈?閮箸?ab 瑼Ｘ API ????
        )
        return

    with st.expander("? ?斗閬?蝝啁?嚗撥?脫郊 / ?脫郊 / ?甇?/ 撘琿甇伐?", expanded=False):
        st.markdown(
            "- **?? 撘琿脫郊** = 餈?3 ??YoY ?????瑼鳴??身 +15%嚗??急? MoM ??0\n"
            "- **?? ?脫郊**   = 餈?3 ??YoY ??> 0% 銝??MoM ??0\n"
            "- **? 撘琿甇?* = 餈?3 ??YoY ????-?瑼鳴??身 -15%嚗??急? MoM ??0\n"
            "- **?? ?甇?*   = 餈?3 ??YoY ??< 0% 銝??MoM ??0\n"
            "- **??銝剜?*   = ?園???嚗??????芰Ⅱ隤?瘛瑕??孵?嚗n"
            "- **??鞈?銝雲** = 銝雲 15 ??甇瑕嚗 12 ?? YoY ?箸? + 3 ???嗆?嚗?銝??芣遛 1.5 撟游虜閬n\n"
            "**?箔?暻潸? YoY + MoM ??隞塚?** YoY ?摮???批?撌殷?憒?1 ?摮平瘛∪迤嚗?MoM 鋆??????甇ａ??箸?雿摯???脫郊??
        )

    # ?? 蝭拚璇辣 ??????????????????????????????????????????
    _c1, _c2, _c3 = st.columns([1, 1, 1])
    with _c1:
        _yoy_thr = st.slider(
            "撘琿脫郊 / 撘琿甇?YoY ?瑼?(%)", 5.0, 50.0, 15.0, 1.0,
            help="餈?3 ??YoY ?券頞?甇日?瑼???撘琿脫郊嚗?其???-甇日?瑼???撘琿甇?,
            key="mrev_yoy_threshold",
        )
    with _c2:
        _mode_label = st.radio(
            "蝭拚璅∪?",
            ["?? 撘琿脫郊", "?? ?脫郊嚗撘琿脫郊嚗?, "?? ?甇伐??怠撥?甇伐?",
             "? 撘琿甇?, "?券"],
            index=1,
            key="mrev_mode",
            horizontal=False,
        )
        _mode_key = {
            "?? 撘琿脫郊": "strong_up",
            "?? ?脫郊嚗撘琿脫郊嚗?: "any_up",
            "?? ?甇伐??怠撥?甇伐?": "any_down",
            "? 撘琿甇?: "strong_down",
            "?券": "all",
        }[_mode_label]
    with _c3:
        _topn = st.number_input(
            "憿舐內銝?蝑", min_value=10, max_value=500, value=100, step=10,
            help="??敺???N 蝑?靘??YoY 蝯??潭?摨?",
            key="mrev_topn",
        )

    if st.button("? ???典??湔?? + 閮?", key="mrev_fetch_btn", type="primary"):
        with st.spinner("甇??撣???塚?FinMind batch嚗? 15-60 蝘???):
            _df_batch = fetch_batch_monthly_revenue(months=18)
        if _df_batch.empty:
            st.error(
                "? **?典??湔????憭望?**\n\n"
                "?航??嚗? FinMind tier 銝??batch嚗 data_id嚗???token ?? ??蝬脰楝?暹?\n\n"
                "?? 隢???鞈?閮箸?ab 瑼Ｘ API ???
            )
            return
        st.success(f"??? **{_df_batch['stock_id'].nunique()}** 瑼蟡?? **{_df_batch['date'].nunique()}** ??鞈?")
        st.session_state["_mrev_batch"] = _df_batch

        # ?郊??TWSE ?迂撠
        try:
            from yield_screener import fetch_twse_yield_pe
            _df_names = fetch_twse_yield_pe()
            if not _df_names.empty and "隞?Ⅳ" in _df_names.columns:
                st.session_state["_mrev_namemap"] = dict(zip(
                    _df_names["隞?Ⅳ"].astype(str),
                    _df_names.get("?迂", pd.Series([""] * len(_df_names))).astype(str),
                ))
        except Exception as _en:
            print(f"[mrev-screener] ?迂撠頛憭望?: {_en}")
            st.session_state["_mrev_namemap"] = {}

    _df_batch = st.session_state.get("_mrev_batch")
    if _df_batch is None or _df_batch.empty:
        st.info("?? 隢???????典??湔????憪?)
        return

    # ?? 閮? + 蝭拚 ?????????????????????????????????????????
    _namemap = st.session_state.get("_mrev_namemap", {})
    _df_screen = screen_from_batch(_df_batch, yoy_threshold=_yoy_thr, name_map=_namemap)
    _df_filtered = filter_by_mode(_df_screen, _mode_key)

    if _df_filtered.empty:
        st.warning(f"? ?具_mode_label}?芋撘?+ YoY ?瑼?{_yoy_thr}% 銝蝚血?璅?嚗??曉祝璇辣")
        return

    # ??嚗??急? YoY 蝯??潮??迎?撘琿脫郊/?甇交筑銝?嚗?
    _df_filtered = _df_filtered.copy()
    _df_filtered["_abs_yoy"] = _df_filtered["YoY(%)"].abs()
    _df_filtered = _df_filtered.sort_values("_abs_yoy", ascending=False).head(int(_topn))
    _df_show = _df_filtered.drop(columns=["_abs_yoy", "_trend_key"])

    # ?? Summary ???????????????????????????????????????????
    _summary_cols = st.columns(5)
    for _i, (_k, _label) in enumerate([
        ("strong_up", "?? 撘琿脫郊"),
        ("up", "?? ?脫郊"),
        ("neutral", "??銝剜?),
        ("down", "?? ?甇?),
        ("strong_down", "? 撘琿甇?),
    ]):
        _cnt = int((_df_screen["_trend_key"] == _k).sum())
        with _summary_cols[_i]:
            st.metric(_label, f"{_cnt} 瑼?)

    st.markdown(f"#### ?? 蝯?嚗 {len(_df_show)} 瑼?繚 靘?YoY 蝯??潭?摨?")
    st.dataframe(_df_show, use_container_width=True, hide_index=True)

    # ?? CSV 銝? ????????????????????????????????????????????
    _csv = _df_show.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "? 銝?蝯? CSV",
        data=_csv,
        file_name=f"monthly_revenue_screen_{_mode_key}_yoy{int(_yoy_thr)}.csv",
        mime="text/csv",
        key="mrev_csv_dl",
    )

