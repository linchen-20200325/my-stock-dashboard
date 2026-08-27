"""tests/test_b3_margin_schema.py — B3 融資餘額口徑 SSOT（v19.179）。

事故回顧
========
`data_cache/finmind_margin.parquet` 的 `margin_balance` 是「元 / 張」雙峰混口徑：
FinMind `TaiwanStockTotalMarginPurchaseShortSale` 是**彙總版長格式**（一天多列、
靠 `name` 分口徑），但 `scripts/update_macro_history.py` 的欄位偵測是照**個股版
寬格式**寫的 → 把所有 name 列一起拿 → `_merge_dedupe` 的
`drop_duplicates(keep="last")` 隨機留一列。

本檔釘住三件事：
1. `shared/margin_schema.py`（L0 SSOT）選列/選欄/單位/sanity 的行為
2. cron（`scripts/update_macro_history.py`）與即時路徑
   （`src/data/daily/daily_data_fetchers.py`）吃**同一份**規則（物件同一性 + AST 守衛）
3. sanity 不合格時 `scripts/export_stock_db.py` **略過整表**（不外送下游）

⚠️ 原始碼守衛一律走 **AST**（排除 docstring / 註解），失敗訊息印出該行原文。
"""

from __future__ import annotations

import ast
import sqlite3
import sys
from pathlib import Path
from unittest import mock

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "scripts"))

from shared.margin_schema import (  # noqa: E402
    MARGIN_BALANCE_SANITY_MAX_YI,
    MARGIN_BALANCE_SANITY_MIN_YI,
    MARGIN_DATASET,
    MARGIN_MONEY_ROW_NAME,
    MARGIN_VOLUME_ROW_NAME,
    MARGIN_WIDE_TODAY_BALANCE_COLS,
    TWD_PER_YI,
    extract_margin_money_series,
    is_margin_money_row,
    is_today_balance_col,
    margin_money_to_yi,
    margin_row_source,
    margin_sanity_ok,
    margin_twd_sanity_mask,
    pick_today_balance_cols,
)

# 2026-08 production 真值（scripts/_out/margin_units_report.txt §3 佐證）
MONEY_TWD = 619_648_244_000        # MarginPurchaseMoney，單位 元 → 6,196.5 億
MONEY_TWD_2 = 631_344_856_000      # 另一日
VOLUME_LOTS = 9_614_955            # MarginPurchaseVolume，單位 張（**不是**金額）


# ═══════════════════════════════════════════════════════════════
# 1. 長格式：只取 Money 列 + 只取 TodayBalance 欄
# ═══════════════════════════════════════════════════════════════
def _long_raw() -> pd.DataFrame:
    """彙總版長格式：一天 4 列（融資金額 / 融資張數 / 融券金額 / 融券張數）。

    欄位含 `YesBalance`（昨日）— 取到它會讓整條序列日期錯位一天（§2.3 PIT）。
    """
    rows = []
    for d, money in (("2026-08-04", MONEY_TWD), ("2026-08-05", MONEY_TWD_2)):
        rows += [
            {"date": d, "name": MARGIN_MONEY_ROW_NAME,
             "TodayBalance": money, "YesBalance": money - 1_000_000_000,
             "buy": 1, "sell": 2},
            {"date": d, "name": MARGIN_VOLUME_ROW_NAME,
             "TodayBalance": VOLUME_LOTS, "YesBalance": VOLUME_LOTS - 10_000,
             "buy": 1, "sell": 2},
            {"date": d, "name": "ShortSaleMoney",
             "TodayBalance": 12_345_678_000, "YesBalance": 12_000_000_000,
             "buy": 1, "sell": 2},
            {"date": d, "name": "ShortSaleVolume",
             "TodayBalance": 543_210, "YesBalance": 540_000, "buy": 1, "sell": 2},
        ]
    return pd.DataFrame(rows)


def test_long_format_picks_money_row_and_today_balance():
    out, meta = extract_margin_money_series(_long_raw())
    assert meta["format"] == "long"
    assert meta["balance_col"] == "TodayBalance", (
        f"必須取當日欄，不可取昨日欄；實際={meta['balance_col']}")
    assert len(out) == 2, "一天只該留一列（Money 列）"
    assert list(out["margin_balance"]) == [float(MONEY_TWD), float(MONEY_TWD_2)]
    assert meta["n_money_rows"] == 2
    assert meta["n_dup_dates"] == 0


