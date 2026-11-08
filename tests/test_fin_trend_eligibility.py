"""tests/test_fin_trend_eligibility.py — 財報趨勢分數「資料資格」單一來源（客戶 2026-11-08 核准）。

客戶原文：「財報維持65%／35%原始權重，必要資料不足不得產生正式綜合評級」。
本批不改正式公式／權重／門檻（TREND_MIN_*）。只讓**所有消費端**（單股 Tab／AI prompt／組合 Tab）共用
`scorability.trend_rating_status` / `trend_prompt_line`，缺值時不得把「➖ 中性 +0.00」當投資結論。

測試分三層：① 純函式資格（六種資料組合＋真 0＋空 dict）② 三消費端一致 ③ 接線＋突變（拔 guard 轉紅）。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.compute.health.fin_trend_score import compute_one_stock_trend
from src.compute.screener import scorability as sc
from src.compute.screener.scorability import (
    is_trend_scorable,
    split_trend_rows,
    trend_prompt_line,
    trend_rating_status,
    trend_sub_texts,
)

REPO = Path(__file__).resolve().parents[1]

# 📌 2026-11-08 DEC-150（客戶核准「財報缺任一必要腿不產正式綜合評級」；有意識的契約變更，⛔ 不是放寬）：
#   資格由「任一腿有效」(OR) 改「兩腿皆有效」(AND)。本檔下列測試的**預期值依裁示翻轉**（舊斷言以刪除線保留於各 docstring／註解）：
#   test_only_monthly_missing／test_only_quarterly_missing_…／test_both_missing_is_unscorable_never_neutral
#   （文案：「⚪ 無法評分」→「⚪ 無法形成正式綜合評級（缺X腿：原因）」；AI 行不再送合分）、
#   test_empty_snapshots_do_not_rescue_via_monthly_leg_flag、test_legacy_rows_without_diff_verdict_fall_back_to_n_snapshots、
#   test_mutation_empty_dict_rule_removed_turns_red（改用月腿有效的列，空 dict 規則才是唯一變數）。
#   其餘斷言（兩腿完整逐字不變、真 0 不誤殺、單季／空 dict／畸形快照不是證據、門檻未動、接線）一字未放寬。

_PASS = {"cash_ratio_status": "🟢", "ocf_status": "🟢", "debt_ratio_status": "🟢"}
_FAIL = {"cash_ratio_status": "🔴", "ocf_status": "🔴", "debt_ratio_status": "🔴"}


def _rev_df(yoy_up: bool = True, n: int = 15) -> pd.DataFrame:
    """15 個月月營收；yoy_up=True → 近月較去年同月 +20%。"""
    dates = pd.date_range("2025-01-01", periods=n, freq="MS")
    rev = [100.0] * n
    if yoy_up:
        for i in range(12, n):
            rev[i] = 120.0
    else:
        for i in range(12, n):
            rev[i] = 100.0
    return pd.DataFrame({"date": dates, "revenue": rev})


def _row(monkeypatch, *, rev: pd.DataFrame | None, snaps: dict[str, dict]) -> dict:
    """真的跑 compute_one_stock_trend（注入式依賴，月營收 monkeypatch）。"""
    import src.data.stock.monthly_revenue_fetcher as mrf
    monkeypatch.setattr(mrf, "fetch_monthly_revenue",
                        lambda sid, months=15: rev if rev is not None else pd.DataFrame())
    return compute_one_stock_trend(
        "2330", "202611", "tok", 0.65,
        fetch_financial_statements=lambda *a, **k: {"error": "no"},
        analyze_financial_health=lambda *a, **k: None,
        list_snapshots=lambda sid: sorted(snaps, reverse=True),
        load_snapshot=lambda sid, ym: snaps.get(ym),
        save_snapshot=lambda *a, **k: None,
    )


# ═══ ① 純函式資格 ═════════════════════════════════════════════
class TestEligibility:
    def test_both_legs_complete_keeps_65_35_and_no_note(self, monkeypatch):
        row = _row(monkeypatch, rev=_rev_df(True),
                   snaps={"202609": _FAIL, "202610": _PASS, "202611": _PASS})
        st = trend_rating_status(row)
        assert st.scorable and st.monthly_ok and st.fin_ok and not st.partial
        assert st.reason_text == "" and st.missing_legs == ()
        # 現有 65/35 計算原封不動
        assert row["score"] == pytest.approx(row["mon_sub"] * 0.65 + row["fin_sub"] * 0.35, abs=1e-2)
        # 完整雙腿 → AI 行與舊格式逐字相同（不退化）
        assert trend_prompt_line(row) == (
            f"財報趨勢分數(月+季 65/35)={row['label']} "
            f"(合分 {row['score']:+.2f},月分 {row['mon_sub']:+.2f}/季分 {row['fin_sub']:+.2f})")
        assert "非完整" not in trend_prompt_line(row) and "僅供診斷" not in trend_prompt_line(row)

    def test_only_monthly_missing(self, monkeypatch):
        row = _row(monkeypatch, rev=None, snaps={"202610": _FAIL, "202611": _PASS})
        st = trend_rating_status(row)
        # ~~assert st.scorable and st.partial~~（DEC-150：缺月營收腿 → 不形成正式綜合評級；有效季分項僅供診斷）
        assert (not st.scorable) and st.partial and st.missing_legs == ("月營收",)
        assert st.unscorable_label.startswith("⚪ 無法形成正式綜合評級（缺月營收腿：")
        assert "月營收無資料" in st.reason_text
        line = trend_prompt_line(row)
        assert line.startswith("財報趨勢資料不足（缺月營收腿") and "無法形成正式綜合評級" in line
        assert "僅供診斷" in line and f"季分 {row['fin_sub']:+.2f}" in line and "不得作為已確認結論" in line
        assert "合分" not in line and row["label"] not in line
        assert row["fin_sub"] > 0                       # 有效分項保留，不丟
        mon_txt, fin_txt = trend_sub_texts(row)
        assert mon_txt == "—（缺）" and fin_txt == f"{row['fin_sub']:+.2f}"

    def test_only_quarterly_missing_half_missing_not_reweighted_but_flagged(self, monkeypatch):
        row = _row(monkeypatch, rev=_rev_df(True), snaps={})
        # 公式不變：月 YoY=+20% → 月分≥2，季缺→0 不重配權（0.65*mon）
        assert row["score"] == pytest.approx(row["mon_sub"] * 0.65, abs=1e-2)
        st = trend_rating_status(row)
        # ~~assert st.scorable and st.partial~~（DEC-150：缺季財報腿 → 不形成正式綜合評級）
        assert (not st.scorable) and st.partial and st.missing_legs == ("季財報",)
        assert "季快照僅 0 期" in st.reason_text
        line = trend_prompt_line(row)
        assert line.startswith("財報趨勢資料不足（缺季財報腿") and "無法形成正式綜合評級" in line
        assert "非完整雙頻率評級" in line and f"月分 {row['mon_sub']:+.2f}" in line
        assert "合分" not in line and row["label"] not in line
        assert row["mon_sub"] != 0                       # 有效月分項保留

    def test_both_missing_is_unscorable_never_neutral(self, monkeypatch):
        row = _row(monkeypatch, rev=None, snaps={})
        assert row["label_code"] == "neutral" and row["score"] == 0.0   # 原純函式行為不動（舊 schema）
        st = trend_rating_status(row)
        assert not st.scorable and not st.monthly_ok and not st.fin_ok
        assert st.unscorable_label.startswith("⚪ 無法形成正式綜合評級（缺月營收腿、季財報腿：")
        line = trend_prompt_line(row)
        assert line.startswith("財報趨勢資料不足（缺月營收腿、季財報腿")      # ~~「…，無法形成綜合評級（…）」~~ 文案依 DEC-150
        assert "無法形成正式綜合評級" in line and "無有效分項" in line
        assert "中性" not in line and "+0.00" not in line and "合分" not in line

    def test_single_quarter_snapshot_is_not_evidence(self, monkeypatch):
        row = _row(monkeypatch, rev=None, snaps={"202611": _PASS})
        st = trend_rating_status(row)
        assert not st.scorable and "季快照僅 1 期" in st.reason_text

    def test_empty_dict_snapshots_are_not_evidence(self, monkeypatch):
        """2~3 期皆空 dict：舊行為 n_snapshots=2/3 → 被當有證據；現在須判無證據。"""
        for snaps in ({"202610": {}, "202611": {}},
                      {"202609": {}, "202610": {}, "202611": {}}):
            row = _row(monkeypatch, rev=None, snaps=snaps)
            assert row["fin_detail"]["n_snapshots"] >= 2          # 原 detail 不動
            assert not is_trend_scorable(row)
            st = trend_rating_status(row)
            assert not st.scorable and "無可比較指標" in st.reason_text

    def test_empty_snapshots_do_not_rescue_via_monthly_leg_flag(self, monkeypatch):
        row = _row(monkeypatch, rev=_rev_df(True), snaps={"202610": {}, "202611": {}})
        st = trend_rating_status(row)
        assert (not st.scorable) and st.partial and st.missing_legs == ("季財報",)   # ~~st.scorable~~（DEC-150）

    def test_malformed_snapshot_without_status_fields(self, monkeypatch):
        junk = {"foo": 1, "Survival_Module": {"x": "text"}}
        row = _row(monkeypatch, rev=None, snaps={"202610": junk, "202611": junk})
        assert not trend_rating_status(row).scorable

    def test_true_zero_score_is_not_mistaken_for_missing(self, monkeypatch):
        """月營收 YoY 平均恰 0（持平）＋ 季快照真的 diff 後不變 → score=0.0 但有真實輸入 → 可評分。"""
        row = _row(monkeypatch, rev=_rev_df(False), snaps={"202610": _PASS, "202611": _PASS})
        assert row["score"] == 0.0 and row["mon_detail"]["n_months"] == 3
        assert row["mon_detail"]["yoy_avg"] == 0.0
        st = trend_rating_status(row)
        assert st.scorable and not st.partial and st.reason_text == ""
        assert "合分 +0.00" in trend_prompt_line(row)           # 真 0 照舊呈現，不被誤抑制

    def test_legacy_rows_without_diff_verdict_fall_back_to_n_snapshots(self):
        """手工列（舊測試／舊 session cache）沒有 diff_verdict → 行為與舊 is_trend_scorable 相同。"""
        row = {"mon_detail": {"n_months": 0}, "fin_detail": {"n_snapshots": 2}}
        assert not is_trend_scorable(row)            # ~~assert is_trend_scorable(row)~~（DEC-150：缺月腿）
        assert is_trend_scorable({"mon_detail": {"n_months": 1}, "fin_detail": {"n_snapshots": 2}})
        assert not is_trend_scorable({"mon_detail": {}, "fin_detail": {}})
        assert not is_trend_scorable({})

    def test_error_row_is_unscorable(self):
        st = trend_rating_status({"label_code": "error"})
        assert not st.scorable and st.reason_text

    def test_thresholds_untouched(self):
        from shared.signal_thresholds import TREND_MIN_FIN_SNAPSHOTS, TREND_MIN_REVENUE_MONTHS
        assert (TREND_MIN_REVENUE_MONTHS, TREND_MIN_FIN_SNAPSHOTS) == (1, 2)


# ═══ ② 三消費端一致 ═══════════════════════════════════════════
class TestConsumersAgree:
    CASES = {
        "both_missing": dict(rev=None, snaps={}),
        "one_snap": dict(rev=None, snaps={"202611": _PASS}),
        "only_monthly": dict(rev="up", snaps={}),                      # DEC-150：單腿 → 一致判無法形成正式評級
        "only_fin": dict(rev=None, snaps={"202610": _FAIL, "202611": _PASS}),
        "empty_dicts": dict(rev=None, snaps={"202610": {}, "202611": {}}),
        "complete": dict(rev="up", snaps={"202609": _FAIL, "202610": _PASS, "202611": _PASS}),
    }

    @pytest.mark.parametrize("name", list(CASES))
    def test_combo_single_ai_same_verdict(self, monkeypatch, name):
        c = self.CASES[name]
        row = _row(monkeypatch, rev=_rev_df(True) if c["rev"] == "up" else None, snaps=c["snaps"])
        ok, bad = split_trend_rows([row])                       # 組合 Tab 用的切分
        st = trend_rating_status(row)                           # 單股 Tab 用
        line = trend_prompt_line(row)                           # AI prompt 用
        assert bool(ok) == st.scorable == (not line.startswith("財報趨勢資料不足"))
        assert bool(bad) == (not st.scorable)


# ═══ ③ 接線＋突變 ═════════════════════════════════════════════
_SEC = REPO / "src/ui/tabs/stock_sections/section_strategy_conclusion.py"
_TAB = REPO / "src/ui/tabs/tab_stock.py"
_GRP = REPO / "src/ui/tabs/tab_stock_grp.py"


def _fin_block(text: str) -> str:
    i = text.index("compute_one_stock_trend as _cost")
    return text[i: i + 4500]


class TestWiring:
    def test_single_tab_uses_shared_status(self):
        # DEC-150 QA 回修：橫幅 HTML 抽成 `build_fin_trend_banner_html`（同檔，行為測試見 test_fina_both_legs_required）
        txt = _SEC.read_text(encoding="utf-8")
        assert "trend_rating_status" in txt and "unscorable_label" in txt
        assert "build_fin_trend_banner_html(_fin_row)" in _fin_block(txt)

    def test_ai_prompt_uses_shared_line(self):
        txt = _TAB.read_text(encoding="utf-8")
        i = txt.index("compute_one_stock_trend as _cost_ai")
        blk = txt[i: i + 2500]
        assert "trend_prompt_line" in blk
        assert "財報趨勢分數(月+季 65/35)={_fin_row_ai.get('label'" not in blk   # 舊的直接餵 label 已移除

    def test_ai_prompt_no_silent_except_pass(self):
        txt = _TAB.read_text(encoding="utf-8")
        i = txt.index("compute_one_stock_trend as _cost_ai")
        blk = txt[i: i + 2500]
        j = blk.index("except Exception")
        handler = blk[j: blk.index("_fund_data2", j)]
        assert "[AI_FIN_TREND]" in handler and "print(" in handler
        assert not any(ln.strip() == "pass" for ln in handler.splitlines())

    def test_combo_tab_guard_still_present(self):
        g = _GRP.read_text(encoding="utf-8")
        assert "split_trend_rows" in g and "⚪ 無法評分" in g

    def test_mutation_removing_guard_turns_red(self, monkeypatch):
        """突變：改寫 `is_trend_scorable` 原始碼為『永遠可評分』，兩腿皆缺的列必須被測試抓到。

        （QA 回修：原版 monkeypatch 一個必然失敗的 lambda；現在改寫被測碼本身後 exec。）"""
        from tests._fina_mutants import load_mutant
        row = _row(monkeypatch, rev=None, snaps={})

        def check(mod):
            assert not mod.trend_rating_status(row).scorable
            assert mod.trend_prompt_line(row).startswith("財報趨勢資料不足")
        check(sc)
        mut = load_mutant("src/compute/screener/scorability.py",
                          "return _m >= int(min_months) and _s >= int(min_snapshots)", "return True")
        with pytest.raises(AssertionError):
            check(mut)

    def test_mutation_empty_dict_rule_removed_turns_red(self, monkeypatch):
        """突變：改寫原始碼拿掉『有效快照需有可比較指標』→ 空 dict 又被當證據（舊缺陷重現）。

        DEC-150：月腿須有效（rev=up），否則兩腿規則本身就擋下，看不出空 dict 規則有沒有被拿掉。"""
        from tests._fina_mutants import load_mutant
        row = _row(monkeypatch, rev=_rev_df(True), snaps={"202610": {}, "202611": {}})
        assert not is_trend_scorable(row)
        mut = load_mutant("src/compute/screener/scorability.py",
                          "if _n_cmp is not None and _n_cmp == 0:", "if False:")
        with pytest.raises(AssertionError):
            assert not mut.is_trend_scorable(row)
