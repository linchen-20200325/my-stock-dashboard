"""批 S6（SEC-r28／SEC-r29 (b)／SEC-r30；2026-10-02）：`scrub_secrets` 補洞與 `tests/_git_tracked.py` 測試補強。

⭐ 硬性要求（同批 S3／S4）：任何輸入都不得比 **e23ff2f 凍結副本**、**bf0ada3 凍結副本**、**main 792c7a2 凍結副本**
（`tests/fixtures/secret_scrub_792c7a2.py`，批 S6 動工前的 main）少遮。判準沿用 `tests/test_sec_s3_0928._is_masking_of`。
"""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib

import pytest

from shared.secret_scrub import MASK, scrub_prose_secrets, scrub_secrets
from tests.test_sec_s3_0928 import _is_masking_of, _mutant
from tests.test_sec_s3_batch_s3 import _FIXTURE_MARKER
from tests.test_sec_s4_batch_s4 import _index
from tests.test_sec_s4_batch_s4 import _never_less as _never_less_e23_bf0

_ROOT = pathlib.Path(__file__).resolve().parents[1]

# ══════════════════════════════════════════════════════════════════
# 基準三：main 792c7a2（批 S4 合併點，批 S6 動工前）的凍結副本
# ══════════════════════════════════════════════════════════════════
_MAIN_FIXTURE = _ROOT / "tests" / "fixtures" / "secret_scrub_792c7a2.py"
#: `git show 792c7a2:shared/secret_scrub.py | sha256sum`（blob e6219c05ab92e40e0476d9369fdb6b6d4fc57113）。
_MAIN_SHA256 = "b6a612c5ba1b0d98a8d2e5b53a9ccb6631c374b6847fbce6e93c733b15153e66"


