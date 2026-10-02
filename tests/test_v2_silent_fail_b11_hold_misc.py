"""批次 11：「💼 我的持股」四件雜項（Q1-r2 ／ Q1-r3 ／ Q1-r5 ／ Q2-r1）。

（客戶 2026-09-26 批次授權「失敗被當成沒結果」的所有卡；⛔ 不新造文案（K1）；
  L1／L3 只准加性改動、預設維持舊行為。）

Q1-r2 —— secrets.toml **格式錯誤**被讀成「你還沒有綁定」（灰「有效的結果」）：
  Streamlit 解析 TOML 失敗時丟 `StreamlitSecretNotFoundError`，它是 `FileNotFoundError` 的子類
  （與「檔案不存在」同一類）⇒ L1 `_get_active_sheet_id()` 吞成空字串、`oauth_state._safe_secret()`
  吞成預設值 ⇒ L3 `get_binding_state()` 回 `unbound` ＋ `read_error=""`。
  修法：L1 新增 `_secrets_read_error()`（只看 Streamlit 的例外鏈：解析失敗有 `__cause__`、
  檔案不存在沒有；**只交型別名**）；L3 在要回 unbound 時呼叫它、記進既有的 `read_error`
  ⇒ 走 Q1（#702）既有紅態。**本檔用真的 Streamlit `Secrets` 讀真的壞檔**，不是手捏例外。

Q1-r3 —— 綁定那一步就讀失敗（例：`oauth_state` 載不進來）時，「這本 Sheet 裡的組合」卡叫你
  「重新用 Google 登入授權一次」＝不實指引（登入一百次也一樣）。改指既有常數
  `STATION_ERROR_WHERE`；綁到了、只是讀組合清單失敗（drift）那一種原文照舊。

Q2-r1 —— ⑤⑥ 分配卡轉紅時，⑦ AI 總結仍把 L3 digest 的「實際配置：核心 X% / 衛星 Y%」送進 prompt
  （現價抓不到時還附一句不實的「部分持股缺金額」）。改：分配卡紅時送出的複本 `allocation=None`
  ⇒ L3 既有契約不寫那一行（只刪不加；L3 一行未動）。

Q1-r5 —— 上游例外的 `repr` 未經清洗就上畫面（實證：secrets.toml 有一個非 UTF-8 位元組時，
  `UnicodeDecodeError` 的 repr 帶出整份檔案原文）。修法：L0 新增 `shared/secret_scrub.py`
  （`scrub_query_secrets` 逐字搬自 `ai_qa_service._scrub_secrets`，後者改引用它、byte-identical；
  `scrub_secrets` 再補解碼例外只留型別名／PEM／秘密欄位／Google 憑證字樣／Sheet ID／絕對路徑）；
  套用在三個出口：page_hold `_error_why()`、預覽卡 `watchlist_error`、L4 `render_holding_detail` 的
  `st.error`。遮罩沿用既有 `***`，⛔ 不加任何說明文字。

每條三件事：(a) 失敗 → 修正後的行為；(b) 真的結果 → 與修前一字不差；(c) 突變 → (a) 轉紅。
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import pathlib
import random
import re
import subprocess
import sys
import types

import pytest
import streamlit
from streamlit import config as st_config
from streamlit.runtime.secrets import Secrets

import src.data.portfolio.gsheet_portfolio as GSP
import src.services.ai_qa_service as AIQ
import src.services.app_ai_service as A
import src.services.dividend_station_service as S
import src.services.holdings_service as HS
import src.services.portfolio_binding_service as SVC
import src.ui.render.station_cards as SC
from shared import secret_scrub as SSC
from shared.station_specs import MISS_FETCH_FAILED
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_LIVE
from src.ui.views import page_hold as PH

_REPO = pathlib.Path(__file__).resolve().parents[1]
_VALID = "有效的結果"
_REQ = PH.HoldRequest(submitted=True, mode=PH.SCOPE_WITH_BINDING)
_RELOGIN = "重新用 Google 登入授權一次"
#: 壞掉的 secrets 檔裡放一個假金鑰 —— 紅卡上**一個字元都不准出現**。
_FAKE_SECRET = "FAKE_SECRET_VALUE_b11"


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str]) -> types.ModuleType:
    """把 `mod` 的原始碼裡每一組 `old` **恰好一處**換成 `new`，載成一個獨立的新模組。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    name = f"_mutant_b11_{mod.__name__.rsplit('.', 1)[-1]}"
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    sys.modules[name] = m
    try:
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


# ── 本批的突變點（每一條拿掉 → 對應的 (a) 必須轉紅）─────────────────────────
_GSP_CAUSE = ("        return type(_e).__name__ if _e.__cause__ is not None else ''\n",
              "        return ''\n")
_SVC_CALL = ("        _sec = _gsp._secrets_read_error()\n", "        _sec = ''\n")
_PH_WHERE = ("            where=(STATION_ERROR_WHERE if binding.error else\n",
             "            where=(\n")
_PH_V2_ROW = ("           None, _v2_raised(SRC_BINDING), _V2_CHECK_NET)),\n"
              "       _v2_rows_for(\"hold.portfolio_count\", COUNT_EMPTY_NOW",
              "           None, _v2_raised(SRC_BINDING),\n"
              "           \"重新用 Google 登入授權一次，或確認那本 Sheet 仍然分享給你\")),\n"
              "       _v2_rows_for(\"hold.portfolio_count\", COUNT_EMPTY_NOW")
_PH_AI = ("                   if _split_state(station) == UI_FAILED else dict(station.digest))\n",
          "                   if False else dict(station.digest))\n")


def _card_text(built) -> str:
    """一張卡上**所有**看得到的字（卡本體 ＋ facts ＋ v2 HTML，含「▸ 詳細」摺疊區）。"""
    card, facts, sig = built
    return repr((card, tuple(facts), sig)) + PH.v2_card_html(card, facts, sig)


# ══════════════════════════════════════════════════════════════════
# Q1-r2：真的 Streamlit `Secrets` 讀真的檔
# ══════════════════════════════════════════════════════════════════
@pytest.fixture
def secrets_file(tmp_path, monkeypatch):
    """把 `st.secrets` 換成一個**真的** `streamlit.runtime.secrets.Secrets`，只讀 `tmp_path` 那一個檔。

    `content=None` → 不建檔（＝真的沒有 secrets）。`session` → `st.session_state`（普通 dict）。
    ⚠️ 只測「壞檔」與「沒有檔」：好檔會讓 Streamlit 裝 file watcher（背景輪詢執行緒）。
    Google 讀取面一律換成「一被叫就炸」—— 本批的路徑全在 unbound，一次網路都不該發。
    """
    _path = tmp_path / "secrets.toml"
    _orig = st_config.get_option("secrets.files")

    def _use(content, *, session=None):
        if content is not None:
            _path.write_bytes(content if isinstance(content, bytes) else content.encode())
        st_config.set_option("secrets.files", [str(_path)])
        monkeypatch.setattr(streamlit, "secrets", Secrets())
        monkeypatch.setattr(streamlit, "session_state", dict(session or {}))
        for _fn in ("list_portfolios", "load_portfolio", "list_stock_watchlists",
                    "load_stock_watchlist"):
            monkeypatch.setattr(GSP, _fn, _network_poison)
        return _path

    yield _use
    st_config.set_option("secrets.files", _orig)


def _network_poison(*_a, **_k):
    raise AssertionError("unbound 路徑不該向 Google 發任何一次讀取")


#: 解析失敗（Unbalanced quotes）—— 失敗那一行**之前**放一個假金鑰。
_MALFORMED = f'client_secret = "{_FAKE_SECRET}"\nportfolio_sheet_id = "abc\n'
#: 讀取例外（非 UTF-8 位元組）—— `UnicodeDecodeError` 的 repr 會帶出整段檔案原文。
_NOT_UTF8 = f'client_secret = "{_FAKE_SECRET}"\n'.encode() + b"\xff\n"


