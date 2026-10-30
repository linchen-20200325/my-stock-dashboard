"""p02～p05 View 卡面測試共用的「資訊守恆」斷言（Phase 2 步驟 2＋4，tests-only）。

客戶原則（`docs/vnext/PRESENTATION_MIGRATION_PLAN_2026-10-29.md §3`）：測試驗證「某段字一定要顯示在
**卡面**」者，改驗 —— 資訊沒有遺失、正確資料可取得、詳細說明可展開、provenance 可追溯、
Missing 語意未改。誠實不變量照原強度保留，只把「在卡面」改成「在卡面 ∪ 摺疊」。

這個檔只放**不依賴頁面版面**的小工具；各頁測試檔自己負責「這頁有哪些卡、哪些常數」。
⛔ 它**只**讀 `card_html` 實際吐出的 HTML（以 `<div class="blk-fold">` 切成 卡面 ／ 摺疊），
不讀任何 production 的登記表 —— 期望值一律由呼叫端用原始 `Card`／`Note`／`facts` 傳進來
（測試是第二把尺）。

⚠️ 「卡面 ∪ 摺疊」在這裡的意思是**同一張卡輸出的 HTML 內**，不是「任何地方出現即可」：
每個檢查都綁定**同一個標籤**的列（或同一張卡的原始來源文字），不會因為別張卡有那個字就放行。
"""
from __future__ import annotations

import dataclasses
import html
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Sequence

_ROW_RE = r'<span class="blk-fact-k">(.*?)</span><span class="blk-fact-v"[^>]*>(.*?)</span>'
FOLD_MARK = '<div class="blk-fold">'

#: 會把「缺值」誤讀成「沒事」的字（客戶指定：0／中性／正常／續抱／安全；步驟 2 QA 補：無異常／沒問題／穩定／無風險）。
#: `0` 只算**獨立的零**（不吃 `10`、`0.5`、`00878`、`00:00`、`30–50%` 裡的 0）；
#: `0.0`／`0.00`（可帶 `%`）在句中也算一個獨立的零（`0.05`、`10.0`、`0.0.1` 不算）。
#: （NFKC 會把全形逗號 `，` 變成 ASCII `,`，所以只有『逗號／句點後面緊接數字』才當千分位／小數點排除。）
#: ⚠️ 比對前一律先 NFKC 正規化（全形 `０` → `0`、全形 `％` → `%`），否則全形零會漏網。
_MISLEADING_TOKEN = re.compile(
    r"中性|正常|續抱|安全|無異常|沒問題|穩定|無風險"
    r"|(?<![\d:：/])(?<!\d[.,])0\.0+%?(?!\d|[.,]\d|[:：/])"
    r"|(?<![\d:：/])(?<!\d[.,])0(?!\d|[.,]\d|[:：/])")
#: 一格的**整個值**若就是這些，等於卡面直接宣稱「0／中性／正常…」（已 NFKC，所以全形 `０` 與 `0` 同列）。
_MISLEADING_WHOLE_VALUES = frozenset({
    "0", "0.0", "0.00", "0%", "0.0%", "中性", "正常", "續抱", "安全", "OK", "ok",
    "無異常", "沒問題", "穩定", "無風險"})


def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def split_face_fold(outer: str) -> tuple[str, str]:
    """（卡面, 摺疊區）。沒有摺疊區 → 摺疊為空字串。與各頁測試檔原本的 `_split` 同義。"""
    i = outer.find(FOLD_MARK)
    return (outer, "") if i < 0 else (outer[:i], outer[i:])


def rows_of(fragment: str) -> list[tuple[str, str]]:
    return [(html.unescape(k), html.unescape(v)) for k, v in re.findall(_ROW_RE, fragment, re.S)]


def face_rows(outer: str) -> list[tuple[str, str]]:
    return rows_of(split_face_fold(outer)[0])


def fold_rows(outer: str) -> list[tuple[str, str]]:
    return rows_of(split_face_fold(outer)[1])


def visible_text(fragment: str) -> str:
    """可見文字：去掉標籤（⛔ 連同所有屬性，所以 `title=` 的字**不算**可見）。"""
    return html.unescape(re.sub(r"<[^>]+>", "\n", fragment))


