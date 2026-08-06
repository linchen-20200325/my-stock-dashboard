"""tests/test_b5b_stock_grp.py — B5-b 🏆 個股組合：同頁三個互斥的候選數 + 假預設值。

實機症狀
========
同一畫面上「候選」有三個互相否定的數字，且其中一處靠「拿不到就給滿分」的預設值
決定生死。查證後的根因（file:line 見報告）：

1. `section_portfolio_summary` 頂部 KPI：分子取自 `score_t3`、分母取自 `results_t3`。
   `section_batch_fetcher` **只在 K 線非空時**才 append `score_t3`，抓不到 K 線的檔
   仍會進 `results_t3` → 兩個 list 長度不等 → 分子分母不同母體。
2. 同頁「③ 多因子評分排行」的結論句自己重算一次，分母改用 `len(score_t3)`
   → 同一個「≥70」在同頁出現兩個不同分母。
3. 「④ 汰弱留強」是第三種定義，且用 `r.get('健康度', 100)` —— 缺讀數預設**滿分**，
   方向與同檔另兩處的預設 0 相反。

修法：三處改吃同一支純函式 `src/compute/screener/scorability.summarize_candidates`
（§2.1 SSOT），且「沒資料」與「評出來很差」在型別上分開（§1）。

📊 財報趨勢 × 轉機同理：月營收與季快照皆缺時 `compute_trend_score` 回 score=0.0，
0.0 正好落在「➖ 中性」帶（±0.5）正中央 → 沒資料被講成「持平」。改標「⚪ 無法評分」。

測試策略
========
以**行為斷言**為主（建構輸入 → 呼叫函式 → 驗結果）。唯二的原始碼守衛用 **AST**
（排除 docstring / 註解，失敗訊息印該行原文），且只釘「不該再出現的呼叫形狀」，
不照抄實作字面。

3 個最容易出錯的輸入（本檔涵蓋）：
  1. `score_t3` 比 `results_t3` 短（抓不到 K 線）—— 就是三個數字打架的成因。
  2. 健康度缺讀數（None / NaN）—— 舊版預設 100 直接判「保留」。
  3. 月營收 + 季快照皆缺 —— 0.0 被當「中性」。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from shared.health_thresholds import HEALTH_GRADE_B_MIN
from shared.signal_thresholds import (
    MULTIFACTOR_ENTRY_MIN,
    TREND_MIN_FIN_SNAPSHOTS,
    TREND_MIN_REVENUE_MONTHS,
)
from src.compute.screener.scorability import (
    build_score_map,
    is_trend_scorable,
    split_trend_rows,
    summarize_candidates,
    trend_row_evidence,
)

_REPO = Path(__file__).resolve().parents[1]
_SUMMARY_PY = _REPO / 'src' / 'ui' / 'tabs' / 'stock_grp_sections' / 'section_portfolio_summary.py'
_AI_PY = _REPO / 'src' / 'ui' / 'tabs' / 'stock_grp_sections' / 'section_ai_portfolio.py'


# ══════════════════════════════════════════════════════════════
# 共用 fixture：重現「score_t3 比 results_t3 短」的實機情境
# ══════════════════════════════════════════════════════════════
def _results():
    """3 檔：A 健康且高分 / B 健康但低分 / C 抓不到 K 線（健康度 0、無多因子分）。"""
    return [
        {'stock_id': 'A', '代碼': 'A', '健康度': 85, '357評價': '🟢便宜'},
        {'stock_id': 'B', '代碼': 'B', '健康度': 60, '357評價': '🟡合理'},
        {'stock_id': 'C', '代碼': 'C', '健康度': 0, '357評價': '-',
         '_fetch_err': '無 K 線資料'},
    ]


def _scores():
    """只有 A / B 有多因子分（C 因無 K 線根本沒進 score_single_stock）。"""
    return [
        {'stock_id': 'A', 'total': 80.0, 'trend': 90, 'momentum': 70,
         'chip': 60, 'volume': 55, 'risk': 50, 'grade': 'A'},
        {'stock_id': 'B', 'total': 40.0, 'trend': 30, 'momentum': 35,
         'chip': 40, 'volume': 45, 'risk': 50, 'grade': 'C'},
    ]


# ══════════════════════════════════════════════════════════════
# 1. summarize_candidates — 同一頁只有一份候選數
# ══════════════════════════════════════════════════════════════
class TestCandidateStatsSingleSource:
    def test_denominator_is_scorable_population_not_total(self):
        """分母 = 可評分檔數（2），不是本批檔數（3）。這正是三個數字打架的成因。"""
        s = summarize_candidates(_results(), _scores())
        assert s.n_total == 3
        assert s.n_scored == 2
        assert s.n_unscored == 1
        assert s.unscored_ids == ('C',)
        assert s.n_scored != s.n_total, '本情境必須是「score 比 results 短」才有意義'

    def test_entry_pass_counts_only_scored(self):
        s = summarize_candidates(_results(), _scores())
        assert s.n_entry_pass == 1          # 只有 A(80) ≥ 70
        assert s.entry_min == MULTIFACTOR_ENTRY_MIN

    def test_denominator_equals_detail_table_row_count(self):
        """KPI 分母必須等於「③ 多因子評分排行」明細表的列數（同一母體，§2.1）。

        明細表用 `scoring_engine.rank_stocks`，故這裡真的呼叫它比長度。
        """
        from src.compute.scoring import rank_stocks
        s = summarize_candidates(_results(), _scores())
        assert len(rank_stocks(_scores())) == s.n_scored

    def test_error_entries_dropped_like_rank_stocks(self):
        """含 'error' 的評分列被丟掉 —— 與 rank_stocks 同一條規則，分母不會漂。"""
        from src.compute.scoring import rank_stocks
        _sc = _scores() + [{'stock_id': 'C', 'total': 0, 'error': '無資料'}]
        s = summarize_candidates(_results(), _sc)
        assert s.n_scored == 2 and 'C' in s.unscored_ids
        assert len(rank_stocks(_sc)) == s.n_scored

    def test_scored_ids_membership(self):
        s = summarize_candidates(_results(), _scores())
        assert s.is_scored('A') and s.is_scored('B')
        assert not s.is_scored('C')

    def test_bool_total_is_not_a_score(self):
        """True 會被 float() 轉成 1.0 —— 那不是分數，必須視為無分。"""
        s = summarize_candidates([{'stock_id': 'X', '健康度': 90}],
                                 [{'stock_id': 'X', 'total': True}])
        assert s.n_scored == 0 and s.unscored_ids == ('X',)

    def test_empty_inputs_do_not_crash(self):
        s = summarize_candidates([], [])
        assert (s.n_total, s.n_scored, s.n_entry_pass, s.n_unscored) == (0, 0, 0, 0)
        assert (s.n_kept, s.n_eliminated, s.n_health_unknown) == (0, 0, 0)

    def test_falls_back_to_daima_key(self):
        """只有 '代碼' 沒有 'stock_id' 的列也要能對上分數。"""
        s = summarize_candidates([{'代碼': 'Z', '健康度': 90}],
                                 [{'stock_id': 'Z', 'total': 99.0}])
        assert s.n_scored == 1 and s.n_entry_pass == 1

    def test_build_score_map_contract(self):
        m = build_score_map(_scores() + [{'stock_id': 'E', 'total': 9, 'error': 'x'},
                                         {'stock_id': 'F'},        # 無 total
                                         {'total': 50.0}])         # 無 stock_id
        assert m == {'A': 80.0, 'B': 40.0}


# ══════════════════════════════════════════════════════════════
# 2. 健康度缺讀數 —— 舊版預設 100 直接判「保留」（假綠燈引信）
# ══════════════════════════════════════════════════════════════
class TestHealthUnknownNotAssumedPerfect:
    def test_missing_health_is_neither_kept_nor_eliminated(self):
        s = summarize_candidates([{'stock_id': 'A'}], [])   # 無 '健康度' 欄
        assert s.n_health_unknown == 1 and s.health_unknown_ids == ('A',)
        assert s.n_kept == 0, '缺讀數不得預設滿分而判「保留」'
        assert s.n_eliminated == 0, '缺讀數也不得預設 0 而判「淘汰」'

    def test_nan_health_is_unknown(self):
        s = summarize_candidates([{'stock_id': 'A', '健康度': float('nan')}], [])
        assert s.n_health_unknown == 1 and s.n_kept == 0 and s.n_eliminated == 0

    def test_zero_health_is_a_real_reading_and_eliminated(self):
        """0 是**有讀數**（< 門檻）→ 淘汰；與「沒讀數」必須分得開。"""
        s = summarize_candidates([{'stock_id': 'A', '健康度': 0}], [])
        assert s.n_eliminated == 1 and s.eliminated_ids == ('A',)
        assert s.n_health_unknown == 0

    def test_threshold_boundary_uses_ssot(self):
        _at = summarize_candidates([{'stock_id': 'A', '健康度': HEALTH_GRADE_B_MIN}], [])
        _below = summarize_candidates(
            [{'stock_id': 'A', '健康度': HEALTH_GRADE_B_MIN - 1}], [])
        assert _at.n_kept == 1 and _at.n_eliminated == 0     # 等於門檻 → 保留
        assert _below.n_eliminated == 1                      # 低於門檻 → 淘汰
        assert _at.health_min == HEALTH_GRADE_B_MIN

    def test_expensive_valuation_eliminates_even_when_healthy(self):
        s = summarize_candidates(
            [{'stock_id': 'A', '健康度': 99, '357評價': '🔴超貴'}], [])
        assert s.eliminated_ids == ('A',) and s.n_kept == 0

    def test_kept_plus_eliminated_plus_unknown_equals_total(self):
        """三個桶互斥且窮盡 —— 這就是「同一頁不會再有第三種算法」的保證。"""
        s = summarize_candidates(_results(), _scores())
        assert s.n_kept + s.n_eliminated + s.n_health_unknown == s.n_total
        assert s.n_health_known == s.n_kept + s.n_eliminated

    def test_scoring_and_health_are_independent_axes(self):
        """有分數但沒健康度 / 有健康度但沒分數 —— 兩軸互不干擾。"""
        s = summarize_candidates(
            [{'stock_id': 'P', 'total_hint': 'no health'},          # 有分無健康度
             {'stock_id': 'Q', '健康度': 90}],                       # 有健康度無分
            [{'stock_id': 'P', 'total': 88.0}])
        assert s.is_scored('P') and not s.is_scored('Q')
        assert s.health_unknown_ids == ('P',)
        assert s.kept_ids == ('Q',)


# ══════════════════════════════════════════════════════════════
# 3. 財報趨勢：0.0 不是「中性」
# ══════════════════════════════════════════════════════════════
def _trend_row(sid, n_months, n_snapshots, **extra):
    row = {'sid': sid, 'label': '➖ 中性', 'label_code': 'neutral',
           'score': 0.0, 'mon_sub': 0.0, 'fin_sub': 0.0, 'note': '',
           'mon_detail': {'n_months': n_months},
           'fin_detail': {'n_snapshots': n_snapshots}}
    row.update(extra)
    return row


class TestTrendScorability:
    def test_no_revenue_and_no_snapshot_is_unscorable(self):
        assert is_trend_scorable(_trend_row('X', 0, 0)) is False

    def test_one_snapshot_alone_cannot_diff(self):
        """1 季快照無法 diff（需 2 季）→ 若月營收也缺 → 無法評分。"""
        assert is_trend_scorable(_trend_row('X', 0, 1)) is False

    def test_two_snapshots_is_scorable(self):
        assert is_trend_scorable(_trend_row('X', 0, TREND_MIN_FIN_SNAPSHOTS)) is True

    def test_revenue_alone_is_scorable(self):
        assert is_trend_scorable(_trend_row('X', TREND_MIN_REVENUE_MONTHS, 0)) is True

    def test_missing_detail_dicts_are_unscorable(self):
        assert is_trend_scorable({'sid': 'X'}) is False
        assert is_trend_scorable({'sid': 'X', 'mon_detail': None,
                                  'fin_detail': 'not-a-dict'}) is False

    def test_trend_row_evidence_defaults_to_zero(self):
        assert trend_row_evidence({}) == (0, 0)
        assert trend_row_evidence({'mon_detail': {'n_months': 3},
                                   'fin_detail': {'n_snapshots': 2}}) == (3, 2)

    def test_split_preserves_order_and_partitions(self):
        rows = [_trend_row('A', 3, 3), _trend_row('B', 0, 0), _trend_row('C', 0, 2)]
        ok, bad = split_trend_rows(rows)
        assert [r['sid'] for r in ok] == ['A', 'C']
        assert [r['sid'] for r in bad] == ['B']
        assert len(ok) + len(bad) == len(rows)

    def test_non_dict_rows_go_to_unscorable(self):
        ok, bad = split_trend_rows([None, 'x', _trend_row('A', 1, 0)])
        assert [r['sid'] for r in ok] == ['A'] and len(bad) == 2


class TestTrendZeroIsNotNeutral:
    """證明 bug 前提為真：缺料時 compute_trend_score 真的回 0.0 → 被判「中性」。"""

    def test_all_missing_scores_zero_and_labels_neutral(self):
        from src.compute.health.fin_trend_score import compute_trend_score
        out = compute_trend_score([], [])
        assert out['score'] == 0.0
        assert out['label_code'] == 'neutral', (
            '若這條掛了代表上游改過判定帶，本檔的「0.0 被當中性」前提要重審')
        # 同一份輸出餵進 is_trend_scorable → 必須被判為無法評分
        _row = {'sid': 'X', 'mon_detail': out['monthly_detail'],
                'fin_detail': out['fin_detail']}
        assert is_trend_scorable(_row) is False

    def test_ssot_min_snapshots_matches_upstream_behaviour(self):
        """TREND_MIN_FIN_SNAPSHOTS 不是憑空的 2 —— 真的打上游函式驗邊界。"""
        from src.compute.health.fin_trend_score import compute_fin_trend_subscore
        _snap = {'survival_module': {}, 'profitability_module': {}}
        _below, _d_below = compute_fin_trend_subscore(
            [_snap] * (TREND_MIN_FIN_SNAPSHOTS - 1))
        _at, _d_at = compute_fin_trend_subscore([_snap] * TREND_MIN_FIN_SNAPSHOTS)
        assert _below == 0.0 and _d_below.get('reason') == 'insufficient_snapshots'
        assert _d_at.get('reason') != 'insufficient_snapshots'
        assert _d_at.get('n_snapshots') == TREND_MIN_FIN_SNAPSHOTS


class TestFinVerdictCode:
    """`_fin_verdict_code`：0 季快照 ≠「首季」。"""

    @staticmethod
    def _fn():
        from src.ui.tabs.tab_stock_grp import _fin_verdict_code
        return _fin_verdict_code

    def test_uses_diff_verdict_when_present(self):
        class _V:
            verdict = 'improving'
        assert self._fn()(_trend_row('A', 3, 3, diff_verdict=_V())) == 'improving'

    def test_error_row_is_fetch_failed(self):
        row = _trend_row('A', 0, 0)
        row['label_code'] = 'error'
        assert self._fn()(row) == 'fetch_failed'

    def test_one_snapshot_is_first_snapshot(self):
        assert self._fn()(_trend_row('A', 0, 1)) == 'first_snapshot'

    def test_zero_snapshot_is_no_snapshot(self):
        assert self._fn()(_trend_row('A', 3, 0)) == 'no_snapshot'

    def test_every_returned_code_has_a_label(self):
        from src.ui.tabs.tab_stock_grp import _FIN_VERDICT_LABEL
        for row in (_trend_row('A', 0, 1), _trend_row('A', 3, 0)):
            assert self._fn()(row) in _FIN_VERDICT_LABEL
        _err = _trend_row('A', 0, 0)
        _err['label_code'] = 'error'
        assert self._fn()(_err) in _FIN_VERDICT_LABEL


# ══════════════════════════════════════════════════════════════
# 4. 多因子子維度欄必須是 score_single_stock 真的回傳的 key
# ══════════════════════════════════════════════════════════════
def _make_ohlcv(prices):
    n = len(prices)
    return pd.DataFrame({
        'close': [float(p) for p in prices],
        'open': [float(p) for p in prices],
        'high': [float(p) * 1.01 for p in prices],
        'low': [float(p) * 0.99 for p in prices],
        'volume': [1_000_000] * n,
    })


class TestMultifactorDimsAreReal:
    def test_dim_keys_exist_in_score_output_and_rs_score_does_not(self):
        """`rs_score` 從未被 score_single_stock 回傳 → 舊欄的 50 是捏造的。"""
        from src.compute.scoring import score_single_stock
        from src.ui.tabs.stock_grp_sections.section_portfolio_summary import _MF_DIMS
        out = score_single_stock(_make_ohlcv([100 + i for i in range(130)]), '2330', 'T')
        assert 'error' not in out
        for _label, _key in _MF_DIMS:
            assert _key in out, f'多因子子維度欄「{_label}」對應的 key {_key!r} 不存在於評分輸出'
        assert 'rs_score' not in out
        assert 'rs_up' not in out

    def test_dim_labels_do_not_claim_rs(self):
        from src.ui.tabs.stock_grp_sections.section_portfolio_summary import _MF_DIMS
        assert 'RS' not in [lbl for lbl, _ in _MF_DIMS]


# ══════════════════════════════════════════════════════════════
# 5. AST 守衛（排除 docstring / 註解；失敗訊息印該行原文）
# ══════════════════════════════════════════════════════════════
def _get_calls_with_default(path: Path, key_literal: str):
    """回 [(lineno, 該行原文)]：所有 `<expr>.get('<key_literal>', <default>)` 呼叫。

    走 AST 而非字串掃描 → docstring / 註解裡出現同樣字面**不會**誤報。
    """
    src = path.read_text(encoding='utf-8')
    lines = src.splitlines()
    hits = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == 'get'):
            continue
        if len(node.args) < 2:          # 沒帶 default → 不是我們要抓的形狀
            continue
        a0 = node.args[0]
        if isinstance(a0, ast.Constant) and a0.value == key_literal:
            hits.append((node.lineno, lines[node.lineno - 1].strip()))
    return hits


class TestNoFabricatedDefaults:
    def test_no_health_default_in_summary_section(self):
        """`健康度` 不得再帶任何 default（舊版 100 = 缺讀數判滿分）。"""
        hits = _get_calls_with_default(_SUMMARY_PY, '健康度')
        assert not hits, (
            '§1：健康度缺讀數必須標「未判定」，不得給預設值。'
            + ''.join(f'\n  {_SUMMARY_PY.name}:{ln}: {txt}' for ln, txt in hits))

    def test_no_rs_score_default_anywhere_in_grp_sections(self):
        """`rs_score` 是 score_single_stock 從未回傳的 key，帶 default = 捏造分數。"""
        hits = []
        for p in (_SUMMARY_PY, _AI_PY):
            hits += [(p.name, ln, txt) for ln, txt in _get_calls_with_default(p, 'rs_score')]
        assert not hits, (
            '§1/§3.3：rs_score 不存在於評分輸出，帶 default 等於憑空製造 RS 分。'
            + ''.join(f'\n  {n}:{ln}: {t}' for n, ln, t in hits))

    def test_no_phantom_result_keys_in_ai_prompt(self):
        """送給 LLM 的欄位不得讀 results_t3 沒有的 key（default 會每檔都生效）。"""
        hits = []
        for _k in ('rsi', 'ma_above', 'vcp_signal'):
            hits += [(_k, ln, txt) for ln, txt in _get_calls_with_default(_AI_PY, _k)]
        assert not hits, (
            '§1：section_batch_fetcher 寫入的是 RSI / 趨勢 / VCP，'
            '讀 rsi / ma_above / vcp_signal 會讓 default 每檔生效 → 餵 LLM 假資料。'
            + ''.join(f'\n  {_AI_PY.name}:{ln}: {t}（key={k!r}）' for k, ln, t in hits))


# ══════════════════════════════════════════════════════════════
# 6. 實機 render：三個區塊吃同一份 stats，數字一致
# ══════════════════════════════════════════════════════════════
def _grp_summary_script():
    """只跑三個渲染子函式（略過 _precompute_fund_map 的網路抓取）。"""
    from src.compute.screener.scorability import summarize_candidates as _sum
    from src.ui.tabs.stock_grp_sections import section_portfolio_summary as _sec

    _res = [
        {'stock_id': 'A', '代碼': 'A', '名稱': 'AA', '現價': '100.00',
         '健康度': 85, '_health': 85, '_val': '🟢便宜', '_trend': '多頭',
         '評級': '🟢A', '357評價': '🟢便宜', 'RSI': '55', 'KD': 'K50/D50'},
        {'stock_id': 'B', '代碼': 'B', '名稱': 'BB', '現價': '50.00',
         '健康度': 60, '_health': 60, '_val': '🟡合理', '_trend': '整理',
         '評級': '🟡B', '357評價': '🟡合理', 'RSI': '45', 'KD': 'K40/D40'},
        {'stock_id': 'C', '代碼': 'C', '名稱': 'CC', '現價': '-',
         '健康度': 0, '_health': 0, '_val': '-', '_trend': '-',
         '評級': '-', '357評價': '-', 'RSI': '-', 'KD': '-'},
    ]
    _sc = [
        {'stock_id': 'A', 'stock_name': 'AA', 'total': 80.0, 'trend': 90,
         'momentum': 70, 'chip': 60, 'volume': 55, 'risk': 50, 'grade': 'A'},
        {'stock_id': 'B', 'stock_name': 'BB', 'total': 40.0, 'trend': 30,
         'momentum': 35, 'chip': 40, 'volume': 45, 'risk': 50, 'grade': 'C'},
    ]
    _stats = _sum(_res, _sc)
    _sec._render_master_table(_res, _sc, {}, _stats)
    _sec._render_multifactor_dims(_sc)
    _sec._render_multifactor_ranking(_sc, {}, _stats)
    _sec._render_elimination_detail(_res, {}, _stats, gemini_call_fn=lambda *a, **k: '')


def _all_text(at) -> list[str]:
    out: list[str] = []
    for _name in ('markdown', 'caption', 'info', 'warning', 'error', 'success', 'text'):
        _seq = getattr(at, _name, None)
        if _seq is None:
            continue
        for _el in _seq:
            _v = getattr(_el, 'value', None)
            if isinstance(_v, str):
                out.append(_v)
    return out


@pytest.mark.slow
class TestGrpSummaryRendersConsistentNumbers:
    @classmethod
    def setup_class(cls):
        try:
            from streamlit.testing.v1 import AppTest  # noqa: F401
        except ImportError:
            pytest.skip('streamlit.testing.v1.AppTest 不可用(collection stub 生態)')

    def test_renders_without_exception_and_numbers_agree(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_function(_grp_summary_script).run(timeout=60)
        assert not at.exception, [f'{e.type}: {str(e.value)[:300]}' for e in at.exception]
        _txt = '\n'.join(_all_text(at))
        _entry = f'{MULTIFACTOR_ENTRY_MIN:.0f}'
        # ③ 結論的分母 = 可評分檔數 2（不是本批 3）
        assert f'1/2 支≥{_entry}分' in _txt, _txt[:1500]
        assert f'1/3 支≥{_entry}分' not in _txt, '分母又用回 results_t3 了'
        # 無法評分的檔要被明講，不是靜靜地變成 0 分
        assert '無法評分' in _txt
        # ④ 汰弱不得宣稱「全數通過」（C 健康度 0 → 淘汰）
        assert '全數通過汰弱篩選' not in _txt

    def test_master_table_marks_unscored_row(self):
        """🏆 組合排行總表：抓不到 K 線的 C 要留白 + 標「無法評分」，不是 0 分。"""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_function(_grp_summary_script).run(timeout=60)
        assert not at.exception, [f'{e.type}: {str(e.value)[:300]}' for e in at.exception]
        _master = None
        for _el in getattr(at, 'dataframe', []):
            _v = getattr(_el, 'value', None)
            if isinstance(_v, pd.DataFrame) and '綜合建議' in _v.columns:
                _master = _v
                break
        assert _master is not None, '找不到組合排行總表'
        _row_c = _master[_master['代碼'] == 'C']
        assert len(_row_c) == 1
        assert '無法評分' in str(_row_c['綜合建議'].iloc[0])
        assert pd.isna(_row_c['多因子'].iloc[0]), '無法評分的檔不得出現 0 分'
        # 有分的 A 仍是真分數，且排在無法評分的 C 之前
        assert _master['多因子'].iloc[0] == 80
        assert list(_master['代碼'])[-1] == 'C'
