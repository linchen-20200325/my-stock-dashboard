"""批 S3（SEC-r13／SEC-r14／SEC-r15／SEC-r17／SEC-r18；2026-09-28 派工、2026-10-01 重做）：`scrub_secrets` 補洞。

- SEC-r13 (a) 方括號取值的 `Authorization`（`headers['Authorization'] = '…'`）→ 值遮掉（`_AUTH_SUBSCRIPT_RE`）；
          (b) 目錄名含 tab（真 tab，或 `repr` 的 `\\t`、多層跳脫）→ 整條路徑一起判、目錄整串遮（`_POSIX_TAB_DIR_RE`）；
          (c) 沒有結尾斜線的空白路徑、(d) 40 萬字記憶體峰值 → 只在檔頭揭露（並以測試釘住）。
- SEC-r14 無標頭 DER「宣告 ≥ 實際」：金鑰後接長 base64、私鑰＋憑證／憑證鏈 → 第二道規則依宣告長度逐段判
  （`_DER_B64_LOOSE_RE`），不再整把外露。
- SEC-r15 BER 不定長（`30 80`）→ 只補檔頭揭露（並以測試釘住仍外露）。
- SEC-r17 換行寬度 16～39、第一行被前綴折短、行尾空白、只用 CR、JSON 的 `\\/` → 第二道規則認得；
  寬度 <16、第一行只剩 1 字、縮排 >16 個空白仍不認得 → 檔頭揭露（並以測試釘住）。
- SEC-r18（測試）見 `tests/test_sec_s3_0928.py`（`_is_masking_of` 收緊、5 字上限守衛）。
- 批 S3 QA 意見：B1 記憶體揭露只對量過的形態成立（本檔量 `_MEM_FORMS` 全部形態）、B2 ReDoS 守衛量 CPU 時間
  取三次最小值、F1 判不了標頭的整齊本體「只加遮罩」、Python 3.10 回退（佔有型量詞以實際編譯探測）。

⭐ 硬性要求：任何輸入都不得比 **e23ff2f 凍結副本**少遮（`tests/fixtures/secret_scrub_e23ff2f.py`，逐位元組核對）；
真實 UI 字串常值輸出變動數 0。判準沿用 `tests/test_sec_s3_0928._is_masking_of`。
"""
from __future__ import annotations

import base64
import functools
import hashlib
import importlib.util
import json
import pathlib
import random
import re
import subprocess
import sys

import pytest

from shared import secret_scrub as SSC
from shared.secret_scrub import MASK, scrub_prose_secrets, scrub_secrets
from tests.test_sec_s3_0928 import _is_masking_of, _mutant, _secret_corpus, _ui_corpus

_ROOT = pathlib.Path(__file__).resolve().parents[1]

# ══════════════════════════════════════════════════════════════════
# 基準：e23ff2f 的凍結副本
# ══════════════════════════════════════════════════════════════════
_FIXTURE = _ROOT / "tests" / "fixtures" / "secret_scrub_e23ff2f.py"
_FIXTURE_MARKER = "# ═══ 原檔開始 ═══\n"
#: `git show e23ff2f:shared/secret_scrub.py | sha256sum`（blob 4d49be42351e472edef71dee678d428bd2232c54）。
_E23_SHA256 = "50824ec9a033d6e7e33f732cbe2bb823f99432dd9559fa50c84caf1e32b3a427"


