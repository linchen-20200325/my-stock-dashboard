"""本機日K查詢的請求／回應純契約（`shared/ui2_contract/local_lookup_request.py`；P-M2g §三）。純合成、離線。"""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import re
import types

import pytest

from shared.ui2_contract import local_lookup_request as R
from shared.ui2_contract.local_lookup_request import (
    LocalLookupRequest as Req, LocalLookupResponse as Resp, LocalProof, build_local_proof as blp,
)
from shared.ui2_contract.local_lookup_result import build_local_lookup_result
from shared.ui2_contract.quote_view import build_quote_view
from shared.ui2_contract.target_selection import parse_ticker_input
from tests.test_ui2_guards import check_capability_marker_scope, check_vm_purity

SRC = pathlib.Path(R.__file__)
REL = "shared/ui2_contract/local_lookup_request.py"
PROOF = LocalProof(bind_address="127.0.0.1", headers_present=True, request_host="localhost", proxy_header_names=())


def _vm():
    q = build_quote_view(parse_ticker_input("0050"), loaded=True, fetch_error=None, close=188.55,
                         trade_date="2026-11-20", fetched_at=None, source="合成", is_stale=False)
    return build_local_lookup_result(
        q, open_=None, high=None, low=None, close=None, volume=None, as_of=None, ma20=None, ma240=None,
        bias20_pct=None, vol_ratio5=None, support=None, resistance=None, source_user_declared=True)


VM = _vm()


# ── 固定詞彙 ─────────────────────────────────────────────────────────
def test_reason_codes_verbatim_and_immutable():
    assert R.REASON_CODES == (
        "not_enabled", "bind_not_loopback", "no_request_context", "host_not_loopback", "proxy_headers_present",
        "hosted_runtime", "dir_invalid", "dir_inside_repo", "file_invalid", "file_not_regular", "file_too_large",
        "file_unreadable", "parse_failed", "bad_request")
    assert isinstance(R.REASON_CODES, tuple) and isinstance(R.REASON_CODE_SET, frozenset)
    assert R.REASON_CODE_SET == frozenset(R.REASON_CODES) and len(R.REASON_CODES) == len(R.REASON_CODE_SET) == 14
    assert R.OPS == ("list", "query")
    with pytest.raises(AttributeError):
        R.REASON_CODE_SET.add("x")                              # type: ignore[attr-defined]


# ── LocalProof ───────────────────────────────────────────────────────
@pytest.mark.parametrize("kw", [
    dict(bind_address="127.0.0.1"), dict(bind_address=None), dict(bind_address=""), dict(bind_address="0.0.0.0"),
    dict(request_host="::1"), dict(request_host="127.0.0.1"), dict(request_host="fe80::1"),
    dict(proxy_header_names=("via",)), dict(proxy_header_names=("forwarded", "via", "x-forwarded-for", "x-real-ip")),
    dict(proxy_header_names=("x-forwarded-host", "x-forwarded-proto")),
])
def test_proof_valid(kw):
    base = dict(bind_address=None, headers_present=True, request_host=None, proxy_header_names=())
    base.update(kw)
    assert LocalProof(**base)


def test_proof_no_headers_minimal():
    assert LocalProof(None, False, None, ())


