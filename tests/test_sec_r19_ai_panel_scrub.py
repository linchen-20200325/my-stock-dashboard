"""SEC-r19（2026-10-01，批 S5）：v1 `tab_ai_chat._render_panel`（🧬 AI 總結本頁）的 AI 散文上畫面前要洗。

AI 產出的六段散文 —— 分析師觀點 `per_analyst[].text`、多空辯論 `bull`／`bear`／`verdict`、
風控 `risk_review.text`、最終報告 `text` —— 改走 L0 `scrub_qa_text`（同 SEC-r11 問答回答）。

測法：**行為**測試（假 streamlit 收集所有輸出字串，真的呼叫 `_render_panel`）：
(1) 秘密逐段只放進其中一段 → 該段一個秘密都不得上畫面（六段各自一案 ⇒ 拔掉任一處清洗 → 對應一案轉紅）；
(2) 不含秘密的散文（含刻意 `**粗體**`）→ 輸出與修法前的 f-string **逐字相同**（零可見字變更）。
"""
from __future__ import annotations

import pytest

import src.ui.tabs.tab_ai_chat as AC
from src.services.ai_qa_service import PanelResult
from tests.test_sec3_scrub_legacy_pages import _PLAIN_MSG, _SECRET_MSG, FakeSt, _assert_no_leak

_FIELDS = ("analyst", "bull", "bear", "verdict", "risk", "report")


def _panel(**over) -> PanelResult:
    t = {f: f"{_PLAIN_MSG} **{f} 粗體**" for f in _FIELDS}
    t.update(over)
    return PanelResult(
        ok=True, text=t["report"], model="gemini-x",
        per_analyst=[{"role": "技術面分析師", "text": t["analyst"]}],
        debate={"bull": t["bull"], "bear": t["bear"], "verdict": t["verdict"]},
        risk_review={"text": t["risk"], "data_ok": "3/3"},
        data_bundle={},
    )


def _render(monkeypatch, res) -> FakeSt:
    _st = FakeSt()
    monkeypatch.setattr(AC, "st", _st)
    AC._render_panel(res)
    return _st


@pytest.mark.parametrize("field", _FIELDS)
def test_each_ai_prose_section_masks_secrets(monkeypatch, field):
    _st = _render(monkeypatch, _panel(**{field: f"結論：{_SECRET_MSG}"}))
    assert "結論：" in _st.text  # 前提：該段真的有上畫面
    _assert_no_leak(_st.text)


def test_plain_prose_rendered_byte_identical(monkeypatch):
    res = _panel()
    _st = _render(monkeypatch, res)
    v = res.per_analyst[0]
    want = [
        f"**{v['role']}**:{v['text']}",
        f"**多方**:{res.debate['bull']}",
        f"**空方**:{res.debate['bear']}",
        f"**裁判**:{res.debate['verdict']}",
        f"🛡️ 風控(資料完整度 {res.risk_review['data_ok']}):{res.risk_review['text']}",
        f"### 🧬 AI 總結｜使用模型:{res.model}\n\n{res.text}",
    ]
    for w in want:
        assert w in _st.out, w
