#!/usr/bin/env python3
"""scripts/publish_data_pr.py — cron 資料以「獨立分支 + PR」發布（取代裸 `git push` main）。

為什麼有這支
------------
main 受 branch protection（required check `ui2-browser-gate`）保護，三支每日 cron
（update_macro_history / update_sector_flow / update_macro_forward_test）直接 `git push`
被 GH006 擋下。本 helper 的路線：

    cron 產出資料 → 判斷「實質變更」→ 推 `auto/data-<job>` 分支 → 以 GITHUB_TOKEN 開/更新 PR
    → 合併由人工（本批不啟用 auto-merge）

⚠️ 本 helper **不** dispatch 任何 workflow（`workflow_dispatch` 產生的 checks 不符合 PR 的
required status checks；已移除 `gh workflow run`，`_guard` 亦禁止 `gh workflow`）。
GITHUB_TOKEN 的 push／PR 事件通常不會觸發 pull_request workflow ⇒ required check
`ui2-browser-gate` 需由有權限者以原生 pull_request 事件觸發（Close→Reopen、Update branch 等；
實際行為以 GitHub 為準，**沙箱無法驗證 → NOT VERIFIED**）。PR body 明文寫出此限制與「未見綠燈
且 head SHA 相符前不得合併」，每次 push 新 head 會更新 body 中的「最新 head SHA」行
（不留言、不洗版）。

硬約束（`_guard` 以程式碼強制，測試以 runner 呼叫記錄斷言）：
不 push main、不帶 --force / --force-with-lease / `+refspec`、不 rebase、不改 GitHub 設定、不碰 workflow。

實質變更判定（§1：不得因過濾而丟掉實質資料）
--------------------------------------------
只決定「要不要發 PR」；一旦要發，commit 的是腳本輸出的**完整**檔案（含揮發欄位的新值）。
- JSON：忽略 `VOLATILE_JSON_KEYS` 列的揮發鍵後比較；未知鍵一律視為實質。
  依據（2026-11-06 讀 origin/main 343f0e0e 實檔）：
    data_cache/metadata.json                    updated_at（頂層；每次執行必變）
    data_cache/sector_flow/metadata.json        updated_at（頂層）
    data_cache/sector_flow/bubble_latest.json   updated_at（頂層）
    data_cache/sector_flow/industry_raw.json    fetched_at（頂層）
    data_cache/macro_last_good/tw_pmi.json      cached_at（頂層；macro_core._macro_durable_save 每次蓋 now()）、fetched_at
  其餘鍵（last_error / last_updated / row_count / per_day / warnings …）全是實質，
  特別是 `last_error` 變化代表來源失敗，**不可濾**。其他 JSON 預設只忽略頂層 updated_at / fetched_at。
- parquet：以 DataFrame 內容比較；忽略 `VOLATILE_PARQUET_COLS`（列級 fetched_at / captured_at）。
- 其他檔：比位元組。新增 / 刪除檔一律實質。

分支已存在時（代表有未合併的開啟中 PR）—— 不 stash、不 rebase、不 force
--------------------------------------------------------------------------------
1. 快照腳本輸出、還原工作樹；2. `checkout -B <branch> origin/<branch>` + 一般 `merge origin/main`
   （衝突 → abort、exit 1）；3. 以 `union_parquet_by_date` 把腳本輸出併入分支既有 parquet；
4. 重算並驗證 metadata；5. commit → 一般 push。

union 規則（fail-closed，**禁止任何「缺值用舊值補」**）
-------------------------------------------------------
key = date（兩邊都有 sector 欄時為 date+sector）。
- 只在分支有的 key → 原樣保留；只在新輸出有的 key → 加入。
- 兩邊都有的 key：忽略揮發欄（fetched_at / captured_at / updated_at）逐欄比對：
  完全相同 → 保持；舊 null、新有值 → 採新值（記錄 log）；
  **舊非 null 而新為 null/缺欄，或兩邊皆非 null 但不同 → PublishError（exit 1，不寫入、不 commit、不 push）**。
- 凍結帳本（`LEDGER_PATHS`，macro_forward_test/signals.parquet）：同 date 已存在則保留既有列，
  任何差異（含舊 null→新有值）一律 fail-closed；新 date 才追加。
- 欄位：分支有而新輸出沒有的欄位保留；共同欄位型別群組衝突 → fail-closed。
- **人工處理步驟（fail-closed 後每天都會紅，直到清除；這是刻意的設計取捨，不自動覆寫）**：
  1) 關閉該資料 PR（不合併）；2) 刪除遠端分支 `auto/data-<job>`；
  3) 下次排程會從 main 重建該分支（分支不存在 → 由 main 為基底開新分支）。
  若判斷是資料契約問題（例如來源改了既有日的值），請回報 ChatGPT 決定契約，不要硬刪資料。
- 本 helper 沒有任何補列／補缺日邏輯：缺漏就是缺漏，不以 11/6 的值冒充 11/5。

metadata 一致性（commit 前重算 + 驗證，不可靠「下次自癒」）
--------------------------------------------------------
讀 origin/main 343f0e0e 實檔後，可由 parquet 重算的欄位（`reconcile_metadata`）：
- data_cache/metadata.json：datasets[name].row_count = len(data_cache/<name>.parquet)；
  last_updated = max(date) 的 ISO 日期（無資料 → null）。例外：last_error 含「sanity 不過」時，
  腳本刻意不替不合格檔背書 last_updated → 只重算 row_count，last_updated 列入未檢查。
- data_cache/sector_flow/metadata.json：row_count = len(daily_net.parquet)；
  last_updated = max(date)；n_days = date 正規化後的相異日數（對照 update_sector_flow 寫法）。
一致性規則（不可重算、但不得矛盾，`verify_metadata`）：last_error 為空時 row_count 不得為 0。
重算後再獨立驗證一次（宣稱值 == 由資料重算值），不符 → fail-closed。
**未檢查**（無法由 parquet 單獨重算，保留最新一輪腳本的值）：sector_flow/bubble_latest.json
（由 compute 層以窗口重算）、metadata 內 coverage／per_day／markets_summary／fetch_diag／
warnings／unresolved_days／holiday 旗標／bubble_window／industry、industry_raw.json、ticker_sector.json。

PR body 的狀態與時間欄位（判不出就寫「無法判定」，不猜）
--------------------------------------------------------
①更新失敗（metadata last_error 非空或 unresolved_days 非空）②休市／無新資料（holiday 旗標，
或各 parquet 相對 origin/main 無新列且無錯誤）③資料過期（最後資料日距今天數；只陳述事實，
不套門檻）。
D3（DEC-148）空抓取三態分流（僅 data_cache/metadata.json 的 dataset 帶 `fetch_outcome` 時）：
只有 FETCH_FAILED 進①；NO_NEW_DATA 進②「無新資料（來源讀取成功）」，**不宣稱資料 fresh**；UNDETERMINED
進②「無法判定」。缺 `fetch_outcome`（舊 metadata）、或 last_error 不是純空抓取標記
（含「sanity 不過」複合字串）→ 維持現行行為（進①）。三態**不**由週末／休市推論；休市推論仍只來自
sector_flow 的 holiday 旗標。`fetch_outcome` 變化屬實質變更（需開 PR）；`fetch_evidence` 不得含時間戳。observation_date＝`--observation-date`，未帶則於表中列各檔最後資料日；
fetched_at 取自資料檔；published_at 一律「n/a（來源未提供）」。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

import pandas as pd

# D3(DEC-148):空抓取三態。本腳本在 workflow 以 `python scripts/publish_data_pr.py` 執行，sys.path[0]=scripts/，
# 需補 repo root 才 import 得到 shared.*（同 scripts/update_macro_history.py 作法）。
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from shared.fetch_outcome import (  # noqa: E402
    META_EVIDENCE_KEY,
    META_OUTCOME_KEY,
    FetchOutcome,
    parse_outcome,
)
from shared.staleness import EMPTY_FETCH_MARKER  # noqa: E402

BASE_BRANCH = "main"
BRANCH_PREFIX = "auto/data-"
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "github-actions[bot]@users.noreply.github.com"

NA_PUBLISHED = "n/a（來源未提供）"

# 揮發鍵：依檔案（相對 repo 根的 posix 路徑）列出；未列的 JSON 用 _DEFAULT_VOLATILE（只忽略頂層）。
VOLATILE_JSON_KEYS: dict[str, frozenset[str]] = {
    "data_cache/metadata.json": frozenset({"updated_at"}),
    "data_cache/sector_flow/metadata.json": frozenset({"updated_at"}),
    "data_cache/sector_flow/bubble_latest.json": frozenset({"updated_at"}),
    "data_cache/sector_flow/industry_raw.json": frozenset({"fetched_at"}),
    # macro_core._macro_durable_save 每次寫入都蓋 cached_at = now()（實讀 src/data/macro/macro_core.py）
    # fetched_at 與 cached_at 同理（重抓時間戳）；value／date／source 等欄位變動仍為實質
    "data_cache/macro_last_good/tw_pmi.json": frozenset({"cached_at", "fetched_at"}),
}
_DEFAULT_VOLATILE = frozenset({"updated_at", "fetched_at"})
VOLATILE_PARQUET_COLS = frozenset({"fetched_at", "captured_at"})
VOLATILE_ROW_COLS = VOLATILE_PARQUET_COLS | {"updated_at"}
PARQUET_KEY = "date"
LEDGER_PATHS = frozenset({"data_cache/macro_forward_test/signals.parquet"})

MACRO_META = "data_cache/metadata.json"
SECTOR_META = "data_cache/sector_flow/metadata.json"
SECTOR_PARQUET = "data_cache/sector_flow/daily_net.parquet"

Result = namedtuple("Result", "rc stdout stderr")

HUMAN_ACTION = "請人工處理：關閉該資料 PR 並刪除分支，或回報 ChatGPT 決定契約。"


class PublishError(RuntimeError):
    """fail loud：訊息直接印給人看。"""


# ───────────────────────── 純函式：實質變更判定 ─────────────────────────
def _strip_keys(obj, drop: frozenset[str], top_only: bool = False, _top: bool = True):
    """移除揮發鍵。top_only=True 時只動頂層（巢狀同名鍵視為實質）。"""
    if isinstance(obj, dict):
        return {k: _strip_keys(v, drop, top_only, False) for k, v in obj.items()
                if not (k in drop and (_top or not top_only))}
    if isinstance(obj, list):
        return [_strip_keys(v, drop, top_only, False) for v in obj]
    return obj


def _canon(obj) -> str:
    """型別嚴格：json.dumps 讓 True/1/1.0 互不相等（Python == 會把它們視為相等）。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def json_substantive_change(path: str, old: bytes, new: bytes) -> bool:
    """True = 有實質差異（揮發鍵以外有任何不同；解析失敗 → 視為實質）。"""
    registered = path in VOLATILE_JSON_KEYS
    drop = VOLATILE_JSON_KEYS.get(path, _DEFAULT_VOLATILE)
    try:
        return _canon(_strip_keys(json.loads(old), drop, not registered)) != \
            _canon(_strip_keys(json.loads(new), drop, not registered))
    except (ValueError, UnicodeDecodeError):
        return old != new