@pytest.mark.parametrize("kw,exc", [
    (dict(bind_address=1), TypeError), (dict(bind_address=True), TypeError), (dict(bind_address=b"x"), TypeError),
    (dict(headers_present=1), TypeError), (dict(headers_present=None), TypeError), (dict(headers_present="yes"), TypeError),
    (dict(request_host=5), TypeError), (dict(request_host=True), TypeError),
    (dict(request_host=""), ValueError), (dict(request_host="LocalHost"), ValueError),
    (dict(request_host="localhost:8501"), ValueError), (dict(request_host="[::1]"), ValueError),
    (dict(request_host="[::1]:8501"), ValueError), (dict(request_host="::G"), ValueError),
    (dict(request_host="a b"), ValueError), (dict(request_host="a\nb"), ValueError), (dict(request_host=" "), ValueError),
    (dict(proxy_header_names=["via"]), TypeError), (dict(proxy_header_names=(1,)), TypeError),
    (dict(proxy_header_names="via"), TypeError), (dict(proxy_header_names=(True,)), TypeError),
    (dict(proxy_header_names=("VIA",)), ValueError), (dict(proxy_header_names=("x-custom",)), ValueError),
    (dict(proxy_header_names=("host",)), ValueError), (dict(proxy_header_names=("x-forwarded-for", "via")), ValueError),
    (dict(proxy_header_names=("via", "via")), ValueError), (dict(proxy_header_names=("forwarded", "via", "forwarded")), ValueError),
])
def test_proof_invalid(kw, exc):
    base = dict(bind_address=None, headers_present=True, request_host=None, proxy_header_names=())
    base.update(kw)
    with pytest.raises(exc):
        LocalProof(**base)


def test_proof_without_headers_cannot_carry_host_or_proxy():
    with pytest.raises(ValueError):
        LocalProof(None, False, "localhost", ())
    with pytest.raises(ValueError):
        LocalProof(None, False, None, ("via",))


def test_proof_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        PROOF.request_host = "evil"                              # type: ignore[misc]
    assert {f.name for f in dataclasses.fields(LocalProof)} == {
        "bind_address", "headers_present", "request_host", "proxy_header_names"}


# ── LocalLookupRequest ───────────────────────────────────────────────
def test_request_valid_forms():
    assert Req("list", PROOF).symbol is None
    r = Req("query", PROOF, symbol="0050", filename="x.csv")
    assert (r.op, r.symbol, r.filename) == ("query", "0050", "x.csv")
    assert Req(op="query", proof=PROOF, symbol="0050", filename="x.csv") == r


@pytest.mark.parametrize("args,exc", [
    (dict(op="delete"), ValueError), (dict(op=""), ValueError), (dict(op=None), ValueError),
    (dict(op=1), ValueError), (dict(op=True), ValueError), (dict(op="LIST"), ValueError),
    (dict(op="query"), ValueError),                                              # 缺 symbol／filename
    (dict(op="query", symbol="0050"), ValueError), (dict(op="query", filename="a.csv"), ValueError),
    (dict(op="query", symbol="", filename="a.csv"), ValueError), (dict(op="query", symbol="0050", filename=""), ValueError),
    (dict(op="query", symbol=50, filename="a.csv"), TypeError), (dict(op="query", symbol="0050", filename=True), TypeError),
    (dict(op="query", symbol=b"0050", filename="a.csv"), TypeError),
    (dict(op="list", symbol="0050"), ValueError), (dict(op="list", filename="a.csv"), ValueError),
    (dict(op="list", symbol="", filename=""), ValueError),                      # list 時須為 None，連空字串都不可
    (dict(op="list", symbol=1), TypeError),
])
def test_request_invalid(args, exc):
    with pytest.raises(exc):
        Req(proof=PROOF, **args)


@pytest.mark.parametrize("op", ["delete", "", None, 1, True, "LIST", "Query", b"list"])
def test_request_bad_op_rejected_even_with_full_query_fields(op):
    with pytest.raises(ValueError):
        Req(op, PROOF, symbol="0050", filename="x.csv")          # type: ignore[arg-type]


@pytest.mark.parametrize("proof", [None, "proof", {"bind_address": "x"}, object()])
def test_request_proof_must_be_localproof(proof):
    with pytest.raises(TypeError):
        Req("list", proof)                                       # type: ignore[arg-type]


def test_request_repr_does_not_leak_filename():
    secret = "SECRET_ACCOUNT_dump_2330.csv"
    r = Req("query", PROOF, symbol="0050", filename=secret)
    assert secret not in repr(r) and secret not in str(r) and "SECRET" not in repr(r)
    assert r.filename == secret                                  # 值本身仍可取用
    assert next(f for f in dataclasses.fields(Req) if f.name == "filename").repr is False


