"""tests 共用：只用 git **已追蹤**的檔案當語料（SEC-r26，批 S4；2026-10-01）。

為什麼：語料測試（`_ui_corpus`／`_secret_corpus`／`_tracked_md_lines` …）原本用 `glob`／`rglob` 掃工作目錄，
**未追蹤檔**（別組留下的草稿、`docs/` 底下的暫存筆記、被 `.gitignore` 擋掉的 `temp/` …）也會混進語料 ——
本機與 CI 結果可能不同。

怎麼做：⛔ 不呼叫 git（`tests/test_zz_test_portability.py` 禁止外部指令）。改為**直接讀 git 的索引檔**
（`.git/index`；worktree 的 `.git` 是一行 `gitdir: …` 的檔案，照著找），取出其中的路徑 ＝ `git ls-files` 的集合
（含已暫存未 commit 的檔；衝突的多個 stage 只算一次）。

讀不了時回傳 `None`，呼叫端退回原本的檔案系統掃描（行為同修前，不會比修前更糟）：
沒有 `.git`（例：`git archive` 解開的副本）、索引版本不是 2／3／4、SHA-256 物件格式、split index（`link` 擴充）、
sparse index（目錄型的項目）、檔案截斷。⚠️ 這些情形本機與 CI 仍可能不同 —— 退回是為了不讓測試在非 git 環境直接壞掉。
"""
from __future__ import annotations

import functools
import pathlib

_SHA1_LEN = 20
_ENTRY_FIXED = 40 + _SHA1_LEN + 2          # ctime..size（40）＋ 物件 id（20）＋ flags（2）
_EXTENDED = 0x4000
_NAME_MASK = 0x0FFF
_DIR_MODE = 0o040000


def _git_dir(root: pathlib.Path) -> pathlib.Path | None:
    dot = root / ".git"
    if dot.is_dir():
        return dot
    if dot.is_file():
        line = dot.read_text(encoding="utf-8").strip()
        if line.startswith("gitdir:"):
            p = pathlib.Path(line[len("gitdir:"):].strip())
            return p if p.is_absolute() else (root / p)
    return None


def _common_dir(git_dir: pathlib.Path) -> pathlib.Path:
    f = git_dir / "commondir"
    if f.is_file():
        p = pathlib.Path(f.read_text(encoding="utf-8").strip())
        return p if p.is_absolute() else (git_dir / p)
    return git_dir


def _sha256_repo(git_dir: pathlib.Path) -> bool:
    cfg = _common_dir(git_dir) / "config"
    if not cfg.is_file():
        return False
    text = cfg.read_text(encoding="utf-8", errors="replace").lower().replace(" ", "").replace("\t", "")
    return "objectformat=sha256" in text


def _varint(b: bytes, i: int) -> tuple[int, int]:
    """git 索引 v4 的位移整數（`offset` 編碼，與 pack 的 varint 不同）。"""
    c = b[i]
    i += 1
    val = c & 0x7F
    while c & 0x80:
        c = b[i]
        i += 1
        val = ((val + 1) << 7) | (c & 0x7F)
    return val, i


def parse_index(data: bytes) -> frozenset[str] | None:
    """解析索引檔內容 → 追蹤中的路徑（POSIX 相對路徑）；格式不支援或截斷 → `None`。"""
    try:
        if data[:4] != b"DIRC":
            return None
        ver = int.from_bytes(data[4:8], "big")
        n = int.from_bytes(data[8:12], "big")
        if ver not in (2, 3, 4):
            return None
        i, prev, out = 12, b"", set()
        for _ in range(n):
            start = i
            mode = int.from_bytes(data[i + 24:i + 28], "big")
            flags = int.from_bytes(data[i + _ENTRY_FIXED - 2:i + _ENTRY_FIXED], "big")
            i += _ENTRY_FIXED
            if flags & _EXTENDED:
                if ver < 3:
                    return None
                i += 2
            if ver == 4:
                strip, i = _varint(data, i)
                end = data.index(b"\0", i)
                if strip > len(prev):
                    return None
                path = prev[:len(prev) - strip] + data[i:end]
                i = end + 1
            else:
                end = data.index(b"\0", i)
                path = data[i:end]
                if (flags & _NAME_MASK) != _NAME_MASK and len(path) != (flags & _NAME_MASK):
                    return None
                #: 項目以 1～8 個 NUL 補到 8 的倍數（從項目開頭算）。
                i = start + ((end - start) // 8 + 1) * 8
            if mode & 0o170000 == _DIR_MODE:
                return None                     # sparse index 的目錄項目：底下的檔案不在索引裡
            prev = path
            out.add(path.decode("utf-8", errors="surrogateescape"))
        #: 擴充區：split index（`link`）的路徑一部分在共用索引 → 不支援。
        while i + 8 <= len(data) - _SHA1_LEN:
            sig, size = data[i:i + 4], int.from_bytes(data[i + 4:i + 8], "big")
            if sig == b"link":
                return None
            i += 8 + size
        return frozenset(out)
    except (IndexError, ValueError):
        return None


@functools.lru_cache(maxsize=4)
def tracked_paths(root: pathlib.Path) -> frozenset[str] | None:
    """`root` 這個 checkout 的追蹤檔集合（相對 `root` 的 POSIX 路徑）；讀不了 → `None`（呼叫端退回檔案系統掃描）。"""
    git_dir = _git_dir(root)
    if git_dir is None or _sha256_repo(git_dir):
        return None
    idx = git_dir / "index"
    if not idx.is_file():
        return None
    return parse_index(idx.read_bytes())


def only_tracked(root: pathlib.Path, files) -> list[pathlib.Path]:
    """`files` 裡留下 git 追蹤中的檔案（保留順序）；追蹤清單讀不了 → 原樣全留（同修前）。"""
    files = list(files)
    tracked = tracked_paths(root)
    if tracked is None:
        return files
    base = root.absolute()
    out = []
    for f in files:
        #: 以字面路徑比（⛔ 不 `resolve()`：連結指到 repo 外會丟 `ValueError`）；不在 `root` 底下 → 不在它的索引裡。
        try:
            rel = f.absolute().relative_to(base).as_posix()
        except ValueError:
            continue
        if rel in tracked:
            out.append(f)
    return out
