"""離線契約測試 — scripts/push_weekly_report.main() 的 fail-loud 與送出契約（DEC-178 Quality Batch 2 ④-A）。

範圍（誠實界線）：這是 **離線 orchestrator 契約測試**，全程 monkeypatch、不連網、不讀任何資料檔。
它**不是** Production E2E，也**不證明** LINE 實際送達、GitHub Secrets（WEEKLY_WATCH_CSV_URL /
GEMINI_API_KEY / LINE 憑證）有效、或週報內容的投資有效性 —— 以上皆 NOT VERIFIED。

釘住的契約（`main()` 內 3 處 `return 1` 是「不送空/假訊息」的唯一保護，原本無任何測試呼叫 `main(`）：
  1. 無 CSV URL → rc=1 且不送、不呼叫 collect_tickers。
  2. collect_tickers 失敗（含真實 collect_tickers 包裝後的例外）→ rc=1、不送、輸出不含 URL。
  3. 解析 0 代號 → rc=1、不送、不呼叫 build_weekly_review。
  4. 正常 → rc=0、送 1 次、訊息含 `format_weekly_message` 標頭「📊 本週組合週報」。
  5. --dry-run → rc=0、不送。
  6. GEMINI_API_KEY 有 → build_weekly_review 收到該 key；無/空 → 收到 None。
突變反向驗證：用 tests/_fina_mutants.py::load_mutant 把 `if not _urls:` / `if not _tickers:` /
`if args.dry_run:` 各改成 `if False:`，對應契約必須轉紅（原碼為綠的對照在同一測試內）。
golden 只釘 rc、送出次數與結構性子字串，不釘含日期的全文。
"""
from __future__ import annotations

import pytest

import scripts.push_weekly_report as W
import src.data.notify.dispatch as D
import src.services.weekly_review_service as WRS
from tests._fina_mutants import load_mutant, load_real

_REL = "scripts/push_weekly_report.py"
_SECRET_URL = "https://docs.example.invalid/spreadsheets/d/SECRET-SHEET-ID-9f3a/pub?output=csv"
_HEADER = "📊 本週組合週報"

# 合成 review（非真實資料）：1 檔亮警示、1 檔正常，AI 缺席 → 走 format_weekly_message 的誠實降級分支。
_FAKE_REVIEW = {
    "macro_lines": ["加權指數：（合成測試資料）"],
    "rows": [{"代號": "2330", "燈號": "🔴 連續落後", "相對基準%": -3.5},
             {"代號": "0050", "燈號": "🟢 正常"}],
    "ai_text": None,
}


def _run(mod, argv=(), *, env=None, tickers=("2330", "0050"), collect_raises=None,
         http_raises=None, capsys=None):
    """在隔離的 monkeypatch 下跑 `mod.main(argv)`，回 (rc, sent, calls, out)。

    mod 可為真實模組或 load_mutant 出來的突變模組（兩者走同一個 harness）。
    `collect_raises`: 替換 mod.collect_tickers 為拋例外版；`http_raises`: 讓 requests.get 拋例外，
    走**真實** collect_tickers 的包裝（驗證 URL 不外洩）。其餘情況 collect_tickers 回固定 tickers
    （與 URL 是否為空無關 → 才能分辨「URL 檢查」與「0 代號檢查」兩道保護）。
    """
    env = env or {}
    sent: list[str] = []
    calls = {"collect": 0, "urls": [], "review": []}
    with pytest.MonkeyPatch.context() as mp:
        for k in ("WEEKLY_WATCH_CSV_URL", "GEMINI_API_KEY"):
            mp.delenv(k, raising=False)
        for k, v in env.items():
            mp.setenv(k, v)

        if http_raises is None:
            def _collect(urls, **kw):
                calls["collect"] += 1
                calls["urls"].append(list(urls))
                if collect_raises is not None:
                    raise collect_raises
                return list(tickers)
            mp.setattr(mod, "collect_tickers", _collect)
        else:
            import requests

            def _get(*a, **k):
                raise http_raises
            mp.setattr(requests, "get", _get)

        def _review(tks, *, api_key=None, as_of=""):
            calls["review"].append({"tickers": list(tks), "api_key": api_key})
            return dict(_FAKE_REVIEW)
        mp.setattr(WRS, "build_weekly_review", _review)
        mp.setattr(D, "send_notification", lambda text, **k: (sent.append(text), 1)[1])

        rc = mod.main(list(argv))
    out = capsys.readouterr().out if capsys is not None else ""
    return rc, sent, calls, out