def test_long_format_volume_row_never_selected():
    """混入 Volume 列（張）→ 斷言**不會**被選中（事故本體）。"""
    out, _meta = extract_margin_money_series(_long_raw())
    assert float(VOLUME_LOTS) not in set(out["margin_balance"]), (
        "MarginPurchaseVolume（張）被當成金額寫入 = B3 事故重現")
    # 全列都在「元」的量級（÷1e8 ∈ sanity 區間）
    assert bool(margin_twd_sanity_mask(out["margin_balance"]).all())


def test_long_format_yesterday_column_never_selected():
    """只留 Yes* 欄（無當日欄）→ 寧可回空,也不拿昨日值頂替（§2.3 PIT / §1）。"""
    raw = _long_raw().drop(columns=["TodayBalance"])
    out, meta = extract_margin_money_series(raw)
    assert out.empty
    assert "當日餘額" in (meta["reason"] or "")


def test_long_format_row_level_provenance():
    """§2.2：source 記到列級（dataset:name:欄），事後分得出 Money vs Volume。"""
    out, _meta = extract_margin_money_series(_long_raw())
    expect = margin_row_source(MARGIN_MONEY_ROW_NAME, "TodayBalance")
    assert set(out["source"]) == {expect}
    assert MARGIN_DATASET in expect and MARGIN_MONEY_ROW_NAME in expect
    assert "TodayBalance" in expect


def test_long_format_no_money_row_returns_empty_not_guess():
    """整組只有 Volume 列 → 回空 + 說明原因，**不**退而求其次拿張數（§1）。"""
    raw = _long_raw()
    raw = raw[raw["name"] != MARGIN_MONEY_ROW_NAME].reset_index(drop=True)
    out, meta = extract_margin_money_series(raw)
    assert out.empty
    assert MARGIN_MONEY_ROW_NAME in (meta["reason"] or "")


def test_chinese_name_variant_accepted():
    raw = _long_raw()
    raw.loc[raw["name"] == MARGIN_MONEY_ROW_NAME, "name"] = "融資金額"
    out, _meta = extract_margin_money_series(raw)
    assert len(out) == 2


@pytest.mark.parametrize("name,expected", [
    ("MarginPurchaseMoney", True),
    ("margin_purchase_money", True),
    ("融資金額", True),
    ("MarginPurchaseVolume", False),     # 張 — 事故元凶
    ("ShortSaleMoney", False),           # 融券金額
    ("ShortSaleVolume", False),
    ("MarginPurchaseTodayBalance", False),   # 寬格式欄名誤入 name 欄
    ("", False),
    (None, False),
])
def test_is_margin_money_row_truth_table(name, expected):
    assert is_margin_money_row(name) is expected


@pytest.mark.parametrize("col,expected", [
    ("TodayBalance", True),
    ("MarginPurchaseTodayBalance", True),
    ("融資餘額", True),
    ("YesBalance", False),               # 昨日 → 日期錯位
    ("YesterdayBalance", False),
    ("yesBalance", False),
    ("buy", False),
])
def test_is_today_balance_col_truth_table(col, expected):
    assert is_today_balance_col(col) is expected


# ═══════════════════════════════════════════════════════════════
# 2. 寬格式（個股樣式）向後相容
# ═══════════════════════════════════════════════════════════════
@pytest.mark.parametrize("col", list(MARGIN_WIDE_TODAY_BALANCE_COLS))
def test_wide_format_backward_compatible(col):
    raw = pd.DataFrame([
        {"date": "2026-08-04", col: MONEY_TWD, "MarginPurchaseYesterdayBalance": 1},
        {"date": "2026-08-05", col: MONEY_TWD_2, "MarginPurchaseYesterdayBalance": 1},
    ])
    out, meta = extract_margin_money_series(raw)
    assert meta["format"] == "wide"
    assert meta["balance_col"] == col
    assert list(out["margin_balance"]) == [float(MONEY_TWD), float(MONEY_TWD_2)]
    assert MARGIN_DATASET in out["source"].iloc[0]


def test_wide_format_refuses_loose_balance_fallback():
    """舊碼的 `next(c for c in cols if "Balance" in c)` 寬鬆 fallback 已移除：
    只有昨日欄時應回空，而不是抓一個看起來像餘額的欄硬上。"""
    raw = pd.DataFrame([{"date": "2026-08-04", "MarginPurchaseYesterdayBalance": MONEY_TWD}])
    out, meta = extract_margin_money_series(raw)
    assert out.empty
    assert "寬格式" in (meta["reason"] or "")


# ═══════════════════════════════════════════════════════════════
# 3. 單位換算 + §3.2 sanity
# ═══════════════════════════════════════════════════════════════
def test_margin_money_to_yi_production_golden():
    assert margin_money_to_yi(MONEY_TWD) == pytest.approx(6196.5)


