"""`src/ui/views/**` 的**通用**全稱句守衛 —— 未經驗證的「全站唯一」一律紅燈。

═══ 這支存在的理由（2026-09-07，一天之內三句全假）═════════════════════
`src/ui/views/` 底下印給使用者看的「全站唯一」被獨立稽核逐句實測，**三句全假**：

  1. 頁4 卡面寫「**全站唯一**乘法點」 → 實測全站**三處**乘 `SHARES_PER_LOT`
     （`portfolio_deep_service` / `dividend_station_service` / `compute.sector_flow`）。
  2. 頁4 卡面寫「**全站唯一**的建議持股 SSOT」 → 實測**至少 4 條活線**
     各自算持股水位，且都沒進到那道 `min()` 仲裁裡。
  3. 頁1 位階卡標題寫「市場位階（**全站唯一出處**）」 → 實測**至少 4 處**獨立判讀，
     其中 `tabs/macro/section_cross_ai.py` 那張卡的標題字面就叫「① 目前總經位階」。

三句都已逐一修掉，也各有專屬守衛：
  · `tests/test_p04_hold_view.py::TestTheLotToShareClaimIsMeasurable`
  · `tests/test_p04_hold_allocation_ssot_claim.py::TestNoScreenTextClaimsTheOnlyWay`
  · `tests/test_p01_today_view.py::TestNoGlobalUniquenessClaim`

⛔ **但那三支只擋各自那一句。** 下一個人在第六頁寫**第四句**一樣的全稱句時，
沒有任何機制會擋 —— 三支專屬守衛全是綠的，因為它們根本沒在看那一頁。
**本檔就是要擋那個**：不是再修一個實例，是把「未經驗證的全稱句」這個**類別**釘住。

對照 `CLAUDE.md §-2` 規則 6 的實證與 §1：
**沒查證的宣稱比沒有宣稱更危險** —— 它印在使用者臉上，而且下一個人會拿它當前提蓋下去。

═══ 判準：白名單登記制，不是啟發式 ═══════════════════════════════════
掃 `src/ui/views/**/*.py`，命中全稱關鍵詞的**每一行**都必須登記在下方 `REGISTRY`，
並標明它是哪一種：

  · `DISCLOSURE`（否定式揭露）—— 這一行是在**否認 / 撤回**一句全稱宣稱，
    或在記錄「舊文案這樣寫、實測為假」。修好之後的正確文案裡**故意保留**了大量
    這種字串（例：`⚠️ 這**不是**全站唯一的持股水位算法`），**它們是對的，不准判紅**。
  · `CLAIM`（主張）—— 這一行**真的在宣稱**某件事全站唯一。
    → **必須**填 `verified_by`，指向一支**會實測那個宣稱**的測試；
      那支測試不存在 → 本檔當場紅燈（`test_claim_entries_point_at_a_test_that_exists`）。

**未登記的新命中 → 紅燈。登記了卻已經對不上任何一行（過期登記）→ 也紅燈。**

⚠️ **為什麼是登記制，不是「附近有沒有『不是』兩個字」這種啟發式**（重點，別改回去）：
  1. **啟發式擋不住換句話說的人。** `不是全站唯一` / `不等於全站唯一` / `≠ 全站唯一`
     可以無限長出新寫法（`稱不上全站唯一`、`並非全站唯一`、`全站唯一？並沒有`…），
     而只要漏掉一種，守衛就靜靜地放行 —— 這正是本檔要防的失效模式的**同一個病**。
  2. **啟發式方向也錯。** 「附近有『不是』」是一個**可以被隨手滿足**的條件：
     下一個人只要在真主張旁邊寫一句「這不是隨便講的」就綠了。
  3. **登記制強迫做那件真正該做的事**：**逐句判讀一次**，而且把判讀結果留成
     可被下一個人複查的白紙黑字（`why` 欄）。對照 `CLAUDE.md §8.2.A.0` 規則 3 ——
     清單要由測試強制，「漏登 = CI 紅燈」而不是「漏登 = 沒人發現」。
  4. **不留 pragma 逃生口**（本檔刻意**沒有** `# xxx-ok` 行尾豁免）：留一個
     行尾註解就能免登記的門，等於留下 `CLAUDE.md §-2` 規則 6 點名的那種
     「可被引用來合理化的正當條文」—— **留但書等於留引用點**。要免判就去登記，
     登記要寫理由，理由會被下一個人讀到。

═══ 怎麼加一筆新登記 ═════════════════════════════════════════════════
1. 先問自己：**我這一行是在「宣稱」還是在「否認」？**
   · 在**否認 / 記錄舊文案為假** → `kind=DISCLOSURE`，`why` 寫清楚它在否認什麼。
   · 在**宣稱** → **先停手**。依 `CLAUDE.md §-2` 規則 6，全稱句要嘛有第二組實測、
     要嘛就別寫。真的要寫，就先寫一支**會去量**的測試（像
     `_lot_multiplication_sites()` 那樣**現場掃 repo**，不要抄名單），
     再回來登 `kind=CLAIM` + `verified_by="tests/檔.py::Class::test_名"`。
2. `snippet` 填**正規化後**該行的一段穩定特徵（≥ 10 字），**不要填行號** ——
   行號在任何一次重構後就失效，而重構不會觸發本清單更新
   （`CLAUDE.md §8.2.A.0` 規則 1：行號是「保證會過期的資訊」）。
   本檔寫作當下 `page_hold.py` 正被另一組同時編輯，實測 6 分鐘內行號就漂了 6 行。
3. 跑 `python -m pytest tests/test_views_no_unverified_universal_claims.py -q`。

═══ 正規化（`_normalize`）為什麼要做 ═════════════════════════════════
比對前先把**空白 / `*` / 反引號 / 各式引號括號**去掉，因為 Markdown 強調會把
關鍵詞切斷：`全站**唯一**` 與 `「全站」唯一` 用字面 grep 都掃不到，
但使用者眼睛看到的**一模一樣**。同一個理由讓 `全 repo 唯一` 與 `全repo唯一` 收斂成一形。
（實測：`page_today.py` 就有一句 `全 repo **沒有任何` 是這樣被切斷的。）

═══ 射程 ═════════════════════════════════════════════════════════════
**只掃 `src/ui/views/**`。** 不掃 `src/ui/tabs/` / `src/ui/etf/` —— 那是客戶明令
本批不得修改的舊版 Tab，掃了只會製造**改不了的紅燈**，而一支沒人能修綠的守衛
最後一定會被 `-k` 掉或被加白名單，等於自己把自己廢掉。
舊版 Tab 的平行判讀改用**揭露**處理（見 `page_today.REGIME_SCOPE_NOTE`）。

═══ fail loud（`CLAUDE.md` §1）═══════════════════════════════════════
views 目錄不見 / 一個 `.py` 都沒掃到 / 檔案讀不到 / `ast.parse` 失敗
→ 一律 `AssertionError`，**不 skip、不靜默通過**。
**一支永遠綠的守衛比沒有守衛更危險** —— 它會讓下一個人以為這件事有人在看。
本檔另有 `TestGuardItself`，用 tmp 檔實際證明它抓得到真違規、也不會被無關字眼騙。
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO = _TESTS_DIR.parent
_VIEWS_REL = "src/ui/views"

# ══════════════════════════════════════════════════════════════════════
# 關鍵詞（**正規化後**的形式：不含空白、不含 * 與引號）
# ══════════════════════════════════════════════════════════════════════
# 每一個都是「**全域範圍** + **唯一/僅/只有**」的組合 —— 也就是
# **要窮舉整個 repo 才能成立**的那種句子。單點可驗的說法（「本頁取自 X」、
# 「該檔唯一」）刻意**不**在列：那些讀一行 code 就能驗，不是本檔要防的東西。
#
# ⚠️ 每加一個關鍵詞，都要先想清楚它會怎麼誤判（逐項如下）：
#   · `全站唯一` / `全域唯一` / `全repo唯一` / `整個repo唯一` / `唯一出處` /
#     `唯一一處` —— 誤判情境：**否定式揭露**（「這不是全站唯一…」）。
#     → 由 `REGISTRY` 的 `DISCLOSURE` 登記處理，不用字面啟發式。
#   · `全站僅` / `全站只有` / `全域只有` / `整個repo只有` —— 誤判情境：
#     「全站僅供內部使用」這種**講用途、不講數量**的句子。
#     → 實測本 repo `src/ui/views/**` 0 命中（量測日 2026-09-07）；
#       真的長出來時同樣走登記，`why` 欄寫明它不是數量宣稱即可。
#
# ⛔ **刻意不收**的近義詞，以及為什麼（不是漏掉）：
#   · 裸 `唯一`：`src/ui/views/**` 有 71 處（量測日 2026-09-07），
#     絕大多數是**單點可驗**的「該檔唯一」「唯一一次」—— 收進來等於逼所有人
#     替可驗的句子登記，清單會迅速膨脹到沒人維護，反而稀釋真正危險的那幾句。
#   · `全站最大` 等**最高級**：那是另一個類別（比較級宣稱），判準不同，
#     混進來會讓 `DISCLOSURE`/`CLAIM` 兩分法失效。
#   · `全 repo 沒有任何` / `全 repo 只有 N 支` 等**否定式 / 計數式全稱句**：
#     它們**確實是同一族的問題**（`page_inspect.py` 就有一句自陳「不精確」，
#     `page_why.py` 有一句沒有任何測試在守的「全 repo 只有 9 支」），
#     但把它們收進來需要一併把那些宣稱**實測到底**，超出本檔射程。
#     **這是有意識的邊界，不是查漏** —— 見本檔結尾的「已知缺口」。
KEYWORDS: tuple[str, ...] = (
    "全站唯一",
    "全站僅",
    "全站只有",
    "全域唯一",
    "全域只有",
    "唯一出處",
    "唯一一處",
    "全repo唯一",
    "整個repo唯一",
    "整個repo只有",
)

# 正規化時要去掉的「雜訊」：空白 + Markdown 強調 + 各式引號括號。
# 只去這些 —— **不去** `，`。`（）` 等真標點，避免把不相干的兩句話黏成關鍵詞。
_NOISE = re.compile(r"""[\s*`「」『』【】“”‘’"']+""")


def _normalize(text: str) -> str:
    """把一行原文正規化成比對用的形式（去空白 / 去強調 / 去引號）。"""
    return _NOISE.sub("", text)


DISCLOSURE = "DISCLOSURE"
CLAIM = "CLAIM"
_KINDS = (DISCLOSURE, CLAIM)

#: `snippet` 的最短長度（正規化後字元數）。
#: 太短的 snippet（例如直接填 `全站唯一`）會變成**一筆蓋全部**的萬用登記，
#: 讓任何新句子都自動「已登記」—— 那等於把守衛關掉。
_MIN_SNIPPET = 10


@dataclass(frozen=True)
class Entry:
    """一筆登記。

    `path`     — repo 相對路徑（posix）。
    `snippet`  — **正規化後**該行的穩定特徵（不是行號）。比對時用
                 「snippet 出現在正規化後的整行裡」判定。
    `kind`     — `DISCLOSURE` 或 `CLAIM`。
    `why`      — 給下一個人看的判讀理由（**必填**，這是登記制的價值所在）。
    `verified_by` — 僅 `CLAIM` 需要：`"tests/檔.py::Class::test_名"`，
                 該符號必須真的存在，否則紅燈。
    """

    path: str
    snippet: str
    kind: str
    why: str
    verified_by: str = ""


# ══════════════════════════════════════════════════════════════════════
# 登記表（量測日 2026-09-07；現況 14 行命中，**全部** DISCLOSURE，0 CLAIM）
# ══════════════════════════════════════════════════════════════════════
# 「0 CLAIM」本身就是這批修完之後的正確狀態：三句全稱句都已被撤回，
# 留在畫面上的只剩**否認它們**的揭露。哪天真的有人要寫回一句 CLAIM，
# 他就得先寫出那支會去量的測試 —— 那正是本檔想造成的摩擦。
REGISTRY: tuple[Entry, ...] = (
    # ── page_hold.py：頁4 兩句（乘法點 / 建議持股 SSOT）的撤回與揭露 ──
    Entry(
        path="src/ui/views/page_hold.py",
        snippet="該檔唯一不是全站唯一",
        kind=DISCLOSURE,
        why="檔頭：明說「該檔唯一」與「全站唯一」是兩句話，別讀成同一句。"
            "這是在**限制**宣稱範圍，不是在宣稱。",
    ),
    Entry(
        path="src/ui/views/page_hold.py",
        snippet="這不是全站唯一的持股水位算法",
        kind=DISCLOSURE,
        why="`AllocationReadout` docstring ＋ 卡面 facts 的同一句否認"
            "（兩行都由本筆涵蓋）：明說本頁的 min() 仲裁**不是**全站唯一，"
            "並逐支點名沒進到仲裁裡的 4 條活線。",
    ),
    Entry(
        path="src/ui/views/page_hold.py",
        snippet="舊文案寫全站唯一的建議持股SSOT",
        kind=DISCLOSURE,
        why="程式碼註解：記錄「舊文案這樣寫、實測為假」的病史。"
            "刪掉這行不會讓畫面變好，只會讓下一個人不知道這裡踩過什麼。",
    ),
    Entry(
        path="src/ui/views/page_hold.py",
        snippet="只把全站唯一四個字刪掉不夠",
        kind=DISCLOSURE,
        why="程式碼註解：說明為什麼要**加一句否認**而不是只把字刪掉 —— "
            "字刪掉之後讀者仍會以為全站只有這一處。",
    ),
    Entry(
        path="src/ui/views/page_hold.py",
        snippet="不是全站唯一（實測：",
        kind=DISCLOSURE,
        why="`build_dividend_cash_card` docstring：明說「該檔唯一」的乘法點"
            "**不是**全站唯一，並列出另外兩支實測也在乘每張股數的模組。",
    ),
    Entry(
        path="src/ui/views/page_hold.py",
        snippet="卡面同時印出該檔唯一≠全站唯一",
        kind=DISCLOSURE,
        why="`build_dividend_cash_card` docstring：交代卡面**一定要印**那一列"
            "「該檔唯一 ≠ 全站唯一」，理由見檔頭。",
    ),
    Entry(
        path="src/ui/views/page_hold.py",
        snippet="舊文案寫全站唯一乘法點",
        kind=DISCLOSURE,
        why="程式碼註解：記錄「全站唯一乘法點」這句實測為假（全站至少三處）的病史。",
    ),
    Entry(
        path="src/ui/views/page_hold.py",
        snippet="只把全站兩個字刪掉不夠",
        kind=DISCLOSURE,
        why="程式碼註解：同上，說明為什麼刪字不夠、必須補一句明示否認。",
    ),
    Entry(
        path="src/ui/views/page_hold.py",
        snippet="該檔唯一不等於全站唯一",
        kind=DISCLOSURE,
        why="配息現金流卡的 facts 標題：印在使用者臉上的那一列否認句本身。",
    ),
    # ── page_today.py：頁1 位階卡「唯一出處」的撤回與揭露 ──
    Entry(
        path="src/ui/views/page_today.py",
        snippet="刻意不再宣稱本卡是本站位階的唯一出處",
        kind=DISCLOSURE,
        why="`REGIME_CARD_LABEL` 的註解：明說**刻意不再宣稱**，並說明改成"
            "單點可驗的說法（本卡的值取自哪一個契約）。",
    ),
    Entry(
        path="src/ui/views/page_today.py",
        snippet="本卡原標題那句唯一出處的宣稱是假的",
        kind=DISCLOSURE,
        why="`REGIME_SCOPE_NOTE` 的註解：記錄 2026-09-07 獨立稽核實測結果"
            "（那句是假的），並逐支點名 4 處未經仲裁的平行判讀。",
    ),
    Entry(
        path="src/ui/views/page_today.py",
        snippet="原文宣稱這是本站的唯一出處，改成單點可驗",
        kind=DISCLOSURE,
        why="`build_verdict_tiles` 內註解：FIX-4 的處置紀錄（原文宣稱 → 改成"
            "單點可驗的說法）。是病史，不是宣稱。",
    ),
    Entry(
        path="src/ui/views/page_today.py",
        snippet="整個repo只有這一處要窮舉才成立",
        kind=DISCLOSURE,
        why="同上註解的下一行：明說「整個 repo 只有這一處」要窮舉才成立、"
            "本組沒有驗過，依 `CLAUDE.md §-2` 規則 6 **就不寫**。"
            "這一行是在解釋**為什麼不寫**，正是本檔想推廣的行為。",
    ),
)


# ══════════════════════════════════════════════════════════════════════
# 掃描（fail loud：任何一種「掃不到」都是 AssertionError，不是靜默通過）
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Hit:
    path: str
    lineno: int
    keywords: tuple[str, ...]
    raw: str
    norm: str

    def describe(self) -> str:
        return f"{self.path}:{self.lineno}  命中 {list(self.keywords)}\n      → {self.raw.strip()}"


def _scan(views_dir: Path, repo: Path) -> tuple[list[Hit], list[str]]:
    """掃一個 views 目錄，回傳 `(命中清單, 掃過的檔案清單)`。

    fail loud 的四條路徑（全部走 `AssertionError`，**不 skip**）：
      F1 目錄不存在 / 不是目錄
      F2 一個 `.py` 都沒掃到（射程被改壞、或目錄被搬走）
      F3 檔案讀不到 / 不是 UTF-8
      F4 `ast.parse` 失敗（檔案根本不是合法 Python → 掃描結果不可信）
    """
    assert views_dir.is_dir(), (                                    # F1
        f"[fail loud] 掃描射程不存在：{views_dir}\n"
        "views 目錄被搬走或改名了？請更新本檔的 `_VIEWS_REL`，"
        "**不要**讓這支守衛靜靜地變成永遠綠。")

    files = sorted(p for p in views_dir.rglob("*.py")
                   if "__pycache__" not in p.parts)
    assert files, (                                                 # F2
        f"[fail loud] {views_dir} 底下一個 .py 都沒掃到。\n"
        "0 檔 = 0 命中 = 永遠綠，那比沒有守衛更危險（CLAUDE.md §1）。")

    hits: list[Hit] = []
    scanned: list[str] = []
    for path in files:
        rel = path.relative_to(repo).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:                # F3
            raise AssertionError(
                f"[fail loud] 讀不到 {rel}：{exc!r}\n"
                "讀不到就等於沒掃到 —— 不准當成「沒有違規」放行。") from exc
        try:
            ast.parse(text, filename=str(path))
        except SyntaxError as exc:                                  # F4
            raise AssertionError(
                f"[fail loud] {rel} 不是合法 Python（{exc}）。\n"
                "檔案壞掉時掃描結果不可信，本守衛拒絕回報「沒有違規」。") from exc

        scanned.append(rel)
        for lineno, raw in enumerate(text.splitlines(), 1):
            norm = _normalize(raw)
            found = tuple(k for k in KEYWORDS if k in norm)
            if found:
                hits.append(Hit(path=rel, lineno=lineno, keywords=found,
                                raw=raw, norm=norm))
    return hits, scanned


def _covering(hit: Hit, registry: tuple[Entry, ...]) -> Entry | None:
    """找出涵蓋這一行的登記（同檔 + snippet 出現在正規化後的整行裡）。"""
    for entry in registry:
        if entry.path == hit.path and entry.snippet in hit.norm:
            return entry
    return None


def _unregistered(hits: list[Hit], registry: tuple[Entry, ...]) -> list[Hit]:
    return [h for h in hits if _covering(h, registry) is None]


def _stale(hits: list[Hit], registry: tuple[Entry, ...]) -> list[Entry]:
    """登記了、卻對不上任何一行 → 過期登記。"""
    used = {id(e) for h in hits if (e := _covering(h, registry)) is not None}
    return [e for e in registry if id(e) not in used]


def _resolve_symbol(spec: str, repo: Path) -> str | None:
    """驗 `"tests/檔.py::Class::test_名"` 真的存在；OK 回 None，否則回錯誤說明。

    用 AST 逐層往下找（不是字串搜尋）—— 註解或字串裡寫個 `def test_x` 不算數。
    """
    parts = [s for s in spec.split("::") if s]
    if len(parts) < 2:
        return (f"格式錯誤：{spec!r}；要寫成 "
                "\"tests/檔.py::Class::test_名\" 或 \"tests/檔.py::test_名\"")
    rel, syms = parts[0], parts[1:]
    path = repo / rel
    if not path.is_file():
        return f"{rel} 不存在"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"{rel} 讀不到：{exc!r}"
    try:
        node: ast.AST = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return f"{rel} 解析失敗：{exc}"
    for sym in syms:
        child = next(
            (c for c in ast.iter_child_nodes(node)
             if isinstance(c, (ast.ClassDef, ast.FunctionDef,
                               ast.AsyncFunctionDef)) and c.name == sym),
            None)
        if child is None:
            return f"{rel} 裡找不到 {sym}（往下第 {syms.index(sym) + 1} 層）"
        node = child
    return None


_SCAN_CACHE: dict[str, tuple[list[Hit], list[str]]] = {}


def _repo_scan() -> tuple[list[Hit], list[str]]:
    """本 repo 的實際掃描結果（整輪只算一次）。"""
    if "v" not in _SCAN_CACHE:
        _SCAN_CACHE["v"] = _scan(_REPO / _VIEWS_REL, _REPO)
    return _SCAN_CACHE["v"]


# ══════════════════════════════════════════════════════════════════════
# 守衛本體
# ══════════════════════════════════════════════════════════════════════
_HOWTO = (
    "\n處置（二選一，**不要**加豁免 pragma —— 本檔刻意沒有那個門）：\n"
    "  A. 這一行是在**否認 / 記錄舊文案為假** → 到 `REGISTRY` 加一筆 "
    "`kind=DISCLOSURE`，`why` 寫清楚它在否認什麼。\n"
    "  B. 這一行**真的在宣稱**全站唯一 → **先停手**。依 CLAUDE.md §-2 規則 6，"
    "全稱句要嘛有第二組實測、要嘛就別寫。\n"
    "     真要寫：先寫一支**現場去掃 repo** 的測試（別抄名單），"
    "再登 `kind=CLAIM` + `verified_by=\"tests/檔.py::Class::test_名\"`。\n"
)


