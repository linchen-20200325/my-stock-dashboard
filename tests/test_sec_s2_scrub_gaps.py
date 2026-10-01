"""SEC 批次 S2（2026-09-27）：SEC-r1 / SEC-r2-f1 / SEC-r10 / SEC-r7-f1。

- SEC-r2-f1：`password: no bot123456789:<token>` —— 原本只遮說明字 `no`，權杖外露 → 整段遮。
- SEC-r1：已知不遮的形態 —— 無 `/` 的 `bot<數字>:<token>`、全形 `：`／`＝`、`%3D`、
  `open?id=`／`uc?id=`、正斜線 UNC `//server/…`、`@`／`→`／`—` 起點的路徑。
- SEC-r10：TOML 賦值遮到行尾時連同行的**收尾粗體** `**` 一起吃掉 → 只留下那個 `**`。
- SEC-r7-f1：`page_why` 使用者自己的提問也洗過才上畫面／寫進紀錄。

⭐ 硬性要求：**任何輸入都不得比舊版少遮**（唯一例外：不屬於秘密的粗體 `**` 與空白）。
「舊版」＝本模組把新規則拔掉、`_ASSIGN_RE` 換回舊取代式的突變體（與 `27f0788` 語意相同）。
全部是行為測試；每條新規則拔掉（突變）→ 對應樣本外露。
"""
from __future__ import annotations

import ast
import collections
import importlib.util
import itertools
import json
import pathlib
import random
import subprocess
import sys

import pytest

from shared import secret_scrub as SSC
from shared.secret_scrub import scrub_query_secrets, scrub_secrets
from tests._git_tracked import only_tracked

_TOK = "Ab1Cd2Ef3Gh4Ij5Kl6Mn7Op8Qr9St0Uv1Wx"   # 36 字、含數字（Telegram token 形狀）


