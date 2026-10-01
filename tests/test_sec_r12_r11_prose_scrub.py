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
- **批 Q 獨立 QA 追加（2026-09-28）**：(1) **依型別分流** —— `TomlDecodeError` 的散文形照舊整段截（toml 0.10.2
  的訊息本身會串入內容：重複表錯誤串入已解析的整包 dict、數字轉換失敗帶出那一行的原始值），只有三種
  `Unicode*Error` 放寬為只截 repr 形（section 1b；有裝 `toml` 就用真的 `toml.loads`，沒有就用逐字錄下的字串）；
  先前的 toml 重複表專用加固因此移除；(2) 少遮邊界 (b) 補第二種例子；(3) v1 在第一題之後也斷言畫面。

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

#: `_LEAKY`（`test_v2_silent_fail_b11_hold_misc`）裡**只靠第 1 類 `Unicode*Error` 散文形**擋的那一筆 ——
#: 散文版刻意不截它（這就是散文版比 `scrub_secrets` 少遮的那一種，見 `TestExactScope`）。
#: ⚠️ 另兩筆只靠散文形擋的（`toml_colon_form`／`toml_wrapped_colon`）是 `TomlDecodeError` —— 依型別分流後
#:    散文版照舊整段截（批 Q QA），所以不在這裡。
_RELAXED_LEAKY = frozenset({"unicode_colon_form"})
_TOML_ONLY_COLON_LEAKY = frozenset({"toml_colon_form", "toml_wrapped_colon"})
_TOML_NAME = "TomlDecodeError"


# ══════════════════════════════════════════════════════════════════
# 工具：散文形「解除」＋還原（蛻變關係用）、突變載入
# ══════════════════════════════════════════════════════════════════
#: 放寬的散文形（三種 `Unicode*Error`＋可有空白／tab＋冒號）。清單與 `SSC._PROSE_RELAXED_EXC` 相同
#: （`test_prose_rule_is_rule_one_with_only_unicode_colon_form_relaxed` 把兩者都逐字釘住）。
#: ⚠️ ⛔ 不含 `TomlDecodeError` —— 它在散文版照截，蛻變關係裡也必須照截。
_COLON_FORM_RE = re.compile(r"(Unicode(?:Decode|Encode|Translate)Error)(?=[ \t]*:)")
#: 把型別名的第一個字母換成 `Q` —— 同樣是英文字母（其他規則的字元類別判斷完全一樣），但第 1 類認不得。
_DEFUSED: dict[str, str] = {
    "UnicodeDecodeError": "QnicodeDecodeError", "UnicodeEncodeError": "QnicodeEncodeError",
    "UnicodeTranslateError": "QnicodeTranslateError"}


def _defuse(x: str) -> str:
    return _COLON_FORM_RE.sub(lambda m: _DEFUSED[m.group(1)], x)


def _unmap(y: str) -> str:
    for _k, _v in _DEFUSED.items():
        y = y.replace(_v, _k)
    return y


def _has_sentinel(x: str) -> bool:
    return any(_v in x for _v in _DEFUSED.values())


def _relaxed_first(x: str) -> bool:
    """第一個命中第 1 類（`scrub_secrets` 那條）的位置是 `Unicode*Error` 的散文形 —— 兩支函式**唯一**可能不同的輸入。"""
    m = SSC._CONTENT_BEARING_EXC_RE.search(x)
    return m is not None and SSC._CONTENT_BEARING_EXC_PROSE_RE.match(x, m.start()) is None


