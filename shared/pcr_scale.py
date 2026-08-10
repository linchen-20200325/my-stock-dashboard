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


# ════════════════════════════════════════════════════════════════
# 先行指標明細表「選PCR」欄的著色帶（**百分比刻度**，H1）
# ════════════════════════════════════════════════════════════════
# 為什麼要有這兩個常數
# ────────────────────────────────────────────────────────────────
# 🧩 籌碼區「📅 資料期間」那行 caption 原本手寫「PCR<100偏空」。它的問題**不是**
# 「100 這條線不存在」—— 同一頁最底下的「🎯 籌碼綜合判斷」計分器確實用
# `>130 / >100 / ≤100` 三段（`section_chips.py`）。問題是：那行 caption 是**它正
# 下方那張表的圖例**，而那張表（`leading_indicators.render_leading_table`）的著色
# 判定式是 `<80 紅 / >120 綠` —— 圖例講的線和表格用的線不是同一條。
#
# 同一欄位在同一頁至少有三組帶（量測日 2026-08-10，皆為百分比刻度）：
#     表格著色           <80 🔴          / >120 🟢     ← 本節兩個常數
#     ⚡ 進階警示（訊號4）<80 🔴 過樂觀   / >150 🟢 恐慌
#     🎯 籌碼綜合判斷     ≤100 −1 分      / >130 +1 分
# 三者方向一致（低 PCR = put 保護不足 = 危險；高 PCR = 恐慌 = 逆向機會），
# 只是敏感度不同。caption 挑了第三組去標第一張表，於是使用者對著一個 90 的讀數
# 會讀到「偏空」，而表格把它塗成中性色。
#
# ⚠️ 與 `config.MACRO_ALERT_RULES['pcr']` 的關係（§4.1 量綱）
# ────────────────────────────────────────────────────────────────
# 那組規則是**標準比值刻度**（red_above 1.5 / yellow_above 1.2 / yellow_below 0.7
# / red_below 0.5），消費端是 `macro_alert` / `calculate_system_state`，
# 取值前一律先經 `normalize_pcr_to_ratio()`。換算成百分比後：
#     yellow_above 1.2 → 120  ← 與本節 PCR_PCT_FEAR_MIN **完全相同**
#     yellow_below 0.7 →  70  ← 與本節 PCR_PCT_COMPLACENCY_MAX(80) **不同**
# 低檔那條線兩邊差 10 個百分點，是既有的真實分歧，本次**不動**（改任一邊都是
# 行為變更，且無證據指出哪一邊才是原意）—— 只把它記在這裡，避免下一個讀者以為
# 這兩個常數是 MACRO_ALERT_RULES 的鏡像而「順手統一」。
#
# ⚠️ 本節是 `render_leading_table` 那兩個 inline 字面的**鏡像**，不是它的來源
# ────────────────────────────────────────────────────────────────
# `leading_indicators.py`（L1）的著色函式目前仍寫死 `if n < 80` / `if n > 120`。
# 那個檔不在本次改動範圍，所以這裡採「鏡像 + 行為守衛」：
# `tests/test_h1_pcr_caption.py` 會**實際呼叫** `render_leading_table()` 餵邊界值，
# 斷言顏色恰好在這兩個常數處翻轉。任一邊改了值、測試立刻紅。
# 之後若要收成單一來源，正確做法是讓 `render_leading_table` 反過來 import 本節。

PCR_PCT_COMPLACENCY_MAX: float = 80.0
"""先行指標表「選PCR」轉紅的上界（**百分比刻度**，＝比值 0.80）。

`< 80` → 紅：買 put 避險的人太少，市場保護不足／過度樂觀，常見於短線頂部。
（同值也是 `section_chips` ⚡ 進階警示 訊號4 的紅線。）
"""

PCR_PCT_FEAR_MIN: float = 120.0
"""先行指標表「選PCR」轉綠的下界（**百分比刻度**，＝比值 1.20）。

`> 120` → 綠：避險需求濃厚、市場偏恐慌，在本系統的逆向框架下屬機會帶。
數值與 `config.MACRO_ALERT_RULES['pcr']['yellow_above']`（比值 1.2）等價。
"""

PCR_PCT_PARITY: float = 100.0
"""put/call **平價點**的百分比刻度表示（＝比值 1.0）。

⚠️ 這是**市場常識**，不是本系統的任何判定線 —— 放在這裡是為了讓 caption 能明說
「1.0（本表 100）是平價點，但本系統的判定帶在 80 / 120」，而不是讓誰拿它去當門檻。
唯一的例外是 `section_chips` 的「🎯 籌碼綜合判斷」計分器，它確實在 100 加減一分；
那是**計分器的敏感度設定**，與表格著色不同用途，不可互相取代。
"""


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
