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
（DEC-074 B 起 `jingqi_for_scoring` 函式內 lazy import 同層 L0 `shared.signal_thresholds` 的計分開關 —— L0→L0，非上行。）
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


#: M1B/M2 為代理值時，貼在數字後面的短註記。
#: **字面沿用 v1** `src/ui/tabs/macro/section_long.py` 長期桶 KPI 卡（v19.183 D2）
#: 既有的那一串 —— B7c 上提到 L0 讓 v1 KPI 卡與 v2 今天頁 m1b 燈共用同一個真相源，
#: ⛔ 不是新文案（K1）。
M1B_PROXY_VALUE_NOTE: str = '（大盤動能代理估算）'


def m1b_m2_proxy_badge(info: Optional[dict]) -> str:
    """代理值 → `M1B_PROXY_VALUE_NOTE`；否則 `''`（可直接串在數字後面）。

    形狀對齊 `macro_helpers.bias_estimated_badge()`：非代理時回空字串，
    呼叫端串接後輸出與未接線前**逐字元相同**。
    """
    return M1B_PROXY_VALUE_NOTE if is_m1b_m2_proxy(info) else ''


def m1b_m2_for_scoring(info: Optional[dict]) -> Optional[dict]:
    """計分／結論／燈號端取 M1B/M2 的唯一入口：代理值 → ``None``；否則原物件。

    DL-f1-s17（客戶 2026-10-02 頁 1 ③「M1B 代理值：只顯示不計分」）：
    `^TWII` 動能代理（`is_m1b_m2_proxy` 為真）**可以顯示**（數字後綴
    `M1B_PROXY_VALUE_NOTE`），但**不得**進任何燈號、結論、三環、策略卡、建議持股上限。
    呼叫端把本函式的回傳當成 `m1b_m2_info` 用 —— 代理時拿到 ``None``，自然走
    各自**既有**的缺值路徑（不另寫一套「代理」分支、不自擬新字）。

    非代理時回**同一個物件**（不複製、不轉型）⇒ 既有計分輸入逐位不變。
    顯示端請照舊讀原始 `m1b_m2_info`（才看得到代理值與註記），不要改讀本函式。
    """
    if is_m1b_m2_proxy(info):
        return None
    return info


# ══════════════════════════════════════════════════════════════════════
# 市場廣度（漲跌家數／旌旗）代理判定 —— DEC-074 B（客戶 2026-10-23）
# ══════════════════════════════════════════════════════════════════════
# 鏡像上方 M1B 三支（`is_m1b_m2_proxy` / `m1b_m2_proxy_badge` / `m1b_m2_for_scoring`），
# 不發明第二種機制（DEC-037 先例）。計分開關在 L0
# `shared.signal_thresholds.BREADTH_PROXY_SCORING_ENABLED`（現為 False）。
#
# 為什麼 `jingqi_info` 只認**明確布林旗標**、不做 source 字串比對：
# producer（`src/services/jingqi_calc.compute_and_store_jingqi`、舊 UI `section_short` 的
# TWSE 單日頂替）自本批起一律寫 `is_proxy`；沒有旗標的 dict（測試 fixture、`section_inputs`
# 由 warroom 合成的 `{'avg': ...}`）沿用既有語意 = 真值（M1B 同一個分寸：拿不到旗標時
# 「不宣稱它是代理值」）。⚠️ 上游 **DataFrame**（`fetch_adl` 的回傳）則相反 —— 缺 `is_proxy`
# 欄**一律視同代理**（fail-safe）：那是原始序列、本 repo 所有已知產出都帶此欄，缺欄＝
# 契約漂移，不得因此把估算家數當真值計分（見 `adl_df_is_proxy`）。

#: 代理廣度值貼在數字後面的短註記（顯示用；判燈／計分一律不讀）。
BREADTH_PROXY_VALUE_NOTE: str = '（代理估算值，不計分）'

#: 受本判定管轄的五桶燈 key（`shared.macro_buckets.BUCKET_DANGER_SPECS` 的 key）。
BREADTH_LAMP_KEYS: frozenset = frozenset({'jingqi', 'adl'})


def is_breadth_proxy(info: Optional[dict]) -> bool:
    """`jingqi_info`（或五桶 readiness 側車的一筆 record）是不是代理（估算）廣度？

    只認明確布林旗標 `is_proxy` / `is_proxy_tier` 為 True（見上方說明）。
    `info` 為 None / 非 dict / 沒有旗標 → False。
    """
    if not isinstance(info, dict):
        return False
    return any(info.get(_k) is True for _k in _PROXY_FLAG_KEYS)


def breadth_proxy_badge(info: Optional[dict]) -> str:
    """代理廣度 → `BREADTH_PROXY_VALUE_NOTE`；否則 `''`（非代理時串接後逐字元不變）。"""
    return BREADTH_PROXY_VALUE_NOTE if is_breadth_proxy(info) else ''


def jingqi_for_scoring(info: Optional[dict]) -> Optional[dict]:
    """計分端取 `jingqi_info` 的唯一入口：代理廣度（且 L0 計分開關關閉）→ ``None``；否則原物件。

    DEC-074 B：代理廣度**可以顯示**、**不得計分**。呼叫端把回傳當 `jingqi_info` 用 ——
    代理時拿到 ``None``，走各自既有的「旌旗缺席」路徑；**但** `calc_traffic_light` 自本批起
    「旌旗缺席 ⇒ 健康分 None（⬜ 未評估）」，不再只剩大盤分重新歸一（DEC-074「不得自行創造
    新權重重新正規化」）。非代理時回**同一個物件**（不複製）⇒ 既有計分輸入逐位不變。
    顯示端請照舊讀原始 `jingqi_info`（才看得到代理值與註記）。
    """
    from shared.signal_thresholds import BREADTH_PROXY_SCORING_ENABLED
    if is_breadth_proxy(info) and not BREADTH_PROXY_SCORING_ENABLED:
        return None
    return info


def adl_df_is_proxy(df) -> bool:
    """`fetch_adl` 回傳的 DataFrame 末列是不是代理（估算）家數？**fail-safe：拿不準一律 True。**

    - None / 空 → True（沒有可宣稱為真值的列；呼叫端本來就會走缺值路徑）
    - 缺 `is_proxy` 欄 → True（契約漂移，不得把估算當真值計分）
    - 末列 `is_proxy` 不是明確的 False（含 NaN / None / True）→ True

    只看**末列**：`market_regime` 吃的是末列 `ad_ratio`；旌旗吃 `tail(5)` 的另見
    `adl_rows_any_proxy`。純 duck typing，L0 不 import pandas。
    """
    return adl_rows_any_proxy(df, 1)


def adl_rows_any_proxy(df, n: int) -> bool:
    """`df` 的最後 `n` 列只要有一列不是明確 `is_proxy is False` → True（fail-safe，同上）。"""
    try:
        if df is None or len(df) == 0:
            return True
        if 'is_proxy' not in getattr(df, 'columns', ()):
            return True
        _tail = df['is_proxy'].tail(max(int(n), 1)).tolist()
    except Exception:  # noqa: BLE001 — 讀不出旗標 = 拿不準 = 代理（fail-safe，不吞成「真值」）
        return True
    # `tolist()` 已把 numpy bool 轉成 Python bool；NaN／None／字串都不是 `False` ⇒ 代理。
    return not all(_v is False for _v in _tail)
