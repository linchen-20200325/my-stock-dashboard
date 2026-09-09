"""src/services/macro_refresh_service.py — 頁1「🚀 更新今日戰情」的**取數編排**（L3）。

T3-1（客戶 2026-09-09 裁決：頁1 的按鈕要**原地**觸發台股今日資料重抓並即時
刷新本頁，不跳轉回舊分頁）。

═══ 這是「平行路徑」，不是「重構既有的」════════════════════════════════
客戶明令**舊 7 個頁籤保留原樣** ⇒ `src/ui/tabs/**` 本階段一個字都不動。
本檔因此是 `src/ui/tabs/tab_macro.py` spinner 區塊那條路徑的**第二條路**，
兩條並存。收編舊分頁是第二階段，**尚未獲准**。

⚠️ **本檔刻意不宣稱「與 `tab_macro` 零行為變更」** —— 那句話是假的。
已知的**刻意差異**共三處，每一處都在下面就地寫明理由：
  1. **`compute_and_store_jingqi` 帶 `df_adl is not None` 守衛**（`_step_jingqi`）
     —— `tab_macro` 沒有這個守衛，cron `scripts/update_macro_forward_test.py` 有。
     本檔跟 cron 站同一邊，理由見該處。
  2. **`compute_and_apply_market_assessment` 包在有逾時的執行緒裡**
     （`_run_with_timeout`）—— `tab_macro` 是直接同步呼叫，可以無限期卡住。
  3. **強制重抓模式不 pop 任何 session key** —— `tab_macro` 的
     `handlers._macro_session_reset()` 會 pop 10 個 key。理由見 `clear_macro_caches`。

═══ 分層（CLAUDE.md §8.2）═════════════════════════════════════════════
**L3 Service**：編排 L1 fetcher（`src.data.daily.daily_data_fetchers`）
＋ 既有 L3（`macro_fetch_orchestrator` / `macro_session_apply` / `jingqi_calc` /
`macro_trio_orchestrator` / `market_assessment_apply` / `data_registry_scanner`），
寫 `st.session_state`。**零 L4 / L5 import、零 UI 呼叫**（進度一律走
`on_event` 回呼交給呼叫端畫）。

§1 Fail Loud：每一步的成敗**逐步記錄在報告裡**，不吞、不合併、不四捨五入成
「更新完成」。部分成功**一律**回 `ok=False`（見 `MacroRefreshReport.ok`）。
"""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable

import streamlit as st

from shared.macro_compute import tw_now_str
from src.compute.macro.macro_session_patch import MACRO_PATCH_KEYS

# ══════════════════════════════════════════════════════════════════
# 模式
# ══════════════════════════════════════════════════════════════════
#: 正常更新：吃既有 `@st.cache_data` TTL 暖快取。
MODE_WARM: str = "warm"
#: 強制重抓：先清快取再抓（對齊舊分頁「🆕 強制重抓」的清除範圍）。
MODE_FORCE: str = "force"

# ══════════════════════════════════════════════════════════════════
# 顯示名 SSOT（呼叫端不得手抄 job key 或自己翻中文）
# ══════════════════════════════════════════════════════════════════
#: `fetch_macro_bundle` 的 job key → 畫面上的名字。
#:
#: key 一律沿用 orchestrator 自己的字串（`_jobs` 的鍵），**本檔不另立命名**。
SOURCE_LABELS: dict[str, str] = {
    "intl": "國際指數（道瓊 / 那斯達克 / 費半 / 10Y / DXY）",
    "tw": "台股大盤與匯率（^TWII / TWD=X）",
    "tech": "權值科技股（TSM / MSFT / NVDA …）",
    "inst": "三大法人買賣超（TWSE BFI82U → FinMind 補救）",
    "margin": "融資餘額（TWSE → HiStock → Wearn）",
    "adl": "市場廣度 ADL（漲跌家數比）",
    "li": "先行指標（期貨 / 選擇權 / 法人留倉）",
}

#: 取數之後的計算 / 落地步驟 → 畫面上的名字。
STEP_CLEAR: str = "clear"
STEP_FETCH: str = "fetch"
STEP_APPLY: str = "apply"
STEP_JINGQI: str = "jingqi"
STEP_TRIO: str = "trio"
STEP_MARKET: str = "market"
STEP_REGISTRY: str = "registry"

