"""批 CM3（DL-f1-s51／s53／s54）：註解／docstring 寫下的事實，用行為釘住。

這三列只改註解，但註解寫的是「程式現在怎麼做」—— 若程式改了、註解沒跟著改，
下一次又會是同一種過時敘述。下列測試守的是**行為**，不是 docstring 字串。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def test_dl_f1_s54_twii_proxy_second_value_is_chg60_div_3(monkeypatch):
    """`_try_twii_proxy` 回 `(chg20, chg60 / 3)`，第二值不是 60 日報酬本身。"""
    import src.data.macro as macro_pkg
    from src.data.macro import tw_macro

    closes = pd.Series([100.0] * 40 + [110.0] * 19 + [120.0])  # 60 列
    monkeypatch.setattr(macro_pkg, "fetch_yf_close", lambda *a, **k: closes)
    chg20, second = tw_macro._try_twii_proxy()
    chg60 = round((120.0 / 100.0 - 1) * 100, 2)          # iloc[-60] = 100
    assert chg20 == round((120.0 / closes.iloc[-20] - 1) * 100, 2)
    assert second == round(chg60 / 3, 2)
    assert second != chg60


def test_dl_f1_s54_twii_proxy_short_series_returns_none(monkeypatch):
    import src.data.macro as macro_pkg
    from src.data.macro import tw_macro

    monkeypatch.setattr(macro_pkg, "fetch_yf_close",
                        lambda *a, **k: pd.Series([100.0] * 59))
    assert tw_macro._try_twii_proxy() is None


def test_dl_f1_s51_nodata_reason_never_rendered():
    """nodata 的 reason 只存在物件上：卡面文字一律「無資料」，不帶 reason。"""
    from src.compute.macro.lamp_direction import LampDirection, format_direction_text
    from shared.lamp_direction_thresholds import LAMP_DIRECTION_NODATA_TEXT

    d = LampDirection(direction="nodata", delta=None, unit="", window_text="",
                      as_of=None, reason="某個只該存在物件上的原因")
    assert format_direction_text(d) == LAMP_DIRECTION_NODATA_TEXT
    assert "某個只該存在物件上的原因" not in format_direction_text(d)


def test_dl_f1_s53_rebuilt_parquet_gap_within_sanity_cap():
    """重建後的 m1m2 parquet：|gap| 全在上界內（docstring 記的實測最大 +24.35 < 30）。"""
    from shared.signal_thresholds import M1B_M2_GAP_SANITY_ABS_MAX_PP

    p = Path(__file__).resolve().parents[1] / "data_cache" / "finmind_m1m2.parquet"
    if not p.exists():
        pytest.skip("本機無 data_cache/finmind_m1m2.parquet")
    gap = pd.read_parquet(p)["m1b_m2_gap"].dropna()
    assert len(gap) > 0
    assert (gap.abs() < M1B_M2_GAP_SANITY_ABS_MAX_PP).all()
