"""SEC 批次 S3（2026-09-28）：S2-f3 ／ S2-f2（a）（b）（c）。

- S2-f3：`page_why._render_qa_leaf` 建 `QaRequest` 時帶的是**原文**提問，經 L3 `run_agent` 原樣送給
  Gemini（畫面上的紀錄反而是洗過的）→ 建 `QaRequest` 前先 `scrub_secrets`（純文字版）。
- S2-f2：`shared/secret_scrub._RULES_POST` 補三種**少遮**形態：
  (a) 目錄名含空白的 POSIX 路徑（`/Users/Jane Doe/…` → 舊版 `***/Jane Doe/…`，使用者名稱與目錄外露）；
  (b) 沒有標頭的 PEM／DER base64 本體（`MIIEvQIBADANBgkq…`，≥60 字、可跨行，舊版原樣輸出）；
  (c) 深層巢狀 `repr`／JSON 的 `{'password': …}`（引號前 ≥5 個反斜線，舊版上限 `\\\\{0,4}` ⇒ 外露）。

⭐ 硬性要求：**任何輸入都不得比舊版少遮**；真實 UI 字串常值（`src/`、`shared/`、`app.py`）輸出變動數 0。
「舊版」＝本模組把本批四條規則從 `_RULES_POST` 拔掉的突變體（本批只在 `_RULES_POST` 尾端加規則，
其餘是註解與新定義 ⇒ 拔掉後與 `d61a1fd` 語意相同）。
每條新規則拔掉（突變）→ 對應樣本外露（`test_dropping_each_new_rule_leaks`）。
"""
from __future__ import annotations

import ast
import base64
import collections
import functools
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
from shared.secret_scrub import MASK, scrub_secrets

_ROOT = pathlib.Path(__file__).resolve().parents[1]


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
    "der_b64": "    (_DER_B64_RE, _mask_der_b64),\n",
    "space_dir": "    (_POSIX_SPACE_DIR_RE, _mask_space_dirs),\n",
}
#: 舊版：本批四條全部拔掉。
_OLD = _mutant(*((line, "") for line in _NEW_LINE.values()))


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
]


@pytest.mark.parametrize("raw,gone,want", _SPACE_PATHS)
def test_a_space_in_directory_name_masked(raw, gone, want):
    out = scrub_secrets(raw)
    assert out == want, out
    assert not [g for g in gone if g in out], out
    assert any(g in _OLD.scrub_secrets(raw) for g in gone), "前提：舊版確實外露"


#: 一般文字 ⛔ 不誤遮：與舊版逐字相同（本條只在「某個目錄段真的含空白」時才動手）。
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
    assert scrub_secrets(raw) == want == _OLD.scrub_secrets(raw)


# ══════════════════════════════════════════════════════════════════
# S2-f2 (b)：沒有標頭的 PEM／DER base64 本體
# ══════════════════════════════════════════════════════════════════
#: 仿 PKCS#8 RSA 私鑰：真實的 DER 開頭（`MIIEvQIBADANBgkq…`）＋ 固定種子的位元組（⛔ 不是真金鑰）。
_DER = (bytes.fromhex("308204bd020100300d06092a864886f70d0101010500048204a7")
        + random.Random(20260928).randbytes(1193))
_B64 = base64.b64encode(_DER).decode()
_LINES = [_B64[i:i + 64] for i in range(0, len(_B64), 64)]
#: Ed25519 PKCS#8（48 位元組 → 64 字，`MC4C…`）。
_ED25519 = base64.b64encode(bytes.fromhex("302e020100300506032b657004220420")
                            + random.Random(7).randbytes(32)).decode()


def test_b_sample_really_looks_like_a_pem_body():
    assert _B64.startswith("MIIEvQIBADANBgkq") and len(_LINES) == 26
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
    assert any(c[:40] in _OLD.scrub_secrets(raw) for c in chunks), "前提：舊版確實外露"


_DER_LAYOUTS = {
    "real_newlines": (lambda ls: "\n".join(ls), MASK),
    "repr_escaped": (lambda ls: repr("\n".join(ls)), f"'{MASK}'"),
    "json_escaped": (lambda ls: json.dumps("\n".join(ls)), f'"{MASK}"'),
    "space_joined": (lambda ls: " ".join(ls), MASK),
}


