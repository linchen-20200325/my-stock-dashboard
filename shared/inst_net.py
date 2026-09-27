"""shared/inst_net.py — 三大法人 net dict 的「這一格其實沒觀測到」旗標（L0，2026-09-27）。

為什麼存在
==========
`daily_data_fetchers._parse_bfi82u_rows` 以 `{'外資及陸資': {'net': 0.0}, ...}` 預填，
TWSE 回傳缺某一列（或該列買賣差額不可解析）時，那一格會**留著 0.0** —— 對既有 3 個
消費點（calc_traffic_light / section_chips / tab_edu）那是既有行為（本批授權⛔ 不改）；
但 foreign_net 燈（五桶 / 今天頁）自 2026-09-27 起把它畫上畫面，0.0 在 low_bad
（yellow=0）下會變成「🟡 0億」＝ §1 捏造的觀測。

作法（**加性**，既有消費點逐位不變）
====================================
`InstNetDict` 是 `dict` 的子類：內容、`repr`、`==`、迭代順序、`json.dumps` 全部與原本的
plain dict 相同；**只多一個屬性** `unobserved_net`（沒有觀測到的 key 集合）。
既有消費點只做 `inst[k]['net']` / `for k in inst` → 完全看不到這個屬性。
只有 foreign_net 燈的取值端以 `is_net_observed()` 讀它 → 沒觀測到 ⇒ None ⇒ 灰燈。

⚠️ 屬性只活在**同一個物件**上：若中途有人 `dict(inst)` 複製，旗標會掉 ⇒ 退回既有行為
（讀 net），⛔ 不會更糟。pickle（`_pkl_put` / `st.cache_data`）會保留屬性；
本批之前寫入的舊 pickle 是 plain dict ⇒ 同樣退回既有行為，直到 TTL 過期。
純常數 / 型別模組，零 import 依賴（可被全層 import）。
"""
from __future__ import annotations

from typing import Any, Iterable


class InstNetDict(dict):
    """plain dict ＋ `unobserved_net`（frozenset：該 key 的 net 不是觀測值，而是預填）。"""

    #: 類別層預設（pickle 還原時 `__init__` 不會被呼叫；也讓舊物件讀得到空集合）。
    unobserved_net: frozenset = frozenset()

    def __init__(self, *args: Any, unobserved_net: Iterable[str] = (), **kw: Any) -> None:
        super().__init__(*args, **kw)
        self.unobserved_net = frozenset(unobserved_net)


def is_net_observed(inst: Any, key: str) -> bool:
    """`inst[key]['net']` 是不是真的觀測值。plain dict（舊路徑 / 舊 pickle）→ True（既有行為）。"""
    return key not in getattr(inst, "unobserved_net", frozenset())
