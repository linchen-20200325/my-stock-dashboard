# -*- coding: utf-8 -*-
"""shared/scoring_regime_gate.py — 「多因子總分到底能不能算」的唯一判定（L0，H1）。

═══ 這個模組在解什麼問題 ══════════════════════════════════════════════
`scoring_engine.stock_score()` 的 6 因子加權表是 **regime 的函數**
（`src/config/config.py::WEIGHT_TABLES`，bull / neutral / bear 三態），而它取表的
寫法是::

    w = WEIGHT_TABLES.get(regime, WEIGHT_TABLES['neutral'])

也就是說 —— **任何 WEIGHT_TABLES 沒有的 regime 值都會靜默拿到 neutral 權重**。
於是 🏆 個股組合的批次評分長年是這樣接線的（`section_batch_fetcher`，H1 前）::

    _grp_regime = (st.session_state.get('macro_state', {}) or {}).get('regime') or 'neutral'
    sf = score_single_stock(df4, sid4, name, regime=_grp_regime)

`st.session_state['macro_state']` 只有在使用者**開過 🌍 總經頁**、且紅綠燈算得出
結論時才由 `section_traffic_light` 寫入。冷啟動直接點 🏆 個股組合時：

  - key 不存在        → `{}.get('regime')` = None → `or 'neutral'` → **捏造「震盪」**
  - key 存在但未評估  → `regime='unknown'`（C1 v19.182 的三態）→ 落進 `.get` 的
                         default → **一樣是 neutral 權重**，而且連捏造都看不出來

兩條路都導向同一個結果：**全批股票用「震盪」權重評分，畫面印出一組看起來完全正常
的分數**。使用者無從得知這組排名是在「總經沒有結論」的前提下算出來的。

三態權重差多少（`config.WEIGHT_TABLES`，量測日 2026-08-10）::

            trend  momentum  chip  volume  risk  fundamental
    bull     0.30      0.25  0.20    0.15  0.05         0.05
    neutral  0.25      0.20  0.20    0.15  0.10         0.10
    bear     0.15      0.10  0.15    0.15  0.25         0.20

趨勢因子在 bull 是 bear 的兩倍、風險因子在 bear 是 bull 的五倍 —— 這不是微調，
是**排名會換人**的量級（見 `tests/test_h1_scoring_regime_gate.py` 的實算）。

═══ 設計決定：未評估時「拒絕評分」而非「挑一組保守權重」 ═══════════════
兩個選項都能滿足「不得靜默用 neutral 權重然後印出正常分數」，本模組選前者：

1. **挑任何一組權重都是替使用者做一個大盤判斷。** 選 bear 等於宣告「不知道就當
   空頭」、選 neutral 等於宣告「不知道就當震盪」—— 兩者都是 §1 明令禁止的
   「自行估一個合理值當常數」。真相是「這個輸入未知」，而未知就是未知。
2. **下游早就有三態機制可用，零改動。** `compute/screener/scorability.py`
   （B5-b）已經把「拿不到資料」與「評出來很差」在型別上分開：沒有分數的檔進
   `unscored_ids`，畫面標「⚪ 無法評分」、多因子欄留白、**不進 KPI 的分子也不進
   分母**。拒絕評分直接複用這條路，不需要在下游新增任何「這個分數不可信」的旗標
   （新增旗標才是真正的高風險改動 —— 旗標一旦漏接就退化回靜默造假）。
3. **可一鍵復原，且復原路徑就在同一畫面。** 使用者按「🚀 一鍵更新全部數據」或
   先開 🌍 總經頁，分數立刻回來。反過來說，靜默用 neutral 權重是**不可復原**的：
   使用者永遠不會知道發生過。

被拒絕的**只有加權總分那一個數字**。健康度、趨勢、357 評價、出場訊號、型態目標價
全部照算照顯示 —— 它們不吃 regime。

═══ 順帶關掉一個潛伏的同類坑：合法但沒有權重表的 regime ═══════════════
canonical regime 集合是 `{bull, neutral, caution, bear, unknown}`
（`shared/regime_arbiter.REGIME_LIGHT` / `macro_state_locker._REGIME_EN`），
但 `WEIGHT_TABLES` **只有 3 個 key** —— `caution`（轉守）沒有對應權重表。

現況查證（2026-08-10）：`arbitrate_regime()` 只回 bull/neutral/bear/unknown，
`macro_state.json` 的 `market_regime` 只可能是 多頭/震盪/空頭/系統異常
→ `normalize_regime` 後也只會是 bull/neutral/bear。所以 `caution` **目前打不到
這裡**，是潛伏坑不是活 bug（§-1：不主動改 `WEIGHT_TABLES`）。

但本模組仍然明確擋掉它：regime 不在 `WEIGHT_TABLES` 的 key 集合裡 → 一律拒絕評分
並說明原因。如此一來，未來哪天真的有 producer 開始回 `caution`，使用者看到的是
「⚪ 無法評分 + 為什麼」，而不是**一組悄悄用震盪權重算出來的空頭排名**。

═══ 分層（§8.2）═══════════════════════════════════════════════════════
L0 Infra：零 I/O、不 import streamlit、不 import 任何 L1+。
`WEIGHT_TABLES` 住 `src/config/config.py`（同屬 L0，合法平行 import），採
**函式內 late import** —— 理由與 `shared/edu_tokens._leek_alert_pct()` 相同：
`src.config` 會條件 import streamlit（EX-L0-1），延後可避免把那條依賴拉進
每一次 `import shared.scoring_regime_gate` 的啟動路徑。

caller::

    from shared.scoring_regime_gate import resolve_scoring_regime
    from src.services.allocation_service import get_macro_regime

    _dec = resolve_scoring_regime(get_macro_regime())
    if _dec.usable:
        sf = score_single_stock(df, sid, name, regime=_dec.regime)
    else:
        ...  # 不評分，並把 _dec.notice() 顯示給使用者
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

_LOG = "[scoring_regime_gate]"

#: 未評估的 canonical regime 字面（`shared.regime_arbiter.UNLOADED_VERDICT.regime`）。
#: 這裡刻意**不** import regime_arbiter —— 只需要比對一個字面，import 進來反而
#: 讓「L0 常數模組」長出跨模組依賴。兩邊一致由 `tests/test_h1_*.py` 釘住。
UNKNOWN_REGIME: str = "unknown"


@dataclass(frozen=True)
class ScoringRegimeDecision:
    """一次「能不能算多因子總分」的判定結果（唯讀）。

    Attributes:
        regime: 可直接餵給 `stock_score(regime=...)` 的 canonical regime；
            `None` 代表**不得評分**（§1：不得改用任何預設權重）。
        reason: 不得評分的原因（一句話，可讀）。`usable` 時為 ``''``。
    """

    regime: Optional[str]
    reason: str = ""

    @property
    def usable(self) -> bool:
        """True → 可以評分；False → 必須拒絕評分。"""
        return self.regime is not None

    def notice(self) -> str:
        """給使用者看的完整警示句（`usable` 時為空字串）。

        內容刻意包含三件事，缺一個使用者就會誤判：

        1. **被擋掉的是什麼**（只有加權總分，不是整個批次分析）；
        2. **為什麼**（權重表是 regime 的函數，任選一組都是捏造）；
        3. **這不是 K 線抓取失敗** —— 畫面上「⚪ 無法評分」那個標記同時服務兩種
           原因，不講清楚使用者會去查網路 / 重抓資料而不是去開總經頁；
        4. **救法**。
        """
        if self.usable:
            return ""
        return (
            f"⬜ 本批**不計算多因子總分**：{self.reason}。"
            "多因子的 6 因子加權表（config.WEIGHT_TABLES）分 bull / neutral / bear "
            "三態，總經沒有結論時任選一組都等於替你做一個大盤判斷（§1 寧可不給，"
            "不給假的）。因此「多因子」欄一律標「⚪ 無法評分」、"
            "「多因子評分排行」為空 —— **這不是 K 線抓取失敗**。"
            "健康度／趨勢／357／出場訊號／型態目標價不吃 regime，全部照常顯示。"
            "救法：按「🚀 一鍵更新全部數據」，或先開 🌍 總經頁讓紅綠燈算出結論，"
            "再重跑一次批次分析。"
        )


def weight_table_regimes() -> tuple[str, ...]:
    """`WEIGHT_TABLES` 目前支援的 regime key（讀不到 → 空 tuple + log）。

    §1：import 失敗**不回一組硬編碼的預設 key**（那會讓本模組在 config 壞掉時
    放行一個其實沒有權重表的 regime）。回空 tuple，`resolve_scoring_regime`
    會據此拒絕評分。
    """
    try:
        from src.config import WEIGHT_TABLES
    except Exception as _e:  # noqa: BLE001 — 讀不到 config 不該炸掉整頁
        print(f"{_LOG} ⚠️ 讀不到 config.WEIGHT_TABLES: {type(_e).__name__}: {_e}")
        return ()
    try:
        return tuple(str(_k) for _k in WEIGHT_TABLES)
    except TypeError as _e:
        print(f"{_LOG} ⚠️ WEIGHT_TABLES 不可疊代: {type(_e).__name__}: {_e}")
        return ()


def resolve_scoring_regime(macro_state: Any) -> ScoringRegimeDecision:
    """canonical 總經契約 → 「能不能算多因子總分」。

    Args:
        macro_state: `allocation_service.get_macro_regime()` 的回傳
            （或 `macro_state_locker.get_macro_state()`，兩者同一份 dict）。
            非 dict / None 一律視為取數失敗。

    Returns:
        ScoringRegimeDecision。`regime` 為 None 時 caller **必須**跳過評分，
        並把 `notice()` 顯示給使用者（§1 降級不靜默）。

    判定順序（先命中先回，每一條都對應一種真實發生過的狀態）::

        1. 不是 dict                     → 取數失敗
        2. is_loaded 為假                → 總經未評估（冷啟動最常見）
        3. regime 空 / == 'unknown'      → 契約自己說未評估
        4. WEIGHT_TABLES 讀不到          → 權重表不可用
        5. regime 不在 WEIGHT_TABLES     → 合法 regime 但沒有權重表（如 caution）
        6. 其他                          → 可評分
    """
    if not isinstance(macro_state, dict):
        return ScoringRegimeDecision(
            None,
            f"總經狀態取數失敗（預期 dict，收到 {type(macro_state).__name__}）",
        )

    if not macro_state.get("is_loaded"):
        return ScoringRegimeDecision(None, "總經未評估（🌍 總經紅綠燈尚未算出結論）")

    _regime = str(macro_state.get("regime") or "").strip().lower()
    if not _regime or _regime == UNKNOWN_REGIME:
        return ScoringRegimeDecision(
            None, "總經契約回報 regime=unknown（未評估，不是「判斷為震盪」）"
        )

    _known = weight_table_regimes()
    if not _known:
        return ScoringRegimeDecision(None, "讀不到 config.WEIGHT_TABLES 權重表")

    if _regime not in _known:
        return ScoringRegimeDecision(
            None,
            f"regime={_regime!r} 在 WEIGHT_TABLES 找不到對應權重表"
            f"（現有 {' / '.join(_known)}）—— 硬套任一組都會讓分數與燈號脫節",
        )

    return ScoringRegimeDecision(_regime, "")