# ───────────────────────── 契約斷言（真實模組與突變模組共用）─────────────────────────
def _check_no_url(mod, capsys):
    rc, sent, calls, out = _run(mod, capsys=capsys)            # 無 env、無 --csv-url
    assert rc == 1
    assert sent == [], "無 URL 時不得送出任何訊息"
    assert calls["collect"] == 0 and calls["review"] == [], "無 URL 不得往下取數/組週報"
    assert "WEEKLY_WATCH_CSV_URL" in out


def _check_zero_tickers(mod, capsys):
    rc, sent, calls, out = _run(mod, env={"WEEKLY_WATCH_CSV_URL": _SECRET_URL},
                                tickers=(), capsys=capsys)
    assert rc == 1
    assert sent == [], "0 代號不得送出（§1 不送空訊息）"
    assert calls["review"] == [], "0 代號不得呼叫 build_weekly_review"
    assert "0 個台股代號" in out


def _check_dry_run(mod, capsys):
    rc, sent, calls, out = _run(mod, ["--dry-run"], env={"WEEKLY_WATCH_CSV_URL": _SECRET_URL},
                                capsys=capsys)
    assert rc == 0
    assert sent == [], "--dry-run 不得送出"
    assert _HEADER in out and "(dry-run)" in out, "dry-run 應把訊息印出供本地驗證"


# ───────────────────────── fail-loud 分支 ─────────────────────────
def test_no_url_returns_1_and_does_not_send(capsys):
    _check_no_url(W, capsys)


def test_csv_url_flag_overrides_missing_env(capsys):
    """--csv-url 可在無 env 時提供來源 → 不走「未設定」分支。"""
    rc, sent, calls, _ = _run(W, ["--csv-url", _SECRET_URL], capsys=capsys)
    assert rc == 0 and len(sent) == 1 and calls["collect"] == 1


def test_collect_tickers_exception_returns_1_no_send_no_url_in_output(capsys):
    """走**真實** collect_tickers：requests.get 的例外訊息內含 URL，輸出不得洩漏。"""
    rc, sent, calls, out = _run(
        W, env={"WEEKLY_WATCH_CSV_URL": _SECRET_URL},
        http_raises=ConnectionError(f"boom {_SECRET_URL}"), capsys=capsys)
    assert rc == 1
    assert sent == [] and calls["review"] == []
    assert "抓取失敗" in out and "第 1/1 份來源處理失敗" in out, "應能定位是第幾份來源壞掉"
    assert _SECRET_URL not in out and "SECRET-SHEET-ID" not in out, "輸出不得洩漏 CSV 連結"
    assert "0 個台股代號" not in out, "例外分支須自己 return 1，不得落入『0 代號』分支（獨立守住 except 的 return）"


def test_collect_tickers_stub_exception_returns_1_no_send(capsys):
    rc, sent, calls, out = _run(W, env={"WEEKLY_WATCH_CSV_URL": _SECRET_URL},
                                collect_raises=RuntimeError("第 1/1 份來源處理失敗(X)"),
                                capsys=capsys)
    assert rc == 1 and sent == [] and calls["review"] == []
    assert _SECRET_URL not in out
    assert "0 個台股代號" not in out, "例外分支須自己 return 1，不得落入『0 代號』分支"


