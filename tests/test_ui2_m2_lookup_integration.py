"""M2「本機日K檔查一檔」整合測試：真 `run_local_lookup`（L3）＋真 L5 邊界（views/target.py）＋真 L0／L1／L2，經 `app_ui2.py` 以 Streamlit AppTest 驅動。

取代 B 舊分支（ccr-0a83cbcc-nq4xl0@9875716d）針對 FinMind 抓取橋的同名測試（那份用「測試內替身」對映 #1289／#1290 的 API；
本機檔路徑走 `run_local_lookup`，不一對一，故改寫為對真模組的整合測試，且無任何「設計性轉紅」測試）。

全離線：合成 CSV 放 **repo 外** `tmp_path`；環境變數 `UI2_LOCAL_OHLCV_DIR` 由 monkeypatch 設定；`st.context.headers` 以
`streamlit.runtime.context.StreamlitHeaders` **真型別**注入（AppTest 無法直接指定請求標頭，故 patch `st.context`）；
`st.get_option("server.address")` 以 patch 注入。AppTest 預設的 `st.context.headers` 為空 StreamlitHeaders，所以不 patch 時＝無 Host。

涵蓋：flag-off 與既有 golden 逐元素相同、opt-in 條件、list／query、六態（OK／STALE／MISSING／FETCH_FAILED 紅／無法使用灰）、
ISO 日期、零價與缺值≠0、F1（量比缺值而非 0.0）、`basis_verified=False`／`source_user_declared=True`／`fetched_at=None` 漏傳即紅、
D-1 文案可見、L5 邊界全分支（0／1／2 筆 Host、無 get_all、malformed Host、非 loopback、proxy 標頭、bind、L3 丟含路徑例外）、
怪檔名、單一呼叫點（AST）、session 紀律。
"""
from __future__ import annotations

import ast
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import src.services.stock_local_lookup_service as svc
import src.ui2.views.target as target
from shared.ui2_contract import local_lookup_result as LLR
from shared.ui2_contract.local_lookup_request import (
    OP_LIST, OP_QUERY, REASON_BAD_REQUEST, REASON_CODE_SET, REASON_FILE_UNREADABLE, REASON_NO_REQUEST_CONTEXT,
    LocalLookupRequest, LocalLookupResponse,
)
from shared.ui2_contract.pages import MODE_CURATED, MODE_LOOKUP, P4_TARGET
from tests.test_ui2_lookup_p1 import _golden, _snapshot

ROOT = Path(__file__).resolve().parent.parent
APP_UI2 = ROOT / "app_ui2.py"
TARGET_PY = ROOT / "src" / "ui2" / "views" / "target.py"
ENV = "UI2_LOCAL_OHLCV_DIR"
LOCAL_RESULT = 'data-ui2-l1="local_lookup_result"'
NOTICE = 'data-ui2-l1="local_lookup_notice"'
_TPE = timezone(timedelta(hours=8))
SECRET_PATH_TEXT = "/home/SECRET_PRIVATE_DIR/secret-file-xyz.csv"


def _today() -> date:
    return datetime.now(_TPE).date()


def _csv(symbol: str = "0050", n: int = 30, end: date | None = None, volume_all: str | None = None,
         close_last: str | None = None, extra: str = "") -> bytes:
    end = end or (_today() - timedelta(days=1))
    lines = ["stock_id,date,open,high,low,close,volume"]
    for i in range(n):
        d = end - timedelta(days=(n - 1 - i))
        close = close_last if (close_last is not None and i == n - 1) else str(101 + i)
        vol = volume_all if volume_all is not None else str(1000 + i)
        lines.append(f"{symbol},{d.isoformat()},{100 + i},{102 + i},{99 + i},{close},{vol}")
    return ("\n".join(lines) + "\n" + extra).encode("utf-8")


class _Ctx:
    """`st.context` 的最小替身：只提供 `.headers`（真 StreamlitHeaders 或刻意的其他型別）。"""

    def __init__(self, headers):
        self.headers = headers


def _sh(pairs):
    from streamlit.runtime.context import StreamlitHeaders          # 只在測試檔 import（L5 守衛禁 streamlit.runtime）
    return StreamlitHeaders(pairs)


GOOD_HEADERS = [("Host", "localhost:8501"), ("Accept", "*/*"), ("User-Agent", "pytest")]


