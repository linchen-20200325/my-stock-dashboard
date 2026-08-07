"""v19.170 建議持股 SSOT 接線層(L3 Service)。

`shared/allocation_decision.py` 是 L0 純函式；本模組是它與 Streamlit
`session_state` 之間的**唯一橋樑**。全站 UI 一律：

    from src.services.allocation_service import get_allocation
    _alloc = get_allocation()
    st.markdown(_alloc.headline())

而**不得**再自行 `compute_position_throttle` / `portfolio_exposure` /
讀 `mkt_info['exposure_pct']` / 硬編碼持股百分比。

為什麼要這層
------------
稽核發現 `warroom_summary['throttle']` 會被 `section_state.py` 整包覆寫抹掉
（`st.session_state['warroom_summary'] = {...}` 沒帶 throttle），
導致 `app.py` 置底常駐條 fallback 回粗略的 `mkt_info['exposure_pct']`=80%，
與油門的 30–50% 打架。本模組改為**每次都由來源重算**，
不依賴任何一個可能被覆寫的中繼 key，從結構上消滅該類 bug。

快取策略
--------
同一次 Streamlit rerun 內以 `_ALLOC_CACHE_KEY` 記憶，避免重複讀檔；
key 由 `(cl_ts, health, regime, exposure_limit_pct, vix, ring1)` 組成，
任一輸入變動即自動失效。
"""
from __future__ import annotations

import streamlit as st

from shared.allocation_decision import (
    AllocationDecision,
    Cap,
    allocation_sleeves,
    build_allocation_decision,
    ring_gate_cap,
    vix_veto_cap,
)
from shared.position_throttle import compute_position_throttle

_ALLOC_CACHE_KEY = '_alloc_decision_cache'
_ALLOC_SIG_KEY = '_alloc_decision_sig'

# 額外天花板由各 section 於 render 期間登記(VIX 否決權 / 三環第一環…)。
# 用獨立 key 而非塞進 warroom_summary，避免再度被整包覆寫。
_EXTRA_CAPS_KEY = '_alloc_extra_caps'
_CONFLICTS_KEY = '_alloc_conflicts'


# ── 對外：登記天花板 / 衝突訊號 ────────────────────────────────────
def register_cap(name: str, pct: int, reason: str = '') -> None:
    """登記一條硬否決天花板(同名覆蓋，冪等；可在 rerun 內重複呼叫)。

    v19.170 注意：VIX 否決權與三環第一環**已改由 `get_allocation()` 自行推導**
    (見 `_derive_intrinsic_caps`)，UI 端不需要、也不應該再靠登記來影響數字。
    本函式保留給未來的臨時性天花板；重複登記相同值時**不會**使快取失效。

    Args:
        name: 天花板名稱，作為冪等 key(如 'VIX 否決權')。
        pct:  持股上限 %。
        reason: 一句話原因，會顯示在「為何是這個數字」明細。
    """
    _caps = st.session_state.setdefault(_EXTRA_CAPS_KEY, {})
    _old = _caps.get(name)
    _new = Cap(name, int(pct), reason)
    if _old == _new:
        return  # 值未變 → 不動快取(避免 render 期間反覆 invalidate)
    _caps[name] = _new
    _invalidate()


def clear_cap(name: str) -> None:
    """撤銷一條天花板(條件不再成立時呼叫，避免上一輪的 cap 殘留)。"""
    _caps = st.session_state.get(_EXTRA_CAPS_KEY) or {}
    if name in _caps:
        _caps.pop(name, None)
        _invalidate()


def register_conflict(text: str) -> None:
    """登記一個與最終結論相反、但被壓制的訊號(顯示用，不影響數字)。

    v19.170：以 `cl_ts`(上次一鍵更新時間戳)分桶存放，資料一換就整批作廢，
    避免舊訊號永久殘留(原實作只增不減、無 clear 途徑)。
    """
    _bucket = st.session_state.get('cl_ts', '')
    _store = st.session_state.get(_CONFLICTS_KEY)
    if not isinstance(_store, dict) or _store.get('_bucket') != _bucket:
        _store = {'_bucket': _bucket, 'items': []}
        st.session_state[_CONFLICTS_KEY] = _store
    if text and text not in _store['items']:
        _store['items'].append(text)
        _invalidate()


