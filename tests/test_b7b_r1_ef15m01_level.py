"""DL-f1-r1：M1B／M2 餘額改取 CBC EF15M01（日平均、依標籤成對、官方年增率對帳）。

═══ fixture 來源（逐字，非推論）══════════════════════════════════════════
`EF15_META`／`EF15_TABLE1`／`EF15_TABLE2`／`EF15_REAL_ROWS` 逐字轉錄自探針 log
（GitHub Actions run 36408641177，`DL-f1-r1_section_verbatim_no_ts.log` 的 (a) 段）：
meta 全文、data.structure 全文、以及 5 列真實資料（列 0、1、468、469、470）。

`_synthetic_rows()` 補一段 **2024-01～2026-04 共 28 個月的自洽合成序列**（≥ 25 個月），
讓對帳與 sanity 測得到：
  - M1B／M2 的 2025-05～07 由真實 2026-05～07 的「餘額 ÷ (1 + 官方年增率)」倒推 ——
    於是那 3 列真實資料的官方年增率可被對帳；
  - 其餘月份平滑成長；每一列合成資料的官方年增率 = 由合成餘額自算後**四捨五入到小數兩位**
    （與 CBC 發布精度一致），t−12 不在 fixture 內的月份則用同一成長率推算。
  - 各序列成長率刻意不同 → M1A 與 M1B 的年增率不同，配錯欄時對帳必然抓得到。
  ⚠️ 真實三列能對帳，是因為它們的 t−12 由它們自己倒推 —— 這**不是**對真實資料的對帳驗證。
     真實全表的對帳另由探針 GitHub Actions run 36419092722 實測：M1B、M2 各 459 列全數落在
     容差內（max|Δ| 0.004993／0.004999 pp）。本容器連不到 CBC（egress 403），本檔只測規則。

無網路：`fetch_url` 以 monkeypatch 回應；寫檔一律導到 `tmp_path`，不碰 repo 的 `data_cache/`。
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import random
import shutil
import sqlite3
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import scripts.update_macro_history as umh

_REPO = Path(__file__).resolve().parent.parent
_REPO_M1M2 = _REPO / "data_cache" / "finmind_m1m2.parquet"

sys.path.insert(0, str(_REPO / "scripts"))
import export_stock_db as E  # noqa: E402  （同 tests/test_export_stock_db.py 的載入方式）

# ── 逐字：探針 (a) 段 EF15M01 meta 全文 ──────────────────────────────────────
EF15_META = {
    "title": "5.貨幣總計數-A.日平均數依期間",
    "sender": "中央銀行",
    "prepared": "2026/9/28 下午 06:16:17",
    "filename": "EF15M01.px",
    "links": "https://cpx.cbc.gov.tw/api/DataAPI/Get?FileName=EF15M01",
    "note": "請參閱各期本行出版之「金融統計月報」。",
    "refperiod": "各項資料發布請參照本行<a href='https://www.stat.gov.tw/News_NoticeCalendar"
                 ".aspx?n=3717&IsControl=0&_Hide=1&Dept=A59000000N'>「預告統計資料發布時間表」</a>",
    "last_updated": "2026-08-27",
    "units": "新台幣百萬元,%",
    "matrix": "EF15",
}

# ── 逐字：探針 (a) 段 EF15M01 data.structure 全文 ────────────────────────────
EF15_TABLE1 = [
    "貨幣機構以外各部門持有通貨",
    "存款貨幣-計",
    "存款貨幣-支票存款",
    "存款貨幣-活期存款",
    "存款貨幣-活期儲蓄存款",
    "準貨幣-計",
    "準貨幣-定期及定期儲蓄存款",
    "準貨幣-外匯存款",
    "準貨幣-郵政儲金",
    "準貨幣-外國人新台幣存款",
    "準貨幣-附買回交易餘額",
    "準貨幣- 貨幣市場共同基金等",
    "貨幣總計數 -Ｍ１Ａ",
    "貨幣總計數 -Ｍ１Ｂ",
    "貨幣總計數 -Ｍ２",
]
EF15_TABLE2 = ["原始值", "年增率"]
I_CASH, I_SAVINGS, I_QUASI, I_MMF, I_M1A, I_M1B, I_M2 = 0, 4, 5, 11, 12, 13, 14

# ── 逐字：探針 (a) 段 5 列真實資料（列 0、1、468、469、470）─────────────────
EF15_REAL_ROWS = [
    ["1987M05", "242643", "-", "1012556", "-", "176462", "-", "305811", "-", "530283", "-",
     "2176920", "-", "1445671", "-", "7044", "-", "724205", "-", "-", "-", "-", "-", "-", "-",
     "724916", "-", "1255199", "-", "3432119", "-"],
    ["1987M06", "243856", "-", "1038393", "-", "180993", "-", "310366", "-", "547034", "-",
     "2189728", "-", "1447774", "-", "7659", "-", "734295", "-", "-", "-", "-", "-", "-", "-",
     "735215", "-", "1282249", "-", "3471977", "-"],
    ["2026M05", "3614814", "6.35", "27004067", "10.00", "417265", "-1.78", "8565184", "9.55",
     "18021618", "10.52", "39354060", "6.52", "22399154", "6.98", "9291302", "8.81", "7304740",
     "1.40", "236501", "42.53", "122363", "22.10", "-", "-", "12597263", "8.20", "30618881",
     "9.56", "69972941", "7.83"],
    ["2026M06", "3584142", "5.64", "27164715", "9.92", "415147", "-1.50", "8582536", "8.84",
     "18167032", "10.73", "39541474", "7.17", "22340309", "6.13", "9550359", "13.97", "7263544",
     "0.73", "267925", "67.33", "119337", "23.26", "-", "-", "12581825", "7.54", "30748857",
     "9.40", "70290331", "8.13"],
    ["2026M07", "3572824", "5.29", "26958124", "7.62", "436246", "0.78", "8707221", "9.97",
     "17814657", "6.68", "39693814", "7.47", "22390151", "6.67", "9631467", "13.72", "7239269",
     "0.30", "299360", "87.13", "133567", "38.18", "-", "-", "12716291", "8.28", "30530948",
     "7.34", "70224762", "7.42"],
]


def _lv_col(i: int) -> int:
    return 1 + 2 * i


def _yy_col(i: int) -> int:
    return 2 + 2 * i


def _p(y: int, m: int) -> str:
    return f"{y}M{m:02d}"


def _shift(y: int, m: int, k: int) -> tuple[int, int]:
    t = y * 12 + (m - 1) + k
    return t // 12, t % 12 + 1


def _round2(x: float) -> str:
    """CBC 發布精度：四捨五入到小數兩位（Decimal 半進位，避開二進位 round 的邊界偏差）。"""
    return str(Decimal(repr(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# 各序列月成長率（刻意各不相同 → M1A 與 M1B 年增率不同）
_GROWTH = {i: 1.0 + 0.0030 + 0.0003 * i for i in range(15)}
_GROWTH[I_M1A] = 1.0040
_GROWTH[I_M1B] = 1.0075
_GROWTH[I_M2] = 1.0060
_SYN_MONTHS = [_shift(2024, 1, k) for k in range(28)]      # 2024-01 … 2026-04


def _synthetic_levels() -> dict[int, dict[tuple[int, int], int]]:
    real = {r[0]: r for r in EF15_REAL_ROWS}
    r05 = real["2026M05"]
    out: dict[int, dict] = {}
    for i in range(15):
        if r05[_lv_col(i)] == "-":
            continue
        base = int(r05[_lv_col(i)])
        g = _GROWTH[i]
        # 2023-01 … 2026-04：以 2026-05 真值往回推（2023 只用來算 2024 的官方年增率,不入表）
        out[i] = {_shift(2023, 1, k): round(base * g ** (-(40 - k))) for k in range(40)}
    for i in (I_M1B, I_M2):
        # 錨點：2025-05～07 由真實 2026-05～07 的餘額與官方年增率倒推
        anchors = {}
        for per, ym in (("2026M05", (2025, 5)), ("2026M06", (2025, 6)), ("2026M07", (2025, 7))):
            lv_t = int(real[per][_lv_col(i)])
            yy_t = float(real[per][_yy_col(i)])
            anchors[ym] = round(lv_t / (1 + yy_t / 100))
        out[i].update(anchors)
        # 2025-08 … 2026-04：錨點 2025-07 → 真值 2026-05 之間幾何內插（平滑接上真實列）
        a7, l05 = anchors[(2025, 7)], int(r05[_lv_col(i)])
        gi = (l05 / a7) ** (1 / 10)
        for k in range(1, 10):
            out[i][_shift(2025, 7, k)] = round(a7 * gi ** k)
        # 2023-01 … 2025-04：自錨點 2025-05 以固定成長率往回推
        a5 = anchors[(2025, 5)]
        for k in range(1, 29):
            out[i][_shift(2025, 5, -k)] = round(a5 * _GROWTH[i] ** (-k))
    return out


def _synthetic_rows() -> list[list[str]]:
    lv = _synthetic_levels()
    rows = []
    for (y, m) in _SYN_MONTHS:
        row = [_p(y, m)]
        for i in range(15):
            if i not in lv:
                row += ["-", "-"]
                continue
            a, b = lv[i][(y, m)], lv[i][_shift(y, m, -12)]
            row += [str(a), _round2((a / b - 1) * 100)]
        rows.append(row)
    return rows


def ef15_rows() -> list[list[str]]:
    """真實 1987-05、1987-06 ＋ 合成 2024-01～2026-04 ＋ 真實 2026-05～07（舊 → 新）。"""
    return ([list(r) for r in EF15_REAL_ROWS[:2]] + _synthetic_rows()
            + [list(r) for r in EF15_REAL_ROWS[2:]])


def ef15_body(rows=None, *, meta=None, table1=None, table2=None) -> dict:
    """組 EF15M01 回應（形狀同探針：頂層 meta + data{dataSets, structure{Table1, Table2}}）。"""
    return {
        "meta": copy.deepcopy(EF15_META if meta is None else meta),
        "data": {
            "dataSets": ef15_rows() if rows is None else rows,
            "structure": {
                "Table1": [{"data": t} for t in (EF15_TABLE1 if table1 is None else table1)],
                "Table2": [{"data": t} for t in (EF15_TABLE2 if table2 is None else table2)],
            },
        },
    }


def official_yoy(vals) -> list[str]:
    """逐月（連續月份）餘額 → CBC 形狀的官方年增率字串（兩位四捨五入；前 12 個月 "-"）。"""
    out = []
    for k, v in enumerate(vals):
        if k < 12:
            out.append("-")
            continue
        a, b = float(v), float(vals[k - 12])
        out.append(_round2((a / b - 1) * 100) if b > 0 else "-")
    return out


def ef15_body_from_levels(periods, m1b, m2, *, m1a=None, m1b_yoy=None, m2_yoy=None) -> dict:
    """任意 M1B／M2（／M1A）餘額序列 → EF15M01 形狀回應；其餘 12 個序列為 "-"。

    官方年增率預設 = `official_yoy`（由給定餘額自算、兩位四捨五入）；
    傳 `m1b_yoy`／`m2_yoy`（字串 list）可覆寫，用來模擬「原始值欄其實是流量」等情境。
    """
    series = {I_M1B: (m1b, m1b_yoy or official_yoy(m1b)),
              I_M2: (m2, m2_yoy or official_yoy(m2))}
    if m1a is not None:
        series[I_M1A] = (m1a, official_yoy(m1a))
    rows = []
    for k, per in enumerate(periods):
        row = [per]
        for i in range(15):
            if i in series:
                row += [str(series[i][0][k]), series[i][1][k]]
            else:
                row += ["-", "-"]
        rows.append(row)
    return ef15_body(rows)


class _R:
    status_code = 200

    def __init__(self, body):
        self._b = body
        self.text = str(body)[:50]

    def json(self):
        return self._b


def patch_ef15(monkeypatch, body, *, ms1_rows=None) -> list:
    """Tier 1（ms1.json）回 `ms1_rows`（預設 None=失敗）；PXWeb 只認得 EF15M01。回請求紀錄。"""
    import src.data.macro.tw_macro as tw
    import src.data.proxy.proxy_helper as ph
    monkeypatch.setattr(tw, "fetch_cbc_ms1_rows", lambda *a, **k: ms1_rows)
    calls: list = []

    def _fu(url, params=None, **k):
        calls.append((params or {}).get("FileName"))
        if (params or {}).get("FileName") != "EF15M01":
            return None                               # 其他檔一律當失敗（不應被請求）
        return _R(body)
    monkeypatch.setattr(ph, "fetch_url", _fu)
    return calls


def _fetch_all():
    return umh.fetch_finmind_m1m2(dt.date(1980, 1, 1), dt.date(2030, 1, 1), "")


def _row_of(rows, per):
    return next(r for r in rows if r[0] == per)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ═════════════════════════════════════════════════════════════════════════════
class TestFixtureTranscription:
    """先確認 fixture 本身沒抄錯：真實列內部恆等式必須成立（否則後面全部白測）。"""

    def test_real_rows_satisfy_monetary_identities(self):
        for r in EF15_REAL_ROWS:
            m1a, m1b, m2 = (int(r[_lv_col(i)]) for i in (I_M1A, I_M1B, I_M2))
            assert m1a + int(r[_lv_col(I_SAVINGS)]) == m1b, r[0]      # M1B = M1A + 活期儲蓄
            assert m1b + int(r[_lv_col(I_QUASI)]) == m2, r[0]         # M2 = M1B + 準貨幣
            assert len(r) == 1 + len(EF15_TABLE1) * len(EF15_TABLE2)

    def test_synthetic_segment_is_long_and_self_consistent(self):
        syn = _synthetic_rows()
        assert len(syn) >= 25
        rows = ef15_rows()
        idx = {r[0]: r for r in rows}
        n = 0
        for r in rows:
            y, m = int(r[0][:4]), int(r[0][5:])
            prev = idx.get(_p(*_shift(y, m, -12)))
            if prev is None or r[_yy_col(I_M1B)] == "-":
                continue
            for i in (I_M1B, I_M2):
                a, b = int(r[_lv_col(i)]), int(prev[_lv_col(i)])
                assert _round2((a / b - 1) * 100) == r[_yy_col(i)], (r[0], i)
                n += 1
        assert n == 2 * 19          # 2025-01 … 2026-07 共 19 個月 × 2 序列（含 3 列真實資料）


# ═════════════════════════════════════════════════════════════════════════════
class TestParseEF15:
    def test_picks_m1b_m2_by_label_not_m1a(self):
        df, desc = umh._parse_cbc_ef15m01_levels(ef15_body())
        assert df is not None, desc
        got = df.set_index("date")
        assert got.loc[dt.date(2026, 7, 1), "m1b"] == 30530948          # row[27]
        assert got.loc[dt.date(2026, 7, 1), "m2"] == 70224762           # row[29]
        assert got.loc[dt.date(1987, 5, 1), "m1b"] == 1255199
        assert got.loc[dt.date(1987, 5, 1), "m2"] == 3432119
        m1a = {int(r[_lv_col(I_M1A)]) for r in EF15_REAL_ROWS}
        assert not (set(got["m1b"]) & m1a), "M1A 的餘額不得出現在 m1b"
        assert str(df["m1b"].dtype) == "int64" and str(df["m2"].dtype) == "int64"
        assert all(type(d) is dt.date and d.day == 1 for d in df["date"])
        assert len(df) == 2 + 28 + 3 and df["date"].is_monotonic_increasing

    def test_nfkc_fullwidth_label_is_normalised(self):
        raw = EF15_TABLE1[I_M1B]
        assert "Ｍ１Ｂ" in raw                                  # 原始標籤確為全形
        df, desc = umh._parse_cbc_ef15m01_levels(ef15_body())
        assert df is not None and "貨幣總計數-M1B" in desc and "貨幣總計數-M2" in desc
        # 半形、全形連字號（U+FF0D）、全形空白（U+3000）→ NFKC 後同名，一樣命中
        for variant in ("貨幣總計數 -M1B", "貨幣總計數－Ｍ１Ｂ", "貨幣總計數　-Ｍ１Ｂ"):
            t1 = list(EF15_TABLE1)
            t1[I_M1B] = variant
            df2, d2 = umh._parse_cbc_ef15m01_levels(ef15_body(table1=t1))
            assert df2 is not None, (variant, d2)
            assert df2["m1b"].tolist() == df["m1b"].tolist()

    def test_missing_m1b_label_fails_loud_never_falls_back_to_m1a(self, capsys):
        t1 = list(EF15_TABLE1)
        t1[I_M1B] = "貨幣總計數 -Ｍ１Ｃ"
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(table1=t1))
        assert df is None and "M1B" in why and "0" in why
        assert "Table1=" in capsys.readouterr().out           # fail loud：印出標籤

    def test_partial_name_is_not_a_match(self):
        t1 = list(EF15_TABLE1)
        t1[I_M1B] = "貨幣總計數 -Ｍ１Ｂ（含外幣）"
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(table1=t1))
        assert df is None and "M1B" in why

    def test_duplicate_series_name_fails_loud(self):
        t1 = list(EF15_TABLE1)
        t1[I_M1A] = "貨幣總計數-M1B"                          # NFKC 後與 M1B 同名
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(table1=t1))
        assert df is None and "2 個" in why

    def test_measures_follow_table2_labels_not_position(self):
        base, _ = umh._parse_cbc_ef15m01_levels(ef15_body())
        swapped = []
        for r in ef15_rows():
            row = [r[0]]
            for i in range(15):
                row += [r[_yy_col(i)], r[_lv_col(i)]]          # 每組改成 [年增率, 原始值]
            swapped.append(row)
        meta = dict(EF15_META, units="%,新台幣百萬元")              # units 與 Table2 同序
        df, why = umh._parse_cbc_ef15m01_levels(
            ef15_body(swapped, meta=meta, table2=["年增率", "原始值"]))
        assert df is not None, why
        pd.testing.assert_frame_equal(df, base)

    def test_missing_yoy_measure_fails_loud(self):
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(table2=["原始值", "月增率"]))
        assert df is None and "年增率" in why

    def test_value_count_mismatch_fails_loud_and_prints_labels(self, capsys):
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(table1=EF15_TABLE1[:-1]))
        out = capsys.readouterr().out
        assert df is None and "14×2" in why
        assert "Table1=" in out and "Table2=" in out and "貨幣總計數 -Ｍ１Ｂ" in out

    def test_truncated_row_fails_loud(self):
        rows = ef15_rows()
        rows[5] = rows[5][:-1]
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows))
        assert df is None and "15×2" in why

    def test_missing_structure_fails_loud(self):
        body = ef15_body()
        del body["data"]["structure"]
        df, why = umh._parse_cbc_ef15m01_levels(body)
        assert df is None and "Table1" in why

    def test_dash_is_missing_not_zero_and_month_dropped_with_log(self, capsys):
        rows = ef15_rows()
        _row_of(rows, "2025M03")[_lv_col(I_M2)] = "-"
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows))
        out = capsys.readouterr().out
        assert df is not None, why
        assert dt.date(2025, 3, 1) not in set(df["date"])
        assert (df["m1b"] > 0).all() and (df["m2"] > 0).all()           # 沒有被填成 0
        assert len(df) == 2 + 28 + 3 - 1
        assert "剔除 1 個月" in out and "2025-03" in out                  # 顯式印出，不靜默

    def test_dash_official_yoy_only_skips_that_reconcile(self):
        rows = ef15_rows()
        _row_of(rows, "2026M01")[_yy_col(I_M1B)] = "-"
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows))
        assert df is not None, why
        assert dt.date(2026, 1, 1) in set(df["date"])

    def test_unknown_token_fails_loud(self):
        rows = ef15_rows()
        _row_of(rows, "2025M03")[_lv_col(I_M1B)] = "…"
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows))
        assert df is None and "2025M03" in why

    def test_non_integer_level_fails_loud(self):
        rows = ef15_rows()
        _row_of(rows, "2026M07")[_lv_col(I_M1B)] = "30530948.5"
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows))
        assert df is None and "整數" in why

    def test_units_other_than_million_twd_fail_loud(self):
        meta = dict(EF15_META, units="新台幣千元,%")
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(meta=meta))
        assert df is None and "units" in why

    def test_title_without_daily_average_fails_loud(self):
        meta = dict(EF15_META, title="5.貨幣總計數-B.月底數依期間")
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(meta=meta))
        assert df is None and "日平均" in why

    def test_official_yoy_mismatch_fails_loud(self, capsys):
        rows = ef15_rows()
        _row_of(rows, "2026M07")[_yy_col(I_M2)] = "7.44"                # 真值 7.42
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows))
        assert df is None and "對帳不符" in why
        assert "2026-07" in capsys.readouterr().out

    def test_mispaired_level_column_caught_by_reconcile(self):
        """把 M1A 的餘額塞進 M1B 的「原始值」欄（標籤不變）→ 年增率對不上 → 拒用。"""
        rows = ef15_rows()
        for r in rows:
            r[_lv_col(I_M1B)] = r[_lv_col(I_M1A)]
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows))
        assert df is None and "對帳不符" in why

    def test_no_reconcilable_row_fails_loud(self):
        rows = ef15_rows()
        for r in rows:
            r[_yy_col(I_M1B)] = "-"
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows))
        assert df is None and "M1B" in why and "對帳" in why

    def test_tolerance_has_no_false_alarm_on_correctly_rounded_data(self):
        """性質測試：真值任意、餘額取整數百萬元、官方年增率四捨五入到兩位 → 絕不誤報。"""
        rnd = random.Random(20260928)
        worst = 0.0
        for _ in range(20000):
            b_true = rnd.uniform(1.0e6, 8.0e7)
            r_true = rnd.uniform(-0.20, 0.40)
            a_true = b_true * (1 + r_true)
            a, b = round(a_true), round(b_true)
            official = float(_round2(r_true * 100))
            diff = abs((a / b - 1) * 100 - official)
            assert diff <= umh._ef15_yoy_tolerance_pp(a, b), (a, b, official, diff)
            worst = max(worst, diff - 0.005)
        assert worst < 1e-3                         # 捨入項確實很小（但仍逐列計入）

    def test_tolerance_derivation_values(self):
        t = umh._ef15_yoy_tolerance_pp(30530948, 28443215)
        assert 0.005 < t < 0.005 + 1e-5             # 近期量級：幾乎只剩半個最小位數
        t_small = umh._ef15_yoy_tolerance_pp(1282249, 1255199)
        assert 0.005 + 5e-5 < t_small < 0.005 + 1e-4


# ═════════════════════════════════════════════════════════════════════════════
class TestQAGuards:
    """批 R 獨立 QA：7 個突變存活的缺口（MQ1、MQ2、MQ3、MQ4、MQ6、MQ7、MQ10）各補一條守衛。"""

    def test_mq1_duplicate_period_fails_loud(self):
        # ① 一模一樣的重複列：若不檢查，後列會靜默覆蓋前列、對帳照樣通過 —— 最危險的一種
        rows = ef15_rows()
        rows.insert(len(rows) - 1, list(_row_of(rows, "2026M06")))
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows))
        assert df is None and "期間重複" in why and "2026M06" in why
        # ② 期間標錯成前一個月（內容不同）→ 同樣以「重複」拒用，不是靠對帳碰巧擋下
        rows = ef15_rows()
        rows[-1][0] = rows[-2][0]
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows))
        assert df is None and "期間重複" in why

    @pytest.mark.parametrize("period", ["2026M7", "2026M13", "2026M00", "2026-07", "115M07",
                                        "2026 M07", ""])
    def test_mq2_period_format_and_month_range(self, period):
        rows = ef15_rows()
        rows[-1][0] = period
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows))
        assert df is None and "期間" in why, period

    @pytest.mark.parametrize("col,value", [("yoy", "nan"), ("yoy", "NaN"), ("yoy", "inf"),
                                           ("yoy", "-inf"), ("level", "nan"), ("level", "inf")])
    def test_mq3_non_finite_values_fail_loud(self, col, value):
        """官方年增率或餘額是 nan／inf → 在解析那一步就以「非有限」拒用（不能靠後面碰巧擋下）。"""
        rows = ef15_rows()
        rows[-1][_yy_col(I_M2) if col == "yoy" else _lv_col(I_M2)] = value
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows))
        assert df is None and "非有限" in why, (col, value)

    def test_mq3_reconcile_comparison_is_nan_safe(self, monkeypatch):
        """第二道：就算上游解析日後漏了有限檢查而放過 nan，對帳比較也必須判不符。
        nan 與任何數比較都是 False —— 寫成「diff > 容差」會把 nan 靜默算成對帳通過。"""
        real = umh._ef15_cell

        def leaky(v):
            return float("nan") if str(v).strip() == "nan" else real(v)
        monkeypatch.setattr(umh, "_ef15_cell", leaky)
        rows = ef15_rows()
        rows[-1][_yy_col(I_M2)] = "nan"
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows))
        assert df is None and "對帳不符" in why

    @pytest.mark.parametrize("idx,short", [(I_M1B, "M1B"), (I_M2, "M2")])
    def test_mq4_each_series_needs_its_own_reconciled_row(self, idx, short):
        rows = ef15_rows()
        for r in rows:
            r[_yy_col(idx)] = "-"
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows))
        assert df is None and short in why and "對帳" in why

    @pytest.mark.parametrize("m1b,m2", [
        ([3074.89, 3053.09], [702903.31, 702247.62]),        # 只有 m1b 重複換算
        ([307488.57, 305309.48], [70290331.0, 70224762.0]),  # 只有 m2 漏換算
    ])
    def test_mq6_export_band_checks_m1b_and_m2_each(self, m1b, m2):
        """m2 ≥ m1b、gap 正常 → 只剩量級帶攔得住；帶子必須兩欄各自檢查。"""
        ok, msg = E._money_supply_sanity_gate(_ms_df(m1b, m2))
        assert not ok and "量級" in msg

    @pytest.mark.parametrize("units,accepted", [("新台幣百萬元,百分比", False),
                                                ("新台幣百萬元,‰", False),
                                                ("新台幣百萬元,pp", False),
                                                ("新台幣百萬元，％", True)])     # 全形（NFKC）仍算 %
    def test_mq7_yoy_unit_must_be_percent(self, units, accepted):
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(meta=dict(EF15_META, units=units)))
        assert (df is not None) is accepted, (units, why)
        if not accepted:
            assert "units" in why

    @pytest.mark.parametrize("units", ["新台幣百萬元,%,%", "新台幣百萬元", ""])
    def test_mq10_unit_count_must_equal_measure_count(self, units):
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(meta=dict(EF15_META, units=units)))
        assert df is None and "units" in why, units


# ═════════════════════════════════════════════════════════════════════════════
class TestFatalRange:
    """QA 建議 2（總管採納）：只有「致命範圍」＝寫入窗口 ＋ gap 的 t−12 基期內的對帳不符才整表拒用；
    更早的列照樣對帳、只印 ⚠️ —— 它們不影響寫入的資料，而每天增量都重解析全表，
    一筆舊歷史被修訂到不一致就會天天擋住。"""

    @staticmethod
    def _off(rows, per, idx=I_M2, by=0.02):
        r = _row_of(rows, per)
        r[_yy_col(idx)] = f"{float(r[_yy_col(idx)]) + by:.2f}"

    def test_fatal_from_helper_boundaries(self):
        f = umh._ef15_fatal_from
        assert f(dt.date(2006, 10, 3)) == dt.date(2005, 11, 1)    # 第一個寫入月 2006-11 往前 12 個月
        assert f(dt.date(2026, 7, 2)) == dt.date(2025, 8, 1)      # 增量：last=2026-07 → start 07-02
        assert f(dt.date(2026, 7, 1)) == dt.date(2025, 7, 1)      # start 恰為月初 → 當月就寫入
        assert f(dt.date(2026, 12, 15)) == dt.date(2026, 1, 1)    # 跨年

    def test_mismatch_before_fatal_range_warns_and_passes(self, capsys):
        base, _ = umh._parse_cbc_ef15m01_levels(ef15_body())
        rows = ef15_rows()
        self._off(rows, "2025M03")
        capsys.readouterr()
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows), fatal_from=dt.date(2025, 6, 1))
        out = capsys.readouterr().out
        assert df is not None, why
        pd.testing.assert_frame_equal(df, base)                  # 資料照樣產出，一列不少
        assert "⚠️" in out and "只警示" in out and "對帳不符 1 列" in out and "2025-03" in out
        assert "max|Δ|=" in out
        # 同一份表不給 fatal_from（＝全表致命）→ 拒用：證明放行靠的是範圍，不是容差變寬
        assert umh._parse_cbc_ef15m01_levels(ef15_body(rows))[0] is None

    @pytest.mark.parametrize("per", ["2025M06", "2026M07"])      # 邊界月（= fatal_from）與最新月
    def test_mismatch_inside_fatal_range_rejects(self, per):
        rows = ef15_rows()
        self._off(rows, per)
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows), fatal_from=dt.date(2025, 6, 1))
        assert df is None and "對帳不符" in why and "致命範圍" in why, per

    def test_fatal_range_needs_a_reconciled_row_for_each_series(self):
        rows = ef15_rows()
        for r in rows:
            if r[0] >= "2026M05":
                r[_yy_col(I_M2)] = "-"                          # 致命範圍內 M2 沒有官方年增率
        df, why = umh._parse_cbc_ef15m01_levels(ef15_body(rows), fatal_from=dt.date(2026, 5, 1))
        assert df is None and "M2" in why and "致命範圍" in why
        # 同一份表、致命範圍放寬到 2025-06 → M2 有可對帳列 → 放行（證明擋下的原因是範圍內無可對帳列）
        assert umh._parse_cbc_ef15m01_levels(ef15_body(rows),
                                             fatal_from=dt.date(2025, 6, 1))[0] is not None

    def test_fetch_derives_fatal_range_from_start(self, monkeypatch, capsys):
        start, end = dt.date(2026, 2, 1), dt.date(2026, 9, 28)   # 致命範圍 ≥ 2025-02
        # ① 範圍前（2025-01）不符 → 照樣寫出 2026-02～07，並印 ⚠️
        rows = ef15_rows()
        self._off(rows, "2025M01")
        patch_ef15(monkeypatch, ef15_body(rows))
        df = umh.fetch_finmind_m1m2(start, end, "")
        out = capsys.readouterr().out
        assert len(df) == 6 and "只警示" in out and "2025-01" in out   # 不符的月份必須被點名
        # ② 2025-02 是第一個寫入月（2026-02）gap 的 t−12 基期 → 屬致命範圍 → 整表拒用
        rows = ef15_rows()
        self._off(rows, "2025M02")
        patch_ef15(monkeypatch, ef15_body(rows))
        assert umh.fetch_finmind_m1m2(start, end, "").empty


# ═════════════════════════════════════════════════════════════════════════════
class TestFetchEF15:
    def test_requests_ef15_exactly_once_and_never_ef19_ef21(self, monkeypatch):
        calls = patch_ef15(monkeypatch, ef15_body())
        df = _fetch_all()
        assert not df.empty
        assert calls == ["EF15M01"]

    def test_tier1_ms1_success_skips_ef15(self, monkeypatch):
        n = 26
        ms1 = [{"年月": f"{2023 + k // 12}-{k % 12 + 1:02d}",
                "M1B": 20_000_000 + 100_000 * k, "M2": 60_000_000 + 200_000 * k}
               for k in range(n)]
        calls = patch_ef15(monkeypatch, ef15_body(), ms1_rows=ms1)
        df = _fetch_all()
        assert calls == [] and not df.empty
        assert (df["source"] == "CBC:ms1.json").all()

    def test_output_levels_source_and_2026_07_gap(self, monkeypatch):
        patch_ef15(monkeypatch, ef15_body())
        df = _fetch_all().set_index("date")
        src = df["source"].iloc[0]
        assert src.startswith("CBC:PXWeb:EF15M01:daily_avg_level[") and "level" in src
        assert "M1B label=貨幣總計數-M1B" in src and "M2 label=貨幣總計數-M2" in src
        # 驗算：官方 gap = 7.34 − 7.42 = −0.08pp；自算值落在兩個序列的捨入容差和之內
        syn = _synthetic_levels()
        tol = (umh._ef15_yoy_tolerance_pp(30530948, syn[I_M1B][(2025, 7)])
               + umh._ef15_yoy_tolerance_pp(70224762, syn[I_M2][(2025, 7)]))
        assert abs(df.loc[dt.date(2026, 7, 1), "m1b_m2_gap"] - (7.34 - 7.42)) <= tol
        assert df.loc[dt.date(2026, 7, 1), "m1b"] == 30530948      # 單位：新台幣百萬元（原值）
        assert df.loc[dt.date(2026, 7, 1), "m2"] == 70224762

    def test_gap_uses_same_month_last_year_when_a_month_is_dropped(self, monkeypatch):
        rows = ef15_rows()
        _row_of(rows, "2025M03")[_lv_col(I_M2)] = "-"
        patch_ef15(monkeypatch, ef15_body(rows))
        df = _fetch_all().set_index("date")
        assert pd.isna(df.loc[dt.date(2026, 3, 1), "m1b_m2_gap"])   # t−12 被剔除 → NaN，不錯配 t−13
        syn = _synthetic_levels()
        exp = ((syn[I_M1B][(2026, 4)] / syn[I_M1B][(2025, 4)] - 1) * 100
               - (syn[I_M2][(2026, 4)] / syn[I_M2][(2025, 4)] - 1) * 100)
        assert df.loc[dt.date(2026, 4, 1), "m1b_m2_gap"] == pytest.approx(exp, abs=1e-12)

    def test_gap_bitwise_equal_to_positional_shift_when_contiguous(self, monkeypatch):
        n = 40
        periods = [_p(*_shift(2020, 1, k)) for k in range(n)]
        m1b = [round(9_000_000 * 1.007 ** k) for k in range(n)]
        m2 = [round(25_000_000 * 1.005 ** k) for k in range(n)]
        patch_ef15(monkeypatch, ef15_body_from_levels(periods, m1b, m2))
        got = _fetch_all()["m1b_m2_gap"].to_numpy()
        s1, s2 = pd.Series(m1b), pd.Series(m2)
        exp = ((s1 / s1.shift(12) - 1) * 100 - (s2 / s2.shift(12) - 1) * 100).to_numpy()
        assert pd.isna(got[:12]).all() and pd.isna(exp[:12]).all()
        assert (got[12:] == exp[12:]).all()                          # 逐位相同，不是近似

    def test_output_schema_matches_committed_parquet(self, monkeypatch, tmp_path):
        if not _REPO_M1M2.exists():
            pytest.skip("repo 無 finmind_m1m2.parquet")
        patch_ef15(monkeypatch, ef15_body())
        df = _fetch_all()
        p = tmp_path / "x.parquet"
        df.to_parquet(p, compression="snappy", index=False)
        new, old = pq.read_schema(p), pq.read_schema(_REPO_M1M2)
        assert new.names == old.names == ["date", "m1b", "m2", "m1b_m2_gap",
                                          "source", "fetched_at"]
        for name in ("date", "m1b", "m2", "m1b_m2_gap"):
            assert new.field(name).type == old.field(name).type, name
        assert str(new.field("date").type) == "date32[day]"
        assert str(new.field("m1b").type) == str(new.field("m2").type) == "int64"
        assert pd.read_parquet(p).dtypes.to_dict() == pd.read_parquet(_REPO_M1M2).dtypes.to_dict()


# ═════════════════════════════════════════════════════════════════════════════
def _flow_like(df: pd.DataFrame) -> pd.DataFrame:
    """把合格的存量表改造成「月變動額」形狀（原本那個錯誤）—— 供 repo 檔已重建為好檔時使用。"""
    bad = df.copy()
    for c in ("m1b", "m2"):
        flow = bad[c].diff()
        flow.iloc[0] = -1                     # 第一個月沒有「上月」→ 直接給一個負值（流量會變號）
        bad[c] = flow.astype("int64")
    return bad


class TestUpdateOneRebuild:
    def _bad_existing(self, tmp_path) -> Path:
        """優先用 repo 裡現有的壞檔；若它已被排程重建成好檔，就把好檔改造成原本那種壞檔。"""
        if not _REPO_M1M2.exists():
            pytest.skip("repo 無 finmind_m1m2.parquet")
        dst = tmp_path / "finmind_m1m2.parquet"
        repo_df = pd.read_parquet(_REPO_M1M2)
        if umh._m1m2_level_sanity(repo_df)[0]:
            _flow_like(repo_df).to_parquet(dst, compression="snappy", index=False)
        else:
            shutil.copyfile(_REPO_M1M2, dst)
        assert umh._m1m2_level_sanity(pd.read_parquet(dst))[0] is False
        return dst

    def test_repo_bad_file_rebuilt_in_full_and_passes_sanity(self, monkeypatch, tmp_path):
        repo_sha = _sha(_REPO_M1M2) if _REPO_M1M2.exists() else None
        dst = self._bad_existing(tmp_path)
        old_schema = pq.read_schema(dst)
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        calls = patch_ef15(monkeypatch, ef15_body())
        today = dt.date(2026, 9, 28)
        meta = umh.update_one("finmind_m1m2", today, False, 20, "tok")
        assert calls == ["EF15M01"]
        assert meta["last_error"] is None and meta["last_updated"] == "2026-07-01"
        new = pd.read_parquet(dst)
        ok, msg = umh._m1m2_level_sanity(new)
        assert ok, msg
        # 整段取代：壞檔的列一列不留，全部來自 EF15M01；窗口 = today − 20×365 天起
        assert new["source"].str.startswith("CBC:PXWeb:EF15M01:daily_avg_level").all()
        start = today - dt.timedelta(days=20 * 365)
        assert min(new["date"]) >= start and len(new) == 28 + 3
        assert meta["row_count"] == len(new)
        # schema（欄名、型別）與既有檔相同；兩個 provenance 字串欄只要求是字串型別
        # （string／large_string 取決於寫檔當下的 pandas 主版本，不是本批可控的 schema）
        s = pq.read_schema(dst)
        assert s.names == old_schema.names
        for n in ("date", "m1b", "m2", "m1b_m2_gap"):
            assert s.field(n).type == old_schema.field(n).type, n
        for n in ("source", "fetched_at"):
            assert pa.types.is_string(s.field(n).type) or pa.types.is_large_string(s.field(n).type)
        assert new.dtypes.to_dict() == pd.read_parquet(_REPO_M1M2).dtypes.to_dict()
        # 絕不寫到 repo 的 data_cache/
        if repo_sha is not None:
            assert _sha(_REPO_M1M2) == repo_sha

    def test_next_day_increment_appends_and_keeps_int64(self, monkeypatch, tmp_path):
        self._bad_existing(tmp_path)
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        patch_ef15(monkeypatch, ef15_body())
        umh.update_one("finmind_m1m2", dt.date(2026, 9, 28), False, 20, "tok")
        first = pd.read_parquet(tmp_path / "finmind_m1m2.parquet")
        # 隔月 CBC 發布 2026-08：以同一成長率延伸一列（官方年增率由餘額自算、兩位四捨五入）
        rows = ef15_rows()
        last = rows[-1]
        syn = _synthetic_levels()
        new_row = ["2026M08"]
        for i in range(15):
            if last[_lv_col(i)] == "-":
                new_row += ["-", "-"]
                continue
            a = round(int(last[_lv_col(i)]) * _GROWTH[i])
            b = syn[i][(2025, 8)]
            new_row += [str(a), _round2((a / b - 1) * 100)]
        patch_ef15(monkeypatch, ef15_body(rows + [new_row]))
        meta = umh.update_one("finmind_m1m2", dt.date(2026, 10, 28), False, 20, "tok")
        after = pd.read_parquet(tmp_path / "finmind_m1m2.parquet")
        assert meta["last_error"] is None and meta["last_updated"] == "2026-08-01"
        assert len(after) == len(first) + 1
        assert after.dtypes.to_dict() == first.dtypes.to_dict()
        assert str(after["m1b"].dtype) == "int64"
        assert umh._m1m2_level_sanity(after)[0]


# ═════════════════════════════════════════════════════════════════════════════
def _ms_df(m1b, m2, gap=0.5):
    return pd.DataFrame({"date": ["2026-06-01", "2026-07-01"], "m1b": m1b, "m2": m2,
                         "m1b_m2_gap": [gap, gap]})


class TestExportMoneySupplyUnit:
    """stock.db `money_supply` 對下游承諾億元：parquet（百萬元）必須 ÷100 才外送，且守門擋單位錯。"""

    def test_gate_accepts_yi_values(self):
        ok, msg = E._money_supply_sanity_gate(_ms_df([307488.57, 305309.48],
                                                     [702903.31, 702247.62]))
        assert ok, msg

    def test_gate_rejects_unconverted_million_values(self):
        ok, msg = E._money_supply_sanity_gate(_ms_df([30748857, 30530948],
                                                     [70290331, 70224762]))
        assert not ok and "量級" in msg

    def test_gate_rejects_double_converted_values(self):
        ok, msg = E._money_supply_sanity_gate(_ms_df([3074.89, 3053.09], [7029.03, 7022.48]))
        assert not ok and "量級" in msg

    def test_write_money_supply_divides_by_100(self, monkeypatch, tmp_path):
        patch_ef15(monkeypatch, ef15_body())
        src = _fetch_all()
        src.to_parquet(tmp_path / "finmind_m1m2.parquet", compression="snappy", index=False)
        monkeypatch.setattr(E, "_DATA_CACHE", tmp_path)
        conn = sqlite3.connect(":memory:")
        n = E.write_money_supply(conn)
        got = pd.read_sql("SELECT * FROM money_supply", conn)
        conn.close()
        assert n == len(src) == len(got)
        assert list(got.columns) == ["date", "m1b", "m2", "m1b_m2_gap"]
        assert (got["m1b"].to_numpy() == src["m1b"].to_numpy() / 100).all()
        assert (got["m2"].to_numpy() == src["m2"].to_numpy() / 100).all()
        row = got.set_index("date").loc["2026-07-01"]
        assert row["m2"] == pytest.approx(702247.62) and row["m1b"] == pytest.approx(305309.48)
        pd.testing.assert_series_equal(got["m1b_m2_gap"], src["m1b_m2_gap"].reset_index(drop=True),
                                       check_names=False)          # gap（pp）不換算

    def test_write_money_supply_skips_bad_parquet(self, monkeypatch, tmp_path):
        if not _REPO_M1M2.exists():
            pytest.skip("repo 無 finmind_m1m2.parquet")
        TestUpdateOneRebuild()._bad_existing(tmp_path)
        monkeypatch.setattr(E, "_DATA_CACHE", tmp_path)
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE money_supply (x)")               # 舊殘留表也要被移除
        assert E.write_money_supply(conn) == -1
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
        conn.close()
        assert "money_supply" not in tables
