"""💰 存股戰情室 L5：headless mount 冒煙（button-gated,不觸發抓取）。"""
from __future__ import annotations

import re
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

    # 防呆 1:ETF 8 + 個股 **3**(4 盞扣掉不出等級的 KD)+ 抓取失敗(ETF)8 = 19,
    # 分母動態算出、非寫死。2026-08-26 user 裁示 KD 移出分母後由 20 變 19。
    assert "/19 盞給得出判定" in _md, f"N/M 分母不對(應為 19):{_md[:400]}"

    # 同一頁不准出現兩個對不起來的數字(user 2026-08-26 裁示的第 2 件事):
    # 第 1 層卡② 的 N/M 必須等於第 3 層燈格牆逐列相加。
    _card = re.search(r"(\d+)/(\d+) 盞給得出判定", _md)
    _wall = re.findall(r"(\d+)/(\d+) 有判定", _md)
    assert _card and _wall, "第 1 層或第 3 層的數字沒有渲染出來"
    assert (int(_card.group(1)), int(_card.group(2))) == \
        (sum(int(_n) for _n, _ in _wall), sum(int(_m) for _, _m in _wall)), \
        f"同一頁兩層數字對不起來:卡片 {_card.group(0)} vs 燈格牆 {_wall}"
    # 只禁「N/M 在看」這個**數字**;卡片說明裡講「以前叫在看」的那句歷史不禁
    # (逼人刪掉歷史,下一個人就不知道為什麼改)。
    assert not re.search(r"\d+/\d+ 盞?在看", _md), "第 3 層還留著寬鬆的『在看』計數"

    # 未實現損益:張→股有乘 1000（10 張 ×(40-35) + 2 張 ×(600-500) = 250,000 元）
    assert "+250,000" in _md, "未實現損益沒有把張換成股(漏乘 = 1000 倍低估)"

    # 兩套刻度表
    assert "同一個名詞，兩套刻度" in _md, "兩套刻度表沒有渲染"
    assert "已修正" in _md and "只剩一套" in _md, "第 1 列仍是舊文案"
    assert "只揭露不改" in _md, "其餘三列沒有標明只揭露不改"


# ══════════════════════════════════════════════════════════════════════
# 階段 D 接線：週線走勢圖掛進「選列右側面板」
#
# 這一組守的是**只有接線這一步會壞掉、而且畫面看起來都正常**的事:
#   1. **沒選列 → 一張圖都不畫。** 這是整個擺法的成本前提 —— 圖沒有被包進
#      `st.expander` / `st.tabs`(那兩者的 body 每次 app run 都執行),而是靠
#      「沒選就進不到那個分支」控制成本。這條若破功,STATE.md v19.132 產業
#      熱力圖冷抓事故會從這裡再來一次,而且畫面完全正常。
#   2. **換列 → plotly key 跟著換。** 撞 key 時 Streamlit 沿用前一個元件:
#      面板標題寫 A、圖畫的是 B。
#   3. **四種列型各自的降級**(ETF 齊全 / ETF 部分缺 / 個股 / 抓取失敗)——
#      降級判斷整套在 L4,本組驗的是「L5 有沒有把對的 payload 交過去」:
#      交錯了的話個股列會拿到「可以重跑一次」這種**錯的指引**。
#
# 列序（`_station_script` 建出來的,五列都走 L3 `build_station_rows` 真函式）:
#   0 = 0050.TW ETF 60 週(齊全)　1 = 0056.TW ETF 30 週(年線缺)
#   2 = 2330 個股　3 = 9999.TW 抓取失敗(ETF)　4 = 0050.TW 同代號第二列(觀察清單)
# ══════════════════════════════════════════════════════════════════════

#: L4 `station_charts._render_one` 組 key 用的 `key_prefix`（兩張圖各一）。
#: 寫在這裡是為了**只數戰情室的圖**,不把頁面其他區塊的 plotly 圖算進來。
_CHART_PREFIXES = ("station_ma_", "station_z_")


