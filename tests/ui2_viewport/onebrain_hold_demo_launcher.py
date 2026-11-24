"""OneBrain 持股 FAKE 示範的專用 streamlit 入口（C-OB-HOLD-DEMO-STAGE2-A1；**tests-only**；⛔ 不是產品入口）。

    UI2_OBDEMO_CASE=R1 streamlit run tests/ui2_viewport/onebrain_hold_demo_launcher.py -- （再以 `?ui2_dev=1` 開頁）

在**不改 `src/ui2`、`app_ui2.py`** 的前提下，把真 `app_ui2.py`（`runpy`）跑起來，並只換一個函式：
`src.ui2.shell.app.get_preview_page_vm`（shell 以 `from … import` 把它放進自己的命名空間，所以只能換 shell 這一份）。
wrapper 只在下列條件**全部**成立時，把預設的「🤖 OneBrain 持股摘要：⬜ 尚未提供」槽換成示範槽：
  ① 頁＝💼 持股（`P4_HOLD`）② 場景＝`cold` ③ 走 FAKE（Real 走 `get_real_page_vm`，不經 wrapper）④ env `UI2_OBDEMO_CASE` ∈ {R1,R2,R3,L1,L2,L3}。
其餘一律原樣轉發（`*args, **kwargs`，含 `mode=`／`account=`／`top_n=`）。

環境變數（皆由啟動端設定；launcher 不讀 Secrets、不連網）：
  UI2_OBDEMO_CASE          必填才注入；未知值 ⇒ ValueError（不靜默）
  UI2_OBDEMO_FAILCLOSED=1  在 launcher 內讓 `ASM.assemble_digest` 暫時 raise（之後還原）⇒ 示範鏈 fail-closed；src 不動
  UI2_OBDEMO_PREVIEW_CSS=1 補充比較用的預覽 CSS（⛔ 非現況、非 baseline、非 DEC-137；Q10）
  UI2_OBDEMO_SEAL=1        在 server 進程封網（拒絕非 loopback 的 `connect`／`getaddrinfo` 並計數）
  UI2_OBDEMO_SEAL_LOG=path 封網拒絕紀錄（JSON lines；由證據 runner 讀回寫進 meta）
  UI2_OBDEMO_TOPICS=0      退回 #1268 原本的「單一持股摘要槽」（無四主題選擇器；原 15/15 證據與舊測試的來源）；未設或其他值＝四主題（預設）

四主題（大盤／產業前瞻／持股健檢／反方風險；`tests/onebrain_holdings_ui2_demo_topics.py`）：槽外一個「🧪 FAKE 預覽控制」群組（`st.radio`，
key＝`ui2_obdemo_topic`）供點選；wrapper 在每次 rerun 依 `st.session_state` 的選擇換槽內容（位置不變、仍注入現行 `onebrain` 槽）。選擇器只在
「本次 run 確實注入」時才畫（Real／非持股頁／非 cold 都沒有）。⛔ 零正式 LLM／Provider／網路；⛔ 不連真資料、不寫快取。

wrapper 的哨兵與計數放在 **shell 模組**（不是 launcher 全域）：AppTest／streamlit 每次 rerun 都會重新執行本檔，
launcher 全域在 pytest 側讀不到，也不會跨 rerun 保留。⛔ 不做 `os.chdir`（`degraded_launcher` 會 chdir，在 AppTest 同進程會洩漏 cwd；
本檔以 `Path(__file__)` 定位 repo 根，從 repo 根啟動即可）。
`install()`／`uninstall()` 供測試 fixture 以 try/finally 保證還原（函式、哨兵、`shell.CSS`、封網）。
"""
from __future__ import annotations

import dataclasses
import functools
import importlib
import ipaddress
import json
import logging
import os
import runpy
import socket
import sys
import threading
from pathlib import Path

try:
    _ROOT = Path(__file__).resolve().parents[2]
except NameError:                                  # 例如被某些 runner 以 exec 載入且無 __file__
    _ROOT = Path(os.getcwd())
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.ui2_contract.pages import P4_HOLD, SCENARIO_COLD  # noqa: E402
from tests import onebrain_holdings_ui2_demo as demo  # noqa: E402
from tests import onebrain_holdings_ui2_demo_topics as T  # noqa: E402
from tests import onebrain_holdings_ui2_demo_vm as VM  # noqa: E402

_log = logging.getLogger(__name__)