class TestQ1r2StreamlitContract:
    """本批依賴的 Streamlit 行為（量測 2026-09-26，streamlit 1.59.2）。它變了 → 這裡先紅。"""

    def test_malformed_is_file_not_found_with_a_cause(self, secrets_file):
        secrets_file(_MALFORMED)
        with pytest.raises(FileNotFoundError) as _ei:
            streamlit.secrets.get(GSP.PORTFOLIO_SHEET_KEY, "")
        assert _ei.value.__cause__ is not None

    def test_missing_is_file_not_found_without_a_cause(self, secrets_file):
        secrets_file(None)
        with pytest.raises(FileNotFoundError) as _ei:
            streamlit.secrets.get(GSP.PORTFOLIO_SHEET_KEY, "")
        assert _ei.value.__cause__ is None

    def test_before_this_batch_malformed_was_swallowed_into_not_set(self, secrets_file):
        """根因：兩支既有 L1 讀取都把壞檔吞成「沒設定」（⛔ 本批不改它們）。"""
        secrets_file(_MALFORMED)
        assert GSP._get_active_sheet_id() == ""
        from src.data.portfolio import oauth_state as OS
        assert OS.is_oauth_configured() is False


class TestQ1r2MalformedSecretsIsRed:
    @pytest.mark.parametrize("session", [{}, {GSP.PORTFOLIO_SHEET_KEY: "SHEET1"}],
                             ids=["no_sheet_in_session", "sheet_in_session"])
    def test_a_l3_records_the_read_error_status_unchanged(self, secrets_file, session):
        secrets_file(_MALFORMED, session=session)
        bs = SVC.get_binding_state()
        assert (bs.status, bs.logged_in, bs.portfolio_count) == (SVC.STATUS_UNBOUND, False, None), (
            "全域狀態列看的三個欄位照舊（它不讀 read_error）")
        assert bs.read_error == "StreamlitSecretNotFoundError"

    def test_a_binding_family_is_the_existing_red(self, secrets_file):
        secrets_file(_MALFORMED)
        b = PH.load_binding(_REQ)
        h = PH.load_holdings(_REQ)
        for built, now in ((PH.build_binding_card(b), PH.BINDING_FAILED_NOW),
                           (PH.build_portfolio_count_card(b), PH.COUNT_FAILED_NOW),
                           (PH.build_holdings_preview_card(h), PH.PREVIEW_FAILED_NOW)):
            card = built[0]
            assert card.state == UI_FAILED, card.key
            assert card.note.now == now, card.key
            assert _VALID not in card.note.why, card.key
        with pytest.raises(RuntimeError, match="StreamlitSecretNotFoundError"):
            HS.get_holdings()

    @pytest.mark.parametrize("content", [_MALFORMED, _NOT_UTF8], ids=["malformed", "not_utf8"])
    def test_a_no_secret_content_or_path_reaches_the_card(self, secrets_file, content):
        """紅卡（含摺疊區）⛔ 不得出現檔案裡的任何金鑰值或檔案路徑。

        ⚠️ `not_utf8` 在這裡由本批的探針接住（Sheet 識別碼已在 session，L1
        `_get_active_sheet_id()` 那時不讀 secrets；探針只交型別名）。Sheet 識別碼**不在** session
        的那一種見 `test_a_sheet_id_read_leak_is_scrubbed_at_the_page_exit`（Q1-r5）。
        """
        _path = secrets_file(content, session={GSP.PORTFOLIO_SHEET_KEY: "SHEET1"})
        b = PH.load_binding(_REQ)
        assert b.error, "要是紅的"
        for built in (PH.build_binding_card(b), PH.build_portfolio_count_card(b)):
            _txt = _card_text(built)
            assert _FAKE_SECRET not in _txt
            assert str(_path) not in _txt and str(_path.parent) not in _txt

    def test_a_read_exception_is_recorded_once(self, secrets_file):
        """讀 Sheet 識別碼那一步已經以同型別記過 → 探針 ⛔ 不重複記。"""
        secrets_file(_NOT_UTF8)
        err = SVC.get_binding_state().read_error
        assert err.startswith("UnicodeDecodeError(") and err.count("UnicodeDecodeError") == 1

    def test_a_sheet_id_read_leak_is_scrubbed_at_the_page_exit(self, secrets_file):
        """Q1-r5 實證的那一條：Sheet 識別碼**不在** session → L3 讀它時的 `repr(UnicodeDecodeError)`
        帶著整份 secrets 檔原文（L3 的 `read_error` 仍是原文 —— 那是資料，不是畫面）；
        畫上卡之前由 `_error_why()` 洗掉：綁定／本數／預覽三張紅卡（含摺疊區）⛔ 不得有金鑰值。
        """
        _path = secrets_file(_NOT_UTF8)
        assert _FAKE_SECRET in SVC.get_binding_state().read_error, "前提：L3 那一份確實帶著原文"
        b = PH.load_binding(_REQ)
        h = PH.load_holdings(_REQ)
        for built in (PH.build_binding_card(b), PH.build_portfolio_count_card(b),
                      PH.build_holdings_preview_card(h)):
            assert built[0].state == UI_FAILED, built[0].key
            _txt = _card_text(built)
            assert _FAKE_SECRET not in _txt, built[0].key
            assert str(_path.parent) not in _txt, built[0].key
            assert "UnicodeDecodeError" in built[0].note.why, "型別名要留著（回報維護者用）"


class TestQ1r2GenuineUnchanged:
    def test_b_no_secrets_file_is_still_the_grey_valid_result(self, secrets_file):
        secrets_file(None)
        bs = SVC.get_binding_state()
        assert (bs.status, bs.read_error) == (SVC.STATUS_UNBOUND, "")
        card = PH.build_binding_card(PH.load_binding(_REQ))[0]
        assert card.state == UI_EMPTY and card.note.now == PH.NOT_BOUND_NOW
        assert _VALID in card.note.why

    def test_b_readable_secrets_without_the_keys_is_still_grey(self, monkeypatch):
        """讀得到、只是沒有那兩個設定 → 灰（有效結果）。用普通 dict 當 secrets（不裝 watcher）。"""
        monkeypatch.setattr(streamlit, "secrets", {"unrelated": "x"})
        monkeypatch.setattr(streamlit, "session_state", {})
        assert GSP._secrets_read_error() == ""
        bs = SVC.get_binding_state()
        assert (bs.status, bs.read_error) == (SVC.STATUS_UNBOUND, "")

    def test_b_no_streamlit_is_empty(self, monkeypatch):
        monkeypatch.setattr(GSP, "st", None)
        assert GSP._secrets_read_error() == ""

    def test_b_bound_path_never_calls_the_probe(self, monkeypatch):
        """已登入＋已綁 → ⛔ 不呼叫探針（它只在要回 unbound 時才問）。"""
        monkeypatch.setattr(GSP, "_has_oauth_tokens", lambda: True)
        monkeypatch.setattr(GSP, "_get_active_sheet_id", lambda: "SHEET1")
        monkeypatch.setattr(GSP, "list_portfolios", lambda **_k: ["核心"])
        monkeypatch.setattr(GSP, "_secrets_read_error", _network_poison)
        bs = SVC.get_binding_state()
        assert (bs.status, bs.portfolio_count, bs.read_error) == (SVC.STATUS_BOUND, 1, "")


class TestQ1r2CallSites:
    def test_only_l3_binding_calls_the_new_probe(self):
        out = set()
        for f in [_REPO / "app.py", *sorted((_REPO / "src").rglob("*.py")),
                  *sorted((_REPO / "scripts").rglob("*.py"))]:
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                if ((isinstance(n, ast.Attribute) and n.attr == "_secrets_read_error")
                        or (isinstance(n, ast.Name) and n.id == "_secrets_read_error")
                        or (isinstance(n, ast.FunctionDef) and n.name == "_secrets_read_error")):
                    out.add(str(f.relative_to(_REPO)))
        assert out == {"src/data/portfolio/gsheet_portfolio.py",
                       "src/services/portfolio_binding_service.py"}


class TestQ1r2Mutations:
    def test_c_a_probe_that_ignores_the_cause_turns_grey(self, secrets_file, monkeypatch):
        m = _mutant(GSP, _GSP_CAUSE)
        monkeypatch.setattr(GSP, "_secrets_read_error", m._secrets_read_error)
        secrets_file(_MALFORMED)
        assert SVC.get_binding_state().read_error == ""
        assert PH.build_binding_card(PH.load_binding(_REQ))[0].note.now == PH.NOT_BOUND_NOW

    def test_c_l3_not_calling_the_probe_turns_grey(self, secrets_file):
        m = _mutant(SVC, _SVC_CALL)
        secrets_file(_MALFORMED)
        assert m.get_binding_state().read_error == ""


