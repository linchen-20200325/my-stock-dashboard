"""批 S4（SEC-r20／SEC-r21／SEC-r22／SEC-r24／SEC-r25 ②／SEC-r26／SEC-r27；2026-10-01）：`scrub_secrets` 補洞與測試補強。

⭐ 硬性要求（同批 S3）：任何輸入都不得比 **e23ff2f 凍結副本**（`tests/fixtures/secret_scrub_e23ff2f.py`）少遮，
也不得比 **main `bf0ada3`**（批 S3r 合併點；凍結副本 `tests/fixtures/secret_scrub_bf0ada3.py`）少遮。
判準沿用 `tests/test_sec_s3_0928._is_masking_of`。
"""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib

import pytest

from shared.secret_scrub import scrub_prose_secrets, scrub_secrets
from tests.test_sec_s3_0928 import _is_masking_of
from tests.test_sec_s3_batch_s3 import _FIXTURE_MARKER, _OLD, _b64, _leak, _pkcs1, _pkcs8, _wrap

_ROOT = pathlib.Path(__file__).resolve().parents[1]

# ══════════════════════════════════════════════════════════════════
# 基準二：main bf0ada3（批 S3r 合併點）的凍結副本
# ══════════════════════════════════════════════════════════════════
_BF0_FIXTURE = _ROOT / "tests" / "fixtures" / "secret_scrub_bf0ada3.py"
#: `git show bf0ada3:shared/secret_scrub.py | sha256sum`（blob 8fb713800e6c2a68377ab313d0d07876a235936e）。
_BF0_SHA256 = "38edd54ca18e355dcae4781b4f9ed111c5b8e176e5d19d7b578c395f00d524a6"


