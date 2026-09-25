"""src/compute/macro/lamp_direction.py — 燈卡「變化方向」列的 L2 純函式（2026-09-24）。

輸入一條 `[(iso_date, value), ...]` 序列，算出「現在比 N 列之前高 / 低 / 差不多」。
常數（視窗、持平帶、文字）全部來自 L0 `shared/lamp_direction_thresholds.py`，
本檔不寫任何門檻數字（§3.3）。

§8.2 L2：純函式 —— 零 I/O、不 import streamlit / requests / proxy / L1。

§1 Fail Loud / Never Fake：
- ⛔ 不 fillna / ffill / 內插。點數不足、端點非有限數、舊值 ≤ 0（算百分比會
  除以零或變號）、日期重複或無法解析、月資料中間缺月 → 一律 `nodata`，
  並在 `reason` 寫明原因（畫面只顯示「無資料」，不編一個箭頭）。
- 未知 key → `KeyError`（不猜一個視窗）。
- **計算本身失敗**（L3 / L2 丟例外）→ caller 用 `error_direction()` 做出
  `direction == "error"`，畫面顯示「計算失敗（例外型別）」—— ⛔ 不整列消失、
  ⛔ 不冒充「無資料」（2026-09-25）。

⚠️ 本檔的輸出**不是燈號**：不參與 `classify_danger()`、不改燈色 / 等級。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from shared.lamp_direction_thresholds import (
    DIRECTION_MODE_DIFF,
    DIRECTION_MODE_NONE,
    DIRECTION_MODE_PCT,
    LAMP_DIRECTION_DECIMALS,
    LAMP_DIRECTION_ERROR_TEMPLATE,
    LAMP_DIRECTION_ERROR_TEXT,
    LAMP_DIRECTION_FLAT_BAND,
    LAMP_DIRECTION_LABELS,
    LAMP_DIRECTION_NODATA_TEXT,
    LAMP_DIRECTION_WINDOWS,
)

DIRECTION_UP = "up"
DIRECTION_FLAT = "flat"
DIRECTION_DOWN = "down"
DIRECTION_NODATA = "nodata"
DIRECTION_ERROR = "error"
DIRECTIONS: tuple[str, ...] = (DIRECTION_UP, DIRECTION_FLAT, DIRECTION_DOWN,
                               DIRECTION_NODATA, DIRECTION_ERROR)


@dataclass(frozen=True)
class LampDirection:
    """一盞燈的變化方向。`direction in ("nodata", "error")` 時 `delta` / `as_of` 為 None。"""

    direction: str                 # 'up' | 'flat' | 'down' | 'nodata' | 'error'
    delta: Optional[float]         # 變化量（單位見 unit）
    unit: str                      # 變化量單位（'%' / ' 個百分點' / ' 點' / ''）
    window_text: str               # '近 20 交易日' / '較上月' / ''
    as_of: Optional[str]           # 最新一點的日期（ISO）
    reason: str = ""               # nodata：原因（給 log，畫面不顯示）；
                                   # error：簡短原因（例外型別名），畫面會顯示

    def __post_init__(self) -> None:
        if self.direction not in DIRECTIONS:
            raise ValueError(f"direction 必須是 {DIRECTIONS}，收到 {self.direction!r}")


def _nodata(cfg: dict, reason: str) -> LampDirection:
    return LampDirection(direction=DIRECTION_NODATA, delta=None,
                         unit=str(cfg["unit"]), window_text=str(cfg["window_text"]),
                         as_of=None, reason=reason)


def error_direction(key: str, reason: str) -> LampDirection:
    """方向**計算失敗**（取數 / 計算丟例外、或結果沒回傳）→ `direction == "error"`。

    `reason` 只放簡短原因（例外型別名，如 ``"RuntimeError"``）—— 它會上畫面，
    ⛔ 不放 stack trace / 例外訊息全文。未知 key → `KeyError`（同 compute）。
    """
    cfg = LAMP_DIRECTION_WINDOWS[key]
    return LampDirection(direction=DIRECTION_ERROR, delta=None,
                         unit=str(cfg["unit"]), window_text=str(cfg["window_text"]),
                         as_of=None, reason=str(reason))


def _parse_iso(d: object) -> Optional[date]:
    try:
        return date.fromisoformat(str(d)[:10])
    except (TypeError, ValueError):
        return None


def compute_lamp_direction(
    key: str,
    points: Optional[Sequence[tuple[str, float]]],
) -> LampDirection:
    """算一盞燈的變化方向。

    Args:
        key: `DangerSpec.key`，必須在 `LAMP_DIRECTION_WINDOWS` 內，否則 `KeyError`。
        points: `[(iso_date, value), ...]`；預期日期遞增，本函式仍會防禦性排序。
            每一列 = 一個觀測（交易日序列一列一個交易日；月序列一列一個月）。

    判定：
        n = lookback_rows；需要至少 n + 1 點。
        pct  : delta = (新 / 舊 − 1) × 100；舊 ≤ 0 → nodata
        diff : delta = 新 − 舊
        |delta| ≤ 持平帶（含等於，浮點以 math.isclose 容差）→ flat；> 0 → up；< 0 → down
    """
    cfg = LAMP_DIRECTION_WINDOWS[key]          # 未知 key → KeyError（刻意）
    mode = cfg["mode"]
    if mode == DIRECTION_MODE_NONE:
        return _nodata(cfg, f"{key}：歷史資料已知不可信，刻意不算方向")
    if mode not in (DIRECTION_MODE_PCT, DIRECTION_MODE_DIFF):
        raise ValueError(f"{key}：未知的 mode {mode!r}")
    band = LAMP_DIRECTION_FLAT_BAND[key]       # 有算方向的 key 一定要有帶寬
    n = int(cfg["lookback_rows"])
    if n < 1:
        raise ValueError(f"{key}：lookback_rows 必須 ≥ 1，收到 {n}")

    if not points:
        return _nodata(cfg, "沒有歷史序列")
    try:
        rows = [(str(d), v) for d, v in points]
    except (TypeError, ValueError):
        return _nodata(cfg, "序列格式不是 (日期, 值)")
    rows.sort(key=lambda r: r[0])
    dates = [r[0] for r in rows]
    if len(set(dates)) != len(dates):
        return _nodata(cfg, "序列內有重複日期")
    if len(rows) < n + 1:
        return _nodata(cfg, f"只有 {len(rows)} 點，需要至少 {n + 1} 點")

    (d_old, v_old), (d_new, v_new) = rows[-(n + 1)], rows[-1]
    try:
        v_old, v_new = float(v_old), float(v_new)
    except (TypeError, ValueError):
        return _nodata(cfg, "端點不是數值")
    if not (math.isfinite(v_old) and math.isfinite(v_new)):
        return _nodata(cfg, "端點為 NaN / inf")

    if cfg.get("monthly"):
        p_old, p_new = _parse_iso(d_old), _parse_iso(d_new)
        if p_old is None or p_new is None:
            return _nodata(cfg, "月份無法解析")
        gap = (p_new.year - p_old.year) * 12 + (p_new.month - p_old.month)
        if gap != n:
            return _nodata(cfg, f"比較的兩點相隔 {gap} 個月，不是 {n} 個月（中間缺月）")

    if mode == DIRECTION_MODE_PCT:
        if v_old <= 0:
            return _nodata(cfg, f"舊值 {v_old} ≤ 0，百分比變化無意義")
        delta = (v_new / v_old - 1.0) * 100.0
    else:
        delta = v_new - v_old
    if not math.isfinite(delta):
        return _nodata(cfg, "變化量非有限數")

    # 方向判在**顯示用的同一個四捨五入值**上 —— 否則 +0.51 會顯示成
    # 「↗ 上升（+0.5 點）」而 +0.50 顯示成「→ 持平（+0.5 點）」，數字與箭頭互相打臉。
    shown = round(delta, LAMP_DIRECTION_DECIMALS)
    if abs(shown) <= band or math.isclose(abs(shown), band, rel_tol=1e-9, abs_tol=1e-12):
        direction = DIRECTION_FLAT
    elif shown > 0:
        direction = DIRECTION_UP
    else:
        direction = DIRECTION_DOWN
    return LampDirection(direction=direction, delta=delta, unit=str(cfg["unit"]),
                         window_text=str(cfg["window_text"]),
                         as_of=str(d_new)[:10], reason="")


def format_direction_text(d: LampDirection) -> str:
    """LampDirection → 卡面文字。

    例：``↗ 上升（近 20 交易日 +9.9%，至 2026-09-24）``；
    ``→ 持平（較上月 +0.3 點，至 2026-08-01）``；無資料 → ``無資料``（⛔ 無箭頭）；
    計算失敗 → ``計算失敗（RuntimeError）``（⛔ 無箭頭；無原因 → ``計算失敗``）。
    """
    if d.direction == DIRECTION_ERROR:
        return (LAMP_DIRECTION_ERROR_TEMPLATE.format(reason=d.reason) if d.reason
                else LAMP_DIRECTION_ERROR_TEXT)
    if d.direction == DIRECTION_NODATA or d.delta is None:
        return LAMP_DIRECTION_NODATA_TEXT
    arrow, zh = LAMP_DIRECTION_LABELS[d.direction]
    shown = round(d.delta, LAMP_DIRECTION_DECIMALS)
    if shown == 0:
        shown = 0.0                            # 避免 "-0.0"
    delta_txt = f"{shown:+.{LAMP_DIRECTION_DECIMALS}f}{d.unit}"
    return f"{arrow} {zh}（{d.window_text} {delta_txt}，至 {d.as_of}）"