def label_union_text(outer: str, label: str) -> str:
    """同一標籤的列，卡面 ∪ 摺疊的值串起來（綁標籤，不是整張卡的全文）。"""
    return "\n".join(v for k, v in face_rows(outer) + fold_rows(outer) if k == label)


def _excerpt_of(shown: str, original: str, gap: str, ellipsis: str, max_chars: int) -> bool:
    """`shown` 是不是 `original` 的摘錄（逐段依序在原文找得到；截斷的「…」先拿掉）。"""
    if shown.endswith(ellipsis) and len(shown) > max_chars:
        shown = shown[:-1]
    pos = 0
    for piece in (shown.split(gap) if gap else [shown]):
        if piece:
            at = original.find(piece, pos)
            if at < 0:
                return False
            pos = at + len(piece)
    return True


# ── T2：facts ─────────────────────────────────────────────────────────────
def drop_note_rows(rows: list[tuple[str, str]], note, keys: Sequence[str],
                    plain: Callable[[object], str], *, exact: bool) -> list[tuple[str, str]]:
    """扣掉 Note 三列，剩下的才是 facts。

    ⚠️ 不能單靠標籤排除：實測 `hold.setup.*` 的 facts 裡有一格標籤就叫「為什麼」，與 Note 的標籤撞名。
    做法：每個 Note 標籤**只扣第一列**（Note 三列排在 facts 前面，現行與規格皆然）；摺疊區的 Note 列
    是整句原文，所以改用 (標籤, 整句原文) **逐字**扣（`exact=True`），比「第一列」更不會誤傷。
    `note is None` ⇒ 不扣任何一列（沒有 Note 就沒有 Note 列）。

    ⚠️ **前提（QA-A 補，由 `note_rows_lead_problems` 守）**：Note 三列排在**所有 facts 之前**。
    「每個標籤只扣第一列」只有在這個前提下才扣對；若日後版面把 Note 移到 facts 之後，而某個 fact 的
    標籤又與 Note 標籤撞名（現有實例：`hold.setup.*` 的 facts 有一格就叫「為什麼」），這裡會扣錯列。
    前提被打破時 `note_rows_lead_problems` 會先紅 —— 要改版面的人必須**同時**升級這個函式。
    """
    if note is None:
        return list(rows)
    out = list(rows)
    for key, part in zip(keys, (note.now, note.why, note.where)):
        want = (key, plain(part))
        idx = next((i for i, r in enumerate(out)
                    if (r == want if exact else r[0] == key)), None)
        if idx is not None:
            del out[idx]
    return out


def fact_union_problems(outer: str, facts: Iterable[tuple[object, object]], *, note,
                        note_keys: Sequence[str], plain: Callable[[object], str],
                        gap: str, ellipsis: str, max_chars: int) -> list[str]:
    """原 `facts` 在「卡面 ∪ 摺疊」的守恆：回傳問題清單（空＝守恆）。

    · (a) **沒遺失**：每個原 fact 的 (標籤, 整句原值) 逐字出現在卡面或摺疊（卡面被摘過／截斷的，
      完整原文必須在摺疊）。
    · (b) **數量相等、不憑空多**：卡面與摺疊（扣掉 Note 三列）的列，以標籤計的多重集合聯集
      ＝ 原 facts 的標籤多重集合（多一列或少一列都紅）。
    · (c) **卡面不捏造**：卡面每一列的值必須是同標籤某個原值的摘錄；摺疊每一列必須與某個原 fact
      逐字相同（摺疊是完整原文，不是第二份摘要）。
    """
    want = [(plain(k), plain(v)) for k, v in facts]
    face = drop_note_rows(face_rows(outer), note, note_keys, plain, exact=False)
    fold = drop_note_rows(fold_rows(outer), note, note_keys, plain, exact=True)
    probs: list[str] = []
    pool = set(face) | set(fold)
    for k, v in want:
        if (k, v) not in pool:
            probs.append(f"fact 遺失（卡面∪摺疊都沒有整句原值）：{k!r}")
    union = Counter(k for k, _ in face) | Counter(k for k, _ in fold)
    if union != Counter(k for k, _ in want):
        probs.append(f"fact 數量／標籤不符：union={dict(union)} want={dict(Counter(k for k, _ in want))}")
    for k, v in face:
        cands = [wv for wk, wv in want if wk == k]
        if not any(_excerpt_of(v, wv, gap, ellipsis, max_chars) for wv in cands):
            probs.append(f"卡面值不是原值摘錄：{k!r} → {v!r}")
    for k, v in fold:
        if (k, v) not in want:
            probs.append(f"摺疊的 fact 列不是原值逐字：{k!r} → {v!r}")
    return probs