def _current_conflicts() -> tuple[str, ...]:
    """取本輪有效的衝突訊號(cl_ts 不符即視為過期)。"""
    _store = st.session_state.get(_CONFLICTS_KEY)
    if not isinstance(_store, dict):
        return ()
    if _store.get('_bucket') != st.session_state.get('cl_ts', ''):
        return ()
    return tuple(_store.get('items') or ())


def reset_allocation_registry() -> None:
    """清空本輪登記的 caps / conflicts。可在總經 tab render 起點呼叫。

    v19.170：核心天花板已改為內生推導，本函式不再是正確性的必要條件，
    僅供除錯或未來的臨時 cap 使用。
    """
    st.session_state[_EXTRA_CAPS_KEY] = {}
    st.session_state.pop(_CONFLICTS_KEY, None)
    _invalidate()


# ── 內生天花板推導(v19.170 修「慢一個 rerun」的順序 bug)────────────
def _safe_float(v) -> float | None:
    try:
        _f = float(v)
    except (TypeError, ValueError):
        return None
    return _f if _f == _f else None  # NaN → None


def _read_vix() -> float | None:
    """從 session 取當前 VIX(對齊 section_mid `_m8_vix.get('current')`)。"""
    _mi = st.session_state.get('macro_info') or {}
    _vix = _mi.get('vix') or {}
    return _safe_float(_vix.get('current')) if isinstance(_vix, dict) else None


def _read_foreign_futures_lots() -> float | None:
    """從 session 取外資期貨淨口(對齊 section_mid `li_latest['外資大小']`)。"""
    _li = st.session_state.get('li_latest')
    try:
        if _li is None or getattr(_li, 'empty', True):
            return None
        if '外資大小' not in getattr(_li, 'columns', []):
            return None
        return _safe_float(_li.iloc[-1].get('外資大小'))
    except Exception as _e:  # noqa: BLE001 — 取數失敗當未知，不炸畫面
        print(f'[allocation] 讀外資期貨淨口失敗: {type(_e).__name__}: {_e}')
        return None


# 三環第一環 B 條件門檻(對齊 section_mid `_cB = _fut8 > -15000`)
_RING1_FUT_MIN_LOTS: int = -15000

# 這兩條天花板一律由 `_derive_intrinsic_caps()` 現算，
# 外部 `register_cap()` 同名登記會被忽略(見 get_allocation)。
_INTRINSIC_CAP_NAMES: frozenset[str] = frozenset({'VIX 否決權', '三環第一環'})


def _derive_intrinsic_caps() -> tuple[list[Cap], list[str]]:
    """由 session 現有資料直接推導核心天花板，**不依賴 UI 呼叫順序**。

    為什麼要這樣做
    --------------
    總經 tab 的 render 順序是
    `warroom(主結論卡) → traffic_light(油門) → mid(三環/VIX) → cross_ai`，
    而 `app.py` 的全站置底常駐條是 module-level、更早執行。
    若天花板靠 `section_mid` 在 render 期間登記，前面三個消費點會讀到
    **上一輪**的 cap → 畫面又出現互相矛盾的數字（這正是本次要消滅的問題）。
    改成在此由來源資料現算，任何消費點在任何時機呼叫都拿到同一個答案。

    Returns:
        (caps, conflicts)
    """
    _caps: list[Cap] = []
    _conflicts: list[str] = []

    _vix = _read_vix()
    _cap_vix = vix_veto_cap(_vix)
    if _cap_vix is not None:
        _caps.append(_cap_vix)

    # ── 三環第一環(解除保險)：A VIX<20 且 B 外資期貨 > -15000 口 ──────
    #
    # v19.170 稽核修正(資訊單調性)：必須把「未知」與「已知且不利」分開。
    # 舊寫法 `_cA = _vix is not None and _vix < 20` 會讓
    #   (VIX=None, 期貨=None)      → 不進分支 → 不扣  → 持股 80–100%
    #   (VIX=None, 期貨=+5000 利多) → _cA=False → 扣 20% → 持股 20%
    # 「多知道一個利多事實，結論反而砍到 20%」是決策函數對資訊集非單調，
    # 使用者會看到「昨天 80%、今天 VIX 抓失敗 → 20%」而找不到原因。
    #
    # 新規則：**只有已知且不利的條件才扣天花板**；資料未知只登記為
    # conflict(誠實揭露不確定性)，不影響數字。加入更多資訊只可能新增
    # 一條失敗、不可能移除一條失敗 → 單調。
    _fut = _read_foreign_futures_lots()
    _fail_bits: list[str] = []
    _unknown_bits: list[str] = []

    if _vix is None:
        _unknown_bits.append('VIX')
    elif _vix >= 20:
        _fail_bits.append(f'VIX {_vix:.1f} ≥ 20')

    if _fut is None:
        _unknown_bits.append('外資期貨淨口')
    elif _fut <= _RING1_FUT_MIN_LOTS:
        _fail_bits.append(f'外資期貨 {_fut:,.0f} 口 ≤ {_RING1_FUT_MIN_LOTS:,}')

    if _fail_bits:
        _cap_ring = ring_gate_cap(False, '、'.join(_fail_bits))
        if _cap_ring is not None:
            _caps.append(_cap_ring)
    if _unknown_bits:
        _conflicts.append(
            f'⚠️ 三環第一環資料不全（{"、".join(_unknown_bits)} 未取得），'
            '未套用該天花板 — 數字可能偏樂觀')
    return _caps, _conflicts


