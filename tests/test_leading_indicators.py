"""
Tests for leading_indicators.py — pure utility functions + bug regression tests.
No HTTP calls; all network-dependent functions are excluded.
"""
import sys
import types
import unittest
from datetime import date

# ── Streamlit stub ────────────────────────────────────────────────────────────
_st = types.ModuleType("streamlit")
_st.cache_data = lambda **kw: (lambda f: f)
_st.secrets = {}
sys.modules.setdefault("streamlit", _st)

import pandas as pd
from bs4 import BeautifulSoup

from src.data.macro import (
    roc_to_ymd, ymd_to_slash, ymd_to_dash, ymd_display,
    to_num, first_num, months_in_range, extract_date,
    find_data_table, expand_table_elem,
    render_leading_table,
)


# ─────────────────────────────────────────────────────────────────────────────
# roc_to_ymd
# ─────────────────────────────────────────────────────────────────────────────
class TestRocToYmd(unittest.TestCase):
    def test_8digit_passthrough(self):
        self.assertEqual(roc_to_ymd("20240401"), "20240401")

    def test_7digit_roc(self):
        # 1150401 = 民國115年4月1日 = 2026-04-01
        self.assertEqual(roc_to_ymd("1150401"), "20260401")

    def test_slash_3digit(self):
        self.assertEqual(roc_to_ymd("113/04/01"), "20240401")

    def test_slash_2digit(self):
        self.assertEqual(roc_to_ymd("99/01/05"), "20100105")

    def test_unmatched_returns_empty(self):
        self.assertEqual(roc_to_ymd("invalid"), "")

    def test_single_digit_day_zero_padded(self):
        self.assertEqual(roc_to_ymd("113/4/1"), "20240401")


# ─────────────────────────────────────────────────────────────────────────────
# ymd formatters
# ─────────────────────────────────────────────────────────────────────────────
class TestYmdFormatters(unittest.TestCase):
    def test_ymd_to_slash(self):
        self.assertEqual(ymd_to_slash("20240401"), "2024/04/01")

    def test_ymd_to_dash(self):
        self.assertEqual(ymd_to_dash("20240401"), "2024-04-01")

    def test_ymd_display(self):
        self.assertEqual(ymd_display("20240401"), "4月1日")

    def test_ymd_display_january(self):
        self.assertEqual(ymd_display("20240101"), "1月1日")


# ─────────────────────────────────────────────────────────────────────────────
# to_num
# ─────────────────────────────────────────────────────────────────────────────
class TestToNum(unittest.TestCase):
    def test_comma_stripped(self):
        self.assertEqual(to_num("43,469"), 43469.0)

    def test_plus_stripped(self):
        self.assertEqual(to_num("+1500"), 1500.0)

    def test_bracket_content_removed(self):
        # re.sub 去掉括號內容 → "" → None
        self.assertIsNone(to_num("(37,392)"))

    def test_null_strings_return_none(self):
        for v in ("", "-", "nan", "NaN", "None", "—", "--", "N/A"):
            self.assertIsNone(to_num(v), msg=f"expected None for {v!r}")

    def test_as_int_rounds_up(self):
        self.assertEqual(to_num("3.7", as_int=True), 4)

    def test_as_int_rounds_down(self):
        self.assertEqual(to_num("3.2", as_int=True), 3)

    def test_plain_float(self):
        self.assertAlmostEqual(to_num("1.5"), 1.5)

    def test_numeric_input(self):
        self.assertEqual(to_num(100), 100.0)

    def test_negative_number(self):
        self.assertEqual(to_num("-500"), -500.0)


# ─────────────────────────────────────────────────────────────────────────────
# first_num
# ─────────────────────────────────────────────────────────────────────────────
class TestFirstNum(unittest.TestCase):
    def test_plain_number(self):
        self.assertEqual(first_num("43469"), 43469)

    def test_comma_number(self):
        self.assertEqual(first_num("43,469"), 43469)

    def test_bracket_format_takes_first(self):
        # "43,469  (37,392)" → 取第一個數字 43469
        self.assertEqual(first_num("43,469  (37,392)"), 43469)

    def test_no_number_returns_none(self):
        self.assertIsNone(first_num("N/A"))

    def test_as_int_false_returns_float(self):
        result = first_num("45.5%", as_int=False)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, float)

    def test_empty_string_returns_none(self):
        self.assertIsNone(first_num(""))


# ─────────────────────────────────────────────────────────────────────────────
# months_in_range
# ─────────────────────────────────────────────────────────────────────────────
class TestMonthsInRange(unittest.TestCase):
    def test_single_month(self):
        self.assertEqual(
            months_in_range(date(2024, 3, 1), date(2024, 3, 31)),
            ["202403"]
        )

    def test_multi_month(self):
        self.assertEqual(
            months_in_range(date(2024, 1, 1), date(2024, 3, 31)),
            ["202401", "202402", "202403"]
        )

    def test_year_crossing(self):
        self.assertEqual(
            months_in_range(date(2023, 11, 1), date(2024, 2, 28)),
            ["202311", "202312", "202401", "202402"]
        )