def test_repr_hides_symbol_bind_address_and_request_host():
    secret_sym, secret_bind, secret_host = "ZZSYM9", "10.9.8.7", "secret-host.example"
    proof = LocalProof(secret_bind, True, secret_host, ())
    r = Req("query", proof, symbol=secret_sym, filename="SECRETFILE.csv")
    for text in (repr(r), str(r), repr(proof), str(proof), repr(Resp("list", True, None, ("a.csv",)))):
        for needle in (secret_sym, secret_bind, secret_host, "SECRETFILE"):
            assert needle not in text, (needle, text)
    for cls, names in ((LocalProof, {"bind_address", "request_host"}), (Req, {"symbol", "filename"})):
        assert {f.name for f in dataclasses.fields(cls) if f.repr is False} == names
    assert (r.symbol, r.proof.request_host, r.proof.bind_address) == (secret_sym, secret_host, secret_bind)


def test_request_frozen():
    r = Req("list", PROOF)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.op = "query"                                           # type: ignore[misc]


# ── 錯誤訊息不回顯輸入 ───────────────────────────────────────────────
def test_error_messages_never_echo_input():
    needle = "SECRET_TOKEN_xyz"
    cases = [
        lambda: Req(needle, PROOF),                                                    # type: ignore[arg-type]
        lambda: Req("list", PROOF, symbol=needle),
        lambda: Req("query", PROOF, symbol=needle, filename=""),
        lambda: Req("query", PROOF, symbol=needle, filename=7),                        # type: ignore[arg-type]
        lambda: LocalProof(needle, True, needle, ()),
        lambda: LocalProof(1, True, None, ()),                                         # type: ignore[arg-type]
        lambda: LocalProof(None, True, needle.upper(), ()),
        lambda: LocalProof(None, True, None, (needle,)),
        lambda: Resp(needle, True),                                                    # type: ignore[arg-type]
        lambda: Resp("list", False, needle),
        lambda: Resp("list", True, needle),
        lambda: Resp("list", True, None, (needle + "/x",)),
        lambda: blp(None, {"Host": needle + ":"}),
        lambda: blp(None, {"Host": 5}),                                                # type: ignore[dict-item]
        lambda: blp(needle, {5: "x"}),                                                 # type: ignore[dict-item]
        lambda: blp(None, {"Host": "a", "host": "b" + needle}),
    ]
    for c in cases:
        with pytest.raises((TypeError, ValueError)) as ei:
            c()
        assert needle not in str(ei.value) and needle.upper() not in str(ei.value), str(ei.value)


# ── LocalLookupResponse ──────────────────────────────────────────────
def test_response_valid_forms():
    assert Resp("list", True, None, ("a.csv", "b.csv"))
    assert Resp("list", True)                                                          # 空目錄合法
    assert Resp("query", True, None, (), VM).vm is VM
    assert Resp("query", False, "parse_failed")
    assert Resp("query", False, "parse_failed", (), VM)                                # 資料態＋parse_failed
    for rc in R.REASON_CODES:
        assert Resp("list", False, rc) and Resp("query", False, rc)
    assert Resp(op="list", ok=True).filenames == () and Resp(op="list", ok=True).reason_code is None