def parquet_substantive_change(old: bytes, new: bytes) -> bool:
    """True = DataFrame 內容有實質差異（忽略揮發列級時間戳欄）。"""
    a = pd.read_parquet(io.BytesIO(old))
    b = pd.read_parquet(io.BytesIO(new))
    a = a.drop(columns=list(VOLATILE_PARQUET_COLS & set(a.columns))).reset_index(drop=True)
    b = b.drop(columns=list(VOLATILE_PARQUET_COLS & set(b.columns))).reset_index(drop=True)
    if list(a.columns) != list(b.columns) or len(a) != len(b):
        return True
    return not a.equals(b)


def is_substantive(path: str, status: str, old: bytes | None, new: bytes | None) -> bool:
    if status in ("A", "D") or old is None or new is None:
        return True
    if path.endswith(".json"):
        return json_substantive_change(path, old, new)
    if path.endswith(".parquet"):
        return parquet_substantive_change(old, new)
    return old != new


# ───────────────────────── parquet 合併（fail-closed） ─────────────────────────
def _dtype_group(dt) -> str:
    k = getattr(dt, "kind", None)
    if k in ("i", "u", "f"):
        return "num"
    if k == "b":
        return "bool"
    if k == "M":
        return "time"
    return str(dt)


def _key_series(df: pd.DataFrame, with_sector: bool) -> pd.Series:
    k = pd.to_datetime(df[PARQUET_KEY]).dt.strftime("%Y-%m-%d")
    if with_sector:
        k = k.str.cat(df["sector"].astype(str), sep="|")
    return k


def _fmt(v) -> str:
    return repr(v.item() if hasattr(v, "item") else v)


