"""S1(2026-08)— 殭屍已載入態：空 session 不得被渲染成「已載入」。

實機重現的 bug
──────────────
使用者在「🌍 總經」按下「🚀 一鍵更新全部數據」成功（紅綠燈「多頭市場」、
綜合健康度 65、今日關鍵 2 項），走訪其他分頁後切回總經，畫面變成：

    ⏳ 燈號等待中（尚無資料）
    今日關鍵剩 1 項（CPI 消失、美債 10Y 還在）
    個股 / 個股組合 / 選股網 / ETF / 工具箱 五頁同時「⬜ 總經未評估」

根因（非 pop、非 TTL、非快取被清）
─────────────────────────────────
`macro_info` 全 repo **沒有任何 pop 點**（33 處 `session_state.pop` 逐一比對），
也沒有 `st.session_state.clear()` / `del st.session_state[...]`（grep 0 hit）。
⇒ 唯一可能是整份 session_state 被重建（Cloud 容器回收 / websocket 斷線 /
記憶體壓力）—— 這一點**非 code 可控，本檔不試圖守衛它**。

code 端真正的缺陷是「重建之後假裝還載入著」：

    app.py 開機閘門  ?chips=1  →  st.session_state['chips_loaded'] = True

把「已載入」**旗標**從 URL 救回來了，但**資料**（cl_data / cl_ts / mkt_info /
macro_info / warroom_summary）全住在 session_state，一個都救不回來。
而 `chips_loaded` 一個人就同時滿足：

    tab_macro.py:146-150   _macro_loaded = bool(cl_data or mkt_info or chips_loaded)
    tab_macro.py:372       _load_heavy   = bool(do_refresh) or bool(chips_loaded)

⇒ 空 session 跳過 tab_macro.py:200-208 誠實的「👉 點擊上方按鈕載入總經資料」，
直接進主流程，然後每一格印空值。

「今日關鍵 2→1」是決定性指紋
────────────────────────────
`fetch_macro_snapshot` 兩項來源不對稱：

    CPI    macro_alert.py:276-282   只讀 session_state['macro_info']，零 fallback
    US10Y  macro_alert.py:204-205   @st.cache_data(TTL_30MIN) → **server 級、跨 session 存活**

所以 CPI 死、US10Y 活 ＝「session 沒了、cache 還在」。純粹切 tab 不會造成這種
不對稱 —— 這條證據把根因從「誰把 key pop 掉了」導向「整份 session 被重建」。

修法與**刻意不做**的事
──────────────────────
只拔掉 app.py 的「跨 session 還原 chips_loaded」，不動 `chips_loaded` 語意。
⚠️ `chips_loaded` 本身不是壞設計，勿一併拔除：
  · tab_macro.py:185 由使用者真的按下按鈕寫入 —— 語意是「本 session 嘗試過載入」。
    抓取失敗時它仍須為 True，畫面才能顯示失敗診斷，而非退回「還沒載入」。
  · section_chips.py:136-137 / :752 用它算 `_attempted`，區分
    「按過但三源全空（→ 印 FINMIND_TOKEN 診斷卡）」vs「根本還沒按」。

本修法**不阻止** session 被重建，而是讓它重建後誠實承認沒資料（§1 Fail Loud）：
使用者看到空狀態 → 按一次按鈕 → 快取還熱 → 數秒回來。

測試設計原則
────────────
**一律走 AST，不用字串比對。** app.py 的 FIX 註解為了說明「原本錯在哪」，
整段逐字引用了 `st.session_state['chips_loaded'] = True` 與 `?chips=1`；
字串掃描 = 保證假紅燈。這條原則沿用 test_f2_app_decomposition.py 的設計原則 #2。
（Python 註解不進 AST，docstring 才會 —— 本檔的斷言對兩者都安全。）
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _tree(rel: str) -> ast.Module:
    return ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8"))


def _str_constants(tree: ast.Module) -> set[str]:
    """AST 內所有**字串字面量**（含 docstring，不含 `#` 註解）。"""
    return {
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }


class TestAppMustNotResurrectLoadedFlag:
    """app.py 不得再讓 `chips_loaded` 跨 session 復活。"""

    _REL = "app.py"

    def test_app_never_references_chips_loaded(self):
        """`chips_loaded` 這個 key 不得以任何形式出現在 app.py 的**程式碼**中。

        唯一的合法寫入者是 `tab_macro.py:185`（使用者按下按鈕）。app.py 只要
        碰到這個 key，就代表又有人試圖從 URL / cookie / 其他外部狀態把
        「已載入」旗標救回來 —— 而資料救不回來，於是空 session 又會被渲染成
        「已載入」。
        """
        _hits = sorted(s for s in _str_constants(_tree(self._REL)) if "chips_loaded" in s)
        assert not _hits, (
            f"{self._REL} 又引用了 chips_loaded：{_hits}\n"
            "→ 這個旗標只能由 tab_macro.py 在使用者實際按下按鈕時寫入。\n"
            "  從 URL / 任何跨 session 來源還原它，會讓「旗標活著、資料死掉」，\n"
            "  空 session 被渲染成已載入（燈號等待中 + 五頁總經未評估）。\n"
            "  見本檔 docstring 與 app.py 開機閘門的 FIX(S1) 註記。"
        )

    def test_query_param_restore_still_covers_sid(self):
        """負向守衛的反面：sid 還原是**正當**的，不可被連坐刪掉。

        sid ＝「使用者選了哪支股票」＝設定，不是抓回來的資料，
        跨 session 還原它不會製造任何假的已載入狀態。
        """
        _consts = _str_constants(_tree(self._REL))
        assert "_qp_sid" in _consts, (
            "app.py 不再還原 sid —— S1 只該拔掉 chips_loaded 的跨 session 還原，"
            "不該連坐移除個股代號這種純設定的還原"
        )


class TestMacroGatesStillHonest:
    """tab_macro 的兩道閘門必須真的看得到「有沒有資料」。"""

    _REL = "src/ui/tabs/tab_macro.py"

    def test_empty_state_gate_checks_real_data(self):
        """`_macro_loaded` 必須至少參考一個**真資料** key，不能只看旗標。

        只要 cl_data / mkt_info 其中一個仍在判定式裡，session 被重建後
        （chips_loaded 已不會復活）就會落到誠實空狀態。
        """
        _consts = _str_constants(_tree(self._REL))
        assert _consts & {"cl_data", "mkt_info"}, (
            f"{self._REL} 的空狀態閘門不再參考任何真資料 key "
            "→ 無法判斷「真的載入過」還是「只是旗標還在」"
        )

    def test_button_still_sets_attempt_flag(self):
        """反向守衛：`chips_loaded` 必須**留在** tab_macro。

        它承載「本 session 嘗試過載入」的語意 —— 抓取失敗時仍須為 True，
        section_chips 才能印出 FINMIND_TOKEN 診斷卡而不是假裝沒載入。
        修 S1 時若把它整個拔掉，會把失敗診斷一起消音（換一種不誠實）。
        """
        assert "chips_loaded" in _str_constants(_tree(self._REL)), (
            f"{self._REL} 的 chips_loaded 被移除 —— S1 只該拔 app.py 的跨 session "
            "還原，不該拔掉「本 session 嘗試過載入」這個語意本身"
        )