def _invalidate() -> None:
    st.session_state.pop(_ALLOC_CACHE_KEY, None)
    st.session_state.pop(_ALLOC_SIG_KEY, None)


# ── 對外：唯一取數入口 ─────────────────────────────────────────────
def get_allocation() -> AllocationDecision:
    """回傳全站唯一的建議持股決策(唯讀)。

    來源鏈(§2.1 上層贏、不平均)::

        warroom_summary(總經紅綠燈) ─┐
        macro_state.json(規則引擎)  ─┴→ get_macro_state() → macro_state
        macro_state.health ──────────→ compute_position_throttle() → 姿態油門
        macro_info.vix / li_latest ──→ _derive_intrinsic_caps() → 硬否決天花板
        (額外登記的 caps 為選配)         ↓
                          build_allocation_decision()  ← 唯一仲裁點

    v19.170：核心天花板(VIX 否決權 / 三環第一環)改為**內生推導**，
    不再依賴 UI render 順序 —— 這消滅了「caps 慢一個 rerun」那類 bug。

    v19.171 補記(實機驗收後修正)：`health` / `regime` 來自 `warroom_summary`，
    而它是在 `tab_macro` 內的 `render_traffic_light_top()` 才寫入的。
    `app.py` 置底常駐條原本是 module level、執行早於 tab 內容，加上
    「🚀 一鍵更新全部數據」的 on_click callback(`handlers._macro_session_reset`)
    會先 pop 掉 `warroom_summary`，導致置底條**實機上永遠顯示「⬜ 總經未評估」**
    (不是偶發、是常態 —— 2026-08-05 線上實測複現)。
    **已於 v19.171 根治**：置底條改用 `st.empty()` 佔位、在所有 tab render 完成
    之後才填充，因此與油門 / 主結論卡 / ETF 橫幅同輪同源。
    其他消費點本來就在 tab 內，不受此限制影響。

    Returns:
        AllocationDecision。總經未評估時 `is_loaded=False`，
        `final_*` 為 None，UI 須誠實顯示未評估(§1 Fail Loud)。
    """
    _wr = st.session_state.get('warroom_summary') or {}
    _extra = st.session_state.get(_EXTRA_CAPS_KEY) or {}

    try:
        from src.services.macro_state_locker import get_macro_state
        _ms = get_macro_state(_wr)
    except Exception as _e:  # noqa: BLE001 — 讀檔/匯入失敗當未評估，不炸畫面
        print(f'[allocation] get_macro_state failed: {type(_e).__name__}: {_e}')
        _ms = {'is_loaded': False, 'regime': 'unknown', 'health': None,
               'defense': False, 'exposure_limit_pct': None}

    _intrinsic, _auto_conf = _derive_intrinsic_caps()
    _conf = tuple(_auto_conf) + _current_conflicts()

    # 內生推導的兩條天花板具**絕對權威**：先把同名的登記版本剔除，
    # 避免「上一輪登記、這一輪條件已不成立」的殘留 cap 繼續壓低持股。
    _cap_map = {k: v for k, v in _extra.items() if k not in _INTRINSIC_CAP_NAMES}
    _cap_map.update({c.name: c for c in _intrinsic})
    _caps = tuple(_cap_map.values())

    # 快取簽章：任一輸入變動即失效
    _sig = (
        st.session_state.get('cl_ts', ''),
        _ms.get('health'), _ms.get('regime'), _ms.get('defense'),
        _ms.get('exposure_limit_pct'), _ms.get('is_loaded'),
        tuple(sorted((c.name, c.pct) for c in _caps)),
        _conf,
    )
    if st.session_state.get(_ALLOC_SIG_KEY) == _sig:
        _cached = st.session_state.get(_ALLOC_CACHE_KEY)
        if isinstance(_cached, AllocationDecision):
            return _cached

    _thr = None
    if _ms.get('health') is not None:
        _thr = compute_position_throttle(
            float(_ms['health']), regime=_ms.get('regime'),
            defense=bool(_ms.get('defense')))

    _decision = build_allocation_decision(
        _ms, throttle=_thr, caps=_caps, conflicts=_conf)

    st.session_state[_ALLOC_CACHE_KEY] = _decision
    st.session_state[_ALLOC_SIG_KEY] = _sig
    return _decision