def test_the_scan_really_reached_the_view_files():
    """fail loud 的入口：射程、檔案數、可讀性、可解析性都先確認過。"""
    hits, scanned = _repo_scan()
    assert scanned, "[fail loud] 掃描結果為空 —— 見 `_scan` 的 F1/F2"
    assert any(p.endswith("page_hold.py") for p in scanned), (
        f"[fail loud] 沒掃到 page_hold.py；實際掃到：{scanned}\n"
        "射程被改窄了？本檔的登記表對得上它，掃不到就代表結果不可信。")
    # 命中數只作為訊息，不作為斷言門檻（0 命中是合法的乾淨狀態，
    # 但那時 `test_no_registry_entry_is_stale` 會把過期登記全部照出來）。
    assert isinstance(hits, list)


def test_every_universal_claim_line_is_registered():
    """`src/ui/views/**` 裡每一行全稱句都必須在 `REGISTRY` 有登記。"""
    hits, _ = _repo_scan()
    bad = _unregistered(hits, REGISTRY)
    assert not bad, (
        f"以下 {len(bad)} 行出現「全站唯一」類的全稱宣稱，但**沒有登記**：\n\n"
        + "\n".join(h.describe() for h in bad)
        + "\n\n2026-09-07 一天之內這類句子被實測出**三句全假**"
          "（乘法點 / 建議持股 SSOT / 位階唯一出處），"
          "所以現在一律要先登記、CLAIM 還要指向會實測它的測試。"
        + _HOWTO)