@pytest.mark.parametrize("layout", sorted(_DER_LAYOUTS))
def test_b_no_line_of_any_key_leaks(layout):
    """200 把固定種子、長度各異（最後一行 0～63 字都有）的假金鑰，整段都要遮掉。

    base64 含 `/`：約 1/64 的行以 `/` 開頭，前面的路徑規則會先把那一行遮成 `***/…`（`4/…`、`1//…` 同理）——
    本體 ⛔ 不能在那裡斷掉（實作時實際踩過：上面那把的第 21 行以 `/` 開頭，之後各行外露）。
    """
    enc, want = _DER_LAYOUTS[layout]
    pre_masked = 0
    for seed in range(200):
        b64 = base64.b64encode(_DER[:26] + random.Random(seed).randbytes(1100 + seed)).decode()
        lines = [b64[i:i + 64] for i in range(0, len(b64), 64)]
        raw = enc(lines)
        out = scrub_secrets(raw)
        if layout == "space_joined" and len(lines[-1]) < 16 and not lines[-1].endswith("="):
            #: 已知邊界（檔頭有寫）：貼成一行時，最後一段 <16 字又沒有 `=` 補位 → 分不出是說明字，不吃（≤15 字）。
            assert out == MASK + " " + lines[-1], seed
        else:
            assert out == want, seed
        pre_masked += MASK in _OLD.scrub_secrets(raw)
    assert pre_masked, "前提：語料裡確實有「某一行先被舊規則遮掉一段」的金鑰"


def test_b_prose_around_the_body_kept():
    assert scrub_secrets(_DER_FORMS["in_prose"]) == "私鑰是 *** 對嗎？"
    assert scrub_secrets(_DER_FORMS["after_equals"]) == "data=***"


def test_b_threshold_is_60_base64_chars():
    assert scrub_secrets(_B64[:59]) == _B64[:59]
    assert scrub_secrets(_B64[:60]) == MASK
    #: 跨行也是算合計字數（換行、跳脫、`=` 不算字）。
    assert scrub_secrets(_B64[:30] + "\\n" + _B64[30:59]) == _B64[:30] + "\\n" + _B64[30:59]
    assert scrub_secrets(_B64[:30] + "\\n" + _B64[30:60]) == MASK


@pytest.mark.parametrize("raw", [
    "MACD 與 MA20 的交叉", "MSCI 權重", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "MIIE",
    "Many Managers Made Money in March", "sha256=" + "9f" * 32, "M" + "a" * 70,
    "MA" + "b" * 20 + " " + "c" * 15 + " end"])
def test_b_ordinary_text_not_masked(raw):
    assert scrub_secrets(raw) == raw == _OLD.scrub_secrets(raw)


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
        assert _SECRET in _OLD.scrub_secrets(raw), f"前提：舊版第 {k} 層確實外露"


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
            assert "ZZtail9" in _OLD.scrub_secrets(raw), "前提：舊版外露"
            assert "ZZtail9" not in scrub_secrets(raw), bs
    assert seen == [7, 15, 31]


def test_c_shallower_levels_unchanged():
    """1～4 層（≤3 個反斜線）舊規則已經遮得掉 → 輸出與舊版逐字相同。"""
    for start, enc in (({"password": _SECRET}, repr), ({"password": _SECRET}, _json)):
        for k, raw in _levels(start, 4 if enc is repr else 3, enc).items():
            assert scrub_secrets(raw) == _OLD.scrub_secrets(raw) and _SECRET not in scrub_secrets(raw), k


@pytest.mark.parametrize("raw", [
    _levels({"user": "bob", "note": "hi"}, 5, repr)[5],        # 不是秘密欄位
    "a" + "\\" * 7 + "'b" + "\\" * 7 + "': c",
    "\\" * 40 + "'password" + "\\" * 40 + "': 'x'",            # 超過上限 32：原樣（同舊版）
])
def test_c_ordinary_text_not_masked_more(raw):
    assert scrub_secrets(raw) == _OLD.scrub_secrets(raw)


