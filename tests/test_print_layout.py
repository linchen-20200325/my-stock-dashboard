"""tests/test_print_layout.py — 瀏覽器列印(Ctrl+P)輸出守衛(2026-08-26)

## 這些測試在守什麼

使用者用瀏覽器列印總經 v2 分頁,內容切在第 1 層就沒了。修法兩件:

**A. 全域 print CSS**(`src/ui/render/print_css.py`)—— Streamlit 的捲動不在
document 上,它自帶的 `@media print` 只還原了一半的捲動容器。

  這一段最危險的失敗**不是列印壞掉,是螢幕壞掉**:CSS 少一個大括號,
  `@media print{` 就不再包住後面的規則,`display:none` 之類會直接生效在
  **螢幕**上 —— 而寫 CSS 的人只會去看列印預覽,不會發現首頁被自己弄爛。
  故本檔用一個小 parser 檢查「PRINT_CSS 裡不存在任何位於 `@media print`
  之外的規則」,並且大括號必須平衡。

**B. 第 3 層的列印版表格**(`macro_v2_cards.print_table_html`)—— `st.dataframe`
走 glide-data-grid,表畫在 <canvas> 上而且虛擬捲動,**捲出視窗的列不在 DOM 裡**,
CSS 救不了,只能另外輸出一份純 HTML 表。

  這一段最危險的失敗是**兩張表分岔**:螢幕一份、紙上一份,講不一樣的話,
  而且兩邊看起來都很正常(§1)。故本檔從**兩個層次**釘住一致性:
    · 純函式層:所有 chip × 搜尋字組合,列印表的每一格 == `visible_table()`
      餵給 `st.dataframe` 的那一格。
    · 接線層(AppTest,真的把分頁 render 出來):畫面上互動表的內容
      == 同一次 render 產生的列印表內容。**篩選改了,兩邊要一起改。**

⚠️ 沙箱沒有真實瀏覽器 —— 本檔**驗不了列印出來長什麼樣**,只驗
「CSS 沒有洩漏到螢幕」與「兩份表資料一致」。實際版面須人工 Ctrl+P 驗證。
"""
from __future__ import annotations

import html as _html
import re
import textwrap

import pytest


# ══════════════════════════════════════════════════════════════════════
# CSS 小 parser —— 「有沒有規則跑到 @media print 外面」
# ══════════════════════════════════════════════════════════════════════
def _rules_outside_media_print(css: str) -> tuple[list[str], int]:
    """回 `(在 @media print 之外的選擇器清單, 收尾時的大括號深度)`。

    深度不為 0 = 大括號沒平衡 = 這段 CSS 本身就壞了(少一個 `}` 正是
    「@media print 沒包住後面規則」最常見的成因)。
    """
    body = re.sub(r"</?style[^>]*>", "", css)
    outside: list[str] = []
    depth = 0
    media_depth: int | None = None      # 進入 @media print 當下的 depth
    buf = ""
    i = 0
    while i < len(body):
        if body.startswith("/*", i):                  # 註解整段跳過
            j = body.find("*/", i + 2)
            i = len(body) if j < 0 else j + 2
            continue
        ch = body[i]
        if ch == "{":
            sel, buf = buf.strip(), ""
            depth += 1
            if sel.startswith("@"):
                if media_depth is None and re.search(r"\bprint\b", sel):
                    media_depth = depth
            elif media_depth is None:
                outside.append(sel)
        elif ch == "}":
            if media_depth is not None and depth == media_depth:
                media_depth = None
            depth -= 1
            buf = ""
        else:
            buf += ch
        i += 1
    return outside, depth


class TestTheCssCheckerActuallyChecks:
    """先證明上面那個 parser 抓得到東西 —— 否則下一組全綠也毫無意義。"""

    def test_a_rule_outside_media_print_is_caught(self):
        bad = "<style>\n.foo{display:none;}\n@media print{.bar{color:red;}}\n</style>"
        outside, depth = _rules_outside_media_print(bad)
        assert outside == [".foo"] and depth == 0

    def test_a_missing_closing_brace_is_caught(self):
        """少一個 `}`:`@media print{` 之後的規則全部洩漏到螢幕。"""
        bad = "<style>@media print{.a{color:red;}\n.b{display:none;}</style>"
        _, depth = _rules_outside_media_print(bad)
        assert depth != 0, "大括號沒平衡卻沒被抓到"

    def test_a_stray_extra_brace_leaks_the_rest(self):
        """多一個 `}` 提前關掉 media query → 後面的規則跑到螢幕上。"""
        bad = "<style>@media print{.a{color:red;}}.b{display:none;}</style>"
        outside, depth = _rules_outside_media_print(bad)
        assert ".b" in outside and depth == 0

    def test_a_clean_print_only_sheet_passes(self):
        ok = "<style>@media print{.a{color:red;}.b{display:none;}}</style>"
        assert _rules_outside_media_print(ok) == ([], 0)