STEP_LABELS: dict[str, str] = {
    STEP_CLEAR: "清除快取（強制重抓模式）",
    STEP_FETCH: "並行抓取 7 個來源",
    STEP_APPLY: "寫入 session（cl_data / 先行指標 / 時間戳）",
    STEP_JINGQI: "旌旗指數（上漲佔比 5 日均）",
    STEP_TRIO: "M1B-M2 / 年線乖離 / 6 源總經快照",
    STEP_MARKET: "市場評估（mkt_info）",
    STEP_REGISTRY: "資料登錄中心掃描",
}

#: `compute_and_apply_market_assessment` 的逾時（秒）。
#:
#: 為什麼一定要包逾時：它的備援分支是
#: `get_market_assessment(df_index=None)` → `src.data.macro.fetch_yf_ohlcv('^TWII')`
#: —— **一次真的 yfinance 取數**，而 `tab_macro` 那條路是**直接同步呼叫、
#: 沒有任何上限**（socket hang 時整頁卡死）。
_MARKET_ASSESS_TIMEOUT_S: int = 45

# ══════════════════════════════════════════════════════════════════
# 這條路徑寫得到什麼 / 摸不到什麼（**畫面誠實標示的唯一來源**）
# ══════════════════════════════════════════════════════════════════
#: 本路徑**可能**寫入的 session key 全集（實測，非推測）。
#:
#: 來源逐項：
#:   · `MACRO_PATCH_KEYS`（9）—— L2 純函式的契約。
#:   · `jingqi_info`  ← `services.jingqi_calc`
#:   · `mkt_info`     ← `services.market_assessment_apply`
#:   · `m1b_m2_info` / `bias_info` / `macro_info` ← `services.macro_trio_orchestrator`
#:   · `data_registry` ← `services.data_registry_scanner`
#: 上列五個模組的 session 寫入點以 AST 掃描逐一確認（2026-09-09）；
#: `tests/test_p01_macro_refresh.py::TestWrittenKeysMatchTheModules` 把它釘住，
#: 任何一支多寫一個 key 而這裡沒補 → 紅燈。
WRITES_SESSION_KEYS: tuple[str, ...] = MACRO_PATCH_KEYS + (
    "jingqi_info", "mkt_info", "m1b_m2_info", "bias_info", "macro_info",
    "data_registry",
)


@dataclass(frozen=True)
class UntouchedBlock:
    """一個**這條路徑碰不到**的畫面區塊。

    ⚠️ 這份清單存在的理由（§1）：使用者按了「更新今日戰情」之後，**沒有更新到
    的東西如果留白，看起來就跟更新過一模一樣**。那是最便宜的一種說謊 ——
    畫面沒有寫任何假數字，卻讓人以為整頁都是今天的。

    Attributes:
        label: 畫面上那一塊叫什麼（使用者看得懂的名字，不是 session key）。
            ⚠️ **不要在 label 裡寫 Markdown 粗體**：呼叫端已經整段包 `**`，
            巢狀的 `**` 會讓畫面冒出裸露的星號（本批 AppTest 實測踩過）。
        session_key: 對應的 session key；`""` = 這一塊沒有單一對應 key。
        why: 為什麼這條路徑碰不到它。
        writer: **誰才寫得到**（2026-09-09 grep 實測結果，逐項可複查）。
    """

    label: str
    session_key: str
    why: str
    writer: str