# ─────────────────────────────────────────────────────────────────────────────
# extract_date
# ─────────────────────────────────────────────────────────────────────────────
class TestExtractDate(unittest.TestCase):
    def test_ad_slash(self):
        self.assertEqual(extract_date("2024/01/15"), "20240115")

    def test_ad_dash(self):
        self.assertEqual(extract_date("2024-04-01"), "20240401")

    def test_roc_slash(self):
        # 113/04/01 → 1911+113=2024
        self.assertEqual(extract_date("113/04/01"), "20240401")

    def test_no_match_returns_none(self):
        self.assertIsNone(extract_date("no date here"))

    def test_embedded_in_text(self):
        self.assertEqual(extract_date("查詢日期: 2024/03/15 結束"), "20240315")


# ─────────────────────────────────────────────────────────────────────────────
# find_data_table
# ─────────────────────────────────────────────────────────────────────────────
_SAMPLE_HTML = """<html><body>
<table><tr><td>導覽列</td></tr></table>
<table>
  <tr><th>外資</th><th>留倉</th><th>口數</th></tr>
  <tr><td>外資</td><td>1000</td><td>2000</td></tr>
</table>
<table>
  <tr><th>外資</th><th>投信</th><th>自營</th><th>留倉</th><th>口數</th><th>金額</th></tr>
  <tr><td>外資</td><td>投信</td><td>自營</td><td>留倉</td><td>口數</td><td>999</td></tr>
</table>
</body></html>"""

class TestFindDataTable(unittest.TestCase):
    def test_finds_matching_table(self):
        tbl = find_data_table(_SAMPLE_HTML, ["外資", "留倉"])
        self.assertIsNotNone(tbl)

    def test_no_match_returns_none(self):
        self.assertIsNone(find_data_table(_SAMPLE_HTML, ["不存在XYZ"]))

    def test_prefers_higher_score(self):
        # 第三個 table 有 外資+投信+自營+留倉+口數 共5個關鍵字命中
        tbl = find_data_table(_SAMPLE_HTML, ["外資", "投信", "自營", "留倉", "口數"])
        self.assertIn("自營", tbl.get_text())

    def test_empty_html_returns_none(self):
        self.assertIsNone(find_data_table("<html></html>", ["外資"]))


# ─────────────────────────────────────────────────────────────────────────────
# expand_table_elem
# ─────────────────────────────────────────────────────────────────────────────
class TestExpandTableElem(unittest.TestCase):
    def test_none_returns_empty(self):
        self.assertEqual(expand_table_elem(None), [])

    def test_simple_table(self):
        html = "<table><tr><td>A</td><td>B</td></tr><tr><td>C</td><td>D</td></tr></table>"
        tbl = BeautifulSoup(html, "html.parser").find("table")
        result = expand_table_elem(tbl)
        self.assertEqual(result[0], ["A", "B"])
        self.assertEqual(result[1], ["C", "D"])

    def test_rowspan_filled(self):
        html = """<table>
            <tr><td rowspan="2">X</td><td>Y</td></tr>
            <tr><td>Z</td></tr>
        </table>"""
        tbl = BeautifulSoup(html, "html.parser").find("table")
        result = expand_table_elem(tbl)
        self.assertEqual(result[0][0], "X")
        self.assertEqual(result[1][0], "X")   # rowspan 展開
        self.assertEqual(result[1][1], "Z")

    def test_colspan_filled(self):
        html = """<table>
            <tr><td colspan="2">SPAN</td></tr>
            <tr><td>L</td><td>R</td></tr>
        </table>"""
        tbl = BeautifulSoup(html, "html.parser").find("table")
        result = expand_table_elem(tbl)
        self.assertEqual(result[0][0], "SPAN")
        self.assertEqual(result[0][1], "SPAN")   # colspan 展開

    def test_empty_table_returns_empty(self):
        html = "<table></table>"
        tbl = BeautifulSoup(html, "html.parser").find("table")
        self.assertEqual(expand_table_elem(tbl), [])


# ─────────────────────────────────────────────────────────────────────────────
# render_leading_table — Bug 2 regression (PCR 閾值 80/120)
# ─────────────────────────────────────────────────────────────────────────────
def _pcr_df(pcr_val):
    return pd.DataFrame([{
        "_date": "20240401", "日期": "4月1日", "成交量": "-",
        "外資": None, "投信": None, "自營": None,
        "外資大小": None, "前五大留倉": None, "前十大留倉": None,
        "選PCR": pcr_val,
        "外(選)": None, "未平倉口數": None, "韭菜指數": None,
    }])