def _expected_prose(x: str) -> str:
    """散文版的「應有輸出」：把 `Unicode*Error` 散文形的型別名當普通字交給 `scrub_secrets`（其餘一律照 `scrub_secrets`）。"""
    return _unmap(scrub_secrets(_defuse(x)))


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
        "UnicodeDecodeError: ", "UnicodeEncodeError : ", "UnicodeTranslateError\t:", "ValueError: UnicodeDecodeError: "])
    def test_every_unicode_type_and_spacing_of_the_colon_form_is_kept(self, head):
        x = f"為什麼出現 {head}codec can't decode 怎麼解？"
        assert scrub_prose_secrets(x) == x
        assert scrub_secrets(x) != x, "前提：錯誤字串那支會截"

    @pytest.mark.parametrize("head", ["TomlDecodeError:", "TomlDecodeError : ", "toml.decoder.TomlDecodeError: ",
                                      "ValueError: TomlDecodeError: "])
    def test_toml_colon_form_is_still_cut_like_the_error_scrubber(self, head):
        """依型別分流（批 Q QA）：`TomlDecodeError` 的散文形照舊整段截 —— 與 `scrub_secrets` 逐字相同。"""
        x = f"為什麼出現 {head}Duplicate keys 怎麼解？"
        assert scrub_prose_secrets(x) == scrub_secrets(x) == x[:x.index(_TOML_NAME) + len(_TOML_NAME)]

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
# 1b. 批 Q QA 依型別分流：`TomlDecodeError` 的散文形照舊整段截（訊息本身會串入內容）
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
#: 數字轉換失敗：未加引號、以數字開頭的值 → Python 的 float()／int() 訊息帶出那一行的**原始值**
#: （批 Q QA 指出的第二條外露通道）：(觸發文件, 逐字錄下的 `str(e)`)。
_TOML_NUM = {
    "float": ("finmind_token = 9f86d081884c7d659a2feaa0c55ad015\n",
              "could not convert string to float: '9f86d081884c7d659a2feaa0c55ad015' (line 1 column 1 char 0)"),
    "int": ("nas_api_key = 9f86d081884c7d659a2f\n",
            "invalid literal for int() with base 0: '9f86d081884c7d659a2f' (line 1 column 1 char 0)"),
}
#: 會外露的值：重複表 dict 裡的（`client_email`／`project_id`／`client_id`／自訂欄位 `my_api_pw` 不在秘密
#: 欄位清單上）＋ 數字轉換失敗帶出的原始值（沒有任何其他規則認得這種十六進位權杖）。
_TOML_LEAKS = ("proj-r12-toml", "svc-r12@", "109876543210987654321", "hunter2customR12", "pkidR12toml",
               "MIIEvR12toml", "AIzaSyTomlR12", "9f86d081884c7d659a2f")
#: 其他種類的 toml 0.10.2 錯誤（沒有列舉成「會串內容」的那幾種）：(觸發文件, 逐字錄下的 `str(e)`)。
_TOML_OTHER = {
    "dup_keys": ("a = 1\na = 2\n", "Duplicate keys! (line 2 column 1 char 6)"),
    "unbalanced": ('token = "abc\n', "Unbalanced quotes (line 1 column 13 char 12)"),
    "bad_group": ("[a b]\nx = 1\n", "Invalid group name 'a b'. Try quoting it. (line 1 column 1 char 0)"),
    "no_value": ("justakey\n", "Key name found without value. Reached end of line. (line 1 column 9 char 8)"),
}
_TOML_ALL = {"dup_table": (_TOML_DOC, _TOML_DUP_RECORDED), **{f"num_{k}": v for k, v in _TOML_NUM.items()},
             **{f"other_{k}": v for k, v in _TOML_OTHER.items()}}
#: 使用者會怎麼貼：traceback 最後一行、只貼型別名＋訊息、冒號前有空白、夾在問句／回答裡、整段 traceback。
_TOML_WRAPS = (
    "toml.decoder.TomlDecodeError: {}",
    "TomlDecodeError : {}",
    "為什麼出現 toml.decoder.TomlDecodeError: {}，怎麼解？",
    "你看到的是 TomlDecodeError: {}。解法：把值加上引號、刪掉重複的表。",
    "Traceback (most recent call last):\n  File \"app.py\", line 9, in <module>\ntoml.decoder.TomlDecodeError: {}",
)
#: 突變：把 `TomlDecodeError` 也加進放寬清單（＝ 分流之前、只截 repr 形的版本）。
_TOML_RELAX_MUT = ('_PROSE_RELAXED_EXC: str = r"Unicode(?:Decode|Encode|Translate)Error"',
                   '_PROSE_RELAXED_EXC: str = r"(?:Unicode(?:Decode|Encode|Translate)Error|TomlDecodeError)"')

#: 突變：拿掉批 S4 的兩條 toml 帶值規則（SEC-r20／SEC-r21）。
_S4_TOML_DROP = (("    (_TOML_EXISTS_DICT_RE, lambda m: m.group(1) + MASK),\n", ""),
                 ("    (_TOML_CONV_RE, _mask_toml_conv_for),\n", ""))


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


def _toml_head(x: str) -> str:
    """`TomlDecodeError` 照截之後應剩下的：第一個型別名（含）之前的全部。"""
    return x[:x.index(_TOML_NAME) + len(_TOML_NAME)]