class TestPrintCssIsPrintOnly:
    """PRINT_CSS 只准影響列印,**一條都不准洩漏到螢幕**。"""

    def test_no_rule_escapes_the_media_query(self):
        from src.ui.render.print_css import PRINT_CSS
        outside, depth = _rules_outside_media_print(PRINT_CSS)
        assert outside == [], (
            f"這些規則不在 @media print 內,會直接影響螢幕顯示:{outside}")
        assert depth == 0, "大括號沒平衡 —— @media print 沒包住全部規則"

    def test_exactly_one_media_block_and_it_is_print(self):
        from src.ui.render.print_css import PRINT_CSS
        ats = re.findall(r"@[a-z-]+[^{]*", PRINT_CSS)
        assert len(ats) == 1, f"預期只有一個 at-rule,實際 {ats}"
        assert re.search(r"\bprint\b", ats[0]), ats[0]

    def test_restores_all_four_scroll_containers(self):
        """四層捲動容器少還原任何一層,內容就還是被關在一個視窗高的盒子裡。

        對照 `print_css.py` docstring 的比對表(Streamlit 1.61.1 / 1.59.0)。
        """
        from src.ui.render.print_css import PRINT_CSS
        for sel in ('[data-testid="stApp"]',
                    '[data-testid="stAppViewContainer"]',
                    '[data-testid="stAppViewContainer"]>div',
                    'section[data-testid="stMain"]'):
            assert sel in PRINT_CSS, f"少了 {sel} 的列印還原規則"

    def test_the_fragile_positional_selector_is_documented(self):
        """`stAppViewContainer>div` 是位置選擇器(那一層沒有 testid 也沒有
        class),Streamlit 改 DOM 就失效。**必須**在檔內寫明它脆弱在哪、
        哪個版本驗過 —— 否則下一個人不會知道要重驗。"""
        import pathlib
        src = pathlib.Path("src/ui/render/print_css.py").read_text(encoding="utf-8")
        assert "1.61.1" in src, "沒有寫明驗證過的 streamlit 版本"
        assert "脆弱" in src or "fragile" in src
        assert "內部實作細節" in src, "沒有寫明 data-testid 不是公開 API"


# ══════════════════════════════════════════════════════════════════════
# 列印版表格:與互動表同一份資料
# ══════════════════════════════════════════════════════════════════════
def _parse_print_table(markup: str) -> dict[str, list[str]]:
    """把 `print_table_html()` 的輸出解析回 `{欄名: [值,...]}`。"""
    ths = [_html.unescape(x) for x in re.findall(r"<th>(.*?)</th>", markup, re.DOTALL)]
    body = re.search(r"<tbody>(.*?)</tbody>", markup, re.DOTALL)
    rows = re.findall(r"<tr>(.*?)</tr>", body.group(1), re.DOTALL) if body else []
    out: dict[str, list[str]] = {h: [] for h in ths}
    for r in rows:
        tds = [_html.unescape(x) for x in re.findall(r"<td>(.*?)</td>", r, re.DOTALL)]
        assert len(tds) == len(ths), f"欄數對不上:{len(tds)} vs {len(ths)}"
        for h, v in zip(ths, tds):
            out[h].append(v)
    return out


def _mixed_rows():
    from src.compute.macro.macro_helpers import compute_five_bucket_summary
    from src.ui.tabs.tab_macro_v2 import build_rows
    rd: dict = {}
    compute_five_bucket_summary(
        macro_info={"vix": 33.0, "us10y": 4.9},
        mkt_info={"foreign_net": -180.0},
        readiness_out=rd,
    )
    return build_rows(rd)