def _station_script(tmp_path):
    """五種列型的戰情室頁面（全離線:`metrics_fn` 注入,不打任何外部網路）。"""
    script = tmp_path / "_mount_charts.py"
    script.write_text(textwrap.dedent("""
        import pandas as pd
        import streamlit as st
        from shared import dividend_station_thresholds as T
        from src.services import dividend_station_service as svc
        from src.ui.etf.etf_tab_dividend_station import render_dividend_station

        def _weekly(n):
            _idx = pd.date_range("2024-01-07", periods=n, freq="W-SUN")
            return pd.Series([100 - i * 0.5 for i in range(n)], index=_idx)

        def _metrics(tk, kind):
            if tk == "9999.TW":                     # 整檔抓取失敗 → _error_row
                raise RuntimeError("HTTPError: 404")
            if kind == T.KIND_STOCK:                # 個股:沒有週K 這回事
                return {"mj_grade": "A", "mj_score_pct": 88, "mj_headline": "體質佳",
                        "mj_fail_items": [], "kd_state": {"k": 70.0, "d": 65.0,
                                                          "label": "無"}}
            return {"weekly_close": _weekly(30 if tk == "0056.TW" else 60)}

        def _h(tk, nm, ac, ak, held=True):
            return {"ticker": tk, "name": nm, "asset_class": ac,
                    "asset_kind": ak, "held": held}

        _holdings = [
            _h("0050.TW", "台灣50", T.ASSET_CORE, T.KIND_ETF),
            _h("0056.TW", "高股息", T.ASSET_CORE, T.KIND_ETF),
            _h("2330", "台積電", T.ASSET_SATELLITE, T.KIND_STOCK),
            _h("9999.TW", "壞掉", T.ASSET_CORE, T.KIND_ETF),
            _h("0050.TW", "台灣50", T.ASSET_CORE, T.KIND_ETF, held=False),
        ]
        st.session_state["_station_holdings"] = []
        st.session_state["_station_vix"] = 17.3
        st.session_state["_station_rows"] = svc.build_station_rows(
            _holdings, vix=17.3, metrics_fn=_metrics)
        render_dividend_station()
    """), encoding="utf-8")
    return str(script)


def _chart_keys(at) -> list[str]:
    """畫面上**戰情室走勢圖**的 plotly key。

    `AppTest` 把 plotly 當 UnknownElement（`el.key` 恆為 None）,key 只在
    proto 的 element id 裡:`"$$ID-<hash>-<key>"`。
    """
    _keys = []
    for _e in at.get("plotly_chart"):
        _parts = str(getattr(_e.proto, "id", "") or "").split("-", 2)
        if len(_parts) == 3 and _parts[2].startswith(_CHART_PREFIXES):
            _keys.append(_parts[2])
    return _keys


def _run(path, rows=None):
    """跑一次頁面;`rows` = 要選中的列序（None = 沒選任何列）。

    `st.dataframe(on_select=...)` 的選取狀態就存在 session_state 的 widget key 底下,
    先塞再 run 等同使用者點了那一列。
    """
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(path, default_timeout=120)
    if rows is not None:
        at.session_state["_station_light_table"] = {
            "selection": {"rows": list(rows), "columns": []}}
    at.run()
    assert not at.exception, f"選 {rows} 時 mount 有 uncaught exception: {at.exception}"
    return at


def _infos(at) -> str:
    return " ".join(a.value for a in at.info)


def test_charts_absent_until_a_row_is_selected(tmp_path):
    """**沒選列 → 0 張圖**（整個擺法的成本前提）。

    附鑑別力對照組:同一份頁面選了第 0 列就畫得出 2 張 —— 沒有這一半的話,
    「0 張」也可能只是圖根本沒接上,而測試照樣綠燈。
    """
    _p = _station_script(tmp_path)

    _idle = _run(_p)
    assert _chart_keys(_idle) == [], "沒選任何列卻畫了圖 —— 成本前提破功"
    _md = " ".join(m.value for m in _idle.markdown)
    assert "點左表任一列" in _md, "沒選列時連引導文字都沒有(那是空面板,不是省成本)"

    _sel = _run(_p, [0])
    assert len(_chart_keys(_sel)) == 2, \
        f"對照組:選了 ETF 列該有 2 張圖,實得 {_chart_keys(_sel)}"