#: 本階段**確定摸不到**的區塊。每一列的 `writer` 都是 2026-09-09 對
#: `src/` ＋ `app.py` ＋ `scripts/` grep `session_state['<key>'] =` 的實測結果。
#:
#: ⚠️ **單組結論**（§-2 規則 6）：這份清單是本次實作組一次掃描的產物，
#: 沒有第二組獨立驗過。它可能**漏列**（少講一個沒更新到的區塊），
#: 但它列出來的每一項都有 grep 證據。
UNTOUCHED_BLOCKS: tuple[UntouchedBlock, ...] = (
    UntouchedBlock(
        label="今日關鍵橫幅的門檻層（④）",
        session_key="macro_alerts",
        why=("門檻層掃描（`check_macro_alerts`）掛在舊「🌍 總經」分頁的"
             "中期桶渲染裡，本路徑沒有渲染那一段，所以掃不到。"
             "本輪之後那張卡最多是「已列出急變層、門檻層未評估」，**不會變綠**"),
        writer="src/ui/tabs/macro/section_mid.py（全 repo 唯一寫入點）",
    ),
    UntouchedBlock(
        label="建議持股（卡①）與市場位階（卡③）",
        session_key="warroom_summary / macro_state.json",
        why=("兩張卡都讀 L3 `macro_state_locker.get_macro_state()`，"
             "而它的四條來源是 `warroom_summary` 與 `macro_state.json` —— "
             "本路徑一個都沒寫。**它們顯示的是上一次跑舊分頁的結果**"),
        writer=("src/ui/tabs/macro/section_traffic_light.py ＋ "
                "src/ui/tabs/macro/section_state.py"),
    ),
    UntouchedBlock(
        label="新聞桶（🗞 系統性風險新聞數）",
        session_key="_macro_news_items",
        why="新聞 RSS 掃描掛在舊分頁的 News AI 區塊，本路徑不跑它",
        writer="src/ui/tabs/macro/section_news_ai.py",
    ),
    UntouchedBlock(
        label="外資期貨淨口的 `futures_net` 旗標",
        session_key="futures_net",
        why=("**全 repo 沒有任何一處寫這個 key**（實測 0 個寫入點）——"
             "五桶取數對它一律吃 `state.get('futures_net', 0)` 的預設值。"
             "⚠️ 這不是本路徑的缺口，是全站的：舊分頁按一百次也一樣。"
             "（判燈實際用的是 `li_latest['外資大小']`，那一項本路徑有更新）"),
        writer="（無）",
    ),
    UntouchedBlock(
        label="舊分頁的「已載入」旗標 `chips_loaded`",
        session_key="chips_loaded",
        why=("那是舊「🌍 總經」分頁自己的 gate 旗標。本路徑刻意不寫 —— "
             "寫了等於替另一個分頁宣稱「你的重資料已經載入」，"
             "而那頁的區塊有一半本路徑沒跑（見上面幾列）"),
        writer="app.py ＋ src/ui/tabs/tab_macro.py",
    ),
    UntouchedBlock(
        label="舊分頁的兩份畫圖快照 `intl_snap` / `ma_snap`",
        session_key="intl_snap / ma_snap",
        why="舊分頁渲染期才產生的繪圖中繼資料，與本頁的卡片無關",
        writer="src/ui/tabs/tab_macro.py（intl_snap）／macro/section_mid.py（ma_snap）",
    ),
)


# ══════════════════════════════════════════════════════════════════
# 報告
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class SourceResult:
    """單一資料來源（`fetch_macro_bundle` 的一個 job）的結論。"""

    name: str
    ok: bool
    detail: str = ""

    @property
    def label(self) -> str:
        """畫面顯示名。找不到就回 key 本身（**不編一個中文名**）。"""
        return SOURCE_LABELS.get(self.name, self.name)


@dataclass(frozen=True)
class StepResult:
    """單一步驟（取數之後的計算 / 落地）的結論。

    `skipped=True` 的語意是「**這一步這一輪沒有條件跑**」，與 `ok=False`
    （跑了但失敗）是兩件事 —— 混在一起就分不出「沒有廣度資料所以沒算旌旗」
    與「算旌旗的時候炸了」。
    """

    name: str
    ok: bool
    detail: str = ""
    skipped: bool = False

    @property
    def label(self) -> str:
        return STEP_LABELS.get(self.name, self.name)


@dataclass(frozen=True)
class MacroRefreshReport:
    """一次「更新今日戰情」的完整結論。**呼叫端照這份畫，不自己判斷成敗。**"""

    mode: str
    started_at: str
    elapsed_s: float
    sources: tuple[SourceResult, ...] = ()
    steps: tuple[StepResult, ...] = ()
    written_keys: tuple[str, ...] = ()
    popped_keys: tuple[str, ...] = ()
    cleared: tuple[str, ...] = ()
    untouched: tuple[UntouchedBlock, ...] = UNTOUCHED_BLOCKS

    @property
    def failures(self) -> tuple[str, ...]:
        """失敗項的顯示名 ＋ 原因。**跳過的步驟不算失敗。**"""
        _out = [f"{_s.label}：{_s.detail or '（來源沒有給原因）'}"
                for _s in self.sources if not _s.ok]
        _out += [f"{_t.label}：{_t.detail or '（沒有給原因）'}"
                 for _t in self.steps if not _t.ok and not _t.skipped]
        return tuple(_out)

    @property
    def skipped(self) -> tuple[str, ...]:
        """這一輪沒有條件跑的步驟。"""
        return tuple(f"{_t.label}：{_t.detail}" for _t in self.steps if _t.skipped)

    @property
    def ok(self) -> bool:
        """**全部來源與步驟都成功**才算成功。

        ⚠️ 這裡刻意沒有「大部分成功就算成功」的門檻：
        部分成功的那一輪，畫面上會有幾格是舊的、幾格是新的，而使用者**無從分辨**。
        把它標成成功，就是讓人拿混合新舊的畫面當今天的結論（§1）。
        """
        return not self.failures


