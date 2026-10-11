"""shared/inst_labels.py — 三大法人身分別名稱判定 SSOT（L0，批 Z40，2026-10-11）。

客戶裁示（Q-z24＝A' 官方口徑、Q-z25＝A）
=========================================
- **外資** ＝ 外資及陸資（**不含**外資自營商）。
- **自營商** ＝ 自營商（自行買賣）＋ 自營商（避險）。
- **外資自營商不再額外加到任何一類**；三大法人合計不含外資自營商項。
  TWSE BFI82U notes 原文：「因外資自營商買賣金額已計入自營商買賣金額，故不納入三大法人買賣金額之合計數計算。」
  ⇒ 外資自營商**已含在**自營商（自行＋避險）內，另加＝重複計算。

官方報表實測（runner 探針 run 38104351927／38105028779，2026-10-08；派工規格轉述）
------------------------------------------------------------------------------
- TWSE T86 19 欄：外資＝`外陸資買賣超股數(不含外資自營商)`、外資自營商＝`外資自營商買賣超股數`、
  投信＝`投信買賣超股數`、自營商＝`自營商買賣超股數`（＝自行＋避險，18975/18975 列成立）、
  三大法人＝`三大法人買賣超股數`（＝外資(不含)＋投信＋自營商，100%）。
- TWSE BFI82U 列：`自營商(自行買賣)`、`自營商(避險)`、`投信`、`外資及陸資(不含外資自營商)`、
  `外資自營商`、`合計`；合計 ＝ 自行＋避險＋投信＋外資(不含)。
- FinMind name：`Foreign_Investor`（＝外資(不含)）、`Foreign_Dealer_Self`（外資自營商）、
  `Investment_Trust`、`Dealer_self`（自行）、`Dealer_Hedging`（避險）、`total`。

⚠️ 子字串陷阱（本模組存在的理由）
- 「外資及陸資(不含外資自營商)」／「外陸資買賣超股數(不含外資自營商)」**含**子字串「外資自營商」與「自營」；
- 「外資自營商買賣超股數」**含**子字串「自營商買賣超股數」；
- 「Foreign_Dealer_Self」**同時含** `foreign` 與 `dealer`。
⇒ 判定一律走本模組，不在各 fetcher 各寫一套 `in` 子字串。

純函式／常數模組，零 import 依賴（可被全層 import）。
"""
from __future__ import annotations

#: FinMind name 值（大小寫依 FinMind 實際回傳）
FINMIND_FOREIGN_INVESTOR: str = "Foreign_Investor"
FINMIND_FOREIGN_DEALER_SELF: str = "Foreign_Dealer_Self"
FINMIND_INVESTMENT_TRUST: str = "Investment_Trust"
#: 自營商 ＝ 自行買賣 ＋ 避險（客戶 Q-z25＝A）
FINMIND_DEALER_NAMES: tuple[str, str] = ("Dealer_self", "Dealer_Hedging")

#: TWSE T86 欄名（strip 後**完全相等**比對；⛔ 不用子字串 —— 見模組 docstring 子字串陷阱）
T86_FOREIGN_NET_COL: str = "外陸資買賣超股數(不含外資自營商)"
#: 2017-12-18 前舊格式外資欄（當時官方外資口徑含外資自營商；只作舊格式備援，完全相等比對）
T86_FOREIGN_NET_COL_LEGACY: str = "外資買賣超股數"
T86_TRUST_NET_COL: str = "投信買賣超股數"
T86_DEALER_NET_COL: str = "自營商買賣超股數"                 # 自行＋避險合計
T86_DEALER_SELF_NET_COL: str = "自營商買賣超股數(自行買賣)"
T86_DEALER_HEDGE_NET_COL: str = "自營商買賣超股數(避險)"
T86_TOTAL_NET_COL: str = "三大法人買賣超股數"


#: 括號修飾語（半形／全形括號皆可；未閉合的左括號視為修飾到字尾）。
#:   ⛔ 不用 `import re`：本模組宣告零 import 依賴 —— 以 `_strip_paren_modifiers` 逐字掃描。
_OPEN_PARENS: str = "(（"
_CLOSE_PARENS: str = ")）"


def _strip_paren_modifiers(s: str) -> str:
    """去掉所有括號修飾語（含括號本身），只留名稱本體。未閉合左括號 → 其後全部視為修飾語。"""
    out: list[str] = []
    depth = 0
    for ch in s:
        if ch in _OPEN_PARENS:
            depth += 1
        elif ch in _CLOSE_PARENS and depth:
            depth -= 1
        elif not depth:
            out.append(ch)
    return "".join(out)


#: 括號內「外資自營商」之前（同一子句）出現任一字 ⇒ 否定修飾（`不含`／`未含`／`不包含`／`不計`／`非`／`排除`／`扣除`…）
_NEG_PREFIX_CHARS: str = "不未非除"
#: 括號內「外資自營商」之後（同一子句）出現任一詞 ⇒ 否定修飾（`(外資自營商除外)`／`(外資自營商不計)`…）
_NEG_SUFFIX_WORDS: tuple[str, ...] = ("除外", "以外", "不計", "不含", "不包", "排除", "扣除", "剔除")
#: 括號內子句分隔（`(不含外資自營商，含外資自營商避險)` 這類多子句修飾語逐句判）
_CLAUSE_SEPS: str = ",，、;；/／"
_FD: str = "外資自營商"