def _assert_toml_colon_form_is_cut(fn) -> None:
    """（被突變測試重用）每一種 toml 訊息 × 每一種貼法：從 `TomlDecodeError` 之後整段拿掉（同 `scrub_secrets`）。"""
    for name, (doc, recorded) in _TOML_ALL.items():
        msg = _toml_message(doc, recorded)
        for wrap in _TOML_WRAPS:
            x = wrap.format(msg)
            out = fn(x)
            assert out == _toml_head(x), (name, wrap[:30], out[-150:])
            assert not [leak for leak in _TOML_LEAKS if leak in out], (name, out[-150:])


class TestTomlColonFormStillCut:
    def test_recorded_messages_match_real_toml(self):
        toml = pytest.importorskip("toml")
        for name, (doc, recorded) in _TOML_ALL.items():
            with pytest.raises(toml.TomlDecodeError) as ei:
                toml.loads(doc)
            assert str(ei.value) == recorded, name

    def test_premise_relaxing_toml_too_leaks_both_known_shapes(self):
        """修前實況（批 Q QA 重現）：`TomlDecodeError` 也只截 repr 形時，重複表 dict 的值與數字轉換的原始值都外露；
        錯誤字串那支（＝ `7020d13` v2 問答用的）兩種都整段截。"""
        #: 批 S4（SEC-r20／SEC-r21）起，toml 帶值訊息另有不靠型別名的兩條規則（`_TOML_EXISTS_DICT_RE`／`_TOML_CONV_RE`）——
        #: 修前實況要把那兩條一併拿掉才看得到（兩層各自承重：只放寬第 1 類時值仍被遮，見 `tests/test_sec_s4_batch_s4.py`）。
        m = _mutant(SSC, _TOML_RELAX_MUT, *_S4_TOML_DROP)
        for name, want in (("dup_table", {"proj-r12-toml", "svc-r12@", "109876543210987654321", "hunter2customR12"}),
                           ("num_float", {"9f86d081884c7d659a2f"}), ("num_int", {"9f86d081884c7d659a2f"})):
            x = f"toml.decoder.TomlDecodeError: {_toml_message(*_TOML_ALL[name])}"
            assert scrub_secrets(x) == "toml.decoder.TomlDecodeError"
            leaked = {leak for leak in _TOML_LEAKS if leak in m.scrub_prose_secrets(x)}
            assert leaked >= want, (name, leaked)

    def test_every_toml_message_is_cut_in_prose_and_markdown(self):
        _assert_toml_colon_form_is_cut(scrub_prose_secrets)
        _assert_toml_colon_form_is_cut(scrub_qa_text)

    @pytest.mark.parametrize("name", sorted(_TOML_ALL))
    def test_prose_equals_the_error_scrubber_on_toml_messages(self, name):
        """toml 訊息（不論哪一種、怎麼貼）：散文版與 `scrub_secrets` 逐字相同。"""
        msg = _toml_message(*_TOML_ALL[name])
        for wrap in _TOML_WRAPS:
            x = wrap.format(msg)
            assert scrub_prose_secrets(x) == scrub_secrets(x)

    @pytest.mark.parametrize("x", [
        _Q_ERR, _A_ERR,
        #: ~~`f"{_UDE}: What? g already exists?{{'g': 1}}"`~~（Unicode 散文形後面接什麼都照留）—— 批 S4（SEC-r20）起
        #: toml 重複表的 dict 不論前面有沒有型別名一律遮（`tests/test_sec_s4_batch_s4.py`），改用不含 toml 形狀的後文：
        f"{_UDE}: invalid start byte {{'g': 1}}",                          # Unicode 散文形後面接什麼都照留
        "UnicodeEncodeError: 'ascii' codec can't encode character '\\xe9' in position 3，怎麼解？",
    ])
    def test_unicode_colon_form_prose_is_still_kept(self, x):
        """SEC-r12 主案例不受分流影響：引用 `Unicode*Error: …` 的提問／回答照舊完整不截。"""
        assert scrub_prose_secrets(x) == x
        assert scrub_secrets(x) != x, "前提：錯誤字串那支會截"

    @pytest.mark.parametrize("name", ["dup_table", "num_float", "num_int"])
    def test_boundary_message_without_the_type_name_is_cut_by_neither(self, name):
        """只貼訊息、不帶型別名 → 第 1 類認不出來，兩支都不截、結果相同（`7020d13` 亦同）。

        ~~據實揭露：值外露~~ —— 批 S4（SEC-r21 (i)）起由 `_TOML_EXISTS_DICT_RE`／`_TOML_CONV_RE` 遮掉值
        （兩支同一份規則，結果仍相同）；原本「前提：真的外露」的斷言改為「值不外露」。"""
        x = f"這是什麼意思：{_toml_message(*_TOML_ALL[name])}"
        assert scrub_prose_secrets(x) == scrub_secrets(x)
        assert not [leak for leak in _TOML_LEAKS if leak in scrub_prose_secrets(x)], "SEC-r21 (i)：值不外露（兩支一樣）"


