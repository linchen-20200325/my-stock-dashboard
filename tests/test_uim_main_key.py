"""tests/test_uim_main_key.py — UI-M：`compute_five_bucket_summary` 加性外露 `main_key`（桶燈號主因燈）。

釘什麼（單一職責）：
  · 每一桶都有 `main_key`；桶全灰／全綠 → None（⛔ 不硬選最差）。
  · 桶為黃／紅 → `main_key` ＝ 該桶 `details` 裡某盞 `danger == 桶等級` 的燈，且 `headline` 開頭就是那盞燈的 label
    （＝它正是 headline／label 已在用的主因燈，不是第二套挑法）。
  · 加性：既有六個鍵仍在、型別不變（其值由 `tests/test_five_bucket_golden.py` 等原有守衛逐位釘住）。
"""
from __future__ import annotations

from src.compute.macro import compute_five_bucket_summary

_BUCKETS = ("long", "mid", "short", "chips", "news")
_OLD_KEYS = {"level", "label", "headline", "color", "emoji", "details"}


def _stressed():
    return dict(macro_info={
        "vix": {"current": 35.0},                 # 紅（> 30）
        "us10y": {"current": 4.8},                # 黃（4.5～5.0）
        "ism_pmi": {"value": 44.0},               # 紅（< 46）
        "us_core_cpi": {"yoy": 2.0},              # 綠
    })


def test_every_bucket_has_main_key_and_old_keys_remain():
    for _out in (compute_five_bucket_summary(), compute_five_bucket_summary(**_stressed())):
        assert set(_out) == set(_BUCKETS)
        for _b in _out.values():
            assert _OLD_KEYS <= set(_b)
            assert "main_key" in _b


def test_all_gray_bucket_has_no_main_key():
    """空輸入 → 五桶全灰 → main_key 全 None（⛔ 不能從全灰的燈裡硬挑一盞）。"""
    for _b in compute_five_bucket_summary().values():
        assert _b["level"] == "gray" and _b["main_key"] is None


def test_non_green_bucket_main_key_is_the_headline_lamp():
    _out = compute_five_bucket_summary(**_stressed())
    _seen_non_green = 0
    for _name, _b in _out.items():
        if _b["level"] in ("yellow", "red"):
            _seen_non_green += 1
            _hit = [d for d in _b["details"] if d["key"] == _b["main_key"]]
            assert len(_hit) == 1, (_name, _b["main_key"])
            assert _hit[0]["danger"] == _b["level"]
            assert _b["headline"].startswith(_hit[0]["label"]), (_name, _b["headline"])
        elif _b["level"] == "green":
            assert _b["main_key"] is None
    assert _seen_non_green >= 2, "測試輸入應至少讓兩桶非綠，否則上面的斷言沒有東西可驗"


def test_main_key_is_the_worst_lamp_not_the_first_lamp():
    """對抗性輸入：中期桶裡**排在最前面**的 `ism_pmi` 是綠燈，真正的黃燈是排在後面的 `us10y`。
    ⇒ `main_key` 必須是 `us10y`（headline 用的那盞），不能只是桶內第一盞。"""
    _out = compute_five_bucket_summary(macro_info={"ism_pmi": {"value": 55.0}, "us10y": {"current": 4.8}})
    _mid = _out["mid"]
    assert _mid["level"] == "yellow"
    assert [d["key"] for d in _mid["details"]][0] == "ism_pmi" and _mid["details"][0]["danger"] == "green"
    assert _mid["main_key"] == "us10y"
    assert _mid["headline"].startswith(next(d["label"] for d in _mid["details"] if d["key"] == "us10y"))