ENV_CASE = "UI2_OBDEMO_CASE"
ENV_FAILCLOSED = "UI2_OBDEMO_FAILCLOSED"
ENV_PREVIEW_CSS = "UI2_OBDEMO_PREVIEW_CSS"
ENV_SEAL = "UI2_OBDEMO_SEAL"
ENV_SEAL_LOG = "UI2_OBDEMO_SEAL_LOG"
ENV_TOPICS = "UI2_OBDEMO_TOPICS"

SHELL_MODULE = "src.ui2.shell.app"
ORIG_ATTR = "_obdemo_orig_get_preview_page_vm"      # 原函式（哨兵；存在＝已安裝）
CSS_ATTR = "_obdemo_orig_css"                       # 原 CSS（哨兵）
STATE_ATTR = "_obdemo_state"                        # 計數與當次 run 狀態
SEAL_ATTR = "_obdemo_seal_state"                    # 掛在 socket 模組上的封網狀態
TESTINFO_KEY = "ui2_obdemo_testinfo"                # 槽外測試資訊容器 key（⛔ 不是 session_state）
CTRL_KEY = "ui2_obdemo_ctrl"                        # 「🧪 FAKE 預覽控制」群組容器 key（選擇器＋測試輸入說明；⛔ 不是 session_state）
DEFAULT_TOPIC = T.DEFAULT_TOPIC
CTRL_TITLE = "🧪 FAKE 預覽控制（測試用；非產品內容、非持股清單）"
#: 控制群組自己的樣式（只作用在 `.st-key-ui2_obdemo_ctrl`；虛線框＋貼底，切主題時不必捲到頁尾）。⛔ 不動 shell.CSS、不動槽的樣式。
CTRL_CSS = (
    # Streamlit ≥1.5x 會把 `st.container(key=…)` 包在 `stLayoutWrapper` 裡：sticky 必須設在外層 wrapper（內層的包含區塊只有它自己那麼高）；
    # 舊版沒有 wrapper 時，直接設在 `.st-key-…` 本身即可。兩條都設、互不衝突（`:has(> …)` 只選到「直接包著它」的 wrapper，不會選到主區塊）。
    "<style>.st-key-ui2_obdemo_ctrl,[data-testid=\"stLayoutWrapper\"]:has(>.st-key-ui2_obdemo_ctrl){position:sticky;bottom:0;z-index:99990}"
    ".st-key-ui2_obdemo_ctrl{margin:16px 0 0 0;padding:6px 12px 8px 12px;gap:.15rem;"
    "border:2px dashed currentColor;border-radius:8px;background:var(--ui2-nav-bg,#161b22);color:var(--ui2-nav-fg,#e6edf3)}"
    ".st-key-ui2_obdemo_ctrl [data-testid=\"stMarkdownContainer\"]{margin:0}"
    ".st-key-ui2_obdemo_ctrl [data-testid=\"stCaptionContainer\"]{font-size:.72rem;line-height:1.3}"
    ".st-key-ui2_obdemo_ctrl [role=\"radiogroup\"]{gap:.1rem .9rem}"
    ".ui2-obdemo-head{font-weight:700;font-size:.82rem;line-height:1.25;margin:0}</style>"
)

#: PREVIEW-ONLY（Q10）：⛔ 非現況、非 baseline、非 DEC-137 正式；只作補充比較。主證據一律是未改 CSS 的現況。
PREVIEW_CSS = (
    "\n/* PREVIEW-ONLY：非現況、非 baseline、非 DEC-137；僅補充比較（Q10） */\n"
    "@media (min-width:769px){.ui2-m-onebrain{display:block}.ui2-m-onebrain .ui2-row{padding:2px 0 4px 0}}\n"
)

def with_preview_css(css: str) -> str:
    """把 PREVIEW_CSS 插進 `shell.CSS` 最後一個 `</style>` **之前**（附加在其後會被當成可見文字渲染，整頁下移）；找不到 ⇒ raise。"""
    i = css.rfind("</style>")
    if i < 0:
        raise RuntimeError("shell.CSS 沒有 </style>：無法插入預覽 CSS")
    return css[:i] + PREVIEW_CSS + css[i:]


_LOOPBACK_NAMES = frozenset({"localhost", "localhost.localdomain"})


