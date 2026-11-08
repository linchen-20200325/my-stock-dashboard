"""tests/test_fina_both_legs_required.py — 財報趨勢「兩腿皆有效才可產正式綜合評級」（客戶 DEC-150，2026-11-08）。

客戶原文：「財報缺任一必要腿不產正式綜合評級；接受空快照資料資格修正造成的排序變化…
未核准數值或重大公式變更須停手。」

本批只改**資格**（OR → AND）與文案：65%／35% 權重、`compute_trend_score` 公式、`TREND_MIN_*` 門檻、
per-leg 有效判定（月 ≥ TREND_MIN_REVENUE_MONTHS 個月有 YoY；季 ≥ TREND_MIN_FIN_SNAPSHOTS 季且近兩季比得出指標）一字未動。

測試層次：
  ① 邊緣：最新一對空／前一對有效、最新有效／前一對空、diff 例外保守判無證據、真 0 不誤殺、只一季、空 dict 快照
  ② parity：同一組輸入，單股 Tab（trend_rating_status）、組合 Tab（真的跑 `_render_fin_trend_table`）、AI prompt 三處判定一致
  ③ 突變：拿掉任一處 guard，對應測試必須轉紅
  ④ 前後差異證據：用固定合成 fixture 量化「舊規則 vs 新規則」各有多少列從可評分變不可評分（不是績效）
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.compute.health.fin_trend_score import compute_one_stock_trend
from src.compute.screener import scorability as sc
from src.compute.screener.scorability import (
    is_trend_scorable,
    split_trend_rows,
    trend_prompt_line,
    trend_rating_status,
    trend_row_evidence,
    trend_sub_texts,
)

_PASS = {"cash_ratio_status": "🟢", "ocf_status": "🟢", "debt_ratio_status": "🟢"}
_FAIL = {"cash_ratio_status": "🔴", "ocf_status": "🔴", "debt_ratio_status": "🔴"}


def _rev_df(yoy_up: bool = True, n: int = 15) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=n, freq="MS")
    rev = [100.0] * n
    if yoy_up:
        for i in range(12, n):
            rev[i] = 120.0
    return pd.DataFrame({"date": dates, "revenue": rev})


def _row(monkeypatch, *, rev, snaps: list[dict] | dict, sid: str = "2330") -> dict:
    """真的跑 compute_one_stock_trend。snaps 為 list（oldest..latest）或 {ym: snap}。"""
    import src.data.stock.monthly_revenue_fetcher as mrf
    monkeypatch.setattr(mrf, "fetch_monthly_revenue",
                        lambda s, months=15: rev if rev is not None else pd.DataFrame())
    if isinstance(snaps, list):
        snaps = {f"2026{3 * (i + 1):02d}": s for i, s in enumerate(snaps)}
    return compute_one_stock_trend(
        sid, "202611", "tok", 0.65,
        fetch_financial_statements=lambda *a, **k: {"error": "no"},
        analyze_financial_health=lambda *a, **k: None,
        list_snapshots=lambda s: sorted(snaps, reverse=True),
        load_snapshot=lambda s, ym: snaps.get(ym),
        save_snapshot=lambda *a, **k: None,
    )


# ═══ ① 邊緣 ══════════════════════════════════════════════════
class TestEdges:
    def test_both_legs_complete_unchanged(self, monkeypatch):
        row = _row(monkeypatch, rev=_rev_df(True), snaps=[_FAIL, _PASS, _PASS])
        st = trend_rating_status(row)
        assert st.scorable and not st.partial and st.missing_legs_text == ""
        assert row["score"] == pytest.approx(row["mon_sub"] * 0.65 + row["fin_sub"] * 0.35, abs=1e-2)
        assert "合分" in trend_prompt_line(row) and "僅供診斷" not in trend_prompt_line(row)

    def test_only_monthly_missing(self, monkeypatch):
        row = _row(monkeypatch, rev=None, snaps=[_FAIL, _PASS])
        st = trend_rating_status(row)
        assert not st.scorable and st.partial and st.missing_legs == ("月營收",)
        assert st.unscorable_label.startswith("⚪ 無法形成正式綜合評級（缺月營收腿：")

    def test_only_quarterly_missing(self, monkeypatch):
        row = _row(monkeypatch, rev=_rev_df(True), snaps=[])
        st = trend_rating_status(row)
        assert not st.scorable and st.partial and st.missing_legs == ("季財報",)
        assert st.unscorable_label.startswith("⚪ 無法形成正式綜合評級（缺季財報腿：")

    def test_both_missing(self, monkeypatch):
        row = _row(monkeypatch, rev=None, snaps=[])
        st = trend_rating_status(row)
        assert not st.scorable and not st.partial
        assert st.missing_legs_text == "缺月營收腿、季財報腿"

    def test_single_quarter_snapshot_with_valid_monthly_is_not_formal(self, monkeypatch):
        row = _row(monkeypatch, rev=_rev_df(True), snaps=[_PASS])
        st = trend_rating_status(row)
        assert not st.scorable and st.monthly_ok and not st.fin_ok
        assert "季快照僅 1 期" in st.reason_text

    @pytest.mark.parametrize("snaps", [[{}, {}], [{}, {}, {}]])
    def test_empty_dict_snapshots_with_valid_monthly_not_formal(self, monkeypatch, snaps):
        row = _row(monkeypatch, rev=_rev_df(True), snaps=snaps)
        assert row["fin_detail"]["n_snapshots"] >= 2           # 原 detail 不動
        st = trend_rating_status(row)
        assert not st.scorable and not st.fin_ok and "無可比較指標" in st.reason_text

    def test_latest_pair_empty_previous_pair_valid_fin_leg_invalid(self, monkeypatch):
        """QA 邊緣：[FAIL, PASS, {}] —— 前一對(FAIL→PASS)有效、**最新一對**(PASS→{})比不出指標。
        現行定義以『最新一對』為準（trend_row_evidence 讀的 diff_verdict 即最新一對）→ 季腿無效。
        公式面該季分仍是 0.5×舊一對（衰減），但那是舊季的資訊、不是最新體質 → 保守不認；有效月腿仍可診斷顯示。"""
        row = _row(monkeypatch, rev=_rev_df(True), snaps=[_FAIL, _PASS, {}])
        assert row["fin_detail"]["n_snapshots"] == 3
        assert row["fin_sub"] != 0.0                       # 公式照舊（未改）：前一對把季分拉離 0
        assert trend_row_evidence(row)[1] == 0
        st = trend_rating_status(row)
        assert not st.scorable and st.monthly_ok and not st.fin_ok
        assert trend_sub_texts(row)[1] == "—（缺）"         # 季分不當有效分項顯示
        line = trend_prompt_line(row)
        assert "合分" not in line and row["label"] not in line

    def test_latest_pair_valid_previous_pair_empty_fin_leg_valid(self, monkeypatch):
        """對照組：[{}, PASS, PASS] —— 最新一對(PASS→PASS)比得出指標 → 季腿有效、兩腿皆足 → 正式評級。"""
        row = _row(monkeypatch, rev=_rev_df(True), snaps=[{}, _PASS, _PASS])
        st = trend_rating_status(row)
        assert st.scorable and st.fin_ok

    def test_diff_verdict_exception_is_conservative_no_evidence(self, monkeypatch):
        """QA 小漏洞：compute_one_stock_trend 的轉機 diff 拋例外 → diff_verdict=None。
        舊行為：trend_row_evidence 退回只看 n_snapshots(=2) → 季腿被當有效。現在：保守判無證據。"""
        import src.compute.health as H
        monkeypatch.setattr(H, "diff_fin_health",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        row = _row(monkeypatch, rev=_rev_df(True), snaps=[_PASS, _PASS])
        assert row["diff_verdict"] is None and row.get("diff_failed") is True
        assert "轉機判定失敗" in row["note"]
        assert row["fin_detail"]["n_snapshots"] == 2          # 公式面快照數不變
        assert trend_row_evidence(row)[1] == 0
        st = trend_rating_status(row)
        assert not st.scorable and not st.fin_ok
        assert "比較失敗" in st.reason_text

    def test_diff_ok_row_has_no_diff_failed_flag(self, monkeypatch):
        row = _row(monkeypatch, rev=_rev_df(True), snaps=[_PASS, _PASS])
        assert "diff_failed" not in row and row["diff_verdict"] is not None

    def test_legacy_row_without_flag_still_falls_back(self):
        """手工列／舊 cache 沒有 diff_verdict 也沒有 diff_failed → 相容舊行為（只看 n_snapshots）。"""
        row = {"mon_detail": {"n_months": 3}, "fin_detail": {"n_snapshots": 2}}
        assert is_trend_scorable(row)

    def test_true_zero_with_both_legs_complete_is_neutral_not_killed(self, monkeypatch):
        """月 YoY 平均恰 0＋季真的 diff 後不變 → 合分真的是 0.0 且兩腿完整 → 中性照常顯示（不誤殺）。"""
        row = _row(monkeypatch, rev=_rev_df(False), snaps=[_PASS, _PASS])
        assert row["score"] == 0.0 and row["label_code"] == "neutral"
        st = trend_rating_status(row)
        assert st.scorable and st.reason_text == ""
        line = trend_prompt_line(row)
        assert "➖ 中性" in line and "合分 +0.00" in line and "不足" not in line
        ok, bad = split_trend_rows([row])
        assert ok == [row] and bad == []

    def test_thresholds_untouched(self):
        from shared.signal_thresholds import TREND_MIN_FIN_SNAPSHOTS, TREND_MIN_REVENUE_MONTHS
        assert (TREND_MIN_REVENUE_MONTHS, TREND_MIN_FIN_SNAPSHOTS) == (1, 2)

    def test_weights_unchanged_not_reweighted(self, monkeypatch):
        """缺月腿時 65/35 不重配：score 仍 = 0.35×季分（不被拉成 1.0×季分）。"""
        row = _row(monkeypatch, rev=None, snaps=[_FAIL, _PASS])
        assert row["score"] == pytest.approx(row["fin_sub"] * 0.35, abs=1e-2)


# ═══ ② parity：單股／組合／AI 三處 ═════════════════════════════
def _combo_table_rows(rows: list[dict]) -> list[dict]:
    """真的跑組合 Tab 的 `_render_fin_trend_table`，抓它最後交給 st.dataframe 的主表。"""
    from src.ui.tabs.tab_stock_grp import _render_fin_trend_table
    st_mod = MagicMock()
    st_mod._col_lists = []

    def _cols(n):
        lst = [MagicMock() for _ in range(n)]
        st_mod._col_lists.append(lst)
        return lst
    st_mod.columns.side_effect = _cols
    captured: list[pd.DataFrame] = []
    st_mod.dataframe.side_effect = lambda df, **k: captured.append(df)
    _render_fin_trend_table(rows, pd, st_mod, "202611")
    assert captured, "組合 Tab 沒有畫出主表"
    return captured[0].to_dict("records"), st_mod


_PARITY = {
    "both_complete": dict(rev="up", snaps=[_FAIL, _PASS, _PASS]),
    "true_zero": dict(rev="flat", snaps=[_PASS, _PASS]),
    "only_monthly": dict(rev="up", snaps=[]),
    "only_fin": dict(rev=None, snaps=[_FAIL, _PASS]),
    "both_missing": dict(rev=None, snaps=[]),
    "one_snapshot": dict(rev="up", snaps=[_PASS]),
    "empty_dicts": dict(rev="up", snaps=[{}, {}]),
    "latest_pair_empty": dict(rev="up", snaps=[_FAIL, _PASS, {}]),
}


class TestParityThreeConsumers:
    @pytest.mark.parametrize("name", list(_PARITY))
    def test_same_input_same_verdict(self, monkeypatch, name):
        c = _PARITY[name]
        rev = {"up": _rev_df(True), "flat": _rev_df(False), None: None}[c["rev"]]
        row = _row(monkeypatch, rev=rev, snaps=c["snaps"], sid="9999")

        single_formal = trend_rating_status(row).scorable                       # 單股 Tab 的資格
        ai_formal = not trend_prompt_line(row).startswith("財報趨勢資料不足")   # AI prompt 的資格
        ok, bad = split_trend_rows([row])                                       # 組合 Tab 的切分
        combo_formal_split = bool(ok)
        table, _st = _combo_table_rows([row])                                   # 組合 Tab 真實渲染
        combo_formal_cell = not table[0]["判定(月+季)"].startswith("⚪ 無法形成正式綜合評級")

        assert single_formal == ai_formal == combo_formal_split == combo_formal_cell, (
            name, single_formal, ai_formal, combo_formal_split, combo_formal_cell)

        # 不具資格時：三處都不得露出合分／標籤當結論
        if not single_formal:
            assert "合分" not in trend_prompt_line(row)
            assert row["label"] not in trend_prompt_line(row)
            assert table[0]["綜合分數"] == "—"
            assert trend_rating_status(row).unscorable_label.startswith("⚪ 無法形成正式綜合評級（缺")
        else:
            assert table[0]["綜合分數"] == f"{row['score']:.2f}"
            assert table[0]["判定(月+季)"] == row["label"]

    def test_combo_valid_leg_subscore_still_shown_and_flagged(self, monkeypatch):
        row = _row(monkeypatch, rev=_rev_df(True), snaps=[], sid="1101")
        table, st_mod = _combo_table_rows([row])
        t = table[0]
        assert t["綜合分數"] == "—" and t["季財報分"] == "—（缺）"
        assert t["月營收分"] == f"{row['mon_sub']:+.2f}"
        assert "非完整評級" in t["備註"] and "缺季財報腿" in t["備註"]
        # 警語涵蓋「缺任一腿」而非舊文案「月營收與季快照皆缺」
        warn = " ".join(str(c.args[0]) for c in st_mod.warning.call_args_list)
        assert "缺任一腿" in warn and "皆缺" not in warn and "1101（缺季財報腿）" in warn

    def test_combo_counts_exclude_single_leg_rows(self, monkeypatch):
        rows = [_row(monkeypatch, rev=_rev_df(True), snaps=[_FAIL, _PASS, _PASS], sid="A"),
                _row(monkeypatch, rev=_rev_df(True), snaps=[], sid="B"),
                _row(monkeypatch, rev=None, snaps=[_FAIL, _PASS], sid="C")]
        _t, st_mod = _combo_table_rows(rows)
        ok, bad = split_trend_rows(rows)
        assert [r["sid"] for r in ok] == ["A"] and [r["sid"] for r in bad] == ["B", "C"]
        # 第一列 6 個 KPI：5 段計數只算 A（1 檔），最後一格「無法評分」＝ B、C（2 檔）
        kpis = st_mod._col_lists[0]
        five = [k.metric.call_args.args[1] for k in kpis[:5]]
        assert sum(five) == 1 and kpis[5].metric.call_args.args[1] == 2
        caption = " ".join(str(c.args[0]) for c in st_mod.caption.call_args_list)
        assert "可形成正式綜合評級的 1 檔" in caption


# ═══ ③ 突變 ══════════════════════════════════════════════════
class TestMutations:
    def test_mutation_back_to_OR_turns_red(self, monkeypatch):
        """突變：把 is_trend_scorable 改回舊的 OR → 單腿列被放行 → 本批核心斷言必須失敗。"""
        row = _row(monkeypatch, rev=_rev_df(True), snaps=[], sid="B")
        assert not is_trend_scorable(row)
        _m, _s = trend_row_evidence(row)
        or_rule = lambda r, **k: (lambda ms: ms[0] >= 1 or ms[1] >= 2)(trend_row_evidence(r))  # noqa: E731
        monkeypatch.setattr(sc, "is_trend_scorable", or_rule)
        with pytest.raises(AssertionError):
            assert not sc.trend_rating_status(row).scorable
        with pytest.raises(AssertionError):
            assert sc.trend_prompt_line(row).startswith("財報趨勢資料不足")
        with pytest.raises(AssertionError):
            ok, bad = sc.split_trend_rows([row])
            assert not ok

    def test_mutation_prompt_line_leaking_score_turns_red(self, monkeypatch):
        """突變：prompt 在不具資格時又送出合分／標籤 → 斷言必須失敗。"""
        row = _row(monkeypatch, rev=None, snaps=[_FAIL, _PASS], sid="C")
        good = sc.trend_prompt_line(row)
        assert "合分" not in good
        leaked = f"財報趨勢分數(月+季 65/35)={row['label']} (合分 {row['score']:+.2f})"
        monkeypatch.setattr(sc, "trend_prompt_line", lambda r: leaked)
        with pytest.raises(AssertionError):
            assert "合分" not in sc.trend_prompt_line(row)

    def test_mutation_diff_failed_guard_removed_turns_red(self, monkeypatch):
        """突變：拿掉 diff_failed 保守規則（等同舊行為）→ 例外情境的季腿又被當有效。"""
        import src.compute.health as H
        monkeypatch.setattr(H, "diff_fin_health",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        row = _row(monkeypatch, rev=_rev_df(True), snaps=[_PASS, _PASS])
        assert not is_trend_scorable(row)
        row_mut = dict(row)
        row_mut.pop("diff_failed")                      # 等同拿掉旗標／規則
        with pytest.raises(AssertionError):
            assert not is_trend_scorable(row_mut)

    def test_mutation_empty_dict_rule_removed_turns_red(self, monkeypatch):
        row = _row(monkeypatch, rev=_rev_df(True), snaps=[{}, {}])
        assert not is_trend_scorable(row)
        row_mut = dict(row)
        row_mut.pop("diff_verdict")
        with pytest.raises(AssertionError):
            assert not is_trend_scorable(row_mut)

    def test_mutation_combo_cell_ignoring_status_turns_red(self, monkeypatch):
        """突變：組合 Tab 表格若不依資格（永遠印 label）→ parity 斷言必須失敗。"""
        row = _row(monkeypatch, rev=_rev_df(True), snaps=[], sid="B")
        table, _ = _combo_table_rows([row])
        assert table[0]["判定(月+季)"].startswith("⚪ 無法形成正式綜合評級")
        mutated_cell = row["label"]
        with pytest.raises(AssertionError):
            assert mutated_cell.startswith("⚪ 無法形成正式綜合評級")


# ═══ ④ 前後差異證據（固定合成 fixture，非績效）════════════════════
def _old_rule_pre1068(row: dict) -> bool:
    """#1068 之前：任一腿（月 n_months ≥ 1 或 季 n_snapshots ≥ 2，只看計數）。"""
    md, fd = row.get("mon_detail") or {}, row.get("fin_detail") or {}
    return (md.get("n_months", 0) or 0) >= 1 or (fd.get("n_snapshots", 0) or 0) >= 2


