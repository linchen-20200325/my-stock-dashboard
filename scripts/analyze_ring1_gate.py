#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""scripts/analyze_ring1_gate.py — 絕對門檻閘門的「歷史關閉率 / 替代門檻 / 事件研究」量測器。

===============================================================================
!! 重要聲明 — 作者從未執行過這支腳本 !!
===============================================================================
本檔由 AI 於「shell 沙箱不可用（session disk not found）」的環境下撰寫，
**作者一次都沒有跑過它**，沒有看過任何一行實際輸出，也沒有跑過任何測試。
所有數字型結論都必須等 user 實際執行後貼回輸出才成立。

因此本腳本刻意採取以下防禦寫法：
  * 每一步都先驗證輸入存在 / 欄位齊全 / 單位合理，不合就大聲說出來（CLAUDE.md §1）
  * 不做任何 fillna / ffill / 猜測換算；算不出就印「算不出 + 為什麼」
  * 任何我沒把握的假設（單位、契約別、發布時點）都印在輸出上讓 user 覆核

如果它在你機器上直接爆掉，那是預期內的風險 —— 請把 traceback 貼回來。


這支腳本在回答什麼問題
===============================================================================
線上「建議持股」目前被壓在 20%，來源是三環第一環 cap：
    ring1_pass = (VIX < 20) AND (外資期貨淨口 > -15000 口)
    ring1_pass == False  =>  持股天花板 20%
      證據：src/services/allocation_service.py:148  `_RING1_FUT_MIN_LOTS = -15000`
            src/services/allocation_service.py:194-207 `_derive_intrinsic_caps()`
            src/ui/tabs/macro/section_mid.py:539-549   `_cA / _cB / _ring1_pass`
            shared/allocation_decision.py:365-378       `ring_gate_cap()`

實測 14 個交易日，外資期貨落在 -74,985 ~ -90,278，**每天**都低於門檻 5 倍以上。
融資餘額同款（紅線 3,400 億 vs 實測 5,235 億），而 shared/macro_buckets.py:271-274
的 margin spec 註解自己就寫著「絕對門檻已被市值成長淹沒、鑑別力歸零」。

假說：這些閘門不是「太嚴格」，而是**永遠關著** => 中間那套五桶 / 健康分 / PCR / VIX
全部白算，系統實質上只剩一個開關。

本腳本用本機已有的歷史資料去**量測**這個假說，不調參數、不下投資建議。


硬性保證
===============================================================================
[唯讀]   只 `pd.read_parquet` / `open(..., 'r')`。除非明確加 `--write-csv`，
         否則一個位元組都不寫。加了也只寫到 `scripts/_out/`（自建目錄），
         **絕不**碰 `data_cache/` / `macro_thresholds.json` / 任何 production 路徑。
[離線]   不 import requests / yfinance / FinMind，不呼叫任何 fetcher。
         只吃 `data_cache/*.parquet`。抓不到就照 §1 明講缺什麼。
[SSOT]   門檻常數優先從 `shared/signal_thresholds.py` / `allocation_service.py` import；
         import 失敗才用字面值 fallback，且**一定**在輸出印出來源 file:line。


已知會踩到的坑（本腳本的處理方式）
===============================================================================
(§4.1 量綱)
  * `finmind_margin.parquet:margin_balance` 原始單位是「元」，要 /1e8 才是「億」。
    公式來源：src/compute/macro/macro_signal_lookback_tw.py:139-150。
    轉換後會做合理性檢查（中位數應落在 100~20000 億），超出就大聲警告。
  * `外資大小` 是 **TX 當量口**（大台淨口 + 0.25 x 小台淨口，
    src/data/macro/leading_indicators.py:262,390），而 `未平倉口數` 是 **MTX 原始口**
    （STATE.md:596 實錘兩者差約 8.9 倍）。所以「外資淨口 / 全市場 OI」佔比版本
    **分子分母契約別不符**，本腳本**不計算**該佔比，只做分位數版本。
  * 報酬視窗一律以「交易日」計（21/63/126 ≈ 1/3/6 個月），**不是日曆日**。

(§2.3 Point-in-Time / 防 lookahead)
  * 融資餘額、三大法人、外資期貨全是**盤後**資料（TWSE ~14:30 TW、TAIFEX ~14:00 TW），
    所以 T 日的訊號最早只能在 **T+1 開盤**進場。本腳本的事件研究一律用
    `entry = open[T+1]`，**不**用 T 日收盤。這點會在輸出中重複標註。
  * 滾動分位數只用「到 t 為止（含 t）」的視窗（pandas rolling 本身即因果），
    不做 centered window、不做全樣本 quantile。

(樣本數誠實)
  * 逐日觸發是**高度重疊**的樣本（連續 200 天亮紅 = 200 個互相重疊的持有視窗），
    統計上不是 200 個獨立觀測。故本腳本同時報告：
      - 逐日樣本數 n_days（會膨脹，僅供參考）
      - **獨立事件數 n_episodes**（連續觸發區段的第一天，才是誠實的樣本數）
    並在 n_episodes < `--min-episodes`（預設 10）時直接標「樣本不足，本節結論不可用」。
  * 右側截斷（最近的觸發日還沒過完 6 個月）會被排除並印出被排除的筆數，
    **不**用較短視窗硬湊（那會偷偷改變樣本組成）。

(存活者偏誤)
  * 不適用 —— 標的是 ^TWII 大盤指數，沒有個股下市問題。


使用方式
===============================================================================
    cd D:\\01.Github\\20260804\\my-Stock-dashboardr1
    python scripts/analyze_ring1_gate.py

Windows 主控台若出現亂碼，建議其一：
    chcp 65001                                    # 切 UTF-8 code page
    python scripts/analyze_ring1_gate.py > scripts/_out/ring1_report.txt 2>&1

常用參數：
    --cache-dir PATH      parquet 目錄（預設 <repo>/data_cache）
    --pct-window N        滾動分位數視窗，交易日（預設 756 ≈ 3 年）
    --pct-levels a,b,c    替代門檻分位（預設 0.90,0.85,0.80）
    --horizons a,b,c      事件研究持有期，交易日（預設 21,63,126）
    --min-episodes N      獨立事件數低於此值即標「樣本不足」（預設 10）
    --start / --end       日期區間過濾（YYYY-MM-DD）
    --all-quarters        印出全部逐季表（預設只印最近 12 季）
    --inspect-pickle      額外檢查 %TEMP%/stock_cache 的先行指標 pickle
                          （預設關閉：unpickle 會執行檔案內的位元組碼；
                            那些檔是你自己 app 寫的，風險自負）
    --write-csv           把逐日明細寫到 scripts/_out/（預設不寫檔）

退出碼：
    0 = 全部分析都跑完
    2 = 主分析（三環第一環）因缺資料無法執行（仍會跑完融資那節）
    1 = 執行期例外
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

SCRIPT_VERSION = "analyze_ring1_gate.py v1 (2026-08-06, UNEXECUTED BY AUTHOR)"

# ── 主控台編碼：Windows cp950 遇到 UTF-8 會炸 UnicodeEncodeError ─────────────
for _stream in ("stdout", "stderr"):
    try:
        getattr(sys, _stream).reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — 舊 Python / 被重導向時沒有 reconfigure，忽略即可
        pass

# ── repo root 進 sys.path（讓 `python scripts/xxx.py` 直跑時 import 得到 shared/src）──
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    import numpy as np
    import pandas as pd
except ImportError as _e:  # §1 Fail Loud：缺套件就講清楚缺什麼，別裝沒事
    print(f"[FATAL] 缺必要套件：{_e}\n請先 `pip install -r requirements.txt`")
    raise SystemExit(1)


# ═══════════════════════════════════════════════════════════════════════════
# 常數載入（優先 SSOT import；失敗則字面值 fallback + 印出來源行號）
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class ConstSource:
    """一個常數的值 + 它是怎麼來的（import 到 or 抄的）。"""
    name: str
    value: float
    origin: str          # "import" | "literal-fallback"
    citation: str        # file:line
    note: str = ""

    def line(self) -> str:
        tag = "SSOT-import" if self.origin == "import" else "字面值 fallback"
        extra = f"  {self.note}" if self.note else ""
        return f"  {self.name:<44} = {self.value:>12,.1f}   [{tag}] {self.citation}{extra}"


