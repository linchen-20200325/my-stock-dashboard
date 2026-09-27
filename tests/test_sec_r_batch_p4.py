"""SEC-r 批次 P4（2026-09-27）：SEC-r2 / SEC-r3 / SEC-r7 / SEC-r9。

- SEC-r2：`api_key: not set` 原本被遮成 `api_key: *** set`（讀起來像「已設定」）→ 整段遮。
- SEC-r3：v2 卡面 `v2_plain()` 把遮罩 `***` 吃成 `*` → 遮罩原樣保留。
- SEC-r7：`page_why` 的 AI 回答在 L5 沒過 `scrub_secrets` → 畫面與對話紀錄都洗過。
- SEC-r9：`data_coverage` 的 detail 欄進 `unsafe_allow_html` 前沒跳脫 → `html.escape`。

全部是**行為**測試（真的呼叫函式／真的跑渲染）；拔掉修法（突變）→ 對應那一條轉紅。
"""
from __future__ import annotations

import datetime as _dt
import html
import re
import time

import pytest

from shared.secret_md import scrub_md_mask
from shared.secret_scrub import MASK, scrub_query_secrets, scrub_secrets

# ══════════════════════════════════════════════════════════════════
# SEC-r2
# ══════════════════════════════════════════════════════════════════
_NEG_CASES = [
    ("api_key: not set", "api_key: ***"),
    ("API_KEY: Not Set", "API_KEY: ***"),
    ("password: not configured", "password: ***"),
    ("'api_key': not set", "'api_key': ***"),
    ('"client_secret": no value', '"client_secret": ***'),
    ("ValueError('fred_api_key: not found')", "ValueError('fred_api_key: ***')"),
]


@pytest.mark.parametrize("raw,want", _NEG_CASES)
def test_r2_negation_phrase_is_masked_whole(raw, want):
    _out = scrub_secrets(raw)
    assert _out == want
    # 反向：畫面上不能出現「*** set」這種讀起來像「已設定」的殘句
    assert not re.search(r"\*\*\* (?:set|configured|value|found)", _out, re.I)


@pytest.mark.parametrize("raw,want", [
    ("password: hunter2", "password: ***"),        # 一般值：照舊
    ("password: no", "password: ***"),             # 單一 no：照舊整個遮
    ("password: not_a_word", "password: ***"),     # 不是片語：照舊
    ("password: hunter2 set", "password: *** set"),  # 一般值後接字：範圍不變（⛔ 不擴大）
    ("api_key = not set", "api_key = ***"),        # TOML 賦值：本來就遮到行尾
])
def test_r2_other_values_unchanged(raw, want):
    assert scrub_secrets(raw) == want


# QA 阻擋（2026-09-27）：`not/no` 後面緊接的是**真秘密**時，⛔ 不得吃掉秘密的前綴字母
# （否則後面的權杖／路徑規則對不上 → 秘密本體外露）。樣本為實際長度的秘密。
_R2_AIZA = "AIzaSyA1b2C3d4E5f6G7h8I9j0KlMnOpQrStUvW"      # 39 字
_R2_YA29 = "ya29.a0AfH6SMBx1234567890abcdefGHIJKLmnopQRSTuvwxYZ_-0123456789"
_R2_GOCSPX = "GOCSPX-abcdefghij1234567KLMNOPqrstuv"
_R2_WINPATH = "C:\\Users\\bob\\.streamlit\\secrets.toml"


@pytest.mark.parametrize("raw,body", [
    (f"api_key: no {_R2_AIZA}", _R2_AIZA[-20:]),
    (f"password: not {_R2_YA29}", _R2_YA29[-20:]),
    (f"secret: no {_R2_GOCSPX}", _R2_GOCSPX[-20:]),
    (f"password: no {_R2_WINPATH}", "Users\\bob"),
])
def test_r2_neg_does_not_eat_a_real_secret_prefix(raw, body):
    _out = scrub_secrets(raw)
    assert body not in _out, _out
    assert MASK in _out


def test_r2_neg_before_query_assignment_matches_baseline():
    """`no key=AIza…`：`key` 後接 `=` ⇒ ⛔ 不走 neg 分支；輸出與基底 1894b50 逐字相同
    （期望值以 `git show 1894b50:shared/secret_scrub.py` 實跑取得）。"""
    _raw = f"password: no key={_R2_AIZA}"
    assert scrub_secrets(_raw) == "password: *** key=***"


def test_r2_plain_prose_untouched():
    for _s in ("the token is not set yet", "key not set", "not set", "價格: not set"):
        assert scrub_secrets(_s) == _s


def test_r2_no_redos_on_neg_branch():
    _big = "password: " + "not " * 200_000 + "x" * 100_000
    _t0 = time.perf_counter()
    scrub_secrets(_big)
    assert time.perf_counter() - _t0 < 5.0


def test_query_scrubber_is_still_the_old_ai_qa_one():
    """`scrub_query_secrets` 本批一字未動：與舊 ai_qa 版本的 regex 逐字等價。"""
    _old_q = re.compile(r"\b(key|token|api[_-]?key|access[_-]?token)=[^&\s\"'<>]+", re.IGNORECASE)
    _old_g = re.compile(r"AIza[0-9A-Za-z_\-]{10,}")

    def _old(s):
        return _old_g.sub("AIza***", _old_q.sub(lambda m: m.group(1) + "=***", str(s)))

    for _s in ("x?key=abc&token=def", "api_key: not set", "AIzaSyA1234567890abcdef",
               "access-token=zz key=1 none", "", "中文 key= 值"):
        assert scrub_query_secrets(_s) == _old(_s)