# ══════════════════════════════════════════════════════════════════
# Q1-r3：綁定讀失敗時，組合本數卡 ⛔ 不叫你重新登入
# ══════════════════════════════════════════════════════════════════
def _broken_binding(err: str = "ImportError('oauth_state broken')") -> PH.BindingReadout:
    """與 `load_binding()` (d)／(e) 同一個讀數形狀。"""
    return PH.BindingReadout(requested=True, submitted=True, count_requested=True, error=err)


def _drift_binding() -> PH.BindingReadout:
    """綁到了、讀組合清單失敗（L3 降級成 bound ＋ None）。"""
    return PH.BindingReadout(requested=True, submitted=True, logged_in=True, sheet_bound=True,
                             status="bound", count_requested=True, portfolio_count=None,
                             count_missing_reason=MISS_FETCH_FAILED)


class TestQ1r3CountCardGuidance:
    def test_a_failed_count_card_points_to_the_existing_constant(self):
        built = PH.build_portfolio_count_card(_broken_binding())
        card = built[0]
        assert (card.state, card.note.now) == (UI_FAILED, PH.COUNT_FAILED_NOW)
        assert card.note.where == PH.STATION_ERROR_WHERE
        assert _RELOGIN not in _card_text(built)

    def test_a_card_face_is_an_excerpt_of_that_constant(self):
        card = PH.build_portfolio_count_card(_broken_binding())[0]
        short, full = PH.v2_short_rows(card)
        assert dict(short)[PH.V2_GUIDE_FACT_KEY] == PH._V2_CHECK_NET
        assert dict(full)[PH.V2_GUIDE_FACT_KEY] == PH.v2_plain(PH.STATION_ERROR_WHERE)

    def test_a_real_broken_oauth_module_end_to_end(self, monkeypatch):
        """真的走 L1：`oauth_state` 載不進來 → Q1 讀失敗 → 本數卡的去哪補 ⛔ 不是重新登入。"""
        monkeypatch.setattr(streamlit, "secrets", {})
        monkeypatch.setattr(streamlit, "session_state", {GSP.PORTFOLIO_SHEET_KEY: "SHEET1"})
        monkeypatch.setitem(sys.modules, "src.data.portfolio.oauth_state", None)
        b = PH.load_binding(_REQ)
        assert "oauth_state" in b.error
        built = PH.build_portfolio_count_card(b)
        assert built[0].state == UI_FAILED and built[0].note.where == PH.STATION_ERROR_WHERE
        assert _RELOGIN not in _card_text(built)

    def test_b_drift_keeps_its_original_guidance(self):
        """綁到了、讀組合清單失敗：授權過期是常見原因 → 原文照舊（一字不動）。"""
        card = PH.build_portfolio_count_card(_drift_binding())[0]
        assert (card.state, card.note.now) == (UI_FAILED, PH.COUNT_DRIFT_NOW)
        assert card.note.where.startswith(_RELOGIN)
        assert dict(PH.v2_short_rows(card)[0])[PH.V2_GUIDE_FACT_KEY].startswith(_RELOGIN)

    def test_b_the_where_text_is_not_new(self):
        """K1：⛔ 沒有新字串 —— 用的是既有常數，且那個常數本來就有別的卡在用。"""
        src = pathlib.Path(PH.__file__).read_text(encoding="utf-8")
        assert src.count("where=STATION_ERROR_WHERE") >= 3

    def test_c_reverting_the_where_brings_back_the_relogin(self):
        m = _mutant(PH, _PH_WHERE)
        card = m.build_portfolio_count_card(
            m.BindingReadout(requested=True, submitted=True, count_requested=True, error="x"))[0]
        assert _RELOGIN in card.note.where

    def test_c_reverting_the_v2_row_breaks_the_face(self):
        m = _mutant(PH, _PH_V2_ROW)
        card = m.build_portfolio_count_card(
            m.BindingReadout(requested=True, submitted=True, count_requested=True, error="x"))[0]
        with pytest.raises(KeyError):
            m.v2_short_rows(card)


# ══════════════════════════════════════════════════════════════════
# Q2-r1：⑤⑥ 分配卡紅 → ⑦ 的 prompt 不帶配置比例
# ══════════════════════════════════════════════════════════════════
# 與 L3 `build_station_rows` 產出的列同形（同 b8 的列）。
_ETF_OK = {"代號": "0056", "種類": "ETF", "held": True, "現價": 35.0, "張數": 3.0,
           "市值": 105.0, "_detail": {}}
_SAT_OK = {"代號": "2330", "種類": "個股", "held": True, "現價": 100.0, "張數": 1.0,
           "市值": 100.0, "_detail": {}}
_SAT_ERR = {"代號": "6505", "種類": "個股", "held": True, "_detail": {"error": "HTTPError 502"}}
_SAT_NO_PRICE = {"代號": "2454", "種類": "個股", "held": True, "現價": None, "張數": 1.0,
                 "市值": None, "_detail": {}}
_SAT_NO_LOTS = {"代號": "3008", "種類": "個股", "held": True, "現價": 150.0, "張數": None,
                "市值": None, "_detail": {}}

_ALLOC_LINE = "實際配置："
_PARTIAL_NOTE = "部分持股缺金額"


def _station(P, rows):
    """真的走 L3 `build_station_digest`（含 `compute_allocation_split`），同 `load_station()`。"""
    dg = S.build_station_digest(list(rows), 17.5)
    return P.StationReadout(requested=True, submitted=True, bound=True, holdings_n=len(rows),
                            rows=tuple(rows), digest=P._digest_map(dg),
                            split=P._digest_map(dg.get("allocation")))


@pytest.fixture
def prompt_of(monkeypatch):
    """按下 ⑦ → 回送進付費 transport 的那一段 prompt（真的走 L3 `build_ai_summary`）。"""
    def _run(P, st_):
        seen: list[str] = []

        def _fake(prompt, **_k):
            seen.append(prompt)
            return "推播文字"

        monkeypatch.setattr(A, "gemini_call", _fake)
        ai = P.load_ai_summary(True, st_, P.SwitchReadout(requested=True, submitted=True))
        assert ai.text == "推播文字" and len(seen) == 1
        return seen[0]
    return _run


_RED_CASES = {"whole_row_failed": (_ETF_OK, _SAT_ERR),
              "no_price": (_ETF_OK, _SAT_NO_PRICE),
              "both": (_ETF_OK, _SAT_ERR, _SAT_NO_PRICE)}
_GENUINE_CASES = {"all_valued": (_ETF_OK, _SAT_OK),
                  "missing_lots_is_partial": (_ETF_OK, _SAT_OK, _SAT_NO_LOTS)}


class TestQ2r1PromptFollowsTheSplitCard:
    @pytest.mark.parametrize("case", sorted(_RED_CASES))
    def test_root_cause_l3_still_computes_a_ratio(self, case):
        """根因（L3 ⛔ 未改）：分配卡紅的輸入，L3 仍算出一個比例、prompt 仍會寫那一行。"""
        st_ = _station(PH, _RED_CASES[case])
        assert st_.digest["allocation"] is not None
        assert _ALLOC_LINE in S.build_summary_prompt(dict(st_.digest))

    @pytest.mark.parametrize("case", sorted(_RED_CASES))
    def test_a_red_split_card_means_no_ratio_in_the_prompt(self, prompt_of, case):
        st_ = _station(PH, _RED_CASES[case])
        assert PH.build_allocation_split_card(st_)[0].state == UI_FAILED
        assert PH.build_core_satellite_card(st_)[0].state == UI_FAILED
        p = prompt_of(PH, st_)
        assert _ALLOC_LINE not in p and _PARTIAL_NOTE not in p
        # 只刪那一行：其餘段落與 L3 對 `allocation=None` 的輸出逐字相同。
        assert p == S.build_summary_prompt(dict(st_.digest, allocation=None))
        assert st_.digest["allocation"] is not None, "畫面讀的那一份 digest ⛔ 不被改動"

    @pytest.mark.parametrize("case", sorted(_GENUINE_CASES))
    def test_b_live_split_card_prompt_is_byte_identical(self, prompt_of, case):
        st_ = _station(PH, _GENUINE_CASES[case])
        assert PH.build_allocation_split_card(st_)[0].state == UI_LIVE
        p = prompt_of(PH, st_)
        assert p == S.build_summary_prompt(dict(st_.digest))
        assert _ALLOC_LINE in p

    def test_b_missing_lots_keeps_the_true_partial_note(self, prompt_of):
        """缺張數 ＝ 真的「缺金額」→ 那句附註本來就對，照留。"""
        assert _PARTIAL_NOTE in prompt_of(PH, _station(PH, _GENUINE_CASES["missing_lots_is_partial"]))

    @pytest.mark.parametrize("case", sorted(_RED_CASES))
    def test_c_dropping_the_guard_sends_the_ratio_again(self, prompt_of, case):
        m = _mutant(PH, _PH_AI)
        assert _ALLOC_LINE in prompt_of(m, _station(m, _RED_CASES[case]))