@pytest.mark.parametrize("bad", [VOLUME_LOTS, 6.19e8, 0, -100, None, float("nan"), "x"])
def test_margin_money_to_yi_rejects(bad):
    assert margin_money_to_yi(bad) is None


def test_margin_sanity_bounds_are_open_interval():
    assert margin_sanity_ok(2800.0) and margin_sanity_ok(1100.0)
    assert not margin_sanity_ok(MARGIN_BALANCE_SANITY_MIN_YI)
    assert not margin_sanity_ok(MARGIN_BALANCE_SANITY_MAX_YI)


def test_margin_twd_sanity_mask_flags_volume_rows():
    s = pd.Series([MONEY_TWD, VOLUME_LOTS, None, 0])
    assert list(margin_twd_sanity_mask(s)) == [True, False, False, False]


def test_extract_does_not_apply_sanity_itself():
    """抽取只負責『選對列與欄』；sanity 政策留給呼叫端（cron raise / export 略過）。"""
    raw = pd.DataFrame([
        {"date": "2026-08-04", "name": MARGIN_MONEY_ROW_NAME, "TodayBalance": 123},
    ])
    out, _meta = extract_margin_money_series(raw)
    assert len(out) == 1 and out["margin_balance"].iloc[0] == 123.0


def test_empty_and_missing_date_inputs():
    for raw in (None, pd.DataFrame(), pd.DataFrame([{"name": "x", "TodayBalance": 1}])):
        out, meta = extract_margin_money_series(raw)
        assert out.empty and meta["reason"]


# ═══════════════════════════════════════════════════════════════
# 4. cron fetcher：sanity 不合格 → 不寫入（raise，由 update_one 接住）
# ═══════════════════════════════════════════════════════════════
def _patch_finmind(monkeypatch, raw: pd.DataFrame):
    from scripts import update_macro_history as umh
    monkeypatch.setattr(umh, "_finmind_get", lambda *a, **k: raw)
    return umh


def test_cron_fetch_margin_happy_path(monkeypatch):
    import datetime as dt
    umh = _patch_finmind(monkeypatch, _long_raw())
    out = umh.fetch_finmind_margin(dt.date(2026, 8, 1), dt.date(2026, 8, 5), "tok")
    assert list(out.columns) == ["date", "margin_balance", "source", "fetched_at"]
    assert len(out) == 2
    assert list(out["margin_balance"]) == [float(MONEY_TWD), float(MONEY_TWD_2)]
    assert out["date"].iloc[0] == dt.date(2026, 8, 4)
    assert MARGIN_MONEY_ROW_NAME in out["source"].iloc[0]
    assert "TodayBalance" in out["source"].iloc[0]


def test_cron_fetch_margin_raises_on_sanity_violation(monkeypatch):
    """混入單位漂移的列 → raise（`update_one` 記 last_error 且**不寫 parquet**）。"""
    import datetime as dt
    raw = _long_raw()
    # 模擬上游把 Money 列改成「仟元」→ ÷1e8 只剩 6.19 億，遠低於下限
    # （用 int 避免 int64 欄位被塞 float 觸發 pandas 型別轉換警告）
    raw.loc[(raw["name"] == MARGIN_MONEY_ROW_NAME) & (raw["date"] == "2026-08-05"),
            "TodayBalance"] = 619_000_000
    umh = _patch_finmind(monkeypatch, raw)
    with pytest.raises(RuntimeError, match="sanity"):
        umh.fetch_finmind_margin(dt.date(2026, 8, 1), dt.date(2026, 8, 5), "tok")


def test_cron_update_one_does_not_write_when_fetcher_raises(monkeypatch, tmp_path):
    """整合：fetcher raise → update_one 記 last_error、**完全不碰 parquet**。"""
    import datetime as dt
    from scripts import update_macro_history as umh

    def _boom(*_a, **_k):
        raise RuntimeError("融資餘額 sanity 失敗：測試")

    monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(umh, "FETCHERS",
                        {**umh.FETCHERS, "finmind_margin": (_boom, True)})
    meta = umh.update_one("finmind_margin", dt.date(2026, 8, 5), True, 1, "tok")
    assert "sanity" in (meta["last_error"] or "")
    assert not (tmp_path / "finmind_margin.parquet").exists()


def test_cron_fetch_margin_empty_upstream_returns_empty(monkeypatch):
    import datetime as dt
    umh = _patch_finmind(monkeypatch, pd.DataFrame())
    assert umh.fetch_finmind_margin(dt.date(2026, 8, 1), dt.date(2026, 8, 5), "t").empty


