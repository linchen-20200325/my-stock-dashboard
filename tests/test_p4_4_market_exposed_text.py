"""tests/test_p4_4_market_exposed_text.py — Phase 4 P4-4（📊 市場頁，內部小修批）：外露層句長守衛＋Primary 圖高現況釘死。

來源：`docs/vnext/phase4_market/p4_3/GATE_REPORT.md` A8（外露 >32 字且非客戶原句 3 塊）／發現項 F3（沒有任何測試釘句長與圖高）。
  A8 ── 外露層（不在 expander 內）的 Caption／Markdown 純文字（去 HTML 標籤、`**`、空白後）＞32 字者，必須是**白名單內的逐字客戶原句／
        契約句**（精確比對：結論句固定模板 `_CONCLUSION_RE`、R8 狀態列半句、⚡ bar 逐片段，每條附出處；⛔ 不用前綴）；其餘一律 ≤32。被縮短的 3 塊（頁首資料日、AI／資料狀態行、圖 C 一行）另釘：
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

from shared import market_conclusion as MC
from src.services import market_twii_view_service as S
from src.ui.views import _market_blocks as B
from src.ui.views import page_market as PM
from src.ui.views import page_today as P
from src.ui_v2 import compact as cp
from tests.test_p4_1_market_first_screen import _events, _report
from tests.test_uim_market_page import _LOADED, _run, _view

_ROOT = pathlib.Path(__file__).resolve().parents[1]
A8_MAX_CHARS = 32          # Gate A8（客戶 DEC-109）：外露層一句 ≤32 字（Gate 量法：去空白後的字元數）

#: 外露層允許超過 32 字的**客戶原句／契約句**，一律**精確比對**（⛔ 不用前綴；前綴會讓任何以該前綴起頭的自寫長句漏過）。
#: 每條附出處。⛔ 新增任何一條都必須有客戶／契約出處，不得為了讓測試過而把 AI 自寫句加進來。
_CONCLUSION_RE = re.compile(
    "市場位階：([^；]+)；台股趨勢：" + re.escape(MC.TREND_UNDEFINED_TEXT) + "；國際趨勢：" + re.escape(MC.TREND_UNDEFINED_TEXT)
    + "；指標危險度：([^；]+)；風險上限：" + re.escape(MC.RISK_CAP_CLAUSE_TEXT) + "。")
#: 今日結論句：客戶原句（DEC-081 Q2-1）＝`shared.market_conclusion.build_market_conclusion` 的固定模板；整句 fullmatch，
#: 兩個可變子句（位階、危險度）來自各自的卡、不得含「；」。以「市場位階：」起頭但不符模板 ⇒ 不豁免。
#: 狀態列「更新時間」半句（R8 契約格式，Phase 4 之前就有）：`本頁更新於 {時間}（{REFRESH_TIME_NOTE}）` 整段 fullmatch。
_STATUS_TIME_RE = re.compile("本頁更新於 [^（）]+（" + re.escape(PM.REFRESH_TIME_NOTE) + "）")
#: ⚡ 一行 bar（客戶 DEC-117 Q8c 核准的一行形式）：`**⚡ 需要處理**` ＋ 以全形空白串起的既有卡片段。整行 >32 是形式本身；
#: 守衛改成**逐片段**各自 ≤32（與 Gate 的 DOM 葉節點量法一致）——自寫長句塞進 bar 仍會紅。
_ALERT_BAR_PREFIX = f"**{B.ALERTS_TITLE}**　"
#: HTML 元件裡逐字的客戶原句（目前 header 各葉節點皆 ≤32，白名單為空；有需要時只能加整句常數）。
_EXACT_VERBATIM_LEAVES: frozenset[str] = frozenset()


@pytest.fixture(autouse=True)
def _fixed_twii_view(monkeypatch):
    monkeypatch.setattr(S, "get_twii_trend_view", lambda n: _view())


def _plain(t: str) -> str:
    """Gate 的字數口徑：去 HTML 標籤、粗體記號、全部空白（含全形空白）。"""
    return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", t).replace("**", ""))


_TEXT = ("Markdown", "Caption", "Info", "Success", "Text", "Error", "Warning")


def _leaves(t: str) -> list[str]:
    """一個外露元素 → 可見文字葉節點：`<style>` 內容不算；HTML 標籤與換行都是葉節點邊界；markdown 表格每個儲存格各一葉。"""
    t = re.sub(r"<style>.*?</style>", "", t, flags=re.S)
    out = []
    for _part in re.split(r"<[^>]+>|\n", t):
        _part = _part.strip()
        if not _part or re.fullmatch(r"[|\-: ]+", _part):
            continue
        out.extend(c.strip() for c in _part.strip("|").split("|")) if _part.startswith("|") else out.append(_part)
    return [x for x in out if x]


def _report_source_texts() -> frozenset[str]:
    """既有 `page_today._render_refresh_report`（DEC-081 Q1=C 禁改）自己畫出的文字：A8 不管它們。其餘 Error／Warning 一律照掃。"""
    import tempfile
    _script = ("import streamlit as st\n"
               "from tests.test_p4_1_market_first_screen import _report\n"
               "from src.ui.views import page_today as P\n"
               "P._render_refresh_report(_report(failed=True))\n")
    from streamlit.testing.v1 import AppTest
    _f = pathlib.Path(tempfile.mkdtemp()) / "_r.py"
    _f.write_text(_script, encoding="utf-8")
    _at = AppTest.from_file(str(_f), default_timeout=120)
    _at.run()
    assert not _at.exception, _at.exception
    return frozenset(_t for _k, _t, _e, _ in _events(_at.main) if _k in _TEXT)


def _violations(at, report_texts: frozenset[str]) -> list[tuple[int, str]]:
    bad = []
    for _k, _t, _e, _keys in _events(at.main):
        if _e is not None or _k not in _TEXT or _t in report_texts:
            continue
        if _CONCLUSION_RE.fullmatch(_t):
            continue
        _pieces = [_t]
        if _t.startswith(_ALERT_BAR_PREFIX):
            _pieces = _t[len(_ALERT_BAR_PREFIX):].split("　")
        for _piece in _pieces:
            for _leaf in _leaves(_piece):
                _head, _sep, _tail = _leaf.partition("｜")
                if _sep and _STATUS_TIME_RE.fullmatch(_head):
                    _leaf = _tail                      # R8 契約半句整段豁免，資料日半句照掃
                if _leaf in _EXACT_VERBATIM_LEAVES:
                    continue
                if len(_plain(_leaf)) > A8_MAX_CHARS:
                    bad.append((len(_plain(_leaf)), _leaf[:80]))
    return bad


def _exposed_sentences(at) -> list[str]:
    """外露層（不在 expander 內）的純文字句：排除 `<style>`／HTML 元件（header、小倍數）與 markdown 表格。"""
    out = []
    for _k, _t, _e, _keys in _events(at.main):
        if _e is None and _k in _TEXT and not _t.lstrip().startswith(("<", "|")):
            out.append(_t)
    return out


def _all_text_in(at, label: str) -> list[str]:
    return [_t for _k, _t, _e, _ in _events(at.main) if _e == label and _k in _TEXT]


class TestA8ExposedSentenceLength:
    @pytest.mark.parametrize("state", ["cold", "loaded", "report", "partial"])
    def test_a8_every_exposed_leaf_is_le_32_or_an_exact_verbatim_sentence(self, tmp_path, state):
        """外露層每個可見文字葉節點（含 unsafe_allow_html 的 HTML 元件、表格儲存格、Warning／Error）≤32 字，
        或是精確比對的客戶／契約句。Error／Warning 只排除既有 page_today 更新報告自己畫的字。"""
        _sess = {"cold": None, "loaded": _LOADED,
                 "report": {**_LOADED, P.SS_REFRESH_REPORT: _report()},
                 "partial": {**_LOADED, P.SS_REFRESH_REPORT: _report(failed=True)}}[state]
        _at = _run(tmp_path, _sess)
        assert not _at.exception, _at.exception
        _bad = _violations(_at, _report_source_texts())
        assert not _bad, f"外露層有 >{A8_MAX_CHARS} 字且不在精確白名單內的葉節點（A8）：{_bad}"

    def test_a8_the_exact_whitelist_exists_on_the_page_and_a_lookalike_prefix_is_not_exempt(self, tmp_path):
        _at = _run(tmp_path, _LOADED)
        _texts = _exposed_sentences(_at)
        assert any(_CONCLUSION_RE.fullmatch(t) for t in _texts)          # 今日結論句真的出現且符合固定模板
        assert any(t.startswith(_ALERT_BAR_PREFIX) for t in _texts)
        # 自寫長句借用白名單開頭 ⇒ 不豁免（這是前綴式白名單的漏洞）
        _fake = "市場位階：" + "這是一句自己寫的很長的說明文字用來測試守衛會不會被前綴騙過去。"
        assert not _CONCLUSION_RE.fullmatch(_fake)
        assert len(_plain("很長" * 20)) > A8_MAX_CHARS            # bar 片段規則：自寫長句塞進 ⚡ bar 仍會被逐片段檢查抓到

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