# ══════════════════════════════════════════════════════════════════
# Q1-r5：L0 `shared/secret_scrub.py` ＋ 三個出口
# ══════════════════════════════════════════════════════════════════
_SHEET_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcd"

#: (輸入, 洗完後 ⛔ 不得出現的片段, 洗完後必須留著的片段)
_LEAKY = {
    "unicode_decode_repr": (
        "UnicodeDecodeError('utf-8', b'client_secret = \"S3CR3T_A\"\\n\\xff\\n', 28, 29, "
        "'invalid start byte')", ("S3CR3T_A", "client_secret", "\\xff"), ("UnicodeDecodeError",)),
    "unicode_decode_nested": (
        repr(RuntimeError(repr(UnicodeDecodeError("utf-8", b"k = \"S3CR3T_B\"\xff", 14, 15,
                                                   "invalid start byte")))),
        ("S3CR3T_B",), ("RuntimeError", "UnicodeDecodeError")),
    "toml_decode_repr": (
        "TomlDecodeError(\"What? g already exists?{'g': {'client_secret': 'S3CR3T_C'}}\")",
        ("S3CR3T_C",), ("TomlDecodeError",)),
    "query_key": (
        "HTTPError('403 Client Error: Forbidden for url: https://x.googleapis.com/v1/m:gen"
        "?key=AIzaSyS3CR3T_DDDDDDDDDD&alt=json')", ("S3CR3T_D",), ("key=***", "alt=json")),
    "query_refresh_token": (
        "url?refresh_token=S3CR3T_E&client_secret=S3CR3T_F&x=1", ("S3CR3T_E", "S3CR3T_F"),
        ("refresh_token=***", "client_secret=***", "x=1")),
    "dict_tokens": (
        "OAuthError(\"{'error': 'invalid_grant', 'refresh_token': 'S3CR3T_G', "
        "'access_token': 'S3CR3T_H'}\")", ("S3CR3T_G", "S3CR3T_H"), ("invalid_grant",)),
    "bare_google_tokens": (
        "tok ya29.S3CR3T_IIIIIIIIII / 1//S3CR3T_JJJJJJJJJJ / GOCSPX-S3CR3T_KKKKKKKK",
        ("S3CR3T_I", "S3CR3T_J", "S3CR3T_K"), ("ya29.***", "1//***", "GOCSPX-***")),
    "pem": (
        "-----BEGIN PRIVATE KEY-----\nS3CR3T_L\n-----END PRIVATE KEY----- tail",
        ("S3CR3T_L", "BEGIN PRIVATE KEY"), ("tail",)),
    "sheet_url": (
        f"see https://docs.google.com/spreadsheets/d/{_SHEET_ID}/edit#gid=0",
        (_SHEET_ID,), ("https://docs.google.com/spreadsheets/d/***/edit",)),
    "sheet_api_path": (
        "ConnectionError(\"HTTPSConnectionPool(host='sheets.googleapis.com', port=443): Max retries "
        f"exceeded with url: /v4/spreadsheets/{_SHEET_ID}/values/portfolios?alt=json\")",
        (_SHEET_ID,), ("sheets.googleapis.com", "Max retries exceeded")),
    "posix_path": (
        "FileNotFoundError(2, 'No such file or directory', '/home/alice/app/.streamlit/secrets.toml')",
        ("/home/alice", "alice", ".streamlit"), ("***/secrets.toml", "No such file or directory")),
    "windows_path": (
        "OSError('C:\\\\Users\\\\bob\\\\secrets.toml')", ("Users", "bob"), ("OSError",)),
    # ── QA 阻擋 1：Windows 正斜線／含空白／UNC ─────────────────────────
    "win_forward_slash": ("OSError('C:/Users/bob/secrets.toml')", ("Users", "bob"), ("OSError('***')",)),
    "win_with_space": ("OSError('C:\\\\Users\\\\Bob Smith\\\\x.toml') retry",
                       ("Bob", "Smith", "x.toml"), ("OSError('***') retry",)),
    "win_with_space_plain": ("open C:\\Users\\Bob Smith\\x.toml failed", ("Bob", "Smith"), ("open ***",)),
    "unc_repr": ("OSError('\\\\\\\\fileserver\\\\share\\\\dir\\\\x.toml')",
                 ("fileserver", "share"), ("OSError('***')",)),
    "unc_plain": ("UNC \\\\fileserver\\share\\dir\\x.toml", ("fileserver", "share"), ("UNC ***",)),
    # ── QA 阻擋 2：TOML 賦值（bytes repr、`\n` 分行、跳脫引號）────────────
    "toml_assign_bytes_repr": (
        repr(b'client_secret = "S3CR3T_M"\npassword = \'S3CR3T_N\'\nname = "keep"\n'),
        ("S3CR3T_M", "S3CR3T_N"), ("client_secret = ***", "password = ***", 'name = "keep"')),
    "toml_assign_escaped_quote": ('refresh_token = "S3CR3T_O\\"S3CR3T_P\\""',
                                  ("S3CR3T_O", "S3CR3T_P"), ("refresh_token = ***",)),
    "toml_assign_nested_repr": (repr(RuntimeError(repr(b'password = "S3CR3T_Q"\nz = 1'))),
                                ("S3CR3T_Q",), ("RuntimeError(",)),
    "toml_assign_no_space_quoted": ('private_key_id="S3CR3T_R"', ("S3CR3T_R",), ("private_key_id=",)),
    # ── QA 阻擋 3：`型別: 訊息` 與 Streamlit 的解析錯誤訊息 ─────────────────
    "toml_colon_form": ("TomlDecodeError: What? g already exists?{'g': {'name': 'S3CR3T_S'}}",
                        ("S3CR3T_S", "What?"), ("TomlDecodeError",)),
    "toml_wrapped_colon": ("ValueError: TomlDecodeError: Duplicate keys! S3CR3T_T",
                           ("S3CR3T_T",), ("ValueError: TomlDecodeError",)),
    "streamlit_parse_msg": (
        "Error parsing secrets file at /mount/src/app/.streamlit/secrets.toml: "
        "What? g already exists?{'g': {'name': 'S3CR3T_U'}}",
        ("S3CR3T_U", "/mount", ".streamlit"), ("Error parsing secrets file",)),
    "unicode_colon_form": ("UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff: S3CR3T_V",
                           ("S3CR3T_V",), ("UnicodeDecodeError",)),
    # ── QA 阻擋 4：Authorization／Bearer／JWT ─────────────────────────────
    "auth_header_bearer": ("Authorization: Bearer S3CR3T_Wxxxxxx", ("S3CR3T_W",),
                           ("Authorization: Bearer ***",)),
    "auth_dict_bearer": ("{'Authorization': 'Bearer S3CR3T_Xxxxxxx', 'x': 1}", ("S3CR3T_X",),
                         ("'Authorization': 'Bearer ***'", "'x': 1")),
    "auth_basic_after_newline_escape": ("hdr\\nAuthorization: Basic S3CR3T_Yxxxx", ("S3CR3T_Y",),
                                        ("Authorization: Basic ***",)),
    "bare_bearer": ("got Bearer S3CR3T_Zxxxxxx back", ("S3CR3T_Z",), ("Bearer ***", "back")),
    "jwt": ("id eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJTM0NSM1QifQ.c2lnbmF0dXJlX1MzQ1IzVA end",
            ("eyJhbGci", "eyJzdWIi", "c2lnbmF0"), ("id *** end",)),
    # ── 一併修 5 ─────────────────────────────────────────────────────────
    "url_userinfo": ("proxy http://alice:S3CR3T_AA@nas.local:3128 down", ("S3CR3T_AA",),
                     ("http://alice:***@nas.local:3128 down",)),
    "spreadsheet_id_query": (f"values?spreadsheetId={_SHEET_ID}&x=1", (_SHEET_ID,),
                             ("spreadsheetId=***&x=1",)),
    "drive_files_path": (f"GET https://www.googleapis.com/drive/v3/files/{_SHEET_ID}?alt=json",
                         (_SHEET_ID,), ("/drive/v3/files/***?alt=json",)),
    "file_url": ("open file:///home/alice/.streamlit/secrets.toml failed", ("alice", ".streamlit"),
                 ("file://***/secrets.toml failed",)),
    "private_key_id_dict": ("{'type': 'service_account', 'private_key_id': 'S3CR3T_AB', 'x': 1}",
                            ("S3CR3T_AB",), ("'private_key_id': '***'", "'x': 1")),
    "oauth_code": ("code=4/0AfJohXnS3CR3TACxxxxxxxxxxxx&scope=x", ("S3CR3TAC",), ("code=4/***&scope=x",)),
    "tilde_path": ("see ~alice/.streamlit/secrets.toml", ("alice", ".streamlit"), ("see ***/secrets.toml",)),
    # ── M4（password 樣本，三種寫法）─────────────────────────────────────────
    "password_assign": ('password = "S3CR3T_AD"', ("S3CR3T_AD",), ("password = ***",)),
    "password_dict": ("{'password': 'S3CR3T_AE', 'x': 1}", ("S3CR3T_AE",), ("'password': '***'",)),
    "password_query": ("login?password=S3CR3T_AF&x=1", ("S3CR3T_AF",), ("password=***&x=1",)),
    "password_colon_bare": ("password: S3CR3T_AG please", ("S3CR3T_AG",), ("password: *** please",)),
    # ── M1（TomlDecodeError，**不含**任何秘密欄位名 —— 只靠那一條規則擋）──────────
    "toml_no_secret_field": ("TomlDecodeError(\"What? g already exists?{'g': {'name': 'S3CR3T_AH'}}\")",
                             ("S3CR3T_AH",), ("TomlDecodeError",)),
    # ── 複驗第 1 條：欄位名緊貼引號＋冒號（`_COLON_BARE_RE` 原本排掉了）─────────────
    "colon_bare_after_quote": ("ValueError('password: S3CR3T_AI')", ("S3CR3T_AI",),
                               ("ValueError('password: ***')",)),
    "colon_bare_after_dquote": ('ValueError("client_secret: S3CR3T_AJ")', ("S3CR3T_AJ",),
                                ('ValueError("client_secret: ***")',)),
    # ── 複驗第 2 條：本 repo 真實的 secrets／環境變數名 ＋ Telegram token ────────────
    "repo_finmind_token_assign": ('FINMIND_TOKEN = "S3CR3T_AK"', ("S3CR3T_AK",), ("FINMIND_TOKEN = ***",)),
    "repo_finmind_token_colon": ("FINMIND_TOKEN: S3CR3T_AL", ("S3CR3T_AL",), ("FINMIND_TOKEN: ***",)),
    "repo_gemini_key_pool": ("GEMINI_API_KEY_2 = S3CR3T_AM", ("S3CR3T_AM",), ("GEMINI_API_KEY_2 = ***",)),
    "repo_line_token_query": ("LINE_CHANNEL_ACCESS_TOKEN=S3CR3T_AN/x+y==", ("S3CR3T_AN",),
                              ("LINE_CHANNEL_ACCESS_TOKEN=***",)),
    "repo_telegram_dict": ("{'TELEGRAM_BOT_TOKEN': 'S3CR3T_AO', 'TELEGRAM_CHAT_ID': '98765'}",
                           ("S3CR3T_AO", "98765"), ("'TELEGRAM_BOT_TOKEN': '***'",)),
    "repo_sheet_id_assign": (f'portfolio_sheet_id = "{_SHEET_ID}"', (_SHEET_ID,), ("portfolio_sheet_id = ***",)),
    "repo_proxy_url_assign": ("PROXY_URL = http://nasuser:S3CR3T_AP@nas:3128", ("S3CR3T_AP", "nasuser"),
                              ("PROXY_URL = ***",)),
    "repo_fred_nas_keys": ("FRED_API_KEY: S3CR3T_AQ; NAS_API_KEY=S3CR3T_AR", ("S3CR3T_AQ", "S3CR3T_AR"),
                           ("FRED_API_KEY: ***", "NAS_API_KEY=***")),
    "telegram_bot_url": ("HTTPError: 401 for url: https://api.telegram.org/bot123456789:"
                         "AAHS3CR3TASxxxxxxxxxxxxxxxxxxxxxxxxx/sendMessage",
                         ("S3CR3TAS", "123456789"), ("api.telegram.org/bot***/sendMessage",)),
    "telegram_bare_token": ("token 123456789:AAHS3CR3TATxxxxxxxxxxxxxxxxxxxxxxxxx leaked",
                            ("S3CR3TAT",), ("token *** leaked",)),
    "published_sheet_csv": ("WATCHLIST_CSV_URL 讀取失敗：https://docs.google.com/spreadsheets/d/e/"
                            "2PACX-1vS3CR3TAUxxxxxxxxxxxx/pub?output=csv", ("S3CR3TAU",),
                            ("/spreadsheets/d/e/***/pub?output=csv",)),
    # ── 複驗第 3 條：全形起點的路徑（QA 突變 R2）───────────────────────────────
    "fullwidth_colon_path": ("路徑：/home/alice/.streamlit/secrets.toml", ("alice", ".streamlit"),
                             ("路徑：***/secrets.toml",)),
    "fullwidth_paren_path": ("（/home/alice/.streamlit/secrets.toml）", ("alice",), ("（***/secrets.toml）",)),
    "fullwidth_bracket_path": ("「/home/alice/.streamlit/secrets.toml」", ("alice",), ("「***/secrets.toml」",)),
}

