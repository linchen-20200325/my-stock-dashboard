"""tests 共用：只用 git **已追蹤**的檔案當語料（SEC-r26，批 S4；2026-10-01）。

為什麼：語料測試（`_ui_corpus`／`_secret_corpus`／`_tracked_md_lines` …）原本用 `glob`／`rglob` 掃工作目錄，
**未追蹤檔**（別組留下的草稿、`docs/` 底下的暫存筆記、被 `.gitignore` 擋掉的 `temp/` …）也會混進語料 ——
本機與 CI 結果可能不同。

怎麼做：⛔ 不呼叫 git（`tests/test_zz_test_portability.py` 禁止外部指令）。改為**直接讀 git 的索引檔**
（`.git/index`；worktree 的 `.git` 是一行 `gitdir: …` 的檔案，照著找），取出其中的路徑 ＝ `git ls-files` 的集合
（含已暫存未 commit 的檔；衝突的多個 stage 只算一次）。

**格式不支援**時回傳 `None`，呼叫端退回原本的檔案系統掃描（行為同修前，不會比修前更糟）：
沒有 `.git`（例：`git archive` 解開的副本）、沒有索引檔、索引版本不是 2／3／4、SHA-256 物件格式、
split index（`link` 擴充）、sparse index（目錄型的項目）。⚠️ 這些情形本機與 CI 仍可能不同 —— 退回是為了不讓測試在
非 git 環境直接壞掉。

批 S4 QA（SEC-r26 修正，2026-10-01）：**格式壞掉**一律 `raise IndexCorrupt`（⛔ 不退回、⛔ 不回傳殘缺集合）——
原本不核對檔尾 SHA-1、照單全收項目數：項目數改成 0 得到空集合、改小得到殘缺集合、路徑翻一個位元得到錯的路徑，
語料測試跟著**空轉通過**。現在核對：簽章 `DIRC`、檔尾 SHA-1（`index.skipHash` 開著時 git 寫全 0，僅此時接受全 0）、
項目數與實際內容（項目之後只能剛好是若干完整擴充區＋檔尾）、路徑依 (路徑, stage) 嚴格遞增（git 的排序）、截斷。
`.git` 檔／`commondir` 不是 UTF-8 → 同樣 `IndexCorrupt`（訊息寫明是哪個檔）。
另外 `only_tracked` 的追蹤集合為空、或少於呼叫端給的下限 → `IndexCorrupt`（語料測試 ⛔ 不得空轉）。
"""
from __future__ import annotations

import functools
import hashlib
import pathlib

_SHA1_LEN = 20
_ENTRY_FIXED = 40 + _SHA1_LEN + 2          # ctime..size（40）＋ 物件 id（20）＋ flags（2）
_EXTENDED = 0x4000
_NAME_MASK = 0x0FFF
_DIR_MODE = 0o040000
_STAGE_SHIFT = 12
#: 本 repo 的語料下限（實測 2026-10-01：追蹤檔 938 個）—— 低於此值代表索引讀錯，語料測試要失敗而不是空轉。
REPO_MIN_TRACKED = 500


class IndexCorrupt(ValueError):
    """索引檔／`.git` 指標檔內容壞掉（與「格式不支援 → `None`」不同：壞掉一律大聲失敗）。"""


def _read_utf8(f: pathlib.Path) -> str:
    raw = f.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise IndexCorrupt(f"{f} 不是 UTF-8（第 {e.start} 位元組）：無法判讀 git 目錄位置") from e


def _git_dir(root: pathlib.Path) -> pathlib.Path | None:
    dot = root / ".git"
    if dot.is_dir():
        return dot
    if dot.is_file():
        line = _read_utf8(dot).strip()
        if line.startswith("gitdir:"):
            p = pathlib.Path(line[len("gitdir:"):].strip())
            return p if p.is_absolute() else (root / p)
    return None


