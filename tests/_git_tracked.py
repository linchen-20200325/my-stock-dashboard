"""tests 共用：只用 git **已追蹤**的檔案當語料（SEC-r26，批 S4；2026-10-01）。

為什麼：語料測試（`_ui_corpus`／`_secret_corpus`／`_tracked_md_lines` …）原本用 `glob`／`rglob` 掃工作目錄，
**未追蹤檔**（別組留下的草稿、`docs/` 底下的暫存筆記、被 `.gitignore` 擋掉的 `temp/` …）也會混進語料 ——
本機與 CI 結果可能不同。

怎麼做：⛔ 不呼叫 git（`tests/test_zz_test_portability.py` 禁止外部指令）。改為**直接讀 git 的索引檔**
（`.git/index`；worktree 的 `.git` 是一行 `gitdir: …` 的檔案，照著找），取出其中的路徑 ＝ `git ls-files` 的集合
（含已暫存未 commit 的檔；衝突的多個 stage 只算一次）。

**格式不支援**時 `parse_index`／`tracked_paths` 回傳 `None`；~~呼叫端退回原本的檔案系統掃描~~（批 S4 QA 第 1 組
後改為 `only_tracked` 一律丟 `IndexUnavailable`，見該函式說明 —— 退回會把未追蹤檔安靜地帶回語料）。不支援的情形：
沒有 `.git`（例：`git archive` 解開的副本）、沒有索引檔、索引版本不是 2／3／4、SHA-256 物件格式、
split index（`link` 擴充）、sparse index（目錄型的項目）。

批 S4 QA（SEC-r26 修正，2026-10-01）：**格式壞掉**一律 `raise IndexCorrupt`（⛔ 不退回、⛔ 不回傳殘缺集合）——
原本不核對檔尾 SHA-1、照單全收項目數：項目數改成 0 得到空集合、改小得到殘缺集合、路徑翻一個位元得到錯的路徑，
語料測試跟著**空轉通過**。現在核對：簽章 `DIRC`、檔尾 SHA-1、
項目數與實際內容（項目之後只能剛好是若干完整擴充區＋檔尾）、路徑依 (路徑, stage) 嚴格遞增（git 的排序）、截斷。
~~（`index.skipHash` 開著時 git 寫全 0，僅此時接受全 0）~~ ← 批 S6（SEC-r30，2026-10-02）改，有意識的更正、不是漏刪：
原本只讀 repo 的 `.git/config` 判 skipHash，全域設定（`~/.gitconfig`）、`git -c index.skipHash=true …`、
`include` 進來的設定都看不到 → 合法索引被誤判 `IndexCorrupt`。現在**檔尾全 0 一律視為「沒有雜湊」**、改靠結構核對
（與 git 自己相同：git 讀索引核對雜湊時，檔尾全 0 就跳過核對、不看設定 —— 2026-10-02 實測 git 2.43：
沒有任何 skipHash 設定的 repo，把索引檔尾改成全 0，`git fsck` 不報錯；改成非 0 的錯值則報 `bad index file sha1 signature`）。
檔尾全 0 時無法以雜湊驗證，故另外從嚴：版本不是 2／3／4 → `IndexCorrupt`（有雜湊時才當「格式不支援」）。
⚠️ 殘餘風險（據實揭露）：檔尾全 0、**且**結構剛好仍完全合法的內容損壞（例：路徑裡某個位元翻轉、長度不變）
認不出來 —— 與 git 本身相同，沒有雜湊就沒有逐位元驗證。v2／v3 每一項的名字各自獨立，一個位元翻轉最多錯 1 個路徑；
**v4 不是**：名字以前綴壓縮（每一項沿用上一項的前段），一個位元翻轉若落在某一項的名字或前綴刪除數裡、而長度與排序
仍合法，後面沿用它的路徑會一起錯（批 S6 QA 實測：加上 v4 名長核對之後，最壞仍約 470 個路徑；git 同樣接受這些檔）。
項目數不變，`min_tracked` 抓不到。批 S6 QA（R30-v4）起 v4 也核對 flags 記載的名長（原本只核對 v2／v3）。
批 S6（SEC-r30）：split index 的「被取代項目」路徑長為 0（git 寫入時剝掉名字），原本先撞上路徑檢查、誤報
`IndexCorrupt`「路徑不合法 b''」；現在名字為空的項目先記下，讀完擴充區看到 `link` → 格式不支援（`IndexUnavailable`
訊息寫明 split index）；沒有 `link` 卻有空名字 → 照舊 `IndexCorrupt`。sparse／其他必要擴充同樣讀完全檔才判「不支援」
（⛔ 不再在中途回傳，後面壞掉的部分也要核對）。
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


class IndexUnavailable(IndexCorrupt):
    """讀不到追蹤清單（格式不支援或不是 git checkout）；`only_tracked` 一律丟這個，⛔ 不退回檔案系統掃描。"""


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
    """解析索引檔內容 → 追蹤中的路徑（POSIX 相對路徑）。

    格式**不支援**（版本、split index、sparse index）→ `None`；內容**壞掉**（簽章、檔尾 SHA-1、項目數對不上、
    排序、截斷）→ `raise IndexCorrupt`。合法的空索引 → `frozenset()`（要不要接受空集合由呼叫端決定，見 `only_tracked`）。
    檔尾全 0 ＝ 沒有雜湊（`index.skipHash`），只靠結構核對（理由見檔頭）。不支援的原因見 `_parse_index`。
    """
    return _parse_index(data)[0]


def _parse_index(data: bytes) -> tuple[frozenset[str] | None, str]:
    """`parse_index` 的本體：回傳（路徑集合或 `None`, 不支援的原因；支援時為空字串）。"""
    if len(data) < 12 + _SHA1_LEN:
        raise IndexCorrupt(f"索引檔只有 {len(data)} 位元組（截斷）")
    if data[:4] != b"DIRC":
        raise IndexCorrupt(f"索引檔簽章不是 DIRC：{data[:4]!r}")
    body, trailer = data[:-_SHA1_LEN], data[-_SHA1_LEN:]
    no_hash = trailer == bytes(_SHA1_LEN)
    if not no_hash and hashlib.sha1(body).digest() != trailer:
        raise IndexCorrupt("索引檔檔尾 SHA-1 對不上（內容被改過或截斷）")
    ver = int.from_bytes(data[4:8], "big")
    n = int.from_bytes(data[8:12], "big")
    if ver not in (2, 3, 4):
        if no_hash:
            raise IndexCorrupt(f"索引版本 {ver} 不是 2／3／4，且檔尾全 0（沒有雜湊可驗證）→ 視為壞掉")
        return None, f"索引版本 {ver} 不支援"
    end_entries = len(body)
    i, prev, prev_key, out = 12, b"", None, set()
    #: 不支援的原因（讀完全檔才回傳 —— 後面壞掉的部分照樣核對）；第一個空名字項目的編號（split index 才合法）。
    unsupported, empty_at = "", None
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
                #: 批 S6 QA（R30-v4）：v4 同樣核對 flags 記載的名長（同 git：不符即「索引項目格式不明」）—— 不核對時，
                #: 檔尾全 0 下一個位元翻轉就能讓後面數百個路徑經前綴壓縮全錯、項目數卻不變（min_tracked 抓不到）。
                if (flags & _NAME_MASK) != _NAME_MASK and len(path) != (flags & _NAME_MASK):
                    raise IndexCorrupt(f"第 {k} 項：路徑長 {len(path)} 與 flags 記載 {flags & _NAME_MASK} 不符（v4）")
            else:
                nul = data.index(b"\0", i, end_entries)
                path = data[i:nul]
                if (flags & _NAME_MASK) != _NAME_MASK and len(path) != (flags & _NAME_MASK):
                    raise IndexCorrupt(f"第 {k} 項：路徑長 {len(path)} 與 flags 記載 {flags & _NAME_MASK} 不符")
                #: 項目以 1～8 個 NUL 補到 8 的倍數（從項目開頭算）。
                i = start + ((nul - start) // 8 + 1) * 8
                if i > end_entries or data[nul:i].strip(b"\0"):
                    raise IndexCorrupt(f"第 {k} 項：補齊的 NUL 不完整")
            #: 批 S7（S6-n4）：flags 名長飽和（0xFFF）只在路徑 ≥ 4095 位元組時才會由 git 寫出（`ce_namelen >= CE_NAMEMASK`）；
            #: 路徑較短卻記 0xFFF ＝ 位元翻轉／偽造 → 同「名長不符」（v2／v3／v4 一律；檔尾全 0 時這是唯一的核對）。
            if (flags & _NAME_MASK) == _NAME_MASK and len(path) < _NAME_MASK:
                raise IndexCorrupt(f"第 {k} 項：flags 名長飽和（0xFFF）但路徑只有 {len(path)} 位元組（應 ≥ {_NAME_MASK}）")
            if not path:
                #: split index 的「被取代項目」：git 寫入時剝掉名字（長度 0）—— 先記下，讀完擴充區才知道合不合法。
                if empty_at is None:
                    empty_at = k
                prev = path                             # v4 的前綴以「上一項寫出的名字」為準（剝掉後是空）
                continue
            if path.startswith(b"/") or b"\0" in path:
                raise IndexCorrupt(f"第 {k} 項：路徑不合法 {path[:80]!r}")
            key = (path, (flags >> _STAGE_SHIFT) & 0x3)
            if prev_key is not None and key <= prev_key:
                raise IndexCorrupt(f"第 {k} 項：路徑未依 git 的排序嚴格遞增（{path[:80]!r}）")
            if mode & 0o170000 == _DIR_MODE:
                unsupported = unsupported or "sparse index（目錄型的項目）"  # 底下的檔案不在索引裡
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
            if size < _SHA1_LEN:
                raise IndexCorrupt(f"split index 的 link 擴充只有 {size} 位元組（至少 {_SHA1_LEN}）")
            #: split index：路徑一部分在共用索引（`sharedindex.<sha>`）→ 不支援。
            unsupported = "split index（link 擴充；路徑一部分在共用索引 sharedindex.*）"
        elif sig[:1].islower():
            unsupported = unsupported or f"看不懂的必要擴充 {sig!r}"  # git 自己也會拒讀
        i += 8 + size
    if empty_at is not None and not unsupported.startswith("split index"):
        raise IndexCorrupt(f"第 {empty_at} 項：路徑不合法 b''")
    if unsupported:
        return None, unsupported
    return frozenset(out), ""


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


def _unavailable_reason(root: pathlib.Path) -> str:
    """`tracked_paths` 回 `None` 的原因（只供錯誤訊息；不快取）。"""
    git_dir = _git_dir(root)
    if git_dir is None:
        return "沒有 .git"
    if _sha256_repo(git_dir):
        return "SHA-256 repo"
    idx = git_dir / "index"
    if not idx.is_file():
        return "沒有索引檔"
    try:
        why = _parse_index(idx.read_bytes())[1]
    except IndexCorrupt as e:
        return f"索引檔壞掉：{e}"
    return why or "索引版本不支援／split 或 sparse index"


def only_tracked(root: pathlib.Path, files, *, min_tracked: int = 1, min_kept: int = 0) -> list[pathlib.Path]:
    """`files` 裡留下 git 追蹤中的檔案（保留順序）。追蹤清單讀不了（`tracked_paths` 回 `None`）→ `IndexUnavailable`。

    批 S4 QA 第 1 組（2026-10-01）決定：`None` ⛔ 不再退回檔案系統掃描 —— 退回會把 SEC-r26 要排除的未追蹤檔帶回語料，
    而且是安靜地帶回。CI（`actions/checkout@v4`）與一般 clone／worktree 都是 v2～v4、非 split／sparse 的索引，讀得到；
    讀不到的環境（`git archive` 副本、split／sparse index、SHA-256 repo）跑這些語料測試會**失敗並寫明原因**，
    要跑請改用一般 checkout。

    ⛔ 不空轉：追蹤集合少於 `min_tracked`（預設 1 ＝ 空集合就失敗）、或留下的檔案少於 `min_kept` → `IndexCorrupt`。
    語料呼叫端傳 repo 規模的下限（見 `REPO_MIN_TRACKED`）。
    """
    files = list(files)
    tracked = tracked_paths(root)
    if tracked is None:
        raise IndexUnavailable(f"{root}：讀不到 git 追蹤清單（{_unavailable_reason(root)}）—— ⛔ 不退回檔案系統掃描"
                               "（會帶回未追蹤檔）；請在一般 git checkout 裡跑（split index 可用 "
                               "`git update-index --no-split-index` 關掉）")
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