@pytest.fixture
def world(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    for k in ("STREAMLIT_SHARING_MODE", "STREAMLIT_RUNTIME_ENV", "UI2_LOOKUP_INPUT", "UI2_DIAG_ENABLE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv(ENV, str(data))
    ctx = _Ctx(_sh(GOOD_HEADERS))
    bind = {"v": "127.0.0.1"}
    real_get_option = st.get_option
    monkeypatch.setattr(st, "context", ctx, raising=False)
    monkeypatch.setattr(st, "get_option", lambda k: bind["v"] if k == "server.address" else real_get_option(k))
    calls = []
    real_run = svc.run_local_lookup

    def spy(request, **kw):
        calls.append(request)
        return real_run(request, **kw)

    monkeypatch.setattr(svc, "run_local_lookup", spy)
    return SimpleNamespace(data=data, ctx=ctx, bind=bind, calls=calls, monkeypatch=monkeypatch, tmp=tmp_path)


def put(world, name="a.csv", data: bytes | None = None):
    (world.data / name).write_bytes(_csv() if data is None else data)


def app(world=None, *, mode=MODE_LOOKUP, scenario="cold") -> AppTest:
    at = AppTest.from_file(str(APP_UI2), default_timeout=60)
    at.session_state["ui2_feed"] = "fake"
    at.session_state["ui2_page"] = P4_TARGET
    at.session_state["ui2_scenario"] = scenario
    at.session_state["ui2_target_mode"] = mode
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def submit(at: AppTest, symbol="0050", filename="a.csv") -> AppTest:
    at.text_input(key="ui2_lookup_text").set_value(symbol)
    if filename is not None:
        at.selectbox(key="ui2_local_file").set_value(filename)
    at.button[0].click().run(timeout=60)
    assert not at.exception, at.exception
    return at


def session_items(at: AppTest) -> dict:
    """AppTest 的 session 狀態（使用者鍵＋具名 widget；不含內部鍵）。

    Streamlit 的 AppTest 在新版（本專案 requirements 上限 <1.60 之外的版本，已於 1.67.0 實測）把 `at.session_state` 換成不再暴露
    `.filtered_state` 的包裝類別（改提供 `items()`／`keys()`／迭代，語意同為過濾後的使用者狀態）；本專案支援版本仍用 `.filtered_state`。
    兩條路徑取同一份資料——不跳過、不放寬任何斷言。"""
    ss = at.session_state
    try:
        return dict(ss.filtered_state)
    except AttributeError:
        return dict(ss.items())


def md(at: AppTest) -> str:
    """頁面 markdown（去掉 <style> 區塊：全域 CSS 本來就含 `ui2-chip--danger` 等 class 定義，不是畫面元素）。"""
    return re.sub(r"<style>.*?</style>", "", "\n".join(m.value for m in at.markdown), flags=re.S)


def assert_no_reason_codes(at: AppTest) -> None:
    """拒絕／失敗畫面不得印出任何固定原因碼（不洩漏是哪個檢查失敗）。"""
    page = md(at)
    for code in REASON_CODE_SET:
        assert code not in page, code


def assert_falls_back_to_plain_symbol_input(at: AppTest) -> None:
    """被拒絕／不可用時退回原代號輸入（有輸入框與送出鈕、沒有檔案選單）。"""
    assert [w for w in at.text_input if w.key == "ui2_lookup_text"]
    assert [b.label for b in at.button] == ["查詢"]
    assert not [w for w in at.selectbox if w.key == "ui2_local_file"]


def result_html(at: AppTest) -> str:
    hits = [m.value for m in at.markdown if LOCAL_RESULT in m.value]
    assert len(hits) == 1, hits
    return hits[0]


def visible(html: str) -> str:
    return re.sub(r"<[^>]*>", " ", html)


def cell(html: str, key: str) -> tuple[str, str]:
    m = re.search(rf'data-ll-key="{key}" data-ll-missing="(\d)"><span class="ui2-ll__k">[^<]*</span><span class="ui2-ll__v">([^<]*)</span>', html)
    assert m, key
    return m.group(1), m.group(2)


# ════════════════════════════════════════════════════════════════════
# 1. flag-off／opt-in
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("scenario", ["cold", "loaded", "missing", "unavailable"])
@pytest.mark.parametrize("mode", [MODE_CURATED, MODE_LOOKUP])
def test_flag_off_identical_to_existing_golden(monkeypatch, scenario, mode):
    monkeypatch.delenv(ENV, raising=False)
    monkeypatch.delenv("UI2_LOOKUP_INPUT", raising=False)
    at = AppTest.from_file(str(APP_UI2), default_timeout=60)
    at.session_state["ui2_feed"] = "fake"
    at.session_state["ui2_page"] = P4_TARGET
    at.session_state["ui2_scenario"] = scenario
    at.session_state["ui2_target_mode"] = mode
    at.run(timeout=60)
    assert not at.exception
    assert _snapshot(at) == _golden()[f"{scenario}|{mode}"]
    assert not any("ui2-ll" in m.value for m in at.markdown)


@pytest.mark.parametrize("val", [None, ""])
def test_env_unset_or_empty_means_entrypoint_does_not_exist(world, val):
    if val is None:
        world.monkeypatch.delenv(ENV)
    else:
        world.monkeypatch.setenv(ENV, val)
    put(world)
    at = app()
    assert not [w for w in at.selectbox if w.key == "ui2_local_file"] and not world.calls
    assert not any("ui2-ll" in m.value for m in at.markdown)


def test_callable_existing_is_not_an_opt_in():
    src = APP_UI2.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_read_local_ohlcv_opt_in")
    body = "\n".join(ast.unparse(st_) for st_ in fn.body[1:])                  # 不含 docstring
    assert "UI2_LOCAL_OHLCV_DIR" in body and "run_local_lookup" not in body and "secrets" not in body
    assert "ui2_dev" not in body


# ════════════════════════════════════════════════════════════════════
# 2. list／query 成功路徑
# ════════════════════════════════════════════════════════════════════
def test_list_shows_only_basenames_in_selectbox(world):
    put(world, "a.csv")
    put(world, "b.csv")
    (world.data / "notes.txt").write_text("x", encoding="utf-8")
    at = app()
    sb = at.selectbox(key="ui2_local_file")
    assert list(sb.options) == ["a.csv", "b.csv"] and sb.label == LLR.TEXT_LOCAL_FILE_LABEL == "本機日K檔選擇"
    assert str(world.data) not in md(at) and "/" not in "".join(sb.options)
    assert [c.op for c in world.calls] == [OP_LIST]


def test_query_ok_shows_all_required_fields_and_copy(world):
    put(world)
    at = submit(app())
    h = result_html(at)
    t = visible(h)
    end = (_today() - timedelta(days=1)).isoformat()
    for s in ("資料正常", "0050", "130.00", f"資料日 {end}", "抓取時間未知", "使用者自述，未經系統驗證",
              "價格口徑由使用者聲明為未調整原始價，系統未驗證；除權息日前後指標可能失真", "日K非即時",
              "🤖 研究解釋：尚未啟用 ⬜", "MA20", "MA240", "乖離20", "量比5", "支撐", "壓力"):
        assert s in t, s
    assert "價格為原始未調整價（未還原除權息）" not in h
    assert [c.op for c in world.calls][:1] == [OP_LIST] and OP_QUERY in [c.op for c in world.calls]
    assert cell(h, "volume") == ("0", "1,029")                       # 量為原值，不標股／張
    assert "股" not in t.replace("使用者", "") and "張" not in t
    assert cell(h, "ma240")[0] == "1" and cell(h, "ma240")[1] == LLR.TEXT_MISSING   # 30 根算不出 MA240 → 缺值字樣，不是 0
    assert cell(h, "ma20")[0] == "0"


def test_query_iso_date_and_loaded_chip_positive(world):
    put(world, data=_csv(end=_today() - timedelta(days=2)))
    h = result_html(submit(app()))
    assert re.search(r"資料日 \d{4}-\d{2}-\d{2}", visible(h)) and "ui2-chip--positive" in h


def test_stale_data_is_warning_not_ok(world):
    put(world, data=_csv(end=_today() - timedelta(days=40)))
    h = result_html(submit(app()))
    assert "資料過期" in h and "ui2-chip--warning" in h and "資料正常" not in h and "ui2-chip--danger" not in h


def test_zero_close_is_missing_never_zero_and_not_red(world):
    put(world, data=_csv(close_last="0"))
    at = submit(app())
    h = result_html(at)
    assert "資料未備" in h and "ui2-chip--danger" not in h                 # parse_failed 的缺值態：警示／灰，不是紅，不顯示 0.00
    assert "0.00" not in visible(h) and 'data-ll-has-data="0"' in h
    assert "查無此股" not in h


def test_f1_ratio_overflow_is_missing_not_zero(world):
    put(world, data=_csv(volume_all="1.7e308"))
    h = result_html(submit(app()))
    miss, val = cell(h, "vol_ratio5")
    assert (miss, val) == ("1", LLR.TEXT_MISSING) and "0.00 倍" not in h


def test_wrong_symbol_in_file_gives_missing_not_other_stock(world):
    put(world, data=_csv(symbol="2330"))
    h = result_html(submit(app(), symbol="0050"))
    assert 'data-ll-has-data="0"' in h and "130.00" not in h


def test_invalid_symbol_input_is_grey_and_never_queries(world):
    put(world)
    at = app()
    at = submit(at, symbol="x")
    assert not any(LOCAL_RESULT in m.value for m in at.markdown)
    assert "代號無效" in md(at) and OP_QUERY not in [c.op for c in world.calls]


def test_curated_mode_shows_selector_but_no_result_and_no_query(world):
    put(world)
    at = app(mode=MODE_CURATED)
    assert at.selectbox(key="ui2_local_file").options == ["a.csv"]
    at = submit(at)
    assert not any(LOCAL_RESULT in m.value for m in at.markdown) and OP_QUERY not in [c.op for c in world.calls]


def test_result_persists_across_rerun_without_storing_data(world):
    put(world)
    at = submit(app())
    at.run(timeout=60)
    assert LOCAL_RESULT in md(at)
    items = session_items(at)
    assert "ui2_lookup_symbol" in items and "ui2_local_queried" in items            # 確實取到了狀態（防「空迴圈假通過」）
    for k, v in items.items():
        if k.startswith("FormSubmitter:"):                                        # Streamlit 內部的表單提交旗標
            continue
        assert k.startswith("ui2_") and not re.search(r"hold|strategy|sheet|portfolio", k, re.I), k
        assert isinstance(v, (str, bool, int, type(None))), (k, type(v))
        assert "130.00" not in str(v) and "stock_id" not in str(v)


def test_no_files_in_directory_is_grey_note(world):
    at = app()
    assert not [w for w in at.selectbox if w.key == "ui2_local_file"]
    assert LLR.TEXT_LOCAL_NO_FILES in md(at) and NOTICE in md(at) and "ui2-chip--danger" not in md(at)
    assert_no_reason_codes(at)
    assert [w for w in at.text_input if w.key == "ui2_lookup_text"]


def test_weird_filenames_are_filtered_and_do_not_break_page(world):
    put(world, "ok.csv")
    for name in ("a:b.csv", "CON.csv", "a\\b.csv", "x.csv."):
        try:
            put(world, name)
        except OSError:
            pass
    at = app()
    assert list(at.selectbox(key="ui2_local_file").options) == ["ok.csv"]
    assert not at.exception


# ════════════════════════════════════════════════════════════════════
# 3. L5 邊界：全分支；拒絕＝固定灰字、L3 未被呼叫（零檔案系統）
# ════════════════════════════════════════════════════════════════════
def _assert_rejected(at, world):
    assert not [w for w in at.selectbox if w.key == "ui2_local_file"]
    assert world.calls == [], "L3 不得在 L5 邊界拒絕時被呼叫"
    assert LLR.TEXT_LOCAL_UNAVAILABLE in md(at) and "ui2-chip--danger" not in md(at)
    assert str(world.data) not in md(at)
    assert_no_reason_codes(at)
    assert_falls_back_to_plain_symbol_input(at)


@pytest.mark.parametrize("headers", [
    _sh([]),                                                                  # 0 筆 Host（空）
    _sh([("Accept", "*/*")]),                                                 # 有標頭但無 Host
])
def test_l5_zero_hosts_rejected_before_l3(world, headers):
    put(world)
    world.ctx.headers = headers
    _assert_rejected(app(), world)


def test_l5_two_hosts_rejected_before_l3_even_though_first_is_loopback(world):
    put(world)
    world.ctx.headers = _sh([("Host", "localhost:8501"), ("host", "evil.example")])
    assert world.ctx.headers["host"] == "localhost:8501"                       # StreamlitHeaders 只回第一個：L5 必須先數
    assert len(world.ctx.headers.get_all("host")) == 2
    _assert_rejected(app(), world)


@pytest.mark.parametrize("headers", [None, {"Host": "localhost"}, ["Host", "localhost"], "Host: localhost", 5])
def test_l5_no_get_all_means_no_request_context(world, headers):
    put(world)
    world.ctx.headers = headers
    _assert_rejected(app(), world)


@pytest.mark.parametrize("host", [":8501", "a:b", "[::1", "[::1]x", "a b", "[a:b]"])
def test_l5_malformed_host_is_bad_request_before_l3(world, host):
    put(world)
    world.ctx.headers = _sh([("Host", host)])
    _assert_rejected(app(), world)


def test_l5_missing_context_attribute_is_rejected(world):
    put(world)
    world.monkeypatch.setattr(st, "context", SimpleNamespace(), raising=False)         # 沒有 headers 屬性
    _assert_rejected(app(), world)


def test_l5_get_option_failure_means_bind_unknown_rejected_by_l3(world):
    put(world)
    world.monkeypatch.setattr(st, "get_option", lambda k: (_ for _ in ()).throw(RuntimeError(SECRET_PATH_TEXT)))
    at = app()
    assert not [w for w in at.selectbox if w.key == "ui2_local_file"] and SECRET_PATH_TEXT not in md(at)
    assert LLR.TEXT_LOCAL_UNAVAILABLE in md(at)


@pytest.mark.parametrize("name,mut", [
    ("host_not_loopback", lambda w: setattr(w.ctx, "headers", _sh([("Host", "example.com")]))),
    ("host_with_127_0_0_2", lambda w: setattr(w.ctx, "headers", _sh([("Host", "127.0.0.2:8501")]))),
    ("proxy_header", lambda w: setattr(w.ctx, "headers", _sh(GOOD_HEADERS + [("X-Forwarded-For", "1.2.3.4")]))),
    ("cf_header", lambda w: setattr(w.ctx, "headers", _sh(GOOD_HEADERS + [("Cf-Connecting-Ip", "1.2.3.4")]))),
    ("bind_all_interfaces", lambda w: w.bind.update(v="0.0.0.0")),
    ("bind_none", lambda w: w.bind.update(v=None)),
])
def test_l3_rejections_are_grey_fixed_sentence_and_leak_nothing(world, name, mut):
    put(world)
    mut(world)
    at = app()
    assert not [w for w in at.selectbox if w.key == "ui2_local_file"]
    assert LLR.TEXT_LOCAL_UNAVAILABLE in md(at) and "ui2-chip--danger" not in md(at)
    assert str(world.data) not in md(at) and "a.csv" not in md(at)
    assert_no_reason_codes(at)
    assert_falls_back_to_plain_symbol_input(at)


def test_good_loopback_variants_are_accepted(world):
    put(world)
    for host in ("localhost:8501", "127.0.0.1:8501", "[::1]:8501", "LOCALHOST"):
        world.ctx.headers = _sh([("Host", host)])
        assert app().selectbox(key="ui2_local_file").options == ["a.csv"], host


# ── L3 丟含路徑例外：頁面與 log 皆不含 ───────────────────────────────
def test_l3_exception_with_path_is_neither_shown_nor_logged(world, capsys):
    put(world)

    def boom(request, **kw):
        raise OSError(13, SECRET_PATH_TEXT)

    world.monkeypatch.setattr(svc, "run_local_lookup", boom)
    at = app()
    out = capsys.readouterr()
    assert SECRET_PATH_TEXT not in md(at) and "SECRET_PRIVATE_DIR" not in md(at)
    assert SECRET_PATH_TEXT not in out.out + out.err and "SECRET_PRIVATE_DIR" not in out.out + out.err
    assert "failed: PermissionError" in out.out                                         # 只記例外類別名
    assert LLR.TEXT_LOCAL_UNAVAILABLE in md(at) or "讀取失敗" in md(at)


def test_l3_exception_on_query_shows_red_fixed_failure(world, capsys):
    put(world)
    at = app()
    real = svc.run_local_lookup

    def flaky(request, **kw):
        if request.op == OP_QUERY:
            raise RuntimeError(SECRET_PATH_TEXT)
        return real(request, **kw)

    world.monkeypatch.setattr(svc, "run_local_lookup", flaky)
    at = submit(at)
    out = capsys.readouterr()
    assert "ui2-chip--danger" in md(at) and "讀取失敗" in md(at) and "讀取失敗，請稍後再試" in md(at)
    assert SECRET_PATH_TEXT not in md(at) + out.out + out.err and "failed: RuntimeError" in out.out
    assert_no_reason_codes(at)


@pytest.mark.parametrize("bad", ["not a response", None, 5, LocalLookupResponse(op=OP_LIST, ok=True)])
def test_l3_wrong_return_type_or_op_is_fixed_code(world, bad):
    put(world)
    world.monkeypatch.setattr(svc, "run_local_lookup", lambda request, **kw: bad if request.op == OP_QUERY else
                              real_list(request))
    at = app()
    at = submit(at)
    assert "讀取失敗" in md(at) and "ui2-chip--danger" in md(at)
    assert_no_reason_codes(at)


def real_list(request):
    return LocalLookupResponse(op=OP_LIST, ok=True, filenames=("a.csv",))


# ── call_local 單元（list 帶 symbol → bad_request，callable 不被呼叫）────────────────
def _proof_ok():
    p, code = target.derive_local_proof(_sh(GOOD_HEADERS), "127.0.0.1")
    assert code is None
    return p


def test_call_local_list_with_symbol_is_bad_request_and_callable_untouched(monkeypatch):
    monkeypatch.setattr(target, "_read_proof", lambda: (_proof_ok(), None))
    seen = []
    r = target.call_local(lambda req: seen.append(req), OP_LIST, symbol="0050")
    assert (r.ok, r.reason_code) == (False, REASON_BAD_REQUEST) and seen == []
    r = target.call_local(lambda req: seen.append(req), OP_QUERY)                         # query 缺 symbol／filename
    assert (r.ok, r.reason_code) == (False, REASON_BAD_REQUEST) and seen == []


def test_call_local_proof_rejection_never_calls_callable(monkeypatch):
    monkeypatch.setattr(target, "_read_proof", lambda: (None, REASON_NO_REQUEST_CONTEXT))
    seen = []
    r = target.call_local(lambda req: seen.append(req), OP_LIST)
    assert (r.ok, r.reason_code) == (False, REASON_NO_REQUEST_CONTEXT) and seen == []


def test_call_local_wraps_every_exception_type_into_fixed_code(monkeypatch, capsys):
    monkeypatch.setattr(target, "_read_proof", lambda: (_proof_ok(), None))
    for exc in (RuntimeError("x" + SECRET_PATH_TEXT), OSError(SECRET_PATH_TEXT), ValueError(SECRET_PATH_TEXT),
                KeyError(SECRET_PATH_TEXT), Exception(SECRET_PATH_TEXT)):
        def boom(req, e=exc):
            raise e
        r = target.call_local(boom, OP_LIST)
        assert (r.ok, r.reason_code) == (False, REASON_FILE_UNREADABLE)
    out = capsys.readouterr()
    assert SECRET_PATH_TEXT not in out.out + out.err


def test_call_local_forwards_exact_request_to_callable(monkeypatch):
    monkeypatch.setattr(target, "_read_proof", lambda: (_proof_ok(), None))
    seen = []

    def ok(req):
        seen.append(req)
        return LocalLookupResponse(op=req.op, ok=True, filenames=("a.csv",)) if req.op == OP_LIST else \
            LocalLookupResponse(op=req.op, ok=False, reason_code="file_invalid")

    assert target.call_local(ok, OP_LIST).filenames == ("a.csv",)
    assert target.call_local(ok, OP_QUERY, symbol="0050", filename="a.csv").reason_code == "file_invalid"
    assert [(r.op, r.symbol, r.filename) for r in seen] == [(OP_LIST, None, None), (OP_QUERY, "0050", "a.csv")]
    assert all(isinstance(r, LocalLookupRequest) for r in seen)


# ── derive_local_proof 純函式分支 ──────────────────────────────────────
def test_derive_local_proof_branches():
    d = target.derive_local_proof
    assert d(None, "127.0.0.1") == (None, REASON_NO_REQUEST_CONTEXT)
    assert d({"Host": "x"}, "127.0.0.1") == (None, REASON_NO_REQUEST_CONTEXT)
    assert d(_sh([]), "127.0.0.1") == (None, REASON_NO_REQUEST_CONTEXT)
    assert d(_sh([("Host", "a"), ("Host", "b")]), "127.0.0.1") == (None, REASON_BAD_REQUEST)
    assert d(_sh([("Host", ":1")]), "127.0.0.1") == (None, REASON_BAD_REQUEST)
    assert d(_sh([("Host", "localhost")]), 5) == (None, REASON_BAD_REQUEST)                  # bind 非 str
    p, c = d(_sh([("Host", "LocalHost:8501"), ("X-Forwarded-For", "1"), ("Via", "p")]), "127.0.0.1")
    assert c is None and (p.bind_address, p.headers_present, p.request_host, p.proxy_header_names) == (
        "127.0.0.1", True, "localhost", ("via", "x-forwarded-for"))
    p, c = d(_sh([("Host", "localhost")]), None)
    assert c is None and p.bind_address is None

    class BadGetAll:
        def get_all(self, k):
            raise RuntimeError("x")
    assert d(BadGetAll(), "127.0.0.1") == (None, REASON_BAD_REQUEST)

    class WeirdGetAll:
        def get_all(self, k):
            return "localhost"
    assert d(WeirdGetAll(), "127.0.0.1") == (None, REASON_BAD_REQUEST)

    class NonStrHost:
        def get_all(self, k):
            return [5]
    assert d(NonStrHost(), "127.0.0.1") == (None, REASON_BAD_REQUEST)


# ════════════════════════════════════════════════════════════════════
# 4. 漏傳即紅（行為／spy）
# ════════════════════════════════════════════════════════════════════
def test_basis_verified_false_and_source_user_declared_true_are_visible_and_passed(world):
    put(world)
    seen = {}
    real_facts, real_result = svc.build_stock_research_facts, svc.build_local_lookup_result
    real_quote = svc.build_quote_view

    def facts(bars, **kw):
        seen["facts_kw"] = dict(kw)
        return real_facts(bars, **kw)

    def result(quote, **kw):
        seen["result_kw"] = dict(kw)
        return real_result(quote, **kw)

    def quote(sel, **kw):
        seen.setdefault("quote_kw", []).append(dict(kw))
        return real_quote(sel, **kw)

    world.monkeypatch.setattr(svc, "build_stock_research_facts", facts)
    world.monkeypatch.setattr(svc, "build_local_lookup_result", result)
    world.monkeypatch.setattr(svc, "build_quote_view", quote)
    h = result_html(submit(app()))
    assert seen["facts_kw"]["basis_verified"] is False
    assert seen["result_kw"]["source_user_declared"] is True
    assert any(q.get("fetched_at") is None and q.get("loaded") is True for q in seen["quote_kw"])
    t = visible(h)
    assert "使用者自述，未經系統驗證" in t and "抓取時間未知" in t and "系統未驗證" in t


# ════════════════════════════════════════════════════════════════════
# 5. 靜態：單一呼叫點／app_ui2 形狀
# ════════════════════════════════════════════════════════════════════
def test_target_py_has_exactly_one_direct_call_of_the_injected_callable_and_it_is_call_local():
    tree = ast.parse(TARGET_PY.read_text(encoding="utf-8"))
    parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "local_lookup"]
    assert len(calls) == 1
    n, fn = calls[0], None
    while n in parents:
        n = parents[n]
        if isinstance(n, ast.FunctionDef):
            fn = n
            break
    assert fn is not None and fn.name == "call_local"
    # 其他函式只把 callable 當參數傳遞（不呼叫）；且沒有 attribute 形式的呼叫（local_lookup.xxx(...)）
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                and n.value.id == "local_lookup"]
    callers_of_call_local = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                             and n.func.id == "call_local"]
    assert len(callers_of_call_local) == 2                                    # list 與 query 各一處，皆經 call_local