def test_selected_etf_row_renders_both_charts(tmp_path):
    """ETF 資料齊全 → 2 張圖;ETF 部分缺(30 週) → 仍 2 張,但年線那條交代原因。"""
    from shared import station_specs as SS

    _p = _station_script(tmp_path)

    _full = _run(_p, [0])
    assert len(_chart_keys(_full)) == 2
    assert SS.MISS_TEXT[SS.MISS_NOT_APPLICABLE] not in _infos(_full)
    assert SS.MISS_TEXT[SS.MISS_FETCH_FAILED] not in _infos(_full)

    _partial = _run(_p, [1])
    assert len(_chart_keys(_partial)) == 2, \
        "只缺年線就整張砍掉 —— 月線/季線與布林 z 都還有真資料可畫"
    _caps = " ".join(c.value for c in _partial.caption)
    assert "年線畫不出來" in _caps, f"缺的那條線沒有交代原因:{_caps[:300]}"
    assert SS.MISS_TEXT[SS.MISS_NOT_ENOUGH] in _caps, "缺線原因沒有走 L0 MISS_TEXT"


def test_stock_row_renders_no_chart_and_says_it_is_not_applicable(tmp_path):
    """個股列 → **0 張圖 + 印 L0「不適用」**（不是空白、不是空圖）。

    §1:這裡若印成「可以重跑一次」/「等時間累積」就是**錯的指引** ——
    個股從頭到尾沒有週K 這回事,重跑一百次也不會有。
    """
    from shared import station_specs as SS

    at = _run(_station_script(tmp_path), [2])
    assert _chart_keys(at) == [], "個股列不該有週線走勢圖"
    _txt = _infos(at)
    assert SS.MISS_TEXT[SS.MISS_NOT_APPLICABLE] in _txt, f"沒印不適用:{_txt[:300]}"
    for _r in (SS.MISS_NO_INPUT, SS.MISS_NOT_ENOUGH, SS.MISS_FETCH_FAILED):
        assert SS.MISS_TEXT[_r] not in _txt, f"個股列給了錯的指引({_r})"


def test_failed_row_renders_no_chart_and_blames_the_fetch(tmp_path):
    """抓取失敗列 → 0 張圖 + 印「整批抓取失敗」那一條（不是「不適用」）。"""
    from shared import station_specs as SS

    at = _run(_station_script(tmp_path), [3])
    assert _chart_keys(at) == [], "抓取失敗列不該有週線走勢圖"
    _txt = _infos(at)
    assert SS.MISS_TEXT[SS.MISS_FETCH_FAILED] in _txt, f"沒印抓取失敗:{_txt[:300]}"
    assert SS.MISS_TEXT[SS.MISS_NOT_APPLICABLE] not in _txt, \
        "抓取失敗被講成「不適用」—— 使用者會以為不用修"


def test_plotly_key_follows_the_selected_row(tmp_path):
    """**換列 → key 跟著換**（紅線 7:撞 key 會讓面板寫 A、圖是 B）。

    第 0 列與第 4 列是**同一個代號**（Portfolio 一列 + Watchlist 一列）——
    只用代號組 key 的話這兩列會撞。
    """
    _p = _station_script(tmp_path)

    _k0 = _chart_keys(_run(_p, [0]))
    _k1 = _chart_keys(_run(_p, [1]))
    _k4 = _chart_keys(_run(_p, [4]))

    assert len(_k0) == len(_k1) == len(_k4) == 2
    assert set(_k0) & set(_k1) == set(), f"換到別檔 key 沒變:{_k0} vs {_k1}"
    assert set(_k0) & set(_k4) == set(), \
        f"同代號的兩列撞 key —— 換列會沿用上一張圖:{_k0} vs {_k4}"
    # 兩張圖在同一列裡也不可以互撞（同一頁同時有週K 與布林 z）。
    assert len(set(_k0)) == 2, f"同一列的兩張圖撞 key:{_k0}"