class InjectionPointMissing(RuntimeError):
    """預設 VM 沒有恰好一個 `onebrain` L1 區塊 ⇒ 不得靜默成功（總管 Q6）。"""


def _truthy(v) -> bool:
    return isinstance(v, str) and v.strip().lower() in ("1", "true")


def _shell():
    return importlib.import_module(SHELL_MODULE)


def get_state(shell=None) -> dict:
    """shell 模組上的計數／當次 run 狀態（不存在則建立）。"""
    shell = shell or _shell()
    st = getattr(shell, STATE_ATTR, None)
    if st is None:
        st = {"installs": 0, "calls": 0, "injected": False, "case": None, "failclosed": False, "topic": None,
              "lock": threading.Lock()}
        setattr(shell, STATE_ATTR, st)
    return st


def selected_case() -> str | None:
    raw = os.environ.get(ENV_CASE)
    if not raw:
        return None
    if raw not in demo.CASES:
        raise ValueError(f"{ENV_CASE}={raw!r} 不是已知案例 {tuple(demo.CASES)}")
    return raw


def topics_enabled() -> bool:
    """四主題為預設；`UI2_OBDEMO_TOPICS=0／false／off` ⇒ 退回 #1268 原本的單一槽。"""
    v = os.environ.get(ENV_TOPICS)
    return not (isinstance(v, str) and v.strip().lower() in ("0", "false", "off"))


def selected_topic(session_state=None) -> str:
    """目前選的主題（`st.session_state[ui2_obdemo_topic]`；沒選 ⇒ 預設）。未知值 ⇒ ValueError（不靜默改成預設）。"""
    if session_state is None:
        import streamlit as st
        session_state = st.session_state
    v = session_state.get(T.KEY_TOPIC)
    if v is None:
        return DEFAULT_TOPIC
    if v not in T.TOPICS:
        raise ValueError(f"{T.KEY_TOPIC}={v!r} 不是已知主題 {T.TOPICS}")
    return v


def inject_section(vm, section):
    """以 `dataclasses.replace` 換掉 VM 內**恰好一個** `onebrain` L1 區塊；否則 raise（不靜默）。"""
    idx = [i for i, s in enumerate(vm.context.sections) if s.section_id == VM.SECTION_ID and s.level == VM.SECTION_LEVEL]
    if len(idx) != 1:
        raise InjectionPointMissing(f"預設 VM 需恰好 1 個 onebrain L1 區塊，實得 {len(idx)}")
    sections = list(vm.context.sections)
    sections[idx[0]] = section
    return dataclasses.replace(vm, context=dataclasses.replace(vm.context, sections=tuple(sections)))


def _raise_assemble(*_a, **_k):
    raise RuntimeError("obdemo: 注入 assemble_digest 例外（launcher 內；fail-closed 示範）")


def _failclosed_fallback_section(case_id: str, err: BaseException):
    """mapper（vm_build）在正常區塊上失敗 ⇒ 改以空的 fail-closed 區塊建固定 5 列（不猜句）；此處再失敗＝漂移，往上拋（fail loud）。
    降級**必須留 log**（CLAUDE.md §1：不得靜默）；只記案例與例外**型別名**，⛔ 不記訊息／值（沿用 demo `_failclosed_block` 的格式）。"""
    _log.warning("onebrain holdings demo %s vm_build fail-closed: %s", case_id, type(err).__name__)
    return VM.build_section(demo.DemoBlock(case_id, (), True, type(err).__name__))


def build_demo_section(case_id: str, failclosed: bool, shell=None):
    """案例 → (示範 SectionVM, 是否為 fail-closed)。fail-closed：只在 launcher 內讓 `ASM.assemble_digest` 暫時 raise（持鎖、finally 還原）。
    mapper 對**正常**區塊失敗（vm_build）⇒ fail-closed 固定列；對 fail-closed 區塊失敗（含文案漂移）⇒ 照常往上拋。"""
    if failclosed:
        asm = demo.ASM
        with get_state(shell)["lock"]:
            real = asm.assemble_digest
            asm.assemble_digest = _raise_assemble
            try:
                block = demo.build_case_block(case_id)
            finally:
                asm.assemble_digest = real
        if block.fail_closed is not True:
            raise RuntimeError("fail-closed 注入未生效（示範鏈沒有 fail-closed）")
    else:
        block = demo.build_case_block(case_id)
    if block.fail_closed:
        return VM.build_section(block), True
    try:
        return VM.build_section(block), False
    except Exception as e:  # noqa: BLE001 — vm_build 失敗只降級成固定 fail-closed 列
        return _failclosed_fallback_section(case_id, e), True


