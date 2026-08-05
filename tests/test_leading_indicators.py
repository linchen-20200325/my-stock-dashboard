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


# ─────────────────────────────────────────────────────────────────────────────
# v19.172 P0a-①:外資身分別白名單 _fgn_mask
# 事故:原本 `str.contains("外資", na=False)` 會同時撈到「外資」「外資及陸資」
# 「外資自營商」三種身分別 → 同一天多列被 **相加** = 重複計數,淨口數被灌成
# 歷史極端值(稽核實測 −87,626 口)。§1:異常要吼出來,且不可相加。
# ─────────────────────────────────────────────────────────────────────────────
def _fut_df(rows):
    """[(身分別, long, short)] → FinMind TaiwanFuturesInstitutionalInvestors 樣式 df。"""
    return pd.DataFrame([
        {"date": "2026-08-04", "institutional_investors": _n,
         "long_open_interest_balance_volume": _l,
         "short_open_interest_balance_volume": _s}
        for _n, _l, _s in rows
    ])


def _mask_list(m):
    """pandas/numpy bool Series → 純 Python list[bool](避免 numpy 標量比較歧義)。"""
    return [bool(x) for x in m]


class TestForeignAliasMask(unittest.TestCase):
    def test_plain_foreign_selected(self):
        from src.data.macro import _fgn_mask
        df = _fut_df([("自營商", 10, 5), ("投信", 1, 1), ("外資", 100, 200)])
        self.assertEqual(_mask_list(_fgn_mask(df)), [False, False, True])

    def test_legacy_alias_selected(self):
        """舊年份寫「外資及陸資」→ 白名單須認得(否則整段外資資料漏掉)。"""
        from src.data.macro import _fgn_mask
        df = _fut_df([("自營商", 10, 5), ("外資及陸資", 100, 200)])
        self.assertEqual(_mask_list(_fgn_mask(df)), [False, True])

    def test_foreign_dealer_excluded(self):
        """「外資自營商」語意不同(同檔選擇權段本就排除),白名單不得收。"""
        from src.data.macro import _fgn_mask
        df = _fut_df([("外資自營商", 999, 0)])
        self.assertEqual(_mask_list(_fgn_mask(df)), [False])

    def test_both_aliases_only_first_taken(self):
        """核心防重:兩個別名同天並存 → 只採第一個,絕不相加。"""
        from src.data.macro import _fgn_mask
        df = _fut_df([("外資", 100, 200), ("外資及陸資", 100, 200)])
        m = _mask_list(_fgn_mask(df))
        self.assertEqual(sum(m), 1, "同天兩別名不可同時計入(會重複計數)")
        self.assertEqual(m, [True, False], "須採第一個出現的別名")

    def test_net_lots_not_doubled(self):
        """回歸:重複計數會讓淨口數翻倍(−100 → −200)。"""
        from src.data.macro import _fgn_mask
        df = _fut_df([("外資", 100, 200), ("外資及陸資", 100, 200)])
        sub = df[_fgn_mask(df)]
        net = int((sub["long_open_interest_balance_volume"]
                   - sub["short_open_interest_balance_volume"]).sum())
        self.assertEqual(net, -100, "重複計數 → 會變 -200")

    def test_missing_column_returns_none(self):
        from src.data.macro import _fgn_mask
        self.assertIsNone(_fgn_mask(pd.DataFrame([{"date": "2026-08-04"}])))

    def test_empty_df_returns_none(self):
        from src.data.macro import _fgn_mask
        self.assertIsNone(_fgn_mask(pd.DataFrame()))
        self.assertIsNone(_fgn_mask(None))

    def test_unknown_identity_returns_all_false(self):
        """上游又改名 → 0 命中,回全 False(該來源不計入),不臆造、不 fallback contains。"""
        from src.data.macro import _fgn_mask
        df = _fut_df([("Foreign_Investor", 100, 200)])
        m = _fgn_mask(df)
        self.assertIsNotNone(m)
        self.assertEqual(sum(_mask_list(m)), 0)

    def test_nan_identity_not_selected(self):
        """身分別為 None/NaN → 不得被選入(原 contains 用 na=False 擋,白名單同效)。"""
        from src.data.macro import _fgn_mask
        df = _fut_df([("外資", 100, 200), (None, 1, 1)])
        self.assertEqual(_mask_list(_fgn_mask(df)), [True, False])