# ══════════════════════════════════════════════════════════════════
# 2. 引用的錯誤訊息裡夾金鑰／路徑／帳密：其餘規則照遮
#    （`_LEAKY` 扣掉只靠 `Unicode*Error` 散文形擋的那 1 筆，其餘每一筆逐一嵌進三種 `Unicode*Error` 散文形；
#     `TomlDecodeError` 樣本嵌進去 → 照舊被截在它那裡）
# ══════════════════════════════════════════════════════════════════
_EMBED = (
    "為什麼出現 UnicodeDecodeError: {} 怎麼解？",
    "你看到的是 UnicodeTranslateError: {}。解法：重新產生 secrets.toml。",
    "UnicodeEncodeError : {}",
)


@pytest.mark.parametrize("wrap", _EMBED, ids=["q", "a", "bare"])
@pytest.mark.parametrize("case", sorted(set(_LEAKY) - _RELAXED_LEAKY))
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
# 3. ⭐ 少遮的確切範圍（只限 `Unicode*Error` 的散文形）—— 其他規則一條不少
# ══════════════════════════════════════════════════════════════════
_SWAP = ("(_CONTENT_BEARING_EXC_PROSE_RE if _re is _CONTENT_BEARING_EXC_RE else _re).sub(_rep, out)",
         "_re.sub(_rep, out)")


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
    """刻意造出的散文形輸入：`Unicode*Error` 散文形放在開頭／中間、前後夾 repr 形或 `TomlDecodeError`、夾在中文句子裡。"""
    rnd = random.Random(20260928)
    base = sorted({r for r, *_ in _LEAKY.values()} | set(_PLAIN))
    base += rnd.sample(sorted(x for x, _p, _s in _fast_results()), 600)
    out: set[str] = set()
    for b in base:
        h = len(b) // 2
        out.update({
            "UnicodeDecodeError: " + b, f"為什麼出現 UnicodeEncodeError : {b} 怎麼解？",
            b + " TomlDecodeError: x", b[:h] + "UnicodeDecodeError:" + b[h:],
            f"UnicodeTranslateError\t: a {b} UnicodeDecodeError('utf-8', b'password = \"zz\"')",
            # `Unicode*Error` 散文形之後才出現 `TomlDecodeError`（重複表／數字轉換的形狀）→ 截在 toml 那裡
            f"UnicodeDecodeError: {b[:40]} TomlDecodeError: What? t already exists?{{'k': '{b}'}}",
            f"{b} UnicodeEncodeError: x\ntoml.decoder.TomlDecodeError: could not convert string to float: '{b}'",
        })
    return tuple(sorted(x for x in out if not _has_sentinel(x)))