def build_demo_topic_section(case_id: str, topic: str, failclosed: bool, shell=None):
    """（案例, 主題）→ (該主題的示範 SectionVM, 是否 fail-closed)。fail-closed 判定與舊槽一致：只在 launcher 內讓 `ASM.assemble_digest`
    暫時 raise（持鎖、finally 還原）後以 `demo.build_case_block` 判定；內容由 `T.build_topic_section` 依該結果誠實降級。"""
    if failclosed:
        asm = demo.ASM
        with get_state(shell)["lock"]:
            real = asm.assemble_digest
            asm.assemble_digest = _raise_assemble
            try:
                block = demo.build_case_block(case_id)
            finally:
                asm.assemble_digest = real
        if block.fail_closed is not True:
            raise RuntimeError("fail-closed 注入未生效（示範鏈沒有 fail-closed）")
    else:
        block = demo.build_case_block(case_id)
    fc = block.fail_closed is True
    return T.build_topic_section(topic, case_id, fail_closed=fc), fc


def testinfo_wanted(state: dict) -> bool:
    """槽外測試資訊只在「本次 run 確實注入、且非 fail-closed」才畫（與 #1265 一致）。"""
    return bool(state.get("injected")) and not state.get("failclosed")


def _make_wrapper(orig, shell):
    @functools.wraps(orig)
    def _obdemo_get_preview_page_vm(page_id, scenario_id, *args, **kwargs):
        st = get_state(shell)
        st["calls"] += 1
        vm = orig(page_id, scenario_id, *args, **kwargs)       # 先原樣轉發（mode／account／top_n 照傳）
        case_id = selected_case()
        if page_id == P4_HOLD and scenario_id == SCENARIO_COLD and case_id is not None:
            failclosed = _truthy(os.environ.get(ENV_FAILCLOSED))
            if topics_enabled():
                topic = selected_topic()
                section, fc = build_demo_topic_section(case_id, topic, failclosed, shell)
                st.update(topic=topic)
            else:
                section, fc = build_demo_section(case_id, failclosed, shell)
                st.update(topic=None)
            vm = inject_section(vm, section)
            st.update(injected=True, case=case_id, failclosed=fc)
        return vm
    _obdemo_get_preview_page_vm.__obdemo_wrapper__ = True
    return _obdemo_get_preview_page_vm


def install() -> None:
    """包一次：原函式存在 shell 哨兵屬性；之後每次呼叫都從哨兵重包（不巢狀）。`PREVIEW_CSS` 同理（只在 env 開時追加）。"""
    shell = _shell()
    st = get_state(shell)
    orig = getattr(shell, ORIG_ATTR, None)
    if orig is None:
        orig = shell.get_preview_page_vm
        setattr(shell, ORIG_ATTR, orig)
    shell.get_preview_page_vm = _make_wrapper(orig, shell)
    css0 = getattr(shell, CSS_ATTR, None)
    if _truthy(os.environ.get(ENV_PREVIEW_CSS)):
        if css0 is None:
            css0 = shell.CSS
            setattr(shell, CSS_ATTR, css0)
        shell.CSS = with_preview_css(css0)
    elif css0 is not None:
        shell.CSS = css0
    st["installs"] += 1


def uninstall() -> None:
    """還原函式、刪哨兵、還原 `shell.CSS`、解除封網。可重複呼叫。"""
    shell = _shell()
    orig = getattr(shell, ORIG_ATTR, None)
    if orig is not None:
        shell.get_preview_page_vm = orig
        delattr(shell, ORIG_ATTR)
    css0 = getattr(shell, CSS_ATTR, None)
    if css0 is not None:
        shell.CSS = css0
        delattr(shell, CSS_ATTR)
    if hasattr(shell, STATE_ATTR):
        delattr(shell, STATE_ATTR)
    unseal_network()


# ── 封網（server 進程；只在 UI2_OBDEMO_SEAL=1 時由 main() 啟用）─────────────────────
def _is_loopback_host(host) -> bool:
    if host is None or host == "":
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not isinstance(host, str):
        return False
    if host.lower() in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def _record_reject(kind: str, host) -> None:
    st = getattr(socket, SEAL_ATTR, None)
    if st is None:
        return
    st["rejected"] += 1
    path = st.get("log")
    if path:
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"kind": kind, "host": str(host)}, ensure_ascii=False) + "\n")
        except OSError:
            pass


