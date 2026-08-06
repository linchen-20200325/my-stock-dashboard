"""shared/pcr_scale.py — 選擇權 PCR 刻度正規化 SSOT（L0，v19.180 B2-b）。

病史（本模組存在的理由）
────────────────────────────────────────────────────────────────
本專案同一個 PCR 有**兩種刻度**共存（CLAUDE.md §4.1 量綱陷阱）：

  - **百分比刻度**（50~200）：`li_latest['選PCR']`
    evidence（寫入端，兩條路徑都 ×100）：
      · `src/data/macro/leading_indicators.py:1309`
        `pcr_dict[dk] = round(b["putV"] / b["callV"] * 100, 1)`（FinMind 估算）
      · `src/data/macro/leading_indicators.py:969-971`
        `if 0.1 < val < 10: val = round(val * 100, 1)` 後只收 `20 < val < 500`
        （TAIFEX pcRatio 精確值，覆蓋估算）
  - **標準比值刻度**（0.5~2.0）：
      · `src/config/config.py:205-212` `MACRO_ALERT_RULES['pcr']`
        （red_above 1.5 / yellow_above 1.2 / yellow_below 0.7 / red_below 0.5）
      · `src/services/macro_state_locker.calculate_system_state` 的 `PCR` 輸入

v19.178 只把「餵給 LLM 的判讀句」換算好，**餵給規則引擎的
`_macro_numbers['PCR']` 仍是百分比刻度** → `pcr > 1.5` 對實測 126.80 恆真
→ 曝險分數系統性 −10 → 曝險上限恆低 10 個百分點。本模組把當時 inline 的
換算收斂成唯一實作，讓所有消費端共用同一條判別線與同一組邊界（§2.1 SSOT）。

為什麼採「自動偵測＋換算」而不是「只判斷不修正」
────────────────────────────────────────────────────────────────
本專案已有兩個刻度守衛先例，差別在**是否存在確定性的判別依據**：

  - `shared.macro_buckets.within_valid_range`（us10y / dxy）—— **只判斷不修正**。
    因為上游可能整個換標的（DXY → UUP ETF ~27），越界值**無法**還原原意，
    §1 不猜，退回 gray + log。
  - `src.compute.risk.reconcile.normalize_tnx_quote`（^TNX）—— **偵測＋換算**。
    因為兩種報價慣例的值域不重疊且皆有文件，偵測是確定性的。

PCR 屬**後者**：比值域 (0, 10] 與百分比域 (10, 500] 完全不重疊
（真實比值極端恐慌約 2.0、歷史從未逼近 10；百分比刻度從未低到 10 —— 那等於
比值 0.1）。而且本專案**已經有兩處在跑這個自動換算**
（`src/data/macro/macro_alert.py:299`、`src/ui/tabs/macro/section_news_ai.py`），
本模組是把既有行為收斂成一份，不是新增一種行為。

兩種刻度都解釋不通（≤0 或 >500 或 NaN）→ 回 `None` + log，§1 **不猜、不填預設**。

caller::

    from shared.pcr_scale import normalize_pcr_to_ratio
    pcr_ratio, scale_src = normalize_pcr_to_ratio(li_latest.iloc[-1]['選PCR'])
"""
from __future__ import annotations

from shared.signal_thresholds import (
    PCR_PERCENT_SCALE_MIN,
    PCR_PERCENT_VALID_MAX,
)

_LOG = "[pcr_scale]"


def normalize_pcr_to_ratio(raw) -> tuple[float | None, str]:
    """把任一刻度的 PCR 原始值收斂成**標準比值刻度**，並回報偵測到的刻度。

    Args:
        raw: PCR 原始值。可能是比值刻度（1.268）、百分比刻度（126.8），
            也可能是 None / NaN / 無法轉 float 的字串（'-' / '' / 'nan'）。

    Returns:
        `(ratio, scale_src)`

        - ``ratio``: float | None —— **標準比值刻度**（≈0.1~5.0）；
          刻度無法判定時為 ``None``（§1 不猜換算，caller 須當「沒有這個指標」，
          **不得**回填 1.0 之類的中性預設）。
        - ``scale_src``: str —— 帶偵測結果的來源標籤，可直接寫進 log / AI context，
          讓事後對帳看得出「這次讀成哪一種刻度」。

    判別區間（邊界與 `macro_alert.py:299` 的既有 `> PCR_PERCENT_SCALE_MIN`
    語意**完全一致**，零行為位移）::

        raw ≤ 0                         → None（PCR = putV/callV 恆為正）
        0 < raw ≤ 10  (SCALE_MIN)       → 比值刻度，原值即比值
        10 < raw ≤ 500 (VALID_MAX)      → 百分比刻度，÷100
        raw > 500 / NaN / 非數值        → None
    """
    if raw is None:
        return None, "PCR(未取得)"
    try:
        v = float(raw)
    except (TypeError, ValueError):
        print(f"{_LOG} ⚠️ PCR 值無法轉 float: {raw!r} → 視為未取得(§1)")
        return None, "PCR(型別錯誤)"
    if v != v:  # NaN guard（NaN 的任何比較皆 False，顯式處理避免誤讀）
        print(f"{_LOG} ⚠️ PCR 值為 NaN → 視為未取得(§1)")
        return None, "PCR(NaN)"

    if v <= 0:
        # PCR = put 量 / call 量，數學上恆 > 0。0 或負值代表上游解析錯，
        # 若當比值放行會命中「< 0.7 過度樂觀」→ 憑空生出一個看多訊號。
        print(f"{_LOG} ⚠️ PCR 值 {v:g} ≤ 0（PCR = putV/callV 恆為正）→ 回 None(§1)")
        return None, f"PCR(非正值 {v:g})"
    if v <= PCR_PERCENT_SCALE_MIN:
        return v, "PCR(比值刻度)"
    if v <= PCR_PERCENT_VALID_MAX:
        return v / 100.0, "PCR(百分比刻度→÷100)"

    print(f"{_LOG} ⚠️ PCR 值 {v:g} 落在兩種刻度的合理範圍外 "
          f"(比值 (0, {PCR_PERCENT_SCALE_MIN:g}] / "
          f"百分比 ({PCR_PERCENT_SCALE_MIN:g}, {PCR_PERCENT_VALID_MAX:g}]) "
          f"→ 回 None，**不猜換算**(§1)。")
    return None, f"PCR(越界 {v:g}，刻度不明)"
