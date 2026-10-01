"""SEC 批次 S3（2026-09-28）：S2-f3 ／ S2-f2（a）（b）（c）＋ 批 S QA 意見 N1／N2／N5。

- S2-f3：`page_why._render_qa_leaf` 建 `QaRequest` 時帶的是**原文**提問，經 L3 `run_agent` 原樣送給
  Gemini（畫面上的紀錄反而是洗過的）→ 建 `QaRequest` 前先 `scrub_secrets`（純文字版）。
- S2-f2：`shared/secret_scrub._RULES_POST` 補三種**少遮**形態：
  (a) 目錄名含空白的 POSIX 路徑（`/Users/Jane Doe/…` → 舊版 `***/Jane Doe/…`，使用者名稱與目錄外露）；
  (b) 沒有標頭的 PEM／DER base64 本體（`MIIEvQIBADANBgkq…`，≥60 字、可跨行，舊版原樣輸出）；
  (c) 深層巢狀 `repr`／JSON 的 `{'password': …}`（引號前 ≥5 個反斜線，舊版上限 `\\\\{0,4}` ⇒ 外露）。
- 批 S QA（多遮收窄）：N1 空白路徑規則 ⛔ 不得把路徑後面的中文說明字當成目錄名吞掉；
  N2 DER 規則 ⛔ 不得遮「`M[A-P]` 開頭、湊滿 60 字」的一般文字（行結構 ＋ 解碼驗證）。

⭐ 硬性要求：**任何輸入都不得比舊版少遮**；真實 UI 字串常值（`src/`、`shared/`、`app.py`）輸出變動數 0。
「舊版」＝ **固定的 d61a1fd 版**（批 S QA N5）：`tests/fixtures/secret_scrub_d61a1fd.py` 是該 commit
`shared/secret_scrub.py` 的逐位元組凍結副本（本檔逐位元組核對 sha256）。判準（QA 定義）：
**新輸出必須能由舊輸出「把若干段換成 `***`」得到**（`_is_masking_of`）。
⚠️ 不再用「目前檔案拔掉新規則」當基準 —— 那是自我參照：舊規則被改壞時基準跟著壞，測不出來。
`_mutant`（拔掉目前檔案的某幾行）只留給「每條新規則都是承重的」那一類測試用。
"""
from __future__ import annotations

import ast
import base64
import functools
import hashlib
import importlib.util
import itertools
import json
import pathlib
import random
import re
import subprocess
import sys

import pytest

from shared import secret_scrub as SSC
from shared.secret_scrub import MASK, scrub_prose_secrets, scrub_secrets

_ROOT = pathlib.Path(__file__).resolve().parents[1]

# ══════════════════════════════════════════════════════════════════
# 基準：d61a1fd 的凍結副本（批 S QA N5）
# ══════════════════════════════════════════════════════════════════
_FIXTURE = _ROOT / "tests" / "fixtures" / "secret_scrub_d61a1fd.py"
_FIXTURE_MARKER = "# ═══ 原檔開始 ═══\n"
#: `git show d61a1fd:shared/secret_scrub.py | sha256sum`（blob 1e495faefc055bbd9e2efef98fb9570d019fe90b）。
_D61_SHA256 = "5acd643510f1bebcef8beef4210ee1c5d2b1d6ee8fed5915f23c90f803fc3b1b"