# ══════════════════════════════════════════════════════════════════
# 每條新規則都是承重的：拔掉 → 對應樣本外露
# ══════════════════════════════════════════════════════════════════
_RULE_SAMPLE = {
    "deep_quoted": (_levels({"password": _SECRET}, 5, repr)[5], _SECRET),
    "deep_assign": (_levels("password='%s'" % _SECRET, 5, repr)[5], _SECRET),
    "der_b64": ("\n".join(_LINES), _LINES[3]),
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
# ⭐ 語料回歸：不得比舊版少遮 ＋ 真實 UI 字串常值輸出變動數 0
# ══════════════════════════════════════════════════════════════════
def _ctr(s: str) -> collections.Counter:
    return collections.Counter(c for c in s if c != "*" and not c.isspace())


def _is_subsequence(small: str, big: str) -> bool:
    it = iter(big)
    return all(c in it for c in small)


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
    """既有測試裡的秘密樣本 ＋ 本批三種形態的組合 ＋ 固定種子的隨機字串。"""
    out = _consts(f for f in _ROOT.joinpath("tests").glob("test_*.py")
                  if "scrub" in f.read_text(encoding="utf-8"))
    fields = ["password", "client_secret", "token", "Authorization", "api_key", "user"]
    vals = [_SECRET, "/Users/Jane Doe/x.toml", _B64[:80], "'x'", "\\n" + _B64[:70]]
    for f, v, enc in itertools.product(fields, vals, (repr, _json)):
        for d in (f"{f}: {v}", f"{f}={v}", {f: v}):
            out.update(_levels(d, 7, enc).values())
    out.update(r for r, *_ in _SPACE_PATHS)
    out.update(_DER_FORMS.values())
    rnd = random.Random(20260928)
    alpha = (list("ab01MIAPz+/=_ :=＝：\"'\\/@→—~()\n\t.-%3D*") + fields
             + [MASK, "\\" * 7, "\\" * 15, "/Users/", "Jane Doe", " Doe/", "MIIEvQIBADANBgkq", "\\n", _TOKEN])
    for _ in range(6000):
        out.add("".join(rnd.choice(alpha) for _ in range(rnd.randint(1, 30))))
    return frozenset(out)


@functools.lru_cache(maxsize=1)
def _pairs() -> tuple[tuple[str, str, str], ...]:
    return tuple((r, _OLD.scrub_secrets(r), scrub_secrets(r)) for r in _ui_corpus() | _secret_corpus())


def test_corpus_is_big_enough():
    """語料真的有收到東西（防「路徑寫錯 ⇒ 空語料 ⇒ 永遠綠」）。"""
    assert len(_ui_corpus()) > 10_000 and len(_secret_corpus()) > 5_000


def test_never_masks_less_than_old():
    """新版遮到的必須涵蓋舊版遮到的：非遮罩字元只少不多（計數），而且是舊版輸出的子序列（順序）。"""
    worse = [r for r, o, n in _pairs()
             if _ctr(n) - _ctr(o) or not _is_subsequence(n.replace("*", ""), o.replace("*", ""))]
    assert not worse, worse[:5]


def test_real_ui_string_constants_unchanged():
    """`src/`、`shared/`、`app.py` 的字串常值：新舊版輸出逐字相同（變動數 0）。"""
    ui = _ui_corpus()
    changed = sorted(r for r, o, n in _pairs() if r in ui and o != n)
    assert not changed, [(r[:120], _OLD.scrub_secrets(r)[:120], scrub_secrets(r)[:120]) for r in changed[:10]]


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
    # (b) DER：短字、逐行、差一字滿 16 的空白續行、超長跳脫
    "MA ", "MAAAA\n", "MA" + "A" * 15 + " ", "A" * 16 + " ", "MA" + _B * 33 + "n", "MAAA" + _B + "n",
    # (a) 空白路徑：起點很多、字數超過上限、括號、`~` 前綴、遮罩起點
    " /a", " /a b", "/a b c d e f ", "***/a b ", "***/a b c d e", "/a (b) c/", "~" + "a" * 70 + "/",
    "@/a b", "***/a(a(a(",
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
              ["deep_one", _B * 7 + "'password" + _B * 7 + "': " + _B * 7 + "'" + "x" * _REDOS_N]]
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
    assert sent == scrub_secrets(_Q) and MASK in sent and "\\*" not in sent


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
    """規格：`asked` 照原文判斷；`question` ＝ `scrub_secrets(原文)`（純文字版，⛔ 不是 `scrub_qa_text`）。"""
    from src.ui.views import page_why as P

    fn = next(n for n in ast.walk(ast.parse(pathlib.Path(P.__file__).read_text(encoding="utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == "_render_qa_leaf")
    reqs = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "QaRequest"]
    assert len(reqs) == 1
    kw = {k.arg: ast.unparse(k.value) for k in reqs[0].keywords}
    assert kw["asked"] == "bool(_question)"
    assert kw["question"] == "scrub_secrets(_question)"