# ─────────────────────────────────────────────────────────────────────────────
# v19.173:三大法人身分別白名單 _inst_mask(韭菜指數 fallback)
# v19.172 只收了「外資」兩處(_fgn_mask);build_leading_fast §7 的韭菜指數
# fallback 仍用 `any(k in ii for k in ["外資","投信","自營"])` —— 同一個 bug class:
#   ① 「外資」+「外資及陸資」同天並存 → 兩列都收 = 重複計數;
#   ② 「外資自營商」同時含 "外資" 與 "自營" → 被當第 4 個法人多收一列。
# 韭菜指數 =(Σshort − Σlong)/(Σshort + Σlong):分子是差、分母是和,重複計入
# 對兩者的放大倍率不同 → 比值失真(下方 test_leek_ratio_* 直接把差異釘住)。
# ─────────────────────────────────────────────────────────────────────────────
def _leek_pct(df):
    """依 build_leading_fast §7 的公式算法人淨空比(韭菜指數 fallback)。"""
    _l = int(df["long_open_interest_balance_volume"].sum())
    _s = int(df["short_open_interest_balance_volume"].sum())
    if _l + _s <= 0:
        return None
    return round((_s - _l) / (_l + _s) * 100, 1)


# 同一天上游同時吐「外資」「外資及陸資」「外資自營商」的最壞情境。
# 正解只該取 外資(100,200) + 投信(10,10) + 自營商(20,30)。
_DIRTY_ROWS = [
    ("外資",       100, 200),
    ("外資及陸資", 100, 200),   # 同一身分別的舊寫法 → 不可與上一列相加
    ("投信",        10,  10),
    ("自營商",      20,  30),
    ("外資自營商", 999,   0),   # 語意不同(外資/自營商的子集)→ 不可另計一列
]