def test_target_py_imports_no_l1_l2_l3():
    tree = ast.parse(TARGET_PY.read_text(encoding="utf-8"))
    mods = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
    assert not [m for m in mods if m.startswith(("src.data", "src.compute")) or (
        m.startswith("src.services") and not m.startswith("src.services.ui2"))]
    assert "src.services.stock_local_lookup_service" not in mods


def test_app_ui2_shape_two_exact_imports_and_ifexp_kwargs():
    src = APP_UI2.read_text(encoding="utf-8")
    tree = ast.parse(src)
    svc_imps = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("src.services")]
    assert sorted((n.module, tuple((a.name, a.asname) for a in n.names)) for n in svc_imps) == [
        ("src.services.connection_diag_service", (("run_connection_check", None),)),
        ("src.services.stock_local_lookup_service", (("run_local_lookup", None),))]
    runs = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "run"]
    assert len(runs) == 1
    kw = {k.arg: k.value for k in runs[0].keywords}
    diag, loc = kw["diag_check"], kw["local_lookup"]
    assert ast.unparse(diag) == "run_connection_check if _read_diag_flag() else None"
    assert isinstance(loc, ast.IfExp) and ast.unparse(loc) == "run_local_lookup if _read_local_ohlcv_opt_in() else None"
    for name in ("run_connection_check", "run_local_lookup"):
        names = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == name]
        assert len(names) == 1, name                                            # import 之外只有 IfExp 一處
        assert not any(isinstance(n, ast.Attribute) and n.attr == name for n in ast.walk(tree))
    assert svc.ENV_LOCAL_OHLCV_DIR == ENV                                        # app_ui2 的字面值與 L3 常數同值
    assert 'os.environ.get("UI2_LOCAL_OHLCV_DIR")' in src