def test_no_registry_entry_is_stale():
    """登記了卻對不上任何一行 → 過期登記，一樣紅燈。

    一份**會說謊的清單比沒有清單更危險**（`CLAUDE.md §8.2.A.0` 的病史）：
    留著對不上的登記，下一個人會以為那句話還在畫面上、還被守著。
    """
    hits, _ = _repo_scan()
    bad = _stale(hits, REGISTRY)
    assert not bad, (
        f"以下 {len(bad)} 筆登記已經對不上任何一行（文案被改掉或刪掉了）：\n\n"
        + "\n".join(f"  {e.path}  snippet={e.snippet!r}" for e in bad)
        + "\n\n處置：確認那句話真的不見了 → **刪掉這筆登記**；\n"
          "      只是被改寫 → 更新 snippet（填正規化後的新特徵，≥ "
        f"{_MIN_SNIPPET} 字，不要填行號）。")


def test_claim_entries_point_at_a_test_that_exists():
    """`CLAIM` 的 `verified_by` 必須指向真的存在的測試符號。

    這是登記制唯一**機器可驗**的那一半：一句全稱宣稱要留在畫面上，
    就得有一支測試真的去量它。指向不存在的測試 = 假的護欄，當場紅燈。
    """
    bad: list[str] = []
    for entry in REGISTRY:
        if entry.kind != CLAIM:
            continue
        err = _resolve_symbol(entry.verified_by, _REPO)
        if err:
            bad.append(f"  {entry.path}  snippet={entry.snippet!r}\n"
                       f"      verified_by={entry.verified_by!r} → {err}")
    assert not bad, (
        "以下 CLAIM 登記指向的測試不存在（＝沒有任何東西在驗那句全稱宣稱）：\n\n"
        + "\n".join(bad)
        + "\n\n沒查證的宣稱比沒有宣稱更危險（CLAUDE.md §-2 規則 6）。")


