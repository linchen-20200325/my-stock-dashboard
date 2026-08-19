#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""scripts/diagnose_margin_units.py — finmind_margin.parquet 單位/口徑污染診斷器（唯讀）。

===============================================================================
!! 重要聲明 —— 作者（AI）從未執行過這支腳本 !!
===============================================================================
本檔在「shell 沙箱不可用（session disk not found）」的環境下撰寫，
**作者一次都沒有跑過它**，沒有看過任何一行實際輸出，也沒有跑過任何測試、
沒有做過任何 syntax check 以外的驗證（連 syntax check 都沒跑）。

所有數字型結論都必須等 user 實際執行後貼回輸出才成立。
如果它在你機器上直接爆掉，那是預期內的風險 —— 請把 traceback 貼回來。

同款前例：scripts/analyze_ring1_gate.py（同樣未經執行）。


這支腳本在回答什麼問題
===============================================================================
`data_cache/finmind_margin.parquet`（4,929 筆，2006-07-17 ~ 2026-08-04）的
`margin_balance` 經 `/1e8` 轉億元後是**雙峰**：

    min=0.00 / P25=0.06 / median=0.12 / P75=1,895.78 / max=6,313.45 億

超過一半的值小於 0.12 億（約 1,240 萬元）。融資餘額不可能是這個數量級
（真實值應在 1,000~6,000 億）。⇒ **歷史序列裡混了至少兩種單位/口徑。**

本腳本**只量測、不修改**，用來分辨：
  (Q1) 壞的是哪一段？（逐年 / 逐區段 / 逐 fetched_at 批次）
  (Q2) 兩個峰各自是什麼口徑？（金額-元 / 金額-仟元 / 張數）
  (Q3) 2009–2023 的「觸發率 0%」是真的低於門檻，還是值被壓成 0？
  (Q4) 有沒有一個明確的「切換日」？（相鄰交易日比值暴跌/暴衝）


AI 的事前假說（**未經執行驗證，僅供對帳，可能全錯**）
===============================================================================
證據鏈（file:line）：

  1. `scripts/update_macro_history.py:219-241 fetch_finmind_margin()`
     打 FinMind dataset `TaiwanStockTotalMarginPurchaseShortSale`（**全市場彙總**版），
     然後用這段挑欄位：

         bal_col = next((c for c in raw.columns
                         if "MarginPurchase" in c and ("Balance" in c or "Today" in c)), None)
         if bal_col is None:
             bal_col = next((c for c in raw.columns if "Balance" in c), None)
         out = raw[["date", bal_col]].copy()          # ← 沒有依 `name` 過濾！

     第一條 next() 是照**個股版** dataset（`TaiwanStockMarginPurchaseShortSale`，
     寬格式、有 `MarginPurchaseTodayBalance` 欄）寫的
     —— 見 `src/data/core/data_loader.py:219-223`。
     但**全市場彙總版是長格式**：欄位 = `date / name / TodayBalance / YesterdayBalance / ...`，
     每個日期有**多列**，靠 `name` 區分口徑。
     ⇒ 第一條 next() 必定落空 → 掉到第二條 → 抓到第一個含 "Balance" 的欄
       （`TodayBalance` 或 `YesterdayBalance`，取決於 JSON key 順序），
       而且**套用到該日期的每一列**（金額列、張數列一起）。

  2. `scripts/update_macro_history.py:82-90 _merge_dedupe()`
         out.drop_duplicates(subset=["date"], keep="last")
     ⇒ 同一天的多列被壓成一列，**留哪一列由 FinMind 回傳的列順序決定**，
       而列順序既不受本專案控制、也沒被斷言過。

  3. 同一個 dataset 在 production 的正確用法寫在
     `src/data/daily/daily_data_fetchers.py:500-520, 561-587`：
         「同組含 MarginPurchaseVolume(張) 與 MarginPurchaseMoney(元) 兩種 margin 列
           —— 只認 **Money** 列」
     並在 `tests/test_review_fixes_v19_74.py:99-107` 釘死兩個實測值：
         MarginPurchaseMoney  = 619,648,244,000  → 6,196.5 億   ✅
         MarginPurchaseVolume =       9,614,955  → None（張，非金額）❌

  4. `ring1_report.txt:88` 已量到本檔**原始值中位數 = 12,389,404**。
     1.24e7 落在 9.6e6（上面那個 Volume 實測值）同一個數量級。

**主假說 H-A（信心：高）**
    低峰 = `MarginPurchaseVolume`（**張 / 交易單位**，全市場融資餘額張數，量級 5e6~2e7）
    高峰 = `MarginPurchaseMoney`（**元**，量級 1e11~6e11）
    兩者被 `_merge_dedupe(keep="last")` 隨機混進同一欄。
    兩峰比值應該 ≈ 「每張融資金額」≈ 1.5e4 ~ 5e4 元/張（合理）。
    ⇒ 本腳本 §3 / §7 會直接驗這條比值。

**次假說 H-B（信心：中低）**
    低峰 = 金額但單位是「仟元」（TWSE MI_MARGN 原生單位）。
    反證：仟元的話原始值應該是 1.9e8 量級（/1e8 = 1.9 億），
          不是觀測到的 1.2e7。所以 H-B 大概率**不成立**，但腳本仍會分類統計它。

**次假說 H-C（信心：中）**
    抓到的是 `YesterdayBalance` 而不是 `TodayBalance`
    （第二條 next() 只認「第一個含 Balance 的欄」，順序由 dict key 決定）。
    這不會造成雙峰，但會讓整條序列**日期錯位一天**（§2.3 PIT 契約不符）。
    本腳本無法從 parquet 單獨證實這條 —— 需要一次真實 API 回應才能定案，
    §9 會印出該怎麼查。

**次假說 H-D（信心：中）**
    bootstrap（`--bootstrap`，一次要 20 年）與每日增量（只要 1~3 天）
    走的是**同一支函式**但**不同的回應**；若 FinMind 對長區間有列數上限或
    列順序不同，兩批寫進來的口徑就會不同。
    ⇒ §5 的 `fetched_at` 分群 × 口徑 crosstab 就是驗這條。


硬性保證
===============================================================================
[唯讀]   只 `pd.read_parquet` / `sqlite3` 唯讀連線 / `Path.stat()`。
         **唯一**會寫的檔案是 `--out` 指定的報告（預設 scripts/_out/margin_units_report.txt）。
         **絕不**碰 `data_cache/` 底下任何位元組、不碰 `macro_thresholds.json`。
