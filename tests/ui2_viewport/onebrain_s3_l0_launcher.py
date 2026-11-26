"""OneBrain S3-L0 可操作隔離原型的專用 streamlit 入口（**tests-only**；⛔ 不是產品入口、不是正式 OneBrain／Real 功能）。

    streamlit run tests/ui2_viewport/onebrain_s3_l0_launcher.py          （再以 `?ui2_dev=1` 開頁可切場景）

客戶 R16 核准範圍（「C：…核准四主題、預設持股健檢、行內證據文案及兩個 tests-only 檔案」）：
在**不改任何既有檔**（`src/ui2`、`shared`、`app_ui2.py`、`scenarios.py`…）的前提下，把真 `app_ui2.py`（`runpy`）跑起來，
並只在下列條件**全部**成立時，把 💼 持股頁「🤖 OneBrain 持股摘要：⬜ 尚未提供」那個既有 L1 槽換成示範內容，
同時在第一屏之後、槽之前畫出四主題切換（原生 `st.radio`，horizontal）：
  ① 頁＝💼 持股（`P4_HOLD`）② 場景＝`cold` ③ 走 FAKE（`vm.is_fake`）④ 該頁 VM 恰有一個 `onebrain` L1 區塊且仍是原本的 `尚未提供` 槽。
其餘一律原樣轉發（Real、一般 FAKE、非持股頁、非 cold ⇒ 無選擇器、無示範內容；Real VM 不經本檔任何程式）。

═══ 四主題（預設持股健檢）與槽內四列 ═══
主題：大盤／產業前瞻／持股健檢／反方風險。槽內以既有 `FieldVM` 行顯示四列：支持證據／反面證據／缺項／拒用。
* 支持／反面證據：只收「有可辨識來源且有資料日」的合成夾具；每筆明標「示意／合成」，非即時、非投資建議。
* 無輸入的列一律 `⬜ 無法判定（無○○輸入）`（unknown ≠ safe；缺資料不補零）。
* 缺項／拒用：只顯示**固定、可公開**的原因與筆數；被拒用項目的原值、文字**絕不**進入 VM／DOM／摘要／log。
* 單純「引用」（沒有可核對來源與資料日）不冒充支持，只計入缺項。
* 風險上限類夾具不得推出反證：直接略過，既不進支持也不進反面。
* 大盤主題的句型（C3）與字數口徑（D7）客戶尚未裁示：本主題不寫任何句子；四列皆為功能層級的「⬜ 尚未提供（本主題尚未開放）」，標題明示「預覽」。
  三種缺值字樣不混用：「尚未提供」＝功能未開放；「無法判定」＝有判讀流程但沒有輸入；「資料未取得」只留給真的缺資料（本原型的列不使用）。

⛔ 零網路、零時鐘（判讀時點固定）、零 Secrets、不讀 Sheet／OAuth、不接 AI／Provider、不 import 任何決策摘要／OneBrain 模組。
夾具為 S3 專用**合成**資料，寫在本檔內；任何夾具出錯 ⇒ 記 log（只記例外型別）並退回原本的槽，頁面與既有規則照常可操作。

環境變數（皆由啟動端設定）：
  UI2_S3_L0_SEED=0         不預設落在「💼 持股／FAKE／cold」（預設會；只在該 session 尚無對應 key 時播種）
  UI2_S3_L0_SEAL_LOG=path  封網記錄檔（JSON lines）：第一行＝啟動標記 `{"kind": "sealed"}`，其後每行是一次被拒絕的非 loopback 連線。
                           launcher `main()` 一律封網（拒絕非 loopback 的連線／名稱解析）；此變數只決定是否留記錄。
本檔狀態（安裝哨兵、計數）放在 **shell／hold 模組**上，不是本檔全域（streamlit 每次 rerun 都重新執行本檔）。
`install()`／`uninstall()` 供測試 fixture 以 try/finally 還原。
"""
from __future__ import annotations

import dataclasses
import importlib
import ipaddress
import json
import logging
import os
import runpy
import socket
import sys
import threading
from dataclasses import dataclass
from html import escape
from datetime import date
from pathlib import Path

try:
    _ROOT = Path(__file__).resolve().parents[2]
except NameError:                                  # 被某些 runner 以 exec 載入且無 __file__
    _ROOT = Path(os.getcwd())