#: 一般訊息：⛔ 一個字都不能被動到。
_PLAIN = (
    "HTTPError 502", "查無資料", "核心 80/20 偏離 +3.0 個百分點", "KeyError('portfolio_sheet_id')",
    "ImportError('oauth_state broken')", "StreamlitSecretNotFoundError", "張數 1/3 · TW/US",
    "RuntimeError('token boom')", "ValueError('invalid literal for int() with base 10: 'x'')",
    "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id=2330",
    "PermissionError(13, 'Permission denied')", "(/1e8) 元→億", "</div>", "a/b/c.toml", "",
    # QA 要求的一般訊息：百分比、日期、公開 URL、KeyError 代號、中文說明、中文之間的斜線
    "報酬 +12.5% ／ 殖利率 5.23%", "2026/09/26 14:30", "2026-09-26T06:30:00Z",
    "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date=20260926&stockNo=2330",
    "KeyError('2330')", "KeyError('00878')", "元/股/張 與 張/元", "（元/股）", "單位：元/股",
    "15~20% 與 1~3 天", "Bearer token", "4/5 盞", "Q4/2026", "KeyError('password')",
    "st.secrets has no key \"portfolio_sheet_id\"", "UnicodeDecodeError", "TomlDecodeError",
    "每股 3.5 元（近 4 季）/ 365 天",
    # 複驗：repo secrets 名只出現、沒有值 → 不動；時間不是 Telegram token
    "未設定 FINMIND_TOKEN", "PROXY_URL 未設定", "時間 14:30:00", "KeyError('FINMIND_TOKEN')",
    "st.secrets has no key \"GEMINI_API_KEY\"", "請設定 GEMINI_API_KEY（可另加 GEMINI_API_KEY_2 ~ _6）",
    "ValueError('invalid literal')", "RuntimeError('quota: 60 per minute')",
)