def get_macro_regime() -> dict:
    """回傳全站唯一的大盤 regime 契約（C1 v19.182；唯讀）。

    這是 `macro_state_locker.get_macro_state()`（L3 純函式）與 Streamlit
    `session_state` 之間的**唯一橋樑** —— 等同 `get_allocation()` 之於持股%。
    任何 UI 一律::

        from src.services.allocation_service import get_macro_regime
        _reg = get_macro_regime()
        if not _reg['is_loaded']:
            st.info('⬜ 總經未評估 — 請先按「🚀 一鍵更新全部數據」')
            return
        ...使用 _reg['regime'] / _reg['light']

    而**不得**再：

    - 直讀 `st.session_state['mkt_info']['regime']`（那是趨勢面**輸入**，
      不是結論；且各處還會補一個捏造的 `'neutral'` 預設）
    - 對 `warroom_summary['traffic_light']` 做 `'綠'/'黃'/'紅'` substring 比對
      （那 4 個 label 根本不含這些字，比對恆不命中）
    - 由紅綠燈 `icon` 反推 regime

    Returns:
        `get_macro_state()` 的 dict。取數失敗一律降級為未評估
        （`is_loaded=False` / `regime='unknown'` / `light='⬜'`），
        **不回填任何預設多空**（§1 Fail Loud）。
    """
    _wr = st.session_state.get('warroom_summary') or {}
    try:
        from src.services.macro_state_locker import get_macro_state
        return get_macro_state(_wr)
    except Exception as _e:  # noqa: BLE001 — 讀檔/匯入失敗當未評估，不炸畫面
        print(f'[allocation] get_macro_regime failed: {type(_e).__name__}: {_e}')
        from shared.regime_arbiter import UNLOADED_VERDICT as _UV
        return {
            'regime': _UV.regime, 'light': _UV.light, 'source': _UV.source,
            'trend_regime': None, 'health': None, 'defense': False,
            'exposure_limit_pct': None, 'traffic_light': None,
            'is_loaded': False,
        }


def get_allocation_sleeves() -> dict[str, int] | None:
    """ETF 三桶配置(股/債/現金)，由 `get_allocation()` 的中值推導。

    Returns:
        dict 或 None(總經未評估 → 不給假配置)。
    """
    return allocation_sleeves(get_allocation())


# ── 便利函式：把常見天花板一次登記完 ───────────────────────────────
def apply_vix_veto(vix: float | None) -> None:
    """依 VIX 登記/撤銷「VIX 否決權」天花板。"""
    _cap = vix_veto_cap(vix)
    if _cap is None:
        clear_cap('VIX 否決權')
    else:
        register_cap(_cap.name, _cap.pct, _cap.reason)


def apply_ring_gate(ring1_pass: bool, detail: str = '') -> None:
    """依三環第一環結果登記/撤銷「三環第一環」天花板。"""
    _cap = ring_gate_cap(ring1_pass, detail)
    if _cap is None:
        clear_cap('三環第一環')
    else:
        register_cap(_cap.name, _cap.pct, _cap.reason)
