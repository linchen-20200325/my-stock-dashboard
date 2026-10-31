"""tests/test_p4_4_market_exposed_text.py — Phase 4 P4-4（📊 市場頁，內部小修批）：外露層句長守衛＋Primary 圖高現況釘死。

來源：`docs/vnext/phase4_market/p4_3/GATE_REPORT.md` A8（外露 >32 字且非客戶原句 3 塊）／發現項 F3（沒有任何測試釘句長與圖高）。
  A8 ── 外露層（不在 expander 內）的 Caption／Markdown 純文字（去 HTML 標籤、`**`、空白後）＞32 字者，必須是**白名單內的逐字客戶原句／
        契約句**（`_VERBATIM_PREFIXES`，每條附出處）；其餘一律 ≤32。被縮短的 3 塊（頁首資料日、AI／資料狀態行、圖 C 一行）另釘：
        外露短版＝原句的前半片段（不新造字），**原整句逐字在摺疊內**（資訊只下沉、不刪）。
  A6 ── ⛔ 本檔**不改**圖高：手機 Primary 圖高 220 vs 契約 ≤140 是**待客戶裁示**的題 2；這裡只把「現況＝220、桌機與手機同一個值」釘死，
        使任何人改圖高（往 140 或別的值）都必須先改本測試＝先過客戶裁示。
判讀一律用 AppTest **渲染後**的元素樹。
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

from src.services import market_twii_view_service as S
from src.ui.views import _market_blocks as B
from src.ui.views import page_market as PM
from src.ui.views import page_today as P
from src.ui_v2 import compact as cp
from tests.test_p4_1_market_first_screen import _events, _report
from tests.test_uim_market_page import _LOADED, _run, _view

_ROOT = pathlib.Path(__file__).resolve().parents[1]
A8_MAX_CHARS = 32          # Gate A8（客戶 DEC-109）：外露層一句 ≤32 字（Gate 量法：去空白後的字元數）

#: 外露層允許超過 32 字的**逐字**客戶原句／契約句（以「元素開頭」認；每條附出處）。⛔ 新增任何一條都必須有客戶／契約出處，
#: 不得為了讓測試過而把 AI 自寫句加進來。
_VERBATIM_PREFIXES: tuple[tuple[str, str], ...] = (
    ("市場位階：", "今日結論句：客戶原句（DEC-081 Q2-1，逐字、只改位置；測試 `test_conclusion_sentence…`）"),
    ("**⚡ 需要處理**", "⚡ 一行 bar：客戶 DEC-117 Q8c 核准的一行形式（由既有常數／`build_key_alert_tile` 字樣組成；"
                       "Gate A8 DOM 量測把它拆成多個 ≤32 字的 span，AppTest 層是整行一個元素）"),
)
#: 狀態列裡的契約片段（R8：更新時間 ≠ 資料日），逐字，計字時整段扣掉。
_VERBATIM_FRAGMENTS: tuple[str, ...] = (PM.REFRESH_TIME_NOTE,)
_STATUS_TIME_PREFIX = "本頁更新於"


@pytest.fixture(autouse=True)
def _fixed_twii_view(monkeypatch):
    monkeypatch.setattr(S, "get_twii_trend_view", lambda n: _view())


def _plain(t: str) -> str:
    """Gate 的字數口徑：去 HTML 標籤、粗體記號、全部空白（含全形空白）。"""
    return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", t).replace("**", ""))


_TEXT = ("Markdown", "Caption", "Info", "Success", "Text")      # Error／Warning＝真錯誤／系統事實，不是 AI 自寫提示句，不在 A8 守衛內


def _exposed_sentences(at) -> list[str]:
    """外露層（不在 expander 內）的純文字句：排除 `<style>`／HTML 元件（header、小倍數）與 markdown 表格。"""
    out = []
    for _k, _t, _e, _keys in _events(at.main):
        if _e is None and _k in _TEXT and not _t.lstrip().startswith(("<", "|")):
            out.append(_t)
    return out


def _all_text_in(at, label: str) -> list[str]:
    return [_t for _k, _t, _e, _ in _events(at.main) if _e == label and _k in _TEXT]


_STATES = {"cold": None, "loaded": _LOADED}


class TestA8ExposedSentenceLength:
    @pytest.mark.parametrize("state", ["cold", "loaded", "report"])
    def test_a8_every_exposed_sentence_is_le_32_or_a_listed_verbatim_sentence(self, tmp_path, state):
        _sess = {**_LOADED, P.SS_REFRESH_REPORT: _report()} if state == "report" else _STATES[state]
        _at = _run(tmp_path, _sess)
        assert not _at.exception, _at.exception
        _bad = []
        for _t in _exposed_sentences(_at):
            if _t.startswith(tuple(_p for _p, _ in _VERBATIM_PREFIXES)):
                continue
            _s = _t
            if _s.startswith(_STATUS_TIME_PREFIX):
                # 狀態列「更新時間」半句＝R8 契約格式（`page_market.status_line`，Phase 4 之前就有：時間戳＋`REFRESH_TIME_NOTE`；
                # 去掉契約片段後仍 ≥33 字，縮短＝改 R8 字樣，不在本批權限）⇒ 整半句視為契約句，只檢查「｜」之後的資料日半句。
                # ⚠️ 「狀態列算不算 metadata」由總管判定；本守衛兩種計法都不放過資料日半句。
                _s = _s.split("｜", 1)[1]
            for _frag in _VERBATIM_FRAGMENTS:
                _s = _s.replace(_frag, "")
            if len(_plain(_s)) > A8_MAX_CHARS:
                _bad.append((len(_plain(_s)), _t[:80]))
        assert not _bad, f"外露層有 >{A8_MAX_CHARS} 字且不在客戶原句白名單內的句子（A8）：{_bad}"

    def test_a8_whitelist_entries_have_a_source_and_really_exist_on_the_page(self, tmp_path):
        """白名單不是垃圾桶：每條都要有出處、而且頁上真的出現過（否則是死白名單，該刪）。"""
        _at = _run(tmp_path, _LOADED)
        _texts = _exposed_sentences(_at)
        for _prefix, _why in _VERBATIM_PREFIXES:
            assert _why.strip()
            assert any(t.startswith(_prefix) for t in _texts), _prefix

    def test_a8_the_three_gate_blocks_are_short_outside_and_verbatim_inside(self, tmp_path):
        _at = _run(tmp_path, _LOADED)
        _out = _exposed_sentences(_at)
        # ① 頁首狀態列（更新時間｜資料日）：外露只到日期，後半句逐字下沉「資料來源與完整度」。
        _head = [t for t in _out if t.startswith(f"{PM.NO_REFRESH_YET}｜")]
        assert len(_head) == 1 and len(_plain(_head[0])) <= A8_MAX_CHARS, _head
        _full = B.data_date_text({"index_as_of": "2026-10-23"})
        assert _full == "資料日：2026-10-23（加權指數，來源：市場評估輸入）"            # 原整句不變
        assert _head[0] == f"{PM.NO_REFRESH_YET}｜資料日：2026-10-23" and _full.startswith(_head[0].split("｜")[1])
        assert B.DATA_DATE_SOURCE_NOTE not in "".join(_out)
        _src = _all_text_in(_at, "資料來源與完整度")
        assert _full in _src
        # ② AI／資料狀態行：外露＝原句前兩段；原整句（含指路句）逐字在同一展開區。
        _ai = [t for t in _out if t.startswith(B.HERO_AI_PLACEHOLDER)]
        assert _ai == [B.ai_status_line_face()] and len(_plain(_ai[0])) <= A8_MAX_CHARS
        assert B.ai_status_line_full() == f"{B.HERO_AI_PLACEHOLDER}　{B.HEALTH_CHIP}{B.HEALTH_CHIP_POINTER}"   # 原整句不變
        assert B.ai_status_line_full().startswith(B.ai_status_line_face())
        assert B.HEALTH_CHIP_POINTER not in "".join(_out)
        assert B.ai_status_line_full() in _src
        # ③ 圖 C 一行：外露＝CHART_C_EMPTY 第一句；整句逐字在圖 C 摺疊「為什麼」（圖 C 的細節另見 test_p4_2 TestC8a）。
        assert B.CHART_C_EMPTY_FACE in _out and len(_plain(B.CHART_C_EMPTY_FACE)) <= A8_MAX_CHARS
        assert B.CHART_C_EMPTY.startswith(B.CHART_C_EMPTY_FACE) and B.CHART_C_EMPTY not in _out
        assert B.CHART_C_EMPTY in _all_text_in(_at, B.FOLD_LABEL)

    def test_a8_short_faces_are_fragments_of_the_original_sentences_not_new_wording(self):
        """縮短只能「取原句既有片段」：外露短版必須是原句的前綴（⛔ 不新造語意）。"""
        assert B.CHART_C_EMPTY.startswith(B.CHART_C_EMPTY_FACE)
        assert B.ai_status_line_full().startswith(B.ai_status_line_face())
        assert B.data_date_text({"index_as_of": "2026-10-23"}).startswith(B.data_date_text({"index_as_of": "2026-10-23"}, full=False))
        assert B.data_date_text({}) == B.data_date_text({}, full=False) == B.DATA_DATE_NOT_PROVIDED

    def test_a8_contract_and_client_sentences_are_not_shortened(self):
        """逐字測試釘住的客戶／契約句不得被這次的縮短波及（記錄：未動的項目）。"""
        assert B.HERO_AI_PLACEHOLDER == "🤖 AI 投資總結：⬜ 尚未提供"
        assert B.HEALTH_CHIP == "⬜ 資料狀態：尚未彙總"
        assert B.HEALTH_CHIP_POINTER == "（逐來源結果見頁首更新鈕下方的更新報告）"
        assert PM.REFRESH_TIME_NOTE == "按下更新的時間，不是資料日"
        assert B.CHART_C_SAY == "用企業獲利 EPS 搭配不同合理本益比情境，觀察目前指數位在便宜、合理或偏貴區域。"
        assert B.CHART_C_BASIS == "查看依據：此區塊未啟用，沒有使用任何資料。"


class TestA6PrimaryHeightIsPinnedAtTodaysValue:
    """⛔ 這不是「220 才對」的宣告：A6（手機 220 vs 契約 ≤140）是待客戶判斷的題 2（GATE_REPORT §11.1）。
    本組只釘**現況**，讓任何人改圖高都必須同時改這裡＝先過客戶裁示。"""

    def test_primary_chart_height_is_220_for_desktop_and_mobile_alike(self):
        assert B.PRIMARY_CHART_HEIGHT_PX == 220 == cp.SLOT_HEIGHT_MAX_PX
        _src = (_ROOT / "src" / "ui" / "views" / "_market_blocks.py").read_text(encoding="utf-8")
        _fn = next(n for n in ast.walk(ast.parse(_src)) if isinstance(n, ast.FunctionDef) and n.name == "render_chart_a")
        _heights = {ast.unparse(kw.value) for n in ast.walk(_fn) if isinstance(n, ast.Call)
                    for kw in n.keywords if kw.arg == "height"}
        assert _heights == {"PRIMARY_CHART_HEIGHT_PX"}, _heights        # 圖與冷啟動槽共用同一個值，沒有依 viewport 分流的第二個高度

    def test_rendered_primary_chart_uses_that_height(self, tmp_path):
        _at = _run(tmp_path, _LOADED)
        _charts = [c for t in ("vega_lite_chart", "arrow_vega_lite_chart", "line_chart", "arrow_line_chart") for c in _at.get(t)]
        assert len(_charts) == 1
        _h = getattr(_charts[0].proto, "height", None)
        assert _h in (None, 0, 220) or _h == B.PRIMARY_CHART_HEIGHT_PX, _h
