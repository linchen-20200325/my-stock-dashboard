"""批 S4：SEC-r24（突變存活）／SEC-r25 ②（多遮）依 S3r（#769 `bf0ada3`）之後的程式**重新界定範圍**後的餘項。

SEC-r24 登記的 6 個突變，針對的是批 S3 第一版（`22d8ec7`，未合併）的規則；S3r 重做後：
  · M09（副檔名長度上限）、M12（`_b64ish` 要求小寫）—— 規則已不存在（`shared/secret_scrub.py` 無對應程式）→ 不適用；
  · M05（Authorization 前字界）、M07（base64 本體用空白分行）—— 規則仍在 → 本檔各加一組針對性測試；
  · M10（跳脫 tab）→ 對到現行的目錄 tab 規則（SEC-r13 (b)）；
  · M16（孤兒續行第一行下限 40）→ 對到現行「判不了標頭時的整齊本體」門檻（`_DER_LOOSE_TIDY_MIN`、≥3 行）——
    同一個門檻也是 SEC-r25 ② 的觸發點（`***重點***` 後面接一行長字串被吞）。
SEC-r25 ② 原實例在現行程式不再重現（一行、兩行都原樣）；本檔把它釘成回歸測試。

每個測試都只看**輸出**（不看內部常數），突變見 `_MUTANTS`，每個都由本檔至少一個測試抓到（`test_each_mutant_is_killed`）。
"""
from __future__ import annotations

import random
import string

import pytest

from shared.secret_md import scrub_qa_text
from shared.secret_scrub import scrub_prose_secrets, scrub_secrets
from tests.test_sec_s3_batch_s3 import _b64, _leak, _pkcs8, _wrap

_FUNCS = [scrub_secrets, scrub_prose_secrets]


# ══════════════════════════════════════════════════════════════════
# M05：`Authorization` 標頭規則要求前面是記號開頭（不是英數／底線）
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("f", _FUNCS)
@pytest.mark.parametrize("raw", ["XAuthorization: tok123abc", "my_Authorization: tok123abc",
                                 "NoAuthorization=tok123abc", "ProxyAuthorization: Basic tok123abc"])
def test_m05_authorization_inside_a_longer_name_unchanged(f, raw):
    assert f(raw) == raw


@pytest.mark.parametrize("f", _FUNCS)
@pytest.mark.parametrize("raw,want", [("Authorization: tok123abc", "Authorization: ***"),
                                      ("x-Authorization: tok123abc", "x-Authorization: ***"),
                                      ("b'a\\nAuthorization: tok123abc'", "b'a\\nAuthorization: ***'")])
def test_m05_authorization_at_token_start_masked(f, raw, want):
    """對照組：記號開頭（含 `-` 之後、`repr` 的 `\\n` 跳脫之後）照遮。"""
    assert f(raw) == want


# ══════════════════════════════════════════════════════════════════
# M07：base64 本體以「換行或空白」分行（空白不算 base64 字；最後一段不算進「實際長度」）
# ══════════════════════════════════════════════════════════════════
#: Ed25519 PKCS#8 開頭（宣告 48 位元組）：第一行 40 字 ＋ 空白 ＋ 19 字 ＝ 59 個 base64 字 < 60 → 不遮。
_ED_HEAD = "MC4CAQAwBQYDK2VwBCIEI"


@pytest.mark.parametrize("f", _FUNCS)
@pytest.mark.parametrize("gap", [" ", "  ", "    ", "\t"])
def test_m07_spaces_are_not_counted_as_base64(f, gap):
    raw = _ED_HEAD + "A" * 19 + gap + "B" * 19
    assert f(raw) == raw


@pytest.mark.parametrize("f", _FUNCS)
@pytest.mark.parametrize("seed", range(3))
@pytest.mark.parametrize("tail", ["", " What", "  WhatIsThisLongDescriptionWordHere"])
def test_m07_space_separated_key_fully_masked(f, seed, tail):
    """空白分行的整把金鑰（後面可接說明字）：一個 20 字片段都不外露。"""
    b = _b64(_pkcs8(seed))
    out = f(" ".join(_wrap(b)) + tail)
    assert _leak(out, b) == 0, out[:120]


# ══════════════════════════════════════════════════════════════════
# M10（→ 現行目錄 tab 規則，SEC-r13 (b)）
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("f", _FUNCS)
@pytest.mark.parametrize("raw,want", [
    ("/home/u/a\tb\tc/x.toml", "***/x.toml"),                          # 同一段多個 tab
    ("'/home/u/my\\\\tdir/x.toml'", "'***/x.toml'"),                   # 兩層 repr：2 個反斜線＋t
    ("'/home/u/a\\\\tb\\\\tc/x.toml'", "'***/x.toml'"),
    ("'/home/u/my\\\\\\\\tdir/x.toml'", "'***/x.toml'"),               # 4 個反斜線＋t
    ("/a\\tb/c", "***/c"),                                             # 1 個反斜線＋t（目錄段只有這一段）
])
def test_m10_tab_dirs_masked_whole(f, raw, want):
    assert f(raw) == want