def _paren_contents(s: str) -> list[str]:
    """回傳每段**最外層**括號內文（含巢狀括號字元）；未閉合左括號 ⇒ 其後全部算一段。"""
    segs: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in s:
        if ch in _OPEN_PARENS:
            if depth:
                buf.append(ch)
            depth += 1
        elif ch in _CLOSE_PARENS and depth:
            depth -= 1
            if depth:
                buf.append(ch)
            else:
                segs.append("".join(buf))
                buf = []
        elif depth:
            buf.append(ch)
    if depth:
        segs.append("".join(buf))
    return segs


def _paren_mentions_foreign_dealer_affirmatively(s: str) -> bool:
    """括號修飾語裡有**非否定**地提到「外資自營商」（`(含外資自營商)`／`(包含外資自營商)`／`(外資自營商)`…）→ True。

    逐括號段、逐子句（`_CLAUSE_SEPS` 切）判：子句含「外資自營商」，且其前無否定字（`_NEG_PREFIX_CHARS`）、
    其後無否定詞（`_NEG_SUFFIX_WORDS`）⇒ 肯定。⚠️ 無修飾詞的裸提及（`外資(外資自營商)`）也算肯定 ——
    口徑不明時從嚴：寧可該類缺值，不可把可能混有外資自營商的數字收進外資（§1）。
    """
    for seg in _paren_contents(s):
        clause = ""
        for ch in seg + _CLAUSE_SEPS[0]:
            if ch not in _CLAUSE_SEPS:
                clause += ch
                continue
            start = clause.find(_FD)
            while start != -1:
                pre, post = clause[:start], clause[start + len(_FD):]
                if not (any(c in pre for c in _NEG_PREFIX_CHARS)
                        or any(w in post for w in _NEG_SUFFIX_WORDS)):
                    return True
                start = clause.find(_FD, start + 1)
            clause = ""
    return False


def is_foreign_mixed_with_dealer_label(name: object) -> bool:
    """「混有外資自營商」的外資類名稱 → True（批 Z40 跟進三，QA F-A）。

    名稱本體（去括號後）**非空且本身不是**外資自營商，但括號修飾語**肯定地**含外資自營商 ——
    例：`外資及陸資(含外資自營商)`、`外資(包含外資自營商)`、全形括號版本。
    這種數字 ＝ 外資(不含) ＋ 外資自營商，**不符客戶口徑**（外資＝不含外資自營商），且外資自營商已含在
    自營商（自行＋避險）內 ⇒ 收進外資＝口徑錯＋主力合計重複計入。
    ⇒ `is_foreign_dealer_label` 對它也回 True，讓所有 caller 走既有「排除／drop」路徑（該類缺值，不收為任何類）。
    """
    s = str(name).strip()
    body = _strip_paren_modifiers(s).strip()
    return bool(body) and _FD not in body and _paren_mentions_foreign_dealer_affirmatively(s)


def is_foreign_dealer_label(name: object) -> bool:
    """「涵蓋外資自營商」的身分別（列名／欄名／FinMind name）→ True；**所有 caller 一律排除（不收為任何類別）**。

    - 英文：`Foreign_Dealer_Self`（不分大小寫、去頭尾空白）。
    - 中文，下列任一成立即 True：
      1. **名稱本體**（去掉所有括號修飾語之後）含「外資自營商」——
         `外資自營商`、`外資自營商買賣超股數`、`外資自營商買進股數`、`外資自營商(含避險)`；
      2. 括號修飾語**肯定地**提到外資自營商（見 `_paren_mentions_foreign_dealer_affirmatively`）——
         a. 本體非空 ⇒ 「混有外資自營商」的外資列（`外資及陸資(含外資自營商)`；
            同 `is_foreign_mixed_with_dealer_label`）：不符口徑，不得收為外資；
         b. 本體為空 ⇒ 名稱整個就是外資自營商（`(外資自營商)`、`（外資自營商）`）。
    - False：括號修飾語為**否定**（`外資及陸資(不含外資自營商)`、`外陸資買賣超股數(不含外資自營商)`、
      `外資(不包含外資自營商)`、`外資及陸資(未含外資自營商)`、`外資(外資自營商除外)`、全形括號版本）——
      括號只是在說明該外資列的口徑不含外資自營商，名稱本身就是客戶口徑的外資。
    - 歷程：批 Z40 跟進二（QA F5）只看本體 ⇒ `(含外資自營商)` 被判 False 而被當外資收進來（QA F-A）、
      `(外資自營商)` 被判 False 而被 `_fm_cat` 因含「外資」歸外資（QA F-B）；批 Z40 跟進三補第 2 條。
      官方名稱（T86 19 欄、BFI82U 6 列、FinMind 6 值）判定與跟進二逐一相同。
    """
    s = str(name).strip()
    if s.lower() == FINMIND_FOREIGN_DEALER_SELF.lower():
        return True
    return (_FD in _strip_paren_modifiers(s)
            or _paren_mentions_foreign_dealer_affirmatively(s))


def is_finmind_foreign_investor(name: object) -> bool:
    """FinMind 外資（不含外資自營商）：name 完全等於 `Foreign_Investor`（去頭尾空白、不分大小寫）。"""
    return str(name).strip().lower() == FINMIND_FOREIGN_INVESTOR.lower()


def is_finmind_dealer(name: object) -> bool:
    """FinMind 自營商（自行＋避險）：name 完全等於 `Dealer_self` 或 `Dealer_Hedging`（去頭尾空白、不分大小寫）。"""
    return str(name).strip().lower() in tuple(n.lower() for n in FINMIND_DEALER_NAMES)
