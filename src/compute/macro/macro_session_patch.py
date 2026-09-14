"""src/compute/macro/macro_session_patch.py — `fetch_macro_bundle` → session patch 的**純函式**（L2）。

T3-1（IA v2 頁1「🚀 更新今日戰情」原地重抓）的寫入層**上半**。
下半是 L3 `src/services/macro_session_apply.py::apply_macro_bundle`
（十行以內，只負責把本函式回傳的東西寫進 `st.session_state`）。

═══ 為什麼要拆成兩半（不是形式主義）═══════════════════════════════════
`tests/test_c3_layering_guard.py` 的 `_KNOWN_VIOLATIONS` 在
`scripts/update_macro_forward_test.py` 那一條裡，**自己寫出了正解**：

    「……把那兩支 L3 的 session_state 寫入與計算拆開（**回傳 dict + 另一層負責寫**）」

拆開之後才有的兩個能力（本批真的用到了，不是理論上的好處）：
  1. **可比對**：頁1 的新路徑與舊 `tab_macro.py` 的 in-line 寫入，可以對同一份
     bundle 逐鍵比對（`tests/test_p01_macro_refresh.py` 的 golden test）。
     沒有這一支純函式，「兩條路徑寫的東西一樣嗎」就只能靠人眼讀 code。
  2. **可測**：本函式零 streamlit、零 I/O，`li_retain_meta` 的累計邏輯
     （rounds / since / last_try / reason）可以直接餵 dict 驗。

═══ 出處（逐鍵對照）═══════════════════════════════════════════════════
本函式的行為是 `src/ui/tabs/tab_macro.py` **spinner 區塊內的 session 寫入段**
（2026-09-09 量測時位於 `:433-489`；**刻意不寫行號在別處**，行號會漂移 ——
真正釘住兩者一致的是上述 golden test）的**逐鍵搬移**：

    assign: adl_debug_msg / cl_data / cl_ts / _is_refreshing /
            _last_inst / _last_inst_date / _last_margin /
            li_latest / li_retain_meta
    pop   : adl_debug_msg / li_latest(no-op，見下) / li_retain_meta

⚠️ **`load_heavy` 必須由呼叫端傳進來，本函式不自己推。**
`tab_macro` 的冷啟動 fallback（`if not _load_heavy and df_li_a is None:
df_li_a = session['li_latest']`）**在寫入區間之外、卻決定了下面所有分支**。
拿 `bundle` 的內容反推 `load_heavy`（例如「inst 是空的就當冷啟動」）
會在「熱啟動但 inst 全敗」時判錯，把「抓了沒拿到」誤寫成「沒抓」。

⚠️ **`li_latest` 的那個 pop 是 no-op，本函式刻意不搬。**
原碼是 `if 'li_latest' not in session: session.pop('li_latest', None)`
—— 條件成立時 key 本來就不在，pop 不做任何事。搬過來只會在
`MACRO_PATCH_POP_KEYS` 裡多一個永遠不生效的鍵，讓讀的人以為
「這條路徑會刪掉 li_latest」。**不搬，並在此記明它的存在**（§-2 規則 6：
沒說出來的省略，下一個人會當成漏抄）。

═══ 分層（CLAUDE.md §8.2）═════════════════════════════════════════════
**L2 Compute**。純函式、零 I/O、零 streamlit、零 pandas import
（`df.empty` 走 duck typing，與原碼同一個寫法）。

**為什麼是 L2 而不是 L0 `shared/`**：`shared/` 是常數 / 門檻 / TTL 層，
被**全層** import（§8.2「L0 不得依賴任何 L1+」的代價就是它必須極薄）。
本函式帶的是**分支邏輯**（冷啟動 fallback、`li_retain_meta` 的累計與
`reason` 三態），那是「運算」不是「常數」；放進 L0 會讓一個所有人都
import 的層長出業務規則。`src/compute/macro/` 既有的鄰居
（`macro_helpers` / `daily_key_alerts`）正是同一類東西。
"""
from __future__ import annotations

from typing import Any, Mapping

# ══════════════════════════════════════════════════════════════════
# 契約（給測試與讀者，**不是**給程式分支用的）
# ══════════════════════════════════════════════════════════════════
#: 本函式**可能**寫入的 session key 全集。
#:
#: 「可能」兩字是認真的 —— `_last_inst` / `_last_margin` / `li_latest` /
#: `li_retain_meta` / `adl_debug_msg` 都帶條件，任一輪的實際 patch 是本集合的
#: 子集。列出全集的用途是讓「這條路徑到底碰得到什麼」可被稽核
#: （`macro_refresh_service.WRITES_SESSION_KEYS` 據此對外宣告，
#: 頁1 再據此**誠實標示本輪沒更新到的區塊**）。
MACRO_PATCH_KEYS: tuple[str, ...] = (
    "adl_debug_msg", "cl_data", "cl_ts", "_is_refreshing",
    "_last_inst", "_last_inst_date", "_last_margin",
    "li_latest", "li_retain_meta",
)

#: 本函式**可能**要求刪除的 session key。
MACRO_PATCH_POP_KEYS: tuple[str, ...] = ("adl_debug_msg", "li_retain_meta")

#: `li_retain_meta['reason']` 的兩種值（原碼的 `'empty_df' if ... else 'none'`）。
LI_RETAIN_REASON_EMPTY: str = "empty_df"
LI_RETAIN_REASON_NONE: str = "none"


