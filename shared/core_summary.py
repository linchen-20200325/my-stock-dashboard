"""shared/core_summary.py — 核心總表資料契約 + 三態 SSOT(L0 純函式,E1 v19.185)。

為什麼需要這個模組
------------------
使用者要求「頂層放核心總表提供最高階整體概況與 KPI」。但本 session 稽核出的最高頻
缺陷不是版面問題,而是 **同一個量被算好幾次、母體不同、答案互相否定**:

- 建議持股 %：同畫面 6 套結論(v19.170 P0-1)
- 大盤 regime：4 個各自為政的 producer(C1 v19.182)
- 個股組合候選數：同頁 3 個互斥算式(B5-b)
- 「今日關鍵」空 items 被當成「無異常」亮綠燈(v19.176 P0-A)

總表若只是「把各頁的數字抄過來再排版一次」,它會變成第 7 個矛盾來源。因此本模組
把 **「一個 KPI 一個 producer」變成結構性強制**:

1. 每個 KPI 只有一支 builder,builder 只吃 **既有 SSOT producer 的輸出**
   (`AllocationDecision` / `get_macro_state()` / `collect_key_alerts()` /
    `summarize_candidates()` / `compute_tab_coverage()` / `detect_frozen_columns`),
   **一律不自己重算**。
2. 每個 KPI 的顯示字串一律由本檔的 `cell_ok` / `cell_unknown` / `cell_failed`
   三支 **唯一 formatter** 產生 —— UI 端(L4)一個說明字串都不准自己寫。

第 2 點治的是 `shared/allocation_decision.py` 檔頭記錄的那個 bug:同一個檔案裡
`range_text` 有「lo == hi 就只印一個數字」的收斂邏輯,`build_allocation_decision`
組 drivers 時卻另用 raw f-string 拼區間 → 線上印出「→ 20–20%」。
**SSOT 模組內部沒有自我一致**。本檔的防線是:`explain` 的第一行由 formatter
用 `value_text` 本身組出來,故「數字」與「說明裡的數字」在型別上不可能不同 ——
`tests/test_e1_core_summary.py::test_explain_first_line_quotes_value_text`
對每個 cell、每種狀態都釘這條。

三態契約(§1 Fail Loud, Never Fake)
----------------------------------
========  ======  ========================================================
status    light   語意
========  ======  ========================================================
`ok`      🟢🟡🔴  **算過且有結論**。light 永遠是彩燈,**不得**是 ⬜/❌。
`unknown` ⬜      **無法判定**:未載入 / 樣本不足 / 缺前置資料。
                  必須說明「缺什麼」+「怎麼補」。
`failed`  ❌      **取數炸了**:顯示 exception type,
                  **不得**靜默退回 `unknown`。
========  ======  ========================================================

⚠️「沒算過」絕不等於「沒問題」。本 session 修掉的假綠燈幾乎全是這個錯,所以
`cell_ok()` 會在收到 ⬜/❌ 當 light 時 **raise** —— 讓「未評估偽裝成有結論」在
建構當下就炸掉,而不是等使用者看到假綠燈。

分層(§8.2)
-----------
L0 Infra:只 import `shared.*`(`allocation_decision` / `regime_arbiter` /
`data_freshness`),零 L1+ 依賴、不 import streamlit、無 I/O。
`CandidateStats`(L2)與 coverage rows(L5 產出)一律以 **duck-typing / plain dict**
接收,**不 import** 產生它們的模組 —— 這是 L0 不得依賴 L1+ 的硬規則要求。

caller::

    from shared.core_summary import CoreSummaryInputs, assemble_core_summary
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

# L0 → L0 只。
from shared.allocation_decision import REGIME_LABEL
from shared.data_freshness import (
    FROZEN_STALE_PERIODS_LEADING,
    FROZEN_WATCH_COLS_LEADING,
    leading_frozen_columns,
    worst_freshness,
)
from shared.regime_arbiter import light_for_regime

# ── 三態 SSOT ──────────────────────────────────────────────────────────────
STATUS_OK: str = 'ok'
STATUS_UNKNOWN: str = 'unknown'
STATUS_FAILED: str = 'failed'

LIGHT_UNKNOWN: str = '⬜'
LIGHT_FAILED: str = '❌'

#: 允許出現在 `status='ok'` 的 cell 上的燈號。⬜/❌ **刻意排除**。
OK_LIGHTS: frozenset[str] = frozenset({'🟢', '🟡', '🟠', '🔴'})

#: `status='unknown'` 的 value 文字。全站一份,避免各處寫成「未評估/尚未評估/--」。
UNKNOWN_VALUE_TEXT: str = '未評估'

#: 已判定的覆蓋率 / 新鮮度燈號(⬜ 代表該列還沒被評估,不算「已判定」)。
_ASSESSED_LIGHTS: frozenset[str] = frozenset({'🟢', '🟡', '🔴'})

# ── KPI 識別碼 + 顯示名(顯示順序 = KPI_ORDER)───────────────────────────────
KPI_REGIME: str = 'regime'
KPI_ALLOCATION: str = 'allocation'
KPI_CAP: str = 'cap'
KPI_ALERTS: str = 'alerts'
KPI_FRESHNESS: str = 'freshness'
KPI_COVERAGE: str = 'coverage'
KPI_FROZEN: str = 'frozen'
KPI_CANDIDATES: str = 'candidates'

KPI_LABELS: dict[str, str] = {
    KPI_REGIME:     '總經燈號',
    KPI_ALLOCATION: '建議持股',
    KPI_CAP:        '硬否決天花板',
    KPI_ALERTS:     '今日關鍵警示',
    KPI_FRESHNESS:  '資料新鮮度（最差源）',
    KPI_COVERAGE:   '資料覆蓋率',
    KPI_FROZEN:     '值凍結告警',
    KPI_CANDIDATES: '個股組合候選',
}

#: 由「結論」到「資料品質」由上而下 —— 使用者先看結論,再看這些結論可不可信。
KPI_ORDER: tuple[str, ...] = (
    KPI_REGIME, KPI_ALLOCATION, KPI_CAP, KPI_ALERTS,
    KPI_FRESHNESS, KPI_COVERAGE, KPI_FROZEN, KPI_CANDIDATES,
)

#: 無硬否決天花板時的顯示文字。**明寫**而非留白 —— 留白會被讀成「漏算」。
NO_CAP_TEXT: str = '無硬否決'

#: 各 KPI 未評估時的統一補法提示(缺什麼 → 怎麼補)。
_FIX_MACRO: str = '開啟「🌍 市場環境 → 🌍 總經」並按「🚀 一鍵更新全部數據」'
_FIX_DIAG: str = '開啟「🔧 工具箱 → 🔎 資料診斷」查看逐項覆蓋率 / 新鮮度'
_FIX_GRP: str = '開啟「🔬 選股 → 🏆 個股組合」輸入代號後按「🚀 批次分析」'


# ══════════════════════════════════════════════════════════════════════════
# 顯示格式化 —— **本檔唯一實作**(§3.3 反捏造 / allocation_decision 教訓)
# ══════════════════════════════════════════════════════════════════════════
def fmt_have_total(have: int, total: int) -> str:
    """`(3, 8)` → `'3/8（38%）'`;`total <= 0` → `'0/0'`(不除以零、不捏造 100%)。

    分子/分母一律由同一支 formatter 出字,避免「KPI 卡寫 3/8、說明寫 3/12」
    這種同頁不同母體(B5-b 的原始病灶)。
    """
    _h, _t = int(have), int(total)
    if _t <= 0:
        return f'{_h}/{_t}'
    return f'{_h}/{_t}（{round(_h / _t * 100)}%）'


def fmt_col_list(names: Sequence[Any], *, sep: str = '、') -> str:
    """欄名/來源名清單 → `'外資、投信、自營'`;空 → `'（無）'`。"""
    _n = [str(x) for x in (names or []) if str(x)]
    return sep.join(_n) if _n else '（無）'


# ══════════════════════════════════════════════════════════════════════════
# 資料契約
# ══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class KpiCell:
    """核心總表的一格。**唯讀**;UI 只准渲染,不准再加工。

    Attributes:
        key:        KPI 識別碼(`KPI_*`)。
        label:      顯示名(`KPI_LABELS`)。
        status:     `STATUS_OK` / `STATUS_UNKNOWN` / `STATUS_FAILED`。
        light:      燈號 emoji。ok → 彩燈;unknown → ⬜;failed → ❌。
        value_text: 這一格的**結論字串**(不含 light,避免畫面重複兩個 emoji)。
        explain:    「這個數字怎麼來的」。第一行由 formatter 組出,**必定包含**
                    `value_text` 逐字 —— UI 端因此不需要、也不得自寫說明。
    """
    key: str
    label: str
    status: str
    light: str
    value_text: str
    explain: tuple[str, ...] = ()

    @property
    def is_ok(self) -> bool:
        return self.status == STATUS_OK

    @property
    def is_unknown(self) -> bool:
        return self.status == STATUS_UNKNOWN

    @property
    def is_failed(self) -> bool:
        return self.status == STATUS_FAILED

    @property
    def display_text(self) -> str:
        """`'🟢 多頭'` —— 畫面上那一格要印的完整字串(唯一出處)。"""
        return f'{self.light} {self.value_text}'


@dataclass(frozen=True)
class CoreSummary:
    """一次組裝的完整核心總表。"""
    cells: tuple[KpiCell, ...] = ()

    def get(self, key: str) -> Optional[KpiCell]:
        for _c in self.cells:
            if _c.key == key:
                return _c
        return None

    @property
    def n_ok(self) -> int:
        return sum(1 for c in self.cells if c.is_ok)

    @property
    def n_unknown(self) -> int:
        return sum(1 for c in self.cells if c.is_unknown)

    @property
    def n_failed(self) -> int:
        return sum(1 for c in self.cells if c.is_failed)

    def headline(self) -> str:
        """一行狀態摘要。**未評估與失敗一律照實報數**,不藏。"""
        return (f'{self.n_ok} 項有結論 ｜ {self.n_unknown} 項未評估 ｜ '
                f'{self.n_failed} 項取數失敗')


@dataclass(frozen=True)
class CoreSummaryInputs:
    """組裝核心總表所需的全部輸入。**每一項都是既有 producer 的輸出**。

    任一欄位可以放一個 `BaseException` —— 代表「L3 取這項時炸了」。builder 會
    把它原樣 re-raise,由 `assemble_core_summary` 轉成 `failed` cell,**保留原始
    例外型別**(不是包成 AttributeError 之類的二手錯誤)。
    """
    #: `allocation_service.get_macro_regime()` 的 dict。
    macro_state: Any = None
    #: `allocation_service.get_allocation()` 的 `AllocationDecision`。
    allocation: Any = None
    #: `data_coverage.compute_tab_coverage()` 的 list[dict]。
    #: **L0/L3 不得自行重算** —— 見模組 docstring 與 service 的注入說明。
    coverage_rows: Any = None
    #: `session_state['li_latest']` DataFrame。
    leading_df: Any = None
    #: `collect_key_alerts()` 的 dict。
    alerts: Any = None
    #: 門檻層這一輪**是否真的評估過** = `bool(session_state['macro_alerts'])`。
    #: 契約與 `macro_ui_components.key_alerts_banner(threshold_scanned=...)` 相同。
    alerts_threshold_scanned: bool = False
    #: `summarize_candidates()` 的 `CandidateStats`(duck-typed,不 import L2)。
    candidate_stats: Any = None


# ══════════════════════════════════════════════════════════════════════════
# 三支唯一 formatter —— 所有 cell 都必須經由它們產生
# ══════════════════════════════════════════════════════════════════════════
def cell_ok(key: str, light: str, value_text: str,
            explain: Sequence[str] = ()) -> KpiCell:
    """有值:算過且有結論。

    Raises:
        ValueError: `light` 是 ⬜/❌ 或不在 `OK_LIGHTS` —— 「未評估偽裝成有結論」
            必須在建構當下就炸,而不是變成畫面上的假綠燈(§1)。
        ValueError: `value_text` 為空 —— 空字串在畫面上等同留白,會被讀成漏算。
    """
    _label = KPI_LABELS.get(key, key)
    if light not in OK_LIGHTS:
        raise ValueError(
            f'cell_ok({key}) 收到非結論燈號 {light!r}；'
            f'⬜/❌ 請改用 cell_unknown / cell_failed（§1 禁止假綠燈）')
    if not str(value_text).strip():
        raise ValueError(f'cell_ok({key}) 的 value_text 為空 —— 留白會被讀成漏算')
    _head = f'{_label}：{light} {value_text}'
    return KpiCell(key=key, label=_label, status=STATUS_OK, light=light,
                   value_text=str(value_text), explain=(_head,) + tuple(explain))


def cell_unknown(key: str, *, missing: str, how_to_fix: str,
                 explain: Sequence[str] = ()) -> KpiCell:
    """無法判定:未載入 / 樣本不足 / 缺前置資料。

    `missing` 與 `how_to_fix` 都是**必填** —— 一格 ⬜ 若不說「缺什麼、怎麼補」,
    使用者只會以為系統壞了(或更糟:以為沒問題)。
    """
    _label = KPI_LABELS.get(key, key)
    _head = (f'{_label}：{LIGHT_UNKNOWN} {UNKNOWN_VALUE_TEXT} — '
             f'缺「{missing}」；補法：{how_to_fix}')
    return KpiCell(key=key, label=_label, status=STATUS_UNKNOWN,
                   light=LIGHT_UNKNOWN, value_text=UNKNOWN_VALUE_TEXT,
                   explain=(_head,) + tuple(explain))


def cell_failed(key: str, exc: BaseException,
                explain: Sequence[str] = ()) -> KpiCell:
    """失敗:取數炸了。**顯示 exception type,不得靜默退回「無法判定」**。"""
    _label = KPI_LABELS.get(key, key)
    _type = type(exc).__name__
    _value = f'取數失敗（{_type}）'
    _msg = str(exc).strip() or '（例外無訊息）'
    _head = f'{_label}：{LIGHT_FAILED} {_value} — {_msg[:300]}'
    return KpiCell(key=key, label=_label, status=STATUS_FAILED,
                   light=LIGHT_FAILED, value_text=_value,
                   explain=(_head,) + tuple(explain))


def _raise_if_error(value: Any) -> None:
    """輸入本身就是例外(L3 取數失敗)→ 原樣拋,保留原始型別給 `cell_failed`。"""
    if isinstance(value, BaseException):
        raise value


def _finite(value: Any) -> Optional[float]:
    """None / 非數字 / NaN / inf → None(§1:不捏造 0)。"""
    try:
        _f = float(value)
    except (TypeError, ValueError):
        return None
    if _f != _f or _f in (float('inf'), float('-inf')):
        return None
    return _f


def _dict_rows(rows: Any) -> list[dict]:
    return [r for r in (rows or []) if isinstance(r, dict)]


# ══════════════════════════════════════════════════════════════════════════
# 8 個 KPI builder —— 每支只吃既有 producer 的輸出,一律不重算
# ══════════════════════════════════════════════════════════════════════════
def build_regime_cell(macro_state: Any, allocation: Any = None) -> KpiCell:
    """KPI 1｜總經燈號 / regime。producer:`allocation_service.get_macro_regime()`。

    另做一條 **同源一致性斷言**:`macro_state['regime']` 與
    `AllocationDecision.regime` 都源自同一次 `get_macro_state()`,兩者若不同
    代表有人繞過 SSOT 塞了第二個 regime → 直接 raise 變成 `failed` cell,
    而不是讓畫面同時印出兩個相反的多空結論(C1 v19.182 要消滅的形狀)。
    """
    _raise_if_error(macro_state)
    _raise_if_error(allocation)
    if not isinstance(macro_state, dict) or not macro_state.get('is_loaded'):
        return cell_unknown(
            KPI_REGIME,
            missing='總經評估結果（warroom_summary / macro_state.json 皆無有效值）',
            how_to_fix=_FIX_MACRO)

    _regime = str(macro_state.get('regime') or 'unknown').strip().lower()
    if _regime == 'unknown':
        return cell_unknown(
            KPI_REGIME,
            missing='可判定的市場 regime（總經標記已載入但未產生結論）',
            how_to_fix=_FIX_MACRO)

    if allocation is not None and getattr(allocation, 'is_loaded', False):
        _alloc_regime = str(getattr(allocation, 'regime', '') or '').strip().lower()
        if _alloc_regime and _alloc_regime != _regime:
            raise ValueError(
                f'regime 不同源：get_macro_regime()={_regime!r} 但 '
                f'AllocationDecision.regime={_alloc_regime!r} —— '
                '兩者應同出自 get_macro_state()，出現分歧代表有人繞過 SSOT')

    _light = str(macro_state.get('light') or '') or light_for_regime(_regime)
    if _light not in OK_LIGHTS:
        _light = light_for_regime(_regime)
    if _light not in OK_LIGHTS:
        return cell_unknown(
            KPI_REGIME,
            missing=f'可對應燈號的 regime（收到 {_regime!r}）',
            how_to_fix=_FIX_MACRO)

    _health = _finite(macro_state.get('health'))
    _extra = [f'判定分支：{macro_state.get("source") or "（未提供）"}']
    _extra.append(f'總經健康分：{_health:.0f}' if _health is not None
                  else '總經健康分：未提供（不影響本格燈號，但姿態油門會退為未評估）')
    _trend = macro_state.get('trend_regime')
    if _trend:
        _extra.append(f'趨勢面輸入 trend_regime={_trend}（僅為輸入，非結論）')
    return cell_ok(KPI_REGIME, _light, REGIME_LABEL.get(_regime, _regime), _extra)


def build_allocation_cell(allocation: Any) -> KpiCell:
    """KPI 2｜建議持股區間。producer:`AllocationDecision.range_text`(唯一出處)。

    `explain` **直接用 `AllocationDecision.drivers`**,一個字都不重寫 ——
    `section_traffic_light.py` 的「📖 為何是這個持股數字？」也是這樣做的,
    兩個畫面因此不可能給出不同的推導說明。
    """
    _raise_if_error(allocation)
    if allocation is None:
        return cell_unknown(
            KPI_ALLOCATION,
            missing='建議持股決策（AllocationDecision）',
            how_to_fix=_FIX_MACRO)
    _drivers = tuple(getattr(allocation, 'drivers', ()) or ())
    if not getattr(allocation, 'is_loaded', False):
        return cell_unknown(
            KPI_ALLOCATION, missing='總經評估結果（姿態油門的唯一輸入是健康分）',
            how_to_fix=_FIX_MACRO, explain=_drivers)
    if getattr(allocation, 'final_lo', None) is None or \
            getattr(allocation, 'final_hi', None) is None:
        return cell_unknown(
            KPI_ALLOCATION, missing='最終持股區間（is_loaded 為真但 final_* 為 None）',
            how_to_fix=_FIX_MACRO, explain=_drivers)

    _light = str(getattr(allocation, 'icon', '') or '')
    if _light not in OK_LIGHTS:
        _light = light_for_regime(getattr(allocation, 'regime', ''))
    # range_text 是顯示格式的 SSOT（含 lo == hi 收斂），drivers 末行走同一支
    # `_fmt_range` → 兩者永遠一致，不會再出現「20%」vs「20–20%」。
    return cell_ok(KPI_ALLOCATION, _light, str(allocation.range_text), _drivers)


def build_cap_cell(allocation: Any) -> KpiCell:
    """KPI 3｜生效的硬否決天花板。producer:`AllocationDecision.cap_text/capped`。

    無 cap 一律**明寫**「無硬否決」(`NO_CAP_TEXT`)—— 留白會被讀成「這裡漏算了」。
    """
    _raise_if_error(allocation)
    if allocation is None or not getattr(allocation, 'is_loaded', False):
        return cell_unknown(
            KPI_CAP, missing='總經評估結果（未評估時不存在「生效的天花板」）',
            how_to_fix=_FIX_MACRO)

    _caps = tuple(getattr(allocation, 'caps', ()) or ())
    _cap_pct = getattr(allocation, 'cap_pct', None)
    _extra = [f'· {getattr(c, "name", "?")}：≤{getattr(c, "pct", "?")}%'
              + (f'（{c.reason}）' if getattr(c, 'reason', '') else '')
              for c in _caps]
    if _cap_pct is None:
        _extra.append('本輪沒有任何硬否決條件成立（薩姆／PMI／外資期貨／VIX 否決權／'
                      '三環第一環皆未觸發），持股上界完全由姿態油門決定。')
        return cell_ok(KPI_CAP, '🟢', NO_CAP_TEXT, _extra)

    _capped = bool(getattr(allocation, 'capped', False))
    _extra.append('✅ 這條天花板**低於**姿態油門上界，已實際壓低最終持股。' if _capped
                  else 'ℹ️ 這條天花板高於姿態油門上界，本輪未實際壓低最終持股。')
    # cap_text 是「哪條天花板生效」的 SSOT property，不在此另拼字串。
    return cell_ok(KPI_CAP, '🔴' if _capped else '🟡',
                   str(allocation.cap_text), _extra)


def build_alerts_cell(alerts: Any, threshold_scanned: bool) -> KpiCell:
    """KPI 4｜今日關鍵警示數。producer:`daily_key_alerts.collect_key_alerts()`。

    三態切法**逐條對齊** `macro_ui_components.key_alerts_banner` 的 docstring
    (本 repo 三態契約最完整的範本):

    - `items` 非空                  → 有結論(紅/黃)
    - `items` 空 且門檻層**未掃描**  → ⬜ 未評估(**絕不**進綠燈分支)
    - `items` 空 且門檻層已掃描      → 🟢 無異常
    """
    _raise_if_error(alerts)
    if not isinstance(alerts, dict):
        return cell_unknown(
            KPI_ALERTS, missing='總經警示掃描結果（collect_key_alerts 未執行）',
            how_to_fix=_FIX_MACRO)

    _items = [i for i in (alerts.get('items') or []) if isinstance(i, dict)]
    _n_red = int(alerts.get('n_red') or 0)
    _n_yellow = int(alerts.get('n_yellow') or 0)

    if not _items:
        if not threshold_scanned:
            return cell_unknown(
                KPI_ALERTS,
                missing='門檻層掃描（總經指標尚未載入，check_macro_alerts 一項都沒取到）',
                how_to_fix=_FIX_MACRO,
                explain=('⚠️ 未評估 ≠ 無異常 —— 空的警示清單有三種來源，'
                         '只有「已掃描且全數正常」那一種可以亮綠燈。',))
        return cell_ok(KPI_ALERTS, '🟢', '雙層掃描無異常',
                       ('門檻層（總經警示規則）＋急變層（單期變化超限）皆已掃描，'
                        '本輪無命中。',))

    _extra = [f'· {i.get("emoji", "")} {i.get("text", "")}'.rstrip()
              for i in _items]
    if not threshold_scanned:
        _extra.append('⚠️ 門檻層尚未評估（總經指標未載入），以上僅含急變層 —— '
                      '未評估 ≠ 無異常。')
    return cell_ok(KPI_ALERTS, '🔴' if _n_red else '🟡',
                   f'{_n_red} 紅 / {_n_yellow} 黃（共 {len(_items)} 項）', _extra)


def build_freshness_cell(coverage_rows: Any) -> KpiCell:
    """KPI 5｜資料新鮮度(全站最差)。producer:`compute_tab_coverage()` 的
    `fresh_emoji` / `fresh_label` 欄 → `data_freshness.worst_freshness()` 取最差。

    **刻意不自己再算一次 staleness**:各分頁的 as-of 取法(哪個 key、哪個
    cadence 門檻)全在 `compute_tab_coverage` 裡,自己重算必然漂移。這裡只做
    「取最差 + 指名是哪一源」。
    """
    _raise_if_error(coverage_rows)
    if coverage_rows is None:
        return cell_unknown(
            KPI_FRESHNESS, missing='各分頁新鮮度明細（compute_tab_coverage 未注入）',
            how_to_fix=_FIX_DIAG)

    _rows = _dict_rows(coverage_rows)
    _levels = [(str(r.get('fresh_emoji') or ''),
                f'{r.get("tab", "?")} {r.get("fresh_label", "")}'.strip())
               for r in _rows]
    _assessed = [lv for lv in _levels if lv[0] in _ASSESSED_LIGHTS]
    _n_pending = len(_levels) - len(_assessed)

    if not _assessed:
        return cell_unknown(
            KPI_FRESHNESS,
            missing=f'可判定的資料日期（{len(_rows)} 個分頁全部無法判定 as-of）',
            how_to_fix=_FIX_MACRO,
            explain=tuple(f'· {lv[1]}' for lv in _levels))

    _emoji, _label = worst_freshness(_assessed)
    _extra = [f'· {lv[0]} {lv[1]}' for lv in _levels]
    if _n_pending:
        _extra.append(f'⬜ 另有 {_n_pending} 個分頁尚未載入 / 取不到資料日期，'
                      '未納入「最差」比較 —— 它們的新鮮度是未知，不是良好。')
    # G2 2026-08-08:原文寫「月頻 45 天」已不成立 —— 月頻的 as_of 是資料月月初,
    # 當期最新一筆天生就 60~90 天,45 天門檻等於每天假紅。月頻已改判「落後幾個
    # 發布期」(shared/staleness.monthly_release_status),這裡跟著改口徑。
    _extra.append('門檻走 shared/staleness SSOT（日頻 7 天 / 季頻 150 天；'
                  '月頻改判「距預期最新資料月落後幾期」，不用天數）。')
    return cell_ok(KPI_FRESHNESS, _emoji, _label, _extra)


def build_coverage_cell(coverage_rows: Any) -> KpiCell:
    """KPI 6｜資料覆蓋率(有值率)。producer:`compute_tab_coverage()` 的 `emoji` 欄。

    ⚠️ 覆蓋率**不是**新鮮度:一個從 9 天前凍結至今的欄位,覆蓋率永遠 100%
    (v19.170 P0-4 事故)。所以本格只回答「有沒有值」,活不活由 KPI 5 / 7 回答。
    """
    _raise_if_error(coverage_rows)
    if coverage_rows is None:
        return cell_unknown(
            KPI_COVERAGE, missing='各分頁覆蓋率明細（compute_tab_coverage 未注入）',
            how_to_fix=_FIX_DIAG)

    _rows = _dict_rows(coverage_rows)
    _assessed = [r for r in _rows if str(r.get('emoji') or '') in _ASSESSED_LIGHTS]
    _n_total, _n_pending = len(_rows), len(_rows) - len(_assessed)
    if not _assessed:
        return cell_unknown(
            KPI_COVERAGE,
            missing=f'任何已載入的資料分頁（{_n_total} 個分頁全部未載入）',
            how_to_fix=_FIX_MACRO,
            explain=tuple(f'· {r.get("tab", "?")} ⬜ {r.get("ratio_txt", "")}'.rstrip()
                          for r in _rows))

    _n_full = sum(1 for r in _assessed if str(r.get('emoji')) == '🟢')
    _value = f'資料完整 {fmt_have_total(_n_full, _n_total)}'
    if _n_pending:
        _value += f'，另 {_n_pending} 個分頁尚未載入'
    _light, _ = worst_freshness([(str(r.get('emoji')), str(r.get('tab', '')))
                                 for r in _assessed])
    _extra = [f'· {r.get("tab", "?")} {r.get("emoji", "")} {r.get("ratio_txt", "")}'.rstrip()
              for r in _rows]
    _extra.append('「有值」只回答欄位不是空的，**不回答值是不是活的** —— '
                  '後者看「資料新鮮度」與「值凍結告警」兩格。')
    return cell_ok(KPI_COVERAGE, _light, _value, _extra)


def build_frozen_cell(leading_df: Any) -> KpiCell:
    """KPI 7｜值凍結告警。producer:`data_freshness.detect_frozen_columns`
    (經 `leading_frozen_columns` 這支帶排序的唯一實作)。

    偵測「欄位有值,但一階差分連續 N 期為 0」—— 覆蓋率查不到、`_is_stale` 旗標
    也抓不到的那種死資料(v19.170 P0-4:三欄連續 9 個交易日不變仍顯示 🟢 3/3)。
    """
    _raise_if_error(leading_df)
    if leading_df is None or getattr(leading_df, 'empty', True):
        return cell_unknown(
            KPI_FROZEN, missing='先行指標資料（session_state["li_latest"]）',
            how_to_fix=_FIX_MACRO)

    _n, _cols = leading_frozen_columns(leading_df)
    if _n <= 0:
        # 區分「掃過且沒凍結」與「根本沒有可掃的欄」——後者不得亮綠燈。
        # ⚠️ 同 data_freshness.leading_frozen_columns:`df.columns` 是 pandas
        # `Index`,`... or []` 會觸發 `ValueError: truth value of a Index is
        # ambiguous`。這裡與該處是同一個 bug 的兩份複本(§2.1)。
        _cols_attr = getattr(leading_df, 'columns', None)
        _have = list(_cols_attr) if _cols_attr is not None else []
        _W = FROZEN_WATCH_COLS_LEADING
        if not any(c in _have for c in _W):
            return cell_unknown(
                KPI_FROZEN,
                missing=f'受監看欄位（需要 {fmt_col_list(_W)} 至少其一）',
                how_to_fix='檢查 leading_indicators 抓取是否成功（🔎 資料診斷 → 進階診斷）')
        return cell_ok(KPI_FROZEN, '🟢', '無凍結欄位',
                       (f'受監看欄位：{fmt_col_list(_W)}',
                        f'判定：最近 {FROZEN_STALE_PERIODS_LEADING} 期一階差分全為 0 '
                        '才算凍結；NaN 不算凍結（不知道有沒有變 ≠ 沒變）。'))

    return cell_ok(
        KPI_FROZEN, '🔴', f'{_n} 欄凍結：{fmt_col_list(_cols)}',
        (f'這 {_n} 欄最近 {FROZEN_STALE_PERIODS_LEADING} 期的值完全沒有變動 —— '
         '覆蓋率仍會是 100%，但這些數字對「今天該不該進場」已無資訊量。',
         '常見成因：上游改版 / FinMind 免費版無此資料 / 抓取失敗後沿用舊快取。'))


def build_candidates_cell(stats: Any) -> KpiCell:
    """KPI 8｜個股組合候選統計。producer:`scorability.summarize_candidates()`。

    分母一律用 `n_scored`(**真的算出多因子分**的檔數),不是 `n_total` ——
    B5-b 的病灶正是分子取自 `score_t3`、分母取自 `results_t3` 這兩個不等長的 list。
    """
    _raise_if_error(stats)
    if stats is None:
        return cell_unknown(
            KPI_CANDIDATES, missing='🏆 個股組合批次分析結果（session_state["t3_data"]）',
            how_to_fix=_FIX_GRP)

    _n_total = int(getattr(stats, 'n_total'))
    _n_scored = int(getattr(stats, 'n_scored'))
    _n_pass = int(getattr(stats, 'n_entry_pass'))
    _n_unscored = int(getattr(stats, 'n_unscored'))
    _entry_min = float(getattr(stats, 'entry_min'))

    if _n_total <= 0:
        return cell_unknown(
            KPI_CANDIDATES, missing='批次分析的候選清單（本批 0 檔）',
            how_to_fix=_FIX_GRP)
    if _n_scored <= 0:
        return cell_ok(
            KPI_CANDIDATES, '🔴', f'{_n_total} 檔全部無法評分',
            (f'本批 {_n_total} 檔沒有任何一檔算得出多因子分（多半是 K 線抓不到）。',
             '無法評分的檔**不進分子也不進分母**，不會被當成 0 分排序（§1）。'))

    _value = (f'入選 {fmt_have_total(_n_pass, _n_scored)}'
              f'（多因子 ≥ {_entry_min:g} 分）')
    _extra = [f'本批 {_n_total} 檔，其中 {_n_scored} 檔算得出多因子分（= 分母）。']
    if _n_unscored:
        _extra.append(f'⚠️ {_n_unscored} 檔無法評分，已排除於分子/分母之外 —— '
                      '它們既不算入選也不算落選，不是 0 分。')
    _extra.append(f'健康度不明的檔同樣既不算 kept 也不算 eliminated'
                  f'（不預設 100 也不預設 0）。')
    return cell_ok(KPI_CANDIDATES, '🟡' if _n_unscored else '🟢', _value, _extra)


# ══════════════════════════════════════════════════════════════════════════
# 組裝
# ══════════════════════════════════════════════════════════════════════════
def assemble_core_summary(inputs: CoreSummaryInputs) -> CoreSummary:
    """把 8 個 KPI 組成核心總表。**任一 builder 拋例外都不會拖垮其他格**。

    Args:
        inputs: 全部由既有 producer 產生的輸入(見 `CoreSummaryInputs`)。

    Returns:
        `CoreSummary`,`cells` 順序 = `KPI_ORDER`。

    Note:
        §1:builder 拋例外 → 該格 `failed`(顯示 exception type),
        **不**靜默退回 `unknown`;builder 回傳非 `KpiCell` → 同樣算 failed
        (契約破了要看得見,不是預設一個空格)。
    """
    _specs: tuple[tuple[str, Any], ...] = (
        (KPI_REGIME,     lambda: build_regime_cell(inputs.macro_state,
                                                   inputs.allocation)),
        (KPI_ALLOCATION, lambda: build_allocation_cell(inputs.allocation)),
        (KPI_CAP,        lambda: build_cap_cell(inputs.allocation)),
        (KPI_ALERTS,     lambda: build_alerts_cell(
            inputs.alerts, bool(inputs.alerts_threshold_scanned))),
        (KPI_FRESHNESS,  lambda: build_freshness_cell(inputs.coverage_rows)),
        (KPI_COVERAGE,   lambda: build_coverage_cell(inputs.coverage_rows)),
        (KPI_FROZEN,     lambda: build_frozen_cell(inputs.leading_df)),
        (KPI_CANDIDATES, lambda: build_candidates_cell(inputs.candidate_stats)),
    )
    _cells: list[KpiCell] = []
    for _key, _fn in _specs:
        try:
            _cell = _fn()
            if not isinstance(_cell, KpiCell):
                raise TypeError(
                    f'builder({_key}) 回傳 {type(_cell).__name__}，非 KpiCell')
        except Exception as _e:  # noqa: BLE001 — 單格失敗不得拖垮整張表
            print(f'[core_summary] KPI「{_key}」建構失敗：'
                  f'{type(_e).__name__}: {_e}')
            _cell = cell_failed(_key, _e)
        _cells.append(_cell)
    # 顯示順序即 KPI_ORDER（_specs 已依該順序排列，此處只做防呆對齊）
    _by_key = {c.key: c for c in _cells}
    return CoreSummary(tuple(_by_key[k] for k in KPI_ORDER if k in _by_key))