class TestInstAliasMask(unittest.TestCase):
    def test_three_categories_selected(self):
        from src.data.macro import _inst_mask
        df = _fut_df([("外資", 1, 1), ("投信", 1, 1), ("自營商", 1, 1)])
        self.assertEqual(_mask_list(_inst_mask(df)), [True, True, True])

    def test_legacy_foreign_alias_selected(self):
        """單獨出現「外資及陸資」(舊年份寫法)時必須認得,否則外資整段漏掉。"""
        from src.data.macro import _inst_mask
        df = _fut_df([("外資及陸資", 1, 1), ("投信", 1, 1)])
        self.assertEqual(_mask_list(_inst_mask(df)), [True, True])

    def test_foreign_dealer_excluded(self):
        """「外資自營商」是子集身分別,原 substring 會多收一列 → 白名單不得收。"""
        from src.data.macro import _inst_mask
        df = _fut_df([("外資自營商", 999, 0)])
        self.assertEqual(_mask_list(_inst_mask(df)), [False])

    def test_both_foreign_aliases_only_first_taken(self):
        """核心防重:同一類別兩個別名同天並存 → 只採第一個,絕不相加。"""
        from src.data.macro import _inst_mask
        df = _fut_df([("外資", 100, 200), ("外資及陸資", 100, 200), ("投信", 1, 1)])
        m = _mask_list(_inst_mask(df))
        self.assertEqual(m, [True, False, True], "外資兩別名不可同時計入")

    def test_dirty_day_selects_exactly_three_rows(self):
        from src.data.macro import _inst_mask
        df = _fut_df(_DIRTY_ROWS)
        self.assertEqual(_mask_list(_inst_mask(df)),
                         [True, False, True, True, False])

    def test_leek_ratio_not_distorted_by_duplicates(self):
        """回歸:重複計入會讓韭菜指數**連正負號都翻掉**(29.7 → −47.3)。"""
        from src.data.macro import _inst_mask
        df = _fut_df(_DIRTY_ROWS)
        # 正解:外資(100,200)+投信(10,10)+自營商(20,30) → Σl=130 Σs=240
        self.assertAlmostEqual(_leek_pct(df[_inst_mask(df)]), 29.7, places=1)
        # 舊 substring 行為(全 5 列都收)→ Σl=1229 Σs=440,比值失真且反向
        self.assertAlmostEqual(_leek_pct(df), -47.3, places=1)

    def test_missing_column_returns_none(self):
        from src.data.macro import _inst_mask
        self.assertIsNone(_inst_mask(pd.DataFrame([{"date": "2026-08-04"}])))

    def test_empty_df_returns_none(self):
        from src.data.macro import _inst_mask
        self.assertIsNone(_inst_mask(pd.DataFrame()))
        self.assertIsNone(_inst_mask(None))

    def test_unknown_identity_returns_all_false(self):
        """上游全改名 → 0 命中回全 False(該日不算韭菜),不臆造、不退回 substring。"""
        from src.data.macro import _inst_mask
        df = _fut_df([("Foreign_Investor", 1, 1), ("Dealer_self", 1, 1)])
        m = _inst_mask(df)
        self.assertIsNotNone(m)
        self.assertEqual(sum(_mask_list(m)), 0)

    def test_nan_identity_not_selected(self):
        from src.data.macro import _inst_mask
        df = _fut_df([("投信", 1, 1), (None, 9, 9)])
        self.assertEqual(_mask_list(_inst_mask(df)), [True, False])

    def test_aliases_share_single_ssot(self):
        """§3.3:外資別名清單只能有一份 —— _INST_ALIASES 必須直接引用 _FGN_ALIASES。"""
        from src.data.macro import _FGN_ALIASES, _INST_ALIASES
        self.assertIs(_INST_ALIASES["外資"], _FGN_ALIASES,
                      "別名清單被抄了第二份,改一邊會漂移")
        self.assertEqual(set(_INST_ALIASES), {"外資", "投信", "自營商"})
        # 沒證據的變體不得被腦補進來(§3.3 反捏造)
        _flat = [a for _al in _INST_ALIASES.values() for a in _al]
        for _bad in ("外資自營商", "投資信託", "自營商(避險)", "自營商(自行買賣)"):
            self.assertNotIn(_bad, _flat)


class TestNoSubstringInstListRegression(unittest.TestCase):
    """原始碼守衛:三大法人 substring 清單 `for k in ["外資","投信","自營"]` 不得復活。

    v19.172 的守衛只擋 `str.contains("外資")`,所以韭菜指數 fallback 的
    `any(k in ii for k in [...])` 整個逃逸、CI 全綠 —— 這條就是補那個洞。
    刻意比對 `for k in [...]` 這個**成員判定慣用法**而非單純三個字串,
    才不會誤殺 `taifex_mtx_data` 裡 `find_data_table(html1, ["小型臺指期貨",
    "外資","投信","自營"])` 的表頭關鍵字清單(那是找 table 用的,不是身分別過濾)。
    """

    def test_source_has_no_substring_inst_list(self):
        import inspect
        import re as _re
        from src.data.macro import leading_indicators as _li
        src = inspect.getsource(_li)
        offenders = []
        for ln in src.splitlines():
            _s = ln.strip()
            if _s.startswith("#"):      # 說明「原本錯在哪」的註解不該被罰
                continue
            _norm = _re.sub(r"\s+", "", _s)
            if ('forkin["外資","投信","自營"]' in _norm
                    or "forkin['外資','投信','自營']" in _norm):
                offenders.append(_s)
        self.assertEqual(offenders, [],
                         f"發現殘留三大法人 substring 清單: {offenders}")


class TestNoContainsForeignRegression(unittest.TestCase):
    """原始碼守衛:`str.contains("外資")` 不得復活(重複計數的根源)。"""

    def test_source_has_no_contains_foreign(self):
        import inspect
        from src.data.macro import leading_indicators as _li
        src = inspect.getsource(_li)
        # 只掃程式碼行,略過中文說明用的註解行(§ 說明文內會引用這個字串當反例)
        offenders = [
            ln.strip() for ln in src.splitlines()
            if not ln.strip().startswith("#")
            and ('str.contains("外資"' in ln or "str.contains('外資'" in ln)
        ]
        self.assertEqual(offenders, [], f"發現殘留 contains 外資: {offenders}")

    def test_whitelist_constant_exists(self):
        from src.data.macro import _FGN_ALIASES
        self.assertIn("外資", _FGN_ALIASES)
        self.assertIn("外資及陸資", _FGN_ALIASES)
        self.assertNotIn("外資自營商", _FGN_ALIASES)