if str(_ROOT) not in sys.path:
    sys.path.insert(0, _ROOT.as_posix())

from shared.ui2_contract.models import (  # noqa: E402
    CapabilityState, FieldState, FieldVM, JudgementState,
)
from shared.ui2_contract.pages import FEED_FAKE, P4_HOLD, SCENARIO_COLD  # noqa: E402
from shared.ui2_contract.text import TEXT_NOT_PROVIDED, TEXT_RISK_CAP_UNDETERMINABLE  # noqa: E402

_log = logging.getLogger(__name__)

ENV_SEED = "UI2_S3_L0_SEED"
ENV_SEAL_LOG = "UI2_S3_L0_SEAL_LOG"

SHELL_MODULE = "src.ui2.shell.app"
HOLD_MODULE = "src.ui2.views.hold"
ORIG_VIEWS_ATTR = "_s3l0_orig_views"      # 掛在 shell 模組：原 VIEWS（哨兵；存在＝已安裝）
ORIG_MD_ATTR = "_s3l0_orig_md"            # 掛在 hold 模組：原 `_md`
STATE_ATTR = "_s3l0_state"                # 掛在 shell 模組：計數與當次 run 狀態
SEAL_ATTR = "_s3l0_seal_state"            # 掛在 socket 模組：封網狀態

# ── session key（G9 紀律：一律 `ui2_` 前綴；純 UI 狀態）────────────────────────
TOPIC_KEY = "ui2_s3l0_topic"
LAST_TOPIC_KEY = "ui2_s3l0_topic_last"     # 最近一次有效主題（segmented_control 單選可被點掉成 None；以此還原，不讓畫面落在「無主題」）
BOX_KEY = "ui2_s3l0_topic_box"            # 容器 key（CSS／測試錨點 `.st-key-ui2_s3l0_topic_box`；非 session_state）
SESSION_KEYS = (TOPIC_KEY, LAST_TOPIC_KEY)

TOPIC_MARKET = "大盤"
TOPIC_INDUSTRY = "產業前瞻"
TOPIC_HOLDINGS = "持股健檢"
TOPIC_COUNTER = "反方風險"
TOPICS = (TOPIC_MARKET, TOPIC_INDUSTRY, TOPIC_HOLDINGS, TOPIC_COUNTER)
DEFAULT_TOPIC = TOPIC_HOLDINGS
NOT_OPEN_TOPICS = (TOPIC_MARKET,)             # 句型（C3）與字數口徑（D7）未裁：本主題尚未開放，不寫任何句子
SELECTOR_LABEL = "預覽主題（示意）"

LABEL_SUPPORT = "支持證據"
LABEL_COUNTER = "反面證據"
LABEL_MISSING = "缺項"
LABEL_REJECTED = "拒用"
ROW_LABELS = (LABEL_SUPPORT, LABEL_COUNTER, LABEL_MISSING, LABEL_REJECTED)

STATUS_PREFIX = "目前主題："
SYNTHETIC_MARK = "示意／合成"
SECTION_ID = "onebrain"
ORIG_SLOT_TITLE = "🤖 OneBrain 持股摘要"


def _section_title(topic: str) -> str:
    tail = "（預覽）" if topic == TOPIC_MARKET else ""
    return f"🤖 OneBrain 示意｜{topic}{tail}｜合成資料，非即時、非投資建議"


def status_text(topic: str) -> str:
    return f"{STATUS_PREFIX}{topic}"


def _no_input(what: str) -> str:
    """無輸入列的固定字樣。開頭必須是 `TEXT_RISK_CAP_UNDETERMINABLE`（`⬜ 無法判定`；判定態允許字樣）。"""
    return f"{TEXT_RISK_CAP_UNDETERMINABLE}（無{what}輸入）"


# ══════════════════════════════════════════════════════════════════════
# 合成夾具（S3 專用；全部是示意資料，不是真實行情、持股或建議）
# ══════════════════════════════════════════════════════════════════════
#: 判讀時點（固定；⛔ 時鐘）。資料日晚於它＝時點不合格；早於它超過 MAX_AGE_DAYS 天＝過期。
REFERENCE_DATE = date(2026, 11, 25)
MAX_AGE_DAYS = 90                              # 夾具專用的過期天數；不是產品門檻、不外露

