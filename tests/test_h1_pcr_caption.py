# -*- coding: utf-8 -*-
"""H1 ②：🧩 籌碼區「選PCR」圖例不得再標一條表格根本不用的線。

修掉的原始碼（`src/ui/tabs/macro/section_chips.py`，「📅 資料期間」那行 caption）::

    f'前五大>{abs(TOP5_LARGE_TRADER_NET_WARN_LOTS):,}口⚠️  PCR<100偏空'

查證結論（與交辦時的假設**不同**，兩點都記在這裡免得被改回去）：

  * 「100」**不是憑空捏造** —— 同一頁最底下的「🎯 籌碼綜合判斷」計分器確實用
    `>130 / >100 / ≤100` 三段。真正的問題是這行 caption 是**它正下方那張表**的
    圖例，而那張表（`leading_indicators.render_leading_table`）的著色判定式是
    `<80 紅 / >120 綠`。圖例標的線 ≠ 表格用的線。
  * 本區顯示的 PCR 是**百分比刻度**（126.8 這種數字），**不是**比值。
    `li_latest['選PCR']` 由 `leading_indicators` 寫入時已 ×100；B2-b 的
    `normalize_pcr_to_ratio()` 只在取值端換算給規則引擎／LLM，**沒有回寫**
    li_latest。所以把 caption 改寫成比值刻度會製造「caption 說 0.8、表格印 126.8」
    的新矛盾 —— 本次**維持百分比刻度**。

測試分兩層：

  A. **行為**：直接呼叫 `render_leading_table()` 餵邊界值，斷言 `選PCR` 欄的顏色
     恰好在 `shared.pcr_scale` 的兩個常數處翻轉。這是本檔的核心 ——
     `render_leading_table` 那兩個 inline 字面（80 / 120）目前還沒下沉，
     這組測試就是把「L0 常數」與「L1 實作」綁在一起的那條繩子。
     順帶釘住「比值 1.0（本表 100）在這張表上不會亮任何燈」。
  B. **AST**：caption 的數字必須來自那兩個常數，且該 caption 內不得再出現
     `100` 這個字面。掃的是 JoinedStr 的節點結構，不掃註解／docstring。
"""
from __future__ import annotations

import ast
import math
import os
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED
from shared.pcr_scale import (
    PCR_PCT_COMPLACENCY_MAX,
    PCR_PCT_FEAR_MIN,
    PCR_PCT_PARITY,
    normalize_pcr_to_ratio,
)
from src.config import MACRO_ALERT_RULES
from src.data.macro.leading_indicators import render_leading_table

_REPO = Path(__file__).resolve().parent.parent
_SECTION = _REPO / "src/ui/tabs/macro/section_chips.py"


# ══════════════════════════════════════════════════════════════
# A. 行為：表格真正的著色帶
# ══════════════════════════════════════════════════════════════
def _pcr_cell_color(pcr: float) -> str | None:
    """把單一 PCR 值渲染進真的表格，回傳該格的顏色（無著色 → None）。

    刻意**只**給 日期／成交量／選PCR 三欄：其餘欄位缺席時 `fmt` 回 "-"、
    `sty` 回 ""，不會產生干擾用的 span。
    """
    df = pd.DataFrame([{"日期": "8月8日", "成交量": "3000億", "選PCR": pcr}])
    html = render_leading_table(df)
    txt = f"{float(pcr):.1f}"          # 對齊 fmt() 的 "選PCR" 分支
    m = re.search(
        r'<span style="color:(#[0-9a-fA-F]{6});">' + re.escape(txt) + r"</span>",
        html)
    if m:
        return m.group(1)
    assert f"<td>{txt}</td>" in html, (
        f"PCR={pcr} 既沒有著色 span 也找不到無色儲存格，"
        f"render_leading_table 的輸出格式可能改了：\n{html[-800:]}")
    return None


class TestTableColourBands:
    """`shared.pcr_scale` 的常數 ↔ `render_leading_table` 的 inline 字面 對帳。"""

    def test_just_below_complacency_max_is_red(self):
        assert _pcr_cell_color(PCR_PCT_COMPLACENCY_MAX - 0.1) == TRAFFIC_RED

    def test_exactly_at_complacency_max_is_uncoloured(self):
        """判定式是 `< 80`（不含等於）—— 邊界方向也一起釘住。"""
        assert _pcr_cell_color(PCR_PCT_COMPLACENCY_MAX) is None

    def test_exactly_at_fear_min_is_uncoloured(self):
        """判定式是 `> 120`（不含等於）。"""
        assert _pcr_cell_color(PCR_PCT_FEAR_MIN) is None

    def test_just_above_fear_min_is_green(self):
        assert _pcr_cell_color(PCR_PCT_FEAR_MIN + 0.1) == TRAFFIC_GREEN

    def test_parity_is_not_a_line_in_this_table(self):
        """比值 1.0（本表 100）**不會**讓這張表亮任何燈 —— 新 caption 的核心主張。

        舊 caption 說「PCR<100偏空」，但讀數 90 在這張表上是無色的。
        """
        assert _pcr_cell_color(PCR_PCT_PARITY) is None
        assert _pcr_cell_color(PCR_PCT_PARITY - 10.0) is None, (
            "90 在表格上無色，caption 卻說它「偏空」—— 這正是本次修掉的矛盾")

    def test_real_world_reading_is_percent_scale(self):
        """實測值 126.8（STATE.md 記錄的線上讀數）在本表落在綠帶，且印成 126.8。"""
        assert _pcr_cell_color(126.8) == TRAFFIC_GREEN
        html = render_leading_table(
            pd.DataFrame([{"日期": "8月8日", "成交量": "3000億", "選PCR": 126.8}]))
        assert "126.8" in html, "本區顯示的是百分比刻度原值，不是換算後的比值"
        assert ">1.3<" not in html and ">1.27<" not in html


