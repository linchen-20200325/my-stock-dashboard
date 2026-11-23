"""OneBrain 持股 FAKE 離線示範 → New UI2 `onebrain` L1 區塊（SectionVM）的 mapper（C-OB-HOLD-DEMO-STAGE2-A1；**tests-only**）。

把 #1265 的 `tests.onebrain_holdings_ui2_demo.DemoBlock`（純文字、分區）轉成**單一** `SectionVM`
（`section_id="onebrain"`、`level="L1"`），供 `tests/ui2_viewport/onebrain_hold_demo_launcher.py` 在 `?ui2_dev=1` 的
FAKE／cold／💼 持股頁**取代**預設的「🤖 OneBrain 持股摘要：⬜ 尚未提供」槽。

⛔ 0 production caller：src／shared／app*／scripts 不得 import 本檔（`test_no_production_file_imports_mapper_or_launcher` 鎖定）。
⛔ 不改 `src/ui2`、`shared/ui2_contract`、`app_ui2.py`。不新增第 8 個 label（白名單＝總管 Q3-5）。
本檔只 import `shared.ui2_contract.*` 與 #1265 的 demo；零網路、零時鐘、零 Secrets。

═══ 列規格（總管 #1199 裁示 D／Q3；列順序固定）═══════════════════════════════════
1 示意（恆有，首列）       ：D 型；文字＝`DISCLOSURE_FIRST`（與 `demo.DISCLOSURE_LINES[0]` 不一致 ⇒ raise）
2 持股判讀（derived 區非空）：J 型；狀態 `⬜ 無法判定`；註腳「此列由畫面依持股狀態推導，非系統摘要原句」
3 存股／資本利得（正常案例）：D 型；Digest 原句**逐字**、依原順序；多句重複 label
5 說明（任一顯示句含「（尚無輸入）」）：D 型；D3 核定註記逐字
6 來源（恆有）／7 時點（恆有）：D 型；時點**不用** `TEXT_ASOF_MISSING`
fail-closed（`block.fail_closed`）：示意／持股判讀′（註腳「此列為固定顯示，非系統摘要原句」）／說明′／來源／時點（5 列）。
**不**消費 `AREA_FOOTER`、`AREA_TEST_INPUT`、第二條 disclosure；不輸出 `FOOTER_DISPLAY`、「示範鏈」、§C 代碼、
「與本頁其他 FAKE 數字無關」。fail-closed 以 `block.fail_closed` 判定（不看 footer 結構）。

⚠️ **DOM `data-state="ok"` ≠ 持股／投資狀態正常**（Q4）：D 列借用 `FieldState.OK` 只當「文字載體」，
所以「⬜ 存股：持股資料不足…」、來源、時點在 DOM 上全是 `data-state="ok"`，彼此無法由屬性區分；
任何測試／判定器**不得**以 `data-state="ok"` 推導持股或安全（`OK_STATE_IS_TEXT_CARRIER_ONLY`）。
"""
from __future__ import annotations

from shared.ui2_contract.models import FieldState, FieldVM, JudgementState, SectionVM
from shared.ui2_contract.text import TEXT_RISK_CAP_UNDETERMINABLE
from tests import onebrain_holdings_ui2_demo as demo

#: 讀碼用的明示常數（Q4）：本 mapper 的 D 列 `data-state="ok"` 只代表「此列有文字」，不代表持股／投資狀態正常。
OK_STATE_IS_TEXT_CARRIER_ONLY = True

SECTION_ID = "onebrain"
SECTION_LEVEL = "L1"
SECTION_TITLE = "🤖 OneBrain 持股摘要"