KIND_SUPPORT = "support"
KIND_COUNTER = "counter"
KIND_CITATION = "citation"                     # 只被「引用」：不是證據
KIND_RISK_CAP = "risk_cap"                     # 風險上限類：不得推出反證，一律略過
KIND_MISSING = "missing"

#: 缺項／拒用的「原因」只准來自這張**固定、可公開的常數表**（⛔ 夾具自寫文字、原值；`classify` 對表外原因 fail loud）。
REASON_CITED_ONLY = "只被引用，沒有可核對的來源與資料日"      # 單純「引用」：不是證據
REASON_NO_SOURCE = "沒有可核對的來源"
REASON_NO_DATE = "沒有可辨識的資料日"
REASON_NO_FINANCIALS = "最新一季財報尚未取得"
REASON_NO_PEER = "同業對照尚未取得"
REASON_STALE = "資料已過期"
REASON_PIT = "資料日晚於判讀時點"
PUBLIC_MISSING_REASONS = (REASON_CITED_ONLY, REASON_NO_SOURCE, REASON_NO_DATE, REASON_NO_FINANCIALS, REASON_NO_PEER)
PUBLIC_REJECT_REASONS = (REASON_STALE, REASON_PIT)
PUBLIC_REASONS = PUBLIC_MISSING_REASONS + PUBLIC_REJECT_REASONS


@dataclass(frozen=True)
class Item:
    kind: str
    text: str                       # 合成敘述；缺項類（KIND_MISSING）必為 PUBLIC_MISSING_REASONS 內的固定原因
    source: str | None = None       # 合成來源名稱
    as_of: str | None = None        # ISO 資料日 YYYY-MM-DD
    raw: str | None = None          # 「原值」：只供夾具表達被拒用的資料；任何輸出面都不得出現


#: 被拒用項目的原值（測試用哨兵；唯一定義處，測試以此掃描 VM／DOM／摘要／log）。
LEAKY_RAW_VALUES = ("7777.77", "原值哨兵甲", "原值哨兵乙")

FIXTURES: dict[str, tuple[Item, ...]] = {
    TOPIC_MARKET: (),
    TOPIC_INDUSTRY: (
        Item(KIND_SUPPORT, "合成產業甲 近三個月訂單維持穩定", "合成產業月報", "2026-11-10"),
        Item(KIND_MISSING, REASON_NO_PEER),
    ),
    TOPIC_HOLDINGS: (
        Item(KIND_SUPPORT, "合成標的甲 最近一季營收高於去年同季", "合成財報摘要", "2026-11-05"),
        Item(KIND_SUPPORT, "合成標的甲 近月法人持股比例持平", "合成籌碼月表", "2026-11-18"),
        Item(KIND_COUNTER, "合成標的甲 毛利率較前一季下滑", "合成財報摘要", "2026-11-05"),
        Item(KIND_CITATION, "合成標的甲 於法說會被提及擴產計畫"),
        Item(KIND_RISK_CAP, "合成組合風險上限接近滿水位", "合成組合表", "2026-11-20"),
        Item(KIND_SUPPORT, "合成標的甲 目標值 7777.77", "合成舊報告", "2026-05-01", raw="7777.77"),
        Item(KIND_COUNTER, "合成標的甲 原值哨兵甲", "合成預告表", "2027-01-15", raw="原值哨兵甲"),
        Item(KIND_MISSING, REASON_NO_FINANCIALS),
    ),
    TOPIC_COUNTER: (
        Item(KIND_COUNTER, "合成標的甲 應收帳款週轉天數拉長", "合成財報摘要", "2026-11-05"),
        Item(KIND_COUNTER, "合成標的乙 大股東近月持股下降", "合成籌碼月表", "2026-11-16"),
        Item(KIND_RISK_CAP, "合成組合風險上限接近滿水位", "合成組合表", "2026-11-20"),
        Item(KIND_COUNTER, "合成標的乙 原值哨兵乙", "合成舊報告", "2026-02-01", raw="原值哨兵乙"),
        Item(KIND_MISSING, REASON_NO_PEER),
    ),
}


@dataclass(frozen=True)
class Buckets:
    support: tuple[Item, ...] = ()
    counter: tuple[Item, ...] = ()
    missing: tuple[str, ...] = ()          # 只放固定可公開字樣
    rejected: tuple[str, ...] = ()         # 只放固定可公開原因（PUBLIC_REJECT_REASONS 之一）