class TestExactScope:
    def test_prose_rule_is_rule_one_with_only_unicode_colon_form_relaxed(self):
        """散文版那條 ＝ 第 1 類那條前面加「放寬清單＋冒號」的否定前瞻（推導失效 → 這裡紅）。

        型別名清單仍只有一份（第 1 類那條）；**不在放寬清單上的型別一律照截** —— 日後第 1 類多加一個型別，
        散文版預設就兩種形都截（安全側），要放寬必須明白改 `_PROSE_RELAXED_EXC`。
        """
        old, new = SSC._CONTENT_BEARING_EXC_RE, SSC._CONTENT_BEARING_EXC_PROSE_RE
        assert old.pattern == r"(Unicode(?:Decode|Encode|Translate)Error|TomlDecodeError)[ \t]*[(:].*"
        assert SSC._PROSE_RELAXED_EXC == r"Unicode(?:Decode|Encode|Translate)Error"
        assert new.pattern == ("(?!" + SSC._PROSE_RELAXED_EXC + r"[ \t]*:)" + old.pattern)
        assert new.pattern == (r"(?!Unicode(?:Decode|Encode|Translate)Error[ \t]*:)"
                               r"(Unicode(?:Decode|Encode|Translate)Error|TomlDecodeError)[ \t]*[(:].*")
        assert new.flags == old.flags and new.flags & re.DOTALL
        assert [r for r, _rep in SSC._RULES].count(old) == 1, "被替換的那一條要真的在規則表裡、而且只有一條"

    @pytest.mark.parametrize("name,colon_kept", [
        ("UnicodeDecodeError", True), ("UnicodeEncodeError", True), ("UnicodeTranslateError", True),
        ("TomlDecodeError", False)])
    def test_the_split_per_type(self, name, colon_kept):
        """逐型別：repr 形（含括號前空白）兩支都截；散文形只有三種 `Unicode*Error` 在散文版保留。"""
        for x in (f"{name}('x')", f"{name} ('x')"):
            assert scrub_prose_secrets(x) == scrub_secrets(x) == name
        for x in (f"{name}: x", f"{name} :x", f"{name}\t: x"):
            assert scrub_secrets(x) == name
            assert scrub_prose_secrets(x) == (x if colon_kept else name)

    def test_prose_pipeline_is_scrub_secrets_with_exactly_one_rule_swapped(self):
        """AST：散文版的函式體 ＝ `scrub_secrets` 的函式體，只有第 1 圈迴圈裡那一個 regex 換掉（沒有其他特例）。

        日後 `scrub_secrets` 多加一個步驟（新迴圈／新呼叫）而散文版沒跟上 → 這裡紅（其他規則一條不少）。
        """
        old, new = _stmts(scrub_secrets), _stmts(scrub_prose_secrets)
        assert sum(_SWAP[0] in s for s in new) == 1
        assert [s.replace(*_SWAP) for s in new] == old

    def test_the_removed_toml_special_case_is_really_gone(self):
        """批 Q QA：分流規則對任何帶 `TomlDecodeError` 型別名的訊息一律照截 ⇒ 先前的專用加固
        （重複表 regex 與其上限常數）已移除，不留特例。"""
        assert not [n for n in vars(SSC) if n.startswith("_TOML_DUP")]

    def test_identical_to_scrub_secrets_unless_the_first_hit_is_the_unicode_colon_form(self):
        rows = _fast_results()
        assert len(rows) > 10_000, "語料不該是空的"
        diff = [x for x, p, s in rows if not _relaxed_first(x) and p != s]
        assert not diff, [d[:100] for d in diff[:5]]
        assert sum(_relaxed_first(x) for x, _p, _s in rows) >= 5, "語料裡要真的有散文形（防空轉）"

    def test_prose_equals_scrub_secrets_with_the_unicode_colon_form_defused(self):
        """蛻變關係：散文版 ＝ `scrub_secrets` 把 `Unicode*Error` 散文形的型別名當成普通字 ——
        少遮的就只有「那個型別名不再觸發截斷」；`TomlDecodeError` 不解除，照截。"""
        bad = [x for x, p, s in _fast_results() if p != (s if _defuse(x) == x else _expected_prose(x))]
        bad += [x for x in _augmented() if scrub_prose_secrets(x) != _expected_prose(x)]
        assert not bad, [b[:100] for b in bad[:5]]
        assert sum(_relaxed_first(x) for x in _augmented()) > 2000

    @pytest.mark.parametrize("case", sorted(_RELAXED_LEAKY))
    def test_scope_a_the_unicode_colon_form_tail_is_left_to_the_other_rules(self, case):
        """據實揭露 (a)：`_LEAKY` 裡只靠 `Unicode*Error` 散文形擋的那一筆，後文沒有任何其他規則命中 → 散文版原樣留著。"""
        raw, gone, _kept = _LEAKY[case]
        assert all(g not in scrub_secrets(raw) for g in gone), "錯誤字串那支照舊擋"
        assert scrub_prose_secrets(raw) == raw

    @pytest.mark.parametrize("case", sorted(_TOML_ONLY_COLON_LEAKY))
    def test_toml_only_colon_samples_are_cut_like_the_error_scrubber(self, case):
        """`_LEAKY` 裡只靠 `TomlDecodeError` 散文形擋的兩筆（含重複表形狀）：散文版照截，與 `scrub_secrets` 相同。"""
        raw, gone, _kept = _LEAKY[case]
        assert scrub_prose_secrets(raw) == scrub_secrets(raw)
        assert not [g for g in gone if g in scrub_prose_secrets(raw)]

    @pytest.mark.parametrize("x,leak", [
        # 與型別名黏在一起、合計超過 256 字上限的權杖串
        (f"password: no {'a1' * 100}{_UDE}:{'b2' * 40} end", "a1" * 100),
        # `no`／`not` 後面緊黏型別名的純字母（批 Q QA 補）
        (f"password: no hunter{_UDE}: 'utf-8' codec can't decode", "hunter"),
        ("api_key: not hunterUnicodeEncodeError: x", "hunter"),
    ])
    def test_scope_b_text_glued_to_the_type_name(self, x, leak):
        """據實揭露 (b)：原本靠「字串在型別名處結束」才遮到的前文，散文版不遮（兩種例子，docstring 同列）。"""
        assert leak not in scrub_secrets(x)
        assert leak in scrub_prose_secrets(x)
        assert scrub_prose_secrets(x) == _expected_prose(x)

    def test_scope_b_does_not_apply_to_toml(self):
        """(b) 只發生在放寬的型別：同樣緊黏在 `TomlDecodeError` 前面 → 散文版照截，與 `scrub_secrets` 相同。"""
        x = f"api_key: not hunter{_TOML_NAME}: x"
        assert scrub_prose_secrets(x) == scrub_secrets(x) and "hunter" not in scrub_prose_secrets(x)

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
        if (not _relaxed_first(x) and p != s) or p != (s if _defuse(x) == x else _expected_prose(x)):
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
            if _relaxed_first(x):
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

    @pytest.mark.parametrize("name", ["dup_table", "num_float", "num_int"])
    def test_pasted_toml_error_is_cut_in_all_three_places(self, monkeypatch, name):
        """批 Q QA 依型別分流：貼 toml 錯誤（重複表 dict／數字轉換的原始值）發問 → 送出／畫面／紀錄都截在
        `TomlDecodeError` 那裡，訊息裡的值一個都不外露。"""
        from src.ui.views import page_why as PW

        x = f"為什麼出現 toml.decoder.TomlDecodeError: {_toml_message(*_TOML_ALL[name])}，怎麼解？"
        head = _toml_head(x)
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

    @pytest.mark.parametrize("name", ["dup_table", "num_float", "num_int"])
    def test_pasted_toml_error_is_cut(self, monkeypatch, tmp_path, name):
        """批 Q QA 依型別分流（v1 端）：貼 toml 錯誤（重複表 dict／數字轉換的原始值）發問 →
        送出／畫面／紀錄都截在 `TomlDecodeError` 那裡。"""
        x = f"為什麼出現 toml.decoder.TomlDecodeError: {_toml_message(*_TOML_ALL[name])}，怎麼解？"
        head = _toml_head(x)
        at = _v1_app(monkeypatch, tmp_path, answer="請把值加上引號、刪掉重複的表。")
        _ask(at, x)
        assert [c["question"] for c in _calls(at)] == [head]
        assert _history(at)[0]["content"] == head and head in _screen(at)
        blob = json.dumps({"calls": _calls(at), "screen": _screen(at), "history": _history(at)}, ensure_ascii=False)
        assert not [leak for leak in _TOML_LEAKS if leak in blob]