@pytest.mark.parametrize("kw,exc", [
    (dict(op="x", ok=True), ValueError), (dict(op=None, ok=True), ValueError), (dict(op=1, ok=True), ValueError),
    (dict(op="list", ok=1), TypeError), (dict(op="list", ok=None), TypeError), (dict(op="list", ok="y"), TypeError),
    (dict(op="list", ok=True, reason_code="not_enabled"), ValueError),              # ok ⇒ reason None
    (dict(op="list", ok=True, reason_code=""), ValueError),
    (dict(op="list", ok=False), ValueError),                                         # not ok ⇒ reason 必填
    (dict(op="list", ok=False, reason_code="nope"), ValueError), (dict(op="list", ok=False, reason_code=""), ValueError),
    (dict(op="list", ok=False, reason_code="NOT_ENABLED"), ValueError),
    (dict(op="list", ok=False, reason_code=5), TypeError), (dict(op="list", ok=False, reason_code=True), TypeError),
    (dict(op="list", ok=True, filenames=["a.csv"]), TypeError), (dict(op="list", ok=True, filenames="a.csv"), TypeError),
    (dict(op="list", ok=True, filenames=(1,)), TypeError), (dict(op="list", ok=True, filenames=(True,)), TypeError),
    (dict(op="list", ok=True, filenames=("",)), ValueError),
    (dict(op="list", ok=True, filenames=("../a.csv",)), ValueError), (dict(op="list", ok=True, filenames=("d\\a.csv",)), ValueError),
    (dict(op="list", ok=True, filenames=("a\x00.csv",)), ValueError),
    (dict(op="list", ok=True, filenames=(".",)), ValueError), (dict(op="list", ok=True, filenames=("..",)), ValueError),
    (dict(op="list", ok=True, filenames=("a.csv", "..")), ValueError),
    (dict(op="list", ok=True, filenames=("a\\b.csv",)), ValueError),                  # 已知取捨：反斜線一律拒，過濾屬 L3
    (dict(op="query", ok=True, filenames=("a.csv",), vm=VM), ValueError),            # filenames 僅 list
    (dict(op="list", ok=False, reason_code="dir_invalid", filenames=("a.csv",)), ValueError),
    (dict(op="query", ok=False, reason_code="parse_failed", filenames=("a.csv",)), ValueError),
    (dict(op="query", ok=True), ValueError),                                         # query 成功必有 vm
    (dict(op="list", ok=True, vm=VM), ValueError),                                   # list 不得有 vm
    (dict(op="list", ok=False, reason_code="parse_failed", vm=VM), ValueError),
    (dict(op="query", ok=False, reason_code="file_invalid", vm=VM), ValueError),     # vm 僅 parse_failed 例外
    (dict(op="query", ok=False, reason_code="bad_request", vm=VM), ValueError),
    (dict(op="query", ok=True, vm="vm"), TypeError), (dict(op="query", ok=True, vm=object()), TypeError),
])
def test_response_invalid(kw, exc):
    with pytest.raises(exc):
        Resp(**kw)


@pytest.mark.parametrize("op", ["LIST", "Query", "QUERY", "List", " list", "list ", "query\n", "ｌｉｓｔ"])
@pytest.mark.parametrize("ok", [True, False])
def test_response_op_case_and_whitespace_variants_rejected(op, ok):
    with pytest.raises(ValueError):
        Resp(op, ok, None if ok else "bad_request")


def test_response_valid_dotted_names_still_ok():
    assert Resp("list", True, None, (".hidden.csv", "a..b.csv", "...csv", "a.csv"))


def test_response_frozen_and_fields():
    r = Resp("list", True, None, ("a.csv",))
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.ok = False                                             # type: ignore[misc]
    assert [f.name for f in dataclasses.fields(Resp)] == ["op", "ok", "reason_code", "filenames", "vm"]
    assert [f.name for f in dataclasses.fields(Req)] == ["op", "proof", "symbol", "filename"]
    assert isinstance(r.filenames, tuple)


# ── build_local_proof ────────────────────────────────────────────────
def test_blp_none_and_empty_headers():
    for h in (None, {}, types.MappingProxyType({})):
        p = blp("127.0.0.1", h)
        assert p == LocalProof("127.0.0.1", False, None, ())
    assert blp(None, None).bind_address is None


@pytest.mark.parametrize("host,want", [
    ("localhost", "localhost"), ("LocalHost", "localhost"), ("localhost:8501", "localhost"),
    ("LOCALHOST:8501", "localhost"), ("127.0.0.1:8501", "127.0.0.1"), ("127.0.0.1", "127.0.0.1"),
    ("[::1]:8501", "::1"), ("[::1]", "::1"), ("[FE80::1]:80", "fe80::1"), ("::1", "::1"),
    (" localhost ", "localhost"), ("example.com:443", "example.com"), ("", None), ("   ", None),
])
def test_blp_host_normalization(host, want):
    assert blp(None, {"Host": host}).request_host == want


