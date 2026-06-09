"""mj_snapshot_io.py — v18.186 MJ 體檢快照持久化層

把 `financial_health_engine.analyze_financial_health` 的 JSON 結果落地
到 `data_cache/mj_snapshots/{sid}_{yyyymm}.json`，供 v18.185
`mj_health_diff` 跨期比對使用，避免每次 session 重打 LLM 燒錢。

設計：
  • atomic write（先寫 .tmp 再 os.replace）防中途斷電壞檔
  • 檔名 `{sid}_{yyyymm}.json`：season anchor 用 YYYYMM（季底月份）
  • list_snapshots(sid) 回所有可用 yyyymm 降序
  • load_latest_two(sid) → (prev_dict, curr_dict) 給 mj_health_diff 直用
  • 純 stdlib zero-dep
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

_DEFAULT_DIR = Path("data_cache/mj_snapshots")
_FILE_RE = re.compile(r"^([A-Za-z0-9\.\-]+)_(\d{6})\.json$")


def _ensure_dir(base: Path | None = None) -> Path:
    d = Path(base) if base else _DEFAULT_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sanitize_sid(sid: Any) -> str:
    """股票代碼防呆 — 只留英數 / . / -，其他剝除避免路徑注入。"""
    s = str(sid or "").strip()
    return re.sub(r"[^A-Za-z0-9\.\-]", "", s)


def _sanitize_yyyymm(yyyymm: Any) -> str:
    """季底月份必須 6 碼數字。"""
    s = str(yyyymm or "").strip()
    return s if re.fullmatch(r"\d{6}", s) else ""


def save_snapshot(
    sid: Any,
    yyyymm: Any,
    mj_result: Any,
    base_dir: Path | None = None,
) -> Path | None:
    """落地單股單期 MJ 體檢 JSON。

    Returns:
        Path of written file on success, None on validation failure.
    """
    _sid = _sanitize_sid(sid)
    _ym = _sanitize_yyyymm(yyyymm)
    if not _sid or not _ym:
        return None
    if not isinstance(mj_result, dict):
        return None
    d = _ensure_dir(base_dir)
    fp = d / f"{_sid}_{_ym}.json"
    tmp = fp.with_suffix(".json.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(mj_result, f, ensure_ascii=False, indent=2)
        os.replace(tmp, fp)
        return fp
    except OSError as e:
        print(f"[mj_snapshot_io] save {_sid}_{_ym} 失敗: {type(e).__name__}: {e}")
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        return None


def load_snapshot(
    sid: Any,
    yyyymm: Any,
    base_dir: Path | None = None,
) -> dict | None:
    """讀回單股單期快照；缺檔/壞 JSON → None。"""
    _sid = _sanitize_sid(sid)
    _ym = _sanitize_yyyymm(yyyymm)
    if not _sid or not _ym:
        return None
    d = _ensure_dir(base_dir)
    fp = d / f"{_sid}_{_ym}.json"
    if not fp.exists():
        return None
    try:
        with fp.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError) as e:
        print(f"[mj_snapshot_io] load {fp.name} 失敗: {type(e).__name__}: {e}")
        return None


def list_snapshots(
    sid: Any,
    base_dir: Path | None = None,
) -> list[str]:
    """列出單股所有可用快照 yyyymm，降序（最新在前）。"""
    _sid = _sanitize_sid(sid)
    if not _sid:
        return []
    d = _ensure_dir(base_dir)
    if not d.exists():
        return []
    out: list[str] = []
    for p in d.iterdir():
        if not p.is_file():
            continue
        m = _FILE_RE.match(p.name)
        if not m:
            continue
        if m.group(1) != _sid:
            continue
        out.append(m.group(2))
    return sorted(out, reverse=True)


def load_latest_two(
    sid: Any,
    base_dir: Path | None = None,
) -> tuple[dict | None, dict | None, str | None, str | None]:
    """取單股最近 2 季快照供 diff_mj_health 直用。

    Returns:
        (prev_dict, curr_dict, prev_yyyymm, curr_yyyymm)
        — 若不足 2 季，缺的位回 None
    """
    yms = list_snapshots(sid, base_dir=base_dir)
    if not yms:
        return None, None, None, None
    curr_ym = yms[0]
    curr = load_snapshot(sid, curr_ym, base_dir=base_dir)
    if len(yms) < 2:
        return None, curr, None, curr_ym
    prev_ym = yms[1]
    prev = load_snapshot(sid, prev_ym, base_dir=base_dir)
    return prev, curr, prev_ym, curr_ym


def list_all_stocks_with_snapshots(
    base_dir: Path | None = None,
) -> list[str]:
    """掃 base_dir 列出所有有快照的 stock_id（去重，升序）。"""
    d = _ensure_dir(base_dir)
    if not d.exists():
        return []
    sids: set[str] = set()
    for p in d.iterdir():
        if not p.is_file():
            continue
        m = _FILE_RE.match(p.name)
        if m:
            sids.add(m.group(1))
    return sorted(sids)