def _parse_day(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def classify(items, reference: date = REFERENCE_DATE) -> Buckets:
    """把夾具分桶（純函式；決定性）。

    * `risk_cap`：略過（⛔ 不得推出反證，也不當支持）。
    * `citation`：不是證據 ⇒ 缺項 `REASON_CITED_ONLY`。
    * `support`／`counter`：缺來源 ⇒ 缺項 `REASON_NO_SOURCE`；資料日缺或無法解析 ⇒ 缺項 `REASON_NO_DATE`；
      資料日晚於判讀時點 ⇒ 拒用 `REASON_PIT`；早於判讀時點超過 `MAX_AGE_DAYS` ⇒ 拒用 `REASON_STALE`；其餘才進支持／反面。
    * 缺項類夾具：其 `text` 必為 `PUBLIC_MISSING_REASONS` 內的固定原因（表外 ⇒ ValueError）。
    缺項／拒用只留固定常數表內的原因，⛔ 保留夾具的文字或原值。
    """
    support: list[Item] = []
    counter: list[Item] = []
    missing: list[str] = []
    rejected: list[str] = []
    for it in items:
        if it.kind == KIND_RISK_CAP:
            continue
        if it.kind == KIND_MISSING:
            if it.text not in PUBLIC_MISSING_REASONS:
                raise ValueError("缺項原因不在固定常數表內")
            missing.append(it.text)
            continue
        if it.kind == KIND_CITATION:
            missing.append(REASON_CITED_ONLY)
            continue
        if it.kind not in (KIND_SUPPORT, KIND_COUNTER):
            raise ValueError("未知的夾具種類")
        day = _parse_day(it.as_of)
        if not it.source:
            missing.append(REASON_NO_SOURCE)
        elif day is None:
            missing.append(REASON_NO_DATE)
        elif day > reference:
            rejected.append(REASON_PIT)
        elif (reference - day).days > MAX_AGE_DAYS:
            rejected.append(REASON_STALE)
        elif it.kind == KIND_SUPPORT:
            support.append(it)
        else:
            counter.append(it)
    return Buckets(tuple(support), tuple(counter), tuple(missing), tuple(rejected))


def _evidence_text(items) -> str:
    return "；".join(f"［{SYNTHETIC_MARK}］{i.text}（來源：{i.source}，資料日 {i.as_of}）" for i in items)


def _grouped(reasons) -> str:
    seen: dict[str, int] = {}
    for r in reasons:
        seen[r] = seen.get(r, 0) + 1
    return "；".join(f"{r}（{n} 項）" if n > 1 else r for r, n in seen.items())


def _ok_row(label: str, text: str) -> FieldVM:
    return FieldVM(label=label, state=FieldState.OK, value_text=text)


def _undeterminable_row(label: str, what: str) -> FieldVM:
    return FieldVM(label=label, state=JudgementState.UNDETERMINABLE, status_text=_no_input(what))


def _not_provided_row(label: str) -> FieldVM:
    """功能層級「尚未提供」（⬜ 尚未提供＝功能未開放；⛔ 不是缺資料、不是無法判定）。"""
    return FieldVM(label=label, state=None, capability=CapabilityState.NOT_PROVIDED,
                   status_text=f"{TEXT_NOT_PROVIDED}（本主題尚未開放）")


def build_fields(topic: str) -> tuple[FieldVM, ...]:
    """某主題的槽內四列（支持證據／反面證據／缺項／拒用）。未知主題 ⇒ KeyError（呼叫端錯誤，不猜）。"""
    b = classify(FIXTURES[topic])
    if topic in NOT_OPEN_TOPICS:
        return tuple(_not_provided_row(lab) for lab in ROW_LABELS)
    support = (_ok_row(LABEL_SUPPORT, _evidence_text(b.support)) if b.support
               else _undeterminable_row(LABEL_SUPPORT, "支持"))
    counter = (_ok_row(LABEL_COUNTER, _evidence_text(b.counter)) if b.counter
               else _undeterminable_row(LABEL_COUNTER, "反證"))
    # 缺項列＝「列出缺什麼」的陳述（原因取自固定常數表），不是資料缺漏態本身 ⇒ 不掛「資料未取得」之類狀態 chip。
    missing = (_ok_row(LABEL_MISSING, "缺：" + _grouped(b.missing))
               if b.missing else _undeterminable_row(LABEL_MISSING, "缺項"))
    rejected = (_ok_row(LABEL_REJECTED, "未採用：" + _grouped(b.rejected) + "（不顯示原值）")
                if b.rejected else _undeterminable_row(LABEL_REJECTED, "拒用"))
    return (support, counter, missing, rejected)


def summary_text(topic: str) -> str:
    """該主題槽內的純文字摘要（螢幕閱讀器順序；測試用來證明拒用原值不外洩）。"""
    parts = [_section_title(topic)]
    for f in build_fields(topic):
        parts.append(" ".join(x for x in (f.label, f.value_text, f.status_text, f.detail) if x))
    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════════
# 注入（只換 shell 的 VIEWS 與 hold 的 `_md`；src 不動）
# ══════════════════════════════════════════════════════════════════════
_TL = threading.local()          # `after_first`：本次 hold 渲染中、第一個 markdown 之後要畫的選擇器


def _shell():
    return importlib.import_module(SHELL_MODULE)


def get_state(shell=None) -> dict:
    shell = shell or _shell()
    st = getattr(shell, STATE_ATTR, None)
    if st is None:
        st = {"installs": 0, "calls": 0, "injected": 0, "fallbacks": 0, "topic": None, "lock": threading.Lock()}
        setattr(shell, STATE_ATTR, st)
    return st


def is_installed() -> bool:
    return getattr(_shell(), ORIG_VIEWS_ATTR, None) is not None


def current_topic(session_state) -> str:
    """目前主題：選擇器的值；缺值（含被點掉的 None）或不是四主題之一 ⇒ 最近一次有效主題；仍無 ⇒ 預設（fail-closed，不猜）。"""
    t = session_state.get(TOPIC_KEY)
    if t in TOPICS:
        return t
    last = session_state.get(LAST_TOPIC_KEY)
    return last if last in TOPICS else DEFAULT_TOPIC


def _plan(vm):
    """回傳要渲染的 VM（槽已換成示範內容）；不適用 ⇒ None。夾具出錯 ⇒ 例外（呼叫端 fail-closed 退回原 VM）。"""
    import streamlit as st
    if not (vm.page_id == P4_HOLD and vm.scenario_id == SCENARIO_COLD and vm.is_fake):
        return None
    slots = [s for s in vm.context.sections if s.section_id == SECTION_ID and s.level == "L1"]
    if len(slots) != 1:
        return None
    slot = slots[0]
    if not (len(slot.fields) == 1 and slot.fields[0].capability is CapabilityState.NOT_PROVIDED):
        return None                                   # 已不是原本的「尚未提供」槽 ⇒ 不蓋掉
    topic = current_topic(st.session_state)
    fields = build_fields(topic)
    new_slot = dataclasses.replace(slot, title=_section_title(topic), fields=fields)
    secs = tuple(new_slot if s is slot else s for s in vm.context.sections)
    return dataclasses.replace(vm, context=dataclasses.replace(vm.context, sections=secs))


#: 只在「本次 run 確實注入」時才輸出（與選擇器同生同滅）：桌機把槽內四列由單行 flex 改成直排，讓四列各占一行、可讀。
#: ⛔ 不動 shell.CSS；只作用在 `[data-ui2-l1="onebrain"]` 這個槽。
SLOT_CSS = (
    '<style>.ui2-m-onebrain[data-ui2-l1="onebrain"]{display:block}'
    '.ui2-m-onebrain[data-ui2-l1="onebrain"] .ui2-row{display:block;padding:4px 0}'
    '.ui2-m-onebrain[data-ui2-l1="onebrain"] .ui2-row__label{opacity:.8;font-size:.85rem}'
    '.ui2-m-onebrain[data-ui2-l1="onebrain"] .ui2-row__body{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px}'
    # 手機（DOM＝建議持股水位 → OneBrain）：把 OneBrain 槽視覺上提到本體最前面，讓選擇器與槽緊鄰（DOM 順序不變；槽內無可聚焦元件）。
    # 桌機用 grid-area 排版，不受影響。
    '@media (max-width:768px){.ui2-h-body>.ui2-h-ob{order:-1}}'
    '[data-ui2-s3l0-status]{font-size:.85rem;opacity:.85;margin:0}</style>'
)


def _draw_selector() -> None:
    import streamlit as st
    topic = current_topic(st.session_state)
    st.session_state[TOPIC_KEY] = topic               # 建立 widget 之前寫入（不傳 default，避免與 session_state 雙重指定）
    st.session_state[LAST_TOPIC_KEY] = topic
    with st.container(key=BOX_KEY):
        # 為何用 segmented_control 而不是 st.radio：Streamlit 1.56 的 radio 每個 input 的 name 都是空字串，
        # Chromium 把整份文件所有「name 為空」的 radio 當成同一組 ⇒ 在選擇器最後一項按 → 會跳到頁面導覽（同樣是 name="" 的 radio）
        # 並直接切換頁籤（1.59.2 無此問題）。segmented_control 是按鈕組，不與導覽 radio 共組。見測試檔的 1.56 調查註解。
        st.segmented_control(SELECTOR_LABEL, TOPICS, selection_mode="single", key=TOPIC_KEY)
        # 補償（不是真正的 ARIA 選取狀態）：Streamlit 1.56 的 segmented_control 是一組沒有 role／aria-checked／aria-pressed 的 <button>，
        # 輔助科技讀不到目前選了哪個（1.59.2 有 role=radio＋checked）。這裡以一行**文字**（`role="status"` 的 live region；純 HTML、零 JS）
        # 傳達目前主題，兩版的 AX tree 都讀得到；控制項本身在 1.56 仍沒有 aria 選取（已知限制，測試明確記錄）。
        st.markdown(SLOT_CSS + f'<div role="status" data-ui2-s3l0-status="1">{escape(status_text(topic))}</div>',
                    unsafe_allow_html=True)


def _make_hold_wrapper(orig_hold):
    def hold_view(vm, *args, **kwargs):
        shell = _shell()
        state = get_state(shell)
        with state["lock"]:
            state["calls"] += 1
        try:
            planned = _plan(vm)
        except Exception as e:  # noqa: BLE001 — fail-closed：夾具／VM 出錯 ⇒ 原槽、無選擇器；只記例外型別
            _log.warning("onebrain s3 l0 fixture failed (%s); falling back to the original slot", type(e).__name__)
            with state["lock"]:
                state["fallbacks"] += 1
            planned = None
        if planned is None:
            return orig_hold(vm, *args, **kwargs)
        with state["lock"]:
            state["injected"] += 1
        _TL.after_first = _draw_selector
        try:
            return orig_hold(planned, *args, **kwargs)
        finally:
            _TL.after_first = None
    return hold_view


def _make_md_dispatch(orig_md):
    def md(html):
        orig_md(html)
        fn = getattr(_TL, "after_first", None)
        if fn is not None:
            _TL.after_first = None
            try:
                fn()
            except Exception as e:  # noqa: BLE001 — 選擇器畫不出來不得拖垮頁面
                _log.warning("onebrain s3 l0 selector failed (%s)", type(e).__name__)
    return md


def install() -> None:
    """安裝（冪等）。換 `shell.VIEWS`（含新的 💼 wrapper）與 `hold._md`；⛔ 不動 src 檔案。"""
    shell = _shell()
    hold = importlib.import_module(HOLD_MODULE)
    state = get_state(shell)
    with state["lock"]:
        if getattr(shell, ORIG_VIEWS_ATTR, None) is not None:
            return
        setattr(shell, ORIG_VIEWS_ATTR, shell.VIEWS)
        setattr(hold, ORIG_MD_ATTR, hold._md)
        views = dict(shell.VIEWS)
        views[P4_HOLD] = _make_hold_wrapper(shell.VIEWS[P4_HOLD])
        shell.VIEWS = views
        hold._md = _make_md_dispatch(hold._md)
        state["installs"] += 1


def uninstall() -> None:
    shell = _shell()
    hold = importlib.import_module(HOLD_MODULE)
    state = get_state(shell)
    with state["lock"]:
        orig = getattr(shell, ORIG_VIEWS_ATTR, None)
        if orig is None:
            return
        shell.VIEWS = orig
        delattr(shell, ORIG_VIEWS_ATTR)
        hold._md = getattr(hold, ORIG_MD_ATTR)
        delattr(hold, ORIG_MD_ATTR)
    if hasattr(shell, STATE_ATTR):
        delattr(shell, STATE_ATTR)


# ══════════════════════════════════════════════════════════════════════
# 封網（零非本機連線；server 進程用）
# ══════════════════════════════════════════════════════════════════════
_LOOPBACK_NAMES = frozenset({"localhost", "localhost.localdomain", ""})


def _is_loopback_host(host) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "ignore")
    h = str(host).strip().strip("[]").lower()
    if h in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(h.split("%")[0]).is_loopback
    except ValueError:
        return False


