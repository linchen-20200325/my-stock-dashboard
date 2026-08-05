"""src/compute/health/fin_snapshot_io.py — v18.186 財報體檢快照持久化層

（v19.174 去識別化：本檔自 `mj_snapshot_io.py` 改名而來，文字敘述移除人名／稱謂。
快照目錄同步 `data_cache/mj_snapshots` → `data_cache/fin_health_snapshots`；
舊目錄保留為**唯讀**相容來源，避免既有本機快照失聯。函式介面 0 改。）

把 `financial_health_engine.analyze_financial_health` 的 JSON 結果落地
到 `data_cache/fin_health_snapshots/{sid}_{yyyymm}.json`，供 v18.185
`fin_health_diff` 跨期比對使用，避免每次 session 重打 LLM 燒錢。

設計：
  • atomic write（先寫 .tmp 再 os.replace）防中途斷電壞檔
  • 檔名 `{sid}_{yyyymm}.json`：season anchor 用 YYYYMM（季底月份）
  • list_snapshots(sid) 回所有可用 yyyymm 降序
  • load_latest_two(sid) → (prev_dict, curr_dict) 給 fin_health_diff 直用
  • 純 stdlib zero-dep
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

_DEFAULT_DIR = Path("data_cache/fin_health_snapshots")
# v19.174 去識別化改名前的舊目錄。**唯讀**相容（只讀不寫、不搬檔），
# 讓改名前已落地的本機快照不至於失聯導致季分數歸零。
# 全部快照自然汰換（約 2 季）後可刪除本常數與 `_read_dirs` 的第二個候選。
_LEGACY_DIR = Path("data_cache/mj_snapshots")
_FILE_RE = re.compile(r"^([A-Za-z0-9\.\-]+)_(\d{6})\.json$")


def _ensure_dir(base: Path | None = None) -> Path:
    """回寫入用目錄（必要時建立）。"""
    d = Path(base) if base else _DEFAULT_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_dirs(base: Path | None = None) -> tuple[Path, ...]:
    """回讀取候選目錄（依優先序）。

    v19.174：base_dir 顯式指定時只用它（保 pytest tmp_path 物理隔離，
    §3.3「測試資料不可流入正式路徑」）；走預設路徑時才額外掛舊目錄唯讀相容。
    """
    if base:
        return (Path(base),)
    return (_DEFAULT_DIR, _LEGACY_DIR)


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
    fh_result: Any,
    base_dir: Path | None = None,
) -> Path | None:
    """落地單股單期財報體檢 JSON。

    Returns:
        Path of written file on success, None on validation failure.
    """
    _sid = _sanitize_sid(sid)
    _ym = _sanitize_yyyymm(yyyymm)
    if not _sid or not _ym:
        return None
    if not isinstance(fh_result, dict):
        return None
    d = _ensure_dir(base_dir)
    fp = d / f"{_sid}_{_ym}.json"
    tmp = fp.with_suffix(".json.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(fh_result, f, ensure_ascii=False, indent=2)
        os.replace(tmp, fp)
        return fp
    except OSError as e:
        print(f"[fin_snapshot_io] save {_sid}_{_ym} 失敗: {type(e).__name__}: {e}")
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                # 真失敗已在上一行 log；.tmp 殘檔清不掉屬非致命（下次 save 會覆寫），
                # 不再二次 log 以免同一次失敗噪音重複（§3.3：非靜默吞例外）
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
    for d in _read_dirs(base_dir):
        fp = d / f"{_sid}_{_ym}.json"
        if not fp.exists():
            continue
        try:
            with fp.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            return None
        except (OSError, json.JSONDecodeError) as e:
            print(f"[fin_snapshot_io] load {fp.name} 失敗: {type(e).__name__}: {e}")
            return None
    return None


def list_snapshots(
    sid: Any,
    base_dir: Path | None = None,
) -> list[str]:
    """列出單股所有可用快照 yyyymm，降序（最新在前）。"""
    _sid = _sanitize_sid(sid)
    if not _sid:
        return []
    out: set[str] = set()
    for d in _read_dirs(base_dir):
        if not d.exists():
            continue
        for p in d.iterdir():
            if not p.is_file():
                continue
            m = _FILE_RE.match(p.name)
            if not m:
                continue
            if m.group(1) != _sid:
                continue
            out.add(m.group(2))
    return sorted(out, reverse=True)


def load_latest_two(
    sid: Any,
    base_dir: Path | None = None,
) -> tuple[dict | None, dict | None, str | None, str | None]:
    """取單股最近 2 季快照供 diff_fin_health 直用。

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
    """掃快照目錄列出所有有快照的 stock_id（去重，升序）。"""
    sids: set[str] = set()
    for d in _read_dirs(base_dir):
        if not d.exists():
            continue
        for p in d.iterdir():
            if not p.is_file():
                continue
            m = _FILE_RE.match(p.name)
            if m:
                sids.add(m.group(1))
    return sorted(sids)


def current_finmind_yyyymm(today: date | None = None) -> str:
    """依今日推算最近已公布完成季的 yyyymm（季底月份）。

    台股財報公告截止：Q1=5/15、Q2=8/14、Q3=11/14、Q4=隔年3/31。

      1-3 月  → 去年 Q3 (yyyy-1)09
      4-5 月  → 去年 Q4 (yyyy-1)12
      6-8 月  → 今年 Q1 yyyy03
      9-11 月 → 今年 Q2 yyyy06
      12 月   → 今年 Q3 yyyy09
    """
    t = today or date.today()
    y, m = t.year, t.month
    if 1 <= m <= 3:
        return f"{y - 1}09"
    if 4 <= m <= 5:
        return f"{y - 1}12"
    if 6 <= m <= 8:
        return f"{y}03"
    if 9 <= m <= 11:
        return f"{y}06"
    return f"{y}09"