def test_the_registry_itself_is_well_formed():
    """登記表自己的體檢 —— 防止用一筆萬用登記把守衛關掉。"""
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()
    for entry in REGISTRY:
        tag = f"{entry.path}::{entry.snippet!r}"
        if entry.kind not in _KINDS:
            problems.append(f"{tag} kind={entry.kind!r} 不在 {_KINDS}")
        if not entry.why.strip():
            problems.append(f"{tag} `why` 是空的 —— 登記制的價值就在這一欄")
        if _normalize(entry.snippet) != entry.snippet:
            problems.append(
                f"{tag} snippet 沒有正規化（含空白/`*`/引號），"
                "永遠比對不到；請填 `_normalize()` 之後的形式")
        if len(entry.snippet) < _MIN_SNIPPET:
            problems.append(
                f"{tag} snippet 太短（{len(entry.snippet)} < {_MIN_SNIPPET}）—— "
                "短 snippet 會變成一筆蓋全部的萬用登記，等於把守衛關掉")
        if any(entry.snippet == k for k in KEYWORDS):
            problems.append(f"{tag} snippet 就等於關鍵詞本身 = 萬用登記")
        if entry.kind == CLAIM and not entry.verified_by.strip():
            problems.append(f"{tag} 是 CLAIM 但沒填 verified_by")
        if entry.kind == DISCLOSURE and entry.verified_by.strip():
            problems.append(
                f"{tag} 是 DISCLOSURE 卻填了 verified_by —— "
                "否定式揭露不需要（也不該）掛一支「驗證那個宣稱」的測試")
        if (entry.path, entry.snippet) in seen:
            problems.append(f"{tag} 重複登記")
        seen.add((entry.path, entry.snippet))
        if not entry.path.startswith(_VIEWS_REL + "/"):
            problems.append(f"{tag} 不在射程 {_VIEWS_REL}/ 內")
    assert not problems, "登記表本身有問題：\n  " + "\n  ".join(problems)