class TestPrintTableMirrorsTheInteractiveTable:

    def test_every_cell_is_identical_for_every_filter(self):
        """所有 chip × 搜尋字組合,列印表每一格 == 互動表每一格。

        兩張表分岔 = 同一頁上螢幕與紙本說不一樣的話,而且兩邊都看起來
        很正常(§1)。這條是那件事的守衛。
        """
        from src.ui.render.macro_v2_cards import print_table_html
        from src.ui.tabs.tab_macro_v2 import CHIP_ORDER, visible_table

        rows = _mixed_rows()
        checked = 0
        for chip in CHIP_ORDER:
            for q in ("", "率", "指數", "VIX", "融資"):
                visible, table = visible_table(rows, chip=chip, query=q)
                if not visible:
                    continue
                got = _parse_print_table(print_table_html(table, "抬頭"))
                assert list(got) == list(table), (
                    f"chip={chip} query={q!r} 欄位不同:{list(got)} vs {list(table)}")
                for col in table:
                    assert got[col] == [str(v) for v in table[col]], (
                        f"chip={chip} query={q!r} 欄「{col}」內容分岔:"
                        f"列印={got[col]} 互動表={table[col]}")
                checked += 1
        assert checked >= 10, f"只比對到 {checked} 組,測試前提失效"

    def test_row_count_follows_the_filter(self):
        """列印表跟著篩選走(不是永遠印全部 16 盞)。"""
        from src.ui.render.macro_v2_cards import print_table_html
        from src.ui.tabs.tab_macro_v2 import visible_table
        rows = _mixed_rows()
        _, all_tbl = visible_table(rows)
        _, chips_tbl = visible_table(rows, chip="chips")
        n_all = len(_parse_print_table(print_table_html(all_tbl, "x"))["指標"])
        n_chips = len(_parse_print_table(print_table_html(chips_tbl, "x"))["指標"])
        assert n_all == len(rows) == 16
        assert 0 < n_chips < n_all, "篩選對列印表沒有作用"

    def test_values_are_html_escaped(self):
        from src.ui.render.macro_v2_cards import print_table_html
        out = print_table_html({"欄": ["<script>x</script>"]}, "&caption")
        assert "<script>" not in out
        assert "&lt;script&gt;" in out and "&amp;caption" in out

    def test_empty_table_yields_no_rows_not_a_fake_row(self):
        from src.ui.render.macro_v2_cards import print_table_html
        out = print_table_html({"欄": []}, "x")
        assert "<td>" not in out


class TestPrintCaption:
    """印出來只有 3 列時,紙上必須寫明「16 盞裡篩了 3 盞」(§1)。"""

    def test_states_shown_total_and_active_filter(self):
        from src.ui.tabs.tab_macro_v2 import print_caption
        cap = print_caption(chip="chips", query="融資", shown=1, total=16)
        assert "1 / 16" in cap
        assert "籌碼" in cap, "沒講出目前選的分類"
        assert "融資" in cap, "沒講出目前的搜尋字"

    def test_omits_an_empty_query(self):
        from src.ui.tabs.tab_macro_v2 import print_caption
        cap = print_caption(chip="all", query="   ", shown=16, total=16)
        assert "全部" in cap and "搜尋「" not in cap


# ══════════════════════════════════════════════════════════════════════
# 接線層:真的把分頁 render 出來,比對畫面上的兩張表
# ══════════════════════════════════════════════════════════════════════
pytestmark_slow = pytest.mark.slow

_SCRIPT = textwrap.dedent("""
    import streamlit as st
    from src.ui.tabs.tab_macro_v2 import render_tab_macro_v2
    render_tab_macro_v2()
""")


def _run_tab(tmp_path, timeout=90):
    from streamlit.testing.v1 import AppTest
    script = tmp_path / "_mount_macro_v2.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=timeout)
    at.run()
    return at