@pytest.mark.parametrize("key", ["Host", "host", "HOST", " Host"])
def test_blp_host_key_case_insensitive(key):
    p = blp(None, {key: "LocalHost:1"})
    assert p.request_host == "localhost" and p.headers_present


def test_blp_unbracketed_ipv6_with_port_is_kept_verbatim_not_stripped():
    """未加括號的 `::1:8501`：保守方向——原樣保留為 IPv6 位址形（不去 port）。L3 不得因此視為本機。"""
    assert blp(None, {"Host": "::1:8501"}).request_host == "::1:8501"
    assert blp(None, {"Host": "[::1]:8501"}).request_host == "::1"


def test_blp_no_host_is_none_but_headers_present():
    p = blp(None, {"User-Agent": "x"})
    assert p.headers_present and p.request_host is None and p.proxy_header_names == ()


@pytest.mark.parametrize("host", [":8501", "a:b", "a:", "[::1", "[::1]x", "[::1]:", "[::1]:80a", "[::1]:123456",
                                  "a b", "[a:b]", "localhost:99999x", "ho\nst", "a:1:2x"])
def test_blp_malformed_host_raises(host):
    with pytest.raises(ValueError):
        blp(None, {"Host": host})


def test_blp_conflicting_hosts_raise_but_duplicate_same_ok():
    with pytest.raises(ValueError):
        blp(None, {"Host": "a.com", "host": "b.com"})
    assert blp(None, {"Host": "a.com:1", "host": "A.com"}).request_host == "a.com"
    assert blp(None, {"Host": "a.com", "host": ""}).request_host == "a.com"


def test_blp_proxy_header_detection():
    h = {"Host": "localhost", "X-Forwarded-For": "1.1.1.1", "x-forwarded-proto": "https", "Forwarded": "for=1",
         "X-Real-IP": "2.2.2.2", "Via": "1.1 p", "X-Forwarded-For ": "dup", "Accept": "*/*", "X-Request-Id": "1",
         "X-Forwarded": "no-prefix-match", "Xforwarded-for": "x"}
    p = blp("127.0.0.1", h)
    assert p.proxy_header_names == ("forwarded", "via", "x-forwarded-for", "x-forwarded-proto", "x-real-ip")
    assert list(p.proxy_header_names) == sorted(set(p.proxy_header_names))


@pytest.mark.parametrize("hdr", ["Forwarded", "X-Real-Ip", "Via", "X-Forwarded-Host", "X-FORWARDED-PORT"])
def test_blp_each_proxy_header_alone(hdr):
    p = blp(None, {hdr: "v"})
    assert p.proxy_header_names == (hdr.lower(),)


NEW_PROXY_NAMES = ("cf-connecting-ip", "cf-ray", "cdn-loop", "true-client-ip", "x-client-ip", "x-original-forwarded-for")
OLD_PROXY_NAMES = ("forwarded", "x-real-ip", "via")


def test_proxy_name_set_exact_and_documented_incomplete():
    assert R.PROXY_HEADER_EXACT == frozenset(OLD_PROXY_NAMES + NEW_PROXY_NAMES)
    assert R.PROXY_HEADER_PREFIX == "x-forwarded-" and isinstance(R.PROXY_HEADER_EXACT, frozenset)
    src = SRC.read_text(encoding="utf-8")
    assert "此清單不完備，不得單獨證明隔離" in src and "黑名單不是正向證明" in src and "L3 精確 loopback 驗證" in src
    assert "不完備" in (R.__doc__ or "") + (R.build_local_proof.__doc__ or "")