def _mutant(*pairs: tuple[str, str]):
    src = pathlib.Path(SSC.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    spec = importlib.util.spec_from_loader("_mutant_sec_s2", loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = SSC.__file__
    exec(compile(src, SSC.__file__, "exec"), m.__dict__)
    return m


_POST_LINE = {
    "fw_assign": "    (_FW_ASSIGN_RE, _mask_assign),\n",
    "fw_colon_quoted": "    (_FW_COLON_QUOTED_RE, _mask_value),\n",
    "fw_colon_bare": "    (_FW_COLON_BARE_RE, _mask_value),\n",
    "pct_query": "    (_PCT_QUERY_SECRET_RE, lambda m: m.group(1) + m.group(2) + MASK),\n",
    "cred_after_mask": "    (_CRED_AFTER_MASK_RE, lambda m: m.group(1) + MASK),\n",
    "tg_bot_prefix": "    (_TG_BOT_PREFIX_RE, MASK),\n",
    "drive_open_id": "    (_DRIVE_OPEN_ID_RE, lambda m: m.group(1) + MASK),\n",
    "fwd_unc": "    (_FWD_UNC_RE, lambda m: MASK + \"/\" + (m.group(1) or \"\")),\n",
    "posix_extra": "    (_POSIX_PATH_EXTRA_RE, lambda m: MASK + \"/\" + (m.group(1) or \"\")),\n",
}
_OLD_ASSIGN = ("    (_ASSIGN_RE, _mask_assign),\n",
               "    (_ASSIGN_RE, lambda m: m.group(\"pre\") + MASK),\n")
#: 舊版語意：新規則全部拔掉 ＋ 賦值換回舊取代式。
_BASELINE = _mutant(_OLD_ASSIGN, *((line, "") for line in _POST_LINE.values()))

# ══════════════════════════════════════════════════════════════════
# 各項樣本：(原文, 不得出現的片段, 期望輸出)；每條新規則拔掉 → 片段外露
# ══════════════════════════════════════════════════════════════════
_CASES = {
    "cred_after_mask": (f"password: no bot123456789:{_TOK}", _TOK, "password: ***"),
    "cred_after_mask_words": ("password: was set to abcdef1234567890abcd end",
                              "abcdef1234567890", "password: *** end"),
    "tg_bot_prefix": (f"bot123456789:{_TOK}", _TOK, "bot***"),
    "fw_colon_bare": ("password：hunter2", "hunter2", "password：***"),
    "fw_colon_quoted": ("{'client_secret'：'s3cr3t'}", "s3cr3t", "{'client_secret'：'***'}"),
    "fw_assign": ("password＝hunter2", "hunter2", "password＝***"),
    "pct_query": ("x?password%3Dhunter2&y=1", "hunter2", "x?password%3D***&y=1"),
    "drive_open_id": ("https://drive.google.com/open?id=1AbCdEfGhIjKlMnOpQr",
                      "1AbCdEfGhIjKlMnOpQr", "https://drive.google.com/open?id=***"),
    "fwd_unc": ("讀不到 //nas01/share/aliceS2/x.toml", "aliceS2", "讀不到 ***/x.toml"),
    "posix_extra": ("see @/home/aliceS2/.streamlit/secrets.toml", "aliceS2", "see @***/secrets.toml"),
}
_CASE_OF_RULE = {"cred_after_mask": "cred_after_mask_words", "tg_bot_prefix": "tg_bot_prefix",
                 "fw_colon_bare": "fw_colon_bare", "fw_colon_quoted": "fw_colon_quoted",
                 "fw_assign": "fw_assign", "pct_query": "pct_query", "drive_open_id": "drive_open_id",
                 "fwd_unc": "fwd_unc", "posix_extra": "posix_extra"}


@pytest.mark.parametrize("name", sorted(_CASES))
def test_new_forms_are_masked(name):
    raw, gone, want = _CASES[name]
    out = scrub_secrets(raw)
    assert gone not in out and out == want, out
    assert gone in _BASELINE.scrub_secrets(raw), "前提：舊版確實外露"


@pytest.mark.parametrize("rule", sorted(_POST_LINE))
def test_dropping_each_new_rule_leaks(rule):
    raw, gone, _want = _CASES[_CASE_OF_RULE[rule]]
    assert gone in _mutant((_POST_LINE[rule], "")).scrub_secrets(raw), rule


@pytest.mark.parametrize("raw", [
    "https://host/a/b", "元/股/張 80/20 14:30", "a@b.com", "api_key: not set", "x → y — z",
    "password: hunter2 and more words", "open?idx=1", "//", "id=1AbCdEfGhIjKlMnOp"])
def test_non_secret_text_same_as_before(raw):
    assert scrub_secrets(raw) == _BASELINE.scrub_secrets(raw)


# ══════════════════════════════════════════════════════════════════
# SEC-r10：收尾粗體
# ══════════════════════════════════════════════════════════════════
_BOLD = [
    ("- **client_secret = abc** — note", "- **client_secret = ***** ***"),
    ("**token = abc**", "**token = *****"),
    ("**token = abc**  ", "**token = *****  "),
    ("b'x\\n**password = z** y\\nq = 1'", "b'x\\n**password = ***** ***\\nq = 1'"),
    ('**token = "a**b" x**', "**token = ***"),             # 引號內的 ** 可能是秘密 → 照舊整段遮
    ("token = abc** x", "token = ***"),                     # 前面沒有未收尾的 ** → 照舊
    ("**a** token = abc** x", "**a** token = ***"),         # 前面的 ** 已收尾 → 照舊
    ("**password ＝ z**", "**password ＝ *****"),
]


@pytest.mark.parametrize("raw,want", _BOLD)
def test_r10_closing_bold_marker_kept(raw, want):
    out = scrub_secrets(raw)
    assert out == want
    assert _ctr(out) - _ctr(_BASELINE.scrub_secrets(raw)) == collections.Counter()


def test_r10_mutant_eats_the_marker_again():
    raw, want = _BOLD[0]
    assert _mutant(_OLD_ASSIGN).scrub_secrets(raw) != want


def test_r10_lookback_is_bounded():
    """往回找行首有上限（`_BOLD_LOOKBACK`）—— 拔掉上限會回到 O(n²)（2MB 實測 100 秒）。

    行為面的守衛：未收尾的 `**` 遠在上限之外 → 看不到 → 照舊整段遮（秘密一樣全遮）。
    """
    far = "**" + "x" * (SSC._BOLD_LOOKBACK + 50) + " token = abc**"
    assert scrub_secrets(far).endswith(" token = ***")
    near = "**" + "x" * 50 + " token = abc**"
    assert scrub_secrets(near).endswith(" token = *****")
    assert _mutant(("_BOLD_LOOKBACK: int = 512", "_BOLD_LOOKBACK: int = 10**9")
                   ).scrub_secrets(far).endswith(" token = *****")


def test_r10_bold_renders_through_scrub_md_mask():
    from shared.secret_md import scrub_md_mask
    assert scrub_md_mask("**client_secret = abc** 說明") == "**client_secret = \\*\\*\\*** \\*\\*\\*"


# ══════════════════════════════════════════════════════════════════
# ⭐ 不得比舊版少遮 ＋ scrub_query_secrets 不變
# ══════════════════════════════════════════════════════════════════
def _ctr(s: str) -> collections.Counter:
    return collections.Counter(c for c in s if c != "*" and not c.isspace())


def _corpus() -> set[str]:
    out: set[str] = set()
    _tests = pathlib.Path(__file__).resolve().parent
    for f in only_tracked(_tests.parent, _tests.glob("test_*.py")):     # SEC-r26（批 S4）：只收 git 追蹤中的檔案
        src = f.read_text(encoding="utf-8")
        if "scrub" not in src:
            continue
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                out.add(node.value)
    fields = ["password", "api_key", "client_secret", "token", "secret", "fred_api_key", "Authorization"]
    seps = [": ", "：", " = ", "=", "＝", '": "', "%3D"]
    vals = ["hunter2", "not set", f"no bot123456789:{_TOK}", "was abcdef1234567890abcd end",
            '"a**b" x**', "abc** — note", "C:\\Users\\a\\x.toml", "/home/u/x.toml", "abc\\ndef"]
    wraps = ["{}", "**{}**", "- **{}** tail", "b'x\\n{}\\nq = 1'", "ValueError('{}')",
             "see {} @/home/u/a/b.toml //srv/sh/f.txt →/etc/a/b"]
    for f, sp, v, w in itertools.product(fields, seps, vals, wraps):
        out.add(w.format(f + sp + v))
    rnd = random.Random(20260927)
    alpha = list("ab01*_ :=＝：\"'\\/@→—\n.-%3D") + fields + ["bot12345:", _TOK]
    for _ in range(4000):
        out.add("".join(rnd.choice(alpha) for _ in range(rnd.randint(1, 24))))
    return out


def test_never_masks_less_than_baseline():
    worse = []
    for raw in _corpus():
        if _ctr(scrub_secrets(raw)) - _ctr(_BASELINE.scrub_secrets(raw)):
            worse.append(raw)
    assert not worse, worse[:5]


def test_query_scrubber_unchanged():
    assert SSC.QUERY_SECRET_RE.pattern == r"\b(key|token|api[_-]?key|access[_-]?token)=[^&\s\"'<>]+"
    assert SSC.GOOGLE_API_KEY_RE.pattern == r"AIza[0-9A-Za-z_\-]{10,}"
    for raw in list(_corpus())[:3000]:
        assert scrub_query_secrets(raw) == _BASELINE.scrub_query_secrets(raw)


# ══════════════════════════════════════════════════════════════════
# ReDoS：新規則的對抗輸入（子程序＋總時限）
# ══════════════════════════════════════════════════════════════════
_REDOS_N = 50_000
_UNITS = ("password： ", "password＝ ", "password%3D", "password: *** a ", "password: *** " + "1" * 20,
          "bot1", "bot123456:", "open?id=", " //a", "//a/", "@/a", "→/a/", "—~a/", "**token = a** ",
          "**", "password: no a a a ",
          # 同一行上大量賦值：`_mask_assign` 往回找行首若不設上限 ⇒ O(n²)（實測 2MB 100 秒）
          "\\n**token = x**", "**token = x** ")
_SCRIPT = ("import json, sys, time\nfrom shared.secret_scrub import scrub_secrets\nout = {}\n"
           "for name, text in json.load(sys.stdin):\n"
           "    t = time.perf_counter(); scrub_secrets(text); out[name] = time.perf_counter() - t\n"
           "print(json.dumps(out))\n")


def test_new_rules_are_linear():
    cases = [[u, (u * (_REDOS_N // len(u) + 1))[:_REDOS_N]] for u in _UNITS]
    cases += [["pw+" + u, "password: " + (u * (_REDOS_N // len(u) + 1))[:_REDOS_N]] for u in _UNITS]
    r = subprocess.run([sys.executable, "-c", _SCRIPT], input=json.dumps(cases), capture_output=True,
                       text=True, timeout=30, cwd=str(pathlib.Path(__file__).resolve().parents[1]))
    assert r.returncode == 0, r.stderr[-2000:]
    slow = {k: v for k, v in json.loads(r.stdout).items() if v > 2.0}
    assert not slow, slow


# ══════════════════════════════════════════════════════════════════
# SEC-r7-f1：使用者自己的提問
# ══════════════════════════════════════════════════════════════════
_Q_KEY = "AIzaSyA1234567890secS2qabcdefg"
_Q = f"我的 password: pwS2zz 跟金鑰 {_Q_KEY} 放 /home/aliceS2q/app/secrets.toml 對嗎？"


def test_r7f1_question_scrubbed_on_screen_and_in_history(monkeypatch):
    from src.ui.views import page_why as P
    from tests.test_p05_why_view import _FakeChatST, _fake_agent, _render_qa

    _fake = _FakeChatST(typed=_Q)
    _fake_agent(monkeypatch, text="偏強。")
    _out = _render_qa(monkeypatch, _fake)
    _hist = [m for m in _fake.session_state[P.SS_QA_HISTORY] if m.get("role") == "user"]
    assert _hist and _hist[-1]["content"] == P.scrub_qa_text(_Q)
    for _leak in (_Q_KEY, "pwS2zz", "aliceS2q"):
        assert _leak not in _out and _leak not in _hist[-1]["content"]


def test_r7f1_clean_question_byte_identical(monkeypatch):
    from src.ui.views import page_why as P
    from tests.test_p05_why_view import _FakeChatST, _fake_agent, _render_qa

    _clean = "2330 **健康度**？元/股 80/20"
    _fake = _FakeChatST(typed=_clean)
    _fake_agent(monkeypatch, text="偏強。")
    _render_qa(monkeypatch, _fake)
    _user = [m for m in _fake.session_state[P.SS_QA_HISTORY] if m.get("role") == "user"]
    assert _user[-1]["content"] == _clean


# ══════════════════════════════════════════════════════════════════
# 獨立 QA 補洞（存活突變體 3 個）
# ══════════════════════════════════════════════════════════════════
_UC = "https://drive.google.com/uc?id=1BoBsEcReTsHeEtIdXyZ123&export=download"


def test_qa_drive_uc_id_masked():
    assert scrub_secrets(_UC) == "https://drive.google.com/uc?id=***&export=download"
    m = _mutant(("((?:open|uc)\\?id=)", "((?:open)\\?id=)"))
    assert "1BoBsEcReTsHeEtIdXyZ123" in m.scrub_secrets(_UC)


def test_qa_em_dash_path_start_masked():
    raw = "讀取失敗 —/home/bob/.streamlit/secrets.toml"
    assert scrub_secrets(raw) == "讀取失敗 —***/secrets.toml"
    m = _mutant(("(?<=[@→—])(?:~", "(?<=[@→])(?:~"))
    assert "/home/bob" in m.scrub_secrets(raw)


def test_qa_bold_lookback_honours_repr_newline_escape():
    """repr 裡的 `\\n` 跳脫算行首：前一行的 `**x` 不得把本行的未收尾 `**` 抵銷。"""
    raw = "b'**x\\n- **password = z** ok'"
    assert scrub_secrets(raw) == "b'**x\\n- **password = ***** ***"  # 值遮到行尾（含收尾引號，同舊版）
    m = _mutant(('("\\n", "\\r", "\\\\n", "\\\\r")', '("\\n", "\\r")'))
    assert m.scrub_secrets(raw) == "b'**x\\n- **password = ***"