def _load_e23():
    spec = importlib.util.spec_from_file_location("_secret_scrub_e23ff2f", _FIXTURE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_E23 = _load_e23()
_OLD = _E23.scrub_secrets


def test_baseline_is_the_frozen_e23ff2f_file_byte_for_byte():
    raw = _FIXTURE.read_bytes()
    marker = _FIXTURE_MARKER.encode("utf-8")
    assert raw.count(marker) == 1
    assert hashlib.sha256(raw.split(marker, 1)[1]).hexdigest() == _E23_SHA256
    assert _OLD is not scrub_secrets and _E23.__file__ == str(_FIXTURE)


def _b64chars(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9+/]", "", s)


# ══════════════════════════════════════════════════════════════════
# SEC-r13 (a)：方括號取值的 Authorization
# ══════════════════════════════════════════════════════════════════
_TOK = "tOk9S3r13AbCdEfGh"
#: (原文, 期望輸出)
_AUTH_SUB = [
    (f"headers['Authorization']='{_TOK}'", "headers['Authorization']='***'"),
    (f"headers['Authorization']='Bearer {_TOK}'", "headers['Authorization']='***'"),   # 舊版只遮權杖
    (f'headers["Authorization"] = "Basic {_TOK}"', 'headers["Authorization"] = "***"'),
    (f"h[b'Authorization'] == b'{_TOK}'", "h[b'Authorization'] == b'***'"),
    (f"h[ 'authorization' ] != '{_TOK}'", "h[ 'authorization' ] != '***'"),
    (f"r.headers['Authorization'] = {_TOK}", "r.headers['Authorization'] = ***"),
    (f"req.headers[u'Authorization'] = rb'{_TOK}' # x", "req.headers[u'Authorization'] = rb'***' # x"),
    (repr({"k": f"h['Authorization'] = '{_TOK}'"}), "{'k': \"h['Authorization'] = '***'\"}"),
    (f"x = h[\\'Authorization\\'] = \\'{_TOK}\\', y", "x = h[\\'Authorization\\'] = \\'***\\', y"),
    (f"h['Authorization'] = '{_TOK}", "h['Authorization'] = ***"),          # 未收尾 → 遮到行尾
]


@pytest.mark.parametrize("raw,want", _AUTH_SUB)
def test_r13a_authorization_subscript_masked(raw, want):
    assert scrub_secrets(raw) == want
    assert _TOK not in scrub_prose_secrets(raw)
    assert _TOK in _OLD(raw) or "Bearer" in raw, "前提：e23ff2f 確實外露"


@pytest.mark.parametrize("raw", [
    "headers[name] = 'x'", "headers['Accept'] = 'text/html'", "h[Authorization] = 'x'",
    "h['Authorization']", "print(h['Authorization'])", "h['Authorization'] in ('a', 'b')",
    "a[b'x'] = b'y'", "見 [Authorization] 說明",
])
def test_r13a_ordinary_text_unchanged(raw):
    assert scrub_secrets(raw) == _OLD(raw)


def test_r13a_string_prefix_must_touch_the_quote():
    """字串前綴只在緊接引號時才算（批 S3 QA N2：前綴排除太寬）—— `b` 後面不是引號就不是前綴。"""
    assert scrub_secrets(f"h[b'Authorization'] = b'{_TOK}'") == "h[b'Authorization'] = b'***'"
    assert scrub_secrets("h[bx'Authorization'] = 'v'") == _OLD("h[bx'Authorization'] = 'v'")
    m = _mutant(('_STR_PFX: str = r"(?:[bBrRuUfF]{1,2}(?=\\\\{0,4}[\\"\']))?"', '_STR_PFX: str = r""'))
    assert _TOK in m.scrub_secrets(f"h[b'Authorization'] = '{_TOK}'"), "前提：拿掉前綴，`b'…'` 那種就外露"


# ══════════════════════════════════════════════════════════════════
# SEC-r13 (b)：目錄名含 tab
# ══════════════════════════════════════════════════════════════════
_TAB_PATH = "/home/aliceS3t/my\tdirS3/app/secrets.toml"


def _repr_n(s: str, n: int) -> str:
    for _ in range(n):
        s = repr(s)
    return s


@pytest.mark.parametrize("levels", [0, 1, 2, 3, 4])
def test_r13b_tab_in_directory_name_masked(levels):
    raw = _repr_n(_TAB_PATH, levels)
    out = scrub_secrets(raw)
    assert not [g for g in ("aliceS3t", "my", "dirS3", "app/") if g in out], out
    assert "secrets.toml" in out and MASK in out
    assert "dirS3" in _OLD(raw), "前提：e23ff2f 外露 tab 後面的目錄"


@pytest.mark.parametrize("raw,want", [
    ("讀不到 /Users/a\tb/x.toml 請檢查", "讀不到 ***/x.toml 請檢查"),
    ("FileNotFoundError: '/home/u/a\tb/c d/x.toml'", "FileNotFoundError: '***/x.toml'"),
    ("see @/home/u/a\tb/x.toml", "see @***/x.toml"),
    ("/a\tb/c\td/e/x", "***/x"),
])
def test_r13b_whole_path_is_judged_together(raw, want):
    """整條路徑一起判：任一目錄段含 tab → 目錄整串一個遮罩、只留末段。"""
    assert scrub_secrets(raw) == want


@pytest.mark.parametrize("raw", [
    "a\tb/c", "欄位\t值/股", "/home/u/my\tfile.toml", "x\t/home/u/y.toml", "/home/u/x.toml\tok",
    "price\t80/20", "\t/a/b", "col1\\tcol2/x",
])
def test_r13b_no_tab_inside_a_directory_unchanged(raw):
    assert scrub_secrets(raw) == _OLD(raw)


def test_r13b_escaped_tab_cap_is_32_backslashes():
    raw = "/home/u/a" + "\\" * 32 + "tb/x.toml"
    assert scrub_secrets(raw) == "***/x.toml"
    raw33 = "/home/u/a" + "\\" * 33 + "tb/x.toml"
    assert scrub_secrets(raw33) == _OLD(raw33)
    m = _mutant(('_TAB_ESC: str = r"(?:\\t|\\\\{1,32}t)"', '_TAB_ESC: str = r"(?:\\t|\\\\{1,1}t)"'))
    assert "dirS3" in m.scrub_secrets(_repr_n(_TAB_PATH, 2)), "前提：只認一層跳脫時，兩層 repr 外露"


# ══════════════════════════════════════════════════════════════════
# SEC-r13 (c)(d)、SEC-r15：只揭露 —— 以測試釘住「仍外露」與檔頭字樣
# ══════════════════════════════════════════════════════════════════
_DOC = SSC.__doc__ or ""


def test_r13c_no_trailing_slash_last_segment_kept_and_disclosed():
    assert scrub_secrets("/Users/Jane Doe") == "***/Jane Doe" == _OLD("/Users/Jane Doe")
    assert "`/Users/Jane Doe`" in _DOC and "SEC-r13 (c)" in _DOC


def test_r15_ber_indefinite_length_still_leaks_and_disclosed():
    ber = base64.b64encode(bytes.fromhex("3080020100") + random.Random(15).randbytes(900)).decode()
    raw = "\n".join(ber[i:i + 64] for i in range(0, len(ber), 64))
    assert scrub_secrets(raw) == raw, "BER 不定長認不出來（DER 不允許不定長）—— 若改了請同步改檔頭"
    assert "`30 80`" in _DOC and "SEC-r15" in _DOC


def test_r13d_memory_disclosure_present():
    assert "SEC-r13 (d)" in _DOC and "⛔ 不是上限" in _DOC and "Python 3.10" in _DOC


# ══════════════════════════════════════════════════════════════════
# 無標頭 DER 樣本（結構一致的仿金鑰／憑證，固定種子，⛔ 不是真金鑰）
# ══════════════════════════════════════════════════════════════════
def _seq(body: bytes) -> bytes:
    n = len(body)
    if n < 0x80:
        return b"\x30" + bytes([n]) + body
    ln = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return b"\x30" + bytes([0x80 | len(ln)]) + ln + body


def _pkcs8(seed: int) -> bytes:
    return _seq(bytes.fromhex("020100300d06092a864886f70d0101010500")
                + random.Random(seed).randbytes(1150 + seed % 64))


def _pkcs1(seed: int) -> bytes:
    return _seq(b"\x02\x01\x00" + random.Random(seed + 7).randbytes(1180 + seed % 64))


def _cert(seed: int) -> bytes:
    return _seq(b"\x30\x82\x03\x00" + random.Random(seed + 99).randbytes(0x300) + random.Random(seed).randbytes(40))


def _b64(der: bytes) -> str:
    return base64.b64encode(der).decode()


def _wrap(b64: str, w: int = 64) -> list[str]:
    return [b64[i:i + w] for i in range(0, len(b64), w)]


def _leak(out: str, b64: str) -> int:
    """`b64` 有幾個 20 字片段原樣留在 `out` 裡（換行、跳脫、空白、`\\/` 都先拿掉再比）。"""
    flat = out.replace("\\/", "/")
    flat = re.sub(r"\\+[nr]|[\s\"'\\]", "", flat)
    return sum(1 for i in range(0, len(b64) - 20, 20) if b64[i:i + 20] in flat)


# ══════════════════════════════════════════════════════════════════
# SEC-r14：宣告長度 < 實際長度 → 逐段判
# ══════════════════════════════════════════════════════════════════
def _arrangements(seed: int) -> dict[str, tuple[str, list[str]]]:
    """(原文, 必須全遮的 base64 本體清單)。"""
    k8, k1, c1, c2 = _b64(_pkcs8(seed)), _b64(_pkcs1(seed)), _b64(_cert(seed)), _b64(_cert(seed + 1))
    tail = _b64(random.Random(seed + 5).randbytes(600))
    return {
        "pkcs8+cert": ("\n".join(_wrap(k8) + _wrap(c1)), [k8, c1]),
        "pkcs1+cert": ("\n".join(_wrap(k1) + _wrap(c1)), [k1, c1]),
        "pkcs8+chain": ("\n".join(_wrap(k8) + _wrap(c1) + _wrap(c2)), [k8, c1, c2]),
        "cert+pkcs8": ("\n".join(_wrap(c1) + _wrap(k8)), [c1, k8]),
        "pkcs8+long_b64": ("\n".join(_wrap(k8) + _wrap(tail)), [k8]),
        "pkcs1+long_b64_crlf": ("\r\n".join(_wrap(k1) + _wrap(tail)), [k1]),
    }


@pytest.mark.parametrize("name", sorted(_arrangements(0)))
def test_r14_declared_length_shorter_than_seen_no_longer_leaks_the_key(name):
    leaked_before = 0
    for seed in range(120):
        raw, must = _arrangements(seed)[name]
        out = scrub_secrets(raw)
        assert not [b for b in must if _leak(out, b)], (name, seed)
        assert _is_masking_of(out, _OLD(raw)), (name, seed)
        leaked_before += _leak(_OLD(raw), must[0]) > 0
    #: e23ff2f 只在「金鑰最後一行 ≥40 字」時外露（短的最後一行會讓第一道規則在那裡收尾、整把照遮）。
    assert leaked_before >= 12, "前提：e23ff2f 在這種排列確實常外露"


def test_r14_only_the_declared_lines_then_judge_the_rest():
    """金鑰後面接著一段不是 DER 的 base64（第一行不是 `M[A-P]`）→ 金鑰遮掉、後面那段照原樣（另判）。"""
    for seed in range(40):
        k = _b64(_pkcs8(seed))
        tail = "Zz" + _b64(random.Random(seed).randbytes(300))[2:]
        lines = _wrap(tail)
        if any(ln.startswith("/") for ln in lines) or len(lines[-1]) < 16:
            continue
        raw = "\n".join(_wrap(k)) + "\n" + "\n".join(lines)
        if _OLD(raw) != raw:
            #: 金鑰最後一行短 → 第一道規則已整把遮掉；後面那段接在遮罩後面，屬檔頭揭露的多遮方向，不在本測試範圍。
            continue
        assert scrub_secrets(raw) == MASK + "\n" + "\n".join(lines), seed
        return
    pytest.fail("找不到合用的種子")


# ══════════════════════════════════════════════════════════════════
# SEC-r17：排版
# ══════════════════════════════════════════════════════════════════
def _first_short(b64: str, n: int, w: int = 64) -> list[str]:
    return [b64[:n]] + _wrap(b64[n:], w)


_LAYOUTS = {
    **{f"width{w}": (lambda b, w=w: "\n".join(_wrap(b, w))) for w in (16, 20, 24, 32, 39)},
    "prefix_short_first": lambda b: "private: " + "\n".join(_first_short(b, 7)),
    "first_line_2_chars": lambda b: "\n".join(_first_short(b, 2)),
    "trailing_space": lambda b: " \n".join(_wrap(b)),
    "trailing_tab_crlf": lambda b: "\t\r\n".join(_wrap(b)),
    "cr_only": lambda b: "\r".join(_wrap(b)),
    "json_slash": lambda b: json.dumps("\n".join(_wrap(b))).replace("/", "\\/"),
    "repr_width32": lambda b: repr("\n".join(_wrap(b, 32))),
    "field_then_body": lambda b: "private_key: " + "\n".join(_wrap(b)),
}


@pytest.mark.parametrize("layout", sorted(_LAYOUTS))
def test_r17_layouts_masked(layout):
    enc = _LAYOUTS[layout]
    before = 0
    for seed in range(60):
        for mk in (_pkcs8, _pkcs1, _cert):
            b = _b64(mk(seed))
            raw = enc(b)
            out = scrub_secrets(raw)
            assert _leak(out, b) == 0, (layout, seed, mk.__name__, out[:120])
            assert _is_masking_of(out, _OLD(raw))
            before += _leak(_OLD(raw), b) > 0
    assert before >= 150, "前提：e23ff2f 在這種排版大多外露"


@pytest.mark.parametrize("layout,enc", [
    ("width12", lambda b: "\n".join(_wrap(b, 12))),
    ("first_line_1_char", lambda b: "\n".join(_first_short(b, 1))),
    ("indent20", lambda b: ("\n" + " " * 20).join(_wrap(b))),
])
def test_r17_disclosed_boundaries_still_leak(layout, enc):
    """檔頭揭露的邊界（寬度 <16、第一行只剩 1 字、縮排 >16）：仍外露 —— 改了請同步改檔頭。"""
    b = _b64(_pkcs8(3))
    assert _leak(scrub_secrets(enc(b)), b) > 0
    assert "換行寬度 <16" in _DOC and "第一行只剩 1 個字" in _DOC and "縮排超過 16 個空白" in _DOC


def test_r17_line_min_is_16():
    b = _b64(_pkcs8(4))
    raw = "\n".join(_wrap(b, 16))
    assert _leak(scrub_secrets(raw), b) == 0
    m = _mutant(("_DER_LOOSE_LINE_MIN: int = 16", "_DER_LOOSE_LINE_MIN: int = 17"))
    assert _leak(m.scrub_secrets(raw), b) > 0, "前提：下限改 17，寬 16 的本體外露"


# ══════════════════════════════════════════════════════════════════
# 批 S3 QA F1：開頭 16 字判不了標頭（前面規則先遮掉）→ 整齊本體「只加遮罩」
# ══════════════════════════════════════════════════════════════════
def _f1_samples(n: int = 6) -> list[tuple[str, str]]:
    """首行被前綴折短到 15 字、下一行以 `/` 開頭（前面的路徑規則先把它遮成 `***/…`）的仿 EC 私鑰。

    開頭 16 個 base64 字裡就有遮罩 ⇒ 判不了標頭 ⇒ e23ff2f 與第一道規則都整把外露（批 S3 QA F1 的形態）。
    """
    out = []
    for seed in range(6000):
        der = _seq(b"\x02\x01\x01\x04\x82\x02\x50" + random.Random(seed).randbytes(0x250))
        b = _b64(der)
        lines = _first_short(b, 15)
        raw = "key " + "\n".join(lines)
        if lines[1].startswith("/") and "***" in _OLD(raw).split("\n")[1]:
            out.append((raw, b))
            if len(out) == n:
                break
    return out


def test_f1_short_first_line_then_premasked_line_masked():
    samples = _f1_samples()
    assert len(samples) >= 3
    for raw, b in samples:
        assert _leak(_OLD(raw), b) > 0, "前提：e23ff2f 外露"
        out = scrub_secrets(raw)
        assert _leak(out, b) == 0 and _is_masking_of(out, _OLD(raw)), out[:120]
    m = _mutant(("_DER_LOOSE_TIDY_MIN: int = 40", "_DER_LOOSE_TIDY_MIN: int = 999"))
    assert _leak(m.scrub_secrets(samples[0][0]), samples[0][1]) > 0, "前提：拿掉 F1 判法即外露"


def test_f1_untidy_lines_after_a_mask_unchanged():
    """判不了標頭、行寬又不整齊（一般文字、長短不一的清單）→ 原樣。"""
    for raw in ("password: ***\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nBBBBBBBBBBBBBBBBBBBB\nCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
                "***\nabcdefghijklmnopqrstuvwxyz\n" + "x" * 30 + "\nend",
                "***\n" + "\n".join(["A" * 39] * 5)):
        assert scrub_secrets(raw) == _OLD(raw), raw[:40]


def test_tidy_needs_3_plain_lines_of_the_same_width():
    """判不了標頭時，「整齊」至少要 3 行同寬（中間行）—— 只有 1～2 行照原樣。"""
    for raw in ("***\n" + "A" * 40 + "\n" + "B" * 40, "***\n" + "A" * 40 + "\n" + "B" * 40 + "\n" + "C" * 40):
        assert scrub_secrets(raw) == _OLD(raw) == raw
    raw4 = "***\n" + "\n".join(c * 40 for c in "ABCD") + "\nE"
    assert scrub_secrets(raw4) == MASK


def test_loose_middle_lines_must_share_width():
    """解得出標頭、但中間各行寬度不一（不像換行排版的本體）→ 原樣。"""
    head = _b64(_pkcs8(11))[:20]
    raw = "\n".join([head, "A" * 30, "B" * 45, "C" * 20, "D" * 33])
    assert scrub_secrets(raw) == _OLD(raw) == raw
    tidy = "\n".join([head, "A" * 30, "B" * 30, "C" * 30, "D" * 33])
    assert scrub_secrets(tidy) == MASK


def test_one_line_key_followed_by_other_base64_lines():
    """一行就是一把完整金鑰（Ed25519，64 字）、後面再接別的 base64 行 → 只遮那一行（宣告只涵蓋第一行也算）。"""
    ed = _b64(bytes.fromhex("302e020100300506032b657004220420") + random.Random(7).randbytes(32))
    tail = ["Q" + _b64(random.Random(s).randbytes(48))[1:] for s in range(3)]
    raw = "\n".join([ed] + tail)
    assert ed in _OLD(raw), "前提：e23ff2f 外露（第一道規則看到宣告 < 實際，整段放行）"
    assert scrub_secrets(raw) == "\n".join([MASK] + tail)


def test_tab_rule_only_acts_when_a_directory_has_a_tab():
    """沒有 tab 的路徑原樣交還（那是舊規則的職責）—— 拔掉舊的 `@` 規則，`@/home/…` 仍外露。"""
    m = _mutant(("    (_POSIX_PATH_EXTRA_RE, lambda m: MASK + \"/\" + (m.group(1) or \"\")),\n", ""))
    #: 字串裡另有一個 tab（不在目錄名裡）⇒ tab 規則確實會跑，但不得替舊規則遮。
    assert "aliceS3" in m.scrub_secrets("see @/home/aliceS3/.streamlit/secrets.toml\tok")


# ══════════════════════════════════════════════════════════════════
# 一般文字 ⛔ 不誤遮
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("raw", [
    "MACD\nAAAAAAAAAAAAAAAAAAAAAAAA\nBBBBBBBBBBBBBBBBBBBBBBBB",
    "MA20/MA60\n2330 2317 2454 2412 2308\n均線糾結",
    "\n".join(["MSFT", "AAPL", "GOOG"] + ["0050,0056,00878,00919"] * 4),
    "\n".join(hashlib.sha256(str(i).encode()).hexdigest() for i in range(6)),
    "Mozilla/5.0 (X11; Linux x86_64)\nAppleWebKit/537.36 (KHTML, like Gecko)\nChrome/120.0 Safari/537.36",
    _b64(b"0x1234abcd, 0x5678ef01, 0x9abcdef0, 0x13572468, 0x24681357" * 3)[:64] + "\n" + "Q" * 64,
])
def test_loose_der_ordinary_text_unchanged(raw):
    assert scrub_secrets(raw) == _OLD(raw)


# ══════════════════════════════════════════════════════════════════
# 每條新規則都是承重的（N5：外露方向的突變要抓得到）
# ══════════════════════════════════════════════════════════════════
_NEW_LINE = {
    "der_loose": ("_der_loose_spans(_t0))",
                  lambda: ("\n".join(_wrap(_b64(_pkcs8(1)), 32)), _b64(_pkcs8(1)))),
    "tab_dir": ("    (_POSIX_TAB_DIR_RE, _mask_tab_dirs),\n", lambda: (_TAB_PATH, "dirS3")),
    "auth_sub": ("    (_AUTH_SUBSCRIPT_RE, _mask_auth_subscript),\n", lambda: (_AUTH_SUB[0][0], _TOK)),
}


@pytest.mark.parametrize("rule", sorted(_NEW_LINE))
def test_dropping_each_new_rule_leaks(rule):
    line, sample = _NEW_LINE[rule]
    raw, gone = sample()
    m = _mutant((line, "[])" if rule == "der_loose" else ""))
    if rule == "der_loose":
        assert _leak(scrub_secrets(raw), gone) == 0 and _leak(m.scrub_secrets(raw), gone) > 0
    else:
        assert gone not in scrub_secrets(raw) and gone in m.scrub_secrets(raw)


@pytest.mark.parametrize("old,new", [
    ("        _need = -(-_total * 4 // 3)", "        _need = -(-_total * 2 // 3)"),   # 涵蓋行數少算
    ("        _i += 1\n    return _out", "        _i = _n\n    return _out"),        # 其餘不另判
    ("            return _ps[_k + 1] - _ps[_i] + _w * (_mc[_k + 1] - _mc[_i])",
     "            return _ps[_k + 1] - _ps[_i] + 999 * (_mc[_k + 1] - _mc[_i])"),         # 遮罩行寬估錯
])
def test_exposure_direction_mutants_are_caught(old, new):
    """外露方向的突變（N5）：每一個都至少讓一個樣本外露。"""
    m = _mutant((old, new))
    hit = 0
    for seed in range(30):
        for name, (raw, must) in _arrangements(seed).items():
            out = m.scrub_secrets(raw)
            hit += any(_leak(out, b) for b in must)
        for raw, b in _f1_samples(3):
            hit += _leak(m.scrub_secrets(raw), b) > 0
        #: S3 QA F2：EC 金鑰＋憑證、行尾空白（金鑰第二行常先被路徑規則遮掉 ⇒ 涵蓋長度要靠行寬估計）。
        for enc in _F2_LAYOUTS.values():
            key, cert = _ec_p256(seed), _ec_cert(seed)
            out = m.scrub_secrets(enc(_wrap(_b64(key)) + _wrap(_b64(cert))))
            hit += _leak(out, _b64(key)) > 0 or _leak(out, _b64(cert)) > 0
        if hit:
            break
    assert hit, (old, new)


# ══════════════════════════════════════════════════════════════════
# Python 3.10 回退：佔有型量詞以實際編譯探測（M26：結構守衛，fast）
# ══════════════════════════════════════════════════════════════════
def test_possessive_quantifiers_used_where_supported():
    try:
        re.compile(r"a*+")
        supported = True
    except re.error:  # pragma: no cover
        supported = False
    assert SSC._POSS == ("+" if supported else "")
    if supported:
        for rx in (SSC._AUTH_SUBSCRIPT_RE, SSC._POSIX_TAB_DIR_RE, SSC._DER_B64_LOOSE_RE):
            assert re.search(r"[*}]\+", rx.pattern), rx.pattern[:80]


def test_python310_fallback_same_results():
    """編譯探測失敗（模擬 3.10）→ `_POSS` 為空字串、一般量詞；比對結果與現行逐字相同。"""
    m = _mutant(('    re.compile(r"a*+")\n', '    re.compile(r"a*+(")\n'))
    assert m._POSS == "" and not re.search(r"[*}]\+", m._DER_B64_LOOSE_RE.pattern)
    samples = [r for r, _ in _AUTH_SUB] + [_repr_n(_TAB_PATH, k) for k in range(4)]
    for seed in range(5):
        samples += [raw for raw, _ in _arrangements(seed).values()]
        samples += [enc(_b64(_pkcs8(seed))) for enc in _LAYOUTS.values()]
    samples += sorted(_secret_corpus())[:3000]
    assert [m.scrub_secrets(s) for s in samples] == [scrub_secrets(s) for s in samples]


def test_header_mentions_the_python310_probe():
    src = pathlib.Path(SSC.__file__).read_text(encoding="utf-8")
    assert "sys.version_info" not in src.split('"""', 2)[2].split("#: 佔有型量詞")[0]
    assert 're.compile(r"a*+")' in src


# ══════════════════════════════════════════════════════════════════
# ⭐ 語料回歸（對 e23ff2f 凍結副本）
# ══════════════════════════════════════════════════════════════════
@functools.lru_cache(maxsize=1)
def _batch_corpus() -> frozenset[str]:
    out = set(_secret_corpus())
    out.update(r for r, _ in _AUTH_SUB)
    out.update(_repr_n(_TAB_PATH, k) for k in range(5))
    for seed in range(3):
        out.update(raw for raw, _ in _arrangements(seed).values())
        out.update(enc(_b64(_pkcs8(seed))) for enc in _LAYOUTS.values())
    rnd = random.Random(20261001)
    alpha = (list("ab01MIAPz+/=_ :=\"'\\/[]\t\r\n.*") + ["Authorization", "\\t", "\\/", "***", "MIIEvQIBADANBgkq",
                                                          "/home/u/", "headers[", "] = ", "A" * 16, "A" * 40])
    for _ in range(6000):
        out.add("".join(rnd.choice(alpha) for _ in range(rnd.randint(1, 40))))
    #: S3 QA 第三輪：DER 行之後緊接路徑（含空白／tab／Windows／UNC／`~/`）—— 這一類不得再比 e23ff2f 少遮。
    out.update(_r3_cases())
    return frozenset(out)


def test_never_masks_less_than_e23ff2f():
    worse = [r for r in _batch_corpus() | _ui_corpus() if not _is_masking_of(scrub_secrets(r), _OLD(r))]
    assert not worse, [(r[:80], _OLD(r)[:80], scrub_secrets(r)[:80]) for r in worse[:5]]


def test_real_ui_string_constants_unchanged_vs_e23ff2f():
    changed = sorted(r for r in _ui_corpus() if scrub_secrets(r) != _OLD(r))
    assert not changed, [(r[:120], scrub_secrets(r)[:120]) for r in changed[:10]]


@functools.lru_cache(maxsize=1)
def _tracked_md_lines() -> tuple[str, ...]:
    """根目錄與 `docs/` 底下的 `.md` 段落（純 Python 掃描；`tests/test_zz_test_portability` 禁止呼叫 git）。

    ⚠️ 只掃這兩處（都是 repo 追蹤的文件區），不 `rglob` 整個工作目錄 —— 未追蹤檔混進語料會讓本機與 CI 結果不同
    （SEC-r26 指出的同型問題）。
    """
    files = [*sorted(_ROOT.glob("*.md")), *sorted(_ROOT.joinpath("docs").rglob("*.md"))]
    out: list[str] = []
    for p in files:
        out.extend(p.read_text(encoding="utf-8", errors="replace").split("\n\n"))
    return tuple(out)


def test_tracked_markdown_paragraphs_unchanged_vs_e23ff2f():
    paras = _tracked_md_lines()
    assert len(paras) > 1000
    changed = [p for p in paras if scrub_secrets(p) != _OLD(p)]
    assert not changed, [(p[:120], scrub_secrets(p)[:120]) for p in changed[:5]]


# ══════════════════════════════════════════════════════════════════
# ReDoS（批 S3 QA B2：量 CPU 時間、取三次最小值 —— 機器滿載時不誤紅）
# ══════════════════════════════════════════════════════════════════
_REDOS_N = 50_000
_B = "\\"
_UNITS = (
    "[", "['Authorization'] = '", "[b'Authorization'] = b'", "[" + _B * 4 + "'Authorization" + _B * 4 + "'] = ",
    "['Authorization'] = " + _B * 4 + "'x", "['Authorization'] == \"" + _B * 2, "[ 'Authorization' ]",
    "/a\tb", "/a" + _B * 40 + "t", "***/a\tb/", " /\ta/", "/a" + _B + "t" + _B + "t/", "@/a\t",
    "MA", "MA\n", "MA" + "A" * 15 + "\n", "M" + "A" * 16 + "\n", "A" * 16 + "\n", "***\n", "***" + "A" * 13 + "\n",
    "MA" + _B + "/", _B + "/" * 3, "MAAA \r\n", "MA\r", "A" * 16 + " " * 17 + "\n", "MA" + _B * 33 + "n",
    "\n" + "A" * 15, "***\nA", "MA" + "A" * 62 + "\n" + "/",
)
_SCRIPT = (
    "import json, sys, time\nimport shared.secret_scrub as S\nout = {}\n"
    "rules = {'der': lambda t: S._der_loose_spans(t), 'tab': lambda t: S._POSIX_TAB_DIR_RE.sub(S._mask_tab_dirs, t),\n"
    "         'auth': lambda t: S._AUTH_SUBSCRIPT_RE.sub(S._mask_auth_subscript, t)}\n"
    "def cpu(f):\n"
    "    best = None\n"
    "    for _ in range(3):\n"
    "        t = time.process_time(); f(); d = time.process_time() - t\n"
    "        best = d if best is None else min(best, d)\n"
    "    return best\n"
    "for name, text in json.load(sys.stdin):\n"
    "    out[name] = cpu(lambda: S.scrub_secrets(text))\n"
    "    for rn, fn in rules.items():\n"
    "        out[name + '/' + rn] = cpu(lambda: fn(text))\n"
    "print(json.dumps(out))\n")


def test_new_rules_are_linear():
    cases = [[f"u{i}", (u * (_REDOS_N // len(u) + 1))[:_REDOS_N]] for i, u in enumerate(_UNITS)]
    key = "\n".join(_wrap(_b64(_pkcs8(9)), 20))
    cases += [["keys", (key + "\n") * (_REDOS_N // len(key))],
              ["key_lines_masked", ("***" + "A" * 61 + "\n") * (_REDOS_N // 65)],
              ["auth_open", "h['Authorization'] = '" + "x" * _REDOS_N],
              ["auth_concat", "h['Authorization'] = 'x'" + " + 'y'" * (_REDOS_N // 6)],
              ["auth_tq", 'h["Authorization"] = """' + "x" * _REDOS_N],
              #: S3 QA F1：一行一把的 Ed25519 清單（舊寫法遞迴、且比 e23ff2f 慢數倍）。
              ["ed25519_rows", "\n".join(["MC4CAQAwBQYDK2VwBCIEI" + "A" * 43] * (_REDOS_N // 65))]]
    r = subprocess.run([sys.executable, "-c", _SCRIPT], input=json.dumps(cases), capture_output=True,
                       text=True, timeout=300, cwd=str(_ROOT))
    assert r.returncode == 0, r.stderr[-2000:]
    slow = {k: v for k, v in json.loads(r.stdout).items() if v > 2.0}
    assert not slow, slow


# ══════════════════════════════════════════════════════════════════
# SEC-r13 (d)／批 S3 QA B1：記憶體峰值（slow：每個形態各開兩個子程序）
# ══════════════════════════════════════════════════════════════════
_MEM_N = 400_000
#: 量法：`tracemalloc` 的峰值（`re` 的回溯堆疊經 `PyMem_*` 配置、會被追蹤）。⚠️ 不用 `ru_maxrss` ——
#: 它是行程的最高水位，先前（產生／解析輸入時）釋放的記憶體會被 `re` 重用，量不出增量。


def _mem_forms() -> dict[str, str]:
    N = _MEM_N
    b = base64.b64encode(random.Random(1).randbytes(N)).decode()
    f = {
        "der_lines64": "MIIE" + "\n".join(_wrap(b, 64)), "der_lines20": "MIIE" + "\n".join(_wrap(b, 20)),
        "der_one": "MA" + "A" * N, "der_cr_trail": "MIIE" + " \r".join(_wrap(b, 64)),
        "json_slash": "MIIE" + "\\n".join(_wrap(b, 64)).replace("/", "\\/"), "json_slash_run": "MIIE" + "A\\/" * N,
        "short_lines": "MA" + "\nAAAAAAAAAAAAAAAA" * N, "mask_lines": "\n".join(["***" + "A" * 61] * N),
        "tab_path": "/a\tb" * N, "tab_path_esc": "/a\\\\tb" * N, "tab_path_words": "/x/a\tb/c " * N,
        "space_path": "/" + "a " * N, "auth_open_sq": "[ 'Authorization' ] = '" + "x" * N,
        "auth_open_dq": '["Authorization"] = "' + "\\x" * N, "auth_open_eq": "[\\'Authorization\\'] = \\'" + "x" * N,
        "auth_many": "['Authorization'] = 'x' " * N, "prose": "這是一般文字 MA20/MA60 ，" * N,
        "deep_bs": "\\" * 7 + "'password" + "\\" * 7 + "': " + "\\" * 7 + "'" + "x" * N,
        "colon_open": "'password': '" + "x" * N, "posix_many": "/a/b/c/d.toml " * N, "b64_plain": b,
    }
    return {k: v[:N] for k, v in f.items()}


def _peak_mb(fn, text: str) -> float:
    import tracemalloc
    started = tracemalloc.is_tracing()
    if not started:
        tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        base = tracemalloc.get_traced_memory()[0]
        fn(text)
        return (tracemalloc.get_traced_memory()[1] - base) / (1 << 20)
    finally:
        if not started:
            tracemalloc.stop()


@pytest.mark.slow
def test_r13d_new_rules_add_little_memory_on_measured_forms():
    """檔頭寫的「21 種形態」＝ `_mem_forms()` 全部；每一種都比 e23ff2f 多 ≤ 5 MB（檔頭同數字）。

    量測紀錄（2026-10-01，tracemalloc）：Python 3.11 最大 +1.9 MB（auth_many）；真 Python 3.10 最大 +4.8 MB（json_slash）。
    上限 5 MB 對 3.11 留 2.6 倍餘裕。
    """
    forms = _mem_forms()
    assert len(forms) == 21 and "21 種形態" in _DOC and "≤ 5 MB" in _DOC
    worse = {n: (_peak_mb(_OLD, t), _peak_mb(scrub_secrets, t)) for n, t in forms.items()}
    worse = {n: v for n, v in worse.items() if v[1] - v[0] > 5}
    assert not worse, worse


@pytest.mark.slow
def test_r13d_python310_fallback_memory_matches_the_disclosure():
    """模擬 3.10（沒有佔有型量詞；以 3.11 編譯一般量詞版）：每種形態比 e23ff2f 多 ≤ 10 MB。

    量測紀錄（2026-10-01，tracemalloc）：本模擬最大 +4.0 MB（json_slash）；真 Python 3.10.20 跑同一份 21 種形態
    最大 +4.8 MB（json_slash）。上限 10 MB ＝ 實測的 2 倍以上餘裕；圈數上限拿掉時本模擬會到 ~118 MB（S3 QA 第三輪）。
    """
    m = _mutant(('    re.compile(r"a*+")\n', '    re.compile(r"a*+(")\n'))
    assert m._POSS == ""
    forms = _mem_forms()
    worst = max(_peak_mb(m.scrub_secrets, t) - _peak_mb(_OLD, t) for t in forms.values())
    assert worst <= 10 and "真 Python 3.10" in _DOC, worst


# ══════════════════════════════════════════════════════════════════
# S3 QA 第二輪（F1／F2／F3）
# ══════════════════════════════════════════════════════════════════
_ED25519_KEY = _b64(bytes.fromhex("302e020100300506032b657004220420") + random.Random(7).randbytes(32))


def _cpu_min3(fn, text: str) -> float:
    import time
    best = None
    for _ in range(3):
        t = time.process_time()
        fn(text)
        d = time.process_time() - t
        best = d if best is None else min(best, d)
    return best


@pytest.mark.parametrize("n", [500, 6000])
def test_f1_many_one_line_keys_no_recursion_and_linear(n):
    """F1：一行一把的 Ed25519 清單 —— 舊寫法每段遞迴一層，500 把就 RecursionError。現在逐行走一次。"""
    raw = "\n".join([_ED25519_KEY] * n)
    out = scrub_secrets(raw)
    assert _ED25519_KEY[:20] not in out and set(out.split("\n")) == {MASK}
    new, old = _cpu_min3(scrub_secrets, raw), _cpu_min3(_OLD, raw)
    assert new <= max(3 * old, 0.5), (new, old)


def test_f1_masking_is_iterative_not_recursive():
    """結構守衛：`_der_loose_block` 不呼叫自己、也不再呼叫 `_DER_B64_LOOSE_RE.sub`。"""
    import ast
    import inspect
    src = inspect.getsource(SSC._der_loose_block)
    names = {n.id for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Attribute)}
    assert "_der_loose_block" not in names and "sub" not in attrs


@pytest.mark.parametrize("count", [1, 2, 3, 5])
def test_f3_last_key_of_a_one_line_key_list_masked(count):
    raw = "\n".join([_ED25519_KEY] * count)
    out = scrub_secrets(raw)
    assert _ED25519_KEY[:16] not in out and set(out.split("\n")) == {MASK}, out
    if count >= 3:
        assert _ED25519_KEY in _OLD(raw).split("\n")[-1], "前提：e23ff2f 最後一把整把外露"


def _ec_p256(seed: int) -> bytes:
    """結構一致的仿 EC P-256 PKCS#8（138 位元組，`MIGHAgEAMBMG…`；固定種子，⛔ 不是真金鑰）。"""
    r = random.Random(seed)
    ecpk = _seq(bytes.fromhex("020101") + b"\x04\x20" + r.randbytes(32) + bytes.fromhex("a144034200") + b"\x04"
                + r.randbytes(64))
    return _seq(bytes.fromhex("020100301306072a8648ce3d020106082a8648ce3d030107") + b"\x04" + bytes([len(ecpk)])
                + ecpk)


def _ec_cert(seed: int) -> bytes:
    r = random.Random(seed + 500)
    return _seq(_seq(r.randbytes(300)) + bytes.fromhex("300a06082a8648ce3d040302") + b"\x03\x48\x00"
                + r.randbytes(71))


_F2_LAYOUTS = {
    "trailing_space": lambda ls: "\n".join(ln + "  " for ln in ls),
    "json_slash": lambda ls: json.dumps("\n".join(ls)).replace("/", "\\/"),
}


@pytest.mark.parametrize("width", [64, 76])
@pytest.mark.parametrize("layout", sorted(_F2_LAYOUTS))
@pytest.mark.parametrize("kind", ["ec_p256", "rsa"])
def test_f2_key_plus_cert_leaks_nothing(kind, layout, width):
    """F2：金鑰＋憑證 × {行尾空白, JSON `\\/`} × {64, 76}：金鑰與憑證都 0 外露（20 個固定種子）。"""
    enc = _F2_LAYOUTS[layout]
    before = 0
    for seed in range(20):
        key, cert = (_ec_p256(seed), _ec_cert(seed)) if kind == "ec_p256" else (_pkcs8(seed), _cert(seed))
        raw = enc(_wrap(_b64(key), width) + _wrap(_b64(cert), width))
        out = scrub_secrets(raw)
        assert _leak(out, _b64(key)) == 0 and _leak(out, _b64(cert)) == 0, (seed, out[:120])
        assert _is_masking_of(out, _OLD(raw))
        before += _leak(_OLD(raw), _b64(key)) > 0
    assert before >= 1, "前提：e23ff2f 在這種排列確實外露"


def test_f2_ec_sample_really_looks_like_p256():
    assert len(_ec_p256(0)) == 138 and _b64(_ec_p256(0)).startswith("MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEH")


_TOK3 = "tOk9S3qaF3AbCdEfGh"


@pytest.mark.parametrize("raw,want", [
    (f"headers['Authorization'] = 'Bearer ' + '{_TOK3}'", "headers['Authorization'] = '***'***"),
    (f"headers['Authorization'] = 'Bearer ' + {_TOK3} + ''", "headers['Authorization'] = '***'***"),
    (f'headers["Authorization"] = """{_TOK3}"""', 'headers["Authorization"] = ***'),
    (f"headers['Authorization'] = '''{_TOK3}\nnext", "headers['Authorization'] = ***\nnext"),
    (f"headers['Authorization'] += '{_TOK3}'", "headers['Authorization'] += '***'"),
])
def test_f3_authorization_forms_fixed(raw, want):
    assert scrub_secrets(raw) == want
    assert _TOK3 in _OLD(raw), "前提：e23ff2f 外露"


@pytest.mark.parametrize("raw", [
    f"headers['Authorization'] = ( '{_TOK3}' )",
    f"headers['Authorization'] =\n'{_TOK3}'",
    f"headers.__setitem__('Authorization', '{_TOK3}')",
])
def test_f3_disclosed_authorization_forms_still_leak(raw):
    """檔頭揭露的三種：仍外露（與 e23ff2f 相同）—— 改了請同步改檔頭。"""
    assert _TOK3 in scrub_secrets(raw) and scrub_secrets(raw) == _OLD(raw)
    assert "`= ( 'tok' )`" in _DOC and "`headers.__setitem__('Authorization', 'tok')`" in _DOC


def test_f3_concat_tail_is_load_bearing():
    raw = f"headers['Authorization'] = 'Bearer ' + '{_TOK3}'"
    m = _mutant(('    return _mask_value(m) + (MASK if m.group("cat") else "")',
                 '    return _mask_value(m) + (m.group("cat") or "")'))
    assert _TOK3 in m.scrub_secrets(raw)


def test_tidy_does_not_swallow_a_wide_line_after_the_run():
    """整齊本體之後若接著一行**不比它短**的別的字串 → 那行不算本體的最後一行，照原樣。"""
    raw = "***\n" + "\n".join(c * 40 for c in "ABCD") + "\n" + "Z" * 60
    assert scrub_secrets(raw) == "***\n" + "Z" * 60


def test_masked_line_width_estimate_does_not_eat_the_next_block():
    """金鑰中間一行先被路徑規則遮掉（寬度不可知）→ 以附近最寬的行估；估小了會把後面不是 DER 的 base64 吃掉一行。"""
    found = 0
    for seed in range(200):
        key = _ec_p256(seed)
        kl = _wrap(_b64(key))
        tail = ["Zz" + _b64(random.Random(10_000 + 3 * seed + j).randbytes(48))[2:] for j in range(3)]
        raw = "\n".join(ln + "  " for ln in kl + tail)
        if not kl[1].startswith("/") or "***" not in _OLD(raw).split("\n")[1] or any(t.startswith("/") for t in tail):
            continue
        found += 1
        out = scrub_secrets(raw)
        assert _leak(out, _b64(key)) == 0 and out.split("\n")[-3:] == [t + "  " for t in tail], out
    assert found >= 1, "前提：樣本裡要有金鑰第二行先被遮掉的"


# ══════════════════════════════════════════════════════════════════
# S3 QA 第三輪
# ══════════════════════════════════════════════════════════════════
#: 1. 回歸：第二道在原文上判、最後一行（短行）吃掉路徑開頭 → 含空白目錄名的規則認不出 → 比 e23ff2f 少遮。
_R3_DER_HEADS = [_b64(_pkcs8(1))[:32], _b64(_pkcs8(1))[:64], "\n".join(_wrap(_b64(_pkcs8(1)))[:2]),
                 _b64(_ec_p256(1))[:64]]
_R3_PATHS = ["/Users/Jane Doe/x.toml", "~/My Docs/a b/x.toml", "/home/x y/z.toml", "C:\\Users\\Jane Doe\\x.toml",
             "\\\\srv\\share x\\y.toml", "/home/u/my\tdir/x.toml", "/Users/JaneDoeLongName1 Doe/x.toml",
             "//nas01/My Share/jane/x.toml", "see @/Users/Jane Doe/x.toml"]
_R3_SEPS = ["\n", "\r\n", "\\n", "\r"]


def _r3_cases() -> list[str]:
    return [h + sep + p for h in _R3_DER_HEADS for p in _R3_PATHS for sep in _R3_SEPS]


def test_r3_path_after_a_der_line_never_masks_less():
    bad = [r for r in _r3_cases() if not _is_masking_of(scrub_secrets(r), _OLD(r))]
    assert not bad, [(b[-40:], _OLD(b)[-30:], scrub_secrets(b)[-30:]) for b in bad[:5]]


def test_r3_the_reported_repro():
    raw = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n/Users/Jane Doe/x.toml"
    assert scrub_secrets(raw) == _OLD(raw) == "MIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n***/x.toml"


def test_r4_old_part_is_exactly_e23ff2f():
    """結構保證：關掉新規則（第二道 DER、`_RULES_NEW`）後，輸出與 e23ff2f 逐字相同 ⇒ 新規則只能在其上多遮。"""
    m = _mutant(("_der_loose_spans(_t0))", "[])"),
                ("    (_POSIX_TAB_DIR_RE, _mask_tab_dirs),\n    (_AUTH_SUBSCRIPT_RE, _mask_auth_subscript),\n", ""))
    corpus = sorted(_batch_corpus() | _ui_corpus())[::3] + _r4_cases(3000)
    diff = [r for r in corpus if m.scrub_secrets(r) != _OLD(r)]
    assert not diff, [(d[:60], _OLD(d)[:60], m.scrub_secrets(d)[:60]) for d in diff[:5]]


@pytest.mark.parametrize("prefix", ["> ", "> > ", ">", ">  "])
@pytest.mark.parametrize("kind", ["pkcs8", "ec_p256", "cert"])
def test_r3_markdown_quote_prefix_masked(prefix, kind):
    """2(a)：Markdown 引用 `> ` 行首的金鑰／憑證（e23ff2f 全數外露）。"""
    mk = {"pkcs8": _pkcs8, "ec_p256": _ec_p256, "cert": _cert}[kind]
    for seed in range(10):
        b = _b64(mk(seed))
        raw = prefix + ("\n" + prefix).join(_wrap(b))
        assert _leak(scrub_secrets(raw), b) == 0, (seed, scrub_secrets(raw)[:80])
    assert _leak(_OLD(prefix + ("\n" + prefix).join(_wrap(_b64(mk(0))))), _b64(mk(0))) > 0


def _ed_cert(seed: int) -> bytes:
    r = random.Random(seed + 900)
    return _seq(_seq(r.randbytes(200 + seed % 48)) + bytes.fromhex("300506032b6570") + b"\x03\x41\x00" + r.randbytes(64))


def test_r3_ed25519_cert_then_one_line_key_json_slash():
    """2(b)：Ed25519 憑證（最後一行短）＋一行 Ed25519 金鑰、JSON `\\n` 且 `/` 跳脫成 `\\/`：金鑰那一行也遮。"""
    hit = before = 0
    for seed in range(200):
        key = _b64(bytes.fromhex("302e020100300506032b657004220420") + random.Random(seed).randbytes(32))
        cert = _wrap(_b64(_ed_cert(seed)))
        if "/" not in key or len(cert[-1]) >= 16:
            continue
        hit += 1
        raw = json.dumps("\n".join(cert + [key])).replace("/", "\\/")
        out = scrub_secrets(raw)
        assert _leak(out, key) == 0 and _leak(out, _b64(_ed_cert(seed))) == 0, out[-90:]
        before += _leak(_OLD(raw), key) > 0
    assert hit >= 5 and before >= 1, (hit, before)


_TOK4 = "tOk9S3qaR3AbCdEfGh"


@pytest.mark.parametrize("raw", [
    f"h['Authorization'] = 'Bearer %s' % '{_TOK4}'",
    f"h['Authorization'] = 'Bearer %s' % ('{_TOK4}',)",
    f"h['Authorization'] = 'Bearer {{}}'.format('{_TOK4}')",
    f"h['Authorization'] = \\\n    '{_TOK4}'",
    f"h['Authorization'] = 'Bearer %s' % {_TOK4}",
])
def test_r3_authorization_percent_format_continuation(raw):
    assert _TOK4 not in scrub_secrets(raw) and _TOK4 in _OLD(raw)


# ══════════════════════════════════════════════════════════════════
# S3 QA 第四輪：同一族的少遮（DER 範圍吃掉路徑開頭）—— 改成結構保證，並以隨機生成器驗證
# ══════════════════════════════════════════════════════════════════
_R4_REPROS = [
    ("MIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n/Users/Jane.Doe Smith/x.toml", "MIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n***/x.toml"),
    ("MIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n/a/b.c d/x.toml", "MIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n***/x.toml"),
    ("MIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n/Users/Jane)Doe x/y", "MIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n***/y"),
]


@pytest.mark.parametrize("raw,want", _R4_REPROS)
def test_r4_reported_repros(raw, want):
    assert _OLD(raw) == want and _is_masking_of(scrub_secrets(raw), want)
    assert "Doe" not in scrub_secrets(raw) and "c d" not in scrub_secrets(raw)


_R4_PUNCT = list(".):,;]}\"'`") + list("。，、；：）」』．")


def _r4_cases(n: int, seed: int = 20261001) -> list[str]:
    """DER 開頭（各種金鑰的完整行／截短行／跨行）× 分隔 × 路徑／說明字尾巴（路徑名裡夾各種半形與全形標點、空白、tab）。"""
    rnd = random.Random(seed)
    keys = [_b64(_pkcs8(i)) for i in range(4)] + [_b64(_ec_p256(i)) for i in range(4)] + [_b64(_cert(1)), _ED25519_KEY]
    seps = ["\n", "\r\n", "\r", "\\n", " \n", "\n> ", "  ", "\t", ""]
    words = ["Jane", "Doe", "My", "Docs", "a", "b", "x y", "Program Files", "王 小明", "dir"]

    def path() -> str:
        segs = []
        for _ in range(rnd.randint(1, 4)):
            w = rnd.choice(words)
            if rnd.random() < 0.6:
                w = w + rnd.choice(_R4_PUNCT + [" ", "\t", ""]) + rnd.choice(words)
            segs.append(w)
        lead = rnd.choice(["/", "/Users/", "~/", "/home/", "C:\\Users\\", "//nas/", "@/", "\\\\srv\\"])
        return lead + "/".join(segs) + "/" + rnd.choice(["x.toml", "y", "secrets.toml", "a b.txt"])

    out = []
    for _ in range(n):
        k = rnd.choice(keys)
        w = rnd.choice([16, 24, 32, 40, 64, 76])
        lines = [k[i:i + w] for i in range(0, len(k), w)][: rnd.randint(1, 4)]
        lines[-1] = lines[-1][: rnd.randint(1, len(lines[-1]))]
        head = rnd.choice(["\n", "\\n", "\r\n"]).join(lines)
        tail = path() if rnd.random() < 0.8 else rnd.choice(["對嗎？", "What is it", "password: x"] + _R4_PUNCT)
        tail += rnd.choice(["", " 讀不到", rnd.choice(_R4_PUNCT), "\n" + path()])
        out.append(rnd.choice(["", "x ", "私鑰 ", "> "]) + head + rnd.choice(seps) + tail)
    return out


def test_r4_property_never_masks_less_than_e23ff2f():
    """隨機生成 20,000 筆（固定種子）：DER 開頭 × 分隔 × 夾標點的路徑／說明字 —— 一筆都不得比 e23ff2f 少遮。"""
    cases = _r4_cases(20_000)
    assert len(set(cases)) > 15_000
    bad = [r for r in cases if not _is_masking_of(scrub_secrets(r), _OLD(r))]
    assert not bad, [(b[-50:], _OLD(b)[-40:], scrub_secrets(b)[-40:]) for b in bad[:5]]


def test_r4_tracked_mapping_only_masks_copied_chars():
    """`_mask_orig_spans` 只遮照抄自基準的字：規則產生的 `***/x.toml` 不受影響。"""
    out, segs = SSC._sub_tracked(SSC._POSIX_SPACE_DIR_RE, SSC._mask_space_dirs, "AB\n/Users/Jane Doe/x.toml",
                                 [(0, 24, 0)])
    assert out == "AB\n***/x.toml" and segs == [(0, 3, 0)]
    assert SSC._mask_orig_spans(out, segs, [(0, 24)]) == "******/x.toml"     # 換行也是照抄的字
    assert SSC._mask_orig_spans(out, segs, [(0, 2)]) == "***\n***/x.toml"
    assert SSC._mask_orig_spans(out, segs, [(1, 2)]) == "A***\n***/x.toml"


_TQ = "'" * 3


@pytest.mark.parametrize("raw", [
    f"h['Authorization'] = 'Bearer ' + \\\n    '{_TOK4}'",
    f"h['Authorization'] = 'Bearer %s' % tok['{_TOK4}']",
    f"h['Authorization'] = 'B' + '{_TOK4}" + "x" * 5000 + "'",
    f"h['Authorization'] = {_TQ}{_TOK4}" + "x" * 5000 + _TQ,
    f"h['Authorization'] = 'B {{}}'.format('{_TOK4}" + "x" * 5000 + "')",
])
def test_r4_authorization_continuation_subscript_and_long_values(raw):
    """續行夾在串接中、`% tok['x']`、超過 4096 字的串接段／三引號值：都遮到（超過上限 → 遮到行尾，檔頭同）。"""
    out = scrub_secrets(raw)
    assert _TOK4 not in out and _is_masking_of(out, _OLD(raw))