def union_parquet_by_date(base: bytes, new: bytes, log=None, ledger: bool = False,
                          ctx: str = "") -> bytes:
    """base（分支現有）∪ new（腳本輸出），規則見模組 docstring「union 規則」。fail-closed。"""
    b = pd.read_parquet(io.BytesIO(base))
    n = pd.read_parquet(io.BytesIO(new))
    if PARQUET_KEY not in b.columns or PARQUET_KEY not in n.columns:
        raise PublishError(f"[{ctx}] parquet 缺 `{PARQUET_KEY}` 欄，無法安全合併，中止。{HUMAN_ACTION}")
    for c in set(b.columns) & set(n.columns):
        if b[c].isna().all() or n[c].isna().all():
            continue
        if _dtype_group(b[c].dtype) != _dtype_group(n[c].dtype):
            raise PublishError(f"[{ctx}] parquet 欄 `{c}` 型別衝突（分支 {b[c].dtype} vs 新輸出 {n[c].dtype}），"
                               f"中止。{HUMAN_ACTION}")
    with_sector = "sector" in b.columns and "sector" in n.columns
    bk, nk = _key_series(b, with_sector), _key_series(n, with_sector)
    for name, k in (("分支既有", bk), ("新輸出", nk)):
        if k.duplicated().any():
            raise PublishError(f"[{ctx}] {name}資料 key 重複 {sorted(set(k[k.duplicated()]))[:5]}，"
                               f"無法安全合併，中止。{HUMAN_ACTION}")
    cols = list(n.columns) + [c for c in b.columns if c not in n.columns]
    bi = b.set_index(bk.rename("_k"))
    ni = n.set_index(nk.rename("_k"))
    _nks = set(nk)
    common = [k for k in bk if k in _nks]

    problems: list[str] = []
    filled = 0
    for c in cols:
        if not common:
            break
        ov = bi.loc[common, c] if c in bi.columns else pd.Series([None] * len(common), index=common, dtype=object)
        nv = ni.loc[common, c] if c in ni.columns else pd.Series([None] * len(common), index=common, dtype=object)
        old_nn, new_nn = ~ov.isna().to_numpy(), ~nv.isna().to_numpy()
        if c in VOLATILE_ROW_COLS:
            continue
        differ = old_nn & new_nn & (ov.astype(object).to_numpy() != nv.astype(object).to_numpy())
        lost = old_nn & ~new_nn
        gained = ~old_nn & new_nn
        bad = differ | lost | (gained if ledger else False)
        for i in [i for i, f in enumerate(bad) if f][:10]:
            problems.append(f"key={common[i]} 欄位={c} 舊值={_fmt(ov.iloc[i])} 新值={_fmt(nv.iloc[i])}")
        filled += int(gained.sum()) if not ledger else 0
    if problems:
        raise PublishError(
            f"[{ctx}] fail-closed：分支既有資料與新輸出對同一 key 衝突（舊非空而新為空／缺欄，或兩邊皆有值但不同；"
            f"凍結帳本任何差異皆不允許），未 commit、未 push、本地工作樹已還原：\n  " + "\n  ".join(problems) + f"\n{HUMAN_ACTION}")
    if log and filled:
        log(f"  [union] 舊 null→新有值，採新值 {filled} 格")

    keep_common = bi.loc[common].reindex(columns=cols)
    new_common = ni.loc[common].reindex(columns=cols)
    merged_common = keep_common.combine_first(new_common)[cols]  # 舊值優先（含揮發欄）；僅舊 null 才取新
    only_b = bi[~bi.index.isin(common)].reindex(columns=cols)
    only_n = ni[~ni.index.isin(common)].reindex(columns=cols)
    if log and len(only_n):
        log(f"  [union] 新輸出獨有 key 追加 {len(only_n)} 列；分支獨有 key 保留 {len(only_b)} 列")
    out = pd.concat([merged_common, only_b, only_n]).reset_index(drop=True)
    for c in cols:
        target = n[c].dtype if c in n.columns else b[c].dtype
        if out[c].dtype != target and (not out[c].isna().any() or target.kind in "fOMmU" or str(target) == "str"):
            try:
                out[c] = out[c].astype(target)
            except (TypeError, ValueError):
                pass
    out = out.iloc[pd.to_datetime(out[PARQUET_KEY]).argsort(kind="stable")].reset_index(drop=True)
    buf = io.BytesIO()
    out.to_parquet(buf, index=False)
    return buf.getvalue()


# ───────────────────────── metadata 重算 / 驗證 ─────────────────────────
def _pq_facts(root: Path, rel: str) -> tuple[int, str | None, int]:
    """(列數, 最後資料日 ISO 或 None, 相異日數)。檔案不存在 → (0, None, 0)。"""
    f = root / rel
    if not f.is_file():
        return 0, None, 0
    df = pd.read_parquet(f)
    if df.empty or PARQUET_KEY not in df.columns:
        return len(df), None, 0
    d = pd.to_datetime(df[PARQUET_KEY]).dt.normalize()
    return len(df), d.max().date().isoformat(), int(d.nunique())


def _expected_claims(root: Path, rel_meta: str, meta: dict):
    """回傳 (claims, problems)。

    claims：{描述: (metadata 宣稱值, 由資料重算值)}，只含可由 parquet 重算的欄位。
    problems：無對應 parquet、卻宣稱有列數／日期的 dataset（D7：不得把 row_count 改 0／last_updated 改 null，
    一律 fail-closed 並指名）；宣稱 row_count=0 且 last_updated=null 者視為與「檔不存在」一致，不產生 claim。
    """
    claims: dict[str, tuple[object, object]] = {}
    problems: list[str] = []

    def one(prefix: str, d: dict, rel_pq: str, check_last: bool) -> None:
        if not (root / rel_pq).is_file():
            if d.get("row_count") not in (0, None) or d.get("last_updated") is not None:
                problems.append(f"{rel_meta} {prefix.rstrip('.') or 'sector_flow'}：無對應 parquet `{rel_pq}`，"
                                f"但 metadata 宣稱 row_count={d.get('row_count')!r} last_updated={d.get('last_updated')!r}")
            return
        rows, last, ndays = _pq_facts(root, rel_pq)
        claims[f"{prefix}row_count"] = (d.get("row_count"), rows)
        if check_last:
            claims[f"{prefix}last_updated"] = (d.get("last_updated"), last)
        if rel_meta == SECTOR_META:
            claims["n_days"] = (d.get("n_days"), ndays)

    if rel_meta == MACRO_META:
        for name, d in (meta.get("datasets") or {}).items():
            # sanity 不過：腳本刻意不替不合格檔背書 last_updated → 只重算 row_count（last_updated 必須為 null，見 consistency）
            one(f"datasets.{name}.", d, f"data_cache/{name}.parquet",
                "sanity 不過" not in str(d.get("last_error") or ""))
    elif rel_meta == SECTOR_META:
        one("", meta, SECTOR_PARQUET, True)
    return claims, problems