def _is_empty_frame(obj: Any) -> bool:
    """`df.empty` —— **與原碼同一個寫法，包含它的脾氣。**

    刻意不寫成 `getattr(obj, 'empty', False)`：那會讓一個「不是 DataFrame 的
    東西」靜默通過並被當成有效的先行指標存進 `li_latest`（§1 造假）。
    上游契約說 `df_li_a` 是 `DataFrame | None`，不是就當場炸。
    """
    return bool(obj.empty)


def build_macro_session_patch(
    bundle: Mapping[str, Any],
    *,
    load_heavy: bool,
    prev_li_latest: Any,
    prev_li_retain_meta: Any,
    now_str: str,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """把 `fetch_macro_bundle()` 的回傳整理成「要寫什麼 / 要刪什麼」。

    Args:
        bundle: `services.macro_fetch_orchestrator.fetch_macro_bundle()` 的回傳。
            7 個資料鍵（`intl_raw` / `tw_raw` / `tech_raw` / `inst` /
            `inst_date` / `margin` / `df_adl_raw` / `df_li_a`）**以 `[]` 直取**
            —— 契約缺鍵就當場 `KeyError`，不用 `.get` 靜默補 `None`（§1）。
        load_heavy: 這一輪有沒有抓重資料（inst / margin / adl / li）。
            **必須由呼叫端傳**，理由見檔頭。
        prev_li_latest: 進來這一輪之前 `session['li_latest']` 的值。
        prev_li_retain_meta: 進來這一輪之前 `session['li_retain_meta']` 的值。
        now_str: 時間戳字串（`shared.macro_compute.tw_now_str()` 的輸出）。
            **由呼叫端注入**，本函式因此可重現（同輸入同輸出，§5 冪等性）。

    Returns:
        `(patch, pops)`：
          · `patch` —— `session_state.update(patch)` 用的 dict。
          · `pops`  —— 要 `session_state.pop(k, None)` 的 key，**有序**。

    ⚠️ **本函式不做任何「這一輪該不該算旌旗」之類的判斷** ——
    那是 `macro_refresh_service` 的事（它與 `tab_macro` 在該點上**刻意不同**，
    見該檔的 `_STEP_JINGQI` 註解）。這裡只搬 session 寫入。
    """
    patch: dict[str, Any] = {}
    pops: list[str] = []

    df_li_a = bundle["df_li_a"]
    # 冷啟動（load_heavy=False）時 li job 根本沒跑 → 沿用上一輪的，避免把
    # 「這輪沒抓」寫成「這輪抓不到」。**這一段在原碼裡位於寫入區間之外，
    # 卻決定了下面所有分支** —— 搬進來是為了讓兩條路徑真的等價。
    if not load_heavy and df_li_a is None:
        df_li_a = prev_li_latest

    # ── ADL debug 訊息：失敗時設、成功時刪 ──────────────────────
    if bundle.get("adl_debug_msg"):
        patch["adl_debug_msg"] = bundle["adl_debug_msg"]
    else:
        pops.append("adl_debug_msg")

    # ── 主要數據 ────────────────────────────────────────────────
    patch["cl_data"] = dict(
        intl=bundle["intl_raw"], tw=bundle["tw_raw"], tech=bundle["tech_raw"],
        inst=bundle["inst"], inst_date=bundle["inst_date"],
        margin=bundle["margin"], adl=bundle["df_adl_raw"])
    patch["cl_ts"] = now_str
    patch["_is_refreshing"] = False  # 資料就位，解除刷新鎖

    # 最後一次有效的法人 / 融資，供 API 失敗時 fallback。
    # ⚠️ truthy guard（不是 `is not None`）—— 與原碼一致：空 dict / 0 都不覆蓋
    # 既有的 last-known-good，否則一次失敗會把上一次的好資料抹掉（§2.4）。
    if bundle["inst"]:
        patch["_last_inst"] = bundle["inst"]
        patch["_last_inst_date"] = bundle["inst_date"]
    if bundle["margin"]:
        patch["_last_margin"] = bundle["margin"]

    # ── 先行指標：拿到就存、拿不到就顯式記「沿用上輪」──────────
    if df_li_a is not None and not _is_empty_frame(df_li_a):
        patch["li_latest"] = df_li_a
        pops.append("li_retain_meta")   # 抓到新資料 → 清掉降級標記
    elif prev_li_latest is not None:
        # §2.4「過期 cache 回傳須帶 is_stale、禁止靜默返回」的落點：
        # 本輪沒抓到、畫面卻照舊渲染上一輪的 li_latest —— 那份 df 身上沒有任何
        # 旗標，於是「什麼都沒抓到」與「抓得好好的」在 UI 上長得一模一樣。
        _prev = prev_li_retain_meta if isinstance(prev_li_retain_meta, dict) else {}
        patch["li_retain_meta"] = {
            "rounds": int(_prev.get("rounds", 0) or 0) + 1,
            "since": _prev.get("since") or now_str,
            "last_try": now_str,
            "reason": (LI_RETAIN_REASON_EMPTY if df_li_a is not None
                       else LI_RETAIN_REASON_NONE),
        }
    # else: 連上一輪都沒有 → 單純的「沒資料」，由覆蓋率欄顯示 ⬜，不需標記。
    # （原碼此處另有一個 `if 'li_latest' not in session: session.pop('li_latest')`
    #   的 no-op，刻意不搬，理由見檔頭。）

    return patch, tuple(pops)
