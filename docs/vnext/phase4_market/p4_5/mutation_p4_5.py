"""P4-5 圖 A 自訂圖表守衛 mutation 驗證（開發用；不被 app／tests import）。
逐一對 src/ui/views/_market_blocks.py 做一個字串突變 → 跑守衛 → 預期轉紅 → 還原。用法：python docs/vnext/phase4_market/p4_5/mutation_p4_5.py"""
import subprocess, pathlib, sys
P = pathlib.Path("src/ui/views/_market_blocks.py")
ORIG = P.read_text(encoding="utf-8")
MUT = [
 ("M1 拿掉 legend", '"color": {"field": "series", "type": "nominal", "legend": _legend,', '"color": {"field": "series", "type": "nominal", "legend": None,'),
 ("M2 legend 少一項（domain 少最後一個）", '"scale": {"domain": _names,', '"scale": {"domain": _names[:-1],'),
 ("M3 y 軸整個 hidden（axis=None）", '"y": {"field": "value", "type": "quantitative", "title": "", "axis": {"grid": True}}', '"y": {"field": "value", "type": "quantitative", "title": "", "axis": None}'),
 ("M4 y 軸刻度標籤關閉", '"axis": {"grid": True}}', '"axis": {"grid": True, "labels": False}}'),
 ("M5 資料被 normalize（除以首值）", "return _long[list(TWII_LONG_COLUMNS)]", "_long['value'] = _long['value'] / _long['value'].iloc[0]\n    return _long[list(TWII_LONG_COLUMNS)]"),
 ("M6 MA 線／缺口被 ffill 補值", "return _long[list(TWII_LONG_COLUMNS)]", "_long['value'] = _long['value'].ffill()\n    return _long[list(TWII_LONG_COLUMNS)]"),
 ("M7 圖高改 140（render_chart_a 呼叫）", "render_twii_chart(twii_chart_frame(_view, _refs), height=PRIMARY_CHART_HEIGHT_PX)", "render_twii_chart(twii_chart_frame(_view, _refs), height=140)"),
 ("M8 legend 欄數 5（右緣超出手機圖寬）", "TWII_LEGEND_COLUMNS: int = 3", "TWII_LEGEND_COLUMNS: int = 5"),
 ("M9 拿掉圖例標題的限定語", 'TWII_LEGEND_TITLE: str = "MA 均為最新值，參考的水平線"', 'TWII_LEGEND_TITLE: str = "MA 均線"'),
 ("M10 色彩對映對調（指數／MA5）", '{TWII_COLUMN: "#2563eb", "MA5": "#f59e0b"', '{TWII_COLUMN: "#f59e0b", "MA5": "#2563eb"'),
 ("M11 sparkline 化（加 width 120）", '"height": height,\n        "autosize"', '"height": height, "width": 120,\n        "autosize"'),
 ("M12 圖例標籤帶回限定語（拿掉 labelExpr）", '"labelExpr": f"replace(datum.label, \'{TWII_MA_QUALIFIER}\', \'\')",', ""),
 ("M13 spec 加滾動 window transform", '"mark": {"type": "line", "strokeWidth": 2},', '"mark": {"type": "line", "strokeWidth": 2}, "transform": [{"window": [{"op": "mean", "field": "value", "as": "value"}], "frame": [-4, 0]}],'),
 ("M14 tooltip 拿掉完整系列名", '{"field": "series", "type": "nominal", "title": "系列"},', ""),
 ("M15 退回 st.line_chart（圖例單行被裁）", 'st.vega_lite_chart(twii_chart_long(frame), twii_chart_spec(list(frame.columns), height=height),\n                       width="stretch", height=height)', 'st.line_chart(frame, height=height)'),
]
bad = 0
try:
    for name, a, b in MUT:
        if ORIG.count(a) != 1:
            print(f"!! {name}: 突變錨點出現 {ORIG.count(a)} 次（應為 1）"); bad += 1; continue
        P.write_text(ORIG.replace(a, b), encoding="utf-8")
        r = subprocess.run([sys.executable, "-m", "pytest", "tests/test_p4_2_market_charts.py", "tests/test_p4_4_market_exposed_text.py", "-q", "-x", "-p", "no:cacheprovider"], capture_output=True, text=True)
        fails = [l for l in r.stdout.splitlines() if l.startswith("FAILED")]
        ok = r.returncode != 0
        print(("紅 OK " if ok else "仍綠 ✗ ") + name + (f"  ← {fails[0].split('::',1)[-1][:90]}" if fails else ""))
        bad += (not ok)
finally:
    P.write_text(ORIG, encoding="utf-8")
print("全部轉紅" if not bad else f"{bad} 項未轉紅")
sys.exit(1 if bad else 0)