[離線]   不 import requests / yfinance / FinMind / streamlit，不呼叫任何 fetcher。
[不修補] 不做 fillna / ffill / 自動換算修正。看到怪值就印出來（CLAUDE.md §1）。
[編碼]   報告用 Python 自己寫檔（`encoding='utf-8'`），**不要**用 PowerShell 的
         `>` 重導向（會變成 UTF-16LE + 中文亂碼，本專案已踩過兩次，
         證據：repo 根目錄那份 `ring1_report.txt`）。


使用方式
===============================================================================
    cd D:\\01.Github\\20260804\\my-Stock-dashboardr1
    python scripts\\diagnose_margin_units.py

報告會同時印到畫面 + 寫到 scripts\\_out\\margin_units_report.txt（UTF-8）。
畫面若亂碼**不影響檔案**；要畫面也正常就先 `chcp 65001`。

常用參數：
    --cache-dir PATH     parquet 目錄（預設 <repo>/data_cache）
    --out FILE           報告輸出路徑（預設 scripts/_out/margin_units_report.txt）
    --no-stdout          只寫檔，不印畫面
    --start / --end      日期區間過濾（YYYY-MM-DD）
    --bp-hi / --bp-lo    斷點偵測的相鄰比值上/下界（預設 100 / 0.01）
    --max-rows N         每張明細表最多印幾列（預設 80）

退出碼：
    0 = 跑完
    2 = 找不到 finmind_margin.parquet / 缺必要欄位（照 §1 大聲說，不猜）
    1 = 執行期例外
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import math
import sqlite3
import sys
import traceback
from pathlib import Path
from typing import Optional

try:
    import numpy as np
    import pandas as pd
except ImportError as _e:  # §1 Fail Loud
    sys.stderr.write(
        f"[FATAL] 缺 pandas / numpy：{type(_e).__name__}: {_e}\n"
        f"        請在本專案的 venv 裡跑：pip install -r requirements.txt\n")
    raise SystemExit(1)


_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ════════════════════════════════════════════════════════════════
# 輸出：同時 tee 到 stdout + 記憶體（最後由 Python 自己寫 UTF-8 檔）
# ════════════════════════════════════════════════════════════════
class Reporter:
    """收集報告行；印畫面失敗（Windows cp950）也不影響檔案內容。"""

    def __init__(self, echo: bool = True) -> None:
        self._lines: list[str] = []
        self._echo = echo
        self._echo_broken = False

    def __call__(self, line: str = "") -> None:
        self._lines.append(line)
        if not self._echo:
            return
        try:
            print(line)
        except Exception:
            # 主控台編碼不支援 → 降級印，但**檔案內容不受影響**
            if not self._echo_broken:
                self._echo_broken = True
                try:
                    print("[警告] 主控台無法顯示部分字元，已降級輸出；"
                          "完整內容請看 --out 指定的檔案。")
                except Exception:
                    pass
            try:
                print(line.encode("utf-8", "replace").decode("ascii", "replace"))
            except Exception:
                pass

    def rule(self, ch: str = "=", n: int = 78) -> None:
        self(ch * n)

    def section(self, title: str) -> None:
        self("")
        self.rule("=")
        self(title)
        self.rule("=")

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(self._lines) + "\n", encoding="utf-8")


def _fmt(v, nd: int = 2) -> str:
    """數字格式化；None / NaN / inf 一律印 'n/a'（不填 0，§1）。"""
    if v is None:
        return "n/a"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if not math.isfinite(f):
        return "n/a"
    return f"{f:,.{nd}f}"


def _sha256_head(path: Path, n: int = 12) -> str:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()[:n]
    except Exception as e:  # noqa: BLE001
        return f"<sha 失敗 {type(e).__name__}>"


# ════════════════════════════════════════════════════════════════
# 口徑分類（**這是解讀，不是事實** —— 分類邊界一律印出來供覆核）
# ════════════════════════════════════════════════════════════════
def _load_sanity_bounds(rep: Reporter) -> tuple[float, float, str]:
    """從 SSOT 取融資餘額合理區間（億）；import 失敗才用字面值 fallback。"""
    try:
        from shared.signal_thresholds import (  # type: ignore
            MARGIN_BALANCE_SANITY_MAX_YI, MARGIN_BALANCE_SANITY_MIN_YI)
        return (float(MARGIN_BALANCE_SANITY_MIN_YI),
                float(MARGIN_BALANCE_SANITY_MAX_YI),
                "SSOT-import shared/signal_thresholds.py:548,554")
    except Exception as e:  # noqa: BLE001
        rep(f"    [!] 無法 import shared.signal_thresholds（{type(e).__name__}: {e}）"
            f"→ 改用字面值 fallback，請自行覆核")
        return (500.0, 10000.0, "FALLBACK 字面值（import 失敗）")


def _load_overheat_threshold(rep: Reporter) -> tuple[float, str]:
    try:
        from shared.signal_thresholds import (  # type: ignore
            MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI)
        return (float(MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI),
                "SSOT-import shared/signal_thresholds.py:122")
    except Exception as e:  # noqa: BLE001
        rep(f"    [!] 無法 import MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI"
            f"（{type(e).__name__}: {e}）→ fallback 3400.0")
        return (3400.0, "FALLBACK 字面值（import 失敗）")


# 口徑標籤（見 docstring 假說 H-A / H-B）
LBL_MONEY_TWD = "H1_金額-元"        # raw/1e8 ∈ [min_yi, max_yi]
LBL_MONEY_KNT = "H2_金額-仟元"      # raw/1e5 ∈ [min_yi, max_yi]
LBL_VOLUME    = "H3_張數"           # raw ∈ [1e6, 5e7]
LBL_ZERO      = "H0_零或負或NaN"
LBL_UNKNOWN   = "H4_不明"


