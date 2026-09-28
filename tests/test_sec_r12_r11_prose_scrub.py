"""SEC-r12／SEC-r11（2026-09-28）：問答散文走「散文版」清洗；v1 🧬 AI 問答頁籤補齊清洗。

- **SEC-r12**：L0 `scrub_secrets` 第 1 類（解碼例外）把「型別名＋左括號」或「型別名＋冒號」起到字串結尾
  整段拿掉、只留型別名 —— 那是給**錯誤訊息**用的（`repr` 會夾帶被解碼的原始位元組）。它也被套在**問答散文**上：
  提問「為什麼出現 UnicodeDecodeError: … 怎麼解？」在畫面、紀錄、送出三處都被截成「為什麼出現
  UnicodeDecodeError」；AI 回答「你看到的是 UnicodeDecodeError: … 解法：…」整段解法消失。
  修法：L0 新增 `shared/secret_scrub.scrub_prose_secrets`（＝ `scrub_secrets`，只有那一條改成只截 repr 形）
  與 `shared/secret_md.scrub_qa_text`（自 `page_why` 下沉、改用散文版）；v2 `page_why` 送 L3 用純文字版、
  畫面／紀錄用 Markdown 版（分工同前）。
- **SEC-r11**：v1 `src/ui/tabs/tab_ai_chat.py::render`（側欄預設畫面）提問以原文上畫面、存進
  `ai_qa_history`、送 `run_agent`，下一題又隨 history 再送一次；AI 回答也沒洗。修法：比照 v2。
- **批 Q 獨立 QA 追加（2026-09-28）**：(1) toml 0.10.2 重複表錯誤把已解析的整包 dict 串進訊息 → 散文版
  仍從大括號起截掉（section 1b；有裝 `toml` 就用真的 `toml.loads`，沒有就用逐字錄下的字串）；
  (2) 少遮邊界 (b) 補第二種例子；(3) v1 在第一題之後也斷言畫面（只在「本輪剛畫」外露的突變直接抓到）。

測法：全部是**行為**測試（真的呼叫函式／真的跑渲染；v1 用 `AppTest`＋假 `run_agent`），
每一個修法點都有**突變驗證**（拔掉 → 本檔對應那一組斷言轉紅）。
⚠️ 本檔驗的全稱結論（例：「除了散文形，其餘輸入與 `scrub_secrets` 逐字相同」）是**本實作組自測，
未經獨立 QA**；語料外的輸入沒有被窮舉（證明靠 AST 同構＋語料＋蛻變關係三條互相印證，不是窮舉）。
"""
from __future__ import annotations

import ast
import functools
import importlib.util
import inspect
import json
import pathlib
import random
import re
import sys
import textwrap
import types

import pytest

from shared import secret_md as SMD
from shared import secret_scrub as SSC
from shared.secret_md import scrub_md_mask, scrub_qa_text
from shared.secret_scrub import MASK, scrub_prose_secrets, scrub_secrets
from tests.test_p05_why_view import _FakeChatST, _fake_agent, _render_qa
from tests.test_sec_s2_scrub_gaps import _UNITS as _S2_REDOS_UNITS
from tests.test_sec_s2_scrub_gaps import _corpus as _s2_corpus
from tests.test_sec_s3_0928 import _capture_agent
from tests.test_v2_silent_fail_b11_hold_misc import (
    _ADVERSARIAL_PREFIXED,
    _ADVERSARIAL_UNITS,
    _LEAKY,
    _PLAIN,
    _REDOS_PER_CASE_S,
    _REDOS_START_TAG,
    _fuzz_corpus,
    _rep,
    _run_redos_cases,
)

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_ESC_MASK = "\\*" * len(MASK)

# ══════════════════════════════════════════════════════════════════
# 樣本
# ══════════════════════════════════════════════════════════════════
_UDE = "UnicodeDecodeError"
_ERR_MSG = "'utf-8' codec can't decode byte 0xff in position 28: invalid start byte"
#: SEC-r12 的兩個實證形狀：引用錯誤訊息的提問、寫出錯誤名稱與解法的 AI 回答（都不含秘密）。
_Q_ERR = f"為什麼出現 {_UDE}: {_ERR_MSG}，怎麼解？"
_A_ERR = f"你看到的是 {_UDE}: {_ERR_MSG}。解法：把 secrets.toml 另存成 UTF-8（無 BOM）後重新啟動。"
#: 引用的錯誤訊息裡夾了路徑、帳密、金鑰 —— 散文形保留，但這三樣仍要被其他規則遮掉。
_KEY = "AIzaSyR12qAbCdEfGhIjKlMnOpQrStUvWx"
_PW = "pwR12zzq"
_USER = "aliceR12"
_Q_ERR_SECRET = (f"為什麼出現 {_UDE}: 讀 /home/{_USER}/app/.streamlit/secrets.toml 時卡住，"
                 f"我的 password: {_PW} 跟金鑰 {_KEY} 怎麼解？")
_Q_ERR_SECRET_WANT = (f"為什麼出現 {_UDE}: 讀 ***/secrets.toml 時卡住，"
                      "我的 password: *** 跟金鑰 AIza*** 怎麼解？")
_LEAKS_Q = (_KEY, _PW, _USER, f"/home/{_USER}", ".streamlit")
#: repr 形（型別名＋左括號）夾帶被解碼的原始位元組 —— 散文版**照舊截掉**。
_REPR_SECRET = "S3R12reprZZ"
_REPR = repr(UnicodeDecodeError("utf-8", f'client_secret = "{_REPR_SECRET}"\n\xff'.encode("latin-1"),
                                28, 29, "invalid start byte"))
#: 沒有任何可遮的東西（含 Markdown 粗體、粗斜體、中文斜線）→ 散文版與 `scrub_qa_text` 都要逐字不動。
_CLEAN_Q = "2330 **健康度**？元/股 80/20 TW/US"
_CLEAN_A = "**偏強**，***注意***量能。\n\n- 元/股 80/20"

#: `_LEAKY`（`test_v2_silent_fail_b11_hold_misc`）裡**只靠第 1 類散文形**擋的三筆 —— 散文版刻意不截它們
#: （這就是散文版比 `scrub_secrets` 少遮的那一種，見 `TestExactScope`）。
_COLON_FIRST_LEAKY = frozenset({"toml_colon_form", "toml_wrapped_colon", "unicode_colon_form"})


# ══════════════════════════════════════════════════════════════════
# 工具：散文形「解除」＋還原（蛻變關係用）、突變載入
# ══════════════════════════════════════════════════════════════════
#: 散文形（型別名＋可有空白／tab＋冒號）。型別名清單與 `SSC._CONTENT_BEARING_EXC_RE` 相同
#: （`test_repr_only_rule_is_rule_one_narrowed_to_the_paren` 把兩者都逐字釘住）。
_COLON_FORM_RE = re.compile(r"(Unicode(?:Decode|Encode|Translate)Error|TomlDecodeError)(?=[ \t]*:)")
#: 把型別名的第一個字母換成 `Q` —— 同樣是英文字母（其他規則的字元類別判斷完全一樣），但第 1 類認不得。
_DEFUSED: dict[str, str] = {
    "UnicodeDecodeError": "QnicodeDecodeError", "UnicodeEncodeError": "QnicodeEncodeError",
    "UnicodeTranslateError": "QnicodeTranslateError", "TomlDecodeError": "QomlDecodeError"}


def _defuse(x: str) -> str:
    return _COLON_FORM_RE.sub(lambda m: _DEFUSED[m.group(1)], x)


def _unmap(y: str) -> str:
    for _k, _v in _DEFUSED.items():
        y = y.replace(_v, _k)
    return y


