"""VN1-STORE「Production Wiring」批（2026-10-20；production 寫入**仍未核准**）— reader／writer 接線守衛。

守：
1. 讀取端 L3 `risk_cap_history_reader_service.read_history`：OK／EMPTY（START_RECORDING）／NO_CREDENTIAL／
   NO_SHEET_ID／TAB_MISSING／SCHEMA_MISMATCH／API_ERROR／IDENTITY_MISMATCH；過期 ⇒ STALE；缺值原樣（⛔ 不轉 0）；
   失敗 ⛔ 不快取、成功才快取；detail 不外洩例外原文／Sheet ID；⛔ 不讀 os.environ、⛔ 不碰持股 Sheet／fund-nav。
2. L1 `build_reader_client`：只 `from_service_account_info(info, READER_SCOPES)`、⛔ 永不 `google.auth.default`；
   拒 writer／fund-nav／external_account／其他身分。
3. L1 writer：`check_writer_credentials_file` 只收 WIF `external_account`（拒 JSON key／任何 key 檔／缺 GAC／
   impersonation 目標不符）；`build_writer_client` 第一步就是閘門 ⇒ 旗標 False 時連 `google.auth.default` 都不會呼叫。
   reader 與 writer 憑證不可互換。
4. 閘門：~~`PRODUCTION_WRITE_APPROVED` 仍為 False~~、是 `load_writer_credentials_or_refuse` 的第一個檢查；
   ⛔ 全 repo 沒有任何地方（含測試）把它設成 True。
   📌 2026-10-21（DEC-066 A，Step 4 子步驟 1；有意識的變更，不是漏刪）：L0 宣告本身改 True（一次性旗標 PR，
   首次寫入嘗試後下一個 PR 立刻改回 False）；「L0 宣告之外沒有任何地方設 True」照守。
   📌 2026-10-22（DEC-066 狀態補註三，客戶裁示 B；有意識的變更，不是漏刪）：窗口因 dry-run Fail-Stop 關閉，
   旗標已回 False；`test_no_code_sets_approved_true` 掃描已重新包含 L0 policy 檔（全 repo 任何 `= True` 都紅燈）。
5. workflow `production-write`：只 workflow_dispatch、寫入 job 只限 main、needs compute、第一個 Python 步驟就是閘門
   （index < auth）、id-token 只在寫入 job、寫入 job env 只有 System Risk Cap Sheet ID（＋寫入總開關），
   ⛔ 持股 Sheet ID／GCP_SERVICE_ACCOUNT_JSON／FinMind／proxy secrets／credentials_json；全部 action 以 SHA 釘版。
6. 突變自驗（in-test）：auth 移到閘門前、拔掉閘門、寫入 env 多一個持股 Sheet ID、compute job 拿 id-token… ⇒ 轉紅。
⛔ 不依賴 PyYAML（沿用 `tests/test_vn1_wif_auth_only.py` 的標準函式庫受限解析器）。不連網：Google 依賴全以假物件替換。
⛔ 本檔**不**修改 `PRODUCTION_WRITE_APPROVED`（連 monkeypatch 都沒有）—— 核准後的檢查一律直接測各檢查函式。
   📌 2026-10-21（DEC-066 A；有意識的變更）：上句「連 monkeypatch 都沒有」不再成立 —— 守「未核准 ⇒ 拒絕」的測試
   以 `force_write_unapproved` 把旗標 monkeypatch 回 **False**（⛔ 只准設 False）；設 True 仍全面禁止。
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from shared import risk_cap_history_policy as P
from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION
from src.data.risk_cap import history as L1H
from src.services import risk_cap_history_reader_service as R
from tests._git_tracked import REPO_MIN_TRACKED, only_tracked
from tests.test_batch_z64 import NOW
from tests.test_p01_macro_refresh import _mutated_module
from tests.test_vn1_store_poc import _invalid, _row
from tests.test_vn1_wif_auth_only import (
    WIF_JOB_PINS,
    WIF_PROVIDER,
    _auth_step,
    _job_text,
    _parse,
    _yaml_lines,
    force_write_unapproved,
)

REPO = Path(__file__).resolve().parents[1]
WORKFLOW_REL = ".github/workflows/risk_cap_history_poc.yml"
POC_SCRIPT_REL = "scripts/risk_cap_history_poc.py"
READER_SVC_REL = "src/services/risk_cap_history_reader_service.py"
L1_REL = "src/data/risk_cap/history.py"

#: 測試用假 Sheet ID（⛔ 不是任何真實 Sheet）。
SID = "TEST_SYSTEM_SHEET_ID"
#: 例外訊息裡的哨兵：不得出現在 detail／輸出。
LEAK = "LEAK-SENTINEL-sheet-1AbCdEf-token-ya29"
#: 假 key 內容（⛔ 不是金鑰；`from_service_account_info` 一律被替換成假物件）。
_FAKE_KEY = "fake-not-a-key"


def _info(**over):
    d = {"type": "service_account", "project_id": "test", "client_email": P.READER_SA_EMAIL,
         "private_key": _FAKE_KEY, "private_key_id": "x"}
    d.update(over)
    return d


def _secrets(**over):
    d = {P.READER_SECRETS_TABLE: _info(), P.READER_SHEET_ID_SECRET_KEY: SID}
    d.update(over)
    return d


class _FakeWS:
    def __init__(self, rows, *, sid=SID, title=P.HISTORY_WORKSHEET_NAME, exc=None):
        self.spreadsheet_id = sid
        self.title = title
        self._rows = rows
        self._exc = exc
        self.reads = 0

    def get_all_values(self):
        self.reads += 1
        if self._exc is not None:
            raise self._exc
        return [list(r) for r in self._rows]

    def append_row(self, values, value_input_option=None):   # pragma: no cover —— 讀取端不得寫
        pytest.fail("讀取端不得寫入")


class _FakeBook:
    def __init__(self, ws, tab_exc=None):
        self._ws = ws
        self._tab_exc = tab_exc

    def worksheet(self, title):
        if self._tab_exc is not None:
            raise self._tab_exc
        assert title == P.HISTORY_WORKSHEET_NAME
        return self._ws


class _FakeClient:
    def __init__(self, book, open_exc=None):
        self._book = book
        self._open_exc = open_exc
        self.opened: list[str] = []

    def open_by_key(self, key):
        self.opened.append(key)
        if self._open_exc is not None:
            raise self._open_exc
        return self._book


def _factory_for(ws=None, *, tab_exc=None, open_exc=None, calls=None):
    def _f(info):
        if calls is not None:
            calls.append(dict(info))
        return _FakeClient(_FakeBook(ws, tab_exc=tab_exc), open_exc=open_exc)
    return _f


def _no_factory(info):
    pytest.fail("前置檢查不過時不得建立 client")


def _values(*rows):
    return [list(P.HISTORY_COLUMNS)] + [[r[c] for c in P.HISTORY_COLUMNS] for r in rows]


class _FakeResponse:
    status_code = 403
    text = LEAK

    def json(self):
        return {"error": {"code": 403, "message": LEAK, "status": "PERMISSION_DENIED"}}


@pytest.fixture(autouse=True)
def _clear_cache():
    R.clear_read_cache()
    yield
    R.clear_read_cache()


def _assert_cache_ttl(mod, rel_text: str | None = None) -> None:
    """快取 TTL 必須是 SSOT `TTL_30MIN`：模組常數、裝飾器實際收到的 ttl（有 streamlit 時）、原始碼裡的裝飾器寫法。"""
    from shared.ttls import TTL_30MIN
    assert mod.HISTORY_READ_TTL_S == TTL_30MIN
    info = getattr(mod._fetch_records_cached, "_info", None)
    if info is not None:
        assert info.ttl == TTL_30MIN, info.ttl
    tree = ast.parse(rel_text if rel_text is not None else (REPO / READER_SVC_REL).read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_fetch_records_cached")
    decos = [d for d in fn.decorator_list if isinstance(d, ast.Call) and ast.unparse(d.func) == "st.cache_data"]
    assert len(decos) == 1
    ttl = [k.value for k in decos[0].keywords if k.arg == "ttl"]
    assert len(ttl) == 1 and ast.unparse(ttl[0]) == "HISTORY_READ_TTL_S", [ast.unparse(t) for t in ttl]
    imp = [n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == "shared.ttls"]
    assert [(a.name, a.asname) for n in imp for a in n.names if (a.asname or a.name) == "TTL_30MIN"] == \
        [("TTL_30MIN", None)]


def _read(secrets=None, factory=None, *, expected="2026-10-14", now=NOW):
    return R.read_history(expected_date=expected, now=now, secrets=_secrets() if secrets is None else secrets,
                          client_factory=factory)


# ══════════════════════════════════════════════════════════════════════════
# 1. 讀取端 L3
# ══════════════════════════════════════════════════════════════════════════
class TestReaderService:
    def test_ok_path_comparable(self):
        prev = _row(**{P.COL_RECORD_DATE: "2026-10-13", P.COL_EXPOSURE_LIMIT_PCT: "59",
                       P.COL_INPUT_ASOF: '{"VIX_Index":"2026-10-12"}'})
        ws = _FakeWS(_values(prev, _row()))
        calls = []
        res = _read(factory=_factory_for(ws, calls=calls))
        assert res.status == P.READ_STATUS_OK
        assert len(res.rows) == 2 and res.rows[1][P.COL_EXPOSURE_LIMIT_PCT] == "60"
        assert res.compare is not None and res.compare.status == P.COMPARE_COMPARABLE
        assert calls == [_info()]                                    # 只拿 reader 表格內容建 client

    def test_opens_by_injected_id_only(self):
        ws = _FakeWS(_values(_row()))
        holder = {}

        def _f(info):
            holder["c"] = _FakeClient(_FakeBook(ws))
            return holder["c"]
        assert _read(factory=_f).status == P.READ_STATUS_OK
        assert holder["c"].opened == [SID]

    @pytest.mark.parametrize("secrets", [
        {},                                                          # 沒有表格
        {P.READER_SHEET_ID_SECRET_KEY: SID},                         # 只有 Sheet ID
        {P.READER_SECRETS_TABLE: {}, P.READER_SHEET_ID_SECRET_KEY: SID},   # 空表格
        {P.READER_SECRETS_TABLE: "not-a-table", P.READER_SHEET_ID_SECRET_KEY: SID},
        # 既有的其他身分表格不得被當成 reader（⛔ 不沿用 [gcp_service_account]）
        {"gcp_service_account": _info(), P.READER_SHEET_ID_SECRET_KEY: SID},
    ])
    def test_missing_credential_table(self, secrets):
        res = _read(secrets, _no_factory)
        assert res.status == P.READ_STATUS_NO_CREDENTIAL and res.compare is None and res.rows == ()

    def test_secrets_unreadable_is_no_credential(self):
        class _Broken:
            def get(self, key):
                raise FileNotFoundError(LEAK)
        res = _read(_Broken(), _no_factory)
        assert res.status == P.READ_STATUS_NO_CREDENTIAL and LEAK not in res.detail

    @pytest.mark.parametrize("sid", [None, "", "   ", f"https://docs.google.com/spreadsheets/d/{SID}/edit",
                                     "a/b", 123])
    def test_missing_or_bad_sheet_id(self, sid):
        s = _secrets()
        if sid is None:
            s.pop(P.READER_SHEET_ID_SECRET_KEY)
        else:
            s[P.READER_SHEET_ID_SECRET_KEY] = sid
        res = _read(s, _no_factory)
        assert res.status == P.READ_STATUS_NO_SHEET_ID and res.compare is None
        assert SID not in res.detail

    def test_tab_missing(self):
        import gspread.exceptions as gse
        res = _read(factory=_factory_for(None, tab_exc=gse.WorksheetNotFound(LEAK)))
        assert res.status == P.READ_STATUS_TAB_MISSING and res.compare is None and LEAK not in res.detail

    @pytest.mark.parametrize("values", [
        [[c for c in P.HISTORY_COLUMNS if c != P.COL_EXPOSURE_LIMIT_PCT]],        # 缺必要欄
        [list(reversed(P.HISTORY_COLUMNS))],                                      # 順序不同
        [["date", "value"], ["2026-10-14", "60"]],                               # 別的表
        [list(P.HISTORY_COLUMNS), ["x"] * (len(P.HISTORY_COLUMNS) + 1)],          # 資料列欄數超過表頭
    ])
    def test_schema_mismatch(self, values):
        res = _read(factory=_factory_for(_FakeWS(values)))
        assert res.status == P.READ_STATUS_SCHEMA_MISMATCH and res.compare is None and res.rows == ()

    @pytest.mark.parametrize("make_exc", [
        lambda: __import__("gspread.exceptions", fromlist=["APIError"]).APIError(_FakeResponse()),
        lambda: __import__("requests.exceptions", fromlist=["ConnectionError"]).ConnectionError(LEAK),
        lambda: __import__("google.auth.exceptions", fromlist=["RefreshError"]).RefreshError(LEAK),
        lambda: TimeoutError(LEAK),
    ])
    @pytest.mark.parametrize("where", ["read", "open"])
    def test_api_error_classified_not_swallowed(self, make_exc, where, capsys):
        exc = make_exc()
        if where == "read":
            f = _factory_for(_FakeWS([], exc=exc))
        else:
            f = _factory_for(None, open_exc=exc)
        res = _read(factory=f)
        assert res.status == P.READ_STATUS_API_ERROR and res.compare is None and res.rows == ()
        assert type(exc).__name__ in res.detail and LEAK not in res.detail
        out = capsys.readouterr().out
        assert P.READ_STATUS_API_ERROR in out and LEAK not in out        # 有記 log、不外洩原文

    def test_programming_error_is_not_classified(self):
        """一般程式錯誤（bug）⛔ 不得被包成 API_ERROR 吞掉 —— 照樣炸（CLAUDE.md §1）。"""
        with pytest.raises(KeyError):
            _read(factory=_factory_for(_FakeWS([], exc=KeyError("bug"))))

    @pytest.mark.parametrize("values", [[], [list(P.HISTORY_COLUMNS)]])
    def test_empty_history_is_empty_start_recording(self, values):
        res = _read(factory=_factory_for(_FakeWS(values)))
        assert res.status == P.READ_STATUS_EMPTY and res.rows == ()
        assert res.compare is not None and res.compare.status == P.COMPARE_START_RECORDING
        assert res.compare.current is None and res.compare.previous is None

    def test_stale_preserved(self):
        old = _row(**{P.COL_RECORD_DATE: "2026-10-01", P.COL_SNAPSHOT_TIMESTAMP: "2026-10-01 10:00:00"})
        res = _read(factory=_factory_for(_FakeWS(_values(old))), now=NOW + timedelta(days=1), expected="2026-10-15")
        assert res.status == P.READ_STATUS_OK
        assert res.compare.status == P.COMPARE_STALE and res.compare.previous is None

    def test_missing_values_not_zero(self):
        bad = _invalid()
        sparse = [list(P.HISTORY_COLUMNS), [bad[c] for c in P.HISTORY_COLUMNS][:6]]   # Sheets 省略列尾空白
        res = _read(factory=_factory_for(_FakeWS(sparse)))
        assert res.status == P.READ_STATUS_OK
        row = res.rows[0]
        assert row[P.COL_EXPOSURE_LIMIT_PCT] == "" and row[P.COL_GIT_SHA] == ""
        assert all(v != "0" for k, v in row.items() if k not in (P.COL_RUN_ID,))
        assert res.compare.status == P.COMPARE_CURRENT_NOT_VALID

    def test_failure_not_cached_success_cached(self):
        import gspread.exceptions as gse
        fail = _factory_for(None, tab_exc=gse.WorksheetNotFound("x"))
        ok = _factory_for(_FakeWS(_values(_row())))
        assert _read(factory=fail).status == P.READ_STATUS_TAB_MISSING
        assert _read(factory=ok).status == P.READ_STATUS_OK                # 失敗沒有被快取
        if not callable(getattr(R._fetch_records_cached, "clear", None)):
            pytest.skip("無 streamlit：沒有快取層可驗")
        assert _read(factory=fail).status == P.READ_STATUS_OK              # 成功被快取（命中快取）
        R.clear_read_cache()
        assert _read(factory=fail).status == P.READ_STATUS_TAB_MISSING

    def test_ttl_from_ssot(self):
        _assert_cache_ttl(R)
        assert not hasattr(P, "READ_STATUSES_CACHEABLE")     # 回修第 1 輪：沒人用的常數已移除

    @pytest.mark.parametrize("old,new", [
        ("@st.cache_data(ttl=HISTORY_READ_TTL_S, show_spinner=False)",
         "@st.cache_data(ttl=None, show_spinner=False)"),
        ("@st.cache_data(ttl=HISTORY_READ_TTL_S, show_spinner=False)", "@st.cache_data(show_spinner=False)"),
        ("HISTORY_READ_TTL_S: int = TTL_30MIN\n", "HISTORY_READ_TTL_S: int = TTL_1HOUR\n"),
        ("from shared.ttls import TTL_30MIN\n", "from shared.ttls import TTL_1HOUR as TTL_30MIN\n"),
    ])
    def test_ttl_mutation_turns_red(self, old, new):
        swaps = [(old, new)]
        if new.startswith("HISTORY_READ_TTL_S"):          # 換常數：另需把 TTL_1HOUR import 進來
            swaps.append(("from shared.ttls import TTL_30MIN\n", "from shared.ttls import TTL_30MIN, TTL_1HOUR\n"))
        mut = _mutated_module(READER_SVC_REL, *swaps)
        with pytest.raises(AssertionError):
            _assert_cache_ttl(mut, rel_text=(REPO / READER_SVC_REL).read_text(encoding="utf-8").replace(old, new))

    @pytest.mark.parametrize("limit", ["", "   ", "abc", "nan", "inf", "-inf", "30%"])
    def test_valid_row_without_usable_limit_is_content_suspect(self, limit, capsys):
        rows = [_row(**{P.COL_RECORD_DATE: "2026-10-13", P.COL_EXPOSURE_LIMIT_PCT: "59"}),
                _row(**{P.COL_EXPOSURE_LIMIT_PCT: limit})]
        res = _read(factory=_factory_for(_FakeWS(_values(*rows))))
        assert res.status == P.READ_STATUS_CONTENT_SUSPECT
        assert res.compare is None and res.rows == ()                 # ⛔ 不送進比較、不回傳半套資料
        assert "第 3 列" in res.detail and SID not in res.detail       # 表頭第 1 列 ⇒ 第 2 筆資料＝第 3 列
        assert "0" not in [r.get(P.COL_EXPOSURE_LIMIT_PCT) for r in res.rows]
        assert P.READ_STATUS_CONTENT_SUSPECT in capsys.readouterr().out

    def test_content_suspect_lists_all_rows(self):
        rows = [_row(**{P.COL_RECORD_DATE: "2026-10-12", P.COL_EXPOSURE_LIMIT_PCT: ""}),
                _invalid(**{P.COL_RECORD_DATE: "2026-10-13"}),                  # 非 VALID 空白 ⇒ 正常
                _row(**{P.COL_EXPOSURE_LIMIT_PCT: "x"})]
        res = _read(factory=_factory_for(_FakeWS(_values(*rows))))
        assert res.status == P.READ_STATUS_CONTENT_SUSPECT and "第 2、4 列" in res.detail

    def test_valid_numeric_limits_are_ok(self):
        rows = [_row(**{P.COL_RECORD_DATE: "2026-10-13", P.COL_EXPOSURE_LIMIT_PCT: "0"}),   # 0 是真值，不是缺值
                _row(**{P.COL_EXPOSURE_LIMIT_PCT: "30.5"})]
        assert _read(factory=_factory_for(_FakeWS(_values(*rows)))).status == P.READ_STATUS_OK

    def test_content_suspect_not_cached(self):
        bad = _factory_for(_FakeWS(_values(_row(**{P.COL_EXPOSURE_LIMIT_PCT: ""}))))
        good = _factory_for(_FakeWS(_values(_row())))
        assert _read(factory=bad).status == P.READ_STATUS_CONTENT_SUSPECT
        assert _read(factory=good).status == P.READ_STATUS_OK               # 疑義結果沒有被快取

    def test_content_check_mutation_turns_red(self):
        mut = _mutated_module(READER_SVC_REL, ("    _check_valid_rows(records)", "    pass  # mutated"))
        if callable(getattr(mut._fetch_records_cached, "clear", None)):
            mut._fetch_records_cached.clear()
        rows = [_row(**{P.COL_RECORD_DATE: "2026-10-13", P.COL_EXPOSURE_LIMIT_PCT: "59"}),
                _row(**{P.COL_EXPOSURE_LIMIT_PCT: ""})]
        res = mut.read_history(expected_date="2026-10-14", now=NOW, secrets=_secrets(),
                               client_factory=_factory_for(_FakeWS(_values(*rows))))
        assert res.status == P.READ_STATUS_OK and res.compare is not None    # 突變體把疑義資料送去比較
        assert _read(factory=_factory_for(_FakeWS(_values(*rows)))).status == P.READ_STATUS_CONTENT_SUSPECT

    def test_reader_build_errors_classified(self, monkeypatch):
        """經真的 `build_reader_client`：key 內容錯（GoogleAuthError／ValueError）⇒ NO_CREDENTIAL；程式 bug 照樣炸。"""
        import google.auth.exceptions as gae
        import gspread
        from google.oauth2 import service_account
        monkeypatch.setattr(gspread, "authorize", lambda creds: pytest.fail("不得建 client"))
        for exc in (gae.MalformedError(LEAK), gae.DefaultCredentialsError(LEAK), ValueError(LEAK)):
            def _boom(info, scopes=None, _e=exc):
                raise _e
            monkeypatch.setattr(service_account.Credentials, "from_service_account_info", staticmethod(_boom))
            res = _read(factory=None)
            assert res.status == P.READ_STATUS_NO_CREDENTIAL and type(exc).__name__ in res.detail
            assert LEAK not in res.detail
        for exc in (TypeError("bug"), KeyError("bug"), AttributeError("bug")):
            def _bug(info, scopes=None, _e=exc):
                raise _e
            monkeypatch.setattr(service_account.Credentials, "from_service_account_info", staticmethod(_bug))
            with pytest.raises(type(exc)):
                _read(factory=None)

    @pytest.mark.parametrize("info", [
        _info(client_email=P.WRITER_SA_EMAIL),
        _info(client_email="fund-nav@other-project.iam.gserviceaccount.com"),
        _info(client_email="someone@mystock20260823.iam.gserviceaccount.com"),
        _info(type="external_account"),
        _info(type="authorized_user"),
        {k: v for k, v in _info().items() if k != "client_email"},
    ])
    def test_identity_mismatch(self, info):
        res = _read(_secrets(**{P.READER_SECRETS_TABLE: info}), _no_factory)
        assert res.status == P.READ_STATUS_IDENTITY_MISMATCH and res.compare is None

    def test_opened_sheet_id_mismatch_is_identity_mismatch(self):
        res = _read(factory=_factory_for(_FakeWS(_values(_row()), sid="OTHER_SHEET")))
        assert res.status == P.READ_STATUS_IDENTITY_MISMATCH and "OTHER_SHEET" not in res.detail

    def test_invalid_key_is_no_credential(self):
        def _f(info):
            raise L1H.ReaderCredentialInvalid("reader key 無法載入（ValueError）")
        assert _read(factory=_f).status == P.READ_STATUS_NO_CREDENTIAL

    def test_result_frozen_and_vocab(self):
        res = _read(factory=_factory_for(_FakeWS([])))
        with pytest.raises(Exception):
            res.status = "x"   # type: ignore[misc]
        assert len(set(P.READ_STATUSES)) == len(P.READ_STATUSES) == 9


# ══════════════════════════════════════════════════════════════════════════
# 2. L1 reader client
# ══════════════════════════════════════════════════════════════════════════
class _FakeCreds:
    def __init__(self, email, scopes):
        self.service_account_email = email
        self.scopes = list(scopes)


@pytest.fixture
def google_fakes(monkeypatch):
    """替換 `from_service_account_info`／`gspread.authorize`；`google.auth.default` 一被呼叫就失敗。"""
    import google.auth
    import gspread
    from google.oauth2 import service_account

    seen = {"sa": [], "authorize": [], "timeout": []}

    def _from_info(info, scopes=None):
        seen["sa"].append((dict(info), tuple(scopes)))
        return _FakeCreds(info.get("client_email"), scopes)

    class _Client:
        """gspread `Client` 替身：只記 `set_timeout`（回修第 1 輪 2026-10-20：client 一律設逾時）。"""

        def set_timeout(self, timeout):
            seen["timeout"].append(timeout)

    client = _Client()
    seen["client"] = client

    def _authorize(creds):
        seen["authorize"].append(creds)
        return client

    def _default(*a, **k):
        raise AssertionError("google.auth.default 不得被呼叫")

    monkeypatch.setattr(service_account.Credentials, "from_service_account_info", staticmethod(_from_info))
    monkeypatch.setattr(gspread, "authorize", _authorize)
    monkeypatch.setattr(google.auth, "default", _default)
    return seen


class TestReaderClient:
    def test_builds_with_readonly_scope_only(self, google_fakes):
        assert L1H.build_reader_client(_info()) is google_fakes["client"]
        assert google_fakes["sa"] == [(_info(), P.READER_SCOPES)]
        assert google_fakes["authorize"][0].scopes == list(P.READER_SCOPES)
        # 📌 2026-10-20（Pre-Hardening 回修第 1 輪）：client 一律設逾時，值取自 L0
        assert google_fakes["timeout"] == [P.SHEETS_HTTP_TIMEOUT_S]

    @pytest.mark.parametrize("info", [
        _info(client_email=P.WRITER_SA_EMAIL),
        _info(client_email="fund-nav@x.iam.gserviceaccount.com"),
        _info(type="external_account"),
        {"type": "external_account", "service_account_impersonation_url":
            f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{P.WRITER_SA_EMAIL}:generateAccessToken"},
        "not-a-mapping",
    ])
    def test_rejects_non_reader(self, google_fakes, info):
        with pytest.raises(L1H.ReaderIdentityMismatch):
            L1H.build_reader_client(info)
        assert google_fakes["sa"] == [] and google_fakes["authorize"] == []

    def test_rejects_creds_with_other_scope(self, monkeypatch, google_fakes):
        from google.oauth2 import service_account
        monkeypatch.setattr(service_account.Credentials, "from_service_account_info",
                            staticmethod(lambda info, scopes=None: _FakeCreds(P.READER_SA_EMAIL, P.WRITER_SCOPES)))
        with pytest.raises(L1H.ReaderIdentityMismatch):
            L1H.build_reader_client(_info())
        assert google_fakes["authorize"] == []

    def test_bad_key_is_invalid_without_leak(self, monkeypatch, google_fakes):
        from google.oauth2 import service_account

        def _boom(info, scopes=None):
            raise ValueError(LEAK)
        monkeypatch.setattr(service_account.Credentials, "from_service_account_info", staticmethod(_boom))
        with pytest.raises(L1H.ReaderCredentialInvalid) as ei:
            L1H.build_reader_client(_info())
        assert LEAK not in str(ei.value)

    def test_reader_path_never_calls_default_static(self):
        """AST：`build_reader_client`／`check_reader_identity` 內沒有任何 `.default(` 呼叫、沒有讀環境變數。"""
        tree = ast.parse((REPO / L1_REL).read_text(encoding="utf-8"))
        fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        for name in ("build_reader_client", "check_reader_identity"):
            for n in ast.walk(fns[name]):
                if isinstance(n, ast.Attribute):
                    assert n.attr not in ("default", "environ", "getenv"), (name, n.attr)


# ══════════════════════════════════════════════════════════════════════════
# 3. L1 writer
# ══════════════════════════════════════════════════════════════════════════
def _wif_file(tmp_path, *, cred_type="external_account", sa=P.WRITER_SA_EMAIL, extra=None, name="gha-creds-t.json"):
    d = {"type": cred_type, "audience": "//iam.googleapis.com/" + WIF_PROVIDER,
         "credential_source": {"url": "https://example.invalid/token", "headers": {"Authorization": f"Bearer {LEAK}"}}}
    if sa is not None:
        d["service_account_impersonation_url"] = (
            f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{sa}:generateAccessToken")
    d.update(extra or {})
    p = tmp_path / name
    p.write_text(json.dumps(d), encoding="utf-8")
    return str(p)


class TestWriterCredentials:
    def test_accepts_wif_external_account(self, tmp_path):
        path = _wif_file(tmp_path)
        assert L1H.check_writer_credentials_file({P.GAC_ENV_VAR: path}) == path

    def test_refuses_missing_gac(self):
        with pytest.raises(L1H.WriterCredentialRefused, match="未設定"):
            L1H.check_writer_credentials_file({})

    def test_refuses_unreadable_or_not_json(self, tmp_path):
        with pytest.raises(L1H.WriterCredentialRefused):
            L1H.check_writer_credentials_file({P.GAC_ENV_VAR: str(tmp_path / "nope.json")})
        bad = tmp_path / "bad.json"
        bad.write_text("{not json " + LEAK, encoding="utf-8")
        with pytest.raises(L1H.WriterCredentialRefused) as ei:
            L1H.check_writer_credentials_file({P.GAC_ENV_VAR: str(bad)})
        assert LEAK not in str(ei.value)

    def test_refuses_service_account_json(self, tmp_path):
        """reader 的 key（或任何 SA JSON key）不得被當成 writer 憑證 —— 兩者不可互換。"""
        p = tmp_path / "sa.json"
        p.write_text(json.dumps(_info()), encoding="utf-8")
        with pytest.raises(L1H.WriterCredentialRefused, match="DEC-064 G1") as ei:
            L1H.check_writer_credentials_file({P.GAC_ENV_VAR: str(p)})
        assert _FAKE_KEY not in str(ei.value)

    @pytest.mark.parametrize("kw", [
        {"cred_type": "authorized_user"}, {"cred_type": "impersonated_service_account"}, {"cred_type": ""},
        {"extra": {"private_key": _FAKE_KEY}},                       # 任何 key 檔都不收
        {"sa": None},                                                # 沒有 impersonation
        {"sa": P.READER_SA_EMAIL},                                   # impersonate 的是 reader
        {"sa": "fund-nav@other.iam.gserviceaccount.com"},
    ])
    def test_refuses_other_files(self, tmp_path, kw):
        with pytest.raises(L1H.WriterCredentialRefused):
            L1H.check_writer_credentials_file({P.GAC_ENV_VAR: _wif_file(tmp_path, **kw)})

    def test_writer_refused_is_not_approved_subclass(self):
        assert issubclass(L1H.WriterCredentialRefused, L1H.ProductionWriteNotApproved)

    def test_wif_file_is_not_a_reader_credential(self, tmp_path):
        info = json.loads(Path(_wif_file(tmp_path)).read_text(encoding="utf-8"))
        with pytest.raises(L1H.ReaderIdentityMismatch):
            L1H.check_reader_identity(info)


class TestWriteGate:
    # ~~`test_flag_still_false`（斷言 L0／L1 旗標為 False）~~ —— 📌 2026-10-21（DEC-066 A，Step 4 子步驟 1；
    #   有意識的變更，不是漏刪）：客戶核准一次性旗標 PR ⇒ 改斷言核准狀態；且核准後其餘閘門照樣拒絕
    #   （寫入總開關未設 ⇒ 拒絕；⛔ 旗標只開第一道）。首次寫入嘗試後下一個 PR 立刻改回 False，本測試同步改回。
    # ~~`test_flag_approved_for_first_write`（斷言 True、第一道放行）~~ —— 📌 2026-10-22（DEC-066 狀態補註三，
    #   客戶裁示 B；有意識的變更，不是漏刪）：首次寫入 Fail-Stop、一次性窗口關閉 ⇒ 改回原名、改回斷言 False，
    #   並守「第一道就擋」（旗標 False ⇒ 連寫入總開關都還沒檢查就拒絕）。
    def test_flag_still_false(self):
        assert P.PRODUCTION_WRITE_APPROVED is False
        assert L1H.PRODUCTION_WRITE_APPROVED is False
        with pytest.raises(L1H.ProductionWriteNotApproved, match="尚未核准"):
            L1H.assert_production_write_approved()

    def test_gate_raises_even_fully_configured(self, tmp_path, monkeypatch):
        force_write_unapproved(monkeypatch)
        env = {P.WRITE_ENABLE_ENV_VAR: "1", P.HISTORY_SHEET_ID_ENV_VAR: SID, P.GAC_ENV_VAR: _wif_file(tmp_path)}
        with pytest.raises(L1H.ProductionWriteNotApproved, match="尚未核准"):
            L1H.load_writer_credentials_or_refuse(env)
        with pytest.raises(L1H.ProductionWriteNotApproved, match="尚未核准"):
            L1H.assert_production_write_approved()

    def test_build_writer_client_gate_first_no_default(self, tmp_path, monkeypatch):
        import google.auth
        import gspread

        def _boom(*a, **k):
            raise AssertionError("閘門未過不得呼叫 Google")
        monkeypatch.setattr(google.auth, "default", _boom)
        monkeypatch.setattr(gspread, "authorize", _boom)
        force_write_unapproved(monkeypatch)
        path = _wif_file(tmp_path)
        monkeypatch.setenv(P.GAC_ENV_VAR, path)
        env = {P.WRITE_ENABLE_ENV_VAR: "1", P.HISTORY_SHEET_ID_ENV_VAR: SID, P.GAC_ENV_VAR: path}
        with pytest.raises(L1H.ProductionWriteNotApproved, match="尚未核准"):
            L1H.build_writer_client(env)
        with pytest.raises(L1H.ProductionWriteNotApproved, match="尚未核准"):
            L1H.build_writer_client({})

    def test_gate_order_static(self):
        """AST：`load_writer_credentials_or_refuse` 第一個呼叫是核准檢查；`build_writer_client` 先呼叫閘門、
        再（且只在其後）呼叫 `google.auth.default`；預設 scope 用 `WRITER_SCOPES`。"""
        tree = ast.parse((REPO / L1_REL).read_text(encoding="utf-8"))
        fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

        def _calls(fn):
            out = []
            for n in ast.walk(fn):
                if isinstance(n, ast.Call):
                    f = n.func
                    name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
                    out.append((n.lineno, n.col_offset, name, n))
            return sorted(out, key=lambda t: (t[0], t[1]))

        load = [c[2] for c in _calls(fns["load_writer_credentials_or_refuse"]) if c[2] != "get"]
        assert load[0] == "assert_production_write_approved", load
        bw = _calls(fns["build_writer_client"])
        names = [c[2] for c in bw]
        # 📌 2026-10-20（Pre-Hardening 回修第 1 輪；有意識的變更）：~~`authorize`~~ 改經 `_authorized_client`
        #   （`gspread.authorize` ＋ L0 逾時；reader／writer 共用），順序意圖不變。
        assert names.index("load_writer_credentials_or_refuse") < names.index("default") \
            < names.index("_authorized_client")
        dflt = next(c[3] for c in bw if c[2] == "default")
        assert [k.arg for k in dflt.keywords] == ["scopes"]
        # 📌 2026-10-20（Pre-Hardening 批；有意識的變更，不是放寬）：~~`"WRITER_SCOPES" in unparse(scopes 引數)`~~ ——
        #   scope 改由 `writer_scopes(scopes)` 決定（只准恰好 WRITER_SCOPES 或 READER_SCOPES，寫後讀回用唯讀）。
        #   舊斷言的意圖（預設就是讀寫 scope、不會拿到更大的 scope）改守：預設值是 WRITER_SCOPES、
        #   傳給 `default` 的是 `writer_scopes` 的結果、且 `writer_scopes` 在閘門之後才呼叫。
        assert ast.unparse(dflt.keywords[0].value) == "list(chosen)"
        assert names.index("load_writer_credentials_or_refuse") < names.index("writer_scopes") < names.index("default")
        assert ast.unparse(fns["build_writer_client"].args.kw_defaults[0]) == "WRITER_SCOPES"
        gate = fns["assert_production_write_approved"]
        assert "PRODUCTION_WRITE_APPROVED" in ast.unparse(gate)
        # 閘門函式沒有任何參數（⛔ 沒有繞過用的旗標／環境變數）
        assert not gate.args.args and not gate.args.kwonlyargs

    def test_no_code_sets_approved_true(self):
        """全 repo（含測試）沒有任何地方把核准旗標設成 True（賦值、monkeypatch.setattr、setattr 皆算）。

        ~~📌 2026-10-21（DEC-066 A，Step 4 子步驟 1；有意識的變更，不是漏刪）：唯一例外是 L0 宣告本身
        （一次性旗標 PR，客戶 2026-10-21 核准）—— L0 檔排除在掃描外，改逐字釘死「恰好一行 `= True` 宣告」；
        其餘檔案（含測試）設 True 照樣紅燈。首次寫入嘗試後下一個 PR 改回 False，本測試同步改回。~~
        📌 2026-10-22（DEC-066 狀態補註三，客戶裁示 B；有意識的變更，不是漏刪）：一次性窗口關閉、旗標改回 False
        ⇒ 恢復 base 行為：**全掃（含 L0 policy 檔）**，任何 `= True` 都紅燈；L0 宣告逐字釘死為 `= False`。
        （順帶補上 QA 指出的漏洞：上一版把 policy 檔整檔排除，檔內其他位置的 `= True` 掃不到。）
        """
        name = "PRODUCTION_WRITE" + "_APPROVED"
        pats = [re.compile(name + r"\s*(?::\s*bool\s*)?=\s*True"),
                re.compile(r"setattr\([^)]*['\"]" + name + r"['\"]\s*,\s*True"),
                re.compile(name + r"\s*=\s*(?!False)\S")]
        files = only_tracked(REPO, [*REPO.rglob("*.py"), *REPO.rglob("*.yml"), *REPO.rglob("*.yaml")],
                             min_tracked=REPO_MIN_TRACKED, min_kept=200)
        hits = {}
        for f in files:
            t = f.read_text(encoding="utf-8")
            if name not in t:
                continue
            found = [p.pattern for p in pats if p.search(t)]
            if found:
                hits[f.relative_to(REPO).as_posix()] = found
        assert not hits, hits
        assert re.search(r"^PRODUCTION_WRITE_APPROVED: bool = False$",
                         (REPO / "shared/risk_cap_history_policy.py").read_text(encoding="utf-8"), re.MULTILINE)

    def test_gate_without_first_check_mutation_turns_red(self, tmp_path, monkeypatch):
        """突變：拔掉第一道核准檢查（旗標仍 False）⇒ 合格 WIF 檔就一路放行；真模組照樣拒絕。"""
        mut = _mutated_module(L1_REL, ("    env = os.environ if environ is None else environ\n"
                                       "    assert_production_write_approved()\n",
                                       "    env = os.environ if environ is None else environ\n"))
        force_write_unapproved(monkeypatch, mut)      # DEC-066 A：L0 已改 True ⇒ 旗標 monkeypatch 回 False
        path = _wif_file(tmp_path)
        env = {P.WRITE_ENABLE_ENV_VAR: "1", P.HISTORY_SHEET_ID_ENV_VAR: SID, P.GAC_ENV_VAR: path}
        assert mut.load_writer_credentials_or_refuse(env) == path
        with pytest.raises(L1H.ProductionWriteNotApproved):
            L1H.load_writer_credentials_or_refuse(env)

    def test_writer_type_check_mutation_turns_red(self, tmp_path):
        mut = _mutated_module(L1_REL, ("    if cred_type == READER_CREDENTIAL_TYPE:\n", "    if False:\n"),
                              ("    if cred_type != WRITER_CREDENTIAL_TYPE:\n", "    if False:\n"),
                              ('    if "private_key" in info:\n', "    if False:\n"))
        p = tmp_path / "sa.json"
        sa = _info()
        sa["service_account_impersonation_url"] = f"x/serviceAccounts/{P.WRITER_SA_EMAIL}:y"
        p.write_text(json.dumps(sa), encoding="utf-8")
        assert mut.check_writer_credentials_file({P.GAC_ENV_VAR: str(p)}) == str(p)     # 突變體收下 SA key
        with pytest.raises(L1H.WriterCredentialRefused):
            L1H.check_writer_credentials_file({P.GAC_ENV_VAR: str(p)})

    def test_reader_identity_mutation_turns_red(self):
        mut = _mutated_module(L1_REL, ("    if email != READER_SA_EMAIL:\n", "    if False:\n"),
                              ("    if email == WRITER_SA_EMAIL:\n", "    if False:\n"))
        info = _info(client_email=P.WRITER_SA_EMAIL)
        assert mut.check_reader_identity(info) == P.WRITER_SA_EMAIL                     # 突變體收下 writer
        with pytest.raises(L1H.ReaderIdentityMismatch):
            L1H.check_reader_identity(info)


class TestAdapterInjection:
    def test_injected_id_verified(self):
        ws = _FakeWS([], sid=SID)
        assert L1H.GspreadWorksheetAdapter(ws, expected_sheet_id=SID).get_all_values() == []
        with pytest.raises(L1H.HistoryTargetMismatch):
            L1H.GspreadWorksheetAdapter(_FakeWS([], sid="OTHER"), expected_sheet_id=SID)

    @pytest.mark.parametrize("bad", ["", "  ", f"https://docs.google.com/spreadsheets/d/{SID}/edit", "a b", None])
    def test_rejects_non_id(self, bad):
        with pytest.raises(L1H.HistoryTargetMismatch):
            L1H.GspreadWorksheetAdapter(_FakeWS([]), expected_sheet_id=bad)
        with pytest.raises(L1H.HistoryTargetMismatch):
            L1H.open_history_worksheet(_FakeClient(_FakeBook(_FakeWS([]))), bad)

    def test_injected_id_ignores_environ(self, monkeypatch):
        monkeypatch.setenv(P.HISTORY_SHEET_ID_ENV_VAR, "OTHER")
        assert L1H.GspreadWorksheetAdapter(_FakeWS([], sid=SID), expected_sheet_id=SID)


# ══════════════════════════════════════════════════════════════════════════
# 4. 腳本
# ══════════════════════════════════════════════════════════════════════════
def _load_poc():
    spec = importlib.util.spec_from_file_location("_poc_script_pw", REPO / POC_SCRIPT_REL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestScript:
    def test_check_write_gate_red(self, capsys, monkeypatch):
        force_write_unapproved(monkeypatch)           # DEC-066 A：L0 已改 True ⇒ 守「未核准 ⇒ 紅燈」需 monkeypatch 回 False
        assert _load_poc().main(["--check-write-gate"]) == 2
        assert "::error::production write is not approved" in capsys.readouterr().out

    def test_check_write_gate_imports_only_l0(self):
        tree = ast.parse((REPO / POC_SCRIPT_REL).read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_check_write_gate")
        mods = {n.module for n in ast.walk(fn) if isinstance(n, ast.ImportFrom)}
        mods |= {a.name for n in ast.walk(fn) if isinstance(n, ast.Import) for a in n.names}
        assert mods == {"shared.risk_cap_history_policy"}, mods
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        first_src_import = min(n.lineno for n in ast.walk(main)
                               if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("src."))
        gate_call = min(n.lineno for n in ast.walk(main)
                        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_check_write_gate")
        assert gate_call < first_src_import

    def test_write_refused_before_anything(self, tmp_path, monkeypatch, capsys):
        mod = _load_poc()
        rec = tmp_path / "rec.json"
        rec.write_text(json.dumps({"record": _row()}), encoding="utf-8")
        monkeypatch.setattr(L1H, "build_writer_client", lambda *a, **k: pytest.fail("閘門未過不得建 writer client"))
        monkeypatch.setattr(L1H, "upsert_record", lambda *a, **k: pytest.fail("閘門未過不得寫"))
        force_write_unapproved(monkeypatch)           # DEC-066 A：L0 已改 True ⇒ 旗標 monkeypatch 回 False
        monkeypatch.setenv(P.WRITE_ENABLE_ENV_VAR, "1")
        monkeypatch.setenv(P.HISTORY_SHEET_ID_ENV_VAR, SID)
        monkeypatch.setenv(P.GAC_ENV_VAR, _wif_file(tmp_path))
        assert mod.main(["--write", "--record", str(rec)]) == 2
        out = capsys.readouterr().out
        assert "尚未核准" in out and SID not in out

    def test_constants_match_scripts(self):
        spec = importlib.util.spec_from_file_location("_perm_pw", REPO / "scripts/risk_cap_permission_test.py")
        perm = importlib.util.module_from_spec(spec)
        sys.modules["_perm_pw"] = perm              # @dataclass 解析型別註解需要模組在 sys.modules
        try:
            spec.loader.exec_module(perm)
        finally:
            sys.modules.pop("_perm_pw", None)
        assert perm.WRITER_SA == P.WRITER_SA_EMAIL and perm.READER_SA == P.READER_SA_EMAIL
        assert perm.GAC_ENV_VAR == P.GAC_ENV_VAR


# ══════════════════════════════════════════════════════════════════════════
# 5. 靜態守衛
# ══════════════════════════════════════════════════════════════════════════
class TestStatic:
    def test_reader_service_reads_no_env_and_no_other_identity(self):
        src = (REPO / READER_SVC_REL).read_text(encoding="utf-8")
        tree = ast.parse(src)
        doc = tree.body[0].value.value          # 模組 docstring 原字串（講「不讀哪些」不算違規）
        for n in ast.walk(tree):
            if isinstance(n, ast.Attribute):
                assert n.attr not in ("environ", "getenv", "session_state", "default"), n.attr
            if isinstance(n, ast.Name):
                assert n.id != "os"
        code_strs = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                     and n.value != doc]
        for bad in ("GCP_SERVICE_ACCOUNT_JSON", "gcp_service_account", "google_oauth", "gsheet_tokens",
                    "fund-nav", "PORTFOLIO_SHEET_ID", "private_key"):
            assert not [v for v in code_strs if bad in v], bad
        imps = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imps |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not [i for i in imps if i and any(p in i for p in ("gsheet_portfolio", "gsheet_sa_reader",
                                                                    "oauth_state", "src.data.portfolio", "src.ui"))]

    def test_retired_reader_env_literal_gone(self):
        retired = "RISK_CAP_HISTORY_READER" + "_SA_JSON"
        assert not hasattr(P, "READER_SA_ENV_VAR")
        files = only_tracked(REPO, [*REPO.rglob("*.py"), *REPO.rglob("*.yml"), *REPO.rglob("*.yaml")],
                             min_tracked=REPO_MIN_TRACKED, min_kept=200)
        hits = [f.relative_to(REPO).as_posix() for f in files
                if not f.relative_to(REPO).as_posix().startswith("tests/") and retired in f.read_text(encoding="utf-8")]
        assert not hits, hits

    def test_secret_names_match_spec(self):
        spec = (REPO / "docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md").read_text(encoding="utf-8")
        assert f"[{P.READER_SECRETS_TABLE}]" in spec
        assert f"{P.READER_SHEET_ID_SECRET_KEY} = " in spec
        assert P.READER_SECRETS_TABLE != "gcp_service_account"

    def test_ui_untouched(self):
        # 📌 2026-10-20（Pre-Hardening 批；有意識的放寬，不是漏改）：app.py 只准 log-only smoke 的一行 import＋一行呼叫
        #   （守衛 `tests/test_vn1_store_poc.py::assert_app_only_smoke_hook`）；src/ui/ 仍一字不得提到。
        from tests.test_vn1_store_poc import assert_app_only_smoke_hook
        for f in (REPO / "src/ui").rglob("*.py"):
            assert "risk_cap_history" not in f.read_text(encoding="utf-8"), f
        assert_app_only_smoke_hook((REPO / "app.py").read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════════════
# 6. workflow
# ══════════════════════════════════════════════════════════════════════════
WRITE_RUN = ("python scripts/risk_cap_history_poc.py --write --record "
             "production-record/risk_cap_history_production_record.json")
GATE_RUN = "python3 scripts/risk_cap_history_poc.py --check-write-gate"
COMPUTE_RUN = "python scripts/risk_cap_history_poc.py --out risk_cap_history_production_record.json"
#: 📌 2026-10-20（Pre-Hardening 批）：寫入 job 只裝 hash 鎖定的最小依賴；compute job 的 sha256 交給寫入 job 比對。
WRITER_PIP_RUN = "pip install --require-hashes --no-deps -r requirements-risk-cap-writer.txt"
SHEET_WRITE_GROUP = "risk-cap-history-sheet-write"
SHA_OUT_RUN = ('set -euo pipefail; sha=$(sha256sum risk_cap_history_production_record.json | cut -d\' \' -f1); '
               'test -n "$sha"; echo "record artifact sha256=$sha"; echo "sha256=$sha" >> "$GITHUB_OUTPUT"')
SHA_CHECK_RUN = ('echo "$EXPECTED_RECORD_SHA256  production-record/risk_cap_history_production_record.json"'
                 ' | sha256sum --check --strict -')
ARTIFACT = "risk-cap-history-production-record"
EXTRA_PINS = {
    # 2026-10-20 `git ls-remote` 實查（輕量 tag ⇒ 即 commit）
    "actions/upload-artifact": ("ea165f8d65b6e75b540449e92b4886f43607fa02", "v4.6.2"),
    "actions/download-artifact": ("d3f86a106a0bac45b974a628896c90dbdf5c8093", "v4.3.0"),
}
PINS = {**WIF_JOB_PINS, **EXTRA_PINS}


def _wf() -> str:
    return (REPO / WORKFLOW_REL).read_text(encoding="utf-8")


def _code(block: str) -> str:
    return "\n".join(c for _, _, c in _yaml_lines(block))


def _pinned(job: dict, block: str) -> None:
    uses = [s["uses"] for s in job["steps"] if "uses" in s]
    for u in uses:
        action, ref = u.split("@", 1)
        assert re.fullmatch(r"[0-9a-f]{40}", ref), u
        sha, ver = PINS[action]
        assert ref == sha, u
        assert re.search(rf"^\s*uses:\s*{re.escape(u)}\s+#\s*{re.escape(ver)}\s*$", block, flags=re.MULTILINE), u
    assert len(re.findall(r"^\s*-?\s*uses:", block, flags=re.MULTILINE)) == len(uses)


def assert_production_write_guards(text: str) -> None:
    d = _parse(text)
    assert set(d["on"]) == {"workflow_dispatch"}
    assert "production-write" in d["on"]["workflow_dispatch"]["inputs"]["mode"]["options"]
    assert d["on"]["workflow_dispatch"]["inputs"]["mode"]["default"] == "dry-run"
    assert "schedule" not in _code(text) and "cron" not in _code(text)
    assert d["permissions"] == {"contents": "read"}
    jobs = d["jobs"]

    # ── compute：⛔ 沒有 id-token、⛔ 沒有 Google 憑證；非 main 第一步紅燈 ──
    c, ct = jobs["production_write_compute"], _job_text(text, "production_write_compute")
    assert c["if"] == "${{ inputs.mode == 'production-write' }}"
    assert c["permissions"] == {"contents": "read"}
    # 📌 2026-10-20（Pre-Hardening 批；有意識的變更）：多 `outputs`（只有紀錄檔 sha256，⛔ 不是 secret）。
    assert set(c) == {"if", "runs-on", "timeout-minutes", "permissions", "outputs", "steps"}, set(c)
    assert c["outputs"] == {"record_sha256": "${{ steps.record_sha256.outputs.sha256 }}"}
    i_c = [i for i, s in enumerate(c["steps"]) if s.get("run") == COMPUTE_RUN]
    i_sha = [i for i, s in enumerate(c["steps"]) if s.get("id") == "record_sha256"]
    i_up = [i for i, s in enumerate(c["steps"]) if s.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(i_c) == len(i_sha) == len(i_up) == 1 and i_c[0] < i_sha[0] < i_up[0]
    assert c["steps"][i_sha[0]]["run"] == SHA_OUT_RUN and "env" not in c["steps"][i_sha[0]]
    # 回修第 1 輪（2026-10-20）：明寫 bash＋set -euo pipefail
    assert c["steps"][i_sha[0]].get("shell") == "bash" and SHA_OUT_RUN.startswith("set -euo pipefail; ")
    assert c["steps"][0].get("if") == "github.ref != 'refs/heads/main'" and c["steps"][0]["run"].endswith("exit 1")
    _pinned(c, ct)
    assert {s["uses"].split("@")[0] for s in c["steps"] if "uses" in s} == {
        "actions/checkout", "actions/setup-python", "actions/upload-artifact"}
    runs = [s for s in c["steps"] if "scripts/" in s.get("run", "")]
    assert len(runs) == 1 and runs[0]["run"] == COMPUTE_RUN
    up = next(s for s in c["steps"] if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert up["with"]["name"] == ARTIFACT and up["with"]["if-no-files-found"] == "error"
    for bad in ("id-token", "google-github-actions", "--write", "RISK_CAP_HISTORY", "credentials_json"):
        assert bad not in _code(ct), bad

    # ── write：只限 main、needs compute、id-token、job 層 concurrency、閘門在任何 auth 之前 ──
    w, wt = jobs["production_write"], _job_text(text, "production_write")
    assert w["if"] == "${{ inputs.mode == 'production-write' && github.ref == 'refs/heads/main' }}"
    assert w.get("needs") == "production_write_compute"
    assert w["permissions"] == {"contents": "read", "id-token": "write"}
    # 📌 2026-10-20（Pre-Hardening 批；有意識的變更，不是漏刪）：~~group: risk-cap-history-production-write~~
    #   改為碰 Sheet 的 job 共用的字面 group（跨 job 序列化；守衛另見 `tests/test_vn1_prehardening.py`）。
    assert w.get("concurrency") == {"group": SHEET_WRITE_GROUP, "cancel-in-progress": False}
    # 📌 2026-10-21（DEC-066 C Step 2；有意識的變更，不是漏刪）：
    #   ~~set(w) == {"if", "needs", "runs-on", "timeout-minutes", "permissions", "concurrency", "steps"}~~
    #   多 `environment`（客戶已建立 Environment `production-risk-cap`＝Step 1；只准本 job 引用、job 層純字串）；
    #   「其他 job／其他 workflow 不得有」與步驟序列不變的守衛在 `tests/test_vn1_prehardening.py` E 節。
    assert set(w) == {"if", "needs", "environment", "runs-on", "timeout-minutes", "permissions", "concurrency",
                      "steps"}, set(w)
    assert w["environment"] == "production-risk-cap"
    _pinned(w, wt)
    steps = w["steps"]
    assert steps[0]["uses"].startswith("actions/checkout@") and steps[0]["with"] == {"persist-credentials": False}
    i_gate = [i for i, s in enumerate(steps) if s.get("run") == GATE_RUN]
    assert i_gate == [1], i_gate                                   # checkout 之後的第一步
    auth = _auth_step(w)
    i_auth = steps.index(auth)
    assert i_gate[0] < i_auth
    assert all("google-github-actions" not in s.get("uses", "") for s in steps[:i_auth])
    assert auth["with"] == _auth_step(jobs["wif_auth_only"])["with"] and "env" not in auth
    i_write = [i for i, s in enumerate(steps) if s.get("run") == WRITE_RUN]
    assert len(i_write) == 1 and i_auth < i_write[0] == len(steps) - 1
    dl = [i for i, s in enumerate(steps) if s.get("uses", "").startswith("actions/download-artifact@")]
    assert len(dl) == 1 and dl[0] < i_auth and steps[dl[0]]["with"]["name"] == ARTIFACT
    # 📌 2026-10-20（Pre-Hardening 批）：只裝 hash 鎖定依賴（在閘門之後）；⛔ 不裝 requirements.txt
    pips = [i for i, s in enumerate(steps) if "pip install" in s.get("run", "")]
    assert len(pips) == 1 and steps[pips[0]]["run"] == WRITER_PIP_RUN and i_gate[0] < pips[0] < i_auth
    assert "requirements.txt" not in _code(wt).replace("requirements-risk-cap-writer.txt", "")
    # 下載後、任何 auth 之前比對 compute job 的 sha256
    sha = [i for i, s in enumerate(steps) if s.get("run") == SHA_CHECK_RUN]
    assert len(sha) == 1 and dl[0] < sha[0] < i_auth
    assert steps[sha[0]]["env"] == {
        "EXPECTED_RECORD_SHA256": "${{ needs.production_write_compute.outputs.record_sha256 }}"}
    # env：只有 sha 比對與寫入兩步有；寫入那一步只有 System Risk Cap Sheet ID ＋寫入總開關
    # （📌 2026-10-20 有意識的放寬：原「只有寫入那一步有 env」多准 sha 比對步驟，其 env 只有 compute job 的 sha256）
    assert [i for i, s in enumerate(steps) if "env" in s] == sha + i_write
    assert steps[i_write[0]]["env"] == {
        P.HISTORY_SHEET_ID_ENV_VAR: "${{ secrets.RISK_CAP_HISTORY_SHEET_ID }}",
        P.WRITE_ENABLE_ENV_VAR: "1",
    }
    wc = _code(wt)
    assert set(re.findall(r"secrets\.([A-Z0-9_]+)", wc)) == {"RISK_CAP_HISTORY_SHEET_ID"}
    for bad in ("PORTFOLIO_SHEET_ID", "STOCK_PORTFOLIO_SHEET_ID", "GCP_SERVICE_ACCOUNT_JSON", "FINMIND", "PROXY",
                "NAS_", "credentials_json", "token_format", "RISK_CAP_READER_TEST_SA_JSON", "contents: write",
                "git push", "--simulate-rerun"):
        assert bad not in wc, bad
    # `--write` 全檔只在寫入 job
    outside = text.replace(wt, "")
    assert "--write" not in _code(outside)
    assert "credentials_json" not in text and "schedule:" not in text and "cron:" not in text


class TestWorkflow:
    def test_guards(self):
        assert_production_write_guards(_wf())

    def test_no_other_workflow_writes_risk_cap(self):
        for f in sorted((REPO / ".github/workflows").glob("*.y*ml")):
            if f.name == Path(WORKFLOW_REL).name:
                continue
            code = "\n".join(ln for ln in f.read_text(encoding="utf-8").splitlines()
                             if not ln.lstrip().startswith("#"))          # 註解提到 PoC 檔名不算
            assert "risk_cap_history_poc.py" not in code and "--write" not in code, f.name
            assert "risk-cap-writer" not in code, f.name


class TestWorkflowMutations:
    @staticmethod
    def _in(job: str, old: str, new: str) -> str:
        text = _wf()
        block = _job_text(text, job)
        assert block.count(old) == 1, (job, old)
        return text.replace(block, block.replace(old, new))

    def test_auth_before_gate_turns_red(self):
        text = _wf()
        block = _job_text(text, "production_write")
        gate = ("      # 只 import L0（標準函式庫）⇒ 系統 python3 即可；未核准 ⇒ exit 2 紅燈，後續步驟（含 auth）全部不跑。\n"
                "      - name: Production write gate (must pass before any auth)\n"
                f"        run: {GATE_RUN}\n\n")
        assert block.count(gate) == 1
        auth_start = block.index("      # 與 wif_auth_only 完全相同的 auth 輸入")
        auth_end = block.index("      # Sheet ID 只從 secrets")
        auth = block[auth_start:auth_end]
        moved = block.replace(gate, "").replace(auth, auth + gate)
        with pytest.raises(AssertionError):
            assert_production_write_guards(text.replace(block, moved))

    @pytest.mark.parametrize("job,old,new", [
        ("production_write", f"        run: {GATE_RUN}\n", "        run: echo skip\n"),
        ("production_write", "      RISK_CAP_HISTORY_WRITE_ENABLED: '1'\n".replace("      ", "          ", 1),
         "          RISK_CAP_HISTORY_WRITE_ENABLED: '1'\n          PORTFOLIO_SHEET_ID: ${{ secrets.PORTFOLIO_SHEET_ID }}\n"),
        ("production_write", " && github.ref == 'refs/heads/main' }}", " }}"),
        ("production_write", "    needs: production_write_compute\n", ""),
        # 2026-10-21（DEC-066 C Step 2）：拿掉／改名 environment ⇒ 紅
        ("production_write", "    environment: production-risk-cap\n", ""),
        ("production_write", "    environment: production-risk-cap\n", "    environment: production\n"),
        ("production_write", "      cancel-in-progress: false\n", "      cancel-in-progress: true\n"),
        ("production_write", "google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093 # v3.0.0",
         "google-github-actions/auth@v3"),
        ("production_write", "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4.3.0",
         "actions/download-artifact@v4"),
        ("production_write", "          export_environment_variables: true\n",
         "          export_environment_variables: true\n          credentials_json: ${{ secrets.GCP_SERVICE_ACCOUNT_JSON }}\n"),
        ("production_write_compute", "    permissions:\n      contents: read\n",
         "    permissions:\n      contents: read\n      id-token: write\n"),
        ("production_write_compute", "        if: github.ref != 'refs/heads/main'\n", ""),
        ("production_write_compute", f"        run: {COMPUTE_RUN}\n", f"        run: {COMPUTE_RUN} --write\n"),
        # 回修第 1 輪（2026-10-20）：sha 步驟拿掉 bash／pipefail ⇒ 紅
        ("production_write_compute", "        shell: bash\n", ""),
        ("production_write_compute", "set -euo pipefail; ", ""),
    ])
    def test_mutation_turns_red(self, job, old, new):
        with pytest.raises(AssertionError):
            assert_production_write_guards(self._in(job, old, new))

    def test_schedule_turns_red(self):
        t = _wf()
        assert t.count("on:\n  workflow_dispatch:\n") == 1
        with pytest.raises(AssertionError):
            assert_production_write_guards(t.replace("on:\n  workflow_dispatch:\n",
                                                     "on:\n  schedule:\n    - cron: '0 9 * * *'\n  workflow_dispatch:\n"))


def test_ruleset_default_used():
    """讀取端預設比較的規則版本＝現行版本（⛔ 本批不改規則語意）。"""
    import inspect
    assert inspect.signature(R.read_history).parameters["ruleset_version"].default == RISK_CAP_RULESET_VERSION