# ══════════════════════════════════════════════════════════════════
# 7. 突變驗證：拔掉每一個修法點 → 上面對應那一組斷言轉紅
# ══════════════════════════════════════════════════════════════════
_L0_SWAP_MUT = ("(_CONTENT_BEARING_EXC_PROSE_RE if _re is _CONTENT_BEARING_EXC_RE else _re)", "_re")
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

    def test_c_l0_relaxing_toml_too_leaks_and_turns_red(self):
        """把 `TomlDecodeError` 也放寬（＝ 分流之前的版本）→ 重複表 dict 與數字轉換的原始值外露，
        `_assert_toml_colon_form_is_cut` 轉紅；Unicode 那一支（SEC-r12 主案例）不受影響。"""
        m = _mutant(SSC, _TOML_RELAX_MUT)
        with pytest.raises(AssertionError):
            _assert_toml_colon_form_is_cut(m.scrub_prose_secrets)
        _assert_prose_keeps_the_colon_form(m.scrub_prose_secrets)

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
#: 後半是 `TomlDecodeError` 散文形與重複表訊息的形狀（大量起點、長串空白），以及放寬清單的否定前瞻
#: 在每個位置都得先看一次的情形（依型別分流後，每個 `Unicode*Error:` 起點都會被前瞻否決、往下一個位置找）。
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
