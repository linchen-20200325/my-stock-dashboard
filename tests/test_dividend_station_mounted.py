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


def test_layer1_conclusion_cards_render(tmp_path):
    """階段 C 第 1 層:三張結論卡 + 兩套刻度表,headless 冒煙。

    守四件事(全都不會讓畫面「看起來」壞掉,所以非測不可):
      1. 三張卡的渲染路徑不炸 —— 涵蓋 ETF 列 / 個股列 / 整檔抓取失敗列。
      2. **巡航 gate 有生效**(防呆 2):這個組合有一列抓取失敗、個股 KD 也沒有等級
         → 絕不可出現「巡航」,必須印「沒東西可以判」。
      3. N/M 用的是嚴格定義(防呆 1),且**分母不是寫死的** —— 8+4+8=20。
      4. 兩套刻度表四列都在,且第 1 列講的是「已修正」而不是舊的「可能相反」。
    """
    from streamlit.testing.v1 import AppTest

    script = tmp_path / "_mount_layer1.py"
    script.write_text(textwrap.dedent("""
        import pandas as pd
        import streamlit as st
        from shared import dividend_station_thresholds as T
        from src.compute.etf import dividend_station as ds
        from src.services import dividend_station_service as svc
        from src.ui.etf.etf_tab_dividend_station import render_dividend_station

        _idx = pd.date_range("2024-01-07", periods=60, freq="W-SUN")
        _wk = pd.Series([100.0] * 60, index=_idx)   # 平盤 → 無紅燈、無加碼金
        _a = ds.assess_holding(
            ticker="0050.TW", name="台灣50", asset_class=T.ASSET_CORE,
            weekly_close=_wk, vix=17.0, premium_pct=0.2, sharpe=1.1,
            total_return_1y_pct=12.0, annual_yield_pct=4.0, inception_years=6.0,
            ann_return_3y_pct=9.0, cum_return_3y_pct=30.0,
            peer_ranks={3: 0.2, 6: 0.2, 12: 0.2})
        _sa = ds.assess_stock(
            ticker="2330", name="台積電", asset_class=T.ASSET_SATELLITE,
            mj_grade="A", mj_score_pct=88, mj_headline="體質佳",
            mj_fail_items=[], kd={"k": 70.0, "d": 65.0, "label": "無"})
        _r_etf = svc.row_from_assessment(_a)
        _r_etf.update({"held": True, "張數": 10.0, "均價": 35.0, "現價": 40.0})
        _r_stk = svc.stock_row_from_assessment(_sa)
        _r_stk.update({"held": True, "張數": 2.0, "均價": 500.0, "現價": 600.0})
        st.session_state["_station_holdings"] = []
        st.session_state["_station_vix"] = 17.3
        st.session_state["_station_rows"] = [
            _r_etf, _r_stk,
            svc._error_row("9999", "壞掉", T.ASSET_CORE, T.KIND_ETF, "HTTPError: 404"),
        ]
        render_dividend_station()
    """), encoding="utf-8")

    at = AppTest.from_file(str(script), default_timeout=90)
    at.run()
    assert not at.exception, f"第 1 層 mount 有 uncaught exception: {at.exception}"

    _md = " ".join(m.value for m in at.markdown)
    assert "這個組合現在該做什麼" in _md, "卡① 沒有渲染"
    assert "訊號可信度" in _md, "卡② 沒有渲染"
    assert "需要處理的檔數" in _md, "卡③ 沒有渲染"

    # 防呆 2:有列給不出判定 → 不准說巡航
    assert "沒東西可以判" in _md, "巡航 gate 沒生效:該說『沒東西可以判』"
    assert "巡航：今天沒有需要動作的部位" not in _md, \
        "有列給不出判定卻印了巡航 —— 防呆 2 破功"

    # 防呆 1:ETF 8 + 個股 4 + 抓取失敗(ETF)8 = 20,分母動態算出、非寫死
    assert "/20 盞給得出判定" in _md, f"N/M 分母不對(應為 20):{_md[:400]}"

    # 未實現損益:張→股有乘 1000（10 張 ×(40-35) + 2 張 ×(600-500) = 250,000 元）
    assert "+250,000" in _md, "未實現損益沒有把張換成股(漏乘 = 1000 倍低估)"

    # 兩套刻度表
    assert "同一個名詞，兩套刻度" in _md, "兩套刻度表沒有渲染"
    assert "已修正" in _md and "只剩一套" in _md, "第 1 列仍是舊文案"
    assert "只揭露不改" in _md, "其餘三列沒有標明只揭露不改"
