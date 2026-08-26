"""💰 存股戰情室 L5：headless mount 冒煙（button-gated,不觸發抓取）。"""
from __future__ import annotations

import textwrap

import pytest

pytestmark = pytest.mark.slow


def test_render_dividend_station_mounts_clean(tmp_path):
    from streamlit.testing.v1 import AppTest

    script = tmp_path / "_mount.py"
    script.write_text(textwrap.dedent("""
        import streamlit as st
        from src.ui.etf.etf_tab_dividend_station import render_dividend_station
        render_dividend_station()
    """), encoding="utf-8")

    at = AppTest.from_file(str(script), default_timeout=60)
    at.run()
    assert not at.exception, f"我的持股戰情室 mount 有 uncaught exception: {at.exception}"
    # 未按執行前顯示提示,不應自動抓取
    heads = [m.value for m in at.markdown]
    assert any("持股戰情室" in h for h in heads)
    labels = [b.label for b in at.button]
    assert "🚀 跑存股戰情室" in labels


def test_light_detail_layer_renders_without_expander(tmp_path):
    """B2 第 3 層:燈格牆 + 選列就地展開,headless 冒煙。

    守三件事(三件都不會讓畫面「看起來」壞掉):
      1. 逐盞燈渲染路徑不炸 —— 涵蓋 ETF 列 / 個股列 / 整檔抓取失敗列三種 row 型態。
      2. **沒有** `st.expander` 裝明細 —— expander 的 body 每次 app run 都會執行,
         N 檔 × 12 盞燈塞進去就是 STATE.md v19.132 產業熱力圖那個坑的另一個入口。
      3. 四態的視覺真的畫出來了(斜紋 = 無資料、虛線 = 未判定)。
    """
    from streamlit.testing.v1 import AppTest

    script = tmp_path / "_mount_lights.py"
    script.write_text(textwrap.dedent("""
        import pandas as pd
        import streamlit as st
        from shared import dividend_station_thresholds as T
        from src.compute.etf import dividend_station as ds
        from src.services import dividend_station_service as svc
        from src.ui.etf.etf_tab_dividend_station import render_dividend_station

        _idx = pd.date_range("2024-01-07", periods=60, freq="W-SUN")
        _wk = pd.Series([100 - i * 0.5 for i in range(60)], index=_idx)
        _a = ds.assess_holding(
            ticker="0056.TW", name="高股息", asset_class=T.ASSET_CORE,
            weekly_close=_wk, vix=45.0, premium_pct=3.0, sharpe=-0.5,
            total_return_1y_pct=-9.0, annual_yield_pct=5.0, inception_years=1.0,
            ann_return_3y_pct=None, cum_return_3y_pct=None, peer_ranks=None)
        _sa = ds.assess_stock(
            ticker="2330", name="台積電", asset_class=T.ASSET_SATELLITE,
            mj_grade="A", mj_score_pct=88, mj_headline="體質佳",
            mj_fail_items=[], kd={"k": 70.0, "d": 65.0, "label": "無"})
        st.session_state["_station_holdings"] = []
        st.session_state["_station_vix"] = 17.3
        st.session_state["_station_rows"] = [
            svc.row_from_assessment(_a),
            svc.stock_row_from_assessment(_sa),
            svc._error_row("9999", "壞掉", T.ASSET_CORE, T.KIND_ETF, "HTTPError: 404"),
        ]
        render_dividend_station()
    """), encoding="utf-8")

    at = AppTest.from_file(str(script), default_timeout=90)
    at.run()
    assert not at.exception, f"逐盞燈明細 mount 有 uncaught exception: {at.exception}"

    _md = " ".join(m.value for m in at.markdown)
    assert "dsl-row" in _md, "燈格牆沒有渲染"
    assert "填色＝判定" in _md, "圖例沒有渲染（沒有圖例就沒人看得懂兩個視覺頻道）"
    assert "dsl-hatch" in _md, "四態的『無資料』斜紋沒有畫出來"
    assert "dsl-dash" in _md, "『未判定』虛線框沒有畫出來"
    # 舊版逐檔明細 expander 已退場;明細改走 st.dataframe(on_select) 選列
    assert not any("逐檔明細" in str(getattr(e, "label", "")) for e in at.expander), \
        "明細不該再放在 expander 裡（body 每次 app run 都會執行）"
