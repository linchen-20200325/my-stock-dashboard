"""C-OB-GX2-CONTRACT-TESTS-1 — 持股上游剔除點「已知缺口」證據測試（tests-only；離線；決定性）。

授權：Issue #1199 總管裁示 https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7052927599
（裁示一，G-X2：docs＋tests-only）。配套文件：
docs/vnext/ONEBRAIN_UPSTREAM_EXCLUSION_POINTS_CONTRACT_EVIDENCE_2026-11-21.md 。

═══ ⚠️ 必讀：本檔是「現況行為釘住」＋「期望改善的 xfail」，不是規範 ═══════════════════
- `test_current_behavior_*` 釘的是**目前真實行為**，其中包含**已知不足**（上游靜默剔除、無計數）。
  它們是缺口**證據**，**不是**「這樣才對」。**不得**被引用來阻止日後經正式 Decision Gate 批准的改善；
  改善落地時，這些測試轉紅是**預期的**，須在同一個被批准的 PR 內顯式更新（不是被悄悄洗掉）。
- `test_desired_*` 以 `xfail(strict=True)` 表達「尚未實現的期望」（📌 C-OB-GX1-L1-ADDITIVE-TALLY-1：L1 那一個已有意識升為正式測試
  `test_l1_tally_reports_dropped_count_and_reasons`；L3 層 `test_desired_excluded_coverage_includes_upstream_dropped_rows` 仍保留 xfail）。現況下它們必須真的 fail（xfailed）；
  若某天 XPASS，strict 會讓 CI 轉紅，提醒維護者：缺口已被改掉，請把測試升為正式斷言並更新文件。
- 本檔**不**實作 G-X1、**不**定義「可評分」資格、**不**宣稱完整母體已有實作；
  `parse_portfolio_records` 的 7→1 是 L1 內部 raw→kept，**不是**獨立 expected。
- 全部使用公開代號（2330／0050 等）與匿名合成資料；不含任何真實持股或 Sheet 內容；0 網路、0 時鐘、0 streamlit。
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import re
from datetime import date

import pytest

import src.data.portfolio.gsheet_portfolio as GSP
import src.services.decision_digest_builder as B
import src.services.dividend_station_service as DSS
from shared.decision_digest import HoldingKey
from shared.station_specs import KEY_INVALID_INPUTS
from src.data.portfolio.gsheet_portfolio import parse_portfolio_records
from src.services.decision_digest_builder import SourceStamp, plan_action_selection
from src.services.dividend_station_service import build_station_rows

REPO = pathlib.Path(__file__).resolve().parents[1]
THIS_FILE = pathlib.Path(__file__).resolve()
DOC = REPO / "docs" / "vnext" / "ONEBRAIN_UPSTREAM_EXCLUSION_POINTS_CONTRACT_EVIDENCE_2026-11-21.md"
STAMP = SourceStamp("dividend_station_service", date(2026, 10, 26))


# ── 合成輸入 ─────────────────────────────────────────────────────────────
def seven_raw_records():
    """7 筆 Sheet 原始列（已過 name 過濾；公開代號；純記憶體）。只有第 1 筆在預設路徑存活。"""
    return [
        {"ticker": "2330", "lots": 2, "avg_price": 100.0},      # 正常
        {"ticker": "", "lots": 1, "avg_price": 50.0},           # 空代號
        {"ticker": "0050", "lots": 0, "avg_price": 120.0},      # lots=0
        {"ticker": "2317", "lots": 1, "avg_price": -1},         # avg<0
        {"ticker": "2454", "lots": "abc", "avg_price": 30.0},   # lots 非數字
        {"ticker": "2412", "lots": "", "avg_price": ""},        # 兩欄空白
        {"ticker": "2882", "lots": None, "avg_price": 10.0},    # lots=None
    ]


def srow(ticker, code="add", held=True, **extra):
    r = {"代號": ticker, "held": held, "_action": code, "建議動作": f"txt-{code}-{ticker}", "_detail": {}}
    r.update(extra)
    return r


def hold(*tickers, held=True):
    return [{"ticker": t, "name": f"n-{t}", "held": held} for t in tickers]


def keys(*tickers):
    return {t: HoldingKey("pf-X", t) for t in tickers}


# ═══ 1. parse_portfolio_records：7 → 1，無任何計數 ═══════════════════════
def test_current_behavior_parse_portfolio_records_silently_drops_6_of_7():
    """【已知缺口證據，非規範】預設路徑：7 筆只剩 1 筆；回傳值就是 list，沒有 raw／dropped 計數可問。"""
    raw = seven_raw_records()
    out = parse_portfolio_records(raw)
    assert out == [{"ticker": "2330", "lots": 2.0, "avg_price": 100.0}]
    assert isinstance(out, list)                       # 型別就是純 list：沒有側車／計數物件
    assert len(raw) - len(out) == 6                    # 差額只能由呼叫端自己持有 raw 才算得出來


def test_current_behavior_keep_blank_only_relaxes_blank_cells():
    """【已知缺口證據，非規範】keep_blank=True 只放寬「空白格」；有填值但不可用者照丟、空代號照丟。"""
    out = parse_portfolio_records(seven_raw_records(), keep_blank=True)
    by_tk = {r["ticker"]: r for r in out}
    assert set(by_tk) == {"2330", "2412", "2882"}      # 2412 兩欄空白保留；2882 lots=None 視為空白保留
    assert by_tk["2412"]["lots"] is None and by_tk["2412"]["avg_price"] is None   # 缺值＝None，不是 0
    assert by_tk["2882"]["lots"] is None and by_tk["2882"]["avg_price"] == 10.0
    assert len(seven_raw_records()) - len(out) == 4    # 仍丟 4 筆（空代號、lots=0、avg<0、非數字），仍無計數


def test_current_behavior_parse_is_pure_and_deterministic():
    raw = seven_raw_records()
    assert parse_portfolio_records(raw) == parse_portfolio_records(raw)
    assert raw == seven_raw_records()                  # 不改輸入


# ═══ 2. build_station_rows：空代號 → 無列、無計數 ════════════════════════
def _stock_h(ticker, held=True, lots=1.0, avg=10.0):
    return {"ticker": ticker, "name": "n", "asset_kind": "stock", "held": held, "lots": lots, "avg_price": avg}


def test_current_behavior_build_station_rows_blank_ticker_yields_no_row_no_count():
    """【已知缺口證據，非規範】空代號（含純空白）直接 continue：不產列、不產錯誤列、不留計數。"""
    calls: list = []

    def metrics_fn(tk, kind):                          # 注入：0 網路、0 時鐘
        calls.append((tk, kind))
        return {}

    rows = build_station_rows([_stock_h(""), _stock_h("   "), _stock_h("2330")], vix=None, metrics_fn=metrics_fn)
    assert len(rows) == 1 and rows[0]["代號"] == "2330"
    assert calls == [("2330", "stock")]                # 空代號連 metrics_fn 都沒呼叫


def test_current_behavior_build_station_rows_nonblank_ticker_always_gets_a_row():
    """非空代號一對一派生（單檔 metrics 失敗亦產錯誤列，而非剔除）→ 對帳 holdings↔station 抓不到 L1 源頭丟失。"""
    def boom(tk, kind):
        raise RuntimeError("synthetic failure")

    rows = build_station_rows([_stock_h("2330"), _stock_h("0050")], vix=None, metrics_fn=boom)
    assert [r["代號"] for r in rows] == ["2330", "0050"]
    assert all((r.get("_detail") or {}).get("error") for r in rows)   # 錯誤列帶 _detail.error（下游會計入 excluded）


# ═══ 3. excluded_invalid_rows 只覆蓋「已進 station_rows 的 held 異常列」═════
def _plan(station_rows, holdings_rows):
    tickers = [h["ticker"] for h in holdings_rows]
    return plan_action_selection(station_rows=station_rows, station_stamp=STAMP,
                                 holdings_rows=holdings_rows, holding_keys=keys(*tickers))


def test_current_behavior_excluded_invalid_rows_counts_only_held_invalid_station_rows():
    """held 異常列（_invalid_inputs／_detail.error）→ excluded_invalid_rows；非 held 異常 → not_held；其餘互斥分類各自計數。"""
    s_rows = [
        srow("2330", "add"),                                              # 合格候選
        srow("0050", "add", **{KEY_INVALID_INPUTS: ("張數",)}),            # held 異常 → excluded_invalid
        srow("2317", "add", _detail={"error": "synthetic"}),              # held 錯誤列 → excluded_invalid
        srow("2454", "add", held=False, **{KEY_INVALID_INPUTS: ("現價",)}),  # 非 held 異常 → not_held（不計 excluded）
        srow("2412", "zzz"),                                              # 未知行動碼 → unrecognized
        srow("9999", "add"),                                              # held、碼合法、對不上持股鍵 → unmatched
        "not-a-mapping",                                                  # non_mapping
    ]
    plan = _plan(s_rows, hold("2330", "0050", "2317", "2454", "2412"))
    assert plan.evaluated is True
    assert plan.station_rows_total == 7
    assert plan.total_eligible == 1
    assert plan.excluded_invalid_rows == 2
    assert plan.station_not_held_rows == 1
    assert plan.unrecognized_action_code_rows == 1
    assert plan.unmatched_station_rows == 1
    assert plan.station_non_mapping_rows == 1
    # 互斥窮盡分割（builder docstring 的恆等式）
    assert plan.station_rows_total == (len(plan.ordered) + plan.station_non_action_rows + plan.station_not_held_rows
                                       + plan.excluded_invalid_rows + plan.unrecognized_action_code_rows
                                       + plan.unmatched_station_rows + plan.station_non_mapping_rows)


def test_current_behavior_rows_dropped_by_parse_are_invisible_to_excluded_invalid_rows():
    """【已知缺口證據，非規範】被 parse 丟棄的持股從未進 station_rows → 任何 plan 計數都看不到它。

    以「同一份 7 筆原始列」走 parse→build_station_rows→plan：6 筆在 L1 消失，plan 的所有計數都只描述那 1 筆。
    """
    kept = parse_portfolio_records(seven_raw_records())
    h_rows = [{"ticker": r["ticker"], "name": "n", "asset_kind": "stock", "held": True,
               "lots": r["lots"], "avg_price": r["avg_price"]} for r in kept]
    s_rows = build_station_rows(h_rows, vix=None, metrics_fn=lambda tk, kind: {})
    plan = _plan(s_rows, [{"ticker": h["ticker"], "name": h["name"], "held": True} for h in h_rows])
    assert plan.station_rows_total == 1 and plan.holdings_rows_total == 1
    assert plan.excluded_invalid_rows is not None and plan.excluded_invalid_rows <= 1
    for name in ("excluded_invalid_rows", "unmatched_station_rows", "holdings_without_station_row",
                 "unrecognized_action_code_rows", "station_non_mapping_rows", "holdings_non_mapping_rows"):
        assert getattr(plan, name) is not None and getattr(plan, name) <= 1      # 沒有任何欄位反映「原本是 7」
    assert not [f for f in plan.__dataclass_fields__ if "raw" in f or "dropped" in f or "parse" in f]


def test_current_behavior_station_derived_from_holdings_reconciliation_cannot_see_l1_loss():
    """【INFERENCE 的可執行佐證】holdings↔station 兩側同源：L1 丟失後兩側仍然「對得上」。"""
    kept = parse_portfolio_records(seven_raw_records())
    h_rows = [{"ticker": r["ticker"], "name": "n", "asset_kind": "stock", "held": True,
               "lots": r["lots"], "avg_price": r["avg_price"]} for r in kept]
    s_rows = build_station_rows(h_rows, vix=None, metrics_fn=lambda tk, kind: {})
    plan = _plan(s_rows, [{"ticker": h["ticker"], "name": h["name"], "held": True} for h in h_rows])
    assert plan.holdings_without_station_row == 0      # 對帳「完全吻合」，卻漏了 6 筆來源列


# ═══ 4. 期望改善（xfail strict）— 尚未實現；不是規範 ═══════════════════
_XFAIL_REASON = ("期望改善尚未實現（DEC-215；docs/vnext/ONEBRAIN_UPSTREAM_EXCLUSION_POINTS_CONTRACT_EVIDENCE_2026-11-21.md）；"
                 "G-X1 未授權，需另行 Decision Gate。strict：若 XPASS 代表缺口已被改掉，請升為正式斷言並更新文件。")


def test_l1_tally_reports_dropped_count_and_reasons():
    """【有意識改寫，不是漏刪】原 `test_desired_parse_layer_reports_dropped_count`（strict xfail，只要求「可問到 dropped==6」）
    已由 C-OB-GX1-L1-ADDITIVE-TALLY-1（客戶授權 #1199 comment 7055751465；施工包 7055505068）的 L1 純加性
    `tally_portfolio_records` 實現，升為更嚴的正式斷言：兩模式精確計數＋逐原因＋與既有解析器保留集合一致。
    ⚠️ 只涵蓋 L1；L3 層期望（下方 `test_desired_excluded_coverage_includes_upstream_dropped_rows`）仍是 xfail，**未實現、不得湊數**。
    ⚠️ `raw` 與 rows 同源，不是獨立 expected completeness；`parse_portfolio_records` 本身仍回純 list（未改）。"""
    raw = seven_raw_records()
    assert isinstance(parse_portfolio_records(raw), list)                 # 既有解析器介面未動
    t = GSP.tally_portfolio_records(raw, keep_blank=False)
    assert (t.status, t.raw, t.kept) == ("ok", 7, 1)
    assert t.raw - t.kept == 6                                            # 原 xfail 的期望：dropped == 6
    assert t.dropped == {"blank_ticker": 1, "non_numeric": 1, "non_finite": 0, "non_positive": 2, "blank_value": 2}
    assert list(t.rows) == parse_portfolio_records(raw)                   # 保留集合與既有解析器逐列相同
    k = GSP.tally_portfolio_records(raw, keep_blank=True)
    assert (k.raw, k.kept, k.kept_with_missing_value) == (7, 3, 2)
    assert k.dropped["blank_value"] == 0
    assert list(k.rows) == parse_portfolio_records(raw, keep_blank=True)


@pytest.mark.xfail(strict=True, reason=_XFAIL_REASON)
def test_desired_excluded_coverage_includes_upstream_dropped_rows():
    """期望：排除揭露涵蓋上游被丟棄的列（目前 plan 無任何欄位反映 L1 丟棄）。"""
    kept = parse_portfolio_records(seven_raw_records())
    h_rows = [{"ticker": r["ticker"], "name": "n", "asset_kind": "stock", "held": True,
               "lots": r["lots"], "avg_price": r["avg_price"]} for r in kept]
    s_rows = build_station_rows(h_rows, vix=None, metrics_fn=lambda tk, kind: {})
    plan = _plan(s_rows, [{"ticker": h["ticker"], "name": h["name"], "held": True} for h in h_rows])
    assert plan.excluded_invalid_rows == 6, "期望把 L1 丟棄的 6 筆也揭露；目前只涵蓋已進戰情表的 held 異常列"


# ═══ 5. 文件漂移守衛（簡單）══════════════════════════════════════════
# 文件表列的剔除點 → (模組, 函式, 原始碼中必須仍存在的 `continue` 所在函式)
_EXCLUSION_POINTS = (
    (GSP, "parse_portfolio_records"),
    (DSS, "build_station_rows"),
    (B, "_scan_action_rows"),
)


def _fn_has_continue(src: str, fn_name: str) -> bool:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fn_name:
            return any(isinstance(n, ast.Continue) for n in ast.walk(node))
    raise AssertionError(f"{fn_name} 不存在（文件表列的剔除點已漂移，請更新文件與本守衛）")


@pytest.mark.parametrize("mod,fn", _EXCLUSION_POINTS)
def test_documented_exclusion_points_still_exist_in_source(mod, fn):
    assert hasattr(mod, fn)
    assert _fn_has_continue(inspect.getsource(mod), fn)


def test_holdings_service_blank_ticker_continue_still_exists():
    import src.services.holdings_service as HS
    src = pathlib.Path(HS.__file__).read_text(encoding="utf-8")
    assert re.search(r"if not _tk:\s*\n\s*continue", src)
    assert re.search(r"if not _tk or _norm\(_tk\) in _seen:\s*\n\s*continue", src)


def test_doc_exists_and_names_every_exclusion_point_and_labels_nv():
    text = DOC.read_text(encoding="utf-8")
    for needle in ("parse_portfolio_records", "build_station_rows", "_scan_action_rows", "holdings_service",
                   "excluded_invalid_rows", "DEC-215", "NOT VERIFIED", "G-X1"):
        assert needle in text, needle


def test_this_file_has_no_ui_network_or_secret_imports():
    tree = ast.parse(THIS_FILE.read_text(encoding="utf-8"))
    banned = {"streamlit", "requests", "urllib", "httpx", "socket", "gspread", "anthropic", "openai"}
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    assert not (mods & banned)