# ══════════════════════════════════════════════════════════════════
# 逾時工具
# ══════════════════════════════════════════════════════════════════
def _run_with_timeout(fn: Callable[[], Any], *, timeout_s: int) -> Any:
    """在**有上限**的執行緒裡跑 `fn`，逾時就拋 `TimeoutError`。

    ⚠️ **不得寫成 `with ThreadPoolExecutor(...) as ex:`** ——
    `__exit__` 會 `shutdown(wait=True)`，也就是**等那條卡住的 thread 跑完**，
    `timeout=` 於是形同不存在。這個坑 `macro_fetch_orchestrator` 的
    「shutdown(wait=False) — 消除 `with TPE` 阻塞 7-20 分鐘的問題」註解記載過。
    這裡用 `try/finally` ＋ `shutdown(wait=False, cancel_futures=True)`。

    ⚠️ **ScriptRunContext 必須手動接到 worker thread 上**：`fn` 多半會碰
    `st.session_state`（例如 `compute_and_apply_market_assessment` 寫 `mkt_info`），
    而沒有 ctx 的 thread 讀寫 session 在 Streamlit 上會失敗 / 變成 no-op。
    接不上時（裸跑 / CI / streamlit 內部 API 改名）**照跑不誤**，
    因為那些環境本來就沒有 session runtime。

    ⚠️ **誠實揭露一個做不到的事**：逾時之後那條 thread **無法被殺掉**
    （Python 沒有這種東西）。它稍後若跑完，仍可能把結果寫進 session ——
    也就是報告說「逾時」，而下一輪 rerun 可能看到那份資料**遲到**。
    報告不會因此改口：它記錄的是「這一輪等到逾時為止沒等到」，那是實話。
    """
    _ctx = None
    try:  # noqa: SIM105 — 這一段在裸跑環境本來就會缺，不是錯誤
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        _ctx = get_script_run_ctx()
    except Exception as _e_ctx:  # noqa: BLE001
        print(f"[總經刷新] ⚠️ 取不到 ScriptRunContext（裸跑環境？）：{_e_ctx!r}")

    def _runner():
        if _ctx is not None:
            try:
                from streamlit.runtime.scriptrunner import add_script_run_ctx
                add_script_run_ctx(threading.current_thread(), _ctx)
            except Exception as _e_add:  # noqa: BLE001
                print(f"[總經刷新] ⚠️ ctx 掛不上 worker thread：{_e_add!r}")
        return fn()

    _ex = ThreadPoolExecutor(max_workers=1)
    try:
        return _ex.submit(_runner).result(timeout=timeout_s)
    finally:
        try:
            _ex.shutdown(wait=False, cancel_futures=True)
        except TypeError:          # Python < 3.9
            _ex.shutdown(wait=False)