# ─────────────────────────────────────────────────────────────────────────────
# v19.172 P0a-②:未平倉口數的契約別標記 + 同當量分母
# 事故:`未平倉口數` 同一欄可能是 MTX 原始口數(taifex_mtx_oi)或 TX 口數
# (largeTraderFutQry),誰先命中算誰;而「外資大小」是 TX 當量(TX + 0.25×MTX),
# 兩者相除 = 量綱錯誤。表頭須把契約別講清楚,不再讓 user 以為同一種口。
# ─────────────────────────────────────────────────────────────────────────────
def _oi_df(oi_val, oi_src, inconsistent=False, fut=None):
    return pd.DataFrame([{
        "_date": "20260804", "日期": "8月4日", "成交量": "-",
        "外資": None, "投信": None, "自營": None,
        "外資大小": fut, "前五大留倉": None, "前十大留倉": None,
        "選PCR": None, "外(選)": None,
        "未平倉口數": oi_val, "_oi_src": oi_src,
        "OI_TX當量": None, "_oi_inconsistent": inconsistent,
        "韭菜指數": None,
    }])


class TestOiContractLabel(unittest.TestCase):
    def test_mtx_source_labeled(self):
        html = render_leading_table(_oi_df(39503, "MTX_raw"))
        self.assertIn("小台 MTX 原始口", html)

    def test_tx_source_labeled(self):
        html = render_leading_table(_oi_df(80000, "TX"))
        self.assertIn("大台 TX 口", html)

    def test_mixed_source_flagged(self):
        df = pd.concat([_oi_df(39503, "MTX_raw"), _oi_df(80000, "TX")],
                       ignore_index=True)
        html = render_leading_table(df)
        self.assertIn("契約別混合", html)

    def test_inconsistent_flag_surfaces(self):
        html = render_leading_table(_oi_df(39503, "MTX_raw", inconsistent=True))
        self.assertIn("不同源", html)

    def test_no_marker_columns_backward_compatible(self):
        """舊 pickle / 舊 schema 無 _oi_src 欄 → 退回中性「口」,不得爆。"""
        html = render_leading_table(_pcr_df(100.0))
        self.assertIn("未平倉口數", html)
        self.assertNotIn("契約別混合", html)

    def test_marker_columns_not_rendered_as_cells(self):
        """`_oi_src` / `OI_TX當量` / `_oi_inconsistent` 不得混進表格欄位。"""
        html = render_leading_table(_oi_df(39503, "MTX_raw"))
        for _c in ("_oi_src", "OI_TX當量", "_oi_inconsistent", "MTX_raw"):
            self.assertNotIn(_c, html, f"{_c} 不該外露到 HTML")

    def test_foreign_futures_header_states_equivalence(self):
        """「外資大小」表頭須標明 TX 當量(否則 user 會以為是原始口數)。"""
        html = render_leading_table(_oi_df(39503, "MTX_raw"))
        self.assertIn("TX當量", html)


class TestMtxToTxFactor(unittest.TestCase):
    """§3.3:當量因子必須是 SSOT 常數,且等於契約乘數比 50/200。"""

    def test_factor_value(self):
        from src.data.macro import _MTX_TO_TX_FACTOR
        self.assertAlmostEqual(_MTX_TO_TX_FACTOR, 50.0 / 200.0)

    def test_equivalent_oi_formula(self):
        """OI_TX當量 = OI_TX + 0.25 × OI_MTX（回歸:分子分母須同當量）。"""
        from src.data.macro import _MTX_TO_TX_FACTOR
        oi_tx, oi_mtx = 80000, 39503
        self.assertEqual(round(oi_tx + _MTX_TO_TX_FACTOR * oi_mtx), 89876)


if __name__ == "__main__":
    unittest.main()