# label 白名單（總管 Q3-5）
LABEL_DEMO = "示意"
LABEL_JUDGEMENT = "持股判讀"
LABEL_BUY_AND_HOLD = "存股"
LABEL_CAPITAL_GAIN = "資本利得"
LABEL_NOTE = "說明"
LABEL_SOURCE = "來源"
LABEL_ASOF = "時點"
LABEL_WHITELIST = (LABEL_DEMO, LABEL_JUDGEMENT, LABEL_BUY_AND_HOLD, LABEL_CAPITAL_GAIN, LABEL_NOTE, LABEL_SOURCE,
                   LABEL_ASOF)
SECTION_TO_LABEL = {"buy_and_hold": LABEL_BUY_AND_HOLD, "capital_gain": LABEL_CAPITAL_GAIN}

# 本 mapper 自有的逐字文案（與 demo 的 DISCLOSURE_LINES[0] 以測試＋執行期檢查綁定）
DISCLOSURE_FIRST = "示意：合成持股快照（FAKE）；非真實持股；非即時 OneBrain；非投資建議"
DERIVED_FOOTNOTE = "此列由畫面依持股狀態推導，非系統摘要原句"
FAILCLOSED_FOOTNOTE = "此列為固定顯示，非系統摘要原句"
FAILCLOSED_NOTE = "示意內容未能產生，未顯示任何摘要句"
SOURCE_VALUE = "FAKE 合成持股快照（非真實持股）"
ASOF_VALUE = "無（FAKE 示意，沒有持股讀取時點）"
#: D3 核定註記（逐字；只在顯示句含 NOTE_TRIGGER 時出現）
NOTE_TRIGGER = "（尚無輸入）"
NOTE_D3 = "註：『尚無輸入』是現行摘要措辭，也可能代表讀取失敗、輸入異常或缺少組合鍵；請勿解讀為零持股。"
#: 槽外「測試輸入說明」前綴（總管裁示 Q3-8 要求保留開頭「測試輸入說明（非系統輸出」）：明示這句描述的是**本示範的合成測試輸入**，
#: 不是系統摘要、也不是持股清單內容（避免被誤讀成「持股清單有 N 列」）。
TEST_INFO_PREFIX = "測試輸入說明（非系統輸出；為本示範的合成測試輸入，非持股清單內容）："
#: 槽外說明的本文白名單（**不**取用 `demo.CASES[cid].test_input`：那些字串含「2 列」，會與槽內顯示列、持股清單的列數撞詞）。
#: 每句必須與 `demo.CASES[cid]` 的實際合成快照一致；一致性由 `tests/test_onebrain_holdings_ui2_demo_view.py` 對照 snapshot／keyed 事實鎖定。
#: 用語：只用「筆」與代號，不寫裸「N 列」；不寫「持股清單」。
TEST_INFO_BODY = {
    "R1": "合成讀取結局：網路例外（不含持股內容）",
    "R2": "合成讀取結局：未選定投資組合（不含持股內容）",
    "R3": "合成測試持股 FAKE-T1、FAKE-T2 可讀；另有 1 筆資料為非數字",
    "L1": "合成測試持股 FAKE-T1、FAKE-T2，均無組合鍵（不在本頁顯示）",
    "L2": "合成測試持股 FAKE-T1、FAKE-T2，僅 FAKE-T1 有組合鍵（不在本頁顯示）",
    "L3": "合成測試持股 FAKE-T1、FAKE-T2，均有組合鍵（不在本頁顯示）",
}

#: 任何狀態都**不得**出現在 UI 槽的字樣（總管 Q3-1／Q3-2／Q3-8）。
UI_SLOT_FORBIDDEN = (
    "顯示＝規則式摘要",            # FOOTER_DISPLAY 整句的前半（任一狀態都不顯示）
    "FakeProvider",               # 含「FakeProvider 草稿不採用」
    "草稿",
    "§C",                         # 工程代碼（§C-2／§C-10）
    "示範鏈",
    "與本頁其他 FAKE 數字無關",   # 第二條 disclosure：cold 畫面不顯示（Q3-1）
    "is_complete",
)