# ══════════════════════════════════════════════════════════════════
# 快取清除
# ══════════════════════════════════════════════════════════════════
def clear_macro_caches() -> tuple[str, ...]:
    """強制重抓模式的快取清除。回傳「實際清掉了哪幾層」。

    清除範圍對齊舊分頁「🆕 強制重抓」（`src/ui/tabs/macro/handlers.py::
    _on_force_clear_click`）的**前三段**：pkl → `st.cache_data` → proxy URL cache。

    ⚠️ **這是一份刻意的重複實作，不是漏看**（§2.1 SSOT）：
    正解是讓 `handlers._on_force_clear_click` 改成呼叫本函式，但
    `src/ui/tabs/**` 在本階段**一個字都不准動**（客戶明令舊 7 頁籤保留原樣）。
    兩份會不會漂開？會 —— 所以 `tests/test_p01_macro_refresh.py::
    TestForceClearMatchesTheOldTab` 逐項比對兩邊清的東西，漂了就紅燈。
    **第二階段收編舊分頁時，第一件事就是把這份併回去。**

    ⛔ **本函式刻意不做 `_macro_session_reset()`（舊分頁的第四段）。**
    那一段會 pop 掉 10 個 session key，其中 `warroom_summary` **本路徑寫不回來**
    （唯一寫入點在 `section_traffic_light.py`，見 `UNTOUCHED_BLOCKS`）——
    清掉它等於讓使用者按一次「更新」之後，建議持股與市場位階兩張卡
    從「上一輪的舊值」變成「完全沒有」。**那不是更新，是刪資料。**
    代價：強制重抓模式下，舊值會被新值覆蓋而不是先歸零 —— 若某一源全敗，
    畫面上留的是上一輪的值。這一點由 `cl_ts` 時間戳與本報告的失敗清單承載。
    """
    _cleared: list[str] = []
    try:
        from shared.cache_layer import _pkl_clear_all
        _pkl_clear_all()
        _cleared.append("本機 pkl 快取")
    except Exception as _e:  # noqa: BLE001 — §1：出聲，不吞
        print(f"[總經刷新] pkl clear failed: {_e!r}")
    try:
        st.cache_data.clear()
        _cleared.append("st.cache_data")
    except Exception as _e:  # noqa: BLE001
        print(f"[總經刷新] st.cache_data clear failed: {_e!r}")
    try:
        from src.data.proxy import proxy_helper as _ph
        _ph._URL_CACHE.clear()
        _ph.reset_proxy_cache()
        _cleared.append("proxy URL / config 快取")
    except Exception as _e:  # noqa: BLE001
        print(f"[總經刷新] proxy clear failed: {_e!r}")
    print(f"[總經刷新] 🗑️ 強制重抓已清：{_cleared}")
    return tuple(_cleared)


# ══════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════
def _secret(key: str) -> str:
    """讀 `st.secrets`；無 secrets.toml 時（CI / 裸跑）回空字串，不炸。"""
    try:
        return str(st.secrets.get(key) or "") if hasattr(st, "secrets") else ""
    except Exception:  # noqa: BLE001
        return ""