def _consistency_problems(rel_meta: str, meta: dict) -> list[str]:
    """不可重算但不得矛盾的規則。

    1) last_error 為空時 row_count 不得為 0；
    2) last_error 含「sanity 不過」時 last_updated 必須為 null
       （scripts/update_macro_history.py 於 skip／抓取例外／抓取為空三個 sanity 分支都不替不合格檔背書 last_updated，
        維持初始值 None）；否則 fail-closed。
    """
    out = []
    if rel_meta == MACRO_META:
        for name, d in (meta.get("datasets") or {}).items():
            if not d.get("last_error") and d.get("row_count") == 0:
                out.append(f"datasets.{name}: last_error 為空但 row_count=0")
            if META_OUTCOME_KEY in d:
                _oc = parse_outcome(d.get(META_OUTCOME_KEY))
                if _oc is None:
                    out.append(f"datasets.{name}: {META_OUTCOME_KEY}={d.get(META_OUTCOME_KEY)!r} 不是三態之一")
                elif _oc is FetchOutcome.FETCH_FAILED and not d.get(META_EVIDENCE_KEY):
                    out.append(f"datasets.{name}: {META_OUTCOME_KEY}=FETCH_FAILED 但沒有 {META_EVIDENCE_KEY}")
            if "sanity 不過" in str(d.get("last_error") or "") and d.get("last_updated") is not None:
                out.append(f"datasets.{name}: last_error 含「sanity 不過」但 last_updated={d.get('last_updated')!r}（必須為 null）")
    elif rel_meta == SECTOR_META:
        if not meta.get("last_error") and meta.get("row_count") == 0:
            out.append("last_error 為空但 row_count=0")
    return out


def _in_scope(rel: str, paths: list[str]) -> bool:
    return any(rel == p or rel.startswith(p.rstrip("/") + "/") for p in paths)


def _set_claim(meta: dict, desc: str, value) -> None:
    parts = desc.split(".")
    node = meta
    if parts[0] == "datasets":
        node = meta["datasets"][parts[1]]
        parts = parts[2:]
    node[parts[-1]] = value


def reconcile_metadata(root: Path, paths: list[str], log=print) -> list[str]:
    """以最終 parquet 重算可重算欄位並寫回 metadata（只在不同時寫）。回傳修正描述。"""
    fixes: list[str] = []
    for rel in (MACRO_META, SECTOR_META):
        f = root / rel
        if not f.is_file() or not _in_scope(rel, paths):
            continue
        meta = json.loads(f.read_text(encoding="utf-8"))
        claims, probs = _expected_claims(root, rel, meta)
        if probs:
            raise PublishError("metadata 與資料不一致（無對應 parquet，fail-closed，不改寫 metadata）：\n  "
                               + "\n  ".join(probs) + f"\n{HUMAN_ACTION}")
        changed = False
        for desc, (claimed, actual) in claims.items():
            if _canon(claimed) != _canon(actual):
                fixes.append(f"{rel} {desc}: {claimed!r} -> {actual!r}")
                _set_claim(meta, desc, actual)
                changed = True
        if changed:
            f.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for x in fixes:
        log(f"  [metadata 重算] {x}")
    return fixes


def verify_metadata(root: Path, paths: list[str]) -> list[str]:
    """獨立驗證：宣稱值 == 由資料重算值，且無矛盾。回傳不符清單（空 = 通過）。"""
    bad: list[str] = []
    for rel in (MACRO_META, SECTOR_META):
        f = root / rel
        if not f.is_file() or not _in_scope(rel, paths):
            continue
        meta = json.loads(f.read_text(encoding="utf-8"))
        claims, probs = _expected_claims(root, rel, meta)
        bad += probs
        for desc, (claimed, actual) in claims.items():
            if _canon(claimed) != _canon(actual):
                bad.append(f"{rel} {desc}: metadata 宣稱 {claimed!r}，資料重算 {actual!r}")
        bad += [f"{rel} {p}" for p in _consistency_problems(rel, meta)]
    return bad


# ───────────────────────── PR body ─────────────────────────
def _max_str(vals: list[str]) -> str | None:
    return max(vals) if vals else None


def collect_fetched_at(files: dict[str, bytes]) -> str:
    """從實際變更檔取最大 fetched_at（不偽造；找不到回 n/a）。"""
    found: list[str] = []
    for path, data in files.items():
        try:
            if path.endswith(".parquet"):
                df = pd.read_parquet(io.BytesIO(data))
                if "fetched_at" in df.columns:
                    found += [str(x) for x in df["fetched_at"].dropna().unique()]
            elif path.endswith(".json"):
                obj = json.loads(data)
                v = obj.get("fetched_at") if isinstance(obj, dict) else None
                if v:
                    found.append(str(v))
        except Exception:  # 只影響 PR 說明文字，不影響資料
            continue
    return _max_str(found) or "n/a（資料檔內無 fetched_at）"