# ═══════════════════════════════════════════════════════════════
# 5. export gate：不合格 → 略過整表 + 警示（不外送下游）
# ═══════════════════════════════════════════════════════════════
def _dirty_parquet_df() -> pd.DataFrame:
    """現況 parquet 的縮影：元 / 張 混在同一欄。"""
    return pd.DataFrame({
        "date": ["2026-08-03", "2026-08-04", "2026-08-05"],
        "margin_balance": [MONEY_TWD, VOLUME_LOTS, MONEY_TWD_2],
    })


def _clean_parquet_df() -> pd.DataFrame:
    return pd.DataFrame({
        "date": ["2026-08-04", "2026-08-05"],
        "margin_balance": [MONEY_TWD, MONEY_TWD_2],
    })


def test_export_margin_gate_rejects_mixed_caliber():
    import export_stock_db as E
    ok, msg = E._margin_sanity_gate(_dirty_parquet_df())
    assert ok is False
    assert "1/3" in msg and "混口徑" in msg


def test_export_margin_gate_accepts_clean():
    import export_stock_db as E
    ok, msg = E._margin_sanity_gate(_clean_parquet_df())
    assert ok is True and "通過" in msg


@pytest.mark.parametrize("df", [
    pd.DataFrame(),
    pd.DataFrame({"date": ["2026-08-04"]}),
    pd.DataFrame({"date": ["2026-08-04"], "margin_balance": [None]}),
])
def test_export_margin_gate_rejects_degenerate(df):
    import export_stock_db as E
    assert E._margin_sanity_gate(df)[0] is False


def test_export_write_margin_skips_table_when_dirty(capsys):
    """§1：略過整表 + 明確警告；不靜默寫入、不寫 NaN、不自行換算補救。"""
    import export_stock_db as E
    conn = sqlite3.connect(":memory:")
    try:
        with mock.patch.object(E, "_read_cache_parquet", return_value=_dirty_parquet_df()):
            n = E.write_margin(conn)
        assert n == -1, "髒序列必須回 -1（source_health 記 absent）"
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "margin" not in tables, "髒序列不得落地 margin 表"
    finally:
        conn.close()
    assert "略過 margin" in capsys.readouterr().err


def test_export_write_margin_drops_stale_table(capsys):
    """本機 / NAS 長存 db：上次的好資料不可在 source_health=absent 時殘留。"""
    import export_stock_db as E
    conn = sqlite3.connect(":memory:")
    try:
        _clean_parquet_df().to_sql("margin", conn, if_exists="replace", index=False)
        with mock.patch.object(E, "_read_cache_parquet", return_value=_dirty_parquet_df()):
            assert E.write_margin(conn) == -1
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "margin" not in tables
    finally:
        conn.close()
    capsys.readouterr()


def test_export_write_margin_writes_when_clean():
    import export_stock_db as E
    conn = sqlite3.connect(":memory:")
    try:
        with mock.patch.object(E, "_read_cache_parquet", return_value=_clean_parquet_df()):
            n = E.write_margin(conn)
        assert n == 2
        rows = conn.execute("SELECT margin_balance FROM margin ORDER BY date").fetchall()
        assert [r[0] for r in rows] == [MONEY_TWD, MONEY_TWD_2]
    finally:
        conn.close()


def test_export_margin_absent_marked_in_source_health():
    """回 -1 → source_health 該維 status=absent（下游看得見『少一張表』）。"""
    import export_stock_db as E
    # 2026-08-27：as_of 改吃 {field: 資料日期|None}（不再是單一匯出日戳記）。
    h = E._health_rows({"margin": -1, "market_index": 100},
                       {"margin": None, "market_index": "2026-08-06"})
    row = h[h["field"] == "margin"].iloc[0]
    assert row["status"] == E._HEALTH_ABSENT and row["n_rows"] == 0


# ═══════════════════════════════════════════════════════════════
# 6. 兩邊實作一致（物件同一性 + AST 守衛，非字串掃描）
# ═══════════════════════════════════════════════════════════════
def _src_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _iter_nodes_skipping_docstrings(tree: ast.AST):
    """走訪 AST，**跳過** Module / FunctionDef / ClassDef 的 docstring 節點。

    註解本來就不進 AST，因此只需排除 docstring，即可保證守衛看的是**可執行碼**。
    """
    docstring_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docstring_nodes.add(id(body[0].value))
    for node in ast.walk(tree):
        if id(node) in docstring_nodes:
            continue
        yield node


