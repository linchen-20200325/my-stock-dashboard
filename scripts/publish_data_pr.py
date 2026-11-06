#!/usr/bin/env python3
"""scripts/publish_data_pr.py — cron 資料以「獨立分支 + PR」發布（取代裸 `git push` main）。

為什麼有這支
------------
main 受 branch protection（required check `ui2-browser-gate`）保護，三支每日 cron
（update_macro_history / update_sector_flow / update_macro_forward_test）直接 `git push`
被 GH006 擋下。本 helper 的路線：

    cron 產出資料 → 判斷「實質變更」→ 推 `auto/data-<job>` 分支 → 以 GITHUB_TOKEN 開/沿用 PR
    → 對該分支 `workflow_dispatch` pr-check.yml（GITHUB_TOKEN 的 push 不會觸發 workflow，
      必須手動 dispatch 才有 required check）→ 合併由人工 / 另行授權（本批不啟用 auto-merge）

硬約束（`_run_checked` 以程式碼強制，測試以 runner 呼叫記錄斷言）：
不 push main、不帶 --force / --force-with-lease / `+refspec`、不 rebase、不改 GitHub 設定。

實質變更判定（§1：不得因過濾而丟掉實質資料）
--------------------------------------------
只決定「要不要發 PR」；一旦要發，commit 的是腳本輸出的**完整**檔案（含揮發欄位的新值）。
- JSON：忽略 `VOLATILE_JSON_KEYS` 列的揮發鍵（任意深度，依鍵名）後比較；未知鍵一律視為實質。
  依據（2026-11-06 讀 origin/main 343f0e0e 實檔）：
    data_cache/metadata.json                    updated_at（頂層；每次執行必變）
    data_cache/sector_flow/metadata.json        updated_at（頂層）
    data_cache/sector_flow/bubble_latest.json   updated_at（頂層）
    data_cache/sector_flow/industry_raw.json    fetched_at（頂層）
  其餘鍵（last_error / last_updated / row_count / per_day / warnings …）全是實質，
  特別是 `last_error` 變化代表來源失敗，**不可濾**。其他 JSON 預設只忽略 updated_at / fetched_at。
- parquet：以 DataFrame 內容比較（pyarrow 位元組不穩定）；忽略 `VOLATILE_PARQUET_COLS`
  （列級 fetched_at / captured_at 重蓋時間戳，腳本對重抓日 keep=last 會重蓋）。
  新增列、刪列、其他欄位值改變、欄位集改變 = 實質。
- 其他檔：比位元組。新增 / 刪除檔一律實質。

分支已存在時（代表有未合併的開啟中 PR）的做法 —— 不 stash、不 rebase、不 force
--------------------------------------------------------------------------------
1. 把腳本輸出（工作樹中變更檔）快照到暫存目錄，工作樹還原乾淨；
2. `git checkout -B <branch> origin/<branch>`，`git merge --no-edit origin/main`
   （一般 merge；衝突 → `merge --abort`、exit 1、不 push、不開 PR）；
3. 以「腳本輸出為準」套回快照：JSON/其他檔直接覆寫；parquet 以 **date 為單位**
   「新輸出的日期整日取代、分支上其餘日期保留」（避免第二天的 cron 以 main 為基底產出、
   覆蓋掉分支上尚未合併的前一天資料；與 update_sector_flow「重寫日先刪該日所有舊列」同語意）；
4. commit（有差異才 commit）→ 一般 push。
已知限制：此情境下 metadata.json 的 row_count 是「最新一輪腳本」的值，可能少於聯集後列數
（僅在 PR 未合併跨日時發生；下一輪於 main 重算會自癒）。

PR body 的時間欄位不偽造：observation_date 來自 `--observation-date`；fetched_at 取自實際變更
資料檔內的 fetched_at；published_at 在這三份資料中不存在 → 一律寫「n/a（來源未提供）」。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

import pandas as pd

BASE_BRANCH = "main"
BRANCH_PREFIX = "auto/data-"
CHECK_WORKFLOW = "pr-check.yml"
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "github-actions[bot]@users.noreply.github.com"

NA_PUBLISHED = "n/a（來源未提供）"

# 揮發鍵：依檔案（相對 repo 根的 posix 路徑）列出；未列的 JSON 用 _DEFAULT_VOLATILE。
VOLATILE_JSON_KEYS: dict[str, frozenset[str]] = {
    "data_cache/metadata.json": frozenset({"updated_at"}),
    "data_cache/sector_flow/metadata.json": frozenset({"updated_at"}),
    "data_cache/sector_flow/bubble_latest.json": frozenset({"updated_at"}),
    "data_cache/sector_flow/industry_raw.json": frozenset({"fetched_at"}),
}
_DEFAULT_VOLATILE = frozenset({"updated_at", "fetched_at"})
VOLATILE_PARQUET_COLS = frozenset({"fetched_at", "captured_at"})
PARQUET_KEY = "date"

Result = namedtuple("Result", "rc stdout stderr")


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
    """True = 有實質差異（揮發鍵以外有任何不同；解析失敗 → 視為實質）。

    已登記檔：揮發鍵依 VOLATILE_JSON_KEYS 於任意深度忽略（照舊）；
    未登記檔：只忽略頂層 updated_at / fetched_at，巢狀位置視為實質。
    """
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


def _dtype_group(dt) -> str:
    k = getattr(dt, "kind", None)
    if k in ("i", "u", "f", "b"):
        return "num" if k != "b" else "bool"
    if k == "M":
        return "time"
    return str(dt)


def union_parquet_by_date(base: bytes, new: bytes, log=None) -> bytes:
    """base（分支上現有）∪ new（腳本輸出）。

    - new 出現的日期整日取代 base 同日列（log 印被取代日期與列數）；
    - 欄位級保守：新列某欄缺值（NaN/None）而同 key（date[+sector]）舊列有值 → 保留舊值；
    - base 有而 new 沒有的欄位保留（不丟）；共同欄位型別群組衝突 → PublishError。
    """
    b = pd.read_parquet(io.BytesIO(base))
    n = pd.read_parquet(io.BytesIO(new))
    if PARQUET_KEY not in b.columns or PARQUET_KEY not in n.columns:
        raise PublishError(f"parquet 缺 `{PARQUET_KEY}` 欄，無法安全合併分支既有資料，中止（不覆寫以免丟資料）")
    for c in set(b.columns) & set(n.columns):
        if b[c].isna().all() or n[c].isna().all():
            continue
        if _dtype_group(b[c].dtype) != _dtype_group(n[c].dtype):
            raise PublishError(f"parquet 欄 `{c}` 型別衝突（分支 {b[c].dtype} vs 新輸出 {n[c].dtype}），中止")
    bd = pd.to_datetime(b[PARQUET_KEY]).dt.normalize()
    nd = pd.to_datetime(n[PARQUET_KEY]).dt.normalize()
    new_days = set(nd)
    rep = bd.isin(new_days).to_numpy()
    old_rep = b[rep]
    if log and rep.any():
        days = sorted({d.date().isoformat() for d in bd[rep]})
        log(f"  [union] 取代分支既有日期 {days}，共 {int(rep.sum())} 列")
    keys = [PARQUET_KEY] + (["sector"] if "sector" in b.columns and "sector" in n.columns else [])

    def _k(df, dates):
        parts = [dates.dt.strftime("%Y-%m-%d")] + [df[c].astype(str) for c in keys[1:]]
        return parts[0] if len(parts) == 1 else parts[0].str.cat(parts[1:], sep="|")

    n = n.copy()
    for c in b.columns:
        if c not in n.columns:  # D4：分支有而新輸出沒有的欄 → 保留（新列補缺值，可由下方同 key 舊值回填）
            col = pd.Series([None] * len(n), index=n.index, dtype=object)
            try:
                col = col.astype(b[c].dtype)
            except (TypeError, ValueError):
                pass
            n[c] = col
    if len(old_rep):
        old_lookup = old_rep.assign(_k=_k(old_rep, bd[rep])).drop_duplicates("_k", keep="last").set_index("_k")
        nk = _k(n, nd)
        if not nk.duplicated().any():
            filled = 0
            for c in n.columns:
                if c not in old_lookup.columns:
                    continue
                m = (n[c].isna() & nk.isin(old_lookup.index)).to_numpy()
                if m.any():
                    vals = old_lookup.loc[nk[m], c].to_numpy()
                    ok = ~pd.isna(vals)
                    if ok.any():
                        idx = n.index[m][ok]
                        n.loc[idx, c] = pd.Series(vals[ok], index=idx).astype(n[c].dtype, errors="ignore")
                        filled += int(ok.sum())
            if log and filled:
                log(f"  [union] 新列缺值而舊列有值 → 保留舊值 {filled} 格")
    out = pd.concat([b[~rep], n], ignore_index=True)
    out = out.loc[:, list(n.columns)]
    out = out.iloc[pd.to_datetime(out[PARQUET_KEY]).argsort(kind="stable")].reset_index(drop=True)
    buf = io.BytesIO()
    out.to_parquet(buf, index=False)
    return buf.getvalue()


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
                v = json.loads(data).get("fetched_at") if isinstance(json.loads(data), dict) else None
                if v:
                    found.append(str(v))
        except Exception:  # 只影響 PR 說明文字，不影響資料
            continue
    return max(found) if found else "n/a（資料檔內無 fetched_at）"


def build_pr_body(job: str, files: list[str], observation_date: str | None, fetched_at: str) -> str:
    listing = "\n".join(f"- `{p}`" for p in files)
    return (
        f"## 自動資料發布：{job}\n\n"
        "本 PR 由每日 cron 自動產生（`scripts/publish_data_pr.py`），內容為腳本實際抓取的資料增量。\n\n"
        "| 欄位 | 值 |\n|---|---|\n"
        f"| observation_date（資料觀測日） | {observation_date or 'n/a（未帶入）'} |\n"
        f"| fetched_at（抓取時間，取自資料檔） | {fetched_at} |\n"
        f"| published_at（來源發布時間） | {NA_PUBLISHED} |\n\n"
        f"### 變更檔\n{listing}\n\n"
        "**未經人工審閱不得合併。** 本 PR 未啟用 auto-merge；required check "
        "`ui2-browser-gate` 由 cron 對本分支 dispatch `pr-check.yml` 產生。\n"
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
    gh pr merge / gh api 含 protection。
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
        if cmd[1:2] == ["api"] and any("protection" in c for c in cmd):
            raise PublishError("禁止透過 gh api 動 branch protection")


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

    def head_bytes(self, path: str) -> bytes | None:
        r = self.git("show", f"HEAD:{path}", check=False, binary=True)
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


def publish(args, pub: Publisher, today: str | None = None) -> int:
    job = args.job
    branch = f"{BRANCH_PREFIX}{job}"
    paths = list(args.paths)
    today = today or _dt.datetime.now(_dt.timezone.utc).date().isoformat()

    changed = pub.detect(paths, args.force_add)
    if not changed:
        pub.log("無實質變更：--paths 下沒有任何變更檔，不開 PR。")
        return 0
    subst, noise = pub.classify(changed)
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
            pub.log(f"[dry-run] git fetch origin {branch} ; git checkout -B {branch} origin/{branch} ; git merge --no-edit origin/{BASE_BRANCH}")
        else:
            pub.log(f"[dry-run] git checkout -B {branch}")
        pub.log(f"[dry-run] {' '.join(add)} ; git commit -m {args.commit_msg!r} ; git push -u origin {branch}")
        pub.log(f"[dry-run] gh pr list --head {branch} --state open ; (無則) gh pr create --base {BASE_BRANCH} --head {branch} --title {title!r}")
        pub.log(f"[dry-run] gh workflow run {CHECK_WORKFLOW} --ref {branch}")
        return 0

    snapshot = {p: pub.worktree_bytes(p) for _, p in changed}  # 供 PR body 與套用
    pub.git("config", "--local", "user.name", BOT_NAME)
    pub.git("config", "--local", "user.email", BOT_EMAIL)

    if not remote_has:
        pub.git("checkout", "-B", branch)  # 工作樹變更隨身帶過去
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
            root = Path(pub.cwd or ".")
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
                    new = union_parquet_by_date(dst.read_bytes(), new, pub.log)
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(new)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        pub.run(add)
        if pub.git("diff", "--cached", "--quiet", check=False).rc != 0:
            pub.gitid("commit", "-m", args.commit_msg)
        head = pub.git("rev-parse", "HEAD").stdout.strip()
        remote_head = pub.git("rev-parse", f"origin/{branch}").stdout.strip()
        pushed = head != remote_head

    if pushed:
        pub.git("push", "-u", "origin", branch)
        pub.log(f"已推送分支 {branch}")
    else:
        pub.log(f"分支 {branch} 已含相同內容，不重複 push。")

    hint = ("分支已推送、PR/check 未建立；請檢查『Allow GitHub Actions to create and approve pull requests』"
            "設定與 actions: write 權限")
    created = False
    try:
        lst = pub.run(["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "number"])
        if json.loads(lst.stdout or "[]"):
            pub.log("已有開啟中的 PR，不重複建立（僅更新分支）。")
        else:
            body = build_pr_body(job, files, args.observation_date,
                                 collect_fetched_at({p: b for p, b in snapshot.items() if b is not None}))
            created = True
            pub.run(["gh", "pr", "create", "--base", BASE_BRANCH, "--head", branch, "--title", title, "--body", body])
            pub.log("已建立 PR。")
        if pushed or created:  # 新建 PR 即使沒有新 push 也要有 required check
            pub.run(["gh", "workflow", "run", CHECK_WORKFLOW, "--ref", branch])
            pub.log(f"已 dispatch {CHECK_WORKFLOW}（--ref {branch}）以產生 required check。")
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