def test_run_signature_local_lookup_defaults_to_none_and_style_only_when_given():
    import inspect

    from src.ui2.shell import app as shell_app
    sig = inspect.signature(shell_app.run)
    assert sig.parameters["local_lookup"].default is None
    src = Path(shell_app.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    run_fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run")
    styles = [n for n in ast.walk(run_fn) if isinstance(n, ast.Name) and n.id == "LOCAL_LOOKUP_RESULT_STYLE"]
    assert len(styles) == 1
    ifs = [n for n in ast.walk(run_fn) if isinstance(n, ast.If) and "LOCAL_LOOKUP_RESULT_STYLE" in ast.unparse(n)]
    assert ifs and ast.unparse(ifs[0].test) == "local_lookup is not None"


def test_local_style_is_style_wrapped_css_constant():
    from src.ui2.components.html import LOCAL_LOOKUP_RESULT_CSS
    from src.ui2.shell.css import LOCAL_LOOKUP_RESULT_STYLE
    assert LOCAL_LOOKUP_RESULT_STYLE.strip().startswith("<style>") and LOCAL_LOOKUP_RESULT_STYLE.strip().endswith("</style>")
    assert LOCAL_LOOKUP_RESULT_CSS in LOCAL_LOOKUP_RESULT_STYLE and "ui2-ll__cols" in LOCAL_LOOKUP_RESULT_STYLE


def test_style_injected_only_when_opt_in(world):
    put(world)
    assert any("ui2-ll__cols" in m.value for m in app().markdown)
    world.monkeypatch.delenv(ENV)
    assert not any("ui2-ll__cols" in m.value for m in app().markdown)


# ════════════════════════════════════════════════════════════════════
# 6. SF-1：已送出的（代號、檔名）與目前輸入不一致時，不得殘留／顯示舊結果
# ════════════════════════════════════════════════════════════════════
def _two_files(world):
    put(world, "a.csv", _csv())                                                 # 末列收盤 130
    put(world, "b.csv", _csv(close_last="130.5"))                                 # 末列收盤 130.5（仍在 low~high 內）


def _shown_symbol(html: str) -> str | None:
    m = re.search(r'<strong class="ui2-ll__symbol">([^<]*)</strong>', html)
    return m.group(1) if m else None


def test_sf1_selected_file_disappears_no_stale_result(world):
    _two_files(world)
    at = submit(app(), symbol="0050", filename="b.csv")
    assert "130.50" in result_html(at)
    (world.data / "b.csv").unlink()
    at.run(timeout=60)
    assert not at.exception
    assert list(at.selectbox(key="ui2_local_file").options) == ["a.csv"]
    assert at.selectbox(key="ui2_local_file").value == "a.csv"
    assert not any(LOCAL_RESULT in m.value for m in at.markdown), "選單已回預設 a.csv，不得自動顯示 (代號, a.csv) 的結果"
    assert "130.00" not in md(at) and "130.50" not in md(at)
    assert at.session_state["ui2_local_queried"] == ""                          # 旗標已清掉


def test_sf1_page_switch_and_back_clears_stale_result(world):
    _two_files(world)
    at = submit(app(), symbol="0050", filename="b.csv")
    assert LOCAL_RESULT in md(at)
    at.session_state["ui2_page"] = "p4_market"
    at.run(timeout=60)
    assert not at.exception
    at.session_state["ui2_page"] = P4_TARGET
    at.run(timeout=60)
    assert not at.exception
    assert at.text_input(key="ui2_lookup_text").value == ""                      # widget 狀態被清空（Streamlit 行為）
    assert not any(LOCAL_RESULT in m.value for m in at.markdown) and "130.50" not in md(at)
    assert "ui2-lookup-status__symbol" not in md(at), "狀態列不得顯示已失效的舊代號"


def test_sf1_stale_flags_without_matching_widgets_never_show_a_result(world):
    """模擬『伺服器端殘留旗標、但 widget 已被重設』：只有旗標與已送出檔名，輸入框／選單是預設值。"""
    _two_files(world)
    at = AppTest.from_file(str(APP_UI2), default_timeout=60)
    at.session_state["ui2_feed"] = "fake"
    at.session_state["ui2_page"] = P4_TARGET
    at.session_state["ui2_scenario"] = "cold"
    at.session_state["ui2_target_mode"] = MODE_LOOKUP
    at.session_state["ui2_local_queried"] = "1"
    at.session_state["ui2_lookup_symbol"] = "0050"
    at.session_state["ui2_local_submitted_file"] = "b.csv"
    at.run(timeout=60)
    assert not at.exception
    assert not any(LOCAL_RESULT in m.value for m in at.markdown)
    assert OP_QUERY not in [c.op for c in world.calls]                           # 連查詢都不會發出


def test_sf1_stale_flags_with_same_file_but_empty_symbol_input_never_show_a_result(world):
    """已送出檔名恰等於目前選單預設值，但輸入框是空的（切頁再回）→ 仍不得顯示（代號必須等於目前輸入）。"""
    _two_files(world)
    at = AppTest.from_file(str(APP_UI2), default_timeout=60)
    at.session_state["ui2_feed"] = "fake"
    at.session_state["ui2_page"] = P4_TARGET
    at.session_state["ui2_scenario"] = "cold"
    at.session_state["ui2_target_mode"] = MODE_LOOKUP
    at.session_state["ui2_local_queried"] = "1"
    at.session_state["ui2_lookup_symbol"] = "0050"
    at.session_state["ui2_local_submitted_file"] = "a.csv"
    at.run(timeout=60)
    assert not at.exception
    assert not any(LOCAL_RESULT in m.value for m in at.markdown) and OP_QUERY not in [c.op for c in world.calls]


def test_sf1_fresh_session_has_no_result(world):
    _two_files(world)
    submit(app(), symbol="0050", filename="b.csv")
    at2 = app()                                                                  # 重新整理＝新 session
    assert not any(LOCAL_RESULT in m.value for m in at2.markdown)


def test_sf1_result_always_matches_current_inputs(world):
    """不論 AppTest 是否模擬表單延遲提交：只要畫出結果，其代號與檔案必須等於目前輸入框／選單。"""
    _two_files(world)
    at = submit(app(), symbol="0050", filename="b.csv")
    assert _shown_symbol(result_html(at)) == "0050" and "130.50" in result_html(at)
    at.selectbox(key="ui2_local_file").set_value("a.csv")
    at.run(timeout=60)
    assert not at.exception
    hits = [m.value for m in at.markdown if LOCAL_RESULT in m.value]
    if hits:
        assert at.selectbox(key="ui2_local_file").value == "b.csv" and "130.50" in hits[0]
        assert "130.00" not in hits[0]
    at.text_input(key="ui2_lookup_text").set_value("2330")
    at.run(timeout=60)
    assert not at.exception
    hits = [m.value for m in at.markdown if LOCAL_RESULT in m.value]
    for h in hits:
        assert _shown_symbol(h) == at.text_input(key="ui2_lookup_text").value or _shown_symbol(h) == "0050" and at.text_input(
            key="ui2_lookup_text").value == "0050"


def test_sf1_change_file_then_submit_shows_the_new_file_only(world):
    _two_files(world)
    at = submit(app(), symbol="0050", filename="b.csv")
    assert "130.50" in result_html(at)
    at = submit(at, symbol="0050", filename="a.csv")
    h = result_html(at)
    assert "130.00" in h and "130.50" not in h


def test_sf1_change_symbol_then_submit_shows_the_new_symbol_only(world):
    put(world, "a.csv", _csv(symbol="0050"))
    put(world, "b.csv", _csv(symbol="2330", close_last="129"))
    at = submit(app(), symbol="0050", filename="a.csv")
    assert _shown_symbol(result_html(at)) == "0050"
    at = submit(at, symbol="2330", filename="b.csv")
    h = result_html(at)
    assert _shown_symbol(h) == "2330" and "129.00" in h and "130.00" not in h


def test_sf1_submitted_file_key_is_ui2_prefixed_and_clean():
    assert target.KEY_LOCAL_SUBMITTED_FILE == "ui2_local_submitted_file"
    assert not re.search(r"lookup|hold|strategy|sheet|portfolio", target.KEY_LOCAL_SUBMITTED_FILE, re.I)


# ════════════════════════════════════════════════════════════════════
# 7. SF-2（待 P／總管確認的 UI 處置）：查詢摘要卡、拒絕說明在兩模式可見
# ════════════════════════════════════════════════════════════════════
SUMMARY_LABEL = "現在狀態（查詢摘要）"


def test_sf2_summary_card_hidden_only_after_a_local_query_ran(world):
    put(world)
    at = app()
    assert SUMMARY_LABEL in md(at) and 'data-ui2-q="q1"' in md(at)               # 未查詢：維持現狀
    at = submit(at)
    page = md(at)
    assert LOCAL_RESULT in page and SUMMARY_LABEL not in page and 'data-ui2-q="q1"' not in page
    assert 'data-ui2-q="q2"' in page and 'data-ui2-q="q3"' in page               # 其餘第一屏列保留


def test_sf2_summary_card_stays_when_rejected_or_curated(world):
    put(world)
    at = app(mode=MODE_CURATED)
    assert 'data-ui2-q="q1"' in md(at)
    world.ctx.headers = _sh([])
    at = app()
    assert SUMMARY_LABEL in md(at) and 'data-ui2-q="q1"' in md(at)               # 被拒絕：維持現狀


def test_sf2_failed_query_also_drops_the_contradicting_card(world):
    put(world)
    at = app()
    real = svc.run_local_lookup

    def flaky(request, **kw):
        if request.op == OP_QUERY:
            raise RuntimeError(SECRET_PATH_TEXT)
        return real(request, **kw)

    world.monkeypatch.setattr(svc, "run_local_lookup", flaky)
    at = submit(at)
    assert "讀取失敗" in md(at) and SUMMARY_LABEL not in md(at)


@pytest.mark.parametrize("mode", [MODE_CURATED, MODE_LOOKUP])
def test_sf2_rejection_note_visible_in_both_modes(world, mode):
    put(world)
    world.ctx.headers = _sh([])
    at = app(mode=mode)
    assert LLR.TEXT_LOCAL_UNAVAILABLE in md(at) and NOTICE in md(at)
    assert_no_reason_codes(at)
    assert_falls_back_to_plain_symbol_input(at)


@pytest.mark.parametrize("mode", [MODE_CURATED, MODE_LOOKUP])
def test_sf2_empty_directory_note_visible_in_both_modes(world, mode):
    at = app(mode=mode)
    assert LLR.TEXT_LOCAL_NO_FILES in md(at) and NOTICE in md(at)


def test_sf2_rejection_note_sits_with_the_input_before_the_summary_card(world):
    put(world)
    world.ctx.headers = _sh([])
    page = md(app())
    assert page.index(LLR.TEXT_LOCAL_UNAVAILABLE) < page.index(SUMMARY_LABEL)


def test_sf2_first_screen_default_output_is_unchanged():
    """`target_first_screen_html` 的預設輸出（既有 render／render_with_lookup 使用）不受 show_summary 參數影響。"""
    import inspect

    from src.ui2.components.html import target_first_screen_html
    sig = inspect.signature(target_first_screen_html)
    assert sig.parameters["show_summary"].default is True
    src = TARGET_PY.read_text(encoding="utf-8")
    assert src.count("show_summary=False") == 1                                  # 只有新入口的一處傳 False


# ════════════════════════════════════════════════════════════════════
# 8. 差額 QA 補洞（N12／N15）
# ════════════════════════════════════════════════════════════════════
FAKE_LOOKUP_RESULT = 'data-ui2-queried="true"'                                 # FAKE 場景「已查詢」結果區的錨點（lookup_result_html）


def test_n12_fake_loaded_lookup_result_exists_when_local_mode_is_off(monkeypatch):
    """對照組：FAKE `loaded` 場景的即時查一檔模式（旗標關）本來就畫出 FAKE 結果區——下面的拒絕測試才有意義。"""
    monkeypatch.delenv(ENV, raising=False)
    at = app(scenario="loaded")
    assert FAKE_LOOKUP_RESULT in md(at)


@pytest.mark.parametrize("how", ["no_host", "two_hosts", "non_loopback", "empty_directory"])
def test_n12_rejected_or_unavailable_never_brings_back_the_fake_result_area(world, how):
    put(world)
    if how == "no_host":
        world.ctx.headers = _sh([])
    elif how == "two_hosts":
        world.ctx.headers = _sh([("Host", "localhost"), ("host", "evil.example")])
    elif how == "non_loopback":
        world.ctx.headers = _sh([("Host", "example.com")])
    else:
        (world.data / "a.csv").unlink()
    at = app(scenario="loaded")
    page = md(at)
    assert FAKE_LOOKUP_RESULT not in page and "ui2-lookup__head" not in page and "ui2-lookup__add" not in page
    assert NOTICE in page                                                      # 灰字說明仍在


def test_n15_curated_mode_submitted_and_matching_keeps_the_summary_row(world):
    """curated＋已送出且條件相符：不執行查詢、不顯示本機結果，且不得誤判為『查詢已執行』而隱藏「查詢摘要」列。"""
    put(world)
    at = app(mode=MODE_CURATED)
    at = submit(at, symbol="0050", filename="a.csv")
    assert at.session_state["ui2_local_queried"] == "1"                          # 已送出且仍相符（旗標保留）
    page = md(at)
    assert 'data-ui2-q="q1"' in page and SUMMARY_LABEL in page
    assert not any(LOCAL_RESULT in m.value for m in at.markdown) and OP_QUERY not in [c.op for c in world.calls]
    # 切到即時查一檔模式：同一組（代號、檔名）仍相符 → 才查詢並隱藏摘要列
    at.session_state["ui2_target_mode"] = MODE_LOOKUP
    at.run(timeout=60)
    assert not at.exception and LOCAL_RESULT in md(at) and SUMMARY_LABEL not in md(at)


# ════════════════════════════════════════════════════════════════════
# 9. T2：「把接線整個拿掉」必紅（A 的 check_app_ui2_source 在完全沒有引用時視為合規，不會擋）
# ════════════════════════════════════════════════════════════════════
def _app_tree():
    return ast.parse(APP_UI2.read_text(encoding="utf-8"))


def test_t2_app_ui2_must_be_wired_exactly_once():
    """app_ui2.py **必須**含：恰一個 run_local_lookup import、IfExp 注入、_read_local_ohlcv_opt_in（os.environ.get 讀 UI2_LOCAL_OHLCV_DIR）。"""
    tree = _app_tree()
    imps = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "src.services.stock_local_lookup_service"]
    assert len(imps) == 1 and [(a.name, a.asname) for a in imps[0].names] == [("run_local_lookup", None)] and imps[0].level == 0
    runs = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "run"]
    assert len(runs) == 1
    loc = {k.arg: k.value for k in runs[0].keywords}.get("local_lookup")
    assert isinstance(loc, ast.IfExp) and ast.unparse(loc) == "run_local_lookup if _read_local_ohlcv_opt_in() else None"
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_read_local_ohlcv_opt_in"]
    assert len(fns) == 1
    body = "\n".join(ast.unparse(x) for x in fns[0].body[1:])
    assert "os.environ.get('UI2_LOCAL_OHLCV_DIR')" in body and body.count("UI2_LOCAL_OHLCV_DIR") == 1