class NetworkSealed(OSError):
    pass


SEAL_MARKER_KIND = "sealed"                       # seal log 第一行的啟動標記（其餘行＝被拒絕的連線）


def _append_log(st: dict, record: dict) -> None:
    if st.get("log_path"):
        try:
            with open(st["log_path"], "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass


def seal_network(log_path: str | None = None) -> dict:
    """拒絕非 loopback 的 `connect`／`connect_ex`／`getaddrinfo`／`create_connection` 並計數（冪等）。回傳狀態 dict。
    `log_path`：每次拒絕追加一行 JSON（供啟動端讀回）。⛔ 不影響 loopback（server 本身與瀏覽器都走 loopback）。"""
    st = getattr(socket, SEAL_ATTR, None)
    if st is not None:
        return st
    st = {"denied": [], "orig": {}, "log_path": log_path}
    setattr(socket, SEAL_ATTR, st)
    _append_log(st, {"kind": SEAL_MARKER_KIND, "pid": os.getpid()})       # 啟動標記：讓「封網真的啟動」可被驗證

    def deny(kind, target):
        st["denied"].append({"kind": kind, "target": str(target)[:200]})
        _append_log(st, st["denied"][-1])
        raise NetworkSealed(f"network sealed: {kind}")

    def addr_host(address):
        if isinstance(address, (tuple, list)) and address:
            return address[0]
        return address if isinstance(address, (str, bytes)) else None

    orig_connect, orig_connect_ex = socket.socket.connect, socket.socket.connect_ex
    orig_gai, orig_cc = socket.getaddrinfo, socket.create_connection
    st["orig"] = {"connect": orig_connect, "connect_ex": orig_connect_ex, "getaddrinfo": orig_gai,
                  "create_connection": orig_cc}

    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _is_loopback_host(addr_host(address)):
            deny("connect", address)
        return orig_connect(self, address)

    def connect_ex(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _is_loopback_host(addr_host(address)):
            deny("connect_ex", address)
        return orig_connect_ex(self, address)

    def getaddrinfo(host, *a, **k):
        if not _is_loopback_host(host):
            deny("getaddrinfo", host)
        return orig_gai(host, *a, **k)

    def create_connection(address, *a, **k):
        if not _is_loopback_host(addr_host(address)):
            deny("create_connection", address)
        return orig_cc(address, *a, **k)

    socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
    socket.getaddrinfo, socket.create_connection = getaddrinfo, create_connection
    return st


def unseal_network() -> None:
    st = getattr(socket, SEAL_ATTR, None)
    if st is None:
        return
    o = st["orig"]
    socket.socket.connect, socket.socket.connect_ex = o["connect"], o["connect_ex"]
    socket.getaddrinfo, socket.create_connection = o["getaddrinfo"], o["create_connection"]
    delattr(socket, SEAL_ATTR)


# ══════════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════════
def _truthy_default_on(v) -> bool:
    return not (isinstance(v, str) and v.strip().lower() in ("0", "false", "off"))


def seed_session() -> None:
    """獨立示範入口預設落在「💼 持股／FAKE／cold」。只在該 session 尚無對應 key 時播種（不覆蓋使用者／開發面已選的值）。"""
    import streamlit as st
    for k, v in (("ui2_feed", FEED_FAKE), ("ui2_page", P4_HOLD), ("ui2_scenario", SCENARIO_COLD)):
        if k not in st.session_state:
            st.session_state[k] = v


def main() -> None:
    seal_network(os.environ.get(ENV_SEAL_LOG))        # 一律封網（log 路徑可選）；⛔ 不連任何非 loopback 位址
    install()
    if _truthy_default_on(os.environ.get(ENV_SEED)):
        seed_session()
    runpy.run_path((_ROOT / "app_ui2.py").as_posix(), run_name="__main__")


if __name__ == "__main__":
    main()
