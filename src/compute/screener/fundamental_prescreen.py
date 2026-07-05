"""src/compute/screener/fundamental_prescreen.py — 全台股基本面初篩(L2 純函式,向量化)。

Phase 2 選股網「全市場基本面漏斗」的核心:讀 MOPS 全市場季快照(每檔一列的
DataFrame),對整個市場一次算 4 項基本面,**四項全過**才入選(survivor)。輸出交由
L3 service → 選股網下游深掃/評分。

與同 package `fundamental_screener.py` 的區別(不重複):
  - fundamental_screener:per-stock dict,需月營收 + QoQ,三率用「QoQ 且 YoY」,
    無負債比/淨流動值 → 進階「轉強」篩選。
  - 本檔(prescreen):全市場 DataFrame 向量化,三率**YoY-only**(本季 vs 去年同季,
    避季節性),含負債比 + 淨流動值 → 入池前的基本面地板。

4 項檢查(門檻走 shared/fundamental_prescreen_thresholds.py SSOT):
  ① pass_debt         負債比 = total_liab / total_assets < DEBT_RATIO_MAX(50%)
  ② pass_three_rise   三率三升 YoY:毛利率/營益率/淨利率 本季『同時嚴格 >』去年同季
  ③ pass_net_current  淨流動值 = current_assets - total_liab > 0(保守版葛拉漢)
  ④ pass_eps_positive 本季 eps > EPS_MIN(獲利為正)

§1 fail-loud / §3.3 反捏造:
  - 缺欄 → raise(不猜);缺『值』(NaN,如金融業無營收)→ 該檢查判 False(誠實標
    「無法驗證通過」,不 fillna(0) 假裝通過)。金融股因無營收 → 三率算不出 → 自然
    被排除,符合價值-margin 選股慣例。
  - 除法一律 guard 分母 > 0,分母 ≤0/NaN → 比率 NaN(不 silent 0、不 inf)。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from shared.fundamental_prescreen_thresholds import (
    DEBT_RATIO_MAX,
    EPS_MIN,
    PRESCREEN_REQUIRED_PASSES,
)

# 輸入必備欄(缺 → fail-loud raise)。provenance / market 等額外欄不強制。
REQUIRED_COLS = (
    "stock_id", "revenue", "gross_profit", "op_income", "net_income",
    "eps", "total_assets", "total_liab", "current_assets",
)

# 輸出欄順序(UI / 下游依此取用)。
_PASS_COLS = ("pass_debt", "pass_three_rise", "pass_net_current", "pass_eps_positive")


def _safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    """num/den;分母 ≤0 或 NaN → NaN(不 silent 0、不 inf)。§4.4 大數除小數 guard。"""
    den_ok = den.where(den > 0)          # ≤0 → NaN
    return num / den_ok


def _margins(df: pd.DataFrame) -> pd.DataFrame:
    """由原始金額算三率(毛利率/營益率/淨利率),index 對齊輸入。revenue≤0 → NaN。"""
    rev = df["revenue"]
    return pd.DataFrame({
        "gross_margin": _safe_ratio(df["gross_profit"], rev),
        "op_margin": _safe_ratio(df["op_income"], rev),
        "net_margin": _safe_ratio(df["net_income"], rev),
    }, index=df.index)


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    """驗證必備欄 + stock_id 轉 str 去重(keep first);數值欄轉 numeric。"""
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"fundamental_prescreen 缺必備欄:{missing}")
    out = df.copy()
    out["stock_id"] = out["stock_id"].astype(str).str.strip()
    out = out.drop_duplicates(subset="stock_id", keep="first")
    for c in REQUIRED_COLS:
        if c != "stock_id":
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def run_fundamental_prescreen(
    current: pd.DataFrame,
    prev: pd.DataFrame | None,
) -> pd.DataFrame:
    """全台股基本面 4 項初篩(純函式,無 I/O)。

    Args:
        current: 最新季全市場,每檔一列,須含 REQUIRED_COLS。
        prev:    去年同季(供三率三升 YoY);同 schema。None / 空 → 三率三升一律不過
                 (無去年同季無法比 YoY,誠實判 False,不猜)。

    Returns:
        DataFrame(依 stock_id 排序,唯一),欄:
          stock_id, eps,
          debt_ratio, gross_margin, op_margin, net_margin(本季比率,供顯示/下游),
          pass_debt / pass_three_rise / pass_net_current / pass_eps_positive(4 布林),
          pass_count(0-4), survivor(bool = 四項全過)。
        current 空 → 回空 DataFrame(帶完整欄位)。
    """
    empty_out = pd.DataFrame(columns=[
        "stock_id", "eps", "debt_ratio", "gross_margin", "op_margin", "net_margin",
        *_PASS_COLS, "pass_count", "survivor",
    ])
    if current is None or current.empty:
        return empty_out

    cur = _prep(current)
    out = pd.DataFrame({"stock_id": cur["stock_id"].to_numpy()})
    out["eps"] = cur["eps"].to_numpy()

    # ① 負債比
    out["debt_ratio"] = _safe_ratio(cur["total_liab"], cur["total_assets"]).to_numpy()

    # 本季三率
    m_c = _margins(cur)
    out["gross_margin"] = m_c["gross_margin"].to_numpy()
    out["op_margin"] = m_c["op_margin"].to_numpy()
    out["net_margin"] = m_c["net_margin"].to_numpy()

    # ② 三率三升 YoY:去年同季三率 map 到本季 stock_id(無 prev → 全 NaN → 不過)
    if prev is not None and not prev.empty:
        pv = _prep(prev)
        m_p = _margins(pv)
        m_p.index = pv["stock_id"].to_numpy()          # 以 stock_id 為 index 供 map
        gm_p = out["stock_id"].map(m_p["gross_margin"])
        om_p = out["stock_id"].map(m_p["op_margin"])
        nm_p = out["stock_id"].map(m_p["net_margin"])
    else:
        gm_p = om_p = nm_p = pd.Series(np.nan, index=out.index)

    # NaN 參與比較 → False(pandas 語意),正好符合「缺值無法驗證 → 不過」
    out["pass_three_rise"] = (
        (out["gross_margin"] > gm_p.to_numpy())
        & (out["op_margin"] > om_p.to_numpy())
        & (out["net_margin"] > nm_p.to_numpy())
    )

    # ① 判定
    out["pass_debt"] = out["debt_ratio"] < DEBT_RATIO_MAX

    # ③ 淨流動值 = 流動資產 - 總負債 > 0(NaN → False)
    net_current = cur["current_assets"].to_numpy() - cur["total_liab"].to_numpy()
    out["pass_net_current"] = net_current > 0

    # ④ 獲利為正
    out["pass_eps_positive"] = out["eps"] > EPS_MIN

    # 布林化(NaN 比較已產生 False,這裡確保 dtype 為 bool)
    for c in _PASS_COLS:
        out[c] = out[c].fillna(False).astype(bool)

    out["pass_count"] = out[list(_PASS_COLS)].sum(axis=1).astype(int)
    out["survivor"] = out["pass_count"] == PRESCREEN_REQUIRED_PASSES

    return out.sort_values("stock_id").reset_index(drop=True)


def survivors_only(prescreen_df: pd.DataFrame) -> pd.DataFrame:
    """便捷:抽出 survivor=True 子集(四項全過),依 eps 由大到小排。"""
    if prescreen_df is None or prescreen_df.empty or "survivor" not in prescreen_df.columns:
        return prescreen_df
    out = prescreen_df[prescreen_df["survivor"]].copy()
    return out.sort_values("eps", ascending=False).reset_index(drop=True)