def _load_bf0():
    spec = importlib.util.spec_from_file_location("_secret_scrub_bf0ada3", _BF0_FIXTURE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_BF0 = _load_bf0()


def test_baseline_bf0ada3_is_frozen_byte_for_byte():
    raw = _BF0_FIXTURE.read_bytes()
    marker = _FIXTURE_MARKER.encode("utf-8")
    assert raw.count(marker) == 1
    assert hashlib.sha256(raw.split(marker, 1)[1]).hexdigest() == _BF0_SHA256
    assert _BF0.scrub_secrets is not scrub_secrets


def _never_less(raw: str) -> None:
    """兩支函式都不得比 e23ff2f、也不得比 bf0ada3 少遮（散文版各自對各自的散文版）。"""
    new_e, new_p = scrub_secrets(raw), scrub_prose_secrets(raw)
    assert _is_masking_of(new_e, _OLD(raw)), ("e23", raw[:120], new_e[:120])
    assert _is_masking_of(new_e, _BF0.scrub_secrets(raw)), ("bf0", raw[:120], new_e[:120])
    assert _is_masking_of(new_p, _BF0.scrub_prose_secrets(raw)), ("bf0-prose", raw[:120], new_p[:120])

# ══════════════════════════════════════════════════════════════════
# SEC-r22：欄位名後面直接接多行無標頭金鑰本體（LF／CRLF）—— 批 S3r 已修，本批補回歸測試
# ══════════════════════════════════════════════════════════════════
#: HANDOFF SEC-r22 列出的 9 種欄位名寫法。
_R22_FIELDS = ["private_key: ", "PRIVATE_KEY=", "key=", "secret: ", "password: ", "token=", "api_key: ",
               "client_secret=", '"private_key": "']


@pytest.mark.parametrize("fn", [scrub_secrets, scrub_prose_secrets], ids=["errors", "prose"])
@pytest.mark.parametrize("nl", ["\n", "\r\n"], ids=["lf", "crlf"])
@pytest.mark.parametrize("field", _R22_FIELDS)
def test_r22_field_then_multiline_key_body_leaks_nothing(field, nl, fn):
    """9 種欄位名 × LF／CRLF × 兩支函式 ＝ 36 組；PKCS#8／PKCS#1 各 8 把（固定種子）：金鑰 0 個 20 字片段外露。"""
    leaked_before = 0
    for seed in range(8):
        for kind in (_pkcs8, _pkcs1):
            b = _b64(kind(seed))
            raw = field + nl.join(_wrap(b))
            out = fn(raw)
            assert _leak(out, b) == 0, (field, nl, seed, kind.__name__)
            _never_less(raw)
            leaked_before += _leak(_OLD(raw), b) > 0
    assert leaked_before == 16, "前提：e23ff2f 在這些形態全數外露（SEC-r22 的原始現象）"


# ══════════════════════════════════════════════════════════════════
# SEC-r20／SEC-r21：toml 帶值的訊息不帶型別名、或排在型別名之前 → 值遮掉（`_TOML_EXISTS_DICT_RE`／`_TOML_CONV_RE`）
# ══════════════════════════════════════════════════════════════════
_TOML_KINDS = ("dup_table", "num_float", "num_int")
_UNI = ("UnicodeDecodeError", "UnicodeEncodeError", "UnicodeTranslateError")
_SECRET_HEX = "9f86d081884c7d659a2f"
#: int()／float() 轉換失敗的真實 traceback 形狀（toml 0.10.2 `loads` 串接 `ValueError` → `TomlDecodeError`；
#: 結構逐字照 Python 3.11 `traceback.format_exc()`，路徑與值換成假的）。
_TB_CHAINED = (
    "Traceback (most recent call last):\n"
    '  File "/usr/lib/python3/site-packages/toml/decoder.py", line 912, in load_value\n'
    "    v = float(v)\n"
    "        ^^^^^^^^\n"
    "ValueError: could not convert string to float: '{v}'\n\n"
    "During handling of the above exception, another exception occurred:\n\n"
    "Traceback (most recent call last):\n"
    '  File "app.py", line 9, in <module>\n'
    "    toml.loads(doc)\n"
    "toml.decoder.TomlDecodeError: could not convert string to float: '{v}' (line 1 column 1 char 0)")
_TB_CHAINED_INT = _TB_CHAINED.replace("float(v)", "int(v, 0)").replace(
    "could not convert string to float", "invalid literal for int() with base 0")


def _toml_leaks(out: str) -> list[str]:
    from tests.test_sec_r12_r11_prose_scrub import _TOML_LEAKS
    return [x for x in _TOML_LEAKS if x in out]


def _toml_msg(kind: str) -> str:
    from tests.test_sec_r12_r11_prose_scrub import _TOML_ALL, _toml_message
    return _toml_message(*_TOML_ALL[kind])


@pytest.mark.parametrize("kind", _TOML_KINDS)
@pytest.mark.parametrize("uni", _UNI)
def test_r20_unicode_colon_form_then_toml_message_without_type_name(uni, kind):
    """SEC-r20：散文版先出現 `Unicode*Error` 散文形（保留），後面接不帶型別名的 toml 訊息 → 值不再外露（3 × 3 ＝ 9 種）。"""
    x = f"為什麼出現 {uni}: 'utf-8' codec can't decode byte 0xff；後來又看到 {_toml_msg(kind)}，怎麼解？"
    assert _toml_leaks(_BF0.scrub_prose_secrets(x)), "前提：bf0ada3 散文版外露"
    out = scrub_prose_secrets(x)
    assert not _toml_leaks(out), out
    assert out.startswith(f"為什麼出現 {uni}: 'utf-8' codec can't decode byte 0xff；"), "SEC-r12：散文形照舊保留"
    _never_less(x)


@pytest.mark.parametrize("fn", [scrub_secrets, scrub_prose_secrets], ids=["errors", "prose"])
@pytest.mark.parametrize("kind", _TOML_KINDS)
@pytest.mark.parametrize("wrap", ["{}", "這是什麼意思：{}", "{}\n請問怎麼修？", "ValueError('{}')"])
def test_r21i_bare_toml_message_masked(wrap, kind, fn):
    """SEC-r21 (i)：只貼 toml 訊息本身（不帶型別名）→ 值遮掉；位置字尾保留。"""
    x = wrap.format(_toml_msg(kind))
    assert _toml_leaks(_BF0.scrub_secrets(x)), "前提：bf0ada3 外露"
    out = fn(x)
    assert not _toml_leaks(out), out
    if kind != "dup_table":
        assert "(line 1 column 1 char 0)" in out
    _never_less(x)


@pytest.mark.parametrize("fn", [scrub_secrets, scrub_prose_secrets], ids=["errors", "prose"])
@pytest.mark.parametrize("tb", [_TB_CHAINED, _TB_CHAINED_INT], ids=["float", "int"])
def test_r21ii_chained_value_error_before_toml_type_name_masked(tb, fn):
    """SEC-r21 (ii)：traceback 裡串接的 `ValueError: could not convert …: '<值>'` 排在 `TomlDecodeError` 之前 → 也遮。"""
    x = tb.format(v=_SECRET_HEX)
    assert _SECRET_HEX in _BF0.scrub_secrets(x), "前提：bf0ada3 外露"
    out = fn(x)
    assert _SECRET_HEX not in out, out
    assert "ValueError: could not convert string to float: ***" in out or "base 0: ***" in out
    _never_less(x)


@pytest.mark.parametrize("x", [
    "ValueError('invalid literal for int() with base 10: 'x'')",        # `_PLAIN` 原樣
    "could not convert string to float: 'N/A'",                         # 一般 float() 錯誤（沒有 toml 位置字尾）
    "ValueError: invalid literal for int() with base 10: '12a'",
    "解析失敗：could not convert string to float: '' ，已略過這一列",
    "the table already exists? {not toml}",                              # 中間有空白 → 不是 toml 的形狀
    "already exists?",
])
def test_r21_general_conversion_errors_unchanged(x):
    """一般 `float()`／`int()` 錯誤（沒有 toml 位置字尾、同段也沒有 `TomlDecodeError`）→ 一字不動（同 bf0ada3）。"""
    assert scrub_secrets(x) == _BF0.scrub_secrets(x) == x
    assert scrub_prose_secrets(x) == x


def test_r21_unclosed_or_overlong_value_masked_to_end_of_line():
    """值超過 4096 字上限（位置字尾被一起吃進去）或找不到收尾 → 遮到行尾；下一行不動。"""
    long_v = "a1" * 3000
    for x in (f"could not convert string to float: '{long_v}' (line 1 column 1 char 0)\n下一行",
              "TomlDecodeError 之前：could not convert string to float: 'unclosed" + _SECRET_HEX + " 尾巴\n下一行"):
        out = scrub_secrets(x)
        assert "a1a1" not in out and _SECRET_HEX not in out and out.endswith("\n下一行"), out[-80:]
        _never_less(x)


def _mutant_ss(*pairs):
    from tests.test_sec_s3_0928 import _mutant
    return _mutant(*pairs)


@pytest.mark.parametrize("old,new,sample", [
    ("    (_TOML_EXISTS_DICT_RE, lambda m: m.group(1) + MASK),\n", "", "dup_table"),
    ("    (_TOML_CONV_RE, _mask_toml_conv_for),\n", "", "num_float"),
    ("    _named = _TOML_TYPE_NAME in text\n", "    _named = False\n", "chained"),                          # 只認位置字尾 → (ii) 外露
    ('_TOML_POS_RE.search(m.group(0), len(m.group("pre"))) is None:',
     "True:", "num_int"),                                                 # 只認型別名 → (i) 外露
])
def test_r20_r21_mutants_leak(old, new, sample):
    m = _mutant_ss((old, new))
    x = _TB_CHAINED.format(v=_SECRET_HEX) if sample == "chained" else f"看到 {_toml_msg(sample)}"
    assert not _toml_leaks(scrub_secrets(x)) and _SECRET_HEX not in scrub_secrets(x)
    assert _toml_leaks(m.scrub_secrets(x)) or _SECRET_HEX in m.scrub_secrets(x), (old, new)


def test_r21_mutant_unconditional_conversion_changes_plain_messages():
    """反方向：拿掉條件（一律遮）→ `_PLAIN` 的一般訊息被改 —— 條件是承重的。"""
    m = _mutant_ss(("    _named = _TOML_TYPE_NAME in text\n", "    _named = True\n"))
    x = "ValueError('invalid literal for int() with base 10: 'x'')"
    assert scrub_secrets(x) == x and m.scrub_secrets(x) != x


def test_r21_disclosed_boundary_bare_conversion_without_suffix_still_leaks():
    """檔頭揭露的邊界：數字轉換訊息沒有位置字尾、同段也沒有 `TomlDecodeError` → 值照原樣。"""
    from shared import secret_scrub as SSC
    x = f"could not convert string to float: '{_SECRET_HEX}'"
    assert scrub_secrets(x) == x and "批 S4 之後仍然外露" in (SSC.__doc__ or "")


# ══════════════════════════════════════════════════════════════════
# ⭐ 結構保證：關掉本批新增的部分 → 輸出與 bf0ada3 逐字相同（⇒ 本批只能在 bf0ada3 之上多遮）
# ══════════════════════════════════════════════════════════════════
#: 本批每一項的「關掉」突變；後面各項（SEC-r27 …）完成時一併登記在這裡。
_S4_OFF: list[tuple[str, str]] = [
    ("    (_TOML_EXISTS_DICT_RE, lambda m: m.group(1) + MASK),\n", ""),
    ("    (_TOML_CONV_RE, _mask_toml_conv_for),\n", ""),
    ("_DERL_INDENT_MAX: int = 256", "_DERL_INDENT_MAX: int = 16"),           # SEC-r27
]


def _s4_corpus(step: int = 3, r4: int = 2000) -> list[str]:
    import random

    from tests.test_sec_s3_batch_s3 import _batch_corpus, _r4_cases
    from tests.test_sec_s3_0928 import _ui_corpus
    out = sorted(_batch_corpus() | _ui_corpus())[::step] + _r4_cases(r4)
    for kind in _TOML_KINDS:
        out += [w.format(_toml_msg(kind)) for w in ("{}", "這是什麼意思：{}", "ValueError('{}')")]
    out += [_TB_CHAINED.format(v=_SECRET_HEX), _TB_CHAINED_INT.format(v="0xZZ")]
    rnd = random.Random(20261001)
    alpha = ["could not convert string to float: ", "invalid literal for int() with base 0: ", "'", '"', "\\'",
             " (line 1 column 1 char 0)", "TomlDecodeError", "already exists?{", "'k': 1}", "\n", " ", "x", "\\"]
    out += ["".join(rnd.choice(alpha) for _ in range(rnd.randint(1, 12))) for _ in range(3000)]
    out += _S4_EXTRA_CORPUS
    return out


#: 後面各項（SEC-r27 …）的樣本也登記在這裡，讓結構保證與「不少遮」一併涵蓋。
_S4_EXTRA_CORPUS: list[str] = []


def _off_diff(corpus: list[str]) -> list[str]:
    from tests.test_sec_s3_0928 import _mutant
    m = _mutant(*_S4_OFF)
    return [r for r in corpus if m.scrub_secrets(r) != _BF0.scrub_secrets(r)
            or m.scrub_prose_secrets(r) != _BF0.scrub_prose_secrets(r)]


def _worse(corpus: list[str]) -> list[str]:
    out = []
    for r in corpus:
        try:
            _never_less(r)
        except AssertionError:
            out.append(r)
    return out


def test_s4_off_is_exactly_bf0ada3_sample():
    """fast：抽樣語料。完整語料見 slow 版。"""
    diff = _off_diff(_s4_corpus(step=25, r4=300))
    assert not diff, [d[:80] for d in diff[:5]]


def test_s4_never_masks_less_sample():
    worse = _worse(_s4_corpus(step=25, r4=300))
    assert not worse, [w[:80] for w in worse[:5]]


@pytest.mark.slow
def test_s4_off_is_exactly_bf0ada3_full():
    diff = _off_diff(_s4_corpus())
    assert not diff, [d[:80] for d in diff[:5]]


@pytest.mark.slow
def test_s4_never_masks_less_than_bf0ada3_or_e23ff2f_full():
    worse = _worse(_s4_corpus())
    assert not worse, [w[:80] for w in worse[:5]]


@pytest.mark.slow
def test_s4_ui_string_constants_unchanged_vs_bf0ada3():
    """（slow：單測超過 5 秒；fast lane 另有 `test_sec_s3_batch_s3::test_real_ui_string_constants_unchanged_vs_e23ff2f`。）"""
    from tests.test_sec_s3_0928 import _ui_corpus
    changed = sorted(r for r in _ui_corpus() if scrub_secrets(r) != _BF0.scrub_secrets(r))
    assert not changed, [c[:120] for c in changed[:5]]


# ══════════════════════════════════════════════════════════════════
# ReDoS／CPU（子程序、CPU 時間取三次最小值）與記憶體峰值（slow）—— 本批新增的形態
# ══════════════════════════════════════════════════════════════════
_CONV = "could not convert string to float: "
_INTL = "invalid literal for int() with base 0: "


def _s4_forms(n: int) -> dict[str, str]:
    """本批新規則的對抗輸入（後面各項的形態也登記在這裡）。"""
    f = {
        "conv_many": (_CONV + "'x' ") * (n // 40), "conv_many_named": (_CONV + "'x' ") * (n // 40) + "TomlDecodeError",
        "conv_open": _CONV + "'" + "x" * n, "conv_esc_open": _INTL + "\\\\'" + "x" * n, "conv_bs": _CONV + "\\" * n,
        "conv_open_suffix": _CONV + "'" + "a" * n + " (line 1 column 1 char 0)",
        "conv_escaped_many": (_INTL + "\\'x\\' ") * (n // 45),
        "conv_lines": (_CONV + "'v' (line 1 column 1 char 0)\n") * (n // 60),
        "dup_many": "already exists?{'" * (n // 17), "dup_open": "already exists?{'" + "x" * n,
    }
    f.update(_S4_EXTRA_FORMS(n))
    return {k: v[:n] for k, v in f.items()}


def _S4_EXTRA_FORMS(n: int) -> dict[str, str]:  # noqa: N802 —— 後面各項擴充
    #: SEC-r27：長空白串夾在換行之間、縮排後接非 base64、多層 `> ` 引用。
    return {"indent_runs": ("MA" + "A" * 62 + "\n" + " " * 300) * (n // 365),
            "indent_then_text": ("MA" + "A" * 62 + "\n" + " " * 255 + "~") * (n // 320),
            "trail_spaces": ("MA" + "A" * 62 + " " * 255 + "\n") * (n // 320),
            "space_nl_runs": (" " * 200 + "\n") * (n // 201), "indent_keys": _r27_indented(n)}


def _r27_indented(n: int) -> str:
    b = _b64(_pkcs8(5))
    return (("\n" + " " * 200).join(_wrap(b)) + "\n") * (n // (len(b) * 5) + 1)


_CPU_SCRIPT = (
    "import json, sys, time, importlib.util\nimport shared.secret_scrub as S\n"
    "spec = importlib.util.spec_from_file_location('bf0', 'tests/fixtures/secret_scrub_bf0ada3.py')\n"
    "B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)\nout = {}\n"
    "def cpu(f):\n"
    "    best = None\n"
    "    for _ in range(3):\n"
    "        t = time.process_time(); f(); d = time.process_time() - t\n"
    "        best = d if best is None else min(best, d)\n"
    "    return best\n"
    "for name, text in json.load(sys.stdin):\n"
    "    out[name] = [cpu(lambda: S.scrub_secrets(text)), cpu(lambda: S.scrub_prose_secrets(text)),\n"
    "                 cpu(lambda: B.scrub_secrets(text))]\n"
    "print(json.dumps(out))\n")


def test_s4_new_rules_are_linear():
    """50k 字：每種形態 ≤ 2 秒（CPU），且不比 bf0ada3 慢 3 倍以上（下限 0.3 秒，避免量測雜訊）。"""
    import json
    import subprocess
    import sys
    cases = [[k, v] for k, v in _s4_forms(50_000).items()]
    r = subprocess.run([sys.executable, "-c", _CPU_SCRIPT], input=json.dumps(cases), capture_output=True,
                       text=True, timeout=600, cwd=str(_ROOT))
    assert r.returncode == 0, r.stderr[-2000:]
    bad = {k: v for k, v in json.loads(r.stdout).items() if max(v[:2]) > 2.0 or max(v[:2]) > max(3 * v[2], 0.3)}
    assert not bad, bad


def _peak_mb(fn, text: str) -> float:
    from tests.test_sec_s3_batch_s3 import _peak_mb as _p
    return _p(fn, text)


@pytest.mark.slow
def test_s4_new_rules_add_little_memory():
    """40 萬字、本批每種形態：比 bf0ada3 多出的峰值（tracemalloc）≤ 5 MB（同批 S3 的測試上限）。"""
    worse = {}
    for name, t in _s4_forms(400_000).items():
        old = _peak_mb(_BF0.scrub_secrets, t)
        new = max(_peak_mb(scrub_secrets, t), _peak_mb(scrub_prose_secrets, t))
        if new - old > 5:
            worse[name] = (old, new)
    assert not worse, worse


# ══════════════════════════════════════════════════════════════════
# SEC-r27：無標頭金鑰的行首縮排超過 16 個空白 → 上限調到 256（`_DERL_INDENT_MAX`）
# ══════════════════════════════════════════════════════════════════
def _indent(b: str, ind: str, tail: str = "", sep: str = "\n") -> str:
    return ind + (tail + sep + ind).join(_wrap(b))


@pytest.mark.parametrize("ind", [17, 20, 32, 64, 128, 256])
@pytest.mark.parametrize("kind", [_pkcs8, _pkcs1], ids=["pkcs8", "pkcs1"])
@pytest.mark.parametrize("sep", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_r27_deep_indent_masked(sep, kind, ind):
    leaked_before = 0
    for seed in range(4):
        b = _b64(kind(seed))
        for raw in (_indent(b, " " * ind, sep=sep), _indent(b, "\t" * (ind // 4), sep=sep),
                    "private_key: " + _indent(b, " " * ind, sep=sep).lstrip(" ")):
            out = scrub_secrets(raw)
            assert _leak(out, b) == 0, (ind, seed, out[:200])
            assert _leak(scrub_prose_secrets(raw), b) == 0
            _never_less(raw)
            leaked_before += _leak(_BF0.scrub_secrets(raw), b) > 0
    assert leaked_before >= 8, "前提：bf0ada3 在縮排 >16 時外露"


@pytest.mark.parametrize("trail", [17, 100, 256])
def test_r27_trailing_spaces_over_16_masked(trail):
    """同一個上限也用在行尾空白（批 S3 只收 ≤16）。"""
    b = _b64(_pkcs8(2))
    raw = _indent(b, "", tail=" " * trail)
    assert _leak(scrub_secrets(raw), b) == 0
    _never_less(raw)


def test_r27_boundary_257_still_leaks_and_disclosed():
    from shared import secret_scrub as SSC
    b = _b64(_pkcs8(3))
    assert _leak(scrub_secrets(_indent(b, " " * 257)), b) > 0
    assert "超過 256 個空白" in (SSC.__doc__ or "") and SSC._DERL_INDENT_MAX == 256


def test_r27_mutant_cap_16_leaks():
    from tests.test_sec_s3_0928 import _mutant
    m = _mutant(("_DERL_INDENT_MAX: int = 256", "_DERL_INDENT_MAX: int = 16"))
    b = _b64(_pkcs8(1))
    raw = _indent(b, " " * 20)
    assert _leak(scrub_secrets(raw), b) == 0 and _leak(m.scrub_secrets(raw), b) > 0


@pytest.mark.parametrize("raw", [
    "MA20 與 MA60\n" + " " * 40 + "均線糾結",                                # 縮排後接一般文字
    "說明：\n" + " " * 30 + "A" * 50 + "\n" + " " * 30 + "B" * 50,           # 縮排的長字（不是 DER）
    "    code:\n" + " " * 24 + "MIIsomething_not_base64 here",
])
def test_r27_indented_ordinary_text_unchanged(raw):
    assert scrub_secrets(raw) == _BF0.scrub_secrets(raw)


_S4_EXTRA_CORPUS.extend(
    _indent(_b64(_pkcs8(s)), " " * ind) + tail
    for s in range(2) for ind in (17, 40, 256, 257) for tail in ("", "\n" + " " * ind + "說明字", "\n/home/u/x.toml"))
