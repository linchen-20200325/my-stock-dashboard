"""xview V1：有效判斷檔數 0 時，⑦ AI 摘要與 LINE「🤖 AI 總結」的 prompt 不得含「續抱」引導句。

背景：`build_summary_prompt` 原只在 digest 有 `invalid` 時拿掉
「沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。」—— 每檔抓取全失敗（total=0）時
仍送這句，等於引導 AI 從零資料給安心結論（§1）。LINE 規則式正文早有 `total<=0` 防線（稽核🔴A），
本修比照同一把尺。

範圍刻意只看 total：部分失敗／燈全 ⚪／無現價仍保留引導句（客戶 Z51/Z52 範圍，
`test_batch_z51` / `test_batch_z52` / `test_dividend_station_service` 已釘住，本檔另釘一次）。
"""
from __future__ import annotations

import math

import pytest

from src.services.dividend_station_service import build_summary_prompt

_HOLD = "續抱、定期定額即可"


def _digest(**kw):
    d = {"vix": 18.0, "total": 2, "reds": [], "held_reds": [], "adds": [], "errors": []}
    d.update(kw)
    return d


@pytest.mark.parametrize("total", [0, -1, None, "3", math.nan, True, False])
def test_no_judged_rows_drops_hold_instruction(total):
    p = build_summary_prompt(_digest(total=total, errors=["0056", "00878"]))
    assert _HOLD not in p
    # 其餘事實照列，不加新結論
    assert "抓取失敗未納入：0056、00878" in p


def test_missing_total_key_drops_hold_instruction():
    d = _digest()
    d.pop("total")
    assert _HOLD not in build_summary_prompt(d)


@pytest.mark.parametrize("total", [1, 2, 7, 3.0])
def test_judged_rows_keep_hold_instruction(total):
    assert _HOLD in build_summary_prompt(_digest(total=total))


def test_total_positive_output_byte_identical_except_count():
    """total>0 → prompt 只有『有效判斷檔數』那行隨 total 變；引導句逐字保留。"""
    a = build_summary_prompt(_digest(total=1))
    b = build_summary_prompt(_digest(total=5))
    assert a.replace("有效判斷檔數：1", "有效判斷檔數：5") == b
    assert "沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。\n" in a


def test_total_zero_differs_only_by_the_instruction():
    """total=0 與 total=1 的差異 = 拿掉那一句 + 檔數；不改其他文字。"""
    z = build_summary_prompt(_digest(total=0))
    o = build_summary_prompt(_digest(total=1))
    assert o.replace("沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。", "") \
            .replace("有效判斷檔數：1", "有效判斷檔數：0") == z


def test_partial_failure_still_keeps_instruction():
    """範圍守衛：部分失敗（total>0、errors 非空）不在本修範圍 → 照舊保留。"""
    assert _HOLD in build_summary_prompt(_digest(total=1, errors=["9999"]))


def test_line_ai_summary_shares_the_fix(monkeypatch):
    """LINE 推播 `_maybe_ai_summary` 共用同一支 prompt → 全數失敗時也不送引導句。"""
    import scripts.push_holdings_daily as P
    import src.services.ai_fetcher as AF

    seen: list[str] = []

    def _fake_post(key, prompt, **kw):
        seen.append(prompt)
        return "ok", "fake-model"

    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(AF, "post_gemini", _fake_post)
    out0 = P._maybe_ai_summary(_digest(total=0, errors=["0056"]), None)
    out1 = P._maybe_ai_summary(_digest(total=2), None)
    assert out0 and out1
    assert len(seen) == 2
    assert _HOLD not in seen[0]
    assert _HOLD in seen[1]