def _has_sentinel(x: str) -> bool:
    return any(_v in x for _v in _DEFUSED.values())


def _colon_first(x: str) -> bool:
    """第一個命中第 1 類（`scrub_secrets` 那條）的位置是散文形 —— 兩支函式**唯一**可能不同的輸入。"""
    m = SSC._CONTENT_BEARING_EXC_RE.search(x)
    return m is not None and SSC._CONTENT_BEARING_EXC_REPR_RE.match(x, m.start()) is None


_TOML_NAME = "TomlDecodeError"
_TOML_EXISTS = "already exists?"
_TOML_GAP_MAX = 512


def _oracle_toml_cut(x: str) -> str:
    """批 Q QA 加固（`_TOML_DUP_TABLE_DICT_RE`）的**獨立實作**：逐字元掃描，不借用產品 regex。

    依序看每一個「`TomlDecodeError`＋空白／tab＋冒號」；冒號之後 0～512 字內（可跨行）最早出現的
    「`already exists?`＋0～4 個空白字元＋左大括號」→ 從那個大括號起整段拿掉；這一個找不到就看下一個。
    """
    start = x.find(_TOML_NAME)
    while start >= 0:
        j = start + len(_TOML_NAME)
        while j < len(x) and x[j] in " \t":
            j += 1
        if j < len(x) and x[j] == ":":
            for gap in range(_TOML_GAP_MAX + 1):
                k = j + 1 + gap
                if k > len(x):
                    break
                if x.startswith(_TOML_EXISTS, k):
                    m = k + len(_TOML_EXISTS)
                    for n in range(5):
                        if m + n < len(x) and x[m + n] == "{" and all(c.isspace() for c in x[m:m + n]):
                            return x[:m + n]
        start = x.find(_TOML_NAME, start + 1)
    return x