def assess_state(files: dict[str, bytes], new_rows: dict[str, int | None], today: str) -> dict:
    """由 metadata／腳本輸出判斷三種狀態；判不出 → 「無法判定」（不猜）。"""
    failures: list[str] = []
    holidays: list[str] = []
    no_new: list[str] = []         # D3：NO_NEW_DATA（來源讀取成功、無新觀測）
    undetermined: list[str] = []   # D3：UNDETERMINED（空抓取但證據不足）
    has_meta = False
    for path, data in files.items():
        if path == MACRO_META:
            has_meta = True
            for name, d in (json.loads(data).get("datasets") or {}).items():
                if d.get("last_error"):
                    # D3：只有「純空抓取標記」且帶合法非 FETCH_FAILED 三態者才從①分流出去；
                    # 其餘（舊 metadata 無欄、FETCH_FAILED、值不合法、last_error 是別的錯／複合字串如「sanity 不過」）
                    # 一律維持現行行為進①。三態不由週末／休市推論。
                    _oc = parse_outcome(d.get(META_OUTCOME_KEY))
                    if d.get("last_error") == EMPTY_FETCH_MARKER and _oc is FetchOutcome.NO_NEW_DATA:
                        no_new.append(name)
                    elif d.get("last_error") == EMPTY_FETCH_MARKER and _oc is FetchOutcome.UNDETERMINED:
                        undetermined.append(name)
                    elif _oc is FetchOutcome.FETCH_FAILED and d.get(META_EVIDENCE_KEY):
                        failures.append(f"{name}: {d['last_error']}（FETCH_FAILED：{d[META_EVIDENCE_KEY]}）")
                    else:
                        failures.append(f"{name}: {d['last_error']}")
        elif path == SECTOR_META:
            has_meta = True
            m = json.loads(data)
            if m.get("last_error"):
                failures.append(f"sector_flow: {m['last_error']}")
            if m.get("unresolved_days"):
                failures.append(f"sector_flow unresolved_days: {m['unresolved_days']}")
            holidays += [d for d, v in (m.get("per_day") or {}).items() if v.get("holiday")]
    last_dates: dict[str, str] = {}
    for path, data in files.items():
        if path.endswith(".parquet"):
            df = pd.read_parquet(io.BytesIO(data))
            if PARQUET_KEY in df.columns and not df.empty:
                last_dates[path] = pd.to_datetime(df[PARQUET_KEY]).max().date().isoformat()
    t = _dt.date.fromisoformat(today)
    stale = {p: (d, (t - _dt.date.fromisoformat(d)).days) for p, d in last_dates.items()}
    weekend_h, weekday_h = [], []
    for d in holidays:
        day = _parse_day(d)
        (weekend_h if day is not None and day.weekday() >= 5 else weekday_h).append(d)
    known_new = [v for v in new_rows.values() if v is not None]
    suspect = (f"⚠️ 週間日無資料，無法區分休市與抓取失敗，需人工確認：{sorted(weekday_h)}"
               if weekday_h else None)
    if failures:
        s2 = "有更新失敗，無法據以判定休市或無新資料" + (f"；{suspect}" if suspect else "")
    elif suspect:
        s2 = suspect  # sector_flow 兩源皆空也會標 holiday 且不記 last_error，週間日不得自動判休市
    elif weekend_h:
        s2 = f"休市（週末日 holiday 旗標）：{sorted(weekend_h)}"
    elif known_new and sum(known_new) == 0:
        s2 = "無新資料（各 parquet 相對 origin/main 無新列，且無錯誤）"
    elif not has_meta and not known_new:
        s2 = "無法判定"
    else:
        s2 = "無（本次有新列，且無休市旗標）"
    if failures:
        s1 = "；".join(failures)
    elif suspect:
        s1 = f"疑似失敗／無法判定（週間日無資料）：{sorted(weekday_h)}"
    elif no_new or undetermined:
        s1 = "無（無 FETCH_FAILED；空抓取已依三態分流，見②）"
    else:
        s1 = "無（metadata 未見 last_error／unresolved_days）" if has_meta else "無法判定（無 metadata 可判讀）"
    # D3：三態文案併入②。NO_NEW_DATA 只代表「來源在請求範圍內沒有新觀測」，不代表資料是最新的；
    # 有 NO_NEW_DATA／UNDETERMINED 時，不再沿用「各 parquet 無新列且無錯誤」那句（它對空抓取不成立）。
    oc_parts: list[str] = []
    if no_new:
        oc_parts.append(f"無新資料（來源讀取成功，請求範圍內無新觀測；不代表資料為最新）：{sorted(no_new)}")
    if undetermined:
        oc_parts.append(f"無法判定（空抓取、證據不足，非失敗亦非確認無新資料）：{sorted(undetermined)}")
    if oc_parts:
        keep_base = bool(failures or suspect or weekend_h)
        s2 = "；".join(([s2] if keep_base else []) + oc_parts)
    return {"failure": s1, "holiday": s2, "stale": stale}


def _parse_day(v: str):
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return _dt.datetime.strptime(str(v), fmt).date()
        except ValueError:
            continue
    return None


STATUS_START = "<!-- data-status:start -->"
STATUS_END = "<!-- data-status:end -->"
# 舊格式（0b9c5b1f／beb45c4c 版）中「確定屬於舊狀態」的標準行；只認原樣行，無法確定的人工文字一律保留。
_LEGACY_LINE_RES = [re.compile(x) for x in (
    r"^最新 head SHA：", r"^### 時間欄位\s*$", r"^\| 欄位 \| 值 \|\s*$", r"^\|---\|---\|\s*$",
    r"^\| observation_date（", r"^\| fetched_at（", r"^\| published_at（",
    r"^### 資料狀態（由 metadata／腳本輸出判斷，判不出即「無法判定」）\s*$",
    r"^- ① 更新失敗：", r"^- ② 休市／無新資料：", r"^- ③ 資料過期（",
    r"^  - `[^`]*`：最後資料日 .*距今 \d+ 天\s*$", r"^  - 無法判定（無 parquet 日期）\s*$")]
_LISTING_HEAD = re.compile(r"^### 變更檔\s*$")
_LISTING_ITEM = re.compile(r"^- `[^`]*`\s*$")
_RESIDUAL_TOKENS = ("observation_date", "時間欄位", "資料狀態", "更新失敗", "休市／無新資料", "最後資料日", "最新 head SHA")
STALE_WARNING = "⚠️ 下方可能殘留舊格式狀態，以此區塊為準"


def head_line(sha: str) -> str:
    return f"最新 head SHA：`{sha}`（每次 cron push 後更新此行；請核對 required check 對應的 SHA 與此相符）"


def build_status_block(files: list[str], observation_date: str | None, fetched_at: str,
                       state: dict | None, head_sha: str) -> str:
    """每次 push 整段重算的區塊：最新 head SHA＋時間欄位＋三態資料狀態＋變更檔。"""
    listing = "\n".join(f"- `{p}`" for p in files)
    state = state or {"failure": "無法判定", "holiday": "無法判定", "stale": {}}
    stale_lines = "\n".join(f"  - `{p}`：最後資料日 {d}，距今 {n} 天" for p, (d, n) in sorted(state["stale"].items())) \
        or "  - 無法判定（無 parquet 日期）"
    return (
        f"{STATUS_START}\n"
        f"{head_line(head_sha)}\n\n"
        "### 時間欄位\n"
        "| 欄位 | 值 |\n|---|---|\n"
        f"| observation_date（資料最後日） | {observation_date or '見下方各檔最後資料日'} |\n"
        f"| fetched_at（抓取時間，取自資料檔） | {fetched_at} |\n"
        f"| published_at（來源發布時間） | {NA_PUBLISHED} |\n\n"
        "### 資料狀態（由 metadata／腳本輸出判斷，判不出即「無法判定」）\n"
        f"- ① 更新失敗：{state['failure']}\n"
        f"- ② 休市／無新資料：{state['holiday']}\n"
        f"- ③ 資料過期（僅陳述事實天數，未套門檻）：\n{stale_lines}\n\n"
        f"### 變更檔\n{listing}\n"
        f"{STATUS_END}"
    )