def seal_network(log_path: str | None = None) -> dict:
    """拒絕非 loopback 的 `socket.connect`／`connect_ex`／`create_connection`／`getaddrinfo` 並計數。冪等。
    ⚠️ 只擋本進程的 Python socket；不是作業系統層封網，也不代表 Streamlit Cloud 行為（NOT VERIFIED）。"""
    existing = getattr(socket, SEAL_ATTR, None)
    if existing is not None:
        return existing
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex
    real_cc, real_gai = socket.create_connection, socket.getaddrinfo
    state = {"rejected": 0, "log": log_path,
             "orig": (real_connect, real_connect_ex, real_cc, real_gai)}

    def _guard(kind, host):
        if not _is_loopback_host(host):
            _record_reject(kind, host)
            return True
        return False

    def connect(self, address):
        if isinstance(address, tuple) and address and _guard("connect", address[0]):
            raise ConnectionRefusedError("obdemo: 封網（非 loopback）")
        return real_connect(self, address)

    def connect_ex(self, address):
        if isinstance(address, tuple) and address and _guard("connect_ex", address[0]):
            return 111
        return real_connect_ex(self, address)

    def create_connection(address, *a, **k):
        if _guard("create_connection", address[0]):
            raise ConnectionRefusedError("obdemo: 封網（非 loopback）")
        return real_cc(address, *a, **k)

    def getaddrinfo(host, *a, **k):
        if _guard("getaddrinfo", host):
            raise socket.gaierror(-2, "obdemo: 封網（非 loopback）")
        return real_gai(host, *a, **k)

    socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
    socket.create_connection, socket.getaddrinfo = create_connection, getaddrinfo
    setattr(socket, SEAL_ATTR, state)
    return state


def unseal_network() -> None:
    state = getattr(socket, SEAL_ATTR, None)
    if state is None:
        return
    real_connect, real_connect_ex, real_cc, real_gai = state["orig"]
    socket.socket.connect, socket.socket.connect_ex = real_connect, real_connect_ex
    socket.create_connection, socket.getaddrinfo = real_cc, real_gai
    delattr(socket, SEAL_ATTR)


def seal_rejected_count() -> int:
    st = getattr(socket, SEAL_ATTR, None)
    return 0 if st is None else st["rejected"]


def render_controls(st, state: dict) -> None:
    """「🧪 FAKE 預覽控制」群組（槽外；⛔ 不在 `onebrain` 槽的 DOM 內）：四主題選擇器＋（非 fail-closed 時）槽外測試輸入說明。
    只在「本次 run 確實注入」時才畫 ⇒ Real／非持股頁／非 cold 沒有選擇器；離開持股頁後 Streamlit 會丟掉該 widget 狀態（回到預設主題）。"""
    with st.container(key=CTRL_KEY):
        st.markdown(CTRL_CSS + f'<div class="ui2-obdemo-head">{CTRL_TITLE}</div>', unsafe_allow_html=True)
        st.radio("OneBrain 主題（預覽）", T.TOPICS, index=T.TOPICS.index(DEFAULT_TOPIC), key=T.KEY_TOPIC, horizontal=True,
                 label_visibility="collapsed")
        if testinfo_wanted(state):
            with st.container(key=TESTINFO_KEY):
                st.caption(T.test_info_text(state["case"]))


def main() -> None:
    import streamlit as st

    install()
    if _truthy(os.environ.get(ENV_SEAL)):
        seal_network(os.environ.get(ENV_SEAL_LOG) or None)
    state = get_state()
    state.update(injected=False, case=None, failclosed=False, topic=None)        # 每次 rerun 重置當次 run 狀態
    runpy.run_path(str(_ROOT / "app_ui2.py"), run_name="__main__")
    if state.get("injected") and topics_enabled():
        render_controls(st, state)
    elif testinfo_wanted(state):
        # 槽外測試資訊（Q3-8；單一槽模式）：獨立容器；只在「本次 run 確實注入、且非 fail-closed」才畫；⛔ 不進 `onebrain` 槽的 DOM
        with st.container(key=TESTINFO_KEY):
            st.caption(VM.test_info_text(state["case"]))


if __name__ == "__main__":
    main()
