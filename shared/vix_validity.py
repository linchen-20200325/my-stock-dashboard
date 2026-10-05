"""shared/vix_validity.py — 「有效 VIX」共用判定（L0 純函式，批 Z7）。

為什麼有這個檔
──────────────
同一頁有三處自己讀 `macro_info['vix']['current']`：§八 `section_mid`（`_vcur8_v`）、
§三 `section_chips.read_v4_macro_veto()`、§九 `section_cross_ai`。批 Z3 在 §八 定了
「VIX 無效 → 視同缺值」的規則，另兩處卻各用各的寬鬆轉法：

  - §三 收下 −5、0、True、'18.5' 照樣判燈（實跑 −40,000 口時判 🔴），§八 揭露框於是列出
    「看的是 VIX=-5.0」（Z3-n4／Z3-n11）；
  - §九 的 `_num` 讓 ≤ 0、−inf、True 印「（安全）」「極度平靜」，10**400 直接拋 OverflowError（Z3-n1）。

本函式把 §八 那套規則抄成一個可單測的 L0 入口，給 §三、§九 用。

規則（與 §八 `_vcur8_v` 逐條相同 —— `tests/test_batch_z7.py` 以輸入矩陣實跑 §八 對拍）
──────────────────────────────────────────────────────────────────────────────
回 None（視同缺值）：
  - None；
  - Python bool、numpy bool（np.True_ 不得當 VIX 1.0）；
  - 複數（Python complex、numpy 複數 —— 不得靠 `math.isfinite` 丟掉虛部當實數）；
  - `math.isfinite()` 拋 TypeError／ValueError／OverflowError 的值：字串（含數字字串 '18.5'）、
    bytes、list、pd.NA、超大整數（10**400）…；
  - 非有限：NaN、±inf；
  - ≤ 0（恐慌指數恆為正；−0.0 亦同）。
其餘回 `float(x)`（極小正數如 5e-324 照常有效）。

⚠️ 刻意與 §八 一致、不額外收緊（改了就不再「同一套規則」）：
  - 上限：本函式**不擋** VIX > 100 —— §八 把「> 100」當成另一件事（結論段「VIX 數值異常」），
    不是有效性；
  - 0 維 numpy 陣列（含 `np.array(True)`）照 §八 現況放行（Z3-n9，已登記、未判定）；
  - `<= 0` 比較放在 try 之外：比較本身拋例外的怪異物件，§八 會拋、本函式也照拋。

⛔ 本檔不 import streamlit／任何 L1+（§8.2 L0）。
"""
from __future__ import annotations

import math

import numpy as np


def vix_value_or_none(x) -> float | None:
    """VIX 有效 → `float(x)`；無效（規則見模組 docstring）→ None。"""
    if x is None or isinstance(x, (bool, np.bool_, complex, np.complexfloating)):
        return None
    try:
        if not math.isfinite(x):
            return None
    except (TypeError, ValueError, OverflowError):   # 非實數／轉不成 float／溢位 → 缺值
        return None
    if x <= 0:
        return None
    return float(x)
