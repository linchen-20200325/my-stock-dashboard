"""src/compute/screener/cross_quarter_trends.py — 全台股跨季基本面趨勢(L2 純函式).

吃「全部季別」的全市場快照(long-form,每檔每季一列),對**比率型指標**做跨季線性
趨勢,揭露「逐季在變好還變壞」。比率對季節性較穩健(不像 QoQ 金額會被 Q1淡/Q4旺 汙染)。

⚠️ 輸入損益欄是「年初至今累計」(AUD-C4,2026-10-15 查證):
  `data_cache/fundamentals/{sii,otc}_*.parquet`(MOPS t163sb04)的 revenue / gross_profit /
  op_income / net_income / eps 為**年初至今累計**(Q2 = 上半年、Q4 = 全年),不是單季。
  實測例:2330 114Q3 revenue = 2,762,963,851、114Q4 = 3,809,054,272(千元,全年累計)。
  ~~原本直接把累計值當逐季值算毛利率/營益率斜率~~ —— 有意識的修改,不是漏刪(2026-10-15,
  AUD-C4,客戶 Q3=A 拍板「先正確拆單季再算跨季趨勢」):累計比率逐季越來越像「年度平均」,
  斜率被跨季平均稀釋且 Q1 處斷崖重置,方向不代表單季在變好變壞。
  **現行**:斜率前先以 `ytd_to_single_quarter` 把**流量欄** revenue / gross_profit / op_income
  拆成單季(同一 roc_year 內 累計n − 累計(n−1);Q1 = 累計;不跨年相減),再算單季比率。
  - 存量欄(total_assets / total_liab)是期末時點值,**不相減**;負債比斜率不變。
  - EPS / net_income **不**單季化(本模組不用)。
  - ~~`revenue_yoy` **不改**:仍是「最新季的年初至今累計營收 vs 去年同期年初至今累計營收」
    (例:最新季為 115Q2 → 115 上半年 vs 114 上半年)。是否改成單季 YoY 屬客戶待裁示(PQ-C4-1)。~~
    —— 有意識的修改,不是漏刪(2026-10-16,客戶裁示 PQ-C4-1 = 推薦方案「單季對去年同季單季」)。
    舊定義的理由仍成立:累計對累計數學上自洽、季節性互相抵消,且不受前季缺/斷層影響;
    被權衡掉的原因:累計 YoY 把「最新一季」稀釋進年初以來的平均,最新季轉弱/轉強會被前幾季
    蓋過(量測日 2026-10-16:兩種算法皆算得出的 1886 檔中 244 檔正負號相反),與因子
    「最新季規模成長」的語意不符。
  - **現行** `revenue_yoy` = 單季營收(roc_year y, season s) / 單季營收(y−1, s) − 1,
    單季值取自同一個 `ytd_to_single_quarter`(sq_revenue)。錨定季 = 該檔「最新一個有累計營收」的季
    (與修前同一錨定規則,只換算式)。任一端單季 NaN(缺季 / 前季缺 / 口徑斷層)或去年同季單季
    營收 ≤ 0 → NaN;**錨定季單季 NaN 時不回退到更早的季**(回退 = 拿舊季冒充最新季)。

⚠️ 前進式凍結(forward_test)方法版本:**2026-10-15 起 trend 因子(favorable_count)改單季斜率**;
  `data_cache/forward_test/picks.parquet` 的 2026-07-22、2026-08-02、2026-09-02、2026-10-02
  四個 cohort 凍結時用的是**累計版**斜率(凍結紀錄不可改寫,picks.parquet 無方法版本欄)。
  **2026-10-16 起 favorable_count 的 revenue_yoy 因子亦改單季 YoY**(PQ-C4-1);上述四個 cohort
  凍結時用的是**累計對累計** YoY。程式內無方法版本常數 / 欄位可標記(凍結 schema 不改),
  方法切換紀錄以本段 + docs 決策紀錄為準。

⚠️ 資料限制(§1 誠實):
  ~~現有快照僅 5 季(114Q1–115Q1)、無 113 前。~~ —— 有意識的修改,不是漏刪(2026-10-15):
  季數會隨 cron 增加而漂移,不寫死(CLAUDE.md §8.2.A.0 規則 4)。量測日 2026-10-15 為
  6 季(114Q1–115Q2)、無 113 前;需要時現場量測 `data_cache/fundamentals/`。故
  - 趨勢用「線性斜率」而非「連續成長季數」(後者季數少 + QoQ 季節性會造假訊號)。
  - 營收 YoY 只算得出最新季 vs 去年同季一個點(無更早年可連續)。
  - 單季 YoY 需要「去年同季」的單季值:去年同季若 season ≥ 2,還需要去年同季的**前一季**快照
    (例:錨定 115Q2 → 需 114Q1、114Q2);缺 → NaN。
  - 單季化已知限制:
    (1) 跨版本差分:舊季快照不重抓,若前季事後更正,當季單季值會含更正額;
    (2) 保險業 115 年起 revenue 欄 NaN,疑 IFRS 17 口徑斷層(**未查證**)→ 該季單季 NaN;
    (3) 停業單位重分類等口徑斷層只能以「單季營收 < 0」偵測(→ 三欄 NaN + 計入
        `single_quarter_breaks`);相減後仍為正的扭曲**偵測不到**。
    (4) 斷層季的**下一季**仍以斷層季的累計值相減(斷層季只作廢它自己的單季值,不作廢累計):
        若斷層成因為重分類,斷層季累計與下一季累計屬同口徑 → 下一季單季值合理;
        否則異常可能**延續到下一季**,且該季不會被計入 `single_quarter_breaks`。
    (5) 前季累計為負(例:累計營收本身即為負)時,相減結果可能轉為正 → 不觸發「單季營收 < 0」,
        **無法偵測**;實例 6901 114Q4 單季營收 = −1,073,250 − (−1,089,714) = +16,464
        (毛利同值 → 單季毛利率剛好 1.0)。

4 個因子(方向語意寫死):
  - gross_margin_slope  單季毛利率跨季斜率, > 0 為佳(獲利品質走揚)
  - op_margin_slope     單季營益率跨季斜率, > 0 為佳(本業經營改善)
  - debt_ratio_slope    負債比(期末存量)跨季斜率, < 0 為佳(逐季去槓桿)
  - revenue_yoy         最新季**單季**營收 vs 去年同季單季營收, > 0 為佳(規模成長)
favorable_count = 上述有資料的因子中「方向為佳」的個數;favorable_of = 有資料的因子數。
single_quarter_breaks = 該檔被判「單季營收 < 0 口徑斷層」而作廢的季數(可追溯,不默默吞掉)。

§1 / §3.3:斜率有效點 < CROSS_QUARTER_MIN_POINTS(SSOT)→ 回 NaN(不硬配);
  單季 revenue ≤ 0 / total_assets ≤ 0 → 該比率 NaN(不 silent 0);
  缺去年同季 / 任一端單季 NaN / 去年同季單季營收 ≤ 0 → yoy NaN;
  單季化缺前季 / 任一端 NaN → 單季 NaN(不補 0、不前值填補)。
§8.2:L2 純函式,零 I/O、零 streamlit。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from shared.cross_quarter_thresholds import CROSS_QUARTER_MIN_POINTS

REQUIRED_COLS = (
    "stock_id", "revenue", "gross_profit", "op_income",
    "total_assets", "total_liab", "roc_year", "season",
)

# 年初至今累計的流量欄(要單季化);存量欄 total_assets / total_liab 不在此列。
YTD_FLOW_COLS = ("revenue", "gross_profit", "op_income")
_SQ_PREFIX = "sq_"
SQ_BREAK_COL = "sq_break"

_OUT_COLS = [
    "stock_id", "n_quarters", "gross_margin_slope", "op_margin_slope",
    "debt_ratio_slope", "revenue_yoy", "favorable_count", "favorable_of",
    "single_quarter_breaks",
]

_QUARTERS_PER_YEAR = 4   # YoY 回溯 4 季 = 去年同季;季序 ordinal 用
_KEY = ["stock_id", "roc_year", "season"]


def ytd_to_single_quarter(df: pd.DataFrame) -> pd.DataFrame:
    """年初至今累計流量欄 → 單季值(純函式,不改輸入)。

    鍵 (stock_id, roc_year, season),須唯一(重複 → ValueError;去重是 caller 的責任)。
    回傳 df 的副本,**保留原累計欄**,另加:
      - `sq_revenue` / `sq_gross_profit` / `sq_op_income`:單季值
      - `sq_break`(bool):相減後單季 revenue < 0 → 判口徑斷層(三欄單季皆 NaN)

    規則:
      - season 1:單季 = 累計;**Q1 永不判斷層**(即使累計營收 < 0 也不設 `sq_break`)。
        理由:Q1 沒有相減,負值是該季真實申報的負營收,不是跨季口徑斷層;且比率本來就因
        分母 ≤ 0 經 `_safe_ratio` 回 NaN,不會產生假讀數(2026-10-15 總管裁定 N1)。
      - season n∈{2,3,4}:單季 = 累計n − 累計(n−1),**限同一 roc_year**(不跨年相減)。
      - 前一季那列不存在 → 該季三欄單季全部 NaN。
      - 任一端該欄 NaN → 該欄單季 NaN(NaN 依算術逐欄傳遞,不補 0、不前值填補)。
      - 相減後單季 revenue < 0 → 三欄單季全部 NaN,`sq_break=True`。
    season 不在 1..4 → ValueError(§1 fail loud,季序無法定義)。
    """
    missing = [c for c in (*_KEY, *YTD_FLOW_COLS) if c not in df.columns]
    if missing:
        raise ValueError(f"ytd_to_single_quarter 缺必備欄:{missing}")
    out = df.copy()
    if out.empty:
        for c in YTD_FLOW_COLS:
            out[_SQ_PREFIX + c] = pd.Series(dtype=float)
        out[SQ_BREAK_COL] = pd.Series(dtype=bool)
        return out
    _season = pd.to_numeric(out["season"], errors="coerce")
    if not _season.isin([1, 2, 3, 4]).all():
        _bad = sorted(set(out.loc[~_season.isin([1, 2, 3, 4]), "season"].astype(str)))
        raise ValueError(f"ytd_to_single_quarter season 須為 1..4,實得:{_bad}")
    if pd.to_numeric(out["roc_year"], errors="coerce").isna().any():
        # NaN 年度在 merge 時會彼此配對 → 會拿別列去減;fail loud,不猜
        raise ValueError("ytd_to_single_quarter roc_year 有缺值 / 非數值")
    if out.duplicated(subset=_KEY).any():
        raise ValueError("ytd_to_single_quarter 鍵 (stock_id, roc_year, season) 有重複")

    _cum = out[list(YTD_FLOW_COLS)].apply(pd.to_numeric, errors="coerce")
    # 前一季(同 roc_year、season−1)那列:把每列的 season +1 當成「下一季的前季」接回去
    _prev = out[_KEY].copy()
    _prev["season"] = _season + 1
    _prev[list(YTD_FLOW_COLS)] = _cum.to_numpy()
    _prev["_prev_exists"] = True
    _left = out[_KEY].copy()
    _left["season"] = _season
    _m = _left.merge(_prev, on=_KEY, how="left", suffixes=("", "_p"))  # 保留左序、左列數
    _m.index = out.index

    _is_q1 = (_season == 1).to_numpy()
    _has_prev = _m["_prev_exists"].eq(True).to_numpy()
    _sq = {}
    for c in YTD_FLOW_COLS:
        _diff = _cum[c].to_numpy(dtype=float) - _m[c].to_numpy(dtype=float)
        _sq[c] = np.where(_is_q1, _cum[c].to_numpy(dtype=float),
                          np.where(_has_prev, _diff, np.nan))
    _break = (~_is_q1) & _has_prev & (_sq["revenue"] < 0)   # NaN < 0 → False
    for c in YTD_FLOW_COLS:
        out[_SQ_PREFIX + c] = np.where(_break, np.nan, _sq[c])
    out[SQ_BREAK_COL] = _break
    return out


def _safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    """num/den;分母 ≤0 或 NaN → NaN(§4.4 guard,不 silent 0、不 inf)。"""
    return num / den.where(den > 0)


def _slope(t: np.ndarray, y: np.ndarray) -> float:
    """(t, y) 一次項最小平方斜率;非 NaN 點 < MIN → NaN。t 為季序(間距感知)。"""
    y = np.asarray(y, dtype=float)
    t = np.asarray(t, dtype=float)
    mask = ~np.isnan(y)
    if int(mask.sum()) < CROSS_QUARTER_MIN_POINTS:
        return float("nan")
    return float(np.polyfit(t[mask], y[mask], 1)[0])


def _revenue_yoy(qord: np.ndarray, revenue: np.ndarray, sq_revenue: np.ndarray) -> float:
    """最新季**單季**營收 vs 去年同季(qord−4)**單季**營收 − 1(PQ-C4-1,2026-10-16)。

    Args:
        qord: 季序 ordinal(roc_year*4 + season−1)。
        revenue: 年初至今**累計**營收 —— 只用來定錨定季(最新一個有累計營收的季,修前同規則)。
        sq_revenue: `ytd_to_single_quarter` 的單季營收(缺前季 / 口徑斷層已是 NaN)。

    錨定季單季 NaN、去年同季列不存在或單季 NaN、去年同季單季 ≤ 0 → NaN(§1,不補 0、
    不回退到更早的季)。
    """
    _cum = {int(q): float(r) for q, r in zip(qord, revenue) if r == r}
    if not _cum:
        return float("nan")
    _latest = max(_cum)
    _sq = {int(q): float(v) for q, v in zip(qord, sq_revenue)}
    _cur = _sq.get(_latest, float("nan"))
    _prev = _sq.get(_latest - _QUARTERS_PER_YEAR, float("nan"))
    if not (_cur == _cur) or not (_prev > 0):     # NaN > 0 → False:去年同季 NaN 亦擋
        return float("nan")
    return _cur / _prev - 1.0


def compute_cross_quarter_trends(all_quarters: pd.DataFrame) -> pd.DataFrame:
    """全台股跨季趨勢因子(純函式,無 I/O)。

    Args:
        all_quarters: 全部季別全市場快照 long-form(每檔每季一列),須含 REQUIRED_COLS。
            revenue / gross_profit / op_income 為**年初至今累計**(MOPS t163sb04 口徑)。

    Returns:
        DataFrame(每檔一列,依 favorable_count 由大到小、stock_id 次序),欄見 _OUT_COLS。
        空輸入 → 回空(帶完整欄位)。斜率/yoy 缺資料 → NaN(不猜)。
    """
    empty = pd.DataFrame(columns=_OUT_COLS)
    if all_quarters is None or all_quarters.empty:
        return empty
    missing = [c for c in REQUIRED_COLS if c not in all_quarters.columns]
    if missing:
        raise ValueError(f"cross_quarter_trends 缺必備欄:{missing}")

    df = all_quarters.copy()
    df["stock_id"] = df["stock_id"].astype(str).str.strip()
    for c in ("revenue", "gross_profit", "op_income", "total_assets", "total_liab",
              "roc_year", "season"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["roc_year", "season"])
    if df.empty:
        return empty

    # 季序 ordinal(間距感知,處理缺季);同檔同季去重(keep last = 最新補抓)
    df["_qord"] = (df["roc_year"] * _QUARTERS_PER_YEAR + (df["season"] - 1)).astype(int)
    df = df.drop_duplicates(subset=["stock_id", "_qord"], keep="last")

    # 累計 → 單季(流量欄);毛利率/營益率改用單季比率。存量欄負債比不變。
    df = ytd_to_single_quarter(df)
    df["_gm"] = _safe_ratio(df["sq_gross_profit"], df["sq_revenue"])
    df["_om"] = _safe_ratio(df["sq_op_income"], df["sq_revenue"])
    df["_debt"] = _safe_ratio(df["total_liab"], df["total_assets"])

    rows = []
    for sid, g in df.groupby("stock_id", sort=False):
        g = g.sort_values("_qord")
        _q = g["_qord"].to_numpy()
        _t = (_q - _q.min()).astype(float)          # 季序自 0 起(間距感知)
        _gm_s = _slope(_t, g["_gm"].to_numpy())
        _om_s = _slope(_t, g["_om"].to_numpy())
        _debt_s = _slope(_t, g["_debt"].to_numpy())
        _yoy = _revenue_yoy(_q, g["revenue"].to_numpy(),
                            g["sq_revenue"].to_numpy())     # 單季對單季(PQ-C4-1)
        # 方向為佳:毛利/營益率漲、負債比降、營收 YoY 正
        _checks = [(_gm_s, _gm_s > 0), (_om_s, _om_s > 0),
                   (_debt_s, _debt_s < 0), (_yoy, _yoy > 0)]
        _avail = [ok for v, ok in _checks if v == v]   # v==v 濾掉 NaN
        rows.append({
            "stock_id": sid,
            "n_quarters": int(len(g)),
            "gross_margin_slope": _gm_s,
            "op_margin_slope": _om_s,
            "debt_ratio_slope": _debt_s,
            "revenue_yoy": _yoy,
            "favorable_count": int(sum(bool(x) for x in _avail)),
            "favorable_of": int(len(_avail)),
            "single_quarter_breaks": int(g[SQ_BREAK_COL].sum()),
        })

    out = pd.DataFrame(rows, columns=_OUT_COLS)
    return out.sort_values(
        ["favorable_count", "stock_id"], ascending=[False, True]
    ).reset_index(drop=True)