@pytest.mark.parametrize("name", NEW_PROXY_NAMES)
def test_each_new_proxy_name_detected_alone_and_in_proof_validation(name):
    assert blp(None, {name: "v"}).proxy_header_names == (name,)
    assert blp(None, {"Host": "localhost", name: "v"}).proxy_header_names == (name,)
    assert LocalProof(None, True, None, (name,))                       # 驗證端同步接受


@pytest.mark.parametrize("name", NEW_PROXY_NAMES)
def test_new_proxy_names_http_header_case_normalized(name):
    http_case = "-".join(w.capitalize() for w in name.split("-"))        # Cf-Connecting-Ip／X-Original-Forwarded-For
    for variant in (http_case, name.upper(), name, " " + http_case):
        assert blp(None, {variant: "v"}).proxy_header_names == (name,), variant
    with pytest.raises(ValueError):
        LocalProof(None, True, None, (http_case,))                      # LocalProof 本身只收小寫


def test_all_proxy_names_combined_sorted_deduped():
    allnames = OLD_PROXY_NAMES + NEW_PROXY_NAMES + ("x-forwarded-for", "x-forwarded-host")
    h = {}
    for i, n in enumerate(allnames):
        h[n.upper() if i % 2 else "-".join(w.capitalize() for w in n.split("-"))] = "v"
        h[n] = "dup"                                                       # 同名多種大小寫＝去重
    h["Host"] = "LocalHost:1"
    p = blp("127.0.0.1", h)
    assert p.proxy_header_names == tuple(sorted(allnames))
    assert list(p.proxy_header_names) == sorted(set(p.proxy_header_names)) and len(p.proxy_header_names) == 11
    assert LocalProof(p.bind_address, p.headers_present, p.request_host, p.proxy_header_names) == p


def test_new_names_combined_with_existing_three_classes():
    p = blp(None, {"Cf-Ray": "1", "Via": "p", "X-Forwarded-For": "1.1.1.1", "Forwarded": "for=1", "X-Real-IP": "2",
                   "True-Client-IP": "3", "CDN-Loop": "c"})
    assert p.proxy_header_names == ("cdn-loop", "cf-ray", "forwarded", "true-client-ip", "via", "x-forwarded-for", "x-real-ip")


@pytest.mark.parametrize("name", ["x-custom", "authorization", "cookie", "cf-visitor", "cf-ipcountry", "x-original-url",
                                  "x-original-forwarded", "x-client", "client-ip", "true-client", "cdn", "x-forwarded",
                                  "user-agent", "accept"])
def test_non_proxy_names_not_kept_and_values_never_in_output(name):
    secret = "SECRETVALUE-abc123"
    p = blp("127.0.0.1", {name: secret, "Host": "localhost"})
    assert p.proxy_header_names == () and secret not in repr(p) and secret not in str(dataclasses.astuple(p))
    with pytest.raises(ValueError):
        LocalProof(None, True, None, (name,))                              # 不在允許集合的任意名稱仍拒


def test_new_proxy_name_values_not_in_output():
    secret = "SECRETVALUE-xyz"
    p = blp(None, {n: secret for n in NEW_PROXY_NAMES})
    assert secret not in repr(p) and secret not in str(dataclasses.astuple(p))


def test_blp_no_proxy_headers_empty_tuple():
    assert blp(None, {"Host": "localhost", "Accept": "x"}).proxy_header_names == ()


def test_blp_bind_address_verbatim():
    for b in ("127.0.0.1", "0.0.0.0", "", "LOCALHOST", None):
        assert blp(b, {"Host": "localhost"}).bind_address == b


@pytest.mark.parametrize("bind,headers", [(1, None), (True, {}), (None, 5), (None, ["Host"]), (None, "Host: x"),
                                          (None, {1: "x"}), (None, {"Host": 5}), (None, {"Host": None}),
                                          (None, {"Host": b"localhost"})])
def test_blp_type_errors(bind, headers):
    with pytest.raises(TypeError):
        blp(bind, headers)                                       # type: ignore[arg-type]


