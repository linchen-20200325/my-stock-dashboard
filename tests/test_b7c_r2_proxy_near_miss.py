"""tests/test_b7c_r2_proxy_near_miss.py — B7c-r2：L0 `is_m1b_m2_proxy` 的「近似標籤」反例。

缺口（HANDOFF B7c-r2，既有缺口，非 #713 造成）：既有測試（`test_d2_macro_sections.py`）
只有「精確標籤 → True」與「完全無關的 source → False」，**沒有**「source 含 proxy 近似字樣
但不是 SSOT 標籤」的反例。L0 docstring 明文「⛔ 不做寬鬆的 substring 嗅探、精確集合比對」——
這裡把那句話變成測試：日後有人把判定改成 `'proxy' in source`、忽略大小寫、strip 空白、
或把旗標改成 truthy 判斷，這些反例會轉紅。

§1 的分寸：這些輸入回 False ＝「不宣稱它是代理值」；缺資料另有呼叫端守門。
"""
from __future__ import annotations

import pytest

from shared.macro_provenance import (
    M1B_PROXY_SOURCE_LABEL,
    M1B_PROXY_SOURCE_LABEL_RAW,
    M1B_PROXY_SOURCE_LABELS,
    M1B_PROXY_VALUE_NOTE,
    is_m1b_m2_proxy,
    m1b_m2_proxy_badge,
)

#: 近似但**不是** SSOT 標籤的 source 字串（子字串、大小寫、空白、前後綴、拆字）。
_NEAR_MISS_SOURCES = (
    "proxy",
    "PROXY",
    "TWII",
    "twii-proxy",
    "TWII-Proxy",
    "TWII-PROXY",
    " TWII-proxy",
    "TWII-proxy ",
    "TWII-proxy\n",
    "TWII-proxy-v2",
    "TWII_proxy",
    "TWII proxy",
    "CBC-tier1 (TWII-proxy fallback)",
    "not TWII-proxy",
    "yahoo:^twii:proxy_tier3",
    "Yahoo:^TWII:proxy_tier2",
    "Yahoo:^TWII:proxy_tier3 ",
    "Yahoo:^TWII",
    "proxy_tier3",
    "CBC-proxy",
    "IMF-proxy",
    "FRED:proxy",
    "TWII-proxy,CBC-tier1",
)


@pytest.mark.parametrize("source", _NEAR_MISS_SOURCES)
def test_near_miss_source_label_is_not_proxy(source):
    assert source not in M1B_PROXY_SOURCE_LABELS, "前提：反例本身不是 SSOT 標籤"
    assert is_m1b_m2_proxy({"source": source}) is False, source
    assert m1b_m2_proxy_badge({"source": source}) == "", source


@pytest.mark.parametrize("source", _NEAR_MISS_SOURCES)
def test_near_miss_source_with_explicit_false_flags_is_not_proxy(source):
    info = {"source": source, "is_proxy": False, "is_proxy_tier": False}
    assert is_m1b_m2_proxy(info) is False, info


#: 旗標必須是 `is True` 才算 —— truthy 但不是 True 的值（字串、數字、容器）不得觸發。
_TRUTHY_NOT_TRUE = ("True", "true", "yes", 1, 1.0, "1", [True], {"x": 1}, object())


@pytest.mark.parametrize("key", ["is_proxy", "is_proxy_tier"])
@pytest.mark.parametrize("val", _TRUTHY_NOT_TRUE, ids=repr)
def test_truthy_but_not_true_flag_is_not_proxy(key, val):
    assert is_m1b_m2_proxy({key: val, "source": "CBC-tier1"}) is False, (key, val)


@pytest.mark.parametrize("source", [
    ("TWII-proxy",), ["TWII-proxy"], b"TWII-proxy", 0, False,
])
def test_non_string_source_is_not_proxy(source):
    """source 不是字串（tuple／list／bytes／0／False）→ 不得被 `str()` 湊成標籤。"""
    assert is_m1b_m2_proxy({"source": source}) is False, source


def test_look_alike_flag_keys_are_ignored():
    """只認 `is_proxy`／`is_proxy_tier` 兩個鍵；近似鍵名不得觸發。"""
    for k in ("proxy", "isProxy", "is_proxy_", "IS_PROXY", "is_proxy_tier3", "tier_used"):
        assert is_m1b_m2_proxy({k: True, "source": "CBC-tier1"}) is False, k


def test_positive_controls_still_true():
    """正對照：同一組測試環境下，真的標籤／真的旗標仍判為代理（反例不是恆 False 造成的）。"""
    assert is_m1b_m2_proxy({"source": M1B_PROXY_SOURCE_LABEL}) is True
    assert is_m1b_m2_proxy({"source": M1B_PROXY_SOURCE_LABEL_RAW}) is True
    assert is_m1b_m2_proxy({"is_proxy": True, "source": "CBC-tier1"}) is True
    assert m1b_m2_proxy_badge({"source": M1B_PROXY_SOURCE_LABEL}) == M1B_PROXY_VALUE_NOTE