class TestRenderLeadingTablePCR(unittest.TestCase):
    """PCR 顏色（v18.158 台股紅綠化）：
    < 80 → 紅 看多/漲；> 120 → 綠 看空/跌；80~120 → 無色

    v19.68 起 leading_indicators 由 shared.colors SSOT 取色(TRAFFIC_RED/GREEN,
    Tailwind #ef4444/#22c55e,原 GitHub #f85149/#3fb950)。本測試**直接引 SSOT**
    斷言,避免硬編 hex 隨色票升級而 drift(§3.3 反捏造:常數從 SSOT 引入)。
    """
    from shared.colors import TRAFFIC_RED as _RED, TRAFFIC_GREEN as _GREEN
    _RED_HEX = _RED.lstrip("#")
    _GREEN_HEX = _GREEN.lstrip("#")

    def test_pcr_below_80_red(self):
        html = render_leading_table(_pcr_df(65.0))
        self.assertIn(self._RED_HEX, html)

    def test_pcr_above_120_green(self):
        html = render_leading_table(_pcr_df(135.0))
        self.assertIn(self._GREEN_HEX, html)

    def test_pcr_neutral_no_data_color(self):
        # 100.0 在 80~120 之間，PCR 欄不應有顏色；其餘欄全 None
        html = render_leading_table(_pcr_df(100.0))
        self.assertNotIn(self._RED_HEX, html)
        self.assertNotIn(self._GREEN_HEX, html)

    def test_pcr_boundary_80_no_red(self):
        # 剛好 80 不觸發紅色（n < 80 為假）
        html = render_leading_table(_pcr_df(80.0))
        self.assertNotIn(self._RED_HEX, html)

    def test_pcr_boundary_120_no_green(self):
        # 剛好 120 不觸發綠色（n > 120 為假）
        html = render_leading_table(_pcr_df(120.0))
        self.assertNotIn(self._GREEN_HEX, html)


# ─────────────────────────────────────────────────────────────────────────────
# v18.342 PR-L2:_load_stale_pickle + _mark_stale 純函式 helper
# user 2026-06-28「如果遇假日則抓前一次的」+ §2.4「過期 cache 須帶 is_stale 旗標」。
# build_leading_fast 全鏈 IO 太多無法整體測,改測抽出的 L0 純 helper(直接 IO pickle
# 檔 + 標 attrs)。整合行為靠 build_leading_fast 內部 2 處 _load_stale_pickle 呼叫
# + 2 處 _mark_stale 呼叫,各路徑覆蓋 code review 確認。
# ─────────────────────────────────────────────────────────────────────────────
class TestStaleCacheHelpers(unittest.TestCase):
    """`_load_stale_pickle` + `_mark_stale` 行為單測。"""

    def setUp(self):
        import os, pickle, tempfile, time
        self._tmpdir = tempfile.mkdtemp(prefix='test_stale_helpers_')
        self._ck = os.path.join(self._tmpdir, 'fake.pkl')
        self._fake_df = pd.DataFrame([
            {'_date': '20260626', '外資': 100.5, '投信': 5.2, '自營': -10.1,
             '外資大小': 12000, '選PCR': 95.0},
        ])
        with open(self._ck, 'wb') as _f:
            pickle.dump(self._fake_df, _f)
        # 設 mtime 為 90 分鐘前(明確過期)
        _past = time.time() - 90 * 60
        os.utime(self._ck, (_past, _past))

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_load_existing_stale_pickle(self):
        """檔案存在 → 返回 (df, age_min)。"""
        from src.data.macro import _load_stale_pickle
        _df, _age = _load_stale_pickle(self._ck)
        self.assertIsNotNone(_df)
        self.assertEqual(len(_df), 1)
        self.assertIsNotNone(_age)
        self.assertGreater(_age, 60, '預期 age > 60 分鐘')

    def test_load_missing_returns_none(self):
        """檔案不存在 → 返回 (None, None) 不爆。"""
        from src.data.macro import _load_stale_pickle
        _df, _age = _load_stale_pickle('/nonexistent/path/no.pkl')
        self.assertIsNone(_df)
        self.assertIsNone(_age)

    def test_load_corrupt_pickle_returns_none(self):
        """檔案存在但 pickle 壞 → 返回 (None, None) 不爆(§1 fail loud + log)。"""
        import os
        _bad_ck = os.path.join(self._tmpdir, 'bad.pkl')
        with open(_bad_ck, 'wb') as _f:
            _f.write(b'not a pickle')
        from src.data.macro import _load_stale_pickle
        _df, _age = _load_stale_pickle(_bad_ck)
        self.assertIsNone(_df)
        self.assertIsNone(_age)

    def test_mark_stale_sets_attrs(self):
        """標 is_stale=True + stale_age_min 到 df.attrs。"""
        from src.data.macro import _mark_stale
        _df = pd.DataFrame([{'x': 1}])
        _out = _mark_stale(_df, 90.5)
        self.assertTrue(_out.attrs.get('is_stale'))
        self.assertEqual(_out.attrs.get('stale_age_min'), 90.5)

    def test_mark_stale_handles_none(self):
        """None df → 返回 None,不爆。"""
        from src.data.macro import _mark_stale
        self.assertIsNone(_mark_stale(None, 30.0))

    def test_mark_stale_without_age(self):
        """age_min=None → 只標 is_stale,不寫 age。"""
        from src.data.macro import _mark_stale
        _df = pd.DataFrame([{'x': 1}])
        _out = _mark_stale(_df, None)
        self.assertTrue(_out.attrs.get('is_stale'))
        self.assertNotIn('stale_age_min', _out.attrs)


if __name__ == "__main__":
    unittest.main()