class TestQ1r5ScrubSecretsUnit:
    @pytest.mark.parametrize("case", sorted(_LEAKY))
    def test_leaky_samples_are_masked(self, case):
        raw, gone, kept = _LEAKY[case]
        out = SSC.scrub_secrets(raw)
        for g in gone:
            assert g not in out, (case, out)
        for k in kept:
            assert k in out, (case, out)

    @pytest.mark.parametrize("text", _PLAIN)
    def test_plain_messages_are_untouched(self, text):
        assert SSC.scrub_secrets(text) == text

    def test_none_is_empty_not_the_word_none(self):
        assert SSC.scrub_secrets(None) == ""

    @pytest.mark.parametrize("case", sorted(_LEAKY))
    def test_idempotent(self, case):
        once = SSC.scrub_secrets(_LEAKY[case][0])
        assert SSC.scrub_secrets(once) == once

    def test_mask_is_the_existing_one_and_no_new_words(self):
        """K1：洗完的字串拿掉既有遮罩 `***` 之後，每一個字元都來自原文 —— ⛔ 沒有任何新造的字。"""
        assert SSC.MASK == "***"
        for raw, _g, _k in _LEAKY.values():
            assert set(SSC.scrub_secrets(raw).replace(SSC.MASK, "")) <= set(raw), raw

    def test_pure_l0_no_imports_beyond_re(self):
        tree = ast.parse(pathlib.Path(SSC.__file__).read_text(encoding="utf-8"))
        mods = {(n.module if isinstance(n, ast.ImportFrom) else a.name)
                for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                for a in (n.names if isinstance(n, ast.Import) else [None])}
        assert mods <= {"__future__", "re"}, mods


# ── QA 6：中文之間的斜線 ⛔ 不當路徑 —— 用 repo 內所有既有字面值驗 ─────────────────
_CJK = "\u3000-\u303f\u3400-\u9fff\uff00-\uffef"
_CJK_RUN_RE = re.compile(r"[\w%s]+(?:/[\w%s]+)+" % (_CJK, _CJK))
_HAS_CJK_RE = re.compile("[%s]" % _CJK)


def _repo_cjk_slash_lines() -> tuple[set[str], set[str]]:
    """repo（`src` / `shared` / `scripts` / `infra` / `mcp_server` / `app.py`）所有字串字面值裡，
    含「中文與斜線相鄰」的行，以及其中的斜線連寫詞（`元/股/張`）。"""
    runs: set[str] = set()
    lines: set[str] = set()
    for base in ("src", "shared", "scripts", "infra", "mcp_server", "app.py"):
        p = _REPO / base
        for f in ([p] if p.is_file() else sorted(p.rglob("*.py"))):
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                if isinstance(n, ast.Constant) and isinstance(n.value, str):
                    for line in n.value.splitlines():
                        _rs = [r for r in _CJK_RUN_RE.findall(line) if _HAS_CJK_RE.search(r)]
                        if _rs:
                            lines.add(line)
                            runs.update(_rs)
    return runs, lines


def _scrub_without_posix_path(text: str) -> str:
    saved = SSC._RULES_AFTER_QUERY
    SSC._RULES_AFTER_QUERY = tuple(r for r in saved if r[0] is not SSC._POSIX_PATH_RE)
    try:
        return SSC.scrub_secrets(text)
    finally:
        SSC._RULES_AFTER_QUERY = saved


class TestQ1r5CjkSlashIsNotAPath:
    def test_every_repo_cjk_slash_run_is_untouched_after_any_separator(self):
        runs, _lines = _repo_cjk_slash_lines()
        assert len(runs) > 100, "掃描範圍不該是空的"
        for r in runs:
            for pre in ("", " ", "(", "'", '"', "=", ":", "，", "（", "\\n"):
                assert SSC.scrub_secrets(pre + r) == pre + r, pre + r

    def test_path_rule_never_eats_a_cjk_slash_run_in_repo_literals(self):
        """整行過清洗：路徑規則 ⛔ 不吃掉任何一個「中文斜線連寫詞」（其他規則吃掉的不算在這條）。"""
        _runs, lines = _repo_cjk_slash_lines()
        for line in lines:
            _full, _nopath = SSC.scrub_secrets(line), _scrub_without_posix_path(line)
            for r in _CJK_RUN_RE.findall(line):
                if _HAS_CJK_RE.search(r) and r in _nopath:
                    assert r in _full, (line, r)

    def test_c_the_old_path_start_rule_would_eat_cjk(self):
        m = _mutant(SSC, ('    _PATH_START + r"(?:~', '    r"(?<![0-9A-Za-z_.:/~*\\\\\\-])" + r"(?:~'))
        assert m.scrub_secrets("元/股/張") != "元/股/張"


# ── 每一類規則都承重：拿掉它 → 那一類的樣本就漏出來（含 QA 存活突變 M1／M4）──────────
_RULE_MUTANTS = {
    "M1_toml_rule": (("|TomlDecodeError)[ \\t]*[(:]", ")[ \\t]*[(:]"), "toml_no_secret_field"),
    "toml_colon_form": (("[ \\t]*[(:].*", "[ \\t]*[(].*"), "toml_colon_form"),
    "streamlit_parse": (("    (_STREAMLIT_PARSE_RE, r\"\\1\"),\n", ""), "streamlit_parse_msg"),
    "M4_password": (("|secret|password|passwd\")", "|secret|passwd\")"), "password_assign"),
    "M4_password_dict": (("|secret|password|passwd\")", "|secret|passwd\")"), "password_dict"),
    "M4_password_query": (("|secret|password|passwd\")", "|secret|passwd\")"), "password_query"),
    "assign_rule": (("    (_ASSIGN_RE, _mask_assign),\n", ""),
                    "toml_assign_bytes_repr"),
    "newline_escape_boundary": (('_TB_FIELD: str = r"(?:(?<![A-Za-z0-9])|(?<=\\\\[nrt]))"',
                                 '_TB_FIELD: str = r"(?<![A-Za-z0-9])"'), "toml_assign_bytes_repr"),
    "win_space": (("[A-Za-z]:(?:\\\\{1,2}|/)[^'\\\"<>|\\r\\n]*",
                   "[A-Za-z]:(?:\\\\{1,2}|/)[^'\\\"<>|\\r\\n\\s]*"), "win_with_space"),
    "unc": (("\\\\{2,4}[A-Za-z0-9]", "\\\\{9,9}[A-Za-z0-9]"), "unc_plain"),
    "auth_header": (("    (_AUTH_HEADER_RE, lambda m: m.group(1) + (m.group(3) or \"\") + MASK),\n", ""),
                    "auth_basic_after_newline_escape"),
    "bearer": (("    (_BEARER_RE, lambda m: m.group(1) + \" \" + MASK),\n", ""), "bare_bearer"),
    "jwt": (("    (_JWT_RE, MASK),\n", ""), "jwt"),
    "userinfo": (("    (_USERINFO_RE, lambda m: m.group(1) + \":\" + MASK + \"@\"),\n", ""), "url_userinfo"),
    "spreadsheet_id_query": (("|spreadsheet[_-]?id|file[_-]?id|key|token)=", "|file[_-]?id|key|token)="),
                             "spreadsheet_id_query"),
    "drive_files": (("|spreadsheets|files|folders)/)", "|spreadsheets|folders)/)"), "drive_files_path"),
    "file_url": (("    (_FILE_URL_RE, lambda m: m.group(1) + MASK + \"/\" + m.group(2)),\n", ""), "file_url"),
    "private_key_id": (("private[_-]?key[_-]?id|private[_-]?key|", "private[_-]?key|"),
                       "private_key_id_dict"),
    "oauth_code": (("4/[0-9A-Za-z_\\-]{20,}", "4/[0-9A-Za-z_\\-]{2000,}"), "oauth_code"),
    "tilde": (("(?:~[A-Za-z0-9_.\\-]{0,64})?/", "/"), "tilde_path"),
    "colon_bare_quote_lookbehind": (('    r"(?P<pre>" + _TB_FIELD + r"(?:" + _FIELDS_STRICT',
                                     '    r"(?P<pre>(?<![\\"\'])" + _TB_FIELD + r"(?:" + _FIELDS_STRICT'),
                                    "colon_bare_after_quote"),
    "repo_fields": (("    _FIELDS_REPO + \"|\"\n", ""), "repo_finmind_token_colon"),
    "repo_fields_gemini_pool": (("gemini[_-]?api[_-]?key(?:[_-]?\\d{1,2})?|", ""), "repo_gemini_key_pool"),
    "telegram": (("\\d{5,12}:[A-Za-z0-9_\\-]{30,}", "\\d{5,12}:[A-Za-z0-9_\\-]{3000,}"), "telegram_bot_url"),
    "published_sheet": (("/d(?:/e)?|spreadsheets", "/d|spreadsheets"), "published_sheet_csv"),
    "R2_fullwidth_start": (('                    r"|(?<=[：（「『，、；]))")', '                    r")")'),
                           "fullwidth_colon_path"),
    "R2_fullwidth_paren": (('                    r"|(?<=[：（「『，、；]))")', '                    r")")'),
                           "fullwidth_paren_path"),
}