# ── T1：Note 三要素全文 ───────────────────────────────────────────────────
def note_union_problems(outer: str, note, *, keys: Sequence[str],
                        plain: Callable[[object], str]) -> list[str]:
    """Note 三段（現況／為什麼沒有／去哪補）的**全文**逐字在「卡面 ∪ 摺疊」，且綁各自的標籤。"""
    pool = set(face_rows(outer)) | set(fold_rows(outer))
    probs = []
    for label, text in zip(keys, (note.now, note.why, note.where)):
        if (label, plain(text)) not in pool:
            probs.append(f"Note「{label}」全文不在卡面∪摺疊：{plain(text)[:40]!r}")
    return probs


# ── T3：限定詞（_MUST_KEEP）──────────────────────────────────────────────
def phrase_union_problems(outer: str, label_to_phrases: dict[str, Iterable[str]]) -> list[str]:
    probs = []
    for label, phrases in label_to_phrases.items():
        text = label_union_text(outer, label)
        for ph in phrases:
            if ph not in text:
                probs.append(f"「{label}」（卡面∪摺疊）少了「{ph}」")
    return probs


def misleading_face_problems(outer: str, sources: Iterable[str],
                             own_values: Iterable[str] = ()) -> list[str]:
    """非 live 卡面 ⛔ 不得把缺值講成「0／中性／正常／續抱／安全」。

    客戶指定的詞在**否定句**裡是合法的（例：「本站不以『中性』代替未評估」），所以不能逐字禁；
    改成兩道綁定來源的檢查（兩道都不依賴版面）：
      1. 卡面**任何一格的整個值**不得就是這些字（`0`、`正常`…），除非那就是該卡某個原始 fact 的整個值
         （`own_values`；例：資料診斷「最後一次回了幾列＝0」是真的量測值，不是替缺值頂的 0）；
      2. 這些字在卡面出現的**次數**不得多於該卡**原始來源**（label／Note 三段／facts）裡的次數 ——
         卡面只准摘錄原文，⛔ 不准自己長出一個。
    """
    face = split_face_fold(outer)[0]
    own = {_nfkc(v).strip() for v in own_values}
    probs = [f"卡面一格的整個值就是 {v!r}（缺值被講成沒事）"
             for _k, v in rows_of(face)
             if _nfkc(v).strip() in _MISLEADING_WHOLE_VALUES and _nfkc(v).strip() not in own]
    got = Counter(m.group(0) for m in _MISLEADING_TOKEN.finditer(_nfkc(visible_text(face))))
    allowed = Counter(m.group(0) for s in sources for m in _MISLEADING_TOKEN.finditer(_nfkc(s)))
    for tok, n in got.items():
        if n > allowed[tok]:
            probs.append(f"卡面出現 {tok!r} ×{n}，原始來源只有 ×{allowed[tok]}（卡面自己長出來的）")
    return probs


# ── T4：沒有出口 ─────────────────────────────────────────────────────────
def no_exit_problems(outer: str, note, *, guide_key: str, marker: str,
                     plain: Callable[[object], str]) -> tuple[list[str], int]:
    """「去哪補」是 `marker`（沒有出口）時，卡面／摺疊都不得被改寫成指路，反之亦然。

    回傳 (問題清單, 實際檢查到的『去哪補』列數)；呼叫端應斷言列數 > 0，避免空轉。
    """
    want = marker in plain(note.where)
    probs, seen = [], 0
    for where, rows in (("卡面", face_rows(outer)), ("摺疊", fold_rows(outer))):
        for k, v in rows:
            if k != guide_key:
                continue
            seen += 1
            if (marker in v) != want:
                probs.append(f"{where}「{guide_key}」{'丟了' if want else '憑空多了'}沒有出口標記：{v!r}")
    return probs, seen