def _chip_radio(at):
    """取第 3 層的「分類」chip radio —— **用 key 取,不用位置取**。

    ## 為什麼這裡不能寫 `at.radio[0]`(2026-08-27 回歸的根因)

    本檔寫成時(commit `6909021`)整個 `render_tab_macro_v2()` 只有**一顆**
    radio,於是 `at.radio[0]` 剛好就是分類 chip。後來 commit `9361ea9`
    在**第 2 層**加了「密度」切換(`key="v2_chart_density"`),它渲染的位置
    在第 3 層之前 → `at.radio[0]` 從此指向密度切換,`set_value("chips")`
    在密度那顆上找不到對應選項,炸成
    `ValueError: 'chips' is not in list`。

    **這不是產品端的 bug** —— 兩顆 radio 各有自己的 key,行為都正確;
    壞掉的是本檔「用位置當把手」這個假設:它把「畫面上第一顆 radio 是誰」
    當成穩定契約,而那從來就不是契約。

    改用 key 之後,若哪天 `v2_detail_chip` 真的被移除/改名,
    `WidgetList.__call__` 會丟 `KeyError: 'v2_detail_chip'` —— 直接指出
    是哪顆 widget 不見了,而不是留下一句要追三層 streamlit 內部才看得懂的
    `'chips' is not in list`(§1:壞掉要講清楚壞在哪)。

    ⚠️ 本函式**沒有放寬任何斷言** —— 兩表連動的檢查一字未改,
    換掉的只是「怎麼找到那顆 chip radio」。
    """
    _r = at.radio("v2_detail_chip")
    # 多一道:確認拿到的真的是分類 chip(選項是中文標籤,不是 chip key)。
    # 若日後有人把 key 掛到別顆 widget 上,這裡就會當場講出實際選項。
    assert "籌碼" in _r.options, (
        f"key='v2_detail_chip' 取到的不是第 3 層分類 chip,選項為 {_r.options}")
    return _r


def _print_table_markup(at):
    # 比對 `<table class=` 而不只是 class 名 —— 只比 class 名會連 CSS 的
    # <style> 區塊一起命中(那裡面也有 `.v2-print-tbl` 的樣式定義)。
    hits = [m.value for m in at.markdown
            if '<table class="v2-print-tbl"' in (m.value or "")]
    assert len(hits) == 1, f"預期畫面上剛好一份列印表,實際 {len(hits)} 份"
    return hits[0]


@pytest.mark.slow
class TestLayer3PrintTableIsWiredToTheSameData:

    def test_tab_renders_without_exception(self, tmp_path):
        at = _run_tab(tmp_path)
        assert not at.exception, f"總經 v2 render 有 uncaught exception:{at.exception}"

    def test_screen_table_and_print_table_agree(self, tmp_path):
        """同一次 render:互動表顯示什麼,列印表就必須是什麼。"""
        at = _run_tab(tmp_path)
        assert not at.exception, at.exception
        assert len(at.dataframe) == 1, f"預期一張互動表,實際 {len(at.dataframe)}"
        shown = at.dataframe[0].value          # DataFrame(欄名同 _table_columns)
        got = _parse_print_table(_print_table_markup(at))
        assert list(got) == list(shown.columns), (
            f"欄位不同:列印={list(got)} 互動表={list(shown.columns)}")
        for col in shown.columns:
            assert got[col] == [str(v) for v in shown[col].tolist()], (
                f"欄「{col}」分岔:列印={got[col]} 互動表={shown[col].tolist()}")

    def test_changing_the_filter_moves_both_tables_together(self, tmp_path):
        """改 chip → 互動表變短,列印表必須跟著變短且內容仍相等。

        若哪天有人把列印表接到未篩選的 `rows`,這條會紅。
        """
        at = _run_tab(tmp_path)
        assert not at.exception, at.exception
        n_before = len(at.dataframe[0].value)
        _chip_radio(at).set_value("chips").run()
        assert not at.exception, at.exception
        shown = at.dataframe[0].value
        got = _parse_print_table(_print_table_markup(at))
        assert len(shown) < n_before, "測試前提失效:切 chip 後互動表沒變短"
        assert len(got["指標"]) == len(shown), (
            f"列印表 {len(got['指標'])} 列 vs 互動表 {len(shown)} 列 —— 沒跟著篩選走")
        for col in shown.columns:
            assert got[col] == [str(v) for v in shown[col].tolist()]

    def test_print_caption_reports_the_active_filter(self, tmp_path):
        at = _run_tab(tmp_path)
        _chip_radio(at).set_value("chips").run()
        assert not at.exception, at.exception
        cap = re.search(r'class="v2-print-cap">(.*?)</p>',
                        _print_table_markup(at), re.DOTALL).group(1)
        assert "籌碼" in cap and "/ 16" in cap