# ══════════════════════════════════════════════════════════════════════
# 守衛的自我驗證 —— 證明它抓得到真違規、不會被無關字眼騙、fail loud 真的會炸
# （CLAUDE.md §6 結尾：「3 個最容易讓這段程式出錯的輸入」）
# ══════════════════════════════════════════════════════════════════════
def _probe(tmp_path: Path, name: str, code: str) -> tuple[list[Hit], list[str]]:
    views = tmp_path / _VIEWS_REL
    views.mkdir(parents=True, exist_ok=True)
    (views / name).write_text(code, encoding="utf-8")
    return _scan(views, tmp_path)


class TestGuardItself:
    def test_catches_an_unregistered_new_claim(self, tmp_path):
        """最重要的一條：第六頁寫第四句全稱句 → 未登記 → 紅。"""
        hits, _ = _probe(tmp_path, "page_new.py",
                         'LABEL = "建議持股水位（全站唯一出處）"\n')
        assert hits, "新寫的全稱句沒被掃到"
        assert _unregistered(hits, REGISTRY), "未登記的新命中必須被判紅"

    def test_catches_markdown_emphasis_and_quote_bypass(self, tmp_path):
        """`全站**唯一**` / `「全站」唯一` / `全 repo 唯一` 都不准漏。"""
        hits, _ = _probe(tmp_path, "page_bypass.py", (
            'A = "本頁是全站**唯一**的出處"\n'
            'B = "這是「全站」唯一的乘法點"\n'
            'C = "全 repo 唯一的一份 SSOT"\n'
            'D = "整個 repo 只有這一處"\n'
        ))
        assert len(hits) == 4, f"換句話說的寫法漏掉了：{[h.raw for h in hits]}"

    def test_not_fooled_by_unrelated_words(self, tmp_path):
        """假陽性防護：`全站上限`/`全站另有`/`全站最大`/`該檔唯一` 都不是全稱宣稱。"""
        hits, _ = _probe(tmp_path, "page_innocent.py", (
            'A = "要求的欄數超過全站上限"\n'
            'B = "全站另有沒進到仲裁裡的獨立算法"\n'
            'C = "線框註記本頁是全站最大 form 受益點"\n'
            'D = "該檔唯一的乘法點住在 L3"\n'
            'E = "這是本頁唯一一次呼叫 L3"\n'
        ))
        assert hits == [], f"誤判了無關字眼：{[h.raw for h in hits]}"

    def test_catches_a_stale_registry_entry(self, tmp_path):
        """文案被改掉 → 登記變成過期 → 紅（不准留一份對不上的清單）。"""
        hits, _ = _probe(tmp_path, "page_x.py", 'A = "無關內容"\n')
        entry = Entry(path=f"{_VIEWS_REL}/page_x.py",
                      snippet="這不是全站唯一的持股水位算法",
                      kind=DISCLOSURE, why="probe")
        assert _stale(hits, (entry,)) == [entry]

    def test_a_claim_pointing_at_a_missing_test_is_reported(self):
        """CLAIM 指向不存在的測試 → 必須被抓出來。"""
        assert _resolve_symbol(
            "tests/test_views_no_unverified_universal_claims.py::"
            "TestGuardItself::test_does_not_exist_at_all", _REPO)
        assert _resolve_symbol("tests/no_such_file_at_all.py::test_x", _REPO)
        assert _resolve_symbol("沒有雙冒號", _REPO)

    def test_a_claim_pointing_at_a_real_test_resolves(self):
        """反向：指向真的存在的測試 → 不得誤判為缺席。"""
        assert _resolve_symbol(
            "tests/test_views_no_unverified_universal_claims.py::"
            "TestGuardItself::test_a_claim_pointing_at_a_real_test_resolves",
            _REPO) is None
        assert _resolve_symbol(
            "tests/test_views_no_unverified_universal_claims.py::"
            "test_every_universal_claim_line_is_registered", _REPO) is None

    def test_fail_loud_on_missing_directory(self, tmp_path):
        """F1：射程不存在 → AssertionError，不是靜默 0 命中。"""
        try:
            _scan(tmp_path / "nope" / "views", tmp_path)
        except AssertionError as exc:
            assert "掃描射程不存在" in str(exc)
        else:
            raise AssertionError("目錄不存在時必須炸，不准回報「沒有違規」")

    def test_fail_loud_on_empty_directory(self, tmp_path):
        """F2：一個 .py 都沒有 → AssertionError。"""
        views = tmp_path / _VIEWS_REL
        views.mkdir(parents=True)
        try:
            _scan(views, tmp_path)
        except AssertionError as exc:
            assert "一個 .py 都沒掃到" in str(exc)
        else:
            raise AssertionError("0 檔 = 永遠綠，必須炸")

    def test_fail_loud_on_undecodable_file(self, tmp_path):
        """F3：不是 UTF-8 → AssertionError（不准當成「沒有違規」）。"""
        views = tmp_path / _VIEWS_REL
        views.mkdir(parents=True)
        (views / "page_bad.py").write_bytes(b'A = "\xff\xfe\x00 not utf8"\n')
        try:
            _scan(views, tmp_path)
        except AssertionError as exc:
            assert "讀不到" in str(exc)
        else:
            raise AssertionError("讀不到檔案時必須炸")

    def test_fail_loud_on_syntax_error(self, tmp_path):
        """F4：`ast.parse` 失敗 → AssertionError。"""
        try:
            _probe(tmp_path, "page_broken.py", "def (:\n")
        except AssertionError as exc:
            assert "不是合法 Python" in str(exc)
        else:
            raise AssertionError("檔案壞掉時必須炸")