def load_constants() -> dict[str, ConstSource]:
    """把本腳本用到的所有門檻常數收在一處，並記錄各自來源。"""
    out: dict[str, ConstSource] = {}

    # ── 三環第一環：外資期貨口數門檻 ────────────────────────────────────
    # 來源 src/services/allocation_service.py:148
    #     `_RING1_FUT_MIN_LOTS: int = -15000`
    # 判定 src/services/allocation_service.py:201
    #     `elif _fut <= _RING1_FUT_MIN_LOTS:` -> 失敗（注意是 <=，不是 <）
    try:
        from src.services.allocation_service import _RING1_FUT_MIN_LOTS as _r1
        out["RING1_FUT_MIN_LOTS"] = ConstSource(
            "RING1_FUT_MIN_LOTS (外資期貨, 口)", float(_r1), "import",
            "src/services/allocation_service.py:148")
    except Exception as _e:  # noqa: BLE001 — 該模組 import streamlit，純 CLI 可能失敗
        out["RING1_FUT_MIN_LOTS"] = ConstSource(
            "RING1_FUT_MIN_LOTS (外資期貨, 口)", -15000.0, "literal-fallback",
            "src/services/allocation_service.py:148",
            note=f"(import 失敗: {type(_e).__name__})")

    # ── 三環第一環：VIX 門檻（inline，無具名常數）──────────────────────
    # src/services/allocation_service.py:196  `elif _vix >= 20:` -> 失敗
    # src/ui/tabs/macro/section_mid.py:539     `_cA = _vix_now8 is not None and _vix_now8 < 20`
    out["RING1_VIX_MAX"] = ConstSource(
        "RING1_VIX_MAX (VIX 上限)", 20.0, "literal-fallback",
        "src/services/allocation_service.py:196 + section_mid.py:539",
        note="(該處為 inline 數字，無具名常數可 import)")

    # ── 融資餘額紅線 / 黃線 ────────────────────────────────────────────
    try:
        from shared.signal_thresholds import (
            MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI as _mo,
            MARGIN_BALANCE_WARN_THRESHOLD_YI as _mw,
            FOREIGN_5D_NET_THRESHOLD_YI as _f5,
        )
        out["MARGIN_RED_YI"] = ConstSource(
            "MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI (億)", float(_mo), "import",
            "shared/signal_thresholds.py:122")
        out["MARGIN_YELLOW_YI"] = ConstSource(
            "MARGIN_BALANCE_WARN_THRESHOLD_YI (億)", float(_mw), "import",
            "shared/signal_thresholds.py:543")
        out["FOREIGN_5D_YI"] = ConstSource(
            "FOREIGN_5D_NET_THRESHOLD_YI (億)", float(_f5), "import",
            "shared/signal_thresholds.py:118")
    except Exception as _e:  # noqa: BLE001
        out["MARGIN_RED_YI"] = ConstSource(
            "MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI (億)", 3400.0, "literal-fallback",
            "shared/signal_thresholds.py:122", note=f"(import 失敗: {type(_e).__name__})")
        out["MARGIN_YELLOW_YI"] = ConstSource(
            "MARGIN_BALANCE_WARN_THRESHOLD_YI (億)", 2500.0, "literal-fallback",
            "shared/signal_thresholds.py:543")
        out["FOREIGN_5D_YI"] = ConstSource(
            "FOREIGN_5D_NET_THRESHOLD_YI (億)", -500.0, "literal-fallback",
            "shared/signal_thresholds.py:118")
    return out


# ── 滾動分位數：優先用專案 SSOT（shared/stats_helpers.rolling_pct_rank）──────
def _rolling_pct_rank(s: "pd.Series", window: int) -> "pd.Series":
    """回傳每個時點在其**過去 window 日（含當日）**內的百分位排名 0~1。

    優先 import `shared.stats_helpers.rolling_pct_rank`（專案 SSOT，
    shared/stats_helpers.py:222，內部 min_periods = max(20, window // 4)）。
    import 失敗才用同式 fallback，並印出警告。

    因果性：pandas `rolling` 的視窗永遠是「到 t 為止」，不含未來 —— 無 lookahead。
    """
    try:
        from shared.stats_helpers import rolling_pct_rank as _rpr
        return _rpr(s, window=window)
    except Exception as _e:  # noqa: BLE001
        print(f"  [WARN] 無法 import shared.stats_helpers.rolling_pct_rank"
              f"（{type(_e).__name__}: {_e}），改用同式 inline fallback"
              f"（公式抄自 shared/stats_helpers.py:257-263）")
        if s.empty:
            return s
        mp = max(20, window // 4)
        return s.rolling(window, min_periods=mp).rank(pct=True)


# ═══════════════════════════════════════════════════════════════════════════
# 通用工具
# ═══════════════════════════════════════════════════════════════════════════
def hr(char: str = "=", n: int = 79) -> str:
    return char * n


def section(title: str, question: str) -> None:
    print()
    print(hr("="))
    print(title)
    print(f"  [這節在回答什麼] {question}")
    print(hr("="))


def sub(title: str) -> None:
    print()
    print(f"-- {title} " + "-" * max(0, 76 - len(title)))


def sha12(path: Path) -> str:
    """檔案 sha256 前 12 碼（§5 可重現性：讓輸出可回溯到確切的輸入檔）。"""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()[:12]
    except Exception as e:  # noqa: BLE001
        return f"<sha 失敗:{type(e).__name__}>"


def fmt_pct(x: Optional[float], nd: int = 2) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "  n/a  "
    return f"{x * 100:.{nd}f}%"


def fmt_num(x: Optional[float], nd: int = 2) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    return f"{x:,.{nd}f}"


def read_parquet_safe(path: Path, required_cols: set[str]) -> tuple[Optional["pd.DataFrame"], str]:
    """安全讀 parquet。回 (df, reason)；df=None 時 reason 說明為什麼。

    行為對齊 src/data/macro/macro_cache_reader.py:25-44 `load_parquet_safe`，
    但額外把「為什麼失敗」回傳出來（§1：不能只回 None 讓上游猜）。
    優先呼叫專案 SSOT，失敗才用本地實作。
    """
    if not path.exists():
        return None, f"檔案不存在：{path}"
    try:
        from src.data.macro.macro_cache_reader import load_parquet_safe as _lps
        df = _lps(path, required_cols)
        if df is None:
            # SSOT 版不說原因，這裡自己再讀一次找出真因
            try:
                raw = pd.read_parquet(path)
            except Exception as e:  # noqa: BLE001
                return None, f"讀檔失敗：{type(e).__name__}: {e}"
            if raw.empty:
                return None, "檔案存在但 0 列"
            missing = required_cols - set(raw.columns)
            return None, (f"缺欄位 {sorted(missing)}；"
                          f"實際欄位={list(raw.columns)}")
        return df, "ok (via macro_cache_reader.load_parquet_safe)"
    except ImportError:
        pass
    except Exception as e:  # noqa: BLE001
        return None, f"macro_cache_reader 失敗：{type(e).__name__}: {e}"
    # fallback：本地實作
    try:
        df = pd.read_parquet(path)
    except Exception as e:  # noqa: BLE001
        return None, f"讀檔失敗：{type(e).__name__}: {e}"
    if df.empty:
        return None, "檔案存在但 0 列"
    missing = required_cols - set(df.columns)
    if missing:
        return None, f"缺欄位 {sorted(missing)}；實際欄位={list(df.columns)}"
    return df, "ok (local fallback reader)"


def to_dated_series(df: "pd.DataFrame", value_col: str, name: str) -> "pd.Series":
    """DataFrame(date, value_col) -> 以 DatetimeIndex 排序、去重、dropna 的 Series。

    §1：dropna 是**顯式**呼叫，且下方一律回報被丟掉幾筆，不靜默。
    """
    s = (df.assign(_d=pd.to_datetime(df["date"]))
           .sort_values("_d")
           .drop_duplicates(subset=["_d"], keep="last")
           .set_index("_d")[value_col]
           .astype(float))
    s.index.name = "date"
    s.name = name
    return s


def runs_of(mask: "pd.Series") -> list[tuple[int, int, bool]]:
    """把布林序列切成連續區段，回 [(start_pos, end_pos_exclusive, value), ...]。"""
    vals = mask.to_numpy(dtype=bool)
    if vals.size == 0:
        return []
    change = np.flatnonzero(np.diff(vals.astype(np.int8)) != 0) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [vals.size]))
    return [(int(a), int(b), bool(vals[a])) for a, b in zip(starts, ends)]


def episodes_of(mask: "pd.Series", value: bool = True) -> list[tuple["pd.Timestamp", "pd.Timestamp", int]]:
    """取出所有 value 狀態的連續區段 (起日, 訖日, 天數)。"""
    out = []
    for a, b, v in runs_of(mask):
        if v is value:
            out.append((mask.index[a], mask.index[b - 1], b - a))
    return out


# ═══════════════════════════════════════════════════════════════════════════
# 資料載入器（純唯讀，各自帶單位轉換 + 合理性檢查）
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class LoadedSeries:
    key: str
    label: str
    unit: str
    series: Optional["pd.Series"]
    source_file: str
    formula: str
    reason: str
    n_raw: int = 0
    n_dropped_na: int = 0
    sanity_ok: bool = True
    sanity_msg: str = ""