def _load_d61():
    spec = importlib.util.spec_from_file_location("_secret_scrub_d61a1fd", _FIXTURE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_D61 = _load_d61()


def test_baseline_is_the_frozen_d61a1fd_file_byte_for_byte():
    """凍結副本：標記那一行之後 ＝ d61a1fd 的 `shared/secret_scrub.py` 原檔（逐位元組）。"""
    raw = _FIXTURE.read_bytes()
    marker = _FIXTURE_MARKER.encode("utf-8")
    assert raw.count(marker) == 1
    assert hashlib.sha256(raw.split(marker, 1)[1]).hexdigest() == _D61_SHA256
    assert _D61.scrub_secrets is not scrub_secrets and _D61.__file__ == str(_FIXTURE)


def _is_masking_of(new: str, old: str) -> bool:
    """`new` 能不能由 `old`「把若干段（可為空）換成 `***`」得到。

    先試快路：以 `***` 切開 `new`，各段依序、不重疊地出現在 `old`（頭尾對齊）。快路失敗時（遮罩旁邊
    剛好有 `*`，切法不唯一），改用位元集合動態規劃：`reach[i]` ＝ `new[:i]` 能對上的 `old` 前綴長度集合。
    """
    if new == old:
        return True
    if MASK not in new:
        #: SEC-r18（批 S3）：沒有遮罩時只能逐字相同。原本快路只比頭尾，沒有遮罩時 `parts` 只有一段，
        #: 頭、尾比的是同一段 ⇒ `("ab", "abXab")` 誤判 True（比文件寬鬆）。
        return False
    parts = new.split(MASK)
    if old.startswith(parts[0]) and old.endswith(parts[-1]) and len(parts[0]) + len(parts[-1]) <= len(old):
        pos, ok = len(parts[0]), True
        for p in parts[1:-1]:
            k = old.find(p, pos)
            if k < 0:
                ok = False
                break
            pos = k + len(p)
        if ok and pos <= len(old) - len(parts[-1]):
            return True
    n = len(old)
    eq: dict[str, int] = {}
    for j, c in enumerate(old):
        eq[c] = eq.get(c, 0) | (1 << j)
    full = (1 << (n + 1)) - 1
    reach = [0] * (len(new) + 1)
    reach[0] = 1
    for i, c in enumerate(new):
        r = reach[i]
        if not r:
            continue
        reach[i + 1] |= (r & eq.get(c, 0)) << 1
        if new.startswith(MASK, i):
            reach[i + 3] |= full & ~((r & -r) - 1)
    return bool(reach[len(new)] >> n & 1)


@pytest.mark.parametrize("new,old,want", [
    ("abc", "abc", True), ("***/x", "***/Jane Doe/x", True), ("***/x", "~/My Docs/x", True),
    ("x*****y", "x**SECRETy", True), ("***", "a/b", True), ("***abc", "abc", True),
    ("abd", "abc", False), ("ba", "ab", False), ("abcd", "abc", False), ("***/y", "***/x", False),
    ("a***c", "abc", True), ("a***c", "ab", False),
    #: SEC-r18（批 S3）：沒有遮罩 ⇒ 只能逐字相同。
    ("ab", "abXab", False), ("", "x", False), ("a", "aXa", False), ("", "", True),
])
def test_masking_criterion_itself(new, old, want):
    assert _is_masking_of(new, old) is want


def _mutant(*pairs: tuple[str, str]):
    src = pathlib.Path(SSC.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    spec = importlib.util.spec_from_loader("_mutant_sec_s3", loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = SSC.__file__
    exec(compile(src, SSC.__file__, "exec"), m.__dict__)
    return m


_NEW_LINE = {
    "deep_quoted": "    (_DEEP_QUOTED_FIELD_RE, _mask_deep_value),\n",
    "deep_assign": "    (_DEEP_ASSIGN_TAIL_RE, lambda m: m.group(1) + MASK),\n",
    "der_b64": "    (_DER_B64_RE, _der_strict_block),\n",          # 批 S3：第一道移進 `_DER_PARTS`（判法不變）
    "space_dir": "    (_POSIX_SPACE_DIR_RE, _mask_space_dirs),\n",
}


def _maxbs(s: str) -> int:
    return max((len(x) for x in re.findall(r"\\+", s)), default=0)


# ══════════════════════════════════════════════════════════════════
# S2-f2 (a)：目錄名含空白的 POSIX 路徑
# ══════════════════════════════════════════════════════════════════
#: (原文, 不得出現的片段, 期望輸出)
_SPACE_PATHS = [
    ("/Users/Jane Doe/app/.streamlit/secrets.toml", ("Jane", "Doe", "app", ".streamlit"), "***/secrets.toml"),
    ("FileNotFoundError: [Errno 2] No such file or directory: '/Users/Jane Doe/app/.streamlit/secrets.toml'",
     ("Jane", "Doe", "app/"), "FileNotFoundError: [Errno 2] No such file or directory: '***/secrets.toml'"),
    ("讀不到 /home/jane doe/proj/x.toml", ("jane", "doe", "proj"), "讀不到 ***/x.toml"),
    ("/home/jane/My Documents/secret stuff/x.toml", ("My", "Documents", "secret", "stuff"), "***/x.toml"),
    ("~/My Documents/x.toml", ("My", "Documents"), "***/x.toml"),              # 舊版整段原樣
    ("/My Drive/jane/x.toml", ("My", "Drive", "jane"), "***/x.toml"),          # 第一段就含空白：舊版整段原樣
    ("file:///Users/Jane Doe/x.toml", ("Jane", "Doe"), "file://***/x.toml"),
    ("b'x\\n/Users/Jane Doe/app/x.toml'", ("Jane", "Doe", "app"), "b'x\\n***/x.toml'"),
    ("see @/Users/Jane Doe/x.toml", ("Jane", "Doe"), "see @***/x.toml"),
    ("//nas01/My Share/jane/x.toml", ("My", "Share", "jane"), "***/x.toml"),
    ("/Users/jane/Dropbox (Personal)/app/secrets.toml", ("jane", "Dropbox", "Personal", "app"), "***/secrets.toml"),
    ("/mnt/c/Program Files (x86)/app/x.py", ("Program", "Files", "x86", "app"), "***/x.py"),
    ("/Users/Jane Doe/", ("Jane", "Doe"), "***/"),
    #: `@` 後面是另一條路徑（第一段就含空白 → 舊的 `@` 規則也遮不到）；`x.toml @` ⛔ 不是目錄名 → `x.toml` 留著。
    ("/a/x.toml @/My Drive/b.toml", ("My", "Drive"), "***/x.toml @***/b.toml"),
    #: 含空白的目錄段之後，不含空白的目錄段照舊規則什麼字都收（中文目錄、長雜湊目錄）。
    ("/Users/Jane Doe/文件/報告.xlsx", ("Jane", "Doe", "文件"), "***/報告.xlsx"),
    ("/Users/Jane Doe/Library/" + "ab12" * 16 + "/Data/x.plist", ("Jane", "Doe", "ab12ab12"), "***/x.plist"),
]


@pytest.mark.parametrize("raw,gone,want", _SPACE_PATHS)
def test_a_space_in_directory_name_masked(raw, gone, want):
    out = scrub_secrets(raw)
    assert out == want, out
    assert not [g for g in gone if g in out], out
    assert any(g in _D61.scrub_secrets(raw) for g in gone), "前提：d61a1fd 確實外露"


#: 一般文字 ⛔ 不誤遮：與 d61a1fd 逐字相同（本條只在「某個目錄段真的含空白」時才動手）。
_SPACE_NEGATIVE = [
    ("元/股/張 80/20 TW/US", "元/股/張 80/20 TW/US"),
    ("單位：元 / 股，a / b / c", "單位：元 / 股，a / b / c"),
    ("https://host/a b/c", "https://host/a b/c"),
    ("at /home/jane/app/x.py line 3", "at ***/x.py line 3"),
    ("讀不到 /home/u/x.toml 請檢查權限", "讀不到 ***/x.toml 請檢查權限"),
    ("(see /a/b) ok", "(see ***/b) ok"),
    ("x.toml @/home/u/a/b.toml", "x.toml @***/b.toml"),
    ("讀取 /tmp/report.csv 完成 3 筆", "讀取 ***/report.csv 完成 3 筆"),   # 末段（檔名）後的說明字不吃
]


@pytest.mark.parametrize("raw,want", _SPACE_NEGATIVE)
def test_a_ordinary_text_not_masked_more(raw, want):
    assert scrub_secrets(raw) == want == _D61.scrub_secrets(raw)


#: 批 S QA N1 的四個實例：(原文, 修後必須還在的說明文字)。修後與 d61a1fd 逐字相同。
_QA_N1 = [
    ("檔案 /data/2330.csv 顯示殖利率 4.5%，配息 3 元/股。", "顯示殖利率 4.5%，配息 3 元"),
    ("建議把 ~/.streamlit/secrets.toml 放好後重啟；另外 MA20/MA60…", "放好後重啟；另外 MA20"),
    ("台積電 /2330 跟 聯發科/2454 哪個好？", "跟 聯發科"),
    ("`/`：約 1/64 的行以 `/` 開頭", "約 1/64 的行以"),
]


@functools.lru_cache(maxsize=1)
def _pre_n1():
    """修前（`314472f`）的「字」：沒有長度上限、中文與全形標點照收 —— 用來證明各實例真的踩得到 N1 的判別。"""
    return _mutant((r'''_SP_DIR_WORD: str = r"[^\s/\\'\"<>|:;,\[\]{}*?@`" + _CJK_PUNCT + r"]{1,%d}" % _SP_DIR_WORD_MAX''',
                    r'''_SP_DIR_WORD: str = r"[^\s/\\'\"<>|:;,\[\]{}*?@→—]+"'''))


@pytest.mark.parametrize("raw,kept", _QA_N1)
def test_n1_prose_after_a_path_is_not_a_directory_name(raw, kept):
    out = scrub_secrets(raw)
    assert kept in out and out == _D61.scrub_secrets(raw), out
    assert kept not in _pre_n1().scrub_secrets(raw), "前提：拿掉 N1 的判別，說明文字確實被吞"


def test_n1_cjk_and_fullwidth_punctuation_are_not_directory_words():
    """含空白的目錄段裡，中文字與全形標點 ⛔ 不算「字」（說明文字不可能被當成目錄名）。"""
    for raw in ("/data/x.csv 顯示殖利率/股", "/data/x.csv 配息，3 元/股", "/data/x.csv 看（附註）/股",
                "/data/x.csv 見「說明」/股", "/data/x.csv 約 3％ 左右/股"):
        assert scrub_secrets(raw) == _D61.scrub_secrets(raw), raw


def test_n1_word_length_cap_is_40():
    """含空白的目錄段裡，每個字 ≤ 40 字元：41 字的一串 ⛔ 不算字；剛好 40 的照樣是目錄名。"""
    raw = "讀不到 /home/u/x.toml " + "A" * 41 + "/y"
    assert scrub_secrets(raw) == _D61.scrub_secrets(raw) == "讀不到 ***/x.toml " + "A" * 41 + "/y"
    assert scrub_secrets("/Users/Jane Doe/" + "A" * 40 + " B/x.toml") == "***/x.toml"


def test_n1_space_directory_is_at_most_5_words():
    """SEC-r18（批 S3）：含空白的目錄段最多 5 個字 —— 5 個字照遮；6 個字那一段起照舊外露（同 d61a1fd）。"""
    assert scrub_secrets("a /Users/a b c d e/x.toml") == "a ***/x.toml"
    raw6 = "a /Users/a b c d e f/x.toml"
    assert scrub_secrets(raw6) == _D61.scrub_secrets(raw6) == "a ***/a b c d e f/x.toml"
    m = _mutant(('_SP_DIR_MULTI: str = _SP_DIR_WORD + r"(?: " + _SP_DIR_WORD + r"){1,4}"',
                 '_SP_DIR_MULTI: str = _SP_DIR_WORD + r"(?: " + _SP_DIR_WORD + r"){1,5}"'))
    assert m.scrub_secrets(raw6) == "a ***/x.toml", "前提：上限放寬一個字，這個測試就會紅"


def test_n1_backtick_is_not_a_directory_word():
    """Markdown 行內程式碼的反引號 ⛔ 不算字：`` `/a/b` and `c/d` `` 不會被當成一條含空白的路徑。"""
    raw = "see `/a/b` and `c/d` too"
    assert scrub_secrets(raw) == _D61.scrub_secrets(raw) == "see `***/b` and `c/d` too"


# ══════════════════════════════════════════════════════════════════
# S2-f2 (b)：沒有標頭的 PEM／DER base64 本體
# ══════════════════════════════════════════════════════════════════
#: 仿 PKCS#8 RSA 私鑰：結構一致的 DER（外層 SEQUENCE 宣告 0x4bd ＝ 1213 位元組內容，內層
#: INTEGER 0、AlgorithmIdentifier、OCTET STRING 0x4a7 ＝ 1191 位元組）＋ 固定種子的位元組（⛔ 不是真金鑰）。
_DER = (bytes.fromhex("308204bd020100300d06092a864886f70d0101010500048204a7")
        + random.Random(20260928).randbytes(1191))
_B64 = base64.b64encode(_DER).decode()
_LINES = [_B64[i:i + 64] for i in range(0, len(_B64), 64)]
#: Ed25519 PKCS#8（48 位元組 → 64 字，`MC4C…`）。
_ED25519 = base64.b64encode(bytes.fromhex("302e020100300506032b657004220420")
                            + random.Random(7).randbytes(32)).decode()


def test_b_sample_really_looks_like_a_pem_body():
    assert _B64.startswith("MIIEvQIBADANBgkq") and len(_LINES) == 26 and len(_DER) == 4 + 0x4bd
    assert _ED25519.startswith("MC4CAQAwBQYDK2VwBCIEI") and len(_ED25519) == 64


_DER_FORMS = {
    "one_line": _B64,
    "real_newlines": "\n".join(_LINES),
    "crlf": "\r\n".join(_LINES),
    "repr_escaped": repr("\n".join(_LINES)),
    "json_escaped": json.dumps("\n".join(_LINES)),
    "json_twice": json.dumps(json.dumps("\n".join(_LINES))),
    "space_joined": " ".join(_LINES),
    "indented": "\n    ".join(_LINES),
    "in_prose": f"私鑰是 {_B64[:80]} 對嗎？",
    "after_equals": f"data={_B64[:70]}",
    "ed25519": _ED25519,
}


@pytest.mark.parametrize("name", sorted(_DER_FORMS))
def test_b_headerless_der_body_masked(name):
    raw = _DER_FORMS[name]
    out = scrub_secrets(raw)
    chunks = [c for c in (_LINES if name != "ed25519" else [_ED25519]) if c[:40] in raw]
    assert chunks and not [c for c in chunks if c[:40] in out], out[:200]
    assert MASK in out
    assert any(c[:40] in _D61.scrub_secrets(raw) for c in chunks), "前提：d61a1fd 確實外露"


def _key(seed: int) -> bytes:
    """結構一致的仿 PKCS#8 私鑰（外層長度欄位 ＝ 內容真正的長度；固定種子，⛔ 不是真金鑰）。"""
    body = bytes.fromhex("020100300d06092a864886f70d0101010500") + random.Random(seed).randbytes(900 + seed)
    return b"\x30\x82" + len(body).to_bytes(2, "big") + body


_DER_LAYOUTS = {
    "one_line": "".join,
    "real_newlines": "\n".join,
    "crlf": "\r\n".join,
    "indented": "\n    ".join,
    "repr_escaped": lambda ls: repr("\n".join(ls)),
    "json_escaped": lambda ls: json.dumps("\n".join(ls)),
    "json_twice": lambda ls: json.dumps(json.dumps("\n".join(ls))),
    "space_joined": " ".join,
}


@pytest.mark.parametrize("layout", sorted(_DER_LAYOUTS))
def test_b_no_line_of_any_key_leaks(layout):
    """200 把長度各異（最後一行 0～63 字都有）的假金鑰：遮完只剩遮罩、引號、跳脫與空白。

    base64 含 `/`：約 1/64 的行以 `/` 開頭，前面的路徑規則會先把那一行遮成 `***/…`（`4/…`、`1//…` 同理）——
    本體 ⛔ 不能在那裡斷掉（實作時實際踩過兩次：一次是沒把 `***` 收進本體，一次是 N2 的行長限制把
    那一行當成太短）。
    """
    enc = _DER_LAYOUTS[layout]
    pre_masked = 0
    for seed in range(200):
        b64 = base64.b64encode(_key(seed)).decode()
        lines = [b64[i:i + 64] for i in range(0, len(b64), 64)]
        raw = enc(lines)
        rest = re.sub(r"[*\"'\\\s]", "", scrub_secrets(raw))
        if layout == "space_joined" and len(lines[-1]) < 16 and not lines[-1].endswith("="):
            #: 已知邊界（檔頭有寫）：貼成一行時，最後一段 <16 字又沒有 `=` 補位 → 分不出是說明字，不吃（≤15 字）。
            assert rest == lines[-1], seed
        else:
            assert rest == "", (seed, rest[:80])
        pre_masked += MASK in _D61.scrub_secrets(raw)
    #: 前提只對多行排版成立（一整行沒有換行，就沒有「以 `/` 開頭的那一行」）。
    assert pre_masked or layout == "one_line", "前提：語料裡確實有「某一行先被舊規則遮掉一段」的金鑰"


def test_b_prose_around_the_body_kept():
    assert scrub_secrets(_DER_FORMS["in_prose"]) == "私鑰是 *** 對嗎？"
    assert scrub_secrets(_DER_FORMS["after_equals"]) == "data=***"


def test_b_threshold_is_60_base64_chars():
    assert scrub_secrets(_B64[:59]) == _B64[:59]
    assert scrub_secrets(_B64[:60]) == MASK
    #: 跨行也是算合計字數（換行、跳脫、`=` 不算字）；多行時第一行須 ≥40 字（N2 行結構）。
    assert scrub_secrets(_B64[:40] + "\\n" + _B64[40:59]) == _B64[:40] + "\\n" + _B64[40:59]
    assert scrub_secrets(_B64[:40] + "\\n" + _B64[40:60]) == MASK


@pytest.mark.parametrize("raw", [
    "MACD 與 MA20 的交叉", "MSCI 權重", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "MIIE",
    "Many Managers Made Money in March", "sha256=" + "9f" * 32, "M" + "a" * 70,
    "MA" + "b" * 20 + " " + "c" * 15 + " end"])
def test_b_ordinary_text_not_masked(raw):
    assert scrub_secrets(raw) == raw == _D61.scrub_secrets(raw)


#: 批 S QA N2 的實例：`M[A-P]` 開頭、湊滿 60 字，但不是 DER → 與 d61a1fd 逐字相同（原樣）。
_QA_N2 = {
    "ticker_list": "\n".join(["MAR", "AAPL", "TSLA", "NVDA", "MSFT", "GOOG", "AMZN", "META", "NFLX", "INTC",
                              "ORCL", "CSCO", "QCOM", "AVGO", "ADBE", "CRM", "AMD"]),
    "ma_and_codes": "\n".join(["MA5", "2330", "2317", "2454", "2412", "2308", "2382", "2881", "2882", "2303",
                               "3711", "2891", "1301", "1303", "2002", "5880"]),
    "search_url": "https://www.google.com/search?q=MACD+divergence+on+weekly+chart+for+2330+and+2454+and+2317+stocks",
    "text_base64": base64.b64encode(b"0050,0056,00878,00919,00929,00940,006208,00713,00692").decode(),
    "uppercase": "MARKETCAPITALIZATIONWEIGHTEDINDEXOFTHETAIWANSTOCKEXCHANGECORPORATION",
    #: 以 "0x" 開頭的文字做成的 base64：外層長度合法（0x78）、宣告也夠長 —— 只有「第一個內層標籤」擋得住。
    "hex_list_base64": base64.b64encode(b"0x1234abcd, 0x5678ef01, 0x9abcdef0, 0x13572468, 0x24681357").decode(),
}


@functools.lru_cache(maxsize=1)
def _pre_n2():
    """拿掉 N2 兩道判別（行長下限降到 2、不做解碼驗證）的版本 —— 用來證明各實例真的踩得到 N2 的判別。"""
    return _mutant(("_DER_B64_LINE_MIN: int = 40", "_DER_B64_LINE_MIN: int = 2"),
                   ("    return MASK if _looks_like_der(_B64_HEAD_RE.match(_lines[0]).group(0), _seen) else _body",
                    "    return MASK"))


@pytest.mark.parametrize("name", sorted(_QA_N2))
def test_n2_not_der_is_not_masked(name):
    raw = _QA_N2[name]
    assert scrub_secrets(raw) == _D61.scrub_secrets(raw) == raw
    assert MASK in _pre_n2().scrub_secrets(raw), "前提：拿掉 N2 的判別，這段確實會被整段遮"


def test_n2_line_structure_short_line_ends_the_body():
    """(i) 行結構：一行太短就停在那裡 —— 金鑰後面接的清單，只有第一行短行跟著被遮。"""
    raw = _LINES[0] + "\nAAPL\nTSLA\nNVDA"
    assert scrub_secrets(raw) == "***\nTSLA\nNVDA"
    #: 第一個項目長得像 DER 開頭、但只有 20 字 → 多行時第一行不到 40 字 → 不接下一行 → 原樣。
    lst = "\n".join([_B64[:20], "AAPL", "TSLA", "NVDA", "MSFT", "GOOG", "AMZN", "META", "NFLX", "INTC", "ORCL"])
    assert scrub_secrets(lst) == _D61.scrub_secrets(lst) == lst


def _b64_of(der: bytes, pad: int = 60) -> str:
    return base64.b64encode(der + random.Random(pad).randbytes(pad)).decode()


def test_n2_decode_check_declared_length_must_cover_what_is_seen():
    """(ii) 宣告的總長 < 實際看到的長度 → 不是（宣告 7 位元組、後面卻還有 60）。截斷的本體則照遮。"""
    raw = _b64_of(bytes.fromhex("3005020100"))
    assert scrub_secrets(raw) == raw
    assert scrub_secrets(_B64[:64] + "\n" + _B64[64:128]) == MASK        # 只截到前兩行：宣告 ≥ 實際


#: (標頭十六進位, 後面補幾個位元組, 期望)。⚠️ 每一列只讓「要測的那一條」決定結果 —— 其餘條件都刻意滿足
#: （宣告長度 ≥ 實際長度、內層標籤合法…），否則拔掉那一條也會被別條擋下，測不出來（實作時實際踩過）。
@pytest.mark.parametrize("head,pad,want", [
    ("308204bd020100", 900, MASK),    # INTEGER（私鑰版本號）
    ("3082050f3049", 900, MASK),      # SEQUENCE（加密私鑰、憑證）
    ("3082060006092a", 900, MASK),    # OID（PKCS#7）
    ("308204bd0401", 900, None),      # 內層是 OCTET STRING → 不是
    ("30817f020100", 60, None),       # 0x81 後面接 0x7f：<0x80 卻用長格式（非最短編碼）→ 不是
    ("3082007f020100", 60, None),     # 長格式有前導 0（0x007f）→ 不是
    ("3080020100", 60, None),         # 不定長（DER 不允許）→ 不是
    ("308500000000400201", 60, None),  # 長度欄位 5 位元組 → 不是
    ("3050027f00", 60, None),         # 內層宣告 0x7f 位元組，裝不進外層的 0x50 → 不是
])
def test_n2_decode_check_der_header_rules(head, pad, want):
    raw = _b64_of(bytes.fromhex(head), pad=pad)
    assert raw[0] == "M" and len(raw) >= 60
    assert scrub_secrets(raw) == (want or raw)


def test_n2_a_word_line_after_a_full_key_does_not_unmask_it():
    """最後一行不拿來比長度：金鑰（剛好 20 行滿行、無補位）後面換行接一個英文字，照樣遮。

    若把最後一行也算進「實際看到的長度」，宣告長度就會 < 實際長度，真金鑰整段外露。
    ⚠️ 種子挑「舊規則一個字都不動」的那把：若某一行先被舊規則遮掉幾個字，實際長度會少算，
    剛好把上面那個錯誤蓋掉（實作時實際踩過：種子 1 有一行以 `/` 開頭）。
    """
    body = bytes.fromhex("020100") + random.Random(2).randbytes(960 - 4 - 3)
    der = b"\x30\x82" + len(body).to_bytes(2, "big") + body
    b64 = base64.b64encode(der).decode()
    key = "\n".join(b64[i:i + 64] for i in range(0, len(b64), 64))
    assert len(b64) == 1280 and not b64.endswith("=") and _D61.scrub_secrets(key) == key, "前提"
    assert scrub_secrets(key + "\nWhat is this key?") == "*** is this key?"


# ══════════════════════════════════════════════════════════════════
# S2-f2 (c)：深層巢狀 repr／JSON
# ══════════════════════════════════════════════════════════════════
_SECRET = "hunter2S3q"
_TOKEN = "Ab1Cd2Ef3Gh4Ij5Kl6Mn7Op8Qr9St0Uv1Wx"   # 36 字、含數字（Telegram token 形狀）


def _levels(start, n: int, enc) -> dict[int, str]:
    """第 1 層＝`enc(start)`（字串則為原文），之後每層再 `enc` 一次。"""
    x = start if isinstance(start, str) else enc(start)
    out = {1: x}
    for lv in range(2, n + 1):
        x = enc(x)
        out[lv] = x
    return out


def _json(o) -> str:
    return json.dumps(o, ensure_ascii=False)


#: (名稱, 起點, 編碼, 要驗的層) —— 每一層引號前的反斜線數在測試裡直接釘住（7／15／31）。
_DEEP = [
    ("dict_password_repr", {"password": _SECRET}, repr, (5, 6, 7)),
    ("dict_client_secret_repr", {"client_secret": _SECRET, "user": "bob"}, repr, (5, 6, 7)),
    ("dict_refresh_token_repr", {"refresh_token": _SECRET}, repr, (5, 6, 7)),
    ("dict_authorization_repr", {"Authorization": "Basic " + _SECRET}, repr, (5, 6, 7)),
    ("fullwidth_colon_repr", "{'password'：'%s'}" % _SECRET, repr, (5, 6, 7)),
    ("dict_password_json", {"password": _SECRET}, _json, (4, 5, 6)),
    ("toml_quoted_key_json", '"password" = "%s"' % _SECRET, _json, (4, 5, 6)),
    ("toml_nospace_json", 'password="%s"' % _SECRET, _json, (4, 5, 6)),
    ("toml_nospace_repr", "password='%s'" % _SECRET, repr, (5, 6, 7)),
]


@pytest.mark.parametrize("name,start,enc,levels", _DEEP, ids=[d[0] for d in _DEEP])
def test_c_deep_nesting_masked(name, start, enc, levels):
    lv = _levels(start, max(levels), enc)
    assert [_maxbs(lv[k]) for k in levels] == [7, 15, 31], "前提：引號前 7／15／31 個反斜線"
    for k in levels:
        raw = lv[k]
        assert _SECRET not in scrub_secrets(raw), (name, k)
        assert _SECRET in _D61.scrub_secrets(raw), f"前提：d61a1fd 第 {k} 層確實外露"


def test_c_closing_quote_found_keeps_the_other_fields():
    """值有收尾 → 只遮值（同一串反斜線＋引號保留），同一個 dict 的其他欄位照舊看得到。"""
    raw = _levels({"client_secret": _SECRET, "user": "bob"}, 5, repr)[5]
    out = scrub_secrets(raw)
    bs = "\\" * 7
    assert f"{bs}'client_secret{bs}': {bs}'***{bs}'" in out
    assert f"{bs}'user{bs}': {bs}'bob{bs}'" in out


def test_c_deeper_quote_inside_value_is_not_the_closing():
    """值裡有「更深一層」的同種引號（反斜線更多）→ ⛔ 不算收尾；收尾必須是剛好同長的反斜線串。"""
    secret = "a'b\"ZZtail9"          # 同時含 ' 與 " ⇒ repr 用 ' 包、值內的 ' 比欄位引號多一層跳脫
    seen = []
    for k in range(2, 9):
        raw = _levels({"password": secret}, k, repr)[k]
        bs = len(re.search(r"(\\*)'password", raw).group(1))   # 欄位名前那串反斜線
        if bs in (7, 15, 31):
            seen.append(bs)
            assert "ZZtail9" in _D61.scrub_secrets(raw), "前提：d61a1fd 外露"
            assert "ZZtail9" not in scrub_secrets(raw), bs
    assert seen == [7, 15, 31]


def test_c_shallower_levels_unchanged():
    """1～4 層（≤3 個反斜線）舊規則已經遮得掉 → 輸出與 d61a1fd 逐字相同。"""
    for start, enc in (({"password": _SECRET}, repr), ({"password": _SECRET}, _json)):
        for k, raw in _levels(start, 4 if enc is repr else 3, enc).items():
            assert scrub_secrets(raw) == _D61.scrub_secrets(raw) and _SECRET not in scrub_secrets(raw), k


@pytest.mark.parametrize("raw", [
    _levels({"user": "bob", "note": "hi"}, 5, repr)[5],        # 不是秘密欄位
    "a" + "\\" * 7 + "'b" + "\\" * 7 + "': c",
    "\\" * 40 + "'password" + "\\" * 40 + "': 'x'",            # 超過上限 32：原樣（同 d61a1fd）
])
def test_c_ordinary_text_not_masked_more(raw):
    assert scrub_secrets(raw) == _D61.scrub_secrets(raw)


# ══════════════════════════════════════════════════════════════════
# 每條新規則都是承重的：拔掉 → 對應樣本外露
# ══════════════════════════════════════════════════════════════════
_RULE_SAMPLE = {
    "deep_quoted": (_levels({"password": _SECRET}, 5, repr)[5], _SECRET),
    "deep_assign": (_levels("password='%s'" % _SECRET, 5, repr)[5], _SECRET),
    "der_b64": (_B64, _LINES[3]),                 # 一整行：第二道（多行）認不到 ⇒ 仍只靠這一條
    "space_dir": ("/Users/Jane Doe/app/.streamlit/secrets.toml", "Jane Doe"),
}


@pytest.mark.parametrize("rule", sorted(_NEW_LINE))
def test_dropping_each_new_rule_leaks(rule):
    raw, gone = _RULE_SAMPLE[rule]
    assert gone not in scrub_secrets(raw)
    assert gone in _mutant((_NEW_LINE[rule], "")).scrub_secrets(raw), rule


def test_c_cap_is_32_backslashes():
    """上限 32（有界）：`repr` 第 7 層（31 個）遮得到；上限改成 6（< 7）→ 第 5 層就外露。"""
    raw7 = _levels({"password": _SECRET}, 7, repr)[7]
    assert _maxbs(raw7) == 31 and _SECRET not in scrub_secrets(raw7)
    m = _mutant(("(?P<pre>(?<!\\\\)(?P<bs>\\\\{5,32})", "(?P<pre>(?<!\\\\)(?P<bs>\\\\{5,6})"))
    assert _SECRET in m.scrub_secrets(_levels({"password": _SECRET}, 5, repr)[5])


def test_a_only_acts_when_a_directory_name_has_a_space():
    """沒有空白的路徑原樣交還（那是舊規則的職責）—— 拔掉舊的 `@` 規則，`@/home/…` 仍外露。"""
    m = _mutant(("    (_POSIX_PATH_EXTRA_RE, lambda m: MASK + \"/\" + (m.group(1) or \"\")),\n", ""))
    assert "aliceS3" in m.scrub_secrets("see @/home/aliceS3/.streamlit/secrets.toml")
    assert "aliceS3" not in scrub_secrets("see @/home/aliceS3/.streamlit/secrets.toml")


# ══════════════════════════════════════════════════════════════════
# ⭐ 語料回歸（對 d61a1fd 凍結副本）：不得少遮 ＋ 真實 UI 字串常值輸出變動數 0
# ══════════════════════════════════════════════════════════════════
def _consts(files) -> set[str]:
    out: set[str] = set()
    for f in files:
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                out.add(node.value)
    return out


@functools.lru_cache(maxsize=1)
def _ui_corpus() -> frozenset[str]:
    files = [*_ROOT.joinpath("src").rglob("*.py"), *_ROOT.joinpath("shared").rglob("*.py"), _ROOT / "app.py"]
    return frozenset(_consts(files))


@functools.lru_cache(maxsize=1)
def _secret_corpus() -> frozenset[str]:
    """既有測試裡的秘密樣本 ＋ 本批形態與 QA 實例的組合 ＋ 固定種子的隨機字串。"""
    out = _consts(f for f in _ROOT.joinpath("tests").glob("test_*.py")
                  if "scrub" in f.read_text(encoding="utf-8"))
    fields = ["password", "client_secret", "token", "Authorization", "api_key", "user"]
    vals = [_SECRET, "/Users/Jane Doe/x.toml", _B64[:80], "'x'", "\\n" + _B64[:70]]
    for f, v, enc in itertools.product(fields, vals, (repr, _json)):
        for d in (f"{f}: {v}", f"{f}={v}", {f: v}):
            out.update(_levels(d, 7, enc).values())
    out.update(r for r, *_ in _SPACE_PATHS)
    out.update(r for r, _ in _QA_N1)
    out.update(_DER_FORMS.values())
    out.update(_QA_N2.values())
    paths = ["/Users/Jane Doe/app/x.toml", "~/.streamlit/secrets.toml", "/data/2330.csv", "/2330", "~/My Docs/a b/x"]
    tails = [" 顯示殖利率 4.5%，配息 3 元/股。", " 放好後重啟；另外 MA20/MA60…", " 跟 聯發科/2454 哪個好？",
             " and then MA20/MA60", "，另外/股", " " + "A" * 41 + "/y", ""]
    for p, t, lead in itertools.product(paths, tails, ("", "檔案 ", "see `", "@", "b'x\\n")):
        out.add(lead + p + t)
    rnd = random.Random(20260928)
    alpha = (list("ab01MIAPz+/=_ :=＝：\"'\\/@→—~()\n\t.-%3D*，。字`") + fields
             + [MASK, "\\" * 7, "\\" * 15, "/Users/", "Jane Doe", " Doe/", "MIIEvQIBADANBgkq", "\\n", _TOKEN,
                _B64[:40], "A" * 40])
    for _ in range(6000):
        out.add("".join(rnd.choice(alpha) for _ in range(rnd.randint(1, 30))))
    return frozenset(out)


@functools.lru_cache(maxsize=1)
def _pairs() -> tuple[tuple[str, str, str], ...]:
    return tuple((r, _D61.scrub_secrets(r), scrub_secrets(r)) for r in _ui_corpus() | _secret_corpus())


def test_corpus_is_big_enough():
    """語料真的有收到東西（防「路徑寫錯 ⇒ 空語料 ⇒ 永遠綠」）。"""
    assert len(_ui_corpus()) > 10_000 and len(_secret_corpus()) > 5_000


def test_never_masks_less_than_d61a1fd():
    """新輸出必須能由 d61a1fd 的輸出「把若干段換成 `***`」得到（QA 判準）。"""
    worse = [r for r, o, n in _pairs() if not _is_masking_of(n, o)]
    assert not worse, [(r[:80], o[:80], n[:80]) for r, o, n in _pairs() if r in worse[:5]]


def test_real_ui_string_constants_unchanged():
    """`src/`、`shared/`、`app.py` 的字串常值：新版與 d61a1fd 輸出逐字相同（變動數 0）。"""
    ui = _ui_corpus()
    changed = sorted(r for r, o, n in _pairs() if r in ui and o != n)
    assert not changed, [(r[:120], _D61.scrub_secrets(r)[:120], scrub_secrets(r)[:120]) for r in changed[:10]]


# ══════════════════════════════════════════════════════════════════
# ReDoS：本批四條的對抗輸入（子程序＋時限；同 `test_sec_s2_scrub_gaps.test_new_rules_are_linear`）
# ══════════════════════════════════════════════════════════════════
_REDOS_N = 50_000
_B = "\\"
_UNITS = (
    # (c) 深層欄位：反斜線串超過上限、未收尾的值、值裡塞更深的引號、每個欄位反斜線數遞減
    _B * 40, _B * 7 + "'", _B * 7 + "'password" + _B * 7 + "': " + _B * 7 + "'",
    _B * 7 + "'password" + _B * 7 + "': " + _B * 7 + "'" + (_B * 15 + "x") * 3,
    "".join(_B * k + "'password" + _B * k + "': " + _B * k + "'x " for k in range(32, 4, -1)),
    "password=a' ", "password=" + _B * 7 + "'x", "key='x ",
    # (b) DER：短字、逐行、差一字滿 16 的空白續行、超長跳脫、剛好 39／40 字的行、含遮罩的行
    "MA ", "MAAAA\n", "MA" + "A" * 15 + " ", "A" * 16 + " ", "MA" + _B * 33 + "n", "MAAA" + _B + "n",
    "MA" + "A" * 37 + "\n", "MA" + "A" * 38 + "\n", "A" * 39 + "\n", "A" * 40 + "\n", "AA***\n", "***\n",
    "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSj\n", "MA" + "A" * 38 + " ",
    # (a) 空白路徑：起點很多、字數超過上限、括號、`~` 前綴、遮罩起點、剛好 40／41 字、中文與全形標點
    " /a", " /a b", "/a b c d e f ", "***/a b ", "***/a b c d e", "/a (b) c/", "~" + "a" * 70 + "/",
    "@/a b", "***/a(a(a(", "***/" + "a" * 40 + " ", " /" + "a" * 41 + " b", "***/x 字", " /字 a/",
    "***/x.toml 顯示殖利率 4.5%，配息 3 元", "/a b/字 ",
)
_SCRIPT = (
    "import json, sys, time\nimport shared.secret_scrub as S\nout = {}\n"
    "rules = {'deep': (S._DEEP_QUOTED_FIELD_RE, S._mask_deep_value),\n"
    "         'tail': (S._DEEP_ASSIGN_TAIL_RE, lambda m: m.group(1) + S.MASK),\n"
    "         'der': (S._DER_B64_RE, S._mask_der_b64), 'sp': (S._POSIX_SPACE_DIR_RE, S._mask_space_dirs)}\n"
    "for name, text in json.load(sys.stdin):\n"
    "    t = time.perf_counter(); S.scrub_secrets(text); out[name] = time.perf_counter() - t\n"
    "    for rn, (rx, rep) in rules.items():\n"
    "        t = time.perf_counter(); rx.sub(rep, text); out[name + '/' + rn] = time.perf_counter() - t\n"
    "print(json.dumps(out))\n")


def test_new_rules_are_linear():
    cases = [[f"u{i}", (u * (_REDOS_N // len(u) + 1))[:_REDOS_N]] for i, u in enumerate(_UNITS)]
    cases += [["der_one", "MA" + "A" * _REDOS_N], ["sp_one", "/" + "a " * (_REDOS_N // 2)],
              ["mask_one", "***/" + "a " * (_REDOS_N // 2)],
              ["deep_one", _B * 7 + "'password" + _B * 7 + "': " + _B * 7 + "'" + "x" * _REDOS_N],
              ["der_lines", "MA" + "A" * 62 + ("\n" + "A" * 64) * (_REDOS_N // 65)],
              ["der_key_rows", ("\n".join(_LINES) + "\n") * (_REDOS_N // len(_B64))]]
    r = subprocess.run([sys.executable, "-c", _SCRIPT], input=json.dumps(cases), capture_output=True,
                       text=True, timeout=60, cwd=str(_ROOT))
    assert r.returncode == 0, r.stderr[-2000:]
    slow = {k: v for k, v in json.loads(r.stdout).items() if v > 2.0}
    assert not slow, slow


# ══════════════════════════════════════════════════════════════════
# S2-f3：`page_why` 送給 L3 的提問先洗
# ══════════════════════════════════════════════════════════════════
_Q_KEY = "AIzaSyS3q0928AbCdEfGhIjKlMnOpQrStUv"
_Q_PW = "pwS3q0928zz"
_Q_USER = "aliceS3q"
_Q = f"金鑰 {_Q_KEY}、password={_Q_PW}、檔案在 /home/{_Q_USER}/app/.streamlit/secrets.toml，怎麼設定？"


def _capture_agent(monkeypatch, *, text: str = "偏強。") -> list:
    """把兩支下游 L3 換成假的，並**攔下實際送出的 question**（同 `test_p05_why_view._fake_agent`）。"""
    from tests.test_p05_why_view import _FakeQA

    calls: list = []
    _key = type(sys)("src.services.app_ai_service")
    _key.get_gemini_api_key = lambda: "k"
    _agent = type(sys)("src.services.ai_qa_service")

    def _run_agent(question, history=None, **kw):
        calls.append({"question": question, "history": history, **kw})
        return _FakeQA(ok=True, text=text)

    _agent.run_agent = _run_agent
    monkeypatch.setitem(sys.modules, "src.services.app_ai_service", _key)
    monkeypatch.setitem(sys.modules, "src.services.ai_qa_service", _agent)
    return calls


def test_f3_question_sent_to_l3_is_scrubbed(monkeypatch):
    from tests.test_p05_why_view import _FakeChatST, _render_qa

    calls = _capture_agent(monkeypatch)
    _render_qa(monkeypatch, _FakeChatST(typed=_Q))
    assert len(calls) == 1
    sent = calls[0]["question"]
    for leak in (_Q_KEY, _Q_PW, f"password={_Q_PW}", _Q_USER, f"/home/{_Q_USER}"):
        assert leak not in sent, (leak, sent)
    #: 純文字版（⛔ 不是 Markdown 跳脫版）：遮罩是 `***`，不是 `\*\*\*`。
    #: ~~`sent == scrub_secrets(_Q)`~~ → SEC-r12（2026-09-28）起送出走**散文版**，改和 `scrub_prose_secrets` 比對
    #: （批 Q QA 意見；有意識的修改，不是漏改）。本樣本不含散文形，兩支結果本來就相同 —— 改的是規格的寫法；
    #: 「送原文」的退回仍由上面的外露斷言與這一行一起擋（`page_why` 改回 `question=_question` → 本條轉紅）。
    assert sent == scrub_prose_secrets(_Q) and MASK in sent and "\\*" not in sent


def test_f3_clean_question_sent_byte_identical(monkeypatch):
    from tests.test_p05_why_view import _FakeChatST, _render_qa

    _clean = "2330 **健康度**？元/股 80/20 TW/US"
    calls = _capture_agent(monkeypatch)
    _render_qa(monkeypatch, _FakeChatST(typed=_clean))
    assert [c["question"] for c in calls] == [_clean]


def test_f3_space_path_in_question_is_scrubbed(monkeypatch):
    """S2-f3 × S2-f2(a)：目錄名含空白的家目錄路徑，送出去的也看不到使用者名稱。"""
    from tests.test_p05_why_view import _FakeChatST, _render_qa

    calls = _capture_agent(monkeypatch)
    _render_qa(monkeypatch, _FakeChatST(typed="檔案 /Users/Alice S3q/app/.streamlit/secrets.toml 對嗎？"))
    sent = calls[0]["question"]
    assert "Alice" not in sent and "S3q" not in sent and sent.endswith("***/secrets.toml 對嗎？")


def test_f3_not_asked_sends_nothing(monkeypatch):
    from tests.test_p05_why_view import _FakeChatST, _render_qa

    calls = _capture_agent(monkeypatch)
    _render_qa(monkeypatch, _FakeChatST(typed="   "))
    assert calls == []


def test_f3_request_shape_asked_from_raw_question_from_scrubbed():
    """規格：`asked` 照原文判斷；`question` ＝ ~~`scrub_secrets(原文)`~~ `scrub_prose_secrets(原文)`
    （純文字版，⛔ 不是 `scrub_qa_text`）。

    ⚠️ SEC-r12（2026-09-28）更新本條最後一個斷言 —— 有意識的修改，不是漏改：原斷言釘住的函式名
    `scrub_secrets` 正是 SEC-r12 的病灶（它的第 1 類把「為什麼出現 型別名＋冒號…怎麼解？」截成只剩型別名，
    連問題都送不出去）。改釘散文版；「純文字版、⛔ 不是 Markdown 版」與 `asked` 照原文判斷兩點不變。
    行為面見 `tests/test_sec_r12_r11_prose_scrub.py`（送出的提問保留引用的錯誤訊息、秘密照遮）。
    """
    from src.ui.views import page_why as P

    fn = next(n for n in ast.walk(ast.parse(pathlib.Path(P.__file__).read_text(encoding="utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == "_render_qa_leaf")
    reqs = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "QaRequest"]
    assert len(reqs) == 1
    kw = {k.arg: ast.unparse(k.value) for k in reqs[0].keywords}
    assert kw["asked"] == "bool(_question)"
    assert kw["question"] == "scrub_prose_secrets(_question)"