class TestScaleContract:
    """常數與既有 SSOT 的關係 —— 相同處與**分歧處**都寫成斷言。"""

    def test_fear_min_equals_macro_alert_yellow_above(self):
        """120 ＝ `MACRO_ALERT_RULES['pcr']['yellow_above']`（比值 1.2）×100。"""
        _pcr_rule = next(r for r in MACRO_ALERT_RULES if r["key"] == "pcr")
        assert math.isclose(PCR_PCT_FEAR_MIN / 100.0,
                            _pcr_rule["yellow_above"], abs_tol=1e-9)

    def test_complacency_max_deliberately_differs_from_yellow_below(self):
        """80 ≠ `yellow_below`（0.7 → 70）—— 既有的真實分歧，本次刻意不動。

        寫成斷言是為了讓「哪天有人順手統一成 70」這件事變成一個必須解釋的紅燈，
        而不是無聲的行為變更。
        """
        _pcr_rule = next(r for r in MACRO_ALERT_RULES if r["key"] == "pcr")
        assert not math.isclose(PCR_PCT_COMPLACENCY_MAX / 100.0,
                                _pcr_rule["yellow_below"], abs_tol=1e-9), (
            "低檔線兩邊已經一致了 —— 請確認是刻意統一（那就同步更新 "
            "shared/pcr_scale 的註解與本測試），還是誤改")

    def test_constants_round_trip_through_the_scale_normaliser(self):
        """兩個常數都是百分比刻度 → 經 B2-b 的正規化器換回比值。"""
        for _pct in (PCR_PCT_COMPLACENCY_MAX, PCR_PCT_FEAR_MIN, PCR_PCT_PARITY):
            _ratio, _src = normalize_pcr_to_ratio(_pct)
            assert math.isclose(_ratio, _pct / 100.0, rel_tol=1e-9)
            assert "百分比" in _src, (
                f"{_pct} 被判成比值刻度 —— 這組常數的量綱前提就不成立了")


# ══════════════════════════════════════════════════════════════
# B. caption 的 AST 守衛
# ══════════════════════════════════════════════════════════════
def _tree():
    src = _SECTION.read_text(encoding="utf-8")
    return ast.parse(src), src


def _caption_joinedstrs(tree: ast.AST) -> list[ast.JoinedStr]:
    """所有 `st.caption(...)` 的 f-string 實參（非 f-string 的直接略過）。"""
    out: list[ast.JoinedStr] = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "caption"):
            for arg in node.args:
                if isinstance(arg, ast.JoinedStr):
                    out.append(arg)
    return out


def _literal_text(js: ast.JoinedStr) -> str:
    return "".join(v.value for v in js.values
                   if isinstance(v, ast.Constant) and isinstance(v.value, str))


def _names_in(js: ast.JoinedStr) -> set[str]:
    return {n.id for v in js.values if isinstance(v, ast.FormattedValue)
            for n in ast.walk(v) if isinstance(n, ast.Name)}


def _find_caption(tree: ast.AST, needle: str) -> ast.JoinedStr:
    hits = [js for js in _caption_joinedstrs(tree) if needle in _literal_text(js)]
    assert hits, f"找不到含「{needle}」的 st.caption —— 守衛失去對象（{_SECTION}）"
    return hits[0]


class TestCaptionWiring:

    def test_imports_the_band_constants(self):
        tree, _src = _tree()
        imported = {alias.name
                    for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                    and n.module == "shared.pcr_scale"
                    for alias in n.names}
        assert {"PCR_PCT_COMPLACENCY_MAX", "PCR_PCT_FEAR_MIN",
                "PCR_PCT_PARITY"} <= imported, (
            "section_chips 未從 shared.pcr_scale 取著色帶常數 —— "
            "caption 的數字可能又被手抄回去")

    def test_period_caption_uses_the_constants(self):
        tree, src = _tree()
        js = _find_caption(tree, "資料期間")
        names = _names_in(js)
        for want in ("PCR_PCT_COMPLACENCY_MAX", "PCR_PCT_FEAR_MIN"):
            assert want in names, (
                f"「資料期間」caption 沒有引用 {want}：\n"
                f"{ast.get_source_segment(src, js)}")

    def test_period_caption_has_no_hand_typed_hundred(self):
        """該 caption 的**字面**部分不得再出現 100（舊的 `PCR<100偏空`）。

        只看 JoinedStr 的 Constant 片段 → 由常數插值產生的數字不受影響，
        註解／docstring 也不在 AST 裡，不會誤觸發。
        """
        tree, src = _tree()
        js = _find_caption(tree, "資料期間")
        text = _literal_text(js)
        assert "100" not in text, (
            "「資料期間」caption 又出現手打的 100（那是 put/call 平價點，"
            "不是本表的判定線）：\n" + str(ast.get_source_segment(src, js)))
        assert "偏空" not in text, (
            "PCR 低檔在本系統的語意是「保護不足／過樂觀」而非「偏空」：\n"
            + str(ast.get_source_segment(src, js)))

    def test_scale_caption_explains_percent_and_parity(self):
        """第二行 caption 必須明說刻度，並點名 1.0 是常識而非本系統門檻。"""
        tree, src = _tree()
        js = _find_caption(tree, "百分比刻度")
        text = _literal_text(js)
        assert "平價點" in text, ast.get_source_segment(src, js)
        assert "不是本系統的判定線" in text, ast.get_source_segment(src, js)
        assert "PCR_PCT_PARITY" in _names_in(js), (
            "平價點的數字也必須來自常數，不可手打：\n"
            + str(ast.get_source_segment(src, js)))
