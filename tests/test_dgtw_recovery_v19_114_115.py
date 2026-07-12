# -*- coding: utf-8 -*-
"""v19.114/115 — dgtw 6100 PMI + 6053 出口 CSV parser 重接回歸鎖。

背景:探針 run 29186611230（美國 IP + NAS）實錘兩條**活 CSV**,現行 parser
從未真解析過(PMI:URL 無 'csv' 字樣被 gate 掉;出口:年度/月份分兩欄+降序未
sort)。本測試用**探針抓到的真實 CSV 樣本**當 fixture(§3.3 不猜格式)。

三個最容易出錯的輸入(§6):
1. 降序來源(出口 115/4 在前) → 必須同月對齊算 YoY,不可 iloc[-1]（取到最舊）
2. Date=YYYYMM 六位數(PMI) + 民國年(出口) → 解析與西元轉換
3. NMI='-' 雜訊欄 / 值域外 / 過舊 → 誠實 skip / None
"""
from __future__ import annotations

import datetime

# 探針實測 PMI CSV（節錄真實 head + 補到 ≥13 月,末筆 = 2026-06 60.7 對帳基準）
_PMI_CSV = "Date,PMI,NMI\n" + "\n".join(
    f"2025{m:02d},{50 + m*0.1:.1f},-" for m in range(1, 13)
) + "\n202601,58.0,-\n202602,58.5,-\n202603,59.0,-\n202604,61.4,-\n" \
    "202605,61.4,-\n202606,60.7,-\n"

# 探針實測海關出口 CSV（民國年、降序;造 25 個月使去年同月 115/? vs 114/? 可對齊）
_EXPORT_HEADER = ('"年度","月份","出口總值(新臺幣千元)","出口(新臺幣千元)",'
                  '"復出口(新臺幣千元)","進口總值(新臺幣千元)"')


def _export_csv():
    # 114 年 1~12 月 + 115 年 1~4 月,降序排列（新月在前,同海關實測）
    rows = []
    for m in range(1, 5):          # 115/4..115/1
        rows.append((115, 5 - m, 2000000000 + (5 - m) * 1000))
    for m in range(1, 13):         # 114/12..114/1
        rows.append((114, 13 - m, 1500000000 + (13 - m) * 1000))
    body = "\n".join(f'"{y}","{mo}","{v}","{int(v*0.9)}","{int(v*0.1)}","{int(v*0.8)}"'
                     for y, mo, v in rows)
    return _EXPORT_HEADER + "\n" + body + "\n"


class TestPmiParse:
    def test_latest_row_picked_within_age(self):
        from src.data.macro.macro_core import _parse_dgtw_pmi_csv
        out = _parse_dgtw_pmi_csv(_PMI_CSV,
                                  today=datetime.date(2026, 7, 12), max_age_days=90)
        assert out == {'value': 60.7, 'date': '2026-06-01'}, out

    def test_out_of_range_skipped(self):
        from src.data.macro.macro_core import _parse_dgtw_pmi_csv
        bad = "Date,PMI,NMI\n202605,120.0,-\n202606,3.0,-\n"   # 皆越界
        assert _parse_dgtw_pmi_csv(
            bad, today=datetime.date(2026, 7, 12), max_age_days=90) is None

    def test_stale_returns_none(self):
        from src.data.macro.macro_core import _parse_dgtw_pmi_csv
        # 最新 2026-06,今天設 2027-06 → age ~365d > 90 → None（不當新資料）
        assert _parse_dgtw_pmi_csv(
            _PMI_CSV, today=datetime.date(2027, 6, 1), max_age_days=90) is None

    def test_empty_and_headeronly(self):
        from src.data.macro.macro_core import _parse_dgtw_pmi_csv
        t = datetime.date(2026, 7, 12)
        assert _parse_dgtw_pmi_csv("", today=t, max_age_days=90) is None
        assert _parse_dgtw_pmi_csv("Date,PMI,NMI\n", today=t, max_age_days=90) is None


class TestExportParse:
    def test_yoy_same_month_alignment_not_iloc(self):
        from src.data.macro.macro_snapshot import _parse_customs_export_csv
        out = _parse_customs_export_csv(_export_csv())
        assert out is not None
        # 最新 = 115/4 = 西元2026/4,值=2000000000+4000=2000004000
        # 去年同月 = 114/4 = 西元2025/4,值=1500000000+4000=1500004000
        # YoY = (2000004000/1500004000 - 1)*100 ≈ 33.33%
        assert out['date'] == '2026-04'
        assert abs(out['yoy'] - 33.33) < 0.05, out

    def test_descending_source_still_correct(self):
        """源降序(115/4 在檔首) → 不得誤取 iloc[-1](=114/1 最舊)。"""
        from src.data.macro.macro_snapshot import _parse_customs_export_csv
        out = _parse_customs_export_csv(_export_csv())
        assert out['date'] == '2026-04', '必須取最新月(115/4),非檔尾最舊列'

    def test_missing_base_month_returns_none(self):
        from src.data.macro.macro_snapshot import _parse_customs_export_csv
        # 只有 115 年 4 個月,無 114 年 → 去年同月缺 → None（§1 不硬湊）
        only115 = _EXPORT_HEADER + "\n" + "\n".join(
            f'"115","{m}","{2000000000+m}","0","0","0"' for m in range(1, 14)
        ) + "\n"
        # 補足 ≥13 列但全 115 年(無去年同月)
        assert _parse_customs_export_csv(only115) is None

    def test_too_few_rows(self):
        from src.data.macro.macro_snapshot import _parse_customs_export_csv
        short = _EXPORT_HEADER + '\n"115","4","2000000000","0","0","0"\n'
        assert _parse_customs_export_csv(short) is None


def test_parsers_are_module_level_pure():
    """兩解析器須為 module-level 純函式（可單測、不需 streamlit/network）。"""
    import src.data.macro.macro_core as mc
    import src.data.macro.macro_snapshot as ms
    assert callable(getattr(mc, '_parse_dgtw_pmi_csv', None))
    assert callable(getattr(ms, '_parse_customs_export_csv', None))
