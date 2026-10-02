"""批 S6（SEC-r28／SEC-r29 (b)／SEC-r30；2026-10-02）：`scrub_secrets` 補洞與 `tests/_git_tracked.py` 測試補強。

⭐ 硬性要求（同批 S3／S4）：任何輸入都不得比 **e23ff2f 凍結副本**、**bf0ada3 凍結副本**、**main 792c7a2 凍結副本**
（`tests/fixtures/secret_scrub_792c7a2.py`，批 S6 動工前的 main）少遮。判準沿用 `tests/test_sec_s3_0928._is_masking_of`。
"""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib

import pytest

from shared.secret_scrub import scrub_prose_secrets, scrub_secrets
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
        parse_index(_r28_bad_padding(), allow_zero_trailer=True)


def test_r28_mutant_without_padding_check_silently_returns_path():
    g = _gt_mutant(_PAD_CHECK, "")
    assert g["parse_index"](_r28_bad_padding(), allow_zero_trailer=True) == frozenset({"ab"})


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


_R29B_OFF = ("    (_TOML_EXISTS_DICT_HTML_RE, lambda m: m.group(1) + MASK),\n", "")
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
_S6_OFF: list[tuple[str, str]] = [_R29B_OFF]
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
    assert SSC.__doc__ == _MAIN.__doc__


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
    return {}


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