def test_zero_tickers_returns_1_and_does_not_send(capsys):
    _check_zero_tickers(W, capsys)


# ───────────────────────── 送出契約 ─────────────────────────
def test_normal_run_sends_exactly_once_with_header(capsys):
    rc, sent, calls, out = _run(W, env={"WEEKLY_WATCH_CSV_URL": _SECRET_URL}, capsys=capsys)
    assert rc == 0
    assert len(sent) == 1, "正常路徑應恰送出 1 次"
    _t = sent[0]
    assert _t.startswith(_HEADER), f"標頭應為「{_HEADER}（日期）」，實得 {_t[:20]!r}"
    # 結構性子字串（不釘日期/全文）：真實 format_weekly_message 對合成 review 的輸出
    assert "〔大盤定調〕" in _t and "〔逐檔體檢〕" in _t
    assert "2330｜🔴 連續落後" in _t, "亮警示的檔應列出"
    assert "非投資建議" in _t
    assert "AI 研判本次未產生" in _t, "AI 缺席時誠實註明，仍送真實數據摘要"
    assert calls["review"][0]["tickers"] == ["2330", "0050"]
    assert "追蹤 2 檔" in out and "已送出 1 則" in out


def test_dry_run_returns_0_and_does_not_send(capsys):
    _check_dry_run(W, capsys)


def test_multi_line_urls_passed_through_as_list(capsys):
    """多行 URL（ETF 分頁 + 個股分頁）→ 來源份數反映在輸出；collect_tickers 收到去重後的 list。"""
    _multi = _SECRET_URL + "\n" + _SECRET_URL + "\nhttps://b.example.invalid/x\n"
    rc, sent, calls, out = _run(W, env={"WEEKLY_WATCH_CSV_URL": _multi}, tickers=("2330",),
                                capsys=capsys)
    assert rc == 0 and len(sent) == 1
    assert calls["urls"] == [[_SECRET_URL, "https://b.example.invalid/x"]]
    assert "來源 2 份" in out


# ───────────────────────── GEMINI_API_KEY 傳遞 ─────────────────────────
def test_gemini_key_present_is_forwarded(capsys):
    _, _, calls, _ = _run(W, env={"WEEKLY_WATCH_CSV_URL": _SECRET_URL, "GEMINI_API_KEY": "k-test"},
                          capsys=capsys)
    assert calls["review"][0]["api_key"] == "k-test"


@pytest.mark.parametrize("env_val", [None, ""])
def test_gemini_key_absent_or_empty_becomes_none(env_val, capsys):
    env = {"WEEKLY_WATCH_CSV_URL": _SECRET_URL}
    if env_val is not None:
        env["GEMINI_API_KEY"] = env_val
    _, _, calls, _ = _run(W, env=env, capsys=capsys)
    assert calls["review"][0]["api_key"] is None, "無/空 key 應傳 None（略過 AI，不得傳空字串）"


# ───────────────────────── 突變反向驗證（拔掉保護必須轉紅）─────────────────────────
MUTANTS = {
    "drop_url_guard": ("    if not _urls:\n", "    if False:\n", _check_no_url),
    "drop_zero_ticker_guard": ("    if not _tickers:\n", "    if False:\n", _check_zero_tickers),
    "drop_dry_run_guard": ("    if args.dry_run:\n", "    if False:\n", _check_dry_run),
}


def test_harness_loads_unmutated_source():
    """對照組：load_real 載得起來、行為與直接 import 一致。"""
    assert callable(load_real(_REL).main)


@pytest.mark.parametrize("name", list(MUTANTS))
def test_mutant_is_killed(name, capsys):
    old, new, chk = MUTANTS[name]
    chk(load_real(_REL), capsys)                       # 原碼（同 harness）為綠
    mut = load_mutant(_REL, old, new, name=f"_wk_{name}")
    with pytest.raises(AssertionError):                # 拔掉保護 → 契約轉紅
        chk(mut, capsys)