# ══════════════════════════════════════════════════════════════════════
# 已知缺口（誠實揭露，CLAUDE.md §-2 規則 6 —— 不要當成「全都擋住了」）
# ══════════════════════════════════════════════════════════════════════
# 1. **只擋「全域範圍 + 唯一/僅/只有」這一族。** 否定式全稱句
#    （`全 repo 沒有任何 …`）與計數式全稱句（`全 repo 只有 9 支 …`）**不在射程**。
#    實測（量測日 2026-09-07）`src/ui/views/**` 兩者都有：
#    `page_inspect.py` 有一句自陳「不精確」的 `全 repo 沒有任何 L3 介面…`，
#    `page_why.py` 印給使用者看的 `全 repo 只有 9 支 fetcher 掛了監控`
#    **目前沒有任何測試在守那個數字**。這是**有意識的射程邊界**（收進來要一併
#    把那些宣稱實測到底），不是查漏 —— 下一輪要不要收，請當成一件獨立的事評估。
# 2. **`DISCLOSURE` 這個分類機器驗不了。** 有人硬把一句真主張登成 DISCLOSURE，
#    本檔擋不住 —— 擋它的是 code review 與 `CLAUDE.md §-2` 規則 4 的獨立複驗。
#    機器可驗的只有 `CLAIM` 那一半（`verified_by` 必須真的存在）。
# 3. **只看單行。** 一句全稱宣稱若被硬換行拆成兩行（關鍵詞跨行切斷），掃不到。
#    現況 `src/ui/views/**` 未見此寫法；真的出現時請把偵測改成「先合併邏輯行」，
#    **不要**改成放寬。