# ══════════════════════════════════════════════════════════════════
# SEC-r3
# ══════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
def v2_plain():
    from src.ui.views.page_today import v2_plain as _f
    return _f


@pytest.mark.parametrize("raw,want", [
    ("key=***", "key=***"),
    ("`key=***`", "key=***"),
    ("**錯誤** key=***", "錯誤 key=***"),
    ("**key=*****", "key=***"),          # 粗體開頭緊貼遮罩收尾
    ("*****x**", "***x"),                # 粗體開頭緊貼遮罩
    ("原始例外：`api_key: ***`", "原始例外：api_key: ***"),
])
def test_r3_mask_survives_v2_plain(v2_plain, raw, want):
    assert v2_plain(raw) == want


@pytest.mark.parametrize("raw", [
    "**今天能不能出手：尚未評估**", "a*b", "**a** **b**", "`code`", "****", "", "3 * 4",
    "**x**y*z", "*",
])
def test_r3_non_mask_text_same_as_before(v2_plain, raw):
    """非遮罩的字串：行為與舊實作（`replace('**','')` → `replace('`','')`）逐字相同。"""
    assert v2_plain(raw) == str(raw).replace("**", "").replace("`", "")


def test_r3_real_scrubbed_error_through_v2_plain(v2_plain):
    _err = scrub_secrets('client_secret = "S3CRETv2" failed')
    assert MASK in _err and "S3CRETv2" not in _err
    assert MASK in v2_plain(f"**讀取失敗**：`{_err}`")


# ══════════════════════════════════════════════════════════════════
# SEC-r7
# ══════════════════════════════════════════════════════════════════
_R7_KEY = "AIzaSyA1234567890secR7abcdefg"
_R7_PW = "pw_R7_zzq"
_R7_ANSWER = (f"**結論**：偏強。\n\n你的設定裡 password: {_R7_PW}，"
              f"金鑰 {_R7_KEY}，檔案在 /home/aliceR7/app/secrets.toml")


def test_r7_render_scrubs_answer_and_history(monkeypatch):
    from src.ui.views import page_why as P
    from tests.test_p05_why_view import _FakeChatST, _fake_agent, _render_qa

    _fake = _FakeChatST(typed="2330 健康度？")
    _fake_agent(monkeypatch, text=_R7_ANSWER)
    _out = _render_qa(monkeypatch, _fake)
    for _leak in (_R7_KEY, _R7_PW, "aliceR7"):
        assert _leak not in _out
    _hist = " ".join(str(m.get("content")) for m in _fake.session_state[P.SS_QA_HISTORY])
    for _leak in (_R7_KEY, _R7_PW, "aliceR7"):
        assert _leak not in _hist
    # 原句粗體保留、遮罩做了 Markdown 跳脫（同 shared/secret_md 慣例）
    assert "**結論**" in _out and "\\*\\*\\*" in _out


def test_r7_clean_answer_is_byte_identical(monkeypatch):
    from src.ui.views import page_why as P
    from tests.test_p05_why_view import _FakeChatST, _fake_agent, _render_qa

    _clean = "**偏強**，***注意***量能。\n\n- 元/股 80/20"
    _fake = _FakeChatST(typed="q")
    _fake_agent(monkeypatch, text=_clean)
    _render_qa(monkeypatch, _fake)
    _body = _fake.session_state[P.SS_QA_HISTORY][-1]["content"]
    assert _body == P.compose_qa_message(_clean)


def test_r7_helper_matches_secret_md_convention():
    from src.ui.views.page_why import scrub_qa_text
    assert scrub_qa_text(_R7_ANSWER) == scrub_md_mask(_R7_ANSWER)
    assert scrub_qa_text("無秘密 **粗體**") == "無秘密 **粗體**"


# ══════════════════════════════════════════════════════════════════
# SEC-r9
# ══════════════════════════════════════════════════════════════════
class _FakeST:
    def __init__(self):
        self.md: list[str] = []

    def markdown(self, body, **_k):
        self.md.append(str(body))

    def caption(self, body, **_k):
        self.md.append(str(body))


def test_r9_detail_is_html_escaped(monkeypatch):
    import src.ui.pages.data_coverage as D
    _detail = "❌ 2330 價格抓取失敗：<script>alert(1)</script> <img src=x onerror=y> a&b \"q\""
    _row = {"tab": "🔬 個股", "emoji": "🔴", "color": "#f00", "ratio_txt": "0/1",
            "detail": _detail, "action": "x"}
    _fake = _FakeST()
    monkeypatch.setattr(D, "st", _fake)
    monkeypatch.setattr(D, "compute_tab_coverage", lambda *a, **k: [_row])
    D.render_data_coverage()
    _all = "\n".join(_fake.md)
    assert "<script>" not in _all and "<img src=x" not in _all
    assert html.escape(_detail) in _all


def test_r9_plain_detail_renders_same_text(monkeypatch):
    import src.ui.pages.data_coverage as D
    _rows = D.compute_tab_coverage(state={"t2_data": {"sid": "2330", "err": "HTTP 502"}},
                                   today=_dt.date(2026, 9, 27))
    _fake = _FakeST()
    monkeypatch.setattr(D, "st", _fake)
    monkeypatch.setattr(D, "compute_tab_coverage", lambda *a, **k: _rows)
    D.render_data_coverage()
    _all = "\n".join(_fake.md)
    for _r in _rows:
        # 沒有 HTML 特殊字元的細項 → 逐字出現（escape 不改一般訊息）
        if not set(_r["detail"]) & set("<>&\"'"):
            assert _r["detail"] in _all