class TestQ1r5EveryRuleIsLoadBearing:
    @pytest.mark.parametrize("name", sorted(_RULE_MUTANTS))
    def test_c_dropping_the_rule_leaks_its_sample(self, name):
        pair, case = _RULE_MUTANTS[name]
        raw, gone, _kept = _LEAKY[case]
        assert all(g not in SSC.scrub_secrets(raw) for g in gone), "前提：正版要遮得掉"
        #: 批 S4（SEC-r20／SEC-r21）的兩條 toml 帶值規則會替含 toml 重複表 dict 的樣本再遮一次（縱深防禦）——
        #: 要看出「這一條舊規則」承重，先把那兩條關掉。
        m = _mutant(SSC, pair, ("    (_TOML_EXISTS_DICT_RE, lambda m: m.group(1) + MASK),\n", ""),
                    ("    (_TOML_CONV_RE, _mask_toml_conv_for),\n", ""))
        out = m.scrub_secrets(raw)
        assert any(g in out for g in gone), (name, out)


# ── ReDoS：每一類對抗輸入都要線性 ──────────────────────────────────────────────
#: ⚠️ **在子程序裡跑、設總時限**（複驗第 3 條）：回溯爆炸時同一個程序裡的呼叫停不下來
#: （實測：反斜線串不設上限時 100k 字元要跑數分鐘），會讓 CI 卡住。子程序逾時 → 直接判紅。
#: 1M 字元的量測見交付報告（最慢 1.47 秒）；這裡用 50k 保持 CI 快。
_REDOS_N = 50_000
_REDOS_PER_CASE_S = 2.0
_REDOS_TOTAL_TIMEOUT_S = 15.0