def load_margin_yi(cache_dir: Path) -> LoadedSeries:
    """融資餘額（億元）。

    公式：margin_balance / 1e8（原始 parquet 單位是「元」）
    來源：src/compute/macro/macro_signal_lookback_tw.py:139-150 `fetch_margin_balance_series`
    """
    path = cache_dir / "finmind_margin.parquet"
    df, reason = read_parquet_safe(path, {"date", "margin_balance"})
    ls = LoadedSeries("margin_yi", "融資餘額", "億 TWD", None,
                      str(path), "margin_balance / 1e8", reason)
    if df is None:
        return ls
    ls.n_raw = len(df)
    s = to_dated_series(df, "margin_balance", "MARGIN_BALANCE_YI") / 1e8
    before = len(s)
    s = s.dropna()
    ls.n_dropped_na = before - len(s)
    ls.series = s
    # §4.1 單位合理性：台股融資餘額歷史大致 800 ~ 6000 億；抓寬到 [100, 20000]
    if not s.empty:
        med = float(s.median())
        if not (100.0 <= med <= 20000.0):
            ls.sanity_ok = False
            ls.sanity_msg = (f"中位數 {med:,.1f} 億 落在合理區間 [100, 20000] 之外 —— "
                             f"上游單位可能不是「元」(本腳本假設 /1e8)。"
                             f"原始中位數 = {med * 1e8:,.0f}。**下方所有融資結論請先存疑**")
    return ls


def load_foreign_spot_5d_yi(cache_dir: Path) -> LoadedSeries:
    """外資**現貨**5 日累積買賣超（億元）。

    公式：foreign_buy.rolling(5, min_periods=5).sum()
    來源：src/compute/macro/macro_signal_lookback_tw.py:116-133
    注意：這是**現貨**，不是期貨。它 **不是**三環第一環那條期貨序列的替代品。
    """
    path = cache_dir / "finmind_inst.parquet"
    df, reason = read_parquet_safe(path, {"date", "foreign_buy"})
    ls = LoadedSeries("foreign_spot_5d_yi", "外資現貨 5 日累積買賣超", "億 TWD", None,
                      str(path), "foreign_buy.rolling(5).sum()", reason)
    if df is None:
        return ls
    ls.n_raw = len(df)
    s0 = to_dated_series(df, "foreign_buy", "FOREIGN_BUY_YI")
    s = s0.rolling(window=5, min_periods=5).sum()
    s.name = "FOREIGN_SELL_5D_YI"
    before = len(s)
    s = s.dropna()
    ls.n_dropped_na = before - len(s)
    ls.series = s
    if not s.empty:
        p99 = float(s.abs().quantile(0.99))
        if p99 > 20000.0:
            ls.sanity_ok = False
            ls.sanity_msg = (f"|5 日累積| 的 P99 = {p99:,.0f} 億，異常巨大 —— "
                             f"上游 foreign_buy 可能不是「億」。**結論請先存疑**")
    return ls