def _make_classifier(min_yi: float, max_yi: float):
    lo_twd, hi_twd = min_yi * 1e8, max_yi * 1e8     # 元
    lo_knt, hi_knt = min_yi * 1e5, max_yi * 1e5     # 仟元
    lo_vol, hi_vol = 1e6, 5e7                        # 張（全市場融資張數量級）

    def classify(v) -> str:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return LBL_ZERO
        if not math.isfinite(f) or f <= 0:
            return LBL_ZERO
        if lo_twd <= f <= hi_twd:
            return LBL_MONEY_TWD
        if lo_knt <= f <= hi_knt:
            return LBL_MONEY_KNT
        if lo_vol <= f <= hi_vol:
            return LBL_VOLUME
        return LBL_UNKNOWN

    bounds_desc = (
        f"{LBL_MONEY_TWD}: raw ∈ [{lo_twd:,.0f}, {hi_twd:,.0f}]（÷1e8 = {min_yi:,.0f}~{max_yi:,.0f} 億）\n"
        f"    {LBL_MONEY_KNT}: raw ∈ [{lo_knt:,.0f}, {hi_knt:,.0f}]（÷1e5 = {min_yi:,.0f}~{max_yi:,.0f} 億）\n"
        f"    {LBL_VOLUME}: raw ∈ [{lo_vol:,.0f}, {hi_vol:,.0f}]（全市場融資餘額張數的合理量級）\n"
        f"    {LBL_ZERO}: <= 0 / NaN / 非數值    {LBL_UNKNOWN}: 以上皆非"
    )
    return classify, bounds_desc


# ════════════════════════════════════════════════════════════════
# 讀檔
# ════════════════════════════════════════════════════════════════
def _read_margin(path: Path, rep: Reporter) -> Optional[pd.DataFrame]:
    if not path.exists():
        rep(f"[FATAL] 找不到 {path}")
        rep("        → 這台機器上根本沒有這份 cache，本診斷無法進行（§1：不猜）。")
        return None
    try:
        df = pd.read_parquet(path)
    except Exception as e:  # noqa: BLE001
        rep(f"[FATAL] 讀 {path.name} 失敗：{type(e).__name__}: {e}")
        return None
    missing = {"date", "margin_balance"} - set(df.columns)
    if missing:
        rep(f"[FATAL] {path.name} 缺必要欄位 {sorted(missing)}；實際欄位={list(df.columns)}")
        return None
    return df


def _prepare(df: pd.DataFrame, rep: Reporter,
             start: Optional[str], end: Optional[str]) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    n_bad_date = int(out["date"].isna().sum())
    if n_bad_date:
        rep(f"    [!] date 欄有 {n_bad_date} 筆無法解析 → 這些列會被排除並在此記錄"
            f"（§1：顯式排除，不靜默）")
        out = out[out["date"].notna()]
    out["margin_balance"] = pd.to_numeric(out["margin_balance"], errors="coerce")
    if start:
        out = out[out["date"] >= pd.Timestamp(start)]
    if end:
        out = out[out["date"] <= pd.Timestamp(end)]
    out = out.sort_values("date").reset_index(drop=True)
    out["year"] = out["date"].dt.year
    return out


# ════════════════════════════════════════════════════════════════
# §0 檔案指紋
# ════════════════════════════════════════════════════════════════
def sec_fingerprint(rep: Reporter, path: Path, raw: pd.DataFrame) -> None:
    rep.section("§0  檔案指紋（把這段連同結論一起貼回來，才知道你我在看同一份檔）")
    try:
        stat = path.stat()
        mtime = _dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
        size = f"{stat.st_size:,} bytes"
    except Exception as e:  # noqa: BLE001
        mtime, size = f"<stat 失敗 {type(e).__name__}>", "n/a"
    rep(f"    路徑        : {path}")
    rep(f"    sha256[:12] : {_sha256_head(path)}")
    rep(f"    大小 / mtime: {size} / {mtime}")
    rep(f"    rows        : {len(raw):,}")
    rep(f"    cols        : {list(raw.columns)}")
    rep(f"    dtypes      : {dict(raw.dtypes.astype(str))}")
    for c in raw.columns:
        n_null = int(raw[c].isna().sum())
        rep(f"      - {c:<16} null={n_null:>6,} / {len(raw):,}")
    rep("")
    rep(f"    本次執行時間 : {_dt.datetime.now().isoformat(timespec='seconds')}")
    rep(f"    Python       : {sys.version.split()[0]}   pandas={pd.__version__}")


# ════════════════════════════════════════════════════════════════
# §1 全域分佈 + log10 直方圖（**客觀**，不帶解讀）
# ════════════════════════════════════════════════════════════════
def sec_global(rep: Reporter, df: pd.DataFrame) -> None:
    rep.section("§1  全域分佈（原始值，未除；外加 log10 量級直方圖 → 雙峰會自己現形）")
    s = df["margin_balance"]
    ok = s[s.notna()]
    rep(f"    n_total={len(s):,}   n_notna={len(ok):,}   n_nan={int(s.isna().sum()):,}")
    rep(f"    日期範圍 {df['date'].min().date()} ~ {df['date'].max().date()}")
    rep(f"    date 單調遞增 = {bool(df['date'].is_monotonic_increasing)}   "
        f"date 唯一 = {bool(df['date'].is_unique)}   "
        f"重複日期數 = {int(df['date'].duplicated().sum()):,}")
    rep("")
    if ok.empty:
        rep("    [!] 全欄皆 NaN，後續分析無法進行。")
        return
    qs = [0.0, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 1.0]
    rep("    分位數（原始值）:")
    for q in qs:
        v = ok.quantile(q)
        rep(f"      P{q*100:>5.1f}  raw={_fmt(v, 0):>22}   ÷1e8={_fmt(v/1e8, 4):>16} 億")
    rep("")
    rep("    log10 量級直方圖（floor(log10(raw))，只算 raw>0）:")
    pos = ok[ok > 0]
    n_le0 = int((ok <= 0).sum())
    if n_le0:
        rep(f"      raw <= 0 : {n_le0:,} 筆   ← 融資餘額不可能 <= 0（§3.2），先記著")
    if pos.empty:
        rep("      （沒有正值）")
    else:
        mags = np.floor(np.log10(pos.to_numpy(dtype=float))).astype(int)
        vc = pd.Series(mags).value_counts().sort_index()
        peak = int(vc.max()) or 1
        for mag, cnt in vc.items():
            mag_i, cnt_i = int(mag), int(cnt)
            bar = "#" * max(1, int(round(cnt_i / peak * 44)))
            rep(f"      1e{mag_i:<3d} ({10.0**mag_i:>16,.0f} ~ {10.0**(mag_i+1):>17,.0f})  "
                f"{cnt_i:>6,}  {bar}")
        rep("")
        rep("      ↑ 如果只看到一坨連續的量級 → 不是單位問題，是別的毛病；")
        rep("        如果看到兩坨中間空一大段 → 雙峰確認，往 §3 看兩峰各是什麼。")