def _scan_blocks(lines: list[str]):
    """標記必須各自獨佔一行（strip 後完全相等）；嵌在人工文字中的標記字樣不算界線。
    回傳 (完整區塊 [(start, end)], 孤兒標記行索引集合)。"""
    blocks: list[tuple[int, int]] = []
    orphans: set[int] = set()
    open_idx = None
    for i, ln in enumerate(lines):
        t = ln.strip()
        if t == STATUS_START:
            if open_idx is not None:
                orphans.add(open_idx)  # 前一個 start 沒有 end
            open_idx = i
        elif t == STATUS_END:
            if open_idx is None:
                orphans.add(i)
            else:
                blocks.append((open_idx, i))
                open_idx = None
    if open_idx is not None:
        orphans.add(open_idx)
    return blocks, orphans


def update_pr_body(old: str, block: str) -> str:
    """只替換標記區塊內容，區塊外（含人工補註）原樣保留。

    - 標記需各自獨佔一行；多個完整區塊 → 保留第一個替換為新內容，其餘移除；
      孤兒 start／end 只移除標記行本身，不吞其間的人工內容。
    - 無完整區塊：保守升級舊格式 —— 只移除確定屬於舊狀態的標準行（舊 head SHA 行、舊時間欄位／三態／變更檔標準行），
      其餘人工文字一律保留，新區塊放在第一個被移除行的位置（沒有則附加尾端）；
      若移除後仍殘留疑似舊狀態字樣（例如標題被改名）→ 在區塊上方加一行警語，避免兩份「看起來都是最新」。
    """
    lines = old.split("\n")
    blocks, orphans = _scan_blocks(lines)
    blines = block.split("\n")
    if blocks:
        out: list[str] = []
        skip_until = -1
        starts = {st: en for st, en in blocks}
        for i, ln in enumerate(lines):
            if i <= skip_until or i in orphans:
                continue
            if i in starts:
                if i == blocks[0][0]:
                    out += blines
                skip_until = starts[i]
                continue
            out.append(ln)
        return re.sub(r"\n{3,}", "\n\n", "\n".join(out))
    kept: list[str] = []
    first = None
    in_list = False
    for i, ln in enumerate(lines):
        if i in orphans:
            continue
        remove = False
        if _LISTING_HEAD.match(ln):
            in_list, remove = True, True
        elif in_list and _LISTING_ITEM.match(ln):
            remove = True
        else:
            in_list = False
            remove = any(r.match(ln) for r in _LEGACY_LINE_RES)
        if remove:
            if first is None:
                first = len(kept)
            continue
        kept.append(ln)
    rest = "\n".join(kept)
    residual = any(tok in rest for tok in _RESIDUAL_TOKENS)
    ins = ([STALE_WARNING, ""] if residual else []) + blines
    if first is None:
        out = kept[:]
        while out and not out[-1].strip():
            out.pop()
        out += [""] + ins + [""]
    else:
        out = kept[:first] + ins + [""] + kept[first:]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


def build_pr_body(job: str, files: list[str], observation_date: str | None, fetched_at: str,
                  state: dict | None = None, head_sha: str = "（push 後更新）") -> str:
    return (
        f"## 自動資料發布：{job}\n\n"
        "本 PR 由每日 cron 自動產生（`scripts/publish_data_pr.py`），內容為腳本實際抓取的資料增量。\n\n"
        "### ⚠️ 合併前必讀\n"
        "本 PR 由 GITHUB_TOKEN 建立，CI 不一定自動觸發；未見 `ui2-browser-gate` 綠燈（且 head SHA 與本 PR 相符）"
        "前不得合併；若無 CI，請有權限者 Close→Reopen 或按 Update branch 以產生原生 pull_request 檢查。\n"
        "**未經人工審閱不得合併。** 本 PR 未啟用 auto-merge。\n\n"
        + build_status_block(files, observation_date, fetched_at, state, head_sha) + "\n\n"
        "### 人工處理（cron 發布 fail-closed 時）\n"
        f"若每日排程在「發布資料」步驟持續失敗：① 關閉本 PR（不合併）；② 刪除分支 `{BRANCH_PREFIX}{job}`；"
        "③ 下次排程會從 main 重建。資料契約疑義請回報 ChatGPT，不要硬刪資料。\n"
    )


# ───────────────────────── subprocess 層（可注入） ─────────────────────────
def default_runner(cmd: list[str], cwd: str | None = None, input: str | None = None,
                   binary: bool = False) -> Result:
    p = subprocess.run(cmd, cwd=cwd, input=input, capture_output=True, text=not binary)
    return Result(p.returncode, p.stdout, p.stderr)


JOB_RE = r"^[a-z0-9][a-z0-9-]*$"
_PUSH_BRANCH_RE = re.compile(r"^auto/data-[a-z0-9][a-z0-9-]*$")


def _guard(cmd: list[str]) -> None:
    """白名單式縱深防禦（只看 argv 的子命令位置，不比對 -m 訊息字串）。

    push 只允許恰為 `push [-u] origin auto/data-<job>`；其餘 push 形式一律拒絕。
    另拒絕 rebase / reset --hard / update-ref / send-pack / pull --rebase /
    gh pr merge / gh workflow（不 dispatch）/ gh api 含 protection。
    """
    if cmd[:1] == ["git"]:
        i = 1
        while i < len(cmd) and cmd[i].startswith("-"):
            i += 2 if cmd[i] in ("-c", "-C", "--git-dir", "--work-tree") else 1
        if i >= len(cmd):
            return
        sub, rest = cmd[i], cmd[i + 1:]
        if sub == "push":
            ok = (rest[:1] == ["-u"] and len(rest) == 3 and rest[1] == "origin" and _PUSH_BRANCH_RE.match(rest[2])) or \
                 (len(rest) == 2 and rest[0] == "origin" and _PUSH_BRANCH_RE.match(rest[1]))
            if not ok:
                raise PublishError(f"禁止的 push 形式（僅允許 push [-u] origin auto/data-<job>）：{' '.join(cmd)}")
        elif sub in ("rebase", "update-ref", "send-pack"):
            raise PublishError(f"禁止 {sub}")
        elif sub == "reset" and "--hard" in rest:
            raise PublishError("禁止 reset --hard")
        elif sub == "pull" and any(r.startswith("--rebase") for r in rest):
            raise PublishError("禁止 pull --rebase")
    elif cmd[:1] == ["gh"]:
        if cmd[1:3] == ["pr", "merge"]:
            raise PublishError("禁止 gh pr merge（合併由人工）")
        if cmd[1:2] == ["workflow"]:
            raise PublishError("禁止 gh workflow（workflow_dispatch 的 checks 不符合 required status checks）")
        if cmd[1:2] == ["api"] and any("protection" in c or "dispatches" in c for c in cmd):
            raise PublishError("禁止透過 gh api 動 branch protection／dispatch workflow")


