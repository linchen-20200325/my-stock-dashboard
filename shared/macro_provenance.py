"""shared/macro_provenance.py — 總經資料「這個數字是真值還是代理值」判定 SSOT（L0）。

v19.183 D2 建立。起因是一個**幽靈 key**（CLAUDE.md §3.3 反捏造 / §1 降級須可見）：

    src/ui/tabs/macro/section_long.py   `_m1b_info.get('is_proxy')`  → 恆 falsy
    src/ui/tabs/macro/section_state.py  `not _m1b2.get('is_proxy')`  → 恆 True

`st.session_state['m1b_m2_info']` 由 `src/data/macro/macro_snapshot.fetch_m1b_m2_block()`
寫入，它回的鍵只有 `{'m1b_yoy', 'm2_yoy', 'gap', 'source'}` —— **從來沒有 `is_proxy`**。
真正帶旗標的是更上游的 `src/data/macro/tw_macro.fetch_cbc_m1b_m2()`，欄位名是
`is_proxy_tier`，而 `fetch_m1b_m2_block` 重新打包 dict 時把它丟掉了，只把資訊
壓成 `source` 字串（Tier 3 時為 ``'TWII-proxy'``）。

實務後果（兩處都是「揭露機制寫了但永遠不會啟動」）：

1. 長期桶 M1B-M2 KPI 卡的「（大盤動能代理估算）」註記**永遠不顯示** ——
   使用者看到的是 `^TWII` 20/60 日動量硬湊出來的兩個數字，畫面卻長得跟
   央行真實 M1B/M2 年增率一模一樣。
2. 拐點面板 §3 的守門 `if _m1b2 and not _m1b2.get('is_proxy')` 本意是
   「代理值不得產生黃金/死亡交叉訊號」，實際上**一次都沒擋掉過**。

修法選擇：不動 L1 producer（`macro_snapshot` 不在本輪授權範圍），改在 L0 建立
單一判定入口，同時吃兩種表示法：

- 未來若 producer 補上明確布林旗標（`is_proxy` / `is_proxy_tier`）→ 直接採用；
- 現況只有 `source` 字串 → 比對本模組的 `M1B_PROXY_SOURCE_LABELS`。

⚠️ 這裡刻意**不做**寬鬆的 substring 嗅探（例如 `'proxy' in source`）：
`section_long.py` v19.176 剛修掉一個「從顯示文案 substring 回推分類」的坑，
同樣的錯不該在 L0 重犯。改為**精確集合比對** + 集合本身就是 SSOT，
producer 換 label 時測試會紅（而不是靜默退回「非代理」）。

§8.2 分層：L0 Infra，零 import（含 stdlib 亦不需要），可被任何層引用。
"""
from __future__ import annotations

from typing import Optional

#: `macro_snapshot.fetch_m1b_m2_block()` 在走到 Tier 3（^TWII 動能代理）時
#: 寫進 `m1b_m2_info['source']` 的字面值。
M1B_PROXY_SOURCE_LABEL: str = 'TWII-proxy'

#: `tw_macro.fetch_cbc_m1b_m2()` 原生 provenance 字串（若哪天 caller 改成直接透傳）。
M1B_PROXY_SOURCE_LABEL_RAW: str = 'Yahoo:^TWII:proxy_tier3'

#: 全部「這不是央行真值」的 source 標籤。精確比對用，**不做 substring**。
M1B_PROXY_SOURCE_LABELS: frozenset = frozenset({
    M1B_PROXY_SOURCE_LABEL,
    M1B_PROXY_SOURCE_LABEL_RAW,
})

#: producer 可能使用的布林旗標欄位名（新舊並存；任一為 True 即視為代理）。
_PROXY_FLAG_KEYS: tuple = ('is_proxy', 'is_proxy_tier')


def is_m1b_m2_proxy(info: Optional[dict]) -> bool:
    """`m1b_m2_info` 這份 M1B/M2 是不是「^TWII 動能代理估算」？

    判定順序（§2.1 上層贏）：

    1. 明確布林旗標 `is_proxy` / `is_proxy_tier` 為 True → 代理。
    2. `source` 落在 `M1B_PROXY_SOURCE_LABELS` → 代理。
    3. 其餘（含 `info` 為 None / 空 dict / 只有 CBC-tier1|2 / FRED / IMF）→ 非代理。

    Args:
        info: `st.session_state['m1b_m2_info']`，可為 None。

    Returns:
        bool。

    Note:
        §1 的分寸：拿不到 `info` 時回 **False**（＝「不宣稱它是代理值」），
        而不是回 True 去嚇人。缺資料本身由呼叫端的 `if info:` 守門處理 ——
        沒有 `m1b_m2_info` 時整個區塊本來就不會渲染，不存在「靜默當成真值」的空間。
    """
    if not isinstance(info, dict):
        return False
    for _k in _PROXY_FLAG_KEYS:
        if info.get(_k) is True:
            return True
    return str(info.get('source') or '') in M1B_PROXY_SOURCE_LABELS