# ════════════════════════════════════════════════════════════════
# §2 逐年統計（**題目要的核心表**）
# ════════════════════════════════════════════════════════════════
def sec_by_year(rep: Reporter, df: pd.DataFrame) -> None:
    rep.section("§2  逐年值域（原始值，不先除）+ 中位數年比 → 單位在哪一年變的會直接跳出來")
    g = df.groupby("year")["margin_balance"]
    tbl = pd.DataFrame({
        "n": g.size(),
        "n_nan": g.apply(lambda x: int(x.isna().sum())),
        "min": g.min(),
        "p25": g.quantile(0.25),
        "median": g.median(),
        "p75": g.quantile(0.75),
        "max": g.max(),
    })
    tbl["ratio_vs_prev"] = tbl["median"] / tbl["median"].shift(1)

    rep(f"    {'年':<6}{'n':>6}{'NaN':>5}"
        f"{'min':>20}{'P25':>20}{'median':>20}{'P75':>20}{'max':>20}"
        f"{'中位數/前一年':>16}")
    rep("    " + "-" * 128)
    for yr, r in tbl.iterrows():
        flag = ""
        rv = r["ratio_vs_prev"]
        if rv is not None and isinstance(rv, float) and math.isfinite(rv):
            if rv > 50 or rv < 0.02:
                flag = "   <<<<<< 量級跳變"
        rep(f"    {int(yr):<6}{int(r['n']):>6}{int(r['n_nan']):>5}"
            f"{_fmt(r['min'],0):>20}{_fmt(r['p25'],0):>20}{_fmt(r['median'],0):>20}"
            f"{_fmt(r['p75'],0):>20}{_fmt(r['max'],0):>20}"
            f"{_fmt(rv,3):>16}{flag}")
    rep("")
    rep("    讀法：`中位數/前一年` 若在某年 ≈ 1e4~1e5 或 ≈ 1e-4~1e-5，")
    rep("          那一年就是口徑切換點；若整段都在 0.5~2 之間，代表該段口徑一致。")