class Publisher:
    def __init__(self, runner=default_runner, cwd: str | None = None, log=print):
        self.runner, self.cwd, self.log = runner, cwd, log

    def run(self, cmd: list[str], check: bool = True, input: str | None = None,
            binary: bool = False) -> Result:
        _guard(cmd)
        r = self.runner(cmd, self.cwd, input, binary)
        if check and r.rc != 0:
            raise PublishError(f"指令失敗 rc={r.rc}：{' '.join(cmd)}\n{r.stderr or ''}")
        return r

    def git(self, *args: str, check: bool = True, binary: bool = False) -> Result:
        return self.run(["git", *args], check=check, binary=binary)

    def gitid(self, *args: str, check: bool = True) -> Result:
        return self.run(["git", "-c", f"user.name={BOT_NAME}", "-c", f"user.email={BOT_EMAIL}", *args], check=check)

    # ── 偵測（不 stage、不寫）──
    def detect(self, paths: list[str], force_add: bool) -> list[tuple[str, str]]:
        out = self.git("status", "--porcelain=v1", "-z", "-uall", "--ignored=matching", "--", *paths).stdout
        res: list[tuple[str, str]] = []
        for ent in filter(None, out.split("\0")):
            xy, path = ent[:2], ent[3:]
            if "__pycache__" in path.split("/") or path.endswith(".pyc"):
                continue
            if xy == "!!":
                if force_add:
                    if path.endswith("/"):  # 被 ignore 的整個目錄項 → 展開成檔案
                        root = Path(self.cwd or ".")
                        for f in sorted((root / path).rglob("*")):
                            rel = f.relative_to(root).as_posix()
                            if f.is_file() and "__pycache__" not in rel.split("/") and not rel.endswith(".pyc"):
                                res.append(("A", rel))
                    else:
                        res.append(("A", path))
            elif xy == "??":
                res.append(("A", path))
            elif "D" in xy:
                res.append(("D", path))
            else:
                res.append(("M", path))
        return sorted(res, key=lambda t: t[1])

    def worktree_bytes(self, path: str) -> bytes | None:
        p = Path(self.cwd or ".") / path
        return p.read_bytes() if p.is_file() else None

    def head_bytes(self, path: str, ref: str = "HEAD") -> bytes | None:
        r = self.git("show", f"{ref}:{path}", check=False, binary=True)
        return r.stdout if r.rc == 0 else None

    def classify(self, changed: list[tuple[str, str]]):
        subst, noise = [], []
        for st, p in changed:
            ok = is_substantive(p, st, self.head_bytes(p) if st != "A" else None,
                                self.worktree_bytes(p) if st != "D" else None)
            (subst if ok else noise).append((st, p))
        return subst, noise

    def restore(self, changed: list[tuple[str, str]]) -> None:
        for st, p in changed:
            if st == "A":
                f = Path(self.cwd or ".") / p
                if f.is_dir():
                    shutil.rmtree(f, ignore_errors=True)
                elif f.exists():
                    f.unlink()
            else:
                self.git("checkout", "HEAD", "--", p)

    def count_new_rows(self, path: str, final: bytes) -> int | None:
        """final 相對 origin/main 的新 key 列數；無法比較回 None。"""
        if not path.endswith(".parquet"):
            return None
        base = self.head_bytes(path, f"origin/{BASE_BRANCH}")
        try:
            f = pd.read_parquet(io.BytesIO(final))
            if base is None:
                return len(f)
            b = pd.read_parquet(io.BytesIO(base))
            ws = "sector" in b.columns and "sector" in f.columns
            return int((~_key_series(f, ws).isin(set(_key_series(b, ws)))).sum())
        except Exception:
            return None


def _abort_cleanup(pub: Publisher, orig: str, changed: list[tuple[str, str]]) -> None:
    """fail-closed 路徑：中止 merge、切回原分支並丟棄本輪腳本輸出，工作樹回到乾淨（未 commit／未 push）。"""
    pub.git("merge", "--abort", check=False)
    pub.git("checkout", "-f", orig, check=False)
    pub.restore([(st, p) for st, p in changed if st == "A"])  # 腳本新產生的未追蹤檔
    pub.log("已還原本地工作樹並切回原分支。")