def _streamlit_headers(pairs):
    from streamlit.runtime.context import StreamlitHeaders          # 只在測試檔 import（L0 模組本身不 import streamlit）
    return StreamlitHeaders(pairs)


def test_blp_with_real_streamlit_headers_type():
    h = _streamlit_headers([("Host", "LocalHost:8501"), ("X-Forwarded-For", "1.1.1.1"), ("Via", "p"), ("Accept", "*/*")])
    assert type(h).__name__ == "StreamlitHeaders"
    p = blp("127.0.0.1", h)
    assert p == LocalProof("127.0.0.1", True, "localhost", ("via", "x-forwarded-for"))
    assert blp(None, _streamlit_headers([])) == LocalProof(None, False, None, ())
    assert blp(None, _streamlit_headers([("Accept", "x")])).request_host is None


def test_blp_cannot_see_second_host_in_streamlit_headers_so_caller_must_use_get_all():
    """記錄已知限制（QA SF-1）：StreamlitHeaders 同名多值只回第一個；L0 看不到第二個 Host → 呼叫端須用 get_all("host")。"""
    h = _streamlit_headers([("Host", "localhost:8501"), ("host", "evil.example")])
    assert h.get_all("host") == ["localhost:8501", "evil.example"]           # 呼叫端可偵測
    assert blp(None, h).request_host == "localhost"                           # L0 只看到第一個（不得宣稱能防多 Host）


def test_docstrings_state_the_wiring_obligations():
    doc = R.__doc__ or ""
    for must in ("get_all", "StreamlitHeaders", "不能", "L3 列目錄時必須先過濾", "反斜線", "::1:8501", "不得"):
        assert must in doc, must
    assert 'headers.get_all("host")` 檢查筆數與值' in doc and "L0 沒有防多 Host，不得宣稱它有" in doc
    bdoc = R.build_local_proof.__doc__ or ""
    assert "get_all" in bdoc and "StreamlitHeaders" in bdoc and "不保證" in bdoc


def test_blp_is_pure_does_not_mutate_input():
    h = {"Host": "LocalHost:1", "Via": "x"}
    before = dict(h)
    blp(None, h)
    assert h == before


def test_blp_output_roundtrips_through_proof_validation():
    p = blp("::1", {"Host": "[::1]:8501", "Via": "x"})
    assert LocalProof(p.bind_address, p.headers_present, p.request_host, p.proxy_header_names) == p


# ── 模組純度／不含「是否本機」判斷 ────────────────────────────────────
def test_module_purity_zero_io_and_scope_guards():
    src = SRC.read_text(encoding="utf-8")
    assert check_vm_purity(src) == []
    assert check_capability_marker_scope(src, REL) == []
    tree = ast.parse(src)
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            assert n.level == 0
            mods.add(n.module or "")
    banned = {"streamlit", "os", "pathlib", "time", "datetime", "socket", "requests", "subprocess", "ipaddress",
              "urllib", "http", "shutil", "tempfile", "src", "app", "app_ui2"}
    assert not [m for m in mods if m.split(".")[0] in banned], mods
    assert all(m.split(".")[0] in {"__future__", "collections", "dataclasses", "typing", "shared"} for m in mods), mods
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not names & {"open", "exec", "eval", "__import__", "print", "input", "getattr", "setattr"}, names
    assert "session_state" not in src


def test_module_defines_no_locality_judgement_function():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    funcs = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    bad = [f for f in funcs if re.search(r"loopback|is_local|localhost|is_private|trusted|allowed|safe", f, re.I)]
    assert bad == [], bad
    assert not hasattr(R, "is_loopback") and not hasattr(R, "is_local")
    public_funcs = {n for n, v in vars(R).items() if isinstance(v, types.FunctionType) and not n.startswith("_") and v.__module__ == R.__name__}
    assert public_funcs == {"build_local_proof"}


def test_dataclasses_are_frozen_and_not_slotted_hacks():
    for cls in (LocalProof, Req, Resp):
        assert cls.__dataclass_params__.frozen is True                     # type: ignore[attr-defined]