def _rep(unit: str, n: int) -> str:
    return (unit * (n // len(unit) + 1))[:n]


_ADVERSARIAL_UNITS = (
    "a", "/", " /a", "\\", "a.", "a://", "\\\\a\\", " ~a/", "'", '"', "\\'", "\\n", "4/", "1//",
    "ya29.", "file://", '="', "/spreadsheets/", "'password': '", '"token": "', "password = \"",
    "Authorization: ", "eyJaaaaaaaaaa.", "C:\\a ", "-----BEGIN PRIVATE KEY-----", "TomlDecodeError",
    "password=", "key=", "123456:", "/bot1", "：/", "password: ", "FINMIND_TOKEN: ", "'password: ")
_ADVERSARIAL_PREFIXED = (
    ("password = ", "x"), ("password: '", "a"), ('password: "', "a"), ("password: \\", "\\"),
    ("a://", "x:"), ("eyJ", "a"), ("Bearer ", "a"), ("C:\\", "a"), ("\\\\", "a"), ("123456:", "a"))

#: SEC-r5：每組開跑前先在 stderr 印一行 `_REDOS_START_TAG + json(name)` 並 flush ——
#: 子程序逾時被砍時，最後一行開跑標記就是**卡住的那一組**，逾時訊息據此點名。
_REDOS_START_TAG = "REDOS-START "
_REDOS_SCRIPT = (
    "import json, sys, time\n"
    "from shared.secret_scrub import scrub_secrets\n"
    "out = {}\n"
    "for name, text in json.load(sys.stdin):\n"
    f"    sys.stderr.write({_REDOS_START_TAG!r} + json.dumps(name) + '\\n')\n"
    "    sys.stderr.flush()\n"
    "    t = time.perf_counter()\n"
    "    scrub_secrets(text)\n"
    "    out[name] = time.perf_counter() - t\n"
    "print(json.dumps(out))\n")


def _redos_last_started(stderr) -> str | None:
    """從（可能被截斷、可能是 bytes 的）stderr 取出最後一組開跑的名稱；沒有就回 None。"""
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", "replace")
    last = None
    for line in (stderr or "").splitlines():
        if line.startswith(_REDOS_START_TAG):
            try:
                last = json.loads(line[len(_REDOS_START_TAG):])
            except ValueError:
                continue
    return last


def _run_redos_cases(cases: list, *, script: str = _REDOS_SCRIPT,
                     timeout_s: float = _REDOS_TOTAL_TIMEOUT_S) -> dict:
    """在子程序跑 `cases`，回 `{name: 秒}`；逾時 → `pytest.fail`，訊息點名卡住的那一組（SEC-r5）。"""
    env = {**os.environ, "PYTHONPATH": str(_REPO), "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run([sys.executable, "-c", script], input=json.dumps(cases),
                              capture_output=True, text=True, cwd=str(_REPO), env=env,
                              timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        stuck = _redos_last_started(exc.stderr)
        where = (f"卡在第 {[c[0] for c in cases].index(stuck) + 1}/{len(cases)} 組：{stuck}"
                 if stuck in {c[0] for c in cases} else "（子程序沒來得及回報開跑到哪一組）")
        pytest.fail(f"清洗函式在 {len(cases)} 組 {_REDOS_N} 字元對抗輸入上超過 "
                    f"{timeout_s} 秒 —— 疑似回溯爆炸（ReDoS）；{where}")
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


class TestQ1r5NoReDoS:
    def test_every_adversarial_input_is_linear_and_fails_fast(self):
        cases = ([[f"unit {u!r}", _rep(u, _REDOS_N)] for u in _ADVERSARIAL_UNITS]
                 + [[f"prefix {p!r}", p + _rep(u, _REDOS_N)] for p, u in _ADVERSARIAL_PREFIXED])
        times = _run_redos_cases(cases)
        assert set(times) == {c[0] for c in cases}
        slow = {k: round(v, 2) for k, v in times.items() if v > _REDOS_PER_CASE_S}
        assert not slow, slow

    # ── SEC-r5：逾時訊息要點名是哪一組 ────────────────────────────────
    def test_timeout_message_names_the_stuck_case(self):
        """把第 2 組換成會睡死的替身：逾時訊息必須點名第 2 組，而不是只說「有一組太慢」。"""
        hang = _REDOS_SCRIPT.replace(
            "    scrub_secrets(text)\n",
            "    scrub_secrets(text) if name != 'unit \\'HANG\\'' else time.sleep(60)\n")
        assert hang != _REDOS_SCRIPT, "前提：替身腳本真的換到了呼叫那一行"
        cases = [["unit 'a'", "a"], ["unit 'HANG'", "x"], ["unit 'b'", "b"]]
        with pytest.raises(pytest.fail.Exception) as ei:
            _run_redos_cases(cases, script=hang, timeout_s=3.0)
        msg = str(ei.value)
        assert "ReDoS" in msg
        assert "unit 'HANG'" in msg and "第 2/3 組" in msg, msg
        assert "unit 'a'" not in msg and "unit 'b'" not in msg, msg

    def test_last_started_parser(self):
        tag = _REDOS_START_TAG
        assert _redos_last_started(None) is None
        assert _redos_last_started("") is None
        assert _redos_last_started(f'{tag}"x"\n{tag}"y"\n') == "y"
        assert _redos_last_started(f'{tag}"x"\n{tag}"y"\n'.encode()) == "y"
        assert _redos_last_started(f'noise\n{tag}"x"\n{tag}"y') == "x"   # 截斷的最後一行不算


# ── `ai_qa_service._scrub_secrets` 改引用 L0 後 byte-identical ─────────────────
#: 搬家前的實作（regex 與函式體逐字複製自 `src/services/ai_qa_service.py` 搬家前的版本）。
_OLD_QS_RE = re.compile(r"\b(key|token|api[_-]?key|access[_-]?token)=[^&\s\"'<>]+", re.IGNORECASE)
_OLD_KEY_RE = re.compile(r"AIza[0-9A-Za-z_\-]{10,}")


def _old_scrub(s) -> str:
    out = _OLD_QS_RE.sub(lambda m: m.group(1) + "=***", str(s))
    return _OLD_KEY_RE.sub("AIza***", out)


def _fuzz_corpus(n: int = 4000) -> list:
    rnd = random.Random(20260926)
    atoms = ["key=", "token=", "api_key=", "API-KEY=", "access_token=", "Access-Token=",
             "refresh_token=", "AIza", "AIzaSy0123456789_-ab", "&", "?", " ", "\"", "'", "<", ">",
             "=", "abc", "XYZ123", "查無", "/home/u/x.toml", "ya29.", "1//", "\n", "_", "-",
             "key", "token", "keytoken=", "mykey=", "b'\\xff'", "UnicodeDecodeError("]
    out = [rnd.choice([None, 0, 1.5, b"key=x", ("key=a",)])]
    for _ in range(n):
        out.append("".join(rnd.choice(atoms) for _ in range(rnd.randint(0, 12))))
    return out + [r for r, _g, _k in _LEAKY.values()] + list(_PLAIN)


class TestAiQaByteIdentical:
    def test_ai_qa_uses_the_l0_function(self):
        assert AIQ._scrub_secrets is SSC.scrub_query_secrets

    def test_byte_identical_to_the_pre_move_implementation(self):
        for s in _fuzz_corpus():
            assert AIQ._scrub_secrets(s) == _old_scrub(s), repr(s)

    def test_the_two_regexes_moved_verbatim(self):
        assert SSC.QUERY_SECRET_RE.pattern == _OLD_QS_RE.pattern
        assert SSC.QUERY_SECRET_RE.flags == _OLD_QS_RE.flags
        assert SSC.GOOGLE_API_KEY_RE.pattern == _OLD_KEY_RE.pattern

    def test_existing_fmt_gemini_error_unchanged(self):
        e = RuntimeError("403 for url https://x/y?key=AIzaSyABCDEFGHIJKLMNOP /home/a/b.py")
        assert AIQ._fmt_gemini_error("P", e) == (
            "P:" + _old_scrub(f"{type(e).__name__}: {e}"))


# ── 三個出口的行為 ─────────────────────────────────────────────────
_LEAK_ERR = _LEAKY["unicode_decode_repr"][0]
_PATH_ERR = _LEAKY["posix_path"][0]


def _preview_with_watchlist_error(P, err: str):
    return P.build_holdings_preview_card(P.HoldingsReadout(
        requested=True, submitted=True, bound=True, portfolio_name="核心",
        holdings=({"ticker": "0056", "name": "高股息", "held": True, "lots": 1.0,
                   "avg_price": 30.0, "asset_kind": "etf"},),
        watchlist_error=err))


class _FakeSt:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def markdown(self, text, **_k):
        self.calls.append(("markdown", str(text)))

    def error(self, text, **_k):
        self.calls.append(("error", str(text)))


def _l4_error_text(mod, monkeypatch, err: str) -> str:
    fake = _FakeSt()
    monkeypatch.setattr(mod, "st", fake)
    mod.render_holding_detail("0056", "高股息", (), error=err)
    errs = [t for k, t in fake.calls if k == "error"]
    assert len(errs) == 1
    return errs[0]


class TestQ1r5ExitPoints:
    @pytest.mark.parametrize("err", [_LEAK_ERR, _PATH_ERR], ids=["decode", "path"])
    def test_a_error_why_is_scrubbed(self, err):
        why = PH._error_why(PH.SRC_BINDING, err)
        assert "S3CR3T_A" not in why and "/home/alice" not in why
        assert why == f"{PH.SRC_BINDING}拋出例外：{SSC.scrub_secrets(err)}"

    @pytest.mark.parametrize("err", ["RuntimeError('token boom')", "KeyError('sid boom')", ""])
    def test_b_error_why_plain_errors_unchanged(self, err):
        _clean = PH.scrub_state_glyphs(err)[0]
        assert PH._error_why(PH.SRC_BINDING, err) == (
            f"{PH.SRC_BINDING}拋出例外：{_clean or PH.UNKNOWN_ERROR_TEXT}")

    def test_a_every_red_card_on_the_page_goes_through_error_why(self):
        """整頁的紅卡 why 都經 `_error_why()`：用戰情表例外把整個家族畫一遍，金鑰值一個都不在。"""
        st_ = PH.StationReadout(requested=True, submitted=True, bound=True, error=_LEAK_ERR)
        builts = list(PH.build_conclusion_cards(st_)) + [
            PH.build_lightwall_card(st_), PH.build_take_profit_card(st_),
            PH.build_allocation_split_card(st_), PH.build_core_satellite_card(st_),
            PH.build_ai_summary_card(PH.load_ai_summary(True, st_, PH.SwitchReadout(
                requested=True, submitted=True)), st_)]
        for built in builts:
            assert built[0].state == UI_FAILED, built[0].key
            assert "S3CR3T_A" not in _card_text(built), built[0].key

    def test_a_preview_watchlist_error_fact_is_scrubbed(self):
        built = _preview_with_watchlist_error(PH, _PATH_ERR)
        _txt = _card_text(built)
        assert "/home/alice" not in _txt and "***/secrets.toml" in _txt

    def test_b_preview_watchlist_plain_error_unchanged(self):
        facts = dict(_preview_with_watchlist_error(PH, "RuntimeError('quota')")[1])
        assert facts["⚠️ 觀察清單這一輪讀不到"].startswith("RuntimeError('quota') —— ")

    def test_a_l4_holding_detail_error_is_scrubbed(self, monkeypatch):
        out = _l4_error_text(SC, monkeypatch, _LEAK_ERR)
        assert "S3CR3T_A" not in out and out == "這一檔整批抓取失敗:UnicodeDecodeError"

    def test_a_l4_masks_are_markdown_escaped(self, monkeypatch):
        """`st.error` 吃 Markdown：遮罩 `***` 以 `\\*` 跳脫，同一行兩個遮罩不會被當成粗斜體吃掉。"""
        out = _l4_error_text(SC, monkeypatch, "url?key=AIzaSyABCDEFGHIJKLMN&token=zzz")
        assert out == "這一檔整批抓取失敗:url?key=\\*\\*\\*&token=\\*\\*\\*"

    def test_b_l4_plain_error_unchanged(self, monkeypatch):
        assert _l4_error_text(SC, monkeypatch, "HTTPError 502") == "這一檔整批抓取失敗:HTTPError 502"


_PH_SCRUB_WHY = ("    _clean, _n = scrub_state_glyphs(scrub_secrets(error) if error else error)\n",
                 "    _clean, _n = scrub_state_glyphs(error)\n")
_PH_SCRUB_WATCH = ('            f"{scrub_secrets(holdings.watchlist_error)} —— 持股本身不受影響，"\n',
                   '            f"{holdings.watchlist_error} —— 持股本身不受影響，"\n')
_SC_SCRUB = ('        _err = scrub_secrets(error).replace("*", "\\\\*")\n',
             '        _err = str(error).replace("*", "\\\\*")\n')


class TestQ1r5Mutations:
    def test_c_dropping_the_error_why_scrub_leaks(self):
        m = _mutant(PH, _PH_SCRUB_WHY)
        assert "S3CR3T_A" in m._error_why(m.SRC_BINDING, _LEAK_ERR)

    def test_c_dropping_the_watchlist_scrub_leaks(self):
        m = _mutant(PH, _PH_SCRUB_WATCH)
        assert "/home/alice" in _card_text(_preview_with_watchlist_error(m, _PATH_ERR))

    def test_c_dropping_the_l4_scrub_leaks(self, monkeypatch):
        m = _mutant(SC, _SC_SCRUB)
        assert "S3CR3T_A" in _l4_error_text(m, monkeypatch, _LEAK_ERR)