def _imported_names_from(tree: ast.AST, module: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            names |= {a.name for a in node.names}
    return names


def test_daily_fetcher_and_shared_share_same_function_objects():
    """即時路徑用的判定函式 = L0 SSOT 的**同一個物件**（不是複製一份）。"""
    from src.data.daily import daily_data_fetchers as D
    import shared.margin_schema as M
    assert D.is_margin_money_row is M.is_margin_money_row
    assert D.pick_today_balance_cols is M.pick_today_balance_cols
    assert D.margin_sanity_ok is M.margin_sanity_ok
    assert D.margin_money_to_yi is M.margin_money_to_yi
    assert D.MARGIN_WIDE_TODAY_BALANCE_COLS is M.MARGIN_WIDE_TODAY_BALANCE_COLS
    # 既有 backward-compat 別名仍等價（tests/test_review_fixes_v19_74.py 依賴）
    assert D._margin_sanity_ok(2800.0) is True
    assert D._finmind_margin_to_yi(MONEY_TWD) == pytest.approx(6196.5)


@pytest.mark.parametrize("rel", [
    "src/data/daily/daily_data_fetchers.py",
    "scripts/update_macro_history.py",
    "scripts/export_stock_db.py",
])
def test_all_three_consumers_import_the_ssot(rel):
    path = _REPO / rel
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = _imported_names_from(tree, "shared.margin_schema")
    assert names, (
        f"{rel} 未 import shared.margin_schema（融資口徑 SSOT）— "
        "規則若各寫一份，B3 事故必復發")


def test_cron_fetcher_has_no_inline_column_detection():
    """AST 守衛：cron `fetch_finmind_margin` 內不得再出現寬鬆欄位偵測字面值。

    只看**可執行碼**的字串常數（docstring 已排除、註解本就不在 AST），
    失敗時印出該行原文。
    """
    path = _REPO / "scripts/update_macro_history.py"
    lines = _src_lines(path)
    tree = ast.parse("\n".join(lines), filename=str(path))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "fetch_finmind_margin"), None)
    assert fn is not None, "找不到 fetch_finmind_margin"

    banned = {"Balance", "MarginPurchase", "Today"}
    offenders = []
    for node in _iter_nodes_skipping_docstrings(fn):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and node.value in banned:
            ln = getattr(node, "lineno", 0)
            raw = lines[ln - 1] if 0 < ln <= len(lines) else "<?>"
            offenders.append(f"{path.name}:{ln}: {raw.strip()}")
    assert not offenders, (
        "欄位偵測應全數走 shared.margin_schema，不得在 cron 內硬寫欄名片段：\n"
        + "\n".join(offenders))


def test_cron_fetcher_calls_extract_and_sanity():
    """AST 守衛：cron 確實呼叫 SSOT 抽取 + sanity，且 sanity 失敗會 raise。"""
    path = _REPO / "scripts/update_macro_history.py"
    lines = _src_lines(path)
    tree = ast.parse("\n".join(lines), filename=str(path))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "fetch_finmind_margin")
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "extract_margin_money_series" in called, f"實際呼叫={sorted(called)}"
    assert "margin_twd_sanity_mask" in called, f"實際呼叫={sorted(called)}"
    assert any(isinstance(n, ast.Raise) for n in ast.walk(fn)), \
        "sanity 失敗必須 raise（由 update_one 接住 → 不寫 parquet）"


def test_export_write_margin_gates_before_to_sql():
    """AST 守衛：`write_margin` 必須先過 gate 才 to_sql（不得無條件寫入）。"""
    path = _REPO / "scripts/export_stock_db.py"
    lines = _src_lines(path)
    tree = ast.parse("\n".join(lines), filename=str(path))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "write_margin")
    calls = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                calls.append((f.lineno, f.id))
            elif isinstance(f, ast.Attribute):
                calls.append((f.lineno, f.attr))
    gate_ln = next((ln for ln, name in calls if name == "_margin_sanity_gate"), None)
    sql_ln = next((ln for ln, name in calls if name == "to_sql"), None)
    assert gate_ln is not None, (
        f"write_margin 未呼叫 _margin_sanity_gate：\n"
        + "\n".join(lines[fn.lineno - 1:fn.end_lineno]))
    assert sql_ln is not None and gate_ln < sql_ln, (
        f"gate 必須在 to_sql 之前；gate@{gate_ln} to_sql@{sql_ln}\n"
        f"{lines[sql_ln - 1].strip()}")


def test_ssot_unit_constant_matches_yi():
    """單位常數不可漂移：1 億 = 1e8 元（§4.1）。"""
    assert TWD_PER_YI == 1e8
    assert margin_money_to_yi(MONEY_TWD) == pytest.approx(MONEY_TWD / TWD_PER_YI, abs=0.05)
    assert pick_today_balance_cols(["TodayBalance", "YesBalance", "buy"]) == ["TodayBalance"]
