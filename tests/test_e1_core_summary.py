"""E1 v19.185 — 核心總表(L0 契約 / L3 接線 / L4 渲染 / L6 時序)。

測試策略(刻意的取捨,寫在最前面免得下一個人踩同一個坑)
--------------------------------------------------------
1. **優先行為斷言**:絕大多數測試是「建構輸入 → 呼叫函式 → 驗結果」。
2. 只有 4 條測試用原始碼掃描,且**一律 AST**(不用字串比對):
   - 凍結欄位契約漂移(比對的是 `ast.literal_eval` 出來的**值**,不是字面);
   - L3 不得 import L5 / L6;
   - L4 不得讀 session_state / 不得 I/O;
   - L6 的**執行時序**(佔位早於 tabs、填充晚於 tabs)。
   前三條斷言的是「**不存在**某種依賴」,最後一條斷言的是行號順序 ——
   都不是「照抄實作字面」,所以實作改壞時它們會紅。
3. 三態(ok / unknown / failed)對 8 個 KPI **逐一**都測得到。

⚠️ 本檔內互相衝突的預期是**設計上不可能**的:每個 KPI 的三態由同一組共用建構子
   驅動(`_inputs_all_ok()` = ok 態、`CoreSummaryInputs()` = unknown 態、
   `_POISON_FIELD` = failed 態),不是各測試各寫一份自己的預期。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pandas as pd
import pytest

from shared.allocation_decision import build_allocation_decision
from shared.core_summary import (
    KPI_ALERTS,
    KPI_ALLOCATION,
    KPI_CANDIDATES,
    KPI_CAP,
    KPI_COVERAGE,
    KPI_FRESHNESS,
    KPI_FROZEN,
    KPI_LABELS,
    KPI_ORDER,
    KPI_REGIME,
    LIGHT_FAILED,
    LIGHT_UNKNOWN,
    NO_CAP_TEXT,
    OK_LIGHTS,
    UNKNOWN_VALUE_TEXT,
    CoreSummaryInputs,
    KpiCell,
    assemble_core_summary,
    cell_ok,
    fmt_have_total,
)
from shared.data_freshness import (
    FROZEN_STALE_PERIODS_LEADING,
    FROZEN_WATCH_COLS_LEADING,
    LEADING_DATE_COL,
)

_REPO = Path(__file__).resolve().parents[1]


# ══════════════════════════════════════════════════════════════════════════
# 共用輸入建構子 —— 所有測試共用同一份，杜絕「同一對象兩組互斥預期」
# ══════════════════════════════════════════════════════════════════════════
def _macro_state(regime: str = 'bull', health: float = 85.0,
                 exposure=None, is_loaded: bool = True) -> dict:
    """模擬 `allocation_service.get_macro_regime()` 的輸出。"""
    _light = {'bull': '🟢', 'neutral': '🟡', 'caution': '🔴', 'bear': '🔴'}
    return {
        'regime': regime, 'light': _light.get(regime, '⬜'),
        'source': 'bull:score', 'trend_regime': regime,
        'health': health, 'defense': False,
        'exposure_limit_pct': exposure, 'traffic_light': None,
        'is_loaded': is_loaded,
    }


def _allocation(regime: str = 'bull', health: float = 85.0, exposure=None):
    """走**真的** `build_allocation_decision`（不是假物件）—— 這樣格式化 SSOT
    的回歸（如 20–20%）才測得到。"""
    return build_allocation_decision(
        _macro_state(regime=regime, health=health, exposure=exposure))


#: `compute_tab_coverage()` 形狀的 4 列：3 列已評估（🟢🟡🔴）+ 1 列未載入（⬜）。
_COVERAGE_ROWS = [
    {'tab': '🌍 總經',   'emoji': '🟢', 'ratio_txt': '8/8',
     'fresh_emoji': '🟢', 'fresh_label': '最新'},
    {'tab': '📈 個股',   'emoji': '🟡', 'ratio_txt': '已查',
     'fresh_emoji': '🟡', 'fresh_label': '落後3日'},
    {'tab': '💰 籌碼面', 'emoji': '🔴', 'ratio_txt': '1/3',
     'fresh_emoji': '🔴', 'fresh_label': '落後9日'},
    {'tab': '🏦 ETF',    'emoji': '⬜', 'ratio_txt': '未查',
     'fresh_emoji': '⬜', 'fresh_label': '未載入'},
]


def _leading_df(frozen: bool = True) -> pd.DataFrame:
    """先行指標 df。`frozen=True` → 『外資』最後 N 期一階差分全為 0。"""
    _n = FROZEN_STALE_PERIODS_LEADING + 3
    _tail = [3.0] * (FROZEN_STALE_PERIODS_LEADING + 1)
    _alive = [float(i) for i in range(_n)]
    return pd.DataFrame({
        LEADING_DATE_COL: pd.date_range('2026-07-20', periods=_n, freq='D'),
        '外資': ([1.0, 2.0] + _tail)[:_n] if frozen else _alive,
        '投信': _alive,
    })


_ALERTS_HIT = {'items': [{'emoji': '🔴', 'text': 'VIX 32', 'severity': 0},
                         {'emoji': '🟡', 'text': 'PMI 47', 'severity': 1}],
               'n_red': 1, 'n_yellow': 1}
_ALERTS_CLEAN = {'items': [], 'n_red': 0, 'n_yellow': 0}


class _FakeStats:
    """`summarize_candidates()` 的 duck-typed 替身（L0 刻意不 import L2）。"""
    n_total = 12
    n_scored = 8
    n_entry_pass = 3
    n_unscored = 4
    entry_min = 70.0


def _inputs_all_ok() -> CoreSummaryInputs:
    return CoreSummaryInputs(
        macro_state=_macro_state(),
        allocation=_allocation(),
        coverage_rows=_COVERAGE_ROWS,
        leading_df=_leading_df(frozen=True),
        alerts=_ALERTS_HIT,
        alerts_threshold_scanned=True,
        candidate_stats=_FakeStats(),
    )


#: KPI → 「毒化哪一個輸入欄位可讓這一格變 failed」。
_POISON_FIELD = {
    KPI_REGIME:     'macro_state',
    KPI_ALLOCATION: 'allocation',
    KPI_CAP:        'allocation',
    KPI_ALERTS:     'alerts',
    KPI_FRESHNESS:  'coverage_rows',
    KPI_COVERAGE:   'coverage_rows',
    KPI_FROZEN:     'leading_df',
    KPI_CANDIDATES: 'candidate_stats',
}


def _replace(inputs: CoreSummaryInputs, **kw) -> CoreSummaryInputs:
    from dataclasses import replace
    return replace(inputs, **kw)


# ══════════════════════════════════════════════════════════════════════════
# A. 未載入（冷啟動）—— 一格綠燈都不准有，一個捏造數字都不准有
# ══════════════════════════════════════════════════════════════════════════
def test_cold_start_yields_exactly_eight_cells_in_order():
    _s = assemble_core_summary(CoreSummaryInputs())
    assert [c.key for c in _s.cells] == list(KPI_ORDER)
    assert len(_s.cells) == 8


def test_cold_start_every_cell_is_unknown():
    _s = assemble_core_summary(CoreSummaryInputs())
    assert _s.n_unknown == 8, [
        (c.key, c.status, c.value_text) for c in _s.cells if not c.is_unknown]
    assert _s.n_ok == 0 and _s.n_failed == 0


def test_cold_start_shows_no_green_light_and_no_fabricated_number():
    """§1:未載入時不得出現任何彩燈,也不得出現任何數字(數字 = 捏造值)。"""
    _s = assemble_core_summary(CoreSummaryInputs())
    for _c in _s.cells:
        assert _c.light == LIGHT_UNKNOWN, f'{_c.key} 未載入卻亮 {_c.light}'
        assert _c.light not in OK_LIGHTS
        assert _c.value_text == UNKNOWN_VALUE_TEXT
        assert not re.search(r'\d', _c.value_text), \
            f'{_c.key} 未載入卻印出數字：{_c.value_text!r}'


def test_cold_start_unknown_says_what_is_missing_and_how_to_fix():
    _s = assemble_core_summary(CoreSummaryInputs())
    for _c in _s.cells:
        _head = _c.explain[0]
        assert '缺「' in _head and '補法：' in _head, f'{_c.key}: {_head!r}'
        # 補法必須指得出具體去哪、按什麼，而不是空話
        assert ('🚀' in _head or '🔎' in _head or '🏆' in _head), _head


# ══════════════════════════════════════════════════════════════════════════
# B. 三態：每個 KPI 的 ok / unknown / failed 都測得到
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize('key', KPI_ORDER)
def test_every_kpi_reaches_ok_state(key):
    _cell = assemble_core_summary(_inputs_all_ok()).get(key)
    assert _cell is not None and _cell.is_ok, (key, _cell)
    assert _cell.light in OK_LIGHTS, f'{key} ok 態燈號 {_cell.light!r} 不是彩燈'
    assert _cell.value_text.strip()


@pytest.mark.parametrize('key', KPI_ORDER)
def test_every_kpi_reaches_unknown_state(key):
    _cell = assemble_core_summary(CoreSummaryInputs()).get(key)
    assert _cell is not None and _cell.is_unknown, (key, _cell)
    assert _cell.light == LIGHT_UNKNOWN


@pytest.mark.parametrize('key', KPI_ORDER)
def test_every_kpi_reaches_failed_state_with_original_exception_type(key):
    """§1:取數炸了要顯示 exception type,**不得**靜默退回「無法判定」。"""
    class _E1Boom(RuntimeError):
        pass

    _bad = _replace(_inputs_all_ok(), **{_POISON_FIELD[key]: _E1Boom('炸了')})
    _cell = assemble_core_summary(_bad).get(key)
    assert _cell is not None and _cell.is_failed, (key, _cell)
    assert _cell.light == LIGHT_FAILED
    assert '_E1Boom' in _cell.value_text, _cell.value_text
    assert _cell.value_text != UNKNOWN_VALUE_TEXT
    assert '炸了' in _cell.explain[0]


def test_one_failing_producer_does_not_break_the_other_cells():
    """任一 producer 拋例外 → 只有那一格失敗,整張表不得崩、其餘不得被連累。"""
    _bad = _replace(_inputs_all_ok(), leading_df=ValueError('li_latest 壞了'))
    _s = assemble_core_summary(_bad)
    assert len(_s.cells) == 8
    assert _s.n_failed == 1 and _s.get(KPI_FROZEN).is_failed
    for _c in _s.cells:
        if _c.key != KPI_FROZEN:
            assert _c.is_ok, (_c.key, _c.status, _c.value_text)


def test_builder_returning_non_cell_is_reported_as_failed(monkeypatch):
    """契約破了要看得見:builder 回非 KpiCell → failed,不是給一個空白格。"""
    import shared.core_summary as _cs
    monkeypatch.setattr(_cs, 'build_regime_cell', lambda *a, **k: '不是 KpiCell')
    _s = _cs.assemble_core_summary(_inputs_all_ok())
    _cell = _s.get(KPI_REGIME)
    assert _cell.is_failed and 'TypeError' in _cell.value_text


def test_headline_reports_unknown_and_failed_counts_honestly():
    _bad = _replace(CoreSummaryInputs(), leading_df=ValueError('x'))
    _s = assemble_core_summary(_bad)
    _h = _s.headline()
    assert f'{_s.n_ok} 項有結論' in _h
    assert f'{_s.n_unknown} 項未評估' in _h
    assert f'{_s.n_failed} 項取數失敗' in _h


# ══════════════════════════════════════════════════════════════════════════
# C. explain 與數字同源（allocation_decision「20–20%」那類 bug 的防線）
# ══════════════════════════════════════════════════════════════════════════
def _all_cells_in_all_states() -> list[KpiCell]:
    _cells: list[KpiCell] = []
    _cells += list(assemble_core_summary(_inputs_all_ok()).cells)
    _cells += list(assemble_core_summary(CoreSummaryInputs()).cells)
    for _k in KPI_ORDER:
        _bad = _replace(_inputs_all_ok(), **{_POISON_FIELD[_k]: KeyError('boom')})
        _cells.append(assemble_core_summary(_bad).get(_k))
    return _cells


@pytest.mark.parametrize('state', ['ok', 'unknown', 'failed'])
def test_explain_first_line_quotes_value_text(state):
    """畫面上的數字必須**逐字**出現在說明第一行。

    這是 `shared/allocation_decision.py:82-96` 那個 bug 的結構性防線:
    當時 `range_text` 與 drivers 各自組字串 → 線上印「最終 … → 20–20%」而
    卡片印「20%」。只要 explain 的第一行是由同一支 formatter 用 `value_text`
    本身組出來,兩者就不可能不一致。
    """
    if state == 'ok':
        _cells = list(assemble_core_summary(_inputs_all_ok()).cells)
    elif state == 'unknown':
        _cells = list(assemble_core_summary(CoreSummaryInputs()).cells)
    else:
        _cells = []
        for _k in KPI_ORDER:
            _bad = _replace(_inputs_all_ok(),
                            **{_POISON_FIELD[_k]: KeyError('boom')})
            _cells.append(assemble_core_summary(_bad).get(_k))
    for _c in _cells:
        assert _c.explain, f'{_c.key} 沒有任何 explain'
        assert _c.value_text in _c.explain[0], (
            f'{_c.key}: value_text={_c.value_text!r} 未出現在 '
            f'explain[0]={_c.explain[0]!r}')
        assert _c.label in _c.explain[0]


def test_display_text_is_light_plus_value_only():
    for _c in _all_cells_in_all_states():
        assert _c.display_text == f'{_c.light} {_c.value_text}'


def test_allocation_collapsed_range_prints_single_number_not_20_dash_20():
    """硬否決把區間壓成 lo == hi 時,不得出現「20–20%」。

    這條是**真的會抓到 bug** 的斷言 —— v19.175 P0-B 之前線上就是印
    「最終 = min(姿態 70%, 天花板 20%) → 20–20%」。
    """
    _alloc = _allocation(health=85.0, exposure=20)   # 姿態 80–100 被壓到 20
    assert _alloc.final_lo == _alloc.final_hi == 20
    _cell = assemble_core_summary(
        _replace(_inputs_all_ok(), macro_state=_macro_state(exposure=20),
                 allocation=_alloc)).get(KPI_ALLOCATION)
    assert _cell.is_ok
    assert _cell.value_text == '20%', _cell.value_text
    _dup = re.compile(r'(\d+)–\1%')          # 「N–N%」;80–100% 這種正常區間不算
    for _line in (_cell.value_text,) + tuple(_cell.explain):
        assert not _dup.search(_line), f'區間塌陷仍印成 N–N%：{_line!r}'


def test_cell_ok_refuses_unknown_or_failed_light():
    """`cell_ok` 是「假綠燈」的最後一道閘 —— 收到 ⬜/❌ 必須當場炸。"""
    for _bad_light in (LIGHT_UNKNOWN, LIGHT_FAILED, '', '🔵'):
        with pytest.raises(ValueError):
            cell_ok(KPI_REGIME, _bad_light, '多頭')


def test_cell_ok_refuses_empty_value_text():
    with pytest.raises(ValueError):
        cell_ok(KPI_REGIME, '🟢', '   ')


def test_fmt_have_total_is_the_only_ratio_formatter():
    assert fmt_have_total(3, 8) == '3/8（38%）'
    assert fmt_have_total(0, 0) == '0/0'        # 不除以零、不捏造 100%
    assert fmt_have_total(4, 4) == '4/4（100%）'


# ══════════════════════════════════════════════════════════════════════════
# D. 各 KPI 的個別行為
# ══════════════════════════════════════════════════════════════════════════
def test_regime_cell_uses_canonical_label_and_light():
    _c = assemble_core_summary(_inputs_all_ok()).get(KPI_REGIME)
    assert _c.value_text == '多頭' and _c.light == '🟢'
    assert 'bull:score' in '\n'.join(_c.explain)


def test_regime_disagreeing_with_allocation_becomes_failed_not_two_answers():
    """同畫面兩個相反的多空結論 = C1 要消滅的形狀 → 寧可失敗也不並列。"""
    _bad = _replace(_inputs_all_ok(),
                    macro_state=_macro_state(regime='bear', health=85.0))
    _c = assemble_core_summary(_bad).get(KPI_REGIME)
    assert _c.is_failed and 'ValueError' in _c.value_text
    assert 'regime 不同源' in _c.explain[0]


def test_cap_cell_writes_no_veto_explicitly_instead_of_blank():
    """無 cap 要**明寫**「無硬否決」—— 留白會被讀成漏算。"""
    _c = assemble_core_summary(_inputs_all_ok()).get(KPI_CAP)
    assert _c.is_ok and _c.value_text == NO_CAP_TEXT and _c.light == '🟢'


def test_cap_cell_uses_cap_text_ssot_when_capped():
    _alloc = _allocation(health=85.0, exposure=20)
    _c = assemble_core_summary(
        _replace(_inputs_all_ok(), macro_state=_macro_state(exposure=20),
                 allocation=_alloc)).get(KPI_CAP)
    assert _c.is_ok and _c.light == '🔴'
    assert _c.value_text == _alloc.cap_text        # 不是另外拼一份字串
    assert '20%' in _c.value_text


def test_alerts_empty_but_not_scanned_is_unknown_never_green():
    """v19.176 P0-A 假綠燈回歸鎖:空 items + 未掃描 ≠ 無異常。"""
    _c = assemble_core_summary(_replace(
        _inputs_all_ok(), alerts=_ALERTS_CLEAN,
        alerts_threshold_scanned=False)).get(KPI_ALERTS)
    assert _c.is_unknown and _c.light == LIGHT_UNKNOWN
    assert '未評估 ≠ 無異常' in '\n'.join(_c.explain)


def test_alerts_empty_and_scanned_is_green():
    _c = assemble_core_summary(_replace(
        _inputs_all_ok(), alerts=_ALERTS_CLEAN,
        alerts_threshold_scanned=True)).get(KPI_ALERTS)
    assert _c.is_ok and _c.light == '🟢'
    assert '無異常' in _c.value_text


def test_alerts_counts_red_and_yellow():
    _c = assemble_core_summary(_inputs_all_ok()).get(KPI_ALERTS)
    assert _c.is_ok and _c.light == '🔴'
    assert _c.value_text == '1 紅 / 1 黃（共 2 項）'


def test_alerts_with_items_but_unscanned_discloses_partial_scan():
    _c = assemble_core_summary(_replace(
        _inputs_all_ok(), alerts_threshold_scanned=False)).get(KPI_ALERTS)
    assert _c.is_ok
    assert '門檻層尚未評估' in '\n'.join(_c.explain)


def test_freshness_names_the_worst_source():
    """§1:整列取最差並**指名道姓**,不得被平均掉。"""
    _c = assemble_core_summary(_inputs_all_ok()).get(KPI_FRESHNESS)
    assert _c.is_ok and _c.light == '🔴'
    assert '籌碼面' in _c.value_text and '落後9日' in _c.value_text
    assert '另有 1 個分頁尚未載入' in '\n'.join(_c.explain)


def test_freshness_unknown_when_no_row_has_a_usable_date():
    _rows = [dict(r, fresh_emoji='⬜', fresh_label='無資料日期')
             for r in _COVERAGE_ROWS]
    _c = assemble_core_summary(
        _replace(_inputs_all_ok(), coverage_rows=_rows)).get(KPI_FRESHNESS)
    assert _c.is_unknown


def test_coverage_counts_full_tabs_and_discloses_pending_ones():
    _c = assemble_core_summary(_inputs_all_ok()).get(KPI_COVERAGE)
    assert _c.is_ok and _c.light == '🔴'          # 最差已評估列是 🔴 籌碼面
    assert fmt_have_total(1, 4) in _c.value_text  # 1/4（25%）
    assert '另 1 個分頁尚未載入' in _c.value_text


def test_coverage_unknown_when_every_tab_is_pending():
    _rows = [dict(r, emoji='⬜') for r in _COVERAGE_ROWS]
    _c = assemble_core_summary(
        _replace(_inputs_all_ok(), coverage_rows=_rows)).get(KPI_COVERAGE)
    assert _c.is_unknown


def test_coverage_and_freshness_come_from_the_same_rows():
    """兩格同源 → 不可能出現「覆蓋率說 4 個分頁、新鮮度說 3 個分頁」。"""
    _s = assemble_core_summary(_inputs_all_ok())
    _cov = '\n'.join(_s.get(KPI_COVERAGE).explain)
    _fre = '\n'.join(_s.get(KPI_FRESHNESS).explain)
    for _row in _COVERAGE_ROWS:
        assert _row['tab'] in _cov and _row['tab'] in _fre


def test_frozen_cell_names_the_frozen_columns():
    _c = assemble_core_summary(_inputs_all_ok()).get(KPI_FROZEN)
    assert _c.is_ok and _c.light == '🔴'
    assert '外資' in _c.value_text and '1 欄凍結' in _c.value_text
    assert '投信' not in _c.value_text          # 還在動的欄不得被點名


def test_frozen_cell_green_when_values_are_alive():
    _c = assemble_core_summary(_replace(
        _inputs_all_ok(), leading_df=_leading_df(frozen=False))).get(KPI_FROZEN)
    assert _c.is_ok and _c.light == '🟢' and _c.value_text == '無凍結欄位'


def test_frozen_cell_unknown_when_watch_columns_absent():
    """沒有可掃的欄 ≠ 沒凍結 —— 不得亮綠燈。"""
    _df = pd.DataFrame({LEADING_DATE_COL: pd.date_range('2026-08-01', periods=4),
                        '不相干欄': [1, 2, 3, 4]})
    _c = assemble_core_summary(
        _replace(_inputs_all_ok(), leading_df=_df)).get(KPI_FROZEN)
    assert _c.is_unknown


def test_frozen_detection_is_order_independent_because_helper_sorts():
    """`detect_frozen_columns` 要求 caller 先排序;helper 內建排序 → 亂序同答案。"""
    _df = _leading_df(frozen=True)
    _shuffled = _df.sample(frac=1.0, random_state=0)
    _a = assemble_core_summary(
        _replace(_inputs_all_ok(), leading_df=_df)).get(KPI_FROZEN)
    _b = assemble_core_summary(
        _replace(_inputs_all_ok(), leading_df=_shuffled)).get(KPI_FROZEN)
    assert _a.value_text == _b.value_text


def test_candidates_denominator_is_scored_not_total():
    """B5-b 回歸鎖:分母必須是 n_scored(算得出分的),不是 n_total。"""
    _c = assemble_core_summary(_inputs_all_ok()).get(KPI_CANDIDATES)
    assert _c.is_ok and _c.light == '🟡'          # 有無法評分的檔 → 黃
    assert fmt_have_total(3, 8) in _c.value_text  # 3/8（38%）
    assert '/12' not in _c.value_text             # n_total 不得當分母
    assert '4 檔無法評分' in '\n'.join(_c.explain)


def test_candidates_all_unscored_is_red_not_green():
    class _AllUnscored(_FakeStats):
        n_scored = 0
        n_entry_pass = 0
        n_unscored = 12

    _c = assemble_core_summary(_replace(
        _inputs_all_ok(), candidate_stats=_AllUnscored())).get(KPI_CANDIDATES)
    assert _c.is_ok and _c.light == '🔴'
    assert '全部無法評分' in _c.value_text


# ══════════════════════════════════════════════════════════════════════════
# E. L3 接線（依賴注入，不需要 streamlit runtime）
# ══════════════════════════════════════════════════════════════════════════
def _service():
    from src.services.core_summary_service import get_core_summary
    return get_core_summary


def test_service_empty_session_is_all_unknown_except_injected_ones():
    _s = _service()(session={}, macro_state=_macro_state(),
                    allocation=_allocation(), coverage_rows=_COVERAGE_ROWS)
    assert _s.get(KPI_REGIME).is_ok
    assert _s.get(KPI_ALLOCATION).is_ok
    assert _s.get(KPI_COVERAGE).is_ok and _s.get(KPI_FRESHNESS).is_ok
    # session 全空 → 這三格必須誠實未評估
    assert _s.get(KPI_ALERTS).is_unknown
    assert _s.get(KPI_FROZEN).is_unknown
    assert _s.get(KPI_CANDIDATES).is_unknown
    assert _s.n_failed == 0


def test_service_without_coverage_rows_marks_two_cells_unknown():
    """L3 不得 import L5 → 沒注入就誠實 ⬜,**不得**自己再算一份覆蓋率。"""
    _s = _service()(session={}, macro_state=_macro_state(),
                    allocation=_allocation())
    assert _s.get(KPI_COVERAGE).is_unknown
    assert _s.get(KPI_FRESHNESS).is_unknown
    assert 'compute_tab_coverage' in _s.get(KPI_COVERAGE).explain[0]


def test_service_threshold_scanned_flag_follows_macro_alerts_truthiness():
    """`macro_alerts` 為 None 或 [] 都是「未評估」,不得走綠燈分支。"""
    for _raw in (None, []):
        _s = _service()(session={'macro_alerts': _raw, 'macro_info': {}},
                        macro_state=_macro_state(), allocation=_allocation())
        assert _s.get(KPI_ALERTS).is_unknown, _raw


def test_service_wires_real_alert_rules_into_ok_state():
    _alerts_raw = [{'level': 'red', 'emoji': '🔴', 'label': 'VIX',
                    'value': 32, 'unit': '', 'message': '恐慌'}]
    _s = _service()(session={'macro_alerts': _alerts_raw, 'macro_info': {}},
                    macro_state=_macro_state(), allocation=_allocation())
    _c = _s.get(KPI_ALERTS)
    assert _c.is_ok and _c.light == '🔴' and '1 紅' in _c.value_text


def test_service_wires_candidate_stats_from_t3_data():
    """走**真的** `summarize_candidates`(不是假物件)—— 分母契約才測得到。"""
    _t3 = {
        'results': [{'stock_id': '2330', '健康度': 80, '357評價': '合理'},
                    {'stock_id': '1101', '健康度': 40, '357評價': '合理'}],
        'score_t3': [{'stock_id': '2330', 'total': 99.0}],
    }
    _s = _service()(session={'t3_data': _t3}, macro_state=_macro_state(),
                    allocation=_allocation())
    _c = _s.get(KPI_CANDIDATES)
    assert _c.is_ok
    assert '/1（' in _c.value_text, _c.value_text   # 分母 = 有分數的 1 檔
    assert '/2（' not in _c.value_text              # 不得用 results 列數當分母


def test_service_wires_leading_df_from_session():
    _s = _service()(session={'li_latest': _leading_df(frozen=True)},
                    macro_state=_macro_state(), allocation=_allocation())
    assert _s.get(KPI_FROZEN).is_ok and '外資' in _s.get(KPI_FROZEN).value_text


def test_service_survives_hostile_session_object():
    class _HostileSession:
        def get(self, *_a, **_k):
            raise RuntimeError('session 壞了')

    _s = _service()(session=_HostileSession(), macro_state=_macro_state(),
                    allocation=_allocation(), coverage_rows=_COVERAGE_ROWS)
    assert len(_s.cells) == 8            # 不得整張表崩掉
    assert _s.get(KPI_REGIME).is_ok


def test_service_triggers_no_http_fetch(monkeypatch):
    """核心總表只顯示『已經算過的東西』—— 一行 HTTP 都不准打。"""
    import urllib.request

    import requests

    # 先把 lazy import 全部暖機再上封鎖：這條測的是「呼叫期不打 HTTP」，
    # 不是「模組 import 期不打 HTTP」（後者由別的守衛負責，混在一起會誤判）。
    _fn = _service()
    _fn(session={'macro_alerts': [], 'macro_info': {},
                 't3_data': {'results': [{'stock_id': '0000'}], 'score_t3': []}},
        macro_state=_macro_state(), allocation=_allocation())

    def _boom(*_a, **_k):
        raise AssertionError('核心總表不得觸發任何 fetch')

    monkeypatch.setattr(requests.sessions.Session, 'request', _boom)
    monkeypatch.setattr(urllib.request, 'urlopen', _boom)
    _t3 = {'results': [{'stock_id': '2330', '健康度': 80}],
           'score_t3': [{'stock_id': '2330', 'total': 88.0}]}
    _s = _fn(
        session={'macro_alerts': [], 'macro_info': {},
                 'li_latest': _leading_df(), 't3_data': _t3},
        macro_state=_macro_state(), allocation=_allocation(),
        coverage_rows=_COVERAGE_ROWS)
    assert _s.n_failed == 0


# ══════════════════════════════════════════════════════════════════════════
# F. 架構守衛（全部 AST；斷言的是「不存在某依賴」與「行號順序」）
# ══════════════════════════════════════════════════════════════════════════
def _parse(rel: str) -> tuple[ast.Module, str]:
    _p = _REPO.joinpath(*rel.split('/'))
    _src = _p.read_text(encoding='utf-8')
    return ast.parse(_src), _src


def _imported_modules(tree: ast.Module) -> list[tuple[str, int]]:
    """所有 import 的模組名 + 行號（含函式內的 late import）。"""
    _out: list[tuple[str, int]] = []
    for _n in ast.walk(tree):
        if isinstance(_n, ast.Import):
            _out += [(a.name, _n.lineno) for a in _n.names]
        elif isinstance(_n, ast.ImportFrom):
            _out.append((_n.module or '', _n.lineno))
    return _out


def test_service_never_imports_ui_or_app_layer():
    """§8.2:L3 不得 import L5;且不得成為第 6 處 `from app import`。"""
    _tree, _src = _parse('src/services/core_summary_service.py')
    _lines = _src.splitlines()
    for _mod, _lineno in _imported_modules(_tree):
        assert not _mod.startswith('src.ui'), (
            f'L3 不得 import L5（第 {_lineno} 行）：{_lines[_lineno - 1].strip()}')
        assert _mod != 'app' and not _mod.startswith('app.'), (
            f'L3 不得 from app import（第 {_lineno} 行）：'
            f'{_lines[_lineno - 1].strip()}')


def test_render_reads_no_session_state_and_does_no_io():
    """§8.2 L4:純渲染。零 session_state 讀取、零 I/O、不 import L1/L5。"""
    _tree, _src = _parse('src/ui/render/core_summary_render.py')
    _lines = _src.splitlines()
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Attribute) and _n.attr == 'session_state':
            pytest.fail(f'L4 不得讀 session_state（第 {_n.lineno} 行）：'
                        f'{_lines[_n.lineno - 1].strip()}')
    _banned = ('requests', 'yfinance', 'FinMind', 'urllib', 'src.data', 'src.ui.pages')
    for _mod, _lineno in _imported_modules(_tree):
        assert not any(_mod == b or _mod.startswith(b + '.') for b in _banned), (
            f'L4 不得 import {_mod}（第 {_lineno} 行）：'
            f'{_lines[_lineno - 1].strip()}')


def _module_level_assign_value(tree: ast.Module, name: str):
    """取 module-level `name = <literal>` / `name: T = <literal>` 的值 + 節點。"""
    for _n in tree.body:
        if isinstance(_n, ast.Assign):
            for _t in _n.targets:
                if isinstance(_t, ast.Name) and _t.id == name:
                    return ast.literal_eval(_n.value), _n
        elif isinstance(_n, ast.AnnAssign) and isinstance(_n.target, ast.Name) \
                and _n.target.id == name and _n.value is not None:
            return ast.literal_eval(_n.value), _n
    return None, None


def test_frozen_watch_contract_does_not_drift_from_data_coverage():
    """凍結欄位契約只准有一份答案。

    `src/ui/pages/data_coverage.py`(L5)有一份私有副本,本檔的 SSOT 在
    `shared/data_freshness.py`(L0)。兩份**值**不相等 → 同一份 li_latest 會在
    診斷頁與核心總表得到互相否定的凍結欄數。比對的是 `literal_eval` 出來的
    值,不是原始碼字面 —— 註解 / 排版 / 換行怎麼改都不影響。

    若該檔已改成直接 import L0 SSOT(副本消失)→ 本測試改驗那條 import。
    """
    _tree, _src = _parse('src/ui/pages/data_coverage.py')
    _expected = {
        '_LI_FROZEN_WATCH_COLS': FROZEN_WATCH_COLS_LEADING,
        '_LI_FROZEN_STALE_PERIODS': FROZEN_STALE_PERIODS_LEADING,
        '_LI_DATE_COL': LEADING_DATE_COL,
    }
    _found_any = False
    for _name, _want in _expected.items():
        _value, _node = _module_level_assign_value(_tree, _name)
        if _node is None:
            continue
        _found_any = True
        assert _value == _want, (
            f'凍結契約漂移：data_coverage.{_name} = {_value!r}，'
            f'但 shared/data_freshness SSOT = {_want!r}。\n'
            f'該檔第 {_node.lineno} 行原文：\n'
            f'{ast.get_source_segment(_src, _node)}')
    if not _found_any:
        _mods = {m for m, _ in _imported_modules(_tree)}
        assert 'shared.data_freshness' in _mods, (
            'data_coverage.py 既沒有 _LI_FROZEN_* 私有副本，也沒有 import '
            'shared.data_freshness —— 凍結契約失去單一出處，請修守衛或修實作。')


def test_app_places_core_summary_placeholder_before_tabs_and_fills_after():
    """L6 時序守衛(v19.171 🔴-1 同款事故的回歸鎖)。

    佔位 `st.empty()` 必須在 `st.tabs(...)` **之前**(版面在最上方),
    填充 `_core_summary_slot.container()` 必須在 `st.tabs(...)` **之後**
    (那時 tab 才把 warroom_summary / macro_alerts / li_latest 寫進 session)。
    順序一旦被改回去,總表就會永遠停在「⬜ 未評估」。
    """
    _tree, _src = _parse('app.py')
    _lines = _src.splitlines()

    _placeholder_ln = None
    _tabs_ln = None
    _fill_ln = None
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Assign):
            for _t in _n.targets:
                if isinstance(_t, ast.Name) and _t.id == '_core_summary_slot':
                    _placeholder_ln = _n.lineno
                if isinstance(_t, ast.Tuple) and any(
                        isinstance(_e, ast.Name) and _e.id == 'tab_market'
                        for _e in _t.elts):
                    _tabs_ln = _n.lineno
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute):
            _v = _n.func.value
            if isinstance(_v, ast.Name) and _v.id == '_core_summary_slot' \
                    and _n.func.attr == 'container':
                _fill_ln = _n.lineno

    assert _placeholder_ln is not None, 'app.py 找不到 `_core_summary_slot` 佔位'
    assert _tabs_ln is not None, 'app.py 找不到主 tabs 的 `st.tabs(...)` 指派'
    assert _fill_ln is not None, 'app.py 找不到 `_core_summary_slot.container()` 填充'
    assert _placeholder_ln < _tabs_ln, (
        f'佔位（第 {_placeholder_ln} 行）必須在 tabs（第 {_tabs_ln} 行）之前：\n'
        f'{_lines[_placeholder_ln - 1].strip()}')
    assert _fill_ln > _tabs_ln, (
        f'填充（第 {_fill_ln} 行）必須在 tabs（第 {_tabs_ln} 行）之後，'
        f'否則會讀到 tab render 前的空 session：\n'
        f'{_lines[_fill_ln - 1].strip()}')


def test_kpi_labels_cover_every_kpi_in_order():
    assert set(KPI_ORDER) == set(KPI_LABELS)
    assert len(KPI_ORDER) == len(set(KPI_ORDER)) == 8