# ════════════════════════════════════════════════════════════════
# §3 口徑分類 + 逐年 crosstab + 連續區段（RLE）
# ════════════════════════════════════════════════════════════════
def sec_mode(rep: Reporter, df: pd.DataFrame, bounds_desc: str, max_rows: int) -> None:
    rep.section("§3  口徑分類（**這是解讀不是事實**；分類邊界如下，請自行覆核）")
    rep(f"    {bounds_desc}")
    rep("")
    vc = df["mode"].value_counts()
    total = max(1, len(df))
    rep("    全域分佈：")
    for label, cnt in vc.items():
        c = int(cnt)
        rep(f"      {str(label):<14} {c:>6,}  ({c/total*100:>5.1f}%)")
    rep("")

    # 兩峰的代表值 + 比值（H-A 的關鍵驗證）
    med_money = df.loc[df["mode"] == LBL_MONEY_TWD, "margin_balance"].median()
    med_vol = df.loc[df["mode"] == LBL_VOLUME, "margin_balance"].median()
    rep("    兩峰代表值：")
    rep(f"      {LBL_MONEY_TWD} 中位數 raw = {_fmt(med_money,0)}  → ÷1e8 = {_fmt(med_money/1e8 if med_money==med_money else None,1)} 億")
    rep(f"      {LBL_VOLUME}   中位數 raw = {_fmt(med_vol,0)}")
    if (med_money == med_money) and (med_vol == med_vol) and med_vol:
        ratio = med_money / med_vol
        rep(f"      兩峰比值 = {_fmt(ratio,1)}  （若假說 H-A 成立，此值 = 「每張融資金額」）")
        verdict = ("✔ 落在 1.5e4~5e4 元/張的合理帶 → **H-A（金額-元 vs 張數）獲得支持**"
                   if 1.0e4 <= ratio <= 8.0e4 else
                   "✖ 不在 1.5e4~5e4 元/張的合理帶 → H-A 存疑，請把本行貼回來重新推敲")
        rep(f"      {verdict}")
        rep("      （對照：台股一張 = 1,000 股；融資成數約 6 成 ⇒ 每張融資金額 ≈ 股價 × 600）")
    else:
        rep("      兩峰其一不存在 → 本檢定跳過（不代表假說成立或不成立）")
    rep("")

    rep("    逐年 × 口徑（列 = 年，欄 = 口徑，值 = 筆數）：")
    ct = pd.crosstab(df["year"], df["mode"])
    cols = list(ct.columns)
    rep("    " + f"{'年':<6}" + "".join(f"{c:>16}" for c in cols))
    rep("    " + "-" * (6 + 16 * len(cols)))
    for yr, r in ct.iterrows():
        rep("    " + f"{int(yr):<6}" + "".join(f"{int(r[c]):>16,}" for c in cols))
    rep("")

    rep("    連續同口徑區段（RLE）—— 直接看「壞的是哪一段」：")
    mode = df["mode"]
    seg_id = (mode != mode.shift()).cumsum()
    segs = df.groupby(seg_id).agg(
        mode=("mode", "first"),
        start=("date", "min"),
        end=("date", "max"),
        n=("date", "size"),
        vmin=("margin_balance", "min"),
        vmax=("margin_balance", "max"),
    )
    rep(f"      區段總數 = {len(segs):,}（越少越像「整段切換」，越多越像「逐日隨機混」）")
    show = segs if len(segs) <= max_rows else pd.concat([segs.head(max_rows // 2),
                                                         segs.tail(max_rows // 2)])
    if len(segs) > max_rows:
        rep(f"      （只印前 {max_rows//2} + 後 {max_rows//2} 段；全部 {len(segs):,} 段）")
    rep(f"      {'口徑':<14}{'起':<12}{'訖':<12}{'筆數':>8}{'min':>20}{'max':>20}")
    rep("      " + "-" * 86)
    for _, r in show.iterrows():
        rep(f"      {r['mode']:<14}{str(r['start'].date()):<12}{str(r['end'].date()):<12}"
            f"{int(r['n']):>8,}{_fmt(r['vmin'],0):>20}{_fmt(r['vmax'],0):>20}")
    rep("")
    rep("      判讀：")
    rep("        * 少數幾段長區段  ⇒ 上游某次改欄位 / 某次 bootstrap 用了不同口徑")
    rep("        * 上千段短區段    ⇒ 每天在兩種口徑之間跳 ⇒ 支持"
        "『同日多列 + drop_duplicates(keep=\"last\") 隨機挑』（假說 H-A 的機制）")


# ════════════════════════════════════════════════════════════════
# §4 source 欄位分佈
# ════════════════════════════════════════════════════════════════
def sec_source(rep: Reporter, df: pd.DataFrame) -> None:
    rep.section("§4  `source` 欄位分佈（有沒有換過來源）")
    if "source" not in df.columns:
        rep("    本檔沒有 source 欄 → 無法從資料端判斷來源；"
            "code 端唯一寫入點是 update_macro_history.py:239")
        return
    n_null = int(df["source"].isna().sum())
    rep(f"    null / 缺值 = {n_null:,} 筆"
        + ("   ← 這些列是 v18.259 加 provenance **之前**寫進去的（時間線證據）"
           if n_null else ""))
    if n_null:
        sub = df[df["source"].isna()]
        rep(f"      日期範圍 {sub['date'].min().date()} ~ {sub['date'].max().date()}")
        rep(f"      口徑分佈 {dict(sub['mode'].value_counts())}")
    rep("")
    grp = df[df["source"].notna()].groupby("source")
    if len(grp) == 0:
        rep("    （沒有非空的 source 值）")
        return
    rep(f"    {'source':<58}{'筆數':>8}{'起':>13}{'訖':>13}")
    rep("    " + "-" * 92)
    for src, sub in grp:
        rep(f"    {str(src)[:56]:<58}{len(sub):>8,}"
            f"{str(sub['date'].min().date()):>13}{str(sub['date'].max().date()):>13}")
    rep("")
    rep("    每個 source × 口徑：")
    ct = pd.crosstab(df["source"].fillna("<NULL>"), df["mode"])
    for src, r in ct.iterrows():
        rep(f"      {str(src)[:56]:<58} " + "  ".join(f"{c}={int(r[c]):,}" for c in ct.columns))
    rep("")
    rep("    ⚠️ code 只寫得出一個字串（'FinMind:TaiwanStockTotalMarginPurchaseShortSale'），")
    rep("       所以 source 欄**分辨不出**同一 dataset 內的 name 子口徑（Money vs Volume）。")
    rep("       這正是本次事故的根因之一：provenance 記到 dataset 就停了，沒記到欄/列。")


# ════════════════════════════════════════════════════════════════
# §5 fetched_at 批次（bootstrap vs 每日增量）
# ════════════════════════════════════════════════════════════════
def sec_fetched_at(rep: Reporter, df: pd.DataFrame, max_rows: int) -> None:
    rep.section("§5  `fetched_at` 批次分群 —— 哪些列是一次寫進去的（bootstrap）、哪些是每日增量")
    if "fetched_at" not in df.columns:
        rep("    本檔沒有 fetched_at 欄 → 跳過。")
        return
    n_null = int(df["fetched_at"].isna().sum())
    rep(f"    null = {n_null:,} 筆"
        + ("   ← v18.259 之前寫入的舊列" if n_null else ""))
    if n_null:
        sub = df[df["fetched_at"].isna()]
        rep(f"      日期範圍 {sub['date'].min().date()} ~ {sub['date'].max().date()}   "
            f"口徑 {dict(sub['mode'].value_counts())}")
    rep("")

    work = df[df["fetched_at"].notna()].copy()
    if work.empty:
        rep("    （沒有非空的 fetched_at）")
        return
    work["fa"] = work["fetched_at"].astype(str)
    grp = work.groupby("fa")
    rep(f"    相異 fetched_at 時間戳數 = {len(grp):,}")
    rep("    （同一個時間戳的成群列 = 同一次寫入。一次 bootstrap 會產生**一個**"
        "涵蓋整段歷史的大群；每日增量各自是 1~3 列的小群。）")
    rep("")
    summ = grp.agg(n=("date", "size"),
                   d0=("date", "min"),
                   d1=("date", "max")).sort_values("n", ascending=False)
    show = summ.head(max_rows)
    rep(f"      {'fetched_at (UTC)':<34}{'筆數':>8}{'資料起':>13}{'資料訖':>13}   口徑分佈")
    rep("      " + "-" * 110)
    for fa, r in show.iterrows():
        sub = work[work["fa"] == fa]
        mix = "  ".join(f"{k}={v:,}" for k, v in sub["mode"].value_counts().items())
        rep(f"      {str(fa)[:32]:<34}{int(r['n']):>8,}"
            f"{str(r['d0'].date()):>13}{str(r['d1'].date()):>13}   {mix}")
    if len(summ) > max_rows:
        rep(f"      （只印筆數最多的前 {max_rows} 群；共 {len(summ):,} 群）")
    rep("")
    rep("    依 fetched_at 的**日期**彙總（看得出跑過幾次 cron / 幾次 bootstrap）：")
    work["fa_day"] = work["fa"].str.slice(0, 10)
    day = work.groupby("fa_day").agg(n=("date", "size"),
                                     d0=("date", "min"), d1=("date", "max"))
    day = day.sort_values("n", ascending=False).head(max_rows)
    rep(f"      {'寫入日(UTC)':<14}{'筆數':>8}{'資料起':>13}{'資料訖':>13}   口徑分佈")
    rep("      " + "-" * 92)
    for d, r in day.iterrows():
        sub = work[work["fa_day"] == d]
        mix = "  ".join(f"{k}={v:,}" for k, v in sub["mode"].value_counts().items())
        rep(f"      {str(d):<14}{int(r['n']):>8,}"
            f"{str(r['d0'].date()):>13}{str(r['d1'].date()):>13}   {mix}")
    rep("")
    rep("    判讀：如果**同一個大群**裡就同時有『金額』與『張數』兩種口徑，")
    rep("          那就不是「換過來源」，而是**單一次抓取內部就混了**")
    rep("          ⇒ 直接坐實 update_macro_history.py:225-236 沒依 `name` 過濾（假說 H-A）。")


# ════════════════════════════════════════════════════════════════
# §6 斷點偵測
# ════════════════════════════════════════════════════════════════
def sec_breakpoints(rep: Reporter, df: pd.DataFrame,
                    hi: float, lo: float, max_rows: int) -> None:
    rep.section(f"§6  斷點偵測 —— 相鄰交易日比值 > {hi:g} 或 < {lo:g}（單位跳變的直接證據）")
    d = df[df["margin_balance"].notna()].reset_index(drop=True)
    if len(d) < 2:
        rep("    有效列不足 2 筆，跳過。")
        return
    v = d["margin_balance"].astype(float)
    prev = v.shift(1)
    ratio = v / prev.where(prev > 0)
    mask = (ratio > hi) | (ratio < lo)
    idx = list(d.index[mask.fillna(False)])
    rep(f"    命中 {len(idx):,} 個斷點（總相鄰對 = {len(d)-1:,}）")
    if not idx:
        rep("    → 沒有任何相鄰跳變 ⇒ 序列在**時間軸上是連續的**，")
        rep("      但 §3 若仍顯示雙峰，代表兩種口徑是**交錯**的而非分段的。")
        return
    rep("")
    rep(f"      {'日期':<12}{'前一日':<12}{'前值':>20}{'本值':>20}{'比值':>14}"
        f"   {'前口徑':<14}{'本口徑':<14}")
    rep("      " + "-" * 112)
    for i in idx[:max_rows]:
        rep(f"      {str(d.loc[i,'date'].date()):<12}"
            f"{str(d.loc[i-1,'date'].date()):<12}"
            f"{_fmt(d.loc[i-1,'margin_balance'],0):>20}"
            f"{_fmt(d.loc[i,'margin_balance'],0):>20}"
            f"{_fmt(ratio.loc[i],4):>14}"
            f"   {d.loc[i-1,'mode']:<14}{d.loc[i,'mode']:<14}")
    if len(idx) > max_rows:
        rep(f"      （只印前 {max_rows} 個；共 {len(idx):,} 個）")
    rep("")
    rep("    判讀：")
    rep("      * 只有 1~2 個斷點 ⇒ 有明確切換日，修法可以「切段處理」")
    rep("      * 幾百上千個斷點 ⇒ 逐日交錯，**沒有乾淨的切點**，只能整份重抓")


# ════════════════════════════════════════════════════════════════
# §7 外部錨點：TWII 指數
# ════════════════════════════════════════════════════════════════
def sec_anchor_twii(rep: Reporter, df: pd.DataFrame, cache_dir: Path) -> None:
    rep.section("§7  外部錨點 —— 同期 ^TWII 指數點位（用常識判斷「X 億搭配 Y 點」合不合理）")
    p = cache_dir / "twii_ohlcv.parquet"
    if not p.exists():
        rep(f"    找不到 {p} → 無法對帳（§1：不編一個指數出來）")
        return
    try:
        tw = pd.read_parquet(p)
    except Exception as e:  # noqa: BLE001
        rep(f"    讀 twii_ohlcv.parquet 失敗：{type(e).__name__}: {e}")
        return
    if "date" not in tw.columns or "close" not in tw.columns:
        rep(f"    twii_ohlcv.parquet 缺 date/close；欄位={list(tw.columns)}")
        return
    tw["date"] = pd.to_datetime(tw["date"], errors="coerce")
    tw["year"] = tw["date"].dt.year
    tw_med = tw.groupby("year")["close"].median()

    money = df[df["mode"] == LBL_MONEY_TWD]
    vol = df[df["mode"] == LBL_VOLUME]
    m_med = money.groupby("year")["margin_balance"].median() / 1e8
    v_med = vol.groupby("year")["margin_balance"].median()
    n_m = money.groupby("year").size()
    n_v = vol.groupby("year").size()

    years = sorted(set(df["year"]))
    rep(f"    {'年':<6}{'TWII中位':>12}"
        f"{'n_金額':>9}{'金額中位(億)':>16}"
        f"{'n_張數':>9}{'張數中位(張)':>16}"
        f"{'推得每張融資(元)':>20}{'融資/指數(億/千點)':>22}")
    rep("    " + "-" * 112)
    for y in years:
        t = tw_med.get(y, float("nan"))
        mm = m_med.get(y, float("nan"))
        vv = v_med.get(y, float("nan"))
        per_lot = (mm * 1e8 / vv) if (mm == mm and vv == vv and vv) else float("nan")
        per_kpt = (mm / (t / 1000.0)) if (mm == mm and t == t and t) else float("nan")
        rep(f"    {int(y):<6}{_fmt(t,0):>12}"
            f"{int(n_m.get(y,0)):>9,}{_fmt(mm,0):>16}"
            f"{int(n_v.get(y,0)):>9,}{_fmt(vv,0):>16}"
            f"{_fmt(per_lot,0):>20}{_fmt(per_kpt,1):>22}")
    rep("")
    rep("    對帳指引（憑常識，不是硬門檻）：")
    rep("      * 台股融資餘額真實區間大致 1,000~6,000 億（2008 海嘯低點 ≈1,100 億）")
    rep("      * 全市場融資餘額張數大致 5,000,000~20,000,000 張")
    rep("      * 「每張融資金額」= 金額/張數，應該落在 1.5 萬~5 萬元/張")
    rep("        （一張 1,000 股 × 融資成數 6 成 ⇒ ≈ 股價 × 600）")
    rep("      * 「融資/指數」在同一個多空循環裡不該差到 10 倍；差很多代表那年口徑不同")


# ════════════════════════════════════════════════════════════════
# §8 觸發率：現況 vs「只留金額列」
# ════════════════════════════════════════════════════════════════
def sec_trigger(rep: Reporter, df: pd.DataFrame, thr: float, thr_src: str) -> None:
    rep.section(f"§8  逐年觸發率（門檻 = {thr:,.0f} 億，來源 {thr_src}）"
                " —— 直接回答「2009–2023 的 0% 是真是假」")
    yi = df["margin_balance"] / 1e8
    df = df.assign(_yi=yi, _trig=(yi >= thr))
    money = df[df["mode"] == LBL_MONEY_TWD]

    rep(f"    {'年':<6}"
        f"{'全部n':>8}{'全部觸發':>10}{'全部觸發率':>12}   "
        f"{'金額列n':>9}{'金額觸發':>10}{'金額觸發率':>12}   {'判定':<28}")
    rep("    " + "-" * 108)
    for y in sorted(set(df["year"])):
        a = df[df["year"] == y]
        m = money[money["year"] == y]
        na, ta = len(a), int(a["_trig"].sum())
        nm, tm = len(m), int(m["_trig"].sum())
        ra = ta / na * 100 if na else float("nan")
        rm = tm / nm * 100 if nm else float("nan")
        if nm == 0:
            verdict = "該年沒有任何金額列 → 觸發率無意義"
        elif nm < na * 0.5:
            verdict = f"金額列僅佔 {nm/na*100:.0f}% → 原數字被稀釋"
        else:
            verdict = "金額列為主 → 原數字大致可信"
        rep(f"    {int(y):<6}"
            f"{na:>8,}{ta:>10,}{_fmt(ra,1):>11}%   "
            f"{nm:>9,}{tm:>10,}{_fmt(rm,1):>11}%   {verdict:<28}")
    rep("")
    rep("    讀法：")
    rep("      * 若某年『全部觸發率 0%』但『金額列 n = 0』")
    rep("        ⇒ 那個 0% 是**資料缺陷造成的假 0**，不是「融資真的低」，不可引用。")
    rep("      * 若某年金額列佔多數且觸發率仍 0%")
    rep("        ⇒ 那個 0% 是真的（該年融資確實低於門檻），原結論可留。")
    rep("      ⚠️ 即使是「金額列」的觸發率，也只是**倖存樣本**的統計 ——")
    rep("         被 drop_duplicates 丟掉的那些日子不是隨機缺失，")
    rep("         所以這張表只能用來**分辨假 0**，不能拿來當校準輸入（§5 可重現性）。")


# ════════════════════════════════════════════════════════════════
# §9 交叉比對：其他 parquet / stock.db
# ════════════════════════════════════════════════════════════════
def sec_crosscheck(rep: Reporter, cache_dir: Path, repo_root: Path) -> None:
    rep.section("§9  交叉比對 —— 本機還有沒有第二份融資資料可以對帳")
    hits = 0
    rep("    掃 data_cache/**.parquet 找含融資/margin/balance 的欄位：")
    try:
        files = sorted(cache_dir.rglob("*.parquet"))
    except Exception as e:  # noqa: BLE001
        rep(f"      掃描失敗：{type(e).__name__}: {e}")
        files = []
    for p in files:
        if p.name == "finmind_margin.parquet":
            continue
        try:
            cols = list(pd.read_parquet(p).columns)
        except Exception as e:  # noqa: BLE001
            rep(f"      {p.name:<34} 讀取失敗 {type(e).__name__}: {e}")
            continue
        cand = [c for c in cols
                if any(k in str(c).lower() for k in ("margin", "balance"))
                or "融資" in str(c) or "融券" in str(c)]
        if cand:
            hits += 1
            rep(f"      {p.name:<34} ← 命中欄位 {cand}")
    if hits == 0:
        rep("      （沒有第二份 —— data_cache 裡只有 finmind_margin.parquet 存融資）")
        rep("      ⇒ **無法做同源對帳**。要驗證只能：(a) 重打一次 FinMind 看原始回應，")
        rep("        或 (b) 拿 TWSE MI_MARGN 某幾天單日值人工比對。§10 有指令。")
    rep("")

    db = repo_root / "stock.db"
    rep(f"    檢查下游匯出 {db}（scripts/export_stock_db.py → `margin` 表）：")
    if not db.exists():
        rep("      本機沒有 stock.db（它由 .github/workflows/export_db.yml 在 CI 產生）。")
        rep("      ⚠️ 但那條 workflow **每天 UTC 21:00** 把同一份髒序列 force-push 到 `data` 分支，")
        rep("         供下游 2026_strategy_0719 多智能體系統讀取 —— 見 §10 生產影響。")
        return
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            q = pd.read_sql_query(
                "SELECT MIN(date) d0, MAX(date) d1, COUNT(*) n, "
                "MIN(margin_balance) vmin, MAX(margin_balance) vmax FROM margin", con)
            rep(f"      {q.to_string(index=False)}")
            rep("      ⇒ 下游拿到的值域跟本檔一致的話，代表污染已經流到 2026 系統。")
        finally:
            con.close()
    except Exception as e:  # noqa: BLE001
        rep(f"      讀 stock.db 失敗（可能沒有 margin 表）：{type(e).__name__}: {e}")


# ════════════════════════════════════════════════════════════════
# §10 生產影響 + 下一步（靜態說明，不做判斷）
# ════════════════════════════════════════════════════════════════
def sec_impact(rep: Reporter) -> None:
    rep.section("§10  這條序列被誰吃了（靜態 code 追蹤結果，寫死在本腳本裡供對照）")
    rep("""
    以下是撰寫本腳本時做的 code 追蹤結論（file:line 可自行覆核），**不是本次執行的產物**：

    [吃了，且會外流] scripts/export_stock_db.py:107-110 `write_margin()`
        → 原封不動寫進 stock.db 的 `margin` 表
        → .github/workflows/export_db.yml（每日 UTC 21:00 = 台灣 05:00）
          force-push 到本 repo 的 `data` 分支
        → 下游 2026_strategy_0719 多智能體系統讀取。
        ⚠️ 而且 export_stock_db.py 的檔頭「單位鐵則」清單裡，
           `margin` 是**唯一沒有標單位**的一項（:12 對比 :11/:13 都有標）。
        ⇒ **最高優先級的外流點**。

    [已移除 v19.181 detox] 原 src/compute/macro/macro_signal_lookback_tw.py 的
        `fetch_margin_balance_series` (MARGIN_BALANCE) 與
        `fetch_margin_growth_5d_series` (MARGIN_GROWTH_5D)（兩者都寫死 `/1e8`）
        及其消費者 multi_factor_optimization，已隨封閉死簇整組移除
        ⇒ 這條 `/1e8` 離線路徑已不存在（對應 UI 早於 v18.399 R6 刪除）。

    [吃了] scripts/analyze_ring1_gate.py:383-393（本次事故的發現者本身）

    [**沒有**吃] scripts/calibrate_macro_traffic.py
        :96-99 `_enrich_with_finmind()` 確實 join 了 margin_balance，
        但 :178-197 `_Features` dataclass **沒有 margin 欄位**，
        :248-266 / :399-422 餵給 calc_traffic_light 的只有 foreign_buy 與 m1b_m2_gap。
        ⇒ margin 是**掛在 DataFrame 上但從未被讀取**的死欄位。
        ⇒ 季度校準（recalibrate_macro.yml）的輸出 macro_thresholds.json
          （只含 HEALTH_DEFENSE_THRESHOLD / BULL_MIN_SCORE）**不受污染**。
          旁證：該檔現值 last_calibrated=null / method="default (uncalibrated)"
          ⇒ 那支 workflow 到目前為止根本沒寫成功過。
        ⇒ **線上燈號門檻沒有被這條髒序列污染。**（本結論來自 code 靜態追蹤，
           若你想再確認，跑 `git log -p macro_thresholds.json` 看有沒有 bot commit。）

    [**沒有**吃] 線上「融資餘額」燈號
        UI 走 src/data/daily/daily_data_fetchers.py:526 `fetch_margin_balance()`
        （即時 6 路 fallback + `_margin_sanity_ok` 500~10,000 億區間守衛），
        **不讀 parquet**。所以畫面上的融資數字與本檔無關。
""".rstrip())


def sec_next(rep: Reporter) -> None:
    rep.section("§11  跑完之後 —— 要驗證假說還缺的那一步（本腳本刻意不做：會打網路）")
    rep("""
    本腳本能證明「序列裡有兩種口徑」，但**不能**證明「那兩種口徑分別叫什麼」，
    因為 parquet 裡已經沒有 `name` 欄了（在 update_macro_history.py:232 就被丟掉）。

    要坐實假說 H-A / H-C，需要看一次**原始 API 回應**。以下指令會打網路，
    所以**不在本腳本內**，請自行決定要不要跑（需要 FINMIND_TOKEN）：

        python -c "import os,requests,pandas as pd; r=requests.get('https://api.finmindtrade.com/api/v4/data', params={'dataset':'TaiwanStockTotalMarginPurchaseShortSale','start_date':'2026-08-01','end_date':'2026-08-04'}, headers={'Authorization':'Bearer '+os.environ['FINMIND_TOKEN']}, timeout=30); d=pd.DataFrame(r.json()['data']); print(list(d.columns)); print(d.head(20).to_string())"

    看三件事：
      (1) 欄位順序裡，第一個含 'Balance' 的是 TodayBalance 還是 YesterdayBalance？
          → 若是 Yesterday，整條序列日期錯位一天（假說 H-C 成立，§2.3 PIT 違規）
      (2) `name` 欄有哪些值？同一天有幾列？
          → 確認 MarginPurchaseMoney / MarginPurchaseVolume 是否並存（假說 H-A）
      (3) 同一天各列在 JSON 裡的**順序**穩不穩定？
          → 這決定 drop_duplicates(keep="last") 會留下誰
""".rstrip())


# ════════════════════════════════════════════════════════════════
# main
# ════════════════════════════════════════════════════════════════
def main() -> int:
    ap = argparse.ArgumentParser(
        description="finmind_margin.parquet 單位/口徑污染診斷（唯讀，不寫 data_cache）")
    ap.add_argument("--cache-dir", default=None,
                    help="parquet 目錄（預設 <repo>/data_cache）")
    ap.add_argument("--out", default=None,
                    help="報告輸出路徑（預設 scripts/_out/margin_units_report.txt，UTF-8）")
    ap.add_argument("--no-stdout", action="store_true", help="只寫檔，不印畫面")
    ap.add_argument("--start", default=None, help="起始日期 YYYY-MM-DD")
    ap.add_argument("--end", default=None, help="結束日期 YYYY-MM-DD")
    ap.add_argument("--bp-hi", type=float, default=100.0, help="斷點比值上界（預設 100）")
    ap.add_argument("--bp-lo", type=float, default=0.01, help="斷點比值下界（預設 0.01）")
    ap.add_argument("--max-rows", type=int, default=80, help="每張明細表最多印幾列")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    cache_dir = Path(args.cache_dir) if args.cache_dir else (_REPO_ROOT / "data_cache")
    out_path = Path(args.out) if args.out else (_REPO_ROOT / "scripts" / "_out"
                                                / "margin_units_report.txt")

    rep = Reporter(echo=not args.no_stdout)
    rep.rule("=")
    rep("  finmind_margin.parquet 單位/口徑污染診斷（唯讀）")
    rep("  !! 本腳本的作者（AI）從未執行過它 —— 所有數字請以你這次的輸出為準 !!")
    rep(f"  cache_dir = {cache_dir}")
    rep(f"  報告輸出   = {out_path}（Python 自寫 UTF-8；請勿用 PowerShell 的 > 重導向）")
    rep.rule("=")

    path = cache_dir / "finmind_margin.parquet"
    raw = _read_margin(path, rep)
    if raw is None:
        rep.save(out_path)
        return 2

    sec_fingerprint(rep, path, raw)

    rep.section("§0.5  前處理（顯式，不靜默丟資料）")
    df = _prepare(raw, rep, args.start, args.end)
    rep(f"    前處理後 rows = {len(df):,}"
        + (f"（已套用 --start={args.start} --end={args.end}）"
           if (args.start or args.end) else ""))
    if df.empty:
        rep("    [FATAL] 過濾後沒有任何列。")
        rep.save(out_path)
        return 2

    min_yi, max_yi, bsrc = _load_sanity_bounds(rep)
    rep(f"    融資餘額合理區間 = [{min_yi:,.0f}, {max_yi:,.0f}] 億   來源：{bsrc}")
    thr, thr_src = _load_overheat_threshold(rep)
    rep(f"    過熱門檻         = {thr:,.0f} 億   來源：{thr_src}")

    classify, bounds_desc = _make_classifier(min_yi, max_yi)
    df["mode"] = df["margin_balance"].map(classify)

    sec_global(rep, df)
    sec_by_year(rep, df)
    sec_mode(rep, df, bounds_desc, args.max_rows)
    sec_source(rep, df)
    sec_fetched_at(rep, df, args.max_rows)
    sec_breakpoints(rep, df, args.bp_hi, args.bp_lo, args.max_rows)
    sec_anchor_twii(rep, df, cache_dir)
    sec_trigger(rep, df, thr, thr_src)
    sec_crosscheck(rep, cache_dir, _REPO_ROOT)
    sec_impact(rep)
    sec_next(rep)

    rep.section("完")
    rep("    本腳本沒有修改任何資料。修法（重新 bootstrap / 加單位守衛 / 讀取端排除）")
    rep("    屬於**提案**，需你核准後才動，且**絕不**手改 data_cache/*.parquet（§1）。")
    rep(f"    報告已寫入：{out_path}")

    rep.save(out_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001  §1 Fail Loud：印完整 traceback，不吞
        traceback.print_exc()
        raise SystemExit(1)