def _load_main():
    spec = importlib.util.spec_from_file_location("_secret_scrub_792c7a2", _MAIN_FIXTURE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MAIN = _load_main()


def test_baseline_main_792c7a2_is_frozen_byte_for_byte():
    raw = _MAIN_FIXTURE.read_bytes()
    marker = _FIXTURE_MARKER.encode("utf-8")
    assert raw.count(marker) == 1
    assert hashlib.sha256(raw.split(marker, 1)[1]).hexdigest() == _MAIN_SHA256
    assert _MAIN.scrub_secrets is not scrub_secrets


def _never_less(raw: str) -> None:
    """不得比 e23ff2f、bf0ada3（`tests/test_sec_s4_batch_s4._never_less`）、也不得比 main 792c7a2 少遮。"""
    _never_less_e23_bf0(raw)
    new_e, new_p = scrub_secrets(raw), scrub_prose_secrets(raw)
    assert _is_masking_of(new_e, _MAIN.scrub_secrets(raw)), ("main", raw[:120], new_e[:120])
    assert _is_masking_of(new_p, _MAIN.scrub_prose_secrets(raw)), ("main-prose", raw[:120], new_p[:120])


# ══════════════════════════════════════════════════════════════════
# SEC-r28 ①：`_TOML_ORIG_MAX` 64 → 1 的突變原本活著 —— 補「≥2 個不同值、錨點都被吃掉」的固定樣本
# ══════════════════════════════════════════════════════════════════
#: 兩段各自被查詢參數那一條吃掉錨點（`abc\ncould` 經 repr 後同一行），值不同 ⇒ 原始文字那一道要記下 ≥2 個值。
_R28_TWO_EATEN = repr(
    "GET https://x.com/v1?token=abc\ncould not convert string to float: '1.2SEC' (line 1 column 1 char 0)\n"
    "GET https://x.com/v2?token=abc\ncould not convert string to float: '3.4TWO' (line 1 column 1 char 0)")


@pytest.mark.parametrize("fn", [scrub_secrets, scrub_prose_secrets], ids=["errors", "prose"])
def test_r28_two_distinct_eaten_toml_values_both_masked(fn):
    out = fn(_R28_TWO_EATEN)
    assert "1.2SEC" not in out and "3.4TWO" not in out, out
    _never_less(_R28_TWO_EATEN)


def test_r28_mutant_orig_max_1_leaks_second_value():
    m = _mutant(("_TOML_ORIG_MAX: int = 64", "_TOML_ORIG_MAX: int = 1"))
    assert "3.4TWO" in m.scrub_secrets(_R28_TWO_EATEN)
    assert "3.4TWO" not in scrub_secrets(_R28_TWO_EATEN)


# ══════════════════════════════════════════════════════════════════
# SEC-r28 ②：拿掉「補齊位元組必須是 NUL」那一道的突變原本活著
# ══════════════════════════════════════════════════════════════════
def _r28_bad_padding() -> bytes:
    """一個項目 `ab`（62＋2＝64 位元組 → 補 8 個 NUL），把第 2 個補齊位元組改成非 NUL；檔尾全 0（skipHash 形）。"""
    body = _index(["ab"], 2)[:-20]
    at = 12 + 64 + 1
    return body[:at] + b"x" + body[at + 1:] + bytes(20)


def _gt_mutant(old: str, new: str) -> dict:
    src = (_ROOT / "tests" / "_git_tracked.py").read_text(encoding="utf-8")
    assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
    g: dict = {"__name__": "_gt_mutant"}
    exec(compile(src.replace(old, new), "_gt_mutant", "exec"), g)
    return g


_PAD_CHECK = ' or data[nul:i].strip(b"\\0")'


def test_r28_non_nul_padding_on_zero_trailer_index_raises():
    from tests._git_tracked import IndexCorrupt, parse_index
    with pytest.raises(IndexCorrupt, match="補齊的 NUL"):
        parse_index(_r28_bad_padding())


def test_r28_mutant_without_padding_check_silently_returns_path():
    g = _gt_mutant(_PAD_CHECK, "")
    assert g["parse_index"](_r28_bad_padding()) == frozenset({"ab"})


# ══════════════════════════════════════════════════════════════════
# SEC-r29 (b)：重複表訊息的 dict 用 HTML 跳脫引號（網頁上複製下來）→ 原本整包外露
# ══════════════════════════════════════════════════════════════════
_HTML_Q = ("&#x27;", "&#39;", "&quot;")
_SUFFIXES = ("", " (line 1 column 1 char 0)")
_R29B_HTML = [f"What? a already exists?{{{q}a{q}: {q}V9SEC{q}}}{suf}" for q in _HTML_Q for suf in _SUFFIXES]
_R29B_PLAIN = [f"What? a already exists?{{{q}a{q}: {q}V9SEC{q}}}{suf}" for q in ("'", '"', "\\'", "\\\\'")
               for suf in _SUFFIXES]


@pytest.mark.parametrize("fn", [scrub_secrets, scrub_prose_secrets], ids=["errors", "prose"])
@pytest.mark.parametrize("x", _R29B_HTML)
def test_r29b_html_quoted_dup_table_dict_masked(x, fn):
    assert "V9SEC" in _MAIN.scrub_secrets(x), "前提：main 外露"
    out = fn(x)
    assert "V9SEC" not in out and out.startswith("What? a already exists?***"), out
    _never_less(x)


@pytest.mark.parametrize("fn", [scrub_secrets, scrub_prose_secrets], ids=["errors", "prose"])
@pytest.mark.parametrize("x", _R29B_PLAIN)
def test_r29b_plain_quote_forms_unchanged_vs_main(x, fn):
    main_fn = _MAIN.scrub_secrets if fn is scrub_secrets else _MAIN.scrub_prose_secrets
    assert fn(x) == main_fn(x) and "V9SEC" not in fn(x)


@pytest.mark.parametrize("x", ["already exists?{&amp;x}", "already exists?{a: &#x27;b&#x27;}", "already exists?&#x27;a&#x27;",
                               "already exists?{ &quot;a&quot;}", "什麼 already exists? {&#39;a&#39;: 1}"])
def test_r29b_non_toml_shapes_unchanged(x):
    """只放寬「`{` 後面緊接引號」那個前瞻：`{` 後不是引號、`?` 後不是 `{` → 原樣。"""
    assert scrub_secrets(x) == x == _MAIN.scrub_secrets(x)


_R29B_OFF = ("    if any(_n in out for _n in _POST_NEEDLES[_TOML_EXISTS_DICT_HTML_RE]):\n", "    if False:\n")
#: 實作組自測抓到的少遮形態（若把 HTML 引號直接併進 `_TOML_EXISTS_DICT_RE`，它先遮到行尾、數字轉換那一條就少遮）。
_R29B_ORDER = [
    "'could not convert string to float: \\&#x27;&#x27;could not convert string to float: already exists?{&quot;a\""
    "could not convert string to float:  (line 1 column 1 char 0)",
    'could not convert string to float: "already exists?{already exists?{&#x27;TomlDecodeError}SEC}?token=abc\\n',
]


@pytest.mark.parametrize("x", _R29B_ORDER)
def test_r29b_rule_order_never_masks_less_than_main(x):
    _never_less(x)


def test_r29b_mutant_widening_old_rule_instead_masks_less():
    """反證排序是承重的：把 HTML 引號併進原本那一條（排在數字轉換之前）→ 上面的樣本比 main 少遮。"""
    from tests.test_sec_s3_0928 import _is_masking_of
    m = _mutant(_R29B_OFF, (r'''(?=\\{0,4}['\"])[^\r\n]*")''' + "\n#: 批 S6",
                            r'''(?=\\{0,4}(?:['\"]|&#x27;|&#39;|&quot;))[^\r\n]*")''' + "\n#: 批 S6"))
    assert any(not _is_masking_of(m.scrub_secrets(x), _MAIN.scrub_secrets(x)) for x in _R29B_ORDER)


def test_r29b_mutant_without_html_quotes_leaks():
    m = _mutant(_R29B_OFF)
    assert all("V9SEC" in m.scrub_secrets(x) for x in _R29B_HTML)
    assert not any("V9SEC" in scrub_secrets(x) for x in _R29B_HTML)


# ══════════════════════════════════════════════════════════════════
# ⭐ 結構保證：關掉本批新增的部分 → 輸出與 main 792c7a2 逐字相同；且本批任何樣本都不比 main／bf0ada3／e23ff2f 少遮
# ══════════════════════════════════════════════════════════════════
#: 本批每一項的「關掉」突變（後面各項完成時一併登記）。
#: 批 S6 QA 修正輪起：本批新增的遮罩全部集中在 `_mask_s6`（main 整條流程之後），這一項關掉全部；各項自己的關掉突變另外登記。
_S6_ALL_OFF = ("    return _mask_s6(orig_vals, out)\n", "    return out\n")
_S6_OFF: list[tuple[str, str]] = [_S6_ALL_OFF, _R29B_OFF]  # SEC-r29 (c) 的關掉突變在檔尾登記（_R29C_OFF）
#: 本批新增的樣本（一併涵蓋於結構保證與「不少遮」）。
_S6_EXTRA_CORPUS: list[str] = _R28_TWO_EATEN.splitlines() + [_R28_TWO_EATEN] + _R29B_HTML + _R29B_PLAIN + _R29B_ORDER


def _s6_corpus(step: int) -> list[str]:
    import random

    from tests.test_sec_s4_batch_s4 import _s4_corpus
    out = _s4_corpus(step=step, r4=2000 // step) + _S6_EXTRA_CORPUS
    rnd = random.Random(20261002)
    alpha = ["already exists?{", *_HTML_Q, "'", '"', "\\", "a", ": ", "}", " (line 1 column 1 char 0)", "\n",
             "could not convert string to float: ", "TomlDecodeError", "?token=abc\\n", "MIIB", "SEC"]
    out += ["".join(rnd.choice(alpha) for _ in range(rnd.randint(1, 14))) for _ in range(3000 // step)]
    return out


def _s6_check(corpus: list[str]) -> None:
    m = _mutant(*_S6_OFF)
    diff = [r for r in corpus if m.scrub_secrets(r) != _MAIN.scrub_secrets(r)
            or m.scrub_prose_secrets(r) != _MAIN.scrub_prose_secrets(r)]
    assert not diff, [d[:120] for d in diff[:5]]
    worse = []
    for r in corpus:
        try:
            _never_less(r)
        except AssertionError:
            worse.append(r)
    assert not worse, [w[:120] for w in worse[:5]]


def test_s6_off_is_exactly_main_and_never_less_sample():
    _s6_check(_s6_corpus(step=15))


@pytest.mark.slow
def test_s6_off_is_exactly_main_and_never_less_full():
    _s6_check(_s6_corpus(step=1))


def test_s6_ui_string_constants_unchanged_vs_main():
    """UI 字串常數（全大寫、型別為 str 的模組常數）與 main 逐字相同。"""
    import shared.secret_scrub as SSC
    cur = {k: v for k, v in vars(SSC).items() if k.isupper() and isinstance(v, str)}
    old = {k: v for k, v in vars(_MAIN).items() if k.isupper() and isinstance(v, str)}
    assert cur == old
    #: ~~`assert SSC.__doc__ == _MAIN.__doc__`~~ ← 批 S6 QA 修正輪（2026-10-02）移除，有意識的更正、不是漏刪：檔頭是行為描述，
    #: 本批要據實補上 SEC-r29 (b)／(c) 與 F1／F3 的行為與邊界（批 S6 QA 第一組 G3），不再與 main 逐字相同；UI 字串常數照舊逐字核對。


# ══════════════════════════════════════════════════════════════════
# ReDoS／CPU（子程序、CPU 時間取三次最小值；對 main 792c7a2）與記憶體峰值 —— 批 S4 的對抗形態＋本批新增
# ══════════════════════════════════════════════════════════════════
def _s6_forms(n: int) -> dict[str, str]:
    from tests.test_sec_s4_batch_s4 import _s4_forms
    f = dict(_s4_forms(n))
    f.update({
        "dup_html_many": "already exists?{&#x27;" * (n // 21), "dup_html_open": "already exists?{&quot;" + "x" * n,
        "dup_html_lines": ("already exists?{&#39;a&#39;: &#39;v&#39;}\n") * (n // 40),
        "dup_bs_html": "already exists?{" + "\\" * n,
    })
    f.update(_S6_EXTRA_FORMS(n))
    return {k: v[:n] for k, v in f.items()}


def _S6_EXTRA_FORMS(n: int) -> dict[str, str]:  # noqa: N802 —— 後面各項擴充
    #: SEC-r29 (c)：剩餘片段那一道 —— 錨點很多、值很長、64 個不同的長值各帶大量錨點、DER 行吃掉錨點。
    from tests.test_sec_s3_batch_s3 import _b64, _pkcs8, _wrap
    key = _wrap(_b64(_pkcs8(5)))[0]
    conv = "could not convert string to float: "
    anchor = "' (line 1 column 1 char 0)"
    longv = key + "\n" + conv + "'" + "A" * 4000 + " S" + anchor
    many_vals = "".join(f"{key}\n{conv}'{'B' * 3000}{k:04d} S{anchor}" + ("x" + anchor) * 300 for k in range(64))
    return {"rem_anchor_flood": longv + ("y" * 3 + anchor) * (n // 30),
            "rem_anchor_mask_flood": longv.replace(anchor, "'\nTomlDecodeError") + ("'" + MASK + "zzzz") * (n // 8),
            "rem_many_long_values": many_vals * (n // len(many_vals) + 1),
            "rem_der_eaten_lines": (key + "\n" + conv + "'" + key + " S" + anchor + "\n") * (n // 200),
            #: 批 S6 QA F1：整窗都是 `***` 的錨點（見 `_f1_repro`）；HTML 引號超長值（批 S6 QA F3）。
            "rem_star_windows": _f1_repro() * (n // 380_000 + 1),
            #: 批 S6 QA 第二輪：沒有英數字、沒有位置字尾的視窗（第二種錨點「收尾引號＋遮罩」）× 64 個長值。
            "rem_noalnum_dot": _qa2_repro(4000, " ." * 150, n), "rem_noalnum_dash": _qa2_repro(4000, "-" * 300, n),
            "rem_noalnum_emdash": _qa2_repro(4000, "—" * 300, n), "rem_noalnum_star999": _qa2_repro(999, "*" * 300, n),
            "html_long_values": ("could not convert string to float: &#x27;" + "x" * 5000 + " (line 1 column 1 char 0)\n") * (n // 5000)}


_CPU_SCRIPT_MAIN = (
    "import json, sys, time, importlib.util\nimport shared.secret_scrub as S\n"
    "spec = importlib.util.spec_from_file_location('m', 'tests/fixtures/secret_scrub_792c7a2.py')\n"
    "B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)\nout = {}\n"
    "def cpu(f):\n"
    "    best = None\n"
    "    for _ in range(3):\n"
    "        t = time.process_time(); f(); d = time.process_time() - t\n"
    "        best = d if best is None else min(best, d)\n"
    "    return best\n"
    "for name, text in json.load(sys.stdin):\n"
    "    out[name] = [cpu(lambda: S.scrub_secrets(text)), cpu(lambda: S.scrub_prose_secrets(text)),\n"
    "                 cpu(lambda: B.scrub_secrets(text)), cpu(lambda: B.scrub_prose_secrets(text))]\n"
    "print(json.dumps(out))\n")


def _cpu(n: int, timeout: int) -> dict:
    import json
    import subprocess
    import sys
    cases = [[k, v] for k, v in _s6_forms(n).items()]
    r = subprocess.run([sys.executable, "-c", _CPU_SCRIPT_MAIN], input=json.dumps(cases), capture_output=True,
                       text=True, timeout=timeout, cwd=str(_ROOT))
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout)


def test_s6_linear_50k():
    """50k 字：每種形態 ≤ 2 秒（CPU），且不比 main 慢 3 倍以上（下限 0.3 秒，量測雜訊）。"""
    bad = {k: v for k, v in _cpu(50_000, 600).items() if max(v[:2]) > 2.0 or max(v[:2]) > max(3 * max(v[2:]), 0.3)}
    assert not bad, bad


@pytest.mark.slow
def test_s6_cpu_400k_within_2x_main_and_1_5s():
    """400k 字：每種形態 ≤ 1.5 秒（CPU），且 ≤ 2 倍 main（下限 0.05 秒，量測雜訊）。"""
    bad = {k: v for k, v in _cpu(400_000, 1800).items()
           if max(v[:2]) > 1.5 or max(v[:2]) > max(2 * max(v[2:]), 0.05)}
    assert not bad, bad


@pytest.mark.slow
def test_s6_memory_within_5mb_of_main():
    """40 萬字、每種形態：比 main 多出的峰值（tracemalloc）≤ 5 MB（同批 S3／S4 的上限）。"""
    from tests.test_sec_s3_batch_s3 import _peak_mb
    worse = {}
    for name, t in _s6_forms(400_000).items():
        old = max(_peak_mb(_MAIN.scrub_secrets, t), _peak_mb(_MAIN.scrub_prose_secrets, t))
        new = max(_peak_mb(scrub_secrets, t), _peak_mb(scrub_prose_secrets, t))
        if new - old > 5:
            worse[name] = (old, new)
    assert not worse, worse


# ══════════════════════════════════════════════════════════════════
# SEC-r30：split index 報清楚的「格式不支援」；檔尾全 0（skipHash，不論設定寫在哪）一律以結構核對
# ══════════════════════════════════════════════════════════════════
#: 真的 git（2.43.0，2026-10-02）產出的索引檔，base64。產生方式（在暫存目錄；⛔ 測試本身不呼叫 git）：
#:   split-v2／split-v4：`git config splitIndex.maxPercentChange 100`；5 個檔 add＋commit（v4 先 `git update-index
#:     --index-version 4`）；`git update-index --split-index`；改 a.md、新增 e.md 後 `git add .`
#:     ⇒ 5 個「被取代項目」路徑長 0（git 寫入時剝掉名字）＋ e.md ＋ `link` 擴充。
#:   skiphash-v2／skiphash-v4：`git -c index.skipHash=true add .`（v4 另加 `-c index.version=4`）—— 設定只在命令列，
#:     repo 的 `.git/config` 看不到（修前因此誤判 `IndexCorrupt`）。
_REAL_INDEX_B64 = {
    "split-v2": (
        "RElSQwAAAAIAAAAGar8dPwfzqXVqvx0/B/OpdQAA/gAANMbiAACBpAAAAAAAAAAAAAAAB3S/CYBf3qtVDjUNCVuU3pXrdFbz"
        "AAAAAGq/HT4mDl1Par8dPiYOXU8AAP4AADTG5gAAgaQAAAAAAAAAAAAAAAVJPNW6J4b/RMFQetPqeZmTfQ7IXgAAAABqvx0+"
        "JngpgGq/HT4meCmAAAD+AAA0xugAAIGkAAAAAAAAAAAAAAAHbO5H98fZ2+S24gqMs+ORXVyuuuEAAAAAar8dPia1MoBqvx0+"
        "JrUygAAA/gAANMbpAACBpAAAAAAAAAAAAAAABcEIEiN5lHz4ab1F3evsoedlR0BXAAAAAGq/HT4m8juAar8dPibyO4AAAP4A"
        "ADTG6gAAgaQAAAAAAAAAAAAAAAVDhvaxIB17ongVbLNdeZPCcQQb2gAAAABqvx0/B/OpdWq/HT8H86l1AAD+AAA0xvUAAIGk"
        "AAAAAAAAAAAAAAACWHvmtMP5P5PEicARG7pVlhR6JssABGUubWQAAAAAAABsaW5rAAAARC/ePsoOqw4KRrmB4DZXWDVN701F"
        "AAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAFAAAAAgAAAAIAAAAAAAAAAAAAAB8AAAAAVFJFRQAAAA0ALTEgMQpjAC0xIDAKseMW"
        "sue7xWIppH0PDErHhhw8Eb4="),
    "split-v4": (
        "RElSQwAAAAQAAAAGar8iEhC+njpqvyISEL6eOgAA/gAANOHCAACBpAAAAAAAAAAAAAAAB3S/CYBf3qtVDjUNCVuU3pXrdFbz"
        "AAAAAGq/IhII518dar8iEgjnXx0AAP4AADThxgAAgaQAAAAAAAAAAAAAAAVJPNW6J4b/RMFQetPqeZmTfQ7IXgAAAABqvyIS"
        "CSRoHWq/IhIJJGgdAAD+AAA04cgAAIGkAAAAAAAAAAAAAAAHbO5H98fZ2+S24gqMs+ORXVyuuuEAAAAAar8iEglhcR1qvyIS"
        "CWFxHQAA/gAANOHJAACBpAAAAAAAAAAAAAAABcEIEiN5lHz4ab1F3evsoedlR0BXAAAAAGq/IhIJnnodar8iEgmeeh0AAP4A"
        "ADThygAAgaQAAAAAAAAAAAAAAAVDhvaxIB17ongVbLNdeZPCcQQb2gAAAABqvyISEL6eOmq/IhIQvp46AAD+AAA04csAAIGk"
        "AAAAAAAAAAAAAAACWHvmtMP5P5PEicARG7pVlhR6JssABABlLm1kAGxpbmsAAABED77zdGy7my+EzGRBI/a5i57qsIEAAAAA"
        "AAAAAQAAAAAAAAAAAAAAAAAAAAUAAAACAAAAAgAAAAAAAAAAAAAAHwAAAABUUkVFAAAADQAtMSAxCmMALTEgMAqvsEQtKD6o"
        "GrrMuvVJDGd9FLJe8A=="),
    "skiphash-v2": (
        "RElSQwAAAAIAAAACar8dJiE1YGNqvx0mITVgYwAA/gAANMbAAACBpAAAAAAAAAAAAAAAAniYGSJhOyr7YCUEL/a9h4rBmU6F"
        "AARhLm1kAAAAAAAAar8dJiE1YGNqvx0mITVgYwAA/gAANMbBAACBpAAAAAAAAAAAAAAAAmF4B5gijRevLTT85M+981VWgyRy"
        "AARiLm1kAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="),
    "skiphash-v4": (
        "RElSQwAAAAQAAAACar8iEhFBRTRqvyISEUFFNAAA/gAANOIGAACBpAAAAAAAAAAAAAAAAniYGSJhOyr7YCUEL/a9h4rBmU6F"
        "AAQAYS5tZABqvyISEUFFNGq/IhIRQUU0AAD+AAA04gcAAIGkAAAAAAAAAAAAAAACYXgHmCKNF68tNPzkz73zVVaDJHIABgRj"
        "L2IubWQAAAAAAAAAAAAAAAAAAAAAAAAAAAA="),
}
_REAL_PATHS = {"split-v2": None, "split-v4": None, "skiphash-v2": frozenset({"a.md", "b.md"}),
               "skiphash-v4": frozenset({"a.md", "c/b.md"})}


def _real(kind: str) -> bytes:
    import base64
    return base64.b64decode(_REAL_INDEX_B64[kind])


@pytest.mark.parametrize("kind", sorted(_REAL_INDEX_B64))
def test_r30_real_git_indexes_parse(kind):
    from tests._git_tracked import parse_index
    data = _real(kind)
    if kind.startswith("skiphash"):
        assert data[-20:] == bytes(20), "前提：git 寫的檔尾是全 0"
    else:
        import hashlib
        assert hashlib.sha1(data[:-20]).digest() == data[-20:] and b"link" in data, "前提：真的 split index"
    assert parse_index(data) == _REAL_PATHS[kind]


@pytest.mark.parametrize("kind", ["split-v2", "split-v4"])
def test_r30_split_index_is_unavailable_with_clear_reason(tmp_path, kind):
    """修前：`IndexCorrupt`「第 0 項：路徑不合法 b''」。修後：`IndexUnavailable`，訊息寫明 split index。"""
    from tests._git_tracked import IndexUnavailable, only_tracked, tracked_paths
    tracked_paths.cache_clear()
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "index").write_bytes(_real(kind))
    (tmp_path / "e.md").write_text("x", encoding="utf-8")
    with pytest.raises(IndexUnavailable, match="split index") as ei:
        only_tracked(tmp_path, [tmp_path / "e.md"])
    assert "路徑不合法" not in str(ei.value)
    tracked_paths.cache_clear()


@pytest.mark.parametrize("kind", ["skiphash-v2", "skiphash-v4"])
@pytest.mark.parametrize("config", ["", "[core]\n\tbare = false\n", "[index]\n\tskipHash = false\n"])
def test_r30_zero_trailer_accepted_whatever_the_repo_config_says(tmp_path, kind, config):
    """skipHash 寫在全域設定或 `-c`：repo config 看不到（或寫著 false）—— 修前誤判 `IndexCorrupt`，修後照常讀。"""
    from tests._git_tracked import only_tracked, tracked_paths
    tracked_paths.cache_clear()
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "index").write_bytes(_real(kind))
    if config:
        (tmp_path / ".git" / "config").write_text(config, encoding="utf-8")
    files = [tmp_path / p for p in sorted(_REAL_PATHS[kind])] + [tmp_path / "untracked.md"]
    assert only_tracked(tmp_path, files, min_kept=2) == files[:2]
    tracked_paths.cache_clear()


def _z(data: bytes) -> bytes:
    """把檔尾換成全 0（skipHash 形）。"""
    return data[:-20] + bytes(20)


_LINK = b"link" + (20).to_bytes(4, "big") + bytes(20)


def _split_synth(ver: int) -> bytes:
    """合成 split index：2 個路徑長 0 的被取代項目 ＋ 1 個一般項目 ＋ `link` 擴充。"""
    out = b"DIRC" + ver.to_bytes(4, "big") + (3).to_bytes(4, "big")
    prev = ""
    for p in ("", "", "e.md"):
        out += _entry(p, ver, prev)
        prev = p
    return _seal(out + _LINK)


def _entry(path: str, ver: int, prev: str = "") -> bytes:
    from tests.test_sec_s4_batch_s4 import _entry as e
    return e(path, ver, prev)


def _seal(body: bytes) -> bytes:
    import hashlib
    return body + hashlib.sha1(body).digest()


@pytest.mark.parametrize("ver", [2, 3, 4])
def test_r30_synthetic_split_index_unsupported(ver):
    from tests._git_tracked import parse_index
    assert parse_index(_split_synth(ver)) is None
    assert parse_index(_z(_split_synth(ver))) is None


#: 壞掉的索引 —— 不論檔尾是真的 SHA-1 還是全 0，一律 `IndexCorrupt`（⛔ 不得變成「不支援」、⛔ 不得被接受）。
_R30_CORRUPT = {
    "empty-name-without-link": _index(["", "e.md"], 2),
    "link-too-short": _index(["a.md", "b.md"], 2, ext=b"link" + (4).to_bytes(4, "big") + bytes(4)),
    "link-then-overrun": _index(["a.md", "b.md"], 2, ext=_LINK + b"TREE" + (999).to_bytes(4, "big")),
    "sparse-then-overrun": _index(["a.md", "b.md"], 2, mode_at=1, ext=b"TREE" + (999).to_bytes(4, "big")),
    "sdir-then-bad-sig": _index(["a.md", "b.md"], 2, ext=b"sdir" + (0).to_bytes(4, "big") + b"\x01\x02\x03\x04" + bytes(4)),
    "count-short": _index(["a.md", "b.md", "c.md"], 2, count=2),
    "count-long": _index(["a.md", "b.md"], 2, count=3),
    "count-0": _index(["a.md", "b.md"], 2, count=0),
    "unsorted": _index(["b.md", "a.md"], 2),
    "duplicate": _index(["a.md", "a.md"], 2),
    "truncated": _index(["a.md", "b.md"], 2)[:-30],
    "v2-extended-flag": _index(["a.md", "b.md"], 2, extended_at=1),
}


@pytest.mark.parametrize("trailer", ["sha1", "zero"])
@pytest.mark.parametrize("kind", sorted(_R30_CORRUPT))
def test_r30_corrupt_index_raises_with_either_trailer(kind, trailer):
    from tests._git_tracked import IndexCorrupt, IndexUnavailable, parse_index
    data = _R30_CORRUPT[kind] if trailer == "sha1" else _z(_R30_CORRUPT[kind])
    with pytest.raises(IndexCorrupt) as ei:
        parse_index(data)
    assert not isinstance(ei.value, IndexUnavailable)


@pytest.mark.parametrize("ver", [1, 5, 0xFFFFFFFF])
def test_r30_unknown_version_with_zero_trailer_is_corrupt_not_unsupported(ver):
    """檔尾全 0 時沒有雜湊可驗證 ⇒ 版本欄位不是 2／3／4 一律當壞掉（有雜湊時才算「不支援」→ `None`）。"""
    from tests._git_tracked import IndexCorrupt, parse_index
    assert parse_index(_index(["a.md"], ver)) is None
    with pytest.raises(IndexCorrupt, match="版本"):
        parse_index(_z(_index(["a.md"], ver)))


def test_r30_zero_trailer_corruption_within_structure_is_disclosed_residual_risk():
    """據實揭露（檔頭）：檔尾全 0、且結構仍完全合法的位元翻轉認不出來（與 git 相同）；有雜湊時照樣抓到。"""
    from tests import _git_tracked as G
    good = _index(["a.md", "b.md"], 2)
    flipped = good[:12 + 62] + b"A" + good[12 + 63:]                    # a.md → A.md：長度、排序都還合法
    with pytest.raises(G.IndexCorrupt):
        G.parse_index(flipped)
    assert G.parse_index(_z(flipped)) == frozenset({"A.md", "b.md"})
    assert "殘餘風險" in (G.__doc__ or "")


# ── 突變：每一道修法拿掉 → 上面至少一個測試紅 ──
_R30_MUTANTS = {
    "zero-trailer-accept-removed": ("    no_hash = trailer == bytes(_SHA1_LEN)\n", "    no_hash = False\n"),
    "empty-name-not-deferred": ("            if not path:\n", "            if False:\n"),
    "empty-without-link-accepted": ('''    if empty_at is not None and not unsupported.startswith("split index"):''',
                                    '''    if False:'''),
    "zero-trailer-version-lenient": ("        if no_hash:\n            raise IndexCorrupt(f\"索引版本",
                                     "        if False:\n            raise IndexCorrupt(f\"索引版本"),
    "v4-name-length-unchecked": ("                if (flags & _NAME_MASK) != _NAME_MASK and len(path) != (flags & _NAME_MASK):\n"
                                 "                    raise IndexCorrupt(f\"第 {k} 項：路徑長 {len(path)} 與 flags 記載 {flags & _NAME_MASK} 不符（v4）\")\n",
                                 ""),
    "link-returns-early": ('''            unsupported = "split index（link 擴充；路徑一部分在共用索引 sharedindex.*）"''',
                           '''            return None, "split index"'''),
}


def _r30_suite(g: dict) -> list[str]:
    """在突變模組上重跑本節的關鍵判定；回傳失敗的判定名。"""
    parse, corrupt = g["parse_index"], g["IndexCorrupt"]
    unavailable = g["IndexUnavailable"]
    fails = []
    for kind in _REAL_INDEX_B64:
        try:
            if parse(_real(kind)) != _REAL_PATHS[kind]:
                fails.append(kind)
        except corrupt:
            fails.append(kind)
    for kind, data in _R30_CORRUPT.items():
        for d in (data, _z(data)):
            try:
                parse(d)
                fails.append(kind)
            except unavailable:
                fails.append(kind)
            except corrupt:
                pass
    try:
        parse(_z(_index(["a.md"], 5)))
        fails.append("v5-zero")
    except corrupt:
        pass
    for d in _r30_v4_bad_name_len():
        try:
            parse(d)
            fails.append("v4-name-len")
        except corrupt:
            pass
    return fails


def _r30_v4_bad_name_len() -> list[bytes]:
    """批 S6 QA（R30-v4）：v4 項目的 flags 名長與實際路徑長不符（git 拒讀）—— 有雜湊、檔尾全 0 兩種都要 `IndexCorrupt`。"""
    good = _index(["a.md", "b/c.md", "b/d.md"], 4)
    body = good[:-20]
    at = 12 + 60                                                        # 第 0 項的 flags（ctime..size 40＋oid 20）
    bad = body[:at] + (3).to_bytes(2, "big") + body[at + 2:]
    return [_seal(bad), bad + bytes(20)]


def test_r30_current_module_passes_suite():
    from tests import _git_tracked as G
    assert _r30_suite(vars(G)) == []


@pytest.mark.parametrize("name", sorted(_R30_MUTANTS))
def test_r30_each_mutant_is_killed(name):
    from tests.test_sec_s6_batch_s6 import _gt_mutant
    assert _r30_suite(_gt_mutant(*_R30_MUTANTS[name])), name


# ══════════════════════════════════════════════════════════════════
# SEC-r29 (c)：DER 金鑰行緊接 toml 訊息 —— DER 那一條吃掉 `could`（或 repr 兩次後吃掉 `\\\'` 的反斜線），
# 值是「像金鑰的字＋空白＋秘密」時，原始文字那一道的完整字面已不在輸出裡 ⇒ 秘密外露（main 亦然）
# ══════════════════════════════════════════════════════════════════
def _r29c_cases() -> list[str]:
    from tests.test_sec_s3_batch_s3 import _b64, _pkcs1, _pkcs8, _wrap
    keyline = _wrap(_b64(_pkcs8(5)))[0]
    keylike = _wrap(_b64(_pkcs8(7)))[0]
    out = []
    for msg in ("could not convert string to float: {q}{v}{q} (line 1 column 1 char 0)",
                "invalid literal for int() with base 0: {q}{v}{q} (line 1 column 1 char 0)",
                "could not convert string to float: {q}{v}{q}\nTomlDecodeError",
                "TomlDecodeError: x\ncould not convert string to float: {q}{v}{q}"):
        for v in (f"{keylike} R29CSECRET", f"{_wrap(_b64(_pkcs1(4)))[0]} R29CSECRET", "MIIB R29CSECRET", "R29CSECRET",
                  f"{keylike} R29CSECRET {keylike}"):
            for q in ("'", '"'):
                for sep in ("\n", "\r\n", " "):
                    out.append(keyline + sep + msg.format(q=q, v=v))
    return out


_R29C = _r29c_cases()
_R29C_FORMS = [(n, f(x)) for x in _R29C for n, f in (("raw", str), ("repr", repr), ("rr", lambda t: repr(repr(t))))]


def test_r29c_premise_main_leaks_in_raw_repr_and_double_repr():
    forms = {n for n, t in _R29C_FORMS if "R29CSECRET" in _MAIN.scrub_secrets(t)}
    assert forms == {"raw", "repr", "rr"}, forms


@pytest.mark.parametrize("fn", [scrub_secrets, scrub_prose_secrets], ids=["errors", "prose"])
def test_r29c_der_line_before_toml_message_value_masked(fn):
    leaks = [t for _, t in _R29C_FORMS if "R29CSECRET" in fn(t)]
    assert not leaks, [(t[-120:], fn(t)[-120:]) for t in leaks[:3]]


def test_r29c_never_masks_less():
    for _, t in _R29C_FORMS:
        _never_less(t)


@pytest.mark.parametrize("x", [
    "could not convert string to float: 'abc' (line 1 column 1 char 0)\n說明：abc 是範例",          # 錨點完整 → 照舊
    "ValueError: could not convert string to float: 'abc def'\n下一行 def' (line 1 column 1 char 0)",  # 一般錯誤 → 不動
    "x' (line 1 column 1 char 0)",
])
def test_r29c_unrelated_text_unchanged_vs_main(x):
    assert scrub_secrets(x) == _MAIN.scrub_secrets(x) and scrub_prose_secrets(x) == _MAIN.scrub_prose_secrets(x)


_R29C_OFF = ("        _spans += _toml_remnant_spans(_head, _close, _ctx, out, _budget, _idx)\n"
             "        if not _has_suf:\n", "        if False:\n")


def test_r29c_mutant_without_remnant_pass_leaks():
    m = _mutant(_R29C_OFF)
    assert any("R29CSECRET" in m.scrub_secrets(t) for _, t in _R29C_FORMS)


def test_r29c_mutant_without_mask_anchor_leaks_double_repr():
    """沒有位置字尾、緊接在後的 `\\\\nTomlDecodeError` 也被遮掉 → 只靠「收尾引號＋遮罩」那個錨點。"""
    m = _mutant(("            _spans += _toml_remnant_spans(_head, _close, MASK, out, _budget, _idx)", "            pass"))
    assert any("R29CSECRET" in m.scrub_secrets(t) for n, t in _R29C_FORMS if n == "rr")


def test_r29c_mutant_last_segment_not_required_as_suffix_masks_unrelated_text():
    """反方向：最靠近錨點那一段不要求是值的結尾 → 錨點前的無關文字也被遮（條件是承重的）。"""
    x = ("could not convert string to float: 'R29CSECRET0123456789abcdefghij0123456789' (line 1 column 1 char 0)\n"
         "ab' (line 1 column 1 char 0)")
    m = _mutant(("or not head.endswith(_last):", "or False:"),
                ("            if not head.endswith(_l0) or (_j0 < 0 and _w0 > 0):", "            if _j0 < 0 and _w0 > 0:"))
    assert scrub_secrets(x) == _MAIN.scrub_secrets(x) and "\nab'" in scrub_secrets(x)
    assert "\nab'" not in m.scrub_secrets(x)


_S6_OFF.append(_R29C_OFF)
_S6_EXTRA_CORPUS.extend(_R29C[::3] + [repr(x) for x in _R29C[1::7]] + [repr(repr(x)) for x in _R29C[2::7]])


# ══════════════════════════════════════════════════════════════════
# 批 S6 QA 修正輪（2026-10-02）：F1 效能、F2 秘密在像金鑰的字之前、F3 超長 HTML 引號值、
# G1 HTML 重複表規則讓原始文字那一道找不到字面（比 main 少遮）、G2 剩餘片段那一道的分支各自有測試殺突變
# ══════════════════════════════════════════════════════════════════
import shared.secret_scrub as _SSC  # noqa: E402

_ANCHOR = "' (line 1 column 1 char 0)"


def _f1_repro() -> str:
    """批 S6 QA F1 的重現：64 個不同的長值＋150 個「整窗都是 `***`」的錨點（舊寫法每個錨點逐段跑 ~690 個空段）。"""
    vals = [f"could not convert string to float: '{i:03d}" + "a" * 999 + _ANCHOR for i in range(64)]
    return "\n".join(vals + ["*" * 2061 + _ANCHOR] * 150)


def _cpu_best(f, x, n=2):
    import time
    best = None
    for _ in range(n):
        t = time.process_time()
        f(x)
        d = time.process_time() - t
        best = d if best is None else min(best, d)
    return best


@pytest.mark.parametrize("fn", ["scrub_secrets", "scrub_prose_secrets"])
def test_f1_star_window_repro_within_2x_main(fn):
    """批 S6 QA F1：分支 4.4 秒、main 0.89 秒（修正前）。現在 ≤ 2 倍 main ＋ 0.2 秒（量測雜訊）。"""
    x = _f1_repro()
    new, old = _cpu_best(getattr(_SSC, fn), x), _cpu_best(getattr(_MAIN, fn), x)
    assert new <= 2 * old + 0.2, (new, old)


def test_f1_star_window_repro_output_never_less():
    x = _f1_repro()
    assert _is_masking_of(scrub_secrets(x), _MAIN.scrub_secrets(x))


def test_f1_budget_exhausted_falls_back_to_masking_whole_window(monkeypatch):
    """工作量用完 → 剩下的錨點不比對、整個視窗遮掉：結果仍是「正常結果再多遮」，秘密不外露。"""
    xs = [t for _, t in _R29C_FORMS[:60]] + [_F2_CASES[0]]
    normal = [scrub_secrets(t) for t in xs]
    monkeypatch.setattr(_SSC, "_TOML_REM_BUDGET", 1)
    for t, n in zip(xs, normal):
        o = scrub_secrets(t)
        assert _is_masking_of(o, n) and "R29CSECRET" not in o and "SECA" not in o, (t[-80:], o[-80:])


def _f2_cases() -> list[str]:
    from tests.test_sec_s3_batch_s3 import _b64, _pkcs8, _wrap
    keyline = _wrap(_b64(_pkcs8(5)))[0]
    keylike = _wrap(_b64(_pkcs8(7)))[0]
    out = []
    for q in ("'", '"', "&#x27;"):
        x = keyline + "\n" + f"could not convert string to float: {q}SECA {keylike}{q} (line 1 column 1 char 0)"
        out += [x, repr(x)]
    return out


_F2_CASES = _f2_cases()


def test_f2_premise_main_leaks():
    assert all("SECA" in _MAIN.scrub_secrets(t) for t in _F2_CASES)


@pytest.mark.parametrize("fn", [scrub_secrets, scrub_prose_secrets], ids=["errors", "prose"])
@pytest.mark.parametrize("x", _F2_CASES)
def test_f2_secret_before_keylike_token_masked(x, fn):
    out = fn(x)
    assert "SECA" not in out, out[-90:]
    _never_less(x)


def test_f2_mutant_without_open_part_leaks():
    m = _mutant(("                _j = _open_part_len(head, _sg, budget)\n", "                _j = 0\n"))
    assert all("SECA" in m.scrub_secrets(t) for t in _F2_CASES)


_F3_LONG = [f"could not convert string to float: {q}1.0SECX" + "x" * 5000 + f"{q} (line 1 column 1 char 0)"
            for q in _HTML_Q]
_F3_OPEN = [f"could not convert string to float: {q}1.0SECX tail (line 1 column 1 char 0)" for q in _HTML_Q] + \
           [f"TomlDecodeError\ninvalid literal for int() with base 0: {q}0xSECX" for q in _HTML_Q]


def test_f3_premise_main_leaks():
    assert all("SECX" in _MAIN.scrub_secrets(t) for t in _F3_LONG + _F3_OPEN)


@pytest.mark.parametrize("fn", [scrub_secrets, scrub_prose_secrets], ids=["errors", "prose"])
@pytest.mark.parametrize("x", _F3_LONG + _F3_OPEN)
def test_f3_over_limit_or_unclosed_html_value_masked_to_end_of_line(x, fn):
    out = fn(x)
    assert "SECX" not in out and out.splitlines()[-1].endswith(": ***"), out[-80:]
    _never_less(x)


@pytest.mark.parametrize("x", [
    "could not convert string to float: &#x27;1.0SECX" + "x" * 5000 + "&#x27;",    # 無字尾、無型別名：一般錯誤
    "could not convert string to float: &#x27;abc&#x27; (line 1 column 1 char 0)\n下一行",  # 4096 字內有收尾：照舊
    "could not convert string to float: &quot;abc",
])
def test_f3_other_shapes_unchanged_vs_main(x):
    assert scrub_secrets(x) == _MAIN.scrub_secrets(x) and scrub_prose_secrets(x) == _MAIN.scrub_prose_secrets(x)


def test_f3_mutant_without_rule_leaks():
    m = _mutant(("_TOML_CONV_HTML_LONG_RE.finditer(out)", "()"))
    assert all("SECX" in m.scrub_secrets(t) for t in _F3_LONG)


_G1 = ["TomlDecodeError ?token=abc\\ncould not convert string to float: 'hunter2SECRET already exists?{&quot;",
       "TomlDecodeError ?token=abc\\ncould not convert string to float: 'hunter2SECRET already exists?{&#x27;a&#x27;: 1",
       "?token=abc\\ncould not convert string to float: 'hunter2SECRET already exists?{&#39;x (line 1 column 1 char 0)"]


@pytest.mark.parametrize("fn", [scrub_secrets, scrub_prose_secrets], ids=["errors", "prose"])
@pytest.mark.parametrize("x", _G1)
def test_g1_html_dup_table_rule_never_hides_value_from_original_text_pass(x, fn):
    """批 S6 QA 第一組 G1：舊寫法分支輸出 `'hunter2SECRET already exists?***`、main 輸出 `***`。"""
    main_fn = _MAIN.scrub_secrets if fn is scrub_secrets else _MAIN.scrub_prose_secrets
    assert "hunter2SECRET" not in main_fn(x), "前提：main 遮得到"
    assert "hunter2SECRET" not in fn(x) and _is_masking_of(fn(x), main_fn(x)), fn(x)


def test_g1_mutant_html_rule_back_in_rules_new_masks_less():
    """反證位置是承重的：把 HTML 重複表那一條放回 `_RULES_NEW`（原始文字那一道之前）→ 比 main 少遮。"""
    m = _mutant(_R29B_OFF, ("    (_TOML_CONV_RE, _mask_toml_conv_for),\n)",
                            "    (_TOML_CONV_RE, _mask_toml_conv_for),\n    (_TOML_EXISTS_DICT_HTML_RE, lambda m: m.group(1) + MASK),\n)"))
    assert "hunter2SECRET" in m.scrub_secrets(_G1[0])


# —— G2：剩餘片段那一道（`_toml_remnant_spans`／`_mask_spans`）每個分支都由下面的測試釘住 ——
_SUF = " (line 1 column 1 char 0)"


def _spans(head: str, out: str, ctx: str = _SUF, mod=_SSC):
    return mod._toml_remnant_spans(head, "'", ctx, out, [mod._TOML_REM_BUDGET])


def test_g2_window_edge_first_segment_not_matched():
    """視窗切斷的第一段（只剩 `cc`）即使字面出現在值裡也不比對 ⇒ 不遮視窗外延的那一段文字。"""
    head = "'" + "c" * 20 + "D" * 100
    out = "c" * 50 + MASK * 68 + "D" * 100 + "'" + _SUF
    p = out.index("'" + _SUF)
    assert _spans(head, out) == [(50, p)]
    m = _mutant(("            if _k == 0 and _w0 > 0:                         # 被視窗切斷的第一段：不比對\n"
                 "                _f = 0\n                break\n", ""))
    assert _spans(head, out, mod=m) != [(50, p)]


def test_g2_preceding_mask_merged_into_span():
    """比對不上的段落後面那個遮罩併進來：`xyz: *** SECRET'…` → `xyz: ***'…`（不是 `xyz: ******'…`）。"""
    head, out = "'abc SECRET", "xyz: " + MASK + " SECRET'" + _SUF
    assert _SSC._mask_spans(out, _spans(head, out)) == "xyz: ***'" + _SUF
    m = _mutant(("        _start = _sp - len(MASK) * (_kp - _f) if _f >= 0 else _w0\n",
                 "        _start = _sp - len(MASK) * (_kp - _f - 1) if _f >= 0 else _w0\n"))
    assert m._mask_spans(out, _spans(head, out, mod=m)) != "xyz: ***'" + _SUF


def test_g2_no_alnum_in_matched_text_not_masked():
    """比對上的只有空白／標點 → 不遮（`_hit` 是承重的）。"""
    head, out = "'ab  ", "zz" + MASK + "  '" + _SUF
    assert _spans(head, out) == []
    m = _mutant(("        if not _hit:\n            continue\n", ""))
    assert _spans(head, out, mod=m) != []


def test_g2_mask_spans_union():
    """聯集：重疊、相接、包含的範圍各併成一個遮罩。"""
    s = "abcdefghij"
    assert _SSC._mask_spans(s, [(0, 5), (3, 8)]) == "***ij"
    assert _SSC._mask_spans(s, [(3, 6), (0, 3)]) == "***ghij"
    assert _SSC._mask_spans(s, [(0, 8), (2, 4)]) == "***ij"
    assert _SSC._mask_spans(s, [(1, 2), (5, 5), (7, 9)]) == "a***cdefg***j"
    m1 = _mutant(("        if _cur is not None and _a <= _cur[1]:\n", "        if False:\n"))
    m2 = _mutant(("            _cur = (_cur[0], max(_cur[1], _b))", "            _cur = (_cur[0], _b)"))
    assert m1._mask_spans(s, [(0, 5), (3, 8)]) != "***ij" and m2._mask_spans(s, [(0, 8), (2, 4)]) != "***ij"


def test_g2_open_part_requires_value_start():
    """開頭片段只認「開頭引號＋值的開頭」：比對不上的段落結尾不是值的開頭 → 停手、不往左延伸。"""
    head = "'SECA KEYLIKE"
    out = "note: 'SECX " + MASK + "'" + _SUF                  # `'SECX ` 不是值的開頭 → 不遮 note
    assert _spans(head, out) == []
    out2 = "note: 'SECA " + MASK + "'" + _SUF
    assert _SSC._mask_spans(out2, _spans(head, out2)) == "note: ***'" + _SUF


def test_g2_budget_fallbacks_each_mask_window(monkeypatch):
    """工作量用完的兩個出口（錨點開頭、逐段比對途中）都把整個視窗遮掉；任一出口改成不遮 → 外露。"""
    head = "'SECA " + "K" * 40
    out = "zz: 'SECA " + MASK + "'" + _SUF
    p = out.index("'" + _SUF)
    w0 = max(0, p - (2 * len(head) + _SSC._TOML_REM_PAD))
    assert _SSC._toml_remnant_spans(head, "'", _SUF, out, [-1]) == [(w0, p)]           # 一開始就用完
    assert _SSC._toml_remnant_spans(head, "'", _SUF, out, [p - w0 + 1]) == [(w0, p)]   # 逐段比對途中用完
    m1 = _mutant(("            _spans.append((_w0, _p))                        # 工作量用完：整個視窗遮掉（只會多遮）\n",
                  "            pass\n"))
    m2 = _mutant(("        if _over:\n            _spans.append((_w0, _p))\n", "        if _over:\n            pass\n"))
    assert m1._toml_remnant_spans(head, "'", _SUF, out, [-1]) == []
    assert m2._toml_remnant_spans(head, "'", _SUF, out, [p - w0 + 1]) == []


_S6_EXTRA_CORPUS.extend(_F2_CASES + _F3_LONG + _F3_OPEN + _G1)


def test_g2_segments_must_appear_in_order_left_of_previous():
    """往左每一段都必須出現在右邊那一段**左邊**：`zz` 在值裡只出現在 `SECRET` 右邊 → 停在 `zz`、不遮它。"""
    head, out = "'Q SECRET zz yy", "zz" + MASK + "SECRET" + MASK + " yy'" + _SUF
    assert _SSC._mask_spans(out, _spans(head, out)) == "zz***'" + _SUF
    m = _mutant(("            _lim, _kp, _sp = _at, _k, _end - len(_sg)", "            _lim, _kp, _sp = _lim, _k, _end - len(_sg)"))
    assert m._mask_spans(out, _spans(head, out, mod=m)) != "zz***'" + _SUF


def test_g2_open_part_needs_at_least_two_chars():
    """只剩開頭引號（1 字）不算開頭片段：`xyz: '*** SECRET'…` → `xyz: '***'…`。"""
    head, out = "'abc SECRET", "xyz: '" + MASK + " SECRET'" + _SUF
    assert _SSC._mask_spans(out, _spans(head, out)) == "xyz: '***'" + _SUF
    m = _mutant(("    while 0 <= _i <= len(sg) - 2:", "    while 0 <= _i <= len(sg) - 1:"))
    assert m._mask_spans(out, _spans(head, out, mod=m)) != "xyz: '***'" + _SUF


def test_g2_empty_value_not_treated_as_remnant():
    """值是空的（只有一對引號）→ 沒有東西可遮，開頭引號照原樣。"""
    q = "&#x27;"
    out = q + q + _SUF
    assert _SSC._toml_remnant_spans(q, q, _SUF, out, [_SSC._TOML_REM_BUDGET]) == []
    m = _mutant(("    if not close or len(head) <= len(close):\n        return []\n    if ctx:",
                 "    if not close:\n        return []\n    if ctx:"))
    assert m._toml_remnant_spans(q, q, _SUF, out, [m._TOML_REM_BUDGET]) != []


def _end_case() -> str:
    from tests.test_sec_s3_batch_s3 import _b64, _pkcs8, _wrap
    return ("TomlDecodeError x\n" + _wrap(_b64(_pkcs8(5)))[0] + "\ncould not convert string to float: '"
            + _wrap(_b64(_pkcs8(7)))[0] + " ENDSEC'")


@pytest.mark.parametrize("fn", [scrub_secrets, scrub_prose_secrets], ids=["errors", "prose"])
def test_g2_value_at_end_of_string_anchor(fn):
    """值在字串結尾（沒有位置字尾、後面也沒有字）→ 錨點是輸出結尾的收尾引號。"""
    x = _end_case()
    assert "ENDSEC" in _MAIN.scrub_secrets(x), "前提：main 外露"
    assert "ENDSEC" not in fn(x), fn(x)[-60:]
    _never_less(x)
    m = _mutant(("        _ps = [len(out) - len(close)] if out.endswith(close) else []", "        _ps = []"))
    assert "ENDSEC" in m.scrub_secrets(x)


_S6_EXTRA_CORPUS.append(_end_case())


# ══════════════════════════════════════════════════════════════════
# 批 S6 QA 第二輪（2026-10-02）：沒有英數字的視窗逐字掃（F1 再發）、找不到收尾的 HTML 引號值＋錨點被吃掉
# ══════════════════════════════════════════════════════════════════
def _qa2_repro(length: int, fill: str, n: int = 400_000) -> str:
    vals = "".join(f"could not convert string to float: '{i:03d}" + "a" * length + "'" + "*" * 16 + "\n" for i in range(64))
    unit = fill + "'" + "*" * 16
    return ("TomlDecodeError\n" + vals + unit * (n // len(unit) + 1))[:n]


@pytest.mark.parametrize("fn", ["scrub_secrets", "scrub_prose_secrets"])
@pytest.mark.parametrize("length,fill", [(4000, " ." * 150), (4000, "-" * 300), (4000, "—" * 300), (999, "*" * 300)],
                         ids=["dot", "dash", "emdash", "star999"])
def test_qa2_noalnum_windows_within_2x_main(fn, length, fill):
    """修正前：分支 1.05～1.53 秒、main 0.46～0.82 秒（≈2.3 倍）；且工作量用完、輸出縮成 59k 字（main 144k）。"""
    x = _qa2_repro(length, fill)
    new, old = _cpu_best(getattr(_SSC, fn), x), _cpu_best(getattr(_MAIN, fn), x)
    assert new <= 2 * old + 0.1 and new <= 1.5, (new, old)
    #: 這幾種形態在工作量上限內就比完（不走「整窗遮掉」）：輸出與 main 一樣長。
    assert len(getattr(_SSC, fn)(x)) == len(getattr(_MAIN, fn)(x))


def test_qa2_has_alnum_matches_regex():
    import random
    rnd = random.Random(7)
    alpha = ["*", " ", ".", "-", "—", "a", "9", "_", "'", "\n", "中"]
    for _ in range(300):
        s = "".join(rnd.choice(alpha) * rnd.choice([1, 3, 300]) for _ in range(rnd.randint(1, 30)))
        idx = [None]
        for _ in range(20):
            a = rnd.randint(0, len(s))
            b = rnd.randint(a, len(s))
            assert _SSC._has_alnum(s, a, b, idx) == (_SSC._ALNUM_RE.search(s, a, b) is not None), (s[:40], a, b)


def test_qa2_last_segment_precheck_is_only_a_shortcut():
    """最後一段先判那一步只是捷徑：拿掉它，輸出逐字相同。"""
    import random
    m = _mutant(("        if _j0 < 0 or out[_j0 - 1:_j0] != \"*\" or _j0 == _w0:\n", "        if False:\n"))
    rnd = random.Random(11)
    alpha = ["could not convert string to float: ", "'", "***", "*", " (line 1 column 1 char 0)", "\n", "TomlDecodeError",
             "?token=abc\\n", "SEC", "a", "ab", " "]
    xs = [t for _, t in _R29C_FORMS[::5]] + _F2_CASES + [_end_case()]
    xs += ["".join(rnd.choice(alpha) for _ in range(rnd.randint(3, 20))) for _ in range(3000)]
    diff = [x for x in xs if m.scrub_secrets(x) != scrub_secrets(x)]
    assert not diff, diff[:3]


_QA2_HTML_EATEN = ["TomlDecodeError ?token=abc\\ncould not convert string to float: &#x27;hunter2SECRET already exists?{&quot;",
                   repr("TomlDecodeError ?token=abc\ncould not convert string to float: &#x27;hunter2SECRET x"),
                   "?token=abc\\ninvalid literal for int() with base 0: &quot;hunter2SECRET (line 1 column 1 char 0)"]


@pytest.mark.parametrize("fn", [scrub_secrets, scrub_prose_secrets], ids=["errors", "prose"])
@pytest.mark.parametrize("x", _QA2_HTML_EATEN)
def test_qa2_unclosed_html_value_with_eaten_anchor_masked(x, fn):
    assert "hunter2SECRET" in _MAIN.scrub_secrets(x), "前提：main 外露"
    assert "hunter2SECRET" not in fn(x), fn(x)
    _never_less(x)


_S6_EXTRA_CORPUS.extend(_QA2_HTML_EATEN)


def test_r30_v4_name_length_mismatch_is_corrupt():
    from tests._git_tracked import IndexCorrupt, IndexUnavailable, parse_index
    assert parse_index(_index(["a.md", "b/c.md", "b/d.md"], 4)) == {"a.md", "b/c.md", "b/d.md"}
    for d in _r30_v4_bad_name_len():
        with pytest.raises(IndexCorrupt, match="v4") as ei:
            parse_index(d)
        assert not isinstance(ei.value, IndexUnavailable)
    from tests import _git_tracked as G
    assert "約 470 個路徑" in (G.__doc__ or "")