@pytest.mark.parametrize("f", _FUNCS)
@pytest.mark.parametrize("raw", ["說明\t***/foo/bar.toml", "token: abc\tdef ***/docs/a/b.md"])
def test_m10_tab_free_dirs_left_to_other_rules(f, raw):
    """目錄段都不含 tab → tab 規則原樣交還（同一段文字別處有 tab 也一樣）。"""
    assert f(raw) == raw


# ══════════════════════════════════════════════════════════════════
# M16 ／ SEC-r25 ②：`***重點***` 後面接長字串 —— 判不了標頭時只遮「≥3 行、同寬 ≥40」的整齊本體
# ══════════════════════════════════════════════════════════════════
def _mixed(rnd: random.Random, n: int) -> str:
    return "".join(rnd.choice(string.ascii_letters + string.digits) for _ in range(n))


@pytest.mark.parametrize("rows", [1, 2])
@pytest.mark.parametrize("width", [40, 64])
@pytest.mark.parametrize("seed", range(3))
def test_r25_2_bold_italic_then_one_or_two_long_lines_unchanged(rows, width, seed):
    """SEC-r25 ② 原實例（一行）與兩行：AI 回答原樣上畫面，`***粗斜體***` 不被跳脫。"""
    rnd = random.Random(seed)
    raw = "***重點***  \n" + "\n".join(_mixed(rnd, width) for _ in range(rows)) + "\n其他 ***粗斜體*** 文字"
    assert scrub_prose_secrets(raw) == raw
    assert scrub_secrets(raw) == raw
    assert scrub_qa_text(raw) == raw


@pytest.mark.parametrize("width", [16, 24, 39])
def test_m16_narrow_tidy_rows_after_mask_unchanged(width):
    """行寬 <40 的整齊多行（清單、代號表）不因前面有 `***` 就被吞。"""
    rnd = random.Random(width)
    raw = "***重點***\n" + "\n".join(_mixed(rnd, width) for _ in range(4))
    assert scrub_prose_secrets(raw) == raw
    assert scrub_secrets(raw) == raw


# ══════════════════════════════════════════════════════════════════
# 突變自證：每個突變都被本檔抓到
# ══════════════════════════════════════════════════════════════════
_MUTANTS = {
    "M05": ('r"(" + _TB + r"Authorization(', 'r"(" + r"Authorization('),
    "M07": (r'_B64_LINE_SPLIT_RE = re.compile(r"(?:\r?\n|(?:\\+r)?\\+n)[ \t]*|[ \t]+")',
            r'_B64_LINE_SPLIT_RE = re.compile(r"(?:\r?\n|(?:\\+r)?\\+n)[ \t]*")'),
    "M10a": ('    if _TAB_IN_DIR_RE.search(m.group("dirs")) is None:\n        return m.group(0)\n', ""),
    "M10b": (r'_TAB_ESC: str = r"(?:\t|\\{1,32}t)"', r'_TAB_ESC: str = r"(?:\t|\\t)"'),
    "M10c": (r'_TAB_ESC + _PATH_SEG + r"){0,64}"', r'_TAB_ESC + _PATH_SEG + r"){0,1}"'),
    "M10d": (r'_TAB_IN_DIR_RE = re.compile(r"\t|\\{1,32}t")', r'_TAB_IN_DIR_RE = re.compile(r"\t")'),
    "M16a": ("if _rows < 3 or _plain < 1", "if _rows < 2 or _plain < 1"),
    "M16b": ("_DER_LOOSE_TIDY_MIN: int = 40", "_DER_LOOSE_TIDY_MIN: int = 16"),
}


def _killed(mod) -> bool:
    rnd = random.Random(0)
    probes = [
        ("XAuthorization: tok123abc", None), ("my_Authorization: tok123abc", None),
        (_ED_HEAD + "A" * 19 + "    " + "B" * 19, None),
        ("/home/u/a\tb\tc/x.toml", "***/x.toml"), ("'/home/u/my\\\\tdir/x.toml'", "'***/x.toml'"),
        ("/a\\tb/c", "***/c"), ("說明\t***/foo/bar.toml", None),
        ("***重點***  \n" + "\n".join(_mixed(rnd, 40) for _ in range(2)), None),
        ("***重點***\n" + "\n".join(_mixed(rnd, 24) for _ in range(4)), None),
    ]
    for raw, want in probes:
        for f in ("scrub_secrets", "scrub_prose_secrets"):
            if getattr(mod, f)(raw) != (raw if want is None else want):
                return True
    b = _b64(_pkcs8(0))
    if _leak(mod.scrub_secrets(" ".join(_wrap(b)) + " What"), b):
        return True
    return False


@pytest.mark.parametrize("name", sorted(_MUTANTS))
def test_each_mutant_is_killed(name):
    from tests.test_sec_s3_0928 import _mutant
    import shared.secret_scrub as cur
    assert not _killed(cur), "前提：現行程式全部通過"
    assert _killed(_mutant(_MUTANTS[name])), name