def load_twii_ohlcv(cache_dir: Path) -> tuple[Optional["pd.DataFrame"], str, dict]:
    """^TWII 日 K。回 (df, reason, diag)；df 以 DatetimeIndex 排序去重。

    來源：data_cache/twii_ohlcv.parquet（scripts/update_macro_history.py:151-183 寫入）
    """
    path = cache_dir / "twii_ohlcv.parquet"
    df, reason = read_parquet_safe(path, {"date", "open", "high", "low", "close"})
    diag: dict = {"path": str(path)}
    if df is None:
        return None, reason, diag
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = (d.sort_values("date")
           .drop_duplicates(subset=["date"], keep="last")
           .set_index("date"))
    for c in ("open", "high", "low", "close"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    diag["n_rows"] = len(d)
    diag["n_close_na"] = int(d["close"].isna().sum())
    diag["n_open_na"] = int(d["open"].isna().sum())
    # §4.2 不變量斷言（只報告，不修正）
    ok = d[["open", "high", "low", "close"]].notna().all(axis=1)
    sub_d = d[ok]
    viol_lohi = int((sub_d["low"] > sub_d["high"]).sum())
    viol_oc = int(((sub_d["open"] > sub_d["high"]) | (sub_d["open"] < sub_d["low"]) |
                   (sub_d["close"] > sub_d["high"]) | (sub_d["close"] < sub_d["low"])).sum())
    diag["ohlc_violation_low_gt_high"] = viol_lohi
    diag["ohlc_violation_oc_out_of_range"] = viol_oc
    diag["monotonic"] = bool(d.index.is_monotonic_increasing)
    diag["unique"] = bool(d.index.is_unique)
    return d, reason, diag


# ═══════════════════════════════════════════════════════════════════════════
# 閘門規格
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class GateSpec:
    key: str
    label: str
    unit: str
    threshold: float
    direction: str            # "above" = value >= thr 觸發; "below" = value <= thr 觸發
    threshold_citation: str
    publish_lag: str          # PIT 說明
    consequence: str          # 觸發後系統做什麼


def gate_mask(s: "pd.Series", spec: GateSpec) -> "pd.Series":
    """閘門是否「關閉 / 亮紅」。語意與 production 一致（含等號）。"""
    if spec.direction == "above":
        return s >= spec.threshold
    return s <= spec.threshold


# ═══════════════════════════════════════════════════════════════════════════
# Step 1：閘門關閉率
# ═══════════════════════════════════════════════════════════════════════════
def report_closure(mask: "pd.Series", spec: GateSpec, s: "pd.Series",
                   all_quarters: bool) -> dict:
    n_total = int(mask.size)
    n_closed = int(mask.sum())
    pct = (n_closed / n_total) if n_total else float("nan")

    print(f"  序列期間        : {mask.index[0].date()} ~ {mask.index[-1].date()}")
    print(f"  總交易日數      : {n_total:,}")
    print(f"  觸發（關閉）日數: {n_closed:,}")
    print(f"  **關閉比例**    : {fmt_pct(pct)}")
    print(f"  判定式          : value {'>=' if spec.direction == 'above' else '<='} "
          f"{spec.threshold:,.1f} {spec.unit}   [{spec.threshold_citation}]")
    print(f"  序列統計        : min={fmt_num(float(s.min()))} / "
          f"P25={fmt_num(float(s.quantile(.25)))} / "
          f"median={fmt_num(float(s.median()))} / "
          f"P75={fmt_num(float(s.quantile(.75)))} / "
          f"max={fmt_num(float(s.max()))} {spec.unit}")

    # 逐年
    sub("逐年關閉比例（看它是不是近年才失效）")
    by_year = pd.DataFrame({"n": 1, "closed": mask.astype(int)}).groupby(mask.index.year).sum()
    by_year["pct"] = by_year["closed"] / by_year["n"]
    print(f"  {'年':<6}{'交易日':>8}{'觸發日':>8}{'關閉比例':>12}   分佈")
    for y, row in by_year.iterrows():
        bar = "#" * int(round(row["pct"] * 40))
        print(f"  {int(y):<6}{int(row['n']):>8}{int(row['closed']):>8}"
              f"{fmt_pct(row['pct'], 1):>12}   {bar}")

    # 逐季
    q_idx = mask.index.to_period("Q")
    by_q = pd.DataFrame({"n": 1, "closed": mask.astype(int)}).groupby(q_idx).sum()
    by_q["pct"] = by_q["closed"] / by_q["n"]
    shown = by_q if all_quarters else by_q.tail(12)
    sub(f"逐季關閉比例（顯示 {len(shown)} / {len(by_q)} 季"
        f"{'' if all_quarters else '，全部請加 --all-quarters'}）")
    print(f"  {'季':<10}{'交易日':>8}{'觸發日':>8}{'關閉比例':>12}")
    for q, row in shown.iterrows():
        print(f"  {str(q):<10}{int(row['n']):>8}{int(row['closed']):>8}"
              f"{fmt_pct(row['pct'], 1):>12}")

    # 連續關閉
    eps = episodes_of(mask, True)
    sub("連續關閉區段")
    if not eps:
        print("  （期間內從未觸發）")
    else:
        longest = max(eps, key=lambda t: t[2])
        print(f"  獨立關閉事件數（連續區段）: {len(eps):,}")
        print(f"  **最長連續關閉天數**      : {longest[2]:,} 個交易日"
              f"  ({longest[0].date()} ~ {longest[1].date()})")
        lens = np.array([e[2] for e in eps], dtype=float)
        print(f"  區段長度分佈              : median={np.median(lens):.0f} / "
              f"mean={lens.mean():.1f} / max={lens.max():.0f} 交易日")
        print("  最近 5 段：")
        for a, b, n in eps[-5:]:
            print(f"    {a.date()} ~ {b.date()}  ({n} 交易日)")
    # 目前狀態
    print(f"  序列最後一日 {mask.index[-1].date()} 的值 = "
          f"{fmt_num(float(s.iloc[-1]))} {spec.unit} -> "
          f"{'觸發（閘門關閉）' if bool(mask.iloc[-1]) else '未觸發（閘門開啟）'}")
    return {"n_total": n_total, "n_closed": n_closed, "pct": pct,
            "n_episodes": len(eps)}


# ═══════════════════════════════════════════════════════════════════════════
# Step 2：替代門檻（滾動分位數）
# ═══════════════════════════════════════════════════════════════════════════
def report_alternative_thresholds(s: "pd.Series", spec: GateSpec,
                                  window_req: int, levels: Sequence[float]) -> dict:
    n = int(s.size)
    window = int(min(window_req, n))
    if window < 2:
        print(f"  [FAIL] 序列長度 {n} < 2，無法計算滾動分位數。")
        return {}
    if window < window_req:
        print(f"  [WARN] 要求視窗 {window_req} 交易日 > 可得序列長度 {n}，"
              f"**改用可得的最長視窗 {window}**（結論的「歷史」比預期短，請留意）。")
    else:
        print(f"  滾動視窗 = {window} 交易日（≈ {window / 252:.1f} 年）")

    pr = _rolling_pct_rank(s, window)
    n_nan = int(pr.isna().sum())
    print(f"  暖機期（分位算不出而排除）: {n_nan:,} 個交易日"
          f"（min_periods = max(20, window//4) = {max(20, window // 4)}）")
    high_bad = (spec.direction == "above")
    p_bad = pr if high_bad else (1.0 - pr)

    # 絕對門檻的對照
    abs_mask = gate_mask(s, spec)
    abs_valid = abs_mask[pr.notna()]
    print()
    print(f"  {'門檻':<28}{'觸發日數':>10}{'觸發比例':>12}{'獨立事件':>10}"
          f"{'最新門檻值':>16}")
    print("  " + "-" * 76)
    print(f"  {'絕對門檻（現行）':<28}{int(abs_valid.sum()):>10}"
          f"{fmt_pct(float(abs_valid.mean()), 1):>12}"
          f"{len(episodes_of(abs_valid, True)):>10}"
          f"{spec.threshold:>16,.1f}")

    out = {}
    for q in levels:
        if not (0.0 < q < 1.0):
            print(f"  [WARN] 跳過非法分位 {q}（需 0 < q < 1）")
            continue
        m = (p_bad >= q) & pr.notna()
        m = m[pr.notna()]
        # 該分位對應的「實際門檻值」（最後一日）：high_bad 取 q 分位，low_bad 取 1-q 分位
        qv = s.rolling(window, min_periods=max(20, window // 4)).quantile(
            q if high_bad else (1.0 - q))
        qv_last = float(qv.iloc[-1]) if np.isfinite(qv.iloc[-1]) else float("nan")
        eps = episodes_of(m, True)
        # 標籤先算好再進 f-string —— 避免巢狀 f-string 在 Python < 3.12 的解析地雷
        _row_label = "滾動分位 {:.2f}".format(q)
        print(f"  {_row_label:<28}{int(m.sum()):>10}"
              f"{fmt_pct(float(m.mean()), 1):>12}{len(eps):>10}"
              f"{qv_last:>16,.1f}")
        out[q] = {"mask": m, "n": int(m.sum()), "rate": float(m.mean()),
                  "episodes": len(eps), "latest_threshold": qv_last}

    # 觸發日的年度分佈
    if out:
        sub("替代門檻的觸發日逐年分佈（每格 = 該年觸發日數）")
        years = sorted(set(s.index.year))
        head = "  " + f"{'分位':<8}" + "".join(f"{y % 100:>5}" for y in years)
        print(head)
        for q, d in out.items():
            m = d["mask"]
            cnt = m.groupby(m.index.year).sum()
            row = "  " + f"{q:<8.2f}" + "".join(
                f"{int(cnt.get(y, 0)):>5}" for y in years)
            print(row)
        am = abs_valid
        cnt = am.groupby(am.index.year).sum()
        print("  " + f"{'絕對':<8}" + "".join(f"{int(cnt.get(y, 0)):>5}" for y in years))
    return out


# ═══════════════════════════════════════════════════════════════════════════
# Step 3：事件研究（PIT 嚴格：T 日訊號 -> T+1 開盤進場）
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class EventStats:
    n: int = 0
    n_excluded_censored: int = 0
    n_excluded_bad_price: int = 0
    median: float = float("nan")
    mean: float = float("nan")
    win_rate: float = float("nan")
    p05: float = float("nan")
    p95: float = float("nan")
    mdd_median: float = float("nan")
    mdd_mean: float = float("nan")
    mdd_worst: float = float("nan")
    n_mdd: int = 0


def _forward_stats(entry_pos: "np.ndarray", px: "pd.DataFrame", h: int) -> EventStats:
    """給定一組進場位置（已是 T+1），算 h 個交易日後的報酬與路徑最大回撤。

    定義（寫死在此，輸出會標註）：
      進場價 = open[entry_pos]            <- T+1 開盤（§2.3 禁用 T 日收盤）
      出場價 = close[entry_pos + h]
      報酬   = 出場價 / 進場價 - 1
      MDD    = min over path of (p / cummax(p) - 1)，
               path = [進場價] + close[entry_pos .. entry_pos + h]
    """
    st = EventStats()
    n_all = len(px)
    o = px["open"].to_numpy(dtype=float)
    c = px["close"].to_numpy(dtype=float)

    exit_pos = entry_pos + h
    ok_range = exit_pos < n_all
    st.n_excluded_censored = int((~ok_range).sum())
    ep = entry_pos[ok_range]
    xp = exit_pos[ok_range]
    if ep.size == 0:
        return st

    entry_px = o[ep]
    exit_px = c[xp]
    ok_px = np.isfinite(entry_px) & np.isfinite(exit_px) & (entry_px > 0)
    st.n_excluded_bad_price = int((~ok_px).sum())
    ep, xp = ep[ok_px], xp[ok_px]
    entry_px, exit_px = entry_px[ok_px], exit_px[ok_px]
    if ep.size == 0:
        return st

    ret = exit_px / entry_px - 1.0
    st.n = int(ret.size)
    st.median = float(np.median(ret))
    st.mean = float(np.mean(ret))
    st.win_rate = float((ret > 0).mean())
    st.p05 = float(np.percentile(ret, 5))
    st.p95 = float(np.percentile(ret, 95))

    # 路徑 MDD：(m, h+1) 矩陣。h=126、m=5000 時約 5MB，可接受。
    offs = np.arange(0, h + 1)
    rows = ep[:, None] + offs[None, :]
    path_close = c[rows]
    path = np.concatenate([entry_px[:, None], path_close], axis=1)
    finite_row = np.isfinite(path).all(axis=1)
    p = path[finite_row]
    if p.shape[0] > 0:
        run_max = np.maximum.accumulate(p, axis=1)
        dd = p / run_max - 1.0
        mdd = dd.min(axis=1)
        st.n_mdd = int(mdd.size)
        st.mdd_median = float(np.median(mdd))
        st.mdd_mean = float(np.mean(mdd))
        st.mdd_worst = float(np.min(mdd))
    return st


def report_event_study(mask: "pd.Series", px: "pd.DataFrame", spec: GateSpec,
                       horizons: Sequence[int], min_episodes: int) -> None:
    """觸發日 vs 未觸發日的前瞻報酬對照（PIT：T+1 開盤進場）。"""
    # 對齊：只用「同時存在於閘門序列與 TWII 交易日」的日期
    common = mask.index.intersection(px.index)
    n_gate_only = int(len(mask.index.difference(px.index)))
    n_px_only = int(len(px.index.difference(mask.index)))
    print(f"  日期對齊：閘門序列 {len(mask):,} 日 / TWII {len(px):,} 日 / "
          f"交集 {len(common):,} 日")
    print(f"            閘門有但 TWII 無 = {n_gate_only:,} 日；"
          f"TWII 有但閘門無 = {n_px_only:,} 日（兩者皆**排除**，不做 ffill 補值）")
    if len(common) == 0:
        print("  [FAIL] 交集為 0，無法做事件研究。")
        return

    m = mask.reindex(common).astype(bool)
    pos_map = pd.Series(np.arange(len(px)), index=px.index)
    t_pos = pos_map.reindex(common).to_numpy(dtype=np.int64)
    entry_pos_all = t_pos + 1  # <-- §2.3 PIT：T 日盤後訊號，最早 T+1 開盤才進得去

    trig = m.to_numpy(dtype=bool)
    eps_trig = episodes_of(m, True)
    eps_open = episodes_of(m, False)

    # 事件層級樣本：每個連續區段只取「第一天」，避免重疊視窗灌水
    first_day_trig = np.zeros(len(m), dtype=bool)
    first_day_open = np.zeros(len(m), dtype=bool)
    for a, b, v in runs_of(m):
        (first_day_trig if v else first_day_open)[a] = True

    print()
    print(f"  進場規則（寫死）：訊號日 T -> **進場價 = T+1 開盤**（{spec.publish_lag}）")
    print(f"  出場規則（寫死）：進場後持有 h 個交易日 -> 出場價 = close[T+1+h]")
    print(f"  持有期換算      ：21 ≈ 1 個月 / 63 ≈ 3 個月 / 126 ≈ 6 個月（**交易日，非日曆日**）")
    print()
    print(f"  逐日樣本數      ：觸發 {int(trig.sum()):,} 日 / 未觸發 {int((~trig).sum()):,} 日")
    print(f"  **獨立事件數**  ：觸發 {len(eps_trig):,} 段 / 未觸發 {len(eps_open):,} 段")
    print("  [!] 逐日樣本互相重疊（連續 N 天亮紅 = N 個重疊的持有視窗），")
    print("      統計上**不是** N 個獨立觀測。下表「逐日」欄僅供參考，")
    print("      **請以「事件」欄（每段只取第一天）為準**。")

    if len(eps_trig) < min_episodes:
        print()
        print(f"  ##############################################################")
        print(f"  # 樣本不足：獨立觸發事件僅 {len(eps_trig)} 段 < 門檻 {min_episodes} 段。")
        print(f"  # **本節結論不可用** —— 任何中位數 / 勝率都只是雜訊。")
        print(f"  ##############################################################")

    for level_name, sel_trig, sel_open in (
        ("逐日（重疊，僅供參考）", trig, ~trig),
        ("事件（每段第一天，主要依據）", first_day_trig, first_day_open),
    ):
        sub(f"{level_name}")
        print(f"  {'持有期':<10}{'組別':<8}{'N':>7}{'中位數':>10}{'平均':>10}"
              f"{'勝率':>9}{'P05':>10}{'P95':>10}{'MDD中位':>10}{'MDD最差':>10}")
        print("  " + "-" * 92)
        for h in horizons:
            for gname, sel in (("觸發", sel_trig), ("未觸發", sel_open)):
                st = _forward_stats(entry_pos_all[sel], px, h)
                print(f"  {str(h) + 'd':<10}{gname:<8}{st.n:>7}"
                      f"{fmt_pct(st.median, 2):>10}{fmt_pct(st.mean, 2):>10}"
                      f"{fmt_pct(st.win_rate, 1):>9}"
                      f"{fmt_pct(st.p05, 1):>10}{fmt_pct(st.p95, 1):>10}"
                      f"{fmt_pct(st.mdd_median, 1):>10}{fmt_pct(st.mdd_worst, 1):>10}")
                if st.n_excluded_censored or st.n_excluded_bad_price:
                    print(f"  {'':<18}(排除：右側截斷 {st.n_excluded_censored} 筆 / "
                          f"價格不可用 {st.n_excluded_bad_price} 筆；MDD 有效 {st.n_mdd} 筆)")
            print("  " + "." * 92)
    print()
    print("  [讀法提醒] 這裡量的是「閘門關閉之後大盤怎麼走」。")
    print("             若觸發組與未觸發組的分佈幾乎一樣，代表這個閘門沒有鑑別力；")
    print("             但**相關不等於因果**，且本節未做顯著性檢定（重疊樣本下 p 值會嚴重高估）。")


# ═══════════════════════════════════════════════════════════════════════════
# Step 0：資料盤點
# ═══════════════════════════════════════════════════════════════════════════
def scan_parquet_columns(cache_dir: Path) -> list[tuple[Path, list[str], int]]:
    """掃 cache_dir 下所有 parquet 的欄位名（優先只讀 schema，不載入資料）。"""
    out = []
    for p in sorted(cache_dir.rglob("*.parquet")):
        cols: list[str] = []
        nrows = -1
        try:
            import pyarrow.parquet as pq  # noqa: PLC0415
            pf = pq.ParquetFile(p)
            cols = list(pf.schema_arrow.names)
            nrows = int(pf.metadata.num_rows)
        except Exception:  # noqa: BLE001 — 沒 pyarrow / 版本差異就退回 pandas
            try:
                df = pd.read_parquet(p)
                cols = list(df.columns)
                nrows = len(df)
            except Exception as e:  # noqa: BLE001
                cols = [f"<讀取失敗 {type(e).__name__}>"]
        out.append((p, cols, nrows))
    return out


def inspect_leading_pickle() -> list[str]:
    """檢查 %TEMP%/stock_cache 內的先行指標 pickle（只做盤點，**不拿來算統計**）。

    路徑 SSOT：shared/cache_layer.py:28
        _PKL_DIR = os.environ.get('STK_PKL_DIR') or tempfile.gettempdir()/'stock_cache'
    檔名是 md5(f'lead_fast_{days}_{token}')，含 FinMind token，無法反推 -> 只能全掃。
    """
    import glob
    import pickle
    import tempfile
    import time

    lines: list[str] = []
    pkl_dir = os.environ.get("STK_PKL_DIR") or os.path.join(tempfile.gettempdir(), "stock_cache")
    lines.append(f"  pickle 目錄：{pkl_dir}")
    if not os.path.isdir(pkl_dir):
        lines.append("  -> 目錄不存在（本機從未跑過 app，或 TEMP 已被清）")
        return lines
    files = sorted(glob.glob(os.path.join(pkl_dir, "*.pkl")))
    lines.append(f"  -> 找到 {len(files)} 個 .pkl")
    hit = 0
    for f in files:
        try:
            age_min = (time.time() - os.path.getmtime(f)) / 60.0
            with open(f, "rb") as fh:
                obj = pickle.load(fh)
        except Exception:  # noqa: BLE001 — 壞檔 / 版本不容 / 非 DataFrame，跳過即可
            continue
        if not isinstance(obj, pd.DataFrame) or "外資大小" not in getattr(obj, "columns", []):
            continue
        hit += 1
        col = pd.to_numeric(obj["外資大小"], errors="coerce")
        dates = obj["Date"] if "Date" in obj.columns else obj.index
        lines.append(f"  [命中] {os.path.basename(f)}")
        lines.append(f"         age = {age_min:,.1f} 分（{age_min / 60 / 24:.2f} 天）"
                     f" / 上限 _STALE_MAX_AGE_MIN = 4320 分"
                     f"（leading_indicators.py:1126）")
        lines.append(f"         列數 = {len(obj)}；欄位 = {list(obj.columns)[:12]}")
        lines.append(f"         日期 = {list(map(str, list(dates)[:3]))} ... "
                     f"{list(map(str, list(dates)[-3:]))}")
        lines.append(f"         外資大小：min={fmt_num(float(col.min()), 0)} / "
                     f"max={fmt_num(float(col.max()), 0)} / "
                     f"非空 {int(col.notna().sum())} 筆")
    if hit == 0:
        lines.append("  -> 沒有任何 pkl 含 `外資大小` 欄")
    lines.append("  [注意] 即使命中，這份快取也只有 build_leading_fast(days=7) 量級的長度")
    lines.append("         （src/data/macro/leading_indicators.py:1196 預設 days=7），")
    lines.append("         且 3 個交易日就會被判超齡丟棄。**本腳本不會拿它做任何統計**。")
    return lines


def step0_inventory(cache_dir: Path, args) -> dict:
    section("§0  資料盤點",
            "本機到底有哪些歷史序列？各自欄位 / 起訖日 / 筆數 / 缺漏率是多少？")

    print(f"  cache 目錄：{cache_dir}")
    if not cache_dir.is_dir():
        print(f"  [FATAL] 目錄不存在。請用 --cache-dir 指定，或確認你在 repo 根目錄執行。")
        return {}

    # metadata.json
    meta_path = cache_dir / "metadata.json"
    meta = {}
    sub("metadata.json（cron 自報的更新狀態）")
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            print(f"  updated_at = {meta.get('updated_at')}")
            print(f"  {'dataset':<20}{'last_updated':<14}{'rows':>8}   last_error")
            for k, v in (meta.get("datasets") or {}).items():
                print(f"  {k:<20}{str(v.get('last_updated')):<14}"
                      f"{int(v.get('row_count') or 0):>8}   {v.get('last_error') or '-'}")
        except Exception as e:  # noqa: BLE001
            print(f"  [WARN] 解析失敗：{type(e).__name__}: {e}")
    else:
        print(f"  [MISSING] {meta_path} 不存在")

    # 全 parquet 欄位掃描
    sub("data_cache/ 全 parquet 欄位掃描（找 `外資大小` / fut_net / VIX / 市值）")
    scanned = scan_parquet_columns(cache_dir)
    if not scanned:
        print("  [MISSING] 目錄下沒有任何 .parquet")
    for p, cols, nrows in scanned:
        rel = p.relative_to(cache_dir)
        print(f"  {str(rel):<44} rows={nrows:>7}  cols={cols}")
    futures_hits = [str(p) for p, cols, _ in scanned
                    if any(("外資大小" in c) or ("fut_net" in c.lower())
                           or ("futures" in c.lower()) for c in cols)]
    vix_hits = [str(p) for p, cols, _ in scanned
                if any("vix" in c.lower() for c in cols)]
    cap_hits = [str(p) for p, cols, _ in scanned
                if any(("market_cap" in c.lower()) or ("市值" in c) for c in cols)]
    print()
    print(f"  含「外資期貨淨口」欄的 parquet : {futures_hits or '**無**'}")
    print(f"  含「VIX」欄的 parquet          : {vix_hits or '**無**'}")
    print(f"  含「總市值」欄的 parquet       : {cap_hits or '**無**'}")

    # pickle
    sub("先行指標 pickle（外資期貨淨口的唯一落地處）")
    if args.inspect_pickle:
        for ln in inspect_leading_pickle():
            print(ln)
    else:
        print("  （未檢查。加 --inspect-pickle 可掃描 %TEMP%/stock_cache；")
        print("    注意 unpickle 會執行檔案內位元組碼 —— 那些檔是你自己 app 寫的，風險自負。）")

    # 主表盤點
    sub("本腳本會用到的序列（含單位轉換與合理性檢查）")
    loaders: list[Callable[[Path], LoadedSeries]] = [load_margin_yi, load_foreign_spot_5d_yi]
    loaded: dict[str, LoadedSeries] = {}
    print(f"  {'序列':<26}{'單位':<10}{'起日':<12}{'訖日':<12}{'筆數':>8}{'缺漏':>8}  狀態")
    print("  " + "-" * 96)
    for fn in loaders:
        ls = fn(cache_dir)
        loaded[ls.key] = ls
        if ls.series is None or ls.series.empty:
            print(f"  {ls.label:<26}{ls.unit:<10}{'-':<12}{'-':<12}{0:>8}{'-':>8}  "
                  f"[MISSING] {ls.reason}")
            continue
        s = ls.series
        print(f"  {ls.label:<26}{ls.unit:<10}{str(s.index[0].date()):<12}"
              f"{str(s.index[-1].date()):<12}{len(s):>8}{ls.n_dropped_na:>8}  "
              f"[OK] {ls.reason}")
        print(f"  {'':<26}公式 = {ls.formula}   檔案 = {Path(ls.source_file).name}"
              f"  sha256[:12] = {sha12(Path(ls.source_file))}")
        if not ls.sanity_ok:
            print(f"  {'':<26}[!! 單位可疑 !!] {ls.sanity_msg}")

    # TWII
    px, px_reason, px_diag = load_twii_ohlcv(cache_dir)
    if px is None:
        print(f"  {'^TWII 日 K':<26}{'點':<10}{'-':<12}{'-':<12}{0:>8}{'-':>8}  "
              f"[MISSING] {px_reason}")
    else:
        print(f"  {'^TWII 日 K':<26}{'點':<10}{str(px.index[0].date()):<12}"
              f"{str(px.index[-1].date()):<12}{len(px):>8}"
              f"{px_diag['n_close_na']:>8}  [OK] {px_reason}")
        print(f"  {'':<26}open 缺 {px_diag['n_open_na']} 筆"
              f"（進場價用 open，缺就整筆排除）"
              f"  sha256[:12] = {sha12(cache_dir / 'twii_ohlcv.parquet')}")
        print(f"  {'':<26}§4.2 不變量：date 遞增={px_diag['monotonic']} / "
              f"date 唯一={px_diag['unique']} / low>high 違反 "
              f"{px_diag['ohlc_violation_low_gt_high']} 筆 / "
              f"O,C 出界 {px_diag['ohlc_violation_oc_out_of_range']} 筆")

    # 缺漏率（相對 TWII 交易日曆）
    if px is not None:
        sub("缺漏率（以 ^TWII 交易日為分母）")
        for k, ls in loaded.items():
            if ls.series is None or ls.series.empty:
                continue
            lo = max(px.index[0], ls.series.index[0])
            hi = min(px.index[-1], ls.series.index[-1])
            cal = px.loc[lo:hi].index
            have = ls.series.index.intersection(cal)
            miss = len(cal) - len(have)
            print(f"  {ls.label:<26} 重疊期 {lo.date()} ~ {hi.date()}："
                  f"TWII {len(cal):,} 日 / 有值 {len(have):,} 日 / "
                  f"缺 {miss:,} 日（{fmt_pct(miss / len(cal) if len(cal) else float('nan'), 2)}）")

    return {"loaded": loaded, "px": px, "px_reason": px_reason,
            "futures_hits": futures_hits, "vix_hits": vix_hits, "cap_hits": cap_hits,
            "meta": meta}


# ═══════════════════════════════════════════════════════════════════════════
# 三環第一環：可行性判定（預期會失敗 -> Fail Loud）
# ═══════════════════════════════════════════════════════════════════════════
def step123_ring1(inv: dict, consts: dict[str, ConstSource]) -> bool:
    section("§1-3  三環第一環閘門（VIX < 20 AND 外資期貨 > -15000 口）",
            "這個閘門在歷史上有多常關著？換成滾動分位數會怎樣？它救到人了嗎？")

    print("  判定式（來源 src/services/allocation_service.py:194-207）：")
    print("      _cA 失敗  <=>  VIX  >= 20")
    print("      _cB 失敗  <=>  外資期貨淨口 <= -15000 口   (注意是 <=)")
    print("      任一失敗  =>   ring_gate_cap(False) -> 持股天花板 20%")
    print("                     [shared/allocation_decision.py:365-378]")
    print()
    print("  需要的兩條**日頻歷史序列**：")
    print("      (1) 外資期貨淨口 `外資大小`（TX 當量口）")
    print("      (2) VIX 日收盤")
    print()

    missing = []
    if not inv.get("futures_hits"):
        missing.append("外資期貨淨口日頻歷史（`外資大小`）")
    if not inv.get("vix_hits"):
        missing.append("VIX 日收盤歷史")

    if not missing:
        print("  [意外] 兩條序列都找到了 —— 但本腳本 v1 尚未實作它們的載入器，")
        print("         因為撰寫當下（2026-08-06）盤點結果是**兩條都不存在**。")
        print("         請把 §0 的 parquet 欄位掃描結果貼回來，我再補載入器。")
        return False

    print("  " + "#" * 74)
    print("  #  無法進行此分析")
    print("  #")
    for m in missing:
        print(f"  #  缺：{m}")
    print("  #")
    print("  #  為什麼缺（code 上的根因）：")
    print("  #   * scripts/update_macro_history.py:48-49 的 DATASETS 只有 5 張表 —")
    print("  #     twii_ohlcv / finmind_inst / finmind_margin / finmind_m1m2 / tw_pmi。")
    print("  #     **外資期貨與 VIX 都不在其中**，所以 cron 從來沒有落地過它們。")
    print("  #   * 外資期貨走的是 src/data/macro/leading_indicators.py:1196")
    print("  #     `build_leading_fast(days=7)` —— 每次現抓約一週，只寫一份")
    print("  #     `%TEMP%/stock_cache/*.pkl` 快照（shared/cache_layer.py:28），")
    print("  #     且 `_STALE_MAX_AGE_MIN = 4320`（3 個交易日，leading_indicators.py:1126）")
    print("  #     一到就丟棄。消費端全是 `.iloc[-1]`（allocation_service.py:141）。")
    print("  #   * VIX 每次都是即時抓 Yahoo（macro_core `fetch_yf_close('^VIX')`），")
    print("  #     只有記憶體 TTL 快取，沒有任何落地序列。")
    print("  #   * data_cache/finmind_inst.parquet 的 `foreign_buy` 是外資**現貨**")
    print("  #     淨買賣超（億元），**不是**期貨口數 —— 兩者不可互相替代。")
    print("  #")
    print("  #  §1 Fail Loud：本腳本**拒絕**用僅有的 7~14 天快取硬算關閉率、")
    print("  #  分位數或事件研究 —— 那會產出一份看起來有結論、實際是雜訊的報告。")
    print("  #")
    print("  #  要讓這節能跑，需要補的資料（擇一）：")
    print("  #   A. 在 scripts/update_macro_history.py 的 DATASETS 加兩張表並 --bootstrap：")
    print("  #      - foreign_futures_net：FinMind `TaiwanFuturesInstitutionalInvestors`")
    print("  #        （TX + MTX，需自行照 leading_indicators.py:390 的公式算 TX 當量：")
    print("  #         外資大小 = 外資大台淨口 + 0.25 x 外資小台淨口）")
    print("  #      - vix_daily：Yahoo chart API `^VIX` 或 FRED `VIXCLS`")
    print("  #      落地後歷史深度取決於上游 —— FinMind 期貨三大法人約 2007 起，")
    print("  #      VIXCLS 自 1990 起，兩者交集可望 >= 15 年。")
    print("  #   B. 若只想先看一眼，TAIFEX 官網有逐日「三大法人-區分各契約」CSV，")
    print("  #      但海外 IP 常被擋，且**下載＝抓網路**，不在本腳本職責內。")
    print("  #")
    print("  #  補完後重跑本腳本，§1/§2/§3 會自動有輸出。")
    print("  " + "#" * 74)
    return False


# ═══════════════════════════════════════════════════════════════════════════
# 一個閘門的完整三段分析（Step1 + Step2 + Step3）
# ═══════════════════════════════════════════════════════════════════════════
def analyze_gate(ls: LoadedSeries, spec: GateSpec, px: Optional["pd.DataFrame"],
                 args, extra_note: str = "") -> Optional["pd.Series"]:
    if ls.series is None or ls.series.empty:
        print(f"  [MISSING] {ls.label} 無法載入：{ls.reason}")
        print(f"            -> 本節跳過（§1：不用其他序列頂替）")
        return None
    s = ls.series
    if args.start:
        s = s[s.index >= pd.Timestamp(args.start)]
    if args.end:
        s = s[s.index <= pd.Timestamp(args.end)]
    if s.empty:
        print("  [MISSING] 套用 --start/--end 之後序列為空。")
        return None

    print(f"  序列來源：{ls.source_file}")
    print(f"  單位轉換：{ls.formula}   （單位 = {ls.unit}）")
    if extra_note:
        print(f"  {extra_note}")
    if not ls.sanity_ok:
        print(f"  [!! 單位可疑 !!] {ls.sanity_msg}")
    print(f"  觸發後果：{spec.consequence}")
    print()

    sub("Step 1 — 閘門關閉率")
    mask = gate_mask(s, spec)
    report_closure(mask, spec, s, args.all_quarters)

    sub("Step 2 — 替代門檻（滾動分位數）的觸發頻率")
    report_alternative_thresholds(s, spec, args.pct_window, args.pct_levels)

    sub("Step 3 — 事件研究：閘門關閉之後，大盤實際怎麼走")
    if px is None:
        print("  [MISSING] ^TWII 日 K 不可用 -> 無法做事件研究。")
    else:
        report_event_study(mask, px, spec, args.horizons, args.min_episodes)
    return mask


# ═══════════════════════════════════════════════════════════════════════════
# 融資餘額的「相對化」版本
# ═══════════════════════════════════════════════════════════════════════════
def report_margin_relative(inv: dict) -> list[str]:
    """融資 / 上市總市值 —— 說明為何算不出。回傳「資料限制」條目。"""
    sub("融資 / 上市總市值（相對化版本）")
    limits: list[str] = []
    if inv.get("cap_hits"):
        print(f"  [意外] 找到疑似市值欄位：{inv['cap_hits']}")
        print("         但本腳本 v1 未實作其載入器（撰寫當下盤點結果是「不存在」）。")
        limits.append("融資/市值比：偵測到疑似市值欄位但未實作載入器，未計算。")
        return limits

    print("  [無法計算] 本機沒有任何『上市總市值』日頻或月頻序列。")
    print()
    print("  證據：")
    print("   * data_cache/ 全 parquet 欄位掃描（見 §0）無 market_cap / 市值 欄。")
    print("   * shared/relative_thresholds.py:180 `margin_leverage_ratio(margin_yi,")
    print("     market_cap_yi)` 這個 helper **沒有任何 caller**，也沒有任何 fetcher")
    print("     供應 `market_cap_yi` —— 它是寫好但從未接線的死碼。")
    print("   * TWSE MI_INDEX 在本專案只被用來取漲跌家數與成交量")
    print("     （tw_macro.py / leading_indicators.py），從未取市值。")
    print()
    print("  §1：**不用替代分母硬湊**。特別是「融資 / TWII 指數點位」看起來很像，")
    print("      但指數是價格指數（不含新上市增量、成分股權重變動），")
    print("      與『上市總市值』是不同的量，拿它當分母會製造一個看起來合理的假數字。")
    print()
    print("  要讓這節能跑，需要補：一條上市總市值日序列")
    print("      （TWSE OpenAPI 有每日總市值；或 FinMind 個股市值逐日加總 —— 後者很貴）")
    print("      加進 scripts/update_macro_history.py 的 DATASETS 並 --bootstrap。")
    print()
    print("  替代做法（本腳本已做）：§2 的滾動分位數版本不需要外部分母，")
    print("      它讓門檻自己跟著歷史水位長大，可直接看『觸發頻率是否回到合理區間』。")
    limits.append("融資/上市總市值比：**未計算** —— 本機無總市值序列，"
                  "且拒絕用指數點位當替代分母（§1）。改以 §2 滾動分位數版本替代。")
    return limits


# ═══════════════════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════════════════
def parse_args(argv: Optional[Sequence[str]] = None):
    p = argparse.ArgumentParser(
        description="量測絕對門檻閘門的歷史關閉率 / 替代門檻 / 事件研究（純唯讀、不抓網路）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cache-dir", default=str(_REPO_ROOT / "data_cache"),
                   help="parquet 目錄（預設 <repo>/data_cache）")
    p.add_argument("--out-dir", default=str(_REPO_ROOT / "scripts" / "_out"),
                   help="輸出目錄（只在 --write-csv 時建立）")
    p.add_argument("--write-csv", action="store_true",
                   help="把逐日明細寫成 CSV 到 --out-dir（預設不寫任何檔）")
    p.add_argument("--pct-window", type=int, default=756,
                   help="滾動分位數視窗，交易日（預設 756 ≈ 3 年）")
    p.add_argument("--pct-levels", default="0.90,0.85,0.80",
                   help="替代門檻分位，逗號分隔（預設 0.90,0.85,0.80）")
    p.add_argument("--horizons", default="21,63,126",
                   help="事件研究持有期，交易日，逗號分隔（預設 21,63,126 ≈ 1/3/6 個月）")
    p.add_argument("--min-episodes", type=int, default=10,
                   help="獨立事件數低於此值即標「樣本不足」（預設 10）")
    p.add_argument("--start", default=None, help="起日 YYYY-MM-DD")
    p.add_argument("--end", default=None, help="訖日 YYYY-MM-DD")
    p.add_argument("--all-quarters", action="store_true", help="印出全部逐季表")
    p.add_argument("--inspect-pickle", action="store_true",
                   help="掃描 %%TEMP%%/stock_cache 的先行指標 pickle（會 unpickle）")
    p.add_argument("--skip-foreign-spot", action="store_true",
                   help="跳過『外資現貨 5 日累積』那節（它是另一個閘門，非三環第一環）")
    a = p.parse_args(argv)
    a.pct_levels = [float(x) for x in str(a.pct_levels).split(",") if x.strip()]
    a.horizons = [int(x) for x in str(a.horizons).split(",") if x.strip()]
    return a


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    cache_dir = Path(args.cache_dir)

    now_utc = _dt.datetime.now(_dt.timezone.utc)
    now_tw = now_utc.astimezone(_dt.timezone(_dt.timedelta(hours=8)))

    print(hr("="))
    print("  三環第一環 / 絕對門檻閘門 —— 歷史量測報告")
    print(hr("="))
    print(f"  腳本版本   : {SCRIPT_VERSION}")
    print(f"  !! 本腳本的作者從未執行過它 —— 所有輸出都請以你這次的實跑為準 !!")
    print(f"  執行時間   : {now_utc.isoformat(timespec='seconds')} (UTC)"
          f" / {now_tw.isoformat(timespec='seconds')} (TW UTC+8)")
    print(f"  Python     : {sys.version.split()[0]}   pandas {pd.__version__}"
          f"   numpy {np.__version__}")
    print(f"  repo root  : {_REPO_ROOT}")
    print(f"  CLI 參數   : {' '.join(sys.argv[1:]) or '(全部使用預設值)'}")
    print(f"  唯讀保證   : 除 --write-csv 外不寫任何檔；絕不碰 data_cache/ 與"
          f" macro_thresholds.json")
    print(f"  離線保證   : 不 import requests / yfinance / FinMind，不呼叫任何 fetcher")

    consts = load_constants()
    sub("門檻常數與其來源（§3.3 反捏造：每個數字都要能指回 SSOT）")
    for c in consts.values():
        print(c.line())

    # ── Step 0 ────────────────────────────────────────────────────────────
    inv = step0_inventory(cache_dir, args)
    if not inv:
        print("\n[FATAL] 資料盤點失敗，終止。")
        return 1
    px = inv.get("px")
    loaded: dict[str, LoadedSeries] = inv.get("loaded", {})

    limitations: list[str] = []

    # ── Step 1-3：三環第一環（預期缺資料）────────────────────────────────
    ring1_ok = step123_ring1(inv, consts)
    if not ring1_ok:
        limitations.append(
            "三環第一環（VIX + 外資期貨）的關閉率 / 替代門檻 / 事件研究："
            "**完全未執行** —— 本機沒有外資期貨淨口與 VIX 的歷史序列，"
            "只有 <= 7 天的即時快取（且 3 天過期）。"
            "這是本次的主要問題，目前無法用資料回答。")

    # ── Step 4：融資餘額（同款檢查，資料齊全）────────────────────────────
    section("§4  融資餘額閘門（>= 3,400 億 亮紅）",
            "同一個假說：絕對門檻是不是也已經被市值成長淹沒、變成永遠亮紅？")
    margin_spec = GateSpec(
        key="margin",
        label="融資餘額",
        unit="億 TWD",
        threshold=consts["MARGIN_RED_YI"].value,
        direction="above",
        threshold_citation=consts["MARGIN_RED_YI"].citation,
        publish_lag="TWSE 盤後約 14:30 TW 公布，故 T 日訊號最早 T+1 開盤可執行",
        consequence="shared/macro_buckets.py:268-275 `margin` DangerSpec -> 籌碼桶亮紅；"
                    "註解自承『絕對門檻已被市值成長淹沒、鑑別力歸零』",
    )
    margin_mask = analyze_gate(
        loaded.get("margin_yi", LoadedSeries("margin_yi", "融資餘額", "億", None,
                                             "-", "-", "loader 未回傳")),
        margin_spec, px, args,
        extra_note=(f"黃線 {consts['MARGIN_YELLOW_YI'].value:,.0f} 億 "
                    f"[{consts['MARGIN_YELLOW_YI'].citation}]（本節只量紅線）"))
    limitations.extend(report_margin_relative(inv))

    # ── 附錄：外資現貨 5 日累積（另一個絕對門檻閘門）──────────────────────
    fs_mask = None
    if not args.skip_foreign_spot:
        section("§5（附錄）外資現貨 5 日累積買賣超閘門（<= -500 億）",
                "同一個假說套到第三個絕對門檻：它的觸發頻率是不是也失控了？")
        print("  " + "!" * 74)
        print("  ! 這是**另一個**閘門，**不是**三環第一環的替代品或代理變數。")
        print("  ! 現貨淨買賣超（億元）與期貨淨口（TX 當量口）是不同的量、不同的契約、")
        print("  ! 不同的量綱，兩者不可互推。放在這裡只是因為它是第三個有歷史可查的")
        print("  ! 絕對門檻，可用來佐證『絕對門檻會被規模成長淹沒』這個一般性假說。")
        print("  " + "!" * 74)
        print()
        fs_spec = GateSpec(
            key="foreign_spot_5d",
            label="外資現貨 5 日累積買賣超",
            unit="億 TWD",
            threshold=consts["FOREIGN_5D_YI"].value,
            direction="below",
            threshold_citation=consts["FOREIGN_5D_YI"].citation,
            publish_lag="TWSE 盤後約 14:30 TW 公布，故 T 日訊號最早 T+1 開盤可執行",
            consequence="src/compute/macro/macro_signal_lookback_tw.py:297-304 "
                        "DEFAULT_TW_SIGNALS 的警戒訊號之一",
        )
        fs_mask = analyze_gate(
            loaded.get("foreign_spot_5d_yi",
                       LoadedSeries("foreign_spot_5d_yi", "外資現貨 5 日累積", "億",
                                    None, "-", "-", "loader 未回傳")),
            fs_spec, px, args)

    # ── 佔比版本（量綱陷阱說明）──────────────────────────────────────────
    section("§6  為什麼沒有『佔比』版本",
            "為什麼不算『外資淨口 / 全市場未平倉』？")
    print("  §4.1 量綱陷阱（v19.172 已查證，STATE.md:596）：")
    print("   * 分子 `外資大小` = 外資大台淨口 + 0.25 x 外資小台淨口 = **TX 當量口**")
    print("     [src/data/macro/leading_indicators.py:262,390]")
    print("   * 分母 `未平倉口數` = `taifex_mtx_oi.get(d) or _lt.get('未平倉')`")
    print("     = **MTX 原始口，或 TX 口，逐列可能不同源**")
    print("     [src/data/macro/leading_indicators.py:1390 附近]")
    print("   * 實測 |-87,626| vs 39,503 —— 分子絕對值大於分母，物理上不可能；")
    print("     若後者是 MTX 原始口，其 TX 當量僅約 9,876 -> **差 8.9 倍**。")
    print("     這是量綱錯誤，不是誤差。")
    print("   * 專案後來另開 `OI_TX當量` 欄（= OI_TX + 0.25 x OI_MTX）作為唯一")
    print("     可與『外資大小』相除的分母 [leading_indicators.py:1616]，")
    print("     但**它同樣沒有歷史落地**（見 §0 掃描）。")
    print()
    print("  結論：**佔比版因分母契約別不符（且無歷史）而未計算**。")
    print("        本報告只做分位數版本（§2），它不需要外部分母，量綱天然自洽。")
    limitations.append(
        "外資期貨『佔全市場 OI 比例』版本：**未計算** —— "
        "分子是 TX 當量口、分母是 MTX 原始口，差約 8.9 倍（STATE.md:596），"
        "且兩者都無歷史落地。")

    # ── CSV（唯一的寫檔路徑）──────────────────────────────────────────────
    if args.write_csv:
        out_dir = Path(args.out_dir)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            stamp = now_tw.strftime("%Y%m%d_%H%M%S")
            written = []
            for name, m in (("margin_gate", margin_mask), ("foreign_spot_gate", fs_mask)):
                if m is None:
                    continue
                fp = out_dir / f"{name}_{stamp}.csv"
                m.rename("gate_closed").to_frame().to_csv(fp, encoding="utf-8-sig")
                written.append(str(fp))
            sub("CSV 輸出")
            for w in written:
                print(f"  已寫入 {w}")
            if not written:
                print("  （沒有可輸出的序列）")
        except Exception as e:  # noqa: BLE001
            print(f"  [WARN] CSV 寫入失敗（不影響上方結論）：{type(e).__name__}: {e}")

    # ── 資料限制（誠實收尾）────────────────────────────────────────────────
    section("§7  資料限制 —— 哪些分析沒跑成、哪些結論不能信",
            "這份報告的邊界在哪裡？")
    if not limitations:
        print("  （無）")
    for i, l in enumerate(limitations, 1):
        print(f"  {i}. {l}")
    print()
    print("  通用限制（一律適用）：")
    print("   a. **重疊樣本**：逐日觸發統計的持有視窗互相重疊，不是獨立觀測。")
    print("      請只用「事件（每段第一天）」那組數字，且本報告未做顯著性檢定。")
    print("   b. **右側截斷**：最近的觸發日還沒過完最長持有期，已被排除；")
    print("      被排除的筆數印在各表下方。這會讓樣本偏向較早的年份。")
    print("   c. **相關 != 因果**：即使觸發組後續報酬較差，也不代表這個閘門")
    print("      『有預測力』—— 它可能只是與另一個真正的驅動因子共動。")
    print("   d. **本腳本不做參數決策**：以上全是量測，門檻要不要改由你決定。")
    print("      改門檻屬行為變更，需獨立驗證（CLAUDE.md §8.1 / shared/relative_thresholds")
    print("      模組頭部亦有同樣聲明）。")
    print("   e. **作者未曾執行本腳本**：若有數字看起來不合理，先懷疑腳本，")
    print("      把輸出貼回來對帳。")
    print()
    print(hr("="))
    print("  報告結束。")
    print(hr("="))
    return 0 if ring1_ok else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as _e:  # noqa: BLE001 — §1：不吞例外，完整 traceback 給 user
        import traceback
        traceback.print_exc()
        print(f"\n[FATAL] 未預期例外：{type(_e).__name__}: {_e}")
        print("        （作者從未執行過本腳本 —— 請把上面整段 traceback 貼回來）")
        raise SystemExit(1)