@pytest.fixture
def run_spy(monkeypatch):
    """攔截 app_ui2 呼叫的 `src.ui2.shell.run`：記錄收到的關鍵字參數，再轉呼叫真的 run。"""
    import src.ui2.shell as shell_pkg
    got: list[dict] = []
    real = shell_pkg.run

    def spy(*a, **kw):
        got.append(dict(kw))
        return real(*a, **kw)

    monkeypatch.setattr(shell_pkg, "run", spy)
    return got


def test_t2_run_really_receives_the_callable_when_env_is_set(world, run_spy):
    put(world)
    app()
    assert run_spy and callable(run_spy[-1]["local_lookup"]) and run_spy[-1]["local_lookup"] is svc.run_local_lookup


@pytest.mark.parametrize("val", [None, "", " ", "   ", "\t", "\n", " \t\n "])
def test_t2_t4b_run_receives_none_when_env_unset_empty_or_whitespace_only(world, run_spy, val):
    if val is None:
        world.monkeypatch.delenv(ENV)
    else:
        world.monkeypatch.setenv(ENV, val)
    put(world)
    at = app()
    assert run_spy and run_spy[-1]["local_lookup"] is None
    assert not [w for w in at.selectbox if w.key == "ui2_local_file"] and world.calls == []
    assert not any("ui2-ll" in m.value for m in at.markdown)