def publish(args, pub: Publisher, today: str | None = None) -> int:
    job = args.job
    branch = f"{BRANCH_PREFIX}{job}"
    paths = list(args.paths)
    today = today or _dt.datetime.now(_dt.timezone.utc).date().isoformat()
    root = Path(pub.cwd or ".")

    changed = pub.detect(paths, args.force_add)
    if not changed:
        pub.log("無實質變更：--paths 下沒有任何變更檔，不開 PR。")
        return 0
    orig = pub.git("symbolic-ref", "-q", "--short", "HEAD", check=False).stdout.strip() \
        or pub.git("rev-parse", "HEAD").stdout.strip()
    try:
        subst, noise = pub.classify(changed)
    except Exception:  # 例如損毀 parquet：還原本輪輸出、原例外往上拋
        if not args.dry_run:
            _abort_cleanup(pub, orig, changed)
        raise
    for st, p in noise:
        pub.log(f"  [僅揮發欄位變動] {p}")
    for st, p in subst:
        pub.log(f"  [實質變更:{st}] {p}")
    if not subst:
        pub.log("無實質變更：僅時間戳等揮發欄位變動，還原工作樹、不開 PR。")
        if not args.dry_run:
            pub.restore(changed)
        return 0

    files = [p for _, p in changed]
    add = ["git", "add"] + (["-f"] if args.force_add else []) + ["--", *paths, ":(exclude,glob)**/__pycache__/**"]
    title_date = args.observation_date or today
    title = f"🤖 資料發布 {job}：{title_date}"
    remote_has = pub.git("ls-remote", "--exit-code", "--heads", "origin", branch, check=False).rc == 0

    if args.dry_run:
        pub.log("[dry-run] 有實質變更，計畫如下（零寫入）：")
        pub.log(f"[dry-run] 分支：{branch}（遠端{'已存在 → merge origin/main 路徑' if remote_has else '不存在 → 由目前 HEAD 建立'}）")
        pub.log(f"[dry-run] 變更檔：{files}")
        if remote_has:
            pub.log(f"[dry-run] git fetch origin {branch} ; git checkout -B {branch} origin/{branch} ; git merge --no-edit origin/{BASE_BRANCH} ; union parquet（fail-closed）")
        else:
            pub.log(f"[dry-run] git checkout -B {branch}")
        pub.log("[dry-run] 重算並驗證 metadata（commit 前）")
        pub.log(f"[dry-run] {' '.join(add)} ; git commit -m {args.commit_msg!r} ; git push -u origin {branch}")
        pub.log(f"[dry-run] gh pr list --head {branch} --state open ; (無則) gh pr create --base {BASE_BRANCH} --head {branch} --title {title!r} ; (有則) gh pr edit <n> --body <更新 head SHA 行>")
        return 0

    def _stage() -> bool:
        snapshot = {p: pub.worktree_bytes(p) for _, p in changed}
        pub.git("config", "--local", "user.name", BOT_NAME)
        pub.git("config", "--local", "user.email", BOT_EMAIL)

        def _finalize_metadata() -> None:
            fixes = reconcile_metadata(root, paths, pub.log)
            bad = verify_metadata(root, paths)
            if bad:
                raise PublishError("metadata 與資料不一致（fail-closed，未 commit、未 push）：\n  " + "\n  ".join(bad)
                                   + f"\n{HUMAN_ACTION}")
            if fixes:
                pub.log(f"metadata 已依資料重算 {len(fixes)} 項並通過驗證。")

        if not remote_has:
            pub.git("checkout", "-B", branch)  # 工作樹變更隨身帶過去
            _finalize_metadata()
            pub.run(add)
            pub.gitid("commit", "-m", args.commit_msg)
            pushed = True
        else:
            tmp = Path(tempfile.mkdtemp(prefix="publish_data_pr_"))
            try:
                for st, p in changed:
                    if st != "D" and snapshot[p] is not None:
                        dst = tmp / p
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_bytes(snapshot[p])
                pub.restore(changed)
                pub.git("fetch", "origin", branch)
                pub.git("fetch", "origin", BASE_BRANCH)
                pub.git("checkout", "-B", branch, f"origin/{branch}")
                m = pub.gitid("merge", "--no-edit", f"origin/{BASE_BRANCH}", check=False)
                if m.rc != 0:
                    pub.git("merge", "--abort", check=False)
                    raise PublishError(
                        f"合併衝突：origin/{BASE_BRANCH} 與 {branch} 無法自動合併，已中止，未 push、未開 PR、遠端未動。\n"
                        f"請人工處理該分支後重跑。\n{m.stdout or ''}{m.stderr or ''}")
                for st, p in changed:
                    dst = root / p
                    if st == "D":
                        if dst.exists():
                            dst.unlink()
                        continue
                    if not (tmp / p).is_file():
                        pub.log(f"  [skip] 無檔案內容可套用：{p}")
                        continue
                    new = (tmp / p).read_bytes()
                    if p.endswith(".parquet") and dst.is_file():
                        new = union_parquet_by_date(dst.read_bytes(), new, pub.log, ledger=p in LEDGER_PATHS,
                                                    ctx=f"job={job} {p}")
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(new)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            _finalize_metadata()
            pub.run(add)
            if pub.git("diff", "--cached", "--quiet", check=False).rc != 0:
                pub.gitid("commit", "-m", args.commit_msg)
            head = pub.git("rev-parse", "HEAD").stdout.strip()
            remote_head = pub.git("rev-parse", f"origin/{branch}").stdout.strip()
            pushed = head != remote_head

        return pushed

    try:
        pushed = _stage()
    except Exception:  # N2：任何例外（含 pandas／IO）都先還原工作樹再原樣往上拋，不吞掉
        _abort_cleanup(pub, orig, changed)
        raise

    if pushed:
        pub.git("push", "-u", "origin", branch)
        pub.log(f"已推送分支 {branch}")
    else:
        pub.log(f"分支 {branch} 已含相同內容，不重複 push。")
    head_sha = pub.git("rev-parse", "HEAD").stdout.strip()

    final = {p: b for p in files if (b := pub.worktree_bytes(p)) is not None}
    state = assess_state(final, {p: pub.count_new_rows(p, b) for p, b in final.items()}, today)
    block = build_status_block(files, args.observation_date, collect_fetched_at(final), state, head_sha)
    body = build_pr_body(job, files, args.observation_date, collect_fetched_at(final), state, head_sha)

    hint = ("分支已推送、PR 未建立／未更新；請檢查『Allow GitHub Actions to create and approve pull requests』"
            "設定與 pull-requests: write 權限")
    try:
        lst = pub.run(["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "number"])
        prs = json.loads(lst.stdout or "[]")
        if prs:
            if pushed:
                n = str(prs[0]["number"])
                cur = json.loads(pub.run(["gh", "pr", "view", n, "--json", "body"]).stdout or "{}").get("body") or ""
                pub.run(["gh", "pr", "edit", n, "--body", update_pr_body(cur, block)])
                pub.log("已有開啟中的 PR：只重算 body 的 data-status 標記區塊，區塊外（含人工補註）保留；不留言。")
            else:
                pub.log("已有開啟中的 PR，分支無新內容，不動。")
        else:
            pub.run(["gh", "pr", "create", "--base", BASE_BRANCH, "--head", branch, "--title", title, "--body", body])
            pub.log("已建立 PR（CI 需由有權限者以原生 pull_request 事件觸發，見 PR body）。")
    except PublishError as e:
        raise PublishError(f"{hint}\n{e}") from e
    return 0


def _job_type(v: str) -> str:
    if not re.match(JOB_RE, v):
        raise argparse.ArgumentTypeError(f"--job 必須符合 {JOB_RE}")
    return v


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--job", required=True, type=_job_type)
    ap.add_argument("--paths", nargs="+", required=True)
    ap.add_argument("--commit-msg", required=True)
    ap.add_argument("--observation-date", default=None)
    ap.add_argument("--force-add", action="store_true", help="等同 git add -f（data_cache/*.parquet 被 .gitignore 蓋）")
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        return publish(args, Publisher())
    except PublishError as e:
        print(f"::error::{e}", file=sys.stderr)
        print(f"[publish_data_pr] FAIL: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