def refresh_macro_now(*, mode: str = MODE_WARM,
                      on_event: Callable[[str, Any], None] | None = None,
                      ) -> MacroRefreshReport:
    """原地重抓今日台股 / 總經資料，並把結果寫進 `st.session_state`。

    Args:
        mode: `MODE_WARM`（吃暖快取）或 `MODE_FORCE`（先清快取再抓）。
            非這兩者一律當 `MODE_WARM`（**並在報告的 `mode` 欄照實記下傳進來的
            值**，不假裝使用者選了 warm）。
        on_event: 進度回呼 `on_event(kind, result)`，
            `kind` ∈ `{"source", "step"}`，`result` 是 `SourceResult` /
            `StepResult` **本體**（不是散開的欄位）。
            ⚠️ 傳物件不傳欄位是刻意的：呼叫端因此拿得到 `label`（顯示名 SSOT
            在本檔）與 `skipped`（跳過 ≠ 成功）。散開成 `(name, ok, detail)`
            會逼呼叫端自己查一次中文名、並且**看不到 `skipped`** ——
            那會讓「本輪沒有條件跑」在進度列上顯示成一個 ✅。
            **純顯示用**；自己拋例外不影響取數。

    Returns:
        `MacroRefreshReport` —— 逐來源、逐步驟的成敗，加上「這一輪寫了哪些
        session key」與「哪些區塊本路徑摸不到」。

    ⚠️ **本函式一律 `load_heavy=True`。** 頁1 的按鈕語意就是「抓今天的」，
    冷啟動輕量模式（只抓 3 個 yfinance job）是舊分頁**進頁不自動抓**那個
    設計的產物，按鈕路徑用不到它。
    """
    _t0 = time.time()
    _started = tw_now_str()
    _sources: list[SourceResult] = []
    _steps: list[StepResult] = []
    _cleared: tuple[str, ...] = ()

    def _emit(kind: str, result: Any) -> None:
        if on_event is None:
            return
        try:
            on_event(kind, result)
        except Exception as _e:  # noqa: BLE001 — 顯示壞掉不得擋取數
            print(f"[總經刷新] ⚠️ on_event 回呼失敗，已略過：{_e!r}")

    def _step(name: str, ok: bool, detail: str = "", skipped: bool = False) -> None:
        _r = StepResult(name=name, ok=ok, detail=detail, skipped=skipped)
        _steps.append(_r)
        _emit("step", _r)

    # ── 0. 清快取（force）──────────────────────────────────────
    if mode == MODE_FORCE:
        _cleared = clear_macro_caches()
        _step(STEP_CLEAR, True, "、".join(_cleared) or "（沒有任何一層清成功）")

    # ── 1. 並行抓 7 個來源 ─────────────────────────────────────
    # ⚠️ **刻意不把 `fetch_macro_bundle` 包進 `_run_with_timeout`**：
    #   (a) 它自己已經有上限（`_AS_COMPLETED_TIMEOUT` = max(job timeout)+20s）
    #       ＋ `shutdown(wait=False, cancel_futures=True)`，會準時回來；
    #   (b) 包起來會讓 `on_job_done` 從 worker thread 被呼叫 → 呼叫端的
    #       `st.status().write()` 失去 ScriptRunContext，逐來源進度就不會出現。
    #   兩害相權：留在主執行緒。
    from src.data.daily.daily_data_fetchers import (
        fetch_adl, fetch_institutional, fetch_margin_balance, fetch_single,
    )
    from src.services.daily_checklist import INTL_MAP, TECH_MAP, TW_MAP
    from src.services.macro_fetch_orchestrator import fetch_macro_bundle

    from src.config import FINMIND_TOKEN, get_finmind_token
    _fm = (get_finmind_token() or FINMIND_TOKEN
           or os.environ.get("FINMIND_TOKEN", "") or "")

    def _on_job(name: str, ok: bool, detail: str) -> None:
        _r = SourceResult(name=name, ok=ok, detail=detail)
        _sources.append(_r)
        _emit("source", _r)

    try:
        _bundle = fetch_macro_bundle(
            load_heavy=True,
            prev_cl_data=st.session_state.get("cl_data") or {},
            fm_token=_fm, li_token=_fm,
            intl_map=INTL_MAP, tw_map=TW_MAP, tech_map=TECH_MAP,
            fetch_single=fetch_single,
            fetch_institutional=fetch_institutional,
            fetch_margin_balance=fetch_margin_balance,
            fetch_adl=fetch_adl,
            on_job_done=_on_job,
        )
        _step(STEP_FETCH, True, f"{_bundle.get('elapsed_s', 0.0):.1f}s")
    except Exception as _e:  # noqa: BLE001 — 整條抓取鏈掛掉：據實回報，不假裝有資料
        print(f"[總經刷新] ❌ fetch_macro_bundle 整條失敗：{_e!r}")
        _step(STEP_FETCH, False, f"{type(_e).__name__}: {_e}")
        return MacroRefreshReport(
            mode=mode, started_at=_started, elapsed_s=time.time() - _t0,
            sources=tuple(_sources), steps=tuple(_steps), cleared=_cleared)

    # ── 2. 寫 session（純函式算 patch，L3 負責寫）─────────────
    _written: tuple[str, ...] = ()
    _popped: tuple[str, ...] = ()
    try:
        from src.services.macro_session_apply import apply_macro_bundle
        _patch, _pops = apply_macro_bundle(
            _bundle, load_heavy=True, now_str=tw_now_str())
        _written, _popped = tuple(_patch), _pops
        _step(STEP_APPLY, True, f"寫入 {len(_written)} 鍵 / 刪除 {len(_popped)} 鍵")
    except Exception as _e:  # noqa: BLE001
        print(f"[總經刷新] ❌ apply_macro_bundle 失敗：{_e!r}")
        _step(STEP_APPLY, False, f"{type(_e).__name__}: {_e}")

    # ── 3. 旌旗指數 ─────────────────────────────────────────────
    # ⛔ **與 `tab_macro` 刻意不同：這裡帶 `df_adl is not None` 守衛。**
    # `tab_macro.py` 是無條件 `compute_and_store_jingqi(df_adl_raw)`，
    # 而 cron `scripts/update_macro_forward_test.py` 有守衛。本檔站 cron 那邊。
    # **理由（不是風格偏好）**：`compute_and_store_jingqi(None)` **不是 no-op** ——
    # 它會掉進「大盤估算」備援（`40 + 上漲天數 × 5`）生出一個看起來正常的數字，
    # 並讓下游的 `health_partial` 由 True 變 False，也就是把「沒有廣度資料」
    # 寫成「有一個估算值、而且資料是齊的」。那是 §1 的造假，而且這個值會被
    # 前進式驗證帳本（`macro_fwd_test_store`）吃進去，**污染的是歷史紀錄**。
    _df_adl = _bundle.get("df_adl_raw")
    if _df_adl is not None:
        try:
            from src.services.jingqi_calc import compute_and_store_jingqi
            compute_and_store_jingqi(_df_adl)
            _step(STEP_JINGQI, True, "ADL 主源")
        except Exception as _e:  # noqa: BLE001
            print(f"[總經刷新] ❌ compute_and_store_jingqi 失敗：{_e!r}")
            _step(STEP_JINGQI, False, f"{type(_e).__name__}: {_e}")
    else:
        _step(STEP_JINGQI, True,
              "本輪沒有 ADL 廣度資料 → **不以大盤漲跌估算一個旌旗值**"
              "（估出來的數字會被當成真的廣度，並清掉「資料不全」的記號）",
              skipped=True)

    # ── 4. M1B-M2 / 乖離 / 6 源總經 ────────────────────────────
    # 同 1：內部已有 200s 全域上限 ＋ `shutdown(wait=False)`，且它的 session
    # 寫入發生在**呼叫端執行緒**（pool 收完之後）→ 不再外包一層 thread。
    # `global_timeout_s` 不覆寫：覆寫等於在 `tab_macro` 之外多一個上限數字，
    # 而 `tests/test_p0a_key_alerts_and_spinner.py` 的上界守衛是從**預設值**解析的。
    try:
        from src.services.macro_trio_orchestrator import run_macro_trio_and_persist
        run_macro_trio_and_persist(
            tw_raw=_bundle.get("tw_raw") or {},
            fred_api_key=(os.environ.get("FRED_API_KEY") or _secret("FRED_API_KEY")),
            fm_token=(os.environ.get("FINMIND_TOKEN") or _secret("FINMIND_TOKEN") or _fm),
        )
        _step(STEP_TRIO, True, "")
    except Exception as _e:  # noqa: BLE001
        print(f"[總經刷新] ❌ run_macro_trio_and_persist 失敗：{_e!r}")
        _step(STEP_TRIO, False, f"{type(_e).__name__}: {_e}")

    # ── 5. 市場評估（**會打 yfinance → 必須有上限**）───────────
    try:
        from src.services.market_assessment_apply import (
            compute_and_apply_market_assessment,
        )
        _run_with_timeout(
            lambda: compute_and_apply_market_assessment(
                inst=_bundle.get("inst") or {},
                tw_raw=_bundle.get("tw_raw") or {},
                margin=_bundle.get("margin"),
                df_adl=_df_adl),
            timeout_s=_MARKET_ASSESS_TIMEOUT_S)
        _step(STEP_MARKET, True, "")
    except Exception as _e:  # noqa: BLE001 — 含 TimeoutError
        print(f"[總經刷新] ❌ 市場評估失敗 / 逾時：{_e!r}")
        _step(STEP_MARKET, False,
              f"{type(_e).__name__}: {_e or f'超過 {_MARKET_ASSESS_TIMEOUT_S}s'}")

    # ── 6. 資料登錄中心（純 session 掃描，無對外請求）───────────
    try:
        from src.services.data_registry_scanner import scan_and_write_data_registry
        scan_and_write_data_registry(
            intl_map=INTL_MAP, tw_map=TW_MAP, tech_map=TECH_MAP)
        _step(STEP_REGISTRY, True, "")
    except Exception as _e:  # noqa: BLE001
        print(f"[總經刷新] ❌ scan_and_write_data_registry 失敗：{_e!r}")
        _step(STEP_REGISTRY, False, f"{type(_e).__name__}: {_e}")

    _report = MacroRefreshReport(
        mode=mode, started_at=_started, elapsed_s=time.time() - _t0,
        sources=tuple(_sources), steps=tuple(_steps),
        written_keys=_written, popped_keys=_popped, cleared=_cleared)
    print(f"[總經刷新] {'✅' if _report.ok else '⚠️'} "
          f"{_report.elapsed_s:.1f}s 失敗 {len(_report.failures)} 項")
    return _report