def _common_dir(git_dir: pathlib.Path) -> pathlib.Path:
    f = git_dir / "commondir"
    if f.is_file():
        p = pathlib.Path(_read_utf8(f).strip())
        return p if p.is_absolute() else (git_dir / p)
    return git_dir


def _config_text(git_dir: pathlib.Path) -> str:
    cfg = _common_dir(git_dir) / "config"
    if not cfg.is_file():
        return ""
    return cfg.read_text(encoding="utf-8", errors="replace").lower().replace(" ", "").replace("\t", "")


def _sha256_repo(git_dir: pathlib.Path) -> bool:
    return "objectformat=sha256" in _config_text(git_dir)


def _skip_hash(git_dir: pathlib.Path) -> bool:
    """`index.skipHash`（或隱含它的 `feature.manyFiles`）開著 → git 寫的檔尾是全 0。粗略判讀：有出現 `=true` 就算。"""
    text = _config_text(git_dir)
    return "skiphash=true" in text or "manyfiles=true" in text


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


def parse_index(data: bytes, *, allow_zero_trailer: bool = False) -> frozenset[str] | None:
    """解析索引檔內容 → 追蹤中的路徑（POSIX 相對路徑）。

    格式**不支援**（版本、split index、sparse index）→ `None`；內容**壞掉**（簽章、檔尾 SHA-1、項目數對不上、
    排序、截斷）→ `raise IndexCorrupt`。合法的空索引 → `frozenset()`（要不要接受空集合由呼叫端決定，見 `only_tracked`）。
    """
    if len(data) < 12 + _SHA1_LEN:
        raise IndexCorrupt(f"索引檔只有 {len(data)} 位元組（截斷）")
    if data[:4] != b"DIRC":
        raise IndexCorrupt(f"索引檔簽章不是 DIRC：{data[:4]!r}")
    body, trailer = data[:-_SHA1_LEN], data[-_SHA1_LEN:]
    if hashlib.sha1(body).digest() != trailer and not (allow_zero_trailer and trailer == bytes(_SHA1_LEN)):
        raise IndexCorrupt("索引檔檔尾 SHA-1 對不上（內容被改過或截斷）")
    ver = int.from_bytes(data[4:8], "big")
    n = int.from_bytes(data[8:12], "big")
    if ver not in (2, 3, 4):
        return None
    end_entries = len(body)
    i, prev, prev_key, out = 12, b"", None, set()
    try:
        for k in range(n):
            start = i
            if i + _ENTRY_FIXED > end_entries:
                raise IndexCorrupt(f"第 {k} 項超出檔尾（宣告 {n} 項）")
            mode = int.from_bytes(data[i + 24:i + 28], "big")
            flags = int.from_bytes(data[i + _ENTRY_FIXED - 2:i + _ENTRY_FIXED], "big")
            i += _ENTRY_FIXED
            if flags & _EXTENDED:
                if ver < 3:
                    raise IndexCorrupt(f"第 {k} 項：v{ver} 索引不該有 extended flag")
                i += 2
            if ver == 4:
                strip, i = _varint(data, i)
                nul = data.index(b"\0", i, end_entries)
                if strip > len(prev):
                    raise IndexCorrupt(f"第 {k} 項：前綴刪除 {strip} 超過前一路徑長 {len(prev)}")
                path = prev[:len(prev) - strip] + data[i:nul]
                i = nul + 1
            else:
                nul = data.index(b"\0", i, end_entries)
                path = data[i:nul]
                if (flags & _NAME_MASK) != _NAME_MASK and len(path) != (flags & _NAME_MASK):
                    raise IndexCorrupt(f"第 {k} 項：路徑長 {len(path)} 與 flags 記載 {flags & _NAME_MASK} 不符")
                #: 項目以 1～8 個 NUL 補到 8 的倍數（從項目開頭算）。
                i = start + ((nul - start) // 8 + 1) * 8
                if i > end_entries or data[nul:i].strip(b"\0"):
                    raise IndexCorrupt(f"第 {k} 項：補齊的 NUL 不完整")
            if not path or path.startswith(b"/") or b"\0" in path:
                raise IndexCorrupt(f"第 {k} 項：路徑不合法 {path[:80]!r}")
            key = (path, (flags >> _STAGE_SHIFT) & 0x3)
            if prev_key is not None and key <= prev_key:
                raise IndexCorrupt(f"第 {k} 項：路徑未依 git 的排序嚴格遞增（{path[:80]!r}）")
            if mode & 0o170000 == _DIR_MODE:
                return None                     # sparse index 的目錄項目：底下的檔案不在索引裡
            prev, prev_key = path, key
            out.add(path.decode("utf-8", errors="surrogateescape"))
    except (IndexError, ValueError) as e:
        if isinstance(e, IndexCorrupt):
            raise
        raise IndexCorrupt(f"索引檔截斷或項目壞掉（宣告 {n} 項）：{e}") from e
    #: 項目之後只能剛好是若干完整擴充區，再接檔尾 —— 項目數與實際內容對不上（改小 → 剩下的項目被當擴充區）就在這裡抓到。
    while i < end_entries:
        if i + 8 > end_entries:
            raise IndexCorrupt(f"擴充區標頭截斷（宣告 {n} 項；項目後剩 {end_entries - i} 位元組）")
        sig, size = data[i:i + 4], int.from_bytes(data[i + 4:i + 8], "big")
        if not all(0x41 <= c <= 0x5A or 0x61 <= c <= 0x7A for c in sig):
            raise IndexCorrupt(f"擴充區簽章不合法 {sig!r}（宣告 {n} 項 → 項目數與內容對不上？）")
        if i + 8 + size > end_entries:
            raise IndexCorrupt(f"擴充區 {sig!r} 長度 {size} 超出檔尾")
        if sig == b"link":
            return None                         # split index：路徑一部分在共用索引 → 不支援
        if sig[:1].islower():
            return None                         # 其他必要擴充：看不懂 → 不支援（git 自己也會拒讀）
        i += 8 + size
    return frozenset(out)


@functools.lru_cache(maxsize=4)
def tracked_paths(root: pathlib.Path) -> frozenset[str] | None:
    """`root` 這個 checkout 的追蹤檔集合（相對 `root` 的 POSIX 路徑）；讀不了 → `None`（呼叫端退回檔案系統掃描）。"""
    git_dir = _git_dir(root)
    if git_dir is None or _sha256_repo(git_dir):
        return None
    idx = git_dir / "index"
    if not idx.is_file():
        return None
    return parse_index(idx.read_bytes(), allow_zero_trailer=_skip_hash(git_dir))


def only_tracked(root: pathlib.Path, files, *, min_tracked: int = 1, min_kept: int = 0) -> list[pathlib.Path]:
    """`files` 裡留下 git 追蹤中的檔案（保留順序）；追蹤清單格式不支援 → 原樣全留（同修前）。

    ⛔ 不空轉：追蹤集合少於 `min_tracked`（預設 1 ＝ 空集合就失敗）、或留下的檔案少於 `min_kept` → `IndexCorrupt`。
    語料呼叫端傳 repo 規模的下限（見 `REPO_MIN_TRACKED`）。
    """
    files = list(files)
    tracked = tracked_paths(root)
    if tracked is None:
        if len(files) < min_kept:
            raise IndexCorrupt(f"{root}：語料只有 {len(files)} 個檔，少於下限 {min_kept}")
        return files
    if len(tracked) < max(min_tracked, 1):
        raise IndexCorrupt(f"{root}：索引只有 {len(tracked)} 個追蹤檔，少於下限 {max(min_tracked, 1)}（語料不得空轉）")
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
    if len(out) < min_kept:
        raise IndexCorrupt(f"{root}：只留下 {len(out)} 個追蹤檔，少於下限 {min_kept}（語料不得空轉）")
    return out