def _expected_prose(x: str) -> str:
    """散文版的「應有輸出」：先套 toml 重複表加固（獨立實作），再把散文形的型別名當普通字交給 `scrub_secrets`。"""
    return _unmap(scrub_secrets(_defuse(_oracle_toml_cut(x))))


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    """把 `mod` 原始碼裡每一組 `old` **恰好一處**換成 `new`，載成獨立的新模組（同本 repo 其他 `_mutant`）。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_r12_{mod.__name__.rsplit('.', 1)[-1]}_{abs(hash(pairs))}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)  # noqa: S102
    finally:
        sys.modules.pop(name, None)
    return m


# ══════════════════════════════════════════════════════════════════
# 1. L0 散文版：散文形保留、repr 形照截、秘密照遮
# ══════════════════════════════════════════════════════════════════
def _assert_prose_keeps_the_colon_form(fn) -> None:
    """（被突變測試重用）散文形的提問／回答逐字保留；引用裡的秘密照遮。"""
    assert fn(_Q_ERR) == _Q_ERR
    assert fn(_A_ERR) == _A_ERR
    assert fn(_Q_ERR_SECRET) == _Q_ERR_SECRET_WANT


class TestProseScrubUnit:
    def test_premise_the_error_scrubber_cuts_prose(self):
        """前提（SEC-r12 的病灶，本批不改）：錯誤字串那支把散文形整段截掉。"""
        assert scrub_secrets(_Q_ERR) == f"為什麼出現 {_UDE}"
        assert scrub_secrets(_A_ERR) == f"你看到的是 {_UDE}"
        assert scrub_secrets(_Q_ERR_SECRET) == f"為什麼出現 {_UDE}"

    def test_colon_form_is_kept_and_secrets_inside_are_still_masked(self):
        _assert_prose_keeps_the_colon_form(scrub_prose_secrets)
        for leak in _LEAKS_Q:
            assert leak not in scrub_prose_secrets(_Q_ERR_SECRET), leak

    @pytest.mark.parametrize("head", [
        "UnicodeDecodeError: ", "UnicodeEncodeError : ", "UnicodeTranslateError\t:", "TomlDecodeError:",
        "ValueError: TomlDecodeError: "])
    def test_every_type_and_spacing_of_the_colon_form_is_kept(self, head):
        x = f"為什麼出現 {head}Duplicate keys 怎麼解？"
        assert scrub_prose_secrets(x) == x
        assert scrub_secrets(x) != x, "前提：錯誤字串那支會截"

    @pytest.mark.parametrize("x,want", [
        (f"這是什麼？{_REPR}", f"這是什麼？{_UDE}"),
        (f"這是什麼？{_UDE} ('utf-8', b'password = \"{_REPR_SECRET}\"')", f"這是什麼？{_UDE}"),
        (repr(RuntimeError(_REPR)), f"RuntimeError('{_UDE}"),
        (f"TomlDecodeError(\"What? {{'g': {{'name': '{_REPR_SECRET}'}}}}\") 是什麼", "TomlDecodeError"),
    ])
    def test_repr_form_is_still_cut(self, x, want):
        """repr 形（型別名＋可有空白＋左括號）：散文版與錯誤字串那支一樣，從那裡起整段拿掉。"""
        assert scrub_prose_secrets(x) == want == scrub_secrets(x)
        assert _REPR_SECRET not in scrub_prose_secrets(x)

    def test_colon_form_then_repr_form_is_cut_at_the_repr_form(self):
        """散文形在前、repr 形在後：散文照留，截在 repr 形（repr 裡的原始位元組照樣不外露）。"""
        x = f"{_UDE}: 先看這個，再看 {_REPR}"
        assert scrub_prose_secrets(x) == f"{_UDE}: 先看這個，再看 {_UDE}"
        assert scrub_secrets(x) == _UDE
        assert _REPR_SECRET not in scrub_prose_secrets(x)

    def test_clean_prose_is_byte_identical(self):
        for x in (_CLEAN_Q, _CLEAN_A, _Q_ERR, _A_ERR, "", "元/股/張 與 張/元"):
            assert scrub_prose_secrets(x) == x

    def test_none_and_non_str(self):
        assert scrub_prose_secrets(None) == "" and scrub_prose_secrets(12) == "12"

    @pytest.mark.parametrize("case", sorted(_LEAKY))
    def test_idempotent_and_no_new_words(self, case):
        """K1：遮罩沿用 `***`，拿掉遮罩後每個字元都來自原文（⛔ 沒有新造的字）；洗兩次＝洗一次。"""
        raw = _LEAKY[case][0]
        once = scrub_prose_secrets(raw)
        assert scrub_prose_secrets(once) == once
        assert set(once.replace(MASK, "")) <= set(raw), (case, once)


# ══════════════════════════════════════════════════════════════════
# 1b. 批 Q QA 加固：toml 0.10.2 重複表錯誤把已解析的整包 dict 串進訊息 → 散文版仍從大括號起截掉
# ══════════════════════════════════════════════════════════════════
#: 觸發重複表錯誤的 secrets.toml（值全是假的；`private_key` 裡的反斜線 n 在 TOML 是換行跳脫）。
_TOML_DOC = (
    'GEMINI_API_KEY = "AIzaSyTomlR12AbCdEfGhIjKlMnOpQrStUv"\n'
    "[gcp_service_account]\n"
    'type = "service_account"\n'
    'project_id = "proj-r12-toml"\n'
    'private_key_id = "pkidR12toml"\n'
    'private_key = "-----BEGIN PRIVATE KEY-----\\nMIIEvR12toml\\n-----END PRIVATE KEY-----\\n"\n'
    'client_email = "svc-r12@proj-r12-toml.iam.gserviceaccount.com"\n'
    'client_id = "109876543210987654321"\n'
    'my_api_pw = "hunter2customR12"\n'
    "\n"
    "[gcp_service_account]\n"
    "x = 1\n")
#: toml 0.10.2 對 `_TOML_DOC` 的 `str(e)`，逐字錄下（2026-09-28）—— 沒裝 toml 時用這一份
#: （有裝時 `test_recorded_messages_match_real_toml` 逐字核對，錄的跟真的不一樣就紅）。
_TOML_DUP_RECORDED = (
    "What? gcp_service_account already exists?{'GEMINI_API_KEY': 'AIzaSyTomlR12AbCdEfGhIjKlMnOpQrStUv', "
    "'gcp_service_account': {'type': 'service_account', 'project_id': 'proj-r12-toml', "
    "'private_key_id': 'pkidR12toml', 'private_key': '-----BEGIN PRIVATE KEY-----\\nMIIEvR12toml\\n"
    "-----END PRIVATE KEY-----\\n', 'client_email': 'svc-r12@proj-r12-toml.iam.gserviceaccount.com', "
    "'client_id': '109876543210987654321', 'my_api_pw': 'hunter2customR12'}} (line 11 column 1 char 380)")
#: dict 裡的值（`client_email`／`project_id`／`client_id`／自訂欄位 `my_api_pw` 不在秘密欄位清單上）。
_TOML_LEAKS = ("proj-r12-toml", "svc-r12@", "109876543210987654321", "hunter2customR12", "pkidR12toml",
               "MIIEvR12toml", "AIzaSyTomlR12")
#: 其他種類的 toml 0.10.2 錯誤（不帶已解析內容）：(觸發文件, 逐字錄下的 `str(e)`)。
_TOML_OTHER = {
    "dup_keys": ("a = 1\na = 2\n", "Duplicate keys! (line 2 column 1 char 6)"),
    "unbalanced": ('token = "abc\n', "Unbalanced quotes (line 1 column 13 char 12)"),
    "bad_group": ("[a b]\nx = 1\n", "Invalid group name 'a b'. Try quoting it. (line 1 column 1 char 0)"),
    "no_value": ("justakey\n", "Key name found without value. Reached end of line. (line 1 column 9 char 8)"),
}
#: 使用者會怎麼貼：traceback 最後一行、只貼型別名＋訊息、冒號前有空白、夾在問句／回答裡、整段 traceback。
_TOML_WRAPS = (
    "toml.decoder.TomlDecodeError: {}",
    "TomlDecodeError : {}",
    "為什麼出現 toml.decoder.TomlDecodeError: {}，怎麼解？",
    "你看到的是 TomlDecodeError: {}。解法：刪掉重複的 [gcp_service_account] 表。",
    "Traceback (most recent call last):\n  File \"app.py\", line 9, in <module>\ntoml.decoder.TomlDecodeError: {}",
)
_TOML_CUT_MUT = ('    out = _TOML_DUP_TABLE_DICT_RE.sub(r"\\1", out)\n', "")


def _toml_message(doc: str, recorded: str) -> str:
    """有裝 toml → 真的 `toml.loads(doc)` 拿 `str(e)`；沒裝 → 逐字錄下的那一份。"""
    try:
        import toml
    except ImportError:
        return recorded
    try:
        toml.loads(doc)
    except toml.TomlDecodeError as e:
        return str(e)
    raise AssertionError("前提：這份 TOML 應該讓 toml.loads 拋錯")


def _assert_toml_dup_dict_is_cut(fn) -> None:
    """（被突變測試重用）重複表錯誤的每一種貼法：從大括號起全部拿掉（前面的問句、型別名、表名照留）。"""
    msg = _toml_message(_TOML_DOC, _TOML_DUP_RECORDED)
    assert "already exists?{" in msg, "前提：真的是重複表錯誤、而且串了 dict"
    for wrap in _TOML_WRAPS:
        for m in (msg, msg.replace("What? ", "What?\n", 1)):     # 第二種：終端機把長行折在表名前
            x = wrap.format(m)
            out = fn(x)
            assert out == x[:x.index(_TOML_EXISTS) + len(_TOML_EXISTS)], (wrap[:30], out[-150:])
            assert not [leak for leak in _TOML_LEAKS if leak in out], out[-150:]


class TestTomlDuplicateTableHardening:
    def test_recorded_messages_match_real_toml(self):
        toml = pytest.importorskip("toml")
        with pytest.raises(toml.TomlDecodeError) as ei:
            toml.loads(_TOML_DOC)
        assert str(ei.value) == _TOML_DUP_RECORDED
        for name, (doc, recorded) in _TOML_OTHER.items():
            with pytest.raises(toml.TomlDecodeError) as ei:
                toml.loads(doc)
            assert str(ei.value) == recorded, name

    def test_premise_error_scrubber_cut_it_and_prose_without_the_hardening_leaks(self):
        """修前實況（批 Q QA 重現）：錯誤字串那支（＝ `7020d13` v2 問答用的）整段截；散文版拿掉加固 → dict 的值外露。"""
        x = f"toml.decoder.TomlDecodeError: {_toml_message(_TOML_DOC, _TOML_DUP_RECORDED)}"
        assert scrub_secrets(x) == "toml.decoder.TomlDecodeError"
        leaked = {leak for leak in _TOML_LEAKS if leak in _mutant(SSC, _TOML_CUT_MUT).scrub_prose_secrets(x)}
        assert leaked >= {"proj-r12-toml", "svc-r12@", "109876543210987654321", "hunter2customR12"}, leaked

    def test_the_whole_parsed_dict_is_cut_in_prose_and_markdown(self):
        _assert_toml_dup_dict_is_cut(scrub_prose_secrets)
        _assert_toml_dup_dict_is_cut(scrub_qa_text)

    @pytest.mark.parametrize("name", sorted(_TOML_OTHER))
    def test_other_toml_errors_quoted_in_prose_are_kept_whole(self, name):
        """反例：其他 toml 錯誤（不帶已解析內容）照舊只走散文版 —— 一個字都不截。"""
        msg = _toml_message(*_TOML_OTHER[name])
        for x in (f"為什麼出現 TomlDecodeError: {msg}，怎麼解？", f"toml.decoder.TomlDecodeError: {msg}"):
            assert scrub_prose_secrets(x) == x
            assert scrub_secrets(x) != x, "前提：錯誤字串那支會截"

    @pytest.mark.parametrize("x", [
        "TomlDecodeError: What? g already exists? 這是什麼意思",           # 沒有大括號
        "TomlDecodeError: What? g already exists? 我該刪掉 {重複的} 表嗎",  # 大括號前面不只空白
        f"{_UDE}: What? g already exists?{{'g': 1}}",                     # 不是 TomlDecodeError
    ])
    def test_other_prose_is_not_affected(self, x):
        assert scrub_prose_secrets(x) == x

    @pytest.mark.parametrize("x", [
        "What? g already exists?{'g': {'client_email': 'z@y'}}",                           # 沒帶型別名
        "TomlDecodeError: What? g already\n exists?{'g': {'client_email': 'z@y'}}",        # 折行拆開了關鍵字
        "TomlDecodeError: " + "x" * 513 + "already exists?{'g': {'client_email': 'z@y'}}",  # 超過 512 字
        "TomlDecodeError: What? g already exists?     {'g': {'client_email': 'z@y'}}",     # 大括號前 5 個空白
    ])
    def test_documented_boundaries_are_not_cut(self, x):
        """據實揭露：這幾種形狀 ⛔ 不截（見 `_TOML_DUP_TABLE_DICT_RE` 註解）；沒帶型別名那一種 `scrub_secrets` 也不截。"""
        assert "{'g'" in scrub_prose_secrets(x)
        assert scrub_prose_secrets(x) == _expected_prose(x)

    def test_matches_the_independent_implementation(self):
        """產品 regex 與 `_oracle_toml_cut`（逐字元掃描的獨立實作）在邊界與隨機組合上逐字相同。"""
        rnd = random.Random(20260929)
        atoms = [_TOML_NAME, ":", " ", "\t", "\n", _TOML_EXISTS, "{", "}", "What? g ", "x" * 97, "y", "'",
                 "already exists", "?", _UDE, "(", "TomlDecode", "：", "　"]
        cases = ["".join(rnd.choice(atoms) for _ in range(rnd.randint(1, 14))) for _ in range(5000)]
        for gap in (0, 1, 511, 512, 513):
            for ws in ("", " ", "\t\n", "    ", "     ", "　"):
                cases.append(f"{_TOML_NAME}:{'z' * gap}{_TOML_EXISTS}{ws}{{'k': 'v'}} tail")
                cases.append(f"{_TOML_NAME} \t:{'z' * gap}{_TOML_EXISTS}{ws}{{")
        for x in cases:
            assert SSC._TOML_DUP_TABLE_DICT_RE.sub(r"\1", x) == _oracle_toml_cut(x), repr(x[:120])

    def test_the_rule_is_pinned(self):
        r = SSC._TOML_DUP_TABLE_DICT_RE
        assert r.pattern == r"(TomlDecodeError[ \t]*:.{0,512}?already exists\?\s{0,4})\{.*"
        assert r.flags & re.DOTALL and SSC._TOML_DUP_GAP_MAX == _TOML_GAP_MAX


# ══════════════════════════════════════════════════════════════════
# 2. 引用的錯誤訊息裡夾金鑰／路徑／帳密：其餘規則照遮
#    （`_LEAKY` 扣掉只靠散文形擋的 3 筆，其餘每一筆逐一嵌進三種散文形）
# ══════════════════════════════════════════════════════════════════
_EMBED = (
    "為什麼出現 UnicodeDecodeError: {} 怎麼解？",
    "你看到的是 TomlDecodeError: {}。解法：重新產生 secrets.toml。",
    "UnicodeEncodeError : {}",
)


@pytest.mark.parametrize("wrap", _EMBED, ids=["q", "a", "bare"])
@pytest.mark.parametrize("case", sorted(set(_LEAKY) - _COLON_FIRST_LEAKY))
def test_secrets_quoted_inside_the_colon_form_are_still_masked(case, wrap):
    raw, gone, kept = _LEAKY[case]
    x = wrap.format(raw)
    out = scrub_prose_secrets(x)
    assert out.startswith(wrap.split("{}")[0]), f"散文形被截了：{out[:120]!r}"
    for g in gone:
        assert g not in out, (case, out)
    for k in kept:
        assert k in out, (case, k, out)
    assert scrub_prose_secrets(x) == _expected_prose(x)


# ══════════════════════════════════════════════════════════════════
# 3. ⭐ 少遮的確切範圍（只限第 1 類散文形）—— 其他規則一條不少
# ══════════════════════════════════════════════════════════════════
_SWAP = ("(_CONTENT_BEARING_EXC_REPR_RE if _re is _CONTENT_BEARING_EXC_RE else _re).sub(_rep, out)",
         "_re.sub(_rep, out)")
#: 批 Q QA 加固那一行（toml 重複表）—— 以同一段原始碼解析後的正規形式比對，不手寫跳脫。
_TOML_CUT_STMT = ast.unparse(ast.parse('out = _TOML_DUP_TABLE_DICT_RE.sub(r"\\1", out)').body[0])


def _stmts(fn) -> list[str]:
    node = ast.parse(textwrap.dedent(inspect.getsource(fn))).body[0]
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return [ast.unparse(s) for s in body]


@functools.lru_cache(maxsize=1)
def _fast_results() -> tuple[tuple[str, str, str], ...]:
    """（原文, 散文版, 錯誤字串版）—— S2 語料（含所有 `scrub` 測試檔的字串常值）＋ fuzz ＋ `_LEAKY` ＋ `_PLAIN`。"""
    corpus = (set(_s2_corpus()) | {s for s in _fuzz_corpus() if isinstance(s, str)}
              | {r for r, *_ in _LEAKY.values()} | set(_PLAIN))
    return tuple((x, scrub_prose_secrets(x), scrub_secrets(x))
                 for x in sorted(corpus) if not _has_sentinel(x))


@functools.lru_cache(maxsize=1)
def _augmented() -> tuple[str, ...]:
    """刻意造出的散文形輸入：散文形放在開頭／中間／結尾、前後夾 repr 形、夾在中文句子裡。"""
    rnd = random.Random(20260928)
    base = sorted({r for r, *_ in _LEAKY.values()} | set(_PLAIN))
    base += rnd.sample(sorted(x for x, _p, _s in _fast_results()), 600)
    out: set[str] = set()
    for b in base:
        h = len(b) // 2
        out.update({
            "UnicodeDecodeError: " + b, f"為什麼出現 UnicodeEncodeError : {b} 怎麼解？",
            b + " TomlDecodeError: x", b[:h] + "TomlDecodeError:" + b[h:],
            f"UnicodeTranslateError\t: a {b} UnicodeDecodeError('utf-8', b'password = \"zz\"')",
            # toml 重複表形狀（批 Q QA 加固）：型別名之後夾著 b、跨行、大括號前有空白
            f"TomlDecodeError: What? {b[:40]} already exists?{{'k': '{b}'}}",
            f"{b} toml.decoder.TomlDecodeError: What? t already exists?\n {{'k': '{b}'}} 怎麼辦",
        })
    return tuple(sorted(x for x in out if not _has_sentinel(x)))


class TestExactScope:
    def test_repr_only_rule_is_rule_one_narrowed_to_the_paren(self):
        """散文版那條 ＝ 第 1 類那條只把 `[(:]` 收窄成左括號（推導失效 → 這裡紅，不會靜默變回全截）。"""
        old, new = SSC._CONTENT_BEARING_EXC_RE, SSC._CONTENT_BEARING_EXC_REPR_RE
        assert old.pattern == r"(Unicode(?:Decode|Encode|Translate)Error|TomlDecodeError)[ \t]*[(:].*"
        assert new.pattern == r"(Unicode(?:Decode|Encode|Translate)Error|TomlDecodeError)[ \t]*\(.*"
        assert new.pattern == old.pattern.replace("[(:]", r"\(") and new.flags == old.flags
        assert new.flags & re.DOTALL
        assert [r for r, _rep in SSC._RULES].count(old) == 1, "被替換的那一條要真的在規則表裡、而且只有一條"

    def test_prose_pipeline_is_scrub_secrets_with_one_rule_swapped_plus_the_toml_cut(self):
        """AST：散文版的函式體 ＝ `scrub_secrets` 的函式體，只有第 1 圈迴圈裡那一個 regex 換掉，
        外加**恰好一行**批 Q QA 加固（toml 重複表），而且排在第 1 圈迴圈**之前**。

        日後 `scrub_secrets` 多加一個步驟（新迴圈／新呼叫）而散文版沒跟上 → 這裡紅（其他規則一條不少）。
        """
        old, new = _stmts(scrub_secrets), _stmts(scrub_prose_secrets)
        assert new.count(_TOML_CUT_STMT) == 1
        loop = next(i for i, s in enumerate(new) if s.startswith("for _re, _rep in _RULES:"))
        assert new.index(_TOML_CUT_STMT) < loop, "toml 加固要在第 1 類之前跑"
        rest = [s for s in new if s != _TOML_CUT_STMT]
        assert sum(_SWAP[0] in s for s in rest) == 1
        assert [s.replace(*_SWAP) for s in rest] == old

    def test_identical_to_scrub_secrets_unless_the_first_hit_is_the_colon_form(self):
        rows = _fast_results()
        assert len(rows) > 10_000, "語料不該是空的"
        diff = [x for x, p, s in rows if not _colon_first(x) and p != s]
        assert not diff, [d[:100] for d in diff[:5]]
        assert sum(_colon_first(x) for x, _p, _s in rows) >= 5, "語料裡要真的有散文形（防空轉）"

    def test_prose_equals_scrub_secrets_with_the_colon_form_defused(self):
        """蛻變關係：散文版 ＝ `scrub_secrets` 把散文形的型別名當成普通字 —— 少遮的就只有「那個型別名不再觸發截斷」。"""
        bad = [x for x, p, s in _fast_results()
               if p != (s if _defuse(x) == x and _oracle_toml_cut(x) == x else _expected_prose(x))]
        bad += [x for x in _augmented() if scrub_prose_secrets(x) != _expected_prose(x)]
        assert not bad, [b[:100] for b in bad[:5]]
        assert sum(_colon_first(x) for x in _augmented()) > 2000

    @pytest.mark.parametrize("case", sorted(_COLON_FIRST_LEAKY - {"toml_colon_form"}))
    def test_scope_a_the_colon_form_tail_is_left_to_the_other_rules(self, case):
        """據實揭露 (a)：`_LEAKY` 裡只靠第 1 類散文形擋的筆數中，**不是** toml 重複表形狀的兩筆：
        後文沒有任何其他規則命中 → 散文版原樣留著。"""
        raw, gone, _kept = _LEAKY[case]
        assert all(g not in scrub_secrets(raw) for g in gone), "錯誤字串那支照舊擋"
        assert scrub_prose_secrets(raw) == raw

    def test_scope_a_the_toml_duplicate_table_sample_is_cut_by_the_hardening(self):
        """`_LEAKY["toml_colon_form"]` 正是 toml 重複表形狀 → 批 Q QA 加固從大括號起截掉（dict 裡的值不外露）。"""
        raw, gone, _kept = _LEAKY["toml_colon_form"]
        out = scrub_prose_secrets(raw)
        assert out == "TomlDecodeError: What? g already exists?"
        assert not [g for g in gone if g != "What?" and g in out]

    @pytest.mark.parametrize("x,leak", [
        # 與型別名黏在一起、合計超過 256 字上限的權杖串
        (f"password: no {'a1' * 100}{_UDE}:{'b2' * 40} end", "a1" * 100),
        # `no`／`not` 後面緊黏型別名的純字母（批 Q QA 補）
        (f"password: no hunter{_UDE}: 'utf-8' codec can't decode", "hunter"),
        (f"api_key: not hunter{_TOML_NAME}: x", "hunter"),
    ])
    def test_scope_b_text_glued_to_the_type_name(self, x, leak):
        """據實揭露 (b)：原本靠「字串在型別名處結束」才遮到的前文，散文版不遮（兩種例子，docstring 同列）。"""
        assert leak not in scrub_secrets(x)
        assert leak in scrub_prose_secrets(x)
        assert scrub_prose_secrets(x) == _expected_prose(x)

    def test_scope_b_a_space_before_the_type_name_keeps_it_masked(self):
        """反例：否定片語與型別名之間有空白 → 兩支都遮到 `no hunter`（(b) 只限緊黏）。"""
        x = f"password: no hunter {_UDE}: x"
        assert "hunter" not in scrub_secrets(x) and "hunter" not in scrub_prose_secrets(x)

    def test_scope_streamlit_parse_message_is_still_cut(self):
        """第 1 類的另一條（Streamlit 解析錯誤）散文版**照舊截斷**（沒有散文形可放；本批不放寬）。"""
        raw = _LEAKY["streamlit_parse_msg"][0]
        assert scrub_prose_secrets(raw) == scrub_secrets(raw) == "Error parsing secrets file"
        assert scrub_prose_secrets(f"為什麼出現 {raw}？") == "為什麼出現 Error parsing secrets file"


@pytest.mark.slow
def test_full_ui_and_secret_corpus_identical_or_defused_equal():
    """（slow lane：單測超過 5 秒）S3 的完整語料（`src/`、`shared/`、`app.py` 全部字串常值 ＋ 秘密語料）。"""
    from tests.test_sec_s3_0928 import _secret_corpus, _ui_corpus

    bad = []
    for x in sorted(x for x in (_ui_corpus() | _secret_corpus()) if not _has_sentinel(x)):
        p, s = scrub_prose_secrets(x), scrub_secrets(x)
        if (not _colon_first(x) and p != s) or p != (
                s if _defuse(x) == x and _oracle_toml_cut(x) == x else _expected_prose(x)):
            bad.append(x)
    assert not bad, [b[:100] for b in bad[:5]]


# ══════════════════════════════════════════════════════════════════
# 4. L0 `scrub_qa_text`（Markdown 版）：下沉、v2 行為不變（散文形以外）
# ══════════════════════════════════════════════════════════════════
class TestQaTextMarkdown:
    def test_no_hit_is_verbatim_hit_escapes_only_the_masks(self):
        assert scrub_qa_text(_CLEAN_A) == _CLEAN_A, "沒命中 → 逐字（`***粗斜體***` 不跳脫）"
        assert scrub_qa_text(_Q_ERR) == _Q_ERR
        assert scrub_qa_text(_Q_ERR_SECRET) == _Q_ERR_SECRET_WANT.replace(MASK, _ESC_MASK)
        assert scrub_qa_text(None) == "" and scrub_qa_text("") == ""

    def test_equals_the_old_v2_helper_on_every_input_without_the_colon_form(self):
        """下沉前 `page_why.scrub_qa_text` ＝ `x if scrub_secrets(x) == x else scrub_md_mask(x)`：
        散文形以外的輸入，新舊逐字相同（v2 行為不變）。"""
        for x in sorted({r for r, *_ in _LEAKY.values()} | set(_PLAIN)
                        | {s for s in _fuzz_corpus() if isinstance(s, str)}):
            if _colon_first(x):
                continue
            old = x if scrub_secrets(x) == x else scrub_md_mask(x)
            assert scrub_qa_text(x) == old, x[:100]

    def test_v2_uses_the_l0_helper_and_does_not_keep_a_copy(self):
        from src.ui.views import page_why as PW

        assert PW.scrub_qa_text is SMD.scrub_qa_text
        assert "def scrub_qa_text" not in pathlib.Path(PW.__file__).read_text(encoding="utf-8")

    def test_v1_does_not_import_the_v2_view_layer(self):
        """v1 L5 ⛔ 不得 import v2 view 模組；清洗函式從 L0 取。"""
        tree = ast.parse((_ROOT / "src/ui/tabs/tab_ai_chat.py").read_text(encoding="utf-8"))
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        mods |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not {m for m in mods if m and m.startswith(("src.ui.views", "src.ui_v2"))}, mods
        imported = {(n.module, a.name) for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
        assert {("shared.secret_md", "scrub_qa_text"), ("shared.secret_scrub", "scrub_prose_secrets")} <= imported


# ══════════════════════════════════════════════════════════════════
# 5. v2 `page_why`：送出／畫面／紀錄三處 ＋ AI 回答
# ══════════════════════════════════════════════════════════════════
def _render_qa_on(mod: types.ModuleType, monkeypatch, fake: _FakeChatST) -> None:
    """同 `test_p05_why_view._render_qa`，但可指定模組（突變版用）。"""
    monkeypatch.setattr(mod, "st", fake)
    monkeypatch.setattr(mod, "section_header", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "_render_one", lambda *_a, **_k: None)
    mod._render_qa_leaf(fake.session_state)


def _v2_user_history(mod, fake) -> list[str]:
    return [m["content"] for m in fake.session_state.get(mod.SS_QA_HISTORY, []) if m.get("role") == "user"]


def _assert_v2_question_kept(mod, monkeypatch) -> None:
    """（被突變測試重用）引用錯誤訊息的提問：送出／畫面／紀錄三處都完整；夾在裡面的秘密三處都遮。"""
    for q, sent_want, shown_want in ((_Q_ERR, _Q_ERR, _Q_ERR),
                                     (_Q_ERR_SECRET, _Q_ERR_SECRET_WANT,
                                      _Q_ERR_SECRET_WANT.replace(MASK, _ESC_MASK))):
        calls = _capture_agent(monkeypatch)
        fake = _FakeChatST(typed=q)
        _render_qa_on(mod, monkeypatch, fake)
        assert [c["question"] for c in calls] == [sent_want], "送出"
        assert shown_want in fake.drawn, "畫面"
        assert _v2_user_history(mod, fake) == [shown_want], "紀錄"
        for leak in (_LEAKS_Q if q is _Q_ERR_SECRET else ()):
            assert all(leak not in t for t in (calls[0]["question"], *fake.drawn, *_v2_user_history(mod, fake)))


class TestV2PageWhy:
    def test_error_quoting_question_is_whole_in_all_three_places(self, monkeypatch):
        from src.ui.views import page_why as PW

        _assert_v2_question_kept(PW, monkeypatch)

    def test_the_answer_keeps_its_solution_and_masks_secrets(self, monkeypatch):
        from src.ui.views import page_why as PW

        for answer, want in ((_A_ERR, _A_ERR),
                             (_A_ERR + f" 你貼的 password: {_PW}", _A_ERR + f" 你貼的 password: {_ESC_MASK}")):
            fake = _FakeChatST(typed="怎麼了？")
            _fake_agent(monkeypatch, text=answer)
            _render_qa(monkeypatch, fake)
            body = PW.compose_qa_message(want)
            assert body in fake.drawn
            assert fake.session_state[PW.SS_QA_HISTORY][-1]["content"] == body
            assert _PW not in "\n".join(fake.drawn)

    def test_repr_form_question_is_still_cut_in_all_three_places(self, monkeypatch):
        from src.ui.views import page_why as PW

        calls = _capture_agent(monkeypatch)
        fake = _FakeChatST(typed=f"這是什麼？{_REPR}")
        _render_qa_on(PW, monkeypatch, fake)
        want = f"這是什麼？{_UDE}"
        assert [c["question"] for c in calls] == [want]
        assert want in fake.drawn and _v2_user_history(PW, fake) == [want]
        assert _REPR_SECRET not in "\n".join(fake.drawn)

    def test_clean_question_is_byte_identical_everywhere(self, monkeypatch):
        from src.ui.views import page_why as PW

        calls = _capture_agent(monkeypatch)
        fake = _FakeChatST(typed=_CLEAN_Q)
        _render_qa_on(PW, monkeypatch, fake)
        assert [c["question"] for c in calls] == [_CLEAN_Q]
        assert _v2_user_history(PW, fake) == [_CLEAN_Q] and _CLEAN_Q in fake.drawn

    def test_pasted_toml_duplicate_table_error_is_cut_in_all_three_places(self, monkeypatch):
        """批 Q QA 加固：貼 toml 重複表錯誤發問 → 送出／畫面／紀錄都截在大括號前，dict 裡的值一個都不外露。"""
        from src.ui.views import page_why as PW

        x = f"為什麼出現 toml.decoder.TomlDecodeError: {_toml_message(_TOML_DOC, _TOML_DUP_RECORDED)}，怎麼解？"
        head = x[:x.index(_TOML_EXISTS) + len(_TOML_EXISTS)]
        calls = _capture_agent(monkeypatch)
        fake = _FakeChatST(typed=x)
        _render_qa_on(PW, monkeypatch, fake)
        assert [c["question"] for c in calls] == [head]
        assert head in fake.drawn and _v2_user_history(PW, fake) == [head]
        blob = "\n".join([*fake.drawn, calls[0]["question"], *_v2_user_history(PW, fake)])
        assert not [leak for leak in _TOML_LEAKS if leak in blob]


# ══════════════════════════════════════════════════════════════════
# 6. v1 `tab_ai_chat.render`：AppTest ＋ 假 `run_agent`
# ══════════════════════════════════════════════════════════════════
#: 假 `run_agent`：記下每一次送出的 question 與 history（深拷貝），回一則固定的回答。
#: `_ac_mod` 有值時改跑那個模組（突變版；由測試先登記進 `sys.modules`）。
_V1_SCRIPT = """
import importlib
import types