# ── 步驟 4：通用 ────────────────────────────────────────────────────────
def hover_only_items(outer: str, gap: str = "") -> list[str]:
    """只活在 `title=` 屬性、**不在任何可見文字（卡面或摺疊本文）**的資訊。0 項才合格。"""
    seen_text = visible_text(outer)
    items = []
    for t in re.findall(r' title="([^"]*)"', outer):
        for piece in (html.unescape(t).split(gap) if gap else [html.unescape(t)]):
            if piece.strip() and piece not in seen_text:
                items.append(piece)
    return items


def folds_open_by_default(outer: str) -> list[str]:
    """摺疊預設不得展開：隱藏 checkbox 不得 `checked`、不得有 `aria-expanded="true"`、
    不得有 `<details open>`。回傳違規片段（空＝預設收合）。"""
    bad = [m.group(0) for m in re.finditer(r'<input[^>]*class="blk-fold-i"[^>]*>', outer)
           if re.search(r"\bchecked\b", m.group(0))]
    bad += re.findall(r'aria-expanded="true"', outer)
    bad += [m.group(0) for m in re.finditer(r"<details\b[^>]*>", outer)
            if re.search(r"\bopen\b", m.group(0))]
    return bad


# ── 步驟 2 QA-A 補強 ─────────────────────────────────────────────────────
def fold_sentinel_problems(outer: str) -> list[str]:
    """`split_face_fold` 的哨兵：卡上有摺疊開關 ⇒ 必須真的切出非空摺疊（反之亦然）。

    沒有這條，`FOLD_MARK` 一旦與實際標記漂開，`fold_rows` 會回空、所有「卡面 ∪ 摺疊」斷言
    默默退化成「只看卡面」（而 `facts ⊆ 卡面` 在沒有摺疊的卡上本來就成立）。"""
    probs = []
    has_toggle = 'class="blk-fold-i"' in outer
    face, fold = split_face_fold(outer)
    if has_toggle and not fold:
        probs.append("有摺疊開關（blk-fold-i），但 split_face_fold 切不出摺疊")
    if has_toggle and not fold_rows(outer) and fold:
        probs.append("切出了摺疊區但讀不到任何一列（_ROW_RE 與實際標記漂開？）")
    if fold and not has_toggle:
        probs.append("有 blk-fold 區塊卻沒有摺疊開關")
    if fold and FOLD_MARK in face:
        probs.append("摺疊標記同時出現在卡面")
    return probs


def note_rows_lead_problems(outer: str, note, keys: Sequence[str]) -> list[str]:
    """`drop_note_rows` 的前提：每個 Note 標籤的**第一列**都排在所有非 Note 列之前（Note 在 facts 前）。"""
    if note is None:
        return []
    rows = face_rows(outer)
    idx = []
    for key in keys:
        i = next((n for n, r in enumerate(rows) if r[0] == key), None)
        if i is None:
            return [f"卡面沒有 Note 標籤「{key}」的列"]
        idx.append(i)
    others = [n for n in range(len(rows)) if n not in idx]
    if others and min(others) < max(idx):
        return [f"Note 三列 {idx} 沒有全部排在 facts 之前（最早的非 Note 列在 {min(others)}）"]
    return []


def face_order_problems(outer: str, facts: Iterable[tuple[object, object]], *, note,
                        keys: Sequence[str], plain: Callable[[object], str]) -> list[str]:
    """卡面順序（M07；⛔ 不綁絕對位置）：

    · Note 三列（現況／為什麼沒有／去哪補，各標籤取第一列）**整體連續、依序**，不得有 fact 穿插其間；
    · 扣掉 Note 三列後，卡面各 fact 的標籤依**原 facts 順序**出現（原 facts 標籤序列的子序列；
      少一列由 `fact_union_problems` 管，這裡只管『相對順序沒被洗掉』）。
    """
    rows = face_rows(outer)
    probs: list[str] = []
    skip: set[int] = set()
    if note is not None:
        idx = []
        for key in keys:
            i = next((n for n, r in enumerate(rows) if r[0] == key), None)
            if i is None:
                return [f"卡面沒有 Note 標籤「{key}」的列"]
            idx.append(i)
        if idx != list(range(idx[0], idx[0] + len(idx))):
            probs.append(f"Note 三列不連續或次序不對：列位置 {idx}")
        skip = set(idx)
    got = [r[0] for n, r in enumerate(rows) if n not in skip]
    want = [plain(k) for k, _ in facts]
    it = iter(want)
    if not all(label in it for label in got):
        probs.append(f"卡面 fact 標籤順序與原 facts 不同：卡面={got} 原={want}")
    return probs


