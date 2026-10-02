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


#: 批 S4 QA F3：原始文字那一道的「關掉」突變（測最後一道本身時要一併關掉，否則被這一道補遮、突變看不出差別）。
_TOML_ORIG_OFF = ("    if not any(_n in text for _n in _POST_NEEDLES[_TOML_CONV_RE]):\n        return []",
                  "    if True:\n        return []")
_TOML_HTML_OFF = (r'''    r"|(?P<he>&#x27;|&#39;|&quot;)(?:(?!(?P=he))[^\r\n]){0,4096}" + _POSS + r"(?P=he)"''', "")


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
    m = _mutant_ss((old, new), _TOML_ORIG_OFF)
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
    _TOML_ORIG_OFF, _TOML_HTML_OFF,                                           # 批 S4 QA F3
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
# 批 S4 QA F3：前面的規則吃掉 toml 錨點（`?token=abc\ncould …` 經 repr 後同一行）→ 在原始文字上判一次；HTML 跳脫引號
# ══════════════════════════════════════════════════════════════════
_F3_EATEN = [
    repr("GET https://x.com/v1?token=abc\ncould not convert string to float: '1.2SEC' (line 1 column 1 char 0)"),
    repr("GET https://x.com/v1?key=abc\n\ninvalid literal for int() with base 0: '0x1SEC' (line 1 column 1 char 0)"),
    "x?api_key=abc\\ncould not convert string to float: '9.9SEC'\nTomlDecodeError",
]
_F3_HTML = [f"{_c}{_q}{_v}{_q} (line 1 column 1 char 0)" for _c in ("could not convert string to float: ",
            "invalid literal for int() with base 0: ") for _q in ("&#x27;", "&#39;", "&quot;") for _v in ("1.2SEC",)]


@pytest.mark.parametrize("fn", [scrub_secrets, scrub_prose_secrets], ids=["errors", "prose"])
@pytest.mark.parametrize("x", _F3_EATEN + _F3_HTML)
def test_f3_toml_value_masked_even_when_anchor_eaten_or_html_quoted(x, fn):
    assert "SEC" in _BF0.scrub_secrets(x) or "SEC" in _BF0.scrub_prose_secrets(x), "前提：main 外露"
    assert "SEC" not in fn(x), fn(x)
    _never_less(x)


def test_f3_plain_float_error_still_untouched():
    for x in ("ValueError: could not convert string to float: '1.2SEC'", "could not convert string to float: &#x27;a&#x27;",
              "invalid literal for int() with base 10: &quot;x&quot;"):
        assert scrub_secrets(x) == x == scrub_prose_secrets(x)


def test_f3_mutant_without_html_quotes_leaks():
    m = _mutant_ss(_TOML_HTML_OFF)
    assert all("SEC" in m.scrub_secrets(x) for x in _F3_HTML) and not any("SEC" in scrub_secrets(x) for x in _F3_HTML)


def test_f3_mutant_without_original_text_pass_leaks():
    m = _mutant_ss(("    return _mask_toml_orig(_toml_vals, _run_post(out))\n\n\ndef scrub_prose_secrets",
                    "    return _run_post(out)\n\n\ndef scrub_prose_secrets"))
    assert "1.2SEC" in m.scrub_secrets(_F3_EATEN[0]) and "1.2SEC" not in scrub_secrets(_F3_EATEN[0])


def test_f3_disclosed_boundary_over_cap_still_leaks_when_anchor_eaten():
    """檔頭揭露的邊界：超過 `_TOML_ORIG_MAX` 個不同值時，第 65 個起錨點被吃掉就外露（同 main）。"""
    from shared import secret_scrub as SSC
    head = "".join(f"could not convert string to float: 'v{k}' (line 1 column 1 char 0)\n" for k in range(SSC._TOML_ORIG_MAX))
    x = head + _F3_EATEN[0]
    assert "1.2SEC" in scrub_secrets(x) and "第 65 個起只靠最後一道" in (SSC.__doc__ or "")
    _never_less(x)