class MapperError(RuntimeError):
    """mapper 輸入不符預期（用 raise，不用 assert）。launcher 讓它往上傳（fail loud，不靜默顯示壞畫面）。"""


def _d(label: str, text: str) -> FieldVM:
    return FieldVM(label, FieldState.OK, value_text=text)


def _judgement(footnote: str) -> FieldVM:
    return FieldVM(LABEL_JUDGEMENT, JudgementState.UNDETERMINABLE,
                   status_text=TEXT_RISK_CAP_UNDETERMINABLE, detail=footnote)


def _check_bound_constants() -> None:
    if demo.DISCLOSURE_LINES[0] != DISCLOSURE_FIRST:
        raise MapperError("示意首列文案與 demo.DISCLOSURE_LINES[0] 不一致（漂移）")
    if demo.HOLDINGS_UNDETERMINABLE != TEXT_RISK_CAP_UNDETERMINABLE:
        raise MapperError("持股判讀狀態字樣與 TEXT_RISK_CAP_UNDETERMINABLE 不一致（漂移）")


def build_fields(block: "demo.DemoBlock") -> tuple:
    """DemoBlock → 逐列 FieldVM（順序即畫面順序）。"""
    _check_bound_constants()
    rows = [_d(LABEL_DEMO, DISCLOSURE_FIRST)]
    if block.fail_closed is True:
        rows.append(_judgement(FAILCLOSED_FOOTNOTE))
        rows.append(_d(LABEL_NOTE, FAILCLOSED_NOTE))
    elif block.fail_closed is False:
        sentences = [ln for ln in block.lines if ln.area == demo.AREA_SYSTEM]
        if not sentences:
            raise MapperError("正常案例沒有 Digest 原句（不得猜句；應由 demo fail-closed）")
        if block.area(demo.AREA_DERIVED):
            if demo.HOLDINGS_UNDETERMINABLE not in block.area(demo.AREA_DERIVED)[0]:
                raise MapperError("derived 區文字不含無法判定字樣")
            rows.append(_judgement(DERIVED_FOOTNOTE))
        for ln in sentences:
            label = SECTION_TO_LABEL.get(ln.section)
            if label is None or type(ln.text) is not str or not ln.text:
                raise MapperError("Digest 原句的段鍵／型別不符")
            rows.append(_d(label, ln.text))               # 逐字：不 strip、不改寫、不重排
        if any(NOTE_TRIGGER in ln.text for ln in sentences):
            rows.append(_d(LABEL_NOTE, NOTE_D3))
    else:
        raise MapperError("block.fail_closed 必須是 bool（未知狀態不得當正常）")
    rows.append(_d(LABEL_SOURCE, SOURCE_VALUE))
    rows.append(_d(LABEL_ASOF, ASOF_VALUE))
    _guard_rows(rows)
    return tuple(rows)


def _guard_rows(rows) -> None:
    for f in rows:
        if f.label not in LABEL_WHITELIST:
            raise MapperError(f"label 不在白名單：{f.label}")
        text = "\n".join(x for x in (f.value_text, f.status_text, f.detail) if x)
        hit = [w for w in UI_SLOT_FORBIDDEN if w in text]
        if hit:
            raise MapperError(f"UI 槽不得出現 {hit}")


def build_section(block: "demo.DemoBlock") -> SectionVM:
    """DemoBlock → 單一 `onebrain` L1 SectionVM（與預設槽同 section_id／level／title）。"""
    return SectionVM(section_id=SECTION_ID, title=SECTION_TITLE, level=SECTION_LEVEL, fields=build_fields(block))


def test_info_text(case_id: str) -> str:
    """槽外「測試輸入說明」整句（launcher 以 `st.caption` 畫在槽外；不屬 SectionVM、不是系統輸出）。
    未知 case id ⇒ KeyError（呼叫端錯誤，照常往上拋）。"""
    return TEST_INFO_PREFIX + TEST_INFO_BODY[case_id]