import streamlit as st

AC = importlib.import_module(st.session_state.get("_ac_mod") or "src.ui.tabs.tab_ai_chat")


def _fake_run_agent(question, history=None, **kw):
    st.session_state.setdefault("_calls", []).append(
        {"question": question, "history": [dict(_m) for _m in (history or [])], "kw": sorted(kw)})
    return types.SimpleNamespace(ok=True, text=st.session_state.get("_answer", ""), model="fake-model",
                                 tool_calls=[], error=None)


_saved = AC.run_agent
AC.run_agent = _fake_run_agent
try:
    AC.render()
finally:
    AC.run_agent = _saved
"""
_V1_HEAD = "### 🧬 AI 解讀｜使用模型:fake-model\n\n"
_V1_KEY = "AIzaSyR11vOneAbCdEfGhIjKlMnOpQrSt"
_V1_PW = "pwR11v1zz"
_V1_USER = "aliceR11"
_V1_TOKEN = "ya29.a0AfH6SMBR11tokenXYZabcdef"
_V1_Q = f"我的金鑰 {_V1_KEY}、password: {_V1_PW}、檔案在 /home/{_V1_USER}/app/.streamlit/secrets.toml，怎麼設定？"
_V1_A = (f"**結論**：請改用環境變數。你貼的 token {_V1_TOKEN} 不要外流；"
         f"設定檔 /home/{_V1_USER}/x/secrets.toml 裡的 password: {_V1_PW} 也要換掉。")
_V1_LEAKS = (_V1_KEY, _V1_PW, _V1_USER, _V1_TOKEN, "/home/")


def _v1_app(monkeypatch, tmp_path, *, answer: str, mod: str | None = None):
    from streamlit.testing.v1 import AppTest

    # 金鑰走環境變數（`_secret` 先看 st.secrets、再看環境變數）；monkeypatch 收尾時還原，
    # `_bridge_secrets_to_env` 的 setdefault 因此不會把值留在這個 process 裡。
    monkeypatch.setenv("GEMINI_API_KEY", "k-test-sec-r11")
    monkeypatch.setenv("FINMIND_TOKEN", "")
    script = tmp_path / "_sec_r11_v1_chat.py"
    script.write_text(_V1_SCRIPT, encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=60)
    at.session_state["_answer"] = answer
    if mod:
        at.session_state["_ac_mod"] = mod
    at.run()
    assert not at.exception, at.exception
    return at


def _ask(at, question: str):
    at.chat_input[0].set_value(question).run()
    assert not at.exception, at.exception
    return at


def _calls(at) -> list[dict]:
    try:
        return list(at.session_state["_calls"])
    except KeyError:
        return []


def _history(at) -> list[dict]:
    return [dict(m) for m in at.session_state["ai_qa_history"]]


def _screen(at) -> list[str]:
    return [m.value for m in at.markdown]


def _v1_secret_flow(monkeypatch, tmp_path, mod: str | None = None):
    """問一題含秘密的、AI 回一則含秘密的，再問第二題
    → (第一輪紀錄, 第一題之後的畫面, 全部送出, 最後的畫面, 最後的紀錄)。"""
    at = _v1_app(monkeypatch, tmp_path, answer=_V1_A, mod=mod)
    assert _calls(at) == [], "還沒問 → 一次都不送（「這一輪有沒有問」以原文判斷）"
    _ask(at, _V1_Q)
    first, screen1 = _history(at), _screen(at)
    _ask(at, "第二題：那 2330 呢？")
    return first, screen1, _calls(at), _screen(at), _history(at)


def _assert_v1_all_scrubbed(first, screen1, calls, screen, history) -> None:
    """（被突變測試重用）送出的提問、兩輪的畫面、紀錄、下一題隨 history 再送的內容：一個秘密都不外露。

    ⚠️ 第一題之後的畫面要**單獨**看（批 Q QA）：那一輪的提問與回答是「本輪剛畫」的，第二輪起畫面上的
    是從紀錄重播的 —— 只看最後的畫面，「本輪剛畫時用原文、紀錄照洗」這種外露會漏掉。
    """
    assert len(calls) == 2
    sent = calls[0]["question"]
    assert sent == scrub_prose_secrets(_V1_Q) and MASK in sent and "\\*" not in sent, "送出：純文字版散文清洗"
    assert first[0] == {"role": "user", "content": scrub_qa_text(_V1_Q)}, "紀錄：Markdown 版散文清洗"
    assert first[1] == {"role": "assistant", "content": _V1_HEAD + scrub_qa_text(_V1_A)}, "紀錄：回答也洗"
    assert calls[1]["history"] == first, "下一題隨 history 送出的就是洗過的紀錄"
    assert first[0]["content"] in screen1 and first[1]["content"] in screen1, "第一題之後的畫面（本輪剛畫）"
    assert first[0]["content"] in screen and first[1]["content"] in screen, "第二題之後的畫面（重播）"
    blob = json.dumps({"calls": calls, "screen1": screen1, "screen": screen, "history": history},
                      ensure_ascii=False)
    for leak in _V1_LEAKS:
        assert leak not in blob, f"秘密 {leak!r} 外露"


class TestV1AiChat:
    def test_question_answer_and_resent_history_are_scrubbed(self, monkeypatch, tmp_path):
        _assert_v1_all_scrubbed(*_v1_secret_flow(monkeypatch, tmp_path))

    def test_error_quoting_question_and_answer_are_not_cut(self, monkeypatch, tmp_path):
        at = _v1_app(monkeypatch, tmp_path, answer=_A_ERR)
        _ask(at, _Q_ERR)
        _ask(at, _Q_ERR_SECRET)
        calls, hist = _calls(at), _history(at)
        assert [c["question"] for c in calls] == [_Q_ERR, _Q_ERR_SECRET_WANT]
        assert [m["content"] for m in hist] == [_Q_ERR, _V1_HEAD + _A_ERR,
                                                _Q_ERR_SECRET_WANT.replace(MASK, _ESC_MASK), _V1_HEAD + _A_ERR]
        assert _Q_ERR in _screen(at) and _V1_HEAD + _A_ERR in _screen(at)
        blob = json.dumps({"calls": calls, "screen": _screen(at), "history": hist}, ensure_ascii=False)
        assert not [leak for leak in _LEAKS_Q if leak in blob]

    def test_clean_question_and_answer_are_byte_identical(self, monkeypatch, tmp_path):
        at = _v1_app(monkeypatch, tmp_path, answer=_CLEAN_A)
        _ask(at, _CLEAN_Q)
        assert [c["question"] for c in _calls(at)] == [_CLEAN_Q]
        assert [m["content"] for m in _history(at)] == [_CLEAN_Q, _V1_HEAD + _CLEAN_A]
        assert _CLEAN_Q in _screen(at) and _V1_HEAD + _CLEAN_A in _screen(at)

    def test_run_agent_call_shape_is_unchanged(self, monkeypatch, tmp_path):
        """只換 question 的內容：history 仍是「本次問題之前」的快照、只帶 `api_key`（⛔ 不帶新旗標）。"""
        at = _v1_app(monkeypatch, tmp_path, answer="偏強。")
        _ask(at, "6239 評分?")
        calls = _calls(at)
        assert [(c["question"], c["history"], c["kw"]) for c in calls] == [("6239 評分?", [], ["api_key"])]

    def test_pasted_toml_duplicate_table_error_is_cut(self, monkeypatch, tmp_path):
        """批 Q QA 加固（v1 端）：貼 toml 重複表錯誤發問 → 送出／畫面／紀錄都截在大括號前。"""
        x = f"為什麼出現 toml.decoder.TomlDecodeError: {_toml_message(_TOML_DOC, _TOML_DUP_RECORDED)}，怎麼解？"
        head = x[:x.index(_TOML_EXISTS) + len(_TOML_EXISTS)]
        at = _v1_app(monkeypatch, tmp_path, answer="請刪掉重複的表。")
        _ask(at, x)
        assert [c["question"] for c in _calls(at)] == [head]
        assert _history(at)[0]["content"] == head and head in _screen(at)
        blob = json.dumps({"calls": _calls(at), "screen": _screen(at), "history": _history(at)}, ensure_ascii=False)
        assert not [leak for leak in _TOML_LEAKS if leak in blob]


# ══════════════════════════════════════════════════════════════════
# 7. 突變驗證：拔掉每一個修法點 → 上面對應那一組斷言轉紅
# ══════════════════════════════════════════════════════════════════
_L0_SWAP_MUT = ("(_CONTENT_BEARING_EXC_REPR_RE if _re is _CONTENT_BEARING_EXC_RE else _re)", "_re")
_MD_MUT = ("    _out = scrub_prose_secrets(_raw)\n", "    _out = scrub_secrets(_raw)\n")
_V2_SEND_MUT = ("question=scrub_prose_secrets(_question)", "question=scrub_secrets(_question)")
_V2_SEND_RAW_MUT = ("question=scrub_prose_secrets(_question)", "question=_question")
_V2_SHOW_MUT = ("from shared.secret_md import scrub_qa_text\n",
                "from shared.secret_md import scrub_md_mask as scrub_qa_text\n")
_V1_MUTANTS = {
    # 送出前不洗（SEC-r11 原狀）
    "send_raw": ("res = run_agent(scrub_prose_secrets(q), _prior, api_key=key)",
                 "res = run_agent(q, _prior, api_key=key)"),
    # 送出改回錯誤字串那支（SEC-r12 原狀）
    "send_error_scrubber": ("from shared.secret_scrub import scrub_prose_secrets\n",
                            "from shared.secret_scrub import scrub_secrets as scrub_prose_secrets\n"),
    # 畫面／紀錄不洗
    "shown_raw": ("    _shown_q = scrub_qa_text(q)\n", "    _shown_q = q\n"),
    # AI 回答不洗
    "answer_raw": ('_text = scrub_qa_text((res.text or "").strip())', '_text = (res.text or "").strip()'),
    # 只有「本輪剛畫」的那一次用原文、紀錄照洗（批 Q QA 突變 ML／MP 一類：修前各只被 1 條測試附帶抓到）
    "screen_only_raw_q": ("        st.markdown(_shown_q)\n", "        st.markdown(q)\n"),
    "screen_only_raw_a": ("        st.markdown(body)\n",
                          '        st.markdown(f"### 🧬 AI 解讀｜使用模型:{res.model}\\n\\n{res.text}" '
                          "if res.ok else body)\n"),
}


def _v1_mutant(monkeypatch, key: str) -> str:
    import src.ui.tabs.tab_ai_chat as AC

    m = _mutant(AC, _V1_MUTANTS[key])
    monkeypatch.setitem(sys.modules, m.__name__, m)
    return m.__name__


class TestMutants:
    def test_c_l0_prose_back_to_the_error_scrubber_cuts_again(self):
        m = _mutant(SSC, _L0_SWAP_MUT)
        assert m.scrub_prose_secrets(_Q_ERR) == f"為什麼出現 {_UDE}"
        with pytest.raises(AssertionError):
            _assert_prose_keeps_the_colon_form(m.scrub_prose_secrets)

    def test_c_l0_markdown_helper_back_to_the_error_scrubber_cuts_again(self):
        m = _mutant(SMD, _MD_MUT)
        assert m.scrub_qa_text(_A_ERR) == f"你看到的是 {_UDE}"

    def test_c_v2_send_back_to_the_error_scrubber_cuts_the_question(self, monkeypatch):
        from src.ui.views import page_why as PW

        with pytest.raises(AssertionError, match="送出"):
            _assert_v2_question_kept(_mutant(PW, _V2_SEND_MUT), monkeypatch)

    def test_c_v2_screen_back_to_the_error_scrubber_cuts_the_question(self, monkeypatch):
        from src.ui.views import page_why as PW

        with pytest.raises(AssertionError, match="畫面"):
            _assert_v2_question_kept(_mutant(PW, _V2_SHOW_MUT), monkeypatch)

    def test_c_v2_sending_the_raw_question_is_caught(self, monkeypatch):
        """「送原文」的退回（S2-f3 之前的狀態）→ 送出那一條轉紅。"""
        from src.ui.views import page_why as PW

        with pytest.raises(AssertionError, match="送出"):
            _assert_v2_question_kept(_mutant(PW, _V2_SEND_RAW_MUT), monkeypatch)

    def test_c_l0_dropping_the_toml_cut_leaks_the_parsed_dict(self):
        """批 Q QA 加固拿掉 → 重複表錯誤的 dict 值外露，`_assert_toml_dup_dict_is_cut` 轉紅。"""
        m = _mutant(SSC, _TOML_CUT_MUT)
        with pytest.raises(AssertionError):
            _assert_toml_dup_dict_is_cut(m.scrub_prose_secrets)

    def test_c_v1_dropping_the_send_scrub_leaks_the_key(self, monkeypatch, tmp_path):
        flow = _v1_secret_flow(monkeypatch, tmp_path, _v1_mutant(monkeypatch, "send_raw"))
        assert _V1_KEY in flow[2][0]["question"], "突變版應把原文送出"
        with pytest.raises(AssertionError):
            _assert_v1_all_scrubbed(*flow)

    def test_c_v1_sending_with_the_error_scrubber_cuts_the_question(self, monkeypatch, tmp_path):
        at = _v1_app(monkeypatch, tmp_path, answer="偏強。", mod=_v1_mutant(monkeypatch, "send_error_scrubber"))
        _ask(at, _Q_ERR)
        assert [c["question"] for c in _calls(at)] == [f"為什麼出現 {_UDE}"], "突變版把提問截到只剩型別名"

    @pytest.mark.parametrize("key,where", [("shown_raw", _V1_KEY), ("answer_raw", _V1_TOKEN)])
    def test_c_v1_dropping_the_screen_or_answer_scrub_leaks(self, monkeypatch, tmp_path, key, where):
        first, screen1, calls, screen, history = _v1_secret_flow(monkeypatch, tmp_path, _v1_mutant(monkeypatch, key))
        assert where in json.dumps(first, ensure_ascii=False), "突變版應把秘密寫進紀錄"
        assert any(where in s for s in screen), "突變版應把秘密畫上畫面"
        assert where in json.dumps(calls[1]["history"], ensure_ascii=False), "下一題隨 history 再送一次"
        with pytest.raises(AssertionError):
            _assert_v1_all_scrubbed(first, screen1, calls, screen, history)

    @pytest.mark.parametrize("key,where", [("screen_only_raw_q", _V1_KEY), ("screen_only_raw_a", _V1_TOKEN)])
    def test_c_v1_raw_text_only_on_the_first_turns_screen_is_caught(self, monkeypatch, tmp_path, key, where):
        """批 Q QA：只在「本輪剛畫」時用原文、紀錄照洗 → 靠「第一題之後的畫面」那一條直接抓到。"""
        first, screen1, calls, screen, history = _v1_secret_flow(monkeypatch, tmp_path, _v1_mutant(monkeypatch, key))
        assert any(where in s for s in screen1), "突變版在第一題那一輪把原文畫上畫面"
        assert where not in json.dumps(first, ensure_ascii=False), "紀錄照洗（只有那一輪的畫面外露）"
        with pytest.raises(AssertionError, match="第一題之後的畫面"):
            _assert_v1_all_scrubbed(first, screen1, calls, screen, history)


# ══════════════════════════════════════════════════════════════════
# 8. ReDoS：散文版專屬的路徑（散文形開頭 ⇒ 後文不再被截、整段交給其他規則掃）
# ══════════════════════════════════════════════════════════════════
#: 沿用 `test_v2_silent_fail_b11_hold_misc` 的子程序守衛（逾時會點名卡住的那一組）。
_PROSE_REDOS_SCRIPT = (
    "import json, sys, time\n"
    "from shared.secret_md import scrub_qa_text\n"
    "from shared.secret_scrub import scrub_prose_secrets\n"
    "out = {}\n"
    "for name, text in json.load(sys.stdin):\n"
    f"    sys.stderr.write({_REDOS_START_TAG!r} + json.dumps(name) + '\\n')\n"
    "    sys.stderr.flush()\n"
    "    fn = scrub_qa_text if name.startswith('md ') else scrub_prose_secrets\n"
    "    t = time.perf_counter()\n"
    "    fn(text)\n"
    "    out[name] = time.perf_counter() - t\n"
    "print(json.dumps(out))\n")
_COLON_HEADS = ("UnicodeDecodeError: ", "TomlDecodeError: ", "UnicodeEncodeError\t: ", "UnicodeTranslateError :")
#: 只衝第 1 類散文版那條 regex 本身：大量型別名、型別名後大量空白卻沒有括號／冒號。
#: 後半是批 Q QA 加固（toml 重複表）那條：大量起點、每個起點都得往後看滿 512 字才放棄、關鍵字後面接一長串空白。
_RULE1_UNITS = ("UnicodeDecodeError: ", "UnicodeDecodeError ", "TomlDecodeError\t", "UnicodeDecodeError(",
                "UnicodeDecodeError" + " " * 50, "TomlDecodeError:a", "Error parsing secrets file ",
                "TomlDecodeError: ", "TomlDecodeError:\n", "TomlDecodeError:already exists?     ",
                "already exists?{", "TomlDecodeError \t:" + "x" * 600, "TomlDecodeError:" + " " * 520)
_N = 50_000


def test_prose_scrub_is_linear_on_adversarial_input():
    units = list(_ADVERSARIAL_UNITS) + list(_S2_REDOS_UNITS)
    cases = [[f"{i} {_COLON_HEADS[i % 4]!r}+{u!r}", _COLON_HEADS[i % 4] + _rep(u, _N)]
             for i, u in enumerate(units)]
    cases += [[f"p{i} {p!r}", _COLON_HEADS[i % 4] + p + _rep(u, _N)] for i, (p, u) in enumerate(_ADVERSARIAL_PREFIXED)]
    cases += [[f"r{i} {u!r}", _rep(u, _N)] for i, u in enumerate(_RULE1_UNITS)]
    cases += [[f"md {i} {u!r}", _COLON_HEADS[0] + _rep(u, _N)] for i, u in enumerate(("password: ", "'", " ~a/"))]
    times = _run_redos_cases(cases, script=_PROSE_REDOS_SCRIPT, timeout_s=45.0)
    assert set(times) == {c[0] for c in cases}
    slow = {k: round(v, 2) for k, v in times.items() if v > _REDOS_PER_CASE_S}
    assert not slow, slow
