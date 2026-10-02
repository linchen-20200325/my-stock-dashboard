"""D2-f42（批 CN）：v1 總經頁「中國拖累」面板的「5 條 series 全敗」提示必須到得了。

根因：L2 `china_macro_snapshot` 恆回 5 key 的非空 dict（失敗者 value=None），
L5 `_render_china_drag_panel` 只用 `if not _snap` 擋，全敗時照樣畫出
乘子 1.000／折扣後＝主分的 4 張卡（看起來像「中國沒拖累」的有效觀測）。

測試走真的 L2 鏈（`get_china_snapshot` → `china_macro_snapshot` →
`compute_china_subscore`），只把 L1 `fetch_china_macro` 換成回全空表。
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from shared.fred_series import (
    FRED_CHN_CPI, FRED_CHN_M2, FRED_CHN_OECD_CLI, FRED_CHN_PMI, FRED_USDCNY,
)

_KEY = "a" * 32
_ALL_FAIL_MSG = "中國資料不足(5 條 series 全敗)"
#: 批 D4 D2-f42-n1：score 為 None 那一支（全敗＋抓到但值全空）改說「全缺」；空結果那支維持「全敗」。
_ALL_MISSING_MSG = "中國資料不足(5 條 series 全缺)"
_SIDS = (FRED_CHN_OECD_CLI, FRED_CHN_PMI, FRED_CHN_CPI, FRED_CHN_M2, FRED_USDCNY)


def _fake_st():
    fake = MagicMock()
    fake.columns.side_effect = lambda n: [MagicMock() for _ in range(n)]
    return fake


def _ok_df(value: float, n: int = 30) -> pd.DataFrame:
    dates = pd.date_range("2024-01-31", periods=n, freq="ME")
    return pd.DataFrame({"date": dates, "value": [value] * n, "source": "FRED:test"})


@pytest.fixture
def run_panel(monkeypatch):
    from src.ui.tabs.macro import helpers as h

    def _run(china_dict: dict):
        fake = _fake_st()
        monkeypatch.setattr(h, "st", fake)
        # 打真正的查找點（barrel 走 PEP 562 __getattr__ 即時轉發至 tw_macro）；
        # ⛔ 不可在 barrel 上 setattr —— undo 會把真函式寫進 barrel __dict__，
        # 之後其他測試對 tw_macro 的 patch 會被繞過（順序相依洩漏）。
        monkeypatch.setattr("src.data.macro.tw_macro.fetch_china_macro",
                            lambda _k: china_dict)
        h._render_china_drag_panel(_KEY, main_health=60.0)
        captions = [str(c.args[0]) for c in fake.caption.call_args_list]
        return fake, captions
    return _run


def test_l2_snapshot_is_truthy_even_when_all_fail():
    """前提釘住：L2 全敗仍回非空 dict（若日後改成回 {}，本批守衛仍成立）。"""
    from src.compute.macro import china_macro_snapshot, compute_china_subscore
    snap = china_macro_snapshot({sid: pd.DataFrame() for sid in _SIDS})
    assert snap  # 非空 → `if not _snap` 擋不到
    assert compute_china_subscore(snap) is None


@pytest.mark.parametrize("china_dict,msg", [
    ({sid: pd.DataFrame() for sid in _SIDS}, _ALL_MISSING_MSG),  # fetch_china_macro 失敗形狀：5 條空表
    ({}, _ALL_MISSING_MSG),  # 整包空（L2 仍回 5 個 key 皆 None 的非空 dict ⇒ 同走 score None 那支）
])
def test_all_fail_shows_caption_and_no_cards(run_panel, china_dict, msg):
    fake, captions = run_panel(china_dict)
    assert any(msg in c for c in captions), captions
    fake.metric.assert_not_called()       # 不畫乘子 1.000／折扣後＝主分 的假卡
    fake.markdown.assert_not_called()


def test_partial_data_still_renders_cards(run_panel):
    """只有 1 條有值 → 正常畫卡（不誤擋）。"""
    china = {sid: pd.DataFrame() for sid in _SIDS}
    china[FRED_CHN_OECD_CLI] = _ok_df(101.0)
    fake, captions = run_panel(china)
    assert not any(_ALL_FAIL_MSG in c or _ALL_MISSING_MSG in c for c in captions), captions
    assert fake.metric.call_count == 4