@pytest.mark.parametrize("val", ["x", "/x", " /x ", "relative/dir"])
def test_t4b_nonblank_values_still_opt_in(world, run_spy, val):
    world.monkeypatch.setenv(ENV, val)
    app()
    assert callable(run_spy[-1]["local_lookup"])                                # opt-in；之後 L3 自行驗證（拒絕為灰字，不 raise）


def test_t4b_opt_in_function_shape_keeps_a_ast_lock_valid():
    """strip 在 get() 之後處理；A 的 AST 形狀鎖（check_app_ui2_source）仍合規。"""
    from tests.test_stock_local_lookup_service import check_app_ui2_source
    assert check_app_ui2_source(APP_UI2.read_text(encoding="utf-8")) == []


# ════════════════════════════════════════════════════════════════════
# 10. T4(a)：get_all 回傳型別非 list（tuple／str／None／generator…）一律「不可證」→ bad_request，且不呼叫 L3
# ════════════════════════════════════════════════════════════════════
class _GetAll:
    def __init__(self, value):
        self.value = value

    def get_all(self, key):
        return self.value

    def __iter__(self):
        return iter(["host"])

    def __getitem__(self, key):
        return "localhost"


def _gen():
    yield "localhost"


@pytest.mark.parametrize("ret", [("localhost",), "localhost", None, _gen(), {"localhost"}, b"localhost", 5, ("a", "b")])
def test_t4a_non_list_get_all_is_bad_request(ret):
    assert target.derive_local_proof(_GetAll(ret), "127.0.0.1") == (None, REASON_BAD_REQUEST)


def test_t4a_list_get_all_is_still_accepted_and_empty_list_is_no_request_context():
    p, code = target.derive_local_proof(_GetAll(["localhost"]), "127.0.0.1")
    assert code is None and p.request_host == "localhost"
    assert target.derive_local_proof(_GetAll([]), "127.0.0.1") == (None, REASON_NO_REQUEST_CONTEXT)
    assert target.derive_local_proof(_GetAll(["a", "b"]), "127.0.0.1") == (None, REASON_BAD_REQUEST)


@pytest.mark.parametrize("ret", [("localhost",), "localhost", None, _gen()])
def test_t4a_non_list_get_all_never_reaches_l3_in_the_app(world, ret):
    put(world)
    world.ctx.headers = _GetAll(ret)
    at = app()
    assert world.calls == [] and LLR.TEXT_LOCAL_UNAVAILABLE in md(at)
    assert not [w for w in at.selectbox if w.key == "ui2_local_file"]
    assert_no_reason_codes(at)
