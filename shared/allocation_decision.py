"""v19.170 建議持股 SSOT — 全站唯一的「該持股幾成」決策物件。

問題(2026-08-04 外部稽核 P0-1)
------------------------------
同一次載入、同一份資料下，畫面上並存 **6 套互相矛盾的持股建議**：

============================================  ==========================  ==========
位置                                          結論                        建議持股
============================================  ==========================  ==========
主結論卡(section_warroom)                     震盪整理｜謹慎觀望          80%
🎚️ 建議持股油門(section_traffic_light)        🟠 轉守                     30–50%
桶2 策略3 VIX 否決權(section_mid)             股匯雙殺，嚴格減碼防守      0–30%
⚔️ 攻擊發動判定 三環(section_mid)             🚫 禁止攻擊                 0–20%
§九 ② 建議配置(section_cross_ai)              ⛔ 防禦模式                 0–20%
ETF 總經連動配置(etf_render.MACRO_ALLOC)      🟢 多頭市場                 股票 70%
全站置底常駐條(app.py)                        🟢 多頭市場(可積極操作)     80%
============================================  ==========================  ==========

根因有三：
1. 四套獨立引擎各自算持股 —— `portfolio_exposure`(80/50/20)、
   `compute_position_throttle`(區間)、`section_mid`/`section_cross_ai` 硬編碼三環、
   `etf_render.MACRO_ALLOC`(70/50/20)。
2. `warroom_summary['throttle']` 被 `section_state` 整包覆寫抹掉，
   下游 fallback 回粗略 `mkt_info['exposure_pct']`。
3. UI 上寫著「實際持股取姿態與風險上限**兩者較低**」，但程式沒有真的執行這條規則。

設計
----
本模組是 **L0 純函式**（零 L1+ 依賴、不 import streamlit），提供：

- `Cap`            — 一條「硬否決天花板」(名稱 / 上限% / 原因)
- `AllocationDecision` — frozen dataclass，全站唯一持股真相
- `build_allocation_decision()` — 由 macro_state + throttle + caps 合成
- `allocation_sleeves()` — 由最終持股中值推導 ETF 三桶配置(股/債/現金)

核心規則(對齊 UI 上既有文案，只是這次真的執行)::

    final_hi = min(posture_hi, *[c.pct for c in caps])
    final_lo = min(posture_lo, final_hi)

亦即：**姿態油門決定「該多積極」，硬否決決定「最多能到哪」，取兩者較低。**

§1 Fail Loud
------------
`is_loaded=False`(總經尚未評估)時，`final_lo/hi` 一律回 `None`，
消費端必須顯示「總經未評估」而**不得**回填 80%/50%/20% 之類的假預設。

caller::

    from shared.allocation_decision import build_allocation_decision, Cap
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

# ── 邊界對齊既有 SSOT(不另立矛盾數字)──────────────────────────────
# 防禦帶上界 20 = EXPOSURE_BEAR(config.py) = position_throttle._DEFENSE_HI_PCT。
DEFENSE_HI_PCT: int = 20

# regime → 中文顯示(全站統一，避免各頁自己翻譯)
REGIME_LABEL: dict[str, str] = {
    'bull':    '多頭',
    'neutral': '震盪',
    'caution': '轉守',
    'bear':    '空頭',
    'unknown': '未評估',
}

# ETF 三桶：非股票部位中，「債券」佔比(其餘為現金)。
# 空頭時債券避險價值高 → 債券吃掉較多；多頭時保留較多機動現金。
_BOND_SHARE_OF_NON_EQUITY: dict[str, float] = {
    'bull':    0.50,
    'neutral': 0.60,
    'caution': 0.65,
    'bear':    0.70,
    'unknown': 0.60,
}


@dataclass(frozen=True)
class Cap:
    """一條硬否決天花板。

    Args:
        name:   顯示名稱(如 '薩姆規則' / 'VIX 否決權' / '三環第一環')
        pct:    持股上限 %(0-100)
        reason: 一句話說明為何觸發(要能被使用者看懂)
    """
    name: str
    pct: int
    reason: str = ''

    def __post_init__(self) -> None:
        if not (0 <= int(self.pct) <= 100):
            raise ValueError(f'Cap.pct 必須在 0-100，收到 {self.pct}（{self.name}）')


@dataclass(frozen=True)
class AllocationDecision:
    """全站唯一的建議持股決策。**唯讀**，任何 UI 一律引用不得自行再算。

    Attributes:
        is_loaded:   總經是否已評估。False → final_* 為 None，UI 須誠實顯示未評估。
        regime:      'bull'/'neutral'/'caution'/'bear'/'unknown'
        health:      總經健康分 0-100(未評估為 None)
        posture_lo/hi: 姿態油門原始區間 %(未受硬否決壓制前)
        posture:     姿態文字('積極'/'中性偏多'/'轉守'/'防禦'...)
        icon:        姿態燈號 emoji
        cap_pct:     所有 Cap 取最小者(無 Cap 為 None)
        cap_name:    生效的那條 Cap 名稱
        caps:        全部 Cap(供明細展開)
        final_lo/hi/mid: **最終**建議持股區間 %(= min(姿態, 天花板))
        capped:      最終是否被硬否決壓低
        drivers:     推導依據(給「為何是這個數字」用)
        conflicts:   與最終結論相反、但被壓制的訊號(要顯示，不要藏)
    """
    is_loaded: bool
    regime: str
    health: float | None
    posture_lo: int | None
    posture_hi: int | None
    posture: str
    icon: str
    cap_pct: int | None
    cap_name: str
    caps: tuple[Cap, ...] = ()
    final_lo: int | None = None
    final_hi: int | None = None
    final_mid: int | None = None
    capped: bool = False
    drivers: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()

    # ── 顯示用 helper(集中在此，避免各頁各自 f-string 出不同格式)──────
    @property
    def range_text(self) -> str:
        """'30–50%'；上下界相同時回 '20%'；未評估回 '--'。"""
        if not self.is_loaded or self.final_lo is None or self.final_hi is None:
            return '--'
        if self.final_lo == self.final_hi:
            return f'{self.final_lo}%'   # v19.170:避免出現 '20–20%' 這種怪字串
        return f'{self.final_lo}–{self.final_hi}%'

    @property
    def mid_text(self) -> str:
        """'40%'；未評估回 '--'。"""
        if not self.is_loaded or self.final_mid is None:
            return '--'
        return f'{self.final_mid}%'

    @property
    def regime_text(self) -> str:
        return REGIME_LABEL.get(self.regime, self.regime or '未評估')

    @property
    def cap_text(self) -> str:
        """'🔒 上限 20%（薩姆規則）'；無 cap 回 ''。"""
        if self.cap_pct is None:
            return ''
        _n = f'（{self.cap_name}）' if self.cap_name else ''
        return f'🔒 上限 {self.cap_pct}%{_n}'

    def headline(self) -> str:
        """一句話結論：'🟠 轉守 → 建議持股 30–50%'。"""
        if not self.is_loaded:
            return '⬜ 總經未評估 — 請先按「🚀 一鍵更新全部數據」'
        return f'{self.icon} {self.posture} → 建議持股 {self.range_text}'


def build_allocation_decision(
    macro_state: dict | None,
    throttle: dict | None = None,
    caps: Iterable[Cap] = (),
    conflicts: Sequence[str] = (),
) -> AllocationDecision:
    """由總經狀態 + 姿態油門 + 硬否決天花板，合成全站唯一的持股決策。

    Args:
        macro_state: `macro_state_locker.get_macro_state()` 的輸出，需含
            `is_loaded` / `regime` / `health` / `defense` / `exposure_limit_pct`。
        throttle: `position_throttle.compute_position_throttle()` 的輸出。
            傳 None 時本函式會自行由 `health` 現算(需 macro_state 有 health)。
        caps: 額外硬否決天花板(VIX 否決權、三環第一環未過…)。
            `macro_state['exposure_limit_pct']` 會自動被納入，不需重複傳。
        conflicts: 與最終結論方向相反、但被壓制的訊號描述。

    Returns:
        AllocationDecision(frozen)。

    Note:
        §1 Fail Loud — `is_loaded=False` 時 final_* 全為 None，
        **不回填任何預設持股%**；消費端須顯示「總經未評估」。
    """
    _ms = macro_state or {}
    _is_loaded = bool(_ms.get('is_loaded'))
    _regime = _ms.get('regime') or 'unknown'
    _health = _ms.get('health')
    _defense = bool(_ms.get('defense'))

    # ── 未評估：誠實回未知，不捏造 ────────────────────────────────
    if not _is_loaded or _health is None:
        return AllocationDecision(
            is_loaded=False, regime=_regime, health=None,
            posture_lo=None, posture_hi=None, posture='未評估', icon='⬜',
            cap_pct=None, cap_name='', caps=tuple(caps),
            drivers=('總經尚未評估（warroom_summary / macro_state.json 皆無有效值）',),
            conflicts=tuple(conflicts),
        )

    # ── 姿態油門(未帶則現算)────────────────────────────────────────
    if not throttle:
        from shared.position_throttle import compute_position_throttle
        throttle = compute_position_throttle(
            float(_health), regime=_regime, defense=_defense)

    _p_lo = int(throttle.get('lo_pct', 0))
    _p_hi = int(throttle.get('hi_pct', DEFENSE_HI_PCT))
    _posture = str(throttle.get('posture', '防禦'))
    _icon = str(throttle.get('icon', '🔴'))

    # ── 蒐集所有硬否決天花板 ──────────────────────────────────────
    _caps: list[Cap] = list(caps)
    _sys_cap = _ms.get('exposure_limit_pct')
    if _sys_cap is not None:
        # v19.170:macro_state.json 是磁碟檔、可能被手改或寫入異常值。
        # 這裡顯式夾限 0-100 並在越界時 log(§1：填補須顯式 + 留跡)，
        # 而非讓 Cap.__post_init__ raise —— 本函式的呼叫點之一是
        # app.py module level，一旦 raise 會讓整站白屏。
        try:
            _raw = int(_sys_cap)
        except (TypeError, ValueError):
            print(f'[allocation] exposure_limit_pct 非整數，已忽略：{_sys_cap!r}')
            _raw = None
        if _raw is not None:
            _clamped = max(0, min(100, _raw))
            if _clamped != _raw:
                print(f'[allocation] exposure_limit_pct={_raw} 越界，已夾限為 {_clamped}')
            _caps.append(Cap('系統風險上限', _clamped,
                             'macro_state 規則引擎（薩姆／PMI／外資期貨硬否決）'))

    _cap_pct: int | None = None
    _cap_name = ''
    if _caps:
        _eff = min(_caps, key=lambda c: int(c.pct))
        _cap_pct, _cap_name = int(_eff.pct), _eff.name

    # ── 核心規則：取姿態與天花板較低者 ────────────────────────────
    _f_hi = _p_hi if _cap_pct is None else min(_p_hi, _cap_pct)
    _f_lo = min(_p_lo, _f_hi)
    _capped = _cap_pct is not None and _cap_pct < _p_hi

    # ── 推導依據(給「為何是這個數字」)──────────────────────────────
    _drivers: list[str] = [
        f'總經健康分 {float(_health):.0f} → 姿態「{_posture}」，油門帶 {_p_lo}–{_p_hi}%',
    ]
    if throttle.get('regime_capped'):
        _drivers.append(f'regime={_regime}／defense={_defense} → 油門已先被壓至防禦帶')
    for _c in sorted(_caps, key=lambda c: int(c.pct)):
        _mark = '✅ 生效' if int(_c.pct) == _cap_pct else '　　'
        _drivers.append(f'{_mark} 天花板「{_c.name}」≤{_c.pct}%'
                        + (f'：{_c.reason}' if _c.reason else ''))
    _drivers.append(f'最終 = min(姿態 {_p_hi}%, 天花板 '
                    f'{_cap_pct if _cap_pct is not None else "—"}%) → {_f_lo}–{_f_hi}%')

    return AllocationDecision(
        is_loaded=True, regime=_regime, health=float(_health),
        posture_lo=_p_lo, posture_hi=_p_hi, posture=_posture, icon=_icon,
        cap_pct=_cap_pct, cap_name=_cap_name, caps=tuple(_caps),
        final_lo=_f_lo, final_hi=_f_hi, final_mid=round((_f_lo + _f_hi) / 2),
        capped=_capped,
        drivers=tuple(_drivers), conflicts=tuple(conflicts),
    )


def allocation_sleeves(decision: AllocationDecision) -> dict[str, int] | None:
    """由最終持股中值推導 ETF 三桶配置，確保與主決策**永不矛盾**。

    取代 `etf_render.MACRO_ALLOC` 那張與主決策脫鉤的靜態表(bull 固定 70%)。

    Args:
        decision: `build_allocation_decision()` 的輸出。

    Returns:
        `{'股票型ETF': int, '債券型ETF': int, '貨幣/現金': int}`(合計 100)；
        `decision.is_loaded=False` 時回 **None**(§1：不假裝有配置建議)。
    """
    if not decision.is_loaded or decision.final_mid is None:
        return None
    _eq = max(0, min(100, int(decision.final_mid)))
    _rest = 100 - _eq
    _bond = int(round(_rest * _BOND_SHARE_OF_NON_EQUITY.get(decision.regime, 0.60)))
    _cash = _rest - _bond
    return {'股票型ETF': _eq, '債券型ETF': _bond, '貨幣/現金': _cash}


def vix_veto_cap(vix: float | None) -> Cap | None:
    """VIX 總經否決權 → Cap(原 section_mid 硬編碼文案的 SSOT 化)。

    v19.174 去識別化:原註解在此帶人名稱謂,已改為來源模組名。

    門檻對齊 `signal_thresholds.VIX_MEDIUM_RISK_THRESHOLD(20)` /
    `VIX_HIGH_RISK_THRESHOLD(25)` 與 macro_buckets 紅線 30。

    Returns:
        Cap 或 None(VIX 未知／< 20 不設限)。
    """
    if vix is None:
        return None
    try:
        _v = float(vix)
    except (TypeError, ValueError):
        return None
    if _v >= 30:
        return Cap('VIX 否決權', 10, f'VIX {_v:.1f} ≥ 30，系統性風險爆發，現金為王')
    if _v >= 20:
        return Cap('VIX 否決權', 30, f'VIX {_v:.1f} 進入 20–30 警戒帶，停止加槓桿')
    return None


def ring_gate_cap(ring1_pass: bool, detail: str = '') -> Cap | None:
    """三環公式第一環(解除保險)未過 → Cap 20%。

    原本 `section_mid` / `section_cross_ai` 各自印一組「持股 0~20%」文字，
    現改為只回傳天花板，由 `build_allocation_decision` 統一仲裁，
    UI 端只顯示「火力分級」而不再輸出競爭的持股數字。

    Returns:
        Cap 或 None(第一環通過 → 不設限)。
    """
    if ring1_pass:
        return None
    return Cap('三環第一環', DEFENSE_HI_PCT,
               detail or 'VIX 過高 或 外資重兵空單 — 技術面突破視為誘多')