@pytest.mark.slow
def test_f3_cpu_400k_within_2x_main_and_1_5s():
    """400k 字：本批全部對抗形態（含 F3）—— 每種 ≤ 1.5 秒（CPU），且 ≤ 2 倍 main（下限 0.05 秒，量測雜訊）。"""
    import json
    import subprocess
    import sys
    cases = [[k, v] for k, v in _s4_forms(400_000).items()]
    r = subprocess.run([sys.executable, "-c", _CPU_SCRIPT], input=json.dumps(cases), capture_output=True,
                       text=True, timeout=1200, cwd=str(_ROOT))
    assert r.returncode == 0, r.stderr[-2000:]
    bad = {k: v for k, v in json.loads(r.stdout).items() if max(v[:2]) > 1.5 or max(v[:2]) > max(2 * v[2], 0.05)}
    assert not bad, bad


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
            "space_nl_runs": (" " * 200 + "\n") * (n // 201), "indent_keys": _r27_indented(n),
            #: 批 S4 QA F3：原始文字那一道（不同值很多、錨點被吃掉、HTML 跳脫引號）。
            "conv_distinct": "".join(f"{_CONV}'v{k}' (line 1 column 1 char 0)\n" for k in range(n // 50)),
            "conv_eaten": "".join(f"?token=a\\n{_CONV}'w{k}' (line 1 column 1 char 0) " for k in range(n // 60)),
            "conv_html_open": _CONV + "&#x27;" + "x" * n, "conv_html_many": (_CONV + "&quot;x&quot; ") * (n // 45)}


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


#: 批 S4 QA（自驗 fuzz 找到）：上限放寬後一塊多接進後面的短行 → 「涵蓋終點那一行含遮罩」不再是最後一行 →
#: 整塊不遮，比 bf0ada3 少遮。修法：bf0ada3 上限 16 那一道照跑、範圍取聯集（`_DERL_INDENT_MAX_BF0`）。
_R27_SHORT_TAIL = "k = \tMC4CAQAw\nabcDEF0123456789+/AIzaSyA1234567890abcdefghijklmnopqrstu{nl}{sp}MIIpassword: x"


@pytest.mark.parametrize("sp", [17, 20, 64, 255, 256])
@pytest.mark.parametrize("nl", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_r27_short_tail_after_wide_gap_not_less_than_bf0(nl, sp):
    raw = _R27_SHORT_TAIL.format(nl=nl, sp=" " * sp)
    assert "MC4CAQAw" not in _BF0.scrub_secrets(raw), "前提：bf0ada3 遮掉這一塊"
    _never_less(raw)
    assert "MC4CAQAw" not in scrub_secrets(raw) and "MC4CAQAw" not in scrub_prose_secrets(raw)


def test_r27_mutant_without_bf0_pass_masks_less():
    from tests.test_sec_s3_0928 import _mutant
    m = _mutant(("_passes.append((_DER_B64_LOOSE_BF0_RE, _DERL_NL_BF0_RE))", "pass"))
    raw = _R27_SHORT_TAIL.format(nl="\r\n", sp=" " * 20)
    assert "MC4CAQAw" in m.scrub_secrets(raw) and "MC4CAQAw" not in scrub_secrets(raw)


_S4_EXTRA_CORPUS.extend(_R27_SHORT_TAIL.format(nl=nl, sp=" " * sp) for nl in ("\n", "\r\n") for sp in (16, 17, 40, 256, 257))


#: 批 S4 QA 第 2 組（F1，2026-10-01）回報的兩個重現：DER 片段之後隔 17～256 個空白接一行 → 修前（只跑上限 256 那一道）
#: 那一行併進塊、整塊不遮，比 main 少遮；16／257 個空白時與 main 相同。
#: ⚠️ main `b6e4409` 的 `shared/secret_scrub.py` 與 `bf0ada3` 逐位元組相同（`git show b6e4409:shared/secret_scrub.py
#: | sha256sum` ＝ `_BF0_SHA256`，2026-10-01 實測）⇒ `_BF0` 凍結副本**就是**現行 main 的行為。
_F1_KEY = "MH\ncCAQEEIBNVy3UGbn+XBg\n/MV/Z81pxZy/d1AvMoBJ\n{sp}" + "x" * 15
_F1_NONKEY = "MIIIjA\nIw0BAQEFAAOCAQ8A\n6fb92427ae41e4649b934ca495991b7852b855\n{sp}5"


@pytest.mark.parametrize("sp", [0, 1, 15, 16, 17, 18, 40, 128, 255, 256, 257, 300])
@pytest.mark.parametrize("form", [_F1_KEY, _F1_NONKEY], ids=["key", "nonkey"])
def test_f1_qa_repro_never_less_than_main(form, sp):
    raw = form.format(sp=" " * sp)
    _never_less(raw)
    if sp == 17 and form is _F1_KEY:
        assert _BF0.scrub_secrets(raw).startswith("***\n"), "前提：main 把整塊遮掉"
        assert scrub_secrets(raw).startswith("***\n") and scrub_prose_secrets(raw).startswith("***\n")


@pytest.mark.parametrize("form", [_F1_KEY, _F1_NONKEY], ids=["key", "nonkey"])
def test_f1_mutant_without_bf0_pass_masks_less_than_main(form):
    """突變：拿掉 bf0ada3（上限 16）那一道 → 兩個重現都比 main 少遮（＝ QA 回報的原始現象）。"""
    from tests.test_sec_s3_0928 import _mutant
    m = _mutant(("_passes.append((_DER_B64_LOOSE_BF0_RE, _DERL_NL_BF0_RE))", "pass"))
    raw = form.format(sp=" " * 17)
    assert not _is_masking_of(m.scrub_secrets(raw), _BF0.scrub_secrets(raw))
    assert _is_masking_of(scrub_secrets(raw), _BF0.scrub_secrets(raw))


#: 批 S4 QA 第 1 組（2026-10-01）的兩種形態：截斷的金鑰（標頭宣告 ~1004 位元組、只留 6 行）後面接縮排 ≥17 的另一塊 →
#: 修前兩塊併成一塊、涵蓋寬度判不過、截斷那把外露（bf0 遮 6 行中的 6 行，修前分支只遮 1 行）；LF／CR／CRLF／repr 的 `\\n`
#: 都會。第二種：repr 跳脫的金鑰、每行行尾空白＋下一行縮排 ≥17。
def _der_b64(n: int, rnd) -> str:
    """開頭是合法 DER 標頭（PKCS#8 外層 SEQUENCE＋版本＋演算法）的 base64；本體 `n` 位元組隨機。"""
    from tests.test_sec_s3_batch_s3 import _seq
    return _b64(_seq(bytes.fromhex("020100300d06092a864886f70d0101010500") + rnd.randbytes(n)))


_F1_SEPS = {"lf": "\n", "cr": "\r", "crlf": "\r\n", "repr": "\\n"}


def _f1_qa1_truncated_then_indented(sep: str, ind: int) -> tuple[str, list[str]]:
    import random
    rnd = random.Random(7)
    a = _wrap(_der_b64(1000, rnd), 64)[:6]
    b = _wrap(_der_b64(400, rnd), 40)
    return sep.join(a) + sep + sep.join(" " * ind + ln for ln in b), a


def _f1_qa1_random(seed: int):
    """QA 第 1 組兩種形態的隨機產生器（固定種子）：截斷的金鑰（2～8 行）＋可選行尾空白＋換行（LF／CR／CRLF／repr `\\n`）
    ＋縮排 ≥17 的另一塊；前面可接欄位名（`private_key:  `、`key=`）。回傳 (換行, 有無行尾空白, 原文)。"""
    import random
    rnd = random.Random(seed)
    sep = rnd.choice(list(_F1_SEPS.values()))
    ind, tr = rnd.choice([17, 18, 20, 32, 64, 200, 256]), rnd.choice([0, 0, 1, 2, 17, 20])
    a = _wrap(_der_b64(rnd.choice([300, 600, 1000, 1200]), rnd), rnd.choice([40, 64, 76]))[:rnd.randint(2, 8)]
    b = _wrap(_der_b64(rnd.choice([100, 400]), rnd), rnd.choice([20, 40, 64]))[:rnd.randint(1, 6)]
    pre = rnd.choice(["", "private_key:  ", "key="])
    return sep, tr > 0, pre + (" " * tr + sep).join(a) + " " * tr + sep + (" " * tr + sep).join(" " * ind + ln for ln in b)


@pytest.mark.parametrize("ind", [16, 17, 20, 64, 256, 257])
@pytest.mark.parametrize("sep", list(_F1_SEPS.values()), ids=list(_F1_SEPS))
def test_f1_qa1_truncated_key_then_indented_block(sep, ind):
    raw, a = _f1_qa1_truncated_then_indented(sep, ind)
    _never_less(raw)
    if ind == 20:
        assert sum(ln in _BF0.scrub_secrets(raw) for ln in a) == 0, "前提：main 遮掉截斷那把的 6 行"
    for fn in (scrub_secrets, scrub_prose_secrets):
        assert sum(ln in fn(raw) for ln in a) <= sum(ln in _BF0.scrub_secrets(raw) for ln in a)


def test_f1_qa1_mutant_without_bf0_pass_masks_less_on_both_shapes():
    """突變（拿掉 bf0 那一道）在 QA 第 1 組兩種形態上都比 main 少遮：CR 的 QA 原例（截斷那把外露 ≥5／6 行），
    以及產生器裡的 repr `\\n`＋行尾空白形態；修後兩者都不少遮。"""
    from tests.test_sec_s3_0928 import _mutant
    m = _mutant(("_passes.append((_DER_B64_LOOSE_BF0_RE, _DERL_NL_BF0_RE))", "pass"))
    raw, a = _f1_qa1_truncated_then_indented("\r", 20)
    assert sum(ln in m.scrub_secrets(raw) for ln in a) >= 5 and sum(ln in scrub_secrets(raw) for ln in a) == 0
    hit = set()
    for seed in range(3000):
        sep, trail, raw = _f1_qa1_random(seed)
        if (sep, trail) in hit or not (sep == "\\n" and trail):
            continue
        if not _is_masking_of(m.scrub_secrets(raw), _BF0.scrub_secrets(raw)):
            hit.add((sep, trail))
            _never_less(raw)
            break
    assert ("\\n", True) in hit, "前提：產生器裡有 repr＋行尾空白的少遮例"


def test_f1_qa1_random_shapes_never_less_sampled():
    for seed in range(300):
        _never_less(_f1_qa1_random(seed)[2])


def _f1_fragments() -> list[str]:
    """DER 片段：QA 的兩個重現 ＋ 真金鑰（PKCS#8／PKCS#1，固定種子）的頭兩行、頭三行（截短）、末兩行、窄換行頭四行。"""
    out = [_F1_KEY.split("\n{sp}")[0], _F1_NONKEY.split("\n{sp}")[0],
           "k = \tMC4CAQAw\nabcDEF0123456789+/AIzaSyA1234567890abcdefghijklmnopqrstu"]
    for kind in (_pkcs8, _pkcs1):
        lines = _wrap(_b64(kind(0)))
        out += ["\n".join(lines[:2]), "\n".join(lines[:3])[:150], "\n".join(lines[-2:]),
                "\n".join(_wrap(_b64(kind(0)), 20)[:4])]
    return out


_F1_TAILS = ("x" * 15, "5", "MIIpassword: x", "說明字", "abc==", "AAAA", "", "/home/u/x.toml", "MIIB" + "A" * 40)


def _f1_property(indents) -> None:
    for frag in _f1_fragments():
        for ind in indents:
            for tail in _F1_TAILS:
                for nl in ("\n", "\r\n"):
                    _never_less(frag + nl + " " * ind + tail)
    #: QA 第 1 組兩種形態（截斷金鑰＋縮排塊 × 4 種換行；repr 金鑰＋行尾空白＋縮排）。
    for ind in indents:
        for sep in _F1_SEPS.values():
            _never_less(_f1_qa1_truncated_then_indented(sep, ind)[0])
    for seed in range(len(indents) * 10):                   # fast 80 組／slow 3010 組
        _never_less(_f1_qa1_random(seed)[2])


def test_f1_property_never_less_than_main_or_e23_sampled_indents():
    """性質（fast）：DER 片段 × 縮排（邊界取樣）× 尾行 × LF／CRLF：兩支函式都不比 e23ff2f、也不比 main 少遮。"""
    _f1_property((0, 15, 16, 17, 18, 64, 256, 257))


@pytest.mark.slow
def test_f1_property_never_less_than_main_or_e23_all_indents_0_to_300():
    """性質（slow）：同上，縮排 0～300 全部（2026-10-01 實測：同形態 19 片段 × 301 × 9 × 2 ＝ 102,942 組 0 例少遮）。"""
    _f1_property(range(301))


# ══════════════════════════════════════════════════════════════════
# SEC-r26：語料只收 git 追蹤中的檔案（讀索引檔、⛔ 不呼叫 git）—— `tests/_git_tracked.py`
# ══════════════════════════════════════════════════════════════════
def _entry(path: str, ver: int, prev: str = "", extended: bool = False, mode: int = 0o100644) -> bytes:
    """合成一個索引項目（欄位值除 mode／flags 外都填 0）。"""
    raw = path.encode()
    head = bytes(24) + mode.to_bytes(4, "big") + bytes(12) + bytes(20)
    flags = min(len(raw), 0x0FFF) | (0x4000 if extended else 0)
    body = head + flags.to_bytes(2, "big") + (b"\0\0" if extended else b"")
    if ver == 4:
        common = 0
        while common < min(len(prev), len(raw)) and prev.encode()[common] == raw[common]:
            common += 1
        strip = len(prev.encode()) - common
        #: git 的 offset varint（多位元組時每多一組先減 1）。
        enc = [strip & 0x7F]
        strip >>= 7
        while strip:
            strip -= 1
            enc.insert(0, 0x80 | (strip & 0x7F))
            strip >>= 7
        return body + bytes(enc) + raw[common:] + b"\0"
    n = len(body) + len(raw)
    return body + raw + b"\0" * (8 - n % 8)


def _index(paths: list[str], ver: int, ext: bytes = b"", extended_at: int = -1, mode_at: int = -1,
           count: int | None = None) -> bytes:
    """合成索引檔；檔尾是真的 SHA-1（批 S4 QA：`parse_index` 會核對）。`count` 可謊報項目數（檔尾照樣算對）。"""
    out = b"DIRC" + ver.to_bytes(4, "big") + (len(paths) if count is None else count).to_bytes(4, "big")
    prev = ""
    for k, p in enumerate(paths):
        out += _entry(p, ver, prev, extended=(k == extended_at), mode=(0o040000 if k == mode_at else 0o100644))
        prev = p
    return _seal(out + ext)


def _seal(body: bytes) -> bytes:
    return body + hashlib.sha1(body).digest()


#: 含 >127 位元組的前綴刪除（v4 多位元組 varint）、>0xFFF 的超長路徑（flags 名長飽和）、非 ASCII。
_PATHS = ["app.py", "docs/a.md", "docs/ab.md", "shared/secret_scrub.py", "tests/x" * 40 + ".py", "中文/檔.md",
          "z/" + "y" * 5000 + ".md", "zz.md"]
#: git 依路徑位元組嚴格遞增排序（批 S4 QA：`parse_index` 會核對排序）。
_PATHS.sort(key=lambda p: p.encode())


@pytest.mark.parametrize("ver", [2, 3, 4])
def test_r26_parse_synthetic_index(ver):
    from tests._git_tracked import parse_index
    assert parse_index(_index(_PATHS, ver)) == frozenset(_PATHS)
    if ver >= 3:
        assert parse_index(_index(_PATHS, ver, extended_at=2)) == frozenset(_PATHS)


@pytest.mark.parametrize("data", [
    _index(_PATHS, 5),                                                                # 版本不支援
    _index(_PATHS, 2, ext=b"link" + (4).to_bytes(4, "big") + bytes(4)),               # split index
    _index(_PATHS, 2, ext=b"sdir" + (4).to_bytes(4, "big") + bytes(4)),               # 看不懂的必要擴充
    _index(_PATHS, 2, mode_at=1),                                                     # sparse index 目錄項目
], ids=["version-5", "split-link", "required-ext", "sparse-dir"])
def test_r26_unsupported_index_returns_none(data):
    from tests._git_tracked import parse_index
    assert parse_index(data) is None


def _flip(data: bytes, at: int) -> bytes:
    return data[:at] + bytes([data[at] ^ 0x01]) + data[at + 1:]


_GOOD2 = _index(_PATHS, 2)
_GOOD4 = _index(_PATHS, 4)


#: 批 S4 QA（SEC-r26 修正）：內容壞掉 ⇒ 一律 `IndexCorrupt`（修前：0 項 → 空集合、項目數改小 → 殘缺集合、
#: 路徑翻一個位元 → 錯的路徑，全都「成功」回傳）。
@pytest.mark.parametrize("data", [
    pytest.param(b"", id="empty-file"),
    pytest.param(_seal(b"XXXX" + bytes(8)), id="bad-signature"),
    pytest.param(_GOOD2[:-40], id="truncated"),
    pytest.param(_GOOD2[:-20] + bytes(20), id="zero-trailer"),
    pytest.param(_flip(_GOOD2, 12 + 62 + 2), id="flipped-path-bit-v2"),
    pytest.param(_flip(_GOOD4, len(_GOOD4) - 30), id="flipped-path-bit-v4"),
    pytest.param(_flip(_GOOD2, len(_GOOD2) - 1), id="flipped-trailer-bit"),
    pytest.param(_index(_PATHS, 2, count=0), id="count-0-sha-ok"),
    pytest.param(_index(_PATHS, 2, count=len(_PATHS) - 1), id="count-short-sha-ok"),
    pytest.param(_index(_PATHS, 4, count=len(_PATHS) - 3), id="count-short-v4-sha-ok"),
    pytest.param(_index(_PATHS, 2, count=len(_PATHS) + 1), id="count-long-sha-ok"),
    pytest.param(_index(_PATHS, 2, count=469), id="count-469-sha-ok"),
    pytest.param(_index(list(reversed(_PATHS)), 2), id="unsorted"),
    pytest.param(_index(["a.md", "a.md"], 2), id="duplicate"),
    pytest.param(_index(_PATHS, 2, extended_at=1), id="v2-extended-flag"),
    pytest.param(_index(_PATHS, 2, ext=b"TREE" + (999).to_bytes(4, "big")), id="ext-overruns"),
])
def test_r26_corrupt_index_raises(data):
    from tests._git_tracked import IndexCorrupt, parse_index
    with pytest.raises(IndexCorrupt):
        parse_index(data)


def test_r26_valid_index_with_optional_extension_and_zero_trailer_flag():
    from tests._git_tracked import parse_index
    assert parse_index(_index(_PATHS, 2, ext=b"TREE" + (3).to_bytes(4, "big") + b"abc")) == frozenset(_PATHS)
    #: `index.skipHash` 開著時 git 寫全 0 檔尾 → 僅在呼叫端說明允許時接受。
    assert parse_index(_GOOD2[:-20] + bytes(20), allow_zero_trailer=True) == frozenset(_PATHS)


def test_r26_valid_empty_index_is_empty_but_only_tracked_refuses_it(tmp_path):
    """合法的空索引：`parse_index` 照實回傳空集合；`only_tracked` 拒絕（語料 ⛔ 不空轉）。"""
    from tests._git_tracked import IndexCorrupt, only_tracked, parse_index, tracked_paths
    assert parse_index(_index([], 2)) == frozenset()
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "index").write_bytes(_index([], 2))
    (tmp_path / "a.md").write_text("x", encoding="utf-8")
    tracked_paths.cache_clear()
    with pytest.raises(IndexCorrupt, match="少於下限"):
        only_tracked(tmp_path, [tmp_path / "a.md"])


def test_r26_below_repo_minimum_or_nothing_kept_raises(tmp_path):
    from tests._git_tracked import REPO_MIN_TRACKED, IndexCorrupt, only_tracked, tracked_paths
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "index").write_bytes(_index(["docs/a.md", "src/x.py"], 2))
    for rel in ("docs/a.md", "src/y.py"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x", encoding="utf-8")
    tracked_paths.cache_clear()
    with pytest.raises(IndexCorrupt, match="少於下限"):
        only_tracked(tmp_path, [tmp_path / "docs/a.md"], min_tracked=REPO_MIN_TRACKED)
    with pytest.raises(IndexCorrupt, match="只留下 0 個"):
        only_tracked(tmp_path, [tmp_path / "src/y.py"], min_kept=1)
    assert only_tracked(tmp_path, [tmp_path / "docs/a.md"], min_kept=1) == [tmp_path / "docs/a.md"]


@pytest.mark.parametrize("which", [".git", "commondir"])
def test_r26_non_utf8_git_pointer_raises_clear_error(tmp_path, which):
    from tests._git_tracked import IndexCorrupt, tracked_paths
    tracked_paths.cache_clear()
    gd = tmp_path / "gd"
    gd.mkdir()
    (gd / "index").write_bytes(_GOOD2)
    if which == ".git":
        (tmp_path / ".git").write_bytes(b"gitdir: /tmp/\xff\xfe\n")
    else:
        (tmp_path / ".git").write_text(f"gitdir: {gd}\n", encoding="utf-8")
        (gd / "commondir").write_bytes(b"\xff..\n")
    with pytest.raises(IndexCorrupt, match="不是 UTF-8"):
        tracked_paths(tmp_path)


def test_r26_only_tracked_filters_untracked_files(tmp_path):
    from tests._git_tracked import only_tracked, tracked_paths
    tracked_paths.cache_clear()
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "index").write_bytes(_index(["docs/a.md", "src/x.py"], 2))
    for rel in ("docs/a.md", "docs/scratch.md", "src/x.py", "src/tmp_untracked.py"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x", encoding="utf-8")
    files = sorted(tmp_path.joinpath("docs").glob("*.md")) + sorted(tmp_path.joinpath("src").glob("*.py"))
    assert [f.name for f in only_tracked(tmp_path, files)] == ["a.md", "x.py"]
    #: worktree：`.git` 是一行 `gitdir:` 的檔案
    wt = tmp_path / "wt"
    (wt / "docs").mkdir(parents=True)
    (wt / "docs" / "a.md").write_text("x", encoding="utf-8")
    (wt / "docs" / "b.md").write_text("x", encoding="utf-8")
    gd = tmp_path / "gd"
    gd.mkdir()
    (gd / "index").write_bytes(_index(["docs/b.md"], 4))
    (wt / ".git").write_text(f"gitdir: {gd}\n", encoding="utf-8")
    assert [f.name for f in only_tracked(wt, sorted((wt / "docs").glob("*.md")))] == ["b.md"]
    #: 沒有 `.git`（例：`git archive` 解開的副本）→ 讀不了 → 大聲失敗（批 S4 QA 第 1 組：⛔ 不退回檔案系統掃描）
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "z.md").write_text("x", encoding="utf-8")
    from tests._git_tracked import IndexUnavailable
    assert tracked_paths(bare) is None
    with pytest.raises(IndexUnavailable):
        only_tracked(bare, [bare / "z.md"])


@pytest.mark.parametrize("kind", ["no-index", "split", "sparse", "version-5", "sha256-repo"])
def test_r26_unsupported_never_falls_back_to_filesystem_scan(tmp_path, kind):
    """批 S4 QA 第 1 組：格式不支援 ⇒ `only_tracked` 大聲失敗（修前：安靜退回檔案系統掃描 ＝ 未追蹤檔回到語料）。"""
    from tests._git_tracked import IndexUnavailable, only_tracked, tracked_paths
    tracked_paths.cache_clear()
    (tmp_path / ".git").mkdir()
    data = {"split": _index(_PATHS, 2, ext=b"link" + (4).to_bytes(4, "big") + bytes(4)),
            "sparse": _index(_PATHS, 2, mode_at=1), "version-5": _index(_PATHS, 5),
            "sha256-repo": _index(_PATHS, 2)}.get(kind)
    if data is not None:
        (tmp_path / ".git" / "index").write_bytes(data)
    if kind == "sha256-repo":
        (tmp_path / ".git" / "config").write_text("[extensions]\n\tobjectFormat = sha256\n", encoding="utf-8")
    (tmp_path / "untracked.md").write_text("x", encoding="utf-8")
    with pytest.raises(IndexUnavailable, match="不退回檔案系統掃描"):
        only_tracked(tmp_path, [tmp_path / "untracked.md"])


def test_r26_this_checkout_reads_its_index():
    """本 repo（CI 與本機皆為 git checkout）：讀得到索引，且含本檔與受測模組。"""
    from tests._git_tracked import tracked_paths
    #: ⛔ 不 skip（批 S4 QA 第 1 組）：讀不到就失敗 —— 語料測試已不再退回檔案系統掃描。
    t = tracked_paths(_ROOT)
    assert t is not None and "shared/secret_scrub.py" in t and len(t) > 500


@pytest.mark.parametrize("mod,fn", [("tests.test_sec_s3_0928", "_ui_corpus"), ("tests.test_sec_s3_0928", "_secret_corpus"),
                                    ("tests.test_sec_s3_batch_s3", "_tracked_md_lines"),
                                    ("tests.test_sec_s2_scrub_gaps", "_corpus")])
def test_r26_every_scrub_corpus_goes_through_only_tracked(mod, fn):
    """結構守衛：每個語料函式都經過 `only_tracked`（拿掉 → 這裡紅）。"""
    import ast
    import importlib
    import inspect
    import textwrap
    f = getattr(importlib.import_module(mod), fn)
    src = textwrap.dedent(inspect.getsource(getattr(f, "__wrapped__", f)))
    calls = {n.func.id for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "only_tracked" in calls, (mod, fn)
    #: 批 S4 QA：每個語料都帶 repo 規模的下限（索引讀錯 → 失敗，⛔ 不空轉）。
    kws = {kw.arg for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
           and n.func.id == "only_tracked" for kw in n.keywords}
    assert {"min_tracked", "min_kept"} <= kws, (mod, fn, kws)


@pytest.mark.parametrize("mod,fn", [("tests.test_sec_s3_0928", "_ui_corpus"), ("tests.test_sec_s3_0928", "_secret_corpus"),
                                    ("tests.test_sec_s3_batch_s3", "_tracked_md_lines"),
                                    ("tests.test_sec_s2_scrub_gaps", "_corpus")])
@pytest.mark.parametrize("reads", [frozenset(), frozenset({"a.md"}), None], ids=["empty", "tiny", "unavailable"])
def test_r26_corpus_fails_instead_of_vacuous_when_index_reads_empty(monkeypatch, mod, fn, reads):
    """索引讀出來是空集合／過小（例：項目數被改小又剛好通過檢查）、或讀不到 → 語料函式失敗，
    ⛔ 不回傳空語料讓測試空轉、⛔ 不退回檔案系統掃描。"""
    import importlib
    from tests import _git_tracked
    monkeypatch.setattr(_git_tracked, "tracked_paths", lambda root: reads)
    f = getattr(importlib.import_module(mod), fn)
    f = getattr(f, "__wrapped__", f)
    with pytest.raises(_git_tracked.IndexCorrupt):
        f()
