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
