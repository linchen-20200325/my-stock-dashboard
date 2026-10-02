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