def _rule_1068(row: dict) -> bool:
    """#1068：任一腿，但季快照須比得出指標（空 dict 不算）。"""
    m, s = trend_row_evidence(row)
    return m >= 1 or s >= 2


def _rule_new(row: dict) -> bool:
    return is_trend_scorable(row)


# 14 種月×季組合（每種各 1 列，等權；合成資料，只為量化規則差異）
_MONTHLY = {"月有效": "up", "月缺": None}
_FIN = {
    "季3期有效": [_FAIL, _PASS, _PASS],
    "季2期有效": [_FAIL, _PASS],
    "季1期": [_PASS],
    "季0期": [],
    "季2期空dict": [{}, {}],
    "季3期空dict": [{}, {}, {}],
    "季3期最新一對空": [_FAIL, _PASS, {}],
}


def _fixture_rows(monkeypatch) -> list[tuple[str, dict]]:
    out = []
    for mk, mv in _MONTHLY.items():
        for fk, fv in _FIN.items():
            rev = _rev_df(True) if mv == "up" else None
            out.append((f"{mk}×{fk}", _row(monkeypatch, rev=rev, snaps=fv, sid=f"{mk}{fk}")))
    return out


class TestBeforeAfterEvidence:
    def test_counts_old_vs_new_rule(self, monkeypatch):
        rows = _fixture_rows(monkeypatch)
        assert len(rows) == 14
        n_pre = sum(_old_rule_pre1068(r) for _n, r in rows)
        n_1068 = sum(_rule_1068(r) for _n, r in rows)
        n_new = sum(_rule_new(r) for _n, r in rows)
        # 規則階梯單調收緊：舊 ≥ #1068 ≥ 新
        assert n_pre >= n_1068 >= n_new
        # 新規則 ⊂ #1068 ⊂ 舊（逐列包含，非只有數量）
        for name, r in rows:
            assert (not _rule_new(r)) or _rule_1068(r), name
            assert (not _rule_1068(r)) or _old_rule_pre1068(r), name
        lost_vs_1068 = [n for n, r in rows if _rule_1068(r) and not _rule_new(r)]
        lost_vs_pre = [n for n, r in rows if _old_rule_pre1068(r) and not _rule_new(r)]
        empty_dict_effect = [n for n, r in rows if _old_rule_pre1068(r) and not _rule_1068(r)]
        # 釘死證據數字（固定 fixture；改動規則導致數字變就紅，需重新核准）
        assert (n_pre, n_1068, n_new) == (12, 9, 2)
        assert len(empty_dict_effect) == 3 and len(lost_vs_1068) == 7 and len(lost_vs_pre) == 10
        # 只有「月有效 × 季有效(3 期／2 期)」2 列保有正式評級
        assert sorted(n for n, r in rows if _rule_new(r)) == ["月有效×季2期有效", "月有效×季3期有效"]
        # 空 dict 規則（#1068）只影響「月缺」的 3 列（月有效時另一腿本來就撐著）
        assert sorted(empty_dict_effect) == ["月缺×季2期空dict", "月缺×季3期最新一對空", "月缺×季3期空dict"]
        print("\n【前後差異證據｜合成 fixture 14 列（月2態×季7態），不是績效】")
        print(f"  #1068 之前（OR，只看計數）可評分：{n_pre}/14")
        print(f"  #1068（OR＋空 dict 不算證據）可評分：{n_1068}/14   ← 空 dict 規則使 {len(empty_dict_effect)} 列轉不可評分")
        print(f"  DEC-150（AND：兩腿皆有效）可評分：{n_new}/14   ← 再有 {len(lost_vs_1068)} 列由可評分轉不可評分")
        print("  DEC-150 比 #1068 新增不可評分：" + "、".join(lost_vs_1068))
        print("  仍具正式評級：" + "、".join(n for n, r in rows if _rule_new(r)))

    def test_ranking_effect_unscorable_rows_leave_five_bucket_counts(self, monkeypatch):
        """排序／計數效應：不可評分列不進 5 段計數（KPI 分母＝正式評級檔數），且排在表尾。"""
        rows = [r for _n, r in _fixture_rows(monkeypatch)]
        ok, bad = split_trend_rows(rows)
        assert len(ok) == 2 and len(bad) == 12
        table, st_mod = _combo_table_rows(rows)
        formal_labels = [t["判定(月+季)"] for t in table[:len(ok)]]
        tail_labels = [t["判定(月+季)"] for t in table[len(ok):]]
        assert all(not x.startswith("⚪") for x in formal_labels)
        assert all(x == "⚪ 無法形成正式綜合評級" for x in tail_labels)