# ── M04：否定／限定詞要留在卡面短句 ──────────────────────────────────────
def negation_on_face_problems(outer: str, note, pins: Iterable[tuple[str, str]], *,
                              keys: Sequence[str],
                              plain: Callable[[object], str]) -> tuple[list[str], int]:
    """手寫釘住的否定／限定詞（`pins` ＝ (標籤, 片語)）：**原文該段確實含這個片語**時，
    同標籤的卡面短句列（第一列）也必須含它。回傳 (問題, 實際檢查到幾組)。

    ⛔ 只檢查「原文確實含該詞」的卡（不得要求原文沒有的字）；片語是人手寫的第二把尺，
    不是從現行卡面反推出來的（反推＝自己驗自己，拔掉守衛也跟著綠）。
    """
    if note is None:
        return [], 0
    parts = dict(zip(keys, (note.now, note.why, note.where)))
    face = face_rows(outer)
    probs, checked = [], 0
    for label, phrase in pins:
        if phrase not in plain(parts[label]):
            continue
        checked += 1
        row = next((v for k, v in face if k == label), None)
        if row is None or phrase not in row:
            probs.append(f"卡面「{label}」短句丟了原文的否定／限定詞「{phrase}」：{row!r}")
    return probs, checked


# ── 轉義（M18）──────────────────────────────────────────────────────────
def escape_problems(out: str, *, evil: str, tricky: str) -> list[str]:
    """`evil`＝帶標籤閉合與 script 的字串；`tricky`＝只含 `<`、`&`、雙引號、單引號的字串。
    兩者都以 fact 的標籤與值、並（呼叫端自行）混進 Note／例外文字送進來。回傳問題清單。"""
    probs = []
    if "<script" in out:
        probs.append("<script 沒被轉義")
    if "alert(1)</" in out:
        probs.append("script 結尾標籤沒被轉義")
    if out.count("<div") != out.count("</div>"):
        probs.append("div 開閉數不等（標記被打破）")
    if tricky in out:
        probs.append("tricky 原樣出現在 HTML（沒轉義）")
    if html.escape(tricky) not in out and html.escape(tricky, quote=False) not in out:
        probs.append("tricky 的轉義形式不在 HTML 裡")
    pool = fold_rows(out) + face_rows(out)
    if (evil, evil) not in fold_rows(out):
        probs.append("evil 標籤／值沒有原樣（unescape 後）出現在摺疊")
    if (tricky, tricky) not in pool:
        probs.append("tricky 標籤／值 unescape 後對不回原文")
    return probs


def evil_card_problems(render: Callable[..., str], card, facts, signal, *,
                       keys: Sequence[str], plain: Callable[[object], str]) -> list[str]:
    """把一張帶 Note 的真卡改裝：標題換成 tricky、`why` 後面接 evil、再多塞 (evil, evil)／(tricky, tricky)
    兩個 fact，渲染後檢查轉義（`<`、`&`、雙引號、單引號、標籤閉合、script）。與 p02 同型。"""
    evil = '"><script>alert(1)</script>' + "x" * 50
    tricky = "a<b & c\"q\" 'r'"
    note = dataclasses.replace(card.note, why=card.note.why + evil)
    card2 = dataclasses.replace(card, note=note, label=tricky)
    out = render(card2, tuple(facts) + ((evil, evil), (tricky, tricky)), signal)
    probs = escape_problems(out, evil=evil, tricky=tricky)
    if (keys[1], plain(note.why)) not in fold_rows(out):
        probs.append("接了 evil 的 Note.why 全文沒有原樣進摺疊")
    if html.escape(plain(tricky)) not in out:
        probs.append("標題的轉義形式不在卡上")
    return probs
